"""
vector_tracer_pro.ui.controllers.main_controller
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Main controller bridging the UI elements with background services and core pipeline.
"""

from __future__ import annotations

import logging
import uuid
from pathlib import Path
from PySide6.QtCore import QObject, QThreadPool, Signal, Slot
from PySide6.QtWidgets import QMessageBox

from vector_tracer_pro.core.image.preprocessor import PreprocessConfig
from vector_tracer_pro.core.marketplace_validator import MarketplacePreset
from vector_tracer_pro.core.pipeline import Pipeline, PipelineResult
from vector_tracer_pro.core.trace_strategy import TraceParams
from vector_tracer_pro.services.batch_runner import BatchJob, BatchProgress, BatchRunner
from vector_tracer_pro.services.preset_manager import PresetManager, TracingPreset
from vector_tracer_pro.ui.main_window import MainWindow
from vector_tracer_pro.ui.widgets import TraceRequest
from vector_tracer_pro.workers import TraceWorker

logger = logging.getLogger(__name__)


class MainController(QObject):
    """Bridge controller between MainWindow GUI and Vector Tracer Pro services."""

    # Thread-safe signals to marshal batch updates from background threads to main GUI thread
    job_progress_received = Signal(BatchProgress)
    job_done_received = Signal(BatchJob)

    def __init__(
        self,
        window: MainWindow,
        pipeline: Pipeline,
        batch_runner: BatchRunner,
        preset_manager: PresetManager,
    ) -> None:
        """Initialize the MainController.

        Parameters
        ----------
        window:
            The MainWindow instance.
        pipeline:
            The core Pipeline processor.
        batch_runner:
            The background batch execution runner.
        preset_manager:
            The preset configuration manager.
        """
        super().__init__()
        self.window = window
        self.pipeline = pipeline
        self.batch_runner = batch_runner
        self.preset_manager = preset_manager

        # Internal queue tracking
        self._batch_jobs: list[BatchJob] = []

        # Wire Up UI signals
        self._connect_signals()

        # Initialize Default State
        self._init_default_state()

    def _connect_signals(self) -> None:
        # File/Drop zone signals
        self.window.drop_zone.files_dropped.connect(self._on_files_dropped)
        self.window.drop_zone.files_selected.connect(self._on_files_dropped)
        
        # File list selection changed
        self.window.file_list.currentItemChanged.connect(self._on_file_list_selection_changed)

        # Control Panel buttons
        self.window.control_panel.trace_requested.connect(self._on_trace_requested)
        self.window.control_panel.add_to_batch_requested.connect(self._on_add_to_batch)

        # Batch Table actions
        self.window.batch_table.cancel_job_requested.connect(self._on_cancel_job)

        # Connect thread marshalling signals
        self.job_progress_received.connect(self._on_batch_progress)
        self.job_done_received.connect(self._on_batch_done)

    def _init_default_state(self) -> None:
        """Fetch presets and configure default output directory."""
        # Load available presets or create a default one
        presets = self.preset_manager.list_presets()
        if not presets:
            default_preset = TracingPreset(
                name="default",
                marketplace="adobe_stock",
                engine_order=["potrace", "vtracer"],
                preprocess_config={"quantize_k": 8},
                trace_params={"turdsize": 10},
            )
            try:
                self.preset_manager.save(default_preset)
                presets = [default_preset.name]
            except Exception as e:
                logger.error("Failed to save default preset: %s", e)

        self.window.control_panel.set_presets(presets)

        # Resolve and set default output path
        from vector_tracer_pro.core.path_manager import PathManager
        try:
            pm = PathManager()
            self.window.control_panel.set_output_dir(pm.get_output_svg_dir())
        except Exception as e:
            logger.error("Failed to resolve default output directory: %s", e)

    # ------------------------------------------------------------------
    # Drag & Drop / File list slots
    # ------------------------------------------------------------------
    @Slot(list)
    def _on_files_dropped(self, paths: list[Path]) -> None:
        """Add newly dragged or selected file paths to the sidebar list."""
        for path in paths:
            # Check for duplicates
            from PySide6.QtCore import Qt
            items = self.window.file_list.findItems(str(path), Qt.MatchFlag.MatchExactly)
            if not items:
                self.window.file_list.addItem(str(path))

        # Auto select the first item if nothing is currently selected
        if not self.window.file_list.currentItem() and self.window.file_list.count() > 0:
            self.window.file_list.setCurrentRow(0)

    @Slot(object, object)
    def _on_file_list_selection_changed(self, current, previous) -> None:
        """Update preview panel and controls when another image is selected."""
        if current is None:
            self.window.preview_panel.clear()
            self.window.control_panel.set_current_input_path(None)
            self.window.set_status("No file selected")
        else:
            path = Path(current.text())
            self.window.preview_panel.show_original(path)
            self.window.control_panel.set_current_input_path(path)
            self.window.set_status(f"Selected: {path.name}")

    # ------------------------------------------------------------------
    # Single Tracing Slots
    # ------------------------------------------------------------------
    @Slot(object)
    def _on_trace_requested(self, request: TraceRequest) -> None:
        """Spawn background TraceWorker for a single file tracing task."""
        # Disable trigger buttons during active trace
        self.window.control_panel.trace_btn.setEnabled(False)
        self.window.control_panel.add_batch_btn.setEnabled(False)

        try:
            preset = self.preset_manager.load(request.preset_name)
        except Exception as e:
            self._on_trace_error(f"Failed to load preset '{request.preset_name}': {e}")
            return

        # Prepare configs
        p_cfg = PreprocessConfig(**preset.preprocess_config) if preset.preprocess_config else None
        t_params = TraceParams(**preset.trace_params) if preset.trace_params else None

        # Build worker
        worker = TraceWorker(
            pipeline=self.pipeline,
            input_path=request.input_path,
            output_dir=request.output_dir,
            preset=MarketplacePreset(preset.marketplace),
            preprocess_config=p_cfg,
            trace_params=t_params,
        )

        # Wire up worker callbacks
        worker.signals.progress.connect(self.window.control_panel.show_progress)
        worker.signals.finished.connect(self._on_trace_finished)
        worker.signals.error.connect(self._on_trace_error)

        # Start execution in global thread pool
        self.window.set_status("Tracing started...")
        QThreadPool.globalInstance().start(worker)

    @Slot(object)
    def _on_trace_finished(self, result: PipelineResult) -> None:
        """Handle successful trace completion."""
        # Re-enable inputs
        self.window.control_panel.set_current_input_path(result.svg_path) # dummy update to trigger enabled states
        self.window.control_panel.set_current_input_path(self._get_selected_path())
        self.window.control_panel.hide_progress()

        # Display result SVG
        self.window.preview_panel.show_result(result.svg_path)
        self.window.set_status(f"Trace completed successfully using {result.engine_used}!")

    @Slot(str)
    def _on_trace_error(self, error_msg: str) -> None:
        """Handle single tracing failures."""
        self.window.control_panel.set_current_input_path(self._get_selected_path())
        self.window.control_panel.hide_progress()
        self.window.set_status("Trace failed")

        QMessageBox.critical(
            self.window,
            "Tracing Error",
            f"An error occurred during tracing:\n{error_msg}",
        )

    # ------------------------------------------------------------------
    # Batch Processing Slots
    # ------------------------------------------------------------------
    @Slot(object)
    def _on_add_to_batch(self, request: TraceRequest) -> None:
        """Queue a file configuration into the batch runner."""
        try:
            preset = self.preset_manager.load(request.preset_name)
        except Exception as e:
            QMessageBox.critical(self.window, "Error", f"Failed to load preset: {e}")
            return

        # Instantiate BatchJob
        job_id = f"job_{uuid.uuid4().hex[:8]}"
        job = BatchJob(
            job_id=job_id,
            input_path=request.input_path,
            output_dir=request.output_dir,
            preset=preset,
            status="pending",
        )

        # Add to local tracker and UI table
        self._batch_jobs.append(job)
        self.window.batch_table.add_job(job)
        self.window.set_status(f"Added job for {request.input_path.name} to batch queue.")

        # Trigger batch execution if no other job is currently active
        self._trigger_next_batch_runs()

    @Slot(object)
    def _on_batch_progress(self, progress: BatchProgress) -> None:
        """Forward batch progress updates to the table widget safely."""
        self.window.batch_table.update_job_progress(progress)
        self.window.set_status(f"Batch progress: {progress.job_id} at {progress.percent}%")

    @Slot(object)
    def _on_batch_done(self, job: BatchJob) -> None:
        """Update job statuses and triggers the next queue execution when done."""
        # Update local job status
        for local_job in self._batch_jobs:
            if local_job.job_id == job.job_id:
                local_job.status = job.status
                local_job.error = job.error
                break

        self.window.batch_table.update_job_status(job)
        
        if job.status == "done":
            logger.info("Batch job %s completed successfully", job.job_id)
        else:
            logger.warning("Batch job %s failed: %s", job.job_id, job.error)

        # Submit next pending jobs
        self._trigger_next_batch_runs()

    @Slot(str)
    def _on_cancel_job(self, job_id: str) -> None:
        """Cancel all running and pending batch jobs (cancellation scope)."""
        logger.info("Cancellation requested for job: %s. Cancelling all.", job_id)
        self.batch_runner.cancel_all()
        
        # Immediately set status and update UI to avoid lag feedback
        for job in self._batch_jobs:
            if job.status in ("pending", "running"):
                job.status = "failed"
                job.error = "Cancelled"
                self.window.batch_table.update_job_status(job)

        self.window.set_status("Batch processing cancelled by user.")

    # ------------------------------------------------------------------
    # Helper Methods
    # ------------------------------------------------------------------
    def _get_selected_path(self) -> Path | None:
        current_item = self.window.file_list.currentItem()
        return Path(current_item.text()) if current_item else None

    def _trigger_next_batch_runs(self) -> None:
        """Check for pending jobs and submit them if the runner is idle."""
        # Find if there are any jobs currently running
        is_running = any(j.status == "running" for j in self._batch_jobs)
        if is_running:
            return  # Let current execution threads finish

        # Collect all pending jobs
        pending_jobs = [j for j in self._batch_jobs if j.status == "pending"]
        if not pending_jobs:
            self.window.set_status("All queued batch jobs finished.")
            return

        # Submit pending batch jobs to runner (runner runs them concurrently up to limit)
        self.window.set_status(f"Starting execution of {len(pending_jobs)} pending jobs...")
        self.batch_runner.submit(
            pending_jobs,
            on_job_progress=self._on_batch_progress_callback,
            on_job_done=self._on_batch_done_callback,
        )

    # Thread-safe callbacks forwarded from the BatchRunner threads
    def _on_batch_progress_callback(self, progress: BatchProgress) -> None:
        self.job_progress_received.emit(progress)

    def _on_batch_done_callback(self, job: BatchJob) -> None:
        self.job_done_received.emit(job)
