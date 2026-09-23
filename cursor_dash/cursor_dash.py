#!/usr/bin/env python3
"""
CURSOR DASH - a 3D tunnel dash.  pygame + numpy (software rendered, no other assets).

You ARE the mouse cursor. The tunnel rushes at you; it climbs, dives, banks and
whips through hairpin turns. Slip through holes, dodge pillars, blades, lasers and
crushers - up, down, left, right. Shave obstacles close for near-miss combos.

Move the mouse (or WASD / arrows / gamepad stick).  SPACE start / retry, ESC pause.
"""
import json
import math
import os
import random
import sys

import numpy as np
import pygame

HERE = os.path.dirname(os.path.abspath(__file__))

# =====================================================================
#  CUSTOMIZE ME
# =====================================================================
CONFIG = {
    "window_size": (1280, 720),
    "render_size": (960, 540),     # internal resolution; 1280x720 = prettier, slower
    "fullscreen": False,
    "fov_degrees": 76,
    "bloom": 1.0,                  # neon glow strength, 0 = off
    "vignette": 0.65,
    "speed_blur": True,            # zoom-ghost at high speed
    "draw_distance": 320,          # world units
    "sound": True,
    # --- two-stick pad (no d-pad / face buttons; each stick has a click).
    #     Run `python cursor_dash.py --joytest` (or gamepad_test.bat), wiggle each stick and
    #     click it, and copy the axis / button numbers it prints into the numbers below.
    "gamepad": {
        "axis_x": 0, "axis_y": 1,          # LEFT stick  horizontal / vertical
        "axis_x2": 2, "axis_y2": 3,        # RIGHT stick horizontal / vertical (try 3, 4 if dead)
        "split_sticks": False,             # True: a stick that only reports left/right -
                                           #   left stick X = cursor left/right, right stick X = up/down
        "invert_x": False, "invert_y": False,
        "deadzone": 0.15,
        "sensitivity": 2.6,                # how fast a full stick push sweeps the cursor
        "use_hat": True,                   # a hat / d-pad, if the device has one
        "btn_recenter": 0,                 # LEFT stick click : snap the cursor to the middle
        "btn_pause": 1,                    # RIGHT stick click: pause / resume
        "btn_back": 0,                     # while paused, this one quits to the title
        # in the title and crash screens ANY stick click starts / retries
    },
    # --- Arduino over a serial cable (Uno / Nano / ESP32 ... anything without native USB gamepad).
    #     Set a port here ("COM5") or start with:  python cursor_dash.py --serial COM5
    "serial": {"port": None, "baud": 115200},
    "stage_length": 800,           # metres per stage
    "difficulties": {              # speed x, spacing x (bigger = easier), shields, curve x
        "Easy":   dict(speed=0.85, gap=1.25, shields=3, curve=0.7),
        "Normal": dict(speed=1.00, gap=1.00, shields=2, curve=1.0),
        "Hard":   dict(speed=1.12, gap=0.88, shields=1, curve=1.25),
        "Insane": dict(speed=1.25, gap=0.76, shields=0, curve=1.5),
    },
}
C = CONFIG

W, H = 7.2, 5.0                    # tunnel half width / half height
RX, RY = W - 1.3, H - 1.3          # cursor travel range
R_HIT = 0.55                       # cursor hit radius
DS = 2.5                           # distance between track frames
RIB = 4                            # a light rib every RIB frames
NMAX = 40000
RING = 16

THEMES = [   # name, neon, danger, fog
    ("NEON GRID",     (0.05, 0.90, 1.00), (1.00, 0.30, 0.10), (0.010, 0.020, 0.035)),
    ("MAGENTA DRIVE", (1.00, 0.15, 0.80), (1.00, 0.85, 0.10), (0.035, 0.008, 0.030)),
    ("SOLAR FORGE",   (1.00, 0.62, 0.10), (0.85, 0.15, 1.00), (0.040, 0.020, 0.005)),
    ("TOXIC CORE",    (0.45, 1.00, 0.20), (1.00, 0.20, 0.30), (0.010, 0.035, 0.008)),
    ("ICE VEIN",      (0.50, 0.72, 1.00), (1.00, 0.45, 0.10), (0.012, 0.020, 0.045)),
    ("BLOOD MOON",    (1.00, 0.15, 0.25), (0.30, 0.95, 1.00), (0.040, 0.006, 0.010)),
]


def norm(v):
    n = np.linalg.norm(v)
    return v / n if n > 1e-9 else v


# cross-section: a rounded rectangle (super-ellipse)
def _section():
    n = 5.0
    xs, ys, nx, ny = [], [], [], []
    for j in range(RING + 1):
        a = j / RING * math.tau
        c, s = math.cos(a), math.sin(a)
        x = W * math.copysign(abs(c) ** (2 / n), c)
        y = H * math.copysign(abs(s) ** (2 / n), s)
        gx = math.copysign((abs(x) / W) ** (n - 1), x) / W
        gy = math.copysign((abs(y) / H) ** (n - 1), y) / H
        l = math.hypot(gx, gy) or 1.0
        xs.append(x); ys.append(y); nx.append(-gx / l); ny.append(-gy / l)     # inward normal
    return (np.array(xs), np.array(ys), np.array(nx), np.array(ny))


XS, YS, NXV, NYV = _section()
NX = (NXV[:-1] + NXV[1:]) / 2
NY = (NYV[:-1] + NYV[1:]) / 2


# =====================================================================
#  Track: an endless procedural path with smooth curvature and banking
# =====================================================================
class Track:
    def __init__(self, rng, curve):
        self.rng, self.curve = rng, curve
        self.P = np.zeros((NMAX, 3), np.float32)
        self.R = np.zeros((NMAX, 3), np.float32)
        self.U = np.zeros((NMAX, 3), np.float32)
        self.T = np.zeros((NMAX, 3), np.float32)
        self.YR = np.zeros(NMAX, np.float32)
        self.n = 0
        self.pos = np.zeros(3)
        self.yaw = self.pitch = 0.0
        self.yr = self.pr = self.ty = self.tp = 0.0
        self.left = 40
        self.yaw0 = 0.0

    def new_section(self):
        rng = self.rng
        lv = self.n * DS / C["stage_length"]
        k = self.curve * (0.65 + min(1.0, lv * 0.22))
        self.left = 14 + int(rng.random() * 30)
        straight = rng.random() < max(0.10, 0.30 - lv * 0.03)
        sign = 1 if rng.random() < 0.5 else -1
        if abs(self.yaw - self.yaw0) > 1.5:               # do not spiral forever
            sign = -1 if self.yaw > self.yaw0 else 1
            self.yaw0 = self.yaw
        self.ty = 0.0 if straight else sign * (0.006 + rng.random() * 0.012) * k
        self.ty = max(-0.032, min(0.032, self.ty))
        self.tp = 0.0 if straight else (rng.random() - 0.5) * 0.010 * k
        if self.pitch > 0.42:
            self.tp = -0.006
        elif self.pitch < -0.42:
            self.tp = 0.006

    def push(self):
        if self.n >= NMAX - 2:
            return
        if self.n < 50:
            self.ty = self.tp = 0.0
        elif self.left <= 0:
            self.new_section()
        self.left -= 1
        self.yr += (self.ty - self.yr) * 0.10
        self.pr += (self.tp - self.pr) * 0.10
        self.yaw += self.yr * DS
        self.pitch = max(-0.6, min(0.6, self.pitch + self.pr * DS))
        cp = math.cos(self.pitch)
        T = np.array([math.sin(self.yaw) * cp, math.sin(self.pitch), -math.cos(self.yaw) * cp])
        R = norm(np.cross(T, (0.0, 1.0, 0.0)))
        U = np.cross(R, T)
        b = max(-0.42, min(0.42, self.yr * 11))            # bank into the turn
        c, s = math.cos(b), math.sin(b)
        R, U = R * c - U * s, U * c + R * s
        i = self.n
        self.P[i], self.R[i], self.U[i], self.T[i], self.YR[i] = self.pos, R, U, T, self.yr
        self.pos = self.pos + T * DS
        self.n += 1

    def extend(self, n):
        while self.n < n and self.n < NMAX - 2:
            self.push()

    def frame(self, s):
        i = int(max(0.0, s) // DS)
        i = min(i, NMAX - 4)
        self.extend(i + 3)
        a = (max(0.0, s) - i * DS) / DS
        p = self.P[i] * (1 - a) + self.P[i + 1] * a
        t = norm(self.T[i] * (1 - a) + self.T[i + 1] * a)
        r = self.R[i] * (1 - a) + self.R[i + 1] * a
        r = norm(r - t * np.dot(r, t))
        u = np.cross(r, t)
        return p.astype(np.float64), r, u, t

    def yawrate(self, s):
        i = min(int(max(0.0, s) // DS), NMAX - 4)
        self.extend(i + 2)
        return float(self.YR[i])


# =====================================================================
#  Obstacles: every obstacle is a set of (possibly moving / rotating) boxes
#  rect = (cx, cy, half_w, half_h, rotation) in the tunnel cross-section
# =====================================================================
def hole_rects(hx, hy, gw, gh):
    X, Y = W + 0.6, H + 0.6
    l, r, b, t = hx - gw / 2, hx + gw / 2, hy - gh / 2, hy + gh / 2
    out = []
    if l > -X + 0.05:
        out.append(((-X + l) / 2, 0, (l + X) / 2, Y, 0))
    if r < X - 0.05:
        out.append(((r + X) / 2, 0, (X - r) / 2, Y, 0))
    if t < Y - 0.05:
        out.append((hx, (t + Y) / 2, gw / 2, (Y - t) / 2, 0))
    if b > -Y + 0.05:
        out.append((hx, (b - Y) / 2, gw / 2, (b + Y) / 2, 0))
    return out


def rect_dist(px, py, r):
    cx, cy, hw, hh, rot = r
    dx, dy = px - cx, py - cy
    c, s = math.cos(-rot), math.sin(-rot)
    lx, ly = dx * c - dy * s, dx * s + dy * c
    qx, qy = max(abs(lx) - hw, 0.0), max(abs(ly) - hh, 0.0)
    return math.hypot(qx, qy)


class Obs:
    def __init__(self, s, depth, fn, laser=False):
        self.s, self.depth, self.fn, self.laser = s, depth, fn, laser
        self.minc = 99.0
        self.fr = None
        self.hit = False
        self.done = False

    def clearance(self, x, y, t):
        return min(rect_dist(x, y, r) for r in self.fn(t)) - R_HIT


class Spawner:
    """Chooses what comes next. Harder patterns unlock stage by stage."""

    POOL = [  # name, unlock stage, weight
        ("pillar", 1, 3), ("block", 1, 3), ("bar", 1, 3), ("hole", 1, 4),
        ("gap", 2, 3), ("mover", 2, 2), ("slalom", 2, 2),
        ("diag", 3, 2), ("spinner", 3, 3), ("lasers", 3, 3),
        ("crusher", 4, 3), ("wave", 4, 2),
        ("grid", 5, 3), ("gauntlet", 6, 3),
    ]

    def __init__(self, game):
        self.g = game
        self.rng = game.rng
        self.safe = (0.0, 0.0)
        self.shards_pending = []

    def rnd(self, a, b):
        return a + (b - a) * self.rng.random()

    def pos(self, spread=1.0):
        return (self.rnd(-RX, RX) * spread, self.rnd(-RY, RY) * spread)

    def spawn(self, s, dist, stage):
        pool = [(n, w) for n, st, w in self.POOL if st <= stage]
        names = [n for n, _ in pool]
        n = self.rng.choices(names, [w for _, w in pool])[0]
        return getattr(self, "p_" + n)(s, stage)

    def add(self, s, depth, fn, laser=False):
        o = Obs(s, depth, fn, laser)
        self.g.obstacles.append(o)
        return o

    def static(self, s, depth, rects, laser=False):
        rects = list(rects)
        return self.add(s, depth, lambda t: rects, laser)

    def shard_line(self, s, x, y, n=3, gold=False):
        for k in range(n):
            self.g.shards.append(dict(s=s - 7 * (k + 1), x=x, y=y, gold=gold and k == 0, got=False))

    def gapsize(self, stage):
        k = min(1.0, (stage - 1) / 6)
        return 4.5 - 1.3 * k, 3.7 - 0.9 * k

    def p_pillar(self, s, stage):
        x = self.rnd(-RX, RX)
        self.static(s, 1.8, [(x, 0, 0.95, H + 0.6, 0)])
        return 1.8

    def p_block(self, s, stage):
        x, y = self.pos()
        self.static(s, 2.6, [(x, y, 1.25, 1.25, self.rnd(-0.5, 0.5))])
        return 2.6

    def p_bar(self, s, stage):
        y = self.rnd(-RY * 0.8, RY * 0.8)
        self.static(s, 1.6, [(0, y, W + 0.6, 0.9, 0)])
        self.safe = (self.safe[0], y + (2.4 if y < 0 else -2.4))
        return 1.6

    def p_hole(self, s, stage):
        gw, gh = self.gapsize(stage)
        hx = max(-RX + 0.4, min(RX - 0.4, self.safe[0] + self.rnd(-1, 1) * RX * 1.1))
        hy = max(-RY + 0.4, min(RY - 0.4, self.safe[1] + self.rnd(-1, 1) * RY * 1.1))
        self.static(s, 1.4, hole_rects(hx, hy, gw, gh))
        self.safe = (hx, hy)
        self.shard_line(s, hx, hy, 3, gold=self.rng.random() < 0.06)
        return 1.4

    def p_gap(self, s, stage):
        gw, _ = self.gapsize(stage)
        hx = max(-RX + 0.4, min(RX - 0.4, self.safe[0] + self.rnd(-1, 1) * RX * 1.1))
        self.static(s, 1.4, hole_rects(hx, 0, gw + 0.4, 2 * H + 2))
        self.safe = (hx, self.safe[1])
        self.shard_line(s, hx, self.rnd(-RY, RY) * 0.6, 3)
        return 1.4

    def p_mover(self, s, stage):
        y = self.rnd(-RY, RY) * 0.7
        f, ph = self.rnd(1.3, 2.2), self.rnd(0, 6.28)
        self.add(s, 2.8, lambda t: [(math.sin(t * f + ph) * (RX - 0.3), y, 1.4, 1.4, t * 0.7)])
        return 2.8

    def p_slalom(self, s, stage):
        k = 4 if stage < 4 else 5
        side = 1 if self.rng.random() < 0.5 else -1
        sp = 21
        for i in range(k):
            self.static(s + i * sp, 1.8, [(side * 3.3, 0, 1.1, H + 0.6, 0)])
            side = -side
        return (k - 1) * sp + 1.8

    def p_diag(self, s, stage):
        rot = self.rnd(0.35, 1.0) * (1 if self.rng.random() < 0.5 else -1)
        cx, cy = self.rnd(-2.8, 2.8), self.rnd(-1.6, 1.6)
        self.static(s, 1.6, [(cx, cy, 4.2, 0.65, rot)])
        return 1.6

    def p_spinner(self, s, stage):
        w = self.rnd(1.1, 2.0 + 0.1 * stage) * (1 if self.rng.random() < 0.5 else -1)
        ph = self.rnd(0, 6.28)
        cross = stage >= 5
        L = 4.1 if not cross else 3.9

        def fn(t):
            a = t * w + ph
            r = [(0, 0, L, 0.42, a)]
            if cross:
                r.append((0, 0, L, 0.42, a + math.pi / 2))
            return r
        self.add(s, 1.2, fn)
        return 1.2

    def p_lasers(self, s, stage):
        k = 1 + min(2, stage // 3)
        vertical = self.rng.random() < 0.4
        f = self.rnd(1.6, 2.8)
        phs = [self.rnd(0, 6.28) for _ in range(k)]
        lim = (W - 1.0) if vertical else (H - 0.9)

        def fn(t):
            out = []
            for i, ph in enumerate(phs):
                v = math.sin(t * f * (1 + 0.15 * i) + ph) * lim
                out.append((v, 0, 0.16, H + 0.6, 0) if vertical else (0, v, W + 0.6, 0.16, 0))
            return out
        self.add(s, 0.4, fn, laser=True)
        return 0.4

    def p_crusher(self, s, stage):
        f, ph = self.rnd(1.6, 2.6), self.rnd(0, 6.28)
        Y = H + 0.6

        def fn(t):
            gy = math.sin(t * f * 0.7 + ph) * 1.5
            g = 3.1 + (1 + math.sin(t * f + ph * 2)) * 1.9
            lo, hi = gy - g / 2, gy + g / 2
            return [(0, (lo - Y) / 2, W + 0.6, (lo + Y) / 2, 0), (0, (hi + Y) / 2, W + 0.6, (Y - hi) / 2, 0)]
        self.add(s, 5.0, fn)
        return 5.0

    def p_wave(self, s, stage):
        """a row of blocks that ripple up and down"""
        f, ph = self.rnd(1.8, 2.6), self.rnd(0, 6.28)
        xs = (-4.6, -1.55, 1.55, 4.6)

        def fn(t):
            return [(x, math.sin(t * f + ph + i * 1.3) * (RY - 0.4), 1.0, 1.0, t) for i, x in enumerate(xs)]
        self.add(s, 2.2, fn)
        return 2.2

    def p_grid(self, s, stage):
        f = self.rnd(1.8, 3.0)
        p1, p2 = self.rnd(0, 6.28), self.rnd(0, 6.28)

        def fn(t):
            return [(0, math.sin(t * f + p1) * (H - 0.9), W + 0.6, 0.16, 0),
                    (math.sin(t * f * 1.2 + p2) * (W - 1.0), 0, 0.16, H + 0.6, 0),
                    (0, math.sin(t * f * 0.8 + p1 + 2) * (H - 0.9), W + 0.6, 0.16, 0)]
        self.add(s, 0.4, fn, laser=True)
        return 0.4

    def p_gauntlet(self, s, stage):
        pos, off = s, 0.0
        for name in self.rng.sample(("hole", "bar", "pillar", "block", "gap", "diag"), 4):
            span = getattr(self, "p_" + name)(pos, stage)
            pos += span + 17
        return pos - s


# =====================================================================
#  Sound (synthesised)
# =====================================================================
class Sfx:
    def __init__(self, enabled):
        self.ok = False
        self.snd = {}
        self.eng = None
        if not enabled:
            return
        try:
            pygame.mixer.init(44100, -16, 1, 512)
            pygame.mixer.set_num_channels(12)
            self.ok = True
            sr = 44100
            rng = np.random.default_rng(3)

            def tone(freqs, dur, vol=0.35, decay=6.0, noise=0.0, sweep=0.0):
                t = np.arange(int(sr * dur)) / sr
                w = sum(np.sin(2 * np.pi * (f * (1 + sweep * t)) * t) for f in freqs) / len(freqs)
                env = np.exp(-decay * t)
                return np.clip((w * vol + noise * rng.standard_normal(len(t))) * env, -1, 1)

            def mk(w):
                return pygame.sndarray.make_sound((np.clip(w, -1, 1) * 32767).astype(np.int16))

            self.snd["pick"] = mk(tone([1320, 1980], 0.22))
            self.snd["gold"] = mk(np.concatenate([tone([f], 0.12, decay=6) for f in (784, 988, 1319, 1568)]))
            self.snd["near"] = mk(tone([300], 0.3, 0.25, 9, 0.5, sweep=3) + tone([1500], 0.3, 0.12, 12))
            self.snd["hit"] = mk(tone([80, 55], 0.55, 0.7, 5, 0.6))
            self.snd["die"] = mk(tone([70, 40], 1.4, 0.8, 2.6, 0.7, sweep=-0.3))
            self.snd["stage"] = mk(np.concatenate([tone([f, f * 1.5], 0.16, 0.3, 5) for f in (392, 523, 659, 784)]))
            self.snd["start"] = mk(tone([220, 440], 0.6, 0.4, 3, 0.05, sweep=1.5))
            # engine: filtered noise + low saw
            n = sr * 2
            t = np.arange(n) / sr
            raw = rng.standard_normal(n)
            k = 60
            wind = np.convolve(raw, np.ones(k) / k, "same")
            saw = ((t * 46) % 1) * 2 - 1
            self.eng = mk(0.5 * wind * 3.0 + 0.16 * saw + 0.12 * np.sin(2 * np.pi * 92 * t))
            self.music = self._music(sr, rng)
        except Exception:
            self.ok = False

    def _music(self, sr, rng):
        bpm = 132
        step = 60 / bpm / 4
        bars = 8
        n = int(sr * step * 16 * bars)
        out = np.zeros(n)
        notes = [55.0, 55.0, 65.4, 49.0, 55.0, 55.0, 73.4, 65.4]   # bass root per bar
        minor = [1, 1.2, 1.5, 1.8, 2.0, 1.8, 1.5, 1.2]

        def put(t0, w, g=1.0):
            i = int(t0 * sr)
            m = min(len(w), n - i)
            if m > 0:
                out[i:i + m] += w[:m] * g
        tk = np.arange(int(sr * 0.25)) / sr
        kick = np.sin(2 * np.pi * (50 + 110 * np.exp(-tk * 30)) * tk) * np.exp(-tk * 12)
        th = np.arange(int(sr * 0.05)) / sr
        hat = rng.standard_normal(len(th)) * np.exp(-th * 90) * 0.25
        for bar in range(bars):
            root = notes[bar]
            for s16 in range(16):
                t0 = (bar * 16 + s16) * step
                if s16 % 4 == 0:
                    put(t0, kick, 0.9)
                if s16 % 2 == 1:
                    put(t0, hat, 0.7)
                if s16 % 2 == 0:                              # bass pulse
                    tb = np.arange(int(sr * step * 1.6)) / sr
                    f = root * (2 if s16 % 8 == 6 else 1)
                    saw = ((tb * f) % 1) * 2 - 1
                    put(t0, saw * np.exp(-tb * 7) * 0.22)
                a = root * 4 * minor[(s16 + bar) % 8]          # arp pluck
                tb = np.arange(int(sr * step * 2)) / sr
                put(t0, np.sin(2 * np.pi * a * tb) * np.exp(-tb * 14) * 0.10)
        out = np.clip(out * 0.9, -1, 1)
        return pygame.sndarray.make_sound((out * 32767).astype(np.int16))

    def play(self, name, vol=1.0):
        if self.ok and name in self.snd:
            ch = self.snd[name].play()
            if ch:
                ch.set_volume(vol)


# =====================================================================
#  Arduino on a serial port: lines like  J,512,498,530,511,0,1
#  (left X, left Y, right X, right Y, left click, right click; raw 0-1023 ADC values)
# =====================================================================
class SerialPad:
    def __init__(self, port, baud):
        import serial          # pip install pyserial
        import threading
        self.ser = serial.Serial(port, baud, timeout=0.1)
        self.raw = None
        self.center = None
        self.axes = [0.0] * 4
        self.buttons = [0, 0]
        self.prev = [0, 0]
        self._boot = []
        self.alive = True
        threading.Thread(target=self._reader, daemon=True).start()

    def _reader(self):
        while self.alive:
            try:
                line = self.ser.readline().decode("ascii", "ignore").strip()
            except Exception:
                self.alive = False
                return
            if self.parse(line):
                pass

    def parse(self, line):
        if not line.startswith("J,"):
            return False
        try:
            v = [int(x) for x in line[2:].split(",")]
        except ValueError:
            return False
        if len(v) < 6:
            return False
        a = v[:4]
        if self.center is None:                   # calibrate: stick at rest for the first samples
            self._boot.append(a)
            if len(self._boot) >= 15:
                self.center = [float(np.median([b[i] for b in self._boot])) for i in range(4)]
            return True
        out = []
        for i in range(4):
            c = self.center[i]
            out.append(clampv((a[i] - c) / max(c, 1023 - c, 1.0), -1.0, 1.0))
        self.axes = out
        self.buttons = [1 if v[4] else 0, 1 if v[5] else 0]
        return True

    def pressed(self):
        new = [i for i in range(2) if self.buttons[i] and not self.prev[i]]
        self.prev = list(self.buttons)
        return new


# =====================================================================
#  Game
# =====================================================================
class Player:
    def __init__(self):
        self.s = 30.0
        self.x = self.y = 0.0
        self.vx = self.vy = 0.0
        self.speed = 30.0
        self.shield = 0
        self.inv = 0.0
        self.combo = 0
        self.bonus = 0
        self.dist = 0.0
        self.roll = 0.0
        self.pitch = 0.0


def clampv(v, a, b):
    return max(a, min(b, v))


class Game:
    def __init__(self):
        pygame.init()
        flags = pygame.FULLSCREEN if C["fullscreen"] else 0
        self.screen = pygame.display.set_mode(C["window_size"], flags)
        pygame.display.set_caption("CURSOR DASH")
        self.clock = pygame.time.Clock()
        self.RW, self.RH = C["render_size"]
        self.surf = pygame.Surface((self.RW, self.RH))
        self.glow = pygame.Surface((self.RW // 2, self.RH // 2))
        self.sfx = Sfx(C["sound"])
        self.f_big = pygame.font.SysFont("bahnschrift,consolas,arial", 72, bold=True)
        self.f_med = pygame.font.SysFont("bahnschrift,consolas,arial", 32, bold=True)
        self.f_sm = pygame.font.SysFont("bahnschrift,consolas,arial", 20)
        self.diff_names = list(C["difficulties"])
        self.diff_i = 1
        self.hi_path = os.path.join(HERE, "highscore.json")
        self.hi = self._load_hi()
        self.state = "title"
        self.ctl = [0.0, 0.0]
        self.mouse_active = False
        self.popups = []
        self.show_fps = False
        self.pad = None
        self.ser = None
        port = C["serial"]["port"]
        if "--serial" in sys.argv:
            port = sys.argv[sys.argv.index("--serial") + 1]
        if port:
            try:
                self.ser = SerialPad(port, C["serial"]["baud"])
                print(f"Arduino serial pad on {port}: keep both sticks centred for a second (auto-calibrates).")
            except Exception as ex:
                print(f"Could not open serial port {port}: {ex}")
        pygame.joystick.init()
        if pygame.joystick.get_count():
            self._open_pad(0)
        self.pal = np.random.default_rng(7).uniform(0.8, 1.15, (64, RING))
        # post-process helpers
        yy, xx = np.mgrid[0:self.RH, 0:self.RW]
        r2 = ((xx / self.RW - 0.5) * 2) ** 2 + ((yy / self.RH - 0.5) * 2) ** 2
        v = 1 - C["vignette"] * np.clip(r2 / 2.0, 0, 1) ** 1.2
        self.vig = pygame.surfarray.make_surface(
            (np.repeat(v.T[:, :, None], 3, 2) * 255).astype(np.uint8))
        self.rng = random.Random()
        self.theme_i = 0
        self.neon = np.array(THEMES[0][1])
        self.danger = np.array(THEMES[0][2])
        self.fogc = np.array(THEMES[0][3])
        self.music_on = False
        self.reset(demo=True)

    def _open_pad(self, i):
        try:
            self.pad = pygame.joystick.Joystick(i)
        except pygame.error:
            self.pad = None

    def axis(self, n):
        g = C["gamepad"]
        if self.ser:
            if 0 <= n < 4:
                v = self.ser.axes[n]
                if abs(v) < g["deadzone"]:
                    return 0.0
                return (abs(v) - g["deadzone"]) / (1 - g["deadzone"]) * (1 if v > 0 else -1)
            return 0.0
        try:
            if self.pad and 0 <= n < self.pad.get_numaxes():
                v = self.pad.get_axis(n)
                if abs(v) < g["deadzone"]:
                    return 0.0
                return (abs(v) - g["deadzone"]) / (1 - g["deadzone"]) * (1 if v > 0 else -1)
        except pygame.error:
            pass
        return 0.0

    def hat(self):
        try:
            if self.pad and C["gamepad"]["use_hat"] and self.pad.get_numhats():
                return self.pad.get_hat(0)
        except pygame.error:
            pass
        return (0, 0)

    # ------------------------------------------------------------ setup
    @property
    def diff(self):
        return C["difficulties"][self.diff_names[self.diff_i]]

    def _load_hi(self):
        try:
            with open(self.hi_path) as f:
                return int(json.load(f).get("best", 0))
        except Exception:
            return 0

    def _save_hi(self):
        try:
            with open(self.hi_path, "w") as f:
                json.dump({"best": self.hi}, f)
        except Exception:
            pass

    def reset(self, demo):
        self.demo = demo
        self.rng = random.Random()
        self.track = Track(self.rng, self.diff["curve"])
        self.obstacles = []
        self.shards = []
        self.sparks = []
        self.trail = []
        self.spawner = Spawner(self)
        self.P = Player()
        self.P.shield = self.diff["shields"]
        self.T = 0.0
        self.next_s = 130.0
        self.stage = 1
        self.banner = (THEMES[0][0], 0.0, 1)
        self.shake = 0.0
        self.flash = 0.0
        self.dead_t = 0.0
        self.popups = []
        self.ap_target = (0.0, 0.0)
        self.ap_t = 0.0
        self.fog_d = C["draw_distance"] * 0.55
        self.fixed_speed = None
        rng = np.random.default_rng(self.rng.randrange(1 << 30))
        self.dust = np.stack([rng.uniform(0, C["draw_distance"], 260), rng.uniform(-W, W, 260),
                              rng.uniform(-H, H, 260)], 1)
        self.cam_pos = None
        self.cam_roll = 0.0
        self.set_theme(0, snap=True)
        self.update_camera(0.1, snap=True)

    def set_theme(self, i, snap=False):
        self.theme_i = i % len(THEMES)
        if snap:
            self.neon = np.array(THEMES[self.theme_i][1])
            self.danger = np.array(THEMES[self.theme_i][2])
            self.fogc = np.array(THEMES[self.theme_i][3])

    def speed_at(self, dist):
        base = 30 + 40 * (1 - math.exp(-dist / 3200))
        return base * self.diff["speed"]

    def start_game(self):
        self.reset(demo=False)
        self.state = "play"
        pygame.mouse.set_visible(False)
        self.sfx.play("start")
        self.start_music()

    def start_music(self):
        if self.sfx.ok and not self.music_on:
            self.sfx.music.play(-1)
            self.sfx.music.set_volume(0.32)
            self.sfx.eng.play(-1)
            self.sfx.eng.set_volume(0.0)
            self.music_on = True

    def popup(self, text, color=(255, 240, 160), size="med"):
        self.popups.append([text, 1.4, color, size])

    # ------------------------------------------------------------ events
    def handle(self, e):
        if e.type == pygame.QUIT:
            self.quit()
        if e.type == pygame.MOUSEMOTION:
            sw, sh = self.screen.get_size()
            self.ctl[0] = clampv((e.pos[0] / sw * 2 - 1) * 1.08, -1, 1)
            self.ctl[1] = clampv(-(e.pos[1] / sh * 2 - 1) * 1.08, -1, 1)
            self.mouse_active = True
        if e.type == pygame.MOUSEBUTTONDOWN and self.state in ("title", "dead"):
            self.confirm()
        if e.type == pygame.JOYDEVICEADDED and self.pad is None:
            self._open_pad(e.device_index)
        if e.type == pygame.JOYDEVICEREMOVED:
            self.pad = None
        if e.type == pygame.JOYHATMOTION and self.state == "title" and e.value[0]:
            self.diff_i = (self.diff_i + e.value[0]) % len(self.diff_names)
        if e.type == pygame.JOYBUTTONDOWN:
            g = C["gamepad"]
            if self.state in ("title", "dead"):
                self.confirm()
            elif self.state == "play":
                if e.button == g["btn_pause"]:
                    self.toggle_pause()
                else:
                    self.ctl = [0.0, 0.0]
            elif self.state == "pause":
                if e.button == g["btn_pause"]:
                    self.toggle_pause()
                elif e.button == g["btn_back"]:
                    self.to_title()
        if e.type == pygame.WINDOWFOCUSLOST and self.state == "play":
            self.toggle_pause()
        if e.type != pygame.KEYDOWN:
            return
        k = e.key
        if k == pygame.K_F11:
            pygame.display.toggle_fullscreen()
        elif k == pygame.K_F3:
            self.show_fps = not self.show_fps
        elif k == pygame.K_F12:
            pygame.image.save(self.screen, os.path.join(HERE, f"shot_{pygame.time.get_ticks()}.png"))
        elif k == pygame.K_m and self.sfx.ok:
            v = self.sfx.music.get_volume()
            self.sfx.music.set_volume(0.0 if v > 0 else 0.32)
        elif self.state == "title":
            if k in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_KP_ENTER):
                self.confirm()
            elif k in (pygame.K_LEFT, pygame.K_a, pygame.K_KP4):
                self.diff_i = (self.diff_i - 1) % len(self.diff_names)
            elif k in (pygame.K_RIGHT, pygame.K_d, pygame.K_KP6):
                self.diff_i = (self.diff_i + 1) % len(self.diff_names)
            elif k == pygame.K_ESCAPE:
                self.quit()
        elif self.state == "play":
            if k in (pygame.K_ESCAPE, pygame.K_p):
                self.toggle_pause()
        elif self.state == "pause":
            if k in (pygame.K_ESCAPE, pygame.K_p, pygame.K_SPACE):
                self.toggle_pause()
            elif k == pygame.K_q:
                self.to_title()
        elif self.state == "dead":
            if k in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_r):
                self.confirm()
            elif k == pygame.K_ESCAPE:
                self.to_title()

    def confirm(self):
        self.start_game()

    def to_title(self):
        self.reset(demo=True)
        self.state = "title"
        pygame.mouse.set_visible(True)

    def toggle_pause(self):
        if self.state == "play":
            self.state = "pause"
            pygame.mouse.set_visible(True)
        elif self.state == "pause":
            self.state = "play"
            pygame.mouse.set_visible(False)

    def quit(self):
        pygame.quit()
        sys.exit()

    # ------------------------------------------------------------ simulation
    def autopilot(self, dt):
        P = self.P
        self.ap_t -= dt
        if self.ap_t > 0:
            return
        self.ap_t = 0.12
        nxt = None
        for o in self.obstacles:
            if o.s - o.depth / 2 > P.s and (nxt is None or o.s < nxt.s):
                nxt = o
        if nxt is None or nxt.s - P.s > 120:
            self.ap_target = (self.ap_target[0] * 0.98, self.ap_target[1] * 0.98)
            return
        tarr = self.T + (nxt.s - P.s) / max(P.speed, 1)
        best, bs = self.ap_target, -1e9
        for cx in np.linspace(-RX, RX, 11):
            for cy in np.linspace(-RY, RY, 7):
                c = min(nxt.clearance(cx, cy, tarr), 2.5)
                sc = c - 0.05 * math.hypot(cx - P.x, cy - P.y)
                if sc > bs:
                    bs, best = sc, (cx, cy)
        self.ap_target = best

    def read_input(self, dt):
        if self.demo:
            self.autopilot(dt)
            self.ctl[0] = self.ap_target[0] / RX
            self.ctl[1] = self.ap_target[1] / RY
            return
        keys = pygame.key.get_pressed()
        dx = float((keys[pygame.K_d] or keys[pygame.K_RIGHT] or keys[pygame.K_KP6]) -
                   (keys[pygame.K_a] or keys[pygame.K_LEFT] or keys[pygame.K_KP4]))
        dy = float((keys[pygame.K_w] or keys[pygame.K_UP] or keys[pygame.K_KP8]) -
                   (keys[pygame.K_s] or keys[pygame.K_DOWN] or keys[pygame.K_KP2] or keys[pygame.K_KP5]))
        if keys[pygame.K_c] or keys[pygame.K_KP0]:            # recenter
            self.ctl = [0.0, 0.0]
        sens = 2.4
        g = C["gamepad"]
        if self.pad or self.ser:
            if g["split_sticks"]:
                ax, ay = self.axis(g["axis_x"]), self.axis(g["axis_x2"])
            else:
                ax, ay = self.axis(g["axis_x"]), self.axis(g["axis_y"])
                if g["axis_x2"] >= 0:
                    ax2, ay2 = self.axis(g["axis_x2"]), self.axis(g["axis_y2"])
                    ax, ay = (ax if abs(ax) >= abs(ax2) else ax2), (ay if abs(ay) >= abs(ay2) else ay2)
            ax *= -1 if g["invert_x"] else 1
            ay *= 1 if g["invert_y"] else -1
            hx, hy = self.hat()
            dx += ax * g["sensitivity"] / sens + hx
            dy += ay * g["sensitivity"] / sens + hy
        if dx or dy:
            self.mouse_active = False
            self.ctl[0] = clampv(self.ctl[0] + dx * dt * sens, -1, 1)
            self.ctl[1] = clampv(self.ctl[1] + dy * dt * sens, -1, 1)

    def update(self, dt):
        for pu in self.popups:
            pu[1] -= dt
        self.popups = [p for p in self.popups if p[1] > 0]
        self.shake = max(0.0, self.shake - dt * 2.2)
        self.flash = max(0.0, self.flash - dt * 2.0)
        if self.ser:
            for b in self.ser.pressed():
                self.handle(pygame.event.Event(pygame.JOYBUTTONDOWN, button=b))
        if self.state == "title" and (self.pad or self.ser):    # flick a stick to change difficulty
            g = C["gamepad"]
            fx = self.axis(g["axis_x"]) or self.axis(g["axis_x2"])
            flick = 1 if fx > 0.6 else -1 if fx < -0.6 else 0
            if flick and flick != getattr(self, "_flick", 0):
                self.diff_i = (self.diff_i + flick) % len(self.diff_names)
            self._flick = flick
        if self.state in ("pause",):
            return
        P, tr = self.P, self.track
        self.T += dt
        dead = self.state == "dead"
        # ---- speed & movement
        if dead:
            self.dead_t += dt
            P.speed *= math.exp(-dt * 2.2)
        else:
            self.read_input(dt)
            target = 34.0 if self.demo else self.speed_at(P.dist)
            P.speed += (target - P.speed) * min(1.0, dt * 0.9)
        P.s += P.speed * dt
        if not self.demo:
            P.dist = P.s - 30.0
        if not dead:
            tx, ty = self.ctl[0] * RX, self.ctl[1] * RY
            k = 1 - math.exp(-dt * (10 if self.demo else 15))
            nx, ny = P.x + (tx - P.x) * k, P.y + (ty - P.y) * k
            P.vx, P.vy = (nx - P.x) / max(dt, 1e-4), (ny - P.y) / max(dt, 1e-4)
            P.x, P.y = nx, ny
            # centrifugal shove in the turns
            P.x -= tr.yawrate(P.s) * P.speed * P.speed * 0.035 * dt
            P.x, P.y = clampv(P.x, -RX - 0.35, RX + 0.35), clampv(P.y, -RY - 0.35, RY + 0.35)
        P.roll += (clampv(-P.vx * 0.030, -0.9, 0.9) - P.roll) * min(1, dt * 10)
        P.pitch += (clampv(P.vy * 0.020, -0.6, 0.6) - P.pitch) * min(1, dt * 10)
        P.inv = max(0.0, P.inv - dt)

        # ---- stage / theme
        stage = int(max(P.dist, 0) // C["stage_length"]) + 1
        if not self.demo and stage != self.stage:
            self.stage = stage
            self.set_theme(stage - 1)
            self.banner = (f"STAGE {stage}  -  {THEMES[self.theme_i][0]}", 3.0, 3.0)
            self.sfx.play("stage")
        elif self.demo:
            self.stage = 1 + int(self.T // 25) % 4
        tn = THEMES[self.theme_i]
        kk = min(1.0, dt * 1.5)
        self.neon += (np.array(tn[1]) - self.neon) * kk
        self.danger += (np.array(tn[2]) - self.danger) * kk
        self.fogc += (np.array(tn[3]) - self.fogc) * kk
        if self.banner[1] > 0:
            self.banner = (self.banner[0], self.banner[1] - dt, self.banner[2])

        # ---- spawn ahead
        lim = P.s + C["draw_distance"] + 20
        while self.next_s < lim:
            dist = self.next_s - 30
            st = self.stage if not self.demo else self.stage
            spd = self.speed_at(dist) if not self.demo else 34
            span = self.spawner.spawn(self.next_s, dist, st)
            lv = max(0.0, dist / C["stage_length"])
            secs = max(0.60, 1.05 - 0.05 * lv) * self.diff["gap"]
            self.next_s += span + spd * secs + 8
        self.obstacles = [o for o in self.obstacles if o.s > P.s - 40]
        self.shards = [q for q in self.shards if q["s"] > P.s - 30 and not q["got"]]

        if not dead:
            self.collide(dt)
        # trail
        fp, fr, fu, ft = tr.frame(P.s)
        wp = fp + fr * P.x + fu * P.y
        self.trail.append((wp, fr.copy()))
        if len(self.trail) > 40:
            self.trail.pop(0)
        # dust: wrap around
        self.dust[:, 0] -= P.speed * dt
        w = self.dust[:, 0] < -8
        n = int(w.sum())
        if n:
            self.dust[w, 0] += C["draw_distance"] + 8
            self.dust[w, 1] = np.random.uniform(-W, W, n)
            self.dust[w, 2] = np.random.uniform(-H, H, n)
        self.dust[:, 1] += np.sin(self.T + self.dust[:, 2]) * dt * 0.3
        # sparks
        for sp in self.sparks:
            sp[0] += sp[1] * dt
            sp[1] = sp[1] * (1 - dt * 1.5)
            sp[2] -= dt
        self.sparks = [s for s in self.sparks if s[2] > 0]
        if self.sfx.ok and self.music_on:
            self.sfx.eng.set_volume(0.0 if dead else min(0.5, 0.12 + P.speed / 180))

    def collide(self, dt):
        P = self.P
        for o in self.obstacles:
            half = o.depth / 2 + R_HIT
            if o.s - half <= P.s and o.s + half >= P.s - P.speed * dt:
                c = o.clearance(P.x, P.y, self.T)
                o.minc = min(o.minc, c)
                if c < 0 and not o.hit and not self.demo:
                    o.hit = True
                    self.hurt()
            elif not o.done and P.s > o.s + half:
                o.done = True
                if not o.hit and o.minc < 0.8 and not self.demo:
                    self.near_miss(o.minc)
        for q in self.shards:
            if not q["got"] and abs(q["s"] - P.s) < 1.6:
                if math.hypot(q["x"] - P.x, q["y"] - P.y) < 1.5:
                    q["got"] = True
                    if q["gold"]:
                        P.shield = min(P.shield + 1, 3)
                        P.bonus += 100
                        self.popup("SHIELD +1", (255, 220, 90))
                        self.sfx.play("gold")
                    else:
                        P.bonus += 10
                        self.sfx.play("pick", 0.6)
                    self.burst(q["s"], q["x"], q["y"], 6, (0.6, 1.0, 1.0))

    def near_miss(self, c):
        P = self.P
        P.combo += 1
        gain = 25 * min(P.combo, 12)
        P.bonus += gain
        self.popup(f"NEAR MISS  x{P.combo}   +{gain}", (255, 255, 140))
        self.sfx.play("near", 0.8)

    def burst(self, s, x, y, n, col, speed=9.0):
        fp, fr, fu, ft = self.track.frame(s)
        p = fp + fr * x + fu * y
        for _ in range(n):
            v = np.random.randn(3)
            v = v / (np.linalg.norm(v) + 1e-6) * np.random.uniform(0.3, 1.0) * speed + ft * self.P.speed * 0.6
            self.sparks.append([p.copy(), v, np.random.uniform(0.4, 1.1), col])

    def hurt(self):
        P = self.P
        if P.inv > 0:
            return
        P.combo = 0
        self.shake = 1.0
        self.flash = 1.0
        if P.shield > 0:
            P.shield -= 1
            P.inv = 1.8
            self.sfx.play("hit")
            self.burst(P.s, P.x, P.y, 40, (1.0, 0.6, 0.2))
            self.popup("SHIELD HIT", (255, 120, 90))
        else:
            self.sfx.play("die")
            self.burst(P.s, P.x, P.y, 160, (1.0, 0.7, 0.3), 16)
            self.state = "dead"
            self.dead_t = 0.0
            pygame.mouse.set_visible(True)
            self.score_now = self.score()
            if self.score_now > self.hi:
                self.hi = self.score_now
                self._save_hi()
                self.new_best = True
            else:
                self.new_best = False

    def score(self):
        return int(max(0.0, self.P.dist)) + self.P.bonus

    # ------------------------------------------------------------ camera
    def update_camera(self, dt, snap=False):
        tr, P = self.track, self.P
        pa, ra, ua, ta = tr.frame(P.s - 8.5)
        pb, rb, ub, tb = tr.frame(P.s + 26)
        want = pa + ra * (P.x * 0.42) + ua * (P.y * 0.42 + 1.9)
        look = pb + rb * (P.x * 0.55) + ub * (P.y * 0.55)
        up = ua
        k = 1.0 if snap or self.cam_pos is None else 1 - math.exp(-dt * 10)
        if self.cam_pos is None:
            self.cam_pos, self.cam_look, self.cam_up = want.copy(), look.copy(), up.copy()
        self.cam_pos += (want - self.cam_pos) * k
        self.cam_look += (look - self.cam_look) * k
        self.cam_up = norm(self.cam_up + (up - self.cam_up) * k)
        pos = self.cam_pos.copy()
        if self.shake > 0:
            pos += np.random.randn(3) * 0.22 * self.shake
        f = norm(self.cam_look - pos)
        r = norm(np.cross(f, self.cam_up))
        u = np.cross(r, f)
        roll = -P.vx * 0.004 + (np.random.randn() * 0.02 * self.shake if self.shake else 0)
        self.cam_roll += (roll - self.cam_roll) * min(1, dt * 6)
        c, s = math.cos(self.cam_roll), math.sin(self.cam_roll)
        self.cr, self.cu = r * c + u * s, u * c - r * s
        self.cf, self.cp = f, pos
        spf = clampv((P.speed - 25) / 50, 0, 1)
        fov = C["fov_degrees"] + spf * 16 + self.flash * 4
        self.F = (self.RW / 2) / math.tan(math.radians(fov) / 2)

    def proj(self, pts):
        rel = pts - self.cp
        xc, yc, zc = rel @ self.cr, rel @ self.cu, rel @ self.cf
        z = np.maximum(zc, 0.05)
        sx = np.clip(self.RW / 2 + self.F * xc / z, -8000, 8000)
        sy = np.clip(self.RH / 2 - self.F * yc / z, -8000, 8000)
        return sx, sy, zc

    # ------------------------------------------------------------ drawing
    def fogmix(self, col, d):
        f = np.exp(-(d / self.fog_d) ** 2)
        f = f[..., None] if np.ndim(col) > np.ndim(f) else f
        return col * f + self.fogc * 255 * (1 - f)

    def draw_scene(self):
        tr, P = self.track, self.P
        surf, glow = self.surf, self.glow
        surf.fill((self.fogc * 255).astype(int).tolist())
        glow.fill((0, 0, 0))
        start = max(0, int((P.s - 10) // DS))
        far_i = start + int(C["draw_distance"] / DS)
        idx = list(range(start, start + 18))
        b = ((idx[-1] + 2) // 2) * 2
        idx += list(range(b, b + 56, 2))
        c = ((idx[-1] + 4) // 4) * 4
        idx += list(range(c, far_i, 4))
        idx = np.array(sorted(set(idx)))
        tr.extend(int(idx[-1]) + 3)
        Pp, Rr, Uu = tr.P[idx].astype(np.float64), tr.R[idx].astype(np.float64), tr.U[idx].astype(np.float64)
        V = Pp[:, None, :] + Rr[:, None, :] * XS[None, :, None] + Uu[:, None, :] * YS[None, :, None]
        sx, sy, zc = self.proj(V)
        pts = np.stack([sx, sy], -1).astype(np.int32)
        M = len(idx)
        # ---- wall lighting
        a, bb = idx[:-1], idx[1:]
        nrm = Rr[:-1, None, :] * NX[None, :, None] + Uu[:-1, None, :] * NY[None, :, None]
        cen = (V[:-1, :-1] + V[:-1, 1:] + V[1:, :-1] + V[1:, 1:]) * 0.25
        d = cen - self.player_world()[0]
        d2 = (d * d).sum(-1) + 1e-3
        dist = np.sqrt(d2)
        lam = np.clip(-(nrm * d).sum(-1) / dist, 0, 1)
        ic = lam * 34 / (d2 + 26)
        m = (a + bb) * 0.5
        span = (bb - a).astype(np.float64)
        r0 = np.round(m / RIB) * RIB
        dmin = np.maximum(np.abs(m - r0) - span / 2, 0) * DS
        glowk = (1 / (1 + (dmin / 1.7) ** 2)) * np.minimum(1.0, 2.2 / span)
        tone = self.pal[(a % 64)[:, None], np.arange(RING)[None, :]]
        seam = np.where((np.arange(RING) % 4 == 0)[None, :], 0.55, 1.0)
        albedo = 0.50 * tone * seam
        light = (self.neon[None, None, :] * (glowk[:, None, None] * 0.95 + 0.03) +
                 np.array([0.9, 0.95, 1.0])[None, None, :] * ic[..., None] * 1.5 +
                 np.array([0.03, 0.035, 0.05]))
        col = albedo[..., None] * light
        col = (1 - np.exp(-col * 1.6)) * 255
        dc = np.linalg.norm(cen - self.cp, axis=-1)
        col = self.fogmix(col, dc)
        cols = np.clip(col, 0, 255).astype(np.uint8).tolist()
        valid = (zc[:-1, :-1] > 0.35) & (zc[:-1, 1:] > 0.35) & (zc[1:, :-1] > 0.35) & (zc[1:, 1:] > 0.35)
        Q = np.stack([pts[:-1, :-1], pts[:-1, 1:], pts[1:, 1:], pts[1:, :-1]], 2).tolist()
        validl = valid.tolist()
        # ---- ribs (frame beams with neon)
        rib_rows = {int(k): k for k in range(M) if idx[k] % RIB == 0 and zc[k].min() > 0.35}
        corner_js = (2, 6, 10, 14)
        obs = sorted([o for o in self.obstacles if o.s > P.s - 12], key=lambda o: -o.s)
        oi = 0
        pdrawn = False
        glow_ops = []
        poly, line = pygame.draw.polygon, pygame.draw.lines
        for k in range(M - 2, -1, -1):
            smid = (idx[k] + idx[k + 1]) * 0.5 * DS
            while oi < len(obs) and obs[oi].s >= smid:
                if not pdrawn and obs[oi].s < P.s:
                    self.draw_player(glow_ops)
                    pdrawn = True
                self.draw_obs(obs[oi], glow_ops)
                oi += 1
            if not pdrawn and P.s >= smid:
                self.draw_player(glow_ops)
                pdrawn = True
            if not (idx[k] >= start):
                continue
            rowv, rowc, rowq = validl[k], cols[k], Q[k]
            for j in range(RING):
                if rowv[j]:
                    poly(surf, rowc[j], rowq[j])
            # neon corner strips
            for j in corner_js:
                if valid[k, j]:
                    p1, p2 = pts[k, j].tolist(), pts[k + 1, j].tolist()
                    fk = float(np.exp(-(dc[k, j] / self.fog_d) ** 2))
                    cc = (self.neon * 255 * (0.35 + 0.65 * fk) * fk).astype(int).tolist()
                    pygame.draw.line(surf, cc, p1, p2, 2)
            kk = k + 1
            if kk in rib_rows and idx[kk] >= start:
                self.draw_rib(kk, V, pts, zc, glow_ops, idx)
        while oi < len(obs):
            self.draw_obs(obs[oi], glow_ops)
            oi += 1
        if not pdrawn:
            self.draw_player(glow_ops)
        self.draw_particles(glow_ops)
        self.flush_glow(glow_ops)
        self.post()

    def player_world(self):
        P = self.P
        fp, fr, fu, ft = self.track.frame(P.s)
        return fp + fr * P.x + fu * P.y, fr, fu, ft

    def draw_rib(self, k, V, pts, zc, glow_ops, idx):
        s = self.surf
        outer = V[k]
        # inward offset ring
        fi = idx[k]
        Rk, Uk = self.track.R[fi].astype(np.float64), self.track.U[fi].astype(np.float64)
        inner = outer + (Rk[None, :] * NXV[:, None] + Uk[None, :] * NYV[:, None]) * 0.65
        ix, iy, _ = self.proj(inner)
        ip = np.stack([ix, iy], -1).astype(np.int32)
        d = float(np.linalg.norm(outer[0] - self.cp))
        f = math.exp(-(d / self.fog_d) ** 2)
        op = pts[k].tolist()
        ipl = ip.tolist()
        base = (self.fogc * 255 * (1 - f) + np.array([34, 37, 44]) * f).astype(int).tolist()
        pygame.draw.polygon(s, base, op + ipl[::-1])
        ncol = (self.neon * 255 * f).astype(int)
        w = int(clampv(120 / max(d, 1), 1, 3))
        pygame.draw.lines(s, ncol.tolist(), True, ipl[:-1], w)
        glow_ops.append((ipl[:-1], (self.neon * 255 * f * 0.9).astype(int).tolist(), max(2, w + 1), True))

    def shade_face(self, center, normal, base, emis=None):
        to = self.cp - center
        dd = float(np.linalg.norm(to)) + 1e-6
        lam = max(0.0, float(np.dot(normal, to / dd)))
        lit = 0.10 + 1.15 * lam * (70 / (dd * dd + 70))
        col = np.array(base) * lit * 255
        if emis is not None:
            col = col + emis * 255
        f = math.exp(-(dd / self.fog_d) ** 2)
        col = col * f + self.fogc * 255 * (1 - f)
        return np.clip(col, 0, 255).astype(int).tolist(), f

    def draw_obs(self, o, glow_ops):
        tr = self.track
        if o.fr is None:
            o.fr = tr.frame(o.s)
        fp, fr, fu, ft = o.fr
        if o.s - self.P.s > self.fog_d * 2.1:
            return
        surf = self.surf
        for (cx, cy, hw, hh, rot) in o.fn(self.T):
            c, s = math.cos(rot), math.sin(rot)
            lx = np.array([-hw, hw, hw, -hw])
            ly = np.array([-hh, -hh, hh, hh])
            x = cx + lx * c - ly * s
            y = cy + lx * s + ly * c
            base = fp + fr * x[:, None] + fu * y[:, None]
            hd = ft * (o.depth / 2)
            V = np.concatenate([base - hd, base + hd])
            sx, sy, zc = self.proj(V)
            if zc.min() < 0.3:
                continue
            P2 = np.stack([sx, sy], -1).astype(np.int32)
            faces = [([0, 1, 2, 3], -ft, base.mean(0) - hd), ([4, 5, 6, 7], ft, base.mean(0) + hd)]
            for k in range(4):
                k2 = (k + 1) % 4
                ex, ey = x[k2] - x[k], y[k2] - y[k]
                nl = math.hypot(ex, ey) or 1
                n3 = fr * (ey / nl) + fu * (-ex / nl)
                cc = (base[k] + base[k2]) / 2
                faces.append(([k, k2, 4 + k2, 4 + k], n3, cc))
            vis = []
            for ids, n3, cc in faces:
                if float(np.dot(n3, self.cp - cc)) > 0:
                    vis.append((float(np.linalg.norm(cc - self.cp)), ids, n3, cc))
            vis.sort(key=lambda v: -v[0])
            for dd, ids, n3, cc in vis:
                quad = P2[ids].tolist()
                if o.laser:
                    f = math.exp(-(dd / self.fog_d) ** 2)
                    colr = (np.array([255, 150, 130]) * f + self.fogc * 255 * (1 - f)).astype(int).tolist()
                    pygame.draw.polygon(surf, colr, quad)
                    continue
                col, f = self.shade_face(cc, n3, (0.16, 0.17, 0.20), self.danger * 0.10)
                pygame.draw.polygon(surf, col, quad)
                if abs(float(np.dot(n3, ft))) > 0.9:                # bevel panel on big faces
                    ctr = np.mean(quad, 0)
                    inner = (ctr + (np.array(quad) - ctr) * 0.78).astype(int).tolist()
                    col2 = [min(255, int(v * 1.5 + 6)) for v in col]
                    pygame.draw.polygon(surf, col2, inner)
                ecol = (self.danger * 255 * f).astype(int).tolist()
                pygame.draw.lines(surf, ecol, True, quad, 2)
                glow_ops.append((quad, (self.danger * 255 * f * 0.8).astype(int).tolist(), 3, True))
            if o.laser:
                mid = (P2[0] + P2[1] + P2[2] + P2[3]) // 4
                d = float(np.linalg.norm(base.mean(0) - self.cp))
                f = math.exp(-(d / self.fog_d) ** 2)
                wdt = int(clampv(120 / max(d, 1), 2, 14))
                # long axis of the laser bar
                if hw > hh:
                    a1, a2 = (P2[0] + P2[3]) // 2, (P2[1] + P2[2]) // 2
                else:
                    a1, a2 = (P2[0] + P2[1]) // 2, (P2[2] + P2[3]) // 2
                glow_ops.append(([a1.tolist(), a2.tolist()], (np.array([255, 60, 40]) * f).astype(int).tolist(), wdt, False))

    def draw_player(self, glow_ops):
        P = self.P
        # trail
        if self.state != "dead" and len(self.trail) > 3:
            tp = np.array([t[0] for t in self.trail])
            tx, ty, tz = self.proj(tp)
            ok = tz > 0.4
            for i in range(1, len(tp)):
                if ok[i] and ok[i - 1]:
                    a = i / len(tp)
                    col = (self.neon * 255 * a * 0.45).astype(int).tolist()
                    glow_ops.append(([(int(tx[i - 1]), int(ty[i - 1])), (int(tx[i]), int(ty[i]))], col,
                                     max(1, int(4 * a)), False))
        if self.state == "dead":
            return
        if P.inv > 0 and int(self.T * 18) % 2 == 0:
            return
        wp, fr, fu, ft = self.player_world()
        # local arrow (x right, z forward), thickness in y
        outline = np.array([(0, 1.3), (-0.75, -0.55), (-0.24, -0.35), (-0.30, -1.25),
                            (0.30, -1.25), (0.24, -0.35), (0.75, -0.55)]) * 0.85
        cr, sr = math.cos(P.roll), math.sin(P.roll)
        cp, sp = math.cos(P.pitch), math.sin(P.pitch)

        def to_world(x, y, z):
            x, y = x * cr - y * sr, x * sr + y * cr           # roll around forward axis
            y, z = y * cp + z * sp, -y * sp + z * cp          # nose up / down
            return wp + fr * x + fu * y + ft * z
        th = 0.11
        top = np.array([to_world(x, th, z) for x, z in outline])
        bot = np.array([to_world(x, -th, z) for x, z in outline])
        allp = np.concatenate([top, bot])
        sx, sy, zc = self.proj(allp)
        if zc.min() < 0.3:
            return
        p2 = np.stack([sx, sy], -1).astype(np.int32)
        T_, B_ = p2[:7], p2[7:]
        facets = [((0, 1, 2), 1.0), ((0, 6, 5), 0.78), ((0, 2, 5), 1.25), ((2, 3, 4, 5), 0.6)]
        # sides
        cam = self.cp
        for k in range(7):
            k2 = (k + 1) % 7
            mid = (top[k] + top[k2]) / 2
            e = outline[k2] - outline[k]
            n2 = np.array([e[1], -e[0]])
            n2 = n2 / (np.linalg.norm(n2) + 1e-9)
            n3 = to_world(n2[0], 0, n2[1]) - wp
            if float(np.dot(n3, cam - mid)) > 0:
                lit = 0.35 + 0.45 * abs(n2[0])
                pygame.draw.polygon(self.surf, [int(v) for v in (np.array([150, 160, 175]) * lit)],
                                    [T_[k].tolist(), T_[k2].tolist(), B_[k2].tolist(), B_[k].tolist()])
        for ids, br in facets:
            colr = np.clip(np.array([205, 212, 225]) * br * 0.85 + self.neon * 255 * 0.22, 0, 255)
            pygame.draw.polygon(self.surf, colr.astype(int).tolist(), [T_[i].tolist() for i in ids])
        pygame.draw.lines(self.surf, (250, 252, 255), True, [T_[i].tolist() for i in range(7)], 2)
        glow_ops.append(([T_[i].tolist() for i in range(7)], (self.neon * 255 * 0.95).astype(int).tolist(), 3, True))
        # engine glow
        tail = to_world(0, 0, -1.35)
        tx_, ty_, tz_ = self.proj(tail[None, :])
        glow_ops.append(([(int(tx_[0]), int(ty_[0])), (int(tx_[0]), int(ty_[0]) + 1)],
                         (self.neon * 255 * 0.7).astype(int).tolist(), 12, False))

    def draw_particles(self, glow_ops):
        tr = self.track
        # dust motes
        s = self.P.s + self.dust[:, 0]
        i = np.minimum((s // DS).astype(int), tr.n - 3)
        i = np.maximum(i, 0)
        a = ((s - i * DS) / DS)[:, None]
        p = tr.P[i] * (1 - a) + tr.P[i + 1] * a
        pos = p + tr.R[i] * self.dust[:, 1:2] + tr.U[i] * self.dust[:, 2:3]
        sx, sy, zc = self.proj(pos.astype(np.float64))
        ok = (zc > 1.0) & (sx > 0) & (sx < self.RW) & (sy > 0) & (sy < self.RH)
        f = np.exp(-(zc / (self.fog_d * 0.8)) ** 2)
        for k in np.nonzero(ok)[0][::1]:
            v = int(150 * f[k])
            if v > 14:
                self.surf.set_at((int(sx[k]), int(sy[k])), (v, v, min(255, v + 25)))
        # sparks
        for pos_, vel, life, col in self.sparks:
            x, y, z = self.proj(pos_[None, :])
            if z[0] > 0.5:
                c = (np.array(col) * 255 * min(1.0, life * 2)).astype(int).tolist()
                r = int(clampv(80 / z[0], 1, 4))
                pygame.draw.circle(self.surf, c, (int(x[0]), int(y[0])), r)
                glow_ops.append(([(int(x[0]), int(y[0])), (int(x[0]), int(y[0]) + 1)], c, r * 3, False))
        # energy shards
        for q in self.shards:
            if q["s"] < self.P.s - 8 or q["s"] > self.P.s + C["draw_distance"] * 0.9:
                continue
            fp, fr, fu, ft = tr.frame(q["s"])
            c = fp + fr * q["x"] + fu * q["y"] + fu * math.sin(self.T * 3 + q["s"]) * 0.2
            x, y, z = self.proj(c[None, :])
            if z[0] < 0.6:
                continue
            f = math.exp(-(z[0] / self.fog_d) ** 2)
            sz = clampv(self.F * (0.45 if q["gold"] else 0.3) / z[0], 1, 60)
            col = np.array((1.0, 0.85, 0.25) if q["gold"] else (0.4, 1.0, 1.0)) * 255 * f
            cx, cy = float(x[0]), float(y[0])
            sq = abs(math.cos(self.T * 3 + q["s"]))
            poly = [(cx, cy - sz * 1.4), (cx + sz * sq, cy), (cx, cy + sz * 1.4), (cx - sz * sq, cy)]
            pygame.draw.polygon(self.surf, col.astype(int).tolist(), poly)
            glow_ops.append(([(int(cx), int(cy)), (int(cx), int(cy) + 1)], (col * 0.8).astype(int).tolist(),
                             int(sz * 4) + 2, False))

    def flush_glow(self, ops):
        g = self.glow
        for pts, col, w, closed in ops:
            if len(pts) < 2:
                continue
            p = [(x // 2, y // 2) for x, y in pts]
            col = tuple(int(clampv(c, 0, 255)) for c in col)
            if len(p) == 2 and p[0] == p[1]:
                pygame.draw.circle(g, col, p[0], max(1, w // 2))
            elif len(p) == 2 or w > 8:
                pygame.draw.line(g, col, p[0], p[1], max(1, w // 2))
                if w > 8:
                    pygame.draw.circle(g, col, p[0], w // 2)
            else:
                pygame.draw.lines(g, col, closed, p, max(1, w // 2))

    def post(self):
        surf, RW, RH = self.surf, self.RW, self.RH
        if C["bloom"] > 0:
            small = pygame.transform.smoothscale(self.glow, (RW // 8, RH // 8))
            big = pygame.transform.smoothscale(small, (RW, RH))
            big2 = pygame.transform.smoothscale(self.glow, (RW, RH))
            big2.set_alpha(140)
            surf.blit(big, (0, 0), special_flags=pygame.BLEND_RGB_ADD)
            surf.blit(big2, (0, 0), special_flags=pygame.BLEND_RGB_ADD)
            if C["bloom"] > 1.0:
                surf.blit(big, (0, 0), special_flags=pygame.BLEND_RGB_ADD)
        sf = clampv((self.P.speed - 38) / 35, 0, 1) if C["speed_blur"] else 0
        if sf > 0.02:
            zw, zh = int(RW * (1 + 0.06 * sf)), int(RH * (1 + 0.06 * sf))
            z = pygame.transform.smoothscale(surf, (zw, zh))
            z.set_alpha(int(70 * sf))
            surf.blit(z, ((RW - zw) // 2, (RH - zh) // 2))
        if C["vignette"] > 0:
            surf.blit(self.vig, (0, 0), special_flags=pygame.BLEND_RGB_MULT)
        if self.flash > 0:
            ov = pygame.Surface((RW, RH))
            ov.fill((255, 40, 20))
            ov.set_alpha(int(110 * self.flash))
            surf.blit(ov, (0, 0))

    # ------------------------------------------------------------ HUD
    def text(self, s, font, color, pos, anchor="topleft"):
        img = font.render(s, True, color)
        r = img.get_rect(**{anchor: pos})
        self.screen.blit(font.render(s, True, (0, 0, 0)), r.move(2, 2))
        self.screen.blit(img, r)
        return r

    def overlay(self, alpha, color=(0, 0, 0)):
        s = pygame.Surface(self.screen.get_size(), pygame.SRCALPHA)
        s.fill((*color, alpha))
        self.screen.blit(s, (0, 0))

    def draw_hud(self):
        sw, sh = self.screen.get_size()
        P = self.P
        neon = tuple(int(c * 255) for c in self.neon)
        self.text(f"{self.score():,}", self.f_big, (245, 250, 255), (sw // 2, 14), "midtop")
        self.text(f"{int(max(P.dist, 0))} m", self.f_med, neon, (28, 22))
        self.text(f"{int(P.speed * 3.6)} km/h", self.f_sm, (200, 210, 225), (28, 62))
        self.text(f"BEST {self.hi:,}", self.f_sm, (255, 230, 140), (sw - 28, 26), "topright")
        self.text(f"STAGE {self.stage}", self.f_sm, neon, (sw - 28, 54), "topright")
        for i in range(max(self.diff["shields"], P.shield)):
            col = neon if i < P.shield else (60, 62, 70)
            pygame.draw.polygon(self.screen, col, [(38 + i * 34, sh - 64), (54 + i * 34, sh - 54),
                                                   (54 + i * 34, sh - 38), (38 + i * 34, sh - 24),
                                                   (22 + i * 34, sh - 38), (22 + i * 34, sh - 54)])
        if P.combo > 1:
            self.text(f"COMBO x{P.combo}", self.f_med, (255, 255, 140), (sw - 28, sh - 60), "topright")
        y = sh // 2 + 60
        for txt, t, col, size in self.popups:
            self.text(txt, self.f_med if size == "med" else self.f_sm, col, (sw // 2, y - int((1.4 - t) * 40)), "midtop")
        if self.banner[1] > 0:
            a = min(1.0, self.banner[1] / 1.0)
            img = self.f_med.render(self.banner[0], True, neon)
            img.set_alpha(int(255 * a))
            self.screen.blit(img, img.get_rect(midtop=(sw // 2, sh // 4)))

    def draw_ui(self):
        sw, sh = self.screen.get_size()
        neon = tuple(int(c * 255) for c in self.neon)
        if self.state == "title":
            self.overlay(90)
            self.text("CURSOR DASH", self.f_big, (245, 250, 255), (sw // 2, sh // 5), "midtop")
            self.text("you are the cursor.  don't touch anything.", self.f_med, neon, (sw // 2, sh // 5 + 88), "midtop")
            d = self.diff_names[self.diff_i]
            self.text(f"<   {d.upper()}   >", self.f_med, (255, 255, 255), (sw // 2, sh * 0.58), "midtop")
            self.text("SPACE / click / stick click - start      LEFT / RIGHT / flick stick - difficulty      ESC - quit",
                      self.f_sm, (200, 210, 230), (sw // 2, sh * 0.58 + 56), "midtop")
            self.text("mouse, WASD / arrows / keypad 8462, or either gamepad stick   (C / left click = recenter)", self.f_sm, (170, 180, 200),
                      (sw // 2, sh * 0.58 + 86), "midtop")
            self.text(f"Best: {self.hi:,}", self.f_sm, (255, 230, 140), (sw // 2, sh * 0.58 + 122), "midtop")
        elif self.state == "play" or self.state == "pause":
            self.draw_hud()
            if self.state == "pause":
                self.overlay(150)
                self.text("PAUSED", self.f_big, (255, 255, 255), (sw // 2, sh // 3), "midtop")
                self.text("ESC / SPACE resume      Q quit to title", self.f_sm, (220, 220, 230),
                          (sw // 2, sh // 3 + 100), "midtop")
        elif self.state == "dead":
            self.draw_hud()
            if self.dead_t > 0.7:
                self.overlay(int(min(170, (self.dead_t - 0.7) * 300)))
                self.text("CRASHED", self.f_big, (255, 90, 80), (sw // 2, sh // 4), "midtop")
                self.text(f"Score {self.score_now:,}   -   {int(self.P.dist)} m", self.f_med, (245, 250, 255),
                          (sw // 2, sh // 2 - 10), "midtop")
                msg = "NEW BEST!" if self.new_best else f"Best {self.hi:,}"
                self.text(msg, self.f_med, (255, 230, 140), (sw // 2, sh // 2 + 40), "midtop")
                self.text("SPACE / click - retry        ESC - title", self.f_sm, (210, 215, 230),
                          (sw // 2, sh // 2 + 100), "midtop")
        if self.show_fps:
            self.text(f"{self.clock.get_fps():.0f} fps", self.f_sm, (255, 255, 255), (8, sh - 26))

    def draw(self):
        self.draw_scene()
        size = self.screen.get_size()
        if size == (self.RW, self.RH):
            self.screen.blit(self.surf, (0, 0))
        else:
            pygame.transform.smoothscale(self.surf, size, self.screen)
        self.draw_ui()

    # ------------------------------------------------------------ loop
    def run(self, frames=None):
        n = 0
        while True:
            dt = min(self.clock.tick(60) / 1000.0, 0.05)
            for e in pygame.event.get():
                self.handle(e)
            if frames is not None:
                dt = 1 / 30
            self.update(dt)
            self.update_camera(dt)
            self.draw()
            pygame.display.flip()
            n += 1
            if frames is not None and n >= frames:
                return


def joytest():
    """Print live axis / button / hat numbers so you can fill in CONFIG['gamepad']."""
    pygame.init()
    pygame.joystick.init()
    pads = [pygame.joystick.Joystick(i) for i in range(pygame.joystick.get_count())]
    if not pads:
        print("No gamepad found. Plug it in and try again.")
        return
    p = pads[0]
    print(f"Pad: {p.get_name()}  axes={p.get_numaxes()} buttons={p.get_numbuttons()} hats={p.get_numhats()}")
    print("Move sticks / press buttons. Ctrl+C to quit.")
    clock, last = pygame.time.Clock(), None
    try:
        while True:
            pygame.event.pump()
            cur = ([round(p.get_axis(i), 2) for i in range(p.get_numaxes())],
                   [i for i in range(p.get_numbuttons()) if p.get_button(i)],
                   [p.get_hat(i) for i in range(p.get_numhats())])
            if cur != last:
                print(f"axes {cur[0]}  pressed {cur[1]}  hats {cur[2]}")
                last = cur
            clock.tick(30)
    except KeyboardInterrupt:
        pass


def main():
    if "--joytest" in sys.argv:
        joytest()
        return
    Game().run()


if __name__ == "__main__":
    main()
