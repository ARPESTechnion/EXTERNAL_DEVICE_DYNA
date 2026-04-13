"""
v3.gui.dyna_tab  -  Dynacool / PPMS control and monitoring tab.

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
    DYNA_TEMP_RATE_MAX_K_MIN,
    DYNA_TEMP_RATE_MIN_K_MIN,
    FIELD_MAX_OE,
    INST_DYNA,
    TEMP_MAX_K,
    TEMP_MIN_K,
)
from v3.core.ui_events import (
    W_DYNA_CHAMBER,
    W_DYNA_CHAMBER_STATUS,
    W_DYNA_CONNECTED,
    W_DYNA_FIELD,
    W_DYNA_FIELD_STATUS,
    W_DYNA_LOG_MESSAGE,
    W_DYNA_SETPOINT,
    W_DYNA_TEMP,
    W_DYNA_TEMP_STATUS,
)
from v3.gui.base_tab import BaseTab, ConnectionHeader
from v3.gui.components import ControlGroup, ValidatingEntry, make_float_validator
from v3.gui.theme import COLORS, FONTS

if TYPE_CHECKING:
    from v3.gui.app import MeasureApp

try:
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
    from matplotlib.figure import Figure
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False


class DynaTab(BaseTab):
    """Dynacool (PPMS) control and status tab."""

    _CHAMBER_MODE_TO_CODE: dict[str, int] = {
        "Seal": 0,
        "Purge and Seal": 1,
        "Vent and Seal": 2,
        "Pump Continuous": 3,
        "Vent Continuous": 4,
        "High Vacuum": 5,
    }

    def __init__(self, parent: ttk.Frame, app: "MeasureApp") -> None:
        super().__init__(parent, app)
        self._conn_header: ConnectionHeader | None = None
        self._temp_value: float | None = None
        self._field_value: float | None = None
        self._chamber_value: int | None = None
        self._temp_status: str = "N/A"
        self._field_status: str = "N/A"
        self._chamber_status: str = "N/A"
        self._temp_rate_k_min: float | None = None
        self._field_rate_oe_s: float | None = None
        self._detached_plot_window: tk.Toplevel | None = None
        self._detached_fig = None
        self._detached_canvas = None
        self._detached_ax_temp = None
        self._detached_ax_field = None
        self._detached_line_temp = None
        self._detached_line_field = None
        self._grid_enabled: bool = True
        self._grid_buttons: list[ttk.Button] = []
        self._xlink_guard: bool = False

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

        right = ttk.Frame(body, width=700, height=560)
        right.grid(row=0, column=1, sticky="nw", padx=(10, 0))
        right.grid_propagate(False)

        self._build_controls(left)
        self._build_plot(right)

    # ------------------------------------------------------------------
    # Controls
    # ------------------------------------------------------------------
    def _build_controls(self, parent: ttk.Frame) -> None:
        # --- Live readouts ---
        rd_group = ControlGroup(parent, "Live Status")
        rd = rd_group.body

        self.temp_display = tk.Label(
            rd,
            text="Temp: N/A",
            font=FONTS["mono"],
            fg=COLORS["accent_temp"],
            bg=COLORS["bg_input"],
            relief="solid",
            borderwidth=1,
            padx=6,
            pady=2,
            anchor="w",
        )
        self.temp_display.pack(fill="x", anchor="w", padx=5, pady=(5, 2))

        self.field_display = tk.Label(
            rd,
            text="Field: N/A",
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

        self.chamber_display = tk.Label(
            rd,
            text="Chamber: N/A",
            font=FONTS["mono"],
            fg=COLORS["accent_info"],
            bg=COLORS["bg_input"],
            relief="solid",
            borderwidth=1,
            padx=6,
            pady=2,
            anchor="w",
        )
        self.chamber_display.pack(fill="x", anchor="w", padx=5, pady=(2, 5))

        # --- Temperature setpoint ---
        tf_group = ControlGroup(parent, "Temperature")
        tf = tf_group.body

        self.set_temp = tk.DoubleVar(value=300.0)
        self.temp_rate = tk.DoubleVar(value=DEFAULT_DYNA_TEMP_RATE)
        self.temp_mode = tk.StringVar(value="fast_settle")

        row = 0
        for label, var in [
            ("Set Temp (K):", self.set_temp),
            ("Rate (K/min):", self.temp_rate),
        ]:
            ttk.Label(tf, text=label).grid(row=row, column=0, sticky="w", padx=5, pady=2)
            validator = (
                make_float_validator(TEMP_MIN_K, TEMP_MAX_K)
                if label.startswith("Set Temp")
                else make_float_validator(DYNA_TEMP_RATE_MIN_K_MIN, DYNA_TEMP_RATE_MAX_K_MIN)
            )
            ValidatingEntry(tf, textvariable=var, width=10, validator=validator).grid(row=row, column=1, padx=5, pady=2)
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

        ttk.Button(tf, text="Set Temperature", style="Primary.TButton", command=self._on_set_temp).grid(
            row=row, column=0, columnspan=2, pady=5
        )

        # --- Field setpoint ---
        ff_group = ControlGroup(parent, "Field")
        ff = ff_group.body

        self.set_field = tk.DoubleVar(value=0.0)
        self.field_rate = tk.DoubleVar(value=DEFAULT_DYNA_FIELD_RATE)
        self.field_mode = tk.StringVar(value="linear")

        row = 0
        for label, var in [
            ("Set Field (Oe):", self.set_field),
            ("Rate (Oe/s):", self.field_rate),
        ]:
            ttk.Label(ff, text=label).grid(row=row, column=0, sticky="w", padx=5, pady=2)
            validator = (
                make_float_validator(-FIELD_MAX_OE, FIELD_MAX_OE)
                if label.startswith("Set Field")
                else make_float_validator(0.0, DEFAULT_DYNA_FIELD_RATE)
            )
            ValidatingEntry(ff, textvariable=var, width=10, validator=validator).grid(row=row, column=1, padx=5, pady=2)
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

        ttk.Button(ff, text="Set Field", style="Primary.TButton", command=self._on_set_field).grid(
            row=row, column=0, columnspan=2, pady=5
        )

        # --- Chamber control ---
        cf_group = ControlGroup(parent, "Chamber")
        cf = cf_group.body

        self.chamber_mode = tk.StringVar(value="Seal")
        row = 0
        ttk.Label(cf, text="Mode:").grid(row=row, column=0, sticky="w", padx=5, pady=2)
        ttk.Combobox(
            cf,
            textvariable=self.chamber_mode,
            values=list(self._CHAMBER_MODE_TO_CODE.keys()),
            state="readonly",
            width=18,
        ).grid(row=row, column=1, padx=5, pady=2, sticky="w")
        row += 1

        ttk.Button(cf, text="Set Chamber", style="Primary.TButton", command=self._on_set_chamber).grid(
            row=row, column=0, columnspan=2, pady=5
        )

        self.dyna_plot_interval = tk.DoubleVar(value=10.0)

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
            font=FONTS["mono_small"],
            relief="sunken",
            width=30,
        )
        self.active_log_label.pack(side="left", padx=5)

        dir_row = ttk.Frame(al)
        dir_row.pack(fill="x", padx=5, pady=2)
        ttk.Label(dir_row, text="Log Dir:").pack(side="left")
        self.log_dir_label = ttk.Label(
            dir_row, text=str(self.app.data_mgr.log_dir),
            font=FONTS["mono_small"], relief="sunken", width=30,
        )
        self.log_dir_label.pack(side="left", padx=5)
        ttk.Button(dir_row, text="Change", style="Secondary.TButton", command=self._change_log_directory).pack(side="left")

        # --- Log area ---
        log_frame = ttk.LabelFrame(parent, text="Dyna Log")
        log_frame.pack(fill="both", expand=True, padx=5, pady=5)
        self.log_text = tk.Text(log_frame, height=6, width=50, state="disabled",
                                font=FONTS["mono_small"], bg=COLORS["bg_input"], fg=COLORS["fg_primary"],
                                insertbackground=COLORS["fg_primary"])
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

        (
            self.fig,
            self.ax_temp,
            self.ax_field,
            self.line_temp,
            self.line_field,
            self.canvas,
        ) = self._create_plot_components(parent)
        self.canvas.get_tk_widget().pack(fill="both", expand=False)
        toolbar = NavigationToolbar2Tk(self.canvas, parent, pack_toolbar=False)
        toolbar.pack(side="top", fill="x")
        toolbar.update()
        self._add_toolbar_buttons(
            toolbar,
            lambda: self._autoscale_axes(self.ax_temp, self.ax_field, self.canvas),
        )
        self._install_x_link_callbacks(self.ax_temp, self.ax_field, self.canvas)

        controls = ttk.Frame(parent)
        controls.pack(fill="x", padx=5, pady=(6, 0))
        ttk.Label(controls, text="Plot interval (s):").pack(side="left")
        ValidatingEntry(
            controls,
            textvariable=self.dyna_plot_interval,
            width=6,
            validator=make_float_validator(0.1, 120.0),
        ).pack(side="left", padx=5)
        ttk.Button(
            controls,
            text="Reset Plot",
            style="Secondary.TButton",
            command=self._on_reset_plot,
        ).pack(side="left", padx=5)
        ttk.Button(
            controls,
            text="Open Graph Window",
            style="Secondary.TButton",
            command=self._open_detached_plot_window,
        ).pack(side="left", padx=5)

    def _create_plot_components(self, parent: tk.Widget):
        fig = Figure(figsize=(6.9, 6.0), dpi=100, constrained_layout=True)
        ax_temp = fig.add_subplot(211)
        ax_field = fig.add_subplot(212, sharex=ax_temp)
        ax_temp.tick_params(axis="both", which="both", direction="in")
        ax_field.tick_params(axis="both", which="both", direction="in")
        ax_temp.set_ylabel("Temp (K)")
        ax_field.set_ylabel("Field (Oe)")
        ax_field.set_xlabel("Time (s)")
        ax_temp.margins(x=0.02)
        ax_field.margins(x=0.02)
        self._apply_grid_to_axes(ax_temp, ax_field)
        line_temp, = ax_temp.plot([], [], color="tab:red", marker="o", linestyle="-", markersize=4)
        line_field, = ax_field.plot([], [], color="tab:green", marker="o", linestyle="-", markersize=4)
        canvas = FigureCanvasTkAgg(fig, master=parent)
        return fig, ax_temp, ax_field, line_temp, line_field, canvas

    def _open_detached_plot_window(self) -> None:
        if not HAS_MATPLOTLIB or self.canvas is None:
            return
        if self._detached_plot_window is not None and self._detached_plot_window.winfo_exists():
            self._detached_plot_window.lift()
            self._detached_plot_window.focus_force()
            return

        win = tk.Toplevel(self.app.root)
        win.title("Dyna Plot")
        win.geometry("760x670")
        win.attributes("-topmost", True)
        frame = ttk.Frame(win, padding=6)
        frame.pack(fill="both", expand=True)
        (
            self._detached_fig,
            self._detached_ax_temp,
            self._detached_ax_field,
            self._detached_line_temp,
            self._detached_line_field,
            self._detached_canvas,
        ) = self._create_plot_components(frame)
        self._detached_canvas.get_tk_widget().pack(fill="both", expand=True)
        detached_toolbar = NavigationToolbar2Tk(self._detached_canvas, frame)
        detached_toolbar.update()
        self._add_toolbar_buttons(
            detached_toolbar,
            lambda: self._autoscale_axes(
                self._detached_ax_temp,
                self._detached_ax_field,
                self._detached_canvas,
            ),
        )
        self._detached_plot_window = win
        self._install_x_link_callbacks(self._detached_ax_temp, self._detached_ax_field, self._detached_canvas)
        win.bind("<Configure>", self._on_detached_window_resize)
        win.protocol("WM_DELETE_WINDOW", self._close_detached_plot_window)
        self.update_plot()

    def _on_detached_window_resize(self, _event: tk.Event) -> None:
        if self._detached_canvas is None or self._detached_fig is None:
            return
        self._detached_fig.tight_layout(pad=0.5, h_pad=0.25)
        self._detached_canvas.draw_idle()

    def _close_detached_plot_window(self) -> None:
        if self._detached_plot_window is not None and self._detached_plot_window.winfo_exists():
            self._detached_plot_window.destroy()
        self._detached_plot_window = None
        self._detached_fig = None
        self._detached_canvas = None
        self._detached_ax_temp = None
        self._detached_ax_field = None
        self._detached_line_temp = None
        self._detached_line_field = None

    def update_plot(self) -> None:
        if self.canvas is None:
            return
        t = self.app.dyna_time_data
        if t:
            self._update_plot_components(
                t,
                self.app.dyna_temp_data,
                self.app.dyna_field_data,
                self.ax_temp,
                self.ax_field,
                self.line_temp,
                self.line_field,
                self.canvas,
            )
            if self._detached_canvas is not None and self._detached_plot_window is not None:
                self._update_plot_components(
                    t,
                    self.app.dyna_temp_data,
                    self.app.dyna_field_data,
                    self._detached_ax_temp,
                    self._detached_ax_field,
                    self._detached_line_temp,
                    self._detached_line_field,
                    self._detached_canvas,
                )

    @staticmethod
    def _update_plot_components(
        t_data,
        temp_data,
        field_data,
        ax_temp,
        ax_field,
        line_temp,
        line_field,
        canvas,
    ) -> None:
        line_temp.set_data(t_data, temp_data)
        line_field.set_data(t_data, field_data)
        for ax in (ax_temp, ax_field):
            ax.relim()
            ax.autoscale_view()
        canvas.draw_idle()

    def _add_toolbar_buttons(self, toolbar: tk.Widget, autoscale_cmd) -> None:
        ttk.Button(toolbar, text="Autoscale", command=autoscale_cmd, width=10).pack(side="left", padx=(6, 0))
        grid_btn = ttk.Button(toolbar, text="Grid On", command=self._toggle_grid, width=10)
        grid_btn.pack(side="left", padx=(4, 0))
        self._grid_buttons.append(grid_btn)
        self._refresh_grid_button_labels()

    def _install_x_link_callbacks(self, upper_ax, lower_ax, canvas) -> None:
        if upper_ax is None or lower_ax is None or canvas is None:
            return
        upper_ax.callbacks.connect("xlim_changed", lambda _ax: self._sync_x_limits(upper_ax, lower_ax, canvas))
        lower_ax.callbacks.connect("xlim_changed", lambda _ax: self._sync_x_limits(lower_ax, upper_ax, canvas))

    def _sync_x_limits(self, source_ax, target_ax, canvas) -> None:
        if source_ax is None or target_ax is None or canvas is None or self._xlink_guard:
            return
        try:
            self._xlink_guard = True
            target_ax.set_xlim(source_ax.get_xlim())
            canvas.draw_idle()
        finally:
            self._xlink_guard = False

    def _apply_grid_to_axes(self, *axes) -> None:
        for ax in axes:
            if ax is None:
                continue
            ax.grid(self._grid_enabled, which="both", linestyle="--", linewidth=0.6, alpha=0.35)

    def _refresh_grid_button_labels(self) -> None:
        text = "Grid On" if self._grid_enabled else "Grid Off"
        active_buttons: list[ttk.Button] = []
        for btn in self._grid_buttons:
            if btn.winfo_exists():
                btn.configure(text=text)
                active_buttons.append(btn)
        self._grid_buttons = active_buttons

    def _toggle_grid(self) -> None:
        self._grid_enabled = not self._grid_enabled
        self._apply_grid_to_axes(self.ax_temp, self.ax_field, self._detached_ax_temp, self._detached_ax_field)
        if self.canvas is not None:
            self.canvas.draw_idle()
        if self._detached_canvas is not None:
            self._detached_canvas.draw_idle()
        self._refresh_grid_button_labels()

    @staticmethod
    def _autoscale_axes(ax_temp, ax_field, canvas) -> None:
        if canvas is None or ax_temp is None or ax_field is None:
            return
        for ax in (ax_temp, ax_field):
            ax.set_autoscalex_on(True)
            ax.set_autoscaley_on(True)
            ax.relim()
            ax.autoscale_view()
        canvas.draw_idle()

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
        elif widget_id == W_DYNA_CHAMBER:
            try:
                self._chamber_value = int(value) if value is not None else None
            except Exception:
                self._chamber_value = None
            self._render_chamber_display()
        elif widget_id == W_DYNA_TEMP_STATUS:
            self._temp_status = self._normalize_status(value)
            self._render_temp_display()
        elif widget_id == W_DYNA_FIELD_STATUS:
            self._field_status = self._normalize_status(value)
            self._render_field_display()
        elif widget_id == W_DYNA_CHAMBER_STATUS:
            self._chamber_status = self._normalize_status(value)
            self._render_chamber_display()
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
                    self._temp_rate_k_min = float(value["temp_rate_k_min"])
                if "temp_mode" in value:
                    self.temp_mode.set(str(value["temp_mode"]))

                if "field_oe" in value:
                    self.set_field.set(float(value["field_oe"]))
                if "field_rate_oe_s" in value:
                    self.field_rate.set(float(value["field_rate_oe_s"]))
                    self._field_rate_oe_s = float(value["field_rate_oe_s"])
                if "field_mode" in value:
                    self.field_mode.set(str(value["field_mode"]))
                if "chamber_mode" in value:
                    token = str(value["chamber_mode"]).strip()
                    if token in self._CHAMBER_MODE_TO_CODE:
                        self.chamber_mode.set(token)
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
            self._chamber_value = None
            self._temp_status = "N/A"
            self._field_status = "N/A"
            self._chamber_status = "N/A"
            self._temp_rate_k_min = None
            self._field_rate_oe_s = None
            self._render_temp_display()
            self._render_field_display()
            self._render_chamber_display()

    def _normalize_status(self, value: Any) -> str:
        if value is None:
            return "N/A"
        text = str(value).strip()
        return text if text else "N/A"

    @staticmethod
    def _fmt_4sig(value: float) -> str:
        """Format *value* to 4 significant figures using fixed-point notation."""
        import math
        if value == 0:
            return "0"
        magnitude = math.floor(math.log10(abs(value)))
        decimal_places = max(0, 3 - magnitude)
        return f"{value:.{decimal_places}f}"

    def _render_temp_display(self) -> None:
        temp_text = f"{self._temp_value:.2f} K" if self._temp_value is not None else "N/A"
        status_suffix = f" ({self._temp_status})" if self._temp_status != "N/A" else ""
        rate_suffix = (
            f" {self._fmt_4sig(self._temp_rate_k_min)} K/min"
            if self._temp_rate_k_min is not None
            else ""
        )
        self.temp_display.configure(text=f"Temp: {temp_text}{status_suffix}{rate_suffix}")

    def _render_field_display(self) -> None:
        field_text = f"{self._field_value:.2f} Oe" if self._field_value is not None else "N/A"
        status_suffix = f" ({self._field_status})" if self._field_status != "N/A" else ""
        rate_suffix = (
            f" {self._field_rate_oe_s:.2f} Oe/s"
            if self._field_rate_oe_s is not None
            else ""
        )
        self.field_display.configure(text=f"Field: {field_text}{status_suffix}{rate_suffix}")

    def _render_chamber_display(self) -> None:
        status_text = self._chamber_status if self._chamber_status != "N/A" else "N/A"
        self.chamber_display.configure(text=f"Chamber: {status_text}")

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

    def _report_dyna_error(self, message: str) -> None:
        self._append_log(f"Error: {message}")
        post_error = getattr(self.app, "post_instrument_error", None)
        if callable(post_error):
            post_error("dyna", message)

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
                self._append_log(
                    f"Error: Temperature {temp} K out of range [{TEMP_MIN_K}, {TEMP_MAX_K}]"
                )
                self.app.ui_bus.post_log(
                    f"Temperature {temp} K out of range [{TEMP_MIN_K}, {TEMP_MAX_K}]"
                )
                return

            if not (DYNA_TEMP_RATE_MIN_K_MIN <= rate <= DYNA_TEMP_RATE_MAX_K_MIN):
                self._append_log(
                    f"Error: Temperature rate {rate} K/min out of range [{DYNA_TEMP_RATE_MIN_K_MIN}, {DYNA_TEMP_RATE_MAX_K_MIN}]"
                )
                self.app.ui_bus.post_log(
                    f"Temperature rate {rate} K/min out of range [{DYNA_TEMP_RATE_MIN_K_MIN}, {DYNA_TEMP_RATE_MAX_K_MIN}]"
                )
                return

            confirm = getattr(self.app, "confirm_dyna_low_temp_transition", None)
            if callable(confirm) and not bool(confirm(temp, source="manual")):
                self.app.ui_bus.post_log(
                    "Set temp aborted: Dyna purge/seal safety confirmation declined."
                )
                return

            self.app.bus.execute(INST_DYNA, "set_temperature", temp, rate, mode_val)
            self._temp_rate_k_min = float(rate)
            self._render_temp_display()
            self.app.ui_bus.post(
                W_DYNA_SETPOINT,
                {
                    "temp_k": float(temp),
                    "temp_rate_k_min": float(rate),
                    "temp_mode": str(mode),
                },
            )
            self.app.ui_bus.post_log(f"PPMS temp → {temp:.1f} K at {rate} K/min ({mode})")
        except Exception as exc:
            self._report_dyna_error(str(exc))
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
                self._append_log(f"Error: Field {field_oe} Oe exceeds ±{FIELD_MAX_OE} Oe")
                self.app.ui_bus.post_log(
                    f"Field {field_oe} Oe exceeds ±{FIELD_MAX_OE} Oe"
                )
                return
            self.app.bus.execute(INST_DYNA, "set_field", field_oe, rate, mode_val)
            self._field_rate_oe_s = float(rate)
            self._render_field_display()
            self.app.ui_bus.post(
                W_DYNA_SETPOINT,
                {
                    "field_oe": float(field_oe),
                    "field_rate_oe_s": float(rate),
                    "field_mode": str(mode),
                },
            )
            self.app.ui_bus.post_log(f"PPMS field → {field_oe:.1f} Oe at {rate} Oe/s ({mode})")
        except Exception as exc:
            self._report_dyna_error(str(exc))
            self.app.ui_bus.post_log(f"Set field error: {exc}")

    def _on_set_chamber(self) -> None:
        try:
            mode = str(self.chamber_mode.get()).strip()
            if mode not in self._CHAMBER_MODE_TO_CODE:
                self._append_log(f"Error: Unknown chamber mode: {mode}")
                self.app.ui_bus.post_log(f"Unknown chamber mode: {mode}")
                return

            mode_code = self._CHAMBER_MODE_TO_CODE[mode]
            self.app.bus.execute(INST_DYNA, "set_chamber", mode_code)
            self.app.ui_bus.post(W_DYNA_SETPOINT, {"chamber_mode": mode})
            self.app.ui_bus.post_log(f"PPMS chamber -> {mode} ({mode_code})")
        except Exception as exc:
            self._report_dyna_error(str(exc))
            self.app.ui_bus.post_log(f"Set chamber error: {exc}")

    def _on_reset_plot(self) -> None:
        """Reset the Dyna plots - clears data and shows only future data."""
        import time
        self.app.dyna_time_data.clear()
        self.app.dyna_temp_data.clear()
        self.app.dyna_field_data.clear()
        self.app.start_time_dyna = time.time()
        self.app.last_plot_time_dyna = time.time()
        self.update_plot()
        if hasattr(self, "canvas") and self.canvas is not None:
            self.canvas.draw()
        if self._detached_canvas is not None:
            self._detached_canvas.draw()
        self.app.ui_bus.post_log(
            f"[{time.strftime('%H:%M:%S')}] Dyna plot reset - showing only new data."
        )
        self._append_log(
            f"[{time.strftime('%H:%M:%S')}] Dyna plot reset - showing only new data."
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
