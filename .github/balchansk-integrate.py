from pathlib import Path
import ast
import os
import re
import subprocess
import sys

SOURCE = Path.cwd()
TARGET = Path('/tmp/balchansk-integration')
BASE = 'e022582ee19523c77e284b9d5042d893ff7202eb'
OLD = 'd3fec28655e9d9cfc095c4e38c91ee2129a401dc'
sys.path.insert(0, str(SOURCE))
from tools.tests.test_validate_adiscord_val_rework import named_block_spans

subprocess.run(['git', 'fetch', '--depth=2', 'origin', BASE], check=True)
subprocess.run(['git', 'worktree', 'add', '--detach', str(TARGET), BASE], check=True)

def read(path, root=TARGET):
    return (root / path).read_text(encoding='utf-8-sig')

def write(path, text):
    p = TARGET / path
    encoding = 'utf-8-sig' if p.read_bytes().startswith(b'\xef\xbb\xbf') else 'utf-8'
    p.write_text(text, encoding=encoding)

def once(text, old, new):
    assert text.count(old) == 1, (old, text.count(old))
    return text.replace(old, new, 1)

def definition(text, name):
    spans = named_block_spans(text, name)
    assert len(spans) == 1, (name, len(spans))
    return spans[0].text

def replace_definition(text, name, replacement):
    return once(text, definition(text, name), replacement)

def unchanged_copy(path):
    original = subprocess.check_output(['git', 'show', f'{OLD}:{path}'], cwd=SOURCE)
    assert (TARGET / path).read_bytes() == original, f'Upstream also modified {path}'
    (TARGET / path).write_bytes((SOURCE / path).read_bytes())

# These country data types have no concurrent edits in the new main commit.
for path in (
    'common/country_leader/ADISCORD_traits_VAL.txt',
    'common/ideas/ADISCORD_VAL_rework_ideas.txt',
    'common/national_focus/ADISCORD_national_focus_VAL.txt',
    'common/national_focus/ADISCORD_national_focus_VAL_defeated.txt',
):
    unchanged_copy(path)

path = 'common/on_actions/02_ADISCORD_VAL_rework_on_actions.txt'
text = read(path)
text = once(text, 'VAL_initialize_arsenal_recovery = yes VAL_call_subjects_to_wars', 'VAL_initialize_arsenal_recovery = yes VAL_grant_contract_warlord = yes VAL_call_subjects_to_wars')
text = once(text, '\ton_startup = {\n\t\teffect = {', '\ton_startup = {\n\t\teffect = {\n\t\t\tOCA = { VAL_initialize_balchansk_administration = yes }')
old = definition(text, 'on_puppet')
new = once(old, 'VAL_call_subjects_to_wars = yes } }', 'VAL_call_subjects_to_wars = yes } OCA = { VAL_reconcile_balchansk_income = yes } }')
text = once(text, old, new)
control = definition(text, 'on_state_control_changed')
control_new = once(control, '\teffect = {', '\teffect = {\n            if = {\n                limit = { FROM.FROM = { OR = { state = 44 state = 88 } } OCA = { exists = yes } }\n                OCA = { VAL_reconcile_balchansk_income = yes }\n            }')
text = once(text, control, control_new)
write(path, text)

path = 'common/scripted_effects/ADISCORD_VAL_effects.txt'
text = read(path)
ours = read(path, SOURCE)
form = definition(text, 'VAL_form_occidian_administration')
form = once(form, '\t\t\tclr_country_flag = VAL_occidian_settlement_pending', '\t\t\tOCA = { VAL_initialize_balchansk_administration = yes }\n\t\t\tclr_country_flag = VAL_occidian_settlement_pending')
text = replace_definition(text, 'VAL_form_occidian_administration', form)
text = replace_definition(text, 'VAL_adopt_commonwealth', definition(ours, 'VAL_adopt_commonwealth'))
for name in ('VAL_grant_contract_warlord', 'VAL_initialize_balchansk_administration', 'VAL_reconcile_balchansk_income'):
    assert not named_block_spans(text, name), name
    text += '\n\n' + definition(ours, name) + '\n'
write(path, text)

path = 'common/scripted_triggers/ADISCORD_VAL_rework_triggers.txt'
text = read(path)
ours = read(path, SOURCE)
for name in ('VAL_supply_base_secured', 'VAL_nod_dominated', 'VAL_nod_border_settled', 'VAL_stelander_dominated', 'VAL_can_proclaim_commonwealth'):
    text = replace_definition(text, name, definition(ours, name))
assert not named_block_spans(text, 'VAL_state_in_contract_sphere')
text += '\n\n# STATE: legal possession and control must both belong to the contract bloc.\n' + definition(ours, 'VAL_state_in_contract_sphere') + '\n'
write(path, text)

# Update only the new administration, supply and formation strings. Preserve
# the independent peace patch's ownership of its scenario presentation.
for language, suffix in (('english', 'english'), ('russian', 'russian')):
    path = f'localisation/{language}/ADISCORD_VAL_decisions_l_{suffix}.yml'
    ours = read(path, SOURCE)
    text = read(path)
    pattern = re.compile(r'^\s+([A-Za-z0-9_.]+):.*$', re.M)
    selected = {}
    for match in pattern.finditer(ours):
        key = match.group(1)
        if key == 'OCA' or key.startswith(('OCA_', 'VAL_Balchansk_', 'VAL_balchansk_', 'VAL_contract_warlord')) or key in ('VAL_supply_base_secured_tt', 'VAL_Occidian_Registries_desc', 'VAL_commonwealth_requirements_tt', 'VAL_commonwealth_proclaimed_tt'):
            selected[key] = match.group(0).strip('\r\n')
    additions = []
    for key, line in selected.items():
        existing = re.compile(r'^\s+' + re.escape(key) + r':.*$', re.M)
        found = list(existing.finditer(text))
        assert len(found) <= 1, key
        if found:
            text = text[:found[0].start()] + '\n' + line.lstrip('\r\n') + text[found[0].end():]
        else:
            additions.append(line)
    text = text.rstrip() + '\n\n # Balchansk charter and Commonwealth\n' + '\n'.join(additions) + '\n'
    write(path, text)

path = 'tools/tests/test_validate_adiscord_val_rework.py'
text = read(path)
ours = read(path, SOURCE)

def method(source, cls, prefix):
    node = next(n for n in ast.parse(source).body if isinstance(n, ast.ClassDef) and n.name == cls)
    methods = [n for n in node.body if isinstance(n, ast.FunctionDef) and n.name.startswith(prefix)]
    assert len(methods) == 1, (cls, prefix)
    n = methods[0]
    lines = source.splitlines(keepends=True)
    return ''.join(lines[n.lineno-1:n.end_lineno])

old = method(text, 'ValFormationAndCommandTests', 'test_formation_requires_campaign')
new = method(ours, 'ValFormationAndCommandTests', 'test_formation_requires_campaign')
text = once(text, old, new)
text = once(text, 'if __name__ == "__main__":\n    unittest.main()', '')
text += '\n\nclass ValBalchanskCommonwealthRegressionTests(unittest.TestCase):\n'
for name in (
    'test_balchansk_charter_and_integration_are_real_alternatives',
    'test_occidian_creation_installs_the_playable_program',
    'test_supply_base_accepts_an_administration_without_forcing_annexation',
    'test_warlord_is_a_character_reward_of_proclamation',
    'test_local_balchansk_income_is_suspended_and_restored_with_its_asset',
):
    text += method(ours, 'ValTreatyAdministrationRegressionTests', name) + '\n\n'
text += 'if __name__ == "__main__":\n    unittest.main()\n'
write(path, text)

path = 'docs/development/focus-effects.md'
text = read(path)
text += '''\n\n### Балчанская администрация и Кефрейтское содружество\n\nOCA сохраняет технический тег и территориальные правила Окцидийского договора,\nно получает название Балчанской договорной администрации. Создание и загрузка\nсуществующей администрации вызывают VAL_initialize_balchansk_administration;\nсмена дерева не сбрасывает уже завершённые фокусы.\n\nВетка VAL после реестров предлагает взаимоисключающие прямую интеграцию и\nБалчанскую хартию. Хартия сохраняет местное правительство, выдаёт ему постоянные\nдоходы и открывает совместную расчётную палату. В дереве администраций 12 фокусов\nOCA видны только Балчанску: гражданское управление либо гарнизонная директория,\nпорт, мастерские, шахты, арсеналы, офицерская подготовка и снабжение.\n\nПортовые и шахтные доходы зависят от владения и контроля штатов 44 и 88.\nVAL_reconcile_balchansk_income удаляет доход при потере объекта и возвращает\nзаработанное учреждение после восстановления контроля без повторной награды.\nИдеи сбрасывают экономический кэш при добавлении и снятии.\n\nVAL_supply_base_secured допускает как прямое владение Окцидией, так и обеспеченную\nадминистрацию OCA. Северный ресурсный пояс остаётся под прямым управлением VAL.\nПровозглашение Содружества требует завершённой кампании, Contracts Outlive Kings,\nнезависимости, мира и стабильности не ниже 50%. Признанные договорные границы\nSRP и YPR не требуют новой войны ради штатов 29 и 46. Владение и контроль через\nподчинённых допускаются, но иностранный владелец или оккупант не засчитывается.\n\nПри провозглашении действующий Валера Солгалов получает личную черту\nVAL_contract_warlord: атака и организация +5%, планирование +10%, расход\nснабжения -5%, командный ресурс +0,10 в день. Черта не суммируется, не меняет\nлидера и не выдаётся совету, заменившему Солгалова. Загрузка существующего\nСодружества восстанавливает награду только действующему Солгалову.\n\nСтатические регрессии находятся в ValBalchanskCommonwealthRegressionTests и\nValFormationAndCommandTests. Нативная приёмка требует свежего запуска HOI4:\nпоявление дерева OCA, обе ветки управления, потеря и возврат доходного объекта,\nобе территориальные модели Содружества и однократная черта действующего лидера.\n'''
write(path, text)

# The completed main peace patch and all three NKA flag sizes remain untouched.
for path in ('common/on_actions/09_ADISCORD_scripted_peace_on_actions.txt', 'common/scripted_effects/ADISCORD_STP_scripted_effects.txt', 'tools/tests/test_adiscord_nod_capitulation_reservation.py', 'gfx/flags/NKA.tga', 'gfx/flags/medium/NKA.tga', 'gfx/flags/small/NKA.tga'):
    expected = subprocess.check_output(['git', 'show', f'{BASE}:{path}'], cwd=TARGET)
    assert (TARGET / path).read_bytes() == expected, path
subprocess.run(['git', 'diff', '--check'], cwd=TARGET, check=True)
print('Balchansk/Commonwealth changes staged on main without replacing its peace or flag changes.')
