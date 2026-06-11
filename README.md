# Vector Tracer Pro

> Production-ready desktop application for converting JPG/PNG raster images into stock-ready SVG files and JPG previews.

## Target Marketplaces

- [Adobe Stock](https://stock.adobe.com/contributor)
- [Shutterstock](https://www.shutterstock.com/contribute)
- [Freepik](https://contributor.freepik.com/)

## Features

- **Multi-colour & monochrome tracing** — automatically selects the best engine per image
- **Dual trace engines** — Potrace (monochrome/greyscale) + Inkscape (multi-colour)
- **Marketplace presets** — built-in validated settings for Adobe Stock, Shutterstock, and Freepik
- **Custom presets** — create, edit, and export your own marketplace profiles
- **Batch processing** — drag-and-drop queue with progress tracking
- **SVG validation** — verified requirements (hard rules) + heuristic recommendations
- **JPG preview export** — pixel-dimension based, marketplace-spec compliant
- **Non-blocking UI** — all tracing runs in background workers

## Requirements

| Dependency | Version | Notes |
|---|---|---|
| Python | ≥ 3.12 | |
| PySide6 | ≥ 6.7.0 | Bundled with installer |
| [Potrace](http://potrace.sourceforge.net/) | ≥ 1.16 | Must be on PATH |
| [Inkscape](https://inkscape.org/) | ≥ 1.0 | Must be installed separately |

## Installation (Development)

```powershell
# 1. Clone the repository
git clone https://github.com/your-org/vector-tracer-pro.git
cd "vector-tracer-pro"

# 2. Create virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 3. Install in editable mode with dev dependencies
pip install -e ".[dev]"

# 4. Install pre-commit hooks
pre-commit install --hook-type pre-commit --hook-type commit-msg

# 5. Verify external dependencies
.\scripts\check_deps.ps1

# 6. Run the application
vector-tracer-pro
```

## Running Tests

```powershell
# Unit tests only (no external binaries required)
pytest -m unit

# All tests including integration (requires Potrace + Inkscape on PATH)
pytest

# With benchmark tests
pytest -m benchmark --benchmark-only
```

## Project Structure

See [`docs/architecture/`](docs/architecture/) for the full architecture documentation.

## Versioning

This project follows [Semantic Versioning 2.0](https://semver.org/). See [`CHANGELOG.md`](CHANGELOG.md) for the release history.

## License

MIT — see [`LICENSE`](LICENSE).
