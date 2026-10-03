"""Testy deployu, idempotencji i przywracania oryginałów."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

import fh6linker.engine as engine_module
import pytest
from fh6linker.linkops import LinkOperationError
from conftest import FakeProject


def test_deploy_uses_hardlink_and_backs_up_original(fake_project: FakeProject) -> None:
    target = fake_project.game_root / "media/Audio/FMODBanks/engine.bank"
    source = (
        fake_project.library_dir
        / "Audio/Engine Mod/media/Audio/FMODBanks/engine.bank"
    )
    original = b"vanilla audio bytes\x00"

    report = fake_project.engine.enable(["Engine Mod"])

    assert report.exit_code == 0
    assert report.files_changed == 1
    assert target.read_bytes() == source.read_bytes()
    assert os.path.samefile(target, source)
    assert target.stat().st_nlink >= 2
    backup = fake_project.backup_dir / "files/media/Audio/FMODBanks/engine.bank"
    assert backup.read_bytes() == original
    entry = fake_project.store.load_state().mods["Audio/Engine Mod"].files[
        "media/Audio/FMODBanks/engine.bank"
    ]
    assert entry.backup_sha256 == hashlib.sha256(original).hexdigest()
    assert entry.backup_size == len(original)
    assert entry.backup_mtime is not None


def test_enable_and_disable_are_idempotent(fake_project: FakeProject) -> None:
    target = fake_project.game_root / "media/Audio/FMODBanks/engine.bank"
    expected = target.read_bytes()

    first_enable = fake_project.engine.enable(["Engine Mod"])
    second_enable = fake_project.engine.enable(["Engine Mod"])
    assert first_enable.exit_code == 0
    assert first_enable.files_changed == 1
    assert second_enable.exit_code == 0
    assert second_enable.files_changed == 0

    first_disable = fake_project.engine.disable(["Engine Mod"])
    second_disable = fake_project.engine.disable(["Engine Mod"])
    assert first_disable.exit_code == 0
    assert first_disable.files_changed == 1
    assert second_disable.exit_code == 0
    assert second_disable.files_changed == 0
    assert target.read_bytes() == expected
    assert not fake_project.engine.status().errors


def test_new_file_directories_are_removed_on_disable(fake_project: FakeProject) -> None:
    mod_root = fake_project.library_dir / "Misc" / "Extra Asset"
    source = mod_root / "media" / "Additional" / "Nested" / "extra.bin"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"additional file")
    target = fake_project.game_root / "media/Additional/Nested/extra.bin"

    enabled = fake_project.engine.enable(["Extra Asset"])
    assert enabled.exit_code == 0
    assert target.read_bytes() == b"additional file"
    state = fake_project.store.load_state()
    assert state.mods["Misc/Extra Asset"].files["media/Additional/Nested/extra.bin"].backup is None

    disabled = fake_project.engine.disable(["Extra Asset"])
    assert disabled.exit_code == 0
    assert not target.exists()
    assert not (fake_project.game_root / "media/Additional/Nested").exists()


def test_restore_returns_game_tree_to_original(fake_project: FakeProject) -> None:
    before = _tree_snapshot(fake_project.game_root)
    for name in ("Engine Mod", "New Bank", "Sky Mod"):
        assert fake_project.engine.enable([name]).exit_code == 0

    report = fake_project.engine.restore()

    assert report.exit_code == 0
    assert _tree_snapshot(fake_project.game_root) == before
    assert fake_project.store.load_state().mods == {}


def test_dry_run_does_not_change_any_tree(fake_project: FakeProject) -> None:
    before_game = _tree_snapshot(fake_project.game_root)
    before_library = _tree_snapshot(fake_project.library_dir)
    before_config = _tree_snapshot(fake_project.config_dir)
    before_backup = _tree_snapshot(fake_project.backup_dir) if fake_project.backup_dir.exists() else {}

    report = fake_project.engine.enable(["Engine Mod"], dry_run=True)

    assert report.dry_run
    assert report.exit_code == 0
    assert report.files_planned == 1
    assert _tree_snapshot(fake_project.game_root) == before_game
    assert _tree_snapshot(fake_project.library_dir) == before_library
    assert _tree_snapshot(fake_project.config_dir) == before_config
    after_backup = _tree_snapshot(fake_project.backup_dir) if fake_project.backup_dir.exists() else {}
    assert after_backup == before_backup


def test_force_transfers_target_and_preserves_original_backup(
    fake_project: FakeProject,
) -> None:
    target_rel = "media/Audio/FMODBanks/engine.bank"
    target = fake_project.game_root / target_rel
    alternative_root = fake_project.library_dir / "Audio/Alternative Engine"
    alternative_source = alternative_root / target_rel
    alternative_source.parent.mkdir(parents=True)
    alternative_source.write_bytes(b"alternative engine audio")
    assert fake_project.engine.enable(["Engine Mod"]).exit_code == 0
    before_state = fake_project.store.load_state()
    original_entry = before_state.mods["Audio/Engine Mod"].files[target_rel]

    report = fake_project.engine.enable(["Alternative Engine"], force=True)

    assert report.exit_code == 0
    state = fake_project.store.load_state()
    assert "Audio/Engine Mod" not in state.mods
    alternative_entry = state.mods["Audio/Alternative Engine"].files[target_rel]
    assert alternative_entry.backup == original_entry.backup
    assert target.read_bytes() == b"alternative engine audio"
    assert os.path.samefile(target, alternative_source)

    disabled = fake_project.engine.disable(["Alternative Engine"])
    assert disabled.exit_code == 0
    assert target.read_bytes() == b"vanilla audio bytes\x00"


def test_force_rollback_restores_previous_owner_and_state(
    fake_project: FakeProject,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target_rel = "media/Audio/FMODBanks/engine.bank"
    target = fake_project.game_root / target_rel
    alternative_root = fake_project.library_dir / "Audio/Alternative Engine"
    alternative_source = alternative_root / target_rel
    alternative_source.parent.mkdir(parents=True)
    alternative_source.write_bytes(b"alternative engine audio")
    assert fake_project.engine.enable(["Engine Mod"]).exit_code == 0
    before_state = fake_project.store.load_state()
    original_create_link = engine_module.create_link

    def fail_alternative(source, destination, method):
        if Path(source) == alternative_source:
            raise LinkOperationError("symulowana awaria wdrożenia")
        return original_create_link(source, destination, method)

    monkeypatch.setattr(engine_module, "create_link", fail_alternative)
    report = fake_project.engine.enable(["Alternative Engine"], force=True)

    assert report.exit_code == 1
    assert target.read_bytes() == b"modded engine audio\x00"
    assert os.path.samefile(target, fake_project.library_dir / "Audio/Engine Mod" / target_rel)
    assert fake_project.store.load_state().to_dict() == before_state.to_dict()


def test_required_privilege_uses_exit_code_three(
    fake_project: FakeProject,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = fake_project.game_root / "media/Audio/FMODBanks/engine.bank"
    original = target.read_bytes()

    def fail_link(*args, **kwargs):
        raise LinkOperationError("Wymagane uprawnienia administratora.", requires_privilege=True)

    monkeypatch.setattr(engine_module, "create_link", fail_link)
    report = fake_project.engine.enable(["Engine Mod"])

    assert report.exit_code == 3
    assert report.privilege_required
    assert target.read_bytes() == original
    assert fake_project.store.load_state().mods == {}


def _tree_snapshot(root: Path) -> dict[str, tuple[str, bytes | None]]:
    snapshot: dict[str, tuple[str, bytes | None]] = {}
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        if path.is_dir():
            snapshot[relative] = ("dir", None)
        elif path.is_file():
            snapshot[relative] = ("file", path.read_bytes())
    return snapshot
