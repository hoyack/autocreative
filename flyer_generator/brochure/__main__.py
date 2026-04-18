"""CLI entrypoint for brochure generation — `python -m flyer_generator.brochure`.

Kept separate from the flyer CLI (flyer_generator/__main__.py) so the existing
flyer invocation is untouched.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Annotated, Optional

import typer

from flyer_generator.brochure.models import (
    BrochureBackPanel,
    BrochureInput,
    BrochureSection,
    ContactBlock,
)
from flyer_generator.brochure.pipeline import BrochureGenerator
from flyer_generator.brochure.stages.layout import compute_panel_layout
from flyer_generator.brochure.stages.prompt_builder import BrochureCoverPromptBuilder
from flyer_generator.config import Settings
from flyer_generator.errors import FlyerGeneratorError
from flyer_generator.logging_config import configure_logging
from flyer_generator.presets import build_default_registry

app = typer.Typer(help="AI-powered tri-fold brochure generator")


def _load_brochure_from_json(path: Path) -> BrochureInput:
    """Load a BrochureInput from a JSON file (full schema)."""
    data = json.loads(path.read_text())
    # Coerce nested objects via Pydantic
    return BrochureInput(**data)


def _load_sections_from_json(path: Path) -> list[BrochureSection]:
    """Load a list of {heading, body} dicts into BrochureSection list."""
    data = json.loads(path.read_text())
    if not isinstance(data, list):
        raise typer.BadParameter(
            f"--sections-json must contain a JSON array, got {type(data).__name__}"
        )
    return [BrochureSection(**item) for item in data]


@app.command()
def main(
    title: Annotated[Optional[str], typer.Option(help="Brochure cover title")] = None,
    subtitle: Annotated[Optional[str], typer.Option(help="Optional cover subtitle")] = None,
    concept: Annotated[Optional[str], typer.Option(help="Style concept for the hero image")] = None,
    preset: Annotated[Optional[str], typer.Option(help="Style preset name")] = None,
    accent: Annotated[str, typer.Option(help="Hex accent color")] = "#F59E0B",
    org: Annotated[Optional[str], typer.Option(help="Publisher / organization name")] = None,
    sections_json: Annotated[
        Optional[Path], typer.Option("--sections-json", help="Path to JSON array of sections")
    ] = None,
    brochure_json: Annotated[
        Optional[Path],
        typer.Option("--brochure-json", help="Load full BrochureInput from JSON file"),
    ] = None,
    prompt: Annotated[
        Optional[str],
        typer.Option("--prompt", help="v2 prompt-driven: natural-language description; runs outline+text+layout+imagery+verify stages"),
    ] = None,
    audience: Annotated[
        Optional[str],
        typer.Option("--audience", help="v2 only: audience/tone hint (e.g. 'young professionals, playful')"),
    ] = None,
    target_length: Annotated[
        str, typer.Option("--target-length", help="v2 only: short | medium | long")
    ] = "medium",
    verify_threshold: Annotated[
        int, typer.Option("--verify-threshold", help="v2 only: rubric score threshold (0 = skip verification)")
    ] = 70,
    output: Annotated[
        Path, typer.Option(help="Output directory for front/back PNGs + PDF")
    ] = Path("./output/brochures"),
    list_presets: Annotated[bool, typer.Option("--list-presets", help="List available presets")] = False,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Print prompt + panel plan without generating")] = False,
    max_attempts: Annotated[Optional[int], typer.Option("--max-attempts", help="Max hero regen attempts")] = None,
) -> None:
    """Generate a tri-fold landscape brochure (outside + inside PNGs + print PDF)."""
    if list_presets:
        registry = build_default_registry()
        for name in registry.list_names():
            p = registry.get(name)
            typer.echo(f"{name}: {p.description}")
        raise typer.Exit(0)

    # --- v2 prompt-driven path (mutually exclusive with --brochure-json / explicit fields) ---
    if prompt is not None:
        if brochure_json is not None or title is not None or sections_json is not None:
            typer.echo(
                "Error: --prompt cannot be combined with --brochure-json or --title/--sections-json.",
                err=True,
            )
            raise typer.Exit(1)
        from flyer_generator.brochure.generative.pipeline import (
            generate_brochure_from_prompt,
        )

        settings = Settings()
        if max_attempts is not None:
            settings.max_bg_attempts = max_attempts
        configure_logging(settings.log_format, settings.log_level)

        try:
            result = asyncio.run(
                generate_brochure_from_prompt(
                    prompt=prompt,
                    settings=settings,
                    style_preset=preset,
                    audience=audience,
                    color_accent=accent if accent != "#F59E0B" else None,
                    target_length=target_length,  # type: ignore[arg-type]
                    verify_threshold=verify_threshold,
                )
            )
        except FlyerGeneratorError as exc:
            typer.echo(f"Brochure generation failed: {exc}", err=True)
            raise typer.Exit(1) from exc

        result.save(output)
        typer.echo(f"Wrote brochure_front.png, brochure_back.png, brochure_print.pdf to {output}")
        typer.echo(f"trace_id: {result.trace_id}")
        raise typer.Exit(0)

    # --- Build BrochureInput (v1 path) ---
    if brochure_json is not None:
        brochure = _load_brochure_from_json(brochure_json)
    else:
        missing = [
            name
            for name, val in (
                ("--title", title),
                ("--concept", concept),
                ("--preset", preset),
                ("--org", org),
                ("--sections-json", sections_json),
            )
            if not val
        ]
        if missing:
            typer.echo(
                f"Missing required options (or use --brochure-json): {', '.join(missing)}",
                err=True,
            )
            raise typer.Exit(1)
        sections = _load_sections_from_json(sections_json)  # type: ignore[arg-type]
        brochure = BrochureInput(
            title=title,  # type: ignore[arg-type]
            subtitle=subtitle,
            hero_concept=concept,  # type: ignore[arg-type]
            style_preset=preset,  # type: ignore[arg-type]
            color_accent=accent,
            org=org,  # type: ignore[arg-type]
            sections=sections,
        )

    # --- Dry-run: print prompt + panel plan ---
    if dry_run:
        registry = build_default_registry()
        builder = BrochureCoverPromptBuilder(registry)
        workflow = builder.build(brochure, attempt=1)
        typer.echo("=== Positive Prompt ===")
        typer.echo(workflow.positive_prompt)
        typer.echo("\n=== Negative Prompt ===")
        typer.echo(workflow.negative_prompt)
        typer.echo(f"\n=== Latent Dimensions: {workflow.latent_dimensions} ===")

        layout = compute_panel_layout()
        typer.echo("\n=== Panel Plan (outside) ===")
        for p in layout.outside_panels:
            typer.echo(f"  {p.index}. {p.name}: trim={p.trim_rect} safe={p.safe_rect}")
        typer.echo("\n=== Panel Plan (inside) ===")
        for p in layout.inside_panels:
            typer.echo(f"  {p.index}. {p.name}: trim={p.trim_rect} safe={p.safe_rect}")
        raise typer.Exit(0)

    # --- Full run ---
    settings = Settings()
    if max_attempts is not None:
        settings.max_bg_attempts = max_attempts
    configure_logging(settings.log_format, settings.log_level)

    generator = BrochureGenerator(settings=settings)
    try:
        result = asyncio.run(generator.generate(brochure))
    except FlyerGeneratorError as exc:
        typer.echo(f"Brochure generation failed: {exc}", err=True)
        raise typer.Exit(1) from exc

    result.save(output)
    typer.echo(f"Wrote brochure_front.png, brochure_back.png, brochure_print.pdf to {output}")
    typer.echo(f"trace_id: {result.trace_id}")
    typer.echo(f"attempts_used: {result.attempts_used}")


if __name__ == "__main__":
    app()


# Silence unused-import warnings for exports re-available via the package root.
_ = (BrochureBackPanel, ContactBlock, sys)
