"""
tests.unit.core.image.test_bitmapper
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Unit tests for the NumPy-based Bitmapper.
"""

from __future__ import annotations

from pathlib import Path
import pytest
import numpy as np
from PIL import Image

from vector_tracer_pro.core.image.loader import ImageMetadata
from vector_tracer_pro.core.image.classifier import ImageCategory
from vector_tracer_pro.core.image.preprocessor import Preprocessor, ProcessedImage, PreprocessConfig
from vector_tracer_pro.core.image.bitmapper import Bitmapper, BitmapFormat, BitmapFile


@pytest.fixture
def bitmapper() -> Bitmapper:
    return Bitmapper()


def test_write_pbm_from_line_art(bitmapper: Bitmapper):
    # Create a simple 10x10 binary image (L mode, shape (H,W))
    data = np.ones((10, 10), dtype=np.float32)
    data[2:8, 2:8] = 0.0  # draw a black square inside
    
    meta = ImageMetadata(width=10, height=10, dpi=(72.0, 72.0), bit_depth=1, original_mode="L")
    processed = ProcessedImage(
        data=data,
        metadata=meta,
        category=ImageCategory.LINE_ART,
        config=PreprocessConfig(),
        applied_steps=["grayscale", "threshold"]
    )
    
    with bitmapper.write(processed, BitmapFormat.PBM) as bitmap:
        assert isinstance(bitmap, BitmapFile)
        assert bitmap.path.exists()
        assert bitmap.format == BitmapFormat.PBM
        assert bitmap.source_category == ImageCategory.LINE_ART
        
        # Verify content
        content = bitmap.path.read_bytes()
        assert content.startswith(b"P4\n10 10\n")
        
        # Header size: len("P4\n10 10\n") = 9
        # Body size: height * ((width + 7) // 8) = 10 * ((10 + 7) // 8) = 10 * 2 = 20 bytes
        assert len(content) == 9 + 20
        
    # Verify cleanup on exit
    assert not bitmap.path.exists()


def test_write_png_from_flat_vector(bitmapper: Bitmapper):
    # Shape (10, 10, 3) RGB
    data = np.zeros((10, 10, 3), dtype=np.float32)
    data[2:8, 2:8, 0] = 1.0  # red square
    
    meta = ImageMetadata(width=10, height=10, dpi=(72.0, 72.0), bit_depth=8, original_mode="RGB")
    processed = ProcessedImage(
        data=data,
        metadata=meta,
        category=ImageCategory.FLAT_VECTOR,
        config=PreprocessConfig(),
        applied_steps=["quantize"]
    )
    
    with bitmapper.write(processed, BitmapFormat.PNG) as bitmap:
        assert bitmap.path.exists()
        assert bitmap.format == BitmapFormat.PNG
        
        # Verify Pillow can open it and it is RGB
        with Image.open(bitmap.path) as img:
            assert img.mode == "RGB"
            assert img.size == (10, 10)
            
    assert not bitmap.path.exists()


def test_write_png_from_line_art_2d(bitmapper: Bitmapper):
    # Shape (10, 10) grayscale
    data = np.ones((10, 10), dtype=np.float32)
    
    meta = ImageMetadata(width=10, height=10, dpi=(72.0, 72.0), bit_depth=8, original_mode="L")
    processed = ProcessedImage(
        data=data,
        metadata=meta,
        category=ImageCategory.LINE_ART,
        config=PreprocessConfig(),
        applied_steps=["grayscale"]
    )
    
    with bitmapper.write(processed, BitmapFormat.PNG) as bitmap:
        assert bitmap.path.exists()
        with Image.open(bitmap.path) as img:
            assert img.mode == "L"
            
    assert not bitmap.path.exists()


def test_cleanup_on_exception(bitmapper: Bitmapper):
    data = np.ones((10, 10), dtype=np.float32)
    meta = ImageMetadata(width=10, height=10, dpi=(72.0, 72.0), bit_depth=1, original_mode="L")
    processed = ProcessedImage(
        data=data,
        metadata=meta,
        category=ImageCategory.LINE_ART,
        config=PreprocessConfig()
    )
    
    temp_path = None
    with pytest.raises(RuntimeError):
        with bitmapper.write(processed, BitmapFormat.PBM) as bitmap:
            temp_path = bitmap.path
            assert temp_path.exists()
            raise RuntimeError("Failure inside with block")
            
    # Verify cleanup runs even when an exception is raised inside the context block
    assert temp_path is not None
    assert not temp_path.exists()


def test_validation_errors(bitmapper: Bitmapper):
    meta = ImageMetadata(width=10, height=10, dpi=(72.0, 72.0), bit_depth=8, original_mode="RGB")
    
    # 1. PBM from 3D array (H, W, 3) -> should raise ValueError
    data_3d = np.ones((10, 10, 3), dtype=np.float32)
    p_3d = ProcessedImage(data=data_3d, metadata=meta, category=ImageCategory.LINE_ART, config=PreprocessConfig())
    with pytest.raises(ValueError) as exc:
        with bitmapper.write(p_3d, BitmapFormat.PBM):
            pass
    assert "supports 2D binary images" in str(exc.value)
    
    # 2. Data not float32 -> should raise ValueError
    data_u8 = np.ones((10, 10), dtype=np.uint8)
    p_u8 = ProcessedImage(data=data_u8, metadata=meta, category=ImageCategory.LINE_ART, config=PreprocessConfig())  # type: ignore
    with pytest.raises(ValueError) as exc:
        with bitmapper.write(p_u8, BitmapFormat.PBM):
            pass
    assert "must be float32 array" in str(exc.value)
    
    # 3. Empty or zero-dimension array -> should raise ValueError
    data_empty = np.zeros((0, 10), dtype=np.float32)
    p_empty = ProcessedImage(data=data_empty, metadata=meta, category=ImageCategory.LINE_ART, config=PreprocessConfig())
    with pytest.raises(ValueError) as exc:
        with bitmapper.write(p_empty, BitmapFormat.PBM):
            pass
    assert "dimensions cannot be zero" in str(exc.value)
