"""
Mock Lock-In amplifier compatible with pymeasure SR830 interface.

Provides SR830-like interface with:
 - attributes: frequency, time_constant, filter_slope, input_config, sensitivity, sine_voltage
 - additional attributes: input_grounding, reference_source, R_lockin, source_current
 - methods: connect(), disconnect(), reset(), clear(), auto_gain(), auto_phase()
 - properties: magnitude, theta (phase)
 - compatibility: MockLockin alias
"""
import time
import random
import math

class MockLockIn:
    # Sensitivity levels (V) typical for SR830-like instruments
    SENSITIVITY_LEVELS = [
        2e-9, 5e-9, 1e-8, 2e-8, 5e-8, 1e-7, 2e-7, 5e-7, 1e-6, 2e-6, 5e-6,
        1e-5, 2e-5, 5e-5, 1e-4, 2e-4, 5e-4, 1e-3, 2e-3, 5e-3, 1e-2, 2e-2,
        5e-2, 1e-1, 2e-1, 5e-1, 1.0
    ]

    def __init__(self,
                 frequency=668.4,
                 time_constant=1.0,
                 filter_slope=24,
                 input_config="A - B",
                 sensitivity=50e-5,
                 sine_voltage=0.0):
        # SR830-like configuration
        self.frequency = float(frequency)
        self.time_constant = float(time_constant)
        self.filter_slope = filter_slope
        self.input_config = input_config
        self.sensitivity = float(sensitivity)
        self.sine_voltage = float(sine_voltage)

        # Additional parameters from LockIn_RB_RT_2
        self.R_lockin = 0.996 * 1e6  # ohms (from LockInConfig)
        self.source_current = 100e-9  # A (from LockInConfig)
        self.input_grounding = "Ground"
        self.reference_source = "Internal"
        self.autogain = False
        self.reserve = "Normal"  # dynamic reserve setting

        # internal caches for properties and simulated noise
        self._last_mag = 1e-6
        self._last_phase = 0.0
        self._connected = False

    # ---- connection / lifecycle ----
    def connect(self):
        self._connected = True
        return "MOCK LOCK-IN CONNECTED"

    def disconnect(self):
        self._connected = False
        return "MOCK LOCK-IN DISCONNECTED"

    def reset(self):
        self.sensitivity = 0
        self.sine_voltage = 0.0
        self._last_mag = 1e-6
        self._last_phase = 0.0

    def clear(self):
        # compatibility no-op
        self._last_mag = 1e-6
        self._last_phase = 0.0

    # ---- simple SCPI-like helpers ----
    def write(self, cmd):
        # Accept commands for compatibility; no real parsing required
        return None

    def query(self, cmd):
        k = str(cmd).upper()
        if "FREQ" in k:
            return str(self.frequency)
        if "SENS" in k or "SENSITIVITY" in k:
            return str(self.sensitivity)
        return ""

    # ---- measurement properties ----
    @property
    def magnitude(self):
        # quick throwaway read: small random variation around last measurement
        noise_std = max(1e-9, 0.01 * abs(self._last_mag) + 1e-9) / math.sqrt(max(1.0, self.time_constant))
        self._last_mag = max(0.0, self._last_mag + random.gauss(0.0, noise_std))
        # if sine_voltage set, bias magnitude toward that (simulate source coupling)
        if self.sine_voltage:
            bias = abs(self.sine_voltage)
            self._last_mag = max(self._last_mag, bias * 0.5 + random.gauss(0, noise_std))
        return float(self._last_mag)

    @property
    def theta(self):
        # phase in degrees with small jitter
        self._last_phase = float(self._last_phase + random.gauss(0.0, 0.2))
        return float(self._last_phase)

    # ---- measurement API ----
    def measure(self, averaging=1):
        """
        Simulate a measurement. Returns tuple:
        (resistance_Ohm, magnitude_V, phase_deg, res_err_Ohm, mag_err_V, phase_err_deg)
        """
        n = max(1, int(averaging))
        mags = []
        phases = []
        for _ in range(n):
            # baseline depends on sine_voltage if present
            baseline = max(1e-9, abs(self.sine_voltage) if self.sine_voltage else 1e-6)
            # noise reduces with longer time constant
            std = baseline * 0.02 / math.sqrt(max(1.0, self.time_constant))
            v = max(0.0, random.gauss(baseline, std))
            p = random.gauss(0.0, 0.2)
            mags.append(v)
            phases.append(p)
            # simulate instrument integration delay
            time.sleep(min(0.01, 0.1 * self.time_constant))

        mag_mean = float(sum(mags) / len(mags))
        phase_mean = float(sum(phases) / len(phases))

        def _std(arr, mean):
            if len(arr) <= 1:
                return 0.0
            s = sum((x - mean) ** 2 for x in arr) / (len(arr) - 1)
            return float(math.sqrt(s))

        mag_err = _std(mags, mag_mean)
        phase_err = _std(phases, phase_mean)

        # Avoid division by zero for current
        I = self.source_current if abs(self.source_current) > 0 else 1e-12
        res_mean = mag_mean / I
        res_err = mag_err / I

        # cache last values for magnitude/phase properties
        self._last_mag = mag_mean
        self._last_phase = phase_mean

        return res_mean, mag_mean, phase_mean, res_err, mag_err, phase_err

    # ---- autogain / sensitivity helpers ----
    def find_sensitivity(self):
        """
        Choose smallest sensitivity that keeps mag < 0.75 * sens.
        If last mag is zero-ish, take a short sample first.
        """
        mag_est = getattr(self, "_last_mag", None)
        if not mag_est or mag_est == 0.0:
            try:
                _, mag_est, _, _, _, _ = self.measure(averaging=3)
            except Exception:
                mag_est = 1e-6

        for s in self.SENSITIVITY_LEVELS:
            if mag_est < 0.75 * s:
                self.sensitivity = s
                return s
        # fallback: largest sensitivity
        self.sensitivity = self.SENSITIVITY_LEVELS[-1]
        return self.sensitivity

    def auto_gain(self):
        # alias for find_sensitivity
        return self.find_sensitivity()

    def auto_phase(self):
        # simulate auto phase-lock; reset phase estimate to zero-ish
        self._last_phase = 0.0
        # slight settling delay
        time.sleep(min(0.05, 0.5 * self.time_constant))
        return None

    def auto_reserve(self):
        # simulate auto reserve; optimize dynamic reserve based on current signal
        current_mag = self.magnitude
        # For SR830-like behavior, set reserve based on signal level
        if current_mag < 1e-6:
            self.reserve = "High Reserve"
        elif current_mag < 1e-3:
            self.reserve = "Normal"
        else:
            self.reserve = "Low Noise"
        # slight settling delay
        time.sleep(min(0.05, 0.5 * self.time_constant))
        return self.reserve

    # ---- compatibility property aliases ----
    @property
    def TimeConstant(self):
        return self.time_constant

    @TimeConstant.setter
    def TimeConstant(self, v):
        try:
            self.time_constant = float(v)
        except Exception:
            self.time_constant = v

    @property
    def Sensitivity(self):
        return self.sensitivity

    @Sensitivity.setter
    def Sensitivity(self, v):
        try:
            self.sensitivity = float(v)
        except Exception:
            self.sensitivity = v

# compatibility alias used elsewhere in repo
MockLockin = MockLockIn