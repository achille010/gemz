# Assets

The game runs without anything here: soldiers, buildings and props are built from simple shapes,
and placeholder sounds are generated into `sounds/gen/`. Drop real files in and they are picked up
at the next mission.

| Folder | What | Used now? |
|---|---|---|
| `sounds/` | `shot`, `enemy_shot`, `reload`, `empty`, `hit`, `step`, `down`, `revive`, `pickup`, `beep`, `explosion`, `win`, `lose`, `music` (.wav / .ogg / .mp3) | **yes**: a file named like these replaces the generated one |
| `sky/` | HDRI panoramas (.hdr / .exr / .jpg / .png), e.g. from polyhaven.com | **yes**: a random one is used for day / dusk |
| `characters/` | ONE rigged soldier in `.glb` (Mixamo -> Blender -> glTF export, animations included) | **yes**: replaces the block soldiers, auto-scaled to 1.8 m, plays its "idle" animation; walk / shoot animations come next session |
| `weapons/` | rifle `.glb` | next session |
| `props/` | medkit, ammo crate, bomb, laptop, radar, barrels, sandbags `.glb` | next session |
| `maps/` | modular building kits `.glb` (Kenney City Kit, Quaternius, Synty-style) | next session |
| `textures/` | PBR sets: concrete, asphalt, sand, brick, metal, wood (albedo + normal + roughness) from ambientCG.com / polyhaven.com | next session |

Free, legal sources: **mixamo.com** (characters + animations), **polyhaven.com** (HDRIs, textures,
models, CC0), **ambientcg.com** (textures, CC0), **kenney.nl** / **quaternius.com** (model kits, CC0),
**sketchfab.com** (filter "Downloadable" + CC licence), **freesound.org** / **kenney.nl/assets/category:Audio** (sounds).
