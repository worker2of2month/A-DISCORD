"""Audit English coverage, including mod overrides of vanilla localisation."""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import re


ENTRY = re.compile(r'^\s*([^\s:#]+):\d*\s*"((?:[^"\\]|\\.)*)"\s*(?:#.*)?$')
# Consume a texticon's frame and closing marker so adjacent English prose is
# not mistaken for another icon, and frame changes remain detectable.
TOKENS = re.compile(r'\$[^$\r\n]+\$|\[[^\]\r\n]+\]|£[A-Za-z0-9_]+(?:\|[0-9]+)?£?|@[A-Z0-9]{3}')
CYRILLIC = re.compile(r'[А-Яа-яЁё]')
# AGENTS.md forbids adding localisation for the exclusion zone.
EXCLUDED_KEYS = {'EXZ_pragmatism_party', 'EXZ_No_Authority', 'EXZ_No_Authority_desc'}


def comparable(value: str) -> str:
    return value.translate(str.maketrans({'—': '-', '–': '-', '−': '-'}))


def read_entries(root: Path, language: str) -> tuple[dict, list[str]]:
    entries = {}
    issues = []
    paths = sorted(root.rglob(f'*_l_{language}.yml'))
    # The engine's replace directory overrides normal localisation.
    paths.sort(key=lambda path: 'replace' in path.relative_to(root).parts)
    for path in paths:
        raw = path.read_bytes()
        text = raw.decode('utf-8-sig')
        if not raw.startswith(b'\xef\xbb\xbf'):
            issues.append(f'{path}: missing UTF-8 BOM')
        if not text.startswith(f'l_{language}:'):
            issues.append(f'{path}: invalid language header')
        for number, line in enumerate(text.splitlines()[1:], 2):
            if not line.strip() or line.lstrip().startswith('#'):
                continue
            match = ENTRY.fullmatch(line)
            if not match:
                issues.append(f'{path}:{number}: malformed localisation entry')
                continue
            key, value = match.groups()
            entries[key] = {'value': value, 'file': str(path), 'line': number}
    return entries, issues


def audit(root: Path, game_root: Path) -> dict:
    russian, ru_issues = read_entries(root / 'localisation', 'russian')
    english, en_issues = read_entries(root / 'localisation', 'english')
    vanilla_ru, _ = read_entries(game_root / 'localisation', 'russian')
    vanilla_en, _ = read_entries(game_root / 'localisation', 'english')
    if not vanilla_ru or not vanilla_en:
        raise ValueError('Both installed-game localisation languages are required')
    missing = {}
    issues = ru_issues + en_issues
    inherited = 0
    excluded = []
    for key, entry in russian.items():
        if 'debug' in key.lower() or 'scenario_debug' in entry['file']:
            continue
        if key in EXCLUDED_KEYS:
            excluded.append(key)
            continue
        if key not in english:
            if key in vanilla_en and comparable(vanilla_ru.get(key, {}).get('value', '')) == comparable(entry['value']):
                inherited += 1
            else:
                missing[key] = entry
            continue
        translated = english[key]
        if entry['value'].strip() and not translated['value'].strip():
            issues.append(f'{translated["file"]}:{translated["line"]}: {key}: empty English translation')
        if CYRILLIC.search(translated['value']):
            issues.append(f'{translated["file"]}:{translated["line"]}: {key}: Cyrillic in English')
        if re.search('[—–−]', translated['value']):
            issues.append(f'{translated["file"]}:{translated["line"]}: {key}: non-ASCII dash in English')
        source_tokens = Counter(TOKENS.findall(entry['value']))
        target_tokens = Counter(TOKENS.findall(translated['value']))
        # Native languages sometimes use different static aliases or formatting.
        native_pair = (
            key in vanilla_ru and key in vanilla_en
            and comparable(entry['value']).replace('\xa0', '')
            == comparable(vanilla_ru[key]['value']).replace('\xa0', '')
            and comparable(translated['value']) == comparable(vanilla_en[key]['value'])
        )
        if source_tokens != target_tokens and not native_pair:
            issues.append(f'{translated["file"]}:{translated["line"]}: {key}: localisation token mismatch')
    return {
        'russian_keys': len(russian), 'english_keys': len(english),
        'inherited_unchanged': inherited, 'missing_count': len(missing),
        'excluded_by_repository_rule': sorted(excluded),
        'missing_by_file': dict(Counter(entry['file'] for entry in missing.values())),
        'missing': missing, 'issues': issues,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument('--game-root', type=Path, required=True)
    parser.add_argument('--report', type=Path)
    parser.add_argument('--limit', type=int, default=20)
    args = parser.parse_args()
    result = audit(args.root, args.game_root)
    if args.report:
        args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'English: {result["english_keys"]}; Russian: {result["russian_keys"]}')
    print(f'Unchanged vanilla fallbacks: {result["inherited_unchanged"]}')
    print(f'Missing English overrides: {result["missing_count"]}')
    print(f'Excluded by repository rule: {", ".join(result["excluded_by_repository_rule"])}')
    for path, count in sorted(result['missing_by_file'].items(), key=lambda item: -item[1]):
        print(f'  {count:5} {path}')
    print(f'Syntax and token issues: {len(result["issues"])}')
    for issue in result['issues'][:args.limit]:
        print(f'  {issue}')
    return int(bool(result['missing_count'] or result['issues']))


if __name__ == '__main__':
    raise SystemExit(main())
