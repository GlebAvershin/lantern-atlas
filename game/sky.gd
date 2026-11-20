extends Control

signal lantern_pressed(index: int)

const GOLD := Color("#f9c67b")
const PAPER := Color("#fff1c8")
const COLD := Color("#739a9d")
const RELAY := Color("#85e2d5")
const INK := Color("#0c2530")
var chart
var hinted := -1
var hovered := -1
var source := -1
var elapsed := 1.0
var changed := 0
var reduced := false
var cursor := 0

func _ready() -> void:
	focus_mode = Control.FOCUS_ALL
	focus_entered.connect(queue_redraw)
	focus_exited.connect(queue_redraw)
	mouse_exited.connect(func(): hovered = -1; queue_redraw())
	set_process(false)

func pitch() -> float:
	return minf((size.x - 64) / chart.width, (size.y - 38) / chart.width)

func center_of(index: int) -> Vector2:
	var half: float = (chart.width - 1) * 0.5
	return size * 0.5 + pitch() * Vector2(index % chart.width - half, floori(index / float(chart.width)) - half)

func clear_feedback() -> void:
	cursor = 0
	hinted = -1
	hovered = -1
	elapsed = 1.0
	source = -1
	set_process(false)
	queue_redraw()

func flash(cell: int) -> void:
	source = cell
	changed = chart.pulses[cell]
	hinted = -1
	elapsed = 1.0 if reduced else 0.0
	set_process(not reduced)
	queue_redraw()

func _process(dt: float) -> void:
	elapsed += dt
	queue_redraw()
	if elapsed >= 0.56:
		set_process(false)

func _draw() -> void:
	if not chart or chart.pulses.is_empty():
		return
	var middle := size / 2
	var radius := minf(size.x, size.y) * 0.46
	var ink := Color("#2b4750")
	for i in 63:
		var p := Vector2(fposmod(i * 77.31 + 17,size.x), fposmod(i*i*9.32+11,size.y))
		draw_circle(p, 0.7 + 0.3 * (i%3), Color("#526872"))
	for f in [0.58, 0.94, 1.0]:
		draw_arc(middle, radius*f, 0,TAU,112,ink,1,true)
	for i in 60:
		var axis := Vector2.UP.rotated(TAU*i/60)
		draw_line(middle+axis*radius*0.96,middle+axis*(radius+ (3 if i%5==0 else 0)),ink,1,true)
	for i in chart.pulses.size():
		if i%chart.width != chart.width-1:
			draw_line(center_of(i), center_of(i+1), ink,1.5,true)
		if i+chart.width < chart.pulses.size():
			draw_line(center_of(i), center_of(i+chart.width), ink,1.5,true)
	if chart.relay.size() == 2:
		draw_dashed_line(center_of(int(chart.relay[0])),center_of(int(chart.relay[1])),Color("#54998f"),2,6,true)
	var preview := 0
	if hovered >= 0 and chart.lights != chart.all_lit and not chart.shutters & (1 << hovered):
		preview = chart.pulses[hovered]
	for i in chart.pulses.size():
		draw_lantern(i, preview)

func draw_lantern(i: int, preview: int) -> void:
	var pos := center_of(i)
	var bit := 1 << i
	var lit: bool = bool(chart.lights & bit)
	var linked: bool = i in chart.relay
	var shut: bool = bool(chart.shutters & bit)
	var r := clampf(pitch()*0.235,13,26)
	var wave := 0.0
	if elapsed < 0.56 and changed & bit and source >= 0:
		var dist := center_of(source).distance_to(pos) / pitch()
		var age := elapsed - minf(0.17,dist*0.064)
		if age >= 0 and age < 0.36:
			wave = sin(PI*age/0.36)
			if i != source:
				var travel := clampf(elapsed / maxf(0.07,dist*0.065),0,1)
				draw_circle(center_of(source).lerp(pos,travel),3,RELAY if linked else GOLD)
	r += wave*3.5
	var rim := GOLD if lit else COLD
	if lit:
		draw_circle(pos,r+5,Color(GOLD,0.08))
	if preview & bit:
		draw_arc(pos,r+5,-PI*0.80,-PI*0.20,12,RELAY,2,true)
		draw_arc(pos,r+5,PI*0.20,PI*0.80,12,RELAY,2,true)
	if hinted == i or (has_focus() and cursor == i):
		draw_arc(pos,r+9,0,TAU,52,PAPER,2.5,true)
	if linked:
		var diamond := PackedVector2Array([pos+Vector2.UP*(r+6),pos+Vector2.RIGHT*(r+6),pos+Vector2.DOWN*(r+6),pos+Vector2.LEFT*(r+6),pos+Vector2.UP*(r+6)])
		draw_colored_polygon(diamond.slice(0,4), INK)
		draw_polyline(diamond,RELAY,2,true)
	draw_circle(pos, r, Color("#523f30") if lit else INK)
	draw_arc(pos,r,0,TAU,48,rim,2,true)
	if shut:
		for x in [-0.38,0,0.38]:
			draw_line(pos+Vector2(x*r,-r*0.43),pos+Vector2(x*r,r*0.43),rim,2.5,true)
	elif lit:
		var star := PackedVector2Array()
		for k in 8:
			star.append(pos+Vector2.UP.rotated(k*TAU/8)*(r*(0.70 if k%2==0 else 0.20)))
		draw_colored_polygon(star,PAPER)
	else:
		draw_circle(pos, r*0.2, rim)
	if wave > 0:
		draw_arc(pos,r+5+5*wave,0,TAU,48,Color(GOLD,wave*0.7),2,true)

func nearest(point: Vector2) -> int:
	for i in chart.pulses.size():
		if point.distance_to(center_of(i)) <= pitch()*0.39:
			return i
	return -1

func _gui_input(event: InputEvent) -> void:
	if event is InputEventKey and event.pressed and not event.echo:
		var x: int = cursor % chart.width
		var y := floori(cursor / float(chart.width))
		match event.keycode:
			KEY_LEFT: x = maxi(0,x-1)
			KEY_RIGHT: x = mini(chart.width-1,x+1)
			KEY_UP: y = maxi(0,y-1)
			KEY_DOWN: y = mini(chart.width-1,y+1)
			KEY_SPACE, KEY_ENTER: lantern_pressed.emit(cursor)
			_: return
		cursor = y * chart.width + x
		queue_redraw()
		accept_event()
	elif event is InputEventMouseMotion:
		hovered = nearest(event.position)
		queue_redraw()
	elif event is InputEventMouseButton and event.button_index == MOUSE_BUTTON_LEFT and event.pressed:
		var cell := nearest(event.position)
		if cell != -1:
			cursor = cell
			lantern_pressed.emit(cell)
			accept_event()
