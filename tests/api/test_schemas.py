"""Plan 20-05: schema smoke + round-trip tests.

Validates the must_haves:
- Every new schema is importable from the barrel.
- Slug regex ``^[a-z0-9][a-z0-9-]*$`` is consistently enforced.
- Platform / Intent Literals reject unknown values.
- ``extra="forbid"`` is enabled on every request/response model.
- ``model_dump(mode="json")`` output round-trips cleanly through
  ``json.dumps`` / ``model_validate``.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from flyer_generator.api.models.job import JobKind, JobStatus
from flyer_generator.api.schemas import (
    BrandKitDetail,
    BrandKitFetchRequest,
    BrandKitSummary,
    BrochureCreateRequest,
    CampaignCreateRequest,
    FlyerCreateRequest,
    JobCreated,
    JobDetail,
    PaginatedBrandKits,
    PostCreateRequest,
    RenderSummary,
    ResultLink,
)
from flyer_generator.brand_kit.models import BrandKit
from flyer_generator.brochure.schema_renderer.content_model import (
    BrochureContent,
    ContentSection,
)
from flyer_generator.models import EventInput


def _event() -> EventInput:
    return EventInput(
        title="T",
        date="D",
        time="TT",
        location_name="L",
        location_address="A",
        fees="F",
        org="O",
        style_concept="SC",
        style_preset="ph",
    )


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Must-have truth #1: barrel import succeeds
# ---------------------------------------------------------------------------


def test_barrel_imports_advertise_all_schemas() -> None:
    # Importing from the package namespace must surface each schema.
    from flyer_generator.api import schemas

    for name in (
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
        "RenderSummary",
        "ResultLink",
    ):
        assert hasattr(schemas, name), f"barrel missing {name}"
        assert name in schemas.__all__, f"__all__ missing {name}"


# ---------------------------------------------------------------------------
# Must-have truth #3: every model has ConfigDict(extra="forbid")
# ---------------------------------------------------------------------------


_ALL_REQUEST_MODELS = [
    BrandKitFetchRequest,
    BrochureCreateRequest,
    CampaignCreateRequest,
    FlyerCreateRequest,
    PostCreateRequest,
]
_ALL_RESPONSE_MODELS = [
    BrandKitDetail,
    BrandKitSummary,
    JobCreated,
    JobDetail,
    PaginatedBrandKits,
    RenderSummary,
    ResultLink,
]


@pytest.mark.parametrize("model_cls", _ALL_REQUEST_MODELS + _ALL_RESPONSE_MODELS)
def test_every_schema_forbids_extra_fields(model_cls: type) -> None:
    assert model_cls.model_config.get("extra") == "forbid", (
        f"{model_cls.__name__} must have ConfigDict(extra='forbid')"
    )


# ---------------------------------------------------------------------------
# Must-have truth #3: model_dump(mode="json") round-trips
# ---------------------------------------------------------------------------


def test_job_created_round_trips() -> None:
    j = JobCreated(job_id="01HJOBA" + "B" * 19)
    dumped = j.model_dump(mode="json")
    assert JobCreated.model_validate(json.loads(json.dumps(dumped))) == j


def test_job_detail_round_trips_string_result_ref() -> None:
    jd = JobDetail(
        id="01HJOB" + "C" * 20,
        kind=JobKind.FLYER,
        status=JobStatus.SUCCEEDED,
        started_at=_now(),
        completed_at=_now(),
        result_ref="/api/v1/renders/01HR" + "D" * 22 + "/image",
        created_at=_now(),
    )
    dumped = jd.model_dump(mode="json")
    rt = JobDetail.model_validate(json.loads(json.dumps(dumped)))
    assert isinstance(rt.result_ref, str)
    assert rt.kind == JobKind.FLYER
    assert rt.status == JobStatus.SUCCEEDED


def test_job_detail_round_trips_list_result_ref() -> None:
    jd = JobDetail(
        id="01HJOB" + "E" * 20,
        kind=JobKind.SOCIAL_CAMPAIGN,
        status=JobStatus.SUCCEEDED,
        result_ref=[
            ResultLink(platform="linkedin", url="/api/v1/renders/01HR" + "F" * 22 + "/image"),
            ResultLink(platform="twitter", url="/api/v1/renders/01HR" + "G" * 22 + "/image"),
        ],
        created_at=_now(),
    )
    dumped = jd.model_dump(mode="json")
    rt = JobDetail.model_validate(json.loads(json.dumps(dumped)))
    assert isinstance(rt.result_ref, list)
    assert rt.result_ref[0].platform == "linkedin"
    assert rt.result_ref[1].platform == "twitter"


def test_job_detail_result_ref_accepts_none() -> None:
    # Queued / running jobs have no result yet.
    jd = JobDetail(
        id="01HJOB" + "H" * 20,
        kind=JobKind.FLYER,
        status=JobStatus.QUEUED,
        created_at=_now(),
    )
    dumped = jd.model_dump(mode="json")
    rt = JobDetail.model_validate(json.loads(json.dumps(dumped)))
    assert rt.result_ref is None


def test_render_summary_round_trips() -> None:
    rs = RenderSummary(id="01HR" + "I" * 22, kind="flyer", comfy_job_id="cf-123", created_at=_now())
    dumped = rs.model_dump(mode="json")
    assert RenderSummary.model_validate(json.loads(json.dumps(dumped))) == rs


def test_flyer_create_request_round_trips_with_event_input() -> None:
    fcr = FlyerCreateRequest(
        event=_event(),
        template="editorial_classic",
        preset="photorealistic",
        brand_kit_slug="shrubnet",
        accent="#AABBCC",
        max_bg_attempts=3,
    )
    dumped = fcr.model_dump(mode="json")
    rt = FlyerCreateRequest.model_validate(json.loads(json.dumps(dumped)))
    assert rt.event.title == "T"
    assert rt.accent == "#AABBCC"
    assert rt.max_bg_attempts == 3


def test_brochure_create_request_round_trips_with_brochure_content() -> None:
    content = BrochureContent(
        title="Docs",
        org="Acme",
        sections=[ContentSection(heading="Intro", body_paragraphs=["hello"])],
    )
    bcr = BrochureCreateRequest(content=content, template="trifold", brand_kit_slug="shrubnet")
    dumped = bcr.model_dump(mode="json")
    rt = BrochureCreateRequest.model_validate(json.loads(json.dumps(dumped)))
    assert rt.content.title == "Docs"
    assert rt.content.sections[0].heading == "Intro"


def test_brand_kit_detail_round_trips_with_brand_kit() -> None:
    kit = BrandKit(name="ShrubnetKit", source_url="https://example.com", fetched_at=_now())
    d = BrandKitDetail(slug="shrubnet", record_created_at=_now(), brand_kit=kit)
    dumped = d.model_dump(mode="json")
    rt = BrandKitDetail.model_validate(json.loads(json.dumps(dumped)))
    assert rt.brand_kit.name == "ShrubnetKit"


def test_paginated_brand_kits_round_trips() -> None:
    s = BrandKitSummary(
        slug="shrubnet",
        name="Shrubnet",
        source_url="https://example.com",
        scraped_at=_now(),
    )
    p = PaginatedBrandKits(items=[s], total=1, limit=10, offset=0)
    dumped = p.model_dump(mode="json")
    rt = PaginatedBrandKits.model_validate(json.loads(json.dumps(dumped)))
    assert rt.total == 1
    assert rt.items[0].slug == "shrubnet"


def test_brand_kit_fetch_request_round_trips_any_http_url() -> None:
    f = BrandKitFetchRequest(url="https://example.com/brand", slug="mykit")
    dumped = f.model_dump(mode="json")
    # Pydantic serializes AnyHttpUrl as a str in JSON mode.
    assert isinstance(dumped["url"], str)
    rt = BrandKitFetchRequest.model_validate(json.loads(json.dumps(dumped)))
    assert str(rt.url) == str(f.url)


def test_post_create_request_round_trips() -> None:
    pcr = PostCreateRequest(
        brand_kit_slug="shrubnet",
        platform="linkedin",
        intent="announcement",
        topic="hello",
    )
    rt = PostCreateRequest.model_validate(json.loads(json.dumps(pcr.model_dump(mode="json"))))
    assert rt.platform == "linkedin"
    assert rt.intent == "announcement"


def test_campaign_create_request_round_trips() -> None:
    ccr = CampaignCreateRequest(
        brand_kit_slug="shrubnet",
        platforms=["linkedin", "twitter"],
        intent="announcement",
        topic="hello",
    )
    rt = CampaignCreateRequest.model_validate(json.loads(json.dumps(ccr.model_dump(mode="json"))))
    assert rt.platforms == ["linkedin", "twitter"]


# ---------------------------------------------------------------------------
# Must-have truth #4: consistent slug regex
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "bad_slug",
    ["UPPER", "-leading-dash", "has space", "has_underscore", "has/slash", "", "ümlaut"],
)
def test_flyer_create_request_rejects_bad_slugs(bad_slug: str) -> None:
    with pytest.raises(ValidationError):
        FlyerCreateRequest(event=_event(), preset="p", brand_kit_slug=bad_slug)


@pytest.mark.parametrize(
    "bad_slug",
    ["UPPER", "-leading-dash", "has space", "has_underscore", ""],
)
def test_brochure_create_request_rejects_bad_slugs(bad_slug: str) -> None:
    content = BrochureContent(
        title="x",
        org="o",
        sections=[ContentSection(heading="h", body_paragraphs=["p"])],
    )
    with pytest.raises(ValidationError):
        BrochureCreateRequest(content=content, template="t", brand_kit_slug=bad_slug)


@pytest.mark.parametrize(
    "bad_slug",
    ["UPPER", "-leading-dash", "has space", "has_underscore"],
)
def test_brand_kit_fetch_request_rejects_bad_slugs(bad_slug: str) -> None:
    with pytest.raises(ValidationError):
        BrandKitFetchRequest(url="https://example.com", slug=bad_slug)


@pytest.mark.parametrize(
    "bad_slug",
    ["UPPER", "-leading-dash", "has space", "has_underscore"],
)
def test_post_create_request_rejects_bad_slugs(bad_slug: str) -> None:
    with pytest.raises(ValidationError):
        PostCreateRequest(
            brand_kit_slug=bad_slug,
            platform="linkedin",
            intent="announcement",
            topic="x",
        )


@pytest.mark.parametrize(
    "bad_slug",
    ["UPPER", "-leading-dash", "has space", "has_underscore"],
)
def test_campaign_create_request_rejects_bad_slugs(bad_slug: str) -> None:
    with pytest.raises(ValidationError):
        CampaignCreateRequest(
            brand_kit_slug=bad_slug,
            platforms=["linkedin"],
            intent="announcement",
            topic="x",
        )


@pytest.mark.parametrize(
    "good_slug",
    ["shrubnet", "a", "0", "ab-cd", "kit-2026", "0abc"],
)
def test_valid_slugs_are_accepted(good_slug: str) -> None:
    assert BrandKitFetchRequest(url="https://example.com", slug=good_slug).slug == good_slug


# ---------------------------------------------------------------------------
# Must-have: platform/intent Literal enforcement
# ---------------------------------------------------------------------------


def test_post_create_request_rejects_unknown_platform() -> None:
    with pytest.raises(ValidationError):
        PostCreateRequest(
            brand_kit_slug="a",
            platform="tiktok",  # not in Literal
            intent="announcement",
            topic="x",
        )


def test_post_create_request_rejects_unknown_intent() -> None:
    with pytest.raises(ValidationError):
        PostCreateRequest(
            brand_kit_slug="a",
            platform="linkedin",
            intent="rant",  # not in Literal
            topic="x",
        )


def test_campaign_create_request_rejects_empty_platforms() -> None:
    with pytest.raises(ValidationError):
        CampaignCreateRequest(
            brand_kit_slug="a",
            platforms=[],
            intent="announcement",
            topic="x",
        )


def test_campaign_create_request_caps_platforms_length() -> None:
    with pytest.raises(ValidationError):
        CampaignCreateRequest(
            brand_kit_slug="a",
            platforms=["linkedin"] * 11,  # max_length=10
            intent="announcement",
            topic="x",
        )


# ---------------------------------------------------------------------------
# FlyerCreateRequest accent regex
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("bad_accent", ["notahex", "#ZZZZZZ", "#FFF", "F59E0B", "#F59E0"])
def test_flyer_create_request_rejects_bad_accent(bad_accent: str) -> None:
    with pytest.raises(ValidationError):
        FlyerCreateRequest(event=_event(), preset="p", accent=bad_accent)


@pytest.mark.parametrize("good_accent", ["#F59E0B", "#000000", "#ffffff", "#aAbBcC"])
def test_flyer_create_request_accepts_good_accent(good_accent: str) -> None:
    req = FlyerCreateRequest(event=_event(), preset="p", accent=good_accent)
    assert req.accent == good_accent


# ---------------------------------------------------------------------------
# FlyerCreateRequest.max_bg_attempts bounds
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("bad_n", [0, -1, 11, 100])
def test_flyer_create_request_rejects_out_of_range_max_bg_attempts(bad_n: int) -> None:
    with pytest.raises(ValidationError):
        FlyerCreateRequest(event=_event(), preset="p", max_bg_attempts=bad_n)


# ---------------------------------------------------------------------------
# Phase 22 Plan 04: FlyerCreateRequest.template + FlyerInput event field
# ---------------------------------------------------------------------------


class TestFlyerCreateRequestTemplate:
    """Phase 22: template field + subtype-optional event fields."""

    def _valid_event(self) -> dict:
        return {
            "title": "T",
            "date": "2026-05-01",
            "time": "7pm",
            "location_name": "Hall",
            "location_address": "1 Main",
            "fees": "Free",
            "org": "Acme",
            "style_concept": "c",
            "style_preset": "photorealistic",
        }

    def test_template_required(self):
        with pytest.raises(ValidationError) as ei:
            FlyerCreateRequest.model_validate(
                {
                    "event": self._valid_event(),
                    "preset": "photorealistic",
                }
            )
        assert "template" in str(ei.value)

    def test_template_min_length(self):
        with pytest.raises(ValidationError):
            FlyerCreateRequest.model_validate(
                {
                    "event": self._valid_event(),
                    "template": "",
                    "preset": "photorealistic",
                }
            )

    def test_template_max_length(self):
        with pytest.raises(ValidationError):
            FlyerCreateRequest.model_validate(
                {
                    "event": self._valid_event(),
                    "template": "a" * 65,
                    "preset": "photorealistic",
                }
            )

    def test_template_wrong_type(self):
        with pytest.raises(ValidationError):
            FlyerCreateRequest.model_validate(
                {
                    "event": self._valid_event(),
                    "template": 123,
                    "preset": "photorealistic",
                }
            )

    def test_event_subtype_info_without_event_fields(self):
        req = FlyerCreateRequest.model_validate(
            {
                "event": {
                    "title": "Notice",
                    "subtype": "info",
                    "description": "Road closure",
                    "org": "City",
                    "style_concept": "c",
                    "style_preset": "photorealistic",
                },
                "template": "editorial_classic",
                "preset": "photorealistic",
            }
        )
        assert req.event.subtype == "info"
        assert req.template == "editorial_classic"

    def test_valid_event_with_template_roundtrip(self):
        payload = {
            "event": self._valid_event(),
            "template": "bold_modern",
            "preset": "photorealistic",
        }
        req = FlyerCreateRequest.model_validate(payload)
        dumped = req.model_dump(mode="json")
        assert dumped["template"] == "bold_modern"
        req2 = FlyerCreateRequest.model_validate(dumped)
        assert req2.template == req.template

    def test_extra_fields_forbidden(self):
        with pytest.raises(ValidationError):
            FlyerCreateRequest.model_validate(
                {
                    "event": self._valid_event(),
                    "template": "editorial_classic",
                    "preset": "photorealistic",
                    "foo": "bar",
                }
            )

    def test_template_max_length_64_accepted(self):
        # Exactly 64 chars must be accepted (boundary).
        req = FlyerCreateRequest.model_validate(
            {
                "event": self._valid_event(),
                "template": "a" * 64,
                "preset": "photorealistic",
            }
        )
        assert len(req.template) == 64

    def test_template_min_length_1_accepted(self):
        # Exactly 1 char must be accepted (boundary).
        req = FlyerCreateRequest.model_validate(
            {
                "event": self._valid_event(),
                "template": "z",
                "preset": "photorealistic",
            }
        )
        assert req.template == "z"
