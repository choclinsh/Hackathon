import struct
import threading
from socket import *
import time
import random

# Constants
MAGIC_COOKIE = 0xabcddcba
OFFER_TYPE = 0x2
REQUEST_TYPE = 0x3
PAYLOAD_TYPE = 0x4


def run_server():
    server_name = "Team Adnan"
    server_socket = socket(AF_INET, SOCK_STREAM)
    server_socket.bind(('', 0))
    server_ip, server_port = server_socket.getsockname()
    server_socket.listen()
    print(f"Server started, listening on IP {server_ip} and port {server_port}")

    # Setup UDP Broadcast
    udp_socket = socket(AF_INET, SOCK_DGRAM)
    udp_socket.setsockopt(SOL_SOCKET, SO_BROADCAST, 1)

    broadcaster = threading.Thread(target=send_offers, args=(udp_socket, server_name, server_port))
    broadcaster.daemon = True
    broadcaster.start()

    while True:
        try:
            client_conn, client_addr = server_socket.accept()
            print(f"Client connected from {client_addr}")

            rounds_number, client_name = get_request(client_conn)
            if rounds_number == 0:
                client_conn.close()
                continue

            # Loop for the requested number of rounds
            for round_num in range(1, rounds_number + 1):
                print(f"\nRound {round_num}/{rounds_number} with '{client_name}'")
                deck = create_deck()
                random.shuffle(deck)
                # We don't print the return value here, we print inside the function or log it
                result = play_round(client_conn, client_name, deck)
                print(f"Round finished. Result: {result}")

            print(f"Finished all rounds with {client_name}. Closing connection.")
            client_conn.close()

        except Exception as e:
            print(f"Server error: {e}")


def send_offers(udp_socket, server_name, tcp_port):
    padded_name = server_name.encode('utf-8').ljust(32, b'\x00')
    offer_msg = struct.pack('!IBH32s', MAGIC_COOKIE, OFFER_TYPE, tcp_port, padded_name)

    my_ip = get_local_ip()

    # 2. Calculate the Broadcast IP (e.g., 172.1.0.255)
    # We assume a standard /24 network (common in labs/homes)
    ip_parts = my_ip.split('.')
    broadcast_ip = f"{ip_parts[0]}.{ip_parts[1]}.{ip_parts[2]}.255"

    print(f"Server started, broadcasting on {broadcast_ip}")

    while True:
        udp_socket.sendto(offer_msg, ('<broadcast>', 13122))
        time.sleep(1)


def get_request(client_conn):
    try:
        data = client_conn.recv(1024)
        if len(data) < 38: return 0, ""

        unpacked = struct.unpack('!IBB32s', data[:38])
        if unpacked[0] != MAGIC_COOKIE or unpacked[1] != REQUEST_TYPE:
            return 0, ""

        rounds = unpacked[2]
        name = unpacked[3].decode('utf-8').rstrip('\x00')
        return rounds, name
    except Exception as e:
        return 0, ""


def play_round(client_socket, client_name, deck):
    player_cards = [deck.pop(), deck.pop()]
    dealer_cards = [deck.pop(), deck.pop()]

    player_total = sum(calculate_card_value(card) for card in player_cards)
    # Only calculate dealer total based on what is visible?
    # Logic: Dealer has 2 cards, one hidden. But for total check we track real total.
    dealer_total = sum(calculate_card_value(card) for card in dealer_cards)

    print(f"Player cards: {print_hand(player_cards)}")
    print(f"Dealer showing: {card_to_string(dealer_cards[0])}")

    # 1. Send Player Cards
    # Check for immediate bust (Double Ace = 22)
    if player_total > 21:
        send_card(client_socket, player_cards[0], 0)  # Active
        send_card(client_socket, player_cards[1], 2)  # Loss immediately
    else:
        for card in player_cards:
            send_card(client_socket, card, 0)  # Active

    # 2. Send Dealer's first card
    send_card(client_socket, dealer_cards[0], 0)

    # 3. Player Turn
    while player_total <= 21:
        choice = receive_player_decision(client_socket)

        if choice == "Hittt":
            card = deck.pop()
            player_cards.append(card)
            player_total += calculate_card_value(card)
            print(f"Player hit: {card_to_string(card)} (Total: {player_total})")

            if player_total > 21:
                send_card(client_socket, card, 2)  # Loss
                return "Dealer won"
            else:
                send_card(client_socket, card, 0)  # Active

        elif choice == "Stand":
            print("Player stands.")
            break
        else:
            print("Client disconnected or invalid choice.")
            return "Error"

    # 4. Dealer Turn
    # Reveal second card
    print(f"Dealer reveals hidden card: {card_to_string(dealer_cards[1])}")
    send_card(client_socket, dealer_cards[1], 0)

    while dealer_total < 17:
        card = deck.pop()
        dealer_cards.append(card)
        dealer_total += calculate_card_value(card)
        print(f"Dealer draws: {card_to_string(card)} (Total: {dealer_total})")

        if dealer_total > 21:
            send_card(client_socket, card, 3)  # Win for player (Dealer bust)
            return "Player won"
        else:
            send_card(client_socket, card, 0)  # Active

    # 5. Determine Winner
    if player_total > dealer_total:
        send_result(client_socket, 3)  # Win
        return "Player won"
    elif player_total < dealer_total:
        send_result(client_socket, 2)  # Loss
        return "Dealer win"
    else:
        send_result(client_socket, 1)  # Tie
        return "Tie"


def receive_player_decision(client_socket):
    # FIX: Read 10 bytes (Header 4+1 + Decision 5)
    data = client_socket.recv(10)
    if len(data) < 10:
        return None

    # FIX: Unpack using '5s' for string, NOT 'BHB'
    unpacked = struct.unpack('!IB5s', data)
    magic = unpacked[0]
    decision = unpacked[2].decode('utf-8')

    if magic != MAGIC_COOKIE:
        return None

    return decision


def send_result(client_socket, result_code):
    """Send round result to client (Type 4, no card)"""
    # FIX: Use 'H' and 'B' dummy values to match the 9-byte format the client expects
    payload_msg = struct.pack('!IBBHB', MAGIC_COOKIE, PAYLOAD_TYPE, result_code, 0, 0)
    client_socket.send(payload_msg)


def send_card(client_socket, card, result_code):
    payload_msg = struct.pack('!IBBHB', MAGIC_COOKIE, PAYLOAD_TYPE, result_code, card['rank'], card['suit'])
    client_socket.send(payload_msg)


# ... Helper functions (createDeck, calculate, etc) remain the same ...
def create_deck():
    deck = []
    for suit in range(4):
        for rank in range(1, 14):
            deck.append({'rank': rank, 'suit': suit})
    return deck


def calculate_card_value(card):
    rank = card['rank']
    if rank == 1:
        return 11
    elif rank >= 11:
        return 10
    else:
        return rank


def card_to_string(card):
    rank_names = ['A', '2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K']
    suit_names = ['♥', '♦', '♣', '♠']
    return f"{rank_names[card['rank'] - 1]}{suit_names[card['suit']]}"


def print_hand(cards):
    return " ".join([card_to_string(c) for c in cards])


def get_local_ip():
    """
    Clever trick to find the real IP address of this computer.
    We don't actually connect to Google (8.8.8.8), but asking the OS
    'how would I get there?' reveals the correct network adapter IP.
    """
    s = socket(AF_INET, SOCK_DGRAM)
    try:
        s.connect(('8.8.8.8', 1))
        IP = s.getsockname()[0]
    except Exception:
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP


if __name__ == "__main__":
    run_server()