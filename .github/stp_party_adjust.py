from pathlib import Path
import re
import subprocess


def change(path, transform):
    p = Path(path)
    raw = p.read_bytes()
    bom = raw.startswith(b'\xef\xbb\xbf')
    before = raw.decode('utf-8-sig')
    after = transform(before)
    assert before != after, path
    p.write_bytes((b'\xef\xbb\xbf' if bom else b'') + after.encode('utf-8'))


def once(text, old, new):
    assert text.count(old) == 1, (old, text.count(old))
    return text.replace(old, new, 1)


def migrate_survival(text):
    old = """        elections = {e.key for e in categories['STP_elections_in_the_party']}
        self.assertTrue({'STP_ps_build_radio', 'STP_ps_build_hq', 'STP_ps_prepare_evacuation',
                         'STP_ps_fund_nod', 'STP_ps_arm_nod', 'STP_ps_val_intelligence', 'STP_ps_val_intercept'} <= elections)
"""
    new = """        elections = {e.key for e in categories['STP_elections_in_the_party']}
        domestic = {'STP_ps_build_radio', 'STP_ps_build_hq', 'STP_ps_prepare_evacuation'}
        foreign = {'STP_ps_fund_nod', 'STP_ps_arm_nod', 'STP_ps_val_intelligence', 'STP_ps_val_intercept'}
        self.assertTrue(domestic <= {e.key for e in categories['STP_party_factions']})
        self.assertTrue(foreign <= {e.key for e in categories['STP_cw_external_intervention']})
        self.assertFalse((domestic | foreign) & elections)
"""
    text = once(text, old, new)
    return once(text, 'def test_preparation_uses_existing_election_category_without_extra_tabs(self):',
                'def test_preparation_reuses_existing_categories_without_extra_tabs(self):')


change('tools/tests/test_adiscord_stp_party_survival.py', migrate_survival)
change('tools/tests/test_adiscord_stp_party_route.py', lambda text: once(text,
    '        decisions = one(categories, "STP_party_factions")\n        self.assertEqual(len(decisions), 7)',
    '        decisions = [e for e in one(categories, "STP_party_factions")\n                     if e.key.startswith("STP_pf_negotiate_")]\n        self.assertEqual(len(decisions), 7)'))

briefings = {
    'russian': '§YЗадача партии§!: сохранить аппарат и ключевые округа до раскола.\nСледите за объявленными операциями подполья: обыски без цели помогают Шабрату. При верности аппарата 70+ подготовка подполья замедляется, ниже 25 — ускоряется. Победа на выборах не отменяет гражданскую войну.\nПроекты правительства — в разделе §Y«Аппарат и подготовка»§!; Нодрул и поставки Кефрейта — во §Y«Внешних операциях»§!.',
    'english': '§YParty objective§!: preserve the apparatus and key districts before the split.\nWatch announced underground operations: searches without a target help Shabrat. At 70+ apparatus loyalty, underground preparation slows down; below 25, it speeds up. An election victory does not prevent civil war.\nGovernment projects are under §YApparatus and Preparation§!; Nodrul and Kefreyt shipments are under §YForeign Operations§!.'
}
for lang, briefing in briefings.items():
    path = 'localisation/' + lang + '/ADISCORD_STP_l_' + lang + '.yml'
    def update_localisation(text, briefing=briefing):
        lines = text.splitlines()
        count = 0
        for i, line in enumerate(lines):
            if line.startswith(' STP_ps_'):
                lines[i] = re.sub(r'^( STP_ps_\w+):0 ', r'\1: ', line)
            if line.startswith(' STP_PARTY_ELECTION_BRIEFING:'):
                lines[i] = ' STP_PARTY_ELECTION_BRIEFING: "' + briefing.replace('\n', '\\n') + '"'
                count += 1
        assert count == 1
        return '\n'.join(lines) + '\n'
    change(path, update_localisation)

# Remove only trailing spaces newly introduced on changed lines.
for path in subprocess.check_output(['git', 'diff', '--name-only'], text=True).splitlines():
    p = Path(path)
    raw = p.read_bytes()
    bom = raw.startswith(b'\xef\xbb\xbf')
    current = raw.decode('utf-8-sig').splitlines(keepends=True)
    diff = subprocess.check_output(['git', 'diff', '--unified=0', '--', path], text=True)
    additions = []
    for line in diff.splitlines():
        match = re.match(r'^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@', line)
        if match:
            start = int(match.group(1)) - 1
            count = int(match.group(2)) if match.group(2) is not None else 1
            additions.extend(range(start, start + count))
    for i in additions:
        if 0 <= i < len(current):
            current[i] = current[i].rstrip('\r\n').rstrip(' \t') + '\n'
    result = ''.join(current).rstrip('\r\n') + '\n'
    p.write_bytes((b'\xef\xbb\xbf' if bom else b'') + result.encode('utf-8'))
print('CATEGORY_CONTRACTS_MIGRATED; NATIVE_LOCALISATION_FORMAT_PRESERVED')
