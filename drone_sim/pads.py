"""Reads the two Arduino pads (HC-05 / HC-06 Bluetooth OR USB cable) for DRONE SIM.

Each pad prints lines like   J,<lx>,<ly>,<rx>,<ry>,<lclick>,<rclick>   (see arduino/drone_pad).
Bluetooth: once an HC-05 is paired, Windows makes two "Standard Serial over Bluetooth link" COM
ports - only the OUTGOING one carries data. We simply open every port in its own thread and keep
the ones that talk. Pads are assigned by config (COM port or Bluetooth address) or first come.

Pad 1 flies the drone (left stick = throttle + yaw, right stick = pitch + roll). Pad 2 is the
optional co-pilot: its clicks work the camera, stabilize and pause. The launcher streams both
to the game over UDP; drone_sim.py also reads a single cabled pad directly without the launcher.
"""
import re
import threading
import time

NUM = re.compile(r"(?<![A-Za-z0-9_.])-?\d+(?:\.\d+)?")

STRICT = re.compile(r"^J,(\d{1,4}),(\d{1,4}),(\d{1,4}),(\d{1,4}),([01]),([01])(?:,(\d{1,3}))?$")


def parse_pad_line(line):
    """Strict parse of 'J,lx,ly,rx,ry,lc,rc[,sum]'. Bluetooth drops / merges bytes now and then;
    a damaged line must be thrown away, not read as a wild stick position. With the checksum
    (sum of the 6 values % 256, sent by the current sketch) damage is caught reliably."""
    m = STRICT.match(line.strip())
    if not m:
        return None
    v = [int(x) for x in m.groups()[:6]]
    if any(a > 1023 for a in v[:4]):
        return None
    if m.group(7) is not None and int(m.group(7)) != sum(v) % 256:
        return None
    return [float(x) for x in v]


class PortReader:
    """Background reader for one COM port. Calibrates the stick centres from the first samples."""

    def __init__(self, dev, desc, hwid, baud):
        self.dev, self.desc, self.hwid, self.baud = dev, desc, hwid, baud
        self.lock = threading.Lock()
        self.status = "opening..."
        self.last_ok = 0.0
        self.lines = 0
        self.bad = 0
        self.vals = None
        self.center = None
        self.idle = None
        self.calib = []
        self.full = 1023.0
        self.stop = False
        self.dead = False
        self.raw = ""
        threading.Thread(target=self._run, daemon=True).start()

    @property
    def bluetooth(self):
        return "bluetooth" in (self.desc or "").lower() or "BTHENUM" in (self.hwid or "").upper()

    @property
    def live(self):
        return time.time() - self.last_ok < 1.0 and self.center is not None

    def feed(self, line):
        line = line.strip()
        if line.startswith("J"):
            nums = parse_pad_line(line)       # our sketch: strict, checksummed
            if nums is None:
                self.bad += 1
                return False
        else:
            nums = [float(n) for n in NUM.findall(line)]   # other pads (generic numbers)
            if len(nums) < 3:
                return False
        with self.lock:
            self.raw = line.strip()
            if self.center is None or len(nums) != len(self.center) + len(self.idle):
                self.calib.append(nums)
                self.calib = [c for c in self.calib if len(c) == len(nums)][-30:]
                if len(self.calib) >= 10:
                    cols = list(zip(*self.calib))
                    na = 2 if len(nums) == 3 else 4
                    self.center = [sorted(c)[len(c) // 2] for c in cols[:na]]
                    self.idle = [max(set(c), key=c.count) for c in cols[na:]]
                    top = max(max(c) for c in cols[:na])
                    self.full = 1.0 if top <= 1.5 else 4095.0 if top > 1100 else 1023.0
                    self.calib = []
            else:
                self.vals = nums
            self.last_ok = time.time()
        return True

    def recalibrate(self):
        with self.lock:
            self.center = self.idle = self.vals = None
            self.calib = []

    def axis(self, i, deadzone):
        with self.lock:
            if self.vals is None or self.center is None or i >= len(self.center):
                return 0.0
            v, c = self.vals[i], self.center[i]
            lo = -1.0 if self.full == 1.0 else 0.0
            span = (self.full - c) if v >= c else (c - lo)
            a = (v - c) / span if span > 1e-6 else 0.0
        a = max(-1.0, min(1.0, a))
        return 0.0 if abs(a) < deadzone else (abs(a) - deadzone) / (1 - deadzone) * (1 if a > 0 else -1)

    def button(self, i):
        with self.lock:
            if self.vals is None or self.idle is None or i >= len(self.idle):
                return False
            return self.vals[len(self.center) + i] != self.idle[i]

    def _run(self):
        import serial
        while not self.stop:
            try:
                # Bluetooth SPP ignores the baud rate; USB uses it. Opening an outgoing BT port
                # makes Windows connect to the module - this can take a few seconds.
                self.status = "connecting..." if self.bluetooth else "opening..."
                s = serial.Serial(self.dev, self.baud, timeout=0.3, write_timeout=1)
            except Exception as e:
                self.status = f"can't open ({str(e)[:40]})"
                for _ in range(50):
                    if self.stop:
                        return
                    time.sleep(0.1)
                continue
            self.status = "open, waiting for data"
            buf = b""
            try:
                while not self.stop:
                    buf += s.read(max(1, s.in_waiting))
                    *lines, buf = buf.split(b"\n")
                    for ln in lines:
                        if self.feed(ln.decode("ascii", "ignore")):
                            self.lines += 1
                            self.status = "live" if self.center else "calibrating - leave the sticks centred"
                    if len(buf) > 4096:
                        buf = b""
            except Exception:
                self.status = "disconnected"
            finally:
                try:
                    s.close()
                except Exception:
                    pass
            time.sleep(1.0)
        self.dead = True


class SimPad:
    """Keyboard-driven fake pad for testing the launcher with no hardware."""
    dev = "SIM"
    desc = "simulated pad"
    bluetooth = False
    status = "simulated"
    raw = ""

    def __init__(self):
        self.state = [0.0, 0.0, 0.0, 0.0, False, False]

    @property
    def live(self):
        return True

    def axis(self, i, dz):
        return self.state[i]

    def button(self, i):
        return self.state[4 + i]

    def recalibrate(self):
        pass


class PadHub:
    """Finds pads on all COM ports and maps them to pilot 1 / co-pilot 2."""

    def __init__(self, cfg):
        self.cfg = cfg
        self.readers = {}
        self.assigned = [None, None]          # device names
        self.sim = [None, None]
        self.error = ""
        self.ports_info = []
        try:
            import serial  # noqa: F401
            from serial.tools import list_ports  # noqa: F401
        except ImportError:
            self.error = "pyserial missing:  pip install pyserial"
            return
        threading.Thread(target=self._scan_loop, daemon=True).start()

    def _scan_loop(self):
        from serial.tools import list_ports
        while True:
            try:
                ports = list_ports.comports()
            except Exception:
                ports = []
            self.ports_info = [(p.device, p.description or "", p.hwid or "") for p in ports]
            for p in ports:
                if p.device not in self.readers and self._worth_opening(p):
                    self.readers[p.device] = PortReader(p.device, p.description, p.hwid, self.cfg.get("baud", 115200))
            for dev in list(self.readers):
                if dev not in [p.device for p in ports]:
                    self.readers[dev].stop = True
                    del self.readers[dev]
            self._assign()
            time.sleep(2.0)

    def _worth_opening(self, p):
        """USB serial: always. Bluetooth: only "outgoing" ports (they carry the remote address;
        incoming ones read ...&000000000000_...), and only the pinned pads if p1/p2 are set,
        so we don't make Windows dial every phone / headset you ever paired."""
        hwid = (p.hwid or "").upper()
        if "BTHENUM" not in hwid and "bluetooth" not in (p.description or "").lower():
            return True
        m = re.search(r"&([0-9A-F]{12})_", hwid)
        if not m or m.group(1) == "000000000000":
            return False
        wants = [w for w in (self.cfg.get("p1", "auto"), self.cfg.get("p2", "auto")) if w and w != "auto"]
        if not wants:
            return True
        addr = m.group(1)
        return any(w.upper() == p.device.upper() or w.upper().replace(":", "") == addr for w in wants)

    def _match(self, reader, want):
        if not want or want == "auto":
            return False
        w = want.upper().replace(":", "").replace("-", "")
        return reader.dev.upper() == want.upper() or (len(w) >= 8 and w in (reader.hwid or "").upper().replace(":", ""))

    def _assign(self):
        live = [r for r in self.readers.values() if r.live]
        wants = [self.cfg.get("p1", "auto"), self.cfg.get("p2", "auto")]
        for i in range(2):
            cur = self.assigned[i]
            if cur and cur in self.readers and time.time() - self.readers[cur].last_ok < 5.0:
                continue
            self.assigned[i] = None
            for r in live:
                if self._match(r, wants[i]):
                    self.assigned[i] = r.dev
        for i in range(2):
            if self.assigned[i] is None and wants[i] in ("", "auto"):
                for r in live:
                    if r.dev not in self.assigned and not any(self._match(r, w) for w in wants):
                        self.assigned[i] = r.dev
                        break

    def swap(self):
        self.assigned.reverse()
        p1, p2 = self.cfg.get("p1", "auto"), self.cfg.get("p2", "auto")
        self.cfg["p1"], self.cfg["p2"] = p2, p1

    def pad(self, i):
        if self.sim[i]:
            return self.sim[i]
        dev = self.assigned[i]
        r = self.readers.get(dev) if dev else None
        return r if r is not None and r.live else None

    def vector(self, i):
        """[lx, ly, rx, ry, lclick, rclick, ok] with up / right positive."""
        p = self.pad(i)
        if p is None:
            return [0, 0, 0, 0, 0, 0, 0]
        dz = self.cfg.get("deadzone", 0.12)
        inv = self.cfg.get("invert", {})
        key = f"p{i + 1}"
        amap = self.cfg.get("map", {}).get(key)       # from the orientation wizard
        out = []
        for a, name in enumerate(["lx", "ly", "rx", "ry"]):
            if amap and name in amap and not isinstance(p, SimPad):
                src, sign = amap[name]
                v = p.axis(int(src), dz) * sign      # wizard already knows the real direction
            else:
                v = p.axis(a, dz)
                if name in ("ly", "ry"):
                    v = -v                  # analog sticks read LOW when pushed up
            if inv.get(f"{key}_{name}"):
                v = -v
            out.append(round(v, 3))
        out += [1 if self._click(i, 0, p, out[0], out[1]) else 0,
                1 if self._click(i, 1, p, out[2], out[3]) else 0, 1]
        return out

    def _click(self, i, b, p, sx, sy):
        """Filtered stick click. KY-023 sticks also press their switch when pushed hard to the
        edge, so a click only STARTS when its own stick is near the centre ("click_guard",
        0..1, set 1.5 to disable); once on, it stays on until released, even while moving the
        stick. Clicks must also be stable for 40 ms (debounce against bounce / BT noise)."""
        if not hasattr(self, "_bs"):
            self._bs = [[{"raw": False, "t": 0.0, "on": False} for _ in range(2)] for _ in range(2)]
        st = self._bs[i][b]
        raw = bool(p.button(b))
        now = time.time()
        if raw != st["raw"]:
            st["raw"], st["t"] = raw, now
        if now - st["t"] < 0.04:
            return st["on"]
        if not raw:
            st["on"] = False
        # left-only flying: the left click (descend) must work while the stick is pushed, so only
        # block it at the very edge, where the stick's own switch presses by accident
        guard = 0.95 if b == 0 and self.cfg.get("left_only", True) else self.cfg.get("click_guard", 0.55)
        centred = (sx * sx + sy * sy) ** 0.5 < guard
        if raw and not st["on"] and centred:
            st["on"] = True
        return st["on"]
