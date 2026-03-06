"""
v3.gui.hall_tab  —  Keithley 2450 (Hall bar) control tab.

Provides controls for Hall bar current sourcing, NPLC, compliance,
voltage range, filter, trigger-before-measure delay, and offset
calibration.  Displays live Hall voltage and field readouts.
"""

from __future__ import annotations

import threading
import tkinter as tk
from tkinter import ttk
from typing import TYPE_CHECKING, Any

from v3.core.constants import INST_KEITHLEY2450
from v3.core.ui_events import (
    W_HALL_CONNECTED,
    W_HALL_RESULT,
    W_HALL_SOURCE_ENABLED,
    W_LED_HALL,
    W_RESULTS_NEW_POINT,
)
from v3.gui.base_tab import BaseTab, ConnectionHeader, make_led, set_led

if TYPE_CHECKING:
    from v3.gui.app import MeasureApp


class HallTab(BaseTab):
    """Hall bar (Keithley 2450) control tab."""

    def __init__(self, parent: ttk.Frame, app: "MeasureApp") -> None:
        super().__init__(parent, app)
        self._conn_header: ConnectionHeader | None = None
        self._measuring = False
        self._source_enabled = False
        self._source_led_after_id: str | None = None

    def create_widgets(self) -> None:
        self._conn_header = ConnectionHeader(
            self.parent,
            instrument_key="hall",
            display_name="Keithley 2450 (Hall)",
            on_connect=lambda: self.app.connect_instrument("hall"),
            on_disconnect=lambda: self.app.disconnect_instrument("hall"),
        )

        body = ttk.Frame(self.parent, padding=10, width=720)
        body.grid(row=1, column=0, columnspan=3, sticky="nw")
        body.grid_propagate(False)
        self.parent.grid_rowconfigure(1, weight=1)
        self.parent.grid_columnconfigure(0, weight=1)

        self._build_settings(body)
        self._build_readouts(body)
        self._build_buttons(body)

    # ------------------------------------------------------------------
    # Settings
    # ------------------------------------------------------------------
    def _build_settings(self, parent: ttk.Frame) -> None:
        sf = ttk.LabelFrame(parent, text="Measurement Settings")
        sf.pack(fill="x", padx=5, pady=5)

        self.k2450_current = tk.DoubleVar(value=2.0)       # mA
        self.k2450_nplc = tk.IntVar(value=5)
        self.k2450_compliance_v = tk.DoubleVar(value=2.0)
        self.k2450_voltage_range = tk.StringVar(value="auto")
        self.k2450_filter_count = tk.IntVar(value=10)
        self.k2450_tbm = tk.DoubleVar(value=0.05)           # seconds
        self.k2450_hall_offset = tk.DoubleVar(value=0.0)     # V
        self.k2450_hall_v2gauss = tk.DoubleVar(value=10000.0 / 215.0)

        entries = [
            ("Current (mA):", self.k2450_current),
            ("NPLC:", self.k2450_nplc),
            ("Compliance (V):", self.k2450_compliance_v),
            ("Filter Count:", self.k2450_filter_count),
            ("TBM delay (s):", self.k2450_tbm),
            ("Hall Offset (V):", self.k2450_hall_offset),
            ("V→Gauss (G/V):", self.k2450_hall_v2gauss),
        ]

        for i, (label, var) in enumerate(entries):
            ttk.Label(sf, text=label).grid(row=i, column=0, sticky="w", padx=5, pady=2)
            ttk.Entry(sf, textvariable=var, width=12).grid(row=i, column=1, padx=5, pady=2)

        # Voltage range selector
        row = len(entries)
        ttk.Label(sf, text="Voltage Range:").grid(row=row, column=0, sticky="w", padx=5, pady=2)
        ttk.OptionMenu(
            sf, self.k2450_voltage_range, "auto",
            "auto", "0.02", "0.2", "2", "20", "200",
        ).grid(row=row, column=1, padx=5, sticky="w")

    # ------------------------------------------------------------------
    # Readouts
    # ------------------------------------------------------------------
    def _build_readouts(self, parent: ttk.Frame) -> None:
        rd = ttk.LabelFrame(parent, text="Hall Measurement")
        rd.pack(fill="x", padx=5, pady=5)

        src_row = ttk.Frame(rd)
        src_row.pack(anchor="w", padx=5, pady=(4, 2))
        self.source_led = make_led(src_row)
        self.source_led.pack(side="left", padx=(0, 4))
        self.source_status_label = ttk.Label(src_row, text="Source: Disabled")
        self.source_status_label.pack(side="left")

        self.result_label = tk.Label(
            rd,
            text="Voltage: --- ± --- V    Field: --- ± --- G",
            font=("Courier", 14), fg="#00FF00", bg="#000000",
        )
        self.result_label.pack(anchor="w", padx=5, pady=5)

    # ------------------------------------------------------------------
    # Buttons
    # ------------------------------------------------------------------
    def _build_buttons(self, parent: ttk.Frame) -> None:
        bf = ttk.Frame(parent)
        bf.pack(fill="x", padx=5, pady=5)

        self.measure_btn = ttk.Button(bf, text="Measure Hall", command=self._on_measure)
        self.measure_btn.pack(side="left", padx=5)
        ttk.Button(bf, text="Enable Source", command=self._on_enable_source).pack(side="left", padx=5)
        ttk.Button(bf, text="Disable Source", command=self._on_disable_source).pack(side="left", padx=5)

    # ------------------------------------------------------------------
    # Event handling
    # ------------------------------------------------------------------
    def on_event(self, widget_id: str, value: Any) -> None:
        if widget_id == W_HALL_RESULT:
            if isinstance(value, dict):
                v = value.get("voltage", 0)
                f = value.get("field", 0)
                v_err = value.get("voltage_error", 0)
                f_err = value.get("field_error", 0)
                self.result_label.configure(
                    text=f"Voltage: {v:.6e} ± {v_err:.2e} V    Field: {f:.2f} ± {f_err:.2f} G"
                )
                self._pulse_source_led()
            elif isinstance(value, str):
                self.result_label.configure(text=value)
        elif widget_id == W_HALL_CONNECTED:
            if self._conn_header:
                self._conn_header.set_connected(bool(value))
            if not bool(value):
                self._set_source_enabled(False)
        elif widget_id == W_HALL_SOURCE_ENABLED:
            self._set_source_enabled(bool(value))

    def on_instrument_connected(self, name: str) -> None:
        if name == "hall" and self._conn_header:
            self._conn_header.set_connected(True)

    def on_instrument_disconnected(self, name: str) -> None:
        if name == "hall" and self._conn_header:
            self._conn_header.set_connected(False)
            self._set_source_enabled(False)
            self.app.ui_bus.post(W_LED_HALL, False)

    def _set_source_enabled(self, enabled: bool) -> None:
        self._source_enabled = enabled
        set_led(self.source_led, enabled)
        self.source_status_label.configure(text=("Source: Enabled" if enabled else "Source: Disabled"))

    def _pulse_source_led(self, duration_ms: int = 500) -> None:
        set_led(self.source_led, True)
        if self._source_led_after_id is not None:
            try:
                self.app.root.after_cancel(self._source_led_after_id)
            except Exception:
                pass
            self._source_led_after_id = None
        self._source_led_after_id = self.app.root.after(
            duration_ms,
            lambda: set_led(self.source_led, self._source_enabled),
        )

    # ------------------------------------------------------------------
    # Button handlers
    # ------------------------------------------------------------------
    def _on_measure(self) -> None:
        """Run a single Hall measurement without blocking the UI."""
        if self._measuring:
            self.app.ui_bus.post_log("Hall measurement already in progress.")
            return
        self._measuring = True
        self.measure_btn.configure(state="disabled")
        t = threading.Thread(target=self._measure_worker, daemon=True, name="hall-measure")
        t.start()

    def _measure_worker(self) -> None:
        try:
            from v3.core.measurements import measure_hall
            ctx = self.app.make_context()

            voltage_range_raw = str(self.k2450_voltage_range.get())
            auto_range = voltage_range_raw.lower() == "auto"
            voltage_range = None if auto_range else float(voltage_range_raw)

            result = measure_hall(
                ctx,
                current_mA=self.k2450_current.get(),
                nplc=self.k2450_nplc.get(),
                compliance_v=self.k2450_compliance_v.get(),
                voltage_range=voltage_range,
                auto_range=auto_range,
                filter_count=self.k2450_filter_count.get(),
                tbm=self.k2450_tbm.get(),
            )

            voltage = float(result.get("Hall Voltage", 0.0))
            field = float(result.get("Hall Field", 0.0))
            voltage_error = abs(float(result.get("Hall Voltage Error", 0.0)))
            field_error = abs(float(result.get("Hall Field Error", 0.0)))

            ctx.data_mgr.write_row(result, measurement_type="Hall")
            self.app.ui_bus.post(W_RESULTS_NEW_POINT, True)

            self.app.ui_bus.post(W_HALL_RESULT, {
                "voltage": voltage,
                "field": field,
                "voltage_error": voltage_error,
                "field_error": field_error,
            })
            self.app.ui_bus.post_log(
                f"Hall: V={voltage:.6e} V, B={field:.2f} G"
            )
        except Exception as exc:
            self.app.ui_bus.post_log(f"Hall measure error: {exc}")
        finally:
            try:
                self.app.root.after(0, self._measure_done)
            except Exception:
                self._measuring = False

    def _measure_done(self) -> None:
        self._measuring = False
        self.measure_btn.configure(state="normal")

    def _on_enable_source(self) -> None:
        try:
            current_mA = self.k2450_current.get()
            self.app.bus.execute(INST_KEITHLEY2450, "__setattr__", "source_current", current_mA)
            self.app.bus.execute(
                INST_KEITHLEY2450,
                "apply_current",
                None,
                self.k2450_compliance_v.get(),
            )
            self.app.bus.execute(INST_KEITHLEY2450, "enable_source")
            self.app.ui_bus.post(W_HALL_SOURCE_ENABLED, True)
            self.app.ui_bus.post(W_LED_HALL, True)
            self.app.ui_bus.post_log(f"K2450 source enabled: {current_mA:.2f} mA")
        except Exception as exc:
            self.app.ui_bus.post_log(f"Enable source error: {exc}")

    def _on_disable_source(self) -> None:
        try:
            self.app.bus.execute(INST_KEITHLEY2450, "disable_source")
            self.app.ui_bus.post(W_HALL_SOURCE_ENABLED, False)
            self.app.ui_bus.post(W_LED_HALL, False)
            self.app.ui_bus.post_log("K2450 source disabled.")
        except Exception as exc:
            self.app.ui_bus.post_log(f"Disable source error: {exc}")
