"""
vector_tracer_pro.ui.widgets.batch_queue_table
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

A widget displaying a table queue of active and completed vectorisation jobs.
"""

from __future__ import annotations

import logging

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QHeaderView,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from vector_tracer_pro.services.batch_runner import BatchJob, BatchProgress

logger = logging.getLogger(__name__)


class BatchQueueTable(QWidget):
    """Table showing progress and statuses of Batch Jobs."""

    cancel_job_requested = Signal(str)  # Emits job_id

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        # Main Layout
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)

        # Table Widget
        self.table = QTableWidget(self)
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(
            [
                "#",
                "Filename",
                "Status",
                "Engine",
                "Progress",
                "Action",
            ]
        )

        # Configure Header sizing
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)

        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)

        self.layout.addWidget(self.table)

        # Map to find row index of job_id quickly
        self._job_rows: dict[str, int] = {}

    def add_job(self, job: BatchJob) -> None:
        """Add a new job entry to the queue table."""
        row = self.table.rowCount()
        self.table.insertRow(row)
        self._job_rows[job.job_id] = row

        # Row Index Label
        item_idx = QTableWidgetItem(str(row + 1))
        item_idx.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.table.setItem(row, 0, item_idx)

        # Filename
        item_name = QTableWidgetItem(job.input_path.name)
        self.table.setItem(row, 1, item_name)

        # Status
        item_status = QTableWidgetItem(job.status.upper())
        item_status.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self._style_status_item(item_status, job.status)
        self.table.setItem(row, 2, item_status)

        # Engine (from engine_order of preset, default to fallback/custom)
        engine_str = ", ".join(job.preset.engine_order) if job.preset.engine_order else "auto"
        item_engine = QTableWidgetItem(engine_str)
        self.table.setItem(row, 3, item_engine)

        # Progress bar
        pbar = QProgressBar(self)
        pbar.setRange(0, 100)
        pbar.setValue(0)
        # Style embedded progress bar specifically
        pbar.setStyleSheet("""
            QProgressBar {
                background-color: #1a1a1e;
                border: 1px solid #2f2f36;
                border-radius: 4px;
                text-align: center;
                height: 16px;
                font-size: 10px;
            }
            QProgressBar::chunk {
                background-color: #6366f1;
            }
        """)
        self.table.setCellWidget(row, 4, pbar)

        # Cancel button
        cancel_btn = QPushButton("Cancel", self)
        cancel_btn.setObjectName("DangerButton")
        # Ensure red danger styling
        cancel_btn.setStyleSheet("""
            QPushButton#DangerButton {
                background-color: #ef4444;
                border: none;
                color: white;
                padding: 4px 8px;
                border-radius: 4px;
                font-size: 11px;
            }
            QPushButton#DangerButton:hover {
                background-color: #dc2626;
            }
            QPushButton#DangerButton:disabled {
                background-color: #27272a;
                color: #52525b;
            }
        """)
        cancel_btn.clicked.connect(
            lambda checked=False, j_id=job.job_id: self.cancel_job_requested.emit(j_id)
        )
        self.table.setCellWidget(row, 5, cancel_btn)

    def update_job_progress(self, progress: BatchProgress) -> None:
        """Update progress value of a specific active job."""
        if progress.job_id not in self._job_rows:
            return
        row = self._job_rows[progress.job_id]

        # Update progress bar
        pbar = self.table.cellWidget(row, 4)
        if isinstance(pbar, QProgressBar):
            pbar.setValue(progress.percent)

        # Also update status text/step
        item_status = self.table.item(row, 2)
        if item_status:
            step_clean = progress.step.replace("_", " ").upper()
            item_status.setText(step_clean)

    def update_job_status(self, job: BatchJob) -> None:
        """Update final status and UI elements for a completed or failed job."""
        if job.job_id not in self._job_rows:
            return
        row = self._job_rows[job.job_id]

        # Update Status Text & Styling
        item_status = self.table.item(row, 2)
        if item_status:
            item_status.setText(job.status.upper())
            self._style_status_item(item_status, job.status)

        # If completed/failed/cancelled, disable cancel button and finish progress bar
        if job.status in ("done", "failed"):
            cancel_btn = self.table.cellWidget(row, 5)
            if isinstance(cancel_btn, QPushButton):
                cancel_btn.setEnabled(False)

            pbar = self.table.cellWidget(row, 4)
            if isinstance(pbar, QProgressBar):
                if job.status == "done":
                    pbar.setValue(100)
                    pbar.setStyleSheet("""
                        QProgressBar::chunk { background-color: #22c55e; }
                    """)
                else:
                    # failed status
                    pbar.setStyleSheet("""
                        QProgressBar::chunk { background-color: #ef4444; }
                    """)

    def _style_status_item(self, item: QTableWidgetItem, status: str) -> None:
        """Apply color highlighting to status text cell."""
        font = item.font()
        font.setBold(True)
        item.setFont(font)

        if status == "pending":
            item.setForeground(QColor("#a1a1aa"))  # Grey
        elif status == "running":
            item.setForeground(QColor("#60a5fa"))  # Blue
        elif status == "done":
            item.setForeground(QColor("#4ade80"))  # Green
        elif status == "failed":
            item.setForeground(QColor("#f87171"))  # Red
