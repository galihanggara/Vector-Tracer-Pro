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

    # 5. Kompilasi installer Inno Setup (jika ISCC tersedia)
    import os
    iscc_paths = [
        r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
        r"C:\Program Files\Inno Setup 6\ISCC.exe",
        # Inno Setup 6.7+ via winget may install to a different location
        r"C:\Program Files (x86)\Inno Setup 6.7\ISCC.exe",
        r"C:\Program Files\Inno Setup 6.7\ISCC.exe",
        # winget sometimes installs with minor version in folder name
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"),
        os.path.expandvars(r"%PROGRAMFILES(X86)%\Inno Setup 6\ISCC.exe"),
        os.path.expandvars(r"%PROGRAMFILES%\Inno Setup 6\ISCC.exe"),
    ]
    # Also try shutil.which in case it's on PATH
    import shutil as _shutil
    iscc_on_path = _shutil.which("ISCC")
    if iscc_on_path:
        iscc_paths.insert(0, iscc_on_path)

    iscc = next((p for p in iscc_paths if Path(p).exists()), None)

    if iscc:
        print(f"\n=== Compiling Inno Setup installer (using {iscc}) ===")
        installer_output = ROOT / "installer" / "output"
        installer_output.mkdir(parents=True, exist_ok=True)
        code = run([iscc, str(ROOT / "installer" / "setup.iss")])
        if code == 0:
            setup_exe = next(installer_output.glob("*.exe"), None)
            if setup_exe:
                size_mb_installer = setup_exe.stat().st_size / 1e6
                print(f"Installer : {setup_exe}")
                print(f"Size      : {size_mb_installer:.1f} MB")
            else:
                print("WARNING: Installer compiled but no .exe found in installer/output/")
        else:
            print("WARNING: Inno Setup compilation failed — installer not created")
    else:
        print("\nINFO: Inno Setup (ISCC.exe) not found — skipping installer compilation")
        print("      Download: https://jrsoftware.org/isdl.php")
        print("      Or run: winget install --id JRSoftware.InnoSetup -e")


if __name__ == "__main__":
    main()


