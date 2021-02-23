"""
PACKET(32) --> | SYNFLAG(1) | ACKFLAG(1) | FINFLAG(1) | SEQNUM(7) | ACKNUM(7) | MSG(15) |
"""

import time
import socket
from threading import Thread
from random import randint
from queue import Queue
from math import ceil

HEADERSIZE = 17
MSGSIZE = 15
PACKETSIZE = HEADERSIZE + MSGSIZE
HOST = (socket.gethostbyname(socket.gethostname()), 8050)

sendQueue = Queue()
receiveQueue = Queue()
sentBuffer = Queue()

# Starts server and listens for connections
def main():
	myServer = socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0)
	myServer.bind(HOST)
	myServer.listen()
	while True:
		client, address = myServer.accept()
		clientThread = Thread(target=client_handler, args=((client, address)))
		clientThread.start()

# Manages incoming connections
def client_handler(client: socket, address: tuple):
	connInfo = {'client': client, 'active': False, 'synSeq': randint(0, 9999990), 'ackSeq': 0}
	handshake(connInfo)
	if not connInfo.get('active'):
		print(f'[{address[0]}: CONNECTION FAILED]')
		return
	print(f'[{address[0]}: CONNECTED SUCCESSFULLY]')

	sendThread = Thread(target=send_msg, args=(connInfo,), daemon=True)
	receiveThread = Thread(target=recv_msg, args=(connInfo,), daemon=True)
	inputThread = Thread(target=user_input, args=(connInfo,), daemon=True)
	receiveThread.start()
	sendThread.start()
	inputThread.start()

	receiveThread.join()
	sendThread.join()
	client.shutdown(2)
	client.close()
	print ('[CONNECTION CLOSED]')

# Manages initial handshake with clients
def handshake(connInfo: dict):
	client = connInfo.get('client')
	synPacket = client.recv(PACKETSIZE).decode('utf-8')
	if synPacket[0:3] != '100':
		return
	ackSeq = int(synPacket[3:10])
	connInfo.update({'ackSeq': ackSeq + 1})
	client.send(create_packet(connInfo, '', '110'))
	connInfo.update({'ackSeq': ackSeq})
	ackPacket = client.recv(PACKETSIZE).decode('utf-8')
	if int(ackPacket[10:17]) != (connInfo.get('synSeq')+1) or ackPacket[0:3] != '010':
		return
	connInfo.update({'active': True})

# Manages data being received from client
def recv_msg(connInfo: dict):
	client: socket = connInfo.get('client')
	done = False
	while not done:
		packet = client.recv(PACKETSIZE).decode('utf-8')
		if packet[0:3] == '000' and packet[17:23] == '#!#!#!':
			msg = []
			msgArrived = True
			while True:
				client.settimeout(5)
				try:
					packet = client.recv(PACKETSIZE).decode('utf-8')
					if packet[0:3] == '000' and packet[17:23] == '!#!#!#':
						msg[len(msg)-1] = msg[len(msg)-1].rstrip()
						break
					msg.append(packet[HEADERSIZE:PACKETSIZE])
				except:
					msgArrived = False
					msg.clear()
					break
			client.settimeout(None)
			if msgArrived:
				output = ''
				output = output.join(msg)
				receiveQueue.put(output)
				print('\033[96m[CLIENT] ' + output + '\033[0m')
				newAckSeq = len(output) + connInfo.get('ackSeq')
				if newAckSeq > 9999990:
					newAckSeq -= 9999990
				connInfo.update({'ackSeq': newAckSeq})
				client.send(create_packet(connInfo, '', '010'))

		elif packet[0:3] == '010':
			msgData = sentBuffer.get()
			newSynSeq = connInfo.get('synSeq') + msgData[1]
			if newSynSeq > 9999990:
				newSynSeq -= 9999990
			if int(packet[10:17]) == newSynSeq:
				connInfo.update({'synSeq': newSynSeq})
			else:
				sendQueue.put(msgData)

		elif packet[0:3] == '001':
			done = True
			connInfo.update({'active': False})

# Manages data being sent to client
def send_msg(connInfo: dict):
	client = connInfo.get('client')
	done = False
	while not done:
		if sentBuffer.empty() and not sendQueue.empty():
			msg = sendQueue.get()
			dataSent = len(msg)
			msgList = []
			loopRange = ceil(dataSent/MSGSIZE)-1

			for x in range(loopRange):
				msgList.append(msg[(MSGSIZE*x):MSGSIZE*(x+1)])
			msgList.append(msg[((loopRange)*MSGSIZE):])

			client.send(create_packet(connInfo, '#!#!#!'))
			for string in msgList:
				packet = create_packet(connInfo, string)
				client.send(packet)
			client.send(create_packet(connInfo, '!#!#!#'))
			sentBuffer.put([msgList, dataSent, time.time(), 0])

		elif not sentBuffer.empty():
			msgData = sentBuffer.get()
			if msgData[3] <= 3 and time.time() - msgData[2] > 10:
				#print('Data not acknowledged, sending again...')
				client.send(create_packet(connInfo, '#!#!#!'))
				for string in msgData[0]:
					packet = create_packet(connInfo, string)
					client.send(packet)
				client.send(create_packet(connInfo, '!#!#!#'))
				msgData[2] = time.time()
				msgData[3] += 1
				sentBuffer.put(msgData)
			elif msgData[3] > 3:
				connInfo.update({'active': False})
				done = True
				print ('[CONNECTION TIMED OUT]')
			else:
				sentBuffer.put(msgData)

		elif not connInfo.get('active') and sendQueue.empty() and sentBuffer.count == 0:
			done = True
			client.send(create_packet(connInfo, '', '001'))
		time.sleep(.1)

# Takes input to be sent to client
def user_input(connInfo: dict):
	while True:
		msg = input()
		if not connInfo.get('active'):
			break
		if (msg == 'END'):
			print('[CONNECTION IS NO LONGER ACTIVE]')
			connInfo.update({'active': False})
			break
		msg = msg.rstrip()
		sendQueue.put(msg)

# Adds header and serializes packets
def create_packet(connInfo: dict, msg: str, flags: str = '000') -> bytes:
	formattedMsg = f'{flags:<03}{connInfo.get("synSeq"):07}{connInfo.get("ackSeq"):07}{msg:<15}'
	return formattedMsg.encode('utf-8')

if __name__ == '__main__':
	main()
