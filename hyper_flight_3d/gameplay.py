import math
import random
import numpy as np

class PlayerJet:
    def __init__(self):
        self.reset()

    def reset(self):
        # Position in 3D Space (X, Y, Z) - Y is height above terrain
        self.pos = [0.0, 150.0, -100.0]
        # Rotations in Degrees (Pitch, Yaw, Roll)
        self.pitch = 0.0
        self.yaw = 0.0
        self.roll = 0.0

        # Dynamics
        self.speed = 40.0         # Current forward speed
        self.min_speed = 15.0
        self.max_speed = 120.0
        self.health = 100.0
        self.weapon_cooldown = 0.0
        self.missile_cooldown = 0.0
        self.boost_active = False

        # Camera offsets
        self.cam_mode = 0 # 0: 3rd person chase, 1: 1st person cockpit

    def get_forward_vector(self):
        p_rad = math.radians(self.pitch)
        y_rad = math.radians(self.yaw)
        r_rad = math.radians(self.roll)

        fx = math.sin(y_rad) * math.cos(p_rad)
        fy = math.sin(p_rad)
        fz = -math.cos(y_rad) * math.cos(p_rad)
        return [fx, fy, fz]

    def update(self, controller, dt, terrain_renderer):
        # 1. Throttle & Speed calculation
        target_speed = self.min_speed + controller.throttle * (self.max_speed - self.min_speed)
        if controller.btn_boost:
            target_speed *= 1.8
            self.boost_active = True
        else:
            self.boost_active = False

        self.speed += (target_speed - self.speed) * min(1.0, dt * 3.0)

        # 2. Rotational Aerodynamics (Pitch, Roll, Yaw)
        turn_rate = 60.0 # deg/sec
        self.pitch += controller.pitch * turn_rate * dt
        self.roll  += controller.roll  * turn_rate * 1.5 * dt
        self.yaw   += controller.yaw   * turn_rate * 0.8 * dt

        # Auto-leveling roll stabilizing towards horizontal
        if abs(controller.roll) < 0.1:
            self.roll *= (1.0 - dt * 2.0)

        # Clamp pitch [-85, 85]
        self.pitch = max(-85.0, min(85.0, self.pitch))

        # 3. Position update along forward vector
        fwd = self.get_forward_vector()
        self.pos[0] += fwd[0] * self.speed * dt
        self.pos[1] += fwd[1] * self.speed * dt
        self.pos[2] += fwd[2] * self.speed * dt

        # 4. Terrain collision check
        terrain_height = 0.0
        if terrain_renderer:
            # Approximate height check
            terrain_height = math.sin(self.pos[0] * 0.005) * math.cos(self.pos[2] * 0.005) * 200.0
        
        min_alt = terrain_height + 5.0
        if self.pos[1] < min_alt:
            self.pos[1] = min_alt
            self.health -= dt * 30.0 # Terrain impact damage
            self.pitch = max(10.0, self.pitch) # Auto pull nose up

        # Cooldown ticks
        self.weapon_cooldown = max(0.0, self.weapon_cooldown - dt)
        self.missile_cooldown = max(0.0, self.missile_cooldown - dt)

    def get_camera_transform(self):
        fwd = self.get_forward_vector()
        if self.cam_mode == 0:
            # 3rd person chase cam
            cam_dist = 22.0
            cam_h = 6.0
            cam_x = self.pos[0] - fwd[0] * cam_dist
            cam_y = self.pos[1] - fwd[1] * cam_dist + cam_h
            cam_z = self.pos[2] - fwd[2] * cam_dist
            return [cam_x, cam_y, cam_z], self.yaw, self.pitch, self.roll
        else:
            # 1st person cockpit view
            return [self.pos[0], self.pos[1] + 1.2, self.pos[2]], self.yaw, self.pitch, self.roll


class LaserBolt:
    def __init__(self, pos, dir_vec, speed=600.0, is_enemy=False):
        self.pos = list(pos)
        self.dir = list(dir_vec)
        self.speed = speed
        self.life = 2.5
        self.is_enemy = is_enemy

    def update(self, dt):
        self.pos[0] += self.dir[0] * self.speed * dt
        self.pos[1] += self.dir[1] * self.speed * dt
        self.pos[2] += self.dir[2] * self.speed * dt
        self.life -= dt
        return self.life > 0.0


class HomingMissile:
    def __init__(self, pos, target_drone):
        self.pos = list(pos)
        self.target = target_drone
        self.speed = 350.0
        self.life = 5.0
        self.dir = [0.0, 0.0, -1.0]

    def update(self, dt):
        if self.target and self.target['alive']:
            # Seek target direction vector
            dx = self.target['pos'][0] - self.pos[0]
            dy = self.target['pos'][1] - self.pos[1]
            dz = self.target['pos'][2] - self.pos[2]
            dist = math.sqrt(dx*dx + dy*dy + dz*dz)
            if dist > 0.1:
                target_dir = [dx/dist, dy/dist, dz/dist]
                # Smooth homing steering blend
                for i in range(3):
                    self.dir[i] += (target_dir[i] - self.dir[i]) * min(1.0, dt * 6.0)
                d_len = math.sqrt(sum(c*c for c in self.dir))
                if d_len > 0:
                    self.dir = [c/d_len for c in self.dir]

        self.pos[0] += self.dir[0] * self.speed * dt
        self.pos[1] += self.dir[1] * self.speed * dt
        self.pos[2] += self.dir[2] * self.speed * dt
        self.life -= dt
        return self.life > 0.0


class GameManager:
    def __init__(self, audio_synth):
        self.audio = audio_synth
        self.player = PlayerJet()
        self.lasers = []
        self.missiles = []
        self.particles = []
        self.drones = []
        self.ring_gates = []
        
        self.current_ring_idx = 0
        self.score = 0
        self.time_elapsed = 0.0
        self.mode = "TARGET_ASSAULT" # "TARGET_ASSAULT", "RING_RACE", "FREE_FLIGHT"

        self.spawn_world_entities()

    def spawn_world_entities(self):
        self.drones.clear()
        self.ring_gates.clear()

        # Spawn 3D Enemy Combat Drones
        for i in range(12):
            ang = random.uniform(0, math.pi * 2)
            dist = random.uniform(300, 1200)
            self.drones.append({
                'id': i,
                'pos': [math.cos(ang)*dist, random.uniform(80, 250), math.sin(ang)*dist],
                'rot': [0.0, random.uniform(0, 360), 0.0],
                'health': 100.0,
                'alive': True,
                'shoot_cd': random.uniform(1.0, 3.0)
            })

        # Spawn Sequential Ring Gates for Apex Race Mode
        g_count = 15
        for i in range(g_count):
            ang = (i / float(g_count)) * math.pi * 1.8
            dist = 400.0 + i * 80.0
            height = 100.0 + math.sin(i * 0.5) * 60.0
            self.ring_gates.append({
                'idx': i,
                'pos': [math.cos(ang)*dist, height, math.sin(ang)*dist - 200],
                'radius': 22.0
            })

    def update(self, controller, dt, terrain_renderer):
        self.time_elapsed += dt
        self.player.update(controller, dt, terrain_renderer)

        # Audio thrust modulation
        if self.audio:
            self.audio.update_engine(controller.throttle, self.player.boost_active)

        # Fire Player Weapons
        if controller.btn_fire and self.player.weapon_cooldown <= 0.0:
            fwd = self.player.get_forward_vector()
            # Dual wingtip plasma bolts
            self.lasers.append(LaserBolt(self.player.pos, fwd, is_enemy=False))
            self.player.weapon_cooldown = 0.12
            if self.audio:
                self.audio.play('laser', volume=0.4)

        if controller.btn_missile and self.player.missile_cooldown <= 0.0:
            # Find closest enemy drone for lock-on homing
            closest_target = None
            min_d = 9999.0
            for d in self.drones:
                if d['alive']:
                    dist = math.sqrt(sum((d['pos'][i] - self.player.pos[i])**2 for i in range(3)))
                    if dist < min_d:
                        min_d = dist
                        closest_target = d
            
            if closest_target:
                self.missiles.append(HomingMissile(self.player.pos, closest_target))
                self.player.missile_cooldown = 1.2
                if self.audio:
                    self.audio.play('missile', volume=0.6)

        # Add Engine Exhaust Particles
        if random.random() < 0.8:
            fwd = self.player.get_forward_vector()
            rx = self.player.pos[0] - fwd[0]*4.0 + random.uniform(-0.5, 0.5)
            ry = self.player.pos[1] - fwd[1]*4.0 + random.uniform(-0.5, 0.5)
            rz = self.player.pos[2] - fwd[2]*4.0 + random.uniform(-0.5, 0.5)
            self.particles.append([rx, ry, rz, -fwd[0]*20, -fwd[1]*20, -fwd[2]*20, 0.0, 0.8, 1.0, 0.9, 0.4])

        # Update Laser Bolts
        alive_lasers = []
        for l in self.lasers:
            if l.update(dt):
                # Check hit collisions with drones
                hit = False
                if not l.is_enemy:
                    for d in self.drones:
                        if d['alive']:
                            dist = math.sqrt(sum((d['pos'][i] - l.pos[i])**2 for i in range(3)))
                            if dist < 8.0:
                                d['health'] -= 35.0
                                hit = True
                                self.spawn_explosion_particles(l.pos, count=10)
                                if d['health'] <= 0.0:
                                    d['alive'] = False
                                    self.score += 500
                                    self.spawn_explosion_particles(d['pos'], count=35)
                                    if self.audio: self.audio.play('explosion', volume=0.7)
                                break
                if not hit:
                    alive_lasers.append(l)
        self.lasers = alive_lasers

        # Update Homing Missiles
        alive_missiles = []
        for m in self.missiles:
            # Spawn missile rocket smoke particles
            self.particles.append([m.pos[0], m.pos[1], m.pos[2], 0, 0, 0, 1.0, 0.6, 0.1, 0.8, 0.5])
            if m.update(dt):
                if m.target and m.target['alive']:
                    dist = math.sqrt(sum((m.target['pos'][i] - m.pos[i])**2 for i in range(3)))
                    if dist < 12.0:
                        m.target['health'] -= 100.0
                        m.target['alive'] = False
                        self.score += 1000
                        self.spawn_explosion_particles(m.pos, count=50)
                        if self.audio: self.audio.play('explosion', volume=0.9)
                        continue
                alive_missiles.append(m)
        self.missiles = alive_missiles

        # Update Enemy Drones AI
        for d in self.drones:
            if d['alive']:
                d['rot'][1] += dt * 30.0
                # Drone shooting at player
                d['shoot_cd'] -= dt
                if d['shoot_cd'] <= 0.0:
                    dist = math.sqrt(sum((self.player.pos[i] - d['pos'][i])**2 for i in range(3)))
                    if dist < 600.0:
                        dir_to_p = [(self.player.pos[i] - d['pos'][i])/dist for i in range(3)]
                        self.lasers.append(LaserBolt(d['pos'], dir_to_p, speed=300.0, is_enemy=True))
                        d['shoot_cd'] = random.uniform(2.0, 4.0)

        # Update Ring Checkpoints
        if self.current_ring_idx < len(self.ring_gates):
            curr_gate = self.ring_gates[self.current_ring_idx]
            dist_g = math.sqrt(sum((curr_gate['pos'][i] - self.player.pos[i])**2 for i in range(3)))
            if dist_g < curr_gate['radius']:
                self.current_ring_idx += 1
                self.score += 250
                if self.audio: self.audio.play('ring', volume=0.8)
                self.spawn_explosion_particles(curr_gate['pos'], count=20, is_cyan=True)

        # Update Particles Physics & Decay
        alive_particles = []
        for p in self.particles:
            p[0] += p[3] * dt
            p[1] += p[4] * dt
            p[2] += p[5] * dt
            p[10] -= dt # life decay
            p[9] = max(0.0, p[10] / 0.8) # alpha decay
            if p[10] > 0.0:
                alive_particles.append(p)
        self.particles = alive_particles

    def spawn_explosion_particles(self, pos, count=30, is_cyan=False):
        for _ in range(count):
            vx = random.uniform(-40, 40)
            vy = random.uniform(-40, 40)
            vz = random.uniform(-40, 40)
            if is_cyan:
                r, g, b = 0.0, 0.9, 1.0
            else:
                r, g, b = random.uniform(0.8, 1.0), random.uniform(0.3, 0.7), 0.0
            self.particles.append([pos[0], pos[1], pos[2], vx, vy, vz, r, g, b, 1.0, random.uniform(0.3, 0.8)])

    def get_game_state_dict(self):
        return {
            'mode_name': self.mode,
            'score': self.score,
            'targets': [d['pos'] for d in self.drones if d['alive']],
            'gates': [g['pos'] for idx, g in enumerate(self.ring_gates) if idx >= self.current_ring_idx]
        }
