"""End-to-end prompt-driven brochure pipeline.

Orchestrates all 7 stages:
1. Outline (LLM text)
2. Text per section (LLM text, parallel)
3. Layout selection (LLM text)
4. Imagery (ComfyCloud — 1 hero + 0-3 spots)
5. Fit optimization (LLM text for mis-sized sections)
6. Compose (SVG → PNG → PDF)
7. Verify (rubric scoring + optional regen loop)
"""

from __future__ import annotations

import uuid
from typing import Literal

import structlog

from flyer_generator.brochure.generative.fit import optimize_fit
from flyer_generator.brochure.generative.imagery import generate_imagery
from flyer_generator.brochure.generative.layout import choose_layout
from flyer_generator.brochure.generative.models import (
    BrochureOutline,
    BrochurePrompt,
    LayoutChoice,
    SectionSpec,
    SectionText,
    TargetLength,
    VerificationVerdict,
)
from flyer_generator.brochure.generative.outline import generate_outline
from flyer_generator.brochure.generative.text import generate_section_texts
from flyer_generator.brochure.generative.verify import verify_brochure
from flyer_generator.brochure.llm_client import TextClient, build_text_client
from flyer_generator.brochure.models import (
    BrochureInput,
    BrochureOutput,
    BrochureSection,
)
from flyer_generator.brochure.stages.composer import compose_brochure_svgs
from flyer_generator.brochure.stages.layout import (
    BLEED_CANVAS_HEIGHT,
    BLEED_CANVAS_WIDTH,
    compute_panel_layout,
)
from flyer_generator.brochure.stages.pdf import assemble_brochure_pdf
from flyer_generator.brochure.templates import get_template
from flyer_generator.config import Settings
from flyer_generator.stages.rasterizer import Rasterizer

logger = structlog.get_logger()


def _panel_role_to_back_panel_kind(role: str) -> Literal["cta", "bio", "map_stub", "contact"]:
    if role == "cta":
        return "cta"
    if role == "detail":
        return "contact"
    return "bio"


def _assemble_brochure_input(
    prompt: BrochurePrompt,
    outline: BrochureOutline,
    texts: list[SectionText],
) -> BrochureInput:
    """Glue outline + text results into a BrochureInput the composer can render.

    Panel assignment strategy (quality tuning, phase 16):
      1. The cover section drives title + hero_concept.
      2. A 'cta' section becomes the back_panel.
      3. All remaining sections (feature + detail) populate `sections`,
         capped at 5. Sections[0] lands on the tuck flap; sections[1..3] on
         the three inner panels; sections[4] overflows to the inner-right
         compact list. Prefer feature sections before detail sections so
         image_hint-bearing content lands on inside panels.
      4. If sections would have <2 items (minimum for BrochureInput),
         repurpose the cta section as a regular section AND make back_panel None.
    """
    cover_section = next(s for s in outline.sections if s.panel_role == "cover")
    title = cover_section.heading
    # Prefer the outline's dedicated cover_image_concept (describes the hero
    # visually) over body_brief (copywriter direction) over raw prompt slice.
    hero_concept = (
        cover_section.cover_image_concept
        or cover_section.body_brief
        or prompt.prompt[:120]
    )

    # Split into cta vs content sections.
    cta_section = next((s for s in outline.sections if s.panel_role == "cta"), None)
    content_specs = [
        s for s in outline.sections if s.panel_role in ("feature", "detail")
    ]

    # Sort: features first (more likely to have image_hint), then details. Stable.
    content_specs.sort(key=lambda s: 0 if s.panel_role == "feature" else 1)

    # If we have <2 content sections, promote cta into content + drop back_panel.
    promoted_cta = False
    if len(content_specs) < 2 and cta_section is not None:
        content_specs.append(cta_section)
        promoted_cta = True

    # Last-resort: if STILL too few, pad with a concise-org section built from cta_intent.
    if len(content_specs) < 2:
        content_specs.append(
            SectionSpec(
                heading="About",
                body_brief=outline.cta_intent,
                image_hint=None,
                panel_role="detail",
            )
        )

    # Map to BrochureSection using generated body text.
    def _body_for(spec: SectionSpec) -> str:
        match = next((t for t in texts if t.heading == spec.heading), None)
        if match is not None:
            return match.body
        return spec.body_brief

    sections: list[BrochureSection] = []
    for spec in content_specs[:5]:
        sections.append(
            BrochureSection(
                heading=spec.heading,
                body=_body_for(spec),
                icon_hint=spec.image_hint,
            )
        )

    # Back panel (only if cta wasn't promoted into content).
    back_panel = None
    if cta_section is not None and not promoted_cta:
        cta_text = next((t for t in texts if t.heading == cta_section.heading), None)
        if cta_text is not None:
            from flyer_generator.brochure.models import BrochureBackPanel

            back_panel = BrochureBackPanel(
                kind=_panel_role_to_back_panel_kind(cta_section.panel_role),
                content=cta_text.body,
            )

    # Prefer the outline's dedicated org_name over the leaky cta_intent fallback.
    # Old behaviour rendered copywriter directions ("Encourage the reader to
    # book a free initial consultation") on the tuck flap. When org_name is
    # missing, derive a short brand from the cover title.
    derived_org = (outline.org_name or title).strip()[:80]
    org = derived_org if derived_org else "Our Team"

    return BrochureInput(
        title=title,
        subtitle=None,
        hero_concept=hero_concept,
        style_preset=outline.suggested_preset,
        color_accent=outline.suggested_accent,
        org=org,
        sections=sections,
        back_panel=back_panel,
    )


async def generate_brochure_from_prompt(
    prompt: str,
    settings: Settings | None = None,
    *,
    style_preset: str | None = None,
    audience: str | None = None,
    color_accent: str | None = None,
    target_length: TargetLength = "medium",
    verify_threshold: int = 70,
    max_verify_iterations: int = 2,
    text_client: TextClient | None = None,
    workflow_name: str = "turbo_landscape",
    layout_template: str | None = None,
    shape_density: str = "medium",
    accent_placement: str = "side_band",
    cover_treatment: str = "image_full",
) -> BrochureOutput:
    """Prompt-driven end-to-end brochure generation.

    Returns a BrochureOutput with verification metadata attached.
    """
    if settings is None:
        settings = Settings()
    if text_client is None:
        text_client = build_text_client(settings)

    trace_id = uuid.uuid4().hex
    log = logger.bind(trace_id=trace_id)

    # --- Stage 1: outline ---
    brochure_prompt = BrochurePrompt(
        prompt=prompt,
        style_preset=style_preset,
        audience=audience,
        color_accent=color_accent,
        target_length=target_length,
    )
    outline = await generate_outline(brochure_prompt, text_client)
    log.info("brochure_outline_ready", sections=len(outline.sections), tone=outline.tone)

    # --- Stage 2: per-section text (parallel) ---
    texts = await generate_section_texts(outline, text_client, target_length=target_length)
    log.info("brochure_text_ready", count=len(texts))

    # --- Stage 3: layout selection ---
    if layout_template is not None:
        layout_choice = LayoutChoice(
            template=layout_template,  # type: ignore[arg-type]
            shape_density=shape_density,  # type: ignore[arg-type]
            accent_placement=accent_placement,  # type: ignore[arg-type]
            cover_treatment=cover_treatment,  # type: ignore[arg-type]
        )
        log.info("brochure_layout_forced", template=layout_template, density=shape_density)
    else:
        layout_choice = await choose_layout(outline, text_client)
        log.info("brochure_layout_chosen", template=layout_choice.template, density=layout_choice.shape_density)
    template = get_template(layout_choice.template)

    # --- Stage 5: fit optimization (runs before imagery since image gen is expensive) ---
    texts = await optimize_fit(texts, template, text_client, target_length=target_length)
    log.info("brochure_fit_optimized")

    # --- Assemble BrochureInput ---
    brochure_input = _assemble_brochure_input(brochure_prompt, outline, texts)
    log.info("brochure_input_assembled", title=brochure_input.title, n_sections=len(brochure_input.sections))

    # --- Stage 4: imagery ---
    # Hero generation can reject all attempts (vision sees text overlays,
    # distorted subjects, etc). Fall back to a shapes-only cover treatment
    # rather than aborting the whole pipeline: the composer now renders a
    # high-contrast title + accent gradient when the hero is a placeholder.
    from flyer_generator.errors import MaxAttemptsExceededError

    try:
        imagery = await generate_imagery(
            brochure=brochure_input,
            outline=outline,
            layout_choice=layout_choice,
            settings=settings,
            workflow_name=workflow_name,
        )
        log.info("brochure_imagery_ready",
                 has_hero=imagery.hero_png_bytes is not None,
                 n_spots=len(imagery.spot_images))
    except MaxAttemptsExceededError as exc:
        log.warning("brochure_imagery_fallback_shapes_only", error=str(exc)[:200])
        from flyer_generator.brochure.generative.imagery import GeneratedImagery

        imagery = GeneratedImagery(
            hero_png_bytes=None,
            spot_images={},
            hero_vision_verdict=None,
            hero_attempts_used=settings.max_bg_attempts,
        )

    # Placeholder hero when imagery skipped / failed.
    hero_is_placeholder = imagery.hero_png_bytes is None
    hero_bytes = imagery.hero_png_bytes or _placeholder_hero()

    # --- Stage 6: compose + rasterize + PDF ---
    rendered = await _render_and_verify(
        brochure_input=brochure_input,
        outline=outline,
        layout_choice=layout_choice,
        template=template,
        hero_bytes=hero_bytes,
        hero_is_placeholder=hero_is_placeholder,
        spot_images=imagery.spot_images,
        settings=settings,
        verify_threshold=verify_threshold,
        max_verify_iterations=max_verify_iterations,
        prompt=prompt,
        log=log,
    )
    front_png, back_png, pdf_bytes, verdict, outside_svg, inside_svg = rendered

    # --- Stage 8: mechanical lint ---
    try:
        from flyer_generator.brochure.generative.lint import lint_brochure

        lint_report = lint_brochure(
            outside_svg=outside_svg,
            inside_svg=inside_svg,
            front_png_bytes=front_png,
            back_png_bytes=back_png,
            layout=compute_panel_layout(),
        )
        log.info("brochure_linted", summary=lint_report.get("_summary", ""))
    except Exception as exc:  # lint is best-effort; don't fail generation on bug
        log.warning("brochure_lint_failed", error=str(exc))
        lint_report = {"_summary": f"lint error: {exc}"}

    return BrochureOutput(
        front_png_bytes=front_png,
        back_png_bytes=back_png,
        pdf_bytes=pdf_bytes,
        dimensions=(BLEED_CANVAS_WIDTH, BLEED_CANVAS_HEIGHT),
        attempts_used=imagery.hero_attempts_used,
        hero_vision_verdict=imagery.hero_vision_verdict,
        verification=verdict,
        lint_report=lint_report,
        trace_id=trace_id,
    )


async def _render_and_verify(
    *,
    brochure_input,
    outline,
    layout_choice,
    template,
    hero_bytes,
    spot_images,
    settings,
    verify_threshold,
    max_verify_iterations,
    prompt,
    log,
    hero_is_placeholder: bool = False,
) -> tuple[bytes, bytes, bytes, VerificationVerdict | None, str, str]:
    """Compose + rasterize + PDF, then verify with regen loop.

    Returns (front_png, back_png, pdf, verdict, outside_svg, inside_svg) — the
    SVGs are handed back so the caller can run the mechanical linter on the
    accepted iteration's markup.
    """
    rasterizer = Rasterizer(width=BLEED_CANVAS_WIDTH, height=BLEED_CANVAS_HEIGHT)
    layout = compute_panel_layout()

    last_verdict: VerificationVerdict | None = None
    # Different seed per iteration → shape positions shift, giving the verifier a
    # genuinely different composition to evaluate (not the same bytes).
    base_title = brochure_input.title

    outside_svg = ""
    inside_svg = ""
    front_png = b""
    back_png = b""

    for iteration in range(1, max_verify_iterations + 1):
        # Nudge the title with an invisible marker per iteration so the composer's
        # seed (derived from title hash) produces different shape positions.
        if iteration > 1:
            iter_brochure = brochure_input.model_copy(
                update={"title": base_title + "\u200b" * (iteration - 1)}
            )
        else:
            iter_brochure = brochure_input

        outside_svg, inside_svg = compose_brochure_svgs(
            iter_brochure,
            layout,
            hero_bytes,
            layout_choice=layout_choice,
            template=template,
            spot_images=spot_images,
            render_guides=False,
            hero_is_placeholder=hero_is_placeholder,
        )
        front_png = rasterizer.rasterize(outside_svg)
        back_png = rasterizer.rasterize(inside_svg)

        if verify_threshold <= 0:
            pdf = assemble_brochure_pdf(front_png, back_png)
            return front_png, back_png, pdf, None, outside_svg, inside_svg

        try:
            verdict = await verify_brochure(
                outside_png_bytes=front_png,
                inside_png_bytes=back_png,
                original_prompt=prompt,
                outline=outline,
                settings=settings,
                iteration=iteration,
            )
        except Exception as exc:
            log.warning("brochure_verify_failed", error=str(exc))
            pdf = assemble_brochure_pdf(front_png, back_png)
            return front_png, back_png, pdf, None, outside_svg, inside_svg

        last_verdict = verdict
        log.info("brochure_verified",
                 iteration=iteration, score=verdict.score,
                 weakest=verdict.weakest_stage)
        if verdict.score >= verify_threshold:
            pdf = assemble_brochure_pdf(front_png, back_png)
            return front_png, back_png, pdf, verdict, outside_svg, inside_svg

    pdf = assemble_brochure_pdf(front_png, back_png)
    return front_png, back_png, pdf, last_verdict, outside_svg, inside_svg


def _placeholder_hero() -> bytes:
    """Return a 1x1 transparent PNG as a placeholder for shapes_only cover treatment.

    The SVG compose step embeds this via <image> at the cover panel; a transparent 1x1 effectively leaves the cover blank so shapes carry the visual weight.
    """
    import io

    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGBA", (1, 1), (0, 0, 0, 0)).save(buf, "PNG")
    return buf.getvalue()
