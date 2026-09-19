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

'''
text = text.replace('\n\nif __name__ == "__main__":', '\n' + method + '\nif __name__ == "__main__":')
p.write_text(text, encoding='utf-8')

p = root / 'economy_patch.py'
text = p.read_text(encoding='utf-8')
text = text.replace('value = 16', 'value = 17').replace('коэффициентом 16', 'коэффициентом 17')
extra = '''# The social policy validator follows the same live five-level schedule.
text = read(validator)
text = once(text, 'for multiplier in ("0.45", "0.75", "1.00", "1.35", "1.80"):',
            'for multiplier in ("0.25", "0.60", "1.00", "1.35", "1.80"):')
write(validator, text)

'''
text = text.replace('print("CHANGED_PATHS", sorted(CHANGED), flush=True)', extra + 'print("CHANGED_PATHS", sorted(CHANGED), flush=True)')
p.write_text(text, encoding='utf-8')
