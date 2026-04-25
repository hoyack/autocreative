"""Direct-invocation tests for ``task_generate_postcard`` (Phase 23-04 PC-01/PC-02/PC-04/PC-06).

Mirrors the brochure worker test pattern in ``tests/api/test_worker_tasks.py``:
hand-rolls a ``ctx`` dict, patches the heavy collaborators
(``load_template`` / ``render_postcard`` / ``Rasterizer`` / ``assemble_postcard_pdf``),
seeds a JobRecord, and awaits the real task function.

Verifies the BLOCKER-2 module-scope import contract (the patch points are
``flyer_generator.api.tasks.postcard.X``), the T-23-01 path-traversal guard
(``_validate_template_slug`` rejects ``.json`` / ``/`` / ``\\``), the
parallel-id pattern (``PostcardRecord.id == job_id``), and the 3-RenderRecord
emission with kinds ``postcard_front`` / ``postcard_back`` / ``postcard_pdf``.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select

from flyer_generator.api.models import (
    JobKind,
    JobRecord,
    JobStatus,
    PostcardRecord,
    RenderRecord,
)
from flyer_generator.models import ComfyJob
from flyer_generator.stages.comfy_client import ComfyClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _payload(template: str = "classic_portrait", with_address: bool = False) -> dict:
    p: dict = {
        "headline": "Hello there",
        "body": "Body copy goes here.",
        "image_hint": None,
        "brand_kit_slug": None,
        "template": template,
        "address_block": None,
    }
    if with_address:
        p["address_block"] = {
            "recipient_name": "Jane Doe",
            "street": "123 Main St",
            "city_state_zip": "Springfield, IL 62701",
        }
    return p


async def _seed_job(sessionmaker, job_id: str, payload: dict | None = None) -> None:
    async with sessionmaker() as s:
        s.add(
            JobRecord(
                id=job_id,
                kind=JobKind.POSTCARD,
                status=JobStatus.QUEUED,
                input_payload=payload or {},
            )
        )
        await s.commit()


class _FakeCanvas:
    width = 1200
    height = 1800


class _FakeTemplate:
    canvas = _FakeCanvas()


def _build_ctx(sessionmaker, tmp_path):
    from flyer_generator.api.config import AppSettings

    settings = AppSettings()
    settings.artifact_root_brochure = tmp_path
    return {"sessionmaker": sessionmaker, "settings": settings, "http_client": None}


# ---------------------------------------------------------------------------
# Test 1 — module imports cleanly
# ---------------------------------------------------------------------------


def test_task_generate_postcard_importable() -> None:
    """The task function imports successfully — no missing-module errors."""
    from flyer_generator.api.tasks.postcard import task_generate_postcard

    assert callable(task_generate_postcard)


# ---------------------------------------------------------------------------
# Test 2 — path-traversal guard
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "bad_name",
    [
        "foo.json",
        "../etc/passwd",
        "subdir/template",
        "subdir\\template",
    ],
)
def test_validate_template_slug_rejects_path_like(bad_name: str) -> None:
    """T-23-01 mitigation: refuses ``.json`` suffix, ``/``, ``\\``."""
    from flyer_generator.api.tasks.postcard import _validate_template_slug

    with pytest.raises(ValueError, match="bare slug"):
        _validate_template_slug(bad_name)


def test_validate_template_slug_accepts_bare_slug() -> None:
    from flyer_generator.api.tasks.postcard import _validate_template_slug

    # Should not raise.
    _validate_template_slug("classic_portrait")
    _validate_template_slug("modern_landscape")


# ---------------------------------------------------------------------------
# Test 3 — collaborators are at module scope (BLOCKER-2 mirror)
# ---------------------------------------------------------------------------


def test_module_scope_collaborators_are_patchable() -> None:
    """Each heavy collaborator must be importable + patchable at the module path."""
    import flyer_generator.api.tasks.postcard as pc_mod

    # All four MUST live as module-level names so unittest.mock.patch can
    # intercept them via ``patch("flyer_generator.api.tasks.postcard.X")``.
    assert hasattr(pc_mod, "load_template")
    assert hasattr(pc_mod, "render_postcard")
    assert hasattr(pc_mod, "Rasterizer")
    assert hasattr(pc_mod, "assemble_postcard_pdf")


# ---------------------------------------------------------------------------
# Test 4 — happy-path: 3 RenderRecords + 1 PostcardRecord + JobRecord SUCCEEDED
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_task_generate_postcard_writes_three_renders_and_postcard(
    sessionmaker_fx, tmp_path
) -> None:
    from flyer_generator.api.tasks.postcard import task_generate_postcard

    jid = "01HPOSTCARD000000000000001"
    payload = _payload(template="classic_portrait")
    await _seed_job(sessionmaker_fx, jid, payload)
    ctx = _build_ctx(sessionmaker_fx, tmp_path)

    fake_template = _FakeTemplate()

    with patch(
        "flyer_generator.api.tasks.postcard.load_template",
        return_value=fake_template,
    ), patch(
        "flyer_generator.api.tasks.postcard.render_postcard",
        return_value=("<svg>front</svg>", "<svg>back</svg>"),
    ), patch(
        "flyer_generator.api.tasks.postcard.Rasterizer"
    ) as RastCls, patch(
        "flyer_generator.api.tasks.postcard.assemble_postcard_pdf",
        return_value=b"%PDF-1.4 fake",
    ):
        RastCls.return_value.rasterize.return_value = b"\x89PNG\r\n"
        result_ref = await task_generate_postcard(ctx, job_id=jid, payload=payload)

    assert result_ref == jid

    async with sessionmaker_fx() as s:
        job = (
            await s.execute(select(JobRecord).where(JobRecord.id == jid))
        ).scalar_one()
        assert job.status == JobStatus.SUCCEEDED
        assert job.result_ref == jid

        renders = (await s.execute(select(RenderRecord))).scalars().all()
        assert len(renders) == 3
        kinds = {r.kind for r in renders}
        assert kinds == {"postcard_front", "postcard_back", "postcard_pdf"}

        postcards = (await s.execute(select(PostcardRecord))).scalars().all()
        assert len(postcards) == 1
        assert postcards[0].id == jid


# ---------------------------------------------------------------------------
# Test 5 — bad template raises ValueError + marks JobRecord FAILED
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_task_generate_postcard_rejects_path_template_and_marks_failed(
    sessionmaker_fx, tmp_path
) -> None:
    from flyer_generator.api.tasks.postcard import task_generate_postcard

    jid = "01HPOSTCARD000000000000002"
    payload = _payload(template="../etc/passwd")
    await _seed_job(sessionmaker_fx, jid, payload)
    ctx = _build_ctx(sessionmaker_fx, tmp_path)

    with pytest.raises(ValueError):
        await task_generate_postcard(ctx, job_id=jid, payload=payload)

    async with sessionmaker_fx() as s:
        job = (
            await s.execute(select(JobRecord).where(JobRecord.id == jid))
        ).scalar_one()
        assert job.status == JobStatus.FAILED
        assert job.error_detail["type"] == "ValueError"


# ---------------------------------------------------------------------------
# Test 6 — load_template raises FileNotFoundError -> JobRecord FAILED
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_task_generate_postcard_load_template_filenotfound(
    sessionmaker_fx, tmp_path
) -> None:
    from flyer_generator.api.tasks.postcard import task_generate_postcard

    jid = "01HPOSTCARD000000000000003"
    payload = _payload(template="nonexistent_template_xyz")
    await _seed_job(sessionmaker_fx, jid, payload)
    ctx = _build_ctx(sessionmaker_fx, tmp_path)

    # Real loader, real failure.
    with pytest.raises(FileNotFoundError):
        await task_generate_postcard(ctx, job_id=jid, payload=payload)

    async with sessionmaker_fx() as s:
        job = (
            await s.execute(select(JobRecord).where(JobRecord.id == jid))
        ).scalar_one()
        assert job.status == JobStatus.FAILED
        assert job.error_detail["type"] == "FileNotFoundError"


# ---------------------------------------------------------------------------
# Test 7 — render_postcard raises -> no PostcardRecord, no committed renders
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_task_generate_postcard_render_failure_rolls_back(
    sessionmaker_fx, tmp_path
) -> None:
    from flyer_generator.api.tasks.postcard import task_generate_postcard

    jid = "01HPOSTCARD000000000000004"
    payload = _payload(template="classic_portrait")
    await _seed_job(sessionmaker_fx, jid, payload)
    ctx = _build_ctx(sessionmaker_fx, tmp_path)

    async with sessionmaker_fx() as s:
        before = (await s.execute(select(RenderRecord))).scalars().all()
    assert before == []

    fake_template = _FakeTemplate()

    with patch(
        "flyer_generator.api.tasks.postcard.load_template",
        return_value=fake_template,
    ), patch(
        "flyer_generator.api.tasks.postcard.render_postcard",
        side_effect=RuntimeError("boom"),
    ):
        with pytest.raises(RuntimeError):
            await task_generate_postcard(ctx, job_id=jid, payload=payload)

    async with sessionmaker_fx() as s:
        # No PostcardRecord, no RenderRecord rows committed.
        postcards = (await s.execute(select(PostcardRecord))).scalars().all()
        assert postcards == []
        renders = (await s.execute(select(RenderRecord))).scalars().all()
        assert renders == []
        job = (
            await s.execute(select(JobRecord).where(JobRecord.id == jid))
        ).scalar_one()
        assert job.status == JobStatus.FAILED
        assert job.error_detail["type"] == "RuntimeError"


# ---------------------------------------------------------------------------
# Test 8 — address-block-present payload threads through to render_postcard
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_task_generate_postcard_threads_address_block(
    sessionmaker_fx, tmp_path
) -> None:
    from flyer_generator.api.tasks.postcard import task_generate_postcard

    jid = "01HPOSTCARD000000000000005"
    payload = _payload(template="classic_portrait", with_address=True)
    await _seed_job(sessionmaker_fx, jid, payload)
    ctx = _build_ctx(sessionmaker_fx, tmp_path)

    seen_args: dict = {}

    def fake_render(template, content):
        seen_args["template"] = template
        seen_args["content"] = content
        return ("<svg>front</svg>", "<svg>back</svg>")

    fake_template = _FakeTemplate()

    with patch(
        "flyer_generator.api.tasks.postcard.load_template",
        return_value=fake_template,
    ), patch(
        "flyer_generator.api.tasks.postcard.render_postcard",
        side_effect=fake_render,
    ), patch(
        "flyer_generator.api.tasks.postcard.Rasterizer"
    ) as RastCls, patch(
        "flyer_generator.api.tasks.postcard.assemble_postcard_pdf",
        return_value=b"%PDF-1.4 fake",
    ):
        RastCls.return_value.rasterize.return_value = b"\x89PNG\r\n"
        await task_generate_postcard(ctx, job_id=jid, payload=payload)

    content = seen_args["content"]
    assert content.headline == "Hello there"
    assert content.body == "Body copy goes here."
    assert content.address_block is not None
    assert content.address_block.recipient_name == "Jane Doe"
    assert content.address_block.street == "123 Main St"
    assert content.address_block.city_state_zip == "Springfield, IL 62701"


# ---------------------------------------------------------------------------
# Test 9 — address_block=None payload still succeeds
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_task_generate_postcard_no_address(
    sessionmaker_fx, tmp_path
) -> None:
    from flyer_generator.api.tasks.postcard import task_generate_postcard

    jid = "01HPOSTCARD000000000000006"
    payload = _payload(template="classic_portrait", with_address=False)
    await _seed_job(sessionmaker_fx, jid, payload)
    ctx = _build_ctx(sessionmaker_fx, tmp_path)

    seen_args: dict = {}

    def fake_render(template, content):
        seen_args["content"] = content
        return ("<svg>front</svg>", "<svg>back</svg>")

    fake_template = _FakeTemplate()

    with patch(
        "flyer_generator.api.tasks.postcard.load_template",
        return_value=fake_template,
    ), patch(
        "flyer_generator.api.tasks.postcard.render_postcard",
        side_effect=fake_render,
    ), patch(
        "flyer_generator.api.tasks.postcard.Rasterizer"
    ) as RastCls, patch(
        "flyer_generator.api.tasks.postcard.assemble_postcard_pdf",
        return_value=b"%PDF-1.4 fake",
    ):
        RastCls.return_value.rasterize.return_value = b"\x89PNG\r\n"
        result_ref = await task_generate_postcard(ctx, job_id=jid, payload=payload)

    assert result_ref == jid
    assert seen_args["content"].address_block is None


# ---------------------------------------------------------------------------
# Test 10 — PostcardRecord.id == job_id (parallel-id assertion)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_postcard_record_id_equals_job_id(sessionmaker_fx, tmp_path) -> None:
    from flyer_generator.api.tasks.postcard import task_generate_postcard

    jid = "01HPOSTCARD000000000000007"
    payload = _payload(template="classic_portrait")
    await _seed_job(sessionmaker_fx, jid, payload)
    ctx = _build_ctx(sessionmaker_fx, tmp_path)

    fake_template = _FakeTemplate()

    with patch(
        "flyer_generator.api.tasks.postcard.load_template",
        return_value=fake_template,
    ), patch(
        "flyer_generator.api.tasks.postcard.render_postcard",
        return_value=("<svg>front</svg>", "<svg>back</svg>"),
    ), patch(
        "flyer_generator.api.tasks.postcard.Rasterizer"
    ) as RastCls, patch(
        "flyer_generator.api.tasks.postcard.assemble_postcard_pdf",
        return_value=b"%PDF-1.4 fake",
    ):
        RastCls.return_value.rasterize.return_value = b"\x89PNG\r\n"
        await task_generate_postcard(ctx, job_id=jid, payload=payload)

    async with sessionmaker_fx() as s:
        postcards = (await s.execute(select(PostcardRecord))).scalars().all()
        assert len(postcards) == 1
        assert postcards[0].id == jid


# ---------------------------------------------------------------------------
# Test 11 — PostcardRecord.template + .brand_kit_slug match payload
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_postcard_record_persists_template_and_brand_kit(
    sessionmaker_fx, tmp_path
) -> None:
    from flyer_generator.api.tasks.postcard import task_generate_postcard

    jid = "01HPOSTCARD000000000000008"
    payload = _payload(template="modern_landscape")
    payload["brand_kit_slug"] = "acme-co"
    await _seed_job(sessionmaker_fx, jid, payload)
    ctx = _build_ctx(sessionmaker_fx, tmp_path)

    fake_template = _FakeTemplate()
    fake_template.canvas = type("C", (), {"width": 1800, "height": 1200})()

    with patch(
        "flyer_generator.api.tasks.postcard.load_template",
        return_value=fake_template,
    ), patch(
        "flyer_generator.api.tasks.postcard.render_postcard",
        return_value=("<svg>front</svg>", "<svg>back</svg>"),
    ), patch(
        "flyer_generator.api.tasks.postcard.Rasterizer"
    ) as RastCls, patch(
        "flyer_generator.api.tasks.postcard.assemble_postcard_pdf",
        return_value=b"%PDF-1.4 fake",
    ):
        RastCls.return_value.rasterize.return_value = b"\x89PNG\r\n"
        await task_generate_postcard(ctx, job_id=jid, payload=payload)

    async with sessionmaker_fx() as s:
        postcard = (await s.execute(select(PostcardRecord))).scalar_one()
        assert postcard.template == "modern_landscape"
        assert postcard.brand_kit_slug == "acme-co"


# ---------------------------------------------------------------------------
# Test 12 — PostcardRecord.content_payload echoes full payload
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_postcard_record_content_payload_round_trips(
    sessionmaker_fx, tmp_path
) -> None:
    from flyer_generator.api.tasks.postcard import task_generate_postcard

    jid = "01HPOSTCARD000000000000009"
    payload = _payload(template="classic_portrait", with_address=True)
    payload["image_hint"] = "soft pastels at sunset"
    await _seed_job(sessionmaker_fx, jid, payload)
    ctx = _build_ctx(sessionmaker_fx, tmp_path)

    fake_template = _FakeTemplate()

    with patch(
        "flyer_generator.api.tasks.postcard.load_template",
        return_value=fake_template,
    ), patch(
        "flyer_generator.api.tasks.postcard.render_postcard",
        return_value=("<svg>front</svg>", "<svg>back</svg>"),
    ), patch(
        "flyer_generator.api.tasks.postcard.Rasterizer"
    ) as RastCls, patch(
        "flyer_generator.api.tasks.postcard.assemble_postcard_pdf",
        return_value=b"%PDF-1.4 fake",
    ):
        RastCls.return_value.rasterize.return_value = b"\x89PNG\r\n"
        await task_generate_postcard(ctx, job_id=jid, payload=payload)

    async with sessionmaker_fx() as s:
        postcard = (await s.execute(select(PostcardRecord))).scalar_one()
        assert postcard.content_payload == payload


# ---------------------------------------------------------------------------
# Test 13 — artifact paths under <artifact_root_brochure>/postcards/<job_id>/
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_artifact_paths_under_postcards_subdir(
    sessionmaker_fx, tmp_path
) -> None:
    from flyer_generator.api.tasks.postcard import task_generate_postcard

    jid = "01HPOSTCARD000000000000010"
    payload = _payload(template="classic_portrait")
    await _seed_job(sessionmaker_fx, jid, payload)
    ctx = _build_ctx(sessionmaker_fx, tmp_path)

    fake_template = _FakeTemplate()

    with patch(
        "flyer_generator.api.tasks.postcard.load_template",
        return_value=fake_template,
    ), patch(
        "flyer_generator.api.tasks.postcard.render_postcard",
        return_value=("<svg>front</svg>", "<svg>back</svg>"),
    ), patch(
        "flyer_generator.api.tasks.postcard.Rasterizer"
    ) as RastCls, patch(
        "flyer_generator.api.tasks.postcard.assemble_postcard_pdf",
        return_value=b"%PDF-1.4 fake",
    ):
        RastCls.return_value.rasterize.return_value = b"\x89PNG\r\n"
        await task_generate_postcard(ctx, job_id=jid, payload=payload)

    async with sessionmaker_fx() as s:
        renders = (await s.execute(select(RenderRecord))).scalars().all()
        for r in renders:
            assert f"/postcards/{jid}/" in r.file_path, (
                f"expected /postcards/{jid}/ in {r.file_path}"
            )


# ---------------------------------------------------------------------------
# Test 14 — task_generate_postcard registered in ALL_TASKS
# ---------------------------------------------------------------------------


def test_task_registered_in_all_tasks() -> None:
    from flyer_generator.api.tasks import ALL_TASKS, task_generate_postcard

    assert task_generate_postcard in ALL_TASKS


# ---------------------------------------------------------------------------
# PLF-01 (Phase 24.1) — Comfy invocation contract.
#
# These two tests patch ``ComfyClient.generate`` directly — the lowest
# integration seam — so a green pass proves the worker actually wires
# Comfy when ``image_hint`` is supplied. Patching a not-yet-existing
# symbol on the worker module would auto-create a stand-in attribute and
# pass trivially, defeating the contract.
# ---------------------------------------------------------------------------


def _fake_comfy_job() -> ComfyJob:
    from datetime import datetime, timezone

    return ComfyJob(
        prompt_id="fake-prompt-id",
        submitted_at=datetime.now(tz=timezone.utc),
        positive_prompt="lush spring garden",
        negative_prompt="",
        seed=42,
        attempt_number=1,
    )


@pytest.mark.asyncio
async def test_task_generate_postcard_invokes_comfy_when_image_hint_set(
    sessionmaker_fx, tmp_path
) -> None:
    """PLF-01: worker MUST call Comfy when payload supplies ``image_hint``.

    Patches ``ComfyClient.generate`` at the lowest seam; the assertion is
    that the await happened at least once. Mirrors the brochure worker's
    ``generate_template_images`` -> ``ComfyClient.generate`` chain.
    """
    from flyer_generator.api.tasks.postcard import task_generate_postcard

    jid = "01HPLF01HASIMAGEHINT0000001"
    payload = _payload(template="classic_portrait")
    payload["image_hint"] = "lush spring garden, soft morning light"
    payload["generate_images"] = True
    await _seed_job(sessionmaker_fx, jid, payload)
    ctx = _build_ctx(sessionmaker_fx, tmp_path)

    fake_template = _FakeTemplate()
    fake_png = b"\x89PNG\r\n\x1a\nfake-payload"

    with patch.object(
        ComfyClient,
        "generate",
        new=AsyncMock(return_value=(_fake_comfy_job(), fake_png)),
    ) as mock_generate, patch(
        "flyer_generator.api.tasks.postcard.load_template",
        return_value=fake_template,
    ), patch(
        "flyer_generator.api.tasks.postcard.render_postcard",
        return_value=("<svg>front</svg>", "<svg>back</svg>"),
    ), patch(
        "flyer_generator.api.tasks.postcard.Rasterizer"
    ) as RastCls, patch(
        "flyer_generator.api.tasks.postcard.assemble_postcard_pdf",
        return_value=b"%PDF-1.4 fake",
    ):
        RastCls.return_value.rasterize.return_value = b"\x89PNG\r\n"
        await task_generate_postcard(ctx, job_id=jid, payload=payload)

    assert mock_generate.await_count >= 1, (
        "ComfyClient.generate must be awaited at least once when image_hint "
        "is supplied — the postcard worker is failing to wire Comfy. "
        "Mirror the brochure worker's generate_template_images path."
    )


@pytest.mark.asyncio
async def test_task_generate_postcard_skips_comfy_when_image_hint_missing(
    sessionmaker_fx, tmp_path
) -> None:
    """PLF-01: worker MUST NOT call Comfy when ``image_hint`` is None.

    Same seam as the positive-path test, asserts call_count == 0.
    """
    from flyer_generator.api.tasks.postcard import task_generate_postcard

    jid = "01HPLF01NOIMAGEHINT00000001"
    payload = _payload(template="classic_portrait")
    payload["image_hint"] = None
    payload["generate_images"] = True
    await _seed_job(sessionmaker_fx, jid, payload)
    ctx = _build_ctx(sessionmaker_fx, tmp_path)

    fake_template = _FakeTemplate()

    with patch.object(
        ComfyClient,
        "generate",
        new=AsyncMock(return_value=(_fake_comfy_job(), b"")),
    ) as mock_generate, patch(
        "flyer_generator.api.tasks.postcard.load_template",
        return_value=fake_template,
    ), patch(
        "flyer_generator.api.tasks.postcard.render_postcard",
        return_value=("<svg>front</svg>", "<svg>back</svg>"),
    ), patch(
        "flyer_generator.api.tasks.postcard.Rasterizer"
    ) as RastCls, patch(
        "flyer_generator.api.tasks.postcard.assemble_postcard_pdf",
        return_value=b"%PDF-1.4 fake",
    ):
        RastCls.return_value.rasterize.return_value = b"\x89PNG\r\n"
        await task_generate_postcard(ctx, job_id=jid, payload=payload)

    assert mock_generate.await_count == 0, (
        "ComfyClient.generate must NOT be awaited when image_hint is None — "
        "the worker is incorrectly calling Comfy without a user hint."
    )
