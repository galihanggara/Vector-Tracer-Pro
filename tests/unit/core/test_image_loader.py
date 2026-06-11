"""
tests.unit.core.test_image_loader
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Unit tests for :mod:`vector_tracer_pro.core.image_loader`.

Uses session-scoped fixtures from ``conftest.py`` for valid images and
creates malformed/unsupported files on-the-fly inside ``tmp_path``.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from vector_tracer_pro.core.exceptions import (
    ImageLoadError,
    ImageTooSmallError,
    UnsupportedFormatError,
)
from vector_tracer_pro.core.image_loader import ImageLoader, ImageMetadata, LoadedImage


# ===========================================================================
# Fixtures
# ===========================================================================


@pytest.fixture(scope="session")
def large_jpg(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """1000×800 RGB JPEG — passes all validation."""
    p = tmp_path_factory.mktemp("loader") / "large.jpg"
    Image.new("RGB", (1000, 800), color=(200, 100, 50)).save(p, format="JPEG")
    return p


@pytest.fixture(scope="session")
def large_png(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """1000×800 RGBA PNG — passes all validation."""
    p = tmp_path_factory.mktemp("loader") / "large.png"
    Image.new("RGBA", (1000, 800), color=(50, 100, 200, 255)).save(p, format="PNG")
    return p


@pytest.fixture(scope="session")
def tiny_jpg(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """50×50 JPEG — too small to pass the minimum dimension check."""
    p = tmp_path_factory.mktemp("loader") / "tiny.jpg"
    Image.new("RGB", (50, 50)).save(p, format="JPEG")
    return p


@pytest.fixture(scope="session")
def bmp_file(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """BMP file — unsupported format."""
    p = tmp_path_factory.mktemp("loader") / "image.bmp"
    Image.new("RGB", (1000, 800)).save(p, format="BMP")
    return p


@pytest.fixture(scope="session")
def corrupt_file(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A file with random bytes — not a real image."""
    p = tmp_path_factory.mktemp("loader") / "corrupt.jpg"
    p.write_bytes(b"\xff\xfe\x00\x01\x02\x03\x04\x05" * 64)
    return p


@pytest.fixture
def loader() -> ImageLoader:
    """ImageLoader with default settings (min 500×500)."""
    return ImageLoader(min_width_px=500, min_height_px=500)


# ===========================================================================
# Successful loading
# ===========================================================================


@pytest.mark.unit
class TestImageLoaderSuccess:
    def test_load_jpeg_returns_loaded_image(
        self, loader: ImageLoader, large_jpg: Path
    ) -> None:
        result = loader.load(large_jpg)
        assert isinstance(result, LoadedImage)

    def test_load_png_returns_loaded_image(
        self, loader: ImageLoader, large_png: Path
    ) -> None:
        result = loader.load(large_png)
        assert isinstance(result, LoadedImage)

    def test_jpeg_metadata_format_is_jpeg(
        self, loader: ImageLoader, large_jpg: Path
    ) -> None:
        result = loader.load(large_jpg)
        assert result.metadata.original_format == "JPEG"

    def test_png_metadata_format_is_png(
        self, loader: ImageLoader, large_png: Path
    ) -> None:
        result = loader.load(large_png)
        assert result.metadata.original_format == "PNG"

    def test_metadata_dimensions_match_actual(
        self, loader: ImageLoader, large_jpg: Path
    ) -> None:
        result = loader.load(large_jpg)
        assert result.metadata.width == 1000
        assert result.metadata.height == 800

    def test_metadata_path_is_absolute(
        self, loader: ImageLoader, large_jpg: Path
    ) -> None:
        result = loader.load(large_jpg)
        assert result.metadata.path.is_absolute()

    def test_metadata_file_size_positive(
        self, loader: ImageLoader, large_jpg: Path
    ) -> None:
        result = loader.load(large_jpg)
        assert result.metadata.file_size_bytes > 0

    def test_png_rgba_has_transparency(
        self, loader: ImageLoader, large_png: Path
    ) -> None:
        result = loader.load(large_png)
        assert result.metadata.has_transparency is True

    def test_jpeg_rgb_no_transparency(
        self, loader: ImageLoader, large_jpg: Path
    ) -> None:
        result = loader.load(large_jpg)
        assert result.metadata.has_transparency is False

    def test_image_object_is_pil_image(
        self, loader: ImageLoader, large_jpg: Path
    ) -> None:
        result = loader.load(large_jpg)
        assert isinstance(result.image, Image.Image)

    def test_load_does_not_mutate_original(
        self, loader: ImageLoader, large_jpg: Path
    ) -> None:
        """Loading should not close or alter the image on disk."""
        size_before = large_jpg.stat().st_size
        loader.load(large_jpg)
        size_after = large_jpg.stat().st_size
        assert size_before == size_after


# ===========================================================================
# ImageMetadata computed properties
# ===========================================================================


@pytest.mark.unit
class TestImageMetadata:
    def test_megapixels_computed_correctly(
        self, loader: ImageLoader, large_jpg: Path
    ) -> None:
        result = loader.load(large_jpg)
        expected = (1000 * 800) / 1_000_000
        assert abs(result.metadata.megapixels - expected) < 0.001

    def test_aspect_ratio_computed_correctly(
        self, loader: ImageLoader, large_jpg: Path
    ) -> None:
        result = loader.load(large_jpg)
        expected = 1000 / 800
        assert abs(result.metadata.aspect_ratio - expected) < 0.01

    def test_str_representation_contains_filename(
        self, loader: ImageLoader, large_jpg: Path
    ) -> None:
        result = loader.load(large_jpg)
        assert "large.jpg" in str(result.metadata)


# ===========================================================================
# Format validation errors
# ===========================================================================


@pytest.mark.unit
class TestFormatValidation:
    def test_bmp_raises_unsupported_format_error(
        self, loader: ImageLoader, bmp_file: Path
    ) -> None:
        with pytest.raises(UnsupportedFormatError) as exc_info:
            loader.load(bmp_file)
        assert exc_info.value.detected_format == "BMP"
        assert str(bmp_file) in exc_info.value.path

    def test_corrupt_file_raises_image_load_error(
        self, loader: ImageLoader, corrupt_file: Path
    ) -> None:
        with pytest.raises(ImageLoadError):
            loader.load(corrupt_file)

    def test_nonexistent_file_raises_image_load_error(
        self, loader: ImageLoader, tmp_path: Path
    ) -> None:
        missing = tmp_path / "does_not_exist.jpg"
        with pytest.raises(ImageLoadError) as exc_info:
            loader.load(missing)
        assert str(missing) in exc_info.value.path

    def test_directory_path_raises_image_load_error(
        self, loader: ImageLoader, tmp_path: Path
    ) -> None:
        with pytest.raises(ImageLoadError):
            loader.load(tmp_path)


# ===========================================================================
# Dimension validation errors
# ===========================================================================


@pytest.mark.unit
class TestDimensionValidation:
    def test_tiny_image_raises_image_too_small_error(
        self, loader: ImageLoader, tiny_jpg: Path
    ) -> None:
        with pytest.raises(ImageTooSmallError) as exc_info:
            loader.load(tiny_jpg)
        exc = exc_info.value
        assert exc.width == 50
        assert exc.height == 50
        assert exc.min_width == 500
        assert exc.min_height == 500

    def test_custom_minimum_can_accept_small_images(
        self, tiny_jpg: Path
    ) -> None:
        """A loader with min 10×10 should accept the 50×50 image."""
        small_loader = ImageLoader(min_width_px=10, min_height_px=10)
        result = small_loader.load(tiny_jpg)
        assert result.metadata.width == 50

    def test_image_exactly_at_minimum_passes(self, tmp_path: Path) -> None:
        exactly = tmp_path / "exact.jpg"
        Image.new("RGB", (500, 500)).save(exactly, format="JPEG")
        loader = ImageLoader(min_width_px=500, min_height_px=500)
        result = loader.load(exactly)
        assert result.metadata.width == 500


# ===========================================================================
# Loader construction
# ===========================================================================


@pytest.mark.unit
class TestImageLoaderConstruction:
    def test_invalid_min_width_raises(self) -> None:
        with pytest.raises(ValueError):
            ImageLoader(min_width_px=0)

    def test_invalid_min_height_raises(self) -> None:
        with pytest.raises(ValueError):
            ImageLoader(min_height_px=-1)

    def test_custom_supported_formats(self, tmp_path: Path) -> None:
        """A loader that accepts only PNG should reject JPEG."""
        jpg = tmp_path / "test.jpg"
        Image.new("RGB", (600, 600)).save(jpg, format="JPEG")
        png_only_loader = ImageLoader(
            min_width_px=100,
            supported_formats=("PNG",),
        )
        with pytest.raises(UnsupportedFormatError):
            png_only_loader.load(jpg)
