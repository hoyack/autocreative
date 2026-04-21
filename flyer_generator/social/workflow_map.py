"""ComfyCloud workflow selection for social-post aspect ratios.

Per 19-RESEARCH.md §Workflow Aspect Mapping: the existing 8 workflow files in
``flyer_generator/workflows/`` cover every social platform aspect. No new
workflows needed.

This module is pure and stateless: no I/O, no global state, no network.
It is consumed by Plan 06 (single-post image generation) and Plan 07
(campaign shared-hero fan-out).
"""

from __future__ import annotations

from typing import Literal, Sequence

from flyer_generator.social.models import Platform

AspectString = Literal["1:1", "4:5", "1.91:1", "16:9", "9:16"]
WorkflowName = Literal["standard_square", "turbo_portrait", "turbo_landscape"]

# Per 19-RESEARCH.md §Workflow Aspect Mapping lines 676-680
_ASPECT_TO_WORKFLOW: dict[str, WorkflowName] = {
    "1:1": "standard_square",
    "4:5": "turbo_portrait",
    "9:16": "turbo_portrait",
    "16:9": "turbo_landscape",
    "1.91:1": "turbo_landscape",
}

# Per platform, the primary aspect the CAMPAIGN source hero should cover.
# See 19-CONTEXT.md §Image generation + 19-RESEARCH.md §Campaign Image Crop.
PLATFORM_TO_ASPECT: dict[Platform, AspectString] = {
    "linkedin": "1.91:1",  # link preview is primary
    "twitter": "16:9",
    "instagram": "1:1",  # feed square is primary
    "facebook": "1.91:1",  # link preview primary
}


def select_workflow_for_aspect(aspect: str) -> WorkflowName:
    """Return the ComfyCloud workflow name for a target aspect string.

    Args:
        aspect: Aspect ratio string such as ``"1:1"``, ``"9:16"``, ``"1.91:1"``.

    Returns:
        One of ``"standard_square"``, ``"turbo_portrait"``, ``"turbo_landscape"``.

    Raises:
        ValueError: when ``aspect`` is not a recognized ratio. This is a
            programmer error (unknown aspect), not a user-input error, so
            ``ValueError`` is used rather than ``SocialError``.
    """
    if aspect not in _ASPECT_TO_WORKFLOW:
        raise ValueError(
            f"unknown aspect {aspect!r}; known: {sorted(_ASPECT_TO_WORKFLOW)}"
        )
    return _ASPECT_TO_WORKFLOW[aspect]


def select_workflow_for_campaign(
    platforms: Sequence[Platform],
    *,
    include_story: bool = False,
) -> WorkflowName:
    """Pick the best single workflow to source a campaign's shared hero.

    Per 19-RESEARCH.md §Campaign Image Crop Strategy §"What the planner must
    decide":

    - If any platform needs 9:16 (IG story), use ``turbo_portrait`` (covers
      1:1 + 4:5 + 9:16 via center-crop without a 45% horizontal loss).
    - Else if every platform prefers landscape (LI/TW/FB), use
      ``turbo_landscape``.
    - Else if every platform prefers square (IG/FB feed), use
      ``standard_square``.
    - Mixed aspects default to ``standard_square`` (best compromise).

    Args:
        platforms: Non-empty sequence of target platforms.
        include_story: If true and Instagram is in ``platforms``, force
            portrait workflow to satisfy the 9:16 story slot.

    Returns:
        One of ``"standard_square"``, ``"turbo_portrait"``, ``"turbo_landscape"``.

    Raises:
        ValueError: when ``platforms`` is empty.
    """
    if not platforms:
        raise ValueError("select_workflow_for_campaign requires at least one platform")
    if include_story and "instagram" in platforms:
        return "turbo_portrait"
    aspects = {PLATFORM_TO_ASPECT[p] for p in platforms}
    # If every platform wants a landscape aspect, use landscape workflow
    if aspects and aspects.issubset({"16:9", "1.91:1"}):
        return "turbo_landscape"
    # If every platform wants square, use standard_square
    if aspects and aspects.issubset({"1:1"}):
        return "standard_square"
    # Mixed: prefer square (covers most cases with minor letterbox concerns)
    return "standard_square"


# Short-form alias used by the orchestrator/success-criteria checks.
# Prefer :func:`select_workflow_for_aspect` in new call sites.
workflow_for_aspect = select_workflow_for_aspect
