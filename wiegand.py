"""
wiegand.py - read card IDs from a wiegand interface card reader

Wiegand protocol has no specific pulse timing specs.
Protocol typically sends normal-high TTL input via Data0 and Data1 signal wires.
Each is pulsed low to signal either a 0 bit (on the Data0 line) or a 1 bit (on the Data1 line).
This reader triggers on falling edges and assumes the read is done if at least 250ms has elapsed since last bit received.
The implementation reads any number of bits, but of course typical HID cards contain 26 or 36 bit numbers.
You can discard bad reads with other bit counts on the receiving end if you like, or adjust the code to discard them on this side (see comment in code).

Use the Card.parse() method to optionally parse the returned card into parts (facility, card number, etc),
    and to apply parity checking. Several common formats are implemented, but you can add your own.
"""

from machine import Pin, Timer

class Wiegand:
    def __init__(self, pin0, pin1, callback = None, timer_id=-1):
        """
        pin0 - the GPIO that goes low when a zero is sent by the reader (Green)
        pin1 - the GPIO that goes low when a one is sent by the reader (White)
        callback - the function called with single card argument when a card is read.
                   eg. def mycallback(card)
                   Leave None if you do not want a callback and will poll using get_card() instead.
        timer_id - the Timer ID to use for completion checks. Defaults to -1
        """
        self.pin0 = Pin(pin0, Pin.IN, Pin.PULL_UP)
        self.pin1 = Pin(pin1, Pin.IN, Pin.PULL_UP)
        self.callback = callback
        self.last_card = None
        self.card_count = 0
        self.doneCheckBits = 0    # stores bit count at last timer interrupt to check if bit count changed since last check
        self.next_card = 0   # accumulates the current card number being red
        self.bits = 0    # counts the bits of the current card being read
        self.timer = Timer(timer_id)    # only create the timer once and reuse it as needed
        self.timerSet = False    # indicates if timer is currently in use
        self.pin0.irq(trigger=Pin.IRQ_FALLING, handler=self._on_pin0)
        self.pin1.irq(trigger=Pin.IRQ_FALLING, handler=self._on_pin1)

    def get_card(self):
        """
        Return a tuple containing the last successfully read card and read number.
        Use the read number to determine if a new card read event has occurred since the last time you polled for a card.
        """
        return (self.last_card, self.card_count)

    def _on_pin0(self, newstate):
        """ Interrupt handler for data0 signal """
        self._on_pin(0)

    def _on_pin1(self, newstate):
        """ Interrupt handler for data1 signal """
        self._on_pin(1)

    def _on_pin(self, bitvalue):
        """
        Common interrupt handling code for data0 or data1 signal.
        Accumulate the bit into the current card number.
        Start the "done" timer if this is the first bit of a new read.
        """
        self.next_card <<= 1
        self.next_card += bitvalue
        self.bits += 1
        if not self.timerSet:
            # start the 'done' timer
            self.doneCheckBits = self.bits
            self.timer.init(period=250, mode=Timer.PERIODIC, callback=self._doneCheck)
            self.timerSet = True

    def _doneCheck(self, t):
        """
        When the 'done' check timer expires, determine if any bits have arrived during the previous period.
        If yes, update the done check bit counter to the current value and let timer continue.
        If no, stop the timer, record the completed card, and call the callback if required.
        """
        if self.bits == self.doneCheckBits:
            # no additional bits detected in last timer period - read must be done
            self.timer.deinit()
            self.timerSet = False
            # can add validation here if you want to suppress/discard unrecognized data (eg bad bit counts, etc)
            self.last_card = Card(self.next_card, self.bits)
            self.card_count += 1
            self.doneCheckBits = 0
            self.next_card = 0
            self.bits = 0
            if self.callback:
                self.callback(self.last_card)
        else:
            # more bits were received within the last period.
            # Remember new bit count to check for change in the next period
            self.doneCheckBits = self.bits

class Card:
    """
    Container for a HID card reader result.
    Implements support for parsing and printing cards in various formats.
    Cards typically have a facility code and a number.

    Properties:
        raw_number:  Integer form of card value.
        bits:  Number of bits of data read from the wiegand input.
        facility:  if successfully parsed, the facility code contained in the card data.
        number:  if successfully parsed, the card number contained in the card data.
        format:  if successfully parsed, the format code that was applied to the card data.
        valid:  indicates whether the card data was successfully parsed by the previous parse() call.
    Methods:
        parse(): applies a card format to the raw card data. If successful, it will set "valid". "facility", "number", and "format".
            Parse will assume a format based on the bit count, but you can force a different format explicitly.
            Can extend the logic with your own formats inside this method.
    """

    def __init__(self, raw_number, bits):
        self.raw_number = raw_number
        self.bits = bits
        self.facility = None
        self.number = None
        self.format = None
        self.valid = False

    def __str__(self):
        if self.valid:
            return  f"{self.facility}-{self.number}"
        else:
             return f"{self.raw_number}"
        
    def __repr__(self):
         return f"{type(self).__name__}({self.raw_number},{self.bits})"
        
    def parse(self, format = None):
        """
        Return a bool indicating whether the current card successfully parsed into the specified format.
        If the format is not specified, it is inferred from the bit count.
        If the card is invalid or the format is not understood, False is returned and the card remains invalid/unparsed.
        If the format implements parity, this is also checked.
        Implemented formats:
           26: Proximity card H10301 26 bit format with parity checks
           36: Proximity card 36 bit format with parity checks
        Format code numbers have no intrinsic meaning - you can add additional format code numbers to parse additional values as you need them.
        """
        if not format and self.valid:
            # no explicit format was requested and card was already successfully parsed - just keep existing parse
            return True
        if format and format == self.format:
            # request for parse with same format that was already applied - return existing parse status
            return self.valid
        if not format:
            # no format was specified - infer it
            format = self.bits
        # reset parse values in preparation for a new parse
        self.valid = False
        self.format = None
        self.number = None
        self.facility = None
        if format == 26:
            # Proximity card H10301 (26 bit) format
            # [high] PFFFFFFFFNNNNNNNNNNNNNNNNP [low]
            # (1 Parity + 8 facility + 16 Card Number + 1 Parity)
            # First 13 (high) bits are EVEN parity
            # Last 13 (low) bit are ODD parity
            # Facility code (F) is 8 bits: 0 - 255
            # Card number (N) is 16 bits: 0 - 65535
            # -- check parity of higher 13 - should be EVEN
            # -- check parity of lower 13 - should be ODD
            if self.bits == 26 and self._parity(self.raw_number >> 13) == 0 and self._parity(self.raw_number & 0x1FFF) == 1:
                # parse was successful
                self.valid = True
                self.format = format
                self.facility = (self.raw_number >> 17) & 0xFF
                self.number = (self.raw_number >> 1) & 0xFFFF
        elif format == 36:
            # Proximity card (36 bit) format
            # [high] PFFFFFFFFFFFFFFNNNNNNNNNNNNNNNNNNNNP [low]
            # (1 Parity + 14 facility + 20 Card Number + 1 Parity)
            # First 18 (high) bits are EVEN parity
            # Last 18 (low) bit are ODD parity
            # -- check parity of higher 18 - should be EVEN
            # -- check parity of lower 18 - should be ODD
            if self.bits == 36 and self._parity(self.raw_number >> 18) == 0 and self._parity(self.raw_number & 0x3FFFF) == 1:
                self.valid = True
                self.format = format
                self.facility = (self.raw_number >> 21) & 0x3FFF
                self.number = (self.raw_number >> 1) & 0xFFFFF
        return self.valid

    def _parity(self, x):
        """
        Returns 0 for even bit parity and 1 for odd bit parity of value x
        Used by parse()
        """
        return bin(x).count('1') % 2
