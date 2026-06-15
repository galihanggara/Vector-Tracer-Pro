"""
vector_tracer_pro.core.image.loader
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Pure Python/NumPy-based image loading and ingestion module.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
import numpy as np
from PIL import Image

from vector_tracer_pro.core.exceptions import (
    CorruptImageError,
    ImageSizeError,
    UnsupportedFormatError,
)


@dataclass(frozen=True)
class ImageMetadata:
    """Metadata of an ingested image.

    Attributes
    ----------
    width:
        Width of the image in pixels.
    height:
        Height of the image in pixels.
    dpi:
        DPI (Dots Per Inch) of the image, defaulting to (72.0, 72.0).
    bit_depth:
        Calculated bit depth of the image (e.g., 1, 8, 16, 32).
    original_mode:
        Original mode of the Pillow Image (e.g. "RGB", "RGBA", "L", "P", etc.).
    """

    width: int
    height: int
    dpi: tuple[float, float]
    bit_depth: int
    original_mode: str


@dataclass(frozen=True)
class ImageData:
    """Numpy array data and metadata for an ingested image.

    Attributes
    ----------
    data:
        Normalized float32 NumPy array of shape (H, W, 3), range [0.0, 1.0], always RGB.
    metadata:
        Immutable metadata of the ingested image.
    """

    data: np.ndarray
    metadata: ImageMetadata


class ImageLoader:
    """Loads and validates raster images for the vector tracing pipeline.

    Validates file existence, format extensions (JPG/JPEG/PNG), image corruption,
    and dimension constraints.
    """

    def __init__(
        self,
        *,
        min_width: int = 32,
        min_height: int = 32,
        max_width: int = 10000,
        max_height: int = 10000,
    ) -> None:
        self.min_width = min_width
        self.min_height = min_height
        self.max_width = max_width
        self.max_height = max_height

    def load(self, path: Path) -> ImageData:
        """Loads and validates a single image file.

        Parameters
        ----------
        path:
            Path to the target raster image.

        Returns
        -------
        ImageData
            Loaded and normalized image data and metadata.

        Raises
        ------
        FileNotFoundError
            If the file does not exist or is not a file.
        PermissionError
            If the file is not readable due to permission errors.
        UnsupportedFormatError
            If the file extension is not .jpg, .jpeg, or .png.
        CorruptImageError
            If the image file is corrupt or fails Pillow verification.
        ImageSizeError
            If the dimensions are outside the configured minimum or maximum bounds.
        """
        path = Path(path).resolve()

        # 1. Existence and readability check
        if not path.exists():
            raise FileNotFoundError(f"Image file not found: {path}")
        if not path.is_file():
            raise FileNotFoundError(f"Path is not a file: {path}")

        try:
            with open(path, "rb") as f:
                pass
        except OSError as exc:
            raise PermissionError(f"Image file is not readable: {path}") from exc

        # 2. Extension check
        suffix = path.suffix.lower()
        if suffix not in (".jpg", ".jpeg", ".png"):
            detected_format = suffix[1:] if suffix.startswith(".") else suffix
            raise UnsupportedFormatError(
                f"Unsupported file format: {suffix}. Only JPG, JPEG, and PNG are supported.",
                path=str(path),
                detected_format=detected_format or "UNKNOWN",
            )

        # 3. Pillow Image.verify()
        try:
            with Image.open(path) as img:
                img.verify()
        except Exception as exc:
            raise CorruptImageError(
                f"Corrupt image file: {path}. Verification failed: {exc}",
                path=str(path),
            ) from exc

        # 4. Dimension checks
        try:
            with Image.open(path) as img:
                width, height = img.size
        except Exception as exc:
            raise CorruptImageError(
                f"Failed to read image dimensions: {path}. Error: {exc}",
                path=str(path),
            ) from exc

        if (
            width < self.min_width
            or height < self.min_height
            or width > self.max_width
            or height > self.max_height
        ):
            raise ImageSizeError(
                f"Image size {width}x{height} is outside allowed range "
                f"[{self.min_width}x{self.min_height} to {self.max_width}x{self.max_height}].",
                path=str(path),
                width=width,
                height=height,
                min_width=self.min_width,
                min_height=self.min_height,
                max_width=self.max_width,
                max_height=self.max_height,
            )

        # 5. Conversion and normalization
        try:
            with Image.open(path) as img:
                img_rgb = img.convert("RGB")
                arr = np.array(img_rgb, dtype=np.float32) / 255.0

                # DPI Extraction
                dpi_val = img.info.get("dpi", (72.0, 72.0))
                if isinstance(dpi_val, tuple) and len(dpi_val) == 2:
                    dpi = (float(dpi_val[0]), float(dpi_val[1]))
                elif isinstance(dpi_val, (int, float)):
                    dpi = (float(dpi_val), float(dpi_val))
                else:
                    dpi = (72.0, 72.0)

                bit_depth = self._get_bit_depth(img.mode)
                original_mode = img.mode

                metadata = ImageMetadata(
                    width=img.width,
                    height=img.height,
                    dpi=dpi,
                    bit_depth=bit_depth,
                    original_mode=original_mode,
                )
                return ImageData(data=arr, metadata=metadata)
        except Exception as exc:
            if isinstance(exc, (UnsupportedFormatError, CorruptImageError, ImageSizeError)):
                raise
            raise CorruptImageError(
                f"Failed to decode image pixels for: {path}. Error: {exc}",
                path=str(path),
            ) from exc

    def _get_bit_depth(self, mode: str) -> int:
        """Derive the bit depth from a Pillow mode string."""
        if mode == "1":
            return 1
        if mode in ("I;16", "I;16B", "I;16L", "I;16S"):
            return 16
        if mode in ("I", "F"):
            return 32
        return 8
