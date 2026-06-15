"""
tests.unit.ui.test_drop_zone
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Unit tests for DropZoneWidget.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from PySide6.QtCore import QMimeData, QPoint, Qt, QUrl
from PySide6.QtGui import QDragEnterEvent, QDropEvent

from vector_tracer_pro.ui.widgets.drop_zone import DropZoneWidget


@pytest.mark.gui
class TestDropZoneWidget:
    """Verifies DropZoneWidget drag/drop and click browse signals."""

    def test_initial_state(self, qtbot) -> None:
        widget = DropZoneWidget()
        qtbot.addWidget(widget)

        assert widget.label.text() == "Drop JPG/PNG here or click to browse"
        assert widget.acceptDrops() is True

    @patch("PySide6.QtWidgets.QFileDialog.getOpenFileNames")
    def test_mouse_click_browse_selects_files(self, mock_get_files, qtbot) -> None:
        widget = DropZoneWidget()
        qtbot.addWidget(widget)

        # Mock user selecting 2 files
        mock_get_files.return_value = (["/path/to/img1.png", "/path/to/img2.jpg"], "Image Files")

        # Track signals
        with qtbot.waitSignal(widget.files_selected) as blocker:
            qtbot.mouseClick(widget, Qt.MouseButton.LeftButton)

        # Verify signals and values
        assert blocker.args[0] == [Path("/path/to/img1.png"), Path("/path/to/img2.jpg")]
        mock_get_files.assert_called_once()

    def test_drag_enter_accepts_valid_image(self, qtbot) -> None:
        widget = DropZoneWidget()
        qtbot.addWidget(widget)

        mime = QMimeData()
        mime.setUrls([QUrl.fromLocalFile("/path/to/image.png")])
        event = QDragEnterEvent(
            QPoint(0, 0),
            Qt.DropAction.CopyAction,
            mime,
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
        )

        widget.dragEnterEvent(event)
        assert event.isAccepted() is True

    def test_drag_enter_ignores_invalid_files(self, qtbot) -> None:
        widget = DropZoneWidget()
        qtbot.addWidget(widget)

        mime = QMimeData()
        mime.setUrls([QUrl.fromLocalFile("/path/to/document.pdf")])
        event = QDragEnterEvent(
            QPoint(0, 0),
            Qt.DropAction.CopyAction,
            mime,
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
        )

        widget.dragEnterEvent(event)
        assert event.isAccepted() is False

    def test_drop_event_emits_paths(self, qtbot) -> None:
        widget = DropZoneWidget()
        qtbot.addWidget(widget)

        mime = QMimeData()
        mime.setUrls(
            [
                QUrl.fromLocalFile("/path/to/img.png"),
                QUrl.fromLocalFile("/path/to/doc.txt"),  # should be ignored
            ]
        )
        event = QDropEvent(
            QPoint(0, 0),
            Qt.DropAction.CopyAction,
            mime,
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
        )

        # Mock that file is a file
        with patch.object(Path, "is_file", return_value=True):
            with qtbot.waitSignal(widget.files_dropped) as blocker:
                widget.dropEvent(event)

            assert blocker.args[0] == [Path("/path/to/img.png")]
            assert event.isAccepted() is True
