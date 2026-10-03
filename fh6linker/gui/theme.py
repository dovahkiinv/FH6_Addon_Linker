"""Paleta kolorów i wspólny, ciemny styl okien tkinter/ttk."""

from __future__ import annotations

from typing import Any

COLORS = {
    "background": "#0d1117",
    "surface": "#161b22",
    "surface_alt": "#21262d",
    "surface_hover": "#30363d",
    "text": "#e6edf3",
    "muted": "#9da7b3",
    "accent": "#167d75",
    "accent_hover": "#11665f",
    "success": "#3fb950",
    "warning": "#f0c76b",
    "warning_bg": "#3b2f1d",
    "danger": "#c43e4f",
    "danger_hover": "#a93243",
    "danger_bg": "#3a2026",
    "border": "#30363d",
    "selection": "#254c50",
    "input": "#0b0f14",
    "tooltip_bg": "#202832",
}


def configure_theme(root: Any, ttk_module: Any | None = None) -> None:
    """Ustawia spójny ciemny styl niezależnie od platformy i bez bibliotek zewnętrznych."""
    if ttk_module is None:
        from tkinter import ttk as ttk_module

    style = ttk_module.Style(root)
    if "clam" in style.theme_names():
        style.theme_use("clam")
    root.configure(background=COLORS["background"])

    style.configure("App.TFrame", background=COLORS["background"])
    style.configure(
        "Card.TFrame",
        background=COLORS["surface"],
        bordercolor=COLORS["border"],
        relief="flat",
    )
    style.configure(
        "TLabel",
        background=COLORS["background"],
        foreground=COLORS["text"],
        font=("Segoe UI", 10),
    )
    style.configure(
        "Title.TLabel",
        background=COLORS["background"],
        foreground=COLORS["text"],
        font=("Segoe UI Semibold", 22),
    )
    style.configure(
        "Subtitle.TLabel",
        background=COLORS["background"],
        foreground=COLORS["muted"],
        font=("Segoe UI", 9),
    )
    style.configure(
        "Banner.TLabel",
        background=COLORS["warning_bg"],
        foreground=COLORS["warning"],
        font=("Segoe UI Semibold", 9),
        padding=(12, 9),
    )
    style.configure(
        "Path.TLabel",
        background=COLORS["surface_alt"],
        foreground=COLORS["muted"],
        font=("Segoe UI", 9),
        padding=(10, 8),
    )
    style.configure(
        "Empty.TLabel",
        background=COLORS["surface"],
        foreground=COLORS["muted"],
        font=("Segoe UI", 11),
        padding=(24, 18),
    )
    style.configure(
        "TButton",
        background=COLORS["surface_alt"],
        foreground=COLORS["text"],
        font=("Segoe UI Semibold", 9),
        padding=(11, 8),
        borderwidth=1,
        bordercolor=COLORS["border"],
        relief="flat",
    )
    style.map(
        "TButton",
        background=[
            ("disabled", "#1a2028"),
            ("pressed", COLORS["surface_hover"]),
            ("active", COLORS["surface_hover"]),
        ],
        foreground=[("disabled", "#6e7681")],
    )
    style.configure(
        "Accent.TButton",
        background=COLORS["accent"],
        foreground="#ffffff",
        padding=(13, 9),
        borderwidth=0,
    )
    style.map(
        "Accent.TButton",
        background=[
            ("disabled", "#245b56"),
            ("pressed", COLORS["accent_hover"]),
            ("active", COLORS["accent_hover"]),
        ],
        foreground=[("disabled", "#9eaaa9")],
    )
    style.configure(
        "Danger.TButton",
        background=COLORS["danger"],
        foreground="#ffffff",
        padding=(13, 9),
        borderwidth=0,
    )
    style.map(
        "Danger.TButton",
        background=[
            ("disabled", "#5e3038"),
            ("pressed", COLORS["danger_hover"]),
            ("active", COLORS["danger_hover"]),
        ],
        foreground=[("disabled", "#c5aeb1")],
    )
    style.configure(
        "Treeview",
        background=COLORS["surface"],
        fieldbackground=COLORS["surface"],
        foreground=COLORS["text"],
        rowheight=32,
        font=("Segoe UI", 9),
        bordercolor=COLORS["border"],
        borderwidth=1,
        lightcolor=COLORS["border"],
        darkcolor=COLORS["border"],
    )
    style.map(
        "Treeview",
        background=[("selected", COLORS["selection"])],
        foreground=[("selected", COLORS["text"])],
    )
    style.configure(
        "Treeview.Heading",
        background=COLORS["surface_alt"],
        foreground=COLORS["text"],
        font=("Segoe UI Semibold", 9),
        padding=(8, 9),
        relief="flat",
        bordercolor=COLORS["border"],
    )
    style.map(
        "Treeview.Heading",
        background=[("active", COLORS["surface_hover"])],
        foreground=[("active", COLORS["text"])],
    )
    style.configure(
        "TEntry",
        padding=(8, 7),
        font=("Segoe UI", 10),
        fieldbackground=COLORS["input"],
        foreground=COLORS["text"],
        bordercolor=COLORS["border"],
        insertcolor=COLORS["text"],
    )
    style.map(
        "TEntry",
        fieldbackground=[("disabled", COLORS["surface_alt"])],
        foreground=[("disabled", COLORS["muted"])],
    )
    style.configure(
        "TCombobox",
        padding=(8, 6),
        font=("Segoe UI", 10),
        fieldbackground=COLORS["input"],
        background=COLORS["surface_alt"],
        foreground=COLORS["text"],
        arrowcolor=COLORS["muted"],
        bordercolor=COLORS["border"],
    )
    style.map(
        "TCombobox",
        fieldbackground=[("readonly", COLORS["surface_alt"]), ("disabled", COLORS["surface_alt"])],
        foreground=[("readonly", COLORS["text"]), ("disabled", COLORS["muted"])],
        selectbackground=[("readonly", COLORS["selection"])],
        selectforeground=[("readonly", COLORS["text"])],
        arrowcolor=[("active", COLORS["text"])],
    )
    style.configure(
        "TScrollbar",
        background=COLORS["surface_alt"],
        troughcolor=COLORS["background"],
        bordercolor=COLORS["background"],
        arrowcolor=COLORS["muted"],
        darkcolor=COLORS["surface_alt"],
        lightcolor=COLORS["surface_alt"],
        relief="flat",
        arrowsize=12,
        width=13,
    )
    style.map("TScrollbar", background=[("active", COLORS["surface_hover"])])
    style.configure(
        "Horizontal.TProgressbar",
        background=COLORS["accent"],
        troughcolor=COLORS["surface_alt"],
        bordercolor=COLORS["surface_alt"],
        lightcolor=COLORS["accent"],
        darkcolor=COLORS["accent"],
    )
    style.configure("TSeparator", background=COLORS["border"])
