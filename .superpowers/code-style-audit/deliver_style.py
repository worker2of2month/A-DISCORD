from pathlib import Path
import hashlib
import json
import os
import subprocess
import sys

root, output = map(lambda value: Path(value).resolve(), sys.argv[1:])
manifest = json.loads((output / 'style-manifest.json').read_text())
base = manifest['base']

def git(*args, env=None, data=None):
    return subprocess.check_output(['git', *args], cwd=root, env=env, input=data).decode().strip()

before = json.loads((output / 'before/summary.json').read_text())
after = json.loads((output / 'after/summary.json').read_text())
finished_before = {item['module'] for item in before['modules'] if item['status'] == 'completed'}
finished_after = {item['module'] for item in after['modules'] if item['status'] == 'completed'}
common = finished_before & finished_after
failure_ids = lambda report: {item['test'] for module in report['modules'] if module['module'] in common for kind in ['failures', 'errors'] for item in module.get(kind, [])}
new = sorted(failure_ids(after) - failure_ids(before))
fixed = sorted(failure_ids(before) - failure_ids(after))
manifest['tests'] = {'comparable_modules': len(common), 'before_tests_run': before['tests_run'], 'after_tests_run': after['tests_run'], 'new_failures': new, 'resolved_failures': fixed, 'before_timeouts': before['timeouts'], 'after_timeouts': after['timeouts'], 'before_crashes': before['crashes'], 'after_crashes': after['crashes']}
for item in manifest['changed']:
    assert hashlib.sha256((root / item['path']).read_bytes()).hexdigest() == item['after'], item['path']
for item in manifest['changed']:
    original = subprocess.check_output(['git', 'show', base + ':' + item['path']], cwd=root)
    assert hashlib.sha256(original).hexdigest() == item['before'], item['path']
entries = git('ls-tree', '-r', base).splitlines()
modes = {line.split('\t', 1)[1]: line.split(' ', 1)[0] for line in entries}
env = dict(os.environ, GIT_INDEX_FILE='/tmp/code-style-delivery-index', GIT_AUTHOR_NAME='github-actions[bot]', GIT_AUTHOR_EMAIL='41898282+github-actions[bot]@users.noreply.github.com', GIT_COMMITTER_NAME='github-actions[bot]', GIT_COMMITTER_EMAIL='41898282+github-actions[bot]@users.noreply.github.com')
git('read-tree', base, env=env)
parent = base
commits = []
for kinds, message in [({'clausewitz', 'generated-focus'}, 'style: normalize authored Clausewitz scripts and rebuild focus outputs'), ({'python'}, 'style: format Python tooling without changing its syntax trees'), ({'localisation', 'lua'}, 'style: normalize localisation layout and define indentation')]:
    group = [item for item in manifest['changed'] if item['kind'] in kinds]
    if not group:
        continue
    for item in group:
        name = item['path']
        blob = git('hash-object', '-w', name)
        git('update-index', '--add', '--cacheinfo', modes[name], blob, name, env=env)
    tree = git('write-tree', env=env)
    parent = git('commit-tree', tree, '-p', parent, env=env, data=(message + '\n').encode())
    commits.append({'commit': parent, 'message': message, 'files': len(group)})
actual = set(git('diff', '--name-only', base, parent).splitlines())
assert actual == {item['path'] for item in manifest['changed']}
git('diff', '--check', base, parent)
branch = 'codex/repository-code-style-' + os.environ['GITHUB_RUN_ID']
git('push', 'origin', parent + ':refs/heads/' + branch)
manifest.update({'branch': branch, 'head': parent, 'commits': commits})
(output / 'delivery.json').write_text(json.dumps(manifest, indent=2))
print(json.dumps({'branch': branch, 'head': parent, 'changed': len(manifest['changed']), 'counts': manifest['counts'], 'tests': manifest['tests'], 'python_exceptions': manifest['python_exceptions']}, indent=2), flush=True)
