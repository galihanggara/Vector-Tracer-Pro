"""
vector_tracer_pro.core.image
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Image ingestion, classification, preprocessing, and bitmapping package.
"""

from vector_tracer_pro.core.image.loader import ImageData, ImageLoader, ImageMetadata
from vector_tracer_pro.core.image.classifier import ImageCategory, ImageClassifier
from vector_tracer_pro.core.image.preprocessor import PreprocessConfig, ProcessedImage, Preprocessor
from vector_tracer_pro.core.image.bitmapper import BitmapFormat, BitmapFile, Bitmapper

__all__ = [
    "ImageMetadata",
    "ImageData",
    "ImageLoader",
    "ImageCategory",
    "ImageClassifier",
    "PreprocessConfig",
    "ProcessedImage",
    "Preprocessor",
    "BitmapFormat",
    "BitmapFile",
    "Bitmapper",
]
