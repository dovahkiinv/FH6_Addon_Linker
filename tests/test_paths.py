"""Testy walidacji i wykrywania ścieżek gry."""

from __future__ import annotations

from pathlib import Path

import pytest

from fh6linker.paths import (
    PathValidationError,
    detect_game_installs,
    validate_config,
    validate_config_paths,
    validate_game_root,
)
from fh6linker.state import AppConfig


def test_invalid_game_path_has_actionable_message(tmp_path: Path) -> None:
    """Zła ścieżka podaje brakujące elementy instalacji."""
    invalid = tmp_path / "not-a-game"
    invalid.mkdir()

    with pytest.raises(PathValidationError, match="[Bb]rak forzahorizon6.exe i folderów media/mediapc"):
        validate_game_root(invalid)


def test_library_inside_game_is_rejected(fake_project: object) -> None:
    """Biblioteka nie może być częścią drzewa gry."""
    game_root = fake_project.game_root  # type: ignore[attr-defined]
    library = game_root / "mods"
    library.mkdir()

    with pytest.raises(PathValidationError, match="Biblioteka modów leży w katalogu gry"):
        validate_config_paths(game_root, library)


def test_default_backup_cannot_overlap_game_or_library(fake_project: object) -> None:
    """Odrzuca również magazyn domyślny wskazany przez katalog konfiguracji."""
    game_root = fake_project.game_root  # type: ignore[attr-defined]
    library = fake_project.library_dir  # type: ignore[attr-defined]
    config = AppConfig(game_root=game_root, library_dir=library)

    with pytest.raises(PathValidationError, match="Magazyn kopii nie może pokrywać się"):
        validate_config(config, default_backup_dir=game_root / "app-config/backups")
    with pytest.raises(PathValidationError, match="Magazyn kopii nie może pokrywać się"):
        validate_config(config, default_backup_dir=library / "app-config/backups")


def test_backup_symlink_cannot_alias_game_folder(fake_project: object, tmp_path: Path) -> None:
    """Weryfikacja backupu uwzględnia istniejące symlinki w ścieżce."""
    game_root = fake_project.game_root  # type: ignore[attr-defined]
    library = fake_project.library_dir  # type: ignore[attr-defined]
    backup_alias = tmp_path / "backup-alias"
    try:
        backup_alias.symlink_to(game_root, target_is_directory=True)
    except OSError:
        pytest.skip("System nie pozwala tworzyć symlinków katalogów bez dodatkowych uprawnień")

    with pytest.raises(PathValidationError, match="Magazyn kopii nie może pokrywać się"):
        validate_config_paths(game_root, library, backup_alias / "backups")


def test_steam_libraryfolders_vdf_autodetects_install(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    steam_root = tmp_path / "Steam"
    library = tmp_path / "SteamLibrary"
    game = library / "steamapps/common/ForzaHorizon6"
    (steam_root / "steamapps").mkdir(parents=True)
    (game / "media").mkdir(parents=True)
    (game / "forzahorizon6.exe").write_bytes(b"fake exe")
    (steam_root / "steamapps/libraryfolders.vdf").write_text(
        '"libraryfolders" { "0" { "path" "'
        + str(steam_root).replace("\\", "\\\\")
        + '" } "1" { "path" "'
        + str(library).replace("\\", "\\\\")
        + '" } }',
        encoding="utf-8",
    )
    monkeypatch.setenv("STEAM_DIR", str(steam_root))

    candidates = detect_game_installs()

    assert any(candidate.path == game.resolve() for candidate in candidates)


def test_game_inside_library_is_rejected(fake_project: object) -> None:
    """Instalacja gry nie może znajdować się wewnątrz biblioteki."""
    parent = fake_project.root / "parent"  # type: ignore[attr-defined]
    game = parent / "game"
    library = parent / "library"
    (game / "media").mkdir(parents=True)
    library.mkdir(parents=True)

    with pytest.raises(PathValidationError, match="Katalog gry leży wewnątrz biblioteki"):
        validate_config_paths(game, parent)
