"""Phase 2: LLM-driven text budgeting for schema templates.

Given a TemplateSchema (which declares char budgets per text region via bbox
+ font_size + line_height) and a high-level user prompt ("a boutique estate-
planning law firm"), call an LLM to write copy for every text region that
fits *exactly* under the declared budgets. The output is a populated
BrochureContent ready for `render_schema_brochure`.

Flow:
  1. collect_text_budgets(template) → list[TextBudget]
     Walks every TextElement + BulletsElement and records the *tightest*
     char budget per content_key (multiple elements may share a key).
  2. generate_content_from_prompt(template, prompt) asks the LLM for a JSON
     object shaped like BrochureContent, embedding every budget in the
     prompt. The LLM must keep each field under its limit.
  3. A validation loop checks the returned JSON against budgets; fields
     over-budget get one retry with a stricter instruction, and a hard
     truncate at a word boundary is the last-resort fallback.

This module is deliberately decoupled from the legacy generative pipeline
(`generative.pipeline`, `generative.outline`) — the schema-renderer path
targets a different surface (templates + content JSON) and has different
constraints (hard char budgets, no narrative outline).
"""

from __future__ import annotations

import json
import re
from typing import NamedTuple

import structlog

from flyer_generator.brand_kit.models import BrandVoice
from flyer_generator.brochure.llm_client import TextClient, build_text_client
from flyer_generator.brochure.schema_renderer.content_model import (
    BackPanelContent,
    BrochureBrief,
    BrochureContent,
    ContentSection,
)
from flyer_generator.brochure.schema_renderer.schema_model import (
    BulletsElement,
    TemplateSchema,
    TextElement,
)
from flyer_generator.brochure.schema_renderer.text_fit import (
    char_budget_for_bbox,
    chars_per_line,
)
from flyer_generator.config import Settings
from flyer_generator.errors import (
    BrandVoiceViolationError,
    VisionAPIError,
    VisionResponseParseError,
)
from flyer_generator.brochure.models import ContactBlock

logger = structlog.get_logger()

_MAX_RETRIES = 1
# Safety margin so LLM output has headroom against our character estimate.
_BUDGET_SLACK = 0.92


class TextBudget(NamedTuple):
    """One unique content region with its tightest character budget."""

    content_key: str  # e.g. "title", "sections[0].heading", "back_panel.bullets"
    role: str  # e.g. "cover_title", "section_heading", "bullet"
    max_chars: int  # tightest budget across all matching template elements
    is_list: bool  # True when content_key resolves to list[str] (bullets)


def _role_font_key(role: str) -> str:
    """Map a text role to the typography size field used by the renderer."""
    mapping = {
        "cover_title": "cover_title_size",
        "cover_subtitle": "cover_subtitle_size",
        "section_heading": "heading_size",
        "lead_paragraph": "body_size",
        "body": "body_size",
        "quote": "heading_size",
        "bullet": "bullet_size",
        "cta_heading": "heading_size",
        "cta_body": "body_size",
        "org_name": "heading_size",
        "tagline": "cover_subtitle_size",
    }
    return mapping.get(role, "body_size")


def _role_line_height(role: str, size: int) -> int:
    factor = {
        "cover_title": 1.05,
        "cover_subtitle": 1.25,
        "section_heading": 1.1,
        "body": 1.28,
        "lead_paragraph": 1.28,
        "bullet": 1.35,
        "quote": 1.2,
        "cta_heading": 1.1,
        "cta_body": 1.28,
        "org_name": 1.1,
        "tagline": 1.2,
    }.get(role, 1.28)
    return int(size * factor)


def _element_budget(
    el: TextElement | BulletsElement, schema: TemplateSchema
) -> int:
    """Compute the char budget this single element can hold."""
    # Font family
    if getattr(el, "font_family", None):
        family = el.font_family  # type: ignore[assignment]
    elif hasattr(el, "role") and el.role in (
        "cover_title",
        "section_heading",
        "cta_heading",
        "org_name",
        "quote",
    ):
        family = schema.typography.heading_family
    else:
        family = schema.typography.body_family

    # Font size
    if getattr(el, "font_size", None):
        size = int(el.font_size)  # type: ignore[assignment]
    elif isinstance(el, TextElement):
        size = int(getattr(schema.typography, _role_font_key(el.role)))
    else:
        size = schema.typography.bullet_size

    # Line height
    if getattr(el, "line_height", None):
        lh = int(el.line_height)  # type: ignore[assignment]
    elif isinstance(el, TextElement):
        lh = _role_line_height(el.role, size)
    else:
        lh = schema.typography.bullet_line_height

    # Budget from bbox
    budget = char_budget_for_bbox(el.bbox, size, lh, family)

    # Tighter of max_chars override and bbox-derived budget
    if isinstance(el, TextElement) and el.max_chars is not None:
        budget = min(budget, el.max_chars)
    return max(1, int(budget * _BUDGET_SLACK))


def _per_item_char_limit(
    el: BulletsElement, schema: TemplateSchema
) -> int:
    """How many chars each individual bullet can hold.

    Accounts for vertical bbox space: when the bullets bbox is taller than
    max_items × line_height, each item can wrap to multiple lines. Previously
    this returned chars-per-line only, which under-budgeted bullets in tall
    bboxes (they rendered as a single line each, leaving huge empty space
    below the last bullet).
    """
    if getattr(el, "font_family", None):
        family = el.font_family  # type: ignore[assignment]
    else:
        family = schema.typography.body_family
    size = int(el.font_size or schema.typography.bullet_size)
    line_height = int(el.line_height or schema.typography.bullet_line_height)
    _, _, w, h = el.bbox
    # Account for bullet marker indent
    usable = max(10.0, w - size * 1.2)
    cpl = chars_per_line(usable, size, family)
    # Vertical allowance: how many lines each bullet gets
    total_lines = max(1, int(h / line_height))
    lines_per_item = max(1, total_lines // max(1, el.max_items))
    return min(el.max_chars_per_item, cpl * lines_per_item)


def collect_text_budgets(template: TemplateSchema) -> list[TextBudget]:
    """Return the tightest budget per unique content_key across all text elements.

    When multiple TextElements reference the same content_key, pick the
    minimum budget — the copy must fit the smallest region. Static text
    elements (no content_key) are skipped.
    """
    by_key: dict[str, TextBudget] = {}

    for panel_name, panel in template.panels.items():
        for el in panel.elements:
            if isinstance(el, TextElement):
                if el.content_key is None or el.role == "static":
                    continue
                key = el.content_key
                # Resolve section.X shorthand against section_index
                if key.startswith("section.") and el.section_index is not None:
                    sub = key.split(".", 1)[1]
                    key = f"sections[{el.section_index}].{sub}"
                budget = _element_budget(el, template)
                existing = by_key.get(key)
                if existing is None or budget < existing.max_chars:
                    by_key[key] = TextBudget(
                        content_key=key,
                        role=el.role,
                        max_chars=budget,
                        is_list=False,
                    )
            elif isinstance(el, BulletsElement):
                key = el.content_key
                if key.startswith("section.") and el.section_index is not None:
                    sub = key.split(".", 1)[1]
                    key = f"sections[{el.section_index}].{sub}"
                # For bullet lists, budget is per-item × max_items
                per_item = _per_item_char_limit(el, template)
                total = per_item * el.max_items
                existing = by_key.get(key)
                if existing is None or total < existing.max_chars:
                    by_key[key] = TextBudget(
                        content_key=key,
                        role="bullet",
                        max_chars=total,
                        is_list=True,
                    )

    return sorted(by_key.values(), key=lambda b: b.content_key)


# --------------------------------------------------------------------------- #
# LLM prompt construction + parsing
# --------------------------------------------------------------------------- #


_SYSTEM_PROMPT = """You are a senior brand copywriter filling in a tri-fold brochure template.

You will receive:
  1. A business/event description.
  2. Optionally, a structured intake brief with target_audience, offerings,
     differentiators, testimonials, awards, key_stats, hours, CTAs, etc.
  3. A list of content fields, each with a role, content_key, and a HARD
     character budget (spaces included).

Write copy for every field.

Fit rules (in order):
  * Respect every char budget. When a field cannot be said more succinctly, cut — never overflow.
  * **Aim for 80-95% of the budget on every field** — a half-filled region looks thin and wastes the design. Expand with specific, on-brand detail rather than padding or cliché. If you cannot honestly fill that much, stop earlier, but first try harder: add a concrete noun, a stat, a differentiator, a sensory verb, a specific audience, a named capability.
  * Bullets: always produce the requested count unless you have fewer than 3 genuine items. Parallel grammar. Start with verbs or concrete nouns when possible.
  * Body paragraphs / lead_paragraph: aim for 2-4 sentences, not 1.

Substance rules:
  * If an intake brief is provided, use its facts VERBATIM or nearly so — do not invent different testimonials, differentiators, offerings, awards, stats, hours, or CTAs. Draw heading/body copy from the brief's offerings + differentiators + value_proposition.
  * Contact: emit user-supplied phone / email / address / url exactly as given. If not supplied, leave null rather than fabricate a plausible value.
  * Keep tone on-brand with the description (warm, clinical, playful, corporate — match the brief).
  * Do not include copy you have not been asked for.
  * **Per-section quote/quote_attribution**: if the template references sections[i].quote, write a genuine 1-3 sentence pull-quote that *restates one of the section's differentiators or value_proposition phrases* in the customer's voice (still fits char budget). quote_attribution should be a specific role + team ("— Engineering partner, 2024 data-platform build") or a first-name + title ("— Maya R., VP Engineering"). Never just repeat the org name in the attribution. If the brief lists real testimonials, use those verbatim first.

Return one JSON object matching the schema below. No prose, no markdown fences."""


def _format_brief(brief: BrochureBrief) -> list[str]:
    """Serialize a BrochureBrief into a compact bullet block for the LLM."""
    out: list[str] = ["", "INTAKE BRIEF (ground truth — use verbatim where possible):"]
    if brief.value_proposition:
        out.append(f"- Value proposition: {brief.value_proposition}")
    if brief.target_audience:
        out.append(f"- Target audience: {brief.target_audience}")
    if brief.brand_voice:
        out.append(f"- Brand voice: {brief.brand_voice}")
    if brief.offerings:
        out.append(f"- Offerings: {', '.join(brief.offerings)}")
    if brief.differentiators:
        out.append(f"- Differentiators: {', '.join(brief.differentiators)}")
    if brief.key_stats:
        out.append(f"- Key stats: {', '.join(brief.key_stats)}")
    if brief.awards:
        out.append(f"- Awards: {', '.join(brief.awards)}")
    if brief.testimonials:
        out.append("- Testimonials:")
        for t in brief.testimonials:
            tail = f" — {t.attribution}" if t.attribution else ""
            out.append(f"    · \"{t.quote}\"{tail}")
    if brief.founded_year:
        out.append(f"- Founded: {brief.founded_year}")
    if brief.hours:
        out.append(f"- Hours: {brief.hours}")
    if brief.locations:
        out.append(f"- Locations: {', '.join(brief.locations)}")
    if brief.primary_cta:
        out.append(f"- Primary CTA: {brief.primary_cta}")
    if brief.secondary_cta:
        out.append(f"- Secondary CTA: {brief.secondary_cta}")
    if brief.keywords:
        out.append(f"- Keywords / tone cues: {', '.join(brief.keywords)}")
    if brief.source_urls:
        out.append(f"- Source URLs (provenance): {', '.join(brief.source_urls)}")
    return out


def _format_contact(contact) -> list[str]:
    """Surface user-supplied contact fields so the LLM copies them verbatim."""
    if contact is None:
        return []
    lines = ["", "CONTACT (use exactly as given — do not invent values):"]
    for field in ("name", "phone", "email", "url", "address"):
        val = getattr(contact, field, None)
        if val:
            lines.append(f"- {field}: {val}")
    return lines if len(lines) > 1 else []


def _render_budget_prompt(
    budgets: list[TextBudget],
    user_prompt: str,
    audience: str | None,
    color_accent: str,
    bullets_per_key: dict[str, int],
    brief: BrochureBrief | None = None,
    contact=None,
) -> str:
    """Render the user-side prompt listing every field + budget."""
    lines = [
        f"Business / event description: {user_prompt}",
    ]
    if audience:
        lines.append(f"Audience / tone: {audience}")
    if brief is not None:
        lines.extend(_format_brief(brief))
    if contact is not None:
        lines.extend(_format_contact(contact))
    lines.append("")
    lines.append(
        "Fill out the following JSON object. Each leaf value has a HARD "
        "character budget — aim for 80-95% of it; do not under-fill."
    )
    lines.append("")
    lines.append("Budgets (content_key → role, max_chars):")
    for b in budgets:
        if b.is_list:
            n = bullets_per_key.get(b.content_key, 4)
            per = b.max_chars // max(1, n)
            lines.append(
                f'  "{b.content_key}"  list of ~{n} {b.role}(s), '
                f"each ≤ {per} chars (total ≤ {b.max_chars})"
            )
        else:
            lines.append(
                f'  "{b.content_key}"  {b.role}, ≤ {b.max_chars} chars'
            )
    lines.append("")
    lines.append(
        "Also produce these meta fields (not in budgets):"
    )
    lines.append(
        "  hero_concept (6-12 words): the COVER photo. Subject must be centered "
        "in the middle third with clean low-detail areas on the LEFT and RIGHT "
        "edges where the title/subtitle will be overlaid. Landscape 16:9 "
        "composition. Soft depth of field, calm atmosphere. Prefer abstract, "
        "minimal, or wide-establishing scenes over tight detail shots. Avoid "
        "UI screens, server racks, dense technical detail, crowded foregrounds, "
        "text/letters/numbers/signage in the image, or any subject that fills "
        "the frame edge-to-edge."
    )
    lines.append(
        "  per-section image_concept (4-10 words): a CONCRETE SCENE that "
        "reinforces the section's idea. Avoid logos, UI, and text inside the "
        "image. These run inside panels so composition is more flexible than "
        "the cover."
    )
    lines.append(
        f"  color_accent: a brand accent hex color (default {color_accent})."
    )
    lines.append("")
    lines.append("JSON shape:")
    lines.append(
        '{"title": str, "subtitle": str|null, "tagline": str|null, '
        '"org": str, "hero_concept": str, "color_accent": str, '
        '"contact": {"name": str|null, "phone": str|null, '
        '"email": str|null, "url": str|null, "address": str|null}, '
        '"sections": [{"heading": str, "lead_paragraph": str|null, '
        '"body_paragraphs": [str], "bullets": [str], "quote": str|null, '
        '"icon_hint": str|null, "image_concept": str|null}], '
        '"back_panel": {"kind": str, "heading": str|null, '
        '"body": str|null, "bullets": [str], "cta_label": str|null, '
        '"footer_note": str|null}}'
    )
    return "\n".join(lines)


def _infer_bullets_per_key(
    template: TemplateSchema,
) -> dict[str, int]:
    """Infer max_items per bullets content_key so the LLM knows list length."""
    out: dict[str, int] = {}
    for panel in template.panels.values():
        for el in panel.elements:
            if isinstance(el, BulletsElement):
                key = el.content_key
                if key.startswith("section.") and el.section_index is not None:
                    key = f"sections[{el.section_index}].{key.split('.', 1)[1]}"
                out[key] = max(out.get(key, 0), el.max_items)
    return out


def _truncate_at_word_boundary(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    if max_chars <= 3:
        return text[:max_chars]
    clipped = text[: max_chars - 1].rstrip()
    # Back off to the last space if there is one in the clipped region
    space = clipped.rfind(" ")
    if space > max_chars * 0.5:
        clipped = clipped[:space]
    return clipped + "…"


def _apply_budgets(
    data: dict,
    budgets: list[TextBudget],
    bullets_per_key: dict[str, int],
) -> tuple[dict, list[str]]:
    """Walk the LLM's JSON and enforce every budget. Returns (corrected, overflow_keys).

    When a field is over budget, truncate at a word boundary and record the key
    in the overflow list so callers can choose to retry the LLM.
    """
    overflow: list[str] = []

    def get_nested(obj, path):
        cur = obj
        for part in path:
            if isinstance(cur, list):
                if not isinstance(part, int) or part >= len(cur):
                    return None
                cur = cur[part]
            elif isinstance(cur, dict):
                cur = cur.get(part)
            else:
                return None
            if cur is None:
                return None
        return cur

    def set_nested(obj, path, value):
        cur = obj
        for part in path[:-1]:
            cur = cur[part]
        cur[path[-1]] = value

    def path_for_key(key: str) -> list:
        if key.startswith("sections["):
            idx_str, rest = key[len("sections[") :].split("]", 1)
            return ["sections", int(idx_str)] + rest.lstrip(".").split(".")
        if "." in key:
            return key.split(".")
        return [key]

    for b in budgets:
        path = path_for_key(b.content_key)
        value = get_nested(data, path)
        if value is None:
            continue
        if b.is_list and isinstance(value, list):
            # Truncate the list to max_items and each item to its share
            n = bullets_per_key.get(b.content_key, len(value) or 1)
            trimmed = [str(v) for v in value[:n]]
            per_item = b.max_chars // max(1, n)
            fixed = [_truncate_at_word_boundary(v, per_item) for v in trimmed]
            if any(len(orig) > per_item for orig in trimmed):
                overflow.append(b.content_key)
            set_nested(data, path, fixed)
        elif isinstance(value, str):
            if len(value) > b.max_chars:
                overflow.append(b.content_key)
                set_nested(data, path, _truncate_at_word_boundary(value, b.max_chars))
    return data, overflow


def _normalize_to_brochure_content(
    data: dict,
    template: TemplateSchema,
    brief: BrochureBrief | None = None,
    supplied_contact=None,
) -> BrochureContent:
    """Coerce the LLM JSON into a validated BrochureContent, filling defaults.

    When `supplied_contact` is non-None, its non-null fields override whatever
    the LLM produced (the brief said "use exactly as given" — this enforces
    that even if the model drifted). `brief` is attached to the returned
    BrochureContent so it persists to content.json for reuse.
    """
    # Ensure required fields exist
    data.setdefault("title", "Untitled")
    data.setdefault("org", "Organization")
    # Sections: BrochureContent requires >=1; pad if missing.
    sections_raw = data.get("sections")
    if not sections_raw:
        sections_raw = [{"heading": "Overview"}]
    normalized_sections: list[ContentSection] = []
    for sect in sections_raw:
        if not isinstance(sect, dict):
            continue
        sect.setdefault("heading", "Heading")
        normalized_sections.append(
            ContentSection(
                heading=str(sect.get("heading", "Heading")),
                lead_paragraph=sect.get("lead_paragraph"),
                body_paragraphs=[str(p) for p in sect.get("body_paragraphs", []) if p],
                bullets=[str(b) for b in sect.get("bullets", []) if b],
                quote=sect.get("quote"),
                quote_attribution=sect.get("quote_attribution"),
                icon_hint=sect.get("icon_hint"),
                image_concept=sect.get("image_concept"),
            )
        )
    contact_raw = data.get("contact") or {}
    contact_fields = {
        k: contact_raw.get(k) for k in ("name", "phone", "email", "url", "address")
    }
    if supplied_contact is not None:
        for k in contact_fields:
            v = getattr(supplied_contact, k, None)
            if v:
                contact_fields[k] = v
    contact = ContactBlock(**contact_fields)
    back_raw = data.get("back_panel") or {}
    back = BackPanelContent(
        kind=str(back_raw.get("kind", "cta")),
        heading=back_raw.get("heading"),
        body=back_raw.get("body"),
        bullets=[str(b) for b in back_raw.get("bullets", []) if b],
        cta_label=back_raw.get("cta_label"),
        cta_detail=back_raw.get("cta_detail"),
        footer_note=back_raw.get("footer_note"),
    )

    return BrochureContent(
        title=str(data["title"]),
        subtitle=data.get("subtitle"),
        tagline=data.get("tagline"),
        org=str(data["org"]),
        hero_concept=data.get("hero_concept"),
        color_accent=str(data.get("color_accent", "#1E3A5F")),
        contact=contact,
        sections=normalized_sections,
        back_panel=back,
        brief=brief,
        extras={
            k: str(v)
            for k, v in (data.get("extras") or {}).items()
            if isinstance(v, (str, int, float))
        },
    )


# --------------------------------------------------------------------------- #
# Brand-voice helpers (wiring BrandVoice → LLM system prompt + banned-word guard)
# --------------------------------------------------------------------------- #


def _enforce_banned_words(text: str, banned: list[str]) -> list[str]:
    """Return banned matches found in text (case-insensitive, word-boundary).

    Fast-path: when ``banned`` is empty, returns ``[]`` without compiling a
    regex. ``re.escape`` is applied to every banned token so a crafted brand
    kit cannot inject regex metacharacters (threat T-19-01-01).
    """
    if not banned:
        return []
    pattern = re.compile(
        r"\b(" + "|".join(re.escape(w) for w in banned) + r")\b",
        re.IGNORECASE,
    )
    return pattern.findall(text)


def _assemble_system_prompt(brand_voice: BrandVoice | None, base: str) -> str:
    """Prepend a VOICE DIRECTIVE block to the system prompt when brand_voice is provided.

    Returns ``base`` unchanged when ``brand_voice is None`` (backwards-compatible).
    The module-level ``_SYSTEM_PROMPT`` constant is never mutated — a new string
    is produced on every call.
    """
    if brand_voice is None:
        return base
    tone = (brand_voice.tone or "").strip() or "(none)"
    phrases = brand_voice.example_phrases or []
    phrases_block = (
        "\n".join(f'    - "{p}"' for p in phrases) if phrases else "    - (none)"
    )
    banned = brand_voice.banned_words or []
    banned_block = (
        "\n".join(f'    - "{w}"' for w in banned) if banned else "    - (none)"
    )
    directive = (
        "VOICE DIRECTIVE (copy must sound like this brand):\n"
        f"  Tone: {tone}\n"
        "  Exemplar phrases (match cadence, do not quote verbatim):\n"
        f"{phrases_block}\n"
        "  Banned words / phrases (NEVER use these — find a synonym):\n"
        f"{banned_block}\n\n"
    )
    return directive + base


def _scan_banned(
    obj: object, banned: list[str], _path: str = ""
) -> list[tuple[str, str]]:
    """Walk a nested JSON-shaped structure and collect (key_path, match) pairs.

    Case-insensitive + word-boundary matching via ``_enforce_banned_words``.
    """
    hits: list[tuple[str, str]] = []
    if isinstance(obj, str):
        for m in _enforce_banned_words(obj, banned):
            hits.append((_path or "(root)", m))
    elif isinstance(obj, dict):
        for k, v in obj.items():
            hits.extend(
                _scan_banned(v, banned, f"{_path}.{k}" if _path else str(k))
            )
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            hits.extend(_scan_banned(v, banned, f"{_path}[{i}]"))
    return hits


# --------------------------------------------------------------------------- #
# Public entry point
# --------------------------------------------------------------------------- #


async def generate_content_from_prompt(
    template: TemplateSchema,
    prompt: str,
    *,
    audience: str | None = None,
    color_accent: str = "#1E3A5F",
    brief: BrochureBrief | None = None,
    contact=None,  # ContactBlock | None
    settings: Settings | None = None,
    text_client: TextClient | None = None,
    brand_voice: BrandVoice | None = None,
    tighter_budgets: dict[str, int] | None = None,
) -> BrochureContent:
    """Ask the configured LLM to write a full BrochureContent that fits
    `template`'s char budgets.

    `brief` (BrochureBrief) and `contact` (ContactBlock) are ground-truth
    inputs the LLM is instructed to use verbatim. The brief embeds the
    interrogative intake (offerings, differentiators, testimonials, awards,
    hours, CTAs, …) so the model anchors copy on real facts instead of
    inventing. `contact` is surfaced the same way so phone/address/email
    never get fabricated.

    ``brand_voice`` (Phase 19) injects a VOICE DIRECTIVE block at the top of
    the system prompt listing tone, exemplar phrases, and banned words. When
    the LLM response contains a banned word, one retry is issued with a
    stricter user prompt; if the retry still contains a banned word,
    ``BrandVoiceViolationError`` is raised.

    ``tighter_budgets`` is accepted for forward compatibility with Plan 19-08
    and is currently unused.

    Fields that come back over budget are automatically truncated at word
    boundaries; on the first occurrence of any overflow we issue one tighter
    retry before falling back to truncation.
    """
    # `tighter_budgets` is accepted for forward-compat (Plan 19-08) but
    # deliberately not consumed yet — ignore explicitly to silence linters.
    _ = tighter_budgets

    if settings is None:
        settings = Settings()
    _owns_client = False
    if text_client is None:
        text_client = build_text_client(settings)
        _owns_client = True

    budgets = collect_text_budgets(template)
    bullets_per_key = _infer_bullets_per_key(template)

    user_prompt = _render_budget_prompt(
        budgets, prompt, audience, color_accent, bullets_per_key,
        brief=brief, contact=contact,
    )
    system_prompt = _assemble_system_prompt(brand_voice, _SYSTEM_PROMPT)

    async def _ask(user: str) -> dict:
        """Single LLM round with JSON-decode + parse-error handling."""
        raw_text = await text_client.complete(
            system=system_prompt,
            user=user,
            response_format="json",
        )
        return json.loads(raw_text)

    try:
        try:
            data = await _ask(user_prompt)
        except (VisionResponseParseError, json.JSONDecodeError) as err:
            logger.warning("text_gen_initial_json_invalid", error=str(err)[:200])
            try:
                data = await _ask(
                    user_prompt
                    + "\n\nYour previous response was not valid JSON. "
                    "Return only a single valid JSON object with no prose, "
                    "no markdown fences, no trailing commas, and every string "
                    "double-quoted and properly escaped."
                )
            except (VisionResponseParseError, json.JSONDecodeError) as err2:
                logger.warning("text_gen_second_json_invalid", error=str(err2)[:200])
                data = {"title": "Untitled", "org": "Organization"}

        # Voice guard: scan for banned words BEFORE the budget retry so voice
        # and overflow retries do not compose or collide (19-RESEARCH.md
        # Open Risk #4). Only runs when brand_voice has non-empty banned_words.
        banned_words = brand_voice.banned_words if brand_voice else []
        if banned_words:
            hits = _scan_banned(data, banned_words)
            if hits:
                match_list = sorted({m for _, m in hits})
                key_list = sorted({k for k, _ in hits})
                logger.info(
                    "text_gen_banned_word_violation",
                    keys=key_list,
                    matches=match_list,
                )
                retry_user = (
                    user_prompt
                    + "\n\nYour previous response used banned words: "
                    + ", ".join(match_list)
                    + ". Rewrite the copy without these words and return the full JSON again."
                )
                try:
                    raw2 = await text_client.complete(
                        system=system_prompt,
                        user=retry_user,
                        response_format="json",
                    )
                    data = json.loads(raw2)
                except (VisionResponseParseError, json.JSONDecodeError) as err:
                    logger.warning(
                        "text_gen_voice_retry_parse_failed", error=str(err)[:200]
                    )
                hits2 = _scan_banned(data, banned_words)
                if hits2:
                    match_list2 = sorted({m for _, m in hits2})
                    key_list2 = sorted({k for k, _ in hits2})
                    raise BrandVoiceViolationError(
                        f"copy contained banned words after retry: {match_list2}",
                        banned_matches=match_list2,
                        keys=key_list2,
                    )

        data, overflow = _apply_budgets(data, budgets, bullets_per_key)

        if overflow and _MAX_RETRIES > 0:
            logger.info("text_gen_overflow_retry", keys=overflow)
            retry_user = (
                user_prompt
                + "\n\nYour previous response overflowed on these fields: "
                + ", ".join(overflow)
                + ". Rewrite each in ~20% fewer characters and return the full JSON again."
            )
            try:
                raw2 = await text_client.complete(
                    system=system_prompt,
                    user=retry_user,
                    response_format="json",
                )
                data = json.loads(raw2)
                data, _ = _apply_budgets(data, budgets, bullets_per_key)
            except (VisionAPIError, VisionResponseParseError, json.JSONDecodeError) as err:
                logger.warning("text_gen_retry_failed", error=str(err))
                # Keep the truncated first response

        return _normalize_to_brochure_content(
            data, template, brief=brief, supplied_contact=contact
        )
    finally:
        if _owns_client and hasattr(text_client, "aclose"):
            await text_client.aclose()  # type: ignore[attr-defined]
