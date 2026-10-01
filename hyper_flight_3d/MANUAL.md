# HYPER FLIGHT 3D - Manual & Flight Guide

A hyper-realistic 3D jet flight & combat simulator built with Pygame, NumPy, procedural audio synthesis, 3D perspective projection, and dedicated **Lab-Made Arduino Dual-Joystick Gamepad Support**.

---------------------------------------------------------------------------------------------

## 1. Quick Start (Windows)

1. Open a terminal in this folder (`hyper_flight_3d`) and install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Double-click **`play.bat`** or run:
   ```bash
   python hyper_flight_3d.py
   ```
   *(Or `python main.py`)*

3. Test your connected Gamepad or Arduino input by double-clicking **`gamepad_test.bat`** or running:
   ```bash
   python hyper_flight_3d.py --joytest
   ```

---

## 2. Flight Dynamics & Aerodynamics

The jet fighter is governed by real 6-DOF (Six Degrees of Freedom) flight mechanics in 3D coordinate space `(X, Y, Z)`:
- **Pitch Nose Up / Down** (`W` / `S` or Left Joystick Y) rotates the aircraft around its transverse axis.
- **Roll Wings Left / Right** (`A` / `D` or Left Joystick X) banks the wings into high-G turns.
- **Yaw Rudder** (`Q` / `E` or Right Joystick X) adjusts heading left or right.
- **Engine Throttle** (`Shift` / `Ctrl` or Right Joystick Y) controls forward speed and rotor thrust.
- **Afterburner Boost**: Grants +80% burst speed with fiery engine exhaust plumes!

---

## 3. Controls Reference

| Action | Keyboard / Mouse | USB Gamepad | Arduino UNO Dual-Stick Pad |
| :--- | :--- | :--- | :--- |
| **Pitch Nose Up/Down** | `W` / `S` or `UP` / `DOWN` | Left Stick Y | **Left Stick Y** (`Pin A1`) |
| **Roll Wings Left/Right** | `A` / `D` or `LEFT` / `RIGHT` | Left Stick X | **Left Stick X** (`Pin A0`) |
| **Yaw Rudder** | `Q` / `E` | Right Stick X | **Right Stick X** (`Pin A2`) |
| **Engine Throttle** | `Shift` (Up) / `Ctrl` (Down) | Right Stick Y | **Right Stick Y** (`Pin A3`) |
| **Fire Plasma Laser** | `SPACE` or Left Click | Button A / Trigger | **Button 1** (`Pin D4`) |
| **Launch Homing Missile** | `F` or Right Click | Button B | **Button 2** (`Pin D5`) |
| **Afterburner Boost** | `TAB` or `LShift` | Button X / RB | **Button 3** (`Pin D6`) |
| **Camera View Switch** | `C` (1st / 3rd Person) | Button Y | **Right Stick Click** (`Pin D3`) |
| **Pause Game** | `ESC` | Start Button | - |

---

## 4. Missions & Game Modes

1. **TARGET ASSAULT (Combat)**:
   - Engage AI-controlled cyber octahedron drones in 3D aerial dogfights.
   - Destroy enemy drones with plasma lasers and 3D homing missiles before timer expires.

2. **RING APEX RACE (Checkpoint Sprint)**:
   - Fly through sequential 3D Torus ring gates floating across mountain canyons.
   - Maintain high airspeed and clear consecutive rings for time bonuses and combo multipliers.

3. **FREE FLIGHT (Sandbox)**:
   - No timer, no high score pressure. Cruise over 3D terrain, mountain ridges, and practice aerobatic maneuvers.

4. **ARDUINO GAMEPAD CALIBRATION**:
   - Live hardware test mode displaying real-time raw analog values (`A0-A3`) and digital pin states (`D2-D6`) with deadzone zero calibration.

---

## 5. Lab-Made Arduino Gamepad Setup

### Wiring Diagram (Arduino UNO / Nano / Mega)
```
  LEFT JOYSTICK (Pitch & Roll):
    VRx  --> Analog Pin A0
    VRy  --> Analog Pin A1
    SW   --> Digital Pin D2 (Active LOW)

  RIGHT JOYSTICK (Yaw & Throttle):
    VRx  --> Analog Pin A2
    VRy  --> Analog Pin A3
    SW   --> Digital Pin D3 (Active LOW)

  EXTRA PUSH BUTTONS:
    Fire Laser     --> Digital Pin D4
    Launch Missile --> Digital Pin D5
    Boost Engine   --> Digital Pin D6

  POWER:
    VCC --> 5V on Arduino
    GND --> GND on Arduino
```

### Flashing Firmware
- **Option A (Serial Mode)**: Upload `arduino/hyper_flight_serial/hyper_flight_serial.ino` to any Arduino (UNO, Nano, Mega, ESP32). Connect via USB and start with `python hyper_flight_3d.py --serial COM3`.
- **Option B (Native USB HID Mode)**: Upload `arduino/hyper_flight_hid/hyper_flight_hid.ino` to Leonardo, Micro, or Pro Micro. Shows up directly as a standard USB Gamepad!

---
*HYPER FLIGHT 3D - Created with Pygame & NumPy.*
