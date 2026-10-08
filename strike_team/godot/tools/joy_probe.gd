extends SceneTree
var n := 0
func _process(_d):
	n += 1
	if n == 30:
		for d in Input.get_connected_joypads():
			var ax := []
			for a in 6: ax.append(snappedf(Input.get_joy_axis(d, a), 0.01))
			print("JOY ", d, " '", Input.get_joy_name(d), "' axes ", ax)
		print("joypads: ", Input.get_connected_joypads().size())
		quit()
	return false
