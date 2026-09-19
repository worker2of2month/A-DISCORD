from pathlib import Path

root = Path(__file__).resolve().parent
p = root / 'economy_balance_tests.py'
text = p.read_text(encoding='utf-8')
text = text.replace('get("VAL_industrial_weekly_income", 0)', 'get("VAL_industrial_weekly_income", -1)')
text = text.replace('if node.key == "focus" and any(', 'if node.key == "focus" and isinstance(node.value, list) and any(')
helper = '''class CountryBudgetFixture(EconomyScriptFixture):
    """Preserve native flag names instead of treating them as yes/no arguments."""

    def condition(self, entries, scope="A", previous=None, root="A"):
        def one(node):
            key, value = node.key, node.value
            if key in ("AND", "OR", "NOT", "hidden_trigger"):
                results = [one(child) for child in value]
                return any(results) if key == "OR" else (not any(results) if key == "NOT" else all(results))
            if key in ("has_country_flag", "has_global_flag"):
                return bool(self.scopes[scope].get(value, False))
            if key == "has_dynamic_modifier":
                name = value if isinstance(value, str) else next(child.value for child in value if child.key == "modifier")
                return name in self.scopes[scope].get("dynamic_modifiers", set())
            return super(CountryBudgetFixture, self).condition([node], scope, previous, root)
        return all(one(node) for node in entries)


'''
text = text.replace('class MaterialEconomyBalanceTests(unittest.TestCase):', helper + 'class MaterialEconomyBalanceTests(unittest.TestCase):')
text = text.replace('fixture = EconomyScriptFixture(facts={"has_country_flag": True, "has_dynamic_modifier": False},', 'fixture = CountryBudgetFixture(facts={},')
text = text.replace('        for stage in range(7):', '        fixture.scopes["A"]["VAL_vorkerland_contracts_disrupted"] = True\n        for stage in range(7):')
method = '''
    def test_frontier_ready_checks_solvency_and_replenishment_independently(self):
        source = read("common/scripted_triggers/ADISCORD_VAL_rework_triggers.txt")
        self.assertIn("VAL_ai_frontier_ready = {", source)
        definitions = {node.key: node.value for node in parse_clausewitz(source)}
        for title, overrides, treasury, debt, expected in (
            ("ready despite general crisis", {}, 25, 2, True),
            ("no field army", {"has_army_manpower": False}, 25, 2, False),
            ("insufficient rifles", {"has_equipment": True}, 25, 2, False),
            ("no reserve", {}, 24.99, 2, False),
            ("budget emergency", {}, 25, 3, False),
            ("already at war", {"has_war": True}, 25, 2, False),
            ("subject", {"is_subject": True}, 25, 2, False),
            ("capitulated", {"has_capitulated": True}, 25, 2, False),
        ):
            with self.subTest(case=title):
                facts = {"has_capitulated": False, "is_subject": False, "has_war": False,
                         "has_army_manpower": True, "has_equipment": False,
                         P + "ai_is_crisis": True}
                facts.update(overrides)
                fixture = CountryBudgetFixture(facts=facts)
                fixture.definitions.update(definitions)
                fixture.scopes["A"].update({P + "treasury": treasury, P + "debt_state": debt})
                self.assertEqual(fixture.condition(definitions["VAL_ai_frontier_ready"]), expected)

    def test_building_roles_remain_income_research_and_near_neutral_industry(self):
        for variable, role in (("ADISCORD_business_center_count", "income"),
                               ("ADISCORD_science_center_count", "research"),
                               ("ADISCORD_industrial_cluster_count", "industry")):
            with self.subTest(role=role):
                fixture = budget_fixture()
                before = calculate(fixture)[P + "weekly_balance"]
                fixture.scopes["A"][variable] += 1
                change = calculate(fixture)[P + "weekly_balance"] - before
                if role == "income":
                    self.assertGreater(change, 4)
                elif role == "research":
                    self.assertLess(change, 0)
                else:
                    self.assertLess(abs(change), 1)

'''
text = text.replace('\n\nif __name__ == "__main__":', '\n' + method + '\nif __name__ == "__main__":')
p.write_text(text, encoding='utf-8')

p = root / 'economy_patch.py'
text = p.read_text(encoding='utf-8')
text = text.replace('value = 16', 'value = 18').replace('коэффициентом 16', 'коэффициентом 18')
extra = '''# The social policy validator follows the same live five-level schedule.
text = read(validator)
text = once(text, 'for multiplier in ("0.45", "0.75", "1.00", "1.35", "1.80"):',
            'for multiplier in ("0.25", "0.60", "1.00", "1.35", "1.80"):')
write(validator, text)

# Cluster income offsets upkeep instead of competing with business centres;
# research centres remain a paid research service at the ordinary budget.
edit_named(EFFECTS, "ADISCORD_economy_calculate_consumer_goods_income", lambda body: once(body,
    "var = ADISCORD_economy_consumer_goods_cluster_temp value = 0.45",
    "var = ADISCORD_economy_consumer_goods_cluster_temp value = 0.045"))
edit_named(EFFECTS, "ADISCORD_economy_calculate_factory_income", lambda body: once(body,
    "var = ADISCORD_economy_factory_income_temp value = 0.12",
    "var = ADISCORD_economy_factory_income_temp value = 0.012"))
edit_named(EFFECTS, "ADISCORD_economy_calculate_building_income", lambda body: once(once(body,
    "var = ADISCORD_economy_building_income_temp value = 0.20",
    "var = ADISCORD_economy_building_income_temp value = 0.02"),
    "var = ADISCORD_economy_building_income_temp value = 0.16",
    "var = ADISCORD_economy_building_income_temp value = 0.016"))

for key, description in {
    "ADISCORD_business_center_desc": "§YРоль: доход§!\\\\nБазовый чистый бюджет до модификаторов: §G+23,00 в месяц§!. Расширяет предел казны и деловую налоговую базу. Фактический недельный результат зависит от модели хозяйства, налогов и развития.",
    "ADISCORD_science_center_desc": "§YРоль: исследования§!\\\\nБазовый чистый бюджет при штатном финансировании, до модификаторов: §R-2,92 в месяц§!. Научная сеть повышает скорость исследований и развитие страны. Более высокий научный бюджет увеличивает содержание.",
    "ADISCORD_industrial_cluster_desc": "§YРоль: производство§!\\\\nПочти нейтрален по бюджету: небольшой доход покрывает содержание. Каждый действующий уровень усиливает выпуск исправных военных заводов своего региона на §G5%§!, до §G15%§!. Реальный денежный результат зависит от законов, оружейных контрактов и развития.",
}.items():
    set_loc("localisation/russian/ADISCORD_economy_l_russian.yml", key, description)

doc = "docs/economy/economic-buildings.md"
body = read(doc)
body = once(body, "`1.05 + 0.25 - 0.10 = +1.20` | +1,20 | +14,40", "`18 × (1.05 + 0.25) - 4 × 0.10 = +23.00` | +23,00 | +276,00")
body = once(body, "`0.20 - 0.35 - 0.12 = -0.27` | −0,27 | −3,24", "`18 × 0.02 - 4 × (2 × 0.35 + 0.12) = -2.92` | −2,92 | −35,04")
body = once(body, "`0.45 + 0.16 - 0.18 - 0.12 = +0.31` | +0,31 | +3,72", "`18 × (0.045 + 0.016) - 4 × (0.18 + 0.12) = -0.102` | −0,102 | −1,224")
body = once(body, "дополнительно даёт `+0.12`, и его базовый чистый поток становится `+0.43` в месяц", "дополнительно даёт `18 × 0.012 = +0.216`, и его базовый чистый поток становится `+0.114` в месяц")
body = body.replace("- содержание: +0,10 к административным расходам в месячной базе.", "- содержание: `4 × 0.10 = 0.40` к месячным административным расходам до модификаторов.")
body = body.replace("- содержание: +0,35 к научным и +0,12 к административным расходам.", "- содержание при штатном бюджете: `4 × 2 × 0.35 = 2.80` на науку и `4 × 0.12 = 0.48` на администрацию до модификаторов.")
body = body.replace("- содержание: +0,18 к военно-промышленным и +0,12 к административным расходам.", "- содержание: `4 × 0.18 = 0.72` на промышленность и `4 × 0.12 = 0.48` на администрацию до модификаторов.")
write(doc, body)
# Remove only the blank indentation introduced at the insertion boundary.
body = read(STP_IDEAS)
write(STP_IDEAS, body.replace("\\n\\t\\n\\t\\t# Postwar programme deltas", "\\n\\n\\t\\t# Postwar programme deltas"))

'''
text = text.replace('print("CHANGED_PATHS", sorted(CHANGED), flush=True)', extra + 'print("CHANGED_PATHS", sorted(CHANGED), flush=True)')
p.write_text(text, encoding='utf-8')
