# STRIKE TEAM - Wireless Pad Guide

Your pad: **Arduino UNO + 2 joysticks + HC-05 Bluetooth module** (address `0022:09:010771`,
shows in Windows as **BT@yocha**, port **COM15**). The PC is the Bluetooth **master**, the
HC-05 is the **slave**.

---

## 1. Every time you play

1. **Power the pad** (USB power bank or external supply on the UNO).
   The HC-05 LED blinks **fast** = waiting for the PC. That's correct.
2. **Close** anything that could hold COM15: the Arduino Serial Monitor, Bluetooth terminal apps.
   The module accepts **one** connection only.
3. **Leave both sticks alone for 2 seconds** after the game connects. It measures the stick centre
   from the first readings. Touching them then = the character drifts.
4. Double-click **`strike_team\play.bat`** and pick:
   - **Solo Operation (1 pad)** = you alone, full screen (this is your pad's mode)
   - Campaign / Random Operation = 2-player split screen (needs a second pad)
5. When the game connects, the HC-05 LED changes from fast blinking to **2 quick blinks, pause**.

**First time, or after rewiring / remounting a joystick:** run **`pad_check.bat`**:
1. P1 must say **Bluetooth COM15 - ready**.
2. Press **`O`** (orient Player 1) and follow the 4 prompts: push the left stick **forward**, then
   **right**, then the right stick **forward**, then **right**, holding each at the edge for half a
   second and letting go in between. It saves automatically.
3. Check the dots: pushing forward must move the dot **up**, pushing right moves it **right**.

This fixes the **"pulls to the left / can't walk forward"** problem: it happens when a joystick
module is mounted rotated, so its X and Y are swapped. The wizard learns your real mounting.

---

## 2. Controls (Arduino pad)

| You do | What happens |
|---|---|
| **Left stick** | Walk forward / back / strafe left / right |
| **Right stick** | Look / turn (up-down is limited so you can't lose the view) |
| **Click the RIGHT stick** (hold = full auto) | **Shoot** |
| **Click the LEFT stick** (tap) | **Crouch** on / off (steadier aim, harder to hit, slower) |
| **Hold the LEFT click + hold the RIGHT click** | **Aim down the scope** while firing |
| Walk over an **ammo crate** (white on the radar) | +4 magazines (automatic) |
| Walk over a **medkit** (pink cross) | Pick it up (automatic) |
| Get downed (0 HP) **with** a medkit | **Self-revive** after a few seconds (solo, automatic) |
| Reload | **Automatic** when the magazine is empty |

Not on the pad (only 2 buttons): **sprint, grenades, manual medkit**. Use the keyboard for
those if you need them: `Shift` sprint, `G` grenade, `H` medkit. `Esc` aborts the mission.

### How to shoot properly (important)
These joysticks also **click when you push them hard to the edge**. To stop accidental shots,
the game **only starts firing if the right stick is near the centre when you click it**:

1. **Aim first** with the right stick.
2. **Let the stick come back toward the centre**, then **press straight down** to fire.
3. Once firing, you can **keep holding and keep turning**; it keeps shooting until you release.

The same rule applies to crouch: tap the left stick while it's near the centre.
Pushing a stick hard while turning/walking will **not** shoot or crouch any more.

---

## 3. What you see on screen

| Where | What |
|---|---|
| Top-left | **Objective** + timer |
| Top-centre | **Compass**: yellow diamond = objective direction |
| Top-right | Kill feed |
| Bottom-left | **Radar** (turns with you): **red dots = enemies**, yellow = objective, white = ammo, pink = medkit. Bars under it: **green = health**, **blue = magazines left** |
| Bottom-right | Ammo in the magazine / total, magazine pips, **your 3 lives**, medkit icon |
| Centre | Crosshair (white X = hit, red X = kill), red arcs = direction you're being shot from |

---

## 4. Mission flow

1. Read the briefing, select **START MISSION**.
2. Follow the **yellow marker** (compass + radar + on-screen diamond).
3. Do the task (defuse, hack, plant charges, grab intel, rescue, kill the commander, hold the zone,
   collect cases). Killing everyone never wins.
4. Then go to the **green extraction zone** and stand inside it.
5. **3 lives.** Downed = 60 s bleed-out; a carried medkit revives you, otherwise you lose a life
   and respawn. No lives left = mission failed.

---

## 5. If something is wrong

| Problem | Fix |
|---|---|
| Shoots when you didn't press | Make sure you're on the latest launcher (has the click guard). Still happening? **Lower** `"click_guard"` in `config.json` (e.g. `0.4`) so the stick must be even more centred to start firing |
| Can't shoot while turning | Expected: centre the stick a bit, then click. To turn the guard off, set `"click_guard": 1.5` in `config.json` |
| Character walks/turns by itself | Restart the mission without touching the sticks for 2 s, or press `R` on the pad-check screen with sticks centred. Still drifting: raise `"deadzone"` to `0.18` |
| Pulls to one side / can't go forward | Stick module is mounted rotated: `pad_check.bat` -> press **`O`** and do the 4 prompts |
| Up/down or left/right is reversed | `pad_check.bat`: keys `1`/`2` flip the left stick X/Y, `3`/`4` flip the right stick X/Y (saved) |
| P1 shows "no pad" | Pad powered? LED fast blinking? Nothing else using COM15? Wait ~5 s - Windows takes a moment to open the Bluetooth link |
| "semaphore timeout" / "network location cannot be reached" | Module is off, out of range, connected to another device, or the pairing went stale: remove **BT@yocha** in Windows Bluetooth settings and pair again (PIN `1234` or `0000`) |
| Garbage / jumping dots | Speed mismatch: `BT_BAUD` in `arduino/fight_pad/fight_pad.ino` must equal the module's `AT+UART?` (yours: **9600**, working) |

---

## 6. Wiring reference

| From | To |
|---|---|
| Left stick VRx / VRy / SW | A0 / A1 / D2 |
| Right stick VRx / VRy / SW | A2 / A3 / D3 |
| Both sticks +5V / GND | 5V / GND |
| HC-05 VCC / GND | 5V / GND |
| HC-05 TXD | D10 |
| HC-05 RXD | D9 (safer through a 1 kΩ + 2 kΩ divider) |

Sketch on the UNO: **`arduino/fight_pad/fight_pad.ino`** (BT_BAUD = 9600).
Config-mode sketch (only for AT commands): `arduino/bt_slave_config/bt_slave_config.ino`.
