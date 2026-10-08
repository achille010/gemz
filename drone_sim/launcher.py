"""DRONE SIM - launcher (the app's entry point).

Python / pygame owns: menus, the two Bluetooth / USB Arduino pads, the mission generator and
saves. drone_sim.py flies the mission: we start it with the mission file and stream both pads
to it over UDP (127.0.0.1:47800) ~60 times per second while it runs.

    python launcher.py              menu
    python launcher.py --pads       open straight on the controller check
    python launcher.py --quick      skip the menu, start a random operation

Pad 1 flies. Pad 2 is the optional co-pilot: its clicks work the camera, stabilize and pause.
Settings live in config.json, shared with the game (this file only touches the launcher keys).
"""
import json
import os
import socket
import subprocess
import sys
import time

import pygame

import missions
import sfxgen
from pads import PadHub, SimPad

HERE = os.path.dirname(os.path.abspath(__file__))
GAME = os.path.join(HERE, "drone_sim.py")
SOUNDS = os.path.join(HERE, "sounds")
CFG_PATH = os.path.join(HERE, "config.json")
SAVE_PATH = os.path.join(HERE, "save.json")
HI_PATH = os.path.join(HERE, "highscore.json")
RUN_DIR = os.path.join(HERE, "run")
UDP_ADDR = ("127.0.0.1", 47800)

# only the launcher's own keys - the game's settings live in the same file and are left alone
DEFAULT_CFG = {
    "fullscreen": False,
    "p1": "auto",                   # "auto", a COM port ("COM7") or an HC-05 address ("0021:07:001EE9")
    "p2": "auto",
    "baud": 115200,                 # USB cable baud (Bluetooth ignores it)
    "deadzone": 0.12,
    "click_guard": 0.55,            # a click only starts with its stick near centre (1.5 = off)
    "invert": {},                   # e.g. {"p1_ly": true}  - toggled on the controller check screen
    "copilot": True,                # pad 2's clicks work camera / stabilize / pause in game
}

ORIENT_STEPS = [("ly", "Push the LEFT stick FORWARD (away from you)"), ("lx", "Push the LEFT stick to the RIGHT"),
                ("ry", "Push the RIGHT stick FORWARD (away from you)"), ("rx", "Push the RIGHT stick to the RIGHT")]

BUILT_IN = [("FREE FLIGHT", "free_flight"), ("RING RUSH", "ring_rush"), ("SLALOM SPRINT", "slalom"),
            ("ALTITUDE ACE", "altitude_ace"), ("PRECISION LANDING", "precision_landing"),
            ("DELIVERY RUN", "delivery"), ("STORM RUSH", "storm_rush")]

BG = (10, 14, 20)
FG = (230, 234, 238)
DIM = (126, 136, 148)
ACC = (90, 210, 255)
BLUE = (60, 130, 255)
RED = (255, 80, 70)
GREEN = (80, 230, 120)
GOLD = (255, 210, 90)


def load_json(path, default):
    try:
        with open(path) as f:
            d = json.load(f)
        if isinstance(default, dict):
            out = dict(default)
            out.update(d)
            return out
        return d
    except Exception:
        return json.loads(json.dumps(default))


def save_json(path, d):
    with open(path, "w") as f:
        json.dump(d, f, indent=2)


def save_cfg(cfg):
    """Write our keys back into the shared config.json without touching the game's."""
    disk = load_json(CFG_PATH, {})
    disk.update({k: cfg[k] for k in DEFAULT_CFG if k in cfg})
    for k in ("map",):
        if k in cfg:
            disk[k] = cfg[k]
    save_json(CFG_PATH, disk)


def find_python():
    """The interpreter to run the game with: this one, unless it's a frozen build."""
    return sys.executable or "python"


class App:
    def __init__(self):
        pygame.init()
        self.cfg = load_json(CFG_PATH, DEFAULT_CFG)
        self.save = load_json(SAVE_PATH, {"campaign": 1, "best": 0, "played": 0, "wins": 0, "stars": 0})
        save_cfg(self.cfg)
        self.snd_dir = sfxgen.ensure(SOUNDS)
        self.screen = pygame.display.set_mode((1100, 680), pygame.RESIZABLE)
        pygame.display.set_caption("DRONE SIM - launcher")
        self.f_big = pygame.font.SysFont("bahnschrift,segoe ui,arial", 64, bold=True)
        self.f_mid = pygame.font.SysFont("bahnschrift,segoe ui,arial", 30, bold=True)
        self.f = pygame.font.SysFont("bahnschrift,segoe ui,arial", 21)
        self.f_small = pygame.font.SysFont("consolas,courier", 16)
        self.clock = pygame.time.Clock()
        self.hub = PadHub(self.cfg)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.screen_name = "menu"
        self.sel = 0
        self.mission = None
        self.mission_id = None
        self.proc = None
        self.result = None
        self.msg = ""
        self.wiz = None
        self.nav_prev = [0, 0]
        self.nav_t = 0.0
        self.btn_prev = [[False, False], [False, False]]
        self.pad_seen = [False, False]
        self.run_started = 0.0
        self.sounds = {}
        self._load_sounds()
        if "--pads" in sys.argv:
            self.screen_name = "pads"
        if "--quick" in sys.argv:
            self.mission = missions.generate()
            self.start_mission()

    # ------------------------------------------------------------------ sound
    def _load_sounds(self):
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(22050, -16, 1, 512)
            for n in sfxgen.NAMES:
                p = os.path.join(self.snd_dir, n + ".wav")
                if os.path.exists(p):
                    self.sounds[n] = pygame.mixer.Sound(p)
        except Exception as e:
            print("Sound disabled: %s" % e)

    def play(self, name, vol=0.7):
        s = self.sounds.get(name)
        if s:
            try:
                s.set_volume(vol)
                s.play()
            except Exception:
                pass

    # ------------------------------------------------------------------ input helpers
    def pad_nav(self):
        """Menu navigation from either pad: stick up/down, right click = OK, left click = back."""
        up = down = ok = back = False
        now = time.time()
        for i in range(2):
            v = self.hub.vector(i)
            if not v[6]:
                continue
            if not self.pad_seen[i]:
                self.pad_seen[i] = True
                self.play("pad")
            d = 1 if v[1] > 0.6 else -1 if v[1] < -0.6 else 0
            if d and (d != self.nav_prev[i] or now - self.nav_t > 0.35):
                up, down = up or d > 0, down or d < 0
                self.nav_t = now
            self.nav_prev[i] = d
            for b in range(2):
                pressed = bool(v[4 + b])
                if pressed and not self.btn_prev[i][b]:
                    ok, back = ok or b == 1, back or b == 0
                self.btn_prev[i][b] = pressed
        return up, down, ok, back

    # ------------------------------------------------------------------ actions
    def stars_total(self):
        hi = load_json(HI_PATH, {})
        return sum(v.get("stars", 0) for v in hi.values() if isinstance(v, dict))

    def menu_items(self):
        return [("Campaign - Mission %d" % self.save["campaign"], "campaign"),
                ("Random Operation", "random"),
                ("Solo Operation  (easier, 1 pad)", "solo"),
                ("Built-in Missions  (the original 7)", "builtin"),
                ("Controller Check (pads / Bluetooth)", "pads"),
                ("Hardware Guide", "guide"),
                ("Quit", "quit")]

    def do(self, action):
        if action == "campaign":
            self.mission = missions.generate(campaign_no=self.save["campaign"])
            self.screen_name, self.sel = "brief", 0
        elif action == "random":
            self.mission = missions.generate()
            self.screen_name, self.sel = "brief", 0
        elif action == "solo":
            self.mission = missions.generate(solo=True)
            self.screen_name, self.sel = "brief", 0
        elif action == "builtin":
            self.screen_name, self.sel = "builtin", 0
        elif action == "pads":
            self.screen_name = "pads"
        elif action == "guide":
            try:
                os.startfile(os.path.join(HERE, "HARDWARE_GUIDE.md"))
            except Exception:
                self.msg = "Open HARDWARE_GUIDE.md in the drone_sim folder"
        elif action == "quit":
            self.quit()

    def launch(self, args, label):
        """Start drone_sim.py with our pads streaming to it."""
        if not os.path.exists(GAME):
            self.msg = "drone_sim.py is missing from this folder"
            self.screen_name = "menu"
            return
        os.makedirs(RUN_DIR, exist_ok=True)
        rpath = os.path.join(RUN_DIR, "result.json")
        if os.path.exists(rpath):
            os.remove(rpath)
        cmd = [find_python(), GAME, "--result", rpath, "--pad-udp", str(UDP_ADDR[1])] + args
        if not self.cfg.get("copilot", True):
            cmd.append("--no-copilot")
        self.play("start")
        try:
            self.proc = subprocess.Popen(cmd, cwd=HERE)
        except Exception as e:
            self.msg = "could not start the game (%s)" % e
            self.screen_name = "menu"
            return
        self.result = None
        self.run_label = label
        self.run_started = time.time()
        self.screen_name = "running"

    def start_mission(self):
        os.makedirs(RUN_DIR, exist_ok=True)
        mpath = os.path.join(RUN_DIR, "mission.json")
        save_json(mpath, self.mission)
        self.mission_id = None
        self.launch(["--mission", mpath], self.mission["name"])

    def start_builtin(self, mid, name):
        self.mission = None
        self.mission_id = mid
        self.launch(["--mission-id", mid], name)

    def poll_game(self):
        if self.proc is None or self.proc.poll() is None:
            return
        self.proc = None
        self.result = load_json(os.path.join(RUN_DIR, "result.json"),
                                {"win": False, "reason": "Game closed"})
        self.save["played"] += 1
        if self.result.get("win"):
            self.save["wins"] += 1
            if self.mission and self.mission.get("campaign_no") == self.save["campaign"]:
                self.save["campaign"] += 1
                self.save["best"] = max(self.save["best"], self.save["campaign"] - 1)
            self.play("confirm")
        else:
            self.play("back")
        self.save["stars"] = self.stars_total()
        save_json(SAVE_PATH, self.save)
        self.screen_name = "result"
        self.screen = pygame.display.set_mode((1100, 680), pygame.RESIZABLE)

    def stream_pads(self):
        try:
            pkt = json.dumps({"p": [self.hub.vector(0), self.hub.vector(1)]}).encode()
            self.sock.sendto(pkt, UDP_ADDR)
        except OSError:
            pass

    def quit(self):
        save_cfg(self.cfg)
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
        pygame.quit()
        os._exit(0)                 # don't wait for serial threads stuck dialling a Bluetooth port

    # ------------------------------------------------------------------ loop
    def run(self):
        while True:
            self.clock.tick(60)
            self.stream_pads()
            self.poll_game()
            keys = []
            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    self.quit()
                if e.type == pygame.KEYDOWN:
                    keys.append(e.key)
            up, down, ok, back = self.pad_nav()
            up = up or pygame.K_UP in keys
            down = down or pygame.K_DOWN in keys
            ok = ok or pygame.K_RETURN in keys or pygame.K_SPACE in keys
            back = back or pygame.K_ESCAPE in keys or pygame.K_BACKSPACE in keys
            if up or down:
                self.play("nav", 0.5)
            getattr(self, "screen_" + self.screen_name)(keys, up, down, ok, back)
            pygame.display.flip()

    # ------------------------------------------------------------------ drawing helpers
    def text(self, t, pos, font=None, col=FG, center=False):
        s = (font or self.f).render(t, True, col)
        r = s.get_rect()
        if center:
            r.midtop = pos
        else:
            r.topleft = pos
        self.screen.blit(s, r)
        return r

    def frame(self, title):
        W, H = self.screen.get_size()
        self.screen.fill(BG)
        for y in range(0, H, 4):
            pygame.draw.line(self.screen, (14, 19, 26), (0, y), (W, y))
        self.text("DRONE SIM", (W // 2, 26), self.f_big, ACC, True)
        self.text(title, (W // 2, 100), self.f_mid, FG, True)
        self.pad_strip()
        if self.msg:
            self.text(self.msg, (W // 2, H - 92), self.f, (255, 150, 120), True)

    def pad_strip(self):
        W, H = self.screen.get_size()
        roles = ["PILOT", "CO-PILOT"]
        for i in range(2):
            col = BLUE if i == 0 else RED
            x = 30 if i == 0 else W // 2 + 10
            p = self.hub.pad(i)
            if p is not None:
                kind = "SIM" if isinstance(p, SimPad) else ("Bluetooth" if p.bluetooth else "USB")
                st = "%s: %s %s  - ready" % (roles[i], kind, p.dev)
                c = GREEN
            elif i == 0:
                st = "PILOT: no pad (keyboard / USB pad still work in game)"
                c = DIM
            else:
                st = "CO-PILOT: none (optional)"
                c = DIM
            pygame.draw.rect(self.screen, col, (x, H - 50, 8, 26))
            self.text(st, (x + 16, H - 48), self.f, c)

    # ------------------------------------------------------------------ screens
    def screen_menu(self, keys, up, down, ok, back):
        items = self.menu_items()
        self.sel = (self.sel + (1 if down else 0) - (1 if up else 0)) % len(items)
        if ok:
            self.msg = ""
            self.play("confirm")
            self.do(items[self.sel][1])
            return
        self.frame("%d ops flown  -  %d won  -  campaign best: mission %d  -  %d stars"
                   % (self.save["played"], self.save["wins"], self.save["best"], self.stars_total()))
        W, _ = self.screen.get_size()
        for k, (label, _) in enumerate(items):
            y = 170 + k * 52
            if k == self.sel:
                pygame.draw.rect(self.screen, (20, 38, 48), (W // 2 - 300, y - 8, 600, 46), border_radius=8)
                pygame.draw.rect(self.screen, ACC, (W // 2 - 300, y - 8, 600, 46), 2, border_radius=8)
            self.text(label, (W // 2, y), self.f_mid, ACC if k == self.sel else FG, True)
        self.text("stick up/down + right click   |   arrows + Enter", (W // 2, 545), self.f, DIM, True)
        for i in range(2):
            p = self.hub.pad(i)
            if p is not None and not isinstance(p, SimPad) and "p%d" % (i + 1) not in self.cfg.get("map", {}):
                self.text("Pad %d not oriented yet: open Controller Check and press %s"
                          % (i + 1, "O" if i == 0 else "P"),
                          (W // 2, 575 + i * 26), self.f, GOLD, True)

    def screen_builtin(self, keys, up, down, ok, back):
        self.sel = (self.sel + (1 if down else 0) - (1 if up else 0)) % len(BUILT_IN)
        if back:
            self.screen_name, self.sel = "menu", 0
            return
        if ok:
            self.play("confirm")
            name, mid = BUILT_IN[self.sel]
            self.start_builtin(mid, name)
            return
        self.frame("BUILT-IN MISSIONS")
        W, _ = self.screen.get_size()
        hi = load_json(HI_PATH, {})
        self.text("the original campaign - stars and best scores live in highscore.json",
                  (W // 2, 142), self.f, DIM, True)
        for k, (name, mid) in enumerate(BUILT_IN):
            y = 185 + k * 48
            rec = hi.get(mid, {})
            if k == self.sel:
                pygame.draw.rect(self.screen, (20, 38, 48), (W // 2 - 330, y - 6, 660, 42), border_radius=8)
                pygame.draw.rect(self.screen, ACC, (W // 2 - 330, y - 6, 660, 42), 2, border_radius=8)
            self.text(name, (W // 2 - 310, y), self.f_mid, ACC if k == self.sel else FG)
            st = rec.get("stars", 0)
            self.text("*" * st + "-" * (3 - st), (W // 2 + 110, y + 2), self.f_mid, GOLD if st else DIM)
            if rec.get("score"):
                self.text("best %d" % rec["score"], (W // 2 + 200, y + 6), self.f, DIM)
        self.text("right click / Enter = fly   -   left click / Esc = back", (W // 2, 560), self.f, DIM, True)

    def screen_brief(self, keys, up, down, ok, back):
        m = self.mission
        opts = ["LAUNCH", "New random mission" if m.get("campaign_no") is None else "Back"]
        self.sel = (self.sel + (1 if down else 0) - (1 if up else 0)) % len(opts)
        if back:
            self.screen_name, self.sel = "menu", 0
            return
        if ok:
            if self.sel == 0:
                self.start_mission()
            elif m.get("campaign_no") is None:
                self.play("nav")
                self.mission = missions.generate(solo=m.get("solo", False))
                self.sel = 0           # snap back to LAUNCH so the next OK flies it
            else:
                self.screen_name, self.sel = "menu", 0
            return
        camp = ("CAMPAIGN MISSION %d" % m["campaign_no"] if m.get("campaign_no")
                else ("SOLO OPERATION" if m.get("solo") else "RANDOM OPERATION"))
        self.frame("%s  -  %s" % (camp, m["code"]))
        W, _ = self.screen.get_size()
        x = 90
        p = m["params"]
        self.text(m["name"].upper(), (x, 148), self.f_mid, ACC)
        self.text("%s   |   %s   |   %s   |   difficulty %d/10"
                  % (m["course_name"], m["district_name"], m["weather_name"], m["difficulty"]),
                  (x, 190), self.f, FG)
        y = 232
        for line in self.wrap(m["brief"], W - 2 * x):
            self.text(line, (x, y), self.f, FG)
            y += 27
        y += 8
        self.text("Clock %d:%02d   -   wind %.1f m/s (gusts x%.1f)   -   battery starts at %d%%, "
                  "drains %.2f%%/s, +%d%% per checkpoint"
                  % (m["time_limit"] // 60, m["time_limit"] % 60, p["wind"], p["gust"],
                     p["battery"], p["drain"], p["recharge"]),
                  (x, y), self.f, DIM)
        y += 34
        for t in m["mod_text"]:
            self.text("!  " + t, (x, y), self.f, (255, 170, 95))
            y += 27
        self.text("3 stars: finish with 40%+ of the clock left, no clipped gates and 25%+ battery",
                  (x, y + 14), self.f, DIM)
        for k, o in enumerate(opts):
            yy = y + 64 + k * 44
            self.text(("> " if k == self.sel else "  ") + o, (x, yy), self.f_mid, ACC if k == self.sel else FG)

    def screen_running(self, keys, up, down, ok, back):
        self.frame("MISSION IN PROGRESS")
        W, _ = self.screen.get_size()
        el = int(time.time() - self.run_started)
        self.text("%s  -  %d:%02d" % (getattr(self, "run_label", ""), el // 60, el % 60),
                  (W // 2, 168), self.f_mid, ACC, True)
        self.text("The game is flying in its own window. Keep this window open:", (W // 2, 228), self.f, FG, True)
        self.text("it streams both pads to the game. Esc in the game ends the run.", (W // 2, 258), self.f, FG, True)
        for i in range(2):
            self.text("pad %d -> %s" % (i + 1, self.hub.vector(i)), (W // 2, 318 + i * 30),
                      self.f_small, BLUE if i == 0 else RED, True)

    def screen_result(self, keys, up, down, ok, back):
        r = self.result or {}
        if ok or back:
            self.screen_name, self.sel = "menu", 0
            return
        win = r.get("win")
        self.frame("MISSION COMPLETE" if win else "MISSION FAILED")
        W, _ = self.screen.get_size()
        self.text(r.get("reason", ""), (W // 2, 168), self.f_mid, GREEN if win else RED, True)
        st = int(r.get("stars", 0) or 0)
        self.text("*" * st + "-" * (3 - st) if st else "no stars", (W // 2, 212), self.f_big,
                  GOLD if st else DIM, True)
        t = int(r.get("time", 0))
        rows = ["Time %d:%02d   -   %.0f s left on the clock" % (t // 60, t % 60, r.get("time_left", 0)),
                "Score %d" % r.get("score", 0),
                "Checkpoints %d / %d   -   gates clipped: %d"
                % (r.get("checkpoints", 0), r.get("total_checkpoints", 0), r.get("clips", 0)),
                "Battery left %.0f%%" % r.get("battery", 0)]
        for k, row in enumerate(rows):
            self.text(row, (W // 2, 300 + k * 32), self.f, FG, True)
        if win and self.mission and self.mission.get("campaign_no"):
            self.text("Campaign: next is mission %d" % self.save["campaign"], (W // 2, 440), self.f, ACC, True)
        self.text("press OK to continue", (W // 2, 492), self.f, DIM, True)

    def screen_pads(self, keys, up, down, ok, back):
        if pygame.K_ESCAPE in keys or pygame.K_BACKSPACE in keys:
            if self.wiz:
                self.wiz = None
                self.msg = "orientation cancelled"
            else:
                self.screen_name = "menu"
            return
        inv = self.cfg.setdefault("invert", {})
        flips = {pygame.K_1: "p1_lx", pygame.K_2: "p1_ly", pygame.K_3: "p1_rx", pygame.K_4: "p1_ry",
                 pygame.K_5: "p2_lx", pygame.K_6: "p2_ly", pygame.K_7: "p2_rx", pygame.K_8: "p2_ry"}
        for k in keys:
            if k in flips:
                inv[flips[k]] = not inv.get(flips[k], False)
                save_cfg(self.cfg)
            elif k == pygame.K_s:
                self.hub.swap()
                save_cfg(self.cfg)
            elif k == pygame.K_r:
                for rd in list(self.hub.readers.values()):
                    rd.recalibrate()
            elif k == pygame.K_c:
                self.cfg["copilot"] = not self.cfg.get("copilot", True)
                save_cfg(self.cfg)
                self.msg = "co-pilot clicks %s" % ("on" if self.cfg["copilot"] else "off")
            elif k in (pygame.K_F1, pygame.K_F2):
                i = 0 if k == pygame.K_F1 else 1
                self.hub.sim[i] = None if self.hub.sim[i] else SimPad()
            elif k in (pygame.K_o, pygame.K_p):
                i = 0 if k == pygame.K_o else 1
                if self.hub.pad(i) is not None and not isinstance(self.hub.pad(i), SimPad):
                    self.wiz = {"pad": i, "step": 0, "res": {}, "hold": 0.0, "release": False}
                else:
                    self.msg = "pad %d: connect it first, then press %s" % (i + 1, "O" if i == 0 else "P")
                    self.play("deny")
        if self.wiz:
            self._orient_step()
        # simulated pads follow the keyboard: pad 1 WASD + TFGH, pad 2 IJKL + numpad
        kp = pygame.key.get_pressed()
        for i, (u, d, l, r, lu, ld, ll, lr, c1, c2) in enumerate([
                (pygame.K_w, pygame.K_s, pygame.K_a, pygame.K_d, pygame.K_t, pygame.K_g,
                 pygame.K_f, pygame.K_h, pygame.K_z, pygame.K_x),
                (pygame.K_i, pygame.K_k, pygame.K_j, pygame.K_l, pygame.K_KP8, pygame.K_KP5,
                 pygame.K_KP4, pygame.K_KP6, pygame.K_n, pygame.K_m)]):
            sp = self.hub.sim[i]
            if sp:
                sp.state = [kp[r] - kp[l], kp[d] - kp[u], kp[lr] - kp[ll], kp[ld] - kp[lu], kp[c1], kp[c2]]
        self.frame("CONTROLLER CHECK")
        W, H = self.screen.get_size()
        labels = [("LEFT  throttle / yaw", "RIGHT  pitch / roll"), ("LEFT  (unused)", "RIGHT  (unused)")]
        for i in range(2):
            x0 = 60 + i * (W // 2)
            col = BLUE if i == 0 else RED
            v = self.hub.vector(i)
            self.text("PAD %d  -  %s" % (i + 1, "PILOT" if i == 0 else "CO-PILOT"),
                      (x0, 148), self.f_mid, col)
            for s, (ax, ay, btn) in enumerate([(0, 1, 4), (2, 3, 5)]):
                cx, cy = x0 + 90 + s * 220, 282
                pygame.draw.circle(self.screen, (34, 42, 50), (cx, cy), 68)
                pygame.draw.circle(self.screen, DIM, (cx, cy), 68, 2)
                dot = (int(cx + v[ax] * 58), int(cy - v[ay] * 58))
                pygame.draw.circle(self.screen, GOLD if v[btn] else col, dot, 16 if v[btn] else 12)
                self.text(labels[i][s], (cx, cy + 78), self.f_small, FG, True)
            p = self.hub.pad(i)
            self.text("raw: %s" % (getattr(p, "raw", "")[:42] if p else "-"), (x0, 400), self.f_small, DIM)
        if self.hub.pad(1) is not None:
            self.text("co-pilot clicks: %s  (C toggles)" % ("camera / stabilize / pause"
                                                            if self.cfg.get("copilot", True) else "off"),
                      (60, 428), self.f_small, GREEN if self.cfg.get("copilot", True) else DIM)
        y = 452
        self.text("PORTS FOUND:", (60, y), self.f, ACC)
        y += 28
        for dev, desc, hwid in self.hub.ports_info[:7]:
            rd = self.hub.readers.get(dev)
            role = " = P1" if self.hub.assigned[0] == dev else " = P2" if self.hub.assigned[1] == dev else ""
            self.text("%-7s%-6s %-44s %s" % (dev, role, desc[:42], rd.status if rd else ""),
                      (60, y), self.f_small, GREEN if role else FG)
            y += 20
        if not self.hub.ports_info:
            self.text("no COM ports yet - pair the HC-05 in Windows Bluetooth settings or plug in a USB cable",
                      (60, y), self.f_small, DIM)
        if self.hub.error:
            self.text(self.hub.error, (60, y + 22), self.f_small, RED)
        self.text("O / P orient pad 1 / 2   1-4 / 5-8 flip axes   S swap pads   R recalibrate   "
                  "C co-pilot   F1/F2 sim pad   Esc back", (W // 2, H - 84), self.f_small, DIM, True)
        if self.wiz:
            wz = self.wiz
            pygame.draw.rect(self.screen, (8, 11, 15), (W // 2 - 380, 160, 760, 150), border_radius=10)
            pygame.draw.rect(self.screen, ACC, (W // 2 - 380, 160, 760, 150), 2, border_radius=10)
            self.text("ORIENT PAD %d  -  step %d / 4" % (wz["pad"] + 1, wz["step"] + 1),
                      (W // 2, 175), self.f_mid, ACC, True)
            txt = "Let go of the stick (back to centre)..." if wz["release"] else ORIENT_STEPS[wz["step"]][1]
            self.text(txt, (W // 2, 225), self.f_mid, FG, True)
            self.text("hold it at the edge for half a second   -   Esc cancels",
                      (W // 2, 270), self.f_small, DIM, True)

    def _orient_step(self):
        """Orientation wizard: find which raw axis (and direction) each stick direction really is."""
        wz = self.wiz
        p = self.hub.pad(wz["pad"])
        if p is None:
            self.wiz = None
            self.msg = "pad disconnected - orientation cancelled"
            return
        raw = [p.axis(a, 0.0) for a in range(4)]
        if wz["release"]:
            if max(abs(v) for v in raw) < 0.25:
                wz["release"] = False
            return
        used = [r[0] for r in wz["res"].values()]
        cand = [a for a in range(4) if a not in used]
        if not cand:
            self.wiz = None
            return
        best = max(cand, key=lambda a: abs(raw[a]))
        if abs(raw[best]) > 0.6:
            wz["hold"] += self.clock.get_time() / 1000.0
            if wz["hold"] > 0.5:
                name = ORIENT_STEPS[wz["step"]][0]
                wz["res"][name] = [best, 1 if raw[best] > 0 else -1]
                wz["step"] += 1
                wz["hold"] = 0.0
                wz["release"] = True
                self.play("nav")
                if wz["step"] == 4:
                    key = "p%d" % (wz["pad"] + 1)
                    self.cfg.setdefault("map", {})[key] = wz["res"]
                    inv = self.cfg.setdefault("invert", {})
                    for n in ("lx", "ly", "rx", "ry"):
                        inv.pop("%s_%s" % (key, n), None)
                    save_cfg(self.cfg)
                    self.msg = "pad %d sticks oriented and saved" % (wz["pad"] + 1)
                    self.play("confirm")
                    self.wiz = None
        else:
            wz["hold"] = 0.0

    def wrap(self, t, width):
        out, line = [], ""
        for w in t.split():
            if self.f.size(line + " " + w)[0] > width:
                out.append(line)
                line = w
            else:
                line = (line + " " + w).strip()
        return out + [line]


if __name__ == "__main__":
    App().run()
