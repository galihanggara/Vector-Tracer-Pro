"""
vector_tracer_pro.core.preprocessor
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Image preprocessing pipeline for Vector Tracer Pro.

Preprocessing prepares a loaded image for tracing by applying a sequence
of transformations selected based on the image's :class:`ImageType`:

+-------------------+-------------------------------------------------+
| Image type        | Steps applied                                   |
+===================+=================================================+
| MONOCHROME        | Resize → RGB flatten → Greyscale → Threshold    |
+-------------------+-------------------------------------------------+
| GREYSCALE         | Resize → RGB flatten → Greyscale → Denoise      |
+-------------------+-------------------------------------------------+
| COLOUR_SIMPLE     | Resize → RGB flatten → Quantise                 |
+-------------------+-------------------------------------------------+
| COLOUR_COMPLEX    | Resize → RGB flatten → Quantise → Denoise       |
+-------------------+-------------------------------------------------+

All transformations produce a **new image object** — the original
:attr:`LoadedImage.image` is never mutated.

Usage
-----
::

    from vector_tracer_pro.core.preprocessor import ImagePreprocessor
    from vector_tracer_pro.config.schema import PreprocessorConfig

    preprocessor = ImagePreprocessor(config=PreprocessorConfig())
    result = preprocessor.preprocess(loaded_image.image, image_type)
    # result.image is ready for bitmapping
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum, auto

from PIL import Image, ImageFilter

from vector_tracer_pro.config.defaults import (
    POTRACE_BLACKLEVEL,
    PREPROCESS_DENOISE_RADIUS,
    PREPROCESS_MAX_DIMENSION_PX,
    PREPROCESS_QUANTISE_COLOURS,
)
from vector_tracer_pro.core.classifier import ImageType
from vector_tracer_pro.core.exceptions import PreprocessingError

logger = logging.getLogger(__name__)


# ===========================================================================
# Step enumeration
# ===========================================================================


class ProcessingStep(Enum):
    """Individual preprocessing steps that may be applied."""

    RESIZE = auto()
    """Image was downscaled to fit within the maximum dimension cap."""

    FLATTEN_ALPHA = auto()
    """RGBA/LA transparency was composited onto a white background."""

    CONVERT_RGB = auto()
    """Image mode was converted to RGB."""

    CONVERT_GREYSCALE = auto()
    """Image was converted to 8-bit greyscale (``"L"`` mode)."""

    THRESHOLD = auto()
    """Greyscale image was binarised to 1-bit using a pixel threshold."""

    QUANTISE = auto()
    """Colour palette was reduced to a fixed number of colours."""

    DENOISE = auto()
    """Median filter was applied to reduce high-frequency noise."""


# ===========================================================================
# Result type
# ===========================================================================


@dataclass(frozen=True)
class ProcessedImage:
    """Result of the preprocessing pipeline.

    Attributes
    ----------
    image:
        The preprocessed PIL ``Image``, ready for bitmapping.
    original_size:
        ``(width, height)`` of the image before preprocessing.
    processed_size:
        ``(width, height)`` of the image after preprocessing.
    steps_applied:
        Ordered list of steps that were executed, providing an audit trail.
    """

    image: Image.Image
    original_size: tuple[int, int]
    processed_size: tuple[int, int]
    steps_applied: list[ProcessingStep] = field(default_factory=list)

    @property
    def was_resized(self) -> bool:
        """``True`` if a RESIZE step was applied."""
        return ProcessingStep.RESIZE in self.steps_applied

    @property
    def scale_factor(self) -> float:
        """Ratio of processed long-edge to original long-edge."""
        orig_long = max(self.original_size)
        proc_long = max(self.processed_size)
        return proc_long / orig_long if orig_long > 0 else 1.0

    def __str__(self) -> str:
        steps = ", ".join(s.name for s in self.steps_applied)
        return (
            f"ProcessedImage("
            f"{self.original_size[0]}x{self.original_size[1]}px -> "
            f"{self.processed_size[0]}x{self.processed_size[1]}px, "
            f"steps=[{steps}])"
        )


# ===========================================================================
# Preprocessor
# ===========================================================================


class ImagePreprocessor:
    """Applies a type-appropriate sequence of preprocessing steps.

    Parameters
    ----------
    max_dimension_px:
        Maximum allowed length of the longest image edge.  Images larger
        than this are proportionally downscaled.  Default: 4096.
    quantise_colours:
        Target palette size for :attr:`ProcessingStep.QUANTISE`.
        Default: 32.
    denoise_radius:
        Radius for the median-filter denoising pass.  ``0`` disables
        denoising.  Default: 1.
    blacklevel:
        Threshold (0.0 - 1.0) used when binarising greyscale images for
        Potrace.  Pixels darker than this value become black.  Default: 0.5.

    Examples
    --------
    >>> preprocessor = ImagePreprocessor()
    >>> result = preprocessor.preprocess(img, ImageType.COLOUR_COMPLEX)
    >>> result.steps_applied
    [ProcessingStep.RESIZE, ProcessingStep.CONVERT_RGB, ProcessingStep.QUANTISE, ...]
    """

    def __init__(
        self,
        *,
        max_dimension_px: int = PREPROCESS_MAX_DIMENSION_PX,
        quantise_colours: int = PREPROCESS_QUANTISE_COLOURS,
        denoise_radius: int = PREPROCESS_DENOISE_RADIUS,
        blacklevel: float = POTRACE_BLACKLEVEL,
    ) -> None:
        if max_dimension_px < 64:
            raise ValueError("max_dimension_px must be >= 64.")
        if quantise_colours < 2:
            raise ValueError("quantise_colours must be >= 2.")
        if denoise_radius < 0:
            raise ValueError("denoise_radius must be >= 0.")
        if not (0.0 <= blacklevel <= 1.0):
            raise ValueError("blacklevel must be in [0.0, 1.0].")

        self._max_dimension_px = max_dimension_px
        self._quantise_colours = quantise_colours
        self._denoise_radius = denoise_radius
        self._blacklevel = blacklevel

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def preprocess(
        self,
        image: Image.Image,
        image_type: ImageType,
    ) -> ProcessedImage:
        """Apply the appropriate preprocessing pipeline for *image_type*.

        Parameters
        ----------
        image:
            Source PIL ``Image``.  Not mutated.
        image_type:
            Classification result that controls which steps run.

        Returns
        -------
        ProcessedImage
            Processed image with audit trail of applied steps.

        Raises
        ------
        PreprocessingError
            If any step fails unexpectedly.
        """
        original_size = (image.width, image.height)
        steps: list[ProcessingStep] = []

        try:
            img = image.copy()

            # Step 1: Resize (all types)
            img, resized = self._resize_if_needed(img)
            if resized:
                steps.append(ProcessingStep.RESIZE)

            # Step 2: Flatten alpha (all types)
            img, flattened = self._flatten_alpha(img)
            if flattened:
                steps.append(ProcessingStep.FLATTEN_ALPHA)

            # Step 3: Type-specific pipeline
            if image_type is ImageType.MONOCHROME:
                img, mono_steps = self._pipeline_monochrome(img)
                steps.extend(mono_steps)

            elif image_type is ImageType.GREYSCALE:
                img, grey_steps = self._pipeline_greyscale(img)
                steps.extend(grey_steps)

            elif image_type is ImageType.COLOUR_SIMPLE:
                img, simple_steps = self._pipeline_colour_simple(img)
                steps.extend(simple_steps)

            else:  # COLOUR_COMPLEX
                img, complex_steps = self._pipeline_colour_complex(img)
                steps.extend(complex_steps)

        except Exception as exc:
            raise PreprocessingError(f"Preprocessing failed for {image_type.value}: {exc}") from exc

        processed_size = (img.width, img.height)
        result = ProcessedImage(
            image=img,
            original_size=original_size,
            processed_size=processed_size,
            steps_applied=steps,
        )
        logger.debug("Preprocessed: %s", result)
        return result

    # ------------------------------------------------------------------
    # Per-type pipelines
    # ------------------------------------------------------------------

    def _pipeline_monochrome(
        self,
        image: Image.Image,
    ) -> tuple[Image.Image, list[ProcessingStep]]:
        """Convert to 1-bit black-and-white (Potrace input)."""
        steps: list[ProcessingStep] = []

        img = self._to_rgb(image)
        steps.append(ProcessingStep.CONVERT_RGB)

        img = self._to_greyscale(img)
        steps.append(ProcessingStep.CONVERT_GREYSCALE)

        img = self._threshold(img)
        steps.append(ProcessingStep.THRESHOLD)

        return img, steps

    def _pipeline_greyscale(
        self,
        image: Image.Image,
    ) -> tuple[Image.Image, list[ProcessingStep]]:
        """Convert to 8-bit greyscale with optional denoising (Potrace input)."""
        steps: list[ProcessingStep] = []

        img = self._to_rgb(image)
        steps.append(ProcessingStep.CONVERT_RGB)

        img = self._to_greyscale(img)
        steps.append(ProcessingStep.CONVERT_GREYSCALE)

        if self._denoise_radius > 0:
            img = self._denoise(img)
            steps.append(ProcessingStep.DENOISE)

        return img, steps

    def _pipeline_colour_simple(
        self,
        image: Image.Image,
    ) -> tuple[Image.Image, list[ProcessingStep]]:
        """Quantise to a limited palette (Inkscape input)."""
        steps: list[ProcessingStep] = []

        img = self._to_rgb(image)
        steps.append(ProcessingStep.CONVERT_RGB)

        img = self._quantise(img)
        steps.append(ProcessingStep.QUANTISE)

        return img, steps

    def _pipeline_colour_complex(
        self,
        image: Image.Image,
    ) -> tuple[Image.Image, list[ProcessingStep]]:
        """Quantise and denoise for rich-colour Inkscape input."""
        steps: list[ProcessingStep] = []

        img = self._to_rgb(image)
        steps.append(ProcessingStep.CONVERT_RGB)

        img = self._quantise(img)
        steps.append(ProcessingStep.QUANTISE)

        if self._denoise_radius > 0:
            img = self._denoise(img)
            steps.append(ProcessingStep.DENOISE)

        return img, steps

    # ------------------------------------------------------------------
    # Atomic transformation helpers
    # ------------------------------------------------------------------

    def _resize_if_needed(self, image: Image.Image) -> tuple[Image.Image, bool]:
        """Proportionally resize *image* if the longest edge exceeds the cap.

        Returns
        -------
        tuple[Image.Image, bool]
            ``(image, was_resized)``
        """
        long_edge = max(image.width, image.height)
        if long_edge <= self._max_dimension_px:
            return image, False

        scale = self._max_dimension_px / long_edge
        new_w = max(1, round(image.width * scale))
        new_h = max(1, round(image.height * scale))
        resized = image.resize((new_w, new_h), Image.Resampling.LANCZOS)
        logger.debug(
            "Resized %dx%d → %dx%d (scale %.3f)",
            image.width,
            image.height,
            new_w,
            new_h,
            scale,
        )
        return resized, True

    def _flatten_alpha(self, image: Image.Image) -> tuple[Image.Image, bool]:
        """Composite RGBA or LA images onto a white background.

        Potrace and Inkscape tracing engines do not handle transparent
        pixels correctly.  Compositing onto white produces the cleanest
        tracing result for most stock imagery.

        Returns
        -------
        tuple[Image.Image, bool]
            ``(image, was_flattened)``
        """
        if image.mode == "RGBA":
            background = Image.new("RGB", image.size, (255, 255, 255))
            background.paste(image, mask=image.split()[3])
            return background, True
        if image.mode == "LA":
            background = Image.new("L", image.size, 255)
            background.paste(image, mask=image.split()[1])
            return background, True
        return image, False

    def _to_rgb(self, image: Image.Image) -> Image.Image:
        """Convert *image* to ``"RGB"`` mode if not already."""
        if image.mode == "RGB":
            return image
        return image.convert("RGB")

    def _to_greyscale(self, image: Image.Image) -> Image.Image:
        """Convert *image* to 8-bit greyscale (``"L"`` mode)."""
        if image.mode == "L":
            return image
        return image.convert("L")

    def _threshold(self, image: Image.Image) -> Image.Image:
        """Binarise a greyscale image using :attr:`_blacklevel`.

        Pixels with value <= ``blacklevel x 255`` become black (0);
        all other pixels become white (255).  Result is ``"L"`` mode
        (not ``"1"``), as Pillow's 1-bit mode has limited filter support.

        Parameters
        ----------
        image:
            8-bit greyscale (``"L"`` mode) image.

        Returns
        -------
        Image.Image
            Binarised ``"L"`` mode image.
        """
        threshold_value = int(self._blacklevel * 255)
        return image.point(lambda px: 0 if px <= threshold_value else 255, "L")

    def _quantise(self, image: Image.Image) -> Image.Image:
        """Reduce the colour palette to :attr:`_quantise_colours` entries.

        Uses Pillow's median-cut quantisation.  The result is returned
        in ``"RGB"`` mode (palette images are immediately converted back).

        Parameters
        ----------
        image:
            ``"RGB"`` mode image.

        Returns
        -------
        Image.Image
            Quantised ``"RGB"`` mode image.
        """
        quantised = image.quantize(colors=self._quantise_colours, method=Image.Quantize.MEDIANCUT)
        return quantised.convert("RGB")

    def _denoise(self, image: Image.Image) -> Image.Image:
        """Apply a median filter to reduce high-frequency noise.

        Parameters
        ----------
        image:
            Image in any mode supported by :class:`PIL.ImageFilter.MedianFilter`.

        Returns
        -------
        Image.Image
            Filtered image.
        """
        size = 2 * self._denoise_radius + 1  # kernel side length (must be odd)
        return image.filter(ImageFilter.MedianFilter(size=size))
