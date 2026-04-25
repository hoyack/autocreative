"""Phase 20 routes barrel — each module exposes a `router` APIRouter."""

from __future__ import annotations

from flyer_generator.api.routes import (
    brand_kits,
    brochures,
    flyers,
    jobs,
    postcards,
    posters,
    renders,
    social,
)

# Ordered list consumed by build_app() to call app.include_router in sequence.
ROUTERS = [
    brand_kits.router,
    flyers.router,
    brochures.router,
    postcards.router,
    posters.router,
    social.router,
    jobs.router,
    renders.router,
]

__all__ = [
    "ROUTERS",
    "brand_kits",
    "brochures",
    "flyers",
    "jobs",
    "postcards",
    "posters",
    "renders",
    "social",
]
