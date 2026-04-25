"""Direct-invocation tests for ``task_generate_poster`` (Phase 24-04 PO-01/PO-02/PO-04).

Mirrors the postcard worker test pattern in ``tests/api/test_worker_postcard_tasks.py``:
hand-rolls a ``ctx`` dict, patches the heavy collaborators (``load_template`` /
``FlyerGenerator``), seeds a JobRecord, and awaits the real task function.

Verifies:
- BLOCKER-2 module-scope import contract (patch points are
  ``flyer_generator.api.tasks.poster.X``)
- T-24-08 path-traversal guard (``_validate_template_slug`` rejects ``.json`` /
  ``/`` / ``\\``)
- ``_size_to_canvas_dimensions`` mapping for the 3 locked sizes (defense-in-
  depth past the Pydantic Literal)
- Parallel-id pattern (``PosterRecord.id == job_id``)
- Single ``RenderRecord(kind="poster_final")`` emission
- ``FlyerGenerator(canvas_dimensions=size_to_dim(size))`` threading
- Compensating rollback on render failure (no orphaned RenderRecord/PosterRecord)
- ALL_TASKS registration
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import select

from flyer_generator.api.models import (
    JobKind,
    JobRecord,
    JobStatus,
    PosterRecord,
    RenderRecord,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _payload(
    template: str = "editorial_grand",
    size: str = "18x24",
    *,
    headline: str = "Hello Poster",
    subheading: str | None = "Subheading copy",
    cta_text: str | None = "RSVP today",
    image_hint: str | None = "soft pastels at sunset",
    style_preset: str = "editorial_modernist",
    brand_kit_slug: str | None = None,
) -> dict:
    return {
        "headline": headline,
        "subheading": subheading,
        "cta_text": cta_text,
        "image_hint": image_hint,
        "brand_kit_slug": brand_kit_slug,
        "style_preset": style_preset,
        "template": template,
        "size": size,
    }


async def _seed_job(sessionmaker, job_id: str, payload: dict | None = None) -> None:
    async with sessionmaker() as s:
        s.add(
            JobRecord(
                id=job_id,
                kind=JobKind.POSTER,
                status=JobStatus.QUEUED,
                input_payload=payload or {},
            )
        )
        await s.commit()


def _make_fake_flyer_output(png_bytes: bytes = b"\x89PNG\r\n\x1a\n_FAKE_") -> MagicMock:
    """Build a MagicMock that quacks like a FlyerOutput for the worker.

    Worker accesses:
      - ``.save(path)`` — writes ``png_bytes`` to disk
      - ``.comfy_job_id`` (via ``getattr(..., None)``)
      - ``.final_vision_verdict`` (via ``getattr(..., None)``;
        when not None, ``.model_dump(mode="json")`` is called)
    """
    out = MagicMock()
    out.comfy_job_id = "fake-comfy-job-123"
    out.final_vision_verdict = None  # worker tolerates None via getattr-default

    def _save(path):
        from pathlib import Path

        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(png_bytes)

    out.save.side_effect = _save
    return out


def _build_ctx(sessionmaker, tmp_path):
    from flyer_generator.api.config import AppSettings

    settings = AppSettings()
    settings.artifact_root_flyer = tmp_path
    return {"sessionmaker": sessionmaker, "settings": settings, "http_client": None}


# ---------------------------------------------------------------------------
# Test 1 — module imports cleanly + module-scope collaborators are patchable
# ---------------------------------------------------------------------------


def test_task_generate_poster_importable() -> None:
    """The task function imports successfully — no missing-module errors."""
    from flyer_generator.api.tasks.poster import task_generate_poster

    assert callable(task_generate_poster)


def test_module_scope_load_template_importable() -> None:
    """BLOCKER-2: ``load_template`` is at module scope so tests can patch it."""
    import flyer_generator.api.tasks.poster as p

    assert hasattr(p, "load_template")
    assert callable(p.load_template)


def test_module_scope_FlyerGenerator_importable() -> None:
    """BLOCKER-2: ``FlyerGenerator`` is at module scope so tests can patch it."""
    import flyer_generator.api.tasks.poster as p

    assert hasattr(p, "FlyerGenerator")


# ---------------------------------------------------------------------------
# Test 2 — _size_to_canvas_dimensions
# ---------------------------------------------------------------------------


def test_size_to_canvas_dimensions_18x24() -> None:
    from flyer_generator.api.tasks.poster import _size_to_canvas_dimensions

    assert _size_to_canvas_dimensions("18x24") == (5400, 7200)


def test_size_to_canvas_dimensions_24x36() -> None:
    from flyer_generator.api.tasks.poster import _size_to_canvas_dimensions

    assert _size_to_canvas_dimensions("24x36") == (7200, 10800)


def test_size_to_canvas_dimensions_27x40() -> None:
    from flyer_generator.api.tasks.poster import _size_to_canvas_dimensions

    assert _size_to_canvas_dimensions("27x40") == (8100, 12000)


def test_size_to_canvas_dimensions_unknown_raises_ValueError() -> None:
    from flyer_generator.api.tasks.poster import _size_to_canvas_dimensions

    with pytest.raises(ValueError, match="unknown poster size"):
        _size_to_canvas_dimensions("36x48")


# ---------------------------------------------------------------------------
# Test 3 — _validate_template_slug (T-24-08 mitigation)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "bad_name",
    [
        "../etc/passwd",
        "foo.json",
        "sub/template",
        "sub\\template",
    ],
)
def test_validate_template_slug_rejects_path_like(bad_name: str) -> None:
    """T-24-08: refuses ``.json`` suffix, ``/``, ``\\``."""
    from flyer_generator.api.tasks.poster import _validate_template_slug

    with pytest.raises(ValueError, match="bare slug"):
        _validate_template_slug(bad_name)


def test_validate_template_slug_accepts_bare_slug() -> None:
    from flyer_generator.api.tasks.poster import _validate_template_slug

    # Should not raise.
    _validate_template_slug("editorial_grand")
    _validate_template_slug("bold_announcement")
    _validate_template_slug("cinematic_onesheet")


# ---------------------------------------------------------------------------
# Test 4 — happy-path: 1 RenderRecord(poster_final) + 1 PosterRecord + JobRecord SUCCEEDED
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_task_writes_render_and_poster_18x24(
    sessionmaker_fx, tmp_path
) -> None:
    from flyer_generator.api.tasks.poster import task_generate_poster

    jid = "01HPOSTER0000000000000018X24"[:26]
    payload = _payload(template="editorial_grand", size="18x24")
    await _seed_job(sessionmaker_fx, jid, payload)
    ctx = _build_ctx(sessionmaker_fx, tmp_path)

    fake_out = _make_fake_flyer_output()
    fake_template = MagicMock()

    with patch(
        "flyer_generator.api.tasks.poster.load_template",
        return_value=fake_template,
    ), patch(
        "flyer_generator.api.tasks.poster.FlyerGenerator"
    ) as GenCls:
        GenCls.return_value.generate = AsyncMock(return_value=fake_out)
        result_ref = await task_generate_poster(ctx, job_id=jid, payload=payload)

    async with sessionmaker_fx() as s:
        job = (
            await s.execute(select(JobRecord).where(JobRecord.id == jid))
        ).scalar_one()
        assert job.status == JobStatus.SUCCEEDED

        renders = (await s.execute(select(RenderRecord))).scalars().all()
        assert len(renders) == 1
        assert renders[0].kind == "poster_final"
        # JobRecord.result_ref is the render id (returned from the worker).
        assert job.result_ref == renders[0].id
        # The worker's own return value is the render id, too.
        assert result_ref == renders[0].id

        posters = (await s.execute(select(PosterRecord))).scalars().all()
        assert len(posters) == 1
        poster = posters[0]
        # Parallel-id contract: PosterRecord.id == job_id.
        assert poster.id == jid
        assert poster.template == "editorial_grand"
        assert poster.size == "18x24"
        assert poster.render_id == renders[0].id


@pytest.mark.asyncio
async def test_task_writes_render_and_poster_24x36(
    sessionmaker_fx, tmp_path
) -> None:
    from flyer_generator.api.tasks.poster import task_generate_poster

    jid = "01HPOSTER0000000000000024X36"[:26]
    payload = _payload(template="bold_announcement", size="24x36")
    await _seed_job(sessionmaker_fx, jid, payload)
    ctx = _build_ctx(sessionmaker_fx, tmp_path)

    fake_out = _make_fake_flyer_output()
    fake_template = MagicMock()

    with patch(
        "flyer_generator.api.tasks.poster.load_template",
        return_value=fake_template,
    ), patch(
        "flyer_generator.api.tasks.poster.FlyerGenerator"
    ) as GenCls:
        GenCls.return_value.generate = AsyncMock(return_value=fake_out)
        await task_generate_poster(ctx, job_id=jid, payload=payload)

    async with sessionmaker_fx() as s:
        poster = (await s.execute(select(PosterRecord))).scalar_one()
        assert poster.size == "24x36"
        assert poster.template == "bold_announcement"


@pytest.mark.asyncio
async def test_task_writes_render_and_poster_27x40(
    sessionmaker_fx, tmp_path
) -> None:
    from flyer_generator.api.tasks.poster import task_generate_poster

    jid = "01HPOSTER0000000000000027X40"[:26]
    payload = _payload(template="cinematic_onesheet", size="27x40")
    await _seed_job(sessionmaker_fx, jid, payload)
    ctx = _build_ctx(sessionmaker_fx, tmp_path)

    fake_out = _make_fake_flyer_output()
    fake_template = MagicMock()

    with patch(
        "flyer_generator.api.tasks.poster.load_template",
        return_value=fake_template,
    ), patch(
        "flyer_generator.api.tasks.poster.FlyerGenerator"
    ) as GenCls:
        GenCls.return_value.generate = AsyncMock(return_value=fake_out)
        await task_generate_poster(ctx, job_id=jid, payload=payload)

    async with sessionmaker_fx() as s:
        poster = (await s.execute(select(PosterRecord))).scalar_one()
        assert poster.size == "27x40"
        assert poster.template == "cinematic_onesheet"


# ---------------------------------------------------------------------------
# Test 5 — canvas_dimensions threads through to FlyerGenerator constructor
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "size,expected_dims",
    [
        ("18x24", (5400, 7200)),
        ("24x36", (7200, 10800)),
        ("27x40", (8100, 12000)),
    ],
)
async def test_task_threads_canvas_dimensions_to_FlyerGenerator(
    sessionmaker_fx, tmp_path, size, expected_dims
) -> None:
    from flyer_generator.api.tasks.poster import task_generate_poster

    jid = ("01HPOSTERTHREADCANVAS" + size.replace("x", "X"))[:26]
    payload = _payload(template="editorial_grand", size=size)
    await _seed_job(sessionmaker_fx, jid, payload)
    ctx = _build_ctx(sessionmaker_fx, tmp_path)

    fake_out = _make_fake_flyer_output()
    fake_template = MagicMock()

    with patch(
        "flyer_generator.api.tasks.poster.load_template",
        return_value=fake_template,
    ), patch(
        "flyer_generator.api.tasks.poster.FlyerGenerator"
    ) as GenCls:
        GenCls.return_value.generate = AsyncMock(return_value=fake_out)
        await task_generate_poster(ctx, job_id=jid, payload=payload)

    # FlyerGenerator should have been constructed exactly once with
    # canvas_dimensions == expected_dims.
    assert GenCls.call_count == 1
    _, kwargs = GenCls.call_args
    assert kwargs.get("canvas_dimensions") == expected_dims


# ---------------------------------------------------------------------------
# Test 6 — load_template called once with payload['template']
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_task_loads_template_at_module_scope(
    sessionmaker_fx, tmp_path
) -> None:
    from flyer_generator.api.tasks.poster import task_generate_poster

    jid = "01HPOSTER0000LOADTEMPLATE000"[:26]
    payload = _payload(template="bold_announcement", size="18x24")
    await _seed_job(sessionmaker_fx, jid, payload)
    ctx = _build_ctx(sessionmaker_fx, tmp_path)

    fake_out = _make_fake_flyer_output()
    fake_template = MagicMock()

    with patch(
        "flyer_generator.api.tasks.poster.load_template",
        return_value=fake_template,
    ) as load_mock, patch(
        "flyer_generator.api.tasks.poster.FlyerGenerator"
    ) as GenCls:
        GenCls.return_value.generate = AsyncMock(return_value=fake_out)
        await task_generate_poster(ctx, job_id=jid, payload=payload)

    load_mock.assert_called_once_with("bold_announcement")


# ---------------------------------------------------------------------------
# Test 7 — bad template (path-like) marks JobRecord FAILED, no commits
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_task_bad_template_path_traversal_marks_failed(
    sessionmaker_fx, tmp_path
) -> None:
    from flyer_generator.api.tasks.poster import task_generate_poster

    jid = "01HPOSTER000PATHTRAVERSAL00"[:26]
    payload = _payload(template="../etc/passwd", size="18x24")
    await _seed_job(sessionmaker_fx, jid, payload)
    ctx = _build_ctx(sessionmaker_fx, tmp_path)

    with pytest.raises(ValueError):
        await task_generate_poster(ctx, job_id=jid, payload=payload)

    async with sessionmaker_fx() as s:
        job = (
            await s.execute(select(JobRecord).where(JobRecord.id == jid))
        ).scalar_one()
        assert job.status == JobStatus.FAILED
        assert job.error_detail["type"] == "ValueError"
        # No artifacts committed.
        assert (await s.execute(select(RenderRecord))).scalars().all() == []
        assert (await s.execute(select(PosterRecord))).scalars().all() == []


# ---------------------------------------------------------------------------
# Test 8 — load_template raises FileNotFoundError -> JobRecord FAILED
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_task_bad_template_filenotfound_marks_failed(
    sessionmaker_fx, tmp_path
) -> None:
    from flyer_generator.api.tasks.poster import task_generate_poster

    jid = "01HPOSTER000NOTFOUNDTEMPLATE"[:26]
    payload = _payload(template="nonexistent_template_xyz", size="18x24")
    await _seed_job(sessionmaker_fx, jid, payload)
    ctx = _build_ctx(sessionmaker_fx, tmp_path)

    with patch(
        "flyer_generator.api.tasks.poster.load_template",
        side_effect=FileNotFoundError("not found"),
    ):
        with pytest.raises(FileNotFoundError):
            await task_generate_poster(ctx, job_id=jid, payload=payload)

    async with sessionmaker_fx() as s:
        job = (
            await s.execute(select(JobRecord).where(JobRecord.id == jid))
        ).scalar_one()
        assert job.status == JobStatus.FAILED
        assert job.error_detail["type"] == "FileNotFoundError"


# ---------------------------------------------------------------------------
# Test 9 — bogus size raises ValueError -> JobRecord FAILED
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_task_bogus_size_raises_and_marks_failed(
    sessionmaker_fx, tmp_path
) -> None:
    """Defense-in-depth past the Pydantic Literal: worker rejects unknown size."""
    from flyer_generator.api.tasks.poster import task_generate_poster

    jid = "01HPOSTER000BOGUSSIZETESTYY"[:26]
    payload = _payload(template="editorial_grand", size="36x48")
    await _seed_job(sessionmaker_fx, jid, payload)
    ctx = _build_ctx(sessionmaker_fx, tmp_path)

    with pytest.raises(ValueError, match="unknown poster size"):
        await task_generate_poster(ctx, job_id=jid, payload=payload)

    async with sessionmaker_fx() as s:
        job = (
            await s.execute(select(JobRecord).where(JobRecord.id == jid))
        ).scalar_one()
        assert job.status == JobStatus.FAILED
        assert job.error_detail["type"] == "ValueError"


# ---------------------------------------------------------------------------
# Test 10 — render failure rolls back: no PosterRecord, no RenderRecord
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_task_render_failure_rolls_back(sessionmaker_fx, tmp_path) -> None:
    from flyer_generator.api.tasks.poster import task_generate_poster

    jid = "01HPOSTER0000RENDERFAILURE0"[:26]
    payload = _payload(template="editorial_grand", size="18x24")
    await _seed_job(sessionmaker_fx, jid, payload)
    ctx = _build_ctx(sessionmaker_fx, tmp_path)

    fake_template = MagicMock()

    with patch(
        "flyer_generator.api.tasks.poster.load_template",
        return_value=fake_template,
    ), patch(
        "flyer_generator.api.tasks.poster.FlyerGenerator"
    ) as GenCls:
        GenCls.return_value.generate = AsyncMock(side_effect=RuntimeError("boom"))
        with pytest.raises(RuntimeError):
            await task_generate_poster(ctx, job_id=jid, payload=payload)

    async with sessionmaker_fx() as s:
        # No PosterRecord, no RenderRecord rows committed.
        posters = (await s.execute(select(PosterRecord))).scalars().all()
        assert posters == []
        renders = (await s.execute(select(RenderRecord))).scalars().all()
        assert renders == []
        job = (
            await s.execute(select(JobRecord).where(JobRecord.id == jid))
        ).scalar_one()
        assert job.status == JobStatus.FAILED
        assert job.error_detail["type"] == "RuntimeError"


# ---------------------------------------------------------------------------
# Test 11 — content_payload echoes full payload dict
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_poster_record_content_payload_round_trips(
    sessionmaker_fx, tmp_path
) -> None:
    from flyer_generator.api.tasks.poster import task_generate_poster

    jid = "01HPOSTER0000CONTENTPAYLOAD"[:26]
    payload = _payload(
        template="editorial_grand",
        size="18x24",
        brand_kit_slug="acme-co",
        image_hint="moody twilight",
    )
    await _seed_job(sessionmaker_fx, jid, payload)
    ctx = _build_ctx(sessionmaker_fx, tmp_path)

    fake_out = _make_fake_flyer_output()
    fake_template = MagicMock()

    with patch(
        "flyer_generator.api.tasks.poster.load_template",
        return_value=fake_template,
    ), patch(
        "flyer_generator.api.tasks.poster.FlyerGenerator"
    ) as GenCls:
        GenCls.return_value.generate = AsyncMock(return_value=fake_out)
        await task_generate_poster(ctx, job_id=jid, payload=payload)

    async with sessionmaker_fx() as s:
        poster = (await s.execute(select(PosterRecord))).scalar_one()
        assert poster.brand_kit_slug == "acme-co"
        assert poster.content_payload == payload


# ---------------------------------------------------------------------------
# Test 12 — artifact path under <artifact_root_flyer>/posters/<job_id>.png
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_artifact_path_under_posters_subdir(
    sessionmaker_fx, tmp_path
) -> None:
    from flyer_generator.api.tasks.poster import task_generate_poster

    jid = "01HPOSTER000ARTIFACTPATH000"[:26]
    payload = _payload(template="editorial_grand", size="18x24")
    await _seed_job(sessionmaker_fx, jid, payload)
    ctx = _build_ctx(sessionmaker_fx, tmp_path)

    fake_out = _make_fake_flyer_output()
    fake_template = MagicMock()

    with patch(
        "flyer_generator.api.tasks.poster.load_template",
        return_value=fake_template,
    ), patch(
        "flyer_generator.api.tasks.poster.FlyerGenerator"
    ) as GenCls:
        GenCls.return_value.generate = AsyncMock(return_value=fake_out)
        await task_generate_poster(ctx, job_id=jid, payload=payload)

    async with sessionmaker_fx() as s:
        renders = (await s.execute(select(RenderRecord))).scalars().all()
        assert len(renders) == 1
        # Namespaced under /posters/.
        assert "/posters/" in renders[0].file_path
        # Filename is <job_id>.png.
        assert renders[0].file_path.endswith(f"{jid}.png")


# ---------------------------------------------------------------------------
# Test 13 — task_generate_poster registered in ALL_TASKS
# ---------------------------------------------------------------------------


def test_task_generate_poster_registered_in_all_tasks() -> None:
    from flyer_generator.api.tasks import ALL_TASKS, task_generate_poster

    assert task_generate_poster in ALL_TASKS
