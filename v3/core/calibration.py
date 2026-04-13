"""
v3.core.calibration  —  Helmholtz and Hall-bar calibration constants and helpers.

Centralizes all field ↔ current conversions to eliminate inconsistent
hardcoded constants.
"""

from __future__ import annotations
from dataclasses import dataclass, field
import random


@dataclass
class CalibrationConfig:
    """
    Holds all calibration parameters for the experiment setup.

    Helmholtz coil system
    ---------------------
    ``ga_per_coil`` is kept as a legacy field name, but represents the
    **total Helmholtz system gain** in Gauss per Ampere (G/A), not per-coil
    gain.  ``num_coils`` is still used for total↔per-coil current splitting.

    Hall bar
    --------
    ``hall_v2gauss``  :  conversion factor  V → Gauss  (user-set per sample)
    ``hall_offset_v`` :  voltage offset  (user-set per sample)
    """

    # Helmholtz
    ga_per_coil: float = 341.71
    num_coils: int = 2

    # Hall bar
    hall_v2gauss: float = 1.0
    hall_offset_v: float = 0.0

    # Hall mock model (used only in mock-mode Hall measurement branch)
    hall_mock_enabled: bool = True
    hall_mock_helmholtz_gain: float = 1.0
    hall_mock_ppms_gain: float = 0.01
    hall_mock_offset_g: float = 2.0
    hall_mock_v2gauss: float = 10000.0 / 0.215
    hall_mock_noise_floor_v: float = 2e-10
    hall_mock_noise_rel: float = 1e-6
    hall_mock_seed: int | None = None

    # Derived — computed in __post_init__
    ga_total: float = field(init=False)
    _hall_mock_rng: random.Random = field(init=False, repr=False)

    def __post_init__(self) -> None:
        # IMPORTANT: ga_per_coil is legacy-named and stores total Helmholtz gain.
        self.ga_total = float(self.ga_per_coil)
        self._hall_mock_rng = random.Random(self.hall_mock_seed)

    # ------------------------------------------------------------------
    # Helmholtz conversions
    # ------------------------------------------------------------------
    def current_to_field(self, current_a: float) -> float:
        """Convert Helmholtz total current (A) → magnetic field (Gauss)."""
        return current_a * self.ga_total

    def field_to_current(self, field_g: float) -> float:
        """Convert Helmholtz field (Gauss) → required total current (A)."""
        if self.ga_total == 0:
            raise ZeroDivisionError("ga_total is zero — calibration not set")
        return field_g / self.ga_total

    def coil_current(self, total_current_a: float) -> float:
        """Current per coil (A) from the total current setpoint."""
        return total_current_a / self.num_coils

    # ------------------------------------------------------------------
    # Hall bar conversions
    # ------------------------------------------------------------------
    def hall_voltage_to_field(self, voltage_v: float) -> float:
        """Convert measured Hall voltage (V) → field (Gauss)."""
        return (voltage_v - self.hall_offset_v) * self.hall_v2gauss

    def hall_field_error(self, voltage_std: float) -> float:
        """Propagate Hall voltage std → field std."""
        return abs(voltage_std * self.hall_v2gauss)

    def hall_mock_rng(self) -> random.Random:
        """Return RNG used by Hall mock model."""
        return self._hall_mock_rng
