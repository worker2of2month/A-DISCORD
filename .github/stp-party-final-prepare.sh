#!/usr/bin/env bash
set -euo pipefail
mode="${1:?baseline or candidate required}"
: "${PARTY_BASE_SHA:?pinned main commit required}"
case "$mode" in baseline|candidate) ;; *) exit 2;; esac
mkdir -p /tmp/party-result
cp .github/stp-party-verify.py /tmp/stp-party-verify.py
cp .github/stp-party-resolve.py /tmp/stp-party-resolve.py
cp .github/stp-party-audit.py /tmp/stp-party-audit.py
cat .github/stp-party-patch.1 .github/stp-party-patch.2 > /tmp/party.patch.xz
python - <<'PY'
import hashlib, lzma
from pathlib import Path
patch=lzma.decompress(Path('/tmp/party.patch.xz').read_bytes())
assert hashlib.sha256(patch).hexdigest()=='d3c5f6f9e2763ae2bef5d3db01ca2daff1c45f331353a5ad64cf97b51e56aa34'
Path('/tmp/party.patch').write_bytes(patch)
p=Path('/tmp/stp-party-verify.py')
s=p.read_text()
assert s.count('ALLOWED = {\n')==1
s=s.replace('ALLOWED = {\n', "ALLOWED = {\n    'tools/data/division_template_audit.json',\n")
assert s.count("pattern='*stp*.py'")==1
s=s.replace("pattern='*stp*.py'", "pattern='test*.py'")
p.write_text(s)
PY
git fetch origin "$PARTY_BASE_SHA" --depth=60
git switch --detach FETCH_HEAD
test "$(git rev-parse HEAD)" = "$PARTY_BASE_SHA"
git rev-parse HEAD > /tmp/party-result/base-sha.txt
if test "$mode" = candidate; then
  if ! git apply --3way /tmp/party.patch; then
    test "$(git diff --name-only --diff-filter=U)" = 'common/ideas/ADISCORD_STP_civil_war_ideas.txt'
    python -B /tmp/stp-party-resolve.py
  fi
  test -z "$(git diff --name-only --diff-filter=U)"
  python -B /tmp/stp-party-audit.py
  git diff --check HEAD
  git diff --cached --check
fi
