#!/usr/bin/env python3
"""
HYPER FLIGHT 3D - SKYBOUND NEXUS
A hyper-realistic 3D Jet Flight & Combat Simulator. Pygame + NumPy.

Fly a 6-DOF Jet Fighter across 3D mountain terrain, dogfight AI combat drones,
sprint through floating 3D ring gates, or practice stunt aerobatics in Free Flight.

Supports:
- Keyboard & Mouse
- Standard USB Gamepads
- Lab-Made Arduino UNO Dual Joystick Gamepad (Serial or USB HID)

Run:
  python hyper_flight_3d.py               (or double-click play.bat)
  python hyper_flight_3d.py --joytest     (or double-click gamepad_test.bat)
  python hyper_flight_3d.py --serial COM3
"""

import sys
import os
import math
import time
import json
import random
import argparse
import threading

import numpy as np
import pygame

try:
    import serial
    import serial.tools.list_ports
    HAS_SERIAL = True
except ImportError:
    HAS_SERIAL = False

HERE = os.path.dirname(os.path.abspath(__file__))
HIGHSCORE_FILE = os.path.join(HERE, "highscore.json")

# =====================================================================
#  CONFIG & HIGHSCORE SYSTEM
# =====================================================================
DEFAULT_CONFIG = {
    "window_size": (1280, 720),
    "fullscreen": False,
    "sound": True,
    "fov": 70.0,
    "draw_distance": 1800.0,
    "gamepad": {
        "deadzone": 0.12,
        "invert_pitch": True
    }
}

def load_highscores():
    if os.path.exists(HIGHSCORE_FILE):
        try:
            with open(HIGHSCORE_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {"TARGET ASSAULT": 0, "RING APEX RACE": 0, "FREE FLIGHT": 0}

def save_highscores(scores):
    try:
        with open(HIGHSCORE_FILE, "w") as f:
            json.dump(scores, f, indent=2)
    except Exception as e:
        print(f"[HighScore] Error saving: {e}")

# =====================================================================
#  SOUND SYNTHESIZER
# =====================================================================
class AudioSynth:
    def __init__(self, enabled=True):
        self.ok = False
        self.sounds = {}
        self.eng_ch = None
        if not enabled:
            return
        try:
            pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=1024)
            self.ok = True
            self._generate_sounds()
        except Exception as e:
            print(f"[Audio] Mixer init failed: {e}")

    def _generate_sounds(self):
        sr = 44100
        # 1. Laser sound
        dur = 0.12
        t = np.linspace(0, dur, int(sr * dur), False)
        freq = np.linspace(1100, 250, len(t))
        w = np.sin(2 * np.pi * freq * t) * np.exp(-t * 20)
        st = np.column_stack((w, w))
        self.sounds['laser'] = pygame.sndarray.make_sound((st * 32767 * 0.35).astype(np.int16))

        # 2. Missile Launch
        dur = 0.4
        t = np.linspace(0, dur, int(sr * dur), False)
        noise = np.random.uniform(-1, 1, len(t))
        swp = np.sin(2 * np.pi * np.linspace(200, 750, len(t)) * t)
        w = (noise * 0.5 + swp * 0.5) * np.exp(-t * 5)
        st = np.column_stack((w, w))
        self.sounds['missile'] = pygame.sndarray.make_sound((st * 32767 * 0.45).astype(np.int16))

        # 3. Explosion
        dur = 0.7
        t = np.linspace(0, dur, int(sr * dur), False)
        noise = np.random.uniform(-1, 1, len(t))
        boom = np.sin(2 * np.pi * 55 * t) * np.exp(-t * 4)
        w = (noise * 0.4 + boom * 0.6)
        st = np.column_stack((w, w))
        self.sounds['explosion'] = pygame.sndarray.make_sound((st * 32767 * 0.6).astype(np.int16))

        # 4. Ring Chime
        dur = 0.25
        t = np.linspace(0, dur, int(sr * dur), False)
        w = (np.sin(2 * np.pi * 880 * t) * 0.6 + np.sin(2 * np.pi * 1760 * t) * 0.4) * np.exp(-t * 12)
        st = np.column_stack((w, w))
        self.sounds['ring'] = pygame.sndarray.make_sound((st * 32767 * 0.5).astype(np.int16))

        # 5. Continuous Jet Engine
        dur = 1.0
        t = np.linspace(0, dur, int(sr * dur), False)
        noise = np.random.uniform(-1, 1, len(t))
        rumble = np.sin(2 * np.pi * 65 * t) * 0.3
        w = noise * 0.35 + rumble
        st = np.column_stack((w, w))
        self.sounds['engine'] = pygame.sndarray.make_sound((st * 32767 * 0.3).astype(np.int16))

    def play(self, name, volume=1.0):
        if self.ok and name in self.sounds:
            s = self.sounds[name]
            s.set_volume(volume)
            s.play()

    def start_engine(self):
        if self.ok and 'engine' in self.sounds and (self.eng_ch is None or not self.eng_ch.get_busy()):
            self.eng_ch = self.sounds['engine'].play(loops=-1)

    def update_engine(self, throttle, boost):
        if self.eng_ch and self.ok:
            v = 0.15 + throttle * 0.45 + (0.3 if boost else 0.0)
            self.eng_ch.set_volume(min(1.0, max(0.1, v)))

    def stop_engine(self):
        if self.eng_ch:
            self.eng_ch.stop()

# =====================================================================
#  INPUT CONTROLLER (ARDUINO SERIAL + USB GAMEPAD + KEYBOARD)
# =====================================================================
class InputController:
    def __init__(self, serial_port=None):
        self.roll = 0.0
        self.pitch = 0.0
        self.yaw = 0.0
        self.throttle = 0.5

        self.btn_fire = False
        self.btn_missile = False
        self.btn_boost = False
        self.btn_cam = False

        self.source_type = "Keyboard/Mouse"
        self.arduino_connected = False
        self.raw_lx = 512; self.raw_ly = 512
        self.raw_rx = 512; self.raw_ry = 512
        self.raw_sw1 = 0; self.raw_sw2 = 0
        self.raw_b1 = 0; self.raw_b2 = 0; self.raw_b3 = 0

        self.deadzone = 0.10
        self.center_lx = 512; self.center_ly = 512
        self.center_rx = 512; self.center_ry = 512

        self.running = True
        self.usb_joy = None
        self._init_usb_joy()

        if HAS_SERIAL:
            self.target_port = serial_port
            self.thread = threading.Thread(target=self._serial_worker, daemon=True)
            self.thread.start()

    def _init_usb_joy(self):
        pygame.joystick.init()
        if pygame.joystick.get_count() > 0:
            try:
                self.usb_joy = pygame.joystick.Joystick(0)
                self.usb_joy.init()
                self.source_type = f"USB: {self.usb_joy.get_name()}"
            except Exception:
                pass

    def _serial_worker(self):
        while self.running:
            if not self.arduino_connected:
                port = self.target_port
                if not port:
                    ports = serial.tools.list_ports.comports()
                    for p in ports:
                        if any(k in p.description.lower() for k in ['arduino', 'ch340', 'ft232', 'usb serial', 'com']):
                            port = p.device
                            break
                    if not port and len(ports) > 0:
                        port = ports[0].device

                if port:
                    try:
                        ser = serial.Serial(port, 115200, timeout=1.0)
                        time.sleep(1.5)
                        self.arduino_connected = True
                        self.source_type = f"Arduino UNO ({port})"
                        print(f"[Serial] Arduino connected on {port}")
                        while self.running and self.arduino_connected:
                            line = ser.readline().decode('ascii', errors='ignore').strip()
                            if line.startswith("J,") or line.startswith("JOY:"):
                                line_clean = line.replace("JOY:", "").replace("J,", "")
                                parts = line_clean.split(",")
                                if len(parts) >= 9:
                                    try:
                                        self.raw_lx = int(parts[0])
                                        self.raw_ly = int(parts[1])
                                        self.raw_rx = int(parts[2])
                                        self.raw_ry = int(parts[3])
                                        self.raw_sw1 = int(parts[4])
                                        self.raw_sw2 = int(parts[5])
                                        self.raw_b1  = int(parts[6])
                                        self.raw_b2  = int(parts[7])
                                        self.raw_b3  = int(parts[8])
                                    except ValueError:
                                        pass
                    except Exception:
                        self.arduino_connected = False
            time.sleep(1.0)

    def _apply_deadzone(self, v):
        if abs(v) < self.deadzone: return 0.0
        s = 1.0 if v > 0 else -1.0
        return s * (abs(v) - self.deadzone) / (1.0 - self.deadzone)

    def update(self, dt):
        h_roll, h_pitch, h_yaw = 0.0, 0.0, 0.0
        h_fire, h_missile, h_boost, h_cam = False, False, False, False

        if self.arduino_connected:
            nlx = (self.raw_lx - self.center_lx) / 512.0
            nly = (self.raw_ly - self.center_ly) / 512.0
            nrx = (self.raw_rx - self.center_rx) / 512.0
            nry = (self.raw_ry - self.center_ry) / 512.0

            h_roll = self._apply_deadzone(nlx)
            h_pitch = self._apply_deadzone(-nly)
            h_yaw = self._apply_deadzone(nrx)

            ry_val = self._apply_deadzone(-nry)
            if abs(ry_val) > 0.05:
                self.throttle = max(0.0, min(1.0, self.throttle + ry_val * dt * 0.8))

            h_fire = bool(self.raw_b1)
            h_missile = bool(self.raw_b2)
            h_boost = bool(self.raw_b3)
            h_cam = bool(self.raw_sw2)

        elif self.usb_joy:
            try:
                if self.usb_joy.get_numaxes() >= 4:
                    h_roll = self._apply_deadzone(self.usb_joy.get_axis(0))
                    h_pitch = self._apply_deadzone(-self.usb_joy.get_axis(1))
                    h_yaw = self._apply_deadzone(self.usb_joy.get_axis(2))
                    ry = self._apply_deadzone(-self.usb_joy.get_axis(3))
                    if abs(ry) > 0.05:
                        self.throttle = max(0.0, min(1.0, self.throttle + ry * dt * 0.8))

                if self.usb_joy.get_numbuttons() >= 4:
                    h_fire = self.usb_joy.get_button(0)
                    h_missile = self.usb_joy.get_button(1)
                    h_boost = self.usb_joy.get_button(2)
                    h_cam = self.usb_joy.get_button(3)
            except Exception:
                pass

        keys = pygame.key.get_pressed()
        k_roll, k_pitch, k_yaw = 0.0, 0.0, 0.0

        if keys[pygame.K_a] or keys[pygame.K_LEFT]:  k_roll -= 1.0
        if keys[pygame.K_d] or keys[pygame.K_RIGHT]: k_roll += 1.0
        if keys[pygame.K_w] or keys[pygame.K_UP]:    k_pitch += 1.0
        if keys[pygame.K_s] or keys[pygame.K_DOWN]:  k_pitch -= 1.0
        if keys[pygame.K_q]: k_yaw -= 1.0
        if keys[pygame.K_e]: k_yaw += 1.0

        if keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT] or keys[pygame.K_KP_PLUS]:
            self.throttle = min(1.0, self.throttle + dt * 0.6)
        if keys[pygame.K_LCTRL] or keys[pygame.K_RCTRL] or keys[pygame.K_KP_MINUS]:
            self.throttle = max(0.0, self.throttle - dt * 0.6)

        m_btns = pygame.mouse.get_pressed()
        rel_x, rel_y = pygame.mouse.get_rel()
        if pygame.mouse.get_focused() and m_btns[0]:
            k_roll += rel_x * 0.04
            k_pitch -= rel_y * 0.04

        k_fire = keys[pygame.K_SPACE] or m_btns[0] or keys[pygame.K_RETURN]
        k_missile = keys[pygame.K_f] or m_btns[2] or keys[pygame.K_m]
        k_boost = keys[pygame.K_TAB] or keys[pygame.K_LSHIFT]
        k_cam = keys[pygame.K_c] or keys[pygame.K_v]

        target_roll  = h_roll + k_roll
        target_pitch = h_pitch + k_pitch
        target_yaw   = h_yaw + k_yaw

        target_roll  = max(-1.0, min(1.0, target_roll))
        target_pitch = max(-1.0, min(1.0, target_pitch))
        target_yaw   = max(-1.0, min(1.0, target_yaw))

        self.roll  += (target_roll - self.roll) * min(1.0, dt * 12.0)
        self.pitch += (target_pitch - self.pitch) * min(1.0, dt * 12.0)
        self.yaw   += (target_yaw - self.yaw) * min(1.0, dt * 12.0)

        self.btn_fire = h_fire or k_fire
        self.btn_missile = h_missile or k_missile
        self.btn_boost = h_boost or k_boost
        self.btn_cam = h_cam or k_cam

    def calibrate(self):
        self.center_lx = self.raw_lx; self.center_ly = self.raw_ly
        self.center_rx = self.raw_rx; self.center_ry = self.raw_ry
        print(f"[Controller] Calibrated zero centers: LX={self.center_lx} LY={self.center_ly}")

    def close(self):
        self.running = False

# =====================================================================
#  3D ENGINE & CAMERA RENDERER
# =====================================================================
class Engine3D:
    def __init__(self, screen):
        self.screen = screen
        self.w, self.h = screen.get_size()
        self.cx, self.cy = self.w // 2, self.h // 2
        self.fov_dist = 600.0
        self.build_terrain()

    def resize(self, w, h):
        self.w, self.h = w, h
        self.cx, self.cy = w // 2, h // 2

    def build_terrain(self):
        # Load imported 3D OBJ Models
        self.raw_models = {}
        models_dir = os.path.join(HERE, "assets", "models")
        for m_name in ["jet_fighter", "cyber_drone", "ring_gate", "missile_rocket"]:
            p = os.path.join(models_dir, f"{m_name}.obj")
            if os.path.exists(p):
                model_data = {'verts': [], 'faces': []}
                with open(p, 'r') as f:
                    for line in f:
                        if line.startswith('v '):
                            model_data['verts'].append([float(x) for x in line.split()[1:4]])
                        elif line.startswith('f '):
                            face = [int(x.split('/')[0]) - 1 for x in line.split()[1:]]
                            model_data['faces'].append(face)
                self.raw_models[m_name] = model_data

    def project_model(self, m_name, pos, rot_y, cam_pos, yaw_rad, pitch_rad, roll_rad, scale=1.0):
        if m_name not in self.raw_models:
            return []
        m = self.raw_models[m_name]
        verts = np.array(m['verts']) * scale
        
        # Apply Y rotation around model origin
        cy, sy = math.cos(math.radians(rot_y)), math.sin(math.radians(rot_y))
        rot_verts = np.zeros_like(verts)
        rot_verts[:, 0] = verts[:, 0] * cy - verts[:, 2] * sy
        rot_verts[:, 1] = verts[:, 1]
        rot_verts[:, 2] = verts[:, 0] * sy + verts[:, 2] * cy

        world_verts = rot_verts + pos
        s_pts = self.project_3d(world_verts, cam_pos, yaw_rad, pitch_rad, roll_rad)
        return s_pts, m['faces']

    def render(self, player, game_state):
        self.screen.fill((8, 12, 28)) # Sunset cyber space background

        # 1. Sky Horizon Gradient
        pygame.draw.rect(self.screen, (20, 10, 45), (0, 0, self.w, self.cy))
        pygame.draw.rect(self.screen, (10, 20, 50), (0, self.cy, self.w, self.h - self.cy))
        pygame.draw.line(self.screen, (0, 220, 255), (0, self.cy), (self.w, self.cy), 2)

        cam_pos, c_yaw, c_pitch, c_roll = player.get_cam_transform()
        yaw_rad = math.radians(c_yaw)
        pitch_rad = math.radians(c_pitch)
        roll_rad = math.radians(c_roll)

        render_queue = []

        # 2. Collect Terrain Polygons
        for poly in self.terrain_polys:
            dist = np.linalg.norm(poly['center'] - cam_pos)
            if dist < 1600.0:
                s_pts = self.project_3d(poly['pts'], cam_pos, yaw_rad, pitch_rad, roll_rad)
                if all(p is not None for p in s_pts):
                    poly_2d = [(p[0], p[1]) for p in s_pts]
                    render_queue.append(('poly', dist, poly_2d, poly['col']))

        # 3. Collect 3D Ring Gate OBJ Models
        for g in game_state['gates']:
            pos = np.array(g['pos'])
            dist = np.linalg.norm(pos - cam_pos)
            if dist < 1800.0:
                s_pts, faces = self.project_model("ring_gate", pos, 0, cam_pos, yaw_rad, pitch_rad, roll_rad, scale=1.2)
                col = (0, 255, 240) if g['active'] else (100, 100, 120)
                for f in faces:
                    if all(i < len(s_pts) and s_pts[i] is not None for i in f):
                        face_pts = [(s_pts[i][0], s_pts[i][1]) for i in f]
                        render_queue.append(('obj_face', dist, face_pts, col))

        # 4. Collect 3D Enemy Drone OBJ Models
        for d in game_state['drones']:
            pos = np.array(d['pos'])
            dist = np.linalg.norm(pos - cam_pos)
            if dist < 1800.0:
                s_pts, faces = self.project_model("cyber_drone", pos, time.time()*40.0, cam_pos, yaw_rad, pitch_rad, roll_rad, scale=1.0)
                for f in faces:
                    if all(i < len(s_pts) and s_pts[i] is not None for i in f):
                        face_pts = [(s_pts[i][0], s_pts[i][1]) for i in f]
                        render_queue.append(('obj_face', dist, face_pts, (255, 40, 60)))

        # 5. Collect 3D Player Jet OBJ Model (3rd person)
        if player.cam_mode == 0:
            p_pos = np.array(player.pos)
            dist = np.linalg.norm(p_pos - cam_pos)
            s_pts, faces = self.project_model("jet_fighter", p_pos, player.yaw, cam_pos, yaw_rad, pitch_rad, roll_rad, scale=1.0)
            for f in faces:
                if all(i < len(s_pts) and s_pts[i] is not None for i in f):
                    face_pts = [(s_pts[i][0], s_pts[i][1]) for i in f]
                    render_queue.append(('obj_face', dist - 2.0, face_pts, (0, 220, 255)))

        # 6. Collect Laser Bolts
        for l in game_state['lasers']:
            l_pos = np.array(l['pos'])
            dist = np.linalg.norm(l_pos - cam_pos)
            if dist < 1800.0:
                s_l = self.project_3d(np.array([l_pos, l_pos + np.array(l['dir'])*25.0]), cam_pos, yaw_rad, pitch_rad, roll_rad)
                if all(p is not None for p in s_l):
                    col = (255, 50, 50) if l['is_enemy'] else (0, 255, 180)
                    render_queue.append(('laser', dist, [(p[0], p[1]) for p in s_l], col))

        # 7. Collect Particles
        for p in game_state['particles']:
            p_pos = np.array([p[0], p[1], p[2]])
            dist = np.linalg.norm(p_pos - cam_pos)
            if dist < 1800.0:
                s_p = self.project_3d(np.array([p_pos]), cam_pos, yaw_rad, pitch_rad, roll_rad)
                if s_p[0] is not None:
                    col = (int(p[6]*255), int(p[7]*255), int(p[8]*255))
                    render_queue.append(('particle', dist, [(s_p[0][0], s_p[0][1])], col))

        # Sort Render Queue (Painter's Algorithm - Far to Near)
        render_queue.sort(key=lambda item: item[1], reverse=True)

        # Draw 3D Entities
        for item in render_queue:
            t_type, dist, pts, col = item
            if t_type == 'poly':
                pygame.draw.polygon(self.screen, col, pts)
                pygame.draw.polygon(self.screen, (10, 30, 60), pts, 1)
            elif t_type == 'obj_face':
                pygame.draw.polygon(self.screen, col, pts)
                pygame.draw.polygon(self.screen, (0, 30, 60), pts, 1)
            elif t_type == 'laser':
                pygame.draw.line(self.screen, col, pts[0], pts[1], 3)
            elif t_type == 'particle':
                pygame.draw.circle(self.screen, col, pts[0], 3)

# =====================================================================
#  PLAYER & GAMEPLAY PHYSICS
# =====================================================================
class PlayerJet:
    def __init__(self):
        self.reset()

    def reset(self):
        self.pos = [0.0, 140.0, -100.0]
        self.pitch = 0.0
        self.yaw = 0.0
        self.roll = 0.0
        self.speed = 50.0
        self.health = 100.0
        self.boost_active = False
        self.cam_mode = 0 # 0: 3rd person, 1: 1st person cockpit
        self.cd_fire = 0.0
        self.cd_missile = 0.0

    def get_forward_vec(self):
        pr, yr = math.radians(self.pitch), math.radians(self.yaw)
        return [math.sin(yr)*math.cos(pr), math.sin(pr), -math.cos(yr)*math.cos(pr)]

    def update(self, ctrl, dt):
        target_spd = 25.0 + ctrl.throttle * 120.0
        if ctrl.btn_boost:
            target_spd *= 1.8
            self.boost_active = True
        else:
            self.boost_active = False

        self.speed += (target_spd - self.speed) * min(1.0, dt * 4.0)

        turn_rate = 65.0
        self.pitch += ctrl.pitch * turn_rate * dt
        self.roll  += ctrl.roll  * turn_rate * 1.6 * dt
        self.yaw   += ctrl.yaw   * turn_rate * 0.9 * dt

        if abs(ctrl.roll) < 0.1:
            self.roll *= (1.0 - dt * 2.5)

        self.pitch = max(-85.0, min(85.0, self.pitch))

        fwd = self.get_forward_vec()
        self.pos[0] += fwd[0] * self.speed * dt
        self.pos[1] += fwd[1] * self.speed * dt
        self.pos[2] += fwd[2] * self.speed * dt

        # Terrain crash boundary
        if self.pos[1] < 12.0:
            self.pos[1] = 12.0
            self.health -= dt * 40.0
            self.pitch = max(15.0, self.pitch)

        self.cd_fire = max(0.0, self.cd_fire - dt)
        self.cd_missile = max(0.0, self.cd_missile - dt)

    def get_cam_transform(self):
        fwd = self.get_forward_vec()
        if self.cam_mode == 0:
            d, h = 26.0, 7.0
            cx = self.pos[0] - fwd[0]*d
            cy = self.pos[1] - fwd[1]*d + h
            cz = self.pos[2] - fwd[2]*d
            return np.array([cx, cy, cz]), self.yaw, self.pitch, self.roll
        else:
            return np.array([self.pos[0], self.pos[1]+1.5, self.pos[2]]), self.yaw, self.pitch, self.roll

class GameplayManager:
    def __init__(self, audio):
        self.audio = audio
        self.player = PlayerJet()
        self.lasers = []
        self.drones = []
        self.ring_gates = []
        self.particles = []
        self.score = 0
        self.time_left = 60.0
        self.mode = "TARGET ASSAULT"
        self.gate_idx = 0
        self.reset()

    def reset(self):
        self.player.reset()
        self.lasers.clear()
        self.drones.clear()
        self.ring_gates.clear()
        self.particles.clear()
        self.score = 0
        self.time_left = 75.0
        self.gate_idx = 0

        # Drones
        for i in range(10):
            ang = random.uniform(0, math.pi * 2)
            dist = random.uniform(300, 1100)
            self.drones.append({
                'id': i,
                'pos': [math.cos(ang)*dist, random.uniform(90, 240), math.sin(ang)*dist],
                'alive': True,
                'hp': 100.0
            })

        # Rings
        for i in range(12):
            ang = (i / 12.0) * math.pi * 1.8
            dist = 350.0 + i * 90.0
            self.ring_gates.append({
                'idx': i,
                'pos': [math.cos(ang)*dist, 110.0 + math.sin(i*0.6)*50.0, math.sin(ang)*dist - 150],
                'radius': 24.0,
                'active': (i == 0)
            })

    def update(self, ctrl, dt):
        self.time_left = max(0.0, self.time_left - dt)
        self.player.update(ctrl, dt)
        if self.audio: self.audio.update_engine(ctrl.throttle, self.player.boost_active)

        # Weapons
        if ctrl.btn_fire and self.player.cd_fire <= 0.0:
            fwd = self.player.get_forward_vec()
            self.lasers.append({'pos': list(self.player.pos), 'dir': fwd, 'is_enemy': False, 'life': 2.0})
            self.player.cd_fire = 0.12
            if self.audio: self.audio.play('laser', volume=0.4)

        # Update Lasers
        alive_l = []
        for l in self.lasers:
            l['pos'][0] += l['dir'][0] * 700.0 * dt
            l['pos'][1] += l['dir'][1] * 700.0 * dt
            l['pos'][2] += l['dir'][2] * 700.0 * dt
            l['life'] -= dt
            if l['life'] > 0.0:
                hit = False
                if not l['is_enemy']:
                    for d in self.drones:
                        if d['alive']:
                            dist = math.sqrt(sum((d['pos'][k] - l['pos'][k])**2 for k in range(3)))
                            if dist < 16.0:
                                d['alive'] = False
                                self.score += 500
                                hit = True
                                self._spawn_explosion(d['pos'])
                                if self.audio: self.audio.play('explosion', volume=0.8)
                                break
                if not hit: alive_l.append(l)
        self.lasers = alive_l

        # Check Ring Gates
        if self.gate_idx < len(self.ring_gates):
            g = self.ring_gates[self.gate_idx]
            dist = math.sqrt(sum((g['pos'][k] - self.player.pos[k])**2 for k in range(3)))
            if dist < g['radius']:
                g['active'] = False
                self.gate_idx += 1
                if self.gate_idx < len(self.ring_gates):
                    self.ring_gates[self.gate_idx]['active'] = True
                self.score += 300
                self.time_left += 5.0
                if self.audio: self.audio.play('ring', volume=0.8)

        # Update Particles
        alive_p = []
        for p in self.particles:
            p[0] += p[3] * dt; p[1] += p[4] * dt; p[2] += p[5] * dt
            p[10] -= dt
            if p[10] > 0.0: alive_p.append(p)
        self.particles = alive_p

    def _spawn_explosion(self, pos):
        for _ in range(35):
            self.particles.append([
                pos[0], pos[1], pos[2],
                random.uniform(-50, 50), random.uniform(-50, 50), random.uniform(-50, 50),
                1.0, random.uniform(0.3, 0.8), 0.0, 1.0, random.uniform(0.3, 0.7)
            ])

    def get_state(self):
        return {
            'drones': [d for d in self.drones if d['alive']],
            'gates': self.ring_gates,
            'lasers': self.lasers,
            'particles': self.particles
        }

# =====================================================================
#  2D HUD & OVERLAY ENGINE
# =====================================================================
class HUDOverlay:
    def __init__(self, screen):
        self.screen = screen
        self.w, self.h = screen.get_size()
        self.font_l = pygame.font.SysFont("Consolas", 28, bold=True)
        self.font_m = pygame.font.SysFont("Consolas", 18, bold=True)
        self.font_s = pygame.font.SysFont("Consolas", 13)

    def resize(self, w, h):
        self.w, self.h = w, h

    def render(self, player, ctrl, game, highscores, fps=60):
        cx, cy = self.w // 2, self.h // 2

        # 1. Pitch Ladder & Horizon Crosshair
        col_hud = (0, 255, 200)
        pygame.draw.line(self.screen, col_hud, (cx - 30, cy), (cx - 10, cy), 2)
        pygame.draw.line(self.screen, col_hud, (cx + 10, cy), (cx + 30, cy), 2)
        pygame.draw.line(self.screen, col_hud, (cx, cy - 20), (cx, cy - 10), 2)

        # Pitch Bar
        pitch_y = cy + player.pitch * 3.5
        pygame.draw.line(self.screen, (0, 255, 200), (cx - 90, pitch_y), (cx - 30, pitch_y), 2)
        pygame.draw.line(self.screen, (0, 255, 200), (cx + 30, pitch_y), (cx + 90, pitch_y), 2)

        # 2. Heading Tape & Altitude
        yaw_deg = int(player.yaw) % 360
        spd = int(player.speed * 10.0)
        alt = int(player.pos[1])

        t_head = self.font_m.render(f"HDG {yaw_deg:03d}°", True, (0, 255, 220))
        self.screen.blit(t_head, (cx - 40, 30))

        t_spd = self.font_m.render(f"SPD {spd} KTS", True, (0, 255, 120))
        self.screen.blit(t_spd, (cx - 280, cy - 10))

        t_alt = self.font_m.render(f"ALT {alt} M", True, (0, 255, 120))
        self.screen.blit(t_alt, (cx + 180, cy - 10))

        # 3. Status Bars (Hull, Throttle, Time, Score)
        bx, by = 30, self.h - 120
        # Hull Bar
        t_hp = self.font_s.render(f"HULL INTEGRITY: {int(player.health)}%", True, (0, 255, 200))
        self.screen.blit(t_hp, (bx, by - 20))
        pygame.draw.rect(self.screen, (30, 40, 60), (bx, by, 200, 12))
        pygame.draw.rect(self.screen, (0, 230, 120), (bx, by, int(player.health * 2.0), 12))

        # Throttle Bar
        t_th = self.font_s.render(f"THROTTLE: {int(ctrl.throttle * 100)}%", True, (255, 200, 0))
        self.screen.blit(t_th, (bx, by + 20))
        pygame.draw.rect(self.screen, (30, 40, 60), (bx, by + 40, 200, 12))
        pygame.draw.rect(self.screen, (255, 180, 0), (bx, by + 40, int(ctrl.throttle * 200.0), 12))

        # Score & High Score
        hi = highscores.get(game.mode, 0)
        t_score = self.font_m.render(f"SCORE: {game.score}  |  HI: {hi}  |  TIME: {int(game.time_left)}s", True, (255, 255, 255))
        self.screen.blit(t_score, (30, 25))

        # 4. Tactical Radar Mini-Map
        rx, ry, rr = self.w - 100, 100, 65
        pygame.draw.circle(self.screen, (0, 200, 255), (rx, ry), rr, 2)
        pygame.draw.circle(self.screen, (0, 255, 0), (rx, ry), 4)

        for d in game.drones:
            if d['alive']:
                dx = int((d['pos'][0] - player.pos[0]) * 0.03)
                dz = int((d['pos'][2] - player.pos[2]) * 0.03)
                if math.sqrt(dx*dx + dz*dz) < rr - 4:
                    pygame.draw.circle(self.screen, (255, 40, 60), (rx + dx, ry + dz), 3)

        for g in game.ring_gates:
            if g['active']:
                dx = int((g['pos'][0] - player.pos[0]) * 0.03)
                dz = int((g['pos'][2] - player.pos[2]) * 0.03)
                if math.sqrt(dx*dx + dz*dz) < rr - 4:
                    pygame.draw.circle(self.screen, (0, 255, 240), (rx + dx, ry + dz), 4, 1)

        # 5. Arduino UNO Telemetry HUD
        ax, ay = self.w - 240, self.h - 140
        t_ard = self.font_s.render("ARDUINO LAB TELEMETRY", True, (0, 240, 255))
        self.screen.blit(t_ard, (ax, ay - 22))

        st_col = (0, 255, 120) if ctrl.arduino_connected else (255, 180, 0)
        t_src = self.font_s.render(f"SOURCE: {ctrl.source_type}", True, st_col)
        self.screen.blit(t_src, (ax, ay - 8))

        # Left Stick Box
        lx_c, ly_c = ax + 35, ay + 45
        pygame.draw.rect(self.screen, (0, 180, 240), (lx_c - 25, ly_c - 25, 50, 50), 1)
        pygame.draw.circle(self.screen, (0, 255, 120), (lx_c + int(ctrl.roll * 20), ly_c - int(ctrl.pitch * 20)), 5)
        self.screen.blit(self.font_s.render("STICK 1", True, (180, 180, 180)), (lx_c - 20, ly_c + 28))

        # Right Stick Box
        rx_c, ry_c = ax + 140, ay + 45
        pygame.draw.rect(self.screen, (0, 180, 240), (rx_c - 25, ry_c - 25, 50, 50), 1)
        pygame.draw.circle(self.screen, (255, 200, 0), (rx_c + int(ctrl.yaw * 20), ry_c - int((ctrl.throttle-0.5)*40)), 5)
        self.screen.blit(self.font_s.render("STICK 2", True, (180, 180, 180)), (rx_c - 20, ry_c + 28))

# =====================================================================
#  MAIN APPLICATION & MENU STATE MACHINE
# =====================================================================
class HyperFlightApp:
    def __init__(self, serial_port=None, joytest=False, sound_enabled=True):
        pygame.init()
        self.w, self.h = 1280, 720
        self.screen = pygame.display.set_mode((self.w, self.h), pygame.RESIZABLE)
        pygame.display.set_caption("HYPER FLIGHT 3D - SKYBOUND NEXUS")

        self.clock = pygame.time.Clock()
        self.highscores = load_highscores()

        self.audio = AudioSynth(enabled=sound_enabled)
        self.ctrl = InputController(serial_port=serial_port)
        self.engine = Engine3D(self.screen)
        self.hud = HUDOverlay(self.screen)
        self.game = GameplayManager(self.audio)

        self.joytest = joytest
        self.state = "MENU" # "MENU", "GAME", "CALIBRATION", "PAUSE"
        self.menu_idx = 0
        self.menu_items = [
            "1. TARGET ASSAULT COMBAT",
            "2. RING APEX CHECKPOINT RACE",
            "3. FREE FLIGHT SANDBOX",
            "4. ARDUINO GAMEPAD CALIBRATION",
            "5. EXIT GAME"
        ]
        self.running = True

    def run_joytest_mode(self):
        print("\n========================================================")
        print("  HYPER FLIGHT 3D - GAMEPAD & ARDUINO JOYSTICK TEST")
        print("========================================================")
        print("Move your joysticks and press buttons. Press Ctrl+C to exit.\n")
        try:
            while True:
                self.ctrl.update(0.016)
                sys.stdout.write(
                    f"\r[{self.ctrl.source_type}] "
                    f"Roll:{self.ctrl.roll:+.2f} | Pitch:{self.ctrl.pitch:+.2f} | "
                    f"Yaw:{self.ctrl.yaw:+.2f} | Thr:{self.ctrl.throttle:.2f} | "
                    f"Fire:{int(self.ctrl.btn_fire)} Miss:{int(self.ctrl.btn_missile)} Boost:{int(self.ctrl.btn_boost)}"
                )
                sys.stdout.flush()
                time.sleep(0.03)
        except KeyboardInterrupt:
            print("\nJoytest ended.")
            self.ctrl.close()

    def run(self):
        if self.joytest:
            self.run_joytest_mode()
            return

        while self.running:
            dt = min(0.1, self.clock.tick(60) / 1000.0)

            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:
                    self.running = False
                elif ev.type == pygame.VIDEORESIZE:
                    self.w, self.h = ev.w, ev.h
                    self.screen = pygame.display.set_mode((self.w, self.h), pygame.RESIZABLE)
                    self.engine.resize(self.w, self.h)
                    self.hud.resize(self.w, self.h)
                elif ev.type == pygame.KEYDOWN:
                    if ev.key == pygame.K_ESCAPE:
                        if self.state == "GAME": self.state = "PAUSE"
                        elif self.state in ("PAUSE", "CALIBRATION"): self.state = "MENU"

                    if self.state == "MENU":
                        if ev.key in (pygame.K_UP, pygame.K_w):
                            self.menu_idx = (self.menu_idx - 1) % len(self.menu_items)
                        elif ev.key in (pygame.K_DOWN, pygame.K_s):
                            self.menu_idx = (self.menu_idx + 1) % len(self.menu_items)
                        elif ev.key in (pygame.K_RETURN, pygame.K_SPACE):
                            self.select_menu_option(self.menu_idx)
                    elif self.state == "PAUSE":
                        if ev.key == pygame.K_r: self.state = "GAME"
                        elif ev.key == pygame.K_m: self.state = "MENU"
                    elif self.state == "GAME":
                        if ev.key == pygame.K_c:
                            self.game.player.cam_mode = 1 - self.game.player.cam_mode
                    elif self.state == "CALIBRATION":
                        if ev.key == pygame.K_c:
                            self.ctrl.calibrate()

            self.ctrl.update(dt)

            if self.state == "MENU":
                self.render_menu()
            elif self.state == "CALIBRATION":
                self.render_calibration()
            elif self.state == "GAME":
                self.game.update(self.ctrl, dt)
                self.engine.render(self.game.player, self.game.get_state())
                self.hud.render(self.game.player, self.ctrl, self.game, self.highscores)

                # High score persistence check
                if self.game.score > self.highscores.get(self.game.mode, 0):
                    self.highscores[self.game.mode] = self.game.score
                    save_highscores(self.highscores)

            elif self.state == "PAUSE":
                self.screen.fill((10, 15, 30))
                cx, cy = self.w // 2, self.h // 2
                t1 = self.hud.font_l.render("GAME PAUSED", True, (255, 255, 0))
                t2 = self.hud.font_m.render("Press [R] to Resume  |  Press [M] for Menu", True, (255, 255, 255))
                self.screen.blit(t1, (cx - 100, cy - 40))
                self.screen.blit(t2, (cx - 180, cy + 20))

            pygame.display.flip()

        self.audio.stop_engine()
        self.ctrl.close()
        pygame.quit()
        sys.exit()

    def select_menu_option(self, idx):
        if idx == 0:
            self.game.mode = "TARGET ASSAULT"
            self.game.reset()
            self.state = "GAME"
            self.audio.start_engine()
        elif idx == 1:
            self.game.mode = "RING APEX RACE"
            self.game.reset()
            self.state = "GAME"
            self.audio.start_engine()
        elif idx == 2:
            self.game.mode = "FREE FLIGHT"
            self.game.reset()
            self.state = "GAME"
            self.audio.start_engine()
        elif idx == 3:
            self.state = "CALIBRATION"
        elif idx == 4:
            self.running = False

    def render_menu(self):
        self.screen.fill((10, 16, 36))
        cx, cy = self.w // 2, self.h // 2

        # Title
        t_main = self.hud.font_l.render("HYPER FLIGHT 3D", True, (0, 240, 255))
        t_sub  = self.hud.font_m.render("SKYBOUND NEXUS - ARDUINO LAB EDITION", True, (180, 0, 255))
        self.screen.blit(t_main, (cx - 130, cy - 210))
        self.screen.blit(t_sub,  (cx - 180, cy - 170))

        # Hardware Badge
        st_col = (0, 255, 120) if self.ctrl.arduino_connected else (255, 180, 0)
        t_src = self.hud.font_m.render(f"HARDWARE SOURCE: {self.ctrl.source_type}", True, st_col)
        self.screen.blit(t_src, (cx - 170, cy - 120))

        # Menu List
        for i, item in enumerate(self.menu_items):
            col = (255, 255, 0) if i == self.menu_idx else (200, 210, 230)
            prefix = "> " if i == self.menu_idx else "  "
            txt = self.hud.font_m.render(prefix + item, True, col)
            self.screen.blit(txt, (cx - 160, cy - 40 + i * 36))

        # High Scores Banner
        hi_txt = f"BEST SCORE: {self.highscores.get('TARGET ASSAULT', 0)} PTS"
        self.screen.blit(self.hud.font_s.render(hi_txt, True, (0, 255, 200)), (cx - 100, cy + 155))

        # Footer
        self.screen.blit(self.hud.font_s.render("Use [UP/DOWN] or [W/S] to browse, [ENTER] to launch", True, (150, 150, 160)), (cx - 210, cy + 195))
        self.screen.blit(self.hud.font_s.render("Arduino Pinout: Joysticks A0-A3 | Buttons D2-D6 | Baud 115200", True, (0, 200, 220)), (cx - 240, cy + 218))

    def render_calibration(self):
        self.screen.fill((8, 14, 30))
        cx, cy = self.w // 2, self.h // 2

        t_title = self.hud.font_l.render("ARDUINO GAMEPAD CALIBRATION & TEST", True, (0, 255, 220))
        self.screen.blit(t_title, (cx - 250, 40))

        self.screen.blit(self.hud.font_m.render(f"Device: {self.ctrl.source_type}", True, (255, 255, 255)), (60, 110))
        self.screen.blit(self.hud.font_m.render(f"Raw Left Stick (A0, A1): LX={self.ctrl.raw_lx}  LY={self.ctrl.raw_ly}", True, (0, 255, 150)), (60, 145))
        self.screen.blit(self.hud.font_m.render(f"Raw Right Stick (A2, A3): RX={self.ctrl.raw_rx}  RY={self.ctrl.raw_ry}", True, (255, 200, 0)), (60, 175))
        self.screen.blit(self.hud.font_m.render(f"Switches (D2-D6): SW1={self.ctrl.raw_sw1} SW2={self.ctrl.raw_sw2} B1={self.ctrl.raw_b1} B2={self.ctrl.raw_b2} B3={self.ctrl.raw_b3}", True, (200, 200, 255)), (60, 205))

        self.screen.blit(self.hud.font_m.render("Press [C] to Calibrate Zero Centers  |  Press [ESC] for Menu", True, (0, 240, 255)), (60, 250))

        # Stick Diagram Boxes
        lx_c, ly_c = cx - 180, cy + 80
        pygame.draw.rect(self.screen, (0, 200, 255), (lx_c - 70, ly_c - 70, 140, 140), 2)
        pygame.draw.circle(self.screen, (0, 255, 120), (lx_c + int(self.ctrl.roll * 60), ly_c - int(self.ctrl.pitch * 60)), 10)
        self.screen.blit(self.hud.font_s.render("LEFT STICK (PITCH/ROLL)", True, (0, 255, 150)), (lx_c - 90, ly_c + 85))

        rx_c, ry_c = cx + 180, cy + 80
        pygame.draw.rect(self.screen, (0, 200, 255), (rx_c - 70, ry_c - 70, 140, 140), 2)
        pygame.draw.circle(self.screen, (255, 200, 0), (rx_c + int(self.ctrl.yaw * 60), ry_c - int((self.ctrl.throttle-0.5)*120)), 10)
        self.screen.blit(self.hud.font_s.render("RIGHT STICK (YAW/THROTTLE)", True, (255, 200, 0)), (rx_c - 90, ry_c + 85))

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="HYPER FLIGHT 3D Simulator")
    parser.add_argument("--serial", help="Serial port for Arduino (e.g. COM3)")
    parser.add_argument("--joytest", action="store_true", help="Run gamepad input test tool")
    parser.add_argument("--nosound", action="store_true", help="Disable sound synthesizer")
    args = parser.parse_args()

    app = HyperFlightApp(serial_port=args.serial, joytest=args.joytest, sound_enabled=not args.nosound)
    app.run()
