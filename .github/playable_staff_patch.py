"""Temporary test-first runner. Never ship this helper or its workflow."""
from pathlib import Path
import subprocess
import sys
import zipfile

ROOT=Path.cwd()
sys.path.insert(0,str(ROOT))
from tools.tests.test_adiscord_stp_preparation import parse_clausewitz, block, scalar, walk
out=Path('/tmp/staff-evidence');out.mkdir(exist_ok=True)
def read(p):return (ROOT/p).read_text(encoding='utf-8-sig')
with zipfile.ZipFile(out/'review-sources.zip','w',zipfile.ZIP_DEFLATED) as z:
    for prefix in ('common','history','interface','localisation','tools','docs/development'):
        for p in (ROOT/prefix).rglob('*'):
            if p.is_file() and p.suffix in ('.txt','.py','.json','.yml','.gfx','.gui','.md'):
                z.write(p,p.relative_to(ROOT))
    z.write(ROOT/'AGENTS.md','AGENTS.md')
print('AUDIT REMAINING EDGES',flush=True)
p='common/scripted_effects/ADISCORD_STP_scripted_effects.txt'
source=read(p);rows=parse_clausewitz(source)
for e in rows:
    if isinstance(e.value,list) and (any(x.key=='remove_country_leader_role' and scalar(x.value,'ideology') in ('national_legitimism','steland_military_directory') for x in walk(e.value)) or any(x.key=='set_country_flag' and x.value=='STP_cw_postwar' for x in walk(e.value))):
        print('LIFECYCLE',e.key,e.line,flush=True)
for p in ('common/country_leader/ADISCORD_minister_traits.txt','common/units/equipment/ADISCORD_air_equipment.txt','common/units/equipment/ADISCORD_armor_equipment.txt'):
    entries=parse_clausewitz(read(p));print('ROOTS',p,[x.key for x in entries],flush=True)
    if 'equipment' in p:
        for x in block(entries,'equipments'):
            if isinstance(x.value,list) and any(v.key=='is_archetype' and v.value=='yes' for v in x.value):print('ARCHETYPE',x.key,flush=True)
print('EXISTING TEST MODULES', [p.name for p in (ROOT/'tools/tests').glob('*') if any(k in p.name for k in ('minister','character','mio','ideolog'))],flush=True)
proc=subprocess.run([sys.executable,'-B','-m','unittest','tools.tests.test_adiscord_playable_staff','-v'],text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
(out/'red.txt').write_text(proc.stdout)
print(proc.stdout,flush=True)
assert proc.returncode!=0,'Missing feature tests unexpectedly passed'
assert 'FAILED (failures=6)' in proc.stdout,'RED must be the six expected missing-feature failures, without errors'
print('RED_CONFIRMED: six missing-feature failures. No production changes.',flush=True)
