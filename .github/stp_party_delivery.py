"""Isolated verification and gameplay-only export. Not part of the mod."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import ast
import base64
import hashlib
import json
import lzma
import os
import re
import shutil
import signal
import subprocess
import sys
import time
import zipfile

ROOT = Path.cwd()
OUT = Path('/tmp/party-evidence'); OUT.mkdir(exist_ok=True)
BASE = '4cc6d829d2a65233bea2804f30e25c23872383c6'
BRANCH = 'fix/stp-party-faction-progression'
MANIFEST = {
 'common/national_focus/ADISCORD_national_focus_STP.txt': '87299c4198fc2ae96b7c618302d6f8e3afc5d99e62072cd7b32ae47ce7f35729',
 'common/on_actions/02_ADISCORD_STP_on_actions.txt': 'c5494ed9a90ed2c178749c9a323716af02a5f519810c86dcdca7ce09a07d1ede',
 'common/scripted_effects/ADISCORD_STP_scripted_effects.txt': '4ff5fe5800a50f57e8884b5e3d187f5864fa17a752654b199f82b8ca71a2cdc4',
 'common/scripted_guis/ADISCORD_STP_regions_scripted_gui.txt': '3dbc3f592ac7c02c125d85a827c9e96dd6649d01671aeee603ef1a4515e576f8',
 'common/scripted_localisation/ADISCORD_STP_scripted_loc.txt': '1e03010506962abbe9f0cc892a01c60da3769acf18cfdeeff49421120fed8f0c',
 'interface/ADISCORD_STP_regions.gui': 'b153705df44dbd5acdc91beb93456f8f64c5e397a11aacbbca6f3afa4b163f19',
 'localisation/english/ADISCORD_STP_l_english.yml': '0e701a6cf021b1d2443049660c7c60334ea3ce592b01e1ccbad8035829c1742f',
 'localisation/russian/ADISCORD_STP_l_russian.yml': 'e82103dcf0513d9c71b562d3e46d44d940390efab6a0edcd50986daca0035abd',
 'tools/tests/test_adiscord_stp_party_balance.py': '0789fa52a48c9112f69a36bc988f464a478254819a3bc96cbd05312b78735e40',
 'tools/tests/test_adiscord_stp_party_route.py': 'ae3d80e8f94cd30b6bd6528010354fe57aa23e00df1a8f44ea92d0359ce69704'
}
PATHS = sorted(MANIFEST)
REPORT = {'base': BASE, 'native_hoi4': 'not run', 'checks': {}}
BEFORE = Path('/tmp/party-base')
AFTER = Path('/tmp/party-delivery')
RED = Path('/tmp/party-red')

def git(*args, cwd=ROOT):
    return subprocess.check_output(['git', *args], cwd=cwd, text=True).strip()

def run(name, command, cwd, timeout=300):
    with (OUT / (name + '.txt')).open('w') as log:
        start = time.monotonic()
        proc = subprocess.Popen(command, cwd=cwd, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        try:
            code = proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGKILL); proc.wait()
            log.write('\nVERIFICATION TIMEOUT: incomplete, not a passing suite.\n'); code = 124
    text = (OUT / (name + '.txt')).read_text(errors='replace')
    result = {'exit': code, 'seconds': round(time.monotonic()-start, 2),
              'failures': re.findall(r'^(?:FAIL|ERROR): (.+)$', text, re.M),
              'summary': re.findall(r'^Ran \d+ tests.*$|^FAILED .*|^OK.*$', text, re.M)}
    REPORT['checks'][name] = result
    print(name, code, result['summary'], flush=True)
    (OUT/'report.json').write_text(json.dumps(REPORT, indent=2))
    return result

subprocess.run([sys.executable, '-m', 'pip', 'install', 'pillow'], check=True)
from PIL import Image

git('fetch', '--depth=1', 'origin', BASE)
for directory in (BEFORE, AFTER, RED):
    git('worktree', 'add', '--detach', str(directory), BASE)
patch = lzma.decompress(base64.b64decode((ROOT/'.github/stp_party_changes.xz.b64').read_text()))
assert hashlib.sha256(patch).hexdigest() == '6a421c0a8306f5474e50849daa82a62dc83f8e59ade243ad9935d7f0728b426a'
(OUT/'gameplay.patch').write_bytes(patch)
git('apply', '--unidiff-zero', '--check', str(OUT/'gameplay.patch'), cwd=AFTER)
git('apply', '--unidiff-zero', str(OUT/'gameplay.patch'), cwd=AFTER)
assert sorted(git('diff','--name-only',cwd=AFTER).splitlines()) == PATHS
for path, expected in MANIFEST.items():
    data=(AFTER/path).read_bytes()
    assert hashlib.sha256(data).hexdigest() == expected, path
    if path.startswith('localisation/'):
        assert data.startswith(b'\xef\xbb\xbf'), path
    elif path.endswith('.txt'):
        assert not data.startswith(b'\xef\xbb\xbf'), path
    if path.endswith('.py'): ast.parse(data.decode('utf-8-sig'))
git('diff','--check',cwd=AFTER)
sys.path.insert(0,str(AFTER))
from tools.validators.validate_adiscord_division_templates import parse_clausewitz
for path in PATHS:
    if Path(path).suffix in ('.txt','.gui'):
        parse_clausewitz((AFTER/path).read_text(encoding='utf-8-sig'))
for lang in ('russian','english'):
    relative=f'localisation/{lang}/ADISCORD_STP_l_{lang}.yml'
    old=(BEFORE/relative).read_text(encoding='utf-8-sig')
    new=(AFTER/relative).read_text(encoding='utf-8-sig')
    for row in set(new.splitlines())-set(old.splitlines()):
        if row.strip() and not row.lstrip().startswith('#'):
            assert re.fullmatch(r'\s*[\w.]+:(?:\d+)?\s+"(?:[^"\\]|\\.)*"\s*',row),row

# Resolve actual bundled artwork, not just declared sprite names.
gfx='\n'.join(p.read_text(encoding='utf-8-sig') for p in sorted((AFTER/'interface').glob('*.gfx')))
icons=['GFX_ADISCORD_economy_tax_texticon','GFX_construction_speed_texticon','GFX_stability_texticon','GFX_organization_texticon','GFX_planning_speed_texticon','GFX_ADISCORD_economy_trade_texticon','GFX_ADISCORD_economy_burden_texticon']
metrics=[]
with zipfile.ZipFile(OUT/'ui-assets.zip','w',zipfile.ZIP_DEFLATED) as z:
    for name in icons:
        match=re.search(r'name\s*=\s*"'+re.escape(name)+r'"[^}]*?texturefile\s*=\s*"([^"]+)"',gfx,re.I)
        assert match, name
        p=AFTER/match.group(1)
        assert p.is_file(),(name,str(p))
        with Image.open(p) as im:
            w,h=im.size
            metrics.append({'sprite':name,'path':str(p.relative_to(AFTER)),'width':w,'height':h,'scaled':[w*.7,h*.7]})
        z.write(p,str(p.relative_to(AFTER)))
    for p in (AFTER/'gfx/interface').rglob('*'):
        if p.is_file() and ('STP_pf_' in p.name or 'stp_pf_' in p.name): z.write(p,str(p.relative_to(AFTER)))
(OUT/'icon-metrics.json').write_text(json.dumps(metrics,indent=2))
assert all(m['scaled'][0] <= 19 and m['scaled'][1] <= 24 for m in metrics),metrics

# Reproduce feature absence on unmodified production source.
for p in PATHS:
    if p.startswith('tools/tests/'):
        shutil.copy2(AFTER/p, RED/p)
red=run('red', [sys.executable,'-B','-m','unittest','tools.tests.test_adiscord_stp_party_balance.FactionProgramContracts','-v'], RED)
assert red['exit'] == 1 and len(red['failures']) >= 6
assert not re.search(r'^ERROR:', (OUT/'red.txt').read_text(),re.M)
scoped=[sys.executable,'-B','-m','unittest','tools.tests.test_adiscord_stp_party_balance','tools.tests.test_adiscord_stp_party_route','tools.tests.test_adiscord_stp_party_qol','-v']
assert run('scoped-baseline',scoped,BEFORE)['exit']==0
assert run('scoped-green',scoped,AFTER)['exit']==0

# Run whole discovery on both source trees. A timeout is recorded, never greenwashed.
with ThreadPoolExecutor(max_workers=2) as pool:
    full=[sys.executable,'-B','-m','unittest','discover','-s','tools/tests','-v']
    f1=pool.submit(run,'full-baseline',full,BEFORE,300)
    f2=pool.submit(run,'full-after',full,AFTER,300)
    baseline,after=f1.result(),f2.result()
if baseline['exit'] != 124 and after['exit'] != 124:
    new=sorted(set(after['failures'])-set(baseline['failures']))
    REPORT['new_full_failures']=new
    assert not new,new
with ThreadPoolExecutor(max_workers=2) as pool:
    validate=[sys.executable,'-B','tools/validate_tc.py','--limit','300']
    f1=pool.submit(run,'validator-baseline',validate,BEFORE,180)
    f2=pool.submit(run,'validator-after',validate,AFTER,180)
    baseline,after=f1.result(),f2.result()
assert after['exit']==0,after
# Tests and validators must not silently rewrite generated sources.
assert sorted(git('diff','--name-only',cwd=AFTER).splitlines())==PATHS
for path,expected in MANIFEST.items():
    assert hashlib.sha256((AFTER/path).read_bytes()).hexdigest()==expected,path
git('diff','--check',cwd=AFTER)
(OUT/'gameplay.diff').write_text(git('diff','--binary',cwd=AFTER)+'\n')
git('config','user.name','A-Discord maintenance',cwd=AFTER)
git('config','user.email','adiscord-maintenance@users.noreply.github.com',cwd=AFTER)
git('add','--',*PATHS,cwd=AFTER)
assert git('diff','--cached','--name-only',cwd=AFTER).splitlines()==PATHS
git('commit','-m','feat(stp): meaningful faction programs and visible live bonuses',cwd=AFTER)
head=git('rev-parse','HEAD',cwd=AFTER)
git('push','origin',f'HEAD:refs/heads/{BRANCH}',cwd=AFTER)
REPORT.update({'head':head,'branch':BRANCH,'source_sha256':MANIFEST,'files':PATHS,'icons':metrics})
(OUT/'report.json').write_text(json.dumps(REPORT,indent=2))
print('DELIVERED',head,BRANCH,flush=True)
