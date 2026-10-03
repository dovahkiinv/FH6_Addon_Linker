"""Paleta kolorów i wspólny styl okien tkinter/ttk."""

from __future__ import annotations

from typing import Any

COLORS = {
    "background": "#f3f6fb",
    "surface": "#ffffff",
    "surface_alt": "#e8eef6",
    "text": "#172033",
    "muted": "#596579",
    "accent": "#167d75",
    "accent_hover": "#11665f",
    "success": "#18794e",
    "warning": "#805b00",
    "warning_bg": "#fff3cd",
    "danger": "#a83131",
    "danger_bg": "#fde8e7",
    "border": "#cbd5e1",
    "selection": "#d8e9f2",
}


def configure_theme(root: Any, ttk_module: Any | None = None) -> None:
    """Ustawia spójny jasny styl bez zależności od zewnętrznych bibliotek."""
    if ttk_module is None:
        from tkinter import ttk as ttk_module

    style = ttk_module.Style(root)
    if "clam" in style.theme_names():
        style.theme_use("clam")
    root.configure(background=COLORS["background"])

    style.configure("App.TFrame", background=COLORS["background"])
    style.configure("Card.TFrame", background=COLORS["surface"], relief="flat")
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
        font=("Segoe UI Semibold", 21),
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
        padding=(10, 7),
    )
    style.configure(
        "TButton",
        background=COLORS["surface_alt"],
        foreground=COLORS["text"],
        font=("Segoe UI Semibold", 9),
        padding=(11, 7),
        borderwidth=0,
    )
    style.map(
        "TButton",
        background=[("disabled", "#e5e7eb"), ("active", "#d5dfeb")],
        foreground=[("disabled", "#8992a0")],
    )
    style.configure(
        "Accent.TButton",
        background=COLORS["accent"],
        foreground="#ffffff",
        padding=(13, 8),
    )
    style.map(
        "Accent.TButton",
        background=[("disabled", "#a8b5c0"), ("active", COLORS["accent_hover"])],
        foreground=[("disabled", "#f8fafc")],
    )
    style.configure(
        "Danger.TButton",
        background=COLORS["danger"],
        foreground="#ffffff",
        padding=(13, 8),
    )
    style.map(
        "Danger.TButton",
        background=[("disabled", "#d5b4b3"), ("active", "#8b2525")],
    )
    style.configure(
        "Treeview",
        background=COLORS["surface"],
        fieldbackground=COLORS["surface"],
        foreground=COLORS["text"],
        rowheight=28,
        font=("Segoe UI", 9),
        bordercolor=COLORS["border"],
        borderwidth=1,
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
        padding=(7, 8),
        relief="flat",
    )
    style.map("Treeview.Heading", background=[("active", "#d5dfeb")])
    style.configure("TEntry", padding=(7, 6), font=("Segoe UI", 10))
    style.configure("TCombobox", padding=(7, 5), font=("Segoe UI", 10))
    style.configure("Horizontal.TProgressbar", background=COLORS["accent"])
