extends SceneTree

func _initialize() -> void:
	run.call_deferred()

func verify(ok: bool, detail: String) -> void:
	if not ok:
		printerr("FAILED: ", detail)
		quit(1)
		assert(ok, detail)

func run() -> void:
	change_scene_to_file("res://atlas.tscn")
	await scene_changed
	await process_frame
	var game = current_scene
	var seen := {}
	var frontier := [511]
	seen[511] = 0
	var head := 0
	while head < frontier.size():
		var before: int = frontier[head]
		head += 1
		for i in range(9):
			var after: int = before ^ game.Chart.pulse_mask(i)
			if not seen.has(after):
				seen[after] = seen[before] + 1
				frontier.append(after)
	verify(seen.size() == 512, "connected board states")
	for i in range(game.Chart.PLATES.size()):
		var initial: int = game.chart.lights
		verify(game.chart.plate == i and seen[initial] == i + 1, "difficulty curve")
		for cell in game.Chart.PLATES[i].switches:
			var click := InputEventMouseButton.new()
			click.button_index = MOUSE_BUTTON_LEFT
			click.pressed = true
			click.position = game.sky.center_of(cell)
			game.sky._gui_input(click)
		verify(game.chart.lights == 511, "solved by taps")
		game.back.pressed.emit()
		verify(game.chart.lights != 511, "undo solved board")
		game.primary.pressed.emit()
		verify(game.chart.lights == initial and game.chart.history.is_empty(), "reset")
		for cell in game.Chart.PLATES[i].switches:
			game.play_move(cell)
		game.primary.pressed.emit()
	verify(game.chart.plate == 0, "replay after final chart")
	verify(game.layout.get_child_count() == 3 and game.sky.size.y >= 310, "runtime layout")
	print("PASS: 512 reachable states; five charts at optimal depths 1–5; tap/undo/restart/advance/replay")
	quit()
