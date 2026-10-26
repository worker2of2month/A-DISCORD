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
            # The fixture starts with an initialized treasury; native cache work is unmodelled.
            elif entry.key not in ("custom_effect_tooltip", "unlock_decision_tooltip", "ADISCORD_economy_mark_dirty",
                                   "ADISCORD_economy_initialize_country"):
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

    def test_club_social_cost_is_paid_only_at_policy_adoption_above_the_floor(self):
        reward = block(self.focuses["STP_pe_festival_policy_b"], "completion_reward")
        for level in range(1, 6):
            facts = {
                ("STP", "ADISCORD_social_system_development_at_least_2", "yes"): level >= 2,
            }
            selected = self.selected(reward, facts)
            payments = [e for e in selected
                        if e.key == "ADISCORD_decrease_social_system_development"]
            self.assertEqual(len(payments), int(level >= 2), level)
            self.assertTrue(any(e.key == "add_ideas"
                                and e.value == "STP_pe_festival_policy_b_idea"
                                for e in selected))
        ideas = parse_clausewitz(read("common/ideas/ADISCORD_STP_civil_war_ideas.txt"))
        self.assertFalse(any(e.key == "ADISCORD_decrease_social_system_development"
                             for e in walk(ideas)))
        for focus_id, focus in self.focuses.items():
            if focus_id != "STP_pe_festival_policy_b":
                self.assertFalse(any(e.key == "ADISCORD_decrease_social_system_development"
                                     for e in walk(block(focus, "completion_reward"))), focus_id)

    def test_all_endings_preserve_benefits_on_every_reachable_policy_and_course(self):
        ideas = {e.key: e.value for e in walk(parse_clausewitz(read(
            "common/ideas/ADISCORD_STP_civil_war_ideas.txt")))
            if e.key.startswith("STP_pe_") and isinstance(e.value, list)}

        def total(active):
            result = {}
            for name in active:
                for modifier in block(ideas[name], "modifier"):
                    result[modifier.key] = result.get(modifier.key, 0) + float(modifier.value)
            return result

        for route in ROUTES:
            for policy_side in ("a", "b"):
                for course_side in ("a", "b"):
                    if route == "festival" and policy_side != course_side:
                        continue
                    prefix = f"STP_pe_{route}_"
                    active = {prefix + f"policy_{policy_side}_idea",
                              prefix + f"course_{course_side}_idea"}
                    if policy_side == "b" and route in ("houses", "security"):
                        active.add(prefix + ("guarantors_idea" if route == "houses"
                                             else "inspectors_idea"))
                    reward = block(self.focuses[prefix + f"ending_{course_side}"],
                                   "completion_reward")
                    removed = {e.value for e in reward if e.key == "remove_ideas"}
                    added = {e.value for e in reward if e.key == "add_ideas"}
                    before = total(active)
                    after = total((active - removed) | added)
                    improved = False
                    for modifier in before.keys() | after.keys():
                        direction = -1 if modifier.endswith("_expense_factor") else 1
                        previous = before.get(modifier, 0) * direction
                        current = after.get(modifier, 0) * direction
                        with self.subTest(route=route, policy=policy_side,
                                          course=course_side, modifier=modifier):
                            if previous > 0:
                                self.assertGreaterEqual(current + 1e-9, previous)
                        improved |= current > max(0, previous) + 1e-9
                    with self.subTest(route=route, policy=policy_side, course=course_side):
                        self.assertTrue(improved)

    def test_inspector_recovery_books_the_full_treasury_receipt(self):
        facts = self.facts("security")
        facts[("STP", "variable", "ADISCORD_economy_treasury")] = 100
        facts[("STP", "variable", "ADISCORD_economy_current_month_action_income")] = 20
        self.apply_transaction(block(self.focuses["STP_pe_security_work_b"],
                                     "completion_reward"), facts)
        self.assertEqual(facts[("STP", "variable", "ADISCORD_economy_treasury")], 850)
        self.assertEqual(facts[("STP", "variable", "ADISCORD_economy_current_month_action_income")], 770)

    def test_accounting_offices_preview_matches_the_persistent_aggregate(self):
        reward = block(self.focuses["STP_pe_regent_work_a"], "completion_reward")
        applied = [e.value for e in walk(reward) if e.key == "add_to_variable"
                   and scalar(e.value, "var") == "STP_pw_ADISCORD_economy_admin_expense_factor"]
        self.assertEqual(len(applied), 1)
        ideas = {e.key: e.value for e in walk(parse_clausewitz(read(
            "common/ideas/ADISCORD_STP_civil_war_ideas.txt"))) if isinstance(e.value, list)}
        preview = block(ideas["STP_pe_regent_work_a_delta"], "modifier")
        self.assertEqual(scalar(preview, "ADISCORD_economy_admin_expense_factor"),
                         scalar(applied[0], "value"))
        self.assertFalse(any(e.key == "add_ideas" and e.value == "STP_pe_regent_work_a_delta"
                             for e in walk(reward)))
        dynamic = {e.key: e.value for e in parse_clausewitz(read(
            "common/dynamic_modifiers/ADISCORD_dynamic_modifiers_STP.txt"))}
        self.assertEqual(scalar(dynamic["STP_pw_party_dynamic"], "ADISCORD_economy_admin_expense_factor"),
                         "STP_pw_ADISCORD_economy_admin_expense_factor")

    def test_club_growth_penalty_runs_for_two_years_without_a_finale_reset(self):
        penalty = "STP_pe_festival_social_retrenchment"
        issued = []
        for focus_id, focus in self.focuses.items():
            for entry in walk(block(focus, "completion_reward")):
                if entry.key == "add_timed_idea" and scalar(entry.value, "idea") == penalty:
                    issued.append((focus_id, scalar(entry.value, "days")))
        self.assertEqual(issued, [("STP_pe_festival_policy_b", "730")])
        ideas = {e.key: e.value for e in walk(parse_clausewitz(read(
            "common/ideas/ADISCORD_STP_civil_war_ideas.txt")))
            if isinstance(e.value, list)}
        spirit = self.require(ideas, penalty)
        self.assertEqual(scalar(block(spirit, "modifier"),
                               "ADISCORD_country_development_social_system_growth_factor"), "-0.75")
        self.assertNotIn("cancel", {e.key for e in spirit})
        for hook in ("on_add", "on_remove"):
            self.assertEqual(scalar(block(spirit, hook), "ADISCORD_economy_mark_dirty"), "yes")
        for effects in self.effects.values():
            if isinstance(effects, list):
                self.assertFalse(any(e.key == "remove_ideas" and e.value == penalty
                                     for e in walk(effects)))

    def test_festival_field_equipment_is_delivered_even_without_a_road_site(self):
        reward = block(self.focuses["STP_pe_festival_work_a"], "completion_reward")
        equipment = {scalar(e.value, "type"): int(scalar(e.value, "amount"))
                     for e in reward if e.key == "add_equipment_to_stockpile"}
        self.assertGreaterEqual(equipment.get("motorized_equipment", 0), 200)
        self.assertGreaterEqual(equipment.get("support_equipment_1", 0), 120)
        self.assertGreaterEqual(float(scalar(reward, "add_stability") or 0), 0.03)

    def test_festival_lower_routes_follow_the_completed_practical_focus(self):
        for side in ("a", "b"):
            course = self.focuses[f"STP_pe_festival_course_{side}"]
            ending = self.focuses[f"STP_pe_festival_ending_{side}"]
            for focus in (course, ending):
                self.assertNotIn("mutually_exclusive", {e.key for e in focus})
            for selected_side in (None, "a", "b"):
                facts = {
                    ("STP", "has_completed_focus", f"STP_pe_festival_work_{candidate}"):
                    selected_side == candidate
                    for candidate in ("a", "b")
                }
                self.assertEqual(matches_conditions(block(course, "available"), facts),
                                 selected_side == side, (side, selected_side))

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
        def position(name):
            focus = focuses[name]
            x, y = int(scalar(focus, "x")), int(scalar(focus, "y"))
            anchors = [e.value for e in focus if e.key == "relative_position_id"]
            if anchors:
                ax, ay = position(anchors[0])
                x, y = x + ax, y + ay
            return x, y

        for leader, route in enumerate(ROUTES, 1):
            facts = self.facts(route)
            facts[("STP", "has_country_flag", "STP_cw_postwar")] = True
            facts[("STP", f"STP_party_leader_{leader}", "yes")] = True
            for phase in (1, 2, 3, 4):
                facts[("STP", "variable", "STP_ch_phase")] = phase
                visible = {}
                collisions = []
                for name, focus in focuses.items():
                    gates = [e.value for e in focus if e.key == "allow_branch"]
                    if all(matches_conditions(gate, facts) for gate in gates):
                        visible[name] = position(name)
                self.assertLessEqual(max(y for x, y in visible.values()), 18)
                for name, (x, y) in visible.items():
                    for other, (ox, oy) in visible.items():
                        if name != other and y == oy:
                            if abs(x - ox) < 2:
                                collisions.append((name, other, x, ox, y))
                self.assertEqual(collisions, [], f"Overlapping leader route {leader}, phase {phase}")

    def test_practical_programmes_do_not_delay_constitutional_laws(self):
        def ancestors(name):
            result = set()
            for entry in self.focuses[name]:
                if entry.key == "prerequisite":
                    for parent in entry.value:
                        if parent.value in self.focuses:
                            result.add(parent.value)
                            result.update(ancestors(parent.value))
            return result

        for route in ROUTES:
            prefix = f"STP_pe_{route}_"
            opening = self.focuses[prefix + "opening"]
            self.assertEqual(scalar(block(opening, "prerequisite"), "focus"),
                             "STP_pw_party_new_republic")
            for side in ("a", "b"):
                policy = self.focuses[prefix + "policy_" + side]
                self.assertLessEqual(7 * (float(scalar(opening, "cost")) +
                                         float(scalar(policy, "cost"))), 21)
                self.assertEqual(scalar(block(policy, "completion_reward"), "add_ideas"),
                                 prefix + "policy_" + side + "_idea")
                ending = self.focuses[prefix + "ending_" + side]
                groups = [e.value for e in ending if e.key == "prerequisite"]
                if route == "festival":
                    self.assertEqual([e.value for group in groups for e in group],
                                     [prefix + "course_" + side])
                    self.assertNotIn("available", {e.key for e in ending})
                    continue
                self.assertEqual(len(groups), 2)
                old_final = [e.value for group in groups for e in group
                             if not e.value.startswith("STP_pe_")][0]
                self.assertFalse(any(a.startswith("STP_pe_") for a in ancestors(old_final)))

    def test_focus_settlement_refunds_pending_payment_once(self):
        for route in ROUTES:
            facts = self.facts(route, receipt=True)
            facts[("STP", "numeric", "has_political_power")] = 0
            facts[("STP", "variable", "ADISCORD_economy_treasury")] = 0
            reward = block(self.focuses[f"STP_pe_{route}_settlement"], "completion_reward")
            self.apply_transaction(reward, facts)
            self.apply_transaction(reward, facts)
            self.apply_transaction(self.effects[f"STP_pe_{route}_settle"], facts)
            self.assertEqual(facts[("STP", "numeric", "has_political_power")], 35)
            self.assertEqual(facts[("STP", "variable", "ADISCORD_economy_treasury")], 450)
            self.assertTrue(facts[("STP", "has_country_flag", f"STP_pe_{route}_prepared")])
            bypass = block(self.focuses[f"STP_pe_{route}_settlement"], "bypass")
            self.assertTrue(matches_conditions(bypass, facts))

    def test_institutions_charge_once_and_deliver_without_future_requirements(self):
        for route in ROUTES:
            decision = self.require(self.decisions, f"STP_pe_{route}_followup")
            self.assertEqual(scalar(decision, "days_re_enable"), "30")
            self.assertFalse(any(e.key == "remove_effect" for e in decision))
            for upgraded in (False, True):
                facts = self.facts(route)
                facts[("STP", "has_completed_focus", f"STP_pe_{route}_next_day")] = True
                facts[("STP", "has_completed_focus", f"STP_pe_{route}_commission")] = upgraded
                self.assertTrue(matches_conditions(block(decision, "custom_cost_trigger"), facts))
                self.apply_transaction(block(decision, "complete_effect"), facts)
                self.assertEqual(facts[("STP", "numeric", "has_political_power")], 0)
                expected = (1000 if upgraded else 750) if route == "houses" else 0
                self.assertEqual(facts[("STP", "variable", "ADISCORD_economy_treasury")], expected)
                self.assertEqual(facts[("STP", "variable", "ADISCORD_economy_current_month_action_costs")], 450)
                previous = dict(facts)
                self.apply_transaction(block(decision, "complete_effect"), facts)
                self.assertEqual(facts, previous)

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
            loc = dict(re.findall(r'^[ \t]+([\w.]+):\d*[ \t]+"((?:[^"\\\r\n]|\\.)*)"[ \t]*\r?$', raw.decode("utf-8-sig"), re.M))
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
