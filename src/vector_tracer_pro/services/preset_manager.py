"""
vector_tracer_pro.services.preset_manager
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Persistently saves and loads user-defined vectorisation presets.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass
class TracingPreset:
    """Dataclass holding all configurations for a custom vectorisation preset."""

    name: str
    marketplace: str  # "adobe_stock" | "shutterstock" | "freepik"
    engine_order: list[str]  # ["potrace", "vtracer", "inkscape"]
    preprocess_config: dict  # serialized PreprocessConfig
    trace_params: dict  # serialized TraceParams


class PresetManager:
    """Manages saving, loading, listing, and deleting tracing presets on disk."""

    def __init__(self, config_dir: Path) -> None:
        """Initialize PresetManager with config directory path.

        Parameters
        ----------
        config_dir:
            Directory where preset JSON files are stored.
        """
        self.config_dir = config_dir
        self.config_dir.mkdir(parents=True, exist_ok=True)

    def save(self, preset: TracingPreset) -> None:
        """Persist a TracingPreset as JSON to disk.

        Parameters
        ----------
        preset:
            The TracingPreset instance to save.
        """
        file_path = self.config_dir / f"{preset.name}.json"
        data = asdict(preset)
        file_path.write_text(json.dumps(data, indent=4), encoding="utf-8")

    def load(self, name: str) -> TracingPreset:
        """Load a TracingPreset from disk by name.

        Parameters
        ----------
        name:
            The preset name (excluding suffix).

        Returns
        -------
        TracingPreset
            The loaded TracingPreset instance.

        Raises
        ------
        FileNotFoundError
            If the preset file does not exist.
        """
        file_path = self.config_dir / f"{name}.json"
        if not file_path.exists():
            raise FileNotFoundError(f"Preset '{name}' not found.")

        data = json.loads(file_path.read_text(encoding="utf-8"))
        return TracingPreset(
            name=data["name"],
            marketplace=data["marketplace"],
            engine_order=data["engine_order"],
            preprocess_config=data["preprocess_config"],
            trace_params=data["trace_params"],
        )

    def list_presets(self) -> list[str]:
        """List all saved preset names sorted alphabetically.

        Returns
        -------
        list[str]
            Alphabetically sorted list of preset names.
        """
        names = []
        for file in self.config_dir.glob("*.json"):
            names.append(file.stem)
        return sorted(names)

    def delete(self, name: str) -> None:
        """Delete a TracingPreset from disk.

        Parameters
        ----------
        name:
            The preset name to delete.

        Raises
        ------
        FileNotFoundError
            If the preset file does not exist.
        """
        file_path = self.config_dir / f"{name}.json"
        if file_path.exists():
            file_path.unlink()
        else:
            raise FileNotFoundError(f"Preset '{name}' not found.")
