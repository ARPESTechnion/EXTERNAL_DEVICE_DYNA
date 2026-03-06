"""
v3.core.measurements  —  Pure-logic measurement functions.

Each measurement function receives a ``MeasurementContext`` and returns a
``dict[str, float]`` data-point.  They do NOT touch Tkinter, do NOT write
CSV directly, and do NOT manage state — those responsibilities belong to
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


# ============================================================================
# MeasurementContext  —  shared dependencies for every measurement
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

    # PPMS snapshot accessors — return current values, or NaN
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
    active_channel = ctx.get_active_channel()

    # Build data point
    data_point: dict[str, Any] = {
        "Time": ctx.data_mgr.elapsed_time(),
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
    excitation: str | None = None,
    frequency: float | None = None,
    tau_idx: int = 0,
) -> dict[str, Any]:
    """
    Continuous lock-in measurement — no settling, no auto-adjust.

    Optionally toggles excitation on/off.
    """
    ctx.ui_bus.post(W_LED_LOCKIN, True)

    if current is None:
        current = 0.0
    if series_resistance is None:
        series_resistance = 0.0

    output_voltage = current * series_resistance

    # Handle excitation toggle
    if excitation == "on":
        ctx.bus.execute(INST_LOCKIN, "sine_output_on")
        ctx.ui_bus.post(W_LOCKIN_OUTPUT_VOLTAGE, output_voltage)
    elif excitation == "off":
        ctx.bus.execute(INST_LOCKIN, "sine_output_off")
        ctx.ui_bus.post(W_LOCKIN_OUTPUT_VOLTAGE, 0.0)
    else:
        ctx.ui_bus.post(W_LOCKIN_OUTPUT_VOLTAGE, output_voltage)

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

    active_channel = ctx.get_active_channel()

    data_point: dict[str, Any] = {
        "Time": ctx.data_mgr.elapsed_time(),
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
    # Hall measurement (skip_write = True equivalent — we merge manually)
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
                ctx.ui_bus.post_log("Warning: Temperature reading is NaN — treating as stable")
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
                ctx.ui_bus.post_log("Warning: Field reading is NaN — treating as stable")
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


def set_lockin_current(
    ctx: MeasurementContext,
    current: float,
    series_resistance: float,
) -> float:
    """Set lock-in excitation current via output voltage = I × R."""
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
        if n < 1 or n > 8:
            raise ValueError(f"Routing number {n} out of range (1–8)")
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
