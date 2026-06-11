"""
tests.unit.core.test_preprocessor
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Unit tests for :mod:`vector_tracer_pro.core.preprocessor`.

All images are synthesised in-memory; no file I/O is performed.
"""

from __future__ import annotations

import pytest
from PIL import Image

from vector_tracer_pro.core.classifier import ImageType
from vector_tracer_pro.core.exceptions import PreprocessingError
from vector_tracer_pro.core.preprocessor import (
    ImagePreprocessor,
    ProcessedImage,
    ProcessingStep,
)


# ===========================================================================
# Fixtures
# ===========================================================================


@pytest.fixture
def prep() -> ImagePreprocessor:
    """ImagePreprocessor with default settings."""
    return ImagePreprocessor()


@pytest.fixture
def prep_no_denoise() -> ImagePreprocessor:
    return ImagePreprocessor(denoise_radius=0)


def _rgb(w: int = 800, h: int = 600, colour: tuple[int, int, int] = (128, 64, 200)) -> Image.Image:
    return Image.new("RGB", (w, h), colour)


def _rgba(w: int = 800, h: int = 600) -> Image.Image:
    return Image.new("RGBA", (w, h), (100, 150, 200, 200))


def _greyscale(w: int = 800, h: int = 600) -> Image.Image:
    return Image.new("L", (w, h), 128)


def _large_rgb(max_dim: int = 6000) -> Image.Image:
    """Image larger than the default 4096px cap."""
    return Image.new("RGB", (max_dim, max_dim // 2), (80, 120, 160))


# ===========================================================================
# ProcessedImage properties
# ===========================================================================


@pytest.mark.unit
class TestProcessedImage:
    def test_was_resized_true_when_resize_in_steps(self) -> None:
        img = _rgb()
        pi = ProcessedImage(
            image=img,
            original_size=(800, 600),
            processed_size=(400, 300),
            steps_applied=[ProcessingStep.RESIZE, ProcessingStep.CONVERT_RGB],
        )
        assert pi.was_resized is True

    def test_was_resized_false_when_no_resize(self) -> None:
        img = _rgb()
        pi = ProcessedImage(
            image=img,
            original_size=(800, 600),
            processed_size=(800, 600),
            steps_applied=[ProcessingStep.CONVERT_RGB],
        )
        assert pi.was_resized is False

    def test_scale_factor_when_resized(self) -> None:
        img = _rgb(400, 300)
        pi = ProcessedImage(
            image=img,
            original_size=(800, 600),
            processed_size=(400, 300),
            steps_applied=[ProcessingStep.RESIZE],
        )
        assert abs(pi.scale_factor - 0.5) < 0.01


# ===========================================================================
# ImagePreprocessor — construction
# ===========================================================================


@pytest.mark.unit
class TestPreprocessorConstruction:
    def test_default_construction_succeeds(self) -> None:
        p = ImagePreprocessor()
        assert p is not None

    def test_max_dimension_too_small_raises(self) -> None:
        with pytest.raises(ValueError, match="max_dimension_px"):
            ImagePreprocessor(max_dimension_px=32)

    def test_quantise_colours_too_few_raises(self) -> None:
        with pytest.raises(ValueError, match="quantise_colours"):
            ImagePreprocessor(quantise_colours=1)

    def test_negative_denoise_radius_raises(self) -> None:
        with pytest.raises(ValueError, match="denoise_radius"):
            ImagePreprocessor(denoise_radius=-1)

    def test_blacklevel_out_of_range_raises(self) -> None:
        with pytest.raises(ValueError, match="blacklevel"):
            ImagePreprocessor(blacklevel=1.5)


# ===========================================================================
# Resize
# ===========================================================================


@pytest.mark.unit
class TestResize:
    def test_large_image_is_resized(self, prep: ImagePreprocessor) -> None:
        big = _large_rgb(6000)
        result = prep.preprocess(big, ImageType.COLOUR_COMPLEX)
        assert ProcessingStep.RESIZE in result.steps_applied
        assert max(result.processed_size) <= prep._max_dimension_px  # noqa: SLF001

    def test_small_image_is_not_resized(self, prep: ImagePreprocessor) -> None:
        small = _rgb(400, 300)
        result = prep.preprocess(small, ImageType.COLOUR_COMPLEX)
        assert ProcessingStep.RESIZE not in result.steps_applied
        assert result.processed_size == (400, 300)

    def test_resize_preserves_aspect_ratio(self, prep: ImagePreprocessor) -> None:
        wide = _rgb(8000, 2000)  # 4:1 aspect
        result = prep.preprocess(wide, ImageType.COLOUR_COMPLEX)
        w, h = result.processed_size
        aspect = w / h
        assert abs(aspect - 4.0) < 0.05

    def test_original_size_recorded_correctly(self, prep: ImagePreprocessor) -> None:
        big = _large_rgb(5000)
        result = prep.preprocess(big, ImageType.COLOUR_SIMPLE)
        assert result.original_size == (5000, 2500)


# ===========================================================================
# Alpha flattening
# ===========================================================================


@pytest.mark.unit
class TestAlphaFlatten:
    def test_rgba_image_is_flattened(self, prep: ImagePreprocessor) -> None:
        img = _rgba()
        result = prep.preprocess(img, ImageType.COLOUR_SIMPLE)
        assert ProcessingStep.FLATTEN_ALPHA in result.steps_applied
        assert result.image.mode != "RGBA"

    def test_rgb_image_is_not_flattened(self, prep: ImagePreprocessor) -> None:
        img = _rgb()
        result = prep.preprocess(img, ImageType.COLOUR_SIMPLE)
        assert ProcessingStep.FLATTEN_ALPHA not in result.steps_applied


# ===========================================================================
# Monochrome pipeline
# ===========================================================================


@pytest.mark.unit
class TestMonochromePipeline:
    def test_monochrome_includes_threshold(self, prep: ImagePreprocessor) -> None:
        result = prep.preprocess(_rgb(), ImageType.MONOCHROME)
        assert ProcessingStep.THRESHOLD in result.steps_applied

    def test_monochrome_includes_greyscale(self, prep: ImagePreprocessor) -> None:
        result = prep.preprocess(_rgb(), ImageType.MONOCHROME)
        assert ProcessingStep.CONVERT_GREYSCALE in result.steps_applied

    def test_monochrome_result_is_l_mode(self, prep: ImagePreprocessor) -> None:
        result = prep.preprocess(_rgb(), ImageType.MONOCHROME)
        assert result.image.mode == "L"

    def test_monochrome_pixels_are_binary(self, prep: ImagePreprocessor) -> None:
        """After threshold, all pixel values should be 0 or 255."""
        result = prep.preprocess(_rgb(100, 100), ImageType.MONOCHROME)
        pixels = list(result.image.get_flattened_data())
        assert all(p in (0, 255) for p in pixels), (
            f"Non-binary pixels found: {set(pixels)}"
        )


# ===========================================================================
# Greyscale pipeline
# ===========================================================================


@pytest.mark.unit
class TestGreyscalePipeline:
    def test_greyscale_does_not_include_threshold(
        self, prep: ImagePreprocessor
    ) -> None:
        result = prep.preprocess(_rgb(), ImageType.GREYSCALE)
        assert ProcessingStep.THRESHOLD not in result.steps_applied

    def test_greyscale_includes_convert_greyscale(
        self, prep: ImagePreprocessor
    ) -> None:
        result = prep.preprocess(_rgb(), ImageType.GREYSCALE)
        assert ProcessingStep.CONVERT_GREYSCALE in result.steps_applied

    def test_greyscale_result_is_l_mode(self, prep: ImagePreprocessor) -> None:
        result = prep.preprocess(_rgb(), ImageType.GREYSCALE)
        assert result.image.mode == "L"

    def test_greyscale_with_denoising_includes_denoise(
        self, prep: ImagePreprocessor
    ) -> None:
        result = prep.preprocess(_rgb(), ImageType.GREYSCALE)
        # prep has denoise_radius=1 (default), so DENOISE should be present
        assert ProcessingStep.DENOISE in result.steps_applied

    def test_greyscale_without_denoise_excludes_denoise(
        self, prep_no_denoise: ImagePreprocessor
    ) -> None:
        result = prep_no_denoise.preprocess(_rgb(), ImageType.GREYSCALE)
        assert ProcessingStep.DENOISE not in result.steps_applied


# ===========================================================================
# Colour simple pipeline
# ===========================================================================


@pytest.mark.unit
class TestColourSimplePipeline:
    def test_colour_simple_includes_quantise(self, prep: ImagePreprocessor) -> None:
        result = prep.preprocess(_rgb(), ImageType.COLOUR_SIMPLE)
        assert ProcessingStep.QUANTISE in result.steps_applied

    def test_colour_simple_result_is_rgb(self, prep: ImagePreprocessor) -> None:
        result = prep.preprocess(_rgb(), ImageType.COLOUR_SIMPLE)
        assert result.image.mode == "RGB"

    def test_colour_simple_reduces_unique_colours(
        self, prep: ImagePreprocessor
    ) -> None:
        """Quantising a gradient should produce fewer unique colours."""
        gradient = Image.new("RGB", (100, 100))
        pix = gradient.load()
        assert pix is not None
        for x in range(100):
            for y in range(100):
                pix[x, y] = (x * 2, y * 2, (x + y) % 256)

        before_count = len(set(gradient.get_flattened_data()))
        result = prep.preprocess(gradient, ImageType.COLOUR_SIMPLE)
        after_count = len(set(result.image.get_flattened_data()))
        assert after_count < before_count

    def test_colour_simple_does_not_include_denoise(
        self, prep: ImagePreprocessor
    ) -> None:
        result = prep.preprocess(_rgb(), ImageType.COLOUR_SIMPLE)
        assert ProcessingStep.DENOISE not in result.steps_applied


# ===========================================================================
# Colour complex pipeline
# ===========================================================================


@pytest.mark.unit
class TestColourComplexPipeline:
    def test_colour_complex_includes_quantise_and_denoise(
        self, prep: ImagePreprocessor
    ) -> None:
        result = prep.preprocess(_rgb(), ImageType.COLOUR_COMPLEX)
        assert ProcessingStep.QUANTISE in result.steps_applied
        assert ProcessingStep.DENOISE in result.steps_applied

    def test_colour_complex_no_denoise_when_disabled(
        self, prep_no_denoise: ImagePreprocessor
    ) -> None:
        result = prep_no_denoise.preprocess(_rgb(), ImageType.COLOUR_COMPLEX)
        assert ProcessingStep.DENOISE not in result.steps_applied

    def test_colour_complex_result_is_rgb(self, prep: ImagePreprocessor) -> None:
        result = prep.preprocess(_rgb(), ImageType.COLOUR_COMPLEX)
        assert result.image.mode == "RGB"


# ===========================================================================
# Original image not mutated
# ===========================================================================


@pytest.mark.unit
class TestImmutability:
    def test_original_image_not_mutated_rgb(self, prep: ImagePreprocessor) -> None:
        img = _rgb(800, 600)
        original_mode = img.mode
        original_size = img.size
        prep.preprocess(img, ImageType.COLOUR_COMPLEX)
        assert img.mode == original_mode
        assert img.size == original_size

    def test_original_image_not_mutated_rgba(self, prep: ImagePreprocessor) -> None:
        img = _rgba()
        original_mode = img.mode
        prep.preprocess(img, ImageType.COLOUR_SIMPLE)
        assert img.mode == original_mode
