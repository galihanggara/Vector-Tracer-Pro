"""
vector_tracer_pro.core.image_loader
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Raster image ingestion and validation.

This module is responsible for:

1. **Loading** — opening image files with Pillow and returning a
   :class:`LoadedImage` that bundles the PIL ``Image`` with rich metadata.
2. **Validating** — rejecting files that are not JPEG or PNG, that are too
   small, or that are otherwise corrupt.  All failures raise typed exceptions
   from :mod:`vector_tracer_pro.core.exceptions`.

Design principles
-----------------
* **No image mutations here** — the loader returns the image exactly as Pillow
  opened it (including original mode: ``"RGB"``, ``"RGBA"``, ``"L"``, ``"P"``,
  etc.).  Normalisation (RGB conversion, alpha flattening) is the
  preprocessor's responsibility.
* **Metadata is computed once** — width, height, format, and file size are
  captured at load time so callers never need to stat the file again.
* **Lazy pixel access** — :attr:`LoadedImage.image` holds the PIL object in
  the lazy-loaded state Pillow returns; no ``.load()`` is forced here to keep
  peak memory low for large images.

Usage
-----
::

    from pathlib import Path
    from vector_tracer_pro.core.image_loader import ImageLoader

    loader = ImageLoader()
    loaded = loader.load(Path("photo.jpg"))
    print(loaded.metadata.width, loaded.metadata.height)
    print(loaded.metadata.original_format)   # "JPEG"
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, UnidentifiedImageError

from vector_tracer_pro.config.defaults import (
    MIN_INPUT_HEIGHT_PX,
    MIN_INPUT_WIDTH_PX,
    SUPPORTED_INPUT_FORMATS,
)
from vector_tracer_pro.core.exceptions import (
    ImageLoadError,
    ImageTooSmallError,
    UnsupportedFormatError,
)

logger = logging.getLogger(__name__)


# ===========================================================================
# Data structures
# ===========================================================================


@dataclass(frozen=True)
class ImageMetadata:
    """Immutable metadata captured at image load time.

    Attributes
    ----------
    path:
        Absolute path to the source file.
    original_format:
        Pillow format string (``"JPEG"`` or ``"PNG"``).
    original_mode:
        Pillow image mode (e.g. ``"RGB"``, ``"RGBA"``, ``"L"``, ``"P"``).
    width:
        Image width in pixels.
    height:
        Image height in pixels.
    file_size_bytes:
        Size of the source file in bytes (from ``Path.stat()``).
    has_transparency:
        ``True`` if the image has an alpha channel or is a palette image with
        a transparency index.
    """

    path: Path
    original_format: str
    original_mode: str
    width: int
    height: int
    file_size_bytes: int
    has_transparency: bool

    @property
    def megapixels(self) -> float:
        """Image resolution in megapixels (width x height / 1_000_000)."""
        return (self.width * self.height) / 1_000_000

    @property
    def aspect_ratio(self) -> float:
        """Width-to-height aspect ratio."""
        return self.width / self.height if self.height else 0.0

    def __str__(self) -> str:
        return (
            f"{self.path.name}  "
            f"{self.width}x{self.height}px  "
            f"{self.original_format}  "
            f"{self.file_size_bytes / 1024:.1f} KB"
        )


@dataclass(frozen=True)
class LoadedImage:
    """Result of successfully loading and validating an image.

    Attributes
    ----------
    image:
        The PIL ``Image`` object.  Not mutated by the loader.
    metadata:
        Captured metadata for the source file.
    """

    image: Image.Image
    metadata: ImageMetadata

    def __str__(self) -> str:
        return f"LoadedImage({self.metadata})"


# ===========================================================================
# Loader
# ===========================================================================


class ImageLoader:
    """Loads and validates JPEG and PNG images for the tracing pipeline.

    Parameters
    ----------
    min_width_px:
        Minimum acceptable image width in pixels.  Images narrower than
        this are rejected with :exc:`ImageTooSmallError`.
    min_height_px:
        Minimum acceptable image height in pixels.
    supported_formats:
        Tuple of Pillow format strings that are accepted.  Defaults to
        ``("JPEG", "PNG")``.

    Examples
    --------
    >>> loader = ImageLoader()
    >>> loaded = loader.load(Path("artwork.png"))
    >>> loaded.metadata.width, loaded.metadata.height
    (1920, 1080)
    """

    def __init__(
        self,
        *,
        min_width_px: int = MIN_INPUT_WIDTH_PX,
        min_height_px: int = MIN_INPUT_HEIGHT_PX,
        supported_formats: tuple[str, ...] = SUPPORTED_INPUT_FORMATS,
    ) -> None:
        if min_width_px < 1 or min_height_px < 1:
            raise ValueError("Minimum dimensions must be >= 1 pixel.")
        self._min_width_px = min_width_px
        self._min_height_px = min_height_px
        self._supported_formats = supported_formats

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load(self, path: Path) -> LoadedImage:
        """Load and validate a single image file.

        Parameters
        ----------
        path:
            Path to the image file.  Must exist and be readable.

        Returns
        -------
        LoadedImage
            Bundled PIL image + validated metadata.

        Raises
        ------
        ImageLoadError
            If the file does not exist, cannot be read, or is corrupt.
        UnsupportedFormatError
            If the file format is not in :attr:`supported_formats`.
        ImageTooSmallError
            If the image dimensions are below the configured minimums.
        """
        path = path.resolve()
        logger.debug("Loading image: %s", path)

        # --- Existence & readability ------------------------------------
        if not path.exists():
            raise ImageLoadError(
                f"Image file not found: {path}",
                path=str(path),
            )
        if not path.is_file():
            raise ImageLoadError(
                f"Path is not a file: {path}",
                path=str(path),
            )

        # --- Open with Pillow -------------------------------------------
        try:
            image = Image.open(path)
            # Force Pillow to read the header and verify it's a real image
            image.verify()
            # Re-open after verify() — verify() leaves the file in a bad state
            image = Image.open(path)
        except UnidentifiedImageError as exc:
            raise ImageLoadError(
                f"File is not a recognised image: {path}",
                path=str(path),
            ) from exc
        except OSError as exc:
            raise ImageLoadError(
                f"Could not open image file: {path} — {exc}",
                path=str(path),
            ) from exc

        # --- Format validation ------------------------------------------
        self._validate_format(image, path)

        # --- Dimension validation ----------------------------------------
        self._validate_dimensions(image, path)

        # --- Build metadata ---------------------------------------------
        file_size = path.stat().st_size
        has_transparency = self._detect_transparency(image)

        metadata = ImageMetadata(
            path=path,
            original_format=image.format or "UNKNOWN",
            original_mode=image.mode,
            width=image.width,
            height=image.height,
            file_size_bytes=file_size,
            has_transparency=has_transparency,
        )

        logger.info("Loaded: %s", metadata)
        return LoadedImage(image=image, metadata=metadata)

    # ------------------------------------------------------------------
    # Validation helpers
    # ------------------------------------------------------------------

    def _validate_format(self, image: Image.Image, path: Path) -> None:
        """Raise :exc:`UnsupportedFormatError` if *image* is not an accepted format."""
        fmt = image.format
        if fmt not in self._supported_formats:
            raise UnsupportedFormatError(
                f"Unsupported format '{fmt}'. Accepted: {', '.join(self._supported_formats)}.",
                path=str(path),
                detected_format=fmt or "UNKNOWN",
            )

    def _validate_dimensions(self, image: Image.Image, path: Path) -> None:
        """Raise :exc:`ImageTooSmallError` if *image* is below minimum dimensions."""
        w, h = image.width, image.height
        if w < self._min_width_px or h < self._min_height_px:
            raise ImageTooSmallError(
                f"Image {w}x{h}px is below minimum {self._min_width_px}x{self._min_height_px}px.",
                path=str(path),
                width=w,
                height=h,
                min_width=self._min_width_px,
                min_height=self._min_height_px,
            )

    @staticmethod
    def _detect_transparency(image: Image.Image) -> bool:
        """Return ``True`` if *image* has meaningful transparency information."""
        return image.mode in ("RGBA", "LA") or (image.mode == "P" and "transparency" in image.info)
