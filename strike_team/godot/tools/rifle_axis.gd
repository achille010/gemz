extends SceneTree
func _init():
	var m: Mesh = load("res://optimized/rifle.res")
	var bb := m.get_aabb()
	var lo := [INF, -INF, INF, -INF]   # y range at -X end, +X end
	var ylo_min := INF; var ylo_max := -INF; var yhi_min := INF; var yhi_max := -INF
	for s in m.get_surface_count():
		var v: PackedVector3Array = m.surface_get_arrays(s)[Mesh.ARRAY_VERTEX]
		for p in v:
			if p.x < bb.position.x + bb.size.x * 0.08:
				ylo_min = min(ylo_min, p.y); ylo_max = max(ylo_max, p.y)
			if p.x > bb.end.x - bb.size.x * 0.08:
				yhi_min = min(yhi_min, p.y); yhi_max = max(yhi_max, p.y)
	print("aabb ", bb, "  -X end height ", ylo_max - ylo_min, "   +X end height ", yhi_max - yhi_min)
	var sk = load("res://characters/soldier.glb").instantiate()
	print("soldier root rot ", sk.rotation_degrees, " child ", sk.get_child(0).name, " rot ", sk.get_child(0).rotation_degrees)
	quit()
