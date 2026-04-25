"""Direct-invocation tests for arq tasks (no Redis involved).

Each test hand-rolls a ``ctx`` dict and awaits the real task function with
mocked generators.  Catches import errors, AttributeErrors, and the
BLOCKER-1 (``campaign.posts`` vs ``posts_full``) + BLOCKER-2 (brochure
imports) regressions that route-layer tests would miss.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select

from flyer_generator.api.models import (
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
from flyer_generator.api.tasks._state import mark_failed, mark_running, mark_succeeded


async def _seed_job(sessionmaker, job_id: str, kind: JobKind) -> None:
    async with sessionmaker() as s:
        s.add(
            JobRecord(
                id=job_id,
                kind=kind,
                status=JobStatus.QUEUED,
                input_payload={},
            )
        )
        await s.commit()


# ---------------------------------------------------------------------------
# State-transition helper tests (pure _state.py)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_mark_running_then_succeeded(sessionmaker_fx) -> None:
    jid = "01HTASKTEST0000000000000001"
    await _seed_job(sessionmaker_fx, jid, JobKind.FLYER)
    await mark_running(sessionmaker_fx, jid)
    await mark_succeeded(sessionmaker_fx, jid, result_ref="01HRENDER" + "A" * 17)

    async with sessionmaker_fx() as s:
        row = (
            await s.execute(select(JobRecord).where(JobRecord.id == jid))
        ).scalar_one()
        assert row.status == JobStatus.SUCCEEDED
        assert row.started_at is not None
        assert row.completed_at is not None
        assert row.result_ref == "01HRENDER" + "A" * 17


@pytest.mark.asyncio
async def test_mark_failed_writes_safe_error_detail(sessionmaker_fx) -> None:
    """T-5 mitigation: ``error_detail`` contains ONLY ``{type, message}``.

    ``BrandKitNotFoundError`` is raised with context kwargs (``slug``,
    ``expected_path``) that MUST NOT surface in the JSON column — they may
    contain filesystem paths or other private scraper reasons.
    """
    jid = "01HTASKTEST0000000000000002"
    await _seed_job(sessionmaker_fx, jid, JobKind.FLYER)
    await mark_running(sessionmaker_fx, jid)

    from flyer_generator.errors import BrandKitNotFoundError

    exc = BrandKitNotFoundError(
        "not found", slug="secret-slug", expected_path="/private/path"
    )
    await mark_failed(sessionmaker_fx, jid, exc)

    async with sessionmaker_fx() as s:
        row = (
            await s.execute(select(JobRecord).where(JobRecord.id == jid))
        ).scalar_one()
        assert row.status == JobStatus.FAILED
        assert set(row.error_detail.keys()) == {"type", "message"}
        assert row.error_detail["type"] == "BrandKitNotFoundError"
        # Context bag keys ("slug", "expected_path") MUST NOT appear.
        assert "slug" not in row.error_detail
        assert "expected_path" not in row.error_detail


# ---------------------------------------------------------------------------
# task_fetch_brand_kit — happy + failure
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_task_fetch_brand_kit_writes_record(sessionmaker_fx, tmp_path) -> None:
    from flyer_generator.api.config import AppSettings
    from flyer_generator.api.tasks.brand_kit import task_fetch_brand_kit
    from flyer_generator.brand_kit.models import BrandKit

    fake_kit = BrandKit(
        name="Fake",
        source_url="https://example.com",
        fetched_at=datetime.now(timezone.utc),
    )

    settings = AppSettings()
    settings.brand_kits_dir = tmp_path

    ctx = {
        "sessionmaker": sessionmaker_fx,
        "settings": settings,
        "http_client": None,  # unused by the mock
    }
    jid = "01HTASKFETCH0000000000000001"
    await _seed_job(sessionmaker_fx, jid, JobKind.BRAND_KIT)

    with patch(
        "flyer_generator.api.tasks.brand_kit.fetch_brand_kit",
        new=AsyncMock(return_value=fake_kit),
    ):
        await task_fetch_brand_kit(
            ctx, job_id=jid, payload={"url": "https://example.com", "slug": "fake"}
        )

    async with sessionmaker_fx() as s:
        job = (
            await s.execute(select(JobRecord).where(JobRecord.id == jid))
        ).scalar_one()
        assert job.status == JobStatus.SUCCEEDED
        kit = (
            await s.execute(
                select(BrandKitRecord).where(BrandKitRecord.slug == "fake")
            )
        ).scalar_one()
        assert kit.name == "Fake"
        assert kit.source_url == "https://example.com"


@pytest.mark.asyncio
async def test_task_raises_on_failure_and_marks_failed(sessionmaker_fx, tmp_path) -> None:
    from flyer_generator.api.config import AppSettings
    from flyer_generator.api.tasks.brand_kit import task_fetch_brand_kit
    from flyer_generator.errors import BrandKitScrapeError

    settings = AppSettings()
    settings.brand_kits_dir = tmp_path

    ctx = {"sessionmaker": sessionmaker_fx, "settings": settings, "http_client": None}
    jid = "01HTASKFETCH0000000000000002"
    await _seed_job(sessionmaker_fx, jid, JobKind.BRAND_KIT)

    with patch(
        "flyer_generator.api.tasks.brand_kit.fetch_brand_kit",
        new=AsyncMock(side_effect=BrandKitScrapeError("ssrf blocked")),
    ):
        with pytest.raises(BrandKitScrapeError):
            await task_fetch_brand_kit(
                ctx,
                job_id=jid,
                payload={"url": "http://169.254.169.254/", "slug": "ssrf"},
            )

    async with sessionmaker_fx() as s:
        job = (
            await s.execute(select(JobRecord).where(JobRecord.id == jid))
        ).scalar_one()
        assert job.status == JobStatus.FAILED
        assert job.error_detail["type"] == "BrandKitScrapeError"


# ---------------------------------------------------------------------------
# Direct-invocation smoke tests for the 4 creative tasks (WARNING-6 closure)
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Helpers shared by Phase 22 flyer-task tests
# ---------------------------------------------------------------------------


class _FakeFlyerOut:
    """Mimics FlyerOutput.save(path) by writing PNG magic bytes."""

    comfy_job_id = None
    final_vision_verdict = None

    def save(self, path):
        from pathlib import Path as _P

        _P(path).write_bytes(b"\x89PNG\r\n")


def _flyer_event_payload(template: str = "editorial_classic", **event_overrides) -> dict:
    """Valid event-subtype FlyerInput payload + template + preset."""
    event = {
        "title": "Test Gala",
        "subtype": "event",
        "date": "2026-05-01",
        "time": "7pm",
        "location_name": "Main Hall",
        "location_address": "1 Main St",
        "fees": "Free",
        "org": "Acme",
        "style_concept": "elegant",
        "style_preset": "photorealistic",
    }
    event.update(event_overrides)
    return {
        "event": event,
        "template": template,
        "preset": "photorealistic",
    }


def _flyer_info_payload(template: str = "editorial_classic") -> dict:
    """Valid info-subtype FlyerInput payload + template + preset."""
    return {
        "event": {
            "title": "Notice",
            "subtype": "info",
            "description": "Public road closure notice.",
            "org": "City",
            "style_concept": "civic",
            "style_preset": "photorealistic",
        },
        "template": template,
        "preset": "photorealistic",
    }


@pytest.mark.asyncio
async def test_task_generate_flyer_writes_render_and_flyer(
    sessionmaker_fx, tmp_path
) -> None:
    """Smoke test: happy path produces RenderRecord + FlyerRecord rows."""
    from flyer_generator.api.config import AppSettings
    from flyer_generator.api.tasks.flyer import task_generate_flyer

    settings = AppSettings()
    settings.artifact_root_flyer = tmp_path
    ctx = {"sessionmaker": sessionmaker_fx, "settings": settings, "http_client": None}

    jid = "01HTASKFLYER000000000000001"
    await _seed_job(sessionmaker_fx, jid, JobKind.FLYER)

    class FakeGen:
        def __init__(self, *a, **kw):
            pass

        async def generate(self, event, *, template=None):
            return _FakeFlyerOut()

    payload = _flyer_event_payload(template="editorial_classic")
    with patch(
        "flyer_generator.api.tasks.flyer.FlyerGenerator", FakeGen
    ), patch(
        "flyer_generator.api.tasks.flyer.load_template",
        return_value=object(),
    ):
        render_id = await task_generate_flyer(ctx, job_id=jid, payload=payload)

    assert render_id is not None
    async with sessionmaker_fx() as s:
        job = (
            await s.execute(select(JobRecord).where(JobRecord.id == jid))
        ).scalar_one()
        assert job.status == JobStatus.SUCCEEDED
        assert job.result_ref == render_id
        assert (await s.execute(select(RenderRecord))).scalars().all()
        assert (await s.execute(select(FlyerRecord))).scalars().all()


# ---------------------------------------------------------------------------
# Phase 22 FT-01 + FT-06 — task_generate_flyer template loading + subtype kind
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_flyer_task_loads_template_at_module_scope(
    sessionmaker_fx, tmp_path
) -> None:
    """BLOCKER-2 mirror: load_template must be patchable at the worker module path."""
    from flyer_generator.api.config import AppSettings
    from flyer_generator.api.tasks.flyer import task_generate_flyer

    settings = AppSettings()
    settings.artifact_root_flyer = tmp_path
    ctx = {"sessionmaker": sessionmaker_fx, "settings": settings, "http_client": None}

    jid = "01HTASKFLYERP22A000000000A"
    await _seed_job(sessionmaker_fx, jid, JobKind.FLYER)

    class FakeGen:
        def __init__(self, *a, **kw):
            pass

        async def generate(self, event, *, template=None):
            return _FakeFlyerOut()

    payload = _flyer_event_payload(template="editorial_classic")
    fake_template = object()
    with patch(
        "flyer_generator.api.tasks.flyer.FlyerGenerator", FakeGen
    ), patch(
        "flyer_generator.api.tasks.flyer.load_template",
        return_value=fake_template,
    ) as m_load:
        await task_generate_flyer(ctx, job_id=jid, payload=payload)
        m_load.assert_called_once_with("editorial_classic")


@pytest.mark.asyncio
async def test_flyer_task_bad_template_raises_and_marks_failed(
    sessionmaker_fx, tmp_path
) -> None:
    """A non-existent template name surfaces FileNotFoundError + marks job failed."""
    from flyer_generator.api.config import AppSettings
    from flyer_generator.api.tasks.flyer import task_generate_flyer

    settings = AppSettings()
    settings.artifact_root_flyer = tmp_path
    ctx = {"sessionmaker": sessionmaker_fx, "settings": settings, "http_client": None}

    jid = "01HTASKFLYERP22B000000000B"
    await _seed_job(sessionmaker_fx, jid, JobKind.FLYER)

    payload = _flyer_event_payload(template="nonexistent_template_xyz")
    # No patch on load_template — let the real loader raise FileNotFoundError.
    with pytest.raises(FileNotFoundError):
        await task_generate_flyer(ctx, job_id=jid, payload=payload)

    async with sessionmaker_fx() as s:
        job = (
            await s.execute(select(JobRecord).where(JobRecord.id == jid))
        ).scalar_one()
        assert job.status == JobStatus.FAILED
        assert job.error_detail["type"] == "FileNotFoundError"


@pytest.mark.asyncio
async def test_flyer_task_event_subtype_produces_event_render_kind(
    sessionmaker_fx, tmp_path
) -> None:
    """subtype='event' → RenderRecord.kind == 'flyer_event_final'."""
    from flyer_generator.api.config import AppSettings
    from flyer_generator.api.tasks.flyer import task_generate_flyer

    settings = AppSettings()
    settings.artifact_root_flyer = tmp_path
    ctx = {"sessionmaker": sessionmaker_fx, "settings": settings, "http_client": None}

    jid = "01HTASKFLYERP22C000000000C"
    await _seed_job(sessionmaker_fx, jid, JobKind.FLYER)

    class FakeGen:
        def __init__(self, *a, **kw):
            pass

        async def generate(self, event, *, template=None):
            return _FakeFlyerOut()

    payload = _flyer_event_payload(template="editorial_classic")
    with patch(
        "flyer_generator.api.tasks.flyer.FlyerGenerator", FakeGen
    ), patch(
        "flyer_generator.api.tasks.flyer.load_template",
        return_value=object(),
    ):
        await task_generate_flyer(ctx, job_id=jid, payload=payload)

    async with sessionmaker_fx() as s:
        renders = (await s.execute(select(RenderRecord))).scalars().all()
        assert len(renders) == 1
        assert renders[0].kind == "flyer_event_final"
        flyers = (await s.execute(select(FlyerRecord))).scalars().all()
        assert len(flyers) == 1
        assert flyers[0].template == "editorial_classic"


@pytest.mark.asyncio
async def test_flyer_task_info_subtype_produces_info_render_kind(
    sessionmaker_fx, tmp_path
) -> None:
    """subtype='info' → RenderRecord.kind == 'flyer_info_final'."""
    from flyer_generator.api.config import AppSettings
    from flyer_generator.api.tasks.flyer import task_generate_flyer

    settings = AppSettings()
    settings.artifact_root_flyer = tmp_path
    ctx = {"sessionmaker": sessionmaker_fx, "settings": settings, "http_client": None}

    jid = "01HTASKFLYERP22D000000000D"
    await _seed_job(sessionmaker_fx, jid, JobKind.FLYER)

    class FakeGen:
        def __init__(self, *a, **kw):
            pass

        async def generate(self, event, *, template=None):
            return _FakeFlyerOut()

    payload = _flyer_info_payload(template="editorial_classic")
    with patch(
        "flyer_generator.api.tasks.flyer.FlyerGenerator", FakeGen
    ), patch(
        "flyer_generator.api.tasks.flyer.load_template",
        return_value=object(),
    ):
        await task_generate_flyer(ctx, job_id=jid, payload=payload)

    async with sessionmaker_fx() as s:
        renders = (await s.execute(select(RenderRecord))).scalars().all()
        assert len(renders) == 1
        assert renders[0].kind == "flyer_info_final"


@pytest.mark.asyncio
async def test_flyer_task_missing_subtype_defaults_to_event(
    sessionmaker_fx, tmp_path
) -> None:
    """Back-compat: payloads without explicit subtype default to 'event' → flyer_event_final."""
    from flyer_generator.api.config import AppSettings
    from flyer_generator.api.tasks.flyer import task_generate_flyer

    settings = AppSettings()
    settings.artifact_root_flyer = tmp_path
    ctx = {"sessionmaker": sessionmaker_fx, "settings": settings, "http_client": None}

    jid = "01HTASKFLYERP22E000000000E"
    await _seed_job(sessionmaker_fx, jid, JobKind.FLYER)

    class FakeGen:
        def __init__(self, *a, **kw):
            pass

        async def generate(self, event, *, template=None):
            return _FakeFlyerOut()

    payload = _flyer_event_payload(template="editorial_classic")
    # Drop the subtype key — FlyerInput defaults to "event".
    del payload["event"]["subtype"]
    with patch(
        "flyer_generator.api.tasks.flyer.FlyerGenerator", FakeGen
    ), patch(
        "flyer_generator.api.tasks.flyer.load_template",
        return_value=object(),
    ):
        await task_generate_flyer(ctx, job_id=jid, payload=payload)

    async with sessionmaker_fx() as s:
        renders = (await s.execute(select(RenderRecord))).scalars().all()
        assert renders[0].kind == "flyer_event_final"


@pytest.mark.asyncio
async def test_flyer_task_threads_template_kwarg_to_generator(
    sessionmaker_fx, tmp_path
) -> None:
    """FlyerGenerator.generate must receive the loaded template as template= kwarg."""
    from flyer_generator.api.config import AppSettings
    from flyer_generator.api.tasks.flyer import task_generate_flyer

    settings = AppSettings()
    settings.artifact_root_flyer = tmp_path
    ctx = {"sessionmaker": sessionmaker_fx, "settings": settings, "http_client": None}

    jid = "01HTASKFLYERP22F000000000F"
    await _seed_job(sessionmaker_fx, jid, JobKind.FLYER)

    fake_template = object()
    seen_kwargs: dict = {}

    class CapturingGen:
        def __init__(self, *a, **kw):
            pass

        async def generate(self, event, *, template=None):
            seen_kwargs["template"] = template
            return _FakeFlyerOut()

    payload = _flyer_event_payload(template="bold_modern")
    with patch(
        "flyer_generator.api.tasks.flyer.FlyerGenerator", CapturingGen
    ), patch(
        "flyer_generator.api.tasks.flyer.load_template",
        return_value=fake_template,
    ):
        await task_generate_flyer(ctx, job_id=jid, payload=payload)

    assert seen_kwargs["template"] is fake_template


@pytest.mark.asyncio
async def test_flyer_task_writes_template_column(
    sessionmaker_fx, tmp_path
) -> None:
    """FlyerRecord.template column populated from payload['template']."""
    from flyer_generator.api.config import AppSettings
    from flyer_generator.api.tasks.flyer import task_generate_flyer

    settings = AppSettings()
    settings.artifact_root_flyer = tmp_path
    ctx = {"sessionmaker": sessionmaker_fx, "settings": settings, "http_client": None}

    jid = "01HTASKFLYERP22G00000000GG"
    await _seed_job(sessionmaker_fx, jid, JobKind.FLYER)

    class FakeGen:
        def __init__(self, *a, **kw):
            pass

        async def generate(self, event, *, template=None):
            return _FakeFlyerOut()

    payload = _flyer_event_payload(template="zine")
    with patch(
        "flyer_generator.api.tasks.flyer.FlyerGenerator", FakeGen
    ), patch(
        "flyer_generator.api.tasks.flyer.load_template",
        return_value=object(),
    ):
        await task_generate_flyer(ctx, job_id=jid, payload=payload)

    async with sessionmaker_fx() as s:
        flyers = (await s.execute(select(FlyerRecord))).scalars().all()
        assert len(flyers) == 1
        assert flyers[0].template == "zine"


@pytest.mark.parametrize(
    "bad_name",
    [
        "../etc/passwd",  # path traversal
        "foo.json",  # bypass attempt: makes load_template treat as file path
        "subdir/template",  # forward slash
        "subdir\\template",  # backslash (Windows-style)
    ],
)
@pytest.mark.asyncio
async def test_flyer_task_rejects_path_like_template_names(
    sessionmaker_fx, tmp_path, bad_name
) -> None:
    """T-22-10 mitigation: worker refuses template names that look like paths."""
    from flyer_generator.api.config import AppSettings
    from flyer_generator.api.tasks.flyer import task_generate_flyer

    settings = AppSettings()
    settings.artifact_root_flyer = tmp_path
    ctx = {"sessionmaker": sessionmaker_fx, "settings": settings, "http_client": None}

    jid = "01HTASKFLYERP22H00000" + str(abs(hash(bad_name)))[:6]
    await _seed_job(sessionmaker_fx, jid, JobKind.FLYER)

    payload = _flyer_event_payload(template=bad_name)
    with pytest.raises(ValueError):
        await task_generate_flyer(ctx, job_id=jid, payload=payload)

    async with sessionmaker_fx() as s:
        job = (
            await s.execute(select(JobRecord).where(JobRecord.id == jid))
        ).scalar_one()
        assert job.status == JobStatus.FAILED
        assert job.error_detail["type"] == "ValueError"


@pytest.mark.asyncio
async def test_task_generate_brochure_imports_cleanly_and_writes_records(
    sessionmaker_fx, tmp_path
) -> None:
    """BLOCKER-2 regression guard.

    Verifies the import chain
    ``from flyer_generator.brochure.schema_renderer.loader import load_template``
    and ``from flyer_generator.brochure.stages.pdf import assemble_brochure_pdf``
    survive a worker boot.  A previous draft had the wrong module paths
    (``registry.load_template_schema`` / ``brochure.pdf_assembly``) — if
    anyone regresses those imports, this test raises at patch time.
    """
    from flyer_generator.api.config import AppSettings
    from flyer_generator.api.tasks.brochure import task_generate_brochure

    settings = AppSettings()
    settings.artifact_root_brochure = tmp_path
    ctx = {"sessionmaker": sessionmaker_fx, "settings": settings, "http_client": None}

    jid = "01HTASKBRO00000000000000001"
    await _seed_job(sessionmaker_fx, jid, JobKind.BROCHURE)

    fake_template = object()
    payload = {
        "template": "trifold_modern",
        "content": {
            "title": "Brochure",
            "org": "Org",
            "sections": [
                {"heading": "Intro", "body_paragraphs": ["Hello."], "bullets": []}
            ],
        },
        "generate_images": False,
    }

    with patch(
        "flyer_generator.api.tasks.brochure.BrochureContent.model_validate",
        return_value=type("C", (), {"title": "Brochure"})(),
    ), patch(
        "flyer_generator.api.tasks.brochure.load_template",
        return_value=fake_template,
    ), patch(
        "flyer_generator.api.tasks.brochure.render_schema_brochure",
        return_value=("<svg/>", "<svg/>"),
    ), patch(
        "flyer_generator.api.tasks.brochure.assemble_brochure_pdf",
        return_value=b"%PDF-1.4",
    ), patch(
        "flyer_generator.api.tasks.brochure.Rasterizer"
    ) as RastCls:
        RastCls.return_value.rasterize.return_value = b"\x89PNG\r\n"
        render_id = await task_generate_brochure(ctx, job_id=jid, payload=payload)

    assert render_id is not None
    # Plan 21-07 parallel-id contract: task returns the BrochureRecord.id
    # (which == job_id), NOT the front render id. This lets /jobs/{id}
    # resolve /brochures/{result_ref} directly.
    assert render_id == jid
    async with sessionmaker_fx() as s:
        job = (
            await s.execute(select(JobRecord).where(JobRecord.id == jid))
        ).scalar_one()
        assert job.status == JobStatus.SUCCEEDED
        # Job's result_ref also == brochure.id == job_id (parallel-id pattern).
        assert job.result_ref == jid
        renders = (await s.execute(select(RenderRecord))).scalars().all()
        assert len(renders) == 3
        kinds = {r.kind for r in renders}
        assert kinds == {"brochure_front", "brochure_back", "brochure_pdf"}
        brochures = (await s.execute(select(BrochureRecord))).scalars().all()
        assert len(brochures) == 1
        # BrochureRecord.id == job_id (the parallel-id assignment this plan
        # introduces; prior behavior auto-generated a distinct ULID).
        assert brochures[0].id == jid


@pytest.mark.asyncio
async def test_task_generate_post_writes_post_and_optional_render(
    sessionmaker_fx, tmp_path
) -> None:
    from flyer_generator.api.config import AppSettings
    from flyer_generator.api.tasks.post import task_generate_post

    settings = AppSettings()
    settings.brand_kits_dir = tmp_path
    settings.social_campaigns_dir = tmp_path / "social"
    ctx = {"sessionmaker": sessionmaker_fx, "settings": settings, "http_client": None}

    jid = "01HTASKPOST00000000000000001"
    await _seed_job(sessionmaker_fx, jid, JobKind.SOCIAL_POST)

    class FakePost:
        platform = "linkedin"
        intent = "announcement"
        image_bytes = b"\x89PNG\r\n"
        image_path = None

        def model_dump(self, **kw):
            return {"platform": self.platform, "intent": self.intent}

    fake_kit = object()

    payload = {
        "brand_kit_slug": "acme",
        "topic": "Launch",
        "intent": "announcement",
        "platform": "linkedin",
    }

    with patch(
        "flyer_generator.api.tasks.post.load_brand_kit",
        return_value=fake_kit,
    ), patch(
        "flyer_generator.api.tasks.post.generate_post",
        new=AsyncMock(return_value=FakePost()),
    ):
        render_id = await task_generate_post(ctx, job_id=jid, payload=payload)

    async with sessionmaker_fx() as s:
        job = (
            await s.execute(select(JobRecord).where(JobRecord.id == jid))
        ).scalar_one()
        assert job.status == JobStatus.SUCCEEDED
        assert (await s.execute(select(PostRecord))).scalars().all()
        # image_bytes was present -> render row exists
        assert (await s.execute(select(RenderRecord))).scalars().all()
        assert render_id is not None


@pytest.mark.asyncio
async def test_task_generate_campaign_iterates_posts_full(
    sessionmaker_fx, tmp_path
) -> None:
    """BLOCKER-1 regression guard.

    Catches the AttributeError that used to happen when the task iterated
    ``campaign.posts`` (which yields string keys) and then accessed
    ``post.image_bytes``.  The correct attribute is
    ``campaign.posts_full.values()``.
    """
    from flyer_generator.api.config import AppSettings
    from flyer_generator.api.tasks.campaign import task_generate_campaign
    from flyer_generator.social.models import Campaign

    settings = AppSettings()
    settings.brand_kits_dir = tmp_path
    settings.social_campaigns_dir = tmp_path / "social"
    ctx = {"sessionmaker": sessionmaker_fx, "settings": settings, "http_client": None}

    jid = "01HTASKCAMP00000000000000001"
    await _seed_job(sessionmaker_fx, jid, JobKind.SOCIAL_CAMPAIGN)

    class FakePost:
        def __init__(self, platform):
            self.platform = platform
            self.intent = "announcement"
            self.image_bytes = b"\x89PNG\r\n"
            self.image_path = None

        def model_dump(self, **kw):
            return {"platform": self.platform, "intent": self.intent}

    posts_full = {
        "linkedin__announcement": FakePost("linkedin"),
        "twitter__announcement": FakePost("twitter"),
    }
    posts_serializable = {
        k: {"platform": v.platform, "intent": v.intent} for k, v in posts_full.items()
    }
    # ``Campaign.posts_full`` is typed ``dict[str, Post]`` — our duck-typed
    # ``FakePost`` would fail strict Pydantic validation. ``model_construct``
    # bypasses validation (canonical pattern for injecting test doubles).
    fake_campaign = Campaign.model_construct(
        campaign_id=jid,
        brand_kit_slug="acme",
        topic="Launch",
        platforms=["linkedin", "twitter"],
        created_at=datetime.now(timezone.utc),
        posts=posts_serializable,
        posts_full=posts_full,
    )

    payload = {
        "brand_kit_slug": "acme",
        "platforms": ["linkedin", "twitter"],
        "intent": "announcement",
        "topic": "Launch",
    }

    with patch(
        "flyer_generator.api.tasks.campaign.load_brand_kit",
        return_value=object(),
    ), patch(
        "flyer_generator.api.tasks.campaign.generate_campaign",
        new=AsyncMock(return_value=fake_campaign),
    ):
        # If the task still iterates ``campaign.posts`` this raises
        # AttributeError on ``post.image_bytes`` (post would be a str key).
        result = await task_generate_campaign(ctx, job_id=jid, payload=payload)

    assert result is None  # campaign tasks return None
    async with sessionmaker_fx() as s:
        job = (
            await s.execute(select(JobRecord).where(JobRecord.id == jid))
        ).scalar_one()
        assert job.status == JobStatus.SUCCEEDED
        assert (
            len((await s.execute(select(CampaignRecord))).scalars().all()) == 1
        )
        assert len((await s.execute(select(PostRecord))).scalars().all()) == 2
        assert len((await s.execute(select(RenderRecord))).scalars().all()) == 2


# ---------------------------------------------------------------------------
# Plan 21-12 WR-01 regression: brochure worker must honor user-supplied workflow
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_brochure_task_honors_user_supplied_workflow(sessionmaker_fx) -> None:
    """WR-01 regression: user-supplied ``workflow`` must reach generate_template_images.

    Before the fix, the worker read ``payload["workflow_name"]`` but the
    schema produces ``payload["workflow"]`` via ``body.model_dump(mode="json")``,
    so user overrides were silently dropped and ``turbo_landscape`` was
    always used.
    """
    from flyer_generator.api.config import AppSettings
    from flyer_generator.api.tasks.brochure import task_generate_brochure

    jid = "01HWR01WORKFLOW00000000001"
    await _seed_job(sessionmaker_fx, jid, JobKind.BROCHURE)

    ctx = {
        "sessionmaker": sessionmaker_fx,
        "settings": AppSettings(),
        "http_client": None,  # generate_template_images is patched below
    }

    payload = {
        "content": {
            "title": "Sample",
            "org": "Test Co",
            "sections": [
                {"heading": "Intro", "body_paragraphs": ["Hi."], "bullets": []}
            ],
        },
        "template": "editorial_classic",
        "generate_images": True,
        "workflow": "foo_portrait",  # <-- user override
        "style_preset": "photorealistic",
    }

    # Patch the heavy collaborators the task calls.
    with patch(
        "flyer_generator.api.tasks.brochure.generate_template_images",
        new=AsyncMock(return_value={}),
    ) as gti, patch(
        "flyer_generator.api.tasks.brochure.load_template",
        return_value=object(),
    ), patch(
        "flyer_generator.api.tasks.brochure.render_schema_brochure",
        return_value=("<svg/>", "<svg/>"),
    ), patch(
        "flyer_generator.api.tasks.brochure.Rasterizer"
    ) as rast_cls, patch(
        "flyer_generator.api.tasks.brochure.assemble_brochure_pdf",
        return_value=b"pdf",
    ):
        rast_cls.return_value.rasterize.return_value = b"png"
        await task_generate_brochure(ctx, job_id=jid, payload=payload)

    # Assertion: generate_template_images was called with workflow_name="foo_portrait".
    assert gti.await_count == 1
    kwargs = gti.await_args.kwargs
    assert kwargs["workflow_name"] == "foo_portrait", (
        f"Expected workflow_name=foo_portrait, got {kwargs['workflow_name']!r}. "
        "WR-01: worker is reading the wrong payload key."
    )
