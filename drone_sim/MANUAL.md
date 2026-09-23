# DRONE SIM - manual

A hyper-realistic-feel FPV quadcopter simulator: real momentum, drag and lean-to-move flight,
a third-person chase camera, a whole open world of skyline buildings, and five challenges
to master. Fly with keyboard, a touchpad/mouse, a real gamepad, or your lab-made two-stick
Arduino pad.

---------------------------------------------------------------------------------------------

## 1. Get the game running (Windows)

1. Install Python 3.10+ from python.org (tick **"Add python to PATH"**).
2. Open a terminal in this folder (`drone_sim`) and run:

   ```
   pip install -r requirements.txt
   ```
   (`pyserial` in that file is only used by the Arduino serial mode; installing it is harmless.)
3. Start it: double-click **play.bat**, or `python drone_sim.py`.

Press **ESC** at any time to pause. `--joytest` (or `gamepad_test.bat`) prints live axis /
button numbers from whatever pad or Arduino you plug in.

## 2. Flight model

The drone is a momentum-based rigid body, not a cursor: gravity pulls it down, thrust from
the rotors pushes it up, and tilting the airframe forward/back or side-to-side is what makes
it actually move forward or strafe - exactly like a real quadcopter. Push too hard and you'll
overshoot; ease off early. Drag slowly bleeds off speed, so there's real weight and momentum
to every move. The small instrument panel (bottom-left) shows your throttle bar and an
artificial horizon that banks and pitches with the airframe.

## 3. Controls

| | Throttle (Y) | Forward/back (Z) | Left/right (X) | Yaw (turn) | Mode-switch | Stabilize |
|---|---|---|---|---|---|---|
| **Keyboard** | Space/Up = up, Shift/Down = down | W / S | A / D | Left/Right or Q/E | TAB | L |
| **Touchpad/Mouse** | left-click = up, right-click = down | drag pad/mouse | drag pad/mouse | - | - | L |
| **Two-stick pad** | LEFT stick up/down (FLY mode) | RIGHT stick up/down (FLY mode) | RIGHT stick up/down (STEER mode) | LEFT stick up/down (STEER mode) | LEFT click | RIGHT click |

Other keys: `R` restart the run, `P`/`ESC` pause, `UP`/`DOWN`/`W`/`S` change mission on the
title screen.

## 4. Missions

Pick one from the title screen (Up/Down to browse, Space/Enter to launch):

* **RING RUSH** - blast through 10 floating gates, in order, before the clock runs out.
  Consecutive gates build a combo for bonus points.
* **SLALOM SPRINT** - thread 14 low poles left-right-left as fast as you can.
* **ALTITUDE ACE** - climb to each glowing ring and hold your altitude inside it for 2 seconds
  before the next one appears.
* **PRECISION LANDING** - fly to the distant pad and touch down soft (low vertical *and*
  horizontal speed) and centred. Time bonus for a quick, gentle landing.
* **FREE FLIGHT** - no clock, no fail state beyond a hard crash. Explore the skyline, practice
  your lean-to-move flying.

Crashing into the ground too hard, or clipping a building, ends the run early (except in Free
Flight, where a soft touchdown is fine). Best score per mission is saved in `highscore.json`.

---------------------------------------------------------------------------------------------

## 5. Your lab-made two-stick pad

Your controller only ever gives the game **6 signals**: each stick's UP, DOWN, and CLICK.
Every one of those 6 signals does something completely different on screen - that's the whole
control scheme, no face buttons needed:

| Signal | FLY mode (default) | STEER mode |
|---|---|---|
| LEFT stick UP | Throttle up (climb) | Yaw left |
| LEFT stick DOWN | Throttle down (descend) | Yaw right |
| LEFT stick CLICK | **Switch to STEER mode** | **Switch back to FLY mode** |
| RIGHT stick UP | Pitch forward (move forward) | Strafe right |
| RIGHT stick DOWN | Pitch back (move backward) | Strafe left |
| RIGHT stick CLICK | **Stabilize** (kill tilt & drift - works in either mode, any time) |

The current mode is always shown top-right during play. Left/right tilt (the X axis) on each
stick isn't used at all - only push up, push down, and click matter, which is exactly what the
lab rig can reliably give you.

### Wiring (either Arduino option)

Two 5-pin analog joystick modules (e.g. KY-023):

```
LEFT  stick : VRx -> A0   VRy -> A1   SW -> D2   +5V -> 5V   GND -> GND
RIGHT stick : VRx -> A2   VRy -> A3   SW -> D3   +5V -> 5V   GND -> GND
```

### Option A - native USB gamepad (`arduino/drone_sim_hid/drone_sim_hid.ino`)

For boards with real USB hardware: Leonardo, Micro, Pro Micro, Esplora, Due. Install the
**"Joystick" by Matthew Heironimus** library (Library Manager), flash the sketch, and the
board just shows up as a Windows gamepad - no drivers, no `--serial` flag needed.

### Option B - any Arduino, over a serial cable (`arduino/drone_sim_serial/drone_sim_serial.ino`)

Works on an Uno, Nano, Mega, ESP32 ... anything. It prints one line per update
(`J,leftX,leftY,rightX,rightY,leftClick,rightClick`). Flash it, find its COM port in the
Arduino IDE, then run:

```
python drone_sim.py --serial COM5
```

(or set `"serial": {"port": "COM5"}` in the `CONFIG` block at the top of `drone_sim.py` so you
don't need the flag every time). Keep both sticks centred for about a second when the game
starts - it auto-calibrates the centre point from whatever it reads first.

If a stick reads inverted (up feels like down), flip `invert_throttle` / `invert_pitch` in
`CONFIG["gamepad"]` at the top of `drone_sim.py`. If a stick feels numb near centre or twitchy
at the edges, adjust `deadzone` or `digital_thresh` in the same block.
