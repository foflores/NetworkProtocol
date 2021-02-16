import socket
import threading

HEADER = 10
HOST = socket.gethostbyname(socket.gethostname())
closeConnection = False

def main():
	myServer = socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0)
	myServer.bind((HOST, 8050))
	myServer.listen()
	while True:
		client, address = myServer.accept()
		print(f"[SERVER] {address[0]} connected successfully!")
		clientThread = threading.Thread(target=clientHandler, args=((client, address)))
		clientThread.start()

def clientHandler(client: socket, address):
	client.send(formatMessage(f"[SERVER] You are now chatting with {HOST}"))
	print(f"[SERVER] You are now chatting with {address[0]}!")
	active = True
	sendThread = threading.Thread(target=sendMsg, args=(client, active), daemon=True)
	receiveThread = threading.Thread(target=receiveMsg, args=(client, address), daemon=True)
	receiveThread.start()
	sendThread.start()
	receiveThread.join()
	active = False
	client.shutdown(2)
	client.close()
	print ("[CONNECTION CLOSED]")

def sendMsg(client: socket, active: bool):
	while True:
		msg = input()
		if (msg == "END"):
			client.send(formatMessage("[CLOSE CONNECTION]"))
			break
		if active:
			client.send(formatMessage(msg))

def receiveMsg(client: socket, address):
	message = ""
	newMessage = True
	closeConnection = False
	while not closeConnection:
		msg = client.recv(10)
		if newMessage:
			msgLength = int(msg)
			newMessage = False
		else:
			message += msg.decode("utf-8")

		if len(message) == msgLength:
			if message == "[CLOSE CONNECTION]":
				client.send(formatMessage("[CLOSE CONNECTION CONFIRMED]"))
				closeConnection = True
			elif message == "[CLOSE CONNECTION CONFIRMED]":
				closeConnection = True
			else:
				print('\033[36m' + message + '\033[0m')
				message = ""
				newMessage = True

def formatMessage(msg):
	formattedMsg = f'{len(msg):<{HEADER}}' + msg
	return formattedMsg.encode("utf-8")

main()
