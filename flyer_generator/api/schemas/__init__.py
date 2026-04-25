"""Phase 20 API schemas barrel."""

from __future__ import annotations

from flyer_generator.api.schemas.brand_kits import (
    BrandKitDetail,
    BrandKitFetchRequest,
    BrandKitSummary,
    PaginatedBrandKits,
)
from flyer_generator.api.schemas.brochures import BrochureCreateRequest
from flyer_generator.api.schemas.flyers import FlyerCreateRequest
from flyer_generator.api.schemas.jobs import JobCreated, JobDetail, ResultLink
from flyer_generator.api.schemas.postcards import (
    AddressBlock,
    PostcardCreateRequest,
    PostcardDetail,
)
from flyer_generator.api.schemas.renders import RenderSummary
from flyer_generator.api.schemas.social import (
    CampaignCreateRequest,
    PostCreateRequest,
)

__all__ = sorted(
    [
        "AddressBlock",
        "BrandKitDetail",
        "BrandKitFetchRequest",
        "BrandKitSummary",
        "BrochureCreateRequest",
        "CampaignCreateRequest",
        "FlyerCreateRequest",
        "JobCreated",
        "JobDetail",
        "PaginatedBrandKits",
        "PostCreateRequest",
        "PostcardCreateRequest",
        "PostcardDetail",
        "RenderSummary",
        "ResultLink",
    ]
)
