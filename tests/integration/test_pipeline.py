"""
tests.integration.test_pipeline
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Integration tests for the Vector Tracer Pro pipeline.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from vector_tracer_pro.core.marketplace_validator import MarketplacePreset
from vector_tracer_pro.core.pipeline import Pipeline, PipelineResult
from vector_tracer_pro.core.trace_strategy import (
    FallbackTracingStrategy,
    InkscapeTracingStrategy,
    PotraceTracingStrategy,
    VTracerTracingStrategy,
)


@pytest.mark.integration
class TestPipelineIntegration:
    @patch.object(PotraceTracingStrategy, "execute")
    @patch.object(InkscapeTracingStrategy, "execute")
    @patch.object(VTracerTracingStrategy, "execute")
    @patch.object(FallbackTracingStrategy, "execute")
    def test_pipeline_integration_end_to_end(
        self,
        mock_fallback,
        mock_vtracer,
        mock_inkscape,
        mock_potrace,
        tmp_path,
    ) -> None:
        # Mock strategy execute to write a compliant SVG file so validation passes
        def mock_execute(input_path, output_svg_path, params=None):
            output_svg_path.write_text(
                '<svg width="4000" height="3000"><metadata>IPTC</metadata></svg>'
            )

        mock_potrace.side_effect = mock_execute
        mock_inkscape.side_effect = mock_execute
        mock_vtracer.side_effect = mock_execute
        mock_fallback.side_effect = mock_execute

        # Setup paths
        fixture_dir = Path(__file__).parent.parent / "fixtures" / "images"
        input_image = fixture_dir / "valid_rgb.jpg"
        assert input_image.exists(), f"Fixture image not found at {input_image}"

        output_dir = tmp_path / "output_svgs"
        output_dir.mkdir()

        # Initialize pipeline
        pipeline = Pipeline()

        # Progress tracking
        progress_calls = []

        def on_progress(step: str, pct: int) -> None:
            progress_calls.append((step, pct))

        # Run pipeline
        result = pipeline.run(
            input_path=input_image,
            output_dir=output_dir,
            preset=MarketplacePreset.SHUTTERSTOCK,
            on_progress=on_progress,
        )

        # 1. Verify output file is generated
        expected_svg = output_dir / "valid_rgb.svg"
        assert expected_svg.exists()
        assert (
            expected_svg.read_text()
            == '<svg width="4000" height="3000"><metadata>IPTC</metadata></svg>'
        )

        # 2. Verify PipelineResult contains correct values
        assert isinstance(result, PipelineResult)
        assert result.svg_path == expected_svg
        assert result.validation_report.passed is True
        assert len(result.validation_report.errors) == 0
        assert len(result.validation_report.warnings) == 0

        # 3. Verify progress percentages were reported sequentially
        expected_steps = [
            "loading",
            "classifying",
            "preprocessing",
            "bitmapping",
            "tracing",
            "validating",
            "done",
        ]
        actual_steps = [call[0] for call in progress_calls]
        assert actual_steps == expected_steps
        assert [call[1] for call in progress_calls] == [10, 20, 40, 55, 80, 95, 100]
