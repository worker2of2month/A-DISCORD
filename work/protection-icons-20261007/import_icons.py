from pathlib import Path
import hashlib
import json
import shutil

root = Path.cwd()
source_dir = root / 'tools/assets/source/technology_weapons'
files = [
    ('броник.png', 'body_armour'),
    ('броник ещё один.png', 'trauma_pads'),
    ('ещё броник.png', 'ceramic_plates'),
    ('gasmask.png', 'respirator'),
    ('наушники.png', 'hearing'),
    ('экзоскелет.png', 'exoskeleton'),
]
manifest = root / 'tools/data/adiscord_technology_weapon_icons.json'
payload = json.loads(manifest.read_text(encoding='utf-8'))
assert not any(entry.get('family') == 'protection' for entry in payload['icons'])
for tier, (original, key) in enumerate(files, 1):
    filename = f'protection_{key}.png'
    destination = source_dir / filename
    assert not destination.exists(), destination
    shutil.copyfile(Path(r'C:\Users\Admin\Desktop\tech') / original, destination)
    payload['icons'].append({
        'key': f'protection_{key}',
        'family': 'protection',
        'source': filename,
        'source_sha256': hashlib.sha256(destination.read_bytes()).hexdigest(),
        'source_size': [70, 70],
        'tier': tier,
        'kind': 'compact',
        'output': f'ADISCORD_equipment_protection_{key}.dds',
        'runtime_master': True,
    })
manifest.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

path = root / 'tools/builders/build_adiscord_technology_system.py'
text = path.read_text(encoding='utf-8')
marker = '    args = parser.parse_args()\n'
assert text.count(marker) == 1
text = text.replace(marker, '''    parser.add_argument(
        "--protection-icons-only",
        action="store_true",
        help="check or apply protective equipment sprites without rebuilding other UI",
    )
''' + marker)
text = text.replace('    if args.night_icons_only:\n', '''    if args.night_icons_only or args.protection_icons_only:
        if args.night_icons_only and args.protection_icons_only:
            parser.error("select only one infantry icon branch")
''')
text = text.replace('parser.error("--night-icons-only cannot be combined with other partial output modes")', 'parser.error("infantry icon branches cannot be combined with other partial output modes")')
text = text.replace('        content = weapon_category_gfx_output("night_combat")', '''        branch_key = "protection" if args.protection_icons_only else "night_combat"
        content = weapon_category_gfx_output(branch_key)''')
text = text.replace('print(f"Night combat sprites', 'print(f"{branch_key} sprites')
path.write_text(text, encoding='utf-8')
