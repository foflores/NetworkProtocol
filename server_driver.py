import time
from threading import Thread
import queue
from network import Connection

def main():
	server = Connection()
	server.listen(8050)
	incoming_message_thread = Thread(target=print_incoming_message, args=(server,))
	incoming_message_thread.start()
	while True:
		clients = server.get_clients()
		for client in clients:
			data = input()
			server.send_data(data, client)

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
