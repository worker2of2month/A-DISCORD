from pathlib import Path
import hashlib
import json
import shutil

source = Path(r'C:\Users\Admin\Desktop\tech\камуфлаж.png')
destination = Path('tools/assets/source/technology_weapons/protection_camouflage.png')
assert not destination.exists()
shutil.copyfile(source, destination)
manifest = Path('tools/data/adiscord_technology_weapon_icons.json')
payload = json.loads(manifest.read_text(encoding='utf-8'))
assert not any(entry['key'] == 'protection_camouflage' for entry in payload['icons'])
payload['icons'].append({
    'key': 'protection_camouflage',
    'family': 'protection',
    'source': destination.name,
    'source_sha256': hashlib.sha256(destination.read_bytes()).hexdigest(),
    'source_size': [70, 70],
    'tier': 7,
    'kind': 'compact',
    'output': 'ADISCORD_equipment_protection_camouflage.dds',
    'runtime_master': True,
})
manifest.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
path = Path('work/protection-icons-20261007/verify.py')
text = path.read_text(encoding='utf-8-sig')
text = text.replace('Exactly 9 intended', 'Exactly 12 intended').replace('6 DDS files', '7 DDS files').replace('All 6 imported', 'All 7 imported')
text = text.replace("('экзоскелет.png', 'exoskeleton')]", "('экзоскелет.png', 'exoskeleton'), ('камуфлаж.png', 'camouflage')]")
path.write_text(text, encoding='utf-8')
