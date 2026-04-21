"""Style presets and registry for flyer generation."""

from pydantic import BaseModel

from flyer_generator.errors import UnknownPresetError


class StylePreset(BaseModel):
    """A named style preset with prompt fragments for image generation."""

    name: str
    positive_fragments: list[str]  # Each fragment may contain {concept} placeholder
    negative_fragment: str
    description: str


class PresetRegistry:
    """Registry of named style presets. Extensible by users."""

    def __init__(self) -> None:
        self._presets: dict[str, StylePreset] = {}

    def register(self, preset: StylePreset) -> None:
        self._presets[preset.name] = preset

    def get(self, name: str) -> StylePreset:
        if name not in self._presets:
            raise UnknownPresetError(
                f"Unknown preset: {name!r}. Available: {self.list_names()}"
            )
        return self._presets[name]

    def list_names(self) -> list[str]:
        return sorted(self._presets.keys())


# Universal flyer directives appended to all presets (from n8n workflow)
FLYER_DIRECTIVES: list[str] = [
    "Smooth clean bokeh areas in the upper third and lower third of the frame.",
    "Main subject centered in middle third of composition.",
    "No text, no writing, no letters, no signs, no symbols.",
    "Pure background art with no graphic design elements.",
    "Tall portrait composition 9:16.",
]

UNIVERSAL_NEGATIVE: str = (
    "text, writing, letters, words, numbers, watermark, logo, signs, symbols, "
    "UI, overlay, graphic design, borders, captions, labels, "
    "blurry, low quality, deformed, disfigured, noisy, grainy, "
    "cluttered composition, busy background, overlapping subjects"
)

def build_default_registry() -> PresetRegistry:
    """Create a PresetRegistry populated with the 6 built-in presets."""
    registry = PresetRegistry()

    # D-15: Six presets verbatim from n8n workflow (docs/n8n.json, Build Background Prompt node)
    builtins = {
        "photorealistic": StylePreset(
            name="photorealistic",
            positive_fragments=[
                "A cinematic photograph: {concept}.",
                "Shot on 35mm film, shallow depth of field, golden hour lighting.",
                "Professional color grading, warm tones, inviting atmosphere.",
            ],
            negative_fragment="cartoon, illustration, painting, anime, 3d render, cgi, drawing, sketch",
            description="Cinematic photograph with film grain and golden hour lighting",
        ),
        "anime": StylePreset(
            name="anime",
            positive_fragments=[
                "A vibrant anime illustration: {concept}.",
                "Studio Ghibli inspired, cel-shaded, rich saturated palette.",
                "Soft ambient lighting, detailed background art, dreamy atmosphere.",
            ],
            negative_fragment="photorealistic, photograph, 3d render, cgi, western cartoon, low detail",
            description="Studio Ghibli-inspired anime illustration with rich colors",
        ),
        "western_cartoon": StylePreset(
            name="western_cartoon",
            positive_fragments=[
                "A stylized cartoon illustration: {concept}.",
                "Bold outlines, flat color fills, playful exaggerated proportions.",
                "Bright cheerful palette, clean vector-style rendering.",
            ],
            negative_fragment="photorealistic, photograph, anime, 3d render, dark, gritty",
            description="Bold cartoon illustration with flat colors and clean outlines",
        ),
        "scifi": StylePreset(
            name="scifi",
            positive_fragments=[
                "A futuristic sci-fi scene: {concept}.",
                "Neon accents, holographic elements, sleek metallic surfaces.",
                "Dramatic volumetric lighting, cyberpunk atmosphere, high-tech environment.",
            ],
            negative_fragment="cartoon, hand-drawn, vintage, rustic, low-tech, blurry",
            description="Futuristic sci-fi scene with neon and volumetric lighting",
        ),
        "watercolor": StylePreset(
            name="watercolor",
            positive_fragments=[
                "A delicate watercolor painting: {concept}.",
                "Soft washes of color, visible paper texture, gentle bleeding edges.",
                "Impressionistic detail, pastel and muted tones, artistic brushwork.",
            ],
            negative_fragment="photorealistic, photograph, sharp lines, 3d render, digital art, cartoon",
            description="Delicate watercolor painting with soft washes and paper texture",
        ),
        "retro_poster": StylePreset(
            name="retro_poster",
            positive_fragments=[
                "A vintage retro poster illustration: {concept}.",
                "Mid-century modern aesthetic, limited color palette, screen-print texture.",
                "Bold geometric shapes, grain overlay, nostalgic warm tones.",
            ],
            negative_fragment="photorealistic, photograph, 3d render, anime, hyper-detailed",
            description="Vintage mid-century poster with screen-print texture",
        ),
        "social_graphic": StylePreset(
            name="social_graphic",
            positive_fragments=[
                "Clean modern B2B SaaS background graphic, zero text: {concept}.",
                "Flat minimalist design, strong visual hierarchy, high contrast, "
                "abstract geometric composition (shapes, gradients, flowing curves).",
                "Modern tech-startup aesthetic, no people or stock photography, "
                "data-viz-forward, professional palette of deep navy, electric blue, "
                "teal, white. CRITICAL: the image has NO text, NO letters, NO words, "
                "NO logos, NO typography of any kind — text is overlaid later.",
            ],
            negative_fragment=(
                "text, letters, words, typography, captions, labels, signs, "
                "logos, watermarks, writing, handwriting, numbers, "
                "cinematic photograph, film grain, golden hour, warm tones, "
                "people, faces, hands, stock photo, generic office, monitors, "
                "keyboard, coffee cup, 3d render, cgi, cluttered, busy composition, "
                "cartoon characters, mascots, childish shapes"
            ),
            description="Clean modern B2B SaaS background graphic — flat, minimal, no text, no people",
        ),
    }

    for preset in builtins.values():
        registry.register(preset)

    return registry
