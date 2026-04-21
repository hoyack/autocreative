"""Post-render audit: whitespace + contrast + content-budget density.

``audit_render(content, template, rendered_png_bytes, *, side='outside')``
returns an ``AuditReport`` that the iterate loop uses to decide whether
to re-render.

Whitespace: per-panel ratio of pixels within a tolerance of the panel's
effective background color. 1.0 = fully empty, 0.0 = every pixel
differs from bg.

Contrast: walk every text-bearing element in the template, compute the
effective bg color (stacking shapes by z-order would be ideal but Phase
18 uses the panel's ``background`` fill as a first-pass approximation --
RESEARCH.md flags this as a simplification), and emit a ``ContrastPair``
per (text color, bg color).

Density: for each ``content_key`` resolved to text, compute a character
budget from the element's bbox via ``text_fit.chars_per_line`` * allowed
line count, then ``len(resolved) / budget``.

The iterate loop re-renders up to ``max_cycles`` times, applying bounded
remediation. Phase 18 remediation is restricted to:
  * ``remediate_contrast`` -- opposite-neutral swap via apply_brand_kit (W10a).
  * ``remediate_density`` -- tighter-budget text_gen regen (caller-supplied
    ``regenerate_fn``) for under-filled regions (W10b). Audit module does
    NOT call the LLM itself.

Edit-in-place LLM rewrites are OUT OF SCOPE (CONTEXT.md §"Audit loop
remediation scope").

W16: BulletsElement font size is sourced from ``template.typography.bullet_size``
(falls back to 32 only when attribute missing -- never true in production).

B1: this module does NOT write to ``flyer_generator/brand_kit/__init__.py``.
Plan 07 owns consolidated re-exports; direct-module imports only.
B3: imports ``BrandKitAuditError`` from ``flyer_generator.errors``.
"""

from __future__ import annotations

import io
import uuid
from collections.abc import Awaitable, Callable
from typing import Literal

import structlog
from PIL import Image
from pydantic import BaseModel, ConfigDict, Field

from flyer_generator.brand_kit.applier import apply_brand_kit
from flyer_generator.brand_kit.contrast import (
    ContrastPair,
    ContrastReport,
    classify_level,
    wcag_ratio,
)
from flyer_generator.brand_kit.models import (
    BrandKit,
    BrandPalette,
    ColorUsage,
)
from flyer_generator.brochure.schema_renderer.content_model import BrochureContent
from flyer_generator.brochure.schema_renderer.schema_model import (
    BulletsElement,
    PanelSchema,
    TemplateSchema,
    TextElement,
)
from flyer_generator.brochure.schema_renderer.text_fit import chars_per_line
from flyer_generator.errors import BrandKitAuditError

logger = structlog.get_logger()


# ---- Pydantic models ----------------------------------------------------


class AuditIssue(BaseModel):
    """A single issue raised by ``audit_render``."""

    model_config = ConfigDict(extra="forbid")

    severity: Literal["info", "warn", "error"]
    category: Literal["whitespace", "contrast", "density"]
    panel: str | None = None
    content_key: str | None = None
    detail: str
    suggested_remediation: str | None = None


class AuditReport(BaseModel):
    """Aggregate verdict: whitespace density per panel, contrast pairs, content-key fill, issues."""

    model_config = ConfigDict(extra="forbid")

    whitespace: dict[str, float] = Field(default_factory=dict)
    contrast: ContrastReport = Field(default_factory=ContrastReport)
    density: dict[str, float] = Field(default_factory=dict)
    issues: list[AuditIssue] = Field(default_factory=list)
    cycle: int = 0

    @property
    def is_clean(self) -> bool:
        """No FAIL contrast, no WARN/ERROR issues (info is fine)."""
        if not self.contrast.overall_aa_pass:
            return False
        return not any(i.severity in ("warn", "error") for i in self.issues)


# ---- Helpers ------------------------------------------------------------


_WHITESPACE_THRESHOLD = 0.85
_DENSITY_LOW_THRESHOLD = 0.50
_TOLERANCE = 12
# Denominator reject for oversize PNGs (see T-18-AUDIT-01 threat register).
_MAX_IMAGE_MP = 50_000_000
_OUTSIDE_ORDER: tuple[str, str, str] = ("back_cover", "tuck_flap", "front_cover")
_INSIDE_ORDER: tuple[str, str, str] = ("inner_left", "inner_center", "inner_right")


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    h = hex_color.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def _panel_bg_hex(panel: PanelSchema, palette_fallback: str = "#FAFAF7") -> str:
    """Extract the panel's effective background hex color (first-pass approximation).

    Shape-stacking (z-order + opacity) is deferred to Phase 19; this returns
    the panel's ``background`` fill color when it's a SolidFill hex, else the
    palette fallback.
    """
    bg = panel.background
    if bg is None:
        return palette_fallback
    color_attr = getattr(bg, "color", None)
    if isinstance(color_attr, str) and color_attr.startswith("#"):
        return color_attr
    return palette_fallback


def _panel_whitespace_ratio(
    img: Image.Image,
    crop_rect: tuple[int, int, int, int],
    bg_hex: str,
    *,
    tolerance: int = _TOLERANCE,
) -> float:
    """Ratio of pixels near bg color within the crop. Downsampled for speed."""
    x, y, w, h = crop_rect
    panel = img.crop((x, y, x + w, y + h))
    # Downsample: each dimension / 15 -> ~225x reduction in pixel count.
    scale_denom = 15
    panel_small = panel.resize(
        (max(1, w // scale_denom), max(1, h // scale_denom)),
        Image.Resampling.LANCZOS,
    )
    br, bgc, bb = _hex_to_rgb(bg_hex)
    # Pillow 14 deprecates ``getdata``; ``tobytes()`` is the forward-compatible
    # accessor and yields raw R,G,B,R,G,B,... bytes for an RGB-mode image.
    raw = panel_small.tobytes()
    total = len(raw) // 3
    hits = 0
    for i in range(0, len(raw), 3):
        pr, pg, pbc = raw[i], raw[i + 1], raw[i + 2]
        if (
            abs(pr - br) <= tolerance
            and abs(pg - bgc) <= tolerance
            and abs(pbc - bb) <= tolerance
        ):
            hits += 1
    return hits / max(1, total)


def _panel_crop_rect(
    side: str, panel_name: str, sheet_w: int, sheet_h: int
) -> tuple[int, int, int, int]:
    """Return the (x, y, w, h) crop rect for a given panel on the sheet.

    Panels on a sheet are laid out left-to-right in one of two fixed orders
    (outside vs. inside); a panel not in the expected order returns a zero
    rect so the caller can skip it.
    """
    order = _OUTSIDE_ORDER if side == "outside" else _INSIDE_ORDER
    try:
        idx = order.index(panel_name)
    except ValueError:
        return (0, 0, 0, 0)
    panel_w = sheet_w // 3
    x = idx * panel_w
    return (x, 0, panel_w, sheet_h)


def _collect_text_elements(
    panel: PanelSchema,
    template: TemplateSchema,
) -> list[tuple[str, str, tuple[float, float, float, float], int]]:
    """Return [(content_key_or_static, color_hex, bbox, font_size), ...].

    W16: BulletsElement font_size is sourced from ``template.typography.bullet_size``
    (falls back to 32 only when the attribute is missing -- documented
    approximation because BulletsElement itself doesn't carry a per-element
    font_size field for audit-time measurement).
    """
    bullet_size = int(getattr(template.typography, "bullet_size", 32))
    out: list[tuple[str, str, tuple[float, float, float, float], int]] = []
    for el in panel.elements:
        if isinstance(el, TextElement):
            color = el.color or "#000000"
            key = el.content_key or f"static:{el.static_text or el.role}"
            font_size = int(el.font_size or 32)
            bbox = (
                float(el.bbox[0]),
                float(el.bbox[1]),
                float(el.bbox[2]),
                float(el.bbox[3]),
            )
            out.append((key, color, bbox, font_size))
        elif isinstance(el, BulletsElement):
            color = el.text_color or "#000000"
            key = el.content_key
            # W16: BulletsElement may have its own font_size override (set on
            # the element in some templates). Prefer the element's own value
            # when provided; otherwise fall back to typography.bullet_size.
            font_size = int(el.font_size or bullet_size)
            bbox = (
                float(el.bbox[0]),
                float(el.bbox[1]),
                float(el.bbox[2]),
                float(el.bbox[3]),
            )
            out.append((key, color, bbox, font_size))
    return out


def _estimate_char_budget(
    bbox: tuple[float, float, float, float], font_size: int, line_height: int
) -> int:
    """Approximate char budget: chars_per_line * max_lines (ceil)."""
    _, _, w, h = bbox
    cpl = chars_per_line(w, font_size)
    max_lines = max(1, int(h / max(1, line_height)))
    return cpl * max_lines


# ---- Shared primitives (B-04) -------------------------------------------


def scan_text_contrast(
    palette: BrandPalette,
    text_over_bg_pairs: list[tuple[str, str]],
) -> ContrastReport:
    """Produce a ContrastReport from a list of (fg_hex, bg_hex) pairs.

    Pure function: no template/panel knowledge, no I/O. Callers (brochure
    ``audit_render``, social ``audit_post``) derive the pair list from their
    own layout + palette mapping and pass it in.

    Classifies each pair as body-text (large_text=False). Callers who need
    large-text classification should pre-filter and call ``classify_level``
    directly; this primitive is kept minimal for reuse.

    Args:
        palette: The brand palette (unused by the primitive itself but
            accepted in the signature so callers can't forget to supply
            a palette-consistent pair list; keeps the primitive traceable).
        text_over_bg_pairs: [(fg_hex, bg_hex), ...] -- every pair is scanned.

    Returns:
        ContrastReport with one ContrastPair per input pair.
    """
    del palette  # accepted for traceability; primitive itself does not use it
    pairs: list[ContrastPair] = []
    for fg_hex, bg_hex in text_over_bg_pairs:
        try:
            ratio = wcag_ratio(fg_hex, bg_hex)
            level = classify_level(fg_hex, bg_hex, large_text=False)
        except Exception as err:  # noqa: BLE001 -- soft-fail per pair (matches audit_render semantics)
            logger.warning(
                "scan_text_contrast_error",
                fg=fg_hex,
                bg=bg_hex,
                error=str(err),
            )
            continue
        pairs.append(
            ContrastPair(
                fg=fg_hex,
                bg=bg_hex,
                ratio=max(1.0, min(21.0, ratio)),
                level=level,
            )
        )
    return ContrastReport(pairs=pairs)


def scan_image_density(
    png_bytes: bytes,
    regions: list[tuple[int, int, int, int]],
) -> dict[str, float]:
    """Compute a per-region fill fraction (1.0 - whitespace_ratio against neutral bg).

    Args:
        png_bytes: PNG bytes. Subject to the 50 MP safety cap (T-18-AUDIT-01).
        regions: [(x, y, w, h), ...]. Returned dict keys are ``f"region_{i}"``.

    Returns:
        dict mapping region key to fill fraction in [0.0, 1.0]. 1.0 = fully
        filled (no whitespace). 0.0 = effectively empty.

    Raises:
        BrandKitAuditError: unreadable PNG or > 50 MP.
    """
    if not regions:
        return {}
    try:
        img = Image.open(io.BytesIO(png_bytes)).convert("RGB")
    except Exception as err:  # noqa: BLE001 -- untrusted bytes
        raise BrandKitAuditError(
            "could not open rendered PNG",
            error=str(err),
        ) from err
    w_img, h_img = img.size
    if w_img * h_img > _MAX_IMAGE_MP:
        raise BrandKitAuditError(
            "rendered PNG exceeds 50 MP cap",
            width=w_img,
            height=h_img,
        )
    # Use the neutral_light approximation as "background" since scan_image_density
    # lives outside the template context. Callers wanting template-aware bg should
    # call _panel_whitespace_ratio directly.
    bg_hex = "#FAFAF7"
    out: dict[str, float] = {}
    for i, (x, y, rw, rh) in enumerate(regions):
        if rw <= 0 or rh <= 0:
            out[f"region_{i}"] = 0.0
            continue
        # Clamp region to image bounds
        rx = max(0, min(int(x), w_img))
        ry = max(0, min(int(y), h_img))
        rw_c = max(0, min(int(rw), w_img - rx))
        rh_c = max(0, min(int(rh), h_img - ry))
        if rw_c <= 0 or rh_c <= 0:
            out[f"region_{i}"] = 0.0
            continue
        whitespace_ratio = _panel_whitespace_ratio(img, (rx, ry, rw_c, rh_c), bg_hex)
        out[f"region_{i}"] = max(0.0, min(1.0, 1.0 - whitespace_ratio))
    return out


# ---- audit_render -------------------------------------------------------


def audit_render(
    content: BrochureContent,
    template: TemplateSchema,
    rendered_png_bytes: bytes,
    *,
    side: Literal["outside", "inside"] = "outside",
    cycle: int = 0,
) -> AuditReport:
    """Produce an ``AuditReport`` for a rendered sheet.

    Args:
        content: Resolved content model (supplies per-key text for density).
        template: Source template (supplies panels, palette, typography).
        rendered_png_bytes: A rendered sheet (outside or inside) as PNG bytes.
        side: Which panel-order to apply when cropping (``outside`` vs. ``inside``).
        cycle: Loop cycle number (0 for first pass).

    Raises:
        BrandKitAuditError: when the PNG is unreadable or exceeds the 50 MP
            cap (T-18-AUDIT-01).
    """
    try:
        img = Image.open(io.BytesIO(rendered_png_bytes)).convert("RGB")
    except Exception as err:  # noqa: BLE001 -- untrusted PNG bytes (T-18-AUDIT-01)
        raise BrandKitAuditError(
            "could not open rendered PNG",
            cycles=cycle,
            error=str(err),
        ) from err
    sheet_w, sheet_h = img.size
    if sheet_w * sheet_h > _MAX_IMAGE_MP:
        raise BrandKitAuditError(
            "rendered PNG exceeds 50 MP cap",
            cycles=cycle,
            width=sheet_w,
            height=sheet_h,
        )

    palette_neutral_light = template.palette.neutral_light

    issues: list[AuditIssue] = []
    whitespace: dict[str, float] = {}
    density: dict[str, float] = {}
    contrast_pairs: list[ContrastPair] = []

    panels_on_sheet = _OUTSIDE_ORDER if side == "outside" else _INSIDE_ORDER

    for panel_name in panels_on_sheet:
        panel = template.panels.get(panel_name)
        if panel is None:
            continue
        bg_hex = _panel_bg_hex(panel, palette_fallback=palette_neutral_light)

        crop_rect = _panel_crop_rect(side, panel_name, sheet_w, sheet_h)
        if crop_rect[2] > 0 and crop_rect[3] > 0:
            ratio = _panel_whitespace_ratio(img, crop_rect, bg_hex)
            whitespace[panel_name] = ratio
            # tuck_flap is typically a narrow filled accent panel; skip its
            # whitespace WARN so we don't spam issues for a correctly-designed
            # sheet. All other panels get the threshold check.
            if panel_name != "tuck_flap" and ratio > _WHITESPACE_THRESHOLD:
                issues.append(
                    AuditIssue(
                        severity="warn",
                        category="whitespace",
                        panel=panel_name,
                        detail=(
                            f"panel {panel_name} whitespace ratio {ratio:.2f} "
                            f"exceeds {_WHITESPACE_THRESHOLD:.2f}"
                        ),
                        suggested_remediation=(
                            "increase content budget or regenerate copy with "
                            "tighter fill"
                        ),
                    )
                )

        for key_or_static, fg_hex, bbox, font_size in _collect_text_elements(
            panel, template
        ):
            try:
                ratio = wcag_ratio(fg_hex, bg_hex)
                level = classify_level(
                    fg_hex, bg_hex, large_text=(font_size >= 24)
                )
            except Exception as err:  # noqa: BLE001 -- soft-fail per element
                logger.warning(
                    "audit_contrast_error",
                    fg=fg_hex,
                    bg=bg_hex,
                    error=str(err),
                )
                continue
            contrast_pairs.append(
                ContrastPair(
                    fg=fg_hex,
                    bg=bg_hex,
                    ratio=max(1.0, min(21.0, ratio)),
                    level=level,
                    panel=panel_name,
                    content_key=key_or_static,
                )
            )
            if level == "FAIL":
                issues.append(
                    AuditIssue(
                        severity="error",
                        category="contrast",
                        panel=panel_name,
                        content_key=key_or_static,
                        detail=f"{fg_hex} on {bg_hex} = {ratio:.2f} < 4.5 (AA)",
                        suggested_remediation=(
                            "swapped to opposite neutral from kit palette"
                        ),
                    )
                )

            # Density only makes sense for real content keys, not static text.
            if key_or_static.startswith("static:"):
                continue
            try:
                resolved = content.resolve_key(key_or_static)
            except Exception:  # noqa: BLE001 -- resolver may raise on bad key
                resolved = None
            if resolved is None:
                continue
            if isinstance(resolved, str):
                text_str = resolved
            elif isinstance(resolved, (list, tuple)):
                text_str = " ".join(str(x) for x in resolved)
            else:
                text_str = str(resolved)
            line_height = int(font_size * 1.35)
            budget = _estimate_char_budget(bbox, font_size, line_height)
            fill = len(text_str) / max(1, budget)
            density[key_or_static] = fill
            if fill < _DENSITY_LOW_THRESHOLD:
                issues.append(
                    AuditIssue(
                        severity="info",
                        category="density",
                        panel=panel_name,
                        content_key=key_or_static,
                        detail=(
                            f"content_key {key_or_static!r} fills "
                            f"{fill * 100:.0f}% of budget "
                            f"({len(text_str)}/{budget})"
                        ),
                        suggested_remediation=(
                            "regenerate with tighter budget or expand content"
                        ),
                    )
                )

    return AuditReport(
        whitespace=whitespace,
        contrast=ContrastReport(pairs=contrast_pairs),
        density=density,
        issues=issues,
        cycle=cycle,
    )


# ---- W10 - Concrete remediation closures -------------------------------


async def remediate_contrast(
    content: BrochureContent,
    template: TemplateSchema,
    audit: AuditReport,
    *,
    kit: BrandKit,
) -> tuple[BrochureContent, TemplateSchema]:
    """W10a: contrast remediation via opposite-neutral swap.

    Swaps the kit's ``primary`` to its ``neutral_dark`` and re-applies via
    ``apply_brand_kit``. The applier's inline AA guard picks the opposite
    neutral when the naive swap fails, which propagates to every text
    region that renders against the template's palette.

    If ``audit`` has no contrast failures, returns (content, template)
    unchanged.

    Caller passes ``kit`` with a valid palette; ``apply_brand_kit`` is
    called as ``apply_brand_kit(template, swapped)`` (template FIRST, kit
    SECOND) -- flipping the arg order is the regression the test
    ``test_remediate_contrast_swaps_failing_text`` guards against.
    """
    if audit.contrast.overall_aa_pass:
        return content, template

    if kit.palette is None:
        logger.warning(
            "remediate_contrast_no_palette",
            n_fails=len(audit.contrast.fails()),
        )
        return content, template

    # Swap in a kit where primary = neutral_dark to force the applier's
    # AA guard to pick the opposite neutral. This is a minimal, surgical
    # re-apply -- no other fields touched.
    swapped = kit.model_copy(
        update={
            "palette": kit.palette.model_copy(
                update={
                    "primary": ColorUsage(hex=kit.palette.neutral_dark.hex),
                }
            )
        }
    )
    # NOTE: arg order is (template, kit) -- template first. apply_brand_kit
    # expects the template as its first positional arg (see applier.py:187).
    new_template, _ = apply_brand_kit(template, swapped)
    logger.info(
        "remediate_contrast_applied",
        n_fails_before=len(audit.contrast.fails()),
    )
    return content, new_template


async def remediate_density(
    content: BrochureContent,
    template: TemplateSchema,
    audit: AuditReport,
    *,
    regenerate_fn: Callable[[dict[str, int]], Awaitable[BrochureContent]],
) -> tuple[BrochureContent, TemplateSchema]:
    """W10b: density remediation via caller-supplied regenerate callback.

    Builds a ``tighter_budgets`` dict mapping each under-filled content_key
    to a TARGET char count (~125% of the current resolved length, i.e. the
    new content will fill ~80% of the tighter budget) and invokes
    ``regenerate_fn(tighter_budgets) -> BrochureContent``.

    The audit module does NOT call any LLM itself -- ``regenerate_fn`` is
    the caller's plug-in (Plan 07's integration wires it via
    ``text_gen.generate_content_from_prompt`` with reduced budgets).
    """
    density_issues = [
        i
        for i in audit.issues
        if i.category == "density" and i.severity == "info" and i.content_key
    ]
    if not density_issues:
        return content, template

    # Build tighter_budgets: for each under-filled key, compute a target
    # char count so the new content fills ~80% of the new budget. We derive
    # this from the current resolved length: target = round(len(resolved) * 1.25).
    tighter_budgets: dict[str, int] = {}
    for issue in density_issues:
        key = issue.content_key
        if key is None:
            continue
        try:
            resolved = content.resolve_key(key)
        except Exception:  # noqa: BLE001 -- resolver may raise on bad key
            continue
        resolved_len = len(resolved) if isinstance(resolved, str) else 0
        tighter_budgets[key] = max(24, int(resolved_len * 1.25))

    if not tighter_budgets:
        return content, template

    try:
        new_content = await regenerate_fn(tighter_budgets)
    except Exception as err:  # noqa: BLE001 -- soft-fail: regen is best-effort
        logger.warning("remediate_density_regen_failed", error=str(err))
        return content, template

    logger.info(
        "remediate_density_applied", keys=list(tighter_budgets.keys())
    )
    return new_content, template


# ---- iterate_audit_loop -------------------------------------------------


RenderFn = Callable[
    [BrochureContent, TemplateSchema], Awaitable[tuple[bytes, bytes]]
]
RemediateFn = Callable[
    [BrochureContent, TemplateSchema, AuditReport],
    Awaitable[tuple[BrochureContent, TemplateSchema]],
]


def _make_default_remediate(
    *,
    kit: BrandKit | None,
    regenerate_fn: Callable[[dict[str, int]], Awaitable[BrochureContent]] | None,
) -> RemediateFn | None:
    """Compose remediate_contrast + remediate_density into a single callback.

    Returns None when the caller supplied neither a kit (for contrast) nor
    a regenerate_fn (for density).
    """
    if kit is None and regenerate_fn is None:
        return None

    async def _composite(
        content: BrochureContent,
        template: TemplateSchema,
        audit: AuditReport,
    ) -> tuple[BrochureContent, TemplateSchema]:
        new_content, new_template = content, template
        if kit is not None and not audit.contrast.overall_aa_pass:
            new_content, new_template = await remediate_contrast(
                new_content, new_template, audit, kit=kit
            )
        if regenerate_fn is not None and any(
            i.category == "density" and i.severity == "info"
            for i in audit.issues
        ):
            new_content, new_template = await remediate_density(
                new_content, new_template, audit, regenerate_fn=regenerate_fn
            )
        return new_content, new_template

    return _composite


async def iterate_audit_loop(
    content: BrochureContent,
    template: TemplateSchema,
    *,
    render: RenderFn,
    remediate: RemediateFn | None = None,
    kit: BrandKit | None = None,
    regenerate_fn: Callable[[dict[str, int]], Awaitable[BrochureContent]]
    | None = None,
    max_cycles: int = 3,
    strict: bool = False,
    side: Literal["outside", "inside"] = "outside",
) -> tuple[AuditReport, BrochureContent, TemplateSchema]:
    """Render -> audit -> remediate, up to ``max_cycles``.

    If ``remediate`` is None, the loop composes a default from
    ``remediate_contrast`` (needs ``kit``) + ``remediate_density`` (needs
    ``regenerate_fn``). Passing both kit AND regenerate_fn gives the
    caller the full SC-6 loop with zero bespoke code.

    Args:
        content: Initial resolved content.
        template: Initial template.
        render: Async callable ``(content, template) -> (outside_png, inside_png)``.
        remediate: Optional explicit remediate callback. When None, a default
            is composed from ``kit`` + ``regenerate_fn``.
        kit: Brand kit used by the default composite remediate for contrast.
        regenerate_fn: Caller-supplied LLM regeneration function used by the
            default composite remediate for density.
        max_cycles: Maximum render+audit iterations.
        strict: When True, raise ``BrandKitAuditError`` on exhaustion; when
            False, return the last report unchanged.
        side: Which sheet to audit (``outside`` or ``inside``).

    Returns:
        (final_report, final_content, final_template)
    """
    trace_id = uuid.uuid4().hex
    log = logger.bind(trace_id=trace_id, audit_side=side, max_cycles=max_cycles)
    log.info("audit_loop_start")

    if remediate is None:
        remediate = _make_default_remediate(kit=kit, regenerate_fn=regenerate_fn)

    current_content = content
    current_template = template
    report: AuditReport | None = None

    for cycle in range(max_cycles):
        outside_png, inside_png = await render(current_content, current_template)
        png = outside_png if side == "outside" else inside_png
        report = audit_render(
            current_content, current_template, png, side=side, cycle=cycle
        )
        if report.is_clean:
            log.info("audit_loop_converged", cycle=cycle, issues=0)
            return report, current_content, current_template
        log.warning(
            "audit_loop_cycle_has_issues",
            cycle=cycle,
            n_issues=len(report.issues),
            contrast_fails=len(report.contrast.fails()),
        )
        if remediate is None:
            # No way to make forward progress without a remediate callback;
            # bail out of the loop and return the last report.
            break
        current_content, current_template = await remediate(
            current_content, current_template, report
        )

    assert report is not None  # noqa: S101 -- invariant: loop always ran once
    log.warning(
        "audit_loop_exhausted",
        cycles=max_cycles,
        issues=len(report.issues),
    )
    if strict:
        raise BrandKitAuditError(
            "audit loop exhausted without clean pass",
            cycles=max_cycles,
            remaining_issues=[i.model_dump() for i in report.issues],
        )
    return report, current_content, current_template
