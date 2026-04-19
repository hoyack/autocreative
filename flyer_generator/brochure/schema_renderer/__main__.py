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
also writes per-slot PNGs to `<output>/images/`.
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

    if prompt is not None:
        from flyer_generator.brochure.schema_renderer.text_gen import (
            collect_text_budgets,
            generate_content_from_prompt,
        )
        from flyer_generator.config import Settings

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

    typer.echo(f"Rendering {tmpl.name} × {content_label}…")
    outside_svg, inside_svg = render_schema_brochure(
        tmpl, ct, images=images, textures=textures, logo_bytes=logo_bytes
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

    typer.echo(f"Wrote outputs to {output}")
    typer.echo(f"  front={len(front_png)} bytes  back={len(back_png)} bytes  pdf={len(pdf)} bytes")


if __name__ == "__main__":
    app()
