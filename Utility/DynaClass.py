import socket
import logging
import os
from enum import IntEnum
# from DynaTemp import CommandTemperature
from time import sleep

class DynaClass(object):
    def __init__(self,HOST,PORT):
        self.HOST = HOST
        self.PORT = PORT

        self.s= socket.socket(socket.AF_INET,socket.SOCK_STREAM)
        self.Temp__state_dictionary = {
            1: "Stable",
            2: "Tracking",
            5: "Near",
            6: "Chasing",
            7: "Pot Operation",
            10: "Standby",
            13: "Diagnostic",
            14: "Impedance Control Error",
            15: "General Failure",
        }

        self.Field__state_dictionary = {
            1: 'Stable',
            2: 'Switch Warming',
            3: 'Switch Cooling',
            4: 'Holding (driven)',
            5: 'Iterate',
            6: 'Ramping',
            7: 'Ramping',
            8: 'Resetting',
            9: 'Current Error',
            10: 'Switch Error',
            11: 'Quenching',
            12: 'Charging Error',
            14: 'PSU Error',
            15: 'General Failure',
        } 

        class TempModeEnum(IntEnum):
            fast_settle = 0
            no_overshoot = 1
        self.Temp_mode = TempModeEnum
        self.TempUnits = 'K'

        class FieldModeEnum(IntEnum):
            linear = 0
            no_overshoot = 1
            oscillate = 2
        self.Field_mode = FieldModeEnum
        self.FieldUnits = 'Oe'

        class Subsystem(IntEnum):
            no_subsystem = 0
            temperature = 1
            field = 2
            position = 4
            chamber = 8
        self.subsystem = Subsystem


        self.To_Wait = Subsystem

        self._set_pointT = 300
        self._set_pointH = 0
        self._set_chamb = 0

    def connect(self):
        print("connecting")
        try:
            self.s.connect((self.HOST,self.PORT))
            print("Connected")
            return 'Dyna Connected'
        except WindowsError:
            return False
    
    def disconnect(self):
        self.s.close()
    
    def send_command_to_socket(self,command):
        try:
            self.s.sendall(bytes(command,'utf-8'))
            data = self.s.recv(1024)
            return data
        except WindowsError:
            return False
        
    def set_temperature(self,
                        set_point: float,
                        rate_per_min: float,
                        approach_mode: IntEnum):

        self.send_command_to_socket("TEMP {0},{1},{2}".format(set_point,rate_per_min,approach_mode))
        return "Set temperture to {0}K at {1} K/min in mode {2}".format(set_point,rate_per_min,self.Temp_mode(approach_mode).name)

    def get_temperature(self):
        err,status_num,temp = self.send_command_to_socket("TEMP?").decode().replace("\r\n","").split(',')
        status_name = self.Temp__state_dictionary[float(status_num)]
        return err,temp,status_num,status_name

    def set_field(self,
                  set_point: float,
                  rate_per_sec: float,
                  approach_mode: IntEnum):

        self.send_command_to_socket("FIELD {0},{1},{2},{3}".format(set_point,rate_per_sec,approach_mode,1))
        return "Set field to {0}Oe at {1} Oe/sec in mode {2}".format(set_point,rate_per_sec,self.Field_mode(approach_mode).name)
    
    def get_field(self):
        err,status_num,field = self.send_command_to_socket("FIELD?").decode().replace("\r\n","").split(',')
        #status_name = self.Field__state_dictionary[float(status_num)]
        return err,field,status_num
    
    def set_pos(self,
                  set_point: float,
                  rate_per_sec: float):

        self.send_command_to_socket("POS {0},{1}".format(set_point,rate_per_sec))
        return "Set position to {0}Deg at {1} Deg/sec".format(set_point,rate_per_sec)
        
    def get_pos(self):
        err,pos,status_num = self.send_command_to_socket("POS?").decode().replace("\r\n","").split(',')
        #status_name = self.Field__state_dictionary[float(status_num)]
        return err,pos,status_num
        
    def wait_for(self,wait_for_this: IntEnum,delay,timeout):
        err = self.send_command_to_socket("WAIT {0},{1},{2}".format(wait_for_this,delay,timeout))
        print(err)
        
    def my_wait_for(self,wait_for_this: IntEnum,delay):  #timeout
        stableCount=0;
        if(wait_for_this==1):
            err,value,status_num,status_name=self.get_temperature()
            while(stableCount<2):
                sleep(5)
                err,value,status_num,status_name=self.get_temperature()
                if(int(status_num)==1):
                    stableCount=stableCount+1
                    print("added stable counter")
                elif(stableCount>0):
                    print("not stable yet")
            
        elif(wait_for_this==2):
            err,value,status_num=self.get_field()
            print(status_num)
            while(stableCount<2):
                print(status_num)
                sleep(5)
                err,value,status_num=self.get_field()
                if(int(status_num)==4):
                    stableCount=stableCount+1
       
        if isinstance(delay,float):
            sleep(delay)
            return True 
        
        if delay == 0:
            return True
        print("start waiting for {0}".format(self.subsystem(wait_for_this).name))
        
        for d in range(delay,-1,-1):
            print(d)
            sleep(1)
        
        print("Finished waiting for {0}".format(self.subsystem(wait_for_this).name))
       
#dyna=DynaClass(HOST=0, PORT=5)
#dyna.connect()