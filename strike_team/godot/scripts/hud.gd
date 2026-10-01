extends Control
## Per-player HUD over one half of the split screen. Safe-zone layout (nothing overlaps):
##   top-left    objective + timer           top-centre  compass (objective / mate bearings)
##   top-right   kill feed                    centre      crosshair, hit marker, prompts
##   bottom-left GTA-style radar + bars       bottom-right weapon / ammo / lives / medkit

const COMPASS_FOV := 150.0
const RADAR_RANGE := 60.0            # metres from centre to the radar's side edge

var main
var idx := 0
var radar: Control
var f_bold: Font
var f_semi: Font
var f_num: Font
var vignette: GradientTexture2D
var s := 1.0                         # UI scale for this view


func _ready() -> void:
	f_bold = _font("Rajdhani-Bold")
	f_semi = _font("Rajdhani-SemiBold")
	f_num = _font("Teko")
	var g := Gradient.new()
	g.set_color(0, Color(0, 0, 0, 0))
	g.set_color(1, Color(0, 0, 0, 1))
	g.add_point(0.55, Color(0, 0, 0, 0))
	vignette = GradientTexture2D.new()
	vignette.gradient = g
	vignette.fill = GradientTexture2D.FILL_RADIAL
	vignette.fill_from = Vector2(0.5, 0.5)
	vignette.fill_to = Vector2(1.05, 1.05)
	radar = Control.new()
	radar.clip_contents = true
	radar.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(radar)
	radar.draw.connect(_draw_radar)


func _font(n: String) -> Font:
	var p := "res://fonts/%s.ttf" % n
	return load(p) if ResourceLoader.exists(p) else ThemeDB.fallback_font


func _process(_dt: float) -> void:
	s = clampf(minf(size.x / 960.0, size.y / 820.0), 0.62, 1.35)
	var rw := 250.0 * s
	var rh := 160.0 * s
	radar.position = Vector2(24.0 * s, size.y - 24.0 * s - rh - 16.0 * s)
	radar.size = Vector2(rw, rh)
	queue_redraw()
	radar.queue_redraw()


# ------------------------------------------------------------------ text helpers
func _t(f: Font, pos: Vector2, t: String, sz: float, c := Color.WHITE, align := HORIZONTAL_ALIGNMENT_LEFT, w := -1.0, outline := 0.0) -> void:
	var px := int(sz * s)
	if outline > 0.0:
		draw_string_outline(f, pos, t, align, w, px, int(outline * s), Color(0, 0, 0, 0.75))
	else:
		draw_string(f, pos + Vector2(0, 1.5 * s), t, align, w, px, Color(0, 0, 0, 0.55))
	draw_string(f, pos, t, align, w, px, c)


func _tw(f: Font, t: String, sz: float) -> float:
	return f.get_string_size(t, HORIZONTAL_ALIGNMENT_LEFT, -1, int(sz * s)).x


func _panel(r: Rect2, a := 0.55) -> void:
	# CoD-style slanted dark panel
	var k := 10.0 * s
	draw_colored_polygon(PackedVector2Array([r.position + Vector2(k, 0), r.position + Vector2(r.size.x, 0),
		r.position + r.size - Vector2(k, 0), r.position + Vector2(0, r.size.y)]), Color(0.03, 0.04, 0.05, a))


# ------------------------------------------------------------------ main draw
func _draw() -> void:
	if main == null or main.players.size() <= idx:
		return
	var p = main.players[idx]
	var W := size.x
	var H := size.y
	var team: Color = main.TEAM_COLORS[idx]
	var blink := int(Time.get_ticks_msec() / 300) % 2 == 0
	# cinematic vignette, red when hurt, dark red when down
	var hurt: float = p.hurt_flash * 0.8
	if p.state == "alive" and p.hp < 40.0:
		hurt += (40.0 - p.hp) / 60.0
	draw_texture_rect(vignette, Rect2(0, 0, W, H), false, Color(1, 1, 1, 0.35))
	if hurt > 0.0:
		draw_texture_rect(vignette, Rect2(0, 0, W, H), false, Color(0.75, 0.0, 0.0, minf(0.9, hurt)))
	draw_rect(Rect2(0, 0, W, 3.0 * s), team)
	if p.state == "down":
		_draw_down(p, W, H)
	else:
		_draw_crosshair(p, W, H)
		_draw_damage_dirs(p, W, H)
	_draw_world_markers(p, W, H)
	_draw_compass(p, W)
	_draw_objective(W)
	_draw_feed(W)
	_draw_weapon(p, W, H, team, blink)
	_draw_radar_frame(p, team)
	_draw_prompts(p, W, H, blink)


func _draw_crosshair(p, W: float, H: float) -> void:
	var c := Vector2(W / 2.0, H / 2.0)
	var g: float = (5.0 + p.recoil * 380.0 + (0.0 if p.crouched else 3.0)) * s
	var l := 8.0 * s
	for d in [Vector2(1, 0), Vector2(-1, 0), Vector2(0, 1), Vector2(0, -1)]:
		draw_line(c + d * (g + 1.0), c + d * (g + l + 1.0), Color(0, 0, 0, 0.5), 3.5 * s)
		draw_line(c + d * g, c + d * (g + l), Color(1, 1, 1, 0.95), 1.8 * s)
	draw_circle(c, 1.4 * s, Color(1, 1, 1, 0.9))
	if p.hitmark > 0.0:
		var hc := Color(1, 0.25, 0.2) if p.hitmark_kill else Color(1, 1, 1)
		for d in [Vector2(1, 1), Vector2(-1, 1), Vector2(1, -1), Vector2(-1, -1)]:
			draw_line(c + d * 6.0 * s, c + d * 14.0 * s, hc, 2.4 * s)


func _draw_damage_dirs(p, W: float, H: float) -> void:
	var c := Vector2(W / 2.0, H / 2.0)
	for hd in p.hit_dirs:
		var rel: Vector3 = hd[0] - p.global_position
		var v := Vector2(rel.x, rel.z).rotated(p.yaw)
		var ang := atan2(v.y, v.x)
		var a: float = clampf(hd[1], 0.0, 1.0)
		draw_arc(c, 90.0 * s, ang - 0.35, ang + 0.35, 16, Color(1, 0.1, 0.05, 0.85 * a), 7.0 * s)


func _draw_down(p, W: float, H: float) -> void:
	draw_rect(Rect2(0, 0, W, H), Color(0.18, 0.0, 0.0, 0.45))
	var c := Vector2(W / 2.0, H * 0.46)
	var frac: float = p.bleed / main.BLEED_TIME
	draw_arc(c, 46.0 * s, 0, TAU, 48, Color(0, 0, 0, 0.5), 8.0 * s)
	draw_arc(c, 46.0 * s, -PI / 2.0, -PI / 2.0 + TAU * frac, 48, Color(1, 0.25, 0.2), 6.0 * s)
	_t(f_num, c + Vector2(-60 * s, 14 * s), "%d" % int(ceil(p.bleed)), 44, Color.WHITE, HORIZONTAL_ALIGNMENT_CENTER, 120 * s)
	_t(f_bold, Vector2(0, c.y + 92 * s), "INCAPACITATED", 34, Color(1, 0.3, 0.25), HORIZONTAL_ALIGNMENT_CENTER, W)
	var o = main.players[1 - idx]
	if main.solo:
		var t2 := "Using your medkit..." if p.has_medkit else "No medkit - you'll lose a life when the timer ends"
		_t(f_semi, Vector2(0, c.y + 122 * s), t2, 19, Color(0.9, 0.9, 0.9), HORIZONTAL_ALIGNMENT_CENTER, W)
		if p.revive_t > 0.0:
			_progress(Vector2(W / 2.0, c.y + 175 * s), p.revive_t / (main.REVIVE_TIME + 1.0), "SELF-REVIVE", Color(0.4, 1, 0.55))
		return
	var tip := "Your teammate is bringing a medkit" if o.state == "alive" and o.has_medkit else ("Your teammate must find a MEDKIT" if o.state == "alive" else "No one can revive you")
	_t(f_semi, Vector2(0, c.y + 122 * s), tip, 19, Color(0.9, 0.9, 0.9), HORIZONTAL_ALIGNMENT_CENTER, W)


func _draw_compass(p, W: float) -> void:
	var cw := minf(460.0 * s, W * 0.5)
	var cx := W / 2.0
	var y := 18.0 * s
	var heading := fposmod(-rad_to_deg(p.yaw), 360.0)
	draw_rect(Rect2(cx - cw / 2.0, y, cw, 26.0 * s), Color(0.02, 0.03, 0.04, 0.45))
	var names := {0: "N", 45: "NE", 90: "E", 135: "SE", 180: "S", 225: "SW", 270: "W", 315: "NW"}
	for a in range(0, 360, 15):
		var off := wrapf(a - heading, -180.0, 180.0)
		if absf(off) > COMPASS_FOV / 2.0:
			continue
		var x := cx + off / COMPASS_FOV * cw
		var alpha := 1.0 - absf(off) / (COMPASS_FOV / 2.0) * 0.7
		if names.has(a):
			_t(f_bold, Vector2(x - 20 * s, y + 20 * s), names[a], 17 if a % 90 == 0 else 13, Color(1, 1, 1, alpha), HORIZONTAL_ALIGNMENT_CENTER, 40 * s)
		else:
			draw_line(Vector2(x, y + 4 * s), Vector2(x, y + 10 * s), Color(1, 1, 1, alpha * 0.6), 1.5 * s)
	draw_colored_polygon(PackedVector2Array([Vector2(cx, y + 27 * s), Vector2(cx - 5 * s, y + 33 * s), Vector2(cx + 5 * s, y + 33 * s)]), Color.WHITE)
	# bearings to objective / teammate
	var marks := []
	for m in main.objective_markers():
		marks.append([m[0], Color(1, 0.82, 0.2)])
	var o = main.players[1 - idx]
	if o.state != "out" and not main.solo:
		marks.append([o.global_position, Color(1, 0.3, 0.3) if o.state == "down" else Color(0.3, 1, 0.45)])
	for m in marks:
		var rel: Vector3 = m[0] - p.global_position
		var v := Vector2(rel.x, rel.z).rotated(p.yaw)
		var off := rad_to_deg(atan2(v.x, -v.y))
		off = clampf(off, -COMPASS_FOV / 2.0, COMPASS_FOV / 2.0)
		var x := cx + off / COMPASS_FOV * cw
		var c: Color = m[1]
		draw_colored_polygon(PackedVector2Array([Vector2(x, y + 2 * s), Vector2(x + 6 * s, y + 9 * s), Vector2(x, y + 16 * s), Vector2(x - 6 * s, y + 9 * s)]), c)


func _draw_objective(W: float) -> void:
	var x := 22.0 * s
	var y := 18.0 * s
	var txt: String = main.objective_text()
	var w := minf(maxf(_tw(f_semi, txt, 19) + 34 * s, 230 * s), W * 0.42)
	_panel(Rect2(x, y, w, 52 * s))
	draw_rect(Rect2(x + 10 * s, y + 8 * s, 3 * s, 36 * s), Color(1, 0.8, 0.2))
	_t(f_bold, Vector2(x + 20 * s, y + 21 * s), "OBJECTIVE", 14, Color(1, 0.8, 0.2))
	_t(f_semi, Vector2(x + 20 * s, y + 42 * s), txt, 19, Color.WHITE, HORIZONTAL_ALIGNMENT_LEFT, w - 26 * s)
	if main.time_left > 0.0:
		var tl: float = main.time_left
		var urgent := tl < 30.0
		var tc := Color(1, 0.3, 0.25) if urgent else Color.WHITE
		_panel(Rect2(x, y + 58 * s, 92 * s, 34 * s), 0.6)
		_t(f_num, Vector2(x + 14 * s, y + 87 * s), "%d:%02d" % [int(tl) / 60, int(tl) % 60], 34, tc)


func _draw_feed(W: float) -> void:
	var y := 22.0 * s
	for e in main.feed:
		var a := clampf(e[1], 0.0, 1.0)
		var txt: String = e[0]
		var w := _tw(f_semi, txt, 16) + 20 * s
		_panel(Rect2(W - 22 * s - w, y, w, 24 * s), 0.5 * a)
		_t(f_semi, Vector2(W - 22 * s - w + 10 * s, y + 18 * s), txt, 16, Color(1, 1, 1, a))
		y += 28 * s


func _draw_weapon(p, W: float, H: float, team: Color, blink: bool) -> void:
	var pw := 250.0 * s
	var ph := 92.0 * s
	var x := W - 24.0 * s - pw
	var y := H - 24.0 * s - ph
	_panel(Rect2(x, y, pw, ph))
	_t(f_bold, Vector2(x + 18 * s, y + 22 * s), "M-762  BATTLE RIFLE", 14, Color(0.8, 0.82, 0.85))
	var low: bool = p.mag <= 6
	var mc := Color(1, 0.35, 0.3) if low else Color.WHITE
	var mag_txt := "%d" % p.mag
	_t(f_num, Vector2(x + 18 * s, y + 78 * s), mag_txt, 62, mc)
	var mx := x + 22 * s + _tw(f_num, mag_txt, 62)
	_t(f_num, Vector2(mx, y + 74 * s), "/ %d" % (p.reloads_left * p.MAG_SIZE), 30, Color(0.75, 0.77, 0.8) if p.reloads_left > 2 else Color(1, 0.5, 0.3))
	# magazine pips
	var px := x + pw - 22 * s
	for i in p.MAG_SIZE:
		var col := Color(1, 1, 1, 0.9) if i < p.mag else Color(1, 1, 1, 0.15)
		var bx: float = px - (i % 15) * 7.0 * s
		var by: float = y + 50 * s + (i / 15) * 13.0 * s
		draw_rect(Rect2(bx - 4 * s, by, 4 * s, 10 * s), col)
	# lives + medkit
	for i in 3:
		var c := team if i < p.lives else Color(1, 1, 1, 0.15)
		var cx := x + pw - 30 * s - i * 22 * s
		draw_colored_polygon(PackedVector2Array([Vector2(cx, y + 12 * s), Vector2(cx + 8 * s, y + 18 * s), Vector2(cx + 6 * s, y + 30 * s), Vector2(cx - 6 * s, y + 30 * s), Vector2(cx - 8 * s, y + 18 * s)]), c)
	if p.has_medkit:
		var m := Vector2(x - 34 * s, y + ph - 26 * s)
		draw_rect(Rect2(m - Vector2(16, 14) * s, Vector2(32, 28) * s), Color(0.95, 0.95, 0.95, 0.95))
		draw_rect(Rect2(m - Vector2(10, 3.5) * s, Vector2(20, 7) * s), Color(0.9, 0.1, 0.15))
		draw_rect(Rect2(m - Vector2(3.5, 10) * s, Vector2(7, 20) * s), Color(0.9, 0.1, 0.15))
	if p.crouched and p.state == "alive":
		_t(f_bold, Vector2(x + 18 * s, y - 8 * s), "CROUCHED", 14, Color(0.8, 0.85, 0.9))


func _draw_prompts(p, W: float, H: float, blink: bool) -> void:
	var y := H / 2.0 + 64.0 * s
	if p.state == "alive":
		if p.reload_t > 0.0:
			_t(f_bold, Vector2(0, y), "RELOADING", 18, Color.WHITE, HORIZONTAL_ALIGNMENT_CENTER, W)
			draw_rect(Rect2(W / 2.0 - 50 * s, y + 8 * s, 100 * s, 4 * s), Color(1, 1, 1, 0.2))
			draw_rect(Rect2(W / 2.0 - 50 * s, y + 8 * s, 100 * s * (1.0 - p.reload_t / 2.0), 4 * s), Color.WHITE)
			y += 34 * s
		elif p.mag == 0 and p.reloads_left == 0 and blink:
			_t(f_bold, Vector2(0, y), "NO AMMO  -  FIND AN AMMO CRATE", 19, Color(1, 0.4, 0.3), HORIZONTAL_ALIGNMENT_CENTER, W)
			y += 34 * s
		if p.revive_t > 0.0:
			_progress(Vector2(W / 2.0, y + 26 * s), p.revive_t / main.REVIVE_TIME, "REVIVING", Color(0.4, 1, 0.55))
			y += 80 * s
		var op: Array = main.objective_progress_for(p)
		if not op.is_empty():
			_progress(Vector2(W / 2.0, y + 26 * s), op[1], op[0], Color(1, 0.82, 0.25))
	var o = main.players[1 - idx]
	if o.state == "down" and p.state == "alive":
		var t := "%s DOWN  ·  %ds  ·  %s" % [main.TEAM_NAMES[o.idx], int(o.bleed), "GO REVIVE" if p.has_medkit else "GRAB A MEDKIT"]
		var w := _tw(f_bold, t, 20) + 40 * s
		_panel(Rect2(W / 2.0 - w / 2.0, 58 * s, w, 32 * s), 0.75)
		_t(f_bold, Vector2(0, 81 * s), t, 20, Color(1, 0.35, 0.3) if blink else Color.WHITE, HORIZONTAL_ALIGNMENT_CENTER, W)
	elif o.state == "out" and p.state == "alive" and not main.solo:
		_t(f_semi, Vector2(0, 80 * s), "%s IS OUT  -  YOU'RE ON YOUR OWN" % main.TEAM_NAMES[o.idx], 16, Color(0.85, 0.85, 0.85), HORIZONTAL_ALIGNMENT_CENTER, W)
	if p.msg_t > 0.0:
		var a := clampf(p.msg_t, 0.0, 1.0)
		var w2 := _tw(f_semi, p.msg, 20) + 40 * s
		_panel(Rect2(W / 2.0 - w2 / 2.0, H * 0.7, w2, 34 * s), 0.6 * a)
		_t(f_semi, Vector2(0, H * 0.7 + 24 * s), p.msg, 20, Color(1, 1, 1, a), HORIZONTAL_ALIGNMENT_CENTER, W)


func _progress(c: Vector2, frac: float, label: String, col: Color) -> void:
	var r := 22.0 * s
	draw_arc(c, r, 0, TAU, 40, Color(0, 0, 0, 0.5), 6.0 * s)
	draw_arc(c, r, -PI / 2.0, -PI / 2.0 + TAU * clampf(frac, 0.0, 1.0), 40, col, 4.5 * s)
	_t(f_num, c + Vector2(-40 * s, 9 * s), "%d" % int(frac * 100.0), 24, Color.WHITE, HORIZONTAL_ALIGNMENT_CENTER, 80 * s)
	_t(f_bold, c + Vector2(-150 * s, r + 22 * s), label, 16, col, HORIZONTAL_ALIGNMENT_CENTER, 300 * s)


func _draw_world_markers(p, W: float, H: float) -> void:
	var cam: Camera3D = main.cams[idx]
	var list := []
	for m in main.objective_markers():
		list.append([m[0] + Vector3(0, 2.2, 0), m[1], Color(1, 0.82, 0.2), true])
	var o = main.players[1 - idx]
	if main.solo:
		pass
	elif o.state == "down":
		list.append([o.global_position + Vector3(0, 1.2, 0), "REVIVE", Color(1, 0.3, 0.3), true])
	elif o.state == "alive":
		list.append([o.global_position + Vector3(0, 2.75, 0), main.TEAM_NAMES[o.idx], main.TEAM_COLORS[o.idx].lightened(0.3), false])
	var want := []
	if p.reloads_left <= 3:
		want.append(["ammo", "AMMO", Color(1, 1, 0.9)])
	if not p.has_medkit and (o.state == "down" or (main.solo and p.hp < 50.0)):
		want.append(["medkit", "MEDKIT", Color(1, 0.45, 0.7)])
	for wv in want:
		var best = null
		var bd := 1e9
		for pk in main.pickups:
			if pk["kind"] == wv[0] and pk["back"] <= 0.0:
				var d: float = p.global_position.distance_to(pk["pos"])
				if d < bd:
					bd = d
					best = pk
		if best != null:
			list.append([best["pos"] + Vector3(0, 1.4, 0), wv[1], wv[2], true])
	var top := 110.0 * s
	for m in list:
		var pos: Vector3 = m[0]
		var behind := cam.is_position_behind(pos)
		var sp := cam.unproject_position(pos)
		var clamp_it: bool = m[3]
		if behind:
			if not clamp_it:
				continue
			sp = Vector2(W - sp.x, H - 150 * s)
		elif not clamp_it and (sp.x < 0 or sp.x > W or sp.y < 0 or sp.y > H):
			continue
		sp.x = clampf(sp.x, 40 * s, W - 40 * s)
		sp.y = clampf(sp.y, top, H - 150 * s)
		var col: Color = m[2]
		var dist := int(p.global_position.distance_to(pos))
		if clamp_it:
			draw_colored_polygon(PackedVector2Array([sp + Vector2(0, -8) * s, sp + Vector2(8, 0) * s, sp + Vector2(0, 8) * s, sp + Vector2(-8, 0) * s]), col)
			draw_polyline(PackedVector2Array([sp + Vector2(0, -8) * s, sp + Vector2(8, 0) * s, sp + Vector2(0, 8) * s, sp + Vector2(-8, 0) * s, sp + Vector2(0, -8) * s]), Color(0, 0, 0, 0.6), 1.5 * s)
		_t(f_bold, sp + Vector2(-70 * s, -14 * s), "%s  %dm" % [m[1], dist], 14, col, HORIZONTAL_ALIGNMENT_CENTER, 140 * s, 4.0)


# ------------------------------------------------------------------ GTA-style radar
func _draw_radar_frame(p, team: Color) -> void:
	var r := Rect2(radar.position, radar.size)
	draw_rect(r.grow(3.0 * s), Color(0, 0, 0, 0.75), false, 3.0 * s)
	# health (green) + ammo reserve (blue) bars under the map, GTA V style
	var by := r.end.y + 6.0 * s
	var bh := 8.0 * s
	var hw := r.size.x * 0.66
	draw_rect(Rect2(r.position.x, by, hw, bh), Color(0.1, 0.25, 0.12, 0.8))
	draw_rect(Rect2(r.position.x, by, hw * clampf(p.hp / 100.0, 0.0, 1.0), bh), Color(0.36, 0.78, 0.38) if p.hp > 35 else Color(0.85, 0.25, 0.2))
	var aw := r.size.x - hw - 4.0 * s
	draw_rect(Rect2(r.position.x + hw + 4.0 * s, by, aw, bh), Color(0.1, 0.18, 0.3, 0.8))
	draw_rect(Rect2(r.position.x + hw + 4.0 * s, by, aw * clampf(p.reloads_left / 12.0, 0.0, 1.0), bh), Color(0.33, 0.6, 0.95))
	_t(f_bold, Vector2(r.position.x, r.position.y - 8.0 * s), ("SOLO" if main.solo else "P%d  %s" % [idx + 1, main.TEAM_NAMES[idx]]), 15, team.lightened(0.25), HORIZONTAL_ALIGNMENT_LEFT, -1, 4.0)


func _draw_radar() -> void:
	if main == null or main.players.size() <= idx or main.gen == null:
		return
	var p = main.players[idx]
	var R := radar
	var sz := R.size
	var c := sz / 2.0 + Vector2(0, sz.y * 0.12)          # player sits a bit low, like GTA
	var k := (sz.x / 2.0) / RADAR_RANGE                   # px per metre
	R.draw_rect(Rect2(Vector2.ZERO, sz), Color(0.1, 0.12, 0.11))
	var tex: Texture2D = main.gen.radar_tex
	if tex != null:
		var mpp: float = main.gen.MAP_HALF * 2.0 / main.gen.MAP_PX     # metres per texture pixel
		var ppos := Vector2(p.global_position.x + main.gen.MAP_HALF, p.global_position.z + main.gen.MAP_HALF) / mpp
		R.draw_set_transform(c, p.yaw, Vector2(k * mpp, k * mpp))
		R.draw_texture(tex, -ppos, Color(1, 1, 1, 0.95))
		R.draw_set_transform(Vector2.ZERO, 0.0, Vector2.ONE)
	# extraction zone
	if main.objective.get("stage", "") == "extract":
		var ez := _rp(p, main.objective["extract"], c, k)
		R.draw_circle(ez, main.EXTRACT_RADIUS * k, Color(0.3, 1, 0.45, 0.3))
	# pickups
	for pk in main.pickups:
		if pk["back"] > 0.0:
			continue
		var v := _rp(p, pk["pos"], c, k)
		if not Rect2(Vector2.ZERO, sz).has_point(v):
			continue
		if pk["kind"] == "ammo":
			R.draw_rect(Rect2(v - Vector2(3.5, 3.5) * s, Vector2(7, 7) * s), Color(0, 0, 0, 0.7))
			R.draw_rect(Rect2(v - Vector2(2.5, 2.5) * s, Vector2(5, 5) * s), Color(1, 1, 0.9))
		else:
			R.draw_rect(Rect2(v - Vector2(4.5, 1.8) * s, Vector2(9, 3.6) * s), Color(1, 0.4, 0.7))
			R.draw_rect(Rect2(v - Vector2(1.8, 4.5) * s, Vector2(3.6, 9) * s), Color(1, 0.4, 0.7))
	# enemies: red dots
	for b in get_tree().get_nodes_in_group("bot"):
		var v := _rp(p, b.global_position, c, k)
		if Rect2(Vector2.ZERO, sz).grow(-2).has_point(v):
			R.draw_circle(v, 4.2 * s, Color(0, 0, 0, 0.6))
			R.draw_circle(v, 3.2 * s, Color(0.95, 0.2, 0.15))
	# objective: yellow, clamped to the edge
	for m in main.objective_markers():
		var v := _edge(_rp(p, m[0], c, k), sz, 8.0 * s)
		var d := 7.0 * s
		R.draw_colored_polygon(PackedVector2Array([v + Vector2(0, -d), v + Vector2(d, 0), v + Vector2(0, d), v + Vector2(-d, 0)]), Color(1, 0.82, 0.2))
	# teammate: green dot, clamped to the edge (blinks red when down)
	var o = main.players[1 - idx]
	if o.state != "out" and not main.solo:
		var v := _edge(_rp(p, o.global_position, c, k), sz, 7.0 * s)
		var oc := Color(0.3, 1, 0.45)
		if o.state == "down":
			oc = Color(1, 0.3, 0.3) if int(Time.get_ticks_msec() / 250) % 2 == 0 else Color.WHITE
		R.draw_circle(v, 6.0 * s, Color(0, 0, 0, 0.7))
		R.draw_circle(v, 4.6 * s, oc)
	# north marker on the rim
	var nv := _edge(c + Vector2(0, -1000).rotated(p.yaw), sz, 10.0 * s)
	R.draw_circle(nv, 8.0 * s, Color(0, 0, 0, 0.6))
	R.draw_string(f_bold, nv + Vector2(-5, 5) * s, "N", HORIZONTAL_ALIGNMENT_LEFT, -1, int(14 * s), Color.WHITE)
	# me: white arrow pointing up
	R.draw_colored_polygon(PackedVector2Array([c + Vector2(0, -9) * s, c + Vector2(7, 7) * s, c + Vector2(0, 3) * s, c + Vector2(-7, 7) * s]), Color(0, 0, 0, 0.6))
	R.draw_colored_polygon(PackedVector2Array([c + Vector2(0, -8) * s, c + Vector2(6, 6) * s, c + Vector2(0, 2.5) * s, c + Vector2(-6, 6) * s]), Color.WHITE)


func _rp(p, pos: Vector3, c: Vector2, k: float) -> Vector2:
	return c + Vector2(pos.x - p.global_position.x, pos.z - p.global_position.z).rotated(p.yaw) * k


func _edge(v: Vector2, sz: Vector2, m: float) -> Vector2:
	return Vector2(clampf(v.x, m, sz.x - m), clampf(v.y, m, sz.y - m))
