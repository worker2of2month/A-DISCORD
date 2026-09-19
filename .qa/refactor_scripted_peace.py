"""One-shot, fail-closed extraction run on a pinned checkout, never on main."""
from __future__ import annotations
import ast
import collections
import contextlib
import importlib
import io
import json
import re
import subprocess
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path.cwd()))
from tools.validators.validate_adiscord_division_templates import parse_clausewitz
from tools.validators.validate_adiscord_val_rework import mask_non_code

ROOT = Path.cwd()
DIR = ROOT / 'common/on_actions'
SHARED = '09_ADISCORD_scripted_peace_on_actions.txt'
GROUPS = {
 '01_ADISCORD_vorkerland_collapse_on_actions.txt': ('vorkerland_collapse', ('on_peace', 'on_capitulation')),
 '02_ADISCORD_STP_on_actions.txt': ('stelander', ('on_peaceconference_ended', 'on_capitulation_immediate', 'on_capitulation')),
 '02_ADISCORD_VAL_rework_on_actions.txt': ('kefreyt', ('on_capitulation_immediate', 'on_capitulation')),
 '02_ADISCORD_rin_oath_crisis_on_actions.txt': ('rin', ('on_capitulation', 'on_peace')),
 '03_ADISCORD_nam_resource_war_on_actions.txt': ('nam', ('on_capitulation',)),
 '03_ADISCORD_vorkerland_diplomacy_on_actions.txt': ('vorkerland_diplomacy', ('on_capitulation', 'on_peace')),
 '04_ADISCORD_STP_northern_capitulation_guard_on_actions.txt': ('northern_reservation', ('on_capitulation_immediate', 'on_capitulation')),
 '09_ADISCORD_VAL_livonn_settlement_on_actions.txt': ('livonn', ('on_capitulation', 'on_weekly_VAL')),
}
DELETED = {k for k, (group, _) in GROUPS.items() if group in ('northern_reservation', 'livonn')}

def canonical(entries):
 return tuple((e.key, e.quoted, canonical(e.value) if isinstance(e.value, list) else e.value) for e in entries)

def hooks(source):
 entries = parse_clausewitz(source)
 roots = [e for e in entries if e.key == 'on_actions']
 assert len(roots) == 1, 'Expected one native on_actions container'
 return roots[0].value

def callback_stream():
 result = collections.defaultdict(list)
 for p in sorted(DIR.glob('*.txt')):
  for hook in hooks(p.read_text(encoding='utf-8-sig')):
   assert len(hook.value) == 1 and hook.value[0].key == 'effect', (p.name, hook.key)
   result[hook.key].extend(canonical(hook.value[0].value))
 return dict(result)

def spans(source):
 masked = mask_non_code(source)
 depths, depth = [], 0
 for c in masked:
  depths.append(depth)
  if c == '{': depth += 1
  elif c == '}': depth -= 1
  assert depth >= 0
 assert depth == 0
 found = []
 for m in re.finditer(r'(?m)^[ \t]*(\w+)\s*=\s*\{', masked):
  if depths[m.start()] != 1: continue
  opening = masked.index('{', m.start(), m.end())
  closing = opening + 1
  while closing < len(masked) and not (masked[closing] == '}' and depths[closing] == 2): closing += 1
  assert closing < len(masked)
  start = m.start()
  while start > 0:
   prev_end = start - 1
   prev_start = source.rfind('\n', 0, prev_end) + 1
   if source[prev_start:prev_end].lstrip().startswith('#'): start = prev_start
   else: break
  end = closing + 1
  if end < len(source) and source[end] == '\n': end += 1
  raw = source[start:end]
  inner = source[opening + 1:closing]
  inner_mask = mask_non_code(inner)
  em = re.search(r'\beffect\s*=\s*\{', inner_mask)
  assert em, m[1]
  eo = inner_mask.index('{', em.start(), em.end())
  ec = len(inner_mask.rstrip()) - 1
  assert inner_mask[ec] == '}'
  effect = inner[eo + 1:ec]
  found.append((m[1], start, end, effect))
 return found

TEST = r'''"""Ownership and native callback order for the shared scripted-peace bus."""
from pathlib import Path
import re
import unittest
from tools.validators.validate_adiscord_division_templates import parse_clausewitz

ROOT = Path(__file__).resolve().parents[2]
DIRECTORY = ROOT / 'common/on_actions'
SHARED = DIRECTORY / '09_ADISCORD_scripted_peace_on_actions.txt'
GENERIC = DIRECTORY / 'ZZ_ADISCORD_default_capitulation_on_actions.txt'
ORDER = {
    'on_capitulation_immediate': ['stelander', 'kefreyt', 'northern_reservation'],
    'on_capitulation': ['vorkerland_collapse', 'stelander', 'kefreyt', 'rin', 'nam', 'vorkerland_diplomacy', 'northern_reservation', 'livonn'],
    'on_peace': ['vorkerland_collapse', 'rin', 'vorkerland_diplomacy'],
    'on_peaceconference_ended': ['stelander'],
    'on_weekly_VAL': ['livonn'],
}

def native_hooks(source):
    roots = [e.value for e in parse_clausewitz(source) if e.key == 'on_actions']
    if len(roots) != 1:
        raise AssertionError('Expected exactly one on_actions root')
    return roots[0]

class ScriptedPeaceOwnershipTests(unittest.TestCase):
    def source(self):
        self.assertTrue(SHARED.is_file(), 'Scripted peace has no shared owner')
        return SHARED.read_text(encoding='utf-8')

    def test_one_definition_for_each_shared_native_hook(self):
        names = [e.key for e in native_hooks(self.source())]
        self.assertEqual(len(names), len(set(names)))
        self.assertEqual(set(names), set(ORDER))

    def test_country_sections_preserve_dispatch_order(self):
        source = self.source()
        for hook, expected in ORDER.items():
            with self.subTest(hook=hook):
                actual = re.findall(r'(?m)^\s*# BEGIN ([a-z_]+):' + re.escape(hook) + r'\s*$', source)
                ends = re.findall(r'(?m)^\s*# END ([a-z_]+):' + re.escape(hook) + r'\s*$', source)
                self.assertEqual(actual, expected)
                self.assertEqual(ends, expected)

    def test_capitulation_has_no_remaining_country_owner(self):
        self.source()
        for path in DIRECTORY.glob('*.txt'):
            if path in (SHARED, GENERIC):
                continue
            names = {e.key for e in native_hooks(path.read_text(encoding='utf-8-sig'))}
            self.assertFalse(names & {'on_capitulation', 'on_capitulation_immediate', 'on_peaceconference_ended'}, path.name)

    def test_generic_fallback_is_separate_and_last(self):
        self.source()
        self.assertTrue(GENERIC.is_file())
        self.assertLess(SHARED.name, GENERIC.name)
        generic = GENERIC.read_text(encoding='utf-8')
        self.assertIn('NOT = { has_global_flag = skip_default_capitulation }', generic)
        self.assertIn('clr_global_flag = skip_default_capitulation', generic)

    def test_obsolete_guard_and_livonn_files_are_removed(self):
        self.source()
        for name in ('04_ADISCORD_STP_northern_capitulation_guard_on_actions.txt', '09_ADISCORD_VAL_livonn_settlement_on_actions.txt'):
            self.assertFalse((DIRECTORY / name).exists(), name)

    def test_no_war_state_mirrors_or_global_periodic_scan(self):
        source = self.source()
        for flag in ('STP_pc_war_val', 'STP_pc_war_nod', 'STP_pc_war_with_sts'):
            self.assertNotIn(flag, source)
        names = {e.key for e in native_hooks(source)}
        self.assertNotIn('on_weekly', names)
        self.assertNotIn('on_daily', names)
        self.assertFalse(SHARED.read_bytes().startswith(b'\xef\xbb\xbf'))

if __name__ == '__main__':
    unittest.main()
'''

HELPER = r'''"""Explicit source views for country contracts spanning native on_action files.

Gameplay is read from its actual owners. Country validators can inspect the
country lifecycle and its shared peace section without seeing other treaties.
The independent scripted-peace tests validate the complete native dispatch.
"""
from __future__ import annotations
import re
from pathlib import Path
from tools.lib.paths import repository_root

SCRIPTED_PEACE = '09_ADISCORD_scripted_peace_on_actions.txt'
_SECTION = re.compile(
    r'(?m)^[ \t]*# BEGIN ([a-z_]+):(on_[A-Za-z_]+)[ \t]*\n'
    r'(.*?)^[ \t]*# END \1:\2[ \t]*$', re.DOTALL,
)

def _path(path: str | Path) -> Path:
    path = Path(path)
    return path if path.is_absolute() else repository_root() / path

def _body(source: str) -> str:
    match = re.fullmatch(r'\s*on_actions\s*=\s*\{(.*)\}\s*', source, re.DOTALL)
    if match is None:
        raise ValueError('Expected one on_actions source container')
    return match[1]

def read_scripted_peace(path: str | Path, section: str) -> str:
    """Read one explicitly named treaty group from the shared native owner."""
    source = _path(path).read_text(encoding='utf-8')
    matches = [m for m in _SECTION.finditer(source) if m[1] == section]
    if not matches or len({m[2] for m in matches}) != len(matches):
        raise ValueError(f'Missing or duplicated scripted-peace section: {section}')
    body = '\n'.join(f'\t{m[2]} = {{\n\t\teffect = {{\n{m[3]}\t\t}}\n\t}}' for m in matches)
    return 'on_actions = {\n' + body + '\n}\n'

def read_country_on_actions(path: str | Path, section: str) -> str:
    """Read an existing country file plus its explicitly selected peace hooks."""
    path = _path(path)
    country = path.read_text(encoding='utf-8')
    peace = read_scripted_peace(path.with_name(SCRIPTED_PEACE), section)
    return 'on_actions = {\n' + _body(country).strip('\n') + '\n' + _body(peace).strip('\n') + '\n}\n'

def country_on_actions_entries(path: str | Path, section: str):
    from tools.validators.validate_adiscord_division_templates import parse_clausewitz
    return parse_clausewitz(read_country_on_actions(path, section))

def scripted_peace_entries(path: str | Path, section: str):
    from tools.validators.validate_adiscord_division_templates import parse_clausewitz
    return parse_clausewitz(read_scripted_peace(path, section))
'''

# Characterize the current checkout before changing any production source.
before = callback_stream()
generic_before = (DIR / 'ZZ_ADISCORD_default_capitulation_on_actions.txt').read_bytes()
test_path = ROOT / 'tools/tests/test_scripted_peace_on_actions.py'
test_path.write_text(TEST, encoding='utf-8')
red = subprocess.run([sys.executable, '-m', 'unittest', 'tools.tests.test_scripted_peace_on_actions'], capture_output=True, text=True)
print('RED_EXIT', red.returncode, flush=True)
assert red.returncode != 0 and 'Scripted peace has no shared owner' in red.stderr, red.stderr
print('RED: missing shared owner detected before extraction', flush=True)

# Move exact effect text in original filename order. Do not add country scopes.
sections = collections.defaultdict(list)
for filename, (section, chosen) in GROUPS.items():
 path = DIR / filename
 source = path.read_text(encoding='utf-8')
 extracted = [item for item in spans(source) if item[0] in chosen]
 assert {item[0] for item in extracted} == set(chosen), filename
 for hook, start, end, effect in extracted:
  sections[hook].append((section, effect))
 for hook, start, end, effect in sorted(extracted, key=lambda item: item[1], reverse=True):
  source = source[:start] + source[end:]
 if filename in DELETED:
  assert not hooks(source), filename
  path.unlink()
 else:
  path.write_text(source, encoding='utf-8')
shared = '# Scripted peace dispatch. Native ROOT/FROM scopes are retained.\n# Section order is contractual: settlements precede the northern reservation\n# and Livonn completion; the separate ZZ handler consumes the final reservation.\non_actions = {\n'
for hook in ('on_capitulation_immediate', 'on_capitulation', 'on_peace', 'on_peaceconference_ended', 'on_weekly_VAL'):
 shared += f'\t{hook} = {{\n\t\teffect = {{\n'
 for section, effect in sections[hook]:
  shared += f'\t\t\t# BEGIN {section}:{hook}\n' + effect.strip('\n') + '\n' + f'\t\t\t# END {section}:{hook}\n\n'
 shared += '\t\t}\n\t}\n'
shared += '}\n'
(DIR / SHARED).write_text(shared, encoding='utf-8')
assert callback_stream() == before, 'Native callback statements/order changed during extraction'
assert (DIR / 'ZZ_ADISCORD_default_capitulation_on_actions.txt').read_bytes() == generic_before
print('EXACT_NATIVE_CALLBACK_STREAM_PRESERVED', len(before), 'hooks', flush=True)
(ROOT / 'tools/lib/on_actions.py').write_text(HELPER, encoding='utf-8')

# Update source readers at explicit call sites, never by monkeypatching read().
reader_changes = []
for path in sorted((ROOT / 'tools').rglob('*.py')):
 if path.name in ('on_actions.py', 'test_scripted_peace_on_actions.py'): continue
 source = path.read_text(encoding='utf-8-sig')
 tree = ast.parse(source)
 assignments = {}
 for node in tree.body:
  if isinstance(node, ast.Assign):
   for target in node.targets:
    if isinstance(target, ast.Name): assignments[target.id] = node.value
  elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
   assignments[node.target.id] = node.value
 def resolve(node, seen=frozenset()):
  if isinstance(node, ast.Constant) and isinstance(node.value, str): return node.value
  if isinstance(node, ast.Name) and node.id in assignments and node.id not in seen:
   return resolve(assignments[node.id], seen | {node.id})
  if isinstance(node, ast.BinOp): return resolve(node.left, seen) + '/' + resolve(node.right, seen)
  if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in ('Path', 'str') and node.args: return resolve(node.args[0], seen)
  return ''
 def segment(node): return ast.get_source_segment(source, node)
 lines = source.encode('utf-8').splitlines(keepends=True)
 offsets = [0]
 for line in lines: offsets.append(offsets[-1] + len(line))
 def bounds(node): return offsets[node.lineno - 1] + node.col_offset, offsets[node.end_lineno - 1] + node.end_col_offset
 replacements, imports = [], set()
 for node in ast.walk(tree):
  mode, target, path_expression = None, None, None
  if isinstance(node, ast.Call):
   if isinstance(node.func, ast.Name) and node.func.id in ('read', 'entries', 'relative_entries') and node.args:
    candidates = [(arg, resolve(arg)) for arg in node.args[:2]]
    hit = next(((arg, text) for arg, text in candidates if any(name in text for name in GROUPS)), None)
    if hit:
     target, resolved = hit
     path_expression = segment(target)
     if len(node.args) >= 2 and target is node.args[1]: path_expression = f'({segment(node.args[0])}) / ({path_expression})'
     mode = 'entries' if node.func.id != 'read' else 'read'
   elif isinstance(node.func, ast.Attribute) and node.func.attr == 'read_text':
    target, resolved = node.func.value, resolve(node.func.value)
    if any(name in resolved for name in GROUPS):
     mode, path_expression = 'read', segment(target)
  elif isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name) and node.value.id == 'sources' and isinstance(node.ctx, ast.Load):
   resolved = resolve(node.slice)
   if any(name in resolved for name in GROUPS): mode, path_expression = 'read', segment(node.slice)
  if mode is None: continue
  filename = next(name for name in GROUPS if name in resolved)
  section = GROUPS[filename][0]
  if filename in DELETED:
   fn = 'scripted_peace_entries' if mode == 'entries' else 'read_scripted_peace'
   path_expression = f'Path({path_expression}).with_name({SHARED!r})'
   imports.add('Path')
  else: fn = 'country_on_actions_entries' if mode == 'entries' else 'read_country_on_actions'
  imports.add(fn)
  start, end = bounds(node)
  replacements.append((start, end, f'{fn}({path_expression}, {section!r})'))
 # Prefer an outer read over a path expression nested in it.
 selected = []
 for start, end, text in sorted(replacements, key=lambda r: (r[0], -r[1])):
  if selected and start < selected[-1][1]: continue
  selected.append((start, end, text))
 if not selected: continue
 data = source.encode('utf-8')
 for start, end, text in reversed(selected): data = data[:start] + text.encode('utf-8') + data[end:]
 new = data.decode('utf-8')
 for old in DELETED: new = new.replace(old, SHARED)
 import_names = sorted(imports - {'Path'})
 extra = 'from tools.lib.on_actions import ' + ', '.join(import_names) + '\n'
 if 'Path' in imports and not re.search(r'from pathlib import .*\bPath\b', source): extra += 'from pathlib import Path\n'
 header_end = 0
 for node in tree.body:
  if (isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str)) or (isinstance(node, ast.ImportFrom) and node.module == '__future__'):
   header_end = node.end_lineno
  else: break
 new_lines = new.splitlines(keepends=True)
 new_lines.insert(header_end, extra)
 new = ''.join(new_lines)
 ast.parse(new)
 path.write_text(new, encoding='utf-8')
 reader_changes.append((str(path.relative_to(ROOT)), len(selected)))
print('EXPLICIT_READER_CHANGES', reader_changes, flush=True)

# Existing Path-only readers must not be called with newly added literal strings.
p = ROOT / 'tools/tests/test_adiscord_stp_postwar_continuation.py'
s = p.read_text(encoding='utf-8')
s = re.sub(r'\bread\("((?:common|events)/[^"\n]+)"\)', r'read(ROOT / "\1")', s)
p.write_text(s, encoding='utf-8')

p = ROOT / 'AGENTS.md'
s = p.read_text(encoding='utf-8')
old = 'Country on_actions belong in `common/on_actions/02_ADISCORD_STP_on_actions.txt`.\nKeep the numeric prefix for capitulation-handler order.'
assert old in s
s = s.replace(old, 'Country lifecycle on_actions belong in `common/on_actions/02_ADISCORD_STP_on_actions.txt`.\nScripted peace and capitulation dispatch is shared in\n`common/on_actions/09_ADISCORD_scripted_peace_on_actions.txt`, with ordered\ncountry sections inside each native hook. Do not duplicate those hooks in\ncountry files. Keep effects, triggers and treaty-choice events in their existing\ncountry files. Northern reservation follows the settlement handlers; Livonn\ncompletion follows the SRP military result. The separate\n`ZZ_ADISCORD_default_capitulation_on_actions.txt` remains last.\nUpdate explicit tooling source views and verify the full native callback order\nwhen moving a handler.')
p.write_text(s, encoding='utf-8')
p = ROOT / 'docs/development/focus-effects.md'
s = p.read_text(encoding='utf-8')
s = s.replace('Его обработчик `09_ADISCORD_VAL_livonn_settlement_on_actions.txt` остаётся отдельным, поскольку выполняется после военного урегулирования.', 'Его раздел `livonn` находится в `09_ADISCORD_scripted_peace_on_actions.txt` после военного урегулирования STP/SRP. Ограниченная недельная проверка завершения договора сохраняется.')
s += '\n## Диспетчеризация скриптового мира\n\n`common/on_actions/09_ADISCORD_scripted_peace_on_actions.txt` содержит обработчики капитуляций и завершения договоров. Внутри каждого нативного hook разделы исполняются в порядке: Воркерланд, Стеланд, Кефрейт, Рин, Наместничество, дипломатия Воркерланда, северная защитная проверка и Ливонн. Раздел включён только в те hooks, которые нужны его механике. Общий `ZZ_ADISCORD_default_capitulation_on_actions.txt` остаётся отдельным и последним.\n\nПеренос не меняет ROOT/FROM, военные результаты, территориальные эффекты или очередь выбора условий. Инициализация стран, подготовка войн, экономика и её периодические обновления остаются у своих владельцев. Эффекты, триггеры и события выбора условий также остаются в файлах соответствующих стран. Для проверок одного региона `tools/lib/on_actions.py` явно объединяет его обычный файл с указанным разделом общего обработчика; общий тест проверяет единичное владение hooks и порядок всех разделов.\n'
p.write_text(s, encoding='utf-8')

assert callback_stream() == before
subprocess.run([sys.executable, '-m', 'unittest', 'tools.tests.test_scripted_peace_on_actions'], check=True)
subprocess.run(['git', 'diff', '--check'], check=True)
for path in DIR.glob('*.txt'):
 if path.name == SHARED or path.name in GROUPS:
  assert not path.read_bytes().startswith(b'\xef\xbb\xbf'), path
print('EXTRACTION_AND_OWNERSHIP_CHECKS_PASS', flush=True)
subprocess.run(['git', 'diff', '--stat'], check=True)
