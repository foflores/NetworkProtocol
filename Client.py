import socket
import threading

HEADER = 10
HOST = "HOSTIP"
LOCALHOST = "192.168.1.108"

def main():
	server = socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0)
	server.connect((LOCALHOST, 8050))
	active = True
	sendThread = threading.Thread(target=sendMsg, args=(server, active), daemon=True)
	receiveThread = threading.Thread(target=receiveMsg, args=(server, 0), daemon=True)
	sendThread.start()
	receiveThread.start()
	receiveThread.join()
	active = False
	print ("[CONNECTION CLOSED]")

def formatMessage(msg):
	formattedMsg = f'{len(msg):<{HEADER}}' + msg
	return formattedMsg.encode("utf-8")

def receiveMsg(server: socket, num):
	message = ""
	newMessage = True
	closeConnection = False
	while not closeConnection:
		msg = server.recv(10)
		if newMessage:
			msgLength = int(msg)
			newMessage = False
		else:
			message += msg.decode("utf-8")

		if len(message) == msgLength:
			if message == "[CLOSE CONNECTION]":
				server.send(formatMessage("[CLOSE CONNECTION CONFIRMED]"))
				closeConnection = True
			elif message == "[CLOSE CONNECTION CONFIRMED]":
				closeConnection = True
			else:
				print('\033[36m' + message + '\033[0m')
				message = ""
				newMessage = True

def sendMsg(server: socket, active: bool):
	while True:
		msg = input()
		if (msg == "END"):
			server.send(formatMessage("[CLOSE CONNECTION]"))
			break
		if active:
			server.send(formatMessage(msg))

main()