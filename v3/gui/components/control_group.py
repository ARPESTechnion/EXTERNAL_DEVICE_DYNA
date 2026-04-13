"""Compact titled container used for grouped controls."""

from __future__ import annotations

from tkinter import ttk


class ControlGroup(ttk.LabelFrame):
    """A lightweight grouped section with consistent margins."""

    def __init__(self, parent: ttk.Widget, title: str, *, pad_x: int = 5, pad_y: int = 4) -> None:
        super().__init__(parent, text=title)
        self.pack(fill="x", padx=pad_x, pady=pad_y)
        self.body = ttk.Frame(self)
        self.body.pack(fill="x", padx=5, pady=4)
