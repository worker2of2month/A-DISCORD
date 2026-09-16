"""Apply a source-hashed audit patch only inside the disposable audit worktree."""
from __future__ import annotations
import base64
import hashlib
import json
import re
import subprocess
import sys
import zlib
from pathlib import Path

PATCH = """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"""
EXPECTED = {
    "common/scripted_effects/ADISCORD_STP_scripted_effects.txt": "fbef70e8d86bf8e80cc988d8d0ee246ec8769ce47ba5f5dc7a84ad9cc47bd609",
    "common/scripted_triggers/ADISCORD_STP_scripted_triggers.txt": "1401cffe3791da489ad7d497081994fdefaf36c8bf14a4efa5a9459706b64ee8",
    "events/ADISCORD_STP_events.txt": "e7f4701417ab88f0794e5b86c5da4e6f0517749d9c3af0aeed25f9f20a6620dd",
    "localisation/replace/ADISCORD_STP_postwar_story_l_russian.yml": None,
    "localisation/replace/ADISCORD_STP_story_l_russian.yml": None,
    "localisation/russian/ADISCORD_STP_l_russian.yml": "11f84a630bf991493c89d9c7e203bf384ed762884d0563e7c7cbd637d8658785",
    "tools/tests/test_adiscord_stp_postwar_continuation.py": "987aaf0441bdec1ccfd4887135ca391813aa9f00eb789126cebc14e2217ed9c8",
    "tools/tests/test_adiscord_stp_postwar_story.py": "67b7add9460f4adc5334901be889ea5156b84cba58676acff056276361999675",
    "tools/tests/test_adiscord_stp_startup.py": "0b29e5f474838deee4f0228b77a0cfe8b6f209ec1d62cc57e808162bbe7dfa3d",
}
BEFORE = {
    "common/scripted_effects/ADISCORD_STP_scripted_effects.txt": "9160c09f5085eb015042215291874987a3ff96125204132fb00795347e4cc53a",
    "common/scripted_triggers/ADISCORD_STP_scripted_triggers.txt": "1e59fe4cb47311c2ca72e34bbdf51421ae7a7375e9ef998059eb19180b5138cb",
    "events/ADISCORD_STP_events.txt": "dfdc9aaed60f1f79da8e9a579e6f7904df4686a93e67163a7fcb0ef1e8f1704d",
    "localisation/replace/ADISCORD_STP_postwar_story_l_russian.yml": "c75092dc507f7ae886dd46ffaa1efa0e82c010f172bd02d983f53a5f232f882e",
    "localisation/replace/ADISCORD_STP_story_l_russian.yml": "731551eb9710afdd1a3632058a2c8d3c0cdf2ab0f4e4efcef6e8608542888ea6",
    "localisation/russian/ADISCORD_STP_l_russian.yml": "203433e734a26d9281c735bd7367b24c23121c73c85a5d6261ba6e7f2327bd31",
    "tools/tests/test_adiscord_stp_postwar_continuation.py": "fda9efd037205ff96b54b8c0b3c385d561980405e3203a3f34d971d4a7ca00f6",
    "tools/tests/test_adiscord_stp_postwar_story.py": "6f240c58edf97a59202ce888c27dbdc4d38b0efa6cc836dff021fadfe141a1f5",
    "tools/tests/test_adiscord_stp_startup.py": "5e3fecb792fc9fc77a40d55d93582e6b397432d580f5ef71462d170d135ad467",
}


def main() -> None:
    root = Path(sys.argv[1]).resolve()
    if subprocess.check_output(['git', 'status', '--porcelain'], cwd=root).strip():
        raise RuntimeError('Refusing a dirty worktree')
    for name, digest in BEFORE.items():
        if hashlib.sha256((root / name).read_bytes()).hexdigest() != digest:
            raise RuntimeError('Source changed: ' + name)
    patch = zlib.decompress(base64.b64decode(PATCH))
    if hashlib.sha256(patch).hexdigest() != 'a8b35a8b311034d8ddc35c7c40a81b3ff480c80e8eeba851146b44355b089427':
        raise RuntimeError('Patch integrity check failed')
    subprocess.run(['git', 'apply', '--check', '-'], input=patch, cwd=root, check=True)
    subprocess.run(['git', 'apply', '-'], input=patch, cwd=root, check=True)
    canonical = root / 'localisation/russian/ADISCORD_STP_l_russian.yml'
    text = canonical.read_text(encoding='utf-8-sig')
    old = ' ADISCORD_STP_pc.7.d: "Передать Тих"'
    if text.count(old) != 1:
        raise RuntimeError('Unexpected successor localisation')
    text = text.replace(old, ' ADISCORD_STP_pc.7.da: "Передать Тих"')
    pattern = re.compile(r'^\s*([\w.]+):(?:\d+)?\s*"(.*)"\s*$')
    latest = {m[1]: line for line in text.splitlines() if (m := pattern.match(line))}
    seen, lines = set(), []
    for line in text.splitlines():
        match = pattern.match(line)
        if match:
            if match[1] in seen:
                continue
            seen.add(match[1])
            line = latest[match[1]]
        lines.append(line)
    index = {m[1]: i for i, line in enumerate(lines) if (m := pattern.match(line))}
    sources = [root / 'localisation/replace' / name for name in (
        'ADISCORD_STP_story_l_russian.yml', 'ADISCORD_STP_postwar_story_l_russian.yml')]
    preserved = {}
    for source in sources:
        added = []
        for line in source.read_text(encoding='utf-8-sig').splitlines():
            match = pattern.match(line)
            if not match:
                continue
            key = match[1]
            preserved[key] = match[2]
            if key in index:
                lines[index[key]] = line
            else:
                added.append(line)
        if added:
            lines += ['', ' # Послевоенные сюжетные события', ''] + added
            index = {m[1]: i for i, line in enumerate(lines) if (m := pattern.match(line))}
    canonical.write_text('\n'.join(lines) + '\n', encoding='utf-8-sig')
    values = {m[1]: m[2] for line in lines if (m := pattern.match(line))}
    if len(preserved) != 84 or any(values[key] != value for key, value in preserved.items()):
        raise RuntimeError('Narrative preservation failed')
    for source in sources:
        source.unlink()
    for name, digest in EXPECTED.items():
        path = root / name
        actual = hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None
        if actual != digest:
            raise RuntimeError('Output mismatch: ' + name)
    changed = set(subprocess.check_output(['git', 'diff', '--name-only'], cwd=root, text=True).splitlines())
    if changed != set(EXPECTED):
        raise RuntimeError('Unexpected changed paths')
    print(json.dumps({'preserved_values': len(preserved), 'sha256': EXPECTED}, indent=2))


if __name__ == '__main__':
    main()
