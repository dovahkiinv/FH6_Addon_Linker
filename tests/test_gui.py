"""Testy modelu widoku GUI oraz tworzenia okien tkinter."""

from __future__ import annotations

from pathlib import Path

import pytest

from conftest import FakeProject
from fh6linker.gui.app import (
    FH6LinkerApp,
    ModRow,
    build_mod_rows,
    filter_mod_rows,
    toggle_visible_selection,
)
from fh6linker.gui.dialogs import PlanDialog, show_user_guide
from fh6linker.gui.theme import COLORS, configure_theme
from fh6linker.gui.wizard import SetupWizard, deployment_paths_changed
from fh6linker.i18n import (
    load_language,
    normalize_language,
    save_language,
    translate,
    translate_category_path,
)
from fh6linker.report import ModStatus, OperationReport, PlannedAction, StatusReport
from fh6linker.scanner import scan_library
from fh6linker.state import AppConfig


def test_view_model_combines_scan_status_and_missing_mods(fake_project: FakeProject) -> None:
    scan = scan_library(fake_project.library_dir)
    status = fake_project.engine.status()
    status.mods.append(
        ModStatus(
            mod_id="Audio/Removed Mod",
            name="Removed Mod",
            category="",
            status="ZERWANY",
            file_count=2,
            broken_count=2,
            warnings=("Mod nie jest już w bibliotece.",),
        )
    )

    rows = build_mod_rows(scan, status, game_root=fake_project.game_root)

    engine_row = next(row for row in rows if row.mod_id == "Audio/Engine Mod")
    removed_row = next(row for row in rows if row.mod_id == "Audio/Removed Mod")
    assert engine_row.status == "wyłączony"
    assert engine_row.category == "Audio"
    assert Path(engine_row.source_root).name == "Engine Mod"
    assert str(fake_project.game_root / "media/Audio/FMODBanks/engine.bank") in engine_row.target_paths
    assert removed_row.category == "Brak w bibliotece"
    assert removed_row.broken_count == 2


def test_dark_theme_configures_root_and_widget_styles() -> None:
    class RootStub:
        options: dict[str, str]

        def configure(self, **options: str) -> None:
            self.options = options

    class StyleStub:
        def __init__(self) -> None:
            self.theme: str | None = None
            self.options: dict[str, dict[str, object]] = {}
            self.maps: dict[str, dict[str, object]] = {}

        def theme_names(self) -> tuple[str, ...]:
            return ("clam",)

        def theme_use(self, theme: str) -> None:
            self.theme = theme

        def configure(self, name: str, **options: object) -> None:
            self.options[name] = options

        def map(self, name: str, **options: object) -> None:
            self.maps[name] = options

    root = RootStub()
    style = StyleStub()

    class TtkStub:
        @staticmethod
        def Style(_root: RootStub) -> StyleStub:
            return style

    configure_theme(root, TtkStub)

    assert root.options["background"] == COLORS["background"]
    assert style.theme == "clam"
    assert style.options["Treeview"]["background"] == COLORS["surface"]
    assert style.options["TFrame"]["background"] == COLORS["background"]
    assert COLORS["background"] == "#080A0D"


def test_active_deployments_protect_configuration_paths(tmp_path: Path) -> None:
    game = tmp_path / "game"
    library = tmp_path / "mods"
    backup = tmp_path / "config" / "backups"
    config = AppConfig(game_root=game, library_dir=library)

    assert not deployment_paths_changed(
        config,
        game,
        library,
        None,
        default_backup_dir=backup,
    )
    assert deployment_paths_changed(
        config,
        tmp_path / "other-game",
        library,
        None,
        default_backup_dir=backup,
    )
    assert deployment_paths_changed(
        config,
        game,
        tmp_path / "other-mods",
        None,
        default_backup_dir=backup,
    )
    assert deployment_paths_changed(
        config,
        game,
        library,
        tmp_path / "other-backups",
        default_backup_dir=backup,
    )
    assert deployment_paths_changed(
        None,
        game,
        library,
        None,
        default_backup_dir=backup,
    )


def test_filter_and_visible_selection_helpers(tmp_path: Path) -> None:
    scan = scan_library(_make_library(tmp_path))
    rows = build_mod_rows(scan, StatusReport())

    filtered = filter_mod_rows(rows, "engine")
    assert [row.name for row in filtered] == ["Engine Mod"]
    assert filter_mod_rows(rows, "not present") == ()

    selected = toggle_visible_selection({"one", "outside"}, {"one", "two"})
    assert selected == {"outside", "one", "two"}
    selected = toggle_visible_selection(selected, {"one", "two"})
    assert selected == {"outside"}
    assert FH6LinkerApp._status_tag("CZĘŚCIOWY") == "partial"
    assert FH6LinkerApp._status_tag("WŁĄCZONY") == "enabled"


def test_background_operations_disable_and_restore_selection_controls() -> None:
    class WidgetStub:
        def __init__(self) -> None:
            self.configured_state = "normal"
            self.state_calls: list[list[str]] = []

        def configure(self, **options: str) -> None:
            self.configured_state = options["state"]

        def state(self, flags: list[str]) -> None:
            self.state_calls.append(flags)

    app = object.__new__(FH6LinkerApp)
    button, tree, filter_entry = WidgetStub(), WidgetStub(), WidgetStub()
    app.tree = tree
    app._action_buttons = [button]
    app._selection_widgets = [tree, filter_entry]

    app._set_controls_enabled(False)
    assert button.configured_state == "disabled"
    assert tree.state_calls == [["disabled"]]
    assert filter_entry.configured_state == "disabled"

    app._set_controls_enabled(True)
    assert button.configured_state == "normal"
    assert tree.state_calls == [["disabled"], ["!disabled"]]
    assert filter_entry.configured_state == "normal"


def test_gui_windows_construct_when_tk_is_available(fake_project: FakeProject) -> None:
    tk = pytest.importorskip("tkinter")
    try:
        root = tk.Tk()
    except tk.TclError as exc:
        pytest.skip(f"Brak pulpitu do testu tkinter: {exc}")
    root.withdraw()
    try:
        app = FH6LinkerApp(root, fake_project.engine)
        assert app.tree.winfo_exists()
        assert app.empty_state.winfo_exists()
        assert app.enable_all_button.winfo_exists()
        assert app.select_all_button.winfo_exists()
        assert app.deselect_all_button.winfo_exists()
        assert app.language_combo.winfo_exists()
        assert len(app._folder_open_buttons) == 3
        app._set_language("en")
        assert app.language_var.get() == "English"
        assert app.enable_all_button.cget("text") == "Enable all"
        assert app.select_all_button.cget("text") == "Select all"
        assert app.deselect_all_button.cget("text") == "Deselect all"
        assert app._display_status("WŁĄCZONY") == "ENABLED"
        assert app._display_category("Bez kategorii") == "Uncategorized"
        help_menu = app._menu_objects[-1]
        assert help_menu.entrycget(0, "label") == "User guide / tutorial…"
        guide = show_user_guide(root, language="en")
        assert guide.title() == "User guide / tutorial"
        guide.destroy()
        app._set_language("pl")
        app._render_tree()
        assert "mediaoverride" in app.empty_state.cget("text")
        assert app.visible_button.instate(["disabled"])
        assert app.clear_selection_button.instate(["disabled"])

        wizard = SetupWizard(root, fake_project.engine)
        assert wizard.window.winfo_exists()
        wizard.window.destroy()

        report = OperationReport(
            operation="enable",
            actions=[
                PlannedAction(
                    "create_link",
                    "Engine Mod",
                    "media/example.bank",
                    source="/mods/Engine Mod/media/example.bank",
                    target="/game/media/example.bank",
                )
            ],
        )
        dialog = PlanDialog(root, "Plan testowy", [report])
        assert dialog.apply_button.instate(["!disabled"])
        assert dialog.text.cget("background") == COLORS["surface"]
        plan_text = dialog.text.get("1.0", "end")
        assert "Źródło: /mods/Engine Mod/media/example.bank" in plan_text
        assert "Cel: /game/media/example.bank" in plan_text
        dialog.window.destroy()
    finally:
        root.destroy()


def test_ui_language_can_be_saved_and_reloaded(tmp_path: Path) -> None:
    config_dir = tmp_path / "app-config"

    assert load_language(config_dir) == "pl"
    assert translate("en", "action_enable_all") == "Enable all"
    assert translate("en", "menu_guide") == "User guide / tutorial…"
    assert translate("en", "category_uncategorized") == "Uncategorized"
    assert normalize_language("English") == "en"
    assert normalize_language("unknown") == "pl"

    save_language(config_dir, "en")
    assert load_language(config_dir) == "en"
    save_language(config_dir, "Polski")
    assert load_language(config_dir) == "pl"


def test_category_labels_and_filters_follow_gui_language() -> None:
    row = ModRow(
        mod_id="Unknown Mod",
        name="Unknown Mod",
        category="Bez kategorii",
        status="wyłączony",
        file_count=1,
    )

    assert translate_category_path("Bez kategorii", "en") == "Uncategorized"
    assert translate_category_path("Camera/Interface", "pl") == "Kamera/Interfejs"
    assert filter_mod_rows((row,), "uncategorized", "en") == (row,)
    assert filter_mod_rows((row,), "bez kategorii", "en") == (row,)


def test_global_selection_changes_desired_ids_without_touching_game_files() -> None:
    app = object.__new__(FH6LinkerApp)
    app._available_mod_ids = {"Audio/Radio", "Camera/FOV"}
    app._desired_mod_ids = {"Removed/Active Mod"}
    renders: list[bool] = []
    app._render_tree = lambda: renders.append(True)

    app.select_all()
    assert app._desired_mod_ids == {
        "Audio/Radio",
        "Camera/FOV",
        "Removed/Active Mod",
    }
    app.deselect_all()
    assert app._desired_mod_ids == set()
    assert len(renders) == 2


def test_enable_all_plans_every_valid_disabled_mod_only() -> None:
    class EngineStub:
        calls: list[tuple[list[str], bool]]

        def __init__(self) -> None:
            self.calls = []

        def enable(self, names: list[str], *, dry_run: bool = False) -> str:
            self.calls.append((list(names), dry_run))
            return "report"

    app = object.__new__(FH6LinkerApp)
    app.language = "en"
    app._available_mod_ids = {"Audio/Existing", "Audio/New B", "Audio/New A"}
    app._active_mod_ids = {"Audio/Existing"}
    app.engine = EngineStub()
    plans: list[tuple[str, object, object, bool]] = []

    def record_plan(title: str, plan: object, execute: object, *, allow_conflicts: bool) -> None:
        plans.append((title, plan, execute, allow_conflicts))

    app._plan_then_confirm = record_plan
    app.enable_all()

    assert len(plans) == 1
    title, plan, execute, allow_conflicts = plans[0]
    assert title == "Enable all mods"
    assert allow_conflicts is False
    assert callable(plan) and callable(execute)
    assert plan() == ["report"]
    assert execute() == ["report"]
    assert app.engine.calls == [
        (["Audio/New A", "Audio/New B"], True),
        (["Audio/New A", "Audio/New B"], False),
    ]


def _make_library(root: Path) -> Path:
    """Tworzy niewielką bibliotekę do czystych testów filtrów."""
    mod = root / "Audio" / "Engine Mod" / "media" / "Audio" / "engine.bank"
    mod.parent.mkdir(parents=True)
    mod.write_bytes(b"engine")
    return root
