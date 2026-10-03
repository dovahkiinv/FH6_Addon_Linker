"""Testy atomowego stanu, journala i blokady instancji."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from fh6linker.state import AppState, JournalEvent, StateError, StateStore


def test_state_save_is_atomic_and_keeps_previous_backup(tmp_path: Path) -> None:
    store = StateStore(tmp_path / "config")
    store.save_state(AppState(game_version_seen="1.0"))
    store.save_state(AppState(game_version_seen="2.0"))

    current = json.loads(store.state_path.read_text(encoding="utf-8"))
    previous = json.loads(store.state_path.with_suffix(".json.bak").read_text(encoding="utf-8"))

    assert current["game_version_seen"] == "2.0"
    assert previous["game_version_seen"] == "1.0"
    assert not list(store.config_dir.glob("*.tmp"))


def test_lock_rejects_second_instance_and_releases_afterward(tmp_path: Path) -> None:
    store = StateStore(tmp_path / "config")

    with store.lock():
        with pytest.raises(StateError, match="jest już uruchomiony"):
            with store.lock():
                raise AssertionError("blokada powinna przerwać wejście")
        assert store.lock_path.exists()

    assert not store.lock_path.exists()


def test_stale_pid_lock_is_removed(tmp_path: Path) -> None:
    store = StateStore(tmp_path / "config")
    store.config_dir.mkdir()
    store.lock_path.write_text('{"pid": 2147483647}', encoding="utf-8")

    with store.lock():
        assert store.lock_path.exists()

    assert not store.lock_path.exists()


def test_journal_roundtrip(tmp_path: Path) -> None:
    store = StateStore(tmp_path / "config")
    event = JournalEvent.create(
        op="enable",
        phase="begin",
        txid="test-transaction",
        mod="Audio/Test",
        file="media/test.bank",
        details={"backup": "files/media/test.bank", "size": 12},
    )
    store.append_journal(event)

    restored = store.read_journal()

    assert len(restored) == 1
    assert restored[0].txid == "test-transaction"
    assert restored[0].details["size"] == 12
