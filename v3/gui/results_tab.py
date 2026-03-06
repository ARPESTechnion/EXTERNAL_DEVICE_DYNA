"""
v3.gui.results_tab  —  Results overview, script editor, and plots.

This tab combines:
* Connection-status LEDs for all instruments
* Synced live readouts (Helmholtz, PPMS, Hall, Lock-in, Switch)
* Two interactive XY plots (user-selectable axes from CSV columns)
* Script editor (load/save/run/pause/abort)
* System log panel
"""

from __future__ import annotations

import math
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import TYPE_CHECKING, Any

from v3.core.constants import CSV_FIELDNAMES, DATA_KEY_TO_CSV, LOGICAL_CHANNELS
from v3.core.ui_events import (
    W_DYNA_FIELD,
    W_DYNA_FIELD_STATUS,
    W_DYNA_TEMP,
    W_DYNA_TEMP_STATUS,
    W_HELMHOLTZ_CURRENT_A,
    W_HELMHOLTZ_CURRENT_B,
    W_HELMHOLTZ_FIELD,
    W_HELMHOLTZ_RAMPING,
    W_INSTRUMENT_CONNECTED,
    W_INSTRUMENT_DISCONNECTED,
    W_LED_HALL,
    W_LED_LOCKIN,
    W_LED_SWITCH,
    W_LOCKIN_PHASE,
    W_LOCKIN_R,
    W_LOCKIN_RESISTANCE,
    W_LOCKIN_X,
    W_LOCKIN_Y,
    W_LOG_MESSAGE,
    W_RESULTS_NEW_POINT,
    W_SCRIPT_LINE,
    W_SCRIPT_STATE,
    W_SCRIPT_STATUS,
    W_SWITCH_STATUS,
    W_HALL_RESULT,
    W_HALL_SOURCE_ENABLED,
)
from v3.gui.base_tab import BaseTab, make_led, set_led

if TYPE_CHECKING:
    from v3.gui.app import MeasureApp

try:
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    from matplotlib.figure import Figure
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False


class ResultsTab(BaseTab):
    """Results overview, plots, script editor, and log."""

    def __init__(self, parent: ttk.Frame, app: "MeasureApp") -> None:
        super().__init__(parent, app)
        self._switch_led_after_id: str | None = None
        self._hall_led_after_id: str | None = None
        self._dyna_temp_value: float | None = None
        self._dyna_field_value: float | None = None
        self._dyna_temp_status: str = "N/A"
        self._dyna_field_status: str = "N/A"
        self._helmholtz_field_value: float | None = None
        self._helmholtz_current_a: float = 0.0
        self._helmholtz_current_b: float = 0.0
        self._helmholtz_ramping: bool = False
        self._plot_refresh_after_id: str | None = None
        self._plot_refresh_min_interval_s: float = 0.5
        self._last_plot_refresh_ts: float = 0.0
        self._csv_to_internal_key: dict[str, str] = {
            csv_key: internal_key for internal_key, csv_key in DATA_KEY_TO_CSV.items()
        }
        self._suspend_modified_event = False
        self.data_filename_var = tk.StringVar(value="No data file")
        self.include_session_header_var = tk.BooleanVar(value=False)
        self.session_user_var = tk.StringVar(value="")
        self.session_sample_var = tk.StringVar(value="")
        self._graph1_color_buttons: dict[str, tk.Button] = {}
        self._graph2_color_buttons: dict[str, tk.Button] = {}
        self._channel_colors: dict[str, str] = {
            "a": "tab:blue",
            "b": "tab:orange",
            "c": "tab:green",
            "d": "tab:red",
            "e": "tab:purple",
            "f": "tab:brown",
            "g": "tab:pink",
            "h": "tab:gray",
        }
        self.channel_filter_vars: dict[str, tk.BooleanVar] = {
            ch: tk.BooleanVar(value=(ch in ("a", "b"))) for ch in LOGICAL_CHANNELS
        }

    def _blink_switch_led(self, duration_ms: int = 500) -> None:
        set_led(self.activity_leds["switch"], True)
        if self._switch_led_after_id is not None:
            try:
                self.app.root.after_cancel(self._switch_led_after_id)
            except Exception:
                pass
            self._switch_led_after_id = None
        self._switch_led_after_id = self.app.root.after(
            duration_ms,
            lambda: set_led(self.activity_leds["switch"], False),
        )

    def _blink_hall_led(self, duration_ms: int = 500) -> None:
        set_led(self.activity_leds["hall"], True)
        if self._hall_led_after_id is not None:
            try:
                self.app.root.after_cancel(self._hall_led_after_id)
            except Exception:
                pass
            self._hall_led_after_id = None
        self._hall_led_after_id = self.app.root.after(
            duration_ms,
            lambda: set_led(self.activity_leds["hall"], False),
        )

    def create_widgets(self) -> None:
        # 3-column layout matching V2
        self.parent.grid_columnconfigure(2, weight=0)
        self.parent.grid_rowconfigure(0, weight=1)

        # --- Left column: graph controls + status indicators ---
        results_left = ttk.Frame(self.parent, padding=10)
        results_left.grid(row=0, column=0, sticky="ns")

        # --- Middle column: script editor + controls ---
        results_middle = ttk.Frame(self.parent, padding=10)
        results_middle.grid(row=0, column=1, sticky="ns")

        # --- Right column: plots ---
        results_right = ttk.Frame(self.parent, width=640, height=760)
        results_right.grid(row=0, column=2, sticky="nw", padx=(5, 0))
        results_right.grid_propagate(False)

        self._build_graph_controls(results_left)
        self._build_status_panel(results_left)
        self._build_script_editor(results_middle)
        self._build_plots(results_right)

    # ------------------------------------------------------------------
    # Graph controls (axis selectors)
    # ------------------------------------------------------------------
    def _build_graph_controls(self, parent: ttk.Frame) -> None:
        gc = ttk.LabelFrame(parent, text="Graph Controls")
        gc.pack(fill="x", padx=5, pady=5)

        cols = [
            col
            for col in CSV_FIELDNAMES
            if col not in ("Measurement_Type", "Notes")
        ]
        self.x1_var = tk.StringVar(value="Time(s)")
        self.y1_var = tk.StringVar(value="Hall_Field(G)")
        self.graph1_style = tk.StringVar(value="Line + Markers")
        self.graph1_color = tk.StringVar(value="Blue")

        self.x2_var = tk.StringVar(value="Time(s)")
        self.y2_var = tk.StringVar(value="LockIn_R(V)")
        self.graph2_style = tk.StringVar(value="Line + Markers")
        self.graph2_color = tk.StringVar(value="Orange")
        color_squares = [
            ("Blue", "#1f77b4"),
            ("Red", "#d62728"),
            ("Orange", "#ff7f0e"),
            ("Green", "#2ca02c"),
            ("Black", "#000000"),
        ]

        # Graph 1 selectors
        g1 = ttk.LabelFrame(gc, text="Graph 1")
        g1.pack(fill="x", padx=2, pady=2)
        r1 = ttk.Frame(g1)
        r1.pack(fill="x")
        ttk.Label(r1, text="X:").pack(side="left")
        x1_combo = ttk.Combobox(r1, textvariable=self.x1_var, values=cols,
                    width=34, state="readonly")
        x1_combo.pack(side="left", padx=2)
        x1_combo.bind("<<ComboboxSelected>>", lambda _e: self._schedule_plot_refresh(force=True))
        r2 = ttk.Frame(g1)
        r2.pack(fill="x")
        ttk.Label(r2, text="Y:").pack(side="left")
        y1_combo = ttk.Combobox(r2, textvariable=self.y1_var, values=cols,
                    width=34, state="readonly")
        y1_combo.pack(side="left", padx=2)
        y1_combo.bind("<<ComboboxSelected>>", lambda _e: self._schedule_plot_refresh(force=True))
        r3 = ttk.Frame(g1)
        r3.pack(fill="x")
        ttk.Label(r3, text="Style:").pack(side="left")
        g1_style_combo = ttk.Combobox(r3, textvariable=self.graph1_style,
                          values=["Line", "Markers", "Line + Markers"],
                          width=18, state="readonly")
        g1_style_combo.pack(side="left", padx=2)
        g1_style_combo.bind("<<ComboboxSelected>>", lambda _e: self._schedule_plot_refresh(force=True))
        swatch_row_1 = ttk.Frame(r3)
        swatch_row_1.pack(side="left", padx=(8, 0))
        self._graph1_color_buttons = {}
        for color_name, color_hex in color_squares:
            btn = tk.Button(
                swatch_row_1,
                width=1,
                height=0,
                bg=color_hex,
                activebackground=color_hex,
                relief="flat",
                borderwidth=0,
                pady=0,
                highlightthickness=1,
                highlightbackground="#d0d0d0",
                highlightcolor="#d0d0d0",
                command=lambda c=color_name: self._on_graph_color_selected(1, c),
            )
            btn.pack(side="left", padx=1)
            self._graph1_color_buttons[color_name] = btn

        # Graph 2 selectors
        g2 = ttk.LabelFrame(gc, text="Graph 2")
        g2.pack(fill="x", padx=2, pady=2)
        r4 = ttk.Frame(g2)
        r4.pack(fill="x")
        ttk.Label(r4, text="X:").pack(side="left")
        x2_combo = ttk.Combobox(r4, textvariable=self.x2_var, values=cols,
                    width=34, state="readonly")
        x2_combo.pack(side="left", padx=2)
        x2_combo.bind("<<ComboboxSelected>>", lambda _e: self._schedule_plot_refresh(force=True))
        r5 = ttk.Frame(g2)
        r5.pack(fill="x")
        ttk.Label(r5, text="Y:").pack(side="left")
        y2_combo = ttk.Combobox(r5, textvariable=self.y2_var, values=cols,
                    width=34, state="readonly")
        y2_combo.pack(side="left", padx=2)
        y2_combo.bind("<<ComboboxSelected>>", lambda _e: self._schedule_plot_refresh(force=True))
        r6 = ttk.Frame(g2)
        r6.pack(fill="x")
        ttk.Label(r6, text="Style:").pack(side="left")
        g2_style_combo = ttk.Combobox(r6, textvariable=self.graph2_style,
                          values=["Line", "Markers", "Line + Markers"],
                          width=18, state="readonly")
        g2_style_combo.pack(side="left", padx=2)
        g2_style_combo.bind("<<ComboboxSelected>>", lambda _e: self._schedule_plot_refresh(force=True))
        swatch_row_2 = ttk.Frame(r6)
        swatch_row_2.pack(side="left", padx=(8, 0))
        self._graph2_color_buttons = {}
        for color_name, color_hex in color_squares:
            btn = tk.Button(
                swatch_row_2,
                width=1,
                height=0,
                bg=color_hex,
                activebackground=color_hex,
                relief="flat",
                borderwidth=0,
                pady=0,
                highlightthickness=1,
                highlightbackground="#d0d0d0",
                highlightcolor="#d0d0d0",
                command=lambda c=color_name: self._on_graph_color_selected(2, c),
            )
            btn.pack(side="left", padx=1)
            self._graph2_color_buttons[color_name] = btn

        self._update_graph_color_buttons()

        filter_frame = ttk.LabelFrame(gc, text="Channel Filter")
        filter_frame.pack(fill="x", padx=2, pady=(4, 2))
        for idx, ch in enumerate(LOGICAL_CHANNELS):
            ttk.Checkbutton(
                filter_frame,
                text=ch.upper(),
                variable=self.channel_filter_vars[ch],
                command=lambda: self._schedule_plot_refresh(force=True),
            ).grid(row=0, column=idx, padx=3, pady=2, sticky="w")

    def _on_graph_color_selected(self, graph_index: int, color_name: str) -> None:
        if graph_index == 1:
            self.graph1_color.set(color_name)
        else:
            self.graph2_color.set(color_name)
        self._update_graph_color_buttons()
        self._schedule_plot_refresh(force=True)

    def _update_graph_color_buttons(self) -> None:
        selected_1 = self.graph1_color.get()
        for name, btn in self._graph1_color_buttons.items():
            if name == selected_1:
                btn.configure(highlightbackground="#000000", highlightcolor="#000000")
            else:
                btn.configure(highlightbackground="#d0d0d0", highlightcolor="#d0d0d0")

        selected_2 = self.graph2_color.get()
        for name, btn in self._graph2_color_buttons.items():
            if name == selected_2:
                btn.configure(highlightbackground="#000000", highlightcolor="#000000")
            else:
                btn.configure(highlightbackground="#d0d0d0", highlightcolor="#d0d0d0")

    # ------------------------------------------------------------------
    # Status panel  —  connection LEDs + synced readouts
    # ------------------------------------------------------------------
    def _build_status_panel(self, parent: ttk.Frame) -> None:
        # --- Activity LEDs (LockIn, Hall, Switch) ---
        ttk.Label(parent, text="Status Indicators:", style="SectionTitle.TLabel").pack(
            anchor="w", padx=5, pady=(10, 2)
        )

        self.activity_leds: dict[str, tk.Label] = {}
        indicator_row = ttk.Frame(parent)
        indicator_row.pack(fill="x", padx=5, pady=1)
        for idx, (key, label_text) in enumerate([
            ("lockin", "LockIn"),
            ("hall", "Hall Bar"),
            ("switch", "Switch"),
        ]):
            item = ttk.Frame(indicator_row)
            item.pack(side="left", padx=(0, 6))
            led = make_led(item)
            led.pack(side="left", padx=(0, 4))
            ttk.Label(item, text=label_text).pack(side="left")
            self.activity_leds[key] = led

            if idx < 2:
                ttk.Separator(indicator_row, orient="vertical").pack(
                    side="left", fill="y", padx=(0, 6)
                )

        ttk.Separator(parent, orient="horizontal").pack(fill="x", padx=5, pady=5)

        # --- System status with instrument readouts ---
        ttk.Label(parent, text="System Status:", style="SectionTitleLarge.TLabel").pack(
            anchor="w", padx=5, pady=2
        )

        # Connection LEDs + readout values
        self.conn_leds: dict[str, tk.Label] = {}
        self.conn_labels: dict[str, ttk.Label] = {}

        def _make_section(parent, key, hdr_text, readout_defs):
            """Create a status section: LED + header + value labels."""
            hdr_row = ttk.Frame(parent)
            hdr_row.pack(fill="x", padx=5, pady=(5, 0))
            led = make_led(hdr_row)
            led.config(font=("Arial", 10))
            led.pack(side="left", padx=(0, 4))
            ttk.Label(hdr_row, text=hdr_text,
                       font=("Arial", 10, "bold", "underline")).pack(side="left")
            self.conn_leds[key] = led

            labels = {}
            for name, text, fg_color in readout_defs:
                lbl = tk.Label(
                    parent, text=text,
                    font=("Courier", 11, "bold"), fg=fg_color,
                    bg="#FFFFFF", relief="solid", borderwidth=1,
                    width=26, anchor="w",
                )
                lbl.pack(anchor="w", padx=(10, 5), pady=1)
                labels[name] = lbl
            return labels

        # PPMS
        ppms = _make_section(parent, "dyna", "PPMS", [
            ("temp", "  Temp: N/A", "#664400"),
            ("field", "  Field: N/A", "#006600"),
        ])
        self.results_dyna_temp = ppms["temp"]
        self.results_dyna_field = ppms["field"]

        # Helmholtz
        helm = _make_section(parent, "helmholtz", "Helmholtz", [
            ("field", "  Field: N/A", "#006600"),
            ("ch_a", "  Ch A: N/A", "#003388"),
            ("ch_b", "  Ch B: N/A", "#664400"),
        ])
        self.results_helmholtz_field = helm["field"]
        self.results_helmholtz_ch_a = helm["ch_a"]
        self.results_helmholtz_ch_b = helm["ch_b"]

        # Hall Bar
        hall = _make_section(parent, "hall", "Hall Bar", [
            ("voltage", "  V: N/A", "#006600"),
            ("field", "  B: N/A", "#006600"),
        ])
        self.results_hall_voltage = hall["voltage"]
        self.results_hall_field = hall["field"]

        # Lock-In
        lockin = _make_section(parent, "lockin", "Lock-In", [
            ("x", "  X: N/A", "#663366"),
            ("y", "  Y: N/A", "#663366"),
            ("r", "  R: N/A", "#663366"),
            ("phase", "  θ: N/A", "#663366"),
            ("resistance", "  Resistance: N/A", "#663366"),
        ])
        self.results_lockin_x = lockin["x"]
        self.results_lockin_y = lockin["y"]
        self.results_lockin_r = lockin["r"]
        self.results_lockin_phase = lockin["phase"]
        self.results_lockin_resistance = lockin["resistance"]

        # Switch
        sw = _make_section(parent, "switch", "Switch", [
            ("status", "  Status: N/A", "#006600"),
        ])
        self.results_switch_status = sw["status"]

    # ------------------------------------------------------------------
    # Plots
    # ------------------------------------------------------------------
    def _build_plots(self, parent: ttk.Frame) -> None:
        if not HAS_MATPLOTLIB:
            ttk.Label(parent, text="(matplotlib not available)").pack()
            self.canvas = None
            return

        # V2-matching: vertically stacked subplots (6,7) figure
        self.fig = Figure(figsize=(6, 7), dpi=100)
        self.ax1 = self.fig.add_subplot(211)
        self.ax2 = self.fig.add_subplot(212)
        self.ax1.tick_params(axis="both", which="both", direction="in")
        self.ax2.tick_params(axis="both", which="both", direction="in")
        self.fig.subplots_adjust(
            left=0.16, right=0.97, top=0.95, bottom=0.10, hspace=0.48
        )

        self.canvas = FigureCanvasTkAgg(self.fig, master=parent)
        self.canvas.get_tk_widget().pack(fill="both", expand=False)

        # Navigation toolbar
        try:
            from matplotlib.backends.backend_tkagg import NavigationToolbar2Tk
            toolbar = NavigationToolbar2Tk(self.canvas, parent)
            toolbar.update()
        except Exception:
            pass

    def refresh_plots(self) -> None:
        """Refresh both plots from the data manager results buffer."""
        if self.canvas is None:
            return
        results = list(self.app.data_mgr.get_results())
        if not results:
            self.ax1.clear()
            self.ax2.clear()
            self.ax1.set_title("Graph 1")
            self.ax2.set_title("Graph 2")
            self.ax1.set_xlabel(self.x1_var.get())
            self.ax1.set_ylabel(self.y1_var.get())
            self.ax2.set_xlabel(self.x2_var.get())
            self.ax2.set_ylabel(self.y2_var.get())
            self.ax1.tick_params(axis="both", which="both", direction="in")
            self.ax2.tick_params(axis="both", which="both", direction="in")
            self.fig.tight_layout(pad=3.0)
            self.canvas.draw_idle()
            self._last_plot_refresh_ts = time.time()
            return

        selected_channels = [ch for ch, var in self.channel_filter_vars.items() if var.get()]
        if not selected_channels:
            selected_channels = list(LOGICAL_CHANNELS)

        for ax, xvar, yvar, style_var, color_var in [
            (self.ax1, self.x1_var, self.y1_var, self.graph1_style, self.graph1_color),
            (self.ax2, self.x2_var, self.y2_var, self.graph2_style, self.graph2_color),
        ]:
            ax.clear()
            x_label = xvar.get()
            y_label = yvar.get()
            x_key = self._resolve_plot_key(x_label)
            y_key = self._resolve_plot_key(y_label)
            style = style_var.get()
            color = self._resolve_plot_color(color_var.get())

            marker = "o" if "Marker" in style else ""
            linestyle = "-" if "Line" in style else "None"

            plotted_series = 0
            if len(selected_channels) > 1:
                for channel in selected_channels:
                    xs: list[float] = []
                    ys: list[float] = []
                    for row in results:
                        row_channel = self._extract_row_channel(row)
                        if row_channel is not None and row_channel != channel:
                            continue
                        x_val = self._row_value_for_channel(row, x_key, channel)
                        y_val = self._row_value_for_channel(row, y_key, channel)
                        x_num = self._to_numeric(x_val)
                        y_num = self._to_numeric(y_val)
                        if x_num is None or y_num is None:
                            continue
                        xs.append(x_num)
                        ys.append(y_num)
                    if xs and ys:
                        plotted_series += 1
                        ax.plot(
                            xs,
                            ys,
                            marker=marker,
                            linestyle=linestyle,
                            markersize=3,
                            color=self._channel_colors.get(channel, color),
                            label=f"Ch {channel.upper()}",
                        )
                if plotted_series > 0:
                    ax.legend(loc="best", fontsize=8)
            else:
                channel = selected_channels[0]
                xs: list[float] = []
                ys: list[float] = []
                for row in results:
                    row_channel = self._extract_row_channel(row)
                    if row_channel is not None and row_channel != channel:
                        continue
                    x_val = self._row_value_for_channel(row, x_key, channel)
                    y_val = self._row_value_for_channel(row, y_key, channel)
                    x_num = self._to_numeric(x_val)
                    y_num = self._to_numeric(y_val)
                    if x_num is None or y_num is None:
                        continue
                    xs.append(x_num)
                    ys.append(y_num)
                if xs and ys:
                    ax.plot(xs, ys, marker=marker, linestyle=linestyle, markersize=3, color=color)
            ax.set_xlabel(x_label)
            ax.set_ylabel(y_label)
            ax.tick_params(axis="both", which="both", direction="in")

        self.fig.tight_layout(pad=3.0)
        self.canvas.draw_idle()
        self._last_plot_refresh_ts = time.time()

    def _resolve_plot_key(self, selected_label: str) -> str:
        """Map CSV column selection to internal results dict key."""
        key = str(selected_label).strip()
        if key in self._csv_to_internal_key:
            return self._csv_to_internal_key[key]
        return key

    def _resolve_plot_color(self, selected_color: str) -> str:
        color_map = {
            "Blue": "tab:blue",
            "Red": "tab:red",
            "Orange": "tab:orange",
            "Green": "tab:green",
            "Black": "black",
        }
        return color_map.get(str(selected_color).strip(), "tab:blue")

    def _to_numeric(self, value: Any) -> float | None:
        """Convert values to finite float for plotting; return None when invalid."""
        try:
            v = float(value)
        except Exception:
            return None
        if math.isnan(v) or math.isinf(v):
            return None
        return v

    def _extract_row_channel(self, row: dict[str, Any]) -> str | None:
        raw = row.get("Channel")
        if raw is not None:
            token = str(raw).strip().lower()
            if token in LOGICAL_CHANNELS:
                return token

        for channel in LOGICAL_CHANNELS:
            for key in (
                f"LockIn_X_{channel}",
                f"LockIn_Y_{channel}",
                f"LockIn_R_{channel}",
                f"LockIn_Theta_{channel}",
                f"Sample_{channel}_Resistance",
            ):
                value = self._to_numeric(row.get(key))
                if value is not None:
                    return channel
        return None

    def _row_value_for_channel(self, row: dict[str, Any], key: str, channel: str) -> Any:
        # Preferred generic keys
        if key in row:
            return row.get(key)

        # Backward-compatible mapping for legacy channel-suffixed lock-in keys
        if key in {
            "LockIn_X", "LockIn_X_Error",
            "LockIn_Y", "LockIn_Y_Error",
            "LockIn_R", "LockIn_R_Error",
            "LockIn_Theta", "LockIn_Theta_Error",
            "Sample_Resistance", "Sample_Resistance_Error",
        }:
            mapped_lookup = {
                "LockIn_X": f"LockIn_X_{channel}",
                "LockIn_X_Error": f"LockIn_X_{channel}_Error",
                "LockIn_Y": f"LockIn_Y_{channel}",
                "LockIn_Y_Error": f"LockIn_Y_{channel}_Error",
                "LockIn_R": f"LockIn_R_{channel}",
                "LockIn_R_Error": f"LockIn_R_{channel}_Error",
                "LockIn_Theta": f"LockIn_Theta_{channel}",
                "LockIn_Theta_Error": f"LockIn_Theta_{channel}_Error",
                "Sample_Resistance": f"Sample_{channel}_Resistance",
                "Sample_Resistance_Error": f"Sample_{channel}_Resistance_Error",
            }
            mapped = mapped_lookup[key]
            return row.get(mapped)

        # If user selected a channel-specific legacy key, only pass it for matching channel.
        channel_suffixes = [f"_{ch}" for ch in LOGICAL_CHANNELS]
        for suffix in channel_suffixes:
            token = f"{suffix}"
            if token in key and not key.endswith("_Error"):
                if suffix != f"_{channel}":
                    return None
                return row.get(key)
            if token in key and key.endswith("_Error"):
                if suffix != f"_{channel}":
                    return None
                return row.get(key)

        return row.get(key)

    def _schedule_plot_refresh(self, *, force: bool = False) -> None:
        """Coalesced/throttled plot refresh, matching V2 behavior."""
        if self.canvas is None:
            return

        if self._plot_refresh_after_id is not None:
            return

        now = time.time()
        elapsed = now - self._last_plot_refresh_ts
        if force or elapsed >= self._plot_refresh_min_interval_s:
            self.refresh_plots()
            return

        delay_ms = max(1, int((self._plot_refresh_min_interval_s - elapsed) * 1000))
        self._plot_refresh_after_id = self.app.root.after(delay_ms, self._run_scheduled_plot_refresh)

    def _run_scheduled_plot_refresh(self) -> None:
        self._plot_refresh_after_id = None
        self.refresh_plots()

    # ------------------------------------------------------------------
    # Script editor
    # ------------------------------------------------------------------
    def _build_script_editor(self, parent: ttk.Frame) -> None:
        data_file_section = ttk.LabelFrame(parent, text="Data File Control")
        data_file_section.pack(fill="x", padx=5, pady=(5, 4))

        data_file_row = ttk.Frame(data_file_section)
        data_file_row.pack(fill="x", padx=5, pady=4)
        ttk.Label(data_file_row, text="Current data file:").pack(side="left")
        ttk.Label(
            data_file_row,
            textvariable=self.data_filename_var,
            font=("Courier", 10),
            relief="sunken",
            background="#f0f0f0",
            anchor="w",
            width=26,
        ).pack(side="left", padx=(4, 0), fill="x", expand=True)

        metadata_row = ttk.Frame(data_file_section)
        metadata_row.pack(fill="x", padx=5, pady=(0, 5))

        ttk.Button(metadata_row, text="Change Data File", command=self._on_change_data_file).pack(
            side="left"
        )

        ttk.Separator(metadata_row, orient="vertical").pack(side="left", fill="y", padx=(8, 8))

        ttk.Checkbutton(
            metadata_row,
            text="Add header",
            variable=self.include_session_header_var,
            command=self._on_session_header_settings_changed,
        ).pack(side="left", padx=(10, 8))

        ttk.Label(metadata_row, text="Sample:").pack(side="left")
        sample_entry = ttk.Entry(metadata_row, textvariable=self.session_sample_var, width=12)
        sample_entry.pack(side="left", padx=(4, 10))
        sample_entry.bind("<KeyRelease>", self._on_session_header_text_edited)
        sample_entry.bind("<FocusOut>", self._on_session_header_text_edited)

        ttk.Label(metadata_row, text="User:").pack(side="left")
        user_entry = ttk.Entry(metadata_row, textvariable=self.session_user_var, width=12)
        user_entry.pack(side="left", padx=(4, 0))
        user_entry.bind("<KeyRelease>", self._on_session_header_text_edited)
        user_entry.bind("<FocusOut>", self._on_session_header_text_edited)

        script_control_section = ttk.LabelFrame(parent, text="Script Control")
        script_control_section.pack(fill="x", padx=5, pady=(4, 5))

        script_name_row = ttk.Frame(script_control_section)
        script_name_row.pack(fill="x", padx=5, pady=4)
        ttk.Label(script_name_row, text="Current script:").pack(side="left")
        ttk.Label(
            script_name_row,
            textvariable=self.app.script_filename,
            font=("Courier", 10),
            relief="sunken",
            background="#f0f0f0",
            anchor="w",
            width=26,
        ).pack(side="left", padx=(4, 0), fill="x", expand=True)

        # Buttons
        btn_row = ttk.Frame(script_control_section)
        btn_row.pack(fill="x", padx=5, pady=2)

        ttk.Button(btn_row, text="Run", command=self._on_run_script).grid(row=0, column=0, padx=2)
        ttk.Button(btn_row, text="Load", command=self._on_load_script).grid(row=0, column=1, padx=2)
        ttk.Button(btn_row, text="Save", command=lambda: self._on_save_script(force_prompt=True)).grid(
            row=0, column=2, padx=2
        )
        self.pause_button = ttk.Button(btn_row, text="Pause", command=self._on_pause_script)
        self.pause_button.grid(row=0, column=3, padx=2)
        ttk.Button(btn_row, text="Abort", command=self._on_abort_script).grid(row=0, column=4, padx=2)

        # Status (Courier 10, sunken, f0f0f0 bg)
        self.script_status = tk.StringVar(value="Status: Idle")
        status_lbl = ttk.Label(
            script_control_section, textvariable=self.script_status,
            font=("Courier", 10), relief="sunken", background="#f0f0f0",
        )
        status_lbl.pack(fill="x", padx=5, pady=(2, 5))

        # Script editor label
        ttk.Label(parent, text="Script Editor:", style="SectionTitle.TLabel").pack(anchor="w", padx=5, pady=(5, 2))

        # Text editor (tk.Text, height=10, width=50, Courier 10)
        editor_frame = ttk.Frame(parent)
        editor_frame.pack(fill="both", expand=True, padx=5, pady=2)

        self.script_text = tk.Text(
            editor_frame, height=14, width=58, font=("Courier", 10),
            undo=True, wrap="none",
        )
        sb = ttk.Scrollbar(editor_frame, command=self.script_text.yview)
        self.script_text.configure(yscrollcommand=sb.set)
        self.script_text.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.script_text.bind("<<Modified>>", self._on_script_modified)
        self.script_text.bind("<Control-z>", self._on_script_undo)
        self.script_text.bind("<Control-Z>", self._on_script_undo)
        self.script_text.bind("<Control-y>", self._on_script_redo)
        self.script_text.bind("<Control-Y>", self._on_script_redo)
        self.script_text.bind("<Control-Shift-z>", self._on_script_redo)
        self.script_text.bind("<Control-Shift-Z>", self._on_script_redo)
        self.script_text.bind("<Control-a>", self._on_script_select_all)
        self.script_text.bind("<Control-A>", self._on_script_select_all)
        self.script_text.bind("<Control-s>", self._on_script_save)
        self.script_text.bind("<Control-S>", self._on_script_save)
        self.script_text.bind("<Control-Shift-s>", self._on_script_save_as)
        self.script_text.bind("<Control-Shift-S>", self._on_script_save_as)
        self.script_text.bind("<Control-o>", self._on_script_load)
        self.script_text.bind("<Control-O>", self._on_script_load)
        self.script_text.bind("<Control-Return>", self._on_script_run)
        self.script_text.bind("<Control-KP_Enter>", self._on_script_run)
        self.script_text.edit_modified(False)

        # Line highlight tags
        self.script_text.tag_configure("current_line", background="#FFFF99")
        self.script_text.tag_configure("loop_body_line", background="#FF9999")

        self._on_session_header_settings_changed()
        self._refresh_data_filename_display()

        # Log (below script editor)
        ttk.Label(parent, text="System Log:", style="SectionTitle.TLabel").pack(
            anchor="w", padx=5, pady=(10, 2)
        )
        log_frame = ttk.Frame(parent)
        log_frame.pack(fill="x", expand=False, padx=5, pady=2)
        self.log_text = tk.Text(
            log_frame, height=4, width=58, state="disabled",
            font=("Courier", 9), wrap="word",
        )
        log_sb = ttk.Scrollbar(log_frame, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=log_sb.set)
        self.log_text.pack(side="left", fill="both", expand=True)
        log_sb.pack(side="right", fill="y")

    # ------------------------------------------------------------------
    # System log helper
    # ------------------------------------------------------------------
    def _append_log(self, msg: str) -> None:
        self.log_text.configure(state="normal")
        self.log_text.insert("end", msg + "\n")
        self.log_text.see("end")
        # Trim to 1000 lines max
        line_count = int(self.log_text.index("end-1c").split(".")[0])
        if line_count > 1000:
            self.log_text.delete("1.0", f"{line_count - 1000}.0")
        self.log_text.configure(state="disabled")

    # ------------------------------------------------------------------
    # Script line highlighting
    # ------------------------------------------------------------------
    def highlight_line(self, line_num: int, loop_level: int = 0, parent_line: int = 0) -> None:
        """Highlight script line(s), keeping loop parent and child visible together."""
        self.script_text.tag_remove("current_line", "1.0", "end")
        self.script_text.tag_remove("loop_body_line", "1.0", "end")
        if line_num > 0:
            if loop_level > 0 and parent_line > 0:
                self.script_text.tag_add("current_line", f"{parent_line}.0", f"{parent_line}.end")
                self.script_text.tag_add("loop_body_line", f"{line_num}.0", f"{line_num}.end")
            else:
                tag_name = "loop_body_line" if loop_level > 0 else "current_line"
                self.script_text.tag_add(tag_name, f"{line_num}.0", f"{line_num}.end")
            self.script_text.see(f"{line_num}.0")

    def clear_highlights(self) -> None:
        """Remove all line highlights."""
        self.script_text.tag_remove("current_line", "1.0", "end")
        self.script_text.tag_remove("loop_body_line", "1.0", "end")

    def _on_script_undo(self, _event: tk.Event | None = None) -> str:
        """Undo in script editor via Ctrl+Z."""
        try:
            self.script_text.edit_undo()
        except tk.TclError:
            pass
        return "break"

    def _on_script_redo(self, _event: tk.Event | None = None) -> str:
        """Redo in script editor via Ctrl+Y / Ctrl+Shift+Z."""
        try:
            self.script_text.edit_redo()
        except tk.TclError:
            pass
        return "break"

    def _on_script_select_all(self, _event: tk.Event | None = None) -> str:
        """Select all text in script editor via Ctrl+A."""
        self.script_text.tag_add("sel", "1.0", "end-1c")
        self.script_text.mark_set("insert", "1.0")
        self.script_text.see("insert")
        return "break"

    def _on_script_save(self, _event: tk.Event | None = None) -> str:
        """Save script editor content via Ctrl+S."""
        self._on_save_script()
        return "break"

    def _on_script_save_as(self, _event: tk.Event | None = None) -> str:
        """Save script editor content via Ctrl+Shift+S (Save As)."""
        self._on_save_script(force_prompt=True)
        return "break"

    def _on_script_load(self, _event: tk.Event | None = None) -> str:
        """Load script into editor via Ctrl+O."""
        self._on_load_script()
        return "break"

    def _on_script_run(self, _event: tk.Event | None = None) -> str:
        """Run script via Ctrl+Enter."""
        self._on_run_script()
        return "break"

    # ------------------------------------------------------------------
    # Event handling
    # ------------------------------------------------------------------
    def on_event(self, widget_id: str, value: Any) -> None:
        if widget_id in {W_SCRIPT_STATUS, W_SCRIPT_STATE, W_SCRIPT_LINE, W_RESULTS_NEW_POINT}:
            self._refresh_data_filename_display()

        # --- Log ---
        if widget_id == W_LOG_MESSAGE:
            self._append_log(str(value))

        # --- Script status ---
        elif widget_id == W_SCRIPT_STATUS:
            self.script_status.set(f"Status: {value}")
        elif widget_id == W_SCRIPT_STATE:
            self.script_status.set(f"State: {value}")
            state_text = str(value).strip().lower()
            if state_text == "paused":
                self.pause_button.configure(text="Unpause")
            else:
                self.pause_button.configure(text="Pause")
            if state_text in {"idle", "error"}:
                self.clear_highlights()
        elif widget_id == W_SCRIPT_LINE:
            if isinstance(value, tuple):
                if len(value) >= 4:
                    line, _total, loop_level, parent_line = value
                    self.highlight_line(int(line), int(loop_level), int(parent_line))
                elif len(value) >= 3:
                    line, _total, loop_level = value
                    self.highlight_line(int(line), int(loop_level), 0)
                elif len(value) >= 2:
                    line, _total = value
                    self.highlight_line(int(line), 0, 0)

        # --- Connection LEDs ---
        elif widget_id == W_INSTRUMENT_CONNECTED:
            key = str(value)
            if key in self.conn_leds:
                set_led(self.conn_leds[key], True)
        elif widget_id == W_INSTRUMENT_DISCONNECTED:
            key = str(value)
            if key in self.conn_leds:
                set_led(self.conn_leds[key], False)

        # --- Activity LEDs (during actions/measurement) ---
        elif widget_id == W_LED_LOCKIN:
            set_led(self.activity_leds["lockin"], bool(value))
        elif widget_id == W_LED_HALL:
            set_led(self.activity_leds["hall"], bool(value))
        elif widget_id == W_HALL_SOURCE_ENABLED:
            set_led(self.activity_leds["hall"], bool(value))
        elif widget_id == W_LED_SWITCH:
            if bool(value):
                self._blink_switch_led()
            else:
                if self._switch_led_after_id is not None:
                    try:
                        self.app.root.after_cancel(self._switch_led_after_id)
                    except Exception:
                        pass
                    self._switch_led_after_id = None
                set_led(self.activity_leds["switch"], False)

        # --- Synced readouts from other tabs ---
        elif widget_id == W_HELMHOLTZ_FIELD:
            self._helmholtz_field_value = float(value)
            self._render_helmholtz_field_label()
        elif widget_id == W_HELMHOLTZ_CURRENT_A:
            self._helmholtz_current_a = float(value)
            self._render_helmholtz_field_label()
            self.results_helmholtz_ch_a.configure(text=f"  Ch A: {value:.4f} A")
        elif widget_id == W_HELMHOLTZ_CURRENT_B:
            self._helmholtz_current_b = float(value)
            self._render_helmholtz_field_label()
            self.results_helmholtz_ch_b.configure(text=f"  Ch B: {value:.4f} A")
        elif widget_id == W_HELMHOLTZ_RAMPING:
            self._helmholtz_ramping = bool(value)
            self._render_helmholtz_field_label()
        elif widget_id == W_DYNA_TEMP:
            self._dyna_temp_value = float(value) if value is not None else None
            self._render_dyna_temp_label()
        elif widget_id == W_DYNA_FIELD:
            self._dyna_field_value = float(value) if value is not None else None
            self._render_dyna_field_label()
        elif widget_id == W_DYNA_TEMP_STATUS:
            self._dyna_temp_status = self._normalize_status(value)
            self._render_dyna_temp_label()
        elif widget_id == W_DYNA_FIELD_STATUS:
            self._dyna_field_status = self._normalize_status(value)
            self._render_dyna_field_label()
        elif widget_id == W_LOCKIN_X:
            self.results_lockin_x.configure(text=f"  X: {value:.6e} V")
        elif widget_id == W_LOCKIN_Y:
            self.results_lockin_y.configure(text=f"  Y: {value:.6e} V")
        elif widget_id == W_LOCKIN_R:
            self.results_lockin_r.configure(text=f"  R: {value:.6e} V")
        elif widget_id == W_LOCKIN_RESISTANCE:
            try:
                v = float(value)
                if v != v:
                    self.results_lockin_resistance.configure(text="  Resistance: N/A")
                else:
                    self.results_lockin_resistance.configure(text=f"  Resistance: {v:.4e} Ω")
            except Exception:
                self.results_lockin_resistance.configure(text="  Resistance: N/A")
        elif widget_id == W_LOCKIN_PHASE:
            self.results_lockin_phase.configure(text=f"  θ: {value:.2f}°")
        elif widget_id == W_SWITCH_STATUS:
            self.results_switch_status.configure(text=f"  {value}")
        elif widget_id == W_HALL_RESULT:
            if isinstance(value, dict):
                v = value.get("voltage", 0)
                f = value.get("field", 0)
                self.results_hall_voltage.configure(text=f"  V: {v:.6e} V")
                self.results_hall_field.configure(text=f"  B: {f:.2f} G")
                self._blink_hall_led()

        # --- New data point → auto-refresh plot ---
        elif widget_id == W_RESULTS_NEW_POINT:
            self._schedule_plot_refresh()

    def on_instrument_connected(self, name: str) -> None:
        if name in self.conn_leds:
            set_led(self.conn_leds[name], True)

    def on_instrument_disconnected(self, name: str) -> None:
        if name in self.conn_leds:
            set_led(self.conn_leds[name], False)
        if name == "hall":
            set_led(self.activity_leds["hall"], False)
        if name == "dyna":
            self._dyna_temp_value = None
            self._dyna_field_value = None
            self._dyna_temp_status = "N/A"
            self._dyna_field_status = "N/A"
            self._render_dyna_temp_label()
            self._render_dyna_field_label()

    def _normalize_status(self, value: Any) -> str:
        if value is None:
            return "N/A"
        text = str(value).strip()
        return text if text else "N/A"

    def _render_dyna_temp_label(self) -> None:
        temp_text = f"{self._dyna_temp_value:.2f} K" if self._dyna_temp_value is not None else "N/A"
        status_suffix = f" ({self._dyna_temp_status})" if self._dyna_temp_status != "N/A" else ""
        self.results_dyna_temp.configure(text=f"  Temp: {temp_text}{status_suffix}")

    def _render_dyna_field_label(self) -> None:
        field_text = f"{self._dyna_field_value:.1f} Oe" if self._dyna_field_value is not None else "N/A"
        status_suffix = f" ({self._dyna_field_status})" if self._dyna_field_status != "N/A" else ""
        self.results_dyna_field.configure(text=f"  Field: {field_text}{status_suffix}")

    def _render_helmholtz_field_label(self) -> None:
        field_text = (
            f"{self._helmholtz_field_value:.2f} G"
            if self._helmholtz_field_value is not None
            else "N/A"
        )
        total_current = abs(self._helmholtz_current_a) + abs(self._helmholtz_current_b)
        if self._helmholtz_ramping:
            state = "Ramping"
        elif total_current > 1e-6:
            state = "Holding"
        else:
            state = "Idle"
        self.results_helmholtz_field.configure(text=f"  Field: {field_text} ({state})")

    # ------------------------------------------------------------------
    # Script button handlers
    # ------------------------------------------------------------------
    def _on_run_script(self) -> None:
        if not self.prompt_save_script_if_needed("before running"):
            return
        script = self.script_text.get("1.0", "end").strip()
        if not script:
            self.app.ui_bus.post_log("No script to run.")
            return
        self.app.run_script(script)

    def _on_pause_script(self) -> None:
        self.app.pause_script()

    def _on_abort_script(self) -> None:
        self.app.abort_script()
        self.clear_highlights()
        self.pause_button.configure(text="Pause")

    def _on_load_script(self) -> None:
        if not self.prompt_save_script_if_needed("before loading another script"):
            return
        path = filedialog.askopenfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
        )
        if path:
            try:
                text = Path(path).read_text(encoding="utf-8")
                self._suspend_modified_event = True
                self.script_text.delete("1.0", "end")
                self.script_text.insert("1.0", text)
                self.script_text.edit_modified(False)
                self._suspend_modified_event = False
                self.app.script_filename.set(Path(path).name)
                self.app.script_file_path = str(path)
                self.app.script_dirty = False
                self.app.ui_bus.post_log(f"Loaded: {path}")
            except Exception as exc:
                self._suspend_modified_event = False
                self.app.ui_bus.post_log(f"Load error: {exc}")

    def _on_save_script(self, force_prompt: bool = False) -> None:
        path = None if force_prompt else self.app.script_file_path
        if not path:
            path = filedialog.asksaveasfilename(
                defaultextension=".txt",
                initialfile=self.app.script_filename.get(),
                filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
            )
        if path:
            try:
                text = self.script_text.get("1.0", "end").strip()
                Path(path).write_text(text, encoding="utf-8")
                self.app.script_filename.set(Path(path).name)
                self.app.script_file_path = str(path)
                self.app.script_dirty = False
                self.script_text.edit_modified(False)
                self.app.ui_bus.post_log(f"Saved: {path}")
            except Exception as exc:
                self.app.ui_bus.post_log(f"Save error: {exc}")

    def _refresh_data_filename_display(self) -> None:
        data_mgr = getattr(self.app, "data_mgr", None)
        data_path = getattr(data_mgr, "data_filename", None)

        if isinstance(data_path, Path):
            text = data_path.name
        elif isinstance(data_path, str) and data_path.strip():
            text = Path(data_path).name
        else:
            text = "No data file"

        self.data_filename_var.set(text)

    def _on_session_header_text_edited(self, _event: tk.Event | None = None) -> None:
        self._on_session_header_settings_changed()

    def _on_session_header_settings_changed(self) -> None:
        data_mgr = getattr(self.app, "data_mgr", None)
        if data_mgr is None:
            return
        if not hasattr(data_mgr, "configure_session_header"):
            return
        try:
            data_mgr.configure_session_header(
                enabled=self.include_session_header_var.get(),
                user=self.session_user_var.get(),
                sample=self.session_sample_var.get(),
            )
        except Exception as exc:
            self.app.ui_bus.post_log(f"Session header config error: {exc}")

    def _on_change_data_file(self) -> None:
        data_mgr = getattr(self.app, "data_mgr", None)
        if data_mgr is None:
            self.app.ui_bus.post_log("Data manager unavailable.")
            return

        self._on_session_header_settings_changed()

        data_path = getattr(data_mgr, "data_filename", None)
        if isinstance(data_path, Path):
            initial_dir = str(data_path.parent)
            initial_file = data_path.name
        else:
            data_dir = getattr(data_mgr, "data_dir", Path.cwd())
            initial_dir = str(data_dir)
            initial_file = "Data.csv"

        selected = filedialog.asksaveasfilename(
            title="Select Data File",
            defaultextension=".csv",
            initialdir=initial_dir,
            initialfile=initial_file,
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
        )
        if not selected:
            return

        target = Path(selected)
        append = False
        if target.exists():
            choice = messagebox.askyesnocancel(
                "Data File Exists",
                "Selected file already exists.\nYes = append to it\nNo = create a numbered new file",
            )
            if choice is None:
                return
            append = bool(choice)

        try:
            new_path = data_mgr.initialize_file(
                directory=str(target.parent),
                filename=target.name,
                append=append,
            )
            if new_path is None:
                self.app.ui_bus.post_log("Failed to change data file.")
                return
            self._refresh_data_filename_display()
            self.app.ui_bus.post_log(f"Data file set to: {new_path}")
        except Exception as exc:
            self.app.ui_bus.post_log(f"Change data file error: {exc}")

    def _on_script_modified(self, _event: tk.Event | None = None) -> None:
        if self._suspend_modified_event:
            self.script_text.edit_modified(False)
            return
        if self.script_text.edit_modified():
            self.app.script_dirty = True
            self.script_text.edit_modified(False)

    def has_unsaved_script_changes(self) -> bool:
        return bool(getattr(self.app, "script_dirty", False))

    def prompt_save_script_if_needed(self, context: str = "") -> bool:
        if not self.has_unsaved_script_changes():
            return True

        message = "Script has unsaved changes. Save now?"
        if context:
            message = f"Script has unsaved changes {context}. Save now?"

        choice = messagebox.askyesnocancel("Unsaved Script", message)
        if choice is None:
            return False
        if choice is False:
            return True

        self._on_save_script()
        return not self.has_unsaved_script_changes()

    def _on_validate_script(self) -> None:
        script = self.script_text.get("1.0", "end").strip()
        if not script:
            self.app.ui_bus.post_log("No script to validate.")
            return

        commands = self.app.parser.parse(script)
        errors = self.app.validator.validate(
            commands,
            connected_instruments=set(self.app.bus.connected_instruments()),
        )
        if errors:
            for e in errors:
                self.app.ui_bus.post_log(
                    f"[{e.severity.upper()}] L{e.line_number}: {e.message}"
                )
        else:
            self.app.ui_bus.post_log("Script validation: OK ✓")
