import socket
from time import sleep
import qdcommandparser

local = "localhost"
Ilay = '10.250.64.16'
Roni = '132.68.72.113'
Dyna ='132.68.75.218'


#Temp ip:
#Roni ='169.254.191.88'
#Dyna ='169.254.191.89'


HOST="localhost"
PORT = 5000

dyna = qdcommandparser.QDCommandParser('DYNACOOL')
s =  socket.socket(socket.AF_INET,socket.SOCK_STREAM)
s.bind((HOST,PORT))
s.listen()
s.settimeout(2.0)
while True:
    print('listening at {}, port: {}'.format(HOST,PORT))
    RUN = True
    while RUN:
        try:
            conn, addr = s.accept()
            print("Connected")
            while True:
                data = conn.recv(1024)
                #if not data: break
                if data == b'exit':
                    print('exiting')
                    RUN = False
                    break
                if data == b'disconnect':
                    break
                print('Connected by: ', addr)
                print('command:',data)
                answer = dyna.parse_cmd(data)
                conn.sendall(bytes(answer,'utf-8'))
            conn.close()
            print('client disconnected')
            sleep(0.5)
        except socket.timeout:
            pass
        except WindowsError as e:
            print(e)
            break
