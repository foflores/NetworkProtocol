import time
from threading import Thread
import queue
from network import Connection


SERVER1 = ("71.249.121.62", 8052)
SERVER2 = ("71.249.121.62", 8053)
SERVER3 = ("71.249.121.62", 8054)

def main():
	server = Connection()
	server.connect(SERVER1)
	server.connect(SERVER2)
	server.connect(SERVER3)
	incoming_message_thread = Thread(target=print_incoming_message, args=(server,))
	incoming_message_thread.start()
	server.send_req("./README.md")
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
