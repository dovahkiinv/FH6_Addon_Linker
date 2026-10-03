"""Okna planu operacji, szczegółów moda i informacji o aplikacji."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from ..report import OperationReport, PlannedAction

_ACTION_LABELS = {
    "create_link": "Utwórz link",
    "repair_link": "Napraw link",
    "force_replace": "Zastąp link innego moda",
    "already_enabled": "Już włączony",
    "remove_link_restore_backup": "Usuń link i przywróć backup",
    "remove_added_file": "Usuń dodany plik",
    "restore_missing_target": "Przywróć brakujący plik",
    "already_missing": "Plik już usunięty",
    "preserve_foreign_file": "Pozostaw obcy plik bez zmian",
    "already_disabled": "Już wyłączony",
    "verify": "Sprawdź plik",
}


class PlanDialog:
    """Pokazuje użytkownikowi pełny plan przed wykonaniem zmian."""

    def __init__(
        self,
        parent: Any,
        title: str,
        reports: Sequence[OperationReport],
        *,
        allow_conflicts: bool = False,
    ) -> None:
        import tkinter as tk
        from tkinter import ttk

        self.tk = tk
        self.approved = False
        self.window = tk.Toplevel(parent)
        self.window.title(title)
        self.window.transient(parent)
        self.window.geometry("760x560")
        self.window.minsize(560, 380)
        self.window.grab_set()
        self.window.protocol("WM_DELETE_WINDOW", self._cancel)
        self.window.columnconfigure(0, weight=1)
        self.window.rowconfigure(1, weight=1)

        actions = [
            action
            for report in reports
            for action in report.actions
            if action.action != "already_enabled" and action.action != "already_disabled"
        ]
        warnings = [message for report in reports for message in report.warnings]
        conflicts = [message for report in reports for message in report.conflicts]
        errors = [message for report in reports for message in report.errors]
        blocked = bool(errors or (conflicts and not allow_conflicts) or not actions)

        summary = ttk.Frame(self.window, padding=(16, 14))
        summary.grid(row=0, column=0, sticky="ew")
        summary.columnconfigure(0, weight=1)
        ttk.Label(
            summary,
            text=f"Plan obejmuje {len(actions)} zmian w plikach.",
            font=("Segoe UI Semibold", 12),
        ).grid(row=0, column=0, sticky="w")
        ttk.Label(
            summary,
            text="Nic nie zostanie zmienione, dopóki nie zatwierdzisz tego planu.",
        ).grid(row=1, column=0, sticky="w", pady=(4, 0))

        content = ttk.Frame(self.window, padding=(16, 0, 16, 12))
        content.grid(row=1, column=0, sticky="nsew")
        content.columnconfigure(0, weight=1)
        content.rowconfigure(0, weight=1)
        self.text = tk.Text(
            content,
            wrap="word",
            relief="solid",
            borderwidth=1,
            padx=10,
            pady=8,
            font=("Consolas", 9),
            background="#ffffff",
            foreground="#172033",
        )
        scrollbar = ttk.Scrollbar(content, orient="vertical", command=self.text.yview)
        self.text.configure(yscrollcommand=scrollbar.set)
        self.text.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        self._write_plan(reports, actions, warnings, conflicts, errors)
        self.text.configure(state="disabled")
        self.text.bind("<Control-c>", lambda _event: self.text.event_generate("<<Copy>>"))

        buttons = ttk.Frame(self.window, padding=(16, 0, 16, 14))
        buttons.grid(row=2, column=0, sticky="ew")
        if blocked:
            ttk.Label(
                buttons,
                text=(
                    "Usuń błędy/konflikty i ponów plan. Konflikty nie są nadpisywane."
                    if errors or (conflicts and not allow_conflicts)
                    else "Brak zmian do wykonania."
                ),
                foreground="#a83131",
            ).pack(side="left", fill="x", expand=True)
        ttk.Button(buttons, text="Anuluj", command=self._cancel).pack(side="right")
        self.apply_button = ttk.Button(
            buttons,
            text="Zastosuj plan",
            style="Accent.TButton",
            command=self._approve,
            state="disabled" if blocked else "normal",
        )
        self.apply_button.pack(side="right", padx=(0, 8))
        self.window.bind("<Escape>", lambda _event: self._cancel())
        self.window.bind("<Control-Return>", lambda _event: self._approve())
        self.window.after(50, self.window.focus_force)

    def show(self) -> bool:
        """Wyświetla okno modalne i zwraca informację o zatwierdzeniu planu."""
        self.window.wait_window()
        return self.approved

    def _write_plan(
        self,
        reports: Sequence[OperationReport],
        actions: Sequence[PlannedAction],
        warnings: Sequence[str],
        conflicts: Sequence[str],
        errors: Sequence[str],
    ) -> None:
        for report in reports:
            self.text.insert("end", f"OPERACJA: {report.operation}\n")
        if actions:
            self.text.insert("end", "\nPLAN PLIKÓW\n")
            for action in actions:
                label = _ACTION_LABELS.get(action.action, action.action)
                line = f"• {label}: {action.mod_name}"
                if action.file:
                    line += f" — {action.file} ({action.size:,} B)"
                if action.source:
                    line += f"\n  Źródło: {action.source}"
                if action.target:
                    line += f"\n  Cel: {action.target}"
                if action.backup:
                    line += f"\n  Backup: {action.backup}"
                if action.note:
                    line += f"\n  {action.note}"
                self.text.insert("end", line + "\n")
        for heading, items in (
            ("OSTRZEŻENIA", warnings),
            ("KONFLIKTY (pozostaną bez zmian)", conflicts),
            ("BŁĘDY", errors),
        ):
            if items:
                self.text.insert("end", f"\n{heading}\n")
                for item in items:
                    self.text.insert("end", f"• {item}\n")

    def _approve(self) -> None:
        self.approved = True
        self.window.destroy()

    def _cancel(self) -> None:
        self.approved = False
        self.window.destroy()


def show_about(parent: Any, version: str) -> None:
    """Pokazuje wersję i zastrzeżenia dotyczące modyfikowania gry."""
    from tkinter import messagebox

    messagebox.showinfo(
        "O aplikacji",
        f"FH6 Addon Linker {version}\n\n"
        "Narzędzie społecznościowe, niezwiązane z Playground Games, Xbox ani Microsoft.\n\n"
        "Modyfikowanie plików gry może naruszać regulamin i grozić banem. "
        "Aplikacja nie gwarantuje bezpieczeństwa konta ani modów.",
        parent=parent,
    )


def show_mod_details(parent: Any, name: str, details: str) -> None:
    """Pokazuje szczegółowe ostrzeżenia i ścieżki wybranego moda."""
    from tkinter import messagebox

    messagebox.showinfo(name, details, parent=parent)
