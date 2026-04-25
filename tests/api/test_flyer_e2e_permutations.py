"""E2E permutation tests for POST /api/v1/flyers (Phase 22 FT-08).

Covers every (template x subtype) permutation through the full request
pipeline:

- HTTP route layer:  schema accepts (template, subtype) for every valid
  combination -> 202 + job_id.
- Worker layer:      worker derives the right RenderRecord.kind from
  FlyerInput.subtype (flyer_event_final | flyer_info_final) for every
  template.
- Schema-edge case:  bogus template slug -- schema accepts any non-empty
  string under 64 chars (validation deferred to worker per CONTEXT
  decision); this test confirms the schema layer does not over-reject.

Matrix derived live from list_templates() and template.subtype_compat:
- 6 event permutations (all templates support 'event')
- 4 info permutations (subtype_compat includes 'info' for editorial_classic,
  minimal_photo, zine, tight_typographic)
- 6 worker-kind permutations (event-subtype across all templates)
- 4 worker-kind permutations (info-subtype across info-compatible templates)
- 1 schema acceptance test for an invalid template slug

Reuses fixtures from tests/api/conftest.py: client, fake_arq_pool,
sessionmaker_fx. Reuses test helpers from tests/api/test_worker_tasks.py:
_FakeFlyerOut, _flyer_event_payload, _flyer_info_payload, _seed_job.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest
from sqlalchemy import select

from flyer_generator.api.models import (
    FlyerRecord,
    JobKind,
    JobRecord,
    JobStatus,
    RenderRecord,
)
from flyer_generator.flyer.schema_renderer import list_templates, load_template

# Reuse helpers from the existing worker-task test module.
from tests.api.test_worker_tasks import (  # noqa: E402
    _FakeFlyerOut,
    _flyer_event_payload,
    _flyer_info_payload,
    _seed_job,
)


# ---------------------------------------------------------------------------
# Permutation enumeration -- live from the loader
# ---------------------------------------------------------------------------


def _event_templates() -> list[str]:
    """All 6 templates support event subtype."""
    return list_templates()


def _info_templates() -> list[str]:
    """Templates whose subtype_compat includes 'info' (4 of 6)."""
    return [n for n in list_templates() if "info" in load_template(n).subtype_compat]


def _route_event_payload(template: str) -> dict:
    """Build a POST /api/v1/flyers request body for event subtype."""
    return {
        "event": {
            "title": "Permutation Event",
            "subtype": "event",
            "date": "2026-05-01",
            "time": "7:00 PM",
            "location_name": "Hall",
            "location_address": "1 Main St",
            "fees": "Free",
            "org": "Acme",
            "url": None,
            "style_concept": "test",
            "style_preset": "photorealistic",
            "color_accent": "#F59E0B",
        },
        "template": template,
        "preset": "photorealistic",
    }


def _route_info_payload(template: str) -> dict:
    """Build a POST /api/v1/flyers request body for info subtype.

    Info subtype omits date/time/venue/fees but the schema still requires
    the FlyerInput shape -- pass them as null per the FE submit handler.
    """
    return {
        "event": {
            "title": "Permutation Notice",
            "subtype": "info",
            "description": "Road closure announcement.",
            "call_to_action": "Plan alternate routes",
            "org": "City",
            "url": None,
            "style_concept": "civic",
            "style_preset": "photorealistic",
            "color_accent": "#F59E0B",
        },
        "template": template,
        "preset": "photorealistic",
    }


# ---------------------------------------------------------------------------
# Route layer -- schema + arq enqueue, no worker run
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "template", _event_templates(), ids=lambda t: f"event-{t}"
)
@pytest.mark.asyncio
async def test_post_event_flyer_per_template(template, client, fake_arq_pool) -> None:
    """Every template accepted via POST /api/v1/flyers with event subtype."""
    resp = await client.post("/api/v1/flyers", json=_route_event_payload(template))
    assert resp.status_code == 202, resp.text
    body = resp.json()
    assert "job_id" in body

    # arq received the right enqueue with the right template + subtype.
    func_name, _args, kwargs = fake_arq_pool.calls[-1]
    assert func_name == "task_generate_flyer"
    assert kwargs["payload"]["template"] == template
    assert kwargs["payload"]["event"]["subtype"] == "event"


@pytest.mark.parametrize(
    "template", _info_templates(), ids=lambda t: f"info-{t}"
)
@pytest.mark.asyncio
async def test_post_info_flyer_per_template(template, client, fake_arq_pool) -> None:
    """Every info-compatible template accepted via POST with info subtype."""
    resp = await client.post("/api/v1/flyers", json=_route_info_payload(template))
    assert resp.status_code == 202, resp.text
    body = resp.json()
    assert "job_id" in body

    func_name, _args, kwargs = fake_arq_pool.calls[-1]
    assert func_name == "task_generate_flyer"
    assert kwargs["payload"]["template"] == template
    assert kwargs["payload"]["event"]["subtype"] == "info"


# ---------------------------------------------------------------------------
# Worker layer -- direct invocation via task_generate_flyer
# ---------------------------------------------------------------------------


class _CapturingGen:
    """FlyerGenerator stub that records the template kwarg and returns FakeFlyerOut."""

    last_template: object | None = None

    def __init__(self, *a, **kw) -> None:
        pass

    async def generate(self, event, *, template=None):
        type(self).last_template = template
        return _FakeFlyerOut()


@pytest.mark.parametrize(
    "template", _event_templates(), ids=lambda t: f"event-kind-{t}"
)
@pytest.mark.asyncio
async def test_worker_produces_event_kind_per_template(
    template, sessionmaker_fx, tmp_path
) -> None:
    """For every template, event-subtype payload yields RenderRecord.kind=flyer_event_final."""
    from flyer_generator.api.config import AppSettings
    from flyer_generator.api.tasks.flyer import task_generate_flyer

    settings = AppSettings()
    settings.artifact_root_flyer = tmp_path
    ctx = {
        "sessionmaker": sessionmaker_fx,
        "settings": settings,
        "http_client": None,
    }

    # JobRecord IDs are 26 chars -- pad/truncate predictably.
    jid = ("01HFTEEPERM" + template.upper().replace("_", "")[:15]).ljust(26, "X")[:26]
    await _seed_job(sessionmaker_fx, jid, JobKind.FLYER)

    # Real loader -- template name comes from list_templates() so it exists on disk.
    payload = _flyer_event_payload(template=template)
    with patch(
        "flyer_generator.api.tasks.flyer.FlyerGenerator", _CapturingGen
    ):
        await task_generate_flyer(ctx, job_id=jid, payload=payload)

    async with sessionmaker_fx() as s:
        renders = (await s.execute(select(RenderRecord))).scalars().all()
        assert len(renders) == 1
        assert renders[0].kind == "flyer_event_final"
        flyers = (await s.execute(select(FlyerRecord))).scalars().all()
        assert len(flyers) == 1
        assert flyers[0].template == template
        # Worker threaded the loaded FlyerTemplateSchema through to the generator.
        assert _CapturingGen.last_template is not None
        # Real load_template returns a FlyerTemplateSchema whose .name matches.
        assert _CapturingGen.last_template.name == template


@pytest.mark.parametrize(
    "template", _info_templates(), ids=lambda t: f"info-kind-{t}"
)
@pytest.mark.asyncio
async def test_worker_produces_info_kind_per_template(
    template, sessionmaker_fx, tmp_path
) -> None:
    """For every info-compatible template, info-subtype payload yields kind=flyer_info_final."""
    from flyer_generator.api.config import AppSettings
    from flyer_generator.api.tasks.flyer import task_generate_flyer

    settings = AppSettings()
    settings.artifact_root_flyer = tmp_path
    ctx = {
        "sessionmaker": sessionmaker_fx,
        "settings": settings,
        "http_client": None,
    }

    jid = ("01HFTIINFO" + template.upper().replace("_", "")[:16]).ljust(26, "X")[:26]
    await _seed_job(sessionmaker_fx, jid, JobKind.FLYER)

    payload = _flyer_info_payload(template=template)
    with patch(
        "flyer_generator.api.tasks.flyer.FlyerGenerator", _CapturingGen
    ):
        await task_generate_flyer(ctx, job_id=jid, payload=payload)

    async with sessionmaker_fx() as s:
        renders = (await s.execute(select(RenderRecord))).scalars().all()
        assert len(renders) == 1
        assert renders[0].kind == "flyer_info_final"
        flyers = (await s.execute(select(FlyerRecord))).scalars().all()
        assert len(flyers) == 1
        assert flyers[0].template == template
        assert _CapturingGen.last_template is not None
        assert _CapturingGen.last_template.name == template


# ---------------------------------------------------------------------------
# Bad template handling -- schema layer accepts; worker rejects at load time
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_bogus_template_passes_schema_returns_202(client, fake_arq_pool) -> None:
    """Schema accepts any string (max_length=64); validation deferred to worker.

    This locks the CONTEXT decision: 'no enum, validation at worker
    load_template() time, not at schema layer'. A typo or freeform slug
    survives the route -- the worker will mark the JobRecord failed with
    FileNotFoundError once it runs (covered separately in
    tests/api/test_worker_tasks.py::test_flyer_task_bad_template_raises_and_marks_failed).
    """
    payload = _route_event_payload(template="nonexistent_template_xyz")
    resp = await client.post("/api/v1/flyers", json=payload)
    assert resp.status_code == 202, resp.text
    body = resp.json()
    assert "job_id" in body

    # Schema-level acceptance -- the bogus name is enqueued for the worker.
    _, _, kwargs = fake_arq_pool.calls[-1]
    assert kwargs["payload"]["template"] == "nonexistent_template_xyz"
