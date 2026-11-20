extends SceneTree

# Scripted footage from the normal game scene, with a disposable voyage log.
func _initialize() -> void:
	run.call_deferred()

func pause(seconds: float) -> void:
	await create_timer(seconds).timeout

func run() -> void:
	var game = load("res://atlas.tscn").instantiate()
	var slot := "user://capture-%d.cfg" % OS.get_process_id()
	game.logbook = game.Logbook.new(slot)
	root.add_child(game)
	current_scene = game
	for index in game.chart.charts.size():
		var show_chart: bool = index in [0,2,7]
		if show_chart:
			await pause(1.10)
		if index == 7 and not OS.get_environment("ATLAS_SCREENSHOT").is_empty():
			await RenderingServer.frame_post_draw
			root.get_texture().get_image().save_png(OS.get_environment("ATLAS_SCREENSHOT"))
		var press_set: int = game.chart.solution()
		for bit in game.chart.pulses.size():
			if press_set & (1 << bit):
				if show_chart:
					game.sky.hovered = bit
					game.sky.queue_redraw()
					await pause(.35)
				var click := InputEventMouseButton.new()
				click.button_index = MOUSE_BUTTON_LEFT
				click.pressed = true
				click.position = game.sky.center_of(bit)
				game.sky._gui_input(click)
				if show_chart:
					await pause(.59)
		if show_chart:
			await pause(.95)
		if index < game.chart.charts.size()-1:
			game.primary.pressed.emit()
	DirAccess.remove_absolute(slot)
	quit()
