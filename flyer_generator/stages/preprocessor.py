"""ImagePreprocessor — upscales raw ComfyCloud output to a configurable final resolution.

Phase 24-02: `ImagePreprocessor` accepts an optional ``final_dimensions``
constructor kwarg so the poster pipeline can upscale to larger canvases
(5400×7200, 7200×10800, 8100×12000) while the existing flyer pipeline
keeps the (1080, 1920) default — preserving byte-identical behavior for
the no-arg call site (``ImagePreprocessor()``).
"""

from __future__ import annotations

import io

from PIL import Image

from flyer_generator.models import ComfyJob, GeneratedBackground


class ImagePreprocessor:
    """Upscales raw PNG bytes to a configurable final resolution via LANCZOS."""

    SOURCE_DIMENSIONS = (832, 1472)
    # Class-level default kept for backwards-compat introspection. The actual
    # upscale target lives on the instance (``self._final_dimensions``).
    FINAL_DIMENSIONS = (1080, 1920)

    def __init__(
        self, final_dimensions: tuple[int, int] = (1080, 1920)
    ) -> None:
        """Construct an ImagePreprocessor that upscales to ``final_dimensions``.

        Args:
            final_dimensions: ``(width, height)`` for the upscaled output.
                Defaults to ``(1080, 1920)`` — the flyer canvas — preserving
                Phase 1–23 byte-identical behavior for the no-arg call site.
        """
        self._final_dimensions = final_dimensions

    def upscale(self, raw_bytes: bytes, comfy_job: ComfyJob) -> GeneratedBackground:
        """Upscale raw PNG bytes to ``self._final_dimensions`` via LANCZOS.

        Args:
            raw_bytes: Raw PNG image bytes (typically 832×1472 from ComfyCloud).
            comfy_job: The ComfyJob metadata associated with this image.

        Returns:
            GeneratedBackground with upscaled image bytes and dimension metadata.
        """
        img = Image.open(io.BytesIO(raw_bytes))
        source_dimensions = img.size  # (width, height)

        resized = img.resize(self._final_dimensions, Image.Resampling.LANCZOS)

        buf = io.BytesIO()
        resized.save(buf, format="PNG")

        return GeneratedBackground(
            image_bytes=buf.getvalue(),
            source_dimensions=source_dimensions,
            final_dimensions=self._final_dimensions,
            comfy_job=comfy_job,
        )
