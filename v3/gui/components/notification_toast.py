"""Non-blocking toast notifications for runtime feedback."""

from __future__ import annotations

import tkinter as tk

from v3.gui.theme import COLORS, FONTS


class NotificationToast:
    """Small top-level popup that auto-dismisses after a short delay."""

    _BG_BY_LEVEL = {
        "info": "#dce9f9",
        "warn": "#f8ead0",
        "error": "#f6d6d6",
    }
    _FG_BY_LEVEL = {
        "info": COLORS["accent_info"],
        "warn": COLORS["accent_warn"],
        "error": COLORS["accent_error"],
    }

    def __init__(self, root: tk.Tk, *, message: str, level: str = "info", duration_ms: int = 4000) -> None:
        self.root = root
        self.message = str(message).strip()
        self.level = level if level in {"info", "warn", "error"} else "info"
        self.duration_ms = max(1000, int(duration_ms))
        self.win: tk.Toplevel | None = None

    def show(self, *, y_offset: int = 0) -> None:
        win = tk.Toplevel(self.root)
        win.overrideredirect(True)
        win.attributes("-topmost", True)

        bg = self._BG_BY_LEVEL[self.level]
        fg = self._FG_BY_LEVEL[self.level]

        container = tk.Frame(win, bg=bg, bd=1, relief="solid")
        container.pack(fill="both", expand=True)

        prefix = {
            "info": "Info",
            "warn": "Warning",
            "error": "Error",
        }[self.level]
        tk.Label(
            container,
            text=f"{prefix}: {self.message}",
            bg=bg,
            fg=fg,
            font=FONTS["mono_small"],
            anchor="w",
            justify="left",
            padx=8,
            pady=6,
        ).pack(fill="both", expand=True)

        win.update_idletasks()
        width = min(max(win.winfo_reqwidth(), 300), 560)
        height = win.winfo_reqheight()
        screen_w = win.winfo_screenwidth()
        screen_h = win.winfo_screenheight()
        x = max(0, screen_w - width - 18)
        y = max(0, screen_h - height - 64 - int(y_offset))
        win.geometry(f"{width}x{height}+{x}+{y}")

        win.after(self.duration_ms, self.destroy)
        self.win = win

    def destroy(self) -> None:
        if self.win is None:
            return
        if self.win.winfo_exists():
            self.win.destroy()
        self.win = None
