"""Run the pinned final integration with sufficient ancestry for a real merge."""
import hashlib
import subprocess
commit='b5306f915700b0e9e3e5ac3892446ba4ac60f34f'
subprocess.run(['git','fetch','--depth=1','origin',commit],check=True)
raw=subprocess.check_output(['git','show',commit+':.github/stp_party_delivery.py'])
assert hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()=='e38cc76e4a65af243735ea3e075d19c7f734cc44'
source=raw.decode('utf-8')
a="git('fetch','--depth=1','origin',ref)"
assert source.count(a)==1
source=source.replace(a,"git('fetch','--depth=32','origin',ref)")
exec(compile(source,'party_final_integration.py','exec'))
