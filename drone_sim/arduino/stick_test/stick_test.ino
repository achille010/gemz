/*
  STICK TEST - finds out if a joystick module, a wire or an Arduino pin is bad.
  USB only (no Bluetooth needed). Serial Monitor at 115200.

  Prints every analog pin A0..A5 and the clicks D2, D3 ten times a second:
     A0=512 A1=508 | A2=511 A3=515 | A4=.. A5=.. | D2=up D3=up
  A healthy stick: ~512 at rest, goes to ~0 and ~1023 at the edges, smoothly.
*/
void setup() {
  pinMode(2, INPUT_PULLUP);
  pinMode(3, INPUT_PULLUP);
  Serial.begin(115200);
  Serial.println(F("Stick test. Move ONE stick at a time."));
}

int rd(int pin) {
  analogRead(pin);                 // throw away the first reading after switching pins
  delayMicroseconds(50);
  return analogRead(pin);
}

void loop() {
  char b[96];
  snprintf(b, sizeof(b), "A0=%4d A1=%4d | A2=%4d A3=%4d | A4=%4d A5=%4d | D2=%s D3=%s",
           rd(A0), rd(A1), rd(A2), rd(A3), rd(A4), rd(A5),
           digitalRead(2) ? "up  " : "DOWN", digitalRead(3) ? "up  " : "DOWN");
  Serial.println(b);
  delay(100);
}
