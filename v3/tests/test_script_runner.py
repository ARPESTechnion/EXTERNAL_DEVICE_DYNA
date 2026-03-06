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
from v3.core.ui_events import UIEventBus, W_HELMHOLTZ_SETPOINT
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
        _post_helmholtz_setpoint(app, field_g=683.42, rate_mA_s=0.2)
        events = app.ui_bus.drain()
        payload = events[W_HELMHOLTZ_SETPOINT]
        self.assertAlmostEqual(float(payload["total_current_a"]), 1.0, places=6)
        self.assertAlmostEqual(float(payload["field_g"]), 683.42, places=6)


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
