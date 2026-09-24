# DRONE SIM - manual

An FPV quadcopter simulator over a sunlit city. It has real momentum, drag and lean-to-move
flight, three cameras and five missions. You can fly it with the keyboard, a touchpad or mouse, a USB
gamepad, or your lab-made two-stick Arduino UNO pad.

The picture is drawn in software (pygame + numpy). The sky, clouds, sun, mountains and textured
ground with roads are drawn one ray per pixel, so the horizon tilts when the drone banks.
Buildings are lit by the sun, have windows and cast shadows, and there are trees with shadows.
The drone is a full 3D model with spinning rotors and LEDs. Propellers kick up dust near the ground,
and crashes throw debris and smoke.

---------------------------------------------------------------------------------------------

## 1. Run it (Windows)

Double-click **play.bat**. The first time, it installs `pygame-ce`, `numpy` and `pyserial` by itself.
`gamepad_test.bat` prints live stick and click values from a USB pad or the Arduino.

If it feels slow, the game lowers the sky/ground resolution by itself (`auto_quality`). You can also
set `"sky_res": (400, 225)`, `"trees": 200` or `"shadows": False` in `CONFIG` at the top of `drone_sim.py`.
F11 = fullscreen, F12 = screenshot.

## 2. Controls

Standard "mode 2" drone layout. **Left stick = up/down and turning, right stick = moving around**,
so you fly in all three directions: X (sideways), Y (forward/back) and Z (up/down).

| Action | Two-stick pad (USB or Arduino) | Keyboard |
|---|---|---|
| Climb / descend (Z) | **left stick up / down** | Space / Up, Shift / Down |
| Turn left / right (yaw) | **left stick left / right** | Q / E or Left / Right |
| Fly forward / back | **right stick up / down** | W / S |
| Slide left / right (roll) | **right stick left / right** | A / D |
| Change camera: chase, FPV, cinematic | **left click tap** | C |
| Restart the run | **left click double tap** | R |
| TURBO (faster, steeper) | **hold left click** | hold Tab |
| STABILIZE (kills tilt and drift) | **right click tap** | L |
| Pause | **right click double tap**, or **both clicks** | P / Esc |
| PRECISION (slow, fine control) | **hold right click** | hold X |

Touchpad/mouse: drag = pitch and roll, left button = climb, right button = descend.

**Menus with only the pad:** push either stick up/down to choose a mission. A **right click** means
select, launch, retry or resume. A **left click** means back, or next mission on the title screen.

**Flight assists (easy to fly):** let go of the right stick and the drone levels itself and brakes.
Let go of the left stick and it holds its altitude. Tune them with `"assist"` and `"alt_hold"` in
`CONFIG` (0 = pure physics, for experts).

The HUD shows the compass with the direction of the next target, speed, altitude and climb rate,
a target marker with its distance (or an edge arrow when it's off screen), and **live stick boxes**
(bottom left) that show exactly what your pad sends. The clicks light up yellow.
If you're about to hit something, **OBSTACLE** or **PULL UP** flashes with a beep.

## 3. Missions and challenge

It's a campaign. **Finish a mission (1 star) to unlock the next one.** The title screen shows your
stars (up to 3 per mission, 18 in total). Missions get windier and harder on the battery as you go.

| # | Mission | Goal | Clock | Wind |
|---|---|---|---|---|
| 0 | FREE FLIGHT | training: no clock, no battery, calm air | - | 0 |
| 1 | RING RUSH | 10 gates | 70 s | light |
| 2 | SLALOM SPRINT | pass inside the ground circle of 14 poles, low and fast | 45 s | light |
| 3 | ALTITUDE ACE | hover inside 5 stacked rings for 2 s each | 80 s | gusty |
| 4 | PRECISION LANDING | set down soft and centred on a far pad in a crosswind | 40 s | strong |
| 5 | DELIVERY RUN | land on 4 rooftops: pick up a parcel, drop it, twice. Parcels are heavy | 120 s | strong |
| 6 | STORM RUSH | the final exam: a gate course through a gale | 60 s | storm |

**What makes it hard:**
* **Battery:** it drains faster with throttle, tilt and a parcel on board. Each checkpoint recharges some.
  Below 25% it beeps. At 0% the motors can't hold you and the drone comes down. Land it softly or crash.
* **Wind and gusts:** a breeze that swings round, with gusts ("GUST!") that shove you. It's stronger
  higher up. The HUD wind gauge shows the direction relative to your view.
* **Clipping a gate:** touch a ring's edge and you lose 60 points and 6% battery, get slowed down, and can't get 3 stars.
* **Stars:** 1 = finish. 2 = finish with 20%+ of the clock left and no clipped gates. 3 = 40%+ left,
  no clips, and 25%+ battery.
* **Score:** each checkpoint gives points plus a combo, and the finish adds time left x 8-12 and battery x 5.
  Best scores and stars go in `highscore.json`.

Too hard or too easy? In `CONFIG`: `"wind_scale"` (0 = calm, 1.5 = nastier), `"battery_scale"`
(0 = infinite battery), `"unlock_all": True` (play any mission), `"assist"` / `"alt_hold"` (0 = expert physics).

## 4. Sounds

Everything has its own sound. The motor whine crossfades with throttle and the wind rushes with speed.
There are also sounds for gates, combos, the countdown, touchdown, crashes, warnings, camera, turbo,
precision, stabilize, pause, resume, menus, low
battery, battery empty, gate clip, gusts, parcel pickup and drop, and stars. Settings live in `CONFIG`:

* `"volume"` (effects, 0-1), `"engine_volume"`, `"wind_volume"`
* `"sound_volumes"`: one sound louder or quieter, e.g. `{"warn": 0.4, "gate": 1.0}` (0 = mute it)
* Your own sounds: put `sounds/<name>.wav` (or .ogg) in the game folder, e.g. `sounds/crash.wav`.
  The motor and wind loops can be replaced too (`eng_lo`, `eng_mid`, `eng_hi`, `wind`).
  All the sound names are listed in `CONFIG`.

## 5. Your Arduino UNO two-stick pad

Windows does **not** see an UNO as a gamepad. It's a COM port, and the game reads it directly.

1. **Wiring** (KY-023 style stick modules, +5V to 5V, GND to GND):
   left stick VRx to A0, VRy to A1, SW to D2; right stick VRx to A2, VRy to A3, SW to D3.
2. **Sketch:** the UNO already runs `vault_runner/arduino/vault_pad/vault_pad.ino`, which works for all
   three games. `arduino/drone_sim_serial` also works.
3. **Close the Arduino IDE Serial Monitor and any other game** (only one program can use COM19).
4. Start the game with your **thumbs off the sticks** for a second, so it can measure their centre.
   The title screen shows `Arduino: connected on COM19`.
5. Check directions in `gamepad_test.bat`: left stick up means `ly` is negative and right means `lx`
   is positive; the right stick is the same (`rx`, `ry`). If one is backwards, set its `invert_..`
   flag in `CONFIG["arduino"]`. If the sticks are swapped, set `"swap_sticks": True`.

The game finds the port and baud rate by itself and reconnects if you unplug the cable.
A one-stick sketch (lines like `x,y,sw`) still works: the stick climbs/descends and turns,
the click taps stabilize, double-taps change camera, and holding it flies forward.

### Troubleshooting

| Problem | Fix |
|---|---|
| "no Arduino found" | Plug it in, close the Serial Monitor and other games, check Device Manager > Ports. |
| Drone drifts by itself | Keep the sticks still at start-up, or raise `"deadzone"` to 0.2. |
| A direction is reversed | Toggle the matching `invert_lx / ly / rx / ry`. |
| Clicks do the wrong thing | Edit `CONFIG["clicks"]` (tap / double / hold for each stick). |
| No sound | The console prints `Sound disabled: <reason>`. Check the Windows output device. |
| Low FPS | Lower `sky_res`, `trees`, or turn `shadows` off. |
