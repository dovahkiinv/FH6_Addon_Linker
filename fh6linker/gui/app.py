"""Główne okno desktopowe FH6 Addon Linker."""

from __future__ import annotations

import queue
import threading
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Iterable

from .. import __version__
from ..engine import LinkerEngine
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
        self._desired_mod_ids: set[str] = set()
        self._sort_column = "name"
        self._sort_reverse = False
        self._action_buttons: list[Any] = []
        self._selection_widgets: list[Any] = []
        self._tooltip_job: str | None = None
        self._tooltip_window: Any | None = None
        self._tooltip_mod_id: str | None = None

        self.root.title("FH6 Addon Linker")
        self.root.geometry("1240x820")
        self.root.minsize(980, 660)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        configure_theme(self.root, ttk)
        self._build_menu()
        self._build_ui()
        self._schedule_event_poll()
        self.root.after(0, self._validate_startup)

    def _build_menu(self) -> None:
        menu = self.tk.Menu(self.root)
        application = self.tk.Menu(menu, tearoff=False)
        application.add_command(label="Konfiguruj foldery…", command=self.open_setup)
        application.add_separator()
        application.add_command(label="Zamknij", command=self._on_close)
        menu.add_cascade(label="Aplikacja", menu=application)
        help_menu = self.tk.Menu(menu, tearoff=False)
        help_menu.add_command(
            label="O aplikacji i ryzyku…",
            command=lambda: show_about(self.root, __version__),
        )
        menu.add_cascade(label="Pomoc", menu=help_menu)
        self.root.configure(menu=menu)

    def _build_ui(self) -> None:
        ttk = self.ttk
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main = ttk.Frame(self.root, style="App.TFrame", padding=(18, 14))
        main.grid(row=0, column=0, sticky="nsew")
        main.columnconfigure(0, weight=1)
        main.rowconfigure(5, weight=1)
        main.rowconfigure(7, weight=1)

        header = ttk.Frame(main, style="App.TFrame")
        header.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        header.columnconfigure(0, weight=1)
        ttk.Label(header, text="FH6 Addon Linker", style="Title.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        ttk.Label(
            header,
            text="Biblioteka modów · bezpieczne wdrażanie i przywracanie",
            style="Subtitle.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(2, 0))
        setup_button = ttk.Button(header, text="Ustawienia ścieżek", command=self.open_setup)
        setup_button.grid(row=0, column=1, rowspan=2, sticky="e", padx=(12, 0))
        self._action_buttons.append(setup_button)

        ttk.Label(
            main,
            text=(
                "⚠ Modyfikowanie plików FH6 może naruszać regulamin i grozić banem. "
                "Przed grą online przywróć zarządzane oryginały i zweryfikuj pliki w Xbox/Steam; "
                "aplikacja nie gwarantuje bezpieczeństwa konta."
            ),
            style="Banner.TLabel",
            wraplength=1150,
            justify="left",
        ).grid(row=1, column=0, sticky="ew", pady=(0, 9))

        self.paths_var = self.tk.StringVar(master=self.root, value="Nie skonfigurowano folderów")
        ttk.Label(main, textvariable=self.paths_var, style="Path.TLabel").grid(
            row=2, column=0, sticky="ew", pady=(0, 10)
        )

        primary = ttk.Frame(main, style="App.TFrame")
        primary.grid(row=3, column=0, sticky="ew", pady=(0, 6))
        for column in range(4):
            primary.columnconfigure(column, weight=1)
        self._add_action_button(
            primary,
            "Zastosuj zaznaczone",
            self.apply_selection,
            "Accent.TButton",
            column=0,
        )
        self._add_action_button(
            primary,
            "Wyłącz wszystkie",
            self.disable_all,
            "TButton",
            column=1,
        )
        self._add_action_button(
            primary,
            "Przywróć oryginały",
            self.restore_all,
            "TButton",
            column=2,
        )
        self._add_action_button(
            primary,
            "Tryb online · przywróć backupy",
            self.online_mode,
            "Danger.TButton",
            column=3,
        )

        secondary = ttk.Frame(main, style="App.TFrame")
        secondary.grid(row=4, column=0, sticky="ew", pady=(0, 8))
        self._add_action_button(secondary, "Sprawdź zaznaczone", self.verify_selected)
        self._add_action_button(secondary, "Napraw zaznaczone", self.repair_selected)
        self._add_action_button(secondary, "Odśwież", self.refresh)
        self.visible_button = ttk.Button(secondary, text="Zaznacz widoczne", command=self.toggle_visible)
        self.visible_button.pack(side="left", padx=(0, 6))
        self.clear_selection_button = ttk.Button(
            secondary,
            text="Wyczyść wybór",
            command=self.clear_visible,
        )
        self.clear_selection_button.pack(side="left")
        self._selection_widgets.extend((self.visible_button, self.clear_selection_button))

        filter_bar = ttk.Frame(main, style="App.TFrame")
        filter_bar.grid(row=5, column=0, sticky="nsew")
        filter_bar.columnconfigure(0, weight=1)
        filter_bar.rowconfigure(1, weight=1)
        filter_row = ttk.Frame(filter_bar, style="App.TFrame")
        filter_row.grid(row=0, column=0, sticky="ew", pady=(0, 7))
        filter_row.columnconfigure(1, weight=1)
        ttk.Label(filter_row, text="Filtruj mody").grid(row=0, column=0, sticky="w")
        self.filter_var = self.tk.StringVar(master=self.root)
        self.filter_entry = ttk.Entry(filter_row, textvariable=self.filter_var)
        self.filter_entry.grid(row=0, column=1, sticky="ew", padx=(10, 0))
        self._selection_widgets.append(self.filter_entry)
        self.filter_entry.bind("<KeyRelease>", lambda _event: self._render_tree())
        self.filter_entry.bind("<Escape>", self._clear_filter)

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
        self.tree.heading("#0", text="Mod / kategoria", anchor="w", command=lambda: self._sort("name"))
        self.tree.heading("choice", text="Wybór", anchor="center")
        self.tree.heading("active", text="Aktywny", anchor="center", command=lambda: self._sort("active"))
        self.tree.heading("files", text="Pliki", anchor="center", command=lambda: self._sort("files"))
        self.tree.heading("status", text="Stan", anchor="center", command=lambda: self._sort("status"))
        self.tree.heading("warnings", text="Uwagi", anchor="w", command=lambda: self._sort("warnings"))
        self.tree.column("#0", width=250, minwidth=170, stretch=True)
        self.tree.column("choice", width=66, minwidth=60, stretch=False, anchor="center")
        self.tree.column("active", width=78, minwidth=70, stretch=False, anchor="center")
        self.tree.column("files", width=62, minwidth=56, stretch=False, anchor="center")
        self.tree.column("status", width=116, minwidth=100, stretch=False, anchor="center")
        self.tree.column("warnings", width=430, minwidth=180, stretch=True)
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
        self.tree.bind("<Button-1>", self._on_tree_click)
        self.tree.bind("<Double-1>", self._on_tree_double_click)
        self.tree.bind("<space>", self._toggle_focused)
        self.tree.bind("<Motion>", self._on_tree_motion)
        self.tree.bind("<Leave>", lambda _event: self._hide_tooltip())

        log_header = ttk.Frame(main, style="App.TFrame")
        log_header.grid(row=6, column=0, sticky="ew", pady=(10, 5))
        log_header.columnconfigure(0, weight=1)
        ttk.Label(log_header, text="Dziennik operacji", font=("Segoe UI Semibold", 10)).grid(
            row=0, column=0, sticky="w"
        )
        ttk.Button(log_header, text="Kopiuj log", command=self._copy_log).grid(row=0, column=1, sticky="e")
        log_frame = ttk.Frame(main, style="Card.TFrame")
        log_frame.grid(row=7, column=0, sticky="nsew")
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        self.log = self.tk.Text(
            log_frame,
            height=7,
            wrap="word",
            relief="flat",
            borderwidth=0,
            padx=10,
            pady=8,
            font=("Consolas", 9),
            background=COLORS["surface"],
            foreground=COLORS["text"],
            state="disabled",
        )
        log_scroll = self.ttk.Scrollbar(log_frame, orient="vertical", command=self.log.yview)
        self.log.configure(yscrollcommand=log_scroll.set)
        self.log.grid(row=0, column=0, sticky="nsew")
        log_scroll.grid(row=0, column=1, sticky="ns")
        self.log.bind("<Control-c>", self._copy_log_event)
        self.log.bind("<Control-C>", self._copy_log_event)

        footer = ttk.Frame(main, style="App.TFrame")
        footer.grid(row=8, column=0, sticky="ew", pady=(8, 0))
        footer.columnconfigure(0, weight=1)
        self.status_var = self.tk.StringVar(master=self.root, value="Gotowe")
        ttk.Label(footer, textvariable=self.status_var, style="Subtitle.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        self.progress = ttk.Progressbar(footer, mode="indeterminate", length=150)
        self.progress.grid(row=0, column=1, sticky="e")

        self.root.bind("<F5>", lambda _event: self.refresh())
        self.root.bind("<Control-f>", self._focus_filter)
        self.root.bind("<Control-F>", self._focus_filter)
        self.root.bind("<Control-Return>", lambda _event: self.apply_selection())
        self._append_log("Uruchomiono FH6 Addon Linker. Najpierw sprawdź plan przed wdrożeniem.")

    def _add_action_button(
        self,
        parent: Any,
        label: str,
        command: Callable[[], None],
        style: str = "TButton",
        *,
        column: int | None = None,
    ) -> Any:
        button = self.ttk.Button(parent, text=label, command=command, style=style)
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
            self._append_log(f"Konfiguracja wymaga uzupełnienia: {exc}")
            self.open_setup(startup=True)
            return
        self.refresh()

    def open_setup(self, *, startup: bool = False) -> None:
        """Otwiera kreator; po pierwszym uruchomieniu wymaga poprawnej konfiguracji."""
        if self._busy:
            self.messagebox.showinfo(
                "Operacja w toku",
                "Poczekaj na zakończenie bieżącej operacji przed zmianą ścieżek.",
                parent=self.root,
            )
            return
        from .wizard import SetupWizard

        wizard = SetupWizard(self.root, self.engine, on_saved=self._after_setup_saved)
        self.root.wait_window(wizard.window)
        if wizard.saved:
            self._append_log("Zapisano konfigurację folderów.")
        elif startup:
            self.root.after_idle(self.root.destroy)

    def _after_setup_saved(self) -> None:
        self._update_path_label()
        self.refresh()

    def refresh(self) -> None:
        """Skanuje bibliotekę i odczytuje status bez blokowania okna."""
        self._start_task("Skanuję bibliotekę i sprawdzam wdrożenia…", self._load_workspace, self._show_workspace)

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
        self._desired_mod_ids = set(self._active_mod_ids)
        self._render_tree()
        for issue in workspace.scan.issues:
            self._append_log(f"{issue.severity.upper()}: {issue.message}")
        for error in workspace.status.errors:
            self._append_log(f"BŁĄD: {error}")
        if workspace.scan.errors:
            self.status_var.set(f"Skan zakończony z {len(workspace.scan.errors)} błędami")
        elif workspace.status.errors:
            self.status_var.set("Odczyt statusu zakończony z błędami")
        else:
            self.status_var.set(f"Gotowe · wykryto {len(workspace.scan.mods)} modów")
        self._append_log(
            f"Odświeżono bibliotekę: {len(workspace.scan.mods)} modów, "
            f"{len(self._active_mod_ids)} aktywnych lub wymagających uwagi."
        )

    def _update_path_label(self) -> None:
        try:
            config = self.store.load_config()
            game = str(config.game_root) if config.game_root else "?"
            library = str(config.library_dir) if config.library_dir else "?"
            backup = config.backup_dir or (self.store.config_dir / "backups")
            self.paths_var.set(f"Gra: {game}    ·    Biblioteka: {library}    ·    Backup: {backup}")
        except Exception as exc:
            self.paths_var.set(f"Nie można odczytać konfiguracji: {exc}")

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
                values=("☑" if checked else "☐", "Tak" if active else "Nie", row.file_count, row.status, warning),
                tags=(self._status_tag(row.status),),
            )
            self._visible_mod_ids.append(row.mod_id)

        if self._visible_mod_ids and set(self._visible_mod_ids).issubset(self._desired_mod_ids):
            self.visible_button.configure(text="Odznacz widoczne")
        else:
            self.visible_button.configure(text="Zaznacz widoczne")

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
        warnings = "\n".join(f"• {warning}" for warning in row.warnings) or "Brak ostrzeżeń."
        targets = "\n".join(f"• {path}" for path in row.target_paths[:20])
        if len(row.target_paths) > 20:
            targets += f"\n… i {len(row.target_paths) - 20} kolejnych plików"
        details = (
            f"ID: {row.mod_id}\nKategoria: {row.category}\nStan: {row.status}\n"
            f"Pliki: {row.file_count} (zerwane: {row.broken_count})\n"
            f"Źródło: {row.source_root or 'brak'}\n\nTargety:\n{targets or 'Brak'}"
            f"\n\nUwagi:\n{warnings}"
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
            targets += f"\n… i {len(row.target_paths) - 8} plików"
        text = (
            f"{row.name}  ·  {row.status}\nID: {row.mod_id}\n"
            f"Źródło: {row.source_root or 'brak'}\nTargety:\n{targets or 'brak'}"
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
            background="#fffbe6",
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

    def apply_selection(self) -> None:
        desired = set(self._desired_mod_ids)
        current = set(self._active_mod_ids)
        to_enable = sorted(desired - current)
        to_disable = sorted(current - desired)
        if not to_enable and not to_disable:
            self._append_log("Wybór nie wymaga zmian.")
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
            "Zastosuj zaznaczone mody",
            plan,
            execute,
            allow_conflicts=False,
        )

    def disable_all(self) -> None:
        names = sorted(self._active_mod_ids)
        if not names:
            self.messagebox.showinfo("Brak aktywnych modów", "Nie ma modów do wyłączenia.", parent=self.root)
            return
        self._plan_then_confirm(
            "Wyłącz wszystkie mody",
            lambda: [self.engine.disable(names, dry_run=True)],
            lambda: [self.engine.disable(names)],
            allow_conflicts=True,
        )

    def restore_all(self) -> None:
        self._restore_with_plan("Przywróć oryginalne pliki gry")

    def online_mode(self) -> None:
        confirmed = self.messagebox.askyesno(
            "Tryb online — przywróć backupy modów",
            "Ta operacja wyłączy zarządzane mody i przywróci zapisane kopie oryginałów.\n\n"
            "Pliki obce lub zmienione pozostaną nietknięte; w razie potrzeby użyj "
            "weryfikacji plików w Xbox/Steam.\n\n"
            "Modyfikowanie plików może naruszać regulamin i grozić banem; "
            "przywrócenie nie gwarantuje bezpieczeństwa konta.\n\n"
            "Czy przygotować plan przywrócenia?",
            parent=self.root,
            icon="warning",
        )
        if confirmed:
            self._restore_with_plan("Tryb online — przywróć backupy zarządzanych plików")

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
            self.messagebox.showinfo("Brak modów", "Nie ma wdrożonych modów do sprawdzenia.", parent=self.root)
            return

        def verify() -> list[OperationReport]:
            reports = [self.engine.verify(names)]
            return reports

        self._run_operation("Weryfikuję pliki…", verify)

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
                "Nie znaleziono zerwanych linków",
                "Zaznacz wdrożone mody albo użyj przycisku Odśwież.",
                parent=self.root,
            )
            return

        self._plan_then_confirm(
            "Napraw zaznaczone mody",
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
            "Sprawdzam pliki i przygotowuję plan…",
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
            self._append_log("Nie ma zmian do wykonania.")
            return
        dialog = PlanDialog(self.root, title, reports, allow_conflicts=allow_conflicts)
        if not dialog.show():
            self._append_log("Anulowano plan; pliki gry pozostały bez zmian.")
            return
        self._run_operation("Wykonuję zatwierdzone zmiany…", execute)

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
                "Operacja wymaga uwagi",
                "\n\n".join(errors[:6]),
                parent=self.root,
            )
        elif conflicts:
            self.messagebox.showwarning(
                "Pozostawiono konflikty",
                "Niektóre pliki nie należą do narzędzia i pozostały bez zmian:\n\n"
                + "\n".join(conflicts[:6]),
                parent=self.root,
            )

    def _log_report(self, report: OperationReport) -> None:
        self._append_log(
            f"{report.operation}: {report.files_changed} zmian, "
            f"{report.files_planned} plików w planie (kod {report.exit_code})."
        )
        for warning in report.warnings:
            self._append_log(f"UWAGA: {warning}")
        for conflict in report.conflicts:
            self._append_log(f"KONFLIKT: {conflict}")
        for error in report.errors:
            self._append_log(f"BŁĄD: {error}")
        if report.privilege_required:
            self._append_log("Wymagane są uprawnienia administratora lub Tryb dewelopera Windows.")

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
                    self.status_var.set("Operacja zakończona błędem")
                    self._append_log(f"BŁĄD ({label}): {payload}")
                    self.messagebox.showerror("Operacja nie powiodła się", str(payload), parent=self.root)
                else:
                    self.status_var.set("Gotowe")
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
                "Operacja w toku",
                "Poczekaj, aż bieżąca operacja zakończy się przed zamknięciem aplikacji.",
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
