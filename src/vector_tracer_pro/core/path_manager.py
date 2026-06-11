"""
vector_tracer_pro.core.path_manager
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Centralised filesystem abstraction for Vector Tracer Pro.

All application directory resolution is performed here.  No other module
should construct application paths directly — they must use this class or
accept paths as parameters.

Design principles
-----------------
* **No hardcoded paths** — all base directories come from ``platformdirs``,
  which returns Windows-appropriate locations (``%APPDATA%``,
  ``%LOCALAPPDATA%``, ``%USERPROFILE%\\Documents``, etc.).
* **Automatic directory creation** — every directory accessor calls
  :meth:`_ensure`, which calls ``Path.mkdir(parents=True, exist_ok=True)``.
* **Thread-safe creation** — a ``threading.Lock`` guards all ``mkdir``
  calls to prevent TOCTOU races in multi-threaded batch contexts.
* **Configurable output root** — the UI can call :meth:`set_output_root`
  when the user selects a different output folder without recreating the
  manager instance.

Typical directory layout on Windows 11
---------------------------------------
::

    %USERPROFILE%\\Documents\\VectorTracerPro\\
        Input\\          ← default file-picker starting directory
        Output\\
            SVG\\        ← traced SVG files
            Previews\\   ← JPG preview files

    %LOCALAPPDATA%\\VectorTracerPro\\
        Cache\\temp\\    ← intermediate BMP / PBM files
        Logs\\           ← rotating log files

    %APPDATA%\\VectorTracerPro\\
        config.json      ← persisted user settings
        presets\\        ← user-created marketplace presets
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Final

from platformdirs import (
    user_cache_dir,
    user_config_dir,
    user_documents_dir,
    user_log_dir,
)

from vector_tracer_pro.config.defaults import APP_AUTHOR, APP_NAME

# Folder name used inside all platform-managed directories.
_APP_FOLDER: Final[str] = APP_NAME  # "VectorTracerPro"


class PathManager:
    """Centralised filesystem path resolver for Vector Tracer Pro.

    Parameters
    ----------
    output_root:
        Override the base directory for SVG and JPG preview output.
        Defaults to ``%USERPROFILE%\\Documents\\VectorTracerPro\\Output``.
    temp_root:
        Override the directory for intermediate temporary files (BMP, PBM,
        temp SVG).  Defaults to the platform user-cache directory.

    Examples
    --------
    Default usage — all paths resolved from platform conventions:

    >>> pm = PathManager()
    >>> svg_dir = pm.get_output_svg_dir()     # created automatically
    >>> bmp = pm.temp_path_for(Path("photo.jpg"), suffix=".bmp")

    Custom output root selected by the user in the UI:

    >>> pm = PathManager(output_root=Path(r"D:\\MyVectors\\Output"))
    >>> pm.get_output_svg_dir()
    WindowsPath('D:/MyVectors/Output/SVG')
    """

    def __init__(
        self,
        *,
        output_root: Path | None = None,
        temp_root: Path | None = None,
    ) -> None:
        # --- platformdirs-derived base directories ----------------------------
        self._user_documents: Path = Path(user_documents_dir())
        self._config_dir: Path = Path(user_config_dir(_APP_FOLDER, APP_AUTHOR))
        self._log_dir: Path = Path(user_log_dir(_APP_FOLDER, APP_AUTHOR))
        self._cache_dir: Path = Path(user_cache_dir(_APP_FOLDER, APP_AUTHOR))

        # --- Configurable roots (support runtime override from UI) ------------
        self._output_root: Path = (
            output_root
            if output_root is not None
            else self._user_documents / _APP_FOLDER / "Output"
        )
        self._temp_root: Path = (
            temp_root if temp_root is not None else self._cache_dir / "temp"
        )

        # Non-reentrant lock — guards all mkdir calls
        self._lock: threading.Lock = threading.Lock()

    # ------------------------------------------------------------------
    # Directory accessors
    # ------------------------------------------------------------------

    def get_input_dir(self) -> Path:
        """Return the default input image staging directory.

        This is where the file-picker dialog opens by default.

        Returns
        -------
        Path
            Typically ``%USERPROFILE%\\Documents\\VectorTracerPro\\Input``.
        """
        return self._ensure(self._user_documents / _APP_FOLDER / "Input")

    def get_output_svg_dir(self) -> Path:
        """Return the directory for traced SVG output files.

        Returns
        -------
        Path
            Typically ``<output_root>\\SVG``.
        """
        return self._ensure(self._output_root / "SVG")

    def get_output_preview_dir(self) -> Path:
        """Return the directory for JPG preview output files.

        Returns
        -------
        Path
            Typically ``<output_root>\\Previews``.
        """
        return self._ensure(self._output_root / "Previews")

    def get_temp_dir(self) -> Path:
        """Return the directory for intermediate temporary files.

        Intermediate files (BMP, PBM, temporary SVG) are written here
        and cleaned up by the pipeline after each trace completes.

        Returns
        -------
        Path
            Typically ``%LOCALAPPDATA%\\VectorTracerPro\\Cache\\temp``.
        """
        return self._ensure(self._temp_root)

    def get_logs_dir(self) -> Path:
        """Return the application log directory.

        Returns
        -------
        Path
            Typically ``%LOCALAPPDATA%\\VectorTracerPro\\Logs``.
        """
        return self._ensure(self._log_dir)

    def get_config_dir(self) -> Path:
        """Return the user configuration directory.

        ``config.json`` and the ``presets/`` sub-directory live here.

        Returns
        -------
        Path
            Typically ``%APPDATA%\\VectorTracerPro``.
        """
        return self._ensure(self._config_dir)

    def get_user_presets_dir(self) -> Path:
        """Return the directory for user-created preset JSON files.

        Returns
        -------
        Path
            Typically ``%APPDATA%\\VectorTracerPro\\presets``.
        """
        return self._ensure(self._config_dir / "presets")

    # ------------------------------------------------------------------
    # Path derivation helpers
    # ------------------------------------------------------------------

    def svg_path_for(self, input_path: Path) -> Path:
        """Derive the output SVG path for a given source image.

        Parameters
        ----------
        input_path:
            Path to the source raster image.

        Returns
        -------
        Path
            Target SVG path with the same stem in :meth:`get_output_svg_dir`.

        Examples
        --------
        >>> pm.svg_path_for(Path("photos/bird.jpg"))
        WindowsPath('.../Output/SVG/bird.svg')
        """
        return self.get_output_svg_dir() / input_path.with_suffix(".svg").name

    def preview_path_for(self, input_path: Path) -> Path:
        """Derive the output JPG preview path for a given source image.

        Parameters
        ----------
        input_path:
            Path to the source raster image.

        Returns
        -------
        Path
            Target JPG path with the same stem in :meth:`get_output_preview_dir`.

        Examples
        --------
        >>> pm.preview_path_for(Path("art/logo.png"))
        WindowsPath('.../Output/Previews/logo.jpg')
        """
        return self.get_output_preview_dir() / input_path.with_suffix(".jpg").name

    def temp_path_for(self, input_path: Path, suffix: str = ".bmp") -> Path:
        """Derive a temporary intermediate file path for a given source image.

        Parameters
        ----------
        input_path:
            Path to the source raster image.
        suffix:
            File extension for the intermediate file.  Use ``".bmp"`` for
            Potrace and ``".pbm"`` for greyscale Potrace inputs.

        Returns
        -------
        Path
            Temporary path inside :meth:`get_temp_dir`.

        Examples
        --------
        >>> pm.temp_path_for(Path("sunset.jpg"), suffix=".bmp")
        WindowsPath('.../Cache/temp/sunset.bmp')
        """
        return self.get_temp_dir() / input_path.with_suffix(suffix).name

    # ------------------------------------------------------------------
    # Bulk operations
    # ------------------------------------------------------------------

    def ensure_all_dirs(self) -> None:
        """Create all standard application directories.

        Safe to call multiple times — uses ``exist_ok=True`` internally.
        Typically called once at application startup by the controller.
        """
        self.get_input_dir()
        self.get_output_svg_dir()
        self.get_output_preview_dir()
        self.get_temp_dir()
        self.get_logs_dir()
        self.get_config_dir()
        self.get_user_presets_dir()

    def set_output_root(self, path: Path) -> None:
        """Update the output root directory at runtime.

        Called by the controller when the user selects a different output
        folder via the UI.  Thread-safe: acquires the internal lock before
        reassigning.

        Parameters
        ----------
        path:
            New output root.  SVG and Preview sub-directories will be
            created under this path on the next accessor call.
        """
        with self._lock:
            self._output_root = path

    def get_output_root(self) -> Path:
        """Return the current output root directory (not auto-created).

        Returns
        -------
        Path
            The current value of the output root.
        """
        with self._lock:
            return self._output_root

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _ensure(self, path: Path) -> Path:
        """Create *path* and all parents if they do not already exist.

        Thread-safe via the internal lock.  Returns *path* unchanged so
        accessors can be used as expressions.

        Parameters
        ----------
        path:
            Directory to create if missing.

        Returns
        -------
        Path
            The same *path* that was passed in.
        """
        with self._lock:
            path.mkdir(parents=True, exist_ok=True)
        return path

    # ------------------------------------------------------------------
    # Dunder methods
    # ------------------------------------------------------------------

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"PathManager("
            f"output_root={self._output_root!r}, "
            f"temp_root={self._temp_root!r})"
        )
