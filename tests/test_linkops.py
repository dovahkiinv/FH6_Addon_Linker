"""Testy metod linkowania i kontroli własności targetu."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from fh6linker.linkops import (
    LinkOperationError,
    create_link,
    copy_file_atomic,
    digest_file,
    is_owned,
    remove_if_owned,
)


def test_hardlink_shares_inode_and_is_removed_only_when_owned(tmp_path: Path) -> None:
    source = tmp_path / "library" / "mod.bin"
    target = tmp_path / "game" / "media" / "mod.bin"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"mod bytes")

    method, warnings = create_link(source, target, "hardlink")
    digest = digest_file(source)

    assert method == "hardlink"
    assert warnings == []
    assert target.read_bytes() == source.read_bytes()
    assert os.path.samefile(source, target)
    assert target.stat().st_nlink >= 2
    assert is_owned(target, source, method, digest.sha256, digest.size)
    assert remove_if_owned(target, source, method, digest.sha256, digest.size)
    assert not target.exists()
    assert source.exists()


def test_foreign_file_is_never_removed(tmp_path: Path) -> None:
    source = tmp_path / "mod.bin"
    target = tmp_path / "game.bin"
    source.write_bytes(b"mod")
    target.write_bytes(b"game update")
    digest = digest_file(source)

    assert not remove_if_owned(target, source, "hardlink", digest.sha256, digest.size)
    assert target.read_bytes() == b"game update"


def test_auto_falls_back_when_hardlink_cannot_be_created(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "mod.bin"
    target = tmp_path / "target.bin"
    source.write_bytes(b"mod")

    def fail_link(*_args: object, **_kwargs: object) -> None:
        raise OSError(18, "Invalid cross-device link")

    monkeypatch.setattr(os, "link", fail_link)
    method, warnings = create_link(source, target, "auto")

    assert method in {"symlink", "copy"}
    assert target.read_bytes() == b"mod"
    assert any("hardlink" in warning for warning in warnings)


def test_atomic_copy_checks_expected_digest_and_never_overwrites(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.bin"
    destination = tmp_path / "destination.bin"
    source.write_bytes(b"backup bytes")

    with pytest.raises(LinkOperationError, match="nie zgadza się"):
        copy_file_atomic(source, destination, overwrite=False, expected_sha256="0" * 64)
    assert not destination.exists()

    destination.write_bytes(b"foreign bytes")
    with pytest.raises(LinkOperationError):
        copy_file_atomic(source, destination, overwrite=False)
    assert destination.read_bytes() == b"foreign bytes"


def test_hardlink_failure_explains_same_volume_requirement(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "mod.bin"
    target = tmp_path / "target.bin"
    source.write_bytes(b"mod")

    def fail_link(*_args: object, **_kwargs: object) -> None:
        raise OSError(18, "Invalid cross-device link")

    monkeypatch.setattr(os, "link", fail_link)
    with pytest.raises(LinkOperationError, match="różnymi wolumenami"):
        create_link(source, target, "hardlink")
