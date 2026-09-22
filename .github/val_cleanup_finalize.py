from pathlib import Path
import ast
import concurrent.futures
import hashlib
import json
import os
import re
import subprocess
import sys

ROOT = Path.cwd()
OUT = Path('/tmp/val-cleanup-review')
OUT.mkdir(exist_ok=True)
BASE = 'e41f07d2417b09aec7461b586b33ecc1467f3800'
reports = {}


def run(name, command, timeout=180):
    with (OUT / (name + '.log')).open('w') as log:
        try:
            code = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, timeout=timeout).returncode
        except subprocess.TimeoutExpired:
            log.write('\nTIMEOUT after ' + str(timeout) + ' seconds\n')
            code = 124
    text = (OUT / (name + '.log')).read_text(errors='replace')
    result = {'returncode': code, 'failures': re.findall(r'^(?:FAIL|ERROR): (.+)$', text, re.M),
              'observed_failures': [line for line in text.splitlines() if re.search(r'\.\.\. (FAIL|ERROR)$', line)],
              'tail': text.splitlines()[-6:]}
    reports[name] = result
    (OUT / 'verification.json').write_text(json.dumps(reports, indent=2))
    print(name, json.dumps(result), flush=True)
    return result


def block(text, name):
    match = re.search(r'(?m)^\s*' + re.escape(name) + r'\s*=\s*\{', text)
    assert match, name
    depth, quoted, escaped = 0, False, False
    for index in range(text.index('{', match.start(), match.end()), len(text)):
        char = text[index]
        if quoted:
            if escaped:
                escaped = False
            elif char == '\\':
                escaped = True
            elif char == '"':
                quoted = False
        elif char == '"':
            quoted = True
        elif char == '{':
            depth += 1
        elif char == '}':
            depth -= 1
            if depth == 0:
                return text[match.start():index + 1]
    raise AssertionError(name)


def one(text, old, new):
    assert text.count(old) == 1, (old[:100], text.count(old))
    return text.replace(old, new)


def replace_method(text, class_name, method_name, replacement):
    cls = next(n for n in ast.parse(text).body if isinstance(n, ast.ClassDef) and n.name == class_name)
    node = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == method_name)
    lines = text.splitlines(keepends=True)
    return ''.join(lines[:node.lineno - 1]) + replacement.rstrip() + '\n' + ''.join(lines[node.end_lineno:])


broad = [sys.executable, '-B', '-m', 'unittest', 'tools.tests.test_val_contract_ui',
         'tools.tests.test_val_export_market', 'tools.tests.test_validate_adiscord_val_rework',
         'tools.tests.test_adiscord_economy_rebalance', '-v']
assert run('baseline-broad', broad)['returncode'] != 124
path = ROOT / 'tools/tests/test_val_contract_ui.py'
text = path.read_text()
old = 'self.assertEqual(reward.count(f"unlock_decision_tooltip = {decision_id}"), 1)'
new = '''from tools.validators.validate_adiscord_division_templates import parse_clausewitz
                rewards = parse_clausewitz(reward)[0].value
                unlocked = [entry.value if isinstance(entry.value, str)
                            else next(child.value for child in entry.value if child.key == "decision")
                            for entry in rewards if entry.key == "unlock_decision_tooltip"]
                self.assertEqual(unlocked.count(decision_id), 1)'''
text = one(text, old, new)
method = '''    def test_paid_reclamation_matches_the_actual_starting_contamination(self):
        from tools.validators.validate_adiscord_division_templates import parse_clausewitz
        from tools.tests.test_adiscord_stp_preparation import matches_conditions
        text = read("common/scripted_triggers/ADISCORD_VAL_rework_triggers.txt")
        gate = parse_clausewitz(named_block(text, "VAL_reclamation_complete"))[0].value
        self.assertEqual({e.key for e in gate if e.key.isdigit()}, {str(n) for n in self.states})
        pollution = named_block(read("common/scripted_effects/ADISCORD_vorkerland_effects.txt"),
                                "ADISCORD_vorkerland_apply_dirty_modifiers")
        initially_dirty = {int(e.key) for e in parse_clausewitz(pollution)[0].value if e.key.isdigit()} & set(self.states)
        self.assertEqual(initially_dirty, {24, 57}, "Review the paid objective when starting contamination changes")
        complete = {("VAL", "has_completed_focus", "VAL_reclamation_return_home"): True}
        for state in self.states:
            complete.update({
                (str(state), "variable", "VAL_reclamation_stage"): 3 if state in initially_dirty else 0,
                (str(state), "is_owned_by", "VAL"): True,
                (str(state), "is_controlled_by", "VAL"): True,
            })
        self.assertTrue(matches_conditions(gate, complete, "VAL"), "Clean home regions have no paid reclamation decision")
        self.assertFalse(matches_conditions(gate, {}, "VAL"), "No completion before paid reclamation")
        self.assertFalse(matches_conditions(gate, complete | {("VAL", "has_variable", "VAL_reclamation_deposit"): True}, "VAL"))
        for state in self.states:
            for stage in (0, 1, 2, 3, 4):
                expected = stage >= 3 or (stage == 0 and state not in initially_dirty)
                with self.subTest(state=state, stage=stage):
                    self.assertEqual(matches_conditions(gate, complete | {(str(state), "variable", "VAL_reclamation_stage"): stage}, "VAL"), expected)
            for key in ("is_owned_by", "is_controlled_by"):
                self.assertFalse(matches_conditions(gate, complete | {(str(state), key, "VAL"): False}, "VAL"))
            for modifier in ("ADISCORD_vorkerland_dirty_state", "VAL_reclamation_stage_1_modifier", "VAL_reclamation_stage_2_modifier"):
                self.assertFalse(matches_conditions(gate, complete | {(str(state), "has_dynamic_modifier", modifier): True}, "VAL"))
        self.assertTrue(matches_conditions(gate, complete | {("999", "variable", "VAL_reclamation_stage"): 0}, "VAL"))
'''
text = replace_method(text, 'TestValReclamationCompletion', 'test_all_seven_home_regions_must_finish_the_paid_three_stage_programme', method)
extra = '''

class TestValReclamationFollowThrough(unittest.TestCase):
    def test_paid_deadline_matches_the_native_decision_duration(self):
        effects = read("common/scripted_effects/ADISCORD_VAL_effects.txt")
        fallback = named_block(effects, "VAL_reclamation_reconcile_state_project")
        age = int(re.search(r"days\\s*>\\s*(\\d+)", fallback).group(1))
        for suffix in ("roads", "water", "settlement"):
            decision = named_block(read("common/decisions/ADISCORD_VAL_decisions.txt"), "VAL_reclamation_" + suffix)
            days = int(re.search(r"days_remove\\s*=\\s*(\\d+)", decision).group(1))
            self.assertEqual(age + 1, days)

    def test_recapturing_the_last_restored_home_region_rechecks_the_spirit(self):
        actions = read("common/on_actions/02_ADISCORD_VAL_rework_on_actions.txt")
        hook = named_block(actions, "on_state_control_changed")
        self.assertIn("ROOT = { tag = VAL has_idea = VAL_harvest_of_ash }", hook)
        self.assertIn("ROOT = { VAL_complete_reclamation = yes }", hook)
        for state in (24, 42, 48, 54, 55, 56, 57):
            self.assertIn("state = " + str(state), hook)
        self.assertNotIn("VAL_complete_reclamation", named_block(actions, "on_weekly_VAL"))

    def test_legacy_compensation_is_removed_by_the_new_save_migration(self):
        effects = read("common/scripted_effects/ADISCORD_VAL_effects.txt")
        refresh = named_block(effects, "VAL_reclamation_refresh_state")
        self.assertIn("has_dynamic_modifier = { modifier = VAL_reclamation_recovered_land }", refresh)
        self.assertIn("remove_dynamic_modifier = { modifier = VAL_reclamation_recovered_land }", refresh)
        self.assertNotIn("add_dynamic_modifier = { modifier = VAL_reclamation_recovered_land }", effects)
        legacy = named_block(read("common/dynamic_modifiers/ADISCORD_VAL_contract_dynamic_modifier.txt"), "VAL_reclamation_recovered_land")
        self.assertIn("enable = { always = no }", legacy)
        startup = named_block(read("common/on_actions/02_ADISCORD_VAL_rework_on_actions.txt"), "on_startup")
        self.assertIn("NOT = { has_country_flag = VAL_reclamation_modifier_migrated_v3 }", startup)
        self.assertIn("set_country_flag = VAL_reclamation_modifier_migrated_v3", startup)

    def test_balchansk_branch_has_localised_names_and_descriptions(self):
        for language in ("russian", "english"):
            text = read(f"localisation/{language}/ADISCORD_VAL_decisions_l_{language}.yml")
            for name in ("VAL_Balchansk_Charter", "VAL_Balchansk_Clearing_House"):
                for key in (name, name + "_desc"):
                    self.assertEqual(len(re.findall(rf'(?m)^\\s*{key}:\\d*\\s+"[^"\\r\\n]+"\\s*$', text)), 1, (language, key))
'''
text = one(text, '\nif __name__ == "__main__":', extra + '\nif __name__ == "__main__":')
path.write_text(text)
red = run('red', [sys.executable, '-B', '-m', 'unittest',
                  'tools.tests.test_val_contract_ui.TestValReclamationCompletion.test_paid_reclamation_matches_the_actual_starting_contamination',
                  'tools.tests.test_val_contract_ui.TestValReclamationFollowThrough', '-v'])
assert red['returncode'] == 1 and red['failures']
# A missing serialized modifier is asserted as a missing block, not an import/runtime error.
assert 'ERROR:' not in (OUT / 'red.log').read_text()

path = ROOT / 'common/scripted_triggers/ADISCORD_VAL_rework_triggers.txt'
text = path.read_text()
old = block(text, 'VAL_reclamation_complete')
new = one(old, '\thas_completed_focus = VAL_reclamation_return_home',
          '\thas_completed_focus = VAL_reclamation_return_home\n\tNOT = { has_variable = VAL_reclamation_deposit }')
for state in (42, 48, 54, 55, 56):
    before = block(new, str(state))
    after = one(before, '\t\tcheck_variable = { var = VAL_reclamation_stage value = 3 compare = greater_than_or_equals }',
                '\t\tOR = {\n\t\t\tNOT = { check_variable = { var = VAL_reclamation_stage value = 1 compare = greater_than_or_equals } }\n\t\t\tcheck_variable = { var = VAL_reclamation_stage value = 3 compare = greater_than_or_equals }\n\t\t}')
    new = one(new, before, after)
text = one(text, old, new)
text = text.replace('# COUNTRY VAL: all seven home regions must be restored, not lost or occupied.',
                    '# COUNTRY VAL: 24 and 57 start contaminated; clean home regions have no paid project.\n# All seven must remain owned, controlled and free of unfinished contamination.')
path.write_text(text, encoding='utf-8')

path = ROOT / 'common/scripted_effects/ADISCORD_VAL_effects.txt'
text = path.read_text()
old = block(text, 'VAL_reclamation_reconcile_state_project')
text = one(text, old, one(old, 'days > 44', 'days > 89'))
old = block(text, 'VAL_reclamation_refresh_state')
marker = '\t\tif = {\n\t\t\tlimit = { has_dynamic_modifier = { modifier = ADISCORD_vorkerland_dirty_state } }'
new = one(old, marker, '\t\tif = {\n\t\t\tlimit = { has_dynamic_modifier = { modifier = VAL_reclamation_recovered_land } }\n\t\t\tremove_dynamic_modifier = { modifier = VAL_reclamation_recovered_land }\n\t\t}\n' + marker)
text = one(text, old, new)
path.write_text(text, encoding='utf-8')

path = ROOT / 'common/dynamic_modifiers/ADISCORD_VAL_contract_dynamic_modifier.txt'
text = path.read_text()
text = one(text, '# State reclamation is represented by one status at a time.',
           '# Retain the serialized legacy ID only for guarded removal from older saves.\nVAL_reclamation_recovered_land = {\n\tenable = { always = no }\n}\n\n# State reclamation is represented by one status at a time.')
path.write_text(text, encoding='utf-8')

path = ROOT / 'common/on_actions/02_ADISCORD_VAL_rework_on_actions.txt'
text = path.read_text()
text = text.replace('VAL_reclamation_modifier_migrated_v2', 'VAL_reclamation_modifier_migrated_v3')
text = one(text, 'set_country_flag = VAL_reclamation_modifier_migrated_v3',
           'set_country_flag = VAL_reclamation_modifier_migrated_v3\n\t\t\t\t\tclr_country_flag = VAL_reclamation_modifier_migrated_v2')
old = block(text, 'on_state_control_changed')
hook = '''
			if = {
				limit = {
					ROOT = { tag = VAL has_idea = VAL_harvest_of_ash }
					FROM.FROM = { OR = { state = 24 state = 42 state = 48 state = 54 state = 55 state = 56 state = 57 } }
				}
				ROOT = { VAL_complete_reclamation = yes }
			}
'''
new = one(old, '\n\t\t\tVAL = { VAL_check_nam_concession = yes }', hook + '\n\t\t\tVAL = { VAL_check_nam_concession = yes }')
text = one(text, old, new)
path.write_text(text, encoding='utf-8')


def set_loc(text, key, value):
    pattern = re.compile(r'(?m)^\s*' + re.escape(key) + r':\d*[^\r\n]*$')
    assert len(list(pattern.finditer(text))) <= 1, key
    line = ' ' + key + ':0 "' + value + '"'
    return pattern.sub(lambda m: line, text) if pattern.search(text) else text.rstrip() + '\n' + line + '\n'


for language in ('russian', 'english'):
    path = ROOT / f'localisation/{language}/ADISCORD_VAL_decisions_l_{language}.yml'
    text = path.read_text(encoding='utf-8-sig')
    ru = language == 'russian'
    values = {
        'VAL_Balchansk_Charter': 'Балчанская хартия' if ru else 'Balchansk Charter',
        'VAL_Balchansk_Charter_desc': 'Закрепим самостоятельное договорное управление Балчанска вместо прямого присоединения Окцидии. Администрация получит собственную хартию и политический ресурс; Кефрейт сохранит транзитные договоры. Этот путь исключает прямую интеграцию.' if ru else 'Establish chartered administration in Balchansk instead of directly integrating Occidia. The administration receives its own charter and political resources, while Kefreyt retains transit contracts. This route excludes direct integration.',
        'VAL_Balchansk_Clearing_House': 'Балчанская расчётная палата' if ru else 'Balchansk Clearing House',
        'VAL_Balchansk_Clearing_House_desc': 'Общая расчётная палата свяжет Балчанскую администрацию с кефрейтскими арсеналами и торговыми конторами. Администрация получит хозяйственный институт, а Кефрейт - промышленный исследовательский бонус и политический ресурс.' if ru else 'A joint clearing house connects the Balchansk administration to Kefreyt arsenals and trading offices. The administration gains an economic institution; Kefreyt receives an industrial research bonus and political resources.',
        'VAL_reclamation_completion_tt': 'Восстановите исходно загрязнённые районы [24.GetName] и [57.GetName] через все три этапа решений: дороги, очистка воды, возвращение жителей. Остальные домашние районы - [42.GetName], [48.GetName], [54.GetName], [55.GetName], [56.GetName] - не требуют работ, пока остаются чистыми; начатое в них восстановление нужно завершить. Когда все семь принадлежат Кефрейту, контролируются им, очищены и нет оплаченного незавершённого этапа, национальный дух §Y«$VAL_harvest_of_ash$»§! снимается автоматически. Одних фокусов недостаточно; промышленные площадки после очистки не требуются.' if ru else 'Restore the initially contaminated regions [24.GetName] and [57.GetName] through all three decision stages: roads, clean water and resettlement. The other home regions - [42.GetName], [48.GetName], [54.GetName], [55.GetName], [56.GetName] - need no work while clean; any restoration started there must be completed. When all seven are owned and controlled by Kefreyt, free of contamination and without an outstanding paid stage, the §Y$VAL_harvest_of_ash$§! spirit is removed automatically. Focuses alone do not suffice; post-reclamation industrial sites are optional.',
        'VAL_reclamation_settlement_result_tt': 'Заменяет остаточное загрязнение восстановленной землёй, добавляет строительное место и гражданское предприятие, если их в регионе меньше 20.\\n\\n$VAL_reclamation_completion_tt$' if ru else 'Replaces residual contamination with reclaimed land, adding a building slot and a civilian factory if the state has fewer than 20.\\n\\n$VAL_reclamation_completion_tt$',
    }
    for key, value in values.items():
        text = set_loc(text, key, value)
    key = 'VAL_reclamation_desc'
    match = re.search(r'(?m)^\s*' + key + r':\d*\s*"(.*)"$', text)
    assert match
    text = set_loc(text, key, match.group(1).replace('45 дней', '90 дней').replace('45 days', '90 days'))
    key = 'VAL_startup_guide'
    match = re.search(r'(?m)^\s*' + key + r':\d*\s*"(.*)"$', text)
    assert match
    extra = '\\n\\n§YЭкспансия расположена в центре под «$VAL_Contracts_Outlive_Kings$».§! Начните с «$VAL_frontier_conference$», подготовьте снабжение и выберите администрацию, затем «$VAL_frontier_security_plan$» откроет северный ультиматум через решения. Доступ возможен и через ранние северные или окцидийские договоры; стеландская гражданская война северную ветку не блокирует.' if ru else '\\n\\n§YExpansion is in the centre below Contracts Outlive Kings.§! Start with $VAL_frontier_conference$, prepare logistics and choose an administration; $VAL_frontier_security_plan$ then opens the northern ultimatum through decisions. Earlier northern or Occidian contracts also allow entry; the Stelander civil war does not block this northern branch.'
    text = set_loc(text, key, match.group(1) + extra)
    path.write_text(text, encoding='utf-8-sig')

assert run('focused', [sys.executable, '-B', '-m', 'unittest', 'tools.tests.test_val_contract_ui', '-v'])['returncode'] == 0
jobs = {
    'final-broad': (broad, 180),
    'validator': ([sys.executable, '-B', 'tools/validate_tc.py', '--limit', '300'], 180),
    'whole-suite': ([sys.executable, '-B', '-m', 'unittest', 'discover', '-s', 'tools/tests', '-p', 'test_*.py', '-v'], 180),
}
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
    pending = {name: pool.submit(run, name, *args) for name, args in jobs.items()}
    for future in pending.values():
        future.result()
assert reports['final-broad']['returncode'] != 124
assert not (set(reports['final-broad']['failures']) - set(reports['baseline-broad']['failures']))
assert reports['validator']['returncode'] == 0
expected = {
    'common/dynamic_modifiers/ADISCORD_VAL_contract_dynamic_modifier.txt',
    'common/on_actions/02_ADISCORD_VAL_rework_on_actions.txt',
    'common/scripted_effects/ADISCORD_VAL_effects.txt',
    'common/scripted_triggers/ADISCORD_VAL_rework_triggers.txt',
    'localisation/english/ADISCORD_VAL_decisions_l_english.yml',
    'localisation/russian/ADISCORD_VAL_decisions_l_russian.yml',
    'tools/tests/test_val_contract_ui.py',
}
actual = set(subprocess.check_output(['git', 'diff', '--name-only']).decode().splitlines())
assert actual == expected, actual
from tools.validators.validate_adiscord_division_templates import parse_clausewitz
hashes = {}
for name in sorted(expected):
    data = Path(name).read_bytes()
    text = data.decode('utf-8-sig')
    assert not re.search(r'(?m)^(<<<<<<< |=======\s*$|>>>>>>> )', text), name
    if name.startswith('localisation/'):
        assert data.startswith(b'\xef\xbb\xbf'), name
        keys = re.findall(r'(?m)^\s*([A-Za-z0-9_.-]+):\d*\s*"', text)
        assert len(set(keys)) == len(keys), name
    elif name.startswith('common/'):
        assert not data.startswith(b'\xef\xbb\xbf'), name
        parse_clausewitz(text)
    hashes[name] = hashlib.sha256(data).hexdigest()
    target = OUT / 'source' / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
subprocess.run(['git', 'diff', '--check'], check=True)
(OUT / 'changes.patch').write_bytes(subprocess.check_output(['git', 'diff', '--binary']))
subprocess.run(['git', 'config', 'user.name', 'A-DISCORD automation'], check=True)
subprocess.run(['git', 'config', 'user.email', '81386071+worker2of2month@users.noreply.github.com'], check=True)
subprocess.run(['git', 'add', '--', *sorted(expected)], check=True)
subprocess.run(['git', 'commit', '-m', 'fix(val): make ash removal reachable and finish expansion localisation'], check=True)
head = subprocess.check_output(['git', 'rev-parse', 'HEAD']).decode().strip()
branch = 'fix/val-reclamation-final-' + os.environ['GITHUB_RUN_ID']
subprocess.run(['git', 'push', 'origin', head + ':refs/heads/' + branch], check=True)
manifest = {'base': BASE, 'head': head, 'branch': branch, 'hashes': hashes, 'native_runtime_tested': False}
(OUT / 'manifest.json').write_text(json.dumps(manifest, indent=2))
print('DELIVERY', json.dumps(manifest), flush=True)
