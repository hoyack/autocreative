"""Brand-kit route tests (API-05).

Covers:
    * POST /api/v1/brand-kits/fetch — happy-path + slug/URL rejections +
      T-2 SSRF passthrough (WARNING-5: the real scraper runs, metadata URL
      rejected, JobRecord transitions to FAILED with typed error_detail).
    * GET /api/v1/brand-kits — empty + populated + filesystem fuse + pagination.
    * GET /api/v1/brand-kits/{slug} — DB hit + 404 w/ T-3 context-bag drop +
      path-param slug regex rejection.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from flyer_generator.api.models import BrandKitRecord, JobKind, JobRecord, JobStatus
from flyer_generator.brand_kit.models import (
    BrandKit,
    BrandPalette,
    BrandTypography,
    ColorUsage,
)


def _sample_kit(name: str = "Sample") -> BrandKit:
    """Build a minimal valid ``BrandKit`` for seeding tests."""
    palette = BrandPalette(
        primary=ColorUsage(hex="#112233"),
        secondary=ColorUsage(hex="#445566"),
        accent=ColorUsage(hex="#778899"),
        neutral_dark=ColorUsage(hex="#000000"),
        neutral_light=ColorUsage(hex="#FFFFFF"),
    )
    typography = BrandTypography(heading_family="Sans", body_family="Sans")
    return BrandKit(
        name=name,
        source_url="https://example.com",
        fetched_at=datetime.now(timezone.utc),
        palette=palette,
        typography=typography,
        logos=[],
    )


# ---------- POST /brand-kits/fetch ----------


@pytest.mark.asyncio
async def test_post_fetch_returns_202_and_enqueues_task(
    client, fake_arq_pool, sessionmaker_fx
) -> None:
    r = await client.post(
        "/api/v1/brand-kits/fetch",
        json={"url": "https://example.com", "slug": "example"},
    )
    assert r.status_code == 202, r.text
    body = r.json()
    assert "job_id" in body
    assert len(body["job_id"]) == 26

    # arq received exactly one enqueue.
    assert len(fake_arq_pool.calls) == 1
    func_name, _args, kwargs = fake_arq_pool.calls[0]
    assert func_name == "task_fetch_brand_kit"
    assert kwargs["job_id"] == body["job_id"]
    # Pydantic's AnyHttpUrl normalizes the URL (may add trailing slash).
    assert kwargs["payload"]["slug"] == "example"
    assert kwargs["payload"]["url"].startswith("https://example.com")

    # JobRecord row was committed with status=queued.
    async with sessionmaker_fx() as s:
        job = (
            await s.execute(select(JobRecord).where(JobRecord.id == body["job_id"]))
        ).scalar_one()
        assert job.status == JobStatus.QUEUED
        assert job.kind == JobKind.BRAND_KIT
        assert job.input_payload["slug"] == "example"


@pytest.mark.asyncio
async def test_post_fetch_rejects_bad_slug(client) -> None:
    r = await client.post(
        "/api/v1/brand-kits/fetch",
        json={"url": "https://example.com", "slug": "BAD_UPPER"},
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_post_fetch_rejects_non_http_url(client) -> None:
    r = await client.post(
        "/api/v1/brand-kits/fetch",
        json={"url": "ftp://example.com", "slug": "ok"},
    )
    assert r.status_code == 422


# ---------- GET /brand-kits list ----------


@pytest.mark.asyncio
async def test_get_list_empty(client, app, tmp_path) -> None:
    # Point at an empty tmp dir so the filesystem fuse produces zero entries
    # regardless of whatever exists at the default ``./.brand-kits``.
    app.state.settings.brand_kits_dir = tmp_path
    r = await client.get("/api/v1/brand-kits")
    assert r.status_code == 200
    body = r.json()
    assert body == {"items": [], "total": 0, "limit": 50, "offset": 0}


@pytest.mark.asyncio
async def test_get_list_returns_db_rows(
    client, app, sessionmaker_fx, tmp_path
) -> None:
    # Empty filesystem; DB-only assertion.
    app.state.settings.brand_kits_dir = tmp_path
    kit = _sample_kit("Shrubnet")
    async with sessionmaker_fx() as s:
        s.add(
            BrandKitRecord(
                slug="shrubnet",
                name="Shrubnet",
                source_url="https://shrubnet.example",
                scraped_at=kit.fetched_at,
                payload=kit.model_dump(mode="json"),
            )
        )
        await s.commit()

    r = await client.get("/api/v1/brand-kits")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 1
    assert body["items"][0]["slug"] == "shrubnet"
    assert body["items"][0]["name"] == "Shrubnet"


@pytest.mark.asyncio
async def test_get_list_fuses_filesystem_only_kit(client, app, tmp_path) -> None:
    # Seed a .brand-kits/<slug>/brand.json on disk, not in DB.
    fs_root = tmp_path / "brand_kits"
    kit_dir = fs_root / "fsonly"
    kit_dir.mkdir(parents=True)
    fs_kit = _sample_kit("OnDisk")
    (kit_dir / "brand.json").write_text(fs_kit.model_dump_json())

    # Override settings to point at tmp_path.
    app.state.settings.brand_kits_dir = fs_root

    r = await client.get("/api/v1/brand-kits")
    assert r.status_code == 200
    body = r.json()
    slugs = [it["slug"] for it in body["items"]]
    assert "fsonly" in slugs
    # fsonly kit contributes to total so the caller knows a page beyond
    # DB-only count still has items.
    assert body["total"] >= 1


@pytest.mark.asyncio
async def test_get_list_pagination_query_params(client, app, tmp_path) -> None:
    app.state.settings.brand_kits_dir = tmp_path
    r = await client.get("/api/v1/brand-kits?limit=10&offset=0")
    assert r.status_code == 200
    body = r.json()
    assert body["limit"] == 10
    assert body["offset"] == 0


@pytest.mark.asyncio
async def test_get_list_rejects_bad_limit(client) -> None:
    r = await client.get("/api/v1/brand-kits?limit=0")
    assert r.status_code == 422
    r = await client.get("/api/v1/brand-kits?limit=500")
    assert r.status_code == 422


# ---------- GET /brand-kits/{slug} ----------


@pytest.mark.asyncio
async def test_get_detail_404_on_missing_slug(client, app, tmp_path) -> None:
    # No DB row + empty filesystem -> BrandKitNotFoundError -> 404.
    app.state.settings.brand_kits_dir = tmp_path
    r = await client.get("/api/v1/brand-kits/nothere")
    assert r.status_code == 404
    body = r.json()
    assert body["error_type"] == "BrandKitNotFoundError"
    # T-3: context bag MUST NOT leak into the HTTP response body.
    assert "slug" not in body
    assert "expected_path" not in body
    assert "available" not in body


@pytest.mark.asyncio
async def test_get_detail_returns_db_row(
    client, app, sessionmaker_fx, tmp_path
) -> None:
    app.state.settings.brand_kits_dir = tmp_path
    kit = _sample_kit("Shrubnet")
    async with sessionmaker_fx() as s:
        s.add(
            BrandKitRecord(
                slug="shrubnet",
                name="Shrubnet",
                source_url="https://shrubnet.example",
                scraped_at=kit.fetched_at,
                payload=kit.model_dump(mode="json"),
            )
        )
        await s.commit()

    r = await client.get("/api/v1/brand-kits/shrubnet")
    assert r.status_code == 200
    body = r.json()
    assert body["slug"] == "shrubnet"
    assert body["brand_kit"]["name"] == "Shrubnet"


@pytest.mark.asyncio
async def test_get_detail_falls_back_to_filesystem(client, app, tmp_path) -> None:
    """DB miss -> filesystem read succeeds -> 200 + record_created_at synthesized."""
    fs_root = tmp_path / "kits"
    kit_dir = fs_root / "diskonly"
    kit_dir.mkdir(parents=True)
    fs_kit = _sample_kit("DiskOnly")
    (kit_dir / "brand.json").write_text(fs_kit.model_dump_json())

    app.state.settings.brand_kits_dir = fs_root

    r = await client.get("/api/v1/brand-kits/diskonly")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["slug"] == "diskonly"
    assert body["brand_kit"]["name"] == "DiskOnly"


@pytest.mark.asyncio
async def test_get_detail_rejects_bad_slug_syntax(client) -> None:
    r = await client.get("/api/v1/brand-kits/BAD_SLUG")
    assert r.status_code == 422


# ---------- GET /brand-kits/{slug}/logos/{filename} (Plan 21-05 Task 1) -----
#
# T-1 HIGH — path-traversal guard, mirroring routes/renders.py::_is_within.
# All four tests return 404 on ANY failure (never 403) to avoid leaking
# filesystem shape. SVG is whitelisted (unlike the renders route), since
# brand-kit logos are commonly SVG.


@pytest.mark.asyncio
async def test_get_brand_kit_logo_serves_png(client, app, tmp_path) -> None:
    app.state.settings.brand_kits_dir = tmp_path
    kit_dir = tmp_path / "demo" / "logos"
    kit_dir.mkdir(parents=True)
    png_path = kit_dir / "primary.png"
    png_path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 16)

    r = await client.get("/api/v1/brand-kits/demo/logos/primary.png")
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/png"
    assert "inline" in r.headers.get("content-disposition", "")


@pytest.mark.asyncio
async def test_get_brand_kit_logo_serves_svg(client, app, tmp_path) -> None:
    app.state.settings.brand_kits_dir = tmp_path
    kit_dir = tmp_path / "demo" / "logos"
    kit_dir.mkdir(parents=True)
    svg_path = kit_dir / "primary.svg"
    svg_path.write_text('<svg xmlns="http://www.w3.org/2000/svg"/>')

    r = await client.get("/api/v1/brand-kits/demo/logos/primary.svg")
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/svg+xml"


@pytest.mark.asyncio
async def test_get_brand_kit_logo_404_on_traversal_attempt(
    client, app, tmp_path
) -> None:
    """T-1 HIGH — a path-traversal attempt via URL-encoded ``..`` must 404.

    FastAPI URL-decodes the path param, so ``..%2Fbrand.json`` arrives in the
    handler as ``../brand.json``. Either the extension whitelist rejects it
    (no whitelisted suffix) or the containment guard rejects the resolved
    path — both return 404 (never 403).
    """
    app.state.settings.brand_kits_dir = tmp_path
    (tmp_path / "demo" / "logos").mkdir(parents=True)
    # Seed a sibling file outside .../logos/ that a naive ``../`` would hit.
    (tmp_path / "demo" / "brand.json").write_text("{}")

    r = await client.get("/api/v1/brand-kits/demo/logos/..%2Fbrand.json")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_get_brand_kit_logo_404_on_missing_file(
    client, app, tmp_path
) -> None:
    """Containment passes (path is inside brand_kits_dir) but file is absent.

    Must return 404 — NOT 403, NOT 500.
    """
    app.state.settings.brand_kits_dir = tmp_path
    (tmp_path / "demo" / "logos").mkdir(parents=True)
    r = await client.get("/api/v1/brand-kits/demo/logos/nope.png")
    assert r.status_code == 404


# ---------- T-2 SSRF inheritance (WARNING-5 closure) ----------
#
# Proof that the Phase-18 SSRF gate (flyer_generator/brand_kit/scraper.py) is
# NOT bypassed by the POST /brand-kits/fetch route.  Plan 20-07's
# ``test_task_raises_on_failure_and_marks_failed`` MOCKS ``fetch_brand_kit``
# and therefore never exercises the real SSRF check.  This test enqueues a
# metadata-service URL and then drives the task directly (no mock), asserting
# the job transitions to FAILED with a ``BrandKitScrapeError``.


@pytest.mark.asyncio
async def test_post_fetch_does_not_bypass_ssrf_gate(
    client, app, sessionmaker_fx, tmp_path
) -> None:
    """T-2 defense-in-depth: route enqueues a metadata-service URL as-is; the
    real scraper (NOT mocked) raises ``BrandKitScrapeError``; task persists
    FAILED with a typed ``error_detail`` (only ``{type, message}`` — T-5).
    """
    import httpx

    from flyer_generator.api.config import AppSettings
    from flyer_generator.api.tasks.brand_kit import task_fetch_brand_kit
    from flyer_generator.errors import BrandKitScrapeError

    # Step 1 — POST the SSRF-style URL; route MUST accept it (202) and enqueue.
    metadata_url = "http://169.254.169.254/latest/meta-data/"
    r = await client.post(
        "/api/v1/brand-kits/fetch",
        json={"url": metadata_url, "slug": "ssrf-probe"},
    )
    assert r.status_code == 202, r.text
    job_id = r.json()["job_id"]

    # Step 2 — drive the task directly (no real Redis / worker) with the same
    # payload the route just enqueued.  Use a REAL (non-mocked) httpx client
    # so the scraper's SSRF gate runs for real and raises BrandKitScrapeError
    # BEFORE any network I/O is attempted.
    settings = AppSettings()
    settings.brand_kits_dir = tmp_path
    async with httpx.AsyncClient(timeout=5.0) as http_client:
        ctx = {
            "sessionmaker": sessionmaker_fx,
            "settings": settings,
            "http_client": http_client,
        }
        # The route normalized the URL into the JobRecord; reuse the exact
        # payload the route enqueued (fetched from arq fake pool).
        with pytest.raises(BrandKitScrapeError):
            await task_fetch_brand_kit(
                ctx,
                job_id=job_id,
                payload={"url": metadata_url, "slug": "ssrf-probe"},
            )

    # Step 3 — JobRecord reflects FAILED + error_detail["type"] ==
    # "BrandKitScrapeError".  The SSRF gate's context kwargs (``url``,
    # ``reason``, ``trace_id``) MUST NOT leak into error_detail (T-5 mitigated
    # by ``_state.mark_failed``).
    async with sessionmaker_fx() as s:
        job = (
            await s.execute(select(JobRecord).where(JobRecord.id == job_id))
        ).scalar_one()
        assert job.status == JobStatus.FAILED
        assert job.error_detail["type"] == "BrandKitScrapeError"
        assert set(job.error_detail.keys()) == {"type", "message"}


# ---------- WR-02 regression (Plan 21-13 Task 1) -----------------------------
#
# list_brand_kits must dedup the filesystem fuse against the FULL set of DB
# slugs, not just the current page's slice. Also `total` must be page-invariant.


@pytest.mark.asyncio
async def test_list_brand_kits_pagination_no_duplicates_across_pages(
    client, app, sessionmaker_fx, tmp_path
) -> None:
    """WR-02 regression: the filesystem fuse must dedup against the FULL
    set of DB slugs, not just the current page's slice.

    Setup: 3 DB rows (staggered scraped_at so ordering is deterministic) +
    1 FS-only kit. With limit=2:
      - page 1 must see EXACTLY 2 items, total=4
      - page 2 must see EXACTLY 2 items, total=4
      - union of all slugs across both pages must have 4 unique values
      - fs-only slug appears EXACTLY ONCE across all pages

    Under the buggy implementation, `db_slugs = {r.slug for r in rows}` is built
    only from the current page's rows. On page 1 the FS-only slug (sorted
    alphabetically after "db-*" via `sorted(base_dir.iterdir())`) may or may
    not appear; more importantly, if a DB slug appears on a different page it
    gets treated as FS-only on the current page, duplicating rows across pages
    AND inflating `total`. This test pins the page-invariant behavior.
    """
    from flyer_generator.api.models import BrandKitRecord

    # --- Seed 3 DB rows with staggered scraped_at so ordering is stable.
    base_time = datetime(2026, 4, 23, 12, 0, 0, tzinfo=timezone.utc)
    async with sessionmaker_fx() as s:
        for i, slug in enumerate(["db-one", "db-two", "db-three"]):
            kit = _sample_kit(name=slug)
            s.add(
                BrandKitRecord(
                    slug=slug,
                    name=kit.name,
                    source_url=kit.source_url,
                    scraped_at=base_time - timedelta(minutes=i),
                    payload=kit.model_dump(mode="json"),
                )
            )
        await s.commit()

    # --- Seed 1 FS-only kit on disk at tmp_path.
    fs_kit_dir = tmp_path / "fs-only"
    fs_kit_dir.mkdir(parents=True)
    fs_kit = _sample_kit(name="fs-only")
    (fs_kit_dir / "brand.json").write_text(fs_kit.model_dump_json())

    # --- Override brand_kits_dir on the already-built app (idiomatic per
    #     existing test patterns in this module — see test_get_list_empty).
    app.state.settings.brand_kits_dir = tmp_path

    # Page 1
    r1 = await client.get("/api/v1/brand-kits?limit=2&offset=0")
    assert r1.status_code == 200, r1.text
    p1 = r1.json()

    # Page 2
    r2 = await client.get("/api/v1/brand-kits?limit=2&offset=2")
    assert r2.status_code == 200, r2.text
    p2 = r2.json()

    # Assertion 1: totals are stable and correct.
    assert p1["total"] == 4, f"Page 1 total={p1['total']} (want 4). WR-02 bug."
    assert p2["total"] == 4, f"Page 2 total={p2['total']} (want 4). WR-02 bug."

    # Assertion 2: no duplicate slugs across pages.
    slugs_p1 = {it["slug"] for it in p1["items"]}
    slugs_p2 = {it["slug"] for it in p2["items"]}
    union = slugs_p1 | slugs_p2
    assert len(union) == 4, (
        f"Expected 4 unique slugs across pages, got {len(union)} from "
        f"{sorted(union)}. WR-02: fs-only slug duplicated across pages."
    )

    # Assertion 3: the FS-only slug appears EXACTLY ONCE across all pages.
    flat_slugs = [it["slug"] for it in p1["items"]] + [
        it["slug"] for it in p2["items"]
    ]
    assert flat_slugs.count("fs-only") == 1, (
        f"fs-only appeared {flat_slugs.count('fs-only')} times (want 1). "
        f"Flat: {flat_slugs}. WR-02 bug."
    )
