"""
vector_tracer_pro.workers.trace_worker
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

A QRunnable worker designed to execute the vectorisation Pipeline in a background thread.
"""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import QObject, QRunnable, Signal, Slot

from vector_tracer_pro.core.image.preprocessor import PreprocessConfig
from vector_tracer_pro.core.marketplace_validator import MarketplacePreset
from vector_tracer_pro.core.pipeline import Pipeline, PipelineResult
from vector_tracer_pro.core.trace_strategy import TraceParams

logger = logging.getLogger(__name__)


class TraceWorkerSignals(QObject):
    """Custom signals emitted by the TraceWorker during thread execution."""

    progress = Signal(str, int)  # Emits (step_name, percent)
    finished = Signal(PipelineResult)  # Emits the resulting PipelineResult
    error = Signal(str)  # Emits error message string


class TraceWorker(QRunnable):
    """Worker runnable to trace a single image on a QThreadPool thread."""

    def __init__(
        self,
        pipeline: Pipeline,
        input_path: Path,
        output_dir: Path,
        preset: MarketplacePreset,
        preprocess_config: PreprocessConfig | None = None,
        trace_params: TraceParams | None = None,
    ) -> None:
        """Initialize the TraceWorker.

        Parameters
        ----------
        pipeline:
            The core Pipeline instance.
        input_path:
            The input image path.
        output_dir:
            The output SVG target directory.
        preset:
            The marketplace validation preset.
        preprocess_config:
            Custom preprocessor settings.
        trace_params:
            Custom trace engine settings.
        """
        super().__init__()
        self.pipeline = pipeline
        self.input_path = input_path
        self.output_dir = output_dir
        self.preset = preset
        self.preprocess_config = preprocess_config
        self.trace_params = trace_params
        self.signals = TraceWorkerSignals()

    @Slot()
    def run(self) -> None:
        """Execute the pipeline run step."""
        logger.debug("Starting trace worker for: %s", self.input_path)
        try:
            # Run the core pipeline with progress callback forwarding to Qt signals
            result = self.pipeline.run(
                input_path=self.input_path,
                output_dir=self.output_dir,
                preset=self.preset,
                preprocess_config=self.preprocess_config,
                trace_params=self.trace_params,
                on_progress=self._forward_progress,
            )
            logger.debug("Trace worker finished successfully for: %s", self.input_path)
            self.signals.finished.emit(result)
        except Exception as e:
            logger.exception("Error executing tracing in thread")
            self.signals.error.emit(str(e))

    def _forward_progress(self, step: str, percent: int) -> None:
        """Forward pipeline callbacks into the Qt main event loop."""
        self.signals.progress.emit(step, percent)
