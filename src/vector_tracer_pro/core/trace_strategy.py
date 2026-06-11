"""
vector_tracer_pro.core.trace_strategy
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Trace strategy selection — determines which engine(s) to use and with
what parameters for a given image classification and marketplace preset.

This module decouples the *decision* of which engine to use from both:
  - :mod:`vector_tracer_pro.core.classifier` (which analyses the image)
  - :mod:`vector_tracer_pro.trace.potrace_engine` / ``inkscape_engine``
    (which perform the actual tracing)

This module implements a true **Strategy Pattern**:
Each vectorisation engine is encapsulated inside its own strategy class
inheriting from the abstract base class ``TracingStrategy``. The client code
(pipeline runner) only needs to call ``strategy.execute(input, output)`` without
worrying about which engine is selected.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum
from pathlib import Path
from typing import Final

from vector_tracer_pro.core.classifier import ClassificationResult, ImageType
from vector_tracer_pro.core.exceptions import TracingError


class TraceEngine(Enum):
    """Available vectorisation engines.

    Attributes
    ----------
    POTRACE:
        Potrace CLI — mono and greyscale tracing.
    INKSCAPE:
        Inkscape headless CLI — multi-colour tracing via ``--actions``.
    VTRACER:
        VTracer CLI — alternative colour tracing (optional, non-critical).
    """

    POTRACE = "potrace"
    INKSCAPE = "inkscape"
    VTRACER = "vtracer"


class TracingStrategy(ABC):
    """Abstract Base Class for vectorisation strategies (Strategy Pattern).

    Parameters
    ----------
    reason:
        Human-readable explanation of why this strategy was chosen.
    params:
        Engine-specific parameters (e.g. turdsize for Potrace, colors for Inkscape).
    """

    def __init__(self, reason: str, params: dict[str, object] | None = None) -> None:
        self.reason: str = reason
        self.params: dict[str, object] = params or {}

    @property
    @abstractmethod
    def primary_engine(self) -> TraceEngine:
        """Return the primary vectorisation engine for this strategy."""
        pass

    @property
    def fallback_engine(self) -> TraceEngine | None:
        """Return the fallback vectorisation engine, or None if not available."""
        return None

    @property
    def engine_params(self) -> dict[str, object]:
        """Return parameters forwarded to the engine."""
        return self.params

    @property
    def uses_potrace(self) -> bool:
        """``True`` if Potrace is the primary or fallback engine."""
        return TraceEngine.POTRACE in (self.primary_engine, self.fallback_engine)

    @property
    def uses_inkscape(self) -> bool:
        """``True`` if Inkscape is the primary or fallback engine."""
        return TraceEngine.INKSCAPE in (self.primary_engine, self.fallback_engine)

    @property
    def uses_vtracer(self) -> bool:
        """``True`` if VTracer is the primary or fallback engine."""
        return TraceEngine.VTRACER in (self.primary_engine, self.fallback_engine)

    @abstractmethod
    def execute(self, input_path: Path, output_svg_path: Path) -> None:
        """Execute the vectorisation engine on the input file.

        Parameters
        ----------
        input_path:
            Path to the input raster file (typically BMP or PBM).
        output_svg_path:
            Target path where the traced SVG file will be written.

        Raises
        ------
        TracingError
            If execution fails.
        """
        pass

    def __str__(self) -> str:
        fallback = (
            f" → fallback: {self.fallback_engine.value}"
            if self.fallback_engine
            else ""
        )
        return (
            f"TraceStrategy("
            f"engine={self.primary_engine.value}{fallback}, "
            f"reason={self.reason!r})"
        )


class PotraceTracingStrategy(TracingStrategy):
    """Strategy that executes the Potrace vectorisation engine."""

    @property
    def primary_engine(self) -> TraceEngine:
        return TraceEngine.POTRACE

    def execute(self, input_path: Path, output_svg_path: Path) -> None:
        """Run Potrace CLI."""
        raise NotImplementedError(
            "PotraceTracingStrategy.execute() is a Sprint 3 deliverable."
        )


class InkscapeTracingStrategy(TracingStrategy):
    """Strategy that executes the Inkscape vectorisation engine."""

    @property
    def primary_engine(self) -> TraceEngine:
        return TraceEngine.INKSCAPE

    def execute(self, input_path: Path, output_svg_path: Path) -> None:
        """Run Inkscape headless CLI."""
        raise NotImplementedError(
            "InkscapeTracingStrategy.execute() is a Sprint 3 deliverable."
        )


class VTracerTracingStrategy(TracingStrategy):
    """Strategy that executes the VTracer vectorisation engine."""

    @property
    def primary_engine(self) -> TraceEngine:
        return TraceEngine.VTRACER

    def execute(self, input_path: Path, output_svg_path: Path) -> None:
        """Run VTracer CLI."""
        raise NotImplementedError(
            "VTracerTracingStrategy.execute() is a Sprint 3 deliverable."
        )


class FallbackTracingStrategy(TracingStrategy):
    """Strategy that wraps a primary strategy and executes a fallback on failure.

    This implements a composite-like Strategy Pattern, allowing transparent
    error handling and engine fallback.
    """

    def __init__(
        self,
        primary: TracingStrategy,
        fallback: TracingStrategy,
        reason: str,
    ) -> None:
        super().__init__(reason=reason)
        self.primary: TracingStrategy = primary
        self.fallback: TracingStrategy = fallback

    @property
    def primary_engine(self) -> TraceEngine:
        return self.primary.primary_engine

    @property
    def fallback_engine(self) -> TraceEngine | None:
        return self.fallback.primary_engine

    @property
    def engine_params(self) -> dict[str, object]:
        return self.primary.engine_params

    def execute(self, input_path: Path, output_svg_path: Path) -> None:
        """Try primary strategy, fall back to secondary on TracingError."""
        try:
            self.primary.execute(input_path, output_svg_path)
        except TracingError as exc:
            # Under actual implementation, log warning and try fallback:
            # logger.warning("Primary engine failed, falling back: %s", exc)
            self.fallback.execute(input_path, output_svg_path)


# ---------------------------------------------------------------------------
# Default strategy templates
# ---------------------------------------------------------------------------

_MONOCHROME_TEMPLATE: Final[TracingStrategy] = PotraceTracingStrategy(
    reason="Monochrome image — Potrace is optimal.",
)
_GREYSCALE_TEMPLATE: Final[TracingStrategy] = PotraceTracingStrategy(
    reason="Greyscale image — Potrace with greyscale pre-processing.",
)
_COLOUR_SIMPLE_TEMPLATE: Final[TracingStrategy] = InkscapeTracingStrategy(
    reason="Simple colour palette — Inkscape multi-colour tracing.",
)
_COLOUR_COMPLEX_TEMPLATE: Final[TracingStrategy] = InkscapeTracingStrategy(
    reason="Complex colour palette — Inkscape full-colour tracing.",
)


class TraceStrategySelector:
    """Selects and instantiates the optimal TracingStrategy for a classified image.

    Parameters
    ----------
    vtracer_available:
        Whether VTracer is installed on PATH. When ``False``, fallback to
        VTracer is disabled and only the primary engine is returned.
    """

    def __init__(self, *, vtracer_available: bool = False) -> None:
        self._vtracer_available = vtracer_available

    def select(
        self,
        classification: ClassificationResult,
        *,
        preset_name: str = "default",
    ) -> TracingStrategy:
        """Select the optimal :class:`TracingStrategy` for *classification*.

        Parameters
        ----------
        classification:
            Result of :class:`~vector_tracer_pro.core.classifier.ImageClassifier`.
        preset_name:
            Active marketplace preset name (e.g. ``"adobe_stock"``). Used
            to apply preset-specific engine parameters.

        Returns
        -------
        TracingStrategy
            Resolved concrete tracing strategy ready to be executed.
        """
        # For now, preset logic is stubbed and we delegate to default_for
        return self.default_for(classification.image_type)

    def default_for(self, image_type: ImageType) -> TracingStrategy:
        """Return the default strategy for *image_type*.

        Suppresses VTracer fallback if ``vtracer_available=False``.

        Parameters
        ----------
        image_type:
            The image classification type.

        Returns
        -------
        TracingStrategy
        """
        if image_type == ImageType.MONOCHROME:
            return _MONOCHROME_TEMPLATE
        if image_type == ImageType.GREYSCALE:
            return _GREYSCALE_TEMPLATE

        # For colour image types, we may use VTracer as a fallback if available
        primary_reason = (
            "Simple colour palette — Inkscape multi-colour tracing."
            if image_type == ImageType.COLOUR_SIMPLE
            else "Complex colour palette — Inkscape full-colour tracing."
        )

        primary = InkscapeTracingStrategy(reason=primary_reason)
        if self._vtracer_available:
            fallback = VTracerTracingStrategy(reason="VTracer fallback option.")
            return FallbackTracingStrategy(
                primary=primary,
                fallback=fallback,
                reason=f"{primary_reason} (VTracer fallback enabled.)",
            )

        return primary
