"""Brand kit subsystem (Phase 18).

This package's public API is assembled by Plan 07 into a single
re-export block. Plans 01-06 and 08 intentionally do NOT write to
this file; every intra-phase test uses direct-module imports such as:

    from flyer_generator.brand_kit.storage import save_brand_kit
    from flyer_generator.brand_kit.models import BrandKit
    from flyer_generator.brand_kit.contrast import wcag_ratio

After Plan 07 lands, end users may import the public names directly
from `flyer_generator.brand_kit` for convenience.
"""
