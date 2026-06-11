"""
Vector Tracer Pro

Production-ready desktop application for converting raster images
to stock-ready SVG files and JPG previews.
"""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__: str = version("vector-tracer-pro")
except PackageNotFoundError:
    # Package is not installed (e.g., running from source without pip install)
    __version__ = "0.0.0-dev"

__author__: str = "Vector Tracer Pro Team"
__license__: str = "MIT"

__all__: list[str] = ["__version__", "__author__", "__license__"]
