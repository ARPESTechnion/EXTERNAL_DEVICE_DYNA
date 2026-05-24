"""
v3.gui.script_runner  -  Command dispatch loop for parsed scripts.

This module bridges the parsed DSL commands with the measurement/control
functions from ``v3.core.measurements``.  It is executed on the
experiment-engine worker thread.
"""

from __future__ import annotations

import logging
import math
import threading
import time
from pathlib import Path
from typing import TYPE_CHECKING

from v3.core.constants import HELMHOLTZ_MAX_CURRENT_A, INST_LOCKIN, INST_SWITCH
from v3.core.experiment_engine import ExperimentEngine, StopRequested
from v3.core.measurements import (
    MeasurementContext,
    configure_channel,
    disable_hall_output,
    enable_hall_output,
    measure_iv_curve,
    measure_resistance,
    measure_lockin_continuous,
    lockin_auto_gain,
    lockin_auto_phase,
    lockin_auto_reserve,
    measure_hall,
    measure_hall_continuous,
    measure_lockin,
    open_all_channels,
    set_dyna_field,
    set_dyna_temp,
    set_lockin_current,
    set_lockin_filter,
    set_lockin_frequency,
    set_lockin_sensitivity,
    set_lockin_time_constant,
    wait_for_events,
)
from v3.core.script_parser import INSTRUMENT_REQUIREMENTS, LOOP_COMMANDS, ParsedCommand
from v3.core.ui_events import (
    W_DYNA_SETPOINT,
    W_HALL_RESULT,
    W_HELMHOLTZ_SETPOINT,
    W_LED_HALL,
    W_LOCKIN_CHANNEL,
    W_LED_LOCKIN,
    W_LOCKIN_OUTPUT_VOLTAGE,
    W_LOCKIN_PHASE,
    W_LOCKIN_PHASE_ERROR,
    W_LOCKIN_R,
    W_LOCKIN_R_ERROR,
    W_LOCKIN_RESISTANCE,
    W_LOCKIN_RESISTANCE_ERROR,
    W_LOCKIN_SENSITIVITY,
    W_LOCKIN_STATUS,
    W_LOCKIN_X,
    W_LOCKIN_X_ERROR,
    W_LOCKIN_Y,
    W_LOCKIN_Y_ERROR,
    W_RESULTS_NEW_POINT,
    W_SWITCH_STATUS,
)

if TYPE_CHECKING:
    from v3.gui.app import MeasureApp

logger = logging.getLogger(__name__)


# SR830 time constants (s) for set_lockin_time_constant seconds→index conversion.
_LOCKIN_TAU_TABLE = [
    10e-6, 30e-6, 100e-6, 300e-6, 1e-3, 3e-3, 10e-3, 30e-3,
    100e-3, 300e-3, 1.0, 3.0, 10.0, 30.0, 100.0, 300.0,
    1e3, 3e3, 10e3, 30e3,
]

_DYNA_FIELD_RES_OE = 1e-3
_DYNA_TEMP_RES_K = 1e-5
_FAIL_FAST_COMMAND_ERRORS = True
_MAX_NESTED_SCRIPT_DEPTH = 8


def _round_to(value: float, resolution: float) -> float:
    if resolution <= 0:
        return float(value)
    return round(float(value) / resolution) * resolution


def _parse_bool(value: str | bool | None, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _seconds_to_tau_index(seconds: float) -> int:
    if not math.isfinite(seconds) or seconds <= 0:
        return 0
    return min(range(len(_LOCKIN_TAU_TABLE)), key=lambda index: abs(_LOCKIN_TAU_TABLE[index] - seconds))


def _parse_voltage_range(raw: str | float | int | None, *, default_raw: str = "auto") -> tuple[float | None, bool]:
    if raw is None:
        raw = default_raw
    text = str(raw).strip().lower()
    if text == "auto":
        return None, True
    if text.endswith("mv"):
        return float(text[:-2]) * 1e-3, False
    if text.endswith("v"):
        return float(text[:-1]), False
    return float(text), False


def _parse_source_value(raw: str | float | int | None, *, mode: str, default: float | None = None) -> float | None:
    if raw is None:
        return default
    text = str(raw).strip().lower()
    if text == "":
        return default

    if mode == "current":
        if text.endswith("ma"):
            return float(text[:-2]) * 1e-3
        if text.endswith("ua"):
            return float(text[:-2]) * 1e-6
        if text.endswith("a"):
            return float(text[:-1])
        return float(text)

    if text.endswith("mv"):
        return float(text[:-2]) * 1e-3
    if text.endswith("v"):
        return float(text[:-1])
    return float(text)


def _parse_iv_range_value(
    raw: str | float | int | None,
    *,
    quantity: str,
    default: float | None = None,
) -> float | None:
    if raw is None:
        return default
    text = str(raw).strip().lower()
    if text == "":
        return default
    if text == "auto":
        return None

    if quantity == "current":
        if text.endswith("ma"):
            return float(text[:-2]) * 1e-3
        if text.endswith("ua"):
            return float(text[:-2]) * 1e-6
        if text.endswith("a"):
            return float(text[:-1])
        return float(text)

    if text.endswith("mv"):
        return float(text[:-2]) * 1e-3
    if text.endswith("v"):
        return float(text[:-1])
    return float(text)


def _kw_with_unit_suffix(cmd: ParsedCommand, key: str, milli_key: str) -> str | None:
    milli_val = cmd.get_str(milli_key, None)
    if milli_val is not None:
        return f"{milli_val}mA"
    return cmd.get_str(key, None)


def _normalize_wait_events(tokens: list[str]) -> list[str]:
    aliases: dict[str, list[str]] = {
        "temp_stable": ["temp"],
        "field_stable": ["field"],
        "dyna_ready": ["field"],
        "helmholtz_field": ["helmholtz"],
        "helmholtz_stable": ["helmholtz"],
    }
    normalized: list[str] = []
    for token in tokens:
        key = token.strip().lower()
        normalized.extend(aliases.get(key, [key]))
    return normalized


def _sleep_with_stop(stop_event: threading.Event, seconds: float) -> None:
    """Interruptible sleep that aborts promptly when stop is requested."""
    duration = max(0.0, float(seconds))
    if duration <= 0:
        return
    if stop_event.wait(timeout=duration):
        raise StopRequested()


def _post_switch_summary(ctx: MeasurementContext, app: "MeasureApp") -> None:
    """Keep Results and Switch tabs synced to the exact same switch status text."""
    try:
        summary = app.switch_tab._switch_state_summary()
    except Exception:
        summary = "Switch: status unavailable"
    ctx.ui_bus.post(W_SWITCH_STATUS, summary)


def _close_active_channel(ctx: MeasurementContext, app: "MeasureApp", channel: str) -> None:
    """Close switch routing for a logical channel and mark it active."""
    token = str(channel).strip().lower()
    if token not in app.channels:
        raise ValueError(f"Channel must be one of: {', '.join(app.channels)}")

    channel_cfg = app.channel_configs.get(token)
    if channel_cfg is None:
        raise ValueError(f"Unknown channel: {token}")

    ip = int(channel_cfg["I+"].get())
    vp = int(channel_cfg["V+"].get())
    vm = int(channel_cfg["V-"].get())
    im = int(channel_cfg["I-"].get())

    open_all_channels(ctx)
    inst = app.bus.get_raw(INST_SWITCH)
    if inst is not None and hasattr(inst, "close_list"):
        app.bus.execute(INST_SWITCH, "close_list", ip, vp, vm, im)
    else:
        for pin in (ip, vp, vm, im):
            app.bus.execute(INST_SWITCH, "close_channel", int(pin))

    current_signature = (
        int(channel_cfg["I+"].get()),
        int(channel_cfg["V+"].get()),
        int(channel_cfg["V-"].get()),
        int(channel_cfg["I-"].get()),
    )
    canonical = min(
        (
            ch for ch in app.channels
            if (
                int(app.channel_configs[ch]["I+"].get()),
                int(app.channel_configs[ch]["V+"].get()),
                int(app.channel_configs[ch]["V-"].get()),
                int(app.channel_configs[ch]["I-"].get()),
            ) == current_signature
        ),
        key=lambda ch: ch.lower(),
        default=token,
    )

    app.active_channel = canonical


def _post_lockin_result_events(ctx: MeasurementContext, app: "MeasureApp", result: dict[str, object]) -> None:
    """Publish lock-in values so Results status panel updates for script-driven measurements."""
    channel = app.active_channel if app.active_channel in app.channels else None

    def _num(value: object) -> float | None:
        try:
            v = float(value)
            if math.isnan(v) or math.isinf(v):
                return None
            return v
        except Exception:
            return None

    def _pick(*keys: str) -> float | None:
        for key in keys:
            if key in result:
                v = _num(result.get(key))
                if v is not None:
                    return v
        return None

    if channel is not None:
        x = _pick("LockIn_X", f"LockIn_X_{channel}")
        x_err = _pick("LockIn_X_Error", f"LockIn_X_{channel}_Error")
        y = _pick("LockIn_Y", f"LockIn_Y_{channel}")
        y_err = _pick("LockIn_Y_Error", f"LockIn_Y_{channel}_Error")
        r = _pick("LockIn_R", f"LockIn_R_{channel}")
        r_err = _pick("LockIn_R_Error", f"LockIn_R_{channel}_Error")
        theta = _pick("LockIn_Theta", f"LockIn_Theta_{channel}")
        theta_err = _pick("LockIn_Theta_Error", f"LockIn_Theta_{channel}_Error")
        resistance = _pick("Sample_Resistance", f"Sample_{channel}_Resistance")
        resistance_err = _pick("Sample_Resistance_Error", f"Sample_{channel}_Resistance_Error")
    else:
        x = _pick("LockIn_X", "LockIn_X_a", "LockIn_X_b")
        x_err = _pick("LockIn_X_Error", "LockIn_X_a_Error", "LockIn_X_b_Error")
        y = _pick("LockIn_Y", "LockIn_Y_a", "LockIn_Y_b")
        y_err = _pick("LockIn_Y_Error", "LockIn_Y_a_Error", "LockIn_Y_b_Error")
        r = _pick("LockIn_R", "LockIn_R_a", "LockIn_R_b")
        r_err = _pick("LockIn_R_Error", "LockIn_R_a_Error", "LockIn_R_b_Error")
        theta = _pick("LockIn_Theta", "LockIn_Theta_a", "LockIn_Theta_b")
        theta_err = _pick("LockIn_Theta_Error", "LockIn_Theta_a_Error", "LockIn_Theta_b_Error")
        resistance = _pick("Sample_Resistance", "Sample_a_Resistance", "Sample_b_Resistance")
        resistance_err = _pick(
            "Sample_Resistance_Error",
            "Sample_a_Resistance_Error",
            "Sample_b_Resistance_Error",
        )

    if x is not None:
        ctx.ui_bus.post(W_LOCKIN_X, x)
    if y is not None:
        ctx.ui_bus.post(W_LOCKIN_Y, y)
    if r is not None:
        ctx.ui_bus.post(W_LOCKIN_R, r)
    if theta is not None:
        ctx.ui_bus.post(W_LOCKIN_PHASE, theta)
    if x_err is not None:
        ctx.ui_bus.post(W_LOCKIN_X_ERROR, x_err)
    if y_err is not None:
        ctx.ui_bus.post(W_LOCKIN_Y_ERROR, y_err)
    if r_err is not None:
        ctx.ui_bus.post(W_LOCKIN_R_ERROR, r_err)
    if theta_err is not None:
        ctx.ui_bus.post(W_LOCKIN_PHASE_ERROR, theta_err)
    if resistance is not None:
        ctx.ui_bus.post(W_LOCKIN_RESISTANCE, resistance)
    if resistance_err is not None:
        ctx.ui_bus.post(W_LOCKIN_RESISTANCE_ERROR, resistance_err)
    if channel is not None:
        ctx.ui_bus.post(W_LOCKIN_CHANNEL, f"Channel {channel.upper()}")
    else:
        ctx.ui_bus.post(W_LOCKIN_CHANNEL, "No channel active")

    # Keep GUI sensitivity selector in sync after measurements that may autorange.
    try:
        sens_idx = int(ctx.bus.execute("lockin", "get_sensitivity"))
        if 0 <= sens_idx <= 26:
            ctx.ui_bus.post(W_LOCKIN_SENSITIVITY, sens_idx)
    except Exception:
        logger.debug("Could not refresh lock-in sensitivity after measurement", exc_info=True)

    ctx.ui_bus.post(W_LOCKIN_STATUS, "LockIn: measurement completed")


def _post_hall_result_events(ctx: MeasurementContext, app: "MeasureApp", result: dict[str, object]) -> None:
    """Publish Hall result values so Hall/Results panels update for scripted Hall measurements."""

    def _num(value: object, default: float = 0.0) -> float:
        try:
            v = float(value)
            if math.isnan(v) or math.isinf(v):
                return default
            return v
        except Exception:
            return default

    voltage = _num(result.get("Hall Voltage", 0.0))
    field = _num(result.get("Hall Field", 0.0))
    voltage_error = _num(result.get("Hall Voltage Error", 0.0))
    field_error = _num(result.get("Hall Field Error", 0.0))

    ctx.ui_bus.post(
        W_HALL_RESULT,
        {
            "voltage": voltage,
            "field": field,
            "voltage_error": voltage_error,
            "field_error": field_error,
        },
    )


def _post_helmholtz_setpoint(app: "MeasureApp", field_g: float, rate_mA_s: float) -> None:
    """Sync Helmholtz tab setpoint widgets to script-issued commands."""
    if not hasattr(app, "ui_bus"):
        return
    total_current = 0.0
    try:
        total_current = float(app.helmholtz.calibration.field_to_current(float(field_g)))
    except Exception:
        total_current = 0.0
    app.ui_bus.post(
        W_HELMHOLTZ_SETPOINT,
        {
            "field_g": float(field_g),
            "rate_mA_s": float(rate_mA_s),
            "total_current_a": total_current,
        },
    )


def _post_dyna_setpoint(
    ctx: MeasurementContext,
    *,
    temp_k: float | None = None,
    temp_rate_k_min: float | None = None,
    temp_mode: str | None = None,
    field_oe: float | None = None,
    field_rate_oe_s: float | None = None,
    field_mode: str | None = None,
) -> None:
    payload: dict[str, object] = {}
    if temp_k is not None:
        payload["temp_k"] = temp_k
    if temp_rate_k_min is not None:
        payload["temp_rate_k_min"] = temp_rate_k_min
    if temp_mode is not None:
        payload["temp_mode"] = temp_mode
    if field_oe is not None:
        payload["field_oe"] = field_oe
    if field_rate_oe_s is not None:
        payload["field_rate_oe_s"] = field_rate_oe_s
    if field_mode is not None:
        payload["field_mode"] = field_mode
    if payload:
        ctx.ui_bus.post(W_DYNA_SETPOINT, payload)


def _required_disconnected_for_command(app: "MeasureApp", command_name: str) -> list[str]:
    required = INSTRUMENT_REQUIREMENTS.get(command_name, [])
    missing: list[str] = []
    for key in required:
        if not bool(app.instrument_connected.get(key, False)):
            missing.append(key)
    return missing


def _is_disconnect_error(exc: Exception) -> bool:
    msg = str(exc).lower()
    return (
        "not connected" in msg
        or "disconnected" in msg
        or "not available" in msg
    )


def _confirm_dyna_cooling_or_abort(
    engine: ExperimentEngine,
    ctx: MeasurementContext,
    app: "MeasureApp",
    *,
    target_temp_k: float,
    command_name: str,
) -> None:
    confirm = getattr(app, "confirm_dyna_low_temp_transition", None)
    if not callable(confirm):
        return

    allowed = bool(confirm(float(target_temp_k), source=f"script:{command_name}"))
    if allowed:
        return

    ctx.ui_bus.post_log(
        "Script aborted: Dyna purge/seal safety confirmation declined."
    )
    engine.request_stop()
    raise StopRequested()


def _measure_hall_with_gui_settings(ctx: MeasurementContext, app: "MeasureApp") -> dict[str, object]:
    """Run one Hall measurement using current Hall-tab settings."""
    hall_vr_raw = app.hall_tab.k2450_voltage_range.get()
    hall_vr = str(hall_vr_raw).strip().lower()
    return measure_hall(
        ctx,
        current_mA=app.hall_tab.k2450_current.get(),
        nplc=app.hall_tab.k2450_nplc.get(),
        compliance_v=app.hall_tab.k2450_compliance_v.get(),
        voltage_range=None if hall_vr == "auto" else float(hall_vr_raw),
        auto_range=hall_vr == "auto",
        filter_count=app.hall_tab.k2450_filter_count.get(),
        tbm=app.hall_tab.k2450_tbm.get(),
    )


def _apply_hall_fix_step(
    engine: ExperimentEngine,
    app: "MeasureApp",
    *,
    target_hall_g: float,
    measured_hall_g: float,
    helmholtz_rate_g_s: float,
    max_current_change_a: float,
) -> float:
    """Apply one Helmholtz correction step and return remaining Hall error in Gauss."""
    engine.check_stop()
    engine.check_pause()

    err_g = target_hall_g - measured_hall_g
    current_helm_g = float(app.helmholtz.snapshot().get("Helmholtz_Field", 0.0) or 0.0)
    target_helm_g = current_helm_g + err_g

    required_change_a = abs(float(app.helmholtz.calibration.field_to_current(err_g)))
    if required_change_a > max_current_change_a:
        raise RuntimeError(
            "Hall correction exceeds allowed current change: "
            f"need {required_change_a:.3f} A, limit {max_current_change_a:.3f} A "
            "(use max_current_change=... to override)."
        )

    target_total_current_a = abs(float(app.helmholtz.calibration.field_to_current(target_helm_g)))
    if target_total_current_a > HELMHOLTZ_MAX_CURRENT_A:
        raise RuntimeError(
            "Hall correction target exceeds Helmholtz safety limit: "
            f"target {target_helm_g:.2f} G requires {target_total_current_a:.3f} A total "
            f"(limit {HELMHOLTZ_MAX_CURRENT_A:.3f} A)."
        )

    # Keep Helmholtz tab setpoint/rate in sync with script-driven Hall correction.
    _post_helmholtz_setpoint(app, target_helm_g, helmholtz_rate_g_s)
    app.helmholtz.set_field(target_helm_g, rate_mA_per_s=helmholtz_rate_g_s)
    app.helmholtz.ramp_to_target(engine.stop_event)
    return err_g


def _run_hall_fix_loop(
    engine: ExperimentEngine,
    ctx: MeasurementContext,
    app: "MeasureApp",
    *,
    target_hall_g: float,
    helmholtz_rate_g_s: float,
    max_current_change_a: float,
    tolerance_g: float = 1.0,
    max_iter: int = 8,
) -> None:
    """Iteratively correct Hall field using Helmholtz setpoints.

    These Hall probe reads are diagnostic for correction only, so they are logged
    but intentionally not written to the main data file.
    """
    for _ in range(max_iter):
        hall_data = _measure_hall_with_gui_settings(ctx, app)
        measured_hall_g = float(hall_data.get("Hall Field", 0.0))

        err_g = target_hall_g - measured_hall_g
        ctx.ui_bus.post_log(
            f"Hall correction: target={target_hall_g:.2f} G, measured={measured_hall_g:.2f} G, err={err_g:.2f} G"
        )

        if abs(err_g) <= tolerance_g:
            return

        _apply_hall_fix_step(
            engine,
            app,
            target_hall_g=target_hall_g,
            measured_hall_g=measured_hall_g,
            helmholtz_rate_g_s=helmholtz_rate_g_s,
            max_current_change_a=max_current_change_a,
        )


def run_commands(
    engine: ExperimentEngine,
    ctx: MeasurementContext,
    commands: list[ParsedCommand],
    app: "MeasureApp",
) -> None:
    """
    Execute a list of parsed commands on the engine's worker thread.

    Parameters
    ----------
    engine : ExperimentEngine
        Provides check_stop(), check_pause(), interruptible_sleep().
    ctx : MeasurementContext
        Shared measurement context.
    commands : list[ParsedCommand]
        Top-level commands to execute.
    app : MeasureApp
        GUI app reference for tab-level settings access.
    """
    total = len(commands)
    for i, cmd in enumerate(commands, start=1):
        engine.check_stop()
        engine.check_pause()
        engine.set_progress(cmd.line_number, total)
        _dispatch(engine, ctx, cmd, app)
        engine.interruptible_sleep(0.1)


def _dispatch(
    engine: ExperimentEngine,
    ctx: MeasurementContext,
    cmd: ParsedCommand,
    app: "MeasureApp",
) -> None:
    """Dispatch a single command."""
    name = cmd.name
    args = cmd.args

    try:
        disconnected = _required_disconnected_for_command(app, name)
        if disconnected:
            instruments = ", ".join(disconnected)
            raise RuntimeError(f"required instrument(s) disconnected: {instruments}")

        # ==============================================================
        # PPMS commands
        # ==============================================================
        if name == "set_dyna_field":
            field_oe = _round_to(float(args[0]), _DYNA_FIELD_RES_OE)
            rate = _round_to(float(args[1]), _DYNA_FIELD_RES_OE)
            approach = args[2] if len(args) > 2 else "linear"
            set_dyna_field(ctx, field_oe, rate, approach)
            _post_dyna_setpoint(ctx, field_oe=field_oe, field_rate_oe_s=rate, field_mode=approach)
            ctx.ui_bus.post_log(f"Set Dyna field: {field_oe:.2f} Oe @ {rate:.2f} Oe/s ({approach})")

        elif name == "set_dyna_temp":
            temp_k = _round_to(float(args[0]), _DYNA_TEMP_RES_K)
            rate = _round_to(float(args[1]), _DYNA_TEMP_RES_K)
            approach = args[2] if len(args) > 2 else "fast_settle"
            _confirm_dyna_cooling_or_abort(
                engine,
                ctx,
                app,
                target_temp_k=temp_k,
                command_name=name,
            )
            set_dyna_temp(ctx, temp_k, rate, approach)
            _post_dyna_setpoint(ctx, temp_k=temp_k, temp_rate_k_min=rate, temp_mode=approach)
            ctx.ui_bus.post_log(f"Set Dyna temp: {temp_k:.2f} K @ {rate:.2f} K/min ({approach})")

        # ==============================================================
        # Helmholtz commands
        # ==============================================================
        elif name == "set_helmholtz_field":
            field_g = float(args[0])
            rate_mA_s = float(args[1])
            _post_helmholtz_setpoint(app, field_g, rate_mA_s)
            app.helmholtz.set_field(field_g, rate_mA_per_s=rate_mA_s)
            app.helmholtz.ramp_to_target(engine.stop_event)
            ctx.ui_bus.post_log(f"Helmholtz → {field_g:.2f} G (done)")

        # ==============================================================
        # Measurement commands
        # ==============================================================
        elif name == "measure_lockin":
            channel = cmd.get_str("channel", app.active_channel or "a")
            if channel in app.channels:
                app.active_channel = channel

            avg = cmd.get_int("avg", int(app.lockin_tab.lockin_averaging.get()))
            what = cmd.get_tuple("what", ("X", "Y", "R", "Theta"))
            current = cmd.get_float("current", app.lockin_tab.lockin_output_current.get())
            series_resistance = cmd.get_float("series_resistance", app.lockin_tab.lockin_r_lockin.get())
            start_sens = cmd.get_int("start_sens", int(app.lockin_tab.lockin_sensitivity_idx.get()))
            use_autorange = cmd.get_bool("use_autorange", True)
            use_autophase = cmd.get_bool("use_autophase", True)
            sample_delay = cmd.get_float("sample_delay", 0.05)
            tau_idx = int(app.lockin_tab.lockin_time_constant_idx.get())
            db_oct = int(app.lockin_tab.lockin_filter_slope.get())
            filter_idx = {6: 0, 12: 1, 18: 2, 24: 3}.get(db_oct, 3)

            result = measure_lockin(
                ctx,
                what=what,
                current=current,
                series_resistance=series_resistance,
                avg=avg,
                start_sens=start_sens,
                use_autorange=use_autorange,
                use_autophase=use_autophase,
                sample_delay=sample_delay,
                tau_idx=tau_idx,
                filter_slope_idx=filter_idx,
                frequency=app.lockin_tab.lockin_frequency.get(),
            )
            ctx.data_mgr.write_row(result, measurement_type="LockIn")
            _post_lockin_result_events(ctx, app, result)
            ctx.ui_bus.post_log("LockIn measurement recorded")
            ctx.ui_bus.post(W_RESULTS_NEW_POINT, True)

        elif name == "continuous_measure_lockin":
            channel = cmd.get_str("channel", app.active_channel or "a")
            if channel in app.channels:
                app.active_channel = channel

            avg = cmd.get_int("avg", int(app.lockin_tab.lockin_averaging.get()))
            what = cmd.get_tuple("what", ("X", "Y", "R", "Theta"))
            sample_delay = cmd.get_float("sample_delay", 0.05)
            tau_idx = int(app.lockin_tab.lockin_time_constant_idx.get())

            result = measure_lockin_continuous(
                ctx,
                what=what,
                avg=avg,
                sample_delay=sample_delay,
                current=app.lockin_tab.lockin_output_current.get(),
                series_resistance=app.lockin_tab.lockin_r_lockin.get(),
                frequency=app.lockin_tab.lockin_frequency.get(),
                tau_idx=tau_idx,
            )
            ctx.data_mgr.write_row(result, measurement_type="LockIn")
            _post_lockin_result_events(ctx, app, result)
            ctx.ui_bus.post_log("LockIn continuous measurement recorded")
            ctx.ui_bus.post(W_RESULTS_NEW_POINT, True)

        elif name == "measure_hall_field":
            current_mA = cmd.get_float("current", app.hall_tab.k2450_current.get())
            nplc = cmd.get_float("nplc", app.hall_tab.k2450_iv_nplc.get())
            compliance_v = cmd.get_float("compliance_v", app.hall_tab.k2450_compliance_v.get())
            voltage_range_raw = cmd.get_str("voltage_range", app.hall_tab.k2450_voltage_range.get())
            voltage_range, auto_range = _parse_voltage_range(
                voltage_range_raw,
                default_raw=str(app.hall_tab.k2450_voltage_range.get()),
            )
            filter_count = cmd.get_int("filter_count", app.hall_tab.k2450_filter_count.get())
            tbm = cmd.get_float("tbm", app.hall_tab.k2450_tbm.get())

            result = measure_hall(
                ctx,
                current_mA=current_mA,
                nplc=nplc,
                compliance_v=compliance_v,
                voltage_range=voltage_range,
                auto_range=auto_range,
                filter_count=filter_count,
                tbm=tbm,
            )
            ctx.data_mgr.write_row(result, measurement_type="Hall")
            _post_hall_result_events(ctx, app, result)
            ctx.ui_bus.post_log("Hall measurement recorded")
            ctx.ui_bus.post(W_RESULTS_NEW_POINT, True)

        elif name == "measure_resistance":
            current_default_a = float(app.hall_tab.k2450_resistance_current_mA.get()) / 1000.0
            current = _parse_source_value(
                _kw_with_unit_suffix(cmd, "current", "current_ma"),
                mode="current",
                default=current_default_a,
            )
            if current is None:
                raise ValueError("measure_resistance requires current")
            nplc = cmd.get_float("nplc", app.hall_tab.k2450_resistance_nplc.get())
            compliance = cmd.get_float("compliance", app.hall_tab.k2450_resistance_compliance_v.get())
            voltage_range_raw = cmd.get_str("voltage_range", app.hall_tab.k2450_resistance_voltage_range.get())
            voltage_range, auto_range = _parse_voltage_range(
                voltage_range_raw,
                default_raw=str(app.hall_tab.k2450_resistance_voltage_range.get()),
            )
            settle_time = cmd.get_float("settle_time", app.hall_tab.k2450_resistance_settle.get())
            repetitions = cmd.get_int("repetitions", app.hall_tab.k2450_resistance_repetitions.get())

            ctx.ui_bus.post(W_LED_HALL, True)
            try:
                result = measure_resistance(
                    ctx,
                    current=float(current),
                    compliance=float(compliance),
                    nplc=nplc,
                    voltage_range=voltage_range,
                    auto_range=auto_range,
                    settle_time=float(settle_time),
                    repetitions=repetitions,
                )
            finally:
                ctx.ui_bus.post(W_LED_HALL, False)
            ctx.data_mgr.write_row(result, measurement_type="Resistance")
            ctx.ui_bus.post_log("Resistance measurement recorded")
            ctx.ui_bus.post(W_RESULTS_NEW_POINT, True)

        elif name == "measure_iv_curve":
            t0 = time.perf_counter()
            mode = cmd.get_str("mode", "current")
            mode_norm = str(mode).strip().lower()
            source_mode = "current" if mode_norm in {"current", "source_current", "i"} else "voltage"

            start = _parse_source_value(_kw_with_unit_suffix(cmd, "start", "start_ma"), mode=source_mode)
            step = _parse_source_value(_kw_with_unit_suffix(cmd, "step", "step_ma"), mode=source_mode)
            iv_min = _parse_source_value(
                _kw_with_unit_suffix(cmd, "min", "min_ma") or cmd.get_str("iv_min", None),
                mode=source_mode,
            )
            iv_max = _parse_source_value(
                _kw_with_unit_suffix(cmd, "max", "max_ma") or cmd.get_str("iv_max", None),
                mode=source_mode,
            )
            stop = _parse_source_value(_kw_with_unit_suffix(cmd, "stop", "stop_ma"), mode=source_mode)

            shape = cmd.get_str("shape", "start_min_max_start" if (iv_min is not None and iv_max is not None) else "start_max_start")
            if start is None or step is None:
                raise ValueError("measure_iv_curve requires start and step")
            if (iv_min is None) ^ (iv_max is None):
                raise ValueError("measure_iv_curve with min/max syntax requires both min and max")
            if iv_min is None and iv_max is None and stop is None:
                raise ValueError("measure_iv_curve requires start,min,max,step (preferred) or start,stop,step")

            if source_mode == "current":
                source_range_raw = _kw_with_unit_suffix(cmd, "source_range", "source_range_ma")
            else:
                source_range_raw = cmd.get_str("source_range", None)
            source_range = _parse_iv_range_value(
                source_range_raw,
                quantity="current" if source_mode == "current" else "voltage",
            )

            if source_mode == "voltage":
                measure_range_raw = _kw_with_unit_suffix(cmd, "measure_range", "measure_range_ma")
            else:
                measure_range_raw = cmd.get_str("measure_range", None)
            measure_range = _parse_iv_range_value(
                measure_range_raw,
                quantity="voltage" if source_mode == "current" else "current",
            )
            compliance = cmd.get_float("compliance")
            nplc = cmd.get_float("nplc", app.hall_tab.k2450_nplc.get())
            auto_range = cmd.get_bool("auto_range", True)
            settle_time = cmd.get_float("settle_time", 0.0)
            repetitions = cmd.get_int("repetitions", 1)
            keep_output = cmd.get_bool("keep_output", False)
            ramp_to_start = cmd.get_bool("ramp_to_start", True)
            reset_to_zero = cmd.get_bool("reset_to_zero", ramp_to_start)

            ctx.ui_bus.post(W_LED_HALL, True)
            try:
                result = measure_iv_curve(
                    ctx,
                    mode=mode,
                    shape=shape,
                    start=float(start),
                    stop=None if stop is None else float(stop),
                    step=float(step),
                    iv_min=None if iv_min is None else float(iv_min),
                    iv_max=None if iv_max is None else float(iv_max),
                    source_range=source_range,
                    measure_range=measure_range,
                    compliance=compliance,
                    nplc=nplc,
                    auto_range=auto_range,
                    settle_time=settle_time,
                    repetitions=repetitions,
                    keep_output=keep_output,
                    ramp_to_start=ramp_to_start,
                    reset_to_zero=reset_to_zero,
                )
            finally:
                ctx.ui_bus.post(W_LED_HALL, False)
            wrote = ctx.data_mgr.write_rows(result["points"], measurement_type="IV")
            if wrote > 0:
                ctx.ui_bus.post(W_RESULTS_NEW_POINT, True)
            elapsed_s = max(0.0, time.perf_counter() - t0)
            ctx.ui_bus.post_log(
                f"IV curve recorded ({result['point_count']} points in {elapsed_s:.2f} s, "
                f"engine={result.get('engine', 'point')})"
            )

        elif name == "continuous_measure_hall_field":
            current_mA = cmd.get_float("current", app.hall_tab.k2450_current.get())
            nplc = cmd.get_float("nplc", app.hall_tab.k2450_nplc.get())
            compliance_v = cmd.get_float("compliance_v", app.hall_tab.k2450_compliance_v.get())
            voltage_range_raw = cmd.get_str("voltage_range", app.hall_tab.k2450_voltage_range.get())
            voltage_range, auto_range = _parse_voltage_range(
                voltage_range_raw,
                default_raw=str(app.hall_tab.k2450_voltage_range.get()),
            )
            filter_count = cmd.get_int("filter_count", app.hall_tab.k2450_filter_count.get())
            tbm = cmd.get_float("tbm", app.hall_tab.k2450_tbm.get())

            result = measure_hall_continuous(
                ctx,
                current_mA=current_mA,
                nplc=nplc,
                compliance_v=compliance_v,
                voltage_range=voltage_range,
                auto_range=auto_range,
                filter_count=filter_count,
                tbm=tbm,
            )
            ctx.data_mgr.write_row(result, measurement_type="Hall")
            _post_hall_result_events(ctx, app, result)
            ctx.ui_bus.post_log("Hall continuous measurement recorded")
            ctx.ui_bus.post(W_RESULTS_NEW_POINT, True)

        elif name == "enable_hall_output":
            current_mA = cmd.get_float("current", app.hall_tab.k2450_current.get())
            compliance_v = cmd.get_float("compliance_v", app.hall_tab.k2450_compliance_v.get())
            enable_hall_output(
                ctx,
                current_mA=current_mA,
                compliance_v=compliance_v,
            )
            ctx.ui_bus.post_log(
                f"Hall source enabled: {float(current_mA):.3f} mA, compliance {float(compliance_v):.3f} V"
            )

        elif name == "disable_hall_output":
            disable_hall_output(ctx)
            ctx.ui_bus.post_log("Hall source disabled")

        elif name == "full_measure":
            channel = args[0] if args else (app.channels[0] if app.channels else "a")
            if channel in app.channels:
                app.active_channel = channel

            hall_voltage_range_raw = cmd.get_str("hall_voltage_range", app.hall_tab.k2450_voltage_range.get())
            hall_voltage_range, hall_auto_range = _parse_voltage_range(
                hall_voltage_range_raw,
                default_raw=str(app.hall_tab.k2450_voltage_range.get()),
            )

            db_oct = int(app.lockin_tab.lockin_filter_slope.get())
            lockin_filter_idx = {6: 0, 12: 1, 18: 2, 24: 3}.get(db_oct, 3)

            lockin_current = cmd.get_float("lockin_current", app.lockin_tab.lockin_output_current.get())
            lockin_series_resistance = cmd.get_float(
                "lockin_series_resistance",
                app.lockin_tab.lockin_r_lockin.get(),
            )
            lockin_avg = cmd.get_int("lockin_avg", int(app.lockin_tab.lockin_averaging.get()))
            lockin_start_sens = cmd.get_int("lockin_start_sens", int(app.lockin_tab.lockin_sensitivity_idx.get()))
            lockin_use_autorange = cmd.get_bool("lockin_use_autorange", True)
            lockin_use_autophase = cmd.get_bool("lockin_use_autophase", True)
            lockin_sample_delay = cmd.get_float("lockin_sample_delay", 0.05)
            lockin_what = cmd.get_tuple("lockin_what", ("X", "Y", "R", "Theta"))

            hall_current_mA = cmd.get_float("hall_current", app.hall_tab.k2450_current.get())
            hall_nplc = cmd.get_float("hall_nplc", app.hall_tab.k2450_nplc.get())
            hall_compliance_v = cmd.get_float("hall_compliance", app.hall_tab.k2450_compliance_v.get())
            hall_filter_count = cmd.get_int("hall_filter", app.hall_tab.k2450_filter_count.get())
            hall_tbm = cmd.get_float("tbm", app.hall_tab.k2450_tbm.get())
            hall_excitation = cmd.get_str("hall_excitation", "cycle")
            hall_excitation = str(hall_excitation).strip().lower()
            time_between = cmd.get_float("time_between", 0.05)

            if hall_excitation == "keep":
                hall_data = measure_hall_continuous(
                    ctx,
                    current_mA=hall_current_mA,
                    nplc=hall_nplc,
                    compliance_v=hall_compliance_v,
                    voltage_range=hall_voltage_range,
                    auto_range=hall_auto_range,
                    filter_count=hall_filter_count,
                    tbm=hall_tbm,
                )
            else:
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

            closed_switch = False
            try:
                _close_active_channel(ctx, app, str(channel))
                closed_switch = True
                _post_switch_summary(ctx, app)

                if time_between > 0:
                    _sleep_with_stop(engine.stop_event, float(time_between))

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
                    tau_idx=int(app.lockin_tab.lockin_time_constant_idx.get()),
                    filter_slope_idx=lockin_filter_idx,
                    frequency=app.lockin_tab.lockin_frequency.get(),
                )
            finally:
                if closed_switch:
                    open_all_channels(ctx)
                    _post_switch_summary(ctx, app)

            result = {**hall_data, **lockin_data}
            ctx.data_mgr.write_row(result, measurement_type="Full")
            _post_hall_result_events(ctx, app, result)
            _post_lockin_result_events(ctx, app, result)
            ctx.ui_bus.post_log("Full measurement recorded")
            ctx.ui_bus.post(W_RESULTS_NEW_POINT, True)

        elif name == "continuous_full_measure":
            hall_voltage_range_raw = cmd.get_str("hall_voltage_range", app.hall_tab.k2450_voltage_range.get())
            hall_voltage_range, hall_auto_range = _parse_voltage_range(
                hall_voltage_range_raw,
                default_raw=str(app.hall_tab.k2450_voltage_range.get()),
            )

            db_oct = int(app.lockin_tab.lockin_filter_slope.get())
            lockin_filter_idx = {6: 0, 12: 1, 18: 2, 24: 3}.get(db_oct, 3)

            lockin_current = app.lockin_tab.lockin_output_current.get()
            lockin_series_resistance = app.lockin_tab.lockin_r_lockin.get()
            lockin_avg = cmd.get_int("lockin_avg", int(app.lockin_tab.lockin_averaging.get()))
            lockin_start_sens = int(app.lockin_tab.lockin_sensitivity_idx.get())
            lockin_use_autorange = cmd.get_bool("lockin_use_autorange", False)
            lockin_use_autophase = cmd.get_bool("lockin_use_autophase", False)
            lockin_sample_delay = cmd.get_float("lockin_sample_delay", 0.05)
            lockin_what = cmd.get_tuple("lockin_what", ("X", "Y", "R", "Theta"))

            hall_current_mA = app.hall_tab.k2450_current.get()
            hall_nplc = cmd.get_float("hall_nplc", app.hall_tab.k2450_nplc.get())
            hall_compliance_v = cmd.get_float("hall_compliance", app.hall_tab.k2450_compliance_v.get())
            hall_filter_count = cmd.get_int("hall_filter", app.hall_tab.k2450_filter_count.get())
            time_between = cmd.get_float("time_between", 0.05)

            hall_data = measure_hall_continuous(
                ctx,
                current_mA=hall_current_mA,
                nplc=hall_nplc,
                compliance_v=hall_compliance_v,
                voltage_range=hall_voltage_range,
                auto_range=hall_auto_range,
                filter_count=hall_filter_count,
                tbm=app.hall_tab.k2450_tbm.get(),
            )

            if time_between > 0:
                _sleep_with_stop(engine.stop_event, float(time_between))

            if lockin_use_autorange or lockin_use_autophase:
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
                    manage_excitation=False,
                    tau_idx=int(app.lockin_tab.lockin_time_constant_idx.get()),
                    filter_slope_idx=lockin_filter_idx,
                    frequency=app.lockin_tab.lockin_frequency.get(),
                )
            else:
                lockin_data = measure_lockin_continuous(
                    ctx,
                    what=lockin_what,
                    avg=lockin_avg,
                    sample_delay=lockin_sample_delay,
                    current=lockin_current,
                    series_resistance=lockin_series_resistance,
                    frequency=app.lockin_tab.lockin_frequency.get(),
                    tau_idx=int(app.lockin_tab.lockin_time_constant_idx.get()),
                )

            result = {**hall_data, **lockin_data}
            ctx.data_mgr.write_row(result, measurement_type="Full")
            _post_hall_result_events(ctx, app, result)
            _post_lockin_result_events(ctx, app, result)
            _post_switch_summary(ctx, app)
            ctx.ui_bus.post_log("Continuous full measurement recorded")
            ctx.ui_bus.post(W_RESULTS_NEW_POINT, True)

        elif name == "set_ppms_field_and_fix_hall":
            target_ppms_oe = float(args[0])
            target_hall_g = float(args[1])
            helm_rate = float(cmd.kwargs.get("helmholtz_rate", 0.1))
            max_current_change_a = float(cmd.kwargs.get("max_current_change", 2.0))

            if max_current_change_a <= 0:
                raise ValueError("max_current_change must be > 0 A")

            set_dyna_field(ctx, target_ppms_oe, rate=10.0, approach="linear")
            wait_for_events(ctx, engine.stop_event, ["field"], additional_time=0)

            _run_hall_fix_loop(
                engine,
                ctx,
                app,
                target_hall_g=target_hall_g,
                helmholtz_rate_g_s=helm_rate,
                max_current_change_a=max_current_change_a,
            )

        elif name == "scan_ppms_field_and_fix_hall":
            start_oe = float(args[0])
            end_oe = float(args[1])
            step_oe = float(args[2])
            target_hall_g = float(args[3])
            rate = float(cmd.kwargs.get("rate", 10.0))
            helm_rate = float(cmd.kwargs.get("helmholtz_rate", 0.1))
            max_current_change_a = float(cmd.kwargs.get("max_current_change", 2.0))

            if max_current_change_a <= 0:
                raise ValueError("max_current_change must be > 0 A")

            for field_oe in _arange(start_oe, end_oe, step_oe):
                engine.check_stop()
                engine.check_pause()

                # Reuse the same logic as set_ppms_field_and_fix_hall
                set_dyna_field(ctx, field_oe, rate=rate, approach="linear")
                wait_for_events(ctx, engine.stop_event, ["field"], additional_time=0)

                _run_hall_fix_loop(
                    engine,
                    ctx,
                    app,
                    target_hall_g=target_hall_g,
                    helmholtz_rate_g_s=helm_rate,
                    max_current_change_a=max_current_change_a,
                )

                if cmd.children:
                    _run_children(engine, ctx, cmd.children, app, parent_line=cmd.line_number)

        # ==============================================================
        # Wait commands
        # ==============================================================
        elif name == "wait_for":
            if not args:
                events = ["temp"]
                additional = 0.0
            else:
                additional = float(args[-1])
                event_tokens = args[:-1]
                events = []
                for token in event_tokens:
                    events.extend([t.strip() for t in token.split(",") if t.strip()])
                if not events:
                    events = ["temp"]
            events = _normalize_wait_events(events)
            wait_for_events(ctx, engine.stop_event, events, additional_time=additional)

        # ==============================================================
        # Lock-in utility commands
        # ==============================================================
        elif name == "auto_gain":
            ctx.ui_bus.post(W_LOCKIN_STATUS, "LockIn: running auto gain")
            sens_idx = int(lockin_auto_gain(ctx))
            app.lockin_tab.lockin_sensitivity_idx.set(sens_idx)
            app.lockin_tab.sens_label.configure(text=app.lockin_tab._sens_text())
            ctx.ui_bus.post(W_LOCKIN_SENSITIVITY, sens_idx)
            ctx.ui_bus.post_log("Lock-in auto gain executed")
            ctx.ui_bus.post_log(f"Lock-in sensitivity index: {sens_idx}")
            ctx.ui_bus.post(W_LOCKIN_STATUS, "LockIn: auto gain completed")
        elif name == "auto_phase":
            ctx.ui_bus.post(W_LOCKIN_STATUS, "LockIn: running auto phase")
            lockin_auto_phase(ctx)
            ctx.ui_bus.post_log("Lock-in auto phase executed")
            ctx.ui_bus.post(W_LOCKIN_STATUS, "LockIn: auto phase completed")
        elif name == "auto_reserve":
            ctx.ui_bus.post(W_LOCKIN_STATUS, "LockIn: running auto reserve")
            lockin_auto_reserve(ctx)
            ctx.ui_bus.post_log("Lock-in auto reserve executed")
            ctx.ui_bus.post(W_LOCKIN_STATUS, "LockIn: auto reserve completed")
        elif name == "set_lockin_time_constant":
            tau_seconds = float(args[0])
            tau_index = _seconds_to_tau_index(tau_seconds)
            set_lockin_time_constant(ctx, tau_index)
            app.lockin_tab.lockin_time_constant_idx.set(tau_index)
            app.lockin_tab.tc_label.configure(text=app.lockin_tab._tc_text())
            ctx.ui_bus.post_log(f"Lock-in time constant set to {tau_seconds} s (idx {tau_index})")
            ctx.ui_bus.post(W_LOCKIN_STATUS, "LockIn: time constant updated")
        elif name == "set_lockin_sensitivity":
            sens_idx = int(float(args[0]))
            set_lockin_sensitivity(ctx, sens_idx)
            app.lockin_tab.lockin_sensitivity_idx.set(sens_idx)
            app.lockin_tab.sens_label.configure(text=app.lockin_tab._sens_text())
            ctx.ui_bus.post(W_LOCKIN_SENSITIVITY, sens_idx)
            ctx.ui_bus.post_log(f"Set Lock-in sensitivity index: {sens_idx}")
            ctx.ui_bus.post(W_LOCKIN_STATUS, "LockIn: sensitivity updated")
        elif name == "set_lockin_filter":
            db_oct = int(float(args[0]))
            filter_idx = {6: 0, 12: 1, 18: 2, 24: 3}.get(db_oct, db_oct)
            set_lockin_filter(ctx, int(filter_idx))
            ctx.ui_bus.post_log(f"Set Lock-in filter: {db_oct} dB/oct")
            ctx.ui_bus.post(W_LOCKIN_STATUS, "LockIn: filter updated")
        elif name == "set_lockin_frequency":
            freq = float(args[0])
            set_lockin_frequency(ctx, freq)
            app.lockin_tab.lockin_frequency.set(freq)
            ctx.ui_bus.post_log(f"Set Lock-in frequency: {freq:.4f} Hz")
            ctx.ui_bus.post(W_LOCKIN_STATUS, "LockIn: frequency updated")
        elif name == "set_lockin_current":
            r = cmd.get_float("series_resistance", app.lockin_tab.lockin_r_lockin.get())
            current_a = float(args[0])
            applied_voltage = set_lockin_current(ctx, current_a, series_resistance=float(r))
            app.lockin_tab.lockin_output_current.set(current_a)
            app.lockin_tab.lockin_r_lockin.set(float(r))
            ctx.ui_bus.post(W_LOCKIN_OUTPUT_VOLTAGE, applied_voltage)
            ctx.ui_bus.post_log(
                f"Set Lock-in current: {current_a:.3e} A (R={float(r):.2f} Ω, Vout={applied_voltage:.4f} V)"
            )
            ctx.ui_bus.post(W_LOCKIN_STATUS, "LockIn: current updated")

        # ==============================================================
        # Switch commands
        # ==============================================================
        elif name == "open_all_channels":
            open_all_channels(ctx)
            app.active_channel = None
            _post_switch_summary(ctx, app)
            ctx.ui_bus.post_log("open_all_channels executed")

        elif name == "close_channel":
            token = str(args[0]).strip().lower()
            if token in app.channels:
                _close_active_channel(ctx, app, token)
                _post_switch_summary(ctx, app)
                ctx.ui_bus.post_log(f"close_channel {token} executed")
            else:
                raise ValueError(f"close_channel requires channel name in: {', '.join(app.channels)}")

        elif name == "configure_channel":
            ch = args[0]
            ip, vp, vm, im = int(args[1]), int(args[2]), int(args[3]), int(args[4])
            configure_channel(ctx, ch, ip, vp, vm, im)
            ctx.data_mgr.append_note(
                f"Reconfigured channel {ch}: I+={ip}, V+={vp}, V-={vm}, I-={im}"
            )
            if ch in app.channel_configs:
                app.channel_configs[ch]["I+"].set(ip)
                app.channel_configs[ch]["V+"].set(vp)
                app.channel_configs[ch]["V-"].set(vm)
                app.channel_configs[ch]["I-"].set(im)
            app.active_channel = ch
            _post_switch_summary(ctx, app)
            ctx.ui_bus.post_log(
                f"configure_channel {ch} executed: I+={ip}, V+={vp}, V-={vm}, I-={im}"
            )

        # ==============================================================
        # Data file commands
        # ==============================================================
        elif name == "initialize_data_file":
            directory = cmd.get_str("directory", None)
            filename = cmd.get_str("filename", None)
            append = _parse_bool(cmd.get_str("append", None), default=False)
            path = ctx.data_mgr.initialize_file(directory=directory, filename=filename, append=append)
            if path is None:
                raise RuntimeError("Failed to initialize data file")
            ctx.ui_bus.post(W_RESULTS_NEW_POINT, True)
            ctx.ui_bus.post_log(f"Data file initialized: {path}")

        elif name == "add_note":
            note = " ".join(args) if args else ""
            ctx.data_mgr.set_note(note)
            ctx.ui_bus.post_log(f"Note: {note}")

        # ==============================================================
        # Loop / scan commands
        # ==============================================================
        elif name in LOOP_COMMANDS:
            _run_loop(engine, ctx, cmd, app)

        elif name == "test":
            ctx.ui_bus.post_log("Test command executed.")

        elif name == "run_saved_script":
            filename = args[0] if args else ""
            _run_saved_script(engine, ctx, app, filename)

        else:
            ctx.ui_bus.post_log(f"Unknown command: {name}")

    except StopRequested:
        raise
    except Exception as exc:
        if name in ("measure_lockin", "continuous_measure_lockin", "full_measure"):
            ctx.ui_bus.post(W_LED_LOCKIN, False)
        ctx.ui_bus.post_log(f"Command error ({name}): {exc}")
        if _is_disconnect_error(exc):
            ctx.ui_bus.post_log("Script aborted due to instrument disconnect.")
            engine.request_stop()
            raise StopRequested()
        logger.exception("Script command '%s' failed", name)
        if _FAIL_FAST_COMMAND_ERRORS:
            raise


# ======================================================================
# Loop execution
# ======================================================================
def _run_loop(
    engine: ExperimentEngine,
    ctx: MeasurementContext,
    cmd: ParsedCommand,
    app: "MeasureApp",
) -> None:
    """Execute a scan/sweep loop command with its children."""
    args = cmd.args
    name = cmd.name

    if name == "scan_dyna_field":
        start, end, step, rate = float(args[0]), float(args[1]), float(args[2]), float(args[3])
        approach = args[4] if len(args) > 4 else "linear"
        values = _arange(start, end, step)
        for val in values:
            engine.check_stop()
            engine.check_pause()
            _post_dyna_setpoint(ctx, field_oe=val, field_rate_oe_s=rate, field_mode=approach)
            set_dyna_field(ctx, val, rate, approach)
            # Wait for stability
            wait_for_events(ctx, engine.stop_event, ["field"], additional_time=0)
            # Run children
            _run_children(engine, ctx, cmd.children, app, parent_line=cmd.line_number)

    elif name == "scan_dyna_temp":
        start, end, step, rate = float(args[0]), float(args[1]), float(args[2]), float(args[3])
        approach = args[4] if len(args) > 4 else "fast_settle"
        values = _arange(start, end, step)
        if values:
            _confirm_dyna_cooling_or_abort(
                engine,
                ctx,
                app,
                target_temp_k=min(values),
                command_name=name,
            )
        for val in values:
            engine.check_stop()
            engine.check_pause()
            _post_dyna_setpoint(ctx, temp_k=val, temp_rate_k_min=rate, temp_mode=approach)
            set_dyna_temp(ctx, val, rate, approach)
            wait_for_events(ctx, engine.stop_event, ["temp"], additional_time=0)
            _run_children(engine, ctx, cmd.children, app, parent_line=cmd.line_number)

    elif name == "sweep_dyna_field":
        start, end, rate = float(args[0]), float(args[1]), float(args[2])
        gap_time = float(cmd.kwargs.get("gap_time", args[3] if len(args) > 3 else 0.0))

        _post_dyna_setpoint(ctx, field_oe=start, field_rate_oe_s=rate, field_mode="linear")
        set_dyna_field(ctx, start, rate, "linear")
        wait_for_events(ctx, engine.stop_event, ["field"], additional_time=0)
        _run_children(engine, ctx, cmd.children, app, parent_line=cmd.line_number)

        _post_dyna_setpoint(ctx, field_oe=end, field_rate_oe_s=rate, field_mode="linear")
        set_dyna_field(ctx, end, rate, "linear")
        while not engine.stop_event.is_set():
            try:
                err, _field, status = ctx.bus.execute("dyna", "get_field")
                if int(status) in (1, 4):
                    break
            except Exception:
                break
            _run_children(engine, ctx, cmd.children, app, parent_line=cmd.line_number)
            if gap_time > 0:
                engine.interruptible_sleep(gap_time)

        _run_children(engine, ctx, cmd.children, app, parent_line=cmd.line_number)

    elif name == "sweep_dyna_temp":
        start, end, rate = float(args[0]), float(args[1]), float(args[2])
        gap_time = float(cmd.kwargs.get("gap_time", args[3] if len(args) > 3 else 0.0))

        _confirm_dyna_cooling_or_abort(
            engine,
            ctx,
            app,
            target_temp_k=min(start, end),
            command_name=name,
        )

        _post_dyna_setpoint(ctx, temp_k=start, temp_rate_k_min=rate, temp_mode="fast_settle")
        set_dyna_temp(ctx, start, rate, "fast_settle")
        wait_for_events(ctx, engine.stop_event, ["temp"], additional_time=0)
        _run_children(engine, ctx, cmd.children, app, parent_line=cmd.line_number)

        _post_dyna_setpoint(ctx, temp_k=end, temp_rate_k_min=rate, temp_mode="fast_settle")
        set_dyna_temp(ctx, end, rate, "fast_settle")
        while not engine.stop_event.is_set():
            try:
                err, _temp, status_num, _status_name = ctx.bus.execute("dyna", "get_temperature")
                if int(status_num) == 1:
                    break
            except Exception:
                break
            _run_children(engine, ctx, cmd.children, app, parent_line=cmd.line_number)
            if gap_time > 0:
                engine.interruptible_sleep(gap_time)

        _run_children(engine, ctx, cmd.children, app, parent_line=cmd.line_number)

    elif name == "scan_helmholtz_field":
        start, end, step, rate = float(args[0]), float(args[1]), float(args[2]), float(args[3])
        values = _arange(start, end, step)
        for val in values:
            engine.check_stop()
            engine.check_pause()
            _post_helmholtz_setpoint(app, val, rate)
            app.helmholtz.set_field(val, rate_mA_per_s=rate)
            app.helmholtz.ramp_to_target(engine.stop_event)
            _run_children(engine, ctx, cmd.children, app, parent_line=cmd.line_number)

    elif name == "sweep_helmholtz_field":
        start, end, rate = float(args[0]), float(args[1]), float(args[2])
        gap_time = float(cmd.kwargs.get("gap_time", args[3] if len(args) > 3 else 0.0))

        _post_helmholtz_setpoint(app, start, rate)
        # Move to start point first
        app.helmholtz.set_field(start, rate_mA_per_s=rate)
        app.helmholtz.ramp_to_target(engine.stop_event)

        # Initial measurement at start
        _run_children(engine, ctx, cmd.children, app, parent_line=cmd.line_number)

        # Start continuous sweep to end point
        _post_helmholtz_setpoint(app, end, rate)
        app.helmholtz.set_field(end, rate_mA_per_s=rate)
        if hasattr(app.helmholtz, "is_enabled") and not bool(getattr(app.helmholtz, "is_enabled")):
            app.helmholtz.enable_output()

        sample_interval = max(0.0, gap_time)
        ramp_done = threading.Event()

        def _ramp_worker() -> None:
            tick_dt = 0.05
            try:
                while not engine.stop_event.is_set():
                    still = app.helmholtz.service_tick(dt=tick_dt)
                    app.helmholtz.apply_tick()
                    if not still:
                        break
                    if engine.stop_event.wait(timeout=tick_dt):
                        break
            finally:
                ramp_done.set()

        ramp_thread = threading.Thread(target=_ramp_worker, daemon=True, name="helmholtz-sweep-ramp")
        ramp_thread.start()

        now = time.monotonic()
        next_sample = (now + sample_interval) if sample_interval > 0 else now

        while not engine.stop_event.is_set() and not ramp_done.is_set():
            engine.check_stop()
            engine.check_pause()

            now = time.monotonic()
            if now >= next_sample:
                _run_children(engine, ctx, cmd.children, app, parent_line=cmd.line_number)
                next_sample = now + sample_interval if sample_interval > 0 else now
            engine.interruptible_sleep(min(0.05, sample_interval) if sample_interval > 0 else 0.05)

        ramp_done.wait(timeout=1.0)

        # Final measurement at endpoint
        _run_children(engine, ctx, cmd.children, app, parent_line=cmd.line_number)

    elif name == "time_sweep":
        sweep_time_s = max(0.0, float(args[0]))
        time_gap_s = max(0.0, float(args[1]))

        start_t = time.monotonic()
        while not engine.stop_event.is_set():
            engine.check_stop()
            engine.check_pause()

            elapsed = time.monotonic() - start_t
            if elapsed >= sweep_time_s:
                break

            _run_children(engine, ctx, cmd.children, app, parent_line=cmd.line_number)
            if time_gap_s > 0:
                engine.interruptible_sleep(time_gap_s)

    elif name == "for_loop":
        iterations = max(0, int(float(args[0])))
        for _ in range(iterations):
            engine.check_stop()
            engine.check_pause()
            _run_children(engine, ctx, cmd.children, app, parent_line=cmd.line_number)


def _run_children(
    engine: ExperimentEngine,
    ctx: MeasurementContext,
    children: list[ParsedCommand],
    app: "MeasureApp",
    parent_line: int = 0,
) -> None:
    """Execute loop body commands."""
    for child in children:
        engine.check_stop()
        engine.check_pause()
        engine.set_progress(
            child.line_number,
            max(engine.total_lines, 1),
            loop_level=1,
            parent_line=parent_line,
        )
        _dispatch(engine, ctx, child, app)
        engine.interruptible_sleep(0.1)


def _run_saved_script(
    engine: ExperimentEngine,
    ctx: MeasurementContext,
    app: "MeasureApp",
    filename: str,
) -> None:
    """Load and execute a script file."""
    raw_path = Path(filename)
    stack: list[Path] = getattr(engine, "_script_stack", [])

    if raw_path.is_absolute():
        path = raw_path.resolve()
    else:
        base_dir = stack[-1].parent if stack else Path.cwd()
        path = (base_dir / raw_path).resolve()

    if not path.exists():
        raise FileNotFoundError(f"Script file not found: {path}")

    if path in stack:
        chain = " -> ".join(str(p) for p in [*stack, path])
        raise RuntimeError(f"run_saved_script recursion cycle detected: {chain}")

    if len(stack) >= _MAX_NESTED_SCRIPT_DEPTH:
        raise RuntimeError(
            f"run_saved_script nesting exceeds max depth {_MAX_NESTED_SCRIPT_DEPTH}"
        )

    text = path.read_text(encoding="utf-8")
    from v3.core.script_parser import ScriptParser, ScriptValidator

    parser = getattr(app, "parser", ScriptParser())
    validator = getattr(app, "validator", ScriptValidator())
    commands = parser.parse(text)
    connected = set(app.bus.connected_instruments()) if hasattr(app, "bus") else None
    errors = validator.validate(commands, connected_instruments=connected)
    real_errors = [e for e in errors if getattr(e, "severity", "error") == "error"]
    if real_errors:
        msg = "; ".join(f"L{e.line_number}: {e.message}" for e in real_errors)
        raise RuntimeError(f"Nested script validation failed ({path.name}): {msg}")

    warnings = [e for e in errors if getattr(e, "severity", "error") == "warning"]
    for warning in warnings:
        ctx.ui_bus.post_log(f"Nested script warning ({path.name}) L{warning.line_number}: {warning.message}")

    stack.append(path)
    setattr(engine, "_script_stack", stack)
    try:
        run_commands(engine, ctx, commands, app)
    finally:
        stack.pop()


def _arange(start: float, end: float, step: float) -> list[float]:
    """Generate a list of values from start to end (inclusive) by step."""
    if step == 0:
        return [start]
    values = []
    if start <= end:
        step = abs(step)
        v = start
        while v <= end + step * 0.001:
            values.append(v)
            v += step
    else:
        step = -abs(step)
        v = start
        while v >= end + step * 0.001:
            values.append(v)
            v += step
    return values
