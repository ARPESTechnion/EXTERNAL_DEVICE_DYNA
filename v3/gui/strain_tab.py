"""
v3.gui.strain_tab  -  RP100 / AH2550A strain-control tab.
"""

from __future__ import annotations

import threading
import tkinter as tk
from tkinter import ttk
from typing import TYPE_CHECKING, Any

from v3.core.constants import DATA_KEY_TO_CSV
from v3.core.strain import generate_voltage_list
from v3.core.ui_events import (
    W_LED_STRAIN,
    W_RESULTS_NEW_POINT,
    W_STRAIN_CAPACITANCE,
    W_STRAIN_CONNECTED,
    W_STRAIN_FORCE,
    W_STRAIN_LOSS,
    W_STRAIN_STATUS,
    W_STRAIN_VOLTAGE_CH1,
    W_STRAIN_VOLTAGE_CH2,
)
from v3.gui.base_tab import BaseTab, ConnectionHeader, make_led
from v3.gui.components import ControlGroup, ValidatingEntry, make_float_validator
from v3.gui.theme import COLORS, FONTS

if TYPE_CHECKING:
    from v3.gui.app import MeasureApp


class StrainTab(BaseTab):
    """Strain-control tab for the RP100 and AH2550A bridge."""

    def __init__(self, parent: ttk.Frame, app: "MeasureApp") -> None:
        super().__init__(parent, app)
        self._conn_header: ConnectionHeader | None = None
        self._measuring = False
        self._measure_lock = threading.Lock()
        self._apply_thread: threading.Thread | None = None
        self._scan_worker: threading.Thread | None = None
        self._connected = False
        self._applied_ch1: float | None = None
        self._applied_ch2: float | None = None
        self._capacitance: float | None = None
        self._loss: float | None = None
        self._force: float | None = None
        self._is_applying = False

    def create_widgets(self) -> None:
        self._conn_header = ConnectionHeader(
            self.parent,
            instrument_key="strain",
            display_name="RP100 / AH2550A",
            on_connect=lambda: self.app.connect_instrument("strain"),
            on_disconnect=lambda: self.app.disconnect_instrument("strain"),
        )

        body = ttk.Frame(self.parent)
        body.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        self.parent.grid_rowconfigure(1, weight=1)
        self.parent.grid_columnconfigure(0, weight=1)

        left = ttk.Frame(body, padding=10)
        left.grid(row=0, column=0, sticky="ns")

        right = ttk.Frame(body, padding=10)
        right.grid(row=0, column=1, sticky="nwes")
        right.grid_columnconfigure(0, weight=1)

        self._build_controls(left)
        self._build_readouts(right)
        self._update_strain_led_state()

    def _build_controls(self, parent: ttk.Frame) -> None:
        source = ControlGroup(parent, "Manual Strain Control")
        sf = source.body

        self.ch1_voltage = tk.DoubleVar(value=0.0)
        self.ch2_voltage = tk.DoubleVar(value=0.0)
        self.dwell_s = tk.DoubleVar(value=10.0)

        ttk.Label(sf, text="Ch1 Voltage (V):").grid(row=0, column=0, sticky="w", padx=5, pady=2)
        ValidatingEntry(sf, textvariable=self.ch1_voltage, width=10, validator=make_float_validator(-250.0, 250.0)).grid(row=0, column=1, padx=5, pady=2)
        ttk.Label(sf, text="Ch2 Voltage (V):").grid(row=1, column=0, sticky="w", padx=5, pady=2)
        ValidatingEntry(sf, textvariable=self.ch2_voltage, width=10, validator=make_float_validator(-250.0, 250.0)).grid(row=1, column=1, padx=5, pady=2)
        ttk.Label(sf, text="Dwell (s):").grid(row=2, column=0, sticky="w", padx=5, pady=2)
        ValidatingEntry(sf, textvariable=self.dwell_s, width=10, validator=make_float_validator(0.0, 120.0)).grid(row=2, column=1, padx=5, pady=2)

        btn_row = ttk.Frame(sf)
        btn_row.grid(row=3, column=0, columnspan=2, sticky="w", padx=5, pady=(6, 2))
        self.apply_btn = ttk.Button(btn_row, text="Apply Strain", style="Primary.TButton", command=self._on_apply_strain)
        self.apply_btn.pack(side="left", padx=(0, 5))
        self.scan_btn = ttk.Button(btn_row, text="Scan Strain", style="Secondary.TButton", command=self._on_scan_strain)
        self.scan_btn.pack(side="left")

        scan = ttk.LabelFrame(parent, text="Scan Range")
        scan.pack(fill="x", padx=5, pady=(8, 5))
        self.scan_start = tk.DoubleVar(value=0.0)
        self.scan_end = tk.DoubleVar(value=20.0)
        self.scan_step = tk.DoubleVar(value=2.0)
        ttk.Label(scan, text="Start (V):").grid(row=0, column=0, sticky="w", padx=5, pady=2)
        ValidatingEntry(scan, textvariable=self.scan_start, width=10, validator=make_float_validator(-250.0, 250.0)).grid(row=0, column=1, padx=5, pady=2)
        ttk.Label(scan, text="End (V):").grid(row=1, column=0, sticky="w", padx=5, pady=2)
        ValidatingEntry(scan, textvariable=self.scan_end, width=10, validator=make_float_validator(-250.0, 250.0)).grid(row=1, column=1, padx=5, pady=2)
        ttk.Label(scan, text="Step (V):").grid(row=2, column=0, sticky="w", padx=5, pady=2)
        ValidatingEntry(scan, textvariable=self.scan_step, width=10, validator=make_float_validator(1e-9, 250.0)).grid(row=2, column=1, padx=5, pady=2)

        ttk.Label(parent, text="Activity:", style="SectionTitle.TLabel").pack(anchor="w", padx=5, pady=(8, 2))
        self.activity_led = make_led(parent)
        self.activity_led.pack(anchor="w", padx=5)
        self.activity_label = ttk.Label(parent, text="Idle")
        self.activity_label.pack(anchor="w", padx=5, pady=(2, 0))

    def _build_readouts(self, parent: ttk.Frame) -> None:
        rd_group = ControlGroup(parent, "Live Readouts")
        rd = rd_group.body

        self.ch1_display = tk.Label(rd, text="Ch1: N/A", font=FONTS["mono"], fg=COLORS["accent_current"], bg=COLORS["bg_input"], relief="solid", borderwidth=1, padx=6, pady=2, anchor="w")
        self.ch1_display.pack(fill="x", padx=5, pady=(5, 2))
        self.ch2_display = tk.Label(rd, text="Ch2: N/A", font=FONTS["mono"], fg=COLORS["accent_current"], bg=COLORS["bg_input"], relief="solid", borderwidth=1, padx=6, pady=2, anchor="w")
        self.ch2_display.pack(fill="x", padx=5, pady=2)
        self.cap_display = tk.Label(rd, text="Capacitance: N/A", font=FONTS["mono"], fg=COLORS["accent_field"], bg=COLORS["bg_input"], relief="solid", borderwidth=1, padx=6, pady=2, anchor="w")
        self.cap_display.pack(fill="x", padx=5, pady=2)
        self.loss_display = tk.Label(rd, text="Loss: N/A", font=FONTS["mono"], fg=COLORS["accent_info"], bg=COLORS["bg_input"], relief="solid", borderwidth=1, padx=6, pady=2, anchor="w")
        self.loss_display.pack(fill="x", padx=5, pady=2)
        self.force_display = tk.Label(rd, text="Force: N/A", font=FONTS["mono"], fg=COLORS["accent_warn"], bg=COLORS["bg_input"], relief="solid", borderwidth=1, padx=6, pady=2, anchor="w")
        self.force_display.pack(fill="x", padx=5, pady=2)

        ttk.Label(rd, text="Status:", style="SectionTitle.TLabel").pack(anchor="w", padx=5, pady=(8, 2))
        self.status_text = tk.Text(rd, height=4, width=58, state="disabled", font=FONTS["mono_small"], wrap="word", foreground=COLORS["fg_primary"], background=COLORS["bg_input"], insertbackground=COLORS["fg_primary"])
        self.status_text.pack(fill="both", expand=False, padx=5, pady=2)

    def _append_status(self, msg: str) -> None:
        self.status_text.configure(state="normal")
        self.status_text.insert("end", msg + "\n")
        self.status_text.see("end")
        self.status_text.configure(state="disabled")

    def _set_led_color(self, led: tk.Label, color: str) -> None:
        led.configure(fg=color)

    def _update_strain_led_state(self) -> None:
        # Strain tri-state policy:
        # red   -> disconnected
        # green -> currently applying/scan in progress
        # yellow-> connected and idle (holding last set voltage)
        if not self._connected:
            self._set_led_color(self.activity_led, COLORS["led_off"])
            self.activity_label.configure(text="Disconnected")
            if self._conn_header is not None:
                self._set_led_color(self._conn_header.led, COLORS["led_off"])
            return

        if self._is_applying:
            self._set_led_color(self.activity_led, COLORS["led_on"])
            self.activity_label.configure(text="Applying")
            if self._conn_header is not None:
                self._set_led_color(self._conn_header.led, COLORS["led_on"])
            return

        idle_color = COLORS["accent_warn"]
        self._set_led_color(self.activity_led, idle_color)
        self.activity_label.configure(text="Idle (holding)")
        if self._conn_header is not None:
            self._set_led_color(self._conn_header.led, idle_color)

    def _set_busy(self, busy: bool, text: str | None = None) -> None:
        self._is_applying = bool(busy)
        self._update_strain_led_state()

    def _temperature_k(self) -> float:
        temp = getattr(self.app, "current_temp", None)
        if temp is None:
            return 300.0
        try:
            return float(temp)
        except Exception:
            return 300.0

    def _record_strain_row(self, ch1: float, ch2: float, cap: float | None, loss: float | None, force: float | None) -> None:
        row = {
            "Measurement_Type": "Strain",
            "Temp": self._temperature_k(),
            "Strain Voltage Ch1": ch1,
            "Strain Voltage Ch2": ch2,
            "Strain Capacitance": cap,
            "Strain Loss": loss,
            "Strain Force": force,
        }
        try:
            self.app.data_mgr.write_row(row, measurement_type="Strain")
            self.app.ui_bus.post(W_RESULTS_NEW_POINT, True)
        except Exception as exc:
            self.app.ui_bus.post_log(f"Strain data write error: {exc}")

    def _apply_current_settings(self) -> None:
        if self._measuring:
            self.app.ui_bus.post_log("Strain operation already in progress.")
            return
        if not self._connected:
            self._append_status("Strain control is disconnected.")
            return
        self._measuring = True
        self._set_busy(True, "Applying")
        worker = threading.Thread(target=self._apply_worker_fn, daemon=True, name="strain-apply")
        self._apply_thread = worker
        worker.start()

    def _on_apply_strain(self) -> None:
        self._apply_current_settings()

    def _apply_worker_fn(self) -> None:
        try:
            controller = self.app.strain
            temp_k = self._temperature_k()
            ch1 = float(self.ch1_voltage.get())
            ch2 = float(self.ch2_voltage.get())
            dwell = float(self.dwell_s.get())
            self.app.ui_bus.post(W_LED_STRAIN, True)
            cap, loss, force = controller.apply_strain(ch1, ch2, sleeptime=dwell, temperature_k=temp_k)
            self._applied_ch1 = ch1
            self._applied_ch2 = ch2
            self._capacitance = cap
            self._loss = loss
            self._force = force

            self.app.ui_bus.post(W_STRAIN_VOLTAGE_CH1, ch1)
            self.app.ui_bus.post(W_STRAIN_VOLTAGE_CH2, ch2)
            self.app.ui_bus.post(W_STRAIN_CAPACITANCE, cap)
            self.app.ui_bus.post(W_STRAIN_LOSS, loss)
            self.app.ui_bus.post(W_STRAIN_FORCE, force)

            self._record_strain_row(ch1, ch2, cap, loss, force)
            self._append_status(f"Applied strain: Ch1={ch1:.3f} V, Ch2={ch2:.3f} V")
            self.app.ui_bus.post_log(f"Strain applied: Ch1={ch1:.3f} V, Ch2={ch2:.3f} V")
        except Exception as exc:
            post_error = getattr(self.app, "post_instrument_error", None)
            if callable(post_error):
                post_error("strain", str(exc))
            self._append_status(str(exc))
            self.app.ui_bus.post_log(f"Strain apply error: {exc}")
        finally:
            self.app.ui_bus.post(W_LED_STRAIN, False)
            self.app.root.after(0, self._measure_done)

    def _on_scan_strain(self) -> None:
        if self._measuring:
            self.app.ui_bus.post_log("Strain operation already in progress.")
            return
        if not self._connected:
            self._append_status("Strain control is disconnected.")
            return
        self._measuring = True
        self._set_busy(True, "Scanning")
        worker = threading.Thread(target=self._scan_worker_fn, daemon=True, name="strain-scan")
        self._scan_worker = worker
        worker.start()

    def _scan_worker_fn(self) -> None:
        try:
            controller = self.app.strain
            temp_k = self._temperature_k()
            pairs = generate_voltage_list(self.scan_start.get(), self.scan_end.get(), self.scan_step.get())
            for ch1, ch2 in pairs:
                self.app.ui_bus.post(W_LED_STRAIN, True)
                cap, loss, force = controller.apply_strain(ch1, ch2, sleeptime=float(self.dwell_s.get()), temperature_k=temp_k)
                self._applied_ch1 = ch1
                self._applied_ch2 = ch2
                self._capacitance = cap
                self._loss = loss
                self._force = force
                self.app.ui_bus.post(W_STRAIN_VOLTAGE_CH1, ch1)
                self.app.ui_bus.post(W_STRAIN_VOLTAGE_CH2, ch2)
                self.app.ui_bus.post(W_STRAIN_CAPACITANCE, cap)
                self.app.ui_bus.post(W_STRAIN_LOSS, loss)
                self.app.ui_bus.post(W_STRAIN_FORCE, force)
                self._record_strain_row(ch1, ch2, cap, loss, force)
            self._append_status(f"Strain scan completed: {len(pairs)} points")
            self.app.ui_bus.post_log(f"Strain scan completed: {len(pairs)} points")
        except Exception as exc:
            post_error = getattr(self.app, "post_instrument_error", None)
            if callable(post_error):
                post_error("strain", str(exc))
            self._append_status(str(exc))
            self.app.ui_bus.post_log(f"Strain scan error: {exc}")
        finally:
            self.app.ui_bus.post(W_LED_STRAIN, False)
            self.app.root.after(0, self._measure_done)

    def _measure_done(self) -> None:
        self._measuring = False
        self._set_busy(False, "Idle")

    def on_event(self, widget_id: str, value: Any) -> None:
        if widget_id == W_STRAIN_CONNECTED:
            self._connected = bool(value)
            if self._conn_header is not None:
                self._conn_header.set_connected(self._connected)
            self._update_strain_led_state()
        elif widget_id == W_LED_STRAIN:
            self._is_applying = bool(value)
            self._update_strain_led_state()
        elif widget_id == W_STRAIN_STATUS:
            self._append_status(str(value))
        elif widget_id == W_STRAIN_VOLTAGE_CH1:
            self._applied_ch1 = None if value is None else float(value)
            self.ch1_display.configure(text=f"Ch1: {value:.3f} V" if value is not None else "Ch1: N/A")
        elif widget_id == W_STRAIN_VOLTAGE_CH2:
            self._applied_ch2 = None if value is None else float(value)
            self.ch2_display.configure(text=f"Ch2: {value:.3f} V" if value is not None else "Ch2: N/A")
        elif widget_id == W_STRAIN_CAPACITANCE:
            self._capacitance = None if value is None else float(value)
            self.cap_display.configure(text=f"Capacitance: {self._capacitance:.6f} pF" if self._capacitance is not None else "Capacitance: N/A")
        elif widget_id == W_STRAIN_LOSS:
            self._loss = None if value is None else float(value)
            self.loss_display.configure(text=f"Loss: {self._loss:.6f}" if self._loss is not None else "Loss: N/A")
        elif widget_id == W_STRAIN_FORCE:
            self._force = None if value is None else float(value)
            self.force_display.configure(text=f"Force: {self._force:.6f}" if self._force is not None else "Force: N/A")

    def on_instrument_connected(self, name: str) -> None:
        if name == "strain" and self._conn_header is not None:
            self._conn_header.set_connected(True)
            self._connected = True
            self._is_applying = False
            self._update_strain_led_state()

    def on_instrument_disconnected(self, name: str) -> None:
        if name == "strain" and self._conn_header is not None:
            self._conn_header.set_connected(False)
            self._connected = False
            self._measuring = False
            self._is_applying = False
            self._update_strain_led_state()