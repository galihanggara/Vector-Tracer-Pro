"""
tests.unit.core.image.test_loader
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Unit tests for the new NumPy-based ImageLoader.
"""

from __future__ import annotations

from pathlib import Path
import pytest
import numpy as np

from vector_tracer_pro.core.exceptions import (
    CorruptImageError,
    ImageSizeError,
    UnsupportedFormatError,
)
from vector_tracer_pro.core.image.loader import ImageLoader, ImageData


@pytest.fixture
def fixtures_dir() -> Path:
    return Path(r"c:\Users\ASUS\Documents\Vector Tracer Pro\tests\fixtures\images")


@pytest.fixture
def loader() -> ImageLoader:
    return ImageLoader(min_width=32, min_height=32, max_width=10000, max_height=10000)


def test_load_valid_rgb(loader: ImageLoader, fixtures_dir: Path):
    path = fixtures_dir / "valid_rgb.jpg"
    res = loader.load(path)
    
    assert isinstance(res, ImageData)
    assert isinstance(res.data, np.ndarray)
    assert res.data.dtype == np.float32
    assert res.data.shape == (200, 200, 3)
    assert np.all(res.data >= 0.0) and np.all(res.data <= 1.0)
    
    meta = res.metadata
    assert meta.width == 200
    assert meta.height == 200
    assert isinstance(meta.dpi, tuple)
    assert len(meta.dpi) == 2
    assert meta.bit_depth == 8
    assert meta.original_mode == "RGB"


def test_load_valid_rgba(loader: ImageLoader, fixtures_dir: Path):
    path = fixtures_dir / "valid_rgba.png"
    res = loader.load(path)
    
    assert res.data.shape == (200, 200, 3)  # always RGB
    assert res.metadata.original_mode == "RGBA"
    assert res.metadata.bit_depth == 8


def test_load_valid_grayscale(loader: ImageLoader, fixtures_dir: Path):
    path = fixtures_dir / "valid_grayscale.png"
    res = loader.load(path)
    
    assert res.data.shape == (200, 200, 3)  # always RGB
    assert res.metadata.original_mode == "L"
    assert res.metadata.bit_depth == 8


def test_load_corrupt(loader: ImageLoader, fixtures_dir: Path):
    path = fixtures_dir / "corrupt.jpg"
    with pytest.raises(CorruptImageError):
        loader.load(path)


def test_load_too_small(loader: ImageLoader, fixtures_dir: Path):
    path = fixtures_dir / "too_small.png"
    with pytest.raises(ImageSizeError) as exc_info:
        loader.load(path)
    
    exc = exc_info.value
    assert exc.width == 4
    assert exc.height == 4
    assert exc.min_width == 32
    assert exc.min_height == 32


def test_load_too_large(fixtures_dir: Path):
    # Setup custom loader with small max dims to trigger too large validation
    strict_loader = ImageLoader(max_width=100, max_height=100)
    path = fixtures_dir / "valid_rgb.jpg"
    with pytest.raises(ImageSizeError) as exc_info:
        strict_loader.load(path)
    
    exc = exc_info.value
    assert exc.width == 200
    assert exc.height == 200
    assert exc.max_width == 100
    assert exc.max_height == 100


def test_load_file_not_found(loader: ImageLoader, tmp_path: Path):
    missing_path = tmp_path / "nonexistent.png"
    with pytest.raises(FileNotFoundError):
        loader.load(missing_path)


def test_load_unsupported_format(loader: ImageLoader, tmp_path: Path):
    unsupported_path = tmp_path / "test.txt"
    unsupported_path.write_text("Not an image")
    with pytest.raises(UnsupportedFormatError) as exc_info:
        loader.load(unsupported_path)
    
    assert exc_info.value.detected_format == "txt"
