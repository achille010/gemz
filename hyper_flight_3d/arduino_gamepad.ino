/*
 * HYPER FLIGHT 3D - Arduino UNO Dual Joystick Gamepad Firmware
 * 
 * Hardware Wiring Guide for Arduino UNO:
 * --------------------------------------------------
 * Left Joystick:
 *   - VRX  --> Analog Pin A0 (Left/Right - Yaw/Roll)
 *   - VRY  --> Analog Pin A1 (Up/Down - Pitch)
 *   - SW   --> Digital Pin D2 (Left Stick Click - Reset View / Lock On)
 * 
 * Right Joystick:
 *   - VRX  --> Analog Pin A2 (Pan Camera X / Throttle Fine)
 *   - VRY  --> Analog Pin A3 (Throttle Up/Down)
 *   - SW   --> Digital Pin D3 (Right Stick Click - Change Camera Mode)
 * 
 * External Push Buttons / Triggers:
 *   - Button 1 (Fire Laser)    --> Digital Pin D4 (with internal pullup)
 *   - Button 2 (Fire Missile)  --> Digital Pin D5 (with internal pullup)
 *   - Button 3 (Boost Speed)   --> Digital Pin D6 (with internal pullup)
 * 
 * Power:
 *   - Connect VCC of both joysticks to 5V on Arduino
 *   - Connect GND of both joysticks and buttons to GND on Arduino
 * 
 * Serial Output Format:
 *   JOY:LX,LY,SW1,RX,RY,SW2,B1,B2,B3
 *   Example: JOY:512,508,1,514,510,1,1,1,1
 */

const int PIN_LX = A0;  // Left Joystick X (Roll/Yaw)
const int PIN_LY = A1;  // Left Joystick Y (Pitch)
const int PIN_SW1 = 2;  // Left Joystick Switch

const int PIN_RX = A2;  // Right Joystick X (Camera Yaw)
const int PIN_RY = A3;  // Right Joystick Y (Throttle / Pitch Fine)
const int PIN_SW2 = 3;  // Right Joystick Switch

const int PIN_BTN1 = 4; // Fire Laser
const int PIN_BTN2 = 5; // Launch Missile
const int PIN_BTN3 = 6; // Boost Engine

void setup() {
  // Initialize Serial Communication at 115200 Baud
  Serial.begin(115200);

  // Configure Digital Pin Modes with internal pull-up resistors
  pinMode(PIN_SW1, INPUT_PULLUP);
  pinMode(PIN_SW2, INPUT_PULLUP);
  pinMode(PIN_BTN1, INPUT_PULLUP);
  pinMode(PIN_BTN2, INPUT_PULLUP);
  pinMode(PIN_BTN3, INPUT_PULLUP);

  // Ready signal
  Serial.println("HYPER_FLIGHT_ARDUINO_READY");
}

void loop() {
  // Read Analog Joystick values (0 - 1023)
  int lx = analogRead(PIN_LX);
  int ly = analogRead(PIN_LY);
  int rx = analogRead(PIN_RX);
  int ry = analogRead(PIN_RY);

  // Read Digital Button values (Active LOW due to INPUT_PULLUP)
  int sw1 = digitalRead(PIN_SW1) == LOW ? 1 : 0;
  int sw2 = digitalRead(PIN_SW2) == LOW ? 1 : 0;
  int b1  = digitalRead(PIN_BTN1) == LOW ? 1 : 0;
  int b2  = digitalRead(PIN_BTN2) == LOW ? 1 : 0;
  int b3  = digitalRead(PIN_BTN3) == LOW ? 1 : 0;

  // Format and transmit over Serial stream
  Serial.print("JOY:");
  Serial.print(lx); Serial.print(",");
  Serial.print(ly); Serial.print(",");
  Serial.print(sw1); Serial.print(",");
  Serial.print(rx); Serial.print(",");
  Serial.print(ry); Serial.print(",");
  Serial.print(sw2); Serial.print(",");
  Serial.print(b1); Serial.print(",");
  Serial.print(b2); Serial.print(",");
  Serial.println(b3);

  // Transmission delay (~60Hz update rate matching screen frame rate)
  delay(16);
}
