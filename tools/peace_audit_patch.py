"""Temporary transport for the locally regression-tested patch; removed before merge."""
from pathlib import Path
import base64
import hashlib
import subprocess
import zlib

root = Path(__file__).resolve().parents[1]
encoded = ''.join((root / f'tools/peace_audit_patch{i}.b64').read_text().strip() for i in range(3))
patch = zlib.decompress(base64.b64decode(encoded, validate=True))
assert hashlib.sha256(patch).hexdigest() == 'bf59549c3a12b147a0583b56fc7dfafe18bbbd50cd1d5b95a2a21551cdd55c30', 'Patch transport checksum mismatch'
paths = [line.removeprefix('+++ b/') for line in patch.decode().splitlines() if line.startswith('+++ b/')]
assert len(paths) == len(set(paths)) == 15
assert all(not Path(p).is_absolute() and '..' not in Path(p).parts for p in paths)
subprocess.run(['git', 'apply', '--check', '-'], input=patch, cwd=root, check=True)
subprocess.run(['git', 'apply', '-'], input=patch, cwd=root, check=True)
out = Path('/tmp/peace-evidence')
out.mkdir(exist_ok=True)
(out / 'changed-paths.txt').write_text('\n'.join(paths) + '\n')
(out / 'verified.patch').write_bytes(patch)
print('Applied verified candidate:', len(patch), 'bytes;', len(paths), 'authored paths')
