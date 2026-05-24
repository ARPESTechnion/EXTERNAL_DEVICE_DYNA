"""
v3.gui.lockin_tab  —  SR830 Lock-in amplifier control tab.

Provides controls for frequency, time constant, sensitivity, filter slope,
output current, and series resistance.  Displays live X/Y/R/θ readouts
(updated via UIEventBus).  Includes Measure and Apply Settings buttons
matching V2 functionality.
"""

from __future__ import annotations

import threading
import time
import tkinter as tk
import math
from tkinter import ttk
from typing import TYPE_CHECKING, Any

from v3.core.constants import INST_LOCKIN
from v3.core.ui_events import (
    W_LOCKIN_CHANNEL,
    W_LOCKIN_CONNECTED,
    W_LOCKIN_OUTPUT_VOLTAGE,
    W_LOCKIN_PHASE,
    W_LOCKIN_PHASE_ERROR,
    W_LOCKIN_R,
    W_LOCKIN_R_ERROR,
    W_LOCKIN_RESISTANCE,
    W_LOCKIN_RESISTANCE_ERROR,
    W_LOCKIN_SENSITIVITY,
    W_LOCKIN_STATUS,
    W_LOCKIN_X,
    W_LOCKIN_X_ERROR,
    W_LOCKIN_Y,
    W_LOCKIN_Y_ERROR,
    W_LED_LOCKIN,
    W_RESULTS_NEW_POINT,
)
from v3.gui.base_tab import BaseTab, ConnectionHeader, make_led, set_led
from v3.gui.components import ValidatingEntry, make_float_validator
from v3.gui.theme import COLORS, FONTS

if TYPE_CHECKING:
    from v3.gui.app import MeasureApp


# SR830 time constant table (seconds)
TAU_TABLE = [
    10e-6, 30e-6, 100e-6, 300e-6, 1e-3, 3e-3, 10e-3, 30e-3,
    100e-3, 300e-3, 1.0, 3.0, 10.0, 30.0, 100.0, 300.0,
    1e3, 3e3, 10e3, 30e3,
]

# Sensitivity table (V)
SENSITIVITY_TABLE = [
    2e-9, 5e-9, 10e-9, 20e-9, 50e-9, 100e-9, 200e-9, 500e-9,
    1e-6, 2e-6, 5e-6, 10e-6, 20e-6, 50e-6, 100e-6, 200e-6, 500e-6,
    1e-3, 2e-3, 5e-3, 10e-3, 20e-3, 50e-3, 100e-3, 200e-3, 500e-3,
    1.0,
]

# Calibrated series resistor values (matching V2)
R_LOCKIN_OPTIONS = {
    "50 Ω": 50.35,
    "1 kΩ": 1000.0,
    "10 kΩ": 10062.1,
    "100 kΩ": 99640.0,
    "0.993 MΩ": 993000.0,
    "1 MΩ": 996500.0,
    "10 MΩ": 9987500.0,
}

# Filter slope dB/oct → SR830 index
_DB_TO_FILTER_INDEX = {6: 0, 12: 1, 18: 2, 24: 3}


def _db_to_filter_index(db_oct: int) -> int:
    """Convert filter slope dB/oct to SR830 filter index (0–3)."""
    idx = _DB_TO_FILTER_INDEX.get(int(db_oct))
    if idx is None:
        closest = min(_DB_TO_FILTER_INDEX, key=lambda x: abs(x - db_oct))
        idx = _DB_TO_FILTER_INDEX[closest]
    return idx


class LockInTab(BaseTab):
    """Lock-in amplifier control and monitoring tab."""

    def __init__(self, parent: ttk.Frame, app: "MeasureApp") -> None:
        super().__init__(parent, app)
        self._conn_header: ConnectionHeader | None = None
        self._measuring = False
        self._measure_buttons: list[ttk.Button] = []
        self._idle_output_voltage = 0.004
        self._status_idle_after_id: str | None = None
        self._x_value: float | None = None
        self._x_error: float | None = None
        self._y_value: float | None = None
        self._y_error: float | None = None
        self._r_value: float | None = None
        self._r_error: float | None = None
        self._theta_value: float | None = None
        self._theta_error: float | None = None
        self._resistance_value: float | None = None
        self._resistance_error: float | None = None

    def create_widgets(self) -> None:
        self._conn_header = ConnectionHeader(
            self.parent,
            instrument_key="lockin",
            display_name="SR830 Lock-In",
            on_connect=lambda: self.app.connect_instrument("lockin"),
            on_disconnect=lambda: self.app.disconnect_instrument("lockin"),
        )

        body = ttk.Frame(self.parent, padding=10, width=760)
        body.grid(row=1, column=0, sticky="nw")
        body.grid_propagate(False)
        self.parent.grid_rowconfigure(1, weight=1)
        self.parent.grid_columnconfigure(0, weight=1)

        self._build_settings(body)
        self._build_measure_buttons(body)
        self._build_readouts(body)

    # ------------------------------------------------------------------
    # Settings panel
    # ------------------------------------------------------------------
    def _build_settings(self, parent: ttk.Frame) -> None:
        sf = ttk.LabelFrame(parent, text="Lock-In Settings")
        sf.pack(fill="x", padx=5, pady=5)

        self.lockin_frequency = tk.DoubleVar(value=173.0)
        self.lockin_time_constant_idx = tk.IntVar(value=9)
        self.lockin_filter_slope = tk.StringVar(value="24")
        self.lockin_sensitivity_idx = tk.IntVar(value=10)
        self.lockin_output_current = tk.DoubleVar(value=100e-9)
        self.lockin_r_lockin = tk.DoubleVar(value=996500)
        self.lockin_averaging = tk.IntVar(value=10)
        self.lockin_r_lockin_idx = tk.StringVar(value="1 MΩ")
        self.lockin_input_shield_grounded = tk.BooleanVar(value=False)
        self.lockin_input_shield_state = tk.StringVar(value="Floating")

        row = 0

        # Frequency
        ttk.Label(sf, text="Frequency (Hz):").grid(row=row, column=0, sticky="w", padx=5, pady=2)
        ValidatingEntry(
            sf,
            textvariable=self.lockin_frequency,
            width=10,
            validator=make_float_validator(0.001, 102000.0),
        ).grid(row=row, column=1, padx=5)
        ttk.Button(sf, text="Set", command=self._set_frequency, width=5).grid(row=row, column=2)
        row += 1

        # Time constant (index selector)
        ttk.Label(sf, text="Time Constant:").grid(row=row, column=0, sticky="w", padx=5, pady=2)
        self.tc_label = ttk.Label(sf, text=self._tc_text())
        self.tc_label.grid(row=row, column=1, padx=5)
        tc_btns = ttk.Frame(sf)
        tc_btns.grid(row=row, column=2)
        ttk.Button(tc_btns, text="◄", width=3, command=self._tc_down).pack(side="left")
        ttk.Button(tc_btns, text="►", width=3, command=self._tc_up).pack(side="left")
        ttk.Button(tc_btns, text="Set", width=4, command=self._set_tc).pack(side="left")
        row += 1

        # Sensitivity (index selector)
        ttk.Label(sf, text="Sensitivity:").grid(row=row, column=0, sticky="w", padx=5, pady=2)
        self.sens_label = ttk.Label(sf, text=self._sens_text())
        self.sens_label.grid(row=row, column=1, padx=5)
        sens_btns = ttk.Frame(sf)
        sens_btns.grid(row=row, column=2)
        ttk.Button(sens_btns, text="◄", width=3, command=self._sens_down).pack(side="left")
        ttk.Button(sens_btns, text="►", width=3, command=self._sens_up).pack(side="left")
        ttk.Button(sens_btns, text="Set", width=4, command=self._set_sens).pack(side="left")
        row += 1

        # Filter slope
        ttk.Label(sf, text="Filter (dB/oct):").grid(row=row, column=0, sticky="w", padx=5, pady=2)
        ttk.OptionMenu(sf, self.lockin_filter_slope, "24", "6", "12", "18", "24").grid(
            row=row, column=1, padx=5, sticky="w"
        )
        ttk.Button(sf, text="Set", command=self._set_filter, width=5).grid(row=row, column=2)
        row += 1

        # Output current
        ttk.Label(sf, text="Output Current (A):").grid(row=row, column=0, sticky="w", padx=5, pady=2)
        ValidatingEntry(
            sf,
            textvariable=self.lockin_output_current,
            width=10,
            validator=make_float_validator(0.0, 1.0),
        ).grid(row=row, column=1, padx=5)
        ttk.Button(sf, text="Set", command=self._set_current, width=5).grid(row=row, column=2)
        row += 1

        # R_lockin selector (calibrated values matching V2)
        ttk.Label(sf, text="R_lockin:").grid(row=row, column=0, sticky="w", padx=5, pady=2)
        r_combo = ttk.Combobox(
            sf, textvariable=self.lockin_r_lockin_idx,
            values=list(R_LOCKIN_OPTIONS.keys()),
            width=13, state="readonly",
        )
        r_combo.grid(row=row, column=1, padx=5, sticky="w")
        self.lockin_r_lockin_idx.trace_add("write", self._on_r_change)
        row += 1

        # Averaging
        ttk.Label(sf, text="Averaging:").grid(row=row, column=0, sticky="w", padx=5, pady=2)
        ValidatingEntry(
            sf,
            textvariable=self.lockin_averaging,
            width=10,
            validator=make_float_validator(1.0, 5000.0),
        ).grid(row=row, column=1, padx=5)
        row += 1

        # Input shield mode toggle
        ttk.Label(sf, text="Input Shield:").grid(row=row, column=0, sticky="w", padx=5, pady=2)
        self.input_shield_state_label = ttk.Label(sf, textvariable=self.lockin_input_shield_state)
        self.input_shield_state_label.grid(row=row, column=1, padx=5, sticky="w")
        self.input_shield_btn = ttk.Button(sf, width=7, command=self._toggle_input_shield)
        self.input_shield_btn.grid(row=row, column=2, padx=5, sticky="w")
        self._refresh_input_shield_button()
        row += 1

        # Utility buttons
        uf = ttk.LabelFrame(parent, text="Utilities")
        uf.pack(fill="x", padx=5, pady=5)
        ttk.Button(uf, text="Auto Gain", command=self._auto_gain).pack(side="left", padx=5, pady=2)
        ttk.Button(uf, text="Auto Phase", command=self._auto_phase).pack(side="left", padx=5, pady=2)
        ttk.Button(uf, text="Auto Reserve", command=self._auto_reserve).pack(side="left", padx=5, pady=2)

    # ------------------------------------------------------------------
    # Measure + Apply Settings buttons
    # ------------------------------------------------------------------
    def _build_measure_buttons(self, parent: ttk.Frame) -> None:
        mf = ttk.LabelFrame(parent, text="Measurement")
        mf.pack(fill="x", padx=5, pady=5)

        self.measure_btn = ttk.Button(mf, text="Measure", command=self._on_measure)
        self.measure_btn.pack(side="left", padx=5, pady=2)
        self.register_measure_button(self.measure_btn)

        self.apply_btn = ttk.Button(mf, text="Apply Settings", command=self._on_apply_settings)
        self.apply_btn.pack(side="left", padx=5, pady=2)

        ttk.Label(mf, text="Sine Output:").pack(side="left", padx=(10, 4))
        self.output_led = make_led(mf)
        self.output_led.pack(side="left", padx=2)
        self._update_output_led(0.0)

    def register_measure_button(self, button: ttk.Button) -> None:
        if button not in self._measure_buttons:
            self._measure_buttons.append(button)
        self._set_measure_buttons_enabled(not self._measuring)

    def _set_measure_buttons_enabled(self, enabled: bool) -> None:
        state = "normal" if enabled else "disabled"
        alive_buttons: list[ttk.Button] = []
        for button in self._measure_buttons:
            try:
                if bool(button.winfo_exists()):
                    button.configure(state=state)
                    alive_buttons.append(button)
            except Exception:
                continue
        self._measure_buttons = alive_buttons

    # ------------------------------------------------------------------
    # Readouts
    # ------------------------------------------------------------------
    def _build_readouts(self, parent: ttk.Frame) -> None:
        rd = ttk.LabelFrame(parent, text="LockIn Measurement")
        rd.pack(fill="x", padx=5, pady=5)

        self.x_label = tk.Label(
            rd,
            font=FONTS["mono"],
            fg=COLORS["accent_current"],
            bg=COLORS["bg_input"],
            relief="solid",
            borderwidth=1,
            padx=6,
            pady=2,
            anchor="w",
        )
        self.x_label.pack(fill="x", padx=5, pady=(5, 2))
        self.y_label = tk.Label(
            rd,
            font=FONTS["mono"],
            fg=COLORS["accent_current"],
            bg=COLORS["bg_input"],
            relief="solid",
            borderwidth=1,
            padx=6,
            pady=2,
            anchor="w",
        )
        self.y_label.pack(fill="x", padx=5, pady=2)
        self.r_label = tk.Label(
            rd,
            font=FONTS["mono"],
            fg=COLORS["accent_resistance"],
            bg=COLORS["bg_input"],
            relief="solid",
            borderwidth=1,
            padx=6,
            pady=2,
            anchor="w",
        )
        self.r_label.pack(fill="x", padx=5, pady=2)
        self.phase_label = tk.Label(
            rd,
            font=FONTS["mono"],
            fg=COLORS["accent_info"],
            bg=COLORS["bg_input"],
            relief="solid",
            borderwidth=1,
            padx=6,
            pady=2,
            anchor="w",
        )
        self.phase_label.pack(fill="x", padx=5, pady=2)
        self.resistance_label = tk.Label(
            rd,
            font=FONTS["mono"],
            fg=COLORS["accent_resistance"],
            bg=COLORS["bg_input"],
            relief="solid",
            borderwidth=1,
            padx=6,
            pady=2,
            anchor="w",
        )
        self.resistance_label.pack(fill="x", padx=5, pady=2)
        self.channel_label = tk.Label(
            rd,
            text="Channel: ---",
            font=FONTS["mono"],
            fg=COLORS["accent_info"],
            bg=COLORS["bg_input"],
            relief="solid",
            borderwidth=1,
            padx=6,
            pady=2,
            anchor="w",
        )
        self.channel_label.pack(fill="x", padx=5, pady=(2, 5))

        self._refresh_readout_labels()

        # Status text box (matches V2)
        ttk.Label(parent, text="Status:", style="SectionTitle.TLabel").pack(
            anchor="w", padx=5, pady=(10, 2)
        )
        self.lockin_status_text = tk.Text(
            parent,
            height=3,
            width=70,
            font=FONTS["mono_small"],
            background=COLORS["bg_input"],
            foreground=COLORS["fg_primary"],
            insertbackground=COLORS["fg_primary"],
            relief="sunken",
            state="disabled",
        )
        self.lockin_status_text.pack(fill="x", padx=5, pady=2)

    # ------------------------------------------------------------------
    # Event handling
    # ------------------------------------------------------------------
    def on_event(self, widget_id: str, value: Any) -> None:
        if widget_id == W_LOCKIN_X:
            self._x_value = self._to_number_or_none(value)
            self._refresh_readout_labels()
        elif widget_id == W_LOCKIN_Y:
            self._y_value = self._to_number_or_none(value)
            self._refresh_readout_labels()
        elif widget_id == W_LOCKIN_R:
            self._r_value = self._to_number_or_none(value)
            self._refresh_readout_labels()
        elif widget_id == W_LOCKIN_PHASE:
            self._theta_value = self._to_number_or_none(value)
            self._refresh_readout_labels()
        elif widget_id == W_LOCKIN_X_ERROR:
            self._x_error = self._to_number_or_none(value)
            self._refresh_readout_labels()
        elif widget_id == W_LOCKIN_Y_ERROR:
            self._y_error = self._to_number_or_none(value)
            self._refresh_readout_labels()
        elif widget_id == W_LOCKIN_R_ERROR:
            self._r_error = self._to_number_or_none(value)
            self._refresh_readout_labels()
        elif widget_id == W_LOCKIN_PHASE_ERROR:
            self._theta_error = self._to_number_or_none(value)
            self._refresh_readout_labels()
        elif widget_id == W_LOCKIN_RESISTANCE:
            self._resistance_value = self._to_number_or_none(value)
            self._refresh_readout_labels()
        elif widget_id == W_LOCKIN_RESISTANCE_ERROR:
            self._resistance_error = self._to_number_or_none(value)
            self._refresh_readout_labels()
        elif widget_id == W_LOCKIN_CHANNEL:
            self.channel_label.configure(text=f"Channel: {value}")
        elif widget_id == W_LOCKIN_SENSITIVITY:
            # Sync sensitivity display when measurement auto-adjusts it
            if isinstance(value, int) and 0 <= value < len(SENSITIVITY_TABLE):
                self.lockin_sensitivity_idx.set(value)
                self.sens_label.configure(text=self._sens_text())
        elif widget_id == W_LOCKIN_STATUS:
            self._set_status_with_idle(str(value))
        elif widget_id == W_LOCKIN_CONNECTED:
            if self._conn_header:
                self._conn_header.set_connected(bool(value))
            if bool(value):
                self._sync_output_led_from_settings()
                self._sync_input_shield_from_instrument()
            else:
                self._update_output_led(0.0)
        elif widget_id == W_LOCKIN_OUTPUT_VOLTAGE:
            try:
                self._update_output_led(float(value))
            except Exception:
                self._update_output_led(0.0)

    def on_instrument_connected(self, name: str) -> None:
        if name == "lockin" and self._conn_header:
            self._conn_header.set_connected(True)
            self._sync_output_led_from_settings()
            self._sync_input_shield_from_instrument()

    def on_instrument_disconnected(self, name: str) -> None:
        if name == "lockin" and self._conn_header:
            self._conn_header.set_connected(False)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _tc_text(self) -> str:
        idx = self.lockin_time_constant_idx.get()
        if 0 <= idx < len(TAU_TABLE):
            v = TAU_TABLE[idx]
            if v >= 1:
                return f"{v:.0f} s"
            elif v >= 1e-3:
                return f"{v * 1e3:.0f} ms"
            else:
                return f"{v * 1e6:.0f} μs"
        return "?"

    def _sens_text(self) -> str:
        idx = self.lockin_sensitivity_idx.get()
        if 0 <= idx < len(SENSITIVITY_TABLE):
            v = SENSITIVITY_TABLE[idx]
            if v >= 1e-3:
                return f"{v * 1e3:.0f} mV"
            elif v >= 1e-6:
                return f"{v * 1e6:.0f} μV"
            else:
                return f"{v * 1e9:.0f} nV"
        return "?"

    def _tc_down(self) -> None:
        idx = max(0, self.lockin_time_constant_idx.get() - 1)
        self.lockin_time_constant_idx.set(idx)
        self.tc_label.configure(text=self._tc_text())

    def _tc_up(self) -> None:
        idx = min(len(TAU_TABLE) - 1, self.lockin_time_constant_idx.get() + 1)
        self.lockin_time_constant_idx.set(idx)
        self.tc_label.configure(text=self._tc_text())

    def _sens_down(self) -> None:
        idx = max(0, self.lockin_sensitivity_idx.get() - 1)
        self.lockin_sensitivity_idx.set(idx)
        self.sens_label.configure(text=self._sens_text())

    def _sens_up(self) -> None:
        idx = min(len(SENSITIVITY_TABLE) - 1, self.lockin_sensitivity_idx.get() + 1)
        self.lockin_sensitivity_idx.set(idx)
        self.sens_label.configure(text=self._sens_text())

    def _on_r_change(self, *_args) -> None:
        key = self.lockin_r_lockin_idx.get()
        val = R_LOCKIN_OPTIONS.get(key, 996500)
        self.lockin_r_lockin.set(val)

    def _update_status_text(self, msg: str) -> None:
        self.lockin_status_text.configure(state="normal")
        self.lockin_status_text.delete("1.0", "end")
        self.lockin_status_text.insert("1.0", msg)
        self.lockin_status_text.configure(state="disabled")

    def _set_status_with_idle(self, msg: str) -> None:
        text = str(msg)
        self._update_status_text(text)
        if self._status_idle_after_id is not None:
            try:
                self.app.root.after_cancel(self._status_idle_after_id)
            except Exception:
                pass
            self._status_idle_after_id = None

        lowered = text.lower()
        if "running" in lowered:
            return

        self._status_idle_after_id = self.app.root.after(
            2000,
            lambda: self._update_status_text("LockIn: Idle"),
        )

    def _update_output_led(self, output_voltage: float) -> None:
        try:
            v = float(output_voltage)
        except Exception:
            v = 0.0
        threshold = max(float(self._idle_output_voltage), 0.0) + 1e-6
        set_led(self.output_led, v > threshold)

    def _sync_output_led_from_settings(self) -> None:
        output_voltage: float | None = None
        try:
            lockin = self.app.bus.get_raw(INST_LOCKIN)
            if lockin is not None:
                min_slvl = getattr(lockin, "_MIN_SLVL", None)
                if min_slvl is not None:
                    self._idle_output_voltage = float(min_slvl)
                if hasattr(lockin, "get_reference_amplitude"):
                    output_voltage = float(self.app.bus.execute(INST_LOCKIN, "get_reference_amplitude"))
        except Exception:
            output_voltage = None

        if output_voltage is None:
            try:
                output_voltage = float(self.lockin_output_current.get()) * float(self.lockin_r_lockin.get())
            except Exception:
                output_voltage = 0.0

        self._update_output_led(output_voltage)

    def _refresh_input_shield_button(self) -> None:
        grounded = self.lockin_input_shield_grounded.get()
        self.lockin_input_shield_state.set("Grounded" if grounded else "Floating")
        self.input_shield_btn.configure(text=("Float" if grounded else "Ground"))

    def _set_input_shield(self, grounded: bool, *, post_log: bool = True) -> None:
        self.app.bus.execute(INST_LOCKIN, "set_input_shield_grounded", bool(grounded))
        self.lockin_input_shield_grounded.set(bool(grounded))
        self._refresh_input_shield_button()
        status_msg = f"LockIn: Input shield {'grounded' if grounded else 'floating'}"
        self._set_status_with_idle(status_msg)
        if post_log:
            mode_text = "ground" if grounded else "float"
            self.app.ui_bus.post_log(f"Lock-in input shield -> {mode_text}")

    def _sync_input_shield_from_instrument(self) -> None:
        try:
            grounded = bool(self.app.bus.execute(INST_LOCKIN, "is_input_shield_grounded"))
            self.lockin_input_shield_grounded.set(grounded)
        except Exception:
            self.lockin_input_shield_grounded.set(False)
        self._refresh_input_shield_button()
        self._set_status_with_idle(
            f"LockIn: Input shield {'grounded' if self.lockin_input_shield_grounded.get() else 'floating'}"
        )

    def _toggle_input_shield(self) -> None:
        if not self.app.instrument_connected.get("lockin", False):
            self.app.ui_bus.post_log("ERROR: Lock-in SR830 not connected.")
            return
        try:
            next_mode_grounded = not self.lockin_input_shield_grounded.get()
            self._set_input_shield(next_mode_grounded, post_log=True)
        except Exception as exc:
            self.app.ui_bus.post_log(f"Set input shield error: {exc}")

    @staticmethod
    def _to_number_or_none(value: Any) -> float | None:
        try:
            out = float(value)
            if math.isnan(out) or math.isinf(out):
                return None
            return out
        except Exception:
            return None

    @staticmethod
    def _format_pm(prefix: str, value: float | None, error: float | None, value_fmt: str, error_fmt: str, unit: str) -> str:
        value_text = "---" if value is None else format(value, value_fmt)
        error_text = "---" if error is None else format(error, error_fmt)
        return f"{prefix}: {value_text} ± {error_text} {unit}"

    def _refresh_readout_labels(self) -> None:
        self.x_label.configure(text=self._format_pm("X", self._x_value, self._x_error, ".4e", ".1e", "V"))
        self.y_label.configure(text=self._format_pm("Y", self._y_value, self._y_error, ".4e", ".1e", "V"))
        self.r_label.configure(text=self._format_pm("R", self._r_value, self._r_error, ".4e", ".1e", "V"))
        self.phase_label.configure(text=self._format_pm("θ", self._theta_value, self._theta_error, ".1f", ".1f", "°"))
        self.resistance_label.configure(
            text=self._format_pm("Resistance", self._resistance_value, self._resistance_error, ".3e", ".1e", "Ω")
        )

    # ------------------------------------------------------------------
    # Button handlers
    # ------------------------------------------------------------------
    def _set_frequency(self) -> None:
        try:
            freq = self.lockin_frequency.get()
            self.app.bus.execute(INST_LOCKIN, "set_frequency", freq)
            self.app.ui_bus.post_log(f"Lock-in frequency → {freq} Hz")
        except Exception as exc:
            self.app.ui_bus.post_log(f"Set frequency error: {exc}")

    def _set_tc(self) -> None:
        try:
            idx = self.lockin_time_constant_idx.get()
            self.app.bus.execute(INST_LOCKIN, "set_time_constant", idx)
            self.app.ui_bus.post_log(f"Lock-in TC → {self._tc_text()}")
        except Exception as exc:
            self.app.ui_bus.post_log(f"Set TC error: {exc}")

    def _set_sens(self) -> None:
        try:
            idx = self.lockin_sensitivity_idx.get()
            self.app.bus.execute(INST_LOCKIN, "set_sensitivity", idx)
            self.app.ui_bus.post_log(f"Lock-in sensitivity → {self._sens_text()}")
        except Exception as exc:
            self.app.ui_bus.post_log(f"Set sensitivity error: {exc}")

    def _set_filter(self) -> None:
        try:
            db_oct = int(self.lockin_filter_slope.get())
            filter_idx = _db_to_filter_index(db_oct)
            self.app.bus.execute(INST_LOCKIN, "set_filter_slope", filter_idx)
            self.app.ui_bus.post_log(f"Lock-in filter → {db_oct} dB/oct (idx {filter_idx})")
        except Exception as exc:
            self.app.ui_bus.post_log(f"Set filter error: {exc}")

    def _set_current(self) -> None:
        try:
            from v3.core.measurements import set_lockin_current

            current = self.lockin_output_current.get()
            r = self.lockin_r_lockin.get()
            lockin = self.app.bus.get_raw(INST_LOCKIN)
            if lockin is None:
                raise RuntimeError("Lock-in is not connected")

            ctx = self.app.make_context()
            voltage = set_lockin_current(ctx, current=float(current), series_resistance=float(r))

            self.app.ui_bus.post(W_LOCKIN_OUTPUT_VOLTAGE, voltage)
            self.app.ui_bus.post_log(f"Lock-in output: {current:.2e} A × {r:.0f} Ω = {voltage:.4f} V")
        except Exception as exc:
            self.app.ui_bus.post_log(f"Set current error: {exc}")

    def _auto_gain(self) -> None:
        self._run_auto_action(
            running_status="LockIn: running auto gain",
            done_status="LockIn: auto gain completed",
            error_prefix="Auto gain error",
            methods=("quick_autorange", "safe_auto_gain", "auto_gain"),
            executed_log="Lock-in auto gain executed.",
            thread_name="lockin-auto-gain",
            sync_sensitivity=True,
        )

    def _auto_phase(self) -> None:
        self._run_auto_action(
            running_status="LockIn: running auto phase",
            done_status="LockIn: auto phase completed",
            error_prefix="Auto phase error",
            methods=("safe_auto_phase", "auto_phase"),
            executed_log="Lock-in auto phase executed.",
            thread_name="lockin-auto-phase",
        )

    def _auto_reserve(self) -> None:
        self._run_auto_action(
            running_status="LockIn: running auto reserve",
            done_status="LockIn: auto reserve completed",
            error_prefix="Auto reserve error",
            methods=("safe_auto_reserve", "auto_reserve"),
            executed_log="Lock-in auto reserve executed.",
            thread_name="lockin-auto-reserve",
        )

    def _run_auto_action(
        self,
        *,
        running_status: str,
        done_status: str,
        error_prefix: str,
        methods: tuple[str, ...],
        executed_log: str,
        thread_name: str,
        sync_sensitivity: bool = False,
    ) -> None:
        self._set_status_with_idle(running_status)

        def worker() -> None:
            try:
                inst = self.app.bus.get_raw(INST_LOCKIN)
                if inst is None:
                    raise RuntimeError("Lock-in is not connected")

                selected_method: str | None = None
                for method_name in methods:
                    if hasattr(inst, method_name):
                        selected_method = method_name
                        break
                if selected_method is None:
                    raise AttributeError("No supported auto function on lock-in driver")

                self.app.bus.execute(INST_LOCKIN, selected_method)

                if sync_sensitivity:
                    try:
                        sens_idx = int(self.app.bus.execute(INST_LOCKIN, "get_sensitivity"))
                        self.app.ui_bus.post(W_LOCKIN_SENSITIVITY, sens_idx)
                    except Exception:
                        self.app.ui_bus.post_log("Auto gain completed, but failed to refresh sensitivity")

                self.app.ui_bus.post_log(executed_log)
                self.app.root.after(0, lambda: self._set_status_with_idle(done_status))
            except Exception as exc:
                self.app.ui_bus.post_log(f"{error_prefix}: {exc}")
                self.app.root.after(0, lambda: self._set_status_with_idle(f"LockIn: {error_prefix.lower()} — {exc}"))

        threading.Thread(target=worker, daemon=True, name=thread_name).start()

    # ------------------------------------------------------------------
    # Measure (matches V2's lockin_measure)
    # ------------------------------------------------------------------
    def _on_measure(self) -> None:
        """Run a single lock-in measurement in a background thread."""
        if self._measuring:
            self.app.ui_bus.post_log("Lock-in measurement already in progress.")
            return
        if not self.app.instrument_connected.get("lockin", False):
            self.app.ui_bus.post_log("ERROR: Lock-in SR830 not connected — cannot measure.")
            return

        self._measuring = True
        self._set_measure_buttons_enabled(False)
        self.app.ui_bus.post(W_LED_LOCKIN, True)
        self._set_status_with_idle("LockIn: running measurement")

        t = threading.Thread(target=self._measure_worker, daemon=True, name="lockin-measure")
        t.start()

    def _measure_worker(self) -> None:
        """Background thread: perform lock-in measurement."""
        try:
            from v3.core.measurements import measure_lockin

            ctx = self.app.make_context()
            tau_idx = self.lockin_time_constant_idx.get()
            db_oct = int(self.lockin_filter_slope.get())
            filter_idx = _db_to_filter_index(db_oct)

            data_point = measure_lockin(
                ctx,
                current=self.lockin_output_current.get(),
                series_resistance=self.lockin_r_lockin.get(),
                avg=self.lockin_averaging.get(),
                tau_idx=tau_idx,
                filter_slope_idx=filter_idx,
                frequency=self.lockin_frequency.get(),
            )

            # Write data row
            ctx.data_mgr.write_row(data_point, measurement_type="LockIn")
            self.app.ui_bus.post(W_RESULTS_NEW_POINT, True)

            # Post UI updates on the main thread
            def _valid_num(v: Any) -> bool:
                return isinstance(v, (int, float)) and not math.isnan(float(v))

            def _pick(*vals: Any, default: float = 0.0) -> float:
                for val in vals:
                    if _valid_num(val):
                        return float(val)
                return default

            x = _pick(data_point.get("LockIn_X"), data_point.get("LockIn_X_a"), data_point.get("LockIn_X_b"), default=0.0)
            y = _pick(data_point.get("LockIn_Y"), data_point.get("LockIn_Y_a"), data_point.get("LockIn_Y_b"), default=0.0)
            r = _pick(data_point.get("LockIn_R"), data_point.get("LockIn_R_a"), data_point.get("LockIn_R_b"), default=0.0)
            theta = _pick(data_point.get("LockIn_Theta"), data_point.get("LockIn_Theta_a"), data_point.get("LockIn_Theta_b"), default=0.0)
            x_err = _pick(data_point.get("LockIn_X_Error"), data_point.get("LockIn_X_a_Error"), data_point.get("LockIn_X_b_Error"), default=float("nan"))
            y_err = _pick(data_point.get("LockIn_Y_Error"), data_point.get("LockIn_Y_a_Error"), data_point.get("LockIn_Y_b_Error"), default=float("nan"))
            r_err = _pick(data_point.get("LockIn_R_Error"), data_point.get("LockIn_R_a_Error"), data_point.get("LockIn_R_b_Error"), default=float("nan"))
            theta_err = _pick(
                data_point.get("LockIn_Theta_Error"),
                data_point.get("LockIn_Theta_a_Error"),
                data_point.get("LockIn_Theta_b_Error"),
                default=float("nan"),
            )
            sample_r = _pick(
                data_point.get("Sample_Resistance"),
                data_point.get("Sample_a_Resistance"),
                data_point.get("Sample_b_Resistance"),
                default=float("nan"),
            )
            sample_r_err = _pick(
                data_point.get("Sample_Resistance_Error"),
                data_point.get("Sample_a_Resistance_Error"),
                data_point.get("Sample_b_Resistance_Error"),
                default=float("nan"),
            )

            self.app.ui_bus.post(W_LOCKIN_X, x)
            self.app.ui_bus.post(W_LOCKIN_Y, y)
            self.app.ui_bus.post(W_LOCKIN_R, r)
            self.app.ui_bus.post(W_LOCKIN_PHASE, theta)
            self.app.ui_bus.post(W_LOCKIN_X_ERROR, x_err)
            self.app.ui_bus.post(W_LOCKIN_Y_ERROR, y_err)
            self.app.ui_bus.post(W_LOCKIN_R_ERROR, r_err)
            self.app.ui_bus.post(W_LOCKIN_PHASE_ERROR, theta_err)
            self.app.ui_bus.post(W_LOCKIN_RESISTANCE, sample_r)
            self.app.ui_bus.post(W_LOCKIN_RESISTANCE_ERROR, sample_r_err)

            # Report active channel
            ch = self.app.active_channel
            if ch:
                self.app.ui_bus.post(W_LOCKIN_CHANNEL, f"Channel {ch.upper()}")
            else:
                self.app.ui_bus.post(W_LOCKIN_CHANNEL, "No channel active")

            self.app.ui_bus.post_log(
                f"[{time.strftime('%H:%M:%S')}] LockIn measurement complete. "
                f"R={r:.6e} V"
            )
            self.app.ui_bus.post(W_LOCKIN_STATUS, "LockIn: measurement completed")

        except Exception as exc:
            self.app.ui_bus.post_log(f"Lock-in measure error: {exc}")
            self.app.ui_bus.post(W_LOCKIN_STATUS, f"LockIn: Error — {exc}")
        finally:
            # Re-enable button on main thread
            try:
                self.app.root.after(0, self._measure_done)
            except Exception:
                # Fallback when Tk main loop is shutting down
                self._measuring = False
                self.app.ui_bus.post(W_LED_LOCKIN, False)

    def _measure_done(self) -> None:
        """Called on main thread after measurement completes."""
        self._measuring = False
        self._set_measure_buttons_enabled(True)
        self.app.ui_bus.post(W_LED_LOCKIN, False)

    # ------------------------------------------------------------------
    # Apply Settings (matches V2's apply_lockin_settings)
    # ------------------------------------------------------------------
    def _on_apply_settings(self) -> None:
        """Bulk-apply all lock-in settings from the GUI to the instrument."""
        if not self.app.instrument_connected.get("lockin", False):
            self.app.ui_bus.post_log("ERROR: Lock-in SR830 not connected.")
            return
        try:
            # Frequency
            self.app.bus.execute(INST_LOCKIN, "set_frequency", self.lockin_frequency.get())

            # Time constant (index)
            tau_idx = self.lockin_time_constant_idx.get()
            self.app.bus.execute(INST_LOCKIN, "set_time_constant", tau_idx)

            # Filter slope (dB → index)
            db_oct = int(self.lockin_filter_slope.get())
            filter_idx = _db_to_filter_index(db_oct)
            self.app.bus.execute(INST_LOCKIN, "set_filter_slope", filter_idx)

            # Sensitivity (index)
            sens_idx = self.lockin_sensitivity_idx.get()
            self.app.bus.execute(INST_LOCKIN, "set_sensitivity", sens_idx)

            # Input shield mode (default float)
            self._set_input_shield(self.lockin_input_shield_grounded.get(), post_log=False)

            # Output voltage (current × R)
            self._set_current()

            tau_val = TAU_TABLE[tau_idx] if 0 <= tau_idx < len(TAU_TABLE) else "?"
            self._update_status_text(
                f"LockIn: Settings applied — Freq: {self.lockin_frequency.get():.1f} Hz, "
                f"τ: {tau_val}s, Filter: {db_oct} dB/oct"
            )
            self.app.ui_bus.post_log("Lock-in settings applied.")
        except Exception as exc:
            self.app.ui_bus.post_log(f"Apply settings error: {exc}")
