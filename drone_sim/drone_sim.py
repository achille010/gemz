#!/usr/bin/env python3
"""
DRONE SIM - an FPV quadcopter flight simulator.  pygame + numpy (software rendered, no assets).

Fly a momentum-based quadcopter over a sunlit city: blast through gate rings against the
clock, thread a low slalom course, chase altitude targets, nail a soft precision landing,
or just cruise in Free Flight.

Controls (standard "mode 2" drone layout):
  LEFT stick  up/down = throttle (climb / descend, Z)   left/right = yaw (turn)
  RIGHT stick up/down = pitch (fly forward / back)      left/right = roll (slide sideways)
  Each stick click: tap / double tap / hold do three different things (see MANUAL.md).
Keyboard: W/S pitch, A/D roll, Up/Down or Space/Shift throttle, Left/Right or Q/E yaw,
C camera, L stabilize, R restart, hold Tab turbo, hold X precision, P/Esc pause.
"""
import json
import math
import os
import random
import re
import sys
import threading
import time
from collections import deque  # noqa: F401  (kept for users extending the missions)

import numpy as np
import pygame
import pygame.gfxdraw

HERE = os.path.dirname(os.path.abspath(__file__))

# =====================================================================
#  CUSTOMIZE ME
# =====================================================================
CONFIG = {
    "window_size": (1280, 720),
    "fullscreen": False,
    "fov_degrees": 78,
    "sky_res": (480, 270),         # resolution of the sky + ground layer. (640, 360) = sharper, slower
    "auto_quality": True,          # lower sky_res by itself if the PC can't keep ~30 fps
    "draw_distance": 330,          # metres
    "shadows": True,
    "trees": 380,
    # --- sound ---------------------------------------------------------
    "sound": True,
    "volume": 0.8,                 # master volume 0..1 for sound effects
    "engine_volume": 0.9,          # motor whine that follows your throttle
    "wind_volume": 0.8,            # wind rush that follows your speed
    # per-sound volume (0 = mute that one). Names: gate combo win touchdown fail crash start tick
    # confirm back pause resume camera stabilize turbo_on turbo_off prec_on prec_off restart warn
    # count go pad deny lowbat empty clip pickup drop star gust.   Your own sounds: drop  sounds/<name>.wav (or .ogg)  next to the game.
    "sound_volumes": {},
    # --- flight ----------------------------------------------------------
    "assist": 1.6,                 # auto-brake when the right stick is centred (0 = pure physics)
    "alt_hold": 2.2,               # holds altitude when the left stick is centred (0 = off)
    "unlock_all": False,           # True = every mission playable without earning stars first
    "wind_scale": 1.0,             # 0 = calm air everywhere, 1.5 = nastier storms
    "battery_scale": 1.0,          # how fast the battery drains (0 = infinite battery)
    # --- USB gamepad (anything Windows lists as a game controller) --------
    "gamepad": {
        "lx": 0, "ly": 1, "rx": 2, "ry": 3,   # axis numbers; run gamepad_test.bat to find yours
        "btn_left": 0, "btn_right": 1,        # stick click button numbers
        "deadzone": 0.12,
        "invert_lx": False, "invert_ly": False, "invert_rx": False, "invert_ry": False,
    },
    # --- Arduino UNO over USB serial (Windows sees it as a COM port, not a gamepad).
    #     Flash arduino/drone_sim_serial (or vault_runner's vault_pad sketch). The game finds the
    #     port and baud rate itself. Lines: lx,ly,rx,ry[,lclick,rclick,...] (labels ok), or a
    #     one-stick "x,y,sw" sketch.
    "arduino": {
        "enabled": True,
        "port": "auto",                # or e.g. "COM19"   (also: --serial COM19)
        "baud": 115200,
        "deadzone": 0.12,
        "invert_lx": False, "invert_ly": False, "invert_rx": False, "invert_ry": False,
        "swap_sticks": False,          # True if left/right sticks are wired the other way round
    },
    # Each stick click does three things (USB pad AND Arduino). Both clicks together = pause.
    # Actions: camera restart turbo stabilize pause precision
    "clicks": {0: {"tap": "camera", "double": "restart", "hold": "turbo"},          # left click
               1: {"tap": "stabilize", "double": "pause", "hold": "precision"}},    # right click
    # one-stick sketches: stick up/down = throttle, left/right = yaw; its click:
    "single_click": {"tap": "stabilize", "double": "camera", "hold": "forward"},
    # LEFT-ONLY pad (right stick broken / not fitted): left stick up/down = fly forward / back,
    # left/right = turn; HOLD right click = climb, HOLD left click = descend; both = pause.
    # Altitude holds by itself and the drone brakes when the stick is centred.
    "left_only": True,
    "hold_time": 0.35,
    "double_time": 0.28,
}
C = CONFIG

# ---------------------------------------------------------------------
#  config.json: the dict above is the DEFAULTS. Anything in config.json next to this file
#  wins, so you can retune the game without editing the code. Missing keys are written back
#  on the first run, and nested dicts (gamepad, arduino, clicks...) merge key by key.
# ---------------------------------------------------------------------
CFG_PATH = os.path.join(HERE, "config.json")


def _merge(base, over):
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            _merge(base[k], v)
        else:
            base[k] = v
    return base


def load_config(path=None, write_back=True):
    """Merge config.json over CONFIG, in place. Tuples stay tuples so the renderer is happy."""
    path = path or CFG_PATH
    try:
        with open(path) as f:
            user = json.load(f)
    except FileNotFoundError:
        user = {}
    except Exception as e:
        print("config.json ignored (%s)" % e)
        user = {}
    # JSON has no tuples and no int keys: put both back
    for k in ("window_size", "sky_res"):
        if isinstance(user.get(k), list):
            user[k] = tuple(user[k])
    if isinstance(user.get("clicks"), dict):
        user["clicks"] = {int(i): v for i, v in user["clicks"].items()}
    _merge(CONFIG, user)
    if write_back:
        try:
            dump = _merge(dict(user), CONFIG)      # keep launcher.py's keys (p1, p2, map...)
            dump["clicks"] = {str(i): v for i, v in CONFIG["clicks"].items()}
            with open(path, "w") as f:
                json.dump(dump, f, indent=2)
        except Exception:
            pass
    return CONFIG

G = 15.0                    # gravity (world units / s^2)
THROTTLE_RANGE = G * 1.15   # extra thrust above/below hover available from stick
MAX_TILT = 0.60             # radians, full stick tilt (~34 deg)
TILT_RESPONSE = 7.0
YAW_RATE = 2.4
DRAG_H = 0.85
DRAG_V = 1.35
GROUND_Y = 0.0
CEILING = 160.0
NEAR = 0.25
ROAD = 128.0                # road grid spacing (m)
ROAD_W = 9.0                # road width (m)

WORLD_UP = np.array([0.0, 1.0, 0.0])
SUN = np.array([0.42, 0.50, 0.76])
SUN = SUN / np.linalg.norm(SUN)
SKY_TOP = np.array([46, 104, 186], np.float32)
SKY_HOR = np.array([196, 214, 232], np.float32)
FOG = np.array([188, 204, 222], np.float32)
SUN_COL = np.array([255, 236, 200], np.float32)
MOUNT_FAR = np.array([156, 172, 196], np.float32)
MOUNT_NEAR = np.array([124, 144, 164], np.float32)


def arg_value(flag, default=None):
    """Value after a command line flag, e.g. --mission run/mission.json."""
    if flag in sys.argv:
        i = sys.argv.index(flag) + 1
        if i < len(sys.argv):
            return sys.argv[i]
    return default


def m_heavy(game):
    """True when the running mission flies a heavy airframe (a generator modifier)."""
    return bool(MISSIONS[game.mission_i].get("heavy"))


def clampv(v, a, b):
    return max(a, min(b, v))


def lerp(a, b, t):
    return a + (b - a) * t


def lerp_angle(a, b, t):
    d = (b - a + math.pi) % math.tau - math.pi
    return a + d * t


def heading_vec(yaw):
    return np.array([math.sin(yaw), 0.0, math.cos(yaw)])


def right_vec(yaw):
    return np.array([math.cos(yaw), 0.0, -math.sin(yaw)])


def basis(yaw, pitch, roll):
    """rows: right, up, forward.  pitch > 0 looks up, roll > 0 banks right."""
    f = np.array([math.sin(yaw) * math.cos(pitch), math.sin(pitch), math.cos(yaw) * math.cos(pitch)])
    r0 = right_vec(yaw)
    u0 = np.cross(f, r0)
    c, s = math.cos(roll), math.sin(roll)
    return np.array([r0 * c - u0 * s, u0 * c + r0 * s, f])


def look_basis(eye, target, roll=0.0):
    f = target - eye
    f = f / (np.linalg.norm(f) + 1e-9)
    r = np.cross(WORLD_UP, f)
    n = np.linalg.norm(r)
    r = r / n if n > 1e-6 else np.array([1.0, 0.0, 0.0])
    u = np.cross(f, r)
    c, s = math.cos(roll), math.sin(roll)
    return np.array([r * c - u * s, u * c + r * s, f])


def shade(col, k):
    return tuple(int(clampv(c * k, 0, 255)) for c in col)


# =====================================================================
#  Sound (synthesised, no external assets)
# =====================================================================
class Sfx:
    def __init__(self, enabled):
        self.ok = False
        self.snd = {}
        self.loops = {}
        self.chans = 2
        if not enabled:
            return
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(44100, -16, 2, 512)
            pygame.mixer.set_num_channels(20)
            sr, _, self.chans = pygame.mixer.get_init()   # the device may force stereo
            self.sr = sr
            rng = np.random.default_rng(11)

            def tone(freqs, dur, vol=0.35, decay=6.0, noise=0.0, sweep=0.0):
                t = np.arange(int(sr * dur)) / sr
                w = sum(np.sin(2 * np.pi * (f * (1 + sweep * t)) * t) for f in freqs) / len(freqs)
                return np.clip((w * vol + noise * rng.standard_normal(len(t))) * np.exp(-decay * t), -1, 1)

            def seq(*parts):
                return np.concatenate(parts)

            mk = self._mk
            S = self.snd
            S["gate"] = mk(seq(*[tone([f], 0.09, 0.30, 8) for f in (784, 1175)]))
            S["combo"] = mk(seq(*[tone([f, f * 1.5], 0.10, 0.28, 7) for f in (523, 659, 880, 1046)]))
            S["win"] = mk(seq(*[tone([f, f * 1.25, f * 1.5], 0.16, 0.3, 4) for f in (523, 659, 784, 1046, 1318)]))
            S["touchdown"] = mk(tone([90], 0.25, 0.6, 16, 0.4))
            S["fail"] = mk(seq(*[tone([f], 0.25, 0.35, 4) for f in (392, 311, 247)]))
            S["crash"] = mk(tone([70, 45], 1.3, 0.8, 2.4, 0.75, sweep=-0.3))
            S["start"] = mk(tone([220, 440], 0.55, 0.4, 3, 0.05, sweep=1.4))
            S["tick"] = mk(tone([1500], 0.04, 0.22, 60))
            S["confirm"] = mk(seq(tone([660], 0.07, decay=12), tone([990], 0.12, decay=8)))
            S["back"] = mk(seq(tone([700], 0.07, decay=12), tone([440], 0.12, decay=8)))
            S["pause"] = mk(tone([440, 330], 0.2, 0.3, 10))
            S["resume"] = mk(seq(tone([520], 0.06, decay=12), tone([780], 0.1, decay=8)))
            S["camera"] = mk(seq(tone([0.1], 0.03, 0, 80, 0.5), tone([0.1], 0.05, 0, 60, 0.4)))
            S["stabilize"] = mk(tone([600], 0.35, 0.35, 7, 0.02, sweep=-0.9))
            S["turbo_on"] = mk(tone([200], 0.35, 0.4, 5, 0.25, sweep=3))
            S["turbo_off"] = mk(tone([500], 0.25, 0.3, 8, 0.1, sweep=-1.5))
            S["prec_on"] = mk(tone([500], 0.18, 0.3, 8, sweep=-0.8))
            S["prec_off"] = mk(tone([300], 0.15, 0.3, 10, sweep=1.5))
            S["restart"] = mk(seq(*[tone([f], 0.06, 0.3, 14) for f in (880, 660, 880)]))
            S["warn"] = mk(seq(tone([1250], 0.07, 0.35, 5), tone([0.1], 0.04, 0), tone([1250], 0.07, 0.35, 5)))
            S["count"] = mk(tone([880], 0.14, 0.4, 10))
            S["go"] = mk(tone([1760, 880], 0.35, 0.4, 5))
            S["pad"] = mk(seq(tone([880], 0.08, decay=10), tone([1320], 0.1, decay=10)))
            S["deny"] = mk(tone([160], 0.25, 0.5, 7))
            S["lowbat"] = mk(seq(tone([988], 0.09, 0.3, 6), tone([0.1], 0.05, 0), tone([740], 0.12, 0.3, 6)))
            S["empty"] = mk(tone([400], 0.9, 0.4, 2, 0.05, sweep=-0.7))
            S["clip"] = mk(tone([1800, 2600], 0.18, 0.35, 14, 0.3))
            S["pickup"] = mk(seq(*[tone([f], 0.07, 0.3, 10) for f in (523, 784, 1046)]))
            S["drop"] = mk(seq(*[tone([f], 0.07, 0.3, 10) for f in (1046, 784, 1318)]))
            S["star"] = mk(tone([1568, 2349], 0.4, 0.3, 5))
            S["gust"] = mk(0.0 * tone([1], 0.01))
            # seamless loops: periodic signals + FFT-shaped (circular) noise
            n = sr
            t = np.arange(n) / sr

            def band_noise(lo, hi):
                spec = np.fft.rfft(rng.standard_normal(n))
                fr = np.fft.rfftfreq(n, 1 / sr)
                spec[(fr < lo) | (fr > hi)] = 0
                w = np.fft.irfft(spec, n)
                return w / (np.abs(w).max() + 1e-9)

            def motor(f):
                w = sum(np.sin(2 * np.pi * f * k * t) / k for k in range(1, 7))
                chop = 0.75 + 0.25 * np.sin(2 * np.pi * 4 * f / 7 * t)
                return 0.32 * w / 2.4 * chop + 0.18 * band_noise(f * 2, f * 9)

            self.loops["eng_lo"] = mk(motor(110))
            self.loops["eng_mid"] = mk(motor(170))
            self.loops["eng_hi"] = mk(motor(250))
            self.loops["wind"] = mk(0.55 * band_noise(80, 900))
            n2 = int(sr * 1.2)
            S["gust"] = mk(0.6 * np.convolve(rng.standard_normal(n2), np.ones(80) / 80, "same") * 3
                           * np.sin(np.linspace(0, np.pi, n2)) ** 2)
            self.ch = {}
            self._custom_and_volume()
            self.ok = True
        except Exception as ex:
            print("Sound disabled:", ex)
            self.ok = False

    def _mk(self, w):
        a = (np.clip(w, -1, 1) * 32767).astype(np.int16)
        if self.chans > 1:
            a = np.repeat(a[:, None], self.chans, 1)
        return pygame.sndarray.make_sound(np.ascontiguousarray(a))

    def _custom_and_volume(self):
        folder = os.path.join(HERE, "sounds")
        if os.path.isdir(folder):
            for fn in os.listdir(folder):
                name, ext = os.path.splitext(fn)
                if ext.lower() in (".wav", ".ogg", ".mp3"):
                    try:
                        snd = pygame.mixer.Sound(os.path.join(folder, fn))
                    except Exception as ex:
                        print(f"Could not load sounds/{fn}: {ex}")
                        continue
                    (self.loops if name in self.loops else self.snd)[name] = snd
        for name, snd in self.snd.items():
            snd.set_volume(clampv(C["volume"] * C["sound_volumes"].get(name, 1.0), 0, 1))

    def play(self, name, vol=1.0):
        if self.ok and name in self.snd:
            ch = self.snd[name].play()
            if ch:
                ch.set_volume(vol)

    def engine(self, thr01, speed01, on=True):
        """Crossfade three motor loops by throttle, plus wind by speed."""
        if not self.ok:
            return
        for k in self.loops:
            if k not in self.ch or not self.ch[k].get_busy():
                self.ch[k] = self.loops[k].play(loops=-1)
        if not all(self.ch.values()):
            return
        ev = C["engine_volume"] * C["volume"] * (1 if on else 0)
        x = clampv(thr01, 0, 1) * 2
        self.ch["eng_lo"].set_volume(ev * 0.55 * max(0.0, 1 - x))
        self.ch["eng_mid"].set_volume(ev * 0.55 * max(0.0, 1 - abs(x - 1)))
        self.ch["eng_hi"].set_volume(ev * 0.55 * max(0.0, x - 1))
        self.ch["wind"].set_volume(C["wind_volume"] * C["volume"] * clampv(speed01, 0, 1) ** 1.5 * 0.7 * (1 if on else 0.3))

    def stop_engine(self):
        for ch in getattr(self, "ch", {}).values():
            if ch:
                ch.stop()
        if self.ok:
            self.ch = {}


# =====================================================================
#  Arduino pad over USB serial (auto port / baud / format, reconnects)
# =====================================================================
class SerialPad:
    """Reads a microcontroller that prints one line of numbers per reading:
         lx, ly, rx, ry[, btn0, btn1, ...]
    Any separator / labels work ("X:512 Y:498 ..."). Axes may be raw ADC (0-1023 / 0-4095)
    or already -1..1. Sticks and buttons are calibrated from their resting state, so
    buttons may report 0 or 1 when pressed. Runs in a background thread and reconnects."""
    NUM = re.compile(r"(?<![A-Za-z0-9_.])-?\d+(?:\.\d+)?")
    GOOD_VIDS = (0x2341, 0x2A03, 0x1A86, 0x0403, 0x10C4, 0x239A)   # Arduino, CH340, FTDI, CP210x, Adafruit

    def __init__(self, cfg, start=True):
        self.cfg = cfg
        self.lock = threading.Lock()
        self.status = "searching for Arduino..."
        self.port = None
        self.connected = False
        self.last_line = ""
        self.vals = None
        self.calib = []
        self.center = self.idle = None
        self.full = 1023.0
        if start:
            try:
                import serial  # noqa: F401
                import serial.tools.list_ports  # noqa: F401
            except ImportError:
                self.status = "pyserial not installed (pip install pyserial)"
                return
            threading.Thread(target=self._run, daemon=True).start()

    # -- parsing (also used directly by tests) --
    def feed(self, line):
        nums = [float(n) for n in self.NUM.findall(line)]
        if len(nums) < 3:
            return False
        with self.lock:
            self.last_line = line.strip()
            if self.center is None or len(nums) != len(self.center) + len(self.idle):
                self.calib.append(nums)
                self.calib = [c for c in self.calib if len(c) == len(nums)][-40:]
                if len(self.calib) >= 12:
                    cols = list(zip(*self.calib))
                    na = 2 if len(nums) == 3 else 4        # "x,y,sw" = one stick
                    self.center = [sorted(c)[len(c) // 2] for c in cols[:na]]
                    self.idle = [max(set(c), key=c.count) for c in cols[na:]]
                    top = max(max(c) for c in cols[:na])
                    self.full = 1.0 if top <= 1.5 else 4095.0 if top > 1100 else 1023.0
                    self.calib = []
                return True
            self.vals = nums
        return True

    def recalibrate(self):
        with self.lock:
            self.center = self.idle = self.vals = None
            self.calib = []

    @property
    def n_axes(self):
        with self.lock:
            return len(self.center) if self.center else 4

    @property
    def ready(self):
        return self.connected and self.vals is not None

    def axis(self, i):
        with self.lock:
            if self.vals is None or not 0 <= i < len(self.center):
                return 0.0
            v, c = self.vals[i], self.center[i]
            lo = -1.0 if self.full == 1.0 else 0.0
            span = (self.full - c) if v >= c else (c - lo)
            a = (v - c) / span if span > 1e-6 else 0.0
        a = max(-1.0, min(1.0, a))
        dz = self.cfg["deadzone"]
        return 0.0 if abs(a) < dz else (abs(a) - dz) / (1 - dz) * (1 if a > 0 else -1)

    def button(self, i):
        with self.lock:
            if self.vals is None or not 0 <= i < len(self.idle):
                return False
            return self.vals[len(self.center) + i] != self.idle[i]

    def num_buttons(self):
        with self.lock:
            return len(self.idle) if self.idle else 0

    # -- serial thread --
    def _candidates(self):
        from serial.tools import list_ports
        if self.cfg["port"] != "auto":
            return [self.cfg["port"]]
        ports = [p for p in list_ports.comports() if "bluetooth" not in (p.description or "").lower()]
        good = [p.device for p in ports if p.vid in self.GOOD_VIDS or
                re.search(r"arduino|ch34|usb.?serial|uno", (p.description or "") + (p.manufacturer or ""), re.I)]
        return good + [p.device for p in ports if p.device not in good]

    def _run(self):
        import serial
        while True:
            for dev in self._candidates():
                for baud in dict.fromkeys([self.cfg["baud"], 115200, 9600, 57600, 38400, 19200, 250000]):
                    try:
                        s = serial.Serial(dev, baud, timeout=0.2)
                    except Exception:
                        break                     # port busy / gone: next port
                    self.status = f"trying {dev} @ {baud}..."
                    ok, t0, buf = 0, time.time(), b""
                    self.recalibrate()
                    try:
                        # the UNO resets when the port opens: give it up to ~3 s to talk
                        while time.time() - t0 < 3.0 and ok < 6:
                            buf += s.read(256)
                            *lines, buf = buf.split(b"\n")
                            for ln in lines:
                                if self.feed(ln.decode("ascii", "ignore")):
                                    ok += 1
                        if ok < 6:
                            s.close()
                            continue
                        self.port, self.connected = dev, True
                        self.status = f"connected on {dev} @ {baud}"
                        while True:
                            buf += s.read(max(1, s.in_waiting))
                            *lines, buf = buf.split(b"\n")
                            for ln in lines:
                                self.feed(ln.decode("ascii", "ignore"))
                    except Exception:
                        pass
                    finally:
                        try:
                            s.close()
                        except Exception:
                            pass
                    if self.connected:
                        self.connected = False
                        self.status = f"{dev} disconnected - searching..."
                        break
            if not self.connected and self.status.startswith(("trying", "searching")):
                self.status = "no Arduino found - plug it in (searching...)"
            time.sleep(1.0)


class UdpPad:
    """A pad fed by launcher.py over UDP instead of by a serial cable.

    The launcher owns the two Arduino pads (see pads.py) and streams both of them here ~60
    times a second as   {"p": [[lx, ly, rx, ry, lclick, rclick, ok], [...]]}   with up and
    right positive. Pad 1 flies the drone; pad 2 is the co-pilot, whose clicks are merged
    into pad 1's so they work the camera, stabilize and pause.

    It deliberately duck-types SerialPad, so the rest of the game reads it without knowing
    which one it got. Axes arrive already deadzoned and oriented, so axis() passes them on.
    """

    def __init__(self, port=47800, copilot=True):
        self.lock = threading.Lock()
        self.port = port
        self.copilot = copilot
        self.connected = False
        self.status = "waiting for the launcher on UDP %d" % port
        self.last_line = ""
        self.vals = [[0.0] * 7, [0.0] * 7]
        self.last_t = 0.0
        self.center = [0.0] * 4          # only here so n_axes / button() line up with SerialPad
        self.idle = [0, 0]
        self.full = 1.0
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self):
        import socket
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.bind(("127.0.0.1", self.port))
        except OSError as e:
            self.status = "UDP %d busy (%s) - is another copy running?" % (self.port, e)
            return
        s.settimeout(0.5)
        while True:
            try:
                data, _ = s.recvfrom(4096)
                pkt = json.loads(data.decode("ascii", "ignore"))
                pads = pkt.get("p") or []
                with self.lock:
                    for i in range(min(2, len(pads))):
                        self.vals[i] = (list(pads[i]) + [0.0] * 7)[:7]
                    self.last_t = time.time()
                    self.last_line = str(pads[0][:6]) if pads else ""
                if not self.connected:
                    self.connected = True
                    self.status = "launcher connected"
            except socket.timeout:
                if self.connected and time.time() - self.last_t > 1.5:
                    self.connected = False
                    self.status = "launcher stopped sending - waiting..."
            except Exception:
                pass

    @property
    def ready(self):
        with self.lock:
            return self.connected and time.time() - self.last_t < 1.5 and bool(self.vals[0][6])

    @property
    def n_axes(self):
        return 4

    def recalibrate(self):
        pass                             # the launcher calibrates the real sticks

    def axis(self, i):
        with self.lock:
            return float(self.vals[0][i]) if 0 <= i < 4 else 0.0

    def button(self, i):
        with self.lock:
            if not 0 <= i < 2:
                return False
            mine = bool(self.vals[0][4 + i])
            mate = bool(self.vals[1][4 + i]) and bool(self.vals[1][6]) and self.copilot
            return mine or mate

    def num_buttons(self):
        return 2

    def copilot_live(self):
        with self.lock:
            return bool(self.vals[1][6]) and time.time() - self.last_t < 1.5


# =====================================================================
#  World: textures, buildings, trees, checkpoints, missions
# =====================================================================
def _noise(rng, cells, size):
    """Seamless value noise, 0..1, (size, size)."""
    small = rng.random((cells, cells)).astype(np.float32)
    big = np.tile(small, (3, 3))
    s = pygame.surfarray.make_surface(np.repeat((big * 255).astype(np.uint8)[..., None], 3, 2))
    s = pygame.transform.smoothscale(s, (size * 3, size * 3))
    a = pygame.surfarray.array3d(s)[size:2 * size, size:2 * size, 0].astype(np.float32) / 255
    return a.T


def make_ground_textures(seed=5):
    rng = np.random.default_rng(seed)
    N = 1024                                    # texels, 0.5 m each -> 512 m tile
    n1 = _noise(rng, 16, N)
    n2 = _noise(rng, 64, N)
    n3 = _noise(rng, 256, N)
    grain = rng.random((N, N)).astype(np.float32)
    g = 0.5 * n1 + 0.3 * n2 + 0.2 * n3
    grass_a = np.array([62, 98, 42], np.float32)
    grass_b = np.array([104, 128, 56], np.float32)
    dry = np.array([140, 128, 82], np.float32)
    tex = grass_a + (grass_b - grass_a) * g[..., None]
    dmask = np.clip((n1 - 0.62) * 5, 0, 1)[..., None]
    tex = tex * (1 - dmask) + dry * dmask
    tex *= (0.88 + 0.24 * grain)[..., None]
    # roads every 128 m (256 texels): asphalt, kerbs, dashed centre line
    idx = np.arange(N)
    m = (idx % 256) * 0.5                       # metres into the block
    road = m < ROAD_W
    kerb = (m >= ROAD_W) & (m < ROAD_W + 1.2)
    line = (np.abs(m - ROAD_W / 2) < 0.18)
    dash = ((idx * 0.5) % 6) < 3.2
    asphalt = np.array([58, 60, 64], np.float32) * (0.9 + 0.2 * grain[..., None])
    kerbc = np.array([150, 148, 140], np.float32)
    rx, rz = road[None, :], road[:, None]
    kx, kz = kerb[None, :], kerb[:, None]
    anyroad = rx | rz
    tex = np.where(((kx | kz) & ~anyroad)[..., None], kerbc, tex)
    tex = np.where(anyroad[..., None], asphalt, tex)
    lines = (line[None, :] & dash[:, None] & ~rz) | (line[:, None] & dash[None, :] & ~rx)
    tex = np.where(lines[..., None], np.array([225, 205, 120], np.float32), tex)
    tex = np.clip(tex, 0, 255).astype(np.float32)
    # a blurred copy for far away (stops shimmering)
    s = pygame.surfarray.make_surface(tex.transpose(1, 0, 2).astype(np.uint8))
    s = pygame.transform.smoothscale(pygame.transform.smoothscale(s, (256, 256)), (256, 256))
    far = pygame.surfarray.array3d(s).transpose(1, 0, 2).astype(np.float32)
    macro = 0.84 + 0.3 * _noise(rng, 8, 256)
    clouds = _noise(rng, 12, 512) * 0.65 + _noise(rng, 48, 512) * 0.35
    return tex, far, macro.astype(np.float32), clouds.astype(np.float32)


def in_road(x, z, margin):
    mx, mz = x % ROAD, z % ROAD
    return (mx < ROAD_W + margin or mx > ROAD - margin) or (mz < ROAD_W + margin or mz > ROAD - margin)


PALETTE = [  # facade, style
    ((196, 186, 168), "concrete"), ((170, 160, 150), "concrete"), ((150, 84, 64), "brick"),
    ((120, 150, 180), "glass"), ((92, 128, 160), "glass"), ((210, 206, 196), "concrete"),
    ((128, 136, 150), "glass"), ((176, 110, 80), "brick"),
]


def make_buildings(rng, n, spread, avoid):
    out = []
    for _ in range(n):
        for _try in range(60):
            x = (rng.random() * 2 - 1) * spread
            z = (rng.random() * 2 - 1) * spread
            w = 6 + rng.random() * 10
            d = 6 + rng.random() * 10
            r = max(w, d) / 2
            if in_road(x - w / 2, z - d / 2, 1.5) or in_road(x + w / 2, z + d / 2, 1.5) or \
                    in_road(x, z, r):
                continue
            if any((x - ax) ** 2 + (z - az) ** 2 < (ar + r) ** 2 for ax, az, ar in avoid):
                continue
            if any(abs(x - b["x"]) < (w + b["w"]) / 2 + 3 and abs(z - b["z"]) < (d + b["d"]) / 2 + 3 for b in out):
                continue
            break
        else:
            continue
        near = math.hypot(x, z)
        h = 8 + rng.random() * (20 + 50 * math.exp(-near / 160))
        col, style = PALETTE[rng.randrange(len(PALETTE))]
        hw, hd = w / 2, d / 2
        corners = [(x - hw, z - hd), (x + hw, z - hd), (x + hw, z + hd), (x - hw, z + hd)]
        pts = np.array([[cx, 0, cz] for cx, cz in corners] + [[cx, h, cz] for cx, cz in corners], float)
        out.append({"x": x, "z": z, "w": w, "d": d, "h": h, "col": col, "style": style, "pts": pts,
                    "antenna": h > 40 and rng.random() < 0.7, "seed": rng.random()})
    return out


def make_trees(rng, n, spread, buildings, avoid):
    out = []
    tries = 0
    while len(out) < n and tries < n * 20:
        tries += 1
        x = (rng.random() * 2 - 1) * spread
        z = (rng.random() * 2 - 1) * spread
        if in_road(x, z, 2.5):
            continue
        if any(abs(x - b["x"]) < b["w"] / 2 + 3 and abs(z - b["z"]) < b["d"] / 2 + 3 for b in buildings):
            continue
        if any((x - ax) ** 2 + (z - az) ** 2 < ar * ar for ax, az, ar in avoid):
            continue
        h = 5 + rng.random() * 5
        out.append((x, z, h, 1.6 + rng.random() * 1.4, rng.random()))
    return np.array(out, float).reshape(-1, 5)


def cp(pos, r, kind="gate", hold=0.0, label=""):
    return {"pos": np.array(pos, dtype=float), "r": r, "kind": kind, "hold": hold, "label": label}


def build_ring_rush(rng):
    pts = []
    x, z, y = 0.0, 20.0, 12.0
    ang = 0.0
    for i in range(10):
        ang += (rng.random() - 0.5) * 1.6
        step = 22 + rng.random() * 10
        x += math.sin(ang) * step
        z += math.cos(ang) * step
        y = clampv(y + (rng.random() - 0.5) * 14, 6, 55)
        pts.append(cp((x, y, z), 5.5, "gate", label=f"GATE {i + 1}"))
    return pts


def build_slalom(rng):
    pts = []
    z = 18.0
    side = 1
    for i in range(14):
        z += 12 + rng.random() * 3
        x = side * (8 + rng.random() * 3) + 40
        side *= -1
        y = 4 + rng.random() * 3
        pts.append(cp((x, y, z), 3.6, "pole", label=f"POLE {i + 1}"))
    return pts


def build_altitude_ace(rng):
    targets = [18, 36, 55, 34, 70]
    return [cp((0.0, y, 20.0), 4.0, "altitude", hold=2.0, label=f"{y:.0f} m") for y in targets]


def build_precision_landing(rng):
    return [cp((26.0, 0.0, 60.0), 4.5, "land", hold=1.4, label="LANDING PAD")]


def build_generated(m, rng):
    """Lay out a course from a missions.py mission dict (see launcher.py).

    Everything the briefing promised comes from here: the checkpoint count and radius, the
    shape of the course and the hold time. Wind, battery and the clock ride on the MISSIONS
    entry that wraps this builder.
    """
    p = m["params"]
    n, r, hold = int(p["gates"]), float(p["gate_r"]), float(p["hold"])
    course = m["course"]
    pts = []
    if course in ("gate_rush", "grand_tour"):
        x, z, y = 0.0, 20.0, 12.0
        ang = 0.0
        spread = 1.6 if course == "gate_rush" else 2.1      # the tour wanders much wider
        for i in range(n):
            ang += (rng.random() - 0.5) * spread
            step = (22 if course == "gate_rush" else 30) + rng.random() * 12
            x += math.sin(ang) * step
            z += math.cos(ang) * step
            y = clampv(y + (rng.random() - 0.5) * 16, 6, 70)
            pts.append(cp((x, y, z), r, "gate", label="GATE %d" % (i + 1)))
        if p.get("tour_landing"):
            last = pts[-1]["pos"] if pts else np.array([0.0, 0.0, 20.0])
            pts.append(cp((last[0] + 18, 0.0, last[2] + 18), max(4.0, r), "land",
                          hold=1.4, label="LANDING PAD"))
    elif course == "slalom":
        z, side = 18.0, 1
        for i in range(n):
            z += 12 + rng.random() * 3
            x = side * (8 + rng.random() * 3) + 40
            side *= -1
            pts.append(cp((x, 4 + rng.random() * 3, z), r, "pole", label="POLE %d" % (i + 1)))
    elif course == "altitude":
        y = 16.0
        for i in range(n):
            y += 11 + rng.random() * 10
            pts.append(cp((rng.uniform(-14, 14), y, 20.0 + rng.uniform(-10, 10)), r,
                          "altitude", hold=hold, label="%.0f m" % y))
    elif course == "landing":
        a = rng.uniform(0, math.tau)
        d = 60 + rng.random() * 70                          # a real crossing, not a hop
        pts.append(cp((math.sin(a) * d, 0.0, 20 + math.cos(a) * d), r, "land",
                      hold=hold, label="LANDING PAD"))
    return pts


def mission_from_file(path):
    """Turn a launcher mission.json into a MISSIONS entry the game can load."""
    with open(path) as f:
        m = json.load(f)
    p = m["params"]
    colors = {"gate_rush": (0.10, 0.95, 1.00), "slalom": (1.00, 0.75, 0.10),
              "altitude": (0.75, 0.50, 1.00), "landing": (0.20, 1.00, 0.45),
              "delivery": (1.00, 0.45, 0.25), "grand_tour": (1.00, 0.30, 0.55)}
    entry = {
        "id": m["code"],
        "name": m["name"].upper(),
        "color": colors.get(m["course"], (1.0, 1.0, 1.0)),
        "time_limit": int(m["time_limit"]),
        "desc": m["brief"],
        "builder": lambda rng, _m=m: build_generated(_m, rng),
        "wind": float(p["wind"]),
        "gust_scale": float(p["gust"]),
        "drain": float(p["drain"]),
        "recharge": int(p["recharge"]),
        "battery": float(p["battery"]),
        "heavy": bool(p.get("heavy")),
        "generated": m,
    }
    if m["course"] == "delivery":
        entry["delivery"] = True
    return entry


# wind: m/s of breeze (gusts on top) - drain: battery % per second at hover - recharge: % per checkpoint
MISSIONS = [
    {"id": "free_flight", "name": "FREE FLIGHT", "color": (1.00, 1.00, 1.00), "time_limit": 0,
     "desc": "Training. No clock, no battery, calm air. Learn the sticks.", "builder": lambda rng: [],
     "wind": 0.0, "drain": 0.0, "recharge": 0},
    {"id": "ring_rush", "name": "RING RUSH", "color": (0.10, 0.95, 1.00), "time_limit": 70,
     "desc": "10 gates, 70 seconds. Clip a gate's edge and it costs you.", "builder": build_ring_rush,
     "wind": 2.0, "drain": 0.9, "recharge": 7},
    {"id": "slalom", "name": "SLALOM SPRINT", "color": (1.00, 0.75, 0.10), "time_limit": 45,
     "desc": "Pass inside the circle of 14 poles. Low, fast, no wobble.", "builder": build_slalom,
     "wind": 3.0, "drain": 1.0, "recharge": 5},
    {"id": "altitude_ace", "name": "ALTITUDE ACE", "color": (0.75, 0.50, 1.00), "time_limit": 80,
     "desc": "Hover inside 5 rings for 2 s each while the gusts shove you.", "builder": build_altitude_ace,
     "wind": 4.5, "drain": 1.1, "recharge": 10},
    {"id": "precision_landing", "name": "PRECISION LANDING", "color": (0.20, 1.00, 0.45), "time_limit": 40,
     "desc": "Set down soft and centred on a distant pad in a crosswind.", "builder": build_precision_landing,
     "wind": 5.0, "drain": 1.3, "recharge": 0},
    {"id": "delivery", "name": "DELIVERY RUN", "color": (1.00, 0.45, 0.25), "time_limit": 120,
     "desc": "Rooftop courier: land to pick up, land to drop. Parcels are heavy.", "builder": lambda rng: [],
     "wind": 6.0, "drain": 1.25, "recharge": 12, "delivery": True},
    {"id": "storm_rush", "name": "STORM RUSH", "color": (1.00, 0.30, 0.55), "time_limit": 60,
     "desc": "The final exam: a gate course through a gale. Good luck.", "builder": build_ring_rush,
     "wind": 9.0, "drain": 1.35, "recharge": 6},
]



# =====================================================================
#  Drone physics
# =====================================================================
class Drone:
    def __init__(self):
        self.reset()

    def reset(self, pos=(0.0, 0.3, -4.0), yaw=0.0):
        self.pos = np.array(pos, dtype=float)
        self.vel = np.zeros(3)
        self.yaw = yaw
        self.pitch_tilt = 0.0
        self.roll_tilt = 0.0
        self.alive = True
        self.landed = True
        self.prop = 0.0
        self.thr = 0.0

    def update(self, dt, throttle_in, yaw_in, pitch_in, roll_in, tilt=MAX_TILT, thr_range=THROTTLE_RANGE,
               yaw_rate=YAW_RATE, wind=None, weight=0.0):
        k = clampv(dt * TILT_RESPONSE, 0, 1)
        self.pitch_tilt = lerp(self.pitch_tilt, pitch_in * tilt, k)
        self.roll_tilt = lerp(self.roll_tilt, roll_in * tilt, k)
        self.yaw += yaw_in * yaw_rate * dt
        self.thr = throttle_in
        thrust = G + throttle_in * thr_range
        vertical = thrust * math.cos(self.pitch_tilt) * math.cos(self.roll_tilt)
        forward = thrust * math.sin(self.pitch_tilt)
        lateral = thrust * math.sin(self.roll_tilt)
        acc = WORLD_UP * (vertical - G - weight) + heading_vec(self.yaw) * forward + right_vec(self.yaw) * lateral
        if wind is not None:
            acc = acc + wind
        self.vel += acc * dt
        dh = DRAG_H + (C["assist"] if abs(pitch_in) < 0.1 and abs(roll_in) < 0.1 else 0.0)
        dv = DRAG_V + (C["alt_hold"] if abs(throttle_in) < 0.1 else 0.0)
        self.vel[0] *= max(0.0, 1 - dh * dt)
        self.vel[2] *= max(0.0, 1 - dh * dt)
        self.vel[1] *= max(0.0, 1 - dv * dt)
        self.pos += self.vel * dt
        if self.pos[1] > CEILING:
            self.pos[1], self.vel[1] = CEILING, min(0.0, self.vel[1])
        self.prop += dt * (40 + 30 * throttle_in)

    @property
    def speed(self):
        return float(np.linalg.norm(self.vel))


# =====================================================================
#  Game
# =====================================================================
class Game:
    def __init__(self):
        pygame.init()
        flags = pygame.FULLSCREEN if C["fullscreen"] else 0
        self.screen = pygame.display.set_mode(C["window_size"], flags)
        pygame.display.set_caption("DRONE SIM")
        self.clock = pygame.time.Clock()
        self.RW, self.RH = self.screen.get_size()
        self.tanx = math.tan(math.radians(C["fov_degrees"]) / 2)
        self.F = (self.RW / 2) / self.tanx
        self.mission_path = arg_value("--mission")
        self.result_path = arg_value("--result")
        self.udp_port = int(arg_value("--pad-udp") or 0)
        self.result_written = False
        self.sfx = Sfx(C["sound"])
        self.f_big = pygame.font.SysFont("bahnschrift,segoe ui,arial", 64, bold=True)
        self.f_med = pygame.font.SysFont("bahnschrift,segoe ui,arial", 30, bold=True)
        self.f_sm = pygame.font.SysFont("bahnschrift,segoe ui,arial", 19)
        self.f_xs = pygame.font.SysFont("bahnschrift,segoe ui,arial", 15)
        self.hi_path = os.path.join(HERE, "highscore.json")
        self.hi = self._load_hi()
        self.state = "title"
        self.mission_i = 0
        self.T = 0.0
        # sky / ground layer
        self.set_sky_res(C["sky_res"])
        self.ft_avg = 0.0
        self.ft_n = 0
        self.tex, self.tex_far, self.macro, self.clouds = make_ground_textures()
        self.tex_flat = np.ascontiguousarray(self.tex.reshape(-1, 3))
        self.tex_far_flat = np.ascontiguousarray(self.tex_far.reshape(-1, 3))
        self.macro_flat = np.ascontiguousarray(self.macro.ravel())
        self.shadow_layer = pygame.Surface((self.RW, self.RH))
        self.shadow_layer.set_colorkey((255, 0, 255))
        self.shadow_layer.set_alpha(85)
        # input
        self.pad = None
        pygame.joystick.init()
        if pygame.joystick.get_count():
            self._open_pad(0)
        if "--serial" in sys.argv:
            C["arduino"]["port"] = sys.argv[sys.argv.index("--serial") + 1]
        # launcher.py owns the pads and streams them over UDP; on our own we read the cable
        if self.udp_port:
            self.ser = UdpPad(self.udp_port, copilot="--no-copilot" not in sys.argv)
        else:
            self.ser = SerialPad(C["arduino"]) if C["arduino"]["enabled"] else None
        self.ser_seen = False
        self.clicks, self.holding = {}, {}
        self.click_prev = [False, False]
        self.combo_armed = True
        self.menu_dir = 0
        self.mouse_stick = [0.0, 0.0]
        self.cam_mode = 0                 # 0 chase, 1 FPV, 2 cinematic
        self.popups = []
        self.particles = []
        self.shake = 0.0
        self.flash = 0.0
        self.warn_t = 0.0
        self.warning = ""
        self.load_mission(0)
        mid = arg_value("--mission-id")
        if mid:
            ids = [m["id"] for m in MISSIONS]
            if mid in ids:
                self.load_mission(ids.index(mid))
                self.state = "briefing"
            else:
                print("unknown mission id %r - expected one of %s" % (mid, ", ".join(ids)))
                self.write_result(False, "unknown mission %s" % mid)
                raise SystemExit(1)
        # a mission handed to us by the launcher: build it and open its briefing straight away
        if self.mission_path:
            try:
                MISSIONS.append(mission_from_file(self.mission_path))
                self.load_mission(len(MISSIONS) - 1)
                self.state = "briefing"
            except Exception as e:
                print("could not load %s: %s" % (self.mission_path, e))
                self.write_result(False, "mission file unreadable")
                raise SystemExit(1)

    def set_sky_res(self, res):
        self.GW, self.GH = int(res[0]), int(res[1])
        xs = ((np.arange(self.GW) + 0.5) / self.GW * 2 - 1) * self.tanx
        ys = (1 - (np.arange(self.GH) + 0.5) / self.GH * 2) * self.tanx * self.RH / self.RW
        self.PX = xs[None, :].astype(np.float32)
        self.PY = ys[:, None].astype(np.float32)

    def auto_quality(self, frame_ms):
        """Every ~2 s: drop the sky/ground resolution if slow, raise it back if there's headroom."""
        if not C["auto_quality"]:
            return
        self.ft_avg += frame_ms
        self.ft_n += 1
        if self.ft_n < 60:
            return
        avg = self.ft_avg / self.ft_n
        self.ft_avg, self.ft_n = 0.0, 0
        w = self.GW
        if avg > 36 and w > 240:
            w = max(240, int(w * 0.85))
        elif avg < 22 and w < C["sky_res"][0]:
            w = min(C["sky_res"][0], int(w * 1.15) + 1)
        if w != self.GW:
            self.set_sky_res((w, round(w * self.RH / self.RW)))

    # ------------------------------------------------------------ highscore
    def _load_hi(self):
        try:
            with open(self.hi_path) as f:
                return json.load(f)
        except Exception:
            return {}

    def _save_hi(self):
        try:
            with open(self.hi_path, "w") as f:
                json.dump(self.hi, f)
        except Exception:
            pass

    # ------------------------------------------------------------ input
    def _open_pad(self, i):
        try:
            self.pad = pygame.joystick.Joystick(i)
        except pygame.error:
            self.pad = None

    def _pad_axis(self, n):
        try:
            if self.pad and 0 <= n < self.pad.get_numaxes():
                v = self.pad.get_axis(n)
                dz = C["gamepad"]["deadzone"]
                return 0.0 if abs(v) < dz else (abs(v) - dz) / (1 - dz) * (1 if v > 0 else -1)
        except pygame.error:
            pass
        return 0.0

    def _pad_button(self, n):
        try:
            return bool(self.pad and 0 <= n < self.pad.get_numbuttons() and self.pad.get_button(n))
        except pygame.error:
            return False

    def stick(self, name):
        """lx / ly / rx / ry in -1..1 (right = +, down = +). USB pad and Arduino combined."""
        g, ar = C["gamepad"], C["arduino"]
        v = self._pad_axis(g[name]) * (-1 if g["invert_" + name] else 1)
        sp = self.ser
        if sp and sp.ready:
            if sp.n_axes == 2:
                a = sp.axis({"lx": 0, "ly": 1}[name]) if name in ("lx", "ly") else 0.0
            else:
                n = name
                if ar["swap_sticks"]:
                    n = {"l": "r", "r": "l"}[n[0]] + n[1]
                a = sp.axis({"lx": 0, "ly": 1, "rx": 2, "ry": 3}[n])
            a *= -1 if ar["invert_" + name] else 1
            if abs(a) > abs(v):
                v = a
        return v

    def click_states(self):
        g = C["gamepad"]
        cur = [self._pad_button(g["btn_left"]), self._pad_button(g["btn_right"])]
        sp = self.ser
        if sp and sp.ready:
            nb = sp.num_buttons()
            if sp.n_axes == 2:
                cur[1] = cur[1] or (nb > 0 and sp.button(0))
            else:
                cur[0] = cur[0] or (nb > 0 and sp.button(0))
                cur[1] = cur[1] or (nb > 1 and sp.button(1))
        return cur

    def one_stick(self):
        return bool(self.ser and self.ser.ready and self.ser.n_axes == 2 and not self.pad)

    def left_only(self):
        return bool(C.get("left_only")) and bool(self.ser and self.ser.ready)

    def held(self, action):
        return action in self.holding.values()

    def poll_pad(self):
        sp = self.ser
        if sp and sp.ready and not self.ser_seen:
            self.ser_seen = True
            self.sfx.play("pad")
            self.popup(f"ARDUINO PAD {sp.status.upper()}", (0.6, 0.85, 1.0))
        elif sp and self.ser_seen and not sp.ready:
            self.ser_seen = False
            self.popup("ARDUINO PAD DISCONNECTED", (1.0, 0.5, 0.4))
        cur = self.click_states()
        prev, self.click_prev = self.click_prev, cur
        now = time.time()
        if cur[0] and cur[1]:
            if self.combo_armed:
                self.combo_armed = False
                self.clicks.clear()
                self.release_holds()
                self.on_action("both")
        elif not self.combo_armed:
            if not any(cur):
                self.combo_armed = True
        elif self.left_only() and self.state in ("play", "countdown"):
            pass                  # clicks are climb / descend while flying (see get_controls)
        else:
            clicks = {1: C["single_click"]} if self.one_stick() else C["clicks"]
            for i, g in clicks.items():
                self._click(i, g, cur[i], prev[i], now)
        # menus: either stick up/down (or left/right) = move selection
        if self.state in ("title",):
            y = self.stick("ly") or self.stick("ry")
            x = self.stick("lx") or self.stick("rx")
            v = y if abs(y) >= abs(x) else x
            d = 1 if v > 0.6 else -1 if v < -0.6 else 0
            if d and d != self.menu_dir:
                self.select_mission(self.mission_i + d)
            self.menu_dir = d

    def release_holds(self):
        for act in list(self.holding.values()):
            self.on_action(act + "_end")
        self.holding.clear()

    def _click(self, i, g, down, was, now):
        st = self.clicks.get(i)
        if down and not was:
            if st and st[2] and now - st[2] < C["double_time"]:
                st[0], st[1] = now, st[1] + 1
            else:
                self.clicks[i] = [now, 1, 0.0]
        elif down and st and i not in self.holding and st[1] == 1 and now - st[0] >= C["hold_time"]:
            self.holding[i] = g["hold"]
            self.on_action(g["hold"], i)
        elif not down and was and st:
            act = self.holding.pop(i, None)
            if act:
                self.clicks.pop(i, None)
                self.on_action(act + "_end", i)
            elif st[1] >= 2:
                self.clicks.pop(i, None)
                self.on_action(g["double"], i)
            else:
                st[2] = now
        elif not down and st and st[2] and now - st[2] >= C["double_time"]:
            self.clicks.pop(i, None)
            self.on_action(g["tap"], i)

    def on_action(self, act, click=None):
        """A stick-click gesture. In menus: right click = confirm, left click = back / next."""
        s = self.state
        if s in ("title", "briefing", "done", "pause"):
            if act.endswith("_end"):
                return
            confirm = click == 1 or act == "both"
            if s == "title":
                self.key(pygame.K_RETURN if confirm else pygame.K_DOWN)
            elif s == "briefing":
                self.key(pygame.K_RETURN if confirm else pygame.K_ESCAPE)
            elif s == "done":
                self.key(pygame.K_RETURN if confirm else pygame.K_ESCAPE)
            elif s == "pause":
                self.key(pygame.K_ESCAPE if confirm else pygame.K_q)
            return
        if s != "play" and s != "countdown":
            return
        if act in ("pause", "both"):
            self.key(pygame.K_ESCAPE)
        elif act == "camera":
            self.cycle_camera()
        elif act == "restart":
            self.restart()
        elif act == "stabilize":
            self.stabilize()
        elif act == "turbo":
            self.sfx.play("turbo_on")
            self.popup("TURBO", (1.0, 0.7, 0.3))
        elif act == "turbo_end":
            self.sfx.play("turbo_off")
        elif act == "precision":
            self.sfx.play("prec_on")
            self.popup("PRECISION", (1.0, 1.0, 0.6))
        elif act == "precision_end":
            self.sfx.play("prec_off")
        elif act == "forward":
            self.sfx.play("turbo_on", 0.5)

    def key(self, k):
        self.handle(pygame.event.Event(pygame.KEYDOWN, key=k))

    def get_controls(self):
        """throttle, yaw, pitch, roll in -1..1"""
        keys = pygame.key.get_pressed()
        thr = float(keys[pygame.K_SPACE] or keys[pygame.K_UP]) - float(keys[pygame.K_LSHIFT] or keys[pygame.K_DOWN])
        yaw = float(keys[pygame.K_RIGHT] or keys[pygame.K_e]) - float(keys[pygame.K_LEFT] or keys[pygame.K_q])
        pit = float(keys[pygame.K_w]) - float(keys[pygame.K_s])
        rol = float(keys[pygame.K_d]) - float(keys[pygame.K_a])
        # touchpad / mouse: drag builds a spring-loaded virtual stick for pitch + roll
        mx, my = pygame.mouse.get_rel()
        if pygame.mouse.get_focused():
            self.mouse_stick[0] = clampv(self.mouse_stick[0] * 0.9 + mx * 0.006, -1, 1)
            self.mouse_stick[1] = clampv(self.mouse_stick[1] * 0.9 + my * 0.006, -1, 1)
            if abs(self.mouse_stick[0]) > 0.05:
                rol += self.mouse_stick[0]
            if abs(self.mouse_stick[1]) > 0.05:
                pit -= self.mouse_stick[1]
            b = pygame.mouse.get_pressed(3)
            thr += b[0] - b[2]
        if self.left_only():
            fwd, turn = -self.stick("ly"), self.stick("lx")
            cl = self.click_states()
            pit += fwd
            yaw += turn
            rol += turn * max(0.0, fwd) * 0.35       # bank into turns while flying forward
            climb = float(cl[1]) - float(cl[0])    # right click climbs, left click descends
            d = getattr(self, "drone", None)
            if climb or d is None:
                thr += climb
                self.alt_target = None
            else:                                  # autopilot: keep the height you let go at
                if getattr(self, "alt_target", None) is None:
                    self.alt_target = float(d.pos[1])
                thr += clampv((self.alt_target - d.pos[1]) * 0.8 - d.vel[1] * 0.6, -1, 1)
        elif self.one_stick():
            thr -= self.stick("ly")
            yaw += self.stick("lx")
            if self.held("forward"):
                pit += 0.7
        else:
            thr -= self.stick("ly")
            yaw += self.stick("lx")
            pit -= self.stick("ry")
            rol += self.stick("rx")
        return tuple(clampv(v, -1, 1) for v in (thr, yaw, pit, rol))

    # ------------------------------------------------------------ mission setup
    def select_mission(self, i):
        self.load_mission(i)
        self.sfx.play("tick")

    def load_mission(self, i):
        self.mission_i = i % len(MISSIONS)
        m = MISSIONS[self.mission_i]
        rng = random.Random(sum(map(ord, m["id"])))
        self.checkpoints = m["builder"](rng)
        avoid = [(0, -4, 14)] + [(c["pos"][0], c["pos"][2], c["r"] + 7) for c in self.checkpoints]
        for a, b in zip(self.checkpoints, self.checkpoints[1:]):      # keep the flight line clear
            for t in (0.25, 0.5, 0.75):
                p = a["pos"] + (b["pos"] - a["pos"]) * t
                avoid.append((p[0], p[2], 6))
        wr = random.Random(99)                         # the city is the same for every mission
        self.buildings = [b for b in make_buildings(wr, 90, 250, [(0, -4, 16)])
                          if all((b["x"] - ax) ** 2 + (b["z"] - az) ** 2 > (ar + max(b["w"], b["d"]) / 2) ** 2
                                 for ax, az, ar in avoid)]
        if m.get("delivery"):
            self.checkpoints = self.make_deliveries(rng)
        self.trees = make_trees(random.Random(7), C["trees"], 250, self.buildings, avoid)
        for b in self.buildings:                      # shadows never move: work them out once
            top = b["pts"][4:] - SUN * (b["h"] / SUN[1])
            b["shadow"] = self._hull(np.vstack([b["pts"][:4], top]))
            b["centre"] = np.array([b["x"], b["h"] / 2, b["z"]])
            b["radius"] = math.sqrt(b["w"] ** 2 + b["d"] ** 2 + b["h"] ** 2) / 2
        self.ready_run()

    def make_deliveries(self, rng):
        """4 rooftop stops: pickup, drop, pickup, drop - each further out."""
        cands = [b for b in self.buildings if 10 < b["h"] < 45 and min(b["w"], b["d"]) >= 7.5
                 and 25 < math.hypot(b["x"], b["z"]) < 190]
        rng.shuffle(cands)
        stops, used = [], []
        for b in sorted(cands[:12], key=lambda b: math.hypot(b["x"], b["z"])):
            if all(math.hypot(b["x"] - u["x"], b["z"] - u["z"]) > 45 for u in used):
                used.append(b)
            if len(used) == 4:
                break
        labels = ["PICKUP 1", "DROP 1", "PICKUP 2", "DROP 2"]
        for i, b in enumerate(used):
            b["pad_i"] = i
            stops.append(cp((b["x"], b["h"], b["z"]), min(b["w"], b["d"]) / 2 - 0.8, "land", hold=1.0,
                            label=labels[i]))
        return stops

    def unlocked(self, i):
        if C["unlock_all"] or i <= 1:
            return True
        return self.hi.get(MISSIONS[i - 1]["id"], {}).get("stars", 0) >= 1

    def total_stars(self):
        return sum(v.get("stars", 0) for v in self.hi.values() if isinstance(v, dict))

    def ready_run(self):
        self.drone = Drone()
        self.cp_i = 0
        self.hold_t = 0.0
        self.elapsed = 0.0
        self.combo = 0
        self.score = 0
        self.time_left = MISSIONS[self.mission_i]["time_limit"]
        self.result = None
        self.popups = []
        self.particles = []
        self.mouse_stick = [0.0, 0.0]
        self.done_t = 0.0
        self.count_t = 0.0
        self.cam_pos = self.drone.pos - heading_vec(0) * 8 + WORLD_UP * 3
        self.cam_R = basis(0, -0.2, 0)
        self.cam_yaw = self.drone.yaw
        self.new_best = False
        self.stars = 0
        self.battery = float(MISSIONS[self.mission_i].get("battery", 100.0))
        self.bat_warn_t = 0.0
        self.bat_empty = False
        self.carrying = False
        self.clips = 0
        m = MISSIONS[self.mission_i]
        self.wind_base = m["wind"] * C["wind_scale"]
        self.wind_dir = random.uniform(0, math.tau)
        self.wind = np.zeros(3)
        self.gusting = False
        for c in self.checkpoints:
            c["clipped"] = False

    def start_mission(self):
        self.ready_run()
        self.state = "countdown"
        self.count_t = 0.0
        self.last_count = 4
        pygame.mouse.get_rel()
        self.sfx.play("start")

    def restart(self):
        self.sfx.play("restart")
        self.release_holds()
        self.start_mission()

    # ------------------------------------------------------------ events
    def handle(self, e):
        if e.type == pygame.QUIT:
            self.quit()
        if e.type == pygame.JOYDEVICEADDED and self.pad is None:
            self._open_pad(e.device_index)
            self.sfx.play("pad")
        if e.type == pygame.JOYDEVICEREMOVED:
            self.pad = None
        if e.type == pygame.WINDOWFOCUSLOST and self.state == "play":
            self.set_pause(True)
        if e.type != pygame.KEYDOWN:
            return
        k = e.key
        if k == pygame.K_F11:
            pygame.display.toggle_fullscreen()
            return
        if k == pygame.K_F12:
            pygame.image.save(self.screen, os.path.join(HERE, f"shot_{pygame.time.get_ticks()}.png"))
            self.sfx.play("camera")
            return
        s = self.state
        if s == "title":
            if k in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_KP_ENTER):
                if self.unlocked(self.mission_i):
                    self.state = "briefing"
                    self.sfx.play("confirm")
                else:
                    self.sfx.play("deny")
                    self.popup(f"LOCKED - finish {MISSIONS[self.mission_i - 1]['name']} first", (1.0, 0.5, 0.4))
            elif k in (pygame.K_UP, pygame.K_w, pygame.K_LEFT):
                self.select_mission(self.mission_i - 1)
            elif k in (pygame.K_DOWN, pygame.K_s, pygame.K_RIGHT):
                self.select_mission(self.mission_i + 1)
            elif k == pygame.K_ESCAPE:
                self.quit()
        elif s == "briefing":
            if k in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_KP_ENTER):
                self.start_mission()
            elif k == pygame.K_ESCAPE:
                self.state = "title"
                self.sfx.play("back")
        elif s in ("play", "countdown"):
            if k in (pygame.K_ESCAPE, pygame.K_p):
                self.set_pause(True)
            elif k == pygame.K_r:
                self.restart()
            elif k == pygame.K_l:
                self.stabilize()
            elif k == pygame.K_c:
                self.cycle_camera()
            elif k == pygame.K_TAB:
                self.on_action("turbo")
            elif k == pygame.K_x:
                self.on_action("precision")
        elif s == "pause":
            if k in (pygame.K_ESCAPE, pygame.K_p, pygame.K_SPACE, pygame.K_RETURN):
                self.set_pause(False)
            elif k == pygame.K_q:
                self.to_title()
        elif s == "done":
            if k in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_r):
                self.start_mission()
            elif k == pygame.K_ESCAPE:
                self.to_title()

    def set_pause(self, on):
        if on and self.state in ("play", "countdown"):
            self.paused_from = self.state
            self.state = "pause"
            self.sfx.play("pause")
            self.release_holds()
        elif not on and self.state == "pause":
            self.state = getattr(self, "paused_from", "play")
            self.sfx.play("resume")
            pygame.mouse.get_rel()

    def to_title(self):
        self.sfx.play("back")
        self.release_holds()
        self.ready_run()
        self.state = "title"

    def write_result(self, win, reason):
        """Leave the outcome where launcher.py can find it. Only ever written once."""
        if not self.result_path or self.result_written:
            return
        self.result_written = True
        m = MISSIONS[self.mission_i] if 0 <= self.mission_i < len(MISSIONS) else {}
        try:
            os.makedirs(os.path.dirname(os.path.abspath(self.result_path)), exist_ok=True)
            with open(self.result_path, "w") as f:
                json.dump({
                    "win": bool(win),
                    "reason": reason,
                    "mission": m.get("id", ""),
                    "stars": int(getattr(self, "stars", 0) or 0),
                    "score": int(getattr(self, "score", 0) or 0),
                    "time": round(float(getattr(self, "elapsed", 0.0)), 1),
                    "time_left": round(float(getattr(self, "time_left", 0) or 0), 1),
                    "battery": round(float(getattr(self, "battery", 0.0)), 1),
                    "checkpoints": int(getattr(self, "cp_i", 0)),
                    "total_checkpoints": len(getattr(self, "checkpoints", []) or []),
                    "clips": int(getattr(self, "clips", 0)),
                }, f, indent=2)
        except Exception as e:
            print("could not write result (%s)" % e)

    def quit(self):
        # closing the window mid-run counts as an abort, so the launcher never hangs waiting
        if not self.result_written:
            r = getattr(self, "result", None)
            self.write_result(r == "win", {"win": "Mission complete", "crash": "Crashed",
                                           "timeout": "Out of time"}.get(r, "Closed before the end"))
        pygame.quit()
        sys.exit()

    def cycle_camera(self):
        self.cam_mode = (self.cam_mode + 1) % 3
        self.sfx.play("camera")
        self.popup(["CHASE CAM", "FPV CAM", "CINEMATIC CAM"][self.cam_mode], (0.7, 0.85, 1.0))

    def stabilize(self):
        d = self.drone
        d.pitch_tilt = d.roll_tilt = 0.0
        d.vel *= 0.3
        self.flash = 0.35
        self.sfx.play("stabilize")
        self.popup("STABILIZED", (0.6, 1.0, 0.7))

    def popup(self, text, col):
        self.popups.append([1.4, text, col])

    # ------------------------------------------------------------ update
    def update(self, dt):
        dt = min(dt, 0.033)
        self.T += dt
        self.shake = max(0.0, self.shake - dt * 2.5)
        self.flash = max(0.0, self.flash - dt)
        for p in self.popups:
            p[0] -= dt
        self.popups = [p for p in self.popups if p[0] > 0]
        self.poll_pad()
        self.update_particles(dt)
        d = self.drone
        if self.state == "title" or self.state == "briefing":
            d.pos[:] = (0.0, 6 + math.sin(self.T * 0.8) * 0.6, -4.0)
            d.yaw = self.T * 0.15
            d.prop += dt * 45
            d.landed = False
            self.sfx.stop_engine()
            self.update_camera(dt, orbit=True)
            return
        if self.state == "pause":
            self.sfx.engine(0, 0, on=False)
            return
        if self.state == "countdown":
            self.count_t += dt
            n = 3 - int(self.count_t / 0.8)
            if n != self.last_count:
                self.last_count = n
                self.sfx.play("go" if n <= 0 else "count")
                if n <= 0:
                    self.state = "play"
            d.prop += dt * 30
            self.sfx.engine(0.2, 0.0)
            self.update_camera(dt)
            return
        if self.state == "done":
            self.done_t += dt
            if d.alive:
                d.vel *= max(0.0, 1 - dt * 2)
                d.pos += d.vel * dt
                d.prop += dt * 20
            self.sfx.engine(0.15, 0, on=d.alive)
            self.update_camera(dt)
            return
        thr, yaw, pit, rol = self.get_controls()
        tilt, trange, yrate = MAX_TILT, THROTTLE_RANGE, YAW_RATE
        if self.held("turbo") or pygame.key.get_pressed()[pygame.K_TAB]:
            tilt, trange, yrate = MAX_TILT * 1.4, THROTTLE_RANGE * 1.35, YAW_RATE * 1.25
        if self.held("precision") or pygame.key.get_pressed()[pygame.K_x]:
            tilt, trange, yrate = MAX_TILT * 0.45, THROTTLE_RANGE * 0.55, YAW_RATE * 0.5
        was_landed = d.landed
        if d.landed and thr <= 0.05:
            d.vel[:] = 0
            d.pitch_tilt *= 0.8
            d.roll_tilt *= 0.8
            d.yaw += yaw * yrate * dt * 0.5
            d.prop += dt * (20 + 20 * max(thr, 0))
        else:
            d.landed = False
            if self.bat_empty:
                thr = min(thr, -0.75)
            weight = (3.0 if self.carrying else 0.0) + (1.5 if m_heavy(self) else 0.0)
            d.update(dt, thr, yaw, pit, rol, tilt, trange, yrate, self.wind, weight)
        self.elapsed += dt
        m = MISSIONS[self.mission_i]
        self.update_wind(dt)
        # battery
        if m["drain"] > 0 and C["battery_scale"] > 0:
            load = 0.2 if d.landed else 0.8 + 1.4 * max(thr, 0) + 0.8 * (abs(pit) + abs(rol)) / 2
            if self.carrying:
                load *= 1.3
            self.battery = max(0.0, self.battery - dt * m["drain"] * C["battery_scale"] * load)
            self.bat_warn_t -= dt
            if 0 < self.battery < 25 and self.bat_warn_t <= 0:
                self.sfx.play("lowbat", 0.8)
                self.bat_warn_t = 2.2 if self.battery > 12 else 1.0
            if self.battery <= 0 and not self.bat_empty:
                self.bat_empty = True
                self.sfx.play("empty")
                self.popup("BATTERY EMPTY - GOING DOWN", (1.0, 0.4, 0.3))
        if m["time_limit"] > 0:
            prev = self.time_left
            self.time_left -= dt
            if self.time_left < 10 and int(prev) != int(self.time_left):
                self.sfx.play("tick", 0.8)
        self.sfx.engine(clampv((thr + 1) / 2, 0, 1) if not d.landed else 0.05, d.speed / 30)
        # prop wash dust
        if d.pos[1] < 5 and not d.landed and random.random() < 0.8:
            a = random.random() * math.tau
            p = np.array([d.pos[0] + math.cos(a) * 0.8, 0.05, d.pos[2] + math.sin(a) * 0.8])
            v = np.array([math.cos(a) * 5, 0.6, math.sin(a) * 5]) * (1.2 - d.pos[1] / 5)
            self.particles.append([p, v, 0.9, (190, 175, 140), 0.5, "dust"])
        # ground / buildings / trees
        crashed = False
        floor = self.floor_at(d.pos)
        if d.pos[1] <= floor + 0.25 and not d.landed:
            soft = d.vel[1] > -5.0 and math.hypot(d.vel[0], d.vel[2]) < 4.0
            if soft:
                d.pos[1] = floor + 0.25
                d.vel[:] = 0
                d.landed = True
                if not was_landed:
                    self.sfx.play("touchdown")
            else:
                crashed = True
        if self.hits_world(d.pos, 0.55):
            crashed = True
        if self.bat_empty and d.landed and d.alive and self.result is None:
            self.finish("battery")
            self.sfx.play("fail")
            return
        if crashed and d.alive:
            self.crash()
            return
        # proximity warning
        self.warning = ""
        self.warn_t -= dt
        v = d.vel
        if np.linalg.norm(v) > 3:
            for t in (0.35, 0.7, 1.1):
                p = d.pos + v * t
                if self.hits_world(p, 0.8) or (p[1] < 0.2 and v[1] < -5):
                    self.warning = "PULL UP" if p[1] < 0.5 else "OBSTACLE"
                    if self.warn_t <= 0:
                        self.sfx.play("warn", 0.7)
                        self.warn_t = 0.55
                    break
        self.update_checkpoints(dt)
        if m["time_limit"] > 0 and self.time_left <= 0 and self.result is None:
            self.finish("lose")
            self.sfx.play("fail")
        self.update_camera(dt)

    def floor_at(self, p):
        """Height you can land on here: the ground, or a rooftop."""
        for b in self.buildings:
            if abs(p[0] - b["x"]) < b["w"] / 2 and abs(p[2] - b["z"]) < b["d"] / 2 and p[1] > b["h"] - 0.3:
                return b["h"]
        return GROUND_Y

    def update_wind(self, dt):
        """A breeze that slowly swings round, plus gusts that come and go."""
        base = self.wind_base
        if base <= 0:
            self.wind[:] = 0
            return
        T = self.elapsed
        self.wind_dir += dt * 0.05 * math.sin(T * 0.13)
        gust = (max(0.0, math.sin(T * 0.45) * math.sin(T * 0.23 + 1.7)) * 1.6
                * MISSIONS[self.mission_i].get("gust_scale", 1.0))
        strength = base * (0.55 + 0.15 * math.sin(T * 1.3) + gust)
        alt_k = 0.6 + 0.4 * clampv(self.drone.pos[1] / 40, 0, 1.5)     # windier higher up
        w = np.array([math.sin(self.wind_dir), 0.0, math.cos(self.wind_dir)]) * strength * alt_k * 0.45
        self.wind = w
        g = gust > 0.8
        if g and not self.gusting:
            self.sfx.play("gust", min(1.0, base / 8))
            if base >= 4:
                self.popup("GUST!", (0.7, 0.85, 1.0))
        self.gusting = g

    def hits_world(self, p, r):
        for b in self.buildings:
            if abs(p[0] - b["x"]) < b["w"] / 2 + r and abs(p[2] - b["z"]) < b["d"] / 2 + r and p[1] < b["h"] - 0.05:
                return True
        if len(self.trees):
            t = self.trees
            dd = (t[:, 0] - p[0]) ** 2 + (t[:, 1] - p[2]) ** 2
            hit = (dd < (t[:, 3] * 0.8 + r) ** 2) & (p[1] < t[:, 2])
            if hit.any():
                return True
        return False

    def crash(self):
        d = self.drone
        d.alive = False
        self.shake = 1.0
        self.flash = 0.6
        self.sfx.play("crash")
        for _ in range(70):
            v = np.random.randn(3) * 6 + d.vel * 0.3 + np.array([0, 4, 0])
            kind = random.choice(["spark", "spark", "debris", "smoke"])
            col = {"spark": (255, 190, 90), "debris": (40, 40, 46), "smoke": (90, 90, 95)}[kind]
            size = {"spark": 0.12, "debris": 0.2, "smoke": 0.9}[kind]
            self.particles.append([d.pos.copy(), v, random.uniform(0.8, 2.2), col, size, kind])
        self.finish("crash")

    def finish(self, result):
        self.star_sound_done = False
        self.result = result
        self.state = "done"
        self.done_t = 0.0
        self.release_holds()
        m = MISSIONS[self.mission_i]
        mid = m["id"]
        if result != "win" or m["time_limit"] <= 0:
            self.write_result(result == "win",
                              {"crash": "Crashed", "timeout": "Out of time"}.get(result, "Mission over"))
            return
        frac = self.time_left / m["time_limit"]
        self.stars = 1 + (frac >= 0.2 and self.clips == 0) + (frac >= 0.4 and self.clips == 0 and self.battery >= 25)
        self.write_result(True, "Mission complete")
        if m.get("generated"):
            return          # launcher ops are one-offs: their codes don't belong in highscore.json
        old = self.hi.get(mid, {})
        rec = dict(old)
        rec["stars"] = max(old.get("stars", 0), self.stars)
        if self.score > old.get("score", 0):
            rec["score"], rec["time"] = self.score, round(self.elapsed, 1)
            self.new_best = True
        was_locked = self.mission_i + 1 < len(MISSIONS) and not self.unlocked(self.mission_i + 1)
        self.hi[mid] = rec
        self._save_hi()
        if was_locked and self.unlocked(self.mission_i + 1):
            self.popup(f"UNLOCKED: {MISSIONS[self.mission_i + 1]['name']}", (1.0, 0.9, 0.4))

    def update_checkpoints(self, dt):
        if self.cp_i >= len(self.checkpoints):
            return
        c = self.checkpoints[self.cp_i]
        d = self.drone
        if c["kind"] == "land":
            inside = (math.hypot(d.pos[0] - c["pos"][0], d.pos[2] - c["pos"][2]) < c["r"]
                      and d.pos[1] < c["pos"][1] + 1.2
                      and abs(d.vel[1]) < 3.0 and math.hypot(d.vel[0], d.vel[2]) < 2.0)
        elif c["kind"] == "pole":
            inside = math.hypot(d.pos[0] - c["pos"][0], d.pos[2] - c["pos"][2]) < c["r"] and d.pos[1] < 12
        else:
            dist = float(np.linalg.norm(d.pos - c["pos"]))
            inside = dist < c["r"] - 0.3
            if c["kind"] == "gate" and not inside and dist < c["r"] + 1.0 and not c["clipped"]:
                n = self.checkpoint_normal(self.cp_i)
                n = n / (np.linalg.norm(n) + 1e-9)
                if abs(float((d.pos - c["pos"]) @ n)) < 0.8:          # right at the ring's plane
                    c["clipped"] = True
                    self.clips += 1
                    self.score = max(0, self.score - 60)
                    self.battery = max(0.0, self.battery - 6)
                    self.shake = max(self.shake, 0.5)
                    d.vel *= 0.6
                    self.sfx.play("clip")
                    self.popup("CLIPPED THE GATE  -60", (1.0, 0.5, 0.3))
        if c["hold"] > 0:
            if inside:
                if int(self.hold_t * 4) != int((self.hold_t + dt) * 4):
                    self.sfx.play("tick", 0.6)
                self.hold_t += dt
                if self.hold_t >= c["hold"]:
                    self.pass_checkpoint(c)
            else:
                self.hold_t = 0.0
        elif inside:
            self.pass_checkpoint(c)

    def pass_checkpoint(self, c):
        m = MISSIONS[self.mission_i]
        if m["recharge"]:
            self.battery = min(100.0, self.battery + m["recharge"])
        if m.get("delivery"):
            self.carrying = c["label"].startswith("PICKUP")
            self.sfx.play("pickup" if self.carrying else "drop")
        self.cp_i += 1
        self.hold_t = 0.0
        self.combo += 1
        gain = 100 + self.combo * 20
        self.score += gain
        self.sfx.play("combo" if self.combo > 1 else "gate", 0.9)
        self.popup(f"{c['label']}  +{gain}", (1.0, 0.95, 0.3))
        for _ in range(24):
            v = np.random.randn(3) * 5
            col = tuple(int(v_ * 255) for v_ in MISSIONS[self.mission_i]["color"])
            self.particles.append([c["pos"].copy(), v, random.uniform(0.5, 1.0), col, 0.18, "spark"])
        if self.cp_i >= len(self.checkpoints):
            self.score += int(max(0, self.time_left) * (12 if c["kind"] == "land" else 8))
            self.score += int(self.battery * 5)
            self.sfx.play("win")
            self.finish("win")

    def update_particles(self, dt):
        keep = []
        for p in self.particles:
            p[2] -= dt
            if p[2] <= 0:
                continue
            if p[5] == "smoke":
                p[1] *= 1 - dt * 1.5
                p[1][1] += dt * 2
                p[4] += dt * 1.4
            elif p[5] == "dust":
                p[1] *= 1 - dt * 2
                p[4] += dt * 1.2
            else:
                p[1][1] -= G * dt
            p[0] = p[0] + p[1] * dt
            if p[0][1] < 0.02:
                p[0][1] = 0.02
                p[1] = p[1] * np.array([0.5, -0.3, 0.5])
            keep.append(p)
        self.particles = keep[-400:]

    def update_camera(self, dt, orbit=False):
        d = self.drone
        k = clampv(dt * 6.0, 0, 1)
        if orbit:
            a = self.T * 0.12
            eye = np.array([math.sin(a) * 26, 14 + math.sin(self.T * 0.3) * 3, -4 + math.cos(a) * 26])
            self.cam_pos = eye
            self.cam_R = look_basis(eye, d.pos + np.array([0, 4, 0]))
            return
        mode = self.cam_mode if d.alive else 0
        if mode == 1:                                           # FPV: camera on the drone, 20 deg uptilt
            self.cam_pos = d.pos + heading_vec(d.yaw) * 0.3 + WORLD_UP * 0.1
            self.cam_R = basis(d.yaw, 0.30 - d.pitch_tilt, d.roll_tilt)
            self.cam_yaw = d.yaw
        else:
            self.cam_yaw = lerp_angle(self.cam_yaw, d.yaw, clampv(dt * 3.5, 0, 1))
            if mode == 0:
                want = d.pos - heading_vec(self.cam_yaw) * 7.5 + WORLD_UP * 2.6
                target = d.pos + heading_vec(self.cam_yaw) * 6 + WORLD_UP * 0.6
                roll = d.roll_tilt * 0.35
            else:                                               # cinematic: wide, high, from the side
                side = right_vec(self.cam_yaw)
                want = d.pos - heading_vec(self.cam_yaw) * 14 + side * 9 + WORLD_UP * 7
                target = d.pos + heading_vec(self.cam_yaw) * 4
                roll = 0.0
            want[1] = max(want[1], 0.7)
            self.cam_pos = self.cam_pos + (want - self.cam_pos) * k
            # never let the camera sit inside a building / tree: pull it in toward the drone
            if self.hits_world(self.cam_pos, 0.4):
                seg = self.cam_pos - d.pos
                for t in np.linspace(1.0, 0.0, 12):
                    if not self.hits_world(d.pos + seg * t, 0.4):
                        self.cam_pos = d.pos + seg * t
                        break
            self.cam_R = look_basis(self.cam_pos, target, roll)
        if self.shake > 0:
            self.cam_pos = self.cam_pos + np.random.randn(3) * 0.25 * self.shake

    # ------------------------------------------------------------ projection helpers
    def xform(self, pts):
        return (np.asarray(pts, float) - self.cam_pos) @ self.cam_R.T

    def project(self, cs):
        """camera-space (n,3) -> list of (x, y) or None; clips against the near plane."""
        z = cs[:, 2]
        if (z > NEAR).all():
            pts = cs
        elif (z <= NEAR).all():
            return None
        else:
            out = []
            n = len(cs)
            for i in range(n):
                a, b = cs[i], cs[(i + 1) % n]
                ina, inb = a[2] > NEAR, b[2] > NEAR
                if ina:
                    out.append(a)
                if ina != inb:
                    t = (NEAR - a[2]) / (b[2] - a[2])
                    out.append(a + (b - a) * t)
            if len(out) < 3:
                return None
            pts = np.array(out)
        sx = self.RW / 2 + pts[:, 0] / pts[:, 2] * self.F
        sy = self.RH / 2 - pts[:, 1] / pts[:, 2] * self.F
        return list(zip(np.clip(sx, -9000, 9000), np.clip(sy, -9000, 9000)))

    def proj_pt(self, p):
        c = self.xform(p[None, :])[0]
        if c[2] <= NEAR:
            return None
        return (self.RW / 2 + c[0] / c[2] * self.F, self.RH / 2 - c[1] / c[2] * self.F, c[2])

    def fogc(self, col, dist):
        q = max(dist, 0) / (C["draw_distance"] * 0.62)
        f = 1 - math.exp(-q * q)
        return tuple(int(col[i] * (1 - f) + FOG[i] * f) for i in range(3))

    # ------------------------------------------------------------ sky + ground (per pixel)
    def draw_environment(self):
        """Sky + ground, one ray per pixel (at sky_res), then scaled to the window."""
        R = self.cam_R.astype(np.float32)
        cam = [float(v) for v in self.cam_pos]           # python floats keep the maths in float32
        S0, S1, S2 = (float(v) for v in SUN)
        r, u, f = R[0], R[1], R[2]
        PX, PY = self.PX, self.PY
        dx = (PX * r[0] + PY * u[0] + f[0]).ravel()
        dy = (PX * r[1] + PY * u[1] + f[1]).ravel()
        dz = (PX * r[2] + PY * u[2] + f[2]).ravel()
        inv = 1.0 / np.sqrt(dx * dx + dy * dy + dz * dz)
        ey = dy * inv                                    # sine of elevation
        out = np.empty((dx.size, 3), np.float32)
        D = np.float32(C["draw_distance"] * 0.62)
        # --- sky: gradient, sun, mountains, clouds
        s = np.nonzero(dy >= -1e-4)[0]
        if s.size:
            e = np.clip(ey[s], 0, 1)
            sky = SKY_HOR + (SKY_TOP - SKY_HOR) * np.sqrt(e)[:, None]
            sd = (dx[s] * S0 + dy[s] * S1 + dz[s] * S2) * inv[s]
            sd = np.clip(sd, 0, 1).astype(np.float32)
            glow = 0.55 * np.exp(-90 * (1 - sd)) + 0.22 * np.exp(-10 * (1 - sd)) + (sd > 0.9993)
            sky += SUN_COL * glow[:, None]
            lo = np.nonzero(e < 0.08)[0]                   # mountains only near the horizon
            if lo.size:
                az = np.arctan2(dx[s][lo], dz[s][lo])
                el = e[lo]
                m1 = 0.035 + 0.022 * (np.sin(az * 3 + 1.0) + 0.5 * np.sin(az * 7 + 2.3) + 0.25 * np.sin(az * 19 + 0.4))
                m2 = 0.018 + 0.014 * (np.sin(az * 5 + 4.0) + 0.6 * np.sin(az * 11 + 1.3) + 0.3 * np.sin(az * 27))
                blk = sky[lo]
                blk[el < m1] = MOUNT_FAR
                blk[el < m2] = MOUNT_NEAR
                sky[lo] = blk
            c = np.nonzero(e > 0.03)[0]                    # clouds on a layer 420 m up
            if c.size:
                si = s[c]
                t = (420.0 - cam[1]) / np.maximum(dy[si], 1e-4)
                cxw = (cam[0] + dx[si] * t + self.T * 3.0) * (16 / 70)
                czw = (cam[2] + dz[si] * t) * (16 / 70)
                cv = self.clouds[czw.astype(np.int32) & 511, cxw.astype(np.int32) & 511]
                ca = np.clip((cv - 0.48) * 3.2, 0, 0.9) * np.clip((e[c] - 0.03) * 8, 0, 1)
                sky[c] = sky[c] * (1 - ca[:, None]) + ((235 + 20 * sd[c]) * ca)[:, None]
            out[s] = sky
        # --- ground: textured, road grid, distance fog
        gi = np.nonzero(dy < -1e-4)[0]
        if gi.size:
            h = max(cam[1], 0.05)
            t = h / -dy[gi]
            dist = t / inv[gi]
            gx = cam[0] + dx[gi] * t
            gz = cam[2] + dz[gi] * t
            col = np.empty((gi.size, 3), np.float32)
            near = dist < 55
            ni, fi = np.nonzero(near)[0], np.nonzero(~near)[0]
            col[ni] = self.tex_flat.take((((gz[ni] * 2).astype(np.int32) & 1023) << 10) |
                                         ((gx[ni] * 2).astype(np.int32) & 1023), axis=0)
            col[fi] = self.tex_far_flat.take((((gz[fi] * 0.5).astype(np.int32) & 255) << 8) |
                                             ((gx[fi] * 0.5).astype(np.int32) & 255), axis=0)
            mac = self.macro_flat.take((((gz * (1 / 24)).astype(np.int32) & 255) << 8) |
                                       ((gx * (1 / 24)).astype(np.int32) & 255))
            q = dist / D
            fk = 1 - np.exp(-q * q)
            col *= (mac * (0.62 + 0.5 * S1) * (1 - fk))[:, None]
            col += FOG * fk[:, None]
            out[gi] = col
        np.clip(out, 0, 255, out=out)
        img = out.astype(np.uint8).reshape(self.GH, self.GW, 3)
        surf = pygame.image.frombuffer(img.tobytes(), (self.GW, self.GH), "RGB")
        # same pixel format as the screen -> smoothscale can write straight into it
        pygame.transform.smoothscale(surf.convert(self.screen), (self.RW, self.RH), self.screen)

    # ------------------------------------------------------------ scene
    def draw_scene(self):
        self.draw_environment()
        scr = self.screen
        cam = self.cam_pos
        dd = C["draw_distance"]
        # --- flat ground decals: launch pad, landing pad
        self.draw_pad(np.array([0.0, 0.02, -4.0]), 5.0, square=True)
        for i, c in enumerate(self.checkpoints):
            if c["kind"] == "land" and c["pos"][1] < 0.5:
                self.draw_pad(c["pos"] + np.array([0, 0.03, 0]), c["r"], active=i == self.cp_i)
        # --- which buildings can be seen (view frustum, generous margins for shadows)
        if self.buildings:
            cen = self.xform(np.array([b["centre"] for b in self.buildings]))
            tx, ty = self.tanx * 1.05, self.tanx * self.RH / self.RW * 1.1
            for b, c in zip(self.buildings, cen):
                r = b["radius"]
                b["vis"] = (c[2] > -r and abs(c[0]) < c[2] * tx + r * 1.5 and abs(c[1]) < c[2] * ty + r * 1.5)
                reach = r + b["h"] * 1.3
                b["vis_shadow"] = c[2] > -reach and abs(c[0]) < c[2] * tx + reach * 1.5
        # --- shadows
        if C["shadows"]:
            sl = self.shadow_layer
            sl.fill((255, 0, 255))
            for b in self.buildings:
                if (b["x"] - cam[0]) ** 2 + (b["z"] - cam[2]) ** 2 > (dd * 0.7) ** 2:
                    continue
                if not b["vis_shadow"]:
                    continue
                p = self.project(self.xform(b["shadow"]))
                if p:
                    pygame.draw.polygon(sl, (0, 0, 0), p)
            for x, z, h, rad, _s in self.trees:
                if (x - cam[0]) ** 2 + (z - cam[2]) ** 2 > 70 ** 2:
                    continue
                c = np.array([x, 0.02, z]) - SUN * (h * 0.6 / SUN[1]) * np.array([1, 0, 1])
                q = self.proj_pt(c)
                if q:
                    rr = max(1, int(rad * self.F / q[2]))
                    pygame.draw.ellipse(sl, (0, 0, 0), (q[0] - rr, q[1] - rr * 0.45, rr * 2, rr * 0.9))
            d = self.drone
            if d.alive and d.pos[1] < 60:
                ring = [d.pos + np.array([math.cos(a) * 0.9, 0, math.sin(a) * 0.9]) for a in np.linspace(0, math.tau, 12, False)]
                ring = np.array(ring)
                ring[:, 1] = 0.03
                p = self.project(self.xform(ring))
                if p:
                    pygame.draw.polygon(sl, (0, 0, 0), p)
            scr.blit(sl, (0, 0))
        # --- objects, painter's algorithm
        items = []
        for b in self.buildings:
            dist = math.hypot(b["x"] - cam[0], b["z"] - cam[2])
            if dist < dd * 1.05 and b["vis"]:
                items.append((dist, 0, b))
        if len(self.trees):
            T_ = self.trees
            n = len(T_)
            ys = np.array([0.0, 0.55, 0.55, 0.72, 0.88])
            kp = np.empty((n, 5, 3))
            kp[:, :, 0] = T_[:, 0:1]
            kp[:, :, 2] = T_[:, 1:2]
            kp[:, :, 1] = T_[:, 2:3] * ys
            kc = self.xform(kp.reshape(-1, 3)).reshape(n, 5, 3)
            self.tree_cs = kc
            zc = kc[:, 1, 2]
            vis = (zc > 0.5) & (zc < dd * 0.8) & (np.abs(kc[:, 1, 0]) < zc * self.tanx * 1.1 + T_[:, 3] * 2)
            for i in np.nonzero(vis)[0]:
                items.append((float(zc[i]), 1, i))
        for i, c in enumerate(self.checkpoints):
            if c["kind"] != "land" and self.cp_i - 1 <= i <= self.cp_i + 3:
                items.append((float(np.linalg.norm(c["pos"] - cam)), 2, i))
        d = self.drone
        if d.alive and self.cam_mode != 1 or self.state in ("title", "briefing"):
            if d.alive:
                items.append((float(np.linalg.norm(d.pos - cam)), 3, None))
        for i, p in enumerate(self.particles):
            items.append((float(np.linalg.norm(p[0] - cam)), 4, p))
        items.sort(key=lambda it: -it[0])
        for dist, kind, obj in items:
            if kind == 0:
                self.draw_building(obj, dist)
            elif kind == 1:
                self.draw_tree(obj, dist)
            elif kind == 2:
                self.draw_checkpoint(obj)
            elif kind == 3:
                self.draw_drone()
            else:
                self.draw_particle(obj)

    @staticmethod
    def _hull(pts):
        P = sorted(set((round(p[0], 3), round(p[2], 3)) for p in pts))
        if len(P) < 3:
            return np.array([[p[0], 0.02, p[1]] for p in P])

        def cross(o, a, b):
            return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
        lo, hi = [], []
        for p in P:
            while len(lo) >= 2 and cross(lo[-2], lo[-1], p) <= 0:
                lo.pop()
            lo.append(p)
        for p in reversed(P):
            while len(hi) >= 2 and cross(hi[-2], hi[-1], p) <= 0:
                hi.pop()
            hi.append(p)
        h = lo[:-1] + hi[:-1]
        return np.array([[x, 0.02, z] for x, z in h])

    def draw_pad(self, c, r, square=False, active=False):
        dist = float(np.linalg.norm(c - self.cam_pos))
        if square:
            pts = np.array([c + [-r, 0, -r], c + [r, 0, -r], c + [r, 0, r], c + [-r, 0, r]])
            base = (150, 150, 146)
        else:
            pts = np.array([c + [math.cos(a) * r, 0, math.sin(a) * r] for a in np.linspace(0, math.tau, 28, False)])
            base = (62, 64, 70)
        p = self.project(self.xform(pts))
        if not p:
            return
        pygame.draw.polygon(self.screen, self.fogc(base, dist), p)
        ring = np.array([c + [math.cos(a) * r * 0.8, 0.01, math.sin(a) * r * 0.8] for a in np.linspace(0, math.tau, 28, False)])
        rc = (255, 215, 60) if square else ((80, 255, 140) if active and int(self.T * 3) % 2 else (240, 240, 240))
        q = self.project(self.xform(ring))
        if q:
            pygame.draw.polygon(self.screen, self.fogc(rc, dist), q, max(1, int(0.25 * self.F / max(dist, 1))))
        s = r * 0.4
        for quad in ([[-s, -s], [-s * 0.6, -s], [-s * 0.6, s], [-s, s]], [[s * 0.6, -s], [s, -s], [s, s], [s * 0.6, s]],
                     [[-s * 0.6, -s * 0.15], [s * 0.6, -s * 0.15], [s * 0.6, s * 0.15], [-s * 0.6, s * 0.15]]):
            w = np.array([c + [a, 0.02, b] for a, b in quad])
            q = self.project(self.xform(w))
            if q:
                pygame.draw.polygon(self.screen, self.fogc(rc, dist), q)

    def draw_building(self, b, dist):
        cam = self.cam_pos
        P = b["pts"]
        cs = self.xform(P)
        base = b["col"]
        amb = 0.52
        faces = []
        if cam[1] > b["h"]:
            faces.append(([4, 5, 6, 7], np.array([0, 1, 0])))
        for i in range(4):
            a, c = P[i], P[(i + 1) % 4]
            n = np.array([c[2] - a[2], 0, -(c[0] - a[0])])
            n /= np.linalg.norm(n)
            mid = (a + c) / 2
            if n[0] * (cam[0] - mid[0]) + n[2] * (cam[2] - mid[2]) > 0:
                faces.append(([i, (i + 1) % 4, (i + 1) % 4 + 4, i + 4], n))
        for idx, n in faces:
            p = self.project(cs[idx])
            if not p:
                continue
            lit = amb + 0.62 * max(0.0, float(n @ SUN))
            if n[1] > 0.5:
                col = shade((118, 118, 122), lit)
            else:
                col = shade(base, lit)
            pygame.draw.polygon(self.screen, self.fogc(col, dist), p)
            if n[1] < 0.5 and dist < 140:
                self.draw_windows(b, idx, n, dist, lit)
        if "pad_i" in b and cam[1] > b["h"] and b["pad_i"] >= self.cp_i:
            c = self.checkpoints[b["pad_i"]]
            self.draw_pad(c["pos"] + np.array([0, 0.04, 0]), c["r"], active=b["pad_i"] == self.cp_i)
        if b["antenna"]:
            top = np.array([b["x"], b["h"], b["z"]])
            a1, a2 = self.proj_pt(top), self.proj_pt(top + np.array([0, 9, 0]))
            if a1 and a2:
                pygame.draw.line(self.screen, self.fogc((70, 70, 76), dist), a1[:2], a2[:2], max(1, int(0.3 * self.F / a2[2])))
                if int(self.T * 1.2 + b["seed"] * 5) % 2 == 0:
                    rr = max(2, int(0.5 * self.F / a2[2]))
                    pygame.gfxdraw.filled_circle(self.screen, int(a2[0]), int(a2[1]), rr, (255, 50, 40, 220))

    def draw_windows(self, b, idx, n, dist, lit):
        P = b["pts"]
        a, c = P[idx[0]], P[idx[1]]
        L = float(np.linalg.norm(c - a))
        e = (c - a) / L
        off = n * 0.05
        glass = b["style"] == "glass"
        view = self.cam_pos - (a + c) / 2
        view /= np.linalg.norm(view) + 1e-9
        fres = 0.35 + 0.65 * (1 - abs(float(view @ n))) ** 2
        refl = SKY_HOR * fres + np.array([30, 40, 58]) * (1 - fres)
        wcol = tuple(int(v) for v in (refl * (0.95 if glass else 0.75)))
        wcol = self.fogc(shade(wcol, 0.75 + 0.35 * lit), dist)
        floor_h = 3.4
        quads = []
        if dist < 50:
            cw = 2.8
            ncol = max(1, int((L - 1.2) / cw))
            pad = (L - ncol * cw) / 2
            y = 1.6
            while y + 1.6 < b["h"]:
                for k in range(ncol):
                    x0 = pad + k * cw + 0.35
                    x1 = x0 + cw - 0.7
                    quads.append([a + e * x0 + off + [0, y, 0], a + e * x1 + off + [0, y, 0],
                                  a + e * x1 + off + [0, y + 1.7, 0], a + e * x0 + off + [0, y + 1.7, 0]])
                y += floor_h
        else:
            y = 1.6
            while y + 1.6 < b["h"]:
                quads.append([a + e * 0.6 + off + [0, y, 0], c - e * 0.6 + off + [0, y, 0],
                              c - e * 0.6 + off + [0, y + 1.6, 0], a + e * 0.6 + off + [0, y + 1.6, 0]])
                y += floor_h
        if not quads:
            return
        Q = np.array(quads)
        cs = self.xform(Q.reshape(-1, 3)).reshape(-1, 4, 3)
        for q in cs:
            p = self.project(q)
            if p:
                pygame.draw.polygon(self.screen, wcol, p)

    def draw_tree(self, i, dist):
        x, z, h, rad, sd = self.trees[i]
        kc = self.tree_cs[i]
        if (kc[:, 2] <= NEAR).any():
            return
        sx = self.RW / 2 + kc[:, 0] / kc[:, 2] * self.F
        sy = self.RH / 2 - kc[:, 1] / kc[:, 2] * self.F
        k = self.F / kc[1, 2]
        pygame.draw.line(self.screen, self.fogc((86, 64, 44), dist), (sx[0], sy[0]), (sx[1], sy[1]),
                         max(1, int(0.35 * k)))
        cols = (self.fogc((34 + 20 * sd, 72 + 20 * sd, 34), dist), self.fogc((54 + 25 * sd, 100 + 20 * sd, 44), dist),
                self.fogc((96 + 30 * sd, 140 + 20 * sd, 64), dist))
        for j, (rr, col, ox) in zip((2, 3, 4), ((1.0, cols[0], 0.0), (0.8, cols[1], 0.12), (0.5, cols[2], 0.22))):
            R_ = max(1, int(rad * rr * self.F / kc[j, 2]))
            pygame.draw.circle(self.screen, col, (int(sx[j] + ox * R_), int(sy[j] - ox * R_)), R_)

    def ring_world(self, center, normal, r, n=28):
        normal = normal / (np.linalg.norm(normal) + 1e-9)
        up = WORLD_UP if abs(normal[1]) < 0.95 else np.array([1.0, 0.0, 0.0])
        u = np.cross(up, normal)
        u /= np.linalg.norm(u) + 1e-9
        v = np.cross(normal, u)
        a = np.linspace(0, math.tau, n, False)
        return center + np.outer(np.cos(a), u) * r + np.outer(np.sin(a), v) * r

    def checkpoint_normal(self, i):
        c = self.checkpoints[i]
        if c["kind"] in ("altitude", "land"):
            return np.array([0.0, 1.0, 0.0])
        prev = np.array([0.0, 0.0, -4.0]) if i == 0 else self.checkpoints[i - 1]["pos"]
        d = c["pos"] - prev
        d[1] = 0
        if np.linalg.norm(d) < 0.01:
            d = np.array([0.0, 0.0, 1.0])
        return d

    def draw_checkpoint(self, i):
        c = self.checkpoints[i]
        passed, active = i < self.cp_i, i == self.cp_i
        base = MISSIONS[self.mission_i]["color"]
        if passed:
            col = (70, 255, 130)
        else:
            k = (1.0 + 0.25 * math.sin(self.T * 6)) if active else 0.6
            col = tuple(int(clampv(v * 255 * k, 0, 255)) for v in base)
        dist = float(np.linalg.norm(c["pos"] - self.cam_pos))
        if c["kind"] == "pole":
            self.draw_pole(c, col, active, dist)
            return
        if c["kind"] == "altitude":                      # beam from the ground
            a, b = self.proj_pt(c["pos"] * [1, 0, 1]), self.proj_pt(c["pos"])
            if a and b:
                pygame.draw.line(self.screen, self.fogc(shade(col, 0.6), dist), a[:2], b[:2], 2)
        pts = self.ring_world(c["pos"], self.checkpoint_normal(i), c["r"])
        cs = self.xform(pts)
        n = len(cs)
        for width_k, cc in ((0.9, shade(col, 0.35)), (0.45, col), (0.14, (255, 255, 255))):
            if not active and width_k < 0.2:
                continue
            for j in range(n):
                a, b = cs[j], cs[(j + 1) % n]
                if a[2] <= NEAR or b[2] <= NEAR:
                    continue
                w = max(1, int(width_k * self.F / ((a[2] + b[2]) / 2)))
                pa = (self.RW / 2 + a[0] / a[2] * self.F, self.RH / 2 - a[1] / a[2] * self.F)
                pb = (self.RW / 2 + b[0] / b[2] * self.F, self.RH / 2 - b[1] / b[2] * self.F)
                pygame.draw.line(self.screen, self.fogc(cc, dist * 0.6), pa, pb, w)

    def draw_pole(self, c, col, active, dist):
        x, z = c["pos"][0], c["pos"][2]
        rgt = self.cam_R[0].copy()
        rgt[1] = 0
        rgt /= np.linalg.norm(rgt) + 1e-9
        w = 0.35
        for k in range(8):
            y0, y1 = k * 1.3, (k + 1) * 1.3
            q = np.array([[x, y0, z] - rgt * w, [x, y0, z] + rgt * w, [x, y1, z] + rgt * w, [x, y1, z] - rgt * w])
            p = self.project(self.xform(q))
            if p:
                cc = col if k % 2 == 0 else (245, 245, 245)
                pygame.draw.polygon(self.screen, self.fogc(cc, dist), p)
        if active:
            flag = np.array([[x, 10.4, z], [x, 9.0, z], [x, 9.7, z] + rgt * 1.6])
            p = self.project(self.xform(flag))
            if p:
                pygame.draw.polygon(self.screen, col, p)
            # guide ring on the ground: pass inside it
            ring = self.ring_world(np.array([x, 0.05, z]), np.array([0, 1.0, 0]), c["r"], 24)
            p = self.project(self.xform(ring))
            if p:
                pygame.draw.polygon(self.screen, self.fogc(col, dist), p, 2)

    def draw_drone(self):
        d = self.drone
        B = basis(d.yaw, -d.pitch_tilt, d.roll_tilt)
        pos = d.pos

        def W(local):
            local = np.asarray(local, float)
            return pos + local @ B

        polys = []
        # arms (X frame)
        for sx, sz in ((1, 1), (-1, 1), (1, -1), (-1, -1)):
            tip = np.array([sx * 0.62, 0.02, sz * 0.62])
            side = np.array([-sz, 0, sx]) / math.sqrt(2) * 0.05
            polys.append((W([side, -side, tip - side, tip + side]), (38, 38, 44), None))
        # body box
        hx, hy, hz = 0.2, 0.08, 0.32
        corners = np.array([[sx * hx, sy * hy, sz * hz] for sy in (-1, 1) for sz in (-1, 1) for sx in (-1, 1)])
        boxf = [([4, 5, 7, 6], [0, 1, 0], (78, 82, 92)), ([0, 1, 3, 2], [0, -1, 0], (30, 30, 34)),
                ([2, 3, 7, 6], [0, 0, 1], (220, 120, 40)), ([0, 1, 5, 4], [0, 0, -1], (50, 52, 58)),
                ([1, 3, 7, 5], [1, 0, 0], (56, 58, 66)), ([0, 2, 6, 4], [-1, 0, 0], (56, 58, 66))]
        wc = W(corners)
        for idx, n, col in boxf:
            nw = np.asarray(n, float) @ B
            if nw @ (self.cam_pos - pos) > 0:
                lit = 0.55 + 0.6 * max(0.0, float(nw @ SUN))
                polys.append((wc[idx], shade(col, lit), None))
        if self.carrying:                                   # parcel slung underneath
            pc = np.array([[sx * 0.18, -0.12 + sy * 0.14, sz * 0.18] for sy in (-1, 1) for sz in (-1, 1) for sx in (-1, 1)])
            pw = W(pc)
            for idx, nn, col in boxf:
                nw = np.asarray(nn, float) @ B
                if nw @ (self.cam_pos - pos) > 0:
                    base = (196, 150, 96) if nn[1] <= 0 else (220, 176, 120)
                    polys.append((pw[idx] + np.array([0, -0.2, 0]), shade(base, 0.6 + 0.5 * max(0.0, float(nw @ SUN))), None))
        # battery on top + camera
        polys.append((W([[-0.1, 0.1, -0.2], [0.1, 0.1, -0.2], [0.1, 0.1, 0.12], [-0.1, 0.1, 0.12]]), (240, 200, 40), None))
        # rotors: translucent discs + blade
        for sx, sz in ((1, 1), (-1, 1), (1, -1), (-1, -1)):
            ctr = np.array([sx * 0.62, 0.09, sz * 0.62])
            ring = [ctr + [math.cos(a) * 0.36, 0, math.sin(a) * 0.36] for a in np.linspace(0, math.tau, 14, False)]
            polys.append((W(ring), (200, 205, 215, 70), "alpha"))
            ang = d.prop * (1 if sx * sz > 0 else -1)
            bl = np.array([math.cos(ang) * 0.36, 0, math.sin(ang) * 0.36])
            polys.append((W([ctr - bl, ctr + bl]), (25, 25, 28), "line"))
            polys.append((W([ctr]), (60, 255, 120) if sz > 0 else (255, 50, 50), "led"))
        items = []
        for pts, col, kind in polys:
            cs = self.xform(pts)
            items.append((cs[:, 2].mean(), cs, col, kind))
        items.sort(key=lambda it: -it[0])
        for z, cs, col, kind in items:
            if kind == "line":
                p = self.project(cs) if len(cs) > 2 else (
                    None if (cs[:, 2] <= NEAR).any() else
                    [(self.RW / 2 + c[0] / c[2] * self.F, self.RH / 2 - c[1] / c[2] * self.F) for c in cs])
                if p:
                    pygame.draw.line(self.screen, col, p[0], p[1], max(1, int(0.05 * self.F / z)))
            elif kind == "led":
                c = cs[0]
                if c[2] > NEAR:
                    r = max(2, int(0.07 * self.F / c[2]))
                    x, y = int(self.RW / 2 + c[0] / c[2] * self.F), int(self.RH / 2 - c[1] / c[2] * self.F)
                    pygame.gfxdraw.filled_circle(self.screen, x, y, r * 2, (*col, 60))
                    pygame.draw.circle(self.screen, col, (x, y), r)
            else:
                p = self.project(cs)
                if p and len(p) >= 3:
                    if kind == "alpha":
                        pygame.gfxdraw.filled_polygon(self.screen, [(int(a), int(b)) for a, b in p], col)
                    else:
                        pygame.draw.polygon(self.screen, col, p)

    def draw_particle(self, p):
        q = self.proj_pt(p[0])
        if not q:
            return
        if q[2] < 1.2:                      # too close to the lens
            return
        r = min(max(1, int(p[4] * self.F / q[2])), 60)
        a = clampv(p[2], 0, 1)
        if p[5] in ("smoke", "dust"):
            pygame.gfxdraw.filled_circle(self.screen, int(q[0]), int(q[1]), r, (*p[3], int(110 * a)))
        else:
            pygame.draw.circle(self.screen, p[3], (int(q[0]), int(q[1])), r)

    # ------------------------------------------------------------ HUD / UI
    def txt(self, font, s, col, pos, anchor="topleft", shadow=True):
        surf = font.render(s, True, col)
        r = surf.get_rect(**{anchor: pos})
        if shadow:
            self.screen.blit(font.render(s, True, (0, 0, 0)), r.move(2, 2))
        self.screen.blit(surf, r)
        return r

    def panel(self, rect, alpha=140, radius=12, border=None):
        s = pygame.Surface(rect.size, pygame.SRCALPHA)
        pygame.draw.rect(s, (8, 12, 22, alpha), s.get_rect(), border_radius=radius)
        if border:
            pygame.draw.rect(s, (*border, 220), s.get_rect(), 2, border_radius=radius)
        self.screen.blit(s, rect)

    def draw_hud(self):
        d = self.drone
        m = MISSIONS[self.mission_i]
        W_, H_ = self.RW, self.RH
        mc = tuple(int(v * 255) for v in m["color"])
        # top-left mission panel
        self.panel(pygame.Rect(14, 12, 300, 92))
        self.txt(self.f_med, m["name"], mc, (28, 18))
        if self.checkpoints:
            self.txt(self.f_sm, f"CHECKPOINT {min(self.cp_i + 1, len(self.checkpoints))}/{len(self.checkpoints)}",
                     (220, 235, 255), (28, 56))
        self.txt(self.f_sm, f"SCORE {self.score}", (255, 225, 110), (28, 78))
        # battery + wind
        if m["drain"] > 0 or self.wind_base > 0:
            self.panel(pygame.Rect(14, 110, 300, 56))
            if m["drain"] > 0:
                b = self.battery
                col = (110, 235, 130) if b > 40 else (255, 200, 80) if b > 20 else (255, 80, 70)
                if b < 20 and int(self.T * 4) % 2:
                    col = (120, 40, 40)
                pygame.draw.rect(self.screen, (40, 46, 60), (28, 120, 150, 16), border_radius=4)
                pygame.draw.rect(self.screen, col, (28, 120, int(150 * b / 100), 16), border_radius=4)
                pygame.draw.rect(self.screen, (200, 210, 230), (178, 124, 4, 8))
                self.txt(self.f_xs, f"BATTERY {b:3.0f}%", (220, 230, 250), (28, 140))
            if self.wind_base > 0:
                wv = self.wind
                ws = float(np.linalg.norm(wv)) / 0.45
                cx, cy = 258, 138
                pygame.draw.circle(self.screen, (40, 46, 60), (cx, cy), 20)
                if ws > 0.1:
                    a = math.atan2(wv[0], wv[2]) - (self.cam_yaw if self.cam_mode != 1 else self.drone.yaw)
                    dx_, dy_ = math.sin(a), -math.cos(a)
                    tip = (cx + dx_ * 17, cy + dy_ * 17)
                    tail = (cx - dx_ * 13, cy - dy_ * 13)
                    pygame.draw.line(self.screen, (170, 210, 255), tail, tip, 3)
                    pygame.draw.circle(self.screen, (170, 210, 255), (int(tip[0]), int(tip[1])), 4)
                self.txt(self.f_xs, f"WIND {ws:3.0f}", (170, 210, 255), (196, 120))
        if self.carrying:
            self.txt(self.f_sm, "PARCEL ON BOARD (heavy)", (255, 170, 90), (28, 172))
        # timer
        if m["time_limit"] > 0:
            col = (255, 90, 90) if self.time_left < 10 else (255, 255, 255)
            self.panel(pygame.Rect(W_ - 170, 12, 156, 52))
            self.txt(self.f_med, f"{max(0, self.time_left):5.1f}s", col, (W_ - 26, 18), "topright")
        # compass tape
        self.draw_compass()
        # speed / altitude
        self.panel(pygame.Rect(14, H_ // 2 - 40, 118, 80))
        self.txt(self.f_xs, "SPEED", (170, 190, 220), (26, H_ // 2 - 34))
        self.txt(self.f_med, f"{d.speed * 3.6:4.0f}", (255, 255, 255), (26, H_ // 2 - 16))
        self.txt(self.f_xs, "km/h", (170, 190, 220), (92, H_ // 2 - 2))
        self.panel(pygame.Rect(W_ - 132, H_ // 2 - 40, 118, 80))
        self.txt(self.f_xs, "ALTITUDE", (170, 190, 220), (W_ - 120, H_ // 2 - 34))
        self.txt(self.f_med, f"{d.pos[1]:5.1f}", (255, 255, 255), (W_ - 120, H_ // 2 - 16))
        self.txt(self.f_xs, "m", (170, 190, 220), (W_ - 34, H_ // 2 - 2))
        vs = d.vel[1]
        self.txt(self.f_xs, f"{'+' if vs >= 0 else ''}{vs:4.1f} m/s", (150, 220, 255) if vs >= 0 else (255, 180, 120),
                 (W_ - 120, H_ // 2 + 18))
        # FPV crosshair + horizon ladder
        if self.cam_mode == 1:
            cx, cy = W_ // 2, H_ // 2
            pygame.draw.line(self.screen, (255, 255, 255), (cx - 22, cy), (cx - 8, cy), 2)
            pygame.draw.line(self.screen, (255, 255, 255), (cx + 8, cy), (cx + 22, cy), 2)
            pygame.draw.line(self.screen, (255, 255, 255), (cx, cy + 8), (cx, cy + 16), 2)
        # target indicator
        self.draw_target()
        # hold progress
        if self.cp_i < len(self.checkpoints) and self.checkpoints[self.cp_i]["hold"] > 0 and self.hold_t > 0:
            frac = clampv(self.hold_t / self.checkpoints[self.cp_i]["hold"], 0, 1)
            r = pygame.Rect(W_ // 2 - 140, H_ // 2 + 70, 280, 16)
            self.panel(r.inflate(10, 10), radius=8)
            pygame.draw.rect(self.screen, (120, 255, 160), (r.x, r.y, int(r.w * frac), r.h), border_radius=6)
            self.txt(self.f_xs, "HOLD", (255, 255, 255), (r.centerx, r.y - 22), "midtop")
        # stick display (bottom centre) - great for checking the lab pad
        self.draw_sticks()
        # flags
        flags = []
        if self.held("turbo") or pygame.key.get_pressed()[pygame.K_TAB]:
            flags.append(("TURBO", (255, 170, 70)))
        if self.held("precision") or pygame.key.get_pressed()[pygame.K_x]:
            flags.append(("PRECISION", (255, 255, 150)))
        if d.landed:
            flags.append(("LANDED - throttle up to take off", (170, 230, 255)))
        flags.append((["CHASE", "FPV", "CINEMATIC"][self.cam_mode] + " CAM", (170, 190, 220)))
        for i, (s, col) in enumerate(flags):
            self.txt(self.f_sm, s, col, (W_ - 20, H_ - 34 - i * 24), "topright")
        if self.warning and int(self.T * 6) % 2 == 0:
            self.txt(self.f_big, self.warning, (255, 70, 60), (W_ // 2, H_ // 2 - 150), "midtop")
        if self.flash > 0:
            s = pygame.Surface((W_, H_), pygame.SRCALPHA)
            s.fill((255, 255, 255, int(120 * self.flash)) if d.alive else (255, 80, 60, int(200 * self.flash)))
            self.screen.blit(s, (0, 0))
        for i, (t, s, colf) in enumerate(self.popups):
            col = tuple(int(v * 255) for v in colf)
            self.txt(self.f_med, s, col, (W_ // 2, 150 + i * 36 - int((1.4 - t) * 18)), "midtop")

    def draw_compass(self):
        W_ = self.RW
        r = pygame.Rect(W_ // 2 - 220, 12, 440, 38)
        self.panel(r, radius=10)
        yaw = self.cam_yaw if self.cam_mode != 1 else self.drone.yaw
        clip = self.screen.get_clip()
        self.screen.set_clip(r)
        for deg in range(0, 360, 15):
            a = math.radians(deg)
            dlt = (a - yaw + math.pi) % math.tau - math.pi
            x = r.centerx + dlt * 260
            if r.x < x < r.right:
                lab = {0: "N", 90: "E", 180: "S", 270: "W"}.get(deg)
                if lab:
                    self.txt(self.f_sm, lab, (255, 255, 255), (x, r.y + 8), "midtop", shadow=False)
                else:
                    pygame.draw.line(self.screen, (160, 175, 200), (x, r.y + 12), (x, r.y + 12 + (10 if deg % 45 == 0 else 5)), 2)
        if self.cp_i < len(self.checkpoints):
            v = self.checkpoints[self.cp_i]["pos"] - self.drone.pos
            a = math.atan2(v[0], v[2])
            dlt = clampv((a - yaw + math.pi) % math.tau - math.pi, -0.82, 0.82)
            x = r.centerx + dlt * 260
            mc = tuple(int(c * 255) for c in MISSIONS[self.mission_i]["color"])
            pygame.draw.polygon(self.screen, mc, [(x, r.bottom - 2), (x - 7, r.bottom - 12), (x + 7, r.bottom - 12)])
        self.screen.set_clip(clip)
        pygame.draw.line(self.screen, (255, 90, 80), (r.centerx, r.y + 2), (r.centerx, r.bottom - 2), 2)

    def draw_target(self):
        if self.cp_i >= len(self.checkpoints):
            return
        c = self.checkpoints[self.cp_i]
        tp = c["pos"] + (np.array([0, 3, 0]) if c["kind"] in ("pole", "land") else 0)
        cs = self.xform(tp[None, :])[0]
        dist = float(np.linalg.norm(c["pos"] - self.drone.pos))
        mc = tuple(int(v * 255) for v in MISSIONS[self.mission_i]["color"])
        W_, H_ = self.RW, self.RH
        if cs[2] > NEAR:
            x = W_ / 2 + cs[0] / cs[2] * self.F
            y = H_ / 2 - cs[1] / cs[2] * self.F
            if 40 < x < W_ - 40 and 60 < y < H_ - 60:
                s = 12
                pygame.draw.polygon(self.screen, mc, [(x, y - s), (x + s, y), (x, y + s), (x - s, y)], 2)
                self.txt(self.f_xs, f"{dist:.0f} m", mc, (x, y + 16), "midtop")
                return
        ang = math.atan2(-cs[1], cs[0]) if cs[2] > 0 else math.atan2(cs[1], -cs[0])
        if cs[2] <= 0 and abs(cs[0]) < 1e-3:
            ang = math.pi / 2
        rx, ry = W_ / 2 - 70, H_ / 2 - 70
        x, y = W_ / 2 + math.cos(ang) * rx, H_ / 2 + math.sin(ang) * ry
        tip = (x + math.cos(ang) * 16, y + math.sin(ang) * 16)
        l = (x + math.cos(ang + 2.5) * 14, y + math.sin(ang + 2.5) * 14)
        r = (x + math.cos(ang - 2.5) * 14, y + math.sin(ang - 2.5) * 14)
        pygame.draw.polygon(self.screen, mc, [tip, l, r])
        self.txt(self.f_xs, f"{dist:.0f} m", mc, (x - math.cos(ang) * 22, y - math.sin(ang) * 22), "center")

    def draw_sticks(self):
        W_, H_ = self.RW, self.RH
        r = pygame.Rect(18, H_ - 116, 230, 102)
        self.panel(r)
        clicks = self.click_states()
        labels = (("THR / YAW", "lx", "ly"), ("PITCH / ROLL", "rx", "ry"))
        for i, (lab, ax, ay) in enumerate(labels):
            bx = r.x + 14 + i * 110
            box = pygame.Rect(bx, r.y + 24, 66, 66)
            pygame.draw.rect(self.screen, (40, 50, 70), box, border_radius=8)
            pygame.draw.rect(self.screen, (255, 210, 90) if clicks[i] else (90, 110, 140), box, 2, border_radius=8)
            keys = pygame.key.get_pressed()
            x, y = self.stick(ax), self.stick(ay)
            if i == 0:
                x = x or (keys[pygame.K_RIGHT] - keys[pygame.K_LEFT])
                y = y or (keys[pygame.K_DOWN] - keys[pygame.K_UP])
            else:
                x = x or (keys[pygame.K_d] - keys[pygame.K_a])
                y = y or (keys[pygame.K_s] - keys[pygame.K_w])
            pygame.draw.circle(self.screen, (120, 220, 255), (int(box.centerx + x * 26), int(box.centery + y * 26)), 7)
            self.txt(self.f_xs, lab, (170, 190, 220), (bx, r.y + 4), shadow=False)
        self.txt(self.f_xs, "L", (170, 190, 220), (r.x + 88, r.bottom - 22), shadow=False)
        self.txt(self.f_xs, "R", (170, 190, 220), (r.x + 198, r.bottom - 22), shadow=False)

    def draw_title(self):
        W_, H_ = self.RW, self.RH
        self.txt(self.f_big, "D R O N E   S I M", (255, 255, 255), (W_ // 2, 46), "midtop")
        self.txt(self.f_sm, "FPV quadcopter flight over a living city", (225, 235, 250), (W_ // 2, 118), "midtop")
        y = 150
        for i, m in enumerate(MISSIONS):
            sel = i == self.mission_i
            mc = tuple(int(v * 255) for v in m["color"]) if self.unlocked(i) else (120, 120, 130)
            r = pygame.Rect(W_ // 2 - 330, y, 660, 70 if sel else 40)
            self.panel(r, 190 if sel else 120, 12, mc if sel else None)
            self.txt(self.f_med if sel else self.f_sm, m["name"], mc, (r.x + 22, r.y + (8 if sel else 9)))
            hi = self.hi.get(m["id"], {})
            if not self.unlocked(i):
                self.txt(self.f_xs, "LOCKED", (170, 170, 180), (r.right - 20, r.y + 14), "topright")
            elif m["time_limit"] > 0:
                st = hi.get("stars", 0)
                self.draw_stars(r.right - 110, r.y + 12, st, 9)
                if hi.get("score"):
                    self.txt(self.f_xs, f"BEST {hi['score']}", (255, 220, 120), (r.right - 124, r.y + 14), "topright")
            if sel:
                self.txt(self.f_sm, m["desc"] if self.unlocked(i) else
                         f"Finish {MISSIONS[i - 1]['name']} to unlock.", (225, 230, 245), (r.x + 22, r.y + 42))
            y += r.h + 6
        maxs = 3 * sum(1 for m in MISSIONS if m["time_limit"] > 0)
        self.txt(self.f_sm, f"STARS {self.total_stars()} / {maxs}", (255, 220, 120), (W_ - 30, 60), "topright")
        hint = "UP / DOWN or either stick: choose     ENTER / right click: select     ESC: quit"
        self.txt(self.f_sm, hint, (225, 235, 250), (W_ // 2, H_ - 70), "midtop")
        status = []
        if self.pad:
            status.append(f"Gamepad: {self.pad.get_name()}")
        if self.ser:
            status.append(f"Arduino: {self.ser.status}")
        self.txt(self.f_xs, "   |   ".join(status) or "No pad - keyboard / mouse", (160, 210, 255), (W_ // 2, H_ - 38), "midtop")

    def draw_stars(self, x, y, n, size=12, total=3):
        for i in range(total):
            cx, cy = x + i * size * 2.6, y + size
            pts = []
            for k in range(10):
                a = -math.pi / 2 + k * math.pi / 5
                rr = size if k % 2 == 0 else size * 0.45
                pts.append((cx + math.cos(a) * rr, cy + math.sin(a) * rr))
            pygame.draw.polygon(self.screen, (255, 210, 60) if i < n else (70, 74, 88), pts)

    def draw_briefing(self):
        W_, H_ = self.RW, self.RH
        m = MISSIONS[self.mission_i]
        mc = tuple(int(v * 255) for v in m["color"])
        r = pygame.Rect(W_ // 2 - 460, 40, 920, 640)
        self.panel(r, 200, 16, mc)
        self.txt(self.f_big, m["name"], mc, (W_ // 2, 54), "midtop")
        self.txt(self.f_sm, m["desc"], (230, 235, 245), (W_ // 2, 126), "midtop")
        lines = [
            ("PAD / ARDUINO", ""),
            *(([("Left stick", "up = fly forward   down = back   left/right = turn"),
                ("Right click", "HOLD = climb"), ("Left click", "HOLD = descend")])
              if self.left_only() else [("Left stick", "up/down = climb / descend      left/right = turn (yaw)")]),
            ("Right stick", "up/down = fly forward / back   left/right = slide sideways"),
            ("Left click", "tap = camera   double = restart   hold = TURBO"),
            ("Right click", "tap = stabilize   double = pause   hold = PRECISION"),
            ("Both clicks", "pause"),
            ("CHALLENGE", ""),
            ("Stars", "1 = finish   2 = 20% time left, no clipped gates   3 = 40% left + battery 25%+"),
            ("Survive", f"wind {m['wind']:.0f} m/s + gusts   battery drains with throttle, checkpoints recharge it"),
            ("KEYBOARD", ""),
            ("Move", "W/S forward-back   A/D sideways   Space/Up climb   Shift/Down descend"),
            ("Turn", "Q/E or Left/Right"),
            ("Other", "C camera   L stabilize   R restart   hold Tab turbo   hold X precision   P pause"),
        ]
        y = 164
        for a, b in lines:
            if not b:
                self.txt(self.f_sm, a, mc, (r.x + 50, y))
            else:
                self.txt(self.f_sm, a, (255, 255, 255), (r.x + 70, y))
                self.txt(self.f_sm, b, (200, 215, 240), (r.x + 230, y))
            y += 29
        self.txt(self.f_med, "ENTER / right click: launch      ESC / left click: back", (255, 255, 255),
                 (W_ // 2, r.bottom - 56), "midtop")

    def draw_done(self):
        W_, H_ = self.RW, self.RH
        if self.done_t < 0.9:
            return
        a = int(min(160, (self.done_t - 0.9) * 400))
        s = pygame.Surface((W_, H_), pygame.SRCALPHA)
        s.fill((0, 0, 0, a))
        self.screen.blit(s, (0, 0))
        title = {"win": "MISSION COMPLETE", "lose": "TIME'S UP", "crash": "CRASHED",
                 "battery": "BATTERY DEAD"}[self.result]
        col = {"win": (120, 255, 160), "lose": (255, 200, 90), "crash": (255, 90, 90),
               "battery": (255, 160, 80)}[self.result]
        if self.result == "win" and MISSIONS[self.mission_i]["time_limit"] > 0:
            self.draw_stars(W_ // 2 - 52, H_ // 2 - 170, self.stars, 18)
            if not getattr(self, "star_sound_done", False) and self.done_t > 1.0:
                self.star_sound_done = True
                for _ in range(self.stars):
                    self.sfx.play("star")
        self.txt(self.f_big, title, col, (W_ // 2, H_ // 2 - 110), "midtop")
        self.txt(self.f_med, f"SCORE {self.score}      TIME {self.elapsed:.1f}s", (255, 255, 255), (W_ // 2, H_ // 2 - 20), "midtop")
        if self.new_best:
            self.txt(self.f_med, "NEW BEST!", (255, 220, 120), (W_ // 2, H_ // 2 + 24), "midtop")
        self.txt(self.f_sm, "ENTER / right click: retry      ESC / left click: missions", (230, 230, 240),
                 (W_ // 2, H_ // 2 + 80), "midtop")

    def draw_pause(self):
        W_, H_ = self.RW, self.RH
        s = pygame.Surface((W_, H_), pygame.SRCALPHA)
        s.fill((0, 0, 0, 140))
        self.screen.blit(s, (0, 0))
        self.txt(self.f_big, "PAUSED", (255, 255, 255), (W_ // 2, H_ // 2 - 60), "midtop")
        self.txt(self.f_sm, "ESC / right click: resume      Q / left click: missions", (220, 220, 230),
                 (W_ // 2, H_ // 2 + 20), "midtop")

    def draw(self):
        self.draw_scene()
        s = self.state
        if s == "title":
            self.draw_title()
        elif s == "briefing":
            self.draw_briefing()
        else:
            self.draw_hud()
            if s == "countdown":
                n = 3 - int(self.count_t / 0.8)
                self.txt(self.f_big, str(n) if n > 0 else "GO!", (255, 255, 255), (self.RW // 2, self.RH // 2 - 90), "midtop")
            elif s == "pause":
                self.draw_pause()
            elif s == "done":
                self.draw_done()
        pygame.display.flip()

    # ------------------------------------------------------------ main loop
    def run(self, frames=None):
        n = 0
        while frames is None or n < frames:
            dt = self.clock.tick(60) / 1000.0
            t0 = time.perf_counter()
            for e in pygame.event.get():
                self.handle(e)
            self.update(dt)
            self.draw()
            self.auto_quality((time.perf_counter() - t0) * 1000)
            n += 1


# =====================================================================
#  Joystick / Arduino pad tester
# =====================================================================
def joytest():
    """Print live stick / click values (USB gamepads AND the Arduino serial pad)."""
    pygame.init()
    pygame.joystick.init()
    pads = [pygame.joystick.Joystick(i) for i in range(pygame.joystick.get_count())]
    for p in pads:
        print(f"USB pad: {p.get_name()}  axes={p.get_numaxes()} buttons={p.get_numbuttons()} hats={p.get_numhats()}")
    if not pads:
        print("No USB gamepad (normal for an Arduino UNO - it talks over a COM port instead).")
    if "--serial" in sys.argv:
        C["arduino"]["port"] = sys.argv[sys.argv.index("--serial") + 1]
    sp = SerialPad(C["arduino"]) if C["arduino"]["enabled"] else None
    print("Leave the sticks centred for 2 seconds while the Arduino is found. Ctrl+C to quit.")
    print("Expected: LEFT up -> ly negative, LEFT right -> lx positive; same for the RIGHT stick (rx, ry).\n")
    clock, last, last_status = pygame.time.Clock(), None, None
    try:
        while True:
            pygame.event.pump()
            if sp and sp.status != last_status:
                print("Arduino:", sp.status)
                last_status = sp.status
            cur = []
            if pads:
                p = pads[0]
                cur.append("USB axes %s pressed %s" % ([round(p.get_axis(i), 1) for i in range(p.get_numaxes())],
                                                        [i for i in range(p.get_numbuttons()) if p.get_button(i)]))
            if sp and sp.ready:
                names = ("lx", "ly", "rx", "ry")[:sp.n_axes]
                cur.append(f"ARDUINO ({sp.n_axes // 2} stick) " +
                           "  ".join(f"{n}={sp.axis(i):+.1f}" for i, n in enumerate(names)) +
                           "  clicks %s" % [i for i in range(sp.num_buttons()) if sp.button(i)] +
                           f"   raw: {sp.last_line}")
            line = " | ".join(cur)
            if line and line != last:
                print(line)
                last = line
            clock.tick(20)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    load_config(arg_value("--config"))
    if "--joytest" in sys.argv:
        joytest()
    else:
        Game().run()
