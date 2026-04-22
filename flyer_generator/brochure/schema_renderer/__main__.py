"""CLI entrypoint: render a brochure from a template + content JSON.

Usage:
    # Pure design render (no API calls)
    python -m flyer_generator.brochure.schema_renderer \\
        --template editorial_classic \\
        --content docs/brochure/sample-content/law_firm.json \\
        --output /tmp/schema-out/

    # With ComfyUI-generated images in image_placeholder slots
    python -m flyer_generator.brochure.schema_renderer \\
        --template hero_image_dominant \\
        --content docs/brochure/sample-content/law_firm.json \\
        --generate-images \\
        --workflow ernie_landscape \\
        --style-preset photorealistic \\
        --output /tmp/schema-out/

Writes `outside.svg`, `inside.svg`, `brochure_front.png`, `brochure_back.png`,
and `brochure_print.pdf` into the output directory. With `--generate-images`,
also writes per-slot PNGs to `<output>/images/`. By default also writes
`audit.json` (disable with `--no-audit`).
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Annotated, Optional

import typer

from flyer_generator.brochure.schema_renderer.content_model import BrochureContent
from flyer_generator.brochure.schema_renderer.loader import list_templates, load_template
from flyer_generator.brochure.schema_renderer.renderer import render_schema_brochure
from flyer_generator.brochure.stages.layout import (
    BLEED_CANVAS_HEIGHT,
    BLEED_CANVAS_WIDTH,
)
from flyer_generator.brochure.stages.pdf import assemble_brochure_pdf
from flyer_generator.stages.rasterizer import Rasterizer

app = typer.Typer(help="Schema-driven brochure renderer (design-first, no LLM/API).")


@app.command()
def render(
    template: Annotated[
        Optional[str],
        typer.Option("--template", help="Template name (under schemas/) or path to a JSON file."),
    ] = None,
    content: Annotated[
        Optional[Path],
        typer.Option("--content", help="Path to a content JSON file."),
    ] = None,
    output: Annotated[
        Path,
        typer.Option("--output", help="Output directory."),
    ] = Path("/tmp/schema-out"),
    list_templates_only: Annotated[
        bool,
        typer.Option("--list-templates", help="List built-in template names and exit."),
    ] = False,
    write_svg: Annotated[
        bool,
        typer.Option("--write-svg/--no-write-svg", help="Write .svg alongside PNG/PDF."),
    ] = True,
    generate_images: Annotated[
        bool,
        typer.Option(
            "--generate-images/--no-generate-images",
            help="Call ComfyUI to fill image_placeholder slots (hero + spots).",
        ),
    ] = False,
    workflow: Annotated[
        str,
        typer.Option("--workflow", help="ComfyUI workflow for image generation."),
    ] = "ernie_landscape",
    style_preset: Annotated[
        str,
        typer.Option("--style-preset", help="Preset for image style (photorealistic, anime, ...)."),
    ] = "photorealistic",
    textures_dir: Annotated[
        Optional[Path],
        typer.Option(
            "--textures-dir",
            help="Directory of <slot>.png files used to fill texture_slot shape fills.",
        ),
    ] = None,
    logo: Annotated[
        Optional[Path],
        typer.Option(
            "--logo",
            help="Path to a PNG/JPG/SVG logo file. Used for every logo_placeholder "
            "element in the template; absent → monogram fallback.",
        ),
    ] = None,
    prompt: Annotated[
        Optional[str],
        typer.Option(
            "--prompt",
            help="Natural-language business/event description. Triggers Phase 2: "
            "LLM writes content fitting the template's char budgets. Mutually "
            "exclusive with --content.",
        ),
    ] = None,
    audience: Annotated[
        Optional[str],
        typer.Option(
            "--audience",
            help="Optional audience/tone hint for --prompt (e.g. 'young professionals, playful').",
        ),
    ] = None,
    color_accent: Annotated[
        Optional[str],
        typer.Option(
            "--color-accent",
            help="Override the template's palette.accent_default with this #RRGGBB hex.",
        ),
    ] = None,
    brand_kit: Annotated[
        Optional[str],
        typer.Option(
            "--brand-kit",
            help=(
                "Apply a brand kit by slug (loaded from `.brand-kits/<slug>/brand.json`). "
                "Overrides --color-accent. Explicit --logo overrides the kit's logo."
            ),
        ),
    ] = None,
    brief_json: Annotated[
        Optional[Path],
        typer.Option(
            "--brief-json",
            help="Path to a JSON BrochureBrief (interrogative intake: offerings, "
            "differentiators, testimonials, hours, CTAs, etc.). Used as ground "
            "truth by the LLM when --prompt is set.",
        ),
    ] = None,
    phone: Annotated[
        Optional[str],
        typer.Option("--phone", help="Contact phone number (preserved verbatim)."),
    ] = None,
    address: Annotated[
        Optional[str],
        typer.Option("--address", help="Contact mailing address (preserved verbatim)."),
    ] = None,
    email: Annotated[
        Optional[str],
        typer.Option("--email", help="Contact email (preserved verbatim)."),
    ] = None,
    url: Annotated[
        Optional[str],
        typer.Option("--url", help="Contact URL (preserved verbatim)."),
    ] = None,
    audit: Annotated[
        bool,
        typer.Option(
            "--audit/--no-audit",
            help="Run audit_render on both sheets after rasterize and write audit.json sidecar.",
        ),
    ] = True,
    iterate_audit: Annotated[
        int,
        typer.Option(
            "--iterate-audit",
            help="Max remediation cycles when audit finds warn/error issues (capped at 3).",
        ),
    ] = 0,
    audit_json: Annotated[
        Optional[Path],
        typer.Option(
            "--audit-json",
            help="Explicit audit.json output path. Defaults to <output>/audit.json.",
        ),
    ] = None,
) -> None:
    """Render a brochure from a template schema + content JSON."""
    if list_templates_only:
        for name in list_templates():
            typer.echo(name)
        raise typer.Exit(0)

    if template is None:
        typer.echo("Error: --template is required.", err=True)
        typer.echo("Hint: run with --list-templates to see available templates.", err=True)
        raise typer.Exit(2)
    if content is None and prompt is None:
        typer.echo(
            "Error: supply either --content <json> or --prompt '<description>'.",
            err=True,
        )
        raise typer.Exit(2)
    if content is not None and prompt is not None:
        typer.echo(
            "Error: --content and --prompt are mutually exclusive.", err=True
        )
        raise typer.Exit(2)

    tmpl = load_template(template)

    # --- Brand kit integration (Phase 18) ---
    logo_bytes_from_kit: bytes | None = None
    if brand_kit is not None:
        from flyer_generator.brand_kit.applier import apply_brand_kit
        from flyer_generator.brand_kit.storage import load_brand_kit
        from flyer_generator.errors import BrandKitError
        try:
            kit = load_brand_kit(brand_kit)
        except BrandKitError as err:
            # BrandKitNotFoundError (subclass of BrandKitError) is raised
            # when the slug does not resolve to a stored kit.
            typer.echo(f"Error: --brand-kit {brand_kit!r} not found: {err}", err=True)
            raise typer.Exit(2) from err
        except FileNotFoundError as err:
            typer.echo(f"Error: --brand-kit {brand_kit!r} not found: {err}", err=True)
            raise typer.Exit(2) from err
        if color_accent is not None:
            typer.echo(
                f"Warning: --brand-kit overrides --color-accent "
                f"({color_accent} ignored in favor of kit palette).",
                err=True,
            )
            color_accent = None
        tmpl, logo_bytes_from_kit = apply_brand_kit(tmpl, kit, slug=brand_kit)
        typer.echo(f"Applied brand kit: {brand_kit}")

    if prompt is not None:
        from flyer_generator.brochure.models import ContactBlock
        from flyer_generator.brochure.schema_renderer.content_model import (
            BrochureBrief,
        )
        from flyer_generator.brochure.schema_renderer.text_gen import (
            collect_text_budgets,
            generate_content_from_prompt,
        )
        from flyer_generator.config import Settings

        brief: BrochureBrief | None = None
        if brief_json is not None:
            if not brief_json.is_file():
                typer.echo(
                    f"Error: --brief-json {brief_json} is not a file.", err=True
                )
                raise typer.Exit(2)
            brief = BrochureBrief.model_validate_json(
                brief_json.read_text(encoding="utf-8")
            )
            typer.echo(f"Loaded brief: {brief_json.name}")

        supplied_contact: ContactBlock | None = None
        if any([phone, address, email, url]):
            supplied_contact = ContactBlock(
                phone=phone, address=address, email=email, url=url
            )

        budgets = collect_text_budgets(tmpl)
        typer.echo(
            f"Phase 2: LLM writing content for {len(budgets)} budgeted fields "
            f"(template={tmpl.name})…"
        )
        ct = asyncio.run(
            generate_content_from_prompt(
                tmpl,
                prompt,
                audience=audience,
                brief=brief,
                contact=supplied_contact,
                settings=Settings(),
            )
        )
        content_label = "--prompt"
    else:
        data = json.loads(content.read_text(encoding="utf-8"))  # type: ignore[union-attr]
        ct = BrochureContent.model_validate(data)
        content_label = content.name if content is not None else "?"

    output.mkdir(parents=True, exist_ok=True)

    if prompt is not None:
        # Persist the LLM-generated content JSON for inspection / reuse
        (output / "content.json").write_text(
            ct.model_dump_json(indent=2), encoding="utf-8"
        )

    images: dict[str, bytes] | None = None
    if generate_images:
        from flyer_generator.brochure.schema_renderer.image_gate import (
            collect_image_slots,
            generate_template_images,
        )
        from flyer_generator.config import Settings

        slots = collect_image_slots(tmpl)
        typer.echo(
            f"Generating images for slots {slots} via workflow={workflow} "
            f"preset={style_preset}…"
        )
        settings = Settings()
        images = asyncio.run(
            generate_template_images(
                tmpl,
                ct,
                style_preset=style_preset,
                workflow_name=workflow,
                settings=settings,
            )
        )
        missing = [s for s in slots if s not in images]
        typer.echo(
            f"  generated={list(images.keys())}  "
            f"fell_back={missing if missing else 'none'}"
        )
        # Persist per-slot images for inspection
        images_dir = output / "images"
        images_dir.mkdir(parents=True, exist_ok=True)
        for slot, raw in images.items():
            (images_dir / f"{slot}.png").write_bytes(raw)

    textures: dict[str, bytes] | None = None
    if textures_dir is not None:
        if not textures_dir.is_dir():
            typer.echo(f"Error: --textures-dir {textures_dir} is not a directory.", err=True)
            raise typer.Exit(2)
        textures = {
            p.stem: p.read_bytes() for p in sorted(textures_dir.glob("*.png"))
        }
        typer.echo(f"Loaded textures: {list(textures.keys())}")

    logo_bytes: bytes | None = None
    if logo is not None:
        if not logo.is_file():
            typer.echo(f"Error: --logo {logo} is not a file.", err=True)
            raise typer.Exit(2)
        logo_bytes = logo.read_bytes()
        typer.echo(f"Loaded logo: {logo.name} ({len(logo_bytes)} bytes)")
    elif logo_bytes_from_kit is not None:
        logo_bytes = logo_bytes_from_kit
        typer.echo(f"Using brand-kit logo ({len(logo_bytes)} bytes)")

    typer.echo(f"Rendering {tmpl.name} × {content_label}…")
    if color_accent:
        typer.echo(f"Palette accent overridden → {color_accent}")
    outside_svg, inside_svg = render_schema_brochure(
        tmpl,
        ct,
        images=images,
        textures=textures,
        logo_bytes=logo_bytes,
        accent_override=color_accent,
    )

    if write_svg:
        (output / "outside.svg").write_text(outside_svg, encoding="utf-8")
        (output / "inside.svg").write_text(inside_svg, encoding="utf-8")

    rasterizer = Rasterizer(width=BLEED_CANVAS_WIDTH, height=BLEED_CANVAS_HEIGHT)
    front_png = rasterizer.rasterize(outside_svg)
    back_png = rasterizer.rasterize(inside_svg)
    (output / "brochure_front.png").write_bytes(front_png)
    (output / "brochure_back.png").write_bytes(back_png)

    pdf = assemble_brochure_pdf(front_png, back_png)
    (output / "brochure_print.pdf").write_bytes(pdf)

    # --- Auto-audit (Phase 18 closure: render → audit.json sidecar) ---
    if audit:
        # Import inside the flag guard: keeps --no-audit fast and avoids pulling
        # the audit module into unrelated test imports of this CLI.
        from flyer_generator.brand_kit import audit as _audit_mod

        final_template = tmpl  # already post-brand-kit-apply if --brand-kit used

        def _summarize(side_name: str, report) -> str:
            fails = report.contrast.fails() if hasattr(report.contrast, "fails") else []
            n_fail = len(fails)
            n_total = len(report.contrast.pairs)
            density_min = min(report.density.values()) if report.density else 1.0
            whitespace_max = (
                max(report.whitespace.values()) if report.whitespace else 0.0
            )
            n_warn = sum(1 for i in report.issues if i.severity == "warn")
            n_err = sum(1 for i in report.issues if i.severity == "error")
            n_info = sum(1 for i in report.issues if i.severity == "info")
            return (
                f"Audit [{side_name}]: AA pass={report.contrast.overall_aa_pass} "
                f"({n_fail}/{n_total} fail), density_min={density_min:.2f}, "
                f"whitespace_max={whitespace_max:.2f}, "
                f"issues={len(report.issues)} ({n_warn + n_err} warn, {n_info} info)"
            )

        report_outside = _audit_mod.audit_render(
            ct, final_template, front_png, side="outside"
        )
        report_inside = _audit_mod.audit_render(
            ct, final_template, back_png, side="inside"
        )

        # Stderr summary only when warn/error issues OR AA fails exist (info-only is silent).
        for _side_name, _rep in (("outside", report_outside), ("inside", report_inside)):
            _has_warnplus = any(
                i.severity in ("warn", "error") for i in _rep.issues
            )
            if _has_warnplus or not _rep.contrast.overall_aa_pass:
                typer.echo(_summarize(_side_name, _rep), err=True)

        # Optional iterate loop: only when requested AND actionable issues exist.
        _needs_iterate = (
            iterate_audit > 0
            and any(
                i.severity in ("warn", "error")
                for r in (report_outside, report_inside)
                for i in r.issues
            )
        )
        if _needs_iterate:
            max_cycles = min(iterate_audit, 3)

            async def _render(c, t):
                out_svg, in_svg = render_schema_brochure(
                    t,
                    c,
                    images=images,
                    textures=textures,
                    logo_bytes=logo_bytes,
                    accent_override=color_accent,
                )
                _f = rasterizer.rasterize(out_svg)
                _b = rasterizer.rasterize(in_svg)
                return _f, _b

            kit_for_iter = None
            if brand_kit is not None:
                from flyer_generator.brand_kit.storage import (
                    load_brand_kit as _lbk,
                )
                try:
                    kit_for_iter = _lbk(brand_kit)
                except Exception:
                    kit_for_iter = None

            # SCOPE DECISION: density regen needs per-key budget-override plumbing
            # that generate_content_from_prompt does not yet support. Passing
            # regenerate_fn=None means the loop will not regenerate copy; contrast
            # remediation still works when a kit is available. Next caller to
            # need density regen should extend generate_content_from_prompt with
            # a tighter_budgets kwarg and wire it here.
            _final_report_outside, _final_content, _final_template_iter = (
                asyncio.run(
                    _audit_mod.iterate_audit_loop(
                        ct,
                        final_template,
                        render=_render,
                        kit=kit_for_iter,
                        regenerate_fn=None,
                        max_cycles=max_cycles,
                        side="outside",
                    )
                )
            )

            # Re-render + re-rasterize with the iterated state so on-disk PNGs
            # match the final audit report.
            out_svg2, in_svg2 = render_schema_brochure(
                _final_template_iter,
                _final_content,
                images=images,
                textures=textures,
                logo_bytes=logo_bytes,
                accent_override=color_accent,
            )
            front_png = rasterizer.rasterize(out_svg2)
            back_png = rasterizer.rasterize(in_svg2)
            (output / "brochure_front.png").write_bytes(front_png)
            (output / "brochure_back.png").write_bytes(back_png)
            if write_svg:
                (output / "outside.svg").write_text(out_svg2, encoding="utf-8")
                (output / "inside.svg").write_text(in_svg2, encoding="utf-8")
            pdf = assemble_brochure_pdf(front_png, back_png)
            (output / "brochure_print.pdf").write_bytes(pdf)

            # Re-audit both sides post-iteration.
            report_outside = _audit_mod.audit_render(
                _final_content, _final_template_iter, front_png, side="outside"
            )
            report_inside = _audit_mod.audit_render(
                _final_content, _final_template_iter, back_png, side="inside"
            )
            typer.echo(
                f"Audit iteration complete (max_cycles={max_cycles}).",
                err=True,
            )
            for _side_name, _rep in (
                ("outside", report_outside),
                ("inside", report_inside),
            ):
                typer.echo(_summarize(_side_name, _rep), err=True)

        # Write audit.json sidecar (always, when --audit).
        combined = {
            "outside": report_outside.model_dump(),
            "inside": report_inside.model_dump(),
            "is_clean_overall": bool(
                report_outside.is_clean and report_inside.is_clean
            ),
        }
        sidecar_path = audit_json if audit_json is not None else (output / "audit.json")
        sidecar_path.parent.mkdir(parents=True, exist_ok=True)
        sidecar_path.write_text(
            json.dumps(combined, indent=2, default=str), encoding="utf-8"
        )

    typer.echo(f"Wrote outputs to {output}")
    typer.echo(f"  front={len(front_png)} bytes  back={len(back_png)} bytes  pdf={len(pdf)} bytes")


if __name__ == "__main__":
    app()
