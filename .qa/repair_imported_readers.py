"""Finish explicit readers whose on_action paths are imported module constants."""
from __future__ import annotations
import ast
import re
from pathlib import Path
ROOT = Path.cwd()
GROUPS = {
 '01_ADISCORD_vorkerland_collapse_on_actions.txt': 'vorkerland_collapse',
 '02_ADISCORD_STP_on_actions.txt': 'stelander',
 '02_ADISCORD_VAL_rework_on_actions.txt': 'kefreyt',
 '02_ADISCORD_rin_oath_crisis_on_actions.txt': 'rin',
 '03_ADISCORD_nam_resource_war_on_actions.txt': 'nam',
 '03_ADISCORD_vorkerland_diplomacy_on_actions.txt': 'vorkerland_diplomacy',
}
cache = {}
def metadata(module):
 if module in cache: return cache[module]
 path = ROOT.joinpath(*module.split('.')).with_suffix('.py')
 if not path.is_file(): return ({}, {}, {})
 assignments, imports, modules = {}, {}, {}
 for node in ast.parse(path.read_text(encoding='utf-8-sig')).body:
  if isinstance(node, ast.Assign):
   for target in node.targets:
    if isinstance(target, ast.Name): assignments[target.id] = node.value
  elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name): assignments[node.target.id] = node.value
  elif isinstance(node, ast.ImportFrom) and node.module:
   for alias in node.names:
    imports[alias.asname or alias.name] = (node.module, alias.name)
    candidate = node.module + '.' + alias.name
    if ROOT.joinpath(*candidate.split('.')).with_suffix('.py').is_file(): modules[alias.asname or alias.name] = candidate
  elif isinstance(node, ast.Import):
   for alias in node.names: modules[alias.asname or alias.name] = alias.name
 cache[module] = (assignments, imports, modules)
 return cache[module]
def resolve(node, module, seen=frozenset()):
 assignments, imports, modules = metadata(module)
 if isinstance(node, ast.Constant) and isinstance(node.value, str): return node.value
 if isinstance(node, ast.Name):
  key = (module, node.id)
  if key in seen: return ''
  if node.id in assignments: return resolve(assignments[node.id], module, seen | {key})
  if node.id in imports:
   other, name = imports[node.id]
   return resolve(ast.Name(id=name), other, seen | {key})
 if isinstance(node, ast.BinOp): return resolve(node.left, module, seen) + '/' + resolve(node.right, module, seen)
 if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in ('Path', 'str') and node.args: return resolve(node.args[0], module, seen)
 if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id in modules:
  return resolve(ast.Name(id=node.attr), modules[node.value.id], seen)
 return ''
changes = []
for path in sorted((ROOT/'tools').rglob('*.py')):
 if path.name in ('on_actions.py', 'test_scripted_peace_on_actions.py'): continue
 module = '.'.join(path.relative_to(ROOT).with_suffix('').parts)
 source = path.read_text(encoding='utf-8-sig')
 tree = ast.parse(source)
 lines = source.encode('utf-8').splitlines(keepends=True)
 offsets = [0]
 for line in lines: offsets.append(offsets[-1] + len(line))
 edits, imports = [], set()
 for node in ast.walk(tree):
  if not isinstance(node, ast.Call): continue
  mode, target = None, None
  if isinstance(node.func, ast.Name) and node.func.id in ('read', 'entries', 'relative_entries'):
   for i, argument in enumerate(node.args[:2]):
    resolved = resolve(argument, module)
    if any(name in resolved for name in GROUPS):
     mode = 'entries' if node.func.id != 'read' else 'read'
     target = ast.get_source_segment(source, argument)
     if i == 1: target = '(' + ast.get_source_segment(source, node.args[0]) + ') / (' + target + ')'
     break
  elif isinstance(node.func, ast.Attribute) and node.func.attr == 'read_text':
   resolved = resolve(node.func.value, module)
   if any(name in resolved for name in GROUPS):
    mode, target = 'read', ast.get_source_segment(source, node.func.value)
  if mode is None: continue
  filename = next(name for name in GROUPS if name in resolved)
  function = 'country_on_actions_entries' if mode == 'entries' else 'read_country_on_actions'
  imports.add(function)
  start = offsets[node.lineno-1] + node.col_offset
  end = offsets[node.end_lineno-1] + node.end_col_offset
  edits.append((start, end, f'{function}({target}, {GROUPS[filename]!r})'))
 if not edits: continue
 selected = []
 for start, end, text in sorted(edits, key=lambda r: (r[0], -r[1])):
  if not selected or start >= selected[-1][1]: selected.append((start, end, text))
 data = source.encode('utf-8')
 for start, end, text in reversed(selected): data = data[:start] + text.encode('utf-8') + data[end:]
 new = data.decode('utf-8')
 already = set()
 for node in tree.body:
  if isinstance(node, ast.ImportFrom) and node.module == 'tools.lib.on_actions': already.update(alias.name for alias in node.names)
 needed = sorted(imports - already)
 if needed:
  header_end = 0
  for node in tree.body:
   if (isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str)) or (isinstance(node, ast.ImportFrom) and node.module == '__future__'): header_end = node.end_lineno
   else: break
  new_lines = new.splitlines(keepends=True)
  new_lines.insert(header_end, 'from tools.lib.on_actions import ' + ', '.join(needed) + '\n')
  new = ''.join(new_lines)
 ast.parse(new)
 path.write_text(new, encoding='utf-8')
 changes.append((str(path.relative_to(ROOT)), len(selected)))
print('IMPORTED_READER_UPDATES', changes, flush=True)
shared = ROOT/'common/on_actions/09_ADISCORD_scripted_peace_on_actions.txt'
source = shared.read_text(encoding='utf-8')
shared.write_text('\n'.join(line.rstrip() for line in source.splitlines()) + '\n', encoding='utf-8')
