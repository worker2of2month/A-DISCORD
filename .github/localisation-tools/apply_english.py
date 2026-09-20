"""Apply the reviewed English catalogue additions in this temporary branch."""
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.validators.validate_adiscord_english_localisation import (
    CYRILLIC, ENTRY, EXCLUDED_KEYS, TOKENS, read_entries,
)


def main():
    source_hash = hashlib.sha256()
    for path in sorted((ROOT / 'localisation').rglob('*_l_russian.yml')):
        source_hash.update(str(path.relative_to(ROOT)).encode() + b'\0' + path.read_bytes() + b'\0')
    if source_hash.hexdigest() != '0f44e68592218736482170e6ecf8a5b5cc49c9b22553baf62394fae98f1a8201':
        raise RuntimeError('Russian catalogues changed: review the new source before applying translations')
    russian, ru_issues = read_entries(ROOT / 'localisation', 'russian')
    english, en_issues = read_entries(ROOT / 'localisation', 'english')
    errors = ru_issues + en_issues
    translated = {}
    for path in sorted((ROOT / '.github/localisation-batches').rglob('*.tsv')):
        for number, line in enumerate(path.read_text(encoding='utf-8').splitlines(), 1):
            if not line.strip():
                continue
            if '\t' not in line:
                errors.append(f'{path}:{number}: missing tab')
                continue
            key, value = line.split('\t', 1)
            key = key.strip()
            if key in translated:
                errors.append(f'{path}:{number}: duplicate translated key {key}')
            translated[key] = value
    for key, entry in russian.items():
        if key not in english and key not in translated and key not in EXCLUDED_KEYS:
            if not CYRILLIC.search(entry['value']):
                translated[key] = entry['value']
    missing = sorted(set(russian) - set(english) - set(translated) - EXCLUDED_KEYS)
    errors.extend(f'Missing translation: {key}' for key in missing)
    pending = defaultdict(list)
    token_errors = []
    for key, value in translated.items():
        if key not in russian or key in EXCLUDED_KEYS:
            errors.append(f'Unexpected translation key: {key}')
            continue
        if key in english:
            if english[key]['value'] != value:
                errors.append(f'Would overwrite existing English translation: {key}')
            continue
        source = russian[key]
        if not ENTRY.fullmatch(f' {key}: "{value}"'):
            errors.append(f'Malformed English value: {key}')
        if CYRILLIC.search(value) or (source['value'].strip() and not value.strip()):
            errors.append(f'Untranslated English value: {key}')
        if re.search('[—–−]', value):
            errors.append(f'Non-ASCII dash: {key}')
        old_tokens, new_tokens = Counter(TOKENS.findall(source['value'])), Counter(TOKENS.findall(value))
        if old_tokens != new_tokens:
            token_errors.append({'key': key, 'source': source['value'], 'english': value,
                                 'lost': list((old_tokens - new_tokens).elements()),
                                 'added': list((new_tokens - old_tokens).elements())})
        path = Path(source['file']).relative_to(ROOT)
        target = ROOT / Path(*('english' if part == 'russian' else part for part in path.parts))
        target = target.with_name(target.name.replace('_l_russian.yml', '_l_english.yml'))
        pending[target].append((source['line'], key, value))
    report = {'source_sha256': source_hash.hexdigest(), 'russian_keys': len(russian),
              'english_before': len(english), 'additions': sum(map(len, pending.values())),
              'by_file': {str(p.relative_to(ROOT)): len(v) for p, v in pending.items()},
              'errors': errors, 'token_errors': token_errors,
              'excluded': sorted(EXCLUDED_KEYS)}
    Path('/tmp/translation-report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if errors:
        return 1
    for path, entries in sorted(pending.items()):
        existing = path.read_bytes() if path.exists() else b'\xef\xbb\xbfl_english:\n'
        if not existing.endswith(b'\n'):
            existing += b'\n'
        lines = [f' {key}: "{value}"' for _, key, value in sorted(entries)]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(existing + ('\n' + '\n'.join(lines) + '\n').encode('utf-8'))
    return int(bool(token_errors))


if __name__ == '__main__':
    raise SystemExit(main())
