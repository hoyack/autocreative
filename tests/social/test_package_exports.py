"""Per checker B1: direct-module imports only.

Asserts the consolidated barrel export in flyer_generator/social/__init__.py
(Plan 09 output) exposes every public name, that __all__ is sorted, and that
the SOC-11 invariant (no publishing-API imports) holds for every .py file
under flyer_generator/social/.
"""

from __future__ import annotations

import flyer_generator.social as social


_EXPECTED_EXPORTS = {
    "Campaign",
    "ImageAspect",
    "ImageSlot",
    "Intent",
    "PLATFORM_REGISTRY",
    "Platform",
    "PlatformRules",
    "Post",
    "PostBrief",
    "PostCopy",
    "PostSpec",
    "PostTemplate",
    "SocialAuditReport",
    "TextSlot",
    "ValidationIssue",
    "ValidationReport",
    "audit_post",
    "flesch_kincaid_grade",
    "format_voice_directive",
    "generate_campaign",
    "generate_post",
    "generate_social_copy",
    "list_campaigns",
    "list_post_templates",
    "load_campaign",
    "load_platform_rules",
    "load_post",
    "load_post_template",
    "parse_template_name",
    "resolve_campaign_dir",
    "save_campaign",
    "save_post",
    "validate_post",
}


def test_all_expected_names_in_all_attr() -> None:
    actual = set(social.__all__)
    missing = _EXPECTED_EXPORTS - actual
    assert not missing, f"missing from __all__: {missing}"


def test_all_is_sorted() -> None:
    assert social.__all__ == sorted(social.__all__)


def test_every_name_in_all_is_importable() -> None:
    for name in social.__all__:
        assert hasattr(social, name), (
            f"{name} in __all__ but not importable from module"
        )


def test_no_platform_api_imports_in_social_package() -> None:
    """I-01: SOC-11 (publishing is OUT OF SCOPE for Phase 19) requires that
    no publishing-API client library leaks into the social package. Scan
    every .py file under flyer_generator/social/ for banned imports.
    """
    import pathlib

    banned_modules = [
        "linkedin_api",
        "tweepy",
        "facebook_sdk",
        "facebook_business",
        "google_api_python_client",
        "googleapiclient",
        "instagrapi",
        "instagram_private_api",
    ]
    root = pathlib.Path(social.__file__).parent
    offenders: list[tuple[pathlib.Path, str]] = []
    for py in root.rglob("*.py"):
        text = py.read_text(encoding="utf-8")
        for mod in banned_modules:
            # Match `import <mod>` or `from <mod>` at a line start.
            if f"import {mod}" in text or f"from {mod}" in text:
                offenders.append((py.relative_to(root), mod))
    assert not offenders, (
        f"publishing-API imports found in social package (SOC-11 violation): "
        f"{offenders}"
    )
