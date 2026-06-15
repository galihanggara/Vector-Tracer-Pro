"""
tests.unit.ui.test_preview_panel
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Unit tests for PreviewPanel.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch
import pytest
from PySide6.QtGui import QPixmap
from PySide6.QtSvgWidgets import QSvgWidget

from vector_tracer_pro.ui.widgets.preview_panel import PreviewPanel


@pytest.mark.gui
class TestPreviewPanel:
    """Verifies image loading, SVG loading, and clearing of PreviewPanel."""

    def test_initial_state(self, qtbot) -> None:
        panel = PreviewPanel()
        qtbot.addWidget(panel)

        assert panel.left_info.text() == "No image selected"
        assert panel.right_info.text() == "No output SVG"
        assert panel.svg_widget is None
        assert panel.placeholder_svg_label.text() == "Waiting for tracing..."

    def test_show_original(self, qtbot, tmp_path) -> None:
        panel = PreviewPanel()
        qtbot.addWidget(panel)

        # Create dummy image path
        img_path = tmp_path / "test.png"
        
        # Mock QPixmap constructor/loading
        with patch.object(QPixmap, "load", return_value=True):
            with patch.object(QPixmap, "isNull", return_value=False):
                with patch.object(QPixmap, "width", return_value=800):
                    with patch.object(QPixmap, "height", return_value=600):
                        panel.show_original(img_path)

        assert panel.left_info.text() == "test.png (800x600)"
        assert panel.original_label.pixmap() is not None

    def test_show_result(self, qtbot, tmp_path) -> None:
        panel = PreviewPanel()
        qtbot.addWidget(panel)

        svg_path = tmp_path / "test.svg"
        svg_path.write_text("<svg></svg>")

        with patch.object(QSvgWidget, "load", return_value=True) as mock_load:
            panel.show_result(svg_path)
            
            assert panel.svg_widget is not None
            assert panel.right_info.text() == "test.svg (0.0 KB)"
            mock_load.assert_called_once_with(str(svg_path))

    def test_clear_resets_views(self, qtbot, tmp_path) -> None:
        panel = PreviewPanel()
        qtbot.addWidget(panel)

        # Set values
        img_path = tmp_path / "test.png"
        svg_path = tmp_path / "test.svg"
        svg_path.write_text("<svg></svg>")

        with patch.object(QPixmap, "load", return_value=True):
            with patch.object(QPixmap, "isNull", return_value=False):
                panel.show_original(img_path)

        with patch.object(QSvgWidget, "load", return_value=True):
            panel.show_result(svg_path)

        # Clear
        panel.clear()

        # Check reset
        assert panel.left_info.text() == "No image selected"
        assert panel.right_info.text() == "No output SVG"
        assert panel.svg_widget is None
        assert panel.placeholder_svg_label.text() == "Waiting for tracing..."
        assert panel.original_label.pixmap().isNull()
