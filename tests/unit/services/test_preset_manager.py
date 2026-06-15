"""
tests.unit.services.test_preset_manager
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Unit tests for PresetManager.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from vector_tracer_pro.services.preset_manager import PresetManager, TracingPreset


@pytest.mark.unit
class TestPresetManager:
    def test_save_and_load_preset(self, tmp_path: Path) -> None:
        manager = PresetManager(tmp_path)
        preset = TracingPreset(
            name="test_preset",
            marketplace="adobe_stock",
            engine_order=["potrace", "inkscape"],
            preprocess_config={"skip_denoise": True},
            trace_params={"turdsize": 10},
        )

        # Save
        manager.save(preset)

        # Verify file exists
        expected_file = tmp_path / "test_preset.json"
        assert expected_file.exists()

        # Load
        loaded = manager.load("test_preset")
        assert loaded.name == "test_preset"
        assert loaded.marketplace == "adobe_stock"
        assert loaded.engine_order == ["potrace", "inkscape"]
        assert loaded.preprocess_config == {"skip_denoise": True}
        assert loaded.trace_params == {"turdsize": 10}

    def test_load_nonexistent_raises_error(self, tmp_path: Path) -> None:
        manager = PresetManager(tmp_path)
        with pytest.raises(FileNotFoundError):
            manager.load("nonexistent")

    def test_list_presets(self, tmp_path: Path) -> None:
        manager = PresetManager(tmp_path)
        preset1 = TracingPreset("preset_b", "shutterstock", [], {}, {})
        preset2 = TracingPreset("preset_a", "freepik", [], {}, {})

        manager.save(preset1)
        manager.save(preset2)

        presets = manager.list_presets()
        assert presets == ["preset_a", "preset_b"]

    def test_delete_preset(self, tmp_path: Path) -> None:
        manager = PresetManager(tmp_path)
        preset = TracingPreset("to_delete", "freepik", [], {}, {})
        manager.save(preset)

        # Verify file exists
        file_path = tmp_path / "to_delete.json"
        assert file_path.exists()

        # Delete
        manager.delete("to_delete")
        assert not file_path.exists()

        # Delete again raises FileNotFoundError
        with pytest.raises(FileNotFoundError):
            manager.delete("to_delete")
