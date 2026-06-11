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
        NotImplementedError
            **Sprint 4 target** — not yet implemented.
        KeyError
            If *marketplace* is not a known profile.
        """
        raise NotImplementedError(
            "MarketplaceValidator.validate_svg() is a Sprint 4 deliverable."
        )

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

        Raises
        ------
        NotImplementedError
            **Sprint 4 target** — not yet implemented.
        """
        raise NotImplementedError(
            "MarketplaceValidator.validate_preview() is a Sprint 4 deliverable."
        )

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
