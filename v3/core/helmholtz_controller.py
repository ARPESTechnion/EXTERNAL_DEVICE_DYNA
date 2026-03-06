"""
v3.core.helmholtz_controller  —  Helmholtz coil ramp service.

Replaces V2's ``KeithleyGUI`` class whose ``update_current()`` ran on the
UI thread every 100 ms.  This controller is called from the **worker
thread** (or any non-UI thread) and drives the ramp step-by-step.

Architecture
------------
* :meth:`set_field` — compute the target current and store it.
* :meth:`ramp_to_target` — blocking call that ramps one tick at a time
  with interruptible delays, checking compliance at each step.
* :meth:`service_tick` — advance one ramp step (non-blocking).
  Called by ``update_ui()`` on the main thread to drive the ramp
  during continuous sweeps where the worker just waits for arrival.
* :meth:`wait_until_stable` — block until actual ≈ target, with
  stop-event support.

Thread safety
-------------
Internal state is protected by ``_lock`` for the software model.
All hardware calls go through :class:`InstrumentBus` which provides
its own per-instrument lock for the Keithley 2600.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import TYPE_CHECKING

from v3.core.calibration import CalibrationConfig
from v3.core.constants import (
    DEFAULT_COMPLIANCE_V,
    DEFAULT_RAMP_RATE_mA_per_s,
    HELMHOLTZ_MAX_RAMP_RATE_mA_per_s,
    HELMHOLTZ_MAX_CURRENT_A,
    INST_KEITHLEY2600,
)
from v3.core.ui_events import (
    UIEventBus,
    W_HELMHOLTZ_CURRENT_A,
    W_HELMHOLTZ_CURRENT_B,
    W_HELMHOLTZ_FIELD,
    W_HELMHOLTZ_RAMPING,
    W_HELMHOLTZ_RESISTANCE_A,
    W_HELMHOLTZ_RESISTANCE_B,
)

if TYPE_CHECKING:
    from v3.core.instrument_bus import InstrumentBus

logger = logging.getLogger(__name__)

_KEITHLEY_CURRENT_RES_A = 1e-9


def _round_to(value: float, resolution: float) -> float:
    if resolution <= 0:
        return float(value)
    return round(float(value) / resolution) * resolution


# ============================================================================
# Exceptions
# ============================================================================
class ComplianceError(RuntimeError):
    """Raised when a compliance voltage limit is exceeded."""


class HelmholtzSafetyError(RuntimeError):
    """Raised when a current setpoint exceeds safety limits."""


# ============================================================================
# HelmholtzController
# ============================================================================
class HelmholtzController:
    """
    Software model + hardware driver for the Helmholtz coil system.

    Parameters
    ----------
    bus : InstrumentBus
        Thread-safe instrument access.
    ui_bus : UIEventBus
        For posting display updates.
    calibration : CalibrationConfig, optional
        Field↔current conversion parameters.
    """

    def __init__(
        self,
        bus: "InstrumentBus",
        ui_bus: UIEventBus,
        calibration: CalibrationConfig | None = None,
    ) -> None:
        self._bus = bus
        self._ui_bus = ui_bus
        self._cal = calibration or CalibrationConfig()

        # Software model state (protected by _lock)
        self._lock = threading.Lock()
        self._target_current: float = 0.0        # per-coil target (A)
        self._actual_a: float = 0.0               # actual current ch A
        self._actual_b: float = 0.0               # actual current ch B
        self._rate: float = DEFAULT_RAMP_RATE_mA_per_s / 1000.0  # A/s
        self._compliance_v: float = DEFAULT_COMPLIANCE_V
        self._enabled: bool = False
        self._is_ramping: bool = False
        self._error_triggered: bool = False
        self._last_res_a: float | None = None
        self._last_res_b: float | None = None
        self._last_applied_a: float | None = None
        self._last_applied_b: float | None = None

    # ------------------------------------------------------------------
    # Read-only properties
    # ------------------------------------------------------------------
    @property
    def target_current(self) -> float:
        """Per-coil target current (A)."""
        return self._target_current

    @property
    def actual_current_a(self) -> float:
        return self._actual_a

    @property
    def actual_current_b(self) -> float:
        return self._actual_b

    @property
    def total_current(self) -> float:
        """Sum of both channel currents (A)."""
        return self._actual_a + self._actual_b

    @property
    def field_gauss(self) -> float:
        """Current magnetic field based on actual current (Gauss)."""
        return self._cal.current_to_field(self.total_current)

    @property
    def is_ramping(self) -> bool:
        return self._is_ramping

    @property
    def is_enabled(self) -> bool:
        return self._enabled

    @property
    def error_triggered(self) -> bool:
        return self._error_triggered

    @property
    def calibration(self) -> CalibrationConfig:
        return self._cal

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------
    def set_ramp_rate(self, rate_mA_per_s: float) -> None:
        """Set the ramp rate in mA/s.  Converted internally to A/s."""
        rate = max(0.01, min(float(rate_mA_per_s), HELMHOLTZ_MAX_RAMP_RATE_mA_per_s))
        with self._lock:
            self._rate = rate / 1000.0

    def set_compliance(self, voltage: float) -> None:
        """Set compliance voltage limit."""
        with self._lock:
            self._compliance_v = voltage

    def set_calibration(self, cal: CalibrationConfig) -> None:
        """Update calibration.  Typically called once at startup."""
        with self._lock:
            self._cal = cal

    # ------------------------------------------------------------------
    # Target setting
    # ------------------------------------------------------------------
    def set_field(self, field_gauss: float, rate_mA_per_s: float | None = None) -> None:
        """
        Set the target Helmholtz field.

        Parameters
        ----------
        field_gauss : float
            Target field in Gauss.
        rate_mA_per_s : float, optional
            Ramp rate override (mA/s).
        """
        total_current = self._cal.field_to_current(field_gauss)
        per_coil = self._cal.coil_current(total_current)

        if abs(total_current) > HELMHOLTZ_MAX_CURRENT_A:
            raise HelmholtzSafetyError(
                f"Requested field {field_gauss} G requires {total_current:.3f} A "
                f"total, exceeding limit of {HELMHOLTZ_MAX_CURRENT_A} A."
            )

        with self._lock:
            self._target_current = per_coil
            if rate_mA_per_s is not None:
                self._rate = rate_mA_per_s / 1000.0
            self._error_triggered = False

        logger.info(
            "Helmholtz target: %.4f A/coil (%.2f G) at %.1f mA/s",
            per_coil, field_gauss, (rate_mA_per_s or self._rate * 1000)
        )

    def set_current(self, per_coil_current: float) -> None:
        """
        Set target current per coil directly (A).

        Validates that total current doesn't exceed safety limits.
        """
        total = abs(per_coil_current) * 2
        if total > HELMHOLTZ_MAX_CURRENT_A:
            raise HelmholtzSafetyError(
                f"Requested {per_coil_current:.3f} A/coil = {total:.3f} A total, "
                f"exceeding limit of {HELMHOLTZ_MAX_CURRENT_A} A."
            )
        with self._lock:
            self._target_current = per_coil_current
            self._error_triggered = False

    # ------------------------------------------------------------------
    # Output enable/disable
    # ------------------------------------------------------------------
    def enable_output(self) -> None:
        """Enable the Keithley 2600 output on both channels."""
        if not self._bus.is_connected(INST_KEITHLEY2600):
            logger.warning("Cannot enable Helmholtz: Keithley 2600 not connected")
            return

        inst = self._bus.get_raw(INST_KEITHLEY2600)

        # Set compliance with method-name fallbacks (mock vs real driver)
        for ch in ("a", "b"):
            self._bus.execute(
                INST_KEITHLEY2600,
                "set_current",
                self._actual_a if ch == "a" else self._actual_b,
                Ch=ch,
            )

            if inst is not None and hasattr(inst, "set_compliance"):
                self._bus.execute(INST_KEITHLEY2600, "set_compliance", self._compliance_v, Ch=ch)
            elif inst is not None and hasattr(inst, "set_voltage_compliance"):
                self._bus.execute(INST_KEITHLEY2600, "set_voltage_compliance", self._compliance_v, Ch=ch)

            # Apply current source mode with compliance where supported
            if inst is not None and hasattr(inst, "apply_current"):
                self._bus.execute(
                    INST_KEITHLEY2600,
                    "apply_current",
                    current_range=None,
                    compliance_voltage=self._compliance_v,
                    Ch=ch,
                )

            if inst is not None and hasattr(inst, "enable_source"):
                self._bus.execute(INST_KEITHLEY2600, "enable_source", Ch=ch)

        with self._lock:
            self._enabled = True
        logger.info("Helmholtz output enabled.")

    def disable_output(self) -> None:
        """Disable output — sets current to zero and turns off output."""
        if self._bus.is_connected(INST_KEITHLEY2600):
            try:
                inst = self._bus.get_raw(INST_KEITHLEY2600)
                self._bus.execute(INST_KEITHLEY2600, "set_current", 0, Ch="a")
                self._bus.execute(INST_KEITHLEY2600, "set_current", 0, Ch="b")
                if inst is not None and hasattr(inst, "disable_output"):
                    self._bus.execute(INST_KEITHLEY2600, "disable_output", Ch="a")
                    self._bus.execute(INST_KEITHLEY2600, "disable_output", Ch="b")
                else:
                    self._bus.execute(INST_KEITHLEY2600, "disable_source", Ch="a")
                    self._bus.execute(INST_KEITHLEY2600, "disable_source", Ch="b")
            except Exception:  # noqa: BLE001
                logger.exception("Failed to disable Helmholtz output")

        with self._lock:
            self._enabled = False
            self._actual_a = 0.0
            self._actual_b = 0.0
            self._is_ramping = False
            self._last_res_a = None
            self._last_res_b = None
            self._last_applied_a = None
            self._last_applied_b = None

        # Push immediate UI refresh so displays update when Disable is pressed
        self._ui_bus.post(W_HELMHOLTZ_CURRENT_A, 0.0)
        self._ui_bus.post(W_HELMHOLTZ_CURRENT_B, 0.0)
        self._ui_bus.post(W_HELMHOLTZ_FIELD, 0.0)
        self._ui_bus.post(W_HELMHOLTZ_RAMPING, False)
        self._ui_bus.post(W_HELMHOLTZ_RESISTANCE_A, float("nan"))
        self._ui_bus.post(W_HELMHOLTZ_RESISTANCE_B, float("nan"))
        logger.info("Helmholtz output disabled.")

    # ------------------------------------------------------------------
    # Ramp algorithm  —  one tick
    # ------------------------------------------------------------------
    def service_tick(self, dt: float = 0.1) -> bool:
        """
        Advance the ramp by one time-step.

        Parameters
        ----------
        dt : float
            Time since last tick (seconds).  Default 100 ms.

        Returns
        -------
        bool
            True if still ramping, False if at target.

        This is the pure-logic equivalent of V2's ``update_current()``.
        Does NOT call hardware — use :meth:`apply_tick` for that.
        """
        auto_disable_zero = False
        with self._lock:
            if not self._enabled:
                self._is_ramping = False
                return False

            max_step = self._rate * dt

            # Channel A
            delta_a = self._target_current - self._actual_a
            if abs(delta_a) > 1e-7:
                step_a = min(max_step, abs(delta_a))
                self._actual_a += step_a if delta_a > 0 else -step_a

            # Channel B
            delta_b = self._target_current - self._actual_b
            if abs(delta_b) > 1e-7:
                step_b = min(max_step, abs(delta_b))
                self._actual_b += step_b if delta_b > 0 else -step_b

            # Check if still ramping AFTER applying steps
            still_a = abs(self._target_current - self._actual_a) > 1e-7
            still_b = abs(self._target_current - self._actual_b) > 1e-7
            ramping = still_a or still_b

            self._is_ramping = ramping
            at_zero_target = abs(self._target_current) <= 1e-7
            at_zero_actual = abs(self._actual_a) <= 1e-7 and abs(self._actual_b) <= 1e-7
            auto_disable_zero = (not ramping) and at_zero_target and at_zero_actual

        if auto_disable_zero:
            self.disable_output()
            return False

        return ramping

    def apply_tick(self) -> None:
        """
        Write the current software-model values to hardware and check
        compliance.

        Call after :meth:`service_tick` when the hardware is connected.
        """
        if not self._bus.is_connected(INST_KEITHLEY2600):
            return

        a, b = self._actual_a, self._actual_b
        a_cmd = _round_to(a, _KEITHLEY_CURRENT_RES_A)
        b_cmd = _round_to(b, _KEITHLEY_CURRENT_RES_A)
        compliance = self._compliance_v

        # Avoid redundant writes when values have not changed.
        write_eps = 1e-9
        skip_write = (
            self._last_applied_a is not None
            and self._last_applied_b is not None
            and abs(a - self._last_applied_a) <= write_eps
            and abs(b - self._last_applied_b) <= write_eps
        )

        if not skip_write:
            try:
                self._bus.execute(INST_KEITHLEY2600, "set_current", a_cmd, Ch="a")
                self._bus.execute(INST_KEITHLEY2600, "apply_current", a_cmd, compliance, Ch="a")
                self._bus.execute(INST_KEITHLEY2600, "set_current", b_cmd, Ch="b")
                self._bus.execute(INST_KEITHLEY2600, "apply_current", b_cmd, compliance, Ch="b")
                self._last_applied_a = a
                self._last_applied_b = b
            except Exception:  # noqa: BLE001
                logger.exception("Failed to apply Helmholtz current")
                return

        # Resistance/compliance check only when current is non-zero
        eps_a = 1e-6
        if abs(a) <= eps_a and abs(b) <= eps_a:
            with self._lock:
                self._last_res_a = None
                self._last_res_b = None
            self._ui_bus.post(W_HELMHOLTZ_RESISTANCE_A, float("nan"))
            self._ui_bus.post(W_HELMHOLTZ_RESISTANCE_B, float("nan"))
        else:
            try:
                res_a = float(self._bus.execute(INST_KEITHLEY2600, "get_resistance", Ch="a"))
                res_b = float(self._bus.execute(INST_KEITHLEY2600, "get_resistance", Ch="b"))
                with self._lock:
                    self._last_res_a = res_a
                    self._last_res_b = res_b
                self._ui_bus.post(W_HELMHOLTZ_RESISTANCE_A, res_a)
                self._ui_bus.post(W_HELMHOLTZ_RESISTANCE_B, res_b)

                if abs(a * res_a) > compliance or abs(b * res_b) > compliance:
                    logger.error(
                        "Compliance exceeded! a=%.4f×%.2f=%.2f V, b=%.4f×%.2f=%.2f V (limit %.1f V)",
                        a, res_a, a * res_a, b, res_b, b * res_b, compliance,
                    )
                    self.disable_output()
                    with self._lock:
                        self._error_triggered = True
                    self._ui_bus.post_log(
                        "⚠ Helmholtz compliance exceeded — output disabled!"
                    )
            except Exception:  # noqa: BLE001
                logger.exception("Compliance check failed")

        # Post UI updates
        total = a + b
        field = self._cal.current_to_field(total)
        self._ui_bus.post(W_HELMHOLTZ_CURRENT_A, a)
        self._ui_bus.post(W_HELMHOLTZ_CURRENT_B, b)
        self._ui_bus.post(W_HELMHOLTZ_FIELD, field)
        self._ui_bus.post(W_HELMHOLTZ_RAMPING, self._is_ramping)

    def read_resistances(self) -> tuple[float, float]:
        """Read coil resistances from hardware. Returns (res_a, res_b)."""
        if not self._bus.is_connected(INST_KEITHLEY2600):
            return (0.0, 0.0)

        # V2 semantics: do not measure resistance when disabled or at zero current
        with self._lock:
            enabled = self._enabled
            a = self._actual_a
            b = self._actual_b
        if (not enabled) or (abs(a) <= 1e-9 and abs(b) <= 1e-9):
            with self._lock:
                self._last_res_a = None
                self._last_res_b = None
            self._ui_bus.post(W_HELMHOLTZ_RESISTANCE_A, float("nan"))
            self._ui_bus.post(W_HELMHOLTZ_RESISTANCE_B, float("nan"))
            return (float("nan"), float("nan"))

        try:
            ra = self._bus.execute(INST_KEITHLEY2600, "get_resistance", Ch="a")
            rb = self._bus.execute(INST_KEITHLEY2600, "get_resistance", Ch="b")
            with self._lock:
                self._last_res_a = float(ra)
                self._last_res_b = float(rb)
            self._ui_bus.post(W_HELMHOLTZ_RESISTANCE_A, ra)
            self._ui_bus.post(W_HELMHOLTZ_RESISTANCE_B, rb)
            return (ra, rb)
        except Exception:  # noqa: BLE001
            logger.exception("Failed to read Helmholtz resistances")
            return (0.0, 0.0)

    # ------------------------------------------------------------------
    # Blocking ramp  (called from worker thread)
    # ------------------------------------------------------------------
    def ramp_to_target(
        self,
        stop_event: threading.Event,
        tick_interval: float = 0.1,
    ) -> None:
        """
        Ramp to the current target, blocking until complete or stopped.

        Parameters
        ----------
        stop_event : threading.Event
            Checked between ticks; if set, returns early.
        tick_interval : float
            Time between ramp steps (seconds).

        Raises
        ------
        ComplianceError
            If compliance is exceeded during the ramp.
        """
        if not self._enabled:
            self.enable_output()

        while True:
            if stop_event.is_set():
                return

            still_ramping = self.service_tick(dt=tick_interval)
            self.apply_tick()

            if self._error_triggered:
                raise ComplianceError("Compliance exceeded during ramp")

            if not still_ramping:
                return

            # Interruptible sleep
            if stop_event.wait(timeout=tick_interval):
                return

    def wait_until_stable(
        self,
        stop_event: threading.Event,
        tolerance_frac: float = 0.01,
        min_tolerance_a: float = 0.001,
        required_stable: int = 2,
        max_wait_s: float = 300.0,
        poll_interval: float = 1.0,
    ) -> bool:
        """
        Wait until actual current matches target within tolerance.

        Parameters
        ----------
        stop_event : threading.Event
            For cancellation.
        tolerance_frac : float
            Fractional tolerance on per-coil target.
        min_tolerance_a : float
            Minimum absolute tolerance (A).
        required_stable : int
            Consecutive stable readings needed.
        max_wait_s : float
            Maximum wait time (seconds).
        poll_interval : float
            Time between checks (seconds).

        Returns
        -------
        bool
            True if stable was reached, False on timeout or stop.
        """
        tol = max(abs(self._target_current) * tolerance_frac, min_tolerance_a)
        stable_count = 0
        deadline = time.monotonic() + max_wait_s

        while time.monotonic() < deadline:
            if stop_event.is_set():
                return False

            # Drive one tick to keep ramping
            self.service_tick()
            self.apply_tick()

            a_ok = abs(self._actual_a - self._target_current) <= tol
            b_ok = abs(self._actual_b - self._target_current) <= tol

            if a_ok and b_ok:
                stable_count += 1
                if stable_count >= required_stable:
                    return True
            else:
                stable_count = 0

            if stop_event.wait(timeout=poll_interval):
                return False

        logger.warning("Helmholtz stability timeout after %.0f s", max_wait_s)
        return False

    # ------------------------------------------------------------------
    # Snapshot (for data recording)
    # ------------------------------------------------------------------
    def snapshot(self) -> dict[str, float | None]:
        """
        Return current Helmholtz state as a data dict suitable for
        DataManager.write_row().
        """
        with self._lock:
            total = self._actual_a + self._actual_b
            return {
                "Helmholtz_Current": total,
                "Helmholtz_Field": self._cal.current_to_field(total),
                "Helmholtz_Resistance_A": self._last_res_a,
                "Helmholtz_Resistance_B": self._last_res_b,
            }
