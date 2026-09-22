"""Read-only verification of PR78; the duplicate roster payload is not applied."""
from pathlib import Path
import hashlib
import json
import subprocess
import sys
import unittest
import zipfile

MERGED = '0b3667dc6c2c3b93aa3adf215e6d5c4a14844b3c'
OUT = Path('/tmp/roster-evidence')
OUT.mkdir(exist_ok=True)
subprocess.run(['git','fetch','--depth=1','origin',MERGED],check=True)
subprocess.run(['git','switch','--detach',MERGED],check=True)
sys.path.insert(0,str(Path.cwd()))
with (OUT/'main_staff_tests.log').open('w') as out:
    suite = unittest.defaultTestLoader.loadTestsFromName('tools.tests.test_adiscord_playable_staff')
    result = unittest.TextTestRunner(stream=out,verbosity=2).run(suite)
manifest = {'verified_main':MERGED,'merged_pr':78,'tests_run':result.testsRun,
            'failures':[t.id() for t,_ in result.failures], 'errors':[t.id() for t,_ in result.errors],
            'skipped':[(t.id(),why) for t,why in result.skipped],
            'native_hoi4_run':False,'duplicate_payload_applied':False,'repository_writes':False}
from tools.tests.test_adiscord_stp_preparation import parse_clausewitz,block,scalar,walk
mio_path = Path('common/military_industrial_organization/organizations/ADISCORD_playable_organizations.txt')
manifest['mio_ids'] = [e.key for e in parse_clausewitz(mio_path.read_text(encoding='utf-8-sig'))]
assert len(manifest['mio_ids']) == 6
with zipfile.ZipFile(OUT/'merged-source.zip','w',zipfile.ZIP_DEFLATED) as z:
    for folder in ('common','history','events','interface','localisation','tools','docs'):
        for p in Path(folder).rglob('*'):
            if p.is_file() and p.suffix in ('.txt','.py','.yml','.yaml','.json','.gfx','.gui','.md','.mod','.csv'):
                z.write(p)
    for name in ('AGENTS.md','descriptor.mod'):
        if Path(name).exists(): z.write(name)
(OUT/'manifest.json').write_text(json.dumps(manifest,indent=2))
print(json.dumps(manifest),flush=True)
assert result.wasSuccessful(), 'Inspect main_staff_tests.log; no gameplay files were changed'
