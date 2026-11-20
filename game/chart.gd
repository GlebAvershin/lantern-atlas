extends RefCounted

const ALL_LIT := 511
const PLATES := [
	{"name": "The Harbour", "switches": [4]},
	{"name": "Twin Beacons", "switches": [0, 8]},
	{"name": "The Navigator", "switches": [1, 3, 8]},
	{"name": "The Long Crossing", "switches": [0, 2, 5, 7]},
	{"name": "First Light", "switches": [0, 2, 4, 6, 8]},
]

var plate := 0
var lights := ALL_LIT
var history: Array[int] = []

static func pulse_mask(index: int) -> int:
	var mask := 1 << index
	for offset: Vector2i in [Vector2i.LEFT, Vector2i.RIGHT, Vector2i.UP, Vector2i.DOWN]:
		var cell := Vector2i(index % 3, floori(index / 3.0)) + offset
		if Rect2i(0, 0, 3, 3).has_point(cell):
			mask |= 1 << (cell.y * 3 + cell.x)
	return mask

func open_plate(index: int) -> void:
	plate = index
	history.clear()
	lights = ALL_LIT
	for cell: int in PLATES[index].switches:
		lights ^= pulse_mask(cell)

func tap(index: int) -> void:
	if index < 0 or index >= 9 or lights == ALL_LIT:
		return
	history.append(lights)
	lights ^= pulse_mask(index)

func undo() -> void:
	if not history.is_empty():
		lights = history.pop_back()
