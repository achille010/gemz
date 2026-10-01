# HYPER FLIGHT 3D - SKYBOUND NEXUS
> **Hyper-Realistic 3D Jet Flight & Cyber Combat Simulator** built with **Pygame**, **PyOpenGL**, procedural audio, dynamic heightmap terrain, particle physics, and **Lab-Made Arduino UNO Dual-Joystick Gamepad Support**.

---

## 🚀 Key Features

- **True 3D Plane Coordinate Space (X, Y, Z)**:
  - Dynamic 6-DOF flight camera (Pitch, Roll, Yaw, X, Y, Z translations).
  - 1st Person Cockpit View and 3rd Person Aerobatic Chase View.
  - Realistic pitch ladder horizon display, altitude gauge, speed tape, lock-on target reticle, and mini-map radar.

- **Hyper-Realistic Visual Engine**:
  - Procedurally generated 3D mountain landscape heightmap with altitude-gradient color shading.
  - Detailed 3D Jet Fighter model with stealth canopy, wingtip navigation beacons, and dynamic engine afterburner plumes.
  - Dynamic sun lighting, specular highlights, and atmospheric cyber haze fog.
  - 3D Sci-Fi Torus Ring Checkpoints with animated glowing energy pulse shields.
  - Enemy Octahedron Combat Drones with rotating energy cores and red targeting lasers.
  - 3D Explosions, missile particle smoke trails, plasma laser bolts, and sonic boom shockwaves.

- **Lab-Made Gamepad Support (Arduino UNO + Dual Joysticks)**:
  - Dedicated Arduino firmware sketch (`arduino_gamepad.ino`) streaming at 115200 Baud over USB serial.
  - Background serial parser thread with auto-detect COM port scanning, deadzone filtering, and neutral center calibration.
  - Live hardware telemetry HUD diagram displaying Left & Right analog stick puck positions and button states in real-time!
  - 3-tier fallback architecture: **Arduino UNO Gamepad** ➔ **USB Xbox/PlayStation Controller** ➔ **Keyboard/Mouse**.

- **Procedural Sound Engine**:
  - Built-in real-time audio synthesizer generating jet engine turbine roars, laser blasts, homing missile launches, explosion booms, and ring chimes without requiring external audio files.

---

## 🔌 Hardware Wiring Diagram (Arduino UNO + 2 Joysticks)

Connect two standard analog joysticks (VRX, VRY, SW) and optional buttons to your Arduino UNO:

```
               ARDUINO UNO PINOUT WIRING
               =========================
  LEFT JOYSTICK (Flight Pitch & Roll):
    - VRX  --> Analog Pin A0  (Roll Axis)
    - VRY  --> Analog Pin A1  (Pitch Axis - Inverted flight pitch)
    - SW   --> Digital Pin D2  (Left Stick Button)

  RIGHT JOYSTICK (Yaw Rudder & Throttle):
    - VRX  --> Analog Pin A2  (Yaw Rudder Axis)
    - VRY  --> Analog Pin A3  (Engine Throttle Axis)
    - SW   --> Digital Pin D3  (Right Stick Button / Cam Switch)

  EXTERNAL PUSH BUTTONS / TRIGGERS:
    - Button 1 (Fire Plasma Laser)    --> Digital Pin D4 (Active LOW)
    - Button 2 (Launch Homing Missile)--> Digital Pin D5 (Active LOW)
    - Button 3 (Afterburner Boost)    --> Digital Pin D6 (Active LOW)

  POWER CONNECTIONS:
    - Connect VCC of both Joysticks to 5V on Arduino
    - Connect GND of all Joysticks and Buttons to GND on Arduino
```

---

## 🎮 Game Controls Summary

| Action | Arduino UNO | USB Gamepad | Keyboard & Mouse |
| :--- | :--- | :--- | :--- |
| **Pitch Nose Up/Down** | Left Joystick Y (A1) | Left Analog Y | `W` / `S` or `UP` / `DOWN` |
| **Roll Wings Left/Right**| Left Joystick X (A0) | Left Analog X | `A` / `D` or `LEFT` / `RIGHT` |
| **Yaw Rudder** | Right Joystick X (A2)| Right Analog X | `Q` / `E` |
| **Throttle Speed** | Right Joystick Y (A3)| Right Analog Y | `LShift` (Up) / `LCtrl` (Down) |
| **Fire Plasma Laser** | Button D4 | Button A / Trigger | `SPACE` or Left Mouse Click |
| **Launch Homing Missile**| Button D5 | Button B | `F` or Right Mouse Click |
| **Afterburner Boost** | Button D6 | Button X / RB | `TAB` or `Shift` |
| **Switch Camera View** | Right Stick SW (D3) | Button Y | `C` (Toggle 1st / 3rd Person) |
| **Pause Menu** | - | Start Button | `ESC` |

---

## 🛠️ How to Setup and Play

### 1. Requirements
Ensure Python 3.9+ and the required packages are installed:
```bash
pip install pygame PyOpenGL PyOpenGL_accelerate numpy pyserial pillow pyrr
```

### 2. Upload Arduino Firmware (Optional if using physical Arduino)
1. Open `arduino_gamepad.ino` in the Arduino IDE.
2. Select **Arduino UNO** board and your COM port.
3. Upload the sketch. The serial monitor will output `JOY:LX,LY,SW1,RX,RY,SW2,B1,B2,B3` at 115200 baud.

### 3. Launch the Game
Run `main.py` from the project directory:
```bash
python main.py
```

---

## 📂 Project Architecture

```
hyper_flight_3d/
├── main.py                # Main application launcher, window creation & state machine
├── arduino_gamepad.ino    # Arduino UNO C++ firmware sketch for dual joysticks & buttons
├── controller.py          # Input manager (Arduino Serial + USB Gamepad + Keyboard fallback)
├── engine3d.py            # OpenGL 3D renderer (Terrain mesh, Jet model, Skybox, Lighting, Fog)
├── hud2d.py               # 2D Heads-Up Display (Pitch ladder, Airspeed, Radar, Arduino Telemetry)
├── gameplay.py            # Flight physics, AI combat drones, ring checkpoints, particles
└── audio_synth.py         # Real-time procedural audio synthesizer (Engine, Lasers, Explosions)
```

---
*Created with Pygame & PyOpenGL.*
