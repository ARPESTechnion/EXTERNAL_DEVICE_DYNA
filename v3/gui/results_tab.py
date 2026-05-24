"""
v3.gui.results_tab  -  Results overview, script editor, and plots.

This tab combines:
* Connection-status LEDs for all instruments
* Synced live readouts (Helmholtz, PPMS, Hall, Lock-in, Switch)
* Two interactive XY plots (user-selectable axes from CSV columns)
* Script editor (load/save/run/pause/abort)
* System log panel
"""

from __future__ import annotations

import csv
import math
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import TYPE_CHECKING, Any, Callable

from v3.core.constants import CSV_FIELDNAMES, DATA_KEY_TO_CSV, INST_LOCKIN, LOGICAL_CHANNELS, SWITCH_PIN_MAX
from v3.core.script_parser import ALLOWED_KWARGS, LOOP_COMMANDS, MIN_POSITIONAL, VALID_COMMANDS
from v3.core.ui_events import (
    W_DYNA_CHAMBER,
    W_DYNA_CHAMBER_STATUS,
    W_DYNA_FIELD,
    W_DYNA_FIELD_STATUS,
    W_DYNA_SETPOINT,
    W_DYNA_TEMP,
    W_DYNA_TEMP_STATUS,
    W_HELMHOLTZ_CURRENT_A,
    W_HELMHOLTZ_CURRENT_B,
    W_HELMHOLTZ_FIELD,
    W_HELMHOLTZ_RAMPING,
    W_HELMHOLTZ_RESISTANCE_A,
    W_HELMHOLTZ_RESISTANCE_B,
    W_HELMHOLTZ_SETPOINT,
    W_INSTRUMENT_CONNECTED,
    W_INSTRUMENT_DISCONNECTED,
    W_LED_HALL,
    W_LED_LOCKIN,
    W_LED_SWITCH,
    W_LOCKIN_OUTPUT_VOLTAGE,
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
from v3.gui.components import StatusStrip, ValidatingEntry, make_float_validator, make_int_validator
from v3.gui.lockin_tab import R_LOCKIN_OPTIONS
from v3.gui.theme import COLORS, FONTS, SPACING

if TYPE_CHECKING:
    from v3.gui.app import MeasureApp

try:
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    from matplotlib.figure import Figure
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False


class ResultsTab(BaseTab):
    """Results overview, plots, script editor, and log."""

    def __init__(self, parent: ttk.Frame, app: "MeasureApp") -> None:
        super().__init__(parent, app)
        self._switch_led_after_id: str | None = None
        self._hall_led_after_id: str | None = None
        self._dyna_temp_value: float | None = None
        self._dyna_field_value: float | None = None
        self._dyna_chamber_value: int | None = None
        self._dyna_temp_status: str = "N/A"
        self._dyna_field_status: str = "N/A"
        self._dyna_chamber_status: str = "N/A"
        self._dyna_temp_rate_k_min: float | None = None
        self._dyna_field_rate_oe_s: float | None = None
        self._helmholtz_field_value: float | None = None
        self._helmholtz_current_a: float = 0.0
        self._helmholtz_current_b: float = 0.0
        self._helmholtz_resistance_a: float | None = None
        self._helmholtz_resistance_b: float | None = None
        self._helmholtz_ramping: bool = False
        self._helmholtz_rate_mA_s: float | None = None
        self._plot_refresh_after_id: str | None = None
        self._plot_refresh_min_interval_s: float = 0.5
        self._last_plot_refresh_ts: float = 0.0
        self.data_plot_range_start_var = tk.IntVar(value=1)
        self.data_plot_range_end_var = tk.IntVar(value=1000)
        # Backward-compatible aliases used by existing tests/helpers.
        self.iv_range_start_var = self.data_plot_range_start_var
        self.iv_range_end_var = self.data_plot_range_end_var
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
        self._errorbar_chk_g1: ttk.Checkbutton | None = None
        self._errorbar_chk_g2: ttk.Checkbutton | None = None
        self._fit_combo_g1: ttk.Combobox | None = None
        self._fit_combo_g2: ttk.Combobox | None = None
        self._plots_grid_enabled: bool = True
        self._plots_grid_button: ttk.Button | None = None
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
        self.channel_filter_vars_g1: dict[str, tk.BooleanVar] = {
            ch: tk.BooleanVar(value=(ch in ("a", "b"))) for ch in LOGICAL_CHANNELS
        }
        self.channel_filter_vars_g2: dict[str, tk.BooleanVar] = {
            ch: tk.BooleanVar(value=(ch in ("a", "b"))) for ch in LOGICAL_CHANNELS
        }
        self.derivative_enabled_g1 = tk.BooleanVar(value=False)
        self.derivative_enabled_g2 = tk.BooleanVar(value=False)
        self.smoothing_enabled_g1 = tk.BooleanVar(value=False)
        self.smoothing_enabled_g2 = tk.BooleanVar(value=False)
        self.smoothing_window_g1 = tk.IntVar(value=5)
        self.smoothing_window_g2 = tk.IntVar(value=5)
        self.errorbars_enabled_g1 = tk.BooleanVar(value=False)
        self.errorbars_enabled_g2 = tk.BooleanVar(value=False)
        self.fit_enabled_g1 = tk.BooleanVar(value=False)
        self.fit_enabled_g2 = tk.BooleanVar(value=False)
        self.fit_model_g1 = tk.StringVar(value="Linear")
        self.fit_model_g2 = tk.StringVar(value="Linear")
        self.link_x_axis_var = tk.BooleanVar(value=False)
        self._xlink_guard = False
        self._last_rendered_graph_data: dict[int, dict[str, Any]] = {1: {}, 2: {}}
        self._command_popup: tk.Toplevel | None = None
        self._command_search_var = tk.StringVar(value="")
        self._command_tree: ttk.Treeview | None = None
        self._command_item_to_name: dict[str, str] = {}
        self._command_preview: tk.Text | None = None
        self._control_popups: dict[str, tk.Toplevel] = {}
        self._lockin_popup_output_led: tk.Label | None = None

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
        results_left = ttk.Frame(self.parent, padding=SPACING["md"])
        results_left.grid(row=0, column=0, sticky="ns")

        # --- Middle column: script editor + controls ---
        results_middle = ttk.Frame(self.parent, padding=SPACING["md"])
        results_middle.grid(row=0, column=1, sticky="ns")

        # --- Right column: plots ---
        results_right = ttk.Frame(self.parent, width=620, height=600)
        results_right.grid(row=0, column=2, sticky="nw", padx=(SPACING["sm"], 0))
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
        gc.pack(fill="x", padx=5, pady=3)

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
            ("Purple", "#9467bd"),
            ("Brown", "#8c564b"),
            ("Pink", "#e377c2"),
        ]

        control_tabs = ttk.Notebook(gc)
        control_tabs.pack(fill="x", padx=2, pady=1)

        g1 = ttk.Frame(control_tabs)
        g2 = ttk.Frame(control_tabs)
        control_tabs.add(g1, text="Graph 1")
        control_tabs.add(g2, text="Graph 2")

        def _build_graph_tab(
            tab: ttk.Frame,
            graph_index: int,
            x_var: tk.StringVar,
            y_var: tk.StringVar,
            style_var: tk.StringVar,
            fit_enabled_var: tk.BooleanVar,
            fit_model_var: tk.StringVar,
            derivative_var: tk.BooleanVar,
            smooth_var: tk.BooleanVar,
            smooth_window_var: tk.IntVar,
            errorbar_var: tk.BooleanVar,
            channel_vars: dict[str, tk.BooleanVar],
        ) -> None:
            axes_row = ttk.Frame(tab)
            axes_row.pack(fill="x", pady=(2, 1))
            ttk.Label(axes_row, text="X:").pack(side="left")
            x_combo = ttk.Combobox(axes_row, textvariable=x_var, values=cols, width=25, state="readonly")
            x_combo.pack(side="left", padx=(2, 6))
            x_combo.bind("<<ComboboxSelected>>", lambda _e: self._schedule_plot_refresh(force=True))

            ttk.Label(axes_row, text="Y:").pack(side="left")
            y_combo = ttk.Combobox(axes_row, textvariable=y_var, values=cols, width=25, state="readonly")
            y_combo.pack(side="left", padx=(2, 0))
            y_combo.bind("<<ComboboxSelected>>", lambda _e: self._schedule_plot_refresh(force=True))

            style_row = ttk.Frame(tab)
            style_row.pack(fill="x", pady=(1, 1))
            ttk.Label(style_row, text="Style:").pack(side="left")
            style_combo = ttk.Combobox(
                style_row,
                textvariable=style_var,
                values=["Line", "Markers", "Line + Markers"],
                width=12,
                state="readonly",
            )
            style_combo.pack(side="left", padx=(2, 8))
            style_combo.bind("<<ComboboxSelected>>", lambda _e: self._schedule_plot_refresh(force=True))

            ttk.Checkbutton(
                style_row,
                text="Fit",
                variable=fit_enabled_var,
                command=lambda: self._schedule_plot_refresh(force=True),
            ).pack(side="left")
            fit_combo = ttk.Combobox(
                style_row,
                textvariable=fit_model_var,
                values=["Linear", "Poly2", "Poly3"],
                width=7,
                state="readonly",
            )
            fit_combo.pack(side="left", padx=(2, 8))
            fit_combo.bind("<<ComboboxSelected>>", lambda _e: self._schedule_plot_refresh(force=True))
            if graph_index == 1:
                self._fit_combo_g1 = fit_combo
            else:
                self._fit_combo_g2 = fit_combo

            ttk.Button(style_row, text="CSV", width=5, command=lambda: self._export_graph_csv(graph_index)).pack(side="right")
            ttk.Button(style_row, text="PNG", width=5, command=lambda: self._export_graph_png(graph_index)).pack(side="right", padx=(0, 4))

            color_row = ttk.Frame(tab)
            color_row.pack(fill="x", pady=(1, 1))
            ttk.Label(color_row, text="Color:").pack(side="left")
            swatch_row = ttk.Frame(color_row)
            swatch_row.pack(side="left", padx=(4, 0))

            color_buttons: dict[str, tk.Button] = {}
            for color_name, color_hex in color_squares:
                btn = tk.Button(
                    swatch_row,
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
                    command=lambda c=color_name: self._on_graph_color_selected(graph_index, c),
                )
                btn.pack(side="left", padx=1)
                color_buttons[color_name] = btn

            if graph_index == 1:
                self._graph1_color_buttons = color_buttons
            else:
                self._graph2_color_buttons = color_buttons

            options_row = ttk.Frame(tab)
            options_row.pack(fill="x", pady=(1, 1))
            ttk.Checkbutton(
                options_row,
                text="dY/dX",
                variable=derivative_var,
                command=lambda: self._schedule_plot_refresh(force=True),
            ).pack(side="left", padx=(0, 6))
            ttk.Checkbutton(
                options_row,
                text="Smooth",
                variable=smooth_var,
                command=lambda: self._schedule_plot_refresh(force=True),
            ).pack(side="left")
            ttk.Label(options_row, text="Win:").pack(side="left", padx=(6, 2))
            smooth_spin = ttk.Spinbox(
                options_row,
                from_=3,
                to=99,
                increment=2,
                textvariable=smooth_window_var,
                width=4,
                command=lambda: self._schedule_plot_refresh(force=True),
            )
            smooth_spin.pack(side="left")
            smooth_spin.bind("<FocusOut>", lambda _e: self._schedule_plot_refresh(force=True))

            errorbar_chk = ttk.Checkbutton(
                options_row,
                text="Show error bars",
                variable=errorbar_var,
                command=lambda: self._schedule_plot_refresh(force=True),
            )
            errorbar_chk.pack(side="left", padx=(8, 0))
            if graph_index == 1:
                self._errorbar_chk_g1 = errorbar_chk
            else:
                self._errorbar_chk_g2 = errorbar_chk

            channels_row = ttk.Frame(tab)
            channels_row.pack(fill="x", pady=(1, 2))
            ttk.Label(channels_row, text="Channels:").pack(side="left")
            channels_grid = ttk.Frame(channels_row)
            channels_grid.pack(side="left", padx=(6, 0))
            for idx, ch in enumerate(LOGICAL_CHANNELS):
                ttk.Checkbutton(
                    channels_grid,
                    text=ch.upper(),
                    variable=channel_vars[ch],
                    command=lambda: self._schedule_plot_refresh(force=True),
                ).grid(row=idx // 4, column=idx % 4, padx=2, pady=0, sticky="w")

        _build_graph_tab(
            g1,
            1,
            self.x1_var,
            self.y1_var,
            self.graph1_style,
            self.fit_enabled_g1,
            self.fit_model_g1,
            self.derivative_enabled_g1,
            self.smoothing_enabled_g1,
            self.smoothing_window_g1,
            self.errorbars_enabled_g1,
            self.channel_filter_vars_g1,
        )

        _build_graph_tab(
            g2,
            2,
            self.x2_var,
            self.y2_var,
            self.graph2_style,
            self.fit_enabled_g2,
            self.fit_model_g2,
            self.derivative_enabled_g2,
            self.smoothing_enabled_g2,
            self.smoothing_window_g2,
            self.errorbars_enabled_g2,
            self.channel_filter_vars_g2,
        )

        link_row = ttk.Frame(gc)
        link_row.pack(fill="x", padx=2, pady=(4, 2))
        ttk.Checkbutton(
            link_row,
            text="Link X-axis (Graph 1 <-> Graph 2)",
            variable=self.link_x_axis_var,
            command=self._on_link_x_axis_toggled,
        ).pack(side="left")

        iv_row = ttk.LabelFrame(parent, text="Data Plot Range")
        iv_row.pack(fill="x", padx=5, pady=(2, 4))
        ttk.Label(iv_row, text="Start:").pack(side="left", padx=(6, 2), pady=4)
        ValidatingEntry(iv_row, textvariable=self.data_plot_range_start_var, width=8, validator=make_int_validator()).pack(side="left", pady=4)
        ttk.Label(iv_row, text="End:").pack(side="left", padx=(10, 2), pady=4)
        ValidatingEntry(iv_row, textvariable=self.data_plot_range_end_var, width=8, validator=make_int_validator()).pack(side="left", pady=4)
        ttk.Button(iv_row, text="Prev", width=6, command=lambda: self._shift_iv_range(-1)).pack(side="left", padx=(10, 2), pady=4)
        ttk.Button(iv_row, text="Next", width=6, command=lambda: self._shift_iv_range(1)).pack(side="left", padx=2, pady=4)
        ttk.Button(iv_row, text="All", width=6, command=self._reset_iv_range).pack(side="left", padx=(10, 2), pady=4)

        self._update_graph_color_buttons()

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
    # Status panel  -  connection LEDs + synced readouts
    # ------------------------------------------------------------------
    def _build_status_panel(self, parent: ttk.Frame) -> None:
        # --- Activity LEDs (LockIn, Hall, Switch) ---
        ttk.Label(parent, text="Status Indicators:", style="SectionTitle.TLabel").pack(
            anchor="w", padx=5, pady=(10, 2)
        )

        indicator_row = StatusStrip(parent)
        indicator_row.pack(fill="x", padx=SPACING["sm"], pady=SPACING["xs"])
        indicator_row.add_indicator("lockin", "LockIn", with_separator=True)
        indicator_row.add_indicator("hall", "Hall Bar", with_separator=True)
        indicator_row.add_indicator("switch", "Switch", with_separator=False)
        self.activity_leds = indicator_row.leds

        ttk.Separator(parent, orient="horizontal").pack(fill="x", padx=SPACING["sm"], pady=SPACING["sm"])

        # --- System status with instrument readouts ---
        ttk.Label(parent, text="System Status:", style="SectionTitleLarge.TLabel").pack(
            anchor="w", padx=SPACING["sm"], pady=SPACING["xs"]
        )

        status_grid = ttk.Frame(parent)
        status_grid.pack(fill="x", padx=SPACING["sm"], pady=(SPACING["xs"], SPACING["sm"]))
        status_grid.grid_columnconfigure(0, weight=1)
        status_grid.grid_columnconfigure(1, weight=1)

        # Connection LEDs + readout values
        self.conn_leds: dict[str, tk.Label] = {}
        self.conn_labels: dict[str, ttk.Label] = {}

        def _make_section(parent, key, hdr_text, readout_defs, row_idx, col_idx, col_span=1):
            """Create a compact card section: LED + header + value labels."""
            card = tk.Frame(parent, bg=COLORS["bg_panel"], relief="groove", borderwidth=1)
            card.grid(
                row=row_idx,
                column=col_idx,
                columnspan=col_span,
                sticky="nsew",
                padx=(0, SPACING["sm"] if col_idx == 0 and col_span == 1 else 0),
                pady=(0, SPACING["sm"]),
            )

            hdr_row = tk.Frame(card, bg=COLORS["bg_panel"])
            hdr_row.pack(fill="x", padx=SPACING["sm"], pady=(SPACING["sm"], SPACING["xs"]))
            led = make_led(hdr_row)
            led.config(font=FONTS["subtitle"], bg=COLORS["bg_panel"])
            led.pack(side="left", padx=(0, 4))
            tk.Label(
                hdr_row,
                text=hdr_text,
                font=("Segoe UI", 10, "bold", "underline"),
                fg=COLORS["fg_primary"],
                bg=COLORS["bg_panel"],
            ).pack(side="left")
            self.conn_leds[key] = led

            labels = {}
            for name, text, fg_color in readout_defs:
                lbl = tk.Label(
                    card, text=text,
                    font=("Consolas", 10, "bold"), fg=fg_color,
                    bg=COLORS["bg_input"], relief="solid", borderwidth=1,
                    width=26, anchor="w",
                )
                lbl.pack(fill="x", padx=SPACING["sm"], pady=(0, SPACING["xs"]))
                labels[name] = lbl
            return labels

        # PPMS
        ppms = _make_section(status_grid, "dyna", "PPMS", [
            ("temp", "  Temp: N/A", "#664400"),
            ("field", "  Field: N/A", "#006600"),
            ("chamber", "  Chamber: N/A", "#225588"),
        ], 0, 0)
        self.results_dyna_temp = ppms["temp"]
        self.results_dyna_field = ppms["field"]
        self.results_dyna_chamber = ppms["chamber"]

        # Helmholtz
        helm = _make_section(status_grid, "helmholtz", "Helmholtz", [
            ("field", "  Field: N/A", "#006600"),
            ("ch_a", "  Ch A: N/A", "#003388"),
            ("ch_b", "  Ch B: N/A", "#664400"),
        ], 0, 1)
        self.results_helmholtz_field = helm["field"]
        self.results_helmholtz_ch_a = helm["ch_a"]
        self.results_helmholtz_ch_b = helm["ch_b"]

        # Hall Bar / K2450
        hall = _make_section(status_grid, "hall", "Hall Bar - K2450", [
            ("voltage", "  V: N/A", "#006600"),
            ("field", "  B: N/A", "#006600"),
            ("resistance", "  R: N/A", "#006600"),
            ("current", "  I(R): N/A", "#006600"),
        ], 1, 0)
        self.results_hall_voltage = hall["voltage"]
        self.results_hall_field = hall["field"]
        self.results_hall_resistance = hall["resistance"]
        self.results_hall_current = hall["current"]

        # Lock-In
        lockin = _make_section(status_grid, "lockin", "Lock-In", [
            ("x", "  X: N/A", "#663366"),
            ("y", "  Y: N/A", "#663366"),
            ("r", "  R: N/A", "#663366"),
            ("phase", "  θ: N/A", "#663366"),
            ("resistance", "  Resistance: N/A", "#663366"),
        ], 1, 1)
        self.results_lockin_x = lockin["x"]
        self.results_lockin_y = lockin["y"]
        self.results_lockin_r = lockin["r"]
        self.results_lockin_phase = lockin["phase"]
        self.results_lockin_resistance = lockin["resistance"]

        # Switch
        sw = _make_section(status_grid, "switch", "Switch", [
            ("status", "  Status: N/A", "#006600"),
        ], 2, 0, 2)
        self.results_switch_status = sw["status"]

        self._bind_results_popup_shortcuts()

    def _bind_double_click(self, widget: tk.Widget, callback: Callable[[], None]) -> None:
        widget.bind("<Double-Button-1>", lambda _event: callback())

    def _bind_results_popup_shortcuts(self) -> None:
        # PPMS
        self._bind_double_click(self.results_dyna_temp, self._open_ppms_temp_popup)
        self._bind_double_click(self.results_dyna_field, self._open_ppms_field_popup)
        self._bind_double_click(self.results_dyna_chamber, self._open_ppms_chamber_popup)

        # Helmholtz
        self._bind_double_click(self.results_helmholtz_field, self._open_helmholtz_popup)

        # Lock-In
        self._bind_double_click(self.results_lockin_x, self._open_lockin_popup)
        self._bind_double_click(self.results_lockin_y, self._open_lockin_popup)
        self._bind_double_click(self.results_lockin_r, self._open_lockin_popup)
        self._bind_double_click(self.results_lockin_phase, self._open_lockin_popup)
        self._bind_double_click(self.results_lockin_resistance, self._open_lockin_popup)

        # Hall bar
        self._bind_double_click(self.results_hall_voltage, self._open_hall_popup)
        self._bind_double_click(self.results_hall_field, self._open_hall_popup)
        self._bind_double_click(self.results_hall_resistance, self._open_hall_popup)
        self._bind_double_click(self.results_hall_current, self._open_hall_popup)

        # Switch
        self._bind_double_click(self.results_switch_status, self._open_switch_popup)

    def _center_popup_to_content(self, popup: tk.Toplevel, *, min_w: int = 280, min_h: int = 140) -> None:
        popup.update_idletasks()
        screen_w = popup.winfo_screenwidth()
        screen_h = popup.winfo_screenheight()
        req_w = popup.winfo_reqwidth() + 14
        req_h = popup.winfo_reqheight() + 14
        width = min(max(req_w, min_w), max(320, int(screen_w * 0.92)))
        height = min(max(req_h, min_h), max(220, int(screen_h * 0.92)))
        x = max(0, (screen_w - width) // 2)
        y = max(0, (screen_h - height) // 2)
        popup.geometry(f"{width}x{height}+{x}+{y}")

    def _close_control_popup(self, key: str) -> None:
        popup = self._control_popups.get(key)
        if popup is not None and popup.winfo_exists():
            popup.destroy()
        if key == "lockin":
            self._lockin_popup_output_led = None
        self._control_popups.pop(key, None)

    def _open_control_popup(
        self,
        key: str,
        title: str,
        builder: Callable[[ttk.Frame], None],
        *,
        min_w: int = 300,
        min_h: int = 180,
    ) -> None:
        existing = self._control_popups.get(key)
        if existing is not None and existing.winfo_exists():
            existing.attributes("-topmost", True)
            existing.lift()
            existing.focus_force()
            return

        popup = tk.Toplevel(self.app.root)
        popup.title(title)
        popup.transient(self.app.root)
        popup.attributes("-topmost", True)

        body = ttk.Frame(popup, padding=10)
        body.pack(fill="both", expand=True)
        builder(body)

        # Footer frame with close button (lower right)
        footer = ttk.Frame(popup, padding=(10, 5))
        footer.pack(fill="x")
        ttk.Button(footer, text="Close", command=lambda k=key: self._close_control_popup(k)).pack(side="right", padx=2)

        self._control_popups[key] = popup
        popup.protocol("WM_DELETE_WINDOW", lambda k=key: self._close_control_popup(k))
        self._center_popup_to_content(popup, min_w=min_w, min_h=min_h)
        popup.lift()
        popup.focus_force()

    def _open_ppms_temp_popup(self) -> None:
        self._open_control_popup("ppms_temp", "PPMS Temperature Control", self._build_ppms_temp_popup, min_w=380, min_h=190)

    def _open_ppms_field_popup(self) -> None:
        self._open_control_popup("ppms_field", "PPMS Field Control", self._build_ppms_field_popup, min_w=390, min_h=190)

    def _open_ppms_chamber_popup(self) -> None:
        self._open_control_popup("ppms_chamber", "PPMS Chamber Control", self._build_ppms_chamber_popup, min_w=360, min_h=160)

    def _open_helmholtz_popup(self) -> None:
        self._open_control_popup("helmholtz", "Helmholtz Setpoints", self._build_helmholtz_popup, min_w=650, min_h=200)

    def _open_lockin_popup(self) -> None:
        self._open_control_popup("lockin", "Lock-In Quick Control", self._build_lockin_popup, min_w=480, min_h=340)

    def _open_hall_popup(self) -> None:
        self._open_control_popup("hall", "Hall Bar Quick Control", self._build_hall_popup, min_w=490, min_h=300)

    def _open_switch_popup(self) -> None:
        self._open_control_popup("switch", "Switch Quick Control", self._build_switch_popup, min_w=600, min_h=280)

    def _build_ppms_temp_popup(self, parent: ttk.Frame) -> None:
        dyna = self.app.dyna_tab
        tf = ttk.LabelFrame(parent, text="Temperature")
        tf.pack(fill="x", padx=2, pady=2)

        ttk.Label(tf, text="Set Temp (K):").grid(row=0, column=0, sticky="w", padx=5, pady=2)
        ttk.Entry(tf, textvariable=dyna.set_temp, width=10).grid(row=0, column=1, padx=5, pady=2)

        ttk.Label(tf, text="Rate (K/min):").grid(row=1, column=0, sticky="w", padx=5, pady=2)
        ttk.Entry(tf, textvariable=dyna.temp_rate, width=10).grid(row=1, column=1, padx=5, pady=2)

        ttk.Label(tf, text="Approach:").grid(row=2, column=0, sticky="w", padx=5, pady=2)
        ttk.Combobox(
            tf,
            textvariable=dyna.temp_mode,
            values=["fast_settle", "no_overshoot"],
            state="readonly",
            width=14,
        ).grid(row=2, column=1, padx=5, pady=2, sticky="w")

        ttk.Button(tf, text="Set Temperature", command=dyna._on_set_temp).grid(
            row=3, column=0, columnspan=2, pady=6
        )

    def _build_ppms_field_popup(self, parent: ttk.Frame) -> None:
        dyna = self.app.dyna_tab
        ff = ttk.LabelFrame(parent, text="Field")
        ff.pack(fill="x", padx=2, pady=2)

        ttk.Label(ff, text="Set Field (Oe):").grid(row=0, column=0, sticky="w", padx=5, pady=2)
        ttk.Entry(ff, textvariable=dyna.set_field, width=10).grid(row=0, column=1, padx=5, pady=2)

        ttk.Label(ff, text="Rate (Oe/s):").grid(row=1, column=0, sticky="w", padx=5, pady=2)
        ttk.Entry(ff, textvariable=dyna.field_rate, width=10).grid(row=1, column=1, padx=5, pady=2)

        ttk.Label(ff, text="Approach:").grid(row=2, column=0, sticky="w", padx=5, pady=2)
        ttk.Combobox(
            ff,
            textvariable=dyna.field_mode,
            values=["linear", "no_overshoot", "oscillate"],
            state="readonly",
            width=14,
        ).grid(row=2, column=1, padx=5, pady=2, sticky="w")

        ttk.Button(ff, text="Set Field", command=dyna._on_set_field).grid(
            row=3, column=0, columnspan=2, pady=6
        )

    def _build_ppms_chamber_popup(self, parent: ttk.Frame) -> None:
        dyna = self.app.dyna_tab
        cf = ttk.LabelFrame(parent, text="Chamber")
        cf.pack(fill="x", padx=2, pady=2)

        ttk.Label(cf, text="Mode:").grid(row=0, column=0, sticky="w", padx=5, pady=2)
        ttk.Combobox(
            cf,
            textvariable=dyna.chamber_mode,
            values=list(dyna._CHAMBER_MODE_TO_CODE.keys()),
            state="readonly",
            width=18,
        ).grid(row=0, column=1, padx=5, pady=2, sticky="w")

        ttk.Button(cf, text="Set Chamber", command=dyna._on_set_chamber).grid(
            row=1, column=0, columnspan=2, pady=6
        )

    def _build_helmholtz_popup(self, parent: ttk.Frame) -> None:
        helm = self.app.helmholtz_tab
        sp = ttk.LabelFrame(parent, text="Setpoints")
        sp.pack(fill="x", padx=2, pady=2)

        ttk.Label(sp, text="Set Current Total (A):").grid(row=0, column=0, sticky="w", padx=5, pady=2)
        ttk.Entry(sp, textvariable=helm.set_current, width=12).grid(row=0, column=1, padx=5, pady=2)
        ttk.Label(sp, text="A").grid(row=0, column=2, sticky="w", padx=2)

        ttk.Label(sp, text="Set Field (G):").grid(row=0, column=3, sticky="w", padx=(14, 5), pady=2)
        ttk.Entry(sp, textvariable=helm.set_field_gauss, width=12).grid(row=0, column=4, padx=5, pady=2)
        ttk.Label(sp, text="G").grid(row=0, column=5, sticky="w", padx=2)

        ttk.Label(sp, text="Compliance (V):").grid(row=1, column=0, sticky="w", padx=5, pady=2)
        ttk.Entry(sp, textvariable=helm.compliance_voltage, width=12).grid(row=1, column=1, padx=5, pady=2)
        ttk.Label(sp, text="V").grid(row=1, column=2, sticky="w", padx=2)

        ttk.Label(sp, text="Ramp Rate (mA/s):").grid(row=2, column=0, sticky="w", padx=5, pady=2)
        ttk.Entry(sp, textvariable=helm.ramp_rate, width=12).grid(row=2, column=1, padx=5, pady=2)
        ttk.Label(sp, text="mA/s").grid(row=2, column=2, sticky="w", padx=2)

        ttk.Label(sp, text="Field Ramp Rate (G/s):").grid(row=2, column=3, sticky="w", padx=(14, 5), pady=2)
        ttk.Entry(sp, textvariable=helm.field_ramp_rate, width=12).grid(row=2, column=4, padx=5, pady=2)
        ttk.Label(sp, text="G/s").grid(row=2, column=5, sticky="w", padx=2)

        btn = ttk.Frame(parent)
        btn.pack(fill="x", padx=2, pady=(6, 2))
        ttk.Button(btn, text="Enable Output", command=helm._on_enable).pack(side="left", padx=2)
        ttk.Button(btn, text="Disable Output", command=helm._on_disable).pack(side="left", padx=2)
        ttk.Button(btn, text="Set Current", command=helm._on_set_current).pack(side="left", padx=2)
        ttk.Button(btn, text="Set Field", command=helm._on_set_field_from_gauss).pack(side="left", padx=2)
        ttk.Button(btn, text="Update", command=helm._on_set_current).pack(side="left", padx=2)
        ttk.Button(btn, text="Reset Plot", command=helm._on_reset_plot).pack(side="left", padx=2)

    def _build_lockin_popup(self, parent: ttk.Frame) -> None:
        lockin = self.app.lockin_tab

        sf = ttk.LabelFrame(parent, text="Lock-In Settings")
        sf.pack(fill="x", padx=2, pady=2)

        ttk.Label(sf, text="Frequency (Hz):").grid(row=0, column=0, sticky="w", padx=5, pady=2)
        ttk.Entry(sf, textvariable=lockin.lockin_frequency, width=10).grid(row=0, column=1, padx=5)
        ttk.Button(sf, text="Set", command=lockin._set_frequency, width=5).grid(row=0, column=2)

        ttk.Label(sf, text="Time Constant:").grid(row=1, column=0, sticky="w", padx=5, pady=2)
        tc_label = ttk.Label(sf, text=lockin._tc_text())
        tc_label.grid(row=1, column=1, padx=5)
        tc_btns = ttk.Frame(sf)
        tc_btns.grid(row=1, column=2)

        def _tc_down() -> None:
            lockin._tc_down()
            tc_label.configure(text=lockin._tc_text())

        def _tc_up() -> None:
            lockin._tc_up()
            tc_label.configure(text=lockin._tc_text())

        def _tc_set() -> None:
            lockin._set_tc()
            tc_label.configure(text=lockin._tc_text())

        ttk.Button(tc_btns, text="◄", width=3, command=_tc_down).pack(side="left")
        ttk.Button(tc_btns, text="►", width=3, command=_tc_up).pack(side="left")
        ttk.Button(tc_btns, text="Set", width=4, command=_tc_set).pack(side="left")

        ttk.Label(sf, text="Sensitivity:").grid(row=2, column=0, sticky="w", padx=5, pady=2)
        sens_label = ttk.Label(sf, text=lockin._sens_text())
        sens_label.grid(row=2, column=1, padx=5)
        sens_btns = ttk.Frame(sf)
        sens_btns.grid(row=2, column=2)

        def _sens_down() -> None:
            lockin._sens_down()
            sens_label.configure(text=lockin._sens_text())

        def _sens_up() -> None:
            lockin._sens_up()
            sens_label.configure(text=lockin._sens_text())

        def _sens_set() -> None:
            lockin._set_sens()
            sens_label.configure(text=lockin._sens_text())

        ttk.Button(sens_btns, text="◄", width=3, command=_sens_down).pack(side="left")
        ttk.Button(sens_btns, text="►", width=3, command=_sens_up).pack(side="left")
        ttk.Button(sens_btns, text="Set", width=4, command=_sens_set).pack(side="left")

        ttk.Label(sf, text="Filter (dB/oct):").grid(row=3, column=0, sticky="w", padx=5, pady=2)
        ttk.OptionMenu(sf, lockin.lockin_filter_slope, lockin.lockin_filter_slope.get(), "6", "12", "18", "24").grid(
            row=3, column=1, padx=5, sticky="w"
        )
        ttk.Button(sf, text="Set", command=lockin._set_filter, width=5).grid(row=3, column=2)

        ttk.Label(sf, text="Output Current (A):").grid(row=4, column=0, sticky="w", padx=5, pady=2)
        ValidatingEntry(
            sf,
            textvariable=lockin.lockin_output_current,
            width=10,
            validator=make_float_validator(0.0, 1.0),
        ).grid(row=4, column=1, padx=5)
        ttk.Button(sf, text="Set", command=lockin._set_current, width=5).grid(row=4, column=2)

        ttk.Label(sf, text="R_lockin:").grid(row=5, column=0, sticky="w", padx=5, pady=2)
        ttk.Combobox(
            sf,
            textvariable=lockin.lockin_r_lockin_idx,
            values=list(R_LOCKIN_OPTIONS.keys()),
            width=13,
            state="readonly",
        ).grid(row=5, column=1, padx=5, sticky="w")

        ttk.Label(sf, text="Averaging:").grid(row=6, column=0, sticky="w", padx=5, pady=2)
        ValidatingEntry(
            sf,
            textvariable=lockin.lockin_averaging,
            width=10,
            validator=make_float_validator(1.0, 5000.0),
        ).grid(row=6, column=1, padx=5)

        ttk.Label(sf, text="Input Shield:").grid(row=7, column=0, sticky="w", padx=5, pady=2)
        ttk.Label(sf, textvariable=lockin.lockin_input_shield_state).grid(row=7, column=1, padx=5, sticky="w")
        ttk.Button(sf, text="Toggle", width=7, command=lockin._toggle_input_shield).grid(row=7, column=2, padx=5, sticky="w")

        uf = ttk.LabelFrame(parent, text="Utilities")
        uf.pack(fill="x", padx=2, pady=4)
        ttk.Button(uf, text="Auto Gain", command=lockin._auto_gain).pack(side="left", padx=5, pady=2)
        ttk.Button(uf, text="Auto Phase", command=lockin._auto_phase).pack(side="left", padx=5, pady=2)
        ttk.Button(uf, text="Auto Reserve", command=lockin._auto_reserve).pack(side="left", padx=5, pady=2)

        mf = ttk.LabelFrame(parent, text="Measurement")
        mf.pack(fill="x", padx=2, pady=2)
        lockin_measure_btn = ttk.Button(mf, text="Measure", command=lockin._on_measure)
        lockin_measure_btn.pack(side="left", padx=5, pady=2)
        lockin.register_measure_button(lockin_measure_btn)
        ttk.Button(mf, text="Apply Settings", command=lockin._on_apply_settings).pack(side="left", padx=5, pady=2)
        ttk.Label(mf, text="Sine Output:").pack(side="left", padx=(10, 4))
        self._lockin_popup_output_led = make_led(mf)
        self._lockin_popup_output_led.pack(side="left", padx=2)
        
        # Sync LED with current output voltage (same logic as main tab)
        try:
            output_voltage: float | None = None
            lockin_inst = self.app.bus.get_raw(INST_LOCKIN)
            if lockin_inst is not None:
                if hasattr(lockin_inst, "get_reference_amplitude"):
                    output_voltage = float(self.app.bus.execute(INST_LOCKIN, "get_reference_amplitude"))
        except Exception:
            output_voltage = None
        
        if output_voltage is None:
            set_led(self._lockin_popup_output_led, False)
            return

        threshold = max(float(lockin._idle_output_voltage), 0.0) + 1e-6
        set_led(self._lockin_popup_output_led, output_voltage > threshold)

    def _build_hall_popup(self, parent: ttk.Frame) -> None:
        hall = self.app.hall_tab

        sf = ttk.LabelFrame(parent, text="Measurement Settings")
        sf.pack(fill="x", padx=2, pady=2)

        ttk.Label(sf, text="Hall Bar Preset:").grid(row=0, column=0, sticky="w", padx=5, pady=2)
        preset_values = [
            *list(hall._HALL_BAR_PRESETS_V_PER_G.keys()),
            hall._CUSTOM_PRESET_NAME,
        ]
        preset_combo = ttk.Combobox(
            sf,
            textvariable=hall.k2450_hall_bar,
            values=preset_values,
            state="readonly",
            width=22,
        )
        preset_combo.grid(row=0, column=1, padx=5, pady=2, sticky="w")
        preset_combo.bind("<<ComboboxSelected>>", hall._on_hall_bar_selected)

        ttk.Label(sf, text="Preset V/G:").grid(row=1, column=0, sticky="w", padx=5, pady=2)
        ttk.Label(sf, textvariable=hall.k2450_hall_v_per_g).grid(row=1, column=1, sticky="w", padx=5, pady=2)

        entries = [
            ("Current (mA):", hall.k2450_current, make_float_validator(0.0, 105.0)),
            ("NPLC:", hall.k2450_nplc, make_float_validator(0.01, 20.0)),
            ("Compliance (V):", hall.k2450_compliance_v, make_float_validator(0.0, 210.0)),
            ("Filter Count:", hall.k2450_filter_count, make_float_validator(1.0, 100.0)),
            ("TBM delay (s):", hall.k2450_tbm, make_float_validator(0.0, 10.0)),
            ("Hall Offset (V):", hall.k2450_hall_offset, make_float_validator(-5.0, 5.0)),
            ("V→Gauss (G/V):", hall.k2450_hall_v2gauss, make_float_validator(-1e7, 1e7)),
        ]
        for idx, (label, var, validator) in enumerate(entries, start=2):
            ttk.Label(sf, text=label).grid(row=idx, column=0, sticky="w", padx=5, pady=2)
            ValidatingEntry(sf, textvariable=var, width=12, validator=validator).grid(row=idx, column=1, padx=5, pady=2)

        vr_row = len(entries) + 2
        ttk.Label(sf, text="Voltage Range:").grid(row=vr_row, column=0, sticky="w", padx=5, pady=2)
        ttk.OptionMenu(
            sf,
            hall.k2450_voltage_range,
            hall.k2450_voltage_range.get(),
            "auto",
            "0.02",
            "0.2",
            "2",
            "20",
            "200",
        ).grid(row=vr_row, column=1, padx=5, sticky="w")

        bf = ttk.LabelFrame(parent, text="Hall Measurement")
        bf.pack(fill="x", padx=2, pady=4)
        hall_measure_btn = ttk.Button(bf, text="Measure Hall", command=hall._on_measure)
        hall_measure_btn.pack(side="left", padx=5, pady=2)
        hall.register_measure_button(hall_measure_btn)
        ttk.Button(bf, text="Set Offset...", command=hall._open_offset_popup).pack(side="left", padx=5, pady=2)
        ttk.Button(bf, text="Enable Source", command=hall._on_enable_source).pack(side="left", padx=5, pady=2)
        ttk.Button(bf, text="Disable Source", command=hall._on_disable_source).pack(side="left", padx=5, pady=2)

        aux = ttk.LabelFrame(parent, text="Resistance / IV")
        aux.pack(fill="x", padx=2, pady=2)
        ttk.Label(aux, text="R Current (mA):").grid(row=0, column=0, sticky="w", padx=5, pady=2)
        ttk.Entry(aux, textvariable=hall.k2450_resistance_current_mA, width=10).grid(row=0, column=1, padx=5, pady=2)
        ttk.Label(aux, text="R Compliance (V):").grid(row=0, column=2, sticky="w", padx=5, pady=2)
        ttk.Entry(aux, textvariable=hall.k2450_resistance_compliance_v, width=10).grid(row=0, column=3, padx=5, pady=2)
        ttk.Label(aux, text="R NPLC:").grid(row=1, column=0, sticky="w", padx=5, pady=2)
        ttk.Entry(aux, textvariable=hall.k2450_resistance_nplc, width=10).grid(row=1, column=1, padx=5, pady=2)
        ttk.Label(aux, text="R Settle (s):").grid(row=1, column=2, sticky="w", padx=5, pady=2)
        ttk.Entry(aux, textvariable=hall.k2450_resistance_settle, width=10).grid(row=1, column=3, padx=5, pady=2)
        ttk.Button(aux, text="Measure Resistance", command=hall._on_measure_resistance).grid(row=1, column=4, padx=5, pady=2)

        ttk.Label(aux, text="IV Shape:").grid(row=2, column=0, sticky="w", padx=5, pady=2)
        ttk.OptionMenu(
            aux,
            hall.k2450_iv_shape,
            hall.k2450_iv_shape.get(),
            "start_min_max_start",
            "start_max_min_start",
            "start_min_start",
            "start_max_start",
        ).grid(row=2, column=1, sticky="w", padx=5, pady=2)
        ttk.Label(aux, text="Start:").grid(row=2, column=2, sticky="w", padx=5, pady=2)
        ttk.Entry(aux, textvariable=hall.k2450_iv_start, width=10).grid(row=2, column=3, padx=5, pady=2)
        ttk.Label(aux, text="Min:").grid(row=3, column=0, sticky="w", padx=5, pady=2)
        ttk.Entry(aux, textvariable=hall.k2450_iv_min, width=10).grid(row=3, column=1, padx=5, pady=2)
        ttk.Label(aux, text="Max:").grid(row=3, column=2, sticky="w", padx=5, pady=2)
        ttk.Entry(aux, textvariable=hall.k2450_iv_max, width=10).grid(row=3, column=3, padx=5, pady=2)
        ttk.Label(aux, text="Step:").grid(row=4, column=0, sticky="w", padx=5, pady=2)
        ttk.Entry(aux, textvariable=hall.k2450_iv_step, width=10).grid(row=4, column=1, padx=5, pady=2)
        ttk.Label(aux, text="IV Compliance:").grid(row=4, column=2, sticky="w", padx=5, pady=2)
        ttk.Entry(aux, textvariable=hall.k2450_iv_compliance, width=10).grid(row=4, column=3, padx=5, pady=2)
        ttk.Label(aux, text="IV NPLC:").grid(row=5, column=0, sticky="w", padx=5, pady=2)
        ttk.Entry(aux, textvariable=hall.k2450_iv_nplc, width=10).grid(row=5, column=1, padx=5, pady=2)
        ttk.Label(aux, text="IV Settle (s):").grid(row=5, column=2, sticky="w", padx=5, pady=2)
        ttk.Entry(aux, textvariable=hall.k2450_iv_settle, width=10).grid(row=5, column=3, padx=5, pady=2)
        ttk.Checkbutton(aux, text="Ramp to start", variable=hall.k2450_iv_ramp_to_start).grid(row=6, column=0, columnspan=2, sticky="w", padx=5, pady=2)
        ttk.Button(aux, text="Measure IV Curve", command=hall._on_measure_iv_curve).grid(row=6, column=4, padx=5, pady=2)

    def _build_switch_popup(self, parent: ttk.Frame) -> None:
        switch = self.app.switch_tab

        cf = ttk.LabelFrame(parent, text="Channel Configuration")
        cf.pack(fill="x", padx=2, pady=2)

        headers = ["Channel", "I+", "V+", "V-", "I-"]
        for col, header in enumerate(headers):
            ttk.Label(cf, text=header, style="SectionTitle.TLabel").grid(
                row=0, column=col, padx=5, pady=2
            )

        for row_idx, ch in enumerate(self.app.channels, start=1):
            ttk.Label(cf, text=ch.upper()).grid(row=row_idx, column=0, padx=5, pady=2)
            for col_idx, pin in enumerate(["I+", "V+", "V-", "I-"], start=1):
                ttk.Spinbox(
                    cf,
                    from_=1,
                    to=SWITCH_PIN_MAX,
                    textvariable=self.app.channel_configs[ch][pin],
                    width=5,
                ).grid(row=row_idx, column=col_idx, padx=5, pady=2)

        ctrl = ttk.LabelFrame(parent, text="Controls")
        ctrl.pack(fill="x", padx=2, pady=4)
        ttk.Label(ctrl, text="Channel:").pack(side="left", padx=5)
        ttk.Combobox(
            ctrl,
            textvariable=switch.close_channel_var,
            values=self.app.channels,
            state="readonly",
            width=8,
        ).pack(side="left", padx=5)
        ttk.Button(ctrl, text="Open All", command=switch._on_open_all).pack(side="left", padx=5)
        ttk.Button(ctrl, text="Close Channel", command=switch._on_close).pack(side="left", padx=5)

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
        self._apply_plot_grid(self.ax1)
        self._apply_plot_grid(self.ax2)
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
            ttk.Button(toolbar, text="Autoscale", command=self._autoscale_all_graphs, width=10).pack(side="left", padx=(6, 0))
            pass  # grid button removed
        except Exception:
            pass

        self.ax1.callbacks.connect("xlim_changed", lambda _ax: self._on_xlim_changed(1))
        self.ax2.callbacks.connect("xlim_changed", lambda _ax: self._on_xlim_changed(2))

    def refresh_plots(self) -> None:
        """Refresh both plots from the data manager results buffer."""
        if self.canvas is None:
            return
        results = self._apply_iv_range_filter(list(self.app.data_mgr.get_results()))
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
            self._apply_plot_grid(self.ax1)
            self._apply_plot_grid(self.ax2)
            self._last_rendered_graph_data = {1: {}, 2: {}}
            self._set_errorbar_control_state(1, False)
            self._set_errorbar_control_state(2, False)
            self.fig.tight_layout(pad=3.0)
            self.canvas.draw_idle()
            self._last_plot_refresh_ts = time.time()
            return

        for graph_index, ax, xvar, yvar, style_var, color_var, derivative_var, smooth_var, smooth_win_var, err_var, fit_var, fit_model_var in [
            (
                1,
                self.ax1,
                self.x1_var,
                self.y1_var,
                self.graph1_style,
                self.graph1_color,
                self.derivative_enabled_g1,
                self.smoothing_enabled_g1,
                self.smoothing_window_g1,
                self.errorbars_enabled_g1,
                self.fit_enabled_g1,
                self.fit_model_g1,
            ),
            (
                2,
                self.ax2,
                self.x2_var,
                self.y2_var,
                self.graph2_style,
                self.graph2_color,
                self.derivative_enabled_g2,
                self.smoothing_enabled_g2,
                self.smoothing_window_g2,
                self.errorbars_enabled_g2,
                self.fit_enabled_g2,
                self.fit_model_g2,
            ),
        ]:
            ax.clear()
            selected_channels = self._selected_channels_for_graph(graph_index)
            x_label = xvar.get()
            y_label = yvar.get()
            x_key = self._resolve_plot_key(x_label)
            y_key = self._resolve_plot_key(y_label)
            style = style_var.get()
            color = self._resolve_plot_color(color_var.get())
            derivative_enabled = bool(derivative_var.get())
            smoothing_enabled = bool(smooth_var.get())
            smoothing_window = self._normalize_smoothing_window(smooth_win_var)
            fit_enabled = bool(fit_var.get()) and HAS_NUMPY

            marker = "o" if "Marker" in style else ""
            linestyle = "-" if "Line" in style else "None"

            has_error_data = self._graph_has_error_data(results, y_key, selected_channels)
            self._set_errorbar_control_state(graph_index, has_error_data and not derivative_enabled)
            show_errorbars = bool(err_var.get()) and has_error_data and not derivative_enabled

            plotted_series = 0
            graph_series: list[dict[str, Any]] = []
            render_channels: list[str | None]
            if len(selected_channels) > 1:
                render_channels = list(selected_channels) + [None]
            else:
                render_channels = [selected_channels[0]]
            for channel in render_channels:
                include_generic = not (len(selected_channels) > 1 and channel is not None)
                xs, ys, yerrs = self._collect_series_data(results, x_key, y_key, channel, include_generic=include_generic)
                if len(xs) < 1:
                    continue

                if smoothing_enabled:
                    ys = self._smooth_series(ys, smoothing_window)

                if derivative_enabled:
                    xs, ys = self._derive_series(xs, ys)
                    yerrs = []

                if not xs or not ys:
                    continue

                plotted_series += 1
                series_color = self._channel_colors.get(channel, color) if (len(selected_channels) > 1 and channel is not None) else color
                label = f"Ch {channel.upper()}" if channel is not None else "Global"
                yerr_plot = [math.nan if e is None else e for e in yerrs] if show_errorbars else None

                if show_errorbars and yerr_plot and any(not math.isnan(v) for v in yerr_plot):
                    ax.errorbar(
                        xs,
                        ys,
                        yerr=yerr_plot,
                        marker=(marker or None),
                        linestyle=linestyle,
                        markersize=3,
                        color=series_color,
                        capsize=3,
                        label=label,
                    )
                else:
                    ax.plot(
                        xs,
                        ys,
                        marker=marker,
                        linestyle=linestyle,
                        markersize=3,
                        color=series_color,
                        label=label,
                    )

                fit_curve: list[float] | None = None
                fit_label: str | None = None
                if fit_enabled:
                    fit_curve, fit_label = self._compute_fit_curve(xs, ys, str(fit_model_var.get()))
                    if fit_curve is not None and fit_label is not None:
                        ax.plot(xs, fit_curve, linestyle="--", linewidth=1.2, color=series_color, alpha=0.9, label=f"{label} fit: {fit_label}")

                graph_series.append(
                    {
                        "channel": "global" if channel is None else channel,
                        "x": list(xs),
                        "y": list(ys),
                        "yerr": list(yerrs),
                        "fit_y": list(fit_curve) if fit_curve is not None else [],
                        "fit_label": fit_label,
                    }
                )

            self._last_rendered_graph_data[graph_index] = {
                "x_label": x_label,
                "y_label": y_label,
                "is_derivative": derivative_enabled,
                "series": graph_series,
            }

            ax.set_xlabel(x_label)
            if derivative_enabled:
                ax.set_ylabel(f"d({y_label})/d({x_label})")
            else:
                ax.set_ylabel(y_label)
            ax.tick_params(axis="both", which="both", direction="in")
            self._apply_plot_grid(ax)
            if plotted_series > 0 and (len(selected_channels) > 1 or fit_enabled):
                ax.legend(loc="best", fontsize=8)

        if self.link_x_axis_var.get():
            self._sync_x_limits_from(1)

        self.fig.tight_layout(pad=3.0)
        self.canvas.draw_idle()
        self._last_plot_refresh_ts = time.time()

    def _reset_iv_range(self) -> None:
        results_count = len(self.app.data_mgr.get_results())
        self.data_plot_range_start_var.set(1)
        self.data_plot_range_end_var.set(max(1, results_count))
        self._schedule_plot_refresh(force=True)

    def _current_iv_range(self) -> tuple[int, int] | None:
        try:
            start = int(self.data_plot_range_start_var.get())
            end = int(self.data_plot_range_end_var.get())
        except Exception:
            return None
        if start > end:
            return None
        return start, end

    def _shift_iv_range(self, direction: int) -> None:
        bounds = self._current_iv_range()
        if bounds is None:
            return
        start, end = bounds
        span = max(1, end - start + 1)
        start = max(1, start + (span * int(direction)))
        end = start + span - 1
        self.data_plot_range_start_var.set(start)
        self.data_plot_range_end_var.set(end)
        self._schedule_plot_refresh(force=True)

    def _apply_iv_range_filter(self, results: list[dict[str, Any]]) -> list[dict[str, Any]]:
        bounds = self._current_iv_range()
        if bounds is None:
            return results

        start, end = bounds
        filtered: list[dict[str, Any]] = []
        for idx, row in enumerate(results, start=1):
            if start <= idx <= end:
                filtered.append(row)
        return filtered

    def _normalize_smoothing_window(self, window_var: tk.IntVar) -> int:
        raw = int(window_var.get()) if window_var.get() else 5
        if raw < 3:
            raw = 3
        if raw % 2 == 0:
            raw += 1
        window_var.set(raw)
        return raw

    def _smooth_series(self, values: list[float], window: int) -> list[float]:
        if len(values) < 3:
            return list(values)
        radius = max(1, window // 2)
        out: list[float] = []
        for idx in range(len(values)):
            lo = max(0, idx - radius)
            hi = min(len(values), idx + radius + 1)
            seg = values[lo:hi]
            out.append(sum(seg) / max(1, len(seg)))
        return out

    def _derive_series(self, xs: list[float], ys: list[float]) -> tuple[list[float], list[float]]:
        if len(xs) < 2 or len(ys) < 2:
            return [], []
        d_x: list[float] = []
        d_y: list[float] = []
        for idx in range(len(xs) - 1):
            dx = xs[idx + 1] - xs[idx]
            if abs(dx) < 1e-15:
                continue
            d_x.append(xs[idx])
            d_y.append((ys[idx + 1] - ys[idx]) / dx)
        return d_x, d_y

    def _compute_fit_curve(self, xs: list[float], ys: list[float], model: str) -> tuple[list[float] | None, str | None]:
        if not HAS_NUMPY:
            return None, None
        degree_map = {"Linear": 1, "Poly2": 2, "Poly3": 3}
        degree = degree_map.get(model, 1)
        if len(xs) < degree + 1:
            return None, None

        x_arr = np.asarray(xs, dtype=float)
        y_arr = np.asarray(ys, dtype=float)
        coeffs = np.polyfit(x_arr, y_arr, degree)
        fit_arr = np.polyval(coeffs, x_arr)

        y_mean = float(np.mean(y_arr))
        ss_res = float(np.sum((y_arr - fit_arr) ** 2))
        ss_tot = float(np.sum((y_arr - y_mean) ** 2))
        r2 = 1.0 - (ss_res / ss_tot) if ss_tot > 1e-15 else 1.0

        if degree == 1:
            text = f"y={coeffs[0]:.3g}x+{coeffs[1]:.3g}, R2={r2:.3f}"
        elif degree == 2:
            text = f"y={coeffs[0]:.3g}x^2+{coeffs[1]:.3g}x+{coeffs[2]:.3g}, R2={r2:.3f}"
        else:
            text = (
                f"y={coeffs[0]:.3g}x^3+{coeffs[1]:.3g}x^2+{coeffs[2]:.3g}x+{coeffs[3]:.3g}, "
                f"R2={r2:.3f}"
            )

        return fit_arr.tolist(), text

    def _error_key_for_y_key(self, y_key: str) -> str | None:
        canonical_map = {
            "Hall Voltage": "Hall Voltage Error",
            "Hall_Field": "Hall Field Error",
            "Hall Field": "Hall Field Error",
            "LockIn_X": "LockIn_X_Error",
            "LockIn_Y": "LockIn_Y_Error",
            "LockIn_R": "LockIn_R_Error",
            "LockIn_Theta": "LockIn_Theta_Error",
            "Sample_Resistance": "Sample_Resistance_Error",
        }
        if y_key in canonical_map:
            return canonical_map[y_key]
        if y_key.endswith("_Error"):
            return None
        if y_key.endswith("(V)"):
            return y_key.replace("(V)", "_Error(V)")
        if y_key.endswith("(G)"):
            return y_key.replace("(G)", "_Error(G)")
        if y_key.endswith("(Ohm)"):
            return y_key.replace("(Ohm)", "_Error(Ohm)")
        if y_key.endswith("(deg)"):
            return y_key.replace("(deg)", "_Error(deg)")
        return f"{y_key}_Error"

    def _collect_series_data(
        self,
        results: list[dict[str, Any]],
        x_key: str,
        y_key: str,
        channel: str | None,
        *,
        include_generic: bool,
    ) -> tuple[list[float], list[float], list[float | None]]:
        xs: list[float] = []
        ys: list[float] = []
        yerrs: list[float | None] = []
        err_key = self._error_key_for_y_key(y_key)

        for row in results:
            row_channel = self._extract_row_channel(row)
            if channel is None:
                if row_channel is not None:
                    continue
            elif row_channel is None and not include_generic:
                continue
            elif row_channel is not None and row_channel != channel:
                continue

            x_val = self._row_value_for_channel(row, x_key, channel)
            y_val = self._row_value_for_channel(row, y_key, channel)
            x_num = self._to_numeric(x_val)
            y_num = self._to_numeric(y_val)
            if x_num is None or y_num is None:
                continue
            xs.append(x_num)
            ys.append(y_num)

            err_num: float | None = None
            if err_key is not None:
                err_val = self._row_value_for_channel(row, err_key, channel)
                err_num = self._to_numeric(err_val)
            yerrs.append(err_num)

        return xs, ys, yerrs

    def _graph_has_error_data(self, results: list[dict[str, Any]], y_key: str, channels: list[str]) -> bool:
        err_key = self._error_key_for_y_key(y_key)
        if err_key is None:
            return False
        candidates: list[str | None] = list(channels)
        if len(channels) > 1:
            candidates.append(None)
        for ch in candidates:
            include_generic = not (len(channels) > 1 and ch is not None)
            for row in results:
                row_channel = self._extract_row_channel(row)
                if ch is None:
                    if row_channel is not None:
                        continue
                elif row_channel is None and not include_generic:
                    continue
                elif row_channel is not None and row_channel != ch:
                    continue
                err_val = self._row_value_for_channel(row, err_key, ch)
                if self._to_numeric(err_val) is not None:
                    return True
        return False

    def _set_errorbar_control_state(self, graph_index: int, enabled: bool) -> None:
        chk = self._errorbar_chk_g1 if graph_index == 1 else self._errorbar_chk_g2
        var = self.errorbars_enabled_g1 if graph_index == 1 else self.errorbars_enabled_g2
        if chk is None:
            return
        chk.configure(state=("normal" if enabled else "disabled"))
        if not enabled:
            var.set(False)

    def _on_link_x_axis_toggled(self) -> None:
        if self.link_x_axis_var.get():
            self._sync_x_limits_from(1)

    def _autoscale_graph(self, graph_index: int) -> None:
        if self.canvas is None:
            return
        ax = self.ax1 if graph_index == 1 else self.ax2
        ax.relim(visible_only=True)
        ax.autoscale_view()
        if self.link_x_axis_var.get():
            self._sync_x_limits_from(graph_index)
        self.canvas.draw_idle()

    def _autoscale_all_graphs(self) -> None:
        if self.canvas is None:
            return
        self.ax1.set_autoscalex_on(True)
        self.ax1.set_autoscaley_on(True)
        self.ax2.set_autoscalex_on(True)
        self.ax2.set_autoscaley_on(True)
        self.ax1.relim(visible_only=True)
        self.ax2.relim(visible_only=True)
        self.ax1.autoscale_view()
        self.ax2.autoscale_view()
        if self.link_x_axis_var.get():
            self._sync_x_limits_from(1)
        self.canvas.draw_idle()

    def _apply_plot_grid(self, ax) -> None:
        ax.grid(self._plots_grid_enabled, which="both", linestyle="--", linewidth=0.6, alpha=0.35)

    def _refresh_plot_grid_button_label(self) -> None:
        if self._plots_grid_button is None or not self._plots_grid_button.winfo_exists():
            return
        self._plots_grid_button.configure(text=("Grid Off" if self._plots_grid_enabled else "Grid On"))

    def _toggle_plots_grid(self) -> None:
        if self.canvas is None:
            return
        self._plots_grid_enabled = not self._plots_grid_enabled
        self._apply_plot_grid(self.ax1)
        self._apply_plot_grid(self.ax2)
        self._refresh_plot_grid_button_label()
        self.canvas.draw_idle()

    def _on_xlim_changed(self, source_graph_index: int) -> None:
        if not self.link_x_axis_var.get() or self._xlink_guard:
            return
        self._sync_x_limits_from(source_graph_index)

    def _sync_x_limits_from(self, source_graph_index: int) -> None:
        if not HAS_MATPLOTLIB or self.canvas is None:
            return
        source_ax = self.ax1 if source_graph_index == 1 else self.ax2
        target_ax = self.ax2 if source_graph_index == 1 else self.ax1
        try:
            self._xlink_guard = True
            target_ax.set_xlim(source_ax.get_xlim())
            self.canvas.draw_idle()
        finally:
            self._xlink_guard = False

    def _export_graph_png(self, graph_index: int) -> None:
        if self.canvas is None:
            return
        ax = self.ax1 if graph_index == 1 else self.ax2
        path = filedialog.asksaveasfilename(
            title=f"Export Graph {graph_index} PNG",
            defaultextension=".png",
            filetypes=[("PNG image", "*.png")],
        )
        if not path:
            return
        try:
            self.canvas.draw()
            renderer = self.fig.canvas.get_renderer()
            bbox = ax.get_tightbbox(renderer).expanded(1.04, 1.08)
            bbox_inches = bbox.transformed(self.fig.dpi_scale_trans.inverted())
            self.fig.savefig(path, dpi=300, bbox_inches=bbox_inches)
            self.app.ui_bus.post_log(f"Graph {graph_index} PNG exported: {path}")
        except Exception as exc:
            messagebox.showerror("Export PNG", f"Failed to export image:\n{exc}")

    def _export_graph_csv(self, graph_index: int) -> None:
        payload = self._last_rendered_graph_data.get(graph_index, {})
        series = payload.get("series", []) if isinstance(payload, dict) else []
        if not series:
            messagebox.showwarning("Export CSV", "No plotted data is available to export.")
            return

        path = filedialog.asksaveasfilename(
            title=f"Export Graph {graph_index} CSV",
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv")],
        )
        if not path:
            return

        x_label = str(payload.get("x_label", "X"))
        y_label = str(payload.get("y_label", "Y"))
        try:
            with open(path, "w", newline="", encoding="utf-8") as fp:
                writer = csv.writer(fp)
                writer.writerow(["Series", "Channel", x_label, y_label, "Y_Error", "Fit_Y", "Fit_Label"])
                for s in series:
                    xs = s.get("x", [])
                    ys = s.get("y", [])
                    yerrs = s.get("yerr", [])
                    fit_y = s.get("fit_y", [])
                    max_len = max(len(xs), len(ys), len(yerrs), len(fit_y))
                    for idx in range(max_len):
                        writer.writerow(
                            [
                                f"Graph {graph_index}",
                                str(s.get("channel", "")),
                                xs[idx] if idx < len(xs) else "",
                                ys[idx] if idx < len(ys) else "",
                                yerrs[idx] if idx < len(yerrs) and yerrs[idx] is not None else "",
                                fit_y[idx] if idx < len(fit_y) else "",
                                s.get("fit_label", "") if idx == 0 else "",
                            ]
                        )
            self.app.ui_bus.post_log(f"Graph {graph_index} CSV exported: {path}")
        except Exception as exc:
            messagebox.showerror("Export CSV", f"Failed to export CSV:\n{exc}")

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
            "Purple": "tab:purple",
            "Brown": "tab:brown",
            "Pink": "tab:pink",
        }
        return color_map.get(str(selected_color).strip(), "tab:blue")

    def _selected_channels_for_graph(self, graph_index: int) -> list[str]:
        channel_vars = self.channel_filter_vars_g1 if graph_index == 1 else self.channel_filter_vars_g2
        selected = [ch for ch, var in channel_vars.items() if var.get()]
        return selected or list(LOGICAL_CHANNELS)

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

    def _row_value_for_channel(self, row: dict[str, Any], key: str, channel: str | None) -> Any:
        # Preferred generic keys
        if key in row:
            return row.get(key)

        if channel is None:
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

        ttk.Button(btn_row, text="Run", style="Primary.TButton", command=self._on_run_script).grid(row=0, column=0, padx=2)
        ttk.Button(btn_row, text="Load", style="Secondary.TButton", command=self._on_load_script).grid(row=0, column=1, padx=2)
        ttk.Button(btn_row, text="Save", style="Secondary.TButton", command=lambda: self._on_save_script(force_prompt=True)).grid(
            row=0, column=2, padx=2
        )
        self.pause_button = ttk.Button(btn_row, text="Pause", style="Secondary.TButton", command=self._on_pause_script)
        self.pause_button.grid(row=0, column=3, padx=2)
        ttk.Button(btn_row, text="Abort", style="Danger.TButton", command=self._on_abort_script).grid(row=0, column=4, padx=2)
        ttk.Button(btn_row, text="Commands", style="Secondary.TButton", command=self._open_commands_popup).grid(row=0, column=5, padx=2)

        # Status (Courier 10, sunken, f0f0f0 bg)
        self.script_status = tk.StringVar(value="Status: Idle")
        status_lbl = tk.Label(
            script_control_section, textvariable=self.script_status,
            font=FONTS["mono"], relief="sunken", background=COLORS["bg_input"],
            foreground=COLORS["fg_primary"], anchor="w",
        )
        status_lbl.pack(fill="x", padx=5, pady=(2, 5))

        # Script editor label
        ttk.Label(parent, text="Script Editor:", style="SectionTitle.TLabel").pack(anchor="w", padx=5, pady=(5, 2))

        # Text editor (tk.Text, height=10, width=50, Courier 10)
        editor_frame = ttk.Frame(parent)
        editor_frame.pack(fill="both", expand=True, padx=5, pady=2)
        editor_frame.rowconfigure(0, weight=1)
        editor_frame.columnconfigure(0, weight=1)

        self.script_text = tk.Text(
            editor_frame, height=14, width=58, font=FONTS["mono"],
            foreground=COLORS["fg_primary"], background=COLORS["bg_input"],
            insertbackground=COLORS["fg_primary"],
            undo=True, wrap="none",
        )
        ysb = ttk.Scrollbar(editor_frame, orient="vertical", command=self.script_text.yview)
        xsb = ttk.Scrollbar(editor_frame, orient="horizontal", command=self.script_text.xview)
        self.script_text.configure(yscrollcommand=ysb.set, xscrollcommand=xsb.set)
        self.script_text.grid(row=0, column=0, sticky="nsew")
        ysb.grid(row=0, column=1, sticky="ns")
        xsb.grid(row=1, column=0, sticky="ew")
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
        self.script_text.tag_configure("current_line", background="#fff2a8")
        self.script_text.tag_configure("loop_body_line", background="#ffd0d0")

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
            font=FONTS["mono_small"], wrap="word",
            foreground=COLORS["fg_primary"], background=COLORS["bg_input"],
            insertbackground=COLORS["fg_primary"],
        )
        self.log_text.tag_configure("warn", foreground=COLORS["accent_warn"])
        self.log_text.tag_configure("error", foreground=COLORS["accent_error"])
        self.log_text.tag_configure("info", foreground=COLORS["fg_primary"])
        log_sb = ttk.Scrollbar(log_frame, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=log_sb.set)
        self.log_text.pack(side="left", fill="both", expand=True)
        log_sb.pack(side="right", fill="y")

    # ------------------------------------------------------------------
    # System log helper
    # ------------------------------------------------------------------
    def _append_log(self, msg: str) -> None:
        lower = str(msg).lower()
        if "error" in lower or "failed" in lower or "exception" in lower:
            tag = "error"
        elif "warning" in lower or "warn" in lower:
            tag = "warn"
        else:
            tag = "info"

        self.log_text.configure(state="normal")
        self.log_text.insert("end", msg + "\n", tag)
        self.log_text.see("end")
        # Trim to 1000 lines max
        line_count = int(self.log_text.index("end-1c").split(".")[0])
        if line_count > 1000:
            self.log_text.delete("1.0", f"{line_count - 1000}.0")
        self.log_text.configure(state="disabled")

    # ------------------------------------------------------------------
    # Script line highlighting
    # ------------------------------------------------------------------
    def _nearest_nonempty_line(self, line_num: int) -> int:
        """Return the nearest non-empty editor line to highlight."""
        if line_num <= 0:
            return 0

        last_line = int(self.script_text.index("end-1c").split(".")[0])
        if last_line <= 0:
            return 0

        target = max(1, min(int(line_num), last_line))
        text = self.script_text.get(f"{target}.0", f"{target}.end")
        if text.strip():
            return target

        for probe in range(target + 1, last_line + 1):
            if self.script_text.get(f"{probe}.0", f"{probe}.end").strip():
                return probe

        for probe in range(target - 1, 0, -1):
            if self.script_text.get(f"{probe}.0", f"{probe}.end").strip():
                return probe

        return 0

    def highlight_line(self, line_num: int, loop_level: int = 0, parent_line: int = 0) -> None:
        """Highlight script line(s), keeping loop parent and child visible together."""
        self.script_text.tag_remove("current_line", "1.0", "end")
        self.script_text.tag_remove("loop_body_line", "1.0", "end")
        target_line = self._nearest_nonempty_line(line_num)
        parent_target = self._nearest_nonempty_line(parent_line) if parent_line > 0 else 0
        if target_line > 0:
            if loop_level > 0 and parent_target > 0:
                self.script_text.tag_add("current_line", f"{parent_target}.0", f"{parent_target}.end")
                self.script_text.tag_add("loop_body_line", f"{target_line}.0", f"{target_line}.end")
            else:
                tag_name = "loop_body_line" if loop_level > 0 else "current_line"
                self.script_text.tag_add(tag_name, f"{target_line}.0", f"{target_line}.end")
            self.script_text.see(f"{target_line}.0")

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
    # Script command helper popup
    # ------------------------------------------------------------------
    def _command_category(self, name: str) -> str:
        if name in {"test", "run_saved_script", "initialize_data_file", "add_note"}:
            return "General"
        if name in {"wait_for", "time_sweep", "for_loop"}:
            return "Timing"
        if name.startswith("set_dyna") or name.startswith("scan_dyna") or name.startswith("sweep_dyna"):
            return "PPMS"
        if name.startswith("set_helmholtz") or name.startswith("scan_helmholtz") or name.startswith("sweep_helmholtz"):
            return "Helmholtz"
        if "hall" in name:
            return "Hall"
        if "lockin" in name or name in {"auto_gain", "auto_phase", "auto_reserve"}:
            return "Lock-In"
        if "channel" in name or "switch" in name:
            return "Switch"
        return "Other"

    def _command_usage(self, name: str) -> str:
        positional_names_map: dict[str, list[str]] = {
            "set_dyna_field": ["field_Oe", "rate_Oe/s", "approach"],
            "set_dyna_temp": ["temp_K", "rate_K/min", "approach"],
            "set_helmholtz_field": ["field_Oe", "rate_Oe/s"],
            "scan_dyna_field": ["start_Oe", "end_Oe", "step_Oe", "rate_Oe/s", "approach"],
            "scan_dyna_temp": ["start_K", "end_K", "step_K", "rate_K/min", "approach"],
            "sweep_dyna_field": ["start_Oe", "end_Oe", "rate_Oe/s"],
            "sweep_dyna_temp": ["start_K", "end_K", "rate_K/min"],
            "scan_helmholtz_field": ["start_Oe", "end_Oe", "step_Oe", "rate_Oe/s"],
            "sweep_helmholtz_field": ["start_Oe", "end_Oe", "rate_Oe/s"],
            "wait_for": ["event1", "additional_time_s"],
            "time_sweep": ["sweep_time_s", "time_gap_s"],
            "for_loop": ["iterations"],
            "set_lockin_time_constant": ["seconds"],
            "set_lockin_sensitivity": ["index_0_to_26"],
            "set_lockin_filter": ["db_oct"],
            "set_lockin_frequency": ["frequency_hz"],
            "set_lockin_current": ["current_A"],
            "set_ppms_field_and_fix_hall": ["field_Oe", "target_hall_G"],
            "scan_ppms_field_and_fix_hall": ["start_Oe", "end_Oe", "step_Oe", "target_hall_G"],
            "full_measure": ["channel"],
            "continuous_full_measure": [],
            "run_saved_script": ["full_path_and_filename"],
            "close_channel": ["channel"],
            "configure_channel": ["channel", "I+", "V+", "V-", "I-"],
        }

        min_pos = int(MIN_POSITIONAL.get(name, 0))
        kwargs = sorted(ALLOWED_KWARGS.get(name, set()))
        usage = [name]
        positional_names = list(positional_names_map.get(name, []))
        if len(positional_names) < min_pos:
            for idx in range(len(positional_names), min_pos):
                positional_names.append(f"arg{idx + 1}")

        for idx in range(min_pos):
            usage.append(f"<{positional_names[idx]}>")
        if kwargs:
            usage.append("[key=value ...]")
        return " ".join(usage)

    def _command_snippet(self, name: str) -> str:
        positional_names_map: dict[str, list[str]] = {
            "set_dyna_field": ["field_Oe", "rate_Oe/s", "approach"],
            "set_dyna_temp": ["temp_K", "rate_K/min", "approach"],
            "set_helmholtz_field": ["field_Oe", "rate_Oe/s"],
            "scan_dyna_field": ["start_Oe", "end_Oe", "step_Oe", "rate_Oe/s", "approach"],
            "scan_dyna_temp": ["start_K", "end_K", "step_K", "rate_K/min", "approach"],
            "sweep_dyna_field": ["start_Oe", "end_Oe", "rate_Oe/s"],
            "sweep_dyna_temp": ["start_K", "end_K", "rate_K/min"],
            "scan_helmholtz_field": ["start_Oe", "end_Oe", "step_Oe", "rate_Oe/s"],
            "sweep_helmholtz_field": ["start_Oe", "end_Oe", "rate_Oe/s"],
            "wait_for": ["event1", "additional_time_s"],
            "time_sweep": ["sweep_time_s", "time_gap_s"],
            "for_loop": ["iterations"],
            "set_lockin_time_constant": ["seconds"],
            "set_lockin_sensitivity": ["index_0_to_26"],
            "set_lockin_filter": ["db_oct"],
            "set_lockin_frequency": ["frequency_hz"],
            "set_lockin_current": ["current_A"],
            "set_ppms_field_and_fix_hall": ["field_Oe", "target_hall_G"],
            "scan_ppms_field_and_fix_hall": ["start_Oe", "end_Oe", "step_Oe", "target_hall_G"],
            "full_measure": ["channel"],
            "continuous_full_measure": [],
            "run_saved_script": ["full_path_and_filename"],
            "close_channel": ["channel"],
            "configure_channel": ["channel", "I+", "V+", "V-", "I-"],
        }

        min_pos = int(MIN_POSITIONAL.get(name, 0))
        kwargs = sorted(ALLOWED_KWARGS.get(name, set()))
        parts = [name]
        positional_names = list(positional_names_map.get(name, []))
        if len(positional_names) < min_pos:
            for idx in range(len(positional_names), min_pos):
                positional_names.append(f"arg{idx + 1}")

        for idx in range(min_pos):
            parts.append(f"<{positional_names[idx]}>")
        if kwargs:
            parts.extend(f"{key}=..." for key in kwargs[:3])
        return " ".join(parts)

    def _open_commands_popup(self) -> None:
        if self._command_popup is not None and self._command_popup.winfo_exists():
            self._command_popup.lift()
            self._command_popup.focus_force()
            return

        popup = tk.Toplevel(self.app.root)
        popup.title("Script Commands")
        popup.geometry("860x560")
        popup.transient(self.app.root)
        popup.attributes("-topmost", True)
        self._command_popup = popup
        self._command_search_var.set("")

        top = ttk.Frame(popup, padding=8)
        top.pack(fill="x")
        ttk.Label(top, text="Search:").pack(side="left")
        search_entry = ttk.Entry(top, textvariable=self._command_search_var, width=40)
        search_entry.pack(side="left", padx=(6, 8))
        search_entry.bind("<KeyRelease>", lambda _e: self._refresh_command_list())
        ttk.Label(top, text="Double-click command to insert into script editor.").pack(side="left")

        body = ttk.Frame(popup, padding=(8, 0, 8, 8))
        body.pack(fill="both", expand=True)
        body.columnconfigure(0, weight=1)
        body.columnconfigure(1, weight=2)
        body.rowconfigure(0, weight=1)

        left = ttk.Frame(body)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        left.rowconfigure(0, weight=1)
        left.columnconfigure(0, weight=1)
        right = ttk.Frame(body)
        right.grid(row=0, column=1, sticky="nsew")
        right.rowconfigure(1, weight=1)
        right.columnconfigure(0, weight=1)

        self._command_tree = ttk.Treeview(left, show="tree", selectmode="browse")
        tree_ysb = ttk.Scrollbar(left, orient="vertical", command=self._command_tree.yview)
        tree_xsb = ttk.Scrollbar(left, orient="horizontal", command=self._command_tree.xview)
        self._command_tree.configure(yscrollcommand=tree_ysb.set, xscrollcommand=tree_xsb.set)
        self._command_tree.grid(row=0, column=0, sticky="nsew")
        tree_ysb.grid(row=0, column=1, sticky="ns")
        tree_xsb.grid(row=1, column=0, sticky="ew")

        ttk.Label(right, text="Preview", style="SectionTitle.TLabel").grid(row=0, column=0, sticky="w", pady=(0, 4))
        self._command_preview = tk.Text(right, height=18, wrap="word", font=("Courier", 10), state="disabled")
        preview_scroll = ttk.Scrollbar(right, orient="vertical", command=self._command_preview.yview)
        self._command_preview.configure(yscrollcommand=preview_scroll.set)
        self._command_preview.grid(row=1, column=0, sticky="nsew")
        preview_scroll.grid(row=1, column=1, sticky="ns")

        button_row = ttk.Frame(popup, padding=8)
        button_row.pack(fill="x")
        ttk.Button(button_row, text="Insert", command=self._insert_selected_command).pack(side="left", padx=(0, 6))
        ttk.Button(button_row, text="Copy", command=self._copy_selected_command).pack(side="left", padx=(0, 6))
        ttk.Button(button_row, text="Close", command=self._close_commands_popup).pack(side="right")

        self._command_tree.bind("<<TreeviewSelect>>", lambda _e: self._preview_selected_command())
        self._command_tree.bind("<Double-Button-1>", lambda _e: self._insert_selected_command())
        popup.protocol("WM_DELETE_WINDOW", self._close_commands_popup)

        self._refresh_command_list()
        search_entry.focus_set()

    def _close_commands_popup(self) -> None:
        if self._command_popup is not None and self._command_popup.winfo_exists():
            self._command_popup.destroy()
        self._command_popup = None
        self._command_tree = None
        self._command_item_to_name = {}

    def _refresh_command_list(self) -> None:
        if self._command_tree is None:
            return
        query = self._command_search_var.get().strip().lower()
        self._command_tree.delete(*self._command_tree.get_children())
        self._command_item_to_name = {}

        categories: dict[str, list[str]] = {}
        for name in sorted(str(cmd) for cmd in VALID_COMMANDS):
            if query and query not in name.lower():
                continue
            categories.setdefault(self._command_category(name), []).append(name)

        first_command_item: str | None = None
        for category in sorted(categories):
            cat_item = self._command_tree.insert("", "end", text=category, open=True)
            for name in categories[category]:
                marker = " [loop]" if name in LOOP_COMMANDS else ""
                item_id = self._command_tree.insert(cat_item, "end", text=f"{name}{marker}")
                self._command_item_to_name[item_id] = name
                if first_command_item is None:
                    first_command_item = item_id

        if first_command_item is not None:
            self._command_tree.selection_set(first_command_item)
            self._command_tree.see(first_command_item)
            self._preview_selected_command()
        else:
            self._set_command_preview("No commands match the current search.")

    def _selected_command_name(self) -> str | None:
        if self._command_tree is None:
            return None
        sel = self._command_tree.selection()
        if not sel:
            return None
        item_id = sel[0]
        return self._command_item_to_name.get(item_id)

    def _set_command_preview(self, text: str) -> None:
        if self._command_preview is None:
            return
        self._command_preview.configure(state="normal")
        self._command_preview.delete("1.0", "end")
        self._command_preview.insert("1.0", text)
        self._command_preview.configure(state="disabled")

    def _preview_selected_command(self) -> None:
        name = self._selected_command_name()
        if name is None:
            self._set_command_preview("Select a command to preview usage.")
            return
        kwargs = sorted(ALLOWED_KWARGS.get(name, set()))
        sample = self._command_snippet(name)

        details = [f"Command: {name}", "", f"Usage: {self._command_usage(name)}"]
        if kwargs:
            details.extend(["", "Allowed kwargs:", ", ".join(kwargs)])

        approach_hints: dict[str, str] = {
            "set_dyna_field": "Approach options: linear, no_overshoot, oscillate",
            "scan_dyna_field": "Approach options: linear, no_overshoot, oscillate",
            "set_dyna_temp": "Approach options: fast_settle (or fast), no_overshoot",
            "scan_dyna_temp": "Approach options: fast_settle (or fast), no_overshoot",
            "sweep_dyna_field": "Approach: fixed to linear for sweep commands",
            "sweep_dyna_temp": "Approach: fixed to fast_settle for sweep commands",
        }
        hint = approach_hints.get(name)
        if hint is not None:
            details.extend(["", hint])

        lockin_setting_hints: dict[str, str] = {
            "set_lockin_time_constant": (
                "Allowed values (s): 10e-6, 30e-6, 100e-6, 300e-6, 1e-3, 3e-3, 10e-3, 30e-3, "
                "100e-3, 300e-3, 1, 3, 10, 30, 100, 300, 1000, 3000"
            ),
            "set_lockin_sensitivity": (
                "Allowed index values: 0..26. Mapping: "
                "0=2nV, 1=5nV, 2=10nV, 3=20nV, 4=50nV, 5=100nV, 6=200nV, 7=500nV, "
                "8=1uV, 9=2uV, 10=5uV, 11=10uV, 12=20uV, 13=50uV, 14=100uV, 15=200uV, 16=500uV, "
                "17=1mV, 18=2mV, 19=5mV, 20=10mV, 21=20mV, 22=50mV, 23=100mV, 24=200mV, 25=500mV, 26=1V"
            ),
            "set_lockin_filter": "Allowed filter values: 6, 12, 18, 24 dB/oct",
            "set_lockin_current": "Setting current to 0 turns lock-in output off.",
        }
        lockin_hint = lockin_setting_hints.get(name)
        if lockin_hint is not None:
            details.extend(["", lockin_hint])

        k2450_hints: dict[str, list[str]] = {
            "measure_resistance": [
                "Parameters:",
                "  current      (A, required)  — DC source current",
                "  current_ma   (mA, optional) — same as current, mA-friendly",
                "  compliance   (V, default 10) — max voltage limit",
                "  nplc         (cycles, default 1) — integration time; 1 NPLC ≈ 16.7 ms at 60 Hz",
                "  settle_time  (s, default 0)  — delay after sourcing before measuring",
                "  repetitions  (integer ≥ 1, default 1) — averages that many readings",
                "  voltage_range (V or 'auto', default 'auto') — measurement voltage range",
                "  Auto usage: set voltage_range=auto (or omit voltage_range)",
            ],
            "measure_iv_curve": [
                "Parameters:",
                "  mode         ('current' or 'voltage', required)",
                "  Preferred syntax: start + min + max + step",
                "  shape        (required) — sweep pattern:",
                "               start_min_max_start  : start → min → max → start",
                "               start_max_min_start  : start → max → min → start",
                "               start_min_start      : start → min → start",
                "               start_max_start      : start → max → start",
                "               single               : start → stop (alias: →)",
                "               return               : start → stop → start (alias: loop / bidirectional)",
                "  start        (A or V, required) — first setpoint",
                "  start_ma     (mA, optional current-mode alias)",
                "  min/max      (A or V, preferred with start/step)",
                "  min_ma/max_ma (mA, optional current-mode aliases)",
                "  stop         (A or V, optional fallback) — sweep limit when min/max are omitted",
                "  step         (A or V, required, non-zero) — step size",
                "  step_ma      (mA, optional current-mode alias)",
                "  compliance   (V for current mode, A for voltage mode; default auto)",
                "  nplc         (cycles, default 1) — integration time",
                "  settle_time  (s, default 0) — delay at each setpoint before measuring",
                "  repetitions  (integer ≥ 1, default 1) — averages per point",
                "  source_range  (A or V; optional)",
                "  measure_range (A or V; optional)",
                "  Auto usage (important): for IV, do NOT write source_range=auto or measure_range=auto.",
                "                         Leave source_range/measure_range out of the command to use Auto.",
                "  auto_range   (true/false, default true) — keep true for Auto measurement range",
                "  ramp_to_start (true/false, default true) — after sweep, step source",
                "                back to start value using the same step size (safe ramp)",
                "  keep_output   (true/false, default false) — leave source enabled after sweep",
            ],
        }
        k2450_hint_lines = k2450_hints.get(name)
        if k2450_hint_lines is not None:
            details.extend([""] + k2450_hint_lines)

        if name == "run_saved_script":
            details.extend(["", "Use full directory + file name (absolute path)."])

        if name == "wait_for":
            details.extend(
                [
                    "",
                    "Wait events:",
                    "temp, field, helmholtz, all, no_event",
                    "Aliases:",
                    "temp_stable->temp, field_stable->field, dyna_ready->field, helmholtz_field/helmholtz_stable->helmholtz",
                ]
            )

        # Keep 1-3 examples per command, copied from Commands.txt for consistency.
        examples_from_docs: dict[str, list[str]] = {
            "test": [
                "test",
            ],
            "initialize_data_file": [
                "initialize_data_file",
                "initialize_data_file filename=custom_data.csv",
                "initialize_data_file directory=/tmp filename=test.csv",
            ],
            "add_note": [
                "add_note Sample appears normal",
                "add_note Stable at 250K",
            ],
            "run_saved_script": [
                "run_saved_script subscript.txt",
            ],
            "wait_for": [
                "wait_for temp 5",
                "wait_for temp field 5",
                "wait_for all 5",
            ],
            "time_sweep": [
                "time_sweep 60 1",
                "time_sweep 300 0.5",
            ],
            "for_loop": [
                "for_loop 10",
            ],
            "set_dyna_temp": [
                "set_dyna_temp 300 5 no_overshoot",
            ],
            "scan_dyna_temp": [
                "scan_dyna_temp 300 400 20 5 no_overshoot",
            ],
            "sweep_dyna_temp": [
                "sweep_dyna_temp 300 350 5 gap_time=3",
                "sweep_dyna_temp 200 400 10 gap_time=0",
            ],
            "set_dyna_field": [
                "set_dyna_field 1000 10 no_overshoot",
            ],
            "scan_dyna_field": [
                "scan_dyna_field 0 2000 200 20 no_overshoot",
            ],
            "sweep_dyna_field": [
                "sweep_dyna_field 0 2000 20 gap_time=5",
                "sweep_dyna_field -1000 1000 50 gap_time=0",
            ],
            "set_helmholtz_field": [
                "set_helmholtz_field 100 5.0",
            ],
            "scan_helmholtz_field": [
                "scan_helmholtz_field 0 500 50 5 linear",
            ],
            "sweep_helmholtz_field": [
                "sweep_helmholtz_field 0 500 5 gap_time=2",
                "sweep_helmholtz_field -300 300 10 gap_time=0",
            ],
            "set_ppms_field_and_fix_hall": [
                "set_ppms_field_and_fix_hall 1000 100.5",
                "set_ppms_field_and_fix_hall 1000 100.5 max_current_change=1.2",
            ],
            "scan_ppms_field_and_fix_hall": [
                "scan_ppms_field_and_fix_hall 0 2000 200 100 rate=10.0",
                "scan_ppms_field_and_fix_hall 0 2000 200 100 rate=20",
                "scan_ppms_field_and_fix_hall -2000 2000 200 100 rate=10 max_current_change=1.5",
            ],
            "measure_hall_field": [
                "measure_hall_field",
                "measure_hall_field current=1.5",
                "measure_hall_field current=1.5 nplc=10 voltage_range=10V",
            ],
            "continuous_measure_hall_field": [
                "continuous_measure_hall_field",
                "continuous_measure_hall_field nplc=1 filter_count=5",
                "continuous_measure_hall_field current=1.0 compliance_v=2 tbm=0.2",
            ],
            "measure_resistance": [
                "measure_resistance current=1e-3",
                "measure_resistance current_ma=0.5 voltage_range=0.02 compliance=0.02",
                "measure_resistance current=1e-3 voltage_range=auto",
                "measure_resistance current=5e-4 nplc=5 repetitions=3",
                "measure_resistance current=1e-3 compliance=5 voltage_range=20V settle_time=0.05",
            ],
            "measure_iv_curve": [
                "measure_iv_curve mode=current start_ma=0 min_ma=-1 max_ma=1 step_ma=0.1 shape=start_min_max_start auto_range=true ramp_to_start=true",
                "measure_iv_curve mode=current shape=start_max_start start=0 stop=1e-3 step=1e-4 compliance=5",
                "measure_iv_curve mode=current shape=single start=0 stop=1e-3 step=1e-4 ramp_to_start=false",
                "measure_iv_curve mode=voltage shape=start_max_start start=0 stop=0.5 step=0.05 measure_range=0.02 auto_range=false",
            ],
            "measure_lockin": [
                "measure_lockin",
                "measure_lockin current=1e-6",
                "measure_lockin what=X,Y,R avg=20 sample_delay=0.1",
            ],
            "continuous_measure_lockin": [
                "continuous_measure_lockin avg=10 sample_delay=0.02",
            ],
            "set_lockin_time_constant": [
                "set_lockin_time_constant 0.3",
                "set_lockin_time_constant 1.0",
                "set_lockin_time_constant 3.0",
            ],
            "set_lockin_sensitivity": [
                "set_lockin_sensitivity 10",
                "set_lockin_sensitivity 17",
                "set_lockin_sensitivity 26",
            ],
            "set_lockin_filter": [
                "set_lockin_filter 6",
                "set_lockin_filter 12",
                "set_lockin_filter 24",
            ],
            "set_lockin_frequency": [
                "set_lockin_frequency 1234.5",
                "set_lockin_frequency 668.4",
                "set_lockin_frequency 500.0",
            ],
            "set_lockin_current": [
                "set_lockin_current 3e-3",
                "set_lockin_current 5e-6 series_resistance=10000",
            ],
            "full_measure": [
                "full_measure a",
                "full_measure c",
                "full_measure a time_between=0.1",
                "full_measure a hall_excitation=keep",
            ],
            "continuous_full_measure": [
                "continuous_full_measure",
                "continuous_full_measure lockin_use_autorange=true",
                "continuous_full_measure time_between=0.1 hall_nplc=5 lockin_avg=20",
            ],
            "configure_channel": [
                "configure_channel a 5 6 7 8",
                "configure_channel b 1 2 3 4",
            ],
            "enable_hall_output": [
                "enable_hall_output current=1.0 compliance_v=2.0",
            ],
            "disable_hall_output": [
                "disable_hall_output",
            ],
        }

        min_pos = int(MIN_POSITIONAL.get(name, 0))
        # Requested behavior:
        # - 0-input commands: do not show examples
        # - 1-input commands: show exactly one example
        # - otherwise: show up to three examples
        force_examples_for_zero_input = {
            "test",
            "initialize_data_file",
            "add_note",
            "measure_hall_field",
            "continuous_measure_hall_field",
            "enable_hall_output",
            "disable_hall_output",
        }
        max_examples = 0 if (min_pos == 0 and name not in force_examples_for_zero_input) else (1 if min_pos == 1 else 3)
        example_lines = examples_from_docs.get(name, [])
        if example_lines and max_examples > 0:
            details.extend(["", "Examples (from Commands.txt):", *example_lines[:max_examples]])

        details.extend(["", "Quick insert sample:", sample])
        self._set_command_preview("\n".join(details))

    def _insert_selected_command(self) -> None:
        name = self._selected_command_name()
        if name is None:
            return
        snippet = self._command_snippet(name)
        self.script_text.insert("insert", snippet)
        if not snippet.endswith("\n"):
            self.script_text.insert("insert", "\n")
        if self._command_popup is not None and self._command_popup.winfo_exists():
            self._command_popup.lift()
            self._command_popup.focus_force()

    def _copy_selected_command(self) -> None:
        name = self._selected_command_name()
        if name is None:
            return
        snippet = self._command_snippet(name)
        self.app.root.clipboard_clear()
        self.app.root.clipboard_append(snippet)
        self._append_log(f"Copied command snippet: {snippet}")

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
            self._render_helmholtz_ch_a_label()
        elif widget_id == W_HELMHOLTZ_CURRENT_B:
            self._helmholtz_current_b = float(value)
            self._render_helmholtz_field_label()
            self._render_helmholtz_ch_b_label()
        elif widget_id == W_HELMHOLTZ_RESISTANCE_A:
            self._helmholtz_resistance_a = float(value) if value is not None else None
            self._render_helmholtz_ch_a_label()
        elif widget_id == W_HELMHOLTZ_RESISTANCE_B:
            self._helmholtz_resistance_b = float(value) if value is not None else None
            self._render_helmholtz_ch_b_label()
        elif widget_id == W_HELMHOLTZ_RAMPING:
            self._helmholtz_ramping = bool(value)
            self._render_helmholtz_field_label()
        elif widget_id == W_DYNA_TEMP:
            self._dyna_temp_value = float(value) if value is not None else None
            self._render_dyna_temp_label()
        elif widget_id == W_DYNA_FIELD:
            self._dyna_field_value = float(value) if value is not None else None
            self._render_dyna_field_label()
        elif widget_id == W_DYNA_CHAMBER:
            try:
                self._dyna_chamber_value = int(value) if value is not None else None
            except Exception:
                self._dyna_chamber_value = None
            self._render_dyna_chamber_label()
        elif widget_id == W_DYNA_TEMP_STATUS:
            self._dyna_temp_status = self._normalize_status(value)
            self._render_dyna_temp_label()
        elif widget_id == W_DYNA_FIELD_STATUS:
            self._dyna_field_status = self._normalize_status(value)
            self._render_dyna_field_label()
        elif widget_id == W_DYNA_SETPOINT:
            if isinstance(value, dict):
                try:
                    if "temp_rate_k_min" in value:
                        self._dyna_temp_rate_k_min = float(value["temp_rate_k_min"])
                    if "field_rate_oe_s" in value:
                        self._dyna_field_rate_oe_s = float(value["field_rate_oe_s"])
                except Exception:
                    pass
                self._render_dyna_temp_label()
                self._render_dyna_field_label()
        elif widget_id == W_HELMHOLTZ_SETPOINT:
            if isinstance(value, dict):
                try:
                    if "rate_mA_s" in value:
                        self._helmholtz_rate_mA_s = float(value["rate_mA_s"])
                except Exception:
                    pass
                self._render_helmholtz_field_label()
        elif widget_id == W_DYNA_CHAMBER_STATUS:
            self._dyna_chamber_status = self._normalize_status(value)
            self._render_dyna_chamber_label()
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
        elif widget_id == W_LOCKIN_OUTPUT_VOLTAGE:
            if self._lockin_popup_output_led is not None:
                try:
                    v = float(value)
                except Exception:
                    v = 0.0
                threshold = max(float(self.app.lockin_tab._idle_output_voltage), 0.0) + 1e-6
                set_led(self._lockin_popup_output_led, v > threshold)
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
            self._refresh_hall_sample_status_from_results()
            self._schedule_plot_refresh()

    def _refresh_hall_sample_status_from_results(self) -> None:
        rows = self.app.data_mgr.get_results()
        for row in reversed(rows):
            mtype = str(row.get("Measurement_Type", "")).strip().lower()
            if mtype not in {"resistance", "iv"}:
                continue

            resistance = self._to_numeric(row.get("Sample_Resistance"))
            if resistance is not None:
                self.results_hall_resistance.configure(text=f"  R: {resistance:.4e} Ohm")

            source_current = self._to_numeric(row.get("IV_Source_Current"))
            measured_current = self._to_numeric(row.get("IV_Measured_Current"))
            current = source_current if source_current is not None else measured_current
            if current is not None:
                self.results_hall_current.configure(text=f"  I(R): {current:.4e} mA")
            return

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
            self._dyna_chamber_value = None
            self._dyna_temp_status = "N/A"
            self._dyna_field_status = "N/A"
            self._dyna_chamber_status = "N/A"
            self._dyna_temp_rate_k_min = None
            self._dyna_field_rate_oe_s = None
            self._render_dyna_temp_label()
            self._render_dyna_field_label()
            self._render_dyna_chamber_label()
        if name == "helmholtz":
            self._helmholtz_rate_mA_s = None
            self._render_helmholtz_field_label()

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

    def _render_dyna_temp_label(self) -> None:
        temp_text = f"{self._fmt_4sig(self._dyna_temp_value)} K" if self._dyna_temp_value is not None else "N/A"
        status_suffix = f" ({self._dyna_temp_status})" if self._dyna_temp_status != "N/A" else ""
        rate_suffix = (
            f" {self._fmt_4sig(self._dyna_temp_rate_k_min)} K/min"
            if self._dyna_temp_rate_k_min is not None
            else ""
        )
        self.results_dyna_temp.configure(text=f"  Temp: {temp_text}{status_suffix}{rate_suffix}")

    def _render_dyna_field_label(self) -> None:
        field_text = f"{self._dyna_field_value:.2f} Oe" if self._dyna_field_value is not None else "N/A"
        status_suffix = f" ({self._dyna_field_status})" if self._dyna_field_status != "N/A" else ""
        rate_suffix = (
            f" {self._dyna_field_rate_oe_s:.2f} Oe/s"
            if self._dyna_field_rate_oe_s is not None
            else ""
        )
        self.results_dyna_field.configure(text=f"  Field: {field_text}{status_suffix}{rate_suffix}")

    def _render_dyna_chamber_label(self) -> None:
        chamber_text = self._dyna_chamber_status if self._dyna_chamber_status != "N/A" else "N/A"
        self.results_dyna_chamber.configure(text=f"  Chamber: {chamber_text}")

    def _render_helmholtz_ch_a_label(self) -> None:
        """Render Ch A with current and resistance combined."""
        show_res = self._helmholtz_resistance_a is not None and not math.isnan(float(self._helmholtz_resistance_a))
        res_txt = f"{float(self._helmholtz_resistance_a):.3f}" if show_res else "--"
        self.results_helmholtz_ch_a.configure(text=f"  Ch A: {self._helmholtz_current_a:.4f} A  /  {res_txt} Ω")

    def _render_helmholtz_ch_b_label(self) -> None:
        """Render Ch B with current and resistance combined."""
        show_res = self._helmholtz_resistance_b is not None and not math.isnan(float(self._helmholtz_resistance_b))
        res_txt = f"{float(self._helmholtz_resistance_b):.3f}" if show_res else "--"
        self.results_helmholtz_ch_b.configure(text=f"  Ch B: {self._helmholtz_current_b:.4f} A  /  {res_txt} Ω")

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
        rate_suffix = (
            f" {self._helmholtz_rate_mA_s:.1f} mA/s"
            if self._helmholtz_rate_mA_s is not None
            else ""
        )
        self.results_helmholtz_field.configure(text=f"  Field: {field_text} ({state}){rate_suffix}")

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
            self._schedule_plot_refresh(force=True)
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

    def _ask_unsaved_script_action(self, message: str) -> str:
        """Show unsaved-script dialog and return one of: save, save_as, no, cancel."""
        result: dict[str, str] = {"choice": "cancel"}

        dialog = tk.Toplevel(self.app.root)
        dialog.title("Unsaved Script")
        dialog.transient(self.app.root)
        dialog.resizable(False, False)

        frame = ttk.Frame(dialog, padding=12)
        frame.pack(fill="both", expand=True)

        ttk.Label(frame, text=message, justify="left", wraplength=460).pack(anchor="w")

        btn_row = ttk.Frame(frame)
        btn_row.pack(fill="x", pady=(12, 0))

        def _choose(value: str) -> None:
            result["choice"] = value
            try:
                dialog.grab_release()
            except Exception:
                pass
            dialog.destroy()

        ttk.Button(btn_row, text="Save", command=lambda: _choose("save")).pack(side="left", padx=(0, 6))
        ttk.Button(btn_row, text="Save As", command=lambda: _choose("save_as")).pack(side="left", padx=(0, 6))
        ttk.Button(btn_row, text="No", command=lambda: _choose("no")).pack(side="left", padx=(0, 6))
        ttk.Button(btn_row, text="Cancel", command=lambda: _choose("cancel")).pack(side="right")

        dialog.protocol("WM_DELETE_WINDOW", lambda: _choose("cancel"))

        dialog.update_idletasks()
        try:
            root_x = int(self.app.root.winfo_rootx())
            root_y = int(self.app.root.winfo_rooty())
            root_w = int(self.app.root.winfo_width())
            root_h = int(self.app.root.winfo_height())
            dlg_w = int(dialog.winfo_reqwidth())
            dlg_h = int(dialog.winfo_reqheight())
            pos_x = root_x + max(0, (root_w - dlg_w) // 2)
            pos_y = root_y + max(0, (root_h - dlg_h) // 2)
            dialog.geometry(f"+{pos_x}+{pos_y}")
        except Exception:
            pass

        dialog.grab_set()
        dialog.wait_window()
        return result["choice"]

    def prompt_save_script_if_needed(self, context: str = "") -> bool:
        if not self.has_unsaved_script_changes():
            return True

        message = "Script has unsaved changes. Save now?"
        if context:
            message = f"Script has unsaved changes {context}. Save now?"

        choice = self._ask_unsaved_script_action(message)

        if choice == "cancel":
            return False
        if choice == "no":
            return True

        if choice == "save_as":
            self._on_save_script(force_prompt=True)
            return not self.has_unsaved_script_changes()

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
