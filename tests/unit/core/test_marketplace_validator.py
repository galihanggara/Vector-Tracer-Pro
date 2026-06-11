"""
tests.unit.core.test_marketplace_validator
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Unit tests for :mod:`vector_tracer_pro.core.marketplace_validator`.
"""

from __future__ import annotations

from pathlib import Path
import pytest

from vector_tracer_pro.core.marketplace_validator import (
    MARKETPLACE_SPECS,
    SUPPORTED_MARKETPLACES,
    MarketplaceValidator,
    RuleStatus,
    ValidationIssue,
    ValidationResult,
    ValidationTier,
)


@pytest.mark.unit
class TestValidationEnums:
    def test_enums(self) -> None:
        assert ValidationTier.VERIFIED.value == "verified"
        assert ValidationTier.HEURISTIC.value == "heuristic"
        assert RuleStatus.PASS.name == "PASS"
        assert RuleStatus.FAIL.name == "FAIL"
        assert RuleStatus.WARN.name == "WARN"


@pytest.mark.unit
class TestValidationIssue:
    def test_properties(self) -> None:
        i1 = ValidationIssue(
            tier=ValidationTier.VERIFIED,
            rule_id="test_rule",
            message="verified failure",
            status=RuleStatus.FAIL,
        )
        assert i1.is_failure is True
        assert i1.is_warning is False

        i2 = ValidationIssue(
            tier=ValidationTier.HEURISTIC,
            rule_id="test_heuristic",
            message="heuristic warning",
            status=RuleStatus.WARN,
        )
        assert i2.is_failure is False
        assert i2.is_warning is True


@pytest.mark.unit
class TestValidationResult:
    def test_compliance(self) -> None:
        r = ValidationResult(
            marketplace="adobe_stock",
            file_path=Path("output.svg"),
            issues=[
                ValidationIssue(
                    tier=ValidationTier.VERIFIED,
                    rule_id="well_formed",
                    message="Valid XML",
                    status=RuleStatus.PASS,
                ),
                ValidationIssue(
                    tier=ValidationTier.HEURISTIC,
                    rule_id="stroke_width",
                    message="Thin stroke",
                    status=RuleStatus.WARN,
                ),
            ],
        )
        assert r.is_compliant is True
        assert len(r.warnings) == 1
        assert len(r.verified_failures) == 0
        assert len(r.passed_rules) == 1

        r_failed = ValidationResult(
            marketplace="adobe_stock",
            file_path=Path("output.svg"),
            issues=[
                ValidationIssue(
                    tier=ValidationTier.VERIFIED,
                    rule_id="no_embedded_rasters",
                    message="Has embedded image",
                    status=RuleStatus.FAIL,
                ),
            ],
        )
        assert r_failed.is_compliant is False
        assert len(r_failed.verified_failures) == 1

    def test_summary(self) -> None:
        r = ValidationResult(
            marketplace="adobe_stock",
            file_path=Path("output.svg"),
            issues=[
                ValidationIssue(
                    tier=ValidationTier.VERIFIED,
                    rule_id="no_embedded_rasters",
                    message="Has embedded image",
                    status=RuleStatus.FAIL,
                ),
                ValidationIssue(
                    tier=ValidationTier.HEURISTIC,
                    rule_id="stroke_width",
                    message="Thin stroke",
                    status=RuleStatus.WARN,
                ),
            ],
        )
        s = r.summary()
        assert "output.svg" in s
        assert "adobe_stock" in s
        assert "NON-COMPLIANT" in s
        assert "1 failure(s)" in s
        assert "1 warning(s)" in s


@pytest.mark.unit
class TestMarketplaceValidator:
    def test_supported_marketplaces(self) -> None:
        validator = MarketplaceValidator()
        supported = validator.supported_marketplaces()
        assert "adobe_stock" in supported
        assert "shutterstock" in supported
        assert "freepik" in supported
        assert len(supported) == 3

    def test_get_spec_valid(self) -> None:
        validator = MarketplaceValidator()
        spec = validator.get_spec("adobe_stock")
        assert spec.name == "adobe_stock"
        assert spec.max_svg_size_mb == 100.0
        assert spec.min_preview_width_px == 1600
        assert spec.min_preview_height_px == 1200

    def test_get_spec_invalid_raises_key_error(self) -> None:
        validator = MarketplaceValidator()
        with pytest.raises(KeyError) as exc_info:
            validator.get_spec("invalid_marketplace")
        assert "Unknown marketplace" in str(exc_info.value)

    def test_validate_svg_raises_not_implemented(self) -> None:
        validator = MarketplaceValidator()
        with pytest.raises(NotImplementedError) as exc_info:
            validator.validate_svg(Path("output.svg"), "adobe_stock")
        assert "validate_svg() is a Sprint 4 deliverable" in str(exc_info.value)

    def test_validate_preview_raises_not_implemented(self) -> None:
        validator = MarketplaceValidator()
        with pytest.raises(NotImplementedError) as exc_info:
            validator.validate_preview(Path("output.jpg"), "adobe_stock")
        assert "validate_preview() is a Sprint 4 deliverable" in str(exc_info.value)
