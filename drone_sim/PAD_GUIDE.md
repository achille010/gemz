# DRONE SIM - Wireless Pad Guide

Your lab-made two-stick Arduino pad, flying the drone. One page, for when you just want to play.

Windows does **not** see an Arduino UNO as a gamepad - it is a COM port, and `launcher.py`
reads it directly (over the USB cable, or over HC-05 Bluetooth once it is paired).

---

## 1. Every time you play

1. Power the pad (USB cable, or battery if the HC-05 is wired).
2. Double-click **`play.bat`**.
3. **Keep your thumbs off the sticks for one second.** The launcher measures the centre point
   while the sticks rest - that is what stops the drone drifting on its own.
4. The bar at the bottom of the launcher should read `PILOT: Bluetooth COM19 - ready`
   (or `USB COM4`). Then: stick up/down to choose, **right click** to select.
5. Pick **Campaign - Mission N**, read the briefing, right-click **LAUNCH**.

A second pad is optional. If one is connected it becomes the **CO-PILOT**, and its clicks
work the camera, stabilize and pause while you fly.

---

## 2. Controls (Arduino pad)

Standard "mode 2" drone layout: **left stick = up/down and turning, right stick = moving around.**

| You do | What happens |
|---|---|
| **Left stick up / down** | Climb / descend (throttle, Z) |
| **Left stick left / right** | Turn left / right (yaw) |
| **Right stick up / down** | Fly forward / back (pitch) |
| **Right stick left / right** | Slide left / right (roll) |
| **Left click** (tap) | Change camera: chase, FPV, cinematic |
| **Left click** (double tap) | Restart the run |
| **Left click** (hold) | **TURBO** - faster and steeper |
| **Right click** (tap) | **STABILIZE** - kills tilt and drift |
| **Right click** (double tap), or both clicks | Pause |
| **Right click** (hold) | **PRECISION** - slow, fine control |

**Menus with only the pad:** push either stick up/down to choose. **Right click** = select,
launch, retry, resume. **Left click** = back.

**Flight assists (on by default):** let go of the right stick and the drone levels itself and
brakes; let go of the left stick and it holds its altitude. Turn them down in `config.json`
(`"assist"`, `"alt_hold"`; 0 = pure physics, for experts).

### How to fly it properly (important)

* **Small inputs.** The drone has real momentum - it keeps going after you let go. Lead your
  turns and start slowing down before the gate, not at it.
* **Throttle is a rate, not a height.** Centre the left stick to hold altitude, don't chase it.
* **Tilt costs height.** Lean hard and you also sink; feed in a little throttle through a fast turn.
* **Use PRECISION for landings** (hold the right click) and STABILIZE whenever it gets away
  from you - one tap puts it flat and still.
* **Watch the battery.** Throttle, tilt and a parcel all drain it faster. Checkpoints give some back.

---

## 3. What you see on screen

| Where | What |
|---|---|
| Top-centre | **Compass** with the direction of the next target, and the wind gauge |
| Top-left | Mission, clock, score and combo |
| Top-right | **Battery** - it beeps below 25% and the motors quit at 0% |
| Centre | The **target marker** with its distance, or an edge arrow when it is off screen |
| Bottom-left | **Live stick boxes** - exactly what your pad is sending. The clicks light up yellow |
| Bottom-right | Speed, altitude and climb rate |
| Flashing | **OBSTACLE** / **PULL UP** with a beep when you are about to hit something |

---

## 4. Mission flow

1. **Briefing** - course, district, weather, difficulty, the clock, and what the modifiers do.
2. **Countdown**, then fly the checkpoints **in order**. Clipping a gate's edge costs points
   and battery, slows you down, and locks you out of 3 stars.
3. **Finish** = all checkpoints (and a landing, on landing and tour courses).
4. **Stars:** 1 = finished. 2 = 20%+ of the clock left and no clips. 3 = 40%+ left, no clips,
   25%+ battery.
5. Win a **campaign** mission and the launcher moves you to the next one (`save.json`).
   Built-in missions keep their stars and best scores in `highscore.json`.

---

## 5. If something is wrong

| Problem | Fix |
|---|---|
| Camera changes / stabilize fires when you didn't press | **Lower** `"click_guard"` in `config.json` (e.g. `0.4`) so the stick must be more centred before a click counts |
| Can't click while the stick is pushed over | Expected - that guard is what stops accidental clicks. To turn it off: `"click_guard": 1.5` |
| Drone drifts by itself | Restart without touching the sticks for 2 s, or press `R` on the controller check with the sticks centred. Still drifting: raise `"deadzone"` to `0.18` |
| Climbs when you push forward / pulls to one side | The stick module is mounted rotated: `pad_check.bat` -> press **`O`** and follow the 4 prompts |
| One direction is reversed | `pad_check.bat`: keys `1`/`2` flip the left stick X/Y, `3`/`4` the right stick X/Y (saved) |
| Pilot and co-pilot are the wrong way round | `pad_check.bat` -> **`S`** swaps them (saved) |
| Shows "no pad" | Pad powered? LED fast-blinking? Nothing else using the COM port (close the Arduino IDE Serial Monitor)? Wait ~5 s - Windows takes a moment to open a Bluetooth link |
| "semaphore timeout" / "network location cannot be reached" | Module off, out of range, connected to something else, or stale pairing: remove it in Windows Bluetooth settings and pair again (PIN `1234` or `0000`) |
| Garbage values / jumping dots | Baud mismatch: `BT_BAUD` in `arduino/drone_pad/drone_pad.ino` must equal the module's `AT+UART?` |
| Laggy, floaty controls over Bluetooth | 9600 baud is only ~30 updates/s. Run `AT+UART=38400,0,0` (see `HARDWARE_GUIDE.md`) and set `BT_BAUD = 38400` |
| Co-pilot clicks interfere | `pad_check.bat` -> **`C`** turns the co-pilot off |

---

## 6. Wiring reference

| From | To |
|---|---|
| Left stick VRx / VRy / SW | A0 / A1 / D2 |
| Right stick VRx / VRy / SW | A2 / A3 / D3 |
| Both sticks +5V / GND | 5V / GND |
| HC-05 VCC / GND | 5V / GND |
| HC-05 TXD | D10 |
| HC-05 RXD | D9 through a 1k / 2k divider to GND (5 V -> ~3.3 V) |

Sketch: `arduino/drone_pad/drone_pad.ino`. It prints
`J,<lx>,<ly>,<rx>,<ry>,<lclick>,<rclick>` to the cable **and** the Bluetooth module, so the
same pad works either way. Full build: `HARDWARE_GUIDE.md`.
