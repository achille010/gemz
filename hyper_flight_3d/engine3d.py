import os
import pygame
from pygame.locals import *
from OpenGL.GL import *
from OpenGL.GLU import *
import numpy as np
import math
import random

from obj_loader import OBJModel

MODELS_DIR = os.path.join(os.path.dirname(__file__), "assets", "models")

class Renderer3D:
    def __init__(self, width=1280, height=720):
        self.width = width
        self.height = height
        self.fov = 70.0
        self.near_clip = 0.5
        self.far_clip = 4000.0

        self.textures = {}
        self.models = {}
        self.init_opengl()
        self.generate_procedural_textures()
        self.load_3d_models()
        self.terrain_mesh = self.build_terrain_mesh(grid_size=60, spacing=40.0)

    def init_opengl(self):
        glViewport(0, 0, self.width, self.height)
        glEnable(GL_DEPTH_TEST)
        glDepthFunc(GL_LEQUAL)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        glShadeModel(GL_SMOOTH)
        glEnable(GL_TEXTURE_2D)
        glEnable(GL_NORMALIZE)

        # Lighting setup
        glEnable(GL_LIGHTING)
        glEnable(GL_LIGHT0)
        glEnable(GL_COLOR_MATERIAL)
        glColorMaterial(GL_FRONT_AND_BACK, GL_AMBIENT_AND_DIFFUSE)

        # Sun / Key Light
        glLightfv(GL_LIGHT0, GL_POSITION, [1000.0, 2000.0, 1000.0, 0.0])
        glLightfv(GL_LIGHT0, GL_DIFFUSE, [1.0, 0.95, 0.85, 1.0])
        glLightfv(GL_LIGHT0, GL_AMBIENT, [0.15, 0.18, 0.3, 1.0])
        glLightfv(GL_LIGHT0, GL_SPECULAR, [1.0, 1.0, 1.0, 1.0])

        # Atmospheric Fog
        glEnable(GL_FOG)
        glFogi(GL_FOG_MODE, GL_EXP2)
        glFogfv(GL_FOG_COLOR, [0.03, 0.05, 0.12, 1.0])
        glFogf(GL_FOG_DENSITY, 0.0007)
        glHint(GL_FOG_HINT, GL_NICEST)

        glClearColor(0.03, 0.05, 0.12, 1.0)

    def resize(self, w, h):
        self.width = max(1, w)
        self.height = max(1, h)
        glViewport(0, 0, self.width, self.height)

    def load_3d_models(self):
        """Loads imported Wavefront .OBJ 3D Model files from assets/models."""
        jet_path = os.path.join(MODELS_DIR, "jet_fighter.obj")
        drone_path = os.path.join(MODELS_DIR, "cyber_drone.obj")
        ring_path = os.path.join(MODELS_DIR, "ring_gate.obj")
        missile_path = os.path.join(MODELS_DIR, "missile_rocket.obj")

        if os.path.exists(jet_path):
            self.models['jet'] = OBJModel(jet_path, color=(0.15, 0.8, 1.0), scale=1.0)
        if os.path.exists(drone_path):
            self.models['drone'] = OBJModel(drone_path, color=(0.9, 0.1, 0.2), scale=1.0)
        if os.path.exists(ring_path):
            self.models['ring'] = OBJModel(ring_path, color=(0.0, 0.9, 1.0), scale=1.0)
        if os.path.exists(missile_path):
            self.models['missile'] = OBJModel(missile_path, color=(1.0, 0.5, 0.0), scale=0.8)

        print(f"[Renderer3D] Loaded {len(self.models)} external 3D OBJ models!")

    def generate_procedural_textures(self):
        grid_img = np.zeros((256, 256, 4), dtype=np.uint8)
        grid_img[:, :, 0] = 10; grid_img[:, :, 1] = 30; grid_img[:, :, 2] = 60; grid_img[:, :, 3] = 255
        grid_img[0:4, :, :] = [0, 240, 255, 255]
        grid_img[:, 0:4, :] = [0, 240, 255, 255]
        grid_img[126:130, :, :] = [180, 0, 255, 255]
        grid_img[:, 126:130, :] = [180, 0, 255, 255]
        self.textures['grid'] = self.load_opengl_texture(grid_img)

    def load_opengl_texture(self, img_array):
        tex_id = glGenTextures(1)
        glBindTexture(GL_TEXTURE_2D, tex_id)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR_MIPMAP_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_REPEAT)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_REPEAT)
        gluBuild2DMipmaps(GL_TEXTURE_2D, GL_RGBA, img_array.shape[1], img_array.shape[0], GL_RGBA, GL_UNSIGNED_BYTE, img_array.tobytes())
        return tex_id

    def build_terrain_mesh(self, grid_size=60, spacing=40.0):
        half = grid_size // 2
        def get_height(x, y):
            dist = math.sqrt(x*x + y*y)
            h = math.sin(x * 0.005) * math.cos(y * 0.005) * 200.0 + math.sin(x * 0.015 + y * 0.01) * 80.0
            if dist < 400.0: h *= (dist / 400.0) ** 2
            return h

        mesh_quads = []
        for i in range(grid_size - 1):
            for j in range(grid_size - 1):
                x0 = (i - half) * spacing; y0 = (j - half) * spacing
                x1 = (i + 1 - half) * spacing; y1 = (j + 1 - half) * spacing

                z00 = get_height(x0, y0); z10 = get_height(x1, y0)
                z11 = get_height(x1, y1); z01 = get_height(x0, y1)

                p00 = (x0, z00, y0); p10 = (x1, z10, y0); p11 = (x1, z11, y1); p01 = (x0, z01, y1)

                v1 = np.array([spacing, z10 - z00, 0.0])
                v2 = np.array([0.0, z01 - z00, spacing])
                norm = np.cross(v2, v1)
                n_len = np.linalg.norm(norm)
                if n_len > 0: norm = norm / n_len
                else: norm = np.array([0.0, 1.0, 0.0])

                mesh_quads.append({
                    'pts': [p00, p10, p11, p01],
                    'norm': norm.tolist(),
                    'uvs': [(i*0.2, j*0.2), ((i+1)*0.2, j*0.2), ((i+1)*0.2, (j+1)*0.2), (i*0.2, (j+1)*0.2)],
                    'avg_z': (z00 + z10 + z11 + z01) * 0.25
                })
        return mesh_quads

    def setup_perspective(self, pos, yaw, pitch, roll):
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        gluPerspective(self.fov, self.width / float(self.height), self.near_clip, self.far_clip)

        glMatrixMode(GL_MODELVIEW)
        glLoadIdentity()

        glRotatef(-roll, 0.0, 0.0, 1.0)
        glRotatef(-pitch, 1.0, 0.0, 0.0)
        glRotatef(-yaw, 0.0, 1.0, 0.0)
        glTranslatef(-pos[0], -pos[1], -pos[2])

    def render_skybox(self, camera_pos):
        glPushMatrix()
        glTranslatef(camera_pos[0], camera_pos[1], camera_pos[2])
        glDisable(GL_LIGHTING)
        glDisable(GL_DEPTH_TEST)

        glBegin(GL_TRIANGLE_FAN)
        glColor3f(0.02, 0.03, 0.1)
        glVertex3f(0, 1500, 0)
        radius = 2000.0
        segments = 16
        for i in range(segments + 1):
            angle = (i / float(segments)) * 2.0 * math.pi
            x = math.cos(angle) * radius
            z = math.sin(angle) * radius
            glColor3f(0.15, 0.05, 0.25)
            glVertex3f(x, 0, z)
        glEnd()

        glEnable(GL_DEPTH_TEST)
        glEnable(GL_LIGHTING)
        glPopMatrix()

    def render_terrain(self, player_pos):
        glPushMatrix()
        glEnable(GL_TEXTURE_2D)
        glBindTexture(GL_TEXTURE_2D, self.textures['grid'])

        glBegin(GL_QUADS)
        for quad in self.terrain_mesh:
            glNormal3fv(quad['norm'])
            avg_h = quad['avg_z']
            h_ratio = max(0.0, min(1.0, (avg_h + 100.0) / 300.0))
            r_col = 0.05 + 0.7 * h_ratio
            g_col = 0.2 + 0.3 * (1.0 - h_ratio)
            b_col = 0.4 + 0.6 * h_ratio
            glColor3f(r_col, g_col, b_col)

            for idx in range(4):
                glTexCoord2fv(quad['uvs'][idx])
                glVertex3fv(quad['pts'][idx])
        glEnd()
        glPopMatrix()

    def draw_player_jet(self, pos, rot, speed_ratio=0.0):
        """Renders imported 3D Jet Fighter OBJ Model."""
        glDisable(GL_TEXTURE_2D)
        if 'jet' in self.models:
            self.models['jet'].render(pos=pos, rot=rot, override_color=(0.15, 0.85, 1.0))
        glEnable(GL_TEXTURE_2D)

    def draw_ring_gate(self, pos, radius=15.0, active=True, time_anim=0.0):
        """Renders imported 3D Torus Ring Gate OBJ Model."""
        glDisable(GL_TEXTURE_2D)
        col = (0.0, 0.9, 1.0) if active else (0.4, 0.4, 0.4)
        if 'ring' in self.models:
            self.models['ring'].render(pos=pos, rot=(0, time_anim * 30.0, 0), override_color=col)
        glEnable(GL_TEXTURE_2D)

    def draw_enemy_drone(self, pos, rot, health=100.0, time_anim=0.0):
        """Renders imported 3D Cyber Combat Drone OBJ Model."""
        glDisable(GL_TEXTURE_2D)
        if 'drone' in self.models:
            self.models['drone'].render(pos=pos, rot=(rot[0], rot[1] + time_anim*45.0, 0), override_color=(0.9, 0.1, 0.2))
        glEnable(GL_TEXTURE_2D)

    def draw_laser(self, start_pos, end_pos, color=(0.0, 1.0, 0.8)):
        glDisable(GL_LIGHTING)
        glDisable(GL_TEXTURE_2D)
        glColor3fv(color)
        glLineWidth(4.0)
        glBegin(GL_LINES)
        glVertex3fv(start_pos)
        glVertex3fv(end_pos)
        glEnd()
        glLineWidth(1.0)
        glEnable(GL_LIGHTING)

    def draw_particles(self, particles):
        glDisable(GL_LIGHTING)
        glDisable(GL_TEXTURE_2D)
        glPointSize(4.0)
        glBegin(GL_POINTS)
        for p in particles:
            glColor4f(p[6], p[7], p[8], p[9])
            glVertex3f(p[0], p[1], p[2])
        glEnd()
        glEnable(GL_LIGHTING)
