/*
  BT SETUP - talk to the HC-05 / HC-06 with AT commands through the Arduino (from the slave config guide).
  Same wiring as fight_pad (module TXD -> D10, module RXD <- D9 through the 1k/2k divider).

  HC-05 (6 pins, has a small button / EN-KEY pin):
    1. Upload this sketch with BT_BAUD = 38400 (the HC-05 AT-mode speed).
    2. Unplug the module's VCC, HOLD its button, plug VCC back, release -> LED blinks slowly (~every 2 s).
    3. Serial Monitor: 38400 baud, "Both NL & CR". Type:
         AT                     -> OK
         AT+ROLE=0              -> OK          (slave)
         AT+INQM=0,5,9          -> OK          (discoverable)
         AT+NAME=STRIKE-P1      -> OK          (STRIKE-P2 on the second pad - easy to tell apart in Windows)
         AT+PSWD="1234"         -> OK          (some firmware wants AT+PSWD=1234 without quotes)
         AT+UART=38400,0,0      -> OK          (optional: then set BT_BAUD = 38400 in fight_pad.ino)
         AT+ADDR?               -> +ADDR:0021:07:001EE9   <- write this down, one per pad
    4. Power cycle it -> fast blinking = normal mode. Upload fight_pad.

  HC-06 (4 pins, no button - it is ALWAYS a slave and is in AT mode whenever nothing is connected):
    1. Set BT_BAUD = 9600 and upload. Serial Monitor: 9600 baud, "No line ending".
    2. Type AT -> OK,  AT+NAMESTRIKE-P1 -> OKsetname,  AT+PIN1234 -> OKsetPIN
       (no "=" and no line ending on most HC-06 firmware; newer ones accept AT+NAME=... with NL & CR)
    3. Upload fight_pad (keep BT_BAUD = 9600 there).
*/
#include <SoftwareSerial.h>

SoftwareSerial bt(10, 9);           // RX, TX

const long BT_BAUD = 38400;         // HC-05 AT mode. HC-06: 9600

void setup() {
  Serial.begin(BT_BAUD);            // keep the monitor at the same speed to make life easy
  bt.begin(BT_BAUD);
  Serial.println(F("BT setup ready - type AT"));
}

void loop() {
  if (Serial.available()) bt.write(Serial.read());
  if (bt.available()) Serial.write(bt.read());
}
