extends Control

const Chart = preload("res://chart.gd")
const StarMap = preload("res://sky.gd")
const GOLD := Color("#ffd788")
const PAPER := Color("#f6f1df")
const MUTED := Color("#a3bbbe")
var chart := Chart.new()
var sky := StarMap.new()
var heading := Label.new()
var stats := Label.new()
var instruction := Label.new()
var primary := Button.new()
var back := Button.new()
var layout := VBoxContainer.new()

func label_style(label: Label, pixels: int, ink: Color) -> void:
	label.add_theme_font_size_override("font_size", pixels)
	label.add_theme_color_override("font_color", ink)
	label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER

func button_style(button: Button, active: bool) -> void:
	var base := StyleBoxFlat.new()
	base.bg_color = GOLD if active else Color("#172f40")
	base.set_corner_radius_all(7)
	for state in ["normal", "hover", "pressed", "disabled"]:
		var variant := base.duplicate() as StyleBoxFlat
		if state == "hover":
			variant.bg_color = base.bg_color.lightened(0.12)
		elif state == "pressed":
			variant.bg_color = base.bg_color.darkened(0.15)
		button.add_theme_stylebox_override(state, variant)
		var color_key: String = "font_color" if state == "normal" else "font_%s_color" % state
		button.add_theme_color_override(color_key, Color("#15212a") if active else PAPER)
	button.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	button.custom_minimum_size.y = 46

func _ready() -> void:
	var margin := MarginContainer.new()
	add_child(margin)
	margin.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	for side in ["left", "right", "top", "bottom"]:
		margin.add_theme_constant_override("margin_" + side, 22)
	margin.add_child(layout)
	layout.add_theme_constant_override("separation", 12)
	var logbook := VBoxContainer.new()
	label_style(stats, 15, GOLD)
	label_style(heading, 32, PAPER)
	logbook.add_child(stats)
	logbook.add_child(heading)
	sky.size_flags_vertical = Control.SIZE_EXPAND_FILL
	sky.custom_minimum_size.y = 310
	sky.lantern_pressed.connect(play_move)
	var controls := VBoxContainer.new()
	controls.add_theme_constant_override("separation", 12)
	label_style(instruction, 17, MUTED)
	instruction.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	controls.add_child(instruction)
	var bar := HBoxContainer.new()
	controls.add_child(bar)
	bar.add_theme_constant_override("separation", 10)
	back.text = "Undo"
	button_style(back, false)
	button_style(primary, true)
	bar.add_child(back)
	bar.add_child(primary)
	back.pressed.connect(undo_move)
	primary.pressed.connect(primary_action)
	var widgets := {"logbook": logbook, "sky": sky, "controls": controls}
	var spec = JSON.parse_string(FileAccess.get_file_as_string("res://hud.json"))
	for slot in spec.rows:
		layout.add_child(widgets[slot])
	open_plate(0)

func open_plate(index: int) -> void:
	chart.open_plate(index)
	refresh()

func play_move(cell: int) -> void:
	if chart.lights == Chart.ALL_LIT:
		return
	chart.tap(cell)
	sky.flash(cell)
	refresh()

func undo_move() -> void:
	chart.undo()
	refresh()

func primary_action() -> void:
	if chart.lights == Chart.ALL_LIT:
		open_plate((chart.plate + 1) % Chart.PLATES.size())
	else:
		open_plate(chart.plate)

func refresh() -> void:
	var solved: bool = chart.lights == Chart.ALL_LIT
	var final_plate: bool = chart.plate == Chart.PLATES.size() - 1
	stats.text = "LANTERN ATLAS    /    %02d OF %02d" % [chart.plate + 1, Chart.PLATES.size()]
	heading.text = Chart.PLATES[chart.plate].name
	sky.lights = chart.lights
	sky.queue_redraw()
	back.disabled = chart.history.is_empty()
	primary.text = ("Play again" if final_plate else "Next chart") if solved else "Restart"
	if solved:
		var message := "Atlas complete" if final_plate else "Chart illuminated"
		instruction.text = "%s · %d moves" % [message, chart.history.size()]
	else:
		instruction.text = "Light every star. Tap one to switch it and its neighbours.\nMoves  %d" % chart.history.size()

func _unhandled_key_input(event: InputEvent) -> void:
	if event is InputEventKey and event.pressed and not event.echo:
		if event.keycode >= KEY_1 and event.keycode <= KEY_9:
			play_move(event.keycode - KEY_1)
		elif event.keycode == KEY_Z:
			undo_move()
