import os
import math

MODELS_DIR = os.path.join(os.path.dirname(__file__), "assets", "models")
os.makedirs(MODELS_DIR, exist_ok=True)

def generate_jet_obj():
    filename = os.path.join(MODELS_DIR, "jet_fighter.obj")
    lines = ["# 3D Jet Fighter Model\n"]
    
    vertices = [
        # Nose & Cockpit
        (0.0, 0.0, -12.0),     # 1: Nose tip
        (0.0, 1.2, -4.0),      # 2: Cockpit top
        (-1.5, 0.0, -3.0),     # 3: Left intake
        (1.5, 0.0, -3.0),      # 4: Right intake
        (0.0, -1.0, -3.0),     # 5: Nose bottom
        
        # Fuselage
        (0.0, 1.5, 2.0),       # 6: Spine top
        (-1.8, 0.0, 4.0),      # 7: Left fuselage
        (1.8, 0.0, 4.0),       # 8: Right fuselage
        (0.0, -1.2, 4.0),      # 9: Bottom fuselage
        
        # Wings Left
        (-12.0, -0.2, 3.0),    # 10: Left Wingtip front
        (-11.5, -0.2, 7.0),    # 11: Left Wingtip rear
        (-1.8, 0.0, 7.5),      # 12: Left Wing root rear
        
        # Wings Right
        (12.0, -0.2, 3.0),     # 13: Right Wingtip front
        (11.5, -0.2, 7.0),     # 14: Right Wingtip rear
        (1.8, 0.0, 7.5),       # 15: Right Wing root rear

        # Tail Vertical Fins
        (-2.2, 4.5, 8.0),      # 16: Left Vertical tail tip
        (2.2, 4.5, 8.0),       # 17: Right Vertical tail tip
        (0.0, 0.5, 9.5),       # 18: Tail cone tip

        # Engine Exhausts
        (-0.9, 0.0, 9.0),      # 19: Left Engine nozzle
        (0.9, 0.0, 9.0)        # 20: Right Engine nozzle
    ]

    for v in vertices:
        lines.append(f"v {v[0]:.4f} {v[1]:.4f} {v[2]:.4f}\n")

    faces = [
        # Nose cone
        (1, 3, 2), (1, 2, 4), (1, 4, 5), (1, 5, 3),
        # Cockpit canopy to spine
        (2, 3, 7, 6), (2, 6, 8, 4),
        # Wings Left
        (3, 10, 11, 12), (3, 12, 7),
        # Wings Right
        (4, 8, 15, 14), (4, 14, 13),
        # Tail fins
        (6, 16, 18, 12), (6, 15, 18, 17),
        # Engine rear
        (7, 12, 19, 9), (8, 9, 20, 15), (9, 19, 20)
    ]

    for f in faces:
        indices = " ".join(str(idx) for idx in f)
        lines.append(f"f {indices}\n")

    with open(filename, 'w') as out:
        out.writelines(lines)
    print(f"[OBJ Generator] Created {filename}")

def generate_drone_obj():
    filename = os.path.join(MODELS_DIR, "cyber_drone.obj")
    lines = ["# 3D Cyber Combat Drone Model\n"]
    
    s = 4.0
    vertices = [
        (0, s*1.5, 0), (0, -s*1.5, 0),
        (s*1.2, 0, 0), (0, 0, s*1.2), (-s*1.2, 0, 0), (0, 0, -s*1.2),
        (s*2.2, 0, s*2.2), (-s*2.2, 0, s*2.2), (-s*2.2, 0, -s*2.2), (s*2.2, 0, -s*2.2)
    ]

    for v in vertices:
        lines.append(f"v {v[0]:.4f} {v[1]:.4f} {v[2]:.4f}\n")

    faces = [
        (1, 3, 4), (1, 4, 5), (1, 5, 6), (1, 6, 3),
        (2, 4, 3), (2, 5, 4), (2, 6, 5), (2, 3, 6),
        (3, 7, 4), (4, 8, 5), (5, 9, 6), (6, 10, 3)
    ]

    for f in faces:
        indices = " ".join(str(idx) for idx in f)
        lines.append(f"f {indices}\n")

    with open(filename, 'w') as out:
        out.writelines(lines)
    print(f"[OBJ Generator] Created {filename}")

def generate_ring_obj():
    filename = os.path.join(MODELS_DIR, "ring_gate.obj")
    lines = ["# 3D Ring Checkpoint Gate Model\n"]
    
    R = 18.0  # Main radius
    r = 2.0   # Tube radius
    segments_main = 24
    segments_tube = 8

    verts = []
    for i in range(segments_main):
        theta = (i / float(segments_main)) * 2.0 * math.pi
        cx = math.cos(theta) * R
        cy = math.sin(theta) * R
        for j in range(segments_tube):
            phi = (j / float(segments_tube)) * 2.0 * math.pi
            px = cx + math.cos(theta) * math.cos(phi) * r
            py = cy + math.sin(theta) * math.cos(phi) * r
            pz = math.sin(phi) * r
            verts.append((px, py, pz))

    for v in verts:
        lines.append(f"v {v[0]:.4f} {v[1]:.4f} {v[2]:.4f}\n")

    for i in range(segments_main):
        i_next = (i + 1) % segments_main
        for j in range(segments_tube):
            j_next = (j + 1) % segments_tube
            v1 = i * segments_tube + j + 1
            v2 = i_next * segments_tube + j + 1
            v3 = i_next * segments_tube + j_next + 1
            v4 = i * segments_tube + j_next + 1
            lines.append(f"f {v1} {v2} {v3} {v4}\n")

    with open(filename, 'w') as out:
        out.writelines(lines)
    print(f"[OBJ Generator] Created {filename}")

def generate_missile_obj():
    filename = os.path.join(MODELS_DIR, "missile_rocket.obj")
    lines = ["# 3D Homing Missile Model\n"]
    
    vertices = [
        (0.0, 0.0, -8.0),   # 1 Nose tip
        (0.6, 0.6, -4.0),   # 2 Body front R
        (-0.6, 0.6, -4.0),  # 3 Body front L
        (-0.6, -0.6, -4.0), # 4 Body front BL
        (0.6, -0.6, -4.0),  # 5 Body front BR

        (0.6, 0.6, 4.0),    # 6 Body rear R
        (-0.6, 0.6, 4.0),   # 7 Body rear L
        (-0.6, -0.6, 4.0),  # 8 Body rear BL
        (0.6, -0.6, 4.0),   # 9 Body rear BR

        (2.5, 0.0, 5.5),    # 10 Fin Right
        (-2.5, 0.0, 5.5),   # 11 Fin Left
        (0.0, 2.5, 5.5),    # 12 Fin Top
        (0.0, -2.5, 5.5)    # 13 Fin Bottom
    ]

    for v in vertices:
        lines.append(f"v {v[0]:.4f} {v[1]:.4f} {v[2]:.4f}\n")

    faces = [
        (1, 2, 3), (1, 3, 4), (1, 4, 5), (1, 5, 2),
        (2, 6, 7, 3), (3, 7, 8, 4), (4, 8, 9, 5), (5, 9, 6, 2),
        (6, 10, 9), (7, 11, 8), (6, 12, 7), (8, 13, 9)
    ]

    for f in faces:
        indices = " ".join(str(idx) for idx in f)
        lines.append(f"f {indices}\n")

    with open(filename, 'w') as out:
        out.writelines(lines)
    print(f"[OBJ Generator] Created {filename}")

if __name__ == "__main__":
    generate_jet_obj()
    generate_drone_obj()
    generate_ring_obj()
    generate_missile_obj()
