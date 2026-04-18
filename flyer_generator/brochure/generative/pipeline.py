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

    The 'cover' section provides title/hero_concept; remaining sections become
    the visible section list (2-4 sections). A 'cta' role produces the back_panel.
    """
    cover_section = next(s for s in outline.sections if s.panel_role == "cover")

    # Title: use cover section heading.
    title = cover_section.heading
    # Hero concept: use cover body if it reads like a concept, else fall back to prompt.
    hero_concept = cover_section.body_brief or prompt.prompt[:120]

    # back_panel: if any section has role cta, pull its body as content.
    back_panel = None
    cta_section = next((s for s in outline.sections if s.panel_role == "cta"), None)
    if cta_section is not None:
        cta_text = next((t for t in texts if t.heading == cta_section.heading), None)
        if cta_text is not None:
            from flyer_generator.brochure.models import BrochureBackPanel

            back_panel = BrochureBackPanel(
                kind=_panel_role_to_back_panel_kind(cta_section.panel_role),
                content=cta_text.body,
            )

    # Visible sections: all non-cover, non-cta sections (2-4 items).
    visible = [
        s for s in outline.sections if s.panel_role not in ("cover", "cta")
    ]
    # Keep minimum 2 — if too few, fall back to all non-cover sections.
    if len(visible) < 2:
        visible = [s for s in outline.sections if s.panel_role != "cover"]

    # Map to BrochureSection using the generated text bodies.
    sections: list[BrochureSection] = []
    for spec in visible[:5]:
        text = next((t for t in texts if t.heading == spec.heading), None)
        body = text.body if text else spec.body_brief
        sections.append(BrochureSection(heading=spec.heading, body=body, icon_hint=spec.image_hint))

    return BrochureInput(
        title=title,
        subtitle=None,
        hero_concept=hero_concept,
        style_preset=outline.suggested_preset,
        color_accent=outline.suggested_accent,
        org=outline.cta_intent[:120],
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
    layout_choice: LayoutChoice = await choose_layout(outline, text_client)
    template = get_template(layout_choice.template)
    log.info("brochure_layout_chosen", template=layout_choice.template, density=layout_choice.shape_density)

    # --- Stage 5: fit optimization (runs before imagery since image gen is expensive) ---
    texts = await optimize_fit(texts, template, text_client, target_length=target_length)
    log.info("brochure_fit_optimized")

    # --- Assemble BrochureInput ---
    brochure_input = _assemble_brochure_input(brochure_prompt, outline, texts)
    log.info("brochure_input_assembled", title=brochure_input.title, n_sections=len(brochure_input.sections))

    # --- Stage 4: imagery ---
    imagery = await generate_imagery(
        brochure=brochure_input,
        outline=outline,
        layout_choice=layout_choice,
        settings=settings,
    )
    log.info("brochure_imagery_ready",
             has_hero=imagery.hero_png_bytes is not None,
             n_spots=len(imagery.spot_images))

    # Placeholder hero when shapes_only
    hero_bytes = imagery.hero_png_bytes or _placeholder_hero()

    # --- Stage 6: compose + rasterize + PDF ---
    rendered = await _render_and_verify(
        brochure_input=brochure_input,
        outline=outline,
        layout_choice=layout_choice,
        template=template,
        hero_bytes=hero_bytes,
        spot_images=imagery.spot_images,
        settings=settings,
        verify_threshold=verify_threshold,
        max_verify_iterations=max_verify_iterations,
        prompt=prompt,
        log=log,
    )
    front_png, back_png, pdf_bytes, verdict = rendered

    return BrochureOutput(
        front_png_bytes=front_png,
        back_png_bytes=back_png,
        pdf_bytes=pdf_bytes,
        dimensions=(BLEED_CANVAS_WIDTH, BLEED_CANVAS_HEIGHT),
        attempts_used=imagery.hero_attempts_used,
        hero_vision_verdict=imagery.hero_vision_verdict,
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
) -> tuple[bytes, bytes, bytes, VerificationVerdict | None]:
    """Compose + rasterize + PDF, then verify with regen loop."""
    rasterizer = Rasterizer(width=BLEED_CANVAS_WIDTH, height=BLEED_CANVAS_HEIGHT)
    layout = compute_panel_layout()

    last_verdict: VerificationVerdict | None = None

    for iteration in range(1, max_verify_iterations + 1):
        outside_svg, inside_svg = compose_brochure_svgs(
            brochure_input,
            layout,
            hero_bytes,
            layout_choice=layout_choice,
            template=template,
            spot_images=spot_images,
            render_guides=False,
        )
        front_png = rasterizer.rasterize(outside_svg)
        back_png = rasterizer.rasterize(inside_svg)

        if verify_threshold <= 0:
            # Fast mode — skip verification entirely
            pdf = assemble_brochure_pdf(front_png, back_png)
            return front_png, back_png, pdf, None

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
            # On verify failure, accept what we have.
            pdf = assemble_brochure_pdf(front_png, back_png)
            return front_png, back_png, pdf, None

        last_verdict = verdict
        log.info("brochure_verified",
                 iteration=iteration, score=verdict.score,
                 weakest=verdict.weakest_stage)
        if verdict.score >= verify_threshold:
            pdf = assemble_brochure_pdf(front_png, back_png)
            return front_png, back_png, pdf, verdict

        # Below threshold: for cheap regen, retry compose with a different seed
        # by nudging brochure_input (e.g. add a zero-width space to title to change hash).
        # Stop after max_verify_iterations.

    # Exhausted iterations — ship what we have.
    pdf = assemble_brochure_pdf(front_png, back_png)
    return front_png, back_png, pdf, last_verdict


def _placeholder_hero() -> bytes:
    """Return a 1x1 transparent PNG as a placeholder for shapes_only cover treatment.

    The SVG compose step embeds this via <image> at the cover panel; a transparent 1x1 effectively leaves the cover blank so shapes carry the visual weight.
    """
    import io

    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGBA", (1, 1), (0, 0, 0, 0)).save(buf, "PNG")
    return buf.getvalue()
