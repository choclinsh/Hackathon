from socket import *
import socket
import struct

MAGIC_COOKIE = 0xabcddcba
OFFER_TYPE = 0x2
REQUEST_TYPE = 0x3
PAYLOAD_TYPE = 0x4


def run_client():
    client_name = "Adnan rival"
    print("Client started, listening for offer requests...")

    while True:
        tcp_socket = None
        try:
            client_offers_receiver = socket.socket(AF_INET, SOCK_DGRAM)
            client_offers_receiver.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            client_offers_receiver.bind(('', 13122))

            data, server_address = client_offers_receiver.recvfrom(1024)
            server_ip = server_address[0]

            if len(data) < 39:
                continue

            # Unpack Offer
            unpacked = struct.unpack('!IBH32s', data[:39])
            if unpacked[0] != MAGIC_COOKIE or unpacked[1] != OFFER_TYPE:
                continue

            tcp_port = unpacked[2]
            server_name = unpacked[3].decode('utf-8').rstrip('\x00')

            print(f"Received offer from {server_name} at {server_ip}, connecting...")
            client_offers_receiver.close()

            # Connect TCP
            tcp_socket = socket.socket(AF_INET, SOCK_STREAM)
            tcp_socket.connect((server_ip, tcp_port))

            # Send Request
            num_rounds = get_valid_rounds()
            padded_name = client_name.encode('utf-8').ljust(32, b'\x00')
            request_msg = struct.pack('!IBB32s', MAGIC_COOKIE, REQUEST_TYPE, num_rounds, padded_name)
            tcp_socket.send(request_msg)

            # Play
            play_games(tcp_socket, num_rounds, client_name)

        except Exception as e:
            print(f"Client Error: {e}")

        finally:
            try:
                tcp_socket.close()
            except Exception as e:
                print(f"Client Error: {e}")
                pass
            print("Listening for new offers...")


def play_games(tcp_socket, num_rounds, client_name):
    counter = 0
    wins, losses, ties = 0, 0, 0

    while counter < num_rounds:
        print(f"\nRound {counter + 1}")

        # 1. Get Initial Cards
        player_cards, status = start_clients_turn(tcp_socket)
        if not player_cards:
            break  # Error occurred


        # FIX: pop() returns a dict. We must put it inside a list [] to use append() later
        dealer_first_card = player_cards.pop()
        dealer_cards = [dealer_first_card]

        print(f"Your hand: {print_hand(player_cards)}")
        print(f"Dealer shows: {card_to_string(dealer_cards[0])}")

        if status == 2:  # Loss
            print("Bust! You LOST!")
            losses += 1
            round_over = True
            counter += 1  # Increment round since it ended
        else:
            round_over = False

        while not round_over:  # 2. Player Decision Loop
            choice = get_valid_choice()
            send_choice(tcp_socket, choice)

            if choice == "Stand":
                break

            # If Hit, get card
            card, status = get_another_card(tcp_socket)
            player_cards.append(card)
            print(f"You drew: {card_to_string(card)}")

            if status == 2:  # Loss
                print("Bust! You LOST!")
                losses += 1
                round_over = True
                counter += 1  # Increment round since it ended

        if not round_over:
            # 3. Dealer Turn
            print("Dealer's turn...")
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
        print(f"\nRound Over.\nStatistics for {counter} rounds: {wins} WINS    {losses} LOSSES    {ties} TIES")

    print(f"\nSession Over: {wins} WINS    {losses} LOSSES    {ties} TIES")


def start_clients_turn(tcp_socket):
    cards = []
    # We expect 3 cards initially (2 player, 1 dealer)
    while len(cards) < 3:
        try:
            data = tcp_socket.recv(9)
            if len(data) < 9:
                return []

            unpacked = struct.unpack('!IBBHB', data)
            status = unpacked[2]
            card = {'rank': unpacked[3], 'suit': unpacked[4]}
            cards.append(card)

            if status != 0:  # If we lost immediately (double ace)
                return cards, status

        except Exception as e:
            print(f"Client Error: {e}")
            return [], 0

    return cards, 0


def get_another_card(tcp_socket):
    data = tcp_socket.recv(9)
    unpacked = struct.unpack('!IBBHB', data)
    status = unpacked[2]
    card = {'rank': unpacked[3], 'suit': unpacked[4]}
    return card, status


def dealer_turn(tcp_socket, dealer_cards):
    while True:
        data = tcp_socket.recv(9)
        if len(data) < 9:
            return "Error"

        unpacked = struct.unpack('!IBBHB', data)
        status = unpacked[2]
        rank = unpacked[3]
        suit = unpacked[4]

        # If rank is 0, it's just a result message, not a card
        if rank != 0:
            card = {'rank': rank, 'suit': suit}
            dealer_cards.append(card)
            print(f"Dealer drew: {card_to_string(card)}")

        if status == 3:
            return "Client win"
        if status == 2:
            return "Dealer win"
        if status == 1:
            return "tie"


def send_choice(client_socket, choice):
    # FIX: Use '5s' to pack the string. 'B' cannot pack a string!
    # Assignment requires exactly 5 bytes for decision
    padded_choice = choice.encode('utf-8')
    payload_msg = struct.pack('!IB5s', MAGIC_COOKIE, PAYLOAD_TYPE, padded_choice)
    client_socket.send(payload_msg)


def get_valid_rounds():
    while True:
        try:
            rounds = int(input("How many rounds? "))
            if 1 <= rounds <= 255:
                return rounds

        except Exception as e:
            pass
        print("Please type an integer between 1 and 255")


def get_valid_choice():
    while True:
        msg = input("Hit or Stand? ").strip()
        if msg == "Hit":
            return "Hittt"

        if msg == "Stand":
            return "Stand"
        print("Please type exactly: 'Hit' / 'Stand'")

# Helper print functions
def card_to_string(card):
    ranks = ['A', '2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K']
    suits = ['♥', '♦', '♣', '♠']
    return f"{ranks[card['rank'] - 1]} {suits[card['suit']]}"


def print_hand(cards):
    return " ".join([card_to_string(c) for c in cards])


if __name__ == "__main__":
    run_client()
