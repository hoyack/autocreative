"""flyer_generator.social CLI -- five commands: post, campaign, list-platforms, list-intents, show-rules.

Mirrors ``flyer_generator.brand_kit.__main__`` in shape:
- typer.Typer(help=..., no_args_is_help=True) app
- SocialError / BrandKitError -> echo to stderr + exit(2)
- asyncio.run() wrapper around async orchestrators

Per SOC-11: these commands produce artifacts only. No publishing to real
platform APIs is performed.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Annotated

import structlog
import typer
from ulid import ULID

from flyer_generator.brand_kit.storage import load_brand_kit
from flyer_generator.errors import BrandKitError, SocialError
from flyer_generator.social.campaign import generate_campaign
from flyer_generator.social.generator import generate_post
from flyer_generator.social.models import PostBrief
from flyer_generator.social.platforms import PLATFORM_REGISTRY, load_platform_rules
from flyer_generator.social.storage import save_campaign, save_post

app = typer.Typer(
    help=(
        "Social-media posting system (Phase 19). Produces artifacts only -- "
        "no publishing."
    ),
    no_args_is_help=True,
)
logger = structlog.get_logger()

_KNOWN_INTENTS = ("announcement", "value-prop", "testimonial")


@app.command()
def post(
    brand_kit: Annotated[
        str,
        typer.Option(
            "--brand-kit",
            help="Brand-kit slug (loaded from .brand-kits/<slug>/).",
        ),
    ],
    platform: Annotated[
        str,
        typer.Option("--platform", help="linkedin|twitter|instagram|facebook"),
    ],
    intent: Annotated[
        str,
        typer.Option("--intent", help="announcement|value-prop|testimonial"),
    ],
    topic: Annotated[str, typer.Option("--topic", help="Post subject")],
    output: Annotated[Path, typer.Option("--output", help="Output directory")],
    cta: Annotated[str | None, typer.Option("--cta")] = None,
    source_url: Annotated[str | None, typer.Option("--source-url")] = None,
    image_hint: Annotated[str | None, typer.Option("--image-hint")] = None,
    campaign_id: Annotated[str | None, typer.Option("--campaign-id")] = None,
    audit: Annotated[bool, typer.Option("--audit/--no-audit")] = True,
) -> None:
    """Generate one post and write artifacts under --output."""
    try:
        kit = load_brand_kit(brand_kit)
    except BrandKitError as err:
        typer.echo(f"Error loading brand kit: {err}", err=True)
        raise typer.Exit(2) from err
    except FileNotFoundError as err:
        typer.echo(f"Error loading brand kit: {err}", err=True)
        raise typer.Exit(2) from err

    cid = campaign_id or str(ULID())
    brief = PostBrief(
        topic=topic,
        intent=intent,  # type: ignore[arg-type]
        platform=platform,  # type: ignore[arg-type]
        cta=cta,
        source_url=source_url,
        image_hint=image_hint,
    )
    try:
        post_obj = asyncio.run(generate_post(brief, kit, audit=audit))
    except SocialError as err:
        typer.echo(f"Error: {err}", err=True)
        for k, v in (getattr(err, "context", None) or {}).items():
            typer.echo(f"  {k}: {v}", err=True)
        raise typer.Exit(2) from err

    # Persist to output dir -- save_post anchors under <output>/<brand_kit>/<cid>/
    save_post(
        post_obj,
        slug=brand_kit,
        campaign_id=cid,
        template_name=f"{platform}__{intent}",
        base_dir=output,
    )
    typer.echo(f"Post written: {output}/{brand_kit}/{cid}/ (campaign_id={cid})")
    typer.echo(
        f"Validation: {'PASSED' if post_obj.validation_report.passed else 'FAILED'}"
    )
    if not post_obj.validation_report.passed:
        for issue in post_obj.validation_report.errors():
            typer.echo(f"  [error] {issue.rule_id}: {issue.message}", err=True)


@app.command()
def campaign(
    brand_kit: Annotated[str, typer.Option("--brand-kit")],
    platforms: Annotated[
        str,
        typer.Option(
            "--platforms",
            help="Comma-separated: linkedin,twitter,instagram,facebook",
        ),
    ],
    topic: Annotated[str, typer.Option("--topic")],
    output: Annotated[Path, typer.Option("--output")],
    intent: Annotated[str, typer.Option("--intent")] = "value-prop",
    cta: Annotated[str | None, typer.Option("--cta")] = None,
    image_hint: Annotated[str | None, typer.Option("--image-hint")] = None,
    include_story: Annotated[bool, typer.Option("--include-story")] = False,
    audit: Annotated[bool, typer.Option("--audit/--no-audit")] = True,
) -> None:
    """Generate a multi-platform campaign with a shared source hero."""
    try:
        kit = load_brand_kit(brand_kit)
    except BrandKitError as err:
        typer.echo(f"Error loading brand kit: {err}", err=True)
        raise typer.Exit(2) from err
    except FileNotFoundError as err:
        typer.echo(f"Error loading brand kit: {err}", err=True)
        raise typer.Exit(2) from err

    platform_list = [p.strip() for p in platforms.split(",") if p.strip()]
    try:
        camp = asyncio.run(
            generate_campaign(
                kit,
                topic=topic,
                platforms=platform_list,  # type: ignore[arg-type]
                intent=intent,  # type: ignore[arg-type]
                include_story=include_story,
                cta=cta,
                image_hint=image_hint,
                audit=audit,
            )
        )
    except SocialError as err:
        typer.echo(f"Error: {err}", err=True)
        raise typer.Exit(2) from err

    save_campaign(camp, base_dir=output)
    typer.echo(
        f"Campaign written: {output}/{camp.brand_kit_slug}/{camp.campaign_id}/"
    )
    typer.echo(f"Posts: {len(camp.posts)}")


@app.command("list-platforms")
def list_platforms() -> None:
    """List supported platforms."""
    for p in sorted(PLATFORM_REGISTRY):
        typer.echo(p)


@app.command("list-intents")
def list_intents() -> None:
    """List supported post intents."""
    for i in _KNOWN_INTENTS:
        typer.echo(i)


@app.command("show-rules")
def show_rules(
    platform: Annotated[str, typer.Argument(help="Platform name")],
) -> None:
    """Print a platform's rules in human-readable form."""
    try:
        rules = load_platform_rules(platform)
    except SocialError as err:
        typer.echo(f"Error: {err}", err=True)
        raise typer.Exit(2) from err
    data = rules.model_dump(mode="json")
    typer.echo(json.dumps(data, indent=2, default=str))


if __name__ == "__main__":
    app()
