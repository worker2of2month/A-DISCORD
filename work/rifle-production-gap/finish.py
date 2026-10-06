from pathlib import Path
import re

from tools.builders import build_adiscord_technology_system as generator

root = Path.cwd()
path = root / "common/units/equipment/ADISCORD_infantry_equipment.txt"
text = path.read_bytes().decode("utf-8")
stats = {
    2168: (27, 3.2, 7.6, 1.4, 5),
    2170: (30, 4.5, 9, 1.7, 6),
    2178: (35, 6, 11.5, 2.2, 8),
    2183: (40, 7.5, 14, 2.8, 10),
    2193: (49, 10, 18, 3.5, 14),
    2200: (60, 13, 23, 4.5, 18),
}
for year, values in stats.items():
    match = re.search(rf"\tADISCORD_infantry_equipment_{year} = \{{.*?\n\t\}}", text, re.DOTALL)
    block = match[0]
    for key, value in zip(("defense", "breakthrough", "soft_attack", "hard_attack", "ap_attack"), values):
        block, count = re.subn(rf"\b{key} = [\d.]+", f"{key} = {value}", block)
        assert count == 1
    text = text[:match.start()] + block + text[match.end():]
path.write_bytes(text.encode("utf-8"))

gui = root / "interface/countrytechtreeview.gui"
(root / "work/rifle-production-gap/gui-before.txt").write_bytes(gui.read_bytes())
generator.write_gui()
first = gui.read_bytes()
generator.write_gui()
assert gui.read_bytes() == first
print("GUI regenerated and second run is byte-identical")
