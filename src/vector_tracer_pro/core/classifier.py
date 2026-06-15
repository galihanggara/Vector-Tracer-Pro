"""
vector_tracer_pro.core.classifier
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Image content classifier for tracing engine selection.

This module analyses the pixel content of a loaded image and returns a
:class:`ClassificationResult` that tells the pipeline which tracing engine
to use and how to pre-process the image.

Classification logic
--------------------
The classifier operates on a downsampled 64 x 64 thumbnail for speed.
Classification proceeds through the following decision tree:

1. **Monochrome** — image mode is ``"1"`` (1-bit), OR fewer than 3
   distinct colours appear in the thumbnail.  Route → Potrace.

2. **Greyscale** — average pixel saturation (HSV colour model) is below
   the configured threshold (default 0.05).  Route → Potrace.

3. **Colour (simple)** — unique colour count in the thumbnail is below
   the configured threshold (default 16).  Route → Inkscape.

4. **Colour (complex)** — everything else.  Route → Inkscape.

The ``confidence`` field is a normalised [0 … 1] float indicating how
strongly the image fits the chosen category.  It is informational only.

Usage
-----
::

    from PIL import Image
    from vector_tracer_pro.core.classifier import ImageClassifier

    img = Image.open("logo.png")
    classifier = ImageClassifier()
    result = classifier.classify(img)
    print(result.image_type, result.recommended_engine)
"""

from __future__ import annotations

import colorsys
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Literal

from PIL import Image

from vector_tracer_pro.config.defaults import (
    COLOUR_SIMPLE_THRESHOLD,
    GREYSCALE_SATURATION_THRESHOLD,
)
from vector_tracer_pro.core.exceptions import ClassificationError

logger = logging.getLogger(__name__)

# Size of the thumbnail used for fast pixel analysis
_SAMPLE_SIZE: int = 64


class ImageType(Enum):
    """Classification categories for input images.

    Determines which tracing engine is selected downstream.
    """

    MONOCHROME = "monochrome"
    """Essentially black-and-white; route to Potrace."""

    GREYSCALE = "greyscale"
    """Desaturated image; route to Potrace with greyscale pre-processing."""

    COLOUR_SIMPLE = "colour_simple"
    """Limited colour palette; route to Inkscape."""

    COLOUR_COMPLEX = "colour_complex"
    """Rich colour palette; route to Inkscape."""

    @property
    def recommended_engine(self) -> Literal["potrace", "inkscape"]:
        """Return the tracing engine recommended for this image type."""
        if self in (ImageType.MONOCHROME, ImageType.GREYSCALE):
            return "potrace"
        return "inkscape"


@dataclass(frozen=True)
class ClassificationResult:
    """Result of classifying one image.

    Attributes
    ----------
    image_type:
        The determined type of the image.
    unique_colour_count:
        Number of distinct colours found in the 64 x 64 thumbnail.
    average_saturation:
        Mean HSV saturation across all thumbnail pixels (0.0 - 1.0).
    confidence:
        Confidence score (0.0 - 1.0) indicating how clearly the image
        fits the chosen category.  Informational only.
    recommended_engine:
        ``"potrace"`` or ``"inkscape"``, derived from :attr:`image_type`.
    """

    image_type: ImageType
    unique_colour_count: int
    average_saturation: float
    confidence: float
    recommended_engine: Literal["potrace", "inkscape"]

    def __str__(self) -> str:
        return (
            f"ClassificationResult("
            f"type={self.image_type.value}, "
            f"colours={self.unique_colour_count}, "
            f"saturation={self.average_saturation:.3f}, "
            f"confidence={self.confidence:.2f}, "
            f"engine={self.recommended_engine})"
        )


class ImageClassifier:
    """Classifies images to select the optimal tracing engine.

    Parameters
    ----------
    colour_simple_threshold:
        Maximum unique-colour count in the thumbnail for the image to be
        considered *colour simple*.  Default: 16.
    greyscale_saturation_threshold:
        Maximum average HSV saturation for the image to be considered
        *greyscale*.  Default: 0.05.

    Examples
    --------
    >>> from PIL import Image
    >>> classifier = ImageClassifier()
    >>> result = classifier.classify(Image.open("logo.png"))
    >>> result.recommended_engine
    'inkscape'
    """

    def __init__(
        self,
        *,
        colour_simple_threshold: int = COLOUR_SIMPLE_THRESHOLD,
        greyscale_saturation_threshold: float = GREYSCALE_SATURATION_THRESHOLD,
    ) -> None:
        if colour_simple_threshold < 2:
            raise ValueError("colour_simple_threshold must be >= 2.")
        if not (0.0 <= greyscale_saturation_threshold <= 1.0):
            raise ValueError("greyscale_saturation_threshold must be in [0, 1].")

        self._colour_simple_threshold: int = colour_simple_threshold
        self._greyscale_saturation_threshold: float = greyscale_saturation_threshold

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def classify(self, image: Image.Image) -> ClassificationResult:
        """Classify *image* and return a :class:`ClassificationResult`.

        Parameters
        ----------
        image:
            Any PIL ``Image`` object.  The image is not mutated.

        Returns
        -------
        ClassificationResult
            Frozen dataclass with type, stats, and recommended engine.

        Raises
        ------
        ClassificationError
            If the image cannot be analysed (e.g. zero-pixel image).
        """
        if image.width == 0 or image.height == 0:
            raise ClassificationError("Cannot classify a zero-dimension image.")

        try:
            thumbnail = self._make_thumbnail(image)
        except Exception as exc:
            raise ClassificationError(
                f"Failed to downsample image for classification: {exc}"
            ) from exc

        # Fast-path: 1-bit images are always monochrome
        if image.mode == "1":
            return ClassificationResult(
                image_type=ImageType.MONOCHROME,
                unique_colour_count=2,
                average_saturation=0.0,
                confidence=1.0,
                recommended_engine=ImageType.MONOCHROME.recommended_engine,
            )

        unique_colours = self._count_unique_colours(thumbnail)
        avg_saturation = self._compute_average_saturation(thumbnail)

        image_type, confidence = self._decide(unique_colours, avg_saturation)

        result = ClassificationResult(
            image_type=image_type,
            unique_colour_count=unique_colours,
            average_saturation=avg_saturation,
            confidence=confidence,
            recommended_engine=image_type.recommended_engine,
        )
        logger.debug("Classified image: %s", result)
        return result

    # ------------------------------------------------------------------
    # Private analysis helpers
    # ------------------------------------------------------------------

    def _make_thumbnail(self, image: Image.Image) -> Image.Image:
        """Return a small RGB thumbnail suitable for pixel analysis.

        The original image is *not* mutated — a copy is made.
        """
        # Flatten RGBA transparency onto a white background
        if image.mode == "RGBA":
            background = Image.new("RGB", image.size, (255, 255, 255))
            background.paste(image, mask=image.split()[3])
            rgb = background
        else:
            rgb = image.convert("RGB")

        return rgb.resize(
            (_SAMPLE_SIZE, _SAMPLE_SIZE),
            Image.Resampling.NEAREST,  # preserve sharp colour edges; no anti-alias mixing
        )

    def _count_unique_colours(self, thumbnail: Image.Image) -> int:
        """Count distinct RGB colours in *thumbnail*.

        Parameters
        ----------
        thumbnail:
            Small RGB image (typically 64 x 64).

        Returns
        -------
        int
            Number of unique (R, G, B) tuples.
        """
        return len(set(thumbnail.get_flattened_data()))

    def _compute_average_saturation(self, thumbnail: Image.Image) -> float:
        """Compute mean HSV saturation across all pixels in *thumbnail*.

        Uses ``colorsys.rgb_to_hsv`` — no numpy required.

        Parameters
        ----------
        thumbnail:
            Small RGB image.

        Returns
        -------
        float
            Average saturation in [0.0, 1.0].
        """
        pixels: list[tuple[int, ...]] = list(thumbnail.get_flattened_data())  # type: ignore[assignment]
        if not pixels:
            return 0.0

        total_saturation: float = 0.0
        for pixel in pixels:
            r, g, b = pixel[0] / 255.0, pixel[1] / 255.0, pixel[2] / 255.0
            _h, s, _v = colorsys.rgb_to_hsv(r, g, b)
            total_saturation += s

        return total_saturation / len(pixels)

    def _decide(
        self,
        unique_colours: int,
        avg_saturation: float,
    ) -> tuple[ImageType, float]:
        """Apply the classification decision tree.

        Parameters
        ----------
        unique_colours:
            Number of unique colours in the thumbnail.
        avg_saturation:
            Average HSV saturation of the thumbnail.

        Returns
        -------
        tuple[ImageType, float]
            The determined type and a confidence score in [0.0, 1.0].
        """
        # --- Monochrome ---------------------------------------------------
        if unique_colours <= 2:
            confidence = 1.0 - min(avg_saturation / 0.1, 1.0)
            return ImageType.MONOCHROME, max(0.5, confidence)

        # --- Greyscale ----------------------------------------------------
        if avg_saturation < self._greyscale_saturation_threshold:
            # Confidence: how far below the threshold the saturation is
            ratio = avg_saturation / max(self._greyscale_saturation_threshold, 1e-9)
            confidence = max(0.5, 1.0 - ratio)
            return ImageType.GREYSCALE, confidence

        # --- Colour (simple) ----------------------------------------------
        if unique_colours < self._colour_simple_threshold:
            # Confidence: how few colours relative to the threshold
            ratio = unique_colours / self._colour_simple_threshold
            confidence = max(0.5, 1.0 - ratio)
            return ImageType.COLOUR_SIMPLE, confidence

        # --- Colour (complex) ---------------------------------------------
        # Confidence: how far above the threshold the colour count is
        excess = unique_colours - self._colour_simple_threshold
        # Saturates at 1.0 when excess >= colour_simple_threshold
        confidence = min(1.0, 0.5 + excess / (2 * self._colour_simple_threshold))
        return ImageType.COLOUR_COMPLEX, confidence
