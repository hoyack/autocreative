"""PostcardContent — runtime payload for the postcard renderer.

Fields mirror PostcardCreateRequest (the API schema in
flyer_generator/api/schemas/postcards.py), but are decoupled at the
module boundary so the schema_renderer package has no dependency on the
api/ package. The worker layer (Phase 23-04) is responsible for
translating a PostcardCreateRequest into a PostcardContent before
invoking ``render_postcard``.

The model also provides ``resolve_key`` which maps a template ``content_key``
string (e.g. ``"headline"``, ``"address_block.street"``) to a typed value.
The renderer uses this single shaped lookup so templates and content stay
loosely coupled — templates declare which slots they want filled, content
declares what to fill them with.

When ``address_block`` is None, ``resolve_key("address_block.<field>")``
returns an empty string (not None) so TextElements in the back panel
render as empty text rather than triggering the renderer's "skip element"
path. This keeps the rendered SVG visually consistent regardless of
whether the caller supplied an address.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class PostcardAddressBlock(BaseModel):
    """Optional addressee + delivery address fields for the back panel.

    Field bounds match the api/schemas/postcards.py::AddressBlock contract
    (1..120 chars per field) so a request payload validated at the API edge
    can round-trip into the renderer payload without surprises.
    """

    model_config = ConfigDict(extra="forbid")

    recipient_name: str = Field(min_length=1, max_length=120)
    street: str = Field(min_length=1, max_length=120)
    city_state_zip: str = Field(min_length=1, max_length=120)


class PostcardContent(BaseModel):
    """Resolved-content payload consumed by ``render_postcard``."""

    model_config = ConfigDict(extra="forbid")

    headline: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=2000)
    image_hint: str | None = Field(default=None, max_length=500)
    address_block: PostcardAddressBlock | None = None

    def resolve_key(
        self, content_key: str, section_index: int | None = None
    ) -> Any:
        """Map a template ``content_key`` to a string value (or None).

        Parameters
        ----------
        content_key:
            Dotted key name from a TextElement / BulletsElement. Supported
            values:
              * ``"headline"`` -> str
              * ``"body"`` -> str
              * ``"image_hint"`` -> str | None
              * ``"address_block.recipient_name"`` -> str | ""
              * ``"address_block.street"`` -> str | ""
              * ``"address_block.city_state_zip"`` -> str | ""
        section_index:
            Reserved for forward compatibility with multi-section postcards;
            currently unused (postcards have a flat content namespace).

        Returns
        -------
        str | None
            The resolved value, ``""`` when the address-block prefix is
            requested but ``self.address_block is None`` (so the renderer
            emits empty text rather than skipping the element), or ``None``
            when the key is not recognised at all (so the renderer falls
            back to ``el.static_text or ""`` per the brochure pattern).
        """
        # Reserved arg consumed only to keep the resolve_key signature
        # parallel to BrochureContent.resolve_key (used by the renderer).
        del section_index

        if content_key == "headline":
            return self.headline
        if content_key == "body":
            return self.body
        if content_key == "image_hint":
            return self.image_hint
        if content_key.startswith("address_block."):
            suffix = content_key[len("address_block.") :]
            if self.address_block is None:
                # Empty string keeps TextElement render path active so the
                # template's bbox + role/typography are still honoured (just
                # with no glyphs); the brochure renderer's `if not text:
                # return ""` path means an empty string also short-circuits
                # at the element level — both behaviors are acceptable, and
                # match the plan's must_have for "address-block TextElements
                # render empty (no exception, no NULL string in SVG)".
                return ""
            value = getattr(self.address_block, suffix, None)
            return value if value is not None else ""
        # Static / unknown -> None (renderer falls back to el.static_text or "").
        return None
