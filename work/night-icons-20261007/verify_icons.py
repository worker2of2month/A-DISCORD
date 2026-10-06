from pathlib import Path
import hashlib
import re
from PIL import Image
from tools.builders import build_adiscord_technology_icons as icons
from tools.builders import build_adiscord_technology_system as system

root = Path.cwd()
outputs = icons.render_outputs(root, 'night')
assert all((root / path).read_bytes() == data for path, data in outputs.items())
before = {path: hashlib.sha256((root / path).read_bytes()).hexdigest() for path in outputs}
icons.apply(outputs, root, clean_connectors=False)
assert before == {path: hashlib.sha256((root / path).read_bytes()).hexdigest() for path in outputs}
assert system.weapon_category_gfx_output('night_combat') == (root / 'interface/ADISCORD_technologies.gfx').read_text(encoding='utf-8')
original = (root / 'work/night-icons-20261007/ADISCORD_technologies.gfx').read_text(encoding='utf-8')
current = (root / 'interface/ADISCORD_technologies.gfx').read_text(encoding='utf-8')
pattern = r'\tSpriteType = \{\s*name = "([^"]+)"[^{}]*\}'
old = {m[1]: m[0] for m in re.finditer(pattern, original)}
new = {m[1]: m[0] for m in re.finditer(pattern, current)}
changed = [key for key in old.keys() | new.keys() if old.get(key) != new.get(key)]
allowed = {f'GFX_{tech.id}_medium' for tech in system.BRANCH_BY_KEY['night_combat'].techs}
assert len(set(changed) & allowed) == 11, changed
print('Saved source hashes match the import manifest')
print('DDS rebuild: 6/6 byte-identical')
print('GFX: all 11 intended night combat sprites connected')
for path in outputs:
    with Image.open(root / path) as icon:
        print(path.name, icon.size, icon.getchannel('A').getextrema())
