"""Tri-fold landscape brochure generator — parallel to the flyer pipeline.

Phase 5 scope: data models + panel geometry only. Pipeline, vision, composer,
PDF assembly, and CLI are added in phases 6-9.
"""

from flyer_generator.brochure.models import (
    BrochureBackPanel,
    BrochureInput,
    BrochureOutput,
    BrochureSection,
    ContactBlock,
    validate_hex_color,
)

__all__ = [
    "BrochureBackPanel",
    "BrochureInput",
    "BrochureOutput",
    "BrochureSection",
    "ContactBlock",
    "validate_hex_color",
]
