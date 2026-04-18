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
    PanelName,
    PanelRect,
    ResolvedBrochureLayout,
    SheetName,
    validate_hex_color,
)
from flyer_generator.brochure.pipeline import BrochureGenerator, generate_brochure
from flyer_generator.brochure.stages.layout import compute_panel_layout

__all__ = [
    "BrochureBackPanel",
    "BrochureGenerator",
    "BrochureInput",
    "BrochureOutput",
    "BrochureSection",
    "ContactBlock",
    "PanelName",
    "PanelRect",
    "ResolvedBrochureLayout",
    "SheetName",
    "compute_panel_layout",
    "generate_brochure",
    "validate_hex_color",
]
