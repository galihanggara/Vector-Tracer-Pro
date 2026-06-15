"""
vector_tracer_pro.core.pipeline
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Orchestrates the vectorisation pipeline from input raster file to validated output SVG.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from vector_tracer_pro.core.classifier import ClassificationResult, ImageType
from vector_tracer_pro.core.image.bitmapper import BitmapFormat, Bitmapper
from vector_tracer_pro.core.image.classifier import ImageCategory, ImageClassifier
from vector_tracer_pro.core.image.loader import ImageLoader
from vector_tracer_pro.core.image.preprocessor import PreprocessConfig, Preprocessor
from vector_tracer_pro.core.marketplace_validator import (
    MarketplacePreset,
    MarketplaceValidator,
    ValidationReport,
)
from vector_tracer_pro.core.trace_strategy import TraceParams, TraceStrategySelector


@dataclass
class PipelineResult:
    """The result of a complete vectorisation pipeline run."""

    svg_path: Path
    category: ImageCategory
    engine_used: str
    validation_report: ValidationReport
    applied_steps: list[str]


_CATEGORY_TO_IMAGE_TYPE = {
    ImageCategory.LINE_ART: ImageType.MONOCHROME,
    ImageCategory.FLAT_VECTOR: ImageType.COLOUR_SIMPLE,
    ImageCategory.PHOTO: ImageType.COLOUR_COMPLEX,
    ImageCategory.LOGO: ImageType.COLOUR_SIMPLE,
}


class Pipeline:
    """Orchestrates image loading, classification, preprocessing, bitmapping,
    tracing, and validation.
    """

    def run(
        self,
        input_path: Path,
        output_dir: Path,
        preset: MarketplacePreset,
        preprocess_config: PreprocessConfig | None = None,
        trace_params: TraceParams | None = None,
        on_progress: Callable[[str, int], None] | None = None,
    ) -> PipelineResult:
        """Run the vectorisation pipeline.

        Parameters
        ----------
        input_path:
            Path to the input raster image file.
        output_dir:
            Directory where the output SVG will be written.
        preset:
            The target marketplace validation profile.
        preprocess_config:
            Custom configuration for preprocessing steps.
        trace_params:
            Custom configuration parameters for tracing engines.
        on_progress:
            Callback invoked at each step with name and percentage.

        Returns
        -------
        PipelineResult
            Summary of the pipeline results.
        """

        def emit(step: str, pct: int) -> None:
            if on_progress:
                on_progress(step, pct)

        # 1. Load image
        emit("loading", 10)
        loader = ImageLoader()
        image_data = loader.load(input_path)

        # 2. Classify
        emit("classifying", 20)
        classifier = ImageClassifier()
        category = classifier.classify(image_data)

        # 3. Preprocess
        emit("preprocessing", 40)
        preprocessor = Preprocessor()
        processed = preprocessor.process(image_data, category, preprocess_config)

        # 4. Bitmap export
        emit("bitmapping", 55)
        fmt = BitmapFormat.PBM if processed.data.ndim == 2 else BitmapFormat.PNG
        bitmapper = Bitmapper()

        with bitmapper.write(processed, fmt) as bmp_file:
            # 5. Trace
            emit("tracing", 80)

            # Map category to ImageType
            image_type = _CATEGORY_TO_IMAGE_TYPE[category]
            class_res = ClassificationResult(
                image_type=image_type,
                unique_colour_count=0,
                average_saturation=0.0,
                confidence=1.0,
                recommended_engine=image_type.recommended_engine,
            )

            # Check vtracer availability dynamically
            from vector_tracer_pro.core.dependency_checker import DependencyChecker

            dep_checker = DependencyChecker()
            report = dep_checker.check_all()
            vtracer_available = report.vtracer_check.passed if report.vtracer_check else False

            selector = TraceStrategySelector(vtracer_available=vtracer_available)
            strategy = selector.select(class_res)

            output_svg_path = output_dir / f"{input_path.stem}.svg"
            strategy.execute(bmp_file.path, output_svg_path, trace_params)

        # 6. Validate
        emit("validating", 95)
        validator = MarketplaceValidator()
        validation_report = validator.validate(output_svg_path, preset)

        # 7. Done
        emit("done", 100)

        return PipelineResult(
            svg_path=output_svg_path,
            category=category,
            engine_used=strategy.primary_engine.value,
            validation_report=validation_report,
            applied_steps=processed.applied_steps,
        )
