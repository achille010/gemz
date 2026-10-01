extends RefCounted
## Loads the imported real assets (Poly Haven models / textures / skies, Mixamo characters)
## with caching, and builds PBR materials. Everything degrades gracefully if a file is missing.

static var _scenes := {}
static var _mats := {}
static var _meshes := {}
static var _sizes := {}


static var _opt := {}


## Game-ready simplified mesh from tools/optimize.gd (falls back to the raw model's first mesh).
static func opt(name: String) -> Mesh:
	if not _opt.has(name):
		var p := "res://optimized/%s.res" % name
		if ResourceLoader.exists(p):
			_opt[name] = load(p)
		else:
			var m := mesh_of(name)
			_opt[name] = m[0] if not m.is_empty() else null
	return _opt[name]


static func has_model(name: String) -> bool:
	return ResourceLoader.exists("res://models/%s/%s.gltf" % [name, name])


static func scene(name: String) -> PackedScene:
	if not _scenes.has(name):
		var p := "res://models/%s/%s.gltf" % [name, name]
		_scenes[name] = load(p) if ResourceLoader.exists(p) else null
	return _scenes[name]


## Instance a model. Returns null when it isn't downloaded.
static func inst(name: String) -> Node3D:
	var s := scene(name)
	if s == null:
		return null
	var n := s.instantiate() as Node3D
	return n


## Local-space bounds of a model (cached).
static func size_of(name: String) -> AABB:
	if not _sizes.has(name):
		var n := inst(name)
		_sizes[name] = aabb(n, Transform3D.IDENTITY) if n != null else AABB(Vector3(-0.5, 0, -0.5), Vector3.ONE)
		if n != null:
			n.free()
	return _sizes[name]


static func aabb(n: Node, xf: Transform3D) -> AABB:
	var out := AABB()
	var first := true
	var t := xf
	if n is Node3D:
		t = xf * (n as Node3D).transform
	if n is MeshInstance3D and (n as MeshInstance3D).mesh != null:
		out = t * (n as MeshInstance3D).mesh.get_aabb()
		first = false
	for c in n.get_children():
		var a := aabb(c, t)
		if a.size != Vector3.ZERO:
			out = a if first else out.merge(a)
			first = false
	return out


## First mesh of a model (for MultiMesh scattering) + its transform inside the model.
static func mesh_of(name: String) -> Array:
	if not _meshes.has(name):
		var n := inst(name)
		_meshes[name] = []
		if n != null:
			var mi := _first_mesh(n, Transform3D.IDENTITY)
			if not mi.is_empty():
				_meshes[name] = mi
			n.free()
	return _meshes[name]


static func _first_mesh(n: Node, xf: Transform3D) -> Array:
	var t := xf
	if n is Node3D:
		t = xf * (n as Node3D).transform
	if n is MeshInstance3D and (n as MeshInstance3D).mesh != null:
		return [(n as MeshInstance3D).mesh, t]
	for c in n.get_children():
		var r := _first_mesh(c, t)
		if not r.is_empty():
			return r
	return []


static func tex(name: String, kind: String) -> Texture2D:
	for ext in ["jpg", "png"]:
		var p := "res://textures/%s/%s.%s" % [name, kind, ext]
		if ResourceLoader.exists(p):
			return load(p)
	return null


## World-space (triplanar) PBR material from a Poly Haven texture set.
static func pbr(name: String, metres_per_tile := 3.0, tint := Color.WHITE, triplanar := true) -> StandardMaterial3D:
	var key := "%s|%.2f|%s|%s" % [name, metres_per_tile, tint.to_html(), triplanar]
	if _mats.has(key):
		return _mats[key]
	var m := StandardMaterial3D.new()
	m.albedo_color = tint
	var d := tex(name, "diff")
	if d != null:
		m.albedo_texture = d
	var n := tex(name, "nor")
	if n != null:
		m.normal_enabled = true
		m.normal_texture = n
		m.normal_scale = 1.0
	var r := tex(name, "rough")
	if r != null:
		m.roughness_texture = r
		m.roughness_texture_channel = BaseMaterial3D.TEXTURE_CHANNEL_GREEN
	m.roughness = 1.0
	if triplanar:
		m.uv1_triplanar = true
		m.uv1_world_triplanar = true
		var s := 1.0 / metres_per_tile
		m.uv1_scale = Vector3(s, s, s)
		m.uv1_triplanar_sharpness = 4.0
	m.texture_filter = BaseMaterial3D.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS_ANISOTROPIC
	_mats[key] = m
	return m


static func sky_files(prefix: String) -> Array:
	var out := []
	var d := DirAccess.open("res://sky")
	if d == null:
		return out
	for f in d.get_files():
		if f.begins_with(prefix) and f.get_extension() == "hdr":
			out.append("res://sky/" + f)
	out.sort()
	return out
