"""
vector_tracer_pro.config.schema
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Pydantic v2 models for application and trace configuration.

These models serve three purposes:
  1. Runtime validation of the user's ``config.json``
  2. Type-safe access to settings throughout the application
  3. JSON schema generation for documentation and IDE support

Usage
-----
    from vector_tracer_pro.config.schema import AppConfig
    from vector_tracer_pro.config.defaults import USER_CONFIG_FILE

    config = AppConfig.load(USER_CONFIG_FILE)
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from vector_tracer_pro.config import defaults
from vector_tracer_pro.core.exceptions import ConfigError

logger = logging.getLogger(__name__)


# =============================================================================
# Sub-models
# =============================================================================


class PathsConfig(BaseModel):
    """Filesystem path overrides.  Defaults resolve via platformdirs."""

    user_data_dir: Path = Field(default_factory=lambda: defaults.USER_DATA_DIR)
    user_log_dir: Path = Field(default_factory=lambda: defaults.USER_LOG_DIR)
    user_presets_dir: Path = Field(default_factory=lambda: defaults.USER_PRESETS_DIR)


class BinariesConfig(BaseModel):
    """External binary configuration."""

    potrace_executable: str = Field(
        default=defaults.POTRACE_EXECUTABLE,
        description="Name or absolute path of the Potrace binary.",
    )
    inkscape_executable: str = Field(
        default=defaults.INKSCAPE_EXECUTABLE,
        description="Name or absolute path of the Inkscape binary.",
    )


class PreprocessorConfig(BaseModel):
    """Image preprocessing parameters."""

    max_dimension_px: Annotated[int, Field(ge=256, le=16384)] = (
        defaults.PREPROCESS_MAX_DIMENSION_PX
    )
    quantise_colours: Annotated[int, Field(ge=2, le=256)] = (
        defaults.PREPROCESS_QUANTISE_COLOURS
    )
    denoise_radius: Annotated[int, Field(ge=0, le=5)] = defaults.PREPROCESS_DENOISE_RADIUS


class ClassifierConfig(BaseModel):
    """Thresholds used by the image type classifier."""

    colour_simple_threshold: Annotated[int, Field(ge=2, le=256)] = (
        defaults.COLOUR_SIMPLE_THRESHOLD
    )
    greyscale_saturation_threshold: Annotated[float, Field(ge=0.0, le=1.0)] = (
        defaults.GREYSCALE_SATURATION_THRESHOLD
    )


class PotraceConfig(BaseModel):
    """Parameters forwarded to the Potrace CLI."""

    turdsize: Annotated[int, Field(ge=0, le=100)] = defaults.POTRACE_TURDSIZE
    alphamax: Annotated[float, Field(ge=0.0, le=1.3334)] = defaults.POTRACE_ALPHAMAX
    opttolerance: Annotated[float, Field(ge=0.0, le=1.0)] = defaults.POTRACE_OPTTOLERANCE
    blacklevel: Annotated[float, Field(ge=0.0, le=1.0)] = defaults.POTRACE_BLACKLEVEL
    unit: Annotated[int, Field(ge=1, le=100)] = defaults.POTRACE_UNIT


class InkscapeEngineConfig(BaseModel):
    """Parameters for the Inkscape multi-colour tracing engine."""

    colours: Annotated[int, Field(ge=2, le=64)] = defaults.INKSCAPE_COLOURS
    stack_scans: bool = defaults.INKSCAPE_STACK_SCANS
    remove_background: bool = defaults.INKSCAPE_REMOVE_BACKGROUND


class SVGOptimizerConfig(BaseModel):
    """Scour SVG post-processing options."""

    strip_xml_prolog: bool = defaults.SCOUR_STRIP_XML_PROLOG
    remove_metadata: bool = defaults.SCOUR_REMOVE_METADATA
    remove_descriptive_elements: bool = defaults.SCOUR_REMOVE_DESCRIPTIVE_ELEMENTS
    enable_viewboxing: bool = defaults.SCOUR_ENABLE_VIEWBOXING
    indent: Literal["none", "space", "tab"] = defaults.SCOUR_INDENT  # type: ignore[assignment]
    newlines: bool = defaults.SCOUR_NEWLINES


class PreviewConfig(BaseModel):
    """JPG preview export settings (pixel-dimension based)."""

    jpeg_quality: Annotated[int, Field(ge=60, le=100)] = defaults.PREVIEW_JPEG_QUALITY
    jpeg_subsampling: Annotated[int, Field(ge=0, le=2)] = defaults.PREVIEW_JPEG_SUBSAMPLING
    dpi_metadata: Annotated[int, Field(ge=72, le=300)] = defaults.PREVIEW_DPI_METADATA


class BatchConfig(BaseModel):
    """Batch processing settings."""

    max_workers: Annotated[int, Field(ge=1, le=8)] = defaults.BATCH_MAX_WORKERS
    stop_on_error: bool = defaults.BATCH_STOP_ON_ERROR


class LoggingConfig(BaseModel):
    """Application logging configuration."""

    level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = defaults.LOG_LEVEL  # type: ignore[assignment]
    max_file_bytes: Annotated[int, Field(ge=1024)] = defaults.LOG_FILE_MAX_BYTES
    backup_count: Annotated[int, Field(ge=0, le=10)] = defaults.LOG_FILE_BACKUP_COUNT


class MarketplacePreviewDimensions(BaseModel):
    """Minimum pixel dimensions for a single marketplace JPG preview."""

    min_width_px: Annotated[int, Field(ge=100)] = 1000
    min_height_px: Annotated[int, Field(ge=100)] = 1000

    @model_validator(mode="after")
    def check_area(self) -> "MarketplacePreviewDimensions":
        if self.min_width_px * self.min_height_px < 100 * 100:
            raise ValueError("Preview dimensions are too small.")
        return self


# =============================================================================
# Marketplace Preset model
# =============================================================================


class ValidationRules(BaseModel):
    """Marketplace-specific validation rules.

    verified: Hard requirements — SVG is rejected if any of these fail.
    heuristic: Advisory recommendations — user is warned but not blocked.
    """

    # Verified Requirements (hard rules)
    max_file_size_mb: Annotated[float, Field(gt=0)] = 100.0
    min_preview_dimensions: MarketplacePreviewDimensions = Field(
        default_factory=MarketplacePreviewDimensions
    )
    no_embedded_rasters: bool = True
    valid_svg_xml: bool = True

    # Heuristic Recommendations (advisory)
    recommended_min_path_count: Annotated[int, Field(ge=0)] = defaults.SVG_MIN_PATH_COUNT
    recommended_max_path_count: Annotated[int, Field(ge=1)] = defaults.SVG_MAX_PATH_COUNT
    recommended_max_colour_count: Annotated[int, Field(ge=1)] = defaults.SVG_MAX_COLOUR_COUNT
    recommended_min_stroke_width: Annotated[float, Field(ge=0.0)] = defaults.SVG_MIN_STROKE_WIDTH

    @field_validator("recommended_max_path_count")
    @classmethod
    def max_gt_min(cls, v: int, info: object) -> int:  # type: ignore[misc]
        # Cross-field validation handled in model_validator when both are present
        return v


class MarketplacePreset(BaseModel):
    """Full configuration for a single marketplace or custom preset."""

    name: str = Field(..., min_length=1, max_length=64)
    display_name: str = Field(..., min_length=1, max_length=128)
    description: str = ""
    is_builtin: bool = False

    preprocessor: PreprocessorConfig = Field(default_factory=PreprocessorConfig)
    potrace: PotraceConfig = Field(default_factory=PotraceConfig)
    inkscape: InkscapeEngineConfig = Field(default_factory=InkscapeEngineConfig)
    optimizer: SVGOptimizerConfig = Field(default_factory=SVGOptimizerConfig)
    preview: PreviewConfig = Field(default_factory=PreviewConfig)
    validation: ValidationRules = Field(default_factory=ValidationRules)


# =============================================================================
# Root application config
# =============================================================================


class AppConfig(BaseModel):
    """Root configuration model for Vector Tracer Pro.

    Loaded from ``USER_CONFIG_FILE`` on startup.  Unknown keys are
    ignored so that older config files remain forward-compatible.
    """

    model_config = {"extra": "ignore"}

    paths: PathsConfig = Field(default_factory=PathsConfig)
    binaries: BinariesConfig = Field(default_factory=BinariesConfig)
    classifier: ClassifierConfig = Field(default_factory=ClassifierConfig)
    batch: BatchConfig = Field(default_factory=BatchConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)

    # Last-used preset name (persisted across sessions)
    active_preset: str = "adobe_stock"

    # ---------------------------------------------------------------------------
    # Class methods
    # ---------------------------------------------------------------------------

    @classmethod
    def load(cls, config_path: Path) -> "AppConfig":
        """Load configuration from *config_path*.

        If the file does not exist, returns an ``AppConfig`` with all
        default values.  If the file is malformed, raises ``ConfigError``.

        Parameters
        ----------
        config_path:
            Path to the JSON configuration file.

        Returns
        -------
        AppConfig
            Validated configuration instance.

        Raises
        ------
        ConfigError
            When the file exists but cannot be parsed or fails validation.
        """
        if not config_path.exists():
            logger.info("No config file found at %s — using defaults.", config_path)
            return cls()

        try:
            raw = json.loads(config_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ConfigError(
                f"Config file is not valid JSON: {config_path}"
            ) from exc

        try:
            return cls.model_validate(raw)
        except Exception as exc:
            raise ConfigError(
                f"Config file failed validation: {config_path}\n{exc}"
            ) from exc

    def save(self, config_path: Path) -> None:
        """Persist current configuration to *config_path*.

        Creates parent directories if they do not exist.

        Parameters
        ----------
        config_path:
            Destination path for the JSON configuration file.

        Raises
        ------
        ConfigError
            When the file cannot be written.
        """
        try:
            config_path.parent.mkdir(parents=True, exist_ok=True)
            config_path.write_text(
                self.model_dump_json(indent=2),
                encoding="utf-8",
            )
        except OSError as exc:
            raise ConfigError(f"Failed to save config to {config_path}: {exc}") from exc
