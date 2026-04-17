"""CLI entrypoint for flyer_generator — run via `python -m flyer_generator`."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Annotated, Optional

import typer

from flyer_generator.config import Settings
from flyer_generator.errors import FlyerGeneratorError
from flyer_generator.logging_config import configure_logging
from flyer_generator.models import EventInput
from flyer_generator.pipeline import FlyerGenerator
from flyer_generator.presets import build_default_registry
from flyer_generator.stages.prompt_builder import StylePromptBuilder

app = typer.Typer(help="AI-powered event flyer generator")

_REQUIRED_FIELDS = [
    "title",
    "date",
    "time",
    "venue",
    "address",
    "fees",
    "org",
    "concept",
    "preset",
]


@app.command()
def main(
    title: Annotated[Optional[str], typer.Option(help="Event title")] = None,
    date: Annotated[Optional[str], typer.Option(help="Event date")] = None,
    time: Annotated[Optional[str], typer.Option(help="Event time")] = None,
    venue: Annotated[Optional[str], typer.Option(help="Venue name")] = None,
    address: Annotated[Optional[str], typer.Option(help="Venue address")] = None,
    fees: Annotated[Optional[str], typer.Option(help="Fee amount")] = None,
    org: Annotated[Optional[str], typer.Option(help="Organizer name")] = None,
    concept: Annotated[Optional[str], typer.Option(help="Style concept for image generation")] = None,
    preset: Annotated[Optional[str], typer.Option(help="Style preset name")] = None,
    accent: Annotated[str, typer.Option(help="Hex accent color")] = "#F59E0B",
    output: Annotated[Path, typer.Option(help="Output PNG path")] = Path("./output/flyer.png"),
    event_json: Annotated[Optional[Path], typer.Option("--event-json", help="Load event from JSON file")] = None,
    list_presets: Annotated[bool, typer.Option("--list-presets", help="List available presets")] = False,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Print prompt without generating")] = False,
    max_attempts: Annotated[Optional[int], typer.Option("--max-attempts", help="Max background generation attempts")] = None,
) -> None:
    """Generate an AI-powered event flyer from structured event data."""
    # D-09: --list-presets
    if list_presets:
        registry = build_default_registry()
        for name in registry.list_names():
            preset_obj = registry.get(name)
            typer.echo(f"{name}: {preset_obj.description}")
        raise typer.Exit()

    # D-08: Event construction
    if event_json is not None:
        try:
            file_content = event_json.read_text(encoding="utf-8")
            event = EventInput.model_validate_json(file_content)
        except FileNotFoundError:
            typer.echo(f"Error: file not found: {event_json}", err=True)
            raise typer.Exit(code=1)
        except Exception as exc:
            typer.echo(f"Error: invalid event JSON: {exc}", err=True)
            raise typer.Exit(code=1)
    else:
        # Check required fields
        local_args = {
            "title": title,
            "date": date,
            "time": time,
            "venue": venue,
            "address": address,
            "fees": fees,
            "org": org,
            "concept": concept,
            "preset": preset,
        }
        missing = [k for k, v in local_args.items() if v is None]
        if missing:
            typer.echo(
                f"Error: missing required options: {', '.join('--' + m for m in missing)}. "
                "Use --event-json to load from file instead.",
                err=True,
            )
            raise typer.Exit(code=1)

        event = EventInput(
            title=title,  # type: ignore[arg-type]
            date=date,  # type: ignore[arg-type]
            time=time,  # type: ignore[arg-type]
            location_name=venue,  # type: ignore[arg-type]
            location_address=address,  # type: ignore[arg-type]
            fees=fees,  # type: ignore[arg-type]
            org=org,  # type: ignore[arg-type]
            style_concept=concept,  # type: ignore[arg-type]
            style_preset=preset,  # type: ignore[arg-type]
            color_accent=accent,
        )

    # D-10: --dry-run
    if dry_run:
        registry = build_default_registry()
        builder = StylePromptBuilder(registry)
        workflow = builder.build(event, attempt=1)
        typer.echo("=== Positive Prompt ===")
        typer.echo(workflow.positive_prompt)
        typer.echo("")
        typer.echo("=== Negative Prompt ===")
        typer.echo(workflow.negative_prompt)
        raise typer.Exit()

    # D-12: Full generation
    settings = Settings()

    # D-11: --max-attempts override
    if max_attempts is not None:
        settings.max_bg_attempts = max_attempts

    configure_logging(settings.log_format, settings.log_level)

    generator = FlyerGenerator(settings)

    try:
        result = asyncio.run(generator.generate(event))
    except FlyerGeneratorError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1)

    result.save(output)
    typer.echo(f"Flyer saved to {output} ({result.attempts_used} attempt(s))")


if __name__ == "__main__":
    app()
