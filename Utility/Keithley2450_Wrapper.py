"""
Keithley 2450 Wrapper for pymeasure
Provides a compatible interface between pymeasure's Keithley2450 and the custom API
used in the measurement GUI.
"""

from pymeasure.instruments.keithley import Keithley2450 as PymeasureKeithley2450
import time
import numpy as np


class Keithley2450Wrapper:
    """
    Wrapper class that adapts pymeasure's Keithley2450 to match the custom
    interface used in the measurement scripts.
    """
    
    def __init__(self, resource_name):
        """
        Initialize the Keithley 2450 via pymeasure.
        
        Parameters
        ----------
        resource_name : str
            VISA resource address, e.g., 'GPIB0::18::INSTR'
        """
        self.instrument = PymeasureKeithley2450(resource_name)
        self.connected = True
        self._default_timeout_ms = 30000
        self._set_timeout_ms(self._default_timeout_ms)
        
        # Configure for rear terminals and 4-wire mode
        self.configure_terminals_and_sense()
        
        # Internal state tracking
        self._source_current = 0.0
        self._source_voltage = 0.0
        self._compliance_voltage = 10.0
        self._compliance_current = 0.1
        self._source_enabled = False
        self._voltage_filter_count = 10

    def _set_timeout_ms(self, timeout_ms):
        """Best-effort VISA timeout configuration in milliseconds."""
        try:
            adapter = getattr(self.instrument, "adapter", None)
            if adapter is None:
                return
            connection = getattr(adapter, "connection", None)
            if connection is not None and hasattr(connection, "timeout"):
                connection.timeout = int(timeout_ms)
                return
            if hasattr(adapter, "timeout"):
                adapter.timeout = int(timeout_ms)
        except Exception:
            # Keep wrapper resilient across pymeasure/adapter variants.
            pass

    def _set_measure_timeout(self, nplc, repetitions):
        """
        Set timeout based on integration time and averaging count.
        1 NPLC is about 20 ms at 50 Hz mains.
        """
        reps = max(int(repetitions), 1)
        integ = max(float(nplc), 0.0)
        estimated_s = integ * 0.02 * reps
        timeout_ms = int(max(self._default_timeout_ms, (estimated_s + 2.0) * 4000.0))
        self._set_timeout_ms(timeout_ms)

    @staticmethod
    def _is_recoverable_comm_error(exc):
        msg = str(exc).lower()
        return (
            "vi_error_tmo" in msg
            or "timeout" in msg
            or "not found in mapped values" in msg
            or "invalid literal for int()" in msg
        )

    def _recover_comm_state(self):
        """Clear parser/buffer state after a transport or parse failure."""
        try:
            self.instrument.write(":ABOR")
        except Exception:
            pass
        try:
            self.instrument.write("*CLS")
        except Exception:
            pass
        try:
            self.configure_terminals_and_sense(terminals='REAR', remote_sense=True)
        except Exception:
            pass
    
    def configure_terminals_and_sense(self, terminals='REAR', remote_sense=True):
        """
        Configure terminal selection and remote sense (4-wire) mode.
        
        Parameters
        ----------
        terminals : str
            'FRONT' or 'REAR' (default: 'REAR')
        remote_sense : bool
            Enable 4-wire remote sense for voltage and current measurements (default: True)
        """
        # Set terminal selection using built-in pymeasure method
        if terminals.upper() == 'REAR':
            self.instrument.use_rear_terminals()
        else:
            self.instrument.use_front_terminals()
        
        # Enable remote sense (4-wire) for voltage and current measurements
        if remote_sense:
            self.instrument.write(":SENS:VOLT:RSEN ON")
            self.instrument.write(":SENS:CURR:RSEN ON")
        else:
            self.instrument.write(":SENS:VOLT:RSEN OFF")
            self.instrument.write(":SENS:CURR:RSEN OFF")
        
    @property
    def source_current(self):
        """Get the source current setpoint."""
        return self._source_current
    
    @source_current.setter
    def source_current(self, value):
        """Set the source current setpoint (in mA in GUI, converted to A for pymeasure)."""
        self._source_current = value
        # Convert mA to A for pymeasure
        self.instrument.source_current = value / 1000.0
    
    @property
    def source_voltage(self):
        """Get the source voltage setpoint."""
        return self._source_voltage
    
    @source_voltage.setter
    def source_voltage(self, value):
        """Set the source voltage setpoint."""
        self._source_voltage = value
        self.instrument.source_voltage = value
    
    @property
    def compliance_voltage(self):
        """Get the compliance voltage."""
        return self._compliance_voltage
    
    @compliance_voltage.setter
    def compliance_voltage(self, value):
        """Set the compliance voltage."""
        self._compliance_voltage = value
        self.instrument.compliance_voltage = value
    
    @property
    def compliance_current(self):
        """Get the compliance current."""
        return self._compliance_current
    
    @compliance_current.setter
    def compliance_current(self, value):
        """Set the compliance current."""
        self._compliance_current = value
        self.instrument.compliance_current = value
    
    def connect(self):
        """Already connected on instantiation with pymeasure."""
        self.connected = True
        return "Keithley 2450 connected via pymeasure"
    
    def disconnect(self):
        """Disconnect from the instrument."""
        self.disable_source()
        if hasattr(self.instrument, 'shutdown'):
            self.instrument.shutdown()
        self.connected = False
    
    def reset(self):
        """Reset the instrument to default state."""
        self.instrument.reset()
        # Reset returns the SMU to defaults, so enforce project wiring mode.
        self.configure_terminals_and_sense(terminals='REAR', remote_sense=True)
        self._source_current = 0
        self._source_voltage = 0
        self.disable_source()
    
    def enable_source(self):
        """Enable the source output."""
        self.instrument.enable_source()
        self._source_enabled = True
    
    def disable_source(self):
        """Disable the source output."""
        self.instrument.disable_source()
        self._source_enabled = False
    
    def apply_current(self, current_range=None, compliance_voltage=10):
        """
        Configure current source mode.
        
        Parameters
        ----------
        current_range : float, optional
            Current range in A (pymeasure uses A, not mA)
        compliance_voltage : float
            Compliance voltage in V
        """
        self.instrument.apply_current(
            current_range=current_range,
            compliance_voltage=compliance_voltage
        )
        self._compliance_voltage = compliance_voltage
    
    def apply_voltage(self, voltage_range=None, compliance_current=0.1):
        """
        Configure voltage source mode.
        
        Parameters
        ----------
        voltage_range : float, optional
            Voltage range in V
        compliance_current : float
            Compliance current in A
        """
        self.instrument.apply_voltage(
            voltage_range=voltage_range,
            compliance_current=compliance_current
        )
        self._compliance_current = compliance_current
    
    def measure_voltage(self, nplc=1, voltage=21.0, auto_range=True, repetitions=1):
        """
        Measure voltage with software averaging.
        
        Parameters
        ----------
        nplc : float
            Number of power line cycles for integration
        voltage : float
            Voltage range (if auto_range=False)
        auto_range : bool
            Enable automatic ranging
        repetitions : int
            Number of measurements to average (default: 1)
        
        Returns
        -------
        tuple
            (average_voltage, std_voltage) in V. If repetitions=1, std=0.0
        """
        self._set_measure_timeout(nplc=nplc, repetitions=repetitions)
        for attempt in range(2):
            try:
                # Use pymeasure's built-in method which properly configures sense function
                if repetitions <= 1:
                    self.instrument.measure_voltage(nplc=nplc, voltage=voltage, auto_range=auto_range)
                    return (self.instrument.voltage, 0.0)

                # Multiple measurements for software averaging
                measurements = []
                for _ in range(repetitions):
                    self.instrument.measure_voltage(nplc=nplc, voltage=voltage, auto_range=auto_range)
                    measurements.append(self.instrument.voltage)

                avg_voltage = np.mean(measurements)
                std_voltage = np.std(measurements, ddof=1) if len(measurements) > 1 else 0.0
                return (avg_voltage, std_voltage)
            except Exception as exc:
                if attempt == 0 and self._is_recoverable_comm_error(exc):
                    self._recover_comm_state()
                    continue
                raise
    
    def measure_current(self, nplc=1, current=1.05, auto_range=True, repetitions=1):
        """
        Measure current with software averaging.
        
        Parameters
        ----------
        nplc : float
            Number of power line cycles for integration
        current : float
            Current range (if auto_range=False)
        auto_range : bool
            Enable automatic ranging
        repetitions : int
            Number of measurements to average (default: 1)
        
        Returns
        -------
        tuple
            (average_current, std_current) in A. If repetitions=1, std=0.0
        """
        self._set_measure_timeout(nplc=nplc, repetitions=repetitions)
        for attempt in range(2):
            try:
                # Use pymeasure's built-in method which properly configures sense function
                if repetitions <= 1:
                    self.instrument.measure_current(nplc=nplc, current=current, auto_range=auto_range)
                    return (self.instrument.current, 0.0)

                # Multiple measurements for software averaging
                measurements = []
                for _ in range(repetitions):
                    self.instrument.measure_current(nplc=nplc, current=current, auto_range=auto_range)
                    measurements.append(self.instrument.current)

                avg_current = np.mean(measurements)
                std_current = np.std(measurements, ddof=1) if len(measurements) > 1 else 0.0
                return (avg_current, std_current)
            except Exception as exc:
                if attempt == 0 and self._is_recoverable_comm_error(exc):
                    self._recover_comm_state()
                    continue
                raise
    
    def voltage_filter_count(self, count):
        """
        Set the voltage measurement filter count.
        
        Parameters
        ----------
        count : int
            Number of measurements to average (1-100)
        """
        self._voltage_filter_count = count
        # pymeasure has separate voltage and current filter counts
        if hasattr(self.instrument, 'voltage_filter_count'):
            self.instrument.voltage_filter_count = count
            # Enable the filter if setting a count > 1
            if count > 1 and hasattr(self.instrument, 'voltage_filter_state'):
                self.instrument.voltage_filter_state = 'ON'
    
    def ramp_to_current(self, target_current, steps=30, pause=20e-3):
        """
        Ramp current to target value.
        
        Parameters
        ----------
        target_current : float
            Target current in mA (will be converted to A)
        steps : int
            Number of ramp steps
        pause : float
            Pause time between steps in seconds
        """
        current_start = self._source_current / 1000.0  # Convert to A
        current_end = target_current / 1000.0  # Convert to A
        
        currents = np.linspace(current_start, current_end, steps)
        for current in currents:
            self.instrument.source_current = current
            time.sleep(pause)
        
        self._source_current = target_current
    
    def ramp_to_voltage(self, target_voltage, steps=30, pause=20e-3):
        """
        Ramp voltage to target value.
        
        Parameters
        ----------
        target_voltage : float
            Target voltage in V
        steps : int
            Number of ramp steps
        pause : float
            Pause time between steps in seconds
        """
        voltages = np.linspace(self._source_voltage, target_voltage, steps)
        for voltage in voltages:
            self.instrument.source_voltage = voltage
            time.sleep(pause)
        
        self._source_voltage = target_voltage
    
    def shutdown(self):
        """Safely shut down: ramp current to zero and disable source."""
        if self._source_current != 0:
            self.ramp_to_current(0)
        self.disable_source()
    
    def write(self, command):
        """Send a raw command to the instrument."""
        self.instrument.write(command)
    
    def query(self, command):
        """Query the instrument with a raw command."""
        return self.instrument.ask(command)



