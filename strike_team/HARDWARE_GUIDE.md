# STRIKE TEAM - Hardware Guide (wireless Arduino pads)

You build **two identical pads**, one per player. Each pad = Arduino UNO + 2 joysticks + 1 Bluetooth
module + a battery. The laptop talks to both pads over Bluetooth; a USB cable also works as a backup.

```
   [ joystick L ]   [ joystick R ]          ))) Bluetooth )))         LAPTOP
          \             /                                        launcher.py (Python)
         [ Arduino UNO ] ---- [ HC-05 ]   ------------------->     |  UDP
              |                                                  Godot 3D game
          [ battery ]
```

---

## 1. Know your parts (what they look like)

| Part | What it looks like | How to recognise it |
|---|---|---|
| **Arduino UNO** | Blue board, about the size of a credit card. USB-B (square printer-style) socket + a round black barrel power jack on one short edge. | Row of headers labelled `A0 ... A5` on one side, `0 ... 13` on the other, `5V`, `3.3V`, `GND`, `VIN` near the power jack. |
| **Joystick module (KY-023)** | A small PCB with a PlayStation-style thumb stick on top. 5 pins on one edge. | Pins labelled `GND`, `+5V`, `VRx`, `VRy`, `SW`. Pressing the stick down clicks (that's `SW`). |
| **HC-05** | A small blue board (about 4 x 1.5 cm) with a green/blue module soldered on top, often a printed antenna zig-zag at one end. **6 pins**. Usually has a tiny push button. | Pins: `EN` (or `KEY`), `VCC`, `GND`, `TXD`, `RXD`, `STATE`. Red LED blinks fast when powered and not connected. |
| **HC-06** | Looks almost the same but has **4 pins** and usually no button. | Pins: `VCC`, `GND`, `TXD`, `RXD`. It can only be a slave, which is exactly what we need. |
| **Resistors** | Tiny beige/blue cylinders with colour bands. | **1 kΩ** = brown-black-red, **2 kΩ** = red-black-red (or use two 1 kΩ in series as 2 kΩ). |
| **Jumper wires** | Coloured wires with pins (male) or sockets (female) on the ends. | You need **female-to-male** to go from module pins to the UNO headers / breadboard. |
| **Breadboard** | White plastic board full of holes. | The 5 holes in a short row are connected; the long `+`/`-` rails along the sides are connected. |

**Ask in class:** "Is our module an HC-05 or HC-06?" (count the pins: 6 = HC-05, 4 = HC-06) and
"Can we keep a 9 V battery clip or power bank for each UNO?"

---

## 2. Wiring (do this twice)

```
 LEFT JOYSTICK          ARDUINO UNO              RIGHT JOYSTICK
   GND  ------------->  GND  <-------------------  GND
   +5V  ------------->  5V   <-------------------  +5V
   VRx  ------------->  A0         A2  <---------  VRx
   VRy  ------------->  A1         A3  <---------  VRy
   SW   ------------->  D2         D3  <---------  SW

 HC-05 / HC-06
   VCC  ------------->  5V
   GND  ------------->  GND
   TXD  ------------->  D10        (module talks -> Arduino listens)
   RXD  <--+--[2 kΩ]--  GND
           |
           +--[1 kΩ]--  D9         (Arduino talks -> module listens, through the divider)
```

**Why the resistors?** The UNO's pins output **5 V**, but the module's `RXD` pin is **3.3 V** logic.
The 1 kΩ + 2 kΩ voltage divider gives 5 V x 2/3 ≈ 3.3 V. Skip it and the module may work for a
while... then die. (`TXD -> D10` needs nothing: 3.3 V is still read as HIGH by the UNO.)

Only one `5V` and two `GND` pins on the UNO? Use the breadboard's `+`/`-` rails: UNO `5V` -> `+` rail,
UNO `GND` -> `-` rail, then every `VCC`/`+5V` goes to `+` and every `GND` goes to `-`.

---

## 3. Configure each Bluetooth module (from BT-Slave--Config.pdf)

1. Open `arduino/bt_setup/bt_setup.ino` in the Arduino IDE, choose **Board: Arduino Uno** and the COM
   port, and upload it.
2. **HC-05:** unplug the module's `VCC` wire, **hold its button**, plug `VCC` back in and release.
   The LED should now blink **slowly** (once every ~2 s) = AT/config mode.
3. Open the Serial Monitor: **38400 baud**, **Both NL & CR**. Type, one at a time:

| Command | Expected reply | Meaning |
|---|---|---|
| `AT` | `OK` | module is listening |
| `AT+ROLE=0` | `OK` | **slave** (the laptop connects to it) |
| `AT+INQM=0,5,9` | `OK` | discoverable |
| `AT+NAME=STRIKE-P1` | `OK` | name shown in Windows (`STRIKE-P2` on the second pad) |
| `AT+PSWD="1234"` | `OK` | pairing PIN (try `AT+PSWD=1234` if it says ERROR) |
| `AT+UART=38400,0,0` | `OK` | *optional* faster data mode - then set `BT_BAUD = 38400` in fight_pad.ino |
| `AT+ADDR?` | `+ADDR:0021:07:001EE9` | **write this address down** (one per pad) |

4. Power-cycle the module (unplug/replug `VCC`, no button) -> fast blinking = normal mode.

**HC-06 instead?** No button needed. Set `BT_BAUD = 9600` in bt_setup.ino, Serial Monitor at
**9600, No line ending**, then `AT` -> `OK`, `AT+NAMESTRIKE-P1`, `AT+PIN1234`. It's always a slave.

---

## 4. Upload the pad sketch

Open `arduino/fight_pad/fight_pad.ino`, upload it to both UNOs. If you changed `AT+UART`, change
`BT_BAUD` at the top to match. Open the Serial Monitor at **115200** - you should see lines like:

```
J,512,498,507,520,0,0
```

Move the sticks -> the numbers change (0 ... 1023). Click a stick -> the last numbers become 1
(the on-board LED "L" lights while the right stick is clicked).

---

## 5. Pair with the laptop

1. Windows **Settings > Bluetooth & devices > Add device > Bluetooth**. Pick `STRIKE-P1` (or `HC-05`),
   PIN `1234` (or `0000`).
2. Repeat for `STRIKE-P2`.
3. **Device Manager > Ports (COM & LPT)**: each pad adds **two** "Standard Serial over Bluetooth link"
   ports. Only the **Outgoing** one carries data (in *More Bluetooth settings > COM Ports* it says
   `Outgoing  STRIKE-P1 'Dev B'`). Note it, e.g. `COM12`.
4. Run **`pad_check.bat`**. The launcher opens the outgoing ports by itself (incoming ones are
   skipped); after a few seconds each pad shows **live** and its stick dot moves. When a pad
   connects, the HC-05 LED changes from fast blinking to **two quick blinks every ~2 s** (or solid).

**Pin the pads to players** (optional, so blue is always blue): edit `config.json`:

```json
"p1": "0021:07:001EE9",      <- the AT+ADDR? of the blue pad (or "COM12")
"p2": "0021:07:00ABCD",
```

Setting these also stops the launcher from trying your other paired Bluetooth devices
(this laptop already has a few phones/headsets paired - with "auto" it tries those too).

---

## 6. Controller check screen (`pad_check.bat`)

| Key | Does |
|---|---|
| `1` `2` `3` `4` | flip P1's left X, left Y, right X, right Y (if up moves the dot down, etc.) |
| `5` `6` `7` `8` | same for P2 |
| `S` | swap P1 / P2 |
| `R` | recalibrate (leave the sticks centred and press) |
| `F1` / `F2` | simulated pad for P1 / P2 (keyboard: WASD + TFGH + C/V, IJKL + numpad + N/M) |

The game calibrates the stick centre on its own from the first readings - **don't touch the
sticks for the first second after the pad connects.**

---

## 7. Troubleshooting

| Symptom | Fix |
|---|---|
| `AT` gives nothing | HC-05 not in AT mode (LED must blink slowly) / wrong baud / TX-RX swapped (module **TXD -> D10**). |
| `AT` gives garbage | Serial Monitor baud doesn't match `BT_BAUD` in bt_setup.ino. |
| Paired but the launcher says "connecting..." forever | Wrong COM port (incoming one) - check the *Outgoing* port; pad off / out of battery; `BT_BAUD` in fight_pad doesn't match the module's `AT+UART`. |
| Data in the USB Serial Monitor but not over Bluetooth | `BT_BAUD` mismatch, or the divider is wired wrong (D9 -> 1 kΩ -> RXD, RXD -> 2 kΩ -> GND). |
| Sticks drift / a direction is stuck | Press `R` on the check screen with sticks centred; raise `"deadzone"` in config.json to 0.18. |
| Stick moves the wrong way | Flip it with keys `1`-`8` on the check screen (saved automatically). |
| Laggy | `AT+UART=38400,0,0` + `BT_BAUD = 38400` in fight_pad.ino (~60 updates/s instead of ~30). |
| UNO resets / acts weird on battery | 9 V "smoke alarm" batteries die fast - use a USB power bank in the UNO's USB socket. |

---

## Shopping / class checklist

- [ ] 2 x Arduino UNO (+ USB-B cables for uploading)
- [ ] 2 x HC-05 (or HC-06)
- [ ] 4 x KY-023 joystick modules
- [ ] 2 x 1 kΩ + 2 x 2 kΩ resistors
- [ ] 2 x small breadboards, ~30 female-to-male + male-to-male jumpers
- [ ] 2 x power banks (or 9 V battery + barrel-jack clip)
- [ ] Write down: each module's `AT+ADDR?` and its Outgoing COM port
