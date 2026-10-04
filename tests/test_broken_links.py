"""Testy wykrywania zerwanych linków, repair i ochrony plików po update."""

from __future__ import annotations

import os
from pathlib import Path

from conftest import FakeProject


def test_media_to_mediapc_mismatch_is_suggested(fake_project: FakeProject) -> None:
    alternate = fake_project.game_root / "mediapc/Audio/FMODBanks/engine.bank"
    alternate.parent.mkdir(parents=True, exist_ok=True)
    alternate.write_bytes(b"pc-specific vanilla")

    report = fake_project.engine.enable(["Engine Mod"], dry_run=True)

    assert report.exit_code == 0
    assert any("powinien używać mediapc/" in warning for warning in report.warnings)
    assert any("Backup obejmie wyłącznie dokładną ścieżkę" in warning for warning in report.warnings)


def test_mismatched_root_warns_but_creates_selected_target_without_backup(
    fake_project: FakeProject,
) -> None:
    target = fake_project.game_root / "media/Audio/FMODBanks/engine.bank"
    alternate = fake_project.game_root / "mediapc/Audio/FMODBanks/engine.bank"
    original = b"pc-specific vanilla"
    target.unlink()
    alternate.parent.mkdir(parents=True, exist_ok=True)
    alternate.write_bytes(original)

    dry_run = fake_project.engine.enable(["Engine Mod"], dry_run=True)

    assert dry_run.exit_code == 0
    assert dry_run.files_planned == 1
    assert any("Plan utworzy nowy target" in warning for warning in dry_run.warnings)
    assert not target.exists()
    assert alternate.read_bytes() == original

    enabled = fake_project.engine.enable(["Engine Mod"])

    assert enabled.exit_code == 0
    assert target.read_bytes() == b"modded engine audio\x00"
    assert alternate.read_bytes() == original
    entry = fake_project.store.load_state().mods["Audio/Engine Mod"].files[
        "media/Audio/FMODBanks/engine.bank"
    ]
    assert entry.backup is None
    assert not fake_project.backup_dir.exists()

    disabled = fake_project.engine.disable(["Engine Mod"])
    assert disabled.exit_code == 0
    assert not target.exists()
    assert alternate.read_bytes() == original


def test_game_update_breaks_link_and_repair_updates_baseline(fake_project: FakeProject) -> None:
    target = fake_project.game_root / "media/Audio/FMODBanks/engine.bank"
    update = target.with_name("engine.bank.updated")
    fake_project.engine.enable(["Engine Mod"])
    update.write_bytes(b"new vanilla after game update")
    os.replace(update, target)

    status = fake_project.engine.status()
    row = next(mod for mod in status.mods if mod.name == "Engine Mod")
    assert row.status == "ZERWANY"
    assert row.broken_count == 1

    repaired = fake_project.engine.repair(["Engine Mod"])
    assert repaired.exit_code == 0
    source = fake_project.library_dir / "Audio/Engine Mod/media/Audio/FMODBanks/engine.bank"
    assert os.path.samefile(target, source)
    assert target.read_bytes() == b"modded engine audio\x00"
    assert fake_project.engine.verify(["Engine Mod"]).exit_code == 0

    disabled = fake_project.engine.disable(["Engine Mod"])
    assert disabled.exit_code == 0
    assert target.read_bytes() == b"new vanilla after game update"


def test_disable_preserves_game_replacement(fake_project: FakeProject) -> None:
    target = fake_project.game_root / "media/Audio/FMODBanks/engine.bank"
    fake_project.engine.enable(["Engine Mod"])
    update = target.with_name("engine.bank.updated")
    update.write_bytes(b"external update stays")
    os.replace(update, target)

    report = fake_project.engine.disable(["Engine Mod"])

    assert report.exit_code == 2
    assert target.read_bytes() == b"external update stays"
    assert any("nie należy już do narzędzia" in conflict for conflict in report.conflicts)
    conflicts = list((fake_project.backup_dir / "conflicts").rglob("engine.bank"))
    assert conflicts
    assert conflicts[0].read_bytes() == b"external update stays"
