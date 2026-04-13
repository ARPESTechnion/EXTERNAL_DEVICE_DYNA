"""
v3.gui.base_tab  —  Abstract base class for all notebook tabs.

Every tab inherits from ``BaseTab`` and implements:

* ``create_widgets()`` — build all Tk widgets.
* ``on_event(widget_id, value)`` — update displays from UIEventBus events.
* ``on_instrument_connected(name)`` / ``on_instrument_disconnected(name)``
  — react to connection-state changes.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import TYPE_CHECKING, Any

from v3.gui.theme import COLORS, FONTS

if TYPE_CHECKING:
    from v3.gui.app import MeasureApp


# ═══════════════════════════════════════════════════════════════════════
# LED helper
# ═══════════════════════════════════════════════════════════════════════
LED_ON_COLOR = COLORS["led_on"]
LED_OFF_COLOR = COLORS["led_off"]
LED_CHAR = "●"


def make_led(parent: tk.Widget, **kwargs) -> tk.Label:
    """Create a coloured LED indicator label (Unicode bullet)."""
    lbl = tk.Label(
        parent,
        text=LED_CHAR,
        fg=LED_OFF_COLOR,
        bg=COLORS["bg_root"],
        font=FONTS["subtitle"],
        **kwargs,
    )
    return lbl


def set_led(led: tk.Label, on: bool) -> None:
    """Set a LED label to green (on) or red (off)."""
    led.configure(fg=LED_ON_COLOR if on else LED_OFF_COLOR)


# ═══════════════════════════════════════════════════════════════════════
# Connection header factory
# ═══════════════════════════════════════════════════════════════════════
class ConnectionHeader:
    """Standard connection strip shown at the top of every instrument tab.

    Contains: LED • status label • Connect / Disconnect button.
    """

    def __init__(
        self,
        parent: tk.Widget,
        instrument_key: str,
        display_name: str,
        on_connect: Any = None,
        on_disconnect: Any = None,
    ) -> None:
        self.instrument_key = instrument_key
        self._on_connect = on_connect
        self._on_disconnect = on_disconnect
        self._connected = False

        frame = ttk.Frame(parent, padding=2)
        frame.grid(row=0, column=0, columnspan=4, sticky="ew")
        frame.grid_columnconfigure(3, weight=1)

        self.led = make_led(frame)
        self.led.grid(row=0, column=0, sticky="w", padx=(0, 6))

        self.status_label = ttk.Label(
            frame,
            text=f"{display_name}: Disconnected",
        )
        self.status_label.grid(row=0, column=1, sticky="w")
        self._display_name = display_name

        self.button = ttk.Button(
            frame,
            text="Connect",
            command=self._toggle,
        )
        self.button.grid(row=0, column=2, sticky="w", padx=(8, 0))

    # --- public API ---------------------------------------------------
    def set_connected(self, connected: bool) -> None:
        """Update the visual state of the header."""
        self._connected = connected
        set_led(self.led, connected)
        if connected:
            self.status_label.configure(text=f"{self._display_name}: Connected")
            self.button.configure(text="Disconnect")
        else:
            self.status_label.configure(text=f"{self._display_name}: Disconnected")
            self.button.configure(text="Connect")

    @property
    def is_connected(self) -> bool:
        return self._connected

    # --- internals ----------------------------------------------------
    def _toggle(self) -> None:
        if self._connected:
            if self._on_disconnect:
                self._on_disconnect()
        else:
            if self._on_connect:
                self._on_connect()


# ═══════════════════════════════════════════════════════════════════════
# BaseTab
# ═══════════════════════════════════════════════════════════════════════
class BaseTab:
    """Abstract base for all notebook tabs.

    Subclasses must implement:

    * ``create_widgets()``
    * ``on_event(widget_id, value)``
    """

    def __init__(self, parent: ttk.Frame, app: "MeasureApp") -> None:
        self.parent = parent
        self.app = app

    def create_widgets(self) -> None:
        """Build all widgets in *self.parent*."""
        raise NotImplementedError

    def on_event(self, widget_id: str, value: Any) -> None:
        """Process a UIEventBus event.  Override in subclasses."""

    def on_instrument_connected(self, name: str) -> None:
        """Called when an instrument is successfully connected."""

    def on_instrument_disconnected(self, name: str) -> None:
        """Called when an instrument is disconnected."""
