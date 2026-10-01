"""Synthesises placeholder sound effects into assets/sounds/gen/ (pure Python, no numpy).
Real recordings with the same name in assets/sounds/ (shot.wav, explosion.ogg, music.mp3 ...) win."""
import math
import os
import random
import struct
import wave

SR = 22050
NAMES = ["shot", "enemy_shot", "reload", "empty", "hit", "down", "revive", "pickup",
         "beep", "explosion", "win", "lose", "step"]


def _noise_env(dur, decay, lp=0.5, amp=1.0, seed=1):
    rnd = random.Random(seed)
    out, y = [], 0.0
    for i in range(int(SR * dur)):
        y += lp * (rnd.uniform(-1, 1) - y)
        out.append(y * amp * math.exp(-i / SR * decay))
    return out


def _tone(freqs, dur, amp=0.5, decay=4.0):
    out = []
    n = int(SR * dur)
    for i in range(n):
        t = i / SR
        f = freqs[min(len(freqs) - 1, int(i / n * len(freqs)))]
        out.append(amp * math.sin(2 * math.pi * f * t) * math.exp(-(t % (dur / len(freqs))) * decay))
    return out


def _mix(*tracks):
    n = max(len(t) for t in tracks)
    return [sum(t[i] for t in tracks if i < len(t)) for i in range(n)]


def _click(at, length=0.02, amp=0.6, seed=3):
    return [0.0] * int(SR * at) + _noise_env(length, 200, 0.9, amp, seed)


def make(name):
    if name == "shot":
        thump = [0.9 * math.sin(2 * math.pi * 70 * i / SR) * math.exp(-i / SR * 30) for i in range(int(SR * 0.2))]
        return _mix(_noise_env(0.35, 14, 0.6, 1.0), thump)
    if name == "enemy_shot":
        return _mix(_noise_env(0.3, 16, 0.35, 0.8, 7))
    if name == "reload":
        return _mix(_click(0.05, amp=0.5), _click(0.55, amp=0.6, seed=5), _click(1.4, 0.03, 0.7, 9))
    if name == "empty":
        return _click(0.0, 0.015, 0.5)
    if name == "hit":
        return _tone([1400], 0.06, 0.4, 40)
    if name == "down":
        return _tone([440, 330, 220], 0.9, 0.5, 2)
    if name == "revive":
        return _tone([523, 659, 784, 1047], 0.6, 0.4, 3)
    if name == "pickup":
        return _tone([880, 1320], 0.18, 0.4, 8)
    if name == "beep":
        return _tone([1000], 0.09, 0.45, 5)
    if name == "explosion":
        boom = [0.9 * math.sin(2 * math.pi * 45 * i / SR) * math.exp(-i / SR * 3) for i in range(int(SR * 1.5))]
        return _mix(_noise_env(2.0, 2.2, 0.08, 1.4, 11), boom)
    if name == "win":
        return _tone([523, 659, 784, 1047, 1047], 1.4, 0.45, 1.5)
    if name == "lose":
        return _tone([392, 349, 311, 262], 1.6, 0.45, 1.2)
    if name == "step":
        return _noise_env(0.08, 60, 0.15, 0.6, random.randrange(99))
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
    gen = os.path.join(sound_dir, "gen")
    os.makedirs(gen, exist_ok=True)
    for n in NAMES:
        p = os.path.join(gen, n + ".wav")
        if not os.path.exists(p):
            write(p, make(n))


if __name__ == "__main__":
    ensure(os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "sounds"))
    print("sounds written")
