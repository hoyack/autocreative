"""ImagePreprocessor — upscales raw ComfyCloud output to final resolution."""

from __future__ import annotations

import io

from PIL import Image

from flyer_generator.models import ComfyJob, GeneratedBackground


class ImagePreprocessor:
    """Upscales raw 832x1472 PNG bytes to 1080x1920 final resolution."""

    SOURCE_DIMENSIONS = (832, 1472)
    FINAL_DIMENSIONS = (1080, 1920)

    def upscale(self, raw_bytes: bytes, comfy_job: ComfyJob) -> GeneratedBackground:
        """Upscale raw PNG bytes to final dimensions using LANCZOS resampling.

        Args:
            raw_bytes: Raw PNG image bytes (typically 832x1472 from ComfyCloud).
            comfy_job: The ComfyJob metadata associated with this image.

        Returns:
            GeneratedBackground with upscaled image bytes and dimension metadata.
        """
        img = Image.open(io.BytesIO(raw_bytes))
        source_dimensions = img.size  # (width, height)

        resized = img.resize(self.FINAL_DIMENSIONS, Image.Resampling.LANCZOS)

        buf = io.BytesIO()
        resized.save(buf, format="PNG")

        return GeneratedBackground(
            image_bytes=buf.getvalue(),
            source_dimensions=source_dimensions,
            final_dimensions=self.FINAL_DIMENSIONS,
            comfy_job=comfy_job,
        )
