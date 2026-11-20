"""Verify the shipped catalogue independently of Godot and the authoring agent."""
import json
import os
from pathlib import Path
import subprocess

root = Path(__file__).resolve().parents[1]
levels = json.loads((root/'game/voyage.json').read_text())
for level in levels:
    width = level['width']
    mask = sum(1 << i for i in level['shutters'])
    pair = level['relay'] or [-1,-1]
    args = [width, mask, *pair, level['lights'], 0]
    report = json.loads(subprocess.check_output([os.environ['ATLAS_ORACLE'], *map(str,args)]))
    assert report['par'] == level['par'] > 0, level['name']
    print(level['name'], report['par'])
trial = json.loads((root/'evidence/nightwatch-authoring.json').read_text())['candidates'][0]
assert trial['review']['accepted'] and trial['review']['par_without_relay'] == -1
assert levels[-1]['name'] == trial['proposal']['title'] and levels[-1]['lights'] == trial['review']['lights']
