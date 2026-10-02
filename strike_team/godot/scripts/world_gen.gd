extends RefCounted
## Builds the battlefield: 240 m play area (road grid, city blocks / base / compounds / woods)
## inside a ring of textured mountains, using real Poly Haven models (simplified by
## tools/optimize.gd), PBR textures and HDRI skies. Also paints the GTA-style radar image.

const A := preload("res://scripts/assets.gd")
const CELL := 6.0
const N := 40                         # cells per side -> 240 m play area
const SPAWN_CELLS := 4
const TERRAIN_HALF := 460.0
const TERRAIN_STEP := 5.0
const MAP_HALF := 150.0               # radar image covers +-150 m
const MAP_PX := 600

const BIOMES := {
	"urban": {"ground": "grass", "gtint": Color(0.75, 0.8, 0.7), "road": "asphalt", "walls": ["brick", "plaster", "concrete", "facade", "plaster2", "yellow"],
		"roads_every": 7, "tall": 1.0, "trees": ["pine", "fir"], "snow": 9999.0, "radar": Color(0.16, 0.19, 0.17)},
	"base": {"ground": "grass_dry", "gtint": Color(0.85, 0.85, 0.75), "road": "asphalt", "walls": ["concrete", "metal", "plaster2"],
		"roads_every": 10, "tall": 0.55, "trees": ["pine", "fir"], "snow": 9999.0, "radar": Color(0.18, 0.19, 0.15)},
	"desert": {"ground": "sand", "gtint": Color(1.0, 0.95, 0.88), "road": "dirt", "walls": ["clay", "plaster", "yellow"],
		"roads_every": 13, "tall": 0.4, "trees": ["quiver", "dead_tree"], "snow": 9999.0, "radar": Color(0.26, 0.22, 0.16)},
	"snow": {"ground": "snow", "gtint": Color(1, 1, 1), "road": "gravel", "walls": ["stone", "white", "concrete"],
		"roads_every": 13, "tall": 0.5, "trees": ["pine", "fir"], "snow": 25.0, "radar": Color(0.28, 0.30, 0.33)},
	"forest": {"ground": "forest", "gtint": Color(0.9, 0.95, 0.85), "road": "dirt", "walls": ["stone", "plaster2", "brick"],
		"roads_every": 13, "tall": 0.45, "trees": ["pine", "fir"], "snow": 9999.0, "radar": Color(0.12, 0.17, 0.12)},
	"docks": {"ground": "gravel", "gtint": Color(0.85, 0.85, 0.85), "road": "asphalt", "walls": ["metal", "concrete", "brick"],
		"roads_every": 10, "tall": 0.7, "trees": ["pine"], "snow": 9999.0, "radar": Color(0.17, 0.18, 0.2)},
}

var half := CELL * N / 2.0
var blocked := PackedByteArray()
var road := PackedByteArray()
var rng: RandomNumberGenerator
var root: Node3D
var biome := {}
var biome_name := "urban"
var night := false
var spawn_points: Array = []
var radar: Image
var radar_tex: ImageTexture
var noise := FastNoiseLite.new()
var mm_lists := {}
var lamp_lights := 0
var sun_dir := Vector3(0.3, -0.8, 0.4)
var dash_mat: StandardMaterial3D
var _glass: StandardMaterial3D
var _lit: StandardMaterial3D


func build(parent: Node3D, mission: Dictionary, r: RandomNumberGenerator, _assets: String) -> void:
	rng = r
	root = parent
	biome_name = mission.get("biome", "urban")
	biome = BIOMES.get(biome_name, BIOMES["urban"])
	night = mission.get("time", "day") == "night"
	blocked.resize(N * N)
	blocked.fill(0)
	road.resize(N * N)
	road.fill(0)
	noise.seed = rng.randi()
	noise.frequency = 0.0045
	noise.fractal_type = FastNoiseLite.FRACTAL_RIDGED
	noise.fractal_octaves = 5
	dash_mat = StandardMaterial3D.new()
	dash_mat.albedo_color = Color(0.85, 0.82, 0.7)
	dash_mat.roughness = 0.7
	radar = Image.create(MAP_PX, MAP_PX, false, Image.FORMAT_RGBA8)
	_environment(mission.get("time", "day"), mission.get("mods", []))
	_terrain()
	_roads()
	_blocks()
	_mountain_dressing()
	_flush_multimeshes()
	spawn_points = [_ground_point(cell_center(1, 2)), _ground_point(cell_center(2, 1))]
	radar_tex = ImageTexture.create_from_image(radar)


# ================================================================ grid helpers
func cell_center(i: int, j: int) -> Vector3:
	return Vector3(-half + (i + 0.5) * CELL, 0.0, -half + (j + 0.5) * CELL)


func _ground_point(p: Vector3) -> Vector3:
	# Snap a world-space point to the terrain surface so spawns never land inside the mesh.
	return Vector3(p.x, height_at(p.x, p.z) + 0.6, p.z)


func _idx(i: int, j: int) -> int:
	return i + j * N


func _inside(i: int, j: int) -> bool:
	return i >= 0 and j >= 0 and i < N and j < N


func is_free(i: int, j: int) -> bool:
	return _inside(i, j) and blocked[_idx(i, j)] == 0 and not (i < SPAWN_CELLS and j < SPAWN_CELLS)


func random_open(avoid: Array, min_d: float) -> Vector3:
	var d := min_d
	for t in 800:
		if t % 100 == 99:
			d *= 0.8
		var i := rng.randi_range(1, N - 2)
		var j := rng.randi_range(1, N - 2)
		if not is_free(i, j):
			continue
		var p := cell_center(i, j) + Vector3(rng.randf_range(-1.5, 1.5), 0, rng.randf_range(-1.5, 1.5))
		var ok := true
		for a in avoid:
			if Vector2(p.x - a.x, p.z - a.z).length() < d:
				ok = false
				break
		if ok:
			return _ground_point(p)
	return _ground_point(cell_center(N / 2, N / 2))


func height_at(x: float, z: float) -> float:
	var d := maxf(absf(x), absf(z))
	var edge := half + 10.0
	if d < edge:
		return 0.0
	var t := smoothstep(edge, edge + 90.0, d)
	var n := (noise.get_noise_2d(x, z) + 1.0) * 0.5
	var base := 30.0 if biome_name == "desert" else 55.0
	var amp := 70.0 if biome_name == "desert" else 150.0
	return t * (base + amp * n * n) + t * 3.0 * sin(x * 0.05) * cos(z * 0.04)


func _to_px(p: Vector3) -> Vector2i:
	return Vector2i(int((p.x + MAP_HALF) / (MAP_HALF * 2.0) * MAP_PX), int((p.z + MAP_HALF) / (MAP_HALF * 2.0) * MAP_PX))


# ================================================================ sky, sun, post-processing
func _environment(tod: String, mods: Array) -> void:
	var prefix := "day_"
	if tod == "dusk":
		prefix = "dusk_"
	elif tod == "night":
		prefix = "night_"
	elif "fog" in mods:
		prefix = "overcast_"
	elif biome_name == "snow" and rng.randf() < 0.6:
		prefix = "snow_"
	var skies := A.sky_files(prefix)
	if skies.is_empty():
		skies = A.sky_files("day_")
	var env := Environment.new()
	var sky := Sky.new()
	var sky_rot := rng.randf_range(0.0, TAU)
	if not skies.is_empty():
		var pm := PanoramaSkyMaterial.new()
		var tex: Texture2D = load(skies[rng.randi() % skies.size()])
		pm.panorama = tex
		pm.energy_multiplier = 0.35 if tod == "night" else 1.0
		sky.sky_material = pm
		sun_dir = _sun_from_hdri(tex, sky_rot)
	else:
		sky.sky_material = ProceduralSkyMaterial.new()
	sky.radiance_size = Sky.RADIANCE_SIZE_256
	env.background_mode = Environment.BG_SKY
	env.sky = sky
	env.sky_rotation = Vector3(0, sky_rot, 0)
	env.ambient_light_source = Environment.AMBIENT_SOURCE_SKY
	env.ambient_light_energy = 0.9 if tod != "night" else 0.7
	env.reflected_light_source = Environment.REFLECTION_SOURCE_SKY
	env.tonemap_mode = Environment.TONE_MAPPER_AGX
	env.tonemap_exposure = 1.0 if tod != "night" else 1.7
	env.ssao_enabled = true
	env.ssao_radius = 1.2
	env.ssao_intensity = 1.6
	env.glow_enabled = true
	env.glow_intensity = 0.6
	env.glow_bloom = 0.04
	env.glow_hdr_threshold = 1.2
	env.adjustment_enabled = true
	env.adjustment_contrast = 1.06
	env.adjustment_saturation = 0.95 if biome_name != "desert" else 0.9
	env.fog_enabled = true
	env.fog_mode = Environment.FOG_MODE_DEPTH
	env.fog_depth_begin = 55.0
	env.fog_depth_end = 210.0        # matches cam.far so distant geometry fades out cleanly
	env.fog_density = 0.08           # was 0.6 - the whole scene used to wash out white
	env.fog_aerial_perspective = 0.35
	env.fog_sky_affect = 0.0
	if "fog" in mods:
		env.fog_mode = Environment.FOG_MODE_EXPONENTIAL
		env.fog_density = 0.018
		env.fog_aerial_perspective = 0.6
		env.fog_light_color = Color(0.62, 0.64, 0.67)
		env.fog_sky_affect = 0.9
	var we := WorldEnvironment.new()
	we.environment = env
	root.add_child(we)
	var sun := DirectionalLight3D.new()
	sun.light_energy = {"day": 1.6, "dusk": 1.1, "night": 0.2}.get(tod, 1.4)
	sun.light_color = {"day": Color(1.0, 0.96, 0.9), "dusk": Color(1.0, 0.68, 0.42), "night": Color(0.6, 0.7, 1.0)}.get(tod, Color.WHITE)
	if "fog" in mods:
		sun.light_energy *= 0.5
	sun.shadow_enabled = true
	sun.shadow_blur = 1.5
	sun.directional_shadow_mode = DirectionalLight3D.SHADOW_PARALLEL_2_SPLITS
	sun.directional_shadow_max_distance = 75.0
	var d := sun_dir.normalized()
	if d.y > -0.15:
		d.y = -0.15 if tod == "dusk" else -0.55
		d = d.normalized()
	sun.look_at_from_position(Vector3.ZERO, d, Vector3.UP)
	root.add_child(sun)


## Brightest point of the HDRI = the sun; aim the light there so shadows match the sky.
func _sun_from_hdri(tex: Texture2D, rot: float) -> Vector3:
	var img := tex.get_image()
	if img == null:
		return Vector3(0.4, -0.7, 0.3)
	img = img.duplicate()
	if img.is_compressed():
		img.decompress()
	img.resize(128, 64, Image.INTERPOLATE_BILINEAR)
	var best := -1.0
	var bu := 0.5
	var bv := 0.3
	for y in 32:
		for x in 128:
			var c := img.get_pixel(x, y)
			var l := c.r * 0.3 + c.g * 0.6 + c.b * 0.1
			if l > best:
				best = l
				bu = (x + 0.5) / 128.0
				bv = (y + 0.5) / 64.0
	var phi := bu * TAU
	var theta := (0.5 - bv) * PI
	var to_sun := Vector3(-sin(phi) * cos(theta), sin(theta), cos(phi) * cos(theta))
	return -to_sun.rotated(Vector3.UP, rot)


# ================================================================ terrain + mountains
func _terrain() -> void:
	var n := int(TERRAIN_HALF * 2.0 / TERRAIN_STEP) + 1
	var verts := PackedVector3Array()
	var norms := PackedVector3Array()
	var uvs := PackedVector2Array()
	verts.resize(n * n)
	norms.resize(n * n)
	uvs.resize(n * n)
	var h := PackedFloat32Array()
	h.resize(n * n)
	for j in n:
		for i in n:
			h[i + j * n] = height_at(-TERRAIN_HALF + i * TERRAIN_STEP, -TERRAIN_HALF + j * TERRAIN_STEP)
	for j in n:
		for i in n:
			var x := -TERRAIN_HALF + i * TERRAIN_STEP
			var z := -TERRAIN_HALF + j * TERRAIN_STEP
			var hl := h[maxi(i - 1, 0) + j * n]
			var hr := h[mini(i + 1, n - 1) + j * n]
			var hd := h[i + maxi(j - 1, 0) * n]
			var hu := h[i + mini(j + 1, n - 1) * n]
			verts[i + j * n] = Vector3(x, h[i + j * n], z)
			norms[i + j * n] = Vector3(hl - hr, 2.0 * TERRAIN_STEP, hd - hu).normalized()
			uvs[i + j * n] = Vector2(x, z)
	var idx := PackedInt32Array()
	idx.resize((n - 1) * (n - 1) * 6)
	var k := 0
	for j in n - 1:
		for i in n - 1:
			var a := i + j * n
			idx[k] = a
			idx[k + 1] = a + 1
			idx[k + 2] = a + n
			idx[k + 3] = a + 1
			idx[k + 4] = a + n + 1
			idx[k + 5] = a + n
			k += 6
	var arr := []
	arr.resize(Mesh.ARRAY_MAX)
	arr[Mesh.ARRAY_VERTEX] = verts
	arr[Mesh.ARRAY_NORMAL] = norms
	arr[Mesh.ARRAY_TEX_UV] = uvs
	arr[Mesh.ARRAY_INDEX] = idx
	var am := ArrayMesh.new()
	am.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arr)
	var sm := ShaderMaterial.new()
	sm.shader = load("res://shaders/terrain.gdshader")
	var g: String = biome["ground"]
	sm.set_shader_parameter("ground_albedo", A.tex(g, "diff"))
	sm.set_shader_parameter("ground_normal", A.tex(g, "nor"))
	sm.set_shader_parameter("ground_rough", A.tex(g, "rough"))
	var rock := "rock2" if biome_name in ["desert", "base"] else "rock"
	sm.set_shader_parameter("rock_albedo", A.tex(rock, "diff"))
	sm.set_shader_parameter("rock_normal", A.tex(rock, "nor"))
	sm.set_shader_parameter("top_albedo", A.tex("snow", "diff"))
	sm.set_shader_parameter("top_normal", A.tex("snow", "nor"))
	sm.set_shader_parameter("ground_tint", biome["gtint"])
	sm.set_shader_parameter("rock_tint", Color(1.0, 0.9, 0.78) if biome_name == "desert" else Color(0.92, 0.92, 0.92))
	sm.set_shader_parameter("snow_height", float(biome["snow"]) if biome_name == "snow" else 95.0)
	sm.set_shader_parameter("ground_tile", 3.5)
	var mi := MeshInstance3D.new()
	mi.mesh = am
	mi.material_override = sm
	root.add_child(mi)
	# flat walkable ground + invisible boundary (mountains are scenery)
	var sb := StaticBody3D.new()
	var cs := CollisionShape3D.new()
	var bs := BoxShape3D.new()
	bs.size = Vector3(TERRAIN_HALF * 2.0, 2.0, TERRAIN_HALF * 2.0)
	cs.shape = bs
	cs.position.y = -1.0
	sb.add_child(cs)
	for s in [-1.0, 1.0]:
		for axis in 2:
			var w := CollisionShape3D.new()
			var wb := BoxShape3D.new()
			wb.size = Vector3(1.0, 30.0, half * 2.0 + 4.0) if axis == 0 else Vector3(half * 2.0 + 4.0, 30.0, 1.0)
			w.shape = wb
			w.position = Vector3(s * (half + 0.5), 15.0, 0) if axis == 0 else Vector3(0, 15.0, s * (half + 0.5))
			sb.add_child(w)
	root.add_child(sb)
	# radar background: hill-shaded terrain
	var base: Color = biome["radar"]
	for py in MAP_PX:
		for px in MAP_PX:
			var wx := (px + 0.5) / MAP_PX * MAP_HALF * 2.0 - MAP_HALF
			var wz := (py + 0.5) / MAP_PX * MAP_HALF * 2.0 - MAP_HALF
			var hh := height_at(wx, wz)
			var shade := clampf((height_at(wx + 2.0, wz + 2.0) - hh) * 0.08, -0.25, 0.25)
			radar.set_pixel(px, py, base.lightened(clampf(hh / 300.0, 0.0, 0.25)).darkened(shade))
	# perimeter of concrete barriers marks the edge of the playable area
	var bar := A.opt("barrier")
	if bar != null:
		var t := -half
		while t < half:
			for s in [-1.0, 1.0]:
				_mm_add("barrier", bar, Transform3D(Basis.IDENTITY, Vector3(t, -bar.get_aabb().position.y, s * (half + 0.4))), 160.0, true)
				_mm_add("barrier", bar, Transform3D(Basis(Vector3.UP, PI / 2.0), Vector3(s * (half + 0.4), -bar.get_aabb().position.y, t)), 160.0, true)
			t += bar.get_aabb().size.x * 0.98


# ================================================================ roads
func _road_line(k: int) -> bool:
	var e: int = biome["roads_every"]
	return k % e == 3 or (e > 7 and k == N - 4)


func _roads() -> void:
	var mat := A.pbr(biome["road"], 5.0)
	var walk := A.pbr("pavement", 3.0)
	var paved: bool = biome["road"] == "asphalt"
	var rc := Color(0.45, 0.47, 0.5) if paved else Color(0.38, 0.34, 0.28)
	var dash := BoxMesh.new()
	dash.size = Vector3(0.15, 0.01, 2.5)
	dash.material = dash_mat
	for k in N:
		if not _road_line(k):
			continue
		var c := -half + (k + 0.5) * CELL
		for axis in 2:
			var rw := CELL * (0.78 if paved else 0.6)
			var size := Vector3(rw, 0.04, half * 2.0) if axis == 0 else Vector3(half * 2.0, 0.04, rw)
			var pos := Vector3(c, 0.02 + axis * 0.004, 0) if axis == 0 else Vector3(0, 0.02 + axis * 0.004, c)
			_plain_box(pos, size, mat)
			if paved:
				for s in [-1.0, 1.0]:
					var off: float = CELL * 0.445 * s
					var ws := Vector3(CELL * 0.11, 0.16, half * 2.0) if axis == 0 else Vector3(half * 2.0, 0.16, CELL * 0.11)
					var wp := Vector3(c + off, 0.08, 0) if axis == 0 else Vector3(0, 0.08, c + off)
					_plain_box(wp, ws, walk)
				var t := -half + 2.0
				while t < half:
					var xf := Transform3D(Basis(Vector3.UP, 0.0 if axis == 0 else PI / 2.0), Vector3(c, 0.05, t) if axis == 0 else Vector3(t, 0.05, c))
					_mm_add("dash", dash, xf, 70.0, false)
					t += 6.0
			for m in N:
				if axis == 0:
					road[_idx(k, m)] = 1
				else:
					road[_idx(m, k)] = 1
			var a0 := _to_px(Vector3(c - rw / 2.0, 0, -half))
			var a1 := _to_px(Vector3(c + rw / 2.0, 0, half))
			if axis == 0:
				radar.fill_rect(Rect2i(a0.x, a0.y, maxi(2, a1.x - a0.x), a1.y - a0.y), rc)
			else:
				radar.fill_rect(Rect2i(a0.y, a0.x, a1.y - a0.y, maxi(2, a1.x - a0.x)), rc)
		if paved:
			var t2 := -half + 9.0
			while t2 < half:
				_lamp(Vector3(c + CELL * 0.47, 0, t2) if rng.randf() < 0.5 else Vector3(t2, 0, c + CELL * 0.47))
				t2 += 30.0


func _lamp(p: Vector3) -> void:
	if A.opt("lamp") == null:
		return
	prop("lamp", p, rng.randf() * TAU, 1.0, false)
	if night and lamp_lights < 18:
		lamp_lights += 1
		var l := OmniLight3D.new()
		l.light_color = Color(1.0, 0.78, 0.5)
		l.light_energy = 3.0
		l.omni_range = 16.0
		l.position = p + Vector3(0, 3.7, 0)
		root.add_child(l)


# ================================================================ blocks
func _blocks() -> void:
	var spans := []
	var k := 0
	while k < N:
		if _road_line(k):
			k += 1
			continue
		var s := k
		while k < N and not _road_line(k):
			k += 1
		spans.append([s, k - s])
	for bx in spans:
		for bz in spans:
			_block(bx[0], bz[0], bx[1], bz[1])


func _block(i0: int, j0: int, w: int, d: int) -> void:
	var kind := ""
	var r := rng.randf()
	match biome_name:
		"urban":
			kind = "city" if r < 0.7 else ("park" if r < 0.8 else "lot")
		"base":
			kind = "hangar" if r < 0.35 else ("barracks" if r < 0.7 else "yard")
		"docks":
			kind = "containers" if r < 0.55 else ("warehouse" if r < 0.85 else "yard")
		"desert":
			kind = "compound" if r < 0.65 else "open"
		_:
			kind = "woods" if r < 0.55 else ("camp" if r < 0.85 else "clearing")
	match kind:
		"city":
			var j := j0
			while j < j0 + d:
				var i := i0
				while i < i0 + w:
					var bw := mini(rng.randi_range(1, 3), i0 + w - i)
					var bd := mini(rng.randi_range(1, 2), j0 + d - j)
					var edge := i == i0 or j == j0 or i + bw >= i0 + w or j + bd >= j0 + d
					if edge and _area_free(i, j, bw, bd) and rng.randf() < 0.85:
						_building_cells(i, j, bw, bd, rng.randf_range(7.0, 22.0) * float(biome["tall"]))
					i += bw
				j += 1
			_scatter_cover(i0, j0, w, d, ["car", "barrier", "trashcan", "cardboard", "barrel2", "utility", "hydrant"], 0.14)
		"park":
			_scatter_cover(i0, j0, w, d, ["barrier2", "trashcan", "shrub2", "boulder"], 0.08)
			_scatter_grass(i0, j0, w, d, 260)
		"lot":
			_scatter_cover(i0, j0, w, d, ["car", "car", "barrier", "barrier2", "trashcan"], 0.25)
		"hangar":
			if _area_free(i0 + 1, j0 + 1, mini(4, w - 2), mini(3, d - 2)):
				_building_cells(i0 + 1, j0 + 1, mini(4, w - 2), mini(3, d - 2), 9.0, "metal")
			_scatter_cover(i0, j0, w, d, ["mil_crate", "old_crate", "jerrycan", "generator", "barrel1", "tyre"], 0.14)
		"barracks":
			for jj in range(j0 + 1, j0 + d - 1, 3):
				if _area_free(i0 + 1, jj, w - 2, 1):
					_building_cells(i0 + 1, jj, w - 2, 1, 4.0, "concrete")
			_scatter_cover(i0, j0, w, d, ["cement", "mil_crate", "barrel1"], 0.12)
		"yard":
			_scatter_cover(i0, j0, w, d, ["mil_crate", "old_crate", "barrier2", "cement", "wood_barrels", "barrel3", "generator", "tyre", "lpg"], 0.3)
			_scatter_grass(i0, j0, w, d, 90)
		"containers":
			_containers(i0, j0, w, d)
		"warehouse":
			if _area_free(i0 + 1, j0 + 1, w - 2, d - 2):
				_building_cells(i0 + 1, j0 + 1, w - 2, d - 2, 10.0, "metal")
			_scatter_cover(i0, j0, w, d, ["barrel1", "barrel2", "crate2", "tyre"], 0.15)
		"compound":
			var j2 := j0
			while j2 < j0 + d:
				var i2 := i0
				while i2 < i0 + w:
					if rng.randf() < 0.45 and _area_free(i2, j2, 1, 1):
						_building_cells(i2, j2, 1, 1, rng.randf_range(3.2, 6.5))
					i2 += rng.randi_range(1, 3)
				j2 += rng.randi_range(1, 2)
			_scatter_cover(i0, j0, w, d, ["barrel3", "crate1", "tyre", "jerrycan", "car", "boulder2"], 0.12)
			_scatter_trees(i0, j0, w, d, 0.05)
		"open":
			_scatter_cover(i0, j0, w, d, ["boulder", "boulder2", "boulder3", "rocks_moss", "dead_tree"], 0.12)
			_scatter_trees(i0, j0, w, d, 0.1)
		"woods":
			_scatter_trees(i0, j0, w, d, 0.55)
			_scatter_cover(i0, j0, w, d, ["boulder", "rocks_moss", "dead_tree", "shrub2"], 0.12)
			_scatter_grass(i0, j0, w, d, 240)
		"camp":
			var placed := 0
			for t in 6:
				var ii := rng.randi_range(i0, i0 + w - 2)
				var jj2 := rng.randi_range(j0, j0 + d - 2)
				if placed < 3 and _area_free(ii, jj2, 2, 1):
					_building_cells(ii, jj2, 2, 1, 3.6)
					placed += 1
			_scatter_cover(i0, j0, w, d, ["crate1", "crate2", "barrel1", "wood_barrels", "generator"], 0.12)
			_scatter_trees(i0, j0, w, d, 0.15)
		"clearing":
			_scatter_cover(i0, j0, w, d, ["boulder", "boulder3", "dead_tree", "shrub2"], 0.1)
			_scatter_grass(i0, j0, w, d, 300)


func _area_free(i: int, j: int, w: int, d: int) -> bool:
	if w <= 0 or d <= 0:
		return false
	for jj in range(j, j + d):
		for ii in range(i, i + w):
			if not is_free(ii, jj) or road[_idx(ii, jj)] == 1:
				return false
	return true


# ================================================================ buildings
func _building_cells(i: int, j: int, w: int, d: int, h: float, style := "") -> void:
	for jj in range(j, j + d):
		for ii in range(i, i + w):
			blocked[_idx(ii, jj)] = 1
	var walls: Array = biome["walls"]
	if style == "":
		style = walls[rng.randi() % walls.size()]
	var inset := rng.randf_range(0.5, 1.0)
	var x0 := -half + i * CELL + inset
	var z0 := -half + j * CELL + inset
	var bw := w * CELL - inset * 2.0
	var bd := d * CELL - inset * 2.0
	var c := Vector3(x0 + bw / 2.0, 0, z0 + bd / 2.0)
	var floors := maxi(1, int(maxf(h, 3.2) / 3.3))
	h = floors * 3.3 + 0.6
	var wall := A.pbr(style, 3.0 if style != "metal" else 2.0)
	var trim := A.pbr("concrete", 2.0, Color(0.75, 0.75, 0.75))
	_solid_box(c + Vector3(0, h / 2.0, 0), Vector3(bw, h, bd), wall)
	_plain_box(c + Vector3(0, h + 0.05, 0), Vector3(bw - 0.1, 0.1, bd - 0.1), A.pbr("roof", 4.0))
	if style != "metal":
		for s in [-1.0, 1.0]:
			_plain_box(c + Vector3(0, h + 0.45, s * (bd / 2.0 - 0.12)), Vector3(bw, 0.8, 0.24), trim)
			_plain_box(c + Vector3(s * (bw / 2.0 - 0.12), h + 0.45, 0), Vector3(0.24, 0.8, bd), trim)
		_plain_box(c + Vector3(0, 0.35, 0), Vector3(bw + 0.12, 0.7, bd + 0.12), trim)
		for f in range(1, floors):
			_plain_box(c + Vector3(0, f * 3.3, 0), Vector3(bw + 0.16, 0.2, bd + 0.16), trim)
		if rng.randf() < 0.6:
			prop("utility", c + Vector3(rng.randf_range(-bw / 4.0, bw / 4.0), h + 0.1, rng.randf_range(-bd / 4.0, bd / 4.0)), rng.randf() * TAU, 1.4, false)
	else:
		_plain_box(c + Vector3(0, h * 0.4, bd / 2.0 + 0.04), Vector3(minf(8.0, bw * 0.6), h * 0.8, 0.08), A.pbr("metal", 1.5, Color(0.55, 0.6, 0.55)))
	if style != "metal" or rng.randf() < 0.5:
		var door_side := rng.randi() % 4
		for side in 4:
			var along := bw if side % 2 == 0 else bd
			var nrm := Vector3([0, 1, 0, -1][side], 0, [1, 0, -1, 0][side])
			var ext := (bd if side % 2 == 0 else bw) / 2.0
			var count := int((along - 1.5) / 3.0)
			var basis := Basis(Vector3.UP, atan2(nrm.x, nrm.z))
			var tang := Vector3(nrm.z, 0, -nrm.x)
			for f in floors:
				for wv in count:
					if f == 0 and side == door_side and wv == count / 2:
						continue
					var off: float = -along / 2.0 + 1.5 + (wv + 0.5) * (along - 3.0) / count
					var pos := c + nrm * (ext + 0.03) + tang * off + Vector3(0, f * 3.3 + 1.9, 0)
					var lit := night and rng.randf() < 0.3
					_mm_add("win_lit" if lit else "win", null, Transform3D(basis, pos), 140.0, false)
					_mm_add("frame", null, Transform3D(basis, pos - nrm * 0.015), 120.0, false)
			if side == door_side:
				_mm_add("door", null, Transform3D(basis, c + nrm * (ext + 0.04) + Vector3(0, 1.15, 0)), 120.0, false)
	var p0 := _to_px(Vector3(x0, 0, z0))
	var p1 := _to_px(Vector3(x0 + bw, 0, z0 + bd))
	var bc := Color(0.38, 0.4, 0.43)
	radar.fill_rect(Rect2i(p0, p1 - p0), bc.darkened(0.3))
	radar.fill_rect(Rect2i(p0 + Vector2i(1, 1), p1 - p0 - Vector2i(2, 2)), bc)


func _containers(i0: int, j0: int, w: int, d: int) -> void:
	var cols := [Color(0.7, 0.22, 0.16), Color(0.16, 0.36, 0.6), Color(0.2, 0.48, 0.3), Color(0.8, 0.58, 0.16), Color(0.55, 0.55, 0.58)]
	for jj in range(j0, j0 + d):
		for ii in range(i0, i0 + w - 1, 2):
			if rng.randf() < 0.45 or not _area_free(ii, jj, 2, 1):
				continue
			blocked[_idx(ii, jj)] = 1
			blocked[_idx(ii + 1, jj)] = 1
			var c := cell_center(ii, jj) + Vector3(CELL / 2.0, 0, 0)
			for s in rng.randi_range(1, 3):
				_solid_box(c + Vector3(0, 1.3 + s * 2.6, 0), Vector3(11.5, 2.58, 2.45), A.pbr("container", 2.6, cols[rng.randi() % cols.size()]))
			var a0 := _to_px(c - Vector3(5.8, 0, 1.2))
			radar.fill_rect(Rect2i(a0, _to_px(c + Vector3(5.8, 0, 1.2)) - a0), Color(0.36, 0.39, 0.42))


# ================================================================ props & vegetation
## Places one real model standing on the ground (box collider from its bounds).
func prop(name: String, pos: Vector3, yaw := 0.0, scale := 1.0, collide := true, vis := 130.0) -> Node3D:
	var mesh := A.opt(name)
	if mesh == null:
		return null
	var aabb := mesh.get_aabb()
	var mi := MeshInstance3D.new()
	mi.mesh = mesh
	mi.position = pos - Vector3(0, aabb.position.y * scale, 0)
	mi.rotation.y = yaw
	mi.scale = Vector3.ONE * scale
	mi.visibility_range_end = vis
	mi.visibility_range_end_margin = 8.0
	mi.visibility_range_fade_mode = GeometryInstance3D.VISIBILITY_RANGE_FADE_SELF
	root.add_child(mi)
	if collide and aabb.size.y * scale > 0.25:
		var sb := StaticBody3D.new()
		var cs := CollisionShape3D.new()
		var bs := BoxShape3D.new()
		bs.size = aabb.size
		cs.shape = bs
		cs.position = aabb.position + aabb.size / 2.0
		sb.add_child(cs)
		mi.add_child(sb)
	return mi


func _scatter_cover(i0: int, j0: int, w: int, d: int, names: Array, chance: float) -> void:
	for jj in range(j0, j0 + d):
		for ii in range(i0, i0 + w):
			if not is_free(ii, jj) or road[_idx(ii, jj)] == 1 or rng.randf() > chance:
				continue
			var name: String = names[rng.randi() % names.size()]
			if A.opt(name) == null:
				continue
			var big := name in ["car", "wood_barrels", "rocks_moss", "boulder2", "dead_tree", "shrub2"]
			var sc := rng.randf_range(1.2, 2.2) if name.begins_with("boulder") else 1.0
			var c := cell_center(ii, jj) + Vector3(rng.randf_range(-1.4, 1.4), 0, rng.randf_range(-1.4, 1.4))
			prop(name, c, rng.randf() * TAU, sc, true)
			blocked[_idx(ii, jj)] = 1
			if not big:
				for e in rng.randi_range(1, 3):
					var n2: String = names[rng.randi() % names.size()]
					if n2 in ["car", "wood_barrels", "rocks_moss", "dead_tree", "boulder2", "shrub2"]:
						continue
					prop(n2, c + Vector3(rng.randf_range(-1.6, 1.6), 0, rng.randf_range(-1.6, 1.6)), rng.randf() * TAU, 1.0, true)
			var px := _to_px(c)
			radar.fill_rect(Rect2i(px - Vector2i(1, 1), Vector2i(3, 3)), Color(0.32, 0.34, 0.35))


func _tree_scale(name: String, mesh: Mesh) -> float:
	if name == "dead_tree":
		return rng.randf_range(1.2, 1.8)
	var target: float = {"pine": 12.0, "fir": 10.0, "tree": 9.0, "quiver": 4.5}.get(name, 8.0)
	return target / maxf(0.1, mesh.get_aabb().size.y) * rng.randf_range(0.8, 1.25)


func _scatter_trees(i0: int, j0: int, w: int, d: int, chance: float) -> void:
	var kinds: Array = biome["trees"]
	for jj in range(j0, j0 + d):
		for ii in range(i0, i0 + w):
			if not is_free(ii, jj) or road[_idx(ii, jj)] == 1 or rng.randf() > chance:
				continue
			var name: String = kinds[rng.randi() % kinds.size()]
			var mesh := A.opt(name)
			if mesh == null:
				continue
			var c := cell_center(ii, jj) + Vector3(rng.randf_range(-1.8, 1.8), 0, rng.randf_range(-1.8, 1.8))
			var sc := _tree_scale(name, mesh)
			_mm_add(name, mesh, Transform3D(Basis(Vector3.UP, rng.randf() * TAU).scaled(Vector3.ONE * sc), c - Vector3(0, mesh.get_aabb().position.y * sc, 0)), 220.0, true)
			var sb := StaticBody3D.new()
			var cs := CollisionShape3D.new()
			var cyl := CylinderShape3D.new()
			cyl.radius = 0.35
			cyl.height = 4.0
			cs.shape = cyl
			sb.position = c + Vector3(0, 2.0, 0)
			sb.add_child(cs)
			root.add_child(sb)
			blocked[_idx(ii, jj)] = 1
			var px := _to_px(c)
			radar.fill_rect(Rect2i(px - Vector2i(2, 2), Vector2i(4, 4)), Color(0.14, 0.26, 0.14))


func _scatter_grass(i0: int, j0: int, w: int, d: int, count: int) -> void:
	if biome_name in ["snow", "desert"]:
		return
	var names := ["grass", "grass2", "fern", "shrub4"]
	for k in count:
		var name: String = names[rng.randi() % names.size()]
		var mesh := A.opt(name)
		if mesh == null:
			continue
		var x := -half + (i0 + rng.randf() * w) * CELL
		var z := -half + (j0 + rng.randf() * d) * CELL
		var ci := int((x + half) / CELL)
		var cj := int((z + half) / CELL)
		if not _inside(ci, cj) or road[_idx(ci, cj)] == 1 or blocked[_idx(ci, cj)] == 1:
			continue
		var sc := rng.randf_range(0.8, 1.4)
		_mm_add(name, mesh, Transform3D(Basis(Vector3.UP, rng.randf() * TAU).scaled(Vector3.ONE * sc), Vector3(x, 0, z)), 55.0, false)


func _mountain_dressing() -> void:
	var kinds: Array = biome["trees"]
	var tries := 2600 if biome_name in ["forest", "snow"] else 900
	for k in tries:
		var a := rng.randf() * TAU
		var dist := rng.randf_range(half + 14.0, TERRAIN_HALF - 30.0)
		var x := cos(a) * dist
		var z := sin(a) * dist
		if maxf(absf(x), absf(z)) < half + 12.0:
			continue
		var h := height_at(x, z)
		var slope := absf(height_at(x + 3.0, z) - h) + absf(height_at(x, z + 3.0) - h)
		if h > (float(biome["snow"]) if biome_name == "snow" else 120.0) or slope > 3.2:
			continue
		var name: String = kinds[rng.randi() % kinds.size()]
		var mesh := A.opt(name)
		if mesh == null:
			continue
		var sc := _tree_scale(name, mesh) * 1.2
		_mm_add("far_" + name, mesh, Transform3D(Basis(Vector3.UP, rng.randf() * TAU).scaled(Vector3.ONE * sc), Vector3(x, h - 0.5, z)), 700.0, false)
		var px := _to_px(Vector3(x, 0, z))
		if px.x >= 0 and px.y >= 0 and px.x < MAP_PX and px.y < MAP_PX:
			radar.set_pixelv(px, Color(0.12, 0.2, 0.12))
	for k in 70:
		var a := rng.randf() * TAU
		var dist := rng.randf_range(half + 24.0, half + 70.0)
		var p := Vector3(cos(a) * dist, 0, sin(a) * dist)
		if maxf(absf(p.x), absf(p.z)) < half + 18.0:
			continue
		var name: String = "cliff" if rng.randf() < 0.5 else ["boulder", "boulder2", "rocks_moss"][rng.randi() % 3]
		var mesh := A.opt(name)
		if mesh == null:
			continue
		var sc := rng.randf_range(2.5, 5.0) if name == "cliff" else rng.randf_range(4.0, 9.0)
		var lo := INF
		for o in [Vector2(0, 0), Vector2(4, 0), Vector2(-4, 0), Vector2(0, 4), Vector2(0, -4)]:
			lo = minf(lo, height_at(p.x + o.x * sc * 0.3, p.z + o.y * sc * 0.3))
		p.y = lo - mesh.get_aabb().position.y * sc - mesh.get_aabb().size.y * sc * 0.25
		_mm_add("far_" + name, mesh, Transform3D(Basis(Vector3.UP, rng.randf() * TAU).scaled(Vector3.ONE * sc), p), 600.0, true)


# ================================================================ batching helpers
func _plain_box(pos: Vector3, size: Vector3, mat: Material) -> void:
	var mi := MeshInstance3D.new()
	var bm := BoxMesh.new()
	bm.size = size
	mi.mesh = bm
	mi.material_override = mat
	mi.position = pos
	root.add_child(mi)


func _solid_box(pos: Vector3, size: Vector3, mat: Material) -> void:
	var sb := StaticBody3D.new()
	sb.position = pos
	var cs := CollisionShape3D.new()
	var bs := BoxShape3D.new()
	bs.size = size
	cs.shape = bs
	sb.add_child(cs)
	var mi := MeshInstance3D.new()
	var bm := BoxMesh.new()
	bm.size = size
	mi.mesh = bm
	mi.material_override = mat
	sb.add_child(mi)
	root.add_child(sb)


## Collect instances; flushed into chunked MultiMeshes (one draw call per chunk per mesh).
func _mm_add(key: String, mesh: Mesh, xf: Transform3D, vis: float, shadows: bool) -> void:
	var chunk := Vector2i(int(floor(xf.origin.x / 60.0)), int(floor(xf.origin.z / 60.0)))
	var k := "%s|%d|%d" % [key, chunk.x, chunk.y]
	if not mm_lists.has(k):
		mm_lists[k] = [key, mesh, [], vis, shadows]
	mm_lists[k][2].append(xf)


var _special := {}
func _special_mesh(key: String) -> Mesh:
	if _special.has(key):
		return _special[key]
	var m: Mesh = null
	match key:
		"win", "win_lit":
			var mat := StandardMaterial3D.new()
			if key == "win":
				mat.albedo_color = Color(0.07, 0.09, 0.11)
				mat.metallic = 0.9
				mat.roughness = 0.05
			else:
				mat.albedo_color = Color(1.0, 0.78, 0.48)
				mat.emission_enabled = true
				mat.emission = Color(1.0, 0.72, 0.4)
				mat.emission_energy_multiplier = 2.2
			var q := BoxMesh.new()
			q.size = Vector3(1.3, 1.6, 0.06)
			q.material = mat
			m = q
		"frame":
			var f := BoxMesh.new()
			f.size = Vector3(1.55, 1.85, 0.05)
			f.material = A.pbr("concrete", 2.0, Color(0.55, 0.55, 0.55))
			m = f
		"door":
			var dm := BoxMesh.new()
			dm.size = Vector3(1.3, 2.3, 0.08)
			dm.material = A.pbr("roof", 1.5, Color(0.35, 0.25, 0.2))
			m = dm
	_special[key] = m
	return m


func _flush_multimeshes() -> void:
	for k in mm_lists:
		var e: Array = mm_lists[k]
		var mesh: Mesh = e[1] if e[1] != null else _special_mesh(e[0])
		if mesh == null:
			continue
		var list: Array = e[2]
		var mm := MultiMesh.new()
		mm.transform_format = MultiMesh.TRANSFORM_3D
		mm.mesh = mesh
		mm.instance_count = list.size()
		for i in list.size():
			mm.set_instance_transform(i, list[i])
		var mmi := MultiMeshInstance3D.new()
		mmi.multimesh = mm
		mmi.visibility_range_end = e[3]
		mmi.visibility_range_end_margin = 10.0
		mmi.visibility_range_fade_mode = GeometryInstance3D.VISIBILITY_RANGE_FADE_SELF
		mmi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_ON if e[4] else GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		root.add_child(mmi)
	mm_lists.clear()
