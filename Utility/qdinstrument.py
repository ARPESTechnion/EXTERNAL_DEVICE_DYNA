import win32com.client
import pythoncom
from enum import IntEnum


class QDInstrument:
    def __init__(self, instrument_type):
        instrument_type = instrument_type.upper()
        if instrument_type == 'DYNACOOL':
            self._class_id = 'QD.MULTIVU.DYNACOOL.1'
        elif instrument_type == 'PPMS':
            self._class_id = 'QD.MULTIVU.PPMS.1'
        elif instrument_type == 'VERSALAB':
            self._class_id = 'QD.MULTIVU.VERSALAB.1'
        elif instrument_type == 'MPMS3':
            self._class_id = 'QD.MULTIVU.MPMS3.1'
        else:
            raise Exception('Unrecognized instrument type: {0}.'.format(instrument_type))
        self._mvu = win32com.client.Dispatch(self._class_id)

        class ToWait(IntEnum):
            temperature = 1
            field = 2
            position = 3

        self.To_Wait = ToWait

    def set_temperature(self, temperature, rate, mode):
        """Sets temperature and returns MultiVu error code"""
        err = self._mvu.SetTemperature(temperature, rate, mode)
        return err

    def get_temperature(self):
        """Gets and returns temperature info as (MultiVu error, temperature, status)"""
        arg0 = win32com.client.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_R8, 0.0)
        arg1 = win32com.client.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
        print(arg0,arg1)
        err = self._mvu.GetTemperature(arg0, arg1)
        # win32com reverses the arguments, so:
        return err, arg1.value, arg0.value

    def set_field(self, field, rate, approach, mode):
        """Sets field and returns MultiVu error code"""
        err = self._mvu.SetField(field, rate, approach, mode)
        return err

    def get_field(self):
        """Gets and returns field info as (MultiVu error, field, status)"""
        arg0 = win32com.client.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_R8, 0.0)
        arg1 = win32com.client.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
        err = self._mvu.GetField(arg0, arg1)
        # win32com reverses the arguments, so:
        return err, arg1.value, arg0.value

    def set_chamber(self, code):
        """Sets chamber and returns MultiVu error code"""
        err = self._mvu.SetChamber(code)
        return err

    def get_chamber(self):
        """Gets chamber status and returns (MultiVu error, status)"""
        arg0 = win32com.client.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
        err = self._mvu.GetChamber(arg0)
        return err, arg0.value
    
    def set_pos(self, position, speed):

        """Sets field and returns MultiVu error code"""
        err = self._mvu.SetPosition("Horizontal Rotator", position, speed, 0)
        return err

    def get_pos(self):
        """Gets and returns field info as (MultiVu error, field, status)"""
        arg0 = win32com.client.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_R8, 0.0)
        arg1 = win32com.client.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
        err = self._mvu.GetPosition("Horizontal Rotator",arg0, arg1)
        # win32com reverses the arguments, so:
        return err, arg0.value, arg1.value

    def get_timestamp(self):
        arg0 = win32com.client.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
        err = self._mvu.GetTimeStamp
        return err, arg0.value

    def get_temp_range(self):
        _minTemp = win32com.client.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_R8, 0.0)
        _maxTemp = win32com.client.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_R8, 0.0)
        _MinRate = win32com.client.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_R8, 0.0)
        _MaxRate = win32com.client.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_R8, 0.0)
        err = self._mvu.GetTempLimits(_minTemp, _maxTemp, _MinRate, _MaxRate)
        return err, _minTemp.value, _maxTemp.value, _MinRate.value, _MaxRate.value
    
    def wait_for(self,wait_for_this,delay,timeout):
        print(wait_for_this,delay,timeout)
        err = self._mvu.WaitFor(wait_for_this, delay, timeout)
        return err

