"""Interfejs wiersza poleceń FH6 Addon Linker."""

from __future__ import annotations

import argparse
from collections.abc import Sequence

from . import __version__


def build_parser() -> argparse.ArgumentParser:
    """Buduje parser CLI dostępny w bieżącym szkielecie M0."""
    parser = argparse.ArgumentParser(
        prog="fh6linker",
        description="Narzędzie do odwracalnego zarządzania modami FH6.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"FH6 Addon Linker {__version__}",
        help="wyświetla wersję i kończy działanie",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Uruchamia parser CLI; właściwe polecenia zostaną dodane w M1."""
    parser = build_parser()
    parser.parse_args(argv)
    parser.print_help()
    return 0
