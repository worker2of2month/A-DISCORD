"""Pinned verification runner with an explicit missing-receipt assertion."""
import hashlib
import subprocess

commit='44efdb0805f8a667fd8854c2182685c5b5a8d6cc'
subprocess.run(['git','fetch','--depth=1','origin',commit],check=True)
raw=subprocess.check_output(['git','show',commit+':.github/stp_party_delivery.py'])
assert hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()=='d24e6f7269e6b533a7a7611f4c712c69504a23d6'
source=raw.decode('utf-8')
source=source.replace('45ac520813543ef20f53c163670c64b2a9c1187836339b7dcd9d1d9924a6dd2d','e012403d47908a39543648c691d71537ffe8f7e0eee40b6b8c0ba6a39487b655')
needle='p.write_text(s.replace(anchor,method+anchor))'
replacement='''s=s.replace(anchor,method+anchor)
line="            self.assertEqual(calls[-1], 'STP_pf_apply_focus_program', fid)"
assert s.count(line)==1
s=s.replace(line,"            self.assertTrue(calls, fid)\\n"+line)
p.write_text(s)'''
assert source.count(needle)==1
source=source.replace(needle,replacement)
exec(compile(source,'pinned_party_delivery.py','exec'))
