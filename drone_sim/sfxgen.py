"""Sounds for the DRONE SIM launcher, and an exporter for the game's built-in sounds.

The game itself synthesises its sounds at start-up (see Sfx in drone_sim.py) and lets any
file in  sounds/<name>.wav  take over. This module covers the two gaps around that:

    python sfxgen.py              write the launcher's menu sounds to sounds/launcher/
    python sfxgen.py --export     render the GAME's built-in sounds to sounds/gen/*.wav

The export is the handy one: those .wav files are exactly what you hear in game, so you can
open one in an editor, change it, and copy it up into  sounds/  to override it for real.
Nothing here ever writes into sounds/ directly, so it can't clobber your own recordings.

Pure Python (no numpy) for the launcher sounds, so the launcher starts even in a bare install.
"""
import math
import os
import random
import struct
import sys
import wave

SR = 22050
# the launcher's own sounds: menu movement, select, back, refused, pad found, mission start
NAMES = ["nav", "confirm", "back", "deny", "pad", "start", "star"]


def _tone(freqs, dur, amp=0.45, decay=6.0):
    """A short note, or a run of notes when several frequencies are given."""
    out = []
    n = int(SR * dur)
    seg = dur / len(freqs)
    for i in range(n):
        t = i / SR
        f = freqs[min(len(freqs) - 1, int(i / n * len(freqs)))]
        out.append(amp * math.sin(2 * math.pi * f * t) * math.exp(-(t % seg) * decay))
    return out


def _noise(dur, decay, lp=0.5, amp=1.0, seed=1):
    rnd = random.Random(seed)
    out, y = [], 0.0
    for i in range(int(SR * dur)):
        y += lp * (rnd.uniform(-1, 1) - y)
        out.append(y * amp * math.exp(-i / SR * decay))
    return out


def _mix(*tracks):
    n = max(len(t) for t in tracks)
    return [sum(t[i] for t in tracks if i < len(t)) for i in range(n)]


def make(name):
    if name == "nav":
        return _tone([900], 0.035, 0.30, 40)
    if name == "confirm":
        return _tone([660, 990], 0.19, 0.42, 9)
    if name == "back":
        return _tone([700, 440], 0.19, 0.38, 9)
    if name == "deny":
        return _tone([160], 0.25, 0.5, 7)
    if name == "pad":
        return _tone([880, 1320], 0.18, 0.40, 10)
    if name == "start":
        # spin-up: a rising whine with rotor noise under it
        whine = [0.4 * math.sin(2 * math.pi * (220 + 320 * (i / (SR * 0.55))) * i / SR)
                 for i in range(int(SR * 0.55))]
        return _mix(whine, _noise(0.55, 3.0, 0.25, 0.35, 4))
    if name == "star":
        return _tone([1568, 2349], 0.4, 0.33, 5)
    return []


def write(path, samples):
    peak = max(1e-6, max(abs(s) for s in samples))
    k = 0.9 / peak if peak > 0.9 else 1.0
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(b"".join(struct.pack("<h", int(max(-1, min(1, s * k)) * 32767)) for s in samples))


def ensure(sound_dir):
    """Write any missing launcher sound into <sound_dir>/launcher/ and return that folder."""
    out = os.path.join(sound_dir, "launcher")
    os.makedirs(out, exist_ok=True)
    for n in NAMES:
        p = os.path.join(out, n + ".wav")
        if not os.path.exists(p):
            try:
                write(p, make(n))
            except Exception:
                pass
    return out


def export_game_sounds(sound_dir):
    """Render drone_sim's built-in sounds to <sound_dir>/gen/*.wav as editable starting points."""
    import numpy as np
    import pygame
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    import drone_sim

    pygame.init()
    sfx = drone_sim.Sfx(True)
    if not sfx.ok:
        print("Sound device unavailable - nothing exported.")
        return 0
    sr = sfx.sr
    out = os.path.join(sound_dir, "gen")
    os.makedirs(out, exist_ok=True)
    n = 0
    for name, snd in sorted(list(sfx.snd.items()) + list(getattr(sfx, "loops", {}).items())):
        try:
            a = pygame.sndarray.array(snd)
            if a.ndim > 1:
                a = a[:, 0]
            with wave.open(os.path.join(out, name + ".wav"), "wb") as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(sr)
                w.writeframes(a.astype("<i2").tobytes())
            n += 1
        except Exception as e:
            print(f"  skipped {name}: {e}")
    print(f"{n} game sounds written to {out}")
    print("Edit one and copy it into sounds/ (same name) to use it in game.")
    return n


if __name__ == "__main__":
    sounds = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sounds")
    if "--export" in sys.argv:
        export_game_sounds(sounds)
    else:
        print("launcher sounds written to", ensure(sounds))
