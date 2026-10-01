extends SceneTree
## Offline: simplifies the photoscanned Poly Haven models to game triangle budgets.
## Each model -> res://optimized/<name>.res : ONE ArrayMesh (all parts baked together, imported
## materials kept) whose base level is within budget, plus coarser automatic LODs for distance.
##     Godot --headless --path godot --script res://tools/optimize.gd

const DEFAULT_BUDGET := 6000
const BUDGET := {
	"pine": 9000, "fir": 9000, "tree": 12000, "quiver": 7000, "dead_tree": 4000,
	"boulder": 2500, "boulder2": 2500, "boulder3": 2000, "rocks_moss": 5000, "cliff": 7000,
	"barrier": 2000, "barrier2": 2000, "hydrant": 2000, "shrub1": 5000, "shrub2": 6000, "shrub3": 3000,
	"grass": 2500, "grass2": 2500, "fern": 2500, "shrub4": 3000, "lamp": 4000, "car": 9000,
	"rifle": 12000, "pistol": 5000,
}


func _bake(n: Node, xf: Transform3D, out: Array) -> void:
	var t := xf
	if n is Node3D:
		t = xf * (n as Node3D).transform
	if n is MeshInstance3D and (n as MeshInstance3D).mesh != null:
		var mi := n as MeshInstance3D
		for s in mi.mesh.get_surface_count():
			var mat: Material = mi.get_surface_override_material(s)
			if mat == null:
				mat = mi.mesh.surface_get_material(s)
			out.append([mi.mesh.surface_get_arrays(s), t, mat])
	for c in n.get_children():
		_bake(c, t, out)


func _transform_arrays(arr: Array, t: Transform3D) -> Array:
	var v: PackedVector3Array = arr[Mesh.ARRAY_VERTEX]
	for i in v.size():
		v[i] = t * v[i]
	arr[Mesh.ARRAY_VERTEX] = v
	var b := t.basis.inverse().transposed()
	if arr[Mesh.ARRAY_NORMAL] != null:
		var nn: PackedVector3Array = arr[Mesh.ARRAY_NORMAL]
		for i in nn.size():
			nn[i] = (b * nn[i]).normalized()
		arr[Mesh.ARRAY_NORMAL] = nn
	if arr[Mesh.ARRAY_TANGENT] != null:
		var tg: PackedFloat32Array = arr[Mesh.ARRAY_TANGENT]
		for i in range(0, tg.size(), 4):
			var d := (t.basis * Vector3(tg[i], tg[i + 1], tg[i + 2])).normalized()
			tg[i] = d.x
			tg[i + 1] = d.y
			tg[i + 2] = d.z
		arr[Mesh.ARRAY_TANGENT] = tg
	return arr


func _tris(arr: Array) -> int:
	return (arr[Mesh.ARRAY_INDEX].size() if arr[Mesh.ARRAY_INDEX] != null else arr[Mesh.ARRAY_VERTEX].size()) / 3


func _init() -> void:
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path("res://optimized"))
	var d := DirAccess.open("res://models")
	for name in d.get_directories():
		var p := "res://models/%s/%s.gltf" % [name, name]
		if FileAccess.file_exists("res://optimized/%s.res" % name):
			continue
		var ps = load(p) if ResourceLoader.exists(p) else null
		if ps == null:
			print(name, ": not imported")
			continue
		var root: Node = ps.instantiate()
		var parts := []
		_bake(root, Transform3D.IDENTITY, parts)
		root.free()
		var before := 0
		for pt in parts:
			before += _tris(pt[0])
		var budget: int = BUDGET.get(name, DEFAULT_BUDGET)
		var am := ArrayMesh.new()
		var after := 0
		for pt in parts:
			var arr: Array = _transform_arrays(pt[0], pt[1])
			arr.resize(Mesh.ARRAY_MAX)
			if arr[Mesh.ARRAY_INDEX] == null:
				var idx := PackedInt32Array()
				idx.resize(arr[Mesh.ARRAY_VERTEX].size())
				for i in idx.size():
					idx[i] = i
				arr[Mesh.ARRAY_INDEX] = idx
			# this surface's share of the budget, proportional to its size
			var share := maxi(300, int(float(budget) * _tris(arr) / maxf(1.0, before)))
			var im := ImporterMesh.new()
			im.add_surface(Mesh.PRIMITIVE_TRIANGLES, arr, [], {}, pt[2])
			im.generate_lods(25.0, 60.0, [])
			var base: PackedInt32Array = arr[Mesh.ARRAY_INDEX]
			var lods := {}
			var picked := -1
			for li in im.get_surface_lod_count(0):
				var ind: PackedInt32Array = im.get_surface_lod_indices(0, li)
				if picked < 0 and ind.size() / 3 <= share:
					picked = li
					base = ind
				elif picked >= 0:
					lods[im.get_surface_lod_size(0, li)] = ind
			if picked < 0 and im.get_surface_lod_count(0) > 0 and base.size() / 3 > share:
				var last := im.get_surface_lod_count(0) - 1
				base = im.get_surface_lod_indices(0, last)
			arr[Mesh.ARRAY_INDEX] = base
			after += base.size() / 3
			am.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arr, [], lods)
			am.surface_set_material(am.get_surface_count() - 1, pt[2])
		var err := ResourceSaver.save(am, "res://optimized/%s.res" % name, ResourceSaver.FLAG_COMPRESS)
		print("%-13s %7d -> %6d tris  %s" % [name, before, after, "ok" if err == OK else "SAVE ERROR %d" % err])
	quit()
