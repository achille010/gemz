#!/usr/bin/env python3
"""
DRONE SIM - a hyper-realistic-feel FPV drone flight simulator. pygame + numpy
(software rendered, no external assets).

Fly a momentum-based quadcopter through five challenges: blast through gate
rings against the clock, thread a low slalom course, chase altitude targets,
nail a soft precision landing, or just cruise the open world in Free Flight.

Move with WASD/arrows/gamepad/Arduino two-stick pad. SPACE start / confirm,
ESC back / pause.
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
    "fov_degrees": 72,
    "fullscreen": False,
    "draw_distance": 260,
    "sound": True,
    # --- two-stick lab pad: each stick only ever gives you 3 usable signals
    #     (UP, DOWN, CLICK) - 6 signals total, and EVERY one of them does something
    #     different on screen. Run `python drone_sim.py --joytest` (or gamepad_test.bat),
    #     wiggle each stick and click it, and copy the axis / button numbers below.
    #
    #     LEFT CLICK  toggles the flight MODE (shown in the HUD):
    #       FLY mode   (default)   LEFT stick = throttle up/down    RIGHT stick = forward/back
    #       STEER mode (after clicking LEFT stick once)
    #                              LEFT stick = yaw left/right      RIGHT stick = strafe left/right
    #     RIGHT CLICK  always STABILIZES: kills tilt & drift dead - a real "panic button".
    #     Click LEFT again to flip back to FLY mode. That is 6 signals -> 6 distinct effects.
    "gamepad": {
        "axis_throttle": 1, "axis_pitch": 3,   # the Y (up/down) axis of the LEFT / RIGHT stick
        "invert_throttle": True,               # True: pushing stick up (negative axis) climbs / yaws / strafes "up"
        "invert_pitch": True,                  # True: pushing stick up moves forward / strafes right
        "deadzone": 0.14,
        "digital_thresh": 0.5,                 # how far a stick must be pushed to register as UP or DOWN
        "btn_mode": 0,                         # LEFT stick click : toggle FLY <-> STEER mode
        "btn_stabilize": 1,                    # RIGHT stick click: kill tilt & drift (always works)
    },
    # --- Arduino over a serial cable (Uno / Nano / ESP32 ... anything without native USB gamepad).
    #     Set a port here ("COM5") or start with:  python drone_sim.py --serial COM5
    "serial": {"port": None, "baud": 115200},
}
C = CONFIG

G = 15.0                    # gravity (world units / s^2)
THROTTLE_RANGE = G * 1.15   # extra thrust above/below hover available from stick
MAX_TILT = 0.60             # radians, full stick tilt (~34 deg)
TILT_RESPONSE = 7.0         # how snappily the airframe leans into a tilt command
YAW_RATE = 2.4              # rad/s at full yaw stick
DRAG_H = 0.85               # horizontal air drag
DRAG_V = 1.35               # vertical air drag
GROUND_Y = 0.0

WORLD_UP = np.array([0.0, 1.0, 0.0])


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


# =====================================================================
#  Sound (synthesised, no external assets)
# =====================================================================
class Sfx:
    def __init__(self, enabled):
        self.ok = False
        self.snd = {}
        self.eng_ch = None
        if not enabled:
            return
        try:
            pygame.mixer.init(44100, -16, 1, 512)
            pygame.mixer.set_num_channels(14)
            self.ok = True
            sr = 44100
            rng = np.random.default_rng(11)

            def tone(freqs, dur, vol=0.35, decay=6.0, noise=0.0, sweep=0.0):
                t = np.arange(int(sr * dur)) / sr
                w = sum(np.sin(2 * np.pi * (f * (1 + sweep * t)) * t) for f in freqs) / len(freqs)
                env = np.exp(-decay * t)
                return np.clip((w * vol + noise * rng.standard_normal(len(t))) * env, -1, 1)

            def mk(w):
                return pygame.sndarray.make_sound((np.clip(w, -1, 1) * 32767).astype(np.int16))

            self.snd["gate"] = mk(np.concatenate([tone([f], 0.09, 0.30, 8) for f in (784, 1175)]))
            self.snd["combo"] = mk(np.concatenate([tone([f, f * 1.5], 0.10, 0.28, 7) for f in (523, 659, 880, 1046)]))
            self.snd["land"] = mk(tone([440, 660], 0.5, 0.35, 3.2, 0.05, sweep=0.4))
            self.snd["fail"] = mk(tone([160], 0.4, 0.4, 6, 0.15))
            self.snd["crash"] = mk(tone([70, 45], 1.2, 0.8, 2.4, 0.75, sweep=-0.3))
            self.snd["start"] = mk(tone([220, 440], 0.55, 0.4, 3, 0.05, sweep=1.4))
            self.snd["ui"] = mk(tone([700], 0.06, 0.25, 20))
            # engine hum: motor whine (bandy noise) that we pitch/volume-shift live
            n = sr * 2
            t = np.arange(n) / sr
            raw = rng.standard_normal(n)
            k = 40
            wind = np.convolve(raw, np.ones(k) / k, "same")
            self.eng_base = mk(0.35 * wind * 3.0 + 0.18 * np.sin(2 * np.pi * 220 * t) +
                                0.10 * np.sin(2 * np.pi * 330 * t))
        except Exception:
            self.ok = False

    def play(self, name, vol=1.0):
        if self.ok and name in self.snd:
            ch = self.snd[name].play()
            if ch:
                ch.set_volume(vol)

    def engine(self, throttle01, speed01):
        if not self.ok:
            return
        if self.eng_ch is None or not self.eng_ch.get_busy():
            self.eng_ch = self.eng_base.play(loops=-1)
        if self.eng_ch:
            vol = clampv(0.10 + 0.30 * throttle01 + 0.15 * speed01, 0.0, 0.7)
            self.eng_ch.set_volume(vol)

    def stop_engine(self):
        if self.eng_ch:
            self.eng_ch.stop()
            self.eng_ch = None


# =====================================================================
#  Arduino two-stick pad on a serial port: lines like  J,512,498,530,511,0,1
#  (left X, left Y, right X, right Y, left click, right click; raw 0-1023 ADC values)
# =====================================================================
class SerialPad:
    def __init__(self, port, baud):
        import serial          # pip install pyserial
        import threading
        self.ser = serial.Serial(port, baud, timeout=0.1)
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
            self.parse(line)

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
#  World: buildings, checkpoints, missions
# =====================================================================
def make_buildings(rng, n, spread, avoid):
    out = []
    for _ in range(n):
        for _try in range(20):
            x = (rng.random() * 2 - 1) * spread
            z = (rng.random() * 2 - 1) * spread
            ok = True
            for (ax, az, ar) in avoid:
                if (x - ax) ** 2 + (z - az) ** 2 < ar * ar:
                    ok = False
                    break
            if ok:
                break
        w = 4 + rng.random() * 7
        d = 4 + rng.random() * 7
        h = 8 + rng.random() * 46
        hue = rng.random()
        col = (int(40 + 50 * hue), int(50 + 40 * (1 - hue)), int(70 + 60 * rng.random()))
        out.append({"x": x, "z": z, "w": w, "d": d, "h": h, "col": col})
    return out


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
        y = clampv(y + (rng.random() - 0.5) * 14, 4, 55)
        pts.append(cp((x, y, z), 5.5, "gate", label=f"GATE {i + 1}"))
    return pts


def build_slalom(rng):
    pts = []
    z = 18.0
    side = 1
    for i in range(14):
        z += 12 + rng.random() * 3
        x = side * (8 + rng.random() * 3)
        side *= -1
        y = 4 + rng.random() * 3
        pts.append(cp((x, y, z), 3.6, "pole", label=f"POLE {i + 1}"))
    return pts


def build_altitude_ace(rng):
    targets = [18, 36, 55, 34, 70]
    return [cp((0.0, y, 0.0), 4.0, "altitude", hold=2.0, label=f"{y:.0f} m") for y in targets]


def build_precision_landing(rng):
    return [cp((26.0, 0.0, -34.0), 4.5, "land", hold=1.4, label="LANDING PAD")]


MISSIONS = [
    {"id": "ring_rush", "name": "RING RUSH", "color": (0.10, 0.95, 1.00), "time_limit": 80,
     "desc": "Blast through all 10 gates before the clock runs out.", "builder": build_ring_rush},
    {"id": "slalom", "name": "SLALOM SPRINT", "color": (1.00, 0.75, 0.10), "time_limit": 50,
     "desc": "Weave through 14 poles low and fast. No room for wobble.", "builder": build_slalom},
    {"id": "altitude_ace", "name": "ALTITUDE ACE", "color": (0.65, 0.40, 1.00), "time_limit": 100,
     "desc": "Climb to each ring and hold your altitude for 2 seconds.", "builder": build_altitude_ace},
    {"id": "precision_landing", "name": "PRECISION LANDING", "color": (0.20, 1.00, 0.45), "time_limit": 45,
     "desc": "Fly to the pad and set down soft and centred.", "builder": build_precision_landing},
    {"id": "free_flight", "name": "FREE FLIGHT", "color": (1.00, 1.00, 1.00), "time_limit": 0,
     "desc": "No clock, no crashing worries beyond pride. Just fly.", "builder": lambda rng: []},
]


# =====================================================================
#  Drone physics
# =====================================================================
class Drone:
    def __init__(self):
        self.reset()

    def reset(self, pos=(0.0, 12.0, 0.0), yaw=0.0):
        self.pos = np.array(pos, dtype=float)
        self.vel = np.zeros(3)
        self.yaw = yaw
        self.pitch_tilt = 0.0
        self.roll_tilt = 0.0
        self.alive = True
        self.landed = False

    def update(self, dt, throttle_in, yaw_in, pitch_in, roll_in):
        tgt_pitch = pitch_in * MAX_TILT
        tgt_roll = roll_in * MAX_TILT
        k = clampv(dt * TILT_RESPONSE, 0, 1)
        self.pitch_tilt = lerp(self.pitch_tilt, tgt_pitch, k)
        self.roll_tilt = lerp(self.roll_tilt, tgt_roll, k)
        self.yaw += yaw_in * YAW_RATE * dt

        thrust_mag = G + throttle_in * THROTTLE_RANGE
        vertical = thrust_mag * math.cos(self.pitch_tilt) * math.cos(self.roll_tilt)
        forward = thrust_mag * math.sin(self.pitch_tilt)
        lateral = thrust_mag * math.sin(self.roll_tilt)

        fwd = heading_vec(self.yaw)
        rgt = right_vec(self.yaw)
        accel = WORLD_UP * (vertical - G) + fwd * forward + rgt * lateral

        self.vel += accel * dt
        self.vel[0] *= max(0.0, 1 - DRAG_H * dt)
        self.vel[2] *= max(0.0, 1 - DRAG_H * dt)
        self.vel[1] *= max(0.0, 1 - DRAG_V * dt)
        self.pos += self.vel * dt

    @property
    def speed(self):
        return float(np.linalg.norm(self.vel))


def project(cam_pos, cam_yaw, cam_pitch, focal, RW, RH, p):
    rel = p - cam_pos
    cy, sy = math.cos(-cam_yaw), math.sin(-cam_yaw)
    x = rel[0] * cy - rel[2] * sy
    z = rel[0] * sy + rel[2] * cy
    y = rel[1]
    cp_, sp = math.cos(-cam_pitch), math.sin(-cam_pitch)
    y2 = y * cp_ - z * sp
    z2 = y * sp + z * cp_
    if z2 < 0.15:
        return None
    sx = RW / 2 + x / z2 * focal
    sy = RH / 2 - y2 / z2 * focal
    return (sx, sy, z2)


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
        self.focal = (self.RW / 2) / math.tan(math.radians(C["fov_degrees"]) / 2)
        self.sfx = Sfx(C["sound"])
        self.f_big = pygame.font.SysFont("bahnschrift,consolas,arial", 64, bold=True)
        self.f_med = pygame.font.SysFont("bahnschrift,consolas,arial", 30, bold=True)
        self.f_sm = pygame.font.SysFont("bahnschrift,consolas,arial", 19)
        self.hi_path = os.path.join(HERE, "highscore.json")
        self.hi = self._load_hi()
        self.state = "title"
        self.mission_i = 0
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
            try:
                self.pad = pygame.joystick.Joystick(0)
            except pygame.error:
                self.pad = None
        self.rng = random.Random()
        self.cam_yaw = 0.0
        self.cam_pitch = -0.22
        self.cam_pos = np.zeros(3)
        self.shake = 0.0
        self.popups = []
        self.control_mode = "fly"          # "fly" (throttle+forward) <-> "steer" (yaw+strafe)
        self.stabilize_flash = 0.0
        self.mouse_stick = [0.0, 0.0]      # virtual analog stick built from touchpad/mouse motion
        self.load_mission(0)

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

    def digital(self, n, invert):
        """UP -> +1, DOWN -> -1, centred -> 0 - the lab pad only ever gives us that."""
        g = C["gamepad"]
        v = self.axis(n) * (-1 if invert else 1)
        if v > g["digital_thresh"]:
            return 1.0
        if v < -g["digital_thresh"]:
            return -1.0
        return 0.0

    def get_controls(self):
        if self.pad or self.ser:
            return self.get_pad_controls()
        return self.get_keyboard_mouse_controls()

    def get_pad_controls(self):
        g = C["gamepad"]
        left = self.digital(g["axis_throttle"], g["invert_throttle"])   # LEFT stick up/down
        right = self.digital(g["axis_pitch"], g["invert_pitch"])        # RIGHT stick up/down
        if self.control_mode == "fly":
            return (left, 0.0, right, 0.0)          # throttle, yaw, pitch, roll
        return (0.0, left, 0.0, right)               # hover, yaw, level, strafe

    def get_keyboard_mouse_controls(self):
        keys = pygame.key.get_pressed()
        yaw_in = float((keys[pygame.K_RIGHT] or keys[pygame.K_e]) - (keys[pygame.K_LEFT] or keys[pygame.K_q]))
        throttle_in = float((keys[pygame.K_SPACE] or keys[pygame.K_UP]) -
                             (keys[pygame.K_LSHIFT] or keys[pygame.K_DOWN]))
        pitch_in = float(keys[pygame.K_w]) - float(keys[pygame.K_s])
        roll_in = float(keys[pygame.K_d]) - float(keys[pygame.K_a])

        # touchpad / mouse: drag builds a spring-loaded virtual stick for pitch+roll
        if self.state == "play":
            mx, my = pygame.mouse.get_rel()
            self.mouse_stick[0] = clampv(self.mouse_stick[0] + mx * 0.006, -1, 1)
            self.mouse_stick[1] = clampv(self.mouse_stick[1] + my * 0.006, -1, 1)
            self.mouse_stick[0] *= 0.90
            self.mouse_stick[1] *= 0.90
            if abs(self.mouse_stick[0]) > 0.05:
                roll_in = clampv(roll_in + self.mouse_stick[0], -1, 1)
            if abs(self.mouse_stick[1]) > 0.05:
                pitch_in = clampv(pitch_in - self.mouse_stick[1], -1, 1)
            buttons = pygame.mouse.get_pressed(3)
            if buttons[0]:
                throttle_in = clampv(throttle_in + 1, -1, 1)
            if buttons[2]:
                throttle_in = clampv(throttle_in - 1, -1, 1)
        return (clampv(throttle_in, -1, 1), clampv(yaw_in, -1, 1),
                clampv(pitch_in, -1, 1), clampv(roll_in, -1, 1))

    # ------------------------------------------------------------ mission setup
    def load_mission(self, i):
        self.mission_i = i % len(MISSIONS)
        m = MISSIONS[self.mission_i]
        rng = random.Random(hash(m["id"]) & 0xFFFF)
        self.checkpoints = m["builder"](rng)
        avoid = [(0, 0, 14)] + [(c["pos"][0], c["pos"][2], c["r"] + 8) for c in self.checkpoints]
        if m["id"] == "precision_landing":
            avoid.append((self.checkpoints[0]["pos"][0], self.checkpoints[0]["pos"][2], 10))
        self.buildings = make_buildings(rng, 34, 140, avoid)
        self.pad_pos = np.array([0.0, 0.0, 0.0])
        self.ready_run()

    def ready_run(self):
        self.drone = Drone()
        self.drone.reset(pos=(0.0, 8.0, -4.0), yaw=0.0)
        self.cp_i = 0
        self.hold_t = 0.0
        self.elapsed = 0.0
        self.combo = 0
        self.score = 0
        self.time_left = MISSIONS[self.mission_i]["time_limit"]
        self.result = None   # "win" / "lose" / "crash"
        self.popups = []
        self.control_mode = "fly"
        self.mouse_stick = [0.0, 0.0]
        self.cam_pos = self.drone.pos.copy()
        self.cam_yaw = self.drone.yaw

    def start_mission(self):
        self.ready_run()
        self.state = "play"
        pygame.mouse.get_rel()   # clear any accumulated touchpad/mouse motion
        self.sfx.play("start")

    # ------------------------------------------------------------ events
    def handle(self, e):
        if e.type == pygame.QUIT:
            self.quit()
        if e.type == pygame.JOYBUTTONDOWN and self.pad:
            g = C["gamepad"]
            if e.button == g["btn_mode"]:
                if self.state == "play":
                    self.toggle_mode()
                elif self.state in ("title", "briefing"):
                    self.start_mission()
                elif self.state == "pause":
                    self.state = "play"
                elif self.state == "done":
                    self.start_mission()
            elif e.button == g["btn_stabilize"]:
                if self.state == "play":
                    self.stabilize()
                elif self.state == "pause":
                    self.state = "title"
        if e.type == pygame.WINDOWFOCUSLOST and self.state == "play":
            self.state = "pause"
        if e.type != pygame.KEYDOWN:
            return
        k = e.key
        if self.state == "title":
            if k in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_KP_ENTER):
                self.state = "briefing"
                self.sfx.play("ui")
            elif k in (pygame.K_UP, pygame.K_w):
                self.load_mission(self.mission_i - 1)
                self.sfx.play("ui")
            elif k in (pygame.K_DOWN, pygame.K_s):
                self.load_mission(self.mission_i + 1)
                self.sfx.play("ui")
            elif k == pygame.K_ESCAPE:
                self.quit()
        elif self.state == "briefing":
            if k in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_KP_ENTER):
                self.start_mission()
            elif k == pygame.K_ESCAPE:
                self.state = "title"
        elif self.state == "play":
            if k in (pygame.K_ESCAPE, pygame.K_p):
                self.state = "pause"
                self.sfx.stop_engine()
            elif k == pygame.K_r:
                self.ready_run()
            elif k == pygame.K_l:
                self.stabilize()
            elif k == pygame.K_TAB:
                self.toggle_mode()
        elif self.state == "pause":
            if k in (pygame.K_ESCAPE, pygame.K_p, pygame.K_SPACE):
                self.state = "play"
            elif k == pygame.K_q:
                self.sfx.stop_engine()
                self.state = "title"
        elif self.state == "done":
            if k in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_r):
                self.start_mission()
            elif k == pygame.K_ESCAPE:
                self.sfx.stop_engine()
                self.state = "title"

    def quit(self):
        pygame.quit()
        sys.exit()

    def toggle_mode(self):
        self.control_mode = "steer" if self.control_mode == "fly" else "fly"
        self.sfx.play("ui")
        label = "STEER: yaw + strafe" if self.control_mode == "steer" else "FLY: throttle + forward"
        self.popups.append((1.2, f"MODE -> {label}", (0.4, 0.9, 1.0)))

    def stabilize(self):
        self.drone.pitch_tilt = self.drone.roll_tilt = 0.0
        self.drone.vel *= 0.35
        self.stabilize_flash = 0.35
        self.sfx.play("ui")
        self.popups.append((0.9, "STABILIZED", (0.6, 1.0, 0.7)))

    # ------------------------------------------------------------ update
    def update(self, dt):
        dt = min(dt, 0.033)
        self.shake = max(0.0, self.shake - dt * 2.5)
        self.stabilize_flash = max(0.0, self.stabilize_flash - dt)
        self.popups = [(t - dt, s, c) for (t, s, c) in self.popups if t - dt > 0]
        if self.ser:
            for btn in self.ser.pressed():
                if self.state == "play":
                    if btn == 0:
                        self.toggle_mode()
                    else:
                        self.stabilize()
                elif self.state in ("title", "briefing", "done") and btn == 0:
                    self.start_mission()
        if self.state != "play":
            return
        thr, yaw, pit, rol = self.get_controls()
        d = self.drone
        d.update(dt, thr, yaw, pit, rol)
        self.elapsed += dt
        m = MISSIONS[self.mission_i]
        if m["time_limit"] > 0:
            self.time_left -= dt
        self.sfx.engine(clampv((thr + 1) / 2, 0, 1), clampv(d.speed / 30, 0, 1))

        # ground / building collisions
        crashed = False
        if d.pos[1] <= GROUND_Y:
            landing_pad = m["id"] == "precision_landing" and self.cp_i >= len(self.checkpoints)
            soft = abs(d.vel[1]) < 4.0 and math.hypot(d.vel[0], d.vel[2]) < 3.0
            if soft:
                d.pos[1] = GROUND_Y
                d.vel[:] = 0
            else:
                crashed = True
        for b in self.buildings:
            hw, hd = b["w"] / 2, b["d"] / 2
            if (abs(d.pos[0] - b["x"]) < hw + 0.6 and abs(d.pos[2] - b["z"]) < hd + 0.6
                    and d.pos[1] < b["h"] + 0.6):
                crashed = True
                break
        if crashed and d.alive:
            d.alive = False
            self.shake = 1.0
            self.sfx.play("crash")
            self.sfx.stop_engine()
            self.result = "crash"
            self.state = "done"
            self._maybe_hi()

        if d.alive:
            self.update_checkpoints(dt)
            if m["time_limit"] > 0 and self.time_left <= 0 and self.result is None:
                self.result = "lose"
                self.state = "done"
                self.sfx.play("fail")
                self.sfx.stop_engine()
                self._maybe_hi()

        self.update_camera(dt)

    def update_checkpoints(self, dt):
        if self.cp_i >= len(self.checkpoints):
            return
        c = self.checkpoints[self.cp_i]
        d = self.drone
        dist = float(np.linalg.norm(d.pos - c["pos"]))
        inside = dist < c["r"]
        if c["kind"] == "land":
            inside = (math.hypot(d.pos[0] - c["pos"][0], d.pos[2] - c["pos"][2]) < c["r"]
                      and d.pos[1] < 1.2 and abs(d.vel[1]) < 3.0 and math.hypot(d.vel[0], d.vel[2]) < 2.0)
        if c["hold"] > 0:
            if inside:
                self.hold_t += dt
                if self.hold_t >= c["hold"]:
                    self.pass_checkpoint(c)
            else:
                self.hold_t = 0.0
        else:
            if inside:
                self.pass_checkpoint(c)

    def pass_checkpoint(self, c):
        self.cp_i += 1
        self.hold_t = 0.0
        self.combo += 1
        gain = 100 + self.combo * 20
        self.score += gain
        if self.combo > 1:
            self.sfx.play("combo", 0.8)
        else:
            self.sfx.play("gate", 0.9)
        self.popups.append((1.4, f"{c['label']}  +{gain}", (1.0, 0.95, 0.3)))
        if self.cp_i >= len(self.checkpoints):
            if c["kind"] == "land":
                self.score += int(max(0, self.time_left) * 12)
                self.sfx.play("land")
            else:
                self.score += int(max(0, self.time_left) * 8)
                self.sfx.play("combo", 1.0)
            self.result = "win"
            self.state = "done"
            self.sfx.stop_engine()
            self._maybe_hi()

    def _maybe_hi(self):
        mid = MISSIONS[self.mission_i]["id"]
        prev = self.hi.get(mid, {}).get("score", 0)
        if self.score > prev:
            self.hi[mid] = {"score": self.score, "time": round(self.elapsed, 1)}
            self._save_hi()

    def update_camera(self, dt):
        d = self.drone
        k = clampv(dt * 5.0, 0, 1)
        self.cam_yaw = lerp_angle(self.cam_yaw, d.yaw, k)
        target_pitch = -0.22 - d.pitch_tilt * 0.35
        self.cam_pitch = lerp(self.cam_pitch, target_pitch, clampv(dt * 4, 0, 1))
        back = heading_vec(self.cam_yaw)
        desired = d.pos - back * 9.0 + WORLD_UP * 3.2
        self.cam_pos = self.cam_pos + (desired - self.cam_pos) * clampv(dt * 6.0, 0, 1)
        if self.cam_pos[1] < d.pos[1] * 0.0 + 0.6:
            self.cam_pos[1] = max(self.cam_pos[1], 0.6)

    # ------------------------------------------------------------ drawing
    def proj(self, p):
        return project(self.cam_pos, self.cam_yaw, self.cam_pitch, self.focal, self.RW, self.RH, p)

    def draw_sky(self):
        top = (18, 22, 46)
        bot = (110, 150, 200)
        horizon = self.RH * 0.5 - self.cam_pitch * self.focal * 0.6
        horizon = clampv(horizon, -80, self.RH + 80)
        for y in range(0, self.RH, 4):
            if y > horizon:
                break
            t = clampv(y / max(horizon, 1), 0, 1)
            col = tuple(int(lerp(top[i], bot[i], t)) for i in range(3))
            pygame.draw.rect(self.screen, col, (0, y, self.RW, 4))
        if horizon < self.RH:
            pygame.draw.rect(self.screen, (34, 46, 30), (0, int(horizon), self.RW, self.RH - int(horizon)))

    def draw_ground(self):
        TILE = 16
        N = 12
        cx = round(self.cam_pos[0] / TILE)
        cz = round(self.cam_pos[2] / TILE)
        quads = []
        for ix in range(-N, N + 1):
            for iz in range(-N, N + 1):
                wx = (cx + ix) * TILE
                wz = (cz + iz) * TILE
                pts = [self.proj(np.array([wx, 0, wz])),
                       self.proj(np.array([wx + TILE, 0, wz])),
                       self.proj(np.array([wx + TILE, 0, wz + TILE])),
                       self.proj(np.array([wx, 0, wz + TILE]))]
                if any(p is None for p in pts):
                    continue
                depth = sum(p[2] for p in pts) / 4
                if depth > C["draw_distance"]:
                    continue
                parity = (cx + ix + cz + iz) % 2
                base = (34, 92, 46) if parity == 0 else (28, 78, 40)
                fog = clampv(depth / C["draw_distance"], 0, 1) ** 1.4
                col = tuple(int(lerp(base[i], (110, 150, 200)[i], fog)) for i in range(3))
                quads.append((depth, [(p[0], p[1]) for p in pts], col))
        quads.sort(key=lambda q: -q[0])
        for _, poly, col in quads:
            pygame.draw.polygon(self.screen, col, poly)

    def draw_building(self, b):
        x, z, w, d_, h = b["x"], b["z"], b["w"], b["d"], b["h"]
        hw, hd = w / 2, d_ / 2
        corners = [(x - hw, z - hd), (x + hw, z - hd), (x + hw, z + hd), (x - hw, z + hd)]
        faces = []
        top = [self.proj(np.array([cx, h, cz])) for cx, cz in corners]
        if all(p for p in top):
            faces.append((sum(p[2] for p in top) / 4, "face", ([(p[0], p[1]) for p in top],
                          tuple(min(255, c + 25) for c in b["col"]))))
        for i in range(4):
            x0, z0 = corners[i]
            x1, z1 = corners[(i + 1) % 4]
            nx, nz = z1 - z0, -(x1 - x0)
            to_cam = np.array([self.cam_pos[0] - (x0 + x1) / 2, 0, self.cam_pos[2] - (z0 + z1) / 2])
            if nx * to_cam[0] + nz * to_cam[2] < 0:
                continue
            pts = [self.proj(np.array([x0, 0, z0])), self.proj(np.array([x1, 0, z1])),
                   self.proj(np.array([x1, h, z1])), self.proj(np.array([x0, h, z0]))]
            if any(p is None for p in pts):
                continue
            depth = sum(p[2] for p in pts) / 4
            if depth > C["draw_distance"] * 1.1:
                continue
            shade = 0.55 + 0.35 * (i % 2)
            col = tuple(int(c * shade) for c in b["col"])
            faces.append((depth, "face", ([(p[0], p[1]) for p in pts], col)))
        return faces

    def ring_points(self, center, normal, r, n=18):
        normal = normal / (np.linalg.norm(normal) + 1e-9)
        up = WORLD_UP if abs(normal[1]) < 0.95 else np.array([1.0, 0.0, 0.0])
        u = np.cross(up, normal)
        u = u / (np.linalg.norm(u) + 1e-9)
        v = np.cross(normal, u)
        pts = []
        for i in range(n + 1):
            a = i / n * math.tau
            pts.append(center + u * (r * math.cos(a)) + v * (r * math.sin(a)))
        return pts

    def checkpoint_normal(self, i):
        c = self.checkpoints[i]
        if c["kind"] == "altitude" or c["kind"] == "land":
            return np.array([0.0, 1.0, 0.0])
        prev = self.drone.pos if i == 0 else self.checkpoints[i - 1]["pos"]
        nxt = self.checkpoints[i + 1]["pos"] if i + 1 < len(self.checkpoints) else c["pos"]
        d = c["pos"] - prev if np.linalg.norm(c["pos"] - prev) > 0.1 else nxt - c["pos"]
        if np.linalg.norm(d) < 0.01:
            d = np.array([0.0, 0.0, 1.0])
        d[1] = 0
        return d

    def draw_ring(self, pts, col, width=5):
        proj = [self.proj(p) for p in pts]
        if any(p is None for p in proj):
            return None
        depth = sum(p[2] for p in proj) / len(proj)
        xy = [(p[0], p[1]) for p in proj]
        if depth > C["draw_distance"] * 1.3:
            return None
        return (depth, "ring", (xy, col, width))

    def draw_drone_marker(self):
        d = self.drone
        fwd = heading_vec(d.yaw)
        rgt = right_vec(d.yaw)
        cx, cy, cz = d.pos
        arm = 1.1
        pts3d = [d.pos + rgt * arm, d.pos - rgt * arm, d.pos + fwd * arm, d.pos - fwd * arm, d.pos]
        proj = [self.proj(p) for p in pts3d]
        if any(p is None for p in proj):
            return None
        depth = proj[4][2]
        col = (255, 70, 70) if not d.alive else (235, 235, 245)
        return (depth, "drone", ([(p[0], p[1]) for p in proj], col))

    def draw_scene(self):
        self.draw_sky()
        self.draw_ground()
        items = []
        for b in self.buildings:
            items.extend(self.draw_building(b))
        for i, c in enumerate(self.checkpoints):
            passed = i < self.cp_i
            active = i == self.cp_i
            future_far = i > self.cp_i + 2
            if future_far:
                continue
            base_col = MISSIONS[self.mission_i]["color"]
            col = (int(60), int(255), int(120)) if passed else \
                  tuple(int(clampv(v * 255 * (1.3 if active else 0.75), 0, 255)) for v in base_col)
            n = self.checkpoint_normal(i)
            if c["kind"] == "pole":
                base = c["pos"].copy(); base[1] = 0
                top = c["pos"].copy(); top[1] = c["pos"][1] * 2 if c["pos"][1] > 0 else 8
                top[1] = 9
                p0, p1 = self.proj(base), self.proj(top)
                if p0 and p1:
                    d = min(p0[2], p1[2])
                    items.append((d, "pole", ((p0[0], p0[1]), (p1[0], p1[1]), col)))
            elif c["kind"] == "land":
                ring = self.ring_points(c["pos"] + np.array([0, 0.02, 0]), n, c["r"], 24)
                r = self.draw_ring(ring, col, 6)
                if r:
                    items.append(r)
            else:
                ring = self.ring_points(c["pos"], n, c["r"], 20)
                r = self.draw_ring(ring, col, 6 if active else 4)
                if r:
                    items.append(r)
        dm = self.draw_drone_marker()
        if dm:
            items.append(dm)
        items.sort(key=lambda it: -it[0])
        for depth, kind, data in items:
            if kind == "ring":
                xy, col, width = data
                if len(xy) > 2:
                    pygame.draw.lines(self.screen, col, False, xy, width)
            elif kind == "pole":
                a, b, col = data
                pygame.draw.line(self.screen, col, a, b, 6)
            elif kind == "drone":
                xy, col = data
                r_, l_, f_, bck, ctr = xy
                pygame.draw.line(self.screen, col, l_, r_, 4)
                pygame.draw.line(self.screen, col, bck, f_, 4)
                for p in (l_, r_, f_, bck):
                    pygame.draw.circle(self.screen, (255, 210, 60), (int(p[0]), int(p[1])), 4)
                pygame.draw.circle(self.screen, col, (int(ctr[0]), int(ctr[1])), 5)
            else:
                xy, col = data
                pygame.draw.polygon(self.screen, col, xy)
                pygame.draw.polygon(self.screen, (10, 12, 18), xy, 1)

    # ------------------------------------------------------------ HUD / UI
    def txt(self, font, s, col, pos, center=False, shadow=True):
        surf = font.render(s, True, col)
        r = surf.get_rect()
        if center:
            r.center = pos
        else:
            r.topleft = pos
        if shadow:
            sh = font.render(s, True, (0, 0, 0))
            self.screen.blit(sh, (r.x + 2, r.y + 2))
        self.screen.blit(surf, r)
        return r

    def draw_hud(self):
        d = self.drone
        m = MISSIONS[self.mission_i]
        self.txt(self.f_med, m["name"], (255, 255, 255), (18, 14))
        self.txt(self.f_sm, f"ALT {d.pos[1]:5.1f} m    SPD {d.speed:4.1f} m/s", (220, 230, 255), (18, 52))
        if m["time_limit"] > 0:
            col = (255, 90, 90) if self.time_left < 10 else (255, 255, 255)
            self.txt(self.f_med, f"{max(0, self.time_left):5.1f}s", col, (self.RW - 18, 14), center=False)
        self.txt(self.f_med, f"SCORE {self.score}", (255, 230, 90), (self.RW - 18 - 220, 14))
        if self.checkpoints:
            self.txt(self.f_sm, f"CHECKPOINT {min(self.cp_i + 1, len(self.checkpoints))}/{len(self.checkpoints)}",
                      (200, 255, 210), (18, 78))
            if self.cp_i < len(self.checkpoints) and self.checkpoints[self.cp_i]["hold"] > 0:
                frac = clampv(self.hold_t / self.checkpoints[self.cp_i]["hold"], 0, 1)
                pygame.draw.rect(self.screen, (60, 60, 70), (18, 100, 200, 10))
                pygame.draw.rect(self.screen, (120, 255, 160), (18, 100, int(200 * frac), 10))
        # throttle bar + artificial horizon (small, bottom-left)
        bx, by = 18, self.RH - 130
        pygame.draw.rect(self.screen, (30, 30, 40), (bx, by, 26, 100), border_radius=4)
        thr01 = clampv((d.vel[1] + THROTTLE_RANGE) / (2 * THROTTLE_RANGE), 0, 1)
        pygame.draw.rect(self.screen, (100, 220, 255), (bx, by + int(100 * (1 - thr01)), 26, int(100 * thr01)),
                          border_radius=4)
        cx, cy = bx + 60 + 45, by + 50
        pygame.draw.circle(self.screen, (20, 20, 26), (cx, cy), 46)
        roll = d.roll_tilt
        pitch_off = clampv(d.pitch_tilt / MAX_TILT, -1, 1) * 30
        horiz = [(cx - 60 * math.cos(roll), cy + pitch_off + 60 * math.sin(roll)),
                  (cx + 60 * math.cos(roll), cy + pitch_off - 60 * math.sin(roll))]
        pygame.draw.line(self.screen, (120, 200, 255), horiz[0], horiz[1], 3)
        pygame.draw.circle(self.screen, (255, 255, 255), (cx, cy), 3)
        pygame.draw.circle(self.screen, (200, 200, 220), (cx, cy), 46, 2)
        if self.pad or self.ser:
            mode_col = (120, 220, 255) if self.control_mode == "fly" else (255, 200, 100)
            surf = self.f_sm.render(f"MODE: {self.control_mode.upper()}  (LEFT click to switch)", True, mode_col)
            self.screen.blit(surf, surf.get_rect(topright=(self.RW - 18, 46)))
        if self.stabilize_flash > 0:
            a = int(255 * clampv(self.stabilize_flash / 0.35, 0, 1) * 0.5)
            flash = pygame.Surface((self.RW, self.RH), pygame.SRCALPHA)
            flash.fill((140, 255, 180, a))
            self.screen.blit(flash, (0, 0))
        for i, (t, s, colf) in enumerate(self.popups):
            a = clampv(t / 1.4, 0, 1)
            col = tuple(int(v * 255) for v in colf)
            self.txt(self.f_med, s, col, (self.RW / 2, 140 + i * 34), center=True)

    def draw_title(self):
        self.draw_sky()
        self.draw_ground()
        self.txt(self.f_big, "D R O N E   S I M", (255, 255, 255), (self.RW / 2, 120), center=True)
        self.txt(self.f_sm, "hyper-realistic-feel FPV flight  -  keyboard, gamepad or Arduino two-stick rig",
                  (200, 210, 230), (self.RW / 2, 168), center=True)
        m = MISSIONS[self.mission_i]
        box = pygame.Rect(self.RW / 2 - 300, 230, 600, 220)
        pygame.draw.rect(self.screen, (10, 12, 22), box, border_radius=14)
        pygame.draw.rect(self.screen, tuple(int(v * 255) for v in m["color"]), box, 3, border_radius=14)
        self.txt(self.f_med, m["name"], tuple(int(v * 255) for v in m["color"]),
                  (self.RW / 2, 270), center=True)
        self.txt(self.f_sm, m["desc"], (230, 230, 240), (self.RW / 2, 315), center=True)
        hi = self.hi.get(m["id"])
        if hi:
            self.txt(self.f_sm, f"BEST SCORE  {hi['score']}   ({hi['time']}s)", (255, 220, 120),
                      (self.RW / 2, 350), center=True)
        self.txt(self.f_sm, "UP/DOWN or W/S: change mission     ENTER/SPACE: select", (200, 210, 230),
                  (self.RW / 2, 400), center=True)
        self.txt(self.f_sm, f"{self.mission_i + 1} / {len(MISSIONS)}", (150, 160, 190), (self.RW / 2, 430),
                  center=True)

    def draw_briefing(self):
        self.draw_sky()
        self.draw_ground()
        m = MISSIONS[self.mission_i]
        self.txt(self.f_big, m["name"], tuple(int(v * 255) for v in m["color"]), (self.RW / 2, 130), center=True)
        self.txt(self.f_med, m["desc"], (230, 230, 240), (self.RW / 2, 190), center=True)
        lines = [
            "GAMEPAD/ARDUINO (2 sticks, 6 signals - each one does something different):",
            "  LEFT up/down = throttle      RIGHT up/down = forward/back     [FLY mode]",
            "  LEFT CLICK = switch to STEER mode: LEFT up/down = yaw, RIGHT up/down = strafe",
            "  RIGHT CLICK = STABILIZE (panic button, kills tilt & drift)",
            "KEYBOARD: WASD = pitch/roll   arrows/space/shift = yaw/throttle   TAB = mode",
            "TOUCHPAD: drag to steer (pitch/roll)   left/right click = throttle up/down",
            "L = stabilize    P/ESC = pause    R = restart",
        ]
        for i, line in enumerate(lines):
            self.txt(self.f_sm, line, (200, 220, 255), (self.RW / 2, 240 + i * 27), center=True)
        self.txt(self.f_med, "SPACE / ENTER to launch", (255, 255, 255), (self.RW / 2, 470), center=True)

    def draw_done(self):
        self.draw_scene()
        overlay = pygame.Surface((self.RW, self.RH), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 150))
        self.screen.blit(overlay, (0, 0))
        title = {"win": "MISSION COMPLETE", "lose": "TIME'S UP", "crash": "CRASHED"}[self.result]
        col = {"win": (120, 255, 160), "lose": (255, 200, 90), "crash": (255, 90, 90)}[self.result]
        self.txt(self.f_big, title, col, (self.RW / 2, self.RH / 2 - 80), center=True)
        self.txt(self.f_med, f"SCORE {self.score}", (255, 255, 255), (self.RW / 2, self.RH / 2 - 20), center=True)
        mid = MISSIONS[self.mission_i]["id"]
        hi = self.hi.get(mid)
        if hi and hi["score"] == self.score:
            self.txt(self.f_sm, "NEW BEST!", (255, 220, 120), (self.RW / 2, self.RH / 2 + 16), center=True)
        self.txt(self.f_sm, "SPACE/ENTER: retry     ESC: mission menu", (220, 220, 230),
                  (self.RW / 2, self.RH / 2 + 60), center=True)

    def draw_pause(self):
        self.draw_scene()
        overlay = pygame.Surface((self.RW, self.RH), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 140))
        self.screen.blit(overlay, (0, 0))
        self.txt(self.f_big, "PAUSED", (255, 255, 255), (self.RW / 2, self.RH / 2 - 40), center=True)
        self.txt(self.f_sm, "SPACE/ESC/P: resume     Q: mission menu", (220, 220, 230),
                  (self.RW / 2, self.RH / 2 + 20), center=True)

    def draw(self):
        if self.state == "title":
            self.draw_title()
        elif self.state == "briefing":
            self.draw_briefing()
        elif self.state == "play":
            self.draw_scene()
            self.draw_hud()
        elif self.state == "pause":
            self.draw_pause()
        elif self.state == "done":
            self.draw_done()
        pygame.display.flip()

    # ------------------------------------------------------------ main loop
    def run(self, frames=None):
        n = 0
        while frames is None or n < frames:
            dt = self.clock.tick(60) / 1000.0
            for e in pygame.event.get():
                self.handle(e)
            self.update(dt)
            self.draw()
            n += 1


# =====================================================================
#  Joystick / Arduino pad tester
# =====================================================================
def joytest():
    """Print live axis / button numbers so you can fill in CONFIG['gamepad']."""
    pygame.init()
    pygame.joystick.init()
    pads = [pygame.joystick.Joystick(i) for i in range(pygame.joystick.get_count())]
    ser = None
    if "--serial" in sys.argv:
        import serial
        port = sys.argv[sys.argv.index("--serial") + 1]
        ser = serial.Serial(port, C["serial"]["baud"], timeout=0.5)
        print(f"Reading Arduino serial pad on {port} ... Ctrl+C to stop.")
    elif not pads:
        print("No joystick / gamepad detected. Plug it in, or use --serial COMx for an Arduino.")
        return
    else:
        print(f"Found {len(pads)} joystick(s). Wiggle sticks / click buttons. Ctrl+C to stop.")
    last = None
    try:
        while True:
            if ser:
                line = ser.readline().decode("ascii", "ignore").strip()
                if line:
                    print(line)
            else:
                pygame.event.pump()
                for p in pads:
                    cur = ([round(p.get_axis(i), 2) for i in range(p.get_numaxes())],
                           [p.get_button(i) for i in range(p.get_numbuttons())],
                           [p.get_hat(i) for i in range(p.get_numhats())])
                    if cur != last:
                        print(f"axes={cur[0]}  buttons={cur[1]}  hats={cur[2]}")
                        last = cur
                pygame.time.wait(60)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    if "--joytest" in sys.argv:
        joytest()
    else:
        Game().run()
