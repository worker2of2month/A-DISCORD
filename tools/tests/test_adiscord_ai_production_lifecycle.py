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


if __name__ == "__main__":
    unittest.main()
