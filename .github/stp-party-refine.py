"""Finish source formatting and validate the concrete focus references."""
from pathlib import Path
import difflib
import re
import subprocess
import sys

sys.path.insert(0, str(Path.cwd()))
from tools.validators.validate_adiscord_division_templates import parse_clausewitz


def read(path):
    return Path(path).read_text(encoding='utf-8-sig')


def write(path, text):
    raw = Path(path).read_bytes()
    enc = 'utf-8-sig' if raw.startswith(b'\xef\xbb\xbf') else 'utf-8'
    Path(path).write_text(text, encoding=enc, newline='')


path = 'common/decisions/categories/ADISCORD_decision_categories_STP.txt'
text = read(path)
text = text.replace('                    has_completed_focus = STP_ps_expedition_request\n', '')
write(path, text)

# Only clean newly inserted/replaced lines; leave unrelated authored whitespace alone.
for path in subprocess.check_output(['git', 'diff', '--name-only'], text=True).splitlines():
    raw = Path(path).read_bytes()
    before = subprocess.check_output(['git', 'show', 'HEAD:' + path]).decode('utf-8-sig').splitlines(keepends=True)
    after = raw.decode('utf-8-sig').splitlines(keepends=True)
    edits = difflib.SequenceMatcher(a=before, b=after, autojunk=False).get_opcodes()
    for operation, a0, a1, b0, b1 in edits:
        if operation in ('insert', 'replace'):
            for i in range(b0, b1):
                after[i] = after[i].rstrip() + ('\n' if after[i].endswith('\n') else '')
    write(path, ''.join(after))

print('FOCUS_AND_COPY_REVIEW')
for line in read('common/national_focus/ADISCORD_national_focus_STP.txt').splitlines():
    if 'id = STP_ps_' in line and any(term in line for term in ('northern', 'expedition')):
        print(line.strip())
for lang in ('russian', 'english'):
    for line in read(f'localisation/{lang}/ADISCORD_STP_l_{lang}.yml').splitlines():
        if line.lstrip().startswith(('STP_ps_war_report:', 'STP_ps_northern_fund:', 'STP_ps_expedition_nod:')):
            print(lang, line)
