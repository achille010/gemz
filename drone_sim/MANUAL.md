# DRONE SIM - manual

An FPV quadcopter simulator over a sunlit city. It has real momentum, drag and lean-to-move
flight, three cameras, seven built-in missions and an endless mission generator. You can fly it
with the keyboard, a touchpad or mouse, a USB gamepad, or your lab-made two-stick Arduino pad -
one pad to fly, an optional second one as co-pilot.

The picture is drawn in software (pygame + numpy). The sky, clouds, sun, mountains and textured
ground with roads are drawn one ray per pixel, so the horizon tilts when the drone banks.
Buildings are lit by the sun, have windows and cast shadows, and there are trees with shadows.
The drone is a full 3D model with spinning rotors and LEDs. Propellers kick up dust near the ground,
and crashes throw debris and smoke.

---------------------------------------------------------------------------------------------

## 1. Run it (Windows)

Double-click **`play.bat`**. The first time, it installs `pygame-ce`, `numpy` and `pyserial`
by itself. That opens the **launcher**, which owns the menus, the Arduino pads, the mission
generator and your saves, and then starts the game for each mission.

| File | What it opens |
|---|---|
| **`play.bat`** | The launcher - this is the normal way to play |
| `pad_check.bat` | The launcher, straight on the controller check screen |
| `fly.bat` | The game on its own, no launcher (keyboard, USB pad, or one cabled Arduino) |
| `gamepad_test.bat` | Prints live stick and click values from a USB pad or the Arduino |

If it feels slow, the game lowers the sky/ground resolution by itself (`auto_quality`). You can
also set `"sky_res": [400, 225]`, `"trees": 200` or `"shadows": false` in **`config.json`**.
F11 = fullscreen, F12 = screenshot.

### What is in the folder

| | |
|---|---|
| `launcher.py` | Menus, campaign saves, the two pads, the controller check, mission briefings |
| `drone_sim.py` | The simulator: physics, renderer, HUD, the 7 built-in missions |
| `pads.py` | Reads the Arduino pads (HC-05 Bluetooth or USB cable) and maps them to pilot / co-pilot |
| `missions.py` | The mission generator (run it on its own to print a sample campaign) |
| `sfxgen.py` | The launcher's menu sounds; `python sfxgen.py --export` dumps the game's sounds as .wav |
| `config.json` | **All** the settings, for the game and the launcher. Created on the first run |
| `save.json` | Campaign progress, ops flown and won |
| `highscore.json` | Stars and best scores for the 7 built-in missions |
| `run/` | `mission.json` and `result.json` - how the launcher and the game talk |
| `arduino/` | `drone_pad` (the pad sketch), `bt_setup`, `bt_slave_config`, `drone_sim_serial`, `drone_sim_hid` |
| `MANUAL.md` `PAD_GUIDE.md` `HARDWARE_GUIDE.md` `ard.md` | This file, the one-page pad guide, the full build guide, the lab snippet |

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

**Menus with only the pad:** push either stick up/down to choose. A **right click** means
select, launch, retry or resume. A **left click** means back.

**Co-pilot (second pad, optional):** its clicks do the camera, stabilize and pause jobs, so
someone else can run the camera while you fly. Turn it off with `C` on the controller check.

**Flight assists (easy to fly):** let go of the right stick and the drone levels itself and
brakes. Let go of the left stick and it holds its altitude. Tune them with `"assist"` and
`"alt_hold"` in `config.json` (0 = pure physics, for experts).

The HUD shows the compass with the direction of the next target, speed, altitude and climb rate,
a target marker with its distance (or an edge arrow when it's off screen), and **live stick boxes**
(bottom left) that show exactly what your pad sends. The clicks light up yellow.
If you're about to hit something, **OBSTACLE** or **PULL UP** flashes with a beep.

## 3. The launcher

| Menu item | What it does |
|---|---|
| **Campaign - Mission N** | The generated campaign. Mission N is always the same op (seeded) and gets harder every 3 missions. Win it and you move to mission N+1 (`save.json`) |
| **Random Operation** | A fresh generated op at a random difficulty. "New random mission" rerolls it from the briefing |
| **Solo Operation** | The same, two difficulty steps easier, more time, less wind - for one pad or a first try |
| **Built-in Missions** | The original 7 below, with their stars and best scores |
| **Controller Check** | Stick dots, clicks, ports, the orientation wizard, simulated pads. See `HARDWARE_GUIDE.md` §6 |
| **Hardware Guide** | Opens `HARDWARE_GUIDE.md` |

A generated op's briefing tells you the course, the district, the weather, the difficulty, the
clock, the wind, the battery numbers and what each modifier does - and every one of those is a
real setting the game then flies, not decoration. Run `python missions.py` to print a sample
campaign.

**Courses:** Gate Rush, Slalom Sprint, Altitude Ace, Precision Landing, Delivery Run, and
Grand Tour (a long gate course ending in a landing).
**Modifiers:** undersized gates, heavy airframe, part-charged battery, no recharge at
checkpoints, extended course, strict clock, squalls.

While a mission runs, keep the launcher window open: it is what streams your pads to the game
(UDP 127.0.0.1:47800). When the mission ends the launcher shows the result and your stars.

## 4. Missions and challenge

The 7 built-in missions are a campaign of their own: **finish one (1 star) to unlock the next.**
Up to 3 stars each, 18 in total, kept in `highscore.json`.

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

Too hard or too easy? In `config.json`: `"wind_scale"` (0 = calm, 1.5 = nastier), `"battery_scale"`
(0 = infinite battery), `"unlock_all": true` (play any built-in mission), `"assist"` / `"alt_hold"`
(0 = expert physics). Generated ops also have a **Solo** mode, which is the gentler version.

## 5. Settings (`config.json`)

Everything lives in one file next to the game, written on the first run. The defaults are the
`CONFIG` dict at the top of `drone_sim.py` plus the launcher's own keys - anything you put in
`config.json` wins, and missing keys are filled back in, so you can delete the file to reset.

| Key | What it does |
|---|---|
| `window_size` `fullscreen` `fov_degrees` | Window and view |
| `sky_res` `auto_quality` `draw_distance` `shadows` `trees` | Picture quality / speed |
| `sound` `volume` `engine_volume` `wind_volume` `sound_volumes` | Sound (see §6) |
| `assist` `alt_hold` `wind_scale` `battery_scale` `unlock_all` | How hard it flies |
| `gamepad` | USB pad axis and button numbers, deadzone, inverts |
| `arduino` | The cabled pad when you run the game without the launcher: port, baud, deadzone, inverts, `swap_sticks` |
| `clicks` `single_click` `hold_time` `double_time` | What tap / double tap / hold do on each click |
| `p1` `p2` `baud` `deadzone` `click_guard` `invert` `map` `copilot` | **Launcher keys**: which pad is which, and the controller check's saved fixes |

`p1` / `p2` take `"auto"`, a COM port (`"COM19"`) or an HC-05 address
(`"0021:07:001EE9"`). `map` is written by the orientation wizard; `invert` by keys `1`-`8` on
the controller check. The launcher and the game each write back only their own keys, so they
never clobber each other.

## 6. Sounds

Everything has its own sound. The motor whine crossfades with throttle and the wind rushes with speed.
There are also sounds for gates, combos, the countdown, touchdown, crashes, warnings, camera, turbo,
precision, stabilize, pause, resume, menus, low
battery, battery empty, gate clip, gusts, parcel pickup and drop, and stars. Settings live in `config.json`:

* `"volume"` (effects, 0-1), `"engine_volume"`, `"wind_volume"`
* `"sound_volumes"`: one sound louder or quieter, e.g. `{"warn": 0.4, "gate": 1.0}` (0 = mute it)
* Your own sounds: put `sounds/<name>.wav` (or .ogg) in the game folder, e.g. `sounds/crash.wav`.
  The motor and wind loops can be replaced too (`eng_lo`, `eng_mid`, `eng_hi`, `wind`).
* **`python sfxgen.py --export`** writes every built-in sound to `sounds/gen/*.wav`. Edit one
  there and copy it into `sounds/` to override it - much easier than guessing a name.
* The launcher's own menu sounds live in `sounds/launcher/` (`python sfxgen.py` rebuilds them).

## 7. Your Arduino two-stick pad

Windows does **not** see an UNO as a gamepad. It's a COM port, and the launcher reads it directly -
over the USB cable, or over HC-05 Bluetooth once paired. One pad flies; a second is the co-pilot.

**Short version:** build it per `HARDWARE_GUIDE.md`, flash `arduino/drone_pad/drone_pad.ino`,
pair it, run `play.bat` with your thumbs off the sticks for a second. Day-to-day use and the
full troubleshooting table are in **`PAD_GUIDE.md`**.

1. **Wiring** (KY-023 style stick modules, +5V to 5V, GND to GND):
   left stick VRx to A0, VRy to A1, SW to D2; right stick VRx to A2, VRy to A3, SW to D3.
   HC-05: VCC to 5V, GND to GND, TXD to D10, RXD to D9 **through a 1k/2k divider**.
2. **Sketch:** `arduino/drone_pad/drone_pad.ino` sends `J,lx,ly,rx,ry,lclick,rclick` to both the
   cable and the Bluetooth module. The `strike_team`/`vault_runner` pad sketches work here too.
3. **Close the Arduino IDE Serial Monitor and any other game** - only one program can hold a COM port.
4. Start with your **thumbs off the sticks** for a second, so the centre can be measured.
   The launcher's bottom bar then reads `PILOT: Bluetooth COM19 - ready`.
5. Check directions in `pad_check.bat`. If a stick is rotated or reversed, press **`O`** (pad 1)
   or **`P`** (pad 2) for the 4-prompt orientation wizard - that is the proper fix. Keys `1`-`8`
   flip single axes, `S` swaps pilot and co-pilot, `R` recalibrates. All saved to `config.json`.

The launcher finds the ports and baud rate by itself and reconnects if you unplug a cable.
Without the launcher (`fly.bat`), the game reads one cabled Arduino directly, using the
`"arduino"` settings - and a one-stick sketch (lines like `x,y,sw`) still works there: the stick
climbs/descends and turns, the click taps stabilize, double-taps change camera, and holding it
flies forward.

### Troubleshooting

| Problem | Fix |
|---|---|
| "no pad" / "no Arduino found" | Plug it in, close the Serial Monitor and other games, check Device Manager > Ports |
| Drone drifts by itself | Keep the sticks still at start-up, press `R` on the controller check, or raise `"deadzone"` to 0.2 |
| A direction is reversed | `pad_check.bat`: `O`/`P` wizard, or keys `1`-`8` |
| Clicks do the wrong thing | Edit `"clicks"` in `config.json` (tap / double / hold for each click) |
| Clicks fire by themselves | Lower `"click_guard"` (e.g. 0.4); `1.5` turns the guard off |
| Laggy over Bluetooth | Set the module **and** `BT_BAUD` in the sketch to 38400 (`HARDWARE_GUIDE.md` §3) |
| No sound | The console prints `Sound disabled: <reason>`. Check the Windows output device |
| Low FPS | Lower `sky_res`, `trees`, or turn `shadows` off |
| Launcher says the game won't start | Run `fly.bat` once - it prints the real Python error |
