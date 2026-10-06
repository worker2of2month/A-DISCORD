import hashlib
import json
from pathlib import Path
import shutil

root = Path.cwd()
manifest = root / 'tools/data/adiscord_technology_weapon_icons.json'
payload = json.loads(manifest.read_text(encoding='utf-8'))
source_dir = root / 'tools/assets/source/technology_weapons'
for number in range(1, 5):
    name = f'night_{number:02}.png'
    target = source_dir / name
    assert not target.exists(), target
    shutil.copyfile(Path(r'C:\Users\Admin\Desktop\tech') / name, target)

sources = {1: 1, 2: 2, 3: 1, 4: 4, 5: 3, 6: 4}
for entry in payload['icons']:
    if not entry['output'].startswith('ADISCORD_night_'):
        continue
    source = f"night_{sources[entry['tier']]:02}.png"
    entry['source'] = source
    entry['source_sha256'] = hashlib.sha256((source_dir / source).read_bytes()).hexdigest()
    entry['source_size'] = [70, 70]
    entry['runtime_master'] = True
    entry.pop('source_uuid', None)
    entry.pop('crop', None)
manifest.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
