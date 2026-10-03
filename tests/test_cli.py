"""Testy poleceń CLI milestone'u M1."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from conftest import FakeProject


def test_cli_scan_enable_status_disable_restore(fake_project: FakeProject) -> None:
    environment = os.environ.copy()
    environment["FH6LINKER_CONFIG_DIR"] = str(fake_project.config_dir)
    environment["PYTHONUTF8"] = "1"
    environment["PYTHONIOENCODING"] = "utf-8"

    scan = _run("scan", "--json", root=fake_project.root, env=environment)
    assert scan.returncode == 0
    assert '"name": "Engine Mod"' in scan.stdout

    dry_run = _run(
        "enable", "Engine Mod", "--dry-run", root=fake_project.root, env=environment
    )
    assert dry_run.returncode == 0
    target = fake_project.game_root / "media/Audio/FMODBanks/engine.bank"
    assert target.read_bytes() == b"vanilla audio bytes\x00"

    enabled = _run("enable", "Engine Mod", root=fake_project.root, env=environment)
    assert enabled.returncode == 0
    assert target.read_bytes() == b"modded engine audio\x00"

    status = _run("status", "--json", root=fake_project.root, env=environment)
    assert status.returncode == 0
    assert '"status": "WŁĄCZONY"' in status.stdout

    disabled = _run("disable", "Engine Mod", root=fake_project.root, env=environment)
    assert disabled.returncode == 0
    assert target.read_bytes() == b"vanilla audio bytes\x00"

    enabled_again = _run("enable", "Engine Mod", root=fake_project.root, env=environment)
    assert enabled_again.returncode == 0
    restored = _run("restore", "--yes", root=fake_project.root, env=environment)
    assert restored.returncode == 0
    assert target.read_bytes() == b"vanilla audio bytes\x00"


def test_cli_set_dry_run_does_not_write_config(fake_project: FakeProject) -> None:
    config_dir = fake_project.root / "dry-config"
    environment = os.environ.copy()
    environment["FH6LINKER_CONFIG_DIR"] = str(config_dir)
    result = _run(
        "set",
        "--game",
        str(fake_project.game_root),
        "--library",
        str(fake_project.library_dir),
        "--dry-run",
        root=fake_project.root,
        env=environment,
    )

    assert result.returncode == 0
    assert "bez zapisu" in result.stdout
    assert not config_dir.exists()


def test_cli_set_dry_run_rejects_default_backup_inside_game(fake_project: FakeProject) -> None:
    config_dir = fake_project.game_root / "app-config"
    environment = os.environ.copy()
    environment["FH6LINKER_CONFIG_DIR"] = str(config_dir)
    result = _run(
        "set",
        "--game",
        str(fake_project.game_root),
        "--library",
        str(fake_project.library_dir),
        "--dry-run",
        root=fake_project.root,
        env=environment,
    )

    assert result.returncode == 1
    assert "Magazyn kopii nie może pokrywać się" in result.stderr
    assert not config_dir.exists()


def test_cli_bad_game_path_explains_validation_error(
    fake_project: FakeProject,
) -> None:
    environment = os.environ.copy()
    environment["FH6LINKER_CONFIG_DIR"] = str(fake_project.root / "cli-config")
    bad_game = fake_project.root / "bad-game"
    bad_game.mkdir()
    result = _run(
        "set",
        "--game",
        str(bad_game),
        "--library",
        str(fake_project.library_dir),
        root=fake_project.root,
        env=environment,
    )

    assert result.returncode == 1
    assert "Brak forzahorizon6.exe i folderów media/mediapc" in result.stderr


def _run(
    *arguments: str,
    root: Path,
    env: dict[str, str],
) -> subprocess.CompletedProcess[str]:
    child_env = env.copy()
    child_env["PYTHONUTF8"] = "1"
    child_env["PYTHONIOENCODING"] = "utf-8"
    return subprocess.run(
        [sys.executable, "-m", "fh6linker", *arguments],
        cwd=root,
        env=child_env,
        capture_output=True,
        encoding="utf-8",
        check=False,
    )
