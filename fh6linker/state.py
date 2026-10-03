"""Konfiguracja, stan atomowy, dziennik WAL i blokada jednej instancji."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterator

APP_NAME = "FH6AddonLinker"
SCHEMA_VERSION = 1


class StateError(RuntimeError):
    """Błąd odczytu lub zapisu trwałego stanu aplikacji."""


@dataclass
class AppConfig:
    """Ustawienia zapisane w config.json."""

    game_root: Path | None = None
    library_dir: Path | None = None
    backup_dir: Path | None = None
    method: str = "auto"
    block_while_game_running: bool = True
    last_scan: str | None = None
    schema: int = SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        """Konwertuje ścieżki na postać zgodną ze schematem JSON."""
        return {
            "schema": self.schema,
            "game_root": str(self.game_root) if self.game_root else None,
            "library_dir": str(self.library_dir) if self.library_dir else None,
            "backup_dir": str(self.backup_dir) if self.backup_dir else None,
            "method": self.method,
            "block_while_game_running": self.block_while_game_running,
            "last_scan": self.last_scan,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AppConfig:
        """Tworzy konfigurację z odczytanego obiektu JSON."""
        schema = int(data.get("schema", SCHEMA_VERSION))
        if schema != SCHEMA_VERSION:
            raise StateError(
                f"Nieobsługiwana wersja konfiguracji ({schema}). "
                "Zrób kopię katalogu konfiguracji i zaktualizuj aplikację."
            )
        return cls(
            game_root=Path(data["game_root"]) if data.get("game_root") else None,
            library_dir=Path(data["library_dir"]) if data.get("library_dir") else None,
            backup_dir=Path(data["backup_dir"]) if data.get("backup_dir") else None,
            method=str(data.get("method", "auto")),
            block_while_game_running=bool(data.get("block_while_game_running", True)),
            last_scan=data.get("last_scan"),
            schema=schema,
        )


@dataclass
class FileState:
    """Informacje potrzebne do zweryfikowania i cofnięcia jednego pliku."""

    method: str
    source: str
    src_sha256: str
    src_size: int
    src_mtime: float
    backup: str | None
    deployed_sha256: str
    deployed_size: int
    backup_sha256: str | None = None
    backup_size: int | None = None
    backup_mtime: float | None = None

    def to_dict(self) -> dict[str, Any]:
        """Zwraca pola zapisane dla pliku w state.json."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FileState:
        """Odtwarza wpis pliku ze stanu."""
        return cls(
            method=str(data.get("method", "hardlink")),
            source=str(data.get("source", "")),
            src_sha256=str(data.get("src_sha256", "")),
            src_size=int(data.get("src_size", 0)),
            src_mtime=float(data.get("src_mtime", 0.0)),
            backup=str(data["backup"]) if data.get("backup") else None,
            deployed_sha256=str(data.get("deployed_sha256", "")),
            deployed_size=int(data.get("deployed_size", 0)),
            backup_sha256=(
                str(data["backup_sha256"]) if data.get("backup_sha256") else None
            ),
            backup_size=(int(data["backup_size"]) if data.get("backup_size") is not None else None),
            backup_mtime=(
                float(data["backup_mtime"]) if data.get("backup_mtime") is not None else None
            ),
        )


@dataclass
class ModState:
    """Stan wdrożenia pojedynczego moda."""

    source_root: str
    moderoot_rel: str
    deployed_at: str
    method: str
    display_name: str = ""
    files: dict[str, FileState] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Zwraca reprezentację zgodną ze schematem state.json."""
        return {
            "source_root": self.source_root,
            "moderoot_rel": self.moderoot_rel,
            "deployed_at": self.deployed_at,
            "method": self.method,
            "display_name": self.display_name,
            "files": {name: info.to_dict() for name, info in self.files.items()},
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ModState:
        """Odtwarza stan moda."""
        return cls(
            source_root=str(data.get("source_root", "")),
            moderoot_rel=str(data.get("moderoot_rel", "")),
            deployed_at=str(data.get("deployed_at", "")),
            method=str(data.get("method", "auto")),
            display_name=str(data.get("display_name", Path(str(data.get("source_root", ""))).name)),
            files={
                str(name): FileState.from_dict(info)
                for name, info in data.get("files", {}).items()
            },
        )


@dataclass
class AppState:
    """Źródło prawdy potrzebne do bezpiecznego rollbacku."""

    mods: dict[str, ModState] = field(default_factory=dict)
    created_dirs: list[str] = field(default_factory=list)
    orphaned_backups: list[str] = field(default_factory=list)
    game_version_seen: str | None = None
    schema: int = SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        """Zwraca state.json w przenośnym formacie."""
        return {
            "schema": self.schema,
            "game_version_seen": self.game_version_seen,
            "mods": {name: mod.to_dict() for name, mod in self.mods.items()},
            "created_dirs": list(self.created_dirs),
            "orphaned_backups": list(self.orphaned_backups),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AppState:
        """Odtwarza stan z JSON i odrzuca niezgodny schemat."""
        schema = int(data.get("schema", SCHEMA_VERSION))
        if schema != SCHEMA_VERSION:
            raise StateError(
                f"Nieobsługiwana wersja stanu ({schema}). "
                "Zachowaj kopię state.json i uruchom zgodną wersję aplikacji."
            )
        return cls(
            mods={
                str(name): ModState.from_dict(mod)
                for name, mod in data.get("mods", {}).items()
            },
            created_dirs=[str(path) for path in data.get("created_dirs", [])],
            orphaned_backups=[
                str(path) for path in data.get("orphaned_backups", [])
            ],
            game_version_seen=data.get("game_version_seen"),
            schema=schema,
        )


@dataclass(frozen=True)
class JournalEvent:
    """Pojedynczy wpis dziennika write-ahead."""

    ts: str
    op: str
    phase: str
    txid: str
    mod: str | None = None
    file: str | None = None
    target: str | None = None
    source: str | None = None
    backup: str | None = None
    method: str | None = None
    action: str | None = None
    details: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        *,
        op: str,
        phase: str,
        txid: str,
        mod: str | None = None,
        file: str | None = None,
        target: str | None = None,
        source: str | None = None,
        backup: str | None = None,
        method: str | None = None,
        action: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> JournalEvent:
        """Buduje zdarzenie z aktualnym znacznikiem czasu."""
        return cls(
            ts=datetime.now(UTC).astimezone().isoformat(timespec="seconds"),
            op=op,
            phase=phase,
            txid=txid,
            mod=mod,
            file=file,
            target=target,
            source=source,
            backup=backup,
            method=method,
            action=action,
            details=details or {},
        )

    def to_dict(self) -> dict[str, Any]:
        """Konwertuje zdarzenie do jednej linii JSONL."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> JournalEvent:
        """Odtwarza zdarzenie z JSONL."""
        return cls(
            ts=str(data.get("ts", "")),
            op=str(data.get("op", "")),
            phase=str(data.get("phase", "")),
            txid=str(data.get("txid", "legacy")),
            mod=data.get("mod"),
            file=data.get("file"),
            target=data.get("target"),
            source=data.get("source"),
            backup=data.get("backup"),
            method=data.get("method"),
            action=data.get("action"),
            details=dict(data.get("details", {})),
        )


def default_config_dir() -> Path:
    """Zwraca standardowy katalog ustawień dla bieżącego systemu."""
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / APP_NAME


class StateStore:
    """Odczyt/zapis konfiguracji, stanu, journala i blokady instancji."""

    def __init__(self, config_dir: Path | None = None) -> None:
        configured = os.environ.get("FH6LINKER_CONFIG_DIR")
        selected_dir = config_dir
        if selected_dir is None and configured:
            selected_dir = Path(configured)
        self.config_dir = (selected_dir or default_config_dir()).expanduser().absolute()
        self.config_path = self.config_dir / "config.json"
        self.state_path = self.config_dir / "state.json"
        self.journal_path = self.config_dir / "journal.jsonl"
        self.lock_path = self.config_dir / "fh6linker.lock"

    def load_config(self) -> AppConfig:
        """Ładuje konfigurację albo zwraca ustawienia początkowe."""
        return self._read_json(self.config_path, AppConfig.from_dict, AppConfig())

    def save_config(self, config: AppConfig) -> None:
        """Zapisuje konfigurację atomowo."""
        self._write_json(self.config_path, config.to_dict())

    def load_state(self) -> AppState:
        """Ładuje stan; przy uszkodzonym pliku próbuje kopię `.bak`."""
        try:
            return self._read_json(self.state_path, AppState.from_dict, AppState())
        except StateError as original_error:
            backup_path = self.state_path.with_suffix(self.state_path.suffix + ".bak")
            if not backup_path.exists():
                raise original_error
            try:
                return self._read_json(backup_path, AppState.from_dict, AppState())
            except StateError:
                raise original_error

    def save_state(self, state: AppState) -> None:
        """Zapisuje stan atomowo i zachowuje poprzednią wersję jako `.bak`."""
        self._write_json(self.state_path, state.to_dict())

    def append_journal(self, event: JournalEvent) -> None:
        """Dopisuje i utrwala zamiar/wynik operacji w dzienniku JSONL."""
        self.config_dir.mkdir(parents=True, exist_ok=True)
        try:
            with self.journal_path.open("a", encoding="utf-8", newline="\n") as stream:
                stream.write(json.dumps(event.to_dict(), ensure_ascii=False) + "\n")
                stream.flush()
                os.fsync(stream.fileno())
        except OSError as exc:
            raise StateError(
                f"Nie mogę zapisać dziennika operacji: {exc}. "
                "Sprawdź miejsce i uprawnienia do katalogu konfiguracji."
            ) from exc

    def read_journal(self) -> list[JournalEvent]:
        """Czyta dziennik, tolerując wyłącznie niekompletny ostatni wiersz."""
        if not self.journal_path.exists():
            return []
        try:
            lines = self.journal_path.read_text(encoding="utf-8").splitlines()
        except OSError as exc:
            raise StateError(f"Nie mogę odczytać journala: {exc}.") from exc
        events: list[JournalEvent] = []
        for index, line in enumerate(lines):
            if not line.strip():
                continue
            try:
                events.append(JournalEvent.from_dict(json.loads(line)))
            except (json.JSONDecodeError, TypeError, ValueError) as exc:
                if index == len(lines) - 1:
                    break
                raise StateError(
                    f"Journal jest uszkodzony w wierszu {index + 1}. "
                    "Zachowaj jego kopię przed dalszymi operacjami."
                ) from exc
        return events

    @contextmanager
    def lock(self) -> Iterator[None]:
        """Zakłada blokadę procesu; usuwa wyłącznie blokadę własnego PID."""
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self._acquire_lock()
        try:
            yield
        finally:
            try:
                data = json.loads(self.lock_path.read_text(encoding="utf-8"))
                if int(data.get("pid", -1)) == os.getpid():
                    self.lock_path.unlink(missing_ok=True)
            except (OSError, ValueError, json.JSONDecodeError):
                pass

    def _acquire_lock(self) -> None:
        """Tworzy blokadę atomowo lub usuwa blokadę martwego procesu."""
        payload = json.dumps({"pid": os.getpid(), "created_at": datetime.now(UTC).isoformat()})
        for _attempt in range(2):
            try:
                descriptor = os.open(
                    self.lock_path,
                    os.O_CREAT | os.O_EXCL | os.O_WRONLY,
                    0o600,
                )
                with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                    stream.write(payload)
                    stream.flush()
                    os.fsync(stream.fileno())
                return
            except FileExistsError:
                if not self._lock_is_stale():
                    raise StateError(
                        "FH6 Addon Linker jest już uruchomiony. "
                        "Zamknij drugie okno lub sprawdź plik blokady w katalogu konfiguracji."
                    )
                self.lock_path.unlink(missing_ok=True)
            except OSError as exc:
                raise StateError(
                    f"Nie mogę założyć blokady operacji: {exc}. "
                    "Sprawdź uprawnienia katalogu konfiguracji."
                ) from exc
        raise StateError("Nie udało się uzyskać blokady; spróbuj ponownie.")

    def _lock_is_stale(self) -> bool:
        """Sprawdza PID, a dla nieczytelnego locka jego wiek."""
        try:
            data = json.loads(self.lock_path.read_text(encoding="utf-8"))
            pid = int(data.get("pid", -1))
        except (OSError, ValueError, json.JSONDecodeError):
            try:
                return datetime.now().timestamp() - self.lock_path.stat().st_mtime > 24 * 3600
            except OSError:
                return False
        if pid <= 0:
            return True
        if os.name == "nt":
            try:
                result = subprocess.run(
                    ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                    check=False,
                )
                return f'"{pid}"' not in result.stdout
            except (OSError, subprocess.SubprocessError):
                return False
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return True
        except PermissionError:
            return False
        except OSError:
            return False
        return False

    def _read_json(self, path: Path, factory: Any, default: Any) -> Any:
        if not path.exists():
            return default
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                raise TypeError("korzeń JSON nie jest obiektem")
            return factory(data)
        except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
            raise StateError(
                f"Nie mogę odczytać {path.name}: {exc}. "
                "Nie kontynuuję, aby nie uszkodzić stanu; sprawdź plik i jego kopię `.bak`."
            ) from exc

    def _write_json(self, path: Path, data: dict[str, Any]) -> None:
        self.config_dir.mkdir(parents=True, exist_ok=True)
        temporary: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                "w",
                encoding="utf-8",
                newline="\n",
                dir=self.config_dir,
                prefix=f".{path.name}.",
                suffix=".tmp",
                delete=False,
            ) as stream:
                temporary = Path(stream.name)
                json.dump(data, stream, ensure_ascii=False, indent=2)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            if path.exists():
                backup_path = path.with_suffix(path.suffix + ".bak")
                shutil.copy2(path, backup_path)
            os.replace(temporary, path)
        except OSError as exc:
            raise StateError(
                f"Nie mogę atomowo zapisać {path.name}: {exc}. "
                "Sprawdź wolne miejsce i uprawnienia katalogu konfiguracji."
            ) from exc
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
