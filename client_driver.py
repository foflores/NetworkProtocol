import socket
import connection

SERVER = ("192.168.1.108", 8051)
HOST = (socket.gethostbyname(socket.gethostname()), 8050)

def main():
	client = connection.Client(SERVER)
	while True:
		data = input()
		client.send(data)

main()
