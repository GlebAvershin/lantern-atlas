extends Control

const Chart = preload("res://chart.gd")
const StarMap = preload("res://sky.gd")
const Logbook = preload("res://logbook.gd")
const SERIF = preload("res://art/CormorantGaramond.ttf")
const COVER = preload("res://art/northwatch.jpg")
const PULSE = preload("res://sfx/pulse.wav")
const RELAY = preload("res://sfx/relay.wav")
const ARRIVAL = preload("res://sfx/arrival.wav")
const GOLD := Color("#f5c586")
const PAPER := Color("#f4eddb")
const MUTED := Color("#b1c6c8")
const DEEP := Color("#112c34")

var chart := Chart.new()
var logbook := Logbook.new()
var sky := StarMap.new()
var heading := Label.new()
var stats := Label.new()
var instruction := Label.new()
var primary := Button.new()
var back := Button.new()
var hint := Button.new()
var chooser := MenuButton.new()
var options := MenuButton.new()
var counter := Label.new()
var voyage_progress := Label.new()
var layout := VBoxContainer.new()
var split := BoxContainer.new()
var cover := TextureRect.new()
var course := Control.new()
var panel := PanelContainer.new()
var voice := AudioStreamPlayer.new()
var reveal: Tween

func label_style(label: Label, pixels: int, ink: Color, serif := false) -> void:
	label.add_theme_font_size_override("font_size", pixels)
	label.add_theme_color_override("font_color", ink)
	if serif:
		label.add_theme_font_override("font",SERIF)

func box(fill: Color, border: Color, radius := 8) -> StyleBoxFlat:
	var style := StyleBoxFlat.new()
	style.bg_color = fill
	style.border_color = border
	style.set_border_width_all(1)
	style.set_corner_radius_all(radius)
	for side in [SIDE_LEFT,SIDE_TOP,SIDE_RIGHT,SIDE_BOTTOM]:
		style.set_content_margin(side, 8)
	return style

func button_style(button: Button, active := false) -> void:
	var fill := GOLD if active else Color("#183942")
	var ink := Color("#172b32") if active else PAPER
	for state in ["normal","hover","pressed","hover_pressed","disabled"]:
		var tone := fill.lightened(.1) if state == "hover" else fill
		button.add_theme_stylebox_override(state, box(tone,Color("#537075") if not active else GOLD))
		var key: String = "font_color" if state == "normal" else "font_%s_color" % state
		button.add_theme_color_override(key, MUTED.darkened(.25) if state == "disabled" else ink)
	button.add_theme_color_override("font_focus_color",ink)
	var focus := box(Color.TRANSPARENT,Color("#8de5de"))
	focus.draw_center = false
	focus.set_border_width_all(2)
	button.add_theme_stylebox_override("focus",focus)
	button.add_theme_font_size_override("font_size",15)
	button.custom_minimum_size.y = 40

func build_cover() -> void:
	cover.texture = COVER
	cover.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	cover.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_COVERED
	cover.mouse_filter = Control.MOUSE_FILTER_IGNORE
	split.add_child(cover)
	var shade := TextureRect.new()
	var gradient := Gradient.new()
	gradient.offsets = PackedFloat32Array([0.0,0.30,0.57,1.0])
	gradient.colors = PackedColorArray([Color("#07182299"),Color("#07182205"),Color("#07182200"),Color("#071822e6")])
	var tex := GradientTexture2D.new()
	tex.gradient = gradient
	tex.fill_from = Vector2(0,0)
	tex.fill_to = Vector2(0,1)
	shade.texture = tex
	shade.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	shade.mouse_filter = Control.MOUSE_FILTER_IGNORE
	cover.add_child(shade)
	shade.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	var title := Label.new()
	title.text = "Lantern Atlas"
	label_style(title,43,PAPER,true)
	cover.add_child(title)
	title.position = Vector2(22,14)
	cover.add_child(course)
	course.mouse_filter = Control.MOUSE_FILTER_IGNORE
	course.set_anchors_and_offsets_preset(Control.PRESET_BOTTOM_WIDE)
	course.offset_left = 24
	course.offset_right = -24
	course.offset_top = -68
	course.offset_bottom = -45
	course.draw.connect(draw_course)
	label_style(voyage_progress,14,PAPER)
	cover.add_child(voyage_progress)
	voyage_progress.set_anchors_and_offsets_preset(Control.PRESET_BOTTOM_WIDE)
	voyage_progress.offset_left = 24
	voyage_progress.offset_top = -44

func draw_course() -> void:
	var count := chart.charts.size()
	var width := minf(course.size.x,260)
	var y := course.size.y*0.5
	course.draw_line(Vector2(5,y),Vector2(width-5,y),Color("#87979a"),1.5,true)
	for i in count:
		var x := lerpf(5,width-5,i/float(count-1))
		var pos := Vector2(x,y)
		course.draw_circle(pos,4.5,GOLD if logbook.best.has(chart.charts[i].name) else DEEP)
		course.draw_arc(pos,4.5,0,TAU,24,PAPER,1,true)
		if i == chart.plate:
			course.draw_arc(pos,8,0,TAU,32,GOLD,1.5,true)

func _ready() -> void:
	add_child(split)
	split.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	split.add_theme_constant_override("separation",0)
	build_cover()
	split.add_child(panel)
	panel.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	panel.size_flags_vertical = Control.SIZE_EXPAND_FILL
	panel.add_theme_stylebox_override("panel",box(DEEP,DEEP,0))
	var margin := MarginContainer.new()
	panel.add_child(margin)
	for side in ["left","right","top","bottom"]:
		margin.add_theme_constant_override("margin_"+side,12)
	margin.add_child(layout)
	layout.add_theme_constant_override("separation",7)
	var header := VBoxContainer.new()
	var top := HBoxContainer.new()
	header.add_child(top)
	stats.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	label_style(stats,13,GOLD)
	top.add_child(stats)
	chooser.text = "Charts"
	options.text = "Settings"
	for menu in [chooser,options]:
		button_style(menu)
		top.add_child(menu)
	chooser.about_to_popup.connect(fill_charts)
	chooser.get_popup().id_pressed.connect(open_plate)
	options.about_to_popup.connect(fill_options)
	options.get_popup().id_pressed.connect(toggle_option)
	label_style(heading,39,PAPER,true)
	header.add_child(heading)
	sky.chart = chart
	sky.lantern_pressed.connect(play_move)
	sky.size_flags_vertical = Control.SIZE_EXPAND_FILL
	var controls := VBoxContainer.new()
	controls.add_theme_constant_override("separation",8)
	label_style(counter,15,GOLD)
	controls.add_child(counter)
	label_style(instruction,16,MUTED)
	instruction.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	instruction.custom_minimum_size.y = 49
	controls.add_child(instruction)
	var actions := HBoxContainer.new()
	controls.add_child(actions)
	actions.add_theme_constant_override("separation",8)
	back.text = "Undo"
	hint.text = "Hint"
	for button in [back,hint,primary]:
		button_style(button, button == primary)
		button.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		actions.add_child(button)
	back.pressed.connect(undo_move)
	hint.pressed.connect(show_hint)
	primary.pressed.connect(primary_action)
	var widgets := {"logbook":header,"sky":sky,"controls":controls}
	var spec = JSON.parse_string(FileAccess.get_file_as_string("res://hud.json"))
	for slot in spec.rows:
		layout.add_child(widgets[slot])
	add_child(voice)
	voice.volume_db = -7
	get_window().size_changed.connect(fit_window)
	fit_window()
	open_plate(clampi(logbook.chapter,0,unlocked()),true)

func fit_window() -> void:
	var portrait := get_window().size.x < get_window().size.y
	var base := Vector2i(440,740) if portrait else Vector2i(900,580)
	if get_window().content_scale_size != base:
		get_window().content_scale_size = base
	split.vertical = portrait
	cover.custom_minimum_size = Vector2(0,135) if portrait else Vector2(330,0)
	sky.custom_minimum_size.y = 240 if portrait else 225

func unlocked() -> int:
	for i in chart.charts.size():
		if not logbook.best.has(chart.charts[i].name):
			return i
	return chart.charts.size()-1

func fill_charts() -> void:
	var menu := chooser.get_popup()
	menu.clear()
	for i in chart.charts.size():
		var spec: Dictionary = chart.charts[i]
		var best: int = logbook.best.get(spec.name,0)
		var text := "%02d   %s" % [i+1,spec.name]
		if best > 0:
			text += "   ·   best %d" % best
		menu.add_item(text,i)
		menu.set_item_disabled(i,i > unlocked())

func fill_options() -> void:
	var menu := options.get_popup()
	menu.clear()
	menu.add_check_item("Sound",0)
	menu.add_check_item("Reduced motion",1)
	menu.set_item_checked(0,not logbook.quiet)
	menu.set_item_checked(1,logbook.reduced)

func toggle_option(id: int) -> void:
	if id == 0:
		logbook.quiet = not logbook.quiet
		if logbook.quiet:
			voice.stop()
	else:
		logbook.reduced = not logbook.reduced
		sky.reduced = logbook.reduced
		if logbook.reduced:
			sky.clear_feedback()
			if reveal:
				reveal.kill()
			panel.modulate.a = 1
	logbook.save()

func checkpoint() -> void:
	logbook.sequence = chart.presses.duplicate()
	logbook.save()

func open_plate(index: int, resume := false) -> void:
	chart.open_plate(index)
	var spec: Dictionary = chart.charts[index]
	var revision := JSON.stringify([spec.name,spec.width,spec.lights,spec.relay,spec.shutters])
	if resume and logbook.revision == revision:
		for move in logbook.sequence:
			if typeof(move) != TYPE_INT or not chart.tap(move):
				chart.open_plate(index)
				break
	logbook.revision = revision
	logbook.chapter = index
	checkpoint()
	sky.clear_feedback()
	sky.reduced = logbook.reduced
	refresh()
	if reveal:
		reveal.kill()
	panel.modulate.a = 1
	if not logbook.reduced:
		panel.modulate.a = .64
		reveal = create_tween()
		reveal.tween_property(panel,"modulate:a",1.0,.28).set_trans(Tween.TRANS_SINE)

func play_move(cell: int) -> void:
	if not chart.tap(cell):
		if cell >= 0 and cell < chart.pulses.size() and chart.shutters & (1 << cell) and chart.lights != chart.all_lit:
			instruction.text = "Shuttered station. Send light from a nearby lantern."
		return
	sky.flash(cell)
	var won := chart.lights == chart.all_lit
	if won:
		var key: String = chart.charts[chart.plate].name
		logbook.best[key] = mini(chart.history.size(),logbook.best.get(key,chart.history.size()))
	checkpoint()
	if not logbook.quiet:
		voice.stream = ARRIVAL if won else (RELAY if cell in chart.relay else PULSE)
		voice.play()
	refresh()

func undo_move() -> void:
	chart.undo()
	checkpoint()
	sky.clear_feedback()
	refresh()

func show_hint() -> void:
	var moves := chart.solution()
	if moves <= 0:
		return
	for i in chart.pulses.size():
		if moves & (1 << i):
			sky.hinted = i
			sky.queue_redraw()
			instruction.text = "Pulse the ringed lantern. It starts a shortest route from here."
			return

func primary_action() -> void:
	if chart.lights == chart.all_lit:
		open_plate((chart.plate + 1) % chart.charts.size())
	else:
		open_plate(chart.plate)

func refresh() -> void:
	var spec: Dictionary = chart.charts[chart.plate]
	var solved := chart.lights == chart.all_lit
	stats.text = "CHART   %02d  /  %02d" % [chart.plate+1,chart.charts.size()]
	heading.text = spec.name
	course.queue_redraw()
	voyage_progress.text = "Nightwatch   /   %d of %d charts lit" % [logbook.best.size(),chart.charts.size()]
	var count := chart.history.size()
	counter.text = "%d %s     ·     Par %d" % [count,"move" if count == 1 else "moves",int(spec.par)]
	if logbook.best.has(spec.name):
		counter.text += "     ·     Best %d" % int(logbook.best[spec.name])
	instruction.text = spec.note
	if solved:
		instruction.text = "Voyage complete. The fleet is home." if chart.plate == chart.charts.size()-1 else "Passage clear. The next chart is open."
	back.disabled = chart.history.is_empty()
	hint.disabled = solved
	primary.text = ("Sail again" if chart.plate == chart.charts.size()-1 else "Next chart") if solved else "Restart"
	sky.queue_redraw()

func _unhandled_key_input(event: InputEvent) -> void:
	if event is InputEventKey and event.pressed and not event.echo:
		if event.keycode >= KEY_1 and event.keycode <= KEY_9:
			play_move(event.keycode - KEY_1)
		elif event.keycode == KEY_Z:
			undo_move()
		elif event.keycode == KEY_H:
			show_hint()
