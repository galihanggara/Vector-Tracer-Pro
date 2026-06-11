"""
tests.unit.core.test_marketplace_validator
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Unit tests for :mod:`vector_tracer_pro.core.marketplace_validator`.
"""

from __future__ import annotations

from pathlib import Path
import pytest
from PIL import Image

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

    def test_validate_svg_missing_file(self) -> None:
        validator = MarketplaceValidator()
        result = validator.validate_svg(Path("nonexistent.svg"), "adobe_stock")
        assert result.is_compliant is False
        assert any(i.rule_id == "file_exists" and i.status == RuleStatus.FAIL for i in result.issues)

    def test_validate_svg_invalid_xml(self, tmp_path: Path) -> None:
        p = tmp_path / "bad.svg"
        p.write_text("invalid xml syntax")
        validator = MarketplaceValidator()
        result = validator.validate_svg(p, "adobe_stock")
        assert result.is_compliant is False
        assert any(i.rule_id == "well_formed_xml" and i.status == RuleStatus.FAIL for i in result.issues)

    def test_validate_svg_compliant(self, tmp_path: Path) -> None:
        p = tmp_path / "good.svg"
        p.write_text(
            '<svg xmlns="http://www.w3.org/2000/svg" width="1600" height="1200" viewBox="0 0 1600 1200">'
            '  <path d="M 0 0 L 10 10 Z" fill="#ff0000" stroke="#000000" stroke-width="1.0" />'
            '  <path d="M 10 10 L 20 20 Z" fill="#00ff00" />'
            '  <path d="M 20 20 L 30 30 Z" fill="#0000ff" />'
            '</svg>'
        )
        validator = MarketplaceValidator()
        result = validator.validate_svg(p, "adobe_stock")
        assert result.is_compliant is True
        # Verify warnings/heuristics are ok (3 paths is recommended_min_paths, so no path_count warning)
        assert len(result.verified_failures) == 0

    def test_validate_svg_embedded_raster(self, tmp_path: Path) -> None:
        p = tmp_path / "embedded.svg"
        p.write_text(
            '<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100">'
            '  <image href="data:image/png;base64,iVBORw0KGgoAAA" width="10" height="10" />'
            '</svg>'
        )
        validator = MarketplaceValidator()
        result = validator.validate_svg(p, "adobe_stock")
        assert result.is_compliant is False
        assert any(i.rule_id == "no_embedded_rasters" and i.status == RuleStatus.FAIL for i in result.issues)

    def test_validate_svg_embedded_raster_url(self, tmp_path: Path) -> None:
        p = tmp_path / "embedded_url.svg"
        p.write_text(
            '<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100">'
            '  <image href="photo.png" width="10" height="10" />'
            '</svg>'
        )
        validator = MarketplaceValidator()
        result = validator.validate_svg(p, "adobe_stock")
        assert result.is_compliant is False
        assert any(i.rule_id == "no_embedded_rasters" and i.status == RuleStatus.FAIL for i in result.issues)

    def test_validate_svg_too_few_paths(self, tmp_path: Path) -> None:
        p = tmp_path / "few_paths.svg"
        p.write_text(
            '<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100">'
            '  <path d="M 0 0 Z" fill="none" />'
            '</svg>'
        )
        validator = MarketplaceValidator()
        result = validator.validate_svg(p, "adobe_stock")
        assert result.is_compliant is True  # still compliant because it is heuristic warning
        assert any(i.rule_id == "path_count" and i.status == RuleStatus.WARN for i in result.issues)

    def test_validate_svg_thin_strokes(self, tmp_path: Path) -> None:
        p = tmp_path / "thin_strokes.svg"
        p.write_text(
            '<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100">'
            '  <line x1="0" y1="0" x2="10" y2="10" stroke="#000" stroke-width="0.2px" />'
            '</svg>'
        )
        validator = MarketplaceValidator()
        result = validator.validate_svg(p, "adobe_stock")
        assert result.is_compliant is True
        assert any(i.rule_id == "stroke_width" and i.status == RuleStatus.WARN for i in result.issues)

    def test_validate_preview_missing_file(self) -> None:
        validator = MarketplaceValidator()
        result = validator.validate_preview(Path("nonexistent.jpg"), "adobe_stock")
        assert result.is_compliant is False
        assert any(i.rule_id == "file_exists" and i.status == RuleStatus.FAIL for i in result.issues)

    def test_validate_preview_non_jpeg(self, tmp_path: Path) -> None:
        p = tmp_path / "preview.png"
        img = Image.new("RGBA", (1600, 1200), color=(255, 255, 255, 255))
        img.save(p, format="PNG")
        
        validator = MarketplaceValidator()
        result = validator.validate_preview(p, "adobe_stock")
        assert result.is_compliant is False
        assert any(i.rule_id == "preview_format" and i.status == RuleStatus.FAIL for i in result.issues)

    def test_validate_preview_compliant(self, tmp_path: Path) -> None:
        p = tmp_path / "preview.jpg"
        img = Image.new("RGB", (1600, 1200), color=(128, 128, 128))
        img.save(p, format="JPEG")
        
        validator = MarketplaceValidator()
        result = validator.validate_preview(p, "adobe_stock")
        assert result.is_compliant is True
        assert len(result.verified_failures) == 0

    def test_validate_preview_too_small(self, tmp_path: Path) -> None:
        p = tmp_path / "small.jpg"
        img = Image.new("RGB", (800, 600), color=(128, 128, 128))
        img.save(p, format="JPEG")
        
        validator = MarketplaceValidator()
        result = validator.validate_preview(p, "adobe_stock")
        assert result.is_compliant is False
        assert any(i.rule_id == "preview_width" and i.status == RuleStatus.FAIL for i in result.issues)
        assert any(i.rule_id == "preview_height" and i.status == RuleStatus.FAIL for i in result.issues)
