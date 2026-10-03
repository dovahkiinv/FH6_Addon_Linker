"""Testy przywracania backupów i ich integralności."""

from __future__ import annotations

from pathlib import Path

import pytest
from conftest import FakeProject


def test_backup_symlink_cannot_escape_backup_store(fake_project: FakeProject) -> None:
    outside = fake_project.root / "outside-backups"
    outside.mkdir()
    fake_project.backup_dir.mkdir()
    try:
        (fake_project.backup_dir / "files").symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("System nie pozwala tworzyć symlinków katalogów bez dodatkowych uprawnień")
    target = fake_project.game_root / "media/Audio/FMODBanks/engine.bank"
    original = target.read_bytes()

    report = fake_project.engine.enable(["Engine Mod"])

    assert report.exit_code == 1
    assert any("Ścieżka backupu wychodzi poza magazyn" in error for error in report.errors)
    assert target.read_bytes() == original
    assert not (outside / "media/Audio/FMODBanks/engine.bank").exists()


def test_disable_refuses_corrupted_backup_and_keeps_mod_link(
    fake_project: FakeProject,
) -> None:
    target = fake_project.game_root / "media/Audio/FMODBanks/engine.bank"
    fake_project.engine.enable(["Engine Mod"])
    state = fake_project.store.load_state()
    entry = state.mods["Audio/Engine Mod"].files["media/Audio/FMODBanks/engine.bank"]
    assert entry.backup is not None
    backup = fake_project.backup_dir / Path(*entry.backup.split("/"))
    backup.write_bytes(b"corrupted backup")
    deployed = target.read_bytes()

    report = fake_project.engine.disable(["Engine Mod"])

    assert report.exit_code == 1
    assert any("Hash kopii zapasowej jest niezgodny" in error for error in report.errors)
    assert target.read_bytes() == deployed
