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

    # PDF round-trip -- 2 pages, mediabox dims match the canvas.
    pdf_bytes = assemble_postcard_pdf(
        front_png, back_png, template.canvas.width, template.canvas.height
    )
    assert pdf_bytes.startswith(b"%PDF-")
    reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
    assert len(reader.pages) == 2
    # Page dims (reportlab points; pagesize was passed as pixels -> 1:1 mapping).
    assert int(reader.pages[0].mediabox.width) == template.canvas.width
    assert int(reader.pages[0].mediabox.height) == template.canvas.height
    assert int(reader.pages[1].mediabox.width) == template.canvas.width
    assert int(reader.pages[1].mediabox.height) == template.canvas.height


def test_render_smoke_xml_escapes_headline() -> None:
    """T-23-09 mitigation regression -- XML escape of user-supplied strings."""
    template = load_template("classic_portrait")
    content = _content(headline="A & B <X>")
    front_svg, _ = render_postcard(template, content)
    # The escaped tokens must appear; the raw form must not.
    assert "&amp;" in front_svg
    assert "&lt;X&gt;" in front_svg
    assert "<X>" not in front_svg
