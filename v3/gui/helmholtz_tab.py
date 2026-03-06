"""
v3.gui.helmholtz_tab  —  Helmholtz coil control tab.

Replicates V2's Helmholtz/Keithley tab with:
* Connection header
* Current/field/compliance setpoint entries
* Ramp rate control
* Live readouts (current A/B, field, resistance A/B)
* Enable/disable output button
* Set-field button
* Helmholtz time-series plot (resistance vs time)
"""

from __future__ import annotations

import math
import tkinter as tk
from tkinter import ttk
from typing import TYPE_CHECKING, Any

from v3.core.constants import (
    DEFAULT_COMPLIANCE_V,
    DEFAULT_RAMP_RATE_mA_per_s,
    HELMHOLTZ_MAX_RAMP_RATE_mA_per_s,
)
from v3.core.helmholtz_controller import HelmholtzSafetyError
from v3.core.ui_events import (
    W_HELMHOLTZ_CONNECTED,
    W_HELMHOLTZ_CURRENT_A,
    W_HELMHOLTZ_CURRENT_B,
    W_HELMHOLTZ_FIELD,
    W_HELMHOLTZ_RAMPING,
    W_HELMHOLTZ_RESISTANCE_A,
    W_HELMHOLTZ_RESISTANCE_B,
    W_HELMHOLTZ_SETPOINT,
)
from v3.gui.base_tab import BaseTab, ConnectionHeader

if TYPE_CHECKING:
    from v3.gui.app import MeasureApp

# Try importing matplotlib — graceful fallback if not available
try:
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    from matplotlib.figure import Figure
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False


class HelmholtzTab(BaseTab):
    """Helmholtz coil control and monitoring tab."""

    def __init__(self, parent: ttk.Frame, app: "MeasureApp") -> None:
        super().__init__(parent, app)
        self._conn_header: ConnectionHeader | None = None
        self._ramping: bool = False

    def create_widgets(self) -> None:
        # --- Connection header ---
        self._conn_header = ConnectionHeader(
            self.parent,
            instrument_key="helmholtz",
            display_name="Keithley 2600 (Helmholtz)",
            on_connect=lambda: self.app.connect_instrument("helmholtz"),
            on_disconnect=lambda: self.app.disconnect_instrument("helmholtz"),
        )

        # --- Main layout: left (controls) + right (plot) ---
        body = ttk.Frame(self.parent)
        body.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        self.parent.grid_rowconfigure(1, weight=1)
        self.parent.grid_columnconfigure(0, weight=1)

        left = ttk.Frame(body, padding=10)
        left.grid(row=0, column=0, sticky="ns")

        right = ttk.Frame(body, width=620, height=520)
        right.grid(row=0, column=1, sticky="nw", padx=(10, 0))
        right.grid_propagate(False)

        self._build_controls(left)
        self._build_plot(right)

    # ------------------------------------------------------------------
    # Controls
    # ------------------------------------------------------------------
    def _build_controls(self, parent: ttk.Frame) -> None:
        # --- Setpoints ---
        sp = ttk.LabelFrame(parent, text="Setpoints")
        sp.pack(fill="x", padx=5, pady=5)

        self.set_current = tk.DoubleVar(value=0.0)
        self.compliance_voltage = tk.DoubleVar(value=DEFAULT_COMPLIANCE_V)
        self.ramp_rate = tk.DoubleVar(value=DEFAULT_RAMP_RATE_mA_per_s)

        row = 0
        for label, var, unit in [
            ("Set Current Total (A):", self.set_current, "A"),
            ("Compliance (V):", self.compliance_voltage, "V"),
            ("Ramp Rate (mA/s):", self.ramp_rate, "mA/s"),
        ]:
            ttk.Label(sp, text=label).grid(row=row, column=0, sticky="w", padx=5, pady=2)
            ttk.Entry(sp, textvariable=var, width=12).grid(row=row, column=1, padx=5, pady=2)
            ttk.Label(sp, text=unit).grid(row=row, column=2, sticky="w", padx=2)
            row += 1

        # --- Buttons ---
        btn = ttk.Frame(parent)
        btn.pack(fill="x", padx=5, pady=5)

        self.enable_btn = ttk.Button(btn, text="Enable Output", command=self._on_enable)
        self.enable_btn.pack(side="left", padx=2)

        self.disable_btn = ttk.Button(btn, text="Disable Output", command=self._on_disable)
        self.disable_btn.pack(side="left", padx=2)

        self.set_field_btn = ttk.Button(btn, text="Set", command=self._on_set_field)
        self.set_field_btn.pack(side="left", padx=2)

        self.update_btn = ttk.Button(btn, text="Update", command=self._on_set_field)
        self.update_btn.pack(side="left", padx=2)

        self.reset_plot_btn = ttk.Button(btn, text="Reset Plot", command=self._on_reset_plot)
        self.reset_plot_btn.pack(side="left", padx=2)

        # --- Readouts ---
        rd = ttk.LabelFrame(parent, text="Live Readouts")
        rd.pack(fill="x", padx=5, pady=5)

        self.readout_a = tk.Label(
            rd, text="Ch A: --- A  / --- Ω",
            font=("Courier", 14), fg="#FF6200", bg="#000000",
        )
        self.readout_a.pack(anchor="w", padx=5, pady=2)

        self.readout_b = tk.Label(
            rd, text="Ch B: --- A  / --- Ω",
            font=("Courier", 14), fg="#FF6200", bg="#000000",
        )
        self.readout_b.pack(anchor="w", padx=5, pady=2)

        self.field_display = tk.Label(
            rd, text="Field: --- G",
            font=("Courier", 14), fg="#00A000", bg="#000000",
        )
        self.field_display.pack(anchor="w", padx=5, pady=2)

        self.ramping_label = tk.Label(
            rd, text="", fg="orange", bg="#000000",
            font=("Courier", 10),
        )
        self.ramping_label.pack(anchor="w", padx=5, pady=2)

        # --- Plot interval ---
        pi = ttk.Frame(parent)
        pi.pack(fill="x", padx=5, pady=2)
        ttk.Label(pi, text="Plot interval (s):").pack(side="left")
        self.plot_interval = tk.DoubleVar(value=10.0)
        ttk.Entry(pi, textvariable=self.plot_interval, width=6).pack(side="left", padx=5)

    # ------------------------------------------------------------------
    # Plot
    # ------------------------------------------------------------------
    def _build_plot(self, parent: ttk.Frame) -> None:
        if not HAS_MATPLOTLIB:
            ttk.Label(parent, text="(matplotlib not available — no plot)").pack()
            self.canvas = None
            self.fig = None
            return

        self.fig = Figure(figsize=(6.2, 4.9), dpi=100)
        self.ax = self.fig.add_subplot(111)
        self.ax.tick_params(axis="both", which="both", direction="in")
        self.ax.set_xlabel("Time (s)")
        self.ax.set_ylabel("Resistance (Ω)")
        self.ax.set_title("Helmholtz Coils Resistance vs Time")
        self.line_a, = self.ax.plot([], [], "-o", label="Ch A", color="tab:blue", markersize=3)
        self.line_b, = self.ax.plot([], [], "-o", label="Ch B", color="tab:orange", markersize=3)
        self.ax.legend(loc="upper left", fontsize=9)
        self.fig.tight_layout()

        self.canvas = FigureCanvasTkAgg(self.fig, master=parent)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)

    def update_plot(self) -> None:
        """Refresh the Helmholtz plot with current data."""
        if self.canvas is None or self.fig is None:
            return
        t = self.app.helmholtz_time_data
        ra = self.app.helmholtz_res_a
        rb = self.app.helmholtz_res_b
        if t:
            self.line_a.set_data(t, ra)
            self.line_b.set_data(t, rb)
            self.ax.relim()
            self.ax.autoscale_view()
            self.canvas.draw_idle()

    # ------------------------------------------------------------------
    # Event handling
    # ------------------------------------------------------------------
    def on_event(self, widget_id: str, value: Any) -> None:
        if widget_id == W_HELMHOLTZ_CURRENT_A:
            self._cur_a = value
            self._update_readout_a()
        elif widget_id == W_HELMHOLTZ_CURRENT_B:
            self._cur_b = value
            self._update_readout_b()
        elif widget_id == W_HELMHOLTZ_FIELD:
            self.field_display.configure(text=f"Field: {value:.2f} G")
        elif widget_id == W_HELMHOLTZ_RESISTANCE_A:
            self._res_a = value
            self._update_readout_a()
        elif widget_id == W_HELMHOLTZ_RESISTANCE_B:
            self._res_b = value
            self._update_readout_b()
        elif widget_id == W_HELMHOLTZ_RAMPING:
            self._ramping = bool(value)
            self._update_status_label()
        elif widget_id == W_HELMHOLTZ_CONNECTED:
            if self._conn_header:
                self._conn_header.set_connected(bool(value))
        elif widget_id == W_HELMHOLTZ_SETPOINT:
            if isinstance(value, dict):
                try:
                    total_current = float(value.get("total_current_a", self.set_current.get()))
                    rate = float(value.get("rate_mA_s", self.ramp_rate.get()))
                    self.set_current.set(total_current)
                    self.ramp_rate.set(rate)
                except Exception:
                    pass

    _cur_a: float | None = None
    _cur_b: float | None = None
    _res_a: float | None = None
    _res_b: float | None = None

    def _update_readout_a(self) -> None:
        if self._cur_a is None:
            self.readout_a.configure(text="Ch A: Disconnected")
            return
        show_res = self._res_a is not None and not math.isnan(float(self._res_a))
        res_txt = f"{float(self._res_a):.3f}" if show_res else "--"
        self.readout_a.configure(text=f"Ch A: {self._cur_a:.4f} A  /  {res_txt} Ω")
        self._update_status_label()

    def _update_readout_b(self) -> None:
        if self._cur_b is None:
            self.readout_b.configure(text="Ch B: Disconnected")
            return
        show_res = self._res_b is not None and not math.isnan(float(self._res_b))
        res_txt = f"{float(self._res_b):.3f}" if show_res else "--"
        self.readout_b.configure(text=f"Ch B: {self._cur_b:.4f} A  /  {res_txt} Ω")
        self._update_status_label()

    def on_instrument_connected(self, name: str) -> None:
        if name == "helmholtz":
            if self._conn_header:
                self._conn_header.set_connected(True)
            self._cur_a = 0.0
            self._cur_b = 0.0
            self._res_a = None
            self._res_b = None
            self._ramping = False
            self._update_readout_a()
            self._update_readout_b()
            self.field_display.configure(text="Field: 0.00 G")

    def on_instrument_disconnected(self, name: str) -> None:
        if name == "helmholtz":
            if self._conn_header:
                self._conn_header.set_connected(False)
            self._cur_a = None
            self._cur_b = None
            self._res_a = None
            self._res_b = None
            self._ramping = False
            self._update_readout_a()
            self._update_readout_b()
            self.field_display.configure(text="Field: Disconnected")

    def _update_status_label(self) -> None:
        if self._cur_a is None or self._cur_b is None:
            self.ramping_label.configure(text="")
            return
        if self._ramping:
            status = "Ramping"
        elif (abs(float(self._cur_a)) + abs(float(self._cur_b))) > 1e-6:
            status = "Holding"
        else:
            status = "Idle"
        self.ramping_label.configure(text=f"Status: {status}")
    # ------------------------------------------------------------------
    # Button handlers
    # ------------------------------------------------------------------
    def _on_enable(self) -> None:
        try:
            c = self.compliance_voltage.get()
            r = min(self.ramp_rate.get(), HELMHOLTZ_MAX_RAMP_RATE_mA_per_s)
            if r <= 0:
                r = DEFAULT_RAMP_RATE_mA_per_s
                self.ramp_rate.set(r)
                self.app.ui_bus.post_log("Helmholtz ramp rate must be > 0; reset to default.")
            if self.ramp_rate.get() > HELMHOLTZ_MAX_RAMP_RATE_mA_per_s:
                self.ramp_rate.set(r)
                self.app.ui_bus.post_log(
                    f"Helmholtz ramp rate capped to {HELMHOLTZ_MAX_RAMP_RATE_mA_per_s:.1f} mA/s (V2 max)."
                )
            self.app.helmholtz.set_compliance(c)
            self.app.helmholtz.set_ramp_rate(r)
            self.app.helmholtz.enable_output()
            self.app.ui_bus.post_log("Helmholtz output enabled.")
        except Exception as exc:
            self.app.ui_bus.post_log(f"Enable error: {exc}")

    def _on_disable(self) -> None:
        try:
            self.app.helmholtz.disable_output()
            self.app.ui_bus.post_log("Helmholtz output disabled.")
        except Exception as exc:
            self.app.ui_bus.post_log(f"Disable error: {exc}")

    def _on_set_field(self) -> None:
        """Set Helmholtz current/compliance/ramp parameters (V2-style set-values)."""
        try:
            total_current = self.set_current.get()
            current_per_coil = total_current / 2.0
            rate = min(self.ramp_rate.get(), HELMHOLTZ_MAX_RAMP_RATE_mA_per_s)
            if rate <= 0:
                rate = DEFAULT_RAMP_RATE_mA_per_s
                self.ramp_rate.set(rate)
                self.app.ui_bus.post_log("Helmholtz ramp rate must be > 0; reset to default.")
            if self.ramp_rate.get() > HELMHOLTZ_MAX_RAMP_RATE_mA_per_s:
                self.ramp_rate.set(rate)
                self.app.ui_bus.post_log(
                    f"Helmholtz ramp rate capped to {HELMHOLTZ_MAX_RAMP_RATE_mA_per_s:.1f} mA/s (V2 max)."
                )
            self.app.helmholtz.set_compliance(self.compliance_voltage.get())
            self.app.helmholtz.set_ramp_rate(rate)
            self.app.helmholtz.set_current(current_per_coil)
            self.app.ui_bus.post_log(
                f"Helmholtz values set: total {total_current:.4f} A "
                f"({current_per_coil:.4f} A/coil), "
                f"{self.compliance_voltage.get():.2f} V, {rate:.1f} mA/s"
            )
        except HelmholtzSafetyError as exc:
            self.app.ui_bus.post_log(f"Safety: {exc}")
        except Exception as exc:
            self.app.ui_bus.post_log(f"Set values error: {exc}")

    def _on_reset_plot(self) -> None:
        """Reset the Helmholtz resistance plot — clears data and shows only future data."""
        import time
        now = time.time()
        self.app.helmholtz_time_data.clear()
        self.app.helmholtz_res_a.clear()
        self.app.helmholtz_res_b.clear()
        self.app.start_time = now
        self.app.last_plot_time = now
        if self.canvas is not None:
            self.line_a.set_data([], [])
            self.line_b.set_data([], [])
            self.ax.set_autoscalex_on(True)
            self.ax.set_autoscaley_on(True)
            self.canvas.draw()
        self.app.ui_bus.post_log(
            f"[{time.strftime('%H:%M:%S')}] Helmholtz plot reset — showing only new data."
        )
