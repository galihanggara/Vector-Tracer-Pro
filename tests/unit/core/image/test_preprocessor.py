"""
tests.unit.core.image.test_preprocessor
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Unit tests for the new NumPy-based Preprocessor.
"""

from __future__ import annotations

from pathlib import Path
import pytest
import numpy as np

from vector_tracer_pro.core.image.loader import ImageLoader, ImageData, ImageMetadata
from vector_tracer_pro.core.image.classifier import ImageCategory
from vector_tracer_pro.core.image.preprocessor import Preprocessor, PreprocessConfig, ProcessedImage


@pytest.fixture
def fixtures_dir() -> Path:
    return Path(r"c:\Users\ASUS\Documents\Vector Tracer Pro\tests\fixtures\images")


@pytest.fixture
def loader() -> ImageLoader:
    return ImageLoader()


@pytest.fixture
def preprocessor() -> Preprocessor:
    return Preprocessor()


def test_preprocess_line_art(loader: ImageLoader, preprocessor: Preprocessor, fixtures_dir: Path):
    img_data = loader.load(fixtures_dir / "line_art.png")
    
    # Process LINE_ART
    res = preprocessor.process(img_data, ImageCategory.LINE_ART)
    
    assert isinstance(res, ProcessedImage)
    assert res.data.ndim == 2  # shape (H, W)
    assert res.data.shape == (200, 200)
    # Check that values are strictly 0.0 or 1.0
    assert np.all((res.data == 0.0) | (res.data == 1.0))
    assert "grayscale" in res.applied_steps
    assert "otsu_threshold" in res.applied_steps
    assert "denoise" in res.applied_steps
    assert res.category == ImageCategory.LINE_ART


def test_preprocess_flat_vector(loader: ImageLoader, preprocessor: Preprocessor, fixtures_dir: Path):
    img_data = loader.load(fixtures_dir / "flat_vector.png")
    
    # Process FLAT_VECTOR with skip_denoise=True so smooth average filter doesn't introduce extra colors
    config = PreprocessConfig(quantize_k=8, skip_denoise=True)
    res = preprocessor.process(img_data, ImageCategory.FLAT_VECTOR, config)
    
    assert res.data.ndim == 3  # shape (H, W, 3)
    assert res.data.shape == (200, 200, 3)
    
    # Check unique colors count is <= k
    flat_data = res.data.reshape(-1, 3)
    flat_u8 = (flat_data * 255.0 + 0.5).astype(np.uint8)
    unique_colors = len(np.unique(flat_u8, axis=0))
    assert unique_colors <= 8
    
    assert "quantize" in res.applied_steps
    assert "smooth" not in res.applied_steps


def test_preprocess_photo_resize_large(preprocessor: Preprocessor):
    # Construct a large image of size 3000x1500 (height x width)
    large_data = np.random.rand(3000, 1500, 3).astype(np.float32)
    meta = ImageMetadata(width=1500, height=3000, dpi=(72.0, 72.0), bit_depth=8, original_mode="RGB")
    img_data = ImageData(data=large_data, metadata=meta)
    
    res = preprocessor.process(img_data, ImageCategory.PHOTO)
    
    # Max dimension is 2000, aspect ratio should be kept (longest edge = height = 2000, width = 1000)
    assert res.data.shape == (2000, 1000, 3)
    assert "resize" in res.applied_steps
    assert "enhance_contrast" in res.applied_steps


def test_preprocess_photo_no_resize_small(loader: ImageLoader, preprocessor: Preprocessor, fixtures_dir: Path):
    img_data = loader.load(fixtures_dir / "photo.png")  # 200x200
    res = preprocessor.process(img_data, ImageCategory.PHOTO)
    
    # Should not resize
    assert res.data.shape == (200, 200, 3)
    assert "resize" not in res.applied_steps
    assert "enhance_contrast" in res.applied_steps


def test_preprocess_skip_steps(loader: ImageLoader, preprocessor: Preprocessor, fixtures_dir: Path):
    img_data = loader.load(fixtures_dir / "line_art.png")
    
    config = PreprocessConfig(skip_denoise=True, skip_threshold=True)
    res = preprocessor.process(img_data, ImageCategory.LINE_ART, config)
    
    # Greyscale is applied, but denoise and threshold are skipped
    assert "grayscale" in res.applied_steps
    assert "otsu_threshold" not in res.applied_steps
    assert "denoise" not in res.applied_steps


def test_preprocess_logo(loader: ImageLoader, preprocessor: Preprocessor, fixtures_dir: Path):
    img_data = loader.load(fixtures_dir / "logo.png")
    res = preprocessor.process(img_data, ImageCategory.LOGO)
    
    assert res.data.ndim == 2
    assert res.data.shape == (200, 200)
    assert np.all((res.data == 0.0) | (res.data == 1.0))
    assert "grayscale" in res.applied_steps
    assert "sharpen" in res.applied_steps
    assert "otsu_threshold" in res.applied_steps


def test_preprocess_default_config_all_categories(loader: ImageLoader, preprocessor: Preprocessor, fixtures_dir: Path):
    # Verify no crash for any category with config=None
    img_data = loader.load(fixtures_dir / "valid_rgb.jpg")
    
    for category in ImageCategory:
        res = preprocessor.process(img_data, category, config=None)
        assert isinstance(res, ProcessedImage)
        if category in (ImageCategory.LINE_ART, ImageCategory.LOGO):
            assert res.data.ndim == 2
        else:
            assert res.data.ndim == 3
