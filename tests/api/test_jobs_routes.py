"""Job polling tests (API-10).

Covers:
- 404 on unknown id
- 422 on bad ULID length
- Queued job: result_ref is None
- Succeeded single-render job: result_ref is a string URL path
- Failed job: error_detail is surfaced unchanged
- Succeeded campaign job: result_ref is a list[ResultLink] fused from
  CampaignRecord.posts -> PostRecord.render
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from flyer_generator.api.models import (
    CampaignRecord,
    JobKind,
    JobRecord,
    JobStatus,
    PostRecord,
    RenderRecord,
)


@pytest.mark.asyncio
async def test_get_job_returns_404_for_unknown_id(client) -> None:
    # 26-char ULID that exists nowhere.
    r = await client.get("/api/v1/jobs/01HABCNOTREAL0000000000000")
    # Id shape is valid (26) but row is missing.
    assert r.status_code == 404
    assert r.json()["detail"] == "job not found"


@pytest.mark.asyncio
async def test_get_job_rejects_bad_id_length(client) -> None:
    r = await client.get("/api/v1/jobs/shortid")
    assert r.status_code == 422  # FastAPI path-param length check


@pytest.mark.asyncio
async def test_get_queued_job_returns_null_result_ref(client, sessionmaker_fx) -> None:
    job_id = "01HABCJOBQUEUED00000000000"  # 26 chars
    async with sessionmaker_fx() as s:
        s.add(
            JobRecord(
                id=job_id,
                kind=JobKind.FLYER,
                status=JobStatus.QUEUED,
                input_payload={},
            )
        )
        await s.commit()

    r = await client.get(f"/api/v1/jobs/{job_id}")
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == job_id
    assert body["status"] == "queued"
    assert body["result_ref"] is None


@pytest.mark.asyncio
async def test_get_succeeded_flyer_job_returns_url_result_ref(
    client, sessionmaker_fx
) -> None:
    render_id = "01HABCRENDER00010000000000"  # 26 chars
    job_id = "01HABCJOBSUCCEED0000000000"  # 26 chars

    async with sessionmaker_fx() as s:
        s.add(
            RenderRecord(
                id=render_id,
                kind="flyer_final",
                # Path not streamed in this test — the fusing is what matters.
                file_path="/tmp/fake.png",
            )
        )
        s.add(
            JobRecord(
                id=job_id,
                kind=JobKind.FLYER,
                status=JobStatus.SUCCEEDED,
                started_at=datetime.now(timezone.utc),
                completed_at=datetime.now(timezone.utc),
                result_ref=render_id,
                input_payload={},
            )
        )
        await s.commit()

    r = await client.get(f"/api/v1/jobs/{job_id}")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "succeeded"
    assert body["result_ref"] == f"/api/v1/renders/{render_id}/image"


@pytest.mark.asyncio
async def test_get_failed_job_surfaces_error_detail(client, sessionmaker_fx) -> None:
    job_id = "01HABCJOBFAILED000000000000"[:26]  # 26 chars
    async with sessionmaker_fx() as s:
        s.add(
            JobRecord(
                id=job_id,
                kind=JobKind.BRAND_KIT,
                status=JobStatus.FAILED,
                error_detail={
                    "type": "BrandKitScrapeError",
                    "message": "ssrf blocked",
                },
                input_payload={},
            )
        )
        await s.commit()

    r = await client.get(f"/api/v1/jobs/{job_id}")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "failed"
    assert body["error_detail"] == {
        "type": "BrandKitScrapeError",
        "message": "ssrf blocked",
    }
    # Succeeded-path fusing MUST NOT run on a failed job — result_ref stays None.
    assert body["result_ref"] is None


@pytest.mark.asyncio
async def test_get_campaign_job_fuses_posts_into_result_links(
    client, sessionmaker_fx
) -> None:
    """Campaign job: result_ref is list[ResultLink] built from posts+renders."""
    # JobRecord.id is reused as CampaignRecord.id (Plan 20-07 contract).
    job_id = "01HABCJOBCAMPAIG0000000000"  # 26 chars
    r1_id = "01HABCRENDERCMP10000000000"  # 26 chars
    r2_id = "01HABCRENDERCMP20000000000"  # 26 chars

    async with sessionmaker_fx() as s:
        s.add(
            RenderRecord(
                id=r1_id,
                kind="social_post_image",
                file_path="/tmp/a.png",
            )
        )
        s.add(
            RenderRecord(
                id=r2_id,
                kind="social_post_image",
                file_path="/tmp/b.png",
            )
        )

        campaign = CampaignRecord(
            id=job_id,
            topic="Launch",
            intent="announcement",
            platforms=["linkedin", "twitter"],
            summary_payload={},
        )
        s.add(campaign)

        s.add(
            PostRecord(
                id="01HABCPOSTLINKED0000000000",
                platform="linkedin",
                intent="announcement",
                topic="Launch",
                campaign_id=job_id,
                post_payload={},
                render_id=r1_id,
            )
        )
        s.add(
            PostRecord(
                id="01HABCPOSTTWEET00000000000",
                platform="twitter",
                intent="announcement",
                topic="Launch",
                campaign_id=job_id,
                post_payload={},
                render_id=r2_id,
            )
        )
        s.add(
            JobRecord(
                id=job_id,
                kind=JobKind.SOCIAL_CAMPAIGN,
                status=JobStatus.SUCCEEDED,
                started_at=datetime.now(timezone.utc),
                completed_at=datetime.now(timezone.utc),
                input_payload={},
            )
        )
        await s.commit()

    r = await client.get(f"/api/v1/jobs/{job_id}")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "succeeded"
    assert isinstance(body["result_ref"], list)
    platforms = {item["platform"] for item in body["result_ref"]}
    assert platforms == {"linkedin", "twitter"}
    urls = {item["url"] for item in body["result_ref"]}
    assert f"/api/v1/renders/{r1_id}/image" in urls
    assert f"/api/v1/renders/{r2_id}/image" in urls


@pytest.mark.asyncio
async def test_get_running_campaign_job_returns_null_result_ref(
    client, sessionmaker_fx
) -> None:
    """Campaign still running: don't fuse — result_ref stays None so clients keep polling."""
    job_id = "01HABCJOBCMPRUNNING0000000"[:26]
    async with sessionmaker_fx() as s:
        s.add(
            JobRecord(
                id=job_id,
                kind=JobKind.SOCIAL_CAMPAIGN,
                status=JobStatus.RUNNING,
                started_at=datetime.now(timezone.utc),
                input_payload={},
            )
        )
        await s.commit()

    r = await client.get(f"/api/v1/jobs/{job_id}")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "running"
    assert body["result_ref"] is None
