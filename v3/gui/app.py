"""
v3.gui.app  —  Main application class for the v3 experiment GUI.

Owns all core subsystems and wires them to the Tkinter GUI via a
notebook of tab modules.

Architecture
------------
* Core objects are created once in ``__init__`` and shared with tabs.
* ``update_ui()`` runs every 100 ms on the main thread — it drains the
  ``UIEventBus`` and dispatches events to each tab.
* Instrument connections go through ``InstrumentBus``.
* Script execution goes through ``ExperimentEngine``.
* Dyna (PPMS) polling runs on a background daemon thread.
"""

from __future__ import annotations

import logging
import math
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk
from typing import Any

from v3.core.calibration import CalibrationConfig
from v3.core.constants import (
    DEFAULT_DATA_DIR,
    DEFAULT_LOG_DIR,
    DYNA_HOST,
    DYNA_PORT,
    DYNA_COOLING_CONFIRM_THRESHOLD_K,
    INST_DYNA,
    INST_KEITHLEY2450,
    INST_KEITHLEY2600,
    INST_LOCKIN,
    INST_SWITCH,
    KEITHLEY2450_ADDRESS,
    KEITHLEY2600_ADDRESS,
    LOCKIN_ADDRESS,
    LOGICAL_CHANNELS,
    MAX_SWITCH_CONFIGS,
    MIN_SWITCH_CONFIGS,
    SWITCH_ADDRESS_7001,
    SWITCH_ADDRESS_MY,
    SWITCH_ADDRESS,
    SWITCH_BACKEND,
    UI_TICK_INTERVAL_MS,
)
from v3.core.data_manager import DataManager
from v3.core.experiment_engine import EngineStateError, ExperimentEngine
from v3.core.helmholtz_controller import HelmholtzController
from v3.core.instrument_bus import InstrumentBus
from v3.core.measurements import MeasurementContext
from v3.core.script_parser import ScriptParser, ScriptValidator
from v3.core.ui_events import (
    UIEventBus,
    W_DYNA_CHAMBER,
    W_DYNA_CHAMBER_STATUS,
    W_DYNA_CONNECTED,
    W_DYNA_FIELD,
    W_DYNA_FIELD_STATUS,
    W_DYNA_TEMP,
    W_DYNA_TEMP_STATUS,
    W_HALL_CONNECTED,
    W_HELMHOLTZ_CONNECTED,
    W_INSTRUMENT_CONNECTED,
    W_INSTRUMENT_DISCONNECTED,
    W_INSTRUMENT_ERROR,
    W_LED_DYNA,
    W_LED_HALL,
    W_LED_HELMHOLTZ,
    W_LED_LOCKIN,
    W_LED_SWITCH,
    W_LOCKIN_CONNECTED,
    W_SWITCH_CONNECTED,
)

# Lazy imports for tabs (avoid circular)
from v3.gui.dyna_tab import DynaTab
from v3.gui.hall_tab import HallTab
from v3.gui.helmholtz_tab import HelmholtzTab
from v3.gui.lockin_tab import LockInTab
from v3.gui.results_tab import ResultsTab
from v3.gui.switch_tab import SwitchTab
from v3.gui.components import NotificationToast
from v3.gui.theme import apply_theme

logger = logging.getLogger(__name__)

# Map user-facing instrument keys → canonical bus names
_KEY_TO_BUS: dict[str, str] = {
    "helmholtz": INST_KEITHLEY2600,
    "hall": INST_KEITHLEY2450,
    "dyna": INST_DYNA,
    "lockin": INST_LOCKIN,
    "switch": INST_SWITCH,
}

# Map user-facing keys → LED widget IDs
_KEY_TO_LED: dict[str, str] = {
    "helmholtz": W_LED_HELMHOLTZ,
    "hall": W_LED_HALL,
    "dyna": W_LED_DYNA,
    "lockin": W_LED_LOCKIN,
    "switch": W_LED_SWITCH,
}

# Map user-facing keys → connected widget IDs
_KEY_TO_CONN: dict[str, str] = {
    "helmholtz": W_HELMHOLTZ_CONNECTED,
    "hall": W_HALL_CONNECTED,
    "dyna": W_DYNA_CONNECTED,
    "lockin": W_LOCKIN_CONNECTED,
    "switch": W_SWITCH_CONNECTED,
}

_DYNA_TEMP_STATES: dict[int, str] = {
    1: "Stable",
    2: "Tracking",
    5: "Near",
    6: "Chasing",
    7: "Pot Operation",
    10: "Standby",
    13: "Diagnostic",
    14: "Impedance Control Error",
    15: "General Failure",
}

_DYNA_FIELD_STATES: dict[int, str] = {
    1: "Stable",
    2: "Switch Warming",
    3: "Switch Cooling",
    4: "Holding",
    5: "Iterate",
    6: "Ramping",
    7: "Ramping",
    8: "Resetting",
    9: "Current Error",
    10: "Switch Error",
    11: "Quenching",
    12: "Charging Error",
    14: "PSU Error",
    15: "General Failure",
}

_DYNA_CHAMBER_STATES: dict[int, str] = {
    0: "Unknown",
    1: "Purged and Sealed",
    2: "Vented and Sealed",
    3: "Sealed",
    4: "Purging/Sealing",
    5: "Venting/Sealing",
    6: "Pre-HiVac",
    7: "HiVac",
    8: "Pumping",
    9: "Flooding",
    14: "HiVac Error",
    15: "General Failure",
}


class MeasureApp:
    """Main application — owns all subsystems and the Tkinter root."""

    # These are injected from outside (or defaulted) so tests can
    # provide mock classes without touching real hardware.
    USE_MOCKUP: bool = False

    def __init__(self, root: tk.Tk, *, use_mockup: bool = False) -> None:
        self.root = root
        self.USE_MOCKUP = use_mockup
        self.root.title("Keithley and Dyna Controller GUI")
        apply_theme(self.root)

        # ==============================================================
        # Core subsystems
        # ==============================================================
        self.calibration = CalibrationConfig()
        self.ui_bus = UIEventBus()
        self.bus = InstrumentBus()
        self.data_mgr = DataManager(
            data_dir=DEFAULT_DATA_DIR,
            log_dir=DEFAULT_LOG_DIR,
        )
        self.helmholtz = HelmholtzController(
            bus=self.bus,
            ui_bus=self.ui_bus,
            calibration=self.calibration,
        )
        self.engine = ExperimentEngine(
            ui_bus=self.ui_bus,
            on_abort_cleanup=self._abort_cleanup,
        )
        self.parser = ScriptParser()
        self.validator = ScriptValidator()

        # ==============================================================
        # Dyna (PPMS) poller
        # ==============================================================
        self._dyna_snapshot_lock = threading.Lock()
        self._dyna_snapshot: dict[str, Any] = {
            "temp_val": None,
            "field_val": None,
            "chamber_val": None,
            "temp_text": "N/A",
            "field_text": "N/A",
            "chamber_text": "N/A",
            "temp_status": "N/A",
            "field_status": "N/A",
            "chamber_status": "N/A",
        }
        self._dyna_poller_stop = threading.Event()
        self._dyna_poller_thread: threading.Thread | None = None

        # ==============================================================
        # Connection state
        # ==============================================================
        self.instrument_connected: dict[str, bool] = {
            k: False for k in _KEY_TO_BUS
        }

        # ==============================================================
        # Misc state
        # ==============================================================
        self._update_ui_id: str | None = None
        self._pending_callbacks: list[str] = []
        self._shutting_down = False
        self._active_toasts: list[NotificationToast] = []
        self.current_temp: float | None = None
        self.current_inplane_field: float | None = None

        # Auto-log tracking
        self.auto_log_enabled = tk.BooleanVar(value=True)

        # Plot time-series data (used by results tab)
        self.helmholtz_time_data: list[float] = []
        self.helmholtz_res_a: list[float] = []
        self.helmholtz_res_b: list[float] = []
        self.dyna_time_data: list[float] = []
        self.dyna_temp_data: list[float] = []
        self.dyna_field_data: list[float] = []
        self.start_time: float = time.time()
        self.start_time_dyna: float = time.time()
        self.last_plot_time: float = 0.0
        self.last_plot_time_dyna: float = 0.0

        # Script tracking
        self.script_filename = tk.StringVar(value="script.txt")
        self.script_file_path: str | None = None
        self.script_dirty: bool = False

        # Switch channels
        self.channels = list(LOGICAL_CHANNELS[:2])
        self.channel_configs: dict[str, dict[str, tk.IntVar]] = {
            "a": {
                "I+": tk.IntVar(value=1), "V+": tk.IntVar(value=2),
                "V-": tk.IntVar(value=3), "I-": tk.IntVar(value=4),
            },
            "b": {
                "I+": tk.IntVar(value=5), "V+": tk.IntVar(value=6),
                "V-": tk.IntVar(value=7), "I-": tk.IntVar(value=8),
            },
        }
        self.active_channel: str | None = None

        # ==============================================================
        # Build the GUI
        # ==============================================================
        main_frame = ttk.Frame(self.root)
        main_frame.grid(row=0, column=0, sticky="nsew")
        self.root.grid_columnconfigure(0, weight=1)
        self.root.grid_rowconfigure(0, weight=1)

        self.notebook = ttk.Notebook(main_frame)
        self.notebook.grid(row=0, column=0, sticky="nsew")
        main_frame.grid_columnconfigure(0, weight=1)
        main_frame.grid_rowconfigure(0, weight=1)

        # Create scrollable tab frames so content remains accessible on small screens
        self._results_frame = self._create_scrollable_tab("Results")
        self._dyna_frame = self._create_scrollable_tab("Dyna")
        self._helmholtz_frame = self._create_scrollable_tab("Helmholtz")
        self._lockin_frame = self._create_scrollable_tab("LockIn")
        self._hall_frame = self._create_scrollable_tab("Hall bar")
        self._switch_frame = self._create_scrollable_tab("Switch")

        # Create tab instances
        self.results_tab = ResultsTab(self._results_frame, self)
        self.dyna_tab = DynaTab(self._dyna_frame, self)
        self.helmholtz_tab = HelmholtzTab(self._helmholtz_frame, self)
        self.lockin_tab = LockInTab(self._lockin_frame, self)
        self.hall_tab = HallTab(self._hall_frame, self)
        self.switch_tab = SwitchTab(self._switch_frame, self)

        self._all_tabs = [
            self.results_tab,
            self.dyna_tab,
            self.helmholtz_tab,
            self.lockin_tab,
            self.hall_tab,
            self.switch_tab,
        ]

        # Build widgets in every tab
        for tab in self._all_tabs:
            tab.create_widgets()

        # Start with all instrument tabs disabled until connected
        for key in _KEY_TO_BUS:
            self._set_tab_interactive_enabled(key, False)

        # ==============================================================
        # Start background services
        # ==============================================================
        self._start_dyna_poller()
        self._schedule_update_ui()
        self._initialize_auto_log_if_enabled()

        # Auto-connect all instruments at startup (matching V2 behavior)
        self.root.after(200, self._auto_connect_all)

        # Geometry and shutdown
        self.root.update_idletasks()
        # Open centered with a generous default size, still bounded by screen size
        required_width = self.root.winfo_reqwidth()
        required_height = self.root.winfo_reqheight()
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        default_width = int(screen_width * 0.85)
        default_height = int(screen_height * 0.80)
        max_width = int(screen_width * 0.97)
        max_height = int(screen_height * 0.90)
        window_width = min(max(required_width + 10, default_width), max_width)
        window_height = min(max(required_height + 10, default_height), max_height)
        self.root.minsize(820, 560)
        pos_x = max(0, (screen_width - window_width) // 2)
        pos_y = max(0, (screen_height - window_height) // 2)
        self.root.geometry(f"{window_width}x{window_height}+{pos_x}+{pos_y}")
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        if self.USE_MOCKUP:
            self.root.after(100, self._show_mockup_warning)

    def _default_channel_template(self, channel: str) -> dict[str, int]:
        """Create a default pin mapping for a logical channel."""
        index = LOGICAL_CHANNELS.index(channel)
        start_pin = 1 if index % 2 == 0 else 5
        return {
            "I+": start_pin,
            "V+": start_pin + 1,
            "V-": start_pin + 2,
            "I-": start_pin + 3,
        }

    def add_channel_config(self, channel: str | None = None, *, clone_from: str | None = None) -> str:
        """Add a logical channel configuration (max 8). Returns channel name."""
        if len(self.channels) >= MAX_SWITCH_CONFIGS:
            raise ValueError(f"Maximum of {MAX_SWITCH_CONFIGS} channel configurations reached")

        if channel is None:
            for candidate in LOGICAL_CHANNELS:
                if candidate not in self.channels:
                    channel = candidate
                    break
        if channel is None:
            raise ValueError("No available channel name")
        channel = str(channel).strip().lower()

        if channel not in LOGICAL_CHANNELS:
            raise ValueError(f"Invalid channel '{channel}'. Allowed: {', '.join(LOGICAL_CHANNELS)}")
        if channel in self.channels:
            raise ValueError(f"Channel '{channel}' already exists")

        template = self._default_channel_template(channel)
        if clone_from:
            src = str(clone_from).strip().lower()
            if src not in self.channel_configs:
                raise ValueError(f"Cannot clone from unknown channel '{src}'")
            src_cfg = self.channel_configs[src]
            template = {
                "I+": int(src_cfg["I+"].get()),
                "V+": int(src_cfg["V+"].get()),
                "V-": int(src_cfg["V-"].get()),
                "I-": int(src_cfg["I-"].get()),
            }

        self.channels.append(channel)
        self.channel_configs[channel] = {
            "I+": tk.IntVar(value=template["I+"]),
            "V+": tk.IntVar(value=template["V+"]),
            "V-": tk.IntVar(value=template["V-"]),
            "I-": tk.IntVar(value=template["I-"]),
        }
        return channel

    def remove_channel_config(self, channel: str) -> None:
        """Remove a logical channel configuration (keeps minimum of 2)."""
        if len(self.channels) <= MIN_SWITCH_CONFIGS:
            raise ValueError(f"At least {MIN_SWITCH_CONFIGS} channel configurations are required")

        token = str(channel).strip().lower()
        if token in {"a", "b"}:
            raise ValueError("Channels 'a' and 'b' are mandatory and cannot be removed")
        if token not in self.channels:
            raise ValueError(f"Unknown channel '{token}'")

        self.channels.remove(token)
        self.channel_configs.pop(token, None)
        if self.active_channel == token:
            self.active_channel = None

    def clone_channel_config(self, source_channel: str, target_channel: str) -> None:
        """Clone pin mapping from source channel to target channel."""
        src = str(source_channel).strip().lower()
        dst = str(target_channel).strip().lower()
        if src not in self.channel_configs or dst not in self.channel_configs:
            raise ValueError("Source and target channels must exist")

        src_cfg = self.channel_configs[src]
        dst_cfg = self.channel_configs[dst]
        for pin in ("I+", "V+", "V-", "I-"):
            dst_cfg[pin].set(int(src_cfg[pin].get()))

    def _create_scrollable_tab(self, title: str) -> ttk.Frame:
        """Create a notebook tab with scrollbars; returns the inner content frame."""
        container = ttk.Frame(self.notebook)
        container.grid_rowconfigure(0, weight=1)
        container.grid_columnconfigure(0, weight=1)

        canvas = tk.Canvas(container, highlightthickness=0)
        v_scroll = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
        h_scroll = ttk.Scrollbar(container, orient="horizontal", command=canvas.xview)
        canvas.configure(yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set)

        canvas.grid(row=0, column=0, sticky="nsew")
        v_scroll.grid(row=0, column=1, sticky="ns")
        h_scroll.grid(row=1, column=0, sticky="ew")

        content = ttk.Frame(canvas)
        content_window = canvas.create_window((0, 0), window=content, anchor="nw")

        def _update_scrollregion(_event: Any | None = None) -> None:
            canvas.configure(scrollregion=canvas.bbox("all"))

        def _on_canvas_resize(event: tk.Event) -> None:
            # Keep content at least as wide as viewport while still allowing horizontal scrolling
            req_width = content.winfo_reqwidth()
            canvas.itemconfigure(content_window, width=max(event.width, req_width))

        content.bind("<Configure>", _update_scrollregion)
        canvas.bind("<Configure>", _on_canvas_resize)

        self.notebook.add(container, text=title)
        return content

    # ==================================================================
    # Measurement context (passed to measurement functions)
    # ==================================================================
    def _sync_hall_calibration_from_ui(self) -> None:
        """Keep core Hall calibration aligned with Hall tab settings."""
        try:
            hall_offset_v = float(self.hall_tab.k2450_hall_offset.get())
            hall_v2gauss = float(self.hall_tab.k2450_hall_v2gauss.get())

            self.calibration.hall_offset_v = hall_offset_v
            self.calibration.hall_v2gauss = hall_v2gauss

            hall_bar = str(self.hall_tab.k2450_hall_bar.get()).strip()
            v_per_g = None
            if hall_v2gauss != 0.0:
                v_per_g = 1.0 / hall_v2gauss

            self.data_mgr.set_hall_metadata(
                hall_bar=hall_bar,
                v_per_g=v_per_g,
                hall_offset_v=hall_offset_v,
            )
        except Exception:
            pass

    def make_context(self) -> MeasurementContext:
        """Build a MeasurementContext from current state."""
        self._sync_hall_calibration_from_ui()
        return MeasurementContext(
            bus=self.bus,
            ui_bus=self.ui_bus,
            data_mgr=self.data_mgr,
            helmholtz=self.helmholtz,
            calibration=self.calibration,
            get_temp=lambda: float("nan") if self.current_temp is None else self.current_temp,
            get_ppms_field=lambda: float("nan") if self.current_inplane_field is None else self.current_inplane_field,
            get_active_channel=lambda: self.active_channel,
        )

    def _set_tab_interactive_enabled(self, key: str, enabled: bool) -> None:
        """Enable/disable interactive widgets in a tab (V2-style graying)."""
        frame_map = {
            "helmholtz": self._helmholtz_frame,
            "hall": self._hall_frame,
            "dyna": self._dyna_frame,
            "lockin": self._lockin_frame,
            "switch": self._switch_frame,
        }
        tab_map = {
            "helmholtz": self.helmholtz_tab,
            "hall": self.hall_tab,
            "dyna": self.dyna_tab,
            "lockin": self.lockin_tab,
            "switch": self.switch_tab,
        }
        root = frame_map.get(key)
        tab = tab_map.get(key)
        if root is None or tab is None:
            return

        protected: set[Any] = set()
        header = getattr(tab, "_conn_header", None)
        if header is not None:
            protected.update({header.button, header.status_label, header.led})

        def _apply(widget: Any) -> None:
            if widget in protected:
                return
            for child in widget.winfo_children():
                _apply(child)
            try:
                cls = str(widget.winfo_class())
                if cls in {"Button", "TButton", "Entry", "TEntry", "Spinbox", "TCombobox", "Checkbutton", "TCheckbutton", "Text"}:
                    widget.configure(state=("normal" if enabled else "disabled"))
            except Exception:
                pass

        _apply(root)

    # ==================================================================
    # Instrument connection / disconnection
    # ==================================================================
    def _show_toast(self, message: str, *, level: str = "info", duration_ms: int = 4000) -> None:
        """Show a short-lived notification in the lower-right corner."""
        msg = str(message).strip()
        if not msg:
            return

        if len(msg) > 220:
            msg = msg[:217] + "..."

        # Drop stale handles.
        self._active_toasts = [
            t for t in self._active_toasts if t.win is not None and t.win.winfo_exists()
        ]

        toast = NotificationToast(
            self.root,
            message=msg,
            level=level,
            duration_ms=duration_ms,
        )
        toast.show(y_offset=len(self._active_toasts) * 44)
        self._active_toasts.append(toast)

    def post_instrument_error(self, key: str, message: str) -> None:
        """Post an instrument-specific error to both system and instrument views."""
        payload = {
            "instrument": str(key),
            "message": str(message),
        }
        self.ui_bus.post(W_INSTRUMENT_ERROR, payload)
        self._show_toast(f"{key}: {message}", level="error", duration_ms=5000)
        if str(key) == "dyna":
            self.ui_bus.post_dyna_log(f"Error: {message}")

    def connect_instrument(self, key: str) -> bool:
        """Connect an instrument by user-facing key.

        Returns True on success, False on failure.
        """
        if self.instrument_connected.get(key, False) and self.bus.is_connected(_KEY_TO_BUS[key]):
            return True
        try:
            bus_name = _KEY_TO_BUS[key]
            handlers = {
                "helmholtz": self._connect_helmholtz,
                "hall": self._connect_hall,
                "dyna": self._connect_dyna,
                "lockin": self._connect_lockin,
                "switch": self._connect_switch,
            }
            success = handlers[key]()
            if success:
                self.instrument_connected[key] = True
                self.ui_bus.post(W_INSTRUMENT_CONNECTED, key)
                for tab in self._all_tabs:
                    tab.on_instrument_connected(key)
                self._set_tab_interactive_enabled(key, True)
                self.ui_bus.post_log(f"{key} connected.")
            return success
        except Exception as exc:  # noqa: BLE001
            logger.exception("Failed to connect %s", key)
            self.post_instrument_error(key, str(exc))
            self.ui_bus.post_log(f"Connection error ({key}): {exc}")
            return False

    def disconnect_instrument(self, key: str) -> None:
        """Disconnect an instrument by user-facing key."""
        try:
            handlers = {
                "helmholtz": self._disconnect_helmholtz,
                "hall": self._disconnect_hall,
                "dyna": self._disconnect_dyna,
                "lockin": self._disconnect_lockin,
                "switch": self._disconnect_switch,
            }
            handlers[key]()
        except Exception as exc:  # noqa: BLE001
            logger.exception("Failed to disconnect %s", key)
            self.post_instrument_error(key, str(exc))
            self.ui_bus.post_log(f"Disconnect error ({key}): {exc}")
        finally:
            self.instrument_connected[key] = False
            self.ui_bus.post(W_INSTRUMENT_DISCONNECTED, key)
            for tab in self._all_tabs:
                tab.on_instrument_disconnected(key)
            self._set_tab_interactive_enabled(key, False)
            self.ui_bus.post_log(f"{key} disconnected.")
            if self.engine.is_running:
                self.ui_bus.post_log(f"Script abort requested: required instrument '{key}' disconnected.")
                self.engine.request_stop()

    # --- Per-instrument connect/disconnect ----------------------------

    def _connect_helmholtz(self) -> bool:
        if self.USE_MOCKUP:
            from Utility.Keithley2600 import MockKeithley2600 as Keithley2600
        else:
            from Utility.Keithley2600 import Keithley2600  # type: ignore[assignment]
        inst = Keithley2600()
        if not self.USE_MOCKUP:
            inst.address = KEITHLEY2600_ADDRESS
        inst.connect()
        inst.reset()
        inst.set_4wires(wires4=False, Ch="ab")
        self.bus.connect(INST_KEITHLEY2600, inst)
        self.helmholtz.disable_output()
        return True

    def _disconnect_helmholtz(self) -> None:
        self.helmholtz.disable_output()
        old = self.bus.disconnect(INST_KEITHLEY2600)
        if old is not None:
            try:
                old.disable_source(Ch="ab")
                old.disconnect()
            except Exception:  # noqa: BLE001
                logger.exception("Helmholtz cleanup failed")

    def _connect_hall(self) -> bool:
        if self.USE_MOCKUP:
            from Utility.Mock_Kethley2450 import MockKeithley2450 as K2450
        else:
            from Utility.Keithley2450_Wrapper import Keithley2450Wrapper as K2450  # type: ignore[assignment]
        inst = K2450(KEITHLEY2450_ADDRESS)
        if not self.USE_MOCKUP:
            inst.query("*IDN?")
        inst.connect()
        inst.reset()
        for _cmd in (":SOUR:FUNC CURR", ":SENS:FUNC 'VOLT'", ":SENS:VOLT:RANG 21", ":SENS:VOLT:RANG:AUTO ON"):
            try:
                inst.write(_cmd)
            except Exception:
                logger.debug("K2450 init command failed: %s", _cmd, exc_info=True)
        self.bus.connect(INST_KEITHLEY2450, inst)
        return True

    def _disconnect_hall(self) -> None:
        try:
            if hasattr(self, "hall_tab") and self.hall_tab is not None:
                self.hall_tab.request_iv_stop("Hall disconnect requested: stopping IV run.", show_status=False)
        except Exception:
            logger.debug("Could not request IV stop before hall disconnect", exc_info=True)
        old = self.bus.disconnect(INST_KEITHLEY2450)
        if old is not None:
            try:
                if hasattr(old, "disconnect"):
                    old.disconnect()
                else:
                    for method in ("disable_source", "shutdown", "close"):
                        if hasattr(old, method):
                            try:
                                getattr(old, method)()
                            except Exception:
                                pass
            except Exception:  # noqa: BLE001
                logger.exception("Hall cleanup failed")

    def _connect_dyna(self) -> bool:
        from Utility.DynaClass import DynaClass
        inst = DynaClass(DYNA_HOST, DYNA_PORT)
        result = inst.connect()
        if result is False:
            raise RuntimeError("DynaClass.connect() returned False")
        self.bus.connect(INST_DYNA, inst)
        return True

    def _disconnect_dyna(self) -> None:
        old = self.bus.disconnect(INST_DYNA)
        if old is not None:
            try:
                old.disconnect()
            except Exception:  # noqa: BLE001
                logger.exception("Dyna cleanup failed")

    def _connect_lockin(self) -> bool:
        if self.USE_MOCKUP:
            from Utility.New_Mock_LockIn import MockLockInSR830 as LockInSR830
        else:
            from Utility.New_LockIn import LockInSR830  # type: ignore[assignment]
        if self.USE_MOCKUP:
            inst = LockInSR830()
            inst.initialize_default_state()
        else:
            inst = LockInSR830(resource=LOCKIN_ADDRESS)
            inst.initialize_default_state(reset=False)
        self.bus.connect(INST_LOCKIN, inst)
        return True

    def _disconnect_lockin(self) -> None:
        old = self.bus.disconnect(INST_LOCKIN)
        if old is not None:
            try:
                if hasattr(old, "sine_output_off"):
                    old.sine_output_off()
                if hasattr(old, "close"):
                    old.close()
                if hasattr(old, "inst") and getattr(old, "inst", None) is not None:
                    old.inst.close()
                if hasattr(old, "rm") and getattr(old, "rm", None) is not None:
                    old.rm.close()
            except Exception:  # noqa: BLE001
                logger.exception("LockIn cleanup failed")

    def _connect_switch(self) -> bool:
        backend = str(SWITCH_BACKEND).strip().lower()

        if backend == "keithley7001":
            if self.USE_MOCKUP:
                from Utility.Keithley7001 import MockKeithley7001 as SwitchDriver
                inst = SwitchDriver()
            else:
                from Utility.Keithley7001 import Keithley7001 as SwitchDriver  # type: ignore[assignment]
                inst = SwitchDriver(resource_name=SWITCH_ADDRESS_7001)
        elif backend in {"my_switch", "legacy"}:
            if self.USE_MOCKUP:
                from Utility.MySwitch import MockSwitch as SwitchDriver
            else:
                from Utility.MySwitch import MySwitch as SwitchDriver  # type: ignore[assignment]
            inst = SwitchDriver()
            if not self.USE_MOCKUP:
                # Keep backward compatibility with older single-address constant.
                inst.address = SWITCH_ADDRESS_MY or SWITCH_ADDRESS
        else:
            raise ValueError(
                f"Unsupported switch backend '{SWITCH_BACKEND}'. "
                "Use 'my_switch' or 'keithley7001'."
            )

        inst.connect()
        inst.open_all()
        self.bus.connect(INST_SWITCH, inst)
        return True

    def _disconnect_switch(self) -> None:
        old = self.bus.disconnect(INST_SWITCH)
        if old is not None:
            try:
                old.open_all()
                old.disconnect()
            except Exception:  # noqa: BLE001
                logger.exception("Switch cleanup failed")

    # ==================================================================
    # Dyna (PPMS) background poller
    # ==================================================================
    def _start_dyna_poller(self) -> None:
        self._dyna_poller_stop.clear()
        self._dyna_poller_thread = threading.Thread(
            target=self._dyna_poll_loop,
            daemon=True,
            name="v3-dyna-poller",
        )
        self._dyna_poller_thread.start()

    def _dyna_poll_loop(self) -> None:
        """Background loop: poll PPMS temp+field every 2 s."""
        while not self._dyna_poller_stop.is_set():
            if self.bus.is_connected(INST_DYNA):
                try:
                    temp = self.bus.execute(INST_DYNA, "get_temperature")
                    field = self.bus.execute(INST_DYNA, "get_field")
                    chamber = None
                    try:
                        chamber = self.bus.execute(INST_DYNA, "get_chamber")
                    except Exception:
                        chamber = None

                    temp_status_raw = None
                    if isinstance(temp, (list, tuple)):
                        if len(temp) >= 4:
                            temp_status_raw = temp[3]
                        elif len(temp) >= 3:
                            temp_status_raw = temp[2]

                    field_status_raw = None
                    if isinstance(field, (list, tuple)):
                        if len(field) >= 4:
                            field_status_raw = field[3]
                        elif len(field) >= 3:
                            field_status_raw = field[2]

                    temp_raw = temp[1] if isinstance(temp, (list, tuple)) else temp
                    field_raw = field[1] if isinstance(field, (list, tuple)) else field
                    chamber_raw = None
                    chamber_status_raw = None
                    if isinstance(chamber, (list, tuple)):
                        if len(chamber) >= 3:
                            chamber_raw = chamber[1]
                            chamber_status_raw = chamber[2]
                        elif len(chamber) >= 2:
                            chamber_raw = chamber[1]
                            chamber_status_raw = chamber[1]
                        elif len(chamber) >= 1:
                            chamber_raw = chamber[0]
                            chamber_status_raw = chamber[0]
                    elif chamber is not None:
                        chamber_raw = chamber
                        chamber_status_raw = chamber

                    temp_val = None if temp_raw is None else float(temp_raw)
                    field_val = None if field_raw is None else float(field_raw)
                    chamber_val = None
                    if chamber_raw is not None:
                        try:
                            chamber_val = int(float(chamber_raw))
                        except Exception:
                            chamber_val = None
                    temp_status = self._normalize_dyna_status("temp", temp_status_raw)
                    field_status = self._normalize_dyna_status("field", field_status_raw)
                    chamber_status = self._normalize_dyna_status("chamber", chamber_status_raw)

                    with self._dyna_snapshot_lock:
                        self._dyna_snapshot["temp_val"] = temp_val
                        self._dyna_snapshot["field_val"] = field_val
                        self._dyna_snapshot["chamber_val"] = chamber_val
                        self._dyna_snapshot["temp_text"] = f"{temp_val:.2f} K" if temp_val is not None else "N/A"
                        self._dyna_snapshot["field_text"] = f"{field_val:.1f} Oe" if field_val is not None else "N/A"
                        self._dyna_snapshot["chamber_text"] = chamber_status
                        self._dyna_snapshot["temp_status"] = temp_status
                        self._dyna_snapshot["field_status"] = field_status
                        self._dyna_snapshot["chamber_status"] = chamber_status

                    self.ui_bus.post(W_DYNA_TEMP, temp_val)
                    self.ui_bus.post(W_DYNA_FIELD, field_val)
                    self.ui_bus.post(W_DYNA_CHAMBER, chamber_val)
                    self.ui_bus.post(W_DYNA_TEMP_STATUS, temp_status)
                    self.ui_bus.post(W_DYNA_FIELD_STATUS, field_status)
                    self.ui_bus.post(W_DYNA_CHAMBER_STATUS, chamber_status)
                except Exception:  # noqa: BLE001
                    logger.debug("Dyna poll error", exc_info=True)

            self._dyna_poller_stop.wait(timeout=2.0)

    def get_dyna_snapshot(self) -> dict[str, Any]:
        """Thread-safe read of the PPMS snapshot."""
        with self._dyna_snapshot_lock:
            return dict(self._dyna_snapshot)

    @staticmethod
    def _normalize_dyna_status(kind: str, raw_status: Any) -> str:
        if raw_status is None:
            return "N/A"

        text = str(raw_status).strip()
        if not text:
            return "N/A"

        if kind == "temp":
            state_map = _DYNA_TEMP_STATES
        elif kind == "field":
            state_map = _DYNA_FIELD_STATES
        elif kind == "chamber":
            state_map = _DYNA_CHAMBER_STATES
        else:
            state_map = {}
        try:
            code = int(float(text))
            return state_map.get(code, text)
        except Exception:
            return text

    # ==================================================================
    # update_ui  —  the 100 ms heartbeat
    # ==================================================================
    def _schedule_update_ui(self) -> None:
        self._update_ui_id = self.root.after(UI_TICK_INTERVAL_MS, self._update_ui)

    def _update_ui(self) -> None:
        """Drain UIEventBus and dispatch events to tabs."""
        if self._shutting_down:
            return

        try:
            # --- Drain events from the bus ---
            events = self.ui_bus.drain()
            for widget_id, value in events.items():
                for tab in self._all_tabs:
                    tab.on_event(widget_id, value)

            # --- Drive Helmholtz ramp from UI thread (for live display) ---
            if self.instrument_connected.get("helmholtz") and self.helmholtz.is_enabled:
                if not self.engine.is_running:
                    # Only tick from UI when worker is not driving the ramp
                    self.helmholtz.service_tick(dt=UI_TICK_INTERVAL_MS / 1000.0)
                    self.helmholtz.apply_tick()

            # --- Update PPMS snapshot into local vars ---
            snap = self.get_dyna_snapshot()
            self.current_temp = snap.get("temp_val")
            self.current_inplane_field = snap.get("field_val")

            # --- Update Dyna plot buffers ---
            now = time.time()
            if self.bus.is_connected(INST_DYNA):
                interval = float(self.dyna_tab.dyna_plot_interval.get()) if hasattr(self, "dyna_tab") else 1.0
                if interval <= 0:
                    interval = 1.0

                if (now - self.last_plot_time_dyna) >= interval:
                    temp_val = self.current_temp
                    field_val = self.current_inplane_field
                    if temp_val is not None and field_val is not None:
                        t_dyna = round(now - self.start_time_dyna, 1)
                        self.dyna_time_data.append(t_dyna)
                        self.dyna_temp_data.append(float(temp_val))
                        self.dyna_field_data.append(float(field_val))

                        # Keep only recent points
                        max_points = 5000
                        if len(self.dyna_time_data) > max_points:
                            excess = len(self.dyna_time_data) - max_points
                            self.dyna_time_data = self.dyna_time_data[excess:]
                            self.dyna_temp_data = self.dyna_temp_data[excess:]
                            self.dyna_field_data = self.dyna_field_data[excess:]

                        self.last_plot_time_dyna = now
                        if hasattr(self, "dyna_tab"):
                            self.dyna_tab.update_plot()
                        if self.auto_log_enabled.get():
                            self._write_auto_log()

            # --- Update Helmholtz plot buffers ---
            if self.instrument_connected.get("helmholtz") and self.helmholtz.is_enabled:
                interval = float(self.helmholtz_tab.plot_interval.get()) if hasattr(self, "helmholtz_tab") else 1.0
                if interval <= 0:
                    interval = 1.0

                if (now - self.last_plot_time) >= interval:
                    snap_h = self.helmholtz.snapshot()
                    res_a = snap_h.get("Helmholtz_Resistance_A")
                    res_b = snap_h.get("Helmholtz_Resistance_B")
                    if (
                        isinstance(res_a, (int, float))
                        and isinstance(res_b, (int, float))
                        and not math.isnan(float(res_a))
                        and not math.isnan(float(res_b))
                    ):
                        t = round(now - self.start_time, 1)
                        self.helmholtz_time_data.append(t)
                        self.helmholtz_res_a.append(float(res_a))
                        self.helmholtz_res_b.append(float(res_b))

                        max_points = 5000
                        if len(self.helmholtz_time_data) > max_points:
                            excess = len(self.helmholtz_time_data) - max_points
                            self.helmholtz_time_data = self.helmholtz_time_data[excess:]
                            self.helmholtz_res_a = self.helmholtz_res_a[excess:]
                            self.helmholtz_res_b = self.helmholtz_res_b[excess:]

                        self.last_plot_time = now
                        if hasattr(self, "helmholtz_tab"):
                            self.helmholtz_tab.update_plot()

        except Exception:  # noqa: BLE001
            logger.exception("update_ui error")

        # Reschedule
        if not self._shutting_down:
            self._schedule_update_ui()

    # ==================================================================
    # Auto-log
    # ==================================================================
    def _write_auto_log(self) -> None:
        """Write one auto-log row with current PPMS + Helmholtz state."""
        try:
            snap = self.get_dyna_snapshot()
            helm = self.helmholtz.snapshot()
            self.data_mgr.write_auto_log_entry(
                temp=snap.get("temp_val", ""),
                ppms_field=snap.get("field_val", ""),
                helmholtz_current_a=self.helmholtz.actual_current_a,
                helmholtz_current_b=self.helmholtz.actual_current_b,
                helmholtz_resistance_a=helm.get("Helmholtz_Resistance_A"),
                helmholtz_resistance_b=helm.get("Helmholtz_Resistance_B"),
                helmholtz_field=helm.get("Helmholtz_Field", ""),
            )
        except Exception:  # noqa: BLE001
            logger.debug("Auto-log write error", exc_info=True)

    def _refresh_auto_log_ui_status(self) -> None:
        if hasattr(self, "dyna_tab") and hasattr(self.dyna_tab, "refresh_auto_log_status"):
            try:
                self.dyna_tab.refresh_auto_log_status()
            except Exception:
                logger.debug("Failed to refresh auto-log UI status", exc_info=True)

    def _initialize_auto_log_if_enabled(self) -> None:
        if not self.auto_log_enabled.get():
            self._refresh_auto_log_ui_status()
            return

        path = self.data_mgr.initialize_auto_log()
        if path is not None:
            self.ui_bus.post_log(f"Auto-logging active: {path}")
        else:
            self.ui_bus.post_log("Auto-logging enabled, but failed to open log file.")
        self._refresh_auto_log_ui_status()

    def set_auto_logging_enabled(self, enabled: bool) -> None:
        self.auto_log_enabled.set(bool(enabled))
        if enabled:
            self._initialize_auto_log_if_enabled()
            return

        self.data_mgr.close_auto_log()
        self.ui_bus.post_log("Auto-logging disabled.")
        self._refresh_auto_log_ui_status()

    def set_auto_log_directory(self, new_dir: Path) -> None:
        self.data_mgr.log_dir = Path(new_dir)
        if self.auto_log_enabled.get():
            self.data_mgr.close_auto_log()
            path = self.data_mgr.initialize_auto_log()
            if path is not None:
                self.ui_bus.post_log(f"Auto-log directory changed. Active log: {path}")
            else:
                self.ui_bus.post_log(
                    "Auto-log directory changed, but failed to open a log file."
                )
        else:
            self.ui_bus.post_log(f"Auto-log directory changed to: {self.data_mgr.log_dir}")
        self._refresh_auto_log_ui_status()

    # ==================================================================
    # Script execution
    # ==================================================================
    def run_script(self, script_text: str) -> None:
        """Parse, validate, and run a script."""
        if self.engine.is_running:
            self.ui_bus.post_log("A script is already running.")
            return

        # Abort cleanup may briefly keep engine in STOPPING; don't try to start until IDLE.
        if getattr(self.engine.state, "value", "") == "stopping":
            settled = self.engine.join(timeout=2.0)
            if not settled or getattr(self.engine.state, "value", "") != "idle":
                self.ui_bus.post_log("Script engine is still stopping. Please try again in a moment.")
                return

        if getattr(self.engine.state, "value", "") == "error":
            try:
                self.engine.reset()
                self.ui_bus.post_log("Previous script error state cleared.")
            except Exception as exc:  # noqa: BLE001
                self.ui_bus.post_log(f"Cannot reset script engine state: {exc}")
                return

        commands = self.parser.parse(script_text)
        errors = self.validator.validate(
            commands,
            connected_instruments=set(self.bus.connected_instruments()),
        )

        # Show errors
        real_errors = [e for e in errors if e.severity == "error"]
        if real_errors:
            msg = "\n".join(f"L{e.line_number}: {e.message}" for e in real_errors)
            self.ui_bus.post_log(f"Script validation errors:\n{msg}")
            self._show_toast("Script validation failed. Check System Log.", level="error", duration_ms=5000)
            return

        warnings = [e for e in errors if e.severity == "warning"]
        if warnings:
            msg = "\n".join(f"L{w.line_number}: {w.message}" for w in warnings)
            self.ui_bus.post_log(f"Warnings:\n{msg}")
            self._show_toast("Script has warnings. Check System Log.", level="warn", duration_ms=4500)

        # Import the script runner
        from v3.gui.script_runner import run_commands

        ctx = self.make_context()

        def target(engine: ExperimentEngine) -> None:
            run_commands(engine, ctx, commands, self)

        try:
            self.engine.start(target)
        except EngineStateError as exc:
            self.ui_bus.post_log(f"Cannot start script: {exc}")
            self._show_toast(f"Cannot start script: {exc}", level="error", duration_ms=5000)
            return
        self.ui_bus.post_log("Script started.")
        self.ui_bus.post_log(
            "Power reminder: display-off is OK, but if Windows enters Sleep/Hibernate the script pauses."
        )

    def pause_script(self) -> None:
        """Toggle pause on the running script."""
        self.engine.toggle_pause()

    def abort_script(self) -> None:
        """Abort the running script."""
        self.engine.request_stop()

    def _apply_abort_safe_state(self) -> None:
        """Best-effort instrument safe state for script abort."""
        try:
            if self.bus.is_connected(INST_KEITHLEY2450):
                self.bus.execute(INST_KEITHLEY2450, "disable_source")
        except Exception:  # noqa: BLE001
            logger.exception("Abort safe-state failed for Hall source")

        try:
            if self.bus.is_connected(INST_LOCKIN):
                lockin = self.bus.get_raw(INST_LOCKIN)
                if lockin is not None:
                    if hasattr(lockin, "sine_output_off"):
                        self.bus.execute(INST_LOCKIN, "sine_output_off")
                    elif hasattr(lockin, "set_reference_amplitude"):
                        self.bus.execute(INST_LOCKIN, "set_reference_amplitude", 0.004)
        except Exception:  # noqa: BLE001
            logger.exception("Abort safe-state failed for LockIn output")

        try:
            if self.bus.is_connected(INST_SWITCH):
                switch = self.bus.get_raw(INST_SWITCH)
                if switch is not None:
                    if hasattr(switch, "open_all_channels"):
                        self.bus.execute(INST_SWITCH, "open_all_channels")
                    elif hasattr(switch, "open_all"):
                        self.bus.execute(INST_SWITCH, "open_all")
        except Exception:  # noqa: BLE001
            logger.exception("Abort safe-state failed for switch matrix")

        try:
            if self.bus.is_connected(INST_KEITHLEY2600):
                rate = 0.1
                try:
                    if hasattr(self, "helmholtz_tab") and hasattr(self.helmholtz_tab, "ramp_rate"):
                        rate = float(self.helmholtz_tab.ramp_rate.get())
                    if not math.isfinite(rate) or rate <= 0:
                        rate = 0.1
                except Exception:
                    rate = 0.1
                self.helmholtz.set_field(0.0, rate_mA_per_s=rate)
                # Do not block abort flow; the controller/UI service loop continues the ramp asynchronously.
                logger.info("Abort safe-state: Helmholtz target set to 0 G (non-blocking).")
        except Exception:  # noqa: BLE001
            logger.exception("Abort safe-state failed for Helmholtz ramp-to-zero")

    def _abort_cleanup(self) -> None:
        """Called by ExperimentEngine when aborting — enter best-effort instrument safe state."""
        self._apply_abort_safe_state()

    # ==================================================================
    # Shutdown
    # ==================================================================
    def on_close(self) -> None:
        """Orderly shutdown with responsive UI close."""
        if self._shutting_down:
            return

        try:
            if not self._confirm_close_while_script_running():
                return
        except Exception:
            logger.exception("Running-script close confirmation failed")

        if hasattr(self, "results_tab"):
            try:
                if not self.results_tab.prompt_save_script_if_needed("before exiting"):
                    return
            except Exception:
                logger.exception("Script save prompt failed during close")

        try:
            if not self._confirm_close_with_nonzero_helmholtz_current():
                return
        except Exception:
            logger.exception("Helmholtz close-current confirmation failed")

        self._shutting_down = True

        # Best effort: try to disable Helmholtz while sessions are still alive.
        try:
            if self.instrument_connected.get("helmholtz"):
                self.helmholtz.disable_output()
        except Exception:  # noqa: BLE001
            logger.exception("Early Helmholtz disable during shutdown failed")

        # 1. Stop background threads
        self._dyna_poller_stop.set()
        if self.engine.is_running:
            self.engine.request_stop()

        # 2. Cancel UI callbacks
        if self._update_ui_id is not None:
            try:
                self.root.after_cancel(self._update_ui_id)
            except Exception:  # noqa: BLE001
                pass
        for cb_id in self._pending_callbacks:
            try:
                self.root.after_cancel(cb_id)
            except Exception:  # noqa: BLE001
                pass
        self._pending_callbacks.clear()

        # Cancel any remaining Tk callbacks (including ones not tracked in _pending_callbacks)
        try:
            for cb_id in list(self.root.tk.call("after", "info")):
                try:
                    self.root.after_cancel(cb_id)
                except Exception:
                    pass
        except Exception:
            pass

        # 3. Complete cleanup synchronously (best-effort)
        try:
            if self._dyna_poller_thread is not None:
                self._dyna_poller_thread.join(timeout=2.0)
        except Exception:  # noqa: BLE001
            pass

        try:
            self.engine.join(timeout=2.0)
        except Exception:  # noqa: BLE001
            pass

        try:
            self.helmholtz.disable_output()
        except Exception:  # noqa: BLE001
            pass

        try:
            self.data_mgr.close()
        except Exception:  # noqa: BLE001
            pass

        # Disconnect Helmholtz first via dedicated path so output-disable is always
        # attempted before driver session teardown.
        if self.instrument_connected.get("helmholtz"):
            try:
                self._disconnect_helmholtz()
            except Exception:  # noqa: BLE001
                logger.exception("Helmholtz dedicated shutdown disconnect failed")
            finally:
                self.instrument_connected["helmholtz"] = False

        # Disconnect low-level objects directly
        for inst_key, bus_name in _KEY_TO_BUS.items():
            if inst_key == "helmholtz":
                continue
            if not self.instrument_connected.get(inst_key):
                continue
            try:
                old = self.bus.disconnect(bus_name)
                if old is None:
                    continue
                for method in ("disable_source", "shutdown", "disconnect", "close"):
                    if hasattr(old, method):
                        try:
                            if method == "disable_source":
                                try:
                                    getattr(old, method)(Ch="ab")
                                except Exception:
                                    getattr(old, method)()
                            else:
                                getattr(old, method)()
                        except Exception:
                            pass
            except Exception:  # noqa: BLE001
                pass

        # 4. Destroy window after cleanup
        try:
            self.root.destroy()
        except Exception:  # noqa: BLE001
            pass

    def _helmholtz_currents_nonzero(self, eps_a: float = 1e-6) -> tuple[bool, float, float]:
        """Return whether Helmholtz channel currents are non-zero, with values."""
        try:
            cur_a = float(self.helmholtz.actual_current_a)
            cur_b = float(self.helmholtz.actual_current_b)
        except Exception:
            return (False, 0.0, 0.0)
        nonzero = abs(cur_a) > eps_a or abs(cur_b) > eps_a
        return (nonzero, cur_a, cur_b)

    def _confirm_close_with_nonzero_helmholtz_current(self) -> bool:
        """Warn before close if Helmholtz current is non-zero. Returns True to continue."""
        if not self.instrument_connected.get("helmholtz"):
            return True

        nonzero, cur_a, cur_b = self._helmholtz_currents_nonzero()
        if not nonzero:
            return True

        msg = (
            "Helmholtz current is not zero.\n\n"
            f"Current A: {cur_a:.6f} A\n"
            f"Current B: {cur_b:.6f} A\n\n"
            "Please ramp both currents down to zero before closing the program.\n"
            "Do you want to close anyway?"
        )
        return bool(messagebox.askyesno("Helmholtz Current Warning", msg, icon="warning"))

    def _confirm_close_while_script_running(self) -> bool:
        """Warn before close if a script/measurement is currently active."""
        if not self.engine.is_running:
            return True

        msg = (
            "A measurement script is currently running.\n\n"
            "Closing now will stop the running script.\n"
            "Are you sure you want to close the app?"
        )
        return bool(messagebox.askyesno("Measurement Running", msg, icon="warning"))

    # ==================================================================
    # Helpers
    # ==================================================================
    def _show_mockup_warning(self) -> None:
        messagebox.showwarning(
            "Mock Mode",
            "Running in MOCKUP mode — no real instruments.",
        )

    def _needs_dyna_cooling_confirmation(self, target_temp_k: float, current_temp_k: float | None) -> bool:
        if current_temp_k is None:
            return False
        return (
            float(current_temp_k) >= DYNA_COOLING_CONFIRM_THRESHOLD_K
            and float(target_temp_k) < DYNA_COOLING_CONFIRM_THRESHOLD_K
        )

    def _show_dyna_cooling_confirmation_dialog(
        self,
        *,
        current_temp_k: float,
        target_temp_k: float,
        source: str,
    ) -> str:
        decision = {"action": "abort"}
        dialog = tk.Toplevel(self.root)
        dialog.title("Dyna Cooling Safety")
        dialog.transient(self.root)
        dialog.resizable(False, False)

        container = ttk.Frame(dialog, padding=12)
        container.grid(row=0, column=0, sticky="nsew")
        dialog.grid_columnconfigure(0, weight=1)
        dialog.grid_rowconfigure(0, weight=1)

        source_text = "script" if source.startswith("script") else "manual control"
        ttk.Label(
            container,
            text=(
                "Dyna is not in purged mode.\n"
                "Cooling below 295 K requires the chamber to be purged and sealed."
            ),
            justify="left",
        ).grid(row=0, column=0, columnspan=3, sticky="w")

        ttk.Label(
            container,
            text=f"Source: {source_text}",
            foreground="#666666",
        ).grid(row=1, column=0, columnspan=3, sticky="w", pady=(8, 6))

        def _close(action: str) -> None:
            decision["action"] = action
            try:
                dialog.grab_release()
            except Exception:
                pass
            dialog.destroy()

        abort_btn = ttk.Button(container, text="Abort", command=lambda: _close("abort"))
        abort_btn.grid(row=2, column=0, sticky="e", padx=(0, 6))
        continue_btn = ttk.Button(container, text="Continue", command=lambda: _close("continue"))
        continue_btn.grid(row=2, column=1, sticky="w", padx=(0, 6))
        purge_btn = ttk.Button(
            container,
            text="Purge and Continue",
            command=lambda: _close("purge_continue"),
        )
        purge_btn.grid(row=2, column=2, sticky="w")

        dialog.protocol("WM_DELETE_WINDOW", lambda: _close("abort"))
        dialog.update_idletasks()
        try:
            root_x = int(self.root.winfo_rootx())
            root_y = int(self.root.winfo_rooty())
            root_w = int(self.root.winfo_width())
            root_h = int(self.root.winfo_height())
            dlg_w = int(dialog.winfo_reqwidth())
            dlg_h = int(dialog.winfo_reqheight())
            pos_x = root_x + max(0, (root_w - dlg_w) // 2)
            pos_y = root_y + max(0, (root_h - dlg_h) // 2)
            dialog.geometry(f"+{pos_x}+{pos_y}")
        except Exception:
            pass
        dialog.grab_set()
        continue_btn.focus_set()
        dialog.wait_window()
        return str(decision["action"])

    def _is_dyna_purged_state(self, chamber_val: object, chamber_status: object) -> bool:
        try:
            if chamber_val is not None and int(float(chamber_val)) == 1:
                return True
        except Exception:
            pass

        text = str(chamber_status).strip().lower() if chamber_status is not None else ""
        return text in {"purged and sealed", "purge and seal", "purged/sealed"}

    def _wait_for_dyna_purged(self, timeout_s: float = 1800.0, poll_s: float = 1.0) -> bool:
        deadline = time.time() + max(1.0, float(timeout_s))

        while time.time() < deadline:
            try:
                snap = self.get_dyna_snapshot()
                if self._is_dyna_purged_state(snap.get("chamber_val"), snap.get("chamber_status")):
                    return True
            except Exception:
                pass

            try:
                if self.bus.is_connected(INST_DYNA):
                    chamber = self.bus.execute(INST_DYNA, "get_chamber")
                    chamber_val = None
                    chamber_status = None
                    if isinstance(chamber, (list, tuple)):
                        if len(chamber) >= 3:
                            chamber_val = chamber[1]
                            chamber_status = chamber[2]
                        elif len(chamber) >= 2:
                            chamber_val = chamber[1]
                            chamber_status = chamber[1]
                        elif len(chamber) >= 1:
                            chamber_val = chamber[0]
                            chamber_status = chamber[0]
                    else:
                        chamber_status = chamber

                    if self._is_dyna_purged_state(chamber_val, chamber_status):
                        return True
            except Exception:
                pass

            if threading.current_thread() is threading.main_thread():
                try:
                    self.root.update_idletasks()
                    self.root.update()
                except Exception:
                    pass

            time.sleep(max(0.1, float(poll_s)))

        return False

    def confirm_dyna_low_temp_transition(self, target_temp_k: float, *, source: str = "manual") -> bool:
        current_temp = self.current_temp
        if current_temp is None:
            try:
                snap_temp = self.get_dyna_snapshot().get("temp_val")
                current_temp = float(snap_temp) if snap_temp is not None else None
            except Exception:
                current_temp = None

        if not self._needs_dyna_cooling_confirmation(target_temp_k, current_temp):
            return True

        try:
            snap = self.get_dyna_snapshot()
            if self._is_dyna_purged_state(snap.get("chamber_val"), snap.get("chamber_status")):
                return True
        except Exception:
            pass

        if threading.current_thread() is threading.main_thread():
            action = self._show_dyna_cooling_confirmation_dialog(
                current_temp_k=float(current_temp),
                target_temp_k=float(target_temp_k),
                source=source,
            )
            if action == "continue":
                return True
            if action == "purge_continue":
                try:
                    self.ui_bus.post_log("Setting Dyna chamber to Purge and Seal before cooling...")
                    self.bus.execute(INST_DYNA, "set_chamber", 1)
                    self.ui_bus.post_log("Waiting for Dyna chamber to reach Purged and Sealed state...")
                    if self._wait_for_dyna_purged():
                        self.ui_bus.post_log("Dyna chamber is Purged and Sealed. Cooling may proceed.")
                        return True
                    self.ui_bus.post_log("Timed out waiting for Dyna chamber to become Purged and Sealed.")
                except Exception as exc:
                    self.ui_bus.post_log(f"Failed to purge Dyna chamber: {exc}")
                return False
            return False

        done = threading.Event()
        result = {"action": "abort"}

        def _prompt() -> None:
            try:
                result["action"] = self._show_dyna_cooling_confirmation_dialog(
                    current_temp_k=float(current_temp),
                    target_temp_k=float(target_temp_k),
                    source=source,
                )
            finally:
                done.set()

        self.root.after(0, _prompt)
        done.wait()
        action = str(result.get("action", "abort"))
        if action == "continue":
            return True
        if action == "purge_continue":
            try:
                self.ui_bus.post_log("Setting Dyna chamber to Purge and Seal before cooling...")
                self.bus.execute(INST_DYNA, "set_chamber", 1)
                self.ui_bus.post_log("Waiting for Dyna chamber to reach Purged and Sealed state...")
                if self._wait_for_dyna_purged():
                    self.ui_bus.post_log("Dyna chamber is Purged and Sealed. Cooling may proceed.")
                    return True
                self.ui_bus.post_log("Timed out waiting for Dyna chamber to become Purged and Sealed.")
            except Exception as exc:
                self.ui_bus.post_log(f"Failed to purge Dyna chamber: {exc}")
            return False
        return False

    def _auto_connect_all(self) -> None:
        """Auto-connect all instruments at startup (matching V2 behavior)."""
        init_errors = []
        for key in ["helmholtz", "hall", "lockin", "switch", "dyna"]:
            try:
                if self.instrument_connected.get(key, False) and self.bus.is_connected(_KEY_TO_BUS[key]):
                    continue
                success = self.connect_instrument(key)
                if success:
                    logger.info("Auto-connected: %s", key)
                else:
                    init_errors.append(f"{key}: connection returned False")
            except Exception as exc:
                init_errors.append(f"{key}: {exc}")
                logger.warning("Auto-connect failed for %s: %s", key, exc)

        if init_errors:
            self.ui_bus.post_log(
                "Auto-connect completed with errors:\n"
                + "\n".join(f"  - {e}" for e in init_errors)
            )
        else:
            self.ui_bus.post_log("All instruments auto-connected successfully.")

    def safe_after(self, delay_ms: int, callback, *args) -> str:
        """Schedule a callback and track it for cleanup."""
        cb_id = self.root.after(delay_ms, callback, *args)
        self._pending_callbacks.append(cb_id)
        return cb_id


# ======================================================================
# Entry point
# ======================================================================
def main(use_mockup: bool = False) -> None:
    """Launch the v3 experiment GUI."""
    root = tk.Tk()
    _app = MeasureApp(root, use_mockup=use_mockup)
    root.mainloop()


if __name__ == "__main__":
    # Default to real mode; use v3/run_app.py for the easy toggle
    main(use_mockup=False)
