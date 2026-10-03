"""Testy kolizji ścieżek i jawnego przejęcia targetu."""

from __future__ import annotations

from pathlib import Path

from conftest import FakeProject


def test_second_mod_conflict_changes_nothing_without_force(fake_project: FakeProject) -> None:
    target = fake_project.game_root / "media/Audio/FMODBanks/engine.bank"
    second_root = fake_project.library_dir / "Audio" / "Alternative Engine"
    second_source = second_root / "media/Audio/FMODBanks/engine.bank"
    second_source.parent.mkdir(parents=True)
    second_source.write_bytes(b"alternative mod")

    first = fake_project.engine.enable(["Engine Mod"])
    before = target.read_bytes()
    second = fake_project.engine.enable(["Alternative Engine"])

    assert first.exit_code == 0
    assert second.exit_code == 2
    assert any("Konflikt" in message for message in second.conflicts)
    assert target.read_bytes() == before
    assert len(fake_project.store.load_state().mods) == 1


def test_force_replacement_is_explicit_and_reported(fake_project: FakeProject) -> None:
    target = fake_project.game_root / "media/Audio/FMODBanks/engine.bank"
    second_source = fake_project.library_dir / "Audio/Alternative/media/Audio/FMODBanks/engine.bank"
    second_source.parent.mkdir(parents=True)
    second_source.write_bytes(b"forced mod")
    fake_project.engine.enable(["Engine Mod"])

    report = fake_project.engine.enable(["Alternative"], force=True)

    assert report.exit_code == 0
    assert target.read_bytes() == b"forced mod"
    assert any("--force" in warning for warning in report.warnings)
