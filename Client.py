'''
PACKET(32) --> | SYNFLAG(1) | ACKFLAG(1) | SEQNUM(7) | ACKNUM(7) | MSG(16)
'''
# 	TODO: add function to terminate connections properly

import time
import socket
from threading import Thread
from random import randint
from queue import Queue
from math import ceil

HEADERSIZE = 16
MSGSIZE = 16
PACKETSIZE = HEADERSIZE + MSGSIZE
WINDOWSIZE = PACKETSIZE

receiveQueue = Queue()
sendQueue = Queue()
sentBuffer = Queue()

#	Initiates connection to server
def main():
	server = socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0)
	server.connect(("192.168.1.108", 8050))

	connInfo = {"server": server, "active": False, "synSeq": randint(0, 9999990), "ackSeq": 0}
	connInfo.update({"synSeq": 100})
	handshake(connInfo)
	if connInfo.get("ackSeq") == -1:
		print("[ATTEMPTED CONNECTION FAILED]")
		return
	print("[CONNECTION SUCCESSFUL]")
	connInfo.update({"active": True})

	sendThread = Thread(target=sendMsg, args=(connInfo, ), daemon=True)
	receiveThread = Thread(target=receiveMsg, args=(connInfo, ), daemon=True)
	inputThread = Thread(target=userInput, args=(connInfo, ), daemon=True)
	receiveThread.start()
	sendThread.start()
	inputThread.start()

	receiveThread.join()
	sendThread.join()
	#insert close connection function
	print ("[CONNECTION CLOSED]")

#	Manages initial handshake with clients
def handshake(connInfo: dict):
	server = connInfo.get("server")
	server.send(createPacket(connInfo, "", True))
	synAckPacket = server.recv(PACKETSIZE).decode("utf-8")
	if synAckPacket[0:2] != '11' or int(synAckPacket[9:16]) != connInfo.get("synSeq")+1:
		connInfo.update({"ackSeq": -1})
		return
	connInfo.update({"ackSeq":int(synAckPacket[2:9])+1})
	server.send(createPacket(connInfo, "", False, True))
	connInfo.update({"ackSeq":int(synAckPacket[2:9])})


#	Manages data being received from client
def receiveMsg(connInfo: dict):
	server = connInfo.get("server")
	done = False
	while not done:
		try:
			packet = server.recv(PACKETSIZE).decode("utf-8")
		except:
			if not connInfo.get("active"):
				done = True
			continue
		if packet[0:2] == '00' and packet[16:22] == "#!#!#!":
			msg = []
			msgArrived = True
			while True:
				server.settimeout(5)
				try:
					packet = server.recv(PACKETSIZE).decode("utf-8")
				except:
					msgArrived = False
					msg.clear()
					break
				if packet[0:2] == '00' and packet[16:22] == "!#!#!#":
					msg[len(msg)-1] = msg[len(msg)-1].rstrip()
					break
				msg.append(packet[HEADERSIZE:PACKETSIZE])
			server.settimeout(None)
			if msgArrived:
				output = ""
				output = output.join(msg)
				receiveQueue.put(output)
				print('\033[96m[SERVER] ' + output + '\033[0m')
				newAckSeq = len(output) + connInfo.get("ackSeq")
				if newAckSeq > 9999990:
					newAckSeq -= 9999990
				connInfo.update({"ackSeq": newAckSeq})
				server.send(createPacket(connInfo, "", False, True))

		elif packet[0:2] == '01':
			msgData = sentBuffer.get()
			newSynSeq = connInfo.get("synSeq") + msgData[1]
			if newSynSeq > 9999990:
				newSynSeq -= 9999990
			if int(packet[9:16]) == newSynSeq:
				connInfo.update({"synSeq": newSynSeq})
			else:
				sendQueue.put(msgData)

#	Manages data being sent to client
def sendMsg(connInfo: dict):
	server = connInfo.get("server")
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

			server.send(createPacket(connInfo, "#!#!#!"))
			for string in msgList:
				packet = createPacket(connInfo, string)
				server.send(packet)
			server.send(createPacket(connInfo, "!#!#!#"))
			sentBuffer.put([msgList, dataSent, time.time(), 0])

		elif not sentBuffer.empty():
			msgData = sentBuffer.get()
			if msgData[3] <= 3 and time.time() - msgData[2] > 10:
				server.send(createPacket(connInfo, "#!#!#!"))
				for string in msgData[0]:
					packet = createPacket(connInfo, string)
					server.send(packet)
				server.send(createPacket(connInfo, "!#!#!#"))
				msgData[2] = time.time()
				msgData[3] += 1
				sentBuffer.put(msgData)
			elif msgData[3] > 3:
				connInfo.update({"active": False})
				done = True
				print ("[CONNECTION TIMED OUT]")
			else:
				sentBuffer.put(msgData)

		elif not connInfo.get("active") and sendQueue.empty() and sentBuffer.count == 0:
			done = True
			server.shutdown(1)
		time.sleep(.1)

#	Takes input to be sent to client
def userInput(connInfo: dict) -> None:
	while True:
		msg = input()
		if not connInfo.get("active"):
			break
		if (msg == "END"):
			print("[CONNECTION IS NO LONGER ACTIVE]")
			connInfo.update({"active": False})
			break
		msg = msg.rstrip()
		sendQueue.put(msg)

#	Adds header and serializes packets
def createPacket(connInfo: dict, msg: str, synBit: bool = False, ackBit: bool = False) -> bytes:
	formattedMsg = f'{int(synBit==True)}{int(ackBit==True)}{connInfo.get("synSeq"):07}{connInfo.get("ackSeq"):07}{msg:<16}'
	return formattedMsg.encode("utf-8")

main()
