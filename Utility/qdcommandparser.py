from qdinstrument import QDInstrument


class QDCommandParser:

    def __init__(self, instrument_type, line_term='\r\n'):
        self.cmd_list = {'TEMP': (self.set_temperature, self.get_temperature),
                         'FIELD': (self.set_field, self.get_field),
                         'CHAMBER': (self.set_chamber, self.get_chamber),
                         'POS': (self.set_pos, self.get_pos),
                         'TIME': (self.get_timestamp, self.get_timestamp),
                         'RANGE':(self.get_temp_range,self.get_temp_range),
                         'WAIT':(self.wait_for, self.wait_for)}

        self._instrument = QDInstrument(instrument_type)
        self._line_term = line_term

    def parse_cmd(self, data):
        data = data.decode()
        cmd = data.split(' ')[0]
        for test_cmd in self.cmd_list:
            if cmd.find(test_cmd) == 0:
                if cmd.find(test_cmd + '?') == 0:
                    return str(self.cmd_list[test_cmd][1]()) + self._line_term
                else:
                    try:
                        cmd, arg_string = data.split(' ', 1)
                    except:
                        return 'No argument(s) given for command {0}.'.format(test_cmd) + self._line_term
                    return str(self.cmd_list[test_cmd][0](arg_string)) + self._line_term
        return 'Unknown command: {0}.'.format(data) + self._line_term

    def get_temperature(self):
        ret = self._instrument.get_temperature()
        return '{0}, {1}, {2}'.format(*ret)

    def set_temperature(self, arg_string):
        try:
            temperature, rate, mode = arg_string.split(',')
            temperature = float(temperature)
            rate = float(rate)
            mode = int(mode)
            err = self._instrument.set_temperature(temperature, rate, mode)
            return err
        except:
            return 'Argument error in TEMP command.'

    def get_field(self):
        ret = self._instrument.get_field()
        return '{0}, {1}, {2}'.format(*ret)

    def set_field(self, arg_string):
        try:
            field, rate, approach, mode = arg_string.split(',')
            field = float(field)
            rate = float(rate)
            approach = int(approach)
            mode = int(mode)
            err = self._instrument.set_field(field, rate, approach, mode)
            return err
        except:
            return 'Argument error in FIELD command.'

    def get_chamber(self):
        ret = self._instrument.get_chamber()
        return '{0}, {1}'.format(*ret)

    def get_timestamp(self):
        ret = self._instrument.get_timestamp()
        return '{0}, {1}'.format(*ret)

    def get_pos(self):
        ret = self._instrument.get_pos()
        return '{0}, {1}, {2}'.format(*ret)

    def set_pos(self, arg_string):
        try:
            position, speed = arg_string.split(',')
            position = float(position)
            speed = float(speed)
            err = self._instrument.set_pos(position, speed)
            return err
        except:
            return 'Argument error in POSITION command.'

    def set_chamber(self, arg_string):
        try:
            code = arg_string
            code = int(code)
            err = self._instrument.set_chamber(code)
            return err
        except:
            return 'Argument error in CHAMBER command'

    def get_temp_range(self):
        ret = self._instrument.get_temp_range()
        return '{0}, {1}, {2}, {3}, {4}'.format(*ret)
    
    def wait_for(self,arg_string):
        wait_for_this,delay,timeout = arg_string.split(',')
        wait_for_this=int(wait_for_this)
        delay=int(delay)
        timeout=int(timeout)
        ret = self._instrument.wait_for(wait_for_this,delay,timeout)
        return '{0}'.format(ret)
