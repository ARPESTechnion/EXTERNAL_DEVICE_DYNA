"""Shared GUI theme tokens and style setup for the v3 Tkinter app."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk


COLORS: dict[str, str] = {
    "bg_root": "#e3e6ea",
    "bg_panel": "#d6dbe1",
    "bg_input": "#f1f3f5",
    "fg_primary": "#1f2a38",
    "fg_muted": "#5f6f82",
    # Unified accent palette by physical quantity
    "accent_temp": "#c85a20",      # Temperature (orange)
    "accent_field": "#1e8a34",     # Magnetic field (green)
    "accent_resistance": "#8a4d21",# Resistance (brown)
    "accent_current": "#1f4f9c",   # Current (blue)
    "accent_info": "#2d6db2",      # Info/Status (blue)
    "accent_chamber": "#1d5f9e",   # Chamber (blue)
    "accent_warn": "#b56b00",
    "accent_error": "#ff6b6b",
    "led_on": "#1e8a34",
    "led_off": "#c54242",
    "button_primary": "#2f7a3f",
    "button_primary_active": "#3c9850",
    "button_secondary": "#c7ced6",
    "button_secondary_active": "#b8c0c9",
    "button_danger": "#c54242",
    "button_danger_active": "#de5353",
}


FONTS: dict[str, tuple[str, int] | tuple[str, int, str]] = {
    "title": ("Segoe UI", 11, "bold"),
    "subtitle": ("Segoe UI", 10, "bold"),
    "body": ("Segoe UI", 10),
    "mono": ("Consolas", 11),
    "mono_small": ("Consolas", 9),
}


SPACING: dict[str, int] = {
    "xs": 2,
    "sm": 5,
    "md": 10,
    "lg": 15,
}


def apply_theme(root: tk.Tk) -> ttk.Style:
    """Apply base ttk theme/style settings and return the style object."""
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except Exception:
        pass

    root.configure(bg=COLORS["bg_root"])

    style.configure("TFrame", background=COLORS["bg_root"])
    style.configure("TLabel", background=COLORS["bg_root"], foreground=COLORS["fg_primary"], font=FONTS["body"])
    style.configure("TLabelframe", background=COLORS["bg_root"], foreground=COLORS["fg_primary"])
    style.configure(
        "TLabelframe.Label",
        background=COLORS["bg_root"],
        foreground=COLORS["fg_primary"],
        font=FONTS["subtitle"],
    )

    style.configure("SectionTitle.TLabel", font=FONTS["subtitle"], foreground=COLORS["fg_primary"])
    style.configure("SectionTitleLarge.TLabel", font=FONTS["title"], foreground=COLORS["fg_primary"])

    style.configure(
        "TButton",
        font=FONTS["body"],
        background=COLORS["button_secondary"],
        foreground=COLORS["fg_primary"],
        borderwidth=1,
    )
    style.map("TButton", background=[("active", COLORS["button_secondary_active"])])

    style.configure(
        "TEntry",
        fieldbackground=COLORS["bg_input"],
        foreground=COLORS["fg_primary"],
        insertcolor=COLORS["fg_primary"],
    )
    style.configure(
        "TCombobox",
        fieldbackground=COLORS["bg_input"],
        background=COLORS["bg_input"],
        foreground=COLORS["fg_primary"],
        arrowcolor=COLORS["fg_primary"],
    )
    style.map(
        "TCombobox",
        fieldbackground=[("readonly", COLORS["bg_input"])],
        foreground=[("readonly", COLORS["fg_primary"])],
    )
    style.configure(
        "TSpinbox",
        fieldbackground=COLORS["bg_input"],
        background=COLORS["bg_input"],
        foreground=COLORS["fg_primary"],
        arrowcolor=COLORS["fg_primary"],
    )
    style.configure(
        "TCheckbutton",
        background=COLORS["bg_root"],
        foreground=COLORS["fg_primary"],
    )
    style.configure(
        "TMenubutton",
        background=COLORS["bg_input"],
        foreground=COLORS["fg_primary"],
    )
    style.map("TMenubutton", background=[("active", COLORS["bg_panel"])])

    style.configure("TNotebook", background=COLORS["bg_root"], borderwidth=0)
    style.configure(
        "TNotebook.Tab",
        background=COLORS["bg_panel"],
        foreground=COLORS["fg_primary"],
        padding=(8, 4),
    )
    style.map(
        "TNotebook.Tab",
        background=[("selected", COLORS["bg_input"])],
        foreground=[("selected", COLORS["fg_primary"])],
    )

    style.configure(
        "Treeview",
        background=COLORS["bg_input"],
        fieldbackground=COLORS["bg_input"],
        foreground=COLORS["fg_primary"],
    )
    style.map("Treeview", background=[("selected", "#bcc7d3")], foreground=[("selected", COLORS["fg_primary"])])

    style.configure(
        "Primary.TButton",
        font=FONTS["body"],
        background=COLORS["button_primary"],
        foreground=COLORS["fg_primary"],
        borderwidth=1,
    )
    style.map("Primary.TButton", background=[("active", COLORS["button_primary_active"])])

    style.configure(
        "Secondary.TButton",
        font=FONTS["body"],
        background=COLORS["button_secondary"],
        foreground=COLORS["fg_primary"],
        borderwidth=1,
    )
    style.map("Secondary.TButton", background=[("active", COLORS["button_secondary_active"])])

    style.configure(
        "Danger.TButton",
        font=FONTS["body"],
        background=COLORS["button_danger"],
        foreground=COLORS["fg_primary"],
        borderwidth=1,
    )
    style.map("Danger.TButton", background=[("active", COLORS["button_danger_active"])])

    return style