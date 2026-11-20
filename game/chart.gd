extends RefCounted

var charts: Array = JSON.parse_string(FileAccess.get_file_as_string("res://voyage.json"))
var plate := 0
var width := 3
var all_lit := 511
var lights := 0
var shutters := 0
var relay: Array = []
var history: Array[int] = []
var presses: Array[int] = []
var pulses: Array[int] = []
var left_table := {}
var right_table := {}

static func weight(bits: int) -> int:
	var count := 0
	while bits != 0:
		bits &= bits - 1
		count += 1
	return count

func open_plate(index: int) -> void:
	var spec: Dictionary = charts[index]
	plate = index
	width = int(spec.width)
	all_lit = (1 << (width * width)) - 1
	lights = int(spec.lights)
	relay = []
	for index_value in spec.relay:
		relay.append(int(index_value))
	shutters = 0
	for cell in spec.shutters:
		shutters |= 1 << int(cell)
	history.clear()
	presses.clear()
	pulses.clear()
	var allowed: Array[int] = []
	for cell in width * width:
		var mask := 1 << cell
		var coords := Vector2i(cell % width, floori(cell / float(width)))
		for step in [Vector2i.LEFT, Vector2i.RIGHT, Vector2i.UP, Vector2i.DOWN]:
			var pos: Vector2i = coords + step
			if Rect2i(0, 0, width, width).has_point(pos):
				mask |= 1 << (pos.y * width + pos.x)
		if relay.size() == 2:
			if cell == int(relay[0]):
				mask ^= 1 << int(relay[1])
			elif cell == int(relay[1]):
				mask ^= 1 << int(relay[0])
		pulses.append(mask)
		if not shutters & (1 << cell):
			allowed.append(cell)
	var middle := floori(allowed.size() / 2.0)
	left_table = half_table(allowed.slice(0, middle))
	right_table = half_table(allowed.slice(middle))

# For each reachable effect, keep the cheapest press set for this half of the board.
func half_table(cells: Array) -> Dictionary:
	var table := {0: 0}
	for cell: int in cells:
		var extended := table.duplicate()
		for before: int in table:
			var after := before ^ pulses[cell]
			var choice := int(table[before]) | (1 << cell)
			if not extended.has(after) or weight(choice) < weight(extended[after]):
				extended[after] = choice
		table = extended
	return table

# Both halves are disjoint. Joining their effects by XOR gives the global minimum.
func solution() -> int:
	var goal := lights ^ all_lit
	var best := -1
	var cost := width * width + 1
	for effect: int in left_table:
		var other := goal ^ effect
		if right_table.has(other):
			var choice := int(left_table[effect]) | int(right_table[other])
			var count := weight(choice)
			if count < cost:
				cost = count
				best = choice
	return best

func tap(cell: int) -> bool:
	if cell < 0 or cell >= pulses.size() or lights == all_lit or shutters & (1 << cell):
		return false
	history.append(lights)
	presses.append(cell)
	lights ^= pulses[cell]
	return true

func undo() -> void:
	if not history.is_empty():
		lights = history.pop_back()
		presses.pop_back()
