"""Główne okno desktopowe FH6 Addon Linker."""

from __future__ import annotations

import os
import queue
import subprocess
import sys
import threading
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Iterable

from .. import __version__
from ..engine import LinkerEngine
from ..i18n import (
    LANGUAGE_LABELS,
    language_from_label,
    load_language,
    normalize_language,
    save_language,
    translate,
)
from ..report import OperationReport, StatusReport
from ..scanner import ScanResult
from ..state import AppState, StateError
from .dialogs import PlanDialog, show_about, show_mod_details
from .theme import COLORS, configure_theme


@dataclass(frozen=True)
class ModRow:
    """Dane jednego wiersza listy modów, niezależne od tkinter."""

    mod_id: str
    name: str
    category: str
    status: str
    file_count: int
    broken_count: int = 0
    warnings: tuple[str, ...] = ()
    source_root: str = ""
    target_paths: tuple[str, ...] = ()


def _full_target_path(target_rel: str, game_root: Path | None) -> str:
    """Zwraca ścieżkę docelową w grze, pozostawiając względną bez konfiguracji."""
    if game_root is None:
        return target_rel
    return str(game_root.joinpath(*PurePosixPath(target_rel).parts))


def open_directory(path: str | Path) -> None:
    """Otwiera istniejący katalog w domyślnym menedżerze plików systemu."""
    directory = Path(path).expanduser()
    if os.name == "nt":
        os.startfile(str(directory))  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(directory)])
    else:
        subprocess.Popen(["xdg-open", str(directory)])


def build_mod_rows(
    scan: ScanResult,
    status: StatusReport,
    state: AppState | None = None,
    game_root: Path | None = None,
) -> tuple[ModRow, ...]:
    """Łączy wynik skanowania ze stanem wdrożeń, także modów usuniętych z biblioteki."""
    statuses = {item.mod_id: item for item in status.mods}
    rows: list[ModRow] = []
    seen: set[str] = set()
    for mod in scan.mods:
        item = statuses.get(mod.mod_id)
        warnings = list(item.warnings if item else ())
        warnings.extend(
            issue.message for issue in mod.issues if issue.severity == "warning"
        )
        rows.append(
            ModRow(
                mod_id=mod.mod_id,
                name=mod.display_name,
                category=mod.category or "Bez kategorii",
                status=item.status if item else "wyłączony",
                file_count=item.file_count if item else len(mod.files),
                broken_count=item.broken_count if item else 0,
                warnings=tuple(dict.fromkeys(warnings)),
                source_root=str(mod.source_root),
                target_paths=tuple(
                    _full_target_path(mod_file.target_rel, game_root)
                    for mod_file in mod.files
                ),
            )
        )
        seen.add(mod.mod_id)

    for item in status.mods:
        if item.mod_id in seen:
            continue
        rows.append(
            ModRow(
                mod_id=item.mod_id,
                name=item.name,
                category=item.category or "Brak w bibliotece",
                status=item.status,
                file_count=item.file_count,
                broken_count=item.broken_count,
                warnings=item.warnings,
                source_root=(
                    state.mods[item.mod_id].source_root
                    if state is not None and item.mod_id in state.mods
                    else ""
                ),
                target_paths=(
                    tuple(
                        _full_target_path(target_rel, game_root)
                        for target_rel in state.mods[item.mod_id].files
                    )
                    if state is not None and item.mod_id in state.mods
                    else ()
                ),
            )
        )
    return tuple(sorted(rows, key=lambda row: (row.category.casefold(), row.name.casefold())))


def filter_mod_rows(rows: Iterable[ModRow], query: str) -> tuple[ModRow, ...]:
    """Filtruje mody po nazwie, kategorii, ID, statusie i ostrzeżeniach."""
    token = query.strip().casefold()
    if not token:
        return tuple(rows)
    return tuple(
        row
        for row in rows
        if token
        in " ".join(
            (row.name, row.category, row.mod_id, row.status, *row.warnings)
        ).casefold()
    )


def toggle_visible_selection(
    selected: Iterable[str], visible: Iterable[str]
) -> set[str]:
    """Zaznacza widoczne mody albo odznacza je, gdy wszystkie są już zaznaczone."""
    current = set(selected)
    shown = set(visible)
    if shown and shown.issubset(current):
        return current - shown
    return current | shown


@dataclass(frozen=True)
class _Workspace:
    scan: ScanResult
    status: StatusReport
    state: AppState | None = None
    game_root: Path | None = None


@dataclass(frozen=True)
class _OperationResult:
    reports: tuple[OperationReport, ...]
    workspace: _Workspace


class FH6LinkerApp:
    """Okno główne: skan, filtrowanie, wybór modów i bezpieczne operacje."""

    def __init__(self, root: Any, engine: LinkerEngine | None = None) -> None:
        import tkinter as tk
        from tkinter import messagebox, ttk

        self.tk = tk
        self.ttk = ttk
        self.messagebox = messagebox
        self.root = root
        self.engine = engine or LinkerEngine()
        self.store = self.engine.store
        self._events: queue.Queue[tuple[str, str, Any, Any]] = queue.Queue()
        self._busy = False
        self._closed = False
        self._rows: tuple[ModRow, ...] = ()
        self._rows_by_id: dict[str, ModRow] = {}
        self._visible_mod_ids: list[str] = []
        self._active_mod_ids: set[str] = set()
        self._available_mod_ids: set[str] = set()
        self._desired_mod_ids: set[str] = set()
        self._sort_column = "name"
        self._sort_reverse = False
        self._action_buttons: list[Any] = []
        self._folder_open_buttons: list[Any] = []
        self._selection_widgets: list[Any] = []
        self._localized_widgets: list[tuple[Any, str, str]] = []
        self.language = load_language(self.store.config_dir)
        self._menu_objects: list[Any] = []
        self._tooltip_job: str | None = None
        self._tooltip_window: Any | None = None
        self._tooltip_mod_id: str | None = None

        self.root.title(self._t("window_title"))
        self.root.geometry("1280x850")
        self.root.minsize(980, 700)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        configure_theme(self.root, ttk)
        self._build_menu()
        self._build_ui()
        self._schedule_event_poll()
        self.root.after(0, self._validate_startup)

    def _t(self, key: str, **values: Any) -> str:
        return translate(self.language, key, **values)

    def _register_text(self, widget: Any, key: str, option: str = "text") -> Any:
        self._localized_widgets.append((widget, key, option))
        widget.configure(**{option: self._t(key)})
        return widget

    def _label(self, parent: Any, key: str, **options: Any) -> Any:
        return self._register_text(
            self.ttk.Label(parent, **options),
            key,
        )

    def _button(
        self,
        parent: Any,
        key: str,
        command: Callable[[], None],
        *,
        style: str = "TButton",
        **options: Any,
    ) -> Any:
        return self._register_text(
            self.ttk.Button(parent, command=command, style=style, **options),
            key,
        )

    def _set_language(self, language: str) -> None:
        """Applies and persists the selected UI language."""
        selected = normalize_language(language)
        if selected == self.language:
            return
        self.language = selected
        if hasattr(self, "language_var"):
            self.language_var.set(LANGUAGE_LABELS[selected])
        try:
            save_language(self.store.config_dir, selected)
        except OSError as exc:
            self._append_log(self._t("language_save_error", error=exc))
        self.root.title(self._t("window_title"))
        self._build_menu()
        for widget, key, option in self._localized_widgets:
            try:
                widget.configure(**{option: self._t(key)})
            except self.tk.TclError:
                continue
        self._update_tree_headings()
        self._render_tree()
        self._update_path_label()

    def _on_language_selected(self, _event: Any = None) -> None:
        self._set_language(language_from_label(self.language_var.get()))

    def _build_menu(self) -> None:
        menu_style = {
            "tearoff": False,
            "background": COLORS["surface"],
            "foreground": COLORS["text"],
            "activebackground": COLORS["selection"],
            "activeforeground": COLORS["text"],
            "disabledforeground": COLORS["muted"],
            "borderwidth": 0,
            "relief": "flat",
        }
        for old_menu in self._menu_objects:
            try:
                old_menu.destroy()
            except self.tk.TclError:
                pass
        self._menu_objects = []
        menu = self.tk.Menu(self.root, **menu_style)
        application = self.tk.Menu(menu, **menu_style)
        application.add_command(label=self._t("menu_setup"), command=self.open_setup)
        application.add_separator()
        application.add_command(label=self._t("menu_close"), command=self._on_close)
        menu.add_cascade(label=self._t("menu_application"), menu=application)
        help_menu = self.tk.Menu(menu, **menu_style)
        help_menu.add_command(
            label=self._t("menu_about"),
            command=lambda: show_about(self.root, __version__, language=self.language),
        )
        menu.add_cascade(label=self._t("menu_help"), menu=help_menu)
        self._menu_objects.extend((menu, application, help_menu))
        self.root.configure(menu=menu)

    def _build_ui(self) -> None:
        ttk = self.ttk
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main = ttk.Frame(self.root, style="App.TFrame", padding=(20, 16))
        main.grid(row=0, column=0, sticky="nsew")
        main.columnconfigure(0, weight=1)
        main.rowconfigure(6, weight=1)

        # Nagłówek
        header = ttk.Frame(main, style="App.TFrame")
        header.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        header.columnconfigure(0, weight=1)
        brand = ttk.Frame(header, style="App.TFrame")
        brand.grid(row=0, column=0, sticky="w")
        ttk.Label(brand, text="FH6", style="BrandMark.TLabel").grid(
            row=0, column=0, rowspan=2, sticky="nsw", padx=(0, 12)
        )
        ttk.Label(brand, text="FH6 Addon Linker", style="Title.TLabel").grid(
            row=0, column=1, sticky="sw"
        )
        self._label(
            brand,
            "header_subtitle",
            style="Subtitle.TLabel",
        ).grid(row=1, column=1, sticky="nw", pady=(1, 0))
        self._label(header, "local_badge", style="Badge.TLabel").grid(
            row=0, column=1, sticky="e", padx=(8, 10)
        )
        self.language_var = self.tk.StringVar(
            master=self.root,
            value=LANGUAGE_LABELS[self.language],
        )
        self.language_combo = ttk.Combobox(
            header,
            textvariable=self.language_var,
            values=(LANGUAGE_LABELS["pl"], LANGUAGE_LABELS["en"]),
            state="readonly",
            width=10,
        )
        self.language_combo.grid(row=0, column=2, rowspan=2, sticky="e", padx=(0, 8))
        self.language_combo.bind("<<ComboboxSelected>>", self._on_language_selected)
        self._action_buttons.append(self.language_combo)
        setup_button = self._button(header, "setup_button", self.open_setup)
        setup_button.grid(row=0, column=3, rowspan=2, sticky="e")
        self._action_buttons.append(setup_button)

        # Ostrzeżenie bezpieczeństwa jest stale widoczne, ale nie konkuruje
        # wizualnie z głównymi akcjami.
        self._label(
            main,
            "safety_banner",
            style="Banner.TLabel",
            wraplength=1120,
            justify="left",
        ).grid(row=1, column=0, sticky="ew", pady=(0, 10))

        # Ścieżki w trzech równych kartach są łatwiejsze do odczytania niż
        # jedna długa linia, która wcześniej ucinała się przy długich folderach.
        self.paths_var = self.tk.StringVar(master=self.root, value=self._t("status_config_missing"))
        self.game_path_var = self.tk.StringVar(master=self.root, value="—")
        self.library_path_var = self.tk.StringVar(master=self.root, value="—")
        self.backup_path_var = self.tk.StringVar(master=self.root, value="—")
        paths = ttk.Frame(main, style="Card.TFrame", padding=(13, 10))
        paths.grid(row=2, column=0, sticky="ew", pady=(0, 10))
        for column in range(3):
            paths.columnconfigure(column, weight=1, uniform="paths")
        for column, (heading_key, variable, folder_kind) in enumerate(
            (
                ("path_game", self.game_path_var, "game"),
                ("path_library", self.library_path_var, "library"),
                ("path_backups", self.backup_path_var, "backup"),
            )
        ):
            item = ttk.Frame(paths, style="Card.TFrame")
            item.grid(row=0, column=column, sticky="nsew", padx=(0 if column == 0 else 14, 0))
            item.columnconfigure(0, weight=1)
            self._label(item, heading_key, style="PathHeading.TLabel").grid(
                row=0, column=0, columnspan=2, sticky="w", pady=(0, 4)
            )
            ttk.Label(
                item,
                textvariable=variable,
                style="PathValue.TLabel",
                wraplength=245,
                justify="left",
            ).grid(row=1, column=0, sticky="ew", padx=(0, 8))
            open_button = self._button(
                item,
                "open_folder",
                lambda kind=folder_kind: self._open_configured_folder(kind),
                style="Compact.TButton",
                width=13,
            )
            open_button.grid(row=1, column=1, sticky="e")
            self._folder_open_buttons.append(open_button)
            self._action_buttons.append(open_button)

        # Małe podsumowanie stanu biblioteki.
        metrics = ttk.Frame(main, style="App.TFrame")
        metrics.grid(row=3, column=0, sticky="ew", pady=(0, 10))
        for column in range(3):
            metrics.columnconfigure(column, weight=1, uniform="metrics")
        self.total_mods_var = self.tk.StringVar(master=self.root, value="—")
        self.active_mods_var = self.tk.StringVar(master=self.root, value="—")
        self.attention_mods_var = self.tk.StringVar(master=self.root, value="—")
        for column, (heading_key, value, style_name) in enumerate(
            (
                ("metric_library", self.total_mods_var, "MetricValue.TLabel"),
                ("metric_active", self.active_mods_var, "MetricActive.TLabel"),
                ("metric_attention", self.attention_mods_var, "MetricAlert.TLabel"),
            )
        ):
            card = ttk.Frame(metrics, style="Metric.TFrame", padding=(14, 9))
            card.grid(
                row=0,
                column=column,
                sticky="ew",
                padx=(0 if column == 0 else 8, 0),
            )
            self._label(card, heading_key, style="MetricLabel.TLabel").grid(
                row=0, column=0, sticky="w"
            )
            ttk.Label(card, textvariable=value, style=style_name).grid(
                row=1, column=0, sticky="w", pady=(1, 0)
            )

        # Główne operacje
        primary = ttk.Frame(main, style="App.TFrame")
        primary.grid(row=4, column=0, sticky="ew", pady=(0, 6))
        for column in range(5):
            primary.columnconfigure(column, weight=1, uniform="primary-actions")
        self.enable_all_button = self._add_action_button(
            primary,
            "action_enable_all",
            self.enable_all,
            "TButton",
            column=0,
        )
        self._add_action_button(
            primary,
            "action_apply_selected",
            self.apply_selection,
            "Accent.TButton",
            column=1,
        )
        self._add_action_button(
            primary,
            "action_disable_all",
            self.disable_all,
            "TButton",
            column=2,
        )
        self._add_action_button(
            primary,
            "action_restore",
            self.restore_all,
            "TButton",
            column=3,
        )
        self._add_action_button(
            primary,
            "action_online",
            self.online_mode,
            "Danger.TButton",
            column=4,
        )

        secondary = ttk.Frame(main, style="App.TFrame")
        secondary.grid(row=5, column=0, sticky="ew", pady=(0, 8))
        self._add_action_button(secondary, "action_verify", self.verify_selected)
        self._add_action_button(secondary, "action_repair", self.repair_selected)
        self._add_action_button(secondary, "action_refresh", self.refresh)

        # Filtr i tabela
        filter_bar = ttk.Frame(main, style="App.TFrame")
        filter_bar.grid(row=6, column=0, sticky="nsew")
        filter_bar.columnconfigure(0, weight=1)
        filter_bar.rowconfigure(1, weight=1)
        filter_row = ttk.Frame(filter_bar, style="App.TFrame")
        filter_row.grid(row=0, column=0, sticky="ew", pady=(0, 7))
        filter_row.columnconfigure(1, weight=1)
        self._label(filter_row, "search_mods", style="Eyebrow.TLabel").grid(
            row=0, column=0, sticky="w", padx=(0, 10)
        )
        self.filter_var = self.tk.StringVar(master=self.root)
        self.filter_entry = ttk.Entry(filter_row, textvariable=self.filter_var)
        self.filter_entry.grid(row=0, column=1, sticky="ew", padx=(0, 8))
        self._selection_widgets.append(self.filter_entry)
        self.filter_entry.bind("<KeyRelease>", lambda _event: self._render_tree())
        self.filter_entry.bind("<Escape>", self._clear_filter)
        self.visible_button = self._button(
            filter_row,
            "select_visible",
            self.toggle_visible,
        )
        self.visible_button.grid(row=0, column=2, sticky="e", padx=(0, 6))
        self.clear_selection_button = self._button(
            filter_row,
            "clear_selection",
            self.clear_visible,
        )
        self.clear_selection_button.grid(row=0, column=3, sticky="e")
        self._selection_widgets.extend((self.visible_button, self.clear_selection_button))

        tree_frame = ttk.Frame(filter_bar, style="Card.TFrame")
        tree_frame.grid(row=1, column=0, sticky="nsew")
        tree_frame.columnconfigure(0, weight=1)
        tree_frame.rowconfigure(0, weight=1)
        columns = ("choice", "active", "files", "status", "warnings")
        self.tree = ttk.Treeview(
            tree_frame,
            columns=columns,
            show=("tree", "headings"),
            selectmode="browse",
        )
        self._selection_widgets.append(self.tree)
        self._tree_heading_keys = {
            "#0": "tree_mod",
            "choice": "tree_choice",
            "active": "tree_active",
            "files": "tree_files",
            "status": "tree_status",
            "warnings": "tree_notes",
        }
        self.tree.heading("#0", anchor="w", command=lambda: self._sort("name"))
        self.tree.heading("choice", anchor="center")
        self.tree.heading("active", anchor="center", command=lambda: self._sort("active"))
        self.tree.heading("files", anchor="center", command=lambda: self._sort("files"))
        self.tree.heading("status", anchor="center", command=lambda: self._sort("status"))
        self.tree.heading("warnings", anchor="w", command=lambda: self._sort("warnings"))
        self._update_tree_headings()
        self.tree.column("#0", width=260, minwidth=170, stretch=True)
        self.tree.column("choice", width=65, minwidth=58, stretch=False, anchor="center")
        self.tree.column("active", width=78, minwidth=68, stretch=False, anchor="center")
        self.tree.column("files", width=62, minwidth=54, stretch=False, anchor="center")
        self.tree.column("status", width=112, minwidth=96, stretch=False, anchor="center")
        self.tree.column("warnings", width=360, minwidth=150, stretch=True)
        self.tree.tag_configure("enabled", foreground=COLORS["success"])
        self.tree.tag_configure("partial", foreground=COLORS["warning"])
        self.tree.tag_configure("broken", foreground=COLORS["danger"])
        self.tree.tag_configure("disabled", foreground=COLORS["muted"])
        self.tree.tag_configure("category", font=("Segoe UI Semibold", 9))
        y_scroll = self.ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        x_scroll = self.ttk.Scrollbar(tree_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=y_scroll.set, xscrollcommand=x_scroll.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        y_scroll.grid(row=0, column=1, sticky="ns")
        x_scroll.grid(row=1, column=0, sticky="ew")
        self.empty_state = ttk.Label(
            tree_frame,
            text=self._t("status_loading"),
            style="Empty.TLabel",
            anchor="center",
            justify="center",
            wraplength=560,
        )
        self.empty_state.place(relx=0.5, rely=0.5, anchor="center")
        self.tree.bind("<Button-1>", self._on_tree_click)
        self.tree.bind("<Double-1>", self._on_tree_double_click)
        self.tree.bind("<space>", self._toggle_focused)
        self.tree.bind("<Motion>", self._on_tree_motion)
        self.tree.bind("<Leave>", lambda _event: self._hide_tooltip())

        log_header = ttk.Frame(main, style="App.TFrame")
        log_header.grid(row=7, column=0, sticky="ew", pady=(10, 5))
        log_header.columnconfigure(0, weight=1)
        self._label(log_header, "log_header", font=("Segoe UI Semibold", 10)).grid(
            row=0, column=0, sticky="w"
        )
        self._button(log_header, "copy_log", self._copy_log).grid(
            row=0, column=1, sticky="e"
        )
        log_frame = ttk.Frame(main, style="Card.TFrame")
        log_frame.grid(row=8, column=0, sticky="ew")
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        self.log = self.tk.Text(
            log_frame,
            height=5,
            wrap="word",
            relief="flat",
            borderwidth=0,
            padx=10,
            pady=8,
            font=("Consolas", 9),
            background=COLORS["surface"],
            foreground=COLORS["text"],
            insertbackground=COLORS["text"],
            selectbackground=COLORS["selection"],
            selectforeground=COLORS["text"],
            state="disabled",
        )
        log_scroll = self.ttk.Scrollbar(log_frame, orient="vertical", command=self.log.yview)
        self.log.configure(yscrollcommand=log_scroll.set)
        self.log.grid(row=0, column=0, sticky="nsew")
        log_scroll.grid(row=0, column=1, sticky="ns")
        self.log.bind("<Control-c>", self._copy_log_event)
        self.log.bind("<Control-C>", self._copy_log_event)

        footer = ttk.Frame(main, style="App.TFrame")
        footer.grid(row=9, column=0, sticky="ew", pady=(8, 0))
        footer.columnconfigure(0, weight=1)
        self.status_var = self.tk.StringVar(master=self.root, value=self._t("status_ready"))
        ttk.Label(footer, textvariable=self.status_var, style="Subtitle.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        self.progress = ttk.Progressbar(footer, mode="indeterminate", length=150)
        self.progress.grid(row=0, column=1, sticky="e")

        self.root.bind("<F5>", lambda _event: self.refresh())
        self.root.bind("<Control-f>", self._focus_filter)
        self.root.bind("<Control-F>", self._focus_filter)
        self.root.bind("<Control-Return>", lambda _event: self.apply_selection())
        self._append_log(self._t("log_startup"))

    def _add_action_button(
        self,
        parent: Any,
        label_key: str,
        command: Callable[[], None],
        style: str = "TButton",
        *,
        column: int | None = None,
    ) -> Any:
        button = self._button(parent, label_key, command, style=style)
        if column is None:
            button.pack(side="left", padx=(0, 6))
        else:
            button.grid(row=0, column=column, sticky="ew", padx=(0 if column == 0 else 6, 6))
        self._action_buttons.append(button)
        return button

    def _validate_startup(self) -> None:
        try:
            from ..paths import validate_config

            validate_config(
                self.store.load_config(),
                default_backup_dir=self.store.config_dir / "backups",
            )
        except (OSError, ValueError, StateError, RuntimeError) as exc:
            self._append_log(self._t("log_config_required", error=exc))
            self.open_setup(startup=True)
            return
        self.refresh()

    def open_setup(self, *, startup: bool = False) -> None:
        """Otwiera kreator; po pierwszym uruchomieniu wymaga poprawnej konfiguracji."""
        if self._busy:
            self.messagebox.showinfo(
                self._t("busy_title"),
                self._t("busy_setup_body"),
                parent=self.root,
            )
            return
        from .wizard import SetupWizard

        wizard = SetupWizard(
            self.root,
            self.engine,
            on_saved=self._after_setup_saved,
            language=self.language,
        )
        self.root.wait_window(wizard.window)
        if wizard.saved:
            self._append_log(self._t("log_config_saved"))
        elif startup:
            self.root.after_idle(self.root.destroy)

    def _after_setup_saved(self) -> None:
        self._update_path_label()
        self.refresh()

    def refresh(self) -> None:
        """Skanuje bibliotekę i odczytuje status bez blokowania okna."""
        self._start_task(self._t("status_scanning"), self._load_workspace, self._show_workspace)

    def _load_workspace(self) -> _Workspace:
        scan = self.engine.scan()
        status = self.engine.status()
        try:
            state = self.store.load_state()
        except StateError:
            state = None
        config = self.store.load_config()
        return _Workspace(
            scan=scan,
            status=status,
            state=state,
            game_root=config.game_root,
        )

    def _show_workspace(self, workspace: _Workspace) -> None:
        self._update_path_label()
        self._rows = build_mod_rows(
            workspace.scan,
            workspace.status,
            workspace.state,
            game_root=workspace.game_root,
        )
        self._rows_by_id = {row.mod_id: row for row in self._rows}
        self._active_mod_ids = {
            row.mod_id for row in self._rows if row.status.casefold() != "wyłączony"
        }
        self._available_mod_ids = {
            mod.mod_id for mod in workspace.scan.mods if mod.valid
        }
        self._desired_mod_ids = set(self._active_mod_ids)
        self.total_mods_var.set(str(len(self._rows)))
        self.active_mods_var.set(str(len(self._active_mod_ids)))
        attention_count = sum(
            1
            for row in self._rows
            if row.broken_count
            or row.status.casefold() in {"zerwany", "częściowy"}
            or row.warnings
        )
        self.attention_mods_var.set(str(attention_count))
        self._render_tree()
        for issue in workspace.scan.issues:
            key = "report_error" if issue.severity == "error" else "report_warning"
            self._append_log(self._t(key, message=issue.message))
        for error in workspace.status.errors:
            self._append_log(self._t("report_error", message=error))
        if workspace.scan.errors:
            self.status_var.set(self._t("status_scan_errors", count=len(workspace.scan.errors)))
        elif workspace.status.errors:
            self.status_var.set(self._t("status_status_errors"))
        else:
            self.status_var.set(self._t("status_found_mods", count=len(workspace.scan.mods)))
        self._append_log(
            self._t(
                "log_scan_summary",
                mods=len(workspace.scan.mods),
                active=len(self._active_mod_ids),
            )
        )

    def _update_path_label(self) -> None:
        try:
            config = self.store.load_config()
            missing = self._t("path_not_configured")
            game = str(config.game_root) if config.game_root else missing
            library = str(config.library_dir) if config.library_dir else missing
            backup = str(config.backup_dir or (self.store.config_dir / "backups"))
            self.game_path_var.set(game)
            self.library_path_var.set(library)
            self.backup_path_var.set(backup)
            self.paths_var.set(
                self._t("path_summary", game=game, library=library, backups=backup)
            )
        except Exception as exc:
            message = self._t("path_read_error", error=exc)
            self.game_path_var.set(message)
            self.library_path_var.set("—")
            self.backup_path_var.set("—")
            self.paths_var.set(message)

    def _open_configured_folder(self, kind: str) -> None:
        """Opens one of the configured game, library, or backup directories."""
        try:
            config = self.store.load_config()
            if kind == "game":
                path = config.game_root
                label_key = "folder_kind_game"
            elif kind == "library":
                path = config.library_dir
                label_key = "folder_kind_library"
            elif kind == "backup":
                path = config.backup_dir or (self.store.config_dir / "backups")
                label_key = "folder_kind_backup"
            else:
                raise ValueError(f"Unknown folder kind: {kind}")
        except (OSError, ValueError, StateError) as exc:
            self.messagebox.showerror(
                self._t("folder_open_error_title"),
                self._t("folder_open_error_body", path=kind, error=exc),
                parent=self.root,
            )
            return

        if path is None:
            self.messagebox.showerror(
                self._t("folder_missing_title"),
                self._t("folder_not_configured_body", folder=self._t(label_key)),
                parent=self.root,
            )
            return
        directory = Path(path).expanduser()
        if not directory.is_dir():
            if kind == "backup":
                create = self.messagebox.askyesno(
                    self._t("backup_create_title"),
                    self._t("backup_create_body", path=directory),
                    parent=self.root,
                )
                if not create:
                    return
                try:
                    directory.mkdir(parents=True, exist_ok=True)
                except OSError as exc:
                    self.messagebox.showerror(
                        self._t("folder_open_error_title"),
                        self._t("folder_open_error_body", path=directory, error=exc),
                        parent=self.root,
                    )
                    return
            else:
                self.messagebox.showerror(
                    self._t("folder_missing_title"),
                    self._t("folder_missing_body", path=directory),
                    parent=self.root,
                )
                return
        try:
            open_directory(directory)
        except (OSError, subprocess.SubprocessError, ValueError) as exc:
            self.messagebox.showerror(
                self._t("folder_open_error_title"),
                self._t("folder_open_error_body", path=directory, error=exc),
                parent=self.root,
            )

    def _update_tree_headings(self) -> None:
        if not hasattr(self, "tree"):
            return
        for column, key in getattr(self, "_tree_heading_keys", {}).items():
            self.tree.heading(column, text=self._t(key))

    def _display_status(self, status: str) -> str:
        normalized = status.casefold()
        key_by_status = {
            "włączony": "state_enabled",
            "częściowy": "state_partial",
            "zerwany": "state_broken",
            "wyłączony": "state_disabled",
        }
        key = key_by_status.get(normalized)
        return self._t(key) if key else status

    def _render_tree(self) -> None:
        self.tree.delete(*self.tree.get_children(""))
        query = self.filter_var.get() if hasattr(self, "filter_var") else ""
        rows = list(filter_mod_rows(self._rows, query))
        rows.sort(key=self._row_sort_key, reverse=self._sort_reverse)
        categories: dict[tuple[str, ...], str] = {}
        self._visible_mod_ids = []

        for row in rows:
            segments = tuple(
                segment for segment in (row.category or "Bez kategorii").split("/") if segment
            )
            parent = ""
            prefix: list[str] = []
            for segment in segments:
                prefix.append(segment.casefold())
                key = tuple(prefix)
                category_iid = categories.get(key)
                if category_iid is None:
                    category_iid = f"category-{len(categories)}"
                    categories[key] = category_iid
                    self.tree.insert(
                        parent,
                        "end",
                        iid=category_iid,
                        text=segment,
                        values=("", "", "", "", ""),
                        tags=("category",),
                        open=True,
                    )
                parent = category_iid

            iid = f"mod:{row.mod_id}"
            active = row.mod_id in self._active_mod_ids
            checked = row.mod_id in self._desired_mod_ids
            warning = " · ".join(row.warnings)
            if len(warning) > 150:
                warning = warning[:147] + "…"
            self.tree.insert(
                parent,
                "end",
                iid=iid,
                text=row.name,
                values=("☑" if checked else "☐", self._t("value_yes") if active else self._t("value_no"), row.file_count, self._display_status(row.status), warning),
                tags=(self._status_tag(row.status),),
            )
            self._visible_mod_ids.append(row.mod_id)

        if not rows:
            if self._rows:
                empty_text = self._t("empty_filter", query=query)
            else:
                empty_text = self._t("empty_library")
            self.empty_state.configure(text=empty_text)
            self.empty_state.place(relx=0.5, rely=0.5, anchor="center")
        else:
            self.empty_state.place_forget()

        all_visible_selected = bool(self._visible_mod_ids) and set(
            self._visible_mod_ids
        ).issubset(self._desired_mod_ids)
        self.visible_button.configure(
            text=self._t("deselect_visible" if all_visible_selected else "select_visible"),
            state="normal" if self._visible_mod_ids else "disabled",
        )
        has_visible_selection = bool(set(self._visible_mod_ids) & self._desired_mod_ids)
        self.clear_selection_button.configure(
            state="normal" if has_visible_selection else "disabled"
        )

    def _row_sort_key(self, row: ModRow) -> Any:
        if self._sort_column == "active":
            return (row.mod_id in self._active_mod_ids, row.category.casefold(), row.name.casefold())
        if self._sort_column == "files":
            return (row.file_count, row.category.casefold(), row.name.casefold())
        if self._sort_column == "status":
            return (row.status.casefold(), row.category.casefold(), row.name.casefold())
        if self._sort_column == "warnings":
            return (len(row.warnings), row.category.casefold(), row.name.casefold())
        return (row.category.casefold(), row.name.casefold())

    def _sort(self, column: str) -> None:
        if self._sort_column == column:
            self._sort_reverse = not self._sort_reverse
        else:
            self._sort_column = column
            self._sort_reverse = False
        self._render_tree()

    @staticmethod
    def _status_tag(status: str) -> str:
        normalized = status.casefold()
        if normalized == "włączony":
            return "enabled"
        if normalized == "częściowy":
            return "partial"
        if normalized == "zerwany":
            return "broken"
        return "disabled"

    def _on_tree_click(self, event: Any) -> str | None:
        region = self.tree.identify("region", event.x, event.y)
        iid = self.tree.identify_row(event.y)
        column = self.tree.identify_column(event.x)
        if region == "cell" and column == "#1" and iid.startswith("mod:"):
            self._toggle_mod(iid[4:])
            return "break"
        return None

    def _on_tree_double_click(self, event: Any) -> None:
        iid = self.tree.identify_row(event.y)
        if iid.startswith("mod:"):
            self._show_details(iid[4:])

    def _toggle_focused(self, _event: Any = None) -> str:
        selection = self.tree.selection()
        if selection and selection[0].startswith("mod:"):
            self._toggle_mod(selection[0][4:])
        return "break"

    def _toggle_mod(self, mod_id: str) -> None:
        if mod_id in self._desired_mod_ids:
            self._desired_mod_ids.remove(mod_id)
        else:
            self._desired_mod_ids.add(mod_id)
        self._render_tree()

    def toggle_visible(self) -> None:
        self._desired_mod_ids = toggle_visible_selection(
            self._desired_mod_ids,
            self._visible_mod_ids,
        )
        self._render_tree()

    def clear_visible(self) -> None:
        self._desired_mod_ids.difference_update(self._visible_mod_ids)
        self._render_tree()

    def _show_details(self, mod_id: str) -> None:
        row = self._rows_by_id.get(mod_id)
        if row is None:
            return
        warnings = "\n".join(f"• {warning}" for warning in row.warnings) or self._t("details_no_warnings")
        targets = "\n".join(f"• {path}" for path in row.target_paths[:20])
        if len(row.target_paths) > 20:
            targets += "\n" + self._t("details_more_files", count=len(row.target_paths) - 20)
        details = (
            f"{self._t('details_id')}: {row.mod_id}\n"
            f"{self._t('details_category')}: {row.category}\n"
            f"{self._t('status_details')}: {self._display_status(row.status)}\n"
            f"{self._t('details_files')}: {row.file_count} "
            f"({self._t('details_broken')}: {row.broken_count})\n"
            f"{self._t('details_source')}: {row.source_root or self._t('details_none')}\n\n"
            f"{self._t('details_targets')}:\n{targets or self._t('details_none')}"
            f"\n\n{self._t('details_notes')}:\n{warnings}"
        )
        show_mod_details(self.root, row.name, details)

    def _on_tree_motion(self, event: Any) -> None:
        iid = self.tree.identify_row(event.y)
        if not iid.startswith("mod:"):
            self._hide_tooltip()
            return
        mod_id = iid[4:]
        if mod_id == self._tooltip_mod_id or mod_id not in self._rows_by_id:
            return
        self._hide_tooltip()
        self._tooltip_mod_id = mod_id
        x_root, y_root = event.x_root, event.y_root
        self._tooltip_job = self.root.after(
            650,
            lambda: self._show_tooltip(mod_id, x_root, y_root),
        )

    def _show_tooltip(self, mod_id: str, x_root: int, y_root: int) -> None:
        self._tooltip_job = None
        row = self._rows_by_id.get(mod_id)
        if row is None:
            return
        targets = "\n".join(row.target_paths[:8])
        if len(row.target_paths) > 8:
            targets += "\n" + self._t("details_more_paths", count=len(row.target_paths) - 8)
        text = (
            f"{row.name}  ·  {self._display_status(row.status)}\n"
            f"{self._t('details_id')}: {row.mod_id}\n"
            f"{self._t('details_source')}: {row.source_root or self._t('details_none')}\n"
            f"{self._t('details_targets')}:\n{targets or self._t('details_none')}"
        )
        tooltip = self.tk.Toplevel(self.root)
        tooltip.wm_overrideredirect(True)
        label = self.tk.Label(
            tooltip,
            text=text,
            justify="left",
            anchor="w",
            wraplength=700,
            padx=9,
            pady=7,
            background=COLORS["tooltip_bg"],
            foreground=COLORS["text"],
            relief="solid",
            borderwidth=1,
            font=("Segoe UI", 9),
        )
        label.pack()
        tooltip.update_idletasks()
        x = min(x_root + 14, self.root.winfo_screenwidth() - tooltip.winfo_reqwidth() - 8)
        y = min(y_root + 16, self.root.winfo_screenheight() - tooltip.winfo_reqheight() - 8)
        tooltip.geometry(f"+{max(0, x)}+{max(0, y)}")
        self._tooltip_window = tooltip

    def _hide_tooltip(self) -> None:
        self._tooltip_mod_id = None
        if self._tooltip_job is not None:
            try:
                self.root.after_cancel(self._tooltip_job)
            except self.tk.TclError:
                pass
            self._tooltip_job = None
        if self._tooltip_window is not None:
            try:
                self._tooltip_window.destroy()
            except self.tk.TclError:
                pass
            self._tooltip_window = None

    def enable_all(self) -> None:
        """Plans activation of every valid, currently disabled library mod."""
        names = sorted(self._available_mod_ids - self._active_mod_ids)
        if not names:
            if self._available_mod_ids:
                title_key, body_key = "enable_all_title", "enable_all_done_body"
            else:
                title_key, body_key = "enable_all_none_title", "enable_all_none_body"
            self.messagebox.showinfo(
                self._t(title_key),
                self._t(body_key),
                parent=self.root,
            )
            return
        self._plan_then_confirm(
            self._t("enable_all_title"),
            lambda: [self.engine.enable(names, dry_run=True)],
            lambda: [self.engine.enable(names)],
            allow_conflicts=False,
        )

    def apply_selection(self) -> None:
        desired = set(self._desired_mod_ids)
        current = set(self._active_mod_ids)
        to_enable = sorted(desired - current)
        to_disable = sorted(current - desired)
        if not to_enable and not to_disable:
            self._append_log(self._t("selection_no_change"))
            return

        def plan() -> list[OperationReport]:
            reports: list[OperationReport] = []
            if to_enable:
                reports.append(self.engine.enable(to_enable, dry_run=True))
            if to_disable:
                reports.append(self.engine.disable(to_disable, dry_run=True))
            return reports

        def execute() -> list[OperationReport]:
            reports: list[OperationReport] = []
            if to_enable:
                reports.append(self.engine.enable(to_enable))
            if to_disable:
                reports.append(self.engine.disable(to_disable))
            return reports

        self._plan_then_confirm(
            self._t("action_apply_selected"),
            plan,
            execute,
            allow_conflicts=False,
        )

    def disable_all(self) -> None:
        names = sorted(self._active_mod_ids)
        if not names:
            self.messagebox.showinfo(
                self._t("disable_none_title"),
                self._t("disable_none_body"),
                parent=self.root,
            )
            return
        self._plan_then_confirm(
            self._t("disable_all_title"),
            lambda: [self.engine.disable(names, dry_run=True)],
            lambda: [self.engine.disable(names)],
            allow_conflicts=True,
        )

    def restore_all(self) -> None:
        self._restore_with_plan(self._t("restore_title"))

    def online_mode(self) -> None:
        confirmed = self.messagebox.askyesno(
            self._t("online_title"),
            self._t("online_body"),
            parent=self.root,
            icon="warning",
        )
        if confirmed:
            self._restore_with_plan(self._t("online_title"))

    def _restore_with_plan(self, title: str) -> None:
        self._plan_then_confirm(
            title,
            lambda: [self.engine.restore(dry_run=True)],
            lambda: [self.engine.restore()],
            allow_conflicts=True,
        )

    def verify_selected(self) -> None:
        names = sorted(self._desired_mod_ids & self._active_mod_ids)
        if not names:
            names = sorted(self._active_mod_ids)
        if not names:
            self.messagebox.showinfo(
                self._t("no_mods_title"),
                self._t("verify_none_body"),
                parent=self.root,
            )
            return

        def verify() -> list[OperationReport]:
            reports = [self.engine.verify(names)]
            return reports

        self._run_operation(self._t("verify_progress"), verify)

    def repair_selected(self) -> None:
        names = sorted(self._desired_mod_ids & self._active_mod_ids)
        if not names:
            names = sorted(
                row.mod_id
                for row in self._rows
                if row.status.casefold() in {"zerwany", "częściowy"}
            )
        if not names:
            self.messagebox.showinfo(
                self._t("repair_none_title"),
                self._t("repair_none_body"),
                parent=self.root,
            )
            return

        self._plan_then_confirm(
            self._t("repair_title"),
            lambda: [self.engine.repair(names, dry_run=True)],
            lambda: [self.engine.repair(names)],
            allow_conflicts=False,
        )

    def _plan_then_confirm(
        self,
        title: str,
        plan: Callable[[], list[OperationReport]],
        execute: Callable[[], list[OperationReport]],
        *,
        allow_conflicts: bool,
    ) -> None:
        self._start_task(
            self._t("task_plan"),
            plan,
            lambda reports: self._show_plan_then_execute(
                title,
                reports,
                execute,
                allow_conflicts=allow_conflicts,
            ),
        )

    def _show_plan_then_execute(
        self,
        title: str,
        reports: list[OperationReport],
        execute: Callable[[], list[OperationReport]],
        *,
        allow_conflicts: bool,
    ) -> None:
        if not reports:
            self._append_log(self._t("log_no_changes"))
            return
        dialog = PlanDialog(
            self.root,
            title,
            reports,
            allow_conflicts=allow_conflicts,
            language=self.language,
        )
        if not dialog.show():
            self._append_log(self._t("log_plan_cancelled"))
            return
        self._run_operation(self._t("task_execute"), execute)

    def _run_operation(
        self,
        label: str,
        operation: Callable[[], list[OperationReport]],
    ) -> None:
        def execute_and_refresh() -> _OperationResult:
            reports = tuple(operation())
            workspace = self._load_workspace()
            return _OperationResult(reports=reports, workspace=workspace)

        self._start_task(label, execute_and_refresh, self._show_operation_result)

    def _show_operation_result(self, result: _OperationResult) -> None:
        for report in result.reports:
            self._log_report(report)
        self._show_workspace(result.workspace)
        errors = [error for report in result.reports for error in report.errors]
        conflicts = [conflict for report in result.reports for conflict in report.conflicts]
        if errors:
            self.messagebox.showerror(
                self._t("operation_error_title"),
                "\n\n".join(errors[:6]),
                parent=self.root,
            )
        elif conflicts:
            self.messagebox.showwarning(
                self._t("conflicts_title"),
                self._t("conflicts_body", conflicts="\n".join(conflicts[:6])),
                parent=self.root,
            )

    def _log_report(self, report: OperationReport) -> None:
        operation_keys = {
            "enable": "plan_operation_enable",
            "disable": "plan_operation_disable",
            "restore": "plan_operation_restore",
            "repair": "plan_operation_repair",
            "verify": "plan_operation_verify",
        }
        operation_key = operation_keys.get(report.operation.casefold())
        operation = self._t(operation_key) if operation_key else report.operation
        self._append_log(
            self._t(
                "report_summary",
                operation=operation,
                changed=report.files_changed,
                planned=report.files_planned,
                code=report.exit_code,
            )
        )
        for warning in report.warnings:
            self._append_log(self._t("report_warning", message=warning))
        for conflict in report.conflicts:
            self._append_log(self._t("report_conflict", message=conflict))
        for error in report.errors:
            self._append_log(self._t("report_error", message=error))
        if report.privilege_required:
            self._append_log(self._t("report_privilege"))

    def _set_controls_enabled(self, enabled: bool) -> None:
        """Blokuje wybory i akcje podczas skanowania lub zmiany plików."""
        state = "normal" if enabled else "disabled"
        for button in self._action_buttons:
            button.configure(state=state)
        for widget in self._selection_widgets:
            if widget is self.tree:
                widget.state(["!disabled"] if enabled else ["disabled"])
            else:
                widget.configure(state=state)

    def _start_task(
        self,
        label: str,
        work: Callable[[], Any],
        on_success: Callable[[Any], None],
    ) -> None:
        if self._busy:
            return
        self._busy = True
        self.status_var.set(label)
        self.progress.start(12)
        self._set_controls_enabled(False)

        def run() -> None:
            try:
                result = work()
            except Exception as exc:
                self._events.put(("error", label, exc, None))
            else:
                self._events.put(("success", label, result, on_success))

        threading.Thread(target=run, name="fh6linker-gui-worker", daemon=True).start()

    def _schedule_event_poll(self) -> None:
        if self._closed:
            return
        try:
            while True:
                kind, label, payload, callback = self._events.get_nowait()
                self._busy = False
                self.progress.stop()
                self._set_controls_enabled(True)
                if kind == "error":
                    self.status_var.set(self._t("task_failed_status"))
                    self._append_log(
                        self._t("task_failed_log", label=label, error=payload)
                    )
                    self.messagebox.showerror(
                        self._t("task_failed_title"),
                        str(payload),
                        parent=self.root,
                    )
                else:
                    self.status_var.set(self._t("status_ready"))
                    callback(payload)
        except queue.Empty:
            pass
        try:
            self.root.after(100, self._schedule_event_poll)
        except self.tk.TclError:
            self._closed = True

    def _append_log(self, message: str) -> None:
        if not hasattr(self, "log"):
            return
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log.configure(state="normal")
        self.log.insert("end", f"[{timestamp}] {message}\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def _copy_log(self) -> None:
        self.log.configure(state="normal")
        self.log.tag_add("sel", "1.0", "end-1c")
        self.log.event_generate("<<Copy>>")
        self.log.tag_remove("sel", "1.0", "end")
        self.log.configure(state="disabled")

    def _copy_log_event(self, _event: Any = None) -> str:
        self._copy_log()
        return "break"

    def _clear_filter(self, _event: Any = None) -> str:
        self.filter_var.set("")
        self._render_tree()
        return "break"

    def _focus_filter(self, _event: Any = None) -> str:
        self.filter_entry.focus_set()
        self.filter_entry.selection_range(0, "end")
        return "break"

    def _on_close(self) -> None:
        if self._busy:
            self.messagebox.showwarning(
                self._t("busy_title"),
                self._t("busy_close_body"),
                parent=self.root,
            )
            return
        self._closed = True
        self.root.destroy()


def main() -> int:
    """Uruchamia desktopowe GUI; tkinter jest importowany dopiero przy starcie okna."""
    try:
        import tkinter as tk
    except ImportError as exc:
        raise RuntimeError(
            "Ten interpreter Pythona nie zawiera tkinter. Zainstaluj Pythona dla Windows "
            "z obsługą Tcl/Tk i uruchom ponownie aplikację."
        ) from exc
    try:
        root = tk.Tk()
    except tk.TclError as exc:
        raise RuntimeError(f"Nie można otworzyć okna GUI: {exc}") from exc
    FH6LinkerApp(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
