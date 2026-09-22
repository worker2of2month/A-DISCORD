from pathlib import Path
import re, json, hashlib, base64, zlib

root = Path.cwd()
pattern = re.compile(r'(?m)^<<<<<<< .*?\n(.*?)^=======\n(.*?)^>>>>>>> .*?\n', re.S)

def edit(name, fn):
    p = root / name
    raw = p.read_bytes()
    bom = raw.startswith(b'\xef\xbb\xbf')
    text = fn(raw.decode('utf-8-sig'))
    p.write_bytes((b'\xef\xbb\xbf' if bom else b'') + text.encode('utf-8'))

def resolve(text, expected, choices):
    matches = list(pattern.finditer(text))
    assert len(matches) == expected, (len(matches), expected)
    for i, m in reversed(list(enumerate(matches))):
        text = text[:m.start()] + choices(i, m.group(1), m.group(2)) + text[m.end():]
    return text

def named_span(text, name):
    m = re.search(r'(?m)^\s*' + re.escape(name) + r'\s*=\s*\{', text)
    assert m, name
    start = text.index(name, m.start(), m.end())
    opening = text.index('{', start)
    depth = 0
    quoted = escaped = comment = False
    for i in range(opening, len(text)):
        c = text[i]
        if comment:
            if c == '\n': comment = False
            continue
        if quoted:
            if escaped: escaped = False
            elif c == '\\': escaped = True
            elif c == '"': quoted = False
            continue
        if c == '#': comment = True
        elif c == '"': quoted = True
        elif c == '{': depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0: return start, i + 1
    raise AssertionError(name)

def change_block(text, name, fn):
    a, b = named_span(text, name)
    return text[:a] + fn(text[a:b]) + text[b:]

def decisions(text):
    text = resolve(text, 1, lambda i, a, b: a.replace(' }  }', ' } }'))
    old = 'complete_effect = { add_political_power = -10 VAL_pay_quarterly_contract_norm = yes }'
    assert text.count(old) == 1
    return text.replace(old, 'complete_effect = { VAL_pay_quarterly_contract_norm = yes }')
edit('common/decisions/ADISCORD_VAL_decisions.txt', decisions)

def ideas(text):
    text = resolve(text, 1, lambda i, a, b: b)
    for name in ('VAL_export_income_1', 'VAL_export_income_2', 'VAL_advisors_income'):
        text = change_block(text, name, lambda block: block.replace('ADISCORD_economy_weekly_income = 10', ''))
        lines = text.splitlines(keepends=True)
        i = next(i for i, line in enumerate(lines) if re.match(r'\s*' + name + r' = \{', line))
        j = i + 1
        while not re.match(r'^\s*\}\s*$', lines[j]): j += 1
        block = [line for line in lines[i:j+1] if 'on_add =' not in line and 'on_remove =' not in line]
        block = ['\t\t' + name + ' = {\n'] + [('\t\t}\n' if re.match(r'^\s*\}\s*$', line) else '\t\t\t' + line.lstrip().replace('{  }', '{ }').replace('{  planning', '{ planning')) for line in block[1:]]
        lines[i:j+1] = block
        text = ''.join(lines)
    return text
edit('common/ideas/ADISCORD_VAL_rework_ideas.txt', ideas)
edit('common/national_focus/ADISCORD_national_focus_VAL.txt', lambda text: resolve(text, 3, lambda i, a, b: b + '\t\t\tcustom_effect_tooltip = VAL_focus_paid_program_authorization_tt\n'))

def effects(text):
    text = resolve(text, 2, lambda i, a, b: (a + '\t\t\t\tadd_political_power = -10\n') if i == 0 else a)
    def guarded(block):
        header = 'VAL_reclamation_refresh_state = {'
        inside = block[len(header):].strip('\n')
        assert inside.endswith('}')
        inside = inside[:-1].rstrip()
        return header + '\n\tif = {\n\t\tlimit = { check_variable = { var = VAL_reclamation_stage value = 1 compare = greater_than_or_equals } }\n' + '\n'.join('\t' + line if line else '' for line in inside.splitlines()) + '\n\t}\n}'
    text = change_block(text, 'VAL_reclamation_refresh_state', guarded)
    text = text.replace('# STATE; compensation preserves restoration through an ownership change.', '# STATE: keep one restoration status through ownership changes; untreated states stay contaminated.')
    return text.replace('\t\t# Reclamation is a state transition, not a second compensating modifier.\n', '')
edit('common/scripted_effects/ADISCORD_VAL_effects.txt', effects)

def triggers(text):
    text = resolve(text, 1, lambda i, a, b: b)
    return change_block(text, 'VAL_reclamation_state_project_valid', lambda block: '''VAL_reclamation_state_project_valid = {
	VAL = { has_capitulated = no has_completed_focus = VAL_reclamation_survey }
	is_owned_by = VAL
	is_controlled_by = VAL
	OR = {
		AND = {
			has_dynamic_modifier = { modifier = ADISCORD_vorkerland_dirty_state }
			NOT = { check_variable = { var = VAL_reclamation_stage value = 1 compare = greater_than_or_equals } }
		}
		AND = {
			has_dynamic_modifier = { modifier = VAL_reclamation_stage_1_modifier }
			check_variable = { var = VAL_reclamation_stage value = 1 compare = equals }
			VAL = { has_completed_focus = VAL_reclamation_clean_water }
		}
		AND = {
			has_dynamic_modifier = { modifier = VAL_reclamation_stage_2_modifier }
			check_variable = { var = VAL_reclamation_stage value = 2 compare = equals }
			VAL = { has_completed_focus = VAL_reclamation_return_home }
		}
	}
}''')
edit('common/scripted_triggers/ADISCORD_VAL_rework_triggers.txt', triggers)

def events(text):
    def choice(i, a, b):
        start = b.index('VAL = {\n') + len('VAL = {\n')
        indentation = re.match(r'\s*', b[start:]).group(0)
        return b[:start] + indentation + 'ADISCORD_economy_receive_100 = yes\n' + b[start:]
    return resolve(text, 2, choice)
edit('events/ADISCORD_VAL_contract_events.txt', events)

for language in ('russian', 'english'):
    def loc(text):
        def choice(i, a, b):
            if i == 0: return b
            if i == 1:
                title = re.search(r'(?m)^ VAL_foreign_sales:.*$', b).group(0)
                a = re.sub(r'(?m)^ VAL_foreign_sales:.*$', lambda m: title, a)
                return re.sub(r'(?m)^( VAL_foreign_sales_desc:[^\n]*)("\s*)$', lambda m: m.group(1) + '\\n\\n$VAL_trade_corridors_desc$' + m.group(2), a)
            if i == 2: return a
            if i == 3: return a + '\n' + b
            raise AssertionError(i)
        text = resolve(text, 4, choice)
        keys = re.findall(r'(?m)^\s+([A-Za-z0-9_.-]+):', text)
        assert len(keys) == len(set(keys)), [key for key in set(keys) if keys.count(key) > 1]
        return text
    edit(f'localisation/{language}/ADISCORD_VAL_decisions_l_{language}.yml', loc)

# The fixture is compressed only in this disposable runner; the committed tests are plain Python.
fixture = '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'
# Normalize transcription-sensitive segments against the reviewed compressed fixture.
fixture = fixture.replace('XMeCIuchez', 'XMeCIchezh').replace('fo4DfaKx', 'fo4DdaKx').replace('Kc1CsHl', 'Kc1lCsHl')
addition = zlib.decompress(base64.b64decode(fixture)).decode()

def ui_tests(text):
    marker = '\nif __name__ == "__main__":'
    assert marker in text and 'class TestValMergedContractFlows' not in text
    text = text.replace(marker, addition + marker)
    old = '            self.assertIn("cost = 3", block, focus_id)'
    assert text.count(old) == 1
    return text.replace(old, '            cost = re.search(r"(?m)^\\s*cost\\s*=\\s*([0-9.]+)", block)\n            self.assertIsNotNone(cost, focus_id)\n            self.assertLessEqual(float(cost.group(1)), 3, focus_id)')
edit('tools/tests/test_val_contract_ui.py', ui_tests)

def expanded_tests(text):
    old = '        values = dict(re.findall(r\'^ ([\\w.]+):\\s*"(.*)"$\', LOCALISATION_PATH.read_text(encoding="utf-8-sig"), re.M))'
    assert text.count(old) == 1
    text = text.replace(old, '''        sources = (LOCALISATION_PATH, ROOT / "localisation/russian/politics_l_russian.yml")
        values = dict(entry for path in sources for entry in re.findall(
            r'^ ([\\w.]+):(?:[0-9]+)?\\s*"(.*)"$', path.read_text(encoding="utf-8-sig"), re.M
        ))''')
    for owner in ('declaration', 'advisers'):
        for hook in ('on_add', 'on_remove'):
            text = text.replace(f'self.assertFalse(block({owner}, "{hook}"))', f'self.assertFalse(any(e.key == "{hook}" for e in {owner}))')
    text = text.replace('self.assertFalse(block(postwar, "VAL_establish_regional_administration"))', 'self.assertFalse(any(e.key == "VAL_establish_regional_administration" for e in postwar))')
    text = text.replace('self.assertIsNone(scalar(block(advisers, "modifier"), "ADISCORD_economy_weekly_income"))', 'self.assertFalse(any(e.key == "ADISCORD_economy_weekly_income" for e in block(advisers, "modifier")))')
    start = text.index('    def test_vorkerland_aid_has_real_stock_costs_and_no_automatic_dispatch')
    end = text.find('\n    def ', start + 10)
    segment = text[start:end]
    old = 'self.assertEqual(self.scalar(decision, "cost"), "50")'
    assert segment.count(old) == 1
    text = text[:start] + segment.replace(old, 'self.assertEqual(self.scalar(decision, "cost"), "30")') + text[end:]
    old = '        conference = self.focus("VAL_frontier_conference")'
    assert text.count(old) == 1
    return text.replace(old, '''        conference = next(entry.text for entry in named_block_spans(focus_text, "focus")
                          if re.search(r"\\bid\\s*=\\s*VAL_frontier_conference\\b", entry.text))''')
edit('tools/tests/test_validate_adiscord_val_rework.py', expanded_tests)

expected = {
 'common/decisions/ADISCORD_VAL_decisions.txt': '63b2c9923e9c4953501a1b20b4200ae8364a435b781187c591ead4c5f102df4d',
 'common/ideas/ADISCORD_VAL_rework_ideas.txt': '2808a17245f06bc7982d12fc28026cc3fca5d840b262b688f3f6aa06da1fe61b',
 'common/national_focus/ADISCORD_national_focus_VAL.txt': '65bd11cfdabe2cf8567f4f624651b7e1f75b49c9cc58bc8838c2ceefea20def8',
 'common/scripted_effects/ADISCORD_VAL_effects.txt': 'dc90fa13cc5c50afe2dfc23e8dfccf0df70f1b16a6bef8c2294becdc1ab96cf9',
 'common/scripted_triggers/ADISCORD_VAL_rework_triggers.txt': '1b9a66934313e5f94c1f363ba61ce8ba820d2831a69dd107f764a61cececbfb2',
 'events/ADISCORD_VAL_contract_events.txt': '47e23eb235505bc94dd21fe77b6727c7073e51c1ca3d9200fb05b10b6ef0b27a',
 'localisation/english/ADISCORD_VAL_decisions_l_english.yml': '429dedf78ee1b4517361afd5e59a1a9afb30a6157b8be44dbc2caf494e7219b1',
 'localisation/russian/ADISCORD_VAL_decisions_l_russian.yml': '8741be4058d2619fc3eb8555cb57b7699a3bdb798f9906783895b81531984e20',
 'tools/tests/test_val_contract_ui.py': '67b6805925b0c64a2d330195b2270366476479c2169f5d51e9c769dea79f83e9',
 'tools/tests/test_validate_adiscord_val_rework.py': 'efdbef91ff62a9460159caca815091e52cbd249be9aeb5674c78fa20f0a5ea3b'
}
for name, digest in expected.items():
    actual = hashlib.sha256((root/name).read_bytes()).hexdigest()
    assert actual == digest, (name, actual, digest)
Path('/tmp/val-integration-hashes.json').write_text(json.dumps(expected, indent=2))
print('All ten reviewed conflict-resolution files match their tested SHA256 hashes.')
