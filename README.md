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

#### How to use drivers
client_driver.py and server_driver.py are setup to send text through a terminal
- Open client_driver.py and change the SERVER1 constant to your local IP
- Run 'python3 server_driver.py' in one terminal
- Run 'python3 client_driver.py' in another terminal
- By default, you can run any number of instance of client_driver.py and communicate with the server.
- The server will be able to respond one by one to each connected client

#### Other configurations
It is also possible to connect one client to multiple servers.
- Run multiple instances of 'python3 server_driver.py', changing the value for 'server.listen(####)' each time
- Open client_driver.py and uncomment SERVER1, SERVER2 and SERVER3
- Make sure the port numbers match the ones the server is listening to and the IP is your local IP
- uncomment 'server.connect(SERVER2)' and 'server.connect(SERVER3)'
- Run 'python3 client_driver.py'
- The client will simultaneously connect to all 3 servers and be able to communicate with them.
