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
* **Thread-safe, re-entrant lock** — an ``RLock`` guards all ``mkdir``
  calls.  Because ``ensure_all_dirs`` calls multiple accessors (each of which
  acquires the lock), an ``RLock`` is required to allow re-acquisition by the
  same thread without deadlock.
* **Collision-free temp paths** — :meth:`temp_path_for` prepends a short
  UUID so that two source files sharing the same stem (e.g. ``logo.jpg``
  from different directories) never produce the same intermediate file.
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
        Cache\\temp\\    ← intermediate BMP / PBM files  (UUID-prefixed)
        Logs\\           ← rotating log files

    %APPDATA%\\VectorTracerPro\\
        config.json      ← persisted user settings
        presets\\        ← user-created marketplace presets
"""

from __future__ import annotations

import logging
import sys
import threading
import uuid
from pathlib import Path
from typing import Final

from platformdirs import (
    user_cache_dir,
    user_config_dir,
    user_documents_dir,
    user_log_dir,
)

from vector_tracer_pro.config.defaults import APP_AUTHOR, APP_NAME

logger = logging.getLogger(__name__)


def _is_bundled() -> bool:
    """Check if the application is running from a PyInstaller bundle."""
    return getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS")


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
        self._temp_root: Path = temp_root if temp_root is not None else self._cache_dir / "temp"

        # Unique session ID for isolating temp folders between app instances
        self._session_id: str = f"session_{uuid.uuid4().hex[:12]}"

        # RLock (re-entrant): the *same* thread can acquire the lock multiple
        # times without blocking.  This is necessary because ensure_all_dirs()
        # calls multiple accessor methods, each of which calls _ensure() and
        # acquires the lock — a plain Lock would deadlock on the second call.
        self._lock: threading.RLock = threading.RLock()

    # ------------------------------------------------------------------
    # Public read-only properties (no side effects, no directory creation)
    # ------------------------------------------------------------------

    @property
    def temp_root(self) -> Path:
        """Return the temp root path without creating it.

        Use this when you need the path for inspection or configuration,
        not when you need the directory to actually exist.
        """
        return self._temp_root

    @property
    def session_id(self) -> str:
        """Return the unique session ID string."""
        return self._session_id

    @property
    def config_dir_path(self) -> Path:
        """Return the config directory path without creating it."""
        return self._config_dir

    @property
    def log_dir_path(self) -> Path:
        """Return the log directory path without creating it."""
        return self._log_dir

    # ------------------------------------------------------------------
    # Directory accessors (auto-create on first call)
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
        """Return the session-isolated directory for intermediate temporary files.

        Intermediate files (BMP, PBM, temporary SVG) are written here
        and cleaned up by the pipeline after each trace completes.

        Returns
        -------
        Path
            Typically ``%LOCALAPPDATA%\\VectorTracerPro\\Cache\\temp\\session_<uuid>``.
        """
        return self._ensure(self._temp_root / self._session_id)

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
        """Derive a **unique** temporary intermediate file path.

        A short UUID prefix is prepended to the stem so that two source images
        sharing the same filename (e.g. ``logo.jpg`` from different directories)
        never produce the same intermediate file.  Each call returns a
        different path even for identical inputs.

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
            Unique temporary path inside :meth:`get_temp_dir`.

        Examples
        --------
        >>> pm.temp_path_for(Path("sunset.jpg"), suffix=".bmp")
        WindowsPath('.../Cache/temp/3a1b2c4d_sunset.bmp')
        """
        unique_prefix = uuid.uuid4().hex[:8]
        filename = f"{unique_prefix}_{input_path.stem}{suffix}"
        return self.get_temp_dir() / filename

    # ------------------------------------------------------------------
    # Cleanup API
    # ------------------------------------------------------------------

    def cleanup_temp_file(self, path: Path) -> bool:
        """Delete a single temporary file produced by this manager.

        Parameters
        ----------
        path:
            Path to the file to delete.

        Returns
        -------
        bool
            ``True`` if the file was deleted; ``False`` if it did not exist.

        Raises
        ------
        OSError
            If the file exists but cannot be deleted (e.g. permission error
            or file locked by another process).
        """
        if not path.is_file():
            return False
        path.unlink()
        logger.debug("Deleted temp file: %s", path)
        return True

    def cleanup_all_temp_files(self) -> int:
        """Delete all *files* in the session temp directory, then delete the folder itself.

        Individual deletion failures are logged at WARNING level and skipped
        so that a single locked file does not abort the entire cleanup.

        Returns
        -------
        int
            Number of files successfully deleted.
        """
        temp_dir = self.get_temp_dir()
        deleted = 0
        if not temp_dir.is_dir():
            return 0
        for entry in temp_dir.iterdir():
            if entry.is_file():
                try:
                    entry.unlink()
                    deleted += 1
                    logger.debug("Deleted temp file: %s", entry)
                except OSError as exc:
                    logger.warning("Could not delete temp file %s: %s", entry, exc)
        try:
            temp_dir.rmdir()
            logger.info("Deleted session temp directory: %s", temp_dir)
        except OSError as exc:
            logger.warning("Could not delete session temp directory %s: %s", temp_dir, exc)
        return deleted

    def cleanup_orphaned_sessions(self) -> int:
        """Delete any other session directories from previous runs that were not cleaned up.

        Searches for sub-directories in the temp root starting with ``"session_"``
        (excluding the current session) and attempts to delete them and their contents.

        Returns
        -------
        int
            Number of orphaned sessions successfully deleted.
        """
        import shutil

        deleted = 0
        if not self._temp_root.is_dir():
            return 0
        for entry in self._temp_root.iterdir():
            if (
                entry.is_dir()
                and entry.name.startswith("session_")
                and entry.name != self._session_id
            ):
                try:
                    shutil.rmtree(entry)
                    deleted += 1
                    logger.info("Deleted orphaned session directory: %s", entry)
                except OSError as exc:
                    logger.warning("Could not delete orphaned session directory %s: %s", entry, exc)
        return deleted

    # ------------------------------------------------------------------
    # Bulk operations
    # ------------------------------------------------------------------

    def ensure_all_dirs(self) -> None:
        """Create all standard application directories.

        Safe to call multiple times — uses ``exist_ok=True`` internally.
        Typically called once at application startup by the controller.
        The ``RLock`` allows this method to call multiple accessors without
        deadlocking on the re-entrant lock acquisitions.
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
        folder via the UI.  Thread-safe via the internal RLock.

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

        Thread-safe via the internal RLock.  Returns *path* unchanged so
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

    def get_binary_dir(self) -> Path:
        """Get the directory containing bundled or dev binaries.

        Returns
        -------
        Path
            The bin/ folder directory.
        """
        if _is_bundled():
            return Path(sys._MEIPASS) / "bin"
        else:
            # Resolve project root
            # path_manager.py is at <project_root>/src/vector_tracer_pro/core/path_manager.py
            project_root = Path(__file__).resolve().parent.parent.parent.parent
            return project_root / "bin"

    def get_binary_path(self, name: str) -> str:
        """Resolve absolute path to a binary under get_binary_dir() or fall back to name.

        On Windows, appends .exe if not present.
        """
        # If the input is already a full path, use it directly
        if Path(name).is_absolute():
            print(f"[DEBUG] get_binary_path({name!r}) absolute: {name}")
            return name

        pure_name = Path(name).stem
        binary_name = f"{pure_name}.exe" if sys.platform == "win32" else pure_name
        local_path = self.get_binary_dir() / binary_name

        print(f"[DEBUG] binary_dir={self.get_binary_dir()}")
        resolved = str(local_path) if local_path.exists() else name
        print(f"[DEBUG] get_binary_path({name!r}) resolved to: {resolved}")

        if local_path.exists():
            return str(local_path)
        return name

    # ------------------------------------------------------------------
    # Dunder methods
    # ------------------------------------------------------------------

    def __repr__(self) -> str:  # pragma: no cover
        return f"PathManager(output_root={self._output_root!r}, temp_root={self._temp_root!r})"
