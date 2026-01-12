from socket import *
import socket
import struct

def run_client():

    client_offers_receiver = socket.socket(AF_INET, SOCK_DGRAM)
    client_offers_receiver.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
    client_offers_receiver.bind(('', 13122))
    print("Client started, listening for offer requests...”")
    while True:
        # Receive data from the socket
        data, server_address = client_offers_receiver.recvfrom(1024)

        # Extract server IP
        server_ip = server_address[0]
        print(f"Received offer from {server_ip}")

        # Validate message size (should be 39 bytes)
        if len(data) != 39:
            print(f"Invalid offer size: {len(data)} bytes, expected 39")
            continue

        # Unpack the offer message
        # Format: magic_cookie (4), message_type (1), tcp_port (2), server_name (32)
        magic_cookie, message_type, tcp_port_bytes, server_name_bytes = struct.unpack('!IbH32s', data)

        # Validate magic cookie
        if magic_cookie != 0xabcddcba:
            print(f"Invalid magic cookie: {hex(magic_cookie)}, expected 0xabcddcba")
            continue

        # Validate message type (should be 0x2 for offer)
        if message_type != 0x2:
            print(f"Invalid message type: {message_type}, expected 2 (offer)")
            continue

        tcp_port = tcp_port_bytes.decode('utf_8')

        # Extract server name (remove null padding)
        server_name = server_name_bytes.rstrip(b'\x00').decode('utf-8')

        # Close UDP socket before connecting via TCP
        client_offers_receiver.close()

        # Connect to the server via TCP and start the game
        ##play_game(server_ip, tcp_port, server_name)

        # After game ends, return to listening for offers
        return run_client()





def get_valid_rounds():
    while True:
        user_input = input("How many rounds would you like to play? ")

        try:
            rounds = int(user_input)

            # we have 1-byte limit (0-255) in the packet
            if 1 <= rounds <= 255:
                return rounds
            else:
                print("Error: Please enter a number between 1 and 255.")

        except ValueError:
            print("Error: That's not a valid integer. Try again.")


if __name__ == "__main__":
    rounds = get_valid_rounds()
    run_client(rounds)