"""
tests.unit.core.test_trace_strategy
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Unit tests for :mod:`vector_tracer_pro.core.trace_strategy`.
"""

from __future__ import annotations

from pathlib import Path
import pytest

from vector_tracer_pro.core.classifier import ClassificationResult, ImageType
from vector_tracer_pro.core.trace_strategy import (
    TraceEngine,
    TraceStrategy,
    TraceStrategySelector,
)


@pytest.mark.unit
class TestTraceEngine:
    def test_enum_members(self) -> None:
        assert TraceEngine.POTRACE.value == "potrace"
        assert TraceEngine.INKSCAPE.value == "inkscape"
        assert TraceEngine.VTRACER.value == "vtracer"


@pytest.mark.unit
class TestTraceStrategy:
    def test_uses_flags(self) -> None:
        ts = TraceStrategy(
            primary_engine=TraceEngine.POTRACE,
            fallback_engine=None,
            reason="Test mono",
        )
        assert ts.uses_potrace is True
        assert ts.uses_inkscape is False
        assert ts.uses_vtracer is False

        ts_color = TraceStrategy(
            primary_engine=TraceEngine.INKSCAPE,
            fallback_engine=TraceEngine.VTRACER,
            reason="Test color",
        )
        assert ts_color.uses_potrace is False
        assert ts_color.uses_inkscape is True
        assert ts_color.uses_vtracer is True

    def test_string_representation(self) -> None:
        ts = TraceStrategy(
            primary_engine=TraceEngine.POTRACE,
            fallback_engine=None,
            reason="Mono reason",
        )
        assert "primary_engine=TraceEngine.POTRACE" not in str(ts)
        assert "engine=potrace" in str(ts)
        assert "Mono reason" in str(ts)

        ts_fallback = TraceStrategy(
            primary_engine=TraceEngine.INKSCAPE,
            fallback_engine=TraceEngine.VTRACER,
            reason="Color reason",
        )
        assert "fallback: vtracer" in str(ts_fallback)


@pytest.mark.unit
class TestTraceStrategySelector:
    def test_default_for_monochrome(self) -> None:
        selector = TraceStrategySelector(vtracer_available=False)
        strategy = selector.default_for(ImageType.MONOCHROME)
        assert strategy.primary_engine == TraceEngine.POTRACE
        assert strategy.fallback_engine is None

    def test_default_for_colour_with_vtracer(self) -> None:
        selector = TraceStrategySelector(vtracer_available=True)
        strategy = selector.default_for(ImageType.COLOUR_SIMPLE)
        assert strategy.primary_engine == TraceEngine.INKSCAPE
        assert strategy.fallback_engine == TraceEngine.VTRACER

    def test_default_for_colour_without_vtracer(self) -> None:
        selector = TraceStrategySelector(vtracer_available=False)
        strategy = selector.default_for(ImageType.COLOUR_SIMPLE)
        assert strategy.primary_engine == TraceEngine.INKSCAPE
        assert strategy.fallback_engine is None
        assert "VTracer unavailable" in strategy.reason

    def test_select_raises_not_implemented(self) -> None:
        selector = TraceStrategySelector()
        mock_classification = ClassificationResult(
            image_type=ImageType.MONOCHROME,
            unique_colour_count=2,
            average_saturation=0.0,
            confidence=1.0,
            recommended_engine="potrace",
        )
        with pytest.raises(NotImplementedError) as exc_info:
            selector.select(mock_classification)
        assert "select() is a Sprint 3 deliverable" in str(exc_info.value)
