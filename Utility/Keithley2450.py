import pyvisa
import time
import numpy as np



class Keithley2450:
    """
    Keithley 2450 SourceMeter driver using PyVISA (GPIB)

    Implements equivalent core functionality to PyMeasure Keithley2450 class,
    plus explicit control of:

        • 2-wire / 4-wire sensing
        • Front / Rear terminals
        • Source voltage/current
        • Measure voltage/current/resistance
        • Compliance limits
        • Output control
        • Autorange
        • Debug mode
    """

    def __init__(self, resource_name, timeout=5000, debug=False):
        self.debug = debug

        self.rm = pyvisa.ResourceManager()
        self.inst = self.rm.open_resource(resource_name)

        self.inst.timeout = timeout
        self.inst.write_termination = '\n'
        self.inst.read_termination = '\n'

        self._id = self.query("*IDN?")
        self.log(f"Connected to {self._id}")

    # --------------------------
    # Low level IO
    # --------------------------

    def write(self, cmd):
        self.log(f">> {cmd}")
        self.inst.write(cmd)

    def query(self, cmd):
        self.log(f">> {cmd}")
        response = self.inst.query(cmd)
        self.log(f"<< {response}")
        return response.strip()

    def log(self, msg):
        if self.debug:
            print(f"[Keithley2450] {msg}")

    # --------------------------
    # Terminal control
    # --------------------------

    def use_front_terminals(self):
        """Select front terminals"""
        self.write("ROUT:TERM FRONT")

    def use_rear_terminals(self):
        """Select rear terminals"""
        self.write("ROUT:TERM REAR")

    def get_terminals(self):
        return self.query("ROUT:TERM?")

    # --------------------------
    # Wire sense control
    # --------------------------

    def set_2wire(self):
        """
        2-wire sensing (local sense)
        """
        self.write("SENS:VOLT:RSEN OFF")
        self.write("SENS:CURR:RSEN OFF")
        self.write("SENS:RES:RSEN OFF")

    def set_4wire(self):
        """
        4-wire sensing (remote sense)
        """
        self.write("SENS:VOLT:RSEN ON")
        self.write("SENS:CURR:RSEN ON")
        self.write("SENS:RES:RSEN ON")

    def is_4wire(self):
        return bool(int(self.query("SENS:VOLT:RSEN?")))

    # --------------------------
    # Source mode
    # --------------------------

    def source_voltage(self):
        self.write("SOUR:FUNC VOLT")

    def source_current(self):
        self.write("SOUR:FUNC CURR")

    def get_source_mode(self):
        return self.query("SOUR:FUNC?")

    # --------------------------
    # Set source level
    # --------------------------

    def set_voltage(self, voltage):
        self.write(f"SOUR:VOLT {voltage}")

    def set_current(self, current):
        self.write(f"SOUR:CURR {current}")

    def get_voltage(self):
        return float(self.query("SOUR:VOLT?"))

    def get_current(self):
        return float(self.query("SOUR:CURR?"))

    # --------------------------
    # Compliance limits
    # --------------------------

    def set_voltage_compliance(self, limit):
        self.write(f"SENS:VOLT:PROT {limit}")

    def set_current_compliance(self, limit):
        self.write(f"SENS:CURR:PROT {limit}")

    # --------------------------
    # NPLC control
    # --------------------------

    def set_nplc(self, nplc):
        """
        Set integration time in power line cycles

        Typical values:
            0.01  fast, noisy
            0.1
            1     good compromise
            10    low noise
            100   ultra low noise
        """
        mode = self.get_measure_mode()

        if "VOLT" in mode:
            self.write(f"SENS:VOLT:NPLC {nplc}")

        elif "CURR" in mode:
            self.write(f"SENS:CURR:NPLC {nplc}")

        elif "RES" in mode:
            self.write(f"SENS:RES:NPLC {nplc}")


    def get_nplc(self):

        mode = self.get_measure_mode()

        if "VOLT" in mode:
            return float(self.query("SENS:VOLT:NPLC?"))

        elif "CURR" in mode:
            return float(self.query("SENS:CURR:NPLC?"))

        elif "RES" in mode:
            return float(self.query("SENS:RES:NPLC?"))

    # --------------------------
    # Filter control
    # --------------------------

    def enable_filter(self, count=10, filter_type="REP"):
        """
        filter_type:
            REP  repeating average
            MOV  moving average
        """

        mode = self.get_measure_mode()

        if "VOLT" in mode:
            base = "SENS:VOLT"

        elif "CURR" in mode:
            base = "SENS:CURR"

        elif "RES" in mode:
            base = "SENS:RES"

        self.write(f"{base}:AVER:TCON {filter_type}")
        self.write(f"{base}:AVER:COUN {count}")
        self.write(f"{base}:AVER ON")


    def disable_filter(self):

        mode = self.get_measure_mode()

        if "VOLT" in mode:
            self.write("SENS:VOLT:AVER OFF")

        elif "CURR" in mode:
            self.write("SENS:CURR:AVER OFF")

        elif "RES" in mode:
            self.write("SENS:RES:AVER OFF")

    # --------------------------
    # Trigger model control
    # --------------------------

    def trigger_immediate(self):
        """
        Single immediate trigger
        """
        self.write("TRIG:LOAD 'SimpleLoop', 1")
        self.write("INIT")


    def trigger_count(self, count):
        """
        Configure multiple trigger measurements
        """

        self.write(f"TRIG:LOAD 'SimpleLoop', {count}")


    def trigger_start(self):
        """
        Start trigger model
        """
        self.write("INIT")


    def wait_for_trigger_complete(self):

        self.write("*WAI")


    # --------------------------
    # Measurement mode
    # --------------------------

    def measure_voltage(self):
        self.write("SENS:FUNC 'VOLT'")

    def measure_current(self):
        self.write("SENS:FUNC 'CURR'")

    def measure_resistance(self):
        self.write("SENS:FUNC 'RES'")

    def get_measure_mode(self):
        return self.query("SENS:FUNC?")

    # --------------------------
    # Read measurement
    # --------------------------

    def read(self):
        """
        Returns float measurement
        """
        return float(self.query("READ?"))

    def measure(self):
        """
        Alias for read()
        """
        return self.read()

    # --------------------------
    # Autorange
    # --------------------------

    def enable_autorange_voltage(self):
        self.write("SENS:VOLT:RANG:AUTO ON")

    def disable_autorange_voltage(self):
        self.write("SENS:VOLT:RANG:AUTO OFF")

    def enable_autorange_current(self):
        self.write("SENS:CURR:RANG:AUTO ON")

    def disable_autorange_current(self):
        self.write("SENS:CURR:RANG:AUTO OFF")

    def enable_autorange_resistance(self):
        self.write("SENS:RES:RANG:AUTO ON")

    def disable_autorange_resistance(self):
        self.write("SENS:RES:RANG:AUTO OFF")

    # --------------------------
    # Output control
    # --------------------------

    def enable_output(self):
        self.write("OUTP ON")

    def disable_output(self):
        self.write("OUTP OFF")

    def output_on(self):
        self.enable_output()

    def output_off(self):
        self.disable_output()

    def is_output_on(self):
        return bool(int(self.query("OUTP?")))

    # --------------------------
    # Range control
    # --------------------------

    def set_voltage_range(self, range_value):
        self.write(f"SOUR:VOLT:RANG {range_value}")

    def set_current_range(self, range_value):
        self.write(f"SOUR:CURR:RANG {range_value}")

    # --------------------------
    # Buffer control
    # --------------------------

    def clear_buffer(self, buffer_name="defbuffer1"):

        self.write(f"TRAC:CLE '{buffer_name}'")


    def set_buffer_size(self, size, buffer_name="defbuffer1"):

        self.write(f"TRAC:POIN {size}, '{buffer_name}'")


    def get_buffer_size(self, buffer_name="defbuffer1"):

        return int(self.query(f"TRAC:POIN? '{buffer_name}'"))


    def read_buffer(self, buffer_name="defbuffer1"):

        data = self.query(f"TRAC:DATA? 1, {self.get_buffer_size(buffer_name)}, '{buffer_name}'")

        return [float(x) for x in data.split(",")]


    def voltage_sweep(self, start, stop, points, delay=0):

        self.write("SOUR:FUNC VOLT")

        self.write(f"SOUR:VOLT:STAR {start}")
        self.write(f"SOUR:VOLT:STOP {stop}")
        self.write(f"SOUR:VOLT:POIN {points}")

        self.write("SOUR:VOLT:MODE SWE")

        self.write(f"SOUR:DEL {delay}")

        self.clear_buffer()

        self.trigger_count(points)

        self.trigger_start()

        self.wait_for_trigger_complete()

        return self.read_buffer()

    def current_sweep(self, start, stop, points, delay=0):

        self.write("SOUR:FUNC CURR")

        self.write(f"SOUR:CURR:STAR {start}")
        self.write(f"SOUR:CURR:STOP {stop}")
        self.write(f"SOUR:CURR:POIN {points}")

        self.write("SOUR:CURR:MODE SWE")

        self.write(f"SOUR:DEL {delay}")

        self.clear_buffer()

        self.trigger_count(points)

        self.trigger_start()

        self.wait_for_trigger_complete()

        return self.read_buffer()

    def voltage_list_sweep(self, voltage_list, delay=0):

        list_str = ",".join(str(v) for v in voltage_list)

        self.write("SOUR:FUNC VOLT")

        self.write(f"SOUR:LIST:VOLT {list_str}")

        self.write("SOUR:VOLT:MODE LIST")

        self.write(f"SOUR:DEL {delay}")

        self.clear_buffer()

        self.trigger_count(len(voltage_list))

        self.trigger_start()

        self.wait_for_trigger_complete()

        return self.read_buffer()


    # --------------------------
    # Reset / clear
    # --------------------------

    def reset(self):
        self.write("*RST")

    def clear(self):
        self.write("*CLS")

    # --------------------------
    # Error handling
    # --------------------------

    def get_error(self):
        return self.query("SYST:ERR?")

    # --------------------------
    # Close
    # --------------------------

    def close(self):
        self.inst.close()
        self.rm.close()



"""
Example usage:

smu = Keithley2450("GPIB0::18::INSTR", debug=True)

smu.reset()

smu.use_rear_terminals()

smu.set_4wire()

smu.source_current()
smu.set_current(1e-6)

smu.measure_voltage()

smu.enable_output()

time.sleep(0.1)

voltage = smu.read()

print("Voltage:", voltage)

smu.disable_output()

smu.close()
"""

class MockKeithley2450:
    """
    Mock Keithley 2450 SourceMeter

    Fully compatible with real Keithley2450 class interface.

    Simulates:

        • Voltage/current source
        • Voltage/current/resistance measurement
        • 2-wire / 4-wire sensing
        • Trigger model
        • Buffer acquisition
        • Sweep mode
        • Filtering
        • NPLC noise scaling

    """

    def __init__(self, resource_name=None, debug=False):

        self.debug = debug

        self.id = "KEITHLEY INSTRUMENTS,MODEL 2450,MOCK,1.0"

        # state
        self.output_enabled = False

        self.source_mode = "CURR"
        self.measure_mode = "VOLT"

        self.source_value = 0.0

        self.terminals = "REAR"

        self.four_wire = True

        self.nplc = 1

        self.filter_enabled = False
        self.filter_count = 1

        # simulated DUT resistance (Ohms)
        self.device_resistance = 1000

        # buffer
        self.buffer = []

        self.buffer_size = 1024

        # trigger
        self.trigger_count_value = 1

        self.log("MockKeithley2450 initialized")

    # --------------------------
    # logging
    # --------------------------

    def log(self, msg):
        if self.debug:
            print(f"[MockKeithley2450] {msg}")

    # --------------------------
    # basic functions
    # --------------------------

    def reset(self):

        self.output_enabled = False
        self.source_value = 0
        self.buffer.clear()

        self.log("Reset")

    def clear(self):

        self.buffer.clear()

    def close(self):

        self.log("Closed")

    def get_error(self):

        return "0, No error"

    # --------------------------
    # terminal control
    # --------------------------

    def use_front_terminals(self):

        self.terminals = "FRONT"

    def use_rear_terminals(self):

        self.terminals = "REAR"

    def get_terminals(self):

        return self.terminals

    # --------------------------
    # wire control
    # --------------------------

    def set_2wire(self):

        self.four_wire = False

    def set_4wire(self):

        self.four_wire = True

    def is_4wire(self):

        return self.four_wire

    # --------------------------
    # source control
    # --------------------------

    def source_voltage(self):

        self.source_mode = "VOLT"

    def source_current(self):

        self.source_mode = "CURR"

    def get_source_mode(self):

        return self.source_mode

    def set_voltage(self, voltage):

        self.source_value = voltage

    def set_current(self, current):

        self.source_value = current

    def get_voltage(self):

        if self.source_mode == "VOLT":
            return self.source_value
        else:
            return self.source_value * self.device_resistance

    def get_current(self):

        if self.source_mode == "CURR":
            return self.source_value
        else:
            return self.source_value / self.device_resistance

    # --------------------------
    # compliance
    # --------------------------

    def set_voltage_compliance(self, limit):
        pass

    def set_current_compliance(self, limit):
        pass

    # --------------------------
    # measurement mode
    # --------------------------

    def measure_voltage(self):

        self.measure_mode = "VOLT"

    def measure_current(self):

        self.measure_mode = "CURR"

    def measure_resistance(self):

        self.measure_mode = "RES"

    def get_measure_mode(self):

        return self.measure_mode

    # --------------------------
    # noise model
    # --------------------------

    def get_noise(self):

        base_noise = 1e-6

        # NPLC improves noise
        noise = base_noise / np.sqrt(self.nplc)

        # 4-wire improves noise
        if self.four_wire:
            noise *= 0.5

        # filtering improves noise
        if self.filter_enabled:
            noise /= np.sqrt(self.filter_count)

        return noise

    # --------------------------
    # measurement simulation
    # --------------------------

    def simulate_measurement(self):

        noise = np.random.normal(0, self.get_noise())

        if self.source_mode == "CURR":

            voltage = self.source_value * self.device_resistance

            current = self.source_value

        else:

            voltage = self.source_value

            current = voltage / self.device_resistance

        if self.measure_mode == "VOLT":

            return voltage + noise

        elif self.measure_mode == "CURR":

            return current + noise

        elif self.measure_mode == "RES":

            return self.device_resistance + noise

    # --------------------------
    # read
    # --------------------------

    def read(self):

        if not self.output_enabled:
            return 0

        time.sleep(self.nplc * 0.02)

        return self.simulate_measurement()

    def measure(self):

        return self.read()

    # --------------------------
    # output control
    # --------------------------

    def enable_output(self):

        self.output_enabled = True

    def disable_output(self):

        self.output_enabled = False

    def output_on(self):

        self.enable_output()

    def output_off(self):

        self.disable_output()

    def is_output_on(self):

        return self.output_enabled

    # --------------------------
    # NPLC
    # --------------------------

    def set_nplc(self, nplc):

        self.nplc = nplc

    def get_nplc(self):

        return self.nplc

    # --------------------------
    # filter
    # --------------------------

    def enable_filter(self, count=10, filter_type="REP"):

        self.filter_enabled = True
        self.filter_count = count

    def disable_filter(self):

        self.filter_enabled = False

    # --------------------------
    # buffer control
    # --------------------------

    def clear_buffer(self, buffer_name="defbuffer1"):

        self.buffer.clear()

    def set_buffer_size(self, size, buffer_name="defbuffer1"):

        self.buffer_size = size

    def get_buffer_size(self, buffer_name="defbuffer1"):

        return len(self.buffer)

    def read_buffer(self, buffer_name="defbuffer1"):

        return self.buffer.copy()

    # --------------------------
    # trigger model
    # --------------------------

    def trigger_count(self, count):

        self.trigger_count_value = count

    def trigger_start(self):

        self.buffer.clear()

        for _ in range(self.trigger_count_value):

            self.buffer.append(self.read())

    def trigger_immediate(self):

        self.trigger_count(1)
        self.trigger_start()

    def wait_for_trigger_complete(self):

        pass

    # --------------------------
    # sweeps
    # --------------------------

    def voltage_sweep(self, start, stop, points, delay=0):

        voltages = np.linspace(start, stop, points)

        self.source_voltage()

        self.buffer.clear()

        for v in voltages:

            self.set_voltage(v)

            time.sleep(delay)

            self.buffer.append(self.read())

        return self.read_buffer()

    def current_sweep(self, start, stop, points, delay=0):

        currents = np.linspace(start, stop, points)

        self.source_current()

        self.buffer.clear()

        for i in currents:

            self.set_current(i)

            time.sleep(delay)

            self.buffer.append(self.read())

        return self.read_buffer()

    def voltage_list_sweep(self, voltage_list, delay=0):

        self.source_voltage()

        self.buffer.clear()

        for v in voltage_list:

            self.set_voltage(v)

            time.sleep(delay)

            self.buffer.append(self.read())

        return self.read_buffer()
