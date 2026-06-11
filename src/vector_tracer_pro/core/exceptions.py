"""
vector_tracer_pro.core.exceptions
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Custom exception hierarchy for Vector Tracer Pro.

All application-level errors descend from VectorTracerError.
The hierarchy is kept flat enough to be catchable at broad or
specific granularity depending on the call-site needs.

Usage
-----
    from vector_tracer_pro.core.exceptions import PotraceError

    try:
        result = potrace_engine.trace(bmp_path)
    except PotraceError as exc:
        logger.error("Potrace failed: %s", exc)
"""

from __future__ import annotations


# =============================================================================
# Base
# =============================================================================


class VectorTracerError(Exception):
    """Base class for all Vector Tracer Pro exceptions.

    All custom exceptions in this application inherit from this class,
    allowing callers to catch any application-level error with a single
    ``except VectorTracerError`` clause.
    """


# =============================================================================
# Dependency errors
# =============================================================================


class DependencyError(VectorTracerError):
    """Raised when a required external binary is missing or incompatible.

    Attributes
    ----------
    binary:
        Name of the missing or incompatible binary (e.g. ``"potrace"``).
    minimum_version:
        The minimum version string required (e.g. ``"1.16"``), or ``None``
        if any version would satisfy the requirement.
    detected_version:
        The version string actually found, or ``None`` if not detected.
    download_url:
        URL where the user can obtain the correct binary.
    """

    def __init__(
        self,
        message: str,
        *,
        binary: str,
        minimum_version: str | None = None,
        detected_version: str | None = None,
        download_url: str = "",
    ) -> None:
        super().__init__(message)
        self.binary = binary
        self.minimum_version = minimum_version
        self.detected_version = detected_version
        self.download_url = download_url


class PotraceMissingError(DependencyError):
    """Potrace binary not found on PATH."""


class InkscapeMissingError(DependencyError):
    """Inkscape binary not found on PATH."""


class InkscapeVersionError(DependencyError):
    """Inkscape found but version does not meet minimum requirement."""


# =============================================================================
# Image loading errors
# =============================================================================


class ImageError(VectorTracerError):
    """Base class for image-related errors."""


class ImageLoadError(ImageError):
    """Raised when an image file cannot be opened or decoded.

    Attributes
    ----------
    path:
        The filesystem path that failed to load.
    """

    def __init__(self, message: str, *, path: str) -> None:
        super().__init__(message)
        self.path = path


class UnsupportedFormatError(ImageError):
    """Raised when the input file format is not JPG or PNG.

    Attributes
    ----------
    path:
        The filesystem path of the offending file.
    detected_format:
        The format string as detected by Pillow (e.g. ``"GIF"``).
    """

    def __init__(
        self,
        message: str,
        *,
        path: str,
        detected_format: str,
    ) -> None:
        super().__init__(message)
        self.path = path
        self.detected_format = detected_format


class ImageTooSmallError(ImageError):
    """Raised when the input image is below the minimum required dimensions.

    Attributes
    ----------
    path:
        The filesystem path.
    width:
        Actual image width in pixels.
    height:
        Actual image height in pixels.
    min_width:
        Minimum required width in pixels.
    min_height:
        Minimum required height in pixels.
    """

    def __init__(
        self,
        message: str,
        *,
        path: str,
        width: int,
        height: int,
        min_width: int,
        min_height: int,
    ) -> None:
        super().__init__(message)
        self.path = path
        self.width = width
        self.height = height
        self.min_width = min_width
        self.min_height = min_height


# =============================================================================
# Preprocessing errors
# =============================================================================


class PreprocessingError(VectorTracerError):
    """Raised when image preprocessing fails (threshold, denoise, quantise)."""


# =============================================================================
# Classification errors
# =============================================================================


class ClassificationError(VectorTracerError):
    """Raised when the image classifier cannot determine image type."""


# =============================================================================
# Tracing errors
# =============================================================================


class TracingError(VectorTracerError):
    """Base class for errors raised during the tracing step."""


class PotraceError(TracingError):
    """Raised when the Potrace subprocess fails or produces invalid output.

    Attributes
    ----------
    return_code:
        Process return code from Potrace.
    stderr:
        Captured stderr output from the Potrace process.
    """

    def __init__(
        self,
        message: str,
        *,
        return_code: int,
        stderr: str = "",
    ) -> None:
        super().__init__(message)
        self.return_code = return_code
        self.stderr = stderr


class InkscapeTracingError(TracingError):
    """Raised when Inkscape headless tracing fails.

    Attributes
    ----------
    return_code:
        Process return code from Inkscape.
    stderr:
        Captured stderr output from the Inkscape process.
    """

    def __init__(
        self,
        message: str,
        *,
        return_code: int,
        stderr: str = "",
    ) -> None:
        super().__init__(message)
        self.return_code = return_code
        self.stderr = stderr


# =============================================================================
# SVG errors
# =============================================================================


class SVGError(VectorTracerError):
    """Base class for SVG-related errors."""


class SVGOptimizationError(SVGError):
    """Raised when scour SVG post-processing fails."""


class SVGValidationError(SVGError):
    """Raised when SVG output fails a verified marketplace requirement.

    Attributes
    ----------
    rule:
        Short identifier of the violated rule (e.g. ``"no_embedded_rasters"``).
    marketplace:
        The marketplace whose rule was violated (e.g. ``"adobe_stock"``),
        or ``None`` if the rule is universal.
    details:
        Human-readable description of the violation.
    """

    def __init__(
        self,
        message: str,
        *,
        rule: str,
        marketplace: str | None = None,
        details: str = "",
    ) -> None:
        super().__init__(message)
        self.rule = rule
        self.marketplace = marketplace
        self.details = details


# =============================================================================
# Export errors
# =============================================================================


class ExportError(VectorTracerError):
    """Raised when writing output files (SVG or JPG) fails."""


class PreviewExportError(ExportError):
    """Raised when JPG preview generation or saving fails."""


# =============================================================================
# Configuration & preset errors
# =============================================================================


class ConfigError(VectorTracerError):
    """Raised when the application configuration is invalid or unreadable."""


class PresetError(VectorTracerError):
    """Base class for preset-related errors."""


class PresetNotFoundError(PresetError):
    """Raised when a requested preset name does not exist.

    Attributes
    ----------
    preset_name:
        The name of the preset that was not found.
    """

    def __init__(self, message: str, *, preset_name: str) -> None:
        super().__init__(message)
        self.preset_name = preset_name


class PresetValidationError(PresetError):
    """Raised when a preset file fails Pydantic schema validation."""


class PresetSaveError(PresetError):
    """Raised when a custom preset cannot be persisted to disk."""


# =============================================================================
# Pipeline errors
# =============================================================================


class PipelineError(VectorTracerError):
    """Raised for unexpected errors in the trace pipeline orchestration.

    Wraps lower-level exceptions with pipeline context when the specific
    error type is not one of the above specialisations.
    """
