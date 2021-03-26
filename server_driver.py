import socket
import time
import connection

SERVER = ("192.168.1.108", 8050)
HOST = (socket.gethostbyname(socket.gethostname()), 8050)

def main():
	server = connection.Server(8051)
	while True:
		clients = server.get_clients()
		for client in clients:
			data = input()
			server.send_to(data, client)

main()
