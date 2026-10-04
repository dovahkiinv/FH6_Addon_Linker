"""Okna planu operacji, szczegółów moda i informacji o aplikacji."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from ..i18n import translate
from ..report import OperationReport, PlannedAction
from .theme import COLORS

_ACTION_KEYS = {
    "create_link": "plan_action_create",
    "repair_link": "plan_action_repair",
    "force_replace": "plan_action_force",
    "already_enabled": "plan_action_already_enabled",
    "remove_link_restore_backup": "plan_action_restore_backup",
    "remove_added_file": "plan_action_remove_added",
    "restore_missing_target": "plan_action_restore_missing",
    "already_missing": "plan_action_already_missing",
    "preserve_foreign_file": "plan_action_preserve_foreign",
    "already_disabled": "plan_action_already_disabled",
    "verify": "plan_action_verify",
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
        language: str = "pl",
    ) -> None:
        import tkinter as tk
        from tkinter import ttk

        self.tk = tk
        self.language = language
        self.approved = False
        self.window = tk.Toplevel(parent)
        self.window.title(title)
        self.window.transient(parent)
        self.window.configure(background=COLORS["background"])
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
            text=translate(language, "plan_summary", count=len(actions)),
            font=("Segoe UI Semibold", 12),
        ).grid(row=0, column=0, sticky="w")
        deployment_actions = [
            action
            for action in actions
            if action.action in {"create_link", "repair_link", "force_replace"}
        ]
        if deployment_actions:
            originals = sum(action.backup is not None for action in deployment_actions)
            new_targets = len(deployment_actions) - originals
            detail = translate(
                language,
                "plan_original_counts",
                backups=originals,
                new=new_targets,
            )
        else:
            detail = translate(language, "plan_review_hint")
        ttk.Label(summary, text=detail, style="Subtitle.TLabel").grid(
            row=1, column=0, sticky="w", pady=(4, 0)
        )
        ttk.Label(
            summary,
            text=translate(language, "plan_no_changes"),
            style="Subtitle.TLabel",
        ).grid(row=2, column=0, sticky="w", pady=(2, 0))

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
            background=COLORS["surface"],
            foreground=COLORS["text"],
            insertbackground=COLORS["text"],
            selectbackground=COLORS["selection"],
            selectforeground=COLORS["text"],
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
                text=translate(
                    language,
                    "plan_blocked"
                    if errors or (conflicts and not allow_conflicts)
                    else "plan_nothing",
                ),
                foreground=COLORS["danger"],
            ).pack(side="left", fill="x", expand=True)
        ttk.Button(buttons, text=translate(language, "plan_cancel"), command=self._cancel).pack(side="right")
        self.apply_button = ttk.Button(
            buttons,
            text=translate(language, "plan_apply"),
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
        operation_keys = {
            "enable": "plan_operation_enable",
            "disable": "plan_operation_disable",
            "restore": "plan_operation_restore",
            "repair": "plan_operation_repair",
            "verify": "plan_operation_verify",
        }
        for report in reports:
            operation_key = operation_keys.get(report.operation.casefold())
            operation = translate(self.language, operation_key) if operation_key else report.operation
            self.text.insert("end", f"{operation.upper()}\n")
        if actions:
            self.text.insert("end", f"\n{translate(self.language, 'plan_files_heading')}\n")
            for action in actions:
                action_key = _ACTION_KEYS.get(action.action)
                label = translate(self.language, action_key) if action_key else action.action
                line = f"• {label}: {action.mod_name}"
                if action.file:
                    line += f" — {action.file} ({action.size:,} B)"
                if action.source:
                    line += f"\n  {translate(self.language, 'plan_source')}: {action.source}"
                if action.target:
                    line += f"\n  {translate(self.language, 'plan_target')}: {action.target}"
                if action.backup:
                    line += f"\n  {translate(self.language, 'plan_backup')}: {action.backup}"
                if action.note:
                    line += f"\n  {action.note}"
                self.text.insert("end", line + "\n")
        for heading_key, items in (
            ("plan_warnings_heading", warnings),
            ("plan_conflicts_heading", conflicts),
            ("plan_errors_heading", errors),
        ):
            if items:
                self.text.insert("end", f"\n{translate(self.language, heading_key)}\n")
                for item in items:
                    self.text.insert("end", f"• {item}\n")

    def _approve(self) -> None:
        self.approved = True
        self.window.destroy()

    def _cancel(self) -> None:
        self.approved = False
        self.window.destroy()


def show_about(parent: Any, version: str, *, language: str = "pl") -> None:
    """Pokazuje wersję i zastrzeżenia dotyczące modyfikowania gry."""
    from tkinter import messagebox

    messagebox.showinfo(
        translate(language, "about_title"),
        translate(language, "about_body", version=version),
        parent=parent,
    )


def show_mod_details(parent: Any, name: str, details: str) -> None:
    """Pokazuje szczegółowe ostrzeżenia i ścieżki wybranego moda."""
    from tkinter import messagebox

    messagebox.showinfo(name, details, parent=parent)
