"""Testy smoke dla szkieletu milestone'u M0."""

from __future__ import annotations

import importlib
import subprocess
import sys
from importlib.metadata import distribution
from pathlib import Path

import fh6linker


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_MODULES = (
    "fh6linker.__main__",
    "fh6linker.cli",
    "fh6linker.paths",
    "fh6linker.linkops",
    "fh6linker.scanner",
    "fh6linker.state",
    "fh6linker.engine",
    "fh6linker.report",
    "fh6linker.importer",
    "fh6linker.i18n",
    "fh6linker.gui",
    "fh6linker.gui.app",
    "fh6linker.gui.wizard",
    "fh6linker.gui.dialogs",
    "fh6linker.gui.theme",
)


def test_scaffold_modules_are_importable() -> None:
    """Wszystkie moduły szkieletu można zaimportować bez efektów ubocznych."""
    for module_name in PACKAGE_MODULES:
        importlib.import_module(module_name)


def test_module_entrypoint_displays_version() -> None:
    """Polecenie python -m fh6linker --version zwraca wersję pakietu."""
    result = subprocess.run(
        [sys.executable, "-m", "fh6linker", "--version"],
        cwd=PROJECT_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert fh6linker.__version__ in result.stdout
    assert result.stderr == ""


def test_console_entrypoint_is_registered() -> None:
    """Instalacja projektu rejestruje polecenie konsolowe fh6linker."""
    entry_points = distribution("fh6-addon-linker").entry_points

    assert any(
        entry_point.group == "console_scripts"
        and entry_point.name == "fh6linker"
        and entry_point.value == "fh6linker.cli:main"
        for entry_point in entry_points
    )


def test_cli_without_arguments_shows_help() -> None:
    """Bez polecenia parser pokazuje użytkownikowi dostępne opcje."""
    result = subprocess.run(
        [sys.executable, "-m", "fh6linker"],
        cwd=PROJECT_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "usage: fh6linker" in result.stdout
