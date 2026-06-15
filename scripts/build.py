#!/usr/bin/env python
"""
scripts.build
~~~~~~~~~~~~~

Build script for compiling Vector Tracer Pro to a standalone directory using PyInstaller.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent


def run(cmd: list[str], **kwargs) -> int:
    """Helper to print and run subprocess commands."""
    print(f"\n>>> {' '.join(cmd)}")
    result = subprocess.run(cmd, **kwargs)
    return result.returncode


def main() -> None:
    """Main build orchestration logic."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-tests", action="store_true")
    parser.add_argument("--version", default="1.0.0")
    args = parser.parse_args()

    # 1. Test suite
    if not args.skip_tests:
        print("=== Running test suite ===")
        # Clear PYTHONPATH to prevent QGIS/system python overrides during execution
        import os
        env = os.environ.copy()
        env["PYTHONPATH"] = ""
        env["PYTHONHOME"] = ""
        code = run([sys.executable, "-m", "pytest", "-p", "no:cov", "-o", "addopts=", "-q"], env=env)
        if code != 0:
            print("ABORT: Tests failed. Fix before building.")
            sys.exit(1)

    # 2. Clean
    print("\n=== Cleaning previous build ===")
    for d in ["dist", "build"]:
        shutil.rmtree(ROOT / d, ignore_errors=True)

    # 3. PyInstaller
    print("\n=== Building with PyInstaller ===")
    code = run([
        sys.executable, "-m", "PyInstaller",
        str(ROOT / "vector_tracer_pro.spec"),
        "--noconfirm",
    ])
    if code != 0:
        print("ABORT: PyInstaller failed.")
        sys.exit(1)

    # 4. Verifikasi output
    dist_dir = ROOT / "dist" / "VectorTracerPro"
    exe = dist_dir / "VectorTracerPro.exe"
    if not exe.exists():
        print(f"ABORT: Output exe not found at {exe}")
        sys.exit(1)

    size_mb = sum(f.stat().st_size for f in dist_dir.rglob("*") if f.is_file()) / 1e6
    if size_mb < 50:
        print(f"WARNING: Build output seems too small ({size_mb:.1f} MB) — check for missing files")

    print(f"\n=== Build successful ===")
    print(f"Output : {dist_dir}")
    print(f"Size   : {size_mb:.1f} MB")
    print(f"Version: {args.version}")


if __name__ == "__main__":
    main()
