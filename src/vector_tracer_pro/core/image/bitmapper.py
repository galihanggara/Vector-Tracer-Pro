"""
vector_tracer_pro.core.image.bitmapper
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Temporary bitmap export helper for Potrace (PBM) and VTracer/Inkscape (PNG).
"""

from __future__ import annotations

import contextlib
import tempfile
from collections.abc import Generator
from contextlib import AbstractContextManager as ContextManager
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

import numpy as np
from PIL import Image

from vector_tracer_pro.core.image.classifier import ImageCategory
from vector_tracer_pro.core.image.preprocessor import ProcessedImage


class BitmapFormat(Enum):
    """Supported export formats for tracing engines."""

    PBM = "pbm"  # Portable BitMap (1-bit uncompressed binary) for Potrace
    PNG = "png"  # Portable Network Graphics for VTracer/Inkscape


@dataclass
class BitmapFile:
    """Descriptor of the generated temporary bitmap file."""

    path: Path
    format: BitmapFormat
    source_category: ImageCategory


class Bitmapper:
    """Exports preprocessed images to temporary files for tracing engines.

    Provides a context manager interface to ensure that temporary files
    are safely cleaned up on both success and error paths.
    """

    def write(
        self,
        processed: ProcessedImage,
        fmt: BitmapFormat,
    ) -> ContextManager[BitmapFile]:
        """Safely write processed image data to a temporary file.

        Parameters
        ----------
        processed:
            The ProcessedImage result from the preprocessor.
        fmt:
            The target BitmapFormat.

        Returns
        -------
        ContextManager[BitmapFile]
            A context manager yielding a BitmapFile descriptor.

        Raises
        ------
        ValueError
            If validation checks fail (dimensions, formats, or data types).
        """
        # Validate input array properties
        if not isinstance(processed.data, np.ndarray):
            raise ValueError("ProcessedImage data must be a numpy array.")
        if processed.data.dtype != np.float32:
            raise ValueError("ProcessedImage data must be float32 array.")
        if processed.data.size == 0 or processed.data.shape[0] == 0 or processed.data.shape[1] == 0:
            raise ValueError("Image dimensions cannot be zero.")

        if fmt == BitmapFormat.PBM and processed.data.ndim != 2:
            raise ValueError("PBM format only supports 2D binary images (shape HxW).")

        @contextlib.contextmanager
        def _context() -> Generator[BitmapFile, None, None]:
            with tempfile.NamedTemporaryFile(
                suffix=f".{fmt.value}",
                delete=False,
            ) as tmp:
                tmp_path = Path(tmp.name)

            try:
                self._write_to_path(processed, tmp_path, fmt)
                yield BitmapFile(
                    path=tmp_path,
                    format=fmt,
                    source_category=processed.category,
                )
            finally:
                if tmp_path.exists():
                    tmp_path.unlink()

        return _context()

    def _write_to_path(self, processed: ProcessedImage, path: Path, fmt: BitmapFormat) -> None:
        """Write processed image data to the target path."""
        if fmt == BitmapFormat.PBM:
            # Potrace interprets 1 as black (foreground) and 0 as white (background).
            # Our float32 data is 0.0 for black, 1.0 for white.
            # Thus, we invert: values < 0.5 (black) become 1, >= 0.5 (white) become 0.
            binary = (processed.data < 0.5).astype(np.uint8)
            height, width = binary.shape

            header = f"P4\n{width} {height}\n".encode("ascii")
            # np.packbits pads rows to multiples of 8 along axis=1 automatically
            body = np.packbits(binary, axis=1).tobytes()

            with path.open("wb") as f:
                f.write(header)
                f.write(body)
        else:
            # PNG Format
            u8_data = (processed.data * 255.0 + 0.5).clip(0, 255).astype(np.uint8)
            if processed.data.ndim == 3:
                img = Image.fromarray(u8_data, mode="RGB")
            else:
                img = Image.fromarray(u8_data, mode="L")
            img.save(path, format="PNG")
