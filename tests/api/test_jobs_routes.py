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

from datetime import datetime, timedelta, timezone

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


# --- GET /api/v1/jobs (list, Plan 21-10 Task 1) -----------------------------
# Tests mirror the brand-kits list tests: empty state, sort order, filters,
# and enum validation. Uses sessionmaker_fx (the fixture that actually exists
# in conftest.py — the plan text suggested `db_session` but no such fixture
# is wired). Terminal jobs / queued jobs / campaign rows all go through the
# same cheap path in the list route (campaigns get result_ref=None per Open
# Question Q1; validated by test_list_jobs_campaign_row_has_null_result_ref).


@pytest.mark.asyncio
async def test_list_jobs_returns_paginated_response_when_empty(client) -> None:
    resp = await client.get("/api/v1/jobs")
    assert resp.status_code == 200
    body = resp.json()
    assert body["items"] == []
    assert body["total"] == 0
    assert body["limit"] == 50
    assert body["offset"] == 0


@pytest.mark.asyncio
async def test_list_jobs_returns_rows_newest_first(client, sessionmaker_fx) -> None:
    now = datetime.now(timezone.utc)
    async with sessionmaker_fx() as s:
        s.add(
            JobRecord(
                id="01OLD" + "A" * 21,  # 26 chars
                kind=JobKind.FLYER,
                status=JobStatus.SUCCEEDED,
                input_payload={},
                created_at=now - timedelta(hours=2),
            )
        )
        s.add(
            JobRecord(
                id="01NEW" + "A" * 21,  # 26 chars
                kind=JobKind.FLYER,
                status=JobStatus.SUCCEEDED,
                input_payload={},
                created_at=now,
            )
        )
        await s.commit()

    resp = await client.get("/api/v1/jobs")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2
    # Newest first.
    assert body["items"][0]["id"].startswith("01NEW")
    assert body["items"][1]["id"].startswith("01OLD")


@pytest.mark.asyncio
async def test_list_jobs_filters_by_kind(client, sessionmaker_fx) -> None:
    async with sessionmaker_fx() as s:
        s.add(
            JobRecord(
                id="01FLYER" + "A" * 19,  # 26 chars
                kind=JobKind.FLYER,
                status=JobStatus.QUEUED,
                input_payload={},
            )
        )
        s.add(
            JobRecord(
                id="01BROC" + "A" * 20,  # 26 chars
                kind=JobKind.BROCHURE,
                status=JobStatus.QUEUED,
                input_payload={},
            )
        )
        await s.commit()

    resp = await client.get("/api/v1/jobs?kind=flyer")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["kind"] == "flyer"


@pytest.mark.asyncio
async def test_list_jobs_filters_by_status(client, sessionmaker_fx) -> None:
    async with sessionmaker_fx() as s:
        s.add(
            JobRecord(
                id="01QUEUE" + "A" * 19,
                kind=JobKind.FLYER,
                status=JobStatus.QUEUED,
                input_payload={},
            )
        )
        s.add(
            JobRecord(
                id="01DONE0" + "A" * 19,
                kind=JobKind.FLYER,
                status=JobStatus.SUCCEEDED,
                input_payload={},
            )
        )
        await s.commit()

    resp = await client.get("/api/v1/jobs?status=succeeded")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["status"] == "succeeded"


@pytest.mark.asyncio
async def test_list_jobs_invalid_kind_is_422(client) -> None:
    resp = await client.get("/api/v1/jobs?kind=not_a_real_kind")
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_list_jobs_campaign_row_has_null_result_ref(
    client, sessionmaker_fx
) -> None:
    """Cheap path: campaigns get result_ref=None in the list view even though
    their single-job-detail endpoint would fuse the ResultLink list."""
    job_id = "01CAMP0" + "A" * 19  # 26 chars
    render_id = "01RNDRLIST" + "A" * 16  # 26 chars

    async with sessionmaker_fx() as s:
        # A succeeded single-render flyer job — result_ref should be a URL string.
        s.add(
            RenderRecord(
                id=render_id,
                kind="flyer_final",
                file_path="/tmp/fake.png",
            )
        )
        s.add(
            JobRecord(
                id="01FLY1S" + "A" * 19,
                kind=JobKind.FLYER,
                status=JobStatus.SUCCEEDED,
                result_ref=render_id,
                input_payload={},
            )
        )
        # A succeeded campaign job — even though the detail route would fuse
        # a list[ResultLink], the list route must return result_ref=None.
        s.add(
            JobRecord(
                id=job_id,
                kind=JobKind.SOCIAL_CAMPAIGN,
                status=JobStatus.SUCCEEDED,
                input_payload={},
            )
        )
        await s.commit()

    resp = await client.get("/api/v1/jobs")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2
    by_id = {row["id"]: row for row in body["items"]}
    assert by_id[job_id]["result_ref"] is None  # cheap-path campaign
    assert (
        by_id["01FLY1S" + "A" * 19]["result_ref"]
        == f"/api/v1/renders/{render_id}/image"
    )
