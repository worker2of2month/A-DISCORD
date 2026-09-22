"""Isolated faction verification and gameplay-only export. Never ship this helper."""
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
from PIL import Image

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
 'interface/ADISCORD_STP_regions.gfx': 'afd15172062248ac86fddc46f6c44fed1e6f2ecfd47ccfe281210b6067073f89',
 'interface/ADISCORD_STP_regions.gui': '3adfd7ee353122b9c608ea6423b3a2ec3caae20c38a1fb705732356da29750e2',
 'localisation/english/ADISCORD_STP_l_english.yml': '3dfdd90668c4dbfa84aa22e9c222ca4f684317337197852f493464b6167bedd1',
 'localisation/russian/ADISCORD_STP_l_russian.yml': 'c7c057e29c2c9eb62cff585c1079f3b095508269ae970c6696a3be5bd8bd104c',
 'tools/tests/test_adiscord_stp_party_balance.py': '45ac520813543ef20f53c163670c64b2a9c1187836339b7dcd9d1d9924a6dd2d',
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

git('fetch', '--depth=1', 'origin', BASE)
for directory in (BEFORE, AFTER, RED):
    git('worktree', 'add', '--detach', str(directory), BASE)
patch = lzma.decompress(base64.b64decode((ROOT/'.github/stp_party_changes.xz.b64').read_text()))
assert hashlib.sha256(patch).hexdigest() == '6a421c0a8306f5474e50849daa82a62dc83f8e59ade243ad9935d7f0728b426a'
(OUT/'original-gameplay.patch').write_bytes(patch)
git('apply', '--unidiff-zero', '--check', str(OUT/'original-gameplay.patch'), cwd=AFTER)
git('apply', '--unidiff-zero', str(OUT/'original-gameplay.patch'), cwd=AFTER)

# The art-only correction uses inspected symbols present in this exact checkout.
p=AFTER/'interface/ADISCORD_STP_regions.gfx'
s=p.read_text(); i=s.rfind('}')
addition='\n\tspriteType = { name = "GFX_STP_pf_stability_effect" texturefile = "gfx/interface/stability_icon.dds" legacy_lazy_load = no }\n\tspriteType = { name = "GFX_STP_pf_organization_effect" texturefile = "gfx/texticons/organization_gain_texticon.dds" legacy_lazy_load = no }\n'
p.write_text(s[:i]+addition+s[i:])
p=AFTER/'interface/ADISCORD_STP_regions.gui'
s=p.read_text().replace('GFX_stability_texticon','GFX_STP_pf_stability_effect').replace('GFX_organization_texticon','GFX_STP_pf_organization_effect')
p.write_text(s)
for language in ('russian','english'):
    p=AFTER/f'localisation/{language}/ADISCORD_STP_l_{language}.yml'
    rows=p.read_text(encoding='utf-8-sig').splitlines(keepends=True)
    rows=[r.replace('£stability_texticon','£STP_pf_stability_effect').replace('£organization_texticon','£STP_pf_organization_effect') if r.lstrip().startswith('STP_pf_') else r for r in rows]
    p.write_text(''.join(rows),encoding='utf-8-sig')
p=AFTER/'tools/tests/test_adiscord_stp_party_balance.py'
s=p.read_text()
method='''    def test_bonus_artwork_aliases_resolve_bundled_stat_symbols(self):
        gfx = read(ROOT / 'interface/ADISCORD_STP_regions.gfx')
        for sprite, path in (
                ('GFX_STP_pf_stability_effect', 'gfx/interface/stability_icon.dds'),
                ('GFX_STP_pf_organization_effect', 'gfx/texticons/organization_gain_texticon.dds')):
            self.assertIn('name = "' + sprite + '"', gfx)
            self.assertIn('texturefile = "' + path + '"', gfx)
            self.assertTrue((ROOT / path).is_file(), path)

'''
anchor='    def test_card_bonus_icons_and_values_fit_below_emblems_and_read_actual_modifier_variables(self):'
assert s.count(anchor)==1
p.write_text(s.replace(anchor,method+anchor))

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
    if Path(path).suffix in ('.txt','.gui','.gfx'):
        parse_clausewitz((AFTER/path).read_text(encoding='utf-8-sig'))
for language in ('russian','english'):
    relative=f'localisation/{language}/ADISCORD_STP_l_{language}.yml'
    old=(BEFORE/relative).read_text(encoding='utf-8-sig')
    new=(AFTER/relative).read_text(encoding='utf-8-sig')
    for row in set(new.splitlines())-set(old.splitlines()):
        if row.strip() and not row.lstrip().startswith('#'):
            assert re.fullmatch(r'\s*[\w.]+:(?:\d+)?\s+"(?:[^"\\]|\\.)*"\s*',row),row

# Resolve actual bundled artwork, not just declared sprite names.
gfx='\n'.join(p.read_text(encoding='utf-8-sig') for p in sorted((AFTER/'interface').glob('*.gfx')))
icons=['GFX_ADISCORD_economy_tax_texticon','GFX_construction_speed_texticon','GFX_STP_pf_stability_effect','GFX_STP_pf_organization_effect','GFX_planning_speed_texticon','GFX_ADISCORD_economy_trade_texticon','GFX_ADISCORD_economy_burden_texticon']
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
    for p in (AFTER/'gfx/interface/STP_regions').glob('*faction*'):
        if p.is_file(): z.write(p,str(p.relative_to(AFTER)))
(OUT/'icon-metrics.json').write_text(json.dumps(metrics,indent=2))
assert all(m['scaled'][0] <= 19 and m['scaled'][1] <= 24 for m in metrics),metrics

# Reproduce missing-feature failures on unchanged production source.
for p in PATHS:
    if p.startswith('tools/tests/'):
        shutil.copy2(AFTER/p, RED/p)
red=run('red', [sys.executable,'-B','-m','unittest','tools.tests.test_adiscord_stp_party_balance.FactionProgramContracts','-v'], RED)
assert red['exit'] == 1 and len(red['failures']) >= 6
assert not re.search(r'^ERROR:', (OUT/'red.txt').read_text(),re.M)
scoped=[sys.executable,'-B','-m','unittest','tools.tests.test_adiscord_stp_party_balance','tools.tests.test_adiscord_stp_party_route','tools.tests.test_adiscord_stp_party_qol','-v']
assert run('scoped-baseline',scoped,BEFORE)['exit']==0
assert run('scoped-green',scoped,AFTER)['exit']==0

# Whole discovery is bounded; incomplete runs are explicitly recorded, never green.
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
