"""Source-level production gate regressions; these do not emulate the game engine."""
from __future__ import annotations

import operator
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
AI = ROOT / "common/ai_strategy"
AA_TECH = "ADISCORD_tech_point_defense_aa"
EARLY_AA_TECH = "ADISCORD_tech_improvised_air_defense"
CARRIER_TECH = "ADISCORD_tech_armored_carrier_program"
FUNDING = "ADISCORD_economy_ai_can_fund_advanced_forces"
OPS = {"=": operator.eq, "<": operator.lt, ">": operator.gt,
       "<=": operator.le, ">=": operator.ge}


def parse(text: str) -> list:
    """Parse the small assignment/comparison subset used by these AI gates."""
    tokens = re.findall(r'"(?:\\.|[^"\\])*"|[{}]|[<>]=?|=|[^\s{}=<>]+',
                        re.sub(r"(?m)#.*$", "", text))
    position = 0

    def entries(nested: bool = False) -> list:
        nonlocal position
        result = []
        while position < len(tokens):
            if tokens[position] == "}":
                if not nested:
                    raise AssertionError("unexpected closing brace")
                position += 1
                return result
            key, comparison = tokens[position:position + 2]
            position += 2
            if comparison not in OPS:
                raise AssertionError(f"unsupported comparison: {comparison}")
            value = tokens[position]
            position += 1
            if value == "{":
                value = entries(True)
            result.append((key, comparison, value))
        if nested:
            raise AssertionError("unclosed block")
        return result

    return entries()


def child(nodes: list, key: str) -> list:
    matches = [value for name, _, value in nodes if name == key]
    if len(matches) != 1 or not isinstance(matches[0], list):
        raise AssertionError(f"expected one block: {key}")
    return matches[0]


def evaluate(nodes: list, context: dict) -> bool:
    """Reject unsupported predicates instead of silently treating them as true."""
    def results() -> list[bool]:
        values = []
        for key, comparison, value in nodes:
            if key in ("AND", "OR", "NOT"):
                nested = [evaluate([entry], context) for entry in value]
                values.append(all(nested) if key == "AND" else
                              any(nested) if key == "OR" else not any(nested))
            elif key == "has_equipment":
                values.append(evaluate(value, context["equipment"]))
            elif key == "stockpile_ratio":
                fields = {name: val for name, _, val in value}
                comparison = next(op for name, op, _ in value if name == "ratio")
                values.append(OPS[comparison](context["stockpile_ratio"][fields["archetype"]],
                                              float(fields["ratio"])))
            elif key in ("set_temp_variable", "multiply_temp_variable", "check_variable"):
                variables = context["variables"]
                name, op, operand = value[0]
                number = variables[operand] if operand in variables else float(operand)
                if key == "set_temp_variable":
                    variables[name] = number
                    values.append(True)
                elif key == "multiply_temp_variable":
                    variables[name] *= number
                    values.append(True)
                else:
                    values.append(OPS[op](variables[name], number))
            elif key in context.get("triggers", {}):
                result = evaluate(context["triggers"][key], context)
                values.append(result if value == "yes" else not result)
            elif key in ("has_tech", "has_country_flag"):
                values.append(value in context[key])
            elif key in context:
                expected = {"yes": True, "no": False}.get(value)
                if expected is None:
                    expected = float(value)
                values.append(OPS[comparison](context[key], expected))
            else:
                raise AssertionError(f"unsupported predicate: {key}")
        return values

    return all(results())


def active(policy: list, context: dict, previously_active: bool = False) -> bool:
    enable = evaluate(child(policy, "enable"), context)
    abort = [value for key, _, value in policy if key == "abort"]
    if abort:
        return (previously_active or enable) and not evaluate(abort[0], context)
    if ("abort_when_not_enabled", "=", "yes") not in policy:
        raise AssertionError("policy requires an explicit lifecycle")
    return enable


class AIProductionLifecycleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        technology = parse((AI / "ADISCORD_technology_doctrine_ai.txt").read_text(encoding="utf-8"))
        val = parse((AI / "VAL.txt").read_text(encoding="utf-8"))
        cls.carriers = child(technology, "ADISCORD_produce_armored_carriers")
        cls.generic_aa = child(technology, "ADISCORD_ai_anti_air_buffer")
        cls.volunteer_aa = child(val, "ADISCORD_VAL_volunteer_air_defence")

    def context(self, *, factories=8, stock=0, funded=True, advanced_aa=False,
                pending=True, aid_open=True) -> dict:
        techs = {EARLY_AA_TECH, CARRIER_TECH}
        if advanced_aa:
            techs.add(AA_TECH)
        return {
            "num_of_military_factories": factories,
            "has_tech": techs,
            "has_country_flag": {"VAL_cw_volunteers_pending"} if pending else set(),
            "STP_cw_kefreyt_aid_open": aid_open,
            FUNDING: funded,
            "ADISCORD_ai_rifle_replacement_emergency": False,
            "equipment": {"anti_air_equipment": stock,
                          "ADISCORD_armored_carrier_archetype": stock},
        }

    def test_aa_minima_never_overlap(self) -> None:
        for factories in (7, 8, 9, 10, 15):
            for advanced in (False, True):
                for stock in (0, 59, 60, 299, 300, 650, 651):
                    with self.subTest(factories=factories, advanced=advanced, stock=stock):
                        ctx = self.context(factories=factories, advanced_aa=advanced, stock=stock)
                        requests = sum(active(p, ctx) for p in (self.generic_aa, self.volunteer_aa))
                        self.assertLessEqual(requests, 1)

    def test_early_volunteer_production_is_not_disabled(self) -> None:
        self.assertTrue(active(self.volunteer_aa, self.context()))
        self.assertFalse(active(self.volunteer_aa, self.context(factories=7)))
        self.assertFalse(active(self.volunteer_aa, self.context(stock=60)))
        self.assertFalse(active(self.volunteer_aa, self.context(pending=False)))
        self.assertFalse(active(self.volunteer_aa, self.context(aid_open=False)))

    def test_technology_upgrade_hands_aa_floor_to_generic_policy(self) -> None:
        before = self.context()
        self.assertTrue(active(self.volunteer_aa, before))
        self.assertFalse(active(self.generic_aa, before))
        after = self.context(advanced_aa=True)
        self.assertFalse(active(self.volunteer_aa, after, previously_active=True))
        self.assertTrue(active(self.generic_aa, after))

    def test_generic_aa_keeps_stock_hysteresis(self) -> None:
        for stock, expected in ((300, True), (650, True), (651, False)):
            with self.subTest(stock=stock):
                self.assertEqual(active(self.generic_aa, self.context(advanced_aa=True, stock=stock), True), expected)
        self.assertFalse(active(self.generic_aa, self.context(advanced_aa=True, stock=300)))

    def test_carrier_policy_aborts_when_funding_is_lost(self) -> None:
        self.assertTrue(active(self.carriers, self.context()))
        for stock in (0, 899, 900, 1000, 1500):
            with self.subTest(stock=stock):
                self.assertFalse(active(self.carriers, self.context(funded=False, stock=stock), True))

    def test_carrier_funding_recovery_respects_restart_stock(self) -> None:
        self.assertFalse(active(self.carriers, self.context(funded=False)))
        self.assertTrue(active(self.carriers, self.context(stock=899)))
        self.assertFalse(active(self.carriers, self.context(stock=900)))

    def test_carrier_stock_and_factory_hysteresis_remains(self) -> None:
        for stock, expected in ((900, True), (1000, True), (1500, True), (1501, False)):
            with self.subTest(stock=stock):
                self.assertEqual(active(self.carriers, self.context(stock=stock), True), expected)
        self.assertFalse(active(self.carriers, self.context(factories=6), True))
        self.assertTrue(active(self.carriers, self.context(factories=7)))

    def test_aa_floors_still_request_one_factory_each(self) -> None:
        for policy in (self.generic_aa, self.volunteer_aa):
            minimums = [dict((key, value) for key, _, value in nodes)
                        for name, _, nodes in policy if name == "ai_strategy"]
            self.assertEqual(minimums, [{"type": "equipment_production_min_factories_archetype",
                                         "id": "anti_air_equipment", "value": "1"}])


class ArmyQualityTests(unittest.TestCase):
    equipment = ("infantry_equipment", "ADISCORD_squad_weapons_equipment",
                 "support_equipment", "artillery_equipment")

    def setUp(self):
        self.triggers = dict((key, value) for key, _, value in parse(
            (ROOT / "common/scripted_triggers/ADISCORD_scripted_triggers_generic.txt").read_text()))
        self.policies = parse((AI / "default.txt").read_text())
        template_text = (ROOT / "common/ai_templates/ADISCORD_land_templates.txt").read_text()
        self.templates = parse(re.sub(r"\b(?:blocked_for|available_for)\s*=\s*\{[^}]*\}",
                                      "", template_text))

    def context(self, fill=1.0, reserve=0.2, target=10):
        return {
            "variables": {key: value for eq in self.equipment for key, value in (
                (f"num_target_equipment_in_armies_k@{eq}", target),
                (f"num_equipment_in_armies_k@{eq}", target * fill))},
            "stockpile_ratio": {eq: reserve for eq in self.equipment},
            "triggers": self.triggers, "is_ai": True, "has_capitulated": False,
            "ADISCORD_economy_ai_is_crisis": False, "has_manpower": 10000,
            "equipment": {eq: 10000 for eq in self.equipment},
        }

    def test_recruitment_brake_has_recovery_hysteresis(self):
        self.assertIn("ADISCORD_ai_rebuild_field_army", [key for key, _, _ in self.policies])
        policy = child(self.policies, "ADISCORD_ai_rebuild_field_army")
        for fill, reserve, old, expected in (
            (.84, .04, False, True), (.85, .04, False, False),
            (.90, .04, True, True), (.95, .04, True, False),
            (.70, .10, True, False), (1, .0, False, False)):
            with self.subTest(fill=fill, reserve=reserve, old=old):
                self.assertEqual(active(policy, self.context(fill, reserve), old), expected)

    def test_each_basic_equipment_shortage_stops_expansion(self):
        self.assertIn("ADISCORD_ai_army_needs_replacements", self.triggers)
        for eq in self.equipment:
            ctx = self.context()
            ctx["variables"][f"num_equipment_in_armies_k@{eq}"] = 7
            ctx["stockpile_ratio"][eq] = 0
            self.assertTrue(evaluate(self.triggers["ADISCORD_ai_army_needs_replacements"], ctx))

    def test_no_army_does_not_lock_initial_recruitment(self):
        self.assertIn("ADISCORD_ai_army_needs_replacements", self.triggers)
        self.assertFalse(evaluate(self.triggers["ADISCORD_ai_army_needs_replacements"],
                                  self.context(0, 0, 0)))

    def test_first_field_upgrade_preserves_replacements_and_manpower(self):
        source = child(child(self.templates, "ADISCORD_infantry_templates"),
                       "ADISCORD_reconstruction_brigade")
        gate = child(source, "can_upgrade_in_field")
        self.assertFalse(evaluate(gate, self.context(.7, 0)))
        self.assertTrue(evaluate(gate, self.context()))
        ctx = self.context()
        ctx["has_manpower"] = 2999
        self.assertFalse(evaluate(gate, ctx))

    def test_infantry_target_chain_starts_with_cheap_design(self):
        role = child(self.templates, "ADISCORD_infantry_templates")
        priorities = [float(child(child(role, name), "upgrade_prio")[0][2]) for name in
                      ("ADISCORD_reconstruction_brigade", "ADISCORD_line_brigade",
                       "ADISCORD_defensive_line_brigade")]
        self.assertGreater(priorities[0], priorities[1])
        self.assertGreater(priorities[1], priorities[2])

    def test_field_readiness_scales_with_army_size(self):
        for target in (.1, 10, 1000):
            ctx = self.context(.84, 0, target)
            self.assertTrue(evaluate(self.triggers["ADISCORD_ai_army_needs_replacements"], ctx))
            self.assertFalse(evaluate(self.triggers["ADISCORD_ai_can_refit_field_army"], ctx))

    def test_baseline_availability_and_field_upgrade_are_separate_contracts(self):
        from tools.validators.validate_adiscord_tech_doctrine import ai_force_progression_contract_issues
        templates = (ROOT / "common/ai_templates/ADISCORD_land_templates.txt").read_text()
        policies = (AI / "default.txt").read_text()
        self.assertEqual(ai_force_progression_contract_issues(templates, policies), [])
        blocked = templates.replace("ADISCORD_reconstruction_brigade = {",
                                    "ADISCORD_reconstruction_brigade = {\n"
                                    "enable = { has_equipment = { infantry_equipment > 3000 } }")
        self.assertIn("AI field baseline must not depend on factories or equipment stock",
                      ai_force_progression_contract_issues(blocked, policies))

    def test_specialist_chains_do_not_skip_the_source_target(self):
        for role, source, target in (
            ("mountaineer", "mountaineer_brigade", "networked_mountaineer_brigade"),
            ("tank", "tank_battlegroup", "networked_tank_battlegroup")):
            tree = child(self.templates, f"ADISCORD_{role}_templates")
            first = child(tree, f"ADISCORD_{source}")
            last = child(tree, f"ADISCORD_{target}")
            self.assertGreater(float(child(first, "upgrade_prio")[0][2]),
                               float(child(last, "upgrade_prio")[0][2]))
            self.assertIn(("ADISCORD_ai_can_refit_field_army", "=", "yes"),
                          child(first, "can_upgrade_in_field"))

    def test_simultaneous_land_and_air_floors_leave_rifle_capacity(self):
        tech = parse((AI / "ADISCORD_technology_doctrine_ai.txt").read_text())
        names = ("produce_squad_weapons_low_stock", "produce_support_equipment_low_stock",
                 "produce_artillery_low_stock", "produce_supply_trucks_low_stock",
                 "limited_air_program", "ai_anti_tank_buffer", "ai_anti_air_buffer",
                 "ai_platform_battlegroups", "produce_armored_carriers", "ai_heavy_platforms")
        policies = [child(self.policies + tech, f"ADISCORD_{name}") for name in names]
        techs = set(re.findall(r"has_tech\s*=\s*(\w+)",
                              (AI / "default.txt").read_text() +
                              (AI / "ADISCORD_technology_doctrine_ai.txt").read_text()))
        stocks = set(re.findall(r"has_equipment\s*=\s*\{\s*(\w+)",
                               (AI / "default.txt").read_text() +
                               (AI / "ADISCORD_technology_doctrine_ai.txt").read_text()))
        for factories in range(1, 21):
            for emergency in (False, True):
                ctx = self.context(.7 if emergency else 1, 0)
                ctx.update({"num_of_military_factories": factories, "num_of_supply_nodes": 1,
                            "has_tech": techs, "has_war": True, FUNDING: True,
                            "ADISCORD_economy_ai_is_healthy": True,
                            "equipment": dict.fromkeys(stocks, 0)})
                floors = 0
                for policy in policies:
                    if active(policy, ctx, True):
                        for name, _, nodes in policy:
                            if name == "ai_strategy":
                                fields = dict((key, val) for key, _, val in nodes)
                                if fields["type"].startswith("equipment_production_min_factories"):
                                    floors += int(fields["value"])
                with self.subTest(factories=factories, emergency=emergency):
                    self.assertLessEqual(floors, factories - 1)
                    if emergency:
                        self.assertLessEqual(floors, 4)


if __name__ == "__main__":
    unittest.main()
