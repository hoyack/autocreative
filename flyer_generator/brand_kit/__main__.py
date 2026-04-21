"""Brand-kit CLI: `python -m flyer_generator.brand_kit {fetch,list,show}`."""

from __future__ import annotations

import asyncio
from typing import Annotated

import structlog
import typer

from flyer_generator.brand_kit.scraper import fetch_brand_kit
from flyer_generator.brand_kit.storage import (
    list_brand_kits,
    load_brand_kit,
)
from flyer_generator.errors import BrandKitError

app = typer.Typer(
    help="Brand-kit scraper and applier (Phase 18).",
    no_args_is_help=True,
)
logger = structlog.get_logger()


@app.command()
def fetch(
    url: Annotated[str, typer.Argument(help="Website URL to scrape.")],
    slug: Annotated[
        str,
        typer.Option(
            "--slug",
            help="Output slug (folder name under .brand-kits/).",
        ),
    ],
    force: Annotated[
        bool,
        typer.Option("--force", help="Overwrite an existing kit with the same slug."),
    ] = False,
) -> None:
    """Scrape `url` into `.brand-kits/<slug>/`."""
    try:
        kit = asyncio.run(fetch_brand_kit(url, slug, force=force))
    except BrandKitError as err:
        typer.echo(f"Error: {err}", err=True)
        for k, v in (err.context or {}).items():
            typer.echo(f"  {k}: {v}", err=True)
        raise typer.Exit(2) from err
    typer.echo(f"Wrote .brand-kits/{slug}/brand.json")
    typer.echo(f"  name: {kit.name}")
    typer.echo(f"  palette: {kit.palette.primary.hex if kit.palette else 'null'}")
    typer.echo(
        f"  typography: {kit.typography.heading_family if kit.typography else 'null'}"
    )
    typer.echo(f"  logos: {len(kit.logos)}")


@app.command("list")
def list_kits() -> None:
    """List kit slugs under FLYER_BRAND_KITS_DIR."""
    for name in list_brand_kits():
        typer.echo(name)


@app.command()
def show(
    slug: Annotated[str, typer.Argument(help="Kit slug to print as JSON.")],
) -> None:
    """Pretty-print a kit's brand.json."""
    try:
        kit = load_brand_kit(slug)
    except FileNotFoundError as err:
        typer.echo(f"Error: kit not found: {err}", err=True)
        raise typer.Exit(2) from err
    except BrandKitError as err:
        typer.echo(f"Error: {err}", err=True)
        raise typer.Exit(2) from err
    typer.echo(kit.model_dump_json(indent=2))


if __name__ == "__main__":
    app()
