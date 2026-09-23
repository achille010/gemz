/*
  CURSOR DASH - serial sketch  (Option B)
  Works on ANY Arduino: Uno, Nano, Mega, ESP32, ESP8266 ... (no native USB gamepad needed).
  It prints one line per update:   J,<leftX>,<leftY>,<rightX>,<rightY>,<leftClick>,<rightClick>
  The game reads it with:          python cursor_dash.py --serial COM5

  Wiring (usual 5-pin analog stick modules):
      LEFT  stick : VRx -> A0   VRy -> A1   SW -> D2   +5V -> 5V   GND -> GND
      RIGHT stick : VRx -> A2   VRy -> A3   SW -> D3   +5V -> 5V   GND -> GND
  ESP32 / 3.3 V boards: power the sticks from 3.3 V and change ADC_MAX to 4095.
  Keep the sticks centred when the game starts - it calibrates the centre point by itself.
*/
const int PIN_LX = A0, PIN_LY = A1, PIN_RX = A2, PIN_RY = A3;
const int PIN_LSW = 2, PIN_RSW = 3;
const int ADC_MAX = 1023;            // 4095 on ESP32

void setup() {
  pinMode(PIN_LSW, INPUT_PULLUP);
  pinMode(PIN_RSW, INPUT_PULLUP);
  Serial.begin(115200);
}

// the game expects 0..1023, so rescale if the board has a bigger ADC
int rd(int pin) { return (long)analogRead(pin) * 1023 / ADC_MAX; }

void loop() {
  Serial.print("J,");
  Serial.print(rd(PIN_LX));  Serial.print(',');
  Serial.print(rd(PIN_LY));  Serial.print(',');
  Serial.print(rd(PIN_RX));  Serial.print(',');
  Serial.print(rd(PIN_RY));  Serial.print(',');
  Serial.print(digitalRead(PIN_LSW) == LOW ? 1 : 0); Serial.print(',');
  Serial.println(digitalRead(PIN_RSW) == LOW ? 1 : 0);
  delay(8);                          // ~120 lines / second
}
