"""Horizontal status strip with LED indicators."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from v3.gui.base_tab import make_led, set_led


class StatusStrip(ttk.Frame):
    """Row of compact LED indicators with labels."""

    def __init__(self, parent: ttk.Widget, *, padding: int = 0) -> None:
        super().__init__(parent, padding=padding)
        self.leds: dict[str, tk.Label] = {}

    def add_indicator(self, key: str, label_text: str, *, with_separator: bool = False) -> None:
        item = ttk.Frame(self)
        item.pack(side="left", padx=(0, 6))
        led = make_led(item)
        led.pack(side="left", padx=(0, 4))
        ttk.Label(item, text=label_text).pack(side="left")
        self.leds[key] = led

        if with_separator:
            ttk.Separator(self, orient="vertical").pack(side="left", fill="y", padx=(0, 6))

    def set_indicator(self, key: str, on: bool) -> None:
        led = self.leds.get(key)
        if led is not None:
            set_led(led, on)
