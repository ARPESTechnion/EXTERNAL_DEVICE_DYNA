"""
Tests for v3.core.measurements
"""

from __future__ import annotations

import math
import threading
import time
import unittest
from enum import IntEnum
from unittest.mock import MagicMock, patch

from v3.core.calibration import CalibrationConfig
from v3.core.data_manager import DataManager
from v3.core.helmholtz_controller import HelmholtzController
from v3.core.instrument_bus import InstrumentBus
from v3.core.measurements import (
    MeasurementContext,
    NAN,
    _assign_channel_data,
    _avg_or_nan,
    _safe_div,
    disable_hall_output,
    enable_hall_output,
    measure_iv_curve,
    measure_resistance,
    measure_hall,
    measure_hall_continuous,
    measure_lockin,
    measure_lockin_continuous,
    full_measure,
    wait_for_temp_stable,
    wait_for_field_stable,
    wait_for_events,
    lockin_auto_gain,
    lockin_auto_phase,
    set_lockin_frequency,
    set_lockin_sensitivity,
    set_lockin_current,
    set_dyna_field,
    set_dyna_temp,
    open_all_channels,
    close_channel,
    configure_channel,
)
from v3.core.constants import INST_LOCKIN, INST_KEITHLEY2450, INST_SWITCH, INST_DYNA
from v3.core.ui_events import UIEventBus
from v3.core.ui_events import W_HALL_SOURCE_ENABLED, W_LED_HALL, W_LOCKIN_OUTPUT_VOLTAGE


def _make_context(
    lockin_result=None,
    hall_result=None,
    temp=300.0,
    ppms_field=0.0,
    active_channel="a",
) -> MeasurementContext:
    """Create a MeasurementContext with mocks."""
    bus = InstrumentBus()
    ui_bus = UIEventBus()
    data_mgr = MagicMock(spec=DataManager)
    data_mgr.elapsed_time.return_value = 1.0
    helmholtz = HelmholtzController(bus, ui_bus)
    cal = CalibrationConfig()

    # Mock lock-in
    mock_lockin = MagicMock()
    if lockin_result is None:
        lockin_result = {
            "X": {"mean": 1e-6, "std": 1e-8},
            "Y": {"mean": 2e-6, "std": 2e-8},
            "R": {"mean": 3e-6, "std": 3e-8},
            "Theta": {"mean": 45.0, "std": 0.5},
            "sens_idx": 10,
        }
    mock_lockin.measure.return_value = lockin_result
    mock_lockin.get_reference_amplitude.return_value = 0.004
    mock_lockin._MIN_SLVL = 0.004
    mock_lockin.SENS_TABLE = [1e-9 * (10 ** (i / 3)) for i in range(27)]
    mock_lockin.TAU_TABLE = [1e-5 * (3 ** i) for i in range(20)]
    mock_lockin.get_frequency.return_value = 137.0
    bus.connect(INST_LOCKIN, mock_lockin)

    # Mock K2450
    mock_k2450 = MagicMock()
    if hall_result is None:
        hall_result = (0.001, 0.0001)
    mock_k2450.measure_voltage.return_value = hall_result
    mock_k2450.measure_resistance.return_value = (123.4, 0.5)
    mock_k2450.source_enabled = False
    mock_k2450._source_enabled = False
    mock_k2450.is_mock_hall = False
    mock_k2450.set_source_current_amps.side_effect = lambda value: setattr(mock_k2450, "current_setpoint", value)
    mock_k2450.set_source_voltage_volts.side_effect = lambda value: setattr(mock_k2450, "voltage_setpoint", value)

    def _enable_source_side_effect(*_args, **_kwargs):
        mock_k2450.source_enabled = True
        mock_k2450._source_enabled = True

    def _disable_source_side_effect(*_args, **_kwargs):
        mock_k2450.source_enabled = False
        mock_k2450._source_enabled = False

    mock_k2450.enable_source.side_effect = _enable_source_side_effect
    mock_k2450.disable_source.side_effect = _disable_source_side_effect
    bus.connect(INST_KEITHLEY2450, mock_k2450)

    # Mock switch
    mock_switch = MagicMock()
    mock_switch.closed_channels = ["1", "2", "3", "4"]
    bus.connect(INST_SWITCH, mock_switch)

    # Mock dyna
    mock_dyna = MagicMock()
    mock_dyna.get_temperature.return_value = (0, temp, 1, "Stable")
    mock_dyna.get_field.return_value = (0, ppms_field, 1)
    bus.connect(INST_DYNA, mock_dyna)

    ctx = MeasurementContext(
        bus=bus,
        ui_bus=ui_bus,
        data_mgr=data_mgr,
        helmholtz=helmholtz,
        calibration=cal,
        get_temp=lambda: temp,
        get_ppms_field=lambda: ppms_field,
        get_active_channel=lambda: active_channel,
    )
    return ctx


# ============================================================================
# Helper tests
# ============================================================================
class TestHelpers(unittest.TestCase):
    def test_avg_or_nan_normal(self):
        self.assertAlmostEqual(_avg_or_nan(10.0, 20.0), 15.0)

    def test_avg_or_nan_none(self):
        self.assertTrue(math.isnan(_avg_or_nan(None, 20.0)))
        self.assertTrue(math.isnan(_avg_or_nan(10.0, None)))

    def test_safe_div_normal(self):
        self.assertAlmostEqual(_safe_div(10.0, 2.0), 5.0)

    def test_safe_div_zero(self):
        self.assertTrue(math.isnan(_safe_div(10.0, 0.0)))

    def test_safe_div_nan(self):
        self.assertTrue(math.isnan(_safe_div(float("nan"), 1.0)))


class TestAssignChannelData(unittest.TestCase):
    def test_channel_a(self):
        dp = {}
        _assign_channel_data(
            dp, "a",
            x=1.0, y=2.0, r=3.0, theta=4.0,
            x_std=0.1, y_std=0.2, r_std=0.3, theta_std=0.4,
            sample_resistance=100.0, sample_resistance_std=1.0,
        )
        self.assertAlmostEqual(dp["LockIn_X_a"], 1.0)
        self.assertAlmostEqual(dp["Sample_a_Resistance"], 100.0)
        self.assertTrue(math.isnan(dp["Sample_b_Resistance"]))

    def test_channel_b(self):
        dp = {}
        _assign_channel_data(
            dp, "b",
            x=1.0, y=2.0, r=3.0, theta=4.0,
            x_std=0.1, y_std=0.2, r_std=0.3, theta_std=0.4,
            sample_resistance=100.0, sample_resistance_std=1.0,
        )
        self.assertAlmostEqual(dp["LockIn_X_b"], 1.0)
        self.assertAlmostEqual(dp["Sample_b_Resistance"], 100.0)
        self.assertTrue(math.isnan(dp["Sample_a_Resistance"]))

    def test_channel_none(self):
        dp = {}
        _assign_channel_data(
            dp, None,
            x=1.0, y=2.0, r=3.0, theta=4.0,
            x_std=0.1, y_std=0.2, r_std=0.3, theta_std=0.4,
            sample_resistance=100.0, sample_resistance_std=1.0,
        )
        self.assertNotIn("LockIn_X_a", dp)
        self.assertNotIn("LockIn_X_b", dp)


# ============================================================================
# Lock-in measurement tests
# ============================================================================
class TestMeasureLockin(unittest.TestCase):
    def test_basic_measurement(self):
        ctx = _make_context()
        result = measure_lockin(ctx, current=0.001, series_resistance=1000.0)

        self.assertIn("Time", result)
        self.assertIn("LockIn_Frequency", result)
        self.assertIn("Temp", result)
        self.assertIn("Helmholtz_Current", result)

    def test_channel_a_data(self):
        ctx = _make_context(active_channel="a")
        result = measure_lockin(ctx, current=0.001, series_resistance=1000.0)

        self.assertIn("LockIn_X_a", result)
        self.assertNotIn("LockIn_X_b", result)
        self.assertIn("Sample_a_Resistance", result)

    def test_channel_b_data(self):
        ctx = _make_context(active_channel="b")
        result = measure_lockin(ctx, current=0.001, series_resistance=1000.0)

        self.assertIn("LockIn_X_b", result)
        self.assertNotIn("LockIn_X_a", result)

    def test_output_voltage_computed(self):
        ctx = _make_context()
        result = measure_lockin(ctx, current=0.001, series_resistance=1000.0)

        self.assertAlmostEqual(result["LockIn_Output_Voltage"], 1.0)
        self.assertAlmostEqual(result["LockIn_Output_Current"], 0.001)

    def test_ppms_averaging(self):
        ctx = _make_context(temp=300.0, ppms_field=1000.0)
        result = measure_lockin(ctx, current=0.001, series_resistance=1000.0)

        self.assertAlmostEqual(result["Temp"], 300.0)
        self.assertAlmostEqual(result["In-plane_Field"], 1000.0)

    def test_posts_output_voltage_event_after_measure(self):
        ctx = _make_context()
        measure_lockin(ctx, current=0.001, series_resistance=1000.0)
        events = ctx.ui_bus.drain()
        self.assertAlmostEqual(events[W_LOCKIN_OUTPUT_VOLTAGE], 0.004)

    def test_records_lockin_average_count(self):
        ctx = _make_context()
        result = measure_lockin(ctx, current=0.001, series_resistance=1000.0, avg=17)
        self.assertEqual(result["LockIn_Average_Count"], 17)


class TestMeasureLockinContinuous(unittest.TestCase):
    def test_basic_continuous(self):
        ctx = _make_context()
        result = measure_lockin_continuous(
            ctx, current=0.001, series_resistance=1000.0
        )
        self.assertIn("Time", result)
        self.assertIn("LockIn_Frequency", result)

    def test_posts_output_voltage_event(self):
        ctx = _make_context()
        measure_lockin_continuous(
            ctx,
            current=0.001,
            series_resistance=1000.0,
        )
        events = ctx.ui_bus.drain()
        self.assertAlmostEqual(events[W_LOCKIN_OUTPUT_VOLTAGE], 1.0)


class TestMeasureResistance(unittest.TestCase):
    def test_basic_resistance_measurement(self):
        ctx = _make_context()
        ctx.bus.get_raw(INST_KEITHLEY2450).measure_voltage.return_value = (1.2, 0.06)
        result = measure_resistance(
            ctx,
            current=1e-3,
            compliance=5.0,
            nplc=1.0,
            voltage_range=20.0,
            auto_range=False,
            settle_time=0.0,
            repetitions=1,
        )

        self.assertIn("Sample_Resistance", result)
        self.assertIn("Sample_Resistance_Error", result)
        self.assertAlmostEqual(result["Sample_Resistance"], 1200.0)
        self.assertAlmostEqual(result["Sample_Resistance_Error"], 60.0)
        self.assertAlmostEqual(result["IV_Source_Current"], 1.0)
        self.assertAlmostEqual(result["IV_Measured_Voltage"], 1.2)

    def test_autorange_primes_safe_voltage_range_before_apply_current(self):
        ctx = _make_context()
        mock_k2450 = ctx.bus.get_raw(INST_KEITHLEY2450)
        mock_k2450.measure_voltage.return_value = (0.5, 0.01)

        measure_resistance(
            ctx,
            current=1e-3,
            compliance=5.0,
            nplc=1.0,
            voltage_range=None,
            auto_range=True,
            settle_time=0.0,
            repetitions=1,
        )

        write_calls = [c.args[0] for c in mock_k2450.write.call_args_list]
        self.assertIn(":SENS:FUNC 'VOLT'", write_calls)
        self.assertIn(":SENS:VOLT:RANG 21", write_calls)
        self.assertIn(":SENS:VOLT:RANG:AUTO ON", write_calls)


class TestMeasureIvCurve(unittest.TestCase):
    def test_current_mode_iv_curve(self):
        ctx = _make_context()
        ctx.bus.get_raw(INST_KEITHLEY2450).measure_voltage.side_effect = [(1.0, 0.1), (2.0, 0.2)]

        result = measure_iv_curve(
            ctx,
            mode="current",
            shape="single",
            start=1e-3,
            stop=2e-3,
            step=1e-3,
            nplc=1.0,
            repetitions=1,
        )

        self.assertEqual(result["mode"], "source_current")
        self.assertEqual(result["point_count"], 2)
        self.assertEqual(len(result["points"]), 2)
        self.assertAlmostEqual(result["points"][0]["IV_Point"], 1)
        self.assertAlmostEqual(result["points"][0]["IV_Source_Current"], 1.0)
        self.assertAlmostEqual(result["points"][0]["IV_Measured_Voltage"], 1.0)
        self.assertNotIn("IV_Resistance", result["points"][0])

    def test_voltage_mode_iv_curve(self):
        ctx = _make_context()
        ctx.bus.get_raw(INST_KEITHLEY2450).measure_current.side_effect = [(1e-3, 1e-4), (2e-3, 2e-4)]

        result = measure_iv_curve(
            ctx,
            mode="voltage",
            shape="single",
            start=0.1,
            stop=0.2,
            step=0.1,
            nplc=1.0,
            repetitions=1,
        )

        self.assertEqual(result["mode"], "source_voltage")
        self.assertEqual(result["point_count"], 2)
        self.assertAlmostEqual(result["points"][0]["IV_Point"], 1)
        self.assertAlmostEqual(result["points"][0]["IV_Source_Voltage"], 0.1)
        self.assertAlmostEqual(result["points"][0]["IV_Measured_Current"], 1.0)
        self.assertNotIn("IV_Resistance", result["points"][0])

    def test_return_shape_iv_curve(self):
        ctx = _make_context()
        mock_k2450 = ctx.bus.get_raw(INST_KEITHLEY2450)
        mock_k2450.measure_voltage.side_effect = [
            (0.0, 0.0),
            (1.0, 0.0),
            (2.0, 0.0),
            (1.0, 0.0),
            (0.0, 0.0),
        ]

        result = measure_iv_curve(
            ctx,
            mode="current",
            shape="return",
            start=0.0,
            stop=2e-3,
            step=1e-3,
            nplc=1.0,
            repetitions=1,
        )

        self.assertEqual(result["shape"], "return")
        self.assertEqual(result["point_count"], 5)
        currents = [point["IV_Source_Current"] for point in result["points"]]
        self.assertEqual(currents, [0.0, 1.0, 2.0, 1.0, 0.0])

    def test_fast_iv_repetitions_collapses_expanded_payload(self):
        ctx = _make_context()
        mock_k2450 = ctx.bus.get_raw(INST_KEITHLEY2450)
        mock_k2450.run_iv_sweep_fast.return_value = [0.9, 1.1, 1.9, 2.1]

        result = measure_iv_curve(
            ctx,
            mode="current",
            shape="single",
            start=1e-3,
            stop=2e-3,
            step=1e-3,
            nplc=1.0,
            repetitions=2,
        )

        self.assertEqual(result["engine"], "fast")
        self.assertEqual(result["point_count"], 2)
        self.assertAlmostEqual(result["points"][0]["IV_Measured_Voltage"], 1.0)
        self.assertAlmostEqual(result["points"][1]["IV_Measured_Voltage"], 2.0)

    def test_fast_iv_repetitions_invalid_payload_falls_back_to_point_mode(self):
        ctx = _make_context()
        mock_k2450 = ctx.bus.get_raw(INST_KEITHLEY2450)

        # For repetitions > 1 this logical-length payload is malformed and
        # must force point-mode fallback.
        mock_k2450.run_iv_sweep_fast.return_value = [1.0, 2.0]
        mock_k2450.measure_voltage.side_effect = [(1.2, 0.1), (2.3, 0.1)]

        result = measure_iv_curve(
            ctx,
            mode="current",
            shape="single",
            start=1e-3,
            stop=2e-3,
            step=1e-3,
            nplc=1.0,
            repetitions=3,
        )

        self.assertEqual(result["engine"], "point")
        self.assertEqual(result["point_count"], 2)
        self.assertAlmostEqual(result["points"][0]["IV_Measured_Voltage"], 1.2)
        self.assertAlmostEqual(result["points"][1]["IV_Measured_Voltage"], 2.3)

    def test_continuous_measure_disables_excitation_management_and_settling_wait(self):
        ctx = _make_context()
        mock_lockin = ctx.bus.get_raw(INST_LOCKIN)

        measure_lockin_continuous(
            ctx,
            current=0.001,
            series_resistance=1000.0,
        )

        mock_lockin.sine_output_on.assert_not_called()
        mock_lockin.sine_output_off.assert_not_called()
        self.assertIs(mock_lockin.measure.call_args.kwargs.get("manage_excitation"), False)
        self.assertIs(
            mock_lockin.measure.call_args.kwargs.get("wait_for_settling_when_no_autorange"),
            False,
        )

    def test_records_lockin_average_count(self):
        ctx = _make_context()
        result = measure_lockin_continuous(
            ctx,
            current=0.001,
            series_resistance=1000.0,
            avg=23,
        )
        self.assertEqual(result["LockIn_Average_Count"], 23)


# ============================================================================
# Hall measurement tests
# ============================================================================
class TestMeasureHall(unittest.TestCase):
    def test_basic_measurement(self):
        ctx = _make_context(hall_result=(0.005, 0.0001))
        result = measure_hall(ctx, current_mA=1.0, compliance_v=10.0)

        self.assertIn("Hall Voltage", result)
        self.assertAlmostEqual(result["Hall Voltage"], 0.005)
        self.assertIn("Hall Voltage Error", result)
        self.assertIn("Hall Field", result)
        self.assertIn("Hall Field Error", result)

    def test_field_conversion(self):
        ctx = _make_context(hall_result=(0.005, 0.0001))
        result = measure_hall(ctx, current_mA=1.0)

        # With default calibration: hall_v2gauss=1.0, offset=0
        self.assertAlmostEqual(result["Hall Field"], 0.005)

    def test_source_events_cleanup(self):
        ctx = _make_context(hall_result=(0.005, 0.0001))
        measure_hall(ctx, current_mA=1.0)
        events = ctx.ui_bus.drain()
        self.assertIs(events[W_HALL_SOURCE_ENABLED], False)
        self.assertIs(events[W_LED_HALL], False)

    def test_continuous_enables_and_waits_when_output_off(self):
        ctx = _make_context(hall_result=(0.005, 0.0001))
        mock_k2450 = ctx.bus.get_raw(INST_KEITHLEY2450)
        mock_k2450.source_enabled = False
        mock_k2450._source_enabled = False

        with patch("v3.core.measurements.time.sleep", return_value=None) as sleep_mock:
            measure_hall_continuous(ctx, current_mA=1.0, compliance_v=2.0, tbm=0.3)

        mock_k2450.enable_source.assert_called_once()
        mock_k2450.disable_source.assert_not_called()
        sleep_mock.assert_called_with(0.3)

    def test_continuous_skips_tbm_when_output_already_on(self):
        ctx = _make_context(hall_result=(0.005, 0.0001))
        mock_k2450 = ctx.bus.get_raw(INST_KEITHLEY2450)
        mock_k2450.source_enabled = True
        mock_k2450._source_enabled = True

        with patch("v3.core.measurements.time.sleep", return_value=None) as sleep_mock:
            measure_hall_continuous(ctx, current_mA=1.0, compliance_v=2.0, tbm=0.3)

        mock_k2450.enable_source.assert_not_called()
        mock_k2450.disable_source.assert_not_called()
        sleep_mock.assert_not_called()

    def test_enable_disable_hall_output_events(self):
        ctx = _make_context(hall_result=(0.005, 0.0001))
        enable_hall_output(ctx, current_mA=1.0, compliance_v=2.0)
        events = ctx.ui_bus.drain()
        self.assertIs(events[W_HALL_SOURCE_ENABLED], True)
        self.assertIs(events[W_LED_HALL], True)

        disable_hall_output(ctx)
        events = ctx.ui_bus.drain()
        self.assertIs(events[W_HALL_SOURCE_ENABLED], False)
        self.assertIs(events[W_LED_HALL], False)

    def test_mock_model_linear_terms(self):
        ctx = _make_context(hall_result=(0.0, 0.0), ppms_field=1000.0)
        mock_k2450 = ctx.bus.get_raw(INST_KEITHLEY2450)
        mock_k2450.is_mock_hall = True

        ctx.helmholtz.snapshot = lambda: {
            "Helmholtz_Current": 0.0,
            "Helmholtz_Field": 500.0,
        }

        cal = ctx.calibration
        cal.hall_mock_enabled = True
        cal.hall_mock_helmholtz_gain = 1.0
        cal.hall_mock_ppms_gain = 0.01
        cal.hall_mock_offset_g = 2.0
        cal.hall_mock_v2gauss = 100.0
        cal.hall_mock_noise_floor_v = 0.0
        cal.hall_mock_noise_rel = 0.0

        result = measure_hall(ctx, current_mA=1.0, filter_count=5)
        self.assertAlmostEqual(result["Hall Field"], 512.0, places=9)
        self.assertAlmostEqual(result["Hall Voltage"], 5.12, places=9)
        self.assertAlmostEqual(result["Hall Field Error"], 0.0, places=9)

    def test_mock_model_adds_noise(self):
        ctx = _make_context(hall_result=(0.0, 0.0), ppms_field=0.0)
        mock_k2450 = ctx.bus.get_raw(INST_KEITHLEY2450)
        mock_k2450.is_mock_hall = True

        ctx.helmholtz.snapshot = lambda: {
            "Helmholtz_Current": 0.0,
            "Helmholtz_Field": 100.0,
        }

        cal = ctx.calibration
        cal.hall_mock_enabled = True
        cal.hall_mock_helmholtz_gain = 1.0
        cal.hall_mock_ppms_gain = 0.0
        cal.hall_mock_offset_g = 0.0
        cal.hall_mock_v2gauss = 50.0
        cal.hall_mock_noise_floor_v = 1e-3
        cal.hall_mock_noise_rel = 0.0
        cal.hall_mock_seed = 12345
        cal.__post_init__()

        result = measure_hall(ctx, current_mA=1.0, filter_count=25)
        self.assertGreater(result["Hall Voltage Error"], 0.0)
        self.assertGreater(result["Hall Field Error"], 0.0)


# ============================================================================
# Full measure tests
# ============================================================================
class TestFullMeasure(unittest.TestCase):
    def test_combines_hall_and_lockin(self):
        ctx = _make_context(
            hall_result=(0.005, 0.0001),
            active_channel="a",
        )
        result = full_measure(
            ctx,
            hall_current_mA=1.0,
            lockin_current=0.001,
            lockin_series_resistance=1000.0,
        )

        # Should have both Hall and Lock-in data
        self.assertIn("Hall Voltage", result)
        self.assertIn("LockIn_X_a", result)
        self.assertIn("Sample_a_Resistance", result)
        self.assertIn("Helmholtz_Current", result)


# ============================================================================
# PPMS wait tests
# ============================================================================
class TestWaitForTempStable(unittest.TestCase):
    def test_already_stable(self):
        ctx = _make_context(temp=300.0)
        stop = threading.Event()
        result = wait_for_temp_stable(ctx, stop, poll_interval=0.01)
        self.assertTrue(result)

    def test_stop_cancels(self):
        ctx = _make_context()
        # Make it not stable
        mock_dyna = ctx.bus.get_raw(INST_DYNA)
        mock_dyna.get_temperature.return_value = (0, 300.0, 5, "Settling")

        stop = threading.Event()
        timer = threading.Timer(0.1, stop.set)
        timer.start()

        result = wait_for_temp_stable(ctx, stop, poll_interval=0.05, max_wait_s=10)
        self.assertFalse(result)
        timer.cancel()


class TestWaitForFieldStable(unittest.TestCase):
    def test_already_stable(self):
        ctx = _make_context(ppms_field=1000.0)
        stop = threading.Event()
        result = wait_for_field_stable(ctx, stop, poll_interval=0.01)
        self.assertTrue(result)


class TestWaitForEvents(unittest.TestCase):
    def test_no_event_countdown(self):
        ctx = _make_context()
        stop = threading.Event()
        # Should finish quickly with tiny duration
        wait_for_events(ctx, stop, ["no_event"], additional_time=0.05)

    def test_no_event_respects_stop_request(self):
        ctx = _make_context()
        stop = threading.Event()
        stop.set()

        t0 = time.perf_counter()
        wait_for_events(ctx, stop, ["no_event"], additional_time=2.0)
        elapsed = time.perf_counter() - t0

        self.assertLess(elapsed, 0.2)

    def test_all_events(self):
        ctx = _make_context()
        stop = threading.Event()
        wait_for_events(ctx, stop, ["all"], additional_time=0.0)


# ============================================================================
# Lock-in utility tests
# ============================================================================
class TestLockinUtilities(unittest.TestCase):
    def test_auto_gain(self):
        ctx = _make_context()
        mock_lockin = ctx.bus.get_raw(INST_LOCKIN)
        mock_lockin.get_sensitivity.return_value = 15
        idx = lockin_auto_gain(ctx)
        self.assertEqual(idx, 15)
        mock_lockin.quick_autorange.assert_called_once()

    def test_auto_gain_falls_back_to_safe_auto_gain(self):
        ctx = _make_context()
        mock_lockin = ctx.bus.get_raw(INST_LOCKIN)
        delattr(mock_lockin, "quick_autorange")
        mock_lockin.get_sensitivity.return_value = 12
        idx = lockin_auto_gain(ctx)
        self.assertEqual(idx, 12)
        mock_lockin.safe_auto_gain.assert_called_once()

    def test_set_frequency(self):
        ctx = _make_context()
        set_lockin_frequency(ctx, 137.0)
        mock_lockin = ctx.bus.get_raw(INST_LOCKIN)
        mock_lockin.set_frequency.assert_called_with(137.0)

    def test_set_sensitivity(self):
        ctx = _make_context()
        set_lockin_sensitivity(ctx, 17)
        mock_lockin = ctx.bus.get_raw(INST_LOCKIN)
        mock_lockin.set_sensitivity.assert_called_with(17)

    def test_set_current_clamps_to_minimum_voltage(self):
        ctx = _make_context()
        mock_lockin = ctx.bus.get_raw(INST_LOCKIN)
        applied_v = set_lockin_current(ctx, current=1e-7, series_resistance=1000.0)
        self.assertAlmostEqual(applied_v, 0.004)
        mock_lockin.set_excitation_current.assert_called_with(4e-6, 1000.0)


class TestDynaApproachResolution(unittest.TestCase):
    def test_set_dyna_temp_fast_settle_alias_to_enum(self):
        ctx = _make_context()
        mock_dyna = ctx.bus.get_raw(INST_DYNA)

        class TempModeEnum(IntEnum):
            fast_settle = 0
            no_overshoot = 1

        mock_dyna.Temp_mode = TempModeEnum

        with patch("v3.core.measurements.time.sleep", return_value=None):
            set_dyna_temp(ctx, 300.0, 2.0, "fast")

        mock_dyna.set_temperature.assert_called_with(300.0, 2.0, TempModeEnum.fast_settle)

    def test_set_dyna_field_string_to_enum(self):
        ctx = _make_context()
        mock_dyna = ctx.bus.get_raw(INST_DYNA)

        class FieldModeEnum(IntEnum):
            linear = 0
            no_overshoot = 1
            oscillate = 2

        mock_dyna.Field_mode = FieldModeEnum

        with patch("v3.core.measurements.time.sleep", return_value=None):
            set_dyna_field(ctx, 1000.0, 10.0, "linear")

        mock_dyna.set_field.assert_called_with(1000.0, 10.0, FieldModeEnum.linear)

    def test_set_dyna_field_rate_capped_to_50(self):
        ctx = _make_context()
        mock_dyna = ctx.bus.get_raw(INST_DYNA)

        class FieldModeEnum(IntEnum):
            linear = 0
            no_overshoot = 1
            oscillate = 2

        mock_dyna.Field_mode = FieldModeEnum

        with patch("v3.core.measurements.time.sleep", return_value=None):
            set_dyna_field(ctx, 1000.0, 120.0, "linear")

        mock_dyna.set_field.assert_called_with(1000.0, 50.0, FieldModeEnum.linear)


# ============================================================================
# Switch tests
# ============================================================================
class TestSwitchCommands(unittest.TestCase):
    def test_open_all(self):
        ctx = _make_context()
        open_all_channels(ctx)
        mock_switch = ctx.bus.get_raw(INST_SWITCH)
        mock_switch.open_all_channels.assert_called_once()

    def test_close_channel(self):
        ctx = _make_context()
        close_channel(ctx, 3)
        mock_switch = ctx.bus.get_raw(INST_SWITCH)
        mock_switch.close_channel.assert_called_with(3)

    def test_configure_channel_validates(self):
        ctx = _make_context()
        with self.assertRaises(ValueError):
            configure_channel(ctx, "a", 1, 1, 3, 4)  # duplicate

        with self.assertRaises(ValueError):
            configure_channel(ctx, "a", 0, 2, 3, 4)  # out of range

        with self.assertRaises(ValueError):
            configure_channel(ctx, "a", 1, 2, 3, 9)  # out of range (1-8)

    def test_configure_channel_success(self):
        ctx = _make_context()
        routing = configure_channel(ctx, "a", 1, 2, 3, 4)
        self.assertEqual(routing, {"I+": 1, "V+": 2, "V-": 3, "I-": 4})


if __name__ == "__main__":
    unittest.main()
