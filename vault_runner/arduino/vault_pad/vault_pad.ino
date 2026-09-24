// VAULT RUNNER pad - Arduino UNO with two analog thumbsticks (KY-023 / PS2-style modules)
//
// Wiring (both modules: +5V -> 5V, GND -> GND)
//   Left stick : VRx -> A0   VRy -> A1   SW -> D2
//   Right stick: VRx -> A2   VRy -> A3   SW -> D3
//   Optional extra push buttons, each between the pin and GND:
//   D4 torch   D5 map   D6 sneak   D7 jump   D8 pause   D9 level view
//
// Output, 100 lines per second at 115200 baud:
//   lx,ly,rx,ry,b0,b1,b2,b3,b4,b5,b6,b7      (axes 0-1023, buttons 1 = pressed)
// The game finds the COM port and centres the sticks by itself.

const byte AXES[4] = {A0, A1, A2, A3};
const byte BUTTONS[8] = {2, 3, 4, 5, 6, 7, 8, 9};

void setup() {
  Serial.begin(115200);
  for (byte i = 0; i < 8; i++) pinMode(BUTTONS[i], INPUT_PULLUP);
}

void loop() {
  for (byte i = 0; i < 4; i++) {
    Serial.print(analogRead(AXES[i]));
    Serial.print(',');
  }
  for (byte i = 0; i < 8; i++) {
    Serial.print(digitalRead(BUTTONS[i]) == LOW ? 1 : 0);
    Serial.print(i < 7 ? ',' : '\n');
  }
  delay(10);
}
