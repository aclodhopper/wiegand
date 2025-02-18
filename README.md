# Micropython Wiegand HID Decoder

## Summary

A small micropython program to read and decode HID 26-bit H10301 and 36-bit card data from a HID Prox card reader.
The data format sent by such readers is [Wiegand protocol](https://en.wikipedia.org/wiki/Wiegand_interface).

This implementation includes additional support for decoding the 26 bit and 36 bit HID Prox card formats and parity checks to extract the facility code and card number from the raw Wiegand bit stream.

## Wiegand Implementation Details

The protocol definition for a Wiegand signal is very loose. Timings are not clearly defined. This implementation triggers on a falling edge, and will detect as fast as the interrupt can handle the edges and as slowly as the timout period that's set in the code - currently 250ms.
It's been tested with 36-bit cards, but in theory, it should be able to receive and decode any Wiegand signal with any number of bits.
If a timeout of 250ms after the last bit is too short for your needs, it can be adjusted in the code, but it seems unlikely a card reader would be transmitting bits that slowly on purpose.

## Micropython Versions

This code has been used successfully with Micropython 1.21+ on an ESP8266 WeMos D1 Mini and also on an ESP32 WROOM devkit V1.

## Readers

It should work with anything that emits the Wiegand protocol.
The HID card reader I tested was a no-name reader with the following specs:

| Wire | Description |
| ------ | ------------------------------ |
| Red | Power, 6-12 VDC |
| Black | Ground |
| Green | data0 (5V, normally high) |
| White | data1 (5V, normally high) |
| Blue | LED |
| Yellow | Beep |

Even though the power input requires 6V+, the Wiegand signals were always 5V. I used voltage divider resistors (1k / 2.2k) to adapt the data0 and data1 signals to 3.3V.

## Credits

Forked from this project [micropython-wiegand](https://github.com/pjz/micropython-wiegand)
