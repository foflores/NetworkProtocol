# Network Protocol
### CS499

#### Use cases implemented:
- initial handshake to establish connection
- breaking down and recreating transmitted data into fixed packet sizes (assuming they are in order)
- sending ACK after each message
- retransmitting message if an ACK is not received (up to 3 times)
- send and receive threads use buffers to allow control of data being sent and received