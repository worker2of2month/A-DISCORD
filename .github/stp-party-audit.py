"""Keep the template reference inventory synchronized with the new party lock."""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))
from tools.validators.validate_adiscord_division_templates import parse_clausewitz

path = Path('tools/data/division_template_audit.json')
text = path.read_text(encoding='utf-8')
row = next(r for r in json.loads(text)['references'] if r['key'] == 'adiscord_stp_postwar_assault_template_unlock')
assert row['count'] == 3
assert row['technical_name'] == 'Stelander Assault Division'
assert row['kind'] == 'technical_reference'

def count(nodes):
    return sum((int(n.key == 'division_template' and n.value == row['technical_name']) if isinstance(n.value,str) else count(n.value)) for n in nodes)

actual = count(parse_clausewitz(Path(row['path']).read_text(encoding='utf-8')))
assert actual == 4, actual
pattern = r'("key": "adiscord_stp_postwar_assault_template_unlock",[^}]+"count": )3'
text, replacements = re.subn(pattern, r'\g<1>4', text)
assert replacements == 1
path.write_text(text, encoding='utf-8')
print('Inventory matches all four existing/new lock, unlock and recruitment references.')
