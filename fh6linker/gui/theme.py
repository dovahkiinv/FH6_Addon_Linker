"""Paleta kolorów i wspólny, ciemny styl okien tkinter/ttk."""

from __future__ import annotations

from typing import Any

# Ciemna, prawie czarna paleta z czytelnym kontrastem i oszczędnym turkusem.
COLORS = {
    "background": "#080A0D",
    "surface": "#11151B",
    "surface_alt": "#191F28",
    "surface_hover": "#252D38",
    "text": "#F1F4F8",
    "muted": "#9AA5B3",
    "accent": "#00A985",
    "accent_hover": "#008D70",
    "success": "#42D98A",
    "warning": "#F3C66B",
    "warning_bg": "#2A2317",
    "danger": "#E85662",
    "danger_hover": "#C94450",
    "danger_bg": "#351D23",
    "border": "#252C36",
    "selection": "#17473E",
    "input": "#0B0E12",
    "tooltip_bg": "#171D25",
}


def configure_theme(root: Any, ttk_module: Any | None = None) -> None:
    """Ustawia spójny, prawie czarny styl niezależnie od platformy."""
    if ttk_module is None:
        from tkinter import ttk as ttk_module

    style = ttk_module.Style(root)
    if "clam" in style.theme_names():
        style.theme_use("clam")

    root.configure(background=COLORS["background"])

    # Ustawiamy bazowy TFrame/TLabel — kreator i okna dialogowe również używają
    # zwykłych ramek, więc bez tego na części systemów zostawały jasnoszare.
    style.configure("TFrame", background=COLORS["background"])
    style.configure(
        "App.TFrame",
        background=COLORS["background"],
    )
    style.configure(
        "Card.TFrame",
        background=COLORS["surface"],
        bordercolor=COLORS["border"],
        borderwidth=1,
        relief="solid",
    )
    style.configure(
        "Metric.TFrame",
        background=COLORS["surface"],
        bordercolor=COLORS["border"],
        borderwidth=1,
        relief="solid",
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
        font=("Segoe UI Semibold", 23),
    )
    style.configure(
        "Subtitle.TLabel",
        background=COLORS["background"],
        foreground=COLORS["muted"],
        font=("Segoe UI", 9),
    )
    style.configure(
        "Eyebrow.TLabel",
        background=COLORS["background"],
        foreground=COLORS["muted"],
        font=("Segoe UI Semibold", 8),
    )
    style.configure(
        "BrandMark.TLabel",
        background=COLORS["accent"],
        foreground="#FFFFFF",
        font=("Segoe UI Semibold", 12),
        padding=(11, 8),
    )
    style.configure(
        "Badge.TLabel",
        background=COLORS["surface_alt"],
        foreground=COLORS["success"],
        font=("Segoe UI Semibold", 8),
        padding=(9, 5),
    )
    style.configure(
        "Banner.TLabel",
        background=COLORS["warning_bg"],
        foreground=COLORS["warning"],
        font=("Segoe UI Semibold", 9),
        padding=(12, 9),
    )
    style.configure(
        "PathHeading.TLabel",
        background=COLORS["surface"],
        foreground=COLORS["muted"],
        font=("Segoe UI Semibold", 8),
    )
    style.configure(
        "PathValue.TLabel",
        background=COLORS["surface"],
        foreground=COLORS["text"],
        font=("Segoe UI", 9),
    )
    style.configure(
        "MetricLabel.TLabel",
        background=COLORS["surface"],
        foreground=COLORS["muted"],
        font=("Segoe UI Semibold", 8),
    )
    style.configure(
        "MetricValue.TLabel",
        background=COLORS["surface"],
        foreground=COLORS["text"],
        font=("Segoe UI Semibold", 21),
    )
    style.configure(
        "MetricActive.TLabel",
        background=COLORS["surface"],
        foreground=COLORS["success"],
        font=("Segoe UI Semibold", 21),
    )
    style.configure(
        "MetricAlert.TLabel",
        background=COLORS["surface"],
        foreground=COLORS["warning"],
        font=("Segoe UI Semibold", 21),
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
        padding=(12, 9),
        borderwidth=1,
        bordercolor=COLORS["border"],
        focuscolor=COLORS["accent"],
        relief="flat",
    )
    style.map(
        "TButton",
        background=[
            ("disabled", "#171B21"),
            ("pressed", COLORS["surface_hover"]),
            ("active", COLORS["surface_hover"]),
        ],
        foreground=[("disabled", "#687382")],
    )
    style.configure(
        "Accent.TButton",
        background=COLORS["accent"],
        foreground="#FFFFFF",
        padding=(14, 10),
        borderwidth=0,
    )
    style.map(
        "Accent.TButton",
        background=[
            ("disabled", "#24564B"),
            ("pressed", COLORS["accent_hover"]),
            ("active", COLORS["accent_hover"]),
        ],
        foreground=[("disabled", "#A4B7B1")],
    )
    style.configure(
        "Danger.TButton",
        background=COLORS["danger"],
        foreground="#FFFFFF",
        padding=(14, 10),
        borderwidth=0,
    )
    style.map(
        "Danger.TButton",
        background=[
            ("disabled", "#5A3036"),
            ("pressed", COLORS["danger_hover"]),
            ("active", COLORS["danger_hover"]),
        ],
        foreground=[("disabled", "#C5AEB1")],
    )

    style.configure(
        "Treeview",
        background=COLORS["surface"],
        fieldbackground=COLORS["surface"],
        foreground=COLORS["text"],
        rowheight=34,
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
        padding=(9, 10),
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
        padding=(9, 8),
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
        padding=(9, 7),
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
