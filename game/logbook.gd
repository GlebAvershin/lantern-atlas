extends RefCounted

const FILE := "user://nightwatch-v2.cfg"
var best := {}
var chapter := 0
var quiet := false
var reduced := false
var file: String

func _init(path: String = FILE) -> void:
	file = path
	var cfg := ConfigFile.new()
	if cfg.load(file) == OK:
		var records = cfg.get_value("voyage","best",{})
		if records is Dictionary:
			for key in records:
				if key is String and records[key] is int and records[key] > 0:
					best[key] = records[key]
		chapter = int(cfg.get_value("voyage","chapter",0))
		quiet = bool(cfg.get_value("settings","quiet",false))
		reduced = bool(cfg.get_value("settings","reduced",false))

func save() -> void:
	var cfg := ConfigFile.new()
	cfg.set_value("voyage","best",best)
	cfg.set_value("voyage","chapter",chapter)
	cfg.set_value("settings","quiet",quiet)
	cfg.set_value("settings","reduced",reduced)
	var temp := file + ".tmp"
	if cfg.save(temp) != OK or DirAccess.rename_absolute(temp,file) != OK:
		push_warning("Could not save the voyage log")
