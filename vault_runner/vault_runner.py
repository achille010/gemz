#!/usr/bin/env python3
"""
VAULT RUNNER - a first-person 3D stealth heist.  pygame + numpy.

Steal loot, grab the keycard, reach the vault door before the alarm sounds.
Read MANUAL.md for controls and the customization menu.
"""
import json
import math
import os
import random
import re
import sys
import threading
import time
from collections import deque

import numpy as np
import pygame

from textures import T, make_sprites, make_textures

HERE = os.path.dirname(os.path.abspath(__file__))

# =====================================================================
#  CUSTOMIZE ME  -  every value here is safe to change
# =====================================================================
CONFIG = {
    # --- display / look ---------------------------------------------
    "window_size": (1280, 720),
    "render_size": (480, 270),   # internal 3D resolution. 640x360 = prettier, slower
    "fullscreen": False,
    "smooth_scaling": True,      # False = crunchy retro pixels
    "fov_degrees": 70,
    "film_grain": 0.035,         # 0 = off
    "vignette": 0.55,            # 0 = off
    "haze": 0.10,                # distance fog strength
    "ambient_light": 0.05,       # raise for easier / brighter game
    "torch_strength": 1.7,
    "lamp_strength": 1.0,
    "head_bob": True,
    "head_bob_z": 1.0,           # real up/down eye movement (0 = off, 2 = double). Small by design
    "sound": True,
    "volume": 0.8,               # master volume 0..1 for every sound effect
    # per-sound volume (0 = mute that one sound). Names: coin bar gem key caught step spot door
    # click blip tick confirm back pause start jump land whoosh sneak pant lost shutter win lose
    # pad buy deny alarm hum.   Your own sound: drop  sounds/<name>.wav  (or .ogg) next to the game.
    "sound_volumes": {"step": 0.7, "hum": 0.6, "alarm": 0.7},
    # --- controls ---------------------------------------------------
    "mouse_sensitivity": 0.0022,
    "turn_speed": 2.2,           # arrow-key turning, radians / second
    # --- gamepad (two-stick pad). Run `python vault_runner.py --joytest`
    #     to see which axis / button numbers YOUR pad reports, then edit here.
    "gamepad": {
        "move_x": 0, "move_y": 1,      # left stick axes
        "look_x": 2, "look_y": 3,      # right stick (try 3 / 4 if it doesn't turn)
        "invert_move_y": False,
        "invert_look_x": False,
        "invert_look_y": False,
        "deadzone": 0.18,
        "look_speed": 2.8,             # radians / second at full deflection
        # button number -> action.  Actions: interact, torch, sneak, map, sprint,
        # jump, center (level the view), pause, use_or_jump (door if near, else jump)
        "buttons": {0: "interact", 1: "torch", 2: "sneak", 3: "map", 4: "sprint", 5: "jump",
                    6: "center", 7: "pause", 8: "sprint", 9: "jump", 10: "sprint", 11: "use_or_jump"},
    },
    # --- Arduino UNO pad over USB serial (a stock UNO is NOT seen as a gamepad by
    #     Windows; it's a COM port). Flash arduino/vault_pad/vault_pad.ino, or use any
    #     sketch that prints one line per reading:  lx, ly, rx, ry[, btn0, btn1, ...]
    "arduino": {
        "enabled": True,
        "port": "auto",                # or e.g. "COM5"
        "baud": 115200,                # other common rates are tried automatically
        "axes": {"move_x": 0, "move_y": 1, "look_x": 2, "look_y": 3},   # column order in the line
        "invert_move_x": False, "invert_move_y": False,
        "invert_look_x": False, "invert_look_y": False,
        "swap_sticks": False,          # True if left/right sticks are wired the other way round
        "deadzone": 0.12,
        # The stick clicks (D2, D3) each do three things: quick tap, double tap, hold.
        "clicks": {0: {"tap": "torch", "double": "map", "hold": "sprint"},          # left stick click
                   1: {"tap": "use_or_jump", "double": "center", "hold": "sneak"}},  # right stick click
        # one-stick sketches (lines like "x,y,sw"): stick walks forward/back and turns
        "single_click": {"tap": "use_or_jump", "double": "torch", "hold": "sprint"},
        "hold_time": 0.35,             # seconds before a press counts as "hold"
        "double_time": 0.28,           # max gap between the two taps of a double tap
        # optional extra push buttons D4..D9 (column index after the axes) -> action
        "buttons": {2: "torch", 3: "map", 4: "sneak", 5: "jump", 6: "pause", 7: "center"},
        "both_clicks_pause": True,     # press both stick clicks together = pause
    },
    "pitch_limit": 0.6,               # how far you can look up / down (fraction of screen)
    "jump_speed": 2.1,
    "gravity": 8.0,
    "crouch_depth": 0.16,             # sneaking lowers the camera by this much
    # --- player -----------------------------------------------------
    "walk_speed": 2.6,          # tiles per second
    "sprint_speed": 4.4,
    "sneak_speed": 1.3,
    "stamina_max": 100.0,
    "stamina_drain": 32.0,
    "stamina_regen": 16.0,
    "start_lives": 3,
    "start_cash": 0,
    # --- economy / scoring -----------------------------------------
    "loot_values": {"coin": 100, "bar": 500, "gem": 1000},
    "time_bonus_per_second": 10,
    "stealth_bonus": 1000,       # finishing a level without being spotted
    "full_loot_bonus": 1500,     # collecting every item on a level
    "caught_cash_penalty": 0.30, # fraction of cash lost when caught
    # --- levels -----------------------------------------------------
    "levels_to_win": 8,
    "level_time_base": 100,
    "level_time_per_cell": 6,
    # --- guards -----------------------------------------------------
    "guard_patrol_speed": 1.4,
    "guard_chase_speed": 3.0,
    "guard_vision": 9.0,
    "guard_torch": True,         # guards carry a flashlight you can see
    "alarm_speed_boost": 1.25,
    # --- difficulty presets (multipliers) ---------------------------
    "difficulties": {
        "Easy":   dict(guards=0.6, gspeed=0.85, vision=0.8, time=1.3, loot=1.0),
        "Normal": dict(guards=1.0, gspeed=1.00, vision=1.0, time=1.0, loot=1.0),
        "Hard":   dict(guards=1.5, gspeed=1.15, vision=1.2, time=0.8, loot=1.25),
    },
    # --- shop: (id, name, base price, description, max level) ------
    "upgrades": [
        ("shoes",   "Running Shoes",  1500, "+8% move speed",          5),
        ("torch",   "Lithium Torch",  1200, "+15% flashlight power",   5),
        ("soles",   "Soft Soles",     2000, "guards see you 12% less", 5),
        ("watch",   "Stopwatch",      1000, "+15 seconds per level",   5),
        ("life",    "Spare Life",     3000, "+1 life",                 3),
    ],
}
C = CONFIG
DIRS = ((1, 0), (-1, 0), (0, 1), (0, -1))
WALL_OF_THEME = {0: 3, 1: 1, 2: 2, 3: 4}     # marble, brick, concrete, metal

SPRITE_DEFS = {   # scale (height in wall units), lift, aspect (w/h), emissive glow
    "coin":        (0.20, 0.30, 1.0, 0.45),
    "bar":         (0.22, 0.00, 1.0, 0.15),
    "gem":         (0.24, 0.30, 1.0, 0.70),
    "key":         (0.30, 0.40, 1.0, 0.85),
    "guard":       (0.85, 0.00, 0.5, 0.00),
    "guard_alert": (0.85, 0.00, 0.5, 0.00),
}


# =====================================================================
#  Level generation
# =====================================================================
def bfs_path(walk, s, t):
    if s == t:
        return []
    prev = {s: None}
    dq = deque([s])
    while dq:
        c = dq.popleft()
        if c == t:
            break
        for dx, dy in DIRS:
            n = (c[0] + dx, c[1] + dy)
            if n not in prev and walk[n[1]][n[0]]:
                prev[n] = c
                dq.append(n)
    if t not in prev:
        return []
    path, c = [], t
    while c != s:
        path.append(c)
        c = prev[c]
    path.reverse()
    return path


def bfs_dist(walk, s):
    h, w = len(walk), len(walk[0])
    dist = [[-1] * w for _ in range(h)]
    dist[s[1]][s[0]] = 0
    dq = deque([s])
    while dq:
        x, y = dq.popleft()
        for dx, dy in DIRS:
            nx, ny = x + dx, y + dy
            if walk[ny][nx] and dist[ny][nx] < 0:
                dist[ny][nx] = dist[y][x] + 1
                dq.append((nx, ny))
    return dist


class Guard:
    def __init__(self, x, y, rng):
        self.x, self.y = x, y
        self.face = rng.uniform(0, math.tau)
        self.state = "patrol"
        self.path = []
        self.lost = 0.0
        self.repath = 0.0
        self.stun = 0.0


class Level:
    def __init__(self, n, diff, rng):
        self.n = n
        cells = min(6 + 2 * n, 19)
        self.cells = cells
        gw = gh = cells * 2 + 1
        self.gw, self.gh = gw, gh
        grid = np.full((gh, gw), -1, np.int8)
        theme = np.full((gh, gw), 3, np.int8)

        # maze (randomised depth-first search)
        stack, seen = [(0, 0)], {(0, 0)}
        grid[1, 1] = 0
        while stack:
            cx, cy = stack[-1]
            nb = [(cx + dx, cy + dy) for dx, dy in DIRS
                  if 0 <= cx + dx < cells and 0 <= cy + dy < cells and (cx + dx, cy + dy) not in seen]
            if not nb:
                stack.pop()
                continue
            nx, ny = rng.choice(nb)
            seen.add((nx, ny))
            grid[cy + ny + 1, cx + nx + 1] = 0
            grid[2 * ny + 1, 2 * nx + 1] = 0
            stack.append((nx, ny))

        # rooms with their own materials
        self.rooms = []
        for _ in range(6 + 2 * n):
            rw, rh = rng.choice((3, 5)), rng.choice((3, 5))
            x0 = 1 + 2 * rng.randint(0, (gw - 2 - rw) // 2)
            y0 = 1 + 2 * rng.randint(0, (gh - 2 - rh) // 2)
            if any(x0 - 1 < r[0] + r[2] + 1 and r[0] - 1 < x0 + rw + 1 and
                   y0 - 1 < r[1] + r[3] + 1 and r[1] - 1 < y0 + rh + 1 for r in self.rooms):
                continue
            th = rng.randint(0, 2)
            grid[y0:y0 + rh, x0:x0 + rw] = 0
            theme[y0:y0 + rh, x0:x0 + rw] = th
            if rw == 5 and rh == 5:
                grid[y0 + 2, x0 + 2] = WALL_OF_THEME[th]      # pillar
            self.rooms.append((x0, y0, rw, rh, th))

        # extra doorways so the maze has loops
        for _ in range(cells * cells // 4):
            x, y = rng.randint(1, gw - 2), rng.randint(1, gh - 2)
            if grid[y, x] == -1 and ((grid[y, x - 1] == 0 and grid[y, x + 1] == 0) or
                                     (grid[y - 1, x] == 0 and grid[y + 1, x] == 0)):
                grid[y, x] = 0

        # wall materials follow the neighbouring room
        for y, x in np.argwhere(grid == -1):
            th = 3
            for dx, dy in DIRS:
                yy, xx = y + dy, x + dx
                if 0 <= yy < gh and 0 <= xx < gw and grid[yy, xx] == 0 and theme[yy, xx] != 3:
                    th = int(theme[yy, xx])
                    break
            grid[y, x] = WALL_OF_THEME[th]

        self.walk = (grid == 0).tolist()
        self.start = (1, 1)
        dist = bfs_dist(self.walk, self.start)
        opens = [(x, y) for y in range(gh) for x in range(gw) if self.walk[y][x]]
        maxd = max(dist[y][x] for x, y in opens)
        far = max(opens, key=lambda c: dist[c[1]][c[0]])

        # vault door: a wall next to the farthest cell (prefer the outer wall)
        cands = [(far[0] + dx, far[1] + dy) for dx, dy in DIRS if grid[far[1] + dy, far[0] + dx] > 0]
        border = [c for c in cands if c[0] in (0, gw - 1) or c[1] in (0, gh - 1)]
        self.exit = rng.choice(border or cands)
        grid[self.exit[1], self.exit[0]] = 5
        self.exit_near = far
        self.grid = grid
        self.floor = theme.copy()
        self.dist = dist
        self.maxd = maxd

        used = {self.start, far}
        free = [c for c in opens if dist[c[1]][c[0]] >= 4 and c not in used]
        rng.shuffle(free)
        dead = [c for c in free if sum(self.walk[c[1] + dy][c[0] + dx] for dx, dy in DIRS) == 1]

        def take(pool, k):
            out = []
            for c in list(pool):
                if len(out) >= k:
                    break
                if c not in used:
                    used.add(c)
                    out.append(c)
            return out

        far_pool = [c for c in free if 0.45 * maxd <= dist[c[1]][c[0]] <= 0.9 * maxd]
        key_cell = take(far_pool or free, 1)[0]
        self.items = [dict(kind="key", x=key_cell[0] + .5, y=key_cell[1] + .5, phase=rng.random() * 6)]
        for kind, k in (("gem", 2 + n), ("bar", 4 + n), ("coin", 12 + 4 * n)):
            cs = take(dead, k) if kind != "coin" else []
            cs += take(free, k - len(cs))
            for c in cs:
                self.items.append(dict(kind=kind, x=c[0] + .5, y=c[1] + .5, phase=rng.random() * 6))
        self.loot_total = len(self.items) - 1

        # guards
        n_g = max(1, min(7, round((1 + (n + 1) // 2) * diff["guards"])))
        spots = [c for c in opens if dist[c[1]][c[0]] >= max(8, int(maxd * 0.25))]
        rng.shuffle(spots)
        self.guards = []
        for c in spots:
            if len(self.guards) >= n_g:
                break
            if all(math.hypot(c[0] - g.x, c[1] - g.y) > 7 for g in self.guards):
                self.guards.append(Guard(c[0] + .5, c[1] + .5, rng))

        # ceiling lamps
        self.lamps = []
        for x0, y0, rw, rh, th in self.rooms:
            self.lamps.append((x0 + rw / 2, y0 + rh / 2, 1.1, rng.random() < 0.3, rng.random() * 6))
        for x, y in opens:
            if rng.random() < 0.10 and all(math.hypot(x + .5 - l[0], y + .5 - l[1]) > 4 for l in self.lamps):
                self.lamps.append((x + .5, y + .5, 0.85, rng.random() < 0.25, rng.random() * 6))
        self.lamps.append((1.5, 1.5, 0.9, False, 0.0))
        self.lamps.append((far[0] + .5, far[1] + .5, 0.9, True, 1.0))
        self.explored = np.zeros((gh, gw), bool)


# =====================================================================
#  Renderer (numpy raycaster with per-pixel lighting)
# =====================================================================
class Renderer:
    def __init__(self, W, H, fov):
        self.W, self.H = W, H
        self.f = math.tan(math.radians(fov) / 2)
        self.K = W / (2 * self.f)                       # pixels per unit at depth 1
        self.cam = (2 * (np.arange(W, dtype=np.float32) + .5) / W - 1)
        self.ys = np.arange(H, dtype=np.float32)[:, None] + .5
        self.walls, self.flats = make_textures()
        self.sprites = make_sprites()
        rx = (np.arange(W, dtype=np.float32)[None, :] + .5 - W / 2) / self.K
        ry = (self.ys - H / 2) / self.K
        self.r2 = (rx * rx + ry * ry).astype(np.float32)
        self.beam2 = np.exp(-self.r2 * 6)[::2, ::2].astype(np.float32)
        v = max(C["vignette"], 0.0)
        vig = 1 - v * np.clip(self.r2 / 0.9, 0, 1) ** 1.3
        self.vig = vig[..., None].astype(np.float32)
        gr = C["film_grain"]
        self.vg = [(self.vig * (1 + gr * np.random.standard_normal((H, W, 1)))).astype(np.float32)
                   for _ in range(6 if gr > 0 else 1)]
        self.gi = 0
        self.alltex = np.concatenate([self.walls, self.flats]).reshape(-1, 3).astype(np.float32)
        self.surf = pygame.Surface((W, H))

    def _lamp_sum(self, lamps, wx, wy):
        s = 0
        for lx, ly, li in lamps:
            s = s + li / (1 + 2.2 * ((wx - lx) ** 2 + (wy - ly) ** 2 + 0.35))
        return s * C["lamp_strength"]

    def render(self, px, py, ang, bob, level, sprites, lamps, torch_on, torch_k, tint, boost=0.0, zeye=0.5):
        W, H, K = self.W, self.H, self.K
        grid = level.grid
        gh, gw = grid.shape
        horizon = H / 2 + bob
        dirx, diry = math.cos(ang), math.sin(ang)
        planex, planey = -diry * self.f, dirx * self.f
        rdx = dirx + planex * self.cam
        rdy = diry + planey * self.cam

        # ---- DDA: all columns at once
        with np.errstate(divide="ignore"):
            ddx = np.abs(1 / np.where(rdx == 0, 1e-9, rdx))
            ddy = np.abs(1 / np.where(rdy == 0, 1e-9, rdy))
        mapx = np.full(W, int(px))
        mapy = np.full(W, int(py))
        stepx = np.where(rdx < 0, -1, 1)
        stepy = np.where(rdy < 0, -1, 1)
        sidex = np.where(rdx < 0, (px - mapx) * ddx, (mapx + 1 - px) * ddx)
        sidey = np.where(rdy < 0, (py - mapy) * ddy, (mapy + 1 - py) * ddy)
        hit = np.zeros(W, bool)
        side = np.zeros(W, np.int8)
        for _ in range(gw + gh):
            act = ~hit
            if not act.any():
                break
            xs_ = sidex < sidey
            mx, my = act & xs_, act & ~xs_
            sidex = np.where(mx, sidex + ddx, sidex)
            sidey = np.where(my, sidey + ddy, sidey)
            mapx = mapx + stepx * mx
            mapy = mapy + stepy * my
            side = np.where(mx, 0, np.where(my, 1, side))
            hit |= act & (grid[mapy, mapx] > 0)
        perp = np.maximum(np.where(side == 0, sidex - ddx, sidey - ddy), 0.05).astype(np.float32)
        hx, hy = px + perp * rdx, py + perp * rdy
        wallx = np.where(side == 0, hy, hx)
        wallx = wallx - np.floor(wallx)
        texx = (wallx * T).astype(np.int32)
        flip = ((side == 0) & (rdx > 0)) | ((side == 1) & (rdy < 0))
        texx = np.where(flip, T - 1 - texx, texx)
        wid = grid[mapy, mapx].astype(np.int32)

        # ---- walls
        lineh = K / perp
        top = horizon + (zeye - 1.0) * lineh
        d = (self.ys - top[None, :]) / lineh[None, :]
        wmask = (d >= 0) & (d < 1)
        ty_w = (np.clip(d, 0, 0.999) * T).astype(np.int32)

        # ---- floor & ceiling
        denom = self.ys - horizon
        rowdist = np.minimum(np.where(denom > 0, zeye, 1.0 - zeye) * K / np.maximum(np.abs(denom), 0.5), 60).astype(np.float32)
        fx = px + rowdist * rdx[None, :]
        fy = py + rowdist * rdy[None, :]
        cell = fy.astype(np.int32) * gw + fx.astype(np.int32)
        sel = np.where(denom > 0, level.floor.ravel().take(cell, mode="clip"), 4)

        # one combined texture fetch for walls + floor + ceiling
        tid = np.where(wmask, wid[None, :], 7 + sel)
        ty = np.where(wmask, ty_w, (fy * T).astype(np.int32) & (T - 1))
        tx = np.where(wmask, texx[None, :], (fx * T).astype(np.int32) & (T - 1))
        img = self.alltex.take((tid * T + ty) * T + tx, axis=0)
        shade = np.where(wmask, (0.65 + 0.35 * np.clip(6 * d * (1 - d), 0, 1)) *
                         np.where(side == 1, 0.78, 1.0)[None, :], 1.0).astype(np.float32)
        img *= shade[..., None]

        # ---- lighting
        # (lighting is smooth, so it is computed at half resolution and upsampled)
        wm2 = wmask[::2, ::2]
        d2 = np.where(wm2, perp[None, ::2], rowdist[::2])
        wx2 = np.where(wm2, hx[None, ::2], fx[::2, ::2])
        wy2 = np.where(wm2, hy[None, ::2], fy[::2, ::2])
        base = C["ambient_light"] + boost
        if torch_on:
            base = base + torch_k * self.beam2 / (1 + 0.12 * d2 * d2)
        else:
            base = np.full(d2.shape, base, np.float32)
        lamp = self._lamp_sum(lamps, wx2, wy2)
        lit = (base[..., None] * np.array([1.0, 0.96, 0.88], np.float32) +
               np.asarray(lamp, np.float32)[..., None] * np.array([1.0, 0.78, 0.5], np.float32)) \
            * np.array(tint, np.float32)
        haze = ((1 - np.exp(-d2 * 0.18)) * C["haze"])[..., None].astype(np.float32)
        fog = haze * np.array([14, 18, 26], np.float32) * (0.3 + lit.mean(-1, keepdims=True))
        lit = lit * (1 - haze)

        def up(a):
            return np.repeat(np.repeat(a, 2, 0), 2, 1)[:H, :W]
        img *= up(lit)
        img += up(fog)

        # ---- sprites
        self._sprites(img, perp, (px, py, dirx, diry, planex, planey, horizon, zeye), sprites, lamps, torch_on,
                      torch_k, tint, boost)

        # ---- post: tone-map, vignette, grain
        img *= 1 / 255.0
        t = img + 1
        img *= img * (1 / 2.56) + 1
        img /= t
        self.gi = (self.gi + 1) % len(self.vg)
        img *= self.vg[self.gi]                     # vignette + film grain
        np.clip(img, 0, 1, out=img)
        img *= 255
        self.surf = pygame.image.frombuffer(img.astype(np.uint8).tobytes(), (W, H), "RGB")
        return self.surf

    def _sprites(self, img, zbuf, cam, sprites, lamps, torch_on, torch_k, tint, boost):
        W, H, K = self.W, self.H, self.K
        px, py, dirx, diry, planex, planey, horizon, zeye = cam
        inv = 1.0 / (planex * diry - dirx * planey)
        order = sorted(sprites, key=lambda s: -((s["x"] - px) ** 2 + (s["y"] - py) ** 2))
        for s in order:
            sx, sy = s["x"] - px, s["y"] - py
            tx = inv * (diry * sx - dirx * sy)
            ty = inv * (-planey * sx + planex * sy)
            if ty < 0.12:
                continue
            scale, lift, aspect, emi = SPRITE_DEFS[s["name"]]
            lift += s.get("bob", 0.0)
            scr_x = W / 2 * (1 + tx / ty)
            h = scale * K / ty
            w = h * aspect
            bottom = horizon + (zeye - lift) * K / ty
            x0, x1 = int(scr_x - w / 2), int(scr_x + w / 2)
            y0, y1 = int(bottom - h), int(bottom)
            cx0, cx1, cy0, cy1 = max(x0, 0), min(x1, W), max(y0, 0), min(y1, H)
            if cx0 >= cx1 or cy0 >= cy1 or x1 == x0 or y1 == y0:
                continue
            rgb, alpha = self.sprites[s["name"]]
            th, tw = alpha.shape
            u = np.clip(((np.arange(cx0, cx1) + .5 - x0) / (x1 - x0) * tw).astype(int), 0, tw - 1)
            v = np.clip(((np.arange(cy0, cy1) + .5 - y0) / (y1 - y0) * th).astype(int), 0, th - 1)
            vis = zbuf[cx0:cx1] > ty
            a = alpha[v[:, None], u[None, :]] & vis[None, :]
            if not a.any():
                continue
            col = rgb[v[:, None], u[None, :]]
            dist = math.hypot(sx, sy)
            L = C["ambient_light"] + boost
            if torch_on:
                r2 = ((scr_x - W / 2) / K) ** 2 + ((bottom - h / 2 - H / 2) / K) ** 2
                L += torch_k * math.exp(-r2 * 6) / (1 + 0.12 * dist * dist)
            lamp = self._lamp_sum(lamps, s["x"], s["y"])
            rgbl = (L * np.array([1.0, 0.96, 0.88]) + lamp * np.array([1.0, 0.78, 0.5])) * np.array(tint)
            rgbl = rgbl + emi
            region = img[cy0:cy1, cx0:cx1]
            region[a] = col[a] * rgbl.astype(np.float32)


# =====================================================================
#  Sound (synthesised, optional)
# =====================================================================
class Sfx:
    def __init__(self, enabled):
        self.ok = False
        self.snd = {}
        if not enabled:
            return
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(44100, -16, 2, 512)
            pygame.mixer.set_num_channels(16)
            sr, _, chans = pygame.mixer.get_init()   # the device may force stereo / another rate
            self.ok = True

            def tone(freqs, dur, vol=0.35, decay=6, noise=0.0):
                t = np.arange(int(sr * dur)) / sr
                w = sum(np.sin(2 * np.pi * f * t) for f in freqs) / len(freqs)
                env = np.exp(-decay * t)
                w = (w * vol + noise * np.random.randn(len(t))) * env
                return np.clip(w, -1, 1)

            def mk(w):
                a = (np.clip(w, -1, 1) * 32767).astype(np.int16)
                if chans > 1:                              # mono -> every output channel
                    a = np.repeat(a[:, None], chans, 1)
                return pygame.sndarray.make_sound(np.ascontiguousarray(a))

            self.snd["coin"] = mk(tone([1200, 1800], 0.25))
            self.snd["bar"] = mk(tone([660, 990, 1320], 0.4))
            self.snd["gem"] = mk(tone([1568, 2093, 2637], 0.6, decay=4))
            self.snd["key"] = mk(np.concatenate([tone([f], 0.16, decay=8) for f in (523, 659, 784, 1047)]))
            self.snd["caught"] = mk(tone([90, 60], 0.7, 0.6, 4, 0.3))
            self.snd["step"] = mk(tone([70], 0.07, 0.5, 45, 0.5))
            self.snd["spot"] = mk(np.concatenate([tone([900], 0.12, decay=3), tone([1200], 0.18, decay=3)]))
            self.snd["door"] = mk(np.concatenate([tone([f], 0.1, decay=5) for f in (300, 400, 520, 700)]))
            self.snd["click"] = mk(tone([2400, 3100], 0.05, 0.4, 60, 0.2))          # flashlight switch
            self.snd["blip"] = mk(tone([1000], 0.06, 0.25, 30))                     # map / help / nothing to use
            self.snd["tick"] = mk(tone([1500], 0.04, 0.22, 60))                     # menu move, countdown
            self.snd["confirm"] = mk(np.concatenate([tone([660], 0.07, decay=12), tone([990], 0.12, decay=8)]))
            self.snd["back"] = mk(np.concatenate([tone([700], 0.07, decay=12), tone([440], 0.12, decay=8)]))
            self.snd["pause"] = mk(tone([440, 330], 0.2, 0.3, 10))
            self.snd["start"] = mk(np.concatenate([tone([f], 0.09, decay=9) for f in (392, 523, 659, 784)]))
            t = np.arange(int(sr * 0.22)) / sr
            self.snd["jump"] = mk(0.3 * np.sin(2 * np.pi * np.cumsum(220 + 900 * t) / sr) * np.exp(-8 * t))
            self.snd["land"] = mk(tone([55], 0.12, 0.6, 30, 0.6))
            self.snd["whoosh"] = mk(np.convolve(np.random.randn(int(sr * 0.25)), np.ones(40) / 40, "same")
                                    * 0.5 * np.sin(np.linspace(0, np.pi, int(sr * 0.25))))
            self.snd["sneak"] = mk(tone([180], 0.15, 0.25, 12, 0.08))
            self.snd["pant"] = mk(np.concatenate([tone([0.1], 0.25, 0, 5, 0.25), tone([0.1], 0.3, 0, 5, 0.18)]))
            self.snd["lost"] = mk(np.concatenate([tone([700], 0.12, decay=5), tone([500], 0.2, decay=5)]))
            self.snd["shutter"] = mk(np.concatenate([tone([0.1], 0.03, 0, 80, 0.6), tone([0.1], 0.05, 0, 60, 0.5)]))
            self.snd["win"] = mk(np.concatenate([tone([f, f * 1.5], 0.16, decay=4) for f in (523, 659, 784, 1047, 1319)]))
            self.snd["lose"] = mk(np.concatenate([tone([f], 0.3, decay=3) for f in (392, 330, 262, 196)]))
            self.snd["pad"] = mk(np.concatenate([tone([880], 0.08, decay=10), tone([1320], 0.1, decay=10)]))
            self.snd["buy"] = mk(tone([880, 1320], 0.3))
            self.snd["deny"] = mk(tone([160], 0.25, 0.5, 7))
            t = np.arange(sr) / sr
            self.snd["alarm"] = mk(0.3 * np.sin(2 * np.pi * np.cumsum(800 + 300 * np.sin(2 * np.pi * 2 * t)) / sr))
            self.snd["hum"] = mk(0.10 * (np.sin(2 * np.pi * 55 * np.arange(2 * sr) / sr) +
                                         0.5 * np.sin(2 * np.pi * 110 * np.arange(2 * sr) / sr)))
            self._custom_and_volume()
        except Exception as ex:
            print("Sound disabled:", ex)
            self.ok = False

    def _custom_and_volume(self):
        folder = os.path.join(HERE, "sounds")
        if os.path.isdir(folder):
            for fn in os.listdir(folder):
                name, ext = os.path.splitext(fn)
                if ext.lower() in (".wav", ".ogg", ".mp3"):
                    try:
                        self.snd[name] = pygame.mixer.Sound(os.path.join(folder, fn))
                    except Exception as ex:
                        print(f"Could not load sounds/{fn}: {ex}")
        for name, snd in self.snd.items():
            snd.set_volume(max(0.0, min(1.0, C["volume"] * C["sound_volumes"].get(name, 1.0))))

    def play(self, name, loops=0):
        if self.ok and name in self.snd:
            self.snd[name].play(loops=loops)

    def stop(self, name):
        if self.ok and name in self.snd:
            self.snd[name].stop()


# =====================================================================
#  Arduino pad over USB serial
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


# =====================================================================
#  Game
# =====================================================================
class Player:
    def __init__(self):
        self.x = self.y = 1.5
        self.angle = 0.0
        self.stamina = C["stamina_max"]
        self.bob = 0.0
        self.step_acc = 0.0
        self.moving = self.sprinting = self.sneaking = False
        self.zamp = 0.0             # eased amplitude of vertical head movement
        self.breath = 0.0
        self.torch = True
        self.pitch = 0.0            # look up / down, -1..1
        self.z = self.vz = 0.0      # jump height and vertical speed
        self.crouch = 0.0           # eased camera drop while sneaking


class Game:
    def __init__(self):
        pygame.init()
        flags = pygame.FULLSCREEN if C["fullscreen"] else 0
        self.screen = pygame.display.set_mode(C["window_size"], flags)
        pygame.display.set_caption("VAULT RUNNER")
        self.clock = pygame.time.Clock()
        self.rw, self.rh = C["render_size"]
        self.renderer = Renderer(self.rw, self.rh, C["fov_degrees"])
        self.sfx = Sfx(C["sound"])
        self.f_big = pygame.font.SysFont("bahnschrift,consolas,arial", 64, bold=True)
        self.f_med = pygame.font.SysFont("bahnschrift,consolas,arial", 30, bold=True)
        self.f_sm = pygame.font.SysFont("bahnschrift,consolas,arial", 20)
        self.diff_names = list(C["difficulties"])
        self.diff_i = 1
        self.rng = random.Random()
        self.hi_path = os.path.join(HERE, "highscore.json")
        self.hi = self._load_hi()
        self.state = "title"
        self.t = 0.0
        self.mouse_dx = 0.0
        self.captured = False
        self.map_mode = 1
        self.show_help = False
        self.last_frame = None
        self.popups = []
        self.flash = 0.0
        self.new_run_level = None
        self.shop_i = 0
        self.pad = None
        self.mouse_dy = 0.0
        self.menu_dir = (0, 0)
        self.spad_prev = []
        self.combo_armed = True
        self.spad_clicks = {}      # button -> [pressed_at, taps, released_at]
        self.spad_holding = {}     # button -> hold action currently active
        self.low_tick = 0
        pygame.joystick.init()
        for i in range(pygame.joystick.get_count()):
            self._open_pad(i)
        self.spad = SerialPad(C["arduino"]) if C["arduino"]["enabled"] else None
        self.spad_seen = False
        self.start_level(1, demo=True)

    # ------------------------------------------------------------ gamepad
    def _open_pad(self, index):
        if self.pad is not None:
            return
        try:
            self.pad = pygame.joystick.Joystick(index)
        except pygame.error:
            self.pad = None

    def axis(self, n):
        try:
            if self.pad and 0 <= n < self.pad.get_numaxes():
                v = self.pad.get_axis(n)
                dz = C["gamepad"]["deadzone"]
                if abs(v) < dz:
                    return 0.0
                return (abs(v) - dz) / (1 - dz) * (1 if v > 0 else -1)
        except pygame.error:
            pass
        return 0.0

    def button(self, n):
        try:
            return bool(self.pad and 0 <= n < self.pad.get_numbuttons() and self.pad.get_button(n))
        except pygame.error:
            return False

    def stick(self, name):
        """name = move_x / move_y / look_x / look_y. Combines USB gamepad + Arduino, -1..1."""
        gp, ar = C["gamepad"], C["arduino"]
        v = self.axis(gp[name]) * (-1 if gp.get("invert_" + name) else 1)
        if self.spad and self.spad.ready and self.spad.n_axes == 2:
            # one stick: push = walk forward/back, sideways = turn
            a = {"move_y": self.spad.axis(1), "look_x": self.spad.axis(0)}.get(name, 0.0)
            a *= -1 if ar.get("invert_" + name) else 1
            return a if abs(a) > abs(v) else v
        if self.spad and self.spad.ready:
            n = name
            if ar["swap_sticks"]:
                n = n.replace("move", "tmp").replace("look", "move").replace("tmp", "look")
            a = self.spad.axis(ar["axes"][n]) * (-1 if ar.get("invert_" + name) else 1)
            if abs(a) > abs(v):
                v = a
        return v

    def held(self, action):
        """Is any button bound to this action held down (USB pad or Arduino)?"""
        for b, act in C["gamepad"]["buttons"].items():
            if act == action and self.button(b):
                return True
        if self.spad and self.spad.ready:
            if action in self.spad_holding.values():
                return True
            if self.spad.n_axes == 4:
                for b, act in C["arduino"]["buttons"].items():
                    if act == action and self.spad.button(b):
                        return True
        return False

    def near_door(self):
        p, ex = self.player, self.level.exit
        return math.hypot(p.x - ex[0] - .5, p.y - ex[1] - .5) < 1.6

    def on_action(self, act):
        """A pad button was pressed: do what it means on the current screen."""
        s = self.state
        if act == "use_or_jump":
            act = "interact" if s != "play" or self.near_door() else "jump"
        k = None
        if s == "play":
            if act == "jump":
                self.jump()
            elif act == "center":
                self.player.pitch = 0.0
                self.sfx.play("click")
            elif act == "sneak":
                self.sfx.play("sneak")
            elif act == "sprint":
                if self.player.stamina > 1:
                    self.sfx.play("whoosh")
            else:
                k = {"interact": pygame.K_e, "torch": pygame.K_f, "map": pygame.K_TAB,
                     "pause": pygame.K_ESCAPE}.get(act)
        elif s == "shop":
            k = {"interact": pygame.K_e, "pause": pygame.K_RETURN, "jump": pygame.K_RETURN,
                 "sprint": pygame.K_RETURN, "map": pygame.K_DOWN, "torch": pygame.K_UP}.get(act)
        elif s == "pause":
            k = {"interact": pygame.K_ESCAPE, "pause": pygame.K_ESCAPE, "jump": pygame.K_ESCAPE,
                 "torch": pygame.K_q, "sprint": pygame.K_q, "map": pygame.K_F1}.get(act)
        elif s == "title":
            k = {"interact": pygame.K_RETURN, "pause": pygame.K_RETURN, "jump": pygame.K_RETURN,
                 "sprint": pygame.K_RIGHT, "torch": pygame.K_LEFT, "map": pygame.K_F1}.get(act)
        else:
            k = pygame.K_RETURN if act in ("interact", "pause", "jump", "sprint") else None
        if k:
            self.handle_event(pygame.event.Event(pygame.KEYDOWN, key=k))

    def jump(self):
        p = self.player
        if p.z <= 0.0 and p.vz == 0.0:
            p.vz = C["jump_speed"]
            self.sfx.play("jump")

    def _click(self, i, g, down, was, now):
        """Stick click gestures: tap / double tap / hold, each its own action."""
        ar = C["arduino"]
        st = self.spad_clicks.get(i)
        if down and not was:
            if st and st[2] and now - st[2] < ar["double_time"]:
                st[0], st[1] = now, st[1] + 1
            else:
                self.spad_clicks[i] = [now, 1, 0.0]
        elif down and st and i not in self.spad_holding and st[1] == 1 and now - st[0] >= ar["hold_time"]:
            self.spad_holding[i] = g["hold"]
            self.on_action(g["hold"])
        elif not down and was and st:
            if self.spad_holding.pop(i, None):
                self.spad_clicks.pop(i, None)
            elif st[1] >= 2:
                self.spad_clicks.pop(i, None)
                self.on_action(g["double"])
            else:
                st[2] = now
        elif not down and st and st[2] and now - st[2] >= ar["double_time"]:
            self.spad_clicks.pop(i, None)
            self.on_action(g["tap"])

    def poll_serial(self):
        """Turn Arduino button edges into actions; the left stick drives the menus."""
        sp = self.spad
        if sp and sp.ready and not self.spad_seen:
            self.spad_seen = True
            self.sfx.play("pad")
            self.say(f"Arduino pad {sp.status}", 3)
        elif sp and self.spad_seen and not sp.ready:
            self.spad_seen = False
            self.say("Arduino pad disconnected", 3)
        if sp and sp.ready:
            ar = C["arduino"]
            cur = [sp.button(i) for i in range(sp.num_buttons())]
            prev = self.spad_prev if len(self.spad_prev) == len(cur) else [False] * len(cur)
            self.spad_prev = cur
            clicks = ar["clicks"] if sp.n_axes == 4 else {0: ar["single_click"]}
            now = time.time()
            if ar["both_clicks_pause"] and len(clicks) >= 2 and len(cur) >= 2 and cur[0] and cur[1]:
                if self.combo_armed:
                    self.combo_armed = False
                    self.spad_clicks.clear()
                    self.spad_holding.clear()
                    self.on_action("pause")
            elif not self.combo_armed:
                if not any(cur[:2]):
                    self.combo_armed = True
            else:
                for i, g in clicks.items():
                    if i < len(cur):
                        self._click(i, g, cur[i], prev[i], now)
                if sp.n_axes == 4:
                    for i, act in ar["buttons"].items():
                        if i < len(cur) and cur[i] and not prev[i]:
                            self.on_action(act)
        # menus: the left stick acts like arrow keys (for pads without a D-pad)
        if self.state != "play":
            x, y = self.stick("move_x"), self.stick("move_y")
            d = (0, 0)
            if abs(x) > 0.6 and abs(x) >= abs(y):
                d = (1 if x > 0 else -1, 0)
            elif abs(y) > 0.6:
                d = (0, 1 if y > 0 else -1)
            if d != self.menu_dir and d != (0, 0):
                k = {(1, 0): pygame.K_RIGHT, (-1, 0): pygame.K_LEFT,
                     (0, 1): pygame.K_DOWN, (0, -1): pygame.K_UP}[d]
                self.handle_event(pygame.event.Event(pygame.KEYDOWN, key=k))
            self.menu_dir = d
        else:
            self.menu_dir = (0, 0)

    # ------------------------------------------------------------ setup
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

    @property
    def diff(self):
        return C["difficulties"][self.diff_names[self.diff_i]]

    def new_run(self):
        self.cash = C["start_cash"]
        self.score = 0
        self.lives = C["start_lives"]
        self.up = {u[0]: 0 for u in C["upgrades"]}
        self.level_no = 1
        self.start_level(1)
        self.set_state("play")

    def start_level(self, n, demo=False):
        self.level_no = n
        self.level = Level(n, self.diff, self.rng)
        self.player = Player()
        self.player.x = self.player.y = 1.5
        for a, (dx, dy) in enumerate(DIRS):           # face the first open direction
            if self.level.walk[1 + dy][1 + dx]:
                self.player.angle = math.atan2(dy, dx)
                break
        self.spotted = 0
        self.alarm = False
        self.has_key = False
        self.items = self.level.items
        self.loot_left = self.level.loot_total
        self.msg = ("", 0.0)
        self.popups = []
        cells = self.level.cells
        up_watch = getattr(self, "up", {}).get("watch", 0)
        self.time_left = ((C["level_time_base"] + C["level_time_per_cell"] * cells) * self.diff["time"]
                          + 15 * up_watch)
        self.level_time = self.time_left
        self.sfx.stop("alarm")
        if not demo:
            self.say(f"LEVEL {n}: find the KEYCARD, then reach the VAULT DOOR", 5)

    def set_state(self, s):
        self.state = s
        want = s == "play"
        pygame.mouse.set_visible(not want)
        pygame.event.set_grab(want)
        self.captured = want
        pygame.mouse.get_rel()
        if s == "play":
            self.sfx.play("hum", -1)
        else:
            self.sfx.stop("hum")
            self.sfx.stop("alarm")

    def say(self, text, secs=3.0):
        self.msg = (text, secs)

    def popup(self, text, color=(255, 230, 120)):
        self.popups.append([text, 1.6, color])

    # ------------------------------------------------------------ helpers
    def free(self, x, y, r=0.22):
        w = self.level.walk
        return (w[int(y - r)][int(x - r)] and w[int(y - r)][int(x + r)] and
                w[int(y + r)][int(x - r)] and w[int(y + r)][int(x + r)])

    def los(self, x0, y0, x1, y1):
        w = self.level.walk
        n = int(math.hypot(x1 - x0, y1 - y0) / 0.15) + 1
        for i in range(1, n):
            t = i / n
            if not w[int(y0 + (y1 - y0) * t)][int(x0 + (x1 - x0) * t)]:
                return False
        return True

    def player_speed(self):
        u = 1 + 0.08 * self.up["shoes"]
        p = self.player
        base = C["sprint_speed"] if p.sprinting else C["sneak_speed"] if p.sneaking else C["walk_speed"]
        return base * u

    # ------------------------------------------------------------ events
    def handle_event(self, e):
        if e.type == pygame.QUIT:
            pygame.quit()
            sys.exit()
        if e.type == pygame.JOYDEVICEADDED:
            self._open_pad(e.device_index)
            self.sfx.play("pad")
            return
        if e.type == pygame.JOYDEVICEREMOVED:
            self.pad = None
            return
        if e.type == pygame.JOYBUTTONDOWN:
            act = C["gamepad"]["buttons"].get(e.button)
            if act:
                self.on_action(act)
            return
        if e.type == pygame.JOYHATMOTION and self.state != "play":
            hx, hy = e.value
            k = {(-1, 0): pygame.K_LEFT, (1, 0): pygame.K_RIGHT, (0, 1): pygame.K_UP, (0, -1): pygame.K_DOWN}.get((hx, hy))
            if k:
                self.handle_event(pygame.event.Event(pygame.KEYDOWN, key=k))
            return
        if e.type == pygame.MOUSEMOTION and self.state == "play" and self.captured:
            self.mouse_dx += e.rel[0]
            self.mouse_dy += e.rel[1]
        if e.type != pygame.KEYDOWN:
            return
        k = e.key
        # numeric keypad (Num Lock ON): same actions as the main keys
        if k == pygame.K_KP_ENTER:
            k = pygame.K_e if self.state == "play" else pygame.K_RETURN
        elif k == pygame.K_KP_PLUS:
            k = pygame.K_f
        elif k == pygame.K_KP_MINUS:
            k = pygame.K_TAB
        elif self.state != "play":
            k = {pygame.K_KP4: pygame.K_LEFT, pygame.K_KP6: pygame.K_RIGHT,
                 pygame.K_KP8: pygame.K_UP, pygame.K_KP2: pygame.K_DOWN,
                 pygame.K_KP5: pygame.K_DOWN}.get(k, k)
        if k == pygame.K_F12:
            path = os.path.join(HERE, f"screenshot_{pygame.time.get_ticks()}.png")
            pygame.image.save(self.screen, path)
            self.sfx.play("shutter")
            self.say("Saved " + os.path.basename(path))
        elif k == pygame.K_F11:
            pygame.display.toggle_fullscreen()
            self.sfx.play("blip")
        elif k == pygame.K_F1:
            self.show_help = not self.show_help
            self.sfx.play("blip")
        elif k == pygame.K_F9 and self.spad:
            self.spad.recalibrate()
            self.sfx.play("pad")
            self.say("Arduino sticks re-centred - leave them untouched for a second", 3)
        elif self.state == "title":
            if k in (pygame.K_RETURN, pygame.K_SPACE):
                self.sfx.play("start")
                self.new_run()
            elif k in (pygame.K_LEFT, pygame.K_a):
                self.diff_i = (self.diff_i - 1) % len(self.diff_names)
                self.sfx.play("tick")
            elif k in (pygame.K_RIGHT, pygame.K_d):
                self.diff_i = (self.diff_i + 1) % len(self.diff_names)
                self.sfx.play("tick")
            elif k == pygame.K_ESCAPE:
                pygame.quit()
                sys.exit()
        elif self.state == "play":
            if k == pygame.K_ESCAPE or k == pygame.K_p:
                self.sfx.play("pause")
                self.set_state("pause")
            elif k == pygame.K_f:
                self.player.torch = not self.player.torch
                self.sfx.play("click")
            elif k == pygame.K_TAB:
                self.map_mode = (self.map_mode + 1) % 3
                self.sfx.play("blip")
            elif k == pygame.K_e:
                self.interact()
            elif k == pygame.K_SPACE:
                self.jump()
            elif k in (pygame.K_HOME, pygame.K_KP1):
                self.player.pitch = 0.0
                self.sfx.play("click")
        elif self.state == "pause":
            if k in (pygame.K_ESCAPE, pygame.K_p):
                self.sfx.play("confirm")
                self.set_state("play")
            elif k == pygame.K_q:
                self.sfx.play("back")
                self.set_state("title")
        elif self.state == "shop":
            n_up = len(C["upgrades"])
            if pygame.K_1 <= k <= pygame.K_9:
                self.buy(k - pygame.K_1)
            elif k == pygame.K_UP:
                self.shop_i = (self.shop_i - 1) % n_up
                self.sfx.play("tick")
            elif k == pygame.K_DOWN:
                self.shop_i = (self.shop_i + 1) % n_up
                self.sfx.play("tick")
            elif k == pygame.K_e:
                self.buy(self.shop_i)
            elif k in (pygame.K_RETURN, pygame.K_SPACE):
                self.sfx.play("start")
                self.start_level(self.level_no + 1)
                self.set_state("play")
        elif self.state in ("gameover", "win"):
            if k in (pygame.K_RETURN, pygame.K_SPACE):
                self.sfx.play("back")
                self.set_state("title")

    def price(self, i):
        uid, name, base, desc, mx = C["upgrades"][i]
        return int(base * (1 + 0.6 * self.up[uid]))

    def buy(self, i):
        if not 0 <= i < len(C["upgrades"]):
            return
        uid, name, base, desc, mx = C["upgrades"][i]
        if self.up[uid] >= mx or self.cash < self.price(i):
            self.sfx.play("deny")
            return
        self.cash -= self.price(i)
        self.up[uid] += 1
        if uid == "life":
            self.lives += 1
        self.sfx.play("buy")

    def interact(self):
        p, lv = self.player, self.level
        ex, ey = lv.exit[0] + .5, lv.exit[1] + .5
        if math.hypot(p.x - ex, p.y - ey) < 1.6:
            if self.has_key:
                self.sfx.play("door")
                self.finish_level()
            else:
                self.sfx.play("deny")
                self.say("The vault door is locked. Find the KEYCARD.", 3)
        else:
            self.sfx.play("blip")
            self.say("Nothing to use here - the vault door is marked on the map.", 2)

    def finish_level(self):
        left = max(0.0, self.time_left)
        tb = int(left * C["time_bonus_per_second"])
        sb = C["stealth_bonus"] if self.spotted == 0 else 0
        fb = C["full_loot_bonus"] if self.loot_left == 0 else 0
        bonus = tb + sb + fb
        self.cash += bonus
        self.score += bonus
        self.summary = [("Time bonus", tb), ("Ghost bonus (never spotted)", sb), ("Full loot bonus", fb)]
        if self.score > self.hi:
            self.hi = self.score
            self._save_hi()
        self.last_frame = pygame.transform.smoothscale(self.screen, self.screen.get_size()).copy()
        self.sfx.play("win" if self.level_no >= C["levels_to_win"] else "door")
        self.set_state("win" if self.level_no >= C["levels_to_win"] else "shop")

    # ------------------------------------------------------------ update
    def update(self, dt):
        self.t += dt
        if self.flash > 0:
            self.flash = max(0, self.flash - dt * 1.5)
        if self.state == "title":
            self.player.angle += dt * 0.25
            return
        if self.state != "play":
            return
        p, lv = self.player, self.level
        keys = pygame.key.get_pressed()
        p.angle += self.mouse_dx * C["mouse_sensitivity"]
        p.pitch -= self.mouse_dy * C["mouse_sensitivity"] * 1.2
        self.mouse_dx = self.mouse_dy = 0.0
        gp = C["gamepad"]
        turn = (keys[pygame.K_RIGHT] or keys[pygame.K_KP9]) - (keys[pygame.K_LEFT] or keys[pygame.K_KP7])
        p.angle += turn * C["turn_speed"] * dt
        # X: turn left / right          Y: look up / down          Z: jump / crouch (below)
        p.angle += self.stick("look_x") * gp["look_speed"] * dt
        tilt = (keys[pygame.K_PAGEUP] or keys[pygame.K_KP3]) - (keys[pygame.K_PAGEDOWN] or keys[pygame.K_KP_DIVIDE])
        p.pitch += (-self.stick("look_y") * 0.9 + tilt * 0.7) * dt * gp["look_speed"] / 2.8
        p.pitch = max(-1.0, min(1.0, p.pitch))
        fwd = float((keys[pygame.K_w] or keys[pygame.K_UP] or keys[pygame.K_KP8]) -
                    (keys[pygame.K_s] or keys[pygame.K_DOWN] or keys[pygame.K_KP5] or keys[pygame.K_KP2]))
        strafe = float((keys[pygame.K_d] or keys[pygame.K_KP6]) - (keys[pygame.K_a] or keys[pygame.K_KP4]))
        fwd += -self.stick("move_y")
        strafe += self.stick("move_x")
        if self.pad and self.pad.get_numhats():
            hx, hy = self.pad.get_hat(0)
            fwd += hy
            strafe += hx
        fwd, strafe = max(-1.0, min(1.0, fwd)), max(-1.0, min(1.0, strafe))
        p.moving = bool(fwd or strafe)
        was_sneak, was_sprint = p.sneaking, p.sprinting
        p.sneaking = bool(keys[pygame.K_LCTRL] or keys[pygame.K_c] or keys[pygame.K_KP_PERIOD] or
                          self.held("sneak"))
        sprint_key = bool(keys[pygame.K_LSHIFT] or keys[pygame.K_KP0] or self.held("sprint"))
        want_sprint = sprint_key and p.moving and p.stamina > 1 and not p.sneaking
        p.sprinting = want_sprint
        if p.sneaking and not was_sneak and not self.held("sneak"):
            self.sfx.play("sneak")                 # (pad presses already played it)
        if p.sprinting and not was_sprint and not self.held("sprint"):
            self.sfx.play("whoosh")
        if was_sprint and p.stamina <= 1:
            self.sfx.play("pant")
            self.say("Out of breath!", 1.5)
        # Z axis: jumping and crouching
        if p.vz or p.z > 0:
            p.vz -= C["gravity"] * dt
            p.z += p.vz * dt
            if p.z <= 0:
                p.z, p.vz = 0.0, 0.0
                self.sfx.play("land")
        p.crouch += ((C["crouch_depth"] if p.sneaking else 0.0) - p.crouch) * min(1.0, dt * 10)
        if p.sprinting:
            p.stamina = max(0, p.stamina - C["stamina_drain"] * dt)
        else:
            p.stamina = min(C["stamina_max"], p.stamina + C["stamina_regen"] * dt)
        if p.moving:
            dx = math.cos(p.angle) * fwd - math.sin(p.angle) * strafe
            dy = math.sin(p.angle) * fwd + math.cos(p.angle) * strafe
            n = math.hypot(dx, dy)
            sp = self.player_speed() * dt * min(1.0, n) / n   # analog sticks: partial tilt = slower
            nx, ny = p.x + dx * sp, p.y + dy * sp
            if self.free(nx, p.y):
                p.x = nx
            if self.free(p.x, ny):
                p.y = ny
            p.step_acc += self.player_speed() * dt
            p.bob += dt * (11 if p.sprinting else 7 if not p.sneaking else 5)
            if p.step_acc > (1.0 if p.sprinting else 0.8):
                p.step_acc = 0
                if not p.sneaking:
                    self.sfx.play("step")
        # vertical head movement: eased in/out so it never pops
        zt = (0.030 if p.sprinting else 0.011 if p.sneaking else 0.020) if p.moving else 0.0
        p.zamp += (zt - p.zamp) * min(1.0, dt * 9)
        p.breath += dt
        # explored map
        cx, cy = int(p.x), int(p.y)
        lv.explored[max(cy - 3, 0):cy + 4, max(cx - 3, 0):cx + 4] = True

        # timer & alarm
        self.time_left -= dt
        sec = int(self.time_left)
        if 0 <= sec < 10 and sec != self.low_tick and not self.alarm:
            self.sfx.play("tick")
        self.low_tick = sec
        if self.time_left <= 0 and not self.alarm:
            self.alarm = True
            self.say("!!! ALARM !!!  Guards know where you are. RUN!", 5)
            self.sfx.play("alarm", -1)

        # pickups
        for it in list(self.items):
            if math.hypot(p.x - it["x"], p.y - it["y"]) < 0.55:
                self.items.remove(it)
                k = it["kind"]
                if k == "key":
                    self.has_key = True
                    self.sfx.play("key")
                    self.say("KEYCARD acquired. Head for the VAULT DOOR (press E).", 4)
                    self.popup("KEYCARD", (255, 90, 90))
                else:
                    v = int(C["loot_values"][k] * self.diff["loot"])
                    self.cash += v
                    self.score += v
                    self.loot_left -= 1
                    self.sfx.play(k)
                    self.popup(f"+${v}")
        for g in lv.guards:
            self.update_guard(g, dt)
        for pu in self.popups:
            pu[1] -= dt
        self.popups = [pu for pu in self.popups if pu[1] > 0]
        if self.msg[1] > 0:
            self.msg = (self.msg[0], self.msg[1] - dt)

    def update_guard(self, g, dt):
        p, lv = self.player, self.level
        if g.stun > 0:
            g.stun -= dt
            return
        dx, dy = p.x - g.x, p.y - g.y
        dist = math.hypot(dx, dy)
        vis = C["guard_vision"] * self.diff["vision"] * (1 - 0.12 * self.up["soles"])
        vis *= 0.45 if p.sneaking else 1.5 if p.sprinting else 1.0
        vis *= 1.25 if p.torch else 1.0
        sees = False
        if dist < vis:
            da = abs((math.atan2(dy, dx) - g.face + math.pi) % math.tau - math.pi)
            sees = (da < 1.0 or dist < 2.5) and self.los(g.x, g.y, p.x, p.y)
        noise = 4.5 if p.sprinting else 0.5 if p.sneaking else 1.6
        heard = p.moving and dist < noise
        aware = sees or heard or self.alarm
        boost = C["alarm_speed_boost"] if self.alarm else 1.0
        if aware:
            if g.state != "chase":
                g.state = "chase"
                g.repath = 0
                if dist < 12:
                    self.spotted += 1
                    self.sfx.play("spot")
                    self.popup("SPOTTED!", (255, 70, 70))
            g.lost = 0
        elif g.state == "chase":
            g.lost += dt
            if g.lost > 4.0:
                g.state = "patrol"
                g.path = []
                self.sfx.play("lost")
                self.popup("You lost him", (150, 220, 255))
        gcell = (int(g.x), int(g.y))
        pcell = (int(p.x), int(p.y))
        if g.state == "chase":
            g.repath -= dt
            if g.repath <= 0:
                g.repath = 0.3
                g.path = bfs_path(lv.walk, gcell, pcell)
            speed = C["guard_chase_speed"] * self.diff["gspeed"] * boost
        else:
            if not g.path:
                for _ in range(6):
                    cx, cy = gcell[0] + self.rng.randint(-10, 10), gcell[1] + self.rng.randint(-10, 10)
                    if 0 < cx < lv.gw - 1 and 0 < cy < lv.gh - 1 and lv.walk[cy][cx]:
                        g.path = bfs_path(lv.walk, gcell, (cx, cy))
                        if g.path:
                            break
            speed = C["guard_patrol_speed"] * self.diff["gspeed"]
        if g.path:
            tx, ty = g.path[0][0] + .5, g.path[0][1] + .5
        elif g.state == "chase":
            tx, ty = p.x, p.y
        else:
            return
        ddx, ddy = tx - g.x, ty - g.y
        d = math.hypot(ddx, ddy)
        step = speed * dt
        if d > 1e-4:
            g.face = math.atan2(ddy, ddx)
        if d <= step:
            g.x, g.y = tx, ty
            if g.path:
                g.path.pop(0)
        else:
            g.x += ddx / d * step
            g.y += ddy / d * step
        if math.hypot(p.x - g.x, p.y - g.y) < 0.6:
            self.caught()

    def caught(self):
        p, lv = self.player, self.level
        self.sfx.play("caught")
        self.flash = 1.0
        loss = int(self.cash * C["caught_cash_penalty"])
        self.cash -= loss
        self.lives -= 1
        self.popup(f"CAUGHT!  -${loss}", (255, 70, 70))
        if self.lives <= 0:
            if self.score > self.hi:
                self.hi = self.score
                self._save_hi()
            self.sfx.play("lose")
            self.set_state("gameover")
            return
        p.x = p.y = 1.5
        for g in lv.guards:
            g.state = "patrol"
            g.path = []
            g.lost = 0
            g.stun = 3.0
        self.say(f"Caught! Lives left: {self.lives}. Guards are stunned for a moment.", 4)

    # ------------------------------------------------------------ drawing
    def draw_world(self, boost=0.0):
        p, lv = self.player, self.level
        sprites = []
        for it in self.items:
            bob = 0.03 * math.sin(self.t * 3 + it["phase"]) if it["kind"] in ("coin", "gem", "key") else 0
            sprites.append(dict(x=it["x"], y=it["y"], name=it["kind"], bob=bob))
        lamps = [(l[0], l[1], l[2] * (0.88 + 0.12 * math.sin(self.t * 17 + l[4]) if l[3] else 1.0))
                 for l in lv.lamps]
        for g in lv.guards:
            sprites.append(dict(x=g.x, y=g.y, name="guard_alert" if g.state == "chase" else "guard"))
            if C["guard_torch"]:
                lamps.append((g.x + math.cos(g.face) * 0.9, g.y + math.sin(g.face) * 0.9, 1.0))
        lamps.sort(key=lambda l: (l[0] - p.x) ** 2 + (l[1] - p.y) ** 2)
        lamps = [l for l in lamps[:7] if (l[0] - p.x) ** 2 + (l[1] - p.y) ** 2 < 100]
        tint = (1, 1, 1)
        if self.alarm:
            k = 0.5 + 0.5 * math.sin(self.t * 8)
            tint = (1.0, 0.45 + 0.4 * (1 - k), 0.45 + 0.4 * (1 - k))
        bob, zeye = 0.0, 0.5
        if C["head_bob"]:
            zk = C["head_bob_z"]
            zeye += zk * (p.zamp * math.sin(2 * p.bob) + 0.004 * math.sin(p.breath * 1.7))
            bob = math.sin(p.bob) * self.rh * 0.25 * p.zamp * zk     # slight pitch sway
        torch_k = C["torch_strength"] * (1 + 0.15 * self.up.get("torch", 0)) if hasattr(self, "up") else 1.7
        bob += getattr(p, "pitch", 0.0) * self.rh * C["pitch_limit"]
        zeye = max(0.08, min(0.95, zeye + getattr(p, "z", 0.0) - getattr(p, "crouch", 0.0)))
        surf = self.renderer.render(p.x, p.y, p.angle, bob, lv, sprites, lamps, p.torch, torch_k, tint, boost, zeye)
        size = self.screen.get_size()
        scaled = pygame.transform.smoothscale(surf, size) if C["smooth_scaling"] else pygame.transform.scale(surf, size)
        self.screen.blit(scaled, (0, 0))

    def text(self, s, font, color, pos, anchor="topleft", shadow=True):
        img = font.render(s, True, color)
        r = img.get_rect(**{anchor: pos})
        if shadow:
            sh = font.render(s, True, (0, 0, 0))
            self.screen.blit(sh, r.move(2, 2))
        self.screen.blit(img, r)
        return r

    def overlay(self, alpha=170, color=(0, 0, 0)):
        s = pygame.Surface(self.screen.get_size(), pygame.SRCALPHA)
        s.fill((*color, alpha))
        self.screen.blit(s, (0, 0))

    def draw_minimap(self):
        if self.map_mode == 0:
            return
        lv, p = self.level, self.player
        arr = np.zeros((lv.gh, lv.gw, 3), np.uint8)
        arr[lv.grid > 0] = (70, 75, 95)
        arr[lv.grid == 0] = (150, 155, 170)
        ex, ey = lv.exit
        arr[ey, ex] = (60, 230, 100) if self.has_key else (230, 70, 60)
        arr[~lv.explored] = (0, 0, 0)
        arr[ey, ex] = (60, 230, 100) if self.has_key else (230, 70, 60)
        surf = pygame.surfarray.make_surface(arr.swapaxes(0, 1))
        c = 6 if self.map_mode == 1 else 14
        surf = pygame.transform.scale(surf, (lv.gw * c, lv.gh * c))
        surf.set_alpha(215)
        pos = (self.screen.get_width() - surf.get_width() - 14, 14) if self.map_mode == 1 else \
            ((self.screen.get_width() - surf.get_width()) // 2, (self.screen.get_height() - surf.get_height()) // 2)
        self.screen.blit(surf, pos)
        pygame.draw.rect(self.screen, (200, 200, 220), (*pos, *surf.get_size()), 1)
        px_, py_ = pos[0] + p.x * c, pos[1] + p.y * c
        pygame.draw.circle(self.screen, (80, 200, 255), (int(px_), int(py_)), max(3, c // 2))
        pygame.draw.line(self.screen, (255, 255, 255), (px_, py_),
                         (px_ + math.cos(p.angle) * c * 1.5, py_ + math.sin(p.angle) * c * 1.5), 2)
        for g in lv.guards:
            if math.hypot(g.x - p.x, g.y - p.y) < 6:
                pygame.draw.circle(self.screen, (255, 60, 60), (int(pos[0] + g.x * c), int(pos[1] + g.y * c)),
                                   max(3, c // 2))

    def draw_hud(self):
        sw, sh = self.screen.get_size()
        p = self.player
        self.text(f"CASH  ${self.cash:,}", self.f_med, (120, 255, 150), (24, 18))
        self.text(f"SCORE {self.score:,}", self.f_sm, (255, 230, 140), (24, 58))
        self.text(f"LEVEL {self.level_no}/{C['levels_to_win']}   LOOT LEFT {self.loot_left}",
                  self.f_sm, (200, 210, 230), (24, 84))
        tl = max(0, self.time_left)
        col = (255, 70, 70) if tl < 30 or self.alarm else (240, 240, 240)
        label = "ALARM" if self.alarm else f"{int(tl) // 60}:{int(tl) % 60:02d}"
        self.text(label, self.f_med, col, (sw // 2, 18), "midtop")
        for i in range(self.lives):
            pygame.draw.circle(self.screen, (230, 50, 70), (sw // 2 - (self.lives - 1) * 14 + i * 28, 66), 9)
        # stamina
        pygame.draw.rect(self.screen, (0, 0, 0), (24, sh - 46, 204, 18))
        w = int(200 * p.stamina / C["stamina_max"])
        pygame.draw.rect(self.screen, (90, 200, 255) if p.stamina > 25 else (255, 150, 60), (26, sh - 44, w, 14))
        self.text("STAMINA", self.f_sm, (220, 220, 220), (24, sh - 72))
        # objective
        obj = "Reach the VAULT DOOR and press E" if self.has_key else "Find the KEYCARD"
        self.text(obj, self.f_sm, (255, 255, 255), (sw // 2, sh - 40), "midbottom")
        mode = "SNEAK" if p.sneaking else "SPRINT" if p.sprinting else ""
        if mode:
            self.text(mode, self.f_sm, (255, 255, 160), (sw // 2, sh // 2 + 40), "midtop")
        chase = any(g.state == "chase" for g in self.level.guards)
        if chase:
            self.text("! GUARD ON YOUR TAIL !", self.f_med, (255, 60, 60), (sw // 2, 100), "midtop")
        ex, ey = self.level.exit[0] + .5, self.level.exit[1] + .5
        if math.hypot(p.x - ex, p.y - ey) < 1.6:
            self.text("[E]  open vault door", self.f_med, (255, 255, 255), (sw // 2, sh // 2 + 90), "midtop")
        if self.msg[1] > 0:
            self.text(self.msg[0], self.f_sm, (255, 240, 200), (sw // 2, sh - 110), "midbottom")
        for i, (s, t, col) in enumerate(self.popups):
            self.text(s, self.f_med, col, (sw // 2, sh // 2 - 60 - int((1.6 - t) * 40)), "midtop")
        # crosshair
        pygame.draw.circle(self.screen, (255, 255, 255), (sw // 2, sh // 2), 2)
        if self.flash > 0:
            self.overlay(int(160 * self.flash), (200, 0, 0))
        self.draw_minimap()

    def draw_help(self):
        self.overlay(215)
        lines = ["CONTROLS", "",
                 "KEYBOARD  W A S D / arrows move, mouse or arrows turn",
                 "KEYPAD (NumLock on)  8/5 move  4/6 strafe  7/9 turn  0 sprint  . sneak  + torch  - map  Enter use",
                 "PAD  left stick move / menus, right stick look (left-right AND up-down)",
                 "     A use  B torch  X sneak  Y map  LB sprint  RB jump  Back level view  Start pause",
                 "ARDUINO  L-click: tap torch, 2x map, hold sprint   R-click: tap door/jump, 2x level view, hold sneak",
                 "         both clicks together = pause      (F9 re-centre sticks)",
                 "SPACE jump  SHIFT sprint  CTRL/C sneak+crouch  F torch  E door  PgUp/PgDn look up/down  HOME level",
                 "TAB minimap small / big / off      ESC or P pause      F11 fullscreen   F12 screenshot",
                 "F1 ... close this help"]
        y = 130
        for i, l in enumerate(lines):
            self.text(l, self.f_med if i == 0 else self.f_sm, (240, 240, 250), (self.screen.get_width() // 2, y), "midtop")
            y += 46 if i == 0 else 34

    def draw(self):
        sw, sh = self.screen.get_size()
        if self.state == "title":
            self.draw_world(boost=0.10)
            self.overlay(90)
            self.text("VAULT RUNNER", self.f_big, (255, 220, 120), (sw // 2, sh // 5), "midtop")
            self.text("a first-person stealth heist", self.f_med, (230, 230, 240), (sw // 2, sh // 5 + 84), "midtop")
            d = self.diff_names[self.diff_i]
            self.text(f"<  Difficulty: {d}  >", self.f_med, (255, 255, 255), (sw // 2, sh * 0.58), "midtop")
            self.text("ENTER - start heist        F1 - controls        ESC - quit", self.f_sm, (200, 210, 230),
                      (sw // 2, sh * 0.58 + 60), "midtop")
            self.text(f"Best score: {self.hi:,}", self.f_sm, (255, 230, 140), (sw // 2, sh * 0.58 + 100), "midtop")
            pads = []
            if self.pad:
                pads.append(f"Gamepad: {self.pad.get_name()}")
            if self.spad:
                pads.append(f"Arduino: {self.spad.status}")
            self.text("   |   ".join(pads) or "No gamepad detected", self.f_sm, (150, 200, 255),
                      (sw // 2, sh - 40), "midtop")
        elif self.state in ("play", "pause"):
            self.draw_world()
            self.draw_hud()
            if self.state == "pause":
                self.overlay(160)
                self.text("PAUSED", self.f_big, (255, 255, 255), (sw // 2, sh // 3), "midtop")
                self.text("ESC / P resume        Q quit to title        F1 controls", self.f_sm, (220, 220, 230),
                          (sw // 2, sh // 3 + 100), "midtop")
        elif self.state == "shop":
            self.screen.fill((10, 12, 20))
            self.text(f"LEVEL {self.level_no} COMPLETE", self.f_big, (120, 255, 150), (sw // 2, 40), "midtop")
            y = 140
            for name, v in self.summary:
                self.text(f"{name:<34} +${v:,}", self.f_sm, (230, 230, 240), (sw // 2, y), "midtop")
                y += 30
            self.text(f"CASH ${self.cash:,}      SCORE {self.score:,}", self.f_med, (255, 230, 140), (sw // 2, y + 10), "midtop")
            y += 80
            self.text("BLACK MARKET  (press number to buy)", self.f_med, (255, 255, 255), (sw // 2, y), "midtop")
            y += 50
            for i, (uid, name, base, desc, mx) in enumerate(C["upgrades"]):
                lvl = self.up[uid]
                cost = "MAX" if lvl >= mx else f"${self.price(i):,}"
                col = (150, 255, 170) if lvl < mx and self.cash >= self.price(i) else (140, 140, 150)
                cur = ">" if i == self.shop_i else " "
                self.text(f"{cur}[{i + 1}] {name:<15} {desc:<26} lvl {lvl}/{mx}   {cost}", self.f_sm, col, (sw // 2, y), "midtop")
                y += 34
            self.text("ENTER / Start - next heist      UP/DOWN + E / A - buy", self.f_med, (255, 255, 255), (sw // 2, sh - 70), "midtop")
        elif self.state in ("gameover", "win"):
            self.screen.fill((14, 6, 8) if self.state == "gameover" else (6, 16, 10))
            t = "BUSTED" if self.state == "gameover" else "PERFECT GETAWAY"
            self.text(t, self.f_big, (255, 90, 90) if self.state == "gameover" else (120, 255, 150), (sw // 2, sh // 4), "midtop")
            self.text(f"Final score: {self.score:,}", self.f_med, (255, 230, 140), (sw // 2, sh // 2), "midtop")
            self.text(f"Best score:  {self.hi:,}", self.f_sm, (230, 230, 240), (sw // 2, sh // 2 + 50), "midtop")
            self.text("ENTER - back to title", self.f_sm, (200, 200, 210), (sw // 2, sh // 2 + 100), "midtop")
        if self.show_help:
            self.draw_help()

    # ------------------------------------------------------------ main loop
    def run(self):
        while True:
            dt = min(self.clock.tick(60) / 1000.0, 0.05)
            for e in pygame.event.get():
                self.handle_event(e)
            self.poll_serial()
            self.update(dt)
            self.draw()
            pygame.display.flip()


def joytest():
    """Print live axis / button numbers (USB gamepads AND the Arduino serial pad)."""
    pygame.init()
    pygame.joystick.init()
    pads = [pygame.joystick.Joystick(i) for i in range(pygame.joystick.get_count())]
    for p in pads:
        print(f"USB pad: {p.get_name()}  axes={p.get_numaxes()} buttons={p.get_numbuttons()} hats={p.get_numhats()}")
    if not pads:
        print("No USB gamepad (normal for an Arduino UNO - it talks over a COM port instead).")
    sp = SerialPad(C["arduino"]) if C["arduino"]["enabled"] else None
    print("Leave the sticks centred for 2 seconds while the Arduino is found. Ctrl+C to quit.\n")
    clock = pygame.time.Clock()
    last, last_status = None, None
    names = ("move_x", "move_y", "look_x", "look_y")
    try:
        while True:
            pygame.event.pump()
            if sp and sp.status != last_status:
                print("Arduino:", sp.status)
                last_status = sp.status
            cur = []
            if pads:
                p = pads[0]
                cur.append("USB axes %s pressed %s hats %s" % (
                    [round(p.get_axis(i), 1) for i in range(p.get_numaxes())],
                    [i for i in range(p.get_numbuttons()) if p.get_button(i)],
                    [p.get_hat(i) for i in range(p.get_numhats())]))
            if sp and sp.ready:
                ax = C["arduino"]["axes"] if sp.n_axes == 4 else {"move_x": 0, "move_y": 1}
                cur.append(f"ARDUINO ({sp.n_axes // 2} stick) " +
                           "  ".join(f"{n}={sp.axis(ax[n]):+.1f}" for n in names if n in ax) +
                           "  buttons %s" % [i for i in range(sp.num_buttons()) if sp.button(i)] +
                           f"   raw: {sp.last_line}")
            line = " | ".join(cur)
            if line and line != last:
                print(line)
                last = line
            clock.tick(20)
    except KeyboardInterrupt:
        pass


def main():
    if "--joytest" in sys.argv:
        joytest()
        return
    Game().run()


if __name__ == "__main__":
    main()
