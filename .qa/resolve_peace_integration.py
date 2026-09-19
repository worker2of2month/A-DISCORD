"""Preserve current main in the two overlapping documentation/test files."""
import os
import subprocess
import sys
from pathlib import Path
EXPECTED = {'docs/development/focus-effects.md', 'tools/tests/test_adiscord_stp_postwar_continuation.py'}
conflicts = set(subprocess.check_output(['git', 'diff', '--name-only', '--diff-filter=U']).decode().splitlines())
assert conflicts == EXPECTED, ('Unexpected conflicts', conflicts)
subprocess.run(['git', 'checkout', '--ours', '--', *sorted(conflicts)], check=True)
# Retain every current economy paragraph and append only the reviewed architecture section.
p = Path('docs/development/focus-effects.md')
s = p.read_text(encoding='utf-8')
old = 'Его обработчик `09_ADISCORD_VAL_livonn_settlement_on_actions.txt` остаётся отдельным, поскольку выполняется после военного урегулирования.'
new = 'Его раздел `livonn` находится в `09_ADISCORD_scripted_peace_on_actions.txt` после военного урегулирования STP/SRP. Ограниченная недельная проверка завершения договора сохраняется.'
assert s.count(old) == 1, 'Livonn documentation anchor changed'
s = s.replace(old, new)
reviewed = subprocess.check_output(['git', 'show', '0e70ce7b5314bf8ad28f83fc3175792b0b699630:docs/development/focus-effects.md']).decode('utf-8')
heading = '\n## Диспетчеризация скриптового мира\n'
assert s.count(heading) == 0 and reviewed.count(heading) == 1
s += heading + reviewed.split(heading, 1)[1]
p.write_text(s, encoding='utf-8')
# Reapply only explicit native-source reader changes to the current test version.
subprocess.run([sys.executable, str(Path(os.environ['RUNNER_TEMP'])/'repair_imported_readers.py')], check=True)
subprocess.run(['git', 'add', '--', *sorted(conflicts)], check=True)
assert not subprocess.check_output(['git', 'diff', '--name-only', '--diff-filter=U']).strip()
print('RESOLVED_WITH_CURRENT_MAIN_AND_EXPLICIT_SOURCE_READERS', flush=True)
