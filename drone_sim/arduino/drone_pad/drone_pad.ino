/*
  DRONE SIM - wireless pad  (Arduino UNO + 2 joysticks + HC-05 or HC-06 Bluetooth module)

  Build ONE for the pilot. Build a SECOND one if you want a co-pilot. Same sketch on both -
  only the Bluetooth NAME differs (set it with bt_setup: DRONE-P1 and DRONE-P2).

  It sends one line per reading:   J,<leftX>,<leftY>,<rightX>,<rightY>,<leftClick>,<rightClick>,<checksum>
  to BOTH the Bluetooth module and the USB cable, so the pad also works plugged in with a cable.
  launcher.py reads it (pads.py) and streams it to the game.

  Controls in the game (standard "mode 2" drone layout):
      LEFT  stick : up/down = throttle (climb / descend)   left/right = yaw (turn)
      RIGHT stick : up/down = pitch (forward / back)       left/right = roll (slide sideways)
      LEFT  click : tap = camera    double tap = restart   hold = TURBO
      RIGHT click : tap = stabilize double tap = pause     hold = PRECISION
      Pad 2 (co-pilot): its clicks do the same camera / stabilize / pause jobs.

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
  A flight pad really wants the faster rate - 9600 is usable but you can feel the lag.

  3.3 V boards (ESP32 etc.): power the sticks from 3.3 V and set ADC_MAX to 4095.
  Keep your thumbs OFF the sticks for a second at start-up: the launcher measures their centre.
*/
#include <SoftwareSerial.h>

SoftwareSerial bt(10, 9);           // RX, TX  - same pins as the slave config guide

const long BT_BAUD = 9600;          // 38400 after AT+UART=38400,0,0  (recommended for flying)
const int PIN_LX = A0, PIN_LY = A1, PIN_RX = A2, PIN_RY = A3;
const int PIN_LSW = 2, PIN_RSW = 3;
const int ADC_MAX = 1023;           // 4095 on ESP32 and other 12-bit boards
const int LED = 13;

char line[56];

// the launcher expects 0..1023, so rescale if this board has a bigger ADC
// The UNO has ONE ADC switched between pins: the first reading after a switch still carries
// the previous stick's voltage (sticks "bleed" into each other). Throw it away, then average 4.
int stick(int pin) {
  analogRead(pin);
  delayMicroseconds(50);
  long t = 0;
  for (int i = 0; i < 4; i++) t += analogRead(pin);
  return t / 4;
}

int rd(int pin) { return (long)stick(pin) * 1023 / ADC_MAX; }

void setup() {
  pinMode(PIN_LSW, INPUT_PULLUP);
  pinMode(PIN_RSW, INPUT_PULLUP);
  pinMode(LED, OUTPUT);
  Serial.begin(115200);             // USB cable (the launcher finds the baud by itself)
  bt.begin(BT_BAUD);
}

void loop() {
  int lc = digitalRead(PIN_LSW) == LOW ? 1 : 0;
  int rc = digitalRead(PIN_RSW) == LOW ? 1 : 0;
  int lx = rd(PIN_LX), ly = rd(PIN_LY), rx = rd(PIN_RX), ry = rd(PIN_RY);
  // last number = checksum: the PC drops any line damaged on the radio link
  int sum = (lx + ly + rx + ry + lc + rc) % 256;
  snprintf(line, sizeof(line), "J,%d,%d,%d,%d,%d,%d,%d\r\n", lx, ly, rx, ry, lc, rc, sum);
  Serial.print(line);
  bt.print(line);                   // at 9600 baud this takes ~28 ms, which paces the loop
  digitalWrite(LED, rc);            // on-board LED lights while the right click is down
  if (BT_BAUD > 9600) delay(10);    // ~60 updates/s at 38400
}
