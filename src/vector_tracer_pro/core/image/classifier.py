"""
vector_tracer_pro.core.image.classifier
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Rule-based image classifier for identifying image categories.
"""

from __future__ import annotations

from enum import Enum
import numpy as np

from vector_tracer_pro.core.image.loader import ImageData

# --- Constants & Thresholds ---
# Minimum edge density for an image to be classified as LINE_ART when colors are limited.
EDGE_DENSITY_LINE_ART_MIN = 0.15

# Unused in decision tree directly but documented as expected threshold for photo max edges.
EDGE_DENSITY_PHOTO_MAX = 0.08

# Maximum unique color count for an image to be considered FLAT_VECTOR.
UNIQUE_COLOR_FLAT_MAX = 64

# Minimum unique color count for an image to be considered PHOTO.
UNIQUE_COLOR_PHOTO_MIN = 500

# Valley threshold relative to peak max_count to classify histogram as bimodal.
BIMODAL_VALLEY_THRESHOLD = 0.1

# Maximum pixel count to downsample to prevent memory explosion during color counting.
DOWNSAMPLE_PIXEL_LIMIT = 10_000


class ImageCategory(Enum):
    """Classification categories for raster images."""

    LINE_ART = "line_art"
    FLAT_VECTOR = "flat_vector"
    PHOTO = "photo"
    LOGO = "logo"


class ImageClassifier:
    """Classifies raster images into vectorization-friendly categories.

    Uses rule-based decision trees based on unique colors, edge density, and histogram analysis.
    """

    def classify(self, image: ImageData) -> ImageCategory:
        """Classify an ImageData object into an ImageCategory.

        Parameters
        ----------
        image:
            The input ImageData object.

        Returns
        -------
        ImageCategory
            The determined category of the image.
        """
        data = image.data

        # Safety checks and strip alpha if present
        if data.ndim != 3:
            raise ValueError("Image data must have 3 dimensions (H, W, channels).")
        if data.shape[2] > 3:
            data = data[:, :, :3]

        # 1. Unique color count (from downsampled pixels)
        unique_colors = self._count_unique_colors(data)

        # 2. Edge density
        edge_density = self._compute_edge_density(data)

        # Decision tree
        if unique_colors <= UNIQUE_COLOR_FLAT_MAX:
            if edge_density >= EDGE_DENSITY_LINE_ART_MIN:
                return ImageCategory.LINE_ART
            else:
                return ImageCategory.FLAT_VECTOR

        if unique_colors >= UNIQUE_COLOR_PHOTO_MIN:
            return ImageCategory.PHOTO

        # Middle range: check if bimodal histogram
        if self._is_bimodal(data):
            return ImageCategory.LOGO
        else:
            return ImageCategory.FLAT_VECTOR

    def _count_unique_colors(self, data: np.ndarray) -> int:
        """Count unique colors in downsampled pixels, rounded to uint8."""
        flat_data = data.reshape(-1, 3)
        num_pixels = flat_data.shape[0]

        if num_pixels > DOWNSAMPLE_PIXEL_LIMIT:
            # Deterministic/random sample of pixels to avoid memory explosion
            indices = np.random.choice(num_pixels, size=DOWNSAMPLE_PIXEL_LIMIT, replace=False)
            sampled = flat_data[indices]
        else:
            sampled = flat_data

        # Quantize to uint8 to avoid float precision noise
        sampled_uint8 = (sampled * 255.0 + 0.5).astype(np.uint8)
        unique_colors = len(np.unique(sampled_uint8, axis=0))
        return unique_colors

    def _compute_edge_density(self, data: np.ndarray) -> float:
        """Compute edge density using simple differences."""
        if data.shape[0] <= 1 or data.shape[1] <= 1:
            return 0.0

        # RGB to Grayscale
        gray = 0.299 * data[:, :, 0] + 0.587 * data[:, :, 1] + 0.114 * data[:, :, 2]

        gx = np.diff(gray, axis=1)
        gy = np.diff(gray, axis=0)

        # Align shapes to compute magnitude
        gx_aligned = gx[:-1, :]
        gy_aligned = gy[:, :-1]

        magnitude = np.sqrt(gx_aligned**2 + gy_aligned**2)
        normalized_magnitude = magnitude / np.sqrt(2.0)

        return float(np.mean(normalized_magnitude))

    def _is_bimodal(self, data: np.ndarray) -> bool:
        """Identify if the image histogram has two peaks separated by a valley."""
        # RGB to Grayscale
        gray = 0.299 * data[:, :, 0] + 0.587 * data[:, :, 1] + 0.114 * data[:, :, 2]

        hist, _ = np.histogram(gray, bins=256, range=(0.0, 1.0))
        max_count = np.max(hist)
        if max_count == 0:
            return False

        valley_limit = BIMODAL_VALLEY_THRESHOLD * max_count

        # Smooth histogram using a 5-bin moving average filter
        smoothed = np.convolve(hist, np.ones(5) / 5.0, mode="same")

        # Find local maxima (peaks)
        peaks = []
        for i in range(2, 254):
            if (
                smoothed[i] > smoothed[i - 1]
                and smoothed[i] > smoothed[i - 2]
                and smoothed[i] > smoothed[i + 1]
                and smoothed[i] > smoothed[i + 2]
                and smoothed[i] > 0.01 * max_count  # Significant peak check
            ):
                peaks.append(i)

        if len(peaks) < 2:
            return False

        # Sort peaks by smoothed bin counts in descending order
        peaks_sorted = sorted(peaks, key=lambda idx: smoothed[idx], reverse=True)

        # Check if there is any pair of major peaks separated by a deep valley
        for i in range(min(5, len(peaks_sorted))):
            for j in range(i + 1, min(5, len(peaks_sorted))):
                p1, p2 = peaks_sorted[i], peaks_sorted[j]
                idx_start, idx_end = min(p1, p2), max(p1, p2)

                # Ensure sufficient distance between the two peaks
                if idx_end - idx_start < 20:
                    continue

                # Locate the minimum in the valley between peaks
                valley_val = np.min(smoothed[idx_start : idx_end + 1])
                if valley_val < valley_limit:
                    return True

        return False
