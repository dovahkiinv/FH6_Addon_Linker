"""Wspólne fixture'y z atrapą gry, biblioteką modów i izolowanym stanem."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from fh6linker.engine import LinkerEngine
from fh6linker.state import StateStore


@dataclass(frozen=True)
class FakeProject:
    """Ścieżki testowej gry i przygotowanego środowiska aplikacji."""

    root: Path
    game_root: Path
    library_dir: Path
    backup_dir: Path
    config_dir: Path
    store: StateStore
    engine: LinkerEngine


@pytest.fixture

def fake_project(tmp_path: Path) -> FakeProject:
    """Tworzy fałszywą instalację FH6 i trzy mody testowe."""
    game_root = tmp_path / "game"
    library_dir = tmp_path / "mods"
    backup_dir = tmp_path / "backups"
    config_dir = tmp_path / "config"

    (game_root / "media" / "Audio" / "FMODBanks").mkdir(parents=True)
    (game_root / "mediapc" / "Textures").mkdir(parents=True)
    (game_root / "forzahorizon6.exe").write_bytes(b"fake game executable")
    (game_root / "media" / "Audio" / "FMODBanks" / "engine.bank").write_bytes(
        b"vanilla audio bytes\x00"
    )
    (game_root / "mediapc" / "Textures" / "sky.dds").write_bytes(b"vanilla texture")

    _write_mod(
        library_dir / "Audio" / "Engine Mod",
        "media/Audio/FMODBanks/engine.bank",
        b"modded engine audio\x00",
    )
    _write_mod(
        library_dir / "Audio" / "New Bank",
        "media/Audio/FMODBanks/new.bank",
        b"new audio bank",
    )
    _write_mod(
        library_dir / "Graphics" / "Sky Mod",
        "mediapc/Textures/sky.dds",
        b"modded sky texture",
    )

    store = StateStore(config_dir)
    engine = LinkerEngine(store)
    engine.configure(game_root, library_dir, backup_dir, method="auto")
    return FakeProject(
        root=tmp_path,
        game_root=game_root,
        library_dir=library_dir,
        backup_dir=backup_dir,
        config_dir=config_dir,
        store=store,
        engine=engine,
    )


def _write_mod(mod_root: Path, target_rel: str, content: bytes) -> None:
    parts = Path(target_rel).parts
    marker = parts[0]
    source = mod_root.joinpath(*parts)
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(content)
