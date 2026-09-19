"""Temporary isolated-branch patch driver; excluded from the gameplay commit."""
from pathlib import Path
import ast
import json
import re
import subprocess
import sys
sys.path.insert(0, str(Path.cwd()))
from tools.tests.test_validate_adiscord_val_rework import named_block_spans

CHANGED = set()
EFFECTS = 'common/scripted_effects/ADISCORD_economy_effects.txt'
MODIFIERS = 'common/scripted_effects/ADISCORD_economy_modifier_effects.txt'
IDEAS = 'common/ideas/ADISCORD_economy_ideas.txt'
AI = 'common/ai_strategy/ADISCORD_economy_ai.txt'
TESTS = 'tools/tests/test_adiscord_economy_weekly_contracts.py'
REBALANCE = 'tools/tests/test_adiscord_economy_rebalance.py'
VALIDATOR = 'tools/validators/validate_adiscord_economy_ai.py'


def load(path):
    return Path(path).read_bytes().decode('utf-8-sig')


def save(path, text):
    p = Path(path)
    bom = p.read_bytes().startswith(b'\xef\xbb\xbf')
    p.write_bytes((b'\xef\xbb\xbf' if bom else b'') + text.encode('utf-8'))
    CHANGED.add(path)


def replace(text, old, new, count=1):
    assert text.count(old) == count, (old[:100], text.count(old), count)
    return text.replace(old, new)


def edit_block(path, name, transform):
    text = load(path)
    matches = named_block_spans(text, name)
    assert len(matches) == 1, (path, name, len(matches))
    b = matches[0]
    save(path, text[:b.start] + transform(b.text) + text[b.end:])


def edit_method(path, name, transform):
    text = load(path)
    matches = [n for n in ast.walk(ast.parse(text)) if isinstance(n, ast.FunctionDef) and n.name == name]
    assert len(matches) == 1, (path, name, len(matches))
    node = matches[0]
    lines = text.splitlines(keepends=True)
    old = ''.join(lines[node.lineno-1:node.end_lineno])
    lines[node.lineno-1:node.end_lineno] = [transform(old)]
    save(path, ''.join(lines))


# Extend the existing source-executing tests before changing gameplay coefficients.
text = load(REBALANCE)
text = replace(text, "        'ADISCORD_state_development_level': 3,", "        'ADISCORD_state_development_level': 3,\n        'ADISCORD_economic_development_level': 3,")
text = replace(text, "        P + 'treasury_cap': 10000,\n", '')
text = replace(text, "    f.run(P + 'calculate_weekly_budget')\n    return f", "    f.run(P + 'calculate_weekly_budget')\n    f.run(P + 'recalculate_treasury_cap')\n    return f")
extra = r'''
    def test_science_network_has_large_but_bounded_native_research_bonuses(self):
        ideas = read('common/ideas/ADISCORD_economy_ideas.txt')
        for tier, expected in enumerate((0.05, 0.10, 0.15, 0.20), 1):
            body = block(ideas, P + f'science_network_{tier}')
            self.assertAlmostEqual(float(re.search(r'research_speed_factor\s*=\s*([\d.]+)', body)[1]), expected)

    def test_science_keeps_its_research_cost_instead_of_becoming_a_cash_printer(self):
        before = building_budget_fixture(science=0).scopes['A']
        after = building_budget_fixture(science=1).scopes['A']
        self.assertAlmostEqual(after[P + 'monthly_balance'] - before[P + 'monthly_balance'], -0.62)

    def test_storage_scales_with_the_economic_building_network(self):
        base = building_budget_fixture(business=0, science=0).scopes['A'][P + 'treasury_cap']
        business = building_budget_fixture(business=1, science=0).scopes['A'][P + 'treasury_cap']
        science = building_budget_fixture(business=0, science=1).scopes['A'][P + 'treasury_cap']
        self.assertEqual(business - base, 100)
        self.assertEqual(science - base, 40)
        large = building_budget_fixture(business=30, science=6).scopes['A'][P + 'treasury_cap']
        self.assertGreater(large, 3000)
        self.assertLessEqual(large, 5000)

    def test_ai_growth_targets_do_not_remove_crisis_or_peacetime_guards(self):
        text = read('common/ai_strategy/ADISCORD_economy_ai.txt')
        healthy = block(text, 'ADISCORD_ai_healthy_civilian_growth')
        for required in ('ADISCORD_economy_ai_is_healthy = yes', 'has_war = no', 'ADISCORD_economy_surplus_streak'):
            self.assertIn(required, healthy)
        self.assertIn('building_target id = ADISCORD_business_center value = 8', healthy)
        self.assertIn('building_target id = ADISCORD_science_center value = 2', healthy)
        self.assertIn('building_target id = ADISCORD_industrial_cluster value = 4', healthy)
        for name in ('ADISCORD_ai_fiscal_crisis', 'ADISCORD_ai_fiscal_stress'):
            body = block(text, name)
            for building in ('business_center', 'science_center', 'industrial_cluster'):
                self.assertIn('building_target id = ADISCORD_' + building + ' value = 0', body)
'''
text = replace(text, '\n\nif __name__ == "__main__":', '\n' + extra + '\n\nif __name__ == "__main__":')
save(REBALANCE, text)
probe = subprocess.run([sys.executable, '-B', '-m', 'unittest', 'tools.tests.test_adiscord_economy_rebalance.BuildingIncomeTests', '-v'], capture_output=True, text=True)
print('BUILDING CONTRACTS BEFORE IMPLEMENTATION\n' + probe.stdout + probe.stderr)
assert probe.returncode != 0 and 'AssertionError' in probe.stderr and '\nERROR:' not in probe.stderr

# Grow actual taxable output while keeping economic models and treasury units.
edit_block(EFFECTS, 'ADISCORD_economy_calculate_business_income', lambda text: replace(replace(replace(text,
    'var = ADISCORD_economy_business_building_temp value = 2.10',
    'var = ADISCORD_economy_business_building_temp value = 30'),
    'var = ADISCORD_economy_business_income min = 0 max = 150',
    'var = ADISCORD_economy_business_income min = 0 max = 5000'),
    '# Business/taxable services. Stronger than ordinary taxes, weaker than resource rents.',
    '# Business centers generate taxable services; the economic model and\n\t# collection modifiers act on this base before weekly settlement.'))
edit_block(EFFECTS, 'ADISCORD_economy_calculate_consumer_goods_income', lambda text: replace(replace(replace(text,
    'var = ADISCORD_economy_consumer_goods_cluster_temp value = 0.45',
    'var = ADISCORD_economy_consumer_goods_cluster_temp value = 10'),
    'var = ADISCORD_economy_consumer_goods_income min = 0 max = 100',
    'var = ADISCORD_economy_consumer_goods_income min = 0 max = 5000'),
    '# Civilian factories are taxable civilian output. This is deliberately below resources/business and below taxes in most states.',
    '# Civilian factories and industrial clusters contribute taxable output.'))
for variable in ('business_income', 'consumer_goods_income'):
    edit_block(MODIFIERS, 'ADISCORD_economy_apply_income_modifier_factors', lambda text, variable=variable: replace(text,
        f'var = ADISCORD_economy_{variable} min = 0 max = 500',
        f'var = ADISCORD_economy_{variable} min = 0 max = 5000'))

# Use the existing weighted-state calculation and normalization, with no new scan.
text = load(EFFECTS)
text = replace(text, 'var = ADISCORD_economy_cluster_factory_output_percent value = 5 }',
               'var = ADISCORD_economy_cluster_factory_output_percent value = 10 }')
text = replace(text, 'var = ADISCORD_economy_cluster_factory_output_percent min = 0 max = 15 }',
               'var = ADISCORD_economy_cluster_factory_output_percent min = 0 max = 30 }', 2)
text = replace(text, 'var = ADISCORD_economy_cluster_factory_output_factor min = 0 max = 0.15 }',
               'var = ADISCORD_economy_cluster_factory_output_factor min = 0 max = 0.30 }', 2)
save(EFFECTS, text)

for tier, (old, new) in enumerate((('0.01', '0.05'), ('0.02', '0.10'), ('0.03', '0.15'), ('0.04', '0.20')), 1):
    edit_block(IDEAS, f'ADISCORD_economy_science_network_{tier}',
               lambda text, old=old, new=new: replace(text, 'research_speed_factor = ' + old, 'research_speed_factor = ' + new))

edit_block(EFFECTS, 'ADISCORD_economy_recalculate_treasury_cap', lambda text: replace(replace(replace(text,
    'var = ADISCORD_economy_cap_temp value = 12 }', 'var = ADISCORD_economy_cap_temp value = 100 }'),
    'var = ADISCORD_economy_cap_temp value = 8 }', 'var = ADISCORD_economy_cap_temp value = 40 }'),
    'var = ADISCORD_economy_treasury_cap min = 300 max = 2000 }',
    'var = ADISCORD_economy_treasury_cap min = 300 max = 5000 }'))

edit_block(AI, 'ADISCORD_ai_fiscal_recovery', lambda text: replace(text,
    'building_target id = ADISCORD_business_center value = 1', 'building_target id = ADISCORD_business_center value = 2'))
edit_block(AI, 'ADISCORD_ai_healthy_civilian_growth', lambda text: replace(replace(text,
    'building_target id = ADISCORD_business_center value = 2', 'building_target id = ADISCORD_business_center value = 8'),
    'building_target id = ADISCORD_industrial_cluster value = 2', 'building_target id = ADISCORD_industrial_cluster value = 4'))
edit_block(AI, 'ADISCORD_ai_healthy_war_industry', lambda text: replace(text,
    'building_target id = ADISCORD_industrial_cluster value = 3', 'building_target id = ADISCORD_industrial_cluster value = 4'))

# Preserve structural checks; align only the authored coefficients and bounds.
edit_method(TESTS, 'test_industrial_cluster_output_is_location_weighted_without_a_new_scan', lambda text: replace(replace(text,
    'cluster_factory_output_percent value = 5', 'cluster_factory_output_percent value = 10'), '"max = 15"', '"max = 30"'))
edit_method(TESTS, 'test_nested_recount_credits_current_owner_not_event_root', lambda text: replace(text,
    'owner[self.PREFIX + "cluster_factory_output_percent"], 10)', 'owner[self.PREFIX + "cluster_factory_output_percent"], 20)'))
edit_method(TESTS, 'test_ai_building_targets_are_bounded_by_fiscal_state', lambda text: replace(replace(replace(text,
    '"ADISCORD_ai_fiscal_recovery": (1, 0, 0)', '"ADISCORD_ai_fiscal_recovery": (2, 0, 0)'),
    '"ADISCORD_ai_healthy_civilian_growth": (2, 2, 2)', '"ADISCORD_ai_healthy_civilian_growth": (8, 2, 4)'),
    r'ADISCORD_industrial_cluster\s+value\s*=\s*3\b', r'ADISCORD_industrial_cluster\s+value\s*=\s*4\b'))
formulas = (
    ('2.10 + 0.25 - 0.10 = +2.25', '30 + 0.25 - 0.10 = +30.15'),
    ('0.20 - 0.35 - 0.12 = -0.27', '0.20 - 0.35 * 2 - 0.12 = -0.62'),
    ('0.45 + 0.16 - 0.18 - 0.12 = +0.31', '10 + 0.16 - 0.18 - 0.12 = +9.86'),
    ('5% × сумма(исправные военные заводы региона × уровень кластера)',
     '10% × сумма(исправные военные заводы региона × уровень кластера)'),
)
def update_formulas(text):
    for old, new in formulas:
        text = replace(text, old, new)
    return text
edit_method(TESTS, 'test_economic_building_reference_documents_roles_and_formulas', update_formulas)
text = load(VALIDATOR)
text = replace(text, '"ADISCORD_economy_cluster_factory_output_percent value = 5"', '"ADISCORD_economy_cluster_factory_output_percent value = 10"')
text = replace(text, 'and "max = 15" in recount', 'and "max = 30" in recount')
text = replace(text, 'industrial cluster output formula is not bounded to +5% per state level', 'industrial cluster output formula is not bounded to +10% per state level')
old = '''    custom_targets = [int(value) for value in re.findall(
        r"building_target\s+id\s*=\s*ADISCORD_(?:business_center|science_center|industrial_cluster)\s+value\s*=\s*(\d+)",
        economy_ai,
    )]
    require(bool(custom_targets) and max(custom_targets) <= 3,
            "AI economic-building targets are missing or encourage uncontrolled construction")'''
new = '''    custom_targets = re.findall(
        r"building_target\s+id\s*=\s*ADISCORD_(business_center|science_center|industrial_cluster)\s+value\s*=\s*(\d+)",
        economy_ai,
    )
    target_limits = {"business_center": 8, "science_center": 2, "industrial_cluster": 4}
    require(bool(custom_targets) and all(int(value) <= target_limits[building]
                                       for building, value in custom_targets),
            "AI economic-building targets are missing or exceed their role-specific limits")'''
text = replace(text, old, new)
save(VALIDATOR, text)

# Player-facing descriptions state the pre-modifier basis, not a fixed payment.
loc_path = 'localisation/russian/ADISCORD_economy_l_russian.yml'
values = {
    'ADISCORD_business_center_desc': r'§YРоль: доход§!\nБазовый чистый вклад одного уровня до модификаторов: §G+30,15 в месяц§! (около §G+6,96 в неделю§!). Деловой центр добавляет 30 к базе услуг, 0,25 прямого дохода и 0,10 административных расходов. Фактический доход зависит от модели экономики, налогов и национальных модификаторов.\n\nПредел казны: §G+100§! до модификаторов. Регион получает §G+5%§! к скорости строительства зданий, §G+10%§! слотов и §G+5%§! к ресурсной отдаче. Доход учитывает только исправные уровни в собственных подконтрольных регионах; каждый следующий центр в стране строится дороже.',
    'ADISCORD_science_center_desc': r'§YРоль: исследования§!\nНациональная сеть из 1/2/4/6 исправных центров даёт соответственно §G+5%/+10%/+15%/+20%§! к скорости исследований. Ступени заменяют друг друга, а не складываются.\n\nПри научном бюджете уровня 3 чистый вклад одного уровня до национальных модификаторов: §R-0,62 в месяц§!. Предел казны: §G+40§! до модификаторов. Центр ускоряет развитие и укрепляет управление. Регион получает §G+5%§! к скорости строительства зданий, §G+6%§! слотов, §G-5%§! к энергопотреблению местных фабрик и §G+3%§! к ресурсной отдаче; каждый следующий центр строится дороже.',
    'ADISCORD_industrial_cluster_desc': r'§YРоль: доход и местное военное производство§!\nКаждый уровень даёт §G+10% к выпуску исправных военных заводов в этом регионе§!, до §G+30%§! при трёх уровнях. Текущий общегосударственный эквивалент: §G+[?ADISCORD_economy_cluster_factory_output_percent|1]%§!. Кластер без военных заводов этот производственный бонус не создаёт.\n\nБазовый чистый вклад до модификаторов: §G+9,86 в месяц§! (около §G+2,28 в неделю§!); при доступном оружейном доходе — §G+9,98 в месяц§!. Национальная сеть кластеров отдельно повышает выпуск заводов. Регион получает §G+10%§! к скорости строительства зданий, §G+8%§! слотов и §G+5%§! к ресурсной отдаче; энергопотребление фабрик повышается на 10%. Учитываются только исправные уровни в собственных подконтрольных регионах; каждый следующий кластер строится дороже.',
}
text = load(loc_path)
for key, value in values.items():
    pattern = re.compile(r'(?m)^(\s*)' + re.escape(key) + r':\d*\s+"[^\r\n]*"\s*$')
    matches = list(pattern.finditer(text))
    assert len(matches) == 1, (key, len(matches))
    match = matches[0]
    # Keep exactly one physical line and avoid absorbing the following newline.
    replacement = match[1].replace('\n', '') + key + ': "' + value + '"'
    trailing = '\n' if match[0].endswith('\n') else ''
    text = text[:match.start()] + replacement + trailing + text[match.end():]
save(loc_path, text)

save('docs/economy/economic-buildings.md', '''# Экономические здания

Деловой центр расширяет доходную базу, научный центр обменивает бюджет на
исследования, промышленный кластер сочетает доход и усиление производства.
Строительная цена измеряется строймощностями HOI4, а не единицами казны.
Каждый следующий объект того же типа в подконтрольных регионах дороже предыдущего.

Доход, содержание и национальные сетевые бонусы дают только исправные уровни
в собственных подконтрольных регионах. При оккупации объект выпадает из экономики
владельца; после возврата контроля снова попадёт в ближайший пересчёт кэша.

## Базовый бюджет

Вклад одного действующего уровня в месячную базу до модификаторов модели,
налогов, общего дохода и расходов. Для научного центра указан бюджет уровня 3.

| Здание | Месячная формула | Чистый поток | За 12 месяцев |
|---|---:|---:|---:|
| Деловой центр | `30 + 0.25 - 0.10 = +30.15` | +30,15 | +361,80 |
| Научный центр | `0.20 - 0.35 * 2 - 0.12 = -0.62` | -0,62 | -7,44 |
| Промышленный кластер | `10 + 0.16 - 0.18 - 0.12 = +9.86` | +9,86 | +118,32 |

Разрешённый оружейный профиль дополнительно даёт кластеру +0,12: чистая база
становится +9,98 в месяц. Научное содержание 0,35 проходит через общий коэффициент
научных расходов 2 и затем через выбранный уровень финансирования; прямой доход
0,20 и административное содержание 0,12 этого коэффициента не получают.

Казна исполняет месячную базу еженедельно: `месячное значение × 3 / 13`.
За 13 недель проходят три месячных расчёта, за 52 недели — 12 месяцев.
Числа в окне экономики отражают действующие коэффициенты, а не гарантированную
фиксированную выплату. Налоговый предпросмотр использует те же доходные базы.

## Деловой центр

Основной объект бюджетного роста. Каждый уровень даёт 30 к базе услуг и
0,25 прямого дохода; административное содержание составляет 0,10 в месяц.
В смешанной модели две поправки к услугам по 1,10 дают чистый вклад
`30 × 1.10 × 1.10 + 0.25 - 0.10 = 36.45`, или около 8,41 в неделю при
нейтральных прочих модификаторах.

Строительство стоит 5500, каждый следующий объект дороже на 750. В регионе
разрешены три уровня. Региональные эффекты: +5% к скорости строительства,
+10% слотов и +5% ресурсной отдачи. Национальный вклад: +0,75 п.п. к месячному
множителю развития и +100 к пределу казны до модификаторов вместимости.

ИИ держит цель два центра в восстановлении и восемь при здоровой мирной
экономике с устойчивым профицитом. В кризисе и при фискальном стрессе цель нулевая.
Цель строительства не выдаёт зданий или денег бесплатно.

## Научный центр

Национальная сеть даёт +5/+10/+15/+20% к скорости исследований при 1/2/4/6
исправных центрах. Ступени заменяют друг друга. Научный центр не является
основным источником денег: его содержание оплачивается через научный бюджет.

Строительство стоит 7000, удорожание +1250; не более двух уровней в регионе.
Региональные эффекты: +5% к скорости строительства, +6% слотов, -5% к энергии
местных фабрик и +3% ресурсной отдачи. Национальный вклад: +2,5 п.п. к месячному
множителю развития, +2 к финансовому контролю и +40 к пределу казны до
модификаторов вместимости. ИИ держит цель два центра только в здоровой мирной
экономике; в восстановлении, стрессе и кризисе цель нулевая.

## Промышленный кластер

Дает 10 к базе гражданского выпуска и 0,16 прямого дохода. Содержание составляет
0,18 военно-промышленных и 0,12 административных расходов в месяц. Гражданский
доход не требует военных заводов, но производственный бонус требует их наличия.

Строительство стоит 8000, удорожание +1500; не более трёх уровней в регионе.
Региональные эффекты: +10% к скорости строительства, +8% слотов, +5% ресурсной
отдачи и +10% энергопотребления фабрик. Каждый уровень добавляет +10% к выпуску
исправных военных заводов своего региона, до +30% при трёх уровнях.
Национальный вклад: +1,5 п.п. к месячному множителю развития. Сеть из 1/2/4/6
кластеров дополнительно даёт +1/+2/+3/+4% выпуска; со второй ступени растёт
набор эффективности. ИИ держит цель четыре кластера в здоровом мире или войне,
один при фискальном стрессе во время войны и ноль в кризисе и восстановлении.

Местное усиление реализовано общегосударственным взвешенным коэффициентом:
`10% × сумма(исправные военные заводы региона × уровень кластера) / все исправные военные заводы страны`.
Повреждённые и неподконтрольные объекты исключены; кластер без военных заводов
не увеличивает этот коэффициент. Максимум взвешенного бонуса составляет 30%.

## Недельный профицит и накопления

Проверочный сценарий использует 60 гражданских и 30 военных фабрик, четыре
верфи, 12 деловых центров, четыре кластера и два научных центра. Развитие равно
3, модель смешанная, налоги и бюджеты уровня 3. Армия насчитывает 250 тысяч
человек, авиация — 300 самолётов, флот — 12 кораблей. Фабрики заняты, обслуживание
долга составляет 6 в месяц. Финансовый контроль и доверие равны 50; фокусных
модификаторов и плоских недельных субсидий нет.

При этих входных данных месячный доход составляет 564,03, расходы 49,19,
чистый недельный баланс около +118,81. Это расчёт скриптовых формул, не замер
полноценной кампании. Он проверяет достижимость профицита и его фактическое
перечисление в казну; сроки строительства и поведение движкового ИИ требуют
игрового прогона. За 13 расчётов при неизменных входных данных казна получает
около 1544,52 сверх начального остатка. Расчётная вместимость здесь равна 1990.

Вместимость рассчитывается по существующей формуле с +100 за деловой и +40 за
научный центр; технический максимум — 5000. Доходные категории услуг и гражданского
выпуска ограничены 5000 каждая, итоговый месячный доход — 10000. Эти пределы
не обрезают сеть из нескольких десятков зданий. Рост основан на строительстве,
а не на бесплатной субсидии всем странам.

## Производительность

Число зданий и взвешенный выпуск кластеров сохраняются в переменных страны.
Плановый пересчёт делает один проход по собственным регионам раз в три месяца;
вне графика он запускается при пометке данных как изменившихся или открытии сводки.
Еженедельное исполнение казны использует кэш без нового `every_owned_state`.
''')
p = 'docs/economy/economy-player-and-runtime.md'
text = load(p)
text = replace(text, 'добавляет 2,10 к базе услуг', 'добавляет 30 к базе услуг')
save(p, text)

Path('/tmp/building-income-paths.json').write_text(json.dumps(sorted(CHANGED)), encoding='utf-8')
for path in sorted(CHANGED):
    raw = Path(path).read_bytes()
    if path.startswith('common/'):
        assert not raw.startswith(b'\xef\xbb\xbf'), path
    if path.startswith('localisation/'):
        assert raw.startswith(b'\xef\xbb\xbf'), path
print('CHANGED_PATHS', json.dumps(sorted(CHANGED)))
