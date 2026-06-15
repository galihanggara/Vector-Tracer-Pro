"""
tests.unit.ui.test_control_panel
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Unit tests for ControlPanel.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import Qt

from vector_tracer_pro.ui.widgets.control_panel import ControlPanel, TraceRequest


@pytest.mark.gui
class TestControlPanel:
    """Verifies ControlPanel UI state transitions and signal emissions."""

    def test_initial_state(self, qtbot) -> None:
        panel = ControlPanel()
        qtbot.addWidget(panel)

        assert panel.preset_combo.count() == 0
        assert panel.marketplace_combo.currentText() == "adobe_stock"
        assert panel.trace_btn.isEnabled() is False
        assert panel.add_batch_btn.isEnabled() is False
        assert panel.progress_bar.isHidden() is True

    def test_set_presets(self, qtbot) -> None:
        panel = ControlPanel()
        qtbot.addWidget(panel)

        panel.set_presets(["preset1", "preset2"])
        assert panel.preset_combo.count() == 2
        assert panel.preset_combo.itemText(0) == "preset1"
        assert panel.preset_combo.itemText(1) == "preset2"

    def test_enables_buttons_when_input_and_output_selected(self, qtbot) -> None:
        panel = ControlPanel()
        qtbot.addWidget(panel)

        panel.set_current_input_path(Path("in.png"))
        assert panel.trace_btn.isEnabled() is False

        panel.set_output_dir(Path("out/"))
        assert panel.trace_btn.isEnabled() is True
        assert panel.add_batch_btn.isEnabled() is True

    def test_trace_now_emits_signal(self, qtbot) -> None:
        panel = ControlPanel()
        qtbot.addWidget(panel)

        panel.set_presets(["my_preset"])
        panel.set_current_input_path(Path("in.png"))
        panel.set_output_dir(Path("out/"))

        with qtbot.waitSignal(panel.trace_requested) as blocker:
            qtbot.mouseClick(panel.trace_btn, Qt.MouseButton.LeftButton)

        assert blocker.args[0] == TraceRequest(
            input_path=Path("in.png"),
            preset_name="my_preset",
            output_dir=Path("out/"),
        )

    def test_add_to_batch_emits_signal(self, qtbot) -> None:
        panel = ControlPanel()
        qtbot.addWidget(panel)

        panel.set_presets(["my_preset"])
        panel.set_current_input_path(Path("in.png"))
        panel.set_output_dir(Path("out/"))

        with qtbot.waitSignal(panel.add_to_batch_requested) as blocker:
            qtbot.mouseClick(panel.add_batch_btn, Qt.MouseButton.LeftButton)

        assert blocker.args[0] == TraceRequest(
            input_path=Path("in.png"),
            preset_name="my_preset",
            output_dir=Path("out/"),
        )

    def test_progress_visibility(self, qtbot) -> None:
        panel = ControlPanel()
        qtbot.addWidget(panel)

        panel.show_progress("preprocessing", 40)
        assert panel.progress_bar.isHidden() is False
        assert panel.progress_label.text() == "Status: preprocessing..."
        assert panel.progress_bar.value() == 40

        panel.hide_progress()
        assert panel.progress_bar.isHidden() is True
        assert panel.progress_label.isHidden() is True
