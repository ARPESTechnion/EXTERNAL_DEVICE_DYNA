"""
v3.gui.dyna_tab  —  Dynacool / PPMS control and monitoring tab.

Displays live temperature and field from the PPMS background poller.
Provides setpoint entries for temperature and field with approach mode.
Includes Reset Plot and Auto-Logging controls.
"""

from __future__ import annotations

import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, ttk
from typing import TYPE_CHECKING, Any

from v3.core.constants import (
    DEFAULT_DYNA_FIELD_RATE,
    DEFAULT_DYNA_TEMP_RATE,
    FIELD_MAX_OE,
    INST_DYNA,
    TEMP_MAX_K,
    TEMP_MIN_K,
)
from v3.core.ui_events import (
    W_DYNA_CONNECTED,
    W_DYNA_FIELD,
    W_DYNA_FIELD_STATUS,
    W_DYNA_LOG_MESSAGE,
    W_DYNA_SETPOINT,
    W_DYNA_TEMP,
    W_DYNA_TEMP_STATUS,
)
from v3.gui.base_tab import BaseTab, ConnectionHeader

if TYPE_CHECKING:
    from v3.gui.app import MeasureApp

try:
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    from matplotlib.figure import Figure
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False


class DynaTab(BaseTab):
    """Dynacool (PPMS) control and status tab."""

    def __init__(self, parent: ttk.Frame, app: "MeasureApp") -> None:
        super().__init__(parent, app)
        self._conn_header: ConnectionHeader | None = None
        self._temp_value: float | None = None
        self._field_value: float | None = None
        self._temp_status: str = "N/A"
        self._field_status: str = "N/A"

    def create_widgets(self) -> None:
        self._conn_header = ConnectionHeader(
            self.parent,
            instrument_key="dyna",
            display_name="Dynacool (PPMS)",
            on_connect=lambda: self.app.connect_instrument("dyna"),
            on_disconnect=lambda: self.app.disconnect_instrument("dyna"),
        )

        body = ttk.Frame(self.parent)
        body.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        self.parent.grid_rowconfigure(1, weight=1)
        self.parent.grid_columnconfigure(0, weight=1)

        left = ttk.Frame(body, padding=10)
        left.grid(row=0, column=0, sticky="ns")

        right = ttk.Frame(body, width=720, height=630)
        right.grid(row=0, column=1, sticky="nw", padx=(10, 0))
        right.grid_propagate(False)

        self._build_controls(left)
        self._build_plot(right)

    # ------------------------------------------------------------------
    # Controls
    # ------------------------------------------------------------------
    def _build_controls(self, parent: ttk.Frame) -> None:
        # --- Live readouts ---
        rd = ttk.LabelFrame(parent, text="Live Status")
        rd.pack(fill="x", padx=5, pady=5)

        self.temp_display = tk.Label(
            rd, text="Temp: N/A",
            font=("Courier", 14), fg="#FF6200", bg="#000000",
        )
        self.temp_display.pack(anchor="w", padx=5, pady=2)

        self.field_display = tk.Label(
            rd, text="Field: N/A",
            font=("Courier", 14), fg="#00A000", bg="#000000",
        )
        self.field_display.pack(anchor="w", padx=5, pady=2)

        # --- Temperature setpoint ---
        tf = ttk.LabelFrame(parent, text="Temperature")
        tf.pack(fill="x", padx=5, pady=5)

        self.set_temp = tk.DoubleVar(value=300.0)
        self.temp_rate = tk.DoubleVar(value=DEFAULT_DYNA_TEMP_RATE)
        self.temp_mode = tk.StringVar(value="fast_settle")

        row = 0
        for label, var in [
            ("Set Temp (K):", self.set_temp),
            ("Rate (K/min):", self.temp_rate),
        ]:
            ttk.Label(tf, text=label).grid(row=row, column=0, sticky="w", padx=5, pady=2)
            ttk.Entry(tf, textvariable=var, width=10).grid(row=row, column=1, padx=5, pady=2)
            row += 1

        ttk.Label(tf, text="Approach:").grid(row=row, column=0, sticky="w", padx=5, pady=2)
        ttk.Combobox(
            tf,
            textvariable=self.temp_mode,
            values=["fast_settle", "no_overshoot"],
            state="readonly",
            width=14,
        ).grid(row=row, column=1, padx=5, pady=2, sticky="w")
        row += 1

        ttk.Button(tf, text="Set Temperature", command=self._on_set_temp).grid(
            row=row, column=0, columnspan=2, pady=5
        )

        # --- Field setpoint ---
        ff = ttk.LabelFrame(parent, text="Field")
        ff.pack(fill="x", padx=5, pady=5)

        self.set_field = tk.DoubleVar(value=0.0)
        self.field_rate = tk.DoubleVar(value=DEFAULT_DYNA_FIELD_RATE)
        self.field_mode = tk.StringVar(value="linear")

        row = 0
        for label, var in [
            ("Set Field (Oe):", self.set_field),
            ("Rate (Oe/s):", self.field_rate),
        ]:
            ttk.Label(ff, text=label).grid(row=row, column=0, sticky="w", padx=5, pady=2)
            ttk.Entry(ff, textvariable=var, width=10).grid(row=row, column=1, padx=5, pady=2)
            row += 1

        ttk.Label(ff, text="Approach:").grid(row=row, column=0, sticky="w", padx=5, pady=2)
        ttk.Combobox(
            ff,
            textvariable=self.field_mode,
            values=["linear", "no_overshoot", "oscillate"],
            state="readonly",
            width=14,
        ).grid(row=row, column=1, padx=5, pady=2, sticky="w")
        row += 1

        ttk.Button(ff, text="Set Field", command=self._on_set_field).grid(
            row=row, column=0, columnspan=2, pady=5
        )

        # --- Plot interval + Reset Plot ---
        pi = ttk.Frame(parent)
        pi.pack(fill="x", padx=5, pady=2)
        ttk.Label(pi, text="Plot interval (s):").pack(side="left")
        self.dyna_plot_interval = tk.DoubleVar(value=10.0)
        ttk.Entry(pi, textvariable=self.dyna_plot_interval, width=6).pack(side="left", padx=5)
        ttk.Button(pi, text="Reset Plot", command=self._on_reset_plot).pack(side="left", padx=5)

        # --- Auto-Logging section ---
        al = ttk.LabelFrame(parent, text="Auto-Logging")
        al.pack(fill="x", padx=5, pady=5)

        auto_row = ttk.Frame(al)
        auto_row.pack(fill="x", padx=5, pady=2)
        ttk.Checkbutton(
            auto_row, text="Enable Auto-Log",
            variable=self.app.auto_log_enabled,
            command=self._on_toggle_auto_log,
        ).pack(side="left")

        active_row = ttk.Frame(al)
        active_row.pack(fill="x", padx=5, pady=2)
        ttk.Label(active_row, text="Active Log:").pack(side="left")
        self.active_log_label = ttk.Label(
            active_row,
            text="None",
            font=("Courier", 8),
            relief="sunken",
            width=30,
        )
        self.active_log_label.pack(side="left", padx=5)

        dir_row = ttk.Frame(al)
        dir_row.pack(fill="x", padx=5, pady=2)
        ttk.Label(dir_row, text="Log Dir:").pack(side="left")
        self.log_dir_label = ttk.Label(
            dir_row, text=str(self.app.data_mgr.log_dir),
            font=("Courier", 8), relief="sunken", width=30,
        )
        self.log_dir_label.pack(side="left", padx=5)
        ttk.Button(dir_row, text="Change", command=self._change_log_directory).pack(side="left")

        # --- Log area ---
        log_frame = ttk.LabelFrame(parent, text="Dyna Log")
        log_frame.pack(fill="both", expand=True, padx=5, pady=5)
        self.log_text = tk.Text(log_frame, height=6, width=50, state="disabled",
                                font=("Courier", 9))
        log_sb = ttk.Scrollbar(log_frame, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=log_sb.set)
        self.log_text.pack(side="left", fill="both", expand=True)
        log_sb.pack(side="right", fill="y")

        self.refresh_auto_log_status()

    # ------------------------------------------------------------------
    # Plot
    # ------------------------------------------------------------------
    def _build_plot(self, parent: ttk.Frame) -> None:
        if not HAS_MATPLOTLIB:
            ttk.Label(parent, text="(matplotlib not available)").pack()
            self.canvas = None
            return

        self.fig = Figure(figsize=(6.9, 6.0), dpi=100)
        self.ax_temp = self.fig.add_subplot(211)
        self.ax_field = self.fig.add_subplot(212)
        self.ax_temp.tick_params(axis="both", which="both", direction="in")
        self.ax_field.tick_params(axis="both", which="both", direction="in")
        self.ax_temp.set_ylabel("Temp (K)")
        self.ax_field.set_ylabel("Field (Oe)")
        self.ax_field.set_xlabel("Time (s)")
        self.ax_temp.margins(x=0.02)
        self.ax_field.margins(x=0.02)
        self.line_temp, = self.ax_temp.plot(
            [], [], color="tab:red", marker="o", linestyle="-", markersize=4
        )
        self.line_field, = self.ax_field.plot(
            [], [], color="tab:green", marker="o", linestyle="-", markersize=4
        )
        self.fig.tight_layout(pad=0.8, h_pad=0.35)

        self.canvas = FigureCanvasTkAgg(self.fig, master=parent)
        self.canvas.get_tk_widget().pack(fill="both", expand=False)

    def update_plot(self) -> None:
        if self.canvas is None:
            return
        t = self.app.dyna_time_data
        if t:
            self.line_temp.set_data(t, self.app.dyna_temp_data)
            self.line_field.set_data(t, self.app.dyna_field_data)
            for ax in (self.ax_temp, self.ax_field):
                ax.relim()
                ax.autoscale_view()
            self.canvas.draw_idle()

    # ------------------------------------------------------------------
    # Event handling
    # ------------------------------------------------------------------
    def on_event(self, widget_id: str, value: Any) -> None:
        if widget_id == W_DYNA_TEMP:
            self._temp_value = float(value) if value is not None else None
            self._render_temp_display()
        elif widget_id == W_DYNA_FIELD:
            self._field_value = float(value) if value is not None else None
            self._render_field_display()
        elif widget_id == W_DYNA_TEMP_STATUS:
            self._temp_status = self._normalize_status(value)
            self._render_temp_display()
        elif widget_id == W_DYNA_FIELD_STATUS:
            self._field_status = self._normalize_status(value)
            self._render_field_display()
        elif widget_id == W_DYNA_LOG_MESSAGE:
            self._append_log(str(value))
        elif widget_id == W_DYNA_CONNECTED:
            if self._conn_header:
                self._conn_header.set_connected(bool(value))
        elif widget_id == W_DYNA_SETPOINT and isinstance(value, dict):
            try:
                if "temp_k" in value:
                    self.set_temp.set(float(value["temp_k"]))
                if "temp_rate_k_min" in value:
                    self.temp_rate.set(float(value["temp_rate_k_min"]))
                if "temp_mode" in value:
                    self.temp_mode.set(str(value["temp_mode"]))

                if "field_oe" in value:
                    self.set_field.set(float(value["field_oe"]))
                if "field_rate_oe_s" in value:
                    self.field_rate.set(float(value["field_rate_oe_s"]))
                if "field_mode" in value:
                    self.field_mode.set(str(value["field_mode"]))
            except Exception:
                pass

    def on_instrument_connected(self, name: str) -> None:
        if name == "dyna" and self._conn_header:
            self._conn_header.set_connected(True)

    def on_instrument_disconnected(self, name: str) -> None:
        if name == "dyna" and self._conn_header:
            self._conn_header.set_connected(False)
            self._temp_value = None
            self._field_value = None
            self._temp_status = "N/A"
            self._field_status = "N/A"
            self._render_temp_display()
            self._render_field_display()

    def _normalize_status(self, value: Any) -> str:
        if value is None:
            return "N/A"
        text = str(value).strip()
        return text if text else "N/A"

    def _render_temp_display(self) -> None:
        temp_text = f"{self._temp_value:.2f} K" if self._temp_value is not None else "N/A"
        status_suffix = f" ({self._temp_status})" if self._temp_status != "N/A" else ""
        self.temp_display.configure(text=f"Temp: {temp_text}{status_suffix}")

    def _render_field_display(self) -> None:
        field_text = f"{self._field_value:.1f} Oe" if self._field_value is not None else "N/A"
        status_suffix = f" ({self._field_status})" if self._field_status != "N/A" else ""
        self.field_display.configure(text=f"Field: {field_text}{status_suffix}")

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------
    def _append_log(self, msg: str) -> None:
        self.log_text.configure(state="normal")
        self.log_text.insert("end", msg + "\n")
        self.log_text.see("end")
        # Trim
        line_count = int(self.log_text.index("end-1c").split(".")[0])
        if line_count > 500:
            self.log_text.delete("1.0", f"{line_count - 500}.0")
        self.log_text.configure(state="disabled")

    # ------------------------------------------------------------------
    # Button handlers
    # ------------------------------------------------------------------
    def _on_set_temp(self) -> None:
        try:
            temp = self.set_temp.get()
            rate = self.temp_rate.get()
            mode = self.temp_mode.get()
            mode_map = {"fast_settle": 0, "no_overshoot": 1}
            mode_val = mode_map.get(mode, 1)
            if not (TEMP_MIN_K <= temp <= TEMP_MAX_K):
                self.app.ui_bus.post_log(
                    f"Temperature {temp} K out of range [{TEMP_MIN_K}, {TEMP_MAX_K}]"
                )
                return
            self.app.bus.execute(INST_DYNA, "set_temperature", temp, rate, mode_val)
            self.app.ui_bus.post_log(f"PPMS temp → {temp:.1f} K at {rate} K/min ({mode})")
        except Exception as exc:
            self.app.ui_bus.post_log(f"Set temp error: {exc}")

    def _on_set_field(self) -> None:
        try:
            field_oe = self.set_field.get()
            rate = self.field_rate.get()
            mode = self.field_mode.get()
            mode_map = {"linear": 0, "no_overshoot": 1, "oscillate": 2}
            mode_val = mode_map.get(mode, 1)

            if rate > 50:
                rate = 50
                self.field_rate.set(50)
                self.app.ui_bus.post_log("PPMS field rate capped to 50 Oe/s (maximum allowed)")

            if abs(field_oe) > FIELD_MAX_OE:
                self.app.ui_bus.post_log(
                    f"Field {field_oe} Oe exceeds ±{FIELD_MAX_OE} Oe"
                )
                return
            self.app.bus.execute(INST_DYNA, "set_field", field_oe, rate, mode_val)
            self.app.ui_bus.post_log(f"PPMS field → {field_oe:.1f} Oe at {rate} Oe/s ({mode})")
        except Exception as exc:
            self.app.ui_bus.post_log(f"Set field error: {exc}")

    def _on_reset_plot(self) -> None:
        """Reset the Dyna plots — clears data and shows only future data."""
        import time
        self.app.dyna_time_data.clear()
        self.app.dyna_temp_data.clear()
        self.app.dyna_field_data.clear()
        self.app.start_time_dyna = time.time()
        self.app.last_plot_time_dyna = time.time()
        self.update_plot()
        if hasattr(self, "canvas") and self.canvas is not None:
            self.canvas.draw()
        self.app.ui_bus.post_log(
            f"[{time.strftime('%H:%M:%S')}] Dyna plot reset — showing only new data."
        )
        self._append_log(
            f"[{time.strftime('%H:%M:%S')}] Dyna plot reset — showing only new data."
        )

    def _change_log_directory(self) -> None:
        """Change the auto-log directory."""
        new_dir = filedialog.askdirectory(
            title="Select Log Directory",
            initialdir=str(self.app.data_mgr.log_dir),
        )
        if new_dir:
            self.app.set_auto_log_directory(Path(new_dir))
            self.refresh_auto_log_status()

    def _on_toggle_auto_log(self) -> None:
        enabled = bool(self.app.auto_log_enabled.get())
        self.app.set_auto_logging_enabled(enabled)
        state_text = "enabled" if enabled else "disabled"
        self._append_log(f"[{time.strftime('%H:%M:%S')}] Auto-log {state_text}.")
        self.refresh_auto_log_status()

    def refresh_auto_log_status(self) -> None:
        self.log_dir_label.configure(text=str(self.app.data_mgr.log_dir))
        active_path = self.app.data_mgr.auto_log_filename
        if self.app.data_mgr.is_auto_log_open and active_path is not None:
            self.active_log_label.configure(text=active_path.name)
        else:
            self.active_log_label.configure(text="None")
