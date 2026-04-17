"""Shared pytest fixtures for the flyer_generator test suite."""

from pathlib import Path

import pytest
from PIL import Image


@pytest.fixture()
def sample_1080x1920_png(tmp_path: Path) -> Path:
    """Generate a minimal 1080x1920 solid-color PNG for composition tests."""
    img = Image.new("RGB", (1080, 1920), color="blue")
    path = tmp_path / "sample_1080x1920.png"
    img.save(path, format="PNG")
    return path
