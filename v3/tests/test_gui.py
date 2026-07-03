"""
Tests for v3.gui modules  —  headless (no display required).

Tests exercise the GUI layer's non-visual logic:
* BaseTab / ConnectionHeader state transitions
* Event dispatching
* Script runner command dispatch
* App-level instrument connection/disconnection (mocked)

Tkinter widgets are created against a real Tk root.  On CI or headless
environments where no display is available, the entire module is skipped.
"""

from __future__ import annotations

import os
import sys
import threading
import time
import unittest
from unittest.mock import MagicMock, patch

import pytest

# ── Skip if no display available ──
_DISPLAY = os.environ.get("DISPLAY", "")
_IS_WINDOWS = sys.platform == "win32"
if not _IS_WINDOWS and not _DISPLAY:
    pytest.skip("No display available", allow_module_level=True)

import tkinter as tk
from tkinter import ttk

from v3.core.calibration import CalibrationConfig
from v3.core.constants import INST_DYNA, INST_KEITHLEY2450, INST_KEITHLEY2600, INST_LOCKIN, INST_SWITCH
from v3.core.experiment_engine import EngineState, ExperimentEngine
from v3.core.helmholtz_controller import HelmholtzController
from v3.core.instrument_bus import InstrumentBus
from v3.core.data_manager import DataManager
from v3.core.measurements import MeasurementContext
from v3.core.ui_events import (
    UIEventBus,
    W_DYNA_CHAMBER,
    W_DYNA_CHAMBER_STATUS,
    W_DYNA_TEMP,
    W_DYNA_TEMP_STATUS,
    W_DYNA_FIELD,
    W_DYNA_FIELD_STATUS,
    W_HELMHOLTZ_CURRENT_A,
    W_HELMHOLTZ_FIELD,
    W_INSTRUMENT_CONNECTED,
    W_INSTRUMENT_DISCONNECTED,
    W_LOG_MESSAGE,
    W_RESULTS_NEW_POINT,
    W_SCRIPT_STATUS,
)
from v3.gui.base_tab import (
    BaseTab,
    ConnectionHeader,
    LED_OFF_COLOR,
    LED_ON_COLOR,
    make_led,
    set_led,
)


# ======================================================================
# Fixtures
# ======================================================================
@pytest.fixture(scope="module")
def root():
    """Create a single Tk root for all tests in this module."""
    r = tk.Tk()
    r.withdraw()
    yield r
    r.destroy()


@pytest.fixture
def ui_bus():
    return UIEventBus()


@pytest.fixture
def bus():
    return InstrumentBus()


# ======================================================================
# BaseTab & ConnectionHeader tests
# ======================================================================
class TestMakeLed:
    def test_creates_label(self, root):
        led = make_led(root)
        assert isinstance(led, tk.Label)
        assert led.cget("fg") == LED_OFF_COLOR

    def test_set_led_on(self, root):
        led = make_led(root)
        set_led(led, True)
        assert led.cget("fg") == LED_ON_COLOR

    def test_set_led_off(self, root):
        led = make_led(root)
        set_led(led, True)
        set_led(led, False)
        assert led.cget("fg") == LED_OFF_COLOR


class TestConnectionHeader:
    def test_initial_state(self, root):
        frame = tk.Frame(root)
        ch = ConnectionHeader(frame, "test", "Test Device")
        assert not ch.is_connected

    def test_set_connected(self, root):
        frame = tk.Frame(root)
        ch = ConnectionHeader(frame, "test", "Test Device")
        ch.set_connected(True)
        assert ch.is_connected
        ch.set_connected(False)
        assert not ch.is_connected

    def test_toggle_calls_callbacks(self, root):
        frame = tk.Frame(root)
        connected_cb = MagicMock()
        disconnected_cb = MagicMock()
        ch = ConnectionHeader(
            frame, "test", "Test",
            on_connect=connected_cb,
            on_disconnect=disconnected_cb,
        )
        # Not connected → toggle → calls connect
        ch._toggle()
        connected_cb.assert_called_once()
        disconnected_cb.assert_not_called()

        # Set connected → toggle → calls disconnect
        ch.set_connected(True)
        ch._toggle()
        disconnected_cb.assert_called_once()


class TestBaseTab:
    def test_abstract_methods(self, root):
        frame = tk.Frame(root)
        app = MagicMock()
        tab = BaseTab(frame, app)
        with pytest.raises(NotImplementedError):
            tab.create_widgets()
        # on_event should not raise
        tab.on_event("test", 42)
        tab.on_instrument_connected("test")
        tab.on_instrument_disconnected("test")


# ======================================================================
# Tab event dispatch tests
# ======================================================================
class TestHelmholtzTabEvents:
    def test_field_display_update(self, root):
        from v3.gui.helmholtz_tab import HelmholtzTab
        frame = ttk.Frame(root)
        app = MagicMock()
        app.connect_instrument = MagicMock()
        app.disconnect_instrument = MagicMock()
        tab = HelmholtzTab(frame, app)
        tab.create_widgets()
        tab.on_event(W_HELMHOLTZ_FIELD, 123.45)
        assert "123.45" in tab.field_display.cget("text")

    def test_current_readout_update(self, root):
        from v3.gui.helmholtz_tab import HelmholtzTab
        frame = ttk.Frame(root)
        app = MagicMock()
        app.connect_instrument = MagicMock()
        app.disconnect_instrument = MagicMock()
        tab = HelmholtzTab(frame, app)
        tab.create_widgets()
        tab.on_event(W_HELMHOLTZ_CURRENT_A, 0.5123)
        assert "0.5123" in tab.readout_a.cget("text")

    def test_reset_plot_clears_and_keeps_autoscale(self, root):
        from v3.gui.helmholtz_tab import HelmholtzTab

        frame = ttk.Frame(root)
        app = MagicMock()
        app.connect_instrument = MagicMock()
        app.disconnect_instrument = MagicMock()
        app.ui_bus = MagicMock()
        app.helmholtz_time_data = [0.0, 1.0, 2.0]
        app.helmholtz_res_a = [1.0, 1.1, 1.2]
        app.helmholtz_res_b = [2.0, 2.1, 2.2]
        app.start_time = 0.0
        app.last_plot_time = 0.0

        tab = HelmholtzTab(frame, app)
        tab.create_widgets()
        tab._on_reset_plot()

        assert app.helmholtz_time_data == []
        assert app.helmholtz_res_a == []
        assert app.helmholtz_res_b == []
        assert app.last_plot_time > 0.0

        if getattr(tab, "canvas", None) is not None:
            assert tab.ax.get_autoscalex_on() is True
            assert tab.ax.get_autoscaley_on() is True


class TestDynaTabEvents:
    def test_temp_update(self, root):
        from v3.gui.dyna_tab import DynaTab
        frame = ttk.Frame(root)
        app = MagicMock()
        app.connect_instrument = MagicMock()
        app.disconnect_instrument = MagicMock()
        tab = DynaTab(frame, app)
        tab.create_widgets()
        tab.on_event(W_DYNA_TEMP, 295.5)
        assert "295.50" in tab.temp_display.cget("text")

    def test_temp_and_field_state_update(self, root):
        from v3.gui.dyna_tab import DynaTab
        frame = ttk.Frame(root)
        app = MagicMock()
        app.connect_instrument = MagicMock()
        app.disconnect_instrument = MagicMock()
        tab = DynaTab(frame, app)
        tab.create_widgets()
        tab.on_event(W_DYNA_TEMP, 295.5)
        tab.on_event(W_DYNA_TEMP_STATUS, "Stable")
        tab.on_event(W_DYNA_FIELD, 1234.0)
        tab.on_event(W_DYNA_FIELD_STATUS, "Ramping")
        assert "Stable" in tab.temp_display.cget("text")
        assert "Ramping" in tab.field_display.cget("text")

    def test_chamber_state_update(self, root):
        from v3.gui.dyna_tab import DynaTab
        frame = ttk.Frame(root)
        app = MagicMock()
        app.connect_instrument = MagicMock()
        app.disconnect_instrument = MagicMock()
        tab = DynaTab(frame, app)
        tab.create_widgets()
        tab.on_event(W_DYNA_CHAMBER, 1)
        tab.on_event(W_DYNA_CHAMBER_STATUS, "Purge and Seal")
        text = tab.chamber_display.cget("text")
        assert "Purge and Seal" in text
        assert "(1)" not in text

    def test_manual_set_chamber_dispatches_command(self, root):
        from v3.gui.dyna_tab import DynaTab

        frame = ttk.Frame(root)
        app = MagicMock()
        app.connect_instrument = MagicMock()
        app.disconnect_instrument = MagicMock()
        app.bus = MagicMock()
        app.ui_bus = UIEventBus()
        app.auto_log_enabled = tk.BooleanVar(value=False)
        app.data_mgr = MagicMock()
        app.data_mgr.log_dir = "."
        app.data_mgr.auto_log_filename = None
        app.data_mgr.is_auto_log_open = False
        app.set_auto_log_directory = MagicMock()
        app.set_auto_logging_enabled = MagicMock()

        tab = DynaTab(frame, app)
        tab.create_widgets()
        tab.chamber_mode.set("High Vacuum")

        tab._on_set_chamber()

        app.bus.execute.assert_called_once_with(INST_DYNA, "set_chamber", 5)

    def test_manual_set_temp_aborts_when_safety_declined(self, root):
        from v3.gui.dyna_tab import DynaTab

        frame = ttk.Frame(root)
        app = MagicMock()
        app.connect_instrument = MagicMock()
        app.disconnect_instrument = MagicMock()
        app.confirm_dyna_low_temp_transition = MagicMock(return_value=False)
        app.bus = MagicMock()
        app.ui_bus = UIEventBus()
        app.auto_log_enabled = tk.BooleanVar(value=False)
        app.data_mgr = MagicMock()
        app.data_mgr.log_dir = "."
        app.data_mgr.auto_log_filename = None
        app.data_mgr.is_auto_log_open = False
        app.set_auto_log_directory = MagicMock()
        app.set_auto_logging_enabled = MagicMock()

        tab = DynaTab(frame, app)
        tab.create_widgets()
        tab.set_temp.set(280.0)
        tab.temp_rate.set(5.0)
        tab.temp_mode.set("fast_settle")

        tab._on_set_temp()

        app.confirm_dyna_low_temp_transition.assert_called_once_with(280.0, source="manual")
        app.bus.execute.assert_not_called()


class TestResultsTabEvents:
    def test_log_message(self, root):
        from v3.gui.results_tab import ResultsTab
        frame = ttk.Frame(root)
        app = MagicMock()
        app.parser = MagicMock()
        app.validator = MagicMock()
        app.script_filename = tk.StringVar(value="test.txt")
        app.bus = InstrumentBus()
        app.data_mgr = MagicMock()
        app.data_mgr.get_results.return_value = []
        tab = ResultsTab(frame, app)
        tab.create_widgets()
        tab.on_event(W_LOG_MESSAGE, "Hello test")
        content = tab.log_text.get("1.0", "end").strip()
        assert "Hello test" in content

    def test_connection_leds(self, root):
        from v3.gui.results_tab import ResultsTab
        frame = ttk.Frame(root)
        app = MagicMock()
        app.parser = MagicMock()
        app.validator = MagicMock()
        app.script_filename = tk.StringVar(value="test.txt")
        app.bus = InstrumentBus()
        app.data_mgr = MagicMock()
        app.data_mgr.get_results.return_value = []
        tab = ResultsTab(frame, app)
        tab.create_widgets()

        tab.on_event(W_INSTRUMENT_CONNECTED, "dyna")
        assert tab.conn_leds["dyna"].cget("fg") == LED_ON_COLOR

        tab.on_event(W_INSTRUMENT_DISCONNECTED, "dyna")
        assert tab.conn_leds["dyna"].cget("fg") == LED_OFF_COLOR

    def test_script_status_update(self, root):
        from v3.gui.results_tab import ResultsTab
        frame = ttk.Frame(root)
        app = MagicMock()
        app.parser = MagicMock()
        app.validator = MagicMock()
        app.script_filename = tk.StringVar(value="test.txt")
        app.bus = InstrumentBus()
        app.data_mgr = MagicMock()
        app.data_mgr.get_results.return_value = []
        tab = ResultsTab(frame, app)
        tab.create_widgets()
        tab.on_event(W_SCRIPT_STATUS, "Running L5/10")
        assert "Running L5/10" in tab.script_status.get()

    def test_dyna_state_update(self, root):
        from v3.gui.results_tab import ResultsTab
        frame = ttk.Frame(root)
        app = MagicMock()
        app.parser = MagicMock()
        app.validator = MagicMock()
        app.script_filename = tk.StringVar(value="test.txt")
        app.bus = InstrumentBus()
        app.data_mgr = MagicMock()
        app.data_mgr.get_results.return_value = []
        tab = ResultsTab(frame, app)
        tab.create_widgets()

        tab.on_event(W_DYNA_TEMP, 300.0)
        tab.on_event(W_DYNA_TEMP_STATUS, "Tracking")
        tab.on_event(W_DYNA_FIELD, 250.0)
        tab.on_event(W_DYNA_FIELD_STATUS, "Stable")

        assert "Tracking" in tab.results_dyna_temp.cget("text")
        assert "Stable" in tab.results_dyna_field.cget("text")

    def test_dyna_chamber_update(self, root):
        from v3.gui.results_tab import ResultsTab
        frame = ttk.Frame(root)
        app = MagicMock()
        app.parser = MagicMock()
        app.validator = MagicMock()
        app.script_filename = tk.StringVar(value="test.txt")
        app.bus = InstrumentBus()
        app.data_mgr = MagicMock()
        app.data_mgr.get_results.return_value = []
        tab = ResultsTab(frame, app)
        tab.create_widgets()

        tab.on_event(W_DYNA_CHAMBER, 2)
        tab.on_event(W_DYNA_CHAMBER_STATUS, "Vent and Seal")

        text = tab.results_dyna_chamber.cget("text")
        assert "Vent and Seal" in text
        assert "(2)" not in text

    def test_iv_range_requires_integer_ordered_bounds(self, root):
        from v3.gui.results_tab import ResultsTab
        frame = ttk.Frame(root)
        app = MagicMock()
        app.parser = MagicMock()
        app.validator = MagicMock()
        app.script_filename = tk.StringVar(value="test.txt")
        app.bus = InstrumentBus()
        app.data_mgr = MagicMock()
        app.data_mgr.get_results.return_value = []
        tab = ResultsTab(frame, app)
        tab.create_widgets()

        tab.iv_range_start_var.set(3000)
        tab.iv_range_end_var.set(2000)
        assert tab._current_iv_range() is None

        tab.iv_range_start_var.set(2000)
        tab.iv_range_end_var.set(3000)
        assert tab._current_iv_range() == (2000, 3000)

    def test_iv_generic_rows_not_duplicated_across_channels(self, root):
        from v3.gui.results_tab import ResultsTab
        frame = ttk.Frame(root)
        app = MagicMock()
        app.parser = MagicMock()
        app.validator = MagicMock()
        app.script_filename = tk.StringVar(value="test.txt")
        app.bus = InstrumentBus()
        app.data_mgr = MagicMock()
        app.data_mgr.get_results.return_value = [
            {"Measurement_Type": "IV", "IV_Point": 1, "IV_Measured_Voltage": 0.1},
            {"Measurement_Type": "IV", "IV_Point": 2, "IV_Measured_Voltage": 0.2},
        ]
        tab = ResultsTab(frame, app)
        tab.create_widgets()

        tab.x1_var.set("IV_Point")
        tab.y1_var.set("IV_Measured_Voltage(V)")
        for var in tab.channel_filter_vars_g1.values():
            var.set(True)

        tab.refresh_plots()
        series = tab._last_rendered_graph_data[1]["series"]
        assert len(series) == 1
        assert series[0]["channel"] == "global"

    def test_auto_follow_latest_updates_range_on_new_point(self, root):
        from v3.gui.results_tab import ResultsTab
        frame = ttk.Frame(root)
        app = MagicMock()
        app.parser = MagicMock()
        app.validator = MagicMock()
        app.script_filename = tk.StringVar(value="test.txt")
        app.bus = InstrumentBus()
        app.data_mgr = MagicMock()
        app.data_mgr.get_results.return_value = [{"Measurement_Type": "IV"}] * 10
        tab = ResultsTab(frame, app)
        tab.create_widgets()

        tab.data_plot_range_start_var.set(1)
        tab.data_plot_range_end_var.set(5)
        tab.auto_follow_latest_var.set(True)

        tab.on_event(W_RESULTS_NEW_POINT, True)

        assert tab.data_plot_range_start_var.get() == 6
        assert tab.data_plot_range_end_var.get() == 10


class TestLockInTabEvents:
    def test_x_y_r_update(self, root):
        from v3.gui.lockin_tab import LockInTab
        from v3.core.ui_events import (
            W_LOCKIN_X,
            W_LOCKIN_Y,
            W_LOCKIN_R,
            W_LOCKIN_X_ERROR,
            W_LOCKIN_Y_ERROR,
            W_LOCKIN_R_ERROR,
        )
        frame = ttk.Frame(root)
        app = MagicMock()
        app.connect_instrument = MagicMock()
        app.disconnect_instrument = MagicMock()
        tab = LockInTab(frame, app)
        tab.create_widgets()
        tab.on_event(W_LOCKIN_X, 1.23e-6)
        tab.on_event(W_LOCKIN_X_ERROR, 2.2e-8)
        assert "1.23" in tab.x_label.cget("text")
        assert "±" in tab.x_label.cget("text")
        tab.on_event(W_LOCKIN_Y, 4.56e-7)
        tab.on_event(W_LOCKIN_Y_ERROR, 3.1e-8)
        assert "4.56" in tab.y_label.cget("text")
        tab.on_event(W_LOCKIN_R, 7.89e-7)
        tab.on_event(W_LOCKIN_R_ERROR, 1.1e-8)
        assert "±" in tab.r_label.cget("text")

    def test_output_led_syncs_on_connect(self, root):
        from v3.gui.lockin_tab import LockInTab
        frame = ttk.Frame(root)
        app = MagicMock()
        app.connect_instrument = MagicMock()
        app.disconnect_instrument = MagicMock()
        app.bus = InstrumentBus()
        tab = LockInTab(frame, app)
        tab.create_widgets()

        tab.lockin_output_current.set(1e-5)
        tab.lockin_r_lockin.set(1000.0)
        tab.on_instrument_connected("lockin")
        assert tab.output_led.cget("fg") == LED_ON_COLOR

        tab.lockin_output_current.set(0.0)
        tab.on_instrument_connected("lockin")
        assert tab.output_led.cget("fg") == LED_OFF_COLOR

    def test_output_led_off_at_idle_minimum_voltage(self, root):
        from v3.gui.lockin_tab import LockInTab
        from v3.core.constants import INST_LOCKIN

        frame = ttk.Frame(root)
        app = MagicMock()
        app.connect_instrument = MagicMock()
        app.disconnect_instrument = MagicMock()
        app.bus = InstrumentBus()

        mock_lockin = MagicMock()
        mock_lockin._MIN_SLVL = 0.004
        mock_lockin.get_reference_amplitude.return_value = 0.004
        app.bus.connect(INST_LOCKIN, mock_lockin)

        tab = LockInTab(frame, app)
        tab.create_widgets()
        tab.on_instrument_connected("lockin")
        assert tab.output_led.cget("fg") == LED_OFF_COLOR


class TestSwitchTabEvents:
    def test_status_update(self, root):
        from v3.gui.switch_tab import SwitchTab
        from v3.core.ui_events import W_SWITCH_STATUS
        frame = ttk.Frame(root)
        app = MagicMock()
        app.connect_instrument = MagicMock()
        app.disconnect_instrument = MagicMock()
        app.channels = ["a", "b"]
        app.channel_configs = {
            "a": {"I+": tk.IntVar(value=1), "V+": tk.IntVar(value=2),
                   "V-": tk.IntVar(value=3), "I-": tk.IntVar(value=4)},
            "b": {"I+": tk.IntVar(value=5), "V+": tk.IntVar(value=6),
                   "V-": tk.IntVar(value=7), "I-": tk.IntVar(value=8)},
        }
        tab = SwitchTab(frame, app)
        tab.create_widgets()
        tab.on_event(W_SWITCH_STATUS, "Ch A: I+=1 V+=2")
        assert "Ch A" in tab.status_label.cget("text")

    def test_duplicate_mapping_summary_uses_lowest_channel(self, root):
        from v3.gui.switch_tab import SwitchTab

        frame = ttk.Frame(root)
        app = MagicMock()
        app.connect_instrument = MagicMock()
        app.disconnect_instrument = MagicMock()
        app.root = root
        app.ui_bus = UIEventBus()
        app.instrument_connected = {"switch": True}
        app.channels = ["a", "b", "c"]
        app.channel_configs = {
            "a": {"I+": tk.IntVar(value=1), "V+": tk.IntVar(value=2), "V-": tk.IntVar(value=3), "I-": tk.IntVar(value=4)},
            "b": {"I+": tk.IntVar(value=1), "V+": tk.IntVar(value=2), "V-": tk.IntVar(value=3), "I-": tk.IntVar(value=4)},
            "c": {"I+": tk.IntVar(value=5), "V+": tk.IntVar(value=6), "V-": tk.IntVar(value=7), "I-": tk.IntVar(value=8)},
        }
        app.bus = InstrumentBus()
        switch = MagicMock()
        switch.closed_channels = {"1", "2", "3", "4"}
        app.bus.connect(INST_SWITCH, switch)

        tab = SwitchTab(frame, app)
        tab.create_widgets()

        summary = tab._switch_state_summary()
        assert summary.startswith("Switch: Channel A Closed")
        assert "duplicate mapping" in summary

    def test_controls_do_not_include_configure_button(self, root):
        from v3.gui.switch_tab import SwitchTab

        frame = ttk.Frame(root)
        app = MagicMock()
        app.connect_instrument = MagicMock()
        app.disconnect_instrument = MagicMock()
        app.channels = ["a", "b"]
        app.channel_configs = {
            "a": {"I+": tk.IntVar(value=1), "V+": tk.IntVar(value=2), "V-": tk.IntVar(value=3), "I-": tk.IntVar(value=4)},
            "b": {"I+": tk.IntVar(value=5), "V+": tk.IntVar(value=6), "V-": tk.IntVar(value=7), "I-": tk.IntVar(value=8)},
        }
        app.ui_bus = UIEventBus()
        app.bus = InstrumentBus()
        app.instrument_connected = {"switch": False}

        tab = SwitchTab(frame, app)
        tab.create_widgets()

        def _iter_widgets(widget):
            yield widget
            for child in widget.winfo_children():
                yield from _iter_widgets(child)

        button_texts = [
            widget.cget("text")
            for widget in _iter_widgets(tab.parent)
            if isinstance(widget, ttk.Button)
        ]
        assert "Configure" not in button_texts

    def test_swapped_i_channels_do_not_collapse_to_lowest(self, root):
        from v3.gui.switch_tab import SwitchTab

        frame = ttk.Frame(root)
        app = MagicMock()
        app.connect_instrument = MagicMock()
        app.disconnect_instrument = MagicMock()
        app.root = root
        app.ui_bus = UIEventBus()
        app.instrument_connected = {"switch": True}
        app.active_channel = "b"
        app.channels = ["a", "b"]
        app.channel_configs = {
            "a": {"I+": tk.IntVar(value=1), "V+": tk.IntVar(value=2), "V-": tk.IntVar(value=4), "I-": tk.IntVar(value=5)},
            "b": {"I+": tk.IntVar(value=5), "V+": tk.IntVar(value=2), "V-": tk.IntVar(value=4), "I-": tk.IntVar(value=1)},
        }
        app.bus = InstrumentBus()
        switch = MagicMock()
        switch.closed_channels = {"1", "2", "4", "5"}
        app.bus.connect(INST_SWITCH, switch)

        tab = SwitchTab(frame, app)
        tab.create_widgets()

        summary = tab._switch_state_summary()
        assert summary.startswith("Switch: Channel B Closed")


class TestHallTabEvents:
    def test_result_update(self, root):
        from v3.gui.hall_tab import HallTab
        from v3.core.ui_events import W_HALL_RESULT
        frame = ttk.Frame(root)
        app = MagicMock()
        app.connect_instrument = MagicMock()
        app.disconnect_instrument = MagicMock()
        tab = HallTab(frame, app)
        tab.create_widgets()
        tab.on_event(W_HALL_RESULT, {
            "voltage": 1.5e-4,
            "field": 12.5,
            "voltage_error": 1.2e-6,
            "field_error": 0.3,
        })
        text = tab.result_label.cget("text")
        assert "1.5" in text
        assert "12.5" in text
        assert "±" in text

    def test_iv_progress_event_updates_hall_progress_widgets(self, root):
        from v3.gui.hall_tab import HallTab
        from v3.core.ui_events import W_IV_PROGRESS

        frame = ttk.Frame(root)
        app = MagicMock()
        app.connect_instrument = MagicMock()
        app.disconnect_instrument = MagicMock()
        tab = HallTab(frame, app)
        tab.create_widgets()

        tab.on_event(
            W_IV_PROGRESS,
            {
                "current": 4,
                "total": 8,
                "percent": 50.0,
                "active": True,
                "elapsed_s": 5.0,
                "estimated_total_s": 10.0,
            },
        )

        assert tab.iv_progress_value.get() == pytest.approx(50.0)
        assert "5.0/10.0 s" in tab.iv_progress_text.get()


# ======================================================================
# Script runner tests (no GUI needed — uses mock app)
# ======================================================================
class TestScriptRunner:
    def test_dispatch_test_command(self, ui_bus):
        from v3.gui.script_runner import _dispatch
        from v3.core.script_parser import ParsedCommand

        engine = MagicMock(spec=ExperimentEngine)
        engine.stop_event = threading.Event()
        ctx = MagicMock(spec=MeasurementContext)
        ctx.ui_bus = ui_bus
        app = MagicMock()

        cmd = ParsedCommand(name="test", args=[], line_number=1, raw="test")
        _dispatch(engine, ctx, cmd, app)

        # Should have posted a log message
        events = ui_bus.drain()
        assert W_LOG_MESSAGE in events
        assert "Test" in events[W_LOG_MESSAGE]

    def test_arange_ascending(self):
        from v3.gui.script_runner import _arange
        result = _arange(0, 10, 5)
        assert len(result) == 3
        assert result[0] == 0
        assert result[-1] == 10

    def test_arange_descending(self):
        from v3.gui.script_runner import _arange
        result = _arange(10, 0, 5)
        assert len(result) == 3
        assert result[0] == 10
        assert result[-1] == 0

    def test_arange_zero_step(self):
        from v3.gui.script_runner import _arange
        result = _arange(5, 5, 0)
        assert result == [5]

    def test_set_dyna_temp_aborts_when_safety_declined(self, ui_bus):
        from v3.gui.script_runner import _dispatch
        from v3.core.experiment_engine import StopRequested
        from v3.core.script_parser import ParsedCommand

        engine = MagicMock(spec=ExperimentEngine)
        engine.stop_event = threading.Event()
        ctx = MagicMock(spec=MeasurementContext)
        ctx.ui_bus = ui_bus

        app = MagicMock()
        app.instrument_connected = {"dyna": True}
        app.confirm_dyna_low_temp_transition = MagicMock(return_value=False)

        cmd = ParsedCommand(
            name="set_dyna_temp",
            args=["250", "5", "fast_settle"],
            line_number=1,
            raw="set_dyna_temp 250 5 fast_settle",
        )

        with patch("v3.gui.script_runner.set_dyna_temp") as set_temp_mock:
            with pytest.raises(StopRequested):
                _dispatch(engine, ctx, cmd, app)

        app.confirm_dyna_low_temp_transition.assert_called_once()
        called_temp = app.confirm_dyna_low_temp_transition.call_args.args[0]
        called_source = app.confirm_dyna_low_temp_transition.call_args.kwargs.get("source")
        assert called_temp == pytest.approx(250.0)
        assert called_source == "script:set_dyna_temp"
        set_temp_mock.assert_not_called()
        engine.request_stop.assert_called_once()


# ======================================================================
# Integration-level: MeasureApp construction (headless)
# ======================================================================
class TestMeasureAppInit:
    """Test that MeasureApp can be instantiated without errors."""

    def test_app_creates(self, root):
        """Minimal construction test — mocks out all heavy deps."""
        # We can't easily construct the full app without patching
        # auto-created subsystems. Instead test that tabs can be
        # created independently.
        from v3.gui.helmholtz_tab import HelmholtzTab
        from v3.gui.dyna_tab import DynaTab
        from v3.gui.lockin_tab import LockInTab
        from v3.gui.hall_tab import HallTab
        from v3.gui.switch_tab import SwitchTab
        from v3.gui.results_tab import ResultsTab

        app = MagicMock()
        app.connect_instrument = MagicMock()
        app.disconnect_instrument = MagicMock()
        app.channels = ["a", "b"]
        app.channel_configs = {
            "a": {"I+": tk.IntVar(value=1), "V+": tk.IntVar(value=2),
                   "V-": tk.IntVar(value=3), "I-": tk.IntVar(value=4)},
            "b": {"I+": tk.IntVar(value=5), "V+": tk.IntVar(value=6),
                   "V-": tk.IntVar(value=7), "I-": tk.IntVar(value=8)},
        }
        app.parser = MagicMock()
        app.validator = MagicMock()
        app.script_filename = tk.StringVar(value="test.txt")
        app.bus = InstrumentBus()
        app.data_mgr = MagicMock()
        app.data_mgr.get_results.return_value = []

        # Verify each tab constructs and creates widgets
        tabs = [
            HelmholtzTab(ttk.Frame(root), app),
            DynaTab(ttk.Frame(root), app),
            LockInTab(ttk.Frame(root), app),
            HallTab(ttk.Frame(root), app),
            SwitchTab(ttk.Frame(root), app),
            ResultsTab(ttk.Frame(root), app),
        ]
        for tab in tabs:
            tab.create_widgets()

        assert len(tabs) == 6


class TestMeasureAppCloseSafety:
    def test_confirm_close_skips_prompt_when_helmholtz_zero(self):
        from v3.gui.app import MeasureApp

        app = MeasureApp.__new__(MeasureApp)
        app.instrument_connected = {"helmholtz": True}
        app.helmholtz = MagicMock()
        app.helmholtz.actual_current_a = 0.0
        app.helmholtz.actual_current_b = 0.0

        with patch("v3.gui.app.messagebox.askyesno") as ask:
            result = app._confirm_close_with_nonzero_helmholtz_current()

        assert result is True
        ask.assert_not_called()

    def test_confirm_close_prompts_when_helmholtz_nonzero(self):
        from v3.gui.app import MeasureApp

        app = MeasureApp.__new__(MeasureApp)
        app.instrument_connected = {"helmholtz": True}
        app.helmholtz = MagicMock()
        app.helmholtz.actual_current_a = 0.012
        app.helmholtz.actual_current_b = 0.0

        with patch("v3.gui.app.messagebox.askyesno", return_value=False) as ask:
            result = app._confirm_close_with_nonzero_helmholtz_current()

        assert result is False
        ask.assert_called_once()
