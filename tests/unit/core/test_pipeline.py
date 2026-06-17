"""
tests.unit.core.test_pipeline
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Unit tests for :mod:`vector_tracer_pro.core.pipeline`.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from vector_tracer_pro.core.image.bitmapper import BitmapFile, BitmapFormat
from vector_tracer_pro.core.image.classifier import ImageCategory
from vector_tracer_pro.core.image.loader import ImageData, ImageMetadata
from vector_tracer_pro.core.image.preprocessor import PreprocessConfig, ProcessedImage
from vector_tracer_pro.core.marketplace_validator import MarketplacePreset, ValidationReport
from vector_tracer_pro.core.pipeline import Pipeline, PipelineResult


@pytest.mark.unit
class TestPipeline:
    @patch("vector_tracer_pro.core.pipeline.MarketplaceValidator")
    @patch("vector_tracer_pro.core.pipeline.TraceStrategySelector")
    @patch("vector_tracer_pro.core.pipeline.Bitmapper")
    @patch("vector_tracer_pro.core.pipeline.Preprocessor")
    @patch("vector_tracer_pro.core.pipeline.ImageClassifier")
    @patch("vector_tracer_pro.core.pipeline.ImageLoader")
    def test_pipeline_full_flow(
        self,
        mock_loader_cls,
        mock_classifier_cls,
        mock_preprocessor_cls,
        mock_bitmapper_cls,
        mock_selector_cls,
        mock_validator_cls,
        tmp_path,
    ) -> None:
        # 1. Setup ImageLoader mock
        mock_loader = mock_loader_cls.return_value
        mock_metadata = ImageMetadata(
            width=100,
            height=100,
            dpi=(72.0, 72.0),
            bit_depth=8,
            original_mode="RGB",
        )
        fake_data = np.zeros((100, 100, 3), dtype=np.float32)
        mock_loader.load.return_value = ImageData(data=fake_data, metadata=mock_metadata)

        # 2. Setup ImageClassifier mock
        mock_classifier = mock_classifier_cls.return_value
        mock_classifier.classify.return_value = ImageCategory.FLAT_VECTOR

        # 3. Setup Preprocessor mock
        mock_preprocessor = mock_preprocessor_cls.return_value
        mock_processed = ProcessedImage(
            data=fake_data,
            metadata=mock_metadata,
            category=ImageCategory.FLAT_VECTOR,
            config=PreprocessConfig(),
            applied_steps=["resize", "quantize"],
        )
        mock_preprocessor.process.return_value = mock_processed

        # 4. Setup Bitmapper mock
        mock_bitmapper = mock_bitmapper_cls.return_value
        mock_bmp_file = BitmapFile(
            path=tmp_path / "temp.png",
            format=BitmapFormat.PNG,
            source_category=ImageCategory.FLAT_VECTOR,
        )

        # Mock context manager write()
        import contextlib

        @contextlib.contextmanager
        def mock_write(processed, fmt):
            yield mock_bmp_file

        mock_bitmapper.write.side_effect = mock_write

        # 5. Setup TraceStrategySelector & Strategy mock
        mock_selector = mock_selector_cls.return_value
        mock_strategy = MagicMock()
        from vector_tracer_pro.core.trace_strategy import TraceEngine

        mock_strategy.primary_engine = TraceEngine.INKSCAPE
        mock_selector.select.return_value = mock_strategy

        # 6. Setup MarketplaceValidator mock
        mock_validator = mock_validator_cls.return_value
        mock_report = ValidationReport(
            preset="adobe_stock",
            passed=True,
            errors=[],
            warnings=[],
        )
        mock_validator.validate.return_value = mock_report

        # 7. Setup progress tracking callback
        progress_calls = []

        def on_progress(step: str, pct: int) -> None:
            progress_calls.append((step, pct))

        # 8. Execute pipeline
        pipeline = Pipeline()
        input_file = tmp_path / "input.png"
        input_file.write_text("fake png")
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        result = pipeline.run(
            input_path=input_file,
            output_dir=output_dir,
            preset=MarketplacePreset.ADOBE_STOCK,
            on_progress=on_progress,
        )

        # 9. Asserts on progress callback
        expected_progress = [
            ("loading", 10),
            ("classifying", 20),
            ("preprocessing", 40),
            ("bitmapping", 55),
            ("tracing", 80),
            ("validating", 95),
            ("done", 100),
        ]
        assert progress_calls == expected_progress

        # 10. Asserts on sub-system calls
        mock_loader.load.assert_called_once_with(input_file)
        mock_classifier.classify.assert_called_once()
        mock_preprocessor.process.assert_called_once()
        mock_bitmapper.write.assert_called_once()
        mock_selector.select.assert_called_once()

        expected_svg_path = output_dir / "input.svg"
        mock_strategy.execute.assert_called_once_with(mock_bmp_file.path, expected_svg_path, None)
        mock_validator.validate.assert_called_once_with(
            expected_svg_path, MarketplacePreset.ADOBE_STOCK
        )

        # 11. Asserts on PipelineResult
        assert isinstance(result, PipelineResult)
        assert result.svg_path == expected_svg_path
        assert result.category == ImageCategory.FLAT_VECTOR
        assert result.engine_used == "inkscape"
        assert result.validation_report == mock_report
        assert result.applied_steps == ["resize", "quantize"]

    @patch("vector_tracer_pro.core.pipeline.MarketplaceValidator")
    @patch("vector_tracer_pro.core.pipeline.Bitmapper")
    @patch("vector_tracer_pro.core.pipeline.Preprocessor")
    @patch("vector_tracer_pro.core.pipeline.ImageClassifier")
    @patch("vector_tracer_pro.core.pipeline.ImageLoader")
    def test_pipeline_uses_vtracer_first_for_photo(
        self,
        mock_loader_cls,
        mock_classifier_cls,
        mock_preprocessor_cls,
        mock_bitmapper_cls,
        mock_validator_cls,
        tmp_path,
    ) -> None:
        mock_loader = mock_loader_cls.return_value
        mock_metadata = ImageMetadata(
            width=100,
            height=100,
            dpi=(72.0, 72.0),
            bit_depth=8,
            original_mode="RGB",
        )
        fake_data = np.zeros((100, 100, 3), dtype=np.float32)
        mock_loader.load.return_value = ImageData(data=fake_data, metadata=mock_metadata)

        # Mock classifier to return PHOTO
        mock_classifier = mock_classifier_cls.return_value
        mock_classifier.classify.return_value = ImageCategory.PHOTO

        mock_preprocessor = mock_preprocessor_cls.return_value
        mock_processed = ProcessedImage(
            data=fake_data,
            metadata=mock_metadata,
            category=ImageCategory.PHOTO,
            config=PreprocessConfig(),
            applied_steps=[],
        )
        mock_preprocessor.process.return_value = mock_processed

        mock_bitmapper = mock_bitmapper_cls.return_value
        mock_bmp_file = BitmapFile(
            path=tmp_path / "temp.png",
            format=BitmapFormat.PNG,
            source_category=ImageCategory.PHOTO,
        )

        import contextlib
        @contextlib.contextmanager
        def mock_write(processed, fmt):
            yield mock_bmp_file

        mock_bitmapper.write.side_effect = mock_write

        mock_validator = mock_validator_cls.return_value
        mock_validator.validate.return_value = ValidationReport(
            preset="adobe_stock", passed=True, errors=[], warnings=[]
        )

        # Patch VTracerTracingStrategy and InkscapeTracingStrategy to see which runs first
        vtracer_path = "vector_tracer_pro.core.trace_strategy.VTracerTracingStrategy.execute"
        inkscape_path = "vector_tracer_pro.core.trace_strategy.InkscapeTracingStrategy.execute"
        with patch(vtracer_path) as mock_vtracer_exec, \
             patch(inkscape_path) as mock_inkscape_exec:

            pipeline = Pipeline()
            input_file = tmp_path / "input.png"
            input_file.write_text("fake png")

            # We mock dependency checks to make sure vtracer is available
            dep_path = "vector_tracer_pro.core.dependency_checker.DependencyChecker.check_all"
            with patch(dep_path) as mock_dep:
                mock_report = MagicMock()
                mock_report.vtracer_check.passed = True
                mock_dep.return_value = mock_report

                pipeline.run(
                    input_path=input_file,
                    output_dir=tmp_path,
                    preset=MarketplacePreset.ADOBE_STOCK,
                )

            # Assert VTracer was executed first
            mock_vtracer_exec.assert_called_once()
            # Inkscape was not called because VTracer execution succeeded
            mock_inkscape_exec.assert_not_called()
