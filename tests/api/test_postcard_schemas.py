"""Phase 23-02 Task 1: PostcardCreateRequest + AddressBlock + PostcardDetail schema tests.

Covers PC-01 (request schema), PC-03 (AddressBlock optional payload). Mirrors the
brochure schema test pattern: positive, length, regex, extra-forbid, barrel.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from flyer_generator.api.schemas import (
    AddressBlock,
    PostcardCreateRequest,
    PostcardDetail,
)


# ---------------------------------------------------------------------------
# PostcardCreateRequest
# ---------------------------------------------------------------------------


def test_postcard_create_request_minimal_payload() -> None:
    """Minimal payload — image_hint, brand_kit_slug, address_block all optional."""
    req = PostcardCreateRequest(
        headline="Hi",
        body="Body text",
        template="classic_portrait",
    )
    assert req.headline == "Hi"
    assert req.body == "Body text"
    assert req.template == "classic_portrait"
    assert req.image_hint is None
    assert req.brand_kit_slug is None
    assert req.address_block is None


def test_postcard_create_request_rejects_empty_headline() -> None:
    with pytest.raises(ValidationError):
        PostcardCreateRequest(headline="", body="ok", template="classic_portrait")


def test_postcard_create_request_rejects_empty_or_oversize_template() -> None:
    with pytest.raises(ValidationError):
        PostcardCreateRequest(headline="x", body="y", template="")
    with pytest.raises(ValidationError):
        PostcardCreateRequest(headline="x", body="y", template="x" * 65)


def test_postcard_create_request_rejects_oversize_headline() -> None:
    with pytest.raises(ValidationError):
        PostcardCreateRequest(
            headline="x" * 201,
            body="ok",
            template="classic_portrait",
        )


def test_postcard_create_request_rejects_oversize_body() -> None:
    with pytest.raises(ValidationError):
        PostcardCreateRequest(
            headline="ok",
            body="x" * 2001,
            template="classic_portrait",
        )


def test_postcard_create_request_rejects_invalid_brand_kit_slug() -> None:
    with pytest.raises(ValidationError):
        PostcardCreateRequest(
            headline="ok",
            body="ok",
            template="classic_portrait",
            brand_kit_slug="not_a_valid_slug!",
        )
    # uppercase fails too
    with pytest.raises(ValidationError):
        PostcardCreateRequest(
            headline="ok",
            body="ok",
            template="classic_portrait",
            brand_kit_slug="UpperSlug",
        )


def test_postcard_create_request_accepts_valid_brand_kit_slug() -> None:
    req = PostcardCreateRequest(
        headline="ok",
        body="ok",
        template="classic_portrait",
        brand_kit_slug="acme-co",
    )
    assert req.brand_kit_slug == "acme-co"


def test_postcard_create_request_rejects_unknown_extra_keys() -> None:
    with pytest.raises(ValidationError):
        PostcardCreateRequest(
            headline="ok",
            body="ok",
            template="classic_portrait",
            unknown_field="boom",  # type: ignore[call-arg]
        )


def test_postcard_create_request_accepts_address_block_dict() -> None:
    req = PostcardCreateRequest(
        headline="Hi",
        body="Body",
        template="classic_portrait",
        address_block={
            "recipient_name": "Jane Doe",
            "street": "123 Main St",
            "city_state_zip": "Brooklyn, NY 11201",
        },
    )
    assert req.address_block is not None
    assert req.address_block.recipient_name == "Jane Doe"
    assert req.address_block.street == "123 Main St"
    assert req.address_block.city_state_zip == "Brooklyn, NY 11201"


def test_postcard_create_request_accepts_address_block_none() -> None:
    req = PostcardCreateRequest(
        headline="Hi",
        body="Body",
        template="classic_portrait",
        address_block=None,
    )
    assert req.address_block is None


# ---------------------------------------------------------------------------
# AddressBlock
# ---------------------------------------------------------------------------


def test_address_block_rejects_empty_fields() -> None:
    with pytest.raises(ValidationError):
        AddressBlock(recipient_name="", street="123", city_state_zip="NY")
    with pytest.raises(ValidationError):
        AddressBlock(recipient_name="Jane", street="", city_state_zip="NY")
    with pytest.raises(ValidationError):
        AddressBlock(recipient_name="Jane", street="123", city_state_zip="")


def test_address_block_rejects_oversize_fields() -> None:
    with pytest.raises(ValidationError):
        AddressBlock(recipient_name="x" * 121, street="123", city_state_zip="NY")
    with pytest.raises(ValidationError):
        AddressBlock(recipient_name="Jane", street="x" * 121, city_state_zip="NY")
    with pytest.raises(ValidationError):
        AddressBlock(
            recipient_name="Jane",
            street="123",
            city_state_zip="x" * 121,
        )


def test_address_block_extra_forbid() -> None:
    with pytest.raises(ValidationError):
        AddressBlock(
            recipient_name="Jane",
            street="123",
            city_state_zip="NY",
            extra="boom",  # type: ignore[call-arg]
        )


# ---------------------------------------------------------------------------
# PostcardDetail
# ---------------------------------------------------------------------------


def test_postcard_detail_accepts_render_urls() -> None:
    detail = PostcardDetail(
        id="01H" + "X" * 23,
        template="classic_portrait",
        brand_kit_slug=None,
        front_render_url="/api/v1/renders/abc/image",
        back_render_url="/api/v1/renders/def/image",
        pdf_render_url="/api/v1/renders/ghi/image",
        created_at=datetime.now(timezone.utc),
    )
    assert detail.front_render_url == "/api/v1/renders/abc/image"
    assert detail.back_render_url == "/api/v1/renders/def/image"
    assert detail.pdf_render_url == "/api/v1/renders/ghi/image"


def test_postcard_detail_accepts_none_render_urls() -> None:
    detail = PostcardDetail(
        id="01H" + "X" * 23,
        template="classic_portrait",
        created_at=datetime.now(timezone.utc),
    )
    assert detail.front_render_url is None
    assert detail.back_render_url is None
    assert detail.pdf_render_url is None
    assert detail.brand_kit_slug is None


# ---------------------------------------------------------------------------
# Barrel re-export
# ---------------------------------------------------------------------------


def test_barrel_reexports_postcard_schemas() -> None:
    """`from flyer_generator.api.schemas import ...` must succeed for all 3 names."""
    from flyer_generator.api.schemas import (  # noqa: F401
        AddressBlock as _AB,
        PostcardCreateRequest as _PCR,
        PostcardDetail as _PD,
    )
    assert _AB is AddressBlock
    assert _PCR is PostcardCreateRequest
    assert _PD is PostcardDetail
