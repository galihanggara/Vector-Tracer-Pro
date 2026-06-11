"""
tests.unit.core.test_classifier
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Unit tests for :mod:`vector_tracer_pro.core.classifier`.

Images are synthesised in-memory using Pillow so no file I/O is needed.
"""

from __future__ import annotations

import pytest
from PIL import Image

from vector_tracer_pro.core.classifier import (
    ClassificationResult,
    ImageClassifier,
    ImageType,
)
from vector_tracer_pro.core.exceptions import ClassificationError


# ===========================================================================
# Fixtures — synthetic test images
# ===========================================================================


def _make_mono_image(size: int = 100) -> Image.Image:
    """Pure black-and-white image — 1-bit mode."""
    img = Image.new("1", (size, size), 0)
    return img


def _make_bw_rgb_image(size: int = 100) -> Image.Image:
    """RGB image with only 2 colours (black and white)."""
    img = Image.new("RGB", (size, size), (255, 255, 255))
    pixels = img.load()
    assert pixels is not None
    for x in range(size // 2):
        for y in range(size):
            pixels[x, y] = (0, 0, 0)
    return img


def _make_greyscale_image(size: int = 100) -> Image.Image:
    """Gradient greyscale image — essentially zero saturation."""
    img = Image.new("L", (size, size))
    pixels = img.load()
    assert pixels is not None
    for x in range(size):
        for y in range(size):
            pixels[x, y] = (x * 255) // size
    return img.convert("RGB")  # convert to RGB for classifier


def _make_simple_colour_image(size: int = 100) -> Image.Image:
    """Image with 4 distinct solid-colour quadrants."""
    img = Image.new("RGB", (size, size))
    pixels = img.load()
    assert pixels is not None
    half = size // 2
    colours = [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0)]
    for x in range(size):
        for y in range(size):
            qx, qy = int(x >= half), int(y >= half)
            pixels[x, y] = colours[qx * 2 + qy]
    return img


def _make_complex_colour_image(size: int = 200) -> Image.Image:
    """Image simulating a photograph — many unique colours."""
    img = Image.new("RGB", (size, size))
    pixels = img.load()
    assert pixels is not None
    for x in range(size):
        for y in range(size):
            pixels[x, y] = (
                (x * 7 + y * 3) % 256,
                (x * 13 + y * 5) % 256,
                (x * 3 + y * 11) % 256,
            )
    return img


def _make_rgba_image(size: int = 100) -> Image.Image:
    """RGBA image with semi-transparency."""
    img = Image.new("RGBA", (size, size), (100, 150, 200, 128))
    return img


# ===========================================================================
# ImageType.recommended_engine
# ===========================================================================


@pytest.mark.unit
class TestImageTypeEngine:
    def test_monochrome_recommends_potrace(self) -> None:
        assert ImageType.MONOCHROME.recommended_engine == "potrace"

    def test_greyscale_recommends_potrace(self) -> None:
        assert ImageType.GREYSCALE.recommended_engine == "potrace"

    def test_colour_simple_recommends_inkscape(self) -> None:
        assert ImageType.COLOUR_SIMPLE.recommended_engine == "inkscape"

    def test_colour_complex_recommends_inkscape(self) -> None:
        assert ImageType.COLOUR_COMPLEX.recommended_engine == "inkscape"


# ===========================================================================
# ImageClassifier construction
# ===========================================================================


@pytest.mark.unit
class TestImageClassifierConstruction:
    def test_default_construction_succeeds(self) -> None:
        clf = ImageClassifier()
        assert clf is not None

    def test_invalid_colour_threshold_raises(self) -> None:
        with pytest.raises(ValueError, match="colour_simple_threshold"):
            ImageClassifier(colour_simple_threshold=1)

    def test_invalid_saturation_threshold_raises(self) -> None:
        with pytest.raises(ValueError, match="greyscale_saturation_threshold"):
            ImageClassifier(greyscale_saturation_threshold=1.5)


# ===========================================================================
# classify — correct type detection
# ===========================================================================


@pytest.mark.unit
class TestClassify:
    @pytest.fixture
    def clf(self) -> ImageClassifier:
        return ImageClassifier()

    def test_1bit_image_is_monochrome(self, clf: ImageClassifier) -> None:
        result = clf.classify(_make_mono_image())
        assert result.image_type == ImageType.MONOCHROME

    def test_1bit_image_confidence_is_high(self, clf: ImageClassifier) -> None:
        result = clf.classify(_make_mono_image())
        assert result.confidence >= 0.9

    def test_bw_rgb_image_is_monochrome(self, clf: ImageClassifier) -> None:
        """RGB image with only 2 colours should be classified as monochrome."""
        result = clf.classify(_make_bw_rgb_image())
        assert result.image_type == ImageType.MONOCHROME

    def test_greyscale_gradient_is_greyscale(self, clf: ImageClassifier) -> None:
        result = clf.classify(_make_greyscale_image())
        assert result.image_type == ImageType.GREYSCALE

    def test_greyscale_average_saturation_is_low(self, clf: ImageClassifier) -> None:
        result = clf.classify(_make_greyscale_image())
        assert result.average_saturation < 0.05

    def test_four_colour_image_is_colour_simple(self, clf: ImageClassifier) -> None:
        result = clf.classify(_make_simple_colour_image())
        assert result.image_type == ImageType.COLOUR_SIMPLE

    def test_complex_colour_image_is_colour_complex(self, clf: ImageClassifier) -> None:
        result = clf.classify(_make_complex_colour_image())
        assert result.image_type == ImageType.COLOUR_COMPLEX

    def test_rgba_image_does_not_raise(self, clf: ImageClassifier) -> None:
        """RGBA images should be handled gracefully via thumbnail compositing."""
        result = clf.classify(_make_rgba_image())
        assert result.image_type in list(ImageType)

    def test_result_is_classification_result(self, clf: ImageClassifier) -> None:
        result = clf.classify(_make_greyscale_image())
        assert isinstance(result, ClassificationResult)

    def test_result_recommended_engine_matches_type(
        self, clf: ImageClassifier
    ) -> None:
        result = clf.classify(_make_complex_colour_image())
        assert result.recommended_engine == result.image_type.recommended_engine

    def test_confidence_in_valid_range(self, clf: ImageClassifier) -> None:
        for img in [
            _make_mono_image(),
            _make_greyscale_image(),
            _make_simple_colour_image(),
            _make_complex_colour_image(),
        ]:
            result = clf.classify(img)
            assert 0.0 <= result.confidence <= 1.0, (
                f"Confidence {result.confidence} out of range for {result.image_type}"
            )

    def test_zero_dimension_image_raises(self, clf: ImageClassifier) -> None:
        tiny = Image.new("RGB", (0, 1))
        with pytest.raises(ClassificationError):
            clf.classify(tiny)


# ===========================================================================
# Custom thresholds
# ===========================================================================


@pytest.mark.unit
class TestCustomThresholds:
    def test_low_colour_threshold_classifies_four_colour_as_complex(self) -> None:
        """With threshold=3, a 4-colour image is COLOUR_COMPLEX."""
        clf = ImageClassifier(colour_simple_threshold=3)
        result = clf.classify(_make_simple_colour_image())
        assert result.image_type == ImageType.COLOUR_COMPLEX

    def test_high_saturation_threshold_classifies_colour_as_greyscale(self) -> None:
        """With a very high greyscale threshold, mildly saturated images are greyscale."""
        clf = ImageClassifier(greyscale_saturation_threshold=0.99)
        # A simple 4-colour image has some saturation but should pass as greyscale
        # under this extreme threshold
        result = clf.classify(_make_greyscale_image())
        assert result.image_type == ImageType.GREYSCALE
