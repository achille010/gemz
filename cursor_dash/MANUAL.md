# CURSOR DASH - manual

You are the mouse cursor. The tunnel rushes at you, climbs, dives, banks and whips through
turns. Slip through holes, dodge pillars, blades, lasers and crushers - up, down, left, right.

---------------------------------------------------------------------------------------------

## 1. Get the game running (Windows)

1. Install Python 3.10+ from python.org (tick **"Add python to PATH"**).
2. Open a terminal in this folder (`cursor_dash`) and run:

   ```
   pip install -r requirements.txt
   ```
   (`pyserial` in that file is only used by the Arduino serial mode; installing it is harmless.)
3. Start it: double-click **play.bat**, or `python cursor_dash.py`.

Slow? Lower `render_size` in the `CONFIG` block at the top of `cursor_dash.py`
(e.g. `(800, 450)`), or set `"bloom": 0`. Press **F3** in game to see the FPS.

## 2. Controls

| Action | Mouse / keyboard | Two-stick pad (USB or Arduino) |
|---|---|---|
| Move cursor left/right (X), up/down (Y) | mouse, W A S D / arrows / keypad 8 4 6 2 | **left stick** |
| Speed along the tunnel (Z): boost / brake | R / F (PgUp / PgDn) | **right stick up / down** |
| Look left/right + bank | Q / E | **right stick left / right** |
| Recenter cursor | C / keypad 0 | **left click tap** |
| Music on/off | M | **left click double tap** |
| Precision (slow, fine movement) | hold Shift | **hold left click** |
| Pause / resume | ESC / P | **right click tap** (or both clicks together) |
| Camera: chase / close | V | **right click double tap** |
| DASH (0.7 s invulnerable burst, 5 s cooldown) | SPACE / Tab | **hold right click** |
| Start / retry | SPACE / ENTER / click | any click |
| Difficulty (title) | LEFT / RIGHT | flick a stick, or click double taps |
| Quit to title (paused) | Q | left click tap |

Other keys: `F11` fullscreen, `F12` screenshot, `F3` FPS. Every action has its own sound.

**Sounds** (`CONFIG` at the top of `cursor_dash.py`): `"volume"` (effects, 0-1), `"music_volume"`,
`"engine_volume"`, and `"sound_volumes"` for single sounds, e.g. `{"near": 0.5, "boost": 0}`.
Your own sounds: put `sounds/<name>.wav` (or .ogg) in the game folder, e.g. `sounds/dash.wav`;
`sounds/music.ogg` replaces the music and `sounds/engine.wav` the engine roar. The sound names are
listed in `CONFIG`.

## 3. How to play

* The tunnel is endless. Speed rises the further you go. Every 800 m is a new **stage** with a
  new colour theme and new obstacle types.
* Orange/red-edged solids and red lasers hurt. Neon-cyan is only scenery.
* **Shields** absorb a hit (you blink for ~2 s). No shields left = crash.
* Cyan **shards** = +10. Gold shards = +1 shield (max 3) and +100.
* **Near miss** (skim an obstacle by less than ~0.8 units) = combo. Each combo step is worth
  more (+25, +50, +75 ... up to x12). A hit resets the combo.
* In the turns the tunnel banks and the g-force pushes you outward - lean against it.
* Score = metres + bonuses. Best score is saved in `highscore.json`.

Difficulties: **Easy** (3 shields, slower), **Normal** (2), **Hard** (1, tighter spacing, sharper
turns), **Insane** (no shields, fastest).

Obstacle families (unlock as stages go by): pillars, blocks, bars, holes, side gaps, sliding blocks,
slaloms, diagonal beams, spinning blades, laser sweeps, crushers, block waves, laser grids, and
gauntlets that chain several of them.

---------------------------------------------------------------------------------------------

## 4. Your lab-made two-stick pad

Your controller: two analog sticks, each with left/right (and up/down), and a click. Nothing else.
The game needs **no** face buttons - the stick clicks do everything:

See the controls table in section 2. Each click does three things (tap, double tap, hold),
so the two sticks and their clicks reach every action.

There are **two ways** to connect it. Pick the one that matches your Arduino.

| Your board | Use |
|---|---|
| **Leonardo, Micro, Pro Micro, Esplora, Due** (native USB) | **Option A** - it becomes a real USB gamepad |
| **Uno, Nano, Mega, ESP32, ESP8266**, or unsure | **Option B** - serial cable, works on everything |

### Wiring (both options)

Each stick module (KY-023 style) has 5 pins:

```
LEFT  stick :  VRx -> A0   VRy -> A1   SW -> D2   +5V -> 5V   GND -> GND
RIGHT stick :  VRx -> A2   VRy -> A3   SW -> D3   +5V -> 5V   GND -> GND
```

* `SW` is the click. The sketches use the internal pull-up, so **no resistor** is needed:
  pressing connects it to GND.
* Only have left/right (no VRy)? Wire just `VRx` and read section "Sticks with only left/right".
* ESP32 / 3.3 V boards: power the sticks from 3.3 V, and set `ADC_MAX` to 4095 in the serial sketch.

### Arduino IDE setup (once)

1. Install the Arduino IDE from arduino.cc.
2. Plug the board in. **Tools -> Board** = your board, **Tools -> Port** = the new COM port.
3. Open the sketch (see below) - File -> Open -> the `.ino` file. Click **Upload** (the arrow).

### Option A - USB gamepad (Leonardo / Micro / Pro Micro)

Sketch: `arduino/cursor_dash_hid/cursor_dash_hid.ino`

1. Arduino IDE -> **Sketch -> Include Library -> Manage Libraries**, search **"Joystick"**,
   install *Joystick by Matthew Heironimus*.
2. Upload the sketch.
3. Windows: press **Win+R**, type `joy.cpl`, Enter. A new "Arduino Leonardo" (or similar) device
   appears - open **Properties** and wiggle the sticks: the crosshairs should move.
4. Run `gamepad_test.bat` (see "Find your numbers" below) and start the game. Done.

```cpp
#include <Joystick.h>

const int PIN_LX = A0, PIN_LY = A1, PIN_RX = A2, PIN_RY = A3;
const int PIN_LSW = 2, PIN_RSW = 3;

Joystick_ pad(JOYSTICK_DEFAULT_REPORT_ID, JOYSTICK_TYPE_GAMEPAD,
              2, 0,                      // 2 buttons, no hat
              true, true, false,         // X, Y, Z
              true, true, false,         // Rx, Ry, Rz
              false, false, false, false, false);

void setup() {
  pinMode(PIN_LSW, INPUT_PULLUP);
  pinMode(PIN_RSW, INPUT_PULLUP);
  pad.setXAxisRange(0, 1023);  pad.setYAxisRange(0, 1023);
  pad.setRxAxisRange(0, 1023); pad.setRyAxisRange(0, 1023);
  pad.begin();
}

void loop() {
  pad.setXAxis(analogRead(PIN_LX));
  pad.setYAxis(analogRead(PIN_LY));
  pad.setRxAxis(analogRead(PIN_RX));
  pad.setRyAxis(analogRead(PIN_RY));
  pad.setButton(0, digitalRead(PIN_LSW) == LOW);   // left click  = button 0
  pad.setButton(1, digitalRead(PIN_RSW) == LOW);   // right click = button 1
  delay(4);
}
```

### Option B - serial cable (Uno / Nano / Mega / ESP32 / anything)

Sketch: `arduino/cursor_dash_serial/cursor_dash_serial.ino`

1. Upload the sketch (Vault Runner's `vault_pad.ino` works too, and is what's on your UNO now).
   **Close the Serial Monitor** afterwards: only one program can use the port.
2. Run `play.bat`. The game **finds the COM port and baud rate itself** (or force one with
   `--serial COM19` / `"port": "COM19"` in `CONFIG["arduino"]`). The title screen shows
   `Arduino: connected on COM19`. Close Vault Runner first, because both can't use the port at once.
3. **Keep both sticks untouched for the first second**: the game measures their resting position.
4. A stick going the wrong way: set `invert_lx / invert_ly / invert_rx / invert_ry` in
   `CONFIG["arduino"]`; sticks swapped: `swap_sticks: True`.

```cpp
const int PIN_LX = A0, PIN_LY = A1, PIN_RX = A2, PIN_RY = A3;
const int PIN_LSW = 2, PIN_RSW = 3;
const int ADC_MAX = 1023;            // 4095 on ESP32

void setup() {
  pinMode(PIN_LSW, INPUT_PULLUP);
  pinMode(PIN_RSW, INPUT_PULLUP);
  Serial.begin(115200);
}

int rd(int pin) { return (long)analogRead(pin) * 1023 / ADC_MAX; }

void loop() {
  Serial.print("J,");
  Serial.print(rd(PIN_LX)); Serial.print(',');
  Serial.print(rd(PIN_LY)); Serial.print(',');
  Serial.print(rd(PIN_RX)); Serial.print(',');
  Serial.print(rd(PIN_RY)); Serial.print(',');
  Serial.print(digitalRead(PIN_LSW) == LOW ? 1 : 0); Serial.print(',');
  Serial.println(digitalRead(PIN_RSW) == LOW ? 1 : 0);
  delay(8);
}
```

Any line format works: `lx,ly,rx,ry,lclick,rclick[,...]`, with or without labels such as `J,`, or a one-stick `x,y,sw`.

### Find your numbers (Option A, or any other USB pad)

Windows numbers axes differently per device. To see yours, run **gamepad_test.bat**
(= `python cursor_dash.py --joytest`) and wiggle each stick / click each one:

```
Pad: Arduino Leonardo  axes=4 buttons=2 hats=0
axes [0.0, 0.0, 0.0, 0.0]  pressed []  hats []
axes [-0.98, 0.0, 0.0, 0.0]  pressed []  hats []      <- left stick pushed left = axis 0
```

Then edit the `"gamepad"` block near the top of `cursor_dash.py`:

| Setting | Meaning |
|---|---|
| `axis_x`, `axis_y` | the axes that moved for the LEFT stick |
| `axis_x2`, `axis_y2` | the axes for the RIGHT stick (often 2,3 - or 3,4 on some pads). `-1` = unused |
| `invert_x`, `invert_y` | flip a direction if the cursor goes the wrong way |
| `deadzone` | ignore tiny stick wobble (raise to 0.25 for a worn / cheap stick) |
| `sensitivity` | how fast a full push sweeps the cursor |
| `btn_left`, `btn_right` | button numbers of the left / right stick click |
| `use_hat` | `False` if the device has a hat that misbehaves |

### Sticks with only left/right

If each stick can only go left/right (one axis), use both sticks together:

```python
"split_sticks": True,     # left stick X = cursor left/right, right stick X = cursor up/down
```
Wire only `VRx` on each stick (A0 for the left, A2 for the right). In `--joytest` the
horizontal axis of the left stick should be `axis_x` and of the right stick `axis_x2`.

### Troubleshooting

| Problem | Fix |
|---|---|
| Nothing moves | Run `gamepad_test.bat`. If it prints "No gamepad found": Option A - re-plug, check `joy.cpl`; Option B - check the title screen's `Arduino:` status line. |
| "Could not open serial port" | Close the Arduino Serial Monitor; check the COM number in Device Manager. |
| Cursor drifts by itself | Raise `deadzone` (0.25). In serial mode keep the sticks still for the first second. |
| Left/right or up/down reversed | Toggle `invert_x` / `invert_y`. |
| Only one stick works | Change `axis_x2/axis_y2` to the numbers `--joytest` printed for the right stick. |
| Stick clicks do the wrong thing | Swap `btn_left` and `btn_right`, or edit `CONFIG["clicks"]`. |
| Game reads a different device (a real pad) | Unplug it, or use `--serial`, which takes priority. |
| Stutter / low FPS | Lower `render_size`, set `"bloom": 0`, close other programs. |

---------------------------------------------------------------------------------------------

## 5. Customize (top of `cursor_dash.py`, the `CONFIG` block)

`render_size`, `fov_degrees`, `bloom`, `vignette`, `speed_blur`, `draw_distance`, `sound`,
`stage_length`, plus the four difficulty presets (`speed`, `gap`, `shields`, `curve`) and the
whole `gamepad` / `arduino` / `clicks` / sound sections above.

## 6. Vault Runner note

Vault Runner (`../vault_runner`) now has a small real **up/down head movement** while you walk.
Tune it with `"head_bob_z"` in its CONFIG (`0` = off, `2` = double).
