import pygame
import threading
import time

try:
    import serial
    import serial.tools.list_ports
    HAS_SERIAL = True
except ImportError:
    HAS_SERIAL = False

class ControllerManager:
    def __init__(self):
        # Axis inputs normalized [-1.0, 1.0]
        self.roll = 0.0      # Left/Right roll (Left Stick X)
        self.pitch = 0.0     # Nose Pitch up/down (Left Stick Y)
        self.yaw = 0.0       # Rudder Yaw left/right (Right Stick X)
        self.throttle = 0.5  # Throttle [0.0, 1.0] (Right Stick Y or buttons)
        
        # Digital Action States
        self.btn_fire = False
        self.btn_missile = False
        self.btn_boost = False
        self.btn_lock = False
        self.btn_cam = False

        # Input Source Status
        self.source_type = "Keyboard/Mouse"  # "Arduino UNO", "USB Gamepad", "Keyboard/Mouse"
        self.arduino_port = None
        self.arduino_connected = False
        self.arduino_thread = None
        self.running = True

        # Arduino raw telemetry debug values
        self.raw_lx = 512
        self.raw_ly = 512
        self.raw_rx = 512
        self.raw_ry = 512
        self.raw_sw1 = 0
        self.raw_sw2 = 0
        self.raw_b1 = 0
        self.raw_b2 = 0
        self.raw_b3 = 0

        # Deadzone & Calibration
        self.deadzone = 0.08
        self.center_lx = 512
        self.center_ly = 512
        self.center_rx = 512
        self.center_ry = 512

        # USB Joystick setup
        self.pygame_joystick = None
        self.init_pygame_joystick()

        # Try connecting to Arduino serial
        if HAS_SERIAL:
            self.start_arduino_thread()

    def init_pygame_joystick(self):
        pygame.joystick.init()
        if pygame.joystick.get_count() > 0:
            try:
                self.pygame_joystick = pygame.joystick.Joystick(0)
                self.pygame_joystick.init()
                self.source_type = f"USB: {self.pygame_joystick.get_name()}"
                print(f"[Controller] Initialized USB Joystick: {self.pygame_joystick.get_name()}")
            except Exception as e:
                print(f"[Controller] Error initializing USB joystick: {e}")

    def scan_arduino_ports(self):
        if not HAS_SERIAL:
            return None
        ports = serial.tools.list_ports.comports()
        for port in ports:
            # Check for standard Arduino hardware descriptors or CH340/FTDI/USB Serial
            desc = port.description.lower()
            if any(k in desc for k in ['arduino', 'ch340', 'ft232', 'usb serial', 'com']):
                return port.device
        if len(ports) > 0:
            return ports[0].device
        return None

    def start_arduino_thread(self):
        self.arduino_thread = threading.Thread(target=self._arduino_worker, daemon=True)
        self.arduino_thread.start()

    def _arduino_worker(self):
        while self.running:
            if not self.arduino_connected:
                port_name = self.scan_arduino_ports()
                if port_name:
                    try:
                        ser = serial.Serial(port_name, 115200, timeout=1.0)
                        time.sleep(1.5)  # Allow Arduino reset after serial connect
                        self.arduino_port = port_name
                        self.arduino_connected = True
                        self.source_type = f"Arduino UNO ({port_name})"
                        print(f"[Controller] Arduino connected on {port_name}!")
                        
                        while self.running and self.arduino_connected:
                            line = ser.readline().decode('ascii', errors='ignore').strip()
                            if line.startswith("JOY:"):
                                parts = line[4:].split(',')
                                if len(parts) >= 9:
                                    try:
                                        self.raw_lx = int(parts[0])
                                        self.raw_ly = int(parts[1])
                                        self.raw_sw1 = int(parts[2])
                                        self.raw_rx = int(parts[3])
                                        self.raw_ry = int(parts[4])
                                        self.raw_sw2 = int(parts[5])
                                        self.raw_b1 = int(parts[6])
                                        self.raw_b2 = int(parts[7])
                                        self.raw_b3 = int(parts[8])
                                    except ValueError:
                                        pass
                    except Exception as e:
                        self.arduino_connected = False
                        self.arduino_port = None
                        if self.pygame_joystick:
                            self.source_type = f"USB Gamepad"
                        else:
                            self.source_type = "Keyboard/Mouse"
            time.sleep(1.0)

    def apply_deadzone(self, val):
        if abs(val) < self.deadzone:
            return 0.0
        sign = 1.0 if val > 0 else -1.0
        return sign * (abs(val) - self.deadzone) / (1.0 - self.deadzone)

    def update(self, dt):
        # 1. Process Arduino Input if connected
        if self.arduino_connected:
            # Map raw analog (0..1023) with calibrated centers to [-1.0, 1.0]
            norm_lx = (self.raw_lx - self.center_lx) / 512.0
            norm_ly = (self.raw_ly - self.center_ly) / 512.0
            norm_rx = (self.raw_rx - self.center_rx) / 512.0
            norm_ry = (self.raw_ry - self.center_ry) / 512.0

            self.roll = self.apply_deadzone(norm_lx)
            self.pitch = self.apply_deadzone(-norm_ly)  # Inverted Y for aircraft flight pitch
            self.yaw = self.apply_deadzone(norm_rx)

            # Throttle adjustments from Right Stick Y
            ry_val = self.apply_deadzone(-norm_ry)
            if abs(ry_val) > 0.05:
                self.throttle = max(0.0, min(1.0, self.throttle + ry_val * dt * 0.8))

            # Buttons
            self.btn_fire = bool(self.raw_b1)
            self.btn_missile = bool(self.raw_b2)
            self.btn_boost = bool(self.raw_b3)
            self.btn_lock = bool(self.raw_sw1)
            self.btn_cam = bool(self.raw_sw2)
            return

        # 2. Process USB Gamepad if available
        if self.pygame_joystick:
            try:
                num_axes = self.pygame_joystick.get_numaxes()
                if num_axes >= 4:
                    self.roll = self.apply_deadzone(self.pygame_joystick.get_axis(0))
                    self.pitch = self.apply_deadzone(-self.pygame_joystick.get_axis(1))
                    self.yaw = self.apply_deadzone(self.pygame_joystick.get_axis(2))
                    ry = self.apply_deadzone(-self.pygame_joystick.get_axis(3))
                    if abs(ry) > 0.05:
                        self.throttle = max(0.0, min(1.0, self.throttle + ry * dt * 0.8))

                # Buttons
                num_btns = self.pygame_joystick.get_numbuttons()
                if num_btns >= 4:
                    self.btn_fire = self.pygame_joystick.get_button(0)
                    self.btn_missile = self.pygame_joystick.get_button(1)
                    self.btn_boost = self.pygame_joystick.get_button(2)
                    self.btn_cam = self.pygame_joystick.get_button(3)
                return
            except Exception:
                pass

        # 3. Process Keyboard & Mouse input fallback
        keys = pygame.key.get_pressed()

        # Keyboard Pitch/Roll/Yaw controls
        target_roll = 0.0
        target_pitch = 0.0
        target_yaw = 0.0

        if keys[pygame.K_a] or keys[pygame.K_LEFT]:
            target_roll -= 1.0
        if keys[pygame.K_d] or keys[pygame.K_RIGHT]:
            target_roll += 1.0
        if keys[pygame.K_w] or keys[pygame.K_UP]:
            target_pitch += 1.0  # Nose pitch up
        if keys[pygame.K_s] or keys[pygame.K_DOWN]:
            target_pitch -= 1.0  # Nose pitch down
        if keys[pygame.K_q]:
            target_yaw -= 1.0
        if keys[pygame.K_e]:
            target_yaw += 1.0

        # Mouse motion smoothing
        rel_x, rel_y = pygame.mouse.get_rel()
        if pygame.mouse.get_focused() and pygame.mouse.get_pressed()[0]:
            target_roll += rel_x * 0.03
            target_pitch -= rel_y * 0.03

        # Throttle adjustments (Shift / Ctrl or W/S alternate)
        if keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT] or keys[pygame.K_KP_PLUS]:
            self.throttle = min(1.0, self.throttle + dt * 0.5)
        if keys[pygame.K_LCTRL] or keys[pygame.K_RCTRL] or keys[pygame.K_KP_MINUS]:
            self.throttle = max(0.0, self.throttle - dt * 0.5)

        # Smooth interpolation for keyboard control responsiveness
        self.roll += (target_roll - self.roll) * min(1.0, dt * 10.0)
        self.pitch += (target_pitch - self.pitch) * min(1.0, dt * 10.0)
        self.yaw += (target_yaw - self.yaw) * min(1.0, dt * 10.0)

        # Action Buttons
        self.btn_fire = keys[pygame.K_SPACE] or pygame.mouse.get_pressed()[0]
        self.btn_missile = keys[pygame.K_f] or pygame.mouse.get_pressed()[2]
        self.btn_boost = keys[pygame.K_TAB] or keys[pygame.K_LSHIFT]
        self.btn_lock = keys[pygame.K_r]
        self.btn_cam = keys[pygame.K_c]

    def calibrate_centers(self):
        """Sets current analog values as joystick neutral centers."""
        self.center_lx = self.raw_lx
        self.center_ly = self.raw_ly
        self.center_rx = self.raw_rx
        self.center_ry = self.raw_ry
        print(f"[Controller] Calibrated neutral centers: LX={self.center_lx}, LY={self.center_ly}, RX={self.center_rx}, RY={self.center_ry}")

    def close(self):
        self.running = False
