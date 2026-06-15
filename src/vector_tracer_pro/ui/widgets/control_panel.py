"""
vector_tracer_pro.ui.widgets.control_panel
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

A panel containing presets, marketplace options, output folder selection, and execution buttons.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

logger = logging.getLogger(__name__)


@dataclass
class TraceRequest:
    """Represents a request to run a single tracing operation."""

    input_path: Path
    preset_name: str
    output_dir: Path


class ControlPanel(QWidget):
    """Contains controls for vectorisation parameters and triggering actions."""

    trace_requested = Signal(TraceRequest)
    add_to_batch_requested = Signal(TraceRequest)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._input_path: Path | None = None
        self._output_dir: Path | None = None

        # Main vertical layout
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(12)

        # Container Frame
        self.container = QFrame(self)
        self.container.setObjectName("ContainerFrame")
        self.container_layout = QVBoxLayout(self.container)
        self.container_layout.setContentsMargins(16, 16, 16, 16)
        self.container_layout.setSpacing(12)

        # Title
        self.title_label = QLabel("Vectorisation Controls", self.container)
        self.title_label.setObjectName("PanelTitle")
        self.container_layout.addWidget(self.title_label)

        # Form Layout for Inputs
        self.form_layout = QFormLayout()
        self.form_layout.setSpacing(10)
        self.form_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        # Preset selection
        self.preset_combo = QComboBox(self.container)
        self.form_layout.addRow("Preset:", self.preset_combo)

        # Marketplace selection
        self.marketplace_combo = QComboBox(self.container)
        self.marketplace_combo.addItems(["adobe_stock", "shutterstock", "freepik"])
        self.form_layout.addRow("Marketplace:", self.marketplace_combo)

        # Output Dir select row
        self.output_layout = QHBoxLayout()
        self.output_label = QLabel("Not selected", self.container)
        self.output_label.setStyleSheet("color: #a1a1aa;")
        self.output_label.setWordWrap(True)
        self.output_browse_btn = QPushButton("Browse...", self.container)
        self.output_browse_btn.clicked.connect(self._on_browse_output)
        self.output_layout.addWidget(self.output_label, 1)
        self.output_layout.addWidget(self.output_browse_btn)
        self.form_layout.addRow("Output Folder:", self.output_layout)

        self.container_layout.addLayout(self.form_layout)

        # Action Buttons Layout
        self.button_layout = QHBoxLayout()
        self.button_layout.setSpacing(8)

        self.trace_btn = QPushButton("Trace Now", self.container)
        self.trace_btn.setObjectName("PrimaryButton")
        self.trace_btn.clicked.connect(self._on_trace_now)
        self.trace_btn.setEnabled(False)

        self.add_batch_btn = QPushButton("Add to Batch", self.container)
        self.add_batch_btn.clicked.connect(self._on_add_to_batch)
        self.add_batch_btn.setEnabled(False)

        self.button_layout.addWidget(self.trace_btn, 1)
        self.button_layout.addWidget(self.add_batch_btn, 1)
        self.container_layout.addLayout(self.button_layout)

        # Progress Section
        self.progress_layout = QVBoxLayout()
        self.progress_label = QLabel("Idle", self.container)
        self.progress_label.setStyleSheet("font-size: 11px; color: #a1a1aa;")
        self.progress_bar = QProgressBar(self.container)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_layout.addWidget(self.progress_label)
        self.progress_layout.addWidget(self.progress_bar)

        # Hide progress elements by default
        self.progress_label.setVisible(False)
        self.progress_bar.setVisible(False)

        self.container_layout.addLayout(self.progress_layout)
        self.main_layout.addWidget(self.container)

    def set_presets(self, presets: list[str]) -> None:
        """Populate preset selection dropdown."""
        self.preset_combo.clear()
        self.preset_combo.addItems(presets)

    def set_current_input_path(self, path: Path | None) -> None:
        """Set the active raster file to vectorize."""
        self._input_path = path
        self._update_buttons_enabled()

    def set_output_dir(self, path: Path) -> None:
        """Set target output directory and display it."""
        self._output_dir = path
        self.output_label.setText(str(path))
        self._update_buttons_enabled()

    def get_output_dir(self) -> Path | None:
        """Get currently configured output directory."""
        return self._output_dir

    def show_progress(self, step: str, percent: int) -> None:
        """Show and update progress bar and label status."""
        self.progress_label.setVisible(True)
        self.progress_bar.setVisible(True)
        self.progress_label.setText(f"Status: {step}...")
        self.progress_bar.setValue(percent)

    def hide_progress(self) -> None:
        """Hide progress components when tracing is idle."""
        self.progress_label.setVisible(False)
        self.progress_bar.setVisible(False)

    def _update_buttons_enabled(self) -> None:
        has_input = self._input_path is not None
        has_output = self._output_dir is not None
        self.trace_btn.setEnabled(has_input and has_output)
        self.add_batch_btn.setEnabled(has_input and has_output)

    def _on_browse_output(self) -> None:
        """Trigger directory chooser dialog for output path."""
        default_dir = str(self._output_dir) if self._output_dir else ""
        directory = QFileDialog.getExistingDirectory(
            self,
            "Select Output Directory",
            default_dir,
        )
        if directory:
            self.set_output_dir(Path(directory))

    def _on_trace_now(self) -> None:
        """Collect configuration and emit tracing signal."""
        if self._input_path and self._output_dir:
            req = TraceRequest(
                input_path=self._input_path,
                preset_name=self.preset_combo.currentText(),
                output_dir=self._output_dir,
            )
            self.trace_requested.emit(req)

    def _on_add_to_batch(self) -> None:
        """Collect configuration and emit add to batch signal."""
        if self._input_path and self._output_dir:
            req = TraceRequest(
                input_path=self._input_path,
                preset_name=self.preset_combo.currentText(),
                output_dir=self._output_dir,
            )
            self.add_to_batch_requested.emit(req)
