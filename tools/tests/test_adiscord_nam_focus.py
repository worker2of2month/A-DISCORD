"""Parsed NAM campaign scenarios; native loading and UI need a fresh game."""

from dataclasses import replace
from decimal import Decimal
from collections import Counter
from contextlib import redirect_stdout
from io import StringIO
from itertools import product
from pathlib import Path
import json
import re
import unittest
from unittest.mock import patch

from tools.builders.build_adiscord_focus_trees import expected_outputs
from tools.tests.test_adiscord_stp_preparation import (
    block, scalar, walk, matches_conditions, selected_effects,
)
from tools.validators.validate_adiscord_division_templates import parse_clausewitz
from tools.validators.validate_adiscord_nam_resource_war import (
    balanced_braces,
    has_script_fragment,
)

ROOT = Path(__file__).resolve().parents[2]
BASE = "ADISCORD_nam_resource_war"
TREES = {
    "main": ("focus_trees/NAM/main/focuses.txt", "NAM_focus", "ADISCORD_NAM_focus.txt"),
    "postwar": ("focus_trees/NAM/postwar/focuses.txt", "NAM_postwar_focus", "ADISCORD_NAM_postwar.txt"),
    "defeated": ("focus_trees/NAM/defeated/focuses.txt", "NAM_defeated_focus", "ADISCORD_NAM_defeated.txt"),
    "exile_radical": ("focus_trees/NAM/exile_radical/focuses.txt", "NAM_exile_radical_focus",
                      "ADISCORD_NAM_exile_radical.txt"),
    "exile_humanist": ("focus_trees/NAM/exile_humanist/focuses.txt", "NAM_exile_humanist_focus",
                       "ADISCORD_NAM_exile_humanist.txt"),
    "exile_corporate": ("focus_trees/NAM/exile_corporate/focuses.txt", "NAM_exile_corporate_focus",
                        "ADISCORD_NAM_exile_corporate.txt"),
}
EXILE = ("exile_radical", "exile_humanist", "exile_corporate")


def read(path):
    return (ROOT / path).read_text(encoding="utf-8-sig")


def parsed(path):
    return parse_clausewitz(read(path))


def tree_focuses(kind):
    tree = block(parsed(TREES[kind][0]), "focus_tree")
    return tree, {scalar(e.value, "id"): e.value for e in tree if e.key == "focus"}


def reachable(focuses, blocked):
    """Prerequisite closure only; availability and bypass are engine-evaluated."""
    completed = set()
    while True:
        ready = set()
        for name, focus in focuses.items():
            if name in completed or name in blocked:
                continue
            requirements = [entry.value for entry in focus if entry.key == "prerequisite"]
            if all(any(child.value in completed for child in group) for group in requirements):
                ready.add(name)
        if not ready:
            return completed
        completed.update(ready)


class NamCampaignTests(unittest.TestCase):
    def test_rom_changes_ideology_only_once_when_confederation_is_dismantled(self):
        characters = block(parsed("common/characters/NAM.txt"), "characters")
        initial = block(block(characters, "NAM_Egor_Rom"), "country_leader")
        self.assertEqual(scalar(initial, "ideology"), "etatism_ideology")
        teardown = block(parsed("common/scripted_effects/ADISCORD_vorkerland_effects.txt"),
                         "ADISCORD_vorkerland_teardown_confederation")
        self.assertEqual(scalar(block(teardown, "NAM"), "NAM_adopt_service_etatism"), "yes")
        transition = self.effects["NAM_adopt_service_etatism"]
        for leader, ideology, expected in (
            ("NAM_Egor_Rom", "etatism_ideology", True),
            ("NAM_Egor_Rom", "service_etatism", False),
            ("another_leader", "etatism_ideology", False),
            ("NAM_Egor_Rom", "humanism_ideology", False),
        ):
            with self.subTest(leader=leader, ideology=ideology):
                facts = {
                    ("NAM", "ruling_leader"): leader,
                    ("NAM", "has_country_leader_ideology", ideology): True,
                }
                selected = [entry for _, entry in selected_effects(transition, facts, "NAM")]
                roles = [entry.value for entry in selected if entry.key == "add_country_leader_role"]
                self.assertEqual(bool(roles), expected)
                if expected:
                    self.assertEqual(len(roles), 1)
                    self.assertEqual(scalar(roles[0], "character"), "NAM_Egor_Rom")
                    self.assertEqual(scalar(roles[0], "promote_leader"), "yes")
                    self.assertEqual(scalar(block(roles[0], "country_leader"), "ideology"), "service_etatism")
                    old_role = block(block(selected, "NAM_Egor_Rom"), "remove_country_leader_role")
                    self.assertEqual(scalar(old_role, "ideology"), "etatism_ideology")
                else:
                    self.assertEqual(selected, [])

    def test_settlement_fragment_accepts_multiline_script(self):
        fragment = "688 = { remove_core_of = SLF add_core_of = NAM }"
        source = (
            "688 = {\n"
            "\tremove_core_of = SLF\n"
            "\t# Restore the national core after the uprising.\n"
            "\tadd_core_of = NAM\n"
            "}"
        )
        self.assertTrue(has_script_fragment(source, fragment))
        self.assertFalse(has_script_fragment(source.replace("NAM", "EFL"), fragment))
        self.assertFalse(
            has_script_fragment("688 = { add_core_of = NAM remove_core_of = SLF }", fragment)
        )

    @classmethod
    def setUpClass(cls):
        cls.tree, cls.focuses = tree_focuses("main")
        cls.postwar_tree, cls.postwar = tree_focuses("postwar")
        cls.defeated_tree, cls.defeated = tree_focuses("defeated")
        cls.exile_trees = {kind: tree_focuses(kind) for kind in EXILE}
        cls.triggers = {e.key: e.value for e in parsed(f"common/scripted_triggers/{BASE}_triggers.txt")}
        cls.effects = {}
        for path in (f"common/scripted_effects/{BASE}_effects.txt", "common/scripted_effects/ADISCORD_shared_action_effects.txt"):
            cls.effects.update({e.key: e.value for e in parsed(path)})
        cls.decisions = {e.key: e.value for e in block(parsed(f"common/decisions/{BASE}_decisions.txt"), "NAM_national_programmes")}
        cls.events = {scalar(e.value, "id"): e.value for e in parsed(f"events/{BASE}_events.txt") if e.key == "country_event"}
        cls.ideas = {e.key: e.value for e in block(block(parsed(f"common/ideas/{BASE}_ideas.txt"), "ideas"), "country")}

    def expand(self, entries):
        """Expand only native boolean scripted-trigger calls, never macro blocks."""
        result = []
        for entry in entries:
            if entry.key in self.triggers:
                self.assertIn(entry.value, ("yes", "no"), entry.key)
                result.append(replace(entry, key="AND" if entry.value == "yes" else "NOT", value=self.expand(self.triggers[entry.key])))
            elif isinstance(entry.value, list):
                result.append(replace(entry, value=self.expand(entry.value)))
            else:
                result.append(entry)
        return result

    def matches(self, entries, facts):
        return matches_conditions(self.expand(entries), facts, "NAM")

    def apply(self, entries, facts):
        """Execute selected accounting statements, leaving engine timing unmodelled."""
        for scope, entry in selected_effects(self.expand(entries), facts, "NAM"):
            if entry.key in self.effects:
                self.apply(self.effects[entry.key], facts)
            elif entry.key == "add_political_power":
                key = (scope, "numeric", "has_political_power")
                facts[key] = facts.get(key, 0) + float(entry.value)
            elif entry.key == "add_fuel":
                key = (scope, "numeric", "has_fuel")
                facts[key] = facts.get(key, 0) + float(entry.value)
            elif entry.key == "add_to_variable":
                key = (scope, "variable", scalar(entry.value, "var"))
                facts[key] = facts.get(key, 0) + float(scalar(entry.value, "value"))
            elif entry.key in ("set_country_flag", "clr_country_flag"):
                facts[(scope, "has_country_flag", entry.value)] = entry.key == "set_country_flag"
            elif entry.key == "add_equipment_to_stockpile":
                key = (scope, "equipment", scalar(entry.value, "type"))
                facts[key] = facts.get(key, 0) + float(scalar(entry.value, "amount"))
            elif entry.key == "add_timed_idea":
                facts[(scope, "has_idea", scalar(entry.value, "idea"))] = True
            elif entry.key == "add_stability":
                facts[(scope, "reward", "stability")] = facts.get((scope, "reward", "stability"), 0) + float(entry.value)

    def facts(self, pp=1000, treasury=10000, fuel=20000):
        result = {
            ("NAM", "exists", "yes"): True,
            ("NAM", "has_capitulated", "no"): True,
            ("NAM", "has_war", "yes"): True,
            ("NAM", "has_war", "no"): True,
            ("NAM", "has_war_with", "SLF"): True,
            ("NAM", "numeric", "has_political_power"): pp,
            ("NAM", "numeric", "has_fuel"): fuel,
            ("NAM", "variable", "ADISCORD_economy_treasury"): treasury,
            ("NAM", "has_global_flag", BASE + "_started"): True,
        }
        for state in (67, 688, 700):
            for condition in ("owns_state", "controls_state"):
                result[("NAM", condition, str(state))] = True
        for focus in self.focuses:
            result[("NAM", "has_completed_focus", focus)] = True
        result[("NAM", "has_completed_focus", "NAM_recognition")] = False
        return result

    def test_tree_selection_and_generated_owner(self):
        self.assertEqual(scalar(self.tree, "id"), "NAM_focus")
        country = block(self.tree, "country")
        self.assertEqual(scalar(block(country, "modifier"), "tag"), "NAM")
        selection = {"postwar": self.postwar_tree, "defeated": self.defeated_tree}
        for kind, tree in selection.items():
            self.assertEqual(scalar(tree, "id"), TREES[kind][1])
            modifier = block(block(tree, "country"), "modifier")
            self.assertEqual(scalar(modifier, "original_tag"), "NAM")
            conditions = [entry for entry in modifier if entry.key != "add"]
            for outcome in (None, "nam_victory", "compromise", "island_exile", "standoff"):
                facts = {("NAM", "original_tag", "NAM"): True}
                if outcome is not None:
                    facts[("NAM", "has_global_flag", BASE + "_" + outcome)] = True
                expected = outcome in (("nam_victory",) if kind == "postwar" else ("compromise",))
                self.assertEqual(self.matches(conditions, facts), expected, (kind, outcome))
        # Event .100 and the corporate takeover load the exile trees; each one
        # also selects only its own course.
        courses = {
            "exile_radical": {"NAM_exile_radical"},
            "exile_humanist": {"NAM_exile_humanist"},
            "exile_corporate": {"NAM_exile_humanist", "NAM_corp_takeover"},
        }
        for kind, own_flags in courses.items():
            tree = self.exile_trees[kind][0]
            self.assertEqual(scalar(tree, "id"), TREES[kind][1])
            modifier = block(block(tree, "country"), "modifier")
            self.assertEqual(scalar(modifier, "original_tag"), "NAM")
            conditions = [entry for entry in modifier if entry.key != "add"]
            for flags in courses.values():
                facts = {
                    ("NAM", "original_tag", "NAM"): True,
                    ("NAM", "has_global_flag", BASE + "_island_exile"): True,
                }
                for flag in flags:
                    facts[("NAM", "has_country_flag", flag)] = True
                self.assertEqual(self.matches(conditions, facts), flags == own_flags, (kind, flags))
        owners = json.loads(read("tools/data/generated_output_owners.json"))
        for kind, (_, _, filename) in TREES.items():
            output = ROOT / "common/national_focus" / filename
            self.assertEqual(output.read_bytes(), expected_outputs()[output], kind)
            self.assertIn(f"common/national_focus/{filename}", str(owners))

    def test_unique_layout_and_real_rewards(self):
        expected = {
            "main": (self.focuses, 110), "postwar": (self.postwar, 54), "defeated": (self.defeated, 24),
            "exile_radical": (self.exile_trees["exile_radical"][1], 60),
            "exile_humanist": (self.exile_trees["exile_humanist"][1], 57),
            "exile_corporate": (self.exile_trees["exile_corporate"][1], 29),
        }
        names = [name for focuses, _ in expected.values() for name in focuses]
        self.assertEqual(len(names), len(set(names)))
        for kind, (focuses, count) in expected.items():
            coordinates = set()
            self.assertEqual(len(focuses), count, kind)
            filters = set()
            for name, focus in focuses.items():
                coordinate = (scalar(focus, "x"), scalar(focus, "y"))
                self.assertNotIn(coordinate, coordinates, name)
                coordinates.add(coordinate)
                self.assertTrue(block(focus, "completion_reward"), name)
                self.assertIn(int(scalar(focus, "cost")), range(1, 13))
                filters.add(tuple(e.value for e in block(focus, "search_filters")))
                self.assertEqual(scalar(block(focus, "available"), "has_capitulated"), "no")
                for group in (e.value for e in focus if e.key == "prerequisite"):
                    for child in group:
                        self.assertIn(child.value, focuses, (name, "prerequisite leaves its tree"))
            self.assertGreaterEqual(len(filters), 4, kind)

    def test_every_policy_combination_reaches_the_branch_finals(self):
        pairs = (("vertical", "districts"), ("export_quays", "domestic_refining"),
                 ("field_guards", "mobile_columns"), ("supports_oil_compact", "supports_export_houses"),
                 ("court_azhar", "fuel_leverage"), ("island_levy_office", "island_concession"))
        # Course-gated alternatives follow the ladder course chosen in the first pair.
        course = {
            "vertical": {"NAM_district_assemblies", "NAM_weber_channel", "NAM_district_volunteers"},
            "districts": {"NAM_namestnik_circuits", "NAM_cache_hunters", "NAM_martial_seals"},
        }
        finals = ("NAM_seal_courts", "NAM_quiet_wells", "NAM_civilian_combine", "NAM_quartermaster",
                  "NAM_pillar_arbitration", "NAM_general_staff_plan", "NAM_island_governors", "NAM_rom_address")
        for choices in product(*pairs):
            blocked = {"NAM_" + other for pair, chosen in zip(pairs, choices) for other in pair if other != chosen}
            completed = reachable(self.focuses, blocked | course[choices[0]])
            for final in finals:
                self.assertIn(final, completed, choices)
            for pair, chosen in zip(pairs, choices):
                group = block(self.focuses["NAM_" + chosen], "mutually_exclusive")
                self.assertEqual({e.value for e in group}, {"NAM_" + n for n in pair if n != chosen})
        for state, federal in (("service_state", "federal_charter"), ("federal_charter", "service_state")):
            for peace in (("civil_dividend", "armed_peace"), ("armed_peace", "civil_dividend")):
                completed = reachable(self.postwar, {"NAM_" + federal, "NAM_" + peace[1]})
                self.assertIn("NAM_svetlogorye", completed)
                ending = "NAM_ladder_of_seals" if state == "service_state" else "NAM_common_fuel_market"
                self.assertIn(ending, completed, state)
        for chosen, other in (("revenge", "accommodation"), ("accommodation", "revenge")):
            completed = reachable(self.defeated, {"NAM_defeat_" + other})
            self.assertIn("NAM_defeat_second_chapter", completed, chosen)
        finals = {
            "exile_radical": "NAM_rad_dominion_of_pillars",
            "exile_humanist": "NAM_hum_union_constitution",
            "exile_corporate": "NAM_board_union_of_boards",
        }
        for kind, final in finals.items():
            focuses = self.exile_trees[kind][1]
            pairs = sorted({
                tuple(sorted((name, entry.value)))
                for name, focus in focuses.items()
                for group in (e.value for e in focus if e.key == "mutually_exclusive")
                for entry in group
            })
            self.assertGreaterEqual(len(pairs), 4, kind)
            for side in (0, 1):
                blocked = {pair[1 - side] for pair in pairs}
                self.assertIn(final, reachable(focuses, blocked), (kind, side))

    def test_each_exile_tree_owns_its_wars_and_script_gates(self):
        from tools.builders.build_adiscord_focus_trees import SHARED_HISTORY_SOURCES

        for kind in EXILE:
            focuses = self.exile_trees[kind][1]
            self.assertNotIn("allow_branch", read(TREES[kind][0]), kind)
            for effect in ("NAM_war_of_return_start", "NAM_great_war_start"):
                callers = [
                    name for name, focus in focuses.items()
                    if effect in [e.key for e in walk(block(focus, "completion_reward"))]
                ]
                self.assertEqual(len(callers), 1, (kind, effect))
        self.assertNotIn("allow_branch", read(TREES["defeated"][0]))
        # Decisions, categories and the piracy window read these completions.
        gates = {
            "exile_radical": ("NAM_exile_general_staff", "NAM_exile_sea_raiders", "NAM_exile_black_market",
                              "NAM_exile_fences", "NAM_exile_marine_orders", "NAM_rad_labour_camps",
                              "NAM_rad_spoils_of_return", "NAM_rad_garrison_belt", "NAM_rad_martial_law"),
            "exile_humanist": ("NAM_hum_citizen_army", "NAM_hum_free_zones", "NAM_hum_steel_exchange",
                               "NAM_hum_labour_bureau", "NAM_hum_innovation_parks", "NAM_hum_credit_arms",
                               "NAM_hum_regulated_partnership", "NAM_hum_charter_commission",
                               "NAM_hum_open_doors", "NAM_hum_marine_contracts", "NAM_hum_union_council",
                               "NAM_hum_federal_treaties", "NAM_hum_harbour_rebuilding"),
            "exile_corporate": ("NAM_hum_company_guard", "NAM_board_landing_contracts", "NAM_board_constitution",
                                "NAM_board_shareholders", "NAM_board_district_auction"),
        }
        for kind, names in gates.items():
            for name in names:
                self.assertIn(name, self.exile_trees[kind][1], (kind, name))
        # The takeover replaces the humanist tree; its completions must survive.
        self.assertIn(TREES["exile_humanist"][0].removeprefix("focus_trees/"), SHARED_HISTORY_SOURCES)

    def test_normal_preparation_fits_external_clock(self):
        path = ("inventory", "open_ledgers", "districts", "public_payroll", "district_guarantees")
        days = sum(int(scalar(self.focuses["NAM_" + key], "cost")) * 7 for key in path)
        self.assertEqual(days, 112)
        self.assertLess(days + 60, 850)
        self.assertNotIn("prerequisite", [e.key for e in self.focuses["NAM_alarm"]])
        self.assertNotIn("prerequisite", [e.key for e in self.postwar["NAM_recognition"]])
        self.assertNotIn("prerequisite", [e.key for e in self.defeated["NAM_defeat_count_losses"]])
        self.assertEqual(int(scalar(self.focuses["NAM_alarm"], "cost")), 1)
        # One full pre-war route (vertical, refining, field guards) fits before the backstop war.
        blocked = {"NAM_districts", "NAM_export_quays", "NAM_mobile_columns", "NAM_supports_export_houses",
                   "NAM_fuel_leverage", "NAM_island_concession", "NAM_hear_the_harbour", "NAM_hear_the_registrar",
                   "NAM_concealed_reserve", "NAM_basin_is_ours", "NAM_district_assemblies", "NAM_weber_channel"}
        war = {name for name, focus in self.focuses.items() if "allow_branch" in [e.key for e in focus]}
        route = reachable(self.focuses, blocked | war)
        self.assertLessEqual(sum(int(scalar(self.focuses[name], "cost")) * 7 for name in route), 1000)
        for name, focus in self.focuses.items():
            if "NAM_restitution_clock_tt" in repr(block(focus, "available")):
                self.assertIn("ADISCORD_nam_resource_war_started", repr(block(focus, "bypass")), name)

    def test_late_political_routes_still_have_a_usable_result(self):
        facts = self.facts()
        facts[("NAM", "has_global_flag", BASE + "_resolved")] = True
        reward = block(self.focuses["NAM_emergency_writ"], "completion_reward")
        self.assertIn("NAM_supply_order", [e.value for e in walk(reward) if e.key == "unlock_decision_tooltip"])
        self.assertTrue(self.matches(block(self.decisions["NAM_supply_order"], "visible"), facts))
        self.assertTrue(self.matches(block(self.decisions["NAM_supply_order"], "available"), facts))
        reward = block(self.focuses["NAM_district_guarantees"], "completion_reward")
        self.apply(reward, facts)
        self.assertEqual(facts[("NAM", "reward", "stability")], 0.03)

    def test_quartermaster_delivers_when_procurement_is_already_unlocked(self):
        for emergency_first in (False, True):
            facts = self.facts()
            facts[("NAM", "has_completed_focus", "NAM_emergency_writ")] = emergency_first
            self.apply(block(self.focuses["NAM_quartermaster"], "completion_reward"), facts)
            self.assertEqual(facts[("NAM", "equipment", "infantry_equipment")], 13500)
            self.assertEqual(facts[("NAM", "equipment", "support_equipment")], 60)

    def test_fractional_affordability_and_actual_debits(self):
        expected = {
            "NAM_export_fuel": (25, 0, 5000), "NAM_workshop_batch": (35, 0, 3000),
            "NAM_supply_order": (25, 500, 0), "NAM_emergency_arsenal": (35, 500, 0),
            "NAM_counterinsurgency": (75, 500, 0), "NAM_relief_batch": (35, 0, 3000),
            "NAM_veteran_housing": (35, 250, 0), "NAM_postwar_rearmament": (35, 500, 0),
            "NAM_sign_compact": (75, 500, 0),
        }
        for name, (pp, treasury, fuel) in expected.items():
            decision = self.decisions[name]
            self.assertEqual(scalar(decision, "cost"), "0")
            for currency, amount, field in (
                ("pp", pp, ("NAM", "numeric", "has_political_power")),
                ("treasury", treasury, ("NAM", "variable", "ADISCORD_economy_treasury")),
                ("fuel", fuel, ("NAM", "numeric", "has_fuel")),
            ):
                if not amount:
                    continue
                facts = self.facts(pp=pp, treasury=treasury, fuel=fuel)
                if name == "NAM_sign_compact":
                    facts[("NAM", "has_global_flag", BASE + "_started")] = False
                self.assertTrue(self.matches(block(decision, "custom_cost_trigger"), facts), name)
                facts[field] = amount - 0.01
                self.assertFalse(self.matches(block(decision, "custom_cost_trigger"), facts), (name, currency))
                before = dict(facts)
                self.apply(block(decision, "complete_effect"), facts)
                self.assertEqual(facts, before, (name, currency, "stale click must not pay"))
            facts = self.facts(pp=pp, treasury=treasury, fuel=fuel)
            if name == "NAM_sign_compact":
                facts[("NAM", "has_global_flag", BASE + "_started")] = False
            self.apply(block(decision, "complete_effect"), facts)
            self.assertEqual(facts[("NAM", "numeric", "has_political_power")], 0, name)
            self.assertEqual(facts[("NAM", "numeric", "has_fuel")], 0, name)
            expected_treasury = 250 if name == "NAM_export_fuel" else 0
            self.assertEqual(facts[("NAM", "variable", "ADISCORD_economy_treasury")], expected_treasury, name)
            self.assertEqual(facts.get(("NAM", "variable", "ADISCORD_economy_current_month_action_costs"), 0), treasury, name)
            rifles = {
                "NAM_supply_order": 13500, "NAM_emergency_arsenal": 18000,
                "NAM_counterinsurgency": 9000, "NAM_relief_batch": 7200,
                "NAM_postwar_rearmament": 18000,
            }
            if name in rifles:
                self.assertEqual(facts[("NAM", "equipment", "infantry_equipment")], rifles[name], name)

    def test_compact_age_loss_repayment_and_delayed_rebellion(self):
        facts = self.facts(pp=150, treasury=1000)
        facts[("NAM", "has_global_flag", BASE + "_started")] = False
        effect = block(self.decisions["NAM_sign_compact"], "complete_effect")
        self.apply(effect, facts)
        balance = facts[("NAM", "variable", "ADISCORD_economy_treasury")]
        self.apply(effect, facts)
        self.assertEqual(facts[("NAM", "variable", "ADISCORD_economy_treasury")], balance)
        facts[("NAM", "flag_days", "NAM_district_compact")] = 59
        self.assertFalse(self.matches(self.triggers["NAM_compact_effective"], facts))
        facts[("NAM", "flag_days", "NAM_district_compact")] = 60
        self.assertTrue(self.matches(self.triggers["NAM_compact_effective"], facts))
        facts[("NAM", "has_country_flag", "NAM_compact_ratified")] = True
        facts[("NAM", "controls_state", "688")] = False
        self.apply(self.effects["NAM_invalidate_lost_compact"], facts)
        self.assertTrue(facts[("NAM", "has_country_flag", "NAM_compact_ratified")])
        self.assertFalse(facts[("NAM", "has_country_flag", "NAM_district_compact")])
        facts[("NAM", "controls_state", "688")] = True
        self.assertTrue(self.matches(self.triggers["NAM_can_sign_compact"], facts))
        rebellion = block(self.effects[BASE + "_start_mainland_rebellion"], "if")
        self.assertNotIn("NAM_compact_effective", [e.key for e in walk(rebellion)])
        self.assertIn("NAM_compact_ratified", [e.value for e in walk(rebellion) if e.key == "has_country_flag"])

    def test_compact_report_does_not_promote_a_late_signature_during_war(self):
        definitions = parsed("common/scripted_localisation/ADISCORD_nam_resource_war_scripted_loc.txt")
        status = next(e.value for e in definitions if scalar(e.value, "name") == "NAMGetCompactStatus")

        def report(facts):
            for entry in status:
                if entry.key != "text":
                    continue
                triggers = [e.value for e in entry.value if e.key == "trigger"]
                if not triggers or self.matches(triggers[0], facts):
                    return scalar(entry.value, "localization_key")
            self.fail("Missing compact status fallback")

        facts = self.facts()
        facts[("NAM", "has_country_flag", "NAM_district_compact")] = True
        facts[("NAM", "flag_days", "NAM_district_compact")] = 90
        self.assertEqual(report(facts), "NAM_compact_wartime_unavailable")
        facts[("NAM", "has_country_flag", "NAM_compact_ratified")] = True
        self.assertEqual(report(facts), "NAM_compact_ratified_status")
        facts[("NAM", "controls_state", "688")] = False
        self.apply(self.effects["NAM_invalidate_lost_compact"], facts)
        self.assertEqual(report(facts), "NAM_compact_interrupted_status")
        facts[("NAM", "has_global_flag", BASE + "_resolved")] = True
        self.assertEqual(report(facts), "NAM_compact_war_closed")

    def test_intro_uses_the_actual_collapse_phase(self):
        descriptions = [e.value for e in self.events[BASE + ".10"] if e.key == "desc"]
        for collapsed in (False, True):
            facts = self.facts()
            facts[("NAM", "has_global_flag", "ADISCORD_vorkerland_collapse_wars_started")] = collapsed
            shown = [scalar(d, "text") for d in descriptions if self.matches(block(d, "trigger"), facts)]
            self.assertEqual(shown, [BASE + (".10.d" if collapsed else ".10.before")])

    def test_mission_never_succeeds_automatically_and_all_treaties_clean_up(self):
        mission = self.decisions["NAM_defend_fields"]
        self.assertFalse(self.matches(block(mission, "available"), self.facts()))
        self.assertEqual(scalar(mission, "days_mission_timeout"), "420")
        self.assertFalse(block(mission, "timeout_effect"))
        for outcome in ("resolve_nam_victory", "resolve_coalition_victory", "resolve_compromise", "resolve_standoff"):
            self.assertIn(BASE + "_clear_temporary_support", [e.key for e in walk(self.effects[BASE + "_" + outcome])])
        self.assertIn("NAM_close_war_programmes", [e.key for e in walk(self.effects[BASE + "_clear_temporary_support"])])
        cleanup = self.effects["NAM_close_war_programmes"]
        self.assertIn("NAM_defend_fields", [e.value for e in cleanup if e.key == "remove_mission"])
        self.assertEqual({e.value for e in cleanup if e.key == "remove_ideas"}, {"NAM_wartime_entrenchment", "NAM_counterstroke_staff", "NAM_rebel_depot_maps"})

    def test_open_payroll_event_cannot_spend_after_money_or_route_changes(self):
        options = {
            scalar(e.value, "name"): e.value
            for e in self.events[BASE + ".10"] if e.key == "option"
        }
        facts = self.facts(treasury=249.99)
        self.apply(options[BASE + ".10.a"], facts)
        self.assertEqual(facts[("NAM", "variable", "ADISCORD_economy_treasury")], 249.99)
        facts[("NAM", "variable", "ADISCORD_economy_treasury")] = 99.99
        self.apply(options[BASE + ".10.c"], facts)
        self.assertEqual(facts[("NAM", "variable", "ADISCORD_economy_treasury")], 99.99)
        facts[("NAM", "has_completed_focus", "NAM_recognition")] = True
        facts[("NAM", "variable", "ADISCORD_economy_treasury")] = 1000
        for suffix in ("a", "b", "c"):
            option = options[BASE + ".10." + suffix]
            self.assertFalse(self.matches(block(option, "trigger"), facts))
            self.apply(option, facts)
        self.assertEqual(facts[("NAM", "variable", "ADISCORD_economy_treasury")], 1000)
        self.assertNotIn(("NAM", "has_idea", "NAM_wage_arrears"), facts)
        close = options[BASE + ".close"]
        self.assertTrue(self.matches(block(close, "trigger"), facts))
        before = facts.copy()
        self.apply(close, facts)
        self.assertEqual(facts, before)

    def test_bilingual_costs_story_limits_and_encoding(self):
        for language in ("russian", "english"):
            path = ROOT / f"localisation/{language}/{BASE}_l_{language}.yml"
            self.assertTrue(path.read_bytes().startswith(b"\xef\xbb\xbf"))
            text = path.read_text(encoding="utf-8-sig")
            values = dict(re.findall(r'^[ \t]*([^ #:\s]+):\d*[ \t]*"(.*)"[ \t]*$', text, re.M))
            exile = [name for kind in EXILE for name in self.exile_trees[kind][1]]
            for name in (*self.focuses, *self.postwar, *self.defeated, *exile):
                self.assertIn(name, values.keys())
                self.assertIn(name + "_desc", values.keys())
            for name, decision in self.decisions.items():
                self.assertIn(name, values)
                self.assertIn(name + "_desc", values)
                for cost in (e.value for e in decision if e.key == "custom_cost_text"):
                    for suffix in ("", "_blocked", "_tooltip"):
                        self.assertIn(cost + suffix, values)
            for number in range(10, 14):
                descriptions = [e.value for e in self.events[f"{BASE}.{number}"] if e.key == "desc"]
                keys = [scalar(d, "text") if isinstance(d, list) else d for d in descriptions]
                for key in keys:
                    prose = values[key].replace("\\n", "\n")
                    self.assertLessEqual(len(prose), 3000)
                    self.assertLessEqual(len(prose.encode("utf-8")), 5500)
                    self.assertNotIn("§Y", prose)
        for path in (*(source for source, _, _ in TREES.values()), "common/ai_strategy_plans/ADISCORD_NAM_plans.txt",
                     f"common/decisions/{BASE}_decisions.txt", f"common/ideas/{BASE}_ideas.txt", f"events/{BASE}_events.txt"):
            self.assertFalse((ROOT / path).read_bytes().startswith(b"\xef\xbb\xbf"))
            self.assertTrue(balanced_braces(read(path)), path)

    def test_institution_changes_invalidate_economy_without_polling(self):
        for name, idea in self.ideas.items():
            if not name.startswith("NAM_"):
                continue
            # Display-only aggregate deltas are never installed; their refresh owns invalidation.
            allowed = [entry.value for entry in idea if entry.key == "allowed"]
            self.assertLessEqual(len(allowed), 1, name)
            if allowed and [(e.key, e.value) for e in allowed[0]] == [("always", "no")]:
                continue
            for hook in ("on_add", "on_remove"):
                self.assertIn("ADISCORD_economy_mark_dirty", [e.key for e in block(idea, hook)], name)
        hooks = read("common/on_actions/03_ADISCORD_nam_resource_war_on_actions.txt")
        self.assertNotIn("on_daily", hooks)
        self.assertNotIn("every_country", hooks)


class NamPillarsTests(unittest.TestCase):
    """Pillars of power: five weighted groups, programme progress and endings."""

    GROUPS = ("nam", "oil", "dist", "garr", "trade")

    @classmethod
    def setUpClass(cls):
        cls.focuses = {}
        for kind in TREES:
            cls.focuses.update(tree_focuses(kind)[1])
        cls.effects = {e.key: e.value for e in parsed(f"common/scripted_effects/{BASE}_effects.txt")}

    def changes(self, entries, kind):
        result = {}
        for entry in walk(entries):
            if entry.key != "add_to_variable":
                continue
            name = scalar(entry.value, "var")
            for group in self.GROUPS:
                if name == f"NAM_grp_{group}_{kind}":
                    result[group] = result.get(group, 0) + float(scalar(entry.value, "value"))
        return result

    def test_initial_influence_is_complete_and_endings_redistribute_it(self):
        initial = {}
        for entry in walk(self.effects["NAM_groups_initialize"]):
            if entry.key == "set_variable" and scalar(entry.value, "var").endswith("_influence"):
                initial[scalar(entry.value, "var")] = float(scalar(entry.value, "value"))
        self.assertEqual(len(initial), 5)
        self.assertEqual(sum(initial.values()), 100)
        endings = [name for name in self.focuses if "_ending_" in name]
        self.assertEqual(len(endings), 4)
        for name in endings:
            shift = self.changes(block(self.focuses[name], "completion_reward"), "influence")
            self.assertTrue(shift, name)
            self.assertEqual(sum(shift.values()), 0, name)
            for group, value in shift.items():
                self.assertGreaterEqual(initial[f"NAM_grp_{group}_influence"] + value, 0, name)

    def test_each_path_final_offers_two_exclusive_endings(self):
        finals = {
            "NAM_ladder_of_seals": ("NAM_ladder_ending_iron", "NAM_ladder_ending_service"),
            "NAM_common_fuel_market": ("NAM_charter_ending_federation", "NAM_charter_ending_oil_union"),
        }
        effects = {
            "NAM_ladder_ending_iron": "NAM_apply_ending_iron",
            "NAM_ladder_ending_service": "NAM_apply_ending_service",
            "NAM_charter_ending_federation": "NAM_apply_ending_federation",
            "NAM_charter_ending_oil_union": "NAM_apply_ending_oil_union",
        }
        for final, pair in finals.items():
            for name in pair:
                focus = self.focuses[name]
                self.assertEqual([e.value for e in block(focus, "prerequisite")], [final], name)
                other = next(n for n in pair if n != name)
                self.assertEqual([e.value for e in block(focus, "mutually_exclusive")], [other], name)
                reward = block(focus, "completion_reward")
                self.assertIn("NAM_prog_ending", repr(reward), name)
                self.assertIn((effects[name], "yes"), [(e.key, e.value) for e in reward], name)
        for source, _, _ in TREES.values():
            self.assertNotIn("NAM_programme", read(source))

    def test_every_support_shift_refreshes_and_is_localised(self):
        texts = {language: read(f"localisation/{language}/{BASE}_l_{language}.yml") for language in ("russian", "english")}
        shifted = 0
        for name, focus in self.focuses.items():
            reward = block(focus, "completion_reward")
            if not self.changes(reward, "support"):
                continue
            shifted += 1
            tooltips = [e.value for e in walk(reward) if e.key == "custom_effect_tooltip"]
            self.assertIn(f"NAM_grp_{name[4:]}_tt", tooltips, name)
            self.assertIn("NAM_groups_refresh", [e.key for e in walk(reward)], name)
            for language, text in texts.items():
                self.assertIn(f" NAM_grp_{name[4:]}_tt:", text, (language, name))
        self.assertGreaterEqual(shifted, 30)

    def test_refresh_covers_every_group_without_world_scans(self):
        source = read(f"common/scripted_effects/{BASE}_effects.txt")
        start = source.index("NAM_groups_refresh = {")
        refresh = source[start:source.index("\n}\n", start)]
        for group in self.GROUPS:
            self.assertIn(f"NAM_grp_{group}_support", refresh)
            self.assertIn(f"NAM_grp_{group}_influence", refresh)
        self.assertIn("force_update_dynamic_modifier = yes", refresh)
        self.assertNotIn("every_country", refresh)
        hooks = read("common/on_actions/03_ADISCORD_nam_resource_war_on_actions.txt")
        self.assertIn("on_monthly_NAM", hooks)
        self.assertIn("NAM = {\n\t\t\t\t\tNAM_groups_initialize = yes", read("common/on_actions/00_ADISCORD_on_actions.txt"))


class NamOptimizationTests(unittest.TestCase):
    """Parsed state transitions and work counts; native timing remains unmodelled."""

    GROUPS = NamPillarsTests.GROUPS

    @classmethod
    def setUpClass(cls):
        cls.effects = {
            entry.key: entry.value
            for entry in parsed(f"common/scripted_effects/{BASE}_effects.txt")
        }

    def normalize(self, entries):
        result = []
        comparisons = {">": "greater_than", "<": "less_than"}
        for entry in entries:
            if entry.key == "check_variable" and not any(e.key == "var" for e in entry.value):
                name, operator, value = (e.value for e in entry.value)
                entry = replace(entry, value=parse_clausewitz(
                    f"var = {name} value = {value} compare = {comparisons[operator]}"
                ))
            elif isinstance(entry.value, list):
                entry = replace(entry, value=self.normalize(entry.value))
            result.append(entry)
        return result

    def execute(self, name, facts, calls):
        arithmetic = {
            "set_variable": lambda old, value: value,
            "add_to_variable": lambda old, value: old + value,
            "subtract_from_variable": lambda old, value: old - value,
            "multiply_variable": lambda old, value: old * value,
            "divide_variable": lambda old, value: old / value,
        }
        for scope, entry in selected_effects(self.normalize(self.effects[name]), facts, "NAM"):
            operation = entry.key.replace("_temp_variable", "_variable")
            if operation in arithmetic:
                variable = scalar(entry.value, "var")
                reference = scalar(entry.value, "value")
                try:
                    value = float(reference)
                except ValueError:
                    value = facts.get((scope, "variable", reference), 0)
                key = (scope, "variable", variable)
                facts[key] = arithmetic[operation](facts.get(key, 0), value)
                if "_temp_variable" not in entry.key:
                    facts[(scope, "has_variable", variable)] = True
            elif operation == "clamp_variable":
                key = (scope, "variable", scalar(entry.value, "var"))
                facts[key] = min(float(scalar(entry.value, "max")), max(
                    float(scalar(entry.value, "min")), facts.get(key, 0)
                ))
            elif entry.key in ("NAM_groups_refresh", "NAM_seal_discipline_clamp"):
                calls[entry.key] += 1
                self.execute(entry.key, facts, calls)
            elif entry.key == "add_dynamic_modifier":
                facts[(scope, "has_dynamic_modifier", scalar(entry.value, "modifier"))] = True
            elif entry.key == "set_country_flag":
                self.assertIsInstance(entry.value, str)
                facts[(scope, "has_country_flag", entry.value)] = True
            elif entry.key == "country_event":
                calls[scalar(entry.value, "id")] += 1
            elif entry.key in (
                "force_update_dynamic_modifier", "ADISCORD_economy_mark_dirty",
                "NAM_groups_check_events",
            ):
                calls[entry.key] += 1
            else:
                self.fail(f"Unsupported optimization fixture effect: {entry.key}")

    def test_monthly_drift_preserves_values_and_only_refreshes_changed_inputs(self):
        for group, support in product(self.GROUPS, (0, 20, 49.49, 49.5, 49.99, 50, 50.01, 50.5, 85, 100)):
            with self.subTest(group=group, support=support):
                facts = {
                    ("NAM", "has_country_flag", "NAM_groups_initialized"): True,
                    ("NAM", "has_dynamic_modifier", "NAM_loyalty_dynamic"): True,
                }
                for current in self.GROUPS:
                    facts[("NAM", "variable", f"NAM_grp_{current}_support")] = 50
                    facts[("NAM", "variable", f"NAM_grp_{current}_influence")] = 20
                key = ("NAM", "variable", f"NAM_grp_{group}_support")
                facts[key] = support
                calls = Counter()
                self.execute("NAM_groups_monthly", facts, calls)
                expected = max(50, support - 0.5) if support >= 50 else min(50, support + 0.5)
                self.assertAlmostEqual(facts[key], expected)
                for current in self.GROUPS:
                    if current != group:
                        self.assertEqual(facts[("NAM", "variable", f"NAM_grp_{current}_support")], 50)
                self.assertEqual(calls["NAM_groups_check_events"], 1)
                self.assertEqual(calls["ADISCORD_economy_mark_dirty"], int(support != 50))
                self.assertEqual(calls["force_update_dynamic_modifier"], int(support != 50))

    def test_monthly_drift_keeps_initialization_guard_and_missing_modifier_refresh(self):
        for initialized, modifier in product((False, True), repeat=2):
            facts = {
                ("NAM", "has_country_flag", "NAM_groups_initialized"): initialized,
                ("NAM", "has_dynamic_modifier", "NAM_loyalty_dynamic"): modifier,
            }
            for group in self.GROUPS:
                facts[("NAM", "variable", f"NAM_grp_{group}_support")] = 50
            calls = Counter()
            self.execute("NAM_groups_monthly", facts, calls)
            self.assertEqual(calls["NAM_groups_check_events"], int(initialized))
            self.assertEqual(calls["NAM_groups_refresh"], int(initialized and not modifier))

    def test_discipline_recovers_and_stops_refreshing_at_cap(self):
        facts = {
            ("NAM", "has_dynamic_modifier", "NAM_seal_discipline_dynamic"): True,
            ("NAM", "has_variable", "NAM_seal_org_factor"): True,
            ("NAM", "has_war", "no"): True,
            ("NAM", "variable", "NAM_seal_discipline"): 96,
            ("NAM", "variable", "NAM_seal_org_factor"): 0.046,
        }
        for expected, updates in ((99, 1), (100, 1), (100, 0), (100, 0)):
            calls = Counter()
            self.execute("NAM_seal_discipline_monthly", facts, calls)
            self.assertEqual(facts[("NAM", "variable", "NAM_seal_discipline")], expected)
            self.assertAlmostEqual(facts[("NAM", "variable", "NAM_seal_org_factor")], (expected - 50) / 1000)
            self.assertEqual(calls["force_update_dynamic_modifier"], updates)

    def test_discipline_unchanged_modifier_still_checks_event_thresholds(self):
        for value, event in ((0, 32), (24, 31), (49, 30), (50, None), (100, None)):
            facts = {
                ("NAM", "has_dynamic_modifier", "NAM_seal_discipline_dynamic"): True,
                ("NAM", "has_variable", "NAM_seal_org_factor"): True,
                ("NAM", "ADISCORD_nam_resource_war_active", "yes"): True,
                ("NAM", "variable", "NAM_seal_discipline"): value,
                ("NAM", "variable", "NAM_seal_org_factor"): (value - 50) / 1000,
            }
            calls = Counter()
            self.execute("NAM_seal_discipline_clamp", facts, calls)
            self.assertEqual(calls["force_update_dynamic_modifier"], 0)
            expected = Counter({f"{BASE}.{event}": 1}) if event else Counter()
            self.assertEqual(calls, expected)
            self.execute("NAM_seal_discipline_clamp", facts, calls)
            if value == 0:
                expected[f"{BASE}.31"] = 1
            self.assertEqual(calls, expected)

    def test_discipline_initial_zero_factor_and_casualty_accounting(self):
        facts = {
            ("NAM", "has_dynamic_modifier", "NAM_seal_discipline_dynamic"): True,
            ("NAM", "ADISCORD_nam_resource_war_active", "yes"): True,
            ("NAM", "variable", "NAM_seal_discipline"): 50,
            ("NAM", "variable", "NAM_seal_casualties_seen_k"): 10,
        }
        calls = Counter()
        self.execute("NAM_seal_discipline_clamp", facts, calls)
        self.assertEqual(calls["force_update_dynamic_modifier"], 1)
        self.assertEqual(facts[("NAM", "variable", "NAM_seal_org_factor")], 0)
        for casualties, expected in ((20, 48), (20, 48), (5, 48), (10, 47)):
            facts[("NAM", "variable", "casualties_k")] = casualties
            self.execute("NAM_seal_discipline_monthly", facts, calls)
            self.assertEqual(facts[("NAM", "variable", "NAM_seal_discipline")], expected)
            self.assertEqual(facts[("NAM", "variable", "NAM_seal_casualties_seen_k")], casualties)

    def test_exile_zero_quota_skips_divisions_and_positive_quota_preserves_order(self):
        body = self.normalize(self.effects["NAM_rw_exile_abandon_state"])
        owners = ("EFL", "NAM", "NAM", "AZH", "NAM")
        for quota in (0, 1, 2, 3, 5):
            facts = {("NAM", "variable", "NAM_exile_to_cut"): quota}
            loops = list(selected_effects(body, facts, "NAM"))
            self.assertEqual(len(loops), int(quota > 0))
            abandoned = []
            for _, loop in loops:
                self.assertEqual(loop.key, "every_state_division")
                owner_filter = block(block(loop.value, "limit"), "OWNER")
                for index, owner in enumerate(owners):
                    if not matches_conditions(owner_filter, facts, owner):
                        continue
                    payload = [e for e in loop.value if e.key != "limit"]
                    for _, entry in selected_effects(payload, facts, "NAM"):
                        if entry.key == "change_division_template":
                            self.assertEqual(scalar(entry.value, "division_template"), "Abandoned Columns")
                            abandoned.append(index)
                        elif entry.key == "subtract_from_temp_variable":
                            facts[("NAM", "variable", scalar(entry.value, "var"))] -= float(scalar(entry.value, "value"))
                        else:
                            self.fail(f"Unsupported evacuation effect: {entry.key}")
            self.assertEqual(abandoned, [1, 2, 4][:quota])
            self.assertEqual(facts[("NAM", "variable", "NAM_exile_to_cut")], max(0, quota - 3))

    def test_exile_fallback_and_diagnostic_scans_have_separate_guards(self):
        body = self.normalize(self.effects["NAM_rw_exile_evacuate"])
        fallback = [
            entry.value for entry in walk(body)
            if entry.key == "if"
            and any(
                scan.key == "every_state" and any(
                    condition.key == "state" and condition.value == "700"
                    for condition in walk(block(scan.value, "limit"))
                )
                for scan in entry.value
            )
        ]
        self.assertEqual(len(fallback), 1)
        for quota in (0, 1):
            facts = {("NAM", "variable", "NAM_exile_to_cut"): quota}
            self.assertEqual(matches_conditions(block(fallback[0], "limit"), facts, "NAM"), quota > 0)
        diagnostic = [
            entry.value for entry in body if entry.key == "if"
            and any(e.key == "log" for e in entry.value)
        ]
        self.assertEqual(len(diagnostic), 1)
        for debug in (False, True):
            facts = {("NAM", "is_debug", "yes"): debug}
            self.assertEqual(matches_conditions(block(diagnostic[0], "limit"), facts, "NAM"), debug)
        # Transport and attrition remain unconditional after the abandonment phase.
        self.assertEqual(len([e for e in body if e.key == "every_state"]), 1)
        self.assertIn("NAM_rw_exile_damage_army", [e.key for e in body])


class NamValidatorTests(unittest.TestCase):
    """Exercise the production validator without changing loaded game files."""

    def validate(self, sources=None, states=None):
        from tools.validators import validate_adiscord_nam_resource_war as validator

        original_read = validator.read
        original_state = validator.state_source
        sources = sources or {}
        states = states or {}

        def read_source(path):
            return sources[path] if path in sources else original_read(path)

        def read_state(state):
            return states[state] if state in states else original_state(state)

        with patch.object(validator, "ISSUES", []), patch.object(
            validator, "read", read_source
        ), patch.object(validator, "state_source", read_state), redirect_stdout(StringIO()):
            result = validator.main()
            return result, list(validator.ISSUES)

    def assert_rejected(self, message, **overrides):
        result, issues = self.validate(**overrides)
        self.assertEqual(result, 1)
        self.assertTrue(any(message in issue for issue in issues), issues)

    def test_current_campaign_passes(self):
        result, issues = self.validate()
        self.assertEqual((result, issues), (0, []))

    def test_orders_cannot_reuse_or_lock_ordinary_templates(self):
        units_path = "history/units/NAM.txt"
        units = read(units_path)
        effects_path = f"common/scripted_effects/{BASE}_effects.txt"
        effects = read(effects_path)
        for role, ordinary, mobilisation in (
            ("guard", "Capital Guard", "Mobilisation Guard"),
            ("infantry", "Line Infantry Brigade", "Mobilisation Infantry Brigade"),
        ):
            with self.subTest(role=role):
                locked = units.replace(
                    f'name = "{ordinary}"',
                    f'name = "{ordinary}"\n\tis_locked = yes',
                )
                self.assert_rejected(
                    f"ordinary {ordinary} must stay editable",
                    sources={units_path: locked},
                )
                rerouted = effects.replace(f'\\"{mobilisation}\\"', f'\\"{ordinary}\\"')
                self.assert_rejected(
                    f"paid {role} must use its fixed mobilisation template",
                    sources={effects_path: rerouted},
                )

    def test_wrong_stockpiles_still_fail(self):
        path = f"common/scripted_effects/{BASE}_effects.txt"
        source = read(path)
        for tag, amount in (("EFL", 30000), ("AZH", 18000), ("SLF", 18000), ("NAM", 15000)):
            with self.subTest(tag=tag):
                token = f"type = infantry_equipment amount = {amount} producer = {tag}"
                self.assertEqual(source.count(token), 1)
                changed = source.replace(token, token.replace(str(amount), str(amount // 10)))
                message = "emergency defence" if tag == "NAM" else f"stockpile for {tag}"
                self.assert_rejected(message, sources={path: changed})

    def test_global_one_shot_news_still_fail(self):
        from tools.validators.validate_adiscord_nam_resource_war import typed_blocks

        path = f"events/{BASE}_events.txt"
        source = read(path)
        for event in typed_blocks(source, "news_event"):
            event_id = re.search(r"\bid\s*=\s*(\S+)", event)[1]
            with self.subTest(event=event_id):
                changed = source.replace(event, event.replace("fire_only_once = no", "fire_only_once = yes"))
                self.assert_rejected(event_id, sources={path: changed})

    def test_debug_category_remains_debug_only_and_country_independent(self):
        path = "common/decisions/categories/ADISCORD_scenario_debug_categories.txt"
        source = read(path)
        for before, after in (("always = yes", "tag = NAM"), ("is_debug = yes", "always = yes")):
            with self.subTest(condition=before):
                self.assert_rejected("shared scenario debug category", sources={path: source.replace(before, after)})

    def test_old_capital_and_victory_points_still_fail(self):
        from tools.validators.validate_adiscord_nam_resource_war import state_source

        path = "history/countries/NAM - NamestnikLand.txt"
        self.assert_rejected("history capital", sources={path: read(path).replace("capital = 700", "capital = 689")})
        for state, before, after in (
            (67, "victory_points = { 6099 1 }", "victory_points = { 6099 1 }\n victory_points = { 1710 1 }"),
            (688, "victory_points = { 16721 5 }", "victory_points = { 689 5 }"),
            (689, "history = {", "history = {\n victory_points = { 2038 5 }"),
            (700, "victory_points = { 16716 5 }", "victory_points = { 16716 4 }"),
        ):
            source = state_source(state)
            with self.subTest(state=state):
                self.assertIn(before, source)
                self.assert_rejected(f"state {state}", states={state: source.replace(before, after)})


class NamBasinGuiTests(unittest.TestCase):
    """Map navigation must never pay for or start a district operation."""

    @classmethod
    def setUpClass(cls):
        root = block(parsed("common/scripted_guis/ADISCORD_NAM_scripted_gui.txt"), "scripted_gui")
        cls.panel = block(root, "ADISCORD_NAM_basin_panel")
        cls.effects = block(cls.panel, "effects")
        cls.triggers = block(cls.panel, "triggers")

    def test_all_six_map_markers_only_select_their_district(self):
        for state in (67, 688, 689, 690, 719, 700):
            click = block(self.effects, f"NAM_bw_select_{state}_click")
            self.assertEqual([entry.key for entry in click], ["set_variable"])
            self.assertEqual(scalar(block(click, "set_variable"), "NAM_bw_selected_state"), str(state))
            visible = block(self.triggers, f"NAM_bw_card_{state}_title_visible")
            if state == 67:
                visible = block(visible, "OR")
                self.assertEqual(scalar(block(visible, "NOT"), "has_variable"), "NAM_bw_selected_state")
            check = block(visible, "check_variable")
            self.assertEqual(scalar(check, "var"), "NAM_bw_selected_state")
            self.assertEqual(scalar(check, "value"), str(state))
            self.assertEqual(scalar(check, "compare"), "equals")

    def test_map_is_embedded_in_the_native_decision_category(self):
        self.assertEqual(scalar(self.panel, "context_type"), "decision_category")
        category = block(parsed(f"common/decisions/categories/{BASE}_categories.txt"), "NAM_national_programmes")
        self.assertEqual(scalar(category, "scripted_gui"), "ADISCORD_NAM_basin_panel")
        source = read("common/scripted_guis/ADISCORD_NAM_scripted_gui.txt")
        self.assertNotIn("NAM_bw_open", source)
        self.assertNotIn("NAM_bw_close_button", source)
        self.assertNotIn("every_country", source)

    def test_map_operations_keep_the_existing_targeted_decision_dispatch(self):
        for state in (67, 688, 689, 690, 719, 700):
            operations = ("line",) if state == 700 else ("repair", "refinery", "line")
            for operation in operations:
                click = block(self.effects, f"NAM_bw_{state}_{operation}_click")
                guarded = block(click, "if")
                limit = block(block(guarded, "limit"), str(state))
                self.assertEqual(scalar(limit, f"NAM_bw_{operation}_startable"), "yes")
                dispatch = block(guarded, "activate_targeted_decision")
                self.assertEqual(scalar(dispatch, "target"), str(state))
                decision = {"repair": "NAM_project_repair_wells", "refinery": "NAM_project_refinery", "line": "NAM_prepare_line"}[operation]
                self.assertEqual(scalar(dispatch, "decision"), decision)
                self.assertEqual([entry.key for entry in guarded], ["limit", "activate_targeted_decision"])

    def test_compact_categories_keep_every_group_input_and_rules(self):
        gui = read("interface/ADISCORD_NAM_basin.gui")
        for language in ("russian", "english"):
            loc = read(f"localisation/{language}/{BASE}_l_{language}.yml")
            for group in ("nam", "oil", "dist", "garr", "trade"):
                self.assertIn(f'NAM_bw_support_{group}', gui)
                row = re.search(rf'^ NAM_bw_support_{group}:.*$', loc, re.M).group()
                self.assertIn(f"NAM_grp_{group}_support", row)
                self.assertIn(f"NAM_grp_{group}_influence", row)
            self.assertRegex(loc, r'(?m)^ NAM_bw_support_rules:.*120.*')
            self.assertRegex(loc, r'(?m)^ NAM_bw_programme_rules:.*420.*')
            self.assertFalse("[?]" in loc, language)

    def test_card_controls_are_direct_scripted_gui_children(self):
        roots = block(parsed("interface/ADISCORD_NAM_basin.gui"), "guiTypes")
        window = next(e.value for e in roots if scalar(e.value, "name") == "ADISCORD_NAM_basin_window")
        controls = {scalar(e.value, "name"): e.value for e in window if isinstance(e.value, list) and e.key.endswith("Type")}
        for state in (67, 688, 689, 690, 719, 700):
            for part in ("title", "body"):
                name = f"NAM_bw_card_{state}_{part}"
                self.assertIn(name, controls)
                self.assertTrue(block(self.triggers, name + "_visible"))
            operations = ("line",) if state == 700 else ("repair", "refinery", "line")
            for operation in operations:
                for suffix in ("", "_price", "_duration"):
                    name = f"NAM_bw_{state}_{operation}{suffix}"
                    self.assertIn(name, controls)
                    self.assertIn("NAM_bw_selected_state", repr(block(self.triggers, name + "_visible")))
        self.assertIn("NAM_bw_port_guidance", controls)
        self.assertIn("NAM_bw_selected_state", repr(block(self.triggers, "NAM_bw_port_guidance_visible")))

    def test_gui_uses_native_decision_panels_and_resolved_tooltip_text(self):
        gui = read("interface/ADISCORD_NAM_basin.gui")
        self.assertNotIn('quadTextureSprite = "GFX_NAM_bw_panel"', gui)
        self.assertIn('quadTextureSprite = "GFX_ADISCORD_decisions_category_desc_bg"', gui)
        for language in ("russian", "english"):
            loc = read(f"localisation/{language}/{BASE}_l_{language}.yml")
            for line in loc.splitlines():
                if line.startswith(" NAM_bw_"):
                    self.assertNotIn("$", line)

    def test_each_selection_shows_one_card_with_its_own_operations(self):
        states = (67, 688, 689, 690, 719, 700)
        for selected in (None, *states):
            facts = {
                ("NAM", "has_variable", "NAM_bw_selected_state"): selected is not None,
                ("NAM", "variable", "NAM_bw_selected_state"): selected or 0,
                ("NAM", "has_completed_focus", "NAM_field_repair_crews"): True,
                ("NAM", "has_completed_focus", "NAM_refinery_programme"): True,
            }
            for state in states:
                facts[(str(state), "is_owned_by", "NAM")] = True
                facts[(str(state), "NAM_bw_line_offered", "yes")] = True
            for state in states:
                names = [f"NAM_bw_card_{state}_title", f"NAM_bw_card_{state}_body"]
                operations = ("line",) if state == 700 else ("repair", "refinery", "line")
                names.extend(f"NAM_bw_{state}_{operation}{suffix}" for operation in operations for suffix in ("", "_price", "_duration"))
                if state == 700:
                    names.append("NAM_bw_port_guidance")
                for name in names:
                    with self.subTest(selected=selected, widget=name):
                        self.assertEqual(matches_conditions(block(self.triggers, name + "_visible"), facts, "NAM"), state == (selected or 67))

    def test_map_geometry_and_generated_files_match(self):
        from tools.builders.build_adiscord_nam_basin_map import build_outputs, check_outputs

        outputs, geometry = build_outputs()
        self.assertEqual(set(geometry), {67, 688, 689, 690, 719, 700})
        for state, node in geometry.items():
            self.assertTrue(node["mask"].getbbox(), state)
            self.assertGreater(node["mask"].getpixel(node["anchor"]), 0, state)
        self.assertEqual(check_outputs(outputs), [])

    def test_support_texticons_cover_focus_and_decision_rewards(self):
        from PIL import Image

        sprites = block(parsed("interface/ADISCORD_NAM_basin.gfx"), "spriteTypes")
        definitions = {scalar(entry.value, "name"): entry.value for entry in sprites}
        for group in ("nam", "oil", "dist", "garr", "trade"):
            sprite = definitions[f"GFX_NAM_support_{group}_texticon"]
            with Image.open(ROOT / scalar(sprite, "texturefile")) as icon:
                self.assertEqual(icon.size, (20, 20))
                self.assertEqual(icon.mode, "RGBA")
            for language in ("russian", "english"):
                loc = read(f"localisation/{language}/{BASE}_l_{language}.yml")
                values = dict(re.findall(r'^ ([^ :]+):\d* "(.*)"$', loc, re.M))
                for key in (f"NAM_concede_{group}_tt", f"NAM_bribe_{group}_tt", f"NAM_favour_{group}_tt"):
                    self.assertRegex(values[key], rf'§[GRY][+-]\d+§! £NAM_support_{group}_texticon')
                self.assertIn(f"£NAM_support_{group}_texticon", values["NAM_grp_independence_day_tt"])


class NamPanelOptimizationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = block(parsed("common/scripted_guis/ADISCORD_NAM_scripted_gui.txt"), "scripted_gui")
        cls.basin = block(root, "ADISCORD_NAM_basin_panel")
        cls.piracy = block(root, "ADISCORD_NAM_piracy_panel")

    def test_hidden_card_buttons_skip_availability_and_selected_cards_keep_it(self):
        class ReadFacts(dict):
            def get(self, key, default=None):
                if key[1].endswith("_startable"):
                    self.reads.append(key)
                return super().get(key, default)

        states = (67, 688, 689, 690, 719, 700)
        triggers = block(self.basin, "triggers")
        for selection, available in product((None, *states, 0), (False, True)):
            for state in states:
                for operation in (("line",) if state == 700 else ("repair", "refinery", "line")):
                    facts = ReadFacts({
                        ("NAM", "has_variable", "NAM_bw_selected_state"): selection is not None,
                        ("NAM", "variable", "NAM_bw_selected_state"): selection or 0,
                        (str(state), f"NAM_bw_{operation}_startable", "yes"): available,
                    })
                    facts.reads = []
                    selected = state == (67 if selection is None else selection)
                    with self.subTest(selection=selection, state=state, operation=operation, available=available):
                        result = matches_conditions(block(triggers, f"NAM_bw_{state}_{operation}_click_enabled"), facts, "NAM")
                        self.assertEqual(result, selected and available)
                        self.assertEqual(len(facts.reads), int(selected))

    def test_line_offer_preserves_conditions_and_skips_neighbours_before_unlock(self):
        source = parsed(f"common/scripted_triggers/{BASE}_triggers.txt")
        offered = block(source, "NAM_bw_line_offered")
        neighbours = block(offered, "any_neighbor_state")
        self.assertEqual(scalar(block(neighbours, "NOT"), "is_owned_by"), "NAM")
        self.assertEqual(offered[-1].key, "any_neighbor_state")
        # Supply the result of the native neighbour predicate independently.
        fixture = [replace(e, value="yes") if e.key == "any_neighbor_state" else e for e in offered]
        for owned, prepared, focus, programme, foreign_neighbour in product((False, True), repeat=5):
            facts = {
                ("67", "is_owned_by", "NAM"): owned,
                ("67", "has_state_flag", "NAM_line_prepared"): prepared,
                ("NAM", "has_completed_focus", "NAM_line_survey"): focus,
                ("NAM", "NAM_line_programme_open", "yes"): programme,
                ("67", "any_neighbor_state", "yes"): foreign_neighbour,
            }
            self.assertEqual(matches_conditions(fixture, facts, "67"),
                             owned and not prepared and focus and programme and foreign_neighbour)
            if not focus or not programme:
                # An unsupported native iterator would fail this fixture if reached.
                self.assertFalse(matches_conditions(offered, facts, "67"))
        startable = block(source, "NAM_bw_line_startable")
        self.assertEqual(startable[-1].key, "NAM_bw_line_offered")
        for controlled, busy, operable, slot, price, offer in product((False, True), repeat=6):
            facts = {
                ("67", "is_controlled_by", "NAM"): controlled,
                ("67", "has_state_flag", "NAM_line_in_progress"): busy,
                ("NAM", "NAM_country_operable", "yes"): operable,
                ("NAM", "NAM_line_slot_free", "yes"): slot,
                ("NAM", "NAM_bw_can_pay_line", "yes"): price,
                ("67", "NAM_bw_line_offered", "yes"): offer,
            }
            self.assertEqual(matches_conditions(startable, facts, "67"),
                             controlled and not busy and operable and slot and price and offer)

    def gauge_frame(self, gauge, facts):
        """Evaluate only the documented temporary arithmetic used by GUI properties."""
        arithmetic = {
            "set_temp_variable": lambda old, value: value,
            "subtract_from_temp_variable": lambda old, value: old - value,
            "divide_temp_variable": lambda old, value: old / value,
            "modulo_temp_variable": lambda old, value: old % value,
            "add_to_temp_variable": lambda old, value: old + value,
        }
        trigger = block(block(self.piracy, "triggers"), f"NAM_pw_{gauge}_track_visible")
        for scope, entry in selected_effects(trigger, facts, "NAM"):
            if entry.key in arithmetic:
                name = scalar(entry.value, "var")
                reference = scalar(entry.value, "value")
                value = facts.get((scope, "variable", reference))
                if value is None:
                    value = Decimal(0) if reference.startswith("NAM_") else Decimal(reference)
                key = (scope, "variable", name)
                facts[key] = arithmetic[entry.key](facts.get(key, Decimal(0)), value)
            elif entry.key == "clamp_temp_variable":
                key = (scope, "variable", scalar(entry.value, "var"))
                facts[key] = min(Decimal(scalar(entry.value, "max")),
                                 max(Decimal(scalar(entry.value, "min")), facts[key]))
            elif entry.key == "always":
                self.assertEqual(entry.value, "yes")
            else:
                self.fail(f"Unexpected GUI arithmetic or persistent write: {entry.key}")
        return facts[("NAM", "variable", f"NAM_pw_{gauge}_frame")]

    def test_gauge_frames_match_strict_thresholds_and_refresh_in_both_directions(self):
        thresholds = [Decimal("2.5") + 5 * i for i in range(20)]
        values = {Decimal(v) / 1000 for v in range(0, 100001, 137)}
        values.update(t + offset for t in thresholds for offset in (Decimal("-0.001"), Decimal(0), Decimal("0.001")))
        values.update(map(Decimal, (-20, 0, 100, 120)))
        for gauge, variable in (("notoriety", "NAM_pirate_notoriety"), ("revenge", "NAM_revenge_readiness")):
            facts = {}
            for value in [*sorted(values), *sorted(values, reverse=True), None]:
                key = ("NAM", "variable", variable)
                if value is None:
                    facts.pop(key, None)
                else:
                    facts[key] = value
                expected = 1 + sum((value or 0) > threshold for threshold in thresholds)
                with self.subTest(gauge=gauge, value=value):
                    self.assertEqual(self.gauge_frame(gauge, facts), expected)
                    self.assertEqual(facts.get(key), value)

    def test_gauge_atlas_pixels_match_the_track_and_twenty_individual_cells(self):
        from PIL import Image
        from tools.builders.build_adiscord_nam_piracy_map import gauge_image, png_bytes
        from io import BytesIO

        with Image.open(ROOT / "gfx/interface/NAM_piracy/segment.png") as source:
            cells = source.copy()
        for gauge, ticks in (("notoriety", (50, 75)), ("revenge", (70,))):
            with Image.open(ROOT / f"gfx/interface/NAM_piracy/gauge_{gauge}.png") as source:
                atlas = source.copy()
            self.assertEqual(atlas.size, (204 * 21, 18))
            with Image.open(BytesIO(png_bytes(gauge_image(ticks)))) as source:
                expected = source.copy()
            for lit in range(21):
                if lit:
                    colour = (1 if lit <= 10 else 2 if lit <= 15 else 3) if gauge == "notoriety" else (4 if lit <= 14 else 5)
                    cell = cells.crop(((colour - 1) * 9, 0, colour * 9, 10))
                    expected.alpha_composite(cell, (2 + (lit - 1) * 10, 4))
                self.assertEqual(atlas.crop((lit * 204, 0, (lit + 1) * 204, 18)).tobytes(), expected.tobytes(), (gauge, lit))

    def test_two_direct_gauge_controls_have_live_frame_bindings_and_no_dirty(self):
        roots = block(parsed("interface/ADISCORD_NAM_piracy.gui"), "guiTypes")
        window = next(e.value for e in roots if scalar(e.value, "name") == "ADISCORD_NAM_piracy_window")
        controls = {scalar(e.value, "name"): e.value for e in window if e.key.endswith("Type")}
        self.assertFalse(any(re.fullmatch(r"NAM_pw_(notoriety|revenge)_\d+", name) for name in controls))
        sprites = {scalar(e.value, "name"): e.value for e in block(parsed("interface/ADISCORD_NAM_piracy.gfx"), "spriteTypes")}
        for gauge, row in (("notoriety", 362), ("revenge", 406)):
            name = f"NAM_pw_{gauge}_track"
            position = block(controls[name], "position")
            self.assertEqual((scalar(position, "x"), scalar(position, "y")), ("150", str(row)))
            self.assertEqual(scalar(block(block(self.piracy, "properties"), name), "frame"), f"NAM_pw_{gauge}_frame")
            self.assertEqual(scalar(sprites[f"GFX_NAM_pw_gauge_{gauge}"], "noOfFrames"), "21")
        for panel in (self.basin, self.piracy):
            self.assertNotIn("dirty", [e.key for e in panel])


class NamQolTests(unittest.TestCase):
    def test_petitions_share_a_pause_without_blocking_an_existing_coup(self):
        effects = parsed(f"common/scripted_effects/{BASE}_effects.txt")
        groups = block(effects, "NAM_groups_check_events")
        guard = block(block(groups, "if"), "limit")
        self.assertTrue(matches_conditions(guard, {}, "NAM"))
        for key, value in (
            ("has_country_flag", "NAM_grp_event_pending"),
            ("has_country_flag", "NAM_rival_event_pending"),
            ("has_country_flag", "NAM_political_petition_cooldown"),
            ("has_active_mission", "NAM_rival_demand"),
        ):
            self.assertFalse(matches_conditions(guard, {("NAM", key, value): True}, "NAM"))
        close = block(effects, "NAM_groups_close_event")
        self.assertEqual(close[0].key, "set_country_flag")
        self.assertEqual(scalar(close[0].value, "flag"), "NAM_political_petition_cooldown")
        self.assertEqual(scalar(close[0].value, "days"), "90")
        self.assertEqual(close[-1].key, "NAM_groups_refresh")
        for entry in walk(groups):
            if entry.key == "set_country_flag" and isinstance(entry.value, list):
                flag = scalar(entry.value, "flag")
                expected = "90" if flag == "NAM_political_petition_cooldown" else "360"
                self.assertEqual(scalar(entry.value, "days"), expected)
        rivals = block(effects, "NAM_rivals_monthly")
        coup = block(block(rivals, "if"), "limit")
        self.assertNotIn("NAM_political_petition_cooldown", repr(coup))
        triggers = parsed(f"common/scripted_triggers/{BASE}_triggers.txt")
        cycle = block(triggers, "NAM_rival_cycle_open")
        self.assertIn("NAM_political_petition_cooldown", repr(cycle))
        self.assertIn("NAM_grp_event_pending", repr(cycle))

    def test_underground_actions_explain_temporary_blockers(self):
        categories = parsed(f"common/decisions/categories/{BASE}_categories.txt")
        underground = block(categories, "NAM_underground")
        self.assertEqual(scalar(block(underground, "visible"), "has_variable"), "NAM_underground")
        for name in ("NAM_underground", "NAM_national_programmes", "NAM_treasury", "NAM_overseas_districts"):
            self.assertEqual(scalar(block(categories, name), "visible_when_empty"), "yes")
        decisions = block(parsed(f"common/decisions/{BASE}_decisions.txt"), "NAM_underground")
        for number in (1, 2, 3):
            decision = block(decisions, f"NAM_weber_talks_{number}")
            self.assertNotIn("NAM_weber_talks_possible", repr(block(decision, "visible")))
            self.assertIn("NAM_weber_talks_possible", repr(block(decision, "available")))
        searches = block(decisions, "NAM_hunt_caches")
        self.assertNotIn("NAM_caches_searched", repr(block(searches, "visible")))
        self.assertIn("NAM_caches_searched", repr(block(searches, "available")))

    def test_support_colours_respect_fractional_thresholds(self):
        definitions = parsed(f"common/scripted_localisation/{BASE}_scripted_loc.txt")
        cases = ((25, "penalty"), (25.5, "neutral"), (69.5, "neutral"),
                 (70, "bonus"), (84.5, "bonus"), (85, "demand"))
        for group, name in (("nam", "Nam"), ("oil", "Oil"), ("dist", "Dist"), ("garr", "Garr"), ("trade", "Trade")):
            definition = next(e.value for e in definitions if scalar(e.value, "name") == f"NAMSupport{name}Colour")
            for support, colour in cases:
                facts = {("NAM", "variable", f"NAM_grp_{group}_support"): support}
                for entry in definition:
                    if entry.key != "text":
                        continue
                    triggers = [e.value for e in entry.value if e.key == "trigger"]
                    if not triggers or matches_conditions(triggers[0], facts, "NAM"):
                        self.assertEqual(scalar(entry.value, "localization_key"), f"NAM_bw_colour_{colour}")
                        break
                else:
                    self.fail("Missing support colour fallback")


if __name__ == "__main__":
    unittest.main()
