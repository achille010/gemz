# STRIKE TEAM

Procedurally generated 3D tactical shooter. **1-player solo** (one Arduino BT pad + Michelle-style
split hidden) or **2-player co-op split-screen** (two pads). Python/pygame launcher + Godot 4 3D
engine. Pads talk to the engine over UDP 127.0.0.1:47800.

---

## Start

- Double-click **`play.bat`** -> opens the launcher menu:
  - *Campaign - Mission N* / *Random Operation* -> 2-player split-screen
  - *Solo Operation (1 pad)* -> single player, full-screen, medkit auto-revives
  - *Controller Check (pads / Bluetooth)* -> live pad test, re-centre and rebind
  - *Hardware Guide* -> opens `HARDWARE_GUIDE.md`
- Alternatives:
  - `python launcher.py --quick` -> skip the menu, jump into a random mission
  - `python launcher.py --pads` -> open the controller check directly
  - `pad_check.bat` -> same, from Explorer

Requires: Python 3.10+ (`pygame-ce`, `pyserial` - `play.bat` installs them) and Godot 4.3+.
Godot is found automatically on PATH or in `C:\Tools`; otherwise set `"godot_exe"` in
`strike_team/config.json`.

---

## Controls

### Movement + look + shoot

| Action | Arduino 2-button BT pad | Xbox / USB pad | Keyboard P1 | Keyboard P2 |
|---|---|---|---|---|
| Move | left stick | left stick | `W A S D` | `I J K L` |
| Look / turn | right stick | right stick | `Q E` yaw, `R F` pitch | arrow keys |
| Shoot (hold = auto) | right-stick click | right trigger / R3 | `Space` | `Enter` |
| Crouch (toggle) | left-stick click | left-stick / B | `C` | `Shift` |

### Sniping (scope / aim down sights)

| Platform | Hold to scope |
|---|---|
| Keyboard P1 | `V` |
| Keyboard P2 | `.` (period) |
| Xbox pad | Left trigger (or left bumper) |
| Arduino 2-button pad | tap left-click to crouch, then **hold the fire button** (combo stands in for a dedicated aim button because the pad only has two) |

While scoped:
- FOV 70 -> 32 with a black vignette + circular lens + crosshair.
- Turn and movement drop to ~0.4x for precise aim.
- Spread collapses to near-zero.
- Body-shot damage ramps 34 -> 110: fully scoped shots **one-shot a soldier**, two-shot a heavy,
  one-shot heads on anything.
- View-bob is suppressed so the reticle stays still.
- No scoping with an empty mag or during reload.

`Esc` aborts back to the launcher.

---

## Rules

- **3 lives each**. Taking damage drops you to the **down** state - you can still turn, but you can
  only be revived by a teammate carrying a medkit (co-op) or by your own medkit (solo). After
  **60 s bleed-out** without a revive you lose a life and respawn at your start point.
- **Health regen** (unless the mission mod says otherwise): 5 s after your last hit, HP ticks back
  up to 100.
- **Weapon**: 30-round mag, 12 reloads to start, then you have to pick up ammo crates (white
  marker on the mini-map). Auto reload when the mag empties.
- **Co-op revives** need the medkit pickup first; in solo your medkit auto-revives you after a
  short wait.
- **Mini-map** (top right, rotates with you): green = squad, red = enemies, yellow = objective,
  white = ammo / medkit.

---

## Missions

Eight generated task types, six biomes, three times of day, random difficulty 1-10. The campaign
tracks consecutive wins in `save.json`.

| Task | Goal |
|---|---|
| Defuse | Hold position next to a bomb until the defuse timer completes - timer kills you if it runs out first. |
| Hack | Stand near a terminal to upload. Waves spawn while you upload. |
| Destroy | Plant charges on all radar/fuel targets. |
| Intel | Grab the laptop, carry it to extraction. |
| Rescue | Find the hostage, escort them out. |
| Assassinate | Kill the gold-uniformed commander. |
| Survive | Hold a zone for N seconds against waves. |
| Collect | Recover scattered supply cases. |

All non-survive tasks finish with an **extraction** phase: everyone (and the hostage, if any) must
reach the green zone together.

---

## Visuals and animation (current state)

- **First-person view**: you see the rifle **plus two gloved hands/forearms** gripping it - a
  trigger hand and a forestock hand. In hip-fire the rifle sits lower-right; while scoped it
  pulls to centre of screen for a sight picture.
- **Teammate / enemies**: Mixamo soldier model with Idle / Walk / Run clips, blended by foot
  speed. On top of the clip the game applies procedural animation:
  - **Aim-pitch lean**: upper body tilts up/down to match where you're looking.
  - **Fire recoil**: upper body kicks back on each shot; the rifle kicks and the muzzle flashes.
  - **Reload sway**: shoulders rock while reloading.
  - **Strafe lean**: the body banks sideways when you slide left/right (so strafing visibly
    differs from forward motion).
  - **Crouch**: body shortens vertically; speed drops to ~2.4 m/s and shots tighten.
- **Death / down**: on going down the model switches to a **physics ragdoll** (hips, spine, head,
  arms, legs each simulated with capsules). The push direction is the direction the shot came
  from - you don't just slump straight down, you fall away from the shooter. The ragdoll resolves
  itself on revive by rebuilding a fresh standing visual.
- **Fog**: depth fog from ~55 m to ~210 m matches camera far-plane so the horizon fades without
  washing the whole scene out.
- **Rendering**: FXAA (no MSAA), 220 m draw distance, soft shadows on the directional sun. The
  second viewport is **fully disabled** in solo mode so single-pad play isn't paying for
  split-screen rendering.

---

## Performance tips

- Solo mode is roughly 2x the FPS of co-op (one viewport instead of two). If frames are tight,
  solo first.
- Close OBS, Discord-overlay, and any other GPU overlay before launching.
- Set Windows power plan to **High Performance** - battery-saver throttles the dGPU hard.
- If the game stutters on first load it's shader compilation; the second mission runs clean.
- The game assumes a dedicated GPU or a recent integrated GPU with Vulkan support.

---

## Hardware

See `HARDWARE_GUIDE.md` for the Arduino + HC-05 wiring, AT-command walkthrough, and Windows
pairing. In short: UNO + 2 joysticks + HC-05 per player, bridged by SoftwareSerial, flashed with
`arduino/fight_pad/fight_pad.ino`. The game auto-detects BT COM ports via `pads.py`.

---

## Files

```
strike_team/
  play.bat                        -> launcher entry point
  launcher.py                     -> pygame menu, pad hub, Godot runner
  pads.py                         -> COM-port scanner + stick calibration
  missions.py                     -> procedural mission generator
  arduino/
    bt_setup/bt_setup.ino         -> HC-05 AT-command bridge (one-time BT config)
    fight_pad/fight_pad.ino       -> the pad firmware (both pads use the same sketch)
  godot/
    main.tscn + scripts/*.gd      -> engine, world generator, bots, player, HUD
  assets/                         -> models, textures, sky, sounds (populated by setup_assets.bat)
```

---

## Known behaviour

- Pressing OK on **New random mission** in the brief re-rolls once and then returns the cursor to
  **START MISSION** - one more OK plays it. (If you hold OK you'll re-roll every tick; move the
  stick back up to START instead.)
- The Michelle hostage model renders mirrored on the current rig; the game uses a civilian-tinted
  soldier for the hostage until that is fixed.
- Bluetooth COM ports can take 5-10 s to come up after Windows wake; relaunch the launcher if a
  pad doesn't show green within ~10 s.
