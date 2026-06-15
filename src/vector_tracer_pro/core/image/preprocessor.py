"""
vector_tracer_pro.core.image.preprocessor
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Image preprocessing pipeline for preparing raster images for tracing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import numpy as np
from PIL import Image

from vector_tracer_pro.core.image.loader import ImageData, ImageMetadata
from vector_tracer_pro.core.image.classifier import ImageCategory


@dataclass
class PreprocessConfig:
    """Configuration options for the preprocessing pipeline.

    Allows toggling individual steps and setting parameters.
    """

    skip_denoise: bool = False
    skip_quantize: bool = False
    skip_resize: bool = False
    skip_enhance: bool = False
    skip_sharpen: bool = False
    skip_threshold: bool = False
    max_dimension: int = 2000
    quantize_k: int = 16
    threshold_value: int | None = None  # None = pakai Otsu


@dataclass
class ProcessedImage:
    """Result of the image preprocessing pipeline.

    Contract:
    ---------
    - For LINE_ART and LOGO, the output `data` has shape (H, W) (2D binary/grayscale float32 array).
    - For FLAT_VECTOR and PHOTO, the output `data` has shape (H, W, 3) (3D RGB float32 array).
    """

    data: np.ndarray
    metadata: ImageMetadata
    category: ImageCategory
    config: PreprocessConfig
    applied_steps: list[str] = field(default_factory=list)


class Preprocessor:
    """Applies type-specific image processing transformations."""

    def process(
        self,
        image: ImageData,
        category: ImageCategory,
        config: PreprocessConfig | None = None,
    ) -> ProcessedImage:
        """Apply category-specific transformations to the image.

        Parameters
        ----------
        image:
            The input ImageData object.
        category:
            The determined category of the image.
        config:
            The PreprocessConfig. If None, default PreprocessConfig() is used.

        Returns
        -------
        ProcessedImage
            The processed image and metadata.
        """
        if config is None:
            config = PreprocessConfig()

        applied_steps: list[str] = []
        data = image.data.copy()

        if category == ImageCategory.LINE_ART:
            # Grayscale conversion
            data = self._to_grayscale(data)
            applied_steps.append("grayscale")

            # Thresholding (Otsu or fixed)
            if not config.skip_threshold:
                if config.threshold_value is not None:
                    thresh = config.threshold_value / 255.0
                    data = np.where(data <= thresh, 0.0, 1.0).astype(np.float32)
                    applied_steps.append("fixed_threshold")
                else:
                    otsu_thresh = self._compute_otsu_threshold(data)
                    data = np.where(data <= otsu_thresh, 0.0, 1.0).astype(np.float32)
                    applied_steps.append("otsu_threshold")

            # Denoising
            if not config.skip_denoise:
                data = self._median_filter_3x3_2d(data)
                applied_steps.append("denoise")

        elif category == ImageCategory.FLAT_VECTOR:
            # Quantize colors (k-means)
            if not config.skip_quantize:
                data = self._quantize_kmeans(data, config.quantize_k)
                applied_steps.append("quantize")

            # Smooth edges
            if not config.skip_denoise:
                data = self._average_filter_3x3_3d(data)
                applied_steps.append("smooth")

        elif category == ImageCategory.PHOTO:
            # Resize
            if not config.skip_resize:
                data, resized = self._resize_max_dimension(data, config.max_dimension)
                if resized:
                    applied_steps.append("resize")

            # Enhance contrast
            if not config.skip_enhance:
                data = self._enhance_contrast(data)
                applied_steps.append("enhance_contrast")

        elif category == ImageCategory.LOGO:
            # Grayscale conversion
            data = self._to_grayscale(data)
            applied_steps.append("grayscale")

            # Sharpening
            if not config.skip_sharpen:
                data = self._sharpen_filter_3x3_2d(data)
                applied_steps.append("sharpen")

            # Thresholding
            if not config.skip_threshold:
                if config.threshold_value is not None:
                    thresh = config.threshold_value / 255.0
                    data = np.where(data <= thresh, 0.0, 1.0).astype(np.float32)
                    applied_steps.append("fixed_threshold")
                else:
                    otsu_thresh = self._compute_otsu_threshold(data)
                    data = np.where(data <= otsu_thresh, 0.0, 1.0).astype(np.float32)
                    applied_steps.append("otsu_threshold")

        return ProcessedImage(
            data=data,
            metadata=ImageMetadata(
                width=data.shape[1],
                height=data.shape[0],
                dpi=image.metadata.dpi,
                bit_depth=image.metadata.bit_depth,
                original_mode=image.metadata.original_mode,
            ),
            category=category,
            config=config,
            applied_steps=applied_steps,
        )

    # --- Preprocessing Step Helper Functions ---

    def _to_grayscale(self, data: np.ndarray) -> np.ndarray:
        """Convert float32 RGB data to 2D grayscale."""
        return 0.299 * data[:, :, 0] + 0.587 * data[:, :, 1] + 0.114 * data[:, :, 2]

    def _compute_otsu_threshold(self, gray: np.ndarray) -> float:
        """Compute the Otsu binarization threshold for a grayscale image."""
        gray_u8 = (gray * 255.0 + 0.5).clip(0, 255).astype(np.uint8)
        hist, _ = np.histogram(gray_u8, bins=256, range=(0, 256))

        total = gray_u8.size
        current_max = 0.0
        threshold = 127

        sum_total = np.sum(np.arange(256) * hist)
        sum_background = 0.0
        weight_background = 0.0

        for i in range(256):
            weight_background += hist[i]
            if weight_background == 0:
                continue
            weight_foreground = total - weight_background
            if weight_foreground == 0:
                break

            sum_background += float(i) * hist[i]
            mean_background = sum_background / weight_background
            mean_foreground = (sum_total - sum_background) / weight_foreground

            # Between-class variance
            var_between = (
                weight_background
                * weight_foreground
                * (mean_background - mean_foreground) ** 2
            )

            if var_between > current_max:
                current_max = var_between
                threshold = i

        return threshold / 255.0

    def _median_filter_3x3_2d(self, arr: np.ndarray) -> np.ndarray:
        """Apply a 3x3 median filter to a 2D array."""
        padded = np.pad(arr, pad_width=1, mode="edge")
        windows = np.lib.stride_tricks.sliding_window_view(padded, (3, 3))
        flat_windows = windows.reshape(arr.shape[0], arr.shape[1], 9)
        return np.median(flat_windows, axis=-1).astype(arr.dtype)

    def _sharpen_filter_3x3_2d(self, gray: np.ndarray) -> np.ndarray:
        """Apply a 3x3 sharpening filter to a 2D array."""
        padded = np.pad(gray, pad_width=1, mode="edge")
        windows = np.lib.stride_tricks.sliding_window_view(padded, (3, 3))
        kernel = np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]], dtype=np.float32)
        sharpened = np.sum(windows * kernel, axis=(-2, -1))
        return np.clip(sharpened, 0.0, 1.0).astype(gray.dtype)

    def _average_filter_3x3_3d(self, data: np.ndarray) -> np.ndarray:
        """Apply a 3x3 box average smoothing filter to a 3D RGB array."""
        padded = np.pad(data, ((1, 1), (1, 1), (0, 0)), mode="edge")
        windows = np.lib.stride_tricks.sliding_window_view(padded, (3, 3), axis=(0, 1))
        return np.mean(windows, axis=(-2, -1)).astype(data.dtype)

    def _enhance_contrast(self, data: np.ndarray) -> np.ndarray:
        """Apply min-max linear contrast stretching per channel."""
        enhanced = np.zeros_like(data)
        for c in range(data.shape[2]):
            c_min = np.min(data[:, :, c])
            c_max = np.max(data[:, :, c])
            if c_max > c_min:
                enhanced[:, :, c] = (data[:, :, c] - c_min) / (c_max - c_min)
            else:
                enhanced[:, :, c] = data[:, :, c]
        return enhanced

    def _resize_max_dimension(
        self, data: np.ndarray, max_dim: int
    ) -> tuple[np.ndarray, bool]:
        """Proportionally resize image if longest edge exceeds max_dim."""
        h, w = data.shape[:2]
        longest = max(h, w)
        if longest <= max_dim:
            return data, False

        # Convert back to PIL Image U8 to use Lanczos interpolation
        img_u8 = (data * 255.0 + 0.5).clip(0, 255).astype(np.uint8)
        pil_img = Image.fromarray(img_u8)

        scale = max_dim / longest
        new_w = int(w * scale)
        new_h = int(h * scale)

        resized_pil = pil_img.resize((new_w, new_h), Image.Resampling.LANCZOS)
        resized_data = np.array(resized_pil, dtype=np.float32) / 255.0
        return resized_data, True

    def _quantize_kmeans(self, data: np.ndarray, k: int) -> np.ndarray:
        """Reduce image colors to k centroids using a memory-safe NumPy k-means."""
        flat_data = data.reshape(-1, 3)
        num_pixels = flat_data.shape[0]

        # Use up to 10,000 pixels for centroid fitting
        sample_limit = 10_000
        if num_pixels > sample_limit:
            # Deterministic RNG for reproducible quantization in testing
            rng = np.random.default_rng(42)
            indices = rng.choice(num_pixels, size=sample_limit, replace=False)
            sample = flat_data[indices]
        else:
            sample = flat_data

        # Initialize centroids randomly from sample
        rng = np.random.default_rng(42)
        k_actual = min(k, sample.shape[0])
        centroids = sample[rng.choice(sample.shape[0], size=k_actual, replace=False)]

        # Standard Lloyd's K-Means clustering algorithm
        for _ in range(12):
            # Distance array of shape (sample_size, k_actual)
            dists = np.sum((sample[:, np.newaxis, :] - centroids[np.newaxis, :, :]) ** 2, axis=2)
            labels = np.argmin(dists, axis=1)

            new_centroids = np.zeros_like(centroids)
            for i in range(k_actual):
                mask = (labels == i)
                if np.any(mask):
                    new_centroids[i] = np.mean(sample[mask], axis=0)
                else:
                    new_centroids[i] = sample[rng.choice(sample.shape[0])]

            if np.allclose(centroids, new_centroids, atol=1e-4):
                centroids = new_centroids
                break
            centroids = new_centroids

        # Chunked mapping to avoid memory blowup on large images
        chunk_size = 100_000
        labels_all = np.zeros(num_pixels, dtype=np.int32)
        for start in range(0, num_pixels, chunk_size):
            end = min(start + chunk_size, num_pixels)
            chunk = flat_data[start:end]
            dists = np.sum((chunk[:, np.newaxis, :] - centroids[np.newaxis, :, :]) ** 2, axis=2)
            labels_all[start:end] = np.argmin(dists, axis=1)

        quantized_flat = centroids[labels_all]
        return quantized_flat.reshape(data.shape)
