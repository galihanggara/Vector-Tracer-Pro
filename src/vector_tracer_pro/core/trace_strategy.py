"""
vector_tracer_pro.core.trace_strategy
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Trace strategy selection — determines which engine(s) to use and with
what parameters for a given image classification and marketplace preset.

This module decouples the *decision* of which engine to use from both:
  - :mod:`vector_tracer_pro.core.classifier` (which analyses the image)
  - :mod:`vector_tracer_pro.trace.potrace_engine` / ``inkscape_engine``
    (which perform the actual tracing)

Planned engine routing (Sprint 3 implementation)
-------------------------------------------------
+------------------+-------------------+----------------------------------+
| Image type       | Primary engine    | Fallback                         |
+==================+===================+==================================+
| MONOCHROME       | Potrace           | —                                |
+------------------+-------------------+----------------------------------+
| GREYSCALE        | Potrace           | —                                |
+------------------+-------------------+----------------------------------+
| COLOUR_SIMPLE    | Inkscape          | VTracer (if available)           |
+------------------+-------------------+----------------------------------+
| COLOUR_COMPLEX   | Inkscape          | VTracer (if available)           |
+------------------+-------------------+----------------------------------+

.. note::

    This file is a **Sprint 2 skeleton**.  The ``TraceStrategySelector``
    class raises :exc:`NotImplementedError` until Sprint 3.  Import the
    types freely; do not call ``select()`` yet.

Usage (Sprint 3+)
-----------------
::

    from vector_tracer_pro.core.classifier import ImageClassifier
    from vector_tracer_pro.core.trace_strategy import TraceStrategySelector

    classifier = ImageClassifier()
    result = classifier.classify(image)

    selector = TraceStrategySelector()
    strategy = selector.select(result, preset_name="adobe_stock")
    # strategy.primary_engine → TraceEngine.INKSCAPE
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from vector_tracer_pro.core.classifier import ClassificationResult, ImageType


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


@dataclass(frozen=True)
class TraceStrategy:
    """Resolved strategy for tracing a single image.

    Attributes
    ----------
    primary_engine:
        The engine that should be attempted first.
    fallback_engine:
        The engine to use if the primary fails, or ``None`` if no fallback
        is available.
    reason:
        Human-readable explanation of why this strategy was chosen.
    engine_params:
        Arbitrary key-value pairs forwarded to the selected engine.
        Exact keys depend on the engine (e.g. ``turdsize`` for Potrace,
        ``colours`` for Inkscape).
    """

    primary_engine: TraceEngine
    fallback_engine: TraceEngine | None
    reason: str
    engine_params: dict[str, object] = field(default_factory=dict)

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


# ---------------------------------------------------------------------------
# Default strategies (read-only reference mapping, used by Sprint 3 impl)
# ---------------------------------------------------------------------------

_DEFAULT_STRATEGY_MAP: dict[ImageType, TraceStrategy] = {
    ImageType.MONOCHROME: TraceStrategy(
        primary_engine=TraceEngine.POTRACE,
        fallback_engine=None,
        reason="Monochrome image — Potrace is optimal.",
    ),
    ImageType.GREYSCALE: TraceStrategy(
        primary_engine=TraceEngine.POTRACE,
        fallback_engine=None,
        reason="Greyscale image — Potrace with greyscale pre-processing.",
    ),
    ImageType.COLOUR_SIMPLE: TraceStrategy(
        primary_engine=TraceEngine.INKSCAPE,
        fallback_engine=TraceEngine.VTRACER,
        reason="Simple colour palette — Inkscape multi-colour tracing.",
    ),
    ImageType.COLOUR_COMPLEX: TraceStrategy(
        primary_engine=TraceEngine.INKSCAPE,
        fallback_engine=TraceEngine.VTRACER,
        reason="Complex colour palette — Inkscape full-colour tracing.",
    ),
}


# ---------------------------------------------------------------------------
# Selector (Sprint 3 implementation target)
# ---------------------------------------------------------------------------


class TraceStrategySelector:
    """Selects the optimal trace engine and parameters for a classified image.

    .. warning::

        **Sprint 3 placeholder.**  Calling :meth:`select` raises
        :exc:`NotImplementedError`.  The class structure is final; only the
        implementation body is missing.

    Parameters
    ----------
    vtracer_available:
        Whether VTracer is installed on PATH.  When ``False``, strategies
        that list VTracer as a fallback will have ``fallback_engine=None``.
    """

    def __init__(self, *, vtracer_available: bool = False) -> None:
        self._vtracer_available = vtracer_available

    def select(
        self,
        classification: ClassificationResult,
        *,
        preset_name: str = "default",
    ) -> TraceStrategy:
        """Select the optimal :class:`TraceStrategy` for *classification*.

        Parameters
        ----------
        classification:
            Result of :class:`~vector_tracer_pro.core.classifier.ImageClassifier`.
        preset_name:
            Active marketplace preset name (e.g. ``"adobe_stock"``).  Used
            in Sprint 3 to apply preset-specific engine parameter overrides.

        Returns
        -------
        TraceStrategy
            Resolved engine selection and parameters.

        Raises
        ------
        NotImplementedError
            **Sprint 3 target** — not yet implemented.
        """
        raise NotImplementedError(
            "TraceStrategySelector.select() is a Sprint 3 deliverable. "
            "Use _DEFAULT_STRATEGY_MAP for read-only reference mapping."
        )

    def default_for(self, image_type: ImageType) -> TraceStrategy:
        """Return the default strategy for *image_type* (no preset overrides).

        This method is safe to call before Sprint 3 — it consults
        :data:`_DEFAULT_STRATEGY_MAP` directly without any preset logic.
        VTracer fallback is suppressed if ``vtracer_available=False``.

        Parameters
        ----------
        image_type:
            The image classification type.

        Returns
        -------
        TraceStrategy
            Default strategy, potentially with VTracer fallback removed.
        """
        base = _DEFAULT_STRATEGY_MAP[image_type]
        if not self._vtracer_available and base.fallback_engine is TraceEngine.VTRACER:
            return TraceStrategy(
                primary_engine=base.primary_engine,
                fallback_engine=None,
                reason=base.reason + " (VTracer unavailable; no fallback.)",
                engine_params=base.engine_params,
            )
        return base
