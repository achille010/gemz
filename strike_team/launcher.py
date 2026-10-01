"""STRIKE TEAM - launcher (the app's entry point).

Python / pygame owns: menus, the two Bluetooth / USB Arduino pads, the mission generator and saves.
Godot 4 renders the 3D battle: we start it with the mission file and stream both pads to it over
UDP (127.0.0.1:47800) ~60 times per second while it runs.

    python launcher.py              menu
    python launcher.py --pads       open straight on the controller check
    python launcher.py --quick      skip the menu, start a random operation
"""
import glob
import json
import os
import shutil
import socket
import subprocess
import sys
import time

import pygame

import missions
import sfxgen
from pads import PadHub, SimPad

HERE = os.path.dirname(os.path.abspath(__file__))
GODOT_DIR = os.path.join(HERE, "godot")
ASSETS = os.path.join(HERE, "assets")
CFG_PATH = os.path.join(HERE, "config.json")
SAVE_PATH = os.path.join(HERE, "save.json")
RUN_DIR = os.path.join(HERE, "run")
UDP_ADDR = ("127.0.0.1", 47800)

DEFAULT_CFG = {
    "godot_exe": "auto",            # or a full path to Godot_v4.x_win64.exe
    "fullscreen": False,
    "p1": "auto",                   # "auto", a COM port ("COM7") or an HC-05 address ("0021:07:001EE9")
    "p2": "auto",
    "baud": 115200,                 # USB cable baud (Bluetooth ignores it)
    "deadzone": 0.12,
    "invert": {},                   # e.g. {"p1_ly": true}  - toggled on the controller check screen
}

BG = (12, 16, 20)
FG = (230, 232, 235)
DIM = (130, 138, 146)
ACC = (255, 200, 60)
BLUE = (60, 130, 255)
RED = (255, 70, 60)
GREEN = (80, 230, 110)


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


def find_godot(cfg):
    if cfg.get("godot_exe", "auto") not in ("", "auto") and os.path.exists(cfg["godot_exe"]):
        return cfg["godot_exe"]
    cands = []
    if os.environ.get("GODOT"):
        cands.append(os.environ["GODOT"])
    for pat in [r"C:\Tools\Godot*win64.exe", r"C:\Tools\Godot\Godot*win64.exe", r"C:\Godot*\Godot*win64.exe",
                os.path.expanduser(r"~\Downloads\Godot*\Godot*win64.exe"), os.path.expanduser(r"~\Downloads\Godot*win64.exe"),
                os.path.expanduser(r"~\Desktop\Godot*win64.exe")]:
        cands += sorted(glob.glob(pat), reverse=True)
    for name in ("godot", "godot4"):
        w = shutil.which(name)
        if w:
            cands.append(w)
    for c in cands:
        if os.path.exists(c) and "console" not in os.path.basename(c).lower():
            return c
    return cands[0] if cands else None


class App:
    def __init__(self):
        pygame.init()
        self.cfg = load_json(CFG_PATH, DEFAULT_CFG)
        self.save = load_json(SAVE_PATH, {"campaign": 1, "best": 0, "played": 0, "wins": 0})
        save_json(CFG_PATH, self.cfg)
        sfxgen.ensure(os.path.join(ASSETS, "sounds"))
        self.screen = pygame.display.set_mode((1100, 680), pygame.RESIZABLE)
        pygame.display.set_caption("STRIKE TEAM - launcher")
        self.f_big = pygame.font.SysFont("bahnschrift,arial", 64, bold=True)
        self.f_mid = pygame.font.SysFont("bahnschrift,arial", 30, bold=True)
        self.f = pygame.font.SysFont("bahnschrift,arial", 21)
        self.f_small = pygame.font.SysFont("consolas,courier", 16)
        self.clock = pygame.time.Clock()
        self.hub = PadHub(self.cfg)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.screen_name = "menu"
        self.sel = 0
        self.mission = None
        self.proc = None
        self.result = None
        self.msg = ""
        self.nav_prev = [0, 0]
        self.nav_t = 0.0
        self.btn_prev = [[False, False], [False, False]]
        self.godot = find_godot(self.cfg)
        if "--pads" in sys.argv:
            self.screen_name = "pads"
        if "--quick" in sys.argv:
            self.mission = missions.generate()
            self.start_mission()

    # ------------------------------------------------------------------ input helpers
    def pad_nav(self):
        """Menu navigation from player 1's (or 2's) pad: stick up/down, right click = OK, left = back."""
        up = down = ok = back = False
        now = time.time()
        for i in range(2):
            v = self.hub.vector(i)
            if not v[6]:
                continue
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
    def menu_items(self):
        n = self.save["campaign"]
        return [("Campaign - Mission %d" % n, "campaign"), ("Random Operation", "random"),
                ("Controller Check (pads / Bluetooth)", "pads"), ("Hardware Guide", "guide"), ("Quit", "quit")]

    def do(self, action):
        if action == "campaign":
            self.mission = missions.generate(campaign_no=self.save["campaign"])
            self.screen_name, self.sel = "brief", 0
        elif action == "random":
            self.mission = missions.generate()
            self.screen_name, self.sel = "brief", 0
        elif action == "pads":
            self.screen_name = "pads"
        elif action == "guide":
            try:
                os.startfile(os.path.join(HERE, "HARDWARE_GUIDE.md"))
            except Exception:
                self.msg = "Open HARDWARE_GUIDE.md in the strike_team folder"
        elif action == "quit":
            self.quit()

    def start_mission(self):
        if not self.godot:
            self.msg = "Godot not found - set \"godot_exe\" in config.json"
            self.screen_name = "menu"
            return
        os.makedirs(RUN_DIR, exist_ok=True)
        mpath = os.path.join(RUN_DIR, "mission.json")
        rpath = os.path.join(RUN_DIR, "result.json")
        save_json(mpath, self.mission)
        if os.path.exists(rpath):
            os.remove(rpath)
        args = [self.godot, "--path", GODOT_DIR]
        args += ["--fullscreen"] if self.cfg.get("fullscreen") else ["--maximized"]
        args += ["--", "--mission", mpath, "--result", rpath, "--assets", ASSETS]
        self.proc = subprocess.Popen(args)
        self.result = None
        self.screen_name = "running"
        self.run_started = time.time()

    def poll_game(self):
        if self.proc is None or self.proc.poll() is None:
            return
        self.proc = None
        rpath = os.path.join(RUN_DIR, "result.json")
        self.result = load_json(rpath, {"win": False, "reason": "Game closed"})
        self.save["played"] += 1
        if self.result.get("win"):
            self.save["wins"] += 1
            if self.mission.get("campaign_no") == self.save["campaign"]:
                self.save["campaign"] += 1
                self.save["best"] = max(self.save["best"], self.save["campaign"] - 1)
        save_json(SAVE_PATH, self.save)
        self.screen_name = "result"
        pygame.display.set_mode((1100, 680), pygame.RESIZABLE)

    def stream_pads(self):
        try:
            pkt = json.dumps({"p": [self.hub.vector(0), self.hub.vector(1)]}).encode()
            self.sock.sendto(pkt, UDP_ADDR)
        except OSError:
            pass

    def quit(self):
        save_json(CFG_PATH, self.cfg)
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
            pygame.draw.line(self.screen, (16, 21, 26), (0, y), (W, y))
        self.text("STRIKE TEAM", (W // 2, 26), self.f_big, ACC, True)
        self.text(title, (W // 2, 100), self.f_mid, FG, True)
        self.pad_strip()
        if self.msg:
            self.text(self.msg, (W // 2, H - 92), self.f, (255, 150, 120), True)

    def pad_strip(self):
        W, H = self.screen.get_size()
        for i in range(2):
            col = BLUE if i == 0 else RED
            x = 30 if i == 0 else W // 2 + 10
            p = self.hub.pad(i)
            if p is not None:
                kind = "SIM" if isinstance(p, SimPad) else ("Bluetooth" if p.bluetooth else "USB")
                st = f"P{i + 1}: {kind} {p.dev}  - ready"
                c = GREEN
            else:
                st = f"P{i + 1}: no pad (keyboard / Xbox pad work in-game)"
                c = DIM
            pygame.draw.rect(self.screen, col, (x, H - 50, 8, 26))
            self.text(st, (x + 16, H - 48), self.f, c)

    # ------------------------------------------------------------------ screens
    def screen_menu(self, keys, up, down, ok, back):
        items = self.menu_items()
        self.sel = (self.sel + (1 if down else 0) - (1 if up else 0)) % len(items)
        if ok:
            self.msg = ""
            self.do(items[self.sel][1])
            return
        self.frame("2-player co-op  -  %d missions won  -  campaign best: %d" % (self.save["wins"], self.save["best"]))
        W, _ = self.screen.get_size()
        for k, (label, _) in enumerate(items):
            y = 180 + k * 58
            if k == self.sel:
                pygame.draw.rect(self.screen, (40, 46, 30), (W // 2 - 300, y - 8, 600, 50), border_radius=8)
                pygame.draw.rect(self.screen, ACC, (W // 2 - 300, y - 8, 600, 50), 2, border_radius=8)
            self.text(label, (W // 2, y), self.f_mid, ACC if k == self.sel else FG, True)
        self.text("stick up/down + right click   |   arrows + Enter", (W // 2, 480), self.f, DIM, True)
        if not self.godot:
            self.text("Godot 4 not found - set godot_exe in config.json", (W // 2, 515), self.f, RED, True)

    def screen_brief(self, keys, up, down, ok, back):
        m = self.mission
        opts = ["START MISSION", "New random mission" if m.get("campaign_no") is None else "Back"]
        self.sel = (self.sel + (1 if down else 0) - (1 if up else 0)) % len(opts)
        if back:
            self.screen_name, self.sel = "menu", 0
            return
        if ok:
            if self.sel == 0:
                self.start_mission()
            elif m.get("campaign_no") is None:
                self.mission = missions.generate()
            else:
                self.screen_name, self.sel = "menu", 0
            return
        camp = f"CAMPAIGN MISSION {m['campaign_no']}" if m.get("campaign_no") else "RANDOM OPERATION"
        self.frame(f"{camp}  -  {m['code']}")
        W, _ = self.screen.get_size()
        x = 90
        self.text(m["name"].upper(), (x, 150), self.f_mid, ACC)
        self.text(f"{m['task_name']}   |   {m['biome_name']}   |   {m['time']}   |   difficulty {m['difficulty']}/10",
                  (x, 192), self.f, FG)
        y = 236
        for line in self.wrap(m["brief"], W - 2 * x):
            self.text(line, (x, y), self.f, FG)
            y += 28
        if m["time_limit"]:
            self.text(f"Time limit: {m['time_limit'] // 60}:{m['time_limit'] % 60:02d}", (x, y + 6), self.f, RED)
            y += 34
        for t in m["mod_text"]:
            self.text("!  " + t, (x, y + 6), self.f, (255, 160, 90))
            y += 28
        self.text("3 lives each  -  downed? your mate has 60 s to bring a medkit  -  both down = mission failed",
                  (x, y + 18), self.f, DIM)
        for k, o in enumerate(opts):
            yy = y + 70 + k * 46
            self.text(("> " if k == self.sel else "  ") + o, (x, yy), self.f_mid, ACC if k == self.sel else FG)

    def screen_running(self, keys, up, down, ok, back):
        self.frame("MISSION IN PROGRESS")
        W, _ = self.screen.get_size()
        el = int(time.time() - self.run_started)
        self.text(f"{self.mission['name']}  -  {el // 60}:{el % 60:02d}", (W // 2, 170), self.f_mid, ACC, True)
        self.text("The game is running in the Godot window. Keep this window open:", (W // 2, 230), self.f, FG, True)
        self.text("it streams both pads to the game. Esc in the game = abort.", (W // 2, 260), self.f, FG, True)
        for i in range(2):
            self.text(f"P{i + 1} -> {self.hub.vector(i)}", (W // 2, 320 + i * 30), self.f_small, BLUE if i == 0 else RED, True)

    def screen_result(self, keys, up, down, ok, back):
        r = self.result or {}
        if ok or back:
            self.screen_name, self.sel = "menu", 0
            return
        win = r.get("win")
        self.frame("MISSION COMPLETE" if win else "MISSION FAILED")
        W, _ = self.screen.get_size()
        self.text(r.get("reason", ""), (W // 2, 170), self.f_mid, GREEN if win else RED, True)
        t = int(r.get("time", 0))
        rows = [f"Time {t // 60}:{t % 60:02d}", f"Enemies killed: {r.get('kills', 0)}  (blue {r.get('p_kills', [0, 0])[0]} / red {r.get('p_kills', [0, 0])[1]})",
                f"Revives: {r.get('revives', 0)}   Times downed: {r.get('downs', 0)}",
                f"Shots: {r.get('shots', 0)}   Accuracy-ish: {int(100 * r.get('kills', 0) * 3 / max(1, r.get('shots', 1)))}%"]
        for k, row in enumerate(rows):
            self.text(row, (W // 2, 230 + k * 34), self.f, FG, True)
        if win and self.mission.get("campaign_no"):
            self.text(f"Campaign: next is mission {self.save['campaign']}", (W // 2, 390), self.f, ACC, True)
        self.text("press OK to continue", (W // 2, 450), self.f, DIM, True)

    def screen_pads(self, keys, up, down, ok, back):
        if pygame.K_ESCAPE in keys or pygame.K_BACKSPACE in keys:
            self.screen_name = "menu"
            return
        inv = self.cfg.setdefault("invert", {})
        flips = {pygame.K_1: "p1_lx", pygame.K_2: "p1_ly", pygame.K_3: "p1_rx", pygame.K_4: "p1_ry",
                 pygame.K_5: "p2_lx", pygame.K_6: "p2_ly", pygame.K_7: "p2_rx", pygame.K_8: "p2_ry"}
        for k in keys:
            if k in flips:
                inv[flips[k]] = not inv.get(flips[k], False)
                save_json(CFG_PATH, self.cfg)
            elif k == pygame.K_s:
                self.hub.swap()
                save_json(CFG_PATH, self.cfg)
            elif k == pygame.K_r:
                for r in list(self.hub.readers.values()):
                    r.recalibrate()
            elif k in (pygame.K_F1, pygame.K_F2):
                i = 0 if k == pygame.K_F1 else 1
                self.hub.sim[i] = None if self.hub.sim[i] else SimPad()
        # simulated pads follow the keyboard: P1 WASD / arrows look, P2 IJKL / numpad
        kp = pygame.key.get_pressed()
        for i, (u, d, l, r, lu, ld, ll, lr, c1, c2) in enumerate([
                (pygame.K_w, pygame.K_s, pygame.K_a, pygame.K_d, pygame.K_t, pygame.K_g, pygame.K_f, pygame.K_h, pygame.K_c, pygame.K_v),
                (pygame.K_i, pygame.K_k, pygame.K_j, pygame.K_l, pygame.K_KP8, pygame.K_KP5, pygame.K_KP4, pygame.K_KP6, pygame.K_n, pygame.K_m)]):
            sp = self.hub.sim[i]
            if sp:
                sp.state = [kp[r] - kp[l], kp[d] - kp[u], kp[lr] - kp[ll], kp[ld] - kp[lu], kp[c1], kp[c2]]
        self.frame("CONTROLLER CHECK")
        W, H = self.screen.get_size()
        for i in range(2):
            x0 = 60 + i * (W // 2)
            col = BLUE if i == 0 else RED
            v = self.hub.vector(i)
            self.text(f"PLAYER {i + 1}", (x0, 150), self.f_mid, col)
            for s, (ax, ay, btn, label) in enumerate([(0, 1, 4, "LEFT  move / click=crouch"), (2, 3, 5, "RIGHT look / click=shoot")]):
                cx, cy = x0 + 90 + s * 220, 290
                pygame.draw.circle(self.screen, (40, 46, 52), (cx, cy), 70)
                pygame.draw.circle(self.screen, DIM, (cx, cy), 70, 2)
                dot = (int(cx + v[ax] * 60), int(cy - v[ay] * 60))
                pygame.draw.circle(self.screen, ACC if v[btn] else col, dot, 16 if v[btn] else 12)
                self.text(label, (cx, cy + 80), self.f_small, FG, True)
            p = self.hub.pad(i)
            self.text(f"raw: {getattr(p, 'raw', '')[:42]}" if p else "raw: -", (x0, 410), self.f_small, DIM)
        y = 450
        self.text("PORTS FOUND:", (60, y), self.f, ACC)
        y += 28
        for dev, desc, hwid in self.hub.ports_info[:7]:
            r = self.hub.readers.get(dev)
            role = " = P1" if self.hub.assigned[0] == dev else " = P2" if self.hub.assigned[1] == dev else ""
            st = r.status if r else ""
            self.text(f"{dev:<7}{role:<6} {desc[:42]:<44} {st}", (60, y), self.f_small, GREEN if role else FG)
            y += 20
        if not self.hub.ports_info:
            self.text("no COM ports yet - pair the HC-05 in Windows Bluetooth settings or plug in a USB cable",
                      (60, y), self.f_small, DIM)
        if self.hub.error:
            self.text(self.hub.error, (60, y + 22), self.f_small, RED)
        self.text("1-4 / 5-8 flip P1 / P2 axes   S swap players   R recalibrate   F1/F2 simulated pad   Esc back",
                  (W // 2, H - 84), self.f_small, DIM, True)

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
