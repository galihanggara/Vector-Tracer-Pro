"""
tests.unit.ui.test_main_controller
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Unit tests for MainController.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest
from PySide6.QtCore import QThreadPool

from vector_tracer_pro.core.pipeline import Pipeline
from vector_tracer_pro.services.batch_runner import BatchJob, BatchProgress, BatchRunner
from vector_tracer_pro.services.preset_manager import PresetManager, TracingPreset
from vector_tracer_pro.ui.controllers.main_controller import MainController
from vector_tracer_pro.ui.main_window import MainWindow
from vector_tracer_pro.ui.widgets import TraceRequest


@pytest.mark.gui
class TestMainController:
    """Verifies event routing between GUI widgets and core/services modules."""

    @pytest.fixture
    def setup_controller(self, qtbot):
        window = MainWindow()
        qtbot.addWidget(window)

        pipeline = MagicMock(spec=Pipeline)
        batch_runner = MagicMock(spec=BatchRunner)
        preset_manager = MagicMock(spec=PresetManager)

        # Mock presets
        preset_manager.list_presets.return_value = ["test_preset"]
        preset_manager.load.return_value = TracingPreset(
            name="test_preset",
            marketplace="adobe_stock",
            engine_order=["potrace"],
            preprocess_config={},
            trace_params={},
        )

        controller = MainController(window, pipeline, batch_runner, preset_manager)
        return controller, window, pipeline, batch_runner, preset_manager

    def test_file_drop_adds_to_list(self, setup_controller) -> None:
        controller, window, _, _, _ = setup_controller

        # Simulate dropping files
        paths = [Path("image1.png"), Path("image2.jpg")]
        window.drop_zone.files_dropped.emit(paths)

        assert window.file_list.count() == 2
        assert window.file_list.item(0).text() == "image1.png"
        assert window.file_list.item(1).text() == "image2.jpg"
        
        # Verify first item got auto-selected
        assert window.file_list.currentRow() == 0

    def test_file_selection_updates_preview(self, setup_controller) -> None:
        controller, window, _, _, _ = setup_controller

        # Add files first
        window.drop_zone.files_dropped.emit([Path("image1.png")])
        window.file_list.setCurrentRow(-1)  # Clear selection

        with patch.object(window.preview_panel, "show_original") as mock_show:
            # Change selection
            window.file_list.setCurrentRow(0)
            mock_show.assert_called_once_with(Path("image1.png"))

    @patch("PySide6.QtCore.QThreadPool.start")
    def test_trace_requested_starts_thread_worker(self, mock_thread_start, setup_controller) -> None:
        controller, window, pipeline, _, _ = setup_controller

        # Request trace
        req = TraceRequest(
            input_path=Path("in.png"),
            preset_name="test_preset",
            output_dir=Path("out/"),
        )
        window.control_panel.trace_requested.emit(req)

        # Threadpool should start the TraceWorker runnable
        mock_thread_start.assert_called_once()

    def test_add_to_batch_adds_to_table_and_submits(self, setup_controller) -> None:
        controller, window, _, batch_runner, _ = setup_controller

        # Request add to batch
        req = TraceRequest(
            input_path=Path("in.png"),
            preset_name="test_preset",
            output_dir=Path("out/"),
        )
        window.control_panel.add_to_batch_requested.emit(req)

        # Verify job is in table
        assert window.batch_table.table.rowCount() == 1
        assert window.batch_table.table.item(0, 1).text() == "in.png"

        # Verify submit called on batch runner
        batch_runner.submit.assert_called_once()
        jobs_submitted = batch_runner.submit.call_args[0][0]
        assert len(jobs_submitted) == 1
        assert jobs_submitted[0].input_path == Path("in.png")

    def test_cancel_all_jobs(self, setup_controller) -> None:
        controller, window, _, batch_runner, _ = setup_controller

        # Queue a job
        req = TraceRequest(
            input_path=Path("in.png"),
            preset_name="test_preset",
            output_dir=Path("out/"),
        )
        window.control_panel.add_to_batch_requested.emit(req)

        # Trigger cancel
        window.batch_table.cancel_job_requested.emit("dummy_job_id")

        # Verify cancel called on batch runner
        batch_runner.cancel_all.assert_called_once()
