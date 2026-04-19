"""CLI entrypoint: render a brochure from a template + content JSON.

Usage:
    python -m flyer_generator.brochure.schema_renderer \\
        --template editorial_classic \\
        --content docs/brochure/sample-content/law_firm.json \\
        --output /tmp/schema-out/

Writes `outside.svg`, `inside.svg`, `brochure_front.png`, `brochure_back.png`,
and `brochure_print.pdf` into the output directory. No API calls.
"""

from __future__ import annotations

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
) -> None:
    """Render a brochure from a template schema + content JSON."""
    if list_templates_only:
        for name in list_templates():
            typer.echo(name)
        raise typer.Exit(0)

    if template is None or content is None:
        typer.echo("Error: both --template and --content are required.", err=True)
        typer.echo("Hint: run with --list-templates to see available templates.", err=True)
        raise typer.Exit(2)

    tmpl = load_template(template)
    data = json.loads(content.read_text(encoding="utf-8"))
    ct = BrochureContent.model_validate(data)

    typer.echo(f"Rendering {tmpl.name} × {content.name}…")
    outside_svg, inside_svg = render_schema_brochure(tmpl, ct)

    output.mkdir(parents=True, exist_ok=True)

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
