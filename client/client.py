import borgle as bg
from borgle import gameloop

import socket

def calcTurn(turn):
    print("my turn")
    pass

bg.calcTurn = calcTurn

#while(True):
#    gameloop()

ClientSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
host = '16.170.245.99'
#host = 'localhost'
port = 6666

print('Waiting for connection')
try:
    ClientSocket.connect((host, port))
except socket.error as e:
    print(str(e))

Response = ClientSocket.recv(1024)
while True:
    Input = input('Say Something: ')
    ClientSocket.send(str.encode(Input))
    Response = ClientSocket.recv(1024)
    print(Response.decode('utf-8'))
