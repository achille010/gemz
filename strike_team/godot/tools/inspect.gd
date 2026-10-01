extends SceneTree
const A = preload("res://scripts/assets.gd")

func tris(n: Node) -> int:
	var t := 0
	if n is MeshInstance3D and n.mesh:
		for s in n.mesh.get_surface_count():
			var arr = n.mesh.surface_get_arrays(s)
			var idx = arr[Mesh.ARRAY_INDEX]
			t += (idx.size() if idx != null else arr[Mesh.ARRAY_VERTEX].size()) / 3
	for c in n.get_children():
		t += tris(c)
	return t

func _init():
	var d := DirAccess.open("res://models")
	for m in d.get_directories():
		var n = A.inst(m)
		if n == null:
			print(m, " MISSING"); continue
		var bb = A.aabb(n, Transform3D.IDENTITY)
		print("%-13s tris %7d  size %s" % [m, tris(n), str(bb.size.snapped(Vector3(0.01,0.01,0.01)))])
		n.free()
	for c in ["soldier", "michelle"]:
		var s = load("res://characters/%s.glb" % c).instantiate()
		var ap = s.find_child("AnimationPlayer", true, false)
		var sk = s.find_child("*", true, false)
		var skel: Skeleton3D = null
		for x in s.find_children("*", "Skeleton3D", true, false): skel = x
		print(c, " tris ", tris(s), " anims ", ap.get_animation_list() if ap else "none", " skel path ", s.get_path_to(skel) if skel else "-", " size ", A.aabb(s, Transform3D.IDENTITY).size)
		if skel:
			var names = []
			for i in skel.get_bone_count(): names.append(skel.get_bone_name(i))
			print("  bones: ", ", ".join(names.slice(0, 60)))
		if ap:
			var an = ap.get_animation(ap.get_animation_list()[0])
			print("  track0: ", an.track_get_path(0), "  len ", an.length)
		s.free()
	quit()
