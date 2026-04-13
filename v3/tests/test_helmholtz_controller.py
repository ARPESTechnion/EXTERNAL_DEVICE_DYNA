"""
Tests for v3.core.helmholtz_controller
"""

from __future__ import annotations

import math
import threading
import time
import unittest
from unittest.mock import MagicMock, patch

from v3.core.calibration import CalibrationConfig
from v3.core.constants import HELMHOLTZ_MAX_CURRENT_A, INST_KEITHLEY2600
from v3.core.helmholtz_controller import (
    ComplianceError,
    HelmholtzController,
    HelmholtzSafetyError,
)
from v3.core.instrument_bus import InstrumentBus
from v3.core.ui_events import UIEventBus


def _make_mock_bus() -> InstrumentBus:
    """InstrumentBus with a mock Keithley 2600 connected."""
    bus = InstrumentBus()
    mock_k = MagicMock()
    mock_k.get_resistance.return_value = 1.0  # 1 Ω
    bus.connect(INST_KEITHLEY2600, mock_k)
    return bus


class TestConstruction(unittest.TestCase):
    def test_defaults(self):
        bus = InstrumentBus()
        ui = UIEventBus()
        ctrl = HelmholtzController(bus, ui)
        self.assertAlmostEqual(ctrl.target_current, 0.0)
        self.assertAlmostEqual(ctrl.actual_current_a, 0.0)
        self.assertAlmostEqual(ctrl.actual_current_b, 0.0)
        self.assertFalse(ctrl.is_ramping)
        self.assertFalse(ctrl.is_enabled)
        self.assertFalse(ctrl.error_triggered)

    def test_custom_calibration(self):
        cal = CalibrationConfig(ga_per_coil=200.0, num_coils=2)
        ctrl = HelmholtzController(InstrumentBus(), UIEventBus(), calibration=cal)
        self.assertAlmostEqual(ctrl.calibration.ga_total, 200.0)


class TestSetField(unittest.TestCase):
    def test_set_field_computes_target(self):
        ctrl = HelmholtzController(InstrumentBus(), UIEventBus())
        cal = ctrl.calibration
        # 341.71 G/A total, so 100 G → ~0.2926 A total → ~0.1463 A/coil
        ctrl.set_field(100.0)
        expected = 100.0 / cal.ga_total / cal.num_coils
        self.assertAlmostEqual(ctrl.target_current, expected, places=5)

    def test_set_field_with_rate_override(self):
        ctrl = HelmholtzController(InstrumentBus(), UIEventBus())
        ctrl.set_field(50.0, rate_mA_per_s=20.0)
        self.assertAlmostEqual(ctrl._rate, 0.02)

    def test_set_field_exceeding_limit_raises(self):
        ctrl = HelmholtzController(InstrumentBus(), UIEventBus())
        # 3A max total → max field = 3 * 341.71 = 1025.13 G
        with self.assertRaises(HelmholtzSafetyError):
            ctrl.set_field(3000.0)

    def test_set_current_directly(self):
        ctrl = HelmholtzController(InstrumentBus(), UIEventBus())
        ctrl.set_current(0.5)  # 0.5 A/coil = 1.0 A total
        self.assertAlmostEqual(ctrl.target_current, 0.5)

    def test_set_current_exceeding_limit_raises(self):
        ctrl = HelmholtzController(InstrumentBus(), UIEventBus())
        with self.assertRaises(HelmholtzSafetyError):
            ctrl.set_current(2.0)  # 2 A/coil = 4 A total


class TestServiceTick(unittest.TestCase):
    def test_tick_when_disabled_returns_false(self):
        ctrl = HelmholtzController(InstrumentBus(), UIEventBus())
        ctrl.set_current(0.5)
        result = ctrl.service_tick(dt=0.1)
        self.assertFalse(result)

    def test_tick_ramps_toward_target(self):
        ctrl = HelmholtzController(InstrumentBus(), UIEventBus())
        ctrl.set_current(0.5)
        ctrl._enabled = True
        ctrl.set_ramp_rate(100.0)  # 100 mA/s = 0.1 A/s

        result = ctrl.service_tick(dt=0.1)
        self.assertTrue(result)  # still ramping
        # 0.1 A/s × 0.1 s = 0.01 A step
        self.assertAlmostEqual(ctrl.actual_current_a, 0.01, places=5)
        self.assertAlmostEqual(ctrl.actual_current_b, 0.01, places=5)

    def test_tick_reaches_target(self):
        ctrl = HelmholtzController(InstrumentBus(), UIEventBus())
        ctrl.set_current(0.01)
        ctrl._enabled = True
        ctrl.set_ramp_rate(1000.0)  # 1 A/s

        # After 0.1s tick: step = 0.1 A >> target 0.01, clamped to target
        result = ctrl.service_tick(dt=0.1)
        self.assertFalse(result)  # done
        self.assertAlmostEqual(ctrl.actual_current_a, 0.01, places=5)
        self.assertAlmostEqual(ctrl.actual_current_b, 0.01, places=5)

    def test_tick_ramps_down(self):
        ctrl = HelmholtzController(InstrumentBus(), UIEventBus())
        ctrl._enabled = True
        ctrl._actual_a = 0.5
        ctrl._actual_b = 0.5
        ctrl.set_current(0.0)
        ctrl.set_ramp_rate(100.0)  # 0.1 A/s

        result = ctrl.service_tick(dt=0.1)
        self.assertTrue(result)
        self.assertAlmostEqual(ctrl.actual_current_a, 0.49, places=5)

    def test_many_ticks_converge(self):
        ctrl = HelmholtzController(InstrumentBus(), UIEventBus())
        ctrl.set_current(0.1)
        ctrl._enabled = True
        ctrl.set_ramp_rate(100.0)  # 0.1 A/s

        for _ in range(200):  # 200 × 0.1s = 20s
            if not ctrl.service_tick(dt=0.1):
                break

        self.assertAlmostEqual(ctrl.actual_current_a, 0.1, places=5)
        self.assertAlmostEqual(ctrl.actual_current_b, 0.1, places=5)
        self.assertFalse(ctrl.is_ramping)

    def test_zero_target_auto_disables_output_when_settled(self):
        ctrl = HelmholtzController(InstrumentBus(), UIEventBus())
        ctrl._enabled = True
        ctrl._actual_a = 0.01
        ctrl._actual_b = 0.01
        ctrl.set_current(0.0)
        ctrl.set_ramp_rate(1000.0)

        still_ramping = ctrl.service_tick(dt=1.0)

        self.assertFalse(still_ramping)
        self.assertFalse(ctrl.is_enabled)
        self.assertAlmostEqual(ctrl.actual_current_a, 0.0, places=7)
        self.assertAlmostEqual(ctrl.actual_current_b, 0.0, places=7)


class TestFieldCalculation(unittest.TestCase):
    def test_field_gauss_at_zero(self):
        ctrl = HelmholtzController(InstrumentBus(), UIEventBus())
        self.assertAlmostEqual(ctrl.field_gauss, 0.0)

    def test_field_gauss_with_current(self):
        ctrl = HelmholtzController(InstrumentBus(), UIEventBus())
        ctrl._actual_a = 0.5
        ctrl._actual_b = 0.5
        # total = 1.0 A → 341.71 G
        self.assertAlmostEqual(ctrl.field_gauss, 341.71, places=1)


class TestEnableDisable(unittest.TestCase):
    def test_enable_output(self):
        bus = _make_mock_bus()
        ctrl = HelmholtzController(bus, UIEventBus())
        ctrl.enable_output()
        self.assertTrue(ctrl.is_enabled)

    def test_disable_output_resets_state(self):
        bus = _make_mock_bus()
        ctrl = HelmholtzController(bus, UIEventBus())
        ctrl._enabled = True
        ctrl._actual_a = 0.5
        ctrl._actual_b = 0.5
        ctrl.disable_output()
        self.assertFalse(ctrl.is_enabled)
        self.assertAlmostEqual(ctrl.actual_current_a, 0.0)
        self.assertAlmostEqual(ctrl.actual_current_b, 0.0)

    def test_enable_without_instrument_noop(self):
        bus = InstrumentBus()  # nothing connected
        ctrl = HelmholtzController(bus, UIEventBus())
        ctrl.enable_output()
        self.assertFalse(ctrl.is_enabled)

    def test_disable_without_instrument_safe(self):
        bus = InstrumentBus()  # nothing connected
        ctrl = HelmholtzController(bus, UIEventBus())
        ctrl._enabled = True
        ctrl.disable_output()
        self.assertFalse(ctrl.is_enabled)

    def test_disable_invalid_session_logs_warning_not_traceback(self):
        class InvalidSession(Exception):
            pass

        bus = _make_mock_bus()
        mock_k = bus.get_raw(INST_KEITHLEY2600)
        mock_k.set_current.side_effect = InvalidSession(
            "Invalid session handle. The resource might be closed."
        )

        ctrl = HelmholtzController(bus, UIEventBus())
        ctrl._enabled = True

        with patch("v3.core.helmholtz_controller.logger") as mock_logger:
            ctrl.disable_output()

        self.assertFalse(ctrl.is_enabled)
        self.assertTrue(mock_logger.warning.called)
        self.assertFalse(mock_logger.exception.called)


class TestApplyTick(unittest.TestCase):
    def test_apply_tick_writes_hardware(self):
        bus = _make_mock_bus()
        ctrl = HelmholtzController(bus, UIEventBus())
        ctrl._enabled = True
        ctrl._actual_a = 0.1
        ctrl._actual_b = 0.1

        ctrl.apply_tick()

        mock_k = bus.get_raw(INST_KEITHLEY2600)
        # Should have called set_current and apply_current for both channels
        self.assertTrue(mock_k.set_current.called)
        self.assertTrue(mock_k.apply_current.called)

    def test_apply_tick_no_instrument_safe(self):
        bus = InstrumentBus()
        ctrl = HelmholtzController(bus, UIEventBus())
        ctrl._enabled = True
        ctrl.apply_tick()  # should not raise


class TestRampToTarget(unittest.TestCase):
    def test_ramp_to_target_basic(self):
        bus = _make_mock_bus()
        ctrl = HelmholtzController(bus, UIEventBus())
        ctrl.set_current(0.01)
        ctrl.set_ramp_rate(1000.0)  # 1 A/s — fast ramp
        stop = threading.Event()

        ctrl.ramp_to_target(stop, tick_interval=0.01)
        self.assertAlmostEqual(ctrl.actual_current_a, 0.01, places=3)
        self.assertFalse(ctrl.is_ramping)

    def test_ramp_to_target_stopped(self):
        bus = _make_mock_bus()
        ctrl = HelmholtzController(bus, UIEventBus())
        ctrl.set_current(1.0)
        ctrl.set_ramp_rate(1.0)  # 0.001 A/s — very slow
        stop = threading.Event()

        # Stop after a short delay
        timer = threading.Timer(0.2, stop.set)
        timer.start()

        ctrl.ramp_to_target(stop, tick_interval=0.05)
        # Should have stopped before reaching target
        self.assertLess(ctrl.actual_current_a, 1.0)
        timer.cancel()


class TestWaitUntilStable(unittest.TestCase):
    def test_already_stable(self):
        ctrl = HelmholtzController(InstrumentBus(), UIEventBus())
        ctrl._enabled = True
        ctrl._target_current = 0.1
        ctrl._actual_a = 0.1
        ctrl._actual_b = 0.1
        stop = threading.Event()

        result = ctrl.wait_until_stable(stop, poll_interval=0.01)
        self.assertTrue(result)

    def test_timeout(self):
        ctrl = HelmholtzController(InstrumentBus(), UIEventBus())
        ctrl._enabled = True
        ctrl._target_current = 1.0
        ctrl._actual_a = 0.0
        ctrl._actual_b = 0.0
        ctrl.set_ramp_rate(0.01)  # extremely slow
        stop = threading.Event()

        result = ctrl.wait_until_stable(
            stop, max_wait_s=0.3, poll_interval=0.05
        )
        self.assertFalse(result)

    def test_stop_cancels_wait(self):
        ctrl = HelmholtzController(InstrumentBus(), UIEventBus())
        ctrl._enabled = True
        ctrl._target_current = 1.0
        ctrl._actual_a = 0.0
        ctrl._actual_b = 0.0
        ctrl.set_ramp_rate(0.01)
        stop = threading.Event()

        timer = threading.Timer(0.1, stop.set)
        timer.start()

        result = ctrl.wait_until_stable(stop, poll_interval=0.05, max_wait_s=10)
        self.assertFalse(result)
        timer.cancel()


class TestSnapshot(unittest.TestCase):
    def test_snapshot_keys(self):
        ctrl = HelmholtzController(InstrumentBus(), UIEventBus())
        ctrl._actual_a = 0.3
        ctrl._actual_b = 0.3
        snap = ctrl.snapshot()
        self.assertIn("Helmholtz_Current", snap)
        self.assertIn("Helmholtz_Field", snap)
        self.assertAlmostEqual(snap["Helmholtz_Current"], 0.6, places=5)
        expected_field = 0.6 * 341.71
        self.assertAlmostEqual(snap["Helmholtz_Field"], expected_field, places=1)


class TestSetRampRate(unittest.TestCase):
    def test_set_ramp_rate(self):
        ctrl = HelmholtzController(InstrumentBus(), UIEventBus())
        ctrl.set_ramp_rate(50.0)  # 50 mA/s
        self.assertAlmostEqual(ctrl._rate, 0.05)


class TestSetCompliance(unittest.TestCase):
    def test_set_compliance(self):
        ctrl = HelmholtzController(InstrumentBus(), UIEventBus())
        ctrl.set_compliance(5.0)
        self.assertAlmostEqual(ctrl._compliance_v, 5.0)


class TestComplianceCheck(unittest.TestCase):
    def test_compliance_exceeded_disables_output(self):
        bus = _make_mock_bus()
        mock_k = bus.get_raw(INST_KEITHLEY2600)
        # Resistance of 100 Ω → at 0.1 A, voltage = 10 V > 3 V compliance
        mock_k.get_resistance.return_value = 100.0

        ctrl = HelmholtzController(bus, UIEventBus())
        ctrl._enabled = True
        ctrl._actual_a = 0.1
        ctrl._actual_b = 0.1

        ctrl.apply_tick()
        self.assertTrue(ctrl.error_triggered)
        self.assertFalse(ctrl.is_enabled)


class TestReadResistances(unittest.TestCase):
    def test_read_resistances(self):
        bus = _make_mock_bus()
        mock_k = bus.get_raw(INST_KEITHLEY2600)
        mock_k.get_resistance.return_value = 2.5

        ctrl = HelmholtzController(bus, UIEventBus())
        ctrl._enabled = True
        ctrl._target_current = 0.1
        ctrl._actual_a = 0.1
        ctrl._actual_b = 0.1
        ra, rb = ctrl.read_resistances()
        self.assertAlmostEqual(ra, 2.5)
        self.assertAlmostEqual(rb, 2.5)

    def test_read_resistances_zero_current_not_measured(self):
        bus = _make_mock_bus()
        mock_k = bus.get_raw(INST_KEITHLEY2600)
        mock_k.get_resistance.return_value = 2.5

        ctrl = HelmholtzController(bus, UIEventBus())
        ctrl._enabled = True
        ctrl._actual_a = 0.0
        ctrl._actual_b = 0.0
        ra, rb = ctrl.read_resistances()
        self.assertTrue(math.isnan(ra))
        self.assertTrue(math.isnan(rb))

    def test_read_resistances_zero_target_still_measured_if_actual_nonzero(self):
        bus = _make_mock_bus()
        mock_k = bus.get_raw(INST_KEITHLEY2600)
        mock_k.get_resistance.return_value = 2.5

        ctrl = HelmholtzController(bus, UIEventBus())
        ctrl._enabled = True
        ctrl._target_current = 0.0
        ctrl._actual_a = 0.2
        ctrl._actual_b = 0.2
        ra, rb = ctrl.read_resistances()
        self.assertAlmostEqual(ra, 2.5)
        self.assertAlmostEqual(rb, 2.5)

    def test_read_resistances_not_connected(self):
        ctrl = HelmholtzController(InstrumentBus(), UIEventBus())
        ra, rb = ctrl.read_resistances()
        self.assertAlmostEqual(ra, 0.0)
        self.assertAlmostEqual(rb, 0.0)


if __name__ == "__main__":
    unittest.main()
