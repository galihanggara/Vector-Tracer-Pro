"""
vector_tracer_pro.core.marketplace_validator
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

SVG and JPG preview validation against marketplace specifications.

Validation is split into two tiers defined in the approved architecture:

Verified Requirements (hard rules — ``ValidationTier.VERIFIED``)
-----------------------------------------------------------------
A file fails these rules at stock submission time and will be rejected.
The pipeline hard-fails and does not export when any VERIFIED rule fails.

* Well-formed SVG XML
* No embedded raster ``<image>`` elements
* Valid ``http://www.w3.org/2000/svg`` namespace
* File size within the marketplace hard limit
* JPG preview minimum pixel dimensions (width × height)

Heuristic Recommendations (advisory — ``ValidationTier.HEURISTIC``)
--------------------------------------------------------------------
These indicate likely-but-not-guaranteed acceptance issues.  The user is
warned but the pipeline continues.

* Path count in the recommended range (too few = too simple, too many = bloated)
* Colour count within typical acceptance range
* No strokes thinner than 0.5 px (render poorly at small sizes)
* Viewbox matches artboard (prevents cropping in marketplace previews)

Built-in marketplace profiles
------------------------------
+---------------+------------------+------------------+------------------+
| Rule          | Adobe Stock      | Shutterstock     | Freepik          |
+===============+==================+==================+==================+
| Max SVG size  | 100 MB           | 50 MB            | 50 MB            |
+---------------+------------------+------------------+------------------+
| Min preview W | 1600 px          | 1500 px          | 1000 px          |
+---------------+------------------+------------------+------------------+
| Min preview H | 1200 px          | 1000 px          | 1000 px          |
+---------------+------------------+------------------+------------------+

.. note::

    This file is a **Sprint 2 skeleton**.  The :class:`MarketplaceValidator`
    class raises :exc:`NotImplementedError` for all public methods until
    Sprint 4.  Import the data types freely; do not call validation methods
    yet.

Usage (Sprint 4+)
-----------------
::

    from pathlib import Path
    from vector_tracer_pro.core.marketplace_validator import MarketplaceValidator

    validator = MarketplaceValidator()
    result = validator.validate_svg(Path("output.svg"), marketplace="adobe_stock")

    if not result.is_compliant:
        for issue in result.verified_failures:
            print(f"[FAIL] {issue.rule_id}: {issue.message}")

    for warning in result.warnings:
        print(f"[WARN] {warning.rule_id}: {warning.message}")
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Final
import xml.etree.ElementTree as ET



# ===========================================================================
# Enumerations
# ===========================================================================


class ValidationTier(Enum):
    """Which tier of validation rule produced this issue.

    Attributes
    ----------
    VERIFIED:
        Hard rule — the file is rejected if this fails.
    HEURISTIC:
        Advisory rule — the user is warned but not blocked.
    """

    VERIFIED = "verified"
    HEURISTIC = "heuristic"


class RuleStatus(Enum):
    """Outcome of applying a single validation rule.

    Attributes
    ----------
    PASS:
        The rule was satisfied.
    FAIL:
        The rule was violated (always paired with VERIFIED tier for blocking
        failures; advisory for HEURISTIC tier).
    WARN:
        The heuristic threshold was exceeded (only used with HEURISTIC tier).
    """

    PASS = auto()
    FAIL = auto()
    WARN = auto()


# ===========================================================================
# Data types
# ===========================================================================


@dataclass(frozen=True)
class ValidationIssue:
    """A single rule result from a marketplace validation pass.

    Attributes
    ----------
    tier:
        Whether this is a VERIFIED (hard) or HEURISTIC (advisory) rule.
    rule_id:
        Short machine-readable identifier, e.g. ``"no_embedded_rasters"``.
    message:
        Human-readable description of the issue.
    status:
        PASS, FAIL, or WARN.
    marketplace:
        Name of the marketplace whose rule this is, or ``None`` for
        universal rules.
    details:
        Optional extra context (e.g. element location in the SVG).
    """

    tier: ValidationTier
    rule_id: str
    message: str
    status: RuleStatus
    marketplace: str | None = None
    details: str = ""

    @property
    def is_failure(self) -> bool:
        """``True`` if this issue represents a FAIL (hard or advisory)."""
        return self.status is RuleStatus.FAIL

    @property
    def is_warning(self) -> bool:
        """``True`` if this is a heuristic warning."""
        return self.status is RuleStatus.WARN


@dataclass(frozen=True)
class ValidationResult:
    """Aggregated result of validating one file against one marketplace.

    Attributes
    ----------
    marketplace:
        Name of the marketplace profile used (e.g. ``"adobe_stock"``).
    file_path:
        Path to the file that was validated.
    issues:
        All :class:`ValidationIssue` objects collected during the pass.
    """

    marketplace: str
    file_path: Path
    issues: list[ValidationIssue] = field(default_factory=list)

    @property
    def is_compliant(self) -> bool:
        """``True`` if no VERIFIED rules failed."""
        return not any(
            i.tier is ValidationTier.VERIFIED and i.status is RuleStatus.FAIL
            for i in self.issues
        )

    @property
    def verified_failures(self) -> list[ValidationIssue]:
        """Hard-rule failures that prevent stock submission."""
        return [
            i
            for i in self.issues
            if i.tier is ValidationTier.VERIFIED and i.status is RuleStatus.FAIL
        ]

    @property
    def warnings(self) -> list[ValidationIssue]:
        """Heuristic recommendations that were not satisfied."""
        return [i for i in self.issues if i.status is RuleStatus.WARN]

    @property
    def passed_rules(self) -> list[ValidationIssue]:
        """All rules that were satisfied."""
        return [i for i in self.issues if i.status is RuleStatus.PASS]

    def summary(self) -> str:
        """Return a one-line compliance summary."""
        status = "COMPLIANT" if self.is_compliant else "NON-COMPLIANT"
        nf = len(self.verified_failures)
        nw = len(self.warnings)
        return (
            f"{self.file_path.name} [{self.marketplace}] — {status} "
            f"({nf} failure(s), {nw} warning(s))"
        )


# ===========================================================================
# Built-in marketplace rule specifications (read-only reference data)
# ===========================================================================


@dataclass(frozen=True)
class MarketplaceSpec:
    """Specification data for one marketplace (immutable).

    Attributes
    ----------
    name:
        Internal identifier (e.g. ``"adobe_stock"``).
    display_name:
        Human-readable name.
    max_svg_size_mb:
        Maximum allowed SVG file size in megabytes (VERIFIED rule).
    min_preview_width_px:
        Minimum JPG preview width in pixels (VERIFIED rule).
    min_preview_height_px:
        Minimum JPG preview height in pixels (VERIFIED rule).
    recommended_min_paths:
        Minimum path count for a visually interesting vector (HEURISTIC).
    recommended_max_paths:
        Maximum path count before file complexity becomes a concern (HEURISTIC).
    recommended_max_colours:
        Maximum distinct colour count for typical acceptance (HEURISTIC).
    min_stroke_width_px:
        Strokes thinner than this threshold trigger a heuristic warning.
    """

    name: str
    display_name: str
    max_svg_size_mb: float
    min_preview_width_px: int
    min_preview_height_px: int
    recommended_min_paths: int = 3
    recommended_max_paths: int = 8000
    recommended_max_colours: int = 64
    min_stroke_width_px: float = 0.5


#: Built-in marketplace specifications.
MARKETPLACE_SPECS: Final[dict[str, MarketplaceSpec]] = {
    "adobe_stock": MarketplaceSpec(
        name="adobe_stock",
        display_name="Adobe Stock",
        max_svg_size_mb=100.0,
        min_preview_width_px=1600,
        min_preview_height_px=1200,
    ),
    "shutterstock": MarketplaceSpec(
        name="shutterstock",
        display_name="Shutterstock",
        max_svg_size_mb=50.0,
        min_preview_width_px=1500,
        min_preview_height_px=1000,
    ),
    "freepik": MarketplaceSpec(
        name="freepik",
        display_name="Freepik",
        max_svg_size_mb=50.0,
        min_preview_width_px=1000,
        min_preview_height_px=1000,
    ),
}

#: Names of all supported marketplaces.
SUPPORTED_MARKETPLACES: Final[frozenset[str]] = frozenset(MARKETPLACE_SPECS.keys())


# ===========================================================================
# Validator (Sprint 4 implementation target)
# ===========================================================================


class MarketplaceValidator:
    """Validates SVG and JPG output files against marketplace specifications.

    .. warning::

        **Sprint 4 placeholder.**  All public methods raise
        :exc:`NotImplementedError`.  Import and instantiate freely;
        do not call validation methods until Sprint 4.

    Examples of planned usage (Sprint 4+)
    --------------------------------------
    ::

        validator = MarketplaceValidator()

        svg_result = validator.validate_svg(
            svg_path=Path("output/logo.svg"),
            marketplace="adobe_stock",
        )
        if not svg_result.is_compliant:
            raise ValueError(svg_result.summary())

        jpg_result = validator.validate_preview(
            jpg_path=Path("output/logo.jpg"),
            marketplace="adobe_stock",
        )
    """

    def __init__(self) -> None:
        self._specs: dict[str, MarketplaceSpec] = dict(MARKETPLACE_SPECS)

    def validate_svg(
        self,
        svg_path: Path,
        marketplace: str,
    ) -> ValidationResult:
        """Validate *svg_path* against the named marketplace's rules.

        Performs both VERIFIED (hard) and HEURISTIC (advisory) checks.

        Parameters
        ----------
        svg_path:
            Path to the SVG file to validate.
        marketplace:
            Marketplace profile name (must be in :data:`SUPPORTED_MARKETPLACES`
            or a user-created preset name).

        Returns
        -------
        ValidationResult
            Aggregated result with all rule outcomes.

        Raises
        ------
        KeyError
            If *marketplace* is not a known profile.
        """
        spec = self.get_spec(marketplace)
        issues: list[ValidationIssue] = []

        # 1. File existence and size check (VERIFIED)
        if not svg_path.is_file():
            issues.append(
                ValidationIssue(
                    tier=ValidationTier.VERIFIED,
                    rule_id="file_exists",
                    message="SVG file does not exist.",
                    status=RuleStatus.FAIL,
                    marketplace=marketplace,
                )
            )
            return ValidationResult(marketplace=marketplace, file_path=svg_path, issues=issues)

        file_size_mb = svg_path.stat().st_size / (1024 * 1024)
        if file_size_mb > spec.max_svg_size_mb:
            issues.append(
                ValidationIssue(
                    tier=ValidationTier.VERIFIED,
                    rule_id="file_size",
                    message=f"SVG file size ({file_size_mb:.2f} MB) exceeds limit of {spec.max_svg_size_mb:.2f} MB.",
                    status=RuleStatus.FAIL,
                    marketplace=marketplace,
                )
            )
        else:
            issues.append(
                ValidationIssue(
                    tier=ValidationTier.VERIFIED,
                    rule_id="file_size",
                    message="SVG file size is within limits.",
                    status=RuleStatus.PASS,
                    marketplace=marketplace,
                )
            )

        # 2. Well-formed SVG XML & Namespaces & Elements (VERIFIED & HEURISTIC)
        from lxml import etree
        try:
            tree = etree.parse(str(svg_path))
            root = tree.getroot()
            
            issues.append(
                ValidationIssue(
                    tier=ValidationTier.VERIFIED,
                    rule_id="well_formed_xml",
                    message="SVG is well-formed XML.",
                    status=RuleStatus.PASS,
                    marketplace=marketplace,
                )
            )

            # Namespace check (VERIFIED)
            svg_ns = "http://www.w3.org/2000/svg"
            if root.tag != f"{{{svg_ns}}}svg" and root.tag != "svg":
                issues.append(
                    ValidationIssue(
                        tier=ValidationTier.VERIFIED,
                        rule_id="svg_namespace",
                        message=f"Invalid root tag namespace. Expected {{{svg_ns}}}svg, got {root.tag}.",
                        status=RuleStatus.FAIL,
                        marketplace=marketplace,
                    )
                )
            else:
                issues.append(
                    ValidationIssue(
                        tier=ValidationTier.VERIFIED,
                        rule_id="svg_namespace",
                        message="Valid SVG namespace confirmed.",
                        status=RuleStatus.PASS,
                        marketplace=marketplace,
                    )
                )

            # Embedded raster check (VERIFIED)
            images = root.xpath("//svg:image", namespaces={"svg": svg_ns}) or root.xpath("//image")
            raster_found = False
            for img in images:
                href = img.get("href") or img.get("{http://www.w3.org/1999/xlink}href")
                if href:
                    href_str = str(href).lower().strip()
                    if (
                        href_str.startswith("data:image/png")
                        or href_str.startswith("data:image/jpeg")
                        or href_str.startswith("data:image/jpg")
                    ):
                        raster_found = True
                        break
                    ext = Path(href_str).suffix
                    if ext in (".png", ".jpg", ".jpeg", ".tiff", ".bmp", ".gif"):
                        raster_found = True
                        break
            
            if raster_found or images:
                issues.append(
                    ValidationIssue(
                        tier=ValidationTier.VERIFIED,
                        rule_id="no_embedded_rasters",
                        message="Embedded raster images found in SVG.",
                        status=RuleStatus.FAIL,
                        marketplace=marketplace,
                    )
                )
            else:
                issues.append(
                    ValidationIssue(
                        tier=ValidationTier.VERIFIED,
                        rule_id="no_embedded_rasters",
                        message="No embedded raster images found.",
                        status=RuleStatus.PASS,
                        marketplace=marketplace,
                    )
                )

            # --- Heuristics ---

            # Path count (HEURISTIC)
            paths = (
                root.xpath("//svg:path", namespaces={"svg": svg_ns})
                + root.xpath("//svg:rect", namespaces={"svg": svg_ns})
                + root.xpath("//svg:circle", namespaces={"svg": svg_ns})
                + root.xpath("//svg:ellipse", namespaces={"svg": svg_ns})
                + root.xpath("//svg:line", namespaces={"svg": svg_ns})
                + root.xpath("//svg:polyline", namespaces={"svg": svg_ns})
                + root.xpath("//svg:polygon", namespaces={"svg": svg_ns})
            ) or (
                root.xpath("//path")
                + root.xpath("//rect")
                + root.xpath("//circle")
                + root.xpath("//ellipse")
                + root.xpath("//line")
                + root.xpath("//polyline")
                + root.xpath("//polygon")
            )
            path_count = len(paths)
            if path_count < spec.recommended_min_paths:
                issues.append(
                    ValidationIssue(
                        tier=ValidationTier.HEURISTIC,
                        rule_id="path_count",
                        message=f"Path count ({path_count}) is below recommendation of {spec.recommended_min_paths}+ paths.",
                        status=RuleStatus.WARN,
                        marketplace=marketplace,
                    )
                )
            elif path_count > spec.recommended_max_paths:
                issues.append(
                    ValidationIssue(
                        tier=ValidationTier.HEURISTIC,
                        rule_id="path_count",
                        message=f"Path count ({path_count}) exceeds recommended maximum of {spec.recommended_max_paths} paths.",
                        status=RuleStatus.WARN,
                        marketplace=marketplace,
                    )
                )
            else:
                issues.append(
                    ValidationIssue(
                        tier=ValidationTier.HEURISTIC,
                        rule_id="path_count",
                        message=f"Path count ({path_count}) is within recommended range.",
                        status=RuleStatus.PASS,
                        marketplace=marketplace,
                    )
                )

            # Colors count (HEURISTIC)
            colors: set[str] = set()
            for elem in root.xpath("//*"):
                fill = elem.get("fill")
                if fill and fill.lower() not in ("none", "inherit", "transparent"):
                    colors.add(fill.strip().lower())
                stroke = elem.get("stroke")
                if stroke and stroke.lower() not in ("none", "inherit", "transparent"):
                    colors.add(stroke.strip().lower())
            
            color_count = len(colors)
            if color_count > spec.recommended_max_colours:
                issues.append(
                    ValidationIssue(
                        tier=ValidationTier.HEURISTIC,
                        rule_id="colour_count",
                        message=f"Distinct color count ({color_count}) exceeds recommended maximum of {spec.recommended_max_colours} colors.",
                        status=RuleStatus.WARN,
                        marketplace=marketplace,
                    )
                )
            else:
                issues.append(
                    ValidationIssue(
                        tier=ValidationTier.HEURISTIC,
                        rule_id="colour_count",
                        message=f"Color count ({color_count}) is within recommended range.",
                        status=RuleStatus.PASS,
                        marketplace=marketplace,
                    )
                )

            # Thin strokes check (HEURISTIC)
            thin_strokes_found = 0
            for elem in root.xpath("//*[@stroke-width]"):
                sw_str = elem.get("stroke-width")
                try:
                    sw_clean = "".join(c for c in sw_str if c.isdigit() or c in (".", ","))
                    sw_val = float(sw_clean)
                    if sw_val < spec.min_stroke_width_px:
                        thin_strokes_found += 1
                except ValueError:
                    pass
            if thin_strokes_found > 0:
                issues.append(
                    ValidationIssue(
                        tier=ValidationTier.HEURISTIC,
                        rule_id="stroke_width",
                        message=f"Found {thin_strokes_found} stroke(s) thinner than {spec.min_stroke_width_px} px.",
                        status=RuleStatus.WARN,
                        marketplace=marketplace,
                    )
                )
            else:
                issues.append(
                    ValidationIssue(
                        tier=ValidationTier.HEURISTIC,
                        rule_id="stroke_width",
                        message="No thin strokes found.",
                        status=RuleStatus.PASS,
                        marketplace=marketplace,
                    )
                )

            # ViewBox matches artboard (HEURISTIC)
            w_str = root.get("width")
            h_str = root.get("height")
            vb_str = root.get("viewBox")
            
            if w_str and h_str and vb_str:
                try:
                    w_val = float("".join(c for c in w_str if c.isdigit() or c in (".", ",")))
                    h_val = float("".join(c for c in h_str if c.isdigit() or c in (".", ",")))
                    vb_parts = [float(p) for p in vb_str.replace(",", " ").split() if p]
                    if len(vb_parts) == 4:
                        vb_w = vb_parts[2]
                        vb_h = vb_parts[3]
                        if abs(w_val - vb_w) > 1.0 or abs(h_val - vb_h) > 1.0:
                            issues.append(
                                ValidationIssue(
                                    tier=ValidationTier.HEURISTIC,
                                    rule_id="viewbox_artboard",
                                    message=f"Artboard dimensions ({w_val}x{h_val}) do not match viewbox dimensions ({vb_w}x{vb_h}).",
                                    status=RuleStatus.WARN,
                                    marketplace=marketplace,
                                )
                            )
                        else:
                            issues.append(
                                ValidationIssue(
                                    tier=ValidationTier.HEURISTIC,
                                    rule_id="viewbox_artboard",
                                    message="Artboard matches viewbox.",
                                    status=RuleStatus.PASS,
                                    marketplace=marketplace,
                                )
                            )
                    else:
                        issues.append(
                            ValidationIssue(
                                tier=ValidationTier.HEURISTIC,
                                rule_id="viewbox_artboard",
                                message="Invalid viewbox attribute structure.",
                                status=RuleStatus.WARN,
                                marketplace=marketplace,
                            )
                        )
                except ValueError:
                    issues.append(
                        ValidationIssue(
                            tier=ValidationTier.HEURISTIC,
                            rule_id="viewbox_artboard",
                            message="Could not parse dimensions to verify viewbox matching.",
                            status=RuleStatus.WARN,
                            marketplace=marketplace,
                        )
                    )
            else:
                issues.append(
                    ValidationIssue(
                        tier=ValidationTier.HEURISTIC,
                        rule_id="viewbox_artboard",
                        message="Missing width, height, or viewBox attributes to verify alignment.",
                        status=RuleStatus.WARN,
                        marketplace=marketplace,
                    )
                )

        except etree.XMLSyntaxError as exc:
            issues.append(
                ValidationIssue(
                    tier=ValidationTier.VERIFIED,
                    rule_id="well_formed_xml",
                    message=f"Invalid XML syntax: {exc}",
                    status=RuleStatus.FAIL,
                    marketplace=marketplace,
                )
            )

        return ValidationResult(marketplace=marketplace, file_path=svg_path, issues=issues)

    def validate_preview(
        self,
        jpg_path: Path,
        marketplace: str,
    ) -> ValidationResult:
        """Validate a JPG preview file against marketplace pixel-dimension rules.

        Parameters
        ----------
        jpg_path:
            Path to the JPG preview to validate.
        marketplace:
            Marketplace profile name.

        Returns
        -------
        ValidationResult
            Aggregated result with dimension and file-size checks.
        """
        spec = self.get_spec(marketplace)
        issues: list[ValidationIssue] = []

        if not jpg_path.is_file():
            issues.append(
                ValidationIssue(
                    tier=ValidationTier.VERIFIED,
                    rule_id="file_exists",
                    message="Preview file does not exist.",
                    status=RuleStatus.FAIL,
                    marketplace=marketplace,
                )
            )
            return ValidationResult(marketplace=marketplace, file_path=jpg_path, issues=issues)

        from PIL import Image
        try:
            with Image.open(jpg_path) as img:
                w, h = img.size
                
                if img.format != "JPEG":
                    issues.append(
                        ValidationIssue(
                            tier=ValidationTier.VERIFIED,
                            rule_id="preview_format",
                            message=f"Invalid preview format: {img.format}. Expected JPEG.",
                            status=RuleStatus.FAIL,
                            marketplace=marketplace,
                        )
                    )
                else:
                    issues.append(
                        ValidationIssue(
                            tier=ValidationTier.VERIFIED,
                            rule_id="preview_format",
                            message="Valid JPEG format confirmed.",
                            status=RuleStatus.PASS,
                            marketplace=marketplace,
                        )
                    )

                # Width check (VERIFIED)
                if w < spec.min_preview_width_px:
                    issues.append(
                        ValidationIssue(
                            tier=ValidationTier.VERIFIED,
                            rule_id="preview_width",
                            message=f"Preview width ({w} px) is below minimum of {spec.min_preview_width_px} px.",
                            status=RuleStatus.FAIL,
                            marketplace=marketplace,
                        )
                    )
                else:
                    issues.append(
                        ValidationIssue(
                            tier=ValidationTier.VERIFIED,
                            rule_id="preview_width",
                            message="Preview width is compliant.",
                            status=RuleStatus.PASS,
                            marketplace=marketplace,
                        )
                    )

                # Height check (VERIFIED)
                if h < spec.min_preview_height_px:
                    issues.append(
                        ValidationIssue(
                            tier=ValidationTier.VERIFIED,
                            rule_id="preview_height",
                            message=f"Preview height ({h} px) is below minimum of {spec.min_preview_height_px} px.",
                            status=RuleStatus.FAIL,
                            marketplace=marketplace,
                        )
                    )
                else:
                    issues.append(
                        ValidationIssue(
                            tier=ValidationTier.VERIFIED,
                            rule_id="preview_height",
                            message="Preview height is compliant.",
                            status=RuleStatus.PASS,
                            marketplace=marketplace,
                        )
                    )

        except Exception as exc:
            issues.append(
                ValidationIssue(
                    tier=ValidationTier.VERIFIED,
                    rule_id="preview_parse",
                    message=f"Failed to open or parse preview image: {exc}",
                    status=RuleStatus.FAIL,
                    marketplace=marketplace,
                )
            )

        return ValidationResult(marketplace=marketplace, file_path=jpg_path, issues=issues)

    def get_spec(self, marketplace: str) -> MarketplaceSpec:
        """Return the :class:`MarketplaceSpec` for *marketplace*.

        This method is safe to call before Sprint 4.

        Parameters
        ----------
        marketplace:
            Marketplace profile name.

        Returns
        -------
        MarketplaceSpec

        Raises
        ------
        KeyError
            If *marketplace* is not recognised.
        """
        if marketplace not in self._specs:
            available = ", ".join(sorted(self._specs))
            raise KeyError(
                f"Unknown marketplace {marketplace!r}. "
                f"Available: {available}"
            )
        return self._specs[marketplace]

    def supported_marketplaces(self) -> list[str]:
        """Return a sorted list of supported marketplace names.

        Safe to call before Sprint 4.
        """
        return sorted(self._specs)

    def validate(self, svg_path: Path, preset: MarketplacePreset) -> ValidationReport:
        """Validate SVG output against specific marketplace preset."""
        if preset == MarketplacePreset.ADOBE_STOCK:
            return self._validate_adobe_stock(svg_path)
        elif preset == MarketplacePreset.SHUTTERSTOCK:
            return self._validate_shutterstock(svg_path)
        elif preset == MarketplacePreset.FREEPIK:
            return self._validate_freepik(svg_path)
        else:
            raise ValueError(f"Unsupported preset: {preset}")

    def _parse_svg_dimension(self, value: str) -> float:
        if not value:
            return 0.0
        value = value.strip().lower()
        
        # Extract numeric part
        num_str = ""
        unit_str = ""
        for char in value:
            if char.isdigit() or char in (".", "-"):
                num_str += char
            elif char.isalpha() or char == "%":
                unit_str += char
                
        if not num_str:
            return 0.0
            
        try:
            val = float(num_str)
        except ValueError:
            return 0.0
        
        if unit_str == "mm":
            return val * (96.0 / 25.4)
        elif unit_str == "cm":
            return val * (96.0 / 2.54)
        elif unit_str == "in":
            return val * 96.0
        elif unit_str == "pt":
            return val * (96.0 / 72.0)
        elif unit_str == "pc":
            return val * 16.0
            
        return val

    def _get_svg_dimensions(self, svg_path: Path) -> tuple[float, float]:
        try:
            tree = ET.parse(svg_path)
            root = tree.getroot()
            width = root.get("width")
            height = root.get("height")
            viewBox = root.get("viewBox")
            
            w_val = 0.0
            h_val = 0.0
            
            if width and "%" not in width:
                w_val = self._parse_svg_dimension(width)
            if height and "%" not in height:
                h_val = self._parse_svg_dimension(height)
                
            if (w_val == 0.0 or h_val == 0.0) and viewBox:
                parts = [float(p) for p in viewBox.replace(",", " ").split() if p]
                if len(parts) == 4:
                    if w_val == 0.0:
                        w_val = parts[2]
                    if h_val == 0.0:
                        h_val = parts[3]
                        
            return w_val, h_val
        except Exception:
            return 0.0, 0.0

    def _validate_adobe_stock(self, svg_path: Path) -> ValidationReport:
        errors: list[ValidationError] = []
        warnings: list[ValidationWarning] = []
        
        # 1. File exists
        if not svg_path.exists():
            errors.append(ValidationError(code="FILE_NOT_FOUND", message="SVG file not found"))
            return ValidationReport(preset="adobe_stock", passed=False, errors=errors, warnings=warnings)
            
        # 2. File size
        size = svg_path.stat().st_size
        if size > 100 * 1024 * 1024:
            errors.append(ValidationError(code="FILE_TOO_LARGE", message="File size exceeds 100MB"))
            
        # 3. Dimensions
        w_val, h_val = self._get_svg_dimensions(svg_path)
        if w_val * h_val < 15_000_000:
            errors.append(ValidationError(code="BELOW_MIN_RESOLUTION", message="Resolution is below 15MP"))
            
        # 4. Color Mode
        try:
            content = svg_path.read_text(errors="ignore")
            if "device-cmyk" in content.lower() or "cmyk" in content.lower():
                errors.append(ValidationError(code="INVALID_COLOR_MODE", message="Color mode must be RGB"))
        except Exception as e:
            errors.append(ValidationError(code="READ_ERROR", message=f"Failed to check color mode: {e}"))
            
        passed = len(errors) == 0
        return ValidationReport(preset="adobe_stock", passed=passed, errors=errors, warnings=warnings)

    def _validate_shutterstock(self, svg_path: Path) -> ValidationReport:
        errors: list[ValidationError] = []
        warnings: list[ValidationWarning] = []
        
        # 1. File exists
        if not svg_path.exists():
            errors.append(ValidationError(code="FILE_NOT_FOUND", message="SVG file not found"))
            return ValidationReport(preset="shutterstock", passed=False, errors=errors, warnings=warnings)
            
        # 2. File size
        size = svg_path.stat().st_size
        if size > 50 * 1024 * 1024:
            errors.append(ValidationError(code="FILE_TOO_LARGE", message="File size exceeds 50MB"))
            
        # 3. Dimensions
        w_val, h_val = self._get_svg_dimensions(svg_path)
        if w_val * h_val < 4_000_000:
            errors.append(ValidationError(code="BELOW_MIN_RESOLUTION", message="Resolution is below 4MP"))
            
        # 4. IPTC warning
        try:
            content = svg_path.read_text(errors="ignore")
            if "<metadata>" not in content.lower() and "<rdf:rdf>" not in content.lower() and "iptc" not in content.lower():
                warnings.append(ValidationWarning(code="MISSING_IPTC", message="IPTC metadata is missing"))
        except Exception:
            pass
            
        passed = len(errors) == 0
        return ValidationReport(preset="shutterstock", passed=passed, errors=errors, warnings=warnings)

    def _validate_freepik(self, svg_path: Path) -> ValidationReport:
        errors: list[ValidationError] = []
        warnings: list[ValidationWarning] = []
        
        # 1. File exists
        if not svg_path.exists():
            errors.append(ValidationError(code="FILE_NOT_FOUND", message="SVG file not found"))
            return ValidationReport(preset="freepik", passed=False, errors=errors, warnings=warnings)
            
        # 2. File size
        size = svg_path.stat().st_size
        if size > 25 * 1024 * 1024:
            errors.append(ValidationError(code="FILE_TOO_LARGE", message="File size exceeds 25MB"))
            
        # 3. Format
        if svg_path.suffix.lower() not in (".svg", ".eps"):
            errors.append(ValidationError(code="INVALID_FORMAT", message="Format not accepted"))
            
        passed = len(errors) == 0
        return ValidationReport(preset="freepik", passed=passed, errors=errors, warnings=warnings)


@dataclass
class ValidationError:
    """Represents a critical compliance failure."""
    code: str
    message: str
    fatal: bool = True


@dataclass
class ValidationWarning:
    """Represents a non-blocking compliance recommendation."""
    code: str
    message: str


@dataclass
class ValidationReport:
    """Report summarizing the compliance state against a preset."""
    preset: str
    passed: bool
    errors: list[ValidationError]
    warnings: list[ValidationWarning]

    def summary(self) -> str:
        status = "PASSED" if self.passed else "FAILED"
        err_msg = f"{len(self.errors)} error(s)"
        warn_msg = f"{len(self.warnings)} warning(s)"
        return f"Marketplace Validation [{self.preset}] — {status} ({err_msg}, {warn_msg})"


class MarketplacePreset(Enum):
    """Presets for target marketplaces."""
    ADOBE_STOCK = "adobe_stock"
    SHUTTERSTOCK = "shutterstock"
    FREEPIK = "freepik"

