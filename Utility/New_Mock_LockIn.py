"""
Mock SR830 lock-in amplifier for offline testing.

Mirrors the full public interface of LockInSR830 so that higher-level
code (GUI, scan scripts) can be developed without hardware.
"""

import time
import math
import random
import numpy as np


class MockLockInSR830:
    """
    Drop-in replacement for LockInSR830 that simulates a noisy
    AC signal without requiring a real instrument.
    """

    # ── Same lookup tables as the real driver ──

    TAU_TABLE = [
        10e-6, 30e-6, 100e-6, 300e-6,
        1e-3,  3e-3,  10e-3,  30e-3,
        100e-3, 300e-3, 1, 3, 10, 30,
        100, 300, 1e3, 3e3, 1e4, 3e4
    ]

    SENS_TABLE = [
        2e-9,   5e-9,   10e-9,  20e-9,  50e-9,
        100e-9, 200e-9, 500e-9,
        1e-6,   2e-6,   5e-6,
        10e-6,  20e-6,  50e-6,
        100e-6, 200e-6, 500e-6,
        1e-3,   2e-3,   5e-3,
        10e-3,  20e-3,  50e-3,
        100e-3, 200e-3, 500e-3, 1.0
    ]

    FILTER_MULT = {0: 5, 1: 7, 2: 9, 3: 12}

    _MIN_SLVL = 0.004
    _MAX_SLVL = 5.0
    _SLVL_RES = 0.001

    # ── Constructor ──

    def __init__(self, resource="MOCK"):
        """Accepts (and ignores) a resource string for API compatibility."""
        self._freq = 223.0
        self._phase = 0.0
        self._slvl = self._MIN_SLVL
        self._sens_idx = 10
        self._tau_idx = 9          # 300 ms
        self._slope_idx = 3        # 24 dB/oct
        self._sync_filter = True
        self._input_shield_grounded = False
        self._overloaded = False   # set manually for testing
        self._auto_busy_until = 0.0
        self._mock_auto_duration_s = 0.05
        print(f"[MOCK] LockInSR830 created (resource={resource!r})")
        self.initialize_default_state()

    # ── Low-level (no-ops for mock) ──

    def write(self, cmd):
        pass

    def query(self, cmd, retries=2, wait_after_write=0.05, force_clear=False):
        return ""

    def _fast_query(self, cmd):
        return ""

    # ── Initialization ──

    def initialize_default_state(self):
        self._slvl = self._MIN_SLVL
        self._freq = 173.0
        self._phase = 0.0
        self._sens_idx = 10
        self._tau_idx = 9
        self._slope_idx = 3
        self._sync_filter = True
        self._input_shield_grounded = False
        print("[MOCK] Default state initialized")

    # ── Reference / sine output ──

    def set_frequency(self, f):
        self._freq = f

    def get_frequency(self):
        return self._freq

    def set_reference_amplitude(self, v):
        v = round(float(v) / self._SLVL_RES) * self._SLVL_RES
        self._slvl = max(self._MIN_SLVL, min(v, self._MAX_SLVL))

    def get_reference_amplitude(self):
        return self._slvl

    def sine_output_on(self, amplitude_v):
        self.set_reference_amplitude(amplitude_v)

    def sine_output_off(self):
        self.set_reference_amplitude(self._MIN_SLVL)

    def set_excitation_current(self, current_rms, series_resistance):
        if series_resistance <= 0:
            raise ValueError("Series resistance must be positive")
        voltage = current_rms * series_resistance
        if voltage > self._MAX_SLVL:
            raise ValueError(
                f"Required SLVL {voltage:.4f} V exceeds SR830 max "
                f"({self._MAX_SLVL} V)."
            )
        self.set_reference_amplitude(voltage)

    # ── Phase ──

    def set_phase(self, deg):
        self._phase = deg

    def get_phase(self):
        return self._phase

    # ── Input shield (ground / float) ──

    def set_input_shield_grounded(self, grounded):
        self._input_shield_grounded = bool(grounded)

    def set_input_shield_float(self):
        self.set_input_shield_grounded(False)

    def set_input_shield_ground(self):
        self.set_input_shield_grounded(True)

    def is_input_shield_grounded(self):
        return self._input_shield_grounded

    # ── Sensitivity / time-constant / filter slope ──

    def set_sensitivity(self, idx):
        if not 0 <= idx < len(self.SENS_TABLE):
            raise ValueError(f"Sensitivity index {idx} out of range")
        self._sens_idx = idx

    def get_sensitivity(self):
        return self._sens_idx

    def set_time_constant(self, idx):
        if not 0 <= idx < len(self.TAU_TABLE):
            raise ValueError(f"Time-constant index {idx} out of range")
        self._tau_idx = idx

    def get_time_constant(self):
        return self._tau_idx

    def set_filter_slope(self, idx):
        if not 0 <= idx <= 3:
            raise ValueError(f"Filter-slope index {idx} out of range")
        self._slope_idx = idx

    def get_filter_slope(self):
        return self._slope_idx

    # ── Simulated signal ──

    def _sim_signal(self):
        """Return a simulated (X, Y) pair based on SLVL + noise."""
        noise_frac = 0.01
        base = self._slvl
        x = base + random.gauss(0, base * noise_frac)
        y = (base * math.sin(math.radians(self._phase))
             + random.gauss(0, base * noise_frac))
        return x, y

    # ── Data outputs ──

    def snap(self, *channels):
        """Simulate SNAP? for channels 1=X, 2=Y, 3=R, 4=θ."""
        if len(channels) < 2 or len(channels) > 6:
            raise ValueError("SNAP requires 2–6 channel parameters")
        x, y = self._sim_signal()
        r = math.hypot(x, y)
        theta = math.degrees(math.atan2(y, x))
        lookup = {1: x, 2: y, 3: r, 4: theta}
        return [lookup.get(ch, 0.0) for ch in channels]

    def read_x(self):
        x, _ = self._sim_signal()
        return x

    def read_y(self):
        _, y = self._sim_signal()
        return y

    def read_r(self):
        x, y = self._sim_signal()
        return math.hypot(x, y)

    def read_theta(self):
        x, y = self._sim_signal()
        return math.degrees(math.atan2(y, x))

    # ── Buffer ──

    def reset_buffer(self):
        pass

    # ── Status ──

    def serial_poll_status(self):
        return self._read_serial_poll_status()

    def _read_serial_poll_status(self):
        # Match real-driver IFC semantics: bit 1 set means idle.
        if time.perf_counter() < self._auto_busy_until:
            return 0
        return 0b10

    @staticmethod
    def _is_internal_command_idle(status_byte):
        return bool(status_byte & (1 << 1))

    def is_overloaded(self):
        return self._overloaded

    # ── Safe auto-commands ──

    def _wait_for_command_complete(
        self,
        timeout_s=15.0,
        poll_interval_s=0.05,
        consecutive_idle_polls=1,
    ):
        if timeout_s <= 0:
            raise ValueError("timeout_s must be positive")
        if poll_interval_s <= 0:
            raise ValueError("poll_interval_s must be positive")
        if consecutive_idle_polls <= 0:
            raise ValueError("consecutive_idle_polls must be positive")

        deadline = time.perf_counter() + float(timeout_s)
        idle_count = 0
        while True:
            now = time.perf_counter()
            if now >= deadline:
                raise TimeoutError(
                    "Mock SR830 auto-command did not complete within "
                    f"{timeout_s:.2f} s"
                )

            if self._is_internal_command_idle(self._read_serial_poll_status()):
                idle_count += 1
                if idle_count >= consecutive_idle_polls:
                    return
            else:
                idle_count = 0

            time.sleep(min(poll_interval_s, max(deadline - now, 0.0)))

    def _safe_auto(
        self,
        cmd,
        timeout_s=15.0,
        poll_interval_s=0.05,
        post_settle_s=0.1,
        consecutive_idle_polls=1,
    ):
        print(f"[MOCK] auto command: {cmd}")
        self._auto_busy_until = time.perf_counter() + max(self._mock_auto_duration_s, 0.0)
        self._wait_for_command_complete(
            timeout_s=timeout_s,
            poll_interval_s=poll_interval_s,
            consecutive_idle_polls=consecutive_idle_polls,
        )
        if post_settle_s > 0:
            time.sleep(min(post_settle_s, 0.2))

    def safe_auto_phase(self, timeout_s=15.0):
        self._safe_auto("APHS", timeout_s)

    def safe_auto_gain(self, timeout_s=15.0):
        self._safe_auto("AGAN", timeout_s)

    def safe_auto_reserve(self, timeout_s=15.0):
        self._safe_auto("ARSV", timeout_s)

    # ── Settling ──

    def estimate_settling_time(self, scale=1.0):
        tau = self.TAU_TABLE[self._tau_idx]
        mult = self.FILTER_MULT[self._slope_idx]
        return mult * tau * scale

    def wait_for_settling(self, scale=1.0, show_timer=False):
        t = self.estimate_settling_time(scale)
        actual = min(t, 0.2)      # cap mock sleep to keep tests fast
        if show_timer:
            print(f"[MOCK] settling for {t:.2f} s")
        time.sleep(actual)

    # ── Quick autorange ──

    def quick_autorange(self, target_fraction=0.7, max_iter=20):
        print("[MOCK] quick_autorange (no-op in mock)")
        self.wait_for_settling(0.5)

    # ── Measurement ──

    def measure(
        self,
        what=("X", "Y", "R", "Theta"),
        current=1e-6,
        series_resistance=10e3,
        avg=10,
        start_sens=10,
        use_autorange=True,
        use_autophase=True,
        sample_delay=0.05,
        manage_excitation=True,
        wait_for_settling_when_no_autorange=True,
    ):
        ch_map = {"X": 1, "Y": 2, "R": 3, "Theta": 4}
        for k in what:
            if k not in ch_map:
                raise ValueError(
                    f"Unknown channel '{k}'. Valid: {list(ch_map.keys())}"
                )

        if start_sens is not None:
            self.set_sensitivity(int(start_sens))
        if manage_excitation:
            self.set_excitation_current(current, series_resistance)
        self.reset_buffer()

        if use_autorange:
            self.quick_autorange()
        if use_autophase:
            self.safe_auto_phase()
        elif wait_for_settling_when_no_autorange:
            self.wait_for_settling(show_timer=True)

        data = {k: [] for k in what}
        for _ in range(avg):
            if len(what) == 1:
                key = what[0]
                if key == "X":
                    vals = [self.read_x()]
                elif key == "Y":
                    vals = [self.read_y()]
                elif key == "R":
                    vals = [self.read_r()]
                elif key == "Theta":
                    vals = [self.read_theta()]
                else:
                    raise ValueError(f"Unknown channel '{key}'")
            else:
                vals = self.snap(*[ch_map[k] for k in what])
            for k, v in zip(what, vals):
                data[k].append(v)
            time.sleep(sample_delay)

        if manage_excitation:
            self.sine_output_off()

        return {
            k: {"mean": float(np.mean(v)), "std": float(np.std(v))}
            for k, v in data.items()
        } | {"sens_idx": self.get_sensitivity()}

    # ── Teardown ──

    def close(self):
        print("[MOCK] closed")
