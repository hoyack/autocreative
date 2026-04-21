"""Voice-aware social copy generation — thin wrapper over text_client.complete.

Reuses:
- Plan 01's _enforce_banned_words + BrandVoiceViolationError (imported; do NOT duplicate)
- flyer_generator.brochure.llm_client.build_text_client for the retry chain
"""

from __future__ import annotations

import json

import structlog

from flyer_generator.brand_kit.models import BrandVoice
from flyer_generator.brochure.llm_client import build_text_client
from flyer_generator.brochure.schema_renderer.text_gen import _enforce_banned_words
from flyer_generator.config import Settings
from flyer_generator.errors import BrandVoiceViolationError
from flyer_generator.social.models import (
    PlatformRules,
    PostBrief,
    PostCopy,
)
from flyer_generator.social.schemas.schema_model import PostTemplate

logger = structlog.get_logger(__name__)


def format_voice_directive(brand_voice: BrandVoice | None) -> str:
    """Return the VOICE DIRECTIVE block (empty string when brand_voice is None)."""
    if brand_voice is None:
        return ""
    tone = (brand_voice.tone or "").strip() or "(none)"
    phrases = brand_voice.example_phrases or []
    phrases_block = (
        "\n".join(f'    - "{p}"' for p in phrases) if phrases else "    - (none)"
    )
    banned = brand_voice.banned_words or []
    banned_block = (
        "\n".join(f'    - "{w}"' for w in banned) if banned else "    - (none)"
    )
    return (
        "VOICE DIRECTIVE (copy must sound like this brand):\n"
        f"  Tone: {tone}\n"
        "  Exemplar phrases (match cadence, do not quote verbatim):\n"
        f"{phrases_block}\n"
        "  Banned words / phrases (NEVER use these — find a synonym):\n"
        f"{banned_block}\n\n"
    )


def _build_system_prompt(brand_voice: BrandVoice | None) -> str:
    voice = format_voice_directive(brand_voice)
    base = (
        "You are a social-media copywriter. Return a single JSON object with exactly "
        "these keys: copy.title (short headline), copy.body (main text), copy.cta "
        "(call to action), copy.hashtags (list of strings, each starting with #). "
        "Honor the per-key character budgets and the platform constraints given in "
        "the user message. Return ONLY the JSON object with no commentary."
    )
    return voice + base


def _build_user_prompt(
    brief: PostBrief,
    platform_rules: PlatformRules,
    template: PostTemplate,
) -> str:
    body_budget = min(
        template.text_budgets.get("copy.body", platform_rules.body_max_chars),
        platform_rules.body_max_chars,
    )
    title_budget = template.text_budgets.get("copy.title", 80)
    cta_budget = template.text_budgets.get("copy.cta", 40)
    hashtag_count = platform_rules.hashtag_recommended_max

    lines: list[str] = [
        f"PLATFORM: {platform_rules.platform}",
        f"INTENT: {brief.intent}",
        f"TOPIC: {brief.topic}",
    ]
    if brief.cta:
        lines.append(f"CTA OVERRIDE: {brief.cta}")
    if brief.source_url:
        lines.append(f"SOURCE URL (may or may not be embeddable): {brief.source_url}")
    if brief.image_hint:
        lines.append(f"IMAGE HINT: {brief.image_hint}")
    lines.extend([
        "",
        "BUDGETS (hard max in characters):",
        f"  copy.title: {title_budget}",
        f"  copy.body: {body_budget}",
        f"  copy.cta: {cta_budget}",
        "",
        f"HASHTAGS FOR {platform_rules.platform.upper()}:",
        f"  - Produce exactly {hashtag_count} hashtags",
    ])
    if platform_rules.hashtag_hard_max is not None:
        lines.append(f"  - Hard cap: {platform_rules.hashtag_hard_max}")
    lines.extend([
        "  - Each hashtag: 4-24 chars, alphanumeric + underscore, start with #",
    ])
    if brief.hashtags_seed:
        lines.append(f"  - Seed keywords: {', '.join(brief.hashtags_seed)}")
    lines.append("  - No duplicates; prefer concrete nouns")
    if platform_rules.strips_links_in_caption:
        lines.append("")
        lines.append(
            f"LINK POLICY: {platform_rules.platform} strips URLs from captions. "
            "Do NOT include clickable URLs in copy.body; use 'link in bio' language instead."
        )
    return "\n".join(lines)


def _scan_banned_in_copy(copy_dict: dict, banned: list[str]) -> tuple[list[str], list[str]]:
    """Return (all_matches, key_paths_with_hits)."""
    if not banned:
        return ([], [])
    matches: list[str] = []
    keys: list[str] = []
    for key, val in copy_dict.items():
        if isinstance(val, str):
            hits = _enforce_banned_words(val, banned)
            if hits:
                matches.extend(hits)
                keys.append(key)
        elif isinstance(val, list):
            for i, item in enumerate(val):
                if isinstance(item, str):
                    hits = _enforce_banned_words(item, banned)
                    if hits:
                        matches.extend(hits)
                        keys.append(f"{key}[{i}]")
    return (sorted(set(matches)), sorted(set(keys)))


def _normalize_to_post_copy(
    raw: dict, platform_rules: PlatformRules
) -> PostCopy:
    # The system prompt describes keys as "copy.title" / "copy.body" — LLMs
    # reasonably interpret this as EITHER dotted-flat keys OR a nested "copy"
    # object. Accept both shapes: unwrap the nested case first.
    if isinstance(raw.get("copy"), dict):
        nested = raw["copy"]
    else:
        nested = {}
    title = nested.get("title") or raw.get("copy.title") or raw.get("title") or ""
    body = nested.get("body") or raw.get("copy.body") or raw.get("body") or ""
    cta = nested.get("cta") or raw.get("copy.cta") or raw.get("cta") or None
    hashtags_raw = (
        nested.get("hashtags") or raw.get("copy.hashtags") or raw.get("hashtags") or []
    )
    if isinstance(hashtags_raw, str):
        hashtags = [h.strip() for h in hashtags_raw.split() if h.strip()]
    else:
        hashtags = [str(h).strip() for h in hashtags_raw if str(h).strip()]
    # Hard-cap hashtags to platform maximum
    if (
        platform_rules.hashtag_hard_max is not None
        and len(hashtags) > platform_rules.hashtag_hard_max
    ):
        hashtags = hashtags[: platform_rules.hashtag_hard_max]
    return PostCopy(title=title, body=body, cta=cta, hashtags=hashtags)


async def generate_social_copy(
    brief: PostBrief,
    platform_rules: PlatformRules,
    template: PostTemplate,
    *,
    brand_voice: BrandVoice | None = None,
    settings: Settings | None = None,
    text_client=None,
) -> PostCopy:
    """Generate voice-aware social copy for a single post.

    Raises BrandVoiceViolationError on repeat banned-word violation after one retry.
    """
    if settings is None:
        settings = Settings()
    _owns_client = False
    if text_client is None:
        text_client = build_text_client(settings)
        _owns_client = True

    system_prompt = _build_system_prompt(brand_voice)
    user_prompt = _build_user_prompt(brief, platform_rules, template)

    log = logger.bind(
        platform=platform_rules.platform,
        intent=brief.intent,
        topic=brief.topic[:40],
    )
    try:
        log.info("social_copy_generate_start")
        raw1 = await text_client.complete(
            system=system_prompt, user=user_prompt, response_format="json"
        )
        data = json.loads(raw1)

        # Banned-word pass
        banned = brand_voice.banned_words if brand_voice else []
        if banned:
            matches, keys = _scan_banned_in_copy(data, banned)
            if matches:
                log.info(
                    "social_copy_banned_word_violation",
                    keys=keys,
                    matches=matches,
                )
                retry_user = (
                    user_prompt
                    + "\n\nYour previous response used banned words: "
                    + ", ".join(matches)
                    + ". Rewrite the copy without them and return the full JSON again."
                )
                raw2 = await text_client.complete(
                    system=system_prompt, user=retry_user, response_format="json"
                )
                data = json.loads(raw2)
                matches2, keys2 = _scan_banned_in_copy(data, banned)
                if matches2:
                    raise BrandVoiceViolationError(
                        f"social copy contained banned words after retry: {matches2}",
                        banned_matches=matches2,
                        keys=keys2,
                    )

        copy = _normalize_to_post_copy(data, platform_rules)
        log.info("social_copy_generate_end", title_len=len(copy.title or ""), body_len=len(copy.body))
        return copy
    finally:
        if _owns_client and hasattr(text_client, "aclose"):
            await text_client.aclose()
