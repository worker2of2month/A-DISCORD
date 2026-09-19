"""Integrate the verified accounting contract without overwriting country work."""
from pathlib import Path
import ast
import subprocess
import sys

CONTROL = Path(__file__).resolve().parent
helpers = (CONTROL / 'economy_patch.py').read_text(encoding='utf-8').split('new_test = ', 1)[0]
exec(compile(helpers, 'economy_patch_helpers.py', 'exec'), globals())
CANDIDATE = '13725b3d3aae2c484397e1d61597cbfc049f0701'
EFFECTS = 'common/scripted_effects/ADISCORD_economy_effects.txt'
MODIFIERS = 'common/scripted_effects/ADISCORD_economy_modifier_effects.txt'
TEST = 'tools/tests/test_adiscord_economy_balance.py'


def candidate(path):
    return subprocess.check_output(['git', 'show', CANDIDATE + ':' + path]).decode('utf-8-sig')


def replace_method(path, name, replacement):
    source = read(path)
    node = next(node for node in ast.walk(ast.parse(source)) if isinstance(node, ast.FunctionDef) and node.name == name)
    lines = source.splitlines(keepends=True)
    lines[node.lineno-1:node.end_lineno] = [replacement.rstrip() + '\n']
    write(path, ''.join(lines))


def function_source(source, name):
    node = next(node for node in ast.walk(ast.parse(source)) if isinstance(node, ast.FunctionDef) and node.name == name)
    lines = source.splitlines(keepends=True)
    return ''.join(lines[node.lineno-1:node.end_lineno])


# Reuse the source-executing budget fixture, but keep the current country's
# authored deltas and readiness predicate rather than installing a second set.
source = candidate(TEST)
remove = {
    'test_each_shabrat_reform_has_an_exact_native_delta_preview',
    'test_val_recovery_returns_four_weekly_per_stage_and_does_not_compound',
    'test_val_ultimatum_and_war_share_readiness_instead_of_24_divisions',
    'test_frontier_ready_checks_solvency_and_replenishment_independently',
}
lines = source.splitlines(keepends=True)
for node in sorted((node for node in ast.walk(ast.parse(source)) if isinstance(node, ast.FunctionDef) and node.name in remove), key=lambda n:n.lineno, reverse=True):
    del lines[node.lineno-1:node.end_lineno]
source = ''.join(lines)
new_method = '''
    def test_refusal_event_uses_the_same_readiness_as_the_offensive(self):
        events = parse_clausewitz(read("events/ADISCORD_VAL_contract_events.txt"))
        option = next(node for node in walk(events) if node.key == "option" and any(
            child.key == "name" and child.value == "val_rework.111.war" for child in node.value))
        chance = next(node for node in option.value if node.key == "ai_chance")
        self.assertTrue(any(node.key == "VAL_ai_frontier_force_ready" for node in walk(chance.value)))
        self.assertFalse(any(node.key == "num_divisions" for node in walk(chance.value)))

'''
source = once(source, '\nif __name__ == "__main__":', '\n' + new_method + '\nif __name__ == "__main__":')
write(TEST, source)
print('RED: integrated budget and event contracts against current main', flush=True)
red = run_tests('tools.tests.test_adiscord_economy_balance')
assert red.returncode != 0 and 'ERROR:' not in red.stderr

# The concurrent commit changed source yields but not the modifier layer.
# Keep every source-yield change and use the smaller fiscal conversion of 8.
original = subprocess.check_output(['git', 'show', 'd6cc3c77078a25f7318fbf7e371fc6779eab3351:' + MODIFIERS]).decode('utf-8-sig')
assert read(MODIFIERS) == original, 'modifier owner changed concurrently'
write(MODIFIERS, candidate(MODIFIERS).replace('value = 18', 'value = 8'))
edit_named(EFFECTS, 'ADISCORD_economy_recalculate_tax_dependent_income', lambda body: once(body,
    '\tset_variable = { var = ADISCORD_economy_monthly_income value = ADISCORD_economy_personal_income }',
    '\tADISCORD_economy_scale_taxable_income = yes\n\tset_variable = { var = ADISCORD_economy_monthly_income value = ADISCORD_economy_personal_income }'))
for kind in ('army', 'research', 'social'):
    for action in ('preview', 'refresh'):
        name = 'ADISCORD_economy_' + action + '_' + kind + '_policy'
        anchor = '\tdivide_variable = { var = ADISCORD_economy_' + kind + '_expenses value = 100 }'
        addition = '\tmultiply_variable = { var = ADISCORD_economy_' + kind + '_expenses value = 4 }'
        edit_named(EFFECTS, name, lambda body, anchor=anchor, addition=addition: once(body, anchor, anchor+'\n'+addition))
# Production clusters must not replace dedicated business centres.
edit_named(EFFECTS, 'ADISCORD_economy_calculate_consumer_goods_income', lambda body: once(body,
    'var = ADISCORD_economy_consumer_goods_cluster_temp value = 0.45',
    'var = ADISCORD_economy_consumer_goods_cluster_temp value = 0.15'))
edit_named(EFFECTS, 'ADISCORD_economy_calculate_factory_income', lambda body: once(body,
    'var = ADISCORD_economy_factory_income_temp value = 0.12',
    'var = ADISCORD_economy_factory_income_temp value = 0.04'))
edit_named(EFFECTS, 'ADISCORD_economy_calculate_building_income', lambda body: once(body,
    'var = ADISCORD_economy_building_income_temp value = 0.16',
    'var = ADISCORD_economy_building_income_temp value = 0.05'))

# Decisions already use the new readiness check; refusal still contained the
# retired division-count veto. Preserve the response probabilities and choice.
path = 'events/ADISCORD_VAL_contract_events.txt'
source = read(path)
old = 'ai_chance = { base = 70 modifier = { factor = 0 num_divisions < 24 } modifier = { factor = 0.3 has_manpower < 20000 } }'
new = 'ai_chance = { base = 70 modifier = { factor = 0 VAL_ai_frontier_force_ready = no } modifier = { factor = 0.3 has_manpower < 20000 } }'
write(path, once(source, old, new))

# Graft only the ownership-aware research validator, retaining every other
# validator change from current main.
validator = 'tools/validators/validate_adiscord_economy_ai.py'
replace_method(validator, 'research_policy_flow_issues', function_source(candidate(validator), 'research_policy_flow_issues'))

loc = 'localisation/russian/ADISCORD_economy_l_russian.yml'
set_loc(loc, 'ADISCORD_business_center_desc', '§YРоль: доход§!\\nБазовый чистый бюджет до модификаторов: §G+18,40 в месяц§!. Расширяет предел казны и деловую налоговую базу. Фактический недельный результат зависит от модели хозяйства, налогов и развития.')
set_loc(loc, 'ADISCORD_science_center_desc', '§YРоль: исследования§!\\nБазовый чистый бюджет при штатном финансировании, до модификаторов: §R-1,68 в месяц§!. Научная сеть повышает скорость исследований и развитие страны. Более высокий научный бюджет увеличивает содержание.')
set_loc(loc, 'ADISCORD_industrial_cluster_desc', '§YРоль: местное военное производство§!\\nПочти нейтрален по бюджету: базовый чистый поток §G+0,40 в месяц§! до модификаторов, либо §G+0,72§! при доступном оружейном доходе. Каждый действующий уровень усиливает выпуск исправных военных заводов своего региона на §G5%§!, до §G15%§!.')

path = 'docs/economy/economic-buildings.md'
source = read(path)
source = once(source, '`2.10 + 0.25 - 0.10 = +2.25` | +2,25 | +27,00', '`8 × (2.10 + 0.25) - 4 × 0.10 = +18.40` | +18,40 | +220,80')
source = once(source, '`0.20 - 0.35 - 0.12 = -0.27` | −0,27 | −3,24', '`8 × 0.20 - 4 × (2 × 0.35 + 0.12) = -1.68` | −1,68 | −20,16')
source = once(source, '`0.45 + 0.16 - 0.18 - 0.12 = +0.31` | +0,31 | +3,72', '`8 × (0.15 + 0.05) - 4 × (0.18 + 0.12) = +0.40` | +0,40 | +4,80')
source = once(source, 'дополнительно даёт `+0.12`, и его базовый чистый поток становится `+0.43` в месяц', 'дополнительно даёт `8 × 0.04 = +0.32`, и его базовый чистый поток становится `+0.72` в месяц')
source = source.replace('- содержание: +0,10 к административным расходам в месячной базе.', '- содержание: `4 × 0.10 = 0.40` к месячным административным расходам до модификаторов.')
source = source.replace('- содержание: +0,35 к научным и +0,12 к административным расходам.', '- содержание при штатном бюджете: `4 × 2 × 0.35 = 2.80` на науку и `4 × 0.12 = 0.48` на администрацию до модификаторов.')
source = source.replace('- содержание: +0,18 к военно-промышленным и +0,12 к административным расходам.', '- содержание: `4 × 0.18 = 0.72` на промышленность и `4 × 0.12 = 0.48` на администрацию до модификаторов.')
write(path, source)

path = 'tools/tests/test_adiscord_economy_weekly_contracts.py'
verified = candidate(path)
for name in ('test_building_tooltips_lead_with_role_and_budget_impact', 'test_economic_building_reference_documents_roles_and_formulas'):
    body = function_source(verified, name)
    body = body.replace('+23,00', '+18,40').replace('-2,92', '-1,68')
    body = body.replace('18 × (1.05 + 0.25) - 4 × 0.10 = +23.00', '8 × (2.10 + 0.25) - 4 × 0.10 = +18.40')
    body = body.replace('18 × 0.02 - 4 × (2 × 0.35 + 0.12) = -2.92', '8 × 0.20 - 4 × (2 × 0.35 + 0.12) = -1.68')
    body = body.replace('18 × (0.045 + 0.016) - 4 × (0.18 + 0.12) = -0.102', '8 × (0.15 + 0.05) - 4 × (0.18 + 0.12) = +0.40')
    replace_method(path, name, body)

path = 'tools/tests/test_adiscord_economy_rebalance.py'
source = read(path)
source = once(source, 'self.assertGreaterEqual(results[1] - results[0], 0.9)', 'self.assertGreaterEqual(results[1] - results[0], 7.2)')
source = once(source, 'self.assertLess(results[1] - results[0], 2)', 'self.assertLess(results[1] - results[0], 16)')
source = once(source, 'self.assertGreater(results[1] - results[0], 2.5)', 'self.assertGreater(results[1] - results[0], 20)')
write(path, source)

path = 'docs/economy/economy-player-and-runtime.md'
write(path, read(path).rstrip() + '''

## Фискальные единицы и достижимые +100 в неделю

После отраслевых модификаторов все шесть источников дохода переводятся
в месячные денежные единицы с коэффициентом 8. Операционные расходы,
включая ремонт, используют коэффициент 4. Проценты не масштабируются:
месячное обслуживание остаётся равным долгу, умноженному на годовую ставку
и делённому на 1200, с последующим модификатором обслуживания. Недельный
перевод остаётся точным `3 / 13`, цены разовых действий не переоцениваются.

Кэш налоговых баз остаётся немасштабированным. Полный пересчёт и налоговый
предпросмотр одинаково переводят четыре налоговых источника, а неналоговый
кэш уже содержит переведённую ренту и доход зданий. Предпросмотр расходов,
немедленное изменение бюджета и недельный расчёт используют одинаковые
денежные единицы. Повторный пересчёт не увеличивает начисление.

Развитая региональная экономика и восстановленный Стеланд должны иметь
достижимый устойчивый профицит не менее 100 в неделю при штатных бюджетах.
Это не стартовая субсидия каждому тегу. Регрессионные сценарии исполняют
арифметику действующих скриптов, включая расходы на полевую армию,
авиацию, флот, науку, социальные обязательства и обслуживание долга.
Такие сценарии не заменяют проверку темпа кампании в движке.
''')

print('GREEN: reconciled source arithmetic and campaign entry', flush=True)
green = run_tests('tools.tests.test_adiscord_economy_balance')
assert green.returncode == 0
subprocess.run(['git', 'diff', '--check'], check=True)
(ROOT.parent / 'changed-paths.txt').write_text('\n'.join(sorted(CHANGED)) + '\n', encoding='utf-8')
print('INTEGRATED_PATHS', sorted(CHANGED), flush=True)
