"""Kreator konfiguracji folderu gry, biblioteki i metody linkowania."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from ..i18n import translate
from ..state import AppConfig, StateError
from .theme import COLORS


def deployment_paths_changed(
    current: AppConfig | None,
    game_root: str | Path,
    library_dir: str | Path,
    backup_dir: str | Path | None,
    *,
    default_backup_dir: Path,
) -> bool:
    """Sprawdza, czy edycja zmieni ścieżki potrzebne do odwrócenia wdrożeń."""
    if current is None or current.game_root is None or current.library_dir is None:
        return True

    def canonical(path: str | Path) -> Path:
        return Path(path).expanduser().resolve(strict=False)

    current_backup = current.backup_dir or default_backup_dir
    proposed_backup = backup_dir or default_backup_dir
    return any(
        (
            canonical(current.game_root) != canonical(game_root),
            canonical(current.library_dir) != canonical(library_dir),
            canonical(current_backup) != canonical(proposed_backup),
        )
    )


class SetupWizard:
    """Modalny kreator pierwszego uruchomienia i zmiany ścieżek."""

    def __init__(
        self,
        parent: Any,
        engine: Any,
        on_saved: Callable[[], None] | None = None,
        *,
        language: str = "pl",
    ) -> None:
        import tkinter as tk
        from tkinter import filedialog, messagebox, ttk

        self.tk = tk
        self.filedialog = filedialog
        self.messagebox = messagebox
        self.ttk = ttk
        self.engine = engine
        self.on_saved = on_saved
        self.language = language
        self.saved = False
        self.detected_paths: dict[str, Path] = {}

        try:
            config = engine.store.load_config()
        except Exception:
            config = None
        self.initial_config = config

        default_library = Path.home() / "Documents" / "FH6Mods"
        self.game_var = tk.StringVar(
            master=parent,
            value=str(config.game_root) if config and config.game_root else "",
        )
        self.library_var = tk.StringVar(
            master=parent,
            value=str(config.library_dir) if config and config.library_dir else str(default_library),
        )
        self.backup_var = tk.StringVar(
            master=parent,
            value=str(config.backup_dir) if config and config.backup_dir else "",
        )
        self.method_var = tk.StringVar(
            master=parent,
            value=config.method if config else "auto",
        )
        self.detected_var = tk.StringVar(master=parent, value="")

        self.window = tk.Toplevel(parent)
        self.window.title(self._t("wizard_title"))
        self.window.transient(parent)
        self.window.configure(background=COLORS["background"])
        self.window.geometry("720x570")
        self.window.minsize(640, 520)
        self.window.grab_set()
        self.window.protocol("WM_DELETE_WINDOW", self._cancel)
        self.window.columnconfigure(0, weight=1)

        outer = ttk.Frame(self.window, padding=24)
        outer.grid(row=0, column=0, sticky="nsew")
        self.window.rowconfigure(0, weight=1)
        outer.columnconfigure(0, weight=1)
        ttk.Label(
            outer,
            text=self._t("wizard_heading"),
            font=("Segoe UI Semibold", 18),
        ).grid(row=0, column=0, sticky="w")
        ttk.Label(
            outer,
            text=self._t("wizard_intro"),
            wraplength=640,
            justify="left",
        ).grid(row=1, column=0, sticky="w", pady=(8, 18))

        form = ttk.Frame(outer)
        form.grid(row=2, column=0, sticky="ew")
        form.columnconfigure(1, weight=1)
        ttk.Label(form, text=self._t("wizard_game")).grid(row=0, column=0, sticky="w", pady=7)
        ttk.Entry(form, textvariable=self.game_var).grid(
            row=0, column=1, sticky="ew", padx=(12, 8), pady=7
        )
        ttk.Button(form, text=self._t("wizard_browse"), command=self._browse_game).grid(
            row=0, column=2, sticky="ew", pady=7
        )

        ttk.Label(form, text=self._t("wizard_library")).grid(row=1, column=0, sticky="w", pady=7)
        ttk.Entry(form, textvariable=self.library_var).grid(
            row=1, column=1, sticky="ew", padx=(12, 8), pady=7
        )
        ttk.Button(form, text=self._t("wizard_browse"), command=self._browse_library).grid(
            row=1, column=2, sticky="ew", pady=7
        )

        ttk.Label(form, text=self._t("wizard_backup")).grid(row=2, column=0, sticky="w", pady=7)
        ttk.Entry(form, textvariable=self.backup_var).grid(
            row=2, column=1, sticky="ew", padx=(12, 8), pady=7
        )
        ttk.Button(form, text=self._t("wizard_browse"), command=self._browse_backup).grid(
            row=2, column=2, sticky="ew", pady=7
        )
        ttk.Label(
            form,
            text=self._t("wizard_backup_note"),
            foreground=COLORS["muted"],
            wraplength=430,
            justify="left",
        ).grid(row=3, column=1, sticky="w", padx=(12, 0), pady=(0, 8))

        ttk.Label(form, text=self._t("wizard_method")).grid(row=4, column=0, sticky="w", pady=7)
        method = ttk.Combobox(
            form,
            textvariable=self.method_var,
            values=("auto", "hardlink", "symlink", "copy"),
            state="readonly",
            width=18,
        )
        method.grid(row=4, column=1, sticky="w", padx=(12, 8), pady=7)
        ttk.Label(
            form,
            text=self._t("wizard_method_help"),
            foreground=COLORS["muted"],
        ).grid(row=4, column=2, sticky="w", pady=7)

        detect = ttk.Frame(outer)
        detect.grid(row=3, column=0, sticky="ew", pady=(18, 0))
        detect.columnconfigure(1, weight=1)
        ttk.Button(detect, text=self._t("wizard_detect"), command=self._detect_game).grid(
            row=0, column=0, sticky="w"
        )
        self.detected_combo = ttk.Combobox(
            detect,
            textvariable=self.detected_var,
            state="readonly",
        )
        self.detected_combo.grid(row=0, column=1, sticky="ew", padx=(12, 0))
        self.detected_combo.bind("<<ComboboxSelected>>", self._select_detected)
        ttk.Label(
            outer,
            text=self._t("wizard_warning"),
            wraplength=640,
            justify="left",
            foreground=COLORS["warning"],
        ).grid(row=4, column=0, sticky="w", pady=(20, 14))

        buttons = ttk.Frame(outer)
        buttons.grid(row=5, column=0, sticky="ew")
        ttk.Button(buttons, text=self._t("wizard_cancel"), command=self._cancel).pack(side="right")
        ttk.Button(
            buttons,
            text=self._t("wizard_save"),
            style="Accent.TButton",
            command=self._save,
        ).pack(side="right", padx=(0, 8))
        self.window.bind("<Escape>", lambda _event: self._cancel())
        self.window.bind("<Return>", lambda _event: self._save())
        self.window.after(50, self.window.focus_force)

    def _browse_game(self) -> None:
        selected = self.filedialog.askdirectory(
            parent=self.window,
            title=self._t("wizard_game_picker"),
            initialdir=self.game_var.get() or str(Path.home()),
        )
        if selected:
            self.game_var.set(selected)

    def _browse_library(self) -> None:
        selected = self.filedialog.askdirectory(
            parent=self.window,
            title=self._t("wizard_library_picker"),
            initialdir=self.library_var.get() or str(Path.home()),
            mustexist=False,
        )
        if selected:
            self.library_var.set(selected)

    def _browse_backup(self) -> None:
        selected = self.filedialog.askdirectory(
            parent=self.window,
            title=self._t("wizard_backup_picker"),
            initialdir=self.backup_var.get() or str(Path.home()),
            mustexist=False,
        )
        if selected:
            self.backup_var.set(selected)

    def _detect_game(self) -> None:
        from ..paths import detect_game_installs

        candidates = detect_game_installs()
        if not candidates:
            self.messagebox.showinfo(
                self._t("wizard_detect_none_title"),
                self._t("wizard_detect_none_body"),
                parent=self.window,
            )
            return
        self.detected_paths = {
            f"{candidate.path}  —  {candidate.source}": candidate.path
            for candidate in candidates
        }
        values = list(self.detected_paths)
        self.detected_combo.configure(values=values)
        self.detected_var.set(values[0])
        self.game_var.set(str(self.detected_paths[values[0]]))
        if len(values) > 1:
            self.messagebox.showinfo(
                self._t("wizard_detect_multiple_title"),
                self._t("wizard_detect_multiple_body"),
                parent=self.window,
            )

    def _select_detected(self, _event: Any = None) -> None:
        selected = self.detected_paths.get(self.detected_var.get())
        if selected:
            self.game_var.set(str(selected))

    def _save(self) -> None:
        from ..paths import normalize_path, validate_game_root

        game_text = self.game_var.get().strip()
        library_text = self.library_var.get().strip()
        if not game_text or not library_text:
            self.messagebox.showerror(
                self._t("wizard_no_paths_title"),
                self._t("wizard_no_paths_body"),
                parent=self.window,
            )
            return

        try:
            state = self.engine.store.load_state()
        except (OSError, StateError) as exc:
            self.messagebox.showerror(
                self._t("wizard_state_error_title"),
                self._t("wizard_state_error_body", error=exc),
                parent=self.window,
            )
            return

        active_mods = [mod_id for mod_id, mod_state in state.mods.items() if mod_state.files]
        if active_mods and deployment_paths_changed(
            self.initial_config,
            game_text,
            library_text,
            self.backup_var.get().strip() or None,
            default_backup_dir=self.engine.store.config_dir / "backups",
        ):
            names = ", ".join(active_mods[:5])
            if len(active_mods) > 5:
                names += f" i {len(active_mods) - 5} innych"
            self.messagebox.showerror(
                self._t("wizard_active_title"),
                self._t("wizard_active_body", mods=names),
                parent=self.window,
            )
            return

        library_path = normalize_path(library_text)
        if not library_path.exists():
            if not self.messagebox.askyesno(
                self._t("wizard_create_library_title"),
                self._t("wizard_create_library_body", path=library_path),
                parent=self.window,
            ):
                return
            try:
                game_path = validate_game_root(game_text)
                library_resolved = library_path.resolve(strict=False)
                if library_resolved.is_relative_to(game_path) or game_path.is_relative_to(
                    library_resolved
                ):
                    raise ValueError("Biblioteka nie może pokrywać się z folderem gry.")
                library_path.mkdir(parents=True, exist_ok=True)
            except (OSError, ValueError) as exc:
                self.messagebox.showerror(
                    self._t("wizard_create_library_error"),
                    str(exc),
                    parent=self.window,
                )
                return

        try:
            config = self.engine.configure(
                game_text,
                library_path,
                self.backup_var.get().strip() or None,
                self.method_var.get(),
            )
        except Exception as exc:
            self.messagebox.showerror(
                self._t("wizard_config_error_title"),
                self._t("wizard_config_error_body", error=exc),
                parent=self.window,
            )
            return

        self.saved = True
        if self.on_saved is not None:
            self.on_saved()
        self.window.destroy()

    def _t(self, key: str, **values: Any) -> str:
        return translate(self.language, key, **values)

    def _cancel(self) -> None:
        self.saved = False
        self.window.destroy()
