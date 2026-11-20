extends Control

signal lantern_pressed(index: int)

const GOLD := Color("#ffd788")
const LIT := Color("#faeece")
const COLD := Color("#719aa4")
const INK := Color("#0a1a29")
var lights := 0
var pulse := -1
var glow := 0.0

func center_of(index: int) -> Vector2:
	return size / 2.0 + 89.0 * Vector2(index % 3 - 1, floori(index / 3.0) - 1)

func flash(index: int) -> void:
	pulse = index
	glow = 1
	set_process(true)

func _process(delta: float) -> void:
	glow = maxf(0, glow - 3.4 * delta)
	queue_redraw()
	if glow == 0:
		set_process(false)

func _draw() -> void:
	var middle := size / 2.0
	var etched := Color("#28404c")
	for j in range(77):
		var point := Vector2(fposmod(j * 79.1 + 31, size.x), fposmod(j * j * 6.73 + 11, size.y))
		draw_circle(point, 0.65 + (j % 3) * 0.3, Color("#4c6570"))
	for radius: float in [54.0, 108.0, 151.0]:
		draw_arc(middle, radius, 0, TAU, 120, etched, 1, true)
	for j in range(60):
		var axis := Vector2.UP.rotated(j * TAU / 60)
		draw_line(middle + axis * 147, middle + axis * (154 if j % 5 == 0 else 150), COLD, 1, true)
	for i in range(9):
		for next: int in [i + 1, i + 3]:
			if next >= 9 or (next == i + 1 and i % 3 == 2):
				continue
			var bright := (lights & (1 << i)) != 0 and (lights & (1 << next)) != 0
			draw_line(center_of(i), center_of(next), Color("#af9568") if bright else etched, 1.5, true)
	for i in range(9):
		var p := center_of(i)
		var is_lit := (lights & (1 << i)) != 0
		draw_circle(p, 20, INK)
		draw_arc(p, 19, 0, TAU, 48, GOLD if is_lit else COLD, 1.5, true)
		if is_lit:
			draw_circle(p, 16, Color("#39392e"))
			var star := PackedVector2Array()
			for k in range(8):
				star.append(p + Vector2.UP.rotated(k * TAU / 8) * (13 if k % 2 == 0 else 3.6))
			draw_colored_polygon(star, LIT)
		else:
			draw_circle(p, 4, COLD)
		if i == pulse and glow > 0:
			draw_arc(p, 21 + (1-glow)*15, 0, TAU, 48, Color(GOLD, glow), 2, true)

func _gui_input(event: InputEvent) -> void:
	if event is InputEventMouseButton and event.button_index == MOUSE_BUTTON_LEFT and event.pressed:
		for i in range(9):
			if event.position.distance_to(center_of(i)) <= 32:
				lantern_pressed.emit(i)
				accept_event()
				return
