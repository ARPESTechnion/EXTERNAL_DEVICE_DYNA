"""Entry widget with lightweight numeric validation feedback."""

from __future__ import annotations

import tkinter as tk
from typing import Callable


Validator = Callable[[str], bool]


def make_float_validator(min_value: float | None = None, max_value: float | None = None, *, allow_empty: bool = False) -> Validator:
    """Create a float-range validator for entry values."""

    def _validate(raw: str) -> bool:
        text = raw.strip()
        if text == "":
            return allow_empty
        try:
            value = float(text)
        except Exception:
            return False
        if min_value is not None and value < min_value:
            return False
        if max_value is not None and value > max_value:
            return False
        return True

    return _validate


def make_int_validator(min_value: int | None = None, max_value: int | None = None, *, allow_empty: bool = False) -> Validator:
    """Create an integer-range validator for entry values."""

    def _validate(raw: str) -> bool:
        text = raw.strip()
        if text == "":
            return allow_empty
        try:
            value = int(text, 10)
        except Exception:
            return False
        if min_value is not None and value < min_value:
            return False
        if max_value is not None and value > max_value:
            return False
        return True

    return _validate


class ValidatingEntry(tk.Entry):
    """Entry that highlights invalid values without blocking typing."""

    def __init__(
        self,
        parent: tk.Widget,
        *,
        validator: Validator,
        textvariable: tk.Variable | None = None,
        width: int = 10,
        normal_bg: str = "#f1f3f5",
        invalid_bg: str = "#ffe2e2",
        **kwargs,
    ) -> None:
        super().__init__(
            parent,
            textvariable=textvariable,
            width=width,
            background=normal_bg,
            insertbackground="#1f2a38",
            **kwargs,
        )
        self._validator = validator
        self._normal_bg = normal_bg
        self._invalid_bg = invalid_bg
        self.bind("<KeyRelease>", self._validate_and_paint)
        self.bind("<FocusOut>", self._validate_and_paint)
        self._validate_and_paint()

    def _validate_and_paint(self, _event: tk.Event | None = None) -> None:
        value = self.get()
        ok = self._validator(value)
        self.configure(background=self._normal_bg if ok else self._invalid_bg)
