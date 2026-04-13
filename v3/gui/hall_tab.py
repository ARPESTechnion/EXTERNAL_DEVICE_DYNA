"""
v3.gui.hall_tab  -  Keithley 2450 (Hall bar) control tab.

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
    W_INSTRUMENT_ERROR,
)
from v3.gui.base_tab import BaseTab, ConnectionHeader, make_led, set_led
from v3.gui.components import ValidatingEntry, make_float_validator
from v3.gui.theme import COLORS, FONTS

if TYPE_CHECKING:
    from v3.gui.app import MeasureApp


class HallTab(BaseTab):
    """Hall bar (Keithley 2450) control tab."""

    _HALL_BAR_PRESETS_V_PER_G: dict[str, float] = {
        "Wire Hall Bar 1": 2.1508e-05,
        "Wire Hall Bar 2": 2.1540e-05,
        "Bond Hall Bar 1": -1.9057e-05,
        "Bond Hall Bar 2": -1.9647e-05,
    }
    _CUSTOM_PRESET_NAME = "Custom"

    def __init__(self, parent: ttk.Frame, app: "MeasureApp") -> None:
        super().__init__(parent, app)
        self._conn_header: ConnectionHeader | None = None
        self._measuring = False
        self._measure_buttons: list[ttk.Button] = []
        self._source_enabled = False
        self._source_led_after_id: str | None = None
        self._updating_preset = False

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
        self._build_status(body)

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
        self.k2450_hall_v2gauss = tk.DoubleVar(value=10000.0 / 0.215)
        self.k2450_hall_bar = tk.StringVar(value="Wire Hall Bar 1")
        self.k2450_hall_v_per_g = tk.StringVar(value="")

        ttk.Label(sf, text="Hall Bar Preset:").grid(row=0, column=0, sticky="w", padx=5, pady=2)
        preset_values = [
            *list(self._HALL_BAR_PRESETS_V_PER_G.keys()),
            self._CUSTOM_PRESET_NAME,
        ]
        preset_combo = ttk.Combobox(
            sf,
            textvariable=self.k2450_hall_bar,
            values=preset_values,
            state="readonly",
            width=22,
        )
        preset_combo.grid(row=0, column=1, padx=5, pady=2, sticky="w")
        preset_combo.bind("<<ComboboxSelected>>", self._on_hall_bar_selected)

        ttk.Label(sf, text="Preset V/G:").grid(row=1, column=0, sticky="w", padx=5, pady=2)
        ttk.Label(sf, textvariable=self.k2450_hall_v_per_g).grid(row=1, column=1, sticky="w", padx=5, pady=2)

        entries = [
            ("Current (mA):", self.k2450_current, make_float_validator(0.0, 105.0)),
            ("NPLC:", self.k2450_nplc, make_float_validator(0.01, 20.0)),
            ("Compliance (V):", self.k2450_compliance_v, make_float_validator(0.0, 210.0)),
            ("Filter Count:", self.k2450_filter_count, make_float_validator(1.0, 100.0)),
            ("TBM delay (s):", self.k2450_tbm, make_float_validator(0.0, 10.0)),
            ("Hall Offset (V):", self.k2450_hall_offset, make_float_validator(-5.0, 5.0)),
            ("V→Gauss (G/V):", self.k2450_hall_v2gauss, make_float_validator(-1e7, 1e7)),
        ]

        row_offset = 2
        for i, (label, var, validator) in enumerate(entries):
            ttk.Label(sf, text=label).grid(row=i + row_offset, column=0, sticky="w", padx=5, pady=2)
            ValidatingEntry(sf, textvariable=var, width=12, validator=validator).grid(
                row=i + row_offset,
                column=1,
                padx=5,
                pady=2,
            )

        # Voltage range selector
        row = len(entries) + row_offset
        ttk.Label(sf, text="Voltage Range:").grid(row=row, column=0, sticky="w", padx=5, pady=2)
        ttk.OptionMenu(
            sf, self.k2450_voltage_range, "auto",
            "auto", "0.02", "0.2", "2", "20", "200",
        ).grid(row=row, column=1, padx=5, sticky="w")

        self._apply_hall_bar_preset(self.k2450_hall_bar.get())
        self.k2450_hall_v2gauss.trace_add("write", self._on_manual_v2gauss_changed)
        self._sync_hall_metadata_to_data_manager()

    def _sync_hall_metadata_to_data_manager(self) -> None:
        try:
            hall_bar = str(self.k2450_hall_bar.get()).strip()
            hall_offset_v = float(self.k2450_hall_offset.get())
            hall_v2gauss = float(self.k2450_hall_v2gauss.get())
            v_per_g = None
            if abs(hall_v2gauss) > 1e-12:
                v_per_g = 1.0 / hall_v2gauss
            self.app.data_mgr.set_hall_metadata(
                hall_bar=hall_bar,
                v_per_g=v_per_g,
                hall_offset_v=hall_offset_v,
            )
        except Exception:
            pass

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
            font=FONTS["mono"],
            fg=COLORS["accent_current"],
            bg=COLORS["bg_input"],
            relief="solid",
            borderwidth=1,
            padx=8,
            pady=4,
            anchor="w",
        )
        self.result_label.pack(fill="x", anchor="w", padx=5, pady=5)

    # ------------------------------------------------------------------
    # Buttons
    # ------------------------------------------------------------------
    def _build_buttons(self, parent: ttk.Frame) -> None:
        bf = ttk.Frame(parent)
        bf.pack(fill="x", padx=5, pady=5)

        self.measure_btn = ttk.Button(bf, text="Measure Hall", command=self._on_measure)
        self.measure_btn.pack(side="left", padx=5)
        self.register_measure_button(self.measure_btn)
        ttk.Button(bf, text="Set Offset...", command=self._open_offset_popup).pack(side="left", padx=5)
        ttk.Button(bf, text="Enable Source", command=self._on_enable_source).pack(side="left", padx=5)
        ttk.Button(bf, text="Disable Source", command=self._on_disable_source).pack(side="left", padx=5)

    def register_measure_button(self, button: ttk.Button) -> None:
        if button not in self._measure_buttons:
            self._measure_buttons.append(button)
        # Keep newly-created UI controls in sync with current measurement state.
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

    def _on_hall_bar_selected(self, _event: tk.Event | None = None) -> None:
        self._apply_hall_bar_preset(self.k2450_hall_bar.get())

    def _on_manual_v2gauss_changed(self, *_args: object) -> None:
        if self._updating_preset:
            return
        if self.k2450_hall_bar.get() != self._CUSTOM_PRESET_NAME:
            self.k2450_hall_bar.set(self._CUSTOM_PRESET_NAME)
            try:
                v2g = float(self.k2450_hall_v2gauss.get())
                if abs(v2g) > 1e-12:
                    self.k2450_hall_v_per_g.set(f"{(1.0 / v2g):.6e} V/G")
            except Exception:
                pass
        self._sync_hall_metadata_to_data_manager()

    def _apply_hall_bar_preset(self, preset_name: str) -> None:
        if preset_name == self._CUSTOM_PRESET_NAME:
            try:
                v2g = float(self.k2450_hall_v2gauss.get())
                if abs(v2g) > 1e-12:
                    self.k2450_hall_v_per_g.set(f"{(1.0 / v2g):.6e} V/G")
            except Exception:
                pass
            return

        v_per_g = self._HALL_BAR_PRESETS_V_PER_G.get(preset_name)
        if v_per_g is None:
            return
        self._updating_preset = True
        try:
            self.k2450_hall_v_per_g.set(f"{v_per_g:.6e} V/G")
            self.k2450_hall_v2gauss.set(1.0 / v_per_g)
        finally:
            self._updating_preset = False
        if hasattr(self, "status_text"):
            self._append_status(
                f"Applied preset '{preset_name}' (V/G={v_per_g:.6e}, G/V={1.0 / v_per_g:.2f})"
            )
        self._sync_hall_metadata_to_data_manager()

    def _center_toplevel(self, window: tk.Toplevel, width: int, height: int) -> None:
        window.update_idletasks()
        sw = window.winfo_screenwidth()
        sh = window.winfo_screenheight()
        x = max(0, (sw - width) // 2)
        y = max(0, (sh - height) // 2)
        window.geometry(f"{width}x{height}+{x}+{y}")

    def _open_offset_popup(self) -> None:
        popup = tk.Toplevel(self.app.root)
        popup.title("Set Hall Offset")
        popup.transient(self.app.root)
        popup.grab_set()

        frame = ttk.Frame(popup, padding=12)
        frame.pack(fill="both", expand=True)

        msg = (
            "Before measuring Hall offset:\n\n"
            "1. Make sure the Hall bar is outside the Dyna field region.\n"
            "2. During this offset measurement the program applies:\n"
            "   Current = 2 mA, NPLC = 10, Filter Count = 100.\n\n"
            "Press 'Measure Offset' to run one Hall measurement and set\n"
            "the measured Hall voltage as the Hall Offset (V)."
        )
        ttk.Label(frame, text=msg, justify="left").pack(anchor="w")

        btn_row = ttk.Frame(frame)
        btn_row.pack(fill="x", pady=(12, 0))

        measure_btn = ttk.Button(btn_row, text="Measure Offset")
        close_btn = ttk.Button(btn_row, text="Close", command=popup.destroy)
        measure_btn.pack(side="left", padx=(0, 8))
        close_btn.pack(side="left")

        def _run_offset() -> None:
            measure_btn.configure(state="disabled")
            close_btn.configure(state="disabled")
            self.k2450_current.set(2.0)
            self.k2450_nplc.set(10)
            self.k2450_filter_count.set(100)

            # Capture Tk-backed values on the main thread before starting the worker.
            voltage_range_raw = str(self.k2450_voltage_range.get())
            auto_range = voltage_range_raw.lower() == "auto"
            voltage_range = None if auto_range else float(voltage_range_raw)
            compliance_v = float(self.k2450_compliance_v.get())
            tbm = float(self.k2450_tbm.get())
            hall_v2gauss = float(self.k2450_hall_v2gauss.get())

            worker = threading.Thread(
                target=self._measure_and_apply_offset_worker,
                args=(popup, compliance_v, tbm, voltage_range, auto_range, hall_v2gauss),
                daemon=True,
                name="hall-offset-measure",
            )
            worker.start()

        measure_btn.configure(command=_run_offset)
        self._center_toplevel(popup, width=560, height=260)

    def _measure_and_apply_offset_worker(
        self,
        popup: tk.Toplevel,
        compliance_v: float,
        tbm: float,
        voltage_range: float | None,
        auto_range: bool,
        hall_v2gauss: float,
    ) -> None:
        try:
            from v3.core.measurements import measure_hall

            ctx = self.app.make_context()

            result = measure_hall(
                ctx,
                current_mA=2.0,
                nplc=10,
                compliance_v=compliance_v,
                voltage_range=voltage_range,
                auto_range=auto_range,
                filter_count=100,
                tbm=tbm,
            )

            voltage = float(result.get("Hall Voltage", 0.0))
            field = float(result.get("Hall Field", 0.0))
            voltage_error = abs(float(result.get("Hall Voltage Error", 0.0)))
            field_error = abs(float(result.get("Hall Field Error", 0.0)))

            if abs(hall_v2gauss) > 1e-12:
                step_v = 0.001 / abs(hall_v2gauss)
                voltage = round(voltage / step_v) * step_v

            def _apply() -> None:
                self.k2450_hall_offset.set(voltage)
                self._sync_hall_metadata_to_data_manager()
                self.app.ui_bus.post(W_HALL_RESULT, {
                    "voltage": voltage,
                    "field": field,
                    "voltage_error": voltage_error,
                    "field_error": field_error,
                })
                self._append_status(f"Hall offset updated to {voltage:.6e} V")
                self.app.ui_bus.post_log(f"Hall offset set from measurement: {voltage:.6e} V")
                if popup.winfo_exists():
                    popup.destroy()

            self.app.root.after(0, _apply)
        except Exception as exc:
            def _show_error() -> None:
                self._append_status(f"Offset measurement failed: {exc}", is_error=True)
                self.app.ui_bus.post_log(f"Hall offset measurement error: {exc}")
                if popup.winfo_exists():
                    popup.destroy()

            self.app.root.after(0, _show_error)

    def _build_status(self, parent: ttk.Frame) -> None:
        ttk.Label(parent, text="Status:", style="SectionTitle.TLabel").pack(
            anchor="w", padx=5, pady=(10, 2)
        )
        self.status_text = tk.Text(
            parent,
            height=3,
            width=70,
            font=("Courier", 10),
            background="#f0f0f0",
            relief="sunken",
            state="disabled",
        )
        self.status_text.pack(fill="x", padx=5, pady=2)

    def _append_status(self, message: str, *, is_error: bool = False) -> None:
        prefix = "Error" if is_error else "Info"
        self.status_text.configure(state="normal")
        self.status_text.insert("end", f"{prefix}: {message}\n")
        self.status_text.see("end")
        line_count = int(self.status_text.index("end-1c").split(".")[0])
        if line_count > 200:
            self.status_text.delete("1.0", f"{line_count - 200}.0")
        self.status_text.configure(state="disabled")

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
        elif widget_id == W_INSTRUMENT_ERROR:
            if isinstance(value, dict) and str(value.get("instrument")) == "hall":
                self._append_status(str(value.get("message", "Unknown error")), is_error=True)

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
        self._set_measure_buttons_enabled(False)
        t = threading.Thread(target=self._measure_worker, daemon=True, name="hall-measure")
        t.start()

    def _measure_worker(self) -> None:
        try:
            from v3.core.measurements import measure_hall
            ctx = self.app.make_context()
            self._sync_hall_metadata_to_data_manager()

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
            self._append_status(f"Measured Hall: V={voltage:.6e} V, B={field:.2f} G")
            self.app.ui_bus.post_log(
                f"Hall: V={voltage:.6e} V, B={field:.2f} G"
            )
        except Exception as exc:
            post_error = getattr(self.app, "post_instrument_error", None)
            if callable(post_error):
                post_error("hall", str(exc))
            else:
                self._append_status(str(exc), is_error=True)
            self.app.ui_bus.post_log(f"Hall measure error: {exc}")
        finally:
            try:
                self.app.root.after(0, self._measure_done)
            except Exception:
                self._measuring = False

    def _measure_done(self) -> None:
        self._measuring = False
        self._set_measure_buttons_enabled(True)

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
            self._append_status(f"Source enabled at {current_mA:.2f} mA")
            self.app.ui_bus.post_log(f"K2450 source enabled: {current_mA:.2f} mA")
        except Exception as exc:
            post_error = getattr(self.app, "post_instrument_error", None)
            if callable(post_error):
                post_error("hall", str(exc))
            else:
                self._append_status(str(exc), is_error=True)
            self.app.ui_bus.post_log(f"Enable source error: {exc}")

    def _on_disable_source(self) -> None:
        try:
            self.app.bus.execute(INST_KEITHLEY2450, "disable_source")
            self.app.ui_bus.post(W_HALL_SOURCE_ENABLED, False)
            self.app.ui_bus.post(W_LED_HALL, False)
            self._append_status("Source disabled.")
            self.app.ui_bus.post_log("K2450 source disabled.")
        except Exception as exc:
            post_error = getattr(self.app, "post_instrument_error", None)
            if callable(post_error):
                post_error("hall", str(exc))
            else:
                self._append_status(str(exc), is_error=True)
            self.app.ui_bus.post_log(f"Disable source error: {exc}")
