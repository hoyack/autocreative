"""Tests for flyer_generator.social.workflow_map.

Per checker B1: direct-module imports only (no star imports).
"""

from __future__ import annotations

import pytest

from flyer_generator.social.workflow_map import (
    PLATFORM_TO_ASPECT,
    select_workflow_for_aspect,
    select_workflow_for_campaign,
)


def test_select_workflow_for_aspect_square() -> None:
    assert select_workflow_for_aspect("1:1") == "standard_square"


def test_select_workflow_for_aspect_portrait() -> None:
    assert select_workflow_for_aspect("9:16") == "turbo_portrait"
    assert select_workflow_for_aspect("4:5") == "turbo_portrait"


def test_select_workflow_for_aspect_landscape() -> None:
    # Landscape aspects use qwen_landscape (Qwen-Image-2512) as of 2026-04-21 —
    # Ernie-family hallucinated text in abstract backdrops even with negatives.
    assert select_workflow_for_aspect("16:9") == "qwen_landscape"
    assert select_workflow_for_aspect("1.91:1") == "qwen_landscape"


def test_select_workflow_for_aspect_unknown_raises() -> None:
    with pytest.raises(ValueError):
        select_workflow_for_aspect("bad")


def test_select_workflow_for_campaign_with_story_uses_portrait() -> None:
    assert (
        select_workflow_for_campaign(["linkedin", "instagram"], include_story=True)
        == "turbo_portrait"
    )


def test_select_workflow_for_campaign_all_landscape() -> None:
    assert (
        select_workflow_for_campaign(
            ["linkedin", "twitter", "facebook"], include_story=False
        )
        == "turbo_landscape"
    )


def test_select_workflow_for_campaign_all_square() -> None:
    assert (
        select_workflow_for_campaign(["instagram"], include_story=False)
        == "standard_square"
    )


def test_select_workflow_for_campaign_empty_raises() -> None:
    with pytest.raises(ValueError):
        select_workflow_for_campaign([], include_story=False)


def test_platform_to_aspect_has_all_four_platforms() -> None:
    assert set(PLATFORM_TO_ASPECT) == {"linkedin", "twitter", "instagram", "facebook"}
