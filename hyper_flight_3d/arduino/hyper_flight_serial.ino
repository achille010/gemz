/*
 * HYPER FLIGHT 3D - Arduino UNO / Nano / Mega / ESP32 Serial Gamepad Firmware
 * 
 * Hardware Wiring:
 * --------------------------------------------------
 * LEFT JOYSTICK (Flight Pitch & Roll):
 *   - VRx  --> Analog Pin A0  (Roll Axis)
 *   - VRy  --> Analog Pin A1  (Pitch Axis)
 *   - SW   --> Digital Pin D2  (Left Stick Button)
 * 
 * RIGHT JOYSTICK (Yaw Rudder & Throttle):
 *   - VRx  --> Analog Pin A2  (Yaw Rudder Axis)
 *   - VRy  --> Analog Pin A3  (Engine Throttle Axis)
 *   - SW   --> Digital Pin D3  (Right Stick Button)
 * 
 * EXTRA ACTION BUTTONS:
 *   - Fire Laser     --> Digital Pin D4 (INPUT_PULLUP)
 *   - Launch Missile --> Digital Pin D5 (INPUT_PULLUP)
 *   - Boost Speed    --> Digital Pin D6 (INPUT_PULLUP)
 * 
 * POWER:
 *   - Connect Joystick VCC to 5V (or 3.3V)
 *   - Connect Joystick GND to GND
 * 
 * Output Serial Stream (115200 Baud):
 *   J,lx,ly,rx,ry,sw1,sw2,b1,b2,b3
 *   Example: J,512,508,514,510,1,1,1,1,1
 */

const int PIN_LX  = A0;
const int PIN_LY  = A1;
const int PIN_SW1 = 2;

const int PIN_RX  = A2;
const int PIN_RY  = A3;
const int PIN_SW2 = 3;

const int PIN_B1  = 4;
const int PIN_B2  = 5;
const int PIN_B3  = 6;

void setup() {
  Serial.begin(115200);
  pinMode(PIN_SW1, INPUT_PULLUP);
  pinMode(PIN_SW2, INPUT_PULLUP);
  pinMode(PIN_B1,  INPUT_PULLUP);
  pinMode(PIN_B2,  INPUT_PULLUP);
  pinMode(PIN_B3,  INPUT_PULLUP);
  Serial.println("HYPER_FLIGHT_ARDUINO_READY");
}

void loop() {
  int lx  = analogRead(PIN_LX);
  int ly  = analogRead(PIN_LY);
  int rx  = analogRead(PIN_RX);
  int ry  = analogRead(PIN_RY);

  int sw1 = digitalRead(PIN_SW1) == LOW ? 1 : 0;
  int sw2 = digitalRead(PIN_SW2) == LOW ? 1 : 0;
  int b1  = digitalRead(PIN_B1)  == LOW ? 1 : 0;
  int b2  = digitalRead(PIN_B2)  == LOW ? 1 : 0;
  int b3  = digitalRead(PIN_B3)  == LOW ? 1 : 0;

  Serial.print("J,");
  Serial.print(lx);  Serial.print(",");
  Serial.print(ly);  Serial.print(",");
  Serial.print(rx);  Serial.print(",");
  Serial.print(ry);  Serial.print(",");
  Serial.print(sw1); Serial.print(",");
  Serial.print(sw2); Serial.print(",");
  Serial.print(b1);  Serial.print(",");
  Serial.print(b2);  Serial.print(",");
  Serial.println(b3);

  delay(16); // ~60Hz update rate
}
