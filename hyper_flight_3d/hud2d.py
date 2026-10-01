import pygame
from OpenGL.GL import *
import math

class HUD2D:
    def __init__(self, width=1280, height=720):
        self.width = width
        self.height = height
        self.font_large = pygame.font.SysFont("Consolas", 28, bold=True)
        self.font_medium = pygame.font.SysFont("Consolas", 18, bold=True)
        self.font_small = pygame.font.SysFont("Consolas", 13)

    def resize(self, w, h):
        self.width = max(1, w)
        self.height = max(1, h)

    def begin_ortho(self):
        glDisable(GL_DEPTH_TEST)
        glDisable(GL_LIGHTING)
        glMatrixMode(GL_PROJECTION)
        glPushMatrix()
        glLoadIdentity()
        glOrtho(0, self.width, self.height, 0, -1, 1)
        glMatrixMode(GL_MODELVIEW)
        glPushMatrix()
        glLoadIdentity()

    def end_ortho(self):
        glMatrixMode(GL_PROJECTION)
        glPopMatrix()
        glMatrixMode(GL_MODELVIEW)
        glPopMatrix()
        glEnable(GL_DEPTH_TEST)
        glEnable(GL_LIGHTING)

    def draw_text(self, text, x, y, color=(0, 255, 220), font=None):
        if font is None: font = self.font_medium
        text_surface = font.render(text, True, color)
        text_data = pygame.image.tostring(text_surface, "RGBA", True)
        w, h = text_surface.get_size()

        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        glRasterPos2i(int(x), int(y + h))
        glDrawPixels(w, h, GL_RGBA, GL_UNSIGNED_BYTE, text_data)

    def render_hud(self, player_jet, controller, game_state, fps=60):
        self.begin_ortho()

        cx = self.width / 2.0
        cy = self.height / 2.0

        # 1. Pitch Ladder & Horizon Crosshair (Cyan/Green Neon)
        glColor4f(0.0, 1.0, 0.8, 0.7)
        glLineWidth(2.0)
        
        # Center boresight reticle
        glBegin(GL_LINES)
        glVertex2f(cx - 30, cy); glVertex2f(cx - 10, cy)
        glVertex2f(cx + 10, cy); glVertex2f(cx + 30, cy)
        glVertex2f(cx, cy - 20); glVertex2f(cx, cy - 10)
        glVertex2f(cx - 10, cy); glVertex2f(cx - 10, cy + 8)
        glVertex2f(cx + 10, cy); glVertex2f(cx + 10, cy + 8)
        glEnd()

        # Pitch Ladder Offset based on Pitch angle
        pitch = player_jet.pitch
        roll = player_jet.roll
        pitch_offset = pitch * 4.0

        glPushMatrix()
        glTranslatef(cx, cy, 0)
        glRotatef(-roll, 0, 0, 1)

        glBegin(GL_LINES)
        # Horizon Line
        glVertex2f(-120, pitch_offset)
        glVertex2f(-40, pitch_offset)
        glVertex2f(40, pitch_offset)
        glVertex2f(120, pitch_offset)

        # +15 Pitch line
        glVertex2f(-80, pitch_offset - 60); glVertex2f(-30, pitch_offset - 60)
        glVertex2f(30, pitch_offset - 60);  glVertex2f(80, pitch_offset - 60)
        glVertex2f(-80, pitch_offset - 60); glVertex2f(-80, pitch_offset - 50)
        glVertex2f(80, pitch_offset - 60);  glVertex2f(80, pitch_offset - 50)

        # -15 Pitch line (Dashed)
        glVertex2f(-80, pitch_offset + 60); glVertex2f(-30, pitch_offset + 60)
        glVertex2f(30, pitch_offset + 60);  glVertex2f(80, pitch_offset + 60)
        glVertex2f(-80, pitch_offset + 60); glVertex2f(-80, pitch_offset + 50)
        glVertex2f(80, pitch_offset + 60);  glVertex2f(80, pitch_offset + 50)
        glEnd()

        glPopMatrix()

        # 2. Heading Compass Tape (Top of screen)
        yaw_deg = int(player_jet.yaw) % 360
        comp_y = 40
        glBegin(GL_LINES)
        glColor4f(0.0, 1.0, 0.8, 0.8)
        glVertex2f(cx - 150, comp_y); glVertex2f(cx + 150, comp_y)
        glVertex2f(cx, comp_y); glVertex2f(cx, comp_y - 12)
        glEnd()
        self.draw_text(f"{yaw_deg:03d}°", cx - 18, comp_y - 30, color=(0, 255, 220), font=self.font_large)

        # 3. Airspeed (Left) & Altitude (Right) Goggles
        # Airspeed box
        speed = int(player_jet.speed * 10.0)
        self.draw_text(f"SPD {speed} KTS", cx - 280, cy - 20, color=(0, 255, 120), font=self.font_medium)
        # Altitude box (Z height)
        alt = int(player_jet.pos[1])
        self.draw_text(f"ALT {alt} M", cx + 180, cy - 20, color=(0, 255, 120), font=self.font_medium)

        # 4. Status Bars (Health, Shield, Throttle, Boost)
        bar_x = 30
        bar_y = self.height - 130
        # Health Bar
        self.draw_text(f"HULL INTEGRITY: {int(player_jet.health)}%", bar_x, bar_y - 22, color=(0, 255, 200), font=self.font_small)
        glColor4f(0.1, 0.2, 0.3, 0.8)
        glBegin(GL_QUADS); glVertex2f(bar_x, bar_y); glVertex2f(bar_x + 200, bar_y); glVertex2f(bar_x + 200, bar_y + 12); glVertex2f(bar_x, bar_y + 12); glEnd()
        glColor4f(0.0, 0.9, 0.4, 0.9)
        hp_w = (player_jet.health / 100.0) * 200.0
        glBegin(GL_QUADS); glVertex2f(bar_x, bar_y); glVertex2f(bar_x + hp_w, bar_y); glVertex2f(bar_x + hp_w, bar_y + 12); glVertex2f(bar_x, bar_y + 12); glEnd()

        # Throttle Bar
        self.draw_text(f"THROTTLE: {int(controller.throttle * 100)}%", bar_x, bar_y + 22, color=(255, 200, 0), font=self.font_small)
        glColor4f(0.1, 0.2, 0.3, 0.8)
        glBegin(GL_QUADS); glVertex2f(bar_x, bar_y + 40); glVertex2f(bar_x + 200, bar_y + 40); glVertex2f(bar_x + 200, bar_y + 52); glVertex2f(bar_x, bar_y + 52); glEnd()
        glColor4f(1.0, 0.7, 0.0, 0.9)
        th_w = controller.throttle * 200.0
        glBegin(GL_QUADS); glVertex2f(bar_x, bar_y + 40); glVertex2f(bar_x + th_w, bar_y + 40); glVertex2f(bar_x + th_w, bar_y + 52); glVertex2f(bar_x, bar_y + 52); glEnd()

        # 5. Mini-map / Radar (Top Right corner)
        radar_cx = self.width - 90
        radar_cy = 90
        radar_r = 65

        # Outer Rim
        glColor4f(0.0, 0.8, 1.0, 0.4)
        glBegin(GL_LINE_LOOP)
        for i in range(24):
            ang = (i / 24.0) * 2.0 * math.pi
            glVertex2f(radar_cx + math.cos(ang)*radar_r, radar_cy + math.sin(ang)*radar_r)
        glEnd()
        # Crosshair lines
        glBegin(GL_LINES)
        glVertex2f(radar_cx - radar_r, radar_cy); glVertex2f(radar_cx + radar_r, radar_cy)
        glVertex2f(radar_cx, radar_cy - radar_r); glVertex2f(radar_cx, radar_cy + radar_r)
        glEnd()

        # Player Marker
        glColor3f(0.0, 1.0, 0.0)
        glPointSize(6.0)
        glBegin(GL_POINTS)
        glVertex2f(radar_cx, radar_cy)
        glEnd()

        # Radar Targets (Drones & Gates)
        for target in game_state.get('targets', []):
            dx = (target[0] - player_jet.pos[0]) * 0.03
            dz = (target[2] - player_jet.pos[2]) * 0.03
            if math.sqrt(dx*dx + dz*dz) < radar_r - 5:
                glColor3f(1.0, 0.2, 0.2) # Red enemy dot
                glBegin(GL_POINTS)
                glVertex2f(radar_cx + dx, radar_cy + dz)
                glEnd()

        for gate in game_state.get('gates', []):
            dx = (gate[0] - player_jet.pos[0]) * 0.03
            dz = (gate[2] - player_jet.pos[2]) * 0.03
            if math.sqrt(dx*dx + dz*dz) < radar_r - 5:
                glColor3f(0.0, 0.9, 1.0) # Cyan gate dot
                glBegin(GL_POINTS)
                glVertex2f(radar_cx + dx, radar_cy + dz)
                glEnd()

        # 6. Arduino UNO Telemetry HUD Diagram (Bottom Right)
        ard_x = self.width - 240
        ard_y = self.height - 150
        
        # Telemetry Box Header
        self.draw_text("ARDUINO HARDWARE TELEMETRY", ard_x, ard_y - 25, color=(0, 255, 180), font=self.font_small)
        status_col = (0, 255, 100) if controller.arduino_connected else (255, 150, 0)
        self.draw_text(f"SOURCE: {controller.source_type}", ard_x, ard_y - 10, color=status_col, font=self.font_small)

        # Dual Stick Analog Diagrams
        # Left Stick Box (Pitch/Roll)
        ls_cx = ard_x + 40
        ls_cy = ard_y + 50
        glColor4f(0.0, 0.7, 0.9, 0.4)
        glBegin(GL_LINE_LOOP); glVertex2f(ls_cx - 30, ls_cy - 30); glVertex2f(ls_cx + 30, ls_cy - 30); glVertex2f(ls_cx + 30, ls_cy + 30); glVertex2f(ls_cx - 30, ls_cy + 30); glEnd()
        # Left Stick Puck
        lp_x = ls_cx + controller.roll * 25.0
        lp_y = ls_cy - controller.pitch * 25.0
        glColor3f(0.0, 1.0, 0.5)
        glPointSize(8.0)
        glBegin(GL_POINTS); glVertex2f(lp_x, lp_y); glEnd()
        self.draw_text("JOY 1", ls_cx - 18, ls_cy + 35, color=(200, 200, 200), font=self.font_small)

        # Right Stick Box (Yaw/Throttle)
        rs_cx = ard_x + 150
        rs_cy = ard_y + 50
        glColor4f(0.0, 0.7, 0.9, 0.4)
        glBegin(GL_LINE_LOOP); glVertex2f(rs_cx - 30, rs_cy - 30); glVertex2f(rs_cx + 30, rs_cy - 30); glVertex2f(rs_cx + 30, rs_cy + 30); glVertex2f(rs_cx - 30, rs_cy + 30); glEnd()
        # Right Stick Puck
        rp_x = rs_cx + controller.yaw * 25.0
        rp_y = rs_cy - (controller.throttle - 0.5) * 50.0
        glColor3f(1.0, 0.8, 0.0)
        glPointSize(8.0)
        glBegin(GL_POINTS); glVertex2f(rp_x, rp_y); glEnd()
        self.draw_text("JOY 2", rs_cx - 18, rs_cy + 35, color=(200, 200, 200), font=self.font_small)

        # FPS & Game Mode
        mode_title = game_state.get('mode_name', 'FREE FLIGHT')
        self.draw_text(f"MODE: {mode_title} | FPS: {int(fps)}", 30, 20, color=(255, 255, 255), font=self.font_medium)

        self.end_ortho()
