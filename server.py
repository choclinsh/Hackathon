import struct
from socket import *
import time

def run_server():
    server_name = "Team Adnan"

    server_socket = socket(AF_INET, SOCK_STREAM)

    # 2. Bind to '0.0.0.0' (listen on all interfaces) and Port 0 (random free port)
    server_socket.bind(('', 0))

    # 3. Retrieve the actual port number assigned by the OS
    server_ip, server_port = server_socket.getsockname()
    server_socket.listen()
    print(f"Server started, listening on IP {server_ip} and port {server_port}")

    client_conn, client_addr = send_offers(server_socket, server_name, server_port)
    print(f"Client connected from {client_addr}")

def send_offers(server_socket, server_name, tcp_port):
    """Send UDP offer broadcasts every second"""
    udp_socket = socket(AF_INET, SOCK_DGRAM)
    udp_socket.setsockopt(SOL_SOCKET, SO_BROADCAST, 1)  # Enable broadcasting

    magic_cookie = b'0xabcddcba'
    message_type = b'0x2'
    server_tcp_port_bytes = tcp_port.to_bytes(2, byteorder='big')
    name_bytes = server_name.encode('utf-8')
    padded_data = name_bytes.ljust(32, b'\x00')

    offer_msg = struct.pack('!IbH32s', magic_cookie, message_type, server_tcp_port_bytes, padded_data)

    while True:
        # Send broadcast
        udp_socket.sendto(offer_msg, ('<broadcast>', 13122))
        print(f"Sent offer broadcast")

        # Sleep for 1 second
        time.sleep(1)
        client_conn, client_addr = server_socket.accept()
        if client_addr and client_conn:
            return client_conn, client_addr

if __name__ == "__main__":
    run_server()
