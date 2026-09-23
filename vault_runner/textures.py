"""Procedural textures and sprites for VAULT RUNNER (no image files needed)."""
import numpy as np
import pygame

T = 128  # texture size (power of two)


# ---------------------------------------------------------------- noise
def _noise(n, cells, rng):
    """Tileable value noise."""
    g = rng.random((cells, cells))
    xs = np.linspace(0, cells, n, endpoint=False)
    i0 = xs.astype(int)
    f = xs - i0
    f = f * f * (3 - 2 * f)
    i1 = (i0 + 1) % cells
    a, b = g[np.ix_(i0, i0)], g[np.ix_(i0, i1)]
    c, d = g[np.ix_(i1, i0)], g[np.ix_(i1, i1)]
    fx, fy = f[None, :], f[:, None]
    return (a * (1 - fx) + b * fx) * (1 - fy) + (c * (1 - fx) + d * fx) * fy


def fbm(n, rng, base=4, octaves=4):
    out, amp, tot = np.zeros((n, n)), 1.0, 0.0
    for o in range(octaves):
        out += amp * _noise(n, min(base * 2 ** o, n), rng)
        tot += amp
        amp *= 0.5
    return out / tot


def _rgb(*ch):
    return np.clip(np.stack(ch, -1), 0, 255).astype(np.float32)


# ---------------------------------------------------------------- walls
def _brick(rng, yy, xx):
    bh, bw = T // 8, T // 4
    row = yy // bh
    xo = (xx + (row % 2) * (bw // 2)) % T
    col = xo // bw
    tint = rng.random((8, 4))[row, col]
    n = fbm(T, rng, 8, 4)
    grain = rng.random((T, T))
    mortar = ((yy % bh) < 2) | ((xo % bw) < 2)
    shade = (0.75 + 0.5 * n) * (0.9 + 0.2 * grain)
    img = _rgb((140 + 60 * tint) * shade, (62 + 30 * tint) * shade, (48 + 22 * tint) * shade)
    hi = (((yy % bh) >= 2) & ((yy % bh) < 4))[..., None]
    img = np.where(hi, img * 1.2, img)
    m = _rgb((150 + 40 * n) * 0.8, (146 + 40 * n) * 0.8, (136 + 40 * n) * 0.8)
    return np.where(mortar[..., None], m, img)


def _concrete(rng, yy, xx):
    n = fbm(T, rng, 4, 5)
    grain = rng.random((T, T))
    g = 105 + 70 * (n - 0.5) + 20 * (grain - 0.5)
    stain = 0.75 + 0.5 * fbm(T, rng, 2, 3)
    g = g * stain
    seam = ((xx % 64) < 2) | ((yy % 64) < 2)
    g = np.where(seam, g * 0.55, g)
    for cx in (6, 58, 70, 122):
        for cy in (6, 58, 70, 122):
            g = np.where((xx - cx) ** 2 + (yy - cy) ** 2 < 6, g * 0.5, g)
    return _rgb(g, g * 1.0, g * 1.04)


def _marble(rng, yy, xx):
    n = fbm(T, rng, 4, 5)
    v = np.sin(xx / T * 2 * np.pi * 2 + yy / T * 2 * np.pi + 7 * n)
    vein = np.exp(-np.abs(v) * 7)
    base = 225 - 35 * fbm(T, rng, 8, 3)
    img = _rgb(base - vein * 110, base - vein * 105, base * 1.02 - vein * 95)
    seam = ((xx % 64) < 1) | ((yy % 64) < 1)
    return np.where(seam[..., None], img * 0.6, img)


def _metal(rng, yy, xx):
    streak = np.tile(rng.random((T, 1)), (1, T)) * 0.5 + rng.random((T, T)) * 0.5
    base = 95 + 40 * streak
    panel = ((xx % 64) < 2) | ((yy % 64) < 2)
    edge = ((xx % 64) == 2) | ((yy % 64) == 2)
    base = np.where(panel, base * 0.4, np.where(edge, base * 1.3, base))
    for cx in (10, 54, 74, 118):
        for cy in (10, 54, 74, 118):
            d2 = (xx - cx) ** 2 + (yy - cy) ** 2
            lit = 1.4 - 0.05 * ((xx - cx) + (yy - cy))
            base = np.where(d2 < 10, base * lit + 20, base)
    return _rgb(base * 0.85, base * 0.95, base * 1.1)


def _vault(rng, yy, xx, lamp):
    streak = np.tile(rng.random((T, 1)), (1, T)) * 0.4 + rng.random((T, T)) * 0.3
    base = 62 + 34 * streak
    cx = cy = T / 2
    d = np.hypot(xx - cx + 0.5, yy - cy + 0.5)
    ang = np.arctan2(yy - cy + 0.5, xx - cx + 0.5)
    ring = np.abs(d - 38) < 5
    hub = d < 12
    spokes = (d < 38) & (np.abs(np.sin(ang * 3)) < 0.1)
    gold = ring | hub | spokes
    hl = 0.8 + 0.5 * (1 - (xx + yy) / (2 * T))
    img = _rgb(base * 0.9, base * 0.95, base * 1.1)
    gcol = _rgb((200 * hl) * (0.85 + 0.3 * streak), (155 * hl) * (0.85 + 0.3 * streak), 55 * hl)
    img = np.where(gold[..., None], gcol, img)
    strip = (yy >= 8) & (yy < 15) & (xx > 36) & (xx < 92)
    img = np.where(strip[..., None], np.array(lamp, np.float32), img)
    haz = (yy > 108) & (yy < 122) & (((xx + yy) // 8) % 2 == 0)
    img = np.where(haz[..., None], np.array([220, 180, 20], np.float32), img)
    border = (xx < 3) | (xx > T - 4) | (yy < 3) | (yy > T - 4)
    return np.where(border[..., None], img * 0.4, img)


# ---------------------------------------------------------------- floors / ceiling
def _wood(rng, yy, xx):
    pw = 16
    row = yy // pw
    tint = rng.random(T // pw)[row]
    n = fbm(T, rng, 4, 4)
    grain = np.sin(xx / T * 2 * np.pi * 4 + 9 * n) * 0.5 + 0.5
    joint = ((xx + row * 37) % 64) < 1
    seam = (yy % pw) < 1
    k = (0.75 + 0.35 * tint) * (0.85 + 0.25 * grain)
    img = _rgb(128 * k, 82 * k, 48 * k)
    return np.where((joint | seam)[..., None], img * 0.35, img)


def _tile(rng, yy, xx):
    check = (((xx // 32) + (yy // 32)) % 2).astype(bool)
    n = fbm(T, rng, 4, 5)
    v = np.exp(-np.abs(np.sin(xx / T * 2 * np.pi * 3 + yy / T * 2 * np.pi * 2 + 6 * n)) * 8)
    base = np.where(check, 215, 48) - v * np.where(check, 70, -25)
    img = _rgb(base, base, base * 1.02)
    grout = ((xx % 32) < 1) | ((yy % 32) < 1)
    return np.where(grout[..., None], img * 0.55 + 20, img)


def _carpet(rng, yy, xx):
    fibre = rng.random((T, T))
    n = fbm(T, rng, 8, 3)
    pat = (((xx + yy) % 32) < 2) | (((xx - yy) % 32) < 2)
    k = (0.65 + 0.5 * fibre) * (0.85 + 0.3 * n)
    img = _rgb(100 * k, 22 * k, 30 * k)
    return np.where(pat[..., None], img + np.array([28, 22, 6], np.float32), img)


def _floor_concrete(rng, yy, xx):
    n = fbm(T, rng, 4, 5)
    g = 88 + 55 * (n - 0.5) + 16 * (rng.random((T, T)) - 0.5)
    g = np.where(((xx % 64) < 1) | ((yy % 64) < 1), g * 0.5, g)
    return _rgb(g, g, g * 1.05)


def _ceiling(rng, yy, xx):
    g = 170 + 25 * (rng.random((T, T)) - 0.5) + 25 * (fbm(T, rng, 8, 3) - 0.5)
    g = np.where(((xx % 64) < 2) | ((yy % 64) < 2), g * 0.4, g)
    return _rgb(g, g, g * 0.97)


def make_textures(seed=7):
    """Returns (walls, flats). walls[i]: 1 brick 2 concrete 3 marble 4 metal
    5 vault(locked) 6 vault(open). flats: 0 wood 1 tile 2 carpet 3 concrete 4 ceiling."""
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[0:T, 0:T]
    walls = [np.zeros((T, T, 3), np.float32),
             _brick(rng, yy, xx), _concrete(rng, yy, xx), _marble(rng, yy, xx),
             _metal(rng, yy, xx),
             _vault(rng, yy, xx, (255, 40, 30)), _vault(rng, yy, xx, (40, 255, 90))]
    flats = [_wood(rng, yy, xx), _tile(rng, yy, xx), _carpet(rng, yy, xx),
             _floor_concrete(rng, yy, xx), _ceiling(rng, yy, xx)]
    return np.stack(walls).astype(np.float32), np.stack(flats).astype(np.float32)


# ---------------------------------------------------------------- sprites
def _lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def _coin():
    s = pygame.Surface((64, 64), pygame.SRCALPHA)
    for i in range(27, 0, -1):
        t = 1 - i / 27
        pygame.draw.circle(s, _lerp((150, 100, 10), (255, 225, 110), t ** 1.5),
                           (32 - int(4 * t), 32 - int(4 * t)), i)
    pygame.draw.circle(s, (120, 80, 10), (32, 32), 27, 2)
    pygame.draw.circle(s, (255, 235, 140), (32, 32), 19, 2)
    pygame.draw.rect(s, (200, 140, 20), (30, 20, 4, 24))
    return s


def _bar_surface():
    s = pygame.Surface((64, 64), pygame.SRCALPHA)

    def bar(x, y, w=28, h=14):
        pygame.draw.polygon(s, (255, 226, 120), [(x + 5, y), (x + w + 5, y), (x + w, y + 5), (x, y + 5)])
        for i in range(h):
            pygame.draw.line(s, _lerp((235, 180, 40), (150, 100, 15), i / h), (x, y + 5 + i), (x + w - 1, y + 5 + i))
        pygame.draw.polygon(s, (180, 125, 20), [(x + w, y + 5), (x + w + 5, y), (x + w + 5, y + h - 1), (x + w, y + h + 4)])
        pygame.draw.rect(s, (255, 240, 170), (x + 6, y + 8, 12, 2))
    bar(6, 36)
    bar(30, 36)
    bar(18, 20)
    return s


def _gem():
    s = pygame.Surface((64, 64), pygame.SRCALPHA)
    P = lambda pts, c: pygame.draw.polygon(s, c, pts)
    P([(14, 24), (22, 12), (42, 12), (50, 24)], (170, 235, 255))
    P([(22, 12), (32, 24), (14, 24)], (120, 200, 245))
    P([(42, 12), (50, 24), (32, 24)], (100, 175, 235))
    P([(14, 24), (32, 24), (32, 56)], (60, 140, 225))
    P([(50, 24), (32, 24), (32, 56)], (35, 100, 200))
    P([(23, 24), (41, 24), (32, 56)], (110, 190, 255))
    P([(26, 13), (33, 13), (30, 20), (24, 20)], (240, 255, 255))
    pygame.draw.polygon(s, (20, 60, 120), [(14, 24), (22, 12), (42, 12), (50, 24), (32, 56)], 2)
    return s


def _key():
    s = pygame.Surface((64, 64), pygame.SRCALPHA)
    card = pygame.Surface((56, 36), pygame.SRCALPHA)
    pygame.draw.rect(card, (200, 30, 40), (0, 0, 56, 36), border_radius=5)
    pygame.draw.rect(card, (255, 90, 90), (0, 0, 56, 36), 2, border_radius=5)
    pygame.draw.rect(card, (15, 15, 20), (0, 8, 56, 7))
    pygame.draw.rect(card, (225, 195, 90), (6, 20, 14, 11), border_radius=2)
    pygame.draw.line(card, (150, 120, 40), (6, 25), (20, 25))
    pygame.draw.line(card, (150, 120, 40), (13, 20), (13, 31))
    pygame.draw.rect(card, (255, 255, 255), (30, 22, 20, 3))
    pygame.draw.rect(card, (255, 255, 255), (30, 28, 12, 3))
    card = pygame.transform.rotate(card, 22)
    s.blit(card, card.get_rect(center=(32, 32)))
    return s


def _guard(alert):
    s = pygame.Surface((64, 128), pygame.SRCALPHA)
    D = pygame.draw
    D.rect(s, (28, 32, 50), (22, 80, 9, 42))
    D.rect(s, (28, 32, 50), (33, 80, 9, 42))
    D.rect(s, (8, 8, 10), (20, 118, 12, 8), border_radius=2)
    D.rect(s, (8, 8, 10), (33, 118, 12, 8), border_radius=2)
    D.rect(s, (42, 58, 100), (17, 38, 30, 44), border_radius=4)
    D.rect(s, (25, 25, 30), (17, 74, 30, 5))
    D.rect(s, (200, 170, 60), (29, 74, 6, 5))
    D.rect(s, (36, 50, 90), (8, 40, 9, 38), border_radius=3)
    D.rect(s, (36, 50, 90), (47, 40, 9, 38), border_radius=3)
    D.circle(s, (215, 172, 140), (12, 80), 5)
    D.circle(s, (215, 172, 140), (52, 80), 5)
    D.rect(s, (255, 240, 170) if not alert else (255, 120, 90), (50, 80, 10, 5))
    D.circle(s, (225, 190, 70), (39, 48), 3)
    D.rect(s, (215, 172, 140), (28, 28, 8, 8))
    D.circle(s, (218, 176, 145), (32, 22), 11)
    D.ellipse(s, (25, 35, 75), (19, 6, 26, 14))
    D.rect(s, (20, 28, 62), (19, 14, 26, 5))
    D.rect(s, (255, 40, 30) if alert else (10, 10, 12), (23, 21, 18, 5))
    D.rect(s, (25, 30, 60), (28, 30, 8, 3))
    return s


def surf_to_arrays(surf):
    rgb = pygame.surfarray.array3d(surf).swapaxes(0, 1).astype(np.float32)
    alpha = pygame.surfarray.array_alpha(surf).swapaxes(0, 1) > 100
    return rgb, alpha


def make_sprites():
    surfs = {"coin": _coin(), "bar": _bar_surface(), "gem": _gem(), "key": _key(),
             "guard": _guard(False), "guard_alert": _guard(True)}
    return {k: surf_to_arrays(v) for k, v in surfs.items()}
