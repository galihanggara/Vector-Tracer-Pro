"""
tests.unit.core.image.test_classifier
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Unit tests for the NumPy-based ImageClassifier.
"""

from __future__ import annotations

from pathlib import Path
import pytest
import numpy as np

from vector_tracer_pro.core.image.loader import ImageLoader, ImageData, ImageMetadata
from vector_tracer_pro.core.image.classifier import ImageCategory, ImageClassifier


@pytest.fixture
def fixtures_dir() -> Path:
    return Path(r"c:\Users\ASUS\Documents\Vector Tracer Pro\tests\fixtures\images")


@pytest.fixture
def loader() -> ImageLoader:
    return ImageLoader()


@pytest.fixture
def classifier() -> ImageClassifier:
    return ImageClassifier()


def test_classify_line_art(loader: ImageLoader, classifier: ImageClassifier, fixtures_dir: Path):
    img_data = loader.load(fixtures_dir / "line_art.png")
    category = classifier.classify(img_data)
    assert category == ImageCategory.LINE_ART


def test_classify_flat_vector(loader: ImageLoader, classifier: ImageClassifier, fixtures_dir: Path):
    img_data = loader.load(fixtures_dir / "flat_vector.png")
    category = classifier.classify(img_data)
    assert category == ImageCategory.FLAT_VECTOR


def test_classify_photo(loader: ImageLoader, classifier: ImageClassifier, fixtures_dir: Path):
    img_data = loader.load(fixtures_dir / "photo.png")
    category = classifier.classify(img_data)
    assert category == ImageCategory.PHOTO


def test_classify_logo(loader: ImageLoader, classifier: ImageClassifier, fixtures_dir: Path):
    img_data = loader.load(fixtures_dir / "logo.png")
    category = classifier.classify(img_data)
    assert category == ImageCategory.LOGO


def test_classify_grayscale(loader: ImageLoader, classifier: ImageClassifier, fixtures_dir: Path):
    # Grayscale has 1 unique color (solid gray 128) -> flatness is <= 64, edge density is 0.
    # So it should be FLAT_VECTOR.
    img_data = loader.load(fixtures_dir / "valid_grayscale.png")
    category = classifier.classify(img_data)
    assert isinstance(category, ImageCategory)
    assert category == ImageCategory.FLAT_VECTOR


def test_classify_rgba_input(classifier: ImageClassifier):
    # Create fake RGBA ImageData (shape H, W, 4)
    data = np.ones((100, 100, 4), dtype=np.float32)
    # Set RGB to green, Alpha to 0.5
    data[:, :, 0] = 0.0
    data[:, :, 1] = 1.0
    data[:, :, 2] = 0.0
    data[:, :, 3] = 0.5
    
    metadata = ImageMetadata(width=100, height=100, dpi=(72.0, 72.0), bit_depth=8, original_mode="RGBA")
    img_data = ImageData(data=data, metadata=metadata)
    
    # Classify should strip alpha and classify as FLAT_VECTOR (1 unique color: green)
    category = classifier.classify(img_data)
    assert category == ImageCategory.FLAT_VECTOR


def test_classify_one_pixel_image(classifier: ImageClassifier):
    # 1x1 pixel image
    data = np.zeros((1, 1, 3), dtype=np.float32)
    metadata = ImageMetadata(width=1, height=1, dpi=(72.0, 72.0), bit_depth=8, original_mode="RGB")
    img_data = ImageData(data=data, metadata=metadata)
    
    category = classifier.classify(img_data)
    # Should not crash, returns FLAT_VECTOR
    assert category == ImageCategory.FLAT_VECTOR
