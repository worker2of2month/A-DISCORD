"""Temporary pinned-source verifier. Never merge this runner into gameplay."""
from pathlib import Path
import base64
import hashlib
import json
import lzma
import os
import subprocess
import sys

BASE = 'bb0d60563451a2a1a83c93bfb83ca81d12384e7e'
PATCH_SHA = 'acb9b9e60351fe7c226ee2da303a17a39018dedf663be4ff8fba59542233b82b'
OUTPUT_SHA = '234ece2dbf4f8c5ee8b5645cc03a9e55216118bcf743bb83dfa990ab2ec262b7'
OUT = Path('/tmp/roster-evidence')
OUT.mkdir(exist_ok=True)
root = Path.cwd()
payload = ''.join((root / f'.github/roster_payload_{i}.txt').read_text().strip() for i in range(3))
assert len(payload) == 20508, len(payload)
patch = lzma.decompress(base64.b64decode(payload, validate=True))
assert hashlib.sha256(patch).hexdigest() == PATCH_SHA, 'Patch transport mismatch'
patch_path = OUT / 'gameplay.patch'
patch_path.write_bytes(patch)
manifest = {'base': BASE, 'native_hoi4_run': False, 'patch_sha256': PATCH_SHA}


def save():
    (OUT / 'manifest.json').write_text(json.dumps(manifest, indent=2))


def git(*args):
    return subprocess.check_output(['git', *args], text=True).strip()


TEST_RUNNER = r'''
import sys,json,unittest,signal,time,traceback
from pathlib import Path
sys.path.insert(0,str(Path.cwd()))
prefix=Path(sys.argv[1]); timeout=int(sys.argv[2]); names=sys.argv[3:]
state={'count':0,'completed':False,'timeout':False,'failures':[],'errors':[],'skipped':[],'started':[],'finished':[]}
def save():prefix.with_suffix('.json').write_text(json.dumps(state,indent=2))
class Result(unittest.TextTestResult):
    def startTest(self,test):
        super().startTest(test);state['started'].append(test.id());save()
    def stopTest(self,test):
        super().stopTest(test);state['count']=self.testsRun;state['finished'].append(test.id());save()
    def addFailure(self,test,err):
        super().addFailure(test,err);state['failures'].append(test.id());save()
    def addError(self,test,err):
        super().addError(test,err);state['errors'].append(test.id());save()
    def addSubTest(self,test,subtest,err):
        super().addSubTest(test,subtest,err)
        if err:
            state['failures' if issubclass(err[0],test.failureException) else 'errors'].append(test.id());save()
    def addSkip(self,test,reason):
        super().addSkip(test,reason);state['skipped'].append([test.id(),reason]);save()
def alarm(*_):
    state['timeout']=True;save();raise KeyboardInterrupt('test time budget exceeded')
signal.signal(signal.SIGALRM,alarm);signal.alarm(timeout)
start=time.monotonic()
with prefix.with_suffix('.log').open('w') as out:
    try:
        suite=unittest.defaultTestLoader.discover('tools/tests') if names==['discover'] else unittest.defaultTestLoader.loadTestsFromNames(names)
        unittest.TextTestRunner(stream=out,verbosity=2,resultclass=Result).run(suite)
        state['completed']=True
    except BaseException as exc:
        state['fatal']=str(exc);traceback.print_exc(file=out)
state['seconds']=time.monotonic()-start;save()
print(json.dumps({k:v for k,v in state.items() if k not in ('started','finished','skipped')}))
'''
runner = OUT / 'run_tests.py'
runner.write_text(TEST_RUNNER)
modules = ['tools.tests.test_adiscord_stp_civil_war', 'tools.tests.test_adiscord_stp_startup',
           'tools.tests.test_adiscord_stp_postwar_continuation', 'tools.tests.test_adiscord_party_texticons',
           'tools.tests.test_val_contract_ui']


def tests(label, names, timeout=150):
    prefix = OUT / label
    with (OUT / (label + '.console')).open('w') as out:
        subprocess.run([sys.executable, '-B', str(runner), str(prefix), str(timeout), *names],
                       stdout=out, stderr=subprocess.STDOUT, check=True, timeout=timeout+20)
    result = json.loads(prefix.with_suffix('.json').read_text())
    manifest[label] = {k:v for k,v in result.items() if k not in ('started','finished')}
    save()
    return result


save()
# Read the complete payload before leaving the temporary verification branch.
git('fetch', '--depth=1', 'origin', BASE)
git('switch', '--detach', BASE)
assert git('rev-parse', 'HEAD') == BASE
baseline = tests('baseline_scoped', modules)
subprocess.run(['git', 'apply', '--check', '--unidiff-zero', str(patch_path)], check=True)
subprocess.run(['git', 'apply', '--unidiff-zero', str(patch_path)], check=True)
paths = git('diff', '--name-only').splitlines()
paths += [p for p in git('ls-files', '--others', '--exclude-standard').splitlines()
          if p in ('tools/tests/test_adiscord_playable_rosters.py',
                   'common/military_industrial_organization/organizations/ADISCORD_playable_organizations.txt')]
paths = sorted(set(paths))
assert len(paths) == 26, paths
assert not any(p.startswith('.github/') for p in paths)
hashes = {p: hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in paths}
assert hashlib.sha256(json.dumps(hashes, sort_keys=True, separators=(',',':')).encode()).hexdigest() == OUTPUT_SHA, 'Reviewed output changed'
manifest['files'] = paths
manifest['sha256'] = hashes
save()
sys.path.insert(0,str(root))
from tools.validators.validate_adiscord_division_templates import parse_clausewitz
for p in paths:
    b = Path(p).read_bytes()
    text = b.decode('utf-8-sig')
    if p.endswith('.txt'):
        assert not b.startswith(b'\xef\xbb\xbf'), p
        parse_clausewitz(text)
    if p.endswith('.yml'):
        assert b.startswith(b'\xef\xbb\xbf'), p
        assert text.splitlines()[0].startswith('l_'), p
    if p.endswith('.py'):
        compile(text,p,'exec')
subprocess.run(['git','diff','--check'],check=True)
scoped = tests('roster_tests', ['tools.tests.test_adiscord_playable_rosters'], 60)
assert scoped['completed'] and scoped['count'] == 20 and not scoped['failures'] and not scoped['errors'], scoped
final = tests('final_scoped', modules)
assert baseline['completed'] and final['completed'], 'Expanded comparative suite did not finish; inspect artifacts'
new_failures = set(final['failures']) - set(baseline['failures'])
new_errors = set(final['errors']) - set(baseline['errors'])
manifest['new_comparative_failures'] = sorted(new_failures)
manifest['new_comparative_errors'] = sorted(new_errors)
save()
assert not new_failures and not new_errors, (new_failures,new_errors)
# A bounded whole-repository run is reported independently, never as a green suite.
tests('whole_repository', ['discover'], 90)
with (OUT / 'validator.log').open('w') as out:
    try:
        result = subprocess.run([sys.executable,'-B','tools/validate_tc.py','--limit','300'],
                                stdout=out,stderr=subprocess.STDOUT,timeout=90)
        manifest['validator_returncode'] = result.returncode
    except subprocess.TimeoutExpired:
        manifest['validator_timeout'] = True
save()
subprocess.run(['git','add','--',*paths],check=True)
subprocess.run(['git','diff','--cached','--check'],check=True)
assert sorted(git('diff','--cached','--name-only').splitlines()) == paths
(OUT / 'delivery.diff').write_text(git('diff','--cached'))
(OUT / 'diffstat.txt').write_text(git('diff','--cached','--stat'))
# Only the audited gameplay/test files become part of the delivery branch.
branch = 'feat/playable-rosters-delivery-' + os.environ['GITHUB_RUN_ID']
git('switch','-c',branch)
git('config','user.name','worker2of2month')
git('config','user.email','81386071+worker2of2month@users.noreply.github.com')
git('commit','-m','feat: playable rosters and living party leadership',
    '-m','Add baseline and focus-gated elite ministers, officers, MIOs and companies to featured countries. Every new Stelander appointment requires the completed civil war. Keep prewar party leaders tied to active characters and clear labels on the split. Twenty targeted tests pass; expanded baseline comparison has no new failure identities. Native HOI4 not run.')
manifest['delivery_branch'] = branch
manifest['delivery_sha'] = git('rev-parse','HEAD')
manifest['delivery_tree'] = git('rev-parse','HEAD^{tree}')
save()
git('push','origin','HEAD:refs/heads/'+branch)
manifest['published'] = True
save()
print(json.dumps({'delivery_branch':branch,'delivery_sha':manifest['delivery_sha'],
                  'roster_tests':scoped['count'],'files':len(paths),'published':True}),flush=True)
