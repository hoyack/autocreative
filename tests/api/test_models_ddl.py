"""Smoke test: Phase 20 ORM models produce valid DDL against SQLite."""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine, inspect

from flyer_generator.api.models import (
    Base,
    BrandKitRecord,
    BrochureRecord,
    CampaignRecord,
    FlyerRecord,
    JobKind,
    JobRecord,
    JobStatus,
    PostRecord,
    RenderRecord,
)


def test_all_tables_create_cleanly_on_sqlite() -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    insp = inspect(engine)
    tables = set(insp.get_table_names())
    assert {
        "jobs",
        "renders",
        "brand_kits",
        "flyers",
        "brochures",
        "campaigns",
        "posts",
    }.issubset(tables), tables


def test_enums_serialize_to_strings() -> None:
    assert JobStatus.QUEUED.value == "queued"
    assert JobKind.SOCIAL_CAMPAIGN.value == "social_campaign"
    # str-subclass: direct string comparison works
    assert JobStatus.RUNNING == "running"


def test_record_classes_exist() -> None:
    for cls in (
        BrandKitRecord,
        FlyerRecord,
        BrochureRecord,
        CampaignRecord,
        PostRecord,
        RenderRecord,
        JobRecord,
    ):
        assert cls.__tablename__, cls
