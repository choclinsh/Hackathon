from socket import *
import socket
import struct

# Protocol constants defined in the assignment
MAGIC_COOKIE = 0xabcddcba
OFFER_TYPE = 0x2
REQUEST_TYPE = 0x3
PAYLOAD_TYPE = 0x4


def run_client():
    client_name = "Adnan rival"

    # Client runs forever until we kill it manually
    while True:
        tcp_socket = None
        print("Client started, listening for offer requests...")
        # UDP Listening (Waiting for a server)
        try:
            client_offers_receiver = socket.socket(AF_INET, SOCK_DGRAM)

            # This is crucial for testing on the same machine to avoid "Address in use" errors
            client_offers_receiver.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

            # Bind to the specific broadcast port defined in the spec
            client_offers_receiver.bind(('', 13122))

            # Block here until we get a broadcast packet
            data, server_address = client_offers_receiver.recvfrom(1024)
            server_ip = server_address[0]

            # Basic sanity check on packet size before unpacking
            if len(data) < 39:
                print("Packet ignored (too short).")
                continue

            # Unpack the offer packet:
            # I = Cookie (4 bytes), B = Type (1 byte), H = Port (2 bytes), 32s = Name (32 bytes)
            unpacked = struct.unpack('!IBH32s', data[:39])

            # Verify protocol integrity
            if unpacked[0] != MAGIC_COOKIE:
                print(f"Invalid cookie: {hex(unpacked[0])}")
                continue
            if unpacked[1] != OFFER_TYPE:
                print(f"Invalid type: {unpacked[1]}")
                continue

            # Extract server details to connect
            tcp_port = unpacked[2]
            # Clean up the name (remove the null padding bytes)
            server_name = unpacked[3].decode('utf-8').rstrip('\x00')

            # We found a server, so we can stop listening for offers now
            client_offers_receiver.close()

            # Establish TCP Connection
            tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            tcp_socket.connect((server_ip, tcp_port))

            # Send Game Request
            num_rounds = get_valid_rounds()

            # The name field must be exactly 32 bytes, padded with nulls if shorter
            padded_name = client_name.encode('utf-8').ljust(32, b'\x00')

            # Pack the request message according to protocol
            request_msg = struct.pack('!IBB32s', MAGIC_COOKIE, REQUEST_TYPE, num_rounds, padded_name)
            tcp_socket.send(request_msg)

            print(f"Request sent for {num_rounds} rounds.")
            print(f"Playing with {server_name}'s server")

            # Enter Game Loop
            play_games(tcp_socket, num_rounds, client_name)

        except Exception as e:
            print(f"Client Loop Exception: {e}")

        finally:
            # Always clean up the socket to prevent resource leaks
            if tcp_socket:
                tcp_socket.close()
            print("Socket closed. Restarting loop...")


def play_games(tcp_socket, num_rounds, client_name):
    counter = 0
    wins, losses, ties = 0, 0, 0

    while counter < num_rounds:
        print(f"\nROUND {counter + 1}!")

        # 1. Get the initial 3 cards (2 for me, 1 for dealer)
        player_cards, status = start_clients_turn(tcp_socket)
        if not player_cards:
            print("Failed to receive initial cards.")
            break

        # The last card received in the startup batch is the dealer's visible card
        dealer_first_card = player_cards.pop()
        dealer_cards = [dealer_first_card]

        print(f"Your hand: {print_hand(player_cards)}")
        print(f"Dealer shows: {card_to_string(dealer_cards[0])}")

        round_over = False

        # Edge case: If we got double Aces and the server flagged immediate loss
        if status == 2:  # 2 = Loss
            print("Bust! You LOST!")
            losses += 1
            round_over = True

        # Player's Turn (Hit or Stand)
        while not round_over:
            choice = get_valid_choice()
            send_choice(tcp_socket, choice)

            if choice == "Stand":
                break

            # If we chose Hit, we wait for the new card
            card, status = get_another_card(tcp_socket)
            player_cards.append(card)
            print(f"You drew: {card_to_string(card)}")

            # Check if that new card made us bust
            if status == 2:  # Loss
                print("Bust! You LOST!")
                losses += 1
                round_over = True

        # Dealer's Turn (only if we didn't bust)
        if not round_over:
            print("Waiting for dealer result...")
            result = dealer_turn(tcp_socket, dealer_cards)

            if result == "client_win":
                print("You WON!")
                wins += 1
            elif result == "dealer_win":
                print("Dealer WON!")
                losses += 1
            elif result == "tie":
                print("It's a TIE!")
                ties += 1

        counter += 1
        print(f"Stats: {wins}W - {losses}L - {ties}T")

    print(f"\nSession Over: {wins} WINS    {losses} LOSSES    {ties} TIES")


def start_clients_turn(tcp_socket):
    cards = []
    # The protocol sends 2 player cards + 1 dealer card = 3 cards total at start
    while len(cards) < 3:
        try:
            # Packet size is exactly 9 bytes (Header + Card info)
            data = tcp_socket.recv(9)
            if len(data) < 9:
                return [], 0

            # Unpack: Magic(4) + Type(1) + Status(1) + Rank(2) + Suit(1)
            unpacked = struct.unpack('!IBBHB', data)
            status = unpacked[2]
            card = {'rank': unpacked[3], 'suit': unpacked[4]}

            cards.append(card)

            # If status is not 0 (active), the round ended (e.g., instant bust)
            if status != 0:
                return cards, status

        except Exception as e:
            print(f"start_clients_turn error: {e}")
            return [], 0

    return cards, 0


def get_another_card(tcp_socket):
    # Helper to receive just one card packet
    data = tcp_socket.recv(9)
    unpacked = struct.unpack('!IBBHB', data)
    status = unpacked[2]
    card = {'rank': unpacked[3], 'suit': unpacked[4]}
    return card, status


def dealer_turn(tcp_socket, dealer_cards):
    while True:  # keep getting cards that the dealer got for himself
        data = tcp_socket.recv(9)
        if len(data) < 9:
            return "Error"

        unpacked = struct.unpack('!IBBHB', data)
        status = unpacked[2]
        rank = unpacked[3]
        suit = unpacked[4]

        # If rank is not 0, it's a real card the dealer drew
        if rank != 0:
            card = {'rank': rank, 'suit': suit}
            dealer_cards.append(card)
            print(f"Dealer drew: {card_to_string(card)}")

        # Check the status byte to see who won
        if status == 3:
            return "client_win"
        if status == 2:
            return "dealer_win"
        if status == 1:
            return "tie"


def send_choice(client_socket, choice):
    # Encode string to bytes
    padded_choice = choice.encode('utf-8')
    # Use '5s' because assignment requires exactly 5 bytes for decision string
    payload_msg = struct.pack('!IB5s', MAGIC_COOKIE, PAYLOAD_TYPE, padded_choice)
    client_socket.send(payload_msg)


def get_valid_rounds():
    while True:
        try:
            r = int(input("How many rounds? "))
            # Packet uses 1 byte for rounds, so max is 255
            if 1 <= r <= 255:
                return r
        except Exception as e:
            print(f"Input error: {e}")

        print("Please type an integer between 1 and 255")


def get_valid_choice():
    while True:
        msg = input("Hit or Stand? ").strip()
        if msg == "Hit":
            return "Hittt"
        if msg == "Stand":
            return "Stand"
        print("Please type exactly: 'Hit' / 'Stand'")


def card_to_string(card):
    # Map internal numbers to pretty symbols for the user
    ranks = ['A', '2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K']
    suits = ['♥', '♦', '♣', '♠']
    return f"{ranks[card['rank'] - 1]}{suits[card['suit']]}"


def print_hand(cards):
    return "    ".join([card_to_string(c) for c in cards])


if __name__ == "__main__":
    run_client()
