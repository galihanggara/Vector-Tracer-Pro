"""
tests.unit.ui.test_main_window
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Unit tests for MainWindow.
"""

from __future__ import annotations

import pytest

from vector_tracer_pro.ui.main_window import MainWindow
from vector_tracer_pro.ui.widgets import (
    BatchQueueTable,
    ControlPanel,
    DropZoneWidget,
    PreviewPanel,
)


@pytest.mark.gui
class TestMainWindow:
    """Verifies layout hierarchy and skeleton construction of MainWindow."""

    def test_window_initialization(self, qtbot) -> None:
        window = MainWindow()
        qtbot.addWidget(window)

        # Check layouts and sizes
        assert window.windowTitle() == "Vector Tracer Pro"
        assert window.centralWidget() is not None
        assert window.horizontal_splitter is not None

        # Check panels exist
        assert isinstance(window.drop_zone, DropZoneWidget)
        assert isinstance(window.preview_panel, PreviewPanel)
        assert isinstance(window.control_panel, ControlPanel)
        assert isinstance(window.batch_table, BatchQueueTable)

    def test_status_bar_updates(self, qtbot) -> None:
        window = MainWindow()
        qtbot.addWidget(window)

        window.set_status("Hello World")
        # Access default status bar message
        assert window.statusBar().currentMessage() == "Hello World"

    def test_menu_bar_items(self, qtbot) -> None:
        window = MainWindow()
        qtbot.addWidget(window)

        menu_bar = window.menuBar()
        menus = menu_bar.findChildren(object)
        
        # Check menus exist by actions
        menu_titles = [action.text() for action in menu_bar.actions()]
        assert "File" in menu_titles
        assert "Preset" in menu_titles
        assert "Help" in menu_titles
