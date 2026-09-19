import io, json, sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path.cwd()))
words = ('stp', 'nod', 'val_', 'val_rework', 'rin_', 'nam_', 'vorkerland', 'scripted_peace', 'sts_successor', 'inner_frontier', 'force_designs', 'wrk_ideology')
names = ['tools.tests.' + p.stem for p in sorted(Path('tools/tests').glob('test*.py')) if any(w in p.stem for w in words)]
result = unittest.TextTestRunner(stream=io.StringIO(), verbosity=0).run(unittest.defaultTestLoader.loadTestsFromNames(names))
problems = {t.id(): error for t, error in result.failures + result.errors}
report = {'tests': result.testsRun, 'problems': problems, 'failures': len(result.failures), 'errors': len(result.errors)}
Path(sys.argv[1]).write_text(json.dumps(report))
print('TESTS', result.testsRun, 'FAILURES', len(result.failures), 'ERRORS', len(result.errors), flush=True)
if len(sys.argv) > 2:
 before = json.loads(Path(sys.argv[2]).read_text())
 new = set(problems) - set(before['problems'])
 fixed = set(before['problems']) - set(problems)
 # A formerly failing assertion becoming an unrelated reader error is also a regression.
 def kind(trace):
  for line in reversed(trace.splitlines()):
   if line and not line[0].isspace() and ':' in line and ('Error' in line.split(':', 1)[0] or 'Exception' in line.split(':', 1)[0]): return line.split(':', 1)[0]
  return 'unknown'
 changed = {name for name in set(problems) & set(before['problems']) if kind(problems[name]) != kind(before['problems'][name])}
 print('NEW_PROBLEMS', sorted(new), flush=True)
 print('CHANGED_FAILURE_TYPES', sorted(changed), flush=True)
 print('BASELINE_PROBLEMS_RESOLVED', sorted(fixed), flush=True)
 print('REMAINING_BASELINE_PROBLEMS', sorted(set(problems) - new), flush=True)
 for name in sorted(new | changed): print(name, '\n', problems[name][-3500:], flush=True)
 if new or changed: sys.exit(1)
