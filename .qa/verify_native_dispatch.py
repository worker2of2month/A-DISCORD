import collections
import subprocess
import sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd()))
from tools.validators.validate_adiscord_division_templates import parse_clausewitz
from tools.lib.on_actions import read_country_on_actions, read_scripted_peace
BASE = 'd6cc3c77078a25f7318fbf7e371fc6779eab3351'
PREFIX = 'common/on_actions/'
SHARED = PREFIX + '09_ADISCORD_scripted_peace_on_actions.txt'
GROUPS = {
 '01_ADISCORD_vorkerland_collapse_on_actions.txt': 'vorkerland_collapse',
 '02_ADISCORD_STP_on_actions.txt': 'stelander',
 '02_ADISCORD_VAL_rework_on_actions.txt': 'kefreyt',
 '02_ADISCORD_rin_oath_crisis_on_actions.txt': 'rin',
 '03_ADISCORD_nam_resource_war_on_actions.txt': 'nam',
 '03_ADISCORD_vorkerland_diplomacy_on_actions.txt': 'vorkerland_diplomacy',
 '04_ADISCORD_STP_northern_capitulation_guard_on_actions.txt': 'northern_reservation',
 '09_ADISCORD_VAL_livonn_settlement_on_actions.txt': 'livonn',
}
def show(path): return subprocess.check_output(['git', 'show', BASE + ':' + path]).decode('utf-8-sig')
def canon(entries): return tuple((e.key, e.quoted, canon(e.value) if isinstance(e.value, list) else e.value) for e in entries)
def hooks(source):
 roots = [e for e in parse_clausewitz(source) if e.key == 'on_actions']
 assert len(roots) == 1
 return roots[0].value

def stream(files):
 output = collections.defaultdict(list)
 for path, source in files:
  for hook in hooks(source):
   assert len(hook.value) == 1 and hook.value[0].key == 'effect', (path, hook.key)
   output[hook.key].extend(canon(hook.value[0].value))
 return dict(output)
old_names = subprocess.check_output(['git', 'ls-tree', '-r', '--name-only', BASE, PREFIX]).decode().splitlines()
old = [(p, show(p)) for p in sorted(old_names) if p.endswith('.txt')]
new = [(str(p), p.read_text(encoding='utf-8-sig')) for p in sorted(Path(PREFIX).glob('*.txt'))]
assert stream(old) == stream(new), 'Native command sequence or scope changed'
print('NATIVE_COMMAND_SEQUENCE_EQUIVALENT', len(stream(new)), 'hooks', flush=True)
for filename, group in GROUPS.items():
 path = PREFIX + filename
 original = {e.key: canon(e.value) for e in hooks(show(path))}
 view = read_country_on_actions(path, group) if Path(path).exists() else read_scripted_peace(SHARED, group)
 restored = {e.key: canon(e.value) for e in hooks(view)}
 assert original == restored, ('Incomplete tooling source view', filename)
print('EXACT_COUNTRY_SOURCE_VIEWS', len(GROUPS), flush=True)
generic = PREFIX + 'ZZ_ADISCORD_default_capitulation_on_actions.txt'
assert subprocess.check_output(['git', 'show', BASE + ':' + generic]) == Path(generic).read_bytes()
print('GENERIC_ZZ_BYTE_IDENTICAL', flush=True)
for p in Path(PREFIX).glob('*.txt'):
 assert not p.read_bytes().startswith(b'\xef\xbb\xbf'), p
for root in ('common', 'events'):
 for p in Path(root).rglob('*.txt'):
  s = p.read_text(encoding='utf-8-sig')
  assert not any(flag in s for flag in ('STP_pc_war_val', 'STP_pc_war_nod', 'STP_pc_war_with_sts')), p
print('OBSOLETE_WAR_MIRRORS_ABSENT', flush=True)
