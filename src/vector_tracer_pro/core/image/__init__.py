"""
vector_tracer_pro.core.image
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Image ingestion, classification, preprocessing, and bitmapping package.
"""

from vector_tracer_pro.core.image.bitmapper import BitmapFile, BitmapFormat, Bitmapper
from vector_tracer_pro.core.image.classifier import ImageCategory, ImageClassifier
from vector_tracer_pro.core.image.loader import ImageData, ImageLoader, ImageMetadata
from vector_tracer_pro.core.image.preprocessor import PreprocessConfig, Preprocessor, ProcessedImage

__all__ = [
    "BitmapFile",
    "BitmapFormat",
    "Bitmapper",
    "ImageCategory",
    "ImageClassifier",
    "ImageData",
    "ImageLoader",
    "ImageMetadata",
    "PreprocessConfig",
    "Preprocessor",
    "ProcessedImage",
]
