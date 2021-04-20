import time
from threading import Thread
import queue
from network import Connection

SERVER = ("192.168.1.108", 8052)

def main():
	client = Connection()
	client.connect(SERVER)
	incoming_message_thread = Thread(target=print_incoming_message, args=(client,))
	incoming_message_thread.start()
	while True:
		data = input()
		client.send_to(data, SERVER)

def print_incoming_message(server):
	while True:
		time.sleep(.01)
		clients = server.get_clients()
		for client in clients:
			try:
				msg = server.recv_from(client)
			except queue.Empty:
				continue
			print (msg)

main()
