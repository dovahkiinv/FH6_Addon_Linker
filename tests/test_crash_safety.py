"""Testy rollbacku po przerwaniu i samonaprawy z journala."""

from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path

from conftest import FakeProject
from fh6linker.linkops import copy_file_atomic, digest_file
from fh6linker.scanner import scan_library
from fh6linker.state import AppState, FileState, JournalEvent, ModState


def test_mid_deploy_exception_rolls_back_all_game_files(fake_project: FakeProject) -> None:
    mod_root = fake_project.library_dir / "Stress" / "Hundred Files"
    game_folder = fake_project.game_root / "media/Stress"
    game_folder.mkdir(parents=True)
    for index in range(100):
        rel = f"media/Stress/file_{index:03}.bin"
        target = fake_project.game_root / rel
        target.write_bytes(f"vanilla-{index}".encode())
        source = mod_root / rel
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_bytes(f"modded-{index}".encode())

    def crash_after_half(completed: int) -> None:
        if completed == 50:
            raise RuntimeError("symulowane przerwanie deployu")

    fake_project.engine.after_file_hook = crash_after_half
    report = fake_project.engine.enable(["Hundred Files"])

    assert report.exit_code == 1
    assert any("symulowane przerwanie" in message for message in report.errors)
    assert fake_project.store.load_state().mods == {}
    assert not fake_project.store.load_state().created_dirs
    for index in range(100):
        target = fake_project.game_root / f"media/Stress/file_{index:03}.bin"
        assert target.read_bytes() == f"vanilla-{index}".encode()
        assert target.stat().st_nlink == 1


def test_status_self_heals_incomplete_enable_journal(fake_project: FakeProject) -> None:
    mod = next(mod for mod in scan_library(fake_project.library_dir).mods if mod.name == "Engine Mod")
    mod_file = mod.files[0]
    target = fake_project.game_root / Path(*mod_file.target_rel.split("/"))
    source = mod_file.source_path
    original = target.read_bytes()
    source_digest = digest_file(source)
    backup_rel = f"files/{mod_file.target_rel}"
    backup = fake_project.backup_dir / Path(*backup_rel.split("/"))
    copy_file_atomic(target, backup)
    target.unlink()
    os.link(source, target)

    state = AppState(
        mods={
            mod.mod_id: ModState(
                source_root=str(mod.source_root),
                moderoot_rel=mod.moderoot_rel,
                deployed_at=datetime.now(UTC).isoformat(),
                method="hardlink",
                files={
                    mod_file.target_rel: FileState(
                        method="hardlink",
                        source=str(source),
                        src_sha256=source_digest.sha256,
                        src_size=source_digest.size,
                        src_mtime=source_digest.mtime,
                        backup=backup_rel,
                        deployed_sha256=source_digest.sha256,
                        deployed_size=source_digest.size,
                    )
                },
            )
        }
    )
    fake_project.store.save_state(state)
    txid = "interrupted-deploy"
    details = {
        "previous_exists": True,
        "previous_mod_entry": None,
        "previous_mod_owned": False,
        "previous_owner_id": None,
        "previous_owner_entry": None,
        "backup_rel": backup_rel,
        "expected_sha256": source_digest.sha256,
        "expected_size": source_digest.size,
        "created_dirs": [],
    }
    events = [
        JournalEvent.create(op="enable", phase="plan", txid=txid),
        JournalEvent.create(
            op="enable",
            phase="begin",
            txid=txid,
            mod=mod.mod_id,
            file=mod_file.target_rel,
            target=str(target),
            source=str(source),
            backup=str(backup),
            method="hardlink",
            details=details,
        ),
        JournalEvent.create(
            op="enable", phase="backup_done", txid=txid,
            mod=mod.mod_id, file=mod_file.target_rel, target=str(target), backup=str(backup),
        ),
        JournalEvent.create(
            op="enable", phase="original_removed", txid=txid,
            mod=mod.mod_id, file=mod_file.target_rel, target=str(target), source=str(source),
            backup=str(backup), method="hardlink", details=details,
        ),
        JournalEvent.create(
            op="enable", phase="link_created", txid=txid,
            mod=mod.mod_id, file=mod_file.target_rel, target=str(target), source=str(source),
            backup=str(backup), method="hardlink", details=details,
        ),
    ]
    for event in events:
        fake_project.store.append_journal(event)

    fresh_engine = type(fake_project.engine)(fake_project.store)
    status = fresh_engine.status()

    assert not status.errors
    assert target.read_bytes() == original
    assert target.stat().st_nlink == 1
    assert fake_project.store.load_state().mods == {}
    assert any(event.phase == "recovered" for event in fake_project.store.read_journal())
