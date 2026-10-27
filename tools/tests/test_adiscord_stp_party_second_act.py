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
            ("STP", f"STP_party_leader_{ROUTES.index(route) + 1}", "yes"): current,
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
            # The fixture starts with an initialized treasury; policy refreshes
            # and native cache work are outside these transaction scenarios.
            elif entry.key not in ("custom_effect_tooltip", "unlock_decision_tooltip", "ADISCORD_economy_mark_dirty",
                                   "ADISCORD_economy_initialize_country", "STP_party_refresh_policies"):
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

    def hedersett_facts(self):
        return {
            ("STP", "STP_pf_active", "yes"): True,
            ("STP", "STP_pf_settled", "yes"): True,
            ("STP", "STP_party_leader_2", "yes"): True,
            ("STP", "has_country_flag", "STP_cw_postwar"): True,
            ("STP", "has_idea", "STP_law_slavery"): True,
            ("STP", "has_idea", "STP_law_hard_drugs"): True,
            ("STP", "numeric", "has_political_power"): 200,
            ("STP", "variable", "ADISCORD_economy_treasury"): 1000,
        }

    def event_option(self, event, suffix):
        option = next(e.value for e in self.events[event]
                      if e.key == "option" and scalar(e.value, "name") == event + "." + suffix)
        return [e for e in option if e.key not in ("name", "trigger", "ai_chance")]

    def offered_options(self, event, facts):
        return [scalar(e.value, "name") for e in self.events[event]
                if e.key == "option" and matches_conditions(
                    next((child.value for child in e.value if child.key == "trigger"), []), facts)]

    def test_leader_crises_keep_material_choices_after_congress_and_decision_detours(self):
        decisions = {e.key: e.value for e in walk(parse_clausewitz(read(
            "common/decisions/ADISCORD_STP_decisions.txt"))) if isinstance(e.value, list)}
        cases = (
            (20, "property_disputes", "property_hearings", "b", "a", -50, -25,
             ("reward", "add_stability"), 0.03),
            (21, "officer_petitions", "officer_commission", "a", "b", -60, -20,
             ("variable", "STP_pw_army_org_regain"), 0.03),
            (22, "contract_disputes", "contract_arbitration", "b", "a", -60, -50,
             ("variable", "STP_pw_industrial_capacity_factory"), 0.03),
            (23, "archive_backlog", "detention_review", "a", "b", -50, -10,
             ("reward", "add_manpower"), 1500),
        )
        pp = ("STP", "numeric", "has_political_power")
        for number, crisis, decision, direct, detour, direct_cost, detour_cost, reward, amount in cases:
            with self.subTest(event=number):
                event = f"ADISCORD_STP_ch.{number}"
                idea = ("STP", "has_idea", "STP_party_" + crisis)
                start = self.hedersett_facts()
                start[idea] = True
                paid = dict(start)
                cheap = dict(start)
                self.apply_transaction(self.event_option(event, direct), paid)
                self.apply_transaction(self.event_option(event, detour), cheap)
                self.assertTrue(cheap[idea])
                cure = decisions["STP_party_" + decision]
                cheap[pp] -= float(scalar(cure, "cost"))
                self.apply_transaction(block(cure, "complete_effect"), cheap)
                self.assertEqual(paid[pp] - start[pp], direct_cost)
                self.assertEqual(cheap[pp] - start[pp], detour_cost)
                self.assertAlmostEqual(paid[("STP",) + reward], amount)
                self.assertEqual(cheap.get(("STP",) + reward, 0), 0)
                for outcome in (paid, cheap):
                    self.assertFalse(outcome[idea])
                    self.assertEqual(self.offered_options(event, outcome), [event + ".z"])
                    settled = dict(outcome)
                    self.apply_transaction(self.event_option(event, "z"), outcome)
                    self.assertEqual(outcome, settled)
                if number == 21:
                    self.assertAlmostEqual(paid[("STP", "variable", "STP_pw_ADISCORD_economy_admin_expense_factor")], 0.02)
                if number == 22:
                    self.assertEqual(cheap[("STP", "variable", "ADISCORD_economy_treasury")], 2000)
                    self.assertAlmostEqual(cheap[("STP", "variable", "STP_pw_ADISCORD_economy_overall_income_factor")], -0.02)

    def test_regent_local_offices_trade_cooperation_for_a_lasting_budget_result(self):
        event = "ADISCORD_STP_ch.24"
        joint = self.hedersett_facts()
        idea = ("STP", "has_idea", "STP_party_mandate_disputes")
        joint[idea] = True
        local = dict(joint)
        self.apply_transaction(self.event_option(event, "a"), joint)
        self.apply_transaction(self.event_option(event, "b"), local)
        self.assertEqual(joint[("STP", "variable", "STP_ch_cooperation")], 1)
        self.assertFalse(joint[idea])
        self.assertTrue(local[idea])
        self.assertEqual(local[("STP", "numeric", "has_political_power")], 165)
        self.assertAlmostEqual(local[("STP", "reward", "add_stability")], 0.03)
        admin = ("STP", "variable", "STP_pw_ADISCORD_economy_admin_expense_factor")
        self.assertAlmostEqual(local[admin], -0.04)
        decisions = {e.key: e.value for e in walk(parse_clausewitz(read(
            "common/decisions/ADISCORD_STP_decisions.txt"))) if isinstance(e.value, list)}
        audit = decisions["STP_party_mandate_audit"]
        local[("STP", "numeric", "has_political_power")] -= float(scalar(audit, "cost"))
        self.apply_transaction(block(audit, "complete_effect"), local)
        self.assertAlmostEqual(local[admin], -0.04)
        self.assertEqual(self.offered_options(event, local), [event + ".z"])

    def test_late_compromise_checks_both_prices_and_never_refunds_them(self):
        pp = ("STP", "numeric", "has_political_power")
        cash = ("STP", "variable", "ADISCORD_economy_treasury")
        costs = ("STP", "variable", "ADISCORD_economy_current_month_action_costs")
        for index, route in enumerate(ROUTES):
            if route == "festival":
                continue
            event = f"ADISCORD_STP_ch.{46 + index}"
            for balance, treasury, receipt in (
                (34.999, 300, False), (35, 299.999, False),
                (35, 300, False), (35, 0, True), (35, 450, True),
            ):
                facts = self.facts(route, receipt=receipt)
                facts[pp] = balance
                facts[cash] = treasury
                facts[("STP", "has_idea", f"STP_pe_{route}_crisis")] = True
                allowed = balance >= 35 and (treasury >= 300 or receipt)
                self.assertEqual(event + ".b" in self.offered_options(event, facts), allowed)
                before = dict(facts)
                self.apply_transaction(self.event_option(event, "b"), facts)
                if not allowed:
                    self.assertEqual(facts, before)
                    continue
                self.assertEqual(facts[pp], 0)
                self.assertEqual(facts[cash], treasury + (450 if receipt else 0) - 300)
                self.assertEqual(facts[costs], 300)
                settled = dict(facts)
                self.apply_transaction(self.event_option(event, "b"), facts)
                self.apply_transaction(self.effects[f"STP_pe_{route}_settle"], facts)
                self.assertEqual(facts, settled)
                # Both paid answers bypass settlement and receive the same next-day grant.
                next_day = self.focuses[f"STP_pe_{route}_next_day"]
                review = self.focuses[f"STP_pe_{route}_commission"]
                self.assertEqual(float(scalar(next_day, "cost")) + float(scalar(review, "cost")), 3)
                self.apply_transaction(block(next_day, "completion_reward"), facts)
                self.apply_transaction(block(review, "completion_reward"), facts)
                self.assertEqual(facts[pp], 0)
                self.assertEqual(facts[cash], settled[cash] + 450)
                self.assertEqual(facts[costs], 300)
                self.assertFalse(facts[("STP", "has_idea", f"STP_pe_{route}_backlash")])

    def test_shared_settlements_buy_institutions_after_support_freezes(self):
        for number, variable, amount in (
            (26, "STP_pw_production_speed_buildings_factor", 0.03),
            (27, "STP_pw_political_power_gain", 0.05),
        ):
            event = f"ADISCORD_STP_pc.{number}"
            for balance, charter in ((539.999, False), (540, False), (540, True)):
                facts = self.hedersett_facts()
                facts[("STP", "STP_pw_can_reconstruct", "yes")] = True
                facts[("STP", "has_completed_focus", "STP_pw_party_civil_charter")] = charter
                cash = ("STP", "variable", "ADISCORD_economy_treasury")
                facts[cash] = balance
                allowed = balance >= 540 and not charter
                self.assertEqual(event + ".b" in self.offered_options(event, facts), allowed)
                payload = self.event_option(event, "b")
                shown = self.selected(payload, facts)
                self.assertFalse(any(e.key == "custom_effect_tooltip" and e.value.endswith("_factions_tt")
                                     for e in shown))
                self.apply_transaction(payload, facts)
                self.assertEqual(facts[cash], balance - 540 if allowed else balance)
                self.assertAlmostEqual(facts.get(("STP", "variable", variable), 0), amount if allowed else 0)

    def test_late_penalties_use_weekly_cash_and_each_routes_own_expense_base(self):
        from tools.tests.test_adiscord_economy_weekly_contracts import (
            EconomyScriptFixture, MODIFIER_EFFECTS,
        )

        ideas = {e.key: e.value for e in walk(parse_clausewitz(read(
            "common/ideas/ADISCORD_STP_civil_war_ideas.txt"))) if isinstance(e.value, list)}
        prefix = "ADISCORD_economy_"

        def budget(income, army, modifiers):
            fixture = EconomyScriptFixture(texts=(MODIFIER_EFFECTS,))
            values = fixture.scopes["A"]
            for name in re.findall(r"\bADISCORD_\w+_factor_bp\b", MODIFIER_EFFECTS):
                values[name] = 100
            values[prefix + "monthly_income"] = income
            values[prefix + "army_expenses"] = army
            for name, delta in modifiers.items():
                if name.startswith(prefix):
                    suffix = name.removeprefix(prefix)
                    values[prefix + "final_" + suffix + "_bp"] += delta * 100
            fixture.run(prefix + "apply_overall_income_modifier_factor")
            fixture.run(prefix + "apply_expense_modifier_factors")
            fixture.run(prefix + "sum_expenses")
            fixture.run(prefix + "calculate_weekly_budget")
            return values[prefix + "weekly_balance"]

        for route in ("houses", "staff", "trade", "security", "regent"):
            backlash = {e.key: float(e.value) for e in block(ideas[f"STP_pe_{route}_backlash"], "modifier")}
            for side in ("a", "b"):
                policy = {e.key: float(e.value) for e in block(ideas[f"STP_pe_{route}_policy_{side}_idea"], "modifier")}
                combined = dict(policy)
                for name, delta in backlash.items():
                    combined[name] = combined.get(name, 0) + delta
                for income, army in ((50, 10), (150, 21.5), (500, 150)):
                    baseline = budget(income, army, policy)
                    weekly_loss = baseline - budget(income, army, combined)
                    expected = (income * -backlash.get(prefix + "overall_income_factor", 0)
                                + army * backlash.get(prefix + "army_expense_factor", 0)) * 3 / 13
                    self.assertAlmostEqual(weekly_loss, expected)
                    # Even three weekly ticks at the large benchmark do not price a 450-cash settlement.
                    self.assertLess(weekly_loss * 3, 450 * 0.05)
                    self.assertGreaterEqual(weekly_loss, 0)
            if route == "security":
                self.assertAlmostEqual(-backlash["political_power_gain"] * 21, 3.15)

    def test_ready_financing_is_displaced_only_when_political_power_is_binding(self):
        programmes = {e.key: e.value for e in walk(parse_clausewitz(read(
            "common/decisions/ADISCORD_STP_decisions.txt")))
            if e.key.startswith("STP_pw_prog_") and isinstance(e.value, list)}
        pp = ("STP", "numeric", "has_political_power")
        cash = ("STP", "variable", "ADISCORD_economy_treasury")
        for route, name, payout in (
            ("houses", "reconstruction_bonds", 1200),
            ("staff", "reconstruction_bonds", 1200),
            ("security", "reconstruction_bonds", 1200),
            ("trade", "export_quota", 1500),
            ("regent", "northern_credit", 1000),
        ):
            programme = programmes["STP_pw_prog_" + name]
            price = float(scalar(programme, "cost"))
            event = f"ADISCORD_STP_ch.{46 + ROUTES.index(route)}"
            for initial_pp in (35, 200):
                outcomes = {}
                for choice in ("a", "b"):
                    facts = self.facts(route)
                    facts[pp] = initial_pp
                    facts[cash] = 900
                    facts[("STP", "has_idea", f"STP_pe_{route}_crisis")] = True
                    self.apply_transaction(self.event_option(event, choice), facts)
                    if facts[pp] >= price:
                        facts[pp] -= price
                        self.apply_transaction(block(programme, "complete_effect"), facts)
                    outcomes[choice] = facts
                if initial_pp == 35:
                    self.assertEqual(outcomes["a"][cash] - outcomes["b"][cash], payout - 150)
                    self.assertGreaterEqual(outcomes["a"][pp], outcomes["b"][pp])
                else:
                    self.assertEqual(outcomes["b"][cash] - outcomes["a"][cash], 150)
                    self.assertEqual(outcomes["a"][pp] - outcomes["b"][pp], 35)

    def test_houses_followup_can_outweigh_concession_savings_with_bonds_on_cooldown(self):
        pp = ("STP", "numeric", "has_political_power")
        cash = ("STP", "variable", "ADISCORD_economy_treasury")
        outcomes = {}
        for choice in ("a", "b"):
            facts = self.facts("houses")
            facts[cash] = 900
            facts[("STP", "has_idea", "STP_pe_houses_crisis")] = True
            self.apply_transaction(self.event_option("ADISCORD_STP_ch.46", choice), facts)
            for suffix in ("next_day", "commission"):
                self.apply_transaction(block(self.focuses["STP_pe_houses_" + suffix], "completion_reward"), facts)
                facts[("STP", "has_completed_focus", "STP_pe_houses_" + suffix)] = True
            # External net gain of 0.5/day for a nominal 21-day focus route.
            facts[pp] += 10.5
            self.apply_transaction(block(self.decisions["STP_pe_houses_followup"], "complete_effect"), facts)
            outcomes[choice] = facts
        self.assertEqual(outcomes["a"][pp], outcomes["b"][pp])
        self.assertEqual(outcomes["a"][cash] - outcomes["b"][cash], 400)

    def test_cooldown_requires_reserving_power_at_every_programme_deadline(self):
        programmes = {e.key: e.value for e in walk(parse_clausewitz(read(
            "common/decisions/ADISCORD_STP_decisions.txt")))
            if e.key.startswith("STP_pw_prog_") and isinstance(e.value, list)}
        bond = programmes["STP_pw_prog_reconstruction_bonds"]
        price = float(scalar(bond, "cost"))
        cooldown = int(scalar(bond, "days_re_enable"))
        # A completed earlier issue leaves either 30 or 60 days of its native cooldown.
        for elapsed, expected_delay in ((60, 20), (30, 0)):
            remaining = cooldown - elapsed
            after_concession = 45 - 35 + remaining * 0.5
            delay = max(0, (price - after_concession) / 0.5)
            self.assertEqual(delay, expected_delay)
            self.assertGreaterEqual(45 + remaining * 0.5, price)
        # Reserve three monthly followups plus each leader's financing and staff training.
        for route in ("houses", "staff", "trade", "security", "regent"):
            schedule = [(21, 35), (51, 35), (81, 35), (60, price)]
            if route in ("trade", "regent", "staff"):
                name = {"trade": "export_quota", "regent": "northern_credit", "staff": "grand_manoeuvres"}[route]
                programme = programmes["STP_pw_prog_" + name]
                self.assertEqual(int(scalar(programme, "days_re_enable")), 120)
                schedule.append((90, float(scalar(programme, "cost"))))
            for choice_cost in (0, 35):
                reserve = 200 - choice_cost
                previous = 0
                for day, cost in sorted(schedule):
                    reserve += (day - previous) * 0.5
                    if route == "security" and choice_cost and previous == 0:
                        reserve -= 3.15
                    self.assertGreaterEqual(reserve, cost, (route, day, choice_cost))
                    reserve -= cost
                    previous = day

    def test_concessions_cross_real_project_cash_thresholds_when_financing_is_busy(self):
        decisions = {e.key: e.value for e in walk(parse_clausewitz(read(
            "common/decisions/ADISCORD_STP_decisions.txt"))) if isinstance(e.value, list)}
        for route, project, treasury in (
            ("houses", "STP_pi_house_road", 700),
            ("staff", "STP_pi_cadre_enrol", 750),
            ("trade", "STP_pi_trade_rifles_standard", 900),
            ("security", "STP_pi_case_orders_full", 750),
            ("regent", "STP_pi_north_local_staff", 750),
        ):
            event = f"ADISCORD_STP_ch.{46 + ROUTES.index(route)}"
            for choice in ("a", "b"):
                facts = self.facts(route)
                facts[("STP", "numeric", "has_political_power")] = 200
                facts[("STP", "numeric", "has_manpower")] = 6000
                facts[("STP", "variable", "ADISCORD_economy_treasury")] = treasury
                facts[("STP", "has_idea", f"STP_pe_{route}_crisis")] = True
                self.apply_transaction(self.event_option(event, choice), facts)
                # This isolates affordability; unlocks, free slots and local assets are separate requirements.
                gate = block(decisions[project], "custom_cost_trigger")
                self.assertEqual(matches_conditions(gate, facts), choice == "b", project)

    def test_ready_settlement_focus_preserves_both_currencies_without_concessions(self):
        for route in ("houses", "staff", "trade", "security", "regent"):
            facts = self.facts(route)
            facts[("STP", "has_idea", f"STP_pe_{route}_crisis")] = True
            event = f"ADISCORD_STP_ch.{46 + ROUTES.index(route)}"
            self.apply_transaction(self.event_option(event, "c"), facts)
            self.apply_transaction(block(self.focuses[f"STP_pe_{route}_settlement"], "completion_reward"), facts)
            self.assertEqual(facts[("STP", "numeric", "has_political_power")], 35)
            self.assertEqual(facts[("STP", "variable", "ADISCORD_economy_treasury")], 450)
            self.assertFalse(facts[("STP", "has_idea", f"STP_pe_{route}_crisis")])
            self.assertFalse(facts.get(("STP", "has_idea", f"STP_pe_{route}_backlash"), False))

    def test_leader_institution_previews_match_applied_aggregate_modifiers(self):
        ideas = {e.key: e.value for e in walk(parse_clausewitz(read(
            "common/ideas/ADISCORD_STP_civil_war_ideas.txt"))) if isinstance(e.value, list)}
        for namespace, number, choice in (("ch", 21, "a"), ("ch", 22, "b"),
                                          ("ch", 24, "b"), ("pc", 26, "b"), ("pc", 27, "b")):
            event = f"ADISCORD_STP_{namespace}.{number}"
            dummy = f"ADISCORD_STP_{namespace}_{number}_{choice}_delta"
            facts = self.hedersett_facts()
            facts[("STP", "STP_pw_can_reconstruct", "yes")] = True
            payload = self.event_option(event, choice)
            selected = self.selected(payload, facts)
            self.assertFalse(any(e.key in ("add_ideas", "swap_ideas") and
                                 (e.value == dummy or isinstance(e.value, list)) for e in selected))
            self.assertTrue(any(e.key == "STP_party_refresh_policies" for e in selected))
            applied = {scalar(e.value, "var"): float(scalar(e.value, "value"))
                       for e in selected if e.key == "add_to_variable"
                       and scalar(e.value, "var").startswith("STP_pw_")}
            preview = {"STP_pw_" + e.key: float(e.value) for e in block(ideas[dummy], "modifier")}
            self.assertEqual(preview, applied, dummy)

    def test_labour_registry_pays_off_in_the_delayed_report_after_elections(self):
        outcomes = {}
        for choice in ("a", "b"):
            facts = self.hedersett_facts()
            self.apply_transaction(self.event_option("ADISCORD_STP_ch.26", choice), facts)
            self.apply_transaction(block(self.events["ADISCORD_STP_ch.29"], "immediate"), facts)
            crisis = facts.get(("STP", "has_idea", "STP_party_forced_labour_resistance"), False)
            self.assertEqual(crisis, choice == "b")
            if choice == "a":
                self.assertEqual(self.offered_options("ADISCORD_STP_ch.29", facts),
                                 ["ADISCORD_STP_ch.29.resolved"])
                self.apply_transaction(self.event_option("ADISCORD_STP_ch.29", "resolved"), facts)
            else:
                self.apply_transaction(self.event_option("ADISCORD_STP_ch.29", "a"), facts)
            outcomes[choice] = facts
        cash = ("STP", "variable", "ADISCORD_economy_treasury")
        pp = ("STP", "numeric", "has_political_power")
        stability = ("STP", "reward", "add_stability")
        self.assertGreater(outcomes["b"][cash], outcomes["a"][cash])
        self.assertGreater(outcomes["a"][pp], outcomes["b"][pp])
        self.assertGreater(outcomes["a"][stability], outcomes["b"][stability])
        cleanup = self.effects["STP_pf_clear"]
        self.assertTrue(any(e.key == "clr_country_flag" and e.value == "STP_party_labour_registry"
                            for e in walk(cleanup)))

    def test_public_festival_choices_remain_distinct_after_faction_support_freezes(self):
        local = self.hedersett_facts()
        central = dict(local)
        self.apply_transaction(self.event_option("ADISCORD_STP_ch.25", "a"), local)
        self.apply_transaction(self.event_option("ADISCORD_STP_ch.25", "b"), central)
        self.assertGreater(local.get(("STP", "reward", "add_stability"), 0),
                           central.get(("STP", "reward", "add_stability"), 0))
        self.assertGreater(central[("STP", "numeric", "has_political_power")],
                           local[("STP", "numeric", "has_political_power")])
        admin = ("STP", "variable", "STP_pw_ADISCORD_economy_admin_expense_factor")
        self.assertGreater(central.get(admin, 0), local.get(admin, 0))

    def test_crisis_decisions_match_event_payments_and_make_open_reports_safe(self):
        decisions = {e.key: e.value for e in walk(parse_clausewitz(read(
            "common/decisions/ADISCORD_STP_decisions.txt")))
            if e.key in ("STP_party_health_commission", "STP_party_labour_inspections")}
        for number, decision, idea, law, close in (
            (28, "STP_party_health_commission", "STP_party_hospital_overload", "STP_law_hard_drugs", "funded"),
            (29, "STP_party_labour_inspections", "STP_party_forced_labour_resistance", "STP_law_slavery", "resolved"),
        ):
            event = f"ADISCORD_STP_ch.{number}"
            via_event = self.hedersett_facts()
            via_event[("STP", "has_idea", idea)] = True
            via_decision = dict(via_event)
            self.apply_transaction(self.event_option(event, "a"), via_event)
            via_decision[("STP", "numeric", "has_political_power")] -= float(scalar(decisions[decision], "cost"))
            self.apply_transaction(block(decisions[decision], "complete_effect"), via_decision)
            self.assertEqual(via_decision, via_event)
            self.assertEqual(self.offered_options(event, via_decision), [event + "." + close])
            before = dict(via_decision)
            self.apply_transaction(self.event_option(event, close), via_decision)
            self.assertEqual(via_decision, before)
            via_decision[("STP", "has_idea", law)] = False
            self.assertEqual(self.offered_options(event, via_decision), [event + ".obsolete"])

    def test_festival_accounts_preserve_a_material_choice_on_both_financing_routes(self):
        income = ("STP", "variable", "STP_pw_ADISCORD_economy_overall_income_factor")
        stability = ("STP", "reward", "add_stability")
        for route, concession in (("patrons", "a"), ("levy", "c")):
            start = self.hedersett_facts()
            start[("STP", "has_completed_focus", "STP_party_festival_" + route)] = True
            self.apply_transaction(block(self.focuses["STP_party_festival_" + route], "completion_reward"), start)
            self.apply_transaction(block(self.events["ADISCORD_STP_ch.30"], "immediate"), start)
            outcomes = {}
            for choice in (concession, "b"):
                facts = dict(start)
                self.apply_transaction(self.event_option("ADISCORD_STP_ch.30", choice), facts)
                outcomes[choice] = facts
            self.assertGreater(outcomes[concession].get(stability, 0), outcomes["b"].get(stability, 0))
            self.assertGreater(outcomes["b"][income], outcomes[concession][income])
            self.assertEqual(outcomes["b"][("STP", "numeric", "has_political_power")],
                             start[("STP", "numeric", "has_political_power")])
            self.assertEqual(outcomes["b"].get(("STP", "has_idea", "STP_party_festival_creditors"), False),
                             route == "patrons")

    def test_club_concessions_keep_their_price_after_the_commission_focus(self):
        for receipt in (False, True):
            facts = self.facts("festival", receipt=receipt)
            facts[("STP", "has_idea", "STP_pe_festival_crisis")] = True
            self.apply_transaction(self.event_option("ADISCORD_STP_ch.47", "b"), facts)
            cash_after = facts[("STP", "variable", "ADISCORD_economy_treasury")]
            self.assertEqual(cash_after, 900 if receipt else 450)
            self.assertFalse(facts[("STP", "has_variable", "STP_pe_festival_deposit")])
            self.assertTrue(facts[("STP", "has_country_flag", "STP_pe_festival_prepared")])
            self.assertLess(facts[("STP", "reward", "add_stability")], 0)
            penalty = facts[("STP", "reward", "add_stability")]
            self.apply_transaction(block(self.focuses["STP_pe_festival_commission"], "completion_reward"), facts)
            self.assertFalse(facts[("STP", "has_idea", "STP_pe_festival_backlash")])
            self.assertEqual(facts[("STP", "reward", "add_stability")], penalty)
            self.apply_transaction(self.effects["STP_pe_festival_settle"], facts)
            self.assertEqual(facts[("STP", "variable", "ADISCORD_economy_treasury")], cash_after)

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

    def test_early_programme_previews_match_applied_variables_and_native_readers(self):
        ideas = {e.key: e.value for e in walk(parse_clausewitz(read(
            "common/ideas/ADISCORD_STP_civil_war_ideas.txt"))) if isinstance(e.value, list)}
        dynamic = {e.key: e.value for e in parse_clausewitz(read(
            "common/dynamic_modifiers/ADISCORD_dynamic_modifiers_STP.txt"))}
        added_fields = {
            "houses_centralise": "ADISCORD_economy_creditworthiness_factor",
            "staff_commandants": "army_org_regain",
            "trade_tenders": "production_factory_efficiency_gain_factor",
            "trade_industry": "industrial_capacity_factory",
            "security_cadres": "ADISCORD_economy_admin_expense_factor",
            "regent_local_budget": "ADISCORD_economy_overall_income_factor",
            "regent_industry": "production_speed_industrial_complex_factor",
        }
        for suffix, new_field in added_fields.items():
            name = "STP_party_" + suffix
            reward = block(self.focuses[name], "completion_reward")
            applied = {}
            for entry in walk(reward):
                if entry.key == "add_to_variable":
                    variable = scalar(entry.value, "var")
                    if variable.startswith("STP_pw_"):
                        modifier = variable.removeprefix("STP_pw_")
                        applied[modifier] = applied.get(modifier, 0) + float(scalar(entry.value, "value"))
            preview = {e.key: float(e.value) for e in block(ideas[name + "_delta"], "modifier")}
            with self.subTest(focus=name):
                self.assertIn(new_field, applied)
                self.assertEqual(preview, applied)
                for modifier in applied:
                    for target in ("STP_pw_party_dynamic", "STP_pw_republic_dynamic"):
                        self.assertEqual(scalar(dynamic[target], modifier), "STP_pw_" + modifier)
                executable = []
                for entry in reward:
                    if entry.key != "effect_tooltip":
                        executable.append(entry)
                        if isinstance(entry.value, list):
                            executable.extend(walk(entry.value))
                self.assertFalse(any(e.key == "swap_ideas" for e in executable))

    def test_efficiency_growth_initializes_once_and_survives_refresh(self):
        variable = "STP_pw_production_factory_efficiency_gain_factor"
        for initialized in (False, True):
            facts = {
                ("STP", "STP_pw_can_reconstruct", "yes"): True,
                ("STP", "has_variable", variable): initialized,
            }
            selected = self.selected(self.effects["STP_pw_refresh_modifier"], facts)
            writes = [e for e in selected if e.key == "set_variable"
                      and scalar(e.value, "var") == variable]
            self.assertEqual(len(writes), int(not initialized))
            if writes:
                self.assertEqual(scalar(writes[0].value, "value"), "0")

    def test_finales_do_not_overwrite_early_programme_aggregate_variables(self):
        changed = ("houses_centralise", "staff_commandants", "trade_tenders", "trade_industry",
                   "security_cadres", "regent_local_budget", "regent_industry")
        protected = set()
        for suffix in changed:
            reward = block(self.focuses["STP_party_" + suffix], "completion_reward")
            protected.update(scalar(e.value, "var") for e in walk(reward)
                             if e.key == "add_to_variable"
                             and scalar(e.value, "var").startswith("STP_pw_"))
        facts = {("STP", "STP_pw_can_reconstruct", "yes"): True}
        facts.update({("STP", "has_variable", name): True for name in protected})
        roots = [self.effects["STP_pw_refresh_modifier"]]
        main_finals = ("STP_party_houses_compact", "STP_party_festival_charter",
                       "STP_party_service_constitution", "STP_party_trade_republic",
                       "STP_party_security_settlement", "STP_party_regent_settlement")
        late_finals = tuple(f"STP_pe_{route}_ending_{side}" for route in ROUTES for side in ("a", "b"))
        for name in main_finals + late_finals:
            roots.append(block(self.focuses[name], "completion_reward"))
        for root in roots:
            for entry in self.selected(root, facts):
                if entry.key in ("set_variable", "subtract_from_variable", "multiply_variable",
                                 "divide_variable", "clamp_variable", "add_to_variable"):
                    self.assertNotIn(scalar(entry.value, "var"), protected)
                elif entry.key == "clear_variable":
                    self.assertNotIn(entry.value, protected)
                elif entry.key == "remove_dynamic_modifier":
                    self.assertNotEqual(scalar(entry.value, "modifier"), "STP_pw_party_dynamic")

    def test_early_equipment_deliveries_are_visible_once_in_native_rewards(self):
        for name, expected in (
            ("STP_party_trade_industry", {"ADISCORD_infantry_equipment_2156": 2700}),
            ("STP_party_trade_imports", {"motorized_equipment": 150,
                                         "train_equipment": 10, "support_equipment_1": 150}),
        ):
            reward = block(self.focuses[name], "completion_reward")
            visible = [e for e in reward if e.key == "add_equipment_to_stockpile"]
            all_deliveries = [e for e in walk(reward) if e.key == "add_equipment_to_stockpile"]
            self.assertEqual(visible, all_deliveries)
            self.assertEqual(len(visible), len(expected))
            self.assertEqual({scalar(e.value, "type"): int(scalar(e.value, "amount"))
                              for e in visible}, expected)

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

    def test_paid_work_refunds_after_government_change_or_loss_of_regime(self):
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
            facts[("STP", "numeric", "has_political_power")] = 70
            self.apply_transaction(block(decision, "complete_effect"), facts)
            facts[("STP", "has_idea", f"STP_pe_{route}_crisis")] = True
            option = next(e.value for e in event if e.key == "option"
                          and scalar(e.value, "name").endswith(".b"))
            self.apply_transaction([e for e in option if e.key not in ("name", "trigger", "ai_chance")], facts)
            self.assertEqual(facts[("STP", "variable", "ADISCORD_economy_treasury")], 450 if route == "festival" else 150)
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



class PartyInstitutionContractTests(unittest.TestCase):
    def test_three_institutions_have_material_actions(self):
        decisions = {e.key: e.value for e in walk(parse_clausewitz(read(
            "common/decisions/ADISCORD_STP_decisions.txt")))
            if isinstance(e.value, list)}
        for name in (
            "STP_pi_house_road", "STP_pi_house_workshop", "STP_pi_house_buyout",
            "STP_pi_cadre_enrol", "STP_pi_cadre_instructors", "STP_pi_cadre_reserve",
            "STP_pi_cadre_mobilise", "STP_pi_artel_road", "STP_pi_artel_workshop",
            "STP_pi_north_training", "STP_pi_north_equipment", "STP_pi_north_industry",
            "STP_pi_north_delivery", "STP_pi_north_local_staff", "STP_pi_north_buyout",
        ):
            self.assertTrue(name in decisions, name)

    def test_mechanics_use_existing_focuses_without_erasing_rewards(self):
        source = parse_clausewitz(read("focus_trees/STP/postwar/party/focuses.txt"))
        focuses = {scalar(e.value, "id"): e.value for e in source if e.key == "focus"}
        expected = {
            "STP_party_houses_estates": "STP_pi_house_road",
            "STP_party_houses_audit": "STP_pi_house_road",
            "STP_ch_service_act": "STP_pi_cadre_enrol",
            "STP_party_staff_reserve_jobs": "STP_pi_artel_road",
            "STP_party_regent_mandate": "STP_pi_north_training",
            "STP_party_regent_schools": "STP_pi_north_local_staff",
            "STP_pe_staff_ending_a": "STP_pi_artel_workshop",
            "STP_pe_staff_ending_b": "STP_pi_cadre_rapid_mobilise",
        }
        for focus_id, decision_id in expected.items():
            self.assertTrue(any(e.key == "unlock_decision_tooltip" and e.value == decision_id
                                for e in walk(block(focuses[focus_id], "completion_reward"))), focus_id)
        for route in ("houses", "staff", "regent"):
            for side in ("a", "b"):
                reward = block(focuses[f"STP_pe_{route}_ending_{side}"], "completion_reward")
                self.assertTrue(any(e.key == "add_ideas" and e.value == f"STP_pe_{route}_ending_{side}_idea"
                                    for e in walk(reward)))
                self.assertFalse(any(e.key == "clear_variable" and e.value.startswith("STP_pi_")
                                     for e in walk(reward)))


class InstitutionScenario:
    """Execute bounded accounting branches; engine scheduling and UI are not simulated."""
    def __init__(self, effects, triggers, government=1):
        self.effects = effects
        self.triggers = triggers
        self.facts = {
            ("STP", "STP_pi_country_valid", "yes"): True,
            ("STP", "STP_pi_has_workshop_site", "yes"): True,
            ("NOD", "exists", "yes"): True,
            ("NOD", "has_capitulated", "no"): True,
            ("FROM", "is_owned_by", "ROOT"): True,
            ("FROM", "is_controlled_by", "ROOT"): True,
            ("FROM", "is_core_of", "STP"): True,
            ("FROM", "fixture_workshop_site", "yes"): True,
            ("FROM", "numeric", "infrastructure"): 2,
            ("STP", "numeric", "has_manpower"): 6000,
        }
        self.set_government(government)
        self.deliveries = []
        self.events = []
        self.temporary = {}
        self.put("ADISCORD_economy_treasury", 10000)
        self.put("ADISCORD_economy_treasury", 20000, "NOD")
        self.run(effects["STP_pi_initialize"])

    def set_government(self, government):
        for index in range(1, 7):
            self.facts[("STP", f"STP_party_leader_{index}", "yes")] = index == government
            self.facts[("STP", f"STP_party_leader_{index}", "no")] = index != government

    def put(self, name, value, scope="STP"):
        self.facts[(scope, "variable", name)] = value
        self.facts[(scope, "has_variable", name)] = True

    def get(self, name, scope="STP"):
        return self.facts.get((scope, "variable", name), 0)

    def number(self, value, scope):
        value = value.removeprefix("var:")
        try:
            return float(value)
        except ValueError:
            if "." in value:
                scope, value = value.split(".", 1)
                return self.get(value, scope)
            return self.temporary.get((scope, value), self.get(value, scope))

    def condition(self, entries, scope="STP"):
        from dataclasses import replace

        def expand(items):
            expanded = []
            for item in items:
                if item.key in self.triggers and item.key not in (
                    "STP_pi_country_valid", "STP_pi_has_workshop_site"
                ):
                    if item.value not in ("yes", "no"):
                        raise AssertionError("Scripted triggers require boolean calls")
                    conjunction = replace(item, key="AND", value=expand(self.triggers[item.key]))
                    expanded.append(conjunction if item.value == "yes" else
                                    replace(item, key="NOT", value=[conjunction]))
                elif item.key == "free_building_slots":
                    expanded.append(replace(item, key="fixture_workshop_site", value="yes"))
                elif isinstance(item.value, list):
                    expanded.append(replace(item, value=expand(item.value)))
                else:
                    expanded.append(item)
            return expanded

        # Explicit cross-country variable references are read in the source scope.
        for (owner, kind, name), value in list(self.facts.items()):
            if kind == "variable" and "." not in name:
                for target in ("STP", "NOD", "FROM"):
                    self.facts[(target, "variable", owner + "." + name)] = value
        return matches_conditions(expand(entries), self.facts, scope)

    def run(self, entries, scope="STP"):
        taken = False
        for entry in entries:
            key = entry.key
            if key == "effect_tooltip":
                continue
            if key in ("if", "else_if", "else"):
                if key == "if":
                    taken = False
                if not taken and (key == "else" or self.condition(block(entry.value, "limit"), scope)):
                    taken = True
                    self.run([e for e in entry.value if e.key != "limit"], scope)
            elif key == "hidden_effect":
                self.run(entry.value, scope)
            elif key in ("STP", "NOD", "FROM", "ROOT"):
                self.run(entry.value, "STP" if key == "ROOT" else key)
            elif key in self.effects and key.startswith("STP_pi_"):
                self.run(self.effects[key], scope)
            elif key in ("set_variable", "set_temp_variable", "add_to_variable", "subtract_from_variable",
                         "multiply_variable", "divide_variable", "multiply_temp_variable",
                         "subtract_from_temp_variable"):
                name = scalar(entry.value, "var")
                amount = self.number(scalar(entry.value, "value"), scope)
                temporary = "temp_variable" in key
                old = self.temporary.get((scope, name), 0) if temporary else self.get(name, scope)
                if key in ("set_variable", "set_temp_variable"):
                    result = amount
                elif key == "add_to_variable":
                    result = old + amount
                elif key in ("subtract_from_variable", "subtract_from_temp_variable"):
                    result = old - amount
                elif key in ("multiply_variable", "multiply_temp_variable"):
                    result = old * amount
                else:
                    result = old / amount
                if temporary:
                    self.temporary[(scope, name)] = result
                else:
                    self.put(name, result, scope)
            elif key == "clear_variable":
                self.facts[(scope, "has_variable", entry.value)] = False
                self.facts.pop((scope, "variable", entry.value), None)
            elif key in ("set_country_flag", "clr_country_flag", "set_state_flag", "clr_state_flag"):
                kind = "has_state_flag" if "state" in key else "has_country_flag"
                name = scalar(entry.value, "flag") if isinstance(entry.value, list) else entry.value
                self.facts[(scope, kind, name)] = key.startswith("set_")
            elif key == "add_manpower":
                fact = (scope, "numeric", "has_manpower")
                self.facts[fact] = self.facts.get(fact, 0) + self.number(entry.value, scope)
            elif key in ("add_equipment_to_stockpile", "add_building_construction",
                         "add_extra_state_shared_building_slots", "army_experience"):
                self.deliveries.append((scope, key, entry.value))
                if key == "add_equipment_to_stockpile":
                    name = "delivered_" + scalar(entry.value, "type")
                    self.put(name, self.get(name, scope) + self.number(scalar(entry.value, "amount"), scope), scope)
            elif key in ("add_stability", "add_political_power"):
                self.put(key, self.get(key, scope) + self.number(entry.value, scope), scope)
            elif key in ("remove_decision", "remove_mission"):
                self.facts[(scope, "has_decision", entry.value)] = False
                self.events.append((scope, key, entry.value))
            elif key == "activate_mission":
                self.facts[(scope, "has_decision", entry.value)] = True
                self.events.append((scope, key, entry.value))
            elif key in ("add_timed_idea", "remove_ideas"):
                name = scalar(entry.value, "idea") if key == "add_timed_idea" else entry.value
                self.facts[(scope, "has_idea", name)] = key == "add_timed_idea"
            elif key == "random_owned_controlled_state":
                self.run([e for e in entry.value if e.key != "limit"], "FROM")
            elif key == "country_event":
                self.events.append((scope, scalar(entry.value, "id")))
            elif key in ("custom_effect_tooltip", "STP_pw_refresh_modifier",
                         "ADISCORD_economy_mark_dirty"):
                pass
            else:
                raise AssertionError(f"Unhandled institution effect: {key}")


class PartyInstitutionAccountingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.effects = {e.key: e.value for e in parse_clausewitz(read(
            "common/scripted_effects/ADISCORD_STP_scripted_effects.txt"))}
        cls.triggers = {e.key: e.value for e in parse_clausewitz(read(
            "common/scripted_triggers/ADISCORD_STP_scripted_triggers.txt"))
            if e.key.startswith("STP_pi_")}
        cls.decisions = {e.key: e.value for e in walk(parse_clausewitz(read(
            "common/decisions/ADISCORD_STP_decisions.txt")))
            if e.key.startswith("STP_pi_") and isinstance(e.value, list)}

    def model(self, government=1):
        return InstitutionScenario(self.effects, self.triggers, government)

    def action(self, model, name, phase="complete_effect"):
        model.run(block(self.decisions[name], phase))

    def test_every_government_change_cancels_paid_work_without_double_refund(self):
        projects = (
            (1, "STP_pi_house_road", 400, "STP_pi_house_slots"),
            (2, "STP_pi_festival_public", 600, "STP_pi_festival_busy"),
            (3, "STP_pi_cadre_enrol", 450, None),
            (4, "STP_pi_trade_rifles_standard", 600, "STP_pi_trade_busy"),
            (5, "STP_pi_case_orders_full", 450, "STP_pi_case_busy"),
            (6, "STP_pi_north_local_staff", 450, None),
        )
        for previous, name, cost, slots in projects:
            for current in range(1, 7):
                if previous == current:
                    continue
                with self.subTest(previous=previous, current=current, project=name):
                    m = self.model(previous)
                    self.action(m, name)
                    self.assertEqual(m.get("ADISCORD_economy_treasury"), 10000 - cost)
                    m.set_government(current)
                    decision = self.decisions[name]
                    self.assertTrue(m.condition(block(decision, "cancel_trigger")))
                    self.assertFalse(m.condition(block(decision, "visible")))
                    # Completion may race native cancellation, but neither may deliver twice.
                    self.action(m, name, "remove_effect")
                    self.action(m, name, "cancel_effect")
                    self.action(m, name, "remove_effect")
                    self.action(m, name)
                    self.assertEqual(m.get("ADISCORD_economy_treasury"), 10000)
                    self.assertEqual(m.get("ADISCORD_economy_current_month_action_income"), cost)
                    self.assertEqual(m.deliveries, [])
                    self.assertEqual(m.facts[("STP", "numeric", "has_manpower")], 6000)
                    if slots:
                        self.assertEqual(m.get(slots), 0)

    def test_government_change_invalidates_northern_offer_and_refunds_both_payers(self):
        for successor in range(1, 6):
            for paid in (False, True):
                m = self.model(6)
                self.action(m, "STP_pi_north_training")
                if paid:
                    m.run(self.effects["STP_pi_north_accept"])
                    self.assertEqual(m.get("ADISCORD_economy_treasury"), 9700)
                    self.assertEqual(m.get("ADISCORD_economy_treasury", "NOD"), 19400)
                m.set_government(successor)
                self.assertFalse(m.condition(self.triggers["STP_pi_north_offer_valid"]))
                mission = "STP_pi_north_delivery" if paid else "STP_pi_north_reply"
                self.assertTrue(m.condition(block(self.decisions[mission], "cancel_trigger")))
                self.action(m, mission, "cancel_effect")
                m.run(self.effects["STP_pi_north_finish"])
                m.run(self.effects["STP_pi_north_accept"])
                self.assertEqual(m.get("ADISCORD_economy_treasury"), 10000)
                self.assertEqual(m.get("ADISCORD_economy_treasury", "NOD"), 20000)
                self.assertEqual(m.get("STP_pi_north_obligations"), 0)
                self.assertEqual(m.deliveries, [])

    def test_institution_bonuses_follow_current_government_without_erasing_ledgers(self):
        m = self.model(3)
        m.put("STP_pi_cadre_instructors", 4000)
        m.put("STP_pi_cadre_reserve", 2000)
        m.put("STP_pi_festival_districts", 2)
        m.put("STP_pi_festival_rate", 0.05)
        m.put("STP_pi_case_public", 2)
        m.put("STP_pi_public_rate", 0.01)
        m.put("STP_pw_army_org_factor", 0.15)
        for current in (3, 2, 5, 1, 6, 4, 3):
            m.set_government(current)
            for _ in range(2):
                m.run(self.effects["STP_pi_refresh"])
            self.assertAlmostEqual(m.get("STP_pw_army_org_factor"), 0.17 if current == 3 else 0.15)
            self.assertAlmostEqual(m.get("STP_pi_training_delta"), -0.1 if current == 3 else 0)
            self.assertAlmostEqual(m.get("STP_pi_social_delta"), 0.1 if current == 2 else 0)
            self.assertAlmostEqual(m.get("STP_pi_public_delta"), 0.02 if current == 5 else 0)
            self.assertEqual(m.get("STP_pi_cadre_instructors"), 4000)
            self.assertEqual(m.get("STP_pi_cadre_reserve"), 2000)
            self.assertEqual(m.get("STP_pi_festival_districts"), 2)
            self.assertEqual(m.get("STP_pi_case_public"), 2)

    def test_house_deposit_blocks_second_project_and_refunds_once(self):
        m = self.model(1)
        self.action(m, "STP_pi_house_road")
        self.assertEqual(m.get("ADISCORD_economy_treasury"), 9600)
        self.assertEqual(m.get("STP_pi_house_slots"), 1)
        self.action(m, "STP_pi_house_workshop")
        self.assertEqual(m.get("ADISCORD_economy_treasury"), 9600)
        m.facts[("FROM", "is_controlled_by", "ROOT")] = False
        self.action(m, "STP_pi_house_road", "remove_effect")
        self.action(m, "STP_pi_house_road", "cancel_effect")
        self.assertEqual(m.get("ADISCORD_economy_treasury"), 10000)
        self.assertEqual(m.get("STP_pi_house_slots"), 0)
        self.assertEqual(m.deliveries, [])

    def test_house_delivery_rechecks_site_and_retains_material_after_buyout(self):
        m = self.model(1)
        self.action(m, "STP_pi_house_workshop")
        m.facts[("FROM", "fixture_workshop_site", "yes")] = False
        self.action(m, "STP_pi_house_workshop", "remove_effect")
        self.assertEqual(m.get("ADISCORD_economy_treasury"), 10000)
        self.assertFalse(m.deliveries)
        m.facts[("FROM", "fixture_workshop_site", "yes")] = True
        self.action(m, "STP_pi_house_workshop")
        self.action(m, "STP_pi_house_workshop", "remove_effect")
        self.action(m, "STP_pi_house_workshop", "remove_effect")
        self.assertEqual(len(m.deliveries), 2)
        self.assertEqual(m.get("STP_pi_house_privileges"), 1)
        m.facts[("STP", "has_completed_focus", "STP_pe_houses_ending_a")] = True
        self.action(m, "STP_pi_house_buyout")
        self.assertEqual(m.get("ADISCORD_economy_treasury"), 8650)
        self.assertEqual(m.get("STP_pi_house_privileges"), 0)
        self.assertEqual(m.get("STP_pi_house_slots"), 0)
        self.assertEqual(len(m.deliveries), 2)

    def test_house_final_expands_capacity_without_resetting_existing_compacts(self):
        m = self.model(1)
        m.put("STP_pi_house_slots", 3)
        self.assertFalse(m.condition(self.triggers["STP_pi_house_capacity"]))
        m.facts[("STP", "has_completed_focus", "STP_pe_houses_ending_b")] = True
        self.assertTrue(m.condition(self.triggers["STP_pi_house_capacity"]))
        m.put("STP_pi_house_slots", 4)
        self.assertFalse(m.condition(self.triggers["STP_pi_house_capacity"]))

    def test_cadres_are_paid_once_with_exact_fractional_manpower_boundary(self):
        for manpower, paid in ((5999.9, False), (6000, True)):
            m = self.model(3)
            m.facts[("STP", "numeric", "has_manpower")] = manpower
            self.action(m, "STP_pi_cadre_enrol")
            self.assertEqual(m.get("STP_pi_cadre_deposit"), 450 if paid else 0)
            self.assertAlmostEqual(m.facts[("STP", "numeric", "has_manpower")], 0 if paid else manpower)
            if paid:
                self.action(m, "STP_pi_cadre_enrol")
                self.action(m, "STP_pi_cadre_enrol", "remove_effect")
                self.action(m, "STP_pi_cadre_enrol", "remove_effect")
                self.action(m, "STP_pi_cadre_enrol")
                self.assertEqual(m.get("STP_pi_cadre_free"), 6000)
                self.assertEqual(m.get("ADISCORD_economy_treasury"), 9550)

    def test_cadre_assignments_and_mobilisation_conserve_people(self):
        m = self.model(3)
        self.action(m, "STP_pi_cadre_enrol")
        self.action(m, "STP_pi_cadre_enrol", "remove_effect")
        self.action(m, "STP_pi_cadre_instructors")
        self.action(m, "STP_pi_cadre_reserve")
        self.action(m, "STP_pi_cadre_mobilise")
        self.action(m, "STP_pi_cadre_rapid_mobilise")
        self.assertEqual(m.get("STP_pi_mobilisation_people"), 2000)
        self.action(m, "STP_pi_cadre_mobilise", "remove_effect")
        self.action(m, "STP_pi_cadre_mobilise", "remove_effect")
        self.assertEqual(m.facts[("STP", "numeric", "has_manpower")], 2000)
        self.assertEqual(m.get("STP_pi_cadre_free") + m.get("STP_pi_cadre_instructors"), 4000)
        self.assertEqual(len(m.deliveries), 1)

    def test_artel_escrow_blocks_other_targets_and_refunds_people_and_money(self):
        m = self.model(3)
        m.put("STP_pi_cadre_free", 6000)
        self.action(m, "STP_pi_artel_road")
        self.assertEqual(m.get("STP_pi_cadre_free"), 4000)
        self.action(m, "STP_pi_artel_workshop")
        self.assertEqual(m.get("STP_pi_cadre_free"), 4000)
        m.facts[("FROM", "has_state_flag", "STP_pi_artel_pending")] = False
        self.action(m, "STP_pi_artel_workshop", "cancel_effect")
        self.assertEqual(m.get("STP_pi_artel_deposit"), 450)
        m.facts[("FROM", "has_state_flag", "STP_pi_artel_pending")] = True
        self.action(m, "STP_pi_artel_road", "cancel_effect")
        self.action(m, "STP_pi_artel_road", "cancel_effect")
        self.assertEqual(m.get("STP_pi_cadre_free"), 6000)
        self.assertEqual(m.get("ADISCORD_economy_treasury"), 10000)

    def test_northern_request_never_charges_before_consent(self):
        m = self.model(6)
        self.action(m, "STP_pi_north_training")
        self.action(m, "STP_pi_north_equipment")
        self.assertEqual(m.get("STP_pi_north_offer"), 1)
        self.assertEqual(m.get("ADISCORD_economy_treasury"), 10000)
        self.assertEqual(m.get("ADISCORD_economy_treasury", "NOD"), 20000)
        self.action(m, "STP_pi_north_reply", "timeout_effect")
        self.assertEqual(m.get("STP_pi_north_offer"), 0)
        self.assertEqual(m.get("STP_pi_north_obligations"), 0)
        m.run(self.effects["STP_pi_north_accept"])
        self.assertEqual(m.get("ADISCORD_economy_treasury"), 10000)

    def test_northern_consent_rechecks_both_prices_and_refunds_exact_receipts(self):
        for scope, amount in (("STP", 299.9), ("NOD", 599.9)):
            m = self.model(6)
            self.action(m, "STP_pi_north_training")
            m.put("ADISCORD_economy_treasury", amount, scope)
            m.run(self.effects["STP_pi_north_accept"])
            self.assertFalse(m.get("STP_pi_north_deposit"))
        m = self.model(6)
        self.action(m, "STP_pi_north_equipment")
        m.run(self.effects["STP_pi_north_accept"])
        m.run(self.effects["STP_pi_north_accept"])
        self.assertEqual(m.get("ADISCORD_economy_treasury"), 9400)
        self.assertEqual(m.get("ADISCORD_economy_treasury", "NOD"), 18800)
        m.facts[("STP", "has_war_with", "NOD")] = True
        m.run(self.effects["STP_pi_north_finish"])
        m.run(self.effects["STP_pi_north_refund"])
        self.assertEqual(m.get("ADISCORD_economy_treasury"), 10000)
        self.assertEqual(m.get("ADISCORD_economy_treasury", "NOD"), 20000)
        self.assertEqual(m.get("STP_pi_north_obligations"), 0)
        self.assertFalse(m.deliveries)

    def test_northern_final_and_buyout_keep_delivered_research(self):
        m = self.model(6)
        m.put("STP_pw_research_speed_factor", 0.12)
        self.action(m, "STP_pi_north_training")
        m.run(self.effects["STP_pi_north_accept"])
        m.run(self.effects["STP_pi_north_finish"])
        m.run(self.effects["STP_pi_north_finish"])
        self.assertAlmostEqual(m.get("STP_pw_research_speed_factor"), 0.15)
        self.assertEqual(m.get("STP_pi_north_obligations"), 1)
        m.run(self.effects["STP_pi_north_improve_terms"])
        self.assertAlmostEqual(m.get("STP_pw_ADISCORD_economy_overall_income_factor"), -0.01)
        m.facts[("STP", "has_completed_focus", "STP_pe_regent_ending_a")] = True
        self.action(m, "STP_pi_north_buyout")
        self.assertEqual(m.get("ADISCORD_economy_treasury"), 9250)
        self.assertEqual(m.get("STP_pi_north_obligations"), 0)
        self.assertAlmostEqual(m.get("STP_pw_research_speed_factor"), 0.15)
        self.assertAlmostEqual(m.get("STP_pw_planning_speed"), 0.05)

    def test_northern_settlement_removes_old_timers_before_another_offer(self):
        m = self.model(6)
        self.action(m, "STP_pi_north_training")
        self.assertTrue(m.facts[("STP", "has_decision", "STP_pi_north_reply")])
        m.run(self.effects["STP_pi_north_decline"])
        self.assertFalse(m.facts[("STP", "has_decision", "STP_pi_north_reply")])
        self.action(m, "STP_pi_north_equipment")
        m.run(self.effects["STP_pi_north_accept"])
        self.assertFalse(m.facts[("STP", "has_decision", "STP_pi_north_reply")])
        self.assertTrue(m.facts[("STP", "has_decision", "STP_pi_north_delivery")])
        m.run(self.effects["STP_pi_north_refund"])
        self.assertFalse(m.facts[("STP", "has_decision", "STP_pi_north_delivery")])
        self.action(m, "STP_pi_north_training")
        m.run(self.effects["STP_pi_north_accept"])
        m.run(self.effects["STP_pi_north_finish"])
        self.assertFalse(m.facts[("STP", "has_decision", "STP_pi_north_delivery")])

    def test_both_northern_finales_enable_specialist_replacement_without_schools(self):
        for side in ("a", "b"):
            with self.subTest(side=side):
                m = self.model(6)
                m.facts[("STP", "has_completed_focus", f"STP_pe_regent_ending_{side}")] = True
                m.facts[("STP", "has_completed_focus", "STP_party_regent_guarantees")] = True
                m.put("STP_pi_north_obligations", 3)
                m.put("STP_pi_north_specialists", 0)
                self.assertTrue(m.condition(block(self.decisions["STP_pi_north_local_staff"], "visible")))
                for _ in range(3):
                    self.action(m, "STP_pi_north_local_staff")
                    self.action(m, "STP_pi_north_local_staff", "remove_effect")
                    self.action(m, "STP_pi_north_buyout")
                self.assertEqual(m.get("STP_pi_north_obligations"), 0)
                self.assertEqual(m.get("STP_pi_north_specialists"), 0)

    def test_mobilisation_unlock_and_final_buyout_are_reachable(self):
        normal = block(self.decisions["STP_pi_cadre_mobilise"], "visible")
        self.assertTrue(any(e.key == "has_completed_focus" and e.value == "STP_ch_regular_service"
                            for e in walk(normal)))
        northern = block(self.decisions["STP_pi_north_buyout"], "visible")
        self.assertTrue(any(e.key == "has_completed_focus" and e.value == "STP_pe_regent_ending_a"
                            for e in walk(northern)))

    def test_new_decisions_explain_availability_without_technical_flags(self):
        for name, decision in self.decisions.items():
            if any(e.key == "days_mission_timeout" for e in decision):
                continue
            availability = block(decision, "available")
            self.assertEqual([e.key for e in availability], ["custom_trigger_tooltip"], name)

    def test_variable_manpower_uses_native_variable_reference(self):
        for name, effect in self.effects.items():
            if not name.startswith("STP_pi_"):
                continue
            for entry in walk(effect):
                if entry.key == "add_manpower" and not entry.value.lstrip("-").isdigit():
                    self.assertTrue(entry.value.startswith("var:"), (name, entry.value))

    def test_assignment_previews_equal_actual_aggregate_deltas(self):
        ideas = {e.key: e.value for e in walk(parse_clausewitz(read(
            "common/ideas/ADISCORD_STP_civil_war_ideas.txt")))
            if e.key.startswith("STP_pi_") and isinstance(e.value, list)}
        dynamics = {e.key: e.value for e in parse_clausewitz(read(
            "common/dynamic_modifiers/ADISCORD_dynamic_modifiers_STP.txt"))}
        consumers = {e.key: e.value for e in dynamics["STP_pw_party_dynamic"]}
        for role in ("instructors", "reserve"):
            m = self.model(3)
            m.put("STP_pi_cadre_free", 2000)
            self.action(m, "STP_pi_cadre_" + role)
            preview = block(ideas["STP_pi_cadre_" + role + "_delta"], "modifier")
            for modifier in preview:
                self.assertAlmostEqual(m.get(consumers[modifier.key]), float(modifier.value))
            self.assertEqual(m.get("STP_pi_cadre_free"), 0)

    def test_district_building_previews_match_delivered_buildings_and_slots(self):
        for name in ("STP_pi_house_road", "STP_pi_house_workshop",
                     "STP_pi_artel_road", "STP_pi_artel_workshop"):
            with self.subTest(decision=name):
                m = self.model(1 if name.startswith("STP_pi_house_") else 3)
                m.put("STP_pi_cadre_free", 2000)
                shown = block(block(self.decisions[name], "complete_effect"), "effect_tooltip")
                preview = [(e.key, tuple((x.key, x.value) for x in e.value)
                            if isinstance(e.value, list) else e.value)
                           for e in walk(shown)
                           if e.key in ("add_building_construction", "add_extra_state_shared_building_slots")]
                self.action(m, name)
                self.assertFalse(m.deliveries)
                self.action(m, name, "remove_effect")
                delivered = [(key, tuple((x.key, x.value) for x in value)
                              if isinstance(value, list) else value)
                             for _, key, value in m.deliveries]
                self.assertEqual(preview, delivered)
                self.assertTrue(preview)

    def test_supplier_expansion_preview_matches_delayed_permanent_delta(self):
        m = self.model(4)
        reward = block(self.decisions["STP_pi_trade_expand"], "complete_effect")
        preview = block(reward, "effect_tooltip")
        idea = scalar(preview, "add_ideas")
        ideas = {e.key: e.value for e in walk(parse_clausewitz(read(
            "common/ideas/ADISCORD_STP_civil_war_ideas.txt"))) if e.key == idea}
        self.action(m, "STP_pi_trade_expand")
        self.assertEqual(m.get("STP_pw_production_factory_max_efficiency_factor"), 0)
        self.action(m, "STP_pi_trade_expand", "remove_effect")
        for modifier in block(ideas[idea], "modifier"):
            self.assertAlmostEqual(m.get("STP_pw_" + modifier.key), float(modifier.value))

    def test_enrolment_cancel_restores_real_people_and_exact_money_once(self):
        m = self.model(3)
        self.action(m, "STP_pi_cadre_enrol")
        self.action(m, "STP_pi_cadre_enrol", "cancel_effect")
        self.action(m, "STP_pi_cadre_enrol", "remove_effect")
        self.assertEqual(m.facts[("STP", "numeric", "has_manpower")], 6000)
        self.assertEqual(m.get("ADISCORD_economy_treasury"), 10000)
        self.assertEqual(m.get("STP_pi_cadre_free"), 0)

    def test_northern_factory_rechecks_site_and_equipment_delivers_only_once(self):
        m = self.model(6)
        self.action(m, "STP_pi_north_industry")
        m.run(self.effects["STP_pi_north_accept"])
        m.facts[("STP", "STP_pi_has_workshop_site", "yes")] = False
        m.run(self.effects["STP_pi_north_finish"])
        self.assertEqual(m.get("ADISCORD_economy_treasury"), 10000)
        self.assertEqual(m.get("ADISCORD_economy_treasury", "NOD"), 20000)
        self.assertFalse(m.deliveries)
        self.action(m, "STP_pi_north_equipment")
        m.run(self.effects["STP_pi_north_accept"])
        m.run(self.effects["STP_pi_north_finish"])
        m.run(self.effects["STP_pi_north_finish"])
        equipment = {scalar(body, "type"): int(scalar(body, "amount"))
                     for _, key, body in m.deliveries if key == "add_equipment_to_stockpile"}
        self.assertEqual(equipment, {"ADISCORD_infantry_equipment_2156": 9000, "support_equipment_1": 180})
        self.assertEqual(len(m.deliveries), 2)
        self.assertEqual(m.get("STP_pi_north_obligations"), 1)

    def test_northern_event_timeout_declines_and_missions_cannot_auto_succeed(self):
        events = {scalar(e.value, "id"): e.value for e in parse_clausewitz(read(
            "events/ADISCORD_STP_events.txt")) if e.key == "country_event"}
        offer = events["ADISCORD_STP_pi.1"]
        self.assertEqual(scalar(offer, "timeout_days"), "14")
        options = [e.value for e in offer if e.key == "option"]
        self.assertEqual(scalar(options[0], "name"), "ADISCORD_STP_pi.1.no")
        self.assertFalse(any(e.key == "trigger" for e in options[0]))
        self.assertTrue(any(e.key == "STP_pi_north_decline" for e in walk(options[0])))
        for name in ("STP_pi_north_reply", "STP_pi_north_delivery"):
            self.assertFalse(self.model(6).condition(block(self.decisions[name], "available")))
        self.assertGreater(int(scalar(self.decisions["STP_pi_north_reply"], "days_mission_timeout")), 15)

    def test_all_new_costs_and_visible_text_have_complete_bilingual_values(self):
        keys = set()
        for name, decision in self.decisions.items():
            keys.update((name, name + "_desc"))
            for entry in walk(decision):
                if entry.key in ("tooltip", "custom_effect_tooltip"):
                    keys.add(entry.value)
                elif entry.key == "custom_cost_text":
                    keys.update((entry.value, entry.value + "_blocked", entry.value + "_tooltip"))
        for language in ("russian", "english"):
            path = ROOT / f"localisation/{language}/ADISCORD_STP_l_{language}.yml"
            self.assertTrue(path.read_bytes().startswith(b"\xef\xbb\xbf"))
            values = dict(re.findall(r'^\s*([^ :]+):\d*\s*"([^"\r\n]*)"\s*$',
                                     path.read_text(encoding="utf-8-sig"), re.MULTILINE))
            self.assertFalse(keys - values.keys(), sorted(keys - values.keys()))

    def test_refresh_is_idempotent_and_preserves_other_focus_rewards(self):
        m = self.model(3)
        m.put("STP_pw_ADISCORD_economy_overall_income_factor", 0.4)
        m.put("STP_pw_army_org_factor", 0.15)
        m.put("STP_pw_training_time_factor", -0.1)
        m.put("STP_pi_house_privileges", 2)
        m.put("STP_pi_cadre_instructors", 4000)
        m.put("STP_pi_cadre_reserve", 2000)
        m.put("STP_pi_north_obligations", 1)
        for _ in range(5):
            m.run(self.effects["STP_pi_refresh"])
        self.assertAlmostEqual(m.get("STP_pw_ADISCORD_economy_overall_income_factor"), 0.34)
        self.assertAlmostEqual(m.get("STP_pw_army_org_factor"), 0.17)
        self.assertAlmostEqual(m.get("STP_pw_training_time_factor"), -0.2)
        self.assertAlmostEqual(m.get("STP_pw_ADISCORD_economy_admin_expense_factor"), 0.03)
        # An intervening focus adds its own reward; reconciliation must retain it.
        m.put("STP_pw_army_org_factor", m.get("STP_pw_army_org_factor") + 0.075)
        m.run(self.effects["STP_pi_refresh"])
        self.assertAlmostEqual(m.get("STP_pw_army_org_factor"), 0.245)

class PartyRemainingInstitutionContracts(unittest.TestCase):
    def test_institution_descriptions_leave_numbers_to_effect_previews(self):
        decisions = {e.key: e.value for e in walk(parse_clausewitz(read(
            "common/decisions/ADISCORD_STP_decisions.txt")))
            if e.key.startswith("STP_pi_") and isinstance(e.value, list)}
        for lang in ("russian", "english"):
            values = dict(re.findall(r'^ ([^:]+):\d* "([^"\r\n]*)"$',
                                     read(f"localisation/{lang}/ADISCORD_STP_l_{lang}.yml"), re.M))
            for name, decision in decisions.items():
                with self.subTest(language=lang, decision=name):
                    self.assertFalse(re.search(r'\d|%|\[\?', values[name + "_desc"]))
                    if any(e.key == "days_mission_timeout" for e in decision):
                        continue
                    self.assertTrue(any(e.key in ("effect_tooltip", "custom_effect_tooltip")
                                        for e in block(decision, "complete_effect")), name)

    def test_calendar_portfolio_and_cases_are_playable(self):
        entries = {e.key for e in walk(parse_clausewitz(read(
            "common/decisions/ADISCORD_STP_decisions.txt")))}
        for name in ("STP_pi_festival_public", "STP_pi_festival_club", "STP_pi_festival_medical",
                     "STP_pi_trade_rifles_standard", "STP_pi_trade_support_rush", "STP_pi_trade_trucks_series",
                     "STP_pi_trade_expand", "STP_pi_case_orders_full", "STP_pi_case_supply_quick",
                     "STP_pi_case_property_public", "STP_pi_case_orders_seal", "STP_pi_case_leverage"):
            self.assertTrue(name in entries, name)

    def test_new_endings_develop_mechanics_without_erasing_their_spirits(self):
        focuses = {scalar(e.value, "id"): e.value for e in parse_clausewitz(read(
            "focus_trees/STP/postwar/party/focuses.txt")) if e.key == "focus"}
        for route in ("festival", "trade", "security"):
            for side in ("a", "b"):
                name = f"STP_pe_{route}_ending_{side}"
                reward = block(focuses[name], "completion_reward")
                self.assertTrue(any(e.key == "custom_effect_tooltip" and e.value == name + "_mechanic_tt"
                                    for e in walk(reward)), name)
                self.assertTrue(any(e.key == "add_ideas" and e.value == name + "_idea"
                                    for e in walk(reward)), name)


class PartyRemainingInstitutionAccountingTests(unittest.TestCase):
    """Finite cases, delivery quotes and cumulative results across finale upgrades."""

    @classmethod
    def setUpClass(cls):
        PartyInstitutionAccountingTests.setUpClass.__func__(cls)

    model = PartyInstitutionAccountingTests.model
    action = PartyInstitutionAccountingTests.action

    def test_all_twelve_finales_preserve_institution_ledgers_and_improve_only_their_share(self):
        focuses = {scalar(e.value, "id"): e.value for e in parse_clausewitz(read(
            "focus_trees/STP/postwar/party/focuses.txt")) if e.key == "focus"}
        retained = {
            "house_slots": 3, "house_privileges": 3,
            "cadre_free": 2000, "cadre_instructors": 2000, "cadre_reserve": 2000,
            "artel_deposit": 900, "artel_people": 2000,
            "north_obligations": 2, "north_specialists": 1,
            "north_deposit": 600, "north_donor_deposit": 1200, "north_kind": 2,
            "festival_districts": 4, "festival_busy": 1,
            "festival_load": 3, "festival_pending_clubs": 1, "festival_reserved": 4,
            "trade_level": 3, "trade_busy": 1,
            "trade_rifles_deposit": 1200, "trade_rifles_quote": 48600,
            "case_public": 2, "case_sealed": 1, "case_credited": 1,
            "case_orders_stage": 2, "case_supply_stage": 2, "case_property_stage": 3,
        }
        aggregates = ("ADISCORD_economy_overall_income_factor", "ADISCORD_economy_admin_expense_factor",
                      "training_time_factor", "army_org_factor", "army_org_regain", "stability_factor",
                      "ADISCORD_country_development_social_system_growth_factor")
        for route in ROUTES:
            for side in ("a", "b"):
                with self.subTest(route=route, finale=side):
                    m = self.model(ROUTES.index(route) + 1)
                    for key, value in retained.items():
                        m.put("STP_pi_" + key, value)
                    for key in aggregates:
                        m.put("STP_pw_" + key, 0.1)
                    m.run(self.effects["STP_pi_refresh"])
                    before = {key: m.get("STP_pw_" + key) for key in aggregates}
                    reward = block(focuses[f"STP_pe_{route}_ending_{side}"], "completion_reward")
                    # Execute the institution portion; native spirits are checked separately.
                    for _, effect in selected_effects(reward, m.facts):
                        if effect.key.startswith("STP_pi_"):
                            m.run([effect])
                        elif effect.key == "set_variable" and scalar(effect.value, "var").startswith("STP_pi_"):
                            m.run([effect])
                    for _ in range(3):
                        m.run(self.effects["STP_pi_refresh"])
                        m.run(self.effects["STP_pi_case_credit"])
                    for key, value in retained.items():
                        if key == "case_credited" and route == "security" and side == "b":
                            self.assertEqual(m.get("STP_pi_" + key), 2)
                        else:
                            self.assertEqual(m.get("STP_pi_" + key), value, key)
                    for key, value in before.items():
                        direction = -1 if key in ("training_time_factor", "ADISCORD_economy_admin_expense_factor") else 1
                        self.assertGreaterEqual(direction * m.get("STP_pw_" + key) + 1e-9, direction * value, key)
                    if route == "festival" and side == "a":
                        self.assertAlmostEqual(m.get("STP_pw_ADISCORD_country_development_social_system_growth_factor"), 0.4)
                    if route == "security" and side == "a":
                        self.assertAlmostEqual(m.get("STP_pw_stability_factor"), 0.12)
                    if route == "security" and side == "b":
                        self.assertEqual(m.get("STP_pi_case_credits"), 1)
                    if route == "regent" and side == "b":
                        self.assertAlmostEqual(m.get("STP_pw_ADISCORD_economy_overall_income_factor"), 0.02)

    def test_northern_equipment_offer_and_summary_match_delivery(self):
        m = self.model(6)
        self.action(m, "STP_pi_north_equipment")
        m.run(self.effects["STP_pi_north_accept"])
        m.run(self.effects["STP_pi_north_finish"])
        rifles = int(m.get("delivered_ADISCORD_infantry_equipment_2156"))
        support = int(m.get("delivered_support_equipment_1"))
        for lang in ("russian", "english"):
            values = dict(re.findall(r'^ ([^:]+):\d* "([^"\r\n]*)"$',
                                     read(f"localisation/{lang}/ADISCORD_STP_l_{lang}.yml"), re.M))
            for key in ("STP_pi_north_equipment_package_tt", "STP_pi_package_equipment", "ADISCORD_STP_pi.1.d_equipment"):
                rendered = re.sub(r'§[A-Za-z!]', '', values[key])
                self.assertRegex(rendered, rf'\b{rifles}\b', key)
                self.assertRegex(rendered, rf'\b{support}\b', key)

    def complete_focus(self, model, name):
        model.facts[("STP", "has_completed_focus", name)] = True

    def rest_district(self, model):
        # Advance the fixture past the native 90-day state cooldown.
        model.facts[("FROM", "has_state_flag", "STP_pi_festival_rest")] = False

    def fresh_festival_district(self, model):
        model.facts = {key: value for key, value in model.facts.items() if key[0] != "FROM"}
        model.facts.update({key: value for key, value in self.model(2).facts.items() if key[0] == "FROM"})

    def test_festival_payment_visibility_and_slot_release(self):
        names = ("STP_pi_festival_public", "STP_pi_festival_club")
        for chosen in names:
            for ending in ("remove_effect", "cancel_effect"):
                with self.subTest(chosen=chosen, ending=ending):
                    m = self.model(2)
                    self.complete_focus(m, "STP_pw_party_unbound_revolution")
                    m.put("ADISCORD_economy_treasury", 599.99)
                    cost = block(self.decisions[chosen], "custom_cost_trigger")
                    self.assertFalse(m.condition(cost))
                    self.assertFalse(m.condition(block(self.decisions[chosen], "visible")))
                    self.action(m, chosen)
                    self.assertEqual(m.get("ADISCORD_economy_treasury"), 599.99)
                    self.assertEqual(m.get("STP_pi_festival_busy"), 0)
                    m.put("ADISCORD_economy_treasury", 600)
                    self.assertTrue(m.condition(cost))
                    self.assertTrue(m.condition(block(self.decisions[chosen], "visible")))
                    self.action(m, chosen)
                    self.assertEqual(m.get("ADISCORD_economy_treasury"), 0)
                    self.assertEqual(m.get("STP_pi_festival_busy"), 1)
                    for name in names:
                        self.assertEqual(m.condition(block(self.decisions[name], "visible")), name == chosen)
                    # The same country counter governs targets without a paid receipt.
                    receipt = {key: value for key, value in m.facts.items() if key[0] == "FROM"}
                    self.fresh_festival_district(m)
                    for name in names:
                        self.assertFalse(m.condition(block(self.decisions[name], "visible")))
                    self.complete_focus(m, "STP_pe_festival_work_a")
                    for name in names:
                        self.assertFalse(m.condition(block(self.decisions[name], "visible")))
                    m.put("ADISCORD_economy_treasury", 600)
                    for name in names:
                        self.assertTrue(m.condition(block(self.decisions[name], "visible")))
                    m.put("ADISCORD_economy_treasury", 0)
                    self.fresh_festival_district(m)
                    m.facts.update(receipt)
                    self.action(m, chosen, ending)
                    self.assertEqual(m.get("STP_pi_festival_busy"), 0)
                    expected = 600 if ending == "cancel_effect" else (1500 if chosen.endswith("club") else 0)
                    self.assertEqual(m.get("ADISCORD_economy_treasury"), expected)
                    self.action(m, chosen, ending)
                    self.assertEqual(m.get("ADISCORD_economy_treasury"), expected)
                    self.rest_district(m)
                    m.put("ADISCORD_economy_treasury", 10000)
                    for name in names:
                        self.assertEqual(m.condition(block(self.decisions[name], "visible")),
                                         ending == "cancel_effect" or name != chosen)

    def test_public_visit_cannot_be_repeated_after_cooldown(self):
        m = self.model(2)
        for _ in range(4):
            self.rest_district(m)
            self.action(m, "STP_pi_festival_public")
            self.action(m, "STP_pi_festival_public", "remove_effect")
            self.assertAlmostEqual(m.get("add_stability"), 0.03)
            self.assertEqual(m.get("STP_pi_festival_districts"), 1)
            self.assertEqual(m.get("STP_pi_festival_busy"), 0)
            self.assertEqual(m.get("ADISCORD_economy_treasury"), 9400)
            self.assertEqual(m.get("STP_pi_festival_public_visits", "FROM"), 1)
        self.assertAlmostEqual(m.get("STP_pw_ADISCORD_country_development_social_system_growth_factor"), 0.05)
        m.put("STP_pi_festival_rate", 0.075)
        for _ in range(3):
            m.run(self.effects["STP_pi_refresh"])
        self.assertAlmostEqual(m.get("STP_pw_ADISCORD_country_development_social_system_growth_factor"), 0.075)

    def test_lost_district_refunds_once_and_frees_booking_and_load(self):
        m = self.model(2)
        self.action(m, "STP_pi_festival_club")
        self.assertEqual(m.get("ADISCORD_economy_treasury"), 9400)
        self.assertEqual(m.get("STP_pi_festival_reserved"), 1)
        m.facts[("FROM", "is_owned_by", "ROOT")] = False
        self.action(m, "STP_pi_festival_club", "remove_effect")
        self.action(m, "STP_pi_festival_club", "cancel_effect")
        self.assertEqual(m.get("ADISCORD_economy_treasury"), 10000)
        for name in ("busy", "reserved", "pending_clubs", "load"):
            self.assertEqual(m.get("STP_pi_festival_" + name), 0)

    def test_club_load_costs_and_clinics_leave_cadre_and_focus_bonuses(self):
        m = self.model(2)
        m.put("STP_pw_ADISCORD_economy_admin_expense_factor", -0.1)
        m.put("STP_pi_cadre_instructors", 2000)
        for _ in range(4):
            self.fresh_festival_district(m)
            self.action(m, "STP_pi_festival_club")
            self.action(m, "STP_pi_festival_club", "remove_effect")
        self.assertEqual(m.get("STP_pi_festival_load"), 4)
        self.assertEqual(m.get("STP_pi_festival_reserved"), 4)
        self.assertAlmostEqual(m.get("STP_pw_ADISCORD_economy_admin_expense_factor"), -0.05)
        m.put("STP_pi_festival_safe", 4)
        for _ in range(3):
            m.run(self.effects["STP_pi_refresh"])
        self.assertAlmostEqual(m.get("STP_pw_ADISCORD_economy_admin_expense_factor"), -0.09)
        self.action(m, "STP_pi_festival_medical")
        self.action(m, "STP_pi_festival_medical", "remove_effect")
        self.assertEqual(m.get("STP_pi_festival_load"), 2)
        self.assertEqual(m.get("STP_pi_festival_reserved"), 2)

    def test_club_final_keeps_paid_quote_and_increases_next_quote(self):
        m = self.model(2)
        self.action(m, "STP_pi_festival_club")
        self.complete_focus(m, "STP_pe_festival_ending_b")
        self.action(m, "STP_pi_festival_club", "remove_effect")
        self.assertEqual(m.get("ADISCORD_economy_treasury"), 10900)
        self.rest_district(m)
        self.action(m, "STP_pi_festival_club")
        self.assertEqual(m.get("ADISCORD_economy_treasury"), 10900)
        self.assertEqual(m.get("STP_pi_festival_quote", "FROM"), 0)
        self.fresh_festival_district(m)
        self.action(m, "STP_pi_festival_club")
        self.assertEqual(m.get("STP_pi_festival_quote", "FROM"), 2250)

    def test_paid_club_reserves_last_load_slot(self):
        m = self.model(2)
        m.put("STP_pi_festival_reserved", 5)
        m.put("STP_pi_festival_load", 5)
        self.action(m, "STP_pi_festival_club")
        self.assertEqual(m.get("STP_pi_festival_reserved"), 6)
        self.assertFalse(m.condition(self.triggers["STP_pi_festival_club_capacity"]))
        self.action(m, "STP_pi_festival_club", "cancel_effect")
        self.assertEqual(m.get("STP_pi_festival_reserved"), 5)

    def test_festival_visibility_checks_local_access_and_load_but_keeps_paid_work(self):
        for name in ("STP_pi_festival_public", "STP_pi_festival_club"):
            for reason in ("ownership", "control", "rest", "brigades", "load"):
                with self.subTest(decision=name, reason=reason):
                    m = self.model(2)
                    self.complete_focus(m, "STP_pw_party_unbound_revolution")
                    visible = block(self.decisions[name], "visible")
                    self.assertTrue(m.condition(visible))
                    if reason == "ownership":
                        m.facts[("FROM", "is_owned_by", "ROOT")] = False
                    elif reason == "control":
                        m.facts[("FROM", "is_controlled_by", "ROOT")] = False
                    elif reason == "rest":
                        m.facts[("FROM", "has_state_flag", "STP_pi_festival_rest")] = True
                    elif reason == "brigades":
                        m.put("STP_pi_festival_busy", 1)
                    else:
                        m.put("STP_pi_festival_reserved", 6)
                    self.assertEqual(m.condition(visible), reason == "load" and name.endswith("public"))
                    m.put("STP_pi_festival_deposit", 600, "FROM")
                    m.put("STP_pi_festival_kind", 1 if name.endswith("public") else 2, "FROM")
                    self.assertTrue(m.condition(visible))

    def test_festival_completion_is_per_type_and_district_and_survives_state_restore(self):
        m = self.model(2)
        self.complete_focus(m, "STP_pw_party_unbound_revolution")
        for name in ("STP_pi_festival_public", "STP_pi_festival_club"):
            self.rest_district(m)
            self.assertTrue(m.condition(block(self.decisions[name], "available")))
            self.action(m, name)
            self.action(m, name, "remove_effect")
        completed = {key: value for key, value in m.facts.items() if key[0] == "FROM"}
        self.fresh_festival_district(m)
        for name in ("STP_pi_festival_public", "STP_pi_festival_club"):
            self.assertTrue(m.condition(block(self.decisions[name], "visible")))
        self.fresh_festival_district(m)
        m.facts.update(completed)
        self.rest_district(m)
        before = m.get("ADISCORD_economy_treasury")
        for name in ("STP_pi_festival_public", "STP_pi_festival_club"):
            self.assertFalse(m.condition(block(self.decisions[name], "visible")))
            self.assertFalse(m.condition(block(self.decisions[name], "available")))
            self.action(m, name)
        self.assertEqual(m.get("ADISCORD_economy_treasury"), before)

    def test_medical_project_refunds_if_public_visits_already_cleared_load(self):
        m = self.model(2)
        m.put("STP_pi_festival_load", 1)
        self.action(m, "STP_pi_festival_medical")
        m.put("STP_pi_festival_load", 0)
        self.action(m, "STP_pi_festival_medical", "remove_effect")
        self.action(m, "STP_pi_festival_medical", "cancel_effect")
        self.assertEqual(m.get("ADISCORD_economy_treasury"), 10000)

    def test_portfolio_capacity_and_product_receipt_prevent_second_debit(self):
        m = self.model(4)
        self.action(m, "STP_pi_trade_rifles_standard")
        self.action(m, "STP_pi_trade_rifles_standard")
        self.action(m, "STP_pi_trade_support_standard")
        self.action(m, "STP_pi_trade_trucks_standard")
        self.assertEqual(m.get("ADISCORD_economy_treasury"), 8800)
        self.assertEqual(m.get("STP_pi_trade_busy"), 2)
        self.complete_focus(m, "STP_pe_trade_ending_a")
        self.action(m, "STP_pi_trade_trucks_standard")
        self.assertEqual(m.get("ADISCORD_economy_treasury"), 8200)
        self.assertEqual(m.get("STP_pi_trade_busy"), 3)

    def test_supplier_and_final_upgrades_do_not_reprice_paid_series(self):
        m = self.model(4)
        self.complete_focus(m, "STP_party_trade_tenders")
        self.action(m, "STP_pi_trade_rifles_series")
        self.assertEqual(m.get("STP_pi_trade_rifles_quote"), 27000)
        m.put("STP_pi_trade_level", 3)
        self.complete_focus(m, "STP_pe_trade_ending_b")
        self.action(m, "STP_pi_trade_rifles_series", "remove_effect")
        self.action(m, "STP_pi_trade_rifles_series", "remove_effect")
        self.assertEqual(m.get("delivered_ADISCORD_infantry_equipment_2156"), 27000)
        self.action(m, "STP_pi_trade_rifles_series")
        self.assertEqual(m.get("STP_pi_trade_rifles_quote"), 72900)

    def test_voluntary_refund_fractions_and_final_insurance(self):
        for mode, cost, refund in (("standard", 600, 540), ("rush", 900, 675), ("series", 1200, 900)):
            for insured in (False, True):
                with self.subTest(mode=mode, insured=insured):
                    m = self.model(4)
                    self.complete_focus(m, "STP_party_trade_tenders")
                    self.complete_focus(m, "STP_party_trade_imports")
                    name = "STP_pi_trade_support_" + mode
                    self.action(m, name)
                    m.facts[("STP", "has_decision", name)] = True
                    if insured:
                        self.complete_focus(m, "STP_pe_trade_ending_a")
                    self.action(m, "STP_pi_trade_support_cancel_order")
                    self.action(m, name, "cancel_effect")
                    self.assertEqual(m.get("ADISCORD_economy_treasury"), 10000 if insured else 10000 - cost + refund)
                    self.assertEqual(m.get("STP_pi_trade_busy"), 0)
                    self.assertFalse(m.facts[("STP", "has_decision", name)])
                    self.assertFalse(m.deliveries)

    def test_forced_cancel_returns_full_price_and_wrong_mode_cannot_deliver(self):
        m = self.model(4)
        self.action(m, "STP_pi_trade_trucks_standard")
        self.action(m, "STP_pi_trade_trucks_rush", "remove_effect")
        self.assertFalse(m.deliveries)
        m.facts[("STP", "STP_pi_country_valid", "yes")] = False
        self.action(m, "STP_pi_trade_trucks_standard", "remove_effect")
        self.assertEqual(m.get("ADISCORD_economy_treasury"), 10000)
        self.assertEqual(m.get("STP_pi_trade_busy"), 0)

    def test_supplier_expansion_shares_capacity_and_caps_at_three(self):
        m = self.model(4)
        m.put("STP_pw_production_factory_max_efficiency_factor", 0.15)
        for _ in range(4):
            self.action(m, "STP_pi_trade_expand")
            self.action(m, "STP_pi_trade_expand", "remove_effect")
        self.assertEqual(m.get("STP_pi_trade_level"), 3)
        self.assertEqual(m.get("ADISCORD_economy_treasury"), 7300)
        self.assertAlmostEqual(m.get("STP_pw_production_factory_max_efficiency_factor"), 0.225)
        self.assertEqual(m.get("STP_pi_trade_busy"), 0)

    def test_quick_case_requires_commission_to_reopen_and_is_finite(self):
        m = self.model(5)
        self.action(m, "STP_pi_case_orders_quick")
        self.action(m, "STP_pi_case_orders_quick", "remove_effect")
        self.action(m, "STP_pi_case_orders_quick")
        self.action(m, "STP_pi_case_orders_full")
        self.assertEqual(m.get("ADISCORD_economy_treasury"), 9850)
        self.assertEqual(m.get("STP_pi_case_orders_stage"), 4)
        self.complete_focus(m, "STP_pe_security_commission")
        self.action(m, "STP_pi_case_orders_full")
        self.action(m, "STP_pi_case_orders_full", "remove_effect")
        self.action(m, "STP_pi_case_orders_public")
        self.action(m, "STP_pi_case_orders_seal")
        self.action(m, "STP_pi_case_orders_full")
        self.assertEqual(m.get("ADISCORD_economy_treasury"), 9400)
        self.assertEqual(m.get("STP_pi_case_orders_stage"), 2)
        self.assertEqual(m.get("STP_pi_case_credits"), 0)

    def test_network_capacity_and_case_cancellation_release_team_once(self):
        m = self.model(5)
        self.action(m, "STP_pi_case_orders_full")
        self.action(m, "STP_pi_case_supply_full")
        self.assertEqual(m.get("STP_pi_case_busy"), 1)
        self.complete_focus(m, "STP_party_security_network")
        self.action(m, "STP_pi_case_supply_full")
        self.action(m, "STP_pi_case_property_full")
        self.assertEqual(m.get("STP_pi_case_busy"), 2)
        self.action(m, "STP_pi_case_orders_full", "cancel_effect")
        self.action(m, "STP_pi_case_orders_full", "cancel_effect")
        self.assertEqual(m.get("STP_pi_case_busy"), 1)
        self.assertEqual(m.get("ADISCORD_economy_treasury"), 9550)

    def test_public_final_is_retroactive_and_refresh_keeps_case_bonuses(self):
        m = self.model(5)
        m.put("STP_pw_stability_factor", 0.1)
        for case in ("orders", "supply", "property"):
            self.action(m, f"STP_pi_case_{case}_full")
            self.action(m, f"STP_pi_case_{case}_full", "remove_effect")
            self.action(m, f"STP_pi_case_{case}_public")
        m.put("STP_pi_public_rate", 0.01)
        for _ in range(4):
            m.run(self.effects["STP_pi_refresh"])
        self.assertAlmostEqual(m.get("STP_pw_stability_factor"), 0.15)
        self.assertAlmostEqual(m.get("STP_pw_ADISCORD_economy_admin_expense_factor"), -0.03)
        self.assertAlmostEqual(m.get("STP_pw_production_speed_industrial_complex_factor"), 0.05)

    def test_archive_final_grants_second_use_even_after_first_was_spent(self):
        m = self.model(5)
        for case in ("orders", "supply", "property"):
            self.action(m, f"STP_pi_case_{case}_full")
            self.action(m, f"STP_pi_case_{case}_full", "remove_effect")
            self.action(m, f"STP_pi_case_{case}_seal")
            self.action(m, "STP_pi_case_leverage")
        self.assertEqual(m.get("add_political_power"), 300)
        self.assertEqual(m.get("STP_pi_case_credits"), 0)
        m.put("STP_pi_case_rate", 2)
        for _ in range(4):
            m.run(self.effects["STP_pi_case_credit"])
        self.assertEqual(m.get("STP_pi_case_credits"), 3)
        self.action(m, "STP_pi_case_apparatus")
        self.action(m, "STP_pi_case_apparatus")
        self.assertEqual(m.get("STP_pi_case_credits"), 2)
        m.run(self.effects["STP_pi_case_credit"])
        self.assertEqual(m.get("STP_pi_case_credits"), 2)

    def test_exact_affordability_and_receipt_survive_new_campaign_initializer(self):
        for balance, paid in ((599.99, False), (600, True)):
            with self.subTest(balance=balance):
                m = self.model(4)
                m.put("ADISCORD_economy_treasury", balance)
                self.action(m, "STP_pi_trade_rifles_standard")
                m.run(self.effects["STP_pi_initialize"])
                self.assertEqual(m.get("STP_pi_trade_busy"), int(paid))
                self.assertAlmostEqual(m.get("ADISCORD_economy_treasury"), balance - (600 if paid else 0))

    def test_public_case_previews_equal_applied_aggregate_deltas(self):
        ideas = {e.key: e.value for e in walk(parse_clausewitz(read(
            "common/ideas/ADISCORD_STP_civil_war_ideas.txt")))
            if e.key.startswith("STP_pi_case_") and isinstance(e.value, list)}
        for case in ("orders", "supply", "property"):
            with self.subTest(case=case):
                m = self.model(5)
                m.put(f"STP_pi_case_{case}_stage", 1)
                self.action(m, f"STP_pi_case_{case}_public")
                for modifier in block(ideas[f"STP_pi_case_{case}_delta"], "modifier"):
                    self.assertAlmostEqual(m.get("STP_pw_" + modifier.key), float(modifier.value))

    def test_apparatus_expiry_invalidates_economy_without_self_activation_check(self):
        ideas = {e.key: e.value for e in walk(parse_clausewitz(read(
            "common/ideas/ADISCORD_STP_civil_war_ideas.txt")))
            if e.key == "STP_pi_case_apparatus_idea"}
        self.assertEqual(scalar(block(ideas["STP_pi_case_apparatus_idea"], "on_remove"),
                                "ADISCORD_economy_mark_dirty"), "yes")
        reward = block(self.decisions["STP_pi_case_apparatus"], "complete_effect")
        self.assertFalse(any(e.key == "has_decision" for e in walk(reward)))
        self.assertFalse(any(e.key == "days_remove" for e in self.decisions["STP_pi_case_apparatus"]))


if __name__ == "__main__":
    unittest.main()
