"""
tests.unit.ui.test_batch_queue_table
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Unit tests for BatchQueueTable.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QProgressBar, QPushButton

from vector_tracer_pro.services.batch_runner import BatchJob, BatchProgress
from vector_tracer_pro.services.preset_manager import TracingPreset
from vector_tracer_pro.ui.widgets.batch_queue_table import BatchQueueTable


@pytest.mark.gui
class TestBatchQueueTable:
    """Verifies table row insertions, status color mappings, and inline widgets."""

    def test_initial_state(self, qtbot) -> None:
        table = BatchQueueTable()
        qtbot.addWidget(table)

        assert table.table.columnCount() == 6
        assert table.table.rowCount() == 0

    def test_add_job(self, qtbot) -> None:
        table = BatchQueueTable()
        qtbot.addWidget(table)

        preset = TracingPreset("test_preset", "adobe_stock", ["potrace"], {}, {})
        job = BatchJob("job_abc", Path("img.png"), Path("out/"), preset, "pending")

        table.add_job(job)

        assert table.table.rowCount() == 1
        assert table.table.item(0, 1).text() == "img.png"
        assert table.table.item(0, 2).text() == "PENDING"
        assert table.table.item(0, 3).text() == "potrace"

        # Verify inline progress bar
        pbar = table.table.cellWidget(0, 4)
        assert isinstance(pbar, QProgressBar)
        assert pbar.value() == 0

        # Verify inline cancel button
        cancel_btn = table.table.cellWidget(0, 5)
        assert isinstance(cancel_btn, QPushButton)
        assert cancel_btn.text() == "Cancel"
        assert cancel_btn.isEnabled() is True

    def test_click_cancel_emits_signal(self, qtbot) -> None:
        table = BatchQueueTable()
        qtbot.addWidget(table)

        preset = TracingPreset("test_preset", "adobe_stock", ["potrace"], {}, {})
        job = BatchJob("job_abc", Path("img.png"), Path("out/"), preset, "pending")
        table.add_job(job)

        cancel_btn = table.table.cellWidget(0, 5)

        with qtbot.waitSignal(table.cancel_job_requested) as blocker:
            qtbot.mouseClick(cancel_btn, Qt.MouseButton.LeftButton)

        assert blocker.args[0] == "job_abc"

    def test_update_job_progress(self, qtbot) -> None:
        table = BatchQueueTable()
        qtbot.addWidget(table)

        preset = TracingPreset("test_preset", "adobe_stock", ["potrace"], {}, {})
        job = BatchJob("job_abc", Path("img.png"), Path("out/"), preset, "pending")
        table.add_job(job)

        progress = BatchProgress("job_abc", "preprocessing", 45)
        table.update_job_progress(progress)

        pbar = table.table.cellWidget(0, 4)
        assert pbar.value() == 45
        assert table.table.item(0, 2).text() == "PREPROCESSING"

    def test_update_job_status_done_disables_cancel(self, qtbot) -> None:
        table = BatchQueueTable()
        qtbot.addWidget(table)

        preset = TracingPreset("test_preset", "adobe_stock", ["potrace"], {}, {})
        job = BatchJob("job_abc", Path("img.png"), Path("out/"), preset, "pending")
        table.add_job(job)

        # Done
        job.status = "done"
        table.update_job_status(job)

        assert table.table.item(0, 2).text() == "DONE"
        cancel_btn = table.table.cellWidget(0, 5)
        assert cancel_btn.isEnabled() is False
        pbar = table.table.cellWidget(0, 4)
        assert pbar.value() == 100
