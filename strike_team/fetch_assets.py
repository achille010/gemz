"""Downloads the real 3D assets STRIKE TEAM uses (all free / CC0 unless noted) into the Godot project.

    python fetch_assets.py            download everything missing
    python fetch_assets.py --sizes    only print what it would download

Sources
  * Poly Haven (polyhaven.com, CC0): photoscanned models, PBR textures, HDRI skies
  * three.js examples (github.com/mrdoob/three.js): Soldier.glb + Michelle.glb (Mixamo characters, animated)
  * Google Fonts (OFL): Rajdhani, Teko
Models / textures go to godot/models, godot/textures, godot/sky, fonts to godot/fonts (+ copies for the launcher).
"""
import json
import os
import shutil
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
GD = os.path.join(HERE, "godot")
RES = "1k"                    # texture resolution: 1k keeps two split-screen views fast

# game name -> Poly Haven model id
MODELS = {
    # weapons & pickups
    "rifle": "bolt_action_rifle_7_62", "pistol": "service_pistol", "ammo": "ammo_box", "medkit": "medical_box",
    "mil_crate": "wooden_military_crate", "old_crate": "old_military_crate", "grenade": "stick_grenade",
    # objectives
    "laptop": "classic_laptop", "radio": "vintage_radio_transceiver", "desk": "metal_office_desk",
    "generator": "portable_generator", "propane": "propane_tank", "lpg": "small_lpg_tank", "toolchest": "metal_tool_chest",
    "searchlight": "portable_searchlight",
    # cover & street props
    "barrier": "concrete_road_barrier", "barrier2": "concrete_road_barrier_02", "barrel1": "Barrel_01",
    "barrel2": "Barrel_02", "barrel3": "barrel_03", "crate1": "wooden_crate_01", "crate2": "wooden_crate_02",
    "tyre": "old_tyre", "car": "covered_car", "jerrycan": "metal_jerrycan", "cement": "cement_bag",
    "trashcan": "metal_trash_can", "utility": "utility_box_01", "lamp": "street_lamp_01", "hydrant": "fire_hydrant",
    "wood_barrels": "wooden_barrels_01", "cardboard": "cardboard_box_01",
    # nature
    # (pine_tree_01 / fir_tree_01 / jacaranda_tree are 0.5-1 GB film scans - far too heavy for a game;
    #  these smaller scans are simplified to game budgets by godot/tools/optimize.gd)
    "pine": "pine_sapling_small", "fir": "fir_sapling", "tree": "island_tree_02", "quiver": "quiver_tree_01",
    "fern": "fern_02", "grass2": "grass_medium_02", "shrub4": "shrub_03", "dead_tree": "dead_tree_trunk",
    "shrub1": "shrub_01", "shrub2": "shrub_02", "shrub3": "shrub_04", "grass": "grass_medium_01",
    "boulder": "boulder_01", "boulder2": "namaqualand_boulder_02", "boulder3": "namaqualand_boulder_05",
    "rocks_moss": "rock_moss_set_01", "cliff": "namaqualand_cliff_01",
}

# game name -> Poly Haven texture id (diffuse + normal + roughness)
TEXTURES = {
    "grass": "leafy_grass", "grass_dry": "dry_ground_01", "forest": "forest_ground_04", "rock": "rock_face",
    "rock2": "rocky_terrain_02", "sand": "aerial_sand", "snow": "snow_02", "dirt": "dirt",
    "asphalt": "asphalt_02", "pavement": "concrete_pavement", "gravel": "gravel_floor",
    "brick": "red_brick_03", "plaster": "beige_wall_001", "concrete": "concrete_wall_008",
    "plaster2": "plastered_wall_04", "yellow": "yellow_plaster", "clay": "clay_plaster",
    "facade": "rectangular_facade_tiles", "metal": "corrugated_iron", "container": "container_side",
    "roof": "concrete_floor_02", "white": "white_plaster_02", "stone": "stone_wall",
}

HDRIS = {
    "day_1": "kloofendal_43d_clear_puresky", "day_2": "kloofendal_48d_partly_cloudy_puresky",
    "day_3": "syferfontein_18d_clear_puresky", "dusk_1": "qwantani_dusk_2_puresky",
    "dusk_2": "industrial_sunset_02_puresky", "night_1": "qwantani_night_puresky",
    "overcast_1": "kloofendal_overcast_puresky", "snow_1": "snow_field_2_puresky",
}

DIRECT = {
    "characters/soldier.glb": "https://raw.githubusercontent.com/mrdoob/three.js/dev/examples/models/gltf/Soldier.glb",
    "characters/michelle.glb": "https://raw.githubusercontent.com/mrdoob/three.js/dev/examples/models/gltf/Michelle.glb",
    "fonts/Rajdhani-Bold.ttf": "https://raw.githubusercontent.com/google/fonts/main/ofl/rajdhani/Rajdhani-Bold.ttf",
    "fonts/Rajdhani-SemiBold.ttf": "https://raw.githubusercontent.com/google/fonts/main/ofl/rajdhani/Rajdhani-SemiBold.ttf",
    "fonts/Rajdhani-Medium.ttf": "https://raw.githubusercontent.com/google/fonts/main/ofl/rajdhani/Rajdhani-Medium.ttf",
    "fonts/Teko.ttf": "https://raw.githubusercontent.com/google/fonts/main/ofl/teko/Teko%5Bwght%5D.ttf",
}

UA = {"User-Agent": "strike-team-asset-fetch/1.0"}


def api(path):
    with urllib.request.urlopen(urllib.request.Request("https://api.polyhaven.com/" + path, headers=UA), timeout=60) as r:
        return json.load(r)


def jobs():
    out = []                                       # (dest, url, size)
    for name, pid in MODELS.items():
        f = api("files/" + pid)["gltf"]
        res = RES if RES in f else sorted(f)[0]
        g = f[res]["gltf"]
        base = os.path.join(GD, "models", name)
        out.append((os.path.join(base, name + ".gltf"), g["url"], g["size"]))
        for rel, inc in g.get("include", {}).items():
            out.append((os.path.join(base, rel), inc["url"], inc["size"]))
    for name, pid in TEXTURES.items():
        f = api("files/" + pid)
        for kind, key in (("diff", "Diffuse"), ("nor", "nor_gl"), ("rough", "Rough")):
            if key not in f:
                continue
            e = f[key][RES]["jpg"] if "jpg" in f[key][RES] else f[key][RES]["png"]
            ext = os.path.splitext(e["url"])[1]
            out.append((os.path.join(GD, "textures", name, kind + ext), e["url"], e["size"]))
    for name, pid in HDRIS.items():
        e = api("files/" + pid)["hdri"]["2k"]["hdr"]
        out.append((os.path.join(GD, "sky", name + ".hdr"), e["url"], e["size"]))
    for rel, url in DIRECT.items():
        out.append((os.path.join(GD, rel), url, 0))
    return out


def fetch(job):
    dest, url, _ = job
    if os.path.exists(dest) and os.path.getsize(dest) > 0:
        return 0
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    tmp = dest + ".part"
    for attempt in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=600) as r, open(tmp, "wb") as f:
                shutil.copyfileobj(r, f, 1 << 20)
            os.replace(tmp, dest)
            return os.path.getsize(dest)
        except Exception as e:
            print(f"  retry {attempt + 1} {os.path.basename(dest)}: {e}")
    raise RuntimeError("download failed: " + url)


def main():
    js = jobs()
    total = sum(s for _, _, s in js)
    print(f"{len(js)} files, ~{total / 1e6:.0f} MB (plus characters / fonts)")
    if "--sizes" in sys.argv:
        per = {}
        for d, _, s in js:
            k = os.path.relpath(d, GD).split(os.sep)[:2]
            per["/".join(k)] = per.get("/".join(k), 0) + s
        for k, v in sorted(per.items(), key=lambda kv: -kv[1]):
            print(f"{v / 1e6:8.1f} MB  {k}")
        return
    done = 0
    with ThreadPoolExecutor(8) as ex:
        for n in ex.map(fetch, js):
            done += n
    # the pygame launcher uses the same fonts
    os.makedirs(os.path.join(HERE, "assets", "fonts"), exist_ok=True)
    for f in os.listdir(os.path.join(GD, "fonts")):
        shutil.copy(os.path.join(GD, "fonts", f), os.path.join(HERE, "assets", "fonts", f))
    print(f"downloaded {done / 1e6:.0f} MB")


if __name__ == "__main__":
    main()
