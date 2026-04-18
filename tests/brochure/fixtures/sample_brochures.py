"""Canned BrochureInput fixtures reused across brochure tests and later phases."""

from __future__ import annotations

from flyer_generator.brochure.models import (
    BrochureBackPanel,
    BrochureInput,
    BrochureSection,
    ContactBlock,
)

MINIMAL_BROCHURE = BrochureInput(
    title="Spring Workshop",
    hero_concept="springtime garden workshop with tools and flowers",
    style_preset="photorealistic",
    color_accent="#2E8B57",
    org="Green Thumb Society",
    sections=[
        BrochureSection(
            heading="What You'll Learn",
            body="Hands-on techniques for planting, pruning, and companion layouts.",
        ),
        BrochureSection(
            heading="Bring Home",
            body="Seed starter kit and a reference card for the growing season.",
        ),
    ],
)


FULL_BROCHURE = BrochureInput(
    title="Annual Developer Conference",
    subtitle="Three days of talks, workshops, and hallway hacks",
    hero_concept="modern conference stage with cinematic lighting and speaker silhouettes",
    style_preset="photorealistic",
    color_accent="#F59E0B",
    org="Dev Collective",
    contact=ContactBlock(
        name="Registrar",
        phone="+1 (555) 010-0000",
        email="hello@example.com",
        url="https://example.com/conf",
        address="500 Main Street, Springfield",
    ),
    sections=[
        BrochureSection(
            heading="Keynotes",
            body="Five keynote speakers across three mornings — industry shifts, craft, and future tooling.",
        ),
        BrochureSection(
            heading="Workshops",
            body="Pick from 12 parallel workshops: performance, accessibility, observability, and more.",
        ),
        BrochureSection(
            heading="Hallway Track",
            body="Structured breakouts, office hours with speakers, and a dedicated quiet lounge.",
        ),
        BrochureSection(
            heading="Evenings",
            body="Opening mixer, speaker dinner, and a closing arcade night.",
        ),
        BrochureSection(
            heading="Travel",
            body="Venue hotel block, airport shuttle schedule, and maps to nearby food.",
        ),
    ],
    back_panel=BrochureBackPanel(
        kind="cta",
        content="Register at example.com/conf — early bird pricing ends April 30.",
    ),
)
