"""
tests.unit.core.test_trace_strategy
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Unit tests for :mod:`vector_tracer_pro.core.trace_strategy`.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from vector_tracer_pro.core.classifier import ClassificationResult, ImageType
from vector_tracer_pro.core.exceptions import (
    DependencyMissingError,
    TraceExecutionError,
    TraceFailedError,
    TraceTimeoutError,
    TracingError,
)
from vector_tracer_pro.core.trace_strategy import (
    FallbackTracingStrategy,
    InkscapeTracingStrategy,
    PotraceTracingStrategy,
    TraceEngine,
    TraceParams,
    TraceStrategySelector,
    TracingStrategy,
    VTracerTracingStrategy,
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

    def test_inkscape_strategy_properties(self) -> None:
        ts = InkscapeTracingStrategy(reason="Test color")
        assert ts.primary_engine == TraceEngine.INKSCAPE
        assert ts.fallback_engine is None
        assert ts.uses_potrace is False
        assert ts.uses_inkscape is True
        assert ts.uses_vtracer is False

    def test_vtracer_strategy_properties(self) -> None:
        ts = VTracerTracingStrategy(reason="Test vtracer")
        assert ts.primary_engine == TraceEngine.VTRACER
        assert ts.fallback_engine is None
        assert ts.uses_potrace is False
        assert ts.uses_inkscape is False
        assert ts.uses_vtracer is True

    def test_fallback_strategy_properties(self) -> None:
        primary = InkscapeTracingStrategy(reason="Primary Inkscape", params={"colors": 8})
        fallback = VTracerTracingStrategy(reason="Fallback VTracer")
        ts = FallbackTracingStrategy(
            primary=primary, fallback=fallback, reason="Fallback composite"
        )

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
        ts_fallback = FallbackTracingStrategy(
            primary=primary, fallback=fallback, reason="Color reason"
        )
        assert "fallback: vtracer" in str(ts_fallback)


@pytest.mark.unit
class TestFallbackStrategyExecution:
    def test_fallback_execution_success(self) -> None:
        primary = MagicMock(spec=TracingStrategy)
        fallback = MagicMock(spec=TracingStrategy)

        ts = FallbackTracingStrategy(primary=primary, fallback=fallback, reason="Test execution")
        ts.execute(Path("in.bmp"), Path("out.svg"))

        primary.execute.assert_called_once_with(Path("in.bmp"), Path("out.svg"), None)
        fallback.execute.assert_not_called()

    def test_fallback_execution_failure_bubbles_to_fallback(self) -> None:
        primary = MagicMock(spec=TracingStrategy)
        primary.execute.side_effect = TracingError("Primary failed")
        fallback = MagicMock(spec=TracingStrategy)

        ts = FallbackTracingStrategy(primary=primary, fallback=fallback, reason="Test execution")
        ts.execute(Path("in.bmp"), Path("out.svg"))

        primary.execute.assert_called_once_with(Path("in.bmp"), Path("out.svg"), None)
        fallback.execute.assert_called_once_with(Path("in.bmp"), Path("out.svg"), None)


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


@pytest.mark.unit
class TestPotraceTracingStrategy:
    @patch("vector_tracer_pro.core.trace_strategy.DependencyChecker")
    @patch("subprocess.run")
    def test_potrace_calls_correct_command(self, mock_run, mock_checker, tmp_path):
        mock_report = MagicMock()
        mock_report.potrace_check.passed = True
        mock_checker.return_value.check_all.return_value = mock_report

        input_file = tmp_path / "in.pbm"
        input_file.write_text("fake pbm")
        output_file = tmp_path / "out.svg"

        def side_effect(*args, **kwargs):
            output_file.write_text("<svg></svg>")
            return MagicMock(returncode=0)

        mock_run.side_effect = side_effect

        strategy = PotraceTracingStrategy(reason="Test Potrace")
        params = TraceParams(turdsize=15, alphamax=0.5, opttolerance=0.1)
        strategy.execute(input_file, output_file, params)

        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        from pathlib import Path

        assert Path(args[0]).stem.lower() == "potrace"
        assert args[1] == str(input_file)
        assert "-s" in args
        assert "-t" in args
        assert args[args.index("-t") + 1] == "15"
        assert "-a" in args
        assert args[args.index("-a") + 1] == "0.5"
        assert "-O" in args
        assert args[args.index("-O") + 1] == "0.1"
        assert "-o" in args
        assert args[args.index("-o") + 1] == str(output_file)

    @patch("vector_tracer_pro.core.trace_strategy.DependencyChecker")
    def test_potrace_missing_dependency(self, mock_checker, tmp_path):
        mock_report = MagicMock()
        mock_report.potrace_check.passed = False
        mock_report.potrace_check.message = "Potrace missing"
        mock_report.potrace_check.minimum_version = "1.16"
        mock_report.potrace_check.detected_version = None
        mock_report.potrace_check.download_url = "http://potrace"
        mock_checker.return_value.check_all.return_value = mock_report

        strategy = PotraceTracingStrategy(reason="Test Potrace")
        with pytest.raises(DependencyMissingError) as exc_info:
            strategy.execute(tmp_path / "in.pbm", tmp_path / "out.svg")
        assert "Potrace missing" in str(exc_info.value)
        assert exc_info.value.binary == "potrace"

    @patch("vector_tracer_pro.core.trace_strategy.DependencyChecker")
    def test_potrace_invalid_input_ext(self, mock_checker, tmp_path):
        mock_report = MagicMock()
        mock_report.potrace_check.passed = True
        mock_checker.return_value.check_all.return_value = mock_report

        strategy = PotraceTracingStrategy(reason="Test Potrace")
        input_file = tmp_path / "in.jpg"
        input_file.write_text("fake jpeg")
        with pytest.raises(ValueError) as exc_info:
            strategy.execute(input_file, tmp_path / "out.svg")
        assert "must be a .pbm file" in str(exc_info.value)

    @patch("vector_tracer_pro.core.trace_strategy.DependencyChecker")
    @patch("subprocess.run")
    def test_potrace_timeout_error(self, mock_run, mock_checker, tmp_path):
        mock_report = MagicMock()
        mock_report.potrace_check.passed = True
        mock_checker.return_value.check_all.return_value = mock_report

        input_file = tmp_path / "in.pbm"
        input_file.write_text("fake pbm")

        mock_run.side_effect = subprocess.TimeoutExpired(cmd=["potrace"], timeout=30)

        strategy = PotraceTracingStrategy(reason="Test Potrace")
        with pytest.raises(TraceTimeoutError) as exc_info:
            strategy.execute(input_file, tmp_path / "out.svg")
        assert "timed out" in str(exc_info.value)

    @patch("vector_tracer_pro.core.trace_strategy.DependencyChecker")
    @patch("subprocess.run")
    def test_potrace_execution_error(self, mock_run, mock_checker, tmp_path):
        mock_report = MagicMock()
        mock_report.potrace_check.passed = True
        mock_checker.return_value.check_all.return_value = mock_report

        input_file = tmp_path / "in.pbm"
        input_file.write_text("fake pbm")

        mock_run.return_value = MagicMock(returncode=1, stderr="Something went wrong")

        strategy = PotraceTracingStrategy(reason="Test Potrace")
        with pytest.raises(TraceExecutionError) as exc_info:
            strategy.execute(input_file, tmp_path / "out.svg")
        assert "failed with return code 1" in str(exc_info.value)
        assert exc_info.value.stderr == "Something went wrong"
        assert exc_info.value.return_code == 1


@pytest.mark.unit
class TestVTracerTracingStrategy:
    @patch("vector_tracer_pro.core.trace_strategy.DependencyChecker")
    @patch("subprocess.run")
    def test_vtracer_calls_correct_command(self, mock_run, mock_checker, tmp_path):
        mock_report = MagicMock()
        mock_report.vtracer_check.passed = True
        mock_checker.return_value.check_all.return_value = mock_report

        input_file = tmp_path / "in.png"
        input_file.write_text("fake png")
        output_file = tmp_path / "out.svg"

        def side_effect(*args, **kwargs):
            output_file.write_text("<svg></svg>")
            return MagicMock(returncode=0)

        mock_run.side_effect = side_effect

        strategy = VTracerTracingStrategy(reason="Test VTracer")
        params = TraceParams(
            colormode="color", filter_speckle=10, color_precision=5, layer_difference=20
        )
        strategy.execute(input_file, output_file, params)

        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        from pathlib import Path

        assert Path(args[0]).stem.lower() == "vtracer"
        assert "--input" in args
        assert args[args.index("--input") + 1] == str(input_file)
        assert "--output" in args
        assert args[args.index("--output") + 1] == str(output_file)
        assert "--colormode" in args
        assert args[args.index("--colormode") + 1] == "color"
        assert "--filter_speckle" in args
        assert args[args.index("--filter_speckle") + 1] == "10"
        assert "--color_precision" in args
        assert args[args.index("--color_precision") + 1] == "5"
        assert "--layer_difference" in args
        assert args[args.index("--layer_difference") + 1] == "20"

    @patch("vector_tracer_pro.core.trace_strategy.DependencyChecker")
    def test_vtracer_missing_dependency(self, mock_checker, tmp_path):
        mock_report = MagicMock()
        mock_report.vtracer_check.passed = False
        mock_report.vtracer_check.message = "VTracer missing"
        mock_report.vtracer_check.minimum_version = "0.6.0"
        mock_report.vtracer_check.detected_version = None
        mock_report.vtracer_check.download_url = "http://vtracer"
        mock_checker.return_value.check_all.return_value = mock_report

        strategy = VTracerTracingStrategy(reason="Test VTracer")
        with pytest.raises(DependencyMissingError) as exc_info:
            strategy.execute(tmp_path / "in.png", tmp_path / "out.svg")
        assert "VTracer missing" in str(exc_info.value)
        assert exc_info.value.binary == "vtracer"

    @patch("vector_tracer_pro.core.trace_strategy.DependencyChecker")
    def test_vtracer_invalid_input_ext(self, mock_checker, tmp_path):
        mock_report = MagicMock()
        mock_report.vtracer_check.passed = True
        mock_checker.return_value.check_all.return_value = mock_report

        strategy = VTracerTracingStrategy(reason="Test VTracer")
        input_file = tmp_path / "in.jpg"
        input_file.write_text("fake jpeg")
        with pytest.raises(ValueError) as exc_info:
            strategy.execute(input_file, tmp_path / "out.svg")
        assert "must be a .png file" in str(exc_info.value)

    @patch("vector_tracer_pro.core.trace_strategy.DependencyChecker")
    @patch("subprocess.run")
    def test_vtracer_timeout_error(self, mock_run, mock_checker, tmp_path):
        mock_report = MagicMock()
        mock_report.vtracer_check.passed = True
        mock_checker.return_value.check_all.return_value = mock_report

        input_file = tmp_path / "in.png"
        input_file.write_text("fake png")

        mock_run.side_effect = subprocess.TimeoutExpired(cmd=["vtracer"], timeout=30)

        strategy = VTracerTracingStrategy(reason="Test VTracer")
        with pytest.raises(TraceTimeoutError) as exc_info:
            strategy.execute(input_file, tmp_path / "out.svg")
        assert "timed out" in str(exc_info.value)

    @patch("vector_tracer_pro.core.trace_strategy.DependencyChecker")
    @patch("subprocess.run")
    def test_vtracer_execution_error(self, mock_run, mock_checker, tmp_path):
        mock_report = MagicMock()
        mock_report.vtracer_check.passed = True
        mock_checker.return_value.check_all.return_value = mock_report

        input_file = tmp_path / "in.png"
        input_file.write_text("fake png")

        mock_run.return_value = MagicMock(returncode=1, stderr="Something went wrong")

        strategy = VTracerTracingStrategy(reason="Test VTracer")
        with pytest.raises(TraceExecutionError) as exc_info:
            strategy.execute(input_file, tmp_path / "out.svg")
        assert "failed with return code 1" in str(exc_info.value)
        assert exc_info.value.stderr == "Something went wrong"
        assert exc_info.value.return_code == 1


@pytest.mark.unit
class TestInkscapeTracingStrategy:
    @patch("vector_tracer_pro.core.trace_strategy.DependencyChecker")
    @patch("subprocess.run")
    def test_inkscape_calls_correct_command(self, mock_run, mock_checker, tmp_path):
        mock_report = MagicMock()
        mock_report.inkscape_check.passed = True
        mock_checker.return_value.check_all.return_value = mock_report

        input_file = tmp_path / "in.png"
        input_file.write_text("fake png")
        output_file = tmp_path / "out.svg"

        def side_effect(*args, **kwargs):
            output_file.write_text("<svg></svg>")
            return MagicMock(returncode=0)

        mock_run.side_effect = side_effect

        strategy = InkscapeTracingStrategy(reason="Test Inkscape")
        params = TraceParams(inkscape_timeout_seconds=90)
        strategy.execute(input_file, output_file, params)

        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        kwargs = mock_run.call_args[1]
        from pathlib import Path

        assert Path(args[0]).stem.lower() == "inkscape"
        assert args[1] == str(input_file)
        assert "--actions" in args
        assert args[args.index("--actions") + 1] == "select-all;org.inkscape.effect.trace"
        assert "--export-filename" in args
        assert args[args.index("--export-filename") + 1] == str(output_file)
        assert kwargs["timeout"] == 90

    @patch("vector_tracer_pro.core.trace_strategy.DependencyChecker")
    @patch("subprocess.run")
    def test_inkscape_succeeds_despite_stderr_output(self, mock_run, mock_checker, tmp_path):
        """Inkscape menulis warning ke stderr meskipun sukses — tidak boleh raise error."""
        mock_report = MagicMock()
        mock_report.inkscape_check.passed = True
        mock_checker.return_value.check_all.return_value = mock_report

        input_file = tmp_path / "in.png"
        input_file.write_text("fake png")
        output_file = tmp_path / "out.svg"

        def side_effect(*args, **kwargs):
            output_file.write_text("<svg></svg>")
            return MagicMock(
                returncode=0,
                stderr="Inkscape 1.2.0 warning: deprecated GTK API\ntracing...",
                stdout="",
            )

        mock_run.side_effect = side_effect

        strategy = InkscapeTracingStrategy(reason="Test Inkscape")
        # Harus tidak raise apapun
        strategy.execute(input_file, output_file, TraceParams())

    @patch("vector_tracer_pro.core.trace_strategy.DependencyChecker")
    def test_inkscape_missing_dependency(self, mock_checker, tmp_path):
        mock_report = MagicMock()
        mock_report.inkscape_check.passed = False
        mock_report.inkscape_check.message = "Inkscape missing"
        mock_report.inkscape_check.minimum_version = "1.0"
        mock_report.inkscape_check.detected_version = None
        mock_report.inkscape_check.download_url = "http://inkscape"
        mock_checker.return_value.check_all.return_value = mock_report

        strategy = InkscapeTracingStrategy(reason="Test Inkscape")
        with pytest.raises(DependencyMissingError) as exc_info:
            strategy.execute(tmp_path / "in.png", tmp_path / "out.svg")
        assert "Inkscape missing" in str(exc_info.value)
        assert exc_info.value.binary == "inkscape"

    @patch("vector_tracer_pro.core.trace_strategy.DependencyChecker")
    def test_inkscape_invalid_input_ext(self, mock_checker, tmp_path):
        mock_report = MagicMock()
        mock_report.inkscape_check.passed = True
        mock_checker.return_value.check_all.return_value = mock_report

        strategy = InkscapeTracingStrategy(reason="Test Inkscape")
        input_file = tmp_path / "in.jpg"
        input_file.write_text("fake jpeg")
        with pytest.raises(ValueError) as exc_info:
            strategy.execute(input_file, tmp_path / "out.svg")
        assert "must be a .png file" in str(exc_info.value)

    @patch("vector_tracer_pro.core.trace_strategy.DependencyChecker")
    @patch("subprocess.run")
    def test_inkscape_timeout_error(self, mock_run, mock_checker, tmp_path):
        mock_report = MagicMock()
        mock_report.inkscape_check.passed = True
        mock_checker.return_value.check_all.return_value = mock_report

        input_file = tmp_path / "in.png"
        input_file.write_text("fake png")

        mock_run.side_effect = subprocess.TimeoutExpired(cmd=["inkscape"], timeout=60)

        strategy = InkscapeTracingStrategy(reason="Test Inkscape")
        with pytest.raises(TraceTimeoutError) as exc_info:
            strategy.execute(input_file, tmp_path / "out.svg")
        assert "timed out" in str(exc_info.value)

    @patch("vector_tracer_pro.core.trace_strategy.DependencyChecker")
    @patch("subprocess.run")
    def test_inkscape_execution_error(self, mock_run, mock_checker, tmp_path):
        mock_report = MagicMock()
        mock_report.inkscape_check.passed = True
        mock_checker.return_value.check_all.return_value = mock_report

        input_file = tmp_path / "in.png"
        input_file.write_text("fake png")

        mock_run.return_value = MagicMock(returncode=1, stderr="Something went wrong")

        strategy = InkscapeTracingStrategy(reason="Test Inkscape")
        with pytest.raises(TraceExecutionError) as exc_info:
            strategy.execute(input_file, tmp_path / "out.svg")
        assert "Something went wrong" in str(exc_info.value)
        assert exc_info.value.stderr == "Something went wrong"
        assert exc_info.value.return_code == 1


@pytest.mark.unit
class TestFallbackTracingStrategy:
    def test_first_engine_fails_tries_next(self, tmp_path) -> None:
        """First engine raises DependencyMissingError -> VTracer succeeds."""
        strategy1 = MagicMock(spec=TracingStrategy)
        strategy1.execute.side_effect = DependencyMissingError("Potrace missing", binary="potrace")

        strategy2 = MagicMock(spec=TracingStrategy)

        fallback = FallbackTracingStrategy(order=["potrace", "vtracer"])
        fallback.strategies = [("potrace", strategy1), ("vtracer", strategy2)]

        # Should not raise anything
        fallback.execute(tmp_path / "in.png", tmp_path / "out.svg")

        strategy1.execute.assert_called_once()
        strategy2.execute.assert_called_once()

    def test_timeout_triggers_fallback(self, tmp_path) -> None:
        """First engine raises TraceTimeoutError -> VTracer succeeds."""
        strategy1 = MagicMock(spec=TracingStrategy)
        strategy1.execute.side_effect = TraceTimeoutError("Potrace timed out")

        strategy2 = MagicMock(spec=TracingStrategy)

        fallback = FallbackTracingStrategy(order=["potrace", "vtracer"])
        fallback.strategies = [("potrace", strategy1), ("vtracer", strategy2)]

        # Should not raise anything
        fallback.execute(tmp_path / "in.png", tmp_path / "out.svg")

        strategy1.execute.assert_called_once()
        strategy2.execute.assert_called_once()

    def test_all_engines_fail_raises_trace_failed_error(self, tmp_path) -> None:
        """All engines fail -> TraceFailedError.

        Assert: all 3 engine names appear in error message.
        """
        strategy1 = MagicMock(spec=TracingStrategy)
        strategy1.execute.side_effect = DependencyMissingError("Potrace missing", binary="potrace")

        strategy2 = MagicMock(spec=TracingStrategy)
        strategy2.execute.side_effect = TraceTimeoutError("VTracer timed out")

        strategy3 = MagicMock(spec=TracingStrategy)
        strategy3.execute.side_effect = TraceExecutionError("Inkscape crashed", return_code=1)

        fallback = FallbackTracingStrategy(order=["potrace", "vtracer", "inkscape"])
        fallback.strategies = [
            ("potrace", strategy1),
            ("vtracer", strategy2),
            ("inkscape", strategy3),
        ]

        with pytest.raises(TraceFailedError) as exc_info:
            fallback.execute(tmp_path / "in.png", tmp_path / "out.svg")

        assert "[potrace]" in str(exc_info.value)
        assert "[vtracer]" in str(exc_info.value)
        assert "[inkscape]" in str(exc_info.value)

        strategy1.execute.assert_called_once()
        strategy2.execute.assert_called_once()
        strategy3.execute.assert_called_once()

    def test_custom_order_respected(self, tmp_path) -> None:
        """Override order vtracer first -> VTracer is called first."""
        strategy1 = MagicMock(spec=TracingStrategy)
        strategy2 = MagicMock(spec=TracingStrategy)

        fallback = FallbackTracingStrategy(order=["vtracer", "potrace"])
        fallback.strategies = [
            ("vtracer", strategy1),
            ("potrace", strategy2),
        ]

        fallback.execute(tmp_path / "in.png", tmp_path / "out.svg")

        strategy1.execute.assert_called_once()
        strategy2.execute.assert_not_called()
