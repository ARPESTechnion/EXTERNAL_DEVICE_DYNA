import random
from time import sleep
import pyvisa
import random
from time import sleep

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
        self.address = 'USB0::0x05E6::0x2614::4083836::INSTR'
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
            self.write("smua.source.func = smua.OUTPUT_DCVOTLS")
            if voltage_range:
                self.write("smua.source.rangev = {0}".format(voltage_range))
            else:
                self.write("smua.source.autorangev = smua.AUTORANGE_ON")
            self.write("smua.source.limiti = {0}".format(compliance_current))
        elif Ch == "b":
            self.write("smub.source.func = smub.OUTPUT_DCVOTLS")
            if voltage_range:
                self.write("smub.source.rangev = {0}".format(voltage_range))
            else:
                self.write("smub.source.autorangev = smub.AUTORANGE_ON")
            self.write("smub.source.limiti = {0}".format(compliance_current))
        elif Ch == "ab":
            self.write("smua.source.func = smua.OUTPUT_DCVOTLS")
            self.write("smub.source.func = smub.OUTPUT_DCVOTLS")
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