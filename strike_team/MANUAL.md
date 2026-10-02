# STRIKE TEAM

Procedurally generated 3D tactical shooter. **Solo** (one Arduino BT pad OR mouse+keyboard, full-screen) or **2-player co-op split-screen** (two pads). Python/pygame launcher + Godot 4 3D engine. Pads talk to the engine over UDP 127.0.0.1:47800.

---

## Start

Double-click **`strike_team\play.bat`**:

- *Campaign - Mission N* / *Random Operation* -> 2-player split-screen
- *Solo Operation (1 pad)* -> single player, full-screen, mouse+keyboard supported, medkit auto-revives
- *Controller Check (pads / Bluetooth)* -> live pad test, re-centre and rebind
- *Hardware Guide* -> opens `HARDWARE_GUIDE.md`

Alternatives:
- `python launcher.py --quick` -> skip menu, jump into a random mission
- `python launcher.py --pads` -> controller check directly

Requires: Python 3.10+ (`pygame-ce`, `pyserial` — `play.bat` installs them) and Godot 4.3+ (auto-detected on PATH or in `C:\Tools`; override with `"godot_exe"` in `config.json`).

---

## Controls

### Solo (one player)

| Action | Mouse + Keyboard | Xbox / USB pad | Arduino 2-button BT pad |
|---|---|---|---|
| Move | `W A S D` | left stick | left stick |
| Look | mouse motion | right stick | right stick |
| **Sprint** | hold `Shift` (needs forward motion) | **L3** (click left stick) | — (not enough buttons) |
| Crouch (toggle) | `C` | `B` | left-stick click |
| Shoot (hold = auto) | left mouse button, or `Space` | right trigger / R3 | right-stick click |
| **Aim down scope** | hold right mouse button, or `V` | left trigger / LB | tap crouch, then **hold fire** |
| **Throw grenade** | `G` | right bumper (RB) | — |
| **Use medkit** (self-heal to full) | `H` | `Y` | automatic when downed |
| Release / recapture cursor | `Esc` / click | — | — |
| Abort mission | `Esc` (second press) | pad quit | pad quit |

### Co-op (two players, split-screen)

| Action | Keyboard P1 (blue) | Keyboard P2 (red) | Pad / BT pad per player |
|---|---|---|---|
| Move | `W A S D` | `I J K L` | left stick |
| Yaw (turn) | `Q E` | `← →` | right stick (horizontal) |
| Pitch (look up/down) | `R F` | `↑ ↓` | right stick (vertical) |
| Shoot | `Space` | `Enter` | right trigger / R3 / right-click |
| **Aim scope** | hold `V` | hold `.` | left trigger / LB / tap-crouch + hold-fire |
| **Sprint** | hold `Shift` | hold `/` | L3 (left-stick click) |
| Crouch (toggle) | `C` | `N` | B / left-stick click |
| **Throw grenade** | `G` | `,` (comma) | RB |
| **Use medkit** (self or revive teammate) | `H` | `;` (semicolon) | Y |
| Abort | `Esc` | `Esc` | — |

Mouse look is **solo only** (co-op uses pad sticks or keyboard arrows for look).

---

## Cheats (dev / debug)

Press at any time during a mission:

| Key | Effect |
|---|---|
| `F7` | Toggle **God Mode** — players take no damage |
| `F8` | Toggle **Infinite Ammo** — mag never depletes |
| `F9` | **Full Resupply** — fill magazine, 12 reload mags, 9 grenades, medkit for every alive player |
| `F10` | **Skip Objective** — auto-completes current main objective, jumps to extraction |

A banner briefly confirms each toggle.

---

## Rules

- **3 lives each**. Taking damage drops you to the **down** state - you can still turn, but you can only be revived by a teammate holding a medkit (co-op) or by your own medkit (solo). After **60 s bleed-out** without a revive you lose a life and respawn at your start point.
- **Health regen** (unless the mission mod says otherwise): 5 s after your last hit, HP ticks back up to 100.
- **Weapon**: 30-round mag, 12 reloads to start, then pick up ammo crates (white on the mini-map). Auto reload when the mag empties.
- **Grenades**: start with **3**. 3-second fuse. ~7 m lethal radius. 1-second throw cooldown.
- **Sprint**: hold the sprint key while moving forward. Stamina depletes in ~3 s and recharges in ~4.5 s. Can't sprint while crouched or scoped.
- **Medkit** pickups give you one medkit — press medkit key to self-heal (any time, any HP), auto-triggers if you're downed in solo, or lets you revive a teammate in co-op by standing within 2.4 m of them for 3 s.
- **Mini-map** (top right, rotates with you): green = squad, red = enemies, yellow = objective, white = ammo / medkit.

---

## Missions (8 types × 6 biomes × 3 times of day)

| Task | Goal |
|---|---|
| Defuse | Hold position next to a bomb until the defuse timer completes - timer kills you if it runs out first. |
| Hack | Stand near a terminal to upload. Waves spawn during upload. |
| Destroy | Plant charges on all radar/fuel targets. |
| Intel | Grab the laptop, carry it to extraction. |
| Rescue | Find the hostage, escort them to extraction. |
| Assassinate | Kill the gold-uniformed commander. |
| Survive | Hold a zone against waves for N seconds. |
| Collect | Recover scattered supply cases. |

All non-survive missions end with an **extraction** phase: everyone (plus hostage, if any) reaches the green zone together.

**Biomes**: urban, base, desert, snow, forest, docks. **Times**: day, dusk, night. Random mods: `heavy` (more heavies), `scarce` (half the ammo), `no_regen`, `sharpshooters`, `fog`, `reinforcements`.

---

## Difficulty 1 - 10

| Diff | Bots | Accuracy | Damage per hit | Soldier HP | Heavy HP | View |
|---|---|---|---|---|---|---|
| 1 | 7 / 12 | ~0.26 | ~9 | 100 | 240 | 42 m |
| 5 | 11 / 20 | ~0.42 | ~12 | 100 | 240 | 42 m |
| 7 | 15 / 24 | ~0.58 | ~15 | 115 | 285 | 46 m |
| **10** | **24 / 45** | **~0.80** | **~20** | **160** | **420** | **60 m** |

Rows: solo-count / co-op-count.

Difficulty 10 is intended as **extremely hard, near-impossible without cheats or sniping** — enemy density, accuracy, HP and sight range all stack. Try `F7` god mode first to scout, then disable and run it clean.

---

## Items / entities currently in the game

- **Weapons**: Bolt-action battle rifle (`M-762`) + **grenades**. Pistol and rocket-launcher are planned but not yet implemented (would need a weapon-switch state and separate viewmodels — follow-up).
- **Pickups**: ammo crate (+4 mags), medkit (+1 charge), supply case (objective).
- **Props**: concrete barriers, barrels, crates, jerrycans, laptops, radios, lamps, searchlights, generators, cars, hostage, bomb, radar dish — all from Poly Haven CC0 scans.
- **Hidden tanks**: 1-2 abandoned tanks tucked into out-of-the-way corners of the map at every mission (2 at diff 5+). Solid cover with proper collision. Static for now; drivable/destructible is a follow-up.

---

## Visuals and animation (current state)

- **First-person**: hip-fire rifle in the lower-right; **true FP arms require an fp_arms.glb** (shipped `soldier.glb` has arms-at-sides in Idle/Walk/Run, which don't appear in the FP view). Drop any CC0 arms model into `godot/characters/fp_arms.glb` to wire real hands.
- **Teammates / enemies**: Mixamo soldier model with Idle / Walk / Run clips, blended by foot speed. Procedural layers add: aim-pitch lean, fire-recoil kick, reload sway, strafe lean, crouch stance.
- **Death**: physics ragdoll pushed in the direction of the shot that killed you. Rebuilds on revive / respawn.
- **Scope**: FOV 70 → 32, black vignette + lens + crosshair, view-bob suppressed, spread near-zero, body-shot damage ramps 34 → 110.
- **Fog**: 55-210 m depth fog matched to the camera far-plane; distant geometry fades cleanly.
- **Rendering**: FXAA, no MSAA, 220 m draw distance, soft shadows. Solo mode fully disables the second viewport.

---

## Performance

- Solo FPS is ~2x co-op (one viewport). If frames are tight, play solo.
- Close OBS, Discord-overlay, screen-recorders.
- Windows power plan on **High Performance**.
- First-mission shader-compile stutter is normal; the second mission runs clean.

---

## Hardware

See `HARDWARE_GUIDE.md`. In short: UNO + 2 joysticks + HC-05 per player, bridged over SoftwareSerial, flashed with `arduino/fight_pad/fight_pad.ino`. One-time BT config uses `arduino/bt_setup/bt_setup.ino` to send AT commands. The game auto-detects BT COM ports via `pads.py`.

---

## Files

```
strike_team/
  play.bat                        -> launcher entry point
  launcher.py                     -> pygame menu, pad hub, Godot runner
  pads.py                         -> COM-port scanner + stick calibration
  missions.py                     -> procedural mission generator
  arduino/
    bt_setup/bt_setup.ino         -> HC-05 AT bridge (one-time BT config)
    fight_pad/fight_pad.ino       -> pad firmware (both pads use the same sketch)
  godot/
    main.tscn + scripts/*.gd      -> engine, world generator, bots, player, HUD
  assets/                         -> models, textures, sky, sounds (populate with setup_assets.bat)
```

---

## Known limitations / planned

- **FP arms** — need an fp_arms.glb or a shooting-pose animation; current viewmodel is the floating rifle.
- **Weapon switching** (pistol, rocket launcher) — needs a weapon-state refactor; grenades are the first secondary.
- **Drivable / destructible tanks** — currently static cover.
- **F1 EA-Sports-style menu** — pygame launcher is functional but basic; a flashy menu redesign is a follow-up.
- **More missions / biomes** — current 8 × 6 × 3 matrix is already large; additional types will come alongside the menu refresh.

---

## Known behaviour

- **Co-op brief** cursor snaps to START after each re-roll — one OK to re-roll, one more to play.
- The Michelle hostage model renders mirrored on the current rig; the game uses a civilian-tinted soldier for the hostage until fixed.
- Bluetooth COM ports can take 5-10 s to come up after Windows wake; relaunch if a pad doesn't show green within ~10 s.
- Grenade physics bounces are simple RigidBody3D; expect them to roll a bit on slopes.
