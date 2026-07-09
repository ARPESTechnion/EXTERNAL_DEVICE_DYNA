"""
v3.core.measurements  -  Pure-logic measurement functions.

Each measurement function receives a ``MeasurementContext`` and returns a
``dict[str, float]`` data-point.  They do NOT touch Tkinter, do NOT write
CSV directly, and do NOT manage state - those responsibilities belong to
the caller (ExperimentEngine / GUI layer).

The ``MeasurementContext`` groups the shared dependencies that every
measurement needs (InstrumentBus, UIEventBus, DataManager, HelmholtzController,
CalibrationConfig, stop_event, and snapshot accessors for PPMS state).
"""

from __future__ import annotations

import logging
import math
import time
from dataclasses import dataclass, field
from typing import Any, Callable

from v3.core.calibration import CalibrationConfig
from v3.core.constants import (
    INST_DYNA,
    INST_KEITHLEY2450,
    INST_LOCKIN,
    INST_SWITCH,
    SWITCH_PIN_MAX,
)
from v3.core.data_manager import DataManager
from v3.core.helmholtz_controller import HelmholtzController
from v3.core.instrument_bus import InstrumentBus
from v3.core.ui_events import (
    UIEventBus,
    W_HALL_SOURCE_ENABLED,
    W_LED_HALL,
    W_LED_LOCKIN,
    W_LED_SWITCH,
    W_LOCKIN_OUTPUT_VOLTAGE,
    W_LOG_MESSAGE,
    W_SWITCH_STATUS,
)

logger = logging.getLogger(__name__)

NAN = float("nan")

_KEITHLEY_CURRENT_RES_A = 1e-9
_LOCKIN_VOLTAGE_RES_V = 1e-3
_DYNA_FIELD_RES_OE = 1e-3
_DYNA_TEMP_RES_K = 1e-5


class IVMeasurementCancelled(RuntimeError):
    """Raised when a cooperative stop is requested during IV measurement."""


# ============================================================================
# MeasurementContext  -  shared dependencies for every measurement
# ============================================================================
@dataclass
class MeasurementContext:
    """
    All resources a measurement function needs, bundled together so that
    function signatures stay clean and testable (inject a mock context).
    """

    bus: InstrumentBus
    ui_bus: UIEventBus
    data_mgr: DataManager
    helmholtz: HelmholtzController
    calibration: CalibrationConfig

    # PPMS snapshot accessors - return current values, or NaN
    get_temp: Callable[[], float] = field(default=lambda: NAN)
    get_ppms_field: Callable[[], float] = field(default=lambda: NAN)

    # Active switch channel ("a", "b", or None)
    get_active_channel: Callable[[], str | None] = field(default=lambda: None)


# ============================================================================
# Helpers
# ============================================================================
def _avg_or_nan(start: float | None, end: float | None) -> float:
    """Average of two nullable values; NaN if either is None."""
    if start is not None and end is not None:
        try:
            return (start + end) / 2.0
        except (TypeError, ValueError):
            return NAN
    return NAN


def _safe_div(a: float, b: float) -> float:
    """Safe division, returns NaN on zero/NaN."""
    try:
        if b == 0 or math.isnan(a) or math.isnan(b):
            return NAN
        return a / b
    except (TypeError, ValueError):
        return NAN


def _round_to(value: float, resolution: float) -> float:
    if resolution <= 0:
        return float(value)
    return round(float(value) / resolution) * resolution


def _finite_or_zero(value: Any) -> float:
    try:
        out = float(value)
        if math.isnan(out) or math.isinf(out):
            return 0.0
        return out
    except Exception:
        return 0.0


def _is_mock_hall_driver(ctx: MeasurementContext) -> bool:
    inst = ctx.bus.get_raw(INST_KEITHLEY2450)
    if inst is None:
        return False
    return bool(getattr(inst, "is_mock_hall", False))


def _simulate_mock_hall_voltage(
    ctx: MeasurementContext,
    *,
    helmholtz_field_g: float,
    ppms_field_oe: float,
    repetitions: int,
) -> tuple[float, float, float, float]:
    """Return mock Hall voltage/std and corresponding field/std."""
    cal = ctx.calibration
    gain_helm = float(getattr(cal, "hall_mock_helmholtz_gain", 1.0))
    gain_ppms = float(getattr(cal, "hall_mock_ppms_gain", 0.01))
    offset_g = float(getattr(cal, "hall_mock_offset_g", 0.0))
    v2g = float(getattr(cal, "hall_mock_v2gauss", 10000.0 / 0.215))
    if not math.isfinite(v2g) or abs(v2g) < 1e-12:
        v2g = 10000.0 / 0.215

    model_field_g = gain_helm * helmholtz_field_g + gain_ppms * ppms_field_oe + offset_g
    nominal_voltage_v = model_field_g / v2g

    noise_floor = max(0.0, float(getattr(cal, "hall_mock_noise_floor_v", 0.0)))
    noise_rel = max(0.0, float(getattr(cal, "hall_mock_noise_rel", 0.0)))
    noise_sigma_v = noise_floor + abs(nominal_voltage_v) * noise_rel

    reps = max(int(repetitions), 1)
    rng = cal.hall_mock_rng() if hasattr(cal, "hall_mock_rng") else None
    if rng is None:
        import random
        rng = random.Random()

    if reps <= 1:
        voltage_v = nominal_voltage_v + (rng.gauss(0.0, noise_sigma_v) if noise_sigma_v > 0 else 0.0)
        voltage_std_v = 0.0
    else:
        samples = [
            nominal_voltage_v + (rng.gauss(0.0, noise_sigma_v) if noise_sigma_v > 0 else 0.0)
            for _ in range(reps)
        ]
        voltage_v = sum(samples) / reps
        variance = sum((sample - voltage_v) ** 2 for sample in samples) / (reps - 1)
        voltage_std_v = math.sqrt(max(0.0, variance))

    field_std_g = abs(voltage_std_v) * abs(v2g)
    return float(voltage_v), float(voltage_std_v), float(model_field_g), float(field_std_g)


# ============================================================================
# Lock-in measurement
# ============================================================================
def measure_lockin(
    ctx: MeasurementContext,
    *,
    what: tuple[str, ...] = ("X", "Y", "R", "Theta"),
    current: float | None = None,
    series_resistance: float | None = None,
    avg: int = 10,
    start_sens: int = 10,
    use_autorange: bool = True,
    use_autophase: bool = True,
    sample_delay: float = 0.05,
    manage_excitation: bool = True,
    tau_idx: int = 0,
    filter_slope_idx: int = 0,
    frequency: float | None = None,
) -> dict[str, Any]:
    """
    Perform a lock-in measurement and return a data-point dict.

    Parameters match V2's ``lockin_measure()`` but without GUI coupling.

    Returns
    -------
    dict
        Data-point dict with keys matching ``DATA_KEY_TO_CSV``.
    """
    ctx.ui_bus.post(W_LED_LOCKIN, True)

    # Capture start conditions
    start_temp = ctx.get_temp()
    start_field = ctx.get_ppms_field()
    start_helmholtz = ctx.helmholtz.snapshot()

    # Configure lock-in
    ctx.bus.execute(INST_LOCKIN, "set_time_constant", tau_idx)
    ctx.bus.execute(INST_LOCKIN, "set_filter_slope", filter_slope_idx)

    # Resolve defaults
    if current is None:
        current = 0.0
    if series_resistance is None:
        series_resistance = 0.0

    output_voltage = current * series_resistance
    ctx.ui_bus.post(W_LOCKIN_OUTPUT_VOLTAGE, output_voltage)

    # Perform measurement via lock-in driver
    result = ctx.bus.execute(
        INST_LOCKIN,
        "measure",
        what=what,
        current=current,
        series_resistance=series_resistance,
        avg=avg,
        start_sens=start_sens,
        use_autorange=use_autorange,
        use_autophase=use_autophase,
        sample_delay=sample_delay,
        manage_excitation=manage_excitation,
    )

    try:
        lockin_raw = ctx.bus.get_raw(INST_LOCKIN)
        if lockin_raw is not None and hasattr(lockin_raw, "get_reference_amplitude"):
            current_output = float(ctx.bus.execute(INST_LOCKIN, "get_reference_amplitude"))
            ctx.ui_bus.post(W_LOCKIN_OUTPUT_VOLTAGE, current_output)
    except Exception:
        logger.debug("Could not read lock-in output amplitude after measurement", exc_info=True)

    # Capture end conditions
    end_temp = ctx.get_temp()
    end_field = ctx.get_ppms_field()
    end_helmholtz = ctx.helmholtz.snapshot()

    # Average start/end conditions
    avg_temp = _avg_or_nan(start_temp, end_temp)
    avg_ppms_field = _avg_or_nan(start_field, end_field)
    avg_helmholtz_current = _avg_or_nan(
        start_helmholtz.get("Helmholtz_Current"),
        end_helmholtz.get("Helmholtz_Current"),
    )
    avg_helmholtz_field = _avg_or_nan(
        start_helmholtz.get("Helmholtz_Field"),
        end_helmholtz.get("Helmholtz_Field"),
    )

    # Extract values
    x = result.get("X", {}).get("mean", NAN)
    y = result.get("Y", {}).get("mean", NAN)
    r = result.get("R", {}).get("mean", NAN)
    theta = result.get("Theta", {}).get("mean", NAN)
    x_std = result.get("X", {}).get("std", NAN)
    y_std = result.get("Y", {}).get("std", NAN)
    r_std = result.get("R", {}).get("std", NAN)
    theta_std = result.get("Theta", {}).get("std", NAN)
    sens_idx = result.get("sens_idx", start_sens)

    # Compute derived values
    sample_resistance = _safe_div(r, current)
    sample_resistance_std = _safe_div(r_std, current)

    # Get sensitivity value from lock-in
    try:
        sens_table = ctx.bus.get_raw(INST_LOCKIN)
        if sens_table is not None and hasattr(sens_table, "SENS_TABLE"):
            sensitivity_v = sens_table.SENS_TABLE[sens_idx]
        else:
            sensitivity_v = NAN
    except (IndexError, AttributeError):
        sensitivity_v = NAN

    # Get tau value
    try:
        lockin_raw = ctx.bus.get_raw(INST_LOCKIN)
        if lockin_raw is not None and hasattr(lockin_raw, "TAU_TABLE"):
            tau_value = lockin_raw.TAU_TABLE[tau_idx]
        else:
            tau_value = NAN
    except (IndexError, AttributeError):
        tau_value = NAN

    # Resolve frequency
    if frequency is None:
        try:
            frequency = ctx.bus.execute(INST_LOCKIN, "get_frequency")
        except Exception:
            frequency = NAN

    # Determine active channel
    active_channel = ctx.get_active_channel() or "N/A"

    # Build data point
    data_point: dict[str, Any] = {
        "Time": ctx.data_mgr.elapsed_time(),
        "LockIn_Average_Count": int(avg),
        "LockIn_Frequency": frequency,
        "LockIn_Sensitivity": sensitivity_v,
        "LockIn_R_lockin": series_resistance,
        "LockIn_Output_Voltage": output_voltage,
        "LockIn_Output_Current": current,
        "LockIn_Time_Constant": tau_value,
        "Helmholtz_Current": avg_helmholtz_current,
        "Helmholtz_Field": avg_helmholtz_field,
        "Temp": avg_temp,
        "In-plane_Field": avg_ppms_field,
    }

    # Channel-specific lock-in data
    _assign_channel_data(
        data_point, active_channel,
        x=x, y=y, r=r, theta=theta,
        x_std=x_std, y_std=y_std, r_std=r_std, theta_std=theta_std,
        sample_resistance=sample_resistance,
        sample_resistance_std=sample_resistance_std,
    )

    ctx.ui_bus.post(W_LED_LOCKIN, False)
    return data_point


# ============================================================================
# Lock-in continuous measurement (no autorange/autophase)
# ============================================================================
def measure_lockin_continuous(
    ctx: MeasurementContext,
    *,
    what: tuple[str, ...] = ("X", "Y", "R", "Theta"),
    avg: int = 10,
    sample_delay: float = 0.05,
    current: float | None = None,
    series_resistance: float | None = None,
    frequency: float | None = None,
    tau_idx: int = 0,
) -> dict[str, Any]:
    """
    Continuous lock-in measurement - no settling, no auto-adjust.

    Excitation is kept ON throughout and after measurement (never turned off).
    """
    ctx.ui_bus.post(W_LED_LOCKIN, True)

    if current is None:
        current = 0.0
    if series_resistance is None:
        series_resistance = 0.0

    output_voltage = current * series_resistance

    ctx.ui_bus.post(W_LOCKIN_OUTPUT_VOLTAGE, output_voltage)

    # Always preserve excitation state (never turn off the output)
    manage_excitation = False

    # Capture start conditions
    start_temp = ctx.get_temp()
    start_field = ctx.get_ppms_field()
    start_helmholtz = ctx.helmholtz.snapshot()

    # Measure without autorange/autophase and without forcing sensitivity
    result = ctx.bus.execute(
        INST_LOCKIN,
        "measure",
        what=what,
        current=current,
        series_resistance=series_resistance,
        avg=avg,
        start_sens=None,
        use_autorange=False,
        use_autophase=False,
        sample_delay=sample_delay,
        manage_excitation=manage_excitation,
        wait_for_settling_when_no_autorange=False,
    )

    # Capture end conditions
    end_temp = ctx.get_temp()
    end_field = ctx.get_ppms_field()
    end_helmholtz = ctx.helmholtz.snapshot()

    avg_temp = _avg_or_nan(start_temp, end_temp)
    avg_ppms_field = _avg_or_nan(start_field, end_field)
    avg_helmholtz_current = _avg_or_nan(
        start_helmholtz.get("Helmholtz_Current"),
        end_helmholtz.get("Helmholtz_Current"),
    )
    avg_helmholtz_field = _avg_or_nan(
        start_helmholtz.get("Helmholtz_Field"),
        end_helmholtz.get("Helmholtz_Field"),
    )

    # Extract values
    x = result.get("X", {}).get("mean", NAN)
    y = result.get("Y", {}).get("mean", NAN)
    r = result.get("R", {}).get("mean", NAN)
    theta = result.get("Theta", {}).get("mean", NAN)
    x_std = result.get("X", {}).get("std", NAN)
    y_std = result.get("Y", {}).get("std", NAN)
    r_std = result.get("R", {}).get("std", NAN)
    theta_std = result.get("Theta", {}).get("std", NAN)
    sens_idx = result.get("sens_idx", 10)

    output_current = current
    sample_resistance = _safe_div(r, current)
    sample_resistance_std = _safe_div(r_std, current)

    # Resolve sensitivity/tau values
    try:
        lockin_raw = ctx.bus.get_raw(INST_LOCKIN)
        sensitivity_v = lockin_raw.SENS_TABLE[sens_idx] if lockin_raw else NAN
        tau_value = lockin_raw.TAU_TABLE[tau_idx] if lockin_raw else NAN
    except (IndexError, AttributeError):
        sensitivity_v = NAN
        tau_value = NAN

    if frequency is None:
        try:
            frequency = ctx.bus.execute(INST_LOCKIN, "get_frequency")
        except Exception:
            frequency = NAN

    active_channel = ctx.get_active_channel() or "N/A"

    data_point: dict[str, Any] = {
        "Time": ctx.data_mgr.elapsed_time(),
        "LockIn_Average_Count": int(avg),
        "LockIn_Frequency": frequency,
        "LockIn_Sensitivity": sensitivity_v,
        "LockIn_R_lockin": series_resistance,
        "LockIn_Output_Voltage": output_voltage,
        "LockIn_Output_Current": output_current,
        "LockIn_Time_Constant": tau_value,
        "Helmholtz_Current": avg_helmholtz_current,
        "Helmholtz_Field": avg_helmholtz_field,
        "Temp": avg_temp,
        "In-plane_Field": avg_ppms_field,
    }

    _assign_channel_data(
        data_point, active_channel,
        x=x, y=y, r=r, theta=theta,
        x_std=x_std, y_std=y_std, r_std=r_std, theta_std=theta_std,
        sample_resistance=sample_resistance,
        sample_resistance_std=sample_resistance_std,
    )

    ctx.ui_bus.post(W_LED_LOCKIN, False)
    return data_point


def _build_linear_segment(start: float, stop: float, step_abs: float) -> list[float]:
    """Build an inclusive linear segment from start to stop."""
    start_f = float(start)
    stop_f = float(stop)
    if abs(stop_f - start_f) < 1e-15:
        return [start_f]

    signed_step = abs(step_abs) if stop_f >= start_f else -abs(step_abs)
    points = [start_f]
    current = start_f
    tol = abs(signed_step) * 1e-12
    while True:
        nxt = current + signed_step
        if signed_step > 0:
            if nxt >= stop_f - tol:
                points.append(stop_f)
                break
        else:
            if nxt <= stop_f + tol:
                points.append(stop_f)
                break
        points.append(float(nxt))
        current = nxt
    return points


def _build_iv_setpoints(
    start: float,
    stop: float,
    step: float,
    shape: str = "start_max_start",
    iv_min: float | None = None,
    iv_max: float | None = None,
) -> list[float]:
    """Build IV setpoints for the requested sweep shape.

    When *iv_min* and *iv_max* are provided they are used directly as the lower
    and upper sweep limits, enabling asymmetric sweeps (e.g. start=0, min=-1 mA,
    max=+1 mA).  When omitted, they are derived from min/max of start and stop.
    """
    start_f = float(start)
    stop_f = float(stop)
    step_f = float(step)
    if abs(step_f) < 1e-15:
        raise ValueError("IV step must be non-zero")

    normalized_shape = str(shape).strip().lower()
    aliases = {
        "loop": "start_min_max_start",
        "bidirectional": "start_min_max_start",
        "start->min->max->start": "start_min_max_start",
        "start->max->min->start": "start_max_min_start",
        "start->min->start": "start_min_start",
        "start->max->start": "start_max_start",
    }
    normalized_shape = aliases.get(normalized_shape, normalized_shape)
    allowed = {
        "single",
        "return",
        "start_min_max_start",
        "start_max_min_start",
        "start_min_start",
        "start_max_start",
    }
    if normalized_shape not in allowed:
        raise ValueError(
            "shape must be one of: start_min_max_start, start_max_min_start, start_min_start, start_max_start"
        )

    # Use explicit min/max when provided (supports asymmetric sweeps).
    actual_min = iv_min if iv_min is not None else min(start_f, stop_f)
    actual_max = iv_max if iv_max is not None else max(start_f, stop_f)

    if normalized_shape == "single":
        targets = [start_f, stop_f]
    elif normalized_shape == "return":
        targets = [start_f, stop_f, start_f]
    elif normalized_shape == "start_min_max_start":
        targets = [start_f, actual_min, actual_max, start_f]
    elif normalized_shape == "start_max_min_start":
        targets = [start_f, actual_max, actual_min, start_f]
    elif normalized_shape == "start_min_start":
        targets = [start_f, actual_min, start_f]
    else:
        targets = [start_f, actual_max, start_f]

    points: list[float] = [targets[0]]
    for target in targets[1:]:
        segment = _build_linear_segment(points[-1], target, abs(step_f))
        if len(segment) > 1:
            points.extend(segment[1:])
    return points


def _build_iv_setpoints_with_directions(
    start: float,
    stop: float,
    step: float,
    shape: str = "start_max_start",
    iv_min: float | None = None,
    iv_max: float | None = None,
) -> tuple[list[float], list[str]]:
    """Same as _build_iv_setpoints but also returns a direction tag for each point.

    Each tag is one of: 'up', 'down', 'flat'.
    """
    setpoints = _build_iv_setpoints(start, stop, step, shape=shape, iv_min=iv_min, iv_max=iv_max)
    directions: list[str] = []
    for i, val in enumerate(setpoints):
        if i == 0:
            # First point: look ahead
            if len(setpoints) > 1:
                d = setpoints[1] - val
                directions.append("up" if d > 0 else ("down" if d < 0 else "flat"))
            else:
                directions.append("flat")
        else:
            d = val - setpoints[i - 1]
            directions.append("up" if d > 0 else ("down" if d < 0 else "flat"))
    return (setpoints, directions)


def estimate_iv_curve_duration(
    *,
    shape: str = "start_max_start",
    start: float,
    stop: float | None = None,
    step: float,
    nplc: float = 1.0,
    settle_time: float = 0.0,
    repetitions: int = 1,
    iv_min: float | None = None,
    iv_max: float | None = None,
    ramp_to_start: bool = True,
    reset_to_zero: bool = True,
) -> float:
    """Estimate total IV run duration in seconds from sweep/ramp settings."""
    normalized_shape = str(shape).strip().lower()

    sweep_stop = stop
    if sweep_stop is None:
        if iv_max is not None:
            sweep_stop = iv_max
        elif iv_min is not None:
            sweep_stop = iv_min
        else:
            sweep_stop = start

    setpoints, _ = _build_iv_setpoints_with_directions(
        start,
        sweep_stop,
        step,
        shape=normalized_shape,
        iv_min=iv_min,
        iv_max=iv_max,
    )

    step_abs = abs(float(step))
    if step_abs < 1e-15:
        raise ValueError("IV step must be non-zero")

    nplc_f = max(0.0, float(nplc))
    reps_i = max(1, int(repetitions))
    mains_hz = 50.0
    point_time_s = max(0.0, float(settle_time) + (nplc_f * reps_i / mains_hz))

    estimate_s = float(len(setpoints)) * point_time_s

    if ramp_to_start and abs(float(start)) > step_abs * 0.5:
        pre_ramp = _build_linear_segment(0.0, float(start), step_abs)
        estimate_s += max(0, len(pre_ramp) - 1) * point_time_s

    final_setpoint = setpoints[-1] if setpoints else float(start)
    if ramp_to_start and setpoints and abs(setpoints[-1] - float(start)) > step_abs * 0.5:
        return_ramp = _build_linear_segment(setpoints[-1], float(start), step_abs)
        estimate_s += max(0, len(return_ramp) - 1) * point_time_s
        final_setpoint = float(start)

    if reset_to_zero and abs(final_setpoint) > step_abs * 0.5:
        zero_ramp = _build_linear_segment(final_setpoint, 0.0, step_abs)
        estimate_s += max(0, len(zero_ramp) - 1) * point_time_s

    return max(0.0, float(estimate_s))


def measure_resistance(
    ctx: MeasurementContext,
    *,
    current: float = 1e-3,
    compliance: float = 10.0,
    nplc: float = 1.0,
    voltage_range: float | None = None,
    auto_range: bool = True,
    settle_time: float = 0.0,
    repetitions: int = 1,
) -> dict[str, Any]:
    """Measure sample resistance by sourcing current and sensing voltage."""
    current_a = float(current)
    if abs(current_a) < 1e-15:
        raise ValueError("current must be non-zero")

    compliance_v = float(compliance)
    nplc_f = float(nplc)
    reps = max(int(repetitions), 1)
    active_channel = ctx.get_active_channel()

    if not bool(auto_range) and voltage_range is not None:
        fixed_v_range = abs(float(voltage_range))
        if fixed_v_range > 0.0 and compliance_v > fixed_v_range:
            logger.info(
                "Resistance: clamping compliance from %.6g V to fixed measure range %.6g V",
                compliance_v,
                fixed_v_range,
            )
            compliance_v = fixed_v_range

    start_temp = ctx.get_temp()
    start_field = ctx.get_ppms_field()
    start_helmholtz = ctx.helmholtz.snapshot()

    try:
        # Some K2450 firmware states reject compliance updates when voltage
        # sense is left in a very low range (for example 20 mV from prior auto
        # range). Prime a safe sense range before changing source limits.
        try:
            ctx.bus.execute(INST_KEITHLEY2450, "write", ":SENS:FUNC 'VOLT'")
            ctx.bus.execute(INST_KEITHLEY2450, "write", ":SENS:VOLT:RANG 21")
            if bool(auto_range):
                ctx.bus.execute(INST_KEITHLEY2450, "write", ":SENS:VOLT:RANG:AUTO ON")
            elif voltage_range is not None:
                ctx.bus.execute(INST_KEITHLEY2450, "write", ":SENS:VOLT:RANG:AUTO OFF")
                ctx.bus.execute(INST_KEITHLEY2450, "write", f":SENS:VOLT:RANG {abs(float(voltage_range)):.12g}")
        except Exception:
            logger.debug("Could not precondition K2450 voltage sense range", exc_info=True)

        source_range = max(abs(current_a) * 1.2, _KEITHLEY_CURRENT_RES_A)
        ctx.bus.execute(
            INST_KEITHLEY2450,
            "apply_current",
            current_range=source_range,
            compliance_voltage=compliance_v,
        )
        ctx.bus.execute(INST_KEITHLEY2450, "enable_source")
        ctx.bus.execute(INST_KEITHLEY2450, "set_source_current_amps", current_a)
        if settle_time > 0:
            time.sleep(float(settle_time))

        measured_voltage, voltage_std = ctx.bus.execute(
            INST_KEITHLEY2450,
            "measure_voltage",
            nplc=nplc_f,
            voltage=21.0 if voltage_range is None else float(voltage_range),
            auto_range=bool(auto_range),
            repetitions=reps,
        )
    finally:
        try:
            ctx.bus.execute(INST_KEITHLEY2450, "set_source_current_amps", 0.0)
        except Exception:
            logger.debug("Could not reset resistance source current", exc_info=True)
        try:
            ctx.bus.execute(INST_KEITHLEY2450, "disable_source")
        except Exception:
            logger.debug("Could not disable resistance source", exc_info=True)

    measured_resistance = _safe_div(float(measured_voltage), current_a)
    resistance_std = abs(_safe_div(float(voltage_std), current_a))

    end_temp = ctx.get_temp()
    end_field = ctx.get_ppms_field()
    end_helmholtz = ctx.helmholtz.snapshot()

    avg_temp = _avg_or_nan(start_temp, end_temp)
    avg_ppms_field = _avg_or_nan(start_field, end_field)
    avg_helmholtz_current = _avg_or_nan(
        start_helmholtz.get("Helmholtz_Current"),
        end_helmholtz.get("Helmholtz_Current"),
    )
    avg_helmholtz_field = _avg_or_nan(
        start_helmholtz.get("Helmholtz_Field"),
        end_helmholtz.get("Helmholtz_Field"),
    )

    return {
        "Time": ctx.data_mgr.elapsed_time(),
        "Channel": active_channel,
        "IV_Source_Current": current_a * 1e3,
        "IV_Measured_Voltage": float(measured_voltage),
        "Sample_Resistance": measured_resistance,
        "Sample_Resistance_Error": resistance_std,
        "Helmholtz_Current": avg_helmholtz_current,
        "Helmholtz_Field": avg_helmholtz_field,
        "Temp": avg_temp,
        "In-plane_Field": avg_ppms_field,
    }


def measure_iv_curve(
    ctx: MeasurementContext,
    *,
    mode: str = "current",
    shape: str = "start_max_start",
    start: float,
    stop: float | None = None,
    step: float,
    source_range: float | None = None,
    measure_range: float | None = None,
    compliance: float | None = None,
    nplc: float = 1.0,
    auto_range: bool = True,
    settle_time: float = 0.0,
    repetitions: int = 1,
    keep_output: bool = False,
    reset_to_zero: bool = True,
    ramp_to_start: bool = True,
    iv_min: float | None = None,
    iv_max: float | None = None,
    env_sample_interval: float = 0.0,
    on_point: Callable[[dict[str, Any]], None] | None = None,
    on_progress: Callable[[int, int], None] | None = None,
    on_should_stop: Callable[[], bool] | None = None,
) -> dict[str, Any]:
    """Measure a full IV curve as a list of per-point data rows."""
    normalized_mode = str(mode).strip().lower()
    if normalized_mode in {"current", "source_current", "i"}:
        source_mode = "source_current"
    elif normalized_mode in {"voltage", "source_voltage", "v"}:
        source_mode = "source_voltage"
    else:
        raise ValueError("mode must be 'current' or 'voltage'")

    normalized_shape = str(shape).strip().lower()

    sweep_stop = stop
    if sweep_stop is None:
        if iv_max is not None:
            sweep_stop = iv_max
        elif iv_min is not None:
            sweep_stop = iv_min
        else:
            sweep_stop = start

    if iv_min is not None and iv_max is not None:
        iv_min_f = float(iv_min)
        iv_max_f = float(iv_max)
        start_f = float(start)
        if iv_min_f >= iv_max_f:
            raise ValueError("IV min must be smaller than IV max")
        if not (iv_min_f < start_f < iv_max_f):
            raise ValueError("IV start must be larger than min and smaller than max")

    setpoints, _sp_directions = _build_iv_setpoints_with_directions(
        start, sweep_stop, step, shape=normalized_shape, iv_min=iv_min, iv_max=iv_max
    )
    if compliance is None:
        compliance = 10.0 if source_mode == "source_current" else 0.1
    compliance_eff = float(compliance)
    if measure_range is not None:
        fixed_measure_range = abs(float(measure_range))
        if fixed_measure_range > 0.0 and compliance_eff > fixed_measure_range:
            logger.info(
                "IV: clamping compliance from %.6g to fixed measure range %.6g",
                compliance_eff,
                fixed_measure_range,
            )
            compliance_eff = fixed_measure_range

    start_helmholtz = ctx.helmholtz.snapshot()
    active_channel = ctx.get_active_channel()

    points: list[dict[str, Any]] = []
    _env_last_time: float = -1.0  # forces a sample on the very first point
    _last_temp: float = ctx.get_temp()
    _last_field: float = ctx.get_ppms_field()
    # Keep ramp cadence aligned with sweep cadence: one ramp step takes about
    # the same time as one measured IV point (NPLC integration + settle time).
    nplc_f = max(0.0, float(nplc))
    reps_i = max(1, int(repetitions))
    mains_hz = 50.0
    ramp_step_pause = max(0.0, float(settle_time) + (nplc_f * reps_i / mains_hz))
    cleanup_ramped_to_start = False
    cleanup_reset_to_zero = False
    cleanup_source_disabled = False
    engine_mode = "point"

    def _maybe_refresh_env() -> tuple[float, float]:
        nonlocal _env_last_time, _last_temp, _last_field
        now = time.perf_counter()
        if env_sample_interval <= 0.0 or (now - _env_last_time) >= env_sample_interval:
            _last_temp = ctx.get_temp()
            _last_field = ctx.get_ppms_field()
            _env_last_time = now
        return _last_temp, _last_field

    def _normalize_fast_payload(
        fast_raw: Any,
        logical_points: int,
        reps: int,
    ) -> tuple[list[float], list[float] | None]:
        measured_raw: list[float]
        sourced_raw: list[float] | None = None

        if isinstance(fast_raw, dict):
            measured_tokens = fast_raw.get("measured")
            sourced_tokens = fast_raw.get("sourced")
            if measured_tokens is None:
                raise RuntimeError("invalid fast IV payload: missing measured values")
            if not isinstance(measured_tokens, (list, tuple)):
                raise RuntimeError("invalid fast IV payload type for measured values")
            measured_raw = [float(v) for v in measured_tokens]
            if sourced_tokens is not None:
                if not isinstance(sourced_tokens, (list, tuple)):
                    raise RuntimeError("invalid fast IV payload type for sourced values")
                sourced_raw = [float(v) for v in sourced_tokens]
        elif isinstance(fast_raw, (int, float)):
            measured_raw = [float(fast_raw)]
        elif isinstance(fast_raw, (list, tuple)):
            measured_raw = [float(v) for v in fast_raw]
        else:
            raise RuntimeError("invalid fast IV payload type")

        def _collapse(values: list[float], label: str) -> list[float]:
            if reps <= 1:
                if len(values) != logical_points:
                    raise RuntimeError(
                        f"invalid fast IV {label} payload length: "
                        f"got {len(values)}, expected {logical_points}"
                    )
                return values

            expanded_points = logical_points * reps
            if len(values) != expanded_points:
                raise RuntimeError(
                    f"invalid fast IV {label} payload length for repetitions={reps}: "
                    f"got {len(values)}, expected {expanded_points}"
                )

            collapsed = []
            for i in range(logical_points):
                seg = values[i * reps:(i + 1) * reps]
                collapsed.append(sum(seg) / float(len(seg)))
            if len(collapsed) != logical_points:
                raise RuntimeError(
                    f"collapsed fast IV {label} payload length mismatch: "
                    f"got {len(collapsed)}, expected {logical_points}"
                )
            return collapsed

        measured = _collapse(measured_raw, "measured")
        sourced = _collapse(sourced_raw, "sourced") if sourced_raw is not None else None
        return (measured, sourced)

    def _check_cancelled() -> None:
        if on_should_stop is None:
            return
        try:
            if bool(on_should_stop()):
                raise IVMeasurementCancelled("IV measurement cancelled by request")
        except IVMeasurementCancelled:
            raise
        except Exception:
            logger.debug("IV stop-check callback failed", exc_info=True)

    def _sleep_interruptible(duration_s: float) -> None:
        remaining = float(duration_s)
        if remaining <= 0.0:
            return
        deadline = time.perf_counter() + remaining
        while True:
            _check_cancelled()
            remaining = deadline - time.perf_counter()
            if remaining <= 0.0:
                return
            time.sleep(min(0.05, remaining))

    try:
        _check_cancelled()
        if source_mode == "source_current":
            ctx.bus.execute(
                INST_KEITHLEY2450,
                "apply_current",
                current_range=source_range,
                compliance_voltage=compliance_eff,
            )
            ctx.bus.execute(INST_KEITHLEY2450, "enable_source")
            _check_cancelled()

            # Pre-sweep ramp: 0 → start (safe ramp before the measured sweep begins)
            if ramp_to_start and abs(float(start)) > abs(float(step)) * 0.5:
                try:
                    pre_ramp = _build_linear_segment(0.0, float(start), abs(float(step)))
                    for sp in pre_ramp[1:]:  # skip 0, which is the source's default-on state
                        _check_cancelled()
                        ctx.bus.execute(INST_KEITHLEY2450, "set_source_current_amps", sp)
                        _sleep_interruptible(ramp_step_pause)
                except Exception as exc:
                    raise RuntimeError("IV pre-ramp to start failed in current mode") from exc

            fast_values = None
            fast_sourced = None
            if setpoints:
                try:
                    _check_cancelled()
                    reps_i = max(int(repetitions), 1)
                    fast_setpoints = [float(sp) for sp in setpoints]
                    if reps_i > 1:
                        expanded = []
                        for sp in fast_setpoints:
                            expanded.extend([sp] * reps_i)
                        fast_setpoints = expanded
                    fast_raw = ctx.bus.execute(
                        INST_KEITHLEY2450,
                        "run_iv_sweep_fast",
                        mode=source_mode,
                        setpoints=fast_setpoints,
                        nplc=nplc,
                        measure_range=measure_range,
                        auto_range=auto_range,
                        settle_time=settle_time,
                        repetitions=1,
                    )
                    fast_values, fast_sourced = _normalize_fast_payload(fast_raw, len(setpoints), reps_i)
                    engine_mode = "fast"
                except Exception:
                    logger.info("Fast IV path unavailable; falling back to point mode", exc_info=True)

            if fast_values is not None:
                try:
                    for index, source_current_a in enumerate(setpoints, start=1):
                        _check_cancelled()
                        measured_voltage_v = float(fast_values[index - 1])
                        sourced_current_a = (
                            float(fast_sourced[index - 1])
                            if fast_sourced is not None
                            else float(source_current_a)
                        )
                        snap = ctx.helmholtz.snapshot()
                        cur_temp, cur_field = _maybe_refresh_env()
                        point = {
                            "Time": ctx.data_mgr.elapsed_time(),
                            "Channel": active_channel,
                            "IV_Point": index,
                            "IV_Sweep_Direction": _sp_directions[index - 1],
                            "IV_Source_Current": sourced_current_a * 1e3,
                            "IV_Source_Voltage": NAN,
                            "IV_Measured_Voltage": measured_voltage_v,
                            "IV_Measured_Current": sourced_current_a * 1e3,
                            "Temp": cur_temp,
                            "In-plane_Field": cur_field,
                            "Helmholtz_Current": snap.get("Helmholtz_Current", start_helmholtz.get("Helmholtz_Current")),
                            "Helmholtz_Field": snap.get("Helmholtz_Field", start_helmholtz.get("Helmholtz_Field")),
                        }
                        points.append(point)
                        if on_point is not None:
                            try:
                                on_point(point)
                            except Exception:
                                logger.debug("IV on_point callback failed", exc_info=True)
                        if on_progress is not None:
                            try:
                                on_progress(index, len(setpoints))
                            except Exception:
                                logger.debug("IV on_progress callback failed", exc_info=True)
                except Exception:
                    logger.info("Fast IV processing failed; falling back to point mode", exc_info=True)
                    fast_values = None
                    points.clear()
            if fast_values is None:
                for index, source_current_a in enumerate(setpoints, start=1):
                    _check_cancelled()
                    ctx.bus.execute(INST_KEITHLEY2450, "set_source_current_amps", source_current_a)
                    _sleep_interruptible(settle_time)
                    measured_voltage_v, measured_voltage_std = ctx.bus.execute(
                        INST_KEITHLEY2450,
                        "measure_voltage",
                        nplc=nplc,
                        voltage=measure_range if measure_range is not None else 21.0,
                        auto_range=auto_range,
                        repetitions=repetitions,
                    )
                    measured_current_a = float(source_current_a)
                    snap = ctx.helmholtz.snapshot()
                    cur_temp, cur_field = _maybe_refresh_env()
                    point = {
                        "Time": ctx.data_mgr.elapsed_time(),
                        "Channel": active_channel,
                        "IV_Point": index,
                        "IV_Sweep_Direction": _sp_directions[index - 1],
                        "IV_Source_Current": source_current_a * 1e3,
                        "IV_Source_Voltage": NAN,
                        "IV_Measured_Voltage": measured_voltage_v,
                        "IV_Measured_Current": measured_current_a * 1e3,
                        "Temp": cur_temp,
                        "In-plane_Field": cur_field,
                        "Helmholtz_Current": snap.get("Helmholtz_Current", start_helmholtz.get("Helmholtz_Current")),
                        "Helmholtz_Field": snap.get("Helmholtz_Field", start_helmholtz.get("Helmholtz_Field")),
                    }
                    points.append(point)
                    if on_point is not None:
                        try:
                            on_point(point)
                        except Exception:
                            logger.debug("IV on_point callback failed", exc_info=True)
                    if on_progress is not None:
                        try:
                            on_progress(index, len(setpoints))
                        except Exception:
                            logger.debug("IV on_progress callback failed", exc_info=True)

        else:
            ctx.bus.execute(
                INST_KEITHLEY2450,
                "apply_voltage",
                voltage_range=source_range,
                compliance_current=compliance_eff,
            )
            ctx.bus.execute(INST_KEITHLEY2450, "enable_source")
            _check_cancelled()

            # Pre-sweep ramp: 0 → start (safe ramp before the measured sweep begins)
            if ramp_to_start and abs(float(start)) > abs(float(step)) * 0.5:
                try:
                    pre_ramp = _build_linear_segment(0.0, float(start), abs(float(step)))
                    for sp in pre_ramp[1:]:
                        _check_cancelled()
                        ctx.bus.execute(INST_KEITHLEY2450, "set_source_voltage_volts", sp)
                        _sleep_interruptible(ramp_step_pause)
                except Exception as exc:
                    raise RuntimeError("IV pre-ramp to start failed in voltage mode") from exc

            fast_values = None
            fast_sourced = None
            if setpoints:
                try:
                    _check_cancelled()
                    reps_i = max(int(repetitions), 1)
                    fast_setpoints = [float(sp) for sp in setpoints]
                    if reps_i > 1:
                        expanded = []
                        for sp in fast_setpoints:
                            expanded.extend([sp] * reps_i)
                        fast_setpoints = expanded
                    fast_raw = ctx.bus.execute(
                        INST_KEITHLEY2450,
                        "run_iv_sweep_fast",
                        mode=source_mode,
                        setpoints=fast_setpoints,
                        nplc=nplc,
                        measure_range=measure_range,
                        auto_range=auto_range,
                        settle_time=settle_time,
                        repetitions=1,
                    )
                    fast_values, fast_sourced = _normalize_fast_payload(fast_raw, len(setpoints), reps_i)
                    engine_mode = "fast"
                except Exception:
                    logger.info("Fast IV path unavailable; falling back to point mode", exc_info=True)

            if fast_values is not None:
                try:
                    for index, source_voltage_v in enumerate(setpoints, start=1):
                        _check_cancelled()
                        commanded_voltage_v = float(source_voltage_v)
                        measured_current_a = float(fast_values[index - 1])
                        sourced_voltage_v = (
                            float(fast_sourced[index - 1])
                            if fast_sourced is not None
                            else commanded_voltage_v
                        )
                        snap = ctx.helmholtz.snapshot()
                        cur_temp, cur_field = _maybe_refresh_env()
                        point = {
                            "Time": ctx.data_mgr.elapsed_time(),
                            "Channel": active_channel,
                            "IV_Point": index,
                            "IV_Sweep_Direction": _sp_directions[index - 1],
                            "IV_Source_Current": NAN,
                            "IV_Source_Voltage": sourced_voltage_v,
                            "IV_Measured_Voltage": commanded_voltage_v,
                            "IV_Measured_Current": measured_current_a * 1e3,
                            "Temp": cur_temp,
                            "In-plane_Field": cur_field,
                            "Helmholtz_Current": snap.get("Helmholtz_Current", start_helmholtz.get("Helmholtz_Current")),
                            "Helmholtz_Field": snap.get("Helmholtz_Field", start_helmholtz.get("Helmholtz_Field")),
                        }
                        points.append(point)
                        if on_point is not None:
                            try:
                                on_point(point)
                            except Exception:
                                logger.debug("IV on_point callback failed", exc_info=True)
                        if on_progress is not None:
                            try:
                                on_progress(index, len(setpoints))
                            except Exception:
                                logger.debug("IV on_progress callback failed", exc_info=True)
                except Exception:
                    logger.info("Fast IV processing failed; falling back to point mode", exc_info=True)
                    fast_values = None
                    points.clear()
            if fast_values is None:
                for index, source_voltage_v in enumerate(setpoints, start=1):
                    _check_cancelled()
                    ctx.bus.execute(INST_KEITHLEY2450, "set_source_voltage_volts", source_voltage_v)
                    _sleep_interruptible(settle_time)
                    measured_current_a, measured_current_std = ctx.bus.execute(
                        INST_KEITHLEY2450,
                        "measure_current",
                        nplc=nplc,
                        current=measure_range if measure_range is not None else 1.05,
                        auto_range=auto_range,
                        repetitions=repetitions,
                    )
                    measured_voltage_v = float(source_voltage_v)
                    snap = ctx.helmholtz.snapshot()
                    cur_temp, cur_field = _maybe_refresh_env()
                    point = {
                        "Time": ctx.data_mgr.elapsed_time(),
                        "Channel": active_channel,
                        "IV_Point": index,
                        "IV_Sweep_Direction": _sp_directions[index - 1],
                        "IV_Source_Current": NAN,
                        "IV_Source_Voltage": source_voltage_v,
                        "IV_Measured_Voltage": measured_voltage_v,
                        "IV_Measured_Current": measured_current_a * 1e3,
                        "Temp": cur_temp,
                        "In-plane_Field": cur_field,
                        "Helmholtz_Current": snap.get("Helmholtz_Current", start_helmholtz.get("Helmholtz_Current")),
                        "Helmholtz_Field": snap.get("Helmholtz_Field", start_helmholtz.get("Helmholtz_Field")),
                    }
                    points.append(point)
                    if on_point is not None:
                        try:
                            on_point(point)
                        except Exception:
                            logger.debug("IV on_point callback failed", exc_info=True)
                    if on_progress is not None:
                        try:
                            on_progress(index, len(setpoints))
                        except Exception:
                            logger.debug("IV on_progress callback failed", exc_info=True)

    finally:
        # ramp_to_start: optional intermediate ramp from sweep end back to start.
        # reset_to_zero: final source level after sweep completion.
        final_setpoint = setpoints[-1] if setpoints else float(start)
        if ramp_to_start and setpoints:
            last_sp = setpoints[-1]
            if abs(last_sp - start) > abs(float(step)) * 0.5:
                try:
                    ramp_pts = _build_linear_segment(last_sp, start, abs(float(step)))
                    for sp in ramp_pts[1:]:
                        if source_mode == "source_current":
                            ctx.bus.execute(INST_KEITHLEY2450, "set_source_current_amps", sp)
                        else:
                            ctx.bus.execute(INST_KEITHLEY2450, "set_source_voltage_volts", sp)
                        time.sleep(ramp_step_pause)
                    final_setpoint = float(start)
                    cleanup_ramped_to_start = True
                except Exception:
                    logger.debug("Could not ramp IV source to start", exc_info=True)
        if reset_to_zero:
            try:
                if abs(final_setpoint) > abs(float(step)) * 0.5:
                    zero_ramp_pts = _build_linear_segment(final_setpoint, 0.0, abs(float(step)))
                    for sp in zero_ramp_pts[1:]:
                        if source_mode == "source_current":
                            ctx.bus.execute(INST_KEITHLEY2450, "set_source_current_amps", sp)
                        else:
                            ctx.bus.execute(INST_KEITHLEY2450, "set_source_voltage_volts", sp)
                        time.sleep(ramp_step_pause)
                else:
                    if source_mode == "source_current":
                        ctx.bus.execute(INST_KEITHLEY2450, "set_source_current_amps", 0.0)
                    else:
                        ctx.bus.execute(INST_KEITHLEY2450, "set_source_voltage_volts", 0.0)
                cleanup_reset_to_zero = True
            except Exception:
                logger.debug("Could not reset IV source to zero", exc_info=True)
        if not keep_output:
            try:
                ctx.bus.execute(INST_KEITHLEY2450, "disable_source")
                cleanup_source_disabled = True
            except Exception:
                logger.debug("Could not disable IV source", exc_info=True)

    return {
        "mode": source_mode,
        "shape": normalized_shape,
        "point_count": len(points),
        "engine": engine_mode,
        "points": points,
        "cleanup": {
            "ramped_to_start": cleanup_ramped_to_start,
            "reset_to_zero": cleanup_reset_to_zero,
            "source_disabled": cleanup_source_disabled,
            "keep_output": bool(keep_output),
            "requested_reset_to_zero": bool(reset_to_zero),
            "requested_ramp_to_start": bool(ramp_to_start),
        },
    }


# ============================================================================
# Hall bar (K2450) measurement
# ============================================================================
def measure_hall(
    ctx: MeasurementContext,
    *,
    current_mA: float = 0.0,
    nplc: float = 1.0,
    compliance_v: float = 10.0,
    voltage_range: float | None = None,
    auto_range: bool = True,
    filter_count: int = 10,
    tbm: float = 0.0,
) -> dict[str, Any]:
    """
    Measure Hall voltage using Keithley 2450.

    Returns data-point dict with Hall voltage, field, and errors.
    """
    # Capture start conditions
    start_temp = ctx.get_temp()
    start_field = ctx.get_ppms_field()
    start_helmholtz = ctx.helmholtz.snapshot()

    # Configure and source
    current_mA = _round_to(float(current_mA), _KEITHLEY_CURRENT_RES_A)
    enable_hall_output(
        ctx,
        current_mA=current_mA,
        compliance_v=compliance_v,
    )

    try:
        if tbm > 0:
            time.sleep(tbm)

        # Measure
        v_range = voltage_range if not auto_range else 21.0
        voltage, voltage_std = ctx.bus.execute(
            INST_KEITHLEY2450,
            "measure_voltage",
            nplc=nplc,
            voltage=v_range,
            auto_range=auto_range,
            repetitions=filter_count,
        )
    finally:
        try:
            disable_hall_output(ctx)
        finally:
            pass

    if _is_mock_hall_driver(ctx) and bool(getattr(ctx.calibration, "hall_mock_enabled", True)):
        helmholtz_field_g = _finite_or_zero(start_helmholtz.get("Helmholtz_Field"))
        ppms_field_oe = _finite_or_zero(start_field)
        voltage, voltage_std, hall_field, hall_field_std = _simulate_mock_hall_voltage(
            ctx,
            helmholtz_field_g=helmholtz_field_g,
            ppms_field_oe=ppms_field_oe,
            repetitions=filter_count,
        )
    else:
        # Convert to field
        hall_field = ctx.calibration.hall_voltage_to_field(voltage)
        hall_field_std = ctx.calibration.hall_field_error(voltage_std)

    # Capture end conditions
    end_temp = ctx.get_temp()
    end_field = ctx.get_ppms_field()
    end_helmholtz = ctx.helmholtz.snapshot()

    avg_temp = _avg_or_nan(start_temp, end_temp)
    avg_ppms_field = _avg_or_nan(start_field, end_field)
    avg_helmholtz_current = _avg_or_nan(
        start_helmholtz.get("Helmholtz_Current"),
        end_helmholtz.get("Helmholtz_Current"),
    )
    avg_helmholtz_field = _avg_or_nan(
        start_helmholtz.get("Helmholtz_Field"),
        end_helmholtz.get("Helmholtz_Field"),
    )

    data_point: dict[str, Any] = {
        "Time": ctx.data_mgr.elapsed_time(),
        "Hall Voltage": voltage,
        "Hall Voltage Error": voltage_std,
        "Hall Field": hall_field,
        "Hall Field Error": hall_field_std,
        "Helmholtz_Current": avg_helmholtz_current,
        "Helmholtz_Field": avg_helmholtz_field,
        "Temp": avg_temp,
        "In-plane_Field": avg_ppms_field,
    }

    return data_point


def _is_hall_output_enabled(ctx: MeasurementContext) -> bool:
    """Best-effort source-state check across real and mock K2450 drivers."""
    try:
        inst = ctx.bus.get_raw(INST_KEITHLEY2450)
        if inst is None:
            return False
        if hasattr(inst, "source_enabled"):
            return bool(getattr(inst, "source_enabled"))
        if hasattr(inst, "_source_enabled"):
            return bool(getattr(inst, "_source_enabled"))
        return False
    except Exception:
        return False


def enable_hall_output(
    ctx: MeasurementContext,
    *,
    current_mA: float,
    compliance_v: float,
) -> None:
    """Enable K2450 source output with current/compliance configuration."""
    current_mA = _round_to(float(current_mA), _KEITHLEY_CURRENT_RES_A)
    ctx.bus.execute(INST_KEITHLEY2450, "__setattr__", "source_current", current_mA)
    ctx.bus.execute(INST_KEITHLEY2450, "apply_current", compliance_voltage=compliance_v)
    ctx.bus.execute(INST_KEITHLEY2450, "voltage_filter_count", 1)
    ctx.bus.execute(INST_KEITHLEY2450, "enable_source")
    ctx.ui_bus.post(W_HALL_SOURCE_ENABLED, True)
    ctx.ui_bus.post(W_LED_HALL, True)


def disable_hall_output(ctx: MeasurementContext) -> None:
    """Disable K2450 source output."""
    ctx.bus.execute(INST_KEITHLEY2450, "disable_source")
    ctx.ui_bus.post(W_HALL_SOURCE_ENABLED, False)
    ctx.ui_bus.post(W_LED_HALL, False)


def measure_hall_continuous(
    ctx: MeasurementContext,
    *,
    current_mA: float = 0.0,
    nplc: float = 1.0,
    compliance_v: float = 10.0,
    voltage_range: float | None = None,
    auto_range: bool = True,
    filter_count: int = 10,
    tbm: float = 0.0,
) -> dict[str, Any]:
    """
    Continuous Hall measurement.

    Behavior:
    - If Hall source is OFF (or unknown), enable it and optionally wait TBM.
    - If Hall source is already ON, skip enable and skip TBM.
    - Never disables source at the end.
    """
    # Capture start conditions
    start_temp = ctx.get_temp()
    start_field = ctx.get_ppms_field()
    start_helmholtz = ctx.helmholtz.snapshot()

    was_enabled = _is_hall_output_enabled(ctx)
    if not was_enabled:
        enable_hall_output(
            ctx,
            current_mA=current_mA,
            compliance_v=compliance_v,
        )
        if tbm > 0:
            time.sleep(tbm)

    v_range = voltage_range if not auto_range else 21.0
    voltage, voltage_std = ctx.bus.execute(
        INST_KEITHLEY2450,
        "measure_voltage",
        nplc=nplc,
        voltage=v_range,
        auto_range=auto_range,
        repetitions=filter_count,
    )

    if _is_mock_hall_driver(ctx) and bool(getattr(ctx.calibration, "hall_mock_enabled", True)):
        helmholtz_field_g = _finite_or_zero(start_helmholtz.get("Helmholtz_Field"))
        ppms_field_oe = _finite_or_zero(start_field)
        voltage, voltage_std, hall_field, hall_field_std = _simulate_mock_hall_voltage(
            ctx,
            helmholtz_field_g=helmholtz_field_g,
            ppms_field_oe=ppms_field_oe,
            repetitions=filter_count,
        )
    else:
        hall_field = ctx.calibration.hall_voltage_to_field(voltage)
        hall_field_std = ctx.calibration.hall_field_error(voltage_std)

    # Capture end conditions
    end_temp = ctx.get_temp()
    end_field = ctx.get_ppms_field()
    end_helmholtz = ctx.helmholtz.snapshot()

    avg_temp = _avg_or_nan(start_temp, end_temp)
    avg_ppms_field = _avg_or_nan(start_field, end_field)
    avg_helmholtz_current = _avg_or_nan(
        start_helmholtz.get("Helmholtz_Current"),
        end_helmholtz.get("Helmholtz_Current"),
    )
    avg_helmholtz_field = _avg_or_nan(
        start_helmholtz.get("Helmholtz_Field"),
        end_helmholtz.get("Helmholtz_Field"),
    )

    data_point: dict[str, Any] = {
        "Time": ctx.data_mgr.elapsed_time(),
        "Hall Voltage": voltage,
        "Hall Voltage Error": voltage_std,
        "Hall Field": hall_field,
        "Hall Field Error": hall_field_std,
        "Helmholtz_Current": avg_helmholtz_current,
        "Helmholtz_Field": avg_helmholtz_field,
        "Temp": avg_temp,
        "In-plane_Field": avg_ppms_field,
    }

    return data_point


# ============================================================================
# Full measure (Lock-in + Hall combined)
# ============================================================================
def full_measure(
    ctx: MeasurementContext,
    *,
    # Hall parameters
    hall_current_mA: float = 0.0,
    hall_nplc: float = 1.0,
    hall_compliance_v: float = 10.0,
    hall_voltage_range: float | None = None,
    hall_auto_range: bool = True,
    hall_filter_count: int = 10,
    hall_tbm: float = 0.0,
    # Lock-in parameters
    lockin_what: tuple[str, ...] = ("X", "Y", "R", "Theta"),
    lockin_current: float | None = None,
    lockin_series_resistance: float | None = None,
    lockin_avg: int = 10,
    lockin_start_sens: int = 10,
    lockin_use_autorange: bool = True,
    lockin_use_autophase: bool = True,
    lockin_sample_delay: float = 0.05,
    lockin_tau_idx: int = 0,
    lockin_filter_slope_idx: int = 0,
    lockin_frequency: float | None = None,
    # Timing
    time_between: float = 0.05,
) -> dict[str, Any]:
    """
    Combined Hall bar + Lock-in measurement in a single data row.

    Performs Hall measurement first, then Lock-in, and merges results.
    """
    # Hall measurement (skip_write = True equivalent - we merge manually)
    hall_data = measure_hall(
        ctx,
        current_mA=hall_current_mA,
        nplc=hall_nplc,
        compliance_v=hall_compliance_v,
        voltage_range=hall_voltage_range,
        auto_range=hall_auto_range,
        filter_count=hall_filter_count,
        tbm=hall_tbm,
    )

    if time_between > 0:
        time.sleep(time_between)

    # Lock-in measurement
    lockin_data = measure_lockin(
        ctx,
        what=lockin_what,
        current=lockin_current,
        series_resistance=lockin_series_resistance,
        avg=lockin_avg,
        start_sens=lockin_start_sens,
        use_autorange=lockin_use_autorange,
        use_autophase=lockin_use_autophase,
        sample_delay=lockin_sample_delay,
        tau_idx=lockin_tau_idx,
        filter_slope_idx=lockin_filter_slope_idx,
        frequency=lockin_frequency,
    )

    # Merge: Lock-in data as base, Hall data overlays
    merged = {**lockin_data, **hall_data}
    # Use lock-in's channel-specific data (already assigned by measure_lockin)
    for key in lockin_data:
        if key.startswith("LockIn_") or key.startswith("Sample_"):
            merged[key] = lockin_data[key]

    return merged


# ============================================================================
# PPMS wait functions (interruptible)
# ============================================================================
def wait_for_temp_stable(
    ctx: MeasurementContext,
    stop_event,
    max_wait_s: float = 18_000,
    poll_interval: float = 2.0,
    required_stable: int = 2,
) -> bool:
    """
    Wait for PPMS temperature to stabilize.

    Returns True if stable, False on timeout/stop.  Unlike V2, this
    checks the stop event for responsiveness.
    """
    stable_count = 0
    deadline = time.monotonic() + max_wait_s

    while time.monotonic() < deadline:
        if stop_event.is_set():
            return False

        try:
            err, temp, status_num, status_name = ctx.bus.execute(
                INST_DYNA, "get_temperature"
            )
            status = int(status_num)
            if status == 1:  # Stable
                stable_count += 1
                if stable_count >= required_stable:
                    ctx.ui_bus.post_log(f"Temperature stable at {temp} K")
                    return True
            else:
                stable_count = 0

            # Handle NaN
            if str(temp).lower() == "nan":
                ctx.ui_bus.post_log("Warning: Temperature reading is NaN - treating as stable")
                return True

        except Exception as e:
            ctx.ui_bus.post_log(f"Warning: Temperature check failed: {e}")
            return True

        if stop_event.wait(timeout=poll_interval):
            return False

    ctx.ui_bus.post_log(f"Temperature stability timeout after {max_wait_s}s")
    return False


def wait_for_field_stable(
    ctx: MeasurementContext,
    stop_event,
    max_wait_s: float = 18_000,
    poll_interval: float = 2.0,
    required_stable: int = 2,
) -> bool:
    """
    Wait for PPMS field to stabilize.

    Returns True if stable, False on timeout/stop.
    """
    stable_count = 0
    deadline = time.monotonic() + max_wait_s

    while time.monotonic() < deadline:
        if stop_event.is_set():
            return False

        try:
            err, field_val, status_num = ctx.bus.execute(
                INST_DYNA, "get_field"
            )
            status = int(status_num)
            if status in (1, 4):  # Stable or Holding
                stable_count += 1
                if stable_count >= required_stable:
                    ctx.ui_bus.post_log(f"Field stable at {field_val} Oe")
                    return True
            else:
                stable_count = 0

            if str(field_val).lower() == "nan":
                ctx.ui_bus.post_log("Warning: Field reading is NaN - treating as stable")
                return True

        except Exception as e:
            ctx.ui_bus.post_log(f"Warning: Field check failed: {e}")
            return True

        if stop_event.wait(timeout=poll_interval):
            return False

    ctx.ui_bus.post_log(f"Field stability timeout after {max_wait_s}s")
    return False


def wait_for_events(
    ctx: MeasurementContext,
    stop_event,
    events: list[str],
    additional_time: float = 0.0,
) -> None:
    """
    Wait for named events in sequence, then countdown.

    Supported events: ``temp``, ``field``, ``helmholtz``, ``no_event``,
    ``all`` (expands to temp + field + helmholtz).
    """
    # Expand "all"
    expanded = []
    for ev in events:
        if ev.lower() == "all":
            expanded.extend(["temp", "field", "helmholtz"])
        else:
            expanded.append(ev.lower())

    # Handle no_event (just countdown)
    if expanded == ["no_event"]:
        _countdown(ctx, stop_event, additional_time, respect_stop=True)
        return

    for ev in expanded:
        if stop_event.is_set():
            return

        if ev == "temp":
            wait_for_temp_stable(ctx, stop_event)
        elif ev == "field":
            wait_for_field_stable(ctx, stop_event)
        elif ev == "helmholtz":
            ctx.helmholtz.wait_until_stable(stop_event)

    if additional_time > 0:
        ctx.ui_bus.post_log(f"Waiting additional {additional_time:.0f}s...")
        _countdown(ctx, stop_event, additional_time)


def _countdown(
    ctx: MeasurementContext,
    stop_event,
    duration: float,
    respect_stop: bool = True,
) -> None:
    """Countdown wait with 1-second ticks and stop-event checking."""
    remaining = int(duration)
    while remaining > 0:
        if respect_stop and stop_event.is_set():
            return
        ctx.ui_bus.post_log(f"Countdown: {remaining}s remaining...")
        if stop_event.wait(timeout=1.0):
            if respect_stop:
                return
        remaining -= 1
    # Fractional tail
    frac = duration - int(duration)
    if frac > 0:
        stop_event.wait(timeout=frac)


# ============================================================================
# Lock-in utility commands
# ============================================================================
def lockin_auto_gain(ctx: MeasurementContext) -> int:
    """Run lock-in auto-gain and return the new sensitivity index."""
    lockin = ctx.bus.get_raw(INST_LOCKIN)
    if lockin is None:
        raise RuntimeError("Lock-in instrument is not connected")

    if hasattr(lockin, "quick_autorange"):
        ctx.bus.execute(INST_LOCKIN, "quick_autorange")
    elif hasattr(lockin, "safe_auto_gain"):
        ctx.bus.execute(INST_LOCKIN, "safe_auto_gain")
    elif hasattr(lockin, "auto_gain"):
        ctx.bus.execute(INST_LOCKIN, "auto_gain")
    else:
        raise AttributeError("Lock-in driver has no auto_gain/safe_auto_gain/quick_autorange method")

    sens_idx = ctx.bus.execute(INST_LOCKIN, "get_sensitivity")
    return sens_idx


def lockin_auto_phase(ctx: MeasurementContext) -> None:
    """Run lock-in auto-phase."""
    lockin = ctx.bus.get_raw(INST_LOCKIN)
    if lockin is None:
        raise RuntimeError("Lock-in instrument is not connected")
    if hasattr(lockin, "safe_auto_phase"):
        ctx.bus.execute(INST_LOCKIN, "safe_auto_phase")
    elif hasattr(lockin, "auto_phase"):
        ctx.bus.execute(INST_LOCKIN, "auto_phase")
    else:
        raise AttributeError("Lock-in driver has no auto_phase/safe_auto_phase method")


def lockin_auto_reserve(ctx: MeasurementContext) -> None:
    """Run lock-in auto-reserve."""
    lockin = ctx.bus.get_raw(INST_LOCKIN)
    if lockin is None:
        raise RuntimeError("Lock-in instrument is not connected")
    if hasattr(lockin, "safe_auto_reserve"):
        ctx.bus.execute(INST_LOCKIN, "safe_auto_reserve")
    elif hasattr(lockin, "auto_reserve"):
        ctx.bus.execute(INST_LOCKIN, "auto_reserve")
    else:
        raise AttributeError("Lock-in driver has no auto_reserve/safe_auto_reserve method")


def set_lockin_time_constant(ctx: MeasurementContext, tau_idx: int) -> None:
    """Set lock-in time constant by index."""
    ctx.bus.execute(INST_LOCKIN, "set_time_constant", tau_idx)


def set_lockin_filter(ctx: MeasurementContext, filter_idx: int) -> None:
    """Set lock-in filter slope by index."""
    ctx.bus.execute(INST_LOCKIN, "set_filter_slope", filter_idx)


def set_lockin_frequency(ctx: MeasurementContext, freq: float) -> None:
    """Set lock-in frequency."""
    ctx.bus.execute(INST_LOCKIN, "set_frequency", freq)


def set_lockin_sensitivity(ctx: MeasurementContext, sens_idx: int) -> None:
    """Set lock-in sensitivity by SR830 sensitivity index."""
    ctx.bus.execute(INST_LOCKIN, "set_sensitivity", int(sens_idx))


def set_lockin_current(
    ctx: MeasurementContext,
    current: float,
    series_resistance: float,
) -> float:
    """Set lock-in excitation current via output voltage = I x R."""
    lockin = ctx.bus.get_raw(INST_LOCKIN)
    if lockin is None:
        raise RuntimeError("Lock-in instrument is not connected")

    if series_resistance <= 0:
        raise ValueError("Series resistance must be positive")

    minimum_voltage = 0.004  # 4 mV hardware-safe minimum
    output_voltage = max(minimum_voltage, current * series_resistance)
    output_voltage = _round_to(output_voltage, _LOCKIN_VOLTAGE_RES_V)
    effective_current = output_voltage / series_resistance

    if hasattr(lockin, "set_excitation_current"):
        ctx.bus.execute(INST_LOCKIN, "set_excitation_current", effective_current, series_resistance)
        return output_voltage

    if hasattr(lockin, "set_reference_amplitude"):
        ctx.bus.execute(INST_LOCKIN, "set_reference_amplitude", output_voltage)
    elif hasattr(lockin, "set_sine_output"):
        ctx.bus.execute(INST_LOCKIN, "set_sine_output", output_voltage)
    elif hasattr(lockin, "sine_output_on"):
        ctx.bus.execute(INST_LOCKIN, "sine_output_on", output_voltage)
    else:
        raise AttributeError("Lock-in driver has no known output-amplitude setter")

    return output_voltage


# ============================================================================
# Switch matrix commands
# ============================================================================
def open_all_channels(ctx: MeasurementContext) -> None:
    """Open all switch matrix channels."""
    inst = ctx.bus.get_raw(INST_SWITCH)
    if inst is None:
        raise RuntimeError("Switch instrument is not connected")

    if hasattr(inst, "open_all_channels"):
        ctx.bus.execute(INST_SWITCH, "open_all_channels")
    elif hasattr(inst, "open_all"):
        ctx.bus.execute(INST_SWITCH, "open_all")
    else:
        raise AttributeError("Switch driver has no open_all/open_all_channels method")
    ctx.ui_bus.post(W_LED_SWITCH, True)
    ctx.ui_bus.post(W_SWITCH_STATUS, "Switch: all channels open")


def close_channel(ctx: MeasurementContext, channel_num: int) -> None:
    """Close a specific switch channel."""
    inst = ctx.bus.get_raw(INST_SWITCH)
    if inst is None:
        raise RuntimeError("Switch instrument is not connected")

    if hasattr(inst, "close_channel"):
        ctx.bus.execute(INST_SWITCH, "close_channel", channel_num)
    elif hasattr(inst, "close_list"):
        # Fallback for legacy MySwitch API
        ctx.bus.execute(INST_SWITCH, "close_list", int(channel_num), 0, 0, 0)
    else:
        raise AttributeError("Switch driver has no close_channel/close_list method")
    ctx.ui_bus.post(W_LED_SWITCH, True)
    ctx.ui_bus.post(W_SWITCH_STATUS, f"Switch: channel {channel_num} closed")


def configure_channel(
    ctx: MeasurementContext,
    channel: str,
    ip: int,
    vp: int,
    vm: int,
    im: int,
) -> dict[str, int]:
    """
    Reconfigure a channel's routing.

    Returns the routing dict for the caller to update state.
    """
    routing = {"I+": ip, "V+": vp, "V-": vm, "I-": im}

    # Validate
    nums = [ip, vp, vm, im]
    for n in nums:
        if n < 1 or n > SWITCH_PIN_MAX:
            raise ValueError(f"Routing number {n} out of range (1-{SWITCH_PIN_MAX})")
    if len(nums) != len(set(nums)):
        raise ValueError(f"Duplicate routing numbers: {nums}")

    # Open all, then apply this routing on the instrument when possible
    open_all_channels(ctx)

    inst = ctx.bus.get_raw(INST_SWITCH)
    if inst is not None:
        if hasattr(inst, "close_list"):
            ctx.bus.execute(INST_SWITCH, "close_list", int(ip), int(vp), int(vm), int(im))
        elif hasattr(inst, "close_channel"):
            for pin in (ip, vp, vm, im):
                ctx.bus.execute(INST_SWITCH, "close_channel", int(pin))

    note = f"Reconfigured channel {channel}: I+={ip}, V+={vp}, V-={vm}, I-={im}"
    ctx.ui_bus.post(W_LED_SWITCH, True)
    ctx.ui_bus.post(W_SWITCH_STATUS, f"Switch: channel {channel} configured")
    ctx.ui_bus.post_log(note)
    return routing


# ============================================================================
# PPMS field/temp setters
# ============================================================================
def set_dyna_field(
    ctx: MeasurementContext,
    field_oe: float,
    rate: float,
    approach: Any,
) -> None:
    """Set PPMS field and do a brief settling delay."""
    field_oe = _round_to(float(field_oe), _DYNA_FIELD_RES_OE)
    rate = _round_to(float(rate), _DYNA_FIELD_RES_OE)
    safe_rate = max(-50.0, min(50.0, float(rate)))
    if safe_rate != float(rate):
        ctx.ui_bus.post_log(
            f"PPMS field rate capped to {safe_rate:.1f} Oe/s (requested {float(rate):.1f} Oe/s)"
        )

    resolved_approach = _resolve_dyna_approach(
        ctx,
        mode_attr="Field_mode",
        approach=approach,
        aliases={
            "linear": "linear",
            "no_overshoot": "no_overshoot",
            "oscillate": "oscillate",
        },
    )
    ctx.bus.execute(INST_DYNA, "set_field", field_oe, safe_rate, resolved_approach)
    time.sleep(2.0)


def set_dyna_temp(
    ctx: MeasurementContext,
    temp_k: float,
    rate: float,
    approach: Any,
) -> None:
    """Set PPMS temperature and do a brief settling delay."""
    temp_k = _round_to(float(temp_k), _DYNA_TEMP_RES_K)
    rate = _round_to(float(rate), _DYNA_TEMP_RES_K)
    resolved_approach = _resolve_dyna_approach(
        ctx,
        mode_attr="Temp_mode",
        approach=approach,
        aliases={
            "fast_settle": "fast_settle",
            "fast": "fast_settle",
            "no_overshoot": "no_overshoot",
        },
    )
    ctx.bus.execute(INST_DYNA, "set_temperature", temp_k, rate, resolved_approach)
    time.sleep(5.0)


def _resolve_dyna_approach(
    ctx: MeasurementContext,
    *,
    mode_attr: str,
    approach: Any,
    aliases: dict[str, str],
) -> Any:
    """Resolve approach token to Dyna enum value when available."""
    if not isinstance(approach, str):
        return approach

    token = approach.strip().lower()
    mapped = aliases.get(token, token)

    dyna = ctx.bus.get_raw(INST_DYNA)
    enum_cls = getattr(dyna, mode_attr, None) if dyna is not None else None
    if enum_cls is None:
        # Fallback to int for raw numeric tokens, else keep string.
        try:
            return int(mapped)
        except Exception:
            return mapped

    try:
        return enum_cls[mapped]
    except Exception:
        try:
            return enum_cls(int(mapped))
        except Exception:
            return mapped


# ============================================================================
# Internal helpers
# ============================================================================
def _assign_channel_data(
    data_point: dict[str, Any],
    active_channel: str | None,
    *,
    x: float,
    y: float,
    r: float,
    theta: float,
    x_std: float,
    y_std: float,
    r_std: float,
    theta_std: float,
    sample_resistance: float,
    sample_resistance_std: float,
) -> None:
    """
    Assign lock-in values to channel-specific keys in the data point.

    Writes generic channel-aware lock-in keys and keeps legacy a/b aliases.
    """
    # Generic channel-aware keys
    data_point["Channel"] = str(active_channel).strip().lower() if active_channel else ""
    data_point["LockIn_X"] = NAN
    data_point["LockIn_X_Error"] = NAN
    data_point["LockIn_Y"] = NAN
    data_point["LockIn_Y_Error"] = NAN
    data_point["LockIn_R"] = NAN
    data_point["LockIn_R_Error"] = NAN
    data_point["LockIn_Theta"] = NAN
    data_point["LockIn_Theta_Error"] = NAN
    data_point["Sample_Resistance"] = NAN
    data_point["Sample_Resistance_Error"] = NAN

    # Legacy aliases for existing a/b schema consumers
    data_point["Sample_a_Resistance"] = NAN
    data_point["Sample_a_Resistance_Error"] = NAN
    data_point["Sample_b_Resistance"] = NAN
    data_point["Sample_b_Resistance_Error"] = NAN

    if active_channel:
        ch = str(active_channel).strip().lower()
        data_point["LockIn_X"] = x
        data_point["LockIn_Y"] = y
        data_point["LockIn_R"] = r
        data_point["LockIn_Theta"] = theta
        data_point["LockIn_X_Error"] = x_std
        data_point["LockIn_Y_Error"] = y_std
        data_point["LockIn_R_Error"] = r_std
        data_point["LockIn_Theta_Error"] = theta_std
        data_point["Sample_Resistance"] = sample_resistance
        data_point["Sample_Resistance_Error"] = sample_resistance_std

    if active_channel in ("a", "b"):
        ch = str(active_channel).strip().lower()
        data_point[f"LockIn_X_{ch}"] = x
        data_point[f"LockIn_Y_{ch}"] = y
        data_point[f"LockIn_R_{ch}"] = r
        data_point[f"LockIn_Theta_{ch}"] = theta
        data_point[f"LockIn_X_{ch}_Error"] = x_std
        data_point[f"LockIn_Y_{ch}_Error"] = y_std
        data_point[f"LockIn_R_{ch}_Error"] = r_std
        data_point[f"LockIn_Theta_{ch}_Error"] = theta_std
        data_point[f"Sample_{ch}_Resistance"] = sample_resistance
        data_point[f"Sample_{ch}_Resistance_Error"] = sample_resistance_std
