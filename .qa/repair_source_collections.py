from pathlib import Path
ROOT = Path.cwd()

def edit(relative, operation):
 p = ROOT / relative
 s = p.read_text(encoding='utf-8')
 s = operation(s)
 p.write_text(s, encoding='utf-8')

def add_import(s):
 line = 'from tools.lib.on_actions import read_country_on_actions\n'
 if line not in s:
  s = s.replace('from __future__ import annotations\n', 'from __future__ import annotations\n' + line, 1)
 return s

def rin(s):
 s = add_import(s)
 anchor = '    events = texts[EVENTS]\n'
 assert s.count(anchor) == 1
 return s.replace(anchor, '    texts[ON_ACTIONS] = read_country_on_actions(ROOT / ON_ACTIONS, "rin")\n\n' + anchor, 1)
edit('tools/validators/validate_adiscord_rin_oath_crisis.py', rin)

def diplomacy(s):
 s = add_import(s)
 old = 'def _load(relative: Path | tuple[Path, ...], issues: list[str]) -> str:'
 assert old in s
 s = s.replace(old, 'def _load(relative: Path | tuple[Path, ...], issues: list[str], *, peace_section: str | None = None) -> str:')
 old = '        source = path.read_text(encoding="utf-8-sig")\n'
 assert s.count(old) == 1
 s = s.replace(old, '        source = (read_country_on_actions(path, peace_section) if peace_section\n                  else path.read_text(encoding="utf-8-sig"))\n')
 old = '_load(DIPLOMACY_ON_ACTIONS, issues)'
 count = s.count(old)
 assert count > 0
 s = s.replace(old, '_load(DIPLOMACY_ON_ACTIONS, issues, peace_section="vorkerland_diplomacy")')
 print('DIPLOMACY_EXPLICIT_LOADS', count)
 return s
edit('tools/validators/validate_adiscord_vorkerland_diplomacy.py', diplomacy)

def spirits(s):
 old = '            ("common/on_actions/01_ADISCORD_vorkerland_collapse_on_actions.txt", None),\n'
 assert s.count(old) == 1
 s = s.replace(old, '')
 anchor = '        runtime = "\\n".join((source_section(read(path), section) if section else read(path)) for path, section in paths)\n'
 assert s.count(anchor) == 1
 return s.replace(anchor, anchor + '        runtime += "\\n" + read_country_on_actions("common/on_actions/01_ADISCORD_vorkerland_collapse_on_actions.txt", "vorkerland_collapse")\n')
edit('tools/tests/test_validate_adiscord_vorkerland_collapse.py', spirits)
