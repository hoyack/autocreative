"""Render artifact streaming tests (API-11).

Includes explicit T-1 (HIGH) path-traversal verification: a RenderRecord row
with ``file_path="/etc/hostname"`` MUST return 404 without leaking the
filesystem shape in the response body.

Test corpus:
- 404 on unknown id
- 422 on bad ULID length
- Happy path: PNG inside ``artifact_root_flyer`` streamed with ``image/png``
- Happy path: PDF inside ``artifact_root_brochure`` streamed with ``application/pdf``
- T-1 path traversal: file_path=/etc/hostname -> 404 (NEVER leaks)
- Dotdot traversal (``..``) inside file_path -> 404 after ``resolve(strict=True)``
- Missing file inside allowed root -> 404 (``resolve(strict=True)`` raises)
- Unknown extension (.exe) inside allowed root -> 404 (whitelist defense)
"""

from __future__ import annotations

from pathlib import Path

import pytest

from flyer_generator.api.models import RenderRecord


@pytest.mark.asyncio
async def test_get_render_404_on_unknown_id(client) -> None:
    r = await client.get("/api/v1/renders/01HABCNOPERENDER0000000000/image")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_get_render_422_on_bad_id_length(client) -> None:
    r = await client.get("/api/v1/renders/shortid/image")
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_get_render_streams_png_inside_flyer_root(
    client, sessionmaker_fx, app, tmp_path
) -> None:
    """Happy path: render in artifact_root_flyer is streamed with correct mime."""
    flyer_root = tmp_path / "flyers"
    flyer_root.mkdir()
    png_path = flyer_root / "sample.png"
    # Minimal PNG-like bytes — FileResponse streams raw bytes, the test only
    # verifies the response wire shape and content-type, not image decoding.
    png_path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 16)

    app.state.settings.artifact_root_flyer = flyer_root

    render_id = "01HABCRENDEROKAY0000000000"  # 26 chars
    async with sessionmaker_fx() as s:
        s.add(
            RenderRecord(
                id=render_id,
                kind="flyer_final",
                file_path=str(png_path),
            )
        )
        await s.commit()

    r = await client.get(f"/api/v1/renders/{render_id}/image")
    assert r.status_code == 200
    assert r.headers.get("content-type") == "image/png"
    disposition = r.headers.get("content-disposition", "")
    assert "inline" in disposition
    assert 'filename="sample.png"' in disposition
    assert r.content.startswith(b"\x89PNG")


@pytest.mark.asyncio
async def test_get_render_streams_pdf_inside_brochure_root(
    client, sessionmaker_fx, app, tmp_path
) -> None:
    brochure_root = tmp_path / "brochures"
    brochure_root.mkdir()
    pdf_path = brochure_root / "print.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n%%EOF\n")

    app.state.settings.artifact_root_brochure = brochure_root

    render_id = "01HABCRENDERPDF10000000000"  # 26 chars
    async with sessionmaker_fx() as s:
        s.add(
            RenderRecord(
                id=render_id,
                kind="brochure_pdf",
                file_path=str(pdf_path),
            )
        )
        await s.commit()

    r = await client.get(f"/api/v1/renders/{render_id}/image")
    assert r.status_code == 200
    assert r.headers.get("content-type") == "application/pdf"


@pytest.mark.asyncio
async def test_get_render_rejects_path_traversal_outside_all_roots(
    client, sessionmaker_fx, app, tmp_path
) -> None:
    """T-1 (HIGH): malicious file_path must NOT stream any file outside allowed roots.

    Scenario: an attacker-controlled RenderRecord row (e.g. via a future bug in a
    route that accepts user-supplied paths) sets ``file_path`` to a system file.
    The containment check MUST force a 404 without hinting at the filesystem.
    """
    # Point ALL four allowed roots inside tmp_path — nothing in /etc/ is reachable.
    app.state.settings.artifact_root_flyer = tmp_path / "flyers"
    app.state.settings.artifact_root_brochure = tmp_path / "brochures"
    app.state.settings.brand_kits_dir = tmp_path / "brand_kits"
    app.state.settings.social_campaigns_dir = tmp_path / "campaigns"
    for d in (
        app.state.settings.artifact_root_flyer,
        app.state.settings.artifact_root_brochure,
        app.state.settings.brand_kits_dir,
        app.state.settings.social_campaigns_dir,
    ):
        Path(d).mkdir(exist_ok=True)

    # Pick a universally-readable system file that lives outside tmp_path.
    target = Path("/etc/hostname")
    if not target.is_file():
        target = Path("/etc/passwd")
    if not target.is_file():
        pytest.skip("test requires /etc/hostname or /etc/passwd on the host")

    render_id = "01HABCRENDTRVRSL0000000000"  # 26 chars
    async with sessionmaker_fx() as s:
        s.add(
            RenderRecord(
                id=render_id,
                kind="flyer_final",
                file_path=str(target),  # malicious path, OUTSIDE all configured roots
            )
        )
        await s.commit()

    r = await client.get(f"/api/v1/renders/{render_id}/image")
    assert r.status_code == 404, (
        f"T-1 path traversal MUST return 404 — got {r.status_code}"
    )
    # Body must NOT hint at the reason (no "outside allowed roots" leak).
    body = r.json()
    # Opaque "render not found" message — same as unknown id, missing file, bad ext.
    assert body.get("detail") == "render not found"


@pytest.mark.asyncio
async def test_get_render_rejects_dotdot_in_filepath(
    client, sessionmaker_fx, app, tmp_path
) -> None:
    """Literal '..' traversal in file_path — still 404 after resolve(strict=True)."""
    flyer_root = tmp_path / "flyers"
    flyer_root.mkdir()
    # Path that LEXICALLY starts under flyer_root but resolves OUTSIDE it.
    # Use enough '..' segments to escape pytest's tmp_path tree
    # (typically /tmp/pytest-of-<user>/pytest-N/<test>/flyers, so 10 levels
    # up reliably reaches '/'; ``Path.resolve`` clamps at filesystem root).
    malicious = flyer_root
    for _ in range(10):
        malicious = malicious / ".."
    malicious = malicious / "etc" / "hostname"

    try:
        real_target = malicious.resolve(strict=True)
    except (FileNotFoundError, OSError):
        pytest.skip("system does not have /etc/hostname")

    # Ensure the resolved target actually escapes the root (sanity check).
    if real_target.is_relative_to(flyer_root.resolve()):
        pytest.skip("resolved target is inside flyer_root; cannot construct traversal")

    app.state.settings.artifact_root_flyer = flyer_root
    app.state.settings.artifact_root_brochure = tmp_path / "brochures"
    app.state.settings.brand_kits_dir = tmp_path / "brand_kits"
    app.state.settings.social_campaigns_dir = tmp_path / "campaigns"
    for d in (
        app.state.settings.artifact_root_brochure,
        app.state.settings.brand_kits_dir,
        app.state.settings.social_campaigns_dir,
    ):
        Path(d).mkdir(exist_ok=True)

    render_id = "01HABCRENDDOTDOT0000000000"  # 26 chars
    async with sessionmaker_fx() as s:
        s.add(
            RenderRecord(
                id=render_id,
                kind="flyer_final",
                file_path=str(malicious),
            )
        )
        await s.commit()

    r = await client.get(f"/api/v1/renders/{render_id}/image")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_get_render_rejects_missing_file_even_inside_root(
    client, sessionmaker_fx, app, tmp_path
) -> None:
    """file_path inside an allowed root but file does NOT exist -> 404 (strict resolve)."""
    flyer_root = tmp_path / "flyers"
    flyer_root.mkdir()
    app.state.settings.artifact_root_flyer = flyer_root

    ghost = flyer_root / "does-not-exist.png"

    render_id = "01HABCRENDGHOST10000000000"  # 26 chars
    async with sessionmaker_fx() as s:
        s.add(
            RenderRecord(
                id=render_id,
                kind="flyer_final",
                file_path=str(ghost),
            )
        )
        await s.commit()

    r = await client.get(f"/api/v1/renders/{render_id}/image")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_get_render_rejects_unknown_extension(
    client, sessionmaker_fx, app, tmp_path
) -> None:
    """Extension whitelist defense-in-depth: .exe -> 404, never octet-stream."""
    flyer_root = tmp_path / "flyers"
    flyer_root.mkdir()
    evil = flyer_root / "inside-root-but-bad-ext.exe"
    evil.write_bytes(b"MZ")  # extension, not content, is what's checked

    app.state.settings.artifact_root_flyer = flyer_root

    render_id = "01HABCRENDBADEXT0000000000"  # 26 chars
    async with sessionmaker_fx() as s:
        s.add(
            RenderRecord(
                id=render_id,
                kind="weird",
                file_path=str(evil),
            )
        )
        await s.commit()

    r = await client.get(f"/api/v1/renders/{render_id}/image")
    assert r.status_code == 404
