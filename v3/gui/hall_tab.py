"""
v3.gui.hall_tab  -  Keithley 2450 (Hall bar) control tab.

Provides controls for Hall bar current sourcing, NPLC, compliance,
voltage range, filter, trigger-before-measure delay, and offset
calibration.  Displays live Hall voltage and field readouts.
"""

from __future__ import annotations

import threading
import traceback
import time
import tkinter as tk
from tkinter import ttk
from typing import TYPE_CHECKING, Any

from v3.core.constants import INST_KEITHLEY2450
from v3.core.ui_events import (
    W_HALL_CONNECTED,
    W_HALL_RESULT,
    W_HALL_SOURCE_ENABLED,
    W_IV_PROGRESS,
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
    _IV_RANGE_OPTIONS_V = ("auto", "0.02", "0.2", "2", "20", "200")
    _IV_RANGE_OPTIONS_MA = ("auto", "0.01", "0.1", "1", "10", "100", "1050")

    def __init__(self, parent: ttk.Frame, app: "MeasureApp") -> None:
        super().__init__(parent, app)
        self._conn_header: ConnectionHeader | None = None
        self._measuring = False
        self._measure_buttons: list[ttk.Button] = []
        self._source_enabled = False
        self._source_led_after_id: str | None = None
        self._updating_preset = False
        self._k2450_aux_worker: threading.Thread | None = None
        self._iv_source_range_label: ttk.Label | None = None
        self._iv_measure_range_label: ttk.Label | None = None
        self._iv_source_range_menu: ttk.OptionMenu | None = None
        self._iv_measure_range_menu: ttk.OptionMenu | None = None
        self._iv_progress_after_id: str | None = None
        self._iv_progress_active = False
        self.iv_progress_value = tk.DoubleVar(value=0.0)
        self.iv_progress_text = tk.StringVar(value="IV progress: idle")
        self.iv_progress_style = "HallIVGreen.Horizontal.TProgressbar"

    def create_widgets(self) -> None:
        self._configure_progress_style()
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

    def _configure_progress_style(self) -> None:
        style = ttk.Style(self.parent)
        style.configure(
            self.iv_progress_style,
            troughcolor="#d9d9d9",
            background="#24a148",
            darkcolor="#1f8a3d",
            lightcolor="#2ecf5d",
            bordercolor="#1f8a3d",
        )

    # ------------------------------------------------------------------
    # Settings
    # ------------------------------------------------------------------
    def _build_settings(self, parent: ttk.Frame) -> None:
        settings_row = ttk.Frame(parent)
        settings_row.pack(fill="x", padx=5, pady=5)
        settings_row.columnconfigure(0, weight=1)
        settings_row.columnconfigure(1, weight=1)

        sf = ttk.LabelFrame(settings_row, text="Hall Measurment Setings")
        sf.grid(row=0, column=0, sticky="nsew", padx=(0, 5))

        self.k2450_current = tk.DoubleVar(value=2.0)       # mA
        self.k2450_nplc = tk.IntVar(value=5)
        self.k2450_compliance_v = tk.DoubleVar(value=2.0)
        self.k2450_voltage_range = tk.StringVar(value="auto")
        self.k2450_filter_count = tk.IntVar(value=10)
        self.k2450_tbm = tk.DoubleVar(value=0.05)           # seconds
        self.k2450_terminals = tk.StringVar(value="REAR")
        self.k2450_terminal_button_text = tk.StringVar(value="")
        self.k2450_active_terminal = tk.StringVar(value="Disconnected")
        self.k2450_hall_offset = tk.DoubleVar(value=0.0)     # V
        self.k2450_hall_v2gauss = tk.DoubleVar(value=10000.0 / 0.215)
        self.k2450_hall_bar = tk.StringVar(value="Wire Hall Bar 1")
        self.k2450_hall_v_per_g = tk.StringVar(value="")
        self.k2450_resistance_current_mA = tk.DoubleVar(value=1.0)
        self.k2450_resistance_compliance_v = tk.DoubleVar(value=10.0)
        self.k2450_resistance_nplc = tk.DoubleVar(value=1.0)
        self.k2450_resistance_voltage_range = tk.StringVar(value="auto")
        self.k2450_resistance_settle = tk.DoubleVar(value=0.0)
        self.k2450_resistance_repetitions = tk.IntVar(value=1)
        self.k2450_iv_mode = tk.StringVar(value="current")
        self.k2450_iv_shape = tk.StringVar(value="start_min_max_start")
        self.k2450_iv_start = tk.DoubleVar(value=0.0)
        self.k2450_iv_min = tk.DoubleVar(value=-1.0)
        self.k2450_iv_max = tk.DoubleVar(value=1.0)
        self.k2450_iv_step = tk.DoubleVar(value=0.1)
        self.k2450_iv_source_range = tk.StringVar(value="auto")
        self.k2450_iv_measure_range = tk.StringVar(value="auto")
        self.k2450_iv_compliance = tk.DoubleVar(value=0.1)
        self.k2450_iv_nplc = tk.DoubleVar(value=1.0)
        self.k2450_iv_settle = tk.DoubleVar(value=0.0)
        self.k2450_iv_repetitions = tk.IntVar(value=1)
        self.k2450_iv_ramp_to_start = tk.BooleanVar(value=True)
        self.k2450_iv_env_interval = tk.DoubleVar(value=0.0)

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

        row += 1
        ttk.Label(sf, text="Terminals:").grid(row=row, column=0, sticky="w", padx=5, pady=2)
        ttk.Button(
            sf,
            textvariable=self.k2450_terminal_button_text,
            command=self._on_terminal_button_pressed,
            width=24,
        ).grid(row=row, column=1, padx=5, pady=2, sticky="w")

        row += 1
        ttk.Label(sf, text="Active Terminal:").grid(row=row, column=0, sticky="w", padx=5, pady=2)
        ttk.Label(sf, textvariable=self.k2450_active_terminal).grid(row=row, column=1, sticky="w", padx=5, pady=2)

        aux = ttk.LabelFrame(settings_row, text="Resistance / IV")
        aux.grid(row=0, column=1, sticky="nsew", padx=(5, 0))
        aux.columnconfigure(1, weight=1)

        ttk.Label(aux, text="R Current (mA):").grid(row=0, column=0, sticky="w", padx=5, pady=2)
        ValidatingEntry(aux, textvariable=self.k2450_resistance_current_mA, width=8, validator=make_float_validator(1e-6, 105.0)).grid(row=0, column=1, sticky="w", padx=5, pady=2)
        ttk.Label(aux, text="R Compliance (V):").grid(row=0, column=2, sticky="w", padx=(10, 2), pady=2)
        ValidatingEntry(aux, textvariable=self.k2450_resistance_compliance_v, width=8, validator=make_float_validator(0.0, 210.0)).grid(row=0, column=3, sticky="w", padx=5, pady=2)
        ttk.Label(aux, text="R NPLC:").grid(row=0, column=4, sticky="w", padx=(10, 2), pady=2)
        ValidatingEntry(aux, textvariable=self.k2450_resistance_nplc, width=8, validator=make_float_validator(0.01, 20.0)).grid(row=0, column=5, sticky="w", padx=5, pady=2)

        ttk.Label(aux, text="R V-range:").grid(row=1, column=0, sticky="w", padx=5, pady=2)
        ttk.OptionMenu(aux, self.k2450_resistance_voltage_range, "auto", "auto", "0.02", "0.2", "2", "20", "200").grid(row=1, column=1, sticky="w", padx=5, pady=2)
        ttk.Label(aux, text="R Settle (s):").grid(row=1, column=2, sticky="w", padx=(10, 2), pady=2)
        ValidatingEntry(aux, textvariable=self.k2450_resistance_settle, width=8, validator=make_float_validator(0.0, 60.0)).grid(row=1, column=3, sticky="w", padx=5, pady=2)
        ttk.Label(aux, text="R Reps:").grid(row=1, column=4, sticky="w", padx=(10, 2), pady=2)
        ValidatingEntry(aux, textvariable=self.k2450_resistance_repetitions, width=8, validator=make_float_validator(1.0, 1000.0)).grid(row=1, column=5, sticky="w", padx=5, pady=2)

        ttk.Label(aux, text="IV Mode:").grid(row=2, column=0, sticky="w", padx=5, pady=2)
        ttk.OptionMenu(aux, self.k2450_iv_mode, "current", "current", "voltage").grid(row=2, column=1, sticky="w", padx=5, pady=2)
        ttk.Label(aux, text="Shape:").grid(row=2, column=2, sticky="w", padx=(10, 2), pady=2)
        ttk.OptionMenu(
            aux,
            self.k2450_iv_shape,
            "start_min_max_start",
            "start_min_max_start",
            "start_max_min_start",
            "start_min_start",
            "start_max_start",
        ).grid(row=2, column=3, sticky="w", padx=5, pady=2)
        ttk.Label(aux, text="Start (mA/V):").grid(row=2, column=4, sticky="w", padx=(10, 2), pady=2)
        ValidatingEntry(aux, textvariable=self.k2450_iv_start, width=8, validator=make_float_validator(-1e6, 1e6)).grid(row=2, column=5, sticky="w", padx=5, pady=2)

        ttk.Label(aux, text="Min (mA/V):").grid(row=3, column=0, sticky="w", padx=5, pady=2)
        ValidatingEntry(aux, textvariable=self.k2450_iv_min, width=8, validator=make_float_validator(-1e6, 1e6)).grid(row=3, column=1, sticky="w", padx=5, pady=2)
        ttk.Label(aux, text="Max (mA/V):").grid(row=3, column=2, sticky="w", padx=(10, 2), pady=2)
        ValidatingEntry(aux, textvariable=self.k2450_iv_max, width=8, validator=make_float_validator(-1e6, 1e6)).grid(row=3, column=3, sticky="w", padx=5, pady=2)
        ttk.Label(aux, text="Step (mA/V):").grid(row=3, column=4, sticky="w", padx=(10, 2), pady=2)
        ValidatingEntry(aux, textvariable=self.k2450_iv_step, width=8, validator=make_float_validator(1e-12, 1e6)).grid(row=3, column=5, sticky="w", padx=5, pady=2)

        ttk.Label(aux, text="Compliance:").grid(row=4, column=0, sticky="w", padx=5, pady=2)
        ValidatingEntry(aux, textvariable=self.k2450_iv_compliance, width=8, validator=make_float_validator(0.0, 210.0)).grid(row=4, column=1, sticky="w", padx=5, pady=2)
        ttk.Label(aux, text="NPLC:").grid(row=4, column=2, sticky="w", padx=(10, 2), pady=2)
        ValidatingEntry(aux, textvariable=self.k2450_iv_nplc, width=8, validator=make_float_validator(0.01, 20.0)).grid(row=4, column=3, sticky="w", padx=5, pady=2)
        ttk.Label(aux, text="Settle (s):").grid(row=4, column=4, sticky="w", padx=(10, 2), pady=2)
        ValidatingEntry(aux, textvariable=self.k2450_iv_settle, width=8, validator=make_float_validator(0.0, 60.0)).grid(row=4, column=5, sticky="w", padx=5, pady=2)

        ttk.Label(aux, text="Reps:").grid(row=5, column=0, sticky="w", padx=5, pady=2)
        ValidatingEntry(aux, textvariable=self.k2450_iv_repetitions, width=8, validator=make_float_validator(1.0, 1000.0)).grid(row=5, column=1, sticky="w", padx=5, pady=2)
        self._iv_source_range_label = ttk.Label(aux, text="Source Range (mA):")
        self._iv_source_range_label.grid(row=5, column=2, sticky="w", padx=(10, 2), pady=2)
        self._iv_source_range_menu = ttk.OptionMenu(aux, self.k2450_iv_source_range, "auto", *self._IV_RANGE_OPTIONS_MA)
        self._iv_source_range_menu.grid(row=5, column=3, sticky="w", padx=5, pady=2)
        self._iv_measure_range_label = ttk.Label(aux, text="Measure Range (V):")
        self._iv_measure_range_label.grid(row=5, column=4, sticky="w", padx=(10, 2), pady=2)
        self._iv_measure_range_menu = ttk.OptionMenu(aux, self.k2450_iv_measure_range, "auto", *self._IV_RANGE_OPTIONS_V)
        self._iv_measure_range_menu.grid(row=5, column=5, sticky="w", padx=5, pady=2)

        ramp_row = ttk.Frame(aux)
        ramp_row.grid(row=6, column=0, columnspan=6, sticky="w", padx=5, pady=2)
        ttk.Checkbutton(ramp_row, text="Ramp", variable=self.k2450_iv_ramp_to_start).pack(side="left")
        ttk.Label(ramp_row, text="Env sample interval (s):").pack(side="left", padx=(20, 2))
        ValidatingEntry(ramp_row, textvariable=self.k2450_iv_env_interval, width=7, validator=make_float_validator(0.0, 3600.0)).pack(side="left")
        self.k2450_aux_result = ttk.Label(aux, text="R / IV: ---", width=44)
        self.k2450_aux_result.grid(row=7, column=0, columnspan=6, sticky="w", padx=(5, 5), pady=2)

        action_row = ttk.Frame(aux)
        action_row.grid(row=8, column=0, columnspan=6, sticky="w", padx=5, pady=(4, 4))
        resistance_btn = ttk.Button(action_row, text="Measure Resistance", command=self._on_measure_resistance)
        resistance_btn.pack(side="left", padx=(0, 6))
        self.register_measure_button(resistance_btn)
        iv_btn = ttk.Button(action_row, text="Measure IV Curve", command=self._on_measure_iv_curve)
        iv_btn.pack(side="left")
        self.register_measure_button(iv_btn)

        self._apply_hall_bar_preset(self.k2450_hall_bar.get())
        self._update_terminal_button_text()
        self.k2450_hall_v2gauss.trace_add("write", self._on_manual_v2gauss_changed)
        self.k2450_iv_mode.trace_add("write", self._on_iv_mode_changed)
        self._update_iv_range_controls()
        self._sync_hall_metadata_to_data_manager()

    def _set_option_menu_values(self, menu_widget: ttk.OptionMenu, variable: tk.StringVar, values: tuple[str, ...]) -> None:
        menu = menu_widget["menu"]
        menu.delete(0, "end")
        for token in values:
            menu.add_command(label=token, command=tk._setit(variable, token))
        if str(variable.get()) not in values:
            variable.set(values[0])

    def _on_iv_mode_changed(self, *_args: object) -> None:
        self._update_iv_range_controls()

    def _update_iv_range_controls(self) -> None:
        if self._iv_source_range_label is None or self._iv_measure_range_label is None:
            return
        if self._iv_source_range_menu is None or self._iv_measure_range_menu is None:
            return

        mode_norm = str(self.k2450_iv_mode.get()).strip().lower()
        if mode_norm in {"current", "source_current", "i"}:
            self._iv_source_range_label.configure(text="Source Range (mA):")
            self._iv_measure_range_label.configure(text="Measure Range (V):")
            self._set_option_menu_values(self._iv_source_range_menu, self.k2450_iv_source_range, self._IV_RANGE_OPTIONS_MA)
            self._set_option_menu_values(self._iv_measure_range_menu, self.k2450_iv_measure_range, self._IV_RANGE_OPTIONS_V)
        else:
            self._iv_source_range_label.configure(text="Source Range (V):")
            self._iv_measure_range_label.configure(text="Measure Range (mA):")
            self._set_option_menu_values(self._iv_source_range_menu, self.k2450_iv_source_range, self._IV_RANGE_OPTIONS_V)
            self._set_option_menu_values(self._iv_measure_range_menu, self.k2450_iv_measure_range, self._IV_RANGE_OPTIONS_MA)

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

        aux_row = ttk.Frame(rd)
        aux_row.pack(fill="x", anchor="w", padx=5, pady=(0, 5))
        self.resistance_display_label = tk.Label(
            aux_row,
            text="Resistance: ---",
            font=FONTS["mono_small"],
            fg=COLORS["fg_primary"],
            bg=COLORS["bg_input"],
            relief="solid",
            borderwidth=1,
            padx=8,
            pady=3,
            anchor="w",
        )
        self.resistance_display_label.pack(side="left", fill="x", expand=True)
        self.resistance_current_display_label = tk.Label(
            aux_row,
            text="R current: ---",
            font=FONTS["mono_small"],
            fg=COLORS["fg_primary"],
            bg=COLORS["bg_input"],
            relief="solid",
            borderwidth=1,
            padx=8,
            pady=3,
            anchor="w",
        )
        self.resistance_current_display_label.pack(side="left", fill="x", expand=True, padx=(6, 0))
        self.resistance_display_label.bind("<Double-Button-1>", lambda _e: self._open_iv_resistance_popup())
        self.resistance_current_display_label.bind("<Double-Button-1>", lambda _e: self._open_iv_resistance_popup())

        prog_row = ttk.LabelFrame(rd, text="IV Progress")
        prog_row.pack(fill="x", anchor="w", padx=5, pady=(0, 5))
        ttk.Progressbar(
            prog_row,
            orient="horizontal",
            mode="determinate",
            maximum=100.0,
            variable=self.iv_progress_value,
            style=self.iv_progress_style,
        ).pack(fill="x", padx=6, pady=(6, 2))
        ttk.Label(prog_row, textvariable=self.iv_progress_text).pack(anchor="w", padx=6, pady=(0, 6))

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

    def _update_terminal_button_text(self) -> None:
        terminal = str(self.k2450_terminals.get()).strip().upper()
        if terminal not in {"REAR", "FRONT"}:
            terminal = "REAR"
            self.k2450_terminals.set(terminal)
        next_terminal = "FRONT" if terminal == "REAR" else "REAR"
        self.k2450_terminal_button_text.set(f"Panel: {terminal} (switch to {next_terminal})")

    def _on_terminal_button_pressed(self) -> None:
        terminal = str(self.k2450_terminals.get()).strip().upper()
        self.k2450_terminals.set("FRONT" if terminal != "FRONT" else "REAR")
        self._update_terminal_button_text()
        self._apply_terminal_selection()

    def _on_terminal_selected(self, _event: tk.Event | None = None) -> None:
        self._update_terminal_button_text()
        self._apply_terminal_selection()

    def _apply_terminal_selection(self) -> None:
        terminal = str(self.k2450_terminals.get()).strip().upper()
        if terminal not in {"REAR", "FRONT"}:
            terminal = "REAR"
            self.k2450_terminals.set(terminal)
        self._update_terminal_button_text()

        if not self.app.bus.is_connected(INST_KEITHLEY2450):
            self.k2450_active_terminal.set("Disconnected")
            if hasattr(self, "status_text"):
                self._append_status(f"K2450 terminals set to {terminal} (will apply on connect).")
            return

        try:
            self.app.bus.execute(
                INST_KEITHLEY2450,
                "configure_terminals_and_sense",
                terminals=terminal,
                remote_sense=True,
            )
            if hasattr(self, "status_text"):
                self._append_status(f"K2450 terminals switched to {terminal}.")
            self.app.ui_bus.post_log(f"K2450 terminals switched to {terminal}")
            self._refresh_terminal_readback()
        except Exception as exc:
            post_error = getattr(self.app, "post_instrument_error", None)
            if callable(post_error):
                post_error("hall", str(exc))
            elif hasattr(self, "status_text"):
                self._append_status(str(exc), is_error=True)
            self.app.ui_bus.post_log(f"K2450 terminal switch error: {exc}")

    def _refresh_terminal_readback(self) -> None:
        if not self.app.bus.is_connected(INST_KEITHLEY2450):
            self.k2450_active_terminal.set("Disconnected")
            return

        try:
            reported = self.app.bus.execute(INST_KEITHLEY2450, "get_terminals")
            text = str(reported).strip().upper().replace('"', "")
            if "FRONT" in text:
                normalized = "FRONT"
            elif "REAR" in text:
                normalized = "REAR"
            else:
                normalized = text or "UNKNOWN"
            self.k2450_active_terminal.set(normalized)
            self.k2450_terminals.set("FRONT" if normalized == "FRONT" else "REAR")
            self._update_terminal_button_text()
        except Exception:
            self.k2450_active_terminal.set("Unknown")

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

    def _open_iv_resistance_popup(self) -> None:
        popup = tk.Toplevel(self.app.root)
        popup.title("K2450 IV / Resistance Control")
        popup.transient(self.app.root)
        popup.attributes("-topmost", True)

        body = ttk.Frame(popup, padding=10)
        body.pack(fill="both", expand=True)

        # --- Resistance ---
        rf = ttk.LabelFrame(body, text="Resistance")
        rf.pack(fill="x", padx=2, pady=2)
        ttk.Label(rf, text="Current (mA):").grid(row=0, column=0, sticky="w", padx=5, pady=2)
        ttk.Entry(rf, textvariable=self.k2450_resistance_current_mA, width=10).grid(row=0, column=1, padx=5, pady=2)
        ttk.Label(rf, text="Compliance (V):").grid(row=0, column=2, sticky="w", padx=5, pady=2)
        ttk.Entry(rf, textvariable=self.k2450_resistance_compliance_v, width=10).grid(row=0, column=3, padx=5, pady=2)
        ttk.Label(rf, text="NPLC:").grid(row=1, column=0, sticky="w", padx=5, pady=2)
        ttk.Entry(rf, textvariable=self.k2450_resistance_nplc, width=10).grid(row=1, column=1, padx=5, pady=2)
        ttk.Label(rf, text="Settle (s):").grid(row=1, column=2, sticky="w", padx=5, pady=2)
        ttk.Entry(rf, textvariable=self.k2450_resistance_settle, width=10).grid(row=1, column=3, padx=5, pady=2)
        ttk.Button(rf, text="Measure Resistance", command=self._on_measure_resistance).grid(row=2, column=0, columnspan=4, pady=4)

        # --- IV Curve ---
        ivf = ttk.LabelFrame(body, text="IV Curve")
        ivf.pack(fill="x", padx=2, pady=6)
        ttk.Label(ivf, text="Shape:").grid(row=0, column=0, sticky="w", padx=5, pady=2)
        ttk.OptionMenu(
            ivf,
            self.k2450_iv_shape,
            self.k2450_iv_shape.get(),
            "start_min_max_start",
            "start_max_min_start",
            "start_min_start",
            "start_max_start",
        ).grid(row=0, column=1, sticky="w", padx=5, pady=2)
        ttk.Label(ivf, text="Mode:").grid(row=0, column=2, sticky="w", padx=5, pady=2)
        ttk.OptionMenu(ivf, self.k2450_iv_mode, self.k2450_iv_mode.get(), "current", "voltage").grid(row=0, column=3, padx=5, pady=2)

        ttk.Label(ivf, text="Start (mA/V):").grid(row=1, column=0, sticky="w", padx=5, pady=2)
        ttk.Entry(ivf, textvariable=self.k2450_iv_start, width=10).grid(row=1, column=1, padx=5, pady=2)
        ttk.Label(ivf, text="Min (mA/V):").grid(row=1, column=2, sticky="w", padx=5, pady=2)
        ttk.Entry(ivf, textvariable=self.k2450_iv_min, width=10).grid(row=1, column=3, padx=5, pady=2)

        ttk.Label(ivf, text="Max (mA/V):").grid(row=2, column=0, sticky="w", padx=5, pady=2)
        ttk.Entry(ivf, textvariable=self.k2450_iv_max, width=10).grid(row=2, column=1, padx=5, pady=2)
        ttk.Label(ivf, text="Step (mA/V):").grid(row=2, column=2, sticky="w", padx=5, pady=2)
        ttk.Entry(ivf, textvariable=self.k2450_iv_step, width=10).grid(row=2, column=3, padx=5, pady=2)

        ttk.Label(ivf, text="Compliance:").grid(row=3, column=0, sticky="w", padx=5, pady=2)
        ttk.Entry(ivf, textvariable=self.k2450_iv_compliance, width=10).grid(row=3, column=1, padx=5, pady=2)
        ttk.Label(ivf, text="NPLC:").grid(row=3, column=2, sticky="w", padx=5, pady=2)
        ttk.Entry(ivf, textvariable=self.k2450_iv_nplc, width=10).grid(row=3, column=3, padx=5, pady=2)

        ttk.Label(ivf, text="Settle (s):").grid(row=4, column=0, sticky="w", padx=5, pady=2)
        ttk.Entry(ivf, textvariable=self.k2450_iv_settle, width=10).grid(row=4, column=1, padx=5, pady=2)
        ttk.Label(ivf, text="Repetitions:").grid(row=4, column=2, sticky="w", padx=5, pady=2)
        ttk.Entry(ivf, textvariable=self.k2450_iv_repetitions, width=10).grid(row=4, column=3, padx=5, pady=2)

        ttk.Checkbutton(ivf, text="Ramp", variable=self.k2450_iv_ramp_to_start).grid(row=5, column=0, columnspan=2, sticky="w", padx=5, pady=2)
        ttk.Label(ivf, text="Env sample interval (s):").grid(row=5, column=2, sticky="w", padx=5, pady=2)
        ttk.Entry(ivf, textvariable=self.k2450_iv_env_interval, width=10).grid(row=5, column=3, padx=5, pady=2)
        ttk.Button(ivf, text="Measure IV Curve", command=self._on_measure_iv_curve).grid(row=6, column=0, columnspan=4, pady=4)

        ttk.Button(body, text="Close", command=popup.destroy).pack(anchor="e", pady=(8, 0))
        self._center_toplevel(popup, width=580, height=510)

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
            if bool(value):
                self._refresh_terminal_readback()
            if not bool(value):
                self._set_source_enabled(False)
                self.k2450_active_terminal.set("Disconnected")
        elif widget_id == W_HALL_SOURCE_ENABLED:
            self._set_source_enabled(bool(value))
        elif widget_id == W_IV_PROGRESS:
            if isinstance(value, dict):
                current = int(value.get("current", 0))
                total = max(int(value.get("total", 1)), 1)
                percent = float(value.get("percent", (100.0 * current / total)))
                active = bool(value.get("active", False))
                elapsed_s = max(0.0, float(value.get("elapsed_s", 0.0)))
                estimated_total_s = max(0.0, float(value.get("estimated_total_s", 0.0)))
                self.iv_progress_value.set(max(0.0, min(100.0, percent)))
                if active:
                    if estimated_total_s > 0.0:
                        self.iv_progress_text.set(
                            f"IV progress: {elapsed_s:.1f}/{estimated_total_s:.1f} s ({percent:.0f}%) [{current}/{total} pts]"
                        )
                    else:
                        self.iv_progress_text.set(f"IV progress: {current}/{total} points ({percent:.0f}%)")
                elif current > 0:
                    if estimated_total_s > 0.0:
                        self.iv_progress_text.set(
                            f"IV done: {elapsed_s:.1f} s (est {estimated_total_s:.1f} s), {current} points"
                        )
                    else:
                        self.iv_progress_text.set(f"IV done: {current} points")
                else:
                    self.iv_progress_text.set("IV progress: idle")
        elif widget_id == W_INSTRUMENT_ERROR:
            if isinstance(value, dict) and str(value.get("instrument")) == "hall":
                self._append_status(str(value.get("message", "Unknown error")), is_error=True)

    def on_instrument_connected(self, name: str) -> None:
        if name == "hall" and self._conn_header:
            self._conn_header.set_connected(True)
            self._refresh_terminal_readback()

    def on_instrument_disconnected(self, name: str) -> None:
        if name == "hall" and self._conn_header:
            self._conn_header.set_connected(False)
            self._set_source_enabled(False)
            self.k2450_active_terminal.set("Disconnected")
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

    def _stop_iv_progress_pulse(self) -> None:
        self._iv_progress_active = False
        if self._iv_progress_after_id is not None:
            try:
                self.app.root.after_cancel(self._iv_progress_after_id)
            except Exception:
                pass
            self._iv_progress_after_id = None

    def _start_iv_progress_pulse(self, *, started_at: float, estimated_total_s: float, point_total: int) -> None:
        self._stop_iv_progress_pulse()
        self._iv_progress_active = True

        def _pulse() -> None:
            if not self._iv_progress_active:
                return

            elapsed_s = max(0.0, time.perf_counter() - started_at)
            if estimated_total_s > 0.0:
                percent = min(99.0, 100.0 * elapsed_s / estimated_total_s)
            else:
                percent = 0.0

            approx_current = 0
            if point_total > 0 and estimated_total_s > 0.0:
                approx_current = max(1, min(point_total, int(round(point_total * percent / 100.0))))

            self.app.ui_bus.post(
                W_IV_PROGRESS,
                {
                    "current": approx_current,
                    "total": max(point_total, 1),
                    "percent": percent,
                    "active": True,
                    "elapsed_s": elapsed_s,
                    "estimated_total_s": estimated_total_s,
                },
            )

            if self._iv_progress_active:
                try:
                    self._iv_progress_after_id = self.app.root.after(100, _pulse)
                except Exception:
                    self._iv_progress_active = False

        try:
            self._iv_progress_after_id = self.app.root.after(0, _pulse)
        except Exception:
            self._iv_progress_active = False

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

    def _on_measure_resistance(self) -> None:
        try:
            if float(self.k2450_resistance_current_mA.get()) <= 0.0:
                raise ValueError("Resistance current must be > 0 mA")
        except Exception as exc:
            self._append_status(str(exc), is_error=True)
            self.app.ui_bus.post_log(f"Resistance measure error: {exc}")
            return
        if self._measuring:
            self.app.ui_bus.post_log("K2450 measurement already in progress.")
            return
        self._measuring = True
        self._set_measure_buttons_enabled(False)
        t = threading.Thread(target=self._measure_resistance_worker, daemon=True, name="hall-resistance-measure")
        t.start()

    def _on_measure_iv_curve(self) -> None:
        if self._measuring:
            self.app.ui_bus.post_log("K2450 measurement already in progress.")
            return

        self._measuring = True
        self._set_measure_buttons_enabled(False)

        try:
            start = float(self.k2450_iv_start.get())
            iv_min = float(self.k2450_iv_min.get())
            iv_max = float(self.k2450_iv_max.get())
            step = float(self.k2450_iv_step.get())
            if abs(step) < 1e-15:
                raise ValueError("IV step must be non-zero")
            if iv_min >= iv_max:
                raise ValueError("IV min must be smaller than IV max")
            if not (iv_min < start < iv_max):
                raise ValueError("IV start must be larger than min and smaller than max")
        except Exception as exc:
            self._append_status(str(exc), is_error=True)
            self.app.ui_bus.post_log(f"IV measure error: {exc}")
            self._measure_done()
            return
        try:
            t = threading.Thread(target=self._measure_iv_worker, daemon=True, name="hall-iv-measure")
            t.start()
        except Exception as exc:
            self._append_status(f"Could not start IV worker: {exc}", is_error=True)
            self.app.ui_bus.post_log(f"IV worker start error: {exc}")
            self._measure_done()

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

    def _measure_resistance_worker(self) -> None:
        try:
            from v3.core.measurements import measure_resistance
            ctx = self.app.make_context()
            self.app.ui_bus.post(W_LED_HALL, True)
            self.app.root.after(0, lambda: set_led(self.source_led, True))

            voltage_range_raw = str(self.k2450_resistance_voltage_range.get())
            auto_range = voltage_range_raw.lower() == "auto"
            voltage_range = None if auto_range else float(voltage_range_raw)
            current_a = float(self.k2450_resistance_current_mA.get()) / 1000.0
            result = measure_resistance(
                ctx,
                current=current_a,
                compliance=float(self.k2450_resistance_compliance_v.get()),
                nplc=float(self.k2450_resistance_nplc.get()),
                voltage_range=voltage_range,
                auto_range=auto_range,
                settle_time=float(self.k2450_resistance_settle.get()),
                repetitions=int(self.k2450_resistance_repetitions.get()),
            )
            ctx.data_mgr.write_row(result, measurement_type="Resistance")
            self.app.ui_bus.post(W_RESULTS_NEW_POINT, True)

            resistance = float(result.get("Sample_Resistance", 0.0))
            resistance_error = abs(float(result.get("Sample_Resistance_Error", 0.0)))
            measured_v = float(result.get("IV_Measured_Voltage", 0.0))

            def _apply() -> None:
                self.k2450_aux_result.configure(text=f"R: {resistance:.6e} +/- {resistance_error:.2e} Ohm (V={measured_v:.3e})")
                self.resistance_display_label.configure(text=f"Resistance: {resistance:.6e} +/- {resistance_error:.2e} Ohm")
                self.resistance_current_display_label.configure(text=f"R current: {current_a * 1000.0:.3f} mA")
                self._append_status(f"Measured resistance: {resistance:.6e} Ohm")
                self.app.ui_bus.post_log(f"K2450 resistance: {resistance:.6e} Ohm")

            self.app.root.after(0, _apply)
        except Exception as exc:
            def _show_error() -> None:
                self._append_status(f"Resistance measurement failed: {exc}", is_error=True)
                self.app.ui_bus.post_log(f"Resistance measure error: {exc}")

            self.app.root.after(0, _show_error)
        finally:
            try:
                self.app.ui_bus.post(W_LED_HALL, False)
                _src = self._source_enabled
                self.app.root.after(0, lambda: set_led(self.source_led, _src))
                self.app.root.after(0, self._measure_done)
            except Exception:
                self._measuring = False

    def _measure_iv_worker(self) -> None:
        try:
            from v3.core.measurements import _build_iv_setpoints_with_directions, estimate_iv_curve_duration, measure_iv_curve
            ctx = self.app.make_context()
            self.app.ui_bus.post(W_LED_HALL, True)
            self.app.root.after(0, lambda: set_led(self.source_led, True))
            t0 = time.perf_counter()

            try:
                self.app.bus.execute(INST_KEITHLEY2450, "set_iv_display_mode")
            except Exception:
                pass

            source_range_raw = str(self.k2450_iv_source_range.get())
            measure_range_raw = str(self.k2450_iv_measure_range.get())
            source_range = None if source_range_raw.lower() == "auto" else float(source_range_raw)
            measure_range = None if measure_range_raw.lower() == "auto" else float(measure_range_raw)
            iv_auto_range = measure_range is None

            iv_mode = str(self.k2450_iv_mode.get())
            mode_norm = iv_mode.strip().lower()
            _ma_to_a = 1e-3 if mode_norm in {"current", "source_current", "i"} else 1.0
            if source_range is not None and mode_norm in {"current", "source_current", "i"}:
                source_range *= 1e-3
            if measure_range is not None and mode_norm in {"voltage", "source_voltage", "v"}:
                measure_range *= 1e-3
            ramp_enabled = bool(self.k2450_iv_ramp_to_start.get())
            start_native = float(self.k2450_iv_start.get()) * _ma_to_a
            min_native = float(self.k2450_iv_min.get()) * _ma_to_a
            max_native = float(self.k2450_iv_max.get()) * _ma_to_a
            step_native = float(self.k2450_iv_step.get()) * _ma_to_a
            try:
                estimated_points = len(
                    _build_iv_setpoints_with_directions(
                        start_native,
                        max_native,
                        step_native,
                        shape=str(self.k2450_iv_shape.get()),
                        iv_min=min_native,
                        iv_max=max_native,
                    )[0]
                )
            except Exception:
                estimated_points = 1
            estimated_total_s = estimate_iv_curve_duration(
                shape=str(self.k2450_iv_shape.get()),
                start=start_native,
                step=step_native,
                iv_min=min_native,
                iv_max=max_native,
                nplc=float(self.k2450_iv_nplc.get()),
                settle_time=float(self.k2450_iv_settle.get()),
                repetitions=int(self.k2450_iv_repetitions.get()),
                ramp_to_start=ramp_enabled,
                reset_to_zero=ramp_enabled,
            )
            self._start_iv_progress_pulse(
                started_at=t0,
                estimated_total_s=estimated_total_s,
                point_total=estimated_points,
            )

            result = measure_iv_curve(
                ctx,
                mode=iv_mode,
                shape=str(self.k2450_iv_shape.get()),
                start=start_native,
                iv_min=min_native,
                iv_max=max_native,
                step=step_native,
                source_range=source_range,
                measure_range=measure_range,
                compliance=float(self.k2450_iv_compliance.get()),
                nplc=float(self.k2450_iv_nplc.get()),
                auto_range=iv_auto_range,
                settle_time=float(self.k2450_iv_settle.get()),
                repetitions=int(self.k2450_iv_repetitions.get()),
                keep_output=False,
                reset_to_zero=ramp_enabled,
                ramp_to_start=ramp_enabled,
                env_sample_interval=float(self.k2450_iv_env_interval.get()),
                on_progress=lambda current, total: self.app.ui_bus.post(
                    W_IV_PROGRESS,
                    {
                        "current": int(current),
                        "total": max(int(total), 1),
                        "percent": (
                            min(
                                99.0,
                                100.0 * max(0.0, time.perf_counter() - t0) / estimated_total_s,
                            )
                            if estimated_total_s > 0.0
                            else (100.0 * float(current) / float(max(total, 1)))
                        ),
                        "active": True,
                        "elapsed_s": max(0.0, time.perf_counter() - t0),
                        "estimated_total_s": estimated_total_s,
                    },
                ),
            )

            if not isinstance(result, dict):
                raise RuntimeError(f"Invalid IV result payload type: {type(result).__name__}")

            try:
                rows = result.get("points", [])
                if isinstance(rows, tuple):
                    rows = list(rows)
                elif not isinstance(rows, list):
                    rows = []

                wrote = ctx.data_mgr.write_rows(rows, measurement_type="IV")
                if wrote > 0:
                    self.app.ui_bus.post(W_RESULTS_NEW_POINT, True)

                elapsed_s = max(0.0, time.perf_counter() - t0)
                engine = str(result.get("engine", "point")).strip().lower()
                engine_msg = (
                    "IV engine: instrument-side fast sweep"
                    if engine == "fast"
                    else "IV engine: point-by-point fallback"
                )

                def _apply() -> None:
                    point_count = int(result.get("point_count", 0))
                    self.k2450_aux_result.configure(text=f"IV: {point_count} points")
                    self._append_status(
                        f"Recorded IV curve with {point_count} points in {elapsed_s:.2f} s"
                    )
                    self._append_status(engine_msg)
                    self.app.ui_bus.post_log(
                        f"IV recorded: {point_count} points in {elapsed_s:.2f} s"
                    )
                    self.app.ui_bus.post_log(
                        f"K2450 IV curve recorded: {point_count} points in {elapsed_s:.2f} s "
                        f"(engine={result.get('engine', 'point')})"
                    )
                    self.app.ui_bus.post_log(f"K2450 {engine_msg}")
                    self.app.ui_bus.post(
                        W_IV_PROGRESS,
                        {
                            "current": point_count,
                            "total": max(point_count, 1),
                            "percent": 100.0,
                            "active": False,
                            "elapsed_s": elapsed_s,
                            "estimated_total_s": estimated_total_s,
                        },
                    )

                self.app.root.after(0, _apply)
            except Exception:
                logger.exception("IV post-processing failed")
                self.app.ui_bus.post_log("IV post-processing warning: measurement finished, but result handling had an issue")
        except Exception as exc:
            exc_text = str(exc)
            logger.error("IV measurement worker failed: %s", exc_text)
            logger.debug("IV measurement traceback:\n%s", traceback.format_exc())
            def _show_error() -> None:
                self._append_status(f"IV measurement failed: {exc_text}", is_error=True)
                self.app.ui_bus.post_log(f"IV measure error: {exc_text}")
                self.app.ui_bus.post(
                    W_IV_PROGRESS,
                    {
                        "current": 0,
                        "total": 1,
                        "percent": 0.0,
                        "active": False,
                        "elapsed_s": max(0.0, time.perf_counter() - t0),
                    },
                )

            self.app.root.after(0, _show_error)
        finally:
            try:
                self._stop_iv_progress_pulse()
                self.app.ui_bus.post(W_LED_HALL, False)
                _src = self._source_enabled
                self.app.root.after(0, lambda: set_led(self.source_led, _src))
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
