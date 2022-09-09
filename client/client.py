#!/usr/bin/env python

from borgle import *
import socket
import hashlib
import os

def menu(ClientSocket):

    while True:
        Response = ClientSocket.recv(1024)
        print(Response.decode())
        choice = input('Your choice: ')
        ClientSocket.send(choice.encode())

        Response = ClientSocket.recv(1024)
        print(Response.decode())
        if choice =="1":
            if login(ClientSocket)==0:
                return "1"
        elif choice == "2":
            register(ClientSocket)  
        elif choice == "3":
            return "3"

def login(ClientSocket):
    get_user_info(ClientSocket)
    response = ClientSocket.recv(1024).decode()
    print(response)
    if "Welcome" in response:
        return 0
    else:
        return -1


def register(ClientSocket):
    get_user_info(ClientSocket)
    response = ClientSocket.recv(1024).decode()
    print(response)

def get_user_info(ClientSocket):
    username = input('username: ')
    ClientSocket.send(username.encode())
    password = input('password: ')
    h = hashlib.new('sha256')
    h.update(password.encode())
    ClientSocket.send(h.hexdigest().encode())

def submit_algorithem(ClientSocket):
    ClientSocket.send((str(os.stat("./subb.py").st_size)).encode())
    with open("./subb.py", "r") as file:
        contents = file.read()
        ClientSocket.send(contents.encode())
        file.close()
    response = ClientSocket.recv(1024).decode()
    print(response)

def fight(ClientSocket):
    rival = input('your choice: ')
    ClientSocket.send(rival.encode())

    response = ClientSocket.recv(1024).decode()
    print(response)

def game_loop(ClientSocket):
    while True:
        Response = ClientSocket.recv(1024)
        print(Response.decode())
        choice = input('Your choice: ')
        ClientSocket.send(choice.encode())
        
        Response = ClientSocket.recv(1024)
        print(Response.decode())
        if choice == "1":
            fight(ClientSocket)
        elif choice =="2":
            submit_algorithem(ClientSocket)
        elif choice == "3":
            return "3"
        


ClientSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
host = '16.170.245.99'
#host = 'localhost'
port = 6666

print('Waiting for connection')
try:
    ClientSocket.connect((host, port))
except socket.error as e:
    print(str(e))

result = menu(ClientSocket)
if result == "1":
    game_loop(ClientSocket)


    


