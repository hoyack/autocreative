"""Per checker B1: direct-module imports only."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from flyer_generator.errors import SocialError
from flyer_generator.social.models import (
    Campaign,
    Post,
    PostCopy,
    ValidationReport,
)
from flyer_generator.social.storage import (
    list_campaigns,
    load_post,
    resolve_campaign_dir,
    save_campaign,
    save_post,
)


def test_resolve_campaign_dir_valid(tmp_path: Path) -> None:
    out = resolve_campaign_dir(
        "my-brand",
        "01HXYZABC123DEF456GHIJKLMN",
        base_dir=tmp_path,
    )
    assert out == tmp_path / "my-brand" / "01HXYZABC123DEF456GHIJKLMN"


def test_resolve_campaign_dir_rejects_bad_slug(tmp_path: Path) -> None:
    with pytest.raises(SocialError):
        resolve_campaign_dir("../evil", "01HXYZABC123DEF456GHIJKLMN", base_dir=tmp_path)


def test_resolve_campaign_dir_rejects_bad_campaign_id(tmp_path: Path) -> None:
    with pytest.raises(SocialError):
        resolve_campaign_dir("ok", "../evil", base_dir=tmp_path)


def test_save_and_load_post_roundtrip(tmp_path: Path) -> None:
    post = Post(
        platform="linkedin",
        intent="value-prop",
        copy=PostCopy(title="T", body="B", cta="C", hashtags=["#x"]),
        image_bytes=b"\x89PNG\r\n\x1a\n" + b"\x00" * 32,
        validation_report=ValidationReport(platform="linkedin"),
        audit_summary="clean",
    )
    post_dir = save_post(
        post,
        slug="my-brand",
        campaign_id="01HXYZABC123DEF456GHIJKLMN",
        template_name="linkedin__value-prop",
        base_dir=tmp_path,
    )
    assert (post_dir / "post.json").exists()
    assert (post_dir / "image.png").exists()

    loaded = load_post(
        "my-brand",
        "01HXYZABC123DEF456GHIJKLMN",
        "linkedin__value-prop",
        base_dir=tmp_path,
    )
    assert loaded.copy.title == "T"
    assert loaded.image_bytes == post.image_bytes


def test_save_campaign_writes_campaign_json(tmp_path: Path) -> None:
    c = Campaign(
        campaign_id="01HXYZABC123DEF456GHIJKLMN",
        brand_kit_slug="my-brand",
        topic="t",
        platforms=["linkedin"],
        created_at=datetime(2026, 4, 21, tzinfo=timezone.utc),
        posts={},
    )
    out = save_campaign(c, base_dir=tmp_path)
    assert (out / "campaign.json").exists()


def test_list_campaigns_empty(tmp_path: Path) -> None:
    assert list_campaigns("my-brand", base_dir=tmp_path) == []


def test_list_campaigns_sorted(tmp_path: Path) -> None:
    for cid in ["01HXYZABC123DEF456GHIJKLMN", "01HXZZABC123DEF456GHIJKLMN"]:
        c = Campaign(
            campaign_id=cid,
            brand_kit_slug="my-brand",
            topic="",
            platforms=[],
            created_at=datetime(2026, 4, 21, tzinfo=timezone.utc),
            posts={},
        )
        save_campaign(c, base_dir=tmp_path)
    result = list_campaigns("my-brand", base_dir=tmp_path)
    assert result == sorted(result)
