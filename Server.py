"""
PACKET(42)
| CHECKSUM(6) | SYNFLAG(1) | ACKFLAG(1) | FINFLAG(1) | BUFSIZE(2) | SYNNUM(7) | ACKNUM(7) | MSG(17)|
"""
import time
import socket
from threading import Thread
from random import randint
from queue import Queue
from math import ceil
from math import floor

CHECKSUMSIZE = 6
FLAGSIZE = 3
BUFFERSIZE = 2
SYNSIZE = 7
ACKSIZE = 7
MSGSIZE = 17

HEADERSIZE = FLAGSIZE + BUFFERSIZE + SYNSIZE + ACKSIZE
PACKETSIZE = HEADERSIZE + MSGSIZE

SYN = '100'
ACK = '010'
SYNACK = '110'
DATA = '000'

HOST = (socket.gethostbyname(socket.gethostname()), 8050)

rawMsgOut = Queue()
msgOut = []
ackIn = dict()
msgIn = dict()
rawMsgIn = Queue()
connInfo = dict()

def startServer():
	myServer = socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0)
	myServer.bind(HOST)
	myServer.listen()
	while True:
		server, address = myServer.accept()
		connInfo.update({
			'server': server,
			'active': False,
			'packetSize': HEADERSIZE + CHECKSUMSIZE,
			'synSeq': randint(0, 9999990),
			'ackSeq': 0,
			'msgInCount': 0
		})
		handshake()
		if not connInfo.get('active'):
			print('CONNECTION ERROR')
		else:
			print('CONNECTED SUCCESSFULLY')
		sendThread = Thread(target=sendMessage)
		receiveThread = Thread(target=receiveMessage)
		inputThread = Thread(target=userInput)
		dataProcessingThread = Thread(target=processData)
		sendThread.start()
		receiveThread.start()
		inputThread.start()
		dataProcessingThread.start()

def sendPacket(msg: str = '', flags: str = DATA, syn: int = -1, ack: int = -1) -> bytes:
	server = connInfo.get('server')
	packet = f'{flags:<0{FLAGSIZE}}{PACKETSIZE+CHECKSUMSIZE:0{BUFFERSIZE}}'

	if syn != -1:
		packet += f'{syn:0{SYNSIZE}}'
	else:
		packet += f'{connInfo.get("synSeq"):0{SYNSIZE}}'
	if ack != -1:
		packet += f'{ack:0{ACKSIZE}}'
	else:
		packet += f'{connInfo.get("ackSeq"):0{ACKSIZE}}'
	if msg != '':
		packet += f'{msg:<{MSGSIZE}}'

	packet = createChecksum(packet)
	server.send(packet.encode('utf-8'))

def handshake():
	server: socket.socket = connInfo.get('server')
	synPacket = verifyChecksum(server.recv(connInfo.get('packetSize')).decode('utf-8'))
	if synPacket == None or synPacket[0:FLAGSIZE] != SYN:
		return
	connInfo.update({'packetSize': int(synPacket[3:5])})
	ackSeq = int(synPacket[5:12])
	connInfo.update({'ackSeq': ackSeq + 1})
	sendPacket(flags=SYNACK)
	connInfo.update({'ackSeq': ackSeq})
	ackPacket = verifyChecksum(server.recv(connInfo.get('packetSize')).decode('utf-8'))
	if synPacket == None or \
		int(ackPacket[12:19]) != (connInfo.get('synSeq')+1) or \
		ackPacket[0:3] != '010':
		return
	connInfo.update({'active': True})

def sendMessage():
	timesSent = 0
	while True:
		if not rawMsgOut.empty() and len(msgOut) == 0:
			syn = connInfo.get('synSeq')
			msg = rawMsgOut.get()
			msg = msg.replace(' ', '/$%/')
			msgLen = len(msg)

			if syn + msgLen >= 9999990:
				syn = syn - 9999990
				connInfo.update({'synSeq': syn})

			loopRange = ceil(len(msg)/MSGSIZE)-1
			for x in range(loopRange):
				msgOut.append([msg[(MSGSIZE*x):MSGSIZE*(x+1)], False])
			msgOut.append([msg[((loopRange)*MSGSIZE):], False])
			msgOut.append(['!#!#!#', False])

		if len(msgOut) != 0:
			syn = connInfo.get('synSeq')
			for i, msg in enumerate(msgOut):
				if not msgOut[i][1]:
					sendPacket(msg[0], syn=syn)
					syn += len(msg[0])
					msgOut[i] = [msg[0], False, syn]

			for i, msg in enumerate(msgOut):
				if msgOut[i][1] == True:
					continue
				ack = None
				timesChecked = 0
				while timesChecked < 5:
					ack = ackIn.get(msg[2])
					if ack == None:
						timesChecked += 1
						time.sleep(1)
					else:
						ackIn.pop(msg[2])
						msgOut[i][1] = True
						timesSent = 0
						timesChecked = 0
						connInfo.update({'synSeq': msg[2]})
						break
				if timesChecked >= 5:
					timesSent += 1
					if timesSent < 3:
						print('[PACKET LOSS! SENDING DATA AGAIN...]')
					else:
						print('[CONNECTION LOST]')
					break
				if msgOut[len(msgOut)-1][1]:
					msgOut.clear()

		if timesSent >= 3:
			break
		time.sleep(.1)

def receiveMessage():
	server: socket.socket = connInfo.get('server')
	while True:
		packet = verifyChecksum(server.recv(connInfo.get('packetSize')).decode('utf-8'))
		if packet == None:
			continue
		syn = int(packet[5:12])
		ack = int(packet[12:19])
		if packet[0:3] == '010':
			ack = int(packet[12:19])
			ackIn.update({ack: packet})
		else:
			msgIn.update({syn: packet})
			msgInCount = connInfo.get('msgInCount') + 1
			connInfo.update({'msgInCount': msgInCount})


def processData():
	messageBuffer = ''
	timesChecked = 0
	while True:
		if connInfo.get('msgInCount') > 0 and timesChecked < 10:
			ack = connInfo.get('ackSeq')
			packet = None
			packet = msgIn.get(ack)
			if packet == None:
				timesChecked += 1
				time.sleep(.01)
				continue
			timesChecked = 0
			msg = packet[HEADERSIZE:PACKETSIZE].rstrip()

			if msg == '!#!#!#':
				messageBuffer = messageBuffer.replace('/$%/', ' ')
				rawMsgIn.put(messageBuffer)
				print(messageBuffer)
				messageBuffer = ''
			else:
				messageBuffer += msg
			connInfo.update({'ackSeq': (ack + len(msg))})
			connInfo.update({'msgInCount': connInfo.get('msgInCount') - 1})
			sendPacket(flags=ACK)
			msgIn.pop(ack)
		elif timesChecked >= 10:
			print('[PACKET LOSS: DATA INCOMPLETE]')
			msgIn.clear()
			timesChecked = 0

		time.sleep(.01)

def userInput() -> None:
	while True:
		msg = input()
		rawMsgOut.put(msg)

def verifyChecksum(packet: str):
	givenChecksum = int(packet[0:CHECKSUMSIZE])
	packet = packet[6:]
	charNum = ''
	for char in packet:
		charNum += f'{ord(char):03}'

	charNum = f'{charNum:0>108}'
	checksum = 0
	for x in range(18):
		checksum += int(charNum[x*6:(x+1)*6])

	while checksum >= 1000000:
		remainder = floor(checksum / 1000000)
		checksum = checksum -(remainder * 1000000)
		checksum += remainder

	if givenChecksum == checksum:
		return packet
	else:
		return None

def createChecksum(packet: str):
	charNum = ''
	for char in packet:
		charNum += f'{ord(char):03}'

	charNum = f'{charNum:0>108}'
	checksum = 0
	for x in range(18):
		checksum += int(charNum[x*6:(x+1)*6])

	while checksum >= 1000000:
		remainder = floor(checksum / 1000000)
		checksum = checksum -(remainder * 1000000)
		checksum += remainder
	checksum = f'{checksum:0>6}'

	return f'{checksum}{packet}'

if __name__ == '__main__':
	startServer()
