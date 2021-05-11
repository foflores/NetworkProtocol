# Network Protocol
### CS499

#### Use cases implemented:
- initial handshake to establish connection
- breaking down and recreating transmitted data into fixed packet sizes
- acknowledges each message
- retransmitting message if an ACK is not received (up to 3 times)
- send and receive threads use buffers to allow control of data being sent and received
- buffer exchange to determine length of messages that will be sent by each side
- Packet sequencing to determine the correct order packets should be in
- checksum to determine the integrity of the message being sent
- using select to allow for a multiple client/server connections simultaneuosly
- files are requested in chunks from connected clients/servers
- implemented non-blocking IO
