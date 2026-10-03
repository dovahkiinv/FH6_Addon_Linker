"""Interfejs wiersza poleceń; rdzeń współdzielony z przyszłym GUI."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from . import __version__
from .engine import LinkerEngine
from .paths import (
    PathValidationError,
    detect_game_installs,
    validate_config,
)
from .scanner import ScanResult
from .state import AppConfig, StateError, StateStore


def build_parser() -> argparse.ArgumentParser:
    """Buduje parser dostępnych poleceń CLI milestone'u M1."""
    parser = argparse.ArgumentParser(
        prog="fh6linker",
        description="Odwracalne zarządzanie modami Forza Horizon 6.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"FH6 Addon Linker {__version__}",
        help="wyświetla wersję i kończy działanie",
    )
    commands = parser.add_subparsers(dest="command")

    set_parser = commands.add_parser("set", help="zapisuje folder gry i bibliotekę modów")
    set_parser.add_argument("--game", required=True, metavar="PATH", help="folder instalacji gry")
    set_parser.add_argument("--library", required=True, metavar="PATH", help="folder biblioteki modów")
    set_parser.add_argument("--backup-dir", metavar="PATH", help="magazyn kopii zapasowych")
    set_parser.add_argument(
        "--method",
        choices=("auto", "hardlink", "symlink", "copy"),
        default="auto",
        help="metoda wdrażania plików (domyślnie auto)",
    )
    set_parser.add_argument("--dry-run", action="store_true", help="sprawdza ścieżki bez zapisu konfiguracji")

    commands.add_parser("autodetect", help="szuka instalacji gry Steam/Xbox")

    scan_parser = commands.add_parser("scan", help="skanuje skonfigurowaną bibliotekę")
    scan_parser.add_argument("--json", action="store_true", help="zwraca raport JSON")

    status_parser = commands.add_parser("status", help="pokazuje stan modów i linków")
    status_parser.add_argument("--json", action="store_true", help="zwraca raport JSON")

    enable_parser = commands.add_parser("enable", help="włącza wskazane mody")
    enable_parser.add_argument("names", nargs="+", metavar="NAZWA")
    enable_parser.add_argument("--force", action="store_true", help="świadomie przejmuje pliki innego moda")
    enable_parser.add_argument("--dry-run", action="store_true", help="pokazuje plan bez zmian na dysku")
    enable_parser.add_argument(
        "--force-while-running",
        action="store_true",
        help="świadomie zezwala na zmianę plików przy uruchomionej grze",
    )

    disable_parser = commands.add_parser("disable", help="wyłącza wskazane mody")
    disable_parser.add_argument("names", nargs="+", metavar="NAZWA")
    disable_parser.add_argument("--dry-run", action="store_true", help="pokazuje plan bez zmian na dysku")
    disable_parser.add_argument("--force-while-running", action="store_true")

    repair_parser = commands.add_parser("repair", help="naprawia zerwane linki wdrożonych modów")
    repair_parser.add_argument("names", nargs="*", metavar="NAZWA")
    repair_parser.add_argument("--dry-run", action="store_true", help="pokazuje plan bez zmian na dysku")
    repair_parser.add_argument("--force-while-running", action="store_true")

    verify_parser = commands.add_parser("verify", help="sprawdza hashe wdrożonych plików")
    verify_parser.add_argument("names", nargs="*", metavar="NAZWA")
    verify_parser.add_argument("--json", action="store_true", help="zwraca raport JSON")

    restore_parser = commands.add_parser("restore", help="wyłącza wszystkie mody i przywraca backupy")
    restore_parser.add_argument("--yes", action="store_true", help="potwierdza przywrócenie oryginałów")
    restore_parser.add_argument("--dry-run", action="store_true", help="pokazuje plan bez zmian na dysku")
    restore_parser.add_argument("--force-while-running", action="store_true")

    commands.add_parser("doctor", help="sprawdza konfigurację i magazyn stanu")
    commands.add_parser("gui", help="uruchamia GUI (dostępne od milestone'u M2)")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Uruchamia wybrane polecenie i zwraca kod zgodny z CLI."""
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        return 0

    store = StateStore()
    engine = LinkerEngine(store)
    try:
        if args.command == "set":
            if args.dry_run:
                planned_config = validate_config(
                    AppConfig(
                        game_root=Path(args.game),
                        library_dir=Path(args.library),
                        backup_dir=Path(args.backup_dir) if args.backup_dir else None,
                        method=args.method,
                    ),
                    default_backup_dir=store.config_dir / "backups",
                )
                _write_text(
                    f"Plan konfiguracji (bez zapisu): gra={planned_config.game_root}; "
                    f"biblioteka={planned_config.library_dir}; "
                    f"backup={planned_config.backup_dir or '(domyślny)'}; "
                    f"metoda={planned_config.method}.\n"
                )
                return 0
            config = engine.configure(args.game, args.library, args.backup_dir, args.method)
            _write_text(
                f"Zapisano konfigurację. Gra: {config.game_root}; biblioteka: {config.library_dir}; "
                f"metoda: {config.method}.\n"
            )
            return 0
        if args.command == "autodetect":
            candidates = detect_game_installs()
            if not candidates:
                _write_text(
                    "Nie wykryto instalacji FH6. Sprawdź, czy gra jest zainstalowana, "
                    "albo użyj `fh6linker set --game PATH --library PATH`.\n"
                )
                return 1
            for candidate in candidates:
                _write_text(f"{candidate.path} ({candidate.source})\n")
            return 0
        if args.command == "scan":
            scan = engine.scan()
            payload = _scan_dict(scan)
            if args.json:
                _write_json(payload)
            else:
                _show_scan(scan)
            return 1 if scan.errors else 0
        if args.command == "status":
            status = engine.status()
            if args.json:
                _write_json(status.as_dict())
            else:
                _show_status(status)
            return 1 if status.errors else 0
        if args.command == "enable":
            report = engine.enable(
                args.names,
                force=args.force,
                dry_run=args.dry_run,
                force_while_running=args.force_while_running,
            )
            _show_operation(report)
            return report.exit_code
        if args.command == "disable":
            report = engine.disable(
                args.names,
                dry_run=args.dry_run,
                force_while_running=args.force_while_running,
            )
            _show_operation(report)
            return report.exit_code
        if args.command == "repair":
            report = engine.repair(
                args.names or None,
                dry_run=args.dry_run,
                force_while_running=args.force_while_running,
            )
            _show_operation(report)
            return report.exit_code
        if args.command == "verify":
            report = engine.verify(args.names or None)
            if args.json:
                _write_json(report.as_dict())
            else:
                _show_operation(report)
            return report.exit_code
        if args.command == "restore":
            if not args.yes and not args.dry_run:
                _write_error(
                    "Przerwano restore: operacja wymaga potwierdzenia. "
                    "Uruchom ponownie z `--yes` po sprawdzeniu kopii zapasowych.\n"
                )
                return 1
            report = engine.restore(
                dry_run=args.dry_run,
                force_while_running=args.force_while_running,
            )
            _show_operation(report)
            return report.exit_code
        if args.command == "doctor":
            return _doctor(store)
        if args.command == "gui":
            _write_error(
                "GUI nie jest jeszcze dostępne w M1. Zostanie dodane w milestone M2; "
                "na razie użyj poleceń CLI.\n"
            )
            return 1
    except (PathValidationError, StateError, OSError, ValueError) as exc:
        _write_error(f"Błąd: {exc}\n")
        return 1

    parser.error("Nieobsługiwane polecenie.")
    return 1


def _doctor(store: StateStore) -> int:
    """Wykonuje podstawowe kontrole bez zmiany plików gry."""
    problems = 0
    try:
        config = validate_config(
            store.load_config(),
            default_backup_dir=store.config_dir / "backups",
        )
    except (StateError, PathValidationError) as exc:
        _write_text(f"Konfiguracja: BŁĄD — {exc}\n")
        return 1
    _write_text(f"Gra: OK — {config.game_root}\n")
    _write_text(f"Biblioteka: OK — {config.library_dir}\n")
    backup_dir = config.backup_dir or (store.config_dir / "backups")
    _write_text(f"Magazyn kopii: {backup_dir}\n")
    try:
        state = store.load_state()
        _write_text(f"Stan: OK — {len(state.mods)} modów w state.json\n")
    except StateError as exc:
        _write_text(f"Stan: BŁĄD — {exc}\n")
        problems += 1
    try:
        free = shutil.disk_usage(backup_dir if backup_dir.exists() else backup_dir.parent).free
        _write_text(f"Wolne miejsce na backupy: {free} B\n")
    except OSError as exc:
        _write_text(f"Wolne miejsce: nie można sprawdzić ({exc})\n")
        problems += 1
    if config.method == "auto":
        _write_text("Metoda linkowania: auto (hardlink → symlink → kopia)\n")
    else:
        _write_text(f"Metoda linkowania: {config.method}\n")
    return 1 if problems else 0


def _scan_dict(scan: ScanResult) -> dict[str, Any]:
    return {
        "library_dir": str(scan.library_dir),
        "mods": [
            {
                "id": mod.mod_id,
                "name": mod.display_name,
                "folder_name": mod.name,
                "category": mod.category,
                "source_root": str(mod.source_root),
                "moderoot_rel": mod.moderoot_rel,
                "root_marker": mod.root_marker,
                "valid": mod.valid,
                "files": [
                    {
                        "source": str(file.source_path),
                        "target": file.target_rel,
                        "size": file.size,
                    }
                    for file in mod.files
                ],
                "warnings": [issue.message for issue in mod.issues],
            }
            for mod in scan.mods
        ],
        "warnings": [issue.message for issue in scan.warnings],
        "errors": [issue.message for issue in scan.errors],
    }


def _show_scan(scan: ScanResult) -> None:
    _write_text(f"Biblioteka: {scan.library_dir}\nWykryte mody: {len(scan.mods)}\n")
    for mod in scan.mods:
        state = "OK" if mod.valid else "BŁĄD STRUKTURY"
        _write_text(f"- {mod.display_name} [{mod.mod_id}] — {len(mod.files)} plików — {state}\n")
        for issue in mod.issues:
            _write_text(f"    {issue.severity}: {issue.message}\n")
    for issue in scan.issues:
        _write_text(f"{issue.severity}: {issue.message}\n")


def _show_status(status: Any) -> None:
    if not status.mods:
        _write_text("Brak modów w bibliotece lub nie skonfigurowano skanu.\n")
    for mod in status.mods:
        _write_text(
            f"{mod.status:12} {mod.name} — {mod.file_count} plików"
            + (f", {mod.broken_count} problemów" if mod.broken_count else "")
            + "\n"
        )
        for warning in mod.warnings:
            _write_text(f"    Uwaga: {warning}\n")
    for warning in status.warnings:
        _write_text(f"Uwaga: {warning}\n")
    for error in status.errors:
        _write_error(f"Błąd: {error}\n")


def _show_operation(report: Any) -> None:
    verb = "Plan" if report.dry_run else "Wynik"
    _write_text(
        f"{verb} operacji {report.operation}: {report.files_planned} plików w planie, "
        f"{report.files_changed} zmian.\n"
    )
    for action in report.actions:
        if report.dry_run:
            line = f"- {action.action}: {action.mod_name}"
            if action.file:
                line += f" — {action.file} ({action.size} B)"
            if action.backup:
                line += f"; backup: {action.backup}"
            if action.note:
                line += f"; {action.note}"
            _write_text(line + "\n")
    for warning in report.warnings:
        _write_text(f"Uwaga: {warning}\n")
    for conflict in report.conflicts:
        _write_error(f"Konflikt: {conflict}\n")
    for error in report.errors:
        _write_error(f"Błąd: {error}\n")


def _write_json(payload: dict[str, Any]) -> None:
    _write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


def _write_text(text: str) -> None:
    sys.stdout.write(text)


def _write_error(text: str) -> None:
    sys.stderr.write(text)


if __name__ == "__main__":
    raise SystemExit(main())
