from pathlib import Path
import re

ROOT = Path.cwd()


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


def focus(text, name):
    match = re.search(r'\bid\s*=\s*' + re.escape(name) + r'\b', text)
    assert match, name
    start = list(re.finditer(r'(?m)^\s*focus\s*=\s*\{', text[:match.start()]))[-1].start()
    return block(text[start:], 'focus')


path = ROOT / 'common/national_focus/ADISCORD_national_focus_VAL.txt'
text = path.read_text(encoding='utf-8')
positions = {
    'VAL_frontier_conference': (20, 13), 'VAL_frontier_logistics': (16, 15),
    'VAL_frontier_commissioners': (19, 15), 'VAL_frontier_provincial_offices': (21, 15),
    'VAL_frontier_return_irem': (24, 15), 'VAL_frontier_security_plan': (20, 17),
    'VAL_frontier_treaty_offices': (20, 18), 'VAL_New_Supply_Base': (20, 19),
    'VAL_Northern_Settlement': (16, 19), 'VAL_Stelander_Ultimatum': (24, 19),
    'VAL_Campaign_Secured': (20, 21), 'VAL_Reopen_Trade_Routes': (16, 23),
    'VAL_Settle_Industrial_Debts': (20, 23), 'VAL_Veterans_Of_The_Campaign': (24, 23),
    'VAL_Return_To_World_Market': (20, 25), 'VAL_Bezhaysk_Operation': (28, 23),
    'VAL_Stelander_Crisis_Opens': (36, 11), 'VAL_Arms_For_The_Burning': (32, 13),
    'VAL_Keep_The_Arsenals': (36, 13), 'VAL_Seize_The_Northern_Passes': (40, 13),
    'VAL_The_Steel_Contract': (36, 15), 'VAL_Occidian_Registries': (36, 17),
    'VAL_Balchansk_Charter': (34, 19), 'VAL_Integrate_Occidia': (38, 19),
    'VAL_Balchansk_Clearing_House': (34, 21), 'VAL_Resource_War_Contracts': (30, 10),
}
for name, (x, y) in positions.items():
    old = focus(text, name)
    new = old
    for key, value in [('x', x), ('y', y)]:
        new, count = re.subn(r'(?m)^(\s*' + key + r'\s*=\s*)-?\d+\s*$', lambda m: m.group(1) + str(value), new)
        assert count == 1, (name, key)
    if name == 'VAL_frontier_conference':
        new = one(new, 'prerequisite = { focus = VAL_The_Steel_Contract focus = VAL_Market_Roads_North }',
                  'prerequisite = { focus = VAL_Contracts_Outlive_Kings }')
    if name in ('VAL_frontier_conference', 'VAL_frontier_security_plan'):
        new = one(new, 'search_filters = {', 'search_filters = { FOCUS_FILTER_ANNEXATION')
    if name == 'VAL_Bezhaysk_Operation':
        new = one(new, 'prerequisite = { focus = VAL_Contracts_Outlive_Kings }', 'prerequisite = { focus = VAL_Campaign_Secured }')
    text = one(text, old, new)
for name, parent in [('VAL_Reopen_Trade_Routes', 'VAL_New_Supply_Base'),
                     ('VAL_Settle_Industrial_Debts', 'VAL_Industrial_Mobilization_Plan'),
                     ('VAL_Veterans_Of_The_Campaign', 'VAL_Army_Of_The_Ledger')]:
    old = focus(text, name)
    text = one(text, old, one(old, '        prerequisite = { focus = ' + parent + ' }\n', ''))
old = focus(text, 'VAL_Campaign_Secured')
new = one(old, '  prerequisite = { focus = VAL_Stelander_Ultimatum }',
          '  prerequisite = { focus = VAL_Stelander_Ultimatum }\n  prerequisite = { focus = VAL_New_Supply_Base }')
text = one(text, old, new)
text = text.replace('# Postwar border policy. The three columns separate logistics, government and claims.',
                    '# Central expansion: logistics, administration and eastern claims flank the northern campaign.')
path.write_text(text, encoding='utf-8')

path = ROOT / 'common/scripted_triggers/ADISCORD_VAL_rework_triggers.txt'
text = path.read_text(encoding='utf-8')
old = block(text, 'VAL_frontier_postwar')
text = one(text, old, one(old, '    has_global_flag = STP_cw_union_wars_finished\n', ''))
recovery = '\n# COUNTRY: only the original seven regions can complete the national reclamation programme.\nVAL_reclamation_fully_restored = {\n\thas_completed_focus = VAL_reclamation_return_home\n\tNOT = { has_variable = VAL_reclamation_deposit }\n'
for state in (24, 42, 48, 54, 55, 56, 57):
    recovery += f'\t{state} = {{ is_owned_by = VAL is_controlled_by = VAL check_variable = {{ var = VAL_reclamation_stage value = 3 compare = greater_than_or_equals }} }}\n'
recovery += '}\n'
text = one(text, '\nVAL_frontier_postwar = {', recovery + "\n# The historical ID is retained; a foreign civil war does not gate Kefreyt's northern policy.\nVAL_frontier_postwar = {")
path.write_text(text, encoding='utf-8')

path = ROOT / 'common/scripted_effects/ADISCORD_VAL_effects.txt'
text = path.read_text(encoding='utf-8')
old = block(text, 'VAL_reclamation_finish_state_project')
new = one(old, 'VAL = { ADISCORD_economy_mark_dirty = yes }',
          'VAL = { ADISCORD_economy_mark_dirty = yes VAL_reclamation_check_full_recovery = yes }')
text = one(text, old, new)
old = block(text, 'VAL_reclamation_reconcile_state_project')
text = one(text, old, one(old, 'days > 44', 'days > 89'))
old = block(text, 'VAL_reclamation_refresh_state')
key = '\t\tif = {\n\t\t\tlimit = { has_dynamic_modifier = { modifier = ADISCORD_vorkerland_dirty_state } }'
new = one(old, key, '\t\tif = {\n\t\t\tlimit = { has_dynamic_modifier = { modifier = VAL_reclamation_recovered_land } }\n\t\t\tremove_dynamic_modifier = { modifier = VAL_reclamation_recovered_land }\n\t\t}\n' + key)
text = one(text, old, new)
recovery = '''
# COUNTRY: successful settlement and load recovery share an idempotent national reward.
VAL_reclamation_check_full_recovery = {
	if = {
		limit = {
			has_idea = VAL_harvest_of_ash
			VAL_reclamation_fully_restored = yes
		}
		remove_ideas = VAL_harvest_of_ash
		ADISCORD_economy_mark_dirty = yes
	}
}
'''
text = one(text, '\nVAL_migrate_reclamation_modifiers = {', recovery + '\nVAL_migrate_reclamation_modifiers = {')
path.write_text(text, encoding='utf-8')

path = ROOT / 'common/dynamic_modifiers/ADISCORD_VAL_contract_dynamic_modifier.txt'
text = path.read_text(encoding='utf-8')
legacy = '# Retain the serialized legacy ID for guarded removal when loading older campaigns.\nVAL_reclamation_recovered_land = {\n\tenable = { always = no }\n}\n\n'
text = one(text, '# State reclamation is represented by one status at a time.', legacy + '# State reclamation is represented by one status at a time.')
path.write_text(text, encoding='utf-8')

path = ROOT / 'common/on_actions/02_ADISCORD_VAL_rework_on_actions.txt'
text = path.read_text(encoding='utf-8')
old = block(text, 'on_startup')
new = one(old, '\t\t\t\t\tVAL_check_nam_concession = yes', '\t\t\t\t\tVAL_check_nam_concession = yes\n\t\t\t\t\tVAL_reclamation_check_full_recovery = yes')
text = one(text, old, new)
old = block(text, 'on_state_control_changed')
hook = '''
			if = {
				limit = {
					ROOT = { tag = VAL has_idea = VAL_harvest_of_ash }
					FROM.FROM = { OR = { state = 24 state = 42 state = 48 state = 54 state = 55 state = 56 state = 57 } }
				}
				ROOT = { VAL_reclamation_check_full_recovery = yes }
			}
'''
new = one(old, '\n\t\t\tVAL = { VAL_check_nam_concession = yes }', hook + '\n\t\t\tVAL = { VAL_check_nam_concession = yes }')
text = one(text, old, new)
path.write_text(text, encoding='utf-8')


def set_loc(text, key, value):
    pattern = re.compile(r'(?m)^\s*' + re.escape(key) + r':\d*[^\r\n]*$')
    matches = list(pattern.finditer(text))
    assert len(matches) <= 1, key
    line = ' ' + key + ':0 "' + value + '"'
    return pattern.sub(lambda m: line, text) if matches else text.rstrip() + '\n' + line + '\n'


for language in ('russian', 'english'):
    path = ROOT / f'localisation/{language}/ADISCORD_VAL_decisions_l_{language}.yml'
    text = path.read_text(encoding='utf-8-sig')
    ru = language == 'russian'
    values = {
        'VAL_frontier_conference': 'План внешней экспансии' if ru else 'Foreign Expansion Plan',
        'VAL_frontier_conference_desc': 'После «Контракты переживают королей» центральная ветка открывает северную экспансию. Подготовьте снабжение и выберите устройство будущих владений, затем предъявите ультиматум северным государствам. Стеландская гражданская война не является условием этого маршрута; Кефрейт должен сохранять независимость и возможность вести собственную кампанию.' if ru else 'After Contracts Outlive Kings, the central branch opens northern expansion. Prepare logistics and choose how future territories will be governed, then issue an ultimatum to the northern states. This route does not require the Stelander civil war to end; Kefreyt must remain independent and able to conduct its own campaign.',
        'VAL_frontier_security_plan': 'Ультиматум северным государствам' if ru else 'Ultimatum to the Northern States',
        'VAL_frontier_security_plan_desc': 'Обеспечив снабжение и определив устройство будущих владений, предъявим требования северному блоку. Фокус открывает решение §Y«$VAL_frontier_demand_CIN$»§! в категории §Y«$VAL_frontier$»§! и выделяет политический ресурс на его запуск. Сам ультиматум отправляется через решение; отказ позволяет начать подготовленную войну.' if ru else 'With logistics prepared and the future administration chosen, issue demands to the northern bloc. This focus unlocks the §Y$VAL_frontier_demand_CIN$§! decision in §Y$VAL_frontier$§! and supplies political resources to launch it. Send the ultimatum through the decision; refusal permits the prepared war.',
        'VAL_frontier_postwar_ready_tt': 'Кефрейт независим, не капитулировал и не выведен из регионального противостояния условиями поражения. Завершение стеландской гражданской войны не требуется.' if ru else 'Kefreyt is independent, has not capitulated and has not been excluded from regional conflict by its defeat terms. The Stelander civil war does not need to end.',
        'VAL_Balchansk_Charter': 'Балчанская хартия' if ru else 'Balchansk Charter',
        'VAL_Balchansk_Charter_desc': 'Закрепим самостоятельное договорное управление Балчанска вместо прямого присоединения Окцидии. Администрация получит собственную хартию и политический ресурс; Кефрейт сохранит транзитные договоры. Этот путь исключает прямую интеграцию.' if ru else 'Establish chartered administration in Balchansk instead of directly integrating Occidia. The administration receives its own charter and political resources, while Kefreyt retains transit contracts. This route excludes direct integration.',
        'VAL_Balchansk_Clearing_House': 'Балчанская расчётная палата' if ru else 'Balchansk Clearing House',
        'VAL_Balchansk_Clearing_House_desc': 'Общая расчётная палата свяжет Балчанскую администрацию с кефрейтскими арсеналами и торговыми конторами. Администрация получит хозяйственный институт, а Кефрейт - промышленный исследовательский бонус и политический ресурс.' if ru else 'A joint clearing house connects the Balchansk administration to Kefreyt arsenals and trading offices. The administration gains an economic institution; Kefreyt receives an industrial research bonus and political resources.',
        'VAL_reclamation_full_recovery_tt': 'После завершения всех трёх этапов в §Yсеми исходных регионах§! и сохранения владения и контроля над ними снимается национальный дух §Y«$VAL_harvest_of_ash$»§!. Промышленные площадки после очистки для этого не требуются.' if ru else 'Completing all three stages in the §Yseven original regions§!, while retaining ownership and control, removes the §Y$VAL_harvest_of_ash$§! national spirit. Post-reclamation industrial sites are not required.',
        'VAL_reclamation_settlement_result_tt': 'Заменяет остаточное загрязнение восстановленной землёй, добавляет строительное место и гражданское предприятие, если их в регионе меньше 20.\\n\\n$VAL_reclamation_full_recovery_tt$' if ru else 'Replaces residual contamination with reclaimed land, adding a building slot and a civilian factory if the state has fewer than 20.\\n\\n$VAL_reclamation_full_recovery_tt$',
    }
    for key, value in values.items():
        text = set_loc(text, key, value)
    key = 'VAL_reclamation_desc'
    match = re.search(r'(?m)^\s*' + key + r':\d*\s*"(.*)"$', text)
    assert match
    value = match.group(1).replace('45 дней', '90 дней').replace('45 days', '90 days') + '\\n\\n$VAL_reclamation_full_recovery_tt$'
    text = set_loc(text, key, value)
    for key in ('VAL_Contracts_Outlive_Kings_desc', 'VAL_startup_guide'):
        match = re.search(r'(?m)^\s*' + key + r':\d*\s*"(.*)"$', text)
        assert match, key
        extra = '\\n\\n§YЭкспансия - центральная ветка под фокусом «$VAL_Contracts_Outlive_Kings$».§! «$VAL_frontier_conference$» ведёт к северному ультиматуму, затем к Нодрулу и Стеландеру. Кризисная ветка Окцидии расположена отдельно справа.' if ru else '\\n\\n§YExpansion follows the central branch below Contracts Outlive Kings.§! $VAL_frontier_conference$ leads to the northern ultimatum and then to Nodrul and Stelander. The Occidian crisis branch is separate on the right.'
        text = set_loc(text, key, match.group(1) + extra)
    path.write_text(text, encoding='utf-8-sig')
    path = ROOT / f'localisation/{language}/ADISCORD_ideas_l_{language}.yml'
    text = path.read_text(encoding='utf-8-sig')
    key = 'VAL_harvest_of_ash_desc'
    match = re.search(r'(?m)^\s*' + key + r':\d*\s*"(.*)"$', text)
    assert match
    value = match.group(1)
    banner = value.find('\\n\\n\\n\\n')
    assert banner >= 0
    text = set_loc(text, key, value[:banner] + '\\n\\n$VAL_reclamation_full_recovery_tt$' + value[banner:])
    path.write_text(text, encoding='utf-8-sig')

path = ROOT / 'tools/tests/test_adiscord_economy_rebalance.py'
text = path.read_text(encoding='utf-8')
text = one(text, 'self.assertIn({"VAL_The_Steel_Contract", "VAL_Market_Roads_North"}, alternatives)',
           'self.assertEqual(alternatives, [{"VAL_Contracts_Outlive_Kings"}])')
path.write_text(text, encoding='utf-8')
