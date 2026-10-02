extends Node
## STRIKE TEAM - 2 player co-op shooter (Godot side).
## launcher.py (Python/pygame) starts this with:
##     -- --mission m.json --result r.json --assets <dir>
## and streams both Arduino pads over UDP 127.0.0.1:47800 as JSON
##     {"p": [[lx, ly, rx, ry, lclick, rclick, ok], [...]]}     (axes -1..1, up / right = +)
## Debug: --showcase (models lined up in front of P1), --shot <png> (screenshot after 5 s, quit).

const UDP_PORT := 47800
const PlayerScript := preload("res://scripts/player.gd")
const BotScript := preload("res://scripts/bot.gd")
const HudScript := preload("res://scripts/hud.gd")
const WorldGen := preload("res://scripts/world_gen.gd")
const A := preload("res://scripts/assets.gd")
const TEAM_COLORS := [Color(0.15, 0.45, 1.0), Color(1.0, 0.18, 0.15)]
const TEAM_NAMES := ["BLUE", "RED"]
const BLEED_TIME := 60.0
const REVIVE_TIME := 3.0
const REVIVE_DIST := 2.4
const EXTRACT_RADIUS := 6.0
const KEYS := [
	[KEY_W, KEY_S, KEY_A, KEY_D, KEY_R, KEY_F, KEY_Q, KEY_E, KEY_C, KEY_SPACE],
	[KEY_I, KEY_K, KEY_J, KEY_L, KEY_UP, KEY_DOWN, KEY_LEFT, KEY_RIGHT, KEY_SHIFT, KEY_ENTER],
]

var mission := {}
var result_path := ""
var assets_dir := ""
var udp := PacketPeerUDP.new()
var pad_state := [[0, 0, 0, 0, 0, 0, 0], [0, 0, 0, 0, 0, 0, 0]]
var pad_time := [-10.0, -10.0]
var crouch_prev := [false, false]
var kb_look := [Vector2.ZERO, Vector2.ZERO]       # smoothed keyboard look input (0..1 each axis)
var rng := RandomNumberGenerator.new()
var gen
var world: Node3D
var holders := []
var cams := []
var viewmodels := []
var players := []
var pickups := []
var objective := {}
var fx := []
var sounds := {}
var sfx_pool := []
var sfx_next := 0
var state := "play"
var end_t := 0.0
var banner: Label
var sub_banner: Label
var banner_t := 0.0
var time_left := -1.0
var elapsed := 0.0
var wave_t := 0.0
var beep_t := 0.0
var difficulty := 3
var showcase := false
var solo := false            # one pad: one player, full screen, medkit = self-revive
var feed := []
var stats := {"kills": 0, "shots": 0, "revives": 0, "downs": 0}


func _ready() -> void:
	var args := OS.get_cmdline_user_args()
	for i in args.size():
		if args[i] == "--mission" and i + 1 < args.size():
			var d = JSON.parse_string(FileAccess.get_file_as_string(args[i + 1]))
			if d is Dictionary:
				mission = d
		elif args[i] == "--result" and i + 1 < args.size():
			result_path = args[i + 1]
		elif args[i] == "--assets" and i + 1 < args.size():
			assets_dir = args[i + 1]
		elif args[i] == "--solo":
			solo = true
		elif args[i] == "--showcase":
			showcase = true
		elif args[i] == "--shot" and i + 1 < args.size():
			_shot_later(args[i + 1])
	if assets_dir == "":
		assets_dir = ProjectSettings.globalize_path("res://").path_join("../assets").simplify_path()
	if mission.is_empty():
		mission = {"name": "Test Operation", "task": ["defuse", "hack", "destroy", "intel", "rescue", "assassinate", "survive", "collect"][randi() % 8],
			"biome": ["urban", "base", "desert", "snow", "forest", "docks"][randi() % 6], "time": "day",
			"seed": randi(), "difficulty": 3, "mods": [], "time_limit": 0, "params": {}}
	DisplayServer.window_set_title("STRIKE TEAM - " + str(mission.get("name", "")))
	rng.seed = int(mission.get("seed", 1))
	difficulty = int(mission.get("difficulty", 3))
	solo = solo or bool(mission.get("solo", false))
	udp.bind(UDP_PORT, "127.0.0.1")
	_load_sounds()
	_build_views()
	gen = WorldGen.new()
	gen.build(world, mission, rng, assets_dir)
	_spawn_players()
	_spawn_pickups()
	_setup_objective()
	_spawn_enemies()
	_build_overlay()
	if showcase:
		_do_showcase()
	if sounds.has("music"):
		var mp := AudioStreamPlayer.new()
		mp.stream = sounds["music"]
		mp.volume_db = -16.0
		add_child(mp)
		mp.play()
		mp.finished.connect(mp.play)
	_flash_banner(str(mission.get("name", "")).to_upper(), objective_text(), 5.0)


func _build_views() -> void:
	var hbox := HBoxContainer.new()
	hbox.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	hbox.add_theme_constant_override("separation", 4)
	add_child(hbox)
	var w3d := World3D.new()
	for i in 2:
		var holder := Control.new()
		holder.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		holder.size_flags_vertical = Control.SIZE_EXPAND_FILL
		holder.clip_contents = true
		hbox.add_child(holder)
		var svc := SubViewportContainer.new()
		svc.stretch = true
		svc.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
		holder.add_child(svc)
		var vp := SubViewport.new()
		vp.world_3d = w3d
		vp.msaa_3d = Viewport.MSAA_DISABLED
		vp.screen_space_aa = Viewport.SCREEN_SPACE_AA_FXAA
		vp.audio_listener_enable_3d = false
		# in solo mode the second viewport is hidden and never rendered: saves ~half the GPU cost
		if solo and i == 1:
			vp.render_target_update_mode = SubViewport.UPDATE_DISABLED
			vp.disable_3d = true
		svc.add_child(vp)
		if i == 0:
			world = Node3D.new()
			vp.add_child(world)
		var cam := Camera3D.new()
		cam.fov = 70.0
		cam.near = 0.05
		cam.far = 220.0
		cam.cull_mask = 0xFFFFF & ~(2 if i == 0 else 4) & ~(32 if i == 0 else 16)
		vp.add_child(cam)
		cam.current = true
		cams.append(cam)
		viewmodels.append(_make_viewmodel(cam, 16 if i == 0 else 32))
		var hud := HudScript.new()
		hud.main = self
		hud.idx = i
		hud.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
		hud.mouse_filter = Control.MOUSE_FILTER_IGNORE
		holder.add_child(hud)
		holders.append(holder)


const RIFLE_YAW := 90.0


func _make_viewmodel(cam: Camera3D, layer: int) -> Node3D:
	var vm := Node3D.new()
	vm.position = Vector3(0.2, -0.19, -0.5)
	cam.add_child(vm)
	var rifle := A.opt("rifle")
	if rifle != null:
		var mi := MeshInstance3D.new()
		mi.mesh = rifle
		mi.layers = layer
		mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		mi.rotation_degrees = Vector3(0, RIFLE_YAW, 0)
		var c := rifle.get_aabb().get_center()
		mi.position = -(Basis(Vector3.UP, deg_to_rad(RIFLE_YAW)) * c) * 0.6
		mi.scale = Vector3.ONE * 0.6
		vm.add_child(mi)
	var g := Gradient.new()
	g.set_color(0, Color(1.0, 0.9, 0.6, 1.0))
	g.set_color(1, Color(1.0, 0.45, 0.1, 0.0))
	var gt := GradientTexture2D.new()
	gt.gradient = g
	gt.fill = GradientTexture2D.FILL_RADIAL
	gt.fill_from = Vector2(0.5, 0.5)
	gt.fill_to = Vector2(0.5, 0.0)
	var q := MeshInstance3D.new()
	var qm := QuadMesh.new()
	qm.size = Vector2(0.28, 0.28)
	q.mesh = qm
	var fm := StandardMaterial3D.new()
	fm.albedo_texture = gt
	fm.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	fm.blend_mode = BaseMaterial3D.BLEND_MODE_ADD
	fm.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	q.material_override = fm
	q.layers = layer
	q.position = Vector3(0, 0.03, -0.42)
	q.visible = false
	vm.add_child(q)
	var flash := OmniLight3D.new()
	flash.light_color = Color(1.0, 0.75, 0.4)
	flash.omni_range = 5.0
	flash.light_energy = 0.0
	flash.position = Vector3(0, 0, -0.6)
	vm.add_child(flash)
	return vm


func _build_overlay() -> void:
	var cl := CanvasLayer.new()
	add_child(cl)
	var font: Font = load("res://fonts/Rajdhani-Bold.ttf") if ResourceLoader.exists("res://fonts/Rajdhani-Bold.ttf") else null
	banner = Label.new()
	banner.set_anchors_and_offsets_preset(Control.PRESET_CENTER_TOP)
	banner.position = Vector2(-700, 150)
	banner.size = Vector2(1400, 80)
	banner.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	banner.add_theme_font_size_override("font_size", 64)
	banner.add_theme_color_override("font_outline_color", Color(0, 0, 0, 0.8))
	banner.add_theme_constant_override("outline_size", 12)
	if font:
		banner.add_theme_font_override("font", font)
	cl.add_child(banner)
	sub_banner = Label.new()
	sub_banner.set_anchors_and_offsets_preset(Control.PRESET_CENTER_TOP)
	sub_banner.position = Vector2(-700, 235)
	sub_banner.size = Vector2(1400, 60)
	sub_banner.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	sub_banner.autowrap_mode = TextServer.AUTOWRAP_WORD
	sub_banner.add_theme_font_size_override("font_size", 26)
	sub_banner.add_theme_color_override("font_outline_color", Color(0, 0, 0, 0.8))
	sub_banner.add_theme_constant_override("outline_size", 8)
	if font:
		sub_banner.add_theme_font_override("font", font)
	cl.add_child(sub_banner)


func _shot_later(path: String) -> void:
	await get_tree().create_timer(5.0).timeout
	await RenderingServer.frame_post_draw
	get_viewport().get_texture().get_image().save_png(path)
	get_tree().quit()


func _do_showcase() -> void:
	var p0 = players[0]
	var b := Basis(Vector3.UP, p0.yaw)
	var fwd := -b.z
	var right := b.x
	p0.pitch = -0.12
	players[1].global_position = p0.global_position + fwd * 3.2 - right * 0.9
	players[1].yaw = p0.yaw + PI / 2.0
	var bot = _spawn_bot(p0.global_position + fwd * 4.5 + right * 1.2, "soldier")
	bot.set_physics_process(false)
	bot.rotation.y = p0.yaw + PI
	var victim = _spawn_bot(p0.global_position + fwd * 2.6 + right * 0.3, "soldier")
	victim.set_physics_process(false)
	get_tree().create_timer(4.0).timeout.connect(func(): victim.take_damage(500.0, p0))
	var h := make_prop("hostage")
	h.position = p0.global_position + fwd * 5.0 + right * 2.6
	var k := 0
	for kind in ["ammo", "medkit", "bomb", "terminal", "laptop", "radar"]:
		var pr := make_prop(kind)
		pr.position = p0.global_position + fwd * (7.0 + k * 0.4) + right * (-3.5 + k * 1.6)
		k += 1


func _flash_banner(big: String, small: String, secs: float) -> void:
	if banner == null:
		return
	banner.text = big
	sub_banner.text = small
	banner_t = secs
	banner.modulate.a = 1.0
	sub_banner.modulate.a = 1.0


# ======================================================================= models
var _soldier_ps: PackedScene
var _hostage_ps: PackedScene
var _tints := {}
var _idle_anim: Animation
const HAND_ROT := Vector3(0, 0, -90)
const HAND_POS := Vector3(0.0, 0.08, 0.04)


func _set_layers(n: Node, layer: int) -> void:
	if n is VisualInstance3D:
		n.layers = layer
	for c in n.get_children():
		_set_layers(c, layer)


func _tint(n: Node, tint: Color) -> void:
	if n is MeshInstance3D and n.mesh != null:
		for s in n.mesh.get_surface_count():
			var m = n.mesh.surface_get_material(s)
			if m is BaseMaterial3D:
				var key := str(m.get_instance_id()) + tint.to_html()
				if not _tints.has(key):
					var d: BaseMaterial3D = m.duplicate()
					d.albedo_color = d.albedo_color * tint
					_tints[key] = d
				n.set_surface_override_material(s, _tints[key])
	for c in n.get_children():
		_tint(c, tint)


func make_soldier(color: Color, layer: int, enemy := false) -> Node3D:
	var root := Node3D.new()
	if _soldier_ps == null and ResourceLoader.exists("res://characters/soldier.glb"):
		_soldier_ps = load("res://characters/soldier.glb")
	if _soldier_ps == null:
		return _block_soldier(color, layer, enemy)
	var model: Node3D = _soldier_ps.instantiate()
	root.add_child(model)                 # glTF import already faces -Z (forward)
	_tint(model, color if enemy else Color(1, 1, 1).lerp(color, 0.22))
	var ap: AnimationPlayer = model.find_child("AnimationPlayer", true, false)
	if ap != null:
		for a in ap.get_animation_list():
			ap.get_animation(a).loop_mode = Animation.LOOP_LINEAR
		ap.play("Idle")
		ap.seek(randf() * 1.5)
	root.set_meta("ap", ap)
	var skel: Skeleton3D = model.find_child("Skeleton3D", true, false)
	var rifle := A.opt("rifle")
	if skel != null and rifle != null:
		var ba := BoneAttachment3D.new()
		ba.bone_name = "mixamorig_RightHand"
		skel.add_child(ba)
		var s := 1.0
		var n: Node = skel
		while n != model and n != null:
			s *= (n as Node3D).scale.x
			n = n.get_parent()
		var g := MeshInstance3D.new()
		g.mesh = rifle
		g.scale = Vector3.ONE / maxf(s, 0.0001) * 0.85
		g.rotation_degrees = HAND_ROT
		g.position = HAND_POS / maxf(s, 0.0001)
		ba.add_child(g)
	_set_layers(root, layer)
	return root


const RAGDOLL_BONES := {
	"mixamorig_Hips": 0.14, "mixamorig_Spine1": 0.13, "mixamorig_Head": 0.11,
	"mixamorig_LeftArm": 0.05, "mixamorig_LeftForeArm": 0.045, "mixamorig_RightArm": 0.05, "mixamorig_RightForeArm": 0.045,
	"mixamorig_LeftUpLeg": 0.075, "mixamorig_LeftLeg": 0.06, "mixamorig_RightUpLeg": 0.075, "mixamorig_RightLeg": 0.06,
}


## Physics ragdoll: the body collapses naturally instead of rotating stiffly.
## `push` is the bullet direction (world space). Returns false if the model has no skeleton.
func ragdoll(visual: Node3D, push: Vector3) -> bool:
	var skel: Skeleton3D = visual.find_child("Skeleton3D", true, false)
	if skel == null:
		return false
	var ap = visual.get_meta("ap", null)
	if ap != null:
		ap.pause()
	var sim := PhysicalBoneSimulator3D.new()
	skel.add_child(sim)
	var gs := skel.global_transform.basis.get_scale().x
	for bname in RAGDOLL_BONES:
		var bi := skel.find_bone(bname)
		if bi < 0:
			continue
		var pb := PhysicalBone3D.new()
		pb.bone_name = bname
		pb.joint_type = PhysicalBone3D.JOINT_TYPE_CONE if bname in ["mixamorig_Head", "mixamorig_LeftArm", "mixamorig_RightArm", "mixamorig_LeftUpLeg", "mixamorig_RightUpLeg", "mixamorig_Spine1"] else PhysicalBone3D.JOINT_TYPE_HINGE
		pb.mass = 4.0
		pb.friction = 0.9
		pb.linear_damp = 0.4
		pb.angular_damp = 2.0
		pb.collision_layer = 0
		pb.collision_mask = 1
		# capsule from this bone towards its first child
		var len := 0.25
		var kids := skel.get_bone_children(bi)
		if not kids.is_empty():
			len = skel.get_bone_rest(kids[0]).origin.length() * gs
		var cs := CollisionShape3D.new()
		var cap := CapsuleShape3D.new()
		cap.radius = RAGDOLL_BONES[bname]
		cap.height = maxf(len, cap.radius * 2.2)
		cs.shape = cap
		pb.add_child(cs)
		pb.body_offset = Transform3D(Basis(), Vector3(0, -len * 0.5 / maxf(gs, 0.0001), 0))
		sim.add_child(pb)
	sim.physical_bones_start_simulation()
	for pb in sim.get_children():
		if pb is PhysicalBone3D:
			pb.apply_central_impulse(push.normalized() * 6.0 + Vector3(0, 1.0, 0))
	return true


func _soldier_idle() -> Animation:
	if _idle_anim == null and _soldier_ps != null:
		var s: Node = _soldier_ps.instantiate()
		var ap: AnimationPlayer = s.find_child("AnimationPlayer", true, false)
		if ap != null and ap.has_animation("Idle"):
			_idle_anim = ap.get_animation("Idle").duplicate()
			for t in range(_idle_anim.get_track_count() - 1, -1, -1):
				if _idle_anim.track_get_type(t) != Animation.TYPE_ROTATION_3D:
					_idle_anim.remove_track(t)
			_idle_anim.loop_mode = Animation.LOOP_LINEAR
		s.free()
	return _idle_anim


func make_hostage() -> Node3D:
	if _hostage_ps == null and ResourceLoader.exists("res://characters/michelle.glb"):
		_hostage_ps = load("res://characters/michelle.glb")
	if _soldier_ps == null and ResourceLoader.exists("res://characters/soldier.glb"):
		_soldier_ps = load("res://characters/soldier.glb")
	if true:                          # Michelle retarget renders flipped - use a civilian-tinted soldier for now
		return make_soldier(Color(1.1, 0.75, 0.45), 1, true)
	var root := Node3D.new()
	var m: Node3D = _hostage_ps.instantiate()
	m.rotation.y = PI
	root.add_child(m)
	var ap: AnimationPlayer = m.find_child("AnimationPlayer", true, false)
	var idle := _soldier_idle()
	if ap != null and idle != null:
		var lib := AnimationLibrary.new()
		lib.add_animation("Idle", idle)
		ap.add_animation_library("h", lib)
		ap.play("h/Idle")
	return root


func animate(visual: Node3D, speed: float, flags: Dictionary = {}) -> void:
	var ap = visual.get_meta("ap", null)
	if ap == null:
		return
	var want := "Idle"
	if speed > 3.8:
		want = "Run"
	elif speed > 0.4:
		want = "Walk"
	if ap.current_animation != want:
		ap.play(want, 0.2)
	# subtle speed modulation on top: crouch slows the walk cycle, firing/reload speeds it slightly
	var base := 1.0 if want == "Idle" else clampf(speed / (5.5 if want == "Run" else 1.6), 0.6, 1.5)
	if flags.get("crouched", false) and want != "Idle":
		base *= 0.6
	if flags.get("firing", false):
		base *= 1.15
	ap.speed_scale = base


func _block_soldier(color: Color, layer: int, enemy := false) -> Node3D:
	var root := Node3D.new()
	var mi := MeshInstance3D.new()
	var cm := CapsuleMesh.new()
	cm.radius = 0.3
	cm.height = 1.8
	mi.mesh = cm
	var m := StandardMaterial3D.new()
	m.albedo_color = Color(0.26, 0.28, 0.22).lerp(color, 0.0 if enemy else 0.45)
	mi.material_override = m
	mi.position.y = 0.9
	mi.layers = layer
	root.add_child(mi)
	return root


const PROPS := {
	"bomb": [["lpg", Vector3(0, 0, 0), 0, 1.3], ["lpg", Vector3(0.5, 0, 0.1), 40, 1.3], ["toolchest", Vector3(0.1, 0, 0.7), 10, 1.0], ["grenade", Vector3(-0.4, 0, 0.5), 80, 1.0]],
	"terminal": [["desk", Vector3.ZERO, 0, 1.0], ["radio", Vector3(-0.4, 0.79, 0), 0, 1.0], ["laptop", Vector3(0.5, 0.79, 0.05), 0, 1.0], ["generator", Vector3(1.6, 0, 0.3), 30, 1.0]],
	"radar": [["generator", Vector3.ZERO, 0, 1.8], ["searchlight", Vector3(0, 1.05, 0), 0, 4.0], ["jerrycan", Vector3(0.9, 0, 0.4), 20, 1.0]],
	"fuel": [["propane", Vector3.ZERO, 0, 2.4], ["propane", Vector3(0.9, 0, 0.2), 0, 2.4], ["barrel1", Vector3(0.3, 0, 1.0), 0, 1.0], ["jerrycan", Vector3(-0.7, 0, 0.6), 50, 1.0]],
	"laptop": [["mil_crate", Vector3.ZERO, 0, 1.0], ["laptop", Vector3(0, 0.46, 0), 180, 1.0]],
	"case": [["toolchest", Vector3.ZERO, 0, 1.2]],
	"ammo": [["mil_crate", Vector3.ZERO, 0, 1.0], ["ammo", Vector3(-0.28, 0.46, 0), 90, 2.0], ["ammo", Vector3(0.28, 0.46, 0), 80, 2.0]],
	"medkit": [["crate1", Vector3.ZERO, 0, 1.0], ["medkit", Vector3(0, 0.35, 0), 0, 1.4]],
}


func make_prop(kind: String) -> Node3D:
	var root := Node3D.new()
	var glow: Color = {"bomb": Color(1, 0.15, 0.1), "terminal": Color(0.2, 1, 0.5), "laptop": Color(0.3, 0.6, 1),
		"ammo": Color(1, 0.95, 0.75), "medkit": Color(1, 0.3, 0.55), "hostage": Color(1, 0.6, 0.2), "zone": Color(0.3, 1, 0.5)}.get(kind, Color(1, 0.85, 0.2))
	if kind == "hostage":
		root.add_child(make_hostage())
	elif kind == "zone":
		var mi := MeshInstance3D.new()
		var cm := CylinderMesh.new()
		cm.top_radius = EXTRACT_RADIUS
		cm.bottom_radius = EXTRACT_RADIUS
		cm.height = 3.0
		cm.cap_top = false
		cm.cap_bottom = false
		mi.mesh = cm
		var m := StandardMaterial3D.new()
		m.albedo_color = Color(0.25, 1.0, 0.45, 0.22)
		m.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
		m.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
		m.cull_mode = BaseMaterial3D.CULL_DISABLED
		mi.material_override = m
		mi.position.y = 1.5
		mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		root.add_child(mi)
		var beam := _part_box(Vector3(0.12, 14, 0.12), Color(0.3, 1, 0.5), 3.0)
		beam.position.y = 7.0
		root.add_child(beam)
	else:
		for p in PROPS.get(kind, []):
			var mesh := A.opt(p[0])
			if mesh == null:
				continue
			var mi := MeshInstance3D.new()
			mi.mesh = mesh
			var sc: float = p[3]
			mi.scale = Vector3.ONE * sc
			mi.rotation.y = deg_to_rad(p[2])
			mi.position = p[1] - Vector3(0, mesh.get_aabb().position.y * sc, 0)
			root.add_child(mi)
	var l := OmniLight3D.new()
	l.light_color = glow
	l.light_energy = 1.5
	l.omni_range = 4.5
	l.position.y = 1.6
	root.add_child(l)
	world.add_child(root)
	return root


func _part_box(sz: Vector3, c: Color, emit: float) -> MeshInstance3D:
	var mi := MeshInstance3D.new()
	var bm := BoxMesh.new()
	bm.size = sz
	mi.mesh = bm
	var m := StandardMaterial3D.new()
	m.albedo_color = c
	m.emission_enabled = emit > 0.0
	m.emission = c
	m.emission_energy_multiplier = emit
	mi.material_override = m
	return mi


# ======================================================================= spawning
func _spawn_players() -> void:
	for i in 2:
		var p := PlayerScript.new()
		var sp: Vector3 = gen.spawn_points[i]
		var face := atan2(sp.x, sp.z)
		world.add_child(p)
		p.setup(self, i, sp + Vector3(0, 0.1, 0), face, TEAM_COLORS[i])
		players.append(p)
		if solo and i == 1:
			p.state = "out"
			p.visible = false
			p.col.disabled = true
			p.set_physics_process(false)


func _spawn_bot(pos: Vector3, kind := "soldier") -> Node:
	var b := BotScript.new()
	world.add_child(b)
	b.setup(self, pos + Vector3(0, 0.1, 0), kind, difficulty)
	return b


func _spawn_enemies() -> void:
	var mods: Array = mission.get("mods", [])
	var spawn_avoid: Array = gen.spawn_points.duplicate()
	for i in (6 + difficulty if solo else 10 + difficulty * 2):
		var kind := "heavy" if randf() < (0.3 if mods.has("heavy") else 0.08) else "soldier"
		_spawn_bot(gen.random_open(spawn_avoid, 40.0), kind)
	for pt in objective.get("points", []):
		for k in 2 + difficulty / 4:
			var a := randf() * TAU
			_spawn_bot(pt["pos"] + Vector3(cos(a), 0, sin(a)) * randf_range(4.0, 9.0), "heavy" if randf() < 0.2 else "soldier")


func spawn_wave(count: int, toward: Vector3) -> void:
	var avoid := []
	for p in players:
		avoid.append(p.global_position)
	for i in count:
		var b = _spawn_bot(gen.random_open(avoid, 30.0), "heavy" if randf() < 0.15 + difficulty * 0.02 else "soldier")
		b.alert = 20.0
		b.last_seen = toward
		b.target = _nearest_player(toward)
	play_sfx("beep", players[0].global_position, -10.0)


func _spawn_pickups() -> void:
	var avoid: Array = gen.spawn_points.duplicate()
	var scarce: bool = mission.get("mods", []).has("scarce")
	for i in (7 if scarce else 12):
		var pos: Vector3 = gen.random_open(avoid, 16.0)
		avoid.append(pos)
		_add_pickup("ammo", pos)
	for i in 6:
		var pos: Vector3 = gen.random_open(avoid, 20.0)
		avoid.append(pos)
		_add_pickup("medkit", pos)
	_add_pickup("medkit", gen.cell_center(1, 1))


func _add_pickup(kind: String, pos: Vector3) -> void:
	var n := make_prop(kind)
	n.position = pos
	pickups.append({"node": n, "kind": kind, "pos": pos, "back": 0.0})


func _nearest_player(pos: Vector3):
	var best = null
	var bd := 1e9
	for p in players:
		if p.state == "alive" and p.global_position.distance_to(pos) < bd:
			bd = p.global_position.distance_to(pos)
			best = p
	return best


# ======================================================================= objectives
func _setup_objective() -> void:
	var task: String = mission.get("task", "defuse")
	var prm: Dictionary = mission.get("params", {})
	var spawn: Array = gen.spawn_points
	objective = {"task": task, "stage": "main", "points": [], "progress": 0.0, "need": 1.0,
		"carrier": null, "item": null, "follow": null, "officer": null, "zone": null}
	var far: Vector3 = gen.random_open(spawn, 110.0)
	objective["extract"] = gen.random_open(spawn + [far], 70.0)
	time_left = float(mission.get("time_limit", 0))
	if time_left <= 0.0:
		time_left = -1.0
	match task:
		"defuse":
			objective["points"] = [{"pos": far, "node": _prop_at("bomb", far), "label": "BOMB", "progress": 0.0, "done": false}]
			objective["need"] = float(prm.get("defuse_time", 10.0))
			if time_left < 0.0:
				time_left = 300.0 - difficulty * 12.0
		"hack":
			objective["points"] = [{"pos": far, "node": _prop_at("terminal", far), "label": "TERMINAL", "progress": 0.0, "done": false}]
			objective["need"] = float(prm.get("hack_time", 45.0))
			wave_t = 10.0
		"destroy":
			var used: Array = spawn.duplicate()
			for i in int(prm.get("targets", 3)):
				var p: Vector3 = gen.random_open(used, 55.0)
				used.append(p)
				objective["points"].append({"pos": p, "node": _prop_at("radar" if i % 2 == 0 else "fuel", p), "label": "TARGET", "progress": 0.0, "done": false})
			objective["need"] = 4.0
		"intel":
			objective["points"] = [{"pos": far, "node": _prop_at("laptop", far), "label": "INTEL", "progress": 0.0, "done": false}]
		"rescue":
			objective["points"] = [{"pos": far, "node": _prop_at("hostage", far), "label": "HOSTAGE", "progress": 0.0, "done": false}]
		"assassinate":
			var o = _spawn_bot(far, "officer")
			objective["officer"] = o
			objective["points"] = [{"pos": far, "node": o, "label": "COMMANDER", "progress": 0.0, "done": false}]
		"survive":
			objective["points"] = [{"pos": far, "node": _prop_at("zone", far), "label": "HOLD", "progress": 0.0, "done": false}]
			objective["need"] = float(prm.get("hold_time", 90.0))
			wave_t = 8.0
		"collect":
			var used2: Array = spawn.duplicate()
			for i in int(prm.get("cases", 4)):
				var p2: Vector3 = gen.random_open(used2, 40.0)
				used2.append(p2)
				objective["points"].append({"pos": p2, "node": _prop_at("case", p2), "label": "SUPPLY", "progress": 0.0, "done": false})


func _prop_at(kind: String, pos: Vector3) -> Node3D:
	var n := make_prop(kind)
	n.position = pos
	return n


func objective_text() -> String:
	var o := objective
	if o.is_empty():
		return ""
	if o["stage"] == "extract":
		return "Get everyone to the extraction zone"
	var left := 0
	for p in o["points"]:
		if not p["done"]:
			left += 1
	match o["task"]:
		"defuse":
			return "Defuse the bomb - hold position next to it"
		"hack":
			return "Hack the terminal - stay close  (%d%%)" % int(100.0 * o["progress"] / o["need"])
		"destroy":
			return "Plant charges on all targets - %d left" % left
		"intel":
			return "Steal the intel" if o["carrier"] == null else "Carry the intel to extraction"
		"rescue":
			return "Find the hostage" if o["follow"] == null else "Escort the hostage to extraction"
		"assassinate":
			return "Eliminate the commander (gold uniform)"
		"survive":
			return "Hold the zone - %ds to go" % int(o["need"] - o["progress"])
		"collect":
			return "Recover the supply cases - %d left" % left
	return ""


func objective_markers() -> Array:
	var out := []
	if objective.is_empty():
		return out
	if objective["stage"] == "extract":
		return [[objective["extract"], "EXTRACT"]]
	for p in objective["points"]:
		if p["done"]:
			continue
		var pos: Vector3 = p["pos"]
		if is_instance_valid(p["node"]):
			pos = p["node"].global_position
		out.append([pos, p["label"]])
	return out


func objective_progress_for(p) -> Array:
	if objective.is_empty() or objective["stage"] != "main" or p.state != "alive":
		return []
	match objective["task"]:
		"defuse", "hack", "survive":
			var pt: Dictionary = objective["points"][0]
			var r := 3.0 if objective["task"] == "defuse" else (5.0 if objective["task"] == "hack" else EXTRACT_RADIUS)
			if _flat_dist(p.global_position, pt["pos"]) < r:
				var lab: String = {"defuse": "DEFUSING", "hack": "UPLOADING", "survive": "HOLDING"}[objective["task"]]
				return [lab, objective["progress"] / objective["need"]]
		"destroy":
			for pt in objective["points"]:
				if not pt["done"] and _flat_dist(p.global_position, pt["pos"]) < 3.0:
					return ["PLANTING CHARGE", pt["progress"] / objective["need"]]
	return []


func _to_extract() -> void:
	if objective["stage"] == "extract":
		return
	objective["stage"] = "extract"
	objective["zone"] = _prop_at("zone", objective["extract"])
	play_sfx("pickup", players[0].global_position, 0.0)
	_flash_banner("OBJECTIVE COMPLETE", "Get to the extraction zone - together.", 4.0)
	spawn_wave(3 + difficulty / 2, objective["extract"])


func _update_objective(dt: float) -> void:
	var o := objective
	if o["stage"] == "extract":
		var need_in := 0
		var inside := 0
		for p in players:
			if p.state == "out":
				continue
			need_in += 1
			if p.state == "alive" and _flat_dist(p.global_position, o["extract"]) < EXTRACT_RADIUS:
				inside += 1
		var esc_ok := true
		if o["task"] == "rescue" and o["follow"] != null:
			esc_ok = _flat_dist(o["follow"].global_position, o["extract"]) < EXTRACT_RADIUS
		if need_in > 0 and inside == need_in and esc_ok:
			_finish(true, "Extraction successful")
		if o["task"] != "rescue" or o["follow"] == null:
			return
	match o["task"]:
		"defuse", "hack", "survive":
			var pt: Dictionary = o["points"][0]
			var r := 3.0 if o["task"] == "defuse" else (5.0 if o["task"] == "hack" else EXTRACT_RADIUS)
			var n := _alive_near(pt["pos"], r)
			if n > 0:
				o["progress"] += dt * (1.0 + 0.5 * (n - 1))
			if o["task"] != "defuse":
				wave_t -= dt
				if wave_t <= 0.0 and (n > 0 or o["progress"] > 0.0):
					wave_t = maxf(7.0, 14.0 - difficulty * 0.6)
					spawn_wave(2 + difficulty / 3, pt["pos"])
			if o["progress"] >= o["need"]:
				pt["done"] = true
				if o["task"] == "defuse":
					play_sfx("pickup", pt["pos"], 0.0)
					_finish(true, "Bomb defused")
				else:
					_to_extract()
		"destroy":
			var left := 0
			for pt in o["points"]:
				if pt["done"]:
					continue
				left += 1
				if _alive_near(pt["pos"], 3.0) > 0:
					pt["progress"] += dt
					if int(pt["progress"] * 2.0) != int((pt["progress"] - dt) * 2.0):
						play_sfx("beep", pt["pos"], -6.0)
					if pt["progress"] >= o["need"]:
						pt["done"] = true
						_say_all("Charge planted")
						_explode(pt["pos"])
						pt["node"].queue_free()
			if left == 0:
				_to_extract()
		"intel", "collect":
			for pt in o["points"]:
				if pt["done"]:
					continue
				for p in players:
					if p.state == "alive" and _flat_dist(p.global_position, pt["node"].global_position) < 1.8:
						pt["done"] = true
						pt["node"].visible = false
						play_sfx("pickup", p.global_position, 0.0)
						if o["task"] == "intel":
							o["carrier"] = p
							p.carrying = "intel"
							_say_all("%s has the intel" % TEAM_NAMES[p.idx])
						else:
							_say_all("Supply case recovered")
						break
			var all_done := true
			for pt in o["points"]:
				all_done = all_done and pt["done"]
			if o["task"] == "collect" and all_done:
				_to_extract()
			elif o["task"] == "intel" and o["carrier"] != null:
				_to_extract()
		"rescue":
			var h: Node3D = o["points"][0]["node"]
			if o["follow"] == null:
				for p in players:
					if p.state == "alive" and _flat_dist(p.global_position, h.global_position) < 2.5:
						o["follow"] = h
						play_sfx("pickup", p.global_position, 0.0)
						_say_all("Hostage found - escort them out")
						_to_extract()
						break
			else:
				var lead = _nearest_player(h.global_position)
				if lead != null:
					var to: Vector3 = lead.global_position - h.global_position
					to.y = 0.0
					if to.length() > 2.2:
						h.global_position += to.normalized() * minf(4.8 * dt, to.length() - 2.2)
						h.look_at(Vector3(lead.global_position.x, h.global_position.y, lead.global_position.z), Vector3.UP)
		"assassinate":
			var off = o["officer"]
			if off == null or not is_instance_valid(off) or off.dead:
				o["points"][0]["done"] = true
				_to_extract()


func drop_carried(p) -> void:
	if p.carrying == "intel":
		p.carrying = ""
		objective["carrier"] = null
		objective["stage"] = "main"
		if objective["zone"] != null:
			objective["zone"].queue_free()
			objective["zone"] = null
		var pt: Dictionary = objective["points"][0]
		pt["done"] = false
		pt["node"].global_position = p.global_position
		pt["node"].visible = true
		_say_all("INTEL DROPPED - pick it up!")


func _alive_near(pos: Vector3, r: float) -> int:
	var n := 0
	for p in players:
		if p.state == "alive" and _flat_dist(p.global_position, pos) < r:
			n += 1
	return n


func _flat_dist(a: Vector3, b: Vector3) -> float:
	return Vector2(a.x - b.x, a.z - b.z).length()


func _say_all(t: String) -> void:
	for p in players:
		p.say(t)


# ======================================================================= events
func on_player_hit(_p, _from: Vector3) -> void:
	pass


func on_player_down(p) -> void:
	stats["downs"] += 1
	var other = players[1 - p.idx]
	if solo:
		p.say("DOWN - your medkit will patch you up" if p.has_medkit else "DOWN - no medkit, you're bleeding out", 5.0)
	elif other.state == "alive":
		other.say("%s IS DOWN - grab a medkit and revive them" % TEAM_NAMES[p.idx], 5.0)
	feed.push_front(["%s  IS DOWN" % TEAM_NAMES[p.idx], 4.0])


func on_player_life_lost(_p) -> void:
	pass


func on_bot_killed(b, by) -> void:
	stats["kills"] += 1
	var who := "EXPLOSION"
	if by != null and by.has_method("say"):
		by.kills += 1
		by.hitmark_kill = true
		who = TEAM_NAMES[by.idx]
	var what: String = {"heavy": "HEAVY", "officer": "COMMANDER"}.get(b.kind, "ENEMY")
	feed.push_front(["%s  >  %s%s" % [who, what, "  (HEADSHOT)" if b.last_headshot else ""], 4.0])
	if feed.size() > 4:
		feed.resize(4)


func alert_bots(pos: Vector3, radius: float, by) -> void:
	for b in get_tree().get_nodes_in_group("bot"):
		if b.global_position.distance_to(pos) < radius:
			b.hear(pos, by)


# ======================================================================= input
func _k(key: int) -> float:
	return 1.0 if Input.is_physical_key_pressed(key) else 0.0


func get_input(i: int) -> Dictionary:
	var mv := Vector2.ZERO
	var lk := Vector2.ZERO
	var crouch := false
	var fire := false
	var now := Time.get_ticks_msec() / 1000.0
	if now - pad_time[i] < 0.6:
		var p: Array = pad_state[i]
		mv += Vector2(float(p[0]), float(p[1]))
		lk += Vector2(float(p[2]), float(p[3]))
		crouch = crouch or float(p[4]) > 0.5
		fire = fire or float(p[5]) > 0.5
	var joys := Input.get_connected_joypads()
	if i < joys.size():
		var d: int = joys[i]
		var l := Vector2(Input.get_joy_axis(d, JOY_AXIS_LEFT_X), -Input.get_joy_axis(d, JOY_AXIS_LEFT_Y))
		var r := Vector2(Input.get_joy_axis(d, JOY_AXIS_RIGHT_X), -Input.get_joy_axis(d, JOY_AXIS_RIGHT_Y))
		if l.length() > 0.2:
			mv += l
		if r.length() > 0.2:
			lk += r
		crouch = crouch or Input.is_joy_button_pressed(d, JOY_BUTTON_LEFT_STICK) or Input.is_joy_button_pressed(d, JOY_BUTTON_B)
		fire = fire or Input.is_joy_button_pressed(d, JOY_BUTTON_RIGHT_STICK) or Input.get_joy_axis(d, JOY_AXIS_TRIGGER_RIGHT) > 0.4
	var k: Array = KEYS[i]
	mv += Vector2(_k(k[3]) - _k(k[2]), _k(k[0]) - _k(k[1]))
	# keyboard look eases from 0 toward target so turning doesn't snap on at full speed
	var kb_target := Vector2(_k(k[7]) - _k(k[6]), _k(k[4]) - _k(k[5]))
	var dt := get_process_delta_time()
	var rate := minf(1.0, dt * 7.0)
	kb_look[i].x = lerp(kb_look[i].x, kb_target.x, rate)
	kb_look[i].y = lerp(kb_look[i].y, kb_target.y, rate)
	if absf(kb_look[i].x) < 0.01 and kb_target.x == 0.0:
		kb_look[i].x = 0.0
	if absf(kb_look[i].y) < 0.01 and kb_target.y == 0.0:
		kb_look[i].y = 0.0
	lk += kb_look[i]
	crouch = crouch or Input.is_physical_key_pressed(k[8])
	fire = fire or Input.is_physical_key_pressed(k[9])
	var pressed: bool = crouch and not crouch_prev[i]
	crouch_prev[i] = crouch
	return {"move": mv.limit_length(1.0), "look": lk.limit_length(1.0), "crouch_pressed": pressed, "fire": fire}


func _poll_udp() -> void:
	var now := Time.get_ticks_msec() / 1000.0
	while udp.get_available_packet_count() > 0:
		var d = JSON.parse_string(udp.get_packet().get_string_from_utf8())
		if d is Dictionary and d.has("p"):
			var arr: Array = d["p"]
			for i in mini(2, arr.size()):
				var p = arr[i]
				if p is Array and p.size() >= 7 and float(p[6]) > 0.5:
					pad_state[i] = p
					pad_time[i] = now


# ======================================================================= main loop
func _process(dt: float) -> void:
	_poll_udp()
	if Input.is_physical_key_pressed(KEY_ESCAPE) and state == "play":
		_finish(false, "Mission aborted")
	for i in 2:
		if solo and i == 1:
			continue
		var p = players[i]
		cams[i].global_transform = p.head.global_transform
		var vm: Node3D = viewmodels[i]
		vm.visible = p.state == "alive"
		var bob := sin(elapsed * 9.0) * 0.01 * minf(1.0, Vector2(p.velocity.x, p.velocity.z).length() / 4.0)
		var rel := 0.25 if p.reload_t > 0.0 else 0.0
		vm.position = vm.position.lerp(Vector3(0.2, -0.19 - rel + bob, -0.5 + p.kick * 3.0), minf(1.0, dt * 14.0))
		var firing: bool = p.fire_cd > 0.06 and p.mag > 0 and p.reload_t <= 0.0 and p.state == "alive"
		vm.get_child(vm.get_child_count() - 1).light_energy = 3.0 if firing else 0.0
		var spr: Node3D = vm.get_child(vm.get_child_count() - 2)
		spr.visible = firing
		spr.rotation.z = randf() * TAU
	var up := []
	for p in players:
		if p.state == "alive":
			up.append(p.idx)
	for i in 2:
		holders[i].visible = (i == 0) if solo else (up.size() != 1 or up[0] == i)
	for e in fx.duplicate():
		e[1] -= dt
		if e[1] <= 0.0:
			if is_instance_valid(e[0]):
				e[0].queue_free()
			fx.erase(e)
	if banner_t > 0.0:
		banner_t -= dt
		banner.modulate.a = clampf(banner_t, 0.0, 1.0)
		sub_banner.modulate.a = banner.modulate.a
	if state != "play":
		end_t -= dt
		if end_t <= 0.0:
			get_tree().quit()
		return
	elapsed += dt
	for e in feed:
		e[1] -= dt
	while not feed.is_empty() and feed[-1][1] <= 0.0:
		feed.pop_back()
	for pk in pickups:
		pk["node"].rotation.y += dt * 0.6
	if time_left > 0.0:
		time_left -= dt
		if objective["task"] == "defuse" and objective["stage"] == "main":
			beep_t -= dt
			if beep_t <= 0.0:
				beep_t = 1.0 if time_left > 30.0 else 0.35
				play_sfx("beep", objective["points"][0]["pos"], -4.0)
		if time_left <= 0.0:
			if objective["task"] == "defuse":
				_explode(objective["points"][0]["pos"])
				_finish(false, "The bomb went off")
			else:
				_finish(false, "Out of time")
			return
	_update_pickups(dt)
	_update_revives(dt)
	_update_objective(dt)
	if state == "play" and up.is_empty():
		_finish(false, "Squad wiped out")
	if state == "play" and mission.get("mods", []).has("reinforcements"):
		wave_t -= dt
		if wave_t <= 0.0 and not objective["task"] in ["hack", "survive"]:
			wave_t = 40.0 - difficulty * 2.0
			var tp = _nearest_player(Vector3.ZERO)
			if tp != null:
				spawn_wave(2 + difficulty / 4, tp.global_position)


func _update_pickups(dt: float) -> void:
	for pk in pickups:
		if pk["back"] > 0.0:
			pk["back"] -= dt
			if pk["back"] <= 0.0:
				pk["node"].visible = true
			continue
		for p in players:
			if p.state != "alive" or _flat_dist(p.global_position, pk["pos"]) > 1.8:
				continue
			if pk["kind"] == "ammo" and p.reloads_left < 12:
				p.reloads_left = mini(12, p.reloads_left + 4)
				p.say("+4 MAGAZINES")
			elif pk["kind"] == "medkit" and not p.has_medkit:
				p.has_medkit = true
				p.say("MEDKIT PICKED UP")
			else:
				continue
			pk["node"].visible = false
			pk["back"] = 60.0
			play_sfx("pickup", p.global_position, -2.0)
			break


func _update_revives(dt: float) -> void:
	if solo:
		var me = players[0]
		if me.state == "down" and me.has_medkit:
			me.revive_t += dt
			if me.revive_t >= REVIVE_TIME + 1.0:
				me.revive_t = 0.0
				me.has_medkit = false
				me.revive()
				stats["revives"] += 1
		else:
			me.revive_t = 0.0
		return
	for p in players:
		var o = players[1 - p.idx]
		if p.state == "alive" and p.has_medkit and o.state == "down" and _flat_dist(p.global_position, o.global_position) < REVIVE_DIST:
			p.revive_t += dt
			if p.revive_t >= REVIVE_TIME:
				p.revive_t = 0.0
				p.has_medkit = false
				o.revive()
				stats["revives"] += 1
		else:
			p.revive_t = 0.0


func _finish(win: bool, reason: String) -> void:
	if state != "play":
		return
	state = "won" if win else "lost"
	end_t = 6.0
	play_sfx("win" if win else "lose", players[0].global_position, 0.0)
	_flash_banner("MISSION COMPLETE" if win else "MISSION FAILED", reason, 99.0)
	banner.add_theme_color_override("font_color", Color(0.4, 1, 0.5) if win else Color(1, 0.3, 0.25))
	if result_path != "":
		var f := FileAccess.open(result_path, FileAccess.WRITE)
		if f != null:
			f.store_string(JSON.stringify({"win": win, "reason": reason, "time": elapsed, "kills": stats["kills"],
				"shots": stats["shots"], "revives": stats["revives"], "downs": stats["downs"],
				"lives": [players[0].lives, players[1].lives], "p_kills": [players[0].kills, players[1].kills]}))
			f.close()


# ======================================================================= fx & sound
func spawn_tracer(a: Vector3, b: Vector3, c: Color) -> void:
	var len := a.distance_to(b)
	if len < 0.5:
		return
	var mi := MeshInstance3D.new()
	var bm := BoxMesh.new()
	bm.size = Vector3(0.015, 0.015, minf(len, 30.0))
	mi.mesh = bm
	var m := StandardMaterial3D.new()
	m.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	m.albedo_color = c
	mi.material_override = m
	mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	world.add_child(mi)
	var mid := a.lerp(b, minf(15.0, len / 2.0) / len)
	mi.look_at_from_position(mid, b, Vector3.UP if absf((b - a).normalized().y) < 0.99 else Vector3.RIGHT)
	fx.append([mi, 0.05])


func spawn_impact(pos: Vector3, blood: bool) -> void:
	var p := CPUParticles3D.new()
	p.one_shot = true
	p.emitting = true
	p.amount = 10
	p.lifetime = 0.35
	p.explosiveness = 1.0
	p.direction = Vector3.UP
	p.spread = 70.0
	p.initial_velocity_min = 1.5
	p.initial_velocity_max = 4.0
	p.scale_amount_min = 0.03
	p.scale_amount_max = 0.07
	var sm := SphereMesh.new()
	sm.radius = 0.5
	sm.height = 1.0
	sm.radial_segments = 6
	sm.rings = 3
	var m := StandardMaterial3D.new()
	m.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	m.albedo_color = Color(0.55, 0.03, 0.03) if blood else Color(1.0, 0.8, 0.45)
	sm.material = m
	p.mesh = sm
	p.position = pos
	world.add_child(p)
	fx.append([p, 0.6])


func _explode(pos: Vector3) -> void:
	play_sfx("explosion", pos, 4.0)
	var l := OmniLight3D.new()
	l.light_color = Color(1, 0.6, 0.25)
	l.light_energy = 12.0
	l.omni_range = 25.0
	l.position = pos + Vector3(0, 2, 0)
	world.add_child(l)
	fx.append([l, 0.5])
	var p := CPUParticles3D.new()
	p.one_shot = true
	p.emitting = true
	p.amount = 40
	p.lifetime = 1.4
	p.explosiveness = 0.95
	p.direction = Vector3.UP
	p.spread = 60.0
	p.initial_velocity_min = 4.0
	p.initial_velocity_max = 12.0
	p.gravity = Vector3(0, -3, 0)
	p.scale_amount_min = 0.6
	p.scale_amount_max = 1.8
	var sm := SphereMesh.new()
	sm.radius = 0.5
	sm.height = 1.0
	var m := StandardMaterial3D.new()
	m.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	m.vertex_color_use_as_albedo = true
	m.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	sm.material = m
	p.mesh = sm
	var g := Gradient.new()
	g.set_color(0, Color(1, 0.75, 0.3, 1))
	g.set_color(1, Color(0.15, 0.15, 0.15, 0))
	p.color_ramp = g
	p.position = pos + Vector3(0, 1, 0)
	world.add_child(p)
	fx.append([p, 1.6])
	for b in get_tree().get_nodes_in_group("bot"):
		if b.global_position.distance_to(pos) < 7.0:
			b.take_damage(500.0, null)


func _load_sounds() -> void:
	for i in 16:
		var ap := AudioStreamPlayer.new()
		add_child(ap)
		sfx_pool.append(ap)
	for dir in [assets_dir.path_join("sounds/gen"), assets_dir.path_join("sounds")]:
		var d := DirAccess.open(str(dir))
		if d == null:
			continue
		for f in d.get_files():
			var ext := f.get_extension().to_lower()
			var path: String = dir.path_join(f)
			var s: AudioStream = null
			if ext == "wav":
				s = AudioStreamWAV.load_from_file(path)
			elif ext == "ogg":
				s = AudioStreamOggVorbis.load_from_file(path)
			elif ext == "mp3":
				s = AudioStreamMP3.load_from_file(path)
			if s != null:
				sounds[f.get_basename().to_lower()] = s


func play_sfx(name: String, pos: Vector3, vol := 0.0) -> void:
	if not sounds.has(name):
		return
	var d := 1e9
	for c in cams:
		d = minf(d, c.global_position.distance_to(pos))
	var db := vol - d * 0.3
	if db < -40.0:
		return
	var ap: AudioStreamPlayer = sfx_pool[sfx_next]
	sfx_next = (sfx_next + 1) % sfx_pool.size()
	ap.stream = sounds[name]
	ap.volume_db = db
	ap.pitch_scale = randf_range(0.95, 1.05)
	ap.play()
