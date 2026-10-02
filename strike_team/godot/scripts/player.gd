extends CharacterBody3D
## One squad member. Left stick = move, left click = crouch (toggle), right stick = look,
## right click = shoot (hold for auto). States: alive -> down (60 s bleed-out) -> respawn or out.

const MAG_SIZE := 30
const START_RELOADS := 12
const WALK := 5.2
const CROUCH_WALK := 2.4
const YAW_RATE := 1.9
const PITCH_RATE := 1.4
const KB_LOOK_RAMP := 7.0            # keyboard look eases from 0 to full over ~1/ramp seconds
const PITCH_LIMIT := 55.0           # degrees - keeps the view from getting lost up / down

var main
var idx := 0
var team_color := Color.BLUE
var lives := 3
var hp := 100.0
var state := "alive"                # alive | down | out
var bleed := 0.0
var yaw := 0.0
var pitch := 0.0
var crouched := false
var mag := MAG_SIZE
var reloads_left := START_RELOADS
var reload_t := 0.0
var fire_cd := 0.0
var has_medkit := false
var revive_t := 0.0
var spawn_pos := Vector3.ZERO
var spawn_yaw := 0.0
var head: Node3D
var visual: Node3D
var arrow: MeshInstance3D
var shape: CapsuleShape3D
var col: CollisionShape3D
var hurt_flash := 0.0
var hitmark := 0.0
var recoil := 0.0
var kick := 0.0
var regen_delay := 0.0
var step_t := 0.0
var msg := ""
var msg_t := 0.0
var carrying := ""
var kills := 0
var anim_t := 0.0
var hitmark_kill := false
var hit_dirs := []
var fire_anim_t := 0.0
var reload_prev := 0.0
var reload_anim_t := 0.0
var aim_t := 0.0                    # 0 = hip-fire, 1 = fully scoped
var aiming := false
const SCOPE_FOV := 32.0
const HIP_FOV := 70.0


func setup(m, i: int, pos: Vector3, look_yaw: float, color: Color) -> void:
	main = m
	idx = i
	team_color = color
	spawn_pos = pos
	spawn_yaw = look_yaw
	position = pos
	yaw = look_yaw
	collision_layer = 2
	collision_mask = 1 | 2 | 4
	if main.mission.get("mods", []).has("scarce"):
		reloads_left = 6
	shape = CapsuleShape3D.new()
	shape.radius = 0.35
	shape.height = 1.8
	col = CollisionShape3D.new()
	col.shape = shape
	col.position.y = 0.9
	add_child(col)
	head = Node3D.new()
	head.position.y = 1.62
	add_child(head)
	# own body + arrow are on a render layer the owner's camera does not draw
	var layer := 2 if idx == 0 else 4
	visual = main.make_soldier(color, layer)
	add_child(visual)
	arrow = MeshInstance3D.new()
	var cone := CylinderMesh.new()
	cone.top_radius = 0.17
	cone.bottom_radius = 0.0
	cone.height = 0.32
	cone.radial_segments = 4
	arrow.mesh = cone
	var am := StandardMaterial3D.new()
	am.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	am.albedo_color = color
	am.no_depth_test = true          # seen through walls: you always know where your mate is
	am.render_priority = 10
	arrow.material_override = am
	arrow.layers = layer
	arrow.position.y = 2.45
	arrow.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	add_child(arrow)


func say(t: String, secs := 2.5) -> void:
	msg = t
	msg_t = secs


func _physics_process(dt: float) -> void:
	var inp: Dictionary = main.get_input(idx)
	hurt_flash = max(0.0, hurt_flash - dt)
	hitmark = max(0.0, hitmark - dt)
	if hitmark <= 0.0:
		hitmark_kill = false
	for hd in hit_dirs:
		hd[1] -= dt
	while not hit_dirs.is_empty() and hit_dirs[0][1] <= 0.0:
		hit_dirs.pop_front()
	msg_t = max(0.0, msg_t - dt)
	recoil = max(0.0, recoil - dt * 0.12)
	kick = lerp(kick, 0.0, dt * 12.0)
	anim_t += dt
	arrow.position.y = 2.45 + sin(anim_t * 3.0) * 0.08
	arrow.rotate_y(dt * 2.0)
	if main.state != "play":
		velocity = Vector3.ZERO
	elif state == "alive":
		_alive(dt, inp)
	elif state == "down":
		_down(dt, inp)
	else:
		velocity = Vector3.ZERO
	if state != "out":
		if not is_on_floor():
			velocity.y -= 22.0 * dt
		move_and_slide()
		if global_position.y < -5.0:
			global_position = spawn_pos
	var target_h := 1.62
	if state == "down":
		target_h = 0.45
	elif crouched:
		target_h = 1.05
	head.position.y = lerp(head.position.y, target_h, dt * 10.0)
	rotation.y = yaw
	head.rotation.x = pitch + kick
	# procedural animation: aim pitch lean + fire recoil + reload sway
	fire_anim_t = max(0.0, fire_anim_t - dt * 4.0)
	if reload_t > 0.0:
		reload_anim_t = min(1.0, reload_anim_t + dt * 4.0)
	else:
		reload_anim_t = max(0.0, reload_anim_t - dt * 4.0)
	var aim_lean: float = clamp(pitch, -0.4, 0.4) * 0.35 if state == "alive" else 0.0
	var recoil_lean: float = -fire_anim_t * 0.18
	var reload_lean: float = reload_anim_t * 0.25
	var base_x := -1.35 if state == "down" else (aim_lean + recoil_lean + reload_lean)
	visual.rotation.x = lerp(visual.rotation.x, base_x, dt * 12.0)
	# strafe lean: tilt the whole body sideways when sliding left/right (local x velocity)
	var local_vx := 0.0
	if state == "alive":
		local_vx = Vector2.from_angle(-yaw).rotated(-PI / 2.0).dot(Vector2(velocity.x, velocity.z))
	var strafe_lean: float = clampf(local_vx * 0.06, -0.25, 0.25)
	var reload_z := sin(main.elapsed * 9.0) * 0.08 * reload_anim_t
	visual.rotation.z = lerp(visual.rotation.z, reload_z + strafe_lean, dt * 10.0)
	visual.scale.y = lerp(visual.scale.y, (0.72 if crouched and state == "alive" else 1.0), dt * 10.0)
	var speed := Vector2(velocity.x, velocity.z).length() if state == "alive" else 0.0
	main.animate(visual, speed, {"crouched": crouched, "firing": fire_anim_t > 0.3, "reloading": reload_t > 0.0})


func _alive(dt: float, inp: Dictionary) -> void:
	if inp["crouch_pressed"]:
		crouched = not crouched
		shape.height = 1.2 if crouched else 1.8
		col.position.y = shape.height / 2.0
	# scope input - only valid when a bullet is actually chambered
	aiming = bool(inp.get("aim", false)) and mag > 0 and reload_t <= 0.0
	aim_t = clamp(aim_t + (dt * 6.5 if aiming else -dt * 7.0), 0.0, 1.0)
	var look_slow: float = lerpf(1.0, 0.35, aim_t)      # scoped = finer aim
	var move_slow: float = lerpf(1.0, 0.45, aim_t)      # scoped = planted stance
	var lk: Vector2 = inp["look"]
	var ms: float = look_slow        # scope sensitivity multiplier applies to mouse too
	yaw -= lk.x * YAW_RATE * look_slow * dt + float(inp.get("yaw_delta", 0.0)) * ms
	pitch = clamp(pitch + lk.y * PITCH_RATE * look_slow * dt + float(inp.get("pitch_delta", 0.0)) * ms, deg_to_rad(-PITCH_LIMIT), deg_to_rad(PITCH_LIMIT))
	var mv: Vector2 = inp["move"]
	var b := Basis(Vector3.UP, yaw)
	var dir := (-b.z * mv.y + b.x * mv.x)
	var spd: float = (CROUCH_WALK if crouched else WALK) * move_slow
	velocity.x = lerp(velocity.x, dir.x * spd, min(1.0, dt * 12.0))
	velocity.z = lerp(velocity.z, dir.z * spd, min(1.0, dt * 12.0))
	if mv.length() > 0.2 and is_on_floor():
		step_t -= dt * mv.length() * (0.6 if crouched else 1.0)
		if step_t <= 0.0:
			step_t = 0.42
			main.play_sfx("step", global_position, -14.0)
	# health regen (not with the "no_regen" modifier)
	regen_delay -= dt
	if regen_delay <= 0.0 and hp < 100.0 and not main.mission.get("mods", []).has("no_regen"):
		hp = min(100.0, hp + 7.0 * dt)
	# weapon: auto reload, 12 reloads then you need ammo crates
	fire_cd -= dt
	if reload_t > 0.0:
		reload_t -= dt
		if reload_t <= 0.0:
			mag = MAG_SIZE
	elif mag <= 0:
		if reloads_left > 0:
			reloads_left -= 1
			reload_t = 2.0
			main.play_sfx("reload", global_position, -4.0)
		elif inp["fire"] and fire_cd <= 0.0:
			fire_cd = 0.5
			main.play_sfx("empty", global_position, -6.0)
			say("OUT OF AMMO - find an ammo crate (white on the map)")
	elif inp["fire"] and fire_cd <= 0.0:
		_shoot()


func _shoot() -> void:
	mag -= 1
	fire_cd = 0.1
	main.stats["shots"] += 1
	var t := head.global_transform
	var base_spread := (0.010 if crouched else 0.022) + recoil
	var spread: float = lerp(base_spread, 0.0008, aim_t)   # scoped shots are near-perfectly on-reticle
	var dir := (-t.basis.z + t.basis.x * randf_range(-spread, spread) + t.basis.y * randf_range(-spread, spread)).normalized()
	var from := t.origin
	var q := PhysicsRayQueryParameters3D.create(from, from + dir * 250.0, 1 | 4)
	q.exclude = [get_rid()]
	var hit := get_world_3d().direct_space_state.intersect_ray(q)
	var end := from + dir * 250.0
	if not hit.is_empty():
		end = hit["position"]
		var c = hit["collider"]
		if c != null and c.is_in_group("bot"):
			var headshot: bool = end.y - c.global_position.y > 1.45
			var body_dmg: float = lerpf(34.0, 110.0, aim_t)   # fully scoped = one-shot a soldier, two-shot a heavy
			c.take_damage(100.0 if headshot else body_dmg, self, headshot)
			hitmark = 0.15
			main.play_sfx("hit", global_position, -8.0)
		main.spawn_impact(end, c != null and c.is_in_group("bot"))
	main.spawn_tracer(from + t.basis.x * 0.2 - t.basis.y * 0.15 - t.basis.z * 0.6, end, Color(1.0, 0.85, 0.5))
	main.play_sfx("shot", global_position, -2.0)
	main.alert_bots(global_position, 35.0, self)
	recoil = min(recoil + 0.005, 0.045)
	kick = 0.018
	fire_anim_t = 1.0


func take_damage(dmg: float, from_pos: Vector3) -> void:
	if state != "alive" or main.state != "play":
		return
	if crouched:
		dmg *= 0.8
	hp -= dmg
	hurt_flash = 0.45
	regen_delay = 5.0
	hit_dirs.append([from_pos, 1.2])
	if hit_dirs.size() > 4:
		hit_dirs.pop_front()
	main.on_player_hit(self, from_pos)
	if hp <= 0.0:
		go_down()


func go_down() -> void:
	state = "down"
	hp = 0.0
	bleed = main.BLEED_TIME
	crouched = false
	reload_t = 0.0
	shape.height = 0.8
	col.position.y = 0.4
	aim_t = 0.0
	aiming = false
	# collapse animation: whichever direction we were hit from pushes the ragdoll
	var push := Vector3.ZERO
	if not hit_dirs.is_empty():
		push = global_position - hit_dirs.back()[0]
	push.y = 0.0
	if push.length() < 0.1:
		push = -global_transform.basis.z
	main.ragdoll(visual, push)
	main.drop_carried(self)
	main.play_sfx("down", global_position, 0.0)
	main.on_player_down(self)


func _down(dt: float, inp: Dictionary) -> void:
	velocity.x = 0.0
	velocity.z = 0.0
	var lk: Vector2 = inp["look"]
	yaw -= lk.x * YAW_RATE * 0.5 * dt
	bleed -= dt
	if bleed <= 0.0:
		lose_life()


func revive() -> void:
	state = "alive"
	hp = 50.0
	regen_delay = 3.0
	shape.height = 1.8
	col.position.y = 0.9
	_rebuild_visual()
	main.play_sfx("revive", global_position, 0.0)
	say("REVIVED - get back in the fight")


func _rebuild_visual() -> void:
	# Ragdoll leaves a PhysicalBoneSimulator in the visual - swap in a fresh standing model.
	if visual != null and is_instance_valid(visual):
		visual.queue_free()
	var layer := 2 if idx == 0 else 4
	visual = main.make_soldier(team_color, layer)
	add_child(visual)


func lose_life() -> void:
	lives -= 1
	if lives > 0:
		global_position = spawn_pos
		velocity = Vector3.ZERO
		yaw = spawn_yaw
		pitch = 0.0
		state = "alive"
		hp = 100.0
		mag = MAG_SIZE
		reload_t = 0.0
		shape.height = 1.8
		col.position.y = 0.9
		_rebuild_visual()
		say("Bled out - %d %s left. Back at spawn." % [lives, "life" if lives == 1 else "lives"], 4.0)
	else:
		state = "out"
		visible = false
		col.disabled = true
	main.on_player_life_lost(self)
