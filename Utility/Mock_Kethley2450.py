import time
import numpy as np

class MockKeithley2450:
    def __init__(self, adapter=None, name="Mock Keithley 2450", **kwargs):
        self.adapter = adapter
        self.name = name
        self.connected = False
        self.is_mock_hall = True

        # Initialize properties
        self._source_mode = 'current'  # 'current' or 'voltage'
        self._source_enabled = False
        self._source_current = 0.0
        self._source_voltage = 0.0
        self._compliance_voltage = 10.0
        self._compliance_current = 0.1
        self._current_range = 1.05
        self._voltage_range = 210.0
        self._source_current_range = 1.05
        self._source_voltage_range = 210.0
        self._nplc = 1
        self._auto_range = True
        self._voltage_filter_count = 10
        self._wires = 2
        self._load_resistance_ohm = 1200.0

    @property
    def source_mode(self):
        return self._source_mode

    @source_mode.setter
    def source_mode(self, value):
        if value in ['current', 'voltage']:
            self._source_mode = value
        else:
            raise ValueError("Invalid source mode")

    @property
    def source_enabled(self):
        return self._source_enabled

    @property
    def current(self):
        # Simulate measurement
        if self._source_mode == 'current':
            return self._source_current + np.random.normal(0, 1e-6)
        if abs(self._load_resistance_ohm) > 1e-12:
            return (self._source_voltage / self._load_resistance_ohm) + np.random.normal(0, 1e-6)
        return np.random.normal(0, 1e-6)

    @property
    def voltage(self):
        # Simulate measurement
        if self._source_mode == 'voltage':
            return self._source_voltage + np.random.normal(0, 1e-3)
        return (self._source_current * self._load_resistance_ohm) + np.random.normal(0, 1e-3)

    @property
    def source_current(self):
        return self._source_current

    @source_current.setter
    def source_current(self, value):
        self._source_current = value

    @property
    def source_voltage(self):
        return self._source_voltage

    @source_voltage.setter
    def source_voltage(self, value):
        self._source_voltage = value

    @property
    def compliance_voltage(self):
        return self._compliance_voltage

    @compliance_voltage.setter
    def compliance_voltage(self, value):
        self._compliance_voltage = value

    @property
    def compliance_current(self):
        return self._compliance_current

    @compliance_current.setter
    def compliance_current(self, value):
        self._compliance_current = value

    def connect(self):
        self.connected = True
        return "Mock Keithley 2450 connected"

    def disconnect(self):
        self.disable_source()
        self.connected = False

    def reset(self):
        self._source_current = 0
        self._source_voltage = 0
        self.disable_source()
        # Reset other settings

    def enable_source(self):
        self._source_enabled = True

    def disable_source(self):
        self._source_enabled = False

    def apply_current(self, current_range=None, compliance_voltage=10):
        self.source_mode = 'current'
        if current_range is not None:
            self._source_current_range = current_range
        self.compliance_voltage = compliance_voltage

    def apply_voltage(self, voltage_range=None, compliance_current=0.1):
        self.source_mode = 'voltage'
        if voltage_range is not None:
            self._source_voltage_range = voltage_range
        self.compliance_current = compliance_current

    def measure_voltage(self, nplc=1, voltage=21.0, auto_range=True, repetitions=1):
        self._nplc = nplc
        if not auto_range:
            self._voltage_range = voltage
        # Timing model: 1 NPLC = 0.02 s per acquisition
        reps = max(int(repetitions), 1)
        acquisition_time_s = max(float(nplc), 0.0) * 0.02 * reps
        if acquisition_time_s > 0:
            time.sleep(acquisition_time_s)

        if self.source_mode == 'current':
            base_voltage = self._source_current * self._load_resistance_ohm
        else:
            base_voltage = self._source_voltage

        sigma = max(abs(self._voltage_range), 1e-6) * 0.01
        if reps <= 1:
            value = np.random.normal(base_voltage, sigma)
            return (value, 0.0)
        measurements = [
            np.random.normal(base_voltage, sigma)
            for _ in range(reps)
        ]
        avg_voltage = float(np.mean(measurements))
        std_voltage = float(np.std(measurements, ddof=1)) if len(measurements) > 1 else 0.0
        return (avg_voltage, std_voltage)

    def measure_current(self, nplc=1, current=1.05, auto_range=True, repetitions=1):
        self._nplc = nplc
        if not auto_range:
            self._current_range = current
        # Timing model: 1 NPLC = 0.02 s per acquisition
        reps = max(int(repetitions), 1)
        acquisition_time_s = max(float(nplc), 0.0) * 0.02 * reps
        if acquisition_time_s > 0:
            time.sleep(acquisition_time_s)

        if self.source_mode == 'voltage':
            if abs(self._load_resistance_ohm) > 1e-12:
                base_current = self._source_voltage / self._load_resistance_ohm
            else:
                base_current = 0.0
        else:
            base_current = self._source_current

        sigma = max(abs(self._current_range), 1e-9) * 0.01
        if reps <= 1:
            value = np.random.normal(base_current, sigma)
            return (value, 0.0)
        measurements = [
            np.random.normal(base_current, sigma)
            for _ in range(reps)
        ]
        avg_current = float(np.mean(measurements))
        std_current = float(np.std(measurements, ddof=1)) if len(measurements) > 1 else 0.0
        return (avg_current, std_current)

    def measure_resistance(self, nplc=1, resistance=1.05, auto_range=True, repetitions=1):
        current = self._source_current
        if abs(current) < 1e-15:
            current = 1e-3
        measured_voltage, voltage_std = self.measure_voltage(
            nplc=nplc,
            voltage=resistance,
            auto_range=auto_range,
            repetitions=repetitions,
        )
        resistance_value = measured_voltage / current
        resistance_std = abs(voltage_std / current)
        return float(resistance_value), float(resistance_std)

    def set_source_current_amps(self, amps):
        self.source_mode = 'current'
        self._source_current = float(amps)

    def set_source_voltage_volts(self, volts):
        self.source_mode = 'voltage'
        self._source_voltage = float(volts)

    def ramp_to_current(self, target_current, steps=30, pause=20e-3):
        currents = np.linspace(self._source_current, target_current, steps)
        for current in currents:
            self._source_current = current
            time.sleep(pause)

    def ramp_to_voltage(self, target_voltage, steps=30, pause=20e-3):
        voltages = np.linspace(self._source_voltage, target_voltage, steps)
        for voltage in voltages:
            self._source_voltage = voltage
            time.sleep(pause)

    def shutdown(self):
        self.ramp_to_current(0)
        self.disable_source()

    def voltage_filter_count(self, count):
        self._voltage_filter_count = count

    def write(self, command):
        """Simulate writing a command to the instrument."""
        pass

    def query(self, command):
        """Simulate querying the instrument and returning a response."""
        if "printbuffer" in command:
            # Simulate returning a fake IV sweep dataset
            max_curr = 1e-6
            curr_step = 1e-8
            down = np.linspace(0, -max_curr, int(max_curr / curr_step) + 1)
            up = np.linspace(-max_curr, max_curr, 2 * int(max_curr / curr_step) + 1)
            back_down = np.linspace(max_curr, 0, int(max_curr / curr_step) + 1)
            current_values = np.concatenate((down, up, back_down))
            voltage_values = [current * 1e3 + np.random.uniform(-1e-4, 1e-4) for current in current_values]
            return ",".join(f"{i},{v}" for i, v in zip(current_values, voltage_values))
        return "MOCK RESPONSE"
