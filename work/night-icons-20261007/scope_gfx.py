from pathlib import Path
import re

path = Path('tools/builders/build_adiscord_technology_system.py')
text = path.read_text(encoding='utf-8')
marker = '    args = parser.parse_args()\n'
assert text.count(marker) == 1
text = text.replace(marker, '''    parser.add_argument(
        "--night-icons-only",
        action="store_true",
        help="check or apply night combat sprites without rebuilding other UI",
    )
''' + marker + '''    if args.night_icons_only:
        if (args.weapon_icons_only or args.uniform_icons_only or args.aircraft_icons_only
                or args.equipment_names_only or args.technology_data_only
                or args.apply_starting_profiles):
            parser.error("--night-icons-only cannot be combined with other partial output modes")
        path = ROOT / "interface/ADISCORD_technologies.gfx"
        content = weapon_category_gfx_output("night_combat")
        changed = path.read_text(encoding="utf-8") != content
        if args.apply and changed:
            path.write_text(content, encoding="utf-8")
        print(f"Night combat sprites {'updated' if args.apply else 'different'}: {int(changed)}")
        return int(changed and not args.apply)
''')
path.write_text(text, encoding='utf-8')

path = Path('interface/ADISCORD_technologies.gfx')
text = path.read_text(encoding='utf-8')
original = Path('work/night-icons-20261007/ADISCORD_technologies.gfx').read_text(encoding='utf-8')
for key in ('electrothermal_ignition', 'biometric_trigger_locks'):
    pattern = rf'\tSpriteType = \{{\s*name = "GFX_ADISCORD_tech_{key}_medium"[^{{}}]*\}}'
    prior = re.search(pattern, original).group(0)
    text, count = re.subn(pattern, lambda match: prior, text)
    assert count == 1
path.write_text(text, encoding='utf-8')
