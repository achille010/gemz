/*
 * HYPER FLIGHT 3D - Arduino Leonardo / Micro / Pro Micro Native USB HID Gamepad
 * Requires "Joystick" library by Matthew Heironimus (Install via Arduino Library Manager)
 */

#include <Joystick.h>

Joystick_ Joystick(JOYSTICK_DEFAULT_REPORT_ID, JOYSTICK_TYPE_GAMEPAD,
  5, 0,                  // Button Count, Hat Switch Count
  true, true, true,      // X, Y, Z Axis
  true, false, false,    // Rx, Ry, Rz Axis
  false, false);         // Rudder, Throttle

const int PIN_LX = A0;
const int PIN_LY = A1;
const int PIN_RX = A2;
const int PIN_RY = A3;

const int PIN_SW1 = 2;
const int PIN_SW2 = 3;
const int PIN_B1  = 4;
const int PIN_B2  = 5;
const int PIN_B3  = 6;

void setup() {
  pinMode(PIN_SW1, INPUT_PULLUP);
  pinMode(PIN_SW2, INPUT_PULLUP);
  pinMode(PIN_B1,  INPUT_PULLUP);
  pinMode(PIN_B2,  INPUT_PULLUP);
  pinMode(PIN_B3,  INPUT_PULLUP);

  Joystick.setXAxisRange(0, 1023);
  Joystick.setYAxisRange(0, 1023);
  Joystick.setZAxisRange(0, 1023);
  Joystick.setRxAxisRange(0, 1023);

  Joystick.begin();
}

void loop() {
  Joystick.setXAxis(analogRead(PIN_LX));
  Joystick.setYAxis(analogRead(PIN_LY));
  Joystick.setZAxis(analogRead(PIN_RX));
  Joystick.setRxAxis(analogRead(PIN_RY));

  Joystick.setButton(0, digitalRead(PIN_SW1) == LOW);
  Joystick.setButton(1, digitalRead(PIN_SW2) == LOW);
  Joystick.setButton(2, digitalRead(PIN_B1)  == LOW);
  Joystick.setButton(3, digitalRead(PIN_B2)  == LOW);
  Joystick.setButton(4, digitalRead(PIN_B3)  == LOW);

  delay(10);
}
