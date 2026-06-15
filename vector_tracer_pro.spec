# -*- mode: python ; coding: utf-8 -*-
"""
vector_tracer_pro.spec
~~~~~~~~~~~~~~~~~~~~~~

Manual PyInstaller spec file for building Vector Tracer Pro.
"""

import sys
from pathlib import Path

block_cipher = None
ROOT = Path(SPECPATH)

a = Analysis(
    [str(ROOT / "src" / "vector_tracer_pro" / "app.py")],
    pathex=[str(ROOT / "src")],
    binaries=[
        (str(ROOT / "bin" / "potrace.exe"), "bin"),
        (str(ROOT / "bin" / "vtracer.exe"), "bin"),
    ],
    datas=[
        (str(ROOT / "src" / "vector_tracer_pro" / "ui" / "styles"), 
         "vector_tracer_pro/ui/styles"),
    ],
    hiddenimports=[
        "PySide6.QtSvgWidgets",
        "PySide6.QtXml",
        "PIL._tkinter_finder",
        "numpy.core._multiarray_umath",
        "vector_tracer_pro.core.image",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "IPython"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="VectorTracerPro",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,        # Headless window for production GUI
    icon=str(ROOT / "assets" / "icon.ico"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="VectorTracerPro",
)
