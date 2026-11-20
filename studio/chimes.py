"""Bake short original resonance cues. The game only loads the resulting PCM files."""
from pathlib import Path
import math
import struct
import wave

out = Path(__file__).resolve().parents[1] / "game/sfx"
out.mkdir(exist_ok=True)
for name, notes in {"pulse": [(0, 418), (.035, 627)], "relay": [(0,418),(.06,698),(.12,837)],
                    "arrival": [(0,392),(.07,494),(.15,587),(.22,784)]}.items():
    frames = bytearray()
    for i in range(int(22050 * (notes[-1][0] + .65))):
        t = i / 22050
        total = 0
        for delay, freq in notes:
            age = t - delay
            if age >= 0:
                env = min(1, age / .009) * math.exp(-9 * age)
                total += env * (math.sin(math.tau*freq*age) + .18*math.sin(math.tau*freq*2.01*age))
        frames.extend(struct.pack('<h', round(5000*total)))
    with wave.open(str(out / (name+'.wav')), 'wb') as stream:
        stream.setparams((1,2,22050,0,'NONE',''))
        stream.writeframes(frames)
