import socket
import time
from threading import Thread
import connection

SERVER = ("192.168.1.108", 8053)

def main():
	client = connection.Client(SERVER)
	incoming_message_thread = Thread(target=print_incoming_message, args=(client,))
	incoming_message_thread.start()
	while True:
		data = input()
		client.send(data)

def print_incoming_message(client):
	while True:
		print(client.recv())

main()
