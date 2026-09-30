"""Parsed route and transaction scenarios; these are not native engine tests."""

from pathlib import Path
import re
import unittest

from tools.tests.test_adiscord_stp_preparation import (
    block, scalar, walk, matches_conditions, selected_effects,
)
from tools.validators.validate_adiscord_division_templates import parse_clausewitz
from tools.lib.focus_sources import read_focus_source

ROOT = Path(__file__).resolve().parents[2]
ROUTES = ("houses", "festival", "staff", "trade", "security", "regent")


def read(path):
    return (ROOT / path).read_text(encoding="utf-8-sig")


class PartySecondActTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.focuses = {
            scalar(e.value, "id"): e.value
            for e in parse_clausewitz(read("focus_trees/STP/postwar/party/focuses.txt"))
            if e.key == "focus" and isinstance(e.value, list)
        }
        cls.effects = {e.key: e.value for e in parse_clausewitz(read(
            "common/scripted_effects/ADISCORD_STP_scripted_effects.txt"))}
        cls.decisions = {e.key: e.value for e in walk(parse_clausewitz(read(
            "common/decisions/ADISCORD_STP_decisions.txt")))
            if e.key.startswith("STP_pe_") and isinstance(e.value, list)}
        cls.events = {scalar(e.value, "id"): e.value for e in parse_clausewitz(read(
            "events/ADISCORD_STP_events.txt")) if e.key == "country_event"}

    def require(self, mapping, name):
        self.assertTrue(name in mapping, f"Missing playable second-act entry: {name}")
        return mapping[name]

    def facts(self, route, receipt=False, current=True, completed=False):
        return {
            ("STP", "STP_pe_current", "yes"): current,
            ("STP", "has_capitulated", "no"): True,
            ("STP", "has_variable", f"STP_pe_{route}_deposit"): receipt,
            ("STP", "variable", f"STP_pe_{route}_deposit"): 450 if receipt else 0,
            ("STP", "has_country_flag", f"STP_pe_{route}_prepared"): completed,
            ("STP", "has_completed_focus", f"STP_pe_{route}_opening"): True,
            ("STP", "numeric", "has_political_power"): 35,
            ("STP", "variable", "ADISCORD_economy_treasury"): 450,
        }

    def selected(self, entries, facts):
        return [e for _, e in selected_effects(entries, facts)]

    def apply_transaction(self, entries, facts):
        """Apply parsed accounting effects; native scheduling remains unmodelled."""
        for _, entry in selected_effects(entries, facts):
            if entry.key.startswith("STP_pe_") and entry.key in self.effects:
                self.apply_transaction(self.effects[entry.key], facts)
            elif entry.key in ("add_to_variable", "subtract_from_variable", "set_variable"):
                name = scalar(entry.value, "var")
                raw = scalar(entry.value, "value")
                try:
                    value = float(raw)
                except ValueError:
                    value = facts.get(("STP", "variable", raw), 0)
                key = ("STP", "variable", name)
                if entry.key == "set_variable":
                    facts[key] = value
                else:
                    sign = -1 if entry.key == "subtract_from_variable" else 1
                    facts[key] = facts.get(key, 0) + sign * value
                facts[("STP", "has_variable", name)] = True
            elif entry.key == "clear_variable":
                facts[("STP", "has_variable", entry.value)] = False
                facts[("STP", "variable", entry.value)] = 0
            elif entry.key == "add_political_power":
                key = ("STP", "numeric", "has_political_power")
                facts[key] = facts.get(key, 0) + float(entry.value)
            elif entry.key in ("set_country_flag", "clr_country_flag"):
                facts[("STP", "has_country_flag", entry.value)] = entry.key == "set_country_flag"
            elif entry.key in ("add_ideas", "remove_ideas"):
                facts[("STP", "has_idea", entry.value)] = entry.key == "add_ideas"
            elif entry.key == "add_timed_idea":
                facts[("STP", "has_idea", scalar(entry.value, "idea"))] = True
            elif entry.key in ("add_manpower", "add_stability", "army_experience"):
                facts[("STP", "reward", entry.key)] = facts.get(("STP", "reward", entry.key), 0) + float(entry.value)
            elif entry.key == "add_equipment_to_stockpile":
                key = ("STP", "equipment", scalar(entry.value, "type"))
                facts[key] = facts.get(key, 0) + float(scalar(entry.value, "amount"))
            elif entry.key not in ("custom_effect_tooltip", "unlock_decision_tooltip", "ADISCORD_economy_mark_dirty"):
                raise AssertionError(f"Unhandled transaction effect: {entry.key}")

    def test_six_routes_each_have_twelve_new_focuses_with_reachable_endings(self):
        for index, route in enumerate(ROUTES, 1):
            shown = {k: v for k, v in self.focuses.items()
                     if k.startswith(f"STP_pe_{route}_")}
            self.assertEqual(len(shown), 12, route)
            for name, focus in shown.items():
                self.assertEqual(scalar(block(focus, "allow_branch"),
                                        f"STP_party_leader_{index}"), "yes")
                self.assertEqual(scalar(focus, "cancel_if_invalid"), "yes")
            reached = set(self.focuses) - set(shown)
            for _ in range(12):
                for name, focus in shown.items():
                    groups = [e.value for e in focus if e.key == "prerequisite"]
                    if all(any(e.value in reached for e in group) for group in groups):
                        reached.add(name)
            self.assertFalse(set(shown) - reached)

    def test_each_exclusive_choice_has_a_route_to_a_terminal_focus(self):
        for route in ROUTES:
            ids = {k for k in self.focuses if k.startswith(f"STP_pe_{route}_")}
            for side in ("a", "b"):
                start = f"STP_pe_{route}_policy_{side}"
                end = f"STP_pe_{route}_ending_{side}"
                self.require(self.focuses, start)
                self.require(self.focuses, end)
                opposite = f"STP_pe_{route}_policy_{'b' if side == 'a' else 'a'}"
                self.assertIn(opposite, [e.value for e in block(self.focuses[start], "mutually_exclusive")])
                # Follow the chosen middle route without requiring the excluded one.
                reached = (set(self.focuses) - ids) | {f"STP_pe_{route}_opening", start}
                for _ in range(12):
                    for name in ids - {opposite, f"STP_pe_{route}_work_{'b' if side == 'a' else 'a'}"}:
                        groups = [e.value for e in self.focuses[name] if e.key == "prerequisite"]
                        if all(any(e.value in reached for e in group) for group in groups):
                            reached.add(name)
                self.assertIn(end, reached)

    def test_new_nodes_do_not_overlap_visible_nodes_from_other_source_fragments(self):
        focuses = {
            scalar(e.value, "id"): e.value
            for e in walk(parse_clausewitz(read_focus_source(
                ROOT / "common/national_focus/ADISCORD_STP_civil_war.txt")))
            if e.key == "focus" and isinstance(e.value, list)
        }
        for leader, route in enumerate(ROUTES, 1):
            facts = self.facts(route)
            facts[("STP", "has_country_flag", "STP_cw_postwar")] = True
            facts[("STP", f"STP_party_leader_{leader}", "yes")] = True
            for phase in (1, 4):
                facts[("STP", "variable", "STP_ch_phase")] = phase
                visible = {}
                for name, focus in focuses.items():
                    gates = [e.value for e in focus if e.key == "allow_branch"]
                    if all(matches_conditions(gate, facts) for gate in gates):
                        visible[name] = (int(scalar(focus, "x")), int(scalar(focus, "y")))
                for name, (x, y) in visible.items():
                    if not name.startswith("STP_pe_"):
                        continue
                    for other, (ox, oy) in visible.items():
                        if name != other and y == oy:
                            self.assertGreaterEqual(abs(x - ox), 2, f"{name} overlaps {other} at phase {phase}")

    def test_program_payment_accepts_exact_balance_and_blocks_duplicate_receipts(self):
        for route in ROUTES:
            decision = self.require(self.decisions, f"STP_pe_{route}_programme")
            gates = block(decision, "custom_cost_trigger")
            for treasury, pp, receipt, expected in (
                (450, 35, False, True), (449.99, 35, False, False),
                (450, 34.99, False, False), (900, 70, True, False),
            ):
                facts = self.facts(route, receipt=receipt)
                facts[("STP", "variable", "ADISCORD_economy_treasury")] = treasury
                facts[("STP", "numeric", "has_political_power")] = pp
                self.assertEqual(matches_conditions(gates, facts), expected)
                selected = self.selected(block(decision, "complete_effect"), facts)
                debits = [e for e in selected if e.key == "subtract_from_variable"]
                self.assertEqual(len(debits), int(expected))
                if expected:
                    self.assertEqual(scalar(debits[0].value, "value"), "450")
                    self.assertEqual([e.value for e in selected if e.key == "add_political_power"], ["-35"])

    def test_paid_work_survives_leader_change_but_lost_regime_only_refunds(self):
        for route in ROUTES:
            helper = self.require(self.effects, f"STP_pe_{route}_settle")
            for current, receipt in ((True, True), (False, True), (True, False), (False, False)):
                facts = self.facts(route, receipt=receipt, current=current)
                selected = self.selected(helper, facts)
                prepared = [e for e in selected if e.key == "set_country_flag"
                            and e.value == f"STP_pe_{route}_prepared"]
                refunds = [e for e in selected if e.key == "add_to_variable"
                           and scalar(e.value, "var") == "ADISCORD_economy_treasury"]
                self.assertEqual(bool(prepared), current and receipt)
                self.assertEqual(bool(refunds), not current and receipt)
                clears = [e.value for e in selected if e.key == "clear_variable"]
                self.assertEqual(f"STP_pe_{route}_deposit" in clears, receipt)

    def test_preparation_prevents_crisis_and_stale_callbacks_do_not_reopen_it(self):
        for index, route in enumerate(ROUTES):
            event = self.require(self.events, f"ADISCORD_STP_ch.{46 + index}")
            for current, prepared in ((True, False), (True, True), (False, False), (False, True)):
                facts = self.facts(route, current=current, completed=prepared)
                selected = self.selected(block(event, "immediate"), facts)
                crises = [e for e in selected if e.key == "add_ideas"]
                self.assertEqual(bool(crises), current and not prepared)

    def test_old_event_keeps_only_a_close_option_after_crisis_is_settled(self):
        for index, route in enumerate(ROUTES):
            event = self.require(self.events, f"ADISCORD_STP_ch.{46 + index}")
            options = [e.value for e in event if e.key == "option"]
            for current, crisis in ((True, True), (True, False), (False, False), (False, True)):
                facts = self.facts(route, current=current)
                facts[("STP", "has_idea", f"STP_pe_{route}_crisis")] = crisis
                shown = [o for o in options if matches_conditions(block(o, "trigger"), facts)]
                self.assertEqual(len(shown), 3 if current and crisis else 1)
                if not (current and crisis):
                    self.assertTrue(scalar(shown[0], "name").endswith(".z"))
                    self.assertFalse(any(e.key.startswith(("add_", "remove_")) for e in shown[0]))

    def test_delivery_cancellation_and_replayed_callbacks_conserve_the_deposit(self):
        for route in ROUTES:
            decision = self.require(self.decisions, f"STP_pe_{route}_programme")
            for completes in (False, True):
                facts = self.facts(route)
                facts[("STP", "variable", "ADISCORD_economy_treasury")] = 900
                facts[("STP", "numeric", "has_political_power")] = 70
                start = block(decision, "complete_effect")
                self.apply_transaction(start, facts)
                self.apply_transaction(start, facts)
                self.assertEqual(facts[("STP", "variable", "ADISCORD_economy_treasury")], 450)
                self.assertEqual(facts[("STP", "numeric", "has_political_power")], 35)
                # A refund in a later accounting period is income, not negative costs.
                facts[("STP", "variable", "ADISCORD_economy_current_month_action_costs")] = 0
                if completes:
                    self.apply_transaction(block(decision, "remove_effect"), facts)
                else:
                    facts[("STP", "STP_pe_current", "yes")] = False
                    self.apply_transaction(block(decision, "cancel_effect"), facts)
                settled = dict(facts)
                self.apply_transaction(block(decision, "cancel_effect"), facts)
                self.apply_transaction(block(decision, "remove_effect"), facts)
                self.assertEqual(facts, settled)
                self.assertEqual(facts[("STP", "variable", "ADISCORD_economy_treasury")], 450 if completes else 900)
                self.assertEqual(facts.get(("STP", "variable", "ADISCORD_economy_current_month_action_income"), 0), 0 if completes else 450)
                self.assertEqual(facts[("STP", "variable", "ADISCORD_economy_current_month_action_costs")], 0)

    def test_concession_settlement_closes_a_running_commission_without_later_rewards(self):
        for index, route in enumerate(ROUTES):
            decision = self.require(self.decisions, f"STP_pe_{route}_programme")
            event = self.require(self.events, f"ADISCORD_STP_ch.{46 + index}")
            facts = self.facts(route)
            self.apply_transaction(block(decision, "complete_effect"), facts)
            facts[("STP", "has_idea", f"STP_pe_{route}_crisis")] = True
            option = next(e.value for e in event if e.key == "option"
                          and scalar(e.value, "name").endswith(".b"))
            self.apply_transaction([e for e in option if e.key not in ("name", "trigger", "ai_chance")], facts)
            self.assertEqual(facts[("STP", "variable", "ADISCORD_economy_treasury")], 450)
            self.assertTrue(matches_conditions(block(decision, "cancel_trigger"), facts))
            settled = dict(facts)
            self.apply_transaction(block(decision, "remove_effect"), facts)
            self.assertEqual(facts, settled)

    def test_new_focuses_and_events_have_complete_bilingual_localisation(self):
        for language in ("russian", "english"):
            raw = (ROOT / f"localisation/{language}/ADISCORD_STP_l_{language}.yml").read_bytes()
            self.assertTrue(raw.startswith(b"\xef\xbb\xbf"))
            loc = dict(re.findall(r'^\s+([\w.]+):\d*\s+"(.*)"$', raw.decode("utf-8-sig"), re.M))
            for name in self.focuses:
                if name.startswith("STP_pe_"):
                    self.assertIn(name, loc)
                    self.assertIn(name + "_desc", loc)
            for number in range(40, 58):
                event = self.require(self.events, f"ADISCORD_STP_ch.{number}")
                for entry in walk(event):
                    if entry.key in ("title", "desc", "text", "name") and isinstance(entry.value, str):
                        self.assertIn(entry.value, loc)


if __name__ == "__main__":
    unittest.main()
