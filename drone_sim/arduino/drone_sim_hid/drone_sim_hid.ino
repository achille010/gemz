/*
  DRONE SIM - USB gamepad sketch  (Option A)
  For boards with NATIVE USB: Arduino Leonardo, Micro, Pro Micro, Esplora, Due (32u4 / SAMD).
  It shows up in Windows as a real "gamepad" with 4 axes + 2 buttons - no extra software needed.
  Only the Y axis of each stick + its click button matter to the game; see drone_sim.py CONFIG.

  Library: "Joystick" by Matthew Heironimus
           Arduino IDE -> Sketch -> Include Library -> Manage Libraries -> search "Joystick"

  Wiring (both sticks are the usual 5-pin analog modules, e.g. KY-023):
      LEFT  stick : VRx -> A0   VRy -> A1   SW -> D2   +5V -> 5V   GND -> GND
      RIGHT stick : VRx -> A2   VRy -> A3   SW -> D3   +5V -> 5V   GND -> GND
*/
#include <Joystick.h>

const int PIN_LX = A0, PIN_LY = A1, PIN_RX = A2, PIN_RY = A3;
const int PIN_LSW = 2, PIN_RSW = 3;

// X, Y = left stick   Rx, Ry = right stick   2 buttons (stick clicks), no hat
Joystick_ pad(JOYSTICK_DEFAULT_REPORT_ID, JOYSTICK_TYPE_GAMEPAD,
              2, 0,
              true, true, false,     // X, Y, Z
              true, true, false,     // Rx, Ry, Rz
              false, false, false, false, false);

void setup() {
  pinMode(PIN_LSW, INPUT_PULLUP);    // click = pulls the pin to GND
  pinMode(PIN_RSW, INPUT_PULLUP);
  pad.setXAxisRange(0, 1023);
  pad.setYAxisRange(0, 1023);
  pad.setRxAxisRange(0, 1023);
  pad.setRyAxisRange(0, 1023);
  pad.begin();
}

void loop() {
  pad.setXAxis(analogRead(PIN_LX));
  pad.setYAxis(analogRead(PIN_LY));
  pad.setRxAxis(analogRead(PIN_RX));
  pad.setRyAxis(analogRead(PIN_RY));
  pad.setButton(0, digitalRead(PIN_LSW) == LOW);   // left stick click  = button 0 (mode toggle)
  pad.setButton(1, digitalRead(PIN_RSW) == LOW);   // right stick click = button 1 (stabilize)
  delay(4);                                        // ~250 updates / second
}
