"""Run repository test modules with explicit, recorded resource bounds."""
from pathlib import Path
import argparse
import concurrent.futures
import json
import os
import signal
import subprocess
import sys
import unittest

EXCLUDED = {'test_default_checks_and_help_are_non_mutating'}

def run_module(root, output, module):
    output.mkdir(parents=True, exist_ok=True)
    log = output / (module + '.log')
    result_file = output / (module + '.json')
    command = [sys.executable, '-B', __file__, str(root), str(output), '--module', module]
    with log.open('w') as stream:
        process = subprocess.Popen(command, cwd=root, stdout=stream, stderr=subprocess.STDOUT, start_new_session=True)
        try:
            code = process.wait(timeout=40)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()
            return {'module': module, 'status': 'timeout', 'seconds': 40}
    if not result_file.exists():
        return {'module': module, 'status': 'crash', 'exit': code}
    return json.loads(result_file.read_text())

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('root', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--module')
    args = parser.parse_args()
    root, output = args.root.resolve(), args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str(root))
    if args.module:
        excluded = []
        def select(suite):
            result = unittest.TestSuite()
            for test in suite:
                if isinstance(test, unittest.TestSuite):
                    result.addTests(select(test))
                elif test.id().rsplit('.', 1)[-1] in EXCLUDED:
                    excluded.append(test.id())
                else:
                    result.addTest(test)
            return result
        suite = select(unittest.defaultTestLoader.loadTestsFromName('tools.tests.' + args.module))
        result = unittest.TextTestRunner(verbosity=2).run(suite)
        report = {
            'module': args.module, 'status': 'completed', 'tests_run': result.testsRun,
            'failures': [{'test': test.id(), 'traceback': trace} for test, trace in result.failures],
            'errors': [{'test': test.id(), 'traceback': trace} for test, trace in result.errors],
            'skipped': [{'test': test.id(), 'reason': reason} for test, reason in result.skipped],
            'excluded': excluded,
        }
        (output / (args.module + '.json')).write_text(json.dumps(report, indent=2))
        return
    modules = sorted(path.stem for path in (root / 'tools/tests').glob('test_*.py'))
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(lambda module: run_module(root, output, module), modules))
    report = {'modules': results, 'tests_run': sum(item.get('tests_run', 0) for item in results)}
    for kind in ['failures', 'errors', 'skipped', 'excluded']:
        report[kind] = [item for module in results for item in module.get(kind, [])]
    report['timeouts'] = [item['module'] for item in results if item['status'] == 'timeout']
    report['crashes'] = [item for item in results if item['status'] == 'crash']
    (output / 'summary.json').write_text(json.dumps(report, indent=2))
    print(json.dumps({key: len(value) if isinstance(value, list) else value for key, value in report.items()}, indent=2), flush=True)

if __name__ == '__main__':
    main()
