# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller: Windows one-file GUI bez konsoli."""

from pathlib import Path

spec_directory = Path(SPECPATH).resolve()
project_root = spec_directory.parent
entry_point = project_root / "FH6AddonLinker.pyw"
if not entry_point.is_file():
    raise FileNotFoundError(f"GUI launcher was not found: {entry_point}")

analysis = Analysis(
    [str(entry_point)],
    pathex=[str(project_root)],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
archive = PYZ(analysis.pure)

# Bez COLLECT: PyInstaller umieści Python, tkinter/Tcl-Tk i aplikację w jednym EXE.
executable = EXE(
    archive,
    analysis.scripts,
    analysis.binaries,
    analysis.datas,
    [],
    name="FH6AddonLinker",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
)
