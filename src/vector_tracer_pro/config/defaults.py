"""
vector_tracer_pro.config.defaults
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Application-wide default settings.

These values are used when no user configuration file exists and as
the baseline when merging user overrides with ``config/schema.py``.

All path values use ``platformdirs`` so the application is portable
across Windows user accounts without hard-coding any paths.
"""

from __future__ import annotations

from pathlib import Path

from platformdirs import user_data_dir, user_log_dir

# ---------------------------------------------------------------------------
# Application identity
# ---------------------------------------------------------------------------
APP_NAME: str = "VectorTracerPro"
APP_AUTHOR: str = "VectorTracerPro"

# ---------------------------------------------------------------------------
# Runtime paths (resolved at import time)
# ---------------------------------------------------------------------------
USER_DATA_DIR: Path = Path(user_data_dir(APP_NAME, APP_AUTHOR))
USER_LOG_DIR: Path = Path(user_log_dir(APP_NAME, APP_AUTHOR))
USER_PRESETS_DIR: Path = USER_DATA_DIR / "presets"
USER_CONFIG_FILE: Path = USER_DATA_DIR / "config.json"

# Built-in preset directory (inside the installed package)
BUILTIN_PRESETS_DIR: Path = Path(__file__).parent.parent / "resources" / "presets"

# ---------------------------------------------------------------------------
# External binary defaults
# ---------------------------------------------------------------------------
POTRACE_EXECUTABLE: str = "potrace"  # expected on PATH
INKSCAPE_EXECUTABLE: str = "inkscape"  # expected on PATH
POTRACE_MINIMUM_VERSION: str = "1.16"
INKSCAPE_MINIMUM_VERSION: str = "1.0"

# ---------------------------------------------------------------------------
# Image loading defaults
# ---------------------------------------------------------------------------
SUPPORTED_INPUT_FORMATS: tuple[str, ...] = ("JPEG", "PNG")
MIN_INPUT_WIDTH_PX: int = 500
MIN_INPUT_HEIGHT_PX: int = 500

# ---------------------------------------------------------------------------
# Classifier thresholds
# ---------------------------------------------------------------------------
# If unique colours in quantised image < this, consider "simple colour"
COLOUR_SIMPLE_THRESHOLD: int = 16
# If unique colours < this, consider "greyscale-like" (route to Potrace)
GREYSCALE_SATURATION_THRESHOLD: float = 0.05  # max average saturation

# ---------------------------------------------------------------------------
# Preprocessor defaults
# ---------------------------------------------------------------------------
PREPROCESS_MAX_DIMENSION_PX: int = 4096  # longest edge cap before tracing
PREPROCESS_QUANTISE_COLOURS: int = 32  # palette size for colour quantisation
PREPROCESS_DENOISE_RADIUS: int = 1  # median filter radius (0 = disabled)

# ---------------------------------------------------------------------------
# Potrace engine defaults
# ---------------------------------------------------------------------------
POTRACE_TURDSIZE: int = 2  # suppress speckles smaller than this
POTRACE_ALPHAMAX: float = 1.0  # corner threshold (0=pointy, >1=round)
POTRACE_OPTTOLERANCE: float = 0.2  # curve optimisation tolerance
POTRACE_BLACKLEVEL: float = 0.5  # threshold between black and white
POTRACE_UNIT: int = 10  # quantisation unit

# ---------------------------------------------------------------------------
# Inkscape engine defaults (multi-colour tracing)
# ---------------------------------------------------------------------------
INKSCAPE_COLOURS: int = 8  # number of colour passes
INKSCAPE_STACK_SCANS: bool = True  # stack colour layers
INKSCAPE_REMOVE_BACKGROUND: bool = True

# ---------------------------------------------------------------------------
# SVG optimiser (scour) defaults
# ---------------------------------------------------------------------------
SCOUR_STRIP_XML_PROLOG: bool = False
SCOUR_REMOVE_METADATA: bool = True
SCOUR_REMOVE_DESCRIPTIVE_ELEMENTS: bool = True
SCOUR_ENABLE_VIEWBOXING: bool = True
SCOUR_INDENT: str = "none"  # no indentation for minimal file size
SCOUR_NEWLINES: bool = False

# ---------------------------------------------------------------------------
# SVG validator defaults
# ---------------------------------------------------------------------------
SVG_MIN_PATH_COUNT: int = 3
SVG_MAX_PATH_COUNT: int = 8000
SVG_MAX_COLOUR_COUNT: int = 64
SVG_MIN_STROKE_WIDTH: float = 0.5  # paths thinner than this trigger a warning

# ---------------------------------------------------------------------------
# JPG preview export defaults (pixel-dimension based, NOT DPI-based)
# ---------------------------------------------------------------------------
PREVIEW_JPEG_QUALITY: int = 90
PREVIEW_JPEG_SUBSAMPLING: int = 0  # 4:4:4 for maximum quality
PREVIEW_DPI_METADATA: int = 72  # metadata only; sizing is pixel-based

# Per-marketplace minimum pixel dimensions for JPG previews
PREVIEW_MIN_DIMENSIONS: dict[str, tuple[int, int]] = {
    # (min_width_px, min_height_px)
    "adobe_stock": (1600, 1200),
    "shutterstock": (1500, 1000),
    "freepik": (1000, 1000),
    "default": (1000, 1000),
}

# ---------------------------------------------------------------------------
# Batch runner defaults
# ---------------------------------------------------------------------------
BATCH_MAX_WORKERS: int = 1  # sequential by default; UI can increase
BATCH_STOP_ON_ERROR: bool = False  # continue batch on single-file failure

# ---------------------------------------------------------------------------
# Logging defaults
# ---------------------------------------------------------------------------
LOG_FILE_MAX_BYTES: int = 5 * 1024 * 1024  # 5 MB per log file
LOG_FILE_BACKUP_COUNT: int = 3  # keep 3 rotated logs
LOG_LEVEL: str = "INFO"
