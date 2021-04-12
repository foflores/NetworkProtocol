"""
PACKET(42)
|CHECKSUM(6) |SYNFLAG(1) |ACKFLAG(1) |FINFLAG(1) |BUFSIZE(2) |SEQNUM(7) |ACKNUM(7) |MSG(17) |
"""
import time
import socket
from select import select
from threading import Thread
from random import randint
from queue import Queue
from math import ceil
from math import floor

CHECKSUM_SIZE = 6
FLAG_SIZE = 3
BUFFER_SIZE = 2
SYN_SIZE = 7
ACK_SIZE = 7
MSG_SIZE = 17

HEADER_SIZE = FLAG_SIZE + BUFFER_SIZE + SYN_SIZE + ACK_SIZE
PACKET_SIZE = HEADER_SIZE + MSG_SIZE

SYN = "100"
ACK = "010"
SYN_ACK = "110"
DATA = "000"

SERVER = ("192.168.1.108", 8050)
HOST = (socket.gethostbyname(socket.gethostname()), 8050)

def create_checksum(packet: str):
	char_num = ''
	for char in packet:
		char_num += f'{ord(char):03}'

	char_num = f'{char_num:0>108}'
	checksum = 0
	for i in range(18):
		checksum += int(char_num[i * 6:(i + 1) * 6])

	while checksum >= 1000000:
		remainder = floor(checksum / 1000000)
		checksum = checksum - (remainder * 1000000)
		checksum += remainder
	checksum = f'{checksum:0>6}'

	return f'{checksum}{packet}'


def verify_checksum(packet: str):
	if len(packet) < 25:
		return None
	given_checksum = int(packet[0:6])
	packet = packet[6:]
	char_num = ''
	for char in packet:
		char_num += f'{ord(char):03}'

	char_num = f'{char_num:0>108}'
	checksum = 0
	for i in range(18):
		checksum += int(char_num[i * 6:(i + 1) * 6])

	while checksum >= 1000000:
		remainder = floor(checksum / 1000000)
		checksum = checksum - (remainder * 1000000)
		checksum += remainder

	if given_checksum == checksum:
		return packet


class Client():
	def __init__(self, address: tuple):
		self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0)
		self.server.connect(address)
		self.conn_info = {
			"packet_size": HEADER_SIZE + CHECKSUM_SIZE,
			"syn_seq": randint(0, 9999990),
			"ack_seq": 0,
		}
		self.raw_outgoing_data = []
		self.outgoing_data = []
		self.ack_received = set()
		self.data_received = {}
		self.msg_buffer = ""
		self.output_queue = Queue()
		if not self._handshake():
			print("[ATTEMPTED CONNECTION FAILED]")
		data_processing_thread = Thread(target=self._data_processing)
		data_processing_thread.start()

	# public
	def send(self, msg: str):
		if msg == "":
			return
		self.raw_outgoing_data.append(msg)

	def recv(self):
		return self.output_queue.get()

	# private
	def _data_processing(self):
		while True:
			# receive incoming packets
			ready_objs, _, _ = select([self.server], [], [], 0)
			for _ in ready_objs:
				data = self._receive_packet()
				if data is None:
					continue
				if data.get("flags") == DATA:
					self._send_packet(
						flags=ACK,
						ack=data.get("syn_seq") + len(data.get("msg")),
					)
					# recreate message from packet
					self.data_received.update({data.get("syn_seq"): data})
					while True:
						if self.conn_info.get("ack_seq") in self.data_received:
							data = self.data_received.get(self.conn_info.get("ack_seq"))
							msg = data.get("msg")
							if msg != "!#!#!#":
								self.msg_buffer += msg
							else:
								complete_msg = self.msg_buffer.replace("/$%/", " ")
								self.output_queue.put(complete_msg)
								self.msg_buffer = ""
							self.conn_info.update({"ack_seq": data.get("syn_seq") + len(msg)})
						else:
							break
				elif data.get("flags") == ACK:
					self.ack_received.add(data.get("ack_seq"))

			# format outgoing data
			if len(self.raw_outgoing_data) != 0:
				for msg in self.raw_outgoing_data:
					syn = self.conn_info.get("syn_seq")
					msg = msg.replace(" ", "/$%/")
					loop_range = ceil(len(msg) / MSG_SIZE) - 1
					for i in range(loop_range):
						msg_slice = msg[(MSG_SIZE * i):MSG_SIZE * (i + 1)]
						self.outgoing_data.append([False, False, syn, msg_slice])
						syn += len(msg_slice)
					msg_slice = msg[((loop_range) * MSG_SIZE):]
					self.outgoing_data.append([False, False, syn, msg_slice])
					syn += len(msg_slice)
					self.outgoing_data.append([False, False, syn, "!#!#!#"])
					syn += 6
					self.conn_info.update({"syn_seq": syn})
				self.raw_outgoing_data.clear()

			# send outgoing packets
			if len(self.outgoing_data) != 0:
				for i, packet_data in enumerate(self.outgoing_data):
					if not packet_data[0]:
						self._send_packet(packet_data[3], syn=packet_data[2])
						if len(packet_data) < 6:
							packet_data = [
								True,
								False,
								packet_data[2],
								packet_data[3],
								time.time(),
								1
							]
						else:
							packet_data = [
								True,
								False,
								packet_data[2],
								packet_data[3],
								time.time(),
								packet_data[5] + 1
							]
						self.outgoing_data[i] = packet_data
					elif packet_data[0] and not packet_data[1]:
						if time.time() - 10 <= packet_data[4]:
							ack_expected = packet_data[2] + len(packet_data[3])
							if ack_expected in self.ack_received:
								self.outgoing_data[i][1] = True
								self.ack_received.remove(ack_expected)
						elif self.outgoing_data[i][5] < 3:
							self.outgoing_data[i][0] = False
							self.outgoing_data[i][4] = time.time()
						else:
							print(["[CONNECTION TIMED OUT]"])
							break
				self.outgoing_data = [x for x in self.outgoing_data if not x[0] or not x[1]]
			time.sleep(.01)

	# helper
	def _handshake(self) -> bool:
		self._send_packet(flags=SYN)
		syn_ack = self._receive_packet()
		if syn_ack is None:
			return False
		if syn_ack.get("flags") != SYN_ACK or syn_ack.get("ack_seq") != self.conn_info.get("syn_seq") + 1:
			return False
		self.conn_info.update({"packet_size": syn_ack.get("packet_size")})
		ack_seq = syn_ack.get("syn_seq")
		self.conn_info.update({"ack_seq": ack_seq})
		self._send_packet(flags=ACK, ack=ack_seq + 1)
		return True

	def _send_packet(self, msg: str = '', flags: str = DATA, syn: int = -1, ack: int = -1) -> bytes:
		packet = f'{flags:<0{FLAG_SIZE}}{PACKET_SIZE+CHECKSUM_SIZE:0{BUFFER_SIZE}}'

		if syn != -1:
			packet += f'{syn:0{SYN_SIZE}}'
		else:
			packet += f'{self.conn_info.get("syn_seq"):0{SYN_SIZE}}'
		if ack != -1:
			packet += f'{ack:0{ACK_SIZE}}'
		else:
			packet += f'{self.conn_info.get("ack_seq"):0{ACK_SIZE}}'
		if msg != '':
			packet += f'{msg:<{MSG_SIZE}}'

		packet = create_checksum(packet)
		self.server.send(packet.encode('utf-8'))

	def _receive_packet(self):
		raw_data = self.server.recv(self.conn_info.get("packet_size")).decode("utf-8")
		raw_data = verify_checksum(raw_data)
		if raw_data is None:
			return None
		data = {
			"flags": raw_data[0:3],
			"packet_size": int(raw_data[3:5]),
			"syn_seq": int(raw_data[5:12]),
			"ack_seq": int(raw_data[12:19]),
			"msg": raw_data[HEADER_SIZE:].rstrip()
		}
		return data

class Server():
	def __init__(self, port: int = 8050, queue_size: int = 5):
		self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0)
		self.server.bind((socket.gethostbyname(socket.gethostname()), port))
		self.server.listen(queue_size)
		self.active_clients = {}
		self.active_sockets = [self.server]
		self.raw_outgoing_data = []
		self.outgoing_data = []
		self.ack_received = dict()
		start_server_thread = Thread(target=self._start_server)
		start_server_thread.start()

	# public
	def send_to(self, msg: str, address: tuple):
		if msg == "":
			return
		if address in self.active_clients:
			self.raw_outgoing_data.append([address, msg])
		else:
			print("[CONNECTION IS NO LONGER ACTIVE]")

	def recv_from(self, address: tuple):
		conn_info = self.active_clients.get(address)
		if conn_info is None:
			return None
		msg_in_queue = conn_info.get("msg_in_queue")
		return msg_in_queue.get(False)

	def get_clients(self):
		return list(self.active_clients.keys())

	# private
	def _start_server(self):
		while True:
			# handle ready I/O
			socket_list = self.active_sockets
			ready_sockets, _, _ = select(socket_list, [], [], 0)
			for sock in ready_sockets:
				# accept incoming connections
				if sock == self.server:
					client, address = self.server.accept()
					conn_info = {
						"client": client,
						"address": address,
						"packet_size": HEADER_SIZE + CHECKSUM_SIZE,
						"syn_seq": randint(0, 9999990),
						"ack_seq": 0,
						"packet_dict": {},
						"partial_msg_buffer": "",
						"msg_in_queue": Queue()
					}
					if self._handshake(conn_info):
						self.active_sockets.append(client)
						self.active_clients.update({address: conn_info})
					else:
						print("[ATTEMPTED CONNECTION FAILED]")
				# receive incoming data
				else:
					num = self._receive_incoming_data(sock)
					if num == 0:
						break

			# format outgoing data
			if len(self.raw_outgoing_data) != 0:
				for data in self.raw_outgoing_data:
					conn_info = self.active_clients.get(data[0])
					msg = data[1]
					syn = conn_info.get("syn_seq")
					msg = msg.replace(" ", "/$%/")
					loop_range = ceil(len(msg) / MSG_SIZE) - 1
					for i in range(loop_range):
						msg_slice = msg[(MSG_SIZE * i):MSG_SIZE * (i + 1)]
						self.outgoing_data.append([data[0], [False, False, syn, msg_slice]])
						syn += len(msg_slice)
					msg_slice = msg[((loop_range) * MSG_SIZE):]
					self.outgoing_data.append([data[0], [False, False, syn, msg_slice]])
					syn += len(msg_slice)
					self.outgoing_data.append([data[0], [False, False, syn, "!#!#!#"]])
					syn += 6
					conn_info.update({"syn_seq": syn})
					self.active_clients.update({data[0]: conn_info})
				self.raw_outgoing_data.clear()

			# send outgoing packets and check for ack packets
			if len(self.outgoing_data) != 0:
				address_timed_out = None
				for i, packet_data in enumerate(self.outgoing_data):
					address = packet_data[0]
					conn_info = self.active_clients.get(address)
					packet_data = packet_data[1]
					if not packet_data[0]:
						try:
							self._send_packet(conn_info, packet_data[3], syn=packet_data[2])
						except (BrokenPipeError, OSError):
							self._clear_inactive_client(address)
							break
						if len(packet_data) < 6:
							packet_data = [
								True,
								False,
								packet_data[2],
								packet_data[3],
								time.time(),
								1
							]
						else:
							packet_data = [
								True,
								False,
								packet_data[2],
								packet_data[3],
								time.time(),
								packet_data[5] + 1
							]
						self.outgoing_data[i] = [address, packet_data]
					elif packet_data[0] and not packet_data[1]:
						ack_expected = packet_data[2] + len(packet_data[3])
						ack_in = self.ack_received.get(address)
						if time.time() - 10 <= packet_data[4]:
							if ack_in is not None and ack_expected in ack_in:
								self.outgoing_data[i][1][1] = True
								ack_in.remove(ack_expected)
								self.ack_received.update({address: ack_in})
						elif self.outgoing_data[i][1][5] < 3 and time.time() - 10 > packet_data[4]:
							self.outgoing_data[i][1][0] = False
							self.outgoing_data[i][1][4] = time.time()
							print("NO ACK RECV, SENDING AGAIN")
						else:
							print([f"[CONNECTION TIMED OUT TO {address}]"])
							address_timed_out = address
							break

				self.outgoing_data = [x for x in self.outgoing_data if not x[1][0] or not x[1][1]]
				# remove any connections that timed out
				if address_timed_out is not None:
					self._clear_inactive_client(address_timed_out)
			time.sleep(.01)

	# helper functions
	def _receive_incoming_data(self, sock: socket.socket) -> int:
		try:
			conn_info = self.active_clients.get(sock.getpeername())
		except OSError:
			return 0
		data = self._receive_packet(sock, conn_info)
		if data is None:
			return 1
		if data.get("flags") == DATA:
			try:
				self._send_packet(
					flags=ACK,
					ack=data.get("syn_seq") + len(data.get("msg")),
					conn_info=conn_info
				)
			except (BrokenPipeError, OSError):
				self._clear_inactive_client(conn_info.get("address"))
				return 0
			packet_dict = conn_info.get("packet_dict")
			partial_msg_buffer = conn_info.get("partial_msg_buffer")
			msg_in_queue = conn_info.get("msg_in_queue")
			packet_dict.update({data.get("syn_seq"): data})
			# recreate message from packet
			while True:
				if conn_info.get("ack_seq") in packet_dict:
					data = packet_dict.get(conn_info.get("ack_seq"))
					msg = data.get("msg")
					if msg != "!#!#!#":
						partial_msg_buffer += msg
					else:
						complete_msg = partial_msg_buffer.replace("/$%/", " ")
						msg_in_queue.put(complete_msg)
						partial_msg_buffer = ""
					conn_info.update({"ack_seq": data.get("syn_seq") + len(msg)})
				else:
					break
			conn_info.update({"packet_dict": packet_dict})
			conn_info.update({"partial_msg_buffer": partial_msg_buffer})
			conn_info.update({"msg_in_queue": msg_in_queue})

		elif data.get("flags") == ACK:
			ack_in = set()
			if sock.getpeername() in self.ack_received:
				ack_in = self.ack_received.get(sock.getpeername())
			ack_in.add(data.get("ack_seq"))
			self.ack_received.update({sock.getpeername(): ack_in})

		return 1

	def _handshake(self, conn_info) -> bool:
		client: socket.socket = conn_info.get("client")
		syn_packet = self._receive_packet(client, conn_info)
		if syn_packet is None or syn_packet.get("flags") != SYN:
			return False
		conn_info.update({"packet_size": syn_packet.get("packet_size")})
		ack_seq = syn_packet.get("syn_seq")
		conn_info.update({"ack_seq": ack_seq})
		try:
			self._send_packet(conn_info=conn_info, flags=SYN_ACK, ack=ack_seq + 1)
		except BrokenPipeError:
			return False
		ack_packet = self._receive_packet(client, conn_info)
		if ack_packet is None or \
			ack_packet.get("ack_seq") != (conn_info.get("syn_seq")+1) or \
			ack_packet.get("flags") != ACK:
			return False
		return True

	def _receive_packet(self, client: socket.socket, conn_info: dict):
		raw_data = client.recv(conn_info.get("packet_size")).decode("utf-8")
		raw_data = verify_checksum(raw_data)
		if raw_data is None:
			return None
		data = {
			"flags": raw_data[0:3],
			"packet_size": int(raw_data[3:5]),
			"syn_seq": int(raw_data[5:12]),
			"ack_seq": int(raw_data[12:19]),
			"msg": raw_data[HEADER_SIZE:].rstrip()
		}
		return data

	def _send_packet(
		self,
		conn_info: dict,
		msg: str = '',
		flags: str = DATA,
		syn: int = -1,
		ack: int = -1
	) -> bytes:
		packet = f'{flags:<0{FLAG_SIZE}}{PACKET_SIZE+CHECKSUM_SIZE:0{BUFFER_SIZE}}'

		if syn != -1:
			packet += f'{syn:0{SYN_SIZE}}'
		else:
			packet += f'{conn_info.get("syn_seq"):0{SYN_SIZE}}'
		if ack != -1:
			packet += f'{ack:0{ACK_SIZE}}'
		else:
			packet += f'{conn_info.get("ack_seq"):0{ACK_SIZE}}'
		if msg != '':
			packet += f'{msg:<{MSG_SIZE}}'

		packet = create_checksum(packet)
		client = conn_info.get("client")
		client.send(packet.encode('utf-8'))

	def _clear_inactive_client(self, address):
		conn_info = self.active_clients.get(address)
		client = conn_info.get("client")
		self.active_sockets.remove(client)
		self.active_clients.pop(address)
		self.raw_outgoing_data = [x for x in self.raw_outgoing_data if x[0] != address]
		self.outgoing_data = [x for x in self.outgoing_data if x[0] != address]
		print(f"[{address} HAS DISCONNECTED]")
