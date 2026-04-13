"""
Tests for v3.gui.script_runner Helmholtz loop behavior.
"""

from __future__ import annotations

import threading
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from v3.core.calibration import CalibrationConfig
from v3.core.ui_events import UIEventBus, W_HELMHOLTZ_SETPOINT, W_LOCKIN_SENSITIVITY, W_LOCKIN_STATUS
from v3.core.script_parser import ParsedCommand
from v3.gui.script_runner import (
    _dispatch,
    _post_helmholtz_setpoint,
    _normalize_wait_events,
    _parse_voltage_range,
    _run_loop,
    _run_saved_script,
    _seconds_to_tau_index,
)


class _DummyEngine:
    def __init__(self) -> None:
        self.stop_event = threading.Event()

    def check_stop(self) -> None:
        if self.stop_event.is_set():
            raise RuntimeError("stop requested")

    def check_pause(self) -> None:
        return

    def interruptible_sleep(self, _seconds: float) -> None:
        return


class _DummyHelmholtz:
    def __init__(self) -> None:
        self._target = 0.0
        self._actual = 0.0
        self._rate = 1.0
        self.apply_calls = 0

    def set_field(self, field_gauss: float, rate_mA_per_s: float | None = None) -> None:
        self._target = float(field_gauss)
        if rate_mA_per_s is not None:
            self._rate = max(float(rate_mA_per_s), 1.0)

    def ramp_to_target(self, _stop_event: threading.Event) -> None:
        self._actual = self._target

    def service_tick(self, dt: float = 0.1) -> bool:
        delta = self._target - self._actual
        if abs(delta) <= 1e-9:
            return False
        step = min(abs(delta), self._rate * dt)
        self._actual += step if delta > 0 else -step
        return abs(self._target - self._actual) > 1e-9

    def apply_tick(self) -> None:
        self.apply_calls += 1


class _DummyApp:
    def __init__(self) -> None:
        self.helmholtz = _DummyHelmholtz()


class _DummyCtx:
    pass


class _DummyHelmholtzForSetpoint:
    def __init__(self) -> None:
        self.calibration = CalibrationConfig()


class _DummySetpointApp:
    def __init__(self) -> None:
        self.ui_bus = UIEventBus()
        self.helmholtz = _DummyHelmholtzForSetpoint()


class TestScriptRunnerHelmholtzSweep(unittest.TestCase):
    def test_sweep_helmholtz_field_advances_and_finishes(self) -> None:
        engine = _DummyEngine()
        ctx = _DummyCtx()
        app = _DummyApp()

        cmd = ParsedCommand(
            name="sweep_helmholtz_field",
            args=["0", "10", "1000"],
            kwargs={},
            children=[],
            line_number=1,
            raw="sweep_helmholtz_field 0 10 1000",
        )

        _run_loop(engine, ctx, cmd, app)

        self.assertGreater(app.helmholtz.apply_calls, 0)
        self.assertAlmostEqual(app.helmholtz._actual, 10.0, places=6)


class TestScriptRunnerHelpers(unittest.TestCase):
    def test_seconds_to_tau_index(self) -> None:
        self.assertEqual(_seconds_to_tau_index(0.3), 9)
        self.assertEqual(_seconds_to_tau_index(1.0), 10)

    def test_parse_voltage_range(self) -> None:
        value, auto = _parse_voltage_range("10V")
        self.assertFalse(auto)
        self.assertAlmostEqual(value, 10.0)

        value, auto = _parse_voltage_range("100mV")
        self.assertFalse(auto)
        self.assertAlmostEqual(value, 0.1)

        value, auto = _parse_voltage_range("auto")
        self.assertTrue(auto)
        self.assertIsNone(value)

    def test_normalize_wait_events_aliases(self) -> None:
        self.assertEqual(_normalize_wait_events(["dyna_ready"]), ["field"])
        self.assertEqual(_normalize_wait_events(["temp_stable", "helmholtz_field"]), ["temp", "helmholtz"])

    def test_post_helmholtz_setpoint_uses_calibration_conversion(self) -> None:
        app = _DummySetpointApp()
        _post_helmholtz_setpoint(app, field_g=341.71, rate_mA_s=0.2)
        events = app.ui_bus.drain()
        payload = events[W_HELMHOLTZ_SETPOINT]
        self.assertAlmostEqual(float(payload["total_current_a"]), 1.0, places=6)
        self.assertAlmostEqual(float(payload["field_g"]), 341.71, places=6)


class TestScriptRunnerHallCommands(unittest.TestCase):
    def _make_app_ctx_engine(self):
        engine = MagicMock()
        engine.stop_event = threading.Event()

        ui_bus = UIEventBus()
        ctx = MagicMock()
        ctx.ui_bus = ui_bus
        ctx.data_mgr = MagicMock()
        ctx.data_mgr.write_row = MagicMock()

        app = MagicMock()
        app.instrument_connected = {"hall": True}
        app.hall_tab = MagicMock()
        app.hall_tab.k2450_current.get.return_value = 1.0
        app.hall_tab.k2450_nplc.get.return_value = 1.0
        app.hall_tab.k2450_compliance_v.get.return_value = 2.0
        app.hall_tab.k2450_voltage_range.get.return_value = "auto"
        app.hall_tab.k2450_filter_count.get.return_value = 5
        app.hall_tab.k2450_tbm.get.return_value = 0.2
        app.hall_tab.k2450_hall_offset.get.return_value = 0.0
        app.hall_tab.k2450_hall_v2gauss.get.return_value = 1.0
        app.ui_bus = ui_bus
        return engine, ctx, app

    @patch("v3.gui.script_runner.measure_hall_continuous")
    def test_dispatch_continuous_measure_hall_field(self, mock_measure_hall_continuous):
        engine, ctx, app = self._make_app_ctx_engine()
        mock_measure_hall_continuous.return_value = {
            "Hall Voltage": 0.001,
            "Hall Field": 0.001,
            "Time": 1.0,
        }

        cmd = ParsedCommand(name="continuous_measure_hall_field", kwargs={}, args=[])
        _dispatch(engine, ctx, cmd, app)

        mock_measure_hall_continuous.assert_called_once()
        ctx.data_mgr.write_row.assert_called_once()

    @patch("v3.gui.script_runner.enable_hall_output")
    def test_dispatch_enable_hall_output(self, mock_enable_hall_output):
        engine, ctx, app = self._make_app_ctx_engine()
        cmd = ParsedCommand(name="enable_hall_output", kwargs={}, args=[])
        _dispatch(engine, ctx, cmd, app)
        mock_enable_hall_output.assert_called_once()

    @patch("v3.gui.script_runner.disable_hall_output")
    def test_dispatch_disable_hall_output(self, mock_disable_hall_output):
        engine, ctx, app = self._make_app_ctx_engine()
        cmd = ParsedCommand(name="disable_hall_output", kwargs={}, args=[])
        _dispatch(engine, ctx, cmd, app)
        mock_disable_hall_output.assert_called_once()


class TestScriptRunnerFullMeasure(unittest.TestCase):
    def _make_app_ctx_engine(self):
        engine = MagicMock()
        engine.stop_event = threading.Event()

        ui_bus = UIEventBus()
        ctx = MagicMock()
        ctx.ui_bus = ui_bus
        ctx.data_mgr = MagicMock()
        ctx.data_mgr.write_row = MagicMock()

        app = MagicMock()
        app.ui_bus = ui_bus
        app.instrument_connected = {"hall": True, "lockin": True, "switch": True}
        app.channels = ["a", "b", "c", "d"]
        app.active_channel = "a"

        app.hall_tab = MagicMock()
        app.hall_tab.k2450_current.get.return_value = 1.0
        app.hall_tab.k2450_nplc.get.return_value = 1.0
        app.hall_tab.k2450_compliance_v.get.return_value = 2.0
        app.hall_tab.k2450_voltage_range.get.return_value = "auto"
        app.hall_tab.k2450_filter_count.get.return_value = 5
        app.hall_tab.k2450_tbm.get.return_value = 0.2

        app.lockin_tab = MagicMock()
        app.lockin_tab.lockin_filter_slope.get.return_value = 24
        app.lockin_tab.lockin_output_current.get.return_value = 1e-6
        app.lockin_tab.lockin_r_lockin.get.return_value = 1000.0
        app.lockin_tab.lockin_averaging.get.return_value = 10
        app.lockin_tab.lockin_sensitivity_idx.get.return_value = 10
        app.lockin_tab.lockin_time_constant_idx.get.return_value = 9
        app.lockin_tab.lockin_frequency.get.return_value = 137.0

        return engine, ctx, app

    @patch("v3.gui.script_runner._post_switch_summary")
    @patch("v3.gui.script_runner._post_lockin_result_events")
    @patch("v3.gui.script_runner._post_hall_result_events")
    @patch("v3.gui.script_runner.open_all_channels")
    @patch("v3.gui.script_runner._close_active_channel")
    @patch("v3.gui.script_runner.measure_lockin")
    @patch("v3.gui.script_runner.measure_hall_continuous")
    @patch("v3.gui.script_runner.measure_hall")
    def test_full_measure_default_cycle_uses_measure_hall(
        self,
        mock_measure_hall,
        mock_measure_hall_continuous,
        mock_measure_lockin,
        mock_close_active_channel,
        mock_open_all_channels,
        _mock_post_hall,
        _mock_post_lockin,
        _mock_post_switch,
    ):
        engine, ctx, app = self._make_app_ctx_engine()
        mock_measure_hall.return_value = {"Hall Voltage": 1.0}
        mock_measure_lockin.return_value = {"LockIn_X_a": 2.0}

        cmd = ParsedCommand(name="full_measure", args=["a"], kwargs={})
        _dispatch(engine, ctx, cmd, app)

        mock_measure_hall.assert_called_once()
        mock_measure_hall_continuous.assert_not_called()
        mock_measure_lockin.assert_called_once()
        mock_close_active_channel.assert_called_once()
        mock_open_all_channels.assert_called_once()
        ctx.data_mgr.write_row.assert_called_once()

    @patch("v3.gui.script_runner._post_switch_summary")
    @patch("v3.gui.script_runner._post_lockin_result_events")
    @patch("v3.gui.script_runner._post_hall_result_events")
    @patch("v3.gui.script_runner.open_all_channels")
    @patch("v3.gui.script_runner._close_active_channel")
    @patch("v3.gui.script_runner.measure_lockin")
    @patch("v3.gui.script_runner.measure_hall_continuous")
    @patch("v3.gui.script_runner.measure_hall")
    def test_full_measure_keep_uses_measure_hall_continuous(
        self,
        mock_measure_hall,
        mock_measure_hall_continuous,
        mock_measure_lockin,
        mock_close_active_channel,
        mock_open_all_channels,
        _mock_post_hall,
        _mock_post_lockin,
        _mock_post_switch,
    ):
        engine, ctx, app = self._make_app_ctx_engine()
        mock_measure_hall_continuous.return_value = {"Hall Voltage": 1.0}
        mock_measure_lockin.return_value = {"LockIn_X_a": 2.0}

        cmd = ParsedCommand(name="full_measure", args=["a"], kwargs={"hall_excitation": "keep"})
        _dispatch(engine, ctx, cmd, app)

        mock_measure_hall.assert_not_called()
        mock_measure_hall_continuous.assert_called_once()
        mock_measure_lockin.assert_called_once()
        mock_close_active_channel.assert_called_once()
        mock_open_all_channels.assert_called_once()
        ctx.data_mgr.write_row.assert_called_once()

class TestScriptRunnerContinuousFullMeasure(unittest.TestCase):
    def _make_app_ctx_engine(self):
        engine = MagicMock()
        engine.stop_event = threading.Event()

        ui_bus = UIEventBus()
        ctx = MagicMock()
        ctx.ui_bus = ui_bus
        ctx.data_mgr = MagicMock()
        ctx.data_mgr.write_row = MagicMock()

        app = MagicMock()
        app.ui_bus = ui_bus
        app.instrument_connected = {"hall": True, "lockin": True, "switch": True}
        app.channels = ["a", "b", "c", "d"]
        app.active_channel = "a"

        app.hall_tab = MagicMock()
        app.hall_tab.k2450_current.get.return_value = 1.0
        app.hall_tab.k2450_nplc.get.return_value = 1.0
        app.hall_tab.k2450_compliance_v.get.return_value = 2.0
        app.hall_tab.k2450_voltage_range.get.return_value = "auto"
        app.hall_tab.k2450_filter_count.get.return_value = 5
        app.hall_tab.k2450_tbm.get.return_value = 0.2

        app.lockin_tab = MagicMock()
        app.lockin_tab.lockin_filter_slope.get.return_value = 24
        app.lockin_tab.lockin_output_current.get.return_value = 1e-6
        app.lockin_tab.lockin_r_lockin.get.return_value = 1000.0
        app.lockin_tab.lockin_averaging.get.return_value = 10
        app.lockin_tab.lockin_sensitivity_idx.get.return_value = 10
        app.lockin_tab.lockin_time_constant_idx.get.return_value = 9
        app.lockin_tab.lockin_frequency.get.return_value = 137.0

        return engine, ctx, app

    @patch("v3.gui.script_runner._post_switch_summary")
    @patch("v3.gui.script_runner._post_lockin_result_events")
    @patch("v3.gui.script_runner._post_hall_result_events")
    @patch("v3.gui.script_runner.open_all_channels")
    @patch("v3.gui.script_runner._close_active_channel")
    @patch("v3.gui.script_runner.measure_lockin")
    @patch("v3.gui.script_runner.measure_lockin_continuous")
    @patch("v3.gui.script_runner.measure_hall_continuous")
    @patch("v3.gui.script_runner.measure_hall")
    def test_continuous_full_measure_default_uses_continuous_hall_and_lockin(
        self,
        mock_measure_hall,
        mock_measure_hall_continuous,
        mock_measure_lockin_continuous,
        mock_measure_lockin,
        mock_close_active_channel,
        mock_open_all_channels,
        _mock_post_hall,
        _mock_post_lockin,
        _mock_post_switch,
    ):
        engine, ctx, app = self._make_app_ctx_engine()
        mock_measure_hall_continuous.return_value = {"Hall Voltage": 1.0}
        mock_measure_lockin_continuous.return_value = {"LockIn_X_a": 2.0}

        cmd = ParsedCommand(name="continuous_full_measure", args=[], kwargs={})
        _dispatch(engine, ctx, cmd, app)

        mock_measure_hall.assert_not_called()
        mock_measure_hall_continuous.assert_called_once()
        mock_measure_lockin_continuous.assert_called_once()
        mock_measure_lockin.assert_not_called()
        mock_close_active_channel.assert_not_called()
        mock_open_all_channels.assert_not_called()
        ctx.data_mgr.write_row.assert_called_once()

    @patch("v3.gui.script_runner._post_switch_summary")
    @patch("v3.gui.script_runner._post_lockin_result_events")
    @patch("v3.gui.script_runner._post_hall_result_events")
    @patch("v3.gui.script_runner.measure_lockin_continuous")
    @patch("v3.gui.script_runner.measure_hall_continuous")
    @patch("v3.gui.script_runner.measure_hall")
    def test_continuous_full_measure_hall_kwargs_are_applied(
        self,
        mock_measure_hall,
        mock_measure_hall_continuous,
        mock_measure_lockin_continuous,
        _mock_post_hall,
        _mock_post_lockin,
        _mock_post_switch,
    ):
        engine, ctx, app = self._make_app_ctx_engine()
        mock_measure_hall_continuous.return_value = {"Hall Voltage": 1.0}
        mock_measure_lockin_continuous.return_value = {"LockIn_X_a": 2.0}

        cmd = ParsedCommand(
            name="continuous_full_measure",
            args=[],
            kwargs={"hall_nplc": "2", "hall_compliance": "3.5", "hall_filter": "7"},
        )
        _dispatch(engine, ctx, cmd, app)

        mock_measure_hall.assert_not_called()
        mock_measure_hall_continuous.assert_called_once()
        self.assertAlmostEqual(mock_measure_hall_continuous.call_args.kwargs["nplc"], 2.0)
        self.assertAlmostEqual(mock_measure_hall_continuous.call_args.kwargs["compliance_v"], 3.5)
        self.assertEqual(mock_measure_hall_continuous.call_args.kwargs["filter_count"], 7)
        mock_measure_lockin_continuous.assert_called_once()

    @patch("v3.gui.script_runner._post_switch_summary")
    @patch("v3.gui.script_runner._post_lockin_result_events")
    @patch("v3.gui.script_runner._post_hall_result_events")
    @patch("v3.gui.script_runner.measure_lockin")
    @patch("v3.gui.script_runner.measure_lockin_continuous")
    @patch("v3.gui.script_runner.measure_hall_continuous")
    def test_continuous_full_measure_auto_flags_use_measure_lockin(
        self,
        mock_measure_hall_continuous,
        mock_measure_lockin_continuous,
        mock_measure_lockin,
        _mock_post_hall,
        _mock_post_lockin,
        _mock_post_switch,
    ):
        engine, ctx, app = self._make_app_ctx_engine()
        mock_measure_hall_continuous.return_value = {"Hall Voltage": 1.0}
        mock_measure_lockin.return_value = {"LockIn_X_a": 2.0}

        cmd = ParsedCommand(
            name="continuous_full_measure",
            args=[],
            kwargs={"lockin_use_autorange": "true"},
        )
        _dispatch(engine, ctx, cmd, app)

        mock_measure_hall_continuous.assert_called_once()
        mock_measure_lockin.assert_called_once()
        self.assertIs(mock_measure_lockin.call_args.kwargs.get("manage_excitation"), False)
        mock_measure_lockin_continuous.assert_not_called()


class TestScriptRunnerLockinUtilityCommands(unittest.TestCase):
    @patch("v3.gui.script_runner.lockin_auto_gain")
    def test_dispatch_auto_gain_updates_gui_and_posts_sensitivity(self, mock_lockin_auto_gain):
        engine = MagicMock()
        engine.stop_event = threading.Event()

        ui_bus = UIEventBus()
        ctx = MagicMock()
        ctx.ui_bus = ui_bus

        app = MagicMock()
        app.instrument_connected = {"lockin": True}
        app.lockin_tab = MagicMock()
        app.lockin_tab.lockin_sensitivity_idx = MagicMock()
        app.lockin_tab.sens_label = MagicMock()
        app.lockin_tab._sens_text.return_value = "20 uV"

        mock_lockin_auto_gain.return_value = 12

        cmd = ParsedCommand(name="auto_gain", args=[], kwargs={})
        _dispatch(engine, ctx, cmd, app)

        mock_lockin_auto_gain.assert_called_once_with(ctx)
        app.lockin_tab.lockin_sensitivity_idx.set.assert_called_once_with(12)
        app.lockin_tab.sens_label.configure.assert_called_once_with(text="20 uV")

        events = ui_bus.drain()
        self.assertEqual(events[W_LOCKIN_SENSITIVITY], 12)
        self.assertEqual(events[W_LOCKIN_STATUS], "LockIn: auto gain completed")

    @patch("v3.gui.script_runner.set_lockin_sensitivity")
    def test_dispatch_set_lockin_sensitivity_updates_gui_and_posts_event(self, mock_set_lockin_sensitivity):
        engine = MagicMock()
        engine.stop_event = threading.Event()

        ui_bus = UIEventBus()
        ctx = MagicMock()
        ctx.ui_bus = ui_bus

        app = MagicMock()
        app.instrument_connected = {"lockin": True}
        app.lockin_tab = MagicMock()
        app.lockin_tab.lockin_sensitivity_idx = MagicMock()
        app.lockin_tab.sens_label = MagicMock()
        app.lockin_tab._sens_text.return_value = "5 uV"

        cmd = ParsedCommand(name="set_lockin_sensitivity", args=["17"], kwargs={})
        _dispatch(engine, ctx, cmd, app)

        mock_set_lockin_sensitivity.assert_called_once_with(ctx, 17)
        app.lockin_tab.lockin_sensitivity_idx.set.assert_called_once_with(17)
        app.lockin_tab.sens_label.configure.assert_called_once_with(text="5 uV")

        events = ui_bus.drain()
        self.assertEqual(events[W_LOCKIN_SENSITIVITY], 17)
        self.assertEqual(events[W_LOCKIN_STATUS], "LockIn: sensitivity updated")


class TestScriptRunnerPpmsHallFixSafety(unittest.TestCase):
    def _make_app_ctx_engine(self):
        engine = MagicMock()
        engine.stop_event = threading.Event()
        engine.check_stop = MagicMock()
        engine.check_pause = MagicMock()

        ui_bus = UIEventBus()
        ctx = MagicMock()
        ctx.ui_bus = ui_bus
        ctx.data_mgr = MagicMock()
        ctx.data_mgr.write_row = MagicMock()

        app = MagicMock()
        app.instrument_connected = {"dyna": True, "helmholtz": True, "hall": True}
        app.ui_bus = ui_bus
        app.hall_tab = MagicMock()
        app.hall_tab.k2450_current.get.return_value = 1.0
        app.hall_tab.k2450_nplc.get.return_value = 1.0
        app.hall_tab.k2450_compliance_v.get.return_value = 2.0
        app.hall_tab.k2450_voltage_range.get.return_value = "auto"
        app.hall_tab.k2450_filter_count.get.return_value = 5
        app.hall_tab.k2450_tbm.get.return_value = 0.2

        app.helmholtz = MagicMock()
        app.helmholtz.calibration = CalibrationConfig()
        app.helmholtz.snapshot.return_value = {"Helmholtz_Field": 0.0}
        app.helmholtz.set_field = MagicMock()
        app.helmholtz.ramp_to_target = MagicMock()

        return engine, ctx, app

    @patch("v3.gui.script_runner.wait_for_events")
    @patch("v3.gui.script_runner.set_dyna_field")
    @patch("v3.gui.script_runner.measure_hall")
    def test_set_ppms_field_and_fix_hall_aborts_when_current_change_exceeds_limit(
        self,
        mock_measure_hall,
        mock_set_dyna_field,
        mock_wait_for_events,
    ):
        engine, ctx, app = self._make_app_ctx_engine()
        mock_measure_hall.return_value = {"Hall Field": 0.0}

        cmd = ParsedCommand(
            name="set_ppms_field_and_fix_hall",
            args=["1000", "100"],
            kwargs={"helmholtz_rate": "0.1", "max_current_change": "0.05"},
        )

        with self.assertRaises(RuntimeError) as err_ctx:
            _dispatch(engine, ctx, cmd, app)

        self.assertIn("exceeds allowed current change", str(err_ctx.exception))
        mock_set_dyna_field.assert_called_once()
        mock_wait_for_events.assert_called_once()
        ctx.data_mgr.write_row.assert_not_called()
        app.helmholtz.set_field.assert_not_called()

    @patch("v3.gui.script_runner.wait_for_events")
    @patch("v3.gui.script_runner.set_dyna_field")
    @patch("v3.gui.script_runner.measure_hall")
    def test_scan_ppms_field_and_fix_hall_aborts_when_current_change_exceeds_limit(
        self,
        mock_measure_hall,
        mock_set_dyna_field,
        mock_wait_for_events,
    ):
        engine, ctx, app = self._make_app_ctx_engine()
        mock_measure_hall.return_value = {"Hall Field": 0.0}

        cmd = ParsedCommand(
            name="scan_ppms_field_and_fix_hall",
            args=["0", "0", "1", "100"],
            kwargs={"rate": "10", "helmholtz_rate": "0.1", "max_current_change": "0.05"},
        )

        with self.assertRaises(RuntimeError) as err_ctx:
            _dispatch(engine, ctx, cmd, app)

        self.assertIn("exceeds allowed current change", str(err_ctx.exception))
        mock_set_dyna_field.assert_called_once()
        mock_wait_for_events.assert_called_once()
        ctx.data_mgr.write_row.assert_not_called()
        app.helmholtz.set_field.assert_not_called()

    @patch("v3.gui.script_runner.wait_for_events")
    @patch("v3.gui.script_runner.set_dyna_field")
    @patch("v3.gui.script_runner.measure_hall")
    def test_set_ppms_field_and_fix_hall_posts_helmholtz_setpoint_event(
        self,
        mock_measure_hall,
        _mock_set_dyna_field,
        _mock_wait_for_events,
    ):
        engine, ctx, app = self._make_app_ctx_engine()
        mock_measure_hall.side_effect = [
            {"Hall Field": 0.0},
            {"Hall Field": 100.0},
        ]

        cmd = ParsedCommand(
            name="set_ppms_field_and_fix_hall",
            args=["1000", "100"],
            kwargs={"helmholtz_rate": "0.25", "max_current_change": "2.0"},
        )

        _dispatch(engine, ctx, cmd, app)

        events = app.ui_bus.drain()
        payload = events[W_HELMHOLTZ_SETPOINT]
        self.assertAlmostEqual(float(payload["rate_mA_s"]), 0.25, places=6)
        ctx.data_mgr.write_row.assert_not_called()


class TestScriptRunnerErrorHandling(unittest.TestCase):
    def test_dispatch_fail_fast_on_command_error(self) -> None:
        engine = MagicMock()
        engine.stop_event = threading.Event()

        ctx = MagicMock()
        ctx.ui_bus = UIEventBus()
        ctx.data_mgr = MagicMock()
        ctx.data_mgr.initialize_file.return_value = None

        app = MagicMock()
        app.instrument_connected = {}

        cmd = ParsedCommand(name="initialize_data_file", kwargs={}, args=[])
        with self.assertRaises(RuntimeError):
            _dispatch(engine, ctx, cmd, app)


class TestRunSavedScriptGuardrails(unittest.TestCase):
    def _make_ctx_app(self):
        ctx = MagicMock()
        ctx.ui_bus = UIEventBus()

        app = MagicMock()
        app.bus = MagicMock()
        app.bus.connected_instruments.return_value = []
        from v3.core.script_parser import ScriptParser, ScriptValidator
        app.parser = ScriptParser()
        app.validator = ScriptValidator()
        return ctx, app

    def test_run_saved_script_detects_cycle(self) -> None:
        engine = MagicMock()
        ctx, app = self._make_ctx_app()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "cycle.txt"
            path.write_text("test\n", encoding="utf-8")
            engine._script_stack = [path.resolve()]
            with self.assertRaises(RuntimeError):
                _run_saved_script(engine, ctx, app, str(path))

    def test_run_saved_script_rejects_invalid_nested_script(self) -> None:
        engine = MagicMock()
        ctx, app = self._make_ctx_app()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad_nested.txt"
            path.write_text("set_lockin_filter invalid\n", encoding="utf-8")
            engine._script_stack = []
            with self.assertRaises(RuntimeError):
                _run_saved_script(engine, ctx, app, str(path))


if __name__ == "__main__":
    unittest.main()
