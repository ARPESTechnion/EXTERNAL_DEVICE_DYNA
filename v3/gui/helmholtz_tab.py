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
    W_INSTRUMENT_ERROR,
)
from v3.gui.base_tab import BaseTab, ConnectionHeader
from v3.gui.components import ControlGroup, ValidatingEntry, make_float_validator
from v3.gui.theme import COLORS, FONTS

if TYPE_CHECKING:
    from v3.gui.app import MeasureApp

# Try importing matplotlib — graceful fallback if not available
try:
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
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
        self._field_rate_mA_s: float | None = None
        self._field_value_g: float | None = None
        self._syncing_setpoints: bool = False
        self._setpoint_input_mode: str = "current"
        self._detached_plot_window: tk.Toplevel | None = None
        self._detached_fig = None
        self._detached_canvas = None
        self._detached_ax = None
        self._detached_line_a = None
        self._detached_line_b = None

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

        right = ttk.Frame(body, width=620, height=470)
        right.grid(row=0, column=1, sticky="nw", padx=(10, 0))
        right.grid_propagate(False)

        self._build_controls(left)
        self._build_plot(right)

    # ------------------------------------------------------------------
    # Controls
    # ------------------------------------------------------------------
    def _build_controls(self, parent: ttk.Frame) -> None:
        # --- Setpoints ---
        sp_group = ControlGroup(parent, "Setpoints")
        sp = sp_group.body

        self.set_current = tk.DoubleVar(value=0.0)
        self.set_field_gauss = tk.DoubleVar(value=0.0)
        self.compliance_voltage = tk.DoubleVar(value=DEFAULT_COMPLIANCE_V)
        self.ramp_rate = tk.DoubleVar(value=DEFAULT_RAMP_RATE_mA_per_s)
        self.field_ramp_rate = tk.DoubleVar(value=self._current_rate_to_field_rate(DEFAULT_RAMP_RATE_mA_per_s))

        ttk.Label(sp, text="Set Current Total (A):").grid(row=0, column=0, sticky="w", padx=5, pady=2)
        ValidatingEntry(sp, textvariable=self.set_current, width=12, validator=make_float_validator(-10.0, 10.0)).grid(row=0, column=1, padx=5, pady=2)
        ttk.Label(sp, text="A").grid(row=0, column=2, sticky="w", padx=2)

        ttk.Label(sp, text="Set Field (G):").grid(row=0, column=3, sticky="w", padx=(14, 5), pady=2)
        ValidatingEntry(sp, textvariable=self.set_field_gauss, width=12, validator=make_float_validator(-50000.0, 50000.0)).grid(row=0, column=4, padx=5, pady=2)
        ttk.Label(sp, text="G").grid(row=0, column=5, sticky="w", padx=2)

        ttk.Label(sp, text="Compliance (V):").grid(row=1, column=0, sticky="w", padx=5, pady=2)
        ValidatingEntry(sp, textvariable=self.compliance_voltage, width=12, validator=make_float_validator(0.0, 20.0)).grid(row=1, column=1, padx=5, pady=2)
        ttk.Label(sp, text="V").grid(row=1, column=2, sticky="w", padx=2)

        ttk.Label(sp, text="Ramp Rate (mA/s):").grid(row=2, column=0, sticky="w", padx=5, pady=2)
        ValidatingEntry(sp, textvariable=self.ramp_rate, width=12, validator=make_float_validator(0.0, HELMHOLTZ_MAX_RAMP_RATE_mA_per_s)).grid(row=2, column=1, padx=5, pady=2)
        ttk.Label(sp, text="mA/s").grid(row=2, column=2, sticky="w", padx=2)

        ttk.Label(sp, text="Field Ramp Rate (G/s):").grid(row=2, column=3, sticky="w", padx=(14, 5), pady=2)
        ValidatingEntry(sp, textvariable=self.field_ramp_rate, width=12, validator=make_float_validator(0.0, 10000.0)).grid(row=2, column=4, padx=5, pady=2)
        ttk.Label(sp, text="G/s").grid(row=2, column=5, sticky="w", padx=2)

        # --- Buttons ---
        btn = ttk.Frame(parent)
        btn.pack(fill="x", padx=5, pady=5)

        self.enable_btn = ttk.Button(btn, text="Enable Output", style="Primary.TButton", command=self._on_enable)
        self.enable_btn.pack(side="left", padx=2)

        self.disable_btn = ttk.Button(btn, text="Disable Output", style="Danger.TButton", command=self._on_disable)
        self.disable_btn.pack(side="left", padx=2)

        self.set_current_btn = ttk.Button(btn, text="Set Current", style="Primary.TButton", command=self._on_set_current)
        self.set_current_btn.pack(side="left", padx=2)

        self.set_field_btn = ttk.Button(btn, text="Set Field", style="Primary.TButton", command=self._on_set_field_from_gauss)
        self.set_field_btn.pack(side="left", padx=2)

        self.update_btn = ttk.Button(btn, text="Update", style="Secondary.TButton", command=self._on_set_current)
        self.update_btn.pack(side="left", padx=2)

        # --- Readouts ---
        rd_group = ControlGroup(parent, "Live Readouts")
        rd = rd_group.body


        self.readout_a = tk.Label(
            rd,
            text="Ch A: --- A  / --- Ω",
            font=FONTS["mono"],
            fg=COLORS["accent_current"],
            bg=COLORS["bg_input"],
            relief="solid",
            borderwidth=1,
            padx=6,
            pady=2,
            anchor="w",
        )
        self.readout_a.pack(fill="x", anchor="w", padx=5, pady=(5, 2))

        self.readout_b = tk.Label(
            rd,
            text="Ch B: --- A  / --- Ω",
            font=FONTS["mono"],
            fg=COLORS["accent_resistance"],
            bg=COLORS["bg_input"],
            relief="solid",
            borderwidth=1,
            padx=6,
            pady=2,
            anchor="w",
        )
        self.readout_b.pack(fill="x", anchor="w", padx=5, pady=2)

        self.field_display = tk.Label(
            rd,
            text="Field: --- G",
            font=FONTS["mono"],
            fg=COLORS["accent_field"],
            bg=COLORS["bg_input"],
            relief="solid",
            borderwidth=1,
            padx=6,
            pady=2,
            anchor="w",
        )
        self.field_display.pack(fill="x", anchor="w", padx=5, pady=2)

        self.state_label = tk.Label(
            rd,
            text="",
            fg=COLORS["fg_muted"],
            bg=COLORS["bg_input"],
            font=FONTS["mono_small"],
            relief="solid",
            borderwidth=1,
            padx=6,
            pady=2,
            anchor="w",
        )
        self.state_label.pack(fill="x", anchor="w", padx=5, pady=(2, 5))

        # --- Plot interval ---
        pi = ttk.Frame(parent)
        pi.pack(fill="x", padx=5, pady=2)
        ttk.Label(pi, text="Plot interval (s):").pack(side="left")
        self.plot_interval = tk.DoubleVar(value=10.0)
        ValidatingEntry(pi, textvariable=self.plot_interval, width=6, validator=make_float_validator(0.1, 120.0)).pack(side="left", padx=5)
        self.reset_plot_btn = ttk.Button(pi, text="Reset Plot", command=self._on_reset_plot)
        self.reset_plot_btn.pack(side="left", padx=4)

        self.open_window_btn = ttk.Button(pi, text="Open Graph Window", command=self._open_detached_plot_window)
        self.open_window_btn.pack(side="left", padx=4)

        ttk.Label(parent, text="Status:", style="SectionTitle.TLabel").pack(
            anchor="w", padx=5, pady=(8, 2)
        )
        self.status_text = tk.Text(
            parent,
            height=3,
            width=56,
            font=FONTS["mono_small"],
            background=COLORS["bg_input"],
            foreground=COLORS["fg_primary"],
            insertbackground=COLORS["fg_primary"],
            relief="sunken",
            state="disabled",
        )
        self.status_text.pack(fill="x", padx=5, pady=2)

        self.set_current.trace_add("write", self._on_current_input_changed)
        self.ramp_rate.trace_add("write", self._on_current_rate_input_changed)
        self.set_field_gauss.trace_add("write", self._on_field_input_changed)
        self.field_ramp_rate.trace_add("write", self._on_field_rate_input_changed)
        self.update_btn.configure(command=self._on_update_setpoint)

        self._sync_field_setpoint_from_current()

    # ------------------------------------------------------------------
    # Plot
    # ------------------------------------------------------------------
    def _build_plot(self, parent: ttk.Frame) -> None:
        if not HAS_MATPLOTLIB:
            ttk.Label(parent, text="(matplotlib not available — no plot)").pack()
            self.canvas = None
            self.fig = None
            return

        self.fig, self.ax, self.line_a, self.line_b, self.canvas = self._create_plot_components(parent)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)
        toolbar = NavigationToolbar2Tk(self.canvas, parent)
        toolbar.update()

    def _create_plot_components(self, parent: tk.Widget):
        fig = Figure(figsize=(6.2, 4.9), dpi=100, constrained_layout=True)
        ax = fig.add_subplot(111)
        ax.tick_params(axis="both", which="both", direction="in")
        ax.set_xlabel("Time (s)")
        ax.set_ylabel("Resistance (Ω)")
        ax.set_title("Helmholtz Coils Resistance vs Time")
        line_a, = ax.plot([], [], "-o", label="Ch A", color="tab:blue", markersize=3)
        line_b, = ax.plot([], [], "-o", label="Ch B", color="tab:orange", markersize=3)
        ax.legend(loc="upper left", fontsize=9)
        canvas = FigureCanvasTkAgg(fig, master=parent)
        return fig, ax, line_a, line_b, canvas

    def _open_detached_plot_window(self) -> None:
        if not HAS_MATPLOTLIB or self.canvas is None:
            return
        if self._detached_plot_window is not None and self._detached_plot_window.winfo_exists():
            self._detached_plot_window.lift()
            self._detached_plot_window.focus_force()
            return

        win = tk.Toplevel(self.app.root)
        win.title("Helmholtz Plot")
        win.geometry("720x560")
        win.attributes("-topmost", True)
        frame = ttk.Frame(win, padding=6)
        frame.pack(fill="both", expand=True)
        (
            self._detached_fig,
            self._detached_ax,
            self._detached_line_a,
            self._detached_line_b,
            self._detached_canvas,
        ) = self._create_plot_components(frame)
        self._detached_canvas.get_tk_widget().pack(fill="both", expand=True)
        detached_toolbar = NavigationToolbar2Tk(self._detached_canvas, frame)
        detached_toolbar.update()
        self._detached_plot_window = win
        win.bind("<Configure>", self._on_detached_window_resize)
        win.protocol("WM_DELETE_WINDOW", self._close_detached_plot_window)
        self.update_plot()

    def _on_detached_window_resize(self, _event: tk.Event) -> None:
        if self._detached_canvas is None or self._detached_fig is None:
            return
        self._detached_fig.tight_layout(pad=0.5)
        self._detached_canvas.draw_idle()

    def _close_detached_plot_window(self) -> None:
        if self._detached_plot_window is not None and self._detached_plot_window.winfo_exists():
            self._detached_plot_window.destroy()
        self._detached_plot_window = None
        self._detached_fig = None
        self._detached_canvas = None
        self._detached_ax = None
        self._detached_line_a = None
        self._detached_line_b = None

    def update_plot(self) -> None:
        """Refresh the Helmholtz plot with current data."""
        if self.canvas is None or self.fig is None:
            return
        t = self.app.helmholtz_time_data
        ra = self.app.helmholtz_res_a
        rb = self.app.helmholtz_res_b
        if t:
            self._update_plot_components(t, ra, rb, self.ax, self.line_a, self.line_b, self.canvas)
            if self._detached_canvas is not None and self._detached_plot_window is not None:
                self._update_plot_components(
                    t,
                    ra,
                    rb,
                    self._detached_ax,
                    self._detached_line_a,
                    self._detached_line_b,
                    self._detached_canvas,
                )

    @staticmethod
    def _update_plot_components(t_data, res_a, res_b, ax, line_a, line_b, canvas) -> None:
        line_a.set_data(t_data, res_a)
        line_b.set_data(t_data, res_b)
        ax.relim()
        ax.autoscale_view()
        canvas.draw_idle()

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
            self._field_value_g = float(value)
            self._update_field_display()
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
                    field_g = float(
                        value.get("field_g", self._current_to_field(total_current))
                    )
                    self._syncing_setpoints = True
                    self.set_current.set(total_current)
                    self.ramp_rate.set(rate)
                    self.set_field_gauss.set(field_g)
                    self.field_ramp_rate.set(self._current_rate_to_field_rate(rate))
                    self._syncing_setpoints = False
                    self._field_rate_mA_s = rate
                    self._update_field_display()
                    if self._cur_a is not None and self._cur_b is not None:
                        self._update_status_label()
                except Exception:
                    self._syncing_setpoints = False
                    pass
        elif widget_id == W_INSTRUMENT_ERROR:
            if isinstance(value, dict) and str(value.get("instrument")) == "helmholtz":
                self._append_status(str(value.get("message", "Unknown error")), is_error=True)

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
            self._field_value_g = 0.0
            self._syncing_setpoints = True
            self.set_current.set(0.0)
            self.set_field_gauss.set(0.0)
            self.ramp_rate.set(DEFAULT_RAMP_RATE_mA_per_s)
            self.field_ramp_rate.set(self._current_rate_to_field_rate(DEFAULT_RAMP_RATE_mA_per_s))
            self._syncing_setpoints = False
            self._update_readout_a()
            self._update_readout_b()
            self._update_field_display()

    def on_instrument_disconnected(self, name: str) -> None:
        if name == "helmholtz":
            if self._conn_header:
                self._conn_header.set_connected(False)
            self._cur_a = None
            self._cur_b = None
            self._res_a = None
            self._res_b = None
            self._ramping = False
            self._field_value_g = None
            self._update_readout_a()
            self._update_readout_b()
            self.field_display.configure(text="Field: Disconnected")

    def _update_field_display(self) -> None:
        if self._field_value_g is None:
            self.field_display.configure(text="Field: Disconnected")
            return
        rate_suffix = (
            f" {self._field_rate_mA_s:.1f} mA/s"
            if self._field_rate_mA_s is not None
            else ""
        )
        self.field_display.configure(text=f"Field: {self._field_value_g:.2f} G{rate_suffix}")

    def _update_status_label(self) -> None:
        if self._cur_a is None or self._cur_b is None:
            self.state_label.configure(text="")
            return
        if self._ramping:
            status = "Ramping"
        elif (abs(float(self._cur_a)) + abs(float(self._cur_b))) > 1e-6:
            status = "Holding"
        else:
            status = "Idle"
        rate_suffix = (
            f" {self._field_rate_mA_s:.1f} mA/s"
            if self._field_rate_mA_s is not None
            else ""
        )
        self.state_label.configure(text=f"State: {status}{rate_suffix}")

    def _append_status(self, message: str, *, is_error: bool = False) -> None:
        prefix = "Error" if is_error else "Info"
        self.status_text.configure(state="normal")
        self.status_text.insert("end", f"{prefix}: {message}\n")
        self.status_text.see("end")
        line_count = int(self.status_text.index("end-1c").split(".")[0])
        if line_count > 200:
            self.status_text.delete("1.0", f"{line_count - 200}.0")
        self.status_text.configure(state="disabled")

    def _current_to_field(self, total_current_a: float) -> float:
        return float(total_current_a) * float(self.app.calibration.ga_total)

    def _field_to_current(self, field_gauss: float) -> float:
        return float(field_gauss) / float(self.app.calibration.ga_total)

    def _current_rate_to_field_rate(self, rate_mA_per_s: float) -> float:
        return (float(rate_mA_per_s) / 1000.0) * float(self.app.calibration.ga_total)

    def _field_rate_to_current_rate(self, rate_gauss_per_s: float) -> float:
        return abs(float(rate_gauss_per_s)) / float(self.app.calibration.ga_total) * 1000.0

    def _sync_field_setpoint_from_current(self) -> None:
        if self._syncing_setpoints:
            return
        self._syncing_setpoints = True
        try:
            self.set_field_gauss.set(self._current_to_field(self.set_current.get()))
            self.field_ramp_rate.set(self._current_rate_to_field_rate(self.ramp_rate.get()))
        finally:
            self._syncing_setpoints = False

    def _sync_current_setpoint_from_field(self) -> None:
        if self._syncing_setpoints:
            return
        self._syncing_setpoints = True
        try:
            self.set_current.set(self._field_to_current(self.set_field_gauss.get()))
            self.ramp_rate.set(self._field_rate_to_current_rate(self.field_ramp_rate.get()))
        finally:
            self._syncing_setpoints = False

    def _on_current_input_changed(self, *_args: object) -> None:
        if self._syncing_setpoints:
            return
        self._setpoint_input_mode = "current"
        self._sync_field_setpoint_from_current()

    def _on_current_rate_input_changed(self, *_args: object) -> None:
        if self._syncing_setpoints:
            return
        self._setpoint_input_mode = "current"
        self._sync_field_setpoint_from_current()

    def _on_field_input_changed(self, *_args: object) -> None:
        if self._syncing_setpoints:
            return
        self._setpoint_input_mode = "field"
        self._sync_current_setpoint_from_field()

    def _on_field_rate_input_changed(self, *_args: object) -> None:
        if self._syncing_setpoints:
            return
        self._setpoint_input_mode = "field"
        self._sync_current_setpoint_from_field()

    def _on_update_setpoint(self) -> None:
        if self._setpoint_input_mode == "field":
            self._on_set_field_from_gauss()
            return
        self._on_set_current()

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
            self._append_status("Output enabled.")
            self.app.ui_bus.post_log("Helmholtz output enabled.")
        except Exception as exc:
            post_error = getattr(self.app, "post_instrument_error", None)
            if callable(post_error):
                post_error("helmholtz", str(exc))
            else:
                self._append_status(str(exc), is_error=True)
            self.app.ui_bus.post_log(f"Enable error: {exc}")

    def _on_disable(self) -> None:
        try:
            self.app.helmholtz.disable_output()
            self._append_status("Output disabled.")
            self.app.ui_bus.post_log("Helmholtz output disabled.")
        except Exception as exc:
            post_error = getattr(self.app, "post_instrument_error", None)
            if callable(post_error):
                post_error("helmholtz", str(exc))
            else:
                self._append_status(str(exc), is_error=True)
            self.app.ui_bus.post_log(f"Disable error: {exc}")

    def _on_set_current(self) -> None:
        """Set Helmholtz using total-current/ramp-rate inputs."""
        self._setpoint_input_mode = "current"
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
            self._field_rate_mA_s = float(rate)
            field_g = float(self._current_to_field(total_current))
            self._syncing_setpoints = True
            self.set_field_gauss.set(field_g)
            self.field_ramp_rate.set(self._current_rate_to_field_rate(rate))
            self._syncing_setpoints = False
            self.app.ui_bus.post(
                W_HELMHOLTZ_SETPOINT,
                {
                    "field_g": field_g,
                    "rate_mA_s": float(rate),
                    "total_current_a": float(total_current),
                },
            )
            self._update_status_label()
            self._append_status(
                f"Set total {total_current:.4f} A, compliance {self.compliance_voltage.get():.2f} V, rate {rate:.1f} mA/s"
            )
            self.app.ui_bus.post_log(
                f"Helmholtz values set: total {total_current:.4f} A "
                f"({current_per_coil:.4f} A/coil), "
                f"{self.compliance_voltage.get():.2f} V, {rate:.1f} mA/s"
            )
        except HelmholtzSafetyError as exc:
            post_error = getattr(self.app, "post_instrument_error", None)
            if callable(post_error):
                post_error("helmholtz", str(exc))
            else:
                self._append_status(str(exc), is_error=True)
            self.app.ui_bus.post_log(f"Safety: {exc}")
        except Exception as exc:
            post_error = getattr(self.app, "post_instrument_error", None)
            if callable(post_error):
                post_error("helmholtz", str(exc))
            else:
                self._append_status(str(exc), is_error=True)
            self.app.ui_bus.post_log(f"Set values error: {exc}")

    def _on_set_field_from_gauss(self) -> None:
        """Set Helmholtz using field/ramp-field inputs."""
        self._setpoint_input_mode = "field"
        try:
            field_g = self.set_field_gauss.get()
            total_current = self._field_to_current(field_g)
            rate_mA_s_raw = self._field_rate_to_current_rate(self.field_ramp_rate.get())
            rate = min(rate_mA_s_raw, HELMHOLTZ_MAX_RAMP_RATE_mA_per_s)
            if rate <= 0:
                rate = DEFAULT_RAMP_RATE_mA_per_s
                self.ramp_rate.set(rate)
                self.field_ramp_rate.set(self._current_rate_to_field_rate(rate))
                self.app.ui_bus.post_log("Helmholtz field ramp rate must be > 0; reset to default.")
            if rate_mA_s_raw > HELMHOLTZ_MAX_RAMP_RATE_mA_per_s:
                self.ramp_rate.set(rate)
                self.field_ramp_rate.set(self._current_rate_to_field_rate(rate))
                self.app.ui_bus.post_log(
                    f"Helmholtz field ramp rate capped to {HELMHOLTZ_MAX_RAMP_RATE_mA_per_s:.1f} mA/s equivalent."
                )

            self.app.helmholtz.set_compliance(self.compliance_voltage.get())
            self.app.helmholtz.set_field(field_g, rate_mA_per_s=rate)
            self._field_rate_mA_s = float(rate)
            self._syncing_setpoints = True
            self.set_current.set(total_current)
            self.ramp_rate.set(rate)
            self.field_ramp_rate.set(self._current_rate_to_field_rate(rate))
            self._syncing_setpoints = False
            self.app.ui_bus.post(
                W_HELMHOLTZ_SETPOINT,
                {
                    "field_g": float(field_g),
                    "rate_mA_s": float(rate),
                    "total_current_a": float(total_current),
                },
            )
            self._update_status_label()
            self._append_status(
                f"Set field {field_g:.2f} G, total {total_current:.4f} A, "
                f"compliance {self.compliance_voltage.get():.2f} V, "
                f"field rate {self.field_ramp_rate.get():.3f} G/s"
            )
            self.app.ui_bus.post_log(
                f"Helmholtz field set: {field_g:.2f} G, "
                f"total {total_current:.4f} A, {rate:.1f} mA/s"
            )
        except HelmholtzSafetyError as exc:
            post_error = getattr(self.app, "post_instrument_error", None)
            if callable(post_error):
                post_error("helmholtz", str(exc))
            else:
                self._append_status(str(exc), is_error=True)
            self.app.ui_bus.post_log(f"Safety: {exc}")
        except Exception as exc:
            post_error = getattr(self.app, "post_instrument_error", None)
            if callable(post_error):
                post_error("helmholtz", str(exc))
            else:
                self._append_status(str(exc), is_error=True)
            self.app.ui_bus.post_log(f"Set field error: {exc}")

    def _on_set_field(self) -> None:
        """Backward-compatible alias: keep existing callers setting current path."""
        self._on_set_current()

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
        if self._detached_canvas is not None and self._detached_ax is not None:
            self._detached_line_a.set_data([], [])
            self._detached_line_b.set_data([], [])
            self._detached_ax.set_autoscalex_on(True)
            self._detached_ax.set_autoscaley_on(True)
            self._detached_canvas.draw()
        self.app.ui_bus.post_log(
            f"[{time.strftime('%H:%M:%S')}] Helmholtz plot reset — showing only new data."
        )
