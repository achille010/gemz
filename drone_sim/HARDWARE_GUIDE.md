# DRONE SIM - Hardware Guide (wireless Arduino pads)

Build the pad from scratch: parts, wiring, Bluetooth setup, pairing, and the controller check.
Follow it once per pad. One pad is enough to fly; a second one is the optional co-pilot.

What you end up with: a two-stick pad that talks to the laptop over Bluetooth (or a plain USB
cable), that `launcher.py` finds by itself and streams to the game.

> Already built one for `strike_team`? **It just works here** - same sketch format, same wiring.
> Flash `arduino/drone_pad/drone_pad.ino` (or keep the strike_team sketch) and skip to step 5.

---

## 1. Know your parts (what they look like)

| Part | How to recognise it | How many |
|---|---|---|
| **Arduino UNO** | Big blue board, USB-B socket (the square printer-style plug) | 1 per pad |
| **KY-023 joystick module** | Small blue board, black thumbstick, 5 pins: GND VCC VRx VRy SW | 2 per pad |
| **HC-05** | Blue daughterboard on a backplate, **6 pins**, small button on the end | 1 per pad |
| **HC-06** | Same look but **4 pins** and **no button** (always a slave - simpler, fine here) | alternative |
| **Resistors** | 1k and 2k (or 2 x 1k in series) for the voltage divider | 2 per pad |
| Jumper wires | Male-female for the modules | ~12 per pad |

The HC-05's **RXD pin is 3.3 V logic**. The UNO sends 5 V. That is what the divider is for -
skipping it is the single most common way these modules die.

---

## 2. Wiring (do this twice if you build two pads)

**Joysticks** - power both from the same 5V / GND rails:

| Left stick | UNO | Right stick | UNO |
|---|---|---|---|
| GND | GND | GND | GND |
| +5V | 5V | +5V | 5V |
| VRx | A0 | VRx | A2 |
| VRy | A1 | VRy | A3 |
| SW | D2 | SW | D3 |

**Bluetooth module:**

| Module | UNO |
|---|---|
| VCC | 5V |
| GND | GND |
| TXD | **D10** (module talks, Arduino listens) |
| RXD | **D9 through the divider** |

The divider, built on the breadboard:

```
    D9 ----[ 1k ]----+----[ 2k ]---- GND
                     |
                 module RXD        (~3.3 V)
```

Double-check before powering up: **VCC and GND the right way round**, and TXD on D10 (not D9).

---

## 3. Configure each Bluetooth module

Use `arduino/bt_setup/bt_setup.ino` - it just passes the Serial Monitor through to the module
(`arduino/bt_slave_config/bt_slave_config.ino` is the same idea from the lab handout, and
`ard.md` is the bare minimum version).

### HC-05 (6 pins, has the button)

1. Upload `bt_setup` with `BT_BAUD = 38400` (the HC-05 **AT-mode** speed).
2. Unplug the module's VCC, **hold its button**, plug VCC back, release.
   The LED should now blink **slowly** (~once every 2 s) = AT mode.
3. Serial Monitor: **38400 baud**, line ending **"Both NL & CR"**. Type:

   | Command | Reply | Why |
   |---|---|---|
   | `AT` | `OK` | it's listening |
   | `AT+ROLE=0` | `OK` | slave |
   | `AT+INQM=0,5,9` | `OK` | discoverable |
   | `AT+NAME=DRONE-P1` | `OK` | name it (`DRONE-P2` on the second pad) |
   | `AT+PSWD="1234"` | `OK` | PIN (some firmware wants `AT+PSWD=1234`) |
   | `AT+UART=38400,0,0` | `OK` | **recommended**: ~60 updates/s instead of ~30 |
   | `AT+ADDR?` | `+ADDR:0021:07:001EE9` | **write this down** - one per pad |

4. Power cycle **without** holding the button -> fast blinking = normal mode.
5. If you set 38400, open `arduino/drone_pad/drone_pad.ino` and set `BT_BAUD = 38400` too.
   A flight pad really wants this: at 9600 the controls feel laggy.

### HC-06 (4 pins, no button)

Always a slave, and in AT mode whenever nothing is connected.

1. Upload `bt_setup` with `BT_BAUD = 9600`. Serial Monitor: **9600**, **"No line ending"**.
2. Type `AT` -> `OK`, then `AT+NAMEDRONE-P1` -> `OKsetname`, `AT+PIN1234` -> `OKsetPIN`.
   (No `=`, no line ending, on most HC-06 firmware.)
3. Leave `BT_BAUD = 9600` in `drone_pad.ino`.

---

## 4. Upload the pad sketch

1. Open `arduino/drone_pad/drone_pad.ino`.
2. Board: **Arduino Uno**. Port: the UNO's COM port.
3. Check `BT_BAUD` matches what the module actually runs at (step 3).
4. Upload, then open the Serial Monitor at **115200**. You should see a flood of
   `J,512,498,505,501,0,0`. Push a stick - the numbers move. Click it - the last two flip to 1.
   **Close the Serial Monitor afterwards**: only one program can hold a COM port.

If the numbers never move, the stick's VRx/VRy are on the wrong analog pins. If a click is
stuck at 1, SW is not on D2 / D3 or the `INPUT_PULLUP` pin is wired to 5V instead of GND.

---

## 5. Pair with the laptop

1. Power the pad. The module's LED should blink fast (not connected yet).
2. Windows: **Settings > Bluetooth & devices > Add device > Bluetooth**.
3. Pick **DRONE-P1**, PIN **1234** (try **0000** if it refuses).
4. Windows creates **two** "Standard Serial over Bluetooth link" COM ports for it.
   **Only the outgoing one carries data** - you don't need to work out which: the launcher
   opens every candidate port and keeps the one that talks.
5. Run **`pad_check.bat`**. Within a few seconds the port list shows your port with `= P1`
   next to it, and the dots move with the sticks.

To pin a pad to a player, put its address or port in `config.json`:

```json
{ "p1": "0021:07:001EE9", "p2": "auto" }
```

With `p1`/`p2` set, the launcher only dials those modules instead of every device you ever
paired - noticeably faster to start, and it stops a paired phone or headset being opened.

---

## 6. Controller check screen (`pad_check.bat`)

| Key | What it does |
|---|---|
| **`O`** / **`P`** | **Orientation wizard** for pad 1 / pad 2 - 4 prompts, then it knows which raw axis is which direction. Fixes rotated stick modules properly |
| `1`-`4` | Flip pad 1 left X / left Y / right X / right Y |
| `5`-`8` | Same for pad 2 |
| `S` | Swap pilot and co-pilot |
| `R` | Recalibrate centres (hands off the sticks) |
| `C` | Co-pilot clicks on / off |
| `F1` / `F2` | Simulated pad 1 / 2 from the keyboard, to test with no hardware |
| `Esc` | Back |

Everything here is saved to `config.json` straight away.

The orientation wizard is the one to use first: flipping axes by hand only helps if the stick
is mounted square. If forward on a stick comes out as a diagonal, the wizard sorts it out.

---

## 7. Troubleshooting

| Symptom | Cause / fix |
|---|---|
| No COM ports listed | Pad not powered, not paired, or the driver is missing. Device Manager > Ports (COM & LPT) |
| Port listed, status "can't open" | Something else holds it: the Arduino IDE Serial Monitor, another copy of the launcher, or `gamepad_test.bat` |
| Status stuck "connecting..." | Bluetooth port, module off or out of range. Windows retries for a few seconds; power cycle the pad |
| "semaphore timeout" | Stale pairing - remove the device in Windows Bluetooth settings and pair again |
| Dots jump around / garbage | `BT_BAUD` in the sketch ≠ the module's `AT+UART?` speed |
| Dots off-centre at rest | Press `R` with your thumbs off the sticks |
| Controls feel laggy over Bluetooth | 9600 baud = ~30 updates/s. Set the module **and** the sketch to 38400 |
| Module got hot / stopped working | RXD was driven at 5 V without the divider |
| Launcher runs, game window never appears | Python can't find `pygame`/`numpy` - run `play.bat` once, it installs them |

---

## Shopping / class checklist

Per pad: 1 x Arduino UNO, 2 x KY-023 joystick module, 1 x HC-05 (or HC-06), 1 x 1k resistor,
1 x 2k resistor, 1 small breadboard, ~12 male-female jumpers, 1 USB-B cable.
Optional: a 9 V battery + barrel jack, or a USB power bank, to cut the pad loose.

Software on the laptop: Python 3.10+, then `play.bat` installs `pygame-ce`, `numpy` and
`pyserial` on its own. No Godot, no 3D assets - the game draws itself in software.
