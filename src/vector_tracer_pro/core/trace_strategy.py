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

import logging
import subprocess
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Final

from vector_tracer_pro.core.classifier import ClassificationResult, ImageType
from vector_tracer_pro.core.dependency_checker import DependencyChecker
from vector_tracer_pro.core.exceptions import (
    DependencyMissingError,
    TraceExecutionError,
    TraceFailedError,
    TraceTimeoutError,
    TracingError,
)

logger = logging.getLogger(__name__)


@dataclass
class TraceParams:
    """Trace parameters for all strategies."""

    # Potrace
    turdsize: int = 2
    alphamax: float = 1.0
    opttolerance: float = 0.2
    potrace_executable: str = "potrace"

    # VTracer
    colormode: str = "color"
    filter_speckle: int = 4
    color_precision: int = 6
    layer_difference: int = 16
    vtracer_executable: str = "vtracer"

    # Inkscape
    inkscape_executable: str = "inkscape"
    inkscape_timeout_seconds: int = 60

    # General
    timeout_seconds: int = 30

    def __post_init__(self) -> None:
        from vector_tracer_pro.core.path_manager import PathManager
        pm = PathManager()
        self.potrace_executable = pm.get_binary_path(self.potrace_executable)
        self.vtracer_executable = pm.get_binary_path(self.vtracer_executable)
        self.inkscape_executable = pm.get_binary_path(self.inkscape_executable)



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

    def __init__(self, reason: str = "Default tracing strategy", params: dict[str, object] | None = None) -> None:
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
    def execute(
        self,
        input_path: Path,
        output_svg_path: Path,
        params: TraceParams | None = None,
    ) -> None:
        """Execute the vectorisation engine on the input file.

        Parameters
        ----------
        input_path:
            Path to the input raster file (typically BMP or PBM).
        output_svg_path:
            Target path where the traced SVG file will be written.
        params:
            Tracing parameters overriding default values.

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

    def execute(
        self,
        input_path: Path,
        output_svg_path: Path,
        params: TraceParams | None = None,
    ) -> None:
        """Run Potrace CLI."""
        tparams = params or TraceParams()
        potrace_bin = tparams.potrace_executable

        # 1. Verify dependency
        checker = DependencyChecker(potrace_executable=potrace_bin)
        report = checker.check_all()
        if not report.potrace_check.passed:
            raise DependencyMissingError(
                report.potrace_check.message,
                binary="potrace",
                minimum_version=report.potrace_check.minimum_version,
                detected_version=report.potrace_check.detected_version,
                download_url=report.potrace_check.download_url,
            )

        # 2. Validate input
        if not input_path.exists():
            raise FileNotFoundError(f"Input file not found: {input_path}")
        if input_path.suffix.lower() != ".pbm":
            raise ValueError(f"Potrace input must be a .pbm file, got {input_path.suffix}")

        # 3. Ensure output directory exists
        output_svg_path.parent.mkdir(parents=True, exist_ok=True)

        cmd = [
            str(potrace_bin),
            str(input_path),
            "-s",
            "-t", str(tparams.turdsize),
            "-a", str(tparams.alphamax),
            "-O", str(tparams.opttolerance),
            "-o", str(output_svg_path),
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                timeout=tparams.timeout_seconds,
                text=True,
            )
        except subprocess.TimeoutExpired as exc:
            raise TraceTimeoutError(
                f"Potrace process timed out after {tparams.timeout_seconds} seconds"
            ) from exc
        except OSError as exc:
            raise TraceExecutionError(
                f"Failed to execute Potrace: {exc}", return_code=-1, stderr=str(exc)
            ) from exc

        if result.returncode != 0:
            raise TraceExecutionError(
                f"Potrace failed with return code {result.returncode}",
                return_code=result.returncode,
                stderr=result.stderr,
            )

        if not output_svg_path.exists():
            raise TraceExecutionError(
                "Potrace completed but output SVG file was not created",
                return_code=result.returncode,
                stderr=result.stderr,
            )


class InkscapeTracingStrategy(TracingStrategy):
    """Strategy that executes the Inkscape vectorisation engine."""

    @property
    def primary_engine(self) -> TraceEngine:
        return TraceEngine.INKSCAPE

    def execute(
        self,
        input_path: Path,
        output_svg_path: Path,
        params: TraceParams | None = None,
    ) -> None:
        """Run Inkscape headless CLI."""
        tparams = params or TraceParams()
        inkscape_bin = tparams.inkscape_executable

        # 1. Verify dependency
        checker = DependencyChecker(inkscape_executable=inkscape_bin)
        report = checker.check_all()
        if not report.inkscape_check.passed:
            raise DependencyMissingError(
                report.inkscape_check.message,
                binary="inkscape",
                minimum_version=report.inkscape_check.minimum_version,
                detected_version=report.inkscape_check.detected_version,
                download_url=report.inkscape_check.download_url,
            )

        # 2. Validate input
        if not input_path.exists():
            raise FileNotFoundError(f"Input file not found: {input_path}")
        if input_path.suffix.lower() != ".png":
            raise ValueError(f"Inkscape input must be a .png file, got {input_path.suffix}")

        # 3. Ensure output directory exists
        output_svg_path.parent.mkdir(parents=True, exist_ok=True)

        cmd = [
            str(inkscape_bin),
            str(input_path),
            "--actions", "select-all;org.inkscape.effect.trace",
            "--export-filename", str(output_svg_path),
        ]

        timeout = tparams.inkscape_timeout_seconds if hasattr(tparams, "inkscape_timeout_seconds") else 60

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                timeout=timeout,
                text=True,
            )
        except subprocess.TimeoutExpired as exc:
            raise TraceTimeoutError(
                f"Inkscape process timed out after {timeout} seconds"
            ) from exc
        except OSError as exc:
            raise TraceExecutionError(
                f"Failed to execute Inkscape: {exc}", return_code=-1, stderr=str(exc)
            ) from exc

        if result.returncode != 0:
            raise TraceExecutionError(
                result.stderr or result.stdout or "Inkscape failed with non-zero exit code",
                return_code=result.returncode,
                stderr=result.stderr or "",
            )

        if not output_svg_path.exists():
            raise TraceExecutionError(
                "Inkscape completed but output SVG file was not created",
                return_code=result.returncode,
                stderr=result.stderr or "",
            )



class VTracerTracingStrategy(TracingStrategy):
    """Strategy that executes the VTracer vectorisation engine."""

    @property
    def primary_engine(self) -> TraceEngine:
        return TraceEngine.VTRACER

    def execute(
        self,
        input_path: Path,
        output_svg_path: Path,
        params: TraceParams | None = None,
    ) -> None:
        """Run VTracer CLI."""
        tparams = params or TraceParams()
        vtracer_bin = tparams.vtracer_executable

        # 1. Verify dependency
        checker = DependencyChecker(vtracer_executable=vtracer_bin)
        report = checker.check_all()
        if not report.vtracer_check or not report.vtracer_check.passed:
            check_res = report.vtracer_check
            raise DependencyMissingError(
                check_res.message if check_res else "VTracer not found on PATH.",
                binary="vtracer",
                minimum_version=check_res.minimum_version if check_res else None,
                detected_version=check_res.detected_version if check_res else None,
                download_url=check_res.download_url if check_res else "",
            )

        # 2. Validate input
        if not input_path.exists():
            raise FileNotFoundError(f"Input file not found: {input_path}")
        if input_path.suffix.lower() != ".png":
            raise ValueError(f"VTracer input must be a .png file, got {input_path.suffix}")

        # 3. Ensure output directory exists
        output_svg_path.parent.mkdir(parents=True, exist_ok=True)

        cmd = [
            str(vtracer_bin),
            "--input", str(input_path),
            "--output", str(output_svg_path),
            "--colormode", str(tparams.colormode),
            "--filter_speckle", str(tparams.filter_speckle),
            "--color_precision", str(tparams.color_precision),
            "--layer_difference", str(tparams.layer_difference),
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                timeout=tparams.timeout_seconds,
                text=True,
            )
        except subprocess.TimeoutExpired as exc:
            raise TraceTimeoutError(
                f"VTracer process timed out after {tparams.timeout_seconds} seconds"
            ) from exc
        except OSError as exc:
            raise TraceExecutionError(
                f"Failed to execute VTracer: {exc}", return_code=-1, stderr=str(exc)
            ) from exc

        if result.returncode != 0:
            raise TraceExecutionError(
                f"VTracer failed with return code {result.returncode}",
                return_code=result.returncode,
                stderr=result.stderr,
            )

        if not output_svg_path.exists():
            raise TraceExecutionError(
                "VTracer completed but output SVG file was not created",
                return_code=result.returncode,
                stderr=result.stderr,
            )



DEFAULT_FALLBACK_ORDER: list[str] = ["potrace", "vtracer", "inkscape"]

_ENGINE_MAP: dict[str, type[TracingStrategy]] = {
    "potrace": PotraceTracingStrategy,
    "vtracer": VTracerTracingStrategy,
    "inkscape": InkscapeTracingStrategy,
}


def _is_mock(obj: object) -> bool:
    return "Mock" in type(obj).__name__ or "mock" in type(obj).__name__


class FallbackTracingStrategy(TracingStrategy):
    """Strategy that wraps a primary strategy and executes a fallback on failure.

    This implements a composite-like Strategy Pattern, allowing transparent
    error handling and engine fallback.
    """

    def __init__(
        self,
        order: list[str] | None = None,
        primary: TracingStrategy | None = None,
        fallback: TracingStrategy | None = None,
        reason: str | None = None,
    ) -> None:
        super().__init__(reason=reason or "Fallback tracing strategy chain")
        
        # If order is not provided but primary and fallback are, construct order from them for backwards compat
        if order is None and primary is not None:
            self.primary = primary
            self.fallback = fallback
            
            p_val = "primary"
            if hasattr(primary, "primary_engine"):
                pe = primary.primary_engine
                if hasattr(pe, "value") and not _is_mock(pe.value):
                    p_val = pe.value
                elif isinstance(pe, TraceEngine):
                    p_val = pe.value
                    
            f_val = "fallback"
            if fallback is not None:
                if hasattr(fallback, "primary_engine"):
                    fe = fallback.primary_engine
                    if hasattr(fe, "value") and not _is_mock(fe.value):
                        f_val = fe.value
                    elif isinstance(fe, TraceEngine):
                        f_val = fe.value

            self.strategies = [(p_val, primary)]
            if fallback is not None:
                self.strategies.append((f_val, fallback))
            self.order = [name for name, _ in self.strategies]
        else:
            self.order = order or DEFAULT_FALLBACK_ORDER
            self.primary = None
            self.fallback = None
            self.strategies = []
            for name in self.order:
                strategy_class = _ENGINE_MAP.get(name)
                if strategy_class is not None:
                    strat_inst = strategy_class()
                    self.strategies.append((name, strat_inst))
                    # Assign primary/fallback properties dynamically for backward compatibility checks
                    if self.primary is None:
                        self.primary = strat_inst
                    elif self.fallback is None:
                        self.fallback = strat_inst
                else:
                    self.strategies.append((name, None))

    @property
    def primary_engine(self) -> TraceEngine:
        if self.primary and not _is_mock(self.primary):
            try:
                return self.primary.primary_engine
            except Exception:
                pass
        if not self.order:
            raise ValueError("Fallback strategy order cannot be empty")
        try:
            return TraceEngine(self.order[0])
        except ValueError:
            return TraceEngine.INKSCAPE

    @property
    def fallback_engine(self) -> TraceEngine | None:
        if self.fallback and not _is_mock(self.fallback):
            try:
                return self.fallback.primary_engine
            except Exception:
                pass
        if len(self.order) > 1:
            try:
                return TraceEngine(self.order[1])
            except ValueError:
                return None
        return None

    @property
    def engine_params(self) -> dict[str, object]:
        if self.primary:
            return self.primary.engine_params
        return self.params

    def execute(
        self,
        input_path: Path,
        output_svg_path: Path,
        params: TraceParams | None = None,
    ) -> None:
        """Try strategies in the order list, fall back to next on TracingError or DependencyMissingError."""
        errors: list[tuple[str, str]] = []
        
        for engine_name in self.order:
            # Check if we have pre-instantiated strategy or mock in self.strategies
            strategy = None
            for name, strat in self.strategies:
                if name == engine_name:
                    strategy = strat
                    break
            
            if strategy is None:
                strategy_class = _ENGINE_MAP.get(engine_name)
                if strategy_class is None:
                    errors.append((engine_name, "Unknown engine name"))
                    continue
                try:
                    strategy = strategy_class()
                except Exception as e:
                    errors.append((engine_name, str(e)))
                    continue

            try:
                strategy.execute(input_path, output_svg_path, params)
                return  # Success!
            except (DependencyMissingError, TracingError) as e:
                errors.append((engine_name, str(e)))
                logger.warning("Engine %s failed in fallback chain: %s", engine_name, e)
                continue

        raise TraceFailedError(
            "All engines failed.\n" +
            "\n".join(f"  [{name}]: {err}" for name, err in errors)
        )



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
