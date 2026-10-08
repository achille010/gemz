/*
  STRIKE TEAM - wireless pad  (Arduino UNO + 2 joysticks + HC-05 or HC-06 Bluetooth module)
  Build TWO of these, one per player. Upload the same sketch to both.

  It sends one line per reading:   J,<leftX>,<leftY>,<rightX>,<rightY>,<leftClick>,<rightClick>,<checksum>
  to BOTH the Bluetooth module and the USB cable, so the pad also works plugged in with a cable.

  Controls in the game:
      LEFT  stick : walk forward / back / left / right      LEFT  click : crouch (toggle)
      RIGHT stick : look around (up/down is limited)        RIGHT click : shoot (hold = auto)

  Wiring
      LEFT  stick : VRx -> A0   VRy -> A1   SW -> D2   +5V -> 5V   GND -> GND
      RIGHT stick : VRx -> A2   VRy -> A3   SW -> D3   +5V -> 5V   GND -> GND
      HC-05 / HC-06:
          VCC -> 5V        GND -> GND
          TXD -> D10       (module talks, Arduino listens)
          RXD <- D9 through a voltage divider:  D9 --[1k]--+--[2k]-- GND
                                                           |
                                                       module RXD
          (the module's RXD is 3.3 V logic - the divider turns the UNO's 5 V into ~3.3 V)

  BT_BAUD must equal the module's data-mode speed: 9600 out of the box. If you ran
  AT+UART=38400,0,0 on the HC-05, change it to 38400 (smoother: ~60 updates/s instead of ~30).
*/
#include <SoftwareSerial.h>

SoftwareSerial bt(10, 9);           // RX, TX  - same pins as the slave config guide

const long BT_BAUD = 9600;
const int PIN_LX = A0, PIN_LY = A1, PIN_RX = A2, PIN_RY = A3;
const int PIN_LSW = 2, PIN_RSW = 3;
const int LED = 13;

char line[56];

// The UNO has ONE ADC switched between pins: the first reading after a switch still carries
// the previous stick's voltage (sticks "bleed" into each other). Throw it away, then average 4.
int stick(int pin) {
  analogRead(pin);
  delayMicroseconds(50);
  long t = 0;
  for (int i = 0; i < 4; i++) t += analogRead(pin);
  return t / 4;
}

void setup() {
  pinMode(PIN_LSW, INPUT_PULLUP);
  pinMode(PIN_RSW, INPUT_PULLUP);
  pinMode(LED, OUTPUT);
  Serial.begin(115200);             // USB cable (game finds the baud by itself)
  bt.begin(BT_BAUD);
}

void loop() {
  int lc = digitalRead(PIN_LSW) == LOW ? 1 : 0;
  int rc = digitalRead(PIN_RSW) == LOW ? 1 : 0;
  int lx = stick(PIN_LX), ly = stick(PIN_LY), rx = stick(PIN_RX), ry = stick(PIN_RY);
  // last number = checksum: the PC drops any line damaged on the radio link
  int sum = (lx + ly + rx + ry + lc + rc) % 256;
  snprintf(line, sizeof(line), "J,%d,%d,%d,%d,%d,%d,%d\r\n", lx, ly, rx, ry, lc, rc, sum);
  Serial.print(line);
  bt.print(line);                   // at 9600 baud this takes ~28 ms, which paces the loop
  digitalWrite(LED, rc);            // on-board LED lights while shooting - handy for testing
  if (BT_BAUD > 9600) delay(10);
}
