"""
vector_tracer_pro.ui.main_window
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Main window container and layout skeleton for Vector Tracer Pro.
"""

from __future__ import annotations

import logging

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QLabel,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from vector_tracer_pro.ui.widgets import (
    BatchQueueTable,
    ControlPanel,
    DropZoneWidget,
    PreviewPanel,
)

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    """Main window class defining layout, splitter sections, menu, and status bars."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Vector Tracer Pro")
        self.resize(1100, 750)

        # Central Widget & Vertical main layout
        self.central_widget = QWidget(self)
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)
        self.main_layout.setContentsMargins(12, 12, 12, 12)
        self.main_layout.setSpacing(10)

        # -------------------------------------------------------------
        # Horizontal Splitter (Left Panel & Right Panel)
        # -------------------------------------------------------------
        self.horizontal_splitter = QSplitter(Qt.Orientation.Horizontal, self)

        # Left Panel Container Widget
        self.left_panel = QWidget(self)
        self.left_layout = QVBoxLayout(self.left_panel)
        self.left_layout.setContentsMargins(0, 0, 0, 0)
        self.left_layout.setSpacing(10)

        self.left_title = QLabel("Source Images", self.left_panel)
        self.left_title.setObjectName("PanelTitle")
        self.left_layout.addWidget(self.left_title)

        # Drop Zone Widget
        self.drop_zone = DropZoneWidget(self.left_panel)
        self.drop_zone.setFixedHeight(120)
        self.left_layout.addWidget(self.drop_zone)

        # File list QListWidget
        self.file_list = QListWidget(self.left_panel)
        self.left_layout.addWidget(self.file_list, 1)

        # Right Panel Container Widget
        self.right_panel = QWidget(self)
        self.right_layout = QVBoxLayout(self.right_panel)
        self.right_layout.setContentsMargins(0, 0, 0, 0)
        self.right_layout.setSpacing(10)

        # Preview Panel Widget
        self.preview_panel = PreviewPanel(self.right_panel)
        self.right_layout.addWidget(self.preview_panel, 3)

        # Control Panel Widget
        self.control_panel = ControlPanel(self.right_panel)
        self.right_layout.addWidget(self.control_panel, 1)

        # Add to splitter
        self.horizontal_splitter.addWidget(self.left_panel)
        self.horizontal_splitter.addWidget(self.right_panel)
        # Give right panel more stretch factor
        self.horizontal_splitter.setStretchFactor(0, 1)
        self.horizontal_splitter.setStretchFactor(1, 3)

        # Add splitter to main vertical layout
        self.main_layout.addWidget(self.horizontal_splitter, 1)

        # -------------------------------------------------------------
        # Bottom Panel (Batch Queue Table)
        # -------------------------------------------------------------
        self.bottom_panel = QWidget(self)
        self.bottom_layout = QVBoxLayout(self.bottom_panel)
        self.bottom_layout.setContentsMargins(0, 0, 0, 0)
        self.bottom_layout.setSpacing(6)

        self.bottom_title = QLabel("Batch Queue Processing", self.bottom_panel)
        self.bottom_title.setObjectName("PanelTitle")
        self.bottom_layout.addWidget(self.bottom_title)

        # Batch Queue Table
        self.batch_table = BatchQueueTable(self.bottom_panel)
        self.batch_table.setFixedHeight(200)
        self.bottom_layout.addWidget(self.batch_table)

        self.main_layout.addWidget(self.bottom_panel)

        # Setup Menus and Status bars
        self._setup_menu_bar()
        self._setup_status_bar()

    def set_status(self, message: str) -> None:
        """Update the status bar text message."""
        self.statusBar().showMessage(message)

    def _setup_menu_bar(self) -> None:
        """Create menu options and binds them to stub placeholders."""
        menu_bar = self.menuBar()

        # File Menu
        file_menu = menu_bar.addMenu("File")

        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # Preset Menu
        preset_menu = menu_bar.addMenu("Preset")

        load_action = QAction("Load Preset...", self)
        load_action.triggered.connect(self._stub_load_preset)
        preset_menu.addAction(load_action)

        save_action = QAction("Save Current Preset...", self)
        save_action.triggered.connect(self._stub_save_preset)
        preset_menu.addAction(save_action)

        # Help Menu
        help_menu = menu_bar.addMenu("Help")

        about_action = QAction("About", self)
        about_action.triggered.connect(self._on_about)
        help_menu.addAction(about_action)

    def _setup_status_bar(self) -> None:
        """Initialize and configure the window status bar."""
        status_bar = self.statusBar()
        status_bar.showMessage("Ready")

    # Menu Action Stubs
    def _stub_load_preset(self) -> None:
        logger.debug("Load preset clicked (stub)")
        self.set_status("Load Preset clicked (feature stub)")

    def _stub_save_preset(self) -> None:
        logger.debug("Save preset clicked (stub)")
        self.set_status("Save Preset clicked (feature stub)")

    def _on_about(self) -> None:
        """Show information popup about Vector Tracer Pro."""
        QMessageBox.about(
            self,
            "About Vector Tracer Pro",
            "<h3>Vector Tracer Pro v0.1.0-alpha.1</h3>"
            "<p>A professional desktop application for converting raster images "
            "into stock-ready vector graphics.</p>"
            "<p>© 2026 Vector Tracer Pro Team</p>",
        )
