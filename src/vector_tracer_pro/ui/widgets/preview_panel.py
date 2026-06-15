"""
vector_tracer_pro.ui.widgets.preview_panel
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

A side-by-side comparison panel displaying the original raster image
and the vectorized SVG output.
"""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtSvgWidgets import QSvgWidget
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

logger = logging.getLogger(__name__)


class PreviewPanel(QWidget):
    """Renders the original raster and vectorized SVG outputs side-by-side."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        # Horizontal main layout
        self.main_layout = QHBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(12)

        # Left Panel (Original)
        self.left_frame = QFrame(self)
        self.left_frame.setObjectName("PanelFrame")
        self.left_layout = QVBoxLayout(self.left_frame)
        self.left_layout.setContentsMargins(12, 12, 12, 12)

        self.left_title = QLabel("Original Image", self.left_frame)
        self.left_title.setObjectName("PanelTitle")
        self.left_layout.addWidget(self.left_title)

        self.original_label = QLabel(self.left_frame)
        self.original_label.setScaledContents(True)
        self.original_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.original_label.setMinimumSize(200, 200)
        self.original_label.setStyleSheet("background-color: #111115; border-radius: 4px;")
        self.left_layout.addWidget(self.original_label, 1)

        self.left_info = QLabel("No image selected", self.left_frame)
        self.left_info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.left_info.setStyleSheet("color: #a1a1aa; font-size: 11px;")
        self.left_layout.addWidget(self.left_info)

        # Right Panel (SVG Result)
        self.right_frame = QFrame(self)
        self.right_frame.setObjectName("PanelFrame")
        self.right_layout = QVBoxLayout(self.right_frame)
        self.right_layout.setContentsMargins(12, 12, 12, 12)

        self.right_title = QLabel("Vectorized SVG", self.right_frame)
        self.right_title.setObjectName("PanelTitle")
        self.right_layout.addWidget(self.right_title)

        # SVG container to hold QSvgWidget dynamically
        self.svg_container = QWidget(self.right_frame)
        self.svg_container_layout = QHBoxLayout(self.svg_container)
        self.svg_container_layout.setContentsMargins(0, 0, 0, 0)
        self.svg_container.setMinimumSize(200, 200)
        self.svg_container.setStyleSheet("background-color: #111115; border-radius: 4px;")

        self.placeholder_svg_label = QLabel("Waiting for tracing...", self.svg_container)
        self.placeholder_svg_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.placeholder_svg_label.setStyleSheet("color: #52525b;")
        self.svg_container_layout.addWidget(self.placeholder_svg_label)
        self.right_layout.addWidget(self.svg_container, 1)

        self.right_info = QLabel("No output SVG", self.right_frame)
        self.right_info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.right_info.setStyleSheet("color: #a1a1aa; font-size: 11px;")
        self.right_layout.addWidget(self.right_info)

        # Add left and right frames to layout
        self.main_layout.addWidget(self.left_frame, 1)
        self.main_layout.addWidget(self.right_frame, 1)

        # Active svg widget
        self.svg_widget: QSvgWidget | None = None

    def show_original(self, image_path: Path) -> None:
        """Load and display the original image."""
        pixmap = QPixmap(str(image_path))
        if pixmap.isNull():
            self.original_label.setText("Failed to load image")
            self.left_info.setText(image_path.name)
            return

        self.original_label.setPixmap(pixmap)
        self.left_info.setText(f"{image_path.name} ({pixmap.width()}x{pixmap.height()})")

    def show_result(self, svg_path: Path) -> None:
        """Load and render the SVG file using QSvgWidget."""
        # Clean up existing placeholder or old SVG widget
        self.clear_svg_container()

        try:
            self.svg_widget = QSvgWidget(self.svg_container)
            self.svg_widget.load(str(svg_path))
            self.svg_container_layout.addWidget(self.svg_widget)

            # Simple SVG path check size or read XML for dimensions
            size = svg_path.stat().st_size
            size_kb = size / 1024.0
            self.right_info.setText(f"{svg_path.name} ({size_kb:.1f} KB)")
        except Exception as e:
            logger.error("Error loading SVG widget: %s", e)
            self.placeholder_svg_label = QLabel("Error rendering SVG", self.svg_container)
            self.placeholder_svg_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.placeholder_svg_label.setStyleSheet("color: #ef4444;")
            self.svg_container_layout.addWidget(self.placeholder_svg_label)
            self.right_info.setText("Error loading result")

    def clear(self) -> None:
        """Reset preview states and clear images."""
        self.original_label.clear()
        self.original_label.setText("")
        self.left_info.setText("No image selected")
        self.clear_svg_container()

        self.placeholder_svg_label = QLabel("Waiting for tracing...", self.svg_container)
        self.placeholder_svg_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.placeholder_svg_label.setStyleSheet("color: #52525b;")
        self.svg_container_layout.addWidget(self.placeholder_svg_label)
        self.right_info.setText("No output SVG")

    def clear_svg_container(self) -> None:
        """Helper to clear child widgets from the SVG container."""
        if self.svg_widget is not None:
            self.svg_container_layout.removeWidget(self.svg_widget)
            self.svg_widget.deleteLater()
            self.svg_widget = None

        # Clear any layout items
        while self.svg_container_layout.count() > 0:
            item = self.svg_container_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
