"""Detekcja instalacji gry, wolumenów i walidacja dozwolonych ścieżek."""

from __future__ import annotations

import os
import re
import string
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .state import AppConfig

GAME_EXECUTABLE = "forzahorizon6.exe"
GAME_DIRECTORY_NAMES = (
    "ForzaHorizon6",
    "Forza Horizon 6",
    "ForzaHorizon6PremiumEdition",
)


class PathValidationError(ValueError):
    """Ścieżka jest nieprawidłowa lub narusza granice bezpieczeństwa."""


@dataclass(frozen=True)
class GameInstall:
    """Wykryta instalacja gry wraz z opisem źródła."""

    path: Path
    source: str


def normalize_path(path: str | Path) -> Path:
    """Rozwija `~` i zwraca bezwzględną ścieżkę bez wymuszania istnienia."""
    return Path(path).expanduser().absolute()


def validate_game_root(path: str | Path) -> Path:
    """Sprawdza istnienie katalogu gry i rozpoznawalnego pliku/katalogu."""
    game_root = normalize_path(path)
    if not game_root.exists() or not game_root.is_dir():
        raise PathValidationError(
            f"Folder gry nie istnieje lub nie jest katalogiem: {game_root}. "
            "Wskaż folder instalacyjny Forza Horizon 6."
        )
    names = {child.name.casefold() for child in game_root.iterdir()}
    valid = GAME_EXECUTABLE.casefold() in names or any(
        marker in names for marker in ("media", "mediapc")
    )
    if not valid:
        raise PathValidationError(
            f"Brak forzahorizon6.exe i folderów media/mediapc w: {game_root}. "
            "Wskaż właściwy folder instalacyjny gry, a nie folder biblioteki Steam ani skrót."
        )
    return game_root.resolve()


def validate_library_dir(path: str | Path) -> Path:
    """Sprawdza, czy biblioteka jest istniejącym katalogiem."""
    library_dir = normalize_path(path)
    if not library_dir.exists() or not library_dir.is_dir():
        raise PathValidationError(
            f"Folder biblioteki modów nie istnieje lub nie jest katalogiem: {library_dir}. "
            "Utwórz folder i wskaż go ponownie."
        )
    return library_dir.resolve()


def validate_config_paths(
    game_root: str | Path,
    library_dir: str | Path,
    backup_dir: str | Path | None = None,
) -> tuple[Path, Path, Path | None]:
    """Waliduje grę, bibliotekę i opcjonalny katalog kopii zapasowych."""
    game = validate_game_root(game_root)
    library = validate_library_dir(library_dir)
    if _contains(game, library):
        raise PathValidationError(
            f"Biblioteka modów leży w katalogu gry: {library}. "
            "Wybierz folder poza instalacją gry, aby skan nie traktował stagingu jako źródła."
        )
    if _contains(library, game):
        raise PathValidationError(
            f"Katalog gry leży wewnątrz biblioteki modów: {game}. "
            "Przenieś bibliotekę poza folder gry i skonfiguruj ścieżki ponownie."
        )
    backup: Path | None = None
    if backup_dir is not None:
        backup = normalize_path(backup_dir).resolve(strict=False)
        overlaps_game = _contains(game, backup) or _contains(backup, game)
        overlaps_library = _contains(library, backup) or _contains(backup, library)
        if overlaps_game or overlaps_library:
            raise PathValidationError(
                f"Magazyn kopii nie może pokrywać się z grą ani biblioteką: {backup}. "
                "Wybierz osobny katalog, najlepiej na dysku z wolnym miejscem."
            )
    return game, library, backup


def validate_config(
    config: AppConfig,
    *,
    default_backup_dir: str | Path | None = None,
) -> AppConfig:
    """Waliduje pełną konfigurację przed operacją na plikach."""
    if config.method not in {"auto", "hardlink", "symlink", "copy"}:
        raise PathValidationError(
            f"Nieobsługiwana metoda linkowania w config.json: {config.method}. "
            "Popraw ustawienie na auto, hardlink, symlink lub copy."
        )
    if config.game_root is None or config.library_dir is None:
        raise PathValidationError(
            "Nie skonfigurowano folderu gry i biblioteki. "
            "Uruchom `fh6linker set --game PATH --library PATH`."
        )
    game, library, backup = validate_config_paths(
        config.game_root, config.library_dir, config.backup_dir
    )
    backup_to_check = backup or (
        normalize_path(default_backup_dir).resolve(strict=False)
        if default_backup_dir is not None
        else None
    )
    if backup_to_check and (
        _contains(game, backup_to_check)
        or _contains(backup_to_check, game)
        or _contains(library, backup_to_check)
        or _contains(backup_to_check, library)
    ):
        raise PathValidationError(
            f"Magazyn kopii nie może pokrywać się z grą ani biblioteką: {backup_to_check}. "
            "Wybierz osobny katalog, najlepiej na dysku z wolnym miejscem."
        )
    return AppConfig(
        game_root=game,
        library_dir=library,
        backup_dir=backup,
        method=config.method,
        block_while_game_running=config.block_while_game_running,
        last_scan=config.last_scan,
        schema=config.schema,
    )


def detect_game_installs() -> list[GameInstall]:
    """Szuka instalacji Steam/Xbox w typowych lokalizacjach systemu."""
    candidates: list[GameInstall] = []
    seen: set[str] = set()

    def add_candidate(path: Path, source: str) -> None:
        try:
            resolved = path.expanduser().resolve()
            key = str(resolved).casefold()
            if key not in seen and _is_game_root(resolved):
                seen.add(key)
                candidates.append(GameInstall(path=resolved, source=source))
        except OSError:
            return

    for library in _steam_libraries():
        for folder_name in GAME_DIRECTORY_NAMES:
            add_candidate(
                library / "steamapps" / "common" / folder_name,
                "Steam",
            )

    for root in _xbox_roots():
        for folder_name in GAME_DIRECTORY_NAMES:
            add_candidate(root / folder_name, "Xbox / Microsoft Store")
            add_candidate(root / "Games" / folder_name, "Xbox / Microsoft Store")
        add_candidate(root, "Xbox / Microsoft Store")

    for root in _typical_roots():
        for folder_name in GAME_DIRECTORY_NAMES:
            add_candidate(root / folder_name, "typowa lokalizacja")

    return candidates


def game_is_running() -> bool:
    """Wykrywa proces gry bez dodatkowych zależności."""
    if os.name == "nt":
        try:
            result = subprocess.run(
                ["tasklist", "/FI", f"IMAGENAME eq {GAME_EXECUTABLE}", "/FO", "CSV", "/NH"],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            return GAME_EXECUTABLE.casefold() in result.stdout.casefold()
        except (OSError, subprocess.SubprocessError):
            return False

    proc_root = Path("/proc")
    if proc_root.is_dir():
        for process_dir in proc_root.iterdir():
            if not process_dir.name.isdigit():
                continue
            for name in ("comm", "exe"):
                try:
                    process_path = process_dir / name
                    process_name = (
                        process_path.resolve().name
                        if name == "exe"
                        else process_path.read_text(encoding="utf-8", errors="ignore").strip()
                    )
                except OSError:
                    continue
                normalized = process_name.casefold()
                if normalized == GAME_EXECUTABLE or normalized.startswith("forzahorizon6."):
                    return True
        return False

    try:
        result = subprocess.run(
            ["pgrep", "-if", GAME_EXECUTABLE],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        return result.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def same_volume(first: str | Path, second: str | Path) -> bool:
    """Sprawdza, czy dwie ścieżki znajdują się na tym samym wolumenie."""
    first_path = normalize_path(first)
    second_path = normalize_path(second)
    if os.name == "nt":
        return first_path.drive.casefold() == second_path.drive.casefold()
    try:
        return first_path.stat().st_dev == second_path.stat().st_dev
    except OSError:
        first_existing = _existing_parent(first_path)
        second_existing = _existing_parent(second_path)
        try:
            return first_existing.stat().st_dev == second_existing.stat().st_dev
        except OSError:
            return False


def _steam_libraries() -> list[Path]:
    """Czyta biblioteki Steam z libraryfolders.vdf i typowych ścieżek."""
    steam_roots: list[Path] = []
    if os.name == "nt":
        for drive in string.ascii_uppercase:
            root = Path(f"{drive}:/")
            steam_roots.extend(
                [root / "Program Files (x86)" / "Steam", root / "Steam"]
            )
    else:
        home = Path.home()
        steam_roots.extend(
            [
                home / ".steam" / "steam",
                home / ".local" / "share" / "Steam",
                home / ".var" / "app" / "com.valvesoftware.Steam" / ".local" / "share" / "Steam",
            ]
        )
    if os.environ.get("STEAM_DIR"):
        steam_roots.insert(0, Path(os.environ["STEAM_DIR"]))

    libraries: list[Path] = []
    seen: set[str] = set()
    for steam_root in steam_roots:
        for library in _read_library_folders(steam_root):
            key = str(library).casefold()
            if key not in seen:
                seen.add(key)
                libraries.append(library)
    return libraries


def _read_library_folders(steam_root: Path) -> list[Path]:
    """Parsuje współczesny i starszy format pliku libraryfolders.vdf."""
    libraries = [steam_root]
    vdf_path = steam_root / "steamapps" / "libraryfolders.vdf"
    if not vdf_path.is_file():
        return libraries
    try:
        text = vdf_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return libraries
    for match in re.finditer(r'"path"\s*"((?:[^"\\]|\\.)*)"', text):
        raw = match.group(1).replace("\\\\", "\\")
        raw = raw.replace("\\", "/") if os.name != "nt" else raw
        path = Path(raw)
        if path.is_absolute():
            libraries.append(path)
    for match in re.finditer(r'"\d+"\s*"([A-Za-z]:\\\\[^"\r\n]+)"', text):
        libraries.append(Path(match.group(1).replace("\\\\", "\\")))
    return libraries


def _xbox_roots() -> list[Path]:
    """Zwraca katalogi XboxGames oraz ścieżki podane przez zmienne środowiska."""
    roots: list[Path] = []
    for variable in ("ProgramW6432", "ProgramFiles", "ProgramFiles(x86)"):
        value = os.environ.get(variable)
        if value:
            roots.append(Path(value) / "XboxGames")
    for drive in string.ascii_uppercase if os.name == "nt" else ():
        roots.append(Path(f"{drive}:/XboxGames"))
    roots.append(Path.home() / "XboxGames")
    return roots


def _typical_roots() -> list[Path]:
    """Typowe katalogi gier, w tym lokalizacje Steam i Xbox."""
    home = Path.home()
    roots = [
        home / "Games",
        home / "Games" / "Forza Horizon 6",
        Path("/mnt/games"),
        Path("/run/media") / home.name,
    ]
    if os.name == "nt":
        roots.extend(
            Path(f"{drive}:/") / folder
            for drive in string.ascii_uppercase
            for folder in ("Games", "XboxGames", "SteamLibrary/steamapps/common")
        )
    return roots


def _is_game_root(path: Path) -> bool:
    if not path.is_dir():
        return False
    try:
        names = {child.name.casefold() for child in path.iterdir()}
    except OSError:
        return False
    return GAME_EXECUTABLE in names or bool(names.intersection({"media", "mediapc"}))


def _contains(parent: Path, child: Path) -> bool:
    """Zwraca True, gdy child jest równy parent lub leży wewnątrz niego."""
    try:
        child.relative_to(parent)
        return True
    except ValueError:
        return False


def _existing_parent(path: Path) -> Path:
    current = path
    while not current.exists() and current != current.parent:
        current = current.parent
    return current
