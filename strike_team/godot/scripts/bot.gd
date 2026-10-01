extends CharacterBody3D
## Enemy soldier: patrols, spots players by line of sight, hunts the last seen position,
## strafes and shoots with distance / crouch dependent accuracy.

var main
var kind := "soldier"               # soldier | heavy | officer
var hp := 100.0
var speed := 3.2
var accuracy := 0.3
var damage := 9.0
var view_dist := 42.0
var home := Vector3.ZERO
var target = null
var last_seen := Vector3.ZERO
var alert := 0.0
var sees := false
var fire_cd := 1.0
var think_t := 0.0
var wander := Vector3.ZERO
var avoid_t := 0.0
var avoid_dir := Vector3.ZERO
var strafe := 1.0
var dead := false
var last_headshot := false
var visual: Node3D


func setup(m, pos: Vector3, k: String, diff: int) -> void:
	main = m
	kind = k
	position = pos
	home = pos
	wander = pos
	add_to_group("bot")
	collision_layer = 4
	collision_mask = 1 | 2 | 4
	var mods: Array = main.mission.get("mods", [])
	accuracy = 0.22 + diff * 0.035 + (0.15 if mods.has("sharpshooters") else 0.0)
	damage = 8.0 + diff * 0.6
	var color := Color(0.5, 0.56, 0.46)
	if kind == "heavy":
		hp = 240.0
		speed = 2.3
		damage *= 1.5
		color = Color(0.3, 0.32, 0.32)
	elif kind == "officer":
		hp = 320.0
		speed = 2.8
		accuracy += 0.1
		color = Color(1.1, 0.85, 0.35)
	var sh := CapsuleShape3D.new()
	sh.radius = 0.35
	sh.height = 1.8
	var cs := CollisionShape3D.new()
	cs.shape = sh
	cs.position.y = 0.9
	add_child(cs)
	visual = main.make_soldier(color, 1, true)
	add_child(visual)
	fire_cd = randf_range(0.5, 2.0)
	strafe = 1.0 if randf() < 0.5 else -1.0


func take_damage(dmg: float, by, headshot := false) -> void:
	if dead:
		return
	last_headshot = headshot
	hp -= dmg
	alert = 10.0
	if by != null:
		target = by
		last_seen = by.global_position
	if hp <= 0.0:
		_die(by)


func hear(pos: Vector3, by) -> void:
	if dead:
		return
	if alert <= 0.0 or target == null:
		target = by
		last_seen = pos
	alert = max(alert, 6.0)


func _die(by) -> void:
	dead = true
	remove_from_group("bot")
	collision_layer = 0
	collision_mask = 1
	main.on_bot_killed(self, by)
	var tw := create_tween()
	var ap = visual.get_meta("ap", null)
	if ap != null:
		ap.pause()
	tw.tween_property(visual, "rotation:x", -1.45, 0.45).set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_IN)
	tw.tween_interval(6.0)
	tw.tween_callback(queue_free)


func _eye() -> Vector3:
	return global_position + Vector3(0, 1.6, 0)


func _can_see(p) -> bool:
	var to: Vector3 = p.head.global_position
	var q := PhysicsRayQueryParameters3D.create(_eye(), to, 1)
	return get_world_3d().direct_space_state.intersect_ray(q).is_empty()


func _physics_process(dt: float) -> void:
	if dead:
		velocity = Vector3(0, velocity.y - 22.0 * dt, 0)
		move_and_slide()
		return
	if main.state != "play":
		return
	think_t -= dt
	alert -= dt
	fire_cd -= dt
	if think_t <= 0.0:
		think_t = randf_range(0.2, 0.35)
		_think()
	var goal := wander
	var spd := speed * 0.45
	var face := Vector3.ZERO
	if target != null and target.state == "alive" and sees:
		face = target.global_position
		var d := global_position.distance_to(target.global_position)
		var to: Vector3 = target.global_position - global_position
		to.y = 0.0
		to = to.normalized()
		if d > 16.0:
			goal = target.global_position
			spd = speed
		else:
			goal = global_position + to.cross(Vector3.UP) * strafe * 3.0 - (to * 2.0 if d < 7.0 else Vector3.ZERO)
			spd = speed * 0.6
		if fire_cd <= 0.0 and main.elapsed > 8.0:
			_fire(d)
	elif alert > 0.0:
		goal = last_seen
		spd = speed
		face = last_seen
		if global_position.distance_to(last_seen) < 2.0:
			alert = min(alert, 1.0)
	elif global_position.distance_to(wander) < 1.5 or randf() < 0.002:
		wander = home + Vector3(randf_range(-10, 10), 0, randf_range(-10, 10))
	var dir := goal - global_position
	dir.y = 0.0
	if dir.length() > 0.6:
		dir = dir.normalized()
	else:
		dir = Vector3.ZERO
	if avoid_t > 0.0:
		avoid_t -= dt
		dir = avoid_dir
	elif is_on_wall() and dir != Vector3.ZERO:
		avoid_t = randf_range(0.6, 1.2)
		avoid_dir = dir.rotated(Vector3.UP, PI / 2.0 * (1.0 if randf() < 0.5 else -1.0))
		strafe = -strafe
	velocity.x = lerp(velocity.x, dir.x * spd, min(1.0, dt * 8.0))
	velocity.z = lerp(velocity.z, dir.z * spd, min(1.0, dt * 8.0))
	if not is_on_floor():
		velocity.y -= 22.0 * dt
	move_and_slide()
	main.animate(visual, Vector2(velocity.x, velocity.z).length())
	if face == Vector3.ZERO and Vector2(velocity.x, velocity.z).length() > 0.3:
		face = global_position + Vector3(velocity.x, 0, velocity.z)
	if face != Vector3.ZERO:
		var want := atan2(-(face.x - global_position.x), -(face.z - global_position.z))
		rotation.y = lerp_angle(rotation.y, want, min(1.0, dt * 8.0))


func _think() -> void:
	sees = false
	var best = null
	var best_d := view_dist * (0.6 if main.mission.get("mods", []).has("fog") or main.mission.get("time", "day") == "night" else 1.0)
	for p in main.players:
		if p.state != "alive":
			continue
		var d := global_position.distance_to(p.global_position)
		if d > best_d:
			continue
		# a 200 degree field of view unless already alerted
		var fwd := -global_transform.basis.z
		var to: Vector3 = (p.global_position - global_position).normalized()
		if alert <= 0.0 and fwd.dot(to) < -0.17 and d > 6.0:
			continue
		if _can_see(p):
			best = p
			best_d = d
	if best != null:
		if alert <= 0.0:
			fire_cd = max(fire_cd, randf_range(0.5, 1.0))   # reaction time
		target = best
		sees = true
		last_seen = best.global_position
		alert = 8.0


func _fire(d: float) -> void:
	fire_cd = randf_range(0.45, 1.0) * (1.4 if kind == "heavy" else 1.0)
	var chance := accuracy * clampf(1.15 - d / 55.0, 0.15, 1.0)
	if target.crouched:
		chance *= 0.65
	if Vector2(target.velocity.x, target.velocity.z).length() > 3.0:
		chance *= 0.75
	var muzzle := global_position + Vector3(0, 1.35, 0) - global_transform.basis.z * 0.6
	var aim: Vector3 = target.head.global_position - Vector3(0, 0.4, 0)
	var hit := randf() < chance
	if not hit:
		aim += Vector3(randf_range(-1.2, 1.2), randf_range(-0.6, 0.9), randf_range(-1.2, 1.2))
	main.spawn_tracer(muzzle, aim, Color(1.0, 0.45, 0.3))
	main.play_sfx("enemy_shot", global_position, -4.0)
	if hit:
		target.take_damage(damage, global_position)
