"""Final integration check. Temporary runner, never merge into the mod."""
from pathlib import Path
import hashlib
import json
import re
import subprocess
import sys

ROOT=Path.cwd()
OUT=Path('/tmp/party-evidence');OUT.mkdir(exist_ok=True)
BASE='4cc6d829d2a65233bea2804f30e25c23872383c6'
MAIN='e7776955daca9c404feea90172f6a52343798c20'
FEATURE='f81d6b219cd639d34b92c0cf8f3fa62be9ae626e'
BRANCH='fix/stp-party-faction-progression'
AFTER=Path('/tmp/party-integrated');BEFORE=Path('/tmp/party-main')
PATHS=sorted(['common/national_focus/ADISCORD_national_focus_STP.txt','common/on_actions/02_ADISCORD_STP_on_actions.txt','common/scripted_effects/ADISCORD_STP_scripted_effects.txt','common/scripted_guis/ADISCORD_STP_regions_scripted_gui.txt','common/scripted_localisation/ADISCORD_STP_scripted_loc.txt','interface/ADISCORD_STP_regions.gfx','interface/ADISCORD_STP_regions.gui','localisation/english/ADISCORD_STP_l_english.yml','localisation/russian/ADISCORD_STP_l_russian.yml','tools/tests/test_adiscord_stp_party_balance.py','tools/tests/test_adiscord_stp_party_route.py','tools/tests/test_adiscord_stp_civil_war.py'])
report={'base':BASE,'integrated_main':MAIN,'feature':FEATURE,'previous_run':35693615317,'native_hoi4':'not run','checks':{}}
def git(*args,cwd=ROOT):
    return subprocess.check_output(['git',*args],cwd=cwd,text=True).strip()
def check(name,args,cwd,timeout=180):
    with (OUT/(name+'.txt')).open('w') as log:
        p=subprocess.run(args,cwd=cwd,stdout=log,stderr=subprocess.STDOUT,timeout=timeout)
    text=(OUT/(name+'.txt')).read_text()
    r={'exit':p.returncode,'summary':re.findall(r'^Ran \d+ tests.*$|^FAILED .*|^OK$',text,re.M),'failures':re.findall(r'^(?:FAIL|ERROR): (.+)$',text,re.M)}
    report['checks'][name]=r
    (OUT/'integration-report.json').write_text(json.dumps(report,indent=2))
    print(name,r,flush=True)
    return r
for ref in (BASE,MAIN,FEATURE):git('fetch','--depth=1','origin',ref)
git('worktree','add','--detach',str(AFTER),FEATURE)
git('worktree','add','--detach',str(BEFORE),MAIN)
git('config','user.name','A-Discord maintenance',cwd=AFTER)
git('config','user.email','adiscord-maintenance@users.noreply.github.com',cwd=AFTER)
git('merge','--no-commit','--no-ff',MAIN,cwd=AFTER)
sys.path.insert(0,str(AFTER))
from tools.validators.validate_adiscord_division_templates import parse_clausewitz

def signature(value):
    return [(e.key,signature(e.value) if isinstance(e.value,list) else e.value) for e in value]
def effects(ref):
    path='common/scripted_effects/ADISCORD_STP_scripted_effects.txt'
    text=git('show',ref+':'+path) if ref else (AFTER/path).read_text()
    return {e.key:signature(e.value) if isinstance(e.value,list) else e.value for e in parse_clausewitz(text)}
old,main,feature,merged=effects(BASE),effects(MAIN),effects(FEATURE),effects(None)
expected={k:(feature.get(k) if feature.get(k)!=old.get(k) else main.get(k)) for k in set(main)|set(feature)}
assert merged==expected,'A concurrent scripted-effect change was lost or conflicted'

# This affected test assumed exactly one hidden_effect, although native rewards
# allow several. Preserve strict variable/dummy/refresh checks across all blocks.
case='tools.tests.test_adiscord_stp_civil_war.PostwarFocusContracts'
red=check('preview-red',[sys.executable,'-B','-m','unittest',case+'.test_native_delta_previews_match_every_authoritative_variable_write','-v'],AFTER)
assert red['exit']==1 and len(red['failures'])==1
assert 'Expected one block hidden_effect' in (OUT/'preview-red.txt').read_text()
p=AFTER/'tools/tests/test_adiscord_stp_civil_war.py'
s=p.read_text()
a='            writes = [e.value for e in walk(ast_block(reward, "hidden_effect")) if e.key == "add_to_variable"]'
b='            hidden = [e.value for e in reward if e.key == "hidden_effect"]\n            writes = [e.value for payload in hidden for e in walk(payload) if e.key == "add_to_variable"]'
assert s.count(a)==1;s=s.replace(a,b)
a='            self.assertEqual(scalar(ast_block(reward, "hidden_effect"), "STP_pw_refresh_modifier"), "yes")'
b='            refreshes = [e.value for payload in hidden for e in payload if e.key == "STP_pw_refresh_modifier"]\n            self.assertEqual(refreshes, ["yes"], name)'
assert s.count(a)==1;s=s.replace(a,b);p.write_text(s)
assert sorted(git('diff','--name-only',MAIN,cwd=AFTER).splitlines())==PATHS
hashes={p:hashlib.sha256((AFTER/p).read_bytes()).hexdigest() for p in PATHS}
scoped=[sys.executable,'-B','-m','unittest','tools.tests.test_adiscord_stp_party_balance','tools.tests.test_adiscord_stp_party_route','tools.tests.test_adiscord_stp_party_qol',case+'.test_native_delta_previews_match_every_authoritative_variable_write','-v']
assert check('scoped-final',scoped,AFTER)['exit']==0
expanded=[sys.executable,'-B','-m','unittest',case,'-v']
before=check('postwar-baseline',expanded,BEFORE)
after=check('postwar-final',expanded,AFTER)
assert set(after['failures'])==set(before['failures'])
assert after['exit']==before['exit']
assert check('validator-final',[sys.executable,'-B','tools/validate_tc.py','--limit','300'],AFTER)['exit']==0
for path,sha in hashes.items():
    assert hashlib.sha256((AFTER/path).read_bytes()).hexdigest()==sha,path
for path in PATHS:
    if path.startswith('localisation/'):assert (AFTER/path).read_bytes().startswith(b'\xef\xbb\xbf')
    if Path(path).suffix in ('.txt','.gui','.gfx'):parse_clausewitz((AFTER/path).read_text(encoding='utf-8-sig'))
git('diff','--check',MAIN,cwd=AFTER)
git('diff','--check','--cached',cwd=AFTER)
git('add','--','tools/tests/test_adiscord_stp_civil_war.py',cwd=AFTER)
git('commit','-m','test(stp): preserve concurrent fixes and inspect all hidden reward blocks',cwd=AFTER)
assert not git('status','--porcelain','--untracked-files=no',cwd=AFTER)
assert sorted(git('diff','--name-only',MAIN,'HEAD',cwd=AFTER).splitlines())==PATHS
head=git('rev-parse','HEAD',cwd=AFTER)
git('push','origin','HEAD:refs/heads/'+BRANCH,cwd=AFTER)
report.update({'head':head,'branch':BRANCH,'files':PATHS,'source_sha256':hashes,'concurrent_effects_preserved':True})
(OUT/'integration-report.json').write_text(json.dumps(report,indent=2))
(OUT/'final-gameplay.diff').write_text(git('diff','--binary',MAIN,'HEAD',cwd=AFTER)+'\n')
print('DELIVERED',head,flush=True)
