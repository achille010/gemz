# VAULT RUNNER — Manual

A first-person 3D stealth heist written in **pygame + numpy**.
Sneak through a night-time vault complex, steal loot, find the **keycard**,
open the **vault door** and escape before the alarm goes off. Spend your cash
at the black market between levels and go deeper.

> **Honest note on "hyperrealistic":** pygame has no GPU 3D pipeline, so true
> photorealism isn't possible in it. This game gets as close as a software
> renderer can: a raycaster with procedurally generated brick / marble / metal /
> wood textures, per-pixel dynamic lighting (flashlight, flickering ceiling lamps,
> guards' torches), distance haze, ambient occlusion, head-bob, film grain and
> vignette. For genuinely photoreal visuals you would move to Ursina/Panda3D/
> Godot/Unreal — I can port it if you want.

---

## 1. Install & run

```
pip install pygame-ce numpy pyserial   (or: pip install -r requirements.txt)
python vault_runner.py           (or double-click play.bat)
```

Files: `vault_runner.py` (game) · `textures.py` (procedural art) · `play.bat` ·
`gamepad_test.bat` · `requirements.txt`. Best score is saved to `highscore.json`.

## 2. The goal

Each level is a randomly generated complex (bigger every level; `levels_to_win` = 8).

1. **Steal loot** for cash and score — coin `$100`, gold bars `$500`, gems `$1,000`.
2. **Find the red KEYCARD** (hidden far from the start).
3. **Reach the vault door** (glowing red steel door on the outer wall), press **E / button 0**.
4. Beat the clock. At 0:00 the **ALARM** sounds: every guard knows where you are and runs faster.

**Bonuses on exit:** time left × $10 · *Ghost bonus* $1,000 (never spotted) · *Full loot bonus* $1,500.

**Guards** patrol with flashlights. They see you in a cone, hear you when you sprint,
and chase along the corridors. If one touches you: **-1 life, lose 30% of cash**, you're
sent back to the start and guards freeze for 3 seconds. 0 lives = BUSTED.

**Stealth tips:** sneaking makes you 55% harder to spot and nearly silent; sprinting
is loud and visible from far away; your flashlight helps you but makes you easier to see;
guards' torch beams show you where they are before you see them.

**Black market** (between levels): Running Shoes, Lithium Torch, Soft Soles, Stopwatch, Spare Life.

## 3. Controls

You can look in all three directions: **X** turn left/right, **Y** look up/down, **Z** jump up / crouch down.
Every action has its own sound.

| Action | Keyboard | Numeric keypad (NumLock ON) | USB gamepad | Arduino UNO pad |
|---|---|---|---|---|
| Move | W A S D / ↑ ↓ | 8 fwd · 5/2 back · 4/6 strafe | Left stick (tilt = speed) / D-pad | Left stick |
| Turn (X) | Mouse, ← → | 7 / 9 | Right stick ↔ | Right stick ↔ |
| Look up/down (Y) | Mouse, PgUp / PgDn | 3 / ÷ | Right stick ↕ | Right stick ↕ |
| Level the view | Home | 1 | Back (6) | D9 button |
| Jump (Z) | Space | | RB (5) / R-stick click | **Right-stick click** (away from door) / D7 |
| Sneak + crouch (Z) | Ctrl / C | . | X (2) | D6 button |
| Sprint | Left Shift | 0 | LB (4) / L-stick click | **Left-stick click** (hold) |
| Open vault door | E | Enter | A (0) | **Right-stick click** (next to door) |
| Flashlight | F | + | B (1) | D4 button |
| Minimap | Tab | − | Y (3) | D5 button |
| Pause | Esc / P | | Start (7) | **Both stick clicks together** / D8 |
| Menus | arrows + Enter | 4 6 8 2 + Enter | Left stick / D-pad + A, Start | Left stick + right click |
| Re-centre Arduino sticks | F9 | | | |
| Help / Fullscreen / Screenshot | F1 / F11 / F12 | | | |

In menus the buttons do different things too. In the shop: torch = up, map = down, sprint/pause = next heist.
In pause: torch/sprint = quit to title, map = help. On the title screen: sprint/torch = change difficulty.

### Arduino UNO two-stick pad (lab-made)

A stock Arduino UNO is **not** seen by Windows as a gamepad. It's a USB serial (COM) port, so the
game reads it directly over serial (the `pyserial` package).

1. **Wiring** (KY-023 style stick modules, +5V→5V, GND→GND):
   Left stick VRx→A0, VRy→A1, SW→D2 · Right stick VRx→A2, VRy→A3, SW→D3.
   Optional buttons (pin to GND): D4 torch, D5 map, D6 sneak, D7 jump, D8 pause, D9 level view.
2. **Flash** `arduino/vault_pad/vault_pad.ino` with the Arduino IDE (board: Arduino Uno).
   If your UNO already runs its own sketch, keep it as long as it prints one line per reading with
   the 4 stick values first and the buttons after (any separator or labels, any common baud rate).
3. **Close the Arduino IDE Serial Monitor**, because only one program can use the COM port at a time.
4. Run `gamepad_test.bat` without touching the sticks. It should say `Arduino: connected on COMx`.
   Push each stick and check the values:
   * left stick up → `move_y` negative · right → `move_x` positive
   * right stick right → `look_x` positive · up → `look_y` negative
   If one is reversed, set its `invert_…` flag in `CONFIG["arduino"]`. If the sticks are swapped, set `swap_sticks: True`.
   If a stick drifts, raise `deadzone` or press F9 in game.
5. Run `play.bat`. The title screen shows the pad status at the bottom.

The sticks are calibrated from their resting position every time the game connects, so keep your
thumbs off them for the first second. The game reconnects by itself if the cable is unplugged.

## 4. Customization menu — pick what you want

Tell me the **numbers** you want (e.g. "1a, 2c, 5b, 7, 9, 12") and I'll build them in.
Items marked ⚙ are already a one-line edit in `CONFIG` at the top of `vault_runner.py`.

### A. Theme / setting (choose one)
1. **Museum heist** (current: marble galleries, brick offices, metal vaults) 
2. Bank vault break-in with laser grids
3. Space station: derelict corridors, airlocks, drones instead of guards
4. Haunted mansion: ghosts, candles, stealing artifacts
5. Cyberpunk data-heist: neon, holo-signs, security robots
6. Prison escape: cells, wardens, searchlights
7. Ancient tomb raider: sandstone, traps, mummies
8. Zombie-apocalypse supply run: scavenge, avoid the horde
9. Casino robbery: slot-machine glow, tables, cameras
10. Underwater research lab: flooded rooms, oxygen meter
11. Ninja / feudal castle at night
12. Supermarket after dark: shopping-spree scoring (grab items, beat checkout)

### B. Task / objective (choose one or mix)
1. Keycard → vault door (current)
2. Deliver packages to numbered drop points before time runs out (courier/taxi style)
3. Collect X items of a set (e.g. all 5 artifacts) and exit
4. Hack terminals (hold E near each for N seconds) then escape
5. Rescue hostages / find survivors and lead them out
6. Defuse bombs before the countdown ends
7. Survive N minutes while stealing as much as possible (endless score-attack)
8. Assassinate a target guard without being seen
9. Photograph objects with an in-game camera for points
10. Plant devices on marked spots
11. Escort a slow NPC to the exit
12. Boss level: steal the "crown jewel" that triggers a massive chase

### C. Money & scoring
1. ⚙ Loot values, time bonus, stealth bonus, full-loot bonus, death penalty
2. Combo multiplier for grabbing loot in quick succession
3. Loot weight — heavier bags slow you down
4. Fence/sell screen: convert loot to cash at rates that vary per level
5. Interest / debt system: you owe a loan that grows each level
6. Daily contracts (random side-goals with bonus pay)
7. Online-style leaderboard (local top-10 table with names)
8. Star rating per level (S/A/B/C)
9. Achievements list (Ghost, Speedrun, Hoarder, Pacifist…)
10. Random rare "golden" loot with huge value and a bigger alarm risk
11. Insurance: pay to keep your cash when caught
12. Stock-market-style loot prices that change every level

### D. Player abilities & gadgets
1. ⚙ Walk / sprint / sneak speed, stamina size, drain and regen
2. Crouch that lowers the camera and lets you hide in vents
3. Lockpick mini-game to open extra locked side rooms with bigger loot
4. Smoke bombs, flash-bangs, noise-makers (throw to distract guards)
5. Night-vision goggles (battery limited, green tint)
6. Grappling hook / jump over low obstacles
7. EMP to disable cameras and lamps
8. Cloak / invisibility with cooldown
9. Radar pulse (ping shows guards through walls for 3 s)
10. Stun gun / tranquilizer darts
11. Dash / slide with cooldown
12. Flashlight battery that must be recharged by pickups

### E. Enemies & AI
1. ⚙ Guard count, speed, vision range, torch on/off, alarm speed boost
2. Guard types: sleepy, jumpy, sniper, dog that tracks by scent
3. Security cameras with sweeping cones
4. Laser tripwires and pressure plates
5. Guards radio each other when they spot you
6. Guards that investigate noises and open/close doors
7. Patrol routes you can learn (fixed instead of random)
8. Drones that fly over walls
9. Boss chaser that never stops (Nemesis style)
10. Guards that wake up / go to shift change at set times
11. Friendly NPC informants that sell tips

### F. Levels & world
1. ⚙ Level count, timer per level, size growth
2. Fixed hand-designed levels loaded from text files
3. Multi-floor buildings with stairs and elevators
4. Doors you open/close (and that guards must open too)
5. Outdoor courtyard with skybox, moon and fog
6. Secret rooms / hidden switches / vents
7. Random events (power outage, fire drill, lockdown)
8. Day/night or weather (rain streaks, thunder flashes)
9. Moving platforms, conveyor belts, hazards
10. Bigger maps with a "you are here" full-screen map item
11. Daily seed: everyone plays the same random level
12. Level editor (paint a map, save, play)

### G. Graphics / "realism" upgrades
1. ⚙ Render resolution, FOV, film grain, vignette, haze, ambient light, lamp/torch strength, head-bob, smooth scaling
2. Swap procedural textures for your own image files (photo brick, real marble…)
3. Normal-mapped walls with per-pixel bump lighting from the flashlight
4. Real-time shadows from the torch (occlusion by pillars)
5. Bloom and lens flare on lamps
6. Animated guard sprites (walk cycle, 8-direction sprites)
7. Reflections on the polished tile floors
8. Volumetric light shafts / dust particles
9. Screen-space effects: motion blur when sprinting, damage blur
10. Higher-quality mode with a 3D engine port (Ursina / Panda3D / Godot)
11. Color-grading presets (noir, cyber, warm film, VHS)
12. Skybox windows showing a city

### H. Audio
1. ⚙ Sound on/off (all sounds are synthesised in code)
2. Real music tracks (stealth theme → chase theme cross-fade)
3. Directional 3D audio for footsteps and guard voices
4. Voice lines ("Who's there?", "Stop!")
5. Ambient soundscapes per room type
6. Heartbeat that speeds up when guards are close

### I. Controls & accessibility
1. ⚙ Mouse sensitivity, turn speed, gamepad deadzone/look speed/buttons/axes
2. Rebindable keys screen in-game
3. Rumble / vibration on gamepad (if your pad supports it)
4. Aim-assist / auto-open doors option
5. Colour-blind palettes and bigger HUD text
6. Toggle-sneak and toggle-sprint options
7. Second-player local co-op (keyboard + pad, split-screen)
8. Touch / on-screen controls

### J. Meta / progression
1. ⚙ Difficulty presets (Easy / Normal / Hard) and shop upgrade list & prices
2. Save & continue campaign
3. Skill tree instead of the shop
4. Unlockable characters with different perks
5. Cosmetic outfits and flashlight colours
6. New Game+ with modifiers (no torch, double guards, one life)
7. Daily / weekly challenge mode
8. Story mode with briefing screens between levels
9. Practice mode with no guards to explore levels
10. Speedrun timer and ghost replays

### K. Quality-of-life & packaging
1. Windows `.exe` build with PyInstaller (no Python needed)
2. Settings menu (resolution, volume, controls) instead of editing code
3. Pause menu with restart-level
4. Tutorial level
5. Performance mode (lower resolution auto-adjust to keep 60 fps)

---

## 5. Quick tweaks you can do right now (no coding skill needed)

Open `vault_runner.py`, look at `CONFIG` at the top:

* Game too hard? Set `"guard_vision": 6.0`, `"levels_to_win": 5`, or pick **Easy** on the title screen.
* Too dark? Raise `"ambient_light"` (try `0.12`) or `"torch_strength"`.
* Too slow on your PC? Lower `"render_size"` to `(400, 225)` or `(320, 180)`.
* Want it prettier? `"render_size": (640, 360)` (needs a fast CPU).
* Crunchy retro look? `"smooth_scaling": False`.
* Bigger payouts? Edit `"loot_values"`.
* Pad turns the wrong way? `"invert_look_x": True`.

## 6. Troubleshooting

* **Choppy / slow:** lower `render_size`. Rendering is pure CPU (numpy).
* **Keypad does nothing:** turn Num Lock ON.
* **Pad not detected:** plug it in before starting, run `gamepad_test.bat` to confirm Windows sees it.
* **View drifts on its own with the pad:** raise `"deadzone"` (e.g. `0.25`).
* **No sound:** the game silently runs without audio if no output device is available.
