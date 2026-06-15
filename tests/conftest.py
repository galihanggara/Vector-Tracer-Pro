"""
Pytest configuration and shared fixtures for Vector Tracer Pro.

Fixture scopes:
  - ``tmp_path`` (built-in): per-test temporary directories
  - ``sample_jpg``: a small valid JPEG for unit tests (no external deps)
  - ``sample_png``: a small valid PNG for unit tests (no external deps)
  - ``app_config``: default AppConfig instance
"""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from vector_tracer_pro.config.schema import AppConfig

# ---------------------------------------------------------------------------
# Sample image fixtures (generated in-memory — no file I/O dependency)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def sample_jpg(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A 200x200 RGB JPEG saved to a session-scoped temporary directory."""
    p = tmp_path_factory.mktemp("fixtures") / "sample.jpg"
    img = Image.new("RGB", (200, 200), color=(120, 80, 200))
    img.save(p, format="JPEG", quality=90)
    return p


@pytest.fixture(scope="session")
def sample_png(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A 200x200 RGBA PNG saved to a session-scoped temporary directory."""
    p = tmp_path_factory.mktemp("fixtures") / "sample.png"
    img = Image.new("RGBA", (200, 200), color=(60, 180, 120, 255))
    img.save(p, format="PNG")
    return p


@pytest.fixture(scope="session")
def sample_mono_png(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A 200x200 black-and-white PNG for Potrace engine tests."""
    p = tmp_path_factory.mktemp("fixtures") / "sample_mono.png"
    img = Image.new("L", (200, 200), color=255)
    # Draw a simple black rectangle
    pixels = img.load()
    assert pixels is not None
    for x in range(50, 150):
        for y in range(50, 150):
            pixels[x, y] = 0
    img.save(p, format="PNG")
    return p


# ---------------------------------------------------------------------------
# Config fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def app_config() -> AppConfig:
    """Default AppConfig with all default values (no file I/O)."""
    return AppConfig()
