extends SceneTree

var failed := false
var total_states := 0

func _initialize() -> void:
	run.call_deferred()

func verify(ok: bool, detail: String) -> void:
	if not ok:
		printerr("FAILED: ",detail)
		failed = true

func press(game, cell: int) -> void:
	var click := InputEventMouseButton.new()
	click.button_index = MOUSE_BUTTON_LEFT
	click.pressed = true
	click.position = game.sky.center_of(cell)
	game.sky._gui_input(click)

func key(game, code: Key) -> void:
	var event := InputEventKey.new()
	event.keycode = code
	event.pressed = true
	game.sky._gui_input(event)

func run() -> void:
	var game = load("res://atlas.tscn").instantiate()
	var path := "user://nightwatch-test-%d.cfg" % OS.get_process_id()
	game.logbook = game.Logbook.new(path)
	root.add_child(game)
	current_scene = game
	await process_frame
	verify(game.unlocked() == 0,"new voyage starts at the harbour")
	for i in game.chart.charts.size():
		var c = game.chart
		var spec: Dictionary = c.charts[i]
		var initial: int = c.lights
		verify(c.plate == i and initial == int(spec.lights),"route progression")
		verify(c.weight(c.solution()) == int(spec.par),"minimum solution from C++ oracle for "+str(spec.name))
		for shutter in spec.shutters:
			press(game,int(shutter))
			verify(c.lights == initial and c.history.is_empty(),"closed station cannot be pressed")
		if not c.relay.is_empty():
			var a: int = c.relay[0]
			var b: int = c.relay[1]
			verify(typeof(c.relay[0]) == TYPE_INT and a in c.relay,"relay identified by visual and audio")
			press(game,a)
			verify(bool((initial ^ c.lights) & (1<<b)),"distant relay toggles")
			game.back.pressed.emit()
		var steps := 0
		while c.lights != c.all_lit and steps < 17:
			game.hint.pressed.emit()
			var pick: int = game.sky.hinted
			verify(pick >= 0,"hint supplies a legal action")
			if pick < 0:
				break
			press(game,pick)
			steps += 1
		verify(steps == int(spec.par) and c.lights == c.all_lit,"hint path is optimal")
		verify(game.logbook.best.get(spec.name,-1) == steps,"best recorded on completion")
		var fresh = game.Logbook.new(path)
		verify(fresh.best.get(spec.name,-1) == steps,"best persisted on disk")
		game.back.pressed.emit()
		verify(c.lights != c.all_lit,"undo after victory")
		game.primary.pressed.emit()
		verify(c.lights == initial and c.history.is_empty(),"restart restores board and counter")
		game.show_hint()
		var answer: int = c.solution()
		for cell in c.pulses.size():
			if answer & (1<<cell):
				press(game,cell)
		game.primary.pressed.emit()
	verify(game.chart.plate == 0 and game.logbook.best.size() == 8,"finish and replay")
	game.open_plate(7)
	game.sky.grab_focus()
	for i in 3:
		key(game,KEY_RIGHT)
		key(game,KEY_DOWN)
	verify(game.sky.cursor == 15, "keyboard reaches last station on large board")
	key(game,KEY_SPACE)
	verify(game.chart.history.size() == 1,"keyboard pulse")
	game.toggle_option(1)
	game.toggle_option(0)
	var reopened = game.Logbook.new(path)
	verify(reopened.reduced and reopened.quiet and reopened.chapter == 7,"settings and chapter survive reopening")
	game.open_plate(0)
	var c = game.chart
	for state in 512:
		c.lights = state
		var solution: int = c.solution()
		var restored := state
		for bit in 9:
			if solution & (1<<bit):
				restored ^= c.pulses[bit]
		verify(restored == 511,"every harbour state solvable")
		total_states += 1
	DirAccess.remove_absolute(path)
	print("Nightwatch: 8 charts, ",total_states," harbour states, relay, shutters, hints, save, restart, keyboard and replay. Passed: ",not failed)
	quit(1 if failed else 0)
