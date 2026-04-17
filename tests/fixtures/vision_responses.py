"""Mock vision response JSON fixtures for VisionEvaluator tests."""

import json

APPROVED_RESPONSE = {
    "approved": True,
    "confidence": 0.85,
    "rejection_reasons": [],
    "refinement_hint": "",
    "zones": {
        "title": "TOP_CENTER",
        "details": "BOTTOM_CENTER",
        "fee_badge": "TOP_RIGHT",
        "org_credit": "BOTTOM_CENTER",
    },
    "text_color": "white",
    "mood_tags": ["warm", "inviting"],
}

REJECTED_RESPONSE = {
    "approved": False,
    "confidence": 0.3,
    "rejection_reasons": ["Image contains visible text", "Too cluttered for overlay"],
    "refinement_hint": "Generate cleaner background with more bokeh areas",
    "zones": None,
    "text_color": "white",
    "mood_tags": ["busy"],
}

LOW_CONFIDENCE_RESPONSE = {
    "approved": True,
    "confidence": 0.45,
    "rejection_reasons": [],
    "refinement_hint": "",
    "zones": {
        "title": "TOP_CENTER",
        "details": "BOTTOM_CENTER",
        "fee_badge": "TOP_RIGHT",
        "org_credit": "BOTTOM_CENTER",
    },
    "text_color": "white",
    "mood_tags": ["neutral"],
}

INVALID_ZONE_RESPONSE = {
    "approved": True,
    "confidence": 0.9,
    "rejection_reasons": [],
    "refinement_hint": "",
    "zones": {
        "title": "INVALID_ZONE",
        "details": "BOTTOM_CENTER",
        "fee_badge": "TOP_RIGHT",
        "org_credit": "BOTTOM_CENTER",
    },
    "text_color": "white",
    "mood_tags": ["warm"],
}

NULL_ZONES_APPROVED_RESPONSE = {
    "approved": True,
    "confidence": 0.8,
    "rejection_reasons": [],
    "refinement_hint": "",
    "zones": None,
    "text_color": "white",
    "mood_tags": ["warm"],
}

MARKDOWN_WRAPPED = (
    "```json\n"
    + json.dumps(APPROVED_RESPONSE)
    + "\n```"
)

PROSE_WRAPPED = (
    "Here is my evaluation:\n\n"
    + json.dumps(APPROVED_RESPONSE)
    + "\n\nLet me know if you need anything else."
)
