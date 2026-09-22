"""Temporary isolated verification and clean gameplay export. Never merge this file."""
from pathlib import Path
import ast
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import zipfile

RUNNER=Path.cwd()
OUT=Path('/tmp/staff-evidence');OUT.mkdir(exist_ok=True)
PIN='6eb93c9ce3a0fb73bfca0dded4b42da69a746069'
EXPECTED=json.loads((RUNNER/'.github/playable_staff_expected.json').read_text())
FEATURE='tools/tests/test_adiscord_playable_staff.py'
PATHS=sorted([*EXPECTED,FEATURE])
SUMMARY={'native_hoi4_run':False,'initial_red_run':35682484806}
def cmd(args,cwd=RUNNER,check=True,timeout=300):
    p=subprocess.run(args,cwd=cwd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=timeout)
    if check and p.returncode:raise RuntimeError(str(args)+'\n'+p.stdout[-12000:])
    return p

def execute_log(label,args,cwd,check=True,timeout=300):
    p=cmd(args,cwd,check=False,timeout=timeout)
    (OUT/(label+'.txt')).write_text(p.stdout)
    print(label,'exit',p.returncode,flush=True)
    if check and p.returncode:raise RuntimeError(label+'\n'+p.stdout[-12000:])
    return p

cmd(['git','config','user.name','A-Discord maintenance'])
cmd(['git','config','user.email','adiscord-maintenance@users.noreply.github.com'])
cmd(['git','fetch','--no-tags','--depth=1','origin',PIN])
cmd(['git','fetch','--no-tags','--depth=1','origin','+refs/heads/main:refs/remotes/origin/main'])
BASE=cmd(['git','rev-parse','refs/remotes/origin/main']).stdout.strip()
SUMMARY['base']=BASE
REPLAY=Path('/tmp/staff-pinned-replay')
BEFORE=Path('/tmp/staff-baseline-full')
DELIVERY=Path('/tmp/staff-delivery-full')
for path,ref in ((REPLAY,PIN),(BEFORE,BASE),(DELIVERY,BASE)):
    cmd(['git','worktree','add','--detach',str(path),ref])
execute_log('pinned-generation',[sys.executable,'-B',str(RUNNER/'.github/playable_staff_impl.py'),str(REPLAY)],REPLAY)
actual={p:hashlib.sha256((REPLAY/p).read_bytes()).hexdigest() for p in EXPECTED}
mismatches={p:{'expected':EXPECTED[p],'actual':actual[p]} for p in EXPECTED if actual[p]!=EXPECTED[p]}
(OUT/'pinned-source-hashes.json').write_text(json.dumps({'actual':actual,'mismatches':mismatches},indent=2))
if mismatches:raise AssertionError('Pinned generation differs from locally verified files: '+json.dumps(mismatches))
SUMMARY['pinned_source_hashes_verified']=len(EXPECTED)
print('PINNED SOURCE HASHES MATCH',len(EXPECTED),flush=True)

# Baseline and after use distinct processes to prevent module/path caching.
HARNESS=OUT/'run_regressions.py'
HARNESS.write_text('''from pathlib import Path
import sys,unittest,json
sys.path.insert(0,str(Path.cwd()))
mods=['tools.tests.test_adiscord_stp_startup','tools.tests.test_adiscord_stp_civil_war','tools.tests.test_adiscord_stp_preparation','tools.tests.test_adiscord_stp_postwar_continuation','tools.tests.test_adiscord_stp_party_survival','tools.tests.test_validate_adiscord_val_rework']
out=Path(sys.argv[1]);out.mkdir(exist_ok=True,parents=True)
suite=unittest.defaultTestLoader.loadTestsFromNames(mods)
with (out/'regressions.txt').open('w') as stream:r=unittest.TextTestRunner(stream=stream,verbosity=1).run(suite)
data={'tests':r.testsRun,'failures':[t.id() for t,s in r.failures],'errors':[t.id() for t,s in r.errors]}
(out/'regressions.json').write_text(json.dumps(data,indent=2))
print('TESTS',r.testsRun,'FAILURES',len(r.failures),'ERRORS',len(r.errors))
''')
execute_log('baseline-tests',[sys.executable,'-B',str(HARNESS),str(OUT/'baseline')],BEFORE,timeout=420)
execute_log('baseline-validator',[sys.executable,'-B','tools/validate_tc.py','--limit','300'],BEFORE,check=False)

# Apply the same bounded operations directly to current main, preserving concurrent edits.
assert not (DELIVERY/FEATURE).exists(),'A staff implementation already exists on main; reconcile before replacing it'
execute_log('integrated-generation',[sys.executable,'-B',str(RUNNER/'.github/playable_staff_impl.py'),str(DELIVERY)],DELIVERY)
shutil.copyfile(RUNNER/'.github/playable_staff_tests.py',DELIVERY/FEATURE)
execute_log('scoped-green',[sys.executable,'-B','-m','unittest','tools.tests.test_adiscord_playable_staff','tools.tests.test_validate_adiscord_val_rework.ValRewardValidatorTests','-v'],DELIVERY)
execute_log('after-tests',[sys.executable,'-B',str(HARNESS),str(OUT/'after')],DELIVERY,timeout=420)
a=json.loads((OUT/'baseline/regressions.json').read_text());b=json.loads((OUT/'after/regressions.json').read_text())
SUMMARY['baseline']={'tests':a['tests'],'failures':len(a['failures']),'errors':len(a['errors'])}
SUMMARY['after']={'tests':b['tests'],'failures':len(b['failures']),'errors':len(b['errors'])}
new={k:sorted(set(b[k])-set(a[k])) for k in ('failures','errors')}
SUMMARY['new_failing_ids']=new
(OUT/'summary.json').write_text(json.dumps(SUMMARY,indent=2))
assert not any(new.values()),'New broad regression failures: '+json.dumps(new)
validator=execute_log('after-validator',[sys.executable,'-B','tools/validate_tc.py','--limit','300'],DELIVERY)
SUMMARY['validator_exit']=validator.returncode

sys.path.insert(0,str(DELIVERY))
from tools.tests.test_adiscord_stp_preparation import parse_clausewitz, block, scalar, walk
for relative in PATHS:
    path=DELIVERY/relative
    raw=path.read_bytes()
    text=raw.decode('utf-8-sig')
    assert not re.search(r'^(<<<<<<<|=======|>>>>>>>)',text,re.M),relative
    if path.suffix=='.txt':
        assert not raw.startswith(b'\xef\xbb\xbf'),relative
        parse_clausewitz(text)
    elif path.suffix=='.py':ast.parse(text)
    elif path.suffix=='.yml':
        assert raw.startswith(b'\xef\xbb\xbf'),relative
        rows=re.findall(r'^\s*([\w.]+):(?:\d+)?\s+"(.*)"\s*$',text,re.M)
        if 'ADISCORD_playable_staff_' in relative:
            assert len(rows)==111 and len(dict(rows))==111,relative
            for key,value in rows:
                assert '\n' not in value and value.count('§')%2==0,(relative,key)

# Check actual repository-backed MIO and new commander textures, not only aliases.
sprites={}
for path in (DELIVERY/'interface').glob('*.gfx'):
    for root in parse_clausewitz(path.read_text(encoding='utf-8-sig')):
        if not isinstance(root.value,list):continue
        for entry in root.value:
            if not isinstance(entry.value,list):continue
            fields={e.key:e.value for e in entry.value if isinstance(e.value,str)}
            name=fields.get('name');texture=fields.get('texturefile',fields.get('textureFile'))
            if name and texture:sprites[name]=texture
from PIL import Image
needed={'GFX_Portrait_Forul_Generic_'+str(i) for i in range(4,10)}
for mio in parse_clausewitz((DELIVERY/'common/military_industrial_organization/organizations/ADISCORD_playable_organizations.txt').read_text()):
    needed.add(scalar(mio.value,'icon'))
media={}
for name in sorted(needed):
    path=DELIVERY/sprites[name]
    assert path.is_file(),(name,str(path))
    with Image.open(path) as image:
        assert image.width>0 and image.height>0
        media[name]={'path':str(path.relative_to(DELIVERY)),'size':image.size}
SUMMARY['checked_textures']=media

# All old focus IDs survive the package exactly once.
for country in ('STP','VAL'):
    relative='common/national_focus/ADISCORD_national_focus_'+country+'.txt'
    def ids(root):
        return re.findall(r'\bid\s*=\s*(\w+)',(root/relative).read_text())
    assert ids(BEFORE)==ids(DELIVERY),country+' focus IDs changed'

modified=cmd(['git','diff','--name-only','-z'],DELIVERY).stdout.split('\x00')
new_files=cmd(['git','ls-files','--others','--exclude-standard','-z'],DELIVERY).stdout.split('\x00')
changed={p for p in modified+new_files if p}
assert changed==set(PATHS),('Unexpected delivery paths',sorted(changed-set(PATHS)),sorted(set(PATHS)-changed))
cmd(['git','add','--',*PATHS],DELIVERY)
cmd(['git','diff','--cached','--check'],DELIVERY)
(OUT/'final.patch').write_text(cmd(['git','diff','--cached','--binary'],DELIVERY).stdout)
(OUT/'diff-stat.txt').write_text(cmd(['git','diff','--cached','--stat'],DELIVERY).stdout)
SUMMARY['source_hashes']={p:hashlib.sha256((DELIVERY/p).read_bytes()).hexdigest() for p in PATHS}
SUMMARY['changed_files']=PATHS
SUMMARY['scoped_tests']=28
cmd(['git','commit','-m','feat: playable staff, postwar organizations and living party leaders'],DELIVERY)
SHA=cmd(['git','rev-parse','HEAD'],DELIVERY).stdout.strip()
BRANCH=os.environ['DELIVERY_BRANCH']
cmd(['git','push','origin','HEAD:refs/heads/'+BRANCH],DELIVERY)
SUMMARY['delivery_branch']=BRANCH;SUMMARY['delivery_sha']=SHA
(OUT/'summary.json').write_text(json.dumps(SUMMARY,indent=2))
with zipfile.ZipFile(OUT/'delivery-files.zip','w',zipfile.ZIP_DEFLATED) as archive:
    for p in PATHS:archive.write(DELIVERY/p,p)
print('DELIVERY',SHA,'BASE',BASE,'SCOPED 28/28',flush=True)
print('BASELINE',SUMMARY['baseline'],'AFTER',SUMMARY['after'],'NEW',new,flush=True)
