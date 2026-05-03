import random
from time import perf_counter, sleep
import pyvisa
import random
from time import perf_counter, sleep


def _normalize_keithley_channel(channel):
    normalized = str(channel).lower()
    if normalized not in ["a", "b"]:
        raise ValueError("Channel must be 'a' or 'b' for IV measurements")
    return normalized


def _normalize_iv_mode(mode):
    normalized = str(mode).lower()
    aliases = {
        "source_current": "source_current",
        "current": "source_current",
        "i": "source_current",
        "source_voltage": "source_voltage",
        "voltage": "source_voltage",
        "v": "source_voltage",
    }
    if normalized not in aliases:
        raise ValueError("mode must be 'source_current' or 'source_voltage'")
    return aliases[normalized]


def _append_unique_value(values, value):
    if not values or abs(values[-1] - value) > 1e-15:
        values.append(float(value))


def _generate_linear_sweep(start, stop, step):
    if step == 0:
        raise ValueError("step must be non-zero")

    start = float(start)
    stop = float(stop)
    step = abs(float(step))
    direction = 1.0 if stop >= start else -1.0
    signed_step = step * direction
    values = []
    current = start
    tolerance = step * 1e-9 + 1e-15

    while True:
        _append_unique_value(values, current)
        if abs(current - stop) <= tolerance:
            break

        next_value = current + signed_step
        if direction > 0 and next_value > stop:
            current = stop
        elif direction < 0 and next_value < stop:
            current = stop
        else:
            current = next_value

    return values


def _build_iv_setpoints(start=None, stop=None, step=None, setpoints=None,
                        max_value=None, min_value=None, include_zero_end=True):
    if setpoints is not None:
        values = [float(value) for value in setpoints]
        if not values:
            raise ValueError("setpoints must not be empty")
        return values

    if max_value is not None or min_value is not None:
        if step is None:
            raise ValueError("step is required for bipolar IV sweeps")

        if max_value is None and min_value is None:
            raise ValueError("At least one of max_value or min_value must be provided")

        if max_value is None:
            max_value = abs(float(min_value))
        if min_value is None:
            min_value = -abs(float(max_value))

        max_value = float(max_value)
        min_value = float(min_value)
        values = [0.0]
        for segment in [
            _generate_linear_sweep(0.0, max_value, step),
            _generate_linear_sweep(max_value, min_value, step),
            _generate_linear_sweep(min_value, 0.0, step) if include_zero_end else [],
        ]:
            for value in segment:
                _append_unique_value(values, value)
        return values

    if start is None or stop is None or step is None:
        raise ValueError(
            "Provide either setpoints, start/stop/step, or max_value/min_value/step"
        )

    return _generate_linear_sweep(start, stop, step)


def _average(values):
    if not values:
        return 0.0, 0.0
    mean_value = sum(values) / len(values)
    if len(values) == 1:
        return mean_value, 0.0
    variance = sum((value - mean_value) ** 2 for value in values) / (len(values) - 1)
    return mean_value, variance ** 0.5


def _safe_resistance(voltage, current):
    if abs(current) <= 1e-15:
        return None
    return voltage / current


def _parse_keithley_numeric_list(response, expected_count=None):
    cleaned = str(response).replace("\r", " ").replace("\n", " ").replace("\t", ",")
    parts = []
    for chunk in cleaned.split(","):
        item = chunk.strip()
        if not item:
            continue
        parts.extend(token for token in item.split() if token)

    values = []
    for token in parts:
        values.append(float(token))

    if expected_count is not None and len(values) != expected_count:
        raise ValueError(
            "Expected {0} values from instrument, got {1}: {2}".format(
                expected_count, len(values), response
            )
        )
    return values

class MockKeithley2600:
    def __init__(self):
        self.address = 'Mock::Keithley::INSTR'
        self.connected = False
        self.current_a = 0.0
        self.current_b = 0.0
        self.voltage_a = 0.0
        self.voltage_b = 0.0

    def connect(self):
        """Simulate connecting to the Keithley 2600."""
        self.connected = True
        return "MOCK KEITHLEY 2600 CONNECTED"

    def disconnect(self):
        self.connected = False
        return True

    def write(self, command):
        print(f"Mock write: {command}")

    def read(self):
        return str(random.uniform(0, 1))

    def apply_current(self, current_range=None, compliance_voltage=0.1, Ch="a"):
        if Ch in ["a", "ab"]:
            print(f"Set current range: {current_range}, Compliance voltage: {compliance_voltage} on channel A")
        if Ch in ["b", "ab"]:
            print(f"Set current range: {current_range}, Compliance voltage: {compliance_voltage} on channel B")

    def apply_voltage(self, voltage_range=None, compliance_current=0.1, Ch="a"):
        if Ch in ["a", "ab"]:
            print(f"Set voltage range: {voltage_range}, Compliance current: {compliance_current} on channel A")
        if Ch in ["b", "ab"]:
            print(f"Set voltage range: {voltage_range}, Compliance current: {compliance_current} on channel B")

    def set_current(self, I, Ch="a"):
        if Ch in ["a", "ab"]:
            self.current_a = I
            print(f"Set current to {I} A on channel A")
        if Ch in ["b", "ab"]:
            self.current_b = I
            print(f"Set current to {I} A on channel B")

    def set_voltage(self, V, Ch="a"):
        if Ch in ["a", "ab"]:
            self.voltage_a = V
            print(f"Set voltage to {V} V on channel A")
        if Ch in ["b", "ab"]:
            self.voltage_b = V
            print(f"Set voltage to {V} V on channel B")

    def measure_current(self, nplc=1, current=0.00001, auto_range=True, Ch="a"):
        """Mock function to simulate current measurement with noise."""
        if Ch in ["a", "ab"]:
            self.write(f"smua.measure.nplc = {nplc}")
            self.write(f"smua.measure.autorangei = {'smua.AUTORANGE_ON' if auto_range else 'smua.AUTORANGE_OFF'}")
            self.set_current(current, "a")

        if Ch in ["b", "ab"]:
            self.write(f"smub.measure.nplc = {nplc}")
            self.write(f"smub.measure.autorangei = {'smub.AUTORANGE_ON' if auto_range else 'smub.AUTORANGE_OFF'}")
            self.set_current(current, "b")

        if Ch not in ["a", "b", "ab"]:
            print("Not a valid channel")
            return None

        sleep(0.1)  # Simulating measurement delay
        result = {}
        if Ch in ["a", "ab"]:
            result["a"] = self.current_a + random.gauss(0, 1e-9)  # Adding small noise
        if Ch in ["b", "ab"]:
            result["b"] = self.current_b + random.gauss(0, 1e-9)

        return result

    def measure_voltage(self, nplc=1, auto_range=True, Ch="a"):
        """Mock function to simulate voltage measurement with noise."""
        if Ch in ["a", "ab"]:
            self.write(f"smua.measure.nplc = {nplc}")
            self.write(f"smua.measure.autorangev = {'smua.AUTORANGE_ON' if auto_range else 'smua.AUTORANGE_OFF'}")
            self.voltage_a = random.gauss(0, 0.01)  # Simulated voltage with noise

        if Ch in ["b", "ab"]:
            self.write(f"smub.measure.nplc = {nplc}")
            self.write(f"smub.measure.autorangev = {'smub.AUTORANGE_ON' if auto_range else 'smub.AUTORANGE_OFF'}")
            self.voltage_b = random.gauss(0, 0.01)

        if Ch not in ["a", "b", "ab"]:
            print("Not a valid channel")
            return None

        sleep(0.1)  # Simulating measurement delay
        result = {}
        if Ch in ["a", "ab"]:
            result["a"] = self.voltage_a
        if Ch in ["b", "ab"]:
            result["b"] = self.voltage_b
        return result

    def get_resistance(self, Ch="a"):
        if Ch == "a":
            sleep(0.1)
            print(f"Measuring with channel {Ch}")
            return random.uniform(0, 1)
        elif Ch == "b":
            sleep(0.1)
            print(f"Measuring with channel {Ch}")
            return random.uniform(0, 1)
        elif Ch == "ab":
            sleep(0.1)
            print(f"Measuring with channel {Ch}")
            return random.uniform(0, 1), random.uniform(0, 1)
        else:
            print("Not a valid channel")
            return None

    def reset(self):
        print(f"The a,b chanels are reset")
        return True

    def measure(self, script_name):
        sleep(0.1)
        print(f"Measuring with script {script_name}")
        return [[random.uniform(0, 1) for _ in range(5)]]

    def set_4wires(self, wires4=True, Ch="a"):
        if Ch in ["a", "ab"]:
            print(f"4-wire mode: {'ON' if wires4 else 'OFF'} on channel A")
        if Ch in ["b", "ab"]:
            print(f"4-wire mode: {'ON' if wires4 else 'OFF'} on channel B")

    def reset(self):
        print("The a, b channels are reset")
        return True
    
    def enable_source(self, Ch="a"):
        """Mock function to enable the output source for the given channel."""
        if Ch in ["a", "ab"]:
            self.write("smua.source.output = smua.OUTPUT_ON")
            print("Source enabled on channel A")

        if Ch in ["b", "ab"]:
            self.write("smub.source.output = smub.OUTPUT_ON")
            print("Source enabled on channel B")

        if Ch not in ["a", "b", "ab"]:
            print("Not a valid channel")

    def disable_source(self, Ch="a"):
        """Mock function to disable the output source for the given channel."""
        if Ch in ["a", "ab"]:
            self.write("smua.source.output = smua.OUTPUT_OFF")
            print("Source disabled on channel A")

        if Ch in ["b", "ab"]:
            self.write("smub.source.output = smub.OUTPUT_OFF")
            print("Source disable on channel B")

        if Ch not in ["a", "b", "ab"]:
            print("Not a valid channel")

    def set_voltage_compliance(self, limit_v, Ch="a"):
        if Ch == "a":
            self.write("smua.source.limitv = {}".format(limit_v))
        elif Ch == "b":
            self.write("smub.source.limitv = {}".format(limit_v))
        elif Ch == "ab":
            self.write("smua.source.limitv = {}".format(limit_v))
            self.write("smub.source.limitv = {}".format(limit_v))
        else:
            print("Not a valid channel")            

    def iv_measurement(self, mode="source_current", start=None, stop=None, step=None,
                       setpoints=None, max_value=None, min_value=None, Ch="a",
                       source_range=None, measure_range=None, compliance=None,
                       nplc=1, auto_range=True, settle_time=0.0, measure_delay=None,
                       repetitions=1, include_zero_end=True, keep_output=False,
                       reset_to_zero=True, use_4wire=None):
        channel = _normalize_keithley_channel(Ch)
        normalized_mode = _normalize_iv_mode(mode)
        points = _build_iv_setpoints(
            start=start,
            stop=stop,
            step=step,
            setpoints=setpoints,
            max_value=max_value,
            min_value=min_value,
            include_zero_end=include_zero_end,
        )

        if repetitions < 1:
            raise ValueError("repetitions must be at least 1")

        if compliance is None:
            compliance = 20.0 if normalized_mode == "source_current" else 0.1

        if use_4wire is not None:
            self.set_4wires(wires4=bool(use_4wire), Ch=channel)

        if normalized_mode == "source_current":
            self.apply_current(current_range=source_range, compliance_voltage=compliance, Ch=channel)
        else:
            self.apply_voltage(voltage_range=source_range, compliance_current=compliance, Ch=channel)

        start_time = 0.0
        result_points = []

        try:
            self.enable_source(Ch=channel)
            for index, setpoint in enumerate(points):
                if normalized_mode == "source_current":
                    self.set_current(setpoint, Ch=channel)
                else:
                    self.set_voltage(setpoint, Ch=channel)

                if settle_time > 0:
                    sleep(settle_time)

                current_reads = []
                voltage_reads = []
                for _ in range(repetitions):
                    current_value = self.current_a if channel == "a" else self.current_b
                    voltage_value = self.voltage_a if channel == "a" else self.voltage_b
                    current_reads.append(current_value + random.gauss(0, 1e-9))
                    voltage_reads.append(voltage_value + random.gauss(0, 1e-6))

                avg_current, std_current = _average(current_reads)
                avg_voltage, std_voltage = _average(voltage_reads)
                result_points.append({
                    "index": index,
                    "setpoint": float(setpoint),
                    "current_a": avg_current,
                    "current_std_a": std_current,
                    "voltage_v": avg_voltage,
                    "voltage_std_v": std_voltage,
                    "resistance_ohm": _safe_resistance(avg_voltage, avg_current),
                    "timestamp_s": start_time,
                    "compliance_hit": False,
                })
                start_time += float(settle_time)
        finally:
            if reset_to_zero:
                if normalized_mode == "source_current":
                    self.set_current(0.0, Ch=channel)
                else:
                    self.set_voltage(0.0, Ch=channel)
            if not keep_output:
                self.disable_source(Ch=channel)

        return {
            "meta": {
                "instrument": "MockKeithley2600",
                "channel": channel,
                "mode": normalized_mode,
                "source_units": "A" if normalized_mode == "source_current" else "V",
                "measure_units": "V" if normalized_mode == "source_current" else "A",
                "setpoint_count": len(points),
                "repetitions": int(repetitions),
                "nplc": float(nplc),
                "auto_range": bool(auto_range),
                "source_range": source_range,
                "measure_range": measure_range,
                "compliance": float(compliance),
                "settle_time_s": float(settle_time),
                "measure_delay_s": None if measure_delay is None else float(measure_delay),
                "use_4wire": use_4wire,
            },
            "points": result_points,
            "arrays": {
                "setpoint": [point["setpoint"] for point in result_points],
                "current_a": [point["current_a"] for point in result_points],
                "voltage_v": [point["voltage_v"] for point in result_points],
                "resistance_ohm": [point["resistance_ohm"] for point in result_points],
                "timestamp_s": [point["timestamp_s"] for point in result_points],
            },
        }


'''
class MockKeithley2600:
    def __init__(self):
        self.address = 'Mock::Keithley::INSTR'
        self.connected = False

    def connect(self):
        """Simulate connecting to the Keithley 2600."""
        self.connected = True
        return "MOCK KEITHLEY 2600 CONNECTED"

    def disconnect(self):
        self.connected = False
        return True

    def write(self, command):
        print(f"Mock write: {command}")

    def read(self):
        return str(random.uniform(0, 1))

    def apply_current(self, current_range=None, compliance_voltage=0.1, Ch="a"):
        if Ch == "a":
            print(f"Set current range: {current_range}, Compliance voltage: {compliance_voltage} on channel A")
        elif Ch == "b":
            print(f"Set current range: {current_range}, Compliance voltage: {compliance_voltage} on channel B")
        elif Ch == "ab":
            print(f"Set current range: {current_range}, Compliance voltage: {compliance_voltage} on channels A and B")
        else:
            print("Not a valid channel")

    def apply_voltage(self, voltage_range=None, compliance_current=0.1, Ch="a"):
        if Ch == "a":
            print(f"Set voltage range: {voltage_range}, Compliance current: {compliance_current} on channel A")
        elif Ch == "b":
            print(f"Set voltage range: {voltage_range}, Compliance current: {compliance_current} on channel B")
        elif Ch == "ab":
            print(f"Set voltage range: {voltage_range}, Compliance current: {compliance_current} on channels A and B")
        else:
            print("Not a valid channel")

    def set_current(self, I, Ch="a"):
        if Ch == "a":
            print(f"Set current to {I} on channel A")
        elif Ch == "b":
            print(f"Set current to {I} on channel B")
        elif Ch == "ab":
            print(f"Set current to {I} on channels A and B")
        else:
            print("Not a valid channel")

    def set_voltage(self, V, Ch="a"):
        if Ch == "a":
            print(f"Set voltage to {V} on channel A")
        elif Ch == "b":
            print(f"Set voltage to {V} on channel B")
        elif Ch == "ab":
            print(f"Set voltage to {V} on channels A and B")
        else:
            print("Not a valid channel")

    def measure(self, script_name):
        sleep(0.1)
        print(f"Measuring with script {script_name}")
        return [[random.uniform(0, 1) for _ in range(5)]]

    def set_4wires(self, wires4=True, Ch="a"):
        if Ch == "a":
            print(f"4-wire mode: {'ON' if wires4 else 'OFF'} on channel A")
        elif Ch == "b":
            print(f"4-wire mode: {'ON' if wires4 else 'OFF'} on channel B")
        elif Ch == "ab":
            print(f"4-wire mode: {'ON' if wires4 else 'OFF'} on channels A and B")
        else:
            print("Not a valid channel")

    def get_resistance(self, Ch="a"):
        if Ch == "a":
            sleep(0.1)
            print(f"Measuring with channel {Ch}")
            return random.uniform(0, 1)
        elif Ch == "b":
            sleep(0.1)
            print(f"Measuring with channel {Ch}")
            return random.uniform(0, 1)
        elif Ch == "ab":
            sleep(0.1)
            print(f"Measuring with channel {Ch}")
            return random.uniform(0, 1), random.uniform(0, 1)
        else:
            print("Not a valid channel")

    def reset(self):
        print(f"The a,b chanels are reset")
        return True
'''


class Keithley2600():
    def __init__(self):
        self.address = 'GPIB0::26::INSTR'
        self.keithley = None
        self.connected = False
        
    
    def connect(self):
        rm = pyvisa.ResourceManager()
        self.keithley = rm.open_resource(self.address)
        self.connected = True
        self.keithley.clear()
        #self.keithley.clear_queue()
        return True
    
    def disconnect(self):
        self.keithley.close()
        self.IsConnected=False
        return True

    def reset(self):
        self.write("smua.reset()")
        self.write("smub.reset()")
        return True

    def write(self,st):
        self.keithley.write(st)

    def read(self):
        return self.keithley.read()

    def load_script(self,script_name, script_text, num_of_points, script_buffer, delay_time):
        self.script_name = script_name
        self.script_text = script_text
        self.script_delay_time = int(delay_time)
        self.script_num_of_points = int(num_of_points)
        self.script_buffer = int(script_buffer)

        full_script = "loadscript {0}\r\n{1}\r\nendscript".format(self.script_name, self.script_text)
        row_split = full_script.split('\n');
        i = 0;
        while row_split[i] != "endscript":
            self.write(row_split[i])
            #print(row_split[i])
            i = i + 1

        self.write(row_split[i])
        #print(row_split[i])
        self.write("{0}.save()".format(self.script_name))
        return "{0} was Loaded".format(self.script_name)
    

    def call_script(self,script_name):
        self.write("{0}.run()".format(script_name))
        return "{0} is running".format(script_name)
    

    def read_data(self):
        self.data = []
        for i in range(self.script_num_of_points):
            out = self.keithley._read_raw(size=self.script_buffer * 32)
            sout = out.decode().replace('\n', '').split(',')
            fout = list()
            for istr in sout:
                fout.append(float(istr))
            self.data.append(fout)
        return self.data
    

    def measure(self,script_name):
        self.call_script(script_name)
        sleep(self.script_delay_time)
        return self.read_data()
        

    def apply_current(self, current_range=None, compliance_voltage=0.1, Ch="a"):
        if Ch == "a":
            self.write("smua.source.func = smua.OUTPUT_DCAMPS")
            if current_range:
                self.write("smua.source.rangei = {0}".format(current_range))
            else:
                self.write("smua.source.autorangei = smua.AUTORANGE_ON")
            self.write("smua.source.limitv = {0}".format(compliance_voltage))
        elif Ch == "b":
            self.write("smub.source.func = smub.OUTPUT_DCAMPS")
            if current_range:
                self.write("smub.source.rangei = {0}".format(current_range))
            else:
                self.write("smub.source.autorangei = smub.AUTORANGE_ON")
            self.write("smub.source.limitv = {0}".format(compliance_voltage))
        elif Ch == "ab":
            self.write("smua.source.func = smua.OUTPUT_DCAMPS")
            self.write("smub.source.func = smub.OUTPUT_DCAMPS")
            if current_range:
                self.write("smua.source.rangei = {0}".format(current_range))
                self.write("smub.source.rangei = {0}".format(current_range))
            else:
                self.write("smua.source.autorangei = smua.AUTORANGE_ON")
                self.write("smub.source.autorangei = smub.AUTORANGE_ON")
            self.write("smua.source.limitv = {0}".format(compliance_voltage))
            self.write("smub.source.limitv = {0}".format(compliance_voltage))
        else:
            print("Not a valid channel")


    def apply_voltage(self, voltage_range=None, compliance_current=0.1, Ch="a"):
        if Ch == "a":
            self.write("smua.source.func = smua.OUTPUT_DCVOLTS")
            if voltage_range:
                self.write("smua.source.rangev = {0}".format(voltage_range))
            else:
                self.write("smua.source.autorangev = smua.AUTORANGE_ON")
            self.write("smua.source.limiti = {0}".format(compliance_current))
        elif Ch == "b":
            self.write("smub.source.func = smub.OUTPUT_DCVOLTS")
            if voltage_range:
                self.write("smub.source.rangev = {0}".format(voltage_range))
            else:
                self.write("smub.source.autorangev = smub.AUTORANGE_ON")
            self.write("smub.source.limiti = {0}".format(compliance_current))
        elif Ch == "ab":
            self.write("smua.source.func = smua.OUTPUT_DCVOLTS")
            self.write("smub.source.func = smub.OUTPUT_DCVOLTS")
            if voltage_range:
                self.write("smua.source.rangev = {0}".format(voltage_range))
                self.write("smub.source.rangev = {0}".format(voltage_range))
            else:
                self.write("smua.source.autorangev = smua.AUTORANGE_ON")
                self.write("smub.source.autorangev = smub.AUTORANGE_ON")
            self.write("smua.source.limiti = {0}".format(compliance_current))
            self.write("smub.source.limiti = {0}".format(compliance_current))
        else:
            print("Not a valid channel")


    def measure_current(self, nplc=1, current=0.00001, auto_range=True, Ch="a"):
        if Ch == "a":
            self.write("smua.measure.nplc = {0}".format(nplc))
            if auto_range:
                self.write("smua.measure.autorangei = smua.AUTORANGE_ON")
            else:
                self.write("smua.measure.autorangei = smua.AUTORANGE_OFF")
            self.set_current(current, "a")
        elif Ch == "b":
            self.write("smub.measure.nplc = {0}".format(nplc))
            if auto_range:
                self.write("smub.measure.autorangei = smub.AUTORANGE_ON")
            else:
                self.write("smub.measure.autorangei = smub.AUTORANGE_OFF")
            self.set_current(current, "b")
        elif Ch == "ab":
            self.write("smua.measure.nplc = {0}".format(nplc))
            self.write("smub.measure.nplc = {0}".format(nplc))
            if auto_range:
                self.write("smua.measure.autorangei = smua.AUTORANGE_ON")
                self.write("smub.measure.autorangei = smub.AUTORANGE_ON")
            else:
                self.write("smua.measure.autorangei = smua.AUTORANGE_OFF")
                self.write("smub.measure.autorangei = smub.AUTORANGE_OFF")
            self.set_current(current, "a")
            self.set_current(current, "b")
        else:
            print("Not a valid channel")


    def measure_voltage(self, nplc=1, auto_range=True, Ch="a"):
        if Ch == "a":
            self.write("smua.measure.nplc = {0}".format(nplc))
            if auto_range:
                self.write("smua.measure.autorangev = smua.AUTORANGE_ON")
            else:
                self.write("smua.measure.autorangev = smua.AUTORANGE_OFF")
        elif Ch == "b":
            self.write("smub.measure.nplc = {0}".format(nplc))
            if auto_range:
                self.write("smub.measure.autorangev = smub.AUTORANGE_ON")
            else:
                self.write("smub.measure.autorangev = smub.AUTORANGE_OFF")
        elif Ch == "ab":
            self.write("smua.measure.nplc = {0}".format(nplc))
            self.write("smub.measure.nplc = {0}".format(nplc))
            if auto_range:
                self.write("smua.measure.autorangev = smua.AUTORANGE_ON")
                self.write("smub.measure.autorangev = smub.AUTORANGE_ON")
            else:
                self.write("smua.measure.autorangev = smua.AUTORANGE_OFF")
                self.write("smub.measure.autorangev = smub.AUTORANGE_OFF")
        else:
            print("Not a valid channel")


    def set_current(self, I, Ch="a"):
        if Ch == "a":
            self.write("smua.source.leveli = {0}".format(I))
        elif Ch == "b":
            self.write("smub.source.leveli = {0}".format(I))
        elif Ch == "ab":
            self.write("smua.source.leveli = {0}".format(I))
            self.write("smub.source.leveli = {0}".format(I))
        else:
            print("Not a valid channel")


    def set_voltage(self, V, Ch="a"):
        if Ch == "a":
            self.write("smua.source.levelv = {0}".format(V))
        elif Ch == "b":
            self.write("smub.source.levelv = {0}".format(V))
        elif Ch == "ab":
            self.write("smua.source.levelv = {0}".format(V))
            self.write("smub.source.levelv = {0}".format(V))
        else:
            print("Not a valid channel")


    def set_current_range(self, current_range, Ch="a"):
        if Ch == "a":
            self.write("smua.measure.rangei = {0}".format(current_range))
        elif Ch == "b":
            self.write("smub.measure.rangei = {0}".format(current_range))
        elif Ch == "ab":
            self.write("smua.measure.rangei = {0}".format(current_range))
            self.write("smub.measure.rangei = {0}".format(current_range))
        else:
            print("Not a valid channel")


    def set_voltage_range(self, voltage_range, Ch="a"):
        if Ch == "a":
            self.write("smua.measure.rangev = {0}".format(voltage_range))
        elif Ch == "b":
            self.write("smub.measure.rangev = {0}".format(voltage_range))
        elif Ch == "ab":
            self.write("smua.measure.rangev = {0}".format(voltage_range))
            self.write("smub.measure.rangev = {0}".format(voltage_range))
        else:
            print("Not a valid channel")

    
        
    def set_nplc(self,nplc,Ch="a"):
        if Ch == "a":
            self.write("smua.measure.nplc = {0}".format(nplc))
        elif Ch == "b":
            self.write("smub.measure.nplc = {0}".format(nplc))
        elif Ch == "ab":
            self.write("smua.measure.nplc = {0}".format(nplc))
            self.write("smub.measure.nplc = {0}".format(nplc))
        else:
            print("Not a valide channel")                
        
        
    def set_voltage_compliance(self,limit_v, Ch="a"):
        if Ch == "a":
            self.write("smua.source.limitv = {0}".format(limit_v))
        elif Ch == "b":
            self.write("smub.source.limitv = {0}".format(limit_v))
        elif Ch == "ab":
            self.write("smua.source.limitv = {0}".format(limit_v))
            self.write("smub.source.limitv = {0}".format(limit_v))
        else:
            print("Not a valide channel")                

        
    def set_current_compliance(self,limit_i,Ch="a"):
        if Ch == "a":
            self.write("smua.source.limiti = {0}".format(limit_i))
        elif Ch == "b":
            self.write("smub.source.limiti = {0}".format(limit_i))
        elif Ch == "ab":
            self.write("smua.source.limiti = {0}".format(limit_i))
            self.write("smub.source.limiti = {0}".format(limit_i))
        else:
            print("Not a valide channel")        
            
        
    def enable_source(self,Ch="a"):
        if Ch == "a":
            self.write("smua.source.output = smua.OUTPUT_ON")
        elif Ch == "b":
            self.write("smub.source.output = smub.OUTPUT_ON")
        elif Ch == "ab":
            self.write("smua.source.output = smua.OUTPUT_ON")
            self.write("smub.source.output = smub.OUTPUT_ON")
        else:
            print("Not a valide channel")
        
    def disable_source(self,Ch='a'):
        if Ch == 'a':
            self.write("smua.source.output = smua.OUTPUT_OFF")
        elif Ch == 'b':
            self.write("smub.source.output = smub.OUTPUT_OFF")
        elif Ch == 'ab':
            self.write("smua.source.output = smub.OUTPUT_OFF")
            self.write("smub.source.output = smub.OUTPUT_OFF")
        else:
            print("Not a valide channel")

    
    def get_voltage(self,Ch='a'):
        if Ch == 'a':
            self.write("print(smua.measure.v())")
            sleep(0.001)
            return self.read()
        elif Ch == 'b':
            self.write("print(smub.measure.v())")
            sleep(0.001)
            return self.read()
        elif Ch == 'ab':
            self.write("print(smua.measure.v())")
            self.write("print(smub.measure.v())")
        else:
            print("Not a valide channel")


    def get_resistance(self,Ch='a'):
        if Ch == 'a':
            self.write("print(smua.measure.r())")
            sleep(0.001)
            return self.read()
        elif Ch == 'b':
            self.write("print(smub.measure.r())")
            sleep(0.001)
            return self.read()
        elif Ch == 'ab':
            self.write("print(smua.measure.r())")
            res_a = self.read()
            self.write("print(smub.measure.r())")
            res_b = self.read()
            return res_a, res_b
        else:
            print("Not a valide channel")

    
    def get_current(self, Ch='a'):
        if Ch == 'a':
            self.write("print(smua.measure.i())")
            sleep(0.001)
            return self.read()
        elif Ch == 'b':
            self.write("print(smub.measure.i())")
            sleep(0.001)
            return self.read()
        elif Ch == 'ab':
            self.write("print(smua.measure.i())")
            self.write("print(smub.measure.i())")
        else:
            print("Not a valide channel")

    
    def set_4wires(self,wires4=True,Ch='a'):
        if Ch == 'a':
            if wires4:
                self.write("smua.sense = smua.SENSE_REMOTE")
            else:
                self.write("smua.sense = smua.SENSE_LOCAL")
        elif Ch == 'b':
            if wires4:
                self.write("smub.sense = smub.SENSE_REMOTE")
            else:
                self.write("smub.sense = smub.SENSE_LOCAL")
        elif Ch == 'ab':
            if wires4:
                self.write("smub.sense = smua.SENSE_REMOTE")
                self.write("smub.sense = smub.SENSE_REMOTE")
            else:
                self.write("smua.sense = smua.SENSE_LOCAL")        
                self.write("smub.sense = smub.SENSE_LOCAL")        
        else:
            print("Not a valide channel")
    
    
    def disable_beep(self):
        self.write("beeper.enable = beeper.OFF")

    def _configure_iv_measurement(self, channel, mode, nplc, auto_range,
                                  measure_range=None, measure_delay=None):
        self.write("smu{0}.measure.count = 1".format(channel))
        self.write("smu{0}.measure.nplc = {1}".format(channel, nplc))

        if measure_delay is None:
            self.write("smu{0}.measure.delay = smu{0}.DELAY_OFF".format(channel))
        else:
            self.write("smu{0}.measure.delay = {1}".format(channel, measure_delay))

        primary_quantity = "v" if mode == "source_current" else "i"
        if auto_range:
            self.write("smu{0}.measure.autorange{1} = smu{0}.AUTORANGE_ON".format(channel, primary_quantity))
        elif measure_range is not None:
            self.write("smu{0}.measure.autorange{1} = smu{0}.AUTORANGE_OFF".format(channel, primary_quantity))
            self.write("smu{0}.measure.range{1} = {2}".format(channel, primary_quantity, measure_range))

    def _measure_iv_once(self, channel):
        self.write("print(smu{0}.measure.iv())".format(channel))
        response = self.read()
        current_value, voltage_value = _parse_keithley_numeric_list(response, expected_count=2)
        return current_value, voltage_value

    def iv_measurement(self, mode="source_current", start=None, stop=None, step=None,
                       setpoints=None, max_value=None, min_value=None, Ch="a",
                       source_range=None, measure_range=None, compliance=None,
                       nplc=1, auto_range=True, settle_time=0.0, measure_delay=None,
                       repetitions=1, include_zero_end=True, keep_output=False,
                       reset_to_zero=True, use_4wire=None):
        channel = _normalize_keithley_channel(Ch)
        normalized_mode = _normalize_iv_mode(mode)
        points = _build_iv_setpoints(
            start=start,
            stop=stop,
            step=step,
            setpoints=setpoints,
            max_value=max_value,
            min_value=min_value,
            include_zero_end=include_zero_end,
        )

        if repetitions < 1:
            raise ValueError("repetitions must be at least 1")

        if compliance is None:
            compliance = 20.0 if normalized_mode == "source_current" else 0.1

        if use_4wire is not None:
            self.set_4wires(wires4=bool(use_4wire), Ch=channel)

        if normalized_mode == "source_current":
            self.apply_current(current_range=source_range, compliance_voltage=compliance, Ch=channel)
        else:
            self.apply_voltage(voltage_range=source_range, compliance_current=compliance, Ch=channel)

        self._configure_iv_measurement(
            channel=channel,
            mode=normalized_mode,
            nplc=nplc,
            auto_range=auto_range,
            measure_range=measure_range,
            measure_delay=measure_delay,
        )

        start_timestamp = perf_counter()
        result_points = []

        try:
            self.enable_source(Ch=channel)
            for index, setpoint in enumerate(points):
                if normalized_mode == "source_current":
                    self.set_current(setpoint, Ch=channel)
                else:
                    self.set_voltage(setpoint, Ch=channel)

                if settle_time > 0:
                    sleep(settle_time)

                current_reads = []
                voltage_reads = []
                for _ in range(repetitions):
                    current_value, voltage_value = self._measure_iv_once(channel)
                    current_reads.append(current_value)
                    voltage_reads.append(voltage_value)

                avg_current, std_current = _average(current_reads)
                avg_voltage, std_voltage = _average(voltage_reads)
                point_timestamp = perf_counter() - start_timestamp
                result_points.append({
                    "index": index,
                    "setpoint": float(setpoint),
                    "current_a": avg_current,
                    "current_std_a": std_current,
                    "voltage_v": avg_voltage,
                    "voltage_std_v": std_voltage,
                    "resistance_ohm": _safe_resistance(avg_voltage, avg_current),
                    "timestamp_s": point_timestamp,
                    "compliance_hit": False,
                })
        finally:
            if reset_to_zero:
                if normalized_mode == "source_current":
                    self.set_current(0.0, Ch=channel)
                else:
                    self.set_voltage(0.0, Ch=channel)
            if not keep_output:
                self.disable_source(Ch=channel)

        return {
            "meta": {
                "instrument": "Keithley2600",
                "channel": channel,
                "mode": normalized_mode,
                "source_units": "A" if normalized_mode == "source_current" else "V",
                "measure_units": "V" if normalized_mode == "source_current" else "A",
                "setpoint_count": len(points),
                "repetitions": int(repetitions),
                "nplc": float(nplc),
                "auto_range": bool(auto_range),
                "source_range": source_range,
                "measure_range": measure_range,
                "compliance": float(compliance),
                "settle_time_s": float(settle_time),
                "measure_delay_s": None if measure_delay is None else float(measure_delay),
                "use_4wire": use_4wire,
            },
            "points": result_points,
            "arrays": {
                "setpoint": [point["setpoint"] for point in result_points],
                "current_a": [point["current_a"] for point in result_points],
                "voltage_v": [point["voltage_v"] for point in result_points],
                "resistance_ohm": [point["resistance_ohm"] for point in result_points],
                "timestamp_s": [point["timestamp_s"] for point in result_points],
            },
        }



    def measure_script(self,meas_curr,AVGnum):
        self.keithley.clear()
        with open(r".\keithley\measure_script.txt") as f:
            script_txt = f.read()
        script_txt = script_txt.replace("{meas_curr}",str(meas_curr))
        script_txt  = script_txt.replace("{AVGnum}",str(int(AVGnum)))
        
        self.load_script("measure",script_txt,5,50,2)
        #print(self.measure("measure"))
        Ip,Vp,Im,Vm,R = self.measure("measure")
        return R


    def pulse_script(self,pulseMax,pulseMin,nplc,tbm,V_comp):
        self.keithley.clear()
        with open(r".\keithley\pulse_script.txt") as f:
        #with open(r".\keithley\pulse_script2.txt") as f:
            script_txt = f.read()
        print(pulseMax)
        script_txt = script_txt.replace("{pulseMax}",str(pulseMax))
        script_txt = script_txt.replace("{pulseMin}",str(pulseMin))
        script_txt = script_txt.replace("{nplc}",str(nplc))
        script_txt = script_txt.replace("{tbm}",str(tbm))
        script_txt = script_txt.replace("{V_comp}",str(V_comp))
        self.load_script("pulse",script_txt, num_of_points=3, script_buffer=10000, delay_time=2)
        #self.load_script("pulse2",script_txt, num_of_points=2, script_buffer=10000, delay_time=2)


        #t,I = self.measure("pulse2")
        V,I,t = self.measure("pulse")
        
        return t,I


    def clear_queue(self):
        #TODO tie this to file option
        self.keithley.clear()
        #self.keithley.clear_queue()