"""Final artwork-only review of the gameplay verified by run 35684528707."""
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
BASE='84104110e06281b14a042976e26a871101d719a5'
EXPECTED=json.loads((RUNNER/'.github/playable_staff_expected.json').read_text())
FEATURE='tools/tests/test_adiscord_playable_staff.py'
PATHS=sorted([*EXPECTED,FEATURE])
SUMMARY={'native_hoi4_run':False,'initial_red_run':35682484806,
         'expanded_regression_run':35684528707,'expanded_regression_artifact':10676322424,
         'expanded_regression_base':BASE,
         'baseline':{'tests':496,'failures':48,'errors':7},
         'after_before_artwork_only_correction':{'tests':497,'failures':48,'errors':7},
         'new_failing_ids_in_expanded_run':{'failures':[],'errors':[]}}

def cmd(args,cwd=RUNNER,check=True,timeout=300):
    p=subprocess.run(args,cwd=cwd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=timeout)
    if check and p.returncode:raise RuntimeError(str(args)+'\n'+p.stdout[-12000:])
    return p

def log(label,args,cwd,check=True,timeout=300):
    p=cmd(args,cwd,check=False,timeout=timeout)
    (OUT/(label+'.txt')).write_text(p.stdout)
    print(label,'exit',p.returncode,flush=True)
    if check and p.returncode:raise RuntimeError(label+'\n'+p.stdout[-12000:])
    return p

cmd(['git','config','user.name','A-Discord maintenance'])
cmd(['git','config','user.email','adiscord-maintenance@users.noreply.github.com'])
cmd(['git','fetch','--no-tags','--depth=1','origin',PIN])
cmd(['git','fetch','--no-tags','--depth=1','origin','+refs/heads/main:refs/remotes/origin/main'])
assert cmd(['git','rev-parse','origin/main']).stdout.strip()==BASE,'Main changed since expanded verification; revalidate rather than reusing its evidence'
SUMMARY['base']=BASE
REPLAY=Path('/tmp/staff-pinned-replay')
DELIVERY=Path('/tmp/staff-delivery-full')
for path,ref in ((REPLAY,PIN),(DELIVERY,BASE)):
    cmd(['git','worktree','add','--detach',str(path),ref])
log('pinned-generation',[sys.executable,'-B',str(RUNNER/'.github/playable_staff_impl.py'),str(REPLAY)],REPLAY)
actual={p:hashlib.sha256((REPLAY/p).read_bytes()).hexdigest() for p in EXPECTED}
assert actual==EXPECTED,'Implementation no longer reproduces the verified source'
SUMMARY['pinned_source_hashes_verified']=len(EXPECTED)
log('integrated-generation',[sys.executable,'-B',str(RUNNER/'.github/playable_staff_impl.py'),str(DELIVERY)],DELIVERY)
shutil.copyfile(RUNNER/'.github/playable_staff_tests.py',DELIVERY/FEATURE)
SUMMARY['before_artwork_source_hashes']={p:hashlib.sha256((DELIVERY/p).read_bytes()).hexdigest() for p in PATHS}

# The previous full-repository run completed both suites and validators before
# exposing a dependency on an unbundled vanilla texture. Replace only NEW
# objects' picture/icon values, never the existing national laws' aliases.
sys.path.insert(0,str(DELIVERY))
from tools.tests.test_adiscord_stp_preparation import parse_clausewitz, block, scalar, walk
MIO='common/military_industrial_organization/organizations/ADISCORD_playable_organizations.txt'
IDEAS=['common/ideas/ADISCORD_STP_civil_war_ideas.txt','common/ideas/ADISCORD_VAL_rework_ideas.txt']
replacements={
 'ADISCORD_law_industrial_policy_military_prioritization':'ADISCORD_economic_system_state_coordinated',
 'ADISCORD_law_information_state_bulletins':'ADISCORD_economic_system_technocratic',
 'ADISCORD_law_military_cadre_army':'ADISCORD_economic_system_industrializing',
 'ADISCORD_law_infrastructure_regional_roadworks':'ADISCORD_economic_system_mixed',
}

def presentation_free(nodes):
    return [(e.key,presentation_free(e.value) if isinstance(e.value,list) else e.value)
            for e in nodes if e.key not in ('picture','icon')]

for relative in [MIO,*IDEAS]:
    path=DELIVERY/relative;old=path.read_text();source=parse_clausewitz(old)
    rows=old.splitlines(keepends=True)
    if relative==MIO:
        allowed_lines={e.line for e in walk(source) if e.key=='icon'}
    else:
        ideas=block(source,'ideas')
        allowed_lines=set()
        for group in ideas:
            if not isinstance(group.value,list):continue
            for idea in group.value:
                if '_qol_' in idea.key and isinstance(idea.value,list):
                    allowed_lines.update(e.line for e in idea.value if e.key=='picture')
    changes=0
    for number in allowed_lines:
        line=rows[number-1]
        for before,after in replacements.items():line=line.replace(before,after)
        changes+=int(line!=rows[number-1]);rows[number-1]=line
    new=''.join(rows)
    assert changes>0,relative
    assert presentation_free(source)==presentation_free(parse_clausewitz(new)),relative+' changed non-presentation semantics'
    path.write_text(new)
SUMMARY['artwork_only_files']=[MIO,*IDEAS]
SUMMARY['expanded_tests_reused_for_identical_gameplay_semantics']=True
log('scoped-green',[sys.executable,'-B','-m','unittest','tools.tests.test_adiscord_playable_staff','tools.tests.test_validate_adiscord_val_rework.ValRewardValidatorTests','-v'],DELIVERY)
validator=log('final-validator',[sys.executable,'-B','tools/validate_tc.py','--limit','300'],DELIVERY)
SUMMARY['validator_exit']=validator.returncode

for relative in PATHS:
    path=DELIVERY/relative;raw=path.read_bytes();text=raw.decode('utf-8-sig')
    assert not re.search(r'^(<<<<<<<|=======|>>>>>>>)',text,re.M),relative
    if path.suffix=='.txt':
        assert not raw.startswith(b'\xef\xbb\xbf'),relative
        parse_clausewitz(text)
    elif path.suffix=='.py':ast.parse(text)
    elif path.suffix=='.yml':
        assert raw.startswith(b'\xef\xbb\xbf'),relative
        if 'ADISCORD_playable_staff_' in relative:
            rows=re.findall(r'^\s*([\w.]+):(?:\d+)?\s+"(.*)"\s*$',text,re.M)
            assert len(rows)==111 and len(dict(rows))==111,relative
            for key,value in rows:assert '\n' not in value and value.count('§')%2==0,(relative,key)

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
for mio in parse_clausewitz((DELIVERY/MIO).read_text()):
    needed.update(e.value for e in walk(mio.value) if e.key=='icon')
for relative in IDEAS:
    for group in block(parse_clausewitz((DELIVERY/relative).read_text()),'ideas'):
        if not isinstance(group.value,list):continue
        for idea in group.value:
            if '_qol_' in idea.key and isinstance(idea.value,list):
                needed.update('GFX_idea_'+e.value for e in idea.value if e.key=='picture')
media={}
for name in sorted(needed):
    path=DELIVERY/sprites[name]
    assert path.is_file(),(name,str(path))
    with Image.open(path) as image:
        assert image.width>0 and image.height>0
        media[name]={'path':str(path.relative_to(DELIVERY)),'size':image.size}
SUMMARY['checked_textures']=media

for country in ('STP','VAL'):
    relative='common/national_focus/ADISCORD_national_focus_'+country+'.txt'
    before=cmd(['git','show',BASE+':'+relative]).stdout
    assert re.findall(r'\bid\s*=\s*(\w+)',before)==re.findall(r'\bid\s*=\s*(\w+)',(DELIVERY/relative).read_text()),country+' focus IDs changed'
modified=cmd(['git','diff','--name-only','-z'],DELIVERY).stdout.split('\x00')
new_files=cmd(['git','ls-files','--others','--exclude-standard','-z'],DELIVERY).stdout.split('\x00')
changed={p for p in modified+new_files if p}
assert changed==set(PATHS),('Unexpected paths',sorted(changed-set(PATHS)),sorted(set(PATHS)-changed))
cmd(['git','add','--',*PATHS],DELIVERY)
cmd(['git','diff','--cached','--check'],DELIVERY)
(OUT/'final.patch').write_text(cmd(['git','diff','--cached','--binary'],DELIVERY).stdout)
(OUT/'diff-stat.txt').write_text(cmd(['git','diff','--cached','--stat'],DELIVERY).stdout)
SUMMARY['source_hashes']={p:hashlib.sha256((DELIVERY/p).read_bytes()).hexdigest() for p in PATHS}
SUMMARY['changed_files']=PATHS;SUMMARY['scoped_tests']=28
cmd(['git','commit','-m','feat: playable staff, postwar organizations and living party leaders'],DELIVERY)
SHA=cmd(['git','rev-parse','HEAD'],DELIVERY).stdout.strip()
BRANCH=os.environ['DELIVERY_BRANCH']
cmd(['git','push','origin','HEAD:refs/heads/'+BRANCH],DELIVERY)
SUMMARY['delivery_branch']=BRANCH;SUMMARY['delivery_sha']=SHA
(OUT/'summary.json').write_text(json.dumps(SUMMARY,indent=2))
with zipfile.ZipFile(OUT/'delivery-files.zip','w',zipfile.ZIP_DEFLATED) as archive:
    for p in PATHS:archive.write(DELIVERY/p,p)
print('DELIVERY',SHA,'BASE',BASE,'SCOPED 28/28',flush=True)
print('Expanded regression evidence: run 35684528707, 496 before / 497 after, identical 48 failures and 7 errors; final change is artwork only.',flush=True)
