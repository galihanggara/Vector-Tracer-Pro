"""
vector_tracer_pro.ui.widgets.drop_zone
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

A custom widget that allows users to drag & drop JPG/PNG files, or click
to browse and select files using a QFileDialog.
"""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QDragEnterEvent, QDragLeaveEvent, QDropEvent, QMouseEvent
from PySide6.QtWidgets import QFileDialog, QHBoxLayout, QLabel, QWidget

logger = logging.getLogger(__name__)


class DropZoneWidget(QWidget):
    """Widget allowing users to drop images or click to select them."""

    files_dropped = Signal(list)  # Emits list[Path]
    files_selected = Signal(list)  # Emits list[Path]

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setObjectName("DropZone")

        # Layout & Label
        self.layout = QHBoxLayout(self)
        self.label = QLabel("Drop JPG/PNG here or click to browse", self)
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setStyleSheet("color: #a1a1aa; font-weight: bold;")
        self.layout.addWidget(self.label)

        # Style definition
        self.idle_style = """
            QWidget#DropZone {
                border: 2px dashed #3f3f46;
                border-radius: 8px;
                background-color: #202024;
            }
            QWidget#DropZone:hover {
                border-color: #52525b;
                background-color: #272730;
            }
        """
        self.active_style = """
            QWidget#DropZone {
                border: 2px solid #6366f1;
                border-radius: 8px;
                background-color: #312e81;
            }
        """
        self.setStyleSheet(self.idle_style)

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        """Handle mouse click to open the file selection dialog."""
        if event.button() == Qt.MouseButton.LeftButton:
            files, _ = QFileDialog.getOpenFileNames(
                self,
                "Select Images to Trace",
                "",
                "Image Files (*.jpg *.jpeg *.png)",
            )
            if files:
                paths = [Path(f) for f in files]
                logger.debug("Files selected via dialog: %s", paths)
                self.files_selected.emit(paths)
        else:
            super().mousePressEvent(event)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:  # noqa: N802
        """Handle drag enter event and filter for image files."""
        if event.mimeData().hasUrls():
            has_valid_file = False
            for url in event.mimeData().urls():
                suffix = Path(url.toLocalFile()).suffix.lower()
                if suffix in (".jpg", ".jpeg", ".png"):
                    has_valid_file = True
                    break
            if has_valid_file:
                event.acceptProposedAction()
                self.setStyleSheet(self.active_style)
        else:
            event.ignore()

    def dragLeaveEvent(self, event: QDragLeaveEvent) -> None:  # noqa: N802
        """Reset styling when the drag leaves the widget bounds."""
        self.setStyleSheet(self.idle_style)
        event.accept()

    def dropEvent(self, event: QDropEvent) -> None:  # noqa: N802
        """Extract dropped local paths and emit the signal."""
        self.setStyleSheet(self.idle_style)
        urls = event.mimeData().urls()
        paths: list[Path] = []
        for url in urls:
            path = Path(url.toLocalFile())
            if path.suffix.lower() in (".jpg", ".jpeg", ".png") and path.is_file():
                paths.append(path)

        if paths:
            logger.debug("Files dropped: %s", paths)
            self.files_dropped.emit(paths)
            event.acceptProposedAction()
        else:
            event.ignore()
