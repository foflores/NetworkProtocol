"""
PACKET(43)
|CHECKSUM(6) |FLAGS(4) |BUFSIZE(2) |SEQNUM(7) |ACKNUM(7) |MSG(17)

get request:
	- requests specific file size from all servers
	- servers return file size
	- make they have file and file is the same size
	- request 1 chunk from each connected server
		- chunks will be sized in 1024 bytes?
		- they will be numbered by chunk size
			- 1: bytes 0 - 1023
			- 2: bytes 1024-2047
			- etc
	- wait up to 30 seconds for chunks
		- if chunk does not arrive, update conn_info
		- request chunk from next server
		- wait 30 secs
		- loop through each server until it arrives
		- or print file incomplete if not
"""
import time
import socket
import os
from select import select
from threading import Thread
from random import randint
from queue import Queue
from math import ceil

CHECKSUM_SIZE = 6
FLAG_SIZE = 4
BUFFER_SIZE = 2
SEQ_SIZE = 7
ACK_SIZE = 7
MSG_SIZE = 17
CHUNK_SIZE = 100
SEP_SIZE = 3

HEADER_SIZE = FLAG_SIZE + BUFFER_SIZE + SEQ_SIZE + ACK_SIZE
PACKET_SIZE = HEADER_SIZE + MSG_SIZE + SEP_SIZE
TRANSMISSION_SIZE = PACKET_SIZE + CHECKSUM_SIZE

SYN = "0000"
SYN_ACK = "0001"
ACK = "0010"
DATA_CHECK = "0011"
DATA_CHECK_R = "0100"
DATA_REQUEST = "0101"
DATA_REQUEST_R = "0110"
DATA = "0111"
FIN = "1000"

PACKET_END = "<|>"
MSG_END = "!#!#!#"

def create_checksum(packet: str) -> str:
	if len(packet) < HEADER_SIZE:
		return None
	c_sum = 0
	for char in packet:
		c_sum += ord(char)

	while c_sum >= 1000000:
		remainder = c_sum / 1000000
		c_sum += remainder
	c_sum = f'{c_sum:0>{CHECKSUM_SIZE}}'

	return f'{c_sum}{packet}'


def verify_checksum(packet: str) -> str:
	if len(packet) < HEADER_SIZE + CHECKSUM_SIZE:
		return None
	given_c_sum = int(packet[0:CHECKSUM_SIZE])
	packet = packet[CHECKSUM_SIZE:]
	c_sum = 0
	for char in packet:
		c_sum += ord(char)

	while c_sum >= 1000000:
		remainder = c_sum / 1000000
		c_sum += remainder
	if given_c_sum == c_sum:
		return packet
	return None


class Connection():
	def __init__(self):
		self.server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, 0)
		self.listening = False
		self.active_conns = {}
		self.raw_outgoing_data = []
		self.outgoing_data = []
		self.ack_received = dict()
		self.clear_connection = Queue()
		self.data_requests = {}
		self.data_requests_r = []
		start_server_thread = Thread(target=self._start_server)
		start_server_thread.start()

	# public
	def send_data(self, msg: str, address: tuple):
		if msg == "":
			return
		if address in self.active_conns:
			self.raw_outgoing_data.append([address, msg, DATA])
		else:
			print(f"{address} IS NOT CONNECTED")

	def send_req(self, f_name: str):
		if f_name == "":
			return
		for address in self.active_conns:
			self.raw_outgoing_data.append([address, f_name, DATA_CHECK])
		num_conns = len(self.active_conns)
		self.data_requests.update({
			f_name: {
				"req_step": 0,
				"file_size": 0,
				"time_started": time.time(),
				"num_conns": num_conns,
				"replies": [],
				"data": dict(),
				"chunks_req": dict()
			}
		})

	def recv_req(self, f_name: str):
		if f_name in self.data_requests:
			data = self.data_requests.get(f_name)
			if data[0] == -1:
				print("[ERROR RECEIVING DATA]")
				return None
			if data[0] == 5:
				return data[0]
			print("[REQUEST IN PROGRESS]")
			return None
		print ("[REQUEST NOT FOUND]")
		return None

	def recv_from(self, address: tuple):
		conn_info = self.active_conns.get(address)
		if conn_info is None:
			print(f"{address} IS NOT CONNECTED")
			return None
		msg_in_queue = conn_info.get("msg_in_queue")
		return msg_in_queue.get(False)

	def get_clients(self):
		return list(self.active_conns.keys())

	def listen(self, port: int = 8050):
		self.server.bind((socket.gethostbyname(socket.gethostname()), port))
		self.listening = True

	def connect(self, address: tuple):
		if not self._handshake_init0(address):
			print("[ATTEMPTED CONNECTION FAILED]")
			return
		conn_timer = time.time()
		while time.time() - conn_timer < 5:
			conn_info = self.active_conns.get(address)
			if conn_info.get("conn_step") == 1:
				print("[CONNECTION SUCCESSFUL]")
				return
			time.sleep(.5)
		print("[ATTEMPTED CONNECTION FAILED]")
		return

	# private
	def _start_server(self):
		while True:
			# check if packet incoming
			ready_sockets, _, _ = select([self.server], [], [], 0)

			# process incoming packet
			if len(ready_sockets) != 0:
				self._sort_incoming_packets()

			# process data requests
			if len(self.data_requests) != 0 or len(self.data_requests_r) != 0:
				self._process_data_requests()

			# format outgoing data
			if len(self.raw_outgoing_data) != 0:
				self._format_outgoing_data()

			if len(self.outgoing_data) != 0:
				for i, packet_data in enumerate(self.outgoing_data):
					# send outgoing data
					if not packet_data[1][0]:
						self._send_outgoing_data(packet_data, i)
					# check for ack packets
					elif packet_data[1][0] and not packet_data[1][1]:
						self._check_for_ack_packets(packet_data, i)
				# clear acknowledged packets
				self.outgoing_data = [x for x in self.outgoing_data if not x[1][0] or not x[1][1]]

			# terminate problematic connections
			while not self.clear_connection.empty():
				self._clear_inactive_client(self.clear_connection.get())

		time.sleep(.001)

	# helper functions
	def _sort_incoming_packets(self):
		data = self._receive_packet()
		if (data is None) or (data.get("address") not in self.active_conns and not self.listening):
			return

		if data.get("address") in self.active_conns:
			conn_info = self.active_conns.get(data.get("address"))
			flags = data.get("flags")
			if conn_info.get("conn_step") == 0:
				if flags == SYN_ACK and not self._handshake_init1(data):
					print("[ATTEMPTED CONNECTION FAILED]")

				elif flags == ACK and not self._handshake1(data):
					print("[ATTEMPTED CONNECTION FAILED]")

			elif conn_info.get("conn_step") == 1:
				if flags in (DATA, DATA_CHECK, DATA_CHECK_R, DATA_REQUEST, DATA_REQUEST_R):
					self._process_data_packet(data)

				elif flags == ACK:
					self._process_ack_packet(data)

		elif data.get("flags") == SYN and self.listening and not self._handshake0(data):
			print("[ATTEMPTED CONNECTION FAILED]")

	def _process_data_packet(self, data):
		# pull connection info
		conn_info = self.active_conns.get(data.get("address"))

		# send ACK packet
		self._send_packet(
			flags=ACK,
			ack=data.get("syn_seq") + len(data.get("msg")),
			conn_info=conn_info
		)

		packet_dict = conn_info.get("packet_dict")
		partial_msg_buffer = conn_info.get("partial_msg_buffer")
		msg_in_queue = conn_info.get("msg_in_queue")
		packet_dict.update({data.get("syn_seq"): data})

		# recreate message from packet
		while True:
			if conn_info.get("ack_seq") in packet_dict:
				data = packet_dict.get(conn_info.get("ack_seq"))
				msg = data.get("msg")
				partial_msg_buffer += msg
				index = partial_msg_buffer.find("!#!#!#")
				if index != -1:
					complete_msg = partial_msg_buffer[0:index]
					if data.get("flags") == DATA:
						msg_in_queue.put(complete_msg)
					else:
						self.data_requests_r.append([data.get("address"), data.get("flags"), complete_msg])
					partial_msg_buffer = ""
				conn_info.update({"ack_seq": data.get("syn_seq") + len(msg)})
			else:
				break

		# update connection info
		conn_info.update({"packet_dict": packet_dict})
		conn_info.update({"partial_msg_buffer": partial_msg_buffer})
		conn_info.update({"msg_in_queue": msg_in_queue})

	def _process_ack_packet(self, data):
		# sort ack packet for correct connection
		ack_in = set()
		if data.get("address") in self.ack_received:
			ack_in = self.ack_received.get(data.get("address"))
		ack_in.add(data.get("ack_seq"))
		self.ack_received.update({data.get("address"): ack_in})

	def _process_data_requests(self):
		for request in self.data_requests_r:
			if request[1] == DATA_CHECK:
				file_path = request[2]
				if os.path.isfile(file_path):
					file_size = str(os.path.getsize(file_path))
					msg = file_path + " " + file_size
					self.raw_outgoing_data.append([request[0], msg, DATA_CHECK_R])
				else:
					msg = file_path + " 0"
					self.raw_outgoing_data.append([request[0], msg, DATA_CHECK_R])

			elif request[1] == DATA_CHECK_R:
				msg = request[2].split()
				req = self.data_requests.get(msg[0])
				address_list = req.get("replies")
				if int(msg[1]) != 0 and time.time() - req.get("time_started") < 10:
					address_list.append(request[0])
					req.update({"replies": address_list})
					req.update({"file_size":int(msg[1])})
					req.update({"num_conns": req.get("num_conns") - 1})

			elif request[1] == DATA_REQUEST:
				msg = request[2].split()
				file = open(msg[0], "rt")
				data = file.read(int(msg[1]))
				data = file.read(int(msg[2]))
				data = msg[0] + " " + msg[1] + " " + msg[2] + " " + data
				self.raw_outgoing_data.append([request[0], data, DATA_REQUEST_R])

			elif request[1] == DATA_REQUEST_R:
				msg = request[2].split(" ", 3)
				print (msg)
				req = self.data_requests.get(msg[0])
				data = req.get("data")
				if time.time() - float(req.get("time_started")) < 10:
					data.update({int(msg[1]): msg[3]})
					req.update({"data": data})
					req.update({"time_started": time.time()})
				self.data_requests.update({msg[0]: req})
				chunks = ceil(req.get("file_size")/CHUNK_SIZE)
				if len(req.get("data")) == chunks:
					counter = 0
					msg = ""
					data = req.get("data")
					while counter < chunks:
						msg += data.get(counter*CHUNK_SIZE)
						counter += 1
					file = open("./README2.md", "w")
					file.write(msg)

		self.data_requests_r.clear()

		for i in self.data_requests:
			req = self.data_requests.get(i)
			if time.time() - req.get("time_started") > 10 or req.get("num_conns") == 0:
				if len(req.get("replies")) != 0 and req.get("req_step") == 0:
					chunks = ceil(req.get("file_size")/CHUNK_SIZE)
					address_count = len(req.get("replies"))
					address_list = req.get("replies")
					chunk_counter = 0
					address_counter = 0
					while chunk_counter < chunks:
						msg = i + " " + str(CHUNK_SIZE*chunk_counter) + " " + str(CHUNK_SIZE)
						self.raw_outgoing_data.append([address_list[address_counter], msg, DATA_REQUEST])
						chunks_req = req.get("chunks_req")
						if address_list[address_counter] in chunks_req:
							chunk_list = chunks_req.get(address_list[address_counter])
							chunk_list.append(CHUNK_SIZE*chunk_counter)
							chunks_req.update({address_list[address_counter]: chunk_list})
						else:
							chunk_list = [CHUNK_SIZE*chunk_counter]
							chunks_req.update({address_list[address_counter]: chunk_list})
						req.update({"chunks_req": chunks_req})
						chunk_counter += 1
						address_counter += 1
						if address_counter == address_count:
							address_counter = 0
					req.update({"req_step": 1})
					req.update({"time_started": time.time()})
			if req.get("req_step") == 1 and (time.time() - req.get("time_started")) > 10:
				chunks = ceil(req.get("file_size")/CHUNK_SIZE)
				data = req.get("data")
				chunks_req = req.get("chunks_req")
				missing_chunks = []
				address_list = req.get("replies")
				for j in range(chunks):
					if (j*CHUNK_SIZE) not in data:
						missing_chunks.append(j*CHUNK_SIZE)
				for j in missing_chunks:
					for k in address_list:
						msg = i + " " + str(j) + " " + str(CHUNK_SIZE)
						if k in chunks_req:
							chunk_list = chunks_req.get(k)
							if j not in chunk_list:
								self.raw_outgoing_data.append([k, msg, DATA_REQUEST])
								chunk_list.append(j)
								chunks_req.update({k: chunk_list})
								break
						self.raw_outgoing_data.append([k, msg, DATA_REQUEST])
						chunks_req.update({k: [j]})
						break
				req.update({"chunks_req": chunks_req})
				req.update({"time_started": time.time()})

			self.data_requests.update({i: req})

	def _format_outgoing_data(self):
		for data in self.raw_outgoing_data:
			conn_info = self.active_conns.get(data[0])
			msg = data[1]
			syn = conn_info.get("syn_seq")
			msg = msg + MSG_END
			loop_range = ceil(len(msg) / MSG_SIZE) - 1
			for i in range(loop_range):
				msg_slice = msg[(MSG_SIZE * i):MSG_SIZE * (i + 1)]
				self.outgoing_data.append([data[0], [False, False, syn, msg_slice, data[2]]])
				syn += len(msg_slice)
				if syn > 9999999:
					syn = syn - 9999999
			msg_slice = msg[((loop_range) * MSG_SIZE):]
			self.outgoing_data.append([data[0], [False, False, syn, msg_slice, data[2]]])
			syn += len(msg_slice)
			if syn > 9999999:
				syn = syn - 9999999
			conn_info.update({"syn_seq": syn})
			self.active_conns.update({data[0]: conn_info})
		self.raw_outgoing_data.clear()

	def _send_outgoing_data(self, packet_data, index):

		address = packet_data[0]
		conn_info = self.active_conns.get(address)
		packet_data = packet_data[1]
		self._send_packet(conn_info, packet_data[3], syn=packet_data[2], flags=packet_data[4])
		if len(packet_data) < 6:
			packet_data = [
				True,
				False,
				packet_data[2],
				packet_data[3],
				packet_data[4],
				time.time(),
				1
			]
		else:
			packet_data = [
				True,
				False,
				packet_data[2],
				packet_data[3],
				packet_data[4],
				time.time(),
				packet_data[5] + 1
			]
		self.outgoing_data[index] = [address, packet_data]

	def _check_for_ack_packets(self, packet_data, index):
		address = packet_data[0]
		packet_data = packet_data[1]
		ack_expected = packet_data[2] + len(packet_data[3])
		if ack_expected > 9999999:
			ack_expected = ack_expected - 9999999
		ack_in = self.ack_received.get(address)
		if time.time() - 10 <= packet_data[5]:
			if ack_in is not None and ack_expected in ack_in:
				self.outgoing_data[index][1][1] = True
				ack_in.remove(ack_expected)
				self.ack_received.update({address: ack_in})
		elif self.outgoing_data[index][1][6] < 3 and time.time() - 10 > packet_data[6]:
			self.outgoing_data[index][1][0] = False
			self.outgoing_data[index][1][5] = time.time()
		else:
			print([f"[CONNECTION TIMED OUT TO {address}]"])
			self.clear_connection.put(address)

	def _handshake0(self, syn_packet) -> bool:
		conn_info = {
			"conn_step": 0,
			"address": syn_packet.get("address"),
			"packet_size": syn_packet.get("packet_size"),
			"syn_seq": randint(0, 9999990),
			"ack_seq": syn_packet.get("syn_seq"),
			"packet_dict": {},
			"partial_msg_buffer": "",
			"msg_in_queue": Queue(),
			"dropped_packets": [0, 0.0]
		}
		ack_seq = syn_packet.get("syn_seq")
		self._send_packet(conn_info=conn_info, flags=SYN_ACK, ack=ack_seq + 1)
		self.active_conns.update({conn_info.get("address"): conn_info})
		return True

	def _handshake1(self, ack_packet) -> bool:
		conn_info = self.active_conns.get(ack_packet.get("address"))
		if ack_packet.get("ack_seq") != (conn_info.get("syn_seq")+1) or \
			ack_packet.get("flags") != ACK:
			self.clear_connection.put(ack_packet.get("address"))
			return False
		conn_info.update({"conn_step": 1})
		self.active_conns.update({ack_packet.get("address"): conn_info})
		print(f'{[ack_packet.get("address")]} CONNECTED SUCCESSFULLY')
		return True

	def _handshake_init0(self, address) -> bool:
		conn_info = {
			"conn_step": 0,
			"address": address,
			"packet_size": HEADER_SIZE,
			"syn_seq": randint(0, 9999990),
			"ack_seq": 0,
			"packet_dict": {},
			"partial_msg_buffer": "",
			"msg_in_queue": Queue(),
			"dropped_packets": [0, 0.0]
		}
		self._send_packet(conn_info, flags=SYN)
		self.active_conns.update({address: conn_info})
		return True

	def _handshake_init1(self, syn_ack_packet) -> bool:
		conn_info = self.active_conns.get(syn_ack_packet.get("address"))
		if syn_ack_packet.get("ack_seq") != conn_info.get("syn_seq") + 1:
			self.clear_connection.put(syn_ack_packet.get("address"))
			return False
		conn_info.update({"packet_size": syn_ack_packet.get("packet_size")})
		ack_seq = syn_ack_packet.get("syn_seq")
		conn_info.update({"ack_seq": ack_seq})
		conn_info.update({"conn_step": 1})
		self.active_conns.update({syn_ack_packet.get("address"): conn_info})
		self._send_packet(conn_info, flags=ACK, ack=ack_seq + 1)
		return True

	def _receive_packet(self):
		raw_data, address = self.server.recvfrom(TRANSMISSION_SIZE)
		raw_data = verify_checksum(raw_data.decode("utf-8"))
		if raw_data is None:
			return None
		msg = raw_data[HEADER_SIZE:].rstrip()
		msg = msg[:(len(msg)-SEP_SIZE)]
		data = {
			"address": address,
			"flags": raw_data[0:FLAG_SIZE],
			"packet_size": int(raw_data[FLAG_SIZE:(FLAG_SIZE+BUFFER_SIZE)]),
			"syn_seq": int(raw_data[(FLAG_SIZE+BUFFER_SIZE):(FLAG_SIZE+BUFFER_SIZE+SEQ_SIZE)]),
			"ack_seq": int(raw_data[(FLAG_SIZE+BUFFER_SIZE+SEQ_SIZE):HEADER_SIZE]),
			"msg": msg
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
		packet = f'{flags:<0{FLAG_SIZE}}{TRANSMISSION_SIZE:0{BUFFER_SIZE}}'

		if syn != -1:
			packet += f'{syn:0{SEQ_SIZE}}'
		else:
			packet += f'{conn_info.get("syn_seq"):0{SEQ_SIZE}}'
		if ack != -1:
			packet += f'{ack:0{ACK_SIZE}}'
		else:
			packet += f'{conn_info.get("ack_seq"):0{ACK_SIZE}}'
		if msg != '':
			msg += PACKET_END
			packet += f'{msg:<{MSG_SIZE + 3}}'

		packet = create_checksum(packet)
		self.server.sendto(packet.encode('utf-8'), conn_info.get("address"))

	def _clear_inactive_client(self, address):
		if address in self.active_conns:
			self.active_conns.pop(address)
			self.raw_outgoing_data = [x for x in self.raw_outgoing_data if x[0] != address]
			self.outgoing_data = [x for x in self.outgoing_data if x[0] != address]
			print(f"[{address} HAS DISCONNECTED]")
