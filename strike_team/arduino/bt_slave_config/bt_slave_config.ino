/*
  BT SLAVE CONFIG - talk to the HC-05 with AT commands through the Arduino UNO.
  (fixed version of strike_team/ard.md)

  PC (Serial Monitor) <--USB / hardware Serial--> UNO <--SoftwareSerial pins 10,9--> HC-05

  Wiring:
    HC-05 VCC -> UNO 5V
    HC-05 GND -> UNO GND
    HC-05 TXD -> UNO D10   (UNO receives on 10)
    HC-05 RXD <- UNO D9    (UNO transmits on 9)

  Serial Monitor: 38400 baud, line ending "Both NL & CR".
*/
#include <SoftwareSerial.h>

SoftwareSerial bt(10, 9);          // RX = D10 (from BT TXD), TX = D9 (to BT RXD)

void setup() {
  Serial.begin(38400);             // USB side (Serial Monitor must match)
  bt.begin(38400);                 // HC-05 AT-mode speed (fixed at 38400 in config mode)
  Serial.println(F("Ready. Put the HC-05 in config mode, then type AT"));
}

void loop() {
  if (Serial.available()) {        // PC -> module
    bt.write(Serial.read());
  }
  if (bt.available()) {            // module -> PC, byte by byte (no 1 s readString delay)
    Serial.write(bt.read());
  }
}

/*
  Leave config mode: power-cycle the HC-05 WITHOUT holding its button.
*/
