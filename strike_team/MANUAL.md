# STRIKE TEAM

Two-player **co-op** tactical shooter. Split screen, two spawn points, three lives each, endless
procedurally generated missions. Python (pygame) launcher + Godot 4 3D engine.

## Start

- **`play.bat`**: menu (Campaign / Random Operation / Controller Check / Hardware Guide)
- **`pad_check.bat`**: test the pads only
- `python launcher.py --quick`: jump straight into a random operation

Needs Python with `pygame-ce` + `pyserial` (play.bat installs them) and **Godot 4.3+** (found
automatically in `C:\Tools`; otherwise set `"godot_exe"` in `config.json`).

## Controls

| | Arduino pad | Keyboard P1 (testing) | Keyboard P2 (testing) | Xbox / USB pad |
|---|---|---|---|---|
| Move | left stick | W A S D | I J K L | left stick |
| Crouch (toggle) | **click** left stick | C | Shift | L3 / B |
| Look | right stick (up/down limited to ±55°) | Q E (turn), R F (up/down) | arrows | right stick |
| Shoot (hold = auto) | **click** right stick | Space | Enter | R3 / right trigger |

`Esc` in the game aborts the mission.

## Rules

- **Blue (P1) and Red (P2)** start at two different spawn points. A coloured arrow always floats
  over your teammate's head, visible through walls.
- **Mini map** (top right, turns with you): **green** = your squad, **red** = enemies,
  **yellow** = objective, **white squares** = ammo, **pink crosses** = medkits.
- **Downed** at 0 HP. You have **60 seconds**. Your teammate must pick up a **medkit** (pink)
  and stand next to you for 3 s to revive you. Bleed out = lose a life and respawn at your spawn.
  **3 lives each.** Out of lives = out of the mission.
- **Both of you down at the same time = MISSION FAILED.**
- When only one of you is standing, the screen switches from split to **one full screen**.
- **Ammo:** 30-round mag, reloads automatically. You carry **12 reloads**; after that you must
  find **ammo crates** (marked on the map, and shown on screen when you're low). Each crate = +4.
- Health regenerates after 5 s without damage (unless the mission says *No regen*).
- Crouching: steadier aim, harder to hit, slower.

## Missions

Every mission has **one specific task**. Killing everybody never wins.

| Task | What to do |
|---|---|
| Defuse the Bomb | reach the bomb, stay next to it until defused, before the timer ends |
| Hack the Terminal | stay near the terminal while it uploads; waves attack you |
| Sabotage | plant charges on every radar / fuel tank, then extract |
| Steal the Intel | grab the laptop, carry it to extraction (drops if the carrier goes down) |
| Hostage Rescue | find the hostage, they follow you, bring them to extraction |
| High Value Target | kill the gold-uniform commander, then extract |
| Hold the Line | keep someone inside the zone for the required time, then extract |
| Supply Run | collect every supply case, then extract |

**Extraction**: *every* player still in the mission must be standing (not downed) inside the green
zone. Nobody gets left behind.

Modifiers stack as difficulty climbs: fog, night, armoured heavies, scarce ammo, sharpshooters,
reinforcements, no regen, strict time limits. 6 maps (city, military base, desert village, frozen
outpost, forest camp, harbour docks) x day / dusk / night, all generated from the mission seed.

**Campaign**: mission N is always the same mission; win it to unlock N+1 (harder every 3 missions,
max difficulty 10). **Random Operation**: a fresh mission every time.

## Files

```
launcher.py      app entry: menus, pads, missions, saves, starts Godot, streams pads over UDP
pads.py          Bluetooth / USB Arduino pad reader
missions.py      mission generator  (python missions.py = preview the campaign)
sfxgen.py        placeholder sound effects
godot/           the 3D game (main.gd, player.gd, bot.gd, world_gen.gd, hud.gd)
arduino/         fight_pad (the controller), bt_setup (HC-05 / HC-06 AT configuration)
assets/          drop real models / textures / sounds here (see assets/README.md)
config.json      pads, Godot path, fullscreen   (created on first run)
save.json        campaign progress
```
