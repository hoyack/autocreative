"""Render-smoke integration: load_template -> render_postcard -> Rasterizer -> assemble_postcard_pdf.

Phase 23 PC-04 verification: full pipeline integration for all 4
permutations (2 templates x address-block-on/off). No HTTP, no DB --
this is the pure-Python contract.

Permutation matrix (locked by CONTEXT.md `## Permutation tests`):
    2 templates x {with_address, without_address} = 4 cases.

Each case asserts:
    - Front + back SVGs start with `<svg ` and embed canvas dims.
    - Address fields render in back SVG iff with_address=True.
    - Rasterized PNGs start with PNG magic + are non-trivially sized.
    - Assembled PDF starts with `%PDF-` and has 2 pages with mediabox
      dims matching template.canvas.

A separate XML-escape regression test guards T-23-09 mitigation
(headline / body must be escaped before reaching the front SVG).
"""

from __future__ import annotations

import io

import pypdf
import pytest

from flyer_generator.postcard.schema_renderer import (
    PostcardAddressBlock,
    PostcardContent,
    load_template,
    render_postcard,
)
from flyer_generator.postcard.stages.pdf import assemble_postcard_pdf
from flyer_generator.stages.rasterizer import Rasterizer

_TEMPLATES = ["classic_portrait", "modern_landscape"]
_ADDRESS_FLAGS = [False, True]


def _content(headline: str = "Save the Date", with_address: bool = False) -> PostcardContent:
    ab: PostcardAddressBlock | None = None
    if with_address:
        ab = PostcardAddressBlock(
            recipient_name="Jane Doe",
            street="123 Main St",
            city_state_zip="Springfield, IL 62701",
        )
    return PostcardContent(
        headline=headline,
        body="Body copy goes here.",
        address_block=ab,
    )


@pytest.mark.parametrize("template_name", _TEMPLATES)
@pytest.mark.parametrize("with_address", _ADDRESS_FLAGS)
def test_render_smoke_all_permutations(template_name: str, with_address: bool) -> None:
    template = load_template(template_name)
    content = _content(with_address=with_address)

    front_svg, back_svg = render_postcard(template, content)
    assert front_svg.startswith("<svg ")
    assert back_svg.startswith("<svg ")
    assert f'width="{template.canvas.width}"' in front_svg
    assert f'height="{template.canvas.height}"' in front_svg
    assert f'width="{template.canvas.width}"' in back_svg
    assert f'height="{template.canvas.height}"' in back_svg

    # Address-block content visibility on the BACK panel only.
    if with_address:
        assert "Jane Doe" in back_svg
        assert "123 Main St" in back_svg
        assert "Springfield, IL 62701" in back_svg
    else:
        assert "Jane Doe" not in back_svg
        assert "123 Main St" not in back_svg
        assert "Springfield, IL 62701" not in back_svg

    # Rasterize each panel at the template canvas dims.
    rast = Rasterizer(width=template.canvas.width, height=template.canvas.height)
    front_png = rast.rasterize(front_svg)
    back_png = rast.rasterize(back_svg)
    assert front_png[:8] == b"\x89PNG\r\n\x1a\n"
    assert back_png[:8] == b"\x89PNG\r\n\x1a\n"
    assert len(front_png) > 1000
    assert len(back_png) > 1000

    # PDF round-trip -- 2 pages, mediabox dims match the canvas (in points).
    pdf_bytes = assemble_postcard_pdf(
        front_png, back_png, template.canvas.width, template.canvas.height
    )
    assert pdf_bytes.startswith(b"%PDF-")
    reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
    assert len(reader.pages) == 2
    # RM-01 (plan 24.2-01): mediabox is in PostScript points (canvas px * 72/300),
    # NOT pixels. 1200 px portrait -> 288 pt = 4 in.
    expected_w_pt = template.canvas.width * 72.0 / 300.0
    expected_h_pt = template.canvas.height * 72.0 / 300.0
    for page in reader.pages:
        assert abs(float(page.mediabox.width) - expected_w_pt) < 0.01
        assert abs(float(page.mediabox.height) - expected_h_pt) < 0.01


def test_render_smoke_xml_escapes_headline() -> None:
    """T-23-09 mitigation regression -- XML escape of user-supplied strings."""
    template = load_template("classic_portrait")
    content = _content(headline="A & B <X>")
    front_svg, _ = render_postcard(template, content)
    # The escaped tokens must appear; the raw form must not.
    assert "&amp;" in front_svg
    assert "&lt;X&gt;" in front_svg
    assert "<X>" not in front_svg


# ---------------------------------------------------------------------------
# PLF-01 (Phase 24.1) -- body must render on the FRONT panel, not just back.
# RED test: today neither shipped schema places `body` on the front, so the
# perception loop got a [ hero ]-only render with NO body copy visible.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("template_name", _TEMPLATES)
def test_postcard_renders_body_on_front(template_name: str) -> None:
    """PLF-01: ``body`` field must appear on the rendered FRONT SVG.

    Before this fix neither ``classic_portrait.json`` nor
    ``modern_landscape.json`` placed a TextElement bound to ``content_key:
    body`` on the front panel — only the headline rendered, leaving the
    rest of the message invisible until the user flipped the card. This
    locks the contract that the body always appears on the public-facing
    front panel.
    """
    template = load_template(template_name)
    body_marker = "Garden Tour starts at 11am"
    content = PostcardContent(headline="Save the Date", body=body_marker)

    front_svg, _back_svg = render_postcard(template, content)

    assert body_marker in front_svg, (
        f"body copy {body_marker!r} must render on the FRONT panel of "
        f"{template_name}; today the schema only places it on the back."
    )


@pytest.mark.parametrize("template_name", _TEMPLATES)
def test_postcard_no_hero_placeholder_label_when_image_hint_present(
    template_name: str,
) -> None:
    """PLF-01: literal ``[ hero ]`` label must never reach the front SVG.

    The perception loop revealed that even when ``image_hint`` is supplied
    by the user (the user's signal "please render an AI image here"), the
    front PNG still contains the literal placeholder text ``[ hero ]`` —
    proof the worker never reached Comfy AND the schema's
    ``show_placeholder_label`` was on. After the fix the label is off in
    both shipped schemas and a real PNG is hydrated when supplied.
    """
    template = load_template(template_name)
    content = PostcardContent(
        headline="Save the Date",
        body="Garden Tour starts at 11am",
        image_hint="lush spring garden",
    )

    # Pretend Comfy succeeded — pass a tiny PNG-shaped byte blob through the
    # renderer's new `images` kwarg (added in Task 2). The renderer must
    # NOT emit the literal "[ hero ]" label when the slot is hydrated.
    fake_png = b"\x89PNG\r\n\x1a\nfakepayload"
    front_svg, _back_svg = render_postcard(
        template, content, images={"hero": fake_png}
    )

    assert "[ hero ]" not in front_svg, (
        f"literal '[ hero ]' must never appear in {template_name}'s front SVG "
        "once a hero image is supplied (or with show_placeholder_label=False)."
    )
