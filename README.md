# Vector Tracer Pro

> **Production-ready desktop application for converting raster images into stock-ready SVG vector graphics.**

[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue)](https://python.org)
[![PySide6](https://img.shields.io/badge/UI-PySide6-41cd52)](https://doc.qt.io/qtforpython/)
[![Tests](https://img.shields.io/badge/tests-320%20passed-brightgreen)]()
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## Overview

Vector Tracer Pro automates the raster-to-vector conversion workflow for stock image contributors. It classifies each image (monochrome, greyscale, colour-simple, colour-complex), selects the optimal tracing engine, validates the output against marketplace specifications, and packages everything into a clean SVG ready for submission.

**Supported tracing engines:**

| Engine | Best for | Bundled |
|---|---|---|
| [Potrace](http://potrace.sourceforge.net/) | Monochrome line art, logos | ✅ `bin/potrace.exe` |
| [VTracer](https://github.com/visioncortex/vtracer) | Colour-simple illustrations | ✅ `bin/vtracer.exe` |
| [Inkscape](https://inkscape.org/) | Complex colour photos | ⚠️ Install separately |

**Supported marketplaces:**

| Marketplace | Min resolution | Max file size |
|---|---|---|
| Adobe Stock | 15 MP | 100 MB |
| Shutterstock | 4 MP | 50 MB |
| Freepik | — | 25 MB |

---

## Quick Start (Pre-built Installer)

1. Download **`VectorTracerPro-Setup-1.0.0.exe`** from the [Releases page](https://github.com/galihanggara/Vector-Tracer-Pro/releases).
2. Run the installer — no administrator rights required.
3. Launch **Vector Tracer Pro** from the Start Menu or desktop shortcut.
4. Drag & drop your images onto the drop zone and click **Trace Now**.

> **Inkscape** (optional, for complex colour images): install from [inkscape.org](https://inkscape.org/release/) and ensure `inkscape.exe` is on your system `PATH`.

---

## Build from Source

### Prerequisites

| Tool | Version | Notes |
|---|---|---|
| Python | 3.12+ | [python.org/downloads](https://www.python.org/downloads/) |
| Git | any | |
| Potrace | 1.16+ | `bin/potrace.exe` already bundled in repo |
| VTracer | 0.6.0+ | `bin/vtracer.exe` already bundled in repo |
| Inkscape | 1.0+ | Optional — install system-wide |

### 1. Clone & Install

```powershell
git clone https://github.com/galihanggara/Vector-Tracer-Pro.git
cd "Vector Tracer Pro"

python -m venv .venv
.venv\Scripts\Activate.ps1

pip install -e ".[dev]"
```

### 2. Run Tests

```powershell
# Clear system Python interference (important on machines with QGIS etc.)
$env:PYTHONPATH = ""; $env:PYTHONHOME = ""
.venv\Scripts\pytest -o addopts="" -q
```

Expected output: **320 passed, 8 skipped**

### 3. Run the Application (Dev Mode)

```powershell
.venv\Scripts\python.exe -m vector_tracer_pro.app
```

### 4. Build Standalone Executable

```powershell
.venv\Scripts\python.exe scripts/build.py
# Output: dist/VectorTracerPro/VectorTracerPro.exe (~168 MB)
```

Options:
```powershell
# Skip test suite for faster iteration builds
.venv\Scripts\python.exe scripts/build.py --skip-tests

# Embed version in build output
.venv\Scripts\python.exe scripts/build.py --version 1.0.1
```

### 5. Build Windows Installer (requires [Inno Setup 6](https://jrsoftware.org/isinfo.php))

```powershell
# First build the executable, then compile the installer
.venv\Scripts\python.exe scripts/build.py
iscc installer\setup.iss
# Output: installer/output/VectorTracerPro-Setup-1.0.0.exe
```

---

## Project Architecture

```
Vector Tracer Pro/
├── bin/                          # Bundled binaries (potrace.exe, vtracer.exe)
├── src/vector_tracer_pro/
│   ├── app.py                    # Entrypoint — Qt bootstrap + update checker
│   ├── config/                   # Pydantic config models & defaults
│   ├── core/
│   │   ├── image/                # ImageLoader, Classifier, Preprocessor, Bitmapper
│   │   ├── dependency_checker.py # Runtime binary & permissions validation
│   │   ├── marketplace_validator.py  # Adobe Stock / Shutterstock / Freepik rules
│   │   ├── path_manager.py       # Centralised filesystem paths + bundle detection
│   │   ├── pipeline.py           # Main orchestrator — load→classify→preprocess→trace→validate
│   │   └── trace_strategy.py     # Potrace / VTracer / Inkscape / Fallback strategies
│   ├── services/
│   │   ├── batch_runner.py       # ThreadPoolExecutor batch processor
│   │   ├── preset_manager.py     # JSON-backed tracing preset storage
│   │   └── updater.py            # GitHub Releases async update checker (QThread)
│   ├── ui/
│   │   ├── main_window.py        # QMainWindow skeleton + splitter layout
│   │   ├── controllers/          # MainController — wires signals, manages workers
│   │   ├── styles/               # Dark QSS theme
│   │   └── widgets/              # DropZone, PreviewPanel, ControlPanel, BatchQueueTable
│   └── workers/
│       └── trace_worker.py       # QRunnable wrapping Pipeline for thread pool
├── tests/
│   ├── integration/              # Real binary tests (auto-skipped if binary absent)
│   └── unit/                     # Fast offline tests — 320 total
├── installer/setup.iss           # Inno Setup Windows installer script
├── scripts/build.py              # Automated build pipeline
└── vector_tracer_pro.spec        # PyInstaller spec — binary bundling + exclusions
```

### Key Design Decisions

| Decision | Rationale |
|---|---|
| **Core has zero Qt imports** | Business logic is testable without a display server |
| **Progress via callback** | `Pipeline.run(on_progress=...)` decouples core from UI threading model |
| **Temp files via context manager** | `Bitmapper.write()` guarantees cleanup even on exceptions |
| **Fallback chain** | Configurable engine order; accumulates errors before raising `TraceFailedError` |
| **Binary resolution** | `PathManager.get_binary_path()` checks bundled `bin/` first, falls back to `PATH` |
| **Update check post-startup** | `UpdateChecker` starts after `window.show()` — zero startup latency impact |

---

## Marketplace Submission Guide

### Adobe Stock

1. Trace with **Potrace** (monochrome) or **Inkscape** (colour).
2. Ensure minimum **15 MP** (`width × height ≥ 15,000,000 px`).
3. File size must be under **100 MB**.
4. Save as **SVG** (the application outputs standards-compliant SVG directly).
5. Upload at [stock.adobe.com/contributor](https://stock.adobe.com/contributor).

### Shutterstock

1. Minimum **4 MP** (`width × height ≥ 4,000,000 px`).
2. File size under **50 MB**.
3. Add IPTC metadata (keywords, description) using your preferred metadata editor before upload.
4. Upload at [submit.shutterstock.com](https://submit.shutterstock.com).

### Freepik

1. File size under **25 MB**.
2. No minimum resolution requirement.
3. Upload at [freepik.com/upload](https://www.freepik.com/upload).

> The **Marketplace** dropdown in the Control Panel selects the validation preset automatically. Any issues are shown in the status bar before you save.

---

## Configuration

User settings are stored in platform-appropriate directories (no registry writes):

| Directory | Content |
|---|---|
| `%APPDATA%\VectorTracerPro\` | `config.json`, user presets |
| `%LOCALAPPDATA%\VectorTracerPro\Cache\temp\` | Intermediate bitmaps (auto-cleaned) |
| `%LOCALAPPDATA%\VectorTracerPro\Logs\` | Rotating log files |

---

## Development

### Running Specific Test Groups

```powershell
# Unit tests only (no binaries required)
.venv\Scripts\pytest -m unit -o addopts="" -q

# Integration tests (requires potrace/inkscape on PATH)
.venv\Scripts\pytest -m integration -o addopts="" -v

# GUI tests only
.venv\Scripts\pytest -m gui -o addopts="" -v
```

### Code Quality

```powershell
# Lint + format check
.venv\Scripts\ruff check src/ tests/
.venv\Scripts\ruff format --check src/ tests/

# Type checking
.venv\Scripts\mypy src/
```

### Adding a New Tracing Engine

1. Subclass `TracingStrategy` in `core/trace_strategy.py`.
2. Implement `execute(input_path, output_path, params)`.
3. Register the class in `_ENGINE_MAP` inside `FallbackTracingStrategy`.
4. Add the engine name to `DEFAULT_FALLBACK_ORDER` (or keep it opt-in).
5. Write unit tests mocking `DependencyChecker` and `subprocess.run`.

---

## License

MIT — see [LICENSE](LICENSE).

---

## Acknowledgements

- [Potrace](http://potrace.sourceforge.net/) by Peter Selinger
- [VTracer](https://github.com/visioncortex/vtracer) by VisionCortex
- [Inkscape](https://inkscape.org/) — free and open-source vector graphics editor
- [PySide6](https://doc.qt.io/qtforpython/) — Qt for Python
