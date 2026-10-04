"""Testy skanowania i filtrowania biblioteki modów."""

from __future__ import annotations

import json
from pathlib import Path
from time import perf_counter

from fh6linker.scanner import scan_library


def test_finds_mod_nested_two_categories_and_ignores_readme(tmp_path: Path) -> None:
    """Mod może leżeć głęboko, a plików poza korzeniem gry nie wdraża się."""
    library = tmp_path / "library"
    mod = library / "Audio" / "Engines" / "Pack A"
    payload = mod / "media" / "Audio" / "FMODBanks" / "engine.bank"
    payload.parent.mkdir(parents=True)
    payload.write_bytes(b"sound")
    (mod / "readme.txt").write_text("Opis moda", encoding="utf-8")
    (mod / ".hidden").write_text("ukryte", encoding="utf-8")
    (mod / "media" / "Audio" / "Thumbs.db").write_bytes(b"noise")

    result = scan_library(library)

    assert len(result.mods) == 1
    assert result.mods[0].mod_id == "Audio/Engines/Pack A"
    assert result.mods[0].files[0].target_rel == "media/Audio/FMODBanks/engine.bank"
    assert "readme.txt" in " ".join(issue.message for issue in result.mods[0].issues)
    assert all("Thumbs.db" not in file.target_rel for file in result.mods[0].files)
    assert all(".hidden" not in file.target_rel for file in result.mods[0].files)


def test_archives_are_silently_ignored_in_library_and_mod_payload(tmp_path: Path) -> None:
    library = tmp_path / "library"
    library.mkdir()
    for name in ("package.zip", "download.RAR", "bundle.7z", "legacy.7zip"):
        (library / name).write_bytes(b"archive")

    mod = library / "Audio" / "Engine Mod"
    payload = mod / "media" / "Audio" / "FMODBanks" / "engine.bank"
    payload.parent.mkdir(parents=True)
    payload.write_bytes(b"sound")
    (mod / "readme.rar").write_bytes(b"archive beside mod")
    (mod / "media" / "Audio" / "extras.zip").write_bytes(b"archive inside game root")

    result = scan_library(library)

    assert len(result.mods) == 1
    assert [item.target_rel for item in result.mods[0].files] == [
        "media/Audio/FMODBanks/engine.bank",
    ]
    messages = [
        issue.message
        for issue in (*result.issues, *result.mods[0].issues)
    ]
    assert not any(name in message.casefold() for message in messages for name in (".zip", ".rar", ".7z", ".7zip"))


def test_metadata_controls_display_name_and_category(tmp_path: Path) -> None:
    mod = tmp_path / "library" / "Effects" / "Raw Folder"
    (mod / "mediapc" / "Textures").mkdir(parents=True)
    (mod / "mediapc" / "Textures" / "one.dds").write_bytes(b"dds")
    (mod / "mod.json").write_text(
        json.dumps({"display_name": "Lepsza nazwa", "category": "Grafika"}),
        encoding="utf-8",
    )

    result = scan_library(mod.parents[1])

    assert result.mods[0].display_name == "Lepsza nazwa"
    assert result.mods[0].category == "Grafika"
    assert result.mods[0].root_marker == "mediapc"


def test_virtual_root_mod_maps_files_to_game_root_and_skips_readme(tmp_path: Path) -> None:
    library = tmp_path / "library"
    mod_root = library / "Tools" / "ReShade"
    config = mod_root / "config"
    config.mkdir(parents=True)
    (mod_root / "mod.json").write_text(
        '{"display_name":"ReShade","category":"Tools"}',
        encoding="utf-8",
    )
    (mod_root / "dinput8.dll").write_bytes(b"loader")
    (config / "reshade.ini").write_text("[GENERAL]", encoding="utf-8")
    (mod_root / "README.md").write_text("documentation", encoding="utf-8")

    result = scan_library(library)

    mod = next(mod for mod in result.mods if mod.display_name == "ReShade")
    assert mod.moderoot_rel == ""
    assert mod.metadata.category == "Tools"
    assert {item.target_rel for item in mod.files} == {
        "dinput8.dll",
        "config/reshade.ini",
    }
    assert any(issue.code == "readme_ignored" for issue in mod.issues)


def test_universal_radio_root_layout_is_recognized_and_mapped_to_game_root(
    tmp_path: Path,
) -> None:
    library = tmp_path / "library"
    mod_root = library / "FH6 Universal Radio 215"
    radio_root = mod_root / "fh6-radio"
    (radio_root / "ui" / "assets").mkdir(parents=True)
    (mod_root / "version.dll").write_bytes(b"radio loader")
    (mod_root / "README.txt").write_text("install beside game executable", encoding="utf-8")
    (radio_root / "config.toml").write_text("[general]", encoding="utf-8")
    (radio_root / "fh6-radio-worker.exe").write_bytes(b"worker")
    (radio_root / "ui" / "assets" / "radio.png").write_bytes(b"artwork")

    result = scan_library(library)

    assert len(result.mods) == 1
    mod = result.mods[0]
    assert mod.valid
    assert mod.display_name == "FH6 Universal Radio"
    assert mod.category == "Audio"
    assert mod.root_marker is None
    assert {item.target_rel for item in mod.files} == {
        "version.dll",
        "fh6-radio/config.toml",
        "fh6-radio/fh6-radio-worker.exe",
        "fh6-radio/ui/assets/radio.png",
    }
    assert not any(issue.code == "loose_file_ignored" for issue in result.issues)
    assert not any(issue.code == "ignored_sidecar" for issue in mod.issues)
    assert any(issue.code == "root_loader_mod" for issue in mod.issues)


def test_universal_radio_manifest_keeps_explicit_name_and_category(tmp_path: Path) -> None:
    library = tmp_path / "library"
    mod_root = library / "Radio Folder"
    radio_root = mod_root / "fh6-radio"
    radio_root.mkdir(parents=True)
    (mod_root / "version.dll").write_bytes(b"loader")
    (radio_root / "config.toml").write_text("[general]", encoding="utf-8")
    (radio_root / "fh6-radio-worker.exe").write_bytes(b"worker")
    (mod_root / "mod.json").write_text(
        '{"display_name":"Custom Radio Name","category":"Custom Audio"}',
        encoding="utf-8",
    )

    result = scan_library(library)

    assert len(result.mods) == 1
    assert result.mods[0].display_name == "Custom Radio Name"
    assert result.mods[0].category == "Custom Audio"
    assert "mod.json" not in {item.target_rel for item in result.mods[0].files}


def test_incomplete_radio_like_folder_remains_unrecognized(tmp_path: Path) -> None:
    library = tmp_path / "library"
    mod_root = library / "Unknown Package"
    radio_root = mod_root / "fh6-radio"
    radio_root.mkdir(parents=True)
    (mod_root / "version.dll").write_bytes(b"not enough markers")
    (radio_root / "config.toml").write_text("[general]", encoding="utf-8")

    result = scan_library(library)

    assert result.mods == []
    assert {issue.code for issue in result.issues} == {"loose_file_ignored"}


def test_conservative_category_inference_for_common_mod_types(tmp_path: Path) -> None:
    library = tmp_path / "library"
    cases = (
        (
            "All Forced Inductions plus 6db",
            "media/Audio/FMODBanks/BOV_Kei_Large.assets.bank",
            "Audio",
        ),
        (
            "FH6 CameraFOV",
            "mediapc/Camera/CameraSettings.ini",
            "Camera",
        ),
        (
            "Quick Menus",
            "mediapc/UI/Resources/Anthem/Global_Transitions.xaml",
            "Interface",
        ),
        (
            "URH_Red",
            "mediapc/UI/MapProfiles/MapIncludes/MapIncludeHudRoads.xml",
            "Map",
        ),
    )
    for name, target, _category in cases:
        payload = library / name / target
        payload.parent.mkdir(parents=True, exist_ok=True)
        payload.write_bytes(b"payload")
    quick_menu_audio = library / "Quick Menus" / "mediapc/Audio/UI4Audio.xml"
    quick_menu_audio.parent.mkdir(parents=True, exist_ok=True)
    quick_menu_audio.write_bytes(b"audio ui")

    result = scan_library(library)

    categories = {mod.name: mod.category for mod in result.mods}
    assert categories == {name: category for name, _target, category in cases}
    quick_menus = next(mod for mod in result.mods if mod.name == "Quick Menus")
    assert {item.target_rel for item in quick_menus.files} == {
        "mediapc/UI/Resources/Anthem/Global_Transitions.xaml",
        "mediapc/Audio/UI4Audio.xml",
    }


def test_explicit_parent_folder_category_overrides_inference(tmp_path: Path) -> None:
    library = tmp_path / "library"
    payload = library / "Custom Category" / "Quick Menus" / "mediapc/UI/menus.xaml"
    payload.parent.mkdir(parents=True)
    payload.write_bytes(b"ui")

    result = scan_library(library)

    assert result.mods[0].category == "Custom Category"


def test_readme_inside_game_root_is_never_deployed(tmp_path: Path) -> None:
    library = tmp_path / "library"
    mod_root = library / "Audio" / "Engine Mod" / "media"
    payload = mod_root / "Audio" / "FMODBanks" / "engine.bank"
    payload.parent.mkdir(parents=True)
    payload.write_bytes(b"sound")
    (mod_root / "README.txt").write_text("documentation", encoding="utf-8")

    result = scan_library(library)

    mod = result.mods[0]
    assert {item.target_rel for item in mod.files} == {
        "media/Audio/FMODBanks/engine.bank",
    }
    assert any(issue.code == "readme_ignored" for issue in mod.issues)


def test_multiple_roots_are_reported_as_error(tmp_path: Path) -> None:
    mod = tmp_path / "library" / "Broken"
    (mod / "media").mkdir(parents=True)
    (mod / "mediapc").mkdir()
    (mod / "media" / "a.bank").write_bytes(b"a")
    (mod / "mediapc" / "b.dds").write_bytes(b"b")

    result = scan_library(mod.parent)

    assert len(result.mods) == 1
    assert not result.mods[0].valid
    assert any(issue.code == "multiple_roots" for issue in result.mods[0].issues)
    assert result.errors


def test_library_root_mod_without_category_clues_stays_uncategorized(tmp_path: Path) -> None:
    library = tmp_path / "Game Mod"
    (library / "media" / "Other").mkdir(parents=True)
    (library / "media" / "Other" / "misc.bin").write_bytes(b"misc")

    result = scan_library(library)

    assert len(result.mods) == 1
    assert result.mods[0].mod_id == library.name
    assert result.mods[0].category == "Bez kategorii"
    assert result.mods[0].files[0].target_rel == "media/Other/misc.bin"


def test_scan_1000_mods_completes_within_three_seconds(tmp_path: Path) -> None:
    library = tmp_path / "library"
    for index in range(1000):
        payload = library / "Category" / f"Mod-{index:04}" / "media" / "Audio" / "bank.bin"
        payload.parent.mkdir(parents=True)
        payload.write_bytes(b"x")

    started = perf_counter()
    result = scan_library(library)
    elapsed = perf_counter() - started

    assert len(result.mods) == 1000
    assert elapsed < 3.0


def test_empty_mod_is_reported(tmp_path: Path) -> None:
    mod = tmp_path / "library" / "Empty"
    (mod / "media").mkdir(parents=True)

    result = scan_library(mod.parent)

    assert not result.mods[0].valid
    assert any(issue.code == "empty_mod" for issue in result.mods[0].issues)
