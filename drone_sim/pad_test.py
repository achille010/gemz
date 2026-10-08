"""Pad wiring test - checks every joystick X, Y and click one by one and says what is wrong.

    python pad_test.py            (finds the pad on Bluetooth or USB by itself)
    python pad_test.py COM15      (or name the port)

Close the game, the launcher and the Arduino Serial Monitor first: only one program can
hold the port.
"""
import sys
import threading
import time

import serial
from serial.tools import list_ports

from pads import parse_pad_line

NAMES = ["Left X (A0)", "Left Y (A1)", "Right X (A2)", "Right Y (A3)", "Left click (D2)", "Right click (D3)"]
latest = {"v": None, "good": 0, "bad": 0, "t": 0.0}


def reader(port):
    try:   # USB sketch speed is 115200; Bluetooth ports ignore the number
        s = serial.Serial(port, 115200, timeout=0.3)
    except Exception:
        return
    buf = b""
    try:
        while True:
            buf += s.read(max(1, s.in_waiting))
            *lines, buf = buf.split(b"\n")
            for ln in lines:
                v = parse_pad_line(ln.decode("ascii", "ignore"))
                if v:
                    latest.update(v=v, t=time.time(), good=latest["good"] + 1)
                elif ln.strip():
                    latest["bad"] += 1
    except Exception:
        pass


def find_port():
    if len(sys.argv) > 1:
        return [sys.argv[1]]
    return [p.device for p in list_ports.comports()
            if "000000000000" not in (p.hwid or "")]   # skip incoming Bluetooth ports


def main():
    print("Looking for the pad... (pad powered, game / Serial Monitor closed)")
    for port in find_port():
        threading.Thread(target=reader, args=(port,), daemon=True).start()
    t0 = time.time()
    while latest["v"] is None:
        if time.time() - t0 > 20:
            print("\nNO valid data from any port.\n - Pad powered? HC-05 LED blinking?\n"
                  " - Re-upload the pad sketch (it must end each line with a checksum).\n"
                  " - USB: is the Serial Monitor still open?")
            return
        time.sleep(0.2)
    print("Pad found. HANDS OFF the sticks for 2 seconds...")
    time.sleep(2)
    rest = list(latest["v"])
    problems = []
    for i in range(4):
        if rest[i] < 300 or rest[i] > 723:
            problems.append(f"{NAMES[i]} rests at {rest[i]:.0f} (should be ~512): loose wire or bad stick")
    for i in (4, 5):
        if rest[i]:
            problems.append(f"{NAMES[i]} reads PRESSED while untouched: SW wire on the wrong pin or shorted to GND")

    steps = [("Push the LEFT stick fully RIGHT and hold", 0), ("Push the LEFT stick fully UP (forward) and hold", 1),
             ("Push the RIGHT stick fully RIGHT and hold", 2), ("Push the RIGHT stick fully UP and hold", 3),
             ("Press the LEFT stick down (click) and hold", 4), ("Press the RIGHT stick down (click) and hold", 5)]
    for text, want in steps:
        print(f"\n>>> {text}  (5 s)")
        best, t0 = None, time.time()
        while time.time() - t0 < 5:
            v = latest["v"]
            moved = [abs(v[i] - rest[i]) / (1 if i > 3 else 512) for i in range(6)]
            top = max(range(6), key=lambda i: moved[i])
            if moved[top] > 0.5:
                best = top
                time.sleep(0.6)
                break
            time.sleep(0.05)
        if best is None:
            print(f"    NOTHING changed -> {NAMES[want]} is dead: check its wire")
            problems.append(f"{NAMES[want]}: no reaction")
        elif best != want:
            print(f"    It moved {NAMES[best]} instead -> wires swapped / stick rotated")
            problems.append(f"'{text}' moved {NAMES[best]} instead of {NAMES[want]}")
        else:
            print(f"    OK ({NAMES[want]})")
        print("    release...")
        while time.time() - t0 < 12 and max(abs(latest["v"][i] - rest[i]) / (1 if i > 3 else 512) for i in range(6)) > 0.3:
            time.sleep(0.05)

    total = latest["good"] + latest["bad"]
    loss = 100 * latest["bad"] / total if total else 0
    print(f"\nRadio: {latest['good']} good lines, {latest['bad']} damaged ({loss:.1f}% dropped)")
    if loss > 10:
        problems.append("many damaged lines: check BT_BAUD matches the module, use the RXD voltage divider, keep the pad close")
    print("\n" + ("ALL GOOD - every stick and click works." if not problems else "PROBLEMS:\n - " + "\n - ".join(problems)))
    print("(Swapped / rotated sticks are fixed in software: pad_check.bat -> press O.)")


if __name__ == "__main__":
    main()
