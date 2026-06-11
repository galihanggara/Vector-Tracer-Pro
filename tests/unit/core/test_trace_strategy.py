"""
tests.unit.core.test_trace_strategy
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Unit tests for :mod:`vector_tracer_pro.core.trace_strategy`.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from vector_tracer_pro.core.classifier import ClassificationResult, ImageType
from vector_tracer_pro.core.exceptions import TracingError
from vector_tracer_pro.core.trace_strategy import (
    TraceEngine,
    TracingStrategy,
    PotraceTracingStrategy,
    InkscapeTracingStrategy,
    VTracerTracingStrategy,
    FallbackTracingStrategy,
    TraceStrategySelector,
)


@pytest.mark.unit
class TestTraceEngine:
    def test_enum_members(self) -> None:
        assert TraceEngine.POTRACE.value == "potrace"
        assert TraceEngine.INKSCAPE.value == "inkscape"
        assert TraceEngine.VTRACER.value == "vtracer"


@pytest.mark.unit
class TestTracingStrategyHierarchy:
    def test_cannot_instantiate_abc(self) -> None:
        with pytest.raises(TypeError):
            # TracingStrategy has abstract methods / properties
            TracingStrategy(reason="ABC")  # type: ignore[abstract]

    def test_potrace_strategy_properties(self) -> None:
        ts = PotraceTracingStrategy(reason="Test mono", params={"turdsize": 10})
        assert ts.primary_engine == TraceEngine.POTRACE
        assert ts.fallback_engine is None
        assert ts.engine_params == {"turdsize": 10}
        assert ts.uses_potrace is True
        assert ts.uses_inkscape is False
        assert ts.uses_vtracer is False
        
        with pytest.raises(NotImplementedError):
            ts.execute(Path("in.bmp"), Path("out.svg"))

    def test_inkscape_strategy_properties(self) -> None:
        ts = InkscapeTracingStrategy(reason="Test color")
        assert ts.primary_engine == TraceEngine.INKSCAPE
        assert ts.fallback_engine is None
        assert ts.uses_potrace is False
        assert ts.uses_inkscape is True
        assert ts.uses_vtracer is False
        
        with pytest.raises(NotImplementedError):
            ts.execute(Path("in.bmp"), Path("out.svg"))

    def test_vtracer_strategy_properties(self) -> None:
        ts = VTracerTracingStrategy(reason="Test vtracer")
        assert ts.primary_engine == TraceEngine.VTRACER
        assert ts.fallback_engine is None
        assert ts.uses_potrace is False
        assert ts.uses_inkscape is False
        assert ts.uses_vtracer is True
        
        with pytest.raises(NotImplementedError):
            ts.execute(Path("in.bmp"), Path("out.svg"))

    def test_fallback_strategy_properties(self) -> None:
        primary = InkscapeTracingStrategy(reason="Primary Inkscape", params={"colors": 8})
        fallback = VTracerTracingStrategy(reason="Fallback VTracer")
        ts = FallbackTracingStrategy(primary=primary, fallback=fallback, reason="Fallback composite")
        
        assert ts.primary_engine == TraceEngine.INKSCAPE
        assert ts.fallback_engine == TraceEngine.VTRACER
        assert ts.engine_params == {"colors": 8}
        assert ts.uses_potrace is False
        assert ts.uses_inkscape is True
        assert ts.uses_vtracer is True

    def test_string_representation(self) -> None:
        ts = PotraceTracingStrategy(reason="Mono reason")
        assert "engine=potrace" in str(ts)
        assert "Mono reason" in str(ts)

        primary = InkscapeTracingStrategy(reason="Inkscape")
        fallback = VTracerTracingStrategy(reason="VTracer")
        ts_fallback = FallbackTracingStrategy(primary=primary, fallback=fallback, reason="Color reason")
        assert "fallback: vtracer" in str(ts_fallback)


@pytest.mark.unit
class TestFallbackStrategyExecution:
    def test_fallback_execution_success(self) -> None:
        primary = MagicMock(spec=TracingStrategy)
        fallback = MagicMock(spec=TracingStrategy)
        
        ts = FallbackTracingStrategy(primary=primary, fallback=fallback, reason="Test execution")
        ts.execute(Path("in.bmp"), Path("out.svg"))
        
        primary.execute.assert_called_once_with(Path("in.bmp"), Path("out.svg"))
        fallback.execute.assert_not_called()

    def test_fallback_execution_failure_bubbles_to_fallback(self) -> None:
        primary = MagicMock(spec=TracingStrategy)
        primary.execute.side_effect = TracingError("Primary failed")
        fallback = MagicMock(spec=TracingStrategy)
        
        ts = FallbackTracingStrategy(primary=primary, fallback=fallback, reason="Test execution")
        ts.execute(Path("in.bmp"), Path("out.svg"))
        
        primary.execute.assert_called_once_with(Path("in.bmp"), Path("out.svg"))
        fallback.execute.assert_called_once_with(Path("in.bmp"), Path("out.svg"))


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

    def test_select_returns_default(self) -> None:
        selector = TraceStrategySelector()
        mock_classification = ClassificationResult(
            image_type=ImageType.MONOCHROME,
            unique_colour_count=2,
            average_saturation=0.0,
            confidence=1.0,
            recommended_engine="potrace",
        )
        strategy = selector.select(mock_classification)
        assert strategy.primary_engine == TraceEngine.POTRACE
