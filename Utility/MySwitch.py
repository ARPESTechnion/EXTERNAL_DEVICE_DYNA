
import time

import pyvisa

import time

class MockSwitch:
    def __init__(self):
        self.name = "MockSwitch"
        self.address = "MOCK::INSTR"
        self.switch = None
        self.data = []
        self.IsConnected = False
        self.closed_channels = set()

    def connect(self):
        """Simulate connecting to the switch."""
        self.switch = "MockResource"
        self.IsConnected = True
        return "MOCK SWITCH, Model 1234, Serial 5678, Firmware 1.0"

    def disconnect(self):
        """Simulate disconnecting the switch."""
        self.switch = None
        self.IsConnected = False

    def write(self, command):
        """Simulate sending a command to the switch."""
        print(f"MockSwitch received command: {command}")
        if "ROUT:OPEN:ALL" in command:
            self.closed_channels.clear()
        elif "ROUTe:CLOSe" in command:
            channels = command.split("(")[-1].strip(")")
            self.closed_channels.update(channels.split(","))

    def read(self):
        """Simulate reading a response from the switch."""
        return "MOCK RESPONSE"

    def open_all(self):
        """Simulate opening all channels."""
        self.write("ROUT:OPEN:ALL ALL")
        print("Switch opend all channels")

    def close_list(self, i1, i2=0, i3=0, i4=0):
        """Simulate closing specific channels."""
        channels = [str(x) for x in [i1, i2, i3, i4] if x != 0]
        txt_parts = [f"110{x}" for x in channels[:4]]
        if txt_parts:
            txt1 = f"(@{','.join(txt_parts)})"
            self.open_all()
            time.sleep(1)
            self.write("ROUTe:CLOSe " + txt1)
            print(f"Switch closed {','.join(channels)}")
        self.closed_channels.update(channels)

# Example usage
#if __name__ == "__main__":
#    switch = MockSwitch()
#    print(switch.connect())
#    switch.close_list(1, 2, 3, 4)
#    switch.disconnect()



class MySwitch(object):


    def __init__(self):

        self.name = ''  # make sure this is correct

        self.address = 'USB0::0x0957::0x0507::MY56482243::INSTR'

        self.switch = ''

        self.data = []

        self.IsConnected = False
        # Track channels closed by this app for UI status.
        self.closed_channels = set()


    def connect(self):

        rm = pyvisa.ResourceManager()

        self.switch = rm.open_resource(self.address)

        return self.switch.query('*IDN?')


    def disconnect(self):

        self.switch.close()

        self.IsConnected = False


    def write(self, st):

        self.switch.write(st)


    def read(self):

        return self.switch.read()


    def open_all(self):

        self.write("ROUT:OPEN:ALL ALL")
        self.closed_channels.clear()
        print("Switch opend all chanells")


    def close_list(self, i1, i2, i3, i4):

        txt1 = "(@110{0},120{1},130{2},140{3})".format(i1, i2, i3, i4)

        print("Switch closed {},{},{},{}".format(i1,i2,i3,i4))

        # print(txt1)  # Uncomment for debugging

        self.open_all()

        time.sleep(1)

        self.write("ROUTe:CLOSe " + txt1)
        self.closed_channels.update({str(i1), str(i2), str(i3), str(i4)})
