"""Wspólny silnik planowania, wdrażania, wyłączania i naprawy modów."""

from __future__ import annotations

import copy
import shutil
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Callable, Iterable

from .linkops import (
    FileDigest,
    LinkOperationError,
    copy_file_atomic,
    create_link,
    digest_file,
    is_owned,
    remove_if_owned,
)
from .paths import (
    PathValidationError,
    game_is_running,
    normalize_path,
    validate_config,
    validate_config_paths,
)
from .report import ModStatus, OperationReport, PlannedAction, StatusReport
from .scanner import Mod, ModFile, ScanResult, scan_library
from .state import (
    AppConfig,
    AppState,
    FileState,
    JournalEvent,
    ModState,
    StateError,
    StateStore,
)


@dataclass
class _PlannedFile:
    """Zweryfikowany element planu deploy/repair."""

    mod: Mod
    mod_file: ModFile
    source_digest: FileDigest
    target: Path
    backup_path: Path | None
    backup_rel: str | None
    backup_needs_copy: bool
    action: str
    previous_owner_id: str | None = None
    previous_owner_entry: FileState | None = None
    previous_mod_entry: FileState | None = None
    replace_owned: bool = False
    original_digest: FileDigest | None = None
    created_dirs: tuple[Path, ...] = ()


class LinkerEngine:
    """Warstwa domenowa używana niezależnie przez CLI i przyszłe GUI."""

    def __init__(
        self,
        store: StateStore | None = None,
        *,
        after_file_hook: Callable[[int], None] | None = None,
    ) -> None:
        self.store = store or StateStore()
        self.after_file_hook = after_file_hook

    def configure(
        self,
        game_root: str | Path,
        library_dir: str | Path,
        backup_dir: str | Path | None = None,
        method: str = "auto",
    ) -> AppConfig:
        """Waliduje i zapisuje ścieżki oraz metodę linkowania."""
        if method not in {"auto", "hardlink", "symlink", "copy"}:
            raise PathValidationError(
                f"Nieznana metoda linkowania: {method}. Wybierz auto, hardlink, symlink lub copy."
            )
        game, library, backup = validate_config_paths(game_root, library_dir, backup_dir)
        config = AppConfig(
            game_root=game,
            library_dir=library,
            backup_dir=backup,
            method=method,
            block_while_game_running=True,
        )
        config = validate_config(
            config,
            default_backup_dir=self.store.config_dir / "backups",
        )
        self.store.save_config(config)
        return config

    def scan(self) -> ScanResult:
        """Skanuje bibliotekę i zapisuje czas ostatniego skanu."""
        config = self._config()
        assert config.library_dir is not None
        result = scan_library(config.library_dir)
        config.last_scan = datetime.now(UTC).astimezone().isoformat(timespec="seconds")
        self.store.save_config(config)
        return result

    def status(self) -> StatusReport:
        """Pokazuje status modów, zerwane linki i zmienione źródła."""
        report = StatusReport()
        try:
            config = self._config()
            with self.store.lock():
                state = self.store.load_state()
                self._recover_incomplete(state, config)
                scan = self._scan(config)
                return self._build_status(scan, state, config)
        except (PathValidationError, StateError, OSError, ValueError) as exc:
            report.errors.append(str(exc))
            return report

    def verify(self, names: Iterable[str] | None = None) -> OperationReport:
        """Porównuje hashe źródeł i wdrożonych plików dla wybranych modów."""
        report = OperationReport(operation="verify")
        try:
            config = self._config()
            with self.store.lock():
                state = self.store.load_state()
                self._recover_incomplete(state, config)
                selected = self._state_mod_ids(state, names, report)
                if report.errors:
                    return report
                assert config.game_root is not None
                for mod_id in selected:
                    mod_state = state.mods[mod_id]
                    for rel, entry in mod_state.files.items():
                        target = self._target_path(config.game_root, rel)
                        source = Path(entry.source)
                        if not is_owned(
                            target,
                            source,
                            entry.method,
                            entry.deployed_sha256,
                            entry.deployed_size,
                        ):
                            report.errors.append(
                                f"ZERWANY: {rel} nie jest już wdrożonym plikiem moda {mod_id}. "
                                "Użyj `repair` albo sprawdź, czy gra nie została zaktualizowana."
                            )
                            continue
                        try:
                            source_digest = digest_file(source)
                            target_digest = digest_file(target)
                        except LinkOperationError as exc:
                            report.errors.append(str(exc))
                            continue
                        if source_digest.sha256 != entry.src_sha256:
                            report.warnings.append(
                                f"Źródło moda {mod_id} zmieniło się: {source}. Wykonaj ponowny deploy."
                            )
                        if target_digest.sha256 != entry.deployed_sha256:
                            report.errors.append(
                                f"Hash wdrożenia jest inny dla {rel}. Sprawdź aktualizację gry lub moda."
                            )
                        report.actions.append(
                            PlannedAction("verify", mod_id, rel, str(source), str(target), size=target_digest.size)
                        )
                report.files_changed = 0
                return report
        except (PathValidationError, StateError, OSError, ValueError) as exc:
            report.errors.append(str(exc))
            return report

    def enable(
        self,
        names: Iterable[str],
        *,
        force: bool = False,
        dry_run: bool = False,
        force_while_running: bool = False,
    ) -> OperationReport:
        """Włącza mody po pełnym planie walidacji i konfliktów."""
        return self._deploy(
            operation="enable",
            names=list(names),
            force=force,
            dry_run=dry_run,
            force_while_running=force_while_running,
            repair=False,
        )

    def repair(
        self,
        names: Iterable[str] | None = None,
        *,
        dry_run: bool = False,
        force_while_running: bool = False,
    ) -> OperationReport:
        """Odtwarza brakujące/zerwanych linki po sprawdzeniu źródeł i backupów."""
        return self._deploy(
            operation="repair",
            names=list(names) if names is not None else None,
            force=False,
            dry_run=dry_run,
            force_while_running=force_while_running,
            repair=True,
        )

    def disable(
        self,
        names: Iterable[str],
        *,
        dry_run: bool = False,
        force_while_running: bool = False,
    ) -> OperationReport:
        """Wyłącza wskazane mody, chroniąc pliki których własności nie potwierdzono."""
        return self._disable(
            list(names),
            operation="disable",
            dry_run=dry_run,
            force_while_running=force_while_running,
        )

    def restore(
        self,
        *,
        dry_run: bool = False,
        force_while_running: bool = False,
    ) -> OperationReport:
        """Wyłącza wszystkie mody i przywraca dostępne kopie waniliowych plików."""
        return self._disable(
            None,
            operation="restore",
            dry_run=dry_run,
            force_while_running=force_while_running,
        )

    def _deploy(
        self,
        *,
        operation: str,
        names: list[str] | None,
        force: bool,
        dry_run: bool,
        force_while_running: bool,
        repair: bool,
    ) -> OperationReport:
        report = OperationReport(operation=operation, dry_run=dry_run)
        try:
            config = self._config()
            self._check_game_running(config, force_while_running)
            if dry_run:
                state = self.store.load_state()
                scan = self._scan(config)
                planned = self._plan_deployment(
                    scan, state, config, names, force=force, repair=repair, report=report
                )
                self._check_backup_space(planned, config, report)
                return report

            with self.store.lock():
                state = self.store.load_state()
                self._recover_incomplete(state, config)
                state = self.store.load_state()
                scan = self._scan(config)
                planned = self._plan_deployment(
                    scan, state, config, names, force=force, repair=repair, report=report
                )
                self._check_backup_space(planned, config, report)
                if report.errors or report.conflicts:
                    return report
                self._execute_deployment(planned, state, config, report)
                return report
        except (PathValidationError, StateError, LinkOperationError, OSError, ValueError) as exc:
            report.errors.append(str(exc))
            if isinstance(exc, LinkOperationError) and exc.requires_privilege:
                report.privilege_required = True
            return report

    def _plan_deployment(
        self,
        scan: ScanResult,
        state: AppState,
        config: AppConfig,
        names: list[str] | None,
        *,
        force: bool,
        repair: bool,
        report: OperationReport,
    ) -> list[_PlannedFile]:
        assert config.game_root is not None
        assert config.library_dir is not None
        backup_dir = self._backup_dir(config)
        mods = self._select_mods(scan, state, names, repair, report)
        planned: list[_PlannedFile] = []
        owners = self._owners(state)
        selected_targets: dict[str, str] = {}

        for mod in mods:
            for issue in mod.issues:
                if issue.severity == "warning":
                    report.warnings.append(issue.message)
            if not mod.valid:
                report.errors.extend(
                    issue.message for issue in mod.issues if issue.severity == "error"
                )
                if not mod.issues:
                    report.errors.append(f"Mod nie zawiera plików do wdrożenia: {mod.display_name}.")
                continue
            current_mod_state = state.mods.get(mod.mod_id)
            for mod_file in mod.files:
                try:
                    source = mod_file.source_path.resolve(strict=True)
                    if not source.is_relative_to(config.library_dir):
                        raise PathValidationError(
                            f"Źródło moda wychodzi poza bibliotekę: {source}. "
                            "Usuń dowiązanie symboliczne i umieść plik bezpośrednio w bibliotece."
                        )
                    source_digest = digest_file(source)
                    target = self._target_path(config.game_root, mod_file.target_rel)
                    existing_entry = (
                        current_mod_state.files.get(mod_file.target_rel)
                        if current_mod_state
                        else None
                    )
                    target_key = mod_file.target_rel.casefold()
                    other_selected = selected_targets.get(target_key)
                    if other_selected and other_selected != mod.mod_id:
                        report.conflicts.append(
                            f"Kolizja: mody {other_selected} i {mod.mod_id} chcą pliku "
                            f"{mod_file.target_rel}. Włącz je osobno albo rozdziel pliki."
                        )
                        continue
                    selected_targets[target_key] = mod.mod_id

                    existing_entry_owned = bool(
                        existing_entry
                        and is_owned(
                            target,
                            Path(existing_entry.source),
                            existing_entry.method,
                            existing_entry.deployed_sha256,
                            existing_entry.deployed_size,
                        )
                    )
                    if existing_entry_owned and existing_entry:
                        if not repair:
                            if source_digest.sha256 != existing_entry.src_sha256:
                                report.warnings.append(
                                    f"Źródło {mod.display_name} zmieniło się od deployu; użyj repair lub "
                                    "wyłącz i włącz moda ponownie."
                                )
                            planned.append(
                                _PlannedFile(
                                    mod,
                                    mod_file,
                                    source_digest,
                                    target,
                                    self._backup_from_entry(existing_entry, backup_dir),
                                    existing_entry.backup,
                                    False,
                                    "already_enabled",
                                    previous_mod_entry=existing_entry,
                                )
                            )
                            report.actions.append(
                                PlannedAction(
                                    "already_enabled",
                                    mod.display_name,
                                    mod_file.target_rel,
                                    str(source),
                                    str(target),
                                    size=source_digest.size,
                                    note="Link już jest aktywny; brak zmian.",
                                )
                            )
                            continue
                        if (
                            source_digest.sha256 == existing_entry.src_sha256
                            and source_digest.size == existing_entry.src_size
                        ):
                            planned.append(
                                _PlannedFile(
                                    mod,
                                    mod_file,
                                    source_digest,
                                    target,
                                    self._backup_from_entry(existing_entry, backup_dir),
                                    existing_entry.backup,
                                    False,
                                    "already_enabled",
                                    previous_mod_entry=existing_entry,
                                )
                            )
                            report.actions.append(
                                PlannedAction(
                                    "already_enabled",
                                    mod.display_name,
                                    mod_file.target_rel,
                                    str(source),
                                    str(target),
                                    size=source_digest.size,
                                    note="Link działa i źródło nie zmieniło się.",
                                )
                            )
                            continue

                    previous_owner_id: str | None = None
                    previous_owner_entry: FileState | None = None
                    for owner_id, owner_entry in owners.get(target_key, []):
                        if owner_id == mod.mod_id:
                            continue
                        if target.exists() or target.is_symlink():
                            if not is_owned(
                                target,
                                Path(owner_entry.source),
                                owner_entry.method,
                                owner_entry.deployed_sha256,
                                owner_entry.deployed_size,
                            ):
                                report.conflicts.append(
                                    f"Konflikt {mod_file.target_rel}: plik w grze nie jest już linkiem "
                                    f"moda {owner_id}; pozostawiam go bez zmian."
                                )
                                continue
                            if not force:
                                report.conflicts.append(
                                    f"Konflikt {mod_file.target_rel}: pliku używa już mod {owner_id}. "
                                    "Wyłącz go albo powtórz z --force."
                                )
                                continue
                            previous_owner_id = owner_id
                            previous_owner_entry = owner_entry
                            report.warnings.append(
                                f"--force zastąpi wdrożenie moda {owner_id} w pliku {mod_file.target_rel}."
                            )
                        else:
                            if not force:
                                report.conflicts.append(
                                    f"Konflikt {mod_file.target_rel}: stan moda {owner_id} nadal rezerwuje "
                                    "ten plik. Użyj disable/repair przed kolejnym wdrożeniem."
                                )
                                continue
                            previous_owner_id = owner_id
                            previous_owner_entry = owner_entry
                            report.warnings.append(
                                f"--force przejmuje nieobecny target {mod_file.target_rel} z moda {owner_id}."
                            )

                    if report.conflicts and any(
                        f"{mod_file.target_rel}" in conflict for conflict in report.conflicts
                    ):
                        continue

                    if existing_entry and (target.exists() or target.is_symlink()) and not repair:
                        report.conflicts.append(
                            f"ZERWANY link {mod_file.target_rel} nie należy już do narzędzia. "
                            "Nie nadpisuję pliku; sprawdź go lub użyj repair po wykonaniu kopii."
                        )
                        continue

                    original_digest: FileDigest | None = None
                    backup_path: Path | None = None
                    backup_rel: str | None = None
                    backup_needs_copy = False
                    replace_owned = bool(existing_entry_owned and repair)
                    if existing_entry_owned and existing_entry:
                        backup_path = self._backup_from_entry(existing_entry, backup_dir)
                        backup_rel = existing_entry.backup
                        if backup_rel and (backup_path is None or not backup_path.is_file()):
                            report.errors.append(
                                f"Brakuje kopii bazowej dla {mod_file.target_rel}; "
                                "nie naprawiam wdrożenia."
                            )
                            continue
                    elif previous_owner_entry is not None:
                        backup_rel = previous_owner_entry.backup
                        backup_path = self._backup_from_entry(previous_owner_entry, backup_dir)
                        if backup_rel and (backup_path is None or not backup_path.is_file()):
                            report.errors.append(
                                f"Brakuje kopii bazowej moda {previous_owner_id} dla {mod_file.target_rel}; "
                                "nie przejmuję pliku. Sprawdź katalog backups."
                            )
                            continue
                    elif existing_entry and existing_entry.backup and not target.exists():
                        backup_rel = existing_entry.backup
                        backup_path = self._backup_from_entry(existing_entry, backup_dir)
                        if backup_path is None or not backup_path.is_file():
                            report.errors.append(
                                f"Brakuje kopii bazowej dla {mod_file.target_rel}. "
                                "Nie można bezpiecznie naprawić wdrożenia."
                            )
                            continue
                    elif target.exists() and not target.is_symlink():
                        try:
                            original_digest = digest_file(target)
                        except LinkOperationError as exc:
                            report.errors.append(str(exc))
                            continue
                        backup_path, backup_rel, backup_needs_copy = self._choose_backup(
                            backup_dir, mod_file.target_rel, original_digest
                        )
                        if repair and existing_entry and existing_entry.backup:
                            old_backup = self._backup_from_entry(existing_entry, backup_dir)
                            if old_backup and old_backup.resolve() != backup_path.resolve():
                                state.orphaned_backups.append(existing_entry.backup)
                    elif existing_entry and existing_entry.backup:
                        backup_rel = existing_entry.backup
                        backup_path = self._backup_from_entry(existing_entry, backup_dir)
                        if backup_path is None or not backup_path.is_file():
                            report.errors.append(
                                f"Brakuje kopii bazowej dla {mod_file.target_rel}. "
                                "Nie można bezpiecznie odtworzyć linku."
                            )
                            continue

                    if backup_path is not None and not backup_needs_copy:
                        backup_entry = previous_owner_entry or existing_entry
                        expected_backup_sha256 = (
                            original_digest.sha256
                            if original_digest is not None
                            else backup_entry.backup_sha256
                            if backup_entry is not None
                            else None
                        )
                        expected_backup_size = (
                            original_digest.size
                            if original_digest is not None
                            else backup_entry.backup_size
                            if backup_entry is not None
                            else None
                        )
                        try:
                            self._verify_backup_path(
                                backup_path,
                                expected_backup_sha256,
                                expected_backup_size,
                            )
                        except LinkOperationError as exc:
                            report.errors.append(str(exc))
                            continue

                    if target.is_symlink() and not existing_entry_owned:
                        report.conflicts.append(
                            f"Plik docelowy jest obcym lub zerwanym symlinkiem: {target}. "
                            "Nie nadpisuję go ani nie podążam za jego celem."
                        )
                        continue
                    missing_dirs = self._missing_game_dirs(config.game_root, target.parent)
                    action = "repair_link" if repair and existing_entry else "create_link"
                    if previous_owner_id:
                        action = "force_replace"
                    planned_file = _PlannedFile(
                        mod=mod,
                        mod_file=mod_file,
                        source_digest=source_digest,
                        target=target,
                        backup_path=backup_path,
                        backup_rel=backup_rel,
                        backup_needs_copy=backup_needs_copy,
                        action=action,
                        previous_owner_id=previous_owner_id,
                        previous_owner_entry=previous_owner_entry,
                        previous_mod_entry=existing_entry,
                        replace_owned=replace_owned,
                        original_digest=original_digest,
                        created_dirs=tuple(missing_dirs),
                    )
                    planned.append(planned_file)
                    report.actions.append(
                        PlannedAction(
                            action,
                            mod.display_name,
                            mod_file.target_rel,
                            str(source),
                            str(target),
                            str(backup_path) if backup_path else None,
                            source_digest.size,
                            "Użyta zostanie kopia pliku." if config.method == "copy" else None,
                        )
                    )
                    self._media_layout_warning(config.game_root, mod_file.target_rel, report)
                except (OSError, ValueError, LinkOperationError, PathValidationError) as exc:
                    report.errors.append(str(exc))

        self._append_scan_issues(scan, report)
        return planned

    def _execute_deployment(
        self,
        planned: list[_PlannedFile],
        state: AppState,
        config: AppConfig,
        report: OperationReport,
    ) -> None:
        changes = [item for item in planned if item.action != "already_enabled"]
        if not changes:
            return
        backup_dir = self._backup_dir(config)
        snapshot = copy.deepcopy(state)
        txid = uuid.uuid4().hex
        self.store.append_journal(
            JournalEvent.create(
                op=report.operation,
                phase="plan",
                txid=txid,
                details={"files": len(changes), "game": str(config.game_root)},
            )
        )
        completed = 0
        try:
            for item in changes:
                previous_mod_entry = (
                    item.previous_mod_entry.to_dict() if item.previous_mod_entry else None
                )
                previous_owner_entry = (
                    item.previous_owner_entry.to_dict() if item.previous_owner_entry else None
                )
                previous_backup_entry = item.previous_owner_entry or item.previous_mod_entry
                expected_backup_sha256 = (
                    item.original_digest.sha256
                    if item.original_digest
                    else previous_backup_entry.backup_sha256
                    if previous_backup_entry
                    else None
                )
                expected_backup_size = (
                    item.original_digest.size
                    if item.original_digest
                    else previous_backup_entry.backup_size
                    if previous_backup_entry
                    else None
                )
                details = {
                    "previous_exists": item.target.exists() or item.target.is_symlink(),
                    "previous_mod_entry": previous_mod_entry,
                    "previous_mod_state": (
                        snapshot.mods[item.mod.mod_id].to_dict()
                        if item.mod.mod_id in snapshot.mods
                        else None
                    ),
                    "previous_mod_owned": item.replace_owned,
                    "previous_owner_id": item.previous_owner_id,
                    "previous_owner_entry": previous_owner_entry,
                    "previous_owner_state": (
                        snapshot.mods[item.previous_owner_id].to_dict()
                        if item.previous_owner_id in snapshot.mods
                        else None
                    ),
                    "backup_rel": item.backup_rel,
                    "backup_needs_copy": item.backup_needs_copy,
                    "backup_sha256": expected_backup_sha256,
                    "backup_size": expected_backup_size,
                    "expected_sha256": item.source_digest.sha256,
                    "expected_size": item.source_digest.size,
                    "created_dirs": [str(path) for path in item.created_dirs],
                }
                self.store.append_journal(
                    JournalEvent.create(
                        op=report.operation,
                        phase="begin",
                        txid=txid,
                        mod=item.mod.mod_id,
                        file=item.mod_file.target_rel,
                        target=str(item.target),
                        source=str(item.mod_file.source_path),
                        backup=str(item.backup_path) if item.backup_path else None,
                        method=config.method,
                        action=item.action,
                        details=details,
                    )
                )
                if item.backup_path is not None:
                    self._assert_backup_path_safe(item.backup_path, backup_dir)
                self._create_game_dirs(item.created_dirs, state)
                if item.previous_owner_id and item.previous_owner_entry:
                    removed = remove_if_owned(
                        item.target,
                        item.previous_owner_entry.source,
                        item.previous_owner_entry.method,
                        item.previous_owner_entry.deployed_sha256,
                        item.previous_owner_entry.deployed_size,
                    )
                    if not removed:
                        raise LinkOperationError(
                            f"Konflikt {item.mod_file.target_rel}: poprzedni link zmienił się po planie. "
                            "Nie nadpisuję go."
                        )
                elif item.replace_owned and item.previous_mod_entry:
                    removed = remove_if_owned(
                        item.target,
                        item.previous_mod_entry.source,
                        item.previous_mod_entry.method,
                        item.previous_mod_entry.deployed_sha256,
                        item.previous_mod_entry.deployed_size,
                    )
                    if not removed:
                        raise LinkOperationError(
                            f"Wdrożenie {item.mod_file.target_rel} zmieniło się po planie. "
                            "Nie nadpisuję pliku."
                        )
                elif item.target.exists() and not item.target.is_symlink():
                    current_digest = digest_file(item.target)
                    if item.original_digest and (
                        current_digest.sha256 != item.original_digest.sha256
                        or current_digest.size != item.original_digest.size
                    ):
                        raise LinkOperationError(
                            f"Plik gry zmienił się po planie: {item.target}. "
                            "Operacja została wstrzymana; wykonaj ponowny skan."
                        )
                    if item.backup_path is None:
                        raise LinkOperationError(
                            f"Brak ścieżki kopii dla istniejącego pliku {item.target}. "
                            "Nie nadpisuję oryginału."
                        )
                    if item.backup_needs_copy:
                        copy_file_atomic(item.target, item.backup_path, overwrite=False)
                    backup_digest = digest_file(item.backup_path)
                    if backup_digest.sha256 != current_digest.sha256:
                        raise LinkOperationError(
                            f"Kopia oryginału {item.target} nie przeszła kontroli SHA-256. "
                            "Plik gry pozostał nietknięty."
                        )
                    self.store.append_journal(
                        JournalEvent.create(
                            op=report.operation,
                            phase="backup_done",
                            txid=txid,
                            mod=item.mod.mod_id,
                            file=item.mod_file.target_rel,
                            target=str(item.target),
                            backup=str(item.backup_path),
                            details={"sha256": backup_digest.sha256, "size": backup_digest.size},
                        )
                    )
                    if item.target.is_symlink() or not item.target.exists():
                        raise LinkOperationError(
                            f"Target {item.target} zmienił się podczas backupu. "
                            "Nie usuwam niezweryfikowanego pliku."
                        )
                    latest_digest = digest_file(item.target)
                    if (
                        latest_digest.sha256 != backup_digest.sha256
                        or latest_digest.size != backup_digest.size
                    ):
                        raise LinkOperationError(
                            f"Target {item.target} zmienił się po utworzeniu kopii. "
                            "Nie usuwam pliku gry."
                        )
                    item.target.unlink()
                elif item.target.is_symlink():
                    raise LinkOperationError(
                        f"Nie nadpisuję niezarządzanego symlinku: {item.target}. "
                        "Usuń go ręcznie po sprawdzeniu dokąd prowadzi."
                    )
                self.store.append_journal(
                    JournalEvent.create(
                        op=report.operation,
                        phase="original_removed",
                        txid=txid,
                        mod=item.mod.mod_id,
                        file=item.mod_file.target_rel,
                        target=str(item.target),
                        source=str(item.mod_file.source_path),
                        backup=str(item.backup_path) if item.backup_path else None,
                        method=config.method,
                        details=details,
                    )
                )
                actual_method, warnings = create_link(
                    item.mod_file.source_path, item.target, config.method
                )
                report.warnings.extend(warnings)
                deployed = digest_file(item.mod_file.source_path)
                if (
                    deployed.sha256 != item.source_digest.sha256
                    or deployed.size != item.source_digest.size
                ):
                    raise LinkOperationError(
                        f"Źródło moda zmieniło się podczas wdrażania: {item.mod_file.source_path}. "
                        "Cofam tę operację; uruchom skan i spróbuj ponownie."
                    )
                self.store.append_journal(
                    JournalEvent.create(
                        op=report.operation,
                        phase="link_created",
                        txid=txid,
                        mod=item.mod.mod_id,
                        file=item.mod_file.target_rel,
                        target=str(item.target),
                        source=str(item.mod_file.source_path),
                        backup=str(item.backup_path) if item.backup_path else None,
                        method=actual_method,
                        details=details,
                    )
                )
                mod_state = state.mods.get(item.mod.mod_id)
                if mod_state is None:
                    mod_state = ModState(
                        source_root=str(item.mod.source_root),
                        moderoot_rel=item.mod.moderoot_rel,
                        deployed_at=datetime.now(UTC).astimezone().isoformat(timespec="seconds"),
                        method=config.method,
                        display_name=item.mod.display_name,
                    )
                    state.mods[item.mod.mod_id] = mod_state
                else:
                    mod_state.source_root = str(item.mod.source_root)
                    mod_state.moderoot_rel = item.mod.moderoot_rel
                    mod_state.method = config.method
                    mod_state.display_name = item.mod.display_name
                backup_digest = (
                    self._verify_backup_path(
                        item.backup_path,
                        expected_backup_sha256,
                        expected_backup_size,
                    )
                    if item.backup_path is not None
                    else None
                )
                mod_state.files[item.mod_file.target_rel] = FileState(
                    method=actual_method,
                    source=str(item.mod_file.source_path),
                    src_sha256=deployed.sha256,
                    src_size=deployed.size,
                    src_mtime=deployed.mtime,
                    backup=item.backup_rel,
                    deployed_sha256=deployed.sha256,
                    deployed_size=deployed.size,
                    backup_sha256=backup_digest.sha256 if backup_digest else None,
                    backup_size=backup_digest.size if backup_digest else None,
                    backup_mtime=backup_digest.mtime if backup_digest else None,
                )
                if item.previous_owner_id:
                    previous_owner = state.mods.get(item.previous_owner_id)
                    if previous_owner is not None:
                        previous_owner.files.pop(item.mod_file.target_rel, None)
                        if not previous_owner.files:
                            state.mods.pop(item.previous_owner_id, None)
                self.store.save_state(state)
                self.store.append_journal(
                    JournalEvent.create(
                        op=report.operation,
                        phase="done",
                        txid=txid,
                        mod=item.mod.mod_id,
                        file=item.mod_file.target_rel,
                        target=str(item.target),
                        source=str(item.mod_file.source_path),
                        backup=str(item.backup_path) if item.backup_path else None,
                        method=actual_method,
                    )
                )
                completed += 1
                report.files_changed += 1
                if self.after_file_hook is not None:
                    self.after_file_hook(completed)
            self.store.save_state(state)
            self.store.append_journal(
                JournalEvent.create(
                    op=report.operation,
                    phase="commit",
                    txid=txid,
                    details={"deployed": completed, "conflicts": len(report.conflicts)},
                )
            )
        except BaseException as exc:
            if isinstance(exc, LinkOperationError) and exc.requires_privilege:
                report.privilege_required = True
            try:
                recovered_state = self.store.load_state()
                self._recover_transaction(txid, recovered_state, config)
                self.store.save_state(recovered_state)
                self.store.append_journal(
                    JournalEvent.create(
                        op=report.operation,
                        phase="rollback",
                        txid=txid,
                        details={"reason": str(exc)},
                    )
                )
            except BaseException as rollback_exc:
                self.store.save_state(snapshot)
                report.errors.append(
                    f"Operacja przerwana ({exc}); rollback też zgłosił błąd ({rollback_exc}). "
                    "Uruchom `fh6linker status` i `fh6linker doctor` przed kolejną zmianą."
                )
            if isinstance(exc, Exception):
                report.errors.append(
                    f"Nie udało się wdrożyć moda: {exc}. "
                    "Sprawdź log i uruchom ponownie status przed kolejną próbą."
                )
            else:
                raise

    def _disable(
        self,
        names: list[str] | None,
        *,
        operation: str,
        dry_run: bool,
        force_while_running: bool,
    ) -> OperationReport:
        report = OperationReport(operation=operation, dry_run=dry_run)
        try:
            config = self._config()
            self._check_game_running(config, force_while_running)
            if dry_run:
                state = self.store.load_state()
                self._plan_disable(state, config, names, report)
                return report
            with self.store.lock():
                state = self.store.load_state()
                self._recover_incomplete(state, config)
                state = self.store.load_state()
                plans = self._plan_disable(state, config, names, report)
                if report.errors:
                    return report
                self._execute_disable(plans, state, config, report)
                return report
        except (PathValidationError, StateError, LinkOperationError, OSError, ValueError) as exc:
            report.errors.append(str(exc))
            if isinstance(exc, LinkOperationError) and exc.requires_privilege:
                report.privilege_required = True
            return report

    def _plan_disable(
        self,
        state: AppState,
        config: AppConfig,
        names: list[str] | None,
        report: OperationReport,
    ) -> list[tuple[str, str, FileState, Path, str]]:
        assert config.game_root is not None
        selected = self._state_mod_ids(state, names, report)
        plans: list[tuple[str, str, FileState, Path, str]] = []
        for mod_id in selected:
            mod_state = state.mods[mod_id]
            if not mod_state.files:
                report.actions.append(PlannedAction("already_disabled", mod_id))
                continue
            for rel, entry in list(mod_state.files.items()):
                target = self._target_path(config.game_root, rel)
                backup_path = self._backup_from_entry(entry, self._backup_dir(config))
                if is_owned(
                    target,
                    Path(entry.source),
                    entry.method,
                    entry.deployed_sha256,
                    entry.deployed_size,
                ):
                    action = "remove_link_restore_backup" if entry.backup else "remove_added_file"
                    if entry.backup and (backup_path is None or not backup_path.is_file()):
                        report.errors.append(
                            f"Brakuje kopii oryginału dla {rel}; pozostawiam link w grze. "
                            "Przywróć backup z kopii zapasowej lub napraw magazyn."
                        )
                        continue
                elif not target.exists() and not target.is_symlink():
                    action = "restore_missing_target" if entry.backup else "already_missing"
                    if entry.backup and (backup_path is None or not backup_path.is_file()):
                        report.errors.append(
                            f"Brakuje pliku gry i kopii oryginału dla {rel}. "
                            "Nie można bezpiecznie przywrócić wanilii."
                        )
                        continue
                else:
                    action = "preserve_foreign_file"
                    report.conflicts.append(
                        f"Konflikt {rel}: plik w grze nie należy już do narzędzia. "
                        "Pozostawiam go bez zmian i nie przywracam na niego starego backupu."
                    )
                if action in {"remove_link_restore_backup", "restore_missing_target"} and backup_path:
                    try:
                        self._verify_backup_path(
                            backup_path, entry.backup_sha256, entry.backup_size
                        )
                    except LinkOperationError as exc:
                        report.errors.append(str(exc))
                        continue
                plans.append((mod_id, rel, entry, target, action))
                report.actions.append(
                    PlannedAction(
                        action,
                        mod_id,
                        rel,
                        entry.source,
                        str(target),
                        str(backup_path) if backup_path else None,
                        entry.src_size,
                    )
                )
        return plans

    def _execute_disable(
        self,
        plans: list[tuple[str, str, FileState, Path, str]],
        state: AppState,
        config: AppConfig,
        report: OperationReport,
    ) -> None:
        if not plans:
            return
        txid = uuid.uuid4().hex
        self.store.append_journal(
            JournalEvent.create(
                op=report.operation,
                phase="plan",
                txid=txid,
                details={"files": len(plans), "game": str(config.game_root)},
            )
        )
        backup_dir = self._backup_dir(config)
        for mod_id, rel, entry, target, action in plans:
            backup_path = self._backup_from_entry(entry, backup_dir)
            details = {"entry": entry.to_dict(), "action": action}
            self.store.append_journal(
                JournalEvent.create(
                    op=report.operation,
                    phase="begin",
                    txid=txid,
                    mod=mod_id,
                    file=rel,
                    target=str(target),
                    source=entry.source,
                    backup=str(backup_path) if backup_path else None,
                    method=entry.method,
                    action=action,
                    details=details,
                )
            )
            try:
                if action in {"remove_link_restore_backup", "restore_missing_target"} and backup_path:
                    self._assert_backup_path_safe(backup_path, backup_dir)
                    self._verify_backup_path(
                        backup_path,
                        entry.backup_sha256,
                        entry.backup_size,
                    )
                if action in {"remove_link_restore_backup", "remove_added_file"}:
                    if not remove_if_owned(
                        target,
                        entry.source,
                        entry.method,
                        entry.deployed_sha256,
                        entry.deployed_size,
                    ):
                        report.conflicts.append(
                            f"Plik {rel} zmienił się po planie; pozostawiam go bez zmian."
                        )
                        continue
                    self.store.append_journal(
                        JournalEvent.create(
                            op=report.operation,
                            phase="target_removed",
                            txid=txid,
                            mod=mod_id,
                            file=rel,
                            target=str(target),
                            source=entry.source,
                            backup=str(backup_path) if backup_path else None,
                            method=entry.method,
                        )
                    )
                    if action == "remove_link_restore_backup" and backup_path is not None:
                        self._assert_backup_path_safe(backup_path, backup_dir)
                        self._verify_backup_path(
                            backup_path, entry.backup_sha256, entry.backup_size
                        )
                        copy_file_atomic(
                            backup_path,
                            target,
                            overwrite=False,
                            expected_sha256=entry.backup_sha256,
                            expected_size=entry.backup_size,
                        )
                        self.store.append_journal(
                            JournalEvent.create(
                                op=report.operation,
                                phase="backup_restored",
                                txid=txid,
                                mod=mod_id,
                                file=rel,
                                target=str(target),
                                backup=str(backup_path),
                            )
                        )
                elif action == "restore_missing_target" and backup_path is not None:
                    self._assert_backup_path_safe(backup_path, backup_dir)
                    self._verify_backup_path(
                        backup_path, entry.backup_sha256, entry.backup_size
                    )
                    copy_file_atomic(
                        backup_path,
                        target,
                        overwrite=False,
                        expected_sha256=entry.backup_sha256,
                        expected_size=entry.backup_size,
                    )
                    self.store.append_journal(
                        JournalEvent.create(
                            op=report.operation,
                            phase="backup_restored",
                            txid=txid,
                            mod=mod_id,
                            file=rel,
                            target=str(target),
                            backup=str(backup_path),
                        )
                    )
                elif action == "preserve_foreign_file":
                    if target.is_symlink():
                        report.warnings.append(
                            f"Pozostawiono obcy symlink {target} bez podążania za jego celem."
                        )
                    else:
                        conflict_path = self._save_conflict(target, rel, backup_dir)
                        report.warnings.append(
                            f"Zapisano dodatkową kopię konfliktu: {conflict_path}. "
                            "Oryginalny plik w grze pozostał nietknięty."
                        )
                    if entry.backup:
                        state.orphaned_backups.append(entry.backup)
                mod_state = state.mods.get(mod_id)
                if mod_state:
                    mod_state.files.pop(rel, None)
                    if not mod_state.files:
                        state.mods.pop(mod_id, None)
                self.store.save_state(state)
                self.store.append_journal(
                    JournalEvent.create(
                        op=report.operation,
                        phase="done",
                        txid=txid,
                        mod=mod_id,
                        file=rel,
                        target=str(target),
                        backup=str(backup_path) if backup_path else None,
                        action=action,
                    )
                )
                report.files_changed += 1
            except (OSError, LinkOperationError, StateError) as exc:
                if isinstance(exc, LinkOperationError) and exc.requires_privilege:
                    report.privilege_required = True
                report.errors.append(
                    f"Nie udało się wyłączyć {rel}: {exc}. "
                    "Pozostałe pliki pozostają zapisane w stanie; ponów disable lub uruchom status."
                )
                break
        self._cleanup_created_dirs(state, config.game_root)
        self.store.save_state(state)
        self.store.append_journal(
            JournalEvent.create(
                op=report.operation,
                phase="commit",
                txid=txid,
                details={"disabled": report.files_changed, "conflicts": len(report.conflicts)},
            )
        )

    def _build_status(
        self,
        scan: ScanResult,
        state: AppState,
        config: AppConfig,
    ) -> StatusReport:
        report = StatusReport()
        self._append_scan_issues(scan, report)
        assert config.game_root is not None
        scanned_by_id = {mod.mod_id: mod for mod in scan.mods}
        for mod in scan.mods:
            mod_state = state.mods.get(mod.mod_id)
            warnings = [issue.message for issue in mod.issues]
            if mod_state is None or not mod_state.files:
                current_status = "wyłączony"
                file_count = len(mod.files)
                broken_count = 0
            else:
                file_count = len(mod_state.files)
                good = 0
                broken = 0
                for rel, entry in mod_state.files.items():
                    target = self._target_path(config.game_root, rel)
                    if is_owned(
                        target,
                        Path(entry.source),
                        entry.method,
                        entry.deployed_sha256,
                        entry.deployed_size,
                    ):
                        good += 1
                        try:
                            source_digest = digest_file(entry.source)
                            if source_digest.sha256 != entry.src_sha256:
                                warnings.append(
                                    f"Źródło zmienione od deployu: {entry.source}; wykonaj ponowny deploy."
                                )
                        except LinkOperationError:
                            warnings.append(f"Nie można odczytać źródła moda: {entry.source}")
                    else:
                        broken += 1
                broken_count = broken
                if broken == 0:
                    current_status = "WŁĄCZONY"
                elif good:
                    current_status = "CZĘŚCIOWY"
                else:
                    current_status = "ZERWANY"
            report.mods.append(
                ModStatus(
                    mod_id=mod.mod_id,
                    name=mod.display_name,
                    category=mod.category,
                    status=current_status,
                    file_count=file_count,
                    broken_count=broken_count,
                    warnings=tuple(dict.fromkeys(warnings)),
                )
            )
        for mod_id, mod_state in state.mods.items():
            if mod_id in scanned_by_id:
                continue
            report.mods.append(
                ModStatus(
                    mod_id=mod_id,
                    name=mod_state.display_name or Path(mod_state.source_root).name or mod_id,
                    category="",
                    status="ZERWANY",
                    file_count=len(mod_state.files),
                    broken_count=len(mod_state.files),
                    warnings=("Modu nie ma już w bibliotece; wdrożone pliki wymagają ręcznego sprawdzenia.",),
                )
            )
        report.mods.sort(key=lambda item: (item.category.casefold(), item.name.casefold()))
        return report

    def _select_mods(
        self,
        scan: ScanResult,
        state: AppState,
        names: list[str] | None,
        repair: bool,
        report: OperationReport,
    ) -> list[Mod]:
        if repair and names is None:
            requested = [mod_id for mod_id in state.mods]
            if not requested:
                report.warnings.append("Nie ma włączonych modów wymagających naprawy.")
                return []
            names = requested
        if not names:
            report.errors.append("Nie wskazano nazw modów do włączenia.")
            return []
        selected: list[Mod] = []
        for requested in names:
            token = requested.casefold()
            matches = [
                mod
                for mod in scan.mods
                if token
                in {
                    mod.mod_id.casefold(),
                    mod.name.casefold(),
                    mod.display_name.casefold(),
                }
            ]
            if len(matches) > 1:
                report.errors.append(
                    f"Nazwa moda jest niejednoznaczna: {requested}. Użyj identyfikatora folderu: "
                    + ", ".join(mod.mod_id for mod in matches)
                )
            elif not matches:
                report.errors.append(
                    f"Nie znaleziono moda `{requested}` w bibliotece. Uruchom `scan` i sprawdź nazwę."
                )
            elif matches[0] not in selected:
                selected.append(matches[0])
        return selected

    def _state_mod_ids(
        self,
        state: AppState,
        names: Iterable[str] | None,
        report: OperationReport,
    ) -> list[str]:
        if names is None:
            return list(state.mods)
        requested_names = list(names)
        selected: list[str] = []
        for requested in requested_names:
            token = requested.casefold()
            matches = [
                mod_id
                for mod_id, mod_state in state.mods.items()
                if token == mod_id.casefold()
                or token == Path(mod_state.source_root).name.casefold()
                or token == mod_state.display_name.casefold()
            ]
            if len(matches) > 1:
                report.errors.append(
                    f"Nazwa moda jest niejednoznaczna: {requested}. Użyj pełnej ścieżki ID."
                )
            elif not matches:
                report.actions.append(
                    PlannedAction("already_disabled", requested, note="Mod nie ma wdrożonych plików.")
                )
            elif matches[0] not in selected:
                selected.append(matches[0])
        return selected

    def _owners(self, state: AppState) -> dict[str, list[tuple[str, FileState]]]:
        owners: dict[str, list[tuple[str, FileState]]] = {}
        for mod_id, mod_state in state.mods.items():
            for rel, entry in mod_state.files.items():
                owners.setdefault(rel.casefold(), []).append((mod_id, entry))
        return owners

    def _check_backup_space(
        self,
        planned: list[_PlannedFile],
        config: AppConfig,
        report: OperationReport,
    ) -> None:
        required = sum(item.original_digest.size for item in planned if item.backup_needs_copy and item.original_digest)
        if required <= 0:
            return
        backup_dir = self._backup_dir(config)
        existing = self._nearest_existing(backup_dir)
        try:
            free = shutil.disk_usage(existing).free
        except OSError as exc:
            report.warnings.append(f"Nie mogę sprawdzić wolnego miejsca dla backupów: {exc}")
            return
        if free < required:
            report.errors.append(
                f"Za mało miejsca na kopie zapasowe: potrzeba około {required} B, "
                f"wolne jest {free} B. Zwolnij miejsce albo wybierz inny magazyn backupów."
            )

    def _choose_backup(
        self,
        backup_dir: Path,
        target_rel: str,
        original_digest: FileDigest,
    ) -> tuple[Path, str, bool]:
        relative = PurePosixPath("files", target_rel)
        candidate = backup_dir.joinpath(*relative.parts)
        self._assert_backup_path_safe(candidate, backup_dir)
        if candidate.is_file():
            try:
                existing = digest_file(candidate)
            except LinkOperationError:
                existing = None
            if existing and existing.sha256 == original_digest.sha256 and existing.size == original_digest.size:
                return candidate, relative.as_posix(), False
            history = PurePosixPath(
                "history",
                datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8],
                target_rel,
            )
            candidate = backup_dir.joinpath(*history.parts)
            self._assert_backup_path_safe(candidate, backup_dir)
            return candidate, history.as_posix(), True
        return candidate, relative.as_posix(), True

    def _verify_backup_path(
        self,
        backup_path: Path,
        expected_sha256: str | None = None,
        expected_size: int | None = None,
    ) -> FileDigest:
        """Weryfikuje kopię przed odtworzeniem albo ponownym użyciem."""
        if not backup_path.is_file():
            raise LinkOperationError(
                f"Brakuje pliku kopii zapasowej: {backup_path}. "
                "Nie usuwam linku ani nie przywracam niepełnych danych."
            )
        digest = digest_file(backup_path)
        if expected_sha256 and digest.sha256 != expected_sha256:
            raise LinkOperationError(
                f"Hash kopii zapasowej jest niezgodny: {backup_path}. "
                "Nie przywracam uszkodzonej kopii; zachowaj ją i sprawdź backups."
            )
        if expected_size is not None and digest.size != expected_size:
            raise LinkOperationError(
                f"Rozmiar kopii zapasowej jest niezgodny: {backup_path}. "
                "Nie przywracam uszkodzonej kopii."
            )
        return digest

    def _backup_from_entry(self, entry: FileState, backup_dir: Path) -> Path | None:
        if not entry.backup:
            return None
        relative = PurePosixPath(entry.backup)
        if relative.is_absolute() or ".." in relative.parts:
            raise StateError(f"Niebezpieczna ścieżka backupu w state.json: {entry.backup}")
        candidate = backup_dir.joinpath(*relative.parts)
        self._assert_backup_path_safe(candidate, backup_dir)
        return candidate

    def _assert_backup_path_safe(self, candidate: Path, backup_dir: Path) -> None:
        """Blokuje symlinki w magazynie, które wyprowadzałyby zapis poza jego root."""
        root = backup_dir.resolve(strict=False)
        try:
            resolved = candidate.resolve(strict=False)
            if not resolved.is_relative_to(root):
                raise StateError(
                    f"Ścieżka backupu wychodzi poza magazyn: {candidate}. "
                    "Usuń podejrzany symlink i sprawdź katalog kopii."
                )
        except (OSError, RuntimeError) as exc:
            raise StateError(
                f"Nie można bezpiecznie rozwiązać ścieżki backupu {candidate}: {exc}."
            ) from exc

    def _backup_dir(self, config: AppConfig) -> Path:
        return (config.backup_dir or (self.store.config_dir / "backups")).resolve(strict=False)

    def _config(self) -> AppConfig:
        config = self.store.load_config()
        return validate_config(
            config,
            default_backup_dir=self.store.config_dir / "backups",
        )

    def _scan(self, config: AppConfig) -> ScanResult:
        assert config.library_dir is not None
        return scan_library(config.library_dir)

    def _check_game_running(self, config: AppConfig, force_while_running: bool) -> None:
        if config.block_while_game_running and not force_while_running and game_is_running():
            raise PathValidationError(
                "Forza Horizon 6 jest uruchomiona; wstrzymuję operację, aby nie uszkodzić plików. "
                "Zamknij grę i spróbuj ponownie. Tylko CLI umożliwia świadome --force-while-running."
            )

    def _target_path(self, game_root: Path, target_rel: str) -> Path:
        relative = PurePosixPath(target_rel)
        if relative.is_absolute() or not relative.parts or ".." in relative.parts:
            raise PathValidationError(f"Niebezpieczna ścieżka docelowa moda: {target_rel}")
        target = game_root.joinpath(*relative.parts)
        resolved = target.resolve(strict=False)
        if not resolved.is_relative_to(game_root.resolve()):
            raise PathValidationError(
                f"Ścieżka docelowa wychodzi poza folder gry: {target}. "
                "Usuń podejrzany symlink z instalacji i spróbuj ponownie."
            )
        return target

    def _missing_game_dirs(self, game_root: Path, parent: Path) -> list[Path]:
        missing: list[Path] = []
        current = parent
        while current != game_root and current.is_relative_to(game_root):
            if not current.exists():
                missing.append(current)
            current = current.parent
        return list(reversed(missing))

    def _create_game_dirs(self, directories: tuple[Path, ...], state: AppState) -> None:
        for directory in directories:
            directory.mkdir(exist_ok=True)
            value = str(directory)
            if value not in state.created_dirs:
                state.created_dirs.append(value)
            self.store.save_state(state)

    def _cleanup_created_dirs(self, state: AppState, game_root: Path) -> None:
        remaining: list[str] = []
        for raw_path in reversed(state.created_dirs):
            directory = Path(raw_path)
            if not directory.resolve(strict=False).is_relative_to(game_root.resolve()):
                continue
            try:
                directory.rmdir()
            except OSError:
                if directory.exists():
                    remaining.append(raw_path)
        state.created_dirs = list(reversed(remaining))

    def _media_layout_warning(
        self,
        game_root: Path,
        target_rel: str,
        report: OperationReport,
    ) -> None:
        parts = PurePosixPath(target_rel).parts
        if len(parts) < 2:
            return
        if parts[0].casefold() == "media":
            alternative = game_root.joinpath("mediapc", *parts[1:])
            if alternative.exists():
                report.warnings.append(
                    f"Mod celuje w media/{PurePosixPath(*parts[1:]).as_posix()}, ale gra ma "
                    f"{alternative}. Sprawdź, czy target powinien używać mediapc/."
                )
        elif parts[0].casefold() == "mediapc":
            alternative = game_root.joinpath("media", *parts[1:])
            if alternative.exists():
                report.warnings.append(
                    f"Mod celuje w mediapc/{PurePosixPath(*parts[1:]).as_posix()}, ale gra ma "
                    f"{alternative}. Sprawdź, czy target powinien używać media/."
                )

    def _append_scan_issues(self, scan: ScanResult, report: OperationReport | StatusReport) -> None:
        for issue in scan.issues:
            if issue.severity == "error":
                report.errors.append(issue.message)
            else:
                report.warnings.append(issue.message)
        for mod in scan.mods:
            for issue in mod.issues:
                if issue.severity == "warning":
                    report.warnings.append(issue.message)

    def _save_conflict(self, source: Path, relative: str, backup_dir: Path) -> Path:
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
        destination = backup_dir / "conflicts" / stamp
        destination = destination.joinpath(*PurePosixPath(relative).parts)
        self._assert_backup_path_safe(destination, backup_dir)
        copy_file_atomic(source, destination, overwrite=False)
        return destination

    def _recover_incomplete(self, state: AppState, config: AppConfig) -> None:
        events = self.store.read_journal()
        grouped: dict[str, list[JournalEvent]] = {}
        for event in events:
            grouped.setdefault(event.txid, []).append(event)
        for txid, transaction in grouped.items():
            if not transaction or any(
                event.phase in {"commit", "rollback", "recovered"} for event in transaction
            ):
                continue
            if not any(event.phase == "plan" for event in transaction):
                continue
            self._recover_transaction(txid, state, config, transaction)
            self.store.save_state(state)
            first = transaction[0]
            self.store.append_journal(
                JournalEvent.create(
                    op=first.op,
                    phase="recovered",
                    txid=txid,
                    details={"strategy": "self-heal", "events": len(transaction)},
                )
            )

    def _recover_transaction(
        self,
        txid: str,
        state: AppState,
        config: AppConfig,
        transaction: list[JournalEvent] | None = None,
    ) -> None:
        events = transaction or [event for event in self.store.read_journal() if event.txid == txid]
        if not events:
            return
        operation = events[0].op
        begins = [event for event in events if event.phase == "begin"]
        if operation in {"enable", "repair"}:
            for begin in reversed(begins):
                self._recover_deploy_file(begin, events, state, config)
        elif operation in {"disable", "restore"}:
            for begin in begins:
                self._recover_disable_file(begin, events, state, config)
        self._cleanup_created_dirs(state, config.game_root or Path.cwd())

    def _recover_deploy_file(
        self,
        begin: JournalEvent,
        events: list[JournalEvent],
        state: AppState,
        config: AppConfig,
    ) -> None:
        if not begin.target or not begin.file or not begin.mod:
            return
        file_events = [
            event
            for event in events
            if event.mod == begin.mod and event.file == begin.file and event.target == begin.target
        ]
        phases = {event.phase for event in file_events}
        details = begin.details
        target = Path(begin.target)
        source = Path(begin.source) if begin.source else Path()
        expected_sha256 = str(details.get("expected_sha256", ""))
        expected_size = int(details.get("expected_size", 0))
        if "original_removed" in phases and target.exists():
            if is_owned(
                target,
                source,
                begin.method or "auto",
                expected_sha256,
                expected_size,
            ):
                remove_if_owned(
                    target,
                    source,
                    begin.method or "auto",
                    expected_sha256,
                    expected_size,
                )
        previous_owner_id = details.get("previous_owner_id")
        previous_owner_data = details.get("previous_owner_entry")
        if previous_owner_id and previous_owner_data:
            previous = FileState.from_dict(previous_owner_data)
            if not target.exists() and not target.is_symlink():
                create_link(previous.source, target, previous.method)
        elif details.get("previous_mod_owned") and details.get("previous_mod_entry"):
            previous = FileState.from_dict(details["previous_mod_entry"])
            if not target.exists() and not target.is_symlink():
                create_link(previous.source, target, previous.method)
        elif details.get("previous_exists") and "original_removed" in phases:
            backup = Path(begin.backup) if begin.backup else None
            if backup is not None:
                if not backup.is_absolute():
                    raise StateError(f"Nieprawidłowa ścieżka backupu w journalu: {backup}")
                self._assert_backup_path_safe(backup, self._backup_dir(config))
            if backup and backup.is_file() and not target.exists() and not target.is_symlink():
                self._verify_backup_path(
                    backup,
                    details.get("backup_sha256"),
                    details.get("backup_size"),
                )
                copy_file_atomic(
                    backup,
                    target,
                    overwrite=False,
                    expected_sha256=details.get("backup_sha256"),
                    expected_size=details.get("backup_size"),
                )
        previous_owner_id = details.get("previous_owner_id")
        previous_owner_state = details.get("previous_owner_state")
        if previous_owner_id and isinstance(previous_owner_state, dict):
            state.mods[previous_owner_id] = ModState.from_dict(previous_owner_state)

        previous_mod_state = details.get("previous_mod_state")
        if isinstance(previous_mod_state, dict):
            state.mods[begin.mod] = ModState.from_dict(previous_mod_state)
        else:
            previous_mod_data = details.get("previous_mod_entry")
            mod_state = state.mods.get(begin.mod)
            if previous_mod_data:
                if mod_state is None:
                    mod_state = ModState(
                        source_root="",
                        moderoot_rel="",
                        deployed_at="",
                        method="auto",
                    )
                    state.mods[begin.mod] = mod_state
                mod_state.files[begin.file] = FileState.from_dict(previous_mod_data)
            elif mod_state:
                mod_state.files.pop(begin.file, None)
                if not mod_state.files:
                    state.mods.pop(begin.mod, None)

    def _recover_disable_file(
        self,
        begin: JournalEvent,
        events: list[JournalEvent],
        state: AppState,
        config: AppConfig,
    ) -> None:
        if not begin.target or not begin.file or not begin.mod:
            return
        phases = {
            event.phase
            for event in events
            if event.mod == begin.mod and event.file == begin.file and event.target == begin.target
        }
        if "target_removed" not in phases and "backup_restored" not in phases:
            return
        entry_data = begin.details.get("entry")
        if not isinstance(entry_data, dict):
            return
        entry = FileState.from_dict(entry_data)
        target = Path(begin.target)
        backup = Path(begin.backup) if begin.backup else None
        if backup is not None:
            if not backup.is_absolute():
                raise StateError(f"Nieprawidłowa ścieżka backupu w journalu: {backup}")
            self._assert_backup_path_safe(backup, self._backup_dir(config))
        if target.exists() and is_owned(
            target,
            entry.source,
            entry.method,
            entry.deployed_sha256,
            entry.deployed_size,
        ):
            remove_if_owned(
                target,
                entry.source,
                entry.method,
                entry.deployed_sha256,
                entry.deployed_size,
            )
        if not target.exists() and backup and backup.is_file():
            self._verify_backup_path(backup, entry.backup_sha256, entry.backup_size)
            copy_file_atomic(
                backup,
                target,
                overwrite=False,
                expected_sha256=entry.backup_sha256,
                expected_size=entry.backup_size,
            )
        mod_state = state.mods.get(begin.mod)
        if mod_state:
            mod_state.files.pop(begin.file, None)
            if not mod_state.files:
                state.mods.pop(begin.mod, None)

    def _nearest_existing(self, path: Path) -> Path:
        current = path
        while not current.exists() and current != current.parent:
            current = current.parent
        return current
