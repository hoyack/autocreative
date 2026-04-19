"""BrochureContent — the data side of the schema renderer.

Templates declare structure ("a heading goes here, a bullet list goes here").
BrochureContent carries the actual words. Template `content_key` strings
navigate this model (e.g. "sections[1].heading", "back_panel.bullets").

Richer than legacy BrochureInput: sections can carry lead_paragraph, bullets,
quote, icon_hint in addition to body_paragraphs; back_panel is a structured
object; contact block is first-class.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from flyer_generator.brochure.models import (
    BrochureInput,
    ContactBlock,
    validate_hex_color,
)


class BackPanelContent(BaseModel):
    """Structured back-cover content.

    Unlike legacy BrochureBackPanel (which collapsed everything into a single
    string), this is a real object: heading + body + bullets + optional
    contact card + CTA button label.
    """

    model_config = ConfigDict(extra="forbid")

    kind: str = "cta"  # cta | bio | map_stub | contact | event
    heading: str | None = None
    body: str | None = None
    bullets: list[str] = Field(default_factory=list)
    cta_label: str | None = None
    cta_detail: str | None = None
    footer_note: str | None = None


class ContentSection(BaseModel):
    """One content section mapped onto tuck_flap or inner_{left,center,right}."""

    model_config = ConfigDict(extra="forbid")

    heading: str
    lead_paragraph: str | None = None
    body_paragraphs: list[str] = Field(default_factory=list)
    bullets: list[str] = Field(default_factory=list)
    quote: str | None = None
    quote_attribution: str | None = None
    icon_hint: str | None = None
    image_concept: str | None = None  # used when template has image_placeholder in this panel


class BrochureContent(BaseModel):
    """Primary content model for the schema renderer."""

    model_config = ConfigDict(extra="forbid")

    title: str
    subtitle: str | None = None
    tagline: str | None = None
    org: str
    hero_concept: str | None = None  # used when template front_cover has image_placeholder
    color_accent: str = "#1E3A5F"  # overrides template.palette.accent_default
    contact: ContactBlock | None = None
    sections: list[ContentSection] = Field(min_length=1, max_length=8)
    back_panel: BackPanelContent | None = None
    # Arbitrary extra key/value pairs referenceable via content_key (e.g. "extras.promo_code")
    extras: dict[str, str] = Field(default_factory=dict)

    @field_validator("color_accent")
    @classmethod
    def _validate_color_accent(cls, v: str) -> str:
        return validate_hex_color(v)

    @classmethod
    def from_brochure_input(cls, b: BrochureInput) -> BrochureContent:
        """Backward-compat adapter: hydrate from legacy BrochureInput.

        Body strings in the legacy model may carry bullet syntax ("- foo"),
        which we split into real bullets here. Everything else maps 1:1.
        """
        sections: list[ContentSection] = []
        for s in b.sections:
            paragraphs: list[str] = []
            bullets: list[str] = []
            current_para: list[str] = []
            for raw in s.body.splitlines():
                line = raw.strip()
                if not line:
                    if current_para:
                        paragraphs.append(" ".join(current_para))
                        current_para = []
                    continue
                if line.startswith("- "):
                    if current_para:
                        paragraphs.append(" ".join(current_para))
                        current_para = []
                    bullets.append(line[2:].strip())
                else:
                    current_para.append(line)
            if current_para:
                paragraphs.append(" ".join(current_para))

            lead = paragraphs[0] if paragraphs else None
            rest = paragraphs[1:] if len(paragraphs) > 1 else []
            sections.append(
                ContentSection(
                    heading=s.heading,
                    lead_paragraph=lead,
                    body_paragraphs=rest,
                    bullets=bullets,
                    icon_hint=s.icon_hint,
                )
            )

        back: BackPanelContent | None = None
        if b.back_panel is not None:
            # Treat the legacy back_panel.content string the same way: split
            # paragraphs + bullets into structured fields.
            paragraphs: list[str] = []
            bullets: list[str] = []
            current_para = []
            for raw in b.back_panel.content.splitlines():
                line = raw.strip()
                if not line:
                    if current_para:
                        paragraphs.append(" ".join(current_para))
                        current_para = []
                    continue
                if line.startswith("- "):
                    if current_para:
                        paragraphs.append(" ".join(current_para))
                        current_para = []
                    bullets.append(line[2:].strip())
                else:
                    current_para.append(line)
            if current_para:
                paragraphs.append(" ".join(current_para))

            heading = paragraphs[0] if paragraphs else None
            body = " ".join(paragraphs[1:]) if len(paragraphs) > 1 else None
            back = BackPanelContent(
                kind=b.back_panel.kind,
                heading=heading,
                body=body,
                bullets=bullets,
            )

        return cls(
            title=b.title,
            subtitle=b.subtitle,
            org=b.org,
            hero_concept=b.hero_concept,
            color_accent=b.color_accent,
            contact=b.contact,
            sections=sections,
            back_panel=back,
        )

    def resolve_key(self, key: str, section_index: int | None = None) -> Any:
        """Resolve a `content_key` expression against this content.

        Supported forms:
          - 'title', 'subtitle', 'tagline', 'org', 'hero_concept'
          - 'contact.phone', 'contact.email', etc.
          - 'sections[i].heading', 'sections[i].lead_paragraph', 'sections[i].bullets', etc.
          - 'section.heading' (when section_index is provided)
          - 'back_panel.heading', 'back_panel.body', 'back_panel.bullets', 'back_panel.cta_label'
          - 'extras.<name>'
        """
        # 'section.X' shorthand when section_index is provided
        if key.startswith("section.") and section_index is not None:
            sub = key.split(".", 1)[1]
            if section_index >= len(self.sections):
                return None
            return getattr(self.sections[section_index], sub, None)

        if key == "title":
            return self.title
        if key == "subtitle":
            return self.subtitle
        if key == "tagline":
            return self.tagline
        if key == "org":
            return self.org
        if key == "hero_concept":
            return self.hero_concept

        if key.startswith("contact."):
            if self.contact is None:
                return None
            return getattr(self.contact, key.split(".", 1)[1], None)

        if key.startswith("sections["):
            # sections[N].field[.subfield]
            try:
                idx_str, rest = key[len("sections[") :].split("]", 1)
                idx = int(idx_str)
                if idx >= len(self.sections):
                    return None
                # rest starts with '.'
                field = rest.lstrip(".")
                return getattr(self.sections[idx], field, None)
            except (ValueError, IndexError):
                return None

        if key.startswith("back_panel."):
            if self.back_panel is None:
                return None
            return getattr(self.back_panel, key.split(".", 1)[1], None)

        if key.startswith("extras."):
            return self.extras.get(key.split(".", 1)[1])

        return None
