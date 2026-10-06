from pathlib import Path
import hashlib
import re
from tools.builders import build_adiscord_technology_icons as builder
from tools.builders import build_adiscord_technology_system as system

root = Path.cwd()
base = root / 'work/protection-icons-20261007'
original = (base / 'ADISCORD_technologies.gfx').read_text(encoding='utf-8')
current = (root / 'interface/ADISCORD_technologies.gfx').read_text(encoding='utf-8')
pattern = r'\tSpriteType = \{\s*name = "([^"]+)"[^{}]*\}'
old = {match[1]: match[0] for match in re.finditer(pattern, original)}
new = {match[1]: match[0] for match in re.finditer(pattern, current)}
changed = {key for key in old.keys() | new.keys() if old.get(key) != new.get(key)}
expected = {f'GFX_ADISCORD_tech_{key}_medium' for key in system.PROTECTION_TECH_ICONS}
assert changed == expected, (changed - expected, expected - changed)
print('Exactly 12 intended GFX sprites changed; all others preserved')
outputs = builder.render_outputs(root, 'protection')
before = {path: hashlib.sha256((root / path).read_bytes()).hexdigest() for path in outputs}
builder.apply(outputs, root, clean_connectors=False)
assert before == {path: hashlib.sha256((root / path).read_bytes()).hexdigest() for path in outputs}
assert current == system.weapon_category_gfx_output('protection')
print('Second generation: 0 changes, 7 DDS files and GFX current')
for original_name, key in [('броник.png', 'body_armour'), ('броник ещё один.png', 'trauma_pads'), ('ещё броник.png', 'ceramic_plates'), ('gasmask.png', 'respirator'), ('наушники.png', 'hearing'), ('экзоскелет.png', 'exoskeleton'), ('камуфлаж.png', 'camouflage')]:
    selected = Path(r'C:\Users\Admin\Desktop\tech') / original_name
    imported = root / f'tools/assets/source/technology_weapons/protection_{key}.png'
    assert selected.read_bytes() == imported.read_bytes()
print('All 7 imported PNGs identical to user files')
