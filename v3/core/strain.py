"""
v3.core.strain  -  Shared strain-control helpers and hardware/mock controllers.

This module keeps the temperature-dependent voltage limit logic, bridge
measurement retries, and force conversion in one place so the GUI and
script runner can use the same behavior in both mock and real mode.
"""

from __future__ import annotations

import logging
import math
import random
import time
from dataclasses import dataclass
from typing import Any

from v3.core.constants import STRAIN_METER_ADDRESS, STRAIN_RP100_ADDRESS

logger = logging.getLogger(__name__)


def generate_voltage_list(v0: float, vf: float, step: float) -> list[tuple[float, float]]:
    """Generate applied strain-voltage pairs for channel 1 and 2."""

    start = float(v0)
    stop = float(vf)
    step = float(step)
    if not math.isfinite(start) or not math.isfinite(stop) or not math.isfinite(step):
        raise ValueError("Strain scan values must be finite")
    if step == 0:
        raise ValueError("Strain scan step must be non-zero")

    direction = 1.0 if stop >= start else -1.0
    increment = abs(step) * direction
    values: list[tuple[float, float]] = []
    current = start
    tolerance = abs(increment) * 1e-9 + 1e-12

    if direction > 0:
        comparator = lambda value: value <= stop + tolerance
    else:
        comparator = lambda value: value >= stop - tolerance

    while comparator(current):
        current_rounded = round(current, 12)
        values.append((current_rounded, round(-current_rounded, 12)))
        current += increment

    return values


def _temperature_voltage_limits(temperature_k: float) -> tuple[float, float]:
    temperature_k = float(temperature_k)
    if temperature_k > 100:
        v_max = 120.0
    elif temperature_k < 4:
        v_max = 200.0
    else:
        v_max = (-4.0 / 5.0) * temperature_k + 200.0

    if temperature_k > 225:
        v_min = -20.0
    elif temperature_k < 4:
        v_min = -200.0
    else:
        v_min = (4.0 / 5.0) * temperature_k - 200.0

    return v_min, v_max


@dataclass
class StrainReading:
    ch1_voltage: float
    ch2_voltage: float
    capacitance: float
    loss: float
    force: float


class BaseStrainController:
    """Shared behavior for the real and mock strain controllers."""

    def __init__(self) -> None:
        self.temperature: float = 300.0
        self.connected: bool = False
        self.pzt_cntrl_active: bool = False
        self.last_voltage_ch1: float = 0.0
        self.last_voltage_ch2: float = 0.0
        self.last_capacitance: float | None = None
        self.last_loss: float | None = None
        self.last_force: float | None = None

    def set_temperature(self, temperature_k: float | None) -> None:
        if temperature_k is None:
            return
        try:
            value = float(temperature_k)
        except Exception:
            return
        if math.isfinite(value):
            self.temperature = value

    def _resolved_temperature(self, temperature_k: float | None = None) -> float:
        if temperature_k is None:
            return float(self.temperature)
        try:
            value = float(temperature_k)
        except Exception:
            return float(self.temperature)
        return value if math.isfinite(value) else float(self.temperature)

    def _safe_disconnect(self) -> None:
        try:
            if self.connected or self.pzt_cntrl_active:
                self.disconnect()
        except Exception:
            logger.exception("Strain safe disconnect failed")

    def check_voltages(self, vs: list[float] | tuple[float, ...], temperature_k: float | None = None) -> None:
        """Ensure voltages are within the temperature-dependent limits."""

        resolved_temperature = self._resolved_temperature(temperature_k)
        v_min, v_max = _temperature_voltage_limits(resolved_temperature)
        v_peak = max(float(v) for v in vs)
        v_trough = min(float(v) for v in vs)

        if v_peak > v_max:
            self._safe_disconnect()
            raise ValueError(
                f"Requested voltage {v_peak} is too high. The maximum permitted voltage at "
                f"{resolved_temperature} K is {v_max}"
            )
        if v_trough < v_min:
            self._safe_disconnect()
            raise ValueError(
                f"Requested voltage {v_trough} is too low. The minimum permitted voltage at "
                f"{resolved_temperature} K is {v_min}"
            )

    def get_force(self, cap: float, temperature_k: float | None = None) -> float:
        """Convert capacitance to force using the attachment's polynomial model."""

        temp_k = self._resolved_temperature(temperature_k)
        alpha = 1708.94
        f0 = 1813.82
        cp = 0.0394
        delta_f0 = 98 - 0.0344 * temp_k - 0.00163 * (temp_k**2) + (4.99e-6) * (temp_k**3) - (8.91e-9) * (temp_k**4)
        k = 1 / (0.91 + (5e-5) * temp_k + (9e-7) * (temp_k**2))
        return k * ((alpha / (float(cap) - cp)) - f0 - delta_f0)

    def snapshot(self) -> dict[str, float | None]:
        return {
            "ch1_voltage": self.last_voltage_ch1,
            "ch2_voltage": self.last_voltage_ch2,
            "capacitance": self.last_capacitance,
            "loss": self.last_loss,
            "force": self.last_force,
            "temperature": self.temperature,
        }

    def _write_voltage_pair(self, ch1_voltage: float, ch2_voltage: float) -> None:
        raise NotImplementedError

    def get_capacitance(self) -> tuple[float | None, float | None]:
        raise NotImplementedError

    def apply_strain(
        self,
        v1: float,
        v2: float,
        sleeptime: float = 10,
        *,
        temperature_k: float | None = None,
    ) -> tuple[float | None, float | None, float | None]:
        """Apply a strain voltage pair, wait, then read capacitance/loss/force."""

        if not self.connected:
            raise RuntimeError("strain control is not connected")

        ch1 = float(v1)
        ch2 = float(v2)
        self.check_voltages([ch1, ch2], temperature_k=temperature_k)
        self._write_voltage_pair(ch1, ch2)
        self.last_voltage_ch1 = ch1
        self.last_voltage_ch2 = ch2
        time.sleep(max(0.0, float(sleeptime)))

        cap, loss = self.get_capacitance()
        self.last_capacitance = cap
        self.last_loss = loss
        if cap is None:
            self.last_force = None
            return None, None, None

        force = self.get_force(cap, temperature_k=temperature_k)
        self.last_force = force
        return cap, loss, force

    def connect(self) -> str:
        raise NotImplementedError

    def disconnect(self) -> None:
        raise NotImplementedError


class RealStrainController(BaseStrainController):
    """Hardware strain controller for RP100 + AH2550A."""

    def __init__(self, rp100_addr: str = STRAIN_RP100_ADDRESS, meter_addr: str = STRAIN_METER_ADDRESS) -> None:
        super().__init__()
        self.rp100_addr = rp100_addr
        self.meter_addr = meter_addr
        self.resource_manager: Any | None = None
        self.power_supply: Any | None = None
        self.meter: Any | None = None
        self.AH2550A_adapter: Any | None = None
        self.AH2550A: Any | None = None

    def connect(self) -> str:
        if self.connected:
            return "Strain control already connected"

        try:
            import pyvisa
            from pymeasure.adapters import VISAAdapter
            from pymeasure.instruments.andeenhagerling import AH2500A
        except Exception as exc:  # pragma: no cover - hardware-only path
            raise ImportError(f"Strain hardware libraries are unavailable: {exc}") from exc

        self.resource_manager = pyvisa.ResourceManager()
        self.power_supply = self.resource_manager.open_resource(self.rp100_addr)
        self.meter = self.resource_manager.open_resource(self.meter_addr)

        try:
            self.power_supply.write("OUTP1 1")
            self.power_supply.write("OUTP2 1")
            self.power_supply.write("SOUR1:VOLT:SLEW 100")
            self.power_supply.write("SOUR2:VOLT:SLEW 100")
        except Exception:
            self.disconnect()
            raise

        self.AH2550A_adapter = VISAAdapter(self.meter_addr)
        try:
            self.AH2550A_adapter.connection.timeout = 10_000
        except Exception:
            pass
        self.AH2550A = AH2500A(self.AH2550A_adapter, timeout=10_000)
        self.connected = True
        self.pzt_cntrl_active = True
        return "Strain control connected"

    def _write_voltage_pair(self, ch1_voltage: float, ch2_voltage: float) -> None:
        if self.power_supply is None:
            raise RuntimeError("strain power supply is not connected")
        self.power_supply.write(f"SOUR1:VOLT {ch1_voltage}")
        self.power_supply.write(f"SOUR2:VOLT {ch2_voltage}")

    def get_capacitance(self) -> tuple[float | None, float | None]:
        if self.AH2550A is None:
            raise RuntimeError("strain capacitance bridge is not connected")

        max_trigger_retries = 3
        max_read_retries = 2

        for trigger_attempt in range(max_trigger_retries):
            try:
                self.AH2550A.trigger()
                time.sleep(0.3)

                for read_attempt in range(max_read_retries):
                    try:
                        capacitance, loss, _voltage = self.AH2550A.triggered_caplossvolt()
                        if capacitance is not None and capacitance != 0:
                            return float(capacitance), float(loss)
                    except Exception as read_error:
                        if read_attempt >= max_read_retries - 1:
                            if trigger_attempt >= max_trigger_retries - 1:
                                logger.error(
                                    "Capacitance bridge read failed after %s attempts: %s",
                                    max_read_retries,
                                    read_error,
                                )
                                return None, None
                            break
                        time.sleep(0.3)
                        continue

                    if read_attempt < max_read_retries - 1:
                        time.sleep(0.2)
                        continue
                    break

                if trigger_attempt < max_trigger_retries - 1:
                    time.sleep(0.5 * (2 ** trigger_attempt))
                    continue
                break
            except Exception as trigger_error:
                if trigger_attempt >= max_trigger_retries - 1:
                    logger.error(
                        "Capacitance bridge trigger failed after %s attempts: %s",
                        max_trigger_retries,
                        trigger_error,
                    )
                    return None, None
                logger.warning(
                    "Capacitance bridge trigger attempt %s failed: %s",
                    trigger_attempt + 1,
                    trigger_error,
                )
                time.sleep(0.5 * (2 ** trigger_attempt))

        logger.warning("Capacitance measurement timed out")
        return None, None

    def disconnect(self) -> None:
        if not self.connected and not self.pzt_cntrl_active:
            return

        try:
            if self.power_supply is not None:
                try:
                    self.power_supply.write("SOUR1:VOLT 0")
                    self.power_supply.write("SOUR2:VOLT 0")
                    time.sleep(2)
                    self.power_supply.write("OUTP1 0")
                    self.power_supply.write("OUTP2 0")
                    time.sleep(1)
                finally:
                    try:
                        self.power_supply.close()
                    except Exception:
                        pass
        finally:
            self.power_supply = None

        try:
            if self.AH2550A is not None:
                try:
                    self.AH2550A.shutdown()
                except Exception:
                    pass
        finally:
            self.AH2550A = None

        try:
            if self.AH2550A_adapter is not None:
                try:
                    self.AH2550A_adapter.close()
                except Exception:
                    pass
        finally:
            self.AH2550A_adapter = None

        try:
            if self.resource_manager is not None:
                try:
                    self.resource_manager.close()
                except Exception:
                    pass
        finally:
            self.resource_manager = None
            self.connected = False
            self.pzt_cntrl_active = False


class MockStrainController(BaseStrainController):
    """Hardware-free strain controller for mockup mode and unit tests."""

    def __init__(self, seed: int = 12345) -> None:
        super().__init__()
        self._rng = random.Random(seed)
        self.mock_delay_s = 0.01
        self.mock_base_capacitance_pf = 12.5
        self.mock_capacitance_scale_pf_per_v = 0.035
        self.mock_loss_floor = 0.01

    def connect(self) -> str:
        self.connected = True
        self.pzt_cntrl_active = True
        return "Mock strain control connected"

    def _write_voltage_pair(self, ch1_voltage: float, ch2_voltage: float) -> None:
        self.last_voltage_ch1 = float(ch1_voltage)
        self.last_voltage_ch2 = float(ch2_voltage)

    def get_capacitance(self) -> tuple[float | None, float | None]:
        if not self.connected:
            raise RuntimeError("strain control is not connected")
        time.sleep(self.mock_delay_s)
        delta = self.last_voltage_ch1 - self.last_voltage_ch2
        cap = self.mock_base_capacitance_pf + self.mock_capacitance_scale_pf_per_v * delta
        cap += self._rng.gauss(0.0, abs(cap) * 0.002)
        loss = self.mock_loss_floor + abs(delta) * 1e-3 + self._rng.gauss(0.0, 2e-4)
        return float(cap), float(loss)

    def disconnect(self) -> None:
        self.connected = False
        self.pzt_cntrl_active = False
        self.last_voltage_ch1 = 0.0
        self.last_voltage_ch2 = 0.0


def build_strain_controller(*, use_mockup: bool) -> BaseStrainController:
    return MockStrainController() if use_mockup else RealStrainController()