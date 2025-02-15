from wiegand import Wiegand

DATA0 = 13  # Green / data0
DATA1 = 14   # White / data1

def on_card(card):
    print(f"raw card number: {card.raw_number}.{card.bits}")
    if card.parse():
        print(f"parsed number: {card}")
    else:
        print(f"Parse failed! {card}")
    print()

w = Wiegand(DATA0, DATA1, on_card)

print("Waiting for card reads...")
