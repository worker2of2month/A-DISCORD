"""Parsed NAM campaign scenarios; native loading and UI need a fresh game."""

from dataclasses import replace
from decimal import Decimal
from collections import ChainMap, Counter
from contextlib import redirect_stdout
from io import StringIO
from itertools import permutations, product
from pathlib import Path
import json
import re
import unittest
from unittest.mock import patch

from tools.builders.build_adiscord_focus_trees import expected_outputs
from tools.tests.test_adiscord_stp_preparation import (
    block, scalar, walk, matches_conditions, selected_effects, focus_exclusion_crossings,
    event_target,
)
from tools.validators.validate_adiscord_division_templates import parse_clausewitz
from tools.validators.validate_adiscord_english_localisation import ENTRY
from tools.validators.validate_adiscord_nam_resource_war import (
    balanced_braces,
    has_script_fragment,
)

ROOT = Path(__file__).resolve().parents[2]
BASE = "ADISCORD_nam_resource_war"
# Global event target naming the country that currently is Vorkerland. After the
# civil war it names the claimant that unified the country on its own tag, and
# that claimant carries the flag of its route.
VORKERLAND = "ADISCORD_vorkerland_nation"
VORKERLAND_SCOPE = "event_target:" + VORKERLAND
VORKERLAND_UNIFIERS = (("worker", "WKR"), ("joint", "VAD"), ("utilitarian", "TVA"))
TREES = {
    "main": ("focus_trees/NAM/main/focuses.txt", "NAM_focus", "ADISCORD_NAM_focus.txt"),
    "wartime": ("focus_trees/NAM/wartime/focuses.txt", "NAM_resource_war_focus", "ADISCORD_NAM_wartime.txt"),
    "postwar": ("focus_trees/NAM/postwar/focuses.txt", "NAM_postwar_focus", "ADISCORD_NAM_postwar.txt"),
    "defeated": ("focus_trees/NAM/defeated/focuses.txt", "NAM_defeated_focus", "ADISCORD_NAM_defeated.txt"),
    "exile_radical": ("focus_trees/NAM/exile_radical/focuses.txt", "NAM_exile_radical_focus",
                      "ADISCORD_NAM_exile_radical.txt"),
    "exile_humanist": ("focus_trees/NAM/exile_humanist/focuses.txt", "NAM_exile_humanist_focus",
                       "ADISCORD_NAM_exile_humanist.txt"),
    "exile_corporate": ("focus_trees/NAM/exile_corporate/focuses.txt", "NAM_exile_corporate_focus",
                        "ADISCORD_NAM_exile_corporate.txt"),
    "south_war": ("focus_trees/NAM/south_war/focuses.txt", "NAM_south_war_focus", "ADISCORD_NAM_south_war.txt"),
}
EXILE = ("exile_radical", "exile_humanist", "exile_corporate")
NATIONAL_CATEGORIES = ("NAM_national_programmes", "NAM_mobilisation", "NAM_basin_economy", "NAM_administration",
                       "NAM_postwar_orders", "NAM_postwar_programmes")
BOARD_PROFILES = (
    (("output", 1), ("construction", 2)),
    (("output", 2), ("growth", 3)),
    (("naval", 3), ("dockyards", 3)),
    (("output", 3), ("ceiling", 1)),
    (("construction", 2), ("growth", 2)),
    (("construction", 3), ("goods", -1)),
)


class BoardVariables(ChainMap):
    """Read indexed operands at their current loop index when selecting a script branch."""

    def __init__(self, facts, read_amount):
        super().__init__(facts)
        self.read_amount = read_amount

    def get(self, key, default=None):
        if len(key) == 3 and key[1] == "variable":
            name = key[2]
            if name == "global.num_days":
                return self.maps[0].get(("global", "variable", "num_days"), default)
            if name.startswith("NAM_board_") and "^" in name and not name.endswith("^num"):
                return self.read_amount(name, key[0])
        return self.maps[0].get(key, default)


class FuelLogistics(ChainMap):
    def get(self, key, default=None):
        if len(key) == 3 and key[1:] == ("fixture_federal_district_member", "PREV"):
            facts = self.maps[0]
            return facts.get(("fixture", "accession_country")) in facts.get((key[0], "array", "NAM_federal_districts"), ())
        if len(key) == 3 and key[1] == "fixture_any_defender":
            return any(matches_conditions(key[2], self, country)
                       for country in self.maps[0].get(("global", "array", "RUS_crisis_defenders"), ()))
        if len(key) == 3 and key[1:] == ("fixture_registered_in", "global.RUS_crisis_defenders"):
            return key[0] in self.maps[0].get(("global", "array", "RUS_crisis_defenders"), ())
        if len(key) == 3 and key[1:] == ("variable", "fixture_fuel_room_k"):
            facts = self.maps[0]
            room = facts[(key[0], "fuel_capacity")] - facts[(key[0], "numeric", "has_fuel")]
            return room / 1000
        return self.maps[0].get(key, default)


class BoardSites(ChainMap):
    def get(self, key, default=None):
        if len(key) == 3 and key[1] == "fixture_owned_board_site":
            return any(matches_conditions(key[2], self, state)
                       for state in self.maps[0].get(("fixture", "board_sites"), ()))
        return self.maps[0].get(key, default)


class PostedGarrisons(dict):
    def get(self, key, default=None):
        if len(key) == 3 and key[1] == "fixture_any_conquered_district":
            return any(matches_conditions(key[2], self, state)
                       for state in self[(key[0], "array", "NAM_conquered_states")])
        return super().get(key, default)


def read(path):
    return (ROOT / path).read_text(encoding="utf-8-sig")


def parsed(path):
    return parse_clausewitz(read(path))


def national_decisions():
    """National orders: the map panel's category and its departments."""
    source = parsed(f"common/decisions/{BASE}_decisions.txt")
    return {e.key: e.value for category in NATIONAL_CATEGORIES for e in block(source, category)}


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
    def test_incident_timeout_text_selects_the_actual_settlement_branch(self):
        definitions = parsed(f"common/scripted_localisation/{BASE}_scripted_loc.txt")
        definition = next(e.value for e in definitions
                          if scalar(e.value, "name") == "NAMIncidentTimeoutOutcome")
        texts = [e.value for e in definition if e.key == "text"]
        branches = [e.value for e in self.effects["NAM_crisis_response_timeout"]
                    if e.key in ("if", "else_if", "else")]
        self.assertEqual(len(texts), len(branches))
        for number in range(1, 6):
            for fire, insurance, pension, fund, paid in product((False, True), repeat=5):
                facts = self.crisis_facts(number)
                facts.update({
                    ("NAM", "has_global_flag", BASE + "_nam_victory"): True,
                    ("NAM", "has_completed_focus", "NAM_field_firefighters"): fire,
                    ("NAM", "has_completed_focus", "NAM_pw_insurance_fund"): insurance,
                    ("NAM", "has_completed_focus", "NAM_pw_family_pensions"): pension,
                    ("NAM", "has_country_flag", "NAM_crisis_fund"): fund,
                    ("NAM", "has_country_flag", "NAM_industrial_claim_paid"): paid,
                })
                shown = next(i for i, text in enumerate(texts)
                             if self.matches(block(text, "trigger"), facts))
                settled = next(i for i, branch in enumerate(branches)
                               if self.matches(block(branch, "limit"), facts))
                self.assertEqual(shown, settled, (number, fire, insurance, pension, fund, paid))
        for language in ("russian", "english"):
            values = {m.group(1): m.group(2) for line in read(
                f"localisation/{language}/{BASE}_l_{language}.yml").splitlines()
                if (m := ENTRY.fullmatch(line))}
            self.assertIn("[NAMIncidentTimeoutOutcome]", values["NAM_incident_response_timeout_tt"])
            for text in texts:
                self.assertTrue(values[scalar(text, "localization_key")])
            for suffix, numbers in {
                "fire": ("-8000",), "strike": ("-3%",), "scandal": ("-2%",),
                "customs": ("-2%", "+5", "+100", "+250"),
                "garrison": ("-2%", "-2000"),
            }.items():
                for number in numbers:
                    self.assertIn(number, values[f"NAM_incident_timeout_{suffix}"])

    def test_delayed_returns_and_southern_deadline_have_phase_tooltips(self):
        decisions = {d.key: d.value for category in parsed(f"common/decisions/{BASE}_decisions.txt")
                     for d in category.value if isinstance(d.value, list)}
        for decision, phase, tooltip in (
            ("NAM_program_air_supply", "remove_effect", "NAM_air_bridge_end_tt"),
            ("NAM_hire_relief_shift", "remove_effect", "NAM_labour_shift_ends_tt"),
            ("NAM_hire_relief_shift", "cancel_effect", "NAM_labour_shift_ends_tt"),
            ("NAM_hum_refit_landing_transports", "cancel_effect", "NAM_hum_refit_aborted_tt"),
            ("ADISCORD_south_preparation", "timeout_effect", "ADISCORD_south_preparation_timeout_tt"),
        ):
            self.assertEqual(scalar(block(decisions[decision], phase), "custom_effect_tooltip"), tooltip)

    def test_metropolitan_rule_tooltip_preserves_programme_lifecycle(self):
        tooltip = block(self.triggers["NAM_independent_programmes_operable"], "custom_trigger_tooltip")
        self.assertEqual(scalar(tooltip, "tooltip"), "NAM_metropolitan_rule_ended_tt")
        self.assertEqual(scalar(tooltip, "has_country_flag"), "NAM_center_vanished")
        for ended, subject, capitulated, exists in product((False, True), repeat=4):
            facts = self.independent_facts()
            facts[("NAM", "has_country_flag", "NAM_center_vanished")] = ended
            facts[("NAM", "is_subject", "no")] = not subject
            facts[("NAM", "has_capitulated", "no")] = not capitulated
            facts[("NAM", "exists", "yes")] = exists
            self.assertEqual(
                self.matches(self.triggers["NAM_independent_programmes_operable"], facts),
                ended and not subject and not capitulated and exists,
            )
            for collapse_started in (False, True):
                facts[("NAM", "has_global_flag", "ADISCORD_vorkerland_collapse_wars_started")] = collapse_started
                self.assertEqual(self.matches(self.triggers["NAM_colony_phase"], facts),
                                 not ended and not collapse_started)

    def test_agreement_draws_use_native_weight_modifiers(self):
        for effect, expected in (("NAM_agreements_monthly", 10), ("NAM_agreement_check_crisis", 5)):
            choices = [
                option.value for entry in walk(self.effects[effect]) if entry.key == "random_list"
                for option in entry.value if option.key == "20"
            ]
            self.assertEqual(len(choices), expected)
            for choice in choices:
                self.assertFalse(any(entry.key == "trigger" for entry in choice))
                self.assertTrue(any(
                    entry.key == "modifier" and scalar(entry.value, "factor") == "0"
                    for entry in choice
                ))

    def test_neighbor_governors_dispatch_in_character_scope(self):
        dispatch = self.effects["NAM_sync_neighbor_governor"]
        for branch, tag in (("if", "EFL"), ("else_if", "AZH")):
            target = block(dispatch, branch)
            self.assertEqual(scalar(block(target, "limit"), "tag"), tag)
            self.assertEqual(scalar(block(target, tag + "_NAM_governor"), "NAM_sync_governor_roles"), "yes")
        roles = self.effects["NAM_sync_governor_roles"]
        parties = {entry.value for entry in walk(roles) if entry.key == "has_government"}
        self.assertEqual(parties, {"humanism", "utilitarism", "chauvinism", "pragmatism",
                                   "anarchism", "technocracy", "etatism", "hedonism"})
        for action in ("add_country_leader_role", "remove_country_leader_role"):
            ideologies = {
                scalar(block(entry.value, "country_leader") if action == "add_country_leader_role"
                       else entry.value, "ideology")
                for entry in walk(roles) if entry.key == action
            }
            self.assertEqual(ideologies, {party + "_ideology" for party in parties})

    def test_debug_console_commands_share_decision_handlers_and_active_war_guard(self):
        commands = ("resolve_nam_victory", "resolve_coalition_victory", "resolve_compromise",
                    "resolve_standoff", "start_resource_war", "prepare_etatism",
                    "prepare_pragmatism", "prepare_humanism")
        events = {scalar(e.value, "id"): e.value for e in parsed("events/ADISCORD_scenario_debug_events.txt")
                  if e.key == "country_event"}
        decisions = block(parsed("common/decisions/ADISCORD_scenario_debug_decisions.txt"),
                          "ADISCORD_scenario_debug_category")
        for index, short in enumerate(commands, 1):
            name = "ADISCORD_nam_debug_" + short
            event = events[f"ADISCORD_nam_debug.{index}"]
            self.assertEqual(scalar(event, "hidden"), "yes")
            self.assertEqual(scalar(event, "is_triggered_only"), "yes")
            self.assertEqual([(e.key, e.value) for e in block(event, "immediate")], [(name, "yes")])
            decision = block(decisions, name)
            self.assertEqual(scalar(decision, "cost"), "0")
            self.assertEqual(scalar(block(decision, "ai_will_do"), "factor"), "0")
            self.assertIn((name, "yes"), [(e.key, e.value) for e in walk(block(decision, "complete_effect"))])
            if index > 4:
                continue
            for started, resolved in ((False, False), (True, False), (False, True), (True, True)):
                facts = self.facts()
                facts[("NAM", "has_global_flag", BASE + "_started")] = started
                facts[("NAM", "has_global_flag", BASE + "_resolved")] = resolved
                selected = [e.key for _, e in selected_effects(self.expand(self.effects[name]), facts, "NAM")]
                self.assertEqual(selected, [BASE + "_" + short] if started and not resolved else [], name)
                self.assertEqual(self.matches(block(decision, "visible"), facts), started and not resolved)

    def test_debug_balance_presets_only_change_unrecorded_live_balance(self):
        for course, value in (("etatism", -0.5), ("pragmatism", 0), ("humanism", 0.5)):
            effect = self.effects["ADISCORD_nam_debug_prepare_" + course]
            for state in ("open", "recorded", "started", "resolved", "no_ladder"):
                facts = self.mandate_facts(0.1)
                facts[("NAM", "tag", "NAM")] = True
                facts[("NAM", "has_global_flag", BASE + "_started")] = state == "started"
                facts[("NAM", "has_global_flag", BASE + "_resolved")] = state == "resolved"
                if state == "recorded":
                    facts[("NAM", "has_variable", "NAM_prewar_balance")] = True
                elif state == "no_ladder":
                    facts[("NAM", "fixture_power_balance", "NAM_ladder_bop")] = False
                chosen = list(selected_effects(self.expand(effect), facts, "EFL"))
                if state != "open":
                    self.assertEqual(chosen, [], (course, state))
                    continue
                self.assertEqual(len(chosen), 1)
                scope, payload = chosen[0]
                self.assertEqual((scope, payload.key), ("NAM", "set_power_balance"))
                self.assertEqual(scalar(payload.value, "id"), "NAM_ladder_bop")
                self.assertEqual(float(scalar(payload.value, "set_value")), value)
                facts[("NAM", "power_balance_value", "NAM_ladder_bop")] = value
                self.apply(self.effects["NAM_freeze_prewar_mandate"], facts)
                self.assertEqual(facts[("NAM", "ruling_party")], course)

    def test_debug_start_preserves_campaign_lifecycle_and_cannot_restart_after_peace(self):
        facts = self.facts()
        facts[("NAM", "has_global_flag", BASE + "_started")] = False
        for flag in ("ADISCORD_fresh_campaign_contract_v1", "ADISCORD_vorkerland_collapse_wars_started"):
            facts[("NAM", "has_global_flag", flag)] = True
        for country, states in (("NAM", (67, 688, 689, 690, 700, 719)),
                                ("EFL", (68, 70, 691, 701, 720, 721, 723, 724, 725, 726)),
                                ("AZH", (69, 692, 722, 727, 728, 729))):
            facts[("NAM", "country_exists", country)] = True
            facts[(country, "is_subject", "no")] = True
            facts[(country, "has_war", "no")] = True
            for state in states:
                facts[(country, "controls_state", str(state))] = True
        source = self.effects["ADISCORD_nam_debug_start_resource_war"]
        calls = lambda: [e.key for _, e in selected_effects(self.expand(source), facts, "NAM")]
        self.assertEqual(calls(), [BASE + "_start"])
        for flag in (BASE + "_started", BASE + "_resolved"):
            facts[("NAM", "has_global_flag", flag)] = True
            self.assertEqual(calls(), [])
            facts[("NAM", "has_global_flag", flag)] = False
        facts[("NAM", "has_global_flag", "ADISCORD_vorkerland_collapse_wars_started")] = False
        self.assertEqual(calls(), [])
        self.assertFalse(any(e.key in ("set_global_flag", "clr_global_flag") for e in walk(source)))

    def mandate_facts(self, balance, leader="NAM_Egor_Rom", ideology="service_etatism"):
        facts = self.facts()
        facts[("fixture", "track_leadership")] = True
        facts[("NAM", "fixture_power_balance", "NAM_ladder_bop")] = True
        facts[("NAM", "power_balance_value", "NAM_ladder_bop")] = balance
        facts[("NAM", "ruling_leader")] = leader
        facts[("NAM", "ruling_party")] = "etatism"
        facts[("NAM", "has_country_leader_ideology", ideology)] = True
        facts[("NAM", "leader_role", leader, ideology)] = True
        return facts

    def test_prewar_mandate_boundaries_freeze_exact_native_balance_once(self):
        for balance, ideology, party in (
                (-1, "etatism_ideology", "etatism"),
                (-0.2501, "etatism_ideology", "etatism"),
                (-0.25, "pragmatism_ideology", "pragmatism"),
                (0, "pragmatism_ideology", "pragmatism"),
                (0.25, "pragmatism_ideology", "pragmatism"),
                (0.2501, "humanism_ideology", "humanism"),
                (1, "humanism_ideology", "humanism")):
            with self.subTest(balance=balance):
                facts = self.mandate_facts(balance)
                self.apply(self.effects["NAM_freeze_prewar_mandate"], facts)
                self.assertEqual(facts[("NAM", "variable", "NAM_prewar_balance")], balance)
                self.assertEqual(facts[("NAM", "ruling_party")], party)
                self.assertEqual(facts[("NAM", "ruling_leader")], "NAM_Egor_Rom")
                active = [key[3] for key, value in facts.items()
                          if key[:3] == ("NAM", "leader_role", "NAM_Egor_Rom") and value]
                self.assertEqual(active, [ideology])
                facts[("NAM", "power_balance_value", "NAM_ladder_bop")] = -balance + 0.1
                before = facts.copy()
                self.apply(self.effects["NAM_adopt_service_etatism"], facts)
                self.assertEqual(facts, before)
                self.apply(self.effects["NAM_freeze_prewar_mandate"], facts)
                self.assertEqual(facts, before)
        start = self.effects["ADISCORD_nam_resource_war_begin_hostilities"]
        opening = next(e.value for e in start if e.key == "NAM")
        self.assertEqual([e.key for e in opening[:2]],
                         ["NAM_agreement_cancel", "NAM_freeze_prewar_mandate"])
        self.assertEqual(sum(e.key == "NAM_freeze_prewar_mandate" for e in walk(start)), 1)

    def test_left_mandate_preserves_direction_for_magnitude_and_signed_scalars(self):
        for native_scalar in (0.6, -0.6):
            facts = self.mandate_facts(-0.6)
            facts[("NAM", "fixture_native_balance_scalar")] = native_scalar
            self.apply(self.effects["NAM_freeze_prewar_mandate"], facts)
            self.assertEqual(facts[("NAM", "variable", "NAM_prewar_balance")], -0.6)
            self.assertEqual(facts[("NAM", "ruling_party")], "etatism")
            self.assertTrue(self.matches(self.triggers["NAM_prewar_service_mandate"], facts))
            self.assertFalse(self.matches(self.triggers["NAM_prewar_district_mandate"], facts))

    def test_right_mandate_uses_native_direction_even_for_inverted_scalar(self):
        for native_scalar in (-0.6, 0.6):
            facts = self.mandate_facts(0.6)
            facts[("NAM", "fixture_native_balance_scalar")] = native_scalar
            self.apply(self.effects["NAM_freeze_prewar_mandate"], facts)
            self.assertEqual(facts[("NAM", "variable", "NAM_prewar_balance")], 0.6)
            self.assertEqual(facts[("NAM", "ruling_party")], "humanism")

    def test_prewar_mandate_preserves_usurper_and_zero_without_ladder(self):
        for leader in ("NAM_Vera_Pechat", "NAM_Arseny_Klyuch", "NAM_Taras_Shtyk", "NAM_Lev_Gavanov"):
            facts = self.mandate_facts(0.7, leader, "etatism_ideology")
            self.apply(self.effects["NAM_freeze_prewar_mandate"], facts)
            self.assertEqual(facts[("NAM", "ruling_leader")], leader)
            self.assertEqual(facts[("NAM", "ruling_party")], "etatism")
            self.assertEqual(facts[("NAM", "variable", "NAM_prewar_balance")], 0.7)
        facts = self.mandate_facts(0.7)
        facts[("NAM", "fixture_power_balance", "NAM_ladder_bop")] = False
        self.apply(self.effects["NAM_freeze_prewar_mandate"], facts)
        self.assertEqual(facts[("NAM", "variable", "NAM_prewar_balance")], 0)
        self.assertEqual(facts[("NAM", "ruling_party")], "pragmatism")

    def test_postwar_constitution_follows_frozen_balance_not_focus_or_live_bop(self):
        for balance in (-0.7, -0.25, 0, 0.25, 0.7):
            for old_focus in ("NAM_districts", "NAM_vertical"):
                facts = self.mandate_facts(balance)
                facts[("NAM", "tag", "NAM")] = True
                facts[("NAM", "is_subject", "no")] = True
                facts[("NAM", "has_global_flag", BASE + "_nam_victory")] = True
                self.apply(self.effects["NAM_freeze_prewar_mandate"], facts)
                facts[("NAM", "has_completed_focus", old_focus)] = True
                facts[("NAM", "power_balance_value", "NAM_ladder_bop")] = -balance
                for name, expected in (("NAM_service_state", balance < -0.25),
                                       ("NAM_federal_charter", balance > 0.25),
                                       ("NAM_pragmatic_compact", -0.25 <= balance <= 0.25)):
                    self.assertEqual(self.matches(block(self.postwar[name], "available"), facts),
                                     expected, (balance, old_focus, name))

    def test_humanist_rom_leaves_party_before_coup_or_political_successor(self):
        for final, character, party in (
                ("NAM_apply_ending_federation", "NAM_Nadezhda_Okrug", "humanism"),
                ("NAM_apply_ending_oil_union", "NAM_Kirill_Vykup", "etatism")):
            facts = self.mandate_facts(0.7)
            self.apply(self.effects["NAM_freeze_prewar_mandate"], facts)
            payload = block(block(self.effects[final], "else"), "hidden_effect")
            self.apply(payload, facts)
            self.assertEqual(facts[("NAM", "ruling_leader")], character)
            self.assertEqual(facts[("NAM", "ruling_party")], party)
            self.assertFalse(facts[("NAM", "leader_role", "NAM_Egor_Rom", "humanism_ideology")])
        for rival, character in enumerate(("NAM_Vera_Pechat", "NAM_Arseny_Klyuch", "NAM_Taras_Shtyk", "NAM_Lev_Gavanov"), 1):
            facts = self.mandate_facts(0.7)
            self.apply(self.effects["NAM_freeze_prewar_mandate"], facts)
            facts[("NAM", "variable", "NAM_rival_current")] = rival
            payload = self.effects["NAM_coup_install"]
            stop = next(i for i, e in enumerate(payload) if e.key == "add_timed_idea")
            self.apply(payload[:stop], facts)
            self.assertEqual(facts[("NAM", "ruling_leader")], character)
            self.assertEqual(facts[("NAM", "ruling_party")], "etatism")
            self.assertFalse(facts[("NAM", "leader_role", "NAM_Egor_Rom", "humanism_ideology")])

    def test_prewar_forecast_uses_stored_result_after_live_balance_changes(self):
        definitions = parsed(f"common/scripted_localisation/{BASE}_scripted_loc.txt")
        course = next(e.value for e in definitions if scalar(e.value, "name") == "NAMGetPrewarCourse")
        for balance, expected in ((-0.7, "vertical"), (-0.25, "service"), (0, "service"), (0.25, "service"), (0.7, "districts")):
            facts = self.mandate_facts(balance)
            for frozen in (False, True):
                if frozen:
                    self.apply(self.effects["NAM_freeze_prewar_mandate"], facts)
                    facts[("NAM", "power_balance_value", "NAM_ladder_bop")] = -balance
                shown = []
                for choice in (e.value for e in course if e.key == "text"):
                    conditions = next((e.value for e in choice if e.key == "trigger"), [])
                    if self.matches(conditions, facts):
                        shown.append(scalar(choice, "localization_key"))
                        break
                self.assertEqual(shown, ["NAM_prewar_course_" + expected])

    def captured_field_facts(self):
        facts = self.facts()
        facts[("NAM", "has_completed_focus", "NAM_wells_under_guard")] = False
        facts[("EFL", "has_war_with", "NAM")] = True
        for state, capacity in (("67", 5), ("688", 1), ("689", 3), ("690", 2), ("719", 1)):
            facts[(state, "has_global_flag", BASE + "_started")] = True
            facts[(state, "controller")] = "NAM"
            facts[(state, "is_owned_by", "NAM")] = True
            facts[(state, "is_controlled_by", "NAM")] = True
            facts[(state, "has_variable", "NAM_field_capacity")] = True
            facts[(state, "variable", "NAM_field_capacity")] = capacity
            facts[(state, "variable", "NAM_field_condition")] = 80
            facts[(state, "variable", "NAM_field_applied_oil")] = capacity * 8
        return facts

    def test_captured_wells_weight_working_capacity_without_stacking(self):
        facts = self.captured_field_facts()
        refresh = self.effects["NAM_captured_fields_refresh"]
        facts[("67", "controller")] = "EFL"
        for _ in range(3):
            self.apply(refresh, facts)
            self.assertEqual(facts[("NAM", "variable", "NAM_basin_capacity")], 12)
            self.assertEqual(facts[("NAM", "variable", "NAM_captured_capacity")], 4)
            self.assertAlmostEqual(facts[("NAM", "variable", "NAM_captured_war_support")], -0.10)
            self.assertAlmostEqual(facts[("NAM", "variable", "NAM_captured_factory_output")], -1 / 15)
        facts[("689", "controller")] = "EFL"
        facts[("689", "variable", "NAM_field_condition")] = 50
        self.apply(refresh, facts)
        self.assertEqual(facts[("NAM", "variable", "NAM_captured_capacity")], 5.5)
        facts[("67", "has_state_flag", "NAM_wells_scorched")] = True
        self.apply(refresh, facts)
        self.assertEqual(facts[("NAM", "variable", "NAM_basin_capacity")], 12)
        self.assertEqual(facts[("NAM", "variable", "NAM_captured_capacity")], 1.5)
        for controller in ("NAM", "VAL"):
            facts[("689", "controller")] = controller
            self.apply(refresh, facts)
            self.assertEqual(facts[("NAM", "variable", "NAM_captured_share")], 0)
            self.assertFalse(facts[("NAM", "has_dynamic_modifier", "NAM_captured_wells_shock")])

    def test_captured_wells_burn_expiry_and_peace_use_current_state(self):
        facts = self.captured_field_facts()
        refresh = self.effects["NAM_captured_fields_refresh"]
        facts[("67", "controller")] = "EFL"
        facts[("67", "has_state_flag", "NAM_wells_scorched")] = True
        facts[("67", "variable", "NAM_field_condition")] = 10
        self.apply(refresh, facts)
        self.assertEqual(facts[("NAM", "variable", "NAM_captured_share")], 0)
        facts[("67", "has_state_flag", "NAM_wells_scorched")] = False
        self.apply(refresh, facts)
        self.assertAlmostEqual(facts[("NAM", "variable", "NAM_captured_share")], 0.5 / 12)
        facts[("NAM", "has_global_flag", BASE + "_resolved")] = True
        self.apply(refresh, facts)
        self.assertEqual(facts[("NAM", "variable", "NAM_captured_share")], 0)
        self.assertFalse(facts[("NAM", "has_dynamic_modifier", "NAM_captured_wells_shock")])
        callback = block(self.events[BASE + ".89"], "immediate")
        self.assertEqual([(e.key, e.value) for e in callback], [("NAM_oil_refresh", "yes")])

    def test_burning_field_penalties_follow_enemy_controller_and_keep_physical_damage(self):
        facts = self.captured_field_facts()
        facts[("67", "has_state_flag", "NAM_wells_scorched")] = True
        facts[("67", "has_dynamic_modifier", "NAM_scorched_wells_modifier")] = True
        refresh = self.effects["NAM_scorched_field_refresh"]
        for controller, expected in (("NAM", 0), ("EFL", -0.2), ("NAM", 0), ("VAL", 0), ("EFL", -0.2)):
            facts[("67", "controller")] = controller
            self.apply(refresh, facts, "67")
            self.assertAlmostEqual(facts[("67", "variable", "NAM_scorched_enemy_speed")], expected)
            self.assertAlmostEqual(facts[("67", "variable", "NAM_scorched_enemy_attrition")], expected * -0.75)
            self.assertAlmostEqual(facts[("67", "variable", "NAM_scorched_enemy_supply")], expected * 5)
            self.assertTrue(facts[("67", "has_dynamic_modifier", "NAM_scorched_wells_modifier")])
        facts[("67", "has_global_flag", BASE + "_resolved")] = True
        self.apply(refresh, facts, "67")
        self.assertEqual(facts[("67", "variable", "NAM_scorched_enemy_speed")], 0)
        self.assertTrue(facts[("67", "has_state_flag", "NAM_wells_scorched")])

    def test_burning_fields_cannot_supply_contracts_through_refinery_or_pipeline(self):
        facts = self.captured_field_facts()
        facts[("67", "has_state_flag", "NAM_wells_scorched")] = True
        facts[("67", "has_state_flag", "NAM_refinery_built")] = True
        facts[("67", "has_state_flag", "NAM_pipeline_built")] = True
        facts[("700", "is_controlled_by", "NAM")] = True
        self.apply(self.effects["NAM_field_update_units"], facts, "67")
        self.assertEqual(facts[("67", "variable", "NAM_field_units")], 0)
        self.assertEqual(facts[("NAM", "variable", "NAM_oil_throughput")], 0)
        facts[("67", "has_state_flag", "NAM_wells_scorched")] = False
        self.apply(self.effects["NAM_field_update_units"], facts, "67")
        self.assertEqual(facts[("67", "variable", "NAM_field_units")], 6)

    def test_well_guards_apply_before_focus_commit_and_return_after_liberation(self):
        facts = self.captured_field_facts()
        modifier = ("67", "has_dynamic_modifier", "NAM_guarded_wells_modifier")
        self.apply(self.effects["NAM_guarded_field_apply"], facts, "67")
        self.assertTrue(facts[modifier])
        facts[("NAM", "has_completed_focus", "NAM_wells_under_guard")] = True
        for controlled in (False, True):
            facts[("67", "is_controlled_by", "NAM")] = controlled
            self.apply(self.effects["NAM_guarded_field_refresh"], facts, "67")
            self.assertEqual(facts[modifier], controlled)
        facts[("67", "has_global_flag", BASE + "_resolved")] = True
        self.apply(self.effects["NAM_guarded_field_refresh"], facts, "67")
        self.assertFalse(facts[modifier])

    def test_scorching_rechecks_target_and_refunds_stale_click_without_damage(self):
        decision = block(block(parsed(f"common/decisions/{BASE}_decisions.txt"), "NAM_mobilisation"), "NAM_scorch_wells")
        def bind_target(entries):
            return [replace(e, key="67" if e.key == "FROM" else e.key,
                            value=bind_target(e.value) if isinstance(e.value, list) else e.value)
                    for e in entries]
        # Supporting group and throughput calculations have separate accounting scenarios.
        settlement = block(decision, "complete_effect")
        with patch.dict(self.effects, {name: [] for name in ("NAM_oil_refresh", "NAM_groups_refresh", "NAM_seal_discipline_clamp")}):
            for cause in (None, "occupied", "ceded", "peace", "burnt", "no_focus", "safe"):
                facts = self.captured_field_facts()
                if cause == "occupied":
                    facts[("67", "is_controlled_by", "NAM")] = False
                elif cause == "ceded":
                    facts[("67", "is_owned_by", "NAM")] = False
                elif cause == "peace":
                    facts[("NAM", "has_global_flag", BASE + "_resolved")] = True
                elif cause == "burnt":
                    facts[("67", "has_state_flag", "NAM_wells_scorched")] = True
                elif cause == "no_focus":
                    facts[("NAM", "has_completed_focus", "NAM_scorched_wells")] = False
                elif cause == "safe":
                    facts[("67", "is_fully_controlled_by", "NAM")] = True
                self.apply(bind_target(settlement), facts)
                if cause is None:
                    self.assertEqual(facts[("67", "building_damage", "infrastructure")], 2)
                    self.assertEqual(facts[("67", "variable", "NAM_field_condition")], 10)
                    self.assertEqual(facts[("NAM", "variable", "NAM_grp_oil_support")], -10)
                    self.assertEqual(facts[("NAM", "variable", "NAM_seal_discipline")], -5)
                else:
                    self.assertNotIn(("67", "building_damage", "infrastructure"), facts)
                    self.assertEqual(facts[("67", "variable", "NAM_field_condition")], 80)
                    self.assertEqual(facts[("NAM", "numeric", "has_political_power")], 1020)
            for condition in (0, 5, 10, 80):
                facts = self.captured_field_facts()
                facts[("67", "variable", "NAM_field_condition")] = condition
                self.apply(bind_target(settlement), facts)
                self.assertEqual(facts[("67", "variable", "NAM_field_condition")], min(condition, 10))
        callback = next(e.value for e in walk(settlement) if e.key == "country_event")
        self.assertEqual((scalar(callback, "days"), scalar(callback, "hours")), ("180", "1"))

    def test_oilfield_choice_is_ready_in_21_days_and_ai_selects_one_alternative(self):
        choices = {"NAM_scorched_wells", "NAM_wells_under_guard"}
        for name in choices:
            focus = self.wartime[name]
            self.assertEqual(scalar(block(focus, "prerequisite"), "focus"), "NAM_alarm")
            self.assertEqual(scalar(block(focus, "mutually_exclusive"), "focus"), (choices - {name}).pop())
            self.assertEqual(7 * (int(scalar(self.wartime["NAM_alarm"], "cost")) + int(scalar(focus, "cost"))), 21)
        for plan in parsed("common/ai_strategy_plans/ADISCORD_NAM_plans.txt"):
            if "resource_war" not in plan.key:
                continue
            queue = [e.value for e in block(plan.value, "ai_national_focuses")]
            self.assertEqual(len(choices.intersection(queue)), 1)
            self.assertIn(queue[queue.index("NAM_alarm") + 1], choices)

    def test_resource_deadline_times_out_without_auto_success_and_preserves_orders(self):
        category = block(parsed(f"common/decisions/{BASE}_decisions.txt"), "NAM_restitution")
        names = {row.key for row in category}
        self.assertIn("NAM_resource_war_deadline", names)
        mission = block(category, "NAM_resource_war_deadline")
        self.assertEqual(int(scalar(mission, "days_mission_timeout")), 450)
        facts = self.independent_facts()
        facts[("NAM", "variable", "NAM_orders_paid")] = 3
        self.assertFalse(self.matches(block(mission, "available"), facts))
        self.apply(block(mission, "timeout_effect"), facts)
        self.assertTrue(facts[("NAM", "has_country_flag", "NAM_rw_war_dispatched")])
        self.assertEqual(facts[("NAM", "variable", "NAM_orders_paid")], 3)
        self.assertTrue(self.matches(self.triggers["NAM_rw_clock_running"], facts))

    def test_one_time_diplomacy_adds_exact_days_in_every_order(self):
        category = block(parsed(f"common/decisions/{BASE}_decisions.txt"), "NAM_restitution")
        self.assertIn("NAM_resource_war_deadline", {row.key for row in category})
        note = block(category, "NAM_restitution_note")
        dossier = block(category, "NAM_ind_border_dossier")
        clock = ("NAM", "variable", "days_mission_timeout@NAM_resource_war_deadline")
        for order in permutations(("desk", "azhar", "note", "dossier")):
            facts = self.independent_facts()
            facts[("NAM", "numeric", "has_fuel")] = 60000
            facts[("NAM", "has_active_mission", "NAM_resource_war_deadline")] = True
            facts[clock] = 450
            facts[("AZH", "exists", "yes")] = True
            facts[("AZH", "has_capitulated", "no")] = True
            for action in order:
                if action in ("desk", "azhar"):
                    name = "NAM_restitution_desk" if action == "desk" else "NAM_court_azhar"
                    self.apply(block(self.focuses[name], "completion_reward"), facts)
                else:
                    decision = note if action == "note" else dossier
                    self.apply(block(decision, "complete_effect"), facts)
                    if action == "dossier":
                        self.apply(block(decision, "remove_effect"), facts)
            self.assertEqual(facts[clock], 675, order)
            for decision in (note, dossier):
                self.apply(block(decision, "complete_effect"), facts)
                if decision is dossier:
                    self.apply(block(decision, "remove_effect"), facts)
            self.apply(self.effects["NAM_rw_buy_time"], facts)
            self.assertEqual(facts[clock], 675, order)

    def test_oil_offers_hide_when_no_export_capacity_and_embargo_hides_clients(self):
        offer = self.decisions["NAM_oil_contract_offer"]
        embargo = self.decisions["NAM_fuel_embargo"]
        def visible(body, facts):
            def bind(rows):
                return [replace(row, key="EFL" if row.key == "FROM" else row.key,
                                value=bind(row.value) if isinstance(row.value, list) else row.value)
                        for row in rows]
            return self.matches(bind(block(body, "visible")), facts)

        facts = self.independent_facts()
        facts.update({
            ("EFL", "tag", "EFL"): True,
            ("EFL", "exists", "yes"): True,
            ("EFL", "has_capitulated", "no"): True,
            ("NAM", "variable", "NAM_oil_free_land_units"): 1,
            ("NAM", "variable", "NAM_oil_free_units"): 1,
            ("NAM", "numeric", "has_political_power"): 0,
        })
        self.assertTrue(visible(offer, facts))
        self.assertTrue(visible(embargo, facts))
        facts[("NAM", "variable", "NAM_oil_free_land_units")] = 0
        facts[("NAM", "variable", "NAM_oil_free_units")] = 0
        self.assertFalse(visible(offer, facts))
        facts[("EFL", "has_country_flag", "NAM_oil_client")] = True
        self.assertFalse(visible(embargo, facts))

    def test_coalition_reserve_tops_up_only_the_missing_fuel_and_convoys(self):
        for fuel, convoys in ((0, 0), (19999, 39), (20000, 40), (30000, 60)):
            facts = {
                ("AZH", "numeric", "has_fuel"): fuel,
                ("AZH", "variable", "fixture_navy_convoy"): convoys,
            }
            for kind in ("train", "motorized", "support"):
                facts[("AZH", "variable", "num_equipment@" + kind + "_equipment")] = 200
            self.apply(self.effects["NAM_rw_coalition_transport_reserve"], facts, "AZH")
            self.assertEqual(facts[("AZH", "numeric", "has_fuel")], max(fuel, 20000))
            self.assertEqual(facts.get(("AZH", "equipment", "convoy_1"), 0), max(0, 40 - convoys))

    def naval_order_facts(self):
        facts = self.independent_facts()
        facts.update({
            ("fixture", "track_units"): True,
            ("NAM", "numeric", "has_manpower"): 3000,
            ("NAM", "variable", "num_battalions_with_type@ADISCORD_marine_infantry"): 0,
            ("NAM", "has_tech", "ADISCORD_tech_svetlogorsk_marine_corps"): True,
            ("NAM", "has_completed_focus", "NAM_pw_landing_supply"): True,
            ("NAM", "has_tech", "ADISCORD_tech_destroyer_hull_2155"): True,
            ("NAM", "has_tech", "ADISCORD_tech_submarine_hull_2155"): True,
            ("NAM", "controls_province", "16716"): True,
            ("NAM", "equipment", "infantry_equipment"): 2700,
            ("NAM", "equipment", "ADISCORD_squad_weapons_equipment"): 144,
            ("700", "is_owned_by", "NAM"): True,
            ("700", "is_controlled_by", "NAM"): True,
            ("700", "numeric", "naval_base"): 1,
            ("700", "numeric", "dockyard"): 1,
            ("700", "numeric", "radar_station"): 0,
        })
        return facts

    def test_naval_orders_survive_tree_and_peace_but_refund_lost_delivery_sites(self):
        cases = (("NAM_coast_observation_order", 50, "radar_station"),
                 ("NAM_escort_order", 100, "ADISCORD_escort_ship_2155"),
                 ("NAM_submarine_order", 100, "ADISCORD_submarine_2155"),
                 ("NAM_marine_detachment_order", 50, "marines"))
        for decision_id, price, result in cases:
            self.assertIn(decision_id, set(self.decisions))
            decision = self.decisions[decision_id]
            for outcome in ("war_tree", "peace", "lost_port", "subject", "capitulated", "cancel"):
                with self.subTest(order=decision_id, outcome=outcome):
                    facts = self.naval_order_facts()
                    pp = facts[("NAM", "numeric", "has_political_power")]
                    self.apply(block(decision, "complete_effect"), facts)
                    self.assertEqual(facts[("NAM", "numeric", "has_political_power")], pp - price)
                    if outcome == "lost_port":
                        facts[("700", "is_controlled_by", "NAM")] = False
                    elif outcome == "subject":
                        facts[("NAM", "is_subject", "no")] = False
                    elif outcome == "capitulated":
                        facts[("NAM", "has_capitulated", "no")] = False
                    elif outcome == "peace":
                        facts[("NAM", "has_war", "yes")] = False
                        facts[("NAM", "has_global_flag", BASE + "_resolved")] = True
                    else:
                        facts[("NAM", "has_focus_tree", "NAM_focus")] = False
                    refunded = outcome in ("lost_port", "subject", "capitulated", "cancel")
                    self.apply(block(decision, "cancel_effect" if outcome == "cancel" else "remove_effect"), facts)
                    self.assertEqual(facts[("NAM", "numeric", "has_political_power")], pp if refunded else pp - price)
                    if result == "radar_station":
                        delivered = facts.get(("700", "building", result), 0)
                    elif result == "marines":
                        delivered = facts.get(("NAM", "reward", "spawned_divisions"), 0)
                        self.assertEqual(facts[("NAM", "numeric", "has_manpower")], 3000 if refunded else 0)
                        self.assertEqual(facts[("NAM", "equipment", "infantry_equipment")], 2700 if refunded else 0)
                        self.assertEqual(facts[("NAM", "equipment", "ADISCORD_squad_weapons_equipment")], 144 if refunded else 0)
                    else:
                        delivered = facts.get(("NAM", "ships", result), 0)
                    self.assertEqual(delivered, 0 if refunded else 2 if result.startswith("ADISCORD_") else 1)
                    settled = dict(facts)
                    self.apply(block(decision, "remove_effect"), facts)
                    self.apply(block(decision, "cancel_effect"), facts)
                    self.assertEqual(facts, settled)

    def test_marine_order_exact_payment_and_current_force_limit(self):
        self.assertIn("NAM_marine_detachment_order", set(self.decisions))
        decision = self.decisions["NAM_marine_detachment_order"]
        for key, boundary in ((("NAM", "numeric", "has_political_power"), 50),
                              (("NAM", "numeric", "has_manpower"), 3000),
                              (("NAM", "equipment", "infantry_equipment"), 2700),
                              (("NAM", "equipment", "ADISCORD_squad_weapons_equipment"), 144)):
            for shortage in (0, 0.01):
                facts = self.naval_order_facts()
                facts[key] = boundary - shortage
                before = dict(facts)
                self.assertEqual(self.matches(block(decision, "custom_cost_trigger"), facts), not shortage)
                self.apply(block(decision, "complete_effect"), facts)
                if shortage:
                    self.assertEqual(facts, before)
        facts = self.naval_order_facts()
        self.apply(block(decision, "complete_effect"), facts)
        paid = dict(facts)
        self.apply(block(decision, "complete_effect"), facts)
        self.assertEqual(facts, paid)
        facts[("NAM", "variable", "num_battalions_with_type@ADISCORD_marine_infantry")] = 7
        self.apply(block(decision, "remove_effect"), facts)
        self.assertEqual(facts[("NAM", "numeric", "has_manpower")], 3000)
        self.assertEqual(facts.get(("NAM", "reward", "spawned_divisions"), 0), 0)

    def test_coalition_muster_counts_existing_units_and_pays_only_the_gap(self):
        for tag, existing, target, rifle_reserve, squad_reserve in (
            ("EFL", 4, 15, 20000, 300), ("EFL", 18, 15, 20000, 300),
            ("AZH", 3, 10, 12000, 200), ("AZH", 14, 10, 12000, 200),
        ):
            capital = "701" if tag == "EFL" else "69"
            facts = {
                ("fixture", "track_units"): True,
                (tag, "capital"): capital,
                (capital, "owner"): tag,
                (capital, "is_owned_by", "PREV"): True,
                (capital, "is_controlled_by", "PREV"): True,
                (tag, "exists", "yes"): True,
                (tag, "has_capitulated", "no"): True,
                (tag, "is_subject", "no"): True,
                (tag, "variable", "num_divisions"): existing,
                (tag, "numeric", "has_manpower"): 90000,
                (tag, "variable", "fixture_navy_convoy"): 40,
            }
            for equipment in ("infantry_equipment", "ADISCORD_squad_weapons_equipment", "support_equipment", "train_equipment", "motorized_equipment"):
                facts[(tag, "variable", "num_equipment@" + equipment)] = 0
            self.apply(self.effects["NAM_rw_coalition_muster"], facts, tag)
            missing = max(0, target - existing)
            self.assertEqual(facts.get((tag, "reward", "spawned_divisions"), 0), missing)
            self.assertEqual(facts[(tag, "numeric", "has_manpower")], 90000 - missing * 4000)
            self.assertEqual(facts[(tag, "variable", "num_equipment@infantry_equipment")], rifle_reserve)
            self.assertEqual(facts[(tag, "variable", "num_equipment@ADISCORD_squad_weapons_equipment")], squad_reserve)
            after = dict(facts)
            self.apply(self.effects["NAM_rw_coalition_muster"], facts, tag)
            self.assertEqual(facts, after)
            for blocked in ((tag, "has_global_flag", BASE + "_resolved"), (tag, "has_country_flag", "NAM_rw_coalition_mobilised")):
                fresh = {key: value for key, value in facts.items() if "NAM_rw_" not in str(key)}
                fresh[blocked] = True
                before = dict(fresh)
                self.apply(self.effects["NAM_rw_coalition_muster"], fresh, tag)
                self.assertEqual(fresh, before)

    def test_coalition_transport_contract_delivers_or_refunds_once(self):
        category = block(parsed(f"common/decisions/{BASE}_decisions.txt"), "NAM_coalition_logistics")
        contract = block(category, "NAM_coalition_transport_contract")
        self.assertEqual(int(scalar(contract, "cost")), 50)
        self.assertEqual(int(scalar(contract, "days_remove")), 35)
        for tag, cancellation in product(("EFL", "AZH"), (None, "cancel_effect", "remove_effect")):
            cancelled = cancellation is not None
            facts = {
                (tag, "has_capitulated", "no"): not cancelled,
                (tag, "numeric", "has_political_power"): 50,
            }
            # Native decision payment is outside the scripted completion effect.
            self.apply(block(contract, "complete_effect"), facts, tag)
            callback = cancellation or "remove_effect"
            self.apply(block(contract, callback), facts, tag)
            self.assertEqual(facts[(tag, "numeric", "has_political_power")], 100 if cancelled else 50)
            for equipment, amount in (("train_equipment_1", 10), ("motorized_equipment_1", 120), ("convoy_1", 20)):
                self.assertEqual(facts.get((tag, "equipment", equipment), 0), 0 if cancelled else amount)
            after = dict(facts)
            self.apply(block(contract, "remove_effect"), facts, tag)
            self.apply(block(contract, "cancel_effect"), facts, tag)
            self.assertEqual(facts, after)

    def test_coalition_landing_requires_a_current_war_and_spare_units(self):
        for tag, state, port, divisions in (("EFL", "723", "6495", 15), ("AZH", "692", "493", 10)):
            facts = {
                (tag, "is_ai", "yes"): True,
                (tag, "has_capitulated", "no"): True,
                ("NAM", "has_capitulated", "no"): True,
                (tag, "has_global_flag", BASE + "_started"): True,
                (tag, "has_war_with", "NAM"): True,
                (tag, "has_tech", "ADISCORD_tech_restored_dockyards"): True,
                (tag, "variable", "fixture_navy_convoy"): 40,
                (tag, "variable", "fixture_navy_ADISCORD_coastal_patrol_vessel"): 1,
                (tag, "numeric", "has_fuel"): 1000,
                (tag, "numeric", "num_divisions"): divisions,
                (tag, "controls_province", port): True,
                (state, "is_owned_by", tag): True,
                (state, "numeric", "naval_base"): 1,
            }
            ready = self.expand(self.triggers["NAM_rw_coalition_landing_ready"])
            self.assertTrue(matches_conditions(ready, facts, tag))
            for key, value in (
                ((tag, "has_war_with", "NAM"), False),
                ((tag, "has_global_flag", BASE + "_resolved"), True),
                ((tag, "controls_province", port), False),
                ((tag, "numeric", "num_divisions"), divisions - 1),
                ((tag, "variable", "fixture_navy_convoy"), 39),
                ((tag, "numeric", "has_fuel"), 999),
                ((tag, "variable", "fixture_navy_ADISCORD_coastal_patrol_vessel"), 0),
            ):
                self.assertFalse(matches_conditions(ready, {**facts, key: value}, tag), (tag, key))

    def crisis_facts(self, number):
        facts = self.economy_facts()
        facts[("NAM", "has_country_flag", "NAM_crisis_open")] = True
        facts[("NAM", "variable", "fixture_flag_value@NAM_crisis_open")] = number
        facts[("NAM", "has_completed_focus", "NAM_field_firefighters")] = False
        facts[("NAM", "has_completed_focus", "NAM_chancellery_purge")] = False
        facts[("NAM", "numeric", "has_manpower")] = 10000
        for group in ("oil", "trade", "nam", "garr", "dist"):
            facts[("NAM", "variable", "NAM_grp_" + group + "_support")] = 50
        return facts

    def crisis_options(self, number):
        return {scalar(e.value, "name").split(".")[-1]: e.value
                for e in self.events[f"ADISCORD_nam_crisis.{number}"] if e.key == "option"}

    def test_smuggling_choices_expose_previews_outside_settlement_guards(self):
        options = self.crisis_options(4)
        for answer, tooltip in (
            ("a", "NAM_crisis_4_a_tt"),
            ("b", "NAM_crisis_4_b_tt"),
            ("z", "NAM_crisis_fund_used_tt"),
        ):
            with self.subTest(answer=answer):
                option = options[answer]
                self.assertEqual(scalar(option, "custom_effect_tooltip"), tooltip)
                settlement = block(option, "hidden_effect")
                self.assertNotIn("custom_effect_tooltip", {e.key for e in walk(settlement)})
                self.assertNotIn("hidden_effect", {e.key for e in walk(settlement)})
                for language in ("russian", "english"):
                    path = ROOT / f"localisation/{language}/ADISCORD_nam_resource_war_l_{language}.yml"
                    self.assertTrue(path.read_bytes().startswith(b"\xef\xbb\xbf"))
                    values = [
                        match.group(2)
                        for line in path.read_text(encoding="utf-8-sig").splitlines()
                        if (match := ENTRY.fullmatch(line)) and match.group(1) == tooltip
                    ]
                    self.assertEqual(len(values), 1)
                    self.assertTrue(values[0])
        for answer, effect, amount in (("a", "add_stability", "-0.02"), ("b", "add_political_power", "-40")):
            option = options[answer]
            self.assertEqual(scalar(block(option, "effect_tooltip"), effect), amount)
            applied = [e.value for e in walk(block(option, "hidden_effect")) if e.key == effect]
            self.assertEqual(applied, [amount])

    def test_guarded_event_choices_expose_previews_without_lifecycle_checks(self):
        answers = {
            "10": ("a", "b", "c"), "20": ("b",), "21": ("a",), "30": ("b",),
            "82": ("a", "b", "c"), "83": ("a", "b", "c"), "84": ("a", "b", "c"),
            "85": ("a", "b", "c", "d_option"), "86": ("a", "b", "c", "d_option"),
            "87": ("a", "b", "c"), "108": ("a", "b"),
            "116": ("a", "b", "c"), "117": ("a", "b", "c"),
        }
        checked = 0
        for number, suffixes in answers.items():
            event_id = f"ADISCORD_nam_resource_war.{number}"
            options = {scalar(e.value, "name"): e.value for e in self.events[event_id] if e.key == "option"}
            for suffix in suffixes:
                name = f"{event_id}.{suffix}"
                with self.subTest(option=name):
                    preview = block(options[name], "effect_tooltip")
                    self.assertTrue(preview)
                    self.assertNotIn("hidden_trigger", {e.key for e in walk(preview)})
                    self.assertFalse(any(e.key in ("if", "else_if", "else") for e in options[name]))
                    settlement = block(options[name], "hidden_effect")
                    self.assertNotIn("hidden_effect", {e.key for e in walk(settlement)})
                    checked += 1
        for number in (1, 2, 3, 5):
            options = self.crisis_options(number)
            names = ["a", "b", "z"]
            if number in (1, 2):
                names.append("NAM_claim_industrial_cover")
            if number == 5:
                names.append("NAM_claim_pension_arrears")
            for name in names:
                with self.subTest(crisis=number, option=name):
                    self.assertTrue(block(options[name], "effect_tooltip"))
                    self.assertNotIn("hidden_trigger", {e.key for e in walk(block(options[name], "effect_tooltip"))})
                    self.assertTrue(block(options[name], "hidden_effect"))
                    checked += 1
        self.assertEqual(checked, 49)

    def test_crisis_previews_follow_the_current_specialisation_price(self):
        for number, focus in ((1, "NAM_field_firefighters"), (2, "NAM_field_firefighters"), (3, "NAM_chancellery_purge")):
            preview = block(self.crisis_options(number)["a"], "effect_tooltip")
            for specialised in (False, True):
                with self.subTest(crisis=number, specialised=specialised):
                    facts = self.crisis_facts(number)
                    facts[("NAM", "has_completed_focus", focus)] = specialised
                    shown = [e for _, e in selected_effects(preview, facts, "NAM")]
                    if number == 3:
                        self.assertEqual(scalar(shown, "add_political_power"), "-30" if specialised else "-60")
                    else:
                        expected = "NAM_crisis_free_tt" if number == 1 else "NAM_crisis_pay_100_tt"
                        prices = {e.value for e in shown if e.key == "custom_effect_tooltip" and e.value in (
                            "NAM_crisis_free_tt", "NAM_crisis_pay_100_tt", "NAM_crisis_pay_250_tt",
                        )}
                        self.assertEqual(prices, {expected if specialised else "NAM_crisis_pay_250_tt"})
        event = self.events["ADISCORD_nam_resource_war.20"]
        answer = next(e.value for e in event if e.key == "option" and scalar(e.value, "name").endswith(".b"))
        preview = block(answer, "effect_tooltip")
        for active in (False, True):
            facts = {("NAM", "NAM_rw_deadline_open", "yes"): active}
            shown = [e.value for _, e in selected_effects(preview, facts, "NAM") if e.key == "add_war_support"]
            self.assertEqual(shown, ["0.05"] if active else [])

    def test_agreement_tooltips_separate_tasks_rewards_and_failure(self):
        event = self.events["ADISCORD_nam_groups.20"]
        options = {scalar(e.value, "name"): e.value for e in event if e.key == "option"}
        for group in ("nam", "oil", "dist", "garr", "trade"):
            option = options[f"NAM_agreement_choose_{group}"]
            shown = []
            for entry in option:
                if entry.key == "custom_effect_tooltip":
                    shown.append(entry.value)
                elif entry.key == "effect_tooltip":
                    idea = block(entry.value, "add_timed_idea")
                    shown.append((scalar(idea, "idea"), scalar(idea, "days")))
            self.assertEqual(shown, [
                "NAM_agreement_project_header_tt", f"NAM_agreement_{group}_terms_tt",
                "NAM_agreement_success_tt", (f"NAM_agreement_{group}_reward", "365"),
                "NAM_agreement_common_terms_tt", (f"NAM_agreement_{group}_failure", "180"),
            ])
        for language in ("russian", "english"):
            path = ROOT / f"localisation/{language}/ADISCORD_nam_resource_war_l_{language}.yml"
            self.assertTrue(path.read_bytes().startswith(b"\xef\xbb\xbf"))
            values = {m.group(1): m.group(2) for line in path.read_text(encoding="utf-8-sig").splitlines()
                      if (m := ENTRY.fullmatch(line))}
            for group in ("nam", "oil", "dist", "garr", "trade"):
                self.assertGreaterEqual(values[f"NAM_agreement_{group}_terms_tt"].count(r"\n"), 3)
            for key in ("NAM_agreement_success_tt", "NAM_agreement_common_terms_tt"):
                self.assertTrue(values[key].startswith(r"\n"))
            self.assertNotIn("-5", values["NAM_agreement_common_terms_tt"])
            self.assertIn("5", values["NAM_agreement_decline_tt"])

    def test_smuggling_preview_does_not_double_charge_or_bypass_settlement(self):
        options = self.crisis_options(4)
        treasury = ("NAM", "variable", "ADISCORD_economy_treasury")
        pp = ("NAM", "numeric", "has_political_power")
        trade = ("NAM", "variable", "NAM_grp_trade_support")
        oil = ("NAM", "variable", "NAM_grp_oil_support")
        with patch.dict(self.effects, {"NAM_groups_refresh": []}):
            for customs, income in ((False, 100), (True, 250)):
                facts = self.crisis_facts(4)
                facts[("NAM", "has_completed_focus", "NAM_chancellery_purge")] = customs
                before = dict(facts)
                self.apply(options["a"], facts)
                self.assertEqual(facts[treasury], before[treasury] + income)
                self.assertEqual(facts[trade], before[trade] + 5)
                self.assertEqual(facts[("NAM", "reward", "stability")], -0.02)
                settled = dict(facts)
                self.apply(options["a"], facts)
                self.assertEqual(facts, settled)
            for balance, payable in ((39.99, False), (40, True)):
                facts = self.crisis_facts(4)
                facts[pp] = balance
                before = dict(facts)
                self.apply(options["b"], facts)
                self.assertEqual(facts[pp], balance - (40 if payable else 0))
                self.assertEqual(facts[trade], before[trade] - (8 if payable else 0))
                self.assertEqual(facts[oil], before[oil] + (4 if payable else 0))
                settled = dict(facts)
                self.apply(options["b"], facts)
                self.assertEqual(facts, settled)

    def test_postwar_insurance_and_family_rolls_settle_only_the_covered_case(self):
        treasury = ("NAM", "variable", "ADISCORD_economy_treasury")
        reserve = ("NAM", "has_country_flag", "NAM_crisis_fund")
        cooldown = ("NAM", "has_country_flag", "NAM_industrial_claim_paid")
        pension = ("NAM", "has_completed_focus", "NAM_pw_family_pensions")
        insured = ("NAM", "has_completed_focus", "NAM_pw_insurance_fund")
        victory = ("NAM", "has_global_flag", BASE + "_nam_victory")
        pending = ("NAM", "has_country_flag", "NAM_crisis_open")
        timeout = self.effects["NAM_crisis_response_timeout"]
        for number in (1, 2, 5):
            option_key = "NAM_claim_pension_arrears" if number == 5 else "NAM_claim_industrial_cover"
            option = self.crisis_options(number)[option_key]
            facts = self.crisis_facts(number)
            facts.update({victory: True, insured: number != 5, pension: number == 5, treasury: 0, reserve: True})
            self.assertTrue(self.matches(block(option, "trigger"), facts))
            for outcome in (option, timeout):
                settled = dict(facts)
                self.apply(outcome, settled)
                self.assertEqual((settled[pending], settled[reserve], settled[treasury]), (False, True, 0))
                self.assertEqual(bool(settled.get(cooldown)), number != 5)
                self.assertEqual(settled[("NAM", "numeric", "has_manpower")], 10000)
                before = dict(settled)
                self.apply(option, settled)
                self.assertEqual(settled, before)
            for override in (
                {victory: False},
                {("NAM", "is_subject", "no"): False},
                {insured: False, pension: False},
                {("NAM", "variable", "fixture_flag_value@NAM_crisis_open"): 2 if number == 1 else 1},
            ):
                stale = {**facts, **override}
                self.assertFalse(self.matches(block(option, "trigger"), stale))
                before = dict(stale)
                self.apply(option, stale)
                self.assertEqual(stale, before)
            if number in (1, 2):
                next_case = {**facts, cooldown: True}
                self.assertFalse(self.matches(block(option, "trigger"), next_case))
                self.apply(timeout, next_case)
                self.assertFalse(next_case[reserve])
            if number == 1:
                brigade = {**facts, ("NAM", "has_completed_focus", "NAM_field_firefighters"): True}
                self.assertFalse(self.matches(block(option, "trigger"), brigade))
                self.apply(timeout, brigade)
                self.assertTrue(brigade[reserve])
                self.assertFalse(brigade.get(cooldown))
        paid = next(e.value for e in walk(self.effects["NAM_settle_industrial_claim"]) if e.key == "set_country_flag")
        self.assertEqual((scalar(paid, "flag"), scalar(paid, "days")), ("NAM_industrial_claim_paid", "180"))

    def test_pension_families_can_fund_veteran_training_through_either_route(self):
        decision = self.decisions["NAM_pw_veteran_course"]
        for veterans, pensions in product((False, True), repeat=2):
            facts = self.postwar_facts()
            for name, known in (("NAM_veterans_return", veterans), ("NAM_pw_family_pensions", pensions)):
                facts[("NAM", "has_completed_focus", name)] = known
            self.assertEqual(self.matches(block(decision, "visible"), facts), veterans or pensions)
            for focus, already in (("NAM_veterans_return", pensions), ("NAM_pw_family_pensions", veterans)):
                result = selected_effects(self.expand(block(self.postwar[focus], "completion_reward")), facts, "NAM")
                self.assertEqual([e.value for _, e in result if e.key == "unlock_decision_tooltip"],
                                 [] if already else ["NAM_pw_veteran_course"])
            self.apply(block(decision, "complete_effect"), facts)
            self.assertEqual(bool(facts.get(("NAM", "has_country_flag", "NAM_pw_veteran_course_paid"))),
                             veterans or pensions)

    def test_federal_army_musters_its_regiment_and_issues_templates_to_actual_members(self):
        focuses = self.exile_trees["exile_humanist"][1]
        reg = "Federal Rifle Regiment"
        brigade = "Union Combined Arms Brigade"
        first = block(focuses["NAM_hum_federal_army"], "completion_reward")
        spawn = next(e.value for e in walk(first) if e.key == "create_unit")
        self.assertEqual(scalar(parse_clausewitz(scalar(spawn, "division")), "division_template"), reg)
        issue = block(focuses["NAM_hum_union_army"], "completion_reward")
        stores = {scalar(e.value, "type"): int(scalar(e.value, "amount"))
                  for e in issue if e.key == "add_equipment_to_stockpile"}
        self.assertEqual(stores, {"artillery_equipment": 48, "support_equipment": 60})
        original = self.board_facts()
        original.update({("NAM", "has_country_flag", "NAM_corp_takeover"): False,
                         ("fixture", "track_templates"): True, ("fixture", "track_units"): True,
                         ("NAM", "capital"): "700", ("700", "is_owned_by", "NAM"): True,
                         ("NAM", "array", "NAM_federal_districts"): ["EFL", "AZH"]})
        for tag in ("EFL", "AZH"):
            original[(tag, "exists", "yes")] = True
            original[(tag, "has_country_flag", "NAM_federal_district")] = True
            original[(tag, "is_subject_of", "NAM")] = tag == "EFL"
        manpower = ("NAM", "numeric", "has_manpower")
        for held, existing in product((True, False), repeat=2):
            facts = {**original, ("700", "is_controlled_by", "NAM"): held,
                     ("NAM", "has_template", reg): existing, manpower: 0}
            self.apply(block(focuses["NAM_hum_federal_army"], "completion_reward"), facts)
            unit_count = facts.get(("NAM", "reward", "spawned_divisions"), 0)
            self.assertEqual(unit_count, int(held and not existing))
            self.assertEqual(facts[manpower] + 4000 * unit_count, 8000)
            self.apply(block(focuses["NAM_hum_union_army"], "completion_reward"), facts)
            for template in (reg, brigade):
                self.assertTrue(facts[("NAM", "has_template", template)])
                self.assertTrue(facts[("EFL", "has_template", template)])
                self.assertFalse(facts.get(("AZH", "has_template", template)))
            self.assertEqual(facts.get(("EFL", "reward", "spawned_divisions"), 0), 0)
        for helper, expected, support in (("NAM_hum_issue_federal_regiment", ["infantry"] * 4, []),
                                          ("NAM_hum_issue_union_brigade", ["infantry"] * 6 + ["ADISCORD_line_artillery"], ["engineer"])):
            template = next(e.value for e in walk(self.effects[helper]) if e.key == "division_template")
            self.assertEqual([e.key for e in block(template, "regiments")], expected)
            self.assertEqual([e.key for e in next((e.value for e in template if e.key == "support"), [])], support)
        # The accession effect also runs for districts created after the focus completed.
        joined = self.effects["NAM_wor_federal_district_join"]
        for army, union, corporate in product((True, False), repeat=3):
            facts = dict(original)
            facts[("NAM", "has_completed_focus", "NAM_hum_federal_army")] = army
            facts[("NAM", "has_completed_focus", "NAM_hum_union_army")] = union
            facts[("NAM", "has_country_flag", "NAM_corp_takeover")] = corporate
            if corporate:
                self.apply(self.effects["NAM_board_initialize"], facts)
            self.apply(joined, facts, "KDR")
            self.assertEqual(bool(facts.get(("KDR", "has_template", reg))), army and not corporate)
            self.assertEqual(bool(facts.get(("KDR", "has_template", brigade))), union and not corporate)

    def test_demobilisation_retools_one_real_plant_or_returns_its_workers(self):
        decision = self.decisions["NAM_convert_wartime_plant"]
        state = "688"
        manpower = ("NAM", "numeric", "has_manpower")
        civilian = (state, "building", "industrial_complex")
        military = (state, "building", "arms_factory")
        project = (state, "has_state_flag", "NAM_project_in_progress")
        count = ("NAM", "variable", "NAM_projects_in_progress")
        plot = (state, "variable", "fixture_building_slots_industrial_complex_no")
        opening = self.postwar_facts()
        opening.update({("NAM", "has_war", "no"): True, ("NAM", "has_global_flag", "ADISCORD_south_hegemon_NAM"): True,
                        (state, "numeric", "industrial_complex"): 18, (state, "numeric", "arms_factory"): 1,
                        plot: 1, manpower: 4000, civilian: 18, military: 1})
        pay = self.bind_field(block(decision, "complete_effect"), state)
        settle = self.bind_field(block(decision, "remove_effect"), state)
        cancel = self.bind_field(block(decision, "cancel_effect"), state)
        start = self.bind_field(block(decision, "available"), state)
        self.assertTrue(self.matches(start, opening))
        self.assertEqual(scalar(decision, "days_remove"), "42")
        for key, value in ((manpower, 3999.99), (plot, 0), ((state, "numeric", "industrial_complex"), 19),
                           ((state, "numeric", "arms_factory"), 0)):
            denied = {**opening, key: value}
            before = dict(denied)
            self.apply(pay, denied)
            self.assertEqual(before, denied)
        paid = dict(opening)
        self.apply(pay, paid)
        self.apply(pay, paid)
        self.assertEqual((paid[manpower], paid[count], paid[military], paid[civilian]), (0, 1, 1, 18))
        for key, value in ((plot, 0), ((state, "is_controlled_by", "NAM"), False), (("NAM", "has_war", "no"), False),
                           ((state, "numeric", "arms_factory"), 0), (("NAM", "is_subject", "no"), False)):
            for callback in (cancel, settle):
                interrupted = {**paid, key: value}
                self.apply(callback, interrupted)
                self.apply(cancel, interrupted)
                self.assertEqual((interrupted[manpower], interrupted[count], interrupted[project]), (4000, 0, False))
                self.assertEqual((interrupted[military], interrupted[civilian]), (1, 18))
        self.apply(settle, paid)
        self.apply(settle, paid)
        self.apply(cancel, paid)
        self.assertEqual((paid[military], paid[civilian], paid[manpower], paid[count]), (0, 20, 0, 0))
        self.assertFalse(self.matches(self.bind_field(block(decision, "visible"), state), paid))

    def test_crisis_fund_covers_all_five_cases_and_is_spent_once(self):
        treasury = block(parsed(f"common/decisions/{BASE}_decisions.txt"), "NAM_treasury")
        fund = block(treasury, "NAM_crisis_fund")
        for cash, payable in ((249.99, False), (250, True)):
            facts = self.crisis_facts(1)
            facts[("NAM", "variable", "ADISCORD_economy_treasury")] = cash
            self.apply(block(fund, "complete_effect"), facts)
            self.assertEqual(facts[("NAM", "variable", "ADISCORD_economy_treasury")], cash - (250 if payable else 0))
            self.assertEqual(facts.get(("NAM", "has_country_flag", "NAM_crisis_fund"), False), payable)
            paid = dict(facts)
            self.apply(block(fund, "complete_effect"), facts)
            self.assertEqual(facts, paid)
        for number in range(1, 6):
            facts = self.crisis_facts(number)
            self.apply(block(fund, "complete_effect"), facts)
            response = self.crisis_options(number)["z"]
            self.assertTrue(self.matches(block(response, "trigger"), facts))
            before = dict(facts)
            self.apply(response, facts)
            before[("NAM", "has_country_flag", "NAM_crisis_open")] = False
            before[("NAM", "has_country_flag", "NAM_crisis_fund")] = False
            before[("NAM", "has_active_mission", "NAM_incident_countdown")] = True
            before[("NAM", "variable", "days_mission_timeout@NAM_incident_countdown")] = 150
            self.assertEqual(facts, before, number)
            self.apply(response, facts)
            self.assertEqual(facts, before, number)

    def test_crisis_answers_reject_other_cases_and_lost_sites_without_spending_the_fund(self):
        for number in range(1, 6):
            options = self.crisis_options(number)
            other = self.crisis_facts(number % 5 + 1)
            other[("NAM", "has_country_flag", "NAM_crisis_fund")] = True
            before = dict(other)
            for response in options.values():
                self.apply(response, other)
                self.assertEqual(other, before, (number, scalar(response, "name")))
            lost = self.crisis_facts(number)
            lost[("NAM", "has_country_flag", "NAM_crisis_fund")] = True
            if number in (1, 2, 4):
                for state in ("67", "688", "689", "690", "719"):
                    lost[("NAM", "controls_state", state)] = False
            else:
                lost[("NAM", "has_capitulated", "no")] = False
            before = dict(lost)
            for key, response in options.items():
                if key == "NAM_crisis_close_case":
                    continue
                self.assertFalse(self.matches(block(response, "trigger"), lost))
                sample = dict(lost)
                self.apply(response, sample)
                expected = dict(before)
                if key == "a":
                    expected[("NAM", "has_country_flag", "NAM_crisis_open")] = False
                    if number in (1, 2, 4):
                        expected[("NAM", "has_active_mission", "NAM_incident_countdown")] = True
                        expected[("NAM", "variable", "days_mission_timeout@NAM_incident_countdown")] = 150
                self.assertEqual(sample, expected)
            close = options["NAM_crisis_close_case"]
            self.assertTrue(self.matches(block(close, "trigger"), lost))
            self.apply(close, lost)
            before[("NAM", "has_country_flag", "NAM_crisis_open")] = False
            if number in (1, 2, 4):
                before[("NAM", "has_active_mission", "NAM_incident_countdown")] = True
                before[("NAM", "variable", "days_mission_timeout@NAM_incident_countdown")] = 150
            self.assertEqual(lost, before)

    def test_crisis_payments_recheck_fractional_prices_and_available_default_answers(self):
        with patch.dict(self.effects, {"NAM_groups_refresh": [], "NAM_oil_refresh": []}):
            for number, specialist, price, currency in (
                (1, False, 250, "treasury"), (1, True, 0, "treasury"),
                (2, False, 250, "treasury"), (2, True, 100, "treasury"),
                (3, False, 60, "pp"), (3, True, 30, "pp"), (5, False, 250, "treasury"),
            ):
                for paid in (False, True):
                    facts = self.crisis_facts(number)
                    name = "NAM_chancellery_purge" if number == 3 else "NAM_field_firefighters"
                    facts[("NAM", "has_completed_focus", name)] = specialist
                    key = ("NAM", "variable", "ADISCORD_economy_treasury") if currency == "treasury" else ("NAM", "numeric", "has_political_power")
                    facts[key] = price if paid or not price else price - 0.01
                    response = self.crisis_options(number)["a"]
                    expected = paid or not price
                    self.assertEqual(self.matches(block(response, "trigger"), facts), expected)
                    before = dict(facts)
                    self.apply(response, facts)
                    self.assertEqual(facts[key], before[key] - (price if expected else 0))
                    self.assertFalse(facts[("NAM", "has_country_flag", "NAM_crisis_open")])
                    settled = dict(facts)
                    self.apply(response, facts)
                    self.assertEqual(facts, settled)
            # Exercise the literal first answer, even when its UI trigger is
            # unaffordable. Native timeout rendering still needs a manual check.
            for number, insured in product(range(1, 6), (False, True)):
                facts = self.crisis_facts(number)
                facts[("NAM", "variable", "ADISCORD_economy_treasury")] = 0
                facts[("NAM", "numeric", "has_political_power")] = 0
                facts[("NAM", "has_country_flag", "NAM_crisis_fund")] = insured
                response = self.crisis_options(number)["a"]
                self.apply(response, facts)
                self.assertFalse(facts[("NAM", "has_country_flag", "NAM_crisis_open")])
                self.assertGreaterEqual(facts[("NAM", "variable", "ADISCORD_economy_treasury")], 0)
                self.assertGreaterEqual(facts[("NAM", "numeric", "has_political_power")], 0)
                if insured and number != 4:
                    self.assertFalse(facts[("NAM", "has_country_flag", "NAM_crisis_fund")])

    def test_crisis_selection_respects_sites_and_prevention_does_not_erase_a_case(self):
        draw = self.effects["NAM_crisis_draw"]
        for office, duration in ((False, 90), (True, 150)):
            facts = self.crisis_facts(1)
            facts[("NAM", "has_country_flag", "NAM_crisis_open")] = False
            facts[("NAM", "has_completed_focus", "NAM_crisis_office")] = office
            self.apply(draw, facts)
            self.assertTrue(facts[("NAM", "has_active_mission", "NAM_incident_countdown")])
            self.assertEqual(facts[("NAM", "variable", "days_mission_timeout@NAM_incident_countdown")], duration)
            before = dict(facts)
            self.apply(draw, facts)
            self.assertEqual(facts, before)
        selection = block(self.effects["NAM_crisis_select"], "random_list")
        for number, entry in enumerate(selection, 1):
            facts = self.crisis_facts(number)
            if number in (1, 2, 4):
                for state in ("67", "688", "689", "690", "719"):
                    facts[("NAM", "controls_state", state)] = False
                suppress = block(entry.value, "modifier")
                self.assertEqual(scalar(suppress, "factor"), "0")
                self.assertTrue(self.matches([e for e in suppress if e.key != "factor"], facts))
            receipt = block(entry.value, "set_country_flag")
            self.assertEqual(scalar(receipt, "value"), str(number))
        treasury = block(parsed(f"common/decisions/{BASE}_decisions.txt"), "NAM_treasury")
        prevention = block(treasury, "NAM_crisis_prevention")
        facts = self.crisis_facts(4)
        self.assertFalse(self.matches(block(prevention, "available"), facts))
        before = dict(facts)
        facts[("NAM", "numeric", "has_political_power")] -= 50
        self.apply(block(prevention, "complete_effect"), facts)
        self.assertEqual(facts, before)
        facts[("NAM", "has_country_flag", "NAM_crisis_open")] = False
        facts[("NAM", "has_active_mission", "NAM_incident_countdown")] = True
        facts[("NAM", "variable", "days_mission_timeout@NAM_incident_countdown")] = 90
        self.apply(block(prevention, "complete_effect"), facts)
        self.assertEqual(facts[("NAM", "variable", "days_mission_timeout@NAM_incident_countdown")], 150)
        self.assertEqual(list(selected_effects(self.expand(draw), facts, "NAM")), [])

    def test_crisis_specialisations_open_and_improve_existing_programmes(self):
        project = self.bind_field(self.decisions["NAM_project_repair_wells"])
        audit = block(block(parsed(f"common/decisions/{BASE}_decisions.txt"), "NAM_treasury"), "NAM_fuel_audit")
        for choice, other in (("NAM_field_firefighters", "NAM_chancellery_purge"), ("NAM_chancellery_purge", "NAM_field_firefighters")):
            self.assertEqual(scalar(block(self.focuses[choice], "mutually_exclusive"), "focus"), other)
        with patch.dict(self.effects, {"NAM_oil_refresh": [], "NAM_groups_refresh": []}):
            for specialist, gain in ((False, 30), (True, 45)):
                facts = self.crisis_facts(1)
                facts[("NAM", "has_completed_focus", "NAM_field_firefighters")] = specialist
                facts[("NAM", "has_completed_focus", "NAM_field_repair_crews")] = not specialist
                facts[("67", "variable", "NAM_field_condition")] = 20
                self.assertTrue(self.matches(block(project, "visible"), facts))
                self.apply(block(project, "complete_effect"), facts)
                self.apply(block(project, "remove_effect"), facts)
                self.assertEqual(facts[("67", "variable", "NAM_field_condition")], 20 + gain)
            for specialist in (False, True):
                facts = self.crisis_facts(3)
                facts[("NAM", "has_completed_focus", "NAM_chancellery_purge")] = specialist
                facts[("NAM", "has_completed_focus", "NAM_well_register")] = not specialist
                facts[("NAM", "variable", "NAM_grp_trade_support")] = 30
                self.assertTrue(self.matches(block(audit, "visible"), facts))
                self.assertTrue(self.matches(block(audit, "available"), facts))
                facts[("NAM", "numeric", "has_political_power")] -= 50
                self.apply(block(audit, "complete_effect"), facts)
                self.assertEqual(facts[("NAM", "numeric", "has_fuel")], 24000)
                self.assertEqual(facts[("NAM", "variable", "ADISCORD_economy_treasury")], 10150 if specialist else 10000)
                self.assertEqual(facts[("NAM", "variable", "NAM_grp_trade_support")], 24 if specialist else 30)
                facts[("NAM", "variable", "NAM_grp_trade_support")] = 29.99
                self.assertEqual(self.matches(block(audit, "available"), facts), not specialist)
        for focus, earlier in (("NAM_field_repair_crews", "NAM_field_firefighters"), ("NAM_well_register", "NAM_chancellery_purge")):
            facts = self.crisis_facts(1)
            facts[("NAM", "has_completed_focus", earlier)] = True
            selected = selected_effects(self.expand(block(self.focuses[focus], "completion_reward")), facts, "NAM")
            self.assertFalse(any(e.key == "unlock_decision_tooltip" for _, e in selected), focus)
        facts = self.crisis_facts(1)
        facts[("NAM", "has_completed_focus", "NAM_field_firefighters")] = True
        facts[("NAM", "has_country_flag", "NAM_crisis_fund")] = True
        for option, expected in (("a", 50), ("b", 0), ("z", 0)):
            weights = block(self.crisis_options(1)[option], "ai_chance")
            weight = int(scalar(weights, "base"))
            for modifier in (e.value for e in weights if e.key == "modifier"):
                if self.matches([e for e in modifier if e.key != "factor"], facts):
                    weight *= float(scalar(modifier, "factor"))
            self.assertEqual(weight, expected)

    def test_repair_cancels_scorched_or_finished_work_without_touching_a_new_project(self):
        project = self.bind_field(self.decisions["NAM_project_repair_wells"])
        for changed in ("scorched", "restored", "lost", "capitulated"):
            facts = self.crisis_facts(1)
            facts[("67", "variable", "NAM_field_condition")] = 20
            self.apply(block(project, "complete_effect"), facts)
            if changed == "scorched":
                facts[("67", "has_state_flag", "NAM_wells_scorched")] = True
            elif changed == "restored":
                facts[("67", "variable", "NAM_field_condition")] = 100
            elif changed == "capitulated":
                facts[("NAM", "has_capitulated", "no")] = False
            else:
                facts[("67", "is_controlled_by", "NAM")] = False
            condition = facts[("67", "variable", "NAM_field_condition")]
            self.assertTrue(self.matches(block(project, "cancel_trigger"), facts))
            self.apply(block(project, "remove_effect"), facts)
            self.assertEqual(facts[("NAM", "variable", "ADISCORD_economy_treasury")], 10000)
            self.assertEqual(facts[("NAM", "numeric", "has_political_power")], 975)
            self.assertEqual(facts[("67", "variable", "NAM_field_condition")], condition)
            facts[("67", "has_state_flag", "NAM_project_in_progress")] = True
            facts[("67", "variable", "NAM_project_deposit")] = 300
            facts[("NAM", "variable", "NAM_projects_in_progress")] = 1
            before = dict(facts)
            self.apply(block(project, "cancel_effect"), facts)
            self.apply(block(project, "remove_effect"), facts)
            self.assertEqual(facts, before)

    def test_main_exclusion_lines_do_not_cross_other_focus_cards(self):
        positions = {name: (int(scalar(body, "x")), int(scalar(body, "y"))) for name, body in self.focuses.items()}
        self.assertEqual(focus_exclusion_crossings(self.focuses, positions), [])
        self.assertNotIn("NAM_district_guarantees", reachable(self.focuses, {"NAM_districts"}))
        self.assertNotIn("NAM_emergency_writ", reachable(self.focuses, {"NAM_vertical"}))

    def preparation_route(self, administration, economy, army, lean=False):
        """One sequential focus queue; national and local projects run alongside it."""
        route = ["letters_to_the_centre", "independence_day", "count_garrisons", "mobilisation_office", "open_ledgers", administration,
                 "well_register", economy, ("machine_shops" if lean else "refinery_programme") if economy == "domestic_refining" else "contract_bureau"]
        route += ["district_guarantees"] if administration == "districts" else ["emergency_writ"]
        route += [army, "engineer_depots", "line_survey", "line_engineers"] if army == "field_guards" else [army, "motor_pool"]
        return ["NAM_" + name for name in route + ["tax_rolls", "one_budget", "neutral_basin"]]

    def run_preparation_budget(self, administration, economy, army, lean=False, full=False, extended=False):
        """Bounded source scenario, not an engine/economy simulation.

        The colony has earmarked 200 PP, 1000 treasury and 8000 fuel. Assume
        0.25 net PP/day while focusing and 1000 net fuel/day capped at 200000,
        no tax/trade income, no new recruits and no factory output. Other stocks
        grow only through this queue and explicitly bought projects.
        Random crises and the weekly budget are separate
        runtime inputs, so the resulting reserve is not a guaranteed forecast.
        The extended queue retains the full stock proved by the colonial
        saving route and pays for every diplomatic delay from that reserve.
        """
        route = self.preparation_route(administration, economy, army, lean)
        if extended:
            full = True
            route += ["NAM_restitution_desk", "NAM_court_azhar"]
        if full:
            route += ["NAM_" + name for name in (
                "open_ledgers", "supports_oil_compact", "garrison_assembly",
                "supports_oil_compact", "garrison_assembly", "pillar_arbitration")]
        if extended:
            route += ["NAM_" + name for name in (
                "emergency_writ" if administration == "vertical" else "district_guarantees",
                "seal_courts", "machine_shops" if economy == "domestic_refining" else "insured_cargoes",
                "civilian_combine", "technical_college", "quartermaster", "port_arsenal", "officer_courses")]
        route = list(dict.fromkeys(route))
        facts = self.economy_facts()
        facts[("AZH", "exists", "yes")] = True
        facts[("AZH", "has_capitulated", "no")] = True
        for name in self.focuses:
            facts[("NAM", "has_completed_focus", name)] = name == "NAM_inventory"
        facts[("NAM", "has_global_flag", "ADISCORD_vorkerland_collapse_wars_started")] = True
        # Only the colonial bypasses already eligible at the collapse cost no time.
        for name, body in self.focuses.items():
            if name == "NAM_independence_day":
                break
            bypass = next((e.value for e in body if e.key == "bypass"), None)
            if bypass is not None and self.matches(bypass, facts):
                facts[("NAM", "has_completed_focus", name)] = True
        facts[("NAM", "has_war", "yes")] = False
        facts[("NAM", "fixture_power_balance", "NAM_ladder_bop")] = True
        facts[("NAM", "power_balance_value", "NAM_ladder_bop")] = 0
        facts[("67", "fixture_foreign_land_border", "yes")] = True
        for name, value in (("has_political_power", 150 if lean else 200), ("has_fuel", 4000 if lean else 8000), ("has_manpower", 0)):
            facts[("NAM", "numeric", name)] = value
        for name, value in (("ADISCORD_economy_treasury", 300 if lean else 1000), ("NAM_order_cap", 4), ("NAM_orders_paid", 0),
                            ("NAM_line_slots", 2), ("NAM_lines_in_progress", 0), ("NAM_project_slots", 1),
                            ("NAM_grp_dist_support", 40), ("NAM_grp_nam_support", 55),
                            ("NAM_grp_oil_support", 40), ("NAM_grp_garr_support", 50), ("NAM_grp_trade_support", 45)):
            facts[("NAM", "variable", name)] = value
        if extended:
            reserve = self.run_colonial_saving_route()
            for kind, name in (("numeric", "has_political_power"), ("numeric", "has_fuel"), ("numeric", "has_manpower"),
                               ("variable", "ADISCORD_economy_treasury")):
                facts[("NAM", kind, name)] = reserve[("NAM", kind, name)]
            facts.update({key: value for key, value in reserve.items() if key[:2] == ("NAM", "equipment")})
            for name in self.focuses:
                if reserve.get(("NAM", "has_completed_focus", name)):
                    facts[("NAM", "has_completed_focus", name)] = True
            route = [name for name in route if not facts[("NAM", "has_completed_focus", name)]]
        facts[("67", "numeric", "synthetic_refinery")] = 0
        facts[("67", "fixture_free_building_slots", "synthetic_refinery:1:yes")] = True
        facts[("67", "fixture_free_building_slots", "arms_factory:1:no")] = True
        projects = dict(self.decisions)
        for category in parsed(f"common/decisions/{BASE}_decisions.txt"):
            if category.key in ("NAM_mobilisation", "NAM_restitution"):
                projects.update({e.key: e.value for e in category.value})
        wanted = {"NAM_ind_sovereign_collections": 2,
                  "NAM_mil_recruit_depots": 2 if administration == "vertical" and army == "field_guards" else 1}
        wanted["NAM_admin_compulsory_delivery" if administration == "vertical" else "NAM_admin_voluntary_enrolment"] = 1
        if administration == "districts":
            wanted["NAM_sign_compact"] = 1
        if economy == "domestic_refining":
            wanted.update(NAM_project_refinery=1, NAM_econ_petrochemical_batch=1)
        else:
            wanted["NAM_export_fuel"] = 1
        if army == "field_guards":
            wanted.update(NAM_order_resource_guard=1, NAM_prepare_line=1, NAM_mil_forward_supply=1)
        else:
            wanted.update(NAM_order_motor_column=1, NAM_mil_carrier_contract=1)
        if lean:
            wanted["NAM_mil_recruit_depots"] = 1
            if administration == "districts":
                del wanted["NAM_admin_voluntary_enrolment"]
            if economy == "domestic_refining":
                del wanted["NAM_project_refinery"]
                del wanted["NAM_econ_petrochemical_batch"]
                wanted["NAM_workshop_batch"] = 1
            if army == "field_guards":
                del wanted["NAM_order_resource_guard"]
                wanted["NAM_order_field_infantry"] = 1
            else:
                del wanted["NAM_mil_carrier_contract"]
        if full:
            wanted["NAM_ind_sovereign_collections"] = 4
            if not extended:
                wanted["NAM_council_fuel_reserve"] = 1
            wanted["NAM_council_arsenal_contract"] = 1
        if extended:
            wanted.update(NAM_restitution_note=1, NAM_ind_border_dossier=1,
                          NAM_mil_arsenal_batch=1, NAM_mil_command_course=1)
            # The completed colonial route supplies the first 5000 recruits.
            wanted["NAM_mil_recruit_depots"] -= 1
            if not wanted["NAM_mil_recruit_depots"]:
                del wanted["NAM_mil_recruit_depots"]
        # Keep real accounting and local delivery effects. Aggregate modifiers,
        # stories, trade offers and war dispatch are outside this budget fixture.
        accounting = {name: body for name, body in self.effects.items() if name in (
            "NAM_add_treasury", "NAM_spend_treasury", "NAM_receive_250", "NAM_line_begin", "NAM_line_complete",
            "NAM_line_release", "NAM_project_begin", "NAM_project_close", "NAM_project_complete_refinery", "NAM_order_register")}
        counts = Counter()
        pending = {}
        cooldown = {}
        completed = {}
        focus_days = {}
        focus_index = 0
        focus_due = 0
        mission = block(block(parsed(f"common/decisions/{BASE}_decisions.txt"), "NAM_restitution"), "NAM_resource_war_deadline")
        clock = ("NAM", "variable", "days_mission_timeout@NAM_resource_war_deadline")
        facts[clock] = int(scalar(mission, "days_mission_timeout"))
        day = 0
        with patch.object(self, "effects", accounting):
            while facts[clock] > 0:
                facts[("NAM", "numeric", "has_political_power")] += 0.25
                fuel_key = ("NAM", "numeric", "has_fuel")
                facts[fuel_key] = min(200000, facts[fuel_key] + 1000)
                for name in list(pending):
                    if pending[name] != day:
                        continue
                    body = self.bind_field(projects[name])
                    self.assertFalse(self.matches(next((e.value for e in body if e.key == "cancel_trigger"), []), facts)
                                     if any(e.key == "cancel_trigger" for e in body) else False, (name, day))
                    self.apply(block(body, "remove_effect"), facts)
                    if name == "NAM_project_refinery":
                        self.assertEqual(facts[("67", "building", "synthetic_refinery")], 1)
                        facts[("67", "numeric", "synthetic_refinery")] = 1
                    del pending[name]
                    facts[("NAM", "has_decision", name)] = False
                    completed[name] = day
                if day == focus_due and focus_index:
                    name = route[focus_index - 1]
                    self.apply(block(self.focuses[name], "completion_reward"), facts)
                    facts[("NAM", "has_completed_focus", name)] = True
                    focus_days[name] = day
                    if name == "NAM_port_arsenal":
                        facts[("700", "numeric", "arms_factory")] = facts.get(("700", "building", "arms_factory"), 0)
                if day == focus_due and focus_index < len(route):
                    name = route[focus_index]
                    body = self.focuses[name]
                    for requirement in (e.value for e in body if e.key == "prerequisite"):
                        self.assertTrue(any(facts.get(("NAM", "has_completed_focus", e.value)) for e in requirement), name)
                    for group in (e.value for e in body if e.key == "mutually_exclusive"):
                        self.assertFalse(any(facts.get(("NAM", "has_completed_focus", e.value)) for e in group), name)
                    self.assertTrue(self.matches(block(body, "available"), facts), name)
                    bypass = next((e.value for e in body if e.key == "bypass"), None)
                    if bypass is not None:
                        self.assertFalse(self.matches(bypass, facts), name)
                    focus_due = day + int(scalar(body, "cost")) * 7
                    focus_index += 1
                for name, limit in wanted.items():
                    if counts[name] >= limit or name in pending or day < cooldown.get(name, 0):
                        continue
                    body = self.bind_field(projects[name])
                    predicates = [e.value for e in body if e.key in ("visible", "available", "custom_cost_trigger")]
                    price = int(next((e.value for e in body if e.key == "cost"), "0"))
                    if not all(self.matches(p, facts) for p in predicates) or facts[("NAM", "numeric", "has_political_power")] < price:
                        continue
                    facts[("NAM", "numeric", "has_political_power")] -= price
                    self.apply(block(body, "complete_effect"), facts)
                    counts[name] += 1
                    duration = int(next((e.value for e in body if e.key == "days_remove"), "0"))
                    cooldown[name] = day + duration + int(next((e.value for e in body if e.key == "days_re_enable"), "0"))
                    if duration:
                        pending[name] = day + duration
                        facts[("NAM", "has_decision", name)] = True
                    else:
                        completed[name] = day
                for key in (("numeric", "has_political_power"), ("numeric", "has_fuel"), ("numeric", "has_manpower"),
                            ("variable", "ADISCORD_economy_treasury"), ("equipment", "support_equipment")):
                    self.assertGreaterEqual(facts.get(("NAM", *key), 0), 0, (administration, economy, army, day, key))
                day += 1
                facts[clock] -= 1
                self.assertLess(day, 1100, "Preparation must retain a finite deadline")
        first_war_day = day
        self.assertEqual(len(focus_days), len(route), (route[focus_index - 1:], first_war_day))
        self.assertEqual(dict(counts), wanted, (administration, economy, army, counts))
        self.assertFalse(pending, (administration, economy, army, pending))
        self.assertLess(max(completed.values()), first_war_day)
        if administration == "districts":
            self.assertLessEqual(completed["NAM_sign_compact"] + 60, 301)
        self.assertEqual(facts[("NAM", "variable", "NAM_lines_in_progress")], 0)
        self.assertEqual(facts[("NAM", "variable", "NAM_projects_in_progress")], 0)
        formation = "infantry" if lean and army == "field_guards" else "guard" if army == "field_guards" else "motor"
        self.assertEqual(facts[("NAM", "variable", "NAM_order_" + formation + "_paid")], 1)
        self.assertEqual(facts[("NAM", "variable", "NAM_orders_paid")], 1)
        if army == "field_guards":
            self.assertTrue(facts[("67", "has_state_flag", "NAM_line_prepared")])
            self.assertTrue(facts[("67", "has_dynamic_modifier", "NAM_mil_forward_depot")])
        elif not lean:
            self.assertEqual(facts[("NAM", "equipment", "ADISCORD_armored_carrier_2163")], 160)
        if economy == "domestic_refining" and not lean:
            self.assertGreaterEqual(facts[("NAM", "equipment", "motorized_equipment")], 150)
            self.assertGreaterEqual(facts[("NAM", "equipment", "artillery_equipment")], 60)
        if extended:
            self.assertEqual(first_war_day, 675)
            self.assertNotIn("NAM_letters_to_the_centre", focus_days)
            self.assertEqual(facts[("AZH", "numeric", "has_fuel")], 60000)
            self.assertTrue(facts[("NAM", "has_country_flag", "NAM_rw_time_bought")])
            self.assertTrue(facts[("NAM", "has_country_flag", "NAM_rw_note_sent")])
            self.assertTrue(facts[("NAM", "has_country_flag", "NAM_ind_border_dossier_used")])
            self.assertFalse(facts[("NAM", "has_country_flag", "NAM_ind_border_dossier_paid")])
            self.assertGreaterEqual(facts[("NAM", "numeric", "army_experience")], 25)
        else:
            self.assertEqual(first_war_day, 450)
        return focus_days, completed

    def test_combined_preparation_routes_pay_and_deliver_before_the_war(self):
        for administration, economy, army in product(("vertical", "districts"), ("export_quays", "domestic_refining"), ("field_guards", "mobile_columns")):
            with self.subTest(administration=administration, economy=economy, army=army):
                self.run_preparation_budget(administration, economy, army)

    def test_council_preparation_budget_pays_for_orders_with_real_collections(self):
        for administration in ("vertical", "districts"):
            self.run_preparation_budget(administration, "export_quays", "field_guards", full=True)

    def test_deadline_warnings_and_voluntary_first_strike_use_the_same_clock(self):
        clock = ("NAM", "variable", "days_mission_timeout@NAM_resource_war_deadline")
        for remaining, notes, ultimatum in ((301, False, False), (300, True, False), (91, True, False), (90, True, True)):
            facts = self.independent_facts()
            facts[clock] = remaining
            self.apply(self.effects["NAM_rw_deadline_monthly"], facts)
            self.assertEqual(facts.get(("NAM", "has_country_flag", "NAM_rw_notes_sent"), False), notes)
            self.assertEqual(facts.get(("NAM", "has_country_flag", "NAM_rw_ultimatum_sent"), False), ultimatum)
        strike = next(e.value for e in self.events[BASE + ".21"] if e.key == "option" and scalar(e.value, "name") == BASE + ".21.e")
        facts = self.independent_facts()
        self.assertTrue(self.matches(block(strike, "trigger"), facts))
        self.apply(block(strike, "hidden_effect"), facts)
        self.assertFalse(facts[("NAM", "has_active_mission", "NAM_resource_war_deadline")])
        self.assertTrue(facts[("NAM", "has_country_flag", "NAM_rw_war_dispatched")])
        self.assertTrue(self.matches(self.triggers["NAM_rw_clock_running"], facts))
        dispatched = facts[("NAM", "variable", "global.NAM_rw_entry_dispatches")]
        self.apply(block(strike, "hidden_effect"), facts)
        self.assertEqual(facts[("NAM", "variable", "global.NAM_rw_entry_dispatches")], dispatched)

    def test_dossier_start_leaves_time_for_its_own_delivery(self):
        dossier = block(block(parsed(f"common/decisions/{BASE}_decisions.txt"), "NAM_restitution"), "NAM_ind_border_dossier")
        for remaining in (0, 1, 20, 21, 22):
            facts = self.independent_facts()
            facts[("NAM", "has_completed_focus", "NAM_neutral_basin")] = True
            facts[("NAM", "variable", "days_mission_timeout@NAM_resource_war_deadline")] = remaining
            self.assertEqual(self.matches(block(dossier, "available"), facts), remaining > 21)
        facts[("NAM", "has_country_flag", "NAM_ind_border_dossier_paid")] = True
        facts[("NAM", "has_country_flag", "NAM_ind_border_dossier_used")] = True
        facts[("NAM", "variable", "days_mission_timeout@NAM_resource_war_deadline")] = 1
        self.assertFalse(self.matches(block(dossier, "cancel_trigger"), facts))

    def test_gateway_reveals_preparation_but_war_uses_a_separate_tree(self):
        gateway = self.focuses["NAM_letters_to_the_centre"]
        self.assertNotIn("bypass", [e.key for e in gateway])
        self.assertIn("mark_focus_tree_layout_dirty", repr(block(gateway, "completion_reward")))
        for name, body in self.focuses.items():
            if not any(e.key == "allow_branch" for e in body):
                continue
            branch = block(body, "allow_branch")
            self.assertNotIn("NAM_inventory", [child.value for entry in body if entry.key == "prerequisite"
                                               for child in entry.value], name)
            self.assertGreater(int(scalar(body, "y")), int(scalar(gateway, "y")), name)
            facts = self.independent_facts()
            facts[("NAM", "has_completed_focus", "NAM_letters_to_the_centre")] = False
            self.assertFalse(self.matches(branch, facts), name)
            facts[("NAM", "has_completed_focus", "NAM_letters_to_the_centre")] = True
            self.assertTrue(self.matches(branch, facts), name)
            colonial = self.colonial_facts()
            colonial[("NAM", "has_completed_focus", "NAM_letters_to_the_centre")] = True
            self.assertTrue(self.matches(branch, colonial), name)
            self.assertFalse(self.matches(block(body, "available"), colonial), name)
        self.assertFalse(set(self.focuses) & set(self.wartime))
        alarm = self.wartime["NAM_alarm"]
        facts = self.independent_facts()
        self.assertFalse(self.matches(block(alarm, "available"), facts))
        facts[("NAM", "has_completed_focus", "NAM_letters_to_the_centre")] = False
        facts[("NAM", "has_global_flag", BASE + "_started")] = True
        self.assertNotIn("allow_branch", read(TREES["wartime"][0]))
        self.assertTrue(self.matches(block(alarm, "available"), facts))
        self.assertFalse(any(e.key == "prerequisite" for e in alarm))
        for language, message in (("russian", "§GОткрывает новые фокусы§!"),
                                  ("english", "§GUnlocks new focuses§!")):
            self.assertIn(f' NAM_preparation_gateway_tt:0 "{message}"',
                          read(f"localisation/{language}/{BASE}_l_{language}.yml"))

    def test_extended_ground_preparation_pays_for_diplomacy_and_finishes_before_its_real_deadline(self):
        for administration, economy, army in product(
                ("vertical", "districts"), ("export_quays", "domestic_refining"),
                ("field_guards", "mobile_columns")):
            with self.subTest(administration=administration, economy=economy, army=army):
                self.run_preparation_budget(administration, economy, army, extended=True)

    def test_council_procurement_checks_prices_and_settles_each_receipt_once(self):
        orders = {
            "NAM_council_fuel_reserve": (25, 150, "numeric", "has_fuel", 6000),
            "NAM_council_import_machinery": (35, 450, "building", "industrial_complex", 1),
            "NAM_council_arsenal_contract": (35, 250, "equipment", "infantry_equipment", 9000),
            "NAM_council_registrar_contract": (25, 150, "tech_bonus", "NAM_civil_engineer_training", (0.5, 1, "industry")),
            "NAM_council_workshop_contract": (25, 150, "building", "infrastructure", 1),
        }
        for name, (pp, money, kind, output, amount) in orders.items():
            decision = self.decisions[name]
            currencies = (("NAM", "numeric", "has_political_power"),
                          ("NAM", "variable", "ADISCORD_economy_treasury"))
            for index in (0, 1):
                facts = self.independent_facts()
                facts[currencies[index]] = (pp, money)[index] - 0.01
                self.assertFalse(self.matches(block(decision, "custom_cost_trigger"), facts))
                before = dict(facts)
                self.apply(block(decision, "complete_effect"), facts)
                self.assertEqual(facts, before)
            for outcome in ("delivery", "capitulation", "subjugation"):
                facts = self.independent_facts()
                for currency, value in zip(currencies, (pp, money)):
                    facts[currency] = value
                self.apply(block(decision, "complete_effect"), facts)
                self.assertEqual([facts[k] for k in currencies], [0, 0])
                paid = dict(facts)
                self.apply(block(decision, "complete_effect"), facts)
                self.assertEqual(facts, paid)
                facts[("NAM", "has_global_flag", BASE + "_started")] = True
                facts[("NAM", "has_completed_focus", scalar(block(decision, "visible"), "has_completed_focus"))] = False
                self.assertFalse(self.matches(block(decision, "cancel_trigger"), facts))
                if outcome == "delivery":
                    recipient = "67" if output == "industrial_complex" else "689" if output == "infrastructure" else "NAM"
                    before = facts.get((recipient, kind, output), 0)
                    self.apply(block(decision, "remove_effect"), facts)
                    self.assertEqual(facts[(recipient, kind, output)], amount if kind == "tech_bonus" else before + amount)
                else:
                    key = "has_capitulated" if outcome == "capitulation" else "is_subject"
                    facts[("NAM", key, "no")] = False
                    self.assertTrue(self.matches(block(decision, "cancel_trigger"), facts))
                    self.apply(block(decision, "cancel_effect"), facts)
                    self.assertEqual([facts[k] for k in currencies], [pp, money])
                settled = dict(facts)
                self.apply(block(decision, "remove_effect"), facts)
                self.apply(block(decision, "cancel_effect"), facts)
                self.assertEqual(facts, settled)

    def test_all_five_council_contracts_restore_support_only_on_delivery(self):
        categories = parsed(f"common/decisions/{BASE}_decisions.txt")
        self.assertFalse(any(e.key.startswith(("NAM_concede_", "NAM_bribe_")) for e in walk(categories)))
        groups = {"fuel_reserve": "oil", "import_machinery": "trade", "arsenal_contract": "garr",
                  "registrar_contract": "nam", "workshop_contract": "dist"}
        for stem, group in groups.items():
            name = "NAM_council_" + stem
            decision = self.decisions[name]
            for outcome in ("delivery", "cancel"):
                facts = self.independent_facts()
                for focus in self.focuses:
                    facts[("NAM", "has_completed_focus", focus)] = focus == scalar(block(decision, "visible"), "has_completed_focus")
                support = ("NAM", "variable", "NAM_grp_" + group + "_support")
                facts[support] = 40
                self.assertTrue(self.matches(block(decision, "visible"), facts), name)
                self.apply(block(decision, "complete_effect"), facts)
                self.assertEqual(facts[support], 40)
                self.apply(block(decision, "remove_effect" if outcome == "delivery" else "cancel_effect"), facts)
                self.assertEqual(facts[support], 52 if outcome == "delivery" else 40)
                after = dict(facts)
                self.apply(block(decision, "remove_effect"), facts)
                self.apply(block(decision, "cancel_effect"), facts)
                self.assertEqual(facts, after)
        for focus, stem, kind, item, amount in (
                ("NAM_supports_oil_compact", "fuel_reserve", "building", "infrastructure", 1),
                ("NAM_supports_export_houses", "import_machinery", "equipment", "convoy", 10),
                ("NAM_garrison_assembly", "arsenal_contract", "equipment", "infantry_equipment", 9000)):
            facts = self.independent_facts()
            recipient = "67" if kind == "building" else "NAM"
            before = facts.get((recipient, kind, item), 0)
            self.apply(block(self.focuses[focus], "completion_reward"), facts)
            self.assertEqual(facts[(recipient, kind, item)], before + amount)
            self.assertFalse(facts.get(("NAM", "has_country_flag", "NAM_council_" + stem + "_paid"), False))
            after = dict(facts)
            self.apply(block(self.decisions["NAM_council_" + stem], "cancel_effect"), facts)
            self.assertEqual(facts, after)

    def test_council_deliveries_reach_and_restore_favour_threshold_despite_monthly_drift(self):
        self.effects = {name: self.effects[name] for name in (
            "NAM_groups_initialize", "NAM_groups_monthly", "NAM_groups_refresh",
            "NAM_favour_pay_support", "NAM_spend_treasury")}
        favours = block(parsed(f"common/decisions/{BASE}_decisions.txt"), "NAM_supports")
        for stem, group in (("fuel_reserve", "oil"), ("import_machinery", "trade"),
                            ("arsenal_contract", "garr"), ("registrar_contract", "nam"),
                            ("workshop_contract", "dist")):
            decision = self.decisions["NAM_council_" + stem]
            favour = block(favours, "NAM_favour_" + group)
            duration = int(scalar(decision, "days_remove"))
            cycle = duration + int(scalar(decision, "days_re_enable"))
            third_delivery = 2 * cycle + duration
            facts = self.independent_facts()
            facts[("NAM", "has_country_flag", "NAM_groups_initialized")] = False
            self.apply(self.effects["NAM_groups_initialize"], facts)
            for pillar in ("nam", "oil", "dist", "garr", "trade"):
                facts[("NAM", "variable", "NAM_grp_" + pillar + "_support")] = 50
            support = ("NAM", "variable", "NAM_grp_" + group + "_support")
            for day in range(third_delivery + int(scalar(favour, "days_re_enable")) + 1):
                if day and day % 30 == 0:
                    self.apply(self.effects["NAM_groups_monthly"], facts)
                if day % cycle == 0 and day // cycle < 4:
                    self.assertTrue(self.matches(block(decision, "custom_cost_trigger"), facts), group)
                    self.apply(block(decision, "complete_effect"), facts)
                if day >= duration and (day - duration) % cycle == 0:
                    self.apply(block(decision, "remove_effect"), facts)
                    # Higher infrastructure or another factory is an actual site change.
                    # This fixture models separate later works while slots remain available.
                if day == third_delivery:
                    self.assertLess(day, 450)
                    self.assertTrue(self.matches(block(favour, "available"), facts), group)
                    before = facts[support]
                    self.apply(block(favour, "complete_effect"), facts)
                    self.assertEqual(facts[support], before - 15)
            self.assertTrue(self.matches(block(favour, "available"), facts), group)

    def test_amnesty_recruits_arrive_once_in_either_completion_order(self):
        subset = {name: self.effects[name] for name in ("NAM_weber_amnesty", "NAM_deliver_amnesty_recruits")}
        for amnesty_first in (False, True):
            facts = self.independent_facts()
            facts[("NAM", "has_completed_focus", "NAM_mine_councils")] = False
            facts[("NAM", "numeric", "has_manpower")] = 120
            with patch.object(self, "effects", subset):
                if amnesty_first:
                    self.apply(subset["NAM_weber_amnesty"], facts)
                    self.assertEqual(facts[("NAM", "numeric", "has_manpower")], 120)
                self.apply(block(self.focuses["NAM_mine_councils"], "completion_reward"), facts)
                self.assertEqual(facts[("NAM", "numeric", "has_manpower")], 2120 if amnesty_first else 120)
                facts[("NAM", "has_completed_focus", "NAM_mine_councils")] = True
                if not amnesty_first:
                    self.apply(subset["NAM_weber_amnesty"], facts)
                self.apply(subset["NAM_deliver_amnesty_recruits"], facts)
                self.assertEqual(facts[("NAM", "numeric", "has_manpower")], 2120)

    def underground_facts(self):
        facts = self.economy_facts()
        facts[("NAM", "has_variable", "NAM_underground")] = True
        facts[("NAM", "variable", "NAM_underground")] = 50
        for group in ("nam", "oil", "dist", "garr", "trade"):
            facts[("NAM", "variable", f"NAM_grp_{group}_support")] = 50
        return facts

    def test_paid_marines_add_to_the_readiness_reward_at_both_landing_sites(self):
        landing = block(self.effects["NAM_wor_revenge_landing"], "if")
        allocation_end = next(index for index, entry in enumerate(landing)
                              if entry.key == "set_temp_variable"
                              and scalar(entry.value, "var") == "NAM_landing_index")
        allocation = [entry for entry in landing[:allocation_end] if entry.key != "limit"]

        def bind_controller(entries):
            return [replace(e, key="EFL" if e.key == "controller" else e.key,
                            value=bind_controller(e.value) if isinstance(e.value, list) else e.value)
                    for e in entries]

        allocation = bind_controller(allocation)
        landing_news = next(entry.value for entry in landing if entry.key == "if"
                            and any(child.key == "country_event" for child in entry.value))
        with patch.object(self, "effects", {}):
            for readiness, paid, hostile_port in product((0, 69.99, 70, 100), range(4), (False, True)):
                facts = self.economy_facts()
                facts[("NAM", "variable", "NAM_revenge_readiness")] = readiness
                facts[("NAM", "variable", "NAM_marine_orders_paid")] = paid
                facts[("EFL", "has_war_with", "NAM")] = hostile_port
                facts[("700", "is_controlled_by", "NAM")] = False
                self.apply(allocation, facts)
                landed = facts[("NAM", "variable", "NAM_marines_landed")]
                island = facts[("NAM", "variable", "NAM_marines_island")]
                free = 2 + int(readiness >= 70)
                self.assertEqual(landed + island, free + paid, (readiness, paid, hostile_port))
                self.assertEqual(landed, min(3, free + paid) if hostile_port else 0)
                self.assertEqual(facts[("NAM", "variable", "NAM_marines_orders_delivered")], paid)
                self.assertEqual(self.matches(block(landing_news, "limit"), facts), hostile_port)
        loops = [entry.value for entry in landing if entry.key == "while_loop_effect"]
        self.assertEqual(len(loops), 2)
        for loop, count, destination in zip(loops, ("NAM_marines_landed", "NAM_marines_island"), ("700", "capital_scope")):
            self.assertEqual(scalar(block(block(loop, "limit"), "check_variable"), "value"), count)
            unit = block(block(loop, destination), "create_unit")
            self.assertEqual(scalar(unit, "owner"), "NAM")
            self.assertIn('division_template = "Island Marines"', scalar(unit, "division"))

    def marine_order_facts(self, humanist):
        facts = self.economy_facts()
        facts[("fixture", "track_templates")] = True
        facts[("fixture", "track_loops")] = True
        facts[("fixture", "track_units")] = True
        facts[("NAM", "tag", "NAM")] = True
        facts[("NAM", "capital")] = "225"
        facts[("NAM", "has_global_flag", "ADISCORD_nam_resource_war_island_exile")] = True
        facts[("NAM", "has_country_flag", "NAM_exile_humanist")] = humanist
        facts[("NAM", "has_country_flag", "NAM_exile_radical")] = not humanist
        for focus in ("NAM_exile_marine_orders", "NAM_hum_marine_contracts"):
            facts[("NAM", "has_completed_focus", focus)] = True
        facts[("NAM", "numeric", "has_manpower")] = 12000
        for variable, value in (("NAM_marine_orders_paid", 0), ("NAM_marine_order_cap", 3),
                                ("NAM_corp_capital", 300), ("NAM_pirate_loot", 300), ("NAM_revenge_readiness", 70)):
            facts[("NAM", "variable", variable)] = value
        return facts

    def test_marine_refund_preserves_the_fixed_template_until_delivery(self):
        definitions = {e.key: e.value for category in parsed(f"common/decisions/{BASE}_decisions.txt")
                       for e in category.value if isinstance(e.value, list)}
        subset = {name: self.effects[name] for name in (
            "NAM_marine_ensure_template", "NAM_marine_unlock_template", "NAM_marine_orders_refund",
            "NAM_corp_capital_add", "NAM_pirate_loot_add",
        )}
        with patch.object(self, "effects", subset):
            for humanist in (False, True):
                with self.subTest(humanist=humanist):
                    facts = self.marine_order_facts(humanist)
                    order = definitions["NAM_order_marines_corp" if humanist else "NAM_order_marines"]
                    currency = "NAM_corp_capital" if humanist else "NAM_pirate_loot"
                    for _ in range(2):
                        self.assertTrue(self.matches(block(order, "visible"), facts))
                        self.apply(block(order, "complete_effect"), facts)
                        self.assertEqual(facts[("NAM", "variable", "NAM_marine_orders_paid")], 1)
                        self.assertTrue(facts[("NAM", "template_locked", "Island Marines")])
                        self.assertTrue(facts[("NAM", "template_recruitable", "Island Marines")])
                        self.apply(subset["NAM_marine_orders_refund"], facts)
                        self.apply(subset["NAM_marine_orders_refund"], facts)
                        self.assertEqual(facts[("NAM", "numeric", "has_manpower")], 12000)
                        self.assertEqual(facts[("NAM", "variable", currency)], 300)
                        self.assertTrue(facts[("NAM", "template_locked", "Island Marines")])
                    facts[("NAM", "has_variable", "NAM_marines_orders_delivered")] = True
                    self.apply(subset["NAM_marine_unlock_template"], facts)
                    self.assertFalse(facts[("NAM", "template_locked", "Island Marines")])
                    self.assertFalse(self.matches(block(order, "visible"), facts))
                    self.assertFalse(self.matches(self.triggers["NAM_marine_order_can_place"], facts))
                    before = facts.copy()
                    self.apply(block(order, "complete_effect"), facts)
                    self.assertEqual(facts, before)

    def test_sardan_levies_and_rakhma_wells_follow_local_control_and_governance(self):
        tree = self.exile_trees["exile_radical"][1]
        levy, wells = (tree[n] for n in ("NAM_rad_sardan_levies", "NAM_rad_rakhma_wells"))
        self.assertIn("oil = 1", read("history/states/255-255.txt"))
        facts = PostedGarrisons(self.independent_facts())
        sites = ("243", "260", "704", "255", "249")
        facts[("NAM", "array", "NAM_conquered_states")] = sites
        for state in sites:
            facts[(state, "is_core_of", "SDR")] = state in ("243", "260", "704")
            facts[(state, "has_state_flag", "NAM_conquered_state")] = True
            facts[(state, "is_owned_by", "NAM")] = True
            facts[(state, "is_controlled_by", "NAM")] = state != "704"
            facts[(state, "has_state_flag", "NAM_rad_local_council")] = state == "243"
        with patch.dict(self.effects, {"NAM_groups_refresh": []}):
            self.assertTrue(self.matches(block(levy, "available"), facts))
            self.assertFalse(self.matches(block(levy, "bypass"), facts))
            facts[("NAM", "numeric", "has_manpower")] = 100
            self.apply(block(levy, "completion_reward"), facts)
            self.assertEqual(facts[("NAM", "numeric", "has_manpower")], 600)
            self.assertEqual([facts.get((s, "numeric", "resistance"), 0) for s in sites], [0, 5, 0, 0, 0])
            facts[("260", "is_owned_by", "NAM")] = False
            self.assertFalse(self.matches(block(levy, "available"), facts))
            self.assertTrue(self.matches(block(levy, "bypass"), facts))
            before = dict(facts)
            self.apply(block(levy, "completion_reward"), facts)
            self.assertEqual(facts, before)
            self.assertEqual(scalar(block(tree["NAM_rad_army_of_dominion"], "prerequisite"), "focus"),
                             "NAM_rad_sardan_levies")
            for ownership, control, council in product((True, False), repeat=3):
                state = PostedGarrisons(facts)
                state[("255", "is_owned_by", "NAM")] = ownership
                state[("255", "is_controlled_by", "NAM")] = control
                state[("255", "has_state_flag", "NAM_rad_local_council")] = council
                works = ownership and control and not council
                self.assertEqual(self.matches(block(wells, "available"), state), works)
                self.assertEqual(self.matches(block(wells, "bypass"), state), not works)
                fuel = ("NAM", "numeric", "has_fuel")
                before = state[fuel]
                self.apply(block(wells, "completion_reward"), state)
                self.assertEqual(state[fuel] - before, 5000 if works else 0)
                self.assertEqual(state.get(("255", "resource", "oil"), 0), 3 if works else 0)
                self.assertNotIn(("NAM", "variable", "NAM_oil_bonus_units"), state)
                self.assertEqual(state.get(("NAM", "variable", "NAM_grp_oil_support"), 0) -
                                 facts.get(("NAM", "variable", "NAM_grp_oil_support"), 0), 4 if works else 0)

    def test_radical_command_post_uses_a_deployed_division_and_paid_stores(self):
        tree = self.exile_trees["exile_radical"][1]
        focus = tree["NAM_rad_garrison_rule"]
        self.assertEqual(scalar(block(focus, "completion_reward"), "unlock_decision_tooltip"),
                         "NAM_rad_deploy_command_post")
        self.assertFalse({"add_manpower", "army_experience"} & {e.key for e in walk(block(focus, "completion_reward"))})
        self.assertEqual({e.value for e in block(tree["NAM_rad_machines_to_islands"], "prerequisite")},
                         {"NAM_rad_garrison_rule", "NAM_rad_extraction_trusts"})
        category = block(parsed(f"common/decisions/{BASE}_decisions.txt"), "NAM_consolidation")
        command = block(category, "NAM_rad_deploy_command_post")
        self.assertEqual(scalar(command, "target_array"), "NAM.owned_states")
        self.assertEqual(scalar(command, "cost"), "0")
        post = "NAM_rad_command_post"
        modifier = block(parsed("common/dynamic_modifiers/ADISCORD_dynamic_modifiers_NAM.txt"), post)
        self.assertEqual((float(scalar(modifier, "local_supplies")), float(scalar(modifier, "resistance_target"))),
                         (1.25, -0.10))
        for cause, target, expected in (("district", "241", True), ("full_road", "241", True),
                ("capital", "700", True), ("capital_with_district", "700", False),
                ("council", "241", False), ("unheld", "241", False), ("foreign", "241", False),
                ("no_divisions", "241", False), ("no_order", "241", False), ("subject", "241", False),
                ("trucks", "241", False), ("tools", "241", False)):
            with self.subTest(cause=cause):
                facts = PostedGarrisons(self.independent_facts())
                facts[("NAM", "array", "NAM_conquered_states")] = ("241",)
                facts[("NAM", "has_country_flag", "NAM_exile_radical")] = True
                facts[("NAM", "has_completed_focus", "NAM_rad_garrison_rule")] = True
                facts[("NAM", "is_subject", "no")] = cause != "subject"
                facts[("NAM", "has_country_flag", "NAM_rad_garrison_order_active")] = cause != "no_order"
                for state in ("241", "700"):
                    facts[(state, "is_owned_by", "NAM")] = state == "700" or cause != "foreign"
                    facts[(state, "is_controlled_by", "NAM")] = state == "700" or cause not in ("unheld", "capital")
                    facts[(state, "is_capital", "yes")] = state == "700"
                    facts[(state, "has_state_flag", "NAM_conquered_state")] = state == "241"
                    facts[(state, "has_state_flag", "NAM_rad_local_council")] = state == "241" and cause == "council"
                    facts[(state, "variable", "fixture_posted_divisions")] = 0 if cause == "no_divisions" else 1
                    facts[(state, "numeric", "infrastructure")] = 5 if cause == "full_road" else 4
                keys = [("NAM", "equipment", e) for e in ("motorized_equipment", "support_equipment")]
                stocks = (29.99 if cause == "trucks" else 30, 59.99 if cause == "tools" else 60)
                facts.update(zip(keys, stocks))
                order = self.bind_field(command, target)
                self.assertEqual(all(self.matches(block(order, check), facts)
                                     for check in ("visible", "available", "custom_cost_trigger")), expected)
                for _ in range(2):
                    self.apply(block(order, "complete_effect"), facts)
                self.assertEqual(tuple(facts[k] for k in keys), (0, 0) if expected else stocks)
                self.assertEqual(facts.get((target, "has_dynamic_modifier", post), False), expected)
                self.assertEqual(facts.get((target, "building", "infrastructure"), 0),
                                 int(expected and cause != "full_road"))
                if expected:
                    self.assertTrue(self.matches(block(modifier, "enable"), facts, target))
                    facts[(target, "variable", "fixture_posted_divisions")] = 0
                    self.assertFalse(self.matches(block(modifier, "enable"), facts, target))
                    self.assertFalse(self.matches(block(modifier, "remove_trigger"), facts, target))
                    facts[(target, "variable", "fixture_posted_divisions")] = 2
                    self.assertTrue(self.matches(block(modifier, "enable"), facts, target))
                    self.apply(self.effects["NAM_rad_devolve_district"], facts, target)
                    self.assertFalse(facts[(target, "has_dynamic_modifier", post)])

    def test_radical_garrison_upkeep_follows_the_battalions_on_the_map(self):
        for staffed, has_order in ((True, True), (True, False), (False, True)):
            facts = PostedGarrisons(self.independent_facts())
            facts.update({
                ("NAM", "array", "NAM_conquered_states"): ("241", "249", "253", "260"),
                ("NAM", "has_country_flag", "NAM_consolidation_started"): True,
                ("NAM", "has_country_flag", "NAM_exile_radical"): True,
                ("NAM", "has_country_flag", "NAM_rad_garrison_order_active"): has_order,
                ("NAM", "variable", "NAM_consolidation"): 75,
                ("NAM", "numeric", "has_stability"): 0.8,
            })
            for state in facts[("NAM", "array", "NAM_conquered_states")]:
                facts[(state, "has_state_flag", "NAM_conquered_state")] = True
                facts[(state, "is_owned_by", "NAM")] = state != "260"
                facts[(state, "is_controlled_by", "NAM")] = state != "253"
                facts[(state, "has_state_flag", "NAM_rad_local_council")] = state == "249"
                facts[(state, "variable", "fixture_posted_divisions")] = 3 if staffed else 0
            cash = ("NAM", "variable", "ADISCORD_economy_treasury")
            before = facts[cash]
            with patch.dict(self.effects, {"NAM_consolidation_clamp": []}):
                self.apply(self.effects["NAM_consolidation_monthly"], facts)
            expected = 3 + 20 * has_order if staffed else 0
            self.assertEqual(before - facts[cash], expected)
            self.assertEqual(facts[("NAM", "variable", "NAM_consolidation_growth")], 5 if staffed and has_order else 2)

    def test_splitting_the_coalition_diverts_only_the_actual_leaders_stocks_once(self):
        focus = self.exile_trees["exile_humanist"][1]["NAM_hum_split_coalition"]
        self.assertEqual(scalar(block(focus, "mutually_exclusive"), "focus"), "NAM_hum_appeal_to_nations")
        self.assertFalse({"SDR", "KDR", "RHM", "EFL", "AZH", "add_war_support", "add_stability"} &
                         {entry.key for entry in walk(block(focus, "completion_reward"))})
        cases = (
            ("EFL", "split", (6000, 700), (1000, 100)),
            ("AZH", "split", (1131, 9), (283, 2)),
            ("EFL", "split", (0, 401), (0, 100)),
            ("AZH", "split", (1, 0), (0, 0)),
            ("EFL", "appeal", (6000, 700), (0, 0)),
            ("AZH", "takeover", (6000, 700), (0, 0)),
        )
        subset = {name: self.effects[name] for name in (
            "NAM_wor_revenge_landing", "NAM_hum_divert_return_supplies",
            "NAM_marine_ensure_template", "NAM_marine_unlock_template")}
        with patch.object(self, "effects", subset):
            for leader, course, stocks, captured in cases:
                with self.subTest(leader=leader, course=course, stocks=stocks):
                    facts = self.marine_order_facts(True)
                    facts[("event_target", "NAM_wor_primary")] = leader
                    facts[("fixture", "fuel_logistics")] = True
                    facts[("NAM", "has_event_target", "NAM_wor_primary")] = True
                    facts[("NAM", "is_subject", "no")] = True
                    facts[("NAM", "has_completed_focus", "NAM_hum_split_coalition")] = course != "appeal"
                    facts[("NAM", "has_country_flag", "NAM_corp_takeover")] = course == "takeover"
                    facts[("700", "is_controlled_by", "NAM")] = True
                    facts[("NAM", "variable", "NAM_marine_orders_paid")] = 0
                    kinds = ("infantry_equipment", "motorized_equipment")
                    for equipment, stock in zip(kinds, stocks):
                        facts[(leader, "variable", "num_equipment@" + equipment)] = stock
                        for tag in ("AZH", "EFL", "SDR", "KDR", "RHM"):
                            facts[(tag, "equipment", equipment)] = stock if tag == leader else 1500
                        facts[("NAM", "equipment", equipment)] = 100
                    for _ in range(2):
                        self.apply(subset["NAM_wor_revenge_landing"], facts)
                    for equipment, stock, moved in zip(kinds, stocks, captured):
                        self.assertEqual(facts[(leader, "equipment", equipment)], stock - moved)
                        self.assertEqual(facts[("NAM", "equipment", equipment)], 100 + moved)
                        for tag in {"AZH", "EFL", "SDR", "KDR", "RHM"} - {leader}:
                            self.assertEqual(facts[(tag, "equipment", equipment)], 1500)

    def test_first_return_landing_delivers_once_even_to_an_owned_harbour(self):
        subset = {name: self.effects[name] for name in (
            "NAM_wor_revenge_landing", "NAM_marine_ensure_template", "NAM_marine_unlock_template",
        )}
        with patch.object(self, "effects", subset):
            for own_harbour, paid in product((False, True), range(4)):
                facts = self.marine_order_facts(True)
                facts[("NAM", "variable", "NAM_marine_orders_paid")] = paid
                facts[("NAM", "has_global_flag", "NAM_war_of_return_started")] = True
                facts[("700", "is_owned_by", "NAM")] = own_harbour
                facts[("700", "is_controlled_by", "NAM")] = True
                self.apply(subset["NAM_wor_revenge_landing"], facts)
                self.assertEqual(facts.get(("NAM", "reward", "spawned_divisions"), 0), 3 + paid)
                self.assertEqual(facts[("NAM", "variable", "NAM_marine_orders_paid")], 0)
                self.assertTrue(facts[("NAM", "has_variable", "NAM_marines_orders_delivered")])
                self.assertFalse(facts[("NAM", "template_locked", "Island Marines")])
                landing_news = next(entry.value for entry in block(subset["NAM_wor_revenge_landing"], "if")
                                    if entry.key == "if" and any(child.key == "country_event" for child in entry.value))
                self.assertFalse(self.matches(block(landing_news, "limit"), facts))
                facts[("NAM", "has_global_flag", "NAM_war_of_return_resolved")] = True
                self.assertTrue(self.matches(self.triggers["NAM_exile_return_programme_open"], facts))
                self.assertFalse(self.matches(self.triggers["NAM_marine_order_can_place"], facts))
                facts[("NAM", "has_global_flag", "NAM_war_of_return_resolved")] = False
                self.apply(subset["NAM_wor_revenge_landing"], facts)
                self.assertEqual(facts[("NAM", "reward", "spawned_divisions")], 3 + paid)

    def test_free_zone_settlement_consumes_only_its_own_receipt_once(self):
        subset = {name: self.effects[name] for name in (
            "NAM_corp_zone_establish", "NAM_corp_zone_release", "NAM_corp_count_zones",
            "NAM_corp_count_zone", "NAM_corp_capital_add",
        )}
        callbacks = ("NAM_corp_zone_establish", "NAM_corp_zone_release")
        with patch.object(self, "effects", subset):
            for owned, controlled, operable, first, second in product((False, True), (False, True), (False, True), callbacks, callbacks):
                with self.subTest(owned=owned, controlled=controlled, operable=operable, first=first, second=second):
                    facts = self.economy_facts()
                    facts[("NAM", "has_capitulated", "no")] = operable
                    facts[("225", "is_owned_by", "NAM")] = owned
                    facts[("225", "is_controlled_by", "NAM")] = controlled
                    for state in ("225", "226"):
                        facts[(state, "has_state_flag", "NAM_free_zone_pending")] = True
                    facts[("NAM", "variable", "NAM_free_zones_pending")] = 2
                    facts[("NAM", "variable", "NAM_corp_capital")] = 0
                    facts[("NAM", "variable", "NAM_corp_influence")] = 20
                    self.apply(subset[first], facts, "225")
                    self.apply(subset[second], facts, "225")
                    delivered = owned and controlled and operable and first == "NAM_corp_zone_establish"
                    self.assertEqual(facts[("NAM", "variable", "NAM_free_zones_pending")], 1)
                    self.assertTrue(facts[("226", "has_state_flag", "NAM_free_zone_pending")])
                    self.assertFalse(facts[("225", "has_state_flag", "NAM_free_zone_pending")])
                    self.assertEqual(facts[("NAM", "variable", "NAM_corp_capital")], 20 if delivered else 0)
                    self.assertEqual(facts[("NAM", "variable", "NAM_corp_influence")], 25 if delivered else 20)
                    self.assertEqual(facts.get(("225", "has_state_flag", "NAM_free_zone"), False), delivered)

    def test_humanist_district_buildings_require_a_current_subject_and_control(self):
        _, focuses = self.exile_trees["exile_humanist"]
        routes = (
            ("NAM_hum_dry_river_works", "SDR", "industrial_complex"),
            ("NAM_hum_water_compact", "RHM", "infrastructure"),
            ("NAM_hum_caravan_charter", "KDR", "infrastructure"),
        )
        with patch.object(self, "effects", {}):
            for (name, recipient, building), subject, owned, controlled in product(routes, (False, True), (False, True), (False, True)):
                with self.subTest(focus=name, subject=subject, owned=owned, controlled=controlled):
                    facts = self.economy_facts()
                    facts[("fixture", "track_units")] = True
                    facts[(recipient, "exists", "yes")] = True
                    facts[(recipient, "has_country_flag", "NAM_federal_district")] = True
                    facts[(recipient, "is_subject_of", "NAM")] = subject
                    facts[(recipient, "capital")] = "726"
                    facts[("726", "is_owned_by", recipient)] = owned
                    facts[("726", "is_controlled_by", recipient)] = controlled
                    self.apply(block(focuses[name], "completion_reward"), facts)
                    self.assertEqual(facts.get(("726", "building", building), 0), int(subject and owned and controlled))
                    self.assertEqual(facts.get((recipient, "reward", "stability"), 0), (0.10 if recipient == "RHM" else 0.05) if subject else 0)
        roads = block(block(focuses["NAM_hum_union_roads"], "completion_reward"), "hidden_effect")
        recipients = block(roads, "every_subject_country")
        self.assertEqual(scalar(block(recipients, "limit"), "has_country_flag"), "NAM_federal_district")
        capital = block(recipients, "capital_scope")
        for owned, controlled in product((False, True), repeat=2):
            facts = {("726", "is_owned_by", "PREV"): owned, ("726", "is_controlled_by", "PREV"): controlled}
            self.apply(capital, facts, "726")
            self.assertEqual(facts.get(("726", "building", "industrial_complex"), 0), int(owned and controlled))

    def test_sweep_risk_uses_exact_percentages_at_fractional_support_boundary(self):
        country = block(block(self.effects["NAM_sweep_complete"], "if"), "NAM")

        def bind_previous(entries, state):
            return [replace(e, key=state if e.key == "PREV" else e.key,
                            value=bind_previous(e.value, state) if isinstance(e.value, list) else e.value)
                    for e in entries]

        subset = {name: self.effects[name] for name in
                  ("NAM_sweep_excesses", "NAM_underground_add", "NAM_underground_clamp")}
        with patch.object(self, "effects", subset):
            for support, chance in ((0, 30), (59, 30), (59.99, 30), (60, 15), (100, 15)):
                for capital, reduction in ((False, 8), (True, 12)):
                    facts = self.underground_facts()
                    facts[("NAM", "variable", "NAM_grp_garr_support")] = support
                    scoped = bind_previous(country, "688" if capital else "67")
                    draws = [entry.value for scope, entry in
                             selected_effects(self.expand(scoped), facts, "NAM") if entry.key == "random"]
                    self.assertEqual(len(draws), 1)
                    self.assertEqual(float(scalar(draws[0], "chance")), chance)
                    self.apply(scoped, facts)
                    self.assertEqual(facts[("NAM", "variable", "NAM_underground")], 50 - reduction)
                    self.assertEqual(facts[("NAM", "variable", "NAM_grp_dist_support")], 46)
                    self.apply(draws[0], facts)
                    self.assertEqual(facts[("NAM", "variable", "NAM_underground")], 53 - reduction)
                    self.assertEqual(facts[("NAM", "variable", "NAM_grp_dist_support")], 42)
                    self.assertEqual(facts[("NAM", "reward", "stability")], -0.02)

    def test_talks_settle_only_their_own_paid_round_and_recheck_amnesty_support(self):
        decisions = block(parsed(f"common/decisions/{BASE}_decisions.txt"), "NAM_underground")
        subset = {name: self.effects[name] for name in
                  ("NAM_weber_talks_refund", "NAM_spend_treasury", "NAM_add_treasury",
                   "NAM_underground_clamp", "NAM_weber_amnesty", "NAM_deliver_amnesty_recruits")}
        pp_key = ("NAM", "numeric", "has_political_power")
        cash_key = ("NAM", "variable", "ADISCORD_economy_treasury")
        receipt_key = ("NAM", "variable", "NAM_weber_talks_deposit")
        with patch.object(self, "effects", subset):
            first = block(decisions, "NAM_weber_talks_1")
            facts = self.underground_facts()
            self.apply(block(first, "remove_effect"), facts)
            self.assertEqual(facts[("NAM", "variable", "NAM_underground")], 40)
            settled = dict(facts)
            self.apply(block(first, "remove_effect"), facts)
            self.assertEqual(facts, settled)
            for number, pp, deposit in ((2, 50, 100), (3, 75, 200)):
                decision = block(decisions, f"NAM_weber_talks_{number}")

                def ready():
                    facts = self.underground_facts()
                    facts[("NAM", "has_country_flag", f"NAM_weber_talks_{number - 1}_done")] = True
                    facts[pp_key], facts[cash_key] = pp, deposit
                    return facts

                for key in (pp_key, cash_key):
                    facts = ready()
                    facts[key] -= 0.01
                    before = dict(facts)
                    self.apply(block(decision, "complete_effect"), facts)
                    self.assertEqual(facts, before)
                for outcome in ("success", "uprising", "capitulation", "support_lost"):
                    if number == 2 and outcome == "support_lost":
                        continue
                    for callback in ("remove_effect", "cancel_effect"):
                        if outcome == "success" and callback == "cancel_effect":
                            continue
                        facts = ready()
                        self.apply(block(decision, "complete_effect"), facts)
                        self.assertEqual((facts[pp_key], facts[cash_key], facts[receipt_key]), (0, 0, deposit))
                        paid = dict(facts)
                        self.apply(block(decision, "complete_effect"), facts)
                        self.assertEqual(facts, paid)
                        self.assertFalse(self.matches(block(decision, "available"), facts))
                        if outcome == "uprising":
                            facts[("NAM", "country_exists", "SLF")] = True
                        elif outcome == "capitulation":
                            facts[("NAM", "has_capitulated", "no")] = False
                        elif outcome == "support_lost":
                            facts[("NAM", "variable", "NAM_grp_dist_support")] = 49.99
                        self.assertEqual(self.matches(block(decision, "cancel_trigger"), facts), outcome != "success")
                        self.apply(block(decision, callback), facts)
                        self.assertEqual(facts[pp_key], 0)
                        self.assertEqual(facts[cash_key], 0 if outcome == "success" else deposit)
                        self.assertFalse(facts[("NAM", "has_variable", "NAM_weber_talks_deposit")])
                        reward = "NAM_weber_talks_2_done" if number == 2 else "NAM_weber_amnesty"
                        self.assertEqual(facts.get(("NAM", "has_country_flag", reward), False), outcome == "success")
                        settled = dict(facts)
                        self.apply(block(decision, "remove_effect"), facts)
                        self.apply(block(decision, "cancel_effect"), facts)
                        self.assertEqual(facts, settled)
                facts = ready()
                facts[receipt_key] = 300 - deposit
                facts[("NAM", "has_variable", "NAM_weber_talks_deposit")] = True
                before = dict(facts)
                for callback in ("complete_effect", "remove_effect", "cancel_effect"):
                    self.apply(block(decision, callback), facts)
                self.assertEqual(facts, before)

    def test_cache_search_rechecks_current_district_before_native_payment_settlement(self):
        decisions = block(parsed(f"common/decisions/{BASE}_decisions.txt"), "NAM_underground")
        search = self.bind_field(block(decisions, "NAM_hunt_caches"))
        subset = {"NAM_underground_clamp": self.effects["NAM_underground_clamp"]}
        with patch.object(self, "effects", subset):
            for blocked in (None, "owner", "control", "amnesty", "searched", "empty"):
                facts = self.underground_facts()
                before_pp = facts[("NAM", "numeric", "has_political_power")]
                facts[("NAM", "numeric", "has_political_power")] -= 30
                if blocked in ("owner", "control"):
                    predicate = "is_owned_by" if blocked == "owner" else "is_controlled_by"
                    facts[("67", predicate, "NAM")] = False
                elif blocked == "amnesty":
                    facts[("NAM", "has_country_flag", "NAM_weber_amnesty")] = True
                elif blocked == "searched":
                    facts[("67", "has_state_flag", "NAM_caches_searched")] = True
                elif blocked == "empty":
                    facts[("NAM", "variable", "NAM_underground")] = 0
                self.apply(block(search, "complete_effect"), facts)
                self.assertEqual(facts[("NAM", "numeric", "has_political_power")], before_pp - (30 if blocked is None else 0))
                self.assertEqual(facts.get(("NAM", "equipment", "infantry_equipment"), 0), 4500 if blocked is None else 0)
                if blocked is None:
                    self.assertEqual(facts[("NAM", "variable", "NAM_underground")], 40)
                    self.assertEqual(facts[("NAM", "variable", "NAM_grp_dist_support")], 45)
                    self.assertTrue(facts[("67", "has_state_flag", "NAM_caches_searched")])
                    facts[("NAM", "numeric", "has_political_power")] -= 30
                    self.apply(block(search, "complete_effect"), facts)
                    self.assertEqual(facts[("NAM", "equipment", "infantry_equipment")], 4500)
                    self.assertEqual(facts[("NAM", "numeric", "has_political_power")], before_pp - 30)

    def test_underground_responses_settle_exact_losses_and_reject_stale_targets(self):
        def bind_value(value):
            if value == "ROOT":
                return "NAM"
            if isinstance(value, str) and value.startswith("ROOT."):
                return "NAM." + value.removeprefix("ROOT.")
            return value

        def bind(entries):
            return [replace(e, key="67" if e.key == "event_target:NAM_ug_field" else e.key,
                            value=bind(e.value) if isinstance(e.value, list) else bind_value(e.value))
                    for e in entries]

        def current_case():
            facts = self.economy_facts()
            facts[("NAM", "has_variable", "NAM_underground")] = True
            facts[("NAM", "has_event_target", "NAM_ug_field")] = True
            facts[("NAM", "numeric", "command_power")] = 15
            return facts

        effects = {name: bind(self.effects[name]) for name in
                   ("NAM_field_apply_damage", "NAM_field_apply_repair", "NAM_underground_close_event", "NAM_spend_treasury")}
        with patch.object(self, "effects", effects):
            for number in (85, 86):
                event = self.events[f"{BASE}.{number}"]
                response = bind(next(e.value for e in event if e.key == "option"
                                     and scalar(e.value, "name") == f"{BASE}.{number}.d_option"))
                close = next(e.value for e in event if e.key == "option" and scalar(e.value, "name") == "NAM_ug_close_case")
                for ended in ("amnesty", "war", "resolution"):
                    facts = current_case()
                    if ended == "amnesty":
                        facts[("NAM", "has_country_flag", "NAM_weber_amnesty")] = True
                    else:
                        facts[("NAM", "has_global_flag", BASE + ("_started" if ended == "war" else "_resolved"))] = True
                    facts[("NAM", "variable", "NAM_ug_rifles_stolen")] = 500
                    facts[("67", "variable", "NAM_ug_damage_receipt")] = 5
                    self.assertTrue(self.matches(block(close, "trigger"), facts))
                    self.assertFalse(self.matches(block(response, "trigger"), facts))
                    self.apply(response, facts)
                    self.assertEqual(facts[("NAM", "numeric", "command_power")], 15)
                    self.assertNotIn(("NAM", "equipment", "infantry_equipment"), facts)
                if number == 86:
                    chase = next(e.value for e in event if e.key == "option"
                                 and scalar(e.value, "name") == f"{BASE}.86.a")
                    success = block(block(block(chase, "hidden_effect"), "if"), "random_list")[0].value
                    for stolen in (0, 0.5, 500, 1500):
                        facts = current_case()
                        facts[("NAM", "variable", "NAM_ug_rifles_stolen")] = stolen
                        self.apply(success, facts)
                        self.assertEqual(facts[("NAM", "equipment", "infantry_equipment")], min(1000, stolen))
                    for stolen in (0.5, 500, 1500):
                        facts = current_case()
                        facts[("NAM", "variable", "NAM_ug_rifles_stolen")] = stolen
                        self.assertTrue(self.matches(block(response, "trigger"), facts))
                        self.apply(response, facts)
                        self.assertEqual(facts[("NAM", "equipment", "infantry_equipment")], stolen)
                        self.assertEqual(facts[("NAM", "numeric", "command_power")], 0)
                        self.apply(response, facts)
                        self.assertEqual(facts[("NAM", "equipment", "infantry_equipment")], stolen)
                else:
                    damage = bind(block(block(block(event, "immediate"), "hidden_effect"),
                                        "random_owned_controlled_state"))
                    # The immediate stores the strike tier's base damage on NAM first.
                    for condition, guarded, base in product((5, 80), (False, True), (15, 30)):
                        facts = current_case()
                        facts[("NAM", "variable", "NAM_ug_strike_damage")] = base
                        facts[("67", "variable", "NAM_field_condition")] = condition
                        facts[("67", "has_variable", "NAM_field_condition")] = True
                        facts[("NAM", "has_decision", "NAM_mil_field_security")] = guarded
                        self.apply(damage, facts, "67")
                        loss = min(condition, base / 2 if guarded else base)
                        self.assertEqual(facts[("67", "variable", "NAM_ug_damage_receipt")], loss)
                        self.assertEqual(facts[("67", "variable", "NAM_field_condition")], condition - loss)
                        self.assertTrue(self.matches(block(response, "trigger"), facts))
                        self.apply(response, facts)
                        self.assertEqual(facts[("67", "variable", "NAM_field_condition")], condition)
                    for cause in ("occupation", "lost", "scorched", "short_cp"):
                        facts = current_case()
                        facts[("67", "variable", "NAM_ug_damage_receipt")] = 5
                        facts[("67", "variable", "NAM_field_condition")] = 20
                        if cause in ("occupation", "lost"):
                            facts[("67", "is_controlled_by" if cause == "occupation" else "is_owned_by", "NAM")] = False
                        elif cause == "scorched":
                            facts[("67", "has_state_flag", "NAM_wells_scorched")] = True
                        else:
                            facts[("NAM", "numeric", "command_power")] = 14.99
                        self.assertFalse(self.matches(block(response, "trigger"), facts), cause)
                        before = facts[("NAM", "numeric", "command_power")]
                        self.apply(response, facts)
                        self.assertEqual(facts[("NAM", "numeric", "command_power")], before)
                        self.assertEqual(facts[("67", "variable", "NAM_field_condition")], 20)
                    ordinary_repair = bind(next(e.value for e in event if e.key == "option"
                                               and scalar(e.value, "name") == f"{BASE}.85.a"))
                    for cause in ("ready", "occupation", "lost", "scorched", "short_treasury"):
                        facts = current_case()
                        treasury = ("NAM", "variable", "ADISCORD_economy_treasury")
                        facts[treasury] = 99.99 if cause == "short_treasury" else 100
                        facts[("67", "variable", "NAM_ug_damage_receipt")] = 15
                        facts[("67", "variable", "NAM_field_condition")] = 20
                        facts[("67", "has_variable", "NAM_field_condition")] = True
                        if cause in ("occupation", "lost"):
                            facts[("67", "is_controlled_by" if cause == "occupation" else "is_owned_by", "NAM")] = False
                        elif cause == "scorched":
                            facts[("67", "has_state_flag", "NAM_wells_scorched")] = True
                        self.assertEqual(self.matches(block(ordinary_repair, "trigger"), facts), cause == "ready")
                        before = facts[treasury]
                        self.apply(ordinary_repair, facts)
                        self.assertEqual(facts[treasury], before - (100 if cause == "ready" else 0))
                        self.assertEqual(facts[("67", "variable", "NAM_field_condition")], 30 if cause == "ready" else 20)

    def island_facts(self):
        facts = self.economy_facts()
        for state in map(str, range(225, 232)):
            facts[(state, "state", state)] = True
            facts[(state, "is_owned_by", "NAM")] = True
            facts[(state, "is_controlled_by", "NAM")] = True
            facts[(state, "numeric", "infrastructure")] = 2
            facts[(state, "has_resistance", "yes")] = False
        facts[("fixture", "previous_state")] = "230"
        return facts

    def island_decisions(self):
        return {e.key: e.value for e in block(parsed(f"common/decisions/{BASE}_decisions.txt"), "NAM_national_programmes")
                if e.key.startswith("NAM_island_") or e.key == "NAM_renegotiate_val_concession"}

    def test_island_reorganisation_opens_usable_programmes_from_their_focuses(self):
        overseas = self.island_decisions()
        category = block(parsed(f"common/decisions/categories/{BASE}_categories.txt"), "NAM_national_programmes")
        for focus, programme in (("NAM_harbour_service", "NAM_island_convoy_service"),
                                 ("NAM_island_accounts", "NAM_island_public_works")):
            facts = self.island_facts()
            for name in self.focuses:
                facts[("NAM", "has_completed_focus", name)] = name in (focus, "NAM_harbour_service", "NAM_inventory")
            body = overseas[programme]
            self.assertIn(programme, [e.value for e in walk(block(self.focuses[focus], "completion_reward"))
                                      if e.key == "unlock_decision_tooltip"])
            self.assertTrue(self.matches(block(category, "visible"), facts))
            self.assertTrue(self.matches(block(body, "visible"), facts))
            self.assertTrue(self.matches(block(self.bind_field(body, "230"), "available"), facts))
        for removed in ("NAM_island_convoys", "NAM_island_governors"):
            self.assertNotIn(removed, self.focuses)
        for name in ("NAM_island_steel_levy", "NAM_island_convoy_service", "NAM_island_concession_231", "NAM_island_public_works"):
            for language in ("russian", "english"):
                text = read(f"localisation/{language}/{BASE}_l_{language}.yml")
                desc = next(line for line in text.splitlines() if line.startswith(" " + name + "_desc:"))
                self.assertNotIn("§", desc)
                self.assertNotIn("£", desc)
        self.assertEqual(scalar(block(self.focuses["NAM_island_accounts"], "prerequisite"), "focus"), "NAM_harbour_service")

    def test_island_works_pay_once_share_slots_and_recheck_delivery(self):
        project = self.bind_field(self.island_decisions()["NAM_island_public_works"], "230")
        for failure in (None, "lost", "occupied", "subject", "capitulated", "built_to_cap", "cancel"):
            facts = self.island_facts()
            facts[("NAM", "variable", "NAM_project_slots")] = 1
            self.apply(block(project, "complete_effect"), facts)
            self.assertEqual(facts[("NAM", "numeric", "has_political_power")], 970)
            self.assertEqual(facts[("NAM", "variable", "ADISCORD_economy_treasury")], 9750)
            self.assertEqual(facts[("NAM", "variable", "NAM_projects_in_progress")], 1)
            paid = dict(facts)
            self.apply(block(project, "complete_effect"), facts)
            self.assertEqual(facts, paid)
            mainland = self.bind_field(self.decisions["NAM_econ_deep_drilling"], "67")
            self.assertFalse(self.matches(block(mainland, "available"), facts))
            self.apply(block(mainland, "complete_effect"), facts)
            self.assertEqual(facts, paid)
            if failure in ("lost", "occupied"):
                facts[("230", "is_owned_by" if failure == "lost" else "is_controlled_by", "NAM")] = False
            elif failure in ("subject", "capitulated"):
                facts[("NAM", "is_subject" if failure == "subject" else "has_capitulated", "no")] = False
            elif failure == "built_to_cap":
                facts[("230", "numeric", "infrastructure")] = 5
            if failure not in (None, "cancel"):
                self.assertTrue(self.matches(block(project, "cancel_trigger"), facts))
            self.apply(block(project, "cancel_effect" if failure == "cancel" else "remove_effect"), facts)
            self.assertEqual(facts[("NAM", "variable", "NAM_projects_in_progress")], 0)
            self.assertEqual(facts.get(("230", "building", "infrastructure"), 0), 0 if failure else 1)
            self.assertNotIn(("230", "numeric", "compliance"), facts)
            self.assertEqual(facts[("NAM", "numeric", "has_political_power")], 1000 if failure else 970)
            self.assertEqual(facts[("NAM", "variable", "ADISCORD_economy_treasury")], 10000 if failure else 9750)
            settled = dict(facts)
            self.apply(block(project, "remove_effect"), facts)
            self.apply(block(project, "cancel_effect"), facts)
            self.assertEqual(facts, settled)
        for pp, treasury, level in ((29.99, 250, 2), (30, 249.99, 2), (30, 250, 5)):
            facts = self.island_facts()
            facts[("NAM", "numeric", "has_political_power")] = pp
            facts[("NAM", "variable", "ADISCORD_economy_treasury")] = treasury
            facts[("230", "numeric", "infrastructure")] = level
            before = dict(facts)
            self.apply(block(project, "complete_effect"), facts)
            self.assertEqual(facts, before)

    def test_shipping_service_and_panel_follow_current_island_control(self):
        service = self.island_decisions()["NAM_island_convoy_service"]
        self.assertEqual(scalar(service, "days_remove"), "180")
        self.assertEqual(scalar(service, "days_re_enable"), "0")
        self.assertIn("ADISCORD_economy_mark_dirty", [e.key for e in self.effects["NAM_island_convoy_close"]])
        dynamic = block(parsed("common/dynamic_modifiers/ADISCORD_dynamic_modifiers_NAM.txt"), "NAM_island_convoy_route")
        displays = parsed(f"common/scripted_localisation/{BASE}_scripted_loc.txt")
        display = next(e.value for e in displays if e.key == "defined_text" and scalar(e.value, "name") == "NAMBasinConvoy")
        active = block(next(e.value for e in display if e.key == "text"), "trigger")
        for cause in ("ready", "lost", "occupied", "subject", "capitulated", "money_short"):
            facts = self.island_facts()
            for state in map(str, range(225, 232)):
                facts[(state, "is_owned_by", "NAM")] = state == "230" and cause != "lost"
                facts[(state, "is_controlled_by", "NAM")] = cause != "occupied"
            if cause in ("subject", "capitulated"):
                facts[("NAM", "is_subject" if cause == "subject" else "has_capitulated", "no")] = False
            facts[("NAM", "numeric", "has_political_power")] = 25
            facts[("NAM", "variable", "ADISCORD_economy_treasury")] = 149.99 if cause == "money_short" else 150
            before = dict(facts)
            self.apply(block(service, "complete_effect"), facts)
            if cause == "ready":
                self.assertEqual(facts[("NAM", "numeric", "has_political_power")], 0)
                self.assertEqual(facts[("NAM", "variable", "ADISCORD_economy_treasury")], 0)
                self.assertEqual(facts[("NAM", "equipment", "convoy")], 8)
                self.assertTrue(self.matches(active, facts))
                self.assertEqual([state for state in map(str, range(225, 232))
                                  if facts.get((state, "has_dynamic_modifier", "NAM_island_convoy_route"))], ["230"])
                for exit_name in ("remove_effect", "cancel_effect"):
                    closed = dict(facts)
                    if exit_name == "cancel_effect":
                        closed[("NAM", "is_subject", "no")] = False
                        self.assertTrue(self.matches(block(service, "cancel_trigger"), closed))
                    self.apply(block(service, exit_name), closed)
                    self.assertFalse(closed[("230", "has_dynamic_modifier", "NAM_island_convoy_route")])
                    self.assertFalse(self.matches(active, closed))
                    self.assertEqual(closed[("NAM", "equipment", "convoy")], 8)
                    self.assertEqual(closed[("NAM", "variable", "ADISCORD_economy_treasury")], 0)
                    self.assertEqual(closed[("NAM", "numeric", "has_political_power")], 0)
                    settled = dict(closed)
                    self.apply(block(service, exit_name), closed)
                    self.assertEqual(closed, settled)
            else:
                self.assertEqual(facts, before)
            # A stale modifier is hidden/disabled immediately, before native removal.
            facts[("230", "has_dynamic_modifier", "NAM_island_convoy_route")] = True
            expected = cause in ("ready", "money_short")
            self.assertEqual(self.matches(active, facts), expected)
            self.assertEqual(matches_conditions(self.expand(block(dynamic, "enable")), facts, "230"), expected)
            self.assertEqual(matches_conditions(self.expand(block(dynamic, "remove_trigger")), facts, "230"), not expected)
        levy = self.island_decisions()["NAM_island_steel_levy"]
        facts = self.island_facts()
        facts[("NAM", "has_country_flag", "NAM_island_levy_active")] = True
        for state in ("228", "230", "231"):
            facts[(state, "is_owned_by", "NAM")] = False
        self.assertFalse(self.matches(block(levy, "available"), facts))
        self.assertTrue(self.matches(block(levy, "cancel_trigger"), facts))
        before = dict(facts)
        self.apply(self.effects["NAM_island_levy_monthly"], facts)
        self.assertEqual(facts, before)

    def test_island_levy_exchanges_current_local_extraction_for_treasury(self):
        levy = self.island_decisions()["NAM_island_steel_levy"]
        dynamic = block(parsed("common/dynamic_modifiers/ADISCORD_dynamic_modifiers_NAM.txt"), "NAM_island_steel_levy_modifier")
        self.assertEqual(float(scalar(dynamic, "state_resources_factor")), -0.15)
        for cause in ("expiry", "subject", "capitulated", "lost_all"):
            facts = self.island_facts()
            treasury = ("NAM", "variable", "ADISCORD_economy_treasury")
            facts[("NAM", "numeric", "has_political_power")] -= 20
            self.apply(block(levy, "complete_effect"), facts)
            for state in ("228", "230", "231"):
                self.assertTrue(facts[(state, "has_dynamic_modifier", "NAM_island_steel_levy_modifier")])
                self.assertTrue(matches_conditions(self.expand(block(dynamic, "enable")), facts, state))
            self.apply(self.effects["NAM_island_levy_monthly"], facts)
            self.assertEqual(facts[treasury], 10090)
            facts[("230", "is_controlled_by", "NAM")] = False
            self.assertFalse(matches_conditions(self.expand(block(dynamic, "enable")), facts, "230"))
            self.assertFalse(matches_conditions(self.expand(block(dynamic, "remove_trigger")), facts, "230"))
            self.apply(self.effects["NAM_island_levy_monthly"], facts)
            self.assertEqual(facts[treasury], 10150)
            facts[("230", "is_controlled_by", "NAM")] = True
            self.assertTrue(matches_conditions(self.expand(block(dynamic, "enable")), facts, "230"))
            self.apply(self.effects["NAM_island_levy_monthly"], facts)
            self.assertEqual(facts[treasury], 10240)
            if cause in ("subject", "capitulated"):
                facts[("NAM", "is_subject" if cause == "subject" else "has_capitulated", "no")] = False
            elif cause == "lost_all":
                for state in ("228", "230", "231"):
                    facts[(state, "is_owned_by", "NAM")] = False
            if cause != "expiry":
                self.assertTrue(self.matches(block(levy, "cancel_trigger"), facts))
                self.apply(self.effects["NAM_island_levy_monthly"], facts)
                self.assertEqual(facts[treasury], 10240)
            ending = "remove_effect" if cause == "expiry" else "cancel_effect"
            self.apply(block(levy, ending), facts)
            for state in ("228", "230", "231"):
                self.assertFalse(facts[(state, "has_dynamic_modifier", "NAM_island_steel_levy_modifier")])
                self.assertFalse(matches_conditions(self.expand(block(dynamic, "enable")), facts, state))
                self.assertTrue(matches_conditions(self.expand(block(dynamic, "remove_trigger")), facts, state))
            self.assertEqual(facts[("NAM", "numeric", "has_political_power")], 980)
            settled = dict(facts)
            self.apply(block(levy, ending), facts)
            self.apply(self.effects["NAM_island_levy_monthly"], facts)
            self.assertEqual(facts, settled)

    def test_newly_acquired_steel_island_pays_only_with_its_extraction_cost(self):
        levy = self.island_decisions()["NAM_island_steel_levy"]
        facts = self.island_facts()
        facts[("231", "is_owned_by", "NAM")] = False
        self.apply(block(levy, "complete_effect"), facts)
        self.assertFalse(facts.get(("231", "has_dynamic_modifier", "NAM_island_steel_levy_modifier"), False))
        self.apply(self.effects["NAM_island_levy_monthly"], facts)
        self.assertEqual(facts[("NAM", "variable", "ADISCORD_economy_treasury")], 10060)
        facts[("231", "is_owned_by", "NAM")] = True
        self.apply(self.effects["NAM_island_levy_monthly"], facts)
        self.assertTrue(facts[("231", "has_dynamic_modifier", "NAM_island_steel_levy_modifier")])
        self.assertEqual(facts[("NAM", "variable", "ADISCORD_economy_treasury")], 10150)

    def test_island_programmes_do_not_promise_occupation_rewards_without_resistance(self):
        dynamic = block(parsed("common/dynamic_modifiers/ADISCORD_dynamic_modifiers_NAM.txt"), "NAM_island_convoy_route")
        self.assertEqual(scalar(dynamic, "state_resources_factor"), "0.15")
        self.assertNotIn("compliance_growth", {entry.key for entry in dynamic})
        reward = block(self.focuses["NAM_island_accounts"], "completion_reward")
        self.assertEqual({e.value for e in reward if e.key == "unlock_decision_tooltip"}, {"NAM_island_public_works", "NAM_project_steel"})
        self.assertNotIn("add_to_variable", {entry.key for entry in walk(reward)})
        keys = ("NAM_island_steel_levy_tt", "NAM_island_steel_levy_unlock_tt",
                "NAM_island_convoy_service_tt", "NAM_island_convoy_service_unlock_tt",
                "NAM_island_public_works_unlock_tt", "NAM_island_public_works_result_tt",
                "NAM_island_public_works_delivered_tt")
        for language in ("russian", "english"):
            lines = read(f"localisation/{language}/{BASE}_l_{language}.yml").splitlines()
            for key in keys:
                line = next(line for line in lines if line.startswith(" " + key + ":"))
                self.assertNotRegex(line, "покорност|compliance", key)

    def test_island_accounts_skips_finished_roads_without_skipping_lost_islands(self):
        bypass = block(self.focuses["NAM_island_accounts"], "bypass")
        facts = self.island_facts()
        self.assertFalse(self.matches(bypass, facts))
        for state in map(str, range(225, 232)):
            facts[(state, "numeric", "infrastructure")] = 5
        self.assertTrue(self.matches(bypass, facts))
        facts[("230", "numeric", "infrastructure")] = 2
        facts[("230", "is_owned_by", "NAM")] = False
        self.assertTrue(self.matches(bypass, facts))
        facts[("230", "is_owned_by", "NAM")] = True
        self.assertFalse(self.matches(bypass, facts))
        for state in map(str, range(225, 232)):
            facts[(state, "is_owned_by", "NAM")] = False
        self.assertFalse(self.matches(bypass, facts))

    def test_fuel_refusal_blocks_repeat_offers_without_blocking_other_buyers(self):
        for buyer in ("VAL", "GLP"):
            facts = self.facts()
            facts[(buyer, "exists", "yes")] = True
            facts[(buyer, "has_capitulated", "no")] = True
            self.apply(self.effects["NAM_oil_offer_contract"], facts, buyer)
            self.assertTrue(facts[(buyer, "has_country_flag", "NAM_oil_offer_pending")])
            event = self.events["ADISCORD_nam_oil.1"]
            first_option = next(row.value for row in event if row.key == "option")
            self.apply(block(first_option, "hidden_effect"), facts, buyer)
            self.assertTrue(facts[(buyer, "has_country_flag", "NAM_oil_offer_declined")])
            self.assertFalse(facts[(buyer, "has_country_flag", "NAM_oil_offer_pending")])
            after = dict(facts)
            for effect in ("NAM_oil_offer_contract", "NAM_oil_decline_contract", "NAM_oil_sign_contract"):
                self.apply(self.effects[effect], facts, buyer)
                self.assertEqual(facts, after, effect)
                selected = selected_effects(self.expand(self.effects[effect]), facts, buyer)
                self.assertFalse(any(e.key == "country_event" for _, e in selected))
            self.assertFalse(matches_conditions(self.expand(block(event, "trigger")), facts, buyer))
            other = "GLP" if buyer == "VAL" else "VAL"
            facts[(other, "exists", "yes")] = True
            facts[(other, "has_capitulated", "no")] = True
            self.apply(self.effects["NAM_oil_offer_contract"], facts, other)
            self.assertTrue(facts[(other, "has_country_flag", "NAM_oil_offer_pending")])

    def test_island_refusal_remembers_the_buyer_and_preserves_other_offer(self):
        offer = self.island_decisions()["NAM_island_concession_231"]
        facts = self.island_facts()
        for tag in ("VAL", "GLP"):
            facts[(tag, "exists", "yes")] = True
            facts[(tag, "has_capitulated", "no")] = True
        self.apply(block(self.bind_field(offer, "VAL"), "complete_effect"), facts)
        self.apply(self.effects["NAM_steel_concession_decline"], facts, "VAL")
        self.assertTrue(facts[("VAL", "has_country_flag", "NAM_steel_concession_declined")])
        self.assertFalse(self.matches(block(self.bind_field(offer, "VAL"), "visible"), facts))
        self.assertFalse(self.matches(block(self.bind_field(offer, "VAL"), "available"), facts))
        self.assertTrue(self.matches(block(self.bind_field(offer, "GLP"), "available"), facts))
        self.apply(block(self.bind_field(offer, "GLP"), "complete_effect"), facts)
        after = dict(facts)
        self.apply(self.effects["NAM_steel_concession_decline"], facts, "VAL")
        self.assertEqual(facts, after)

    def test_island_concession_rechecks_buyer_payment_and_current_offer(self):
        offer = self.island_decisions()["NAM_island_concession_231"]
        for buyer, value in (("VAL", 1), ("GLP", 2)):
            for cause in ("ready", "lost", "occupied", "war", "money_short", "subject", "expired", "another_buyer"):
                facts = self.island_facts()
                facts[(buyer, "exists", "yes")] = True
                facts[(buyer, "has_capitulated", "no")] = True
                facts[(buyer, "variable", "ADISCORD_economy_treasury")] = 300
                # Native decision payment precedes the complete effect.
                facts[("NAM", "numeric", "has_political_power")] -= 20
                self.apply(block(self.bind_field(offer, buyer), "complete_effect"), facts)
                self.assertTrue(facts[("NAM", "has_country_flag", "NAM_concession_231_pending")])
                self.assertEqual(facts[("NAM", "variable", "fixture_flag_value@NAM_concession_231_pending")], value)
                if cause in ("lost", "occupied"):
                    facts[("231", "is_owned_by" if cause == "lost" else "is_controlled_by", "NAM")] = False
                elif cause == "war":
                    facts[(buyer, "has_war_with", "NAM")] = True
                elif cause == "money_short":
                    facts[(buyer, "variable", "ADISCORD_economy_treasury")] = 299.99
                elif cause == "subject":
                    facts[("NAM", "is_subject", "no")] = False
                elif cause == "expired":
                    facts[("NAM", "has_country_flag", "NAM_concession_231_pending")] = False
                elif cause == "another_buyer":
                    facts[("NAM", "variable", "fixture_flag_value@NAM_concession_231_pending")] = 3 - value
                before = dict(facts)
                self.apply(self.effects["NAM_steel_concession_grant"], facts, buyer)
                if cause == "ready":
                    self.assertEqual(facts[(buyer, "variable", "ADISCORD_economy_treasury")], 0)
                    self.assertEqual(facts[("NAM", "variable", "ADISCORD_economy_treasury")], 10300)
                    self.assertEqual(facts[("NAM", "resource_rights", "231")], buyer)
                    self.assertFalse(facts[("NAM", "has_country_flag", "NAM_concession_231_pending")])
                    settled = dict(facts)
                    self.apply(self.effects["NAM_steel_concession_grant"], facts, buyer)
                    self.assertEqual(facts, settled)
                else:
                    self.assertEqual(facts, before, (buyer, cause))
                if cause == "another_buyer":
                    self.apply(self.effects["NAM_steel_concession_decline"], facts, buyer)
                    self.assertEqual(facts, before)

    def test_war_operations_share_headquarters_and_close_with_the_war(self):
        names = ("NAM_war_supply_priority", "NAM_war_counterstroke_operation")
        for name, other, cp, fuel in ((names[0], names[1], 25, 1000), (names[1], names[0], 35, 2000)):
            body = self.decisions[name]
            self.assertEqual(scalar(body, "days_remove"), "21")
            for cause in ("ready", "headquarters_busy", "fuel_short", "command_short", "peace", "subjugation"):
                facts = self.independent_facts()
                facts[("NAM", "has_global_flag", BASE + "_started")] = cause != "peace"
                facts[("NAM", "has_war", "no")] = False
                facts[("NAM", "has_decision", other)] = cause == "headquarters_busy"
                facts[("NAM", "numeric", "has_fuel")] = fuel - (0.01 if cause == "fuel_short" else 0)
                facts[("NAM", "numeric", "command_power")] = cp - (0.01 if cause == "command_short" else 0)
                facts[("NAM", "is_subject", "no")] = cause != "subjugation"
                before = dict(facts)
                self.assertEqual(self.matches(block(body, "visible"), facts), cause != "peace")
                self.apply(block(body, "complete_effect"), facts)
                if cause == "ready":
                    self.assertEqual(facts[("NAM", "numeric", "has_fuel")], 0)
                    self.assertEqual(facts[("NAM", "numeric", "command_power")], 0)
                else:
                    self.assertEqual(facts, before)
                    selected = [e for _, e in selected_effects(self.expand(block(body, "complete_effect")), facts, "NAM")]
                    self.assertIn(("remove_decision", name), [(e.key, e.value) for e in selected])
                if cause in ("headquarters_busy", "peace", "subjugation"):
                    self.assertFalse(self.matches(block(body, "available"), before))
                if cause in ("peace", "subjugation"):
                    self.assertTrue(self.matches(block(body, "cancel_trigger"), before))
            self.assertIn(("remove_decision", name), [(e.key, e.value) for e in self.effects["NAM_close_war_programmes"]])

    def run_colonial_saving_route(self):
        route = ("inventory", "centre_hourglass", "second_ledger", "quiet_officer_lists", "sand_runs_out",
                 "last_centre_register", "metropolitan_quota", "concealed_reserve", "wrk_trade_house",
                 "wrk_return_cargo", "metropolitan_depots", "colonial_watch",
                 "oilfield_militia", "pipeline_patrols", "print_shop_raid", "colony_order", "letters_to_the_centre")
        facts = self.colonial_facts()
        for name in self.focuses:
            facts[("NAM", "has_completed_focus", name)] = False
        facts[("NAM", "has_variable", "NAM_hidden_reserve")] = False
        for name in ("has_political_power", "has_fuel", "has_manpower"):
            facts[("NAM", "numeric", name)] = 0
        defaults = block(parsed("common/scripted_effects/ADISCORD_economy_effects.txt"), "ADISCORD_economy_set_default_values")
        treasury = next(e.value for e in defaults if e.key == "set_variable" and scalar(e.value, "var") == "ADISCORD_economy_treasury")
        facts[("NAM", "variable", "ADISCORD_economy_treasury")] = float(scalar(treasury, "value"))
        projects = block(parsed(f"common/decisions/{BASE}_decisions.txt"), "NAM_colony")
        fuel_order = block(projects, "NAM_colonial_fuel_reserve")
        cash_order = block(projects, "NAM_colonial_reserve_fund")
        shipment = block(projects, "NAM_wrk_fuel_shipment")
        accounting = {name: body for name, body in self.effects.items() if name in (
            "NAM_add_treasury", "NAM_wrk_trade_refresh", "NAM_colony_monthly", "NAM_colony_hourglass_payout",
            "NAM_metropolitan_flight", "NAM_hidden_fuel_release")}
        accounting["ADISCORD_vorkerland_release_evacuated_fuel"] = block(parsed("common/scripted_effects/ADISCORD_vorkerland_effects.txt"), "ADISCORD_vorkerland_release_evacuated_fuel")
        facts[("WKR", "exists", "yes")] = True
        day = 0
        completions = {}
        for name in route:
            name = "NAM_" + name
            day += int(scalar(self.focuses[name], "cost")) * 7
            completions[day] = name
        self.assertEqual(day, 329)
        startup = parsed("common/on_actions/01_ADISCORD_vorkerland_collapse_on_actions.txt")
        collapse = next(e.value for e in walk(startup) if e.key == "country_event"
                        and scalar(e.value, "id") == "ADISCORD_vorkerland_phase.1")
        self.assertLess(day, int(scalar(collapse, "days")))
        for name in self.COLONIAL_CASH_ORDERS:
            order = block(projects, name)
            unlock = scalar(block(order, "visible"), "has_completed_focus")
            unlock_day = next(day for day, focus in completions.items() if focus == unlock)
            self.assertLess(unlock_day + int(scalar(order, "days_remove")), int(scalar(collapse, "days")), name)
        paid_day = next(day for day, name in completions.items() if name == "NAM_concealed_reserve")
        fuel_due = paid_day + int(scalar(fuel_order, "days_remove"))
        first_shipment = next(day for day, name in completions.items() if name == "NAM_wrk_trade_house")
        shipment_days = (first_shipment, first_shipment + int(scalar(shipment, "days_re_enable")))
        cash_days = (shipment_days[0] + 1, shipment_days[1] + 1)
        cash_due = tuple(day + int(scalar(cash_order, "days_remove")) for day in cash_days)
        with patch.object(self, "effects", accounting):
            for day in range(1, 351):
                facts[("NAM", "numeric", "has_political_power")] += 0.25
                # Conservative net refinery output with the starting harbour tanks.
                fuel_key = ("NAM", "numeric", "has_fuel")
                facts[fuel_key] = min(200000, facts[fuel_key] + 1000)
                if day in completions:
                    name = completions[day]
                    focus = self.focuses[name]
                    for requirement in (e.value for e in focus if e.key == "prerequisite"):
                        self.assertTrue(any(facts.get(("NAM", "has_completed_focus", e.value)) for e in requirement), name)
                    self.assertTrue(self.matches(block(focus, "available"), facts), name)
                    self.apply(block(focus, "completion_reward"), facts)
                    facts[("NAM", "has_completed_focus", name)] = True
                if day == paid_day:
                    self.assertTrue(self.matches(block(fuel_order, "visible"), facts))
                    self.assertTrue(self.matches(block(fuel_order, "available"), facts))
                    self.assertTrue(self.matches(block(fuel_order, "custom_cost_trigger"), facts))
                    facts[("NAM", "numeric", "has_political_power")] -= int(scalar(fuel_order, "cost"))
                    self.apply(block(fuel_order, "complete_effect"), facts)
                if day == fuel_due:
                    self.apply(block(fuel_order, "remove_effect"), facts)
                if day in shipment_days:
                    for key in ("visible", "available", "custom_cost_trigger"):
                        self.assertTrue(self.matches(block(shipment, key), facts), (day, key))
                    self.apply(block(shipment, "complete_effect"), facts)
                if day in cash_days:
                    for key in ("visible", "available", "custom_cost_trigger"):
                        self.assertTrue(self.matches(block(cash_order, key), facts), (day, key))
                    self.apply(block(cash_order, "complete_effect"), facts)
                if day in cash_due:
                    self.apply(block(cash_order, "remove_effect"), facts)
                # At most 31 days per monthly pulse is a conservative calendar.
                if day % 31 == 0:
                    self.apply(self.effects["NAM_colony_monthly"], facts)
                self.assertGreaterEqual(facts[("NAM", "numeric", "has_political_power")], 0)
                self.assertGreaterEqual(facts[("NAM", "numeric", "has_fuel")], 0)
            self.apply(self.effects["NAM_metropolitan_flight"], facts)
        return facts

    def test_metropolitan_flight_conserves_shelters_and_seizes_unfinished_receipts_once(self):
        cases = ("no_shelter", "prepared", "pending", "debt", "small_depot")
        for case in cases:
            with self.subTest(case=case):
                facts = self.colonial_facts()
                treasury = ("NAM", "variable", "ADISCORD_economy_treasury")
                fuel = ("NAM", "numeric", "has_fuel")
                facts[treasury] = -50 if case == "debt" else 1000
                facts[fuel] = 80000
                facts[("WKR", "exists", "yes")] = True
                facts[("WKR", "variable", "ADISCORD_economy_treasury")] = 200
                facts[("WKR", "numeric", "has_fuel")] = 90000
                facts[("WKR", "fuel_capacity")] = 100000
                facts[("NAM", "variable", "NAM_hidden_reserve")] = 300 if case != "no_shelter" else 0
                facts[("NAM", "variable", "NAM_hidden_fuel")] = 60000 if case != "no_shelter" else 0
                facts[("NAM", "fuel_capacity")] = 30000 if case == "small_depot" else 200000
                if case == "pending":
                    for receipt in ("NAM_colonial_reserve_fund_paid", "NAM_colonial_fuel_reserve_paid", "NAM_colonial_artillery_contract_paid"):
                        facts[("NAM", "has_country_flag", receipt)] = True
                    facts[("NAM", "variable", "NAM_wrk_echelon_deposit")] = 90000
                    facts[("NAM", "variable", "NAM_wrk_concession_deposit")] = 200
                    facts[("67", "has_state_flag", "NAM_sweep_in_progress")] = True
                    facts[("67", "variable", "NAM_sweep_deposit")] = 75
                    facts[("fixture", "previous_state")] = "67"
                effects = {name: body for name, body in self.effects.items() if name in (
                    "NAM_metropolitan_flight", "NAM_colony_hourglass_payout", "NAM_hidden_fuel_release",
                    "NAM_colonial_artillery_contract_refund", "NAM_colonial_local_register_refund",
                    "NAM_colonial_emergency_stocks_refund", "NAM_colonial_reserve_fund_refund",
                    "NAM_wrk_concession_refund", "NAM_sweep_release", "NAM_add_treasury")}
                effects["ADISCORD_vorkerland_release_evacuated_fuel"] = block(parsed("common/scripted_effects/ADISCORD_vorkerland_effects.txt"), "ADISCORD_vorkerland_release_evacuated_fuel")
                with patch.object(self, "effects", effects):
                    self.apply(effects["NAM_metropolitan_flight"], facts)
                    taken_cash = 1975 if case == "pending" else 0 if case == "debt" else 1000
                    taken_fuel = 210000 if case == "pending" else 80000
                    self.assertEqual(facts[("NAM", "variable", "NAM_evacuated_treasury")], taken_cash)
                    self.assertEqual(facts[("NAM", "variable", "NAM_evacuated_fuel")], taken_fuel)
                    self.assertEqual(facts[("WKR", "variable", "ADISCORD_economy_treasury")], 200 + taken_cash)
                    self.assertEqual(facts[("WKR", "numeric", "has_fuel")], 100000)
                    self.assertEqual(facts[("WKR", "variable", "WKR_evacuated_fuel_reserve")], taken_fuel - 10000)
                    self.assertEqual(facts[treasury], 0 if case == "no_shelter" else 250 if case == "debt" else 300)
                    self.assertEqual(facts[fuel] + facts[("NAM", "variable", "NAM_hidden_fuel")], 0 if case == "no_shelter" else 60000)
                    if case == "small_depot":
                        self.assertEqual(facts[fuel], 30000)
                        facts[fuel] = 10000
                        self.apply(effects["NAM_hidden_fuel_release"], facts)
                        self.assertEqual(facts[fuel], 30000)
                        self.assertEqual(facts[("NAM", "variable", "NAM_hidden_fuel")], 10000)
                    settled = dict(facts)
                    self.apply(effects["NAM_metropolitan_flight"], facts)
                    self.apply(effects["NAM_colony_hourglass_payout"], facts)
                    self.apply(effects["NAM_colonial_reserve_fund_refund"], facts)
                    self.apply(effects["NAM_colonial_artillery_contract_refund"], facts)
                    self.assertEqual(facts, settled)
        notice = self.events["ADISCORD_nam_resource_war.88"]
        self.assertNotIn("immediate", [e.key for e in notice])
        self.assertEqual({e.key for e in block(notice, "option")}, {"name", "custom_effect_tooltip"})
        teardown = block(parsed("common/scripted_effects/ADISCORD_vorkerland_effects.txt"), "ADISCORD_vorkerland_teardown_confederation")
        self.assertEqual(scalar(block(teardown, "NAM"), "NAM_metropolitan_flight"), "yes")

    def test_cancelled_fuel_shelter_keeps_overflow_open_and_cannot_refund_twice(self):
        decision = self.colonial_projects()["NAM_colonial_fuel_reserve"]
        facts = self.colonial_facts()
        fuel = ("NAM", "numeric", "has_fuel")
        facts[fuel] = 39999.99
        self.assertFalse(self.matches(block(decision, "custom_cost_trigger"), facts))
        before = dict(facts)
        self.apply(block(decision, "complete_effect"), facts)
        self.assertEqual(facts, before)
        facts[fuel] = 40000
        self.assertTrue(self.matches(block(decision, "custom_cost_trigger"), facts))
        self.apply(block(decision, "complete_effect"), facts)
        self.assertEqual(facts[fuel], 0)
        facts[fuel] = 190000
        self.apply(block(decision, "cancel_effect"), facts)
        self.assertEqual(facts[fuel], 200000)
        self.assertEqual(facts[("NAM", "variable", "NAM_open_fuel_reserve")], 30000)
        self.assertEqual(facts[("NAM", "variable", "NAM_hidden_fuel")], 0)
        before = dict(facts)
        self.apply(block(decision, "cancel_effect"), facts)
        self.apply(block(decision, "remove_effect"), facts)
        self.assertEqual(facts, before)

    def test_colonial_saving_route_funds_the_preparation_reserve(self):
        facts = self.run_colonial_saving_route()
        self.assertEqual(facts[("NAM", "numeric", "has_political_power")], 257.5)
        self.assertEqual(facts[("NAM", "variable", "ADISCORD_economy_treasury")], 1200)
        self.assertEqual(facts[("NAM", "numeric", "has_fuel")], 60000)

    def test_low_reserve_routes_prioritise_preparation_over_capital_projects(self):
        for administration, economy, army in product(("vertical", "districts"), ("export_quays", "domestic_refining"), ("field_guards", "mobile_columns")):
            with self.subTest(administration=administration, economy=economy, army=army):
                self.run_preparation_budget(administration, economy, army, lean=True)

    def test_prewar_depot_survives_waiting_for_the_attack(self):
        body = self.decisions["NAM_mil_forward_supply"]
        installation = [e.value for e in walk(block(body, "remove_effect")) if e.key == "add_dynamic_modifier"]
        self.assertEqual(len(installation), 1)
        self.assertEqual(scalar(installation[0], "modifier"), "NAM_mil_forward_depot")
        self.assertNotIn("days", [e.key for e in installation[0]])
        dynamic = block(parsed("common/dynamic_modifiers/ADISCORD_dynamic_modifiers_NAM.txt"), "NAM_mil_forward_depot")
        for war in (False, True):
            facts = self.economy_facts()
            facts[("NAM", "has_global_flag", BASE + "_started")] = war
            facts[("NAM", "has_global_flag", BASE + "_scheduled")] = not war
            self.assertTrue(matches_conditions(self.expand(block(dynamic, "enable")), facts, "67"))
            facts[("NAM", "has_global_flag", BASE + "_resolved")] = True
            facts[("NAM", "has_global_flag", BASE + "_scheduled")] = False
            self.assertFalse(matches_conditions(self.expand(block(dynamic, "enable")), facts, "67"))

    def test_ai_prepares_the_compact_refinery_and_lines_before_other_programmes(self):
        plan = block(parsed("common/ai_strategy_plans/ADISCORD_NAM_plans.txt"), "NAM_prewar_plan")
        queue = [e.value for e in block(plan, "ai_national_focuses")]
        start = queue.index("NAM_independence_day")
        route = self.preparation_route("districts", "domestic_refining", "field_guards")
        self.assertLess(queue.index("NAM_letters_to_the_centre"), start)
        self.assertEqual(queue[start:start + len(route) - 1], route[1:])
        self.assertFalse(set(queue) & set(self.wartime))
        days, deliveries = self.run_preparation_budget("districts", "domestic_refining", "field_guards")
        self.assertLessEqual(deliveries["NAM_sign_compact"] + 60, 301)
        self.assertLess(deliveries["NAM_econ_petrochemical_batch"], 700)
        self.assertLess(deliveries["NAM_mil_forward_supply"], 700)

    def test_azhar_focus_and_ultimatum_share_one_paid_delay(self):
        body = self.focuses["NAM_court_azhar"]
        for first_strike, receiver in ((True, True), (False, False)):
            facts = self.independent_facts()
            facts[("AZH", "exists", "yes")] = receiver
            facts[("NAM", "has_country_flag", "NAM_rw_first_strike")] = first_strike
            self.assertFalse(self.matches(block(body, "available"), facts))
            before = dict(facts)
            self.apply(block(body, "completion_reward"), facts)
            self.assertEqual(facts, before)
        for fuel, allowed in ((59999.99, False), (60000, True)):
            facts = self.independent_facts()
            facts[("AZH", "exists", "yes")] = True
            facts[("AZH", "has_capitulated", "no")] = True
            facts[("NAM", "numeric", "has_fuel")] = fuel
            self.assertEqual(self.matches(block(body, "available"), facts), allowed)
            with patch.object(self, "effects", {}):
                self.apply(block(body, "completion_reward"), facts)
                self.assertEqual(facts[("NAM", "numeric", "has_fuel")], fuel - (60000 if allowed else 0))
                self.assertEqual(facts.get(("AZH", "numeric", "has_fuel"), 0), 60000 if allowed else 0)
                paid = dict(facts)
                self.apply(block(body, "completion_reward"), facts)
                self.assertEqual(facts, paid)
            if allowed:
                self.assertTrue(self.matches(block(body, "bypass"), facts))
                self.apply(self.effects["NAM_rw_buy_time"], facts)
                self.assertEqual(facts, paid)

    def test_diplomatic_decisions_have_distinct_focus_gates_and_no_event_unlock(self):
        category = block(parsed(f"common/decisions/{BASE}_decisions.txt"), "NAM_restitution")
        note = block(category, "NAM_restitution_note")
        dossier = block(category, "NAM_ind_border_dossier")
        for focus, decision in (("NAM_neutral_basin", "NAM_ind_border_dossier"),
                                ("NAM_restitution_desk", "NAM_restitution_note")):
            reward = block(self.focuses[focus], "completion_reward")
            unlocks = [e.value for e in walk(reward) if e.key == "unlock_decision_tooltip"]
            self.assertEqual(unlocks, [decision])
        event = self.events[BASE + ".20"]
        self.assertFalse(any(e.key == "unlock_decision_tooltip" for e in walk(event)))
        answer = next(e.value for e in event
                      if e.key == "option" and scalar(e.value, "name") == BASE + ".20.a")
        for neutral, desk, sent in product((False, True), repeat=3):
            with self.subTest(neutral=neutral, desk=desk, sent=sent):
                facts = self.independent_facts()
                facts[("NAM", "has_completed_focus", "NAM_neutral_basin")] = neutral
                facts[("NAM", "has_completed_focus", "NAM_restitution_desk")] = desk
                facts[("NAM", "has_country_flag", "NAM_rw_note_sent")] = sent
                self.assertEqual(self.matches(block(note, "visible"), facts), desk and not sent)
                self.assertEqual(self.matches(block(dossier, "visible"), facts), neutral)
                self.apply(answer, facts)
                self.assertEqual(self.matches(block(note, "visible"), facts), desk and not sent)
                self.assertEqual(self.matches(block(dossier, "visible"), facts), neutral)

    def test_diplomatic_reply_updates_real_group_bonuses_only_during_live_threat(self):
        event = self.events[BASE + ".20"]
        answer = next(e.value for e in event
                      if e.key == "option" and scalar(e.value, "name") == BASE + ".20.a")
        preview = block(answer, "effect_tooltip")
        self.assertEqual(scalar(event, "fire_only_once"), "yes")
        for state in ("active", "dispatched", "war", "peace", "no_mission"):
            for trade, garrison in ((65, 72), (95, 3)):
                with self.subTest(state=state, trade=trade, garrison=garrison):
                    facts = self.independent_facts()
                    facts[("NAM", "has_country_flag", "NAM_groups_initialized")] = True
                    for group, influence in (("nam", 30), ("oil", 20), ("dist", 20),
                                             ("garr", 20), ("trade", 10)):
                        facts[("NAM", "variable", f"NAM_grp_{group}_support")] = 50
                        facts[("NAM", "variable", f"NAM_grp_{group}_influence")] = influence
                    facts[("NAM", "variable", "NAM_grp_trade_support")] = trade
                    facts[("NAM", "variable", "NAM_grp_garr_support")] = garrison
                    self.apply(self.effects["NAM_groups_refresh"], facts)
                    if state == "dispatched":
                        facts[("NAM", "has_country_flag", "NAM_rw_war_dispatched")] = True
                    elif state == "war":
                        facts[("NAM", "has_global_flag", BASE + "_started")] = True
                    elif state == "peace":
                        facts[("NAM", "has_global_flag", BASE + "_resolved")] = True
                    elif state == "no_mission":
                        facts[("NAM", "has_active_mission", "NAM_resource_war_deadline")] = False
                    before = dict(facts)
                    shown = [e.value for _, e in selected_effects(self.expand(preview), facts, "NAM")
                             if e.key == "custom_effect_tooltip"]
                    self.assertEqual(shown, ["NAM_claims_diplomatic_reply_tt"] if state == "active" else [])
                    self.apply(answer, facts)
                    if state != "active":
                        self.assertEqual(facts, before)
                        continue
                    self.assertEqual(facts[("NAM", "variable", "NAM_grp_trade_support")], min(100, trade + 10))
                    self.assertEqual(facts[("NAM", "variable", "NAM_grp_garr_support")], max(0, garrison - 5))
                    self.assertEqual(facts[("NAM", "variable", "NAM_loy_trade_income")], 0.05)
                    self.assertEqual(facts[("NAM", "variable", "NAM_loy_army_org")], 0 if garrison == 72 else -0.05)
                    for key in (("NAM", "variable", "days_mission_timeout@NAM_resource_war_deadline"),
                                ("NAM", "numeric", "has_political_power")):
                        self.assertEqual(facts[key], before[key])
        self.assertTrue(any(e.key == "ADISCORD_economy_mark_dirty"
                            for e in walk(self.effects["NAM_groups_refresh"])))

    def test_restitution_courses_merge_directly_and_keep_distinct_actions(self):
        root = self.focuses["NAM_restitution_desk"]
        final = self.focuses["NAM_general_staff_plan"]
        self.assertEqual(scalar(block(root, "prerequisite"), "focus"), "NAM_independence_day")
        self.assertEqual([e.value for e in block(final, "prerequisite")], ["NAM_court_azhar", "NAM_fuel_leverage"])
        self.assertNotIn("NAM_basin_talks", self.focuses)
        self.assertNotIn("NAM_eflor_fuel_prices", self.focuses)
        for name, alternative in (("NAM_court_azhar", "NAM_fuel_leverage"), ("NAM_fuel_leverage", "NAM_court_azhar")):
            course = self.focuses[name]
            self.assertEqual(scalar(block(course, "prerequisite"), "focus"), "NAM_restitution_desk")
            self.assertEqual(scalar(block(course, "mutually_exclusive"), "focus"), alternative)
            self.assertEqual(sum(int(scalar(f, "cost")) * 7 for f in (root, course, final)), 77)
        facts = self.independent_facts()
        facts[("NAM", "numeric", "has_fuel")] = 60000
        facts[("AZH", "exists", "yes")] = True
        facts[("AZH", "has_capitulated", "no")] = True
        self.apply(block(self.focuses["NAM_court_azhar"], "completion_reward"), facts)
        self.assertEqual(facts[("NAM", "variable", "days_mission_timeout@NAM_resource_war_deadline")], 525)
        pressure = block(self.focuses["NAM_fuel_leverage"], "completion_reward")
        self.assertEqual(scalar(pressure, "unlock_decision_tooltip"), "NAM_fuel_embargo")
        self.assertEqual(scalar(pressure, "add_political_power"), "25")
        self.assertFalse(any(e.key in ("NAM_receive_250", "add_to_variable") for e in walk(pressure)))

    def test_azhar_purchase_rejects_stale_threat_and_receiver_at_both_prices(self):
        reward = block(self.focuses["NAM_court_azhar"], "completion_reward")
        emergency = self.effects["NAM_rw_buy_time"]
        for source, price in ((reward, 60000), (emergency, 120000)):
            for key, value in (
                (("NAM", "is_subject", "no"), False),
                (("NAM", "has_global_flag", BASE + "_scheduled"), False),
                (("NAM", "has_global_flag", BASE + "_started"), True),
                (("NAM", "has_global_flag", BASE + "_resolved"), True),
                (("NAM", "has_country_flag", "NAM_rw_war_dispatched"), True),
                (("NAM", "has_country_flag", "NAM_rw_first_strike"), True),
                (("NAM", "has_country_flag", "NAM_rw_time_bought"), True),
                (("EFL", "exists", "yes"), False),
                (("AZH", "exists", "yes"), False),
                (("AZH", "has_capitulated", "no"), False),
                (("AZH", "has_war_with", "NAM"), True),
            ):
                facts = self.independent_facts()
                facts[("AZH", "exists", "yes")] = True
                facts[("AZH", "has_capitulated", "no")] = True
                facts[("NAM", "numeric", "has_fuel")] = price
                facts[key] = value
                before = dict(facts)
                self.apply(source, facts)
                self.assertEqual(facts, before, (price, key))
            for fuel, expected in ((price - 0.01, 0), (price, price)):
                facts = self.independent_facts()
                facts[("AZH", "exists", "yes")] = True
                facts[("AZH", "has_capitulated", "no")] = True
                facts[("NAM", "numeric", "has_fuel")] = fuel
                with patch.object(self, "effects", {}):
                    self.apply(source, facts)
                self.assertEqual(facts[("NAM", "numeric", "has_fuel")], fuel - expected)
                self.assertEqual(facts.get(("AZH", "numeric", "has_fuel"), 0), expected)
                paid = dict(facts)
                self.apply(source, facts)
                self.assertEqual(facts, paid)

    def test_all_capacity_reward_orders_cap_at_six_and_supply_replacements(self):
        names = ("NAM_garrison_assembly", "NAM_reserve_rolls", "NAM_general_staff_plan")
        capacity = self.effects["NAM_expand_mobilisation_capacity"]
        for order in permutations(names):
            facts = self.independent_facts()
            facts[("NAM", "variable", "NAM_order_cap")] = 4
            facts[("NAM", "numeric", "has_manpower")] = 0
            with patch.object(self, "effects", {"NAM_expand_mobilisation_capacity": capacity}):
                for name in order:
                    self.apply(block(self.focuses[name], "completion_reward"), facts)
                    self.assertLessEqual(facts[("NAM", "variable", "NAM_order_cap")], 6)
            self.assertEqual(facts[("NAM", "variable", "NAM_order_cap")], 6)
            self.assertEqual(facts[("NAM", "numeric", "has_manpower")], 5000)
            for paid, allowed in ((5, True), (6, False)):
                facts[("NAM", "variable", "NAM_orders_paid")] = paid
                self.assertEqual(self.matches(self.triggers["NAM_order_can_place"], facts), allowed)
        facts = self.independent_facts()
        facts[("NAM", "has_global_flag", BASE + "_scheduled")] = False
        facts[("NAM", "variable", "NAM_order_cap")] = 4
        with patch.object(self, "effects", {"NAM_expand_mobilisation_capacity": capacity}):
            self.apply(block(self.focuses["NAM_garrison_assembly"], "completion_reward"), facts)
        self.assertEqual(facts[("NAM", "numeric", "command_power")], 20)
        self.assertEqual(facts[("NAM", "variable", "NAM_order_cap")], 4)

    def test_embargo_unlock_is_usable_without_the_oil_branch(self):
        facts = self.independent_facts()
        for focus in self.focuses:
            facts[("NAM", "has_completed_focus", focus)] = False
        completed = reachable(self.focuses, {"NAM_court_azhar"})
        self.assertIn("NAM_fuel_leverage", completed)
        # The mandatory colonial chain opens the national category; the oil
        # branch is not a prerequisite of diplomatic pressure.
        for focus in ("NAM_inventory", "NAM_letters_to_the_centre", "NAM_independence_day",
                      "NAM_restitution_desk", "NAM_fuel_leverage"):
            facts[("NAM", "has_completed_focus", focus)] = True
        category = block(parsed("common/decisions/categories/ADISCORD_nam_resource_war_categories.txt"), "NAM_national_programmes")
        self.assertTrue(self.matches(block(category, "visible"), facts))
        self.assertFalse(facts[("NAM", "has_completed_focus", "NAM_well_register")])
        for target in ("EFL", "AZH", "SHL"):
            facts[(target, "tag", target)] = True
            facts[(target, "exists", "yes")] = True
            decision = self.bind_embargo(self.decisions["NAM_fuel_embargo"], target)
            self.assertTrue(self.matches(block(decision, "visible"), facts), target)
            self.assertTrue(self.matches(block(decision, "available"), facts), target)
            facts[(target, "has_country_flag", "NAM_oil_client")] = True
            self.assertFalse(self.matches(block(decision, "visible"), facts), target)
            self.assertFalse(self.matches(block(decision, "available"), facts), target)
            facts[(target, "has_country_flag", "NAM_oil_client")] = False

    def bind_embargo(self, entries, target):
        return [replace(e, key=target if e.key == "FROM" else e.key,
                        value=self.bind_embargo(e.value, target) if isinstance(e.value, list) else e.value)
                for e in entries]

    def test_embargo_applies_once_and_lifting_cannot_farm_support(self):
        effects = {name: self.effects[name] for name in ("NAM_oil_impose_embargo", "NAM_oil_lift_embargo", "NAM_rw_start_tribute")}
        for target in ("EFL", "AZH", "SHL"):
            impose = self.bind_embargo(self.decisions["NAM_fuel_embargo"], target)
            lift = self.bind_embargo(self.decisions["NAM_fuel_embargo_lift"], target)
            facts = self.independent_facts()
            facts[(target, "tag", target)] = True
            facts[(target, "exists", "yes")] = True
            support = ("NAM", "variable", "NAM_grp_trade_support")
            modifier = (target, "has_dynamic_modifier", "NAM_fuel_embargo_modifier")
            facts[support] = 50
            pp = facts[("NAM", "numeric", "has_political_power")]
            facts[("NAM", "numeric", "has_political_power")] -= int(scalar(impose, "cost"))
            with patch.object(self, "effects", effects):
                self.apply(block(impose, "complete_effect"), facts)
                self.assertTrue(facts[modifier])
                self.assertEqual(facts[support], 40)
                self.assertEqual(facts[("NAM", "numeric", "has_political_power")], pp - 25)
                before = dict(facts)
                self.apply(effects["NAM_oil_impose_embargo"], facts, target)
                self.assertEqual(facts, before)
                self.assertTrue(self.matches(block(lift, "visible"), facts))
                self.apply(block(lift, "complete_effect"), facts)
                self.assertFalse(facts[modifier])
                self.assertEqual(facts[support], 45)
                after = dict(facts)
                self.apply(block(lift, "complete_effect"), facts)
                self.assertEqual(facts, after)
                # Tribute automatically opens the two promised supply routes;
                # a previously rendered lift button cannot grant support later.
                self.apply(effects["NAM_oil_impose_embargo"], facts, target)
                self.apply(effects["NAM_rw_start_tribute"], facts)
                self.assertEqual(facts[modifier], target == "SHL")
                before = facts[support]
                self.apply(block(lift, "complete_effect"), facts)
                self.assertEqual(facts[support] - before, 5 if target == "SHL" else 0)
        dynamic = block(parsed("common/dynamic_modifiers/ADISCORD_dynamic_modifiers_NAM.txt"), "NAM_fuel_embargo_modifier")
        self.assertEqual(scalar(dynamic, "fuel_gain_factor"), "-0.20")
        self.assertEqual(scalar(dynamic, "army_fuel_consumption_factor"), "0.05")
        # The actual target-scoped modifier supplies its native numeric preview.
        self.assertIn("add_dynamic_modifier", [e.key for e in block(effects["NAM_oil_impose_embargo"], "if")])

    def test_stale_embargo_payment_refunds_without_changing_the_target(self):
        decision = self.bind_embargo(self.decisions["NAM_fuel_embargo"], "EFL")
        for key, value in (
            (("NAM", "is_subject", "no"), False),
            (("NAM", "has_completed_focus", "NAM_fuel_leverage"), False),
            (("EFL", "exists", "yes"), False),
            (("EFL", "has_country_flag", "NAM_oil_client"), True),
            (("EFL", "has_dynamic_modifier", "NAM_fuel_embargo_modifier"), True),
            (("NAM", "has_country_flag", "NAM_rw_tribute"), True),
        ):
            facts = self.independent_facts()
            facts[("EFL", "tag", "EFL")] = True
            facts[("NAM", "variable", "NAM_grp_trade_support")] = 50
            facts[key] = value
            before = dict(facts)
            facts[("NAM", "numeric", "has_political_power")] -= 25
            self.apply(block(decision, "complete_effect"), facts)
            self.assertEqual(facts, before, key)

    def test_losing_the_basin_closes_embargo_and_island_exile_cannot_reopen_it(self):
        decision = self.bind_embargo(self.decisions["NAM_fuel_embargo"], "EFL")
        cleanup_entry = next(e for e in self.effects["NAM_oil_refresh"]
                             if e.key == "if" and "NAM_fuel_embargo_source" in repr(e.value))
        cleanup = cleanup_entry.value
        dynamics = block(parsed("common/dynamic_modifiers/ADISCORD_dynamic_modifiers_NAM.txt"), "NAM_fuel_embargo_modifier")
        facts = self.independent_facts()
        facts[("EFL", "tag", "EFL")] = True
        facts[("NAM", "variable", "NAM_oil_bonus_units")] = 5
        fields = ("67", "688", "689", "690", "719")
        for state in fields:
            facts[("NAM", "controls_state", state)] = False
        # Every individual controlled field sustains the source, regardless
        # of its owner; the oil accounting uses the same control contract.
        for state in fields:
            facts[("NAM", "controls_state", state)] = True
            self.assertTrue(self.matches(block(decision, "available"), facts))
            self.assertTrue(self.matches(block(dynamics, "enable"), facts))
            facts[("NAM", "controls_state", state)] = False
        facts[("NAM", "controls_state", "225")] = True
        self.assertFalse(self.matches(block(decision, "available"), facts))
        self.assertFalse(self.matches(block(dynamics, "enable"), facts))
        self.assertTrue(self.matches(block(cleanup, "limit"), facts))
        before = dict(facts)
        facts[("NAM", "numeric", "has_political_power")] -= 25
        self.apply(block(decision, "complete_effect"), facts)
        self.assertEqual(facts, before)
        for target in ("EFL", "AZH", "SHL"):
            facts[(target, "has_dynamic_modifier", "NAM_fuel_embargo_modifier")] = True
            facts[(target, "opinion", "embargoed_us:NAM")] = True
        with patch.object(self, "effects", {"NAM_oil_lift_embargo": self.effects["NAM_oil_lift_embargo"]}):
            self.apply([cleanup_entry], facts)
        for target in ("EFL", "AZH", "SHL"):
            self.assertFalse(facts[(target, "has_dynamic_modifier", "NAM_fuel_embargo_modifier")])
            self.assertFalse(facts[(target, "opinion", "embargoed_us:NAM")])
        lift = self.effects["NAM_oil_lift_embargo"]
        self.assertIn("ADISCORD_economy_mark_dirty", [e.key for e in walk(lift)])
        callback = read("common/on_actions/03_ADISCORD_nam_resource_war_on_actions.txt")
        self.assertIn("NAM = { NAM_oil_refresh = yes }", callback)


    def military_facts(self):
        facts = self.economy_facts()
        facts[("NAM", "has_war", "no")] = False
        facts[("NAM", "variable", "NAM_line_slots")] = 3
        facts[("NAM", "variable", "NAM_lines_in_progress")] = 0
        facts[("NAM", "equipment", "support_equipment")] = 300
        for state in ("67", "688", "689", "690", "719", "700"):
            facts[(state, "has_state_flag", "NAM_line_prepared")] = True
            facts[(state, "has_variable", "NAM_field_condition")] = True
        facts[("700", "numeric", "arms_factory")] = 1
        return facts

    def military_projects(self):
        return {name: body for name, body in self.decisions.items() if name.startswith("NAM_mil_")}

    def test_military_focus_actions_and_real_bypass_boundaries(self):
        section = read(TREES["main"][0]).split("# ----- Garrisons, mobilisation orders and defence lines -----", 1)[1].split("# ----- Air service -----", 1)[0]
        names = re.findall(r"\bid = (NAM_\w+)", section)
        self.assertEqual(len(names), 12)
        for name in names:
            self.assertTrue(any(e.key == "unlock_decision_tooltip" for e in walk(block(self.focuses[name], "completion_reward"))), name)
        self.assertEqual(len(self.military_projects()), 9)
        facts = self.military_facts()
        for name, body in self.military_projects().items():
            self.assertTrue(self.matches(block(self.bind_field(body), "visible"), facts), name)
            self.assertTrue(self.matches(block(self.bind_field(body), "available"), facts), name)
        depot = self.decisions["NAM_mil_forward_supply"]
        facts[("NAM", "variable", "NAM_line_slots")] = 2
        self.assertFalse(self.matches(block(depot, "visible"), facts))
        # Bypassed prewar focuses do not reopen supply orders after settlement.
        facts[("NAM", "has_global_flag", BASE + "_scheduled")] = False
        facts[("NAM", "has_global_flag", BASE + "_resolved")] = True
        self.assertFalse(self.matches(block(self.decisions["NAM_mil_reserve_arsenal"], "visible"), facts))

    def motor_order_facts(self):
        facts = self.military_facts()
        facts[("NAM", "numeric", "has_manpower")] = 4600
        facts[("NAM", "variable", "NAM_order_cap")] = 4
        facts[("NAM", "variable", "NAM_orders_paid")] = 0
        return facts

    def test_motor_order_unlocks_after_both_institutions_in_either_order(self):
        pair = ("NAM_motor_pool", "NAM_mobilisation_office")
        decision = block(block(parsed(f"common/decisions/{BASE}_decisions.txt"), "NAM_mobilisation"), "NAM_order_motor_column")
        for order in permutations(pair):
            facts = self.motor_order_facts()
            for focus in pair:
                facts[("NAM", "has_completed_focus", focus)] = False
            for index, focus in enumerate(order):
                reward = block(self.focuses[focus], "completion_reward")
                unlocked = [e.value for _, e in selected_effects(self.expand(reward), facts, "NAM")
                            if e.key == "unlock_decision_tooltip"]
                self.assertEqual("NAM_order_motor_column" in unlocked, index == 1, (order, focus))
                # Native completion history is updated after the reward is evaluated.
                self.apply(reward, facts)
                facts[("NAM", "has_completed_focus", focus)] = True
                self.assertEqual(self.matches(block(decision, "visible"), facts), index == 1)
            self.assertTrue(self.matches(block(decision, "custom_cost_trigger"), facts))
            self.apply(block(decision, "complete_effect"), facts)
            self.assertEqual(facts[("NAM", "variable", "NAM_order_motor_paid")], 1)
            self.assertEqual(facts[("NAM", "variable", "NAM_orders_paid")], 1)

    def test_motor_order_rejects_missing_institutions_and_closed_preparation(self):
        decision = block(block(parsed(f"common/decisions/{BASE}_decisions.txt"), "NAM_mobilisation"), "NAM_order_motor_column")
        for pool, office, clock in product((False, True), repeat=3):
            facts = self.motor_order_facts()
            facts[("NAM", "has_completed_focus", "NAM_motor_pool")] = pool
            facts[("NAM", "has_completed_focus", "NAM_mobilisation_office")] = office
            facts[("NAM", "has_global_flag", BASE + "_scheduled")] = clock
            allowed = pool and office and clock
            self.assertEqual(self.matches(block(decision, "visible"), facts), allowed)
            before = dict(facts)
            self.apply(block(decision, "complete_effect"), facts)
            if allowed:
                self.assertEqual(facts[("NAM", "numeric", "has_fuel")], before[("NAM", "numeric", "has_fuel")] - 3000)
                self.assertEqual(facts[("NAM", "numeric", "has_manpower")], before[("NAM", "numeric", "has_manpower")] - 4600)
            else:
                self.assertEqual(facts, before)
        for phase in ("started", "resolved"):
            facts = self.motor_order_facts()
            facts[("NAM", "has_global_flag", BASE + "_scheduled")] = False
            facts[("NAM", "has_global_flag", BASE + "_" + phase)] = True
            for name in ("NAM_motor_pool", "NAM_mobilisation_office"):
                reward = block(self.focuses[name], "completion_reward")
                unlocked = [e.value for _, e in selected_effects(self.expand(reward), facts, "NAM")
                            if e.key == "unlock_decision_tooltip"]
                self.assertNotIn("NAM_order_motor_column", unlocked)
                if name == "NAM_motor_pool":
                    self.assertIn("NAM_mil_carrier_contract", unlocked)
            self.assertTrue(self.matches(block(self.decisions["NAM_mil_carrier_contract"], "visible"), facts))
            self.assertTrue(self.matches(block(self.decisions["NAM_mil_carrier_contract"], "available"), facts))

    def test_military_prices_and_debits_use_exact_balances(self):
        prices = {
            "recruit_depots": (35, 200, 0, 0), "engineer_supplies": (25, 150, 0, 0),
            "carrier_contract": (35, 250, 0, 0), "reserve_arsenal": (30, 300, 0, 0),
            "arsenal_batch": (35, 250, 0, 0), "command_course": (35, 150, 0, 0),
            "mobile_surge": (40, 0, 3000, 0), "forward_supply": (25, 150, 0, 60),
        }
        keys = (("NAM", "numeric", "has_political_power"), ("NAM", "variable", "ADISCORD_economy_treasury"),
                ("NAM", "numeric", "has_fuel"), ("NAM", "equipment", "support_equipment"))
        for suffix, amounts in prices.items():
            body = self.bind_field(self.decisions["NAM_mil_" + suffix])
            for key, price in zip(keys, amounts):
                if not price:
                    continue
                facts = self.military_facts()
                facts.update(zip(keys, amounts))
                self.assertTrue(self.matches(block(body, "custom_cost_trigger"), facts), suffix)
                facts[key] -= 0.001
                self.assertFalse(self.matches(block(body, "custom_cost_trigger"), facts), suffix)
                before = dict(facts)
                self.apply(block(body, "complete_effect"), facts)
                self.assertEqual(facts, before, (suffix, key))
            facts = self.military_facts()
            facts.update(zip(keys, amounts))
            self.apply(block(body, "complete_effect"), facts)
            self.assertEqual([facts[k] for k in keys], [0, 0, 0, 0], suffix)
            paid = dict(facts)
            self.apply(block(body, "complete_effect"), facts)
            self.assertEqual(facts, paid, suffix)
        security = self.decisions["NAM_mil_field_security"]
        self.assertEqual(scalar(security, "cost"), "35")
        self.assertFalse(any(e.key == "custom_cost_text" for e in security))
        depot = self.decisions["NAM_mil_forward_supply"]
        debit = [e.value for e in walk(block(depot, "complete_effect"))
                 if e.key == "add_equipment_to_stockpile" and scalar(e.value, "amount") == "-60"]
        self.assertEqual(len(debit), 1)
        self.assertFalse(any(e.key == "producer" for e in debit[0]))

    def test_military_procurement_delivers_once_and_refunds_interrupted_orders(self):
        rewards = {
            "recruit_depots": (("numeric", "has_manpower", 12000),),
            "engineer_supplies": (("equipment", "support_equipment", 180), ("equipment", "artillery_equipment", 36)),
            "carrier_contract": (("equipment", "ADISCORD_armored_carrier_2163", 160), ("equipment", "support_equipment", 60)),
            "reserve_arsenal": (("equipment", "infantry_equipment", 9000), ("equipment", "support_equipment", 80)),
            "arsenal_batch": (("equipment", "artillery_equipment", 60), ("equipment", "anti_air_equipment", 36), ("equipment", "anti_tank_equipment", 36)),
            "command_course": (("numeric", "army_experience", 25), ("numeric", "command_power", 20)),
        }
        for suffix, deltas in rewards.items():
            body = self.decisions["NAM_mil_" + suffix]
            facts = self.military_facts()
            self.apply(block(body, "complete_effect"), facts)
            before = dict(facts)
            facts[("NAM", "has_global_flag", BASE + "_scheduled")] = False
            facts[("NAM", "has_global_flag", BASE + "_started")] = True
            self.assertFalse(self.matches(block(body, "cancel_trigger"), facts), suffix)
            self.apply(block(body, "remove_effect"), facts)
            for kind, resource, delta in deltas:
                key = ("NAM", kind, resource)
                self.assertEqual(facts[key] - before.get(key, 0), delta, suffix)
            settled = dict(facts)
            self.apply(block(body, "remove_effect"), facts)
            self.apply(block(body, "cancel_effect"), facts)
            self.assertEqual(facts, settled, suffix)
            for ended in (("NAM", "is_subject", "no"), ("NAM", "has_capitulated", "no")):
                for exit_name in ("remove_effect", "cancel_effect"):
                    facts = self.military_facts()
                    self.apply(block(body, "complete_effect"), facts)
                    facts[ended] = False
                    self.apply(block(body, exit_name), facts)
                    self.assertEqual(facts[("NAM", "numeric", "has_political_power")], 1000, suffix)
                    self.assertEqual(facts[("NAM", "variable", "ADISCORD_economy_treasury")], 10000, suffix)
                    settled = dict(facts)
                    self.apply(block(body, "remove_effect"), facts)
                    self.apply(block(body, "cancel_effect"), facts)
                    self.assertEqual(facts, settled, suffix)

    def test_oilfield_security_mitigates_held_fields_but_not_scorched_ceded_land(self):
        with patch.dict(self.effects, {"NAM_oil_refresh": []}):
            for damage in (15, 20, 70):
                for active, owned, controlled, independent in product((False, True), repeat=4):
                    facts = self.military_facts()
                    facts[("NAM", "has_decision", "NAM_mil_field_security")] = active
                    facts[("67", "is_owned_by", "NAM")] = owned
                    facts[("67", "is_controlled_by", "NAM")] = controlled
                    facts[("NAM", "is_subject", "no")] = independent
                    facts[("67", "variable", "NAM_field_damage_amount")] = damage
                    self.apply(self.effects["NAM_field_apply_damage"], facts, "67")
                    mitigation = 0.5 if active and owned and controlled and independent else 1
                    self.assertEqual(facts[("67", "variable", "NAM_field_condition")], 80 - damage * mitigation)
                    self.assertEqual(facts[("67", "variable", "NAM_field_damage_amount")], damage)
        scorched = self.decisions.get("NAM_scorch_wells")
        if scorched is None:
            scorched = block(block(parsed(f"common/decisions/{BASE}_decisions.txt"), "NAM_mobilisation"), "NAM_scorch_wells")
        self.assertFalse(any(e.key == "NAM_field_apply_damage" for e in walk(scorched)))

    def test_mobile_operation_spends_fuel_and_closes_on_every_terminal_condition(self):
        body = self.decisions["NAM_mil_mobile_surge"]
        modifier = "NAM_mil_mobile_operation"
        definition = block(parsed("common/dynamic_modifiers/ADISCORD_dynamic_modifiers_NAM.txt"), modifier)
        for key in (("NAM", "has_war", "yes"), ("NAM", "is_subject", "no"), ("NAM", "has_capitulated", "no")):
            facts = self.military_facts()
            self.apply(block(body, "complete_effect"), facts)
            self.assertTrue(facts[("NAM", "has_dynamic_modifier", modifier)])
            self.assertEqual(facts[("NAM", "numeric", "has_fuel")], 17000)
            self.assertEqual(facts[("NAM", "numeric", "has_political_power")], 960)
            facts[key] = False
            self.assertTrue(self.matches(block(body, "cancel_trigger"), facts))
            self.assertFalse(self.matches(block(definition, "enable"), facts))
            self.assertTrue(self.matches(block(definition, "remove_trigger"), facts))
            self.apply(block(body, "cancel_effect"), facts)
            self.assertFalse(facts[("NAM", "has_dynamic_modifier", modifier)])
            settled = dict(facts)
            self.apply(block(body, "remove_effect"), facts)
            self.assertEqual(facts, settled)
        self.assertEqual(scalar(definition, "army_speed_factor"), "0.10")
        self.assertEqual(scalar(definition, "army_fuel_consumption_factor"), "0.15")

    def test_forward_supply_uses_line_slots_and_refunds_every_paid_resource(self):
        body = self.bind_field(self.decisions["NAM_mil_forward_supply"])
        for ended in (("67", "is_owned_by", "NAM"), ("67", "is_controlled_by", "NAM"),
                      ("NAM", "is_subject", "no"), ("NAM", "has_capitulated", "no"), ("campaign",)):
            facts = self.military_facts()
            self.apply(block(body, "complete_effect"), facts)
            self.assertEqual(facts[("NAM", "variable", "NAM_lines_in_progress")], 1)
            self.assertEqual(facts[("NAM", "equipment", "support_equipment")], 240)
            paid = dict(facts)
            self.apply(block(body, "complete_effect"), facts)
            self.assertEqual(facts, paid)
            ordinary = self.bind_field(block(block(parsed(f"common/decisions/{BASE}_decisions.txt"), "NAM_mobilisation"), "NAM_prepare_line"))
            self.assertFalse(self.matches(block(ordinary, "available"), facts))
            if ended == ("campaign",):
                facts[("NAM", "has_global_flag", BASE + "_scheduled")] = False
                facts[("NAM", "has_global_flag", BASE + "_resolved")] = True
            else:
                facts[ended] = False
            self.assertTrue(self.matches(block(body, "cancel_trigger"), facts))
            self.apply(block(body, "remove_effect"), facts)
            self.assertEqual(facts[("NAM", "numeric", "has_political_power")], 1000)
            self.assertEqual(facts[("NAM", "variable", "ADISCORD_economy_treasury")], 10000)
            self.assertEqual(facts[("NAM", "equipment", "support_equipment")], 300)
            self.assertEqual(facts[("NAM", "variable", "NAM_lines_in_progress")], 0)
            settled = dict(facts)
            self.apply(block(body, "cancel_effect"), facts)
            self.assertEqual(facts, settled)
        facts = self.military_facts()
        facts[("NAM", "variable", "NAM_lines_in_progress")] = 3
        before = dict(facts)
        self.apply(block(body, "complete_effect"), facts)
        self.assertEqual(facts, before)

    def test_completed_forward_depot_stays_local_and_ordinary_lines_keep_their_price(self):
        body = self.bind_field(self.decisions["NAM_mil_forward_supply"])
        facts = self.military_facts()
        self.apply(block(body, "complete_effect"), facts)
        self.apply(block(body, "remove_effect"), facts)
        self.assertTrue(facts[("67", "has_dynamic_modifier", "NAM_mil_forward_depot")])
        self.assertFalse(facts[("67", "has_variable", "NAM_line_supply_deposit")])
        self.assertEqual(facts[("NAM", "variable", "NAM_lines_in_progress")], 0)
        settled = dict(facts)
        self.apply(block(body, "cancel_effect"), facts)
        self.apply(block(body, "remove_effect"), facts)
        self.assertEqual(facts, settled)
        definition = block(parsed("common/dynamic_modifiers/ADISCORD_dynamic_modifiers_NAM.txt"), "NAM_mil_forward_depot")
        self.assertTrue(matches_conditions(self.expand(block(definition, "enable")), facts, "67"))
        facts[("67", "is_controlled_by", "NAM")] = False
        self.assertFalse(matches_conditions(self.expand(block(definition, "enable")), facts, "67"))
        self.assertTrue(matches_conditions(self.expand(block(definition, "remove_trigger")), facts, "67"))
        facts = self.military_facts()
        facts[("67", "has_state_flag", "NAM_line_in_progress")] = True
        facts[("NAM", "variable", "NAM_lines_in_progress")] = 1
        facts[("NAM", "variable", "ADISCORD_economy_treasury")] = 9900
        facts[("NAM", "numeric", "has_political_power")] = 970
        self.apply(self.effects["NAM_line_release"], facts, "67")
        self.assertEqual(facts[("NAM", "variable", "ADISCORD_economy_treasury")], 10000)
        self.assertEqual(facts[("NAM", "numeric", "has_political_power")], 970)
        self.assertEqual(facts[("NAM", "equipment", "support_equipment")], 300)

    def ordinary_line_fixture(self):
        decision = block(block(parsed(f"common/decisions/{BASE}_decisions.txt"), "NAM_mobilisation"), "NAM_prepare_line")
        facts = self.military_facts()
        facts[("67", "has_state_flag", "NAM_line_prepared")] = False
        facts[("67", "fixture_foreign_land_border", "yes")] = True
        return self.bind_field(decision), facts

    def test_line_payment_rechecks_the_live_offer_and_does_not_overwrite_escrow(self):
        failures = (
            (("NAM", "has_global_flag", BASE + "_scheduled"), False),
            (("NAM", "has_completed_focus", "NAM_line_survey"), False),
            (("NAM", "has_capitulated", "no"), False),
            (("67", "is_owned_by", "NAM"), False),
            (("67", "is_controlled_by", "NAM"), False),
            (("67", "fixture_foreign_land_border", "yes"), False),
            (("67", "has_state_flag", "NAM_line_prepared"), True),
            (("67", "has_state_flag", "NAM_line_in_progress"), True),
        )
        for key, value in failures:
            decision, facts = self.ordinary_line_fixture()
            facts[key] = value
            before = dict(facts)
            self.apply(block(decision, "complete_effect"), facts)
            self.assertEqual(facts, before, key)
        decision, facts = self.ordinary_line_fixture()
        self.apply(block(decision, "complete_effect"), facts)
        self.assertEqual(facts[("NAM", "numeric", "has_political_power")], 970)
        self.assertEqual(facts[("NAM", "variable", "ADISCORD_economy_treasury")], 9900)
        self.assertEqual(facts[("NAM", "variable", "NAM_lines_in_progress")], 1)
        paid = dict(facts)
        self.apply(block(decision, "complete_effect"), facts)
        self.assertEqual(facts, paid)

    def test_paid_permanent_line_finishes_after_peace_or_refunds_a_lost_site(self):
        for loss in (None, ("NAM", "has_capitulated", "no"), ("67", "is_owned_by", "NAM"),
                     ("67", "is_controlled_by", "NAM"), ("67", "fixture_foreign_land_border", "yes")):
            decision, facts = self.ordinary_line_fixture()
            self.apply(block(decision, "complete_effect"), facts)
            facts[("NAM", "has_global_flag", BASE + "_scheduled")] = False
            facts[("NAM", "has_global_flag", BASE + "_resolved")] = True
            if loss:
                facts[loss] = False
            self.assertFalse(self.matches(block(decision, "available"), facts))
            self.apply(block(decision, "remove_effect"), facts)
            self.assertEqual(facts.get(("67", "has_state_flag", "NAM_line_prepared"), False), loss is None)
            self.assertEqual(facts.get(("67", "building", "bunker"), 0), 2 if loss is None else 0)
            self.assertEqual(facts[("NAM", "variable", "ADISCORD_economy_treasury")], 9900 if loss is None else 10000)
            self.assertEqual(facts[("NAM", "numeric", "has_political_power")], 970)
            self.assertEqual(facts[("NAM", "variable", "NAM_lines_in_progress")], 0)
            settled = dict(facts)
            self.apply(block(decision, "remove_effect"), facts)
            self.apply(block(decision, "cancel_effect"), facts)
            self.assertEqual(facts, settled)

    def test_old_line_callback_cannot_settle_a_new_forward_depot(self):
        decision, facts = self.ordinary_line_fixture()
        self.apply(block(decision, "complete_effect"), facts)
        self.apply(block(decision, "remove_effect"), facts)
        depot = self.bind_field(self.decisions["NAM_mil_forward_supply"])
        self.apply(block(depot, "complete_effect"), facts)
        self.assertEqual(facts[("67", "variable", "NAM_line_supply_deposit")], 150)
        pending = dict(facts)
        self.apply(block(decision, "remove_effect"), facts)
        self.apply(block(decision, "cancel_effect"), facts)
        self.assertEqual(facts, pending)
        self.apply(block(depot, "remove_effect"), facts)
        self.assertTrue(facts[("67", "has_dynamic_modifier", "NAM_mil_forward_depot")])
        self.assertEqual(facts[("NAM", "variable", "NAM_lines_in_progress")], 0)

    def test_carrier_order_matches_the_real_column_and_quartermaster_upgrades_supply(self):
        unit = block(block(parsed("common/units/ADISCORD_land_units.txt"), "sub_units"), "ADISCORD_mechanized_infantry")
        self.assertEqual(scalar(block(unit, "need"), "ADISCORD_armored_carrier_archetype"), "40")
        self.assertEqual(sum(e.key == "ADISCORD_mechanized_infantry" for e in walk(self.effects["NAM_order_ensure_templates"])), 4)
        body = self.decisions["NAM_mil_carrier_contract"]
        facts = self.military_facts()
        technology = ("NAM", "has_tech", "ADISCORD_tech_armored_carrier_program")
        self.apply(block(body, "complete_effect"), facts)
        self.assertFalse(facts.get(technology, False))
        self.apply(block(body, "remove_effect"), facts)
        self.assertTrue(facts[technology])
        self.assertEqual(facts[("NAM", "equipment", "ADISCORD_armored_carrier_2163")], 160)
        for quartermaster in (False, True):
            facts = self.military_facts()
            facts[("NAM", "has_completed_focus", "NAM_quartermaster")] = quartermaster
            self.apply(block(self.decisions["NAM_supply_order"], "complete_effect"), facts)
            self.assertEqual(facts.get(("NAM", "equipment", "ADISCORD_squad_weapons_equipment"), 0), 80 if quartermaster else 0)

    def test_military_programmes_fit_the_normal_preparation_window(self):
        paths = (
            (("count_garrisons", "mobile_columns", "motor_pool"), 28, 84),
            (("count_garrisons", "mobilisation_office", "line_survey", "reserve_rolls"), 21, 84),
            (("count_garrisons", "mobile_columns", "motor_pool", "quartermaster", "officer_courses"), 21, 126),
        )
        for path, duration, expected in paths:
            days = sum(int(scalar(self.focuses["NAM_" + f], "cost")) * 7 for f in path)
            self.assertEqual(days + duration, expected)
            self.assertLess(expected, 300)
        surveyed = sum(int(scalar(self.focuses["NAM_" + f], "cost")) * 7 for f in ("count_garrisons", "field_guards", "mobilisation_office", "line_survey"))
        engineers = surveyed + int(scalar(self.focuses["NAM_line_engineers"], "cost")) * 7
        self.assertEqual(max(surveyed + 35, engineers) + 14, 112)
        days = 0
        reached = {"NAM_independence_day": 0}
        for name in ("count_garrisons", "mobilisation_office", "line_survey", "field_guards", "line_engineers"):
            body = self.focuses["NAM_" + name]
            for requirement in (e.value for e in body if e.key == "prerequisite"):
                self.assertTrue(any(e.value in reached for e in requirement), name)
            days += int(scalar(body, "cost")) * 7
            reached["NAM_" + name] = days
        mobilization = block(parsed(f"common/decisions/{BASE}_decisions.txt"), "NAM_mobilisation")
        line_duration = int(scalar(block(mobilization, "NAM_prepare_line"), "days_remove"))
        depot_duration = int(scalar(self.decisions["NAM_mil_forward_supply"], "days_remove"))
        line_ready = reached["NAM_line_survey"] + line_duration
        self.assertEqual(max(line_ready, reached["NAM_line_engineers"]) + depot_duration, 98)

    def economy_facts(self):
        facts = self.independent_facts()
        facts[("NAM", "variable", "NAM_oil_contracts")] = 2
        facts[("NAM", "variable", "NAM_project_slots")] = 2
        facts[("NAM", "variable", "NAM_projects_in_progress")] = 0
        facts[("fixture", "previous_state")] = "67"
        for state in ("67", "688", "689", "690", "719", "700"):
            for predicate in ("is_owned_by", "is_controlled_by"):
                facts[(state, predicate, "NAM")] = True
            for predicate in ("owns_state", "controls_state"):
                facts[("NAM", predicate, state)] = True
            facts[(state, "variable", "NAM_field_capacity")] = 8
            facts[(state, "variable", "NAM_field_max_capacity")] = 11
            facts[(state, "has_variable", "NAM_field_capacity")] = True
            facts[(state, "variable", "NAM_field_condition")] = 80
        facts[("67", "numeric", "synthetic_refinery")] = 1
        facts[("700", "numeric", "fuel_silo")] = 1
        facts[("67", "fixture_free_building_slots", "arms_factory:1:yes")] = True
        return facts

    def bind_field(self, entries, state="67"):
        """Resolve the native decision target; shared effects retain their state scope."""
        return [replace(e, key=state if e.key == "FROM" else e.key,
                        value=self.bind_field(e.value, state) if isinstance(e.value, list)
                        else "NAM" if e.value == "ROOT" else e.value) for e in entries]

    def economy_projects(self):
        return {name: body for name, body in self.decisions.items() if name.startswith("NAM_econ_")}

    def test_pragmatic_repair_partnerships_reopen_fields_and_leave_one_spare_pump(self):
        focus = self.postwar["NAM_repair_depots"]
        unlock = "NAM_econ_emergency_service"
        self.assertIn(unlock, [e.value for e in walk(block(focus, "completion_reward"))
                               if e.key == "unlock_decision_tooltip"])
        order = self.bind_field(self.decisions[unlock])
        condition = ("67", "variable", "NAM_field_condition")
        burn = ("67", "has_state_flag", "NAM_wells_scorched")
        modifier = ("67", "has_dynamic_modifier", "NAM_scorched_wells_modifier")
        spare = ("67", "has_state_flag", "NAM_field_spare_pump")
        with patch.dict(self.effects, {"NAM_oil_refresh": []}):
            for cooperative, commission, burning in product((False, True), repeat=3):
                facts = self.economy_facts()
                facts[("NAM", "has_completed_focus", "NAM_second_drilling_crew")] = False
                facts[("NAM", "has_completed_focus", "NAM_pw_energy_commission")] = commission
                facts[("NAM", "has_completed_focus", "NAM_repair_depots")] = cooperative
                facts[("67", "has_variable", "NAM_field_condition")] = True
                facts[condition] = 10
                facts[burn] = facts[modifier] = burning
                allowed = (cooperative or commission) and (not burning or cooperative)
                self.assertEqual(self.matches(block(order, "visible"), facts), cooperative or commission)
                self.assertEqual(self.matches(block(order, "available"), facts), allowed)
                self.apply(block(order, "complete_effect"), facts)
                cash = ("NAM", "variable", "ADISCORD_economy_treasury")
                self.assertEqual(facts[cash], 9750 if allowed else 10000)
                if not allowed:
                    continue
                paid = dict(facts)
                facts[("67", "is_controlled_by", "NAM")] = False
                self.assertTrue(self.matches(block(order, "cancel_trigger"), facts))
                self.apply(block(order, "remove_effect"), facts)
                self.apply(block(order, "cancel_effect"), facts)
                self.assertEqual(facts[cash], 10000)
                self.assertEqual(facts[("NAM", "numeric", "has_political_power")], 1000)
                self.assertEqual((facts[condition], facts[burn], facts[modifier]), (10, burning, burning))
                self.assertFalse(facts.get(spare, False))
                facts = paid
                self.apply(block(order, "remove_effect"), facts)
                repaired = 75 if commission else 60
                self.assertEqual((facts[condition], facts[burn], facts[modifier]), (repaired, False, False))
                self.assertEqual(bool(facts.get(spare)), cooperative)
                facts[("67", "variable", "NAM_field_damage_amount")] = 40
                self.apply(self.effects["NAM_field_apply_damage"], facts, "67")
                self.assertEqual(facts[condition], repaired - (15 if cooperative else 40))
                self.assertFalse(facts.get(spare, False))
                self.apply(self.effects["NAM_field_apply_damage"], facts, "67")
                self.assertEqual(facts[condition], max(0, repaired - (55 if cooperative else 80)))
            facts = self.economy_facts()
            facts[("NAM", "has_completed_focus", "NAM_repair_depots")] = True
            facts[("67", "has_variable", "NAM_field_condition")] = True
            facts[condition] = 100
            self.assertTrue(self.matches(block(order, "available"), facts))
            self.apply(block(order, "complete_effect"), facts)
            self.apply(block(order, "remove_effect"), facts)
            self.assertTrue(facts[spare])
            self.assertFalse(self.matches(block(order, "available"), facts))
            facts[("67", "variable", "NAM_field_damage_amount")] = 10
            self.apply(self.effects["NAM_field_apply_damage"], facts, "67")
            self.assertEqual(facts[condition], 100)
            self.assertFalse(facts[spare])
            self.assertTrue(self.matches(block(order, "available"), facts))

        facts = self.economy_facts()
        facts.update(self.captured_field_facts())
        facts[("fixture", "previous_state")] = "67"
        facts[("NAM", "variable", "NAM_oil_bonus_units")] = 0
        facts[("NAM", "has_completed_focus", "NAM_repair_depots")] = True
        facts[burn] = facts[modifier] = True
        facts[condition] = 10
        self.apply(self.effects["NAM_field_update_units"], facts, "67")
        self.assertEqual(facts[("67", "variable", "NAM_field_units")], 0)
        self.apply(block(order, "complete_effect"), facts)
        self.apply(block(order, "remove_effect"), facts)
        self.assertGreater(facts[("67", "variable", "NAM_field_units")], 0)
        self.assertGreater(facts[("67", "variable", "NAM_field_oil")], 5)

    def test_economic_focuses_all_unlock_actions_and_orders_fit_the_deadline(self):
        source = read(TREES["main"][0])
        section = source.split("# ----- Oil economy -----", 1)[1].split("# ----- Garrisons", 1)[0]
        names = re.findall(r"\bid = (NAM_\w+)", section)
        self.assertEqual(len(names), 16)
        for name in names:
            self.assertTrue(any(e.key == "unlock_decision_tooltip" for e in walk(block(self.focuses[name], "completion_reward"))), name)
        projects = self.economy_projects()
        self.assertEqual(len(projects), 9)
        for name, project in projects.items():
            facts = self.economy_facts()
            project = self.bind_field(project)
            self.assertTrue(self.matches(block(project, "visible"), facts), name)
            self.assertTrue(self.matches(block(project, "available"), facts), name)
            if name.endswith("export_dispatch"):
                facts[("NAM", "has_country_flag", "NAM_econ_dispatch_paid")] = True
            self.assertFalse(self.matches(block(project, "cancel_trigger"), facts), name)
        paths = (
            (("well_register", "export_quays", "insured_cargoes"), 21),
            (("well_register", "domestic_refining", "refinery_programme"), 90 + 28),
            (("well_register", "contract_bureau", "field_repair_crews", "klyuchevsk_pipeline", "deep_wells"), 42),
            (("well_register", "domestic_refining", "machine_shops", "civilian_combine", "technical_college"), 35),
        )
        for focuses, duration in paths:
            days = sum(int(scalar(self.focuses["NAM_" + f], "cost")) * 7 for f in focuses)
            self.assertLess(days + duration, 300, focuses)

    def test_economic_prices_check_fractional_balances_and_cannot_double_charge(self):
        prices = {
            "insured_freighters": (35, 200, 0), "petrochemical_batch": (40, 200, 4000),
            "strategic_reserve": (30, 650, 0), "combine_arsenal": (40, 350, 0),
            "road_columns": (25, 150, 1500), "engineer_practice": (40, 200, 0),
            "deep_drilling": (30, 200, 0), "emergency_service": (30, 250, 0),
            "export_dispatch": (25, 50, 0),
        }
        keys = (("NAM", "numeric", "has_political_power"), ("NAM", "variable", "ADISCORD_economy_treasury"), ("NAM", "numeric", "has_fuel"))
        for suffix, amounts in prices.items():
            name = "NAM_econ_" + suffix
            project = self.bind_field(self.decisions[name])
            self.assertEqual(scalar(project, "cost"), "0")
            for key, price in zip(keys, amounts):
                if price == 0:
                    continue
                facts = self.economy_facts()
                facts.update(zip(keys, amounts))
                self.assertTrue(self.matches(block(project, "custom_cost_trigger"), facts), name)
                facts[key] -= 0.001
                self.assertFalse(self.matches(block(project, "custom_cost_trigger"), facts), name)
                before = dict(facts)
                self.apply(block(project, "complete_effect"), facts)
                self.assertEqual(facts, before, (name, key))
            facts = self.economy_facts()
            facts.update(zip(keys, amounts))
            self.apply(block(project, "complete_effect"), facts)
            for key in keys:
                self.assertEqual(facts[key], 0, name)
            self.assertEqual(facts[("NAM", "variable", "ADISCORD_economy_current_month_action_costs")], amounts[1])
            if suffix != "export_dispatch":
                paid = dict(facts)
                self.apply(block(project, "complete_effect"), facts)
                self.assertEqual(facts, paid, name)

    def test_national_economic_orders_refund_and_deliver_once(self):
        for name, project in self.economy_projects().items():
            if any(e.key == "state_target" for e in project) or name.endswith("export_dispatch"):
                continue
            for failed in (("NAM", "is_subject", "no"), ("NAM", "has_capitulated", "no")):
                for exit_name in ("remove_effect", "cancel_effect"):
                    facts = self.economy_facts()
                    self.apply(block(project, "complete_effect"), facts)
                    facts[failed] = False
                    self.assertTrue(self.matches(block(project, "cancel_trigger"), facts))
                    self.apply(block(project, exit_name), facts)
                    self.assertEqual(facts[("NAM", "numeric", "has_political_power")], 1000, name)
                    self.assertEqual(facts[("NAM", "variable", "ADISCORD_economy_treasury")], 10000, name)
                    self.assertEqual(facts[("NAM", "numeric", "has_fuel")], 20000, name)
                    facts[failed] = True
                    settled = dict(facts)
                    self.apply(block(project, "remove_effect"), facts)
                    self.apply(block(project, "cancel_effect"), facts)
                    self.assertEqual(facts, settled, name)
            facts = self.economy_facts()
            self.apply(block(project, "complete_effect"), facts)
            self.apply(block(project, "remove_effect"), facts)
            self.assertFalse(facts[("NAM", "has_country_flag", name + "_paid")])
            settled = dict(facts)
            self.apply(block(project, "remove_effect"), facts)
            self.apply(block(project, "cancel_effect"), facts)
            self.assertEqual(facts, settled, name)
            if name.endswith("petrochemical_batch"):
                self.assertEqual(facts[("NAM", "equipment", "motorized_equipment")], 150)
                self.assertEqual(facts[("NAM", "equipment", "artillery_equipment")], 60)
            if name.endswith("insured_freighters"):
                self.assertEqual(facts[("NAM", "equipment", "convoy")], 25)
            if name.endswith("strategic_reserve"):
                self.assertEqual(facts[("NAM", "numeric", "has_fuel")], 28000)
            if name.endswith("combine_arsenal"):
                self.assertEqual(facts[("67", "building", "arms_factory")], 1)
            if name.endswith("road_columns"):
                self.assertEqual(facts[("NAM", "equipment", "motorized_equipment")], 100)
            if name.endswith("engineer_practice"):
                self.assertEqual(facts[("NAM", "tech_bonus", name)], (0.5, 2, "industry"))

    def test_processing_requires_a_real_controlled_refinery_and_refunds_its_loss(self):
        project = self.decisions["NAM_econ_petrochemical_batch"]
        for lost in (("67", "numeric", "synthetic_refinery"), ("67", "is_owned_by", "NAM"), ("67", "is_controlled_by", "NAM")):
            facts = self.economy_facts()
            self.apply(block(project, "complete_effect"), facts)
            facts[lost] = 0
            self.assertFalse(self.matches(block(project, "available"), facts))
            self.assertTrue(self.matches(block(project, "cancel_trigger"), facts))
            self.apply(block(project, "remove_effect"), facts)
            self.assertEqual(facts[("NAM", "numeric", "has_fuel")], 20000)
            self.assertEqual(facts[("NAM", "variable", "ADISCORD_economy_treasury")], 10000)
            self.assertNotIn(("NAM", "equipment", "artillery_equipment"), facts)
            facts[("689", "numeric", "synthetic_refinery")] = 1
            self.assertTrue(self.matches(block(project, "available"), facts))

    def test_export_dispatch_only_pays_for_actual_deliveries_without_debiting_buyers(self):
        for fuel, active, paid, harbour, expected_revenue, deliveries in (
            (14999.99, True, True, True, 0, 0), (15000, True, True, True, 70, 1),
            (30000, True, True, True, 140, 2), (30000, False, True, True, 80, 2),
            (30000, True, True, False, 80, 2), (30000, True, False, True, 80, 2),
        ):
            facts = self.economy_facts()
            facts[("NAM", "numeric", "has_fuel")] = fuel
            facts[("NAM", "has_decision", "NAM_econ_export_dispatch")] = active
            facts[("NAM", "has_country_flag", "NAM_econ_dispatch_paid")] = paid
            facts[("NAM", "controls_state", "700")] = harbour
            for buyer in ("EFL", "AZH"):
                facts[(buyer, "has_country_flag", "NAM_oil_client")] = True
                facts[(buyer, "variable", "ADISCORD_economy_treasury")] = 123
            self.apply(self.effects["NAM_oil_settle_clients"], facts)
            self.assertEqual(facts[("NAM", "variable", "ADISCORD_economy_treasury")], 10000 + expected_revenue)
            self.assertEqual(facts[("NAM", "numeric", "has_fuel")], fuel - deliveries * 15000)
            self.assertEqual(sum(facts.get((buyer, "numeric", "has_fuel"), 0) for buyer in ("EFL", "AZH")), deliveries * 15000)
            for buyer in ("EFL", "AZH"):
                self.assertEqual(facts[(buyer, "variable", "ADISCORD_economy_treasury")], 123)
        dispatch = self.decisions["NAM_econ_export_dispatch"]
        facts = self.economy_facts()
        facts[("NAM", "variable", "NAM_oil_contracts")] = 0
        self.assertFalse(self.matches(block(dispatch, "available"), facts))
        facts[("NAM", "has_country_flag", "NAM_econ_dispatch_paid")] = True
        self.assertFalse(self.matches(block(dispatch, "cancel_trigger"), facts))
        before = facts[("NAM", "variable", "ADISCORD_economy_treasury")]
        self.apply(block(dispatch, "cancel_effect"), facts)
        self.assertFalse(facts[("NAM", "has_country_flag", "NAM_econ_dispatch_paid")])
        self.assertEqual(facts[("NAM", "variable", "ADISCORD_economy_treasury")], before)

    def test_field_orders_share_slots_and_cannot_overwrite_another_payment(self):
        projects = [self.bind_field(self.decisions["NAM_econ_" + name]) for name in ("deep_drilling", "emergency_service")]
        for project in projects:
            facts = self.economy_facts()
            self.apply(block(project, "complete_effect"), facts)
            self.assertEqual(facts[("NAM", "variable", "NAM_projects_in_progress")], 1)
            self.assertTrue(facts[("67", "has_state_flag", "NAM_project_in_progress")])
            paid = dict(facts)
            for contender in projects:
                self.assertFalse(self.matches(block(contender, "available"), facts))
                self.apply(block(contender, "complete_effect"), facts)
                self.assertEqual(facts, paid)
            for name in ("NAM_project_repair_wells", "NAM_project_refinery"):
                contender = self.bind_field(self.decisions[name])
                self.assertFalse(self.matches(block(contender, "available"), facts), name)
            # A second state may use the second slot; a third state cannot pay.
            second = self.bind_field(self.decisions["NAM_econ_deep_drilling"], "689")
            self.apply(block(second, "complete_effect"), facts)
            self.assertEqual(facts[("NAM", "variable", "NAM_projects_in_progress")], 2)
            third = self.bind_field(self.decisions["NAM_econ_emergency_service"], "690")
            paid = dict(facts)
            self.assertFalse(self.matches(block(third, "available"), facts))
            self.apply(block(third, "complete_effect"), facts)
            self.assertEqual(facts, paid)
            self.apply(block(project, "cancel_effect"), facts)
            self.assertEqual(facts[("NAM", "variable", "NAM_projects_in_progress")], 1)
            self.assertEqual(facts[("NAM", "numeric", "has_political_power")], 970)
            self.assertEqual(facts[("NAM", "variable", "ADISCORD_economy_treasury")], 9800)
            self.assertTrue(facts[("689", "has_state_flag", "NAM_project_in_progress")])
            self.assertEqual(facts[("689", "variable", "NAM_project_deposit")], 200)

    def test_field_delivery_and_refund_release_only_their_own_escrow(self):
        with patch.dict(self.effects, {"NAM_oil_refresh": []}):
            for suffix, variable, delta in (("deep_drilling", "NAM_field_capacity", 2), ("emergency_service", "NAM_field_condition", 20)):
                project = self.bind_field(self.decisions["NAM_econ_" + suffix])
                facts = self.economy_facts()
                self.apply(block(project, "complete_effect"), facts)
                before = facts[("67", "variable", variable)]
                self.apply(block(project, "remove_effect"), facts)
                self.assertEqual(facts[("67", "variable", variable)], before + delta)
                self.assertEqual(facts[("NAM", "variable", "NAM_projects_in_progress")], 0)
                self.assertFalse(facts[("67", "has_variable", "NAM_project_pp_deposit")])
                settled = dict(facts)
                self.apply(block(project, "cancel_effect"), facts)
                self.apply(block(project, "remove_effect"), facts)
                self.assertEqual(facts, settled)
                for lost in (("67", "is_owned_by", "NAM"), ("67", "is_controlled_by", "NAM"), ("NAM", "is_subject", "no"), ("NAM", "has_capitulated", "no")):
                    facts = self.economy_facts()
                    self.apply(block(project, "complete_effect"), facts)
                    facts[lost] = False
                    self.assertTrue(self.matches(block(project, "cancel_trigger"), facts))
                    self.apply(block(project, "remove_effect"), facts)
                    self.assertEqual(facts[("NAM", "numeric", "has_political_power")], 1000)
                    self.assertEqual(facts[("NAM", "variable", "ADISCORD_economy_treasury")], 10000)
                    self.assertEqual(facts[("NAM", "variable", "NAM_projects_in_progress")], 0)
                    settled = dict(facts)
                    self.apply(block(project, "cancel_effect"), facts)
                    self.assertEqual(facts, settled)
            old = self.bind_field(self.decisions["NAM_econ_deep_drilling"])
            new = self.bind_field(self.decisions["NAM_econ_emergency_service"])
            facts = self.economy_facts()
            self.apply(block(old, "complete_effect"), facts)
            self.apply(block(old, "cancel_effect"), facts)
            self.apply(block(new, "complete_effect"), facts)
            paid = dict(facts)
            self.apply(block(old, "cancel_effect"), facts)
            self.apply(block(old, "remove_effect"), facts)
            self.assertEqual(facts, paid)
            # Ordinary repairs escrow money only; the optional PP receipt must not invent a refund.
            facts = self.economy_facts()
            facts[("67", "has_state_flag", "NAM_project_in_progress")] = True
            facts[("67", "variable", "NAM_project_deposit")] = 150
            facts[("NAM", "variable", "NAM_projects_in_progress")] = 1
            facts[("NAM", "variable", "ADISCORD_economy_treasury")] = 9850
            facts[("NAM", "numeric", "has_political_power")] = 975
            self.apply(self.effects["NAM_project_release"], facts, "67")
            self.assertEqual(facts[("NAM", "variable", "ADISCORD_economy_treasury")], 10000)
            self.assertEqual(facts[("NAM", "numeric", "has_political_power")], 975)
            self.assertEqual(facts[("NAM", "variable", "NAM_projects_in_progress")], 0)

    def test_grid_crews_wire_healthy_fields_and_generation_follows_live_supply(self):
        facts = self.postwar_facts()
        facts[("NAM", "has_completed_focus", "NAM_repair_depots")] = False
        condition = ("67", "variable", "NAM_field_condition")
        oil = ("67", "resource", "oil")
        contracts = ("67", "variable", "NAM_field_units")
        connected = ("67", "has_state_flag", "NAM_grid_feeder")
        facts[condition] = 100
        work = self.bind_field(self.decisions["NAM_econ_emergency_service"])
        facts[("NAM", "has_completed_focus", "NAM_pw_power_grid")] = False
        self.assertFalse(self.matches(block(work, "available"), facts))
        facts[("NAM", "has_completed_focus", "NAM_pw_power_grid")] = True
        self.assertTrue(self.matches(block(work, "available"), facts))
        with patch.dict(self.effects, {"NAM_oil_refresh": []}):
            self.apply(block(work, "complete_effect"), facts)
            self.assertFalse(facts.get(connected))
            self.apply(block(work, "remove_effect"), facts)
            self.assertTrue(facts[connected])
            self.assertFalse(self.matches(block(work, "available"), facts))

        facts[oil] = 7
        facts[("67", "variable", "NAM_field_applied_oil")] = 0
        field = self.effects["NAM_field_update_units"]
        for plant in (("NAM", "has_country_flag", "NAM_program_regional_power_commissioned"),
                      ("NAM", "has_country_flag", "NAM_dryriver_power_cooperative"),
                      ("688", "has_dynamic_modifier", "NAM_svetlogorsk_hydropower")):
            facts[plant] = True
            self.apply(field, facts, "67")
            self.apply(field, facts, "67")
            self.assertEqual((facts[oil], facts[contracts]), (97, 9))
            lost = (("688", "is_controlled_by", "NAM") if plant[0] == "688"
                    else ("NAM", "controls_state", "690"))
            facts[lost] = False
            self.apply(field, facts, "67")
            self.assertEqual((facts[oil], facts[contracts]), (87, 8))
            facts[lost] = True
            facts[plant] = False

        order = self.bind_field(self.decisions["NAM_grid_send_generator"])
        other = self.bind_field(self.decisions["NAM_grid_send_generator"], "689")
        fuel = ("NAM", "numeric", "has_fuel")
        facts[("689", "has_state_flag", "NAM_grid_feeder")] = True
        facts[fuel] = 14999
        self.assertFalse(self.matches(block(order, "custom_cost_trigger"), facts))
        with patch.dict(self.effects, {"NAM_oil_refresh": []}):
            self.apply(block(order, "complete_effect"), facts)
            self.assertEqual(facts[fuel], 14999)
            facts[fuel] = 30000
            self.apply(block(order, "complete_effect"), facts)
            self.assertFalse(self.matches(block(other, "available"), facts))
            self.apply(block(other, "complete_effect"), facts)
            self.apply(block(order, "complete_effect"), facts)
            self.assertEqual(facts[fuel], 15000)
            self.apply(field, facts, "67")
            self.assertEqual((facts[oil], facts[contracts]), (97, 9))
            facts[("NAM", "has_country_flag", "NAM_program_regional_power_commissioned")] = True
            facts[condition] = 50
            self.apply(field, facts, "67")
            self.assertEqual((facts[oil], facts[contracts]), (57, 5))
            facts[("NAM", "is_subject", "no")] = False
            self.assertFalse(self.matches(block(order, "cancel_trigger"), facts))
            self.apply(field, facts, "67")
            self.assertEqual(facts[oil], 57)
            facts[("NAM", "is_subject", "no")] = True
            burned = dict(facts)
            burned[("67", "has_state_flag", "NAM_wells_scorched")] = True
            self.assertTrue(self.matches(block(order, "cancel_trigger"), burned))
            self.apply(field, burned, "67")
            self.assertEqual((burned[oil], burned[contracts]), (47, 0))
            completed = dict(facts)
            self.apply(block(order, "remove_effect"), completed)
            self.apply(field, completed, "67")
            self.assertEqual((completed[oil], completed[contracts], completed[fuel]), (52, 4, 15000))
            facts[("67", "is_controlled_by", "NAM")] = False
            self.assertTrue(self.matches(block(order, "cancel_trigger"), facts))
            self.apply(block(order, "cancel_effect"), facts)
            self.apply(block(order, "remove_effect"), facts)
            self.apply(field, facts, "67")
            self.assertEqual((facts[oil], facts[contracts], facts[fuel]), (47, 0, 15000))
            self.assertTrue(self.matches(block(other, "available"), facts))

    def test_commissioning_a_real_power_source_restarts_already_wired_pumps(self):
        for decision, target in (("NAM_project_hydroelectric", "688"),
                                 ("NAM_program_regional_power", None),
                                 ("NAM_pw_rural_electrification", None)):
            with self.subTest(decision=decision):
                facts = self.postwar_facts()
                for state in ("67", "688", "689", "690", "719"):
                    facts[(state, "variable", "NAM_field_applied_oil")] = 64
                    facts[(state, "resource", "oil")] = 64
                facts[("67", "has_state_flag", "NAM_grid_feeder")] = True
                facts[("688", "variable", "fixture_building_slots_industrial_complex_yes")] = 2
                facts[("NAM", "variable", "NAM_oil_bonus_units")] = 0
                self.assertFalse(self.matches(self.triggers["NAM_grid_has_power"], facts))
                order = self.bind_field(self.decisions[decision], target) if target else self.decisions[decision]
                self.assertTrue(self.matches(block(order, "available"), facts))
                self.apply(block(order, "complete_effect"), facts)
                self.assertEqual(facts[("67", "resource", "oil")], 64)
                self.apply(block(order, "remove_effect"), facts)
                self.assertTrue(self.matches(self.triggers["NAM_grid_has_power"], facts))
                self.assertEqual(facts[("67", "resource", "oil")], 72)
                self.assertEqual(facts[("67", "variable", "NAM_field_units")], 7)
                self.assertEqual(facts[("689", "resource", "oil")], 64)

    def test_oil_damage_repair_and_expansion_change_real_resources_without_erasing_other_sources(self):
        facts = self.economy_facts()
        with patch.dict(self.effects, {"NAM_oil_refresh": []}):
            self.apply(self.effects["NAM_oil_initialize"], facts)
        for state, capacity, maximum in (("67", 5, 11), ("688", 1, 3), ("689", 3, 7), ("690", 2, 5), ("719", 1, 3)):
            with self.subTest(state=state):
                facts[("fixture", "previous_state")] = state
                oil = (state, "resource", "oil")
                facts[oil] = capacity * 8 + 7
                self.assertEqual(facts[(state, "variable", "NAM_field_max_capacity")], maximum)
                self.apply(self.effects["NAM_field_update_units"], facts, state)
                self.assertEqual(facts[oil], capacity * 8 + 7)
                facts[(state, "variable", "NAM_field_condition")] = 40
                self.apply(self.effects["NAM_field_update_units"], facts, state)
                self.assertEqual(facts[oil], capacity * 4 + 7)
                facts[(state, "is_controlled_by", "NAM")] = False
                self.apply(self.effects["NAM_field_update_units"], facts, state)
                self.assertEqual(facts[oil], capacity * 4 + 7)
                self.assertEqual(facts[(state, "variable", "NAM_field_units")], 0)
                facts[(state, "variable", "NAM_field_condition")] = 100
                facts[(state, "variable", "NAM_field_capacity")] = maximum
                self.apply(self.effects["NAM_field_update_units"], facts, state)
                self.assertEqual(facts[oil], maximum * 10 + 7)
                self.apply(self.effects["NAM_field_update_units"], facts, state)
                self.assertEqual(facts[oil], maximum * 10 + 7)

    def test_mines_and_dam_share_escrow_recheck_sites_and_settle_once(self):
        for kind, state, pp, cash, resource, delta in (
                ("hydroelectric", "688", 50, 1200, None, 2),
                ("chromium", "67", 30, 400, "chromium", 6),
                ("steel", "231", 40, 600, "steel", 12)):
            decision = self.bind_field(self.decisions["NAM_project_" + kind], state)
            for lost in (False, True):
                with self.subTest(kind=kind, lost=lost):
                    facts = self.postwar_facts()
                    facts[("fixture", "previous_state")] = state
                    facts[(state, "is_owned_by", "NAM")] = True
                    facts[(state, "is_controlled_by", "NAM")] = True
                    facts[(state, "variable", "fixture_building_slots_industrial_complex_yes")] = 2
                    self.assertTrue(self.matches(block(decision, "available"), facts))
                    money = ("NAM", "variable", "ADISCORD_economy_treasury")
                    political = ("NAM", "numeric", "has_political_power")
                    initial = (facts[money], facts[political])
                    for key, price in ((money, cash), (political, pp)):
                        short = dict(facts)
                        short[key] = price - 0.01
                        self.assertFalse(self.matches(block(decision, "custom_cost_trigger"), short))
                        before = dict(short)
                        self.apply(block(decision, "complete_effect"), short)
                        self.assertEqual(short, before)
                    self.apply(block(decision, "complete_effect"), facts)
                    self.assertEqual((facts[money], facts[political]), (initial[0] - cash, initial[1] - pp))
                    paid = dict(facts)
                    self.apply(block(decision, "complete_effect"), facts)
                    self.assertEqual(facts, paid)
                    facts[(state, "is_controlled_by", "NAM")] = not lost
                    self.apply(block(decision, "remove_effect"), facts)
                    if lost:
                        self.assertEqual((facts[money], facts[political]), initial)
                        self.assertEqual(facts.get((state, "resource", resource), 0), 0)
                    elif resource:
                        self.assertEqual(facts[(state, "resource", resource)], delta)
                        self.assertTrue(facts[(state, "has_state_flag", "NAM_" + kind + "_mine_expanded")])
                    else:
                        self.assertEqual(facts[(state, "building", "industrial_complex")], 2)
                        self.assertTrue(facts[(state, "has_dynamic_modifier", "NAM_svetlogorsk_hydropower")])
                    self.assertEqual(facts[("NAM", "variable", "NAM_projects_in_progress")], 0)
                    settled = dict(facts)
                    self.apply(block(decision, "remove_effect"), facts)
                    self.apply(block(decision, "cancel_effect"), facts)
                    self.assertEqual(facts, settled)

    def test_border_integration_thresholds_receipts_and_autonomy(self):
        state = "723"
        for name, pp, cash, compliance, resistance in (
                ("NAM_border_reconstruction", 35, 400, 65, 25),
                ("NAM_border_incorporation", 75, 500, 80, 20)):
            decision = self.bind_field(self.decisions[name], state)
            for outcome in ("success", "occupation", "subjugation", "cancel", "threshold"):
                with self.subTest(decision=name, outcome=outcome):
                    facts = self.postwar_facts()
                    facts[("fixture", "previous_state")] = state
                    facts[(state, "is_owned_by", "NAM")] = True
                    facts[(state, "is_controlled_by", "NAM")] = True
                    facts[(state, "has_resistance", "yes")] = True
                    facts[(state, "numeric", "compliance")] = compliance
                    facts[(state, "numeric", "resistance")] = resistance
                    for focus in ("NAM_border_administration", "NAM_border_security", "NAM_border_citizenship"):
                        facts[("NAM", "has_completed_focus", focus)] = True
                    self.assertTrue(self.matches(block(decision, "available"), facts))
                    money = ("NAM", "variable", "ADISCORD_economy_treasury")
                    political = ("NAM", "numeric", "has_political_power")
                    initial = (facts[money], facts[political])
                    for key, price in ((money, cash), (political, pp)):
                        poor = dict(facts)
                        poor[key] = price - 0.01
                        self.assertFalse(self.matches(block(decision, "custom_cost_trigger"), poor))
                        before = dict(poor)
                        self.apply(block(decision, "complete_effect"), poor)
                        self.assertEqual(poor, before)
                    self.apply(block(decision, "complete_effect"), facts)
                    self.assertEqual((facts[money], facts[political]), (initial[0] - cash, initial[1] - pp))
                    paid = dict(facts)
                    self.apply(block(decision, "complete_effect"), facts)
                    self.assertEqual(facts, paid)
                    if outcome == "occupation":
                        facts[(state, "is_controlled_by", "NAM")] = False
                    elif outcome == "subjugation":
                        facts[("NAM", "is_subject", "no")] = False
                    elif outcome == "threshold":
                        facts[(state, "numeric", "compliance")] = 79.999
                    callback = "cancel_effect" if outcome == "cancel" else "remove_effect"
                    self.apply(block(decision, callback), facts)
                    success = outcome == "success" or outcome == "threshold" and name == "NAM_border_reconstruction"
                    if success and name == "NAM_border_incorporation":
                        self.assertTrue(facts[(state, "is_core_of", "NAM")])
                        self.assertFalse(facts.get((state, "has_dynamic_modifier", "NAM_border_autonomous_district"), False))
                    elif success:
                        self.assertEqual(facts[(state, "numeric", "resistance")], 15)
                        self.assertGreater(facts[(state, "numeric", "compliance")], compliance)
                    else:
                        self.assertEqual((facts[money], facts[political]), initial)
                        self.assertFalse(facts.get((state, "is_core_of", "NAM"), False))
                    self.assertEqual(facts[("NAM", "variable", "NAM_projects_in_progress")], 0)
                    settled = dict(facts)
                    self.apply(block(decision, "remove_effect"), facts)
                    self.apply(block(decision, "cancel_effect"), facts)
                    self.assertEqual(facts, settled)
        facts = self.postwar_facts()
        facts[(state, "is_owned_by", "NAM")] = True
        facts[(state, "is_controlled_by", "NAM")] = True
        facts[("NAM", "has_completed_focus", "NAM_border_compacts")] = True
        agreement = self.bind_field(self.decisions["NAM_border_autonomy_agreement"], state)
        self.assertEqual(scalar(agreement, "cost"), "30")
        self.assertFalse(any(e.key == "days_remove" for e in agreement))
        self.assertTrue(self.matches(block(agreement, "available"), facts))
        busy = dict(facts)
        busy[(state, "has_state_flag", "NAM_project_in_progress")] = True
        self.assertFalse(self.matches(block(agreement, "available"), busy))
        self.apply(block(agreement, "complete_effect"), facts)
        self.assertTrue(facts[(state, "is_core_of", "NAM")])
        self.assertTrue(facts[(state, "has_dynamic_modifier", "NAM_border_autonomous_district")])
        settled = dict(facts)
        self.apply(block(agreement, "complete_effect"), facts)
        self.assertEqual(facts, settled)
        self.assertFalse(self.matches(block(agreement, "visible"), facts))

    def test_underground_settlement_hides_ui_refunds_once_and_blocks_late_events(self):
        category = block(parsed("common/decisions/categories/ADISCORD_nam_resource_war_categories.txt"), "NAM_underground")
        gui = block(block(parsed("common/scripted_guis/ADISCORD_NAM_scripted_gui.txt"), "scripted_gui"), "ADISCORD_NAM_basin_panel")
        map_gate = block(block(gui, "triggers"), "NAM_bw_underground_visible")
        for amnesty in (False, True):
            for deposit in (0, 100, 200):
                facts = self.postwar_facts()
                facts[("NAM", "has_global_flag", BASE + "_resolved")] = True
                facts[("NAM", "has_variable", "NAM_underground")] = True
                facts[("NAM", "variable", "NAM_underground")] = 80
                facts[("NAM", "variable", "NAM_underground_growth")] = 3
                facts[("NAM", "has_country_flag", "NAM_weber_amnesty")] = amnesty
                facts[("NAM", "has_country_flag", "NAM_ug_event_pending")] = True
                facts[("NAM", "variable", "NAM_weber_talks_deposit")] = deposit
                facts[("NAM", "has_variable", "NAM_weber_talks_deposit")] = deposit > 0
                self.assertFalse(self.matches(block(category, "visible"), facts))
                self.assertFalse(self.matches(map_gate, facts))
                money = ("NAM", "variable", "ADISCORD_economy_treasury")
                original = facts[money]
                self.apply(self.effects["NAM_underground_close_campaign"], facts)
                self.assertEqual(facts[money], original + deposit)
                self.assertFalse(facts[("NAM", "has_variable", "NAM_underground")])
                self.assertFalse(facts[("NAM", "has_country_flag", "NAM_ug_event_pending")])
                self.assertEqual(facts[("NAM", "has_country_flag", "NAM_weber_amnesty")], amnesty)
                settled = dict(facts)
                self.apply(self.effects["NAM_underground_close_campaign"], facts)
                self.assertEqual(facts, settled)
                for number in range(82, 88):
                    event = self.events[f"ADISCORD_nam_resource_war.{number}"]
                    self.assertFalse(self.matches(block(event, "trigger"), facts))
                    for option in (e.value for e in event if e.key == "option"):
                        self.apply(option, facts)
                        self.assertEqual(facts[money], settled[money])
                        self.assertFalse(facts[("NAM", "has_variable", "NAM_underground")])
                facts[("NAM", "variable", "NAM_underground_change")] = 10
                self.apply(self.effects["NAM_underground_add"], facts)
                self.assertFalse(facts[("NAM", "has_variable", "NAM_underground")])
        cleanup = self.effects["ADISCORD_nam_resource_war_clear_temporary_support"]
        self.assertTrue(any(e.key == "NAM_underground_close_campaign" for e in walk(cleanup)))

    def test_victory_factory_reparations_have_a_recipient_duration_and_terminal_cleanup(self):
        ideas = block(parsed("common/ideas/ADISCORD_nam_resource_war_ideas.txt"), "ideas")
        idea = block(block(ideas, "country"), "NAM_reparations_to_svetlogorye")
        target = block(idea, "targeted_modifier")
        self.assertEqual(scalar(target, "tag"), "NAM")
        self.assertEqual(float(scalar(target, "cic_to_target_factor")), 0.25)
        self.assertEqual(float(scalar(target, "mic_to_target_factor")), 0.25)
        self.assertEqual(scalar(block(idea, "allowed_civil_war"), "always"), "no")
        for payer in ("AZH", "EFL"):
            facts = {(payer, "exists", "yes"): True, (payer, "country_exists", "NAM"): True}
            selected = list(selected_effects(self.expand(self.effects["NAM_rw_apply_punishment"]), facts, payer))
            reparations = [e.value for scope, e in selected if scope == payer and e.key == "add_timed_idea"
                           and scalar(e.value, "idea") == "NAM_reparations_to_svetlogorye"]
            self.assertEqual(len(reparations), 1)
            self.assertEqual(scalar(reparations[0], "days"), "730")
            self.assertFalse(matches_conditions(block(idea, "cancel"), facts, payer))
            for key in ((payer, "country_exists", "NAM"), (payer, "has_war_with", "NAM")):
                terminal = dict(facts)
                terminal[key] = key[1] == "has_war_with"
                self.assertTrue(matches_conditions(block(idea, "cancel"), terminal, payer))
            paid = dict(facts)
            paid[(payer, "has_idea", "NAM_reparations_to_svetlogorye")] = True
            cleanup = list(selected_effects(self.expand(self.effects["NAM_rw_clear_punishment"]), paid, payer))
            self.assertEqual(sum(e.key == "remove_ideas" and e.value == "NAM_reparations_to_svetlogorye"
                                 for scope, e in cleanup if scope == payer), 1)
            for hook in ("on_add", "on_remove"):
                recipients = {scope for scope, e in selected_effects(block(idea, hook), facts, payer)
                              if e.key == "ADISCORD_economy_mark_dirty"}
                self.assertEqual(recipients, {payer, "NAM"})
        victory = read("common/scripted_effects/ADISCORD_nam_resource_war_effects.txt")
        self.assertIn("NAM_rw_punish_defeated_coalition = yes", victory)

    def test_border_settlement_reads_frozen_mandate_and_dam_callbacks_use_fixed_site(self):
        victory = self.effects["ADISCORD_nam_resource_war_resolve_nam_victory"]
        for balance, expected in ((-0.6, {"701", "720", "721", "722", "723", "727"}),
                                  (0.0, {"701", "720", "721", "722"}),
                                  (0.6, {"701", "720", "721", "722"})):
            facts = self.facts()
            facts[("NAM", "has_variable", "NAM_prewar_balance")] = True
            facts[("NAM", "variable", "NAM_prewar_balance")] = balance
            facts[("NAM", "power_balance_value", "NAM_ladder_bop")] = -balance
            selected = selected_effects(self.expand(victory), facts, "NAM")
            awards = {scope for scope, entry in selected if entry.key == "NAM_rw_award_border_state"}
            self.assertEqual(awards, expected)
        dam = self.decisions["NAM_project_hydroelectric"]
        for callback in ("complete_effect", "remove_effect", "cancel_effect"):
            self.assertFalse(any(e.key == "FROM" for e in walk(block(dam, callback))))
            self.assertTrue(any(e.key == "688" for e in walk(block(dam, callback))))

    def statist_allotment_facts(self, prefect=False, inspector=False, statute=False):
        facts = self.postwar_facts()
        facts[("NAM", "has_variable", "NAM_prewar_balance")] = True
        facts[("NAM", "variable", "NAM_prewar_balance")] = -0.5
        for name, completed in (("civil_service_exam", not prefect), ("appointed_prefects", prefect),
                                ("district_inspectorate", inspector), ("reconstruction_statute", statute)):
            facts[("NAM", "has_completed_focus", "NAM_" + name)] = completed
        for state in ("688", "690", "723"):
            facts[(state, "is_owned_by", "NAM")] = True
            facts[(state, "is_controlled_by", "NAM")] = True
            facts[(state, "is_core_of", "NAM")] = state != "723"
            facts[(state, "numeric", "infrastructure")] = 3
        return facts

    def test_statist_exam_spends_the_levy_on_a_local_road_or_a_single_serviced_site(self):
        decision = "NAM_pw_district_allotment"
        for course in ("NAM_civil_service_exam", "NAM_appointed_prefects"):
            self.assertEqual(scalar(block(self.postwar[course], "completion_reward"), "unlock_decision_tooltip"), decision)
        state = "688"
        order = self.bind_field(self.decisions[decision], state)
        cash = ("NAM", "variable", "ADISCORD_economy_treasury")
        pp = ("NAM", "numeric", "has_political_power")
        for road, inspector, surveyed in product((3, 5), (False, True), (False, True)):
            facts = self.statist_allotment_facts(inspector=inspector)
            facts[(state, "numeric", "infrastructure")] = road
            opened = (state, "has_state_flag", "NAM_pw_allotment_site_opened")
            facts[opened] = surveyed
            facts[pp] = 25
            available = road < 5 or not surveyed
            self.assertEqual(self.matches(block(order, "available"), facts), available)
            before = dict(facts)
            self.apply(block(order, "complete_effect"), facts)
            if not available:
                self.assertEqual(facts, before)
                continue
            self.assertEqual(facts[pp], 0)
            self.assertFalse(self.matches(block(self.decisions["NAM_district_audit"], "available"), facts))
            self.apply(block(order, "remove_effect"), facts)
            self.assertEqual(facts[cash], before[cash])
            self.assertEqual(facts.get((state, "building", "infrastructure"), 0), int(road < 5))
            self.assertEqual(facts.get((state, "reward", "building_slots"), 0), int(not surveyed and (road == 5 or inspector)))
            self.assertEqual(facts[opened], surveyed or road == 5 or inspector)
            self.assertFalse(facts[("NAM", "has_country_flag", "NAM_pw_civil_busy")])
            settled = dict(facts)
            self.apply(block(order, "remove_effect"), facts)
            self.apply(block(order, "cancel_effect"), facts)
            self.assertEqual(facts, settled)
        audit = self.decisions["NAM_district_audit"]
        for prefect in (False, True):
            facts = self.statist_allotment_facts(prefect=prefect)
            before = facts[cash]
            self.apply(block(audit, "complete_effect"), facts)
            self.assertFalse(self.matches(block(order, "available"), facts))
            self.apply(block(audit, "remove_effect"), facts)
            self.assertEqual(facts[cash], before + 250)
            self.assertTrue(self.matches(block(order, "available"), facts))

    def test_statist_prefects_use_the_current_roads_and_wait_for_the_district_fleet(self):
        state = "723"
        order = self.bind_field(self.decisions["NAM_pw_district_allotment"], state)
        modifier = "NAM_pw_district_fleet_called"
        modifiers = parsed("common/dynamic_modifiers/ADISCORD_dynamic_modifiers_NAM.txt")
        self.assertEqual(float(scalar(block(modifiers, modifier), "local_supplies")), -0.5)
        for roads, inspected in product((0, 3, 4, 5), (False, True)):
            facts = self.statist_allotment_facts(prefect=True)
            self.apply(block(order, "complete_effect"), facts)
            facts[("NAM", "has_completed_focus", "NAM_district_inspectorate")] = inspected
            facts[(state, "numeric", "infrastructure")] = roads
            timers = [scalar(e.value, "days") for _, e in selected_effects(
                self.expand(self.effects["NAM_pw_district_allotment_settle"]), facts, state) if e.key == "add_dynamic_modifier"]
            self.assertEqual(timers, ["90" if inspected else "180"] if roads else [])
            stock = ("NAM", "equipment", "motorized_equipment")
            before = facts.get(stock, 0)
            self.apply(block(order, "remove_effect"), facts)
            self.assertEqual(facts.get(stock, 0) - before, 120 if roads >= 4 else 80 if roads else 0)
            self.assertEqual(bool(facts.get((state, "has_dynamic_modifier", modifier))), bool(roads))
            self.assertFalse(self.matches(block(order, "available"), facts))
            if roads:
                facts[(state, "has_dynamic_modifier", modifier)] = False
                self.assertTrue(self.matches(block(order, "available"), facts))

    def test_statist_local_orders_preserve_each_receipt_through_devolution_and_loss(self):
        name = "NAM_pw_district_allotment"
        central, local = [self.bind_field(self.decisions[name], state) for state in ("688", "690")]
        pp = ("NAM", "numeric", "has_political_power")
        busy = ("NAM", "has_country_flag", "NAM_pw_civil_busy")
        for finish in ("remove_effect", "cancel_effect"):
            facts = self.statist_allotment_facts()
            initial = facts[pp]
            self.apply(block(central, "complete_effect"), facts)
            self.assertTrue(facts[busy])
            self.assertFalse(self.matches(block(local, "available"), facts))
            facts[("NAM", "has_completed_focus", "NAM_reconstruction_statute")] = True
            self.assertTrue(self.matches(block(local, "available"), facts))
            self.apply(block(local, "complete_effect"), facts)
            self.assertEqual(facts[pp], initial-50)
            for order in (central, local):
                paid = dict(facts)
                self.apply(block(order, "complete_effect"), facts)
                self.assertEqual(facts, paid)
            facts[("690", "has_dynamic_modifier", "NAM_border_autonomous_district")] = True
            self.assertTrue(self.matches(block(local, "cancel_trigger"), facts))
            self.apply(block(local, finish), facts)
            self.assertTrue(facts[busy])
            self.assertEqual(facts[pp], initial-25)
            facts[("688", "is_controlled_by", "NAM")] = False
            self.apply(block(central, finish), facts)
            self.assertEqual(facts[pp], initial)
            self.assertFalse(facts[busy])
            settled = dict(facts)
            for order in (central, local):
                self.apply(block(order, "remove_effect"), facts)
                self.apply(block(order, "cancel_effect"), facts)
            self.assertEqual(facts, settled)
        facts = self.statist_allotment_facts()
        for key, value in ((pp, 24.999), (("NAM", "variable", "NAM_grp_dist_support"), 29.999),
                           (("NAM", "variable", "NAM_prewar_balance"), -0.25),
                           (("NAM", "is_subject", "no"), False), (("688", "is_owned_by", "NAM"), False)):
            unavailable = {**facts, key: value}
            before = dict(unavailable)
            self.apply(block(central, "complete_effect"), unavailable)
            self.assertEqual(unavailable, before)

    def test_statist_archives_and_courts_work_at_home_and_under_the_treaty(self):
        archives = "NAM_pw_district_title_books"
        awards = "NAM_pw_civil_court_awards"
        projects = {"NAM_pw_provincial_records": "NAM_pw_register_district_titles",
                    "NAM_pw_administrative_courts": "NAM_pw_hear_district_appeals"}
        districts = {"67", "688", "689", "690", "700", "719", "701", "720", "721", "722", "723", "727"}
        for focus, decision in projects.items():
            self.assertEqual(scalar(block(self.postwar[focus], "completion_reward"), "unlock_decision_tooltip"), decision)
            self.assertEqual({e.value for e in block(self.decisions[decision], "targets")}, districts)
        self.assertEqual([scalar(self.decisions[name], "cost") for name in projects.values()], ["35", "25"])
        modifiers = parsed("common/dynamic_modifiers/ADISCORD_dynamic_modifiers_NAM.txt")
        self.assertEqual(int(scalar(block(modifiers, archives), "local_building_slots")), 1)
        self.assertEqual(float(scalar(block(modifiers, awards), "state_production_speed_buildings_factor")), 0.20)
        for state, core, occupied in (("688", True, False), ("723", False, True),
                                      ("701", True, False), ("727", False, False)):
            with self.subTest(state=state):
                facts = self.postwar_facts()
                facts[("NAM", "has_variable", "NAM_prewar_balance")] = True
                facts[("NAM", "variable", "NAM_prewar_balance")] = -0.5
                facts[(state, "is_owned_by", "NAM")] = True
                facts[(state, "is_controlled_by", "NAM")] = True
                facts[(state, "is_core_of", "NAM")] = core
                facts[(state, "has_resistance", "yes")] = occupied
                compliance = (state, "numeric", "compliance")
                resistance = (state, "numeric", "resistance")
                facts[compliance] = 65
                facts[resistance] = 26
                decision, session = [self.bind_field(self.decisions[name], state) for name in projects.values()]
                for registered in (False, True):
                    land = facts.copy()
                    if registered:
                        self.assertTrue(self.matches(block(decision, "available"), land))
                        self.apply(block(decision, "complete_effect"), land)
                        self.assertTrue(land[(state, "has_dynamic_modifier", archives)])
                        self.assertEqual(land[compliance], 65 + 5 * occupied)
                        self.assertFalse(self.matches(block(decision, "visible"), land))
                        checked = land.copy()
                        self.apply(block(decision, "complete_effect"), land)
                        self.assertEqual(land, checked)
                    self.assertTrue(self.matches(block(session, "available"), land))
                    effect = block(session, "complete_effect")
                    terms = [(scope, scalar(e.value, "days")) for scope, e in
                             selected_effects(self.expand(effect), land, "NAM") if e.key == "add_dynamic_modifier"]
                    self.assertEqual(terms, [(state, "180" if registered else "90")])
                    self.apply(effect, land)
                    self.assertTrue(land[(state, "has_dynamic_modifier", awards)])
                    self.assertEqual(land[compliance], 65 + 10 * (registered and occupied))
                    self.assertEqual(land[resistance], 26 - 5 * occupied)
                    self.assertEqual(land[(state, "is_core_of", "NAM")], core)
                    self.assertFalse(self.matches(block(session, "available"), land))
                    settled = land.copy()
                    self.apply(effect, land)
                    self.assertEqual(land, settled)
                    if occupied:
                        self.assertFalse(self.matches(self.triggers["NAM_border_citizenship_ready"], land, state))
                        agreement = self.bind_field(self.decisions["NAM_border_autonomy_agreement"], state)
                        self.apply(block(agreement, "complete_effect"), land)
                        self.assertTrue(land[(state, "is_core_of", "NAM")])
                        self.assertTrue(land[(state, "has_dynamic_modifier", "NAM_border_autonomous_district")])
                        for institution in (awards, archives):
                            self.assertFalse(self.matches(block(block(modifiers, institution), "enable"), land, state))

                for key, value in (((state, "is_owned_by", "NAM"), False), ((state, "is_controlled_by", "NAM"), False),
                                   (("NAM", "is_subject", "no"), False), (("NAM", "variable", "NAM_prewar_balance"), 0),
                                   ((state, "has_dynamic_modifier", "NAM_border_autonomous_district"), True)):
                    unavailable = {**facts, key: value}
                    for institution, project in ((archives, decision), (awards, session)):
                        self.assertFalse(self.matches(block(project, "available"), unavailable))
                        self.assertFalse(self.matches(block(block(modifiers, institution), "enable"), unavailable, state))
                        before = unavailable.copy()
                        self.apply(block(project, "complete_effect"), unavailable)
                        self.assertEqual(unavailable, before)
                        self.assertTrue(self.matches(block(block(modifiers, institution), "enable"), facts, state))
                    if key[-1] == "NAM_border_autonomous_district":
                        self.assertFalse(self.matches(block(session, "visible"), unavailable))
                        self.assertFalse(self.matches(block(decision, "visible"), unavailable))

    def test_border_citizenship_rechecks_exact_thresholds_and_route(self):
        state = "727"
        decision = self.bind_field(self.decisions["NAM_border_incorporation"], state)
        for compliance, resistance, security, expected in (
                (80, 20, True, True), (79.999, 20, True, False),
                (80, 20.001, True, False), (80, 20, False, False)):
            facts = self.postwar_facts()
            facts[(state, "is_owned_by", "NAM")] = True
            facts[(state, "is_controlled_by", "NAM")] = True
            facts[(state, "numeric", "compliance")] = compliance
            facts[(state, "numeric", "resistance")] = resistance
            facts[("NAM", "has_completed_focus", "NAM_border_security")] = security
            self.assertEqual(self.matches(block(decision, "available"), facts), expected)
        dynamic = block(parsed("common/dynamic_modifiers/ADISCORD_dynamic_modifiers_NAM.txt"), "NAM_border_autonomous_district")
        self.assertEqual(scalar(dynamic, "local_factories"), "-0.50")
        self.assertEqual(scalar(dynamic, "state_production_speed_buildings_factor"), "-0.50")
        self.assertEqual(scalar(dynamic, "local_manpower"), "-0.50")
        self.assertEqual(scalar(dynamic, "state_resources_factor"), "-0.35")

    def test_incident_missions_cannot_auto_succeed_and_timeout_rearms_only_once(self):
        for number in range(1, 6):
            self.assertEqual(scalar(self.events[f"ADISCORD_nam_crisis.{number}"], "timeout_days"), "22")
        for name in ("NAM_incident_countdown", "NAM_incident_response"):
            mission = self.missions[name]
            self.assertFalse(self.matches(block(mission, "available"), self.economy_facts()))
            self.assertEqual(scalar(mission, "selectable_mission"), "no")
        for fund in (False, True):
            facts = self.crisis_facts(3)
            facts[("NAM", "has_country_flag", "NAM_crisis_fund")] = fund
            facts[("NAM", "has_active_mission", "NAM_incident_response")] = True
            self.apply(self.effects["NAM_crisis_response_timeout"], facts)
            self.assertFalse(facts[("NAM", "has_country_flag", "NAM_crisis_open")])
            self.assertFalse(facts[("NAM", "has_country_flag", "NAM_crisis_fund")])
            self.assertTrue(facts[("NAM", "has_active_mission", "NAM_incident_countdown")])
            self.assertEqual(facts.get(("NAM", "reward", "stability"), 0), 0 if fund else -0.02)
            settled = dict(facts)
            self.apply(self.effects["NAM_crisis_response_timeout"], facts)
            self.assertEqual(facts, settled)
            self.apply(self.crisis_options(3)["a"], facts)
            self.assertEqual(facts, settled)
        draw = block(self.effects["NAM_crisis_draw"], "if")
        choices = block(draw, "random_list")
        for choice, extra in zip(choices, (0, 30, 60)):
            facts = self.economy_facts()
            facts[("NAM", "has_active_mission", "NAM_incident_countdown")] = True
            facts[("NAM", "variable", "days_mission_timeout@NAM_incident_countdown")] = 90
            self.apply(choice.value, facts)
            self.assertEqual(facts[("NAM", "variable", "days_mission_timeout@NAM_incident_countdown")], 90 + extra)

    def test_inventory_and_broadcasting_grant_slots_and_paid_radio_settles_once(self):
        grants = []
        for focuses in (self.focuses, self.postwar):
            grants.extend(name for name, focus in focuses.items()
                          if any(e.key == "ADISCORD_campaign_slot_grant" for e in walk(block(focus, "completion_reward"))))
        self.assertEqual(grants, ["NAM_inventory", "NAM_pw_civil_communications"])
        facts = self.independent_facts()
        facts[("NAM", "variable", "ADISCORD_available_campaign_slots")] = 1
        radio = block(block(parsed(f"common/decisions/{BASE}_decisions.txt"), "NAM_public_campaigns"), "NAM_radio_network")
        self.apply(block(radio, "complete_effect"), facts)
        self.assertEqual(facts[("NAM", "variable", "ADISCORD_available_campaign_slots")], 2)
        paid = dict(facts)
        self.apply(block(radio, "complete_effect"), facts)
        self.assertEqual(facts, paid)
        wages = self.decisions["NAM_campaign_wages_on_time"]
        self.apply(block(wages, "complete_effect"), facts)
        self.assertEqual(facts[("NAM", "variable", "ADISCORD_available_campaign_slots")], 2)
        paid = dict(facts)
        self.apply(block(wages, "complete_effect"), facts)
        self.assertEqual(facts, paid)

    def test_deep_drilling_ceiling_and_scorched_fields_block_payment(self):
        for suffix in ("deep_drilling", "emergency_service"):
            project = self.bind_field(self.decisions["NAM_econ_" + suffix])
            facts = self.economy_facts()
            facts[("67", "has_state_flag", "NAM_wells_scorched")] = True
            self.assertFalse(self.matches(block(project, "available"), facts))
            before = dict(facts)
            self.apply(block(project, "complete_effect"), facts)
            self.assertEqual(facts, before)
        project = self.bind_field(self.decisions["NAM_econ_deep_drilling"])
        for capacity, possible in ((10, True), (10.999, True), (11, False), (12, False)):
            facts = self.economy_facts()
            facts[("67", "variable", "NAM_field_capacity")] = capacity
            self.assertEqual(self.matches(block(project, "available"), facts), possible)

    def admin_projects(self):
        return {name: body for name, body in self.decisions.items() if name.startswith("NAM_admin_")}

    def admin_facts(self):
        facts = self.independent_facts()
        facts[("NAM", "fixture_power_balance", "NAM_ladder_bop")] = True
        facts[("NAM", "power_balance_value", "NAM_ladder_bop")] = 0
        facts[("688", "fixture_free_building_slots", "industrial_complex:1:yes")] = True
        for group in ("nam", "dist", "oil", "garr", "trade"):
            facts[("NAM", "variable", "NAM_grp_" + group + "_support")] = 70
        return facts

    def start_admin_project(self, project, facts):
        facts[("NAM", "numeric", "has_political_power")] -= int(scalar(project, "cost"))
        self.apply(block(project, "complete_effect"), facts)

    def test_admin_focus_unlocks_follow_the_exclusive_courses(self):
        owners = {
            "common_stores": "garrison_assembly", "compulsory_delivery": "vertical",
            "warehouse_inspection": "garrison_assembly", "tax_arrears": "tax_rolls",
            "transport_requisition": "garrison_assembly", "governor_levy": "emergency_writ",
            "voluntary_enrolment": "districts", "pay_local_arrears": "district_guarantees",
            "district_guard_contract": "garrison_assembly",
            "svetlogorsk_cooperative": "district_guarantees", "seal_appeal": "seal_courts",
        }
        projects = self.admin_projects()
        self.assertEqual(set(projects), {"NAM_admin_" + name for name in owners})
        for suffix, owner in owners.items():
            name = "NAM_admin_" + suffix
            reward = block(self.focuses["NAM_" + owner], "completion_reward")
            self.assertIn(name, {e.value for e in walk(reward) if e.key == "unlock_decision_tooltip"})
            facts = self.admin_facts()
            self.assertTrue(self.matches(block(projects[name], "visible"), facts), name)
            self.assertTrue(self.matches(block(projects[name], "available"), facts), name)
            facts[("NAM", "has_completed_focus", "NAM_" + owner)] = False
            self.assertFalse(self.matches(block(projects[name], "visible"), facts), name)
        budget = block(self.focuses["NAM_one_budget"], "completion_reward")
        self.assertIn("NAM_emergency_decrees", {e.value for e in walk(budget) if e.key == "unlock_decision_tooltip"})

    def test_admin_custom_prices_have_exact_boundaries_and_single_debit(self):
        for suffix, pp, cash in (("voluntary_enrolment", 30, 150), ("pay_local_arrears", 20, 200),
                                 ("district_guard_contract", 35, 200), ("svetlogorsk_cooperative", 30, 300)):
            name = "NAM_admin_" + suffix
            project = self.decisions[name]
            self.assertEqual(scalar(project, "cost"), "0")
            for political, treasury, affordable in ((pp - 0.001, cash, False), (pp, cash - 0.001, False), (pp, cash, True)):
                facts = self.admin_facts()
                facts[("NAM", "numeric", "has_political_power")] = political
                facts[("NAM", "variable", "ADISCORD_economy_treasury")] = treasury
                self.assertEqual(self.matches(block(project, "custom_cost_trigger"), facts), affordable, name)
                self.apply(block(project, "complete_effect"), facts)
                self.assertEqual(facts[("NAM", "numeric", "has_political_power")], political - (pp if affordable else 0))
                self.assertEqual(facts[("NAM", "variable", "ADISCORD_economy_treasury")], treasury - (cash if affordable else 0))
                self.assertEqual(facts.get(("NAM", "has_country_flag", name + "_paid"), False), affordable)
            facts = self.admin_facts()
            self.start_admin_project(project, facts)
            paid = dict(facts)
            self.apply(block(project, "complete_effect"), facts)
            self.assertEqual(facts, paid, name)
            self.assertEqual(facts[("NAM", "variable", "ADISCORD_economy_current_month_action_costs")], cash)

    def test_admin_orders_refund_both_currencies_once_on_every_exit(self):
        for name, project in self.admin_projects().items():
            for failed in (("NAM", "is_subject", "no"), ("NAM", "has_capitulated", "no"),
                           ("NAM", "fixture_power_balance", "NAM_ladder_bop")):
                for exit_name in ("remove_effect", "cancel_effect"):
                    facts = self.admin_facts()
                    self.start_admin_project(project, facts)
                    facts[failed] = False
                    self.assertTrue(self.matches(block(project, "cancel_trigger"), facts), name)
                    self.apply(block(project, exit_name), facts)
                    self.assertEqual(facts[("NAM", "numeric", "has_political_power")], 1000, name)
                    self.assertEqual(facts[("NAM", "variable", "ADISCORD_economy_treasury")], 10000, name)
                    self.assertFalse(facts[("NAM", "has_country_flag", name + "_paid")])
                    facts[failed] = True
                    settled = dict(facts)
                    self.apply(block(project, "remove_effect"), facts)
                    self.apply(block(project, "cancel_effect"), facts)
                    self.assertEqual(facts, settled, name)
                    self.assertFalse(any(key[1] in ("equipment", "reward", "building") for key in facts))

    def test_without_courts_trust_is_required_through_delivery_and_payroll_restores_it(self):
        for suffix, threshold in (("voluntary_enrolment", 50), ("district_guard_contract", 55), ("svetlogorsk_cooperative", 60)):
            name = "NAM_admin_" + suffix
            project = self.decisions[name]
            facts = self.admin_facts()
            facts[("NAM", "has_completed_focus", "NAM_seal_courts")] = False
            support = ("NAM", "variable", "NAM_grp_dist_support")
            facts[support] = threshold - 0.001
            self.assertFalse(self.matches(block(project, "available"), facts), name)
            self.apply(block(project, "complete_effect"), facts)
            self.assertFalse(facts.get(("NAM", "has_country_flag", name + "_paid"), False))
            facts[support] = threshold
            self.assertTrue(self.matches(block(project, "available"), facts), name)
            self.start_admin_project(project, facts)
            facts[support] = threshold - 0.001
            self.assertTrue(self.matches(block(project, "cancel_trigger"), facts), name)
            self.apply(block(project, "remove_effect"), facts)
            self.assertEqual(facts[("NAM", "variable", "ADISCORD_economy_treasury")], 10000)
            self.assertEqual(facts[("NAM", "numeric", "has_political_power")], 1000)
        payroll = self.decisions["NAM_admin_pay_local_arrears"]
        facts = self.admin_facts()
        facts[("NAM", "variable", "NAM_grp_dist_support")] = 10
        self.assertTrue(self.matches(block(payroll, "available"), facts))
        self.start_admin_project(payroll, facts)
        self.apply(block(payroll, "remove_effect"), facts)
        self.assertEqual(facts[("NAM", "variable", "NAM_grp_dist_support")], 22)

    def test_courts_secure_existing_district_orders_without_waiving_new_order_trust(self):
        programmes = (
            ("voluntary_enrolment", 50, 30, 150, ("NAM", "numeric", "has_manpower"), 6000),
            ("district_guard_contract", 55, 35, 200, ("NAM", "equipment", "infantry_equipment"), 6000),
            ("svetlogorsk_cooperative", 60, 30, 300, ("688", "building", "industrial_complex"), 1),
        )
        court = ("NAM", "has_completed_focus", "NAM_seal_courts")
        support = ("NAM", "variable", "NAM_grp_dist_support")
        for suffix, threshold, pp, cash, reward, amount in programmes:
            name = "NAM_admin_" + suffix
            project = self.decisions[name]
            for initial_court in (False, True):
                with self.subTest(programme=name, court_before_payment=initial_court):
                    facts = self.admin_facts()
                    facts[court] = initial_court
                    facts[support] = threshold
                    self.start_admin_project(project, facts)
                    self.assertTrue(facts[("NAM", "has_country_flag", name + "_paid")])
                    facts[court] = True
                    facts[support] = 0
                    self.assertFalse(self.matches(block(project, "cancel_trigger"), facts))
                    before_reward = facts.get(reward, 0)
                    self.apply(block(project, "remove_effect"), facts)
                    self.assertEqual(facts[reward] - before_reward, amount)
                    self.assertEqual(facts[("NAM", "numeric", "has_political_power")], 1000 - pp)
                    self.assertEqual(facts[("NAM", "variable", "ADISCORD_economy_treasury")], 10000 - cash)
                    self.assertFalse(facts[("NAM", "has_country_flag", name + "_paid")])
                    settled = dict(facts)
                    self.apply(block(project, "remove_effect"), facts)
                    self.apply(block(project, "cancel_effect"), facts)
                    self.assertEqual(facts, settled)
            facts = self.admin_facts()
            facts[court] = True
            facts[support] = threshold - 0.001
            self.assertFalse(self.matches(block(project, "available"), facts), name)
            before = dict(facts)
            self.apply(block(project, "complete_effect"), facts)
            self.assertEqual(facts, before, name)

    def test_court_protection_does_not_cover_failed_administration_or_local_sites(self):
        court = ("NAM", "has_completed_focus", "NAM_seal_courts")
        for suffix in ("voluntary_enrolment", "district_guard_contract", "svetlogorsk_cooperative"):
            name = "NAM_admin_" + suffix
            project = self.decisions[name]
            losses = [("NAM", "is_subject", "no"), ("NAM", "has_capitulated", "no"),
                      ("NAM", "fixture_power_balance", "NAM_ladder_bop")]
            if suffix == "svetlogorsk_cooperative":
                losses += [("NAM", "owns_state", "688"), ("NAM", "controls_state", "688"),
                           ("688", "fixture_free_building_slots", "industrial_complex:1:yes")]
            for loss, callback in product(losses, ("cancel_effect", "remove_effect")):
                with self.subTest(programme=name, loss=loss, callback=callback):
                    facts = self.admin_facts()
                    facts[court] = True
                    self.start_admin_project(project, facts)
                    facts[("NAM", "variable", "NAM_grp_dist_support")] = 0
                    facts[loss] = False
                    self.assertTrue(self.matches(block(project, "cancel_trigger"), facts))
                    self.apply(block(project, callback), facts)
                    self.assertEqual(facts[("NAM", "numeric", "has_political_power")], 1000)
                    self.assertEqual(facts[("NAM", "variable", "ADISCORD_economy_treasury")], 10000)
                    self.assertFalse(facts[("NAM", "has_country_flag", name + "_paid")])
                    self.assertFalse(any(key[1] in ("equipment", "reward", "building") for key in facts))
                    settled = dict(facts)
                    self.apply(block(project, "remove_effect"), facts)
                    self.apply(block(project, "cancel_effect"), facts)
                    self.assertEqual(facts, settled)

    def test_admin_deliveries_have_distinct_material_and_political_results(self):
        expected = {
            "common_stores": {("equipment", "support_equipment"): 100, ("numeric", "has_fuel"): 2000},
            "compulsory_delivery": {("equipment", "infantry_equipment"): 4500, ("variable", "NAM_grp_dist_support"): -6, ("variable", "NAM_grp_oil_support"): -3},
            "warehouse_inspection": {("equipment", "artillery_equipment"): 40, ("equipment", "support_equipment"): 90, ("variable", "NAM_grp_garr_support"): -4},
            "tax_arrears": {("variable", "ADISCORD_economy_treasury"): 350, ("variable", "NAM_grp_trade_support"): -3},
            "transport_requisition": {("equipment", "motorized_equipment"): 100, ("numeric", "has_fuel"): 1500, ("variable", "NAM_grp_dist_support"): -5},
            "governor_levy": {("variable", "ADISCORD_economy_treasury"): 400, ("variable", "NAM_grp_nam_support"): -5},
            "voluntary_enrolment": {("numeric", "has_manpower"): 6000},
            "pay_local_arrears": {("reward", "stability"): 0.02, ("variable", "NAM_grp_dist_support"): 12},
            "district_guard_contract": {("equipment", "infantry_equipment"): 6000, ("equipment", "support_equipment"): 60},
            "svetlogorsk_cooperative": {},
            "seal_appeal": {("variable", "NAM_grp_nam_support"): 4, ("variable", "NAM_grp_dist_support"): 8},
        }
        for suffix, deltas in expected.items():
            project = self.decisions["NAM_admin_" + suffix]
            facts = self.admin_facts()
            self.start_admin_project(project, facts)
            before = dict(facts)
            self.apply(block(project, "remove_effect"), facts)
            for key, delta in deltas.items():
                full_key = ("NAM", *key)
                self.assertAlmostEqual(facts[full_key] - before.get(full_key, 0), delta, msg=suffix)
            settled = dict(facts)
            self.apply(block(project, "remove_effect"), facts)
            self.apply(block(project, "cancel_effect"), facts)
            self.assertEqual(facts, settled, suffix)
            if suffix in ("compulsory_delivery", "warehouse_inspection", "transport_requisition", "governor_levy"):
                self.assertLess(facts[("NAM", "power_balance_value", "NAM_ladder_bop")], 0)
            if suffix in ("voluntary_enrolment", "pay_local_arrears", "district_guard_contract", "svetlogorsk_cooperative"):
                self.assertGreater(facts[("NAM", "power_balance_value", "NAM_ladder_bop")], 0)
            if suffix == "svetlogorsk_cooperative":
                self.assertEqual(facts[("688", "building", "industrial_complex")], 1)
                self.assertEqual(facts[("688", "reward", "building_slots")], 1)

    def test_cooperative_refunds_lost_site_but_general_orders_survive_war_and_exile(self):
        for name, project in self.admin_projects().items():
            facts = self.admin_facts()
            self.start_admin_project(project, facts)
            facts[("NAM", "has_global_flag", BASE + "_started")] = True
            facts[("NAM", "has_global_flag", BASE + "_resolved")] = True
            facts[("NAM", "has_global_flag", BASE + "_island_exile")] = True
            facts[("NAM", "owns_state", "688")] = False
            self.assertEqual(self.matches(block(project, "cancel_trigger"), facts), name.endswith("svetlogorsk_cooperative"))
        project = self.decisions["NAM_admin_svetlogorsk_cooperative"]
        for lost in (("NAM", "owns_state", "688"), ("NAM", "controls_state", "688"),
                     ("688", "fixture_free_building_slots", "industrial_complex:1:yes")):
            facts = self.admin_facts()
            self.start_admin_project(project, facts)
            facts[lost] = False
            self.apply(block(project, "remove_effect"), facts)
            self.assertEqual(facts[("NAM", "variable", "ADISCORD_economy_treasury")], 10000)
            self.assertEqual(facts[("NAM", "numeric", "has_political_power")], 1000)
            self.assertNotIn(("688", "building", "industrial_complex"), facts)
            facts[lost] = True
            self.assertTrue(self.matches(block(project, "available"), facts))
        self.assertEqual(scalar(project, "fire_only_once"), "no")

    def test_seal_appeals_moderate_both_extremes_without_crossing_the_centre(self):
        project = self.decisions["NAM_admin_seal_appeal"]
        key = ("NAM", "power_balance_value", "NAM_ladder_bop")
        for initial, final in ((-0.8, -0.7), (-0.11, -0.01), (-0.1, -0.1), (0, 0), (0.1, 0.1), (0.11, 0.01), (0.8, 0.7)):
            facts = self.admin_facts()
            facts[key] = initial
            self.start_admin_project(project, facts)
            self.apply(block(project, "remove_effect"), facts)
            self.assertAlmostEqual(facts[key], final)

    def test_admin_timeline_and_emergency_budget(self):
        for course in (("vertical", "emergency_writ"),
                       ("districts", "district_guarantees")):
            sequence = ("open_ledgers", *course, "tax_rolls", "one_budget", "supports_oil_compact", "pillar_arbitration", "seal_courts")
            days = sum(int(scalar(self.focuses["NAM_" + name], "cost")) * 7 for name in sequence)
            self.assertEqual(days, 189)
            self.assertLess(days + 14 + 21, 300)
        budget = block(block(parsed(f"common/decisions/{BASE}_decisions.txt"), "NAM_treasury"), "NAM_emergency_decrees")
        self.assertEqual(scalar(budget, "cost"), "50")
        facts = self.admin_facts()
        self.apply(block(budget, "complete_effect"), facts)
        self.assertEqual(facts[("NAM", "variable", "ADISCORD_economy_treasury")], 10500)
        self.assertEqual(facts[("NAM", "variable", "ADISCORD_economy_current_month_action_income")], 500)

    def independence_projects(self):
        source = parsed(f"common/decisions/{BASE}_decisions.txt")
        return {e.key: e.value for category in ("NAM_administration", "NAM_mobilisation", "NAM_restitution")
                for e in block(source, category) if e.key.startswith("NAM_ind_")}

    def independent_facts(self):
        facts = self.facts()
        facts[("NAM", "is_subject", "no")] = True
        facts[("NAM", "has_country_flag", "NAM_center_vanished")] = True
        facts[("NAM", "has_global_flag", BASE + "_started")] = False
        facts[("NAM", "has_global_flag", BASE + "_scheduled")] = True
        facts[("EFL", "exists", "yes")] = True
        facts[("NAM", "has_active_mission", "NAM_resource_war_deadline")] = True
        facts[("NAM", "variable", "days_mission_timeout@NAM_resource_war_deadline")] = 450
        for state in ("67", "689"):
            facts[(state, "is_owned_by", "NAM")] = True
            facts[(state, "is_controlled_by", "NAM")] = True
            facts[(state, "variable", "fixture_building_slots_industrial_complex_yes")] = 3
            facts[(state, "numeric", "infrastructure")] = 2
        return facts

    def test_independence_focuses_unlock_usable_programmes(self):
        expected = {
            "NAM_independence_day": {"NAM_ind_sovereign_collections"},
            "NAM_neutral_basin": {"NAM_ind_border_dossier"},
            "NAM_basin_is_ours": {"NAM_ind_defence_supply"},
            "NAM_provisional_statute": {"NAM_ind_statute_commissions", "NAM_ind_reservist_register"},
            "NAM_rom_address": {"NAM_campaign_our_own_word", "NAM_radio_network"},
        }
        for focus_id, names in expected.items():
            reward = block(self.focuses[focus_id], "completion_reward")
            facts = self.independent_facts()
            facts[("NAM", "has_completed_focus", "NAM_restitution_desk")] = False
            shown = selected_effects(self.expand(reward), facts, "NAM")
            self.assertEqual({e.value for _, e in shown if e.key == "unlock_decision_tooltip"}, names)
        projects = self.independence_projects()
        self.assertEqual(len(projects), 5)
        for name, project in projects.items():
            facts = self.independent_facts()
            facts[("NAM", "has_country_flag", "NAM_ind_defence_supply_authorised")] = True
            self.assertTrue(self.matches(block(project, "visible"), facts), name)
            self.assertTrue(self.matches(block(project, "available"), facts), name)
            self.assertFalse(self.matches(block(project, "cancel_trigger"), facts), name)
            self.assertGreater(int(scalar(project, "cost")), 0)
            self.assertFalse(any(e.key in ("custom_cost_text", "custom_cost_trigger") for e in project))
            self.assertFalse(any(e.key == "add_political_power" for _, e in selected_effects(self.expand(block(project, "complete_effect")), facts, "NAM")))
        address = block(self.focuses["NAM_rom_address"], "completion_reward")
        self.assertEqual(sum(e.key == "ADISCORD_campaign_slot_grant" for e in walk(address)), 0)
        self.assertEqual(scalar(block(address, "country_event"), "id"), BASE + ".70")

    def test_independent_institutions_survive_war_and_settlement_but_refund_subjugation(self):
        for name, project in self.independence_projects().items():
            if name == "NAM_ind_border_dossier":
                continue
            for phase in ("preparation", "war", "nam_victory", "compromise", "island_exile"):
                facts = self.independent_facts()
                if phase != "preparation":
                    facts[("NAM", "has_global_flag", BASE + "_scheduled")] = False
                    facts[("NAM", "has_global_flag", BASE + "_started")] = True
                if phase not in ("preparation", "war"):
                    facts[("NAM", "has_global_flag", BASE + "_resolved")] = True
                    facts[("NAM", "has_global_flag", BASE + "_" + phase)] = True
                if phase == "island_exile":
                    facts[("NAM", "owns_state", "688")] = False
                    facts[("NAM", "controls_state", "688")] = False
                self.assertTrue(self.matches(block(project, "available"), facts), (name, phase))
                self.assertFalse(self.matches(block(project, "cancel_trigger"), facts), (name, phase))
                for key in (("NAM", "is_subject", "no"), ("NAM", "has_capitulated", "no")):
                    ended = dict(facts)
                    ended[key] = False
                    self.assertFalse(self.matches(block(project, "available"), ended))
                    self.assertTrue(self.matches(block(project, "cancel_trigger"), ended))

    def test_independence_orders_refund_once_and_cannot_deliver_after_refund(self):
        for name, project in self.independence_projects().items():
            for first_exit in ("cancel_effect", "remove_effect"):
                with self.subTest(project=name, exit=first_exit):
                    facts = self.independent_facts()
                    facts[("NAM", "numeric", "has_political_power")] -= int(scalar(project, "cost"))
                    self.apply(block(project, "complete_effect"), facts)
                    receipt = ("NAM", "has_country_flag", name + "_paid")
                    self.assertTrue(facts[receipt])
                    facts[("NAM", "is_subject", "no")] = False
                    self.apply(block(project, first_exit), facts)
                    self.assertEqual(facts[("NAM", "numeric", "has_political_power")], 1000)
                    self.assertFalse(facts[receipt])
                    # Liberation and an ordinary reload preserve the settled receipt.
                    facts = dict(facts)
                    facts[("NAM", "is_subject", "no")] = True
                    self.apply(block(project, "remove_effect"), facts)
                    self.apply(block(project, "cancel_effect"), facts)
                    self.assertEqual(facts[("NAM", "numeric", "has_political_power")], 1000)
                    self.assertEqual(facts[("NAM", "variable", "ADISCORD_economy_treasury")], 10000)
                    self.assertFalse(any(key[1] == "equipment" for key in facts))

    def test_independence_deliveries_reach_nam_and_update_real_accounts(self):
        projects = self.independence_projects()
        for name, deltas in (
            ("NAM_ind_sovereign_collections", {("NAM", "variable", "ADISCORD_economy_treasury"): 250,
                                                ("NAM", "variable", "ADISCORD_economy_current_month_action_income"): 250}),
            ("NAM_ind_defence_supply", {("NAM", "equipment", "infantry_equipment"): 6000,
                                        ("NAM", "equipment", "support_equipment"): 60}),
            ("NAM_ind_statute_commissions", {("NAM", "variable", "NAM_grp_dist_support"): 6,
                                             ("NAM", "variable", "NAM_grp_nam_support"): 3,
                                             ("NAM", "reward", "stability"): 0.02}),
            ("NAM_ind_border_dossier", {("NAM", "variable", "days_mission_timeout@NAM_resource_war_deadline"): 60,
                                        ("NAM", "variable", "NAM_grp_trade_support"): 3}),
        ):
            facts = self.independent_facts()
            # The threshold dispatcher is tested separately; no threshold is crossed here.
            facts[("NAM", "has_global_flag", BASE + "_scheduled")] = name == "NAM_ind_border_dossier"
            before = dict(facts)
            self.apply(block(projects[name], "complete_effect"), facts)
            self.apply(block(projects[name], "remove_effect"), facts)
            for key, delta in deltas.items():
                self.assertAlmostEqual(facts[key] - before.get(key, 0), delta, msg=name)
            settled = dict(facts)
            self.apply(block(projects[name], "remove_effect"), facts)
            self.apply(block(projects[name], "cancel_effect"), facts)
            self.assertEqual(facts, settled, name)
        treasury = self.effects["NAM_receive_250"]
        self.assertEqual(scalar(treasury, "ADISCORD_economy_mark_dirty"), "yes")
        recruits = projects["NAM_ind_reservist_register"]
        self.assertEqual([e.value for e in walk(block(recruits, "remove_effect")) if e.key == "add_manpower"], ["4000"])

    def test_neutral_dossier_closes_with_its_claim_and_defence_is_not_a_bypass_reward(self):
        projects = self.independence_projects()
        dossier = projects["NAM_ind_border_dossier"]
        cases = (
            (("NAM", "has_global_flag", BASE + "_scheduled"), False),
            (("NAM", "has_global_flag", BASE + "_started"), True),
            (("NAM", "has_global_flag", BASE + "_resolved"), True),
            (("NAM", "has_country_flag", "NAM_rw_war_dispatched"), True),
            (("EFL", "exists", "yes"), False),
            (("NAM", "has_active_mission", "NAM_resource_war_deadline"), False),
        )
        for key, value in cases:
            facts = self.independent_facts()
            self.apply(block(dossier, "complete_effect"), facts)
            facts[key] = value
            deadline = facts[("NAM", "variable", "days_mission_timeout@NAM_resource_war_deadline")]
            self.assertFalse(self.matches(block(dossier, "available"), facts))
            self.assertTrue(self.matches(block(dossier, "cancel_trigger"), facts))
            self.apply(block(dossier, "remove_effect"), facts)
            self.assertEqual(facts[("NAM", "variable", "days_mission_timeout@NAM_resource_war_deadline")], deadline)
        defence = projects["NAM_ind_defence_supply"]
        facts = self.independent_facts()
        # Both focuses may be bypassed when the threat ends, without running either reward.
        self.assertFalse(self.matches(block(defence, "visible"), facts))
        reward = block(self.focuses["NAM_basin_is_ours"], "completion_reward")
        marker = next(e for e in walk(reward) if e.key == "set_country_flag" and e.value == "NAM_ind_defence_supply_authorised")
        self.apply([marker], facts)
        self.assertTrue(self.matches(block(defence, "visible"), facts))
        notes = block(block(parsed(f"common/decisions/{BASE}_decisions.txt"), "NAM_restitution"), "NAM_restitution_note")
        facts[("NAM", "has_completed_focus", "NAM_restitution_desk")] = False
        self.assertFalse(self.matches(block(notes, "visible"), facts))
        facts[("NAM", "has_completed_focus", "NAM_restitution_desk")] = True
        self.assertTrue(self.matches(block(notes, "visible"), facts))

    def test_independence_campaign_slot_survives_peace_and_returns_once_on_subjugation(self):
        campaign = block(block(parsed(f"common/decisions/{BASE}_decisions.txt"), "NAM_public_campaigns"), "NAM_campaign_our_own_word")
        shared = {e.key: e.value for e in parsed("common/scripted_triggers/ADISCORD_shared_action_triggers.txt")}
        with patch.dict(self.triggers, shared):
            facts = self.independent_facts()
            slots = ("NAM", "variable", "ADISCORD_available_campaign_slots")
            facts[slots] = 0
            self.assertFalse(self.matches(block(campaign, "available"), facts))
            facts[slots] = 1
            self.assertTrue(self.matches(block(campaign, "available"), facts))
            self.apply(block(campaign, "complete_effect"), facts)
            self.assertEqual(facts[slots], 0)
            for phase in ("started", "resolved", "island_exile"):
                facts[("NAM", "has_global_flag", BASE + "_" + phase)] = True
                self.assertFalse(self.matches(block(campaign, "cancel_trigger"), facts))
            facts[("NAM", "is_subject", "no")] = False
            self.assertTrue(self.matches(block(campaign, "cancel_trigger"), facts))
            self.apply(block(campaign, "cancel_effect"), facts)
            self.assertEqual(facts[slots], 1)
            self.apply(block(campaign, "remove_effect"), facts)
            self.apply(block(campaign, "cancel_effect"), facts)
            self.assertEqual(facts[slots], 1)

    def test_independence_programmes_fit_both_normal_focus_routes(self):
        projects = self.independence_projects()
        for course in ("NAM_neutral_basin", "NAM_basin_is_ours"):
            days = 0
            for focus_id in ("NAM_independence_day", course, "NAM_provisional_statute", "NAM_rom_address"):
                days += int(scalar(self.focuses[focus_id], "cost")) * 7
                unlocks = [e.value for e in block(self.focuses[focus_id], "completion_reward") if e.key == "unlock_decision_tooltip"]
                for name in unlocks:
                    if name in projects:
                        self.assertLess(days + int(scalar(projects[name], "days_remove")), 300, name)
            self.assertEqual(days, 70)
            self.assertLess(days + 60, 300)

    def colonial_projects(self):
        category = block(parsed(f"common/decisions/{BASE}_decisions.txt"), "NAM_colony")
        return {e.key: e.value for e in category if e.key.startswith("NAM_colonial_")}

    def colonial_facts(self):
        facts = self.facts(fuel=80000)
        facts[("NAM", "is_subject", "yes")] = True
        facts[("WRK", "exists", "yes")] = True
        facts[("NAM", "has_global_flag", BASE + "_started")] = False
        facts[("NAM", "has_variable", "NAM_underground")] = True
        facts[("NAM", "has_variable", "NAM_hidden_reserve")] = True
        facts[("NAM", "variable", "NAM_underground")] = 30
        facts[("700", "fixture_free_building_slots", "arms_factory:1:yes")] = True
        facts[("700", "variable", "fixture_building_slots_arms_factory_yes")] = 3
        return facts

    def test_colonial_concession_refunds_between_liberation_and_war_flag(self):
        category = block(parsed(f"common/decisions/{BASE}_decisions.txt"), "NAM_colony")
        decision = block(category, "NAM_wrk_trade_concession")
        for key in (("WRK", "exists", "yes"), ("NAM", "is_subject", "yes")):
            facts = self.colonial_facts()
            treasury = facts[("NAM", "variable", "ADISCORD_economy_treasury")]
            pp = facts[("NAM", "numeric", "has_political_power")]
            self.apply(block(decision, "complete_effect"), facts)
            self.assertEqual(facts[("NAM", "variable", "NAM_wrk_concession_deposit")], 200)
            facts[key] = False
            with patch.dict(self.effects, {"NAM_wrk_trade_refresh": []}):
                self.apply(block(decision, "remove_effect"), facts)
            self.apply(block(decision, "cancel_effect"), facts)
            self.apply(block(decision, "remove_effect"), facts)
            self.assertEqual(facts[("NAM", "variable", "ADISCORD_economy_treasury")], treasury)
            self.assertEqual(facts[("NAM", "numeric", "has_political_power")], pp - 50)
            self.assertFalse(facts.get(("NAM", "has_country_flag", "NAM_wrk_concession_active"), False))
            self.apply(block(decision, "complete_effect"), facts)
            self.assertEqual(facts[("NAM", "numeric", "has_political_power")], pp - 50)

    def test_colonial_fuel_trade_prices_and_echelon_settlement(self):
        colony = block(parsed(f"common/decisions/{BASE}_decisions.txt"), "NAM_colony")
        for name, price in (("NAM_wrk_fuel_shipment", 40000), ("NAM_wrk_emergency_echelon", 90000)):
            decision = block(colony, name)
            for fuel in (price - 0.01, price):
                facts = self.colonial_facts()
                facts[("NAM", "numeric", "has_fuel")] = fuel
                facts[("NAM", "variable", "NAM_wrk_trade_level")] = 0
                self.apply(self.effects["NAM_wrk_trade_refresh"], facts)
                self.assertEqual(self.matches(block(decision, "custom_cost_trigger"), facts), fuel == price)
                before = dict(facts)
                with patch.dict(self.effects, {"NAM_groups_refresh": []}):
                    self.apply(block(decision, "complete_effect"), facts)
                if fuel < price:
                    self.assertEqual(facts, before)
                else:
                    self.assertEqual(facts[("NAM", "numeric", "has_fuel")], 0)
                    if name == "NAM_wrk_fuel_shipment":
                        self.assertEqual(facts[("WRK", "numeric", "has_fuel")], price)

        decision = block(colony, "NAM_wrk_emergency_echelon")
        for cancelled in (False, True):
            facts = self.colonial_facts()
            facts[("NAM", "numeric", "has_fuel")] = 90000
            self.apply(block(decision, "complete_effect"), facts)
            self.assertEqual(facts[("NAM", "variable", "NAM_wrk_echelon_deposit")], 90000)
            if cancelled:
                facts[("WRK", "exists", "yes")] = False
            with patch.dict(self.effects, {"NAM_groups_refresh": []}):
                self.apply(block(decision, "remove_effect"), facts)
                self.apply(block(decision, "cancel_effect"), facts)
                self.apply(block(decision, "remove_effect"), facts)
            self.assertEqual(facts[("NAM", "numeric", "has_fuel")], 90000 if cancelled else 0)
            self.assertEqual(facts.get(("WRK", "numeric", "has_fuel"), 0), 0 if cancelled else 90000)
            self.assertEqual(facts.get(("NAM", "equipment", "infantry_equipment"), 0), 0 if cancelled else 6000)
            self.assertFalse(facts.get(("NAM", "has_variable", "NAM_wrk_echelon_deposit"), False))

    COLONIAL_CASH_ORDERS = {
        "NAM_colonial_artillery_contract": (0, 450, 35),
        "NAM_colonial_local_register": (50, 300, 28),
        "NAM_colonial_emergency_stocks": (0, 650, 21),
    }

    def test_colonial_cash_orders_pay_once_refund_and_deliver_material_packages(self):
        rewards = {
            "NAM_colonial_artillery_contract": {("equipment", "artillery_equipment"): 240, ("equipment", "support_equipment"): 160},
            "NAM_colonial_local_register": {("numeric", "has_manpower"): 12000, ("numeric", "army_experience"): 30},
            "NAM_colonial_emergency_stocks": {("equipment", "infantry_equipment"): 12000, ("equipment", "support_equipment"): 200, ("equipment", "motorized_equipment"): 300},
        }
        for name, (pp, money, days) in self.COLONIAL_CASH_ORDERS.items():
            decision = self.colonial_projects()[name]
            self.assertEqual(scalar(decision, "cost"), "0")
            self.assertEqual(int(scalar(decision, "days_remove")), days)
            pp_key = ("NAM", "numeric", "has_political_power")
            cash_key = ("NAM", "variable", "ADISCORD_economy_treasury")
            for shortage in ("cash", "pp", None):
                if shortage == "pp" and pp == 0:
                    continue
                facts = self.colonial_facts()
                facts[pp_key] = pp - (0.01 if shortage == "pp" else 0)
                facts[cash_key] = money - (0.01 if shortage == "cash" else 0)
                self.assertEqual(self.matches(block(decision, "custom_cost_trigger"), facts), shortage is None, name)
                for paid in (False, True):
                    preview_facts = dict(facts)
                    preview_facts[("NAM", "has_country_flag", name + "_paid")] = paid
                    preview = [
                        entry.value for _, entry in selected_effects(
                            self.expand(block(decision, "complete_effect")), preview_facts, "NAM"
                        ) if entry.key == "custom_effect_tooltip"
                    ]
                    self.assertEqual(preview.count(name + "_result_tt"), 1, (name, shortage, paid))
                before = dict(facts)
                self.apply(block(decision, "complete_effect"), facts)
                if shortage:
                    self.assertEqual(facts, before, name)
                    continue
                self.assertEqual((facts[pp_key], facts[cash_key]), (0, 0))
                paid = dict(facts)
                self.apply(block(decision, "complete_effect"), facts)
                self.assertEqual(facts, paid, (name, "duplicate debit"))
                for terminal in ("delivery", "collapse", "independence", "capitulation", "cancel"):
                    settled = dict(paid)
                    if terminal == "collapse":
                        settled[("WRK", "exists", "yes")] = False
                    elif terminal == "independence":
                        settled[("NAM", "is_subject", "yes")] = False
                    elif terminal == "capitulation":
                        settled[("NAM", "has_capitulated", "no")] = False
                    if terminal not in ("delivery", "cancel"):
                        self.assertTrue(self.matches(block(decision, "cancel_trigger"), settled))
                    self.apply(block(decision, "cancel_effect" if terminal == "cancel" else "remove_effect"), settled)
                    self.assertEqual((settled[pp_key], settled[cash_key]), (0, 0) if terminal == "delivery" else (pp, money))
                    for field, amount in rewards[name].items():
                        key = ("NAM", *field)
                        self.assertEqual(settled.get(key, 0) - paid.get(key, 0), amount if terminal == "delivery" else 0, (name, terminal, field))
                    after = dict(settled)
                    self.apply(block(decision, "remove_effect"), settled)
                    self.apply(block(decision, "cancel_effect"), settled)
                    self.assertEqual(settled, after, (name, terminal, "duplicate settlement"))

    def test_colonial_projects_unlock_before_collapse_and_recheck_delivery(self):
        projects = self.colonial_projects()
        self.assertEqual(len(projects), 12)
        for name, decision in projects.items():
            with self.subTest(project=name):
                focus_id = scalar(block(decision, "visible"), "has_completed_focus")
                reward = block(self.focuses[focus_id], "completion_reward")
                facts = self.colonial_facts()
                visible_reward = [e for _, e in selected_effects(self.expand(reward), facts, "NAM")]
                self.assertIn(name, [e.value for e in visible_reward if e.key == "unlock_decision_tooltip"])
                self.assertTrue(self.matches(block(decision, "visible"), facts))
                self.assertTrue(self.matches(block(decision, "available"), facts))
                self.assertFalse(self.matches(block(decision, "cancel_trigger"), facts))
                if name in self.COLONIAL_CASH_ORDERS or name in ("NAM_colonial_reserve_fund", "NAM_colonial_fuel_reserve"):
                    self.assertEqual(scalar(decision, "cost"), "0")
                    self.assertTrue(self.matches(block(decision, "custom_cost_trigger"), facts))
                else:
                    self.assertNotIn("custom_cost_text", [e.key for e in decision])
                    # The engine pays the native cost once; no script debits it again.
                    self.assertFalse(any(e.key == "add_political_power" for e in walk(block(decision, "complete_effect"))))
                settlement = block(block(decision, "remove_effect"), "if")
                requirements = []
                for condition in block(settlement, "limit"):
                    if condition.key == "custom_trigger_tooltip":
                        requirements.extend(e for e in condition.value if e.key != "tooltip")
                    else:
                        requirements.append(condition)
                self.assertEqual(scalar(requirements, "NAM_colonial_programme_operable"), "yes")
                for key in (
                    ("NAM", "has_country_flag", "NAM_center_vanished"),
                    ("NAM", "has_global_flag", "ADISCORD_vorkerland_collapse_wars_started"),
                ):
                    ended = dict(facts)
                    ended[key] = True
                    self.assertFalse(self.matches(block(decision, "visible"), ended))
                    self.assertFalse(self.matches(block(decision, "available"), ended))
                    self.assertTrue(self.matches(block(decision, "cancel_trigger"), ended))
                for key in (("WRK", "exists", "yes"), ("NAM", "has_capitulated", "no"), ("NAM", "is_subject", "yes")):
                    ended = dict(facts)
                    ended[key] = False
                    self.assertTrue(self.matches(block(decision, "cancel_trigger"), ended))

    def test_colonial_refunds_are_once_only_and_prevent_late_delivery(self):
        for name, decision in self.colonial_projects().items():
            for first_exit in ("cancel_effect", "remove_effect"):
                with self.subTest(project=name, exit=first_exit):
                    facts = self.colonial_facts()
                    cost = int(scalar(decision, "cost"))
                    facts[("NAM", "numeric", "has_political_power")] -= cost
                    self.apply(block(decision, "complete_effect"), facts)
                    receipt = ("NAM", "has_country_flag", name + "_paid")
                    self.assertTrue(facts[receipt])
                    facts[("NAM", "has_country_flag", "NAM_center_vanished")] = True
                    self.apply(block(decision, first_exit), facts)
                    self.assertFalse(facts[receipt])
                    self.assertEqual(facts[("NAM", "numeric", "has_political_power")], 1000)
                    # A second callback, including after ordinary save/load, cannot refund or deliver twice.
                    facts = dict(facts)
                    self.apply(block(decision, "cancel_effect"), facts)
                    self.apply(block(decision, "remove_effect"), facts)
                    self.assertEqual(facts[("NAM", "numeric", "has_political_power")], 1000)
                    self.assertFalse(any(key[1] == "equipment" for key in facts))

    def test_colonial_delivery_consumes_receipt_and_lost_harbour_cancels(self):
        projects = self.colonial_projects()
        for name, resource, expected in (
            ("NAM_colonial_rifle_contract", ("NAM", "equipment", "infantry_equipment"), 4500),
            ("NAM_colonial_fuel_reserve", ("NAM", "variable", "NAM_hidden_fuel"), 40000),
        ):
            decision = projects[name]
            facts = self.colonial_facts()
            self.apply(block(decision, "complete_effect"), facts)
            self.apply(block(decision, "remove_effect"), facts)
            self.assertEqual(facts[resource], expected)
            self.apply(block(decision, "remove_effect"), facts)
            self.apply(block(decision, "cancel_effect"), facts)
            self.assertEqual(facts[resource], expected)
            self.assertEqual(facts[("NAM", "numeric", "has_political_power")], 975 if name == "NAM_colonial_fuel_reserve" else 1000)
        factory = projects["NAM_colonial_workshops"]
        self.assertEqual(scalar(factory, "fire_only_once"), "no")
        self.assertEqual(scalar(factory, "days_re_enable"), "120")
        for condition in ("owns_state", "controls_state"):
            facts = self.colonial_facts()
            facts[("NAM", condition, "700")] = False
            self.assertFalse(self.matches(block(factory, "available"), facts))
            self.assertTrue(self.matches(block(factory, "cancel_trigger"), facts))
            limit = block(block(block(factory, "remove_effect"), "if"), "limit")
            facts[("NAM", "has_country_flag", "NAM_colonial_workshops_paid")] = True
            self.assertFalse(self.matches(limit, facts))

    def test_colonial_workshop_refunds_when_another_project_fills_the_site(self):
        factory = self.colonial_projects()["NAM_colonial_workshops"]
        self.assertEqual(sum(e.key == "free_building_slots" for e in walk(factory)), 3)
        for entry in walk(factory):
            if entry.key == "free_building_slots":
                self.assertEqual([e.value for e in entry.value if not e.key], ["size", ">", "0"])
        facts = self.colonial_facts()
        for slots in (1, 2, 3, 10):
            facts[("700", "variable", "fixture_building_slots_arms_factory_yes")] = slots
            self.assertTrue(self.matches(block(factory, "available"), facts))
        facts[("NAM", "numeric", "has_political_power")] -= 60
        self.apply(block(factory, "complete_effect"), facts)
        facts[("700", "fixture_free_building_slots", "arms_factory:1:yes")] = False
        facts[("700", "variable", "fixture_building_slots_arms_factory_yes")] = 0
        self.assertFalse(self.matches(block(factory, "available"), facts))
        self.assertTrue(self.matches(block(factory, "cancel_trigger"), facts))
        self.apply(block(factory, "remove_effect"), facts)
        self.assertEqual(facts[("NAM", "numeric", "has_political_power")], 1000)
        self.assertFalse(facts[("NAM", "has_country_flag", "NAM_colonial_workshops_paid")])

    def test_colonial_concession_enters_weekly_budget_without_a_second_monthly_payment(self):
        modifier = block(parsed("common/dynamic_modifiers/ADISCORD_dynamic_modifiers_NAM.txt"), "NAM_wrk_concession_income")
        self.assertEqual(scalar(modifier, "ADISCORD_economy_weekly_income"), "NAM_wrk_trade_weekly_income")
        budget = block(parsed("common/scripted_effects/ADISCORD_economy_effects.txt"), "ADISCORD_economy_calculate_weekly_budget")
        for level in range(4):
            with self.subTest(trade_level=level):
                facts = self.colonial_facts()
                facts[("NAM", "variable", "NAM_wrk_trade_level")] = level
                facts[("NAM", "variable", "ADISCORD_economy_treasury")] = 123
                self.apply(self.effects["NAM_wrk_trade_refresh"], facts)
                self.assertFalse(facts.get(("NAM", "has_dynamic_modifier", "NAM_wrk_concession_income"), False))
                facts[("NAM", "has_country_flag", "NAM_wrk_concession_active")] = True
                self.apply(self.effects["NAM_wrk_trade_refresh"], facts)
                self.assertTrue(facts[("NAM", "has_dynamic_modifier", "NAM_wrk_concession_income")])
                self.assertTrue(self.matches(block(modifier, "enable"), facts))
                monthly = 40 + 20 * level
                weekly = facts[("NAM", "variable", "NAM_wrk_trade_weekly_income")]
                self.assertAlmostEqual(weekly * 52, monthly * 12)
                facts[("NAM", "variable", "ADISCORD_economy_final_weekly_income_bonus")] = weekly
                facts[("NAM", "variable", "ADISCORD_economy_monthly_income")] = 0
                facts[("NAM", "variable", "ADISCORD_economy_monthly_expenses")] = 0
                facts[("NAM", "variable", "ADISCORD_economy_inflation_delta_temp")] = 0
                self.apply(budget, facts)
                self.assertAlmostEqual(facts[("NAM", "variable", "ADISCORD_economy_weekly_income")], weekly)
                self.apply(self.effects["NAM_colony_monthly"], facts)
                self.assertEqual(facts[("NAM", "variable", "ADISCORD_economy_treasury")], 123)
                with patch.dict(self.effects, {name: [] for name in ("NAM_refresh_garrison", "NAM_refresh_navy", "NAM_refresh_air")}):
                    self.apply(self.effects["NAM_colony_close"], facts)
                self.assertFalse(facts[("NAM", "has_dynamic_modifier", "NAM_wrk_concession_income")])
                self.assertFalse(facts[("NAM", "has_country_flag", "NAM_wrk_concession_active")])
                self.assertTrue(self.matches(block(modifier, "remove_trigger"), facts))

    def test_colonial_propaganda_opens_early_without_bypass_unlocks(self):
        campaigns = block(parsed(f"common/decisions/{BASE}_decisions.txt"), "NAM_colonial_campaigns")
        early = {
            "NAM_campaign_every_seal_counts": "NAM_inventory",
            "NAM_campaign_ladder_holds": "NAM_imperial_gendarmes",
            "NAM_campaign_answer_leaflets": "NAM_colonial_watch",
        }
        for name, focus_id in early.items():
            facts = self.colonial_facts()
            for key in tuple(facts):
                if key[1] == "has_completed_focus":
                    facts[key] = False
            facts[("NAM", "has_completed_focus", focus_id)] = True
            decision = block(campaigns, name)
            self.assertTrue(self.matches(block(decision, "visible"), facts), name)
            facts[("NAM", "variable", "ADISCORD_available_campaign_slots")] = 0
            # The shared slot predicate is supplied explicitly by the test expander.
            available = block(decision, "available")
            shared = {e.key: e.value for e in parsed("common/scripted_triggers/ADISCORD_shared_action_triggers.txt")}
            with patch.dict(self.triggers, shared):
                self.assertFalse(self.matches(available, facts), name)
                facts[("NAM", "variable", "ADISCORD_available_campaign_slots")] = 1
                self.assertTrue(self.matches(available, facts), name)
            facts[("NAM", "has_country_flag", "NAM_center_vanished")] = True
            self.assertFalse(self.matches(block(decision, "visible"), facts), name)
        inventory = block(self.focuses["NAM_inventory"], "completion_reward")
        self.assertEqual(sum(e.key == "ADISCORD_campaign_slot_grant" for e in walk(inventory)), 1)
        guard = block(block(parsed(f"common/decisions/{BASE}_decisions.txt"), "NAM_underground"), "NAM_colonial_pipeline_guard")
        facts = self.colonial_facts()
        self.assertFalse(self.matches(block(guard, "visible"), facts))
        facts[("NAM", "has_country_flag", "NAM_pipeline_guard_authorised")] = True
        facts[("NAM", "has_country_flag", "NAM_center_vanished")] = True
        self.assertTrue(self.matches(block(guard, "visible"), facts))

    def test_counterpropaganda_returns_its_slot_once_on_every_exit(self):
        campaigns = block(parsed(f"common/decisions/{BASE}_decisions.txt"), "NAM_colonial_campaigns")
        campaign = block(campaigns, "NAM_campaign_answer_leaflets")
        shared = {e.key: e.value for e in parsed("common/scripted_triggers/ADISCORD_shared_action_triggers.txt")}
        with patch.dict(self.triggers, shared):
            for exit_name in ("remove_effect", "cancel_effect"):
                facts = self.colonial_facts()
                slot = ("NAM", "variable", "ADISCORD_available_campaign_slots")
                facts[slot] = 1
                self.apply(block(campaign, "complete_effect"), facts)
                self.assertEqual(facts[slot], 0)
                # Colonial campaigns close when the metropole collapses.
                facts[("NAM", "has_country_flag", "NAM_center_vanished")] = True
                self.assertTrue(self.matches(block(campaign, "cancel_trigger"), facts))
                facts[("NAM", "has_country_flag", "NAM_weber_amnesty")] = True
                self.assertTrue(self.matches(block(campaign, "cancel_trigger"), facts))
                self.apply(block(campaign, exit_name), facts)
                self.assertEqual(facts[slot], 1)
                self.apply(block(campaign, "remove_effect"), facts)
                self.apply(block(campaign, "cancel_effect"), facts)
                self.assertEqual(facts[slot], 1)

    def test_security_programmes_change_the_reported_growth_only_while_active(self):
        monthly = block(self.effects["NAM_underground_monthly"], "if")
        names = ("NAM_disrupt_print_supply", "NAM_colonial_pipeline_guard", "NAM_campaign_answer_leaflets")
        rules = [e for e in monthly if e.key == "if" and any(n in repr(e) for n in names)]
        self.assertEqual(len(rules), 3)
        for flags in product((False, True), repeat=3):
            facts = {("NAM", "has_decision", name): active for name, active in zip(names, flags)}
            selected = [e for _, e in selected_effects(rules, facts, "NAM")]
            delta = sum(int(scalar(e.value, "value")) for e in selected if e.key == "add_to_temp_variable")
            self.assertEqual(delta, sum(change for change, active in zip((-3, -2, -2), flags) if active))
        snapshot = next(e for e in monthly if e.key == "set_variable")
        self.assertTrue(all(monthly.index(e) < monthly.index(snapshot) for e in rules))

    def test_colonial_route_timing_includes_the_paid_response(self):
        startup = parsed("common/on_actions/01_ADISCORD_vorkerland_collapse_on_actions.txt")
        collapse = next(e.value for e in walk(startup) if e.key == "country_event"
                        and scalar(e.value, "id") == "ADISCORD_vorkerland_phase.1")
        deadline = int(scalar(collapse, "days"))
        archive = self.colonial_projects()["NAM_colonial_archive_transfer"]
        for quota, security, centre in product(
                ("deliver_the_quota", "concealed_reserve"), ("imperial_gendarmes", "oilfield_militia"),
                ("commissioner_plan", "second_ledger")):
            routes = (
                ("metropolitan_quota", quota, "wrk_trade_house", "wrk_return_cargo", "metropolitan_depots"),
                ("colonial_watch", security, "pipeline_patrols", "print_shop_raid", "colony_order"),
                ("centre_hourglass", centre, "metropolitan_instructors" if centre == "commissioner_plan" else "quiet_officer_lists",
                 "sand_runs_out", "last_centre_register"),
            )
            for order in permutations(routes):
                route = ["inventory"] + [name for chain in order for name in chain] + ["letters_to_the_centre"]
                complete = set()
                day = 0
                for name in route:
                    focus_id = "NAM_" + name
                    focus = self.focuses[focus_id]
                    for group in (e.value for e in focus if e.key == "prerequisite"):
                        self.assertTrue(any(e.value in complete for e in group), focus_id)
                    day += int(scalar(focus, "cost")) * 7
                    complete.add(focus_id)
                self.assertEqual(day, 329)
                self.assertEqual(day + int(scalar(archive, "days_remove")), 343)
                self.assertLess(day + int(scalar(archive, "days_remove")), deadline)
        letters = self.focuses["NAM_letters_to_the_centre"]
        self.assertEqual([scalar(e.value, "focus") for e in letters if e.key == "prerequisite"],
                         ["NAM_metropolitan_depots", "NAM_colony_order", "NAM_last_centre_register"])

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

    def test_print_shop_focus_opens_two_paid_underground_operations(self):
        reward = block(self.focuses["NAM_print_shop_raid"], "completion_reward")
        self.assertEqual(scalar(reward, "add_political_power"), "35")
        unlocks = [e.value for e in reward if e.key == "unlock_decision_tooltip"]
        self.assertEqual(unlocks, ["NAM_disrupt_print_supply", "NAM_intercept_underground_couriers"])
        self.assertNotIn("NAM_underground", repr(reward))
        decisions = block(parsed(f"common/decisions/{BASE}_decisions.txt"), "NAM_underground")
        for name, cost in zip(unlocks, (25, 40)):
            decision = block(decisions, name)
            self.assertEqual(scalar(decision, "cost"), str(cost))
            self.assertEqual(scalar(block(decision, "visible"), "has_completed_focus"), "NAM_print_shop_raid")
            self.assertFalse(any(e.key == "add_political_power" for e in walk(decision)))
        russian = (ROOT / f"localisation/russian/{BASE}_l_russian.yml").read_bytes()
        self.assertTrue(russian.startswith(b"\xef\xbb\xbf"))
        self.assertIn(' NAM_print_shop_raid:0 "Найти чернила будущего восстания"', russian.decode("utf-8-sig"))

    def test_print_operations_close_when_the_network_or_campaign_phase_ends(self):
        decisions = block(parsed(f"common/decisions/{BASE}_decisions.txt"), "NAM_underground")
        control = block(decisions, "NAM_disrupt_print_supply")
        self.assertEqual(scalar(control, "days_remove"), "60")
        for amnesty, started, resolved, owns_capital, operable in product((False, True), repeat=5):
            facts = self.facts()
            facts[("NAM", "has_country_flag", "NAM_weber_amnesty")] = amnesty
            facts[("NAM", "has_global_flag", BASE + "_started")] = started
            facts[("NAM", "has_global_flag", BASE + "_resolved")] = resolved
            facts[("NAM", "owns_state", "688")] = owns_capital
            facts[("NAM", "has_capitulated", "no")] = operable
            facts[("NAM", "has_variable", "NAM_underground")] = True
            facts[("NAM", "variable", "NAM_underground")] = 12
            expected = not amnesty and not started and not resolved and owns_capital and operable
            for name in ("NAM_disrupt_print_supply", "NAM_intercept_underground_couriers"):
                self.assertEqual(self.matches(block(block(decisions, name), "available"), facts), expected)
            self.assertEqual(self.matches(block(control, "cancel_trigger"), facts), not expected)
        facts = self.facts()
        facts[("NAM", "has_global_flag", BASE + "_started")] = False
        facts[("NAM", "has_variable", "NAM_underground")] = True
        facts[("NAM", "variable", "NAM_underground")] = 0
        for name in ("NAM_disrupt_print_supply", "NAM_intercept_underground_couriers"):
            self.assertFalse(self.matches(block(block(decisions, name), "available"), facts))

    def test_print_control_uses_active_decision_and_courier_raids_have_a_tradeoff(self):
        monthly = block(self.effects["NAM_underground_monthly"], "if")
        control = next(e for e in monthly if e.key == "if" and "NAM_disrupt_print_supply" in repr(e))
        for active in (False, True):
            facts = {("NAM", "has_decision", "NAM_disrupt_print_supply"): active}
            selected = [e for _, e in selected_effects([control], facts, "NAM")]
            delta = sum(int(scalar(e.value, "value")) for e in selected if e.key == "add_to_temp_variable")
            self.assertEqual(delta, -3 if active else 0)
        snapshot = next(e for e in monthly if e.key == "set_variable")
        self.assertLess(monthly.index(control), monthly.index(snapshot))
        self.assertEqual(scalar(snapshot.value, "var"), "NAM_underground_growth")
        decisions = block(parsed(f"common/decisions/{BASE}_decisions.txt"), "NAM_underground")
        raid = block(decisions, "NAM_intercept_underground_couriers")
        self.assertEqual(scalar(raid, "days_re_enable"), "60")
        payload = block(block(raid, "complete_effect"), "hidden_effect")
        self.assertEqual(scalar(block(payload, "set_temp_variable"), "value"), "-12")
        self.assertEqual(scalar(payload, "NAM_underground_add"), "yes")
        self.assertEqual(scalar(block(payload, "add_to_variable"), "var"), "NAM_grp_dist_support")
        self.assertEqual(scalar(block(payload, "add_to_variable"), "value"), "-4")
        self.assertEqual(scalar(payload, "NAM_groups_refresh"), "yes")

    def test_manual_nam_icons_do_not_require_archived_originals(self):
        import tempfile
        from tools.builders import build_adiscord_nam_focus_icons as icons

        records = json.loads(read("tools/assets/source/focus_icons/NAM/focus_art_prompts.json"))
        focus_ids = tuple(
            entry["focus_id"] for entry in records["focus_compositions"]
            if entry.get("export_runtime", True) is False
        )
        self.assertTrue(focus_ids)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / icons.MANIFEST
            manifest.parent.mkdir(parents=True)
            manifest.write_text(json.dumps({"focus_compositions": [{
                "focus_id": focus_id,
                "export_runtime": False,
                "file": "missing_original.png",
            } for focus_id in focus_ids]}), encoding="utf-8")
            for focus_id in focus_ids:
                runtime = root / icons.OUTPUT / f"GFX_focus_{focus_id}.png"
                runtime.parent.mkdir(parents=True, exist_ok=True)
                runtime.write_bytes(b"manual runtime image")
            with patch.object(icons, "ROOT", root):
                self.assertEqual(icons.expected_outputs(), {})
                self.assertEqual(icons.expected_outputs(), {})
            for focus_id in focus_ids:
                runtime = root / icons.OUTPUT / f"GFX_focus_{focus_id}.png"
                self.assertEqual(runtime.read_bytes(), b"manual runtime image")
        manifest = json.loads(read("tools/assets/source/focus_icons/NAM/focus_art_prompts.json"))
        registry = json.loads(read("tools/data/generated_output_owners.json"))
        family = next(e for e in registry["families"] if e["id"] == "nam_focus_icons")
        for focus_id in focus_ids:
            entry = next(e for e in manifest["focus_compositions"] if e["focus_id"] == focus_id)
            self.assertIs(entry["export_runtime"], False)
            self.assertNotIn(f"gfx/interface/goals/NAM/GFX_focus_{focus_id}.png", family["output_globs"])

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

    def agreement_facts(self, number=1):
        facts = self.independent_facts()
        facts[("NAM", "has_country_flag", "NAM_independence_declared")] = True
        facts[("NAM", "has_country_flag", "NAM_groups_initialized")] = True
        facts[("NAM", "has_variable", "NAM_agreement_current")] = True
        facts[("NAM", "variable", "NAM_agreement_current")] = number
        facts[("NAM", "variable", "NAM_agreement_progress")] = 0
        facts[("NAM", "variable", "NAM_agreement_target")] = 2
        facts[("NAM", "has_active_mission", "NAM_agreement_deadline")] = True
        for group in ("nam", "oil", "dist", "garr", "trade"):
            facts[("NAM", "variable", f"NAM_grp_{group}_support")] = 50
            facts[("NAM", "variable", f"NAM_grp_{group}_influence")] = 20
        return facts

    def test_agreement_missions_are_visible_beside_their_paid_programmes(self):
        categories = parsed(f"common/decisions/categories/{BASE}_categories.txt")
        category = block(categories, "NAM_national_programmes")
        decisions = parsed(f"common/decisions/{BASE}_decisions.txt")
        programmes = block(decisions, "NAM_national_programmes")
        for name in ("NAM_agreement_deadline", "NAM_agreement_crisis"):
            mission = block(programmes, name)
            self.assertTrue(mission)
            self.assertEqual(sum(e.key == name for e in walk(decisions)), 1)
            self.assertEqual(scalar(mission, "priority"), "100")
            for active in (False, True):
                facts = {("NAM", "has_active_mission", name): active}
                self.assertEqual(self.matches(block(mission, "visible"), facts), active)
                self.assertEqual(self.matches(block(category, "visible"), facts), active)

        facts = self.agreement_facts()
        facts[("NAM", "has_active_mission", "NAM_agreement_deadline")] = False
        facts[("NAM", "has_country_flag", "NAM_agreement_offer_pending")] = True
        self.apply(self.effects["NAM_agreement_start"], facts)
        mission = self.decisions["NAM_agreement_deadline"]
        self.assertTrue(self.matches(block(mission, "visible"), facts))
        self.assertFalse(self.matches(block(mission, "available"), facts))
        self.assertFalse(self.matches(block(mission, "cancel_trigger"), facts))
        self.assertEqual(scalar(mission, "days_mission_timeout"), "180")
        audit = block(programmes, "NAM_agreement_audit")
        self.assertTrue(self.matches(block(audit, "visible"), facts))

    def test_agreement_audit_payment_delivery_and_repeated_cancellation(self):
        decision = self.decisions["NAM_agreement_audit"]
        for pp, cash, ready in ((75, 600, True), (74.99, 600, False), (75, 599.99, False)):
            facts = self.agreement_facts()
            facts[("NAM", "numeric", "has_political_power")] = pp
            facts[("NAM", "variable", "ADISCORD_economy_treasury")] = cash
            self.assertEqual(self.matches(self.triggers["NAM_agreement_audit_ready"], facts), ready)
        facts = self.agreement_facts()
        before = dict(facts)
        self.apply(block(decision, "complete_effect"), facts)
        self.assertEqual(facts[("NAM", "variable", "ADISCORD_economy_treasury")], 9400)
        self.assertEqual(facts[("NAM", "numeric", "has_political_power")], 925)
        self.assertFalse(self.matches(self.triggers["NAM_agreement_audit_ready"], facts))
        self.apply(self.effects["NAM_agreement_refund"], facts)
        self.apply(self.effects["NAM_agreement_refund"], facts)
        for key in (("NAM", "variable", "ADISCORD_economy_treasury"), ("NAM", "numeric", "has_political_power")):
            self.assertEqual(facts[key], before[key])
        self.apply(block(decision, "complete_effect"), facts)
        self.apply(block(decision, "remove_effect"), facts)
        self.assertEqual(facts[("NAM", "reward", "stability")], 0.05)
        self.apply(block(decision, "remove_effect"), facts)
        self.assertEqual(facts[("NAM", "reward", "stability")], 0.05)
        for cash, met in ((299.99, False), (300, True)):
            facts[("NAM", "variable", "ADISCORD_economy_treasury")] = cash
            self.assertEqual(self.matches(self.triggers["NAM_agreement_goal_met"], facts), met)

    def test_agreement_export_requires_real_fuel_and_tracks_three_deliveries(self):
        decision = self.decisions["NAM_agreement_export"]
        facts = self.agreement_facts(5)
        facts[("700", "is_owned_by", "NAM")] = True
        facts[("700", "is_controlled_by", "NAM")] = True
        for stock, payable in ((99999.99, False), (100000, True)):
            facts[("NAM", "numeric", "has_fuel")] = stock
            self.assertEqual(self.matches(block(decision, "custom_cost_trigger"), facts), payable)
        for number in range(1, 4):
            facts[("NAM", "numeric", "has_fuel")] = 100000
            self.apply(block(decision, "complete_effect"), facts)
            self.assertEqual(facts[("NAM", "numeric", "has_fuel")], 0)
            self.assertEqual(facts[("NAM", "variable", "ADISCORD_economy_treasury")], 10000 + 300 * number)
            self.assertEqual(facts[("NAM", "variable", "NAM_agreement_progress")], number)
            self.assertEqual(self.matches(self.triggers["NAM_agreement_goal_met"], facts), number == 3)
        self.assertEqual(scalar(decision, "days_re_enable"), "30")

    def test_agreement_failure_warns_and_war_cancels_without_support_loss(self):
        facts = self.agreement_facts(1)
        facts[("NAM", "variable", "NAM_grp_nam_support")] = 40
        self.apply(self.effects["NAM_agreement_failure"], facts)
        self.assertTrue(facts[("NAM", "has_active_mission", "NAM_agreement_crisis")])
        self.assertEqual(facts[("NAM", "variable", "NAM_grp_nam_support")], 20)
        self.assertTrue(facts[("NAM", "has_idea", "NAM_agreement_nam_failure")])
        facts[("NAM", "has_war", "no")] = False
        self.apply(self.effects["NAM_agreement_cancel"], facts)
        self.apply(self.effects["NAM_agreement_cancel"], facts)
        self.assertEqual(facts[("NAM", "variable", "NAM_grp_nam_support")], 20)
        self.assertFalse(facts[("NAM", "has_variable", "NAM_agreement_current")])
        self.assertFalse(facts[("NAM", "has_active_mission", "NAM_agreement_crisis")])
        self.assertTrue(facts[("NAM", "has_country_flag", "NAM_agreement_cooldown")])

    def test_agreement_offer_closes_safely_after_war_and_does_not_depend_on_ending(self):
        event = self.events["ADISCORD_nam_groups.20"]
        facts = self.agreement_facts()
        facts[("NAM", "has_variable", "NAM_agreement_current")] = False
        facts[("NAM", "has_country_flag", "NAM_agreement_offer_pending")] = True
        facts[("NAM", "variable", "NAM_agreement_offer_a")] = 1
        facts[("NAM", "variable", "NAM_agreement_offer_b")] = 4
        facts[("NAM", "has_country_flag", "NAM_ladder_settled")] = True
        options = [entry.value for entry in event if entry.key == "option"]
        self.assertTrue(self.matches(block(event, "trigger"), facts))
        self.assertTrue(self.matches(block(options[0], "trigger"), facts))
        facts[("NAM", "has_war", "no")] = False
        self.assertFalse(self.matches(block(options[0], "trigger"), facts))
        self.assertTrue(self.matches(block(options[-1], "trigger"), facts))
        self.apply(block(options[-1], "hidden_effect"), facts)
        self.assertFalse(facts[("NAM", "has_country_flag", "NAM_agreement_offer_pending")])

    def test_agreement_district_delivery_rechecks_ownership_and_is_idempotent(self):
        for controlled in (True, False):
            facts = self.agreement_facts(3)
            facts[("689", "has_state_flag", "NAM_agreement_building")] = True
            facts[("689", "has_state_flag", "NAM_project_in_progress")] = True
            facts[("689", "is_controlled_by", "NAM")] = controlled
            facts[("689", "variable", "NAM_project_deposit")] = 900
            facts[("689", "has_variable", "NAM_project_pp_deposit")] = True
            facts[("689", "variable", "NAM_project_pp_deposit")] = 50
            facts[("NAM", "variable", "NAM_projects_in_progress")] = 1
            facts[("fixture", "previous_state")] = "689"
            self.apply(self.effects["NAM_agreement_district_deliver"], facts, "689")
            self.apply(self.effects["NAM_agreement_district_deliver"], facts, "689")
            self.assertEqual(facts[("NAM", "variable", "NAM_projects_in_progress")], 0)
            self.assertEqual(facts[("NAM", "variable", "NAM_agreement_progress")], int(controlled))
            self.assertEqual(facts.get(("689", "building", "industrial_complex"), 0), int(controlled))
            self.assertEqual(facts[("NAM", "variable", "ADISCORD_economy_treasury")], 10000 + (0 if controlled else 900))

    @classmethod
    def setUpClass(cls):
        cls.tree, cls.focuses = tree_focuses("main")
        cls.wartime_tree, cls.wartime = tree_focuses("wartime")
        cls.postwar_tree, cls.postwar = tree_focuses("postwar")
        cls.defeated_tree, cls.defeated = tree_focuses("defeated")
        cls.south_war_tree, cls.south_war = tree_focuses("south_war")
        cls.exile_trees = {kind: tree_focuses(kind) for kind in EXILE}
        cls.triggers = {e.key: e.value for e in parsed(f"common/scripted_triggers/{BASE}_triggers.txt")}
        cls.triggers["RUS_crisis_side_compatible"] = block(
            parsed("common/scripted_triggers/ADISCORD_RUS_scripted_triggers.txt"), "RUS_crisis_side_compatible")
        cls.effects = {}
        for path in (f"common/scripted_effects/{BASE}_effects.txt", "common/scripted_effects/ADISCORD_shared_action_effects.txt"):
            cls.effects.update({e.key: e.value for e in parsed(path)})
        cls.decisions = national_decisions()
        cls.missions = {decision.key: decision.value
                        for category in parsed(f"common/decisions/{BASE}_decisions.txt")
                        for decision in category.value
                        if isinstance(decision.value, list)
                        and any(e.key == "days_mission_timeout" for e in decision.value)}
        cls.events = {scalar(e.value, "id"): e.value for e in parsed(f"events/{BASE}_events.txt") if e.key == "country_event"}
        cls.ideas = {e.key: e.value for e in block(block(parsed(f"common/ideas/{BASE}_ideas.txt"), "ideas"), "country")}

    def expand(self, entries):
        """Expand boolean triggers and bind explicit native building-slot fixtures."""
        result = []
        for entry in entries:
            if entry.key == "any_owned_state" and any(e.key.startswith("NAM_board_") and e.key.endswith("_site")
                                                      for e in entry.value):
                result.append(replace(entry, key="fixture_owned_board_site", value=tuple(self.expand(entry.value))))
            elif entry.key == "overlord" and [(e.key, e.value) for e in entry.value] == [("NAM_wor_southern_tag", "yes")]:
                tags = block(self.triggers["NAM_wor_southern_tag"], "OR")
                self.assertTrue(all(tag.key == "tag" for tag in tags))
                result.append(replace(entry, key="OR", value=[replace(tag, key="is_subject_of") for tag in tags]))
            elif entry.key == "set_variable" and len(entry.value) == 1:
                assignment = entry.value[0]
                self.assertIsInstance(assignment.value, str)
                self.assertTrue(assignment.key)
                result.append(replace(entry, value=[replace(assignment, key="var", value=assignment.key),
                                                    replace(assignment, key="value")]))
            elif entry.key == "for_loop_effect" and scalar(entry.value, "value").startswith("NAM_board_"):
                result.append(replace(entry, key="fixture_board_loop"))
            elif entry.key in ("NAM_rus_fuel_room", "NAM_exchange_fuel_room"):
                # The fuel variables use thousands of units in recipient scope.
                assignment, subtraction, condition = self.triggers[entry.key]
                self.assertEqual([assignment.key, subtraction.key, condition.key],
                                 ["set_temp_variable", "subtract_from_temp_variable", "check_variable"])
                result_var = scalar(assignment.value, "var")
                self.assertEqual(scalar(assignment.value, "value"), "max_fuel_k")
                self.assertEqual(scalar(subtraction.value, "var"), result_var)
                self.assertEqual(scalar(subtraction.value, "value"), "fuel_k")
                self.assertEqual(scalar(condition.value, "var"), result_var)
                comparison = replace(condition, value=[replace(e, value="fixture_fuel_room_k") if e.key == "var"
                                                       else e for e in condition.value])
                self.assertIn(entry.value, ("yes", "no"))
                result.append(comparison if entry.value == "yes" else replace(entry, key="NOT", value=[comparison]))
            elif entry.key in self.triggers:
                self.assertIn(entry.value, ("yes", "no"), entry.key)
                predicate = replace(entry, key="AND", value=self.expand(self.triggers[entry.key]))
                # A false scripted predicate negates its whole conjunction;
                # native NOT with several direct children would negate each.
                result.append(predicate if entry.value == "yes" else replace(entry, key="NOT", value=[predicate]))
            elif entry.key == "has_country_flag" and isinstance(entry.value, list) and any(e.value == "value" and not e.key for e in entry.value):
                field, operator, value = [e.value for e in entry.value if not e.key]
                self.assertEqual(field, "value")
                comparison = {"<": "less_than", ">": "greater_than"}[operator]
                flag = scalar(entry.value, "flag")
                numeric = replace(entry, key="check_variable", value=[replace(entry, key=k, value=v) for k, v in
                    (("var", "fixture_flag_value@" + flag), ("value", value), ("compare", comparison))])
                result.append(replace(entry, key="AND", value=[replace(entry, value=flag), numeric]))
            elif entry.key == "has_country_flag" and isinstance(entry.value, list) and any(e.value == "<" for e in entry.value):
                comparison = [e.value for e in entry.value if not e.key]
                self.assertEqual(comparison[:2], ["days", "<"])
                flag = scalar(entry.value, "flag")
                age = int(comparison[2])
                # Native flag age is an integer: present and not older than
                # N-1 is precisely younger than N, including the absent case.
                older = [replace(e, value=">" if e.value == "<" else str(age - 1) if e.value == comparison[2] else e.value)
                         for e in entry.value]
                result.append(replace(entry, key="AND", value=[replace(entry, value=flag),
                              replace(entry, key="NOT", value=[replace(entry, value=older)])]))
            elif entry.key == "is_in_array" and scalar(entry.value, "array") == "NAM_federal_districts":
                result.append(replace(entry, key="fixture_federal_district_member", value=scalar(entry.value, "value")))
            elif entry.key == "check_variable" and len(entry.value) == 1 and entry.value[0].key:
                field = entry.value[0]
                self.assertIsInstance(field.value, str)
                result.append(replace(entry, value=[replace(entry, key=k, value=v) for k, v in
                                                    (("var", field.key), ("value", field.value), ("compare", "equals"))]))
            elif entry.key == "check_variable" and all(not e.key for e in entry.value):
                variable, operator, value = (e.value for e in entry.value)
                comparison = {">": "greater_than", "<": "less_than", "=": "equals"}[operator]
                result.append(replace(entry, value=[replace(entry, key=k, value=v) for k, v in
                                                    (("var", variable), ("value", value), ("compare", comparison))]))
            elif entry.key == "has_railway_connection":
                self.assertEqual(scalar(entry.value, "build_only_on_allied"), "yes")
                key = scalar(entry.value, "start_state") + ":" + scalar(entry.value, "target_state")
                result.append(replace(entry, key="fixture_railway_connection", value=key))
            elif entry.key == "is_in_array" and any(
                    e.key == "array" and e.value == "global.RUS_crisis_defenders" for e in entry.value):
                self.assertEqual(scalar(entry.value, "value"), "THIS")
                result.append(replace(entry, key="fixture_registered_in", value="global.RUS_crisis_defenders"))
            elif entry.key == "any_of_scopes" and scalar(entry.value, "array") == "global.RUS_crisis_defenders":
                filters = self.expand([e for e in entry.value if e.key != "array"])
                result.append(replace(entry, key="fixture_any_defender", value=tuple(filters)))
            elif entry.key == "any_of_scopes" and scalar(entry.value, "array") == "NAM_conquered_states":
                filters = self.expand([e for e in entry.value if e.key != "array"])
                result.append(replace(entry, key="fixture_any_conquered_district", value=tuple(filters)))
            elif entry.key == "NAM" and any(e.key == "divisions_in_state" for e in entry.value):
                units = block(entry.value, "divisions_in_state")
                self.assertEqual(scalar(units, "state"), "PREV")
                self.assertEqual([e.value for e in units if not e.key], ["size", ">", "0"])
                result.append(replace(entry, value=self.expand([e for e in entry.value if e.key != "divisions_in_state"])))
                result.append(replace(entry, key="check_variable", value=[
                    replace(entry, key=k, value=v) for k, v in (("var", "fixture_posted_divisions"),
                        ("value", "0"), ("compare", "greater_than"))]))
            elif entry.key == "has_army_manpower":
                field, operator, value = [e.value for e in entry.value if not e.key]
                self.assertEqual((field, operator), ("size", ">"))
                result.append(replace(entry, key="check_variable", value=[
                    replace(entry, key=k, value=v) for k, v in (
                        ("var", "fixture_army_manpower"), ("value", value), ("compare", "greater_than"),
                    )
                ]))
            elif entry.key == "has_navy_size":
                comparison = [e.value for e in entry.value if not e.key]
                self.assertEqual(len(comparison), 3)
                field, operator, value = comparison
                self.assertEqual(field, "size")
                kind = next(e.value for e in entry.value if e.key in ("type", "unit"))
                variable = "fixture_navy_" + kind
                result.append(replace(entry, key="check_variable", value=[
                    replace(entry, key=k, value=v) for k, v in (
                        ("var", variable), ("value", value),
                        ("compare", {"<": "less_than", ">": "greater_than", "=": "equals"}[operator]),
                    )
                ]))
            elif entry.key == "free_building_slots":
                comparison = [e.value for e in entry.value if not e.key]
                if comparison:
                    self.assertEqual(comparison[:2], ["size", ">"])
                    building = scalar(entry.value, "building")
                    locked = scalar(entry.value, "include_locked")
                    result.append(replace(entry, key="check_variable", value=[
                        replace(entry, key=k, value=v) for k, v in (
                            ("var", f"fixture_building_slots_{building}_{locked}"),
                            ("value", comparison[2]), ("compare", "greater_than"),
                        )
                    ]))
                else:
                    self.assertEqual({e.key for e in entry.value}, {"building", "size", "include_locked"})
                    key = ":".join(scalar(entry.value, name) for name in ("building", "size", "include_locked"))
                    result.append(replace(entry, key="fixture_free_building_slots", value=key))
            elif entry.key in ("NAM_Vera_Pechat", "NAM_Arseny_Klyuch", "NAM_Taras_Shtyk", "NAM_Lev_Gavanov") and any(child.key == "is_hired_as_advisor" for child in entry.value):
                self.assertEqual(scalar(entry.value, "is_hired_as_advisor"), "yes")
                result.append(replace(entry, key="fixture_hired_character", value=entry.key))
            elif entry.key == "has_power_balance":
                self.assertEqual({e.key for e in entry.value}, {"id"})
                result.append(replace(entry, key="fixture_power_balance", value=scalar(entry.value, "id")))
            elif entry.key == "any_neighbor_state" and any(child.key == "controller" for child in entry.value):
                self.assertEqual(scalar(block(entry.value, "controller"), "has_war_with"), "NAM")
                result.append(replace(entry, key="fixture_hostile_land_border", value="yes"))
            elif entry.key == "any_neighbor_state":
                self.assertEqual(scalar(block(entry.value, "NOT"), "is_owned_by"), "NAM")
                result.append(replace(entry, key="fixture_foreign_land_border", value="yes"))
            elif isinstance(entry.value, list):
                result.append(replace(entry, value=self.expand(entry.value)))
            else:
                result.append(entry)
        return result

    def matches(self, entries, facts, scope="NAM"):
        view = FuelLogistics(facts) if facts.get(("fixture", "fuel_logistics")) else facts
        if ("fixture", "board_sites") in facts:
            view = BoardSites(facts)
        return matches_conditions(self.expand(entries), view, scope)

    def apply(self, entries, facts, current_scope="NAM"):
        """Execute selected accounting statements, leaving engine timing unmodelled."""
        def indexed_cell(name, scope):
            array, index = name.split("^", 1)
            values = (facts[(scope, "array", array)] if (scope, "array", array) in facts
                      else facts[("fixture", "temp_array", array)])
            position = amount(index, scope)
            self.assertEqual(position, int(position))
            self.assertTrue(0 <= position < len(values), (name, position))
            return values, int(position)

        def amount(value, scope):
            if "^" in value and value.split("^", 1)[0].startswith("NAM_board_"):
                values, position = indexed_cell(value, scope)
                return values[position]
            if value == "power_balance_value":
                return facts.get((scope, "fixture_native_balance_scalar"),
                                 abs(facts[(scope, "power_balance_value", "NAM_ladder_bop")]))
            if value == "fuel_k":
                return facts.get((scope, "numeric", "has_fuel"), 0) / 1000
            if value == "max_fuel_k":
                return facts.get((scope, "fuel_capacity"), 200000) / 1000
            try:
                return float(value)
            except ValueError:
                if "." in value:
                    holder, variable = value.split(".", 1)
                    if holder == "PREV":
                        holder = current_scope if current_scope.isdigit() else facts[("fixture", "previous_state")]
                    return facts[(holder, "variable", variable)]
                return facts[(scope, "variable", value)]

        conditions = BoardVariables(facts, amount) if ("global", "variable", "num_days") in facts else facts
        if facts.get(("fixture", "fuel_logistics")):
            conditions = FuelLogistics(facts)
        if ("fixture", "board_sites") in facts:
            conditions = BoardSites(facts)
        if ("fixture", "federal_front") in facts:
            # The shared selector resolves event targets from these bindings.
            for name, target in facts[("fixture", "federal_front")].items():
                facts[("event_target", name)] = target
        for scope, entry in selected_effects(self.expand(entries), conditions, current_scope):
            if entry.key == "add_ace":
                ace = (scope, "ace", scalar(entry.value, "type"))
                facts[ace] = facts.get(ace, 0) + 1
            elif entry.key in self.effects:
                self.apply(self.effects[entry.key], facts, scope)
            elif entry.key == "round_temp_variable" and entry.value.startswith("NAM_hum_diverted_"):
                key = (scope, "variable", entry.value)
                facts[key] = int(facts[key] + 0.5)
            elif entry.key == "save_global_event_target_as" and entry.value == "NAM_tenant_petition_site":
                facts[("NAM", "has_event_target", entry.value)] = True
                facts[("event_target", entry.value)] = scope
            elif entry.key == "clear_global_event_target" and entry.value == "NAM_tenant_petition_site":
                facts[("NAM", "has_event_target", entry.value)] = False
                facts.pop(("event_target", entry.value), None)
            elif entry.key == "country_event" and ("fixture", "board_callbacks") in facts:
                if scalar(entry.value, "id") == BASE + ".111":
                    delay = next(e for e in entry.value if e.key in ("days", "hours"))
                    calls = facts[("fixture", "board_callbacks")]
                    facts[("fixture", "board_callbacks")] = (*calls, (delay.key, int(delay.value)))
            elif entry.key == "clear_temp_array" and entry.value.startswith("NAM_board_"):
                facts[("fixture", "temp_array", entry.value)] = []
            elif entry.key == "resize_temp_array" and scalar(entry.value, "array").startswith("NAM_board_"):
                self.assertEqual(facts[("fixture", "temp_array", scalar(entry.value, "array"))], [])
                facts[("fixture", "temp_array", scalar(entry.value, "array"))] = (
                    [int(scalar(entry.value, "value"))] * int(scalar(entry.value, "size")))
            elif entry.key == "resize_array" and scalar(entry.value, "array") == "NAM_board_objection_days":
                name = scalar(entry.value, "array")
                size = int(scalar(entry.value, "size"))
                fill = int(next((e.value for e in entry.value if e.key == "value"), 0))
                old = facts.get((scope, "array", name), ())
                facts[(scope, "array", name)] = (old + (fill,) * size)[:size]
                facts[(scope, "variable", name + "^num")] = size
            elif entry.key == "set_variable" and scalar(entry.value, "var").startswith("NAM_board_objection_days^"):
                field = scalar(entry.value, "var")
                values, index = indexed_cell(field, scope)
                datum = amount(scalar(entry.value, "value"), scope)
                facts[(scope, "array", field.split("^", 1)[0])] = (*values[:index], datum, *values[index + 1:])
            elif entry.key == "add_to_temp_array" and any(
                    e.key == "array" and e.value.startswith("NAM_board_") for e in entry.value):
                name = scalar(entry.value, "array")
                array = facts[("fixture", "temp_array", name)]
                value = amount(scalar(entry.value, "value"), scope)
                facts[(scope, "variable", f"{name}^{len(array)}")] = value
                array.append(value)
            elif entry.key == "fixture_board_loop":
                controls = {e.key: e.value for e in entry.value if e.key in ("start", "end", "value", "add", "compare")}
                self.assertLessEqual(set(controls), {"start", "end", "value"})
                start, end = int(controls.get("start", 0)), int(controls["end"])
                self.assertTrue(0 <= start <= end <= 7)
                body = [e for e in entry.value if e.key not in controls]
                for index in range(start, end):
                    facts[(scope, "variable", controls["value"])] = index
                    self.apply(body, facts, scope)
            elif entry.key == "find_highest_in_array" and scalar(entry.value, "array").startswith("NAM_board_"):
                values = facts[("fixture", "temp_array", scalar(entry.value, "array"))]
                facts[(scope, "variable", scalar(entry.value, "index"))] = values.index(max(values))
                facts[(scope, "variable", scalar(entry.value, "value"))] = max(values)
            elif entry.key == "for_each_scope_loop" and scalar(entry.value, "array") == "NAM_federal_districts":
                for district in facts.get((scope, "array", "NAM_federal_districts"), ()):
                    self.apply([e for e in entry.value if e.key != "array"], facts, district)
            elif entry.key == "for_each_scope_loop" and scalar(entry.value, "array") == "NAM_conquered_states":
                for state in facts.get((scope, "array", "NAM_conquered_states"), ()):
                    self.apply([e for e in entry.value if e.key != "array"], facts, state)
            elif entry.key == "for_each_scope_loop" and ("fixture", "federal_front") in facts:
                name = scalar(entry.value, "array")
                self.assertIn(name, ("global.NAM_hum_federal_army", "global.NAM_wor_participants"))
                for member in facts[name]:
                    self.apply([e for e in entry.value if e.key != "array"], facts, member)
            elif entry.key == "add_to_array" and scalar(entry.value, "array") == "global.NAM_hum_federal_army":
                self.assertEqual(scalar(entry.value, "value"), "THIS")
                facts["global.NAM_hum_federal_army"].append(scope)
            elif entry.key == "clear_array" and entry.value == "global.NAM_hum_federal_army":
                facts[entry.value] = []
            elif entry.key == "save_event_target_as" and entry.value == "NAM_hum_mustered_district":
                facts[("fixture", "federal_front")][entry.value] = scope
                facts[("event_target", entry.value)] = scope
            elif entry.key == "add_to_war" and ("fixture", "federal_front") in facts:
                self.assertEqual(scalar(entry.value, "targeted_alliance"), "NAM")
                self.assertEqual(scalar(entry.value, "enemy"), "event_target:NAM_wor_primary")
                facts[("fixture", "federal_calls")].append(scope)
                for enemy in facts["global.NAM_wor_participants"]:
                    facts[(scope, "has_war_with", enemy)] = True
                    facts[(enemy, "has_war_with", scope)] = True
            elif entry.key == "white_peace" and ("fixture", "federal_front") in facts:
                self.assertEqual(entry.value, "event_target:NAM_hum_mustered_district")
                ally = facts[("fixture", "federal_front")]["NAM_hum_mustered_district"]
                facts[(scope, "has_war_with", ally)] = False
                facts[(ally, "has_war_with", scope)] = False
            elif entry.key == "for_each_scope_loop" and scalar(entry.value, "array") == "global.RUS_crisis_defenders":
                for country in facts.get(("global", "array", "RUS_crisis_defenders"), ()):
                    self.apply([e for e in entry.value if e.key != "array"], facts, country)
            elif entry.key == "country_event" and facts.get(("fixture", "fuel_logistics")):
                event = scalar(entry.value, "id")
                key = (scope, "scheduled_event", event)
                facts[key] = facts.get(key, 0) + 1
            elif entry.key in ("set_temp_variable", "add_to_temp_variable") and "^" in scalar(entry.value, "var"):
                values, position = indexed_cell(scalar(entry.value, "var"), scope)
                change = amount(scalar(entry.value, "value"), scope)
                values[position] = change if entry.key == "set_temp_variable" else values[position] + change
            elif entry.key == "NAM_Egor_Rom" and facts.get(("fixture", "track_leadership")):
                self.apply(entry.value, facts, entry.key)
            elif entry.key == "remove_country_leader_role" and facts.get(("fixture", "track_leadership")):
                ideology = scalar(entry.value, "ideology")
                facts[("NAM", "leader_role", scope, ideology)] = False
                facts[("NAM", "has_country_leader_ideology", ideology)] = False
            elif entry.key == "set_politics" and facts.get(("fixture", "track_leadership")):
                facts[(scope, "ruling_party")] = scalar(entry.value, "ruling_party")
            elif entry.key == "add_country_leader_role" and facts.get(("fixture", "track_leadership")):
                character = scalar(entry.value, "character")
                ideology = scalar(block(entry.value, "country_leader"), "ideology")
                facts[(scope, "leader_role", character, ideology)] = True
                if scalar(entry.value, "promote_leader") == "yes":
                    facts[(scope, "ruling_leader")] = character
                    for key in list(facts):
                        if key[:2] == (scope, "has_country_leader_ideology"):
                            facts[key] = False
                    facts[(scope, "has_country_leader_ideology", ideology)] = True
            elif entry.key == "add_days_mission_timeout":
                mission = scalar(entry.value, "mission")
                key = (scope, "variable", "days_mission_timeout@" + mission)
                if facts.get((scope, "has_active_mission", mission)):
                    facts[key] += float(scalar(entry.value, "days"))
            elif entry.key == "remove_mission":
                facts[(scope, "has_active_mission", entry.value)] = False
            elif entry.key == "activate_mission":
                facts[(scope, "has_active_mission", entry.value)] = True
                facts[(scope, "variable", "days_mission_timeout@" + entry.value)] = float(scalar(self.missions[entry.value], "days_mission_timeout"))
            elif entry.key == "round_variable":
                key = (scope, "variable", entry.value)
                facts[key] = int(facts[key] + 0.5)
            elif entry.key == "add_resource":
                key = (scope, "resource", scalar(entry.value, "type"))
                facts[key] = facts.get(key, 0) + amount(scalar(entry.value, "amount"), scope)
            elif entry.key == "add_political_power":
                key = (scope, "numeric", "has_political_power")
                facts[key] = facts.get(key, 0) + amount(entry.value, scope)
            elif entry.key == "add_fuel":
                key = (scope, "numeric", "has_fuel")
                facts[key] = facts.get(key, 0) + amount(entry.value, scope)
            elif entry.key == "set_fuel":
                facts[(scope, "numeric", "has_fuel")] = amount(entry.value, scope)
            elif entry.key in ("army_experience", "navy_experience", "add_command_power"):
                key = (scope, "numeric", "command_power" if entry.key == "add_command_power" else entry.key)
                facts[key] = facts.get(key, 0) + float(entry.value)
            elif entry.key in ("multiply_temp_variable", "multiply_variable"):
                key = (scope, "variable", scalar(entry.value, "var"))
                facts[key] *= amount(scalar(entry.value, "value"), scope)
            elif entry.key in ("divide_temp_variable", "divide_variable"):
                key = (scope, "variable", scalar(entry.value, "var"))
                facts[key] /= amount(scalar(entry.value, "value"), scope)
            elif entry.key in ("set_variable", "set_temp_variable", "add_to_variable", "subtract_from_variable", "add_to_temp_variable", "subtract_from_temp_variable"):
                key = (scope, "variable", scalar(entry.value, "var"))
                value = amount(scalar(entry.value, "value"), scope)
                if entry.key in ("set_variable", "set_temp_variable"):
                    facts[key] = value
                else:
                    facts[key] = facts.get(key, 0) + value * (-1 if entry.key.startswith("subtract_from_") else 1)
                facts[(scope, "has_variable", key[2])] = True
            elif entry.key == "clear_variable":
                facts.pop((scope, "variable", entry.value), None)
                facts[(scope, "has_variable", entry.value)] = False
            elif entry.key in ("clamp_variable", "clamp_temp_variable"):
                key = (scope, "variable", scalar(entry.value, "var"))
                facts[key] = max(amount(scalar(entry.value, "min"), scope), min(amount(scalar(entry.value, "max"), scope), facts[key]))
            elif entry.key == "add_manpower":
                key = (scope, "numeric", "has_manpower")
                facts[key] = facts.get(key, 0) + amount(entry.value, scope)
            elif entry.key == "while_loop_effect" and facts.get(("fixture", "track_loops")):
                limit = block(entry.value, "limit")
                body = [child for child in entry.value if child.key != "limit"]
                for _ in range(65):
                    if not matches_conditions(self.expand(limit), facts, scope):
                        break
                    self.apply(body, facts, scope)
                else:
                    self.fail("Fixture loop exceeded its bounded formation count")
            elif entry.key == "division_template" and facts.get(("fixture", "track_templates")):
                name = scalar(entry.value, "name")
                facts[(scope, "has_template", name)] = True
                facts[(scope, "template_locked", name)] = any(
                    field.key == "is_locked" and field.value == "yes" for field in entry.value
                )
            elif entry.key == "set_division_template_lock" and facts.get(("fixture", "track_templates")):
                facts[(scope, "template_locked", scalar(entry.value, "division_template"))] = scalar(entry.value, "is_locked") == "yes"
            elif entry.key == "set_division_force_allow_recruiting" and facts.get(("fixture", "track_templates")):
                facts[(scope, "template_recruitable", scalar(entry.value, "division_template"))] = scalar(entry.value, "force_allow_recruiting") == "yes"
            elif entry.key == "add_power_balance_value":
                key = (scope, "power_balance_value", scalar(entry.value, "id"))
                facts[key] = max(-1, min(1, facts.get(key, 0) + float(scalar(entry.value, "value"))))
            elif entry.key == "damage_building":
                key = (scope, "building_damage", scalar(entry.value, "type"))
                facts[key] = facts.get(key, 0) + float(scalar(entry.value, "damage"))
            elif entry.key == "remove_building":
                key = (scope, "building", scalar(entry.value, "type"))
                facts[key] = max(0, facts.get(key, 0) - int(scalar(entry.value, "level")))
            elif entry.key == "add_building_construction":
                key = (scope, "building", scalar(entry.value, "type"))
                facts[key] = facts.get(key, 0) + int(scalar(entry.value, "level"))
                if scalar(entry.value, "type") == "supply_node":
                    facts[(scope, "numeric", "supply_node")] = facts[key]
            elif entry.key == "add_extra_state_shared_building_slots":
                key = (scope, "reward", "building_slots")
                facts[key] = facts.get(key, 0) + int(entry.value)
            elif entry.key in ("set_country_flag", "clr_country_flag"):
                name = scalar(entry.value, "flag") if isinstance(entry.value, list) else entry.value
                facts[(scope, "has_country_flag", name)] = entry.key == "set_country_flag"
                if facts.get(("fixture", "fuel_logistics")) and isinstance(entry.value, list):
                    days = next((e.value for e in entry.value if e.key == "days"), None)
                    if days is not None:
                        facts[(scope, "flag_duration", name)] = int(days)
                if isinstance(entry.value, list):
                    value = next((e.value for e in entry.value if e.key == "value"), "1")
                    facts[(scope, "variable", "fixture_flag_value@" + name)] = float(value)
            elif entry.key in ("set_state_flag", "clr_state_flag"):
                name = scalar(entry.value, "flag") if isinstance(entry.value, list) else entry.value
                facts[(scope, "has_state_flag", name)] = entry.key == "set_state_flag"
            elif entry.key == "add_tech_bonus":
                categories = tuple(child.value for child in entry.value if child.key == "category")
                facts[(scope, "tech_bonus", scalar(entry.value, "name"))] = (
                    float(scalar(entry.value, "bonus")), int(scalar(entry.value, "uses")),
                    categories[0] if len(categories) == 1 else categories)
            elif entry.key == "set_technology":
                for technology in entry.value:
                    if technology.key != "popup":
                        facts[(scope, "has_tech", technology.key)] = technology.value == "1"
            elif entry.key in ("add_dynamic_modifier", "remove_dynamic_modifier"):
                name = scalar(entry.value, "modifier")
                facts[(scope, "has_dynamic_modifier", name)] = entry.key == "add_dynamic_modifier"
            elif entry.key == "add_equipment_to_stockpile":
                key = (scope, "equipment", scalar(entry.value, "type"))
                facts[key] = facts.get(key, 0) + amount(scalar(entry.value, "amount"), scope)
                navy_count = (scope, "variable", "fixture_navy_convoy")
                if key[2] == "convoy_1" and navy_count in facts:
                    facts[navy_count] += amount(scalar(entry.value, "amount"), scope)
                archetype = re.sub(r"_\d+$", "", key[2])
                stock = (scope, "variable", "num_equipment@" + archetype)
                if stock in facts:
                    facts[stock] += amount(scalar(entry.value, "amount"), scope)
                    facts[(scope, "equipment", archetype)] = facts[stock]
            elif entry.key == "send_equipment" and facts.get(("fixture", "fuel_logistics")):
                equipment = scalar(entry.value, "equipment")
                source = (scope, "equipment", equipment)
                recipient = scalar(entry.value, "target")
                recipient = facts.get(("fixture", recipient), recipient)
                destination = (recipient, "equipment", equipment)
                quantity = amount(scalar(entry.value, "amount"), scope)
                self.assertGreater(quantity, 0)
                self.assertGreaterEqual(facts.get(source, 0), quantity, (source, quantity))
                self.assertNotEqual(source, destination)
                facts[source] -= quantity
                facts[destination] = facts.get(destination, 0) + quantity
            elif entry.key == "puppet" and ("fixture", "accession_country") in facts:
                self.assertEqual((scope, entry.value), ("NAM", "PREV"))
                country = facts[("fixture", "accession_country")]
                facts[(country, "is_subject_of", scope)] = True
                facts[(country, "is_subject", "no")] = False
            elif entry.key == "set_autonomy" and ("fixture", "accession_country") in facts:
                self.assertEqual((scope, scalar(entry.value, "target")), ("NAM", "PREV"))
                country = facts[("fixture", "accession_country")]
                facts[(country, "autonomy")] = scalar(entry.value, "autonomy_state")
            elif entry.key == "add_to_array" and scalar(entry.value, "array") == "NAM_federal_districts":
                if ("fixture", "accession_country") in facts:
                    self.assertEqual((scope, scalar(entry.value, "value")), ("NAM", "PREV"))
                    key = (scope, "array", "NAM_federal_districts")
                    facts[key] = (*facts.get(key, ()), facts[("fixture", "accession_country")])
            elif entry.key == "owner" and facts.get(("fixture", "market_owners")):
                self.apply(entry.value, facts, facts[(scope, "owner")])
            elif entry.key == "every_owned_state" and ("fixture", "returnee_sites") in facts:
                for state in facts[("fixture", "returnee_sites")]:
                    if facts.get((state, "is_owned_by", scope)) and self.matches(block(entry.value, "limit"), facts, state):
                        self.apply([e for e in entry.value if e.key != "limit"], facts, state)
            elif entry.key == "random_owned_state" and ("fixture", "board_sites") in facts:
                for state in facts[("fixture", "board_sites")]:
                    if matches_conditions(block(entry.value, "limit"), conditions, state):
                        self.apply([e for e in entry.value if e.key != "limit"], facts, state)
                        break
            elif entry.key == "capital_scope" and (facts.get(("fixture", "track_units")) or
                                                   ("fixture", "board_sites") in facts):
                self.apply(entry.value, facts, facts[(scope, "capital")])
            elif entry.key == "create_unit" and facts.get(("fixture", "track_units")):
                owner = scalar(entry.value, "owner")
                if owner == "PREV":
                    owner = facts[(scope, "owner")]
                key = (owner, "reward", "spawned_divisions")
                facts[key] = facts.get(key, 0) + 1
            elif entry.key == "build_railway" and any(e.key == "path" for e in entry.value):
                path = [int(e.value) for e in block(entry.value, "path")]
                key = (scope, "fixture_rail_edges")
                edges = set(facts.get(key, ()))
                edges.update(tuple(sorted(pair)) for pair in zip(path, path[1:]))
                facts[key] = tuple(sorted(edges))
                connected = {16716}
                while True:
                    added = {end for edge in edges if connected.intersection(edge) for end in edge}
                    if added <= connected:
                        break
                    connected.update(added)
                for state, node in (("690", 9016), ("719", 6961)):
                    facts[(scope, "fixture_railway_connection", "700:" + state)] = node in connected
            elif entry.key == "create_ship":
                key = (scope, "ships", scalar(entry.value, "type"))
                facts[key] = facts.get(key, 0) + int(scalar(entry.value, "amount"))
            elif entry.key == "add_timed_idea":
                facts[(scope, "has_idea", scalar(entry.value, "idea"))] = True
                facts[(scope, "idea_days", scalar(entry.value, "idea"))] = int(scalar(entry.value, "days"))
            elif entry.key == "remove_ideas" and isinstance(entry.value, str):
                facts[(scope, "has_idea", entry.value)] = False
                facts.pop((scope, "idea_days", entry.value), None)
            elif entry.key in ("add_stability", "add_war_support"):
                key = (scope, "reward", entry.key.removeprefix("add_"))
                facts[key] = facts.get(key, 0) + float(entry.value)
            elif entry.key in ("add_core_of", "remove_core_of"):
                facts[(scope, "is_core_of", entry.value)] = entry.key == "add_core_of"
            elif entry.key == "add_resistance":
                key = (scope, "numeric", "resistance")
                facts[key] = max(0, min(100, facts.get(key, 0) + float(entry.value)))
            elif entry.key == "add_compliance":
                self.assertTrue(facts.get((scope, "has_resistance", "yes"), False),
                                f"Cannot change compliance in {scope} without resistance")
                key = (scope, "numeric", "compliance")
                facts[key] = max(0, min(100, facts.get(key, 0) + float(entry.value)))
            elif entry.key == "give_resource_rights":
                facts[(scope, "resource_rights", scalar(entry.value, "state"))] = scalar(entry.value, "receiver")
            elif entry.key in ("add_opinion_modifier", "remove_opinion_modifier"):
                key = scalar(entry.value, "modifier") + ":" + scalar(entry.value, "target")
                facts[(scope, "opinion", key)] = entry.key == "add_opinion_modifier"

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
        for focus in (*self.focuses, *self.wartime):
            result[("NAM", "has_completed_focus", focus)] = True
        result[("NAM", "has_completed_focus", "NAM_recognition")] = False
        for name in ("NAM_hidden_fuel", "NAM_open_fuel_reserve", "WKR_evacuated_fuel_reserve"):
            result[("NAM", "variable", name)] = 0
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
        def unconditional_conditions(entries):
            for entry in entries:
                if entry.key in ("AND", "custom_trigger_tooltip", "hidden_trigger"):
                    yield from unconditional_conditions(entry.value)
                else:
                    yield entry

        expected = {
            "main": (self.focuses, 95), "wartime": (self.wartime, 40),
            "postwar": (self.postwar, 246), "defeated": (self.defeated, 22),
            "south_war": (self.south_war, 68),
            "exile_radical": (self.exile_trees["exile_radical"][1], 72),
            "exile_humanist": (self.exile_trees["exile_humanist"][1], 73),
            "exile_corporate": (self.exile_trees["exile_corporate"][1], 34),
        }
        names = [name for focuses, _ in expected.values() for name in focuses]
        self.assertEqual(len(names), len(set(names)))
        for kind, (focuses, count) in expected.items():
            coordinates = set()
            self.assertEqual(len(focuses), count, kind)
            filters = set()
            for name, focus in focuses.items():
                # War-tree course branches share cells; allow_branch shows one course.
                gate = repr([(e.key, repr(e.value)) for e in block(focus, "allow_branch")]) if kind == "south_war" else ""
                coordinate = (scalar(focus, "x"), scalar(focus, "y"), gate)
                self.assertNotIn(coordinate, coordinates, name)
                coordinates.add(coordinate)
                self.assertTrue(block(focus, "completion_reward"), name)
                self.assertIn(int(scalar(focus, "cost")), range(1, 13))
                filters.add(tuple(e.value for e in block(focus, "search_filters")))
                available = unconditional_conditions(self.expand(block(focus, "available")))
                self.assertTrue(any(e.key == "has_capitulated" and e.value == "no" for e in available), name)
                for group in (e.value for e in focus if e.key == "prerequisite"):
                    for child in group:
                        self.assertIn(child.value, focuses, (name, "prerequisite leaves its tree"))
            self.assertGreaterEqual(len(filters), 4, kind)

    def test_compact_layout_connects_all_programmes_to_the_independence_focus(self):
        positions = {name: (int(scalar(body, "x")), int(scalar(body, "y")))
                     for name, body in self.focuses.items()}
        self.assertLessEqual(max(x for x, _ in positions.values()) - min(x for x, _ in positions.values()), 73)
        self.assertLessEqual(max(y for _, y in positions.values()), 13)
        for name, body in self.focuses.items():
            for requirement in (e.value for e in body if e.key == "prerequisite"):
                for parent in requirement:
                    self.assertLess(positions[parent.value][1], positions[name][1], (name, parent.value))
            if any(e.key == "allow_branch" for e in body):
                self.assertEqual(scalar(block(body, "allow_branch"), "has_completed_focus"), "NAM_letters_to_the_centre")
                if name != "NAM_independence_day":
                    self.assertEqual(scalar(block(body, "prerequisite"), "focus"), "NAM_independence_day", name)
                    self.assertEqual(positions[name][1], positions["NAM_independence_day"][1] + 1, name)

    def test_independent_programmes_can_change_priority_without_skipping_the_final_requirements(self):
        routes = (
            (("open_ledgers", "districts"),
             (("district_guarantees", "tax_rolls", "one_budget"),
              ("supports_oil_compact", "pillar_arbitration")), "seal_courts"),
            (("open_ledgers", "vertical"),
             (("emergency_writ", "tax_rolls", "one_budget"),
              ("supports_export_houses", "pillar_arbitration")), "seal_courts"),
            (("flight_school",), (("air_ground_service",), ("air_interceptors",)), "air_operations"),
            (("flight_school",), (("air_ground_service",), ("air_support",)), "air_operations"),
        )

        def ready(name, completed):
            body = self.focuses["NAM_" + name]
            return all(any(e.value in completed for e in group.value) for group in body if group.key == "prerequisite")

        for foundation, branches, final in routes:
            for order in permutations(branches):
                complete = {"NAM_letters_to_the_centre", "NAM_independence_day"}
                for name in foundation:
                    self.assertTrue(ready(name, complete), name)
                    complete.add("NAM_" + name)
                self.assertFalse(ready(final, complete), final)
                for index, branch in enumerate(order):
                    for name in branch:
                        self.assertTrue(ready(name, complete), (name, order))
                        complete.add("NAM_" + name)
                    self.assertEqual(ready(final, complete), index == len(order) - 1, (final, order))
        foundation = {"NAM_well_register", "NAM_contract_bureau", "NAM_field_repair_crews"}
        for name in ("fuel_depots", "second_drilling_crew", "klyuchevsk_pipeline"):
            self.assertTrue(ready(name, foundation), name)
        completed = reachable(self.focuses, {"NAM_escort_school", "NAM_active_squadron"})
        self.assertIn("NAM_island_accounts", completed)
        self.assertNotIn("NAM_naval_construction", completed)

    def test_wartime_tree_retains_shared_history_and_loads_after_war_entry(self):
        from tools.builders.build_adiscord_focus_trees import SHARED_HISTORY_SOURCES
        for kind in ("main", "wartime"):
            self.assertIn(TREES[kind][0].removeprefix("focus_trees/"), SHARED_HISTORY_SOURCES)
            native = parsed("common/national_focus/" + TREES[kind][2])
            definitions = [scalar(e.value, "id") for e in native if e.key == "shared_focus"]
            self.assertCountEqual(definitions, self.focuses if kind == "main" else self.wartime)
            roots = {e.value for e in block(native, "focus_tree") if e.key == "shared_focus"}
            source = self.focuses if kind == "main" else self.wartime
            self.assertEqual(roots, {name for name, body in source.items() if not any(e.key == "prerequisite" for e in body)})
        start = list(walk(self.effects["ADISCORD_nam_resource_war_begin_hostilities"]))
        switch = next(i for i, entry in enumerate(start) if entry.key == "load_focus_tree"
                      and scalar(entry.value, "tree") == "NAM_resource_war_focus")
        for key in ("NAM_deliver_mobilisation_orders", "declare_war_on", "add_to_war"):
            self.assertLess(max(i for i, entry in enumerate(start) if entry.key == key), switch, key)
        self.assertEqual(scalar(start[switch].value, "keep_completed"), "yes")
        conditions = [e for e in block(block(self.wartime_tree, "country"), "modifier") if e.key != "add"]
        for started, resolved in product((False, True), repeat=2):
            facts = {("NAM", "original_tag", "NAM"): True,
                     ("NAM", "has_global_flag", BASE + "_started"): started,
                     ("NAM", "has_global_flag", BASE + "_resolved"): resolved}
            self.assertEqual(self.matches(conditions, facts), started and not resolved)
        for name in ("ADISCORD_nam_resource_war_close_external", "ADISCORD_nam_resource_war_resolve_coalition_victory"):
            switches = [e.value for e in walk(self.effects[name]) if e.key == "load_focus_tree"]
            fallback = [body for body in switches if scalar(body, "tree") == "NAM_focus"]
            self.assertEqual(len(fallback), 1, name)
            self.assertEqual(scalar(fallback[0], "keep_completed"), "yes")

    def test_wartime_procurement_delivers_or_refunds_and_releases_civil_slot(self):
        orders = {
            "NAM_war_transport_purchase": ("NAM_war_rear_directorate", 35, 650,
                {("NAM", "equipment", "motorized_equipment"): 300,
                 ("NAM", "equipment", "train_equipment"): 15}),
            "NAM_war_refugee_registration": ("NAM_war_civilian_routes", 25, 350,
                {("NAM", "numeric", "has_manpower"): 6000,
                 ("NAM", "reward", "stability"): 0.03}),
        }
        for name, (focus, pp, cash, rewards) in orders.items():
            decision = self.decisions[name]
            for outcome in ("delivery", "peace", "capitulation", "unaffordable"):
                facts = self.postwar_facts()
                facts[("NAM", "has_global_flag", BASE + "_started")] = True
                facts[("NAM", "has_global_flag", BASE + "_resolved")] = False
                facts[("NAM", "has_war", "yes")] = True
                facts[("NAM", "has_completed_focus", focus)] = True
                facts[("NAM", "numeric", "has_political_power")] = pp
                facts[("NAM", "variable", "ADISCORD_economy_treasury")] = cash - (0.01 if outcome == "unaffordable" else 0)
                for key in rewards:
                    facts[key] = 0
                initial = dict(facts)
                self.apply(block(decision, "complete_effect"), facts)
                if outcome == "unaffordable":
                    self.assertEqual(facts, initial)
                    continue
                self.assertEqual(facts[("NAM", "numeric", "has_political_power")], 0)
                self.assertEqual(facts[("NAM", "variable", "ADISCORD_economy_treasury")], 0)
                paid = dict(facts)
                self.apply(block(decision, "complete_effect"), facts)
                self.assertEqual(facts, paid)
                for other in orders:
                    self.assertFalse(self.matches(block(self.decisions[other], "available"), facts))
                if outcome == "peace":
                    facts[("NAM", "has_global_flag", BASE + "_resolved")] = True
                    with patch.dict(self.effects, {"NAM_oil_refresh": []}):
                        self.apply(self.effects["NAM_close_war_programmes"], facts)
                elif outcome == "capitulation":
                    facts[("NAM", "has_capitulated", "no")] = False
                    self.assertTrue(self.matches(block(decision, "cancel_trigger"), facts))
                self.apply(block(decision, "remove_effect"), facts)
                for key, amount in rewards.items():
                    self.assertAlmostEqual(facts.get(key, 0), amount if outcome == "delivery" else 0, msg=(name, outcome, key))
                if outcome != "delivery":
                    self.assertEqual(facts[("NAM", "numeric", "has_political_power")], pp)
                    self.assertEqual(facts[("NAM", "variable", "ADISCORD_economy_treasury")], cash)
                self.assertFalse(facts[("NAM", "has_country_flag", "NAM_pw_civil_busy")])
                settled = dict(facts)
                self.apply(block(decision, "remove_effect"), facts)
                self.apply(block(decision, "cancel_effect"), facts)
                self.assertEqual(facts, settled)

    def test_wartime_new_purchase_prices_recheck_fractional_balances_and_current_war(self):
        cases = (
            ("NAM_war_arms_purchase", "NAM_war_procurement_board", 35, "treasury", 500,
             {"infantry_equipment": 6000, "support_equipment": 100}),
            ("NAM_war_oil_for_arms", "NAM_war_fuel_barter", 25, "fuel", 20000,
             {"artillery_equipment": 120, "support_equipment": 80}),
        )
        for name, focus, pp, currency, price, delivery in cases:
            decision = self.decisions[name]
            self.assertEqual(scalar(decision, "cost"), "0")
            self.assertEqual(scalar(decision, "days_re_enable"), "45")
            for outcome in ("success", "short_pp", "short_material", "peace", "subject", "locked"):
                with self.subTest(decision=name, outcome=outcome):
                    facts = self.postwar_facts()
                    facts[("NAM", "has_global_flag", BASE + "_started")] = True
                    facts[("NAM", "has_global_flag", BASE + "_resolved")] = outcome == "peace"
                    facts[("NAM", "has_war", "yes")] = True
                    facts[("NAM", "is_subject", "no")] = outcome != "subject"
                    facts[("NAM", "has_completed_focus", focus)] = outcome != "locked"
                    pp_key = ("NAM", "numeric", "has_political_power")
                    material_key = (("NAM", "variable", "ADISCORD_economy_treasury")
                                    if currency == "treasury" else ("NAM", "numeric", "has_fuel"))
                    facts[pp_key] = pp - (0.01 if outcome == "short_pp" else 0)
                    facts[material_key] = price - (0.01 if outcome == "short_material" else 0)
                    self.assertEqual(self.matches(block(decision, "custom_cost_trigger"), facts),
                                     outcome not in ("short_pp", "short_material"))
                    before = dict(facts)
                    self.apply(block(decision, "complete_effect"), facts)
                    if outcome != "success":
                        self.assertEqual(facts, before)
                        continue
                    self.assertEqual(facts[pp_key], 0)
                    self.assertEqual(facts[material_key], 0)
                    for equipment, amount in delivery.items():
                        self.assertEqual(facts[("NAM", "equipment", equipment)], amount)
                    if currency == "treasury":
                        self.assertEqual(facts[("NAM", "variable", "ADISCORD_economy_current_month_action_costs")],
                                         before.get(("NAM", "variable", "ADISCORD_economy_current_month_action_costs"), 0) + price)

    def test_wartime_service_programmes_cancel_with_war_or_lost_shipyard(self):
        names = ("NAM_war_medical_rotation", "NAM_war_ammunition_push",
                 "NAM_war_dockyard_rotation", "NAM_war_air_service_rotation")
        cleanup = {e.value for e in walk(self.effects["NAM_close_war_programmes"])
                   if e.key == "remove_decision"}
        for name in names:
            decision = self.decisions[name]
            self.assertIn(name, cleanup)
            self.assertTrue(block(decision, "modifier"))
            self.assertFalse(any(e.key == "add_political_power" for e in walk(decision)))
            for outcome in ("active", "peace", "subject", "capitulation", "no_war", "lost_port"):
                facts = self.postwar_facts()
                facts[("NAM", "has_global_flag", BASE + "_started")] = True
                facts[("NAM", "has_global_flag", BASE + "_resolved")] = outcome == "peace"
                facts[("NAM", "is_subject", "no")] = outcome != "subject"
                facts[("NAM", "has_capitulated", "no")] = outcome != "capitulation"
                facts[("NAM", "has_war", "yes")] = outcome != "no_war"
                facts[("NAM", "controls_state", "700")] = outcome != "lost_port"
                ready = parse_clausewitz("controls_state = 700")
                with patch.dict(self.triggers, {"NAM_naval_shipyard_ready": ready}):
                    active = outcome == "active" or (outcome == "lost_port" and name != "NAM_war_dockyard_rotation")
                    self.assertEqual(self.matches(block(decision, "available"), facts), active, (name, outcome))
                    self.assertEqual(self.matches(block(decision, "cancel_trigger"), facts), not active, (name, outcome))
            for hook in ("complete_effect", "remove_effect", "cancel_effect"):
                self.assertIn("ADISCORD_economy_mark_dirty", {e.key for e in walk(block(decision, hook))})

    def test_wartime_extended_routes_fit_mission_and_keep_exclusion_links_clear(self):
        positions = {name: (int(scalar(body, "x")), int(scalar(body, "y")))
                     for name, body in self.wartime.items()}
        self.assertFalse(focus_exclusion_crossings(self.wartime, positions))
        mission_days = int(scalar(self.decisions["NAM_defend_fields"], "days_mission_timeout"))
        for plan in parsed("common/ai_strategy_plans/ADISCORD_NAM_plans.txt"):
            if not plan.key.startswith("NAM_resource_war_"):
                continue
            route = [e.value for e in block(plan.value, "ai_national_focuses")]
            self.assertEqual(len(route), len(set(route)))
            self.assertLess(sum(7 * int(scalar(self.wartime[name], "cost")) for name in route), mission_days)
            for focus in ("NAM_war_procurement_board", "NAM_war_rear_reserve", "NAM_war_fuel_barter",
                          "NAM_war_naval_repair_service", "NAM_war_air_maintenance", "NAM_war_counterbattery"):
                self.assertIn(focus, route)

    def test_wartime_conscription_advances_current_law_once_and_bypasses_ceiling(self):
        focus = self.wartime["NAM_war_conscription_rolls"]
        laws = ("disarmed_nation", "volunteer_only", "limited_conscription",
                "extensive_conscription", "service_by_requirement", "all_adults_serve",
                "scraping_the_barrel")
        self.assertEqual(7 * (int(scalar(self.wartime["NAM_alarm"], "cost"))
                              + int(scalar(focus, "cost"))), 21)
        for index, law in enumerate(laws):
            with self.subTest(law=law):
                facts = {("NAM", "has_idea", law): True}
                selected = selected_effects(block(focus, "completion_reward"), facts, "NAM")
                changed = [entry.value for scope, entry in selected if entry.key == "add_ideas"]
                self.assertEqual(changed, list(laws[index + 1:index + 2]))
                self.assertEqual(self.matches(block(focus, "bypass"), facts), index == len(laws) - 1)
        native_laws = block(parsed("common/ideas/_manpower.txt"), "ideas")
        mobilization = block(native_laws, "mobilization_laws")
        for law in laws[1:]:
            on_add = list(walk(block(block(mobilization, law), "on_add")))
            self.assertTrue(any(e.key == "ADISCORD_economy_queue_law_refresh" for e in on_add))

    def test_wartime_instructors_end_with_current_war_or_country_operability(self):
        decision = self.decisions["NAM_war_frontline_instructors"]
        self.assertEqual(scalar(decision, "cost"), "50")
        self.assertEqual(scalar(decision, "days_remove"), "60")
        self.assertNotIn("custom_cost_text", {e.key for e in decision})
        self.assertFalse(any(e.key == "add_political_power" for e in walk(decision)))
        for ended, subject, capitulated, at_war in product((False, True), repeat=4):
            facts = self.postwar_facts()
            facts[("NAM", "has_global_flag", BASE + "_started")] = True
            facts[("NAM", "has_global_flag", BASE + "_resolved")] = ended
            facts[("NAM", "is_subject", "no")] = not subject
            facts[("NAM", "has_capitulated", "no")] = not capitulated
            facts[("NAM", "has_war", "yes")] = at_war
            facts[("NAM", "has_war", "no")] = not at_war
            active = not ended and not subject and not capitulated and at_war
            self.assertEqual(self.matches(block(decision, "available"), facts), active)
            self.assertEqual(self.matches(block(decision, "cancel_trigger"), facts), not active)
        removed = {e.value for e in walk(self.effects["NAM_close_war_programmes"])
                   if e.key == "remove_decision"}
        self.assertIn("NAM_war_frontline_instructors", removed)

    def test_wartime_aircraft_follow_selected_role_and_harbour_rechecks_site(self):
        reward = block(self.wartime["NAM_war_replacement_aircraft"], "completion_reward")
        for interceptors, equipment in ((True, "ADISCORD_fighter_airframe_2163"),
                                        (False, "ADISCORD_cas_airframe_2170")):
            facts = {("NAM", "has_completed_focus", "NAM_war_interceptor_control"): interceptors}
            self.apply(reward, facts)
            stock = {key[2]: value for key, value in facts.items() if key[1] == "equipment"}
            self.assertEqual(stock, {equipment: 24})
        harbour = self.wartime["NAM_war_harbour_workshops"]
        entry_site = block(block(harbour, "available"), "700")
        delivery = block(block(block(harbour, "completion_reward"), "700"), "if")
        # Identical native predicates prevent construction after occupation or a filled slot.
        def signature(body):
            return [(e.key, signature(e.value) if isinstance(e.value, list) else e.value)
                    for e in body]

        self.assertEqual(signature(entry_site), signature(block(delivery, "limit")))
        self.assertEqual(scalar(entry_site, "is_owned_by"), "ROOT")
        self.assertEqual(scalar(entry_site, "is_controlled_by"), "ROOT")
        self.assertTrue(block(entry_site, "free_building_slots"))

    def test_wartime_expansion_uses_choices_and_cleans_temporary_ideas(self):
        pairs = (("war_depot_network", "war_mobile_workshops"),
                 ("war_civilian_routes", "war_factory_shifts"),
                 ("war_convoy_escort", "war_coastal_batteries"),
                 ("war_interceptor_control", "war_air_ground_liaison"),
                 ("war_short_training", "war_veteran_cadres"),
                 ("war_medical_trains", "war_shell_priority"),
                 ("war_fuel_discipline", "war_extraction_surge"))
        for a, b in pairs:
            for left, right in ((a, b), (b, a)):
                self.assertEqual(scalar(block(self.wartime["NAM_" + left], "mutually_exclusive"), "focus"), "NAM_" + right)
        ideas = block(block(parsed("common/ideas/ADISCORD_nam_resource_war_ideas.txt"), "ideas"), "country")
        cleanup = {e.value for e in walk(self.effects["NAM_close_war_programmes"]) if e.key == "remove_ideas"}
        for focus in self.wartime.values():
            for timed in (e.value for e in walk(block(focus, "completion_reward")) if e.key == "add_timed_idea"):
                name = scalar(timed, "idea")
                self.assertIn(name, cleanup)
                cancel = block(block(ideas, name), "cancel")
                condition = block(cancel, "custom_trigger_tooltip")
                self.assertEqual(scalar(condition, "tooltip"), "NAM_resource_war_spirit_ended_tt")
                self.assertEqual(scalar(condition, "ADISCORD_nam_resource_war_active"), "no")
        for balance, district, martial in ((-0.6, False, True), (0, True, True), (0.6, True, False)):
            facts = self.mandate_facts(balance)
            self.apply(self.effects["NAM_freeze_prewar_mandate"], facts)
            self.assertEqual(self.matches(block(self.wartime["NAM_district_volunteers"], "available"), facts), district)
            self.assertEqual(self.matches(block(self.wartime["NAM_martial_seals"], "available"), facts), martial)

    def test_wartime_ai_uses_only_its_tree_and_one_political_course(self):
        plans = parsed("common/ai_strategy_plans/ADISCORD_NAM_plans.txt")
        for vertical in (False, True):
            course = "vertical" if vertical else "district"
            plan = block(plans, f"NAM_resource_war_{course}_plan")
            facts = {("NAM", "tag", "NAM"): True, ("NAM", "is_ai", "yes"): True,
                     ("NAM", "has_focus_tree", "NAM_resource_war_focus"): True,
                     ("NAM", "has_variable", "NAM_prewar_balance"): True,
                     ("NAM", "variable", "NAM_prewar_balance"): -0.6 if vertical else 0.6}
            self.assertTrue(self.matches(block(plan, "enable"), facts))
            facts[("NAM", "variable", "NAM_prewar_balance")] = 0.6 if vertical else -0.6
            self.assertFalse(self.matches(block(plan, "enable"), facts))
            completed = set()
            for entry in block(plan, "ai_national_focuses"):
                self.assertIn(entry.value, self.wartime)
                body = self.wartime[entry.value]
                for requirement in (e.value for e in body if e.key == "prerequisite"):
                    self.assertTrue(any(e.value in completed for e in requirement), entry.value)
                for exclusion in (e.value for e in body if e.key == "mutually_exclusive"):
                    self.assertFalse(any(e.value in completed for e in exclusion), entry.value)
                completed.add(entry.value)
            self.assertIn("NAM_oil_score", completed)

    def test_services_preserve_accumulated_values_when_independence_is_announced_again(self):
        facts = self.independent_facts()
        values = {"NAM_gar_army_org": 0.03, "NAM_gar_convoy_escort": 0.10,
                  "NAM_navy_repair_speed": 0.10, "NAM_navy_landing_speed": 0.10,
                  "NAM_air_accidents": -0.10, "NAM_air_mission_efficiency": 0.05,
                  "NAM_air_intercept_efficiency": 0.10, "NAM_air_cas_efficiency": 0.10}
        for variable, value in values.items():
            facts[("NAM", "variable", variable)] = value
        for _ in range(2):
            self.apply(self.effects["NAM_colony_close"], facts)
            for modifier in ("NAM_garrison_dynamic", "NAM_navy_dynamic", "NAM_air_dynamic"):
                self.assertTrue(facts[("NAM", "has_dynamic_modifier", modifier)])
            for variable, value in values.items():
                self.assertEqual(facts[("NAM", "variable", variable)], value)
        dynamics = parsed("common/dynamic_modifiers/ADISCORD_dynamic_modifiers_NAM.txt")
        army = block(dynamics, "NAM_garrison_dynamic")
        navy = block(dynamics, "NAM_navy_dynamic")
        self.assertNotIn("convoy_escort_efficiency", {entry.key for entry in army})
        self.assertEqual(scalar(navy, "convoy_escort_efficiency"), "NAM_gar_convoy_escort")

    def test_naval_branch_previews_equal_fleet_deltas_and_grants_no_army(self):
        navy = block(parsed("common/dynamic_modifiers/ADISCORD_dynamic_modifiers_NAM.txt"), "NAM_navy_dynamic")
        fields = {entry.value: entry.key for entry in navy if entry.key not in ("icon", "enable")}
        previewed = ("NAM_harbour_service", "NAM_repair_yard", "NAM_escort_school", "NAM_active_squadron",
                     "NAM_naval_construction", "NAM_basin_reconnaissance", "NAM_naval_staff", "NAM_basin_minefields")
        army_unlocks = {"NAM_order_coastal_battalion", "NAM_marine_detachment_order"}
        for name in (*previewed, "NAM_coastal_battalions"):
            reward = block(self.focuses[name], "completion_reward")
            entries = list(walk(reward))
            self.assertFalse(army_unlocks & {e.value for e in entries if e.key == "unlock_decision_tooltip"}, name)
            self.assertFalse({"add_manpower", "army_experience"} & {e.key for e in entries}, name)
            self.assertNotIn("FOCUS_FILTER_ARMY_XP", {e.value for e in block(self.focuses[name], "search_filters")}, name)
            if name not in previewed:
                continue
            ideas = [e.value for e in entries if e.key == "add_idea"]
            self.assertEqual(len(ideas), 1, name)
            deltas = {fields[scalar(e.value, "var")]: Decimal(scalar(e.value, "value"))
                      for e in entries if e.key == "add_to_variable" and scalar(e.value, "var") in fields}
            preview = {e.key: Decimal(e.value) for e in block(self.ideas[ideas[0]], "modifier")}
            self.assertEqual(preview, deltas, name)
        rolls = [e.value for e in block(self.focuses["NAM_reserve_rolls"], "completion_reward")
                 if e.key == "unlock_decision_tooltip"]
        self.assertIn("NAM_order_coastal_battalion", rolls)

    def test_air_and_naval_choices_rejoin_and_remain_optional_to_land_preparation(self):
        pairs = (("NAM_escort_school", "NAM_active_squadron"),
                 ("NAM_air_interceptors", "NAM_air_support"))
        for choices in product(*pairs):
            blocked = {other for pair, chosen in zip(pairs, choices) for other in pair if other != chosen}
            completed = reachable(self.focuses, blocked)
            for final in ("NAM_air_operations", "NAM_coastal_battalions", "NAM_naval_construction", "NAM_basin_minefields", "NAM_island_accounts", "NAM_quartermaster"):
                self.assertIn(final, completed)
            for pair, chosen in zip(pairs, choices):
                self.assertEqual({entry.value for entry in block(self.focuses[chosen], "mutually_exclusive")},
                                 set(pair) - {chosen})
        for name in ("NAM_air_operations", "NAM_naval_construction"):
            requirements = [entry for entry in self.focuses[name] if entry.key == "prerequisite"]
            alternatives = [entry.value for entry in requirements if len(entry.value) == 2]
            self.assertEqual(len(alternatives), 1)
        self.assertEqual(scalar(block(self.focuses["NAM_island_accounts"], "prerequisite"), "focus"), "NAM_harbour_service")
        for choice in pairs[1]:
            days = sum(int(scalar(self.focuses[name], "cost")) * 7 for name in
                       ("NAM_flight_school", "NAM_air_ground_service", choice, "NAM_air_operations"))
            self.assertEqual(days, 49)
            ready = days - int(scalar(self.focuses["NAM_air_operations"], "cost")) * 7
            land_route = self.preparation_route("districts", "export_quays", "mobile_columns", lean=True)
            land_days = sum(int(scalar(self.focuses[name], "cost")) * 7 for name in land_route)
            self.assertLess(land_days + ready, 700)
        plans = read("common/ai_strategy_plans/ADISCORD_NAM_plans.txt")
        self.assertIn("\n\t\tNAM_naval_staff\n", plans)
        self.assertNotIn("\n\t\tNAM_active_squadron\n", plans)
        self.assertNotIn("\n\t\tNAM_air_support\n", plans)

    def test_aircraft_purchases_check_exact_prices_and_deliver_only_to_nam(self):
        for name, focus_id, equipment in (
            ("NAM_air_fighter_order", "NAM_air_interceptors", "ADISCORD_fighter_airframe_2163"),
            ("NAM_air_cas_order", "NAM_air_support", "ADISCORD_cas_airframe_2170"),
        ):
            decision = self.decisions[name]
            self.assertEqual(scalar(decision, "cost"), "0")
            self.assertEqual(scalar(decision, "days_re_enable"), "90")
            self.assertIn(focus_id, [e.value for e in walk(block(decision, "visible")) if e.key == "has_completed_focus"])
            for pp, treasury, fuel, affordable in ((30, 300, 1000, True), (29.99, 300, 1000, False),
                                                   (30, 299.99, 1000, False), (30, 300, 999.99, False)):
                facts = self.independent_facts()
                facts[("NAM", "has_completed_focus", focus_id)] = True
                facts[("NAM", "numeric", "has_political_power")] = pp
                facts[("NAM", "variable", "ADISCORD_economy_treasury")] = treasury
                facts[("NAM", "numeric", "has_fuel")] = fuel
                self.assertEqual(self.matches(block(decision, "custom_cost_trigger"), facts), affordable)
                self.apply(block(decision, "complete_effect"), facts)
                self.assertEqual(facts.get(("NAM", "equipment", equipment), 0), 24 if affordable else 0)
                self.assertEqual(facts[("NAM", "numeric", "has_political_power")], pp - (30 if affordable else 0))
                self.assertEqual(facts[("NAM", "variable", "ADISCORD_economy_treasury")], treasury - (300 if affordable else 0))
                self.assertEqual(facts[("NAM", "numeric", "has_fuel")], fuel - (1000 if affordable else 0))
            for predicate in (("has_capitulated", "no"), ("is_subject", "no"), ("has_country_flag", "NAM_center_vanished")):
                facts = self.independent_facts()
                facts[("NAM", "has_completed_focus", focus_id)] = True
                facts[("NAM", *predicate)] = False
                self.assertFalse(self.matches(block(decision, "available"), facts))
                self.apply(block(decision, "complete_effect"), facts)
                self.assertNotIn(("NAM", "equipment", equipment), facts)

    def test_service_modifier_fields_and_icons_are_attested_in_the_engine(self):
        vocabulary = json.loads(read("tools/data/adiscord_modifier_fields.json"))
        definitions = parsed("common/dynamic_modifiers/ADISCORD_dynamic_modifiers_NAM.txt")
        for name in ("NAM_garrison_dynamic", "NAM_navy_dynamic", "NAM_air_dynamic"):
            for entry in block(definitions, name):
                if entry.key == "icon":
                    self.assertIn(entry.value, vocabulary["sprites"])
                elif entry.key != "enable":
                    self.assertIn(entry.key, vocabulary["country"], (name, entry.key))

    def test_every_policy_combination_reaches_the_branch_finals(self):
        pairs = (("vertical", "districts"), ("export_quays", "domestic_refining"),
                 ("field_guards", "mobile_columns"), ("supports_oil_compact", "supports_export_houses"),
                 ("court_azhar", "fuel_leverage"), ("island_levy_office", "island_concession"))
        # Course-gated alternatives follow the ladder course chosen in the first pair.
        course = {
            "vertical": {"NAM_district_guarantees", "NAM_weber_channel", "NAM_district_volunteers"},
            "districts": {"NAM_emergency_writ", "NAM_cache_hunters", "NAM_martial_seals"},
        }
        finals = ("NAM_seal_courts", "NAM_civilian_combine", "NAM_quartermaster",
                  "NAM_pillar_arbitration", "NAM_general_staff_plan", "NAM_island_accounts", "NAM_rom_address")
        for choices in product(*pairs):
            blocked = {"NAM_" + other for pair, chosen in zip(pairs, choices) for other in pair if other != chosen}
            completed = reachable(self.focuses, blocked | course[choices[0]])
            for final in finals:
                self.assertIn(final, completed, choices)
            underground_final = "NAM_field_gendarmes" if choices[0] == "vertical" else "NAM_mine_councils"
            other_final = "NAM_mine_councils" if choices[0] == "vertical" else "NAM_field_gendarmes"
            self.assertIn(underground_final, completed, choices)
            self.assertNotIn(other_final, completed, choices)
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

    def test_klyuchevsk_strike_follows_the_field_controller_and_ends_on_liberation(self):
        focuses = self.exile_trees["exile_radical"][1]
        strike = focuses["NAM_exile_klyuchevsk_strike"]
        underground = focuses["NAM_exile_armed_underground"]
        modifier = block(parsed("common/dynamic_modifiers/ADISCORD_dynamic_modifiers_NAM.txt"),
                         "NAM_klyuchevsk_oil_strike")
        self.assertEqual(scalar(modifier, "state_resources_factor"), "-0.50")
        for controller, owner, at_war, allied, subject, won, active in (
            ("AZH", "EFL", False, False, False, False, True),
            ("VAL", "EFL", True, False, False, False, True),
            ("VAL", "EFL", False, False, False, False, False),
            ("VAL", "VAL", False, False, False, False, False),
            ("KDR", "KDR", False, False, False, False, False),
            ("AZH", "EFL", False, True, False, False, False),
            ("AZH", "EFL", False, False, True, False, False),
            ("NAM", "EFL", False, False, False, False, False),
            ("EFL", "EFL", False, False, False, True, False),
        ):
            with self.subTest(controller=controller, owner=owner, won=won, allied=allied, subject=subject):
                facts = self.facts()
                facts.update({("67", "controller"): controller, ("67", "owner"): owner,
                              ("67", "is_controlled_by", "NAM"): controller == "NAM",
                              (controller, "owns_state", "PREV"): controller == owner,
                              (controller, "exists", "yes"): True, (controller, "has_capitulated", "no"): True,
                              (controller, "is_subject", "no"): not subject,
                              (controller, "is_subject_of", "NAM"): subject,
                              (controller, "is_in_faction_with", "NAM"): allied,
                              (controller, "has_war_with", "NAM"): at_war,
                              ("67", "has_global_flag", "NAM_war_of_return_won"): won})
                self.assertEqual(self.matches(block(strike, "available"), facts), active)
                self.assertEqual(self.matches(block(modifier, "enable"), facts, "67"), active)
                self.assertEqual(self.matches(block(modifier, "remove_trigger"), facts, "67"), not active)
                for focus, effect, value in ((strike, "add_fuel", "-30000"),
                                             (underground, "add_stability", "-0.03")):
                    actions = [entry for scope, entry in selected_effects(
                        self.expand(block(focus, "completion_reward")), facts, "NAM") if scope == "67"]
                    self.assertFalse(any(entry.key == "owner" for entry in actions))
                    effects = [scalar(entry.value, effect) for entry in actions if entry.key == "controller"]
                    self.assertEqual(effects, [value] if active else [])
                    if focus is strike:
                        timers = [scalar(entry.value, "days") for entry in actions if entry.key == "add_dynamic_modifier"]
                        self.assertEqual(timers, ["180"] if active else [])
                if active and not at_war:
                    facts[(controller, "has_global_flag", "NAM_war_of_return_started")] = True
                    self.assertFalse(self.matches(block(modifier, "enable"), facts, "67"))
                    facts[(controller, "has_war_with", "NAM")] = True
                    self.assertTrue(self.matches(block(modifier, "enable"), facts, "67"))

    def test_penal_mines_pay_only_for_controlled_sites_and_never_block_the_capital(self):
        focuses = self.exile_trees["exile_radical"][1]
        mines = focuses["NAM_rad_penal_mines"]
        for east, north in product(range(4), repeat=2):
            facts = self.independent_facts()
            expected = []
            for state, status, resource in (("227", east, "tungsten"), ("229", north, "chromium")):
                facts[(state, "is_owned_by", "NAM")] = bool(status & 1)
                facts[(state, "is_controlled_by", "NAM")] = bool(status & 2)
                if status == 3:
                    expected.append((state, resource, "2"))
            with self.subTest(east=east, north=north):
                self.assertEqual(self.matches(block(mines, "available"), facts), bool(expected))
                self.assertEqual(self.matches(block(mines, "bypass"), facts), not expected)
                reward = [e for _, e in selected_effects(self.expand(block(mines, "completion_reward")), facts, "NAM")]
                delivered = [(scalar(e.value, "state"), scalar(e.value, "type"), scalar(e.value, "amount"))
                             for e in reward if e.key == "add_resource"]
                self.assertEqual(delivered, expected)
                self.assertEqual(any(e.key == "add_stability" for e in reward), bool(expected))
                self.assertEqual(any(e.key == "NAM_groups_refresh" for e in reward), bool(expected))
                # Completing or bypassing the mines leaves the same route open.
                completed = {"NAM_rad_military_roads", "NAM_rad_penal_mines", "NAM_rad_island_airfields"}
                requirements = [e.value for e in focuses["NAM_rad_fortress_capital"] if e.key == "prerequisite"]
                self.assertTrue(all(any(e.value in completed for e in group) for group in requirements))

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
        # The return operation requires the final focus of every exile branch.
        capstones = {
            "NAM_rad_war_of_return": ("exile_radical", {
                "NAM_exile_harbour_pilots", "NAM_rad_fortress_capital", "NAM_rad_island_fuel_dumps",
                "NAM_rad_cadet_corps", "NAM_exile_landing_craft", "NAM_exile_corsair_admiralty"}),
            "NAM_hum_war_of_return": ("exile_humanist", {
                "NAM_hum_return_manifesto", "NAM_exile_overseas_districts", "NAM_hum_free_city_charter",
                "NAM_hum_army_of_citizens", "NAM_hum_charter_commission"}),
        }
        for name, (kind, expected) in capstones.items():
            groups = [[e.value for e in g] for g in (e.value for e in self.exile_trees[kind][1][name]
                                                      if e.key == "prerequisite")]
            self.assertTrue(all(len(group) == 1 for group in groups), name)
            self.assertEqual({group[0] for group in groups}, expected, name)
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
                                "NAM_board_shareholders", "NAM_board_district_auction",
                                "NAM_board_reconstruction_tenders"),
        }
        for kind, names in gates.items():
            for name in names:
                self.assertIn(name, self.exile_trees[kind][1], (kind, name))
        # The takeover replaces the humanist tree; its completions must survive.
        self.assertIn(TREES["exile_humanist"][0].removeprefix("focus_trees/"), SHARED_HISTORY_SOURCES)

    @staticmethod
    def board_stocks(facts):
        accounts = (("numeric", "has_fuel"), ("numeric", "has_manpower"),
                    ("variable", "NAM_corp_capital"), ("variable", "ADISCORD_economy_treasury"))
        balance = {key: facts.get(("NAM", *key), 0) for key in accounts}
        balance.update({key[1:]: value for key, value in facts.items() if key[:2] == ("NAM", "equipment")})
        return balance

    def board_facts(self):
        facts = self.facts(fuel=0)
        facts[("NAM", "has_country_flag", "NAM_exile_humanist")] = True
        facts[("NAM", "has_country_flag", "NAM_corp_takeover")] = True
        facts[("NAM", "is_subject", "no")] = True
        facts[("global", "variable", "num_days")] = 2000
        facts[("fixture", "board_callbacks")] = ()
        return facts

    def assert_board_industry(self, facts, lots, factors):
        total = Counter()
        for company, (profile, factor) in enumerate(zip(BOARD_PROFILES, factors), 1):
            for rate, (field, points) in zip(("a", "b"), profile):
                contribution = factor * points
                self.assertAlmostEqual(facts[("NAM", "variable", f"NAM_board_rate_{rate}_{company}")], contribution)
                total[field] += contribution
        for owner, (field, points) in zip(lots, (("output", 2), ("naval", 3), ("construction", 2))):
            if owner == 0:
                total[field] += points
        for field, points in total.items():
            self.assertAlmostEqual(facts[("NAM", "variable", "NAM_board_mod_" + field)], points / 100, msg=field)

    def test_board_ballots_and_industrial_effects_follow_live_assets_and_ministers(self):
        companies = range(1, 7)
        ministers = ("minister_NAM_Boris_Nar", "minister_NAM_Fedot_Mir", "minister_NAM_Pavel_Ordyntsev",
                     "minister_NAM_Mara_Kluch", "NAM_board_labor_nominee", "NAM_board_bank_nominee")
        districts = ("EFL", "AZH", "RHM", "SDR", "KDR")
        cases = [
            ((0, 0, 0), set(), ()),
            ((0, 0, 0), {1, 2, 3, 4}, ()),
            # Only Eflor and Azhar remain undisputed federal holdings.
            ((0, 4, 6), {2, 4, 6}, (6, 6, 4, 4, 4)),
            ((2, 3, 6), {3, 5, 6}, (4, 4, 1, 1, 1)),
        ]
        for company, auction in enumerate((2, 0, 1, 1, 0, 2), 1):
            lots = [0, 0, 0]
            lots[auction] = company
            cases.append((tuple(lots), {company}, (company, company)))
            cases.append((tuple(lots), {1, 2, 3, 4} - {company}, (company, company)))

        def board_values(facts, column):
            return tuple(facts[("NAM", "variable", f"NAM_board_{column}_{i}")] for i in companies)

        for lots, hired, owners in cases:
            with self.subTest(lots=lots, hired=hired, owners=owners):
                facts = self.board_facts()
                self.apply(self.effects["NAM_board_initialize"], facts)
                self.assertEqual(facts[("fixture", "board_callbacks")], (("days", 30),))
                self.assertEqual(board_values(facts, "rank"), (1, 3, 5, 2, 4, 6))
                for lot, buyer in zip(("rail", "yards", "depots"), lots):
                    key = ("NAM", "variable", "NAM_board_lot_" + lot)
                    self.assertEqual(facts[key], 0)
                    facts[key] = buyer
                for i, minister in enumerate(ministers, 1):
                    facts[("NAM", "has_idea", minister)] = i in hired
                facts[("NAM", "array", "NAM_federal_districts")] = districts[:len(owners)]
                for tag, owner in zip(districts, owners):
                    facts[(tag, "exists", "yes")] = tag != "KDR"
                    facts[(tag, "is_subject_of", "NAM")] = tag != "SDR"
                    facts[(tag, "has_country_flag", "NAM_federal_district")] = True
                    facts[(tag, "has_country_flag", "NAM_corp_disputed")] = tag == "RHM"
                    facts[(tag, "has_variable", "NAM_corp_district_owner")] = True
                    facts[(tag, "variable", "NAM_corp_district_owner")] = owner
                sectors = tuple(((1, 3, 5) + lots).count(i) for i in companies)
                concessions = tuple(owners[:2].count(i) for i in companies)
                votes = tuple(3 * s + 2 * d + int(i in hired)
                              for i, s, d in zip(companies, sectors, concessions))
                ranking = tuple(sorted(companies, key=lambda i: (-votes[i - 1], i)))
                opening = self.board_stocks(facts)
                self.apply(self.effects["NAM_board_recount"], facts)
                for name, expected in (("sectors", sectors), ("districts", concessions), ("votes", votes),
                                       ("rank", ranking)):
                    self.assertEqual(board_values(facts, name), expected)
                self.assertEqual(self.board_stocks(facts), opening)
                # A concession can establish a mandate on its own. Extra districts contribute votes.
                mandates = [max(sector, int(district > 0)) for sector, district in zip(sectors, concessions)]
                levels = [mandate + int(mandate > 0 and i == ranking[0]) for i, mandate in zip(companies, mandates)]
                active = [level if i in hired else 0 for i, level in zip(companies, levels)]
                self.assert_board_industry(facts, lots, active)
                deadline = ("NAM", "array", "NAM_board_objection_days")
                today = ("global", "variable", "num_days")
                self.assertEqual(facts[deadline][1:],
                                 tuple(facts[today] + 30 if level and i not in hired else 0
                                       for i, level in zip(companies, levels)))
                deadlines = facts[deadline]
                callbacks = facts[("fixture", "board_callbacks")]
                facts[today] += 29
                self.apply(self.effects["NAM_board_recount"], facts)
                self.assertEqual(facts[deadline], deadlines)
                self.assert_board_industry(facts, lots, active)
                facts[today] += 1
                mature = [level if i in hired else -level / 2 for i, level in zip(companies, levels)]
                for _ in range(2):
                    self.apply(self.effects["NAM_board_recount"], facts)
                    self.assert_board_industry(facts, lots, mature)
                    self.assertEqual(self.board_stocks(facts), opening)
                    self.assertEqual(facts[("fixture", "board_callbacks")], callbacks)

    @staticmethod
    def operating_board_district(facts, district, capital):
        facts.update({
            (district, "exists", "yes"): True,
            (district, "is_subject_of", "NAM"): True,
            (district, "has_country_flag", "NAM_federal_district"): True,
            (district, "has_capitulated", "no"): True,
            (district, "capital"): capital,
            (capital, "is_owned_by", "PREV"): True,
            (capital, "is_controlled_by", "PREV"): True,
        })

    def test_political_charters_require_current_jurisdiction_at_both_ends(self):
        tree = self.exile_trees["exile_corporate"][1]
        districts = (
            ("eflor", "EFL", "701", ("oil", "steel")), ("azhar", "AZH", "69", ("shipping", "bank")),
            ("sardan", "SDR", "260", ("arsenal", "artel")), ("rakhma", "RHM", "253", ("oil", "steel")),
            ("kadir", "KDR", "241", ("shipping", "bank")),
        )
        for key, district, capital, operators in districts:
            for operator in operators:
                name = f"NAM_board_{key}_{operator}"
                focus = tree[name]
                reward = block(focus, "completion_reward")
                self.assertEqual([e.key for e in reward], ["if"], name)
                release = block(block(reward, "if"), "limit")
                facts = self.board_facts()
                self.operating_board_district(facts, district, capital)
                slots = (capital, "variable", "fixture_building_slots_arms_factory_yes")
                facts.update({slots: 1, ("701", "is_owned_by", "EFL"): True,
                              ("701", "is_controlled_by", "EFL"): True})
                cases = [((district, "is_subject_of", "NAM"), False, True),
                         ((district, "has_country_flag", "NAM_federal_district"), False, True),
                         ((district, "has_capitulated", "no"), False, False),
                         ((capital, "is_controlled_by", "PREV"), False, False),
                         ((district, "has_country_flag", "NAM_corp_disputed"), True, False),
                         (("NAM", "is_subject", "no"), False, False)]
                if operator == "steel":
                    cases.append((slots, 0, False))
                if name == "NAM_board_eflor_oil":
                    cases.append((("701", "is_controlled_by", "EFL"), False, False))
                self.assertTrue(self.matches(block(focus, "available"), facts), name)
                self.assertTrue(self.matches(release, facts), name)
                for fact, value, gone in cases:
                    denied = {**facts, fact: value}
                    self.assertFalse(self.matches(block(focus, "available"), denied), (name, fact))
                    self.assertFalse(self.matches(release, denied), (name, fact))
                    snapshot = dict(denied)
                    self.apply(reward, denied)
                    self.assertEqual(denied, snapshot)
                    if district in ("SDR", "RHM", "KDR"):
                        self.assertEqual(self.matches(block(focus, "bypass"), denied), gone, (name, fact))

    def test_eflor_quota_tracks_the_field_and_operator_without_stacking(self):
        facts = self.board_facts()
        self.operating_board_district(facts, "EFL", "701")
        entitlement = ("NAM", "has_completed_focus", "NAM_board_eflor_oil")
        control = ("701", "is_controlled_by", "EFL")
        owner = ("EFL", "variable", "NAM_corp_district_owner")
        dispute = ("EFL", "has_country_flag", "NAM_corp_disputed")
        subject = ("EFL", "is_subject_of", "NAM")
        base = ("NAM", "variable", "NAM_oil_bonus_units")
        facts.update({("701", "is_owned_by", "EFL"): True, control: True, owner: 1, base: 3})
        effect = self.effects["NAM_board_sync_eflor_quota"]
        refresh = self.effects["NAM_oil_refresh"]
        self.assertEqual(scalar(next(e.value for e in refresh if e.key == "set_variable"
                                     and scalar(e.value, "var") == "NAM_oil_throughput"), "value"), "NAM_oil_bonus_units")
        with patch.dict(self.effects, {"NAM_oil_refresh": []}):
            for key, value, expected in ((entitlement, False, 3), (entitlement, True, 4), (dispute, True, 3),
                                         (dispute, False, 4), (control, False, 3), (control, True, 4),
                                         (owner, 2, 3), (owner, 1, 4), (subject, False, 3), (subject, True, 4)):
                facts[key] = value
                for _ in range(2):
                    self.apply(effect, facts)
                    self.assertEqual(facts[base], expected)

    def test_district_status_event_resolves_the_current_title_after_liberation(self):
        event_id = BASE + ".112"
        event = self.events[event_id]
        self.assertEqual(scalar(event, "hidden"), "yes")
        self.assertEqual(scalar(event, "is_triggered_only"), "yes")
        self.assertEqual(scalar(block(event, "trigger"), "has_variable"), "NAM_corp_district_owner")
        self.assertEqual(scalar(block(event, "immediate"), "NAM_board_sync_district_status"), "yes")
        actions = block(parsed("common/on_actions/03_ADISCORD_nam_resource_war_on_actions.txt"), "on_actions")
        for hook in ("on_puppet", "on_release_as_puppet", "on_subject_free", "on_release_as_free",
                     "on_liberate", "on_subject_autonomy_level_change"):
            self.assertEqual(scalar(block(block(actions, hook), "effect"), "NAM_board_subject_change"), "yes")
        subject_change = self.effects["NAM_board_subject_change"]
        calls = [e for e in walk(subject_change) if e.key == "country_event" and scalar(e.value, "id") == event_id]
        self.assertEqual([scalar(e.value, "hours") for e in calls], ["1"])
        self.assertFalse(any(e.key == "drop_cosmetic_tag" for e in walk(subject_change)))

        sync = self.effects["NAM_board_sync_district_status"]
        profiles = self.effects["NAM_corp_district_set_name"]
        tags = ("EFL", "AZH", "RHM", "SDR", "KDR")
        self.assertEqual({e.value for e in walk(self.triggers["NAM_board_has_charter_cosmetic"])
                          if e.key == "has_cosmetic_tag"},
                         {f"{tag}_NAM_corp_{i}" for tag in tags for i in range(1, 7)})
        for tag in tags:
            for operator in range(1, 7):
                charter = f"{tag}_NAM_corp_{operator}"
                facts = self.board_facts()
                facts.update({(tag, "exists", "yes"): True,
                              (tag, "has_country_flag", "NAM_federal_district"): True,
                              (tag, "variable", "NAM_corp_district_owner"): operator})
                for subject, cosmetic in ((False, charter), (False, "foreign_cosmetic"), (True, "foreign_cosmetic")):
                    # Both loss and reacquisition may occur before the queued callback.
                    current = {**facts, (tag, "is_subject_of", "NAM"): subject,
                               (tag, "has_cosmetic_tag", cosmetic): True}
                    actions = [(scope, e.key) for scope, e in selected_effects(self.expand(sync), current, tag)]
                    self.assertEqual((tag, "drop_cosmetic_tag") in actions, not subject and cosmetic == charter)
                    self.assertEqual((tag, "NAM_corp_district_set_name") in actions, subject)
                    self.assertIn((tag, "force_update_dynamic_modifier"), actions)
                    self.assertIn((tag, "ADISCORD_economy_mark_dirty"), actions)
                    if subject:
                        names = [e.value for _, e in selected_effects(self.expand(profiles), current, tag)
                                 if e.key == "set_cosmetic_tag"]
                        self.assertEqual(names, [charter])

    def test_rakhma_oil_and_charter_shipment_retain_the_overflow_for_later_unloading(self):
        reward = block(self.exile_trees["exile_corporate"][1]["NAM_board_rakhma_oil"], "completion_reward")
        shipment = self.effects["NAM_board_ship_district_order"]
        tank = ("NAM", "numeric", "has_fuel")
        reserve = ("NAM", "variable", "NAM_open_fuel_reserve")
        for room in (0, 5000, 10000):
            facts = self.board_facts()
            self.operating_board_district(facts, "RHM", "253")
            facts.update({tank: 100000 - room, ("NAM", "fuel_capacity"): 100000, reserve: 1000})
            self.apply(self.effects["NAM_board_initialize"], facts)
            self.apply(reward, facts)
            self.assertEqual((facts[tank], facts[reserve]), (100000, 31000 - room))
            self.assertEqual(facts[("RHM", "variable", "NAM_corp_district_owner")], 1)
            self.apply(shipment, facts, "RHM")
            self.assertEqual((facts[tank], facts[reserve]), (100000, 43000 - room))
            facts[tank] -= 50000
            self.apply(self.effects["NAM_open_fuel_release"], facts)
            self.apply(self.effects["NAM_open_fuel_release"], facts)
            self.assertEqual((facts[tank], facts[reserve]), (93000 - room, 0))

    def test_board_charter_delivers_the_operators_goods_to_svetlogorye(self):
        tree = self.exile_trees["exile_corporate"][1]
        reward = block(tree["NAM_board_union_of_boards"], "completion_reward")
        decisions = block(parsed(f"common/decisions/{BASE}_decisions.txt"), "NAM_free_zones")
        renew = block(block(decisions, "NAM_corp_charter_renewal"), "complete_effect")
        cargo = (
            ("numeric", "has_fuel", 12000), ("equipment", "motorized_equipment_1", 100),
            ("equipment", "convoy_1", 4), ("equipment", "artillery_equipment_1", 30),
            ("numeric", "has_manpower", 250), ("variable", "NAM_corp_capital", 15),
        )
        for operator, (kind, resource, amount) in enumerate(cargo, 1):
            facts = self.facts(fuel=0)
            facts[("NAM", "has_country_flag", "NAM_corp_takeover")] = True
            facts[("NAM", "has_country_flag", "NAM_exile_humanist")] = True
            facts[("NAM", "is_subject", "no")] = True
            facts[("NAM", "array", "NAM_federal_districts")] = ("EFL", "AZH", "RHM")
            for district in ("EFL", "AZH", "RHM", "FROM"):
                self.operating_board_district(facts, district, {"AZH": "69", "RHM": "253"}.get(district, "701"))
                facts[(district, "is_subject_of", "NAM")] = district != "RHM"
                facts[(district, "has_variable", "NAM_corp_district_owner")] = True
                facts[(district, "variable", "NAM_corp_district_owner")] = operator
                facts[(district, "has_country_flag", "NAM_corp_disputed")] = district == "AZH"
            balance = ("NAM", kind, resource)
            self.apply(reward, facts)
            self.assertEqual(facts[balance], amount)
            self.assertNotIn(("EFL", kind, resource), facts)
            for completed in (False, True):
                paid = dict(facts)
                paid[("NAM", "has_completed_focus", "NAM_board_union_of_boards")] = completed
                self.apply(renew, paid)
                renewal_capital = 40 if operator == 6 else 0
                self.assertEqual(paid[balance], amount * (1 + completed) + renewal_capital)

    def test_board_tenders_preserve_public_assets_or_transfer_title_once_without_cargo(self):
        category = block(parsed(f"common/decisions/{BASE}_decisions.txt"), "NAM_free_zones")
        cases = (
            ("rail", 24, None, (2, 5)),
            ("yards", 25, "NAM_board_island_concessions", (3, 4)),
            ("depots", 26, "NAM_board_shareholders", (1, 6)),
        )
        for lot, number, focus, bidders in cases:
            decision_name = "NAM_board_tender_" + lot
            decision = block(category, decision_name)
            event = self.events[f"ADISCORD_nam_story.{number}"]
            options = [e.value for e in event if e.key == "option"]
            self.assertEqual([scalar(option, "name") for option in options], [
                "NAM_board_tender_keep", *(f"NAM_board_tender_accept_{bidder}" for bidder in bidders)])
            self.assertNotIn("trigger", [entry.key for entry in options[0]])
            self.assertEqual(scalar(decision, "cost"), "0")
            source = (block(self.exile_trees["exile_corporate"][1][focus], "completion_reward") if focus
                      else block(self.events[BASE + ".103"], "option"))
            self.assertIn(decision_name, [e.value for e in source if e.key == "unlock_decision_tooltip"])
            owner = ("NAM", "variable", "NAM_board_lot_" + lot)
            facts = self.board_facts()
            self.apply(self.effects["NAM_board_initialize"], facts)
            facts[("NAM", "has_country_flag", "NAM_corp_takeover")] = False
            facts[("NAM", "has_country_flag", "NAM_exile_humanist")] = True
            facts[("NAM", "is_subject", "no")] = True
            self.assertFalse(self.matches(block(decision, "visible"), facts))
            facts[("NAM", "has_country_flag", "NAM_corp_takeover")] = True
            if focus:
                self.assertFalse(self.matches(block(decision, "visible"), facts))
                facts[("NAM", "has_completed_focus", focus)] = True
            self.assertTrue(self.matches(block(decision, "visible"), facts))
            dispatch = block(decision, "complete_effect")
            ai = block(block(decision, "ai_will_do"), "modifier")
            stop = [e for e in ai if e.key != "factor"]
            self.assertEqual(scalar(ai, "factor"), "0")
            funded = dict(facts)
            funded[("NAM", "has_war", "yes")] = True
            funded[("NAM", "has_war", "no")] = False
            self.assertTrue(self.matches(stop, funded))
            if lot == "depots":
                bank_gate = block(block(options[2], "ai_chance"), "modifier")
                bank_stop = [e for e in bank_gate if e.key != "factor"]
                for war, pp in product((False, True), (74, 75)):
                    budget = dict(facts)
                    budget[("NAM", "has_war", "yes")] = war
                    budget[("NAM", "has_war", "no")] = not war
                    budget[("NAM", "numeric", "has_political_power")] = pp
                    self.assertEqual(self.matches(stop, budget), war or pp < 75)
                    self.assertEqual(self.matches(bank_stop, budget), war or pp < 75)
            for bidder in bidders:
                represented = dict(funded)
                minister = scalar(self.triggers[f"NAM_board_minister_{bidder}"], "has_idea")
                represented[("NAM", "has_idea", minister)] = True
                self.assertFalse(self.matches(stop, represented))
                for option, buyer in zip(options[1:], bidders):
                    ignore_bid = block(block(option, "ai_chance"), "modifier")
                    self.assertEqual(scalar(ignore_bid, "factor"), "0")
                    self.assertEqual(self.matches([e for e in ignore_bid if e.key != "factor"], represented),
                                     buyer != bidder)
            shown = [scalar(e.value, "id") for _, e in selected_effects(self.expand(dispatch), facts, "NAM")
                     if e.key == "country_event"]
            self.assertEqual(shown, [f"ADISCORD_nam_story.{number}"])
            self.apply(dispatch, facts)
            self.assertEqual(facts[owner], 0)
            self.assertEqual(facts[("NAM", "numeric", "has_political_power")], 1000)
            self.assertEqual(facts[("NAM", "variable", "ADISCORD_economy_treasury")], 10000)
            self.assertFalse(self.matches(block(decision, "visible"), facts))
            keep = dict(facts)
            self.apply(options[0], keep)
            self.assertEqual(keep[owner], 0)
            cooldown = next(e.value for e in walk(options[0]) if e.key == "set_country_flag")
            self.assertEqual(scalar(cooldown, "days"), "30")
            self.assertFalse(self.matches(block(decision, "visible"), keep))
            keep[("NAM", "has_country_flag", scalar(cooldown, "flag"))] = False
            self.assertTrue(self.matches(block(decision, "visible"), keep))
            for index, bidder in enumerate(bidders, 1):
                option = options[index]
                today = ("global", "variable", "num_days")
                objections = ("NAM", "array", "NAM_board_objection_days")
                at_deadline = dict(facts)
                at_deadline[today] += 30
                self.apply(block(self.events[BASE + ".111"], "immediate"), at_deadline)
                self.apply(option, at_deadline)
                rate = ("NAM", "variable", f"NAM_board_rate_a_{bidder}")
                if bidder in (1, 3, 5):
                    self.assertEqual(at_deadline[objections][bidder], facts[objections][bidder])
                    self.assertEqual(at_deadline[rate], -1.5 * BOARD_PROFILES[bidder - 1][0][1])
                else:
                    self.assertEqual(at_deadline[objections][bidder], at_deadline[today] + 30)
                    self.assertEqual(at_deadline[rate], 0)
                for changed in (("NAM", "is_subject", "no"), ("NAM", "has_capitulated", "no"),
                                ("NAM", "has_country_flag", "NAM_corp_takeover")):
                    stale = dict(facts)
                    stale[changed] = False
                    self.assertFalse(self.matches(block(option, "trigger"), stale))
                    before = dict(stale)
                    self.apply(option, stale)
                    self.assertEqual(stale, before)
                result = dict(facts)
                self.assertTrue(self.matches(block(option, "trigger"), result))
                opening = self.board_stocks(result)
                self.apply(option, result)
                self.assertEqual(result[owner], bidder)
                self.assertEqual(self.board_stocks(result), opening)
                self.assertFalse(self.matches(block(decision, "visible"), result))
                settled = dict(result)
                self.apply(options[1], result)
                self.apply(options[2], result)
                self.assertEqual(result, settled)

    def test_board_ministers_share_two_seats_and_recount_after_staff_changes(self):
        slots = {}
        for filename in ("ADISCORD_ministers_all_countries.txt", f"{BASE}_ideas.txt"):
            for slot in block(parsed("common/ideas/" + filename), "ideas"):
                if slot.key.startswith("political_advisor_"):
                    slots.update((idea.key, (slot.key, idea.value)) for idea in slot.value)
        expected = ("economy", "education", "foreign_affairs", "defense", "education", "economy")
        for i, ministry in enumerate(expected, 1):
            minister = scalar(self.triggers[f"NAM_board_minister_{i}"], "has_idea")
            slot, idea = slots[minister]
            self.assertEqual(slot, "political_advisor_minister_of_" + ministry)
            for callback in ("on_add", "on_remove"):
                self.assertIn("NAM_board_queue_recount", [e.key for e in walk(block(idea, callback))])

        queue = block(self.effects["NAM_board_queue_recount"], "if")
        dispatch = block(queue, "country_event")
        self.assertEqual(scalar(dispatch, "hours"), "1")
        event = self.events[scalar(dispatch, "id")]
        self.assertEqual(scalar(block(event, "immediate"), "NAM_board_recount"), "yes")
        self.assertNotIn("NAM_board_monthly_orders", self.effects)
        monthly = [e for e in walk(self.effects["NAM_corp_monthly"]) if e.key == "NAM_board_recount"]
        self.assertEqual(len(monthly), 1)
        dividends = self.effects["NAM_corp_district_dividend"]
        for key in ("add_fuel", "add_manpower", "add_equipment_to_stockpile"):
            self.assertNotIn(key, {e.key for e in walk(dividends)})

        modifier = block(parsed("common/dynamic_modifiers/ADISCORD_dynamic_modifiers_NAM.txt"),
                         "NAM_board_industrial_policy")
        for field, suffix in (("industrial_capacity_factory", "output"),
                              ("production_factory_efficiency_gain_factor", "growth"),
                              ("industrial_capacity_dockyard", "naval"),
                              ("production_speed_dockyard_factor", "dockyards"),
                              ("production_factory_max_efficiency_factor", "ceiling"),
                              ("production_speed_buildings_factor", "construction"),
                              ("consumer_goods_factor", "goods")):
            self.assertEqual(scalar(modifier, field), "NAM_board_mod_" + suffix)

    def test_board_vacancies_recover_when_the_representative_returns_or_the_contract_ends(self):
        facts = self.board_facts()
        self.apply(self.effects["NAM_board_initialize"], facts)
        facts[("NAM", "array", "NAM_federal_districts")] = ["EFL", "AZH"]
        for tag in ("EFL", "AZH"):
            facts[(tag, "exists", "yes")] = True
            facts[(tag, "is_subject_of", "NAM")] = True
            facts[(tag, "has_country_flag", "NAM_federal_district")] = True
            facts[(tag, "has_variable", "NAM_corp_district_owner")] = True
            facts[(tag, "variable", "NAM_corp_district_owner")] = 6
        opening = self.board_stocks(facts)
        bank = ("NAM", "has_idea", "NAM_board_bank_nominee")
        deadline = ("NAM", "array", "NAM_board_objection_days")
        today = ("global", "variable", "num_days")
        # Two concessions elect a chairman without an industrial sector.
        facts[bank] = True
        self.apply(self.effects["NAM_board_recount"], facts)
        self.assertEqual(facts[("NAM", "variable", "NAM_board_rank_1")], 6)
        self.assert_board_industry(facts, (0, 0, 0), (0, 0, 0, 0, 0, 2))
        facts[bank] = False
        callbacks = facts[("fixture", "board_callbacks")]
        self.apply(self.effects["NAM_board_recount"], facts)
        self.assertEqual(facts[("fixture", "board_callbacks")], (*callbacks, ("days", 30)))
        self.assertEqual(facts[deadline][6], facts[today] + 30)
        self.assert_board_industry(facts, (0, 0, 0), (0, 0, 0, 0, 0, 0))
        facts[today] += 30
        self.apply(self.effects["NAM_board_recount"], facts)
        self.assert_board_industry(facts, (0, 0, 0), (-0.5, 0, -0.5, 0, -0.5, -1))
        facts[bank] = True
        self.apply(self.effects["NAM_board_recount"], facts)
        self.assertEqual(facts[deadline][6], 0)
        self.assert_board_industry(facts, (0, 0, 0), (-0.5, 0, -0.5, 0, -0.5, 2))

        facts[bank] = False
        self.apply(self.effects["NAM_board_recount"], facts)
        facts[today] += 1
        self.apply(block(self.events[BASE + ".111"], "immediate"), facts)
        self.assert_board_industry(facts, (0, 0, 0), (-0.5, 0, -0.5, 0, -0.5, 0))
        facts[today] += 29
        facts[("EFL", "has_country_flag", "NAM_corp_disputed")] = True
        facts[("AZH", "is_subject_of", "NAM")] = False
        facts[("NAM", "variable", "NAM_board_lot_depots")] = 1
        facts[("NAM", "has_idea", "minister_NAM_Boris_Nar")] = True
        self.apply(self.effects["NAM_board_initialize"], facts)
        self.assertEqual(facts[("NAM", "variable", "NAM_board_lot_depots")], 1)
        self.assertEqual(facts[("NAM", "variable", "NAM_board_rank_1")], 1)
        self.assertEqual(facts[("NAM", "variable", "NAM_board_districts_6")], 0)
        self.assertEqual(facts[deadline][6], 0)
        self.assert_board_industry(facts, (0, 0, 1), (3, 0, -0.5, 0, -0.5, 0))
        self.assertEqual(self.board_stocks(facts), opening)

        event = self.events[BASE + ".111"]
        facts[("NAM", "is_subject", "no")] = False
        self.assertTrue(self.matches(block(event, "trigger"), facts))
        self.apply(block(event, "immediate"), facts)
        self.assertFalse(facts.get(("NAM", "has_dynamic_modifier", "NAM_board_industrial_policy")))
        facts[("NAM", "is_subject", "no")] = True
        self.apply(block(event, "immediate"), facts)
        self.assertTrue(facts[("NAM", "has_dynamic_modifier", "NAM_board_industrial_policy")])
        self.assert_board_industry(facts, (0, 0, 1), (3, 0, -0.5, 0, -0.5, 0))
        self.assertEqual(self.board_stocks(facts), opening)

    def test_radical_military_and_civil_rule_work_on_annexed_land(self):
        south = block(parsed(f"common/decisions/{BASE}_decisions.txt"), "NAM_southern_lands")
        levy = block(south, "NAM_rad_levy_transport")
        council = block(south, "NAM_rad_install_council")
        focuses = self.exile_trees["exile_radical"][1]
        facts = self.facts()
        facts.update({
            ("NAM", "has_country_flag", "NAM_exile_radical"): True,
            ("FROM", "has_state_flag", "NAM_conquered_state"): True,
            ("FROM", "is_owned_by", "NAM"): True,
            ("FROM", "is_controlled_by", "NAM"): True,
            ("FROM", "is_owned_by", "ROOT"): True,
            ("FROM", "numeric", "infrastructure"): 2,
        })
        for focus, name, choice in (("NAM_rad_hostage_system", "NAM_rad_levy_transport", levy),
                                    ("NAM_rad_collaborator_councils", "NAM_rad_install_council", council)):
            self.assertEqual(scalar(block(focuses[focus], "completion_reward"), "unlock_decision_tooltip"), name)
            self.assertEqual(scalar(choice, "target_array"), "NAM.NAM_conquered_states")
            self.assertFalse(self.matches(block(choice, "visible"), facts))
            facts[("NAM", "has_completed_focus", focus)] = True
            self.assertTrue(self.matches(block(choice, "visible"), facts))
            self.assertTrue(self.matches(block(choice, "available"), facts))
            for condition in ("is_owned_by", "is_controlled_by"):
                lost = {**facts, ("FROM", condition, "NAM"): False}
                self.assertFalse(self.matches(block(choice, "available"), lost))
                self.apply(block(choice, "complete_effect"), lost)
                self.assertFalse(lost.get(("FROM", "has_state_flag", "NAM_rad_local_council")))
                self.assertFalse(lost.get(("FROM", "has_state_flag", "NAM_rad_transport_levied")))

        depleted = {**facts, ("FROM", "numeric", "infrastructure"): 1}
        self.assertFalse(self.matches(block(levy, "available"), depleted))
        self.apply(block(levy, "complete_effect"), depleted)
        self.assertNotIn(("NAM", "equipment", "motorized_equipment"), depleted)
        requisitions = facts.copy()
        delivery = block(levy, "complete_effect")
        removed = [(scope, scalar(e.value, "type"), scalar(e.value, "level"))
                   for scope, e in selected_effects(self.expand(delivery), requisitions, "NAM")
                   if e.key == "remove_building"]
        self.assertEqual(removed, [("FROM", "infrastructure", "1")])
        self.apply(delivery, requisitions)
        self.assertFalse(self.matches(block(levy, "visible"), requisitions))
        self.apply(delivery, requisitions)
        self.assertEqual(requisitions[("NAM", "equipment", "motorized_equipment")], 100)

        facts[("FROM", "has_state_flag", "NAM_labour_camp_building")] = True
        self.assertFalse(self.matches(block(council, "available"), facts))
        self.apply(block(council, "complete_effect"), facts)
        self.assertFalse(facts.get(("FROM", "has_state_flag", "NAM_rad_local_council")))
        facts[("FROM", "has_state_flag", "NAM_labour_camp_building")] = False
        modifiers = ("NAM_conquered_state_modifier", "NAM_labour_camp_state")
        for modifier in modifiers:
            facts[("FROM", "has_dynamic_modifier", modifier)] = True
        self.apply(block(council, "complete_effect"), facts)
        for modifier in modifiers:
            self.assertFalse(facts[("FROM", "has_dynamic_modifier", modifier)])
        self.assertTrue(facts[("FROM", "has_state_flag", "NAM_rad_local_council")])
        self.assertFalse(self.matches(block(council, "visible"), facts))
        for decision, unlock in (("NAM_radical_labour_camp", "NAM_rad_labour_camps"),
                                 ("NAM_radical_strip_state", "NAM_rad_spoils_of_return")):
            facts[("NAM", "has_completed_focus", unlock)] = True
            self.assertFalse(self.matches(block(block(south, decision), "visible"), facts))
        self.apply(block(block(south, "NAM_radical_strip_state"), "complete_effect"), facts)
        self.assertFalse(facts.get(("FROM", "has_state_flag", "NAM_state_stripped")))
        self.assertEqual(sum(e.key == "NAM_rad_direct_rule" for e in walk(focuses["NAM_rad_machines_to_islands"])), 3)
        self.apply(self.effects["NAM_wor_take_state"], facts, "FROM")
        self.assertFalse(facts[("FROM", "has_dynamic_modifier", modifiers[0])])

    def test_kadir_tolls_require_both_ownership_and_control(self):
        focus = self.exile_trees["exile_radical"][1]["NAM_rad_kadir_tolls"]
        for owned, controlled in product((False, True), repeat=2):
            with self.subTest(owned=owned, controlled=controlled):
                facts = self.facts(treasury=0)
                facts[("NAM", "owns_state", "241")] = owned
                facts[("NAM", "controls_state", "241")] = controlled
                self.assertEqual(self.matches(block(focus, "available"), facts), owned and controlled)
                self.assertEqual(self.matches(block(focus, "bypass"), facts), not owned)
                self.apply(block(focus, "completion_reward"), facts)
                self.assertEqual(facts[("NAM", "variable", "ADISCORD_economy_treasury")], 0)

    def test_southern_requisition_and_kadir_tolls_compete_for_the_actual_markets(self):
        focuses = self.exile_trees["exile_radical"][1]
        tribute = focuses["NAM_rad_southern_tribute"]
        decision_name = "NAM_rad_garrison_requisition"
        self.assertEqual(scalar(block(tribute, "completion_reward"), "unlock_decision_tooltip"), decision_name)
        lands = block(parsed(f"common/decisions/{BASE}_decisions.txt"), "NAM_southern_lands")
        decision = block(lands, decision_name)
        self.assertEqual(scalar(decision, "target_array"), "NAM.NAM_conquered_states")
        modifier = "NAM_rad_requisitioned_market"
        installed = [e.value for e in walk(block(decision, "complete_effect")) if e.key == "add_dynamic_modifier"]
        self.assertEqual([(scalar(m, "modifier"), scalar(m, "days")) for m in installed], [(modifier, "90")])
        dynamic = block(parsed("common/dynamic_modifiers/ADISCORD_dynamic_modifiers_NAM.txt"), modifier)
        self.assertEqual((float(scalar(dynamic, "local_supplies")), float(scalar(dynamic, "local_factories"))),
                         (1.5, -0.5))
        hooks = parsed(f"common/on_actions/03_{BASE}_on_actions.txt")
        monthly = block(block(block(hooks, "on_actions"), "on_monthly_NAM"), "effect")
        self.assertEqual(sum(e.key == "NAM_rad_collect_kadir_tolls" for e in walk(monthly)), 1)
        collect = self.effects["NAM_rad_collect_kadir_tolls"]
        facts = self.facts(treasury=0)
        facts[("NAM", "has_country_flag", "NAM_exile_radical")] = True
        facts[("NAM", "has_completed_focus", "NAM_rad_southern_tribute")] = True
        facts[("NAM", "has_completed_focus", "NAM_rad_kadir_tolls")] = True
        facts[("NAM", "is_subject", "no")] = True
        for state in ("241", "249"):
            facts[(state, "is_owned_by", "NAM")] = True
            facts[(state, "is_controlled_by", "NAM")] = True
            facts[(state, "has_state_flag", "NAM_conquered_state")] = True
            facts[(state, "numeric", "industrial_complex")] = 1
            facts[(state, "numeric", "infrastructure")] = 2
        route = ("16723", "16747", "16752", "16725")
        rails = [line.split()[2:] for line in read("map/railways.txt").splitlines()]
        for a, b in zip(route, route[1:]):
            self.assertTrue(any({x, y} == {a, b} for path in rails for x, y in zip(path, path[1:])))
        for province in route:
            facts[("NAM", "controls_province", province)] = True

        treasury = ("NAM", "variable", "ADISCORD_economy_treasury")
        income = ("NAM", "variable", "ADISCORD_economy_current_month_action_income")

        def collect_month(state, expected):
            before = (state.get(treasury, 0), state.get(income, 0))
            self.apply(collect, state)
            self.assertEqual((state.get(treasury, 0), state.get(income, 0)),
                             tuple(amount + expected for amount in before))

        collect_month(facts, 50)
        for key, value, expected in (
            (("NAM", "has_completed_focus", "NAM_rad_kadir_tolls"), False, 0),
            (("NAM", "has_country_flag", "NAM_exile_radical"), False, 0),
            (("NAM", "is_subject", "no"), False, 0),
            (("NAM", "has_capitulated", "no"), False, 0),
            *((("NAM", "controls_province", province), False, 0 if province == route[0] else 20)
              for province in route),
        ):
            with self.subTest(key=key):
                collect_month({**facts, key: value}, expected)
        for state, reduced in (("241", 0), ("249", 20)):
            for key, value in ((("is_owned_by", "NAM"), False), (("is_controlled_by", "NAM"), False),
                               (("numeric", "industrial_complex"), 0), (("numeric", "infrastructure"), 1)):
                collect_month({**facts, (state, *key): value}, reduced)

            project = self.bind_field(decision, state)
            working = facts.copy()
            self.assertTrue(self.matches(block(project, "visible"), working))
            self.assertTrue(self.matches(block(project, "available"), working))
            market = "kadir" if state == "241" else "basiran"
            shown = [e.value for _, e in selected_effects(self.expand(block(project, "complete_effect")), working, "NAM")
                     if e.key == "custom_effect_tooltip"]
            self.assertEqual(shown, [f"NAM_rad_{market}_requisition_tt"])
            self.apply(block(project, "complete_effect"), working)
            self.assertTrue(working[(state, "has_dynamic_modifier", modifier)])
            self.assertFalse(self.matches(block(project, "available"), working))
            self.assertTrue(self.matches(block(dynamic, "enable"), working, state))
            self.assertFalse(self.matches(block(dynamic, "remove_trigger"), working, state))
            collect_month(working, reduced)
            for key, value in ((("is_controlled_by", "NAM"), False),
                               (("is_owned_by", "NAM"), False), (("numeric", "industrial_complex"), 0),
                               (("has_state_flag", "NAM_rad_local_council"), True)):
                lost = {**working, (state, *key): value}
                self.assertFalse(self.matches(block(dynamic, "enable"), lost, state))
                self.assertTrue(self.matches(block(dynamic, "remove_trigger"), lost, state))
                lost[(state, "has_dynamic_modifier", modifier)] = False
                self.apply(block(project, "complete_effect"), lost)
                self.assertFalse(lost[(state, "has_dynamic_modifier", modifier)])
            working[(state, "has_dynamic_modifier", modifier)] = False
            collect_month(working, 50)

    def test_radical_return_preparation_preserves_every_route_without_padded_stages(self):
        from functools import lru_cache

        focuses = self.exile_trees["exile_radical"][1]
        exclusions = {
            name: {entry.value for group in focus if group.key == "mutually_exclusive" for entry in group.value}
            for name, focus in focuses.items()
        }

        @lru_cache(maxsize=None)
        def routes_to(name):
            routes = {frozenset({name})}
            for group in (entry.value for entry in focuses[name] if entry.key == "prerequisite"):
                alternatives = {route for entry in group for route in routes_to(entry.value)}
                routes = {left | right for left, right in product(routes, alternatives)
                          if all(not exclusions[node].intersection(left | right) for node in left | right)}
            return routes

        preparation = {
            ("NAM", "has_global_flag", "ADISCORD_nam_resource_war_island_exile"): True,
            ("NAM", "has_country_flag", "NAM_exile_radical"): True,
            ("NAM", "variable", "NAM_revenge_readiness"): 0,
            ("67", "controller"): "EFL",
            ("EFL", "exists", "yes"): True,
            ("EFL", "has_capitulated", "no"): True,
            ("EFL", "is_subject", "no"): True,
        }

        def readiness_gain(entries):
            return sum(float(scalar(entry.value, "value"))
                       for scope, entry in selected_effects(self.expand(entries), preparation, "NAM")
                       if scope == "NAM" and entry.key == "add_to_variable"
                       and scalar(entry.value, "var") == "NAM_revenge_readiness")

        initial = readiness_gain(self.effects["NAM_exile_choose_radical"])
        routes = routes_to("NAM_rad_war_of_return")
        gains = {name: readiness_gain(block(focuses[name], "completion_reward")) for name in set().union(*routes)}
        self.assertGreater(len(routes), 1)
        for route in routes:
            self.assertLessEqual(sum(int(scalar(focuses[name], "cost")) * 7 for name in route), 1295)
            readiness = min(100, initial + sum(gains[name] for name in route if name != "NAM_rad_war_of_return"))
            facts = {("NAM", "variable", "NAM_revenge_readiness"): readiness,
                     ("NAM", "variable", "NAM_marine_orders_paid"): 0}
            self.assertTrue(self.matches(self.triggers["NAM_landing_third_division"], facts), (readiness, route))
        with patch.object(self, "effects", {}):
            for name, army_xp, navy_xp, command in (
                ("NAM_rad_cadet_corps", 10, 0, 20), ("NAM_exile_harbour_pilots", 20, 10, 0),
            ):
                facts = {}
                self.apply(block(focuses[name], "completion_reward"), facts)
                self.assertEqual(facts.get(("NAM", "numeric", "army_experience"), 0), army_xp)
                self.assertEqual(facts.get(("NAM", "numeric", "navy_experience"), 0), navy_xp)
                self.assertEqual(facts.get(("NAM", "numeric", "command_power"), 0), command)
                self.assertEqual(facts.get(("NAM", "reward", "war_support"), 0), 0.05)
                if name == "NAM_rad_cadet_corps":
                    self.assertEqual(facts[("NAM", "tech_bonus", name)],
                                     (0.5, 2, ("infantry_weapons", "support_tech")))

    def test_investor_orders_survive_an_early_takeover_and_settle_once(self):
        programmes = block(parsed(f"common/decisions/{BASE}_decisions.txt"), "NAM_free_zones")
        park = block(programmes, "NAM_corp_innovation_park")
        arms = block(programmes, "NAM_corp_buy_arms")
        for civilian in (True, False):
            facts = {
                ("NAM", "tag", "NAM"): True,
                ("NAM", "exists", "yes"): True,
                ("NAM", "has_capitulated", "no"): True,
                ("NAM", "has_country_flag", "NAM_exile_humanist"): True,
                ("NAM", "has_country_flag", "NAM_corp_takeover"): True,
                ("NAM", "has_completed_focus", "NAM_board_humanist_facade"): civilian,
                ("NAM", "has_completed_focus", "NAM_board_purge_ministers"): not civilian,
                ("NAM", "numeric", "has_political_power"): 25,
                ("NAM", "variable", "NAM_corp_capital"): 60,
                ("NAM", "variable", "NAM_free_zones_active"): 0,
            }
            self.assertEqual(self.matches(block(park, "visible"), facts), civilian)
            self.assertEqual(self.matches(block(arms, "visible"), facts), not civilian)
            if civilian:
                self.apply(block(park, "complete_effect"), facts)
                self.assertEqual(facts[("NAM", "variable", "NAM_corp_capital")], 0)
                self.assertFalse(self.matches(block(park, "available"), facts))
                self.apply(block(park, "remove_effect"), facts)
                self.apply(block(park, "remove_effect"), facts)
                self.apply(block(park, "cancel_effect"), facts)
                self.assertTrue(facts[("NAM", "has_tech", "ADISCORD_tech_armored_rail_convoys")])
                self.assertEqual(facts[("NAM", "equipment", "armored_train_equipment_1")], 12)
                self.assertEqual(facts[("NAM", "equipment", "motorized_equipment_1")], 100)
                self.assertEqual(facts[("NAM", "variable", "NAM_corp_capital")], 0)
                facts[("NAM", "variable", "NAM_corp_capital")] = 60
                facts[("NAM", "numeric", "has_political_power")] = 25
                self.apply(block(park, "complete_effect"), facts)
                self.apply(block(park, "cancel_effect"), facts)
                self.apply(block(park, "remove_effect"), facts)
                self.assertEqual(facts[("NAM", "variable", "NAM_corp_capital")], 60)
                self.assertEqual(facts[("NAM", "equipment", "armored_train_equipment_1")], 12)
            else:
                self.apply(block(arms, "complete_effect"), facts)
                self.assertEqual(facts[("NAM", "equipment", "ADISCORD_armored_carrier_2163")], 40)
                self.assertTrue(facts[("NAM", "has_tech", "ADISCORD_tech_armored_carrier_program")])
                self.assertEqual(facts[("NAM", "variable", "NAM_corp_capital")], 0)

    def test_island_steel_contract_only_withdraws_available_steel(self):
        decision = block(block(parsed(f"common/decisions/{BASE}_decisions.txt"), "NAM_free_zones"),
                         "NAM_corp_sell_steel")
        effect = block(block(block(decision, "complete_effect"), "if"), "hidden_effect")
        delivery = block(effect, "random_owned_state")
        self.assertEqual(scalar(block(delivery, "limit"), "NAM_corp_steel_site"), "yes")
        self.assertEqual(scalar(block(delivery, "add_dynamic_modifier"), "days"), "60")
        modifier = block(parsed("common/dynamic_modifiers/ADISCORD_dynamic_modifiers_NAM.txt"),
                         "NAM_corp_steel_export_state")
        self.assertEqual({e.key for e in modifier}, {"icon", "enable", "state_resource_steel"})
        self.assertEqual(scalar(modifier, "state_resource_steel"), "-8")
        conditions = self.expand(self.triggers["NAM_corp_steel_site"])
        for state, ore, owned, controlled, committed in product(
                ("230", "688"), (0, 7.9, 8, 16), (False, True), (False, True), (False, True)):
            facts = {
                (state, "variable", "resource@steel"): ore,
                (state, "is_owned_by", "NAM"): owned,
                (state, "is_controlled_by", "NAM"): controlled,
                (state, "has_dynamic_modifier", "NAM_corp_steel_export_state"): committed,
            }
            self.assertEqual(matches_conditions(conditions, facts, state),
                             state == "230" and owned and controlled and ore >= 8 and not committed)

    def humanist_government_facts(self):
        return {
            ("NAM", "exists", "yes"): True,
            ("NAM", "has_capitulated", "no"): True,
            ("NAM", "is_subject", "no"): True,
            ("NAM", "has_country_flag", "NAM_center_vanished"): True,
            ("NAM", "has_country_flag", "NAM_exile_humanist"): True,
            ("NAM", "has_global_flag", BASE + "_island_exile"): True,
            ("225", "is_owned_by", "NAM"): True,
            ("225", "is_controlled_by", "NAM"): True,
        }

    def test_humanist_government_programmes_open_at_the_choice_and_close_at_takeover(self):
        courses = {
            "NAM_hum_exile_parliament": "NAM_hum_finance_island_cooperative",
            "NAM_hum_salvation_cabinet": "NAM_hum_refit_landing_transports",
        }
        panel = block(parsed(f"common/decisions/categories/{BASE}_categories.txt"), "NAM_national_programmes")
        focuses = self.exile_trees["exile_humanist"][1]
        for course, takeover in product(courses, (False, True)):
            facts = self.humanist_government_facts()
            facts[("NAM", "has_completed_focus", course)] = True
            facts[("NAM", "has_country_flag", "NAM_corp_takeover")] = takeover
            self.assertTrue(self.matches(block(panel, "visible"), facts))
            self.assertEqual(scalar(block(focuses[course], "completion_reward"), "unlock_decision_tooltip"), courses[course])
            for name, decision in courses.items():
                self.assertEqual(self.matches(block(self.decisions[decision], "visible"), facts),
                                 name == course and not takeover)

    def test_parliament_pays_for_a_working_island_cooperative(self):
        decision = self.decisions["NAM_hum_finance_island_cooperative"]
        for pp, treasury, factories, control, room in (
                (35, 250, 1, True, 1), (35, 250, 2, True, 1), (35, 250, 1, False, 1),
                (34.9, 250, 1, True, 1), (35, 249.9, 1, True, 1), (35, 250, 1, True, 0)):
            facts = self.humanist_government_facts()
            facts.update({
                ("NAM", "has_completed_focus", "NAM_hum_exile_parliament"): True,
                ("NAM", "numeric", "has_political_power"): pp,
                ("NAM", "variable", "ADISCORD_economy_treasury"): treasury,
                ("NAM", "variable", "NAM_corp_influence"): 20,
                ("NAM", "variable", "NAM_free_zones_active"): 0,
                ("FROM", "state", "225"): True,
                ("FROM", "is_owned_by", "NAM"): True,
                ("FROM", "is_controlled_by", "NAM"): control,
                ("FROM", "numeric", "industrial_complex"): factories,
                ("FROM", "variable", "fixture_building_slots_industrial_complex_yes"): room,
            })
            self.apply(block(decision, "complete_effect"), facts)
            built = int(control and room and pp >= 35 and treasury >= 250 and factories < 2)
            self.assertEqual(facts.get(("FROM", "building", "industrial_complex"), 0), built)
            self.assertEqual(facts[("NAM", "numeric", "has_political_power")], pp - built * 35)
            self.assertEqual(facts[("NAM", "variable", "ADISCORD_economy_treasury")], treasury - built * 250)
            self.assertEqual(facts[("NAM", "variable", "NAM_corp_influence")], 20 - built * 4)

    def test_cabinet_refit_honours_signed_orders_and_stops_training_after_landing(self):
        refit = self.decisions["NAM_hum_refit_landing_transports"]
        self.assertEqual(scalar(block(refit, "modifier"), "civilian_factory_use"), "2")
        self.assertEqual(scalar(refit, "days_remove"), "35")
        for takeover, at_war, lost_port in product((False, True), repeat=3):
            facts = self.humanist_government_facts()
            facts[("NAM", "has_completed_focus", "NAM_hum_salvation_cabinet")] = True
            facts[("NAM", "variable", "NAM_revenge_readiness")] = 10
            for factories in (1, 2):
                facts[("NAM", "numeric", "num_of_civilian_factories_available_for_projects")] = factories
                self.assertEqual(self.matches(block(refit, "available"), facts), factories >= 2)
            self.apply(block(refit, "complete_effect"), facts)
            facts[("NAM", "has_country_flag", "NAM_corp_takeover")] = takeover
            facts[("NAM", "has_global_flag", "NAM_war_of_return_started")] = at_war
            facts[("225", "is_controlled_by", "NAM")] = not lost_port
            self.assertEqual(self.matches(block(refit, "cancel_trigger"), facts), lost_port)
            if lost_port:
                self.apply(block(refit, "cancel_effect"), facts)
            for _ in range(2):
                self.apply(block(refit, "remove_effect"), facts)
            self.assertEqual(facts.get(("NAM", "equipment", "convoy_1"), 0), 0 if lost_port else 12)
            self.assertEqual(facts[("NAM", "variable", "NAM_revenge_readiness")],
                             10 if lost_port or at_war else 18)

    def test_union_faculty_endowment_pays_once_and_follows_the_district(self):
        focus = self.exile_trees["exile_humanist"][1]["NAM_hum_union_university"]
        self.assertEqual(scalar(block(focus, "completion_reward"), "add_research_slot"), "1")
        decision = block(block(parsed(f"common/decisions/{BASE}_decisions.txt"), "NAM_southern_lands"),
                         "NAM_hum_endow_district_faculty")
        self.assertEqual(scalar(decision, "target_array"), "NAM.NAM_federal_districts")
        for subject, independent_government, treasury in product((True, False), (True, False), (299.9, 600)):
            facts = self.humanist_government_facts()
            facts.update({
                ("NAM", "has_country_flag", "NAM_corp_takeover"): not independent_government,
                ("NAM", "has_completed_focus", "NAM_hum_union_university"): True,
                ("NAM", "variable", "ADISCORD_economy_treasury"): treasury,
                ("FROM", "exists", "yes"): True,
                ("FROM", "has_capitulated", "no"): True,
                ("FROM", "has_country_flag", "NAM_federal_district"): True,
                ("FROM", "is_subject_of", "NAM"): subject,
            })
            expected = subject and independent_government and treasury >= 300
            for attempt in range(2):
                payload = list(selected_effects(self.expand(block(decision, "complete_effect")), facts, "NAM"))
                grants = [(scope, e.value) for scope, e in payload if e.key == "add_research_slot"]
                self.assertEqual(grants, [("FROM", "1")] if expected and not attempt else [])
                self.apply(block(decision, "complete_effect"), facts)
            self.assertEqual(facts[("NAM", "variable", "ADISCORD_economy_treasury")],
                             treasury - (300 if expected else 0))

    def test_company_courts_rule_by_cabinet_and_protect_only_the_winning_district(self):
        case = block(self.effects["NAM_corp_arbitrate_dispute"], "event_target:NAM_corp_dispute_district")
        for courts, purge in product((False, True), repeat=2):
            facts = {("NAM", "has_completed_focus", "NAM_board_corporate_courts"): courts,
                     ("NAM", "has_completed_focus", "NAM_board_purge_ministers"): purge}
            outcome = [e for _, e in selected_effects(case, facts, "EFL")]
            self.assertEqual(any(e.key == "random_list" for e in outcome), not courts)
            self.assertEqual(any(e.key == "NAM_corp_dispute_award_claimant" for e in outcome), courts and purge)
            self.assertEqual(any(e.key == "NAM_corp_dispute_clear" for e in outcome), courts and not purge)
            terms = [scalar(e.value, "days") for e in outcome if e.key == "set_country_flag"
                     and scalar(e.value, "flag") == "NAM_corp_court_protection"]
            self.assertEqual(terms, ["180"] if courts else [])
        candidates = block(block(self.effects["NAM_corp_open_dispute"], "random_scope_in_array"), "limit")
        facts = {("EFL", "has_variable", "NAM_corp_district_owner"): True}
        self.operating_board_district(facts, "EFL", "701")
        self.assertTrue(self.matches(candidates, facts, "EFL"))
        facts[("EFL", "has_country_flag", "NAM_corp_court_protection")] = True
        self.assertFalse(self.matches(candidates, facts, "EFL"))

    def test_old_concession_answers_cannot_collect_capital_or_reassign_a_district(self):
        event = self.events["ADISCORD_nam_resource_war.108"]
        options = {scalar(e.value, "name").rsplit(".", 1)[1]: e.value for e in event if e.key == "option"}

        def bind_case(entries):
            case_scopes = ("event_target:NAM_corp_case_district", "event_target:NAM_corp_dispute_district")
            return [replace(e, key="EFL" if e.key in case_scopes else e.key,
                            value=bind_case(e.value) if isinstance(e.value, list) else e.value) for e in entries]

        category = block(parsed(f"common/decisions/{BASE}_decisions.txt"), "NAM_free_zones")
        decision = bind_case(block(category, "NAM_corp_board_arbitration"))
        for subject, disputed, claimant, sovereign, controls in product((False, True), repeat=5):
            live = subject and disputed and claimant and sovereign and controls
            facts = self.board_facts()
            self.operating_board_district(facts, "EFL", "701")
            facts.update({
                ("NAM", "is_subject", "no"): sovereign,
                ("701", "is_controlled_by", "PREV"): controls,
                ("EFL", "exists", "yes"): True,
                ("EFL", "is_subject_of", "NAM"): subject,
                ("EFL", "has_variable", "NAM_corp_district_owner"): True,
                ("EFL", "has_country_flag", "NAM_corp_disputed"): disputed,
                ("EFL", "has_variable", "NAM_corp_dispute_claimant"): claimant,
                ("NAM", "variable", "NAM_corp_capital"): 20,
            })
            self.assertEqual(self.matches(block(decision, "available"), facts), live)
            self.assertEqual(self.matches(block(bind_case(event), "trigger"), facts), live)
            for answer in ("a", "b", "c", "closed"):
                option = bind_case(options[answer])
                self.assertEqual(self.matches(block(option, "trigger"), facts), not live if answer == "closed" else live)
                if answer in ("a", "b"):
                    settlement = block(block(block(option, "hidden_effect"), "if"), "limit")
                    self.assertEqual(self.matches(settlement, facts), live)
                    if not live:
                        self.apply(option, facts)
                        self.assertEqual(facts[("NAM", "variable", "NAM_corp_capital")], 20)
            facts[("NAM", "variable", "NAM_corp_capital")] = 30
            settlement = block(block(block(decision, "complete_effect"), "if"), "limit")
            self.assertEqual(self.matches(settlement, facts), live)
        self.assertEqual(scalar(block(self.effects["NAM_corp_open_dispute"], "random_scope_in_array"),
                                "save_event_target_as"), "NAM_corp_case_district")

        monthly = self.effects["NAM_corp_districts_monthly"]
        draw = next(entry.value for entry in monthly if entry.key == "if"
                    and any(child.key == "random_list" for child in entry.value))
        self.assertEqual(scalar(block(draw, "limit"), "has_completed_focus"), "NAM_board_constitution")
        sync = self.effects["NAM_board_sync_district_status"]
        facts = self.board_facts()
        self.operating_board_district(facts, "EFL", "701")
        facts[("EFL", "has_country_flag", "NAM_corp_disputed")] = True
        for subject, occupied in product((False, True), repeat=2):
            facts[("EFL", "is_subject_of", "NAM")] = subject
            facts[("701", "is_controlled_by", "PREV")] = not occupied
            selected = [e.key for _, e in selected_effects(self.expand(sync), facts, "EFL")]
            self.assertEqual("NAM_corp_dispute_clear" in selected, not subject)
        self.assertFalse(any(e.value == "NAM_corp_dispute_cooldown" for e in walk(self.effects["NAM_corp_dispute_clear"])))

    def test_southern_school_classes_exchange_only_known_machine_tool_technology(self):
        course = self.effects["NAM_teach_machine_tools"]
        curriculum = [next(e.key for e in block(step.value, "set_technology") if e.key != "popup")
                      for step in course]
        industry = block(parsed("common/technologies/ADISCORD_industry.txt"), "technologies")
        technologies = {e.key: e.value for e in industry}
        self.assertEqual(len(set(curriculum)), 5)
        for first, second in zip(curriculum, curriculum[1:]):
            self.assertIn(second, [e.value for e in walk(technologies[first]) if e.key == "leads_to_tech"])

        exchange = block(self.effects["NAM_khazar_school_exchange"], "SHL")
        self.assertEqual([(e.key, e.value) for e in exchange if isinstance(e.value, str)],
                         [("NAM_teach_machine_tools", "yes")])
        self.assertEqual(scalar(block(exchange, "NAM"), "NAM_teach_machine_tools"), "yes")

        def scope_partner(entries, teacher):
            return [replace(e, key=teacher if e.key == "PREV" else e.key,
                            value=scope_partner(e.value, teacher) if isinstance(e.value, list) else e.value)
                    for e in entries]

        for teacher, student in (("NAM", "SHL"), ("SHL", "NAM")):
            bound = scope_partner(course, teacher)
            for taught, studied in product(range(6), repeat=2):
                facts = {(country, "has_tech", tech): index < level
                         for country, level in ((teacher, taught), (student, studied))
                         for index, tech in enumerate(curriculum)}
                self.apply(bound, facts, student)
                learned = [tech for tech in curriculum if facts[(student, "has_tech", tech)]]
                self.assertEqual(learned, curriculum[:studied + int(taught > studied)])
                self.assertEqual([tech for tech in curriculum if facts[(teacher, "has_tech", tech)]],
                                 curriculum[:taught])

        focus = ("NAM", "has_completed_focus", "NAM_pw_southern_schools")
        paid = ("NAM", "has_country_flag", "NAM_pw_district_schools_paid")
        facts = self.independent_facts()
        facts.update({focus: True, paid: True, ("NAM", "has_global_flag", BASE + "_nam_victory"): True,
                      ("SHL", "exists", "yes"): True, ("SHL", "has_capitulated", "no"): True,
                      ("SHL", "is_subject_of", "NAM"): True, ("SHL", "owns_state", "699"): True,
                      ("SHL", "controls_state", "699"): True})
        self.assertTrue(self.matches(block(self.decisions["NAM_pw_district_schools"], "visible"), facts))
        settle = self.effects["NAM_pw_district_schools_settle"]
        # The settlement clears its receipt before the exchange. Replayed callbacks cannot teach another class.
        with patch.dict(self.effects, {"NAM_khazar_school_exchange": parse_clausewitz("add_political_power = 1")}):
            for missing in (None, focus, paid, ("SHL", "is_subject_of", "NAM"), ("SHL", "controls_state", "699")):
                state = facts.copy()
                if missing:
                    state[missing] = False
                balance = ("NAM", "numeric", "has_political_power")
                opening = state.get(balance, 0)
                self.apply(settle, state)
                self.apply(settle, state)
                self.assertEqual(state.get(balance, 0) - opening, int(missing is None))
                self.assertEqual(state.get(("NAM", "equipment", "support_equipment"), 0),
                                 0 if missing == paid else 60)

    def test_company_expedition_contracts_deliver_ships_or_a_field_regiment(self):
        focuses = self.exile_trees["exile_corporate"][1]
        regiment = focuses["NAM_board_mercenary_battalions"]
        fleet = focuses["NAM_board_private_navy"]
        regiment_reward = block(regiment, "completion_reward")
        template = next(e.value for e in walk(regiment_reward) if e.key == "division_template")
        unit = next(e.value for e in walk(regiment_reward) if e.key == "create_unit")
        self.assertEqual([e.key for e in block(template, "regiments")], ["infantry"] * 3)
        self.assertEqual([e.key for e in block(template, "support")], ["engineer"])
        self.assertNotIn("is_locked", [e.key for e in template])
        spawned = parse_clausewitz(scalar(unit, "division"))
        self.assertEqual(scalar(spawned, "name"), "1-й контрактный пехотный полк")
        self.assertEqual(scalar(spawned, "division_template"), scalar(template, "name"))
        self.assertEqual((scalar(spawned, "start_equipment_factor"), scalar(spawned, "start_manpower_factor")),
                         ("1.0", "1.0"))
        self.assertFalse(any(e.key in ("add_equipment_to_stockpile", "add_manpower") for e in walk(regiment_reward)))
        for held, port, sovereign in product((False, True), repeat=3):
            facts = self.board_facts()
            facts.update({("NAM", "is_subject", "no"): sovereign, ("NAM", "capital"): "225",
                          ("225", "is_owned_by", "NAM"): True, ("225", "is_controlled_by", "NAM"): held,
                          ("NAM", "ADISCORD_has_operational_naval_base", "yes"): port,
                          ("fixture", "track_units"): True})
            for focus, eligible, result, count in (
                (regiment, held and sovereign, ("NAM", "reward", "spawned_divisions"), 1),
                (fleet, port and sovereign, ("NAM", "ships", "ADISCORD_escort_ship_2155"), 2),
            ):
                after = dict(facts)
                self.assertEqual(self.matches(block(focus, "available"), after), eligible)
                self.apply(block(focus, "completion_reward"), after)
                self.assertEqual(after.get(result, 0), count if eligible else 0)
        naval_reward = block(fleet, "completion_reward")
        facts = self.board_facts()
        facts[("NAM", "ADISCORD_has_operational_naval_base", "yes")] = True
        facts[("NAM", "has_completed_focus", "NAM_harbour_service")] = False
        for prior in (None, "NAM_harbour_service", "NAM_defeat_harbour_economy"):
            active = {**facts, ("NAM", "has_completed_focus", prior): True}
            unlocks = [e.value for _, e in selected_effects(self.expand(naval_reward), active, "NAM")
                       if e.key == "unlock_decision_tooltip"]
            self.assertEqual(unlocks, [] if prior else ["NAM_island_convoy_service"])
            active[("NAM", "has_completed_focus", "NAM_board_private_navy")] = True
            self.assertTrue(self.matches(block(self.decisions["NAM_island_convoy_service"], "visible"), active))

    def test_corporate_expedition_and_capital_courses_rejoin_without_the_excluded_focus(self):
        focuses = self.exile_trees["exile_corporate"][1]
        military = ("NAM_board_private_navy", "NAM_board_mercenary_battalions")
        capital = ("NAM_board_company_housing", "NAM_board_company_docks")
        for force, investment in product(military, capital):
            choices = (force, investment)
            blocked = (set(military) | set(capital)) - set(choices)
            for chosen, pair in zip(choices, (military, capital)):
                self.assertEqual({e.value for e in block(focuses[chosen], "mutually_exclusive")}, set(pair) - {chosen})
            completed = reachable(focuses, blocked)
            self.assertIn("NAM_board_war_of_return", completed)
            self.assertIn("NAM_board_company_airport", completed)
            self.assertFalse(completed & blocked)
            self.assertNotIn("NAM_board_war_of_return", reachable(focuses, blocked | {"NAM_board_landing_contracts"}))
            self.assertNotIn("NAM_board_war_of_return", reachable(focuses, set(military)))
            self.assertNotIn("NAM_board_company_airport", reachable(focuses, set(capital)))
        plan = block(parsed("common/ai_strategy_plans/ADISCORD_NAM_plans.txt"), "NAM_exile_corporate_plan")
        queue = {e.value for e in block(plan, "ai_national_focuses")}
        self.assertEqual(queue & set(military), {"NAM_board_private_navy"})
        self.assertEqual(queue & set(capital), {"NAM_board_company_docks"})

    def board_capital_sites(self, sites=("228",)):
        facts = self.independent_facts()
        facts[("fixture", "board_sites")] = sites
        facts[("NAM", "capital")] = sites[0]
        facts[("NAM", "has_country_flag", "NAM_corp_takeover")] = True
        facts[("NAM", "has_country_flag", "NAM_exile_humanist")] = True
        facts[("NAM", "variable", "NAM_corp_capital")] = 50
        facts[("NAM", "variable", "NAM_free_zone_slots")] = 1
        for state in sites:
            facts[(state, "is_owned_by", "NAM")] = True
            facts[(state, "is_controlled_by", "NAM")] = True
            facts[(state, "is_coastal", "yes")] = True
            facts[(state, "numeric", "naval_base")] = 2
            for building in ("industrial_complex", "dockyard", "ADISCORD_business_center"):
                facts[(state, "variable", "fixture_building_slots_" + building + "_yes")] = 1
                facts[(state, "variable", "fixture_building_slots_" + building + "_no")] = 0
        return facts

    def test_corporate_docks_recheck_the_capitals_coast_ownership_and_control(self):
        docks = self.exile_trees["exile_corporate"][1]["NAM_board_company_docks"]
        for owned, controlled, coastal, naval_base in product((False, True), repeat=4):
            facts = self.board_capital_sites()
            facts[("228", "is_owned_by", "NAM")] = owned
            facts[("228", "is_controlled_by", "NAM")] = controlled
            facts[("228", "is_coastal", "yes")] = coastal
            facts[("228", "numeric", "naval_base")] = int(naval_base)
            ready = owned and controlled and coastal and naval_base
            self.assertEqual(self.matches(block(docks, "available"), facts), ready)
            self.apply(block(docks, "completion_reward"), facts)
            self.assertEqual(facts.get(("228", "building", "dockyard"), 0), int(ready))
            self.assertEqual(facts.get(("NAM", "equipment", "convoy"), 0), 10 * ready)

        charter = self.decisions["NAM_econ_insured_freighters"]
        for alternative in ("228", "225"):
            facts = self.board_capital_sites(("228", "225"))
            facts[("NAM", "owns_state", "700")] = False
            facts[("NAM", "has_completed_focus", "NAM_insured_cargoes")] = False
            facts[("NAM", "has_completed_focus", "NAM_board_company_docks")] = False
            self.assertFalse(self.matches(block(charter, "visible"), facts))
            facts[("228", "numeric", "dockyard")] = 20 if alternative == "225" else 0
            self.apply(block(docks, "completion_reward"), facts)
            self.assertEqual(facts[(alternative, "building", "dockyard")], 1)
            self.assertEqual(facts[(alternative, "reward", "building_slots")], 1)
            facts[("NAM", "has_completed_focus", "NAM_board_company_docks")] = True
            self.assertTrue(self.matches(block(charter, "visible"), facts))
            self.assertTrue(self.matches(block(charter, "available"), facts))
            cash = ("NAM", "variable", "ADISCORD_economy_treasury")
            pp = ("NAM", "numeric", "has_political_power")
            before = facts[cash], facts[pp]
            self.apply(block(charter, "complete_effect"), facts)
            facts[("228", "is_controlled_by", "NAM")] = False
            facts[("225", "is_controlled_by", "NAM")] = alternative == "225"
            self.apply(block(charter, "remove_effect"), facts)
            self.apply(block(charter, "cancel_effect"), facts)
            if alternative == "225":
                self.assertEqual(facts[("NAM", "equipment", "convoy")], 35)
                self.assertEqual((facts[cash], facts[pp]), (before[0] - 200, before[1] - 35))
            else:
                self.assertEqual(facts[("NAM", "equipment", "convoy")], 10)
                self.assertEqual((facts[cash], facts[pp]), before)

    def test_corporate_housing_and_offices_follow_usable_sites_and_do_not_exceed_caps(self):
        tree = self.exile_trees["exile_corporate"][1]
        archive = tree["NAM_board_company_capital"]
        house = tree["NAM_board_company_housing"]
        modifier = block(parsed("common/dynamic_modifiers/ADISCORD_dynamic_modifiers_NAM.txt"),
                         "NAM_board_company_quarters_state")
        self.assertEqual(float(scalar(modifier, "state_production_speed_industrial_complex_factor")), 0.35)
        for cap in (1, 2, 3):
            facts = self.board_capital_sites(("688", "231"))
            facts[("NAM", "variable", "NAM_free_zone_slots")] = cap
            self.apply(block(house, "completion_reward"), facts)
            self.assertEqual(facts[("231", "building", "industrial_complex")], 1)
            self.assertTrue(facts[("231", "has_dynamic_modifier", "NAM_board_company_quarters_state")])
            self.assertEqual(facts[("NAM", "variable", "NAM_free_zone_slots")], min(cap + 1, 3))
            self.assertFalse(facts.get(("688", "building", "industrial_complex")))
            facts[("231", "is_controlled_by", "NAM")] = False
            self.assertFalse(self.matches(block(modifier, "enable"), facts, "231"))
        for too_many, expected in ((False, "688"), (True, "225")):
            facts = self.board_capital_sites(("688", "225"))
            facts[("688", "numeric", "ADISCORD_business_center")] = 3 if too_many else 2
            self.apply(block(archive, "completion_reward"), facts)
            self.assertEqual(facts[(expected, "building", "ADISCORD_business_center")], 1)
            self.assertEqual(facts[("NAM", "variable", "NAM_corp_capital")], 80)
        for state, allowed in (("231", False), ("688", True)):
            facts = self.board_capital_sites(("688", "231"))
            facts[("231", "numeric", "industrial_complex")] = 20
            self.apply(block(house, "completion_reward"), facts)
            self.assertEqual(bool(facts.get((state, "building", "industrial_complex"))), allowed)

    def test_corporate_airport_reassigns_runways_and_delivers_cargo_planes_at_the_cap(self):
        airport = self.exile_trees["exile_corporate"][1]["NAM_board_company_airport"]
        for level, held, backup, expected in ((8, True, 4, (2, 0)), (9, True, 4, (1, 0)),
                                              (10, True, 4, (0, 2)), (8, False, 9, (0, 1)),
                                              (10, True, 10, (0, 0))):
            facts = self.board_capital_sites(("228", "231"))
            facts[("228", "is_controlled_by", "NAM")] = held
            facts[("228", "numeric", "air_base")] = level
            facts[("231", "numeric", "air_base")] = backup
            self.assertTrue(self.matches(block(airport, "available"), facts))
            self.apply(block(airport, "completion_reward"), facts)
            self.assertEqual(tuple(facts.get((state, "building", "air_base"), 0) for state in ("228", "231")), expected)
            self.assertEqual(facts[("NAM", "equipment", "ADISCORD_transport_airframe_2162")], 24)
        facts = self.board_capital_sites()
        facts[("228", "is_controlled_by", "NAM")] = False
        self.assertFalse(self.matches(block(airport, "available"), facts))
        self.apply(block(airport, "completion_reward"), facts)
        self.assertFalse(facts.get(("NAM", "equipment", "ADISCORD_transport_airframe_2162")))

    def test_corporate_charters_inherit_live_zones_and_book_only_available_capacity(self):
        category = block(parsed(f"common/decisions/{BASE}_decisions.txt"), "NAM_free_zones")
        charter = self.bind_field(block(category, "NAM_corp_charter_free_zone"), "225")
        facts = self.board_capital_sites(("225", "228"))
        board = ("NAM", "has_country_flag", "NAM_corp_takeover")
        human = ("NAM", "has_completed_focus", "NAM_hum_free_zones")
        capital = ("NAM", "has_completed_focus", "NAM_board_company_capital")
        active = ("NAM", "variable", "NAM_free_zones_active")
        pending = ("NAM", "variable", "NAM_free_zones_pending")
        for board_governs, inherited, offices, expected in (
                (False, False, False, False), (False, True, False, True),
                (True, False, False, False), (True, True, False, True), (True, False, True, True)):
            facts[board], facts[human], facts[capital] = board_governs, inherited, offices
            self.assertEqual(self.matches(block(charter, "visible"), facts), expected)
        facts[("228", "has_state_flag", "NAM_free_zone")] = True
        facts[active], facts[pending] = 1, 0
        calculation = self.triggers["NAM_corp_zone_slot_free"]
        with patch.dict(self.triggers, {"NAM_corp_zone_slot_free": calculation[2:]}):
            self.apply(calculation[:2], facts)
            self.assertFalse(self.matches(block(charter, "available"), facts))
            self.apply(block(charter, "complete_effect"), facts)
            self.assertEqual(facts[pending], 0)
            housing = self.exile_trees["exile_corporate"][1]["NAM_board_company_housing"]
            self.apply(block(housing, "completion_reward"), facts)
            self.apply(calculation[:2], facts)
            self.assertTrue(self.matches(block(charter, "available"), facts))
            self.apply(block(charter, "complete_effect"), facts)
            self.apply(calculation[:2], facts)
            self.apply(block(charter, "complete_effect"), facts)
            self.assertEqual(facts[pending], 1)
        for independent in (False, True):
            colony = {**facts, ("NAM", "is_subject", "no"): independent}
            self.assertEqual(self.matches(block(charter, "cancel_trigger"), colony), not independent)
            self.apply(block(charter, "remove_effect"), colony)
            self.apply(block(charter, "cancel_effect"), colony)
            self.assertEqual(colony[pending], 0)
            self.assertTrue(colony[("228", "has_state_flag", "NAM_free_zone")])
            self.assertEqual(bool(colony.get(("225", "has_state_flag", "NAM_free_zone"))), independent)
            self.assertEqual(colony[active], 2 if independent else 1)

    def test_corporate_landing_contracts_preserve_prior_preparation_and_preview_only_real_gains(self):
        focus = self.exile_trees["exile_corporate"][1]["NAM_board_landing_contracts"]
        for prior, cap, readiness in ((False, 1, 20), (True, 2, 100), (True, 3, 70),
                                      (True, 3, 90), (True, 3, 95), (True, 3, 100), (False, 3, 100)):
            facts = self.independent_facts()
            facts[("NAM", "has_completed_focus", "NAM_hum_marine_contracts")] = prior
            facts[("NAM", "variable", "NAM_marine_order_cap")] = cap
            facts[("NAM", "variable", "NAM_revenge_readiness")] = readiness
            with self.subTest(prior=prior, cap=cap, readiness=readiness):
                self.assertEqual(self.matches(block(focus, "bypass"), facts), prior and cap == 3 and readiness == 100)
                reward = block(focus, "completion_reward")
                selected = [e for _, e in selected_effects(self.expand(reward), facts, "NAM")]
                self.assertEqual(any(e.key == "unlock_decision_tooltip" for e in selected), not prior)
                tooltips = {e.value for e in selected if e.key == "custom_effect_tooltip"}
                self.assertEqual("NAM_hum_company_guard_tt" in tooltips, cap < 3)
                self.assertEqual("NAM_board_landing_contracts_tt" in tooltips, readiness <= 90)
                self.assertEqual("NAM_board_landing_readiness_cap_tt" in tooltips, 90 < readiness < 100)
                before = dict(facts)
                self.apply(reward, facts)
                self.assertEqual(facts[("NAM", "variable", "NAM_marine_order_cap")], min(cap + 1, 3))
                self.assertEqual(facts[("NAM", "variable", "NAM_revenge_readiness")], min(readiness + 10, 100))
                if prior and cap == 3 and readiness == 100:
                    self.assertEqual(facts, before)
            facts[("NAM", "has_global_flag", "NAM_wor_exile_war")] = True
            self.assertTrue(self.matches(block(focus, "bypass"), facts))

    def test_normal_preparation_fits_external_clock(self):
        path = ("independence_day", "open_ledgers", "districts", "district_guarantees")
        days = sum(int(scalar(self.focuses["NAM_" + key], "cost")) * 7 for key in path)
        self.assertEqual(days, 91)
        self.assertLess(days + 60, 300)
        self.assertNotIn("prerequisite", [e.key for e in self.wartime["NAM_alarm"]])
        self.assertNotIn("prerequisite", [e.key for e in self.postwar["NAM_recognition"]])
        self.assertNotIn("prerequisite", [e.key for e in self.defeated["NAM_defeat_count_losses"]])
        self.assertEqual(int(scalar(self.wartime["NAM_alarm"], "cost")), 1)
        for name, focus in self.focuses.items():
            if "NAM_restitution_clock_tt" in repr(block(focus, "available")):
                self.assertIn("ADISCORD_nam_resource_war_started", repr(block(focus, "bypass")), name)

    def test_late_political_routes_still_have_a_usable_result(self):
        facts = self.facts()
        facts[("NAM", "has_global_flag", BASE + "_resolved")] = True
        reward = block(self.focuses["NAM_garrison_assembly"], "completion_reward")
        self.assertIn("NAM_supply_order", [e.value for e in walk(reward) if e.key == "unlock_decision_tooltip"])
        self.assertTrue(self.matches(block(self.decisions["NAM_supply_order"], "visible"), facts))
        self.assertTrue(self.matches(block(self.decisions["NAM_supply_order"], "available"), facts))
        reward = block(self.focuses["NAM_district_guarantees"], "completion_reward")
        self.apply(reward, facts)
        self.assertEqual(facts[("NAM", "variable", "NAM_adm_stability_factor")], 0.03)

    def test_quartermaster_delivers_when_procurement_is_already_unlocked(self):
        for emergency_first in (False, True):
            facts = self.facts()
            facts[("NAM", "has_completed_focus", "NAM_emergency_writ")] = emergency_first
            self.apply(block(self.focuses["NAM_quartermaster"], "completion_reward"), facts)
            self.assertEqual(facts[("NAM", "equipment", "infantry_equipment")], 13500)
            self.assertEqual(facts[("NAM", "equipment", "support_equipment")], 60)

    def test_design_offices_exchange_real_chassis_at_either_works(self):
        decision = self.decisions["NAM_exchange_chassis"]
        reward = block(decision, "complete_effect")
        trucks = ("NAM", "equipment", "motorized_equipment")
        kits = ("NAM", "equipment", "support_equipment")
        carriers = ("NAM", "equipment", "ADISCORD_armored_carrier_2163")
        tech = ("NAM", "has_tech", "ADISCORD_tech_armored_carrier_program")
        for site, factory in (("688", "arms_factory"), ("700", "industrial_complex")):
            facts = self.facts()
            facts.update({
                ("NAM", "has_completed_focus", "NAM_domestic_designs"): True,
                ("NAM", "has_global_flag", "ADISCORD_nam_resource_war_nam_victory"): True,
                ("NAM", "is_subject", "no"): True,
                (site, "is_owned_by", "NAM"): True,
                (site, "is_controlled_by", "NAM"): True,
                (site, "numeric", factory): 1,
                trucks: 100, kits: 45,
            })
            self.assertTrue(self.matches(block(decision, "available"), facts))
            for key, value in ((trucks, 99.99), (kits, 44.99), ((site, "is_controlled_by", "NAM"), False),
                               ((site, "numeric", factory), 0), (("NAM", "is_subject", "no"), False),
                               (("NAM", "has_completed_focus", "NAM_domestic_designs"), False)):
                denied = {**facts, key: value}
                before = dict(denied)
                self.apply(reward, denied)
                self.assertEqual(denied, before)
            self.assertTrue(self.matches(block(decision, "custom_cost_trigger"), facts))
            self.apply(reward, facts)
            self.assertEqual((facts[trucks], facts[kits], facts[carriers], facts[tech]), (0, 0, 75, True))
            self.apply(reward, facts)
            self.assertEqual(facts[carriers], 75)
            facts.update({trucks: 100, kits: 45})
            self.apply(reward, facts)
            self.assertEqual((facts[trucks], facts[kits], facts[carriers]), (0, 0, 150))
        self.assertEqual(scalar(decision, "days_re_enable"), "45")

    def test_pragmatic_court_warrants_require_a_paid_award_and_cap_reserved_cargo(self):
        court = self.decisions["NAM_pw_contract_arbitration"]
        charter = self.decisions["NAM_pw_barter_charter"]
        collect = self.decisions["NAM_prag_collect_award"]
        stock = ("NAM", "variable", "NAM_prag_warrants")
        encumbered = ("NAM", "has_country_flag", "NAM_prag_warrant_pledged")
        fuel = ("NAM", "numeric", "has_fuel")
        cash = ("NAM", "variable", "ADISCORD_economy_treasury")
        pp = ("NAM", "numeric", "has_political_power")
        guarantee = ("NAM", "has_completed_focus", "NAM_balanced_accounts")
        opening = self.postwar_facts()
        opening.update({fuel: 0, ("700", "numeric", "naval_base"): 1, guarantee: False, stock: 0,
                        ("NAM", "owns_state", "688"): False})
        before = opening[pp], opening[cash]
        self.apply(block(court, "complete_effect"), opening)
        self.apply(block(court, "complete_effect"), opening)
        self.assertEqual((opening[pp], opening[cash]), (before[0] - 35, before[1] - 350))
        cancel = dict(opening)
        self.apply(block(court, "cancel_effect"), cancel)
        self.apply(block(court, "remove_effect"), cancel)
        self.assertEqual((cancel[pp], cancel[cash], cancel[stock]), (*before, 0))
        self.apply(block(court, "remove_effect"), opening)
        self.apply(block(court, "remove_effect"), opening)
        self.assertEqual(opening[stock], 1)
        for key in ("NAM_commercial_reserve", "NAM_warehouse_receipts", "NAM_rus_expedition_staff"):
            opening[("NAM", "has_completed_focus", key)] = False
        self.assertTrue(self.matches(block(charter, "visible"), opening))
        self.assertTrue(self.matches(block(charter, "custom_cost_trigger"), opening))
        self.assertFalse(self.matches(block(court, "visible"), opening))
        before_charter = dict(opening)
        self.apply(block(charter, "complete_effect"), opening)
        self.assertEqual((opening[encumbered], opening[stock], opening[fuel]), (True, 1, 0))
        self.assertTrue(self.matches(block(charter, "visible"), opening))
        self.assertFalse(self.matches(block(collect, "visible"), opening))
        self.apply(block(collect, "complete_effect"), opening)
        self.assertEqual((opening[stock], opening[fuel]), (1, 0))
        for lost in (False, True):
            facts = dict(opening)
            facts[("NAM", "controls_state", "700")] = not lost
            self.apply(block(charter, "remove_effect"), facts)
            self.apply(block(charter, "cancel_effect"), facts)
            self.assertEqual((facts[stock], facts[fuel], facts[encumbered]), (1 if lost else 0, 0, False))
            self.assertEqual(facts.get(("NAM", "equipment", "convoy"), 0), 0 if lost else 24)
        second = {**before_charter, guarantee: True, ("NAM", "has_completed_focus", "NAM_commercial_reserve"): True}
        self.apply(block(charter, "complete_effect"), second)
        self.assertTrue(second[encumbered])
        self.assertTrue(self.matches(block(court, "visible"), second))
        self.assertTrue(self.matches(block(court, "available"), second))
        self.apply(block(court, "complete_effect"), second)
        self.apply(block(court, "remove_effect"), second)
        self.assertEqual(second[stock], 2)
        self.assertFalse(self.matches(block(court, "visible"), second))
        self.apply(block(collect, "complete_effect"), second)
        self.apply(block(collect, "complete_effect"), second)
        self.assertEqual(second[stock], 1)
        self.assertEqual(second[fuel] + second.get(("NAM", "variable", "NAM_open_fuel_reserve"), 0), 60000)
        self.apply(block(charter, "remove_effect"), second)
        self.assertEqual(second[stock], 0)

    def test_pragmatic_finals_split_one_warrant_by_its_actual_destination(self):
        cash = ("NAM", "variable", "ADISCORD_economy_treasury")
        debt = ("NAM", "variable", "NAM_bond_balance")
        stock = ("NAM", "variable", "NAM_prag_warrants")
        remainder = ("NAM", "variable", "NAM_open_fuel_reserve")
        fuel = ("NAM", "numeric", "has_fuel")
        fund = ("NAM", "has_country_flag", "NAM_crisis_fund")
        republic = ("NAM", "has_completed_focus", "NAM_prag_ending_republic")
        board = ("NAM", "has_completed_focus", "NAM_prag_ending_directorate")
        opening = self.postwar_facts()
        opening.update({("700", "numeric", "naval_base"): 1, stock: 1, fuel: 0,
                        ("NAM", "fuel_capacity"): 10000, fund: False, debt: 0})
        towns = self.decisions["NAM_prag_municipal_delivery"]
        bankers = self.decisions["NAM_prag_redeem_debentures"]
        for district in (False, True):
            for amount in (0, 150.5, 600, 660):
                original = {**opening, debt: amount, republic: district, board: not district}
                for decision in (towns, bankers):
                    campaign = dict(original)
                    accepted = district if decision is towns else not district and amount > 0
                    self.assertEqual(self.matches(block(decision, "visible"), campaign), accepted)
                    self.apply(block(decision, "complete_effect"), campaign)
                    self.apply(block(decision, "complete_effect"), campaign)
                    if not accepted:
                        self.assertEqual(campaign, original)
                        continue
                    self.assertEqual((campaign[stock], campaign[fund]), (0, district))
                    self.assertEqual(campaign[debt], amount if district else max(0, amount - 600))
                    received = 40000 if district else 60000 - 100 * min(600, amount)
                    self.assertEqual(campaign[fuel] + campaign.get(remainder, 0), received)
                    self.assertLessEqual(campaign[fuel], 10000)
        for key, val in ((fund, True), (("NAM", "controls_province", "16716"), False),
                         (("NAM", "is_subject", "no"), False)):
            blocked = {**opening, republic: True, key: val}
            self.apply(block(towns, "complete_effect"), blocked)
            self.assertEqual(blocked[stock], 1)
        stamp = ("NAM", "has_country_flag", "NAM_certified_export")
        issue = self.decisions["NAM_issue_harbour_bonds"]
        charter = self.decisions["NAM_pw_barter_charter"]
        for municipal in (False, True):
            facts = {**opening, board: True, republic: False, ("fixture", "fuel_logistics"): True,
                     ("NAM", "has_completed_focus", "NAM_municipal_bonds"): municipal, stamp: False}
            self.apply(block(issue, "complete_effect"), facts)
            self.assertEqual(facts[debt], 0)
            self.apply(block(charter, "complete_effect"), facts)
            self.apply(block(charter, "remove_effect"), facts)
            self.assertTrue(facts[stamp])
            self.assertEqual(facts[("NAM", "flag_duration", "NAM_certified_export")], 180 if municipal else 90)
            before = facts[cash]
            self.apply(block(issue, "complete_effect"), facts)
            self.apply(block(issue, "complete_effect"), facts)
            self.assertEqual((facts[debt], facts[cash], facts[stamp]), (660, before + 600, False))

    def test_municipal_bonds_require_a_fresh_sale_and_withhold_only_remaining_debt(self):
        sale = block(self.decisions["NAM_export_fuel"], "complete_effect")
        issue = block(self.decisions["NAM_issue_harbour_bonds"], "complete_effect")
        cash = ("NAM", "variable", "ADISCORD_economy_treasury")
        debt = ("NAM", "variable", "NAM_bond_balance")
        stamp = ("NAM", "has_country_flag", "NAM_certified_export")
        fuel = ("NAM", "numeric", "has_fuel")
        port = ("NAM", "controls_state", "700")
        for consortium, gross in ((False, 400), (True, 500)):
            facts = self.facts(treasury=0, fuel=600000)
            facts.update({
                ("fixture", "fuel_logistics"): True,
                ("NAM", "is_subject", "no"): True,
                ("NAM", "has_global_flag", "ADISCORD_nam_resource_war_nam_victory"): True,
                ("NAM", "has_completed_focus", "NAM_export_quays"): False,
                ("NAM", "has_completed_focus", "NAM_customs_clearinghouse"): True,
                ("NAM", "has_completed_focus", "NAM_municipal_bonds"): True,
                ("NAM", "has_completed_focus", "NAM_oil_exchange"): consortium,
                ("NAM", "has_completed_focus", "NAM_export_consortium"): consortium,
                ("NAM", "variable", "NAM_exchange_receipts"): 0,
                debt: 0,
            })
            self.apply(issue, facts)
            self.assertEqual((facts[cash], facts[debt]), (0, 0))
            self.apply(sale, facts)
            self.assertEqual((facts[cash], facts[stamp]), (gross, True))
            self.assertEqual(facts[("NAM", "flag_duration", "NAM_certified_export")], 90)
            for key in (port, stamp, ("NAM", "is_subject", "no")):
                denied = {**facts, key: False}
                self.apply(issue, denied)
                self.assertEqual((denied[cash], denied[debt]), (gross, 0))
            self.apply(issue, facts)
            self.apply(issue, facts)
            self.assertEqual((facts[cash], facts[debt], facts[stamp]), (gross + 600, 660, False))
            failed = {**facts, fuel: 59999.99}
            self.apply(sale, failed)
            self.assertEqual((failed[cash], failed[debt], failed[stamp]), (facts[cash], 660, False))
            for remaining, retention in ((460, 200), (260, 200), (60, 200), (0, 60)):
                before = facts[cash]
                self.apply(sale, facts)
                self.assertEqual((facts[cash] - before, facts[debt]), (gross - retention, remaining))
                if remaining:
                    self.apply(issue, facts)
                    self.assertEqual(facts[debt], remaining)
            self.apply(issue, facts)
            self.assertEqual(facts[debt], 660)
            facts[("NAM", "has_completed_focus", "NAM_commercial_commonwealth")] = True
            self.apply(issue, facts)
            self.assertEqual(facts[debt], 660)
            self.apply(sale, facts)
            self.apply(issue, facts)
            self.assertEqual(facts[debt], 1120)
            self.apply(sale, facts)
            self.apply(issue, facts)
            self.assertEqual(facts[debt], 920)
            self.assertTrue(facts[stamp])

    def test_outstanding_bonds_remain_payable_after_losing_the_port(self):
        monthly = self.effects["NAM_oil_monthly"]
        self.assertEqual(sum(e.key == "NAM_pay_municipal_instalment" for e in walk(monthly)), 1)
        instalment = self.effects["NAM_pay_municipal_instalment"]
        cash = ("NAM", "variable", "ADISCORD_economy_treasury")
        debt = ("NAM", "variable", "NAM_bond_balance")
        costs = ("NAM", "variable", "ADISCORD_economy_current_month_action_costs")
        facts = self.facts(treasury=0)
        facts.update({debt: 140, costs: 0, ("NAM", "controls_state", "700"): False})
        for balance, expected in ((0, 0), (-10, 0), (1000, 60), (30.75, 30.75), (100, 49.25), (100, 0)):
            facts[cash] = balance
            before = facts[debt], facts[costs]
            self.apply(instalment, facts)
            self.assertEqual((facts[cash], facts[debt], facts[costs]),
                             (balance - expected, before[0] - expected, before[1] + expected))

    def test_oil_exchange_receipts_are_backed_by_actual_sales(self):
        sale = self.decisions["NAM_export_fuel"]
        redeem = self.decisions["NAM_exchange_redeem"]
        fuel = ("NAM", "numeric", "has_fuel")
        cash = ("NAM", "variable", "ADISCORD_economy_treasury")
        receipts = ("NAM", "variable", "NAM_exchange_receipts")
        for consortium, sale_price, capacity in ((True, 500, 1), (False, 400, 2)):
            facts = self.facts(treasury=1000, fuel=180000)
            facts[("fixture", "fuel_logistics")] = True
            facts[("NAM", "fuel_capacity")] = 180000
            facts[("NAM", "has_completed_focus", "NAM_export_quays")] = False
            facts[("NAM", "has_completed_focus", "NAM_export_consortium")] = consortium
            facts[("NAM", "has_completed_focus", "NAM_state_refineries")] = not consortium
            self.assertFalse(self.matches(block(sale, "visible"), facts))
            self.apply(block(self.postwar["NAM_oil_exchange"], "completion_reward"), facts)
            facts[("NAM", "has_completed_focus", "NAM_oil_exchange")] = True
            self.assertTrue(self.matches(block(sale, "visible"), facts))
            self.assertFalse(self.matches(block(redeem, "visible"), facts))
            for lot in range(1, 4):
                self.apply(block(sale, "complete_effect"), facts)
                self.assertEqual(facts[receipts], min(lot, capacity))
                self.assertEqual(facts[fuel], 180000 - lot * 60000)
                self.assertEqual(facts[cash], 1000 + lot * sale_price)
            for key, value in ((cash, 549.99), (fuel, 120000.01), (("NAM", "controls_state", "700"), False)):
                failed = dict(facts)
                failed[key] = value
                before = (failed[fuel], failed[cash], failed[receipts])
                self.apply(block(redeem, "complete_effect"), failed)
                self.assertEqual((failed[fuel], failed[cash], failed[receipts]), before)
            for lot in range(1, capacity + 1):
                self.apply(block(redeem, "complete_effect"), facts)
                self.assertEqual((facts[fuel], facts[cash], facts[receipts]),
                                 (lot * 60000, 1000 + 3 * sale_price - 550 * lot, capacity - lot))
            depleted = dict(facts)
            self.apply(block(redeem, "complete_effect"), facts)
            self.assertEqual(facts, depleted)

    def test_fractional_affordability_and_actual_debits(self):
        expected = {
            "NAM_export_fuel": (25, 0, 60000), "NAM_workshop_batch": (35, 0, 3000),
            "NAM_supply_order": (25, 500, 0), "NAM_emergency_arsenal": (35, 500, 0),
            "NAM_counterinsurgency": (75, 500, 0), "NAM_relief_batch": (35, 0, 3000),
            "NAM_sign_compact": (50, 350, 0),
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
            expected_treasury = 400 if name == "NAM_export_fuel" else 0
            self.assertEqual(facts[("NAM", "variable", "ADISCORD_economy_treasury")], expected_treasury, name)
            self.assertEqual(facts.get(("NAM", "variable", "ADISCORD_economy_current_month_action_costs"), 0), treasury, name)
            rifles = {
                "NAM_supply_order": 13500, "NAM_emergency_arsenal": 18000,
                "NAM_counterinsurgency": 9000, "NAM_relief_batch": 7200,
            }
            if name in rifles:
                self.assertEqual(facts[("NAM", "equipment", "infantry_equipment")], rifles[name], name)

    POSTWAR_ORDERS = {
        "NAM_pw_development_works": (50, 900, 0, 70, "civil"),
        "NAM_pw_merchant_order": (35, 650, 0, 42, "civil"),
        "NAM_pw_rural_electrification": (40, 550, 0, 56, "civil"),
        "NAM_veteran_housing": (35, 500, 0, 42, "civil"),
        "NAM_postwar_rearmament": (35, 400, 0, 35, "military"),
        "NAM_district_audit": (25, 0, 0, 14, "civil"),
        "NAM_pw_veteran_course": (25, 150, 0, 21, "military"),
        "NAM_pw_garrison_order": (25, 200, 0, 21, "military"),
        "NAM_pw_fuel_quota": (20, 0, 0, 14, "civil"),
        "NAM_pw_state_arsenal": (40, 650, 0, 42, "civil"),
        "NAM_pw_district_congress": (20, 100, 0, 14, "civil"),
        "NAM_pw_district_schools": (25, 200, 0, 35, "civil"),
        "NAM_pw_militia_reserve": (25, 200, 0, 35, "military"),
        "NAM_pw_district_cooperative": (45, 450, 0, 56, "civil"),
        "NAM_pw_export_shipment": (25, 0, 60000, 21, "civil"),
    }

    def postwar_facts(self):
        facts = self.economy_facts()
        facts[("NAM", "has_global_flag", BASE + "_nam_victory")] = True
        for focus in self.postwar:
            facts[("NAM", "has_completed_focus", focus)] = True
        for focus in ("haulage_cooperatives", "tool_cooperatives", "chartered_tonnage", "tractor_leasing",
                      "public_credit", "district_fair", "licensed_assembly", "rescue_college", "pw_industrial_commission",
                      "pw_armament_inspectorate", "freight_brokerage", "relief_register"):
            facts[("NAM", "has_completed_focus", "NAM_" + focus)] = False
        for group in ("nam", "oil", "dist", "garr", "trade"):
            facts[("NAM", "variable", f"NAM_grp_{group}_support")] = 60
        for state, kind in (("700", "industrial_complex"), ("700", "arms_factory"), ("688", "industrial_complex")):
            facts[(state, "variable", f"fixture_building_slots_{kind}_no")] = 3
            facts[(state, "fixture_free_building_slots", f"{kind}:1:yes")] = True
        facts[("NAM", "owns_state", "690")] = True
        facts[("NAM", "controls_state", "690")] = True
        facts[("690", "numeric", "infrastructure")] = 2
        for state in ("67", "688", "689", "690", "700", "719"):
            facts[("NAM", "owns_state", state)] = True
            facts[("NAM", "controls_state", state)] = True
        for province in (16721, 16865, 4321, 2935, 8351, 9016, 9641, 11926, 176, 6961, 16873, 16884, 16716):
            facts[("NAM", "controls_province", str(province))] = True
        return facts

    def test_postwar_orders_pay_once_refund_once_and_survive_renewed_war(self):
        currencies = (("NAM", "numeric", "has_political_power"),
                      ("NAM", "variable", "ADISCORD_economy_treasury"),
                      ("NAM", "numeric", "has_fuel"))
        for name, (pp, money, fuel, days, channel) in self.POSTWAR_ORDERS.items():
            decision = self.decisions[name]
            self.assertEqual(scalar(decision, "cost"), "0", name)
            self.assertEqual(int(scalar(decision, "days_remove")), days, name)
            if name == "NAM_pw_rural_electrification":
                self.assertFalse(any(entry.key == "days_re_enable" for entry in decision))
            else:
                self.assertGreaterEqual(int(scalar(decision, "days_re_enable")), 60, name)
            for key, price in zip(currencies, (pp, money, fuel)):
                if price == 0:
                    continue
                facts = self.postwar_facts()
                facts[key] = price - 0.01
                self.assertFalse(self.matches(block(decision, "custom_cost_trigger"), facts), name)
                before = dict(facts)
                self.apply(block(decision, "complete_effect"), facts)
                self.assertEqual(facts, before, (name, key, "stale unaffordable click"))
            for cause in ("subjugation", "capitulation", "ordinary_cancel"):
                facts = self.postwar_facts()
                for key, price in zip(currencies, (pp, money, fuel)):
                    facts[key] = price
                self.assertTrue(self.matches(block(decision, "available"), facts), name)
                self.assertTrue(self.matches(block(decision, "custom_cost_trigger"), facts), name)
                self.apply(block(decision, "complete_effect"), facts)
                self.assertEqual([facts[k] for k in currencies], [0, 0, 0], name)
                self.assertTrue(facts[("NAM", "has_country_flag", name + "_paid")])
                self.assertTrue(facts[("NAM", "has_country_flag", f"NAM_pw_{channel}_busy")])
                paid = dict(facts)
                self.apply(block(decision, "complete_effect"), facts)
                self.assertEqual(facts, paid, (name, "duplicate payment"))
                facts[("NAM", "has_war", "yes")] = True
                facts[("NAM", "has_war", "no")] = False
                self.assertFalse(self.matches(block(decision, "cancel_trigger"), facts), name)
                if cause == "subjugation":
                    facts[("NAM", "is_subject", "no")] = False
                elif cause == "capitulation":
                    facts[("NAM", "has_capitulated", "no")] = False
                if cause != "ordinary_cancel":
                    self.assertTrue(self.matches(block(decision, "cancel_trigger"), facts), name)
                self.apply(block(decision, "cancel_effect"), facts)
                self.assertEqual([facts[k] for k in currencies], [pp, money, fuel], name)
                refunded = dict(facts)
                self.apply(block(decision, "remove_effect"), facts)
                self.apply(block(decision, "cancel_effect"), facts)
                self.assertEqual(facts, refunded, (name, "late callback"))
                self.assertFalse(facts[("NAM", "has_country_flag", f"NAM_pw_{channel}_busy")])

    def test_shared_southern_preparation_has_forty_nodes_and_no_mandate_gate(self):
        roots = {"NAM_pw_transport_commission", "NAM_pw_army_review", "NAM_pw_naval_review", "NAM_pw_air_review"}
        reachable = set(roots)
        while True:
            children = {name for name, focus in self.postwar.items()
                        if any(e.key == "prerequisite" and any(p.value in reachable for p in e.value) for e in focus)}
            if children <= reachable:
                break
            reachable.update(children)
        self.assertEqual(len(reachable - {"NAM_svetlogorsk_shipyards"}), 40)
        for name in reachable:
            for gate in (e.value for e in self.postwar[name] if e.key == "allow_branch"):
                self.assertFalse(any(e.key.startswith("NAM_prewar_") for e in walk(gate)), name)
                for balance in (-0.5, 0, 0.5):
                    facts = self.postwar_facts()
                    facts[("NAM", "has_variable", "NAM_prewar_balance")] = True
                    facts[("NAM", "variable", "NAM_prewar_balance")] = balance
                    self.assertTrue(self.matches(gate, facts), (name, balance))

    def test_victory_raids_do_not_unlock_the_exile_course(self):
        for outcome in ("victory", "standoff", "defeat", "radical", "humanist"):
            facts = self.postwar_facts()
            facts[("NAM", "has_global_flag", BASE + "_nam_victory")] = outcome in ("victory", "standoff")
            facts[("NAM", "has_global_flag", BASE + "_standoff")] = outcome == "standoff"
            facts[("NAM", "has_global_flag", BASE + "_island_exile")] = outcome in ("radical", "humanist")
            facts[("NAM", "has_country_flag", "NAM_exile_radical")] = outcome == "radical"
            for focus in ("NAM_exile_sea_raiders", "NAM_exile_fences"):
                facts[("NAM", "has_completed_focus", focus)] = False
            self.assertEqual(self.matches(self.triggers["NAM_piracy_open"], facts), outcome == "radical")
            self.assertEqual(self.matches(self.triggers["NAM_pirate_commissioned"], facts), outcome == "victory")
            self.assertEqual(self.matches(self.triggers["NAM_pirate_exchange_open"], facts), outcome == "victory")
            for focus in ("NAM_exile_sea_raiders", "NAM_exile_fences"):
                facts[("NAM", "has_completed_focus", focus)] = True
            self.assertEqual(self.matches(self.triggers["NAM_pirate_commissioned"], facts),
                             outcome in ("radical", "victory"))

    def test_closed_raid_releases_its_flotilla_and_refunds_fuel_once(self):
        category = block(parsed("common/decisions/ADISCORD_nam_resource_war_decisions.txt"), "NAM_piracy")
        for lane, callback in product(("oil", "coast", "strait", "crossing"),
                                      ("cancel_effect", "remove_effect")):
            raid = block(category, "NAM_pirate_raid_lane_" + lane)
            facts = self.postwar_facts()
            facts[("NAM", "is_subject", "no")] = False
            facts[("NAM", "fuel_capacity")] = 200000
            facts[("NAM", "numeric", "has_fuel")] = 200000
            facts[("NAM", "variable", "NAM_pirate_raids_active")] = 1
            facts[("NAM", "has_country_flag", "NAM_pirate_at_sea_" + lane)] = True
            self.apply(block(raid, callback), facts)
            self.apply(block(raid, "cancel_effect"), facts)
            self.assertEqual(facts[("NAM", "variable", "NAM_pirate_raids_active")], 0)
            self.assertEqual(facts[("NAM", "variable", "NAM_open_fuel_reserve")], 1000)
            facts[("NAM", "numeric", "has_fuel")] -= 1200
            self.apply(self.effects["NAM_open_fuel_release"], facts)
            self.assertEqual(facts[("NAM", "numeric", "has_fuel")], 199800)
            self.assertEqual(facts[("NAM", "variable", "NAM_open_fuel_reserve")], 0)

    def test_preparation_existing_assets_do_not_lock_unrelated_focuses(self):
        facts = self.postwar_facts()
        for state in ("690", "719", "700"):
            for kind, level in (("infrastructure", 5), ("air_base", 10), ("radar_station", 6), ("supply_node", 1)):
                facts[(state, "numeric", kind)] = level
        for short in ("freight_depots", "logistics_depots"):
            focus = self.postwar["NAM_pw_" + short]
            self.assertTrue(self.matches(block(focus, "bypass"), facts), short)
        for short in ("fuel_reservoirs", "power_reserve", "ground_control", "air_supply", "southern_corridor",
                      "airfield_network", "radar_posts", "naval_workshops"):
            self.assertTrue(self.matches(block(self.postwar["NAM_pw_" + short], "available"), facts), short)
        self.assertEqual([e.value for e in block(self.postwar["NAM_pw_radar_posts"], "prerequisite")], ["NAM_pw_air_review"])
        for short in ("freight_depots", "logistics_depots"):
            self.assertNotIn("mutually_exclusive", [e.key for e in self.postwar["NAM_pw_" + short]])

    def test_preparation_readiness_uses_real_reserves_not_division_count(self):
        focus = self.postwar["NAM_pw_southern_army"]
        facts = self.postwar_facts()
        facts[("NAM", "numeric", "num_divisions")] = 100
        self.assertFalse(self.matches(block(focus, "available"), facts))
        facts[("NAM", "variable", "fixture_army_manpower")] = 18000
        facts[("NAM", "equipment", "infantry_equipment")] = 3000
        facts[("NAM", "equipment", "support_equipment")] = 199.99
        self.assertFalse(self.matches(block(focus, "available"), facts))
        facts[("NAM", "equipment", "support_equipment")] = 200
        self.assertTrue(self.matches(block(focus, "available"), facts))
        facts[("NAM", "variable", "fixture_army_manpower")] = 0
        facts[("NAM", "numeric", "has_manpower")] = 6000
        facts[("NAM", "equipment", "infantry_equipment")] = 9000
        self.assertTrue(self.matches(block(focus, "available"), facts))
        ready = block(self.postwar["NAM_pw_freight_schedule"], "available")
        facts[("NAM", "equipment", "motorized_equipment")] = 200
        facts[("NAM", "owns_state", "719")] = False
        self.assertFalse(self.matches(ready, facts))
        facts[("690", "numeric", "supply_node")] = 1
        self.assertTrue(self.matches(block(self.postwar["NAM_pw_logistics_depots"], "bypass"), facts))
        self.assertFalse(self.matches(ready, facts))
        facts[("NAM", "fixture_railway_connection", "700:690")] = True
        self.assertTrue(self.matches(ready, facts))
        facts[("NAM", "equipment", "motorized_equipment")] = 199.99
        self.assertFalse(self.matches(ready, facts))

    def test_army_review_offers_replacements_or_rifles_in_one_military_queue(self):
        rifles = self.decisions["NAM_program_reserve_centres"]
        instructors = self.decisions["NAM_pw_veteran_course"]
        review = ("NAM", "has_completed_focus", "NAM_pw_army_review")
        funds = ("NAM", "variable", "ADISCORD_economy_treasury")
        people = ("NAM", "numeric", "has_manpower")
        stock = ("NAM", "equipment", "infantry_equipment")
        for reviewed, choose_rifles in product((False, True), repeat=2):
            facts = self.postwar_facts()
            facts[review] = reviewed
            for focus in ("reserve_centres", "breakthrough_army", "mobile_army"):
                facts[("NAM", "has_completed_focus", "NAM_pw_" + focus)] = False
            self.assertEqual(self.matches(block(rifles, "visible"), facts), reviewed)
            self.assertTrue(self.matches(block(instructors, "visible"), facts))
            active, other = (rifles, instructors) if choose_rifles else (instructors, rifles)
            before = dict(facts)
            self.apply(block(active, "complete_effect"), facts)
            if choose_rifles and not reviewed:
                self.assertEqual(facts, before)
                continue
            self.assertEqual(before[funds] - facts[funds], 850 if choose_rifles else 150)
            self.assertFalse(self.matches(block(other, "available"), facts))
            paid = dict(facts)
            self.apply(block(other, "complete_effect"), facts)
            self.assertEqual(facts, paid)
            self.apply(block(active, "remove_effect"), facts)
            self.assertEqual(facts.get(stock, 0) - before.get(stock, 0), 18000 if choose_rifles else 0)
            self.assertEqual(facts.get(people, 0) - before.get(people, 0), 2000 if reviewed and not choose_rifles else 0)
            settled = dict(facts)
            self.apply(block(active, "remove_effect"), facts)
            self.apply(block(active, "cancel_effect"), facts)
            self.assertEqual(facts, settled)
            self.assertTrue(self.matches(block(other, "available"), facts))

    def test_reserve_regiments_pack_current_establishment_and_refund_on_subjugation(self):
        order = self.decisions["NAM_program_reserve_centres"]
        equipment = ("infantry_equipment", "artillery_equipment", "motorized_equipment")
        funds = ("NAM", "variable", "ADISCORD_economy_treasury")
        for doctrine, centres, occupied in product(("none", "breakthrough_army", "mobile_army"), (False, True), (False, True)):
            facts = self.postwar_facts()
            for focus in ("reserve_centres", "breakthrough_army", "mobile_army"):
                facts[("NAM", "has_completed_focus", "NAM_pw_" + focus)] = False
            before = dict(facts)
            self.apply(block(order, "complete_effect"), facts)
            facts[("NAM", "has_completed_focus", "NAM_pw_reserve_centres")] = centres
            if doctrine != "none":
                facts[("NAM", "has_completed_focus", "NAM_pw_" + doctrine)] = True
            facts[("NAM", "is_subject", "no")] = not occupied
            self.assertEqual(self.matches(block(order, "cancel_trigger"), facts), occupied)
            self.apply(block(order, "remove_effect"), facts)
            amounts = tuple(facts.get(("NAM", "equipment", kind), 0) - before.get(("NAM", "equipment", kind), 0)
                            for kind in equipment)
            self.assertEqual(amounts, (0, 0, 0) if occupied else (
                27000 if centres else 18000, 60 if doctrine == "breakthrough_army" else 0,
                120 if doctrine == "mobile_army" else 0))
            self.assertEqual(facts[funds], before[funds] - (0 if occupied else 850))
            facts[("NAM", "is_subject", "no")] = True
            settled = dict(facts)
            self.apply(block(order, "remove_effect"), facts)
            self.apply(block(order, "cancel_effect"), facts)
            self.assertEqual(facts, settled)

    def test_combined_arms_previews_and_delivers_only_the_available_orders(self):
        reward = block(self.postwar["NAM_pw_combined_arms"], "completion_reward")
        plans = parsed("common/ai_strategy_plans/ADISCORD_NAM_plans.txt")
        for name, mobile in (("NAM_postwar_plan", False), ("NAM_postwar_vertical_plan", False),
                             ("NAM_postwar_pragmatic_plan", True)):
            focuses = block(block(plans, name), "ai_national_focuses")
            planned = [e.value for e in focuses]
            course = "NAM_pw_mobile_army" if mobile else "NAM_pw_breakthrough_army"
            workshop = "NAM_pw_field_workshops" if mobile else "NAM_pw_engineer_units"
            self.assertLess(planned.index(course), planned.index(workshop))
            self.assertLess(planned.index(workshop), planned.index("NAM_pw_combined_arms"))
            self.assertNotIn("NAM_pw_breakthrough_army" if mobile else "NAM_pw_mobile_army", planned)
        for mobile, motor_pool in product((False, True), repeat=2):
            facts = self.postwar_facts()
            facts[("NAM", "has_completed_focus", "NAM_pw_engineer_units")] = not mobile
            facts[("NAM", "has_completed_focus", "NAM_pw_field_workshops")] = mobile
            facts[("NAM", "has_completed_focus", "NAM_motor_pool")] = motor_pool
            shown = {e.value for _, e in selected_effects(self.expand(reward), facts, "NAM")
                     if e.key == "custom_effect_tooltip"}
            for order, tip, eligible, kind, quantity in (
                ("NAM_program_engineer_units", "NAM_pw_combined_engineers_tt", not mobile, "artillery_equipment", 120),
                ("NAM_mil_carrier_contract", "NAM_pw_combined_carriers_tt", mobile or motor_pool, "ADISCORD_armored_carrier_2163", 240),
            ):
                decision = self.decisions[order]
                self.assertEqual(tip in shown, eligible)
                self.assertEqual(self.matches(block(decision, "visible"), facts), eligible)
                if eligible:
                    stock = ("NAM", "equipment", kind)
                    before = facts.get(stock, 0)
                    self.apply(block(decision, "complete_effect"), facts)
                    self.apply(block(decision, "remove_effect"), facts)
                    self.assertEqual(facts[stock] - before, quantity)

    def test_staff_exercises_fill_only_missing_commands_and_force_one_field_assignment(self):
        legacy = {"NAM_field_guards": "NAM_mil_field_security", "NAM_mobile_columns": "NAM_mil_mobile_surge",
                  "NAM_officer_courses": "NAM_mil_command_course"}
        reward = block(self.postwar["NAM_pw_staff_exercises"], "completion_reward")
        for old, officers in product((None, "NAM_field_guards", "NAM_mobile_columns"), (False, True)):
            facts = self.postwar_facts()
            for focus, order in legacy.items():
                inherited = old == focus or focus == "NAM_officer_courses" and officers
                facts[("NAM", "has_completed_focus", focus)] = inherited
                facts[("NAM", "has_completed_focus", "NAM_pw_staff_exercises")] = False
                self.assertEqual(self.matches(block(self.decisions[order], "visible"), facts), inherited)
            unlocked = {e.value for _, e in selected_effects(self.expand(reward), facts, "NAM")
                        if e.key == "unlock_decision_tooltip"}
            self.assertEqual(unlocked, {order for focus, order in legacy.items()
                                        if not facts[("NAM", "has_completed_focus", focus)]})
            facts[("NAM", "has_completed_focus", "NAM_pw_staff_exercises")] = True
            for order in legacy.values():
                self.assertTrue(self.matches(block(self.decisions[order], "visible"), facts))
        guard = self.decisions["NAM_mil_field_security"]
        column = self.decisions["NAM_mil_mobile_surge"]
        facts[("NAM", "has_war", "yes")] = False
        self.assertTrue(self.matches(block(guard, "available"), facts))
        self.assertFalse(self.matches(block(column, "available"), facts))
        facts[("NAM", "has_war", "yes")] = True
        facts[("NAM", "has_decision", "NAM_mil_field_security")] = True
        self.assertFalse(self.matches(block(column, "available"), facts))
        before = dict(facts)
        self.apply(block(column, "complete_effect"), facts)
        self.assertEqual(facts, before)
        facts[("NAM", "has_decision", "NAM_mil_field_security")] = False
        self.apply(block(column, "complete_effect"), facts)
        self.assertTrue(facts[("NAM", "has_dynamic_modifier", "NAM_mil_mobile_operation")])
        self.assertFalse(self.matches(block(guard, "available"), facts))
        self.apply(block(column, "remove_effect"), facts)
        self.assertTrue(self.matches(block(guard, "available"), facts))

    def test_postwar_air_board_preserves_old_contracts_and_shares_one_paid_trial(self):
        orders = ("NAM_air_fighter_order", "NAM_air_cas_order")
        licences = ("NAM_air_interceptors", "NAM_air_support")
        specialties = ("NAM_pw_air_defence", "NAM_pw_frontline_air")
        treasury = ("NAM", "variable", "ADISCORD_economy_treasury")
        trial = ("NAM", "has_country_flag", "NAM_air_trial_used")
        for prewar in (None, 0, 1):
            for first in (0, 1):
                facts = self.postwar_facts()
                for i in (0, 1):
                    facts[("NAM", "has_completed_focus", licences[i])] = i == prewar
                    facts[("NAM", "has_completed_focus", specialties[i])] = False
                review = block(self.postwar["NAM_pw_air_review"], "completion_reward")
                visible = [e.value for _, e in selected_effects(self.expand(review), facts, "NAM")
                           if e.key == "unlock_decision_tooltip"]
                self.assertEqual(visible, [name for i, name in enumerate(orders) if i != prewar])
                order = self.decisions[orders[first]]
                self.assertTrue(self.matches(block(order, "visible"), facts))
                denied = {**facts, treasury: 299.99}
                self.apply(block(order, "complete_effect"), denied)
                self.assertFalse(denied.get(trial, False))
                old_cash = facts[treasury]
                self.apply(block(order, "complete_effect"), facts)
                self.assertEqual(facts[treasury], old_cash - 300)
                self.assertEqual(bool(facts.get(trial)), first != prewar)
                for i, name in enumerate(orders):
                    still_open = i == prewar or first == prewar
                    self.assertEqual(self.matches(block(self.decisions[name], "visible"), facts), still_open)
                    if not still_open:
                        stale = dict(facts)
                        self.apply(block(self.decisions[name], "complete_effect"), stale)
                        self.assertEqual(stale, facts)

    def test_postwar_air_orders_deliver_the_selected_series_and_rebuild_only_real_stock(self):
        for kind, new, old_model, model, tech in (
            ("fighter", "NAM_pw_air_defence", "ADISCORD_fighter_airframe_2163", "ADISCORD_fighter_airframe_2161",
             "ADISCORD_tech_high_altitude_interceptors"),
            ("cas", "NAM_pw_frontline_air", "ADISCORD_cas_airframe_2170", "ADISCORD_attack_airframe_2163",
             "ADISCORD_tech_precision_glide_bomb_kits"),
        ):
            body = self.decisions["NAM_air_" + kind + "_order"]
            for command, workshop, stock in product((False, True), (False, True), (11.99, 12)):
                facts = self.postwar_facts()
                for course in ("NAM_pw_air_defence", "NAM_pw_frontline_air"):
                    facts[("NAM", "has_completed_focus", course)] = course == new
                facts[("NAM", "has_completed_focus", "NAM_pw_southern_air_command")] = command
                facts[("NAM", "has_completed_focus", "NAM_pw_engine_workshops")] = workshop
                facts[("NAM", "equipment", old_model)] = stock
                if workshop:
                    self.apply(block(self.postwar["NAM_pw_engine_workshops"], "completion_reward"), facts)
                    self.assertTrue(facts[("NAM", "has_tech", tech)])
                self.apply(block(body, "complete_effect"), facts)
                rebuilt = 12 if workshop and stock >= 12 else 0
                self.assertEqual(facts[("NAM", "equipment", model)], (36 if command else 24) + rebuilt)
                self.assertEqual(facts[("NAM", "equipment", old_model)], stock - rebuilt)

    def test_air_bridge_commits_transports_to_one_district_and_suspends_supply_on_capture(self):
        body = self.decisions["NAM_program_air_supply"]
        site, other = "690", "719"
        order = self.bind_field(body, site)
        other_order = self.bind_field(body, other)
        air = ("NAM", "equipment", "ADISCORD_transport_airframe_2162")
        cash = ("NAM", "variable", "ADISCORD_economy_treasury")
        fuel = ("NAM", "numeric", "has_fuel")
        staff = ("NAM", "has_country_flag", "NAM_pw_military_busy")
        delivery = (site, "has_dynamic_modifier", "NAM_air_bridge_deliveries")
        airport = ("700", "numeric", "air_base")
        observers = ("NAM", "has_completed_focus", "NAM_pw_ground_control")
        dynamic = block(parsed("common/dynamic_modifiers/ADISCORD_dynamic_modifiers_NAM.txt"), "NAM_air_bridge_deliveries")
        self.assertEqual(scalar(dynamic, "local_supplies_for_controller"), "3")
        self.assertEqual(scalar(body, "on_map_mode"), "map_only")
        self.assertEqual(scalar(body, "days_remove"), "63")
        facts = self.postwar_facts()
        facts.update({air: 12, cash: 350, fuel: 15000, airport: 1, observers: False,
                      (site, "is_controlled_by", "NAM"): True, (site, "is_owned_by", "NAM"): True,
                      (other, "is_controlled_by", "NAM"): True, (other, "is_owned_by", "NAM"): True})
        self.assertTrue(self.matches(block(order, "visible"), facts))
        for key, amount in ((air, 11.99), (cash, 349.99), (fuel, 14999.99), (airport, 0),
                            ((site, "is_owned_by", "NAM"), False), ((site, "is_controlled_by", "NAM"), False)):
            denied = {**facts, key: amount}
            before = dict(denied)
            self.apply(block(order, "complete_effect"), denied)
            self.assertEqual(denied, before)
        occupied = {**facts, (site, "is_owned_by", "NAM"): False, observers: True}
        self.assertTrue(self.matches(block(order, "visible"), occupied))
        self.apply(block(order, "complete_effect"), occupied)
        self.assertTrue(occupied[delivery])
        self.apply(block(order, "complete_effect"), facts)
        self.assertEqual((facts[air], facts[cash], facts[fuel], facts[staff]), (0, 0, 0, True))
        self.assertTrue(facts[delivery])
        self.assertTrue(self.matches(block(dynamic, "enable"), facts, site))
        for name in ("complete_effect", "cancel_effect", "remove_effect"):
            duplicate = {**facts, air: 12, cash: 350, fuel: 15000}
            before = dict(duplicate)
            self.apply(block(other_order, name), duplicate)
            self.assertEqual(before, duplicate)
        for failure in (None, ((site, "is_controlled_by", "NAM"), False), (("NAM", "controls_state", "700"), False),
                        (("NAM", "is_subject", "no"), False), (airport, 0)):
            ended = dict(facts)
            if failure:
                ended[failure[0]] = failure[1]
                self.assertTrue(self.matches(block(order, "cancel_trigger"), ended))
                self.assertFalse(self.matches(block(dynamic, "enable"), ended, site))
                self.assertTrue(self.matches(block(order, "visible"), ended))
            self.apply(block(order, "cancel_effect" if failure else "remove_effect"), ended)
            self.apply(block(order, "cancel_effect"), ended)
            self.apply(block(order, "remove_effect"), ended)
            self.assertEqual((ended[air], ended[cash], ended[fuel], ended[staff], ended[delivery]), (12, 0, 0, False, False))

    def test_paid_air_school_commissions_one_assignable_ace_on_the_next_delivery(self):
        school = self.decisions["NAM_program_flight_schools"]
        for kind, role in (("fighter", "fighter_unique"), ("cas", "support_unique")):
            facts = self.postwar_facts()
            self.apply(block(school, "complete_effect"), facts)
            self.apply(block(school, "remove_effect"), facts)
            self.apply(block(school, "remove_effect"), facts)
            self.assertFalse(self.matches(block(school, "visible"), facts))
            order = self.decisions["NAM_air_" + kind + "_order"]
            cash = ("NAM", "variable", "ADISCORD_economy_treasury")
            denied = {**facts, cash: 299.99}
            self.apply(block(order, "complete_effect"), denied)
            self.assertNotIn(("NAM", "ace", role), denied)
            self.apply(block(order, "complete_effect"), facts)
            self.assertEqual(facts[("NAM", "ace", role)], 1)
            self.apply(block(school, "complete_effect"), facts)
            self.apply(block(school, "remove_effect"), facts)
            self.apply(block(order, "complete_effect"), facts)
            self.assertEqual(facts[("NAM", "ace", role)], 1)

    def test_victory_navy_mobilises_merchant_hulls_even_with_a_prewar_ship_programme(self):
        key = "NAM_pw_patrol_refit"
        review = block(self.postwar["NAM_pw_naval_review"], "completion_reward")
        self.assertIn(key, [e.value for e in review if e.key == "unlock_decision_tooltip"])
        decision = self.decisions[key]
        self.assertEqual(scalar(decision, "days_remove"), "42")
        convoy = ("NAM", "equipment", "convoy")
        patrol = ("NAM", "ships", "ADISCORD_coastal_patrol_ship_1")
        for school, order in (("NAM_escort_school", "NAM_escort_order"), ("NAM_active_squadron", "NAM_submarine_order")):
            for end in ("deliver", "lose_yard", "capitulate", "cancel"):
                facts = self.naval_order_facts()
                facts.update({("NAM", "has_global_flag", BASE + "_nam_victory"): True,
                              ("NAM", "has_completed_focus", "NAM_naval_construction"): True,
                              ("NAM", "has_completed_focus", school): True, convoy: 0,
                              ("NAM", "controls_province", "689"): True,
                              ("688", "is_controlled_by", "NAM"): True, ("688", "is_owned_by", "NAM"): True,
                              ("688", "numeric", "dockyard"): 1, ("688", "numeric", "naval_base"): 2,
                              ("700", "numeric", "dockyard"): 0})
                self.apply(review, facts)
                self.assertEqual(facts[convoy], 10)
                facts[("NAM", "has_completed_focus", "NAM_pw_naval_review")] = True
                self.assertTrue(self.matches(block(decision, "visible"), facts))
                self.assertTrue(self.matches(block(decision, "available"), facts))
                self.assertTrue(self.matches(block(self.decisions[order], "available"), facts))
                ship_order = dict(facts)
                self.apply(block(self.decisions[order], "complete_effect"), ship_order)
                self.assertFalse(self.matches(block(decision, "available"), ship_order))
                self.apply(block(decision, "complete_effect"), ship_order)
                self.assertEqual(ship_order[convoy], 10)
                self.apply(block(decision, "complete_effect"), facts)
                self.assertEqual(facts[convoy], 0)
                self.assertFalse(self.matches(block(self.decisions[order], "available"), facts))
                paid = dict(facts)
                self.apply(block(decision, "complete_effect"), facts)
                self.apply(block(self.decisions[order], "complete_effect"), facts)
                self.assertEqual(facts, paid)
                if end == "lose_yard":
                    facts[("NAM", "controls_province", "689")] = False
                if end == "capitulate":
                    facts[("NAM", "has_capitulated", "no")] = False
                self.assertEqual(self.matches(block(decision, "cancel_trigger"), facts), end in ("lose_yard", "capitulate"))
                self.apply(block(decision, "cancel_effect" if end == "cancel" else "remove_effect"), facts)
                self.assertEqual(facts[convoy], 0 if end == "deliver" else 10)
                self.assertEqual(facts.get(patrol, 0), int(end == "deliver"))
                settled = dict(facts)
                self.apply(block(decision, "remove_effect"), facts)
                self.apply(block(decision, "cancel_effect"), facts)
                self.assertEqual(facts, settled)
        facts[convoy] = 9.99
        self.assertFalse(self.matches(block(decision, "custom_cost_trigger"), facts))

    def test_victory_landing_supply_opens_marine_orders_and_rechecks_the_force(self):
        limit = ("NAM", "variable", "num_battalions_with_type@ADISCORD_marine_infantry")
        decision = self.decisions["NAM_marine_detachment_order"]
        for expanded, current, at_delivery in product((False, True), (3, 6, 7), (6, 7)):
            facts = self.naval_order_facts()
            facts.update({("NAM", "has_completed_focus", "NAM_pw_landing_supply"): expanded, limit: current})
            self.assertEqual(self.matches(block(decision, "visible"), facts), expanded)
            self.assertEqual(self.matches(block(decision, "available"), facts), current <= 6)
            self.apply(block(decision, "complete_effect"), facts)
            paid = expanded and current <= 6
            self.assertEqual(facts[("NAM", "numeric", "has_manpower")], 0 if paid else 3000)
            facts[limit] = at_delivery
            self.apply(block(decision, "remove_effect"), facts)
            delivered = paid and at_delivery == 6
            self.assertEqual(facts.get(("NAM", "reward", "spawned_divisions"), 0), int(delivered))
            self.assertEqual(facts[("NAM", "numeric", "has_manpower")], 0 if delivered else 3000)

    def test_victory_shipyards_fit_the_held_site_and_orders_survive_a_change_of_yard(self):
        yards = self.postwar["NAM_svetlogorsk_shipyards"]
        site = ("688", "variable", "fixture_building_slots_dockyard_yes")
        for room, port in product((0, 1), (False, True)):
            facts = self.postwar_facts()
            facts.update({site: room, ("NAM", "controls_province", "689"): port, ("NAM", "has_war", "no"): False})
            self.assertEqual(self.matches(block(yards, "available"), facts), port)
            if port:
                self.apply(block(block(yards, "completion_reward"), "688"), facts, "688")
                self.assertEqual(facts.get(("688", "building", "dockyard"), 0), room)
                self.assertEqual(facts.get(("688", "reward", "building_slots"), 0), room)
        for course, old, order in (("escort_fleet", "NAM_escort_school", "NAM_escort_order"),
                                   ("strike_fleet", "NAM_active_squadron", "NAM_submarine_order")):
            reward = block(self.postwar["NAM_pw_" + course], "completion_reward")
            offer = next(e.value for e in reward if e.key == "if" and any(x.key == "unlock_decision_tooltip" for x in e.value))
            for prior, built in product((False, True), repeat=2):
                facts = self.naval_order_facts()
                facts.update({("NAM", "has_completed_focus", old): prior,
                              ("NAM", "has_completed_focus", "NAM_naval_construction"): built})
                self.assertEqual(self.matches(block(offer, "limit"), facts), not (prior and built))
            facts.update({("NAM", "has_global_flag", BASE + "_nam_victory"): True,
                          ("NAM", "controls_province", "689"): True, ("688", "numeric", "naval_base"): 2,
                          ("688", "numeric", "dockyard"): 1, ("688", "is_owned_by", "NAM"): True,
                          ("688", "is_controlled_by", "NAM"): True})
            d = self.decisions[order]
            self.apply(block(d, "complete_effect"), facts)
            for held, harbour in product((False, True), repeat=2):
                handoff = {**facts, ("700", "is_controlled_by", "NAM"): held,
                           ("NAM", "controls_province", "16716"): harbour,
                           ("NAM", "has_country_flag", "NAM_program_naval_workshops_commissioned"): True}
                self.assertFalse(self.matches(block(d, "cancel_trigger"), handoff))
                self.apply(block(d, "remove_effect"), handoff)
                self.assertEqual(sum(n for key, n in handoff.items() if key[:2] == ("NAM", "ships")),
                                 3 if held and harbour else 2)

    def test_postwar_naval_courses_deliver_distinct_ships_with_legacy_orders(self):
        for course, kind in (("escort_fleet", "ADISCORD_escort_ship_2155"),
                             ("strike_fleet", "ADISCORD_submarine_2155")):
            for legacy in ("NAM_escort_school", "NAM_active_squadron"):
                facts = self.postwar_facts()
                facts[("NAM", "has_completed_focus", "NAM_naval_construction")] = True
                facts[("NAM", "has_completed_focus", legacy)] = True
                self.apply(block(self.postwar["NAM_pw_" + course], "completion_reward"), facts)
                self.assertEqual(facts[("NAM", "ships", kind)], 2)

    def test_government_programme_extension_depends_on_completed_institution(self):
        for short, focus in (("industrial_schedule", "cabinet_statute"),
                             ("regional_contracts", "state_chamber")):
            name = "NAM_pw_" + short
            for upgraded in (False, True):
                facts = self.expanded_programme_facts()
                facts[("NAM", "has_completed_focus", "NAM_pw_" + focus)] = upgraded
                order = self.decisions[name]
                self.apply(block(order, "complete_effect"), facts)
                self.apply(block(order, "remove_effect"), facts)
                self.assertEqual(facts[("NAM", "idea_days", name + "_idea")], 270 if upgraded else 180)

    def test_flight_training_refund_preserves_paid_fuel_when_storage_is_full(self):
        facts = self.postwar_facts()
        facts[("NAM", "numeric", "has_fuel")] = 200000
        facts[("NAM", "fuel_capacity")] = 200000
        cash = facts[("NAM", "variable", "ADISCORD_economy_treasury")]
        order = self.decisions["NAM_program_flight_schools"]
        self.apply(block(order, "complete_effect"), facts)
        self.assertEqual(facts[("NAM", "numeric", "has_fuel")], 185000)
        facts[("NAM", "numeric", "has_fuel")] = 200000
        facts[("NAM", "is_subject", "no")] = False
        self.apply(block(order, "remove_effect"), facts)
        self.assertEqual(facts[("NAM", "numeric", "has_fuel")], 200000)
        self.assertEqual(facts[("NAM", "variable", "NAM_open_fuel_reserve")], 15000)
        self.assertEqual(facts[("NAM", "variable", "ADISCORD_economy_treasury")], cash)
        snapshot = dict(facts)
        self.apply(block(order, "cancel_effect"), facts)
        self.assertEqual(facts, snapshot)

    def test_survey_raises_a_full_fields_ceiling_only_on_first_delivery(self):
        facts = self.economy_facts()
        facts[("NAM", "has_completed_focus", "NAM_deep_wells")] = False
        facts[("NAM", "has_completed_focus", "NAM_cooperative_congress")] = True
        facts[("67", "has_variable", "NAM_field_max_capacity")] = True
        facts[("67", "variable", "NAM_field_capacity")] = 11
        project = self.bind_field(self.decisions["NAM_econ_deep_drilling"])
        self.assertTrue(self.matches(block(project, "visible"), facts))
        self.assertTrue(self.matches(block(project, "available"), facts))
        initial = facts[("NAM", "variable", "ADISCORD_economy_treasury")]
        self.apply(block(project, "complete_effect"), facts)
        self.apply(block(project, "cancel_effect"), facts)
        self.assertEqual(facts[("NAM", "variable", "ADISCORD_economy_treasury")], initial)
        self.assertFalse(facts.get(("67", "has_state_flag", "NAM_artel_surveyed"), False))
        self.apply(block(project, "complete_effect"), facts)
        with patch.dict(self.effects, {"NAM_oil_refresh": []}):
            for _ in range(2):
                self.apply(block(project, "remove_effect"), facts)
        self.assertEqual(facts[("67", "variable", "NAM_field_max_capacity")], 13)
        self.assertEqual(facts[("67", "variable", "NAM_field_capacity")], 13)
        self.assertFalse(self.matches(block(project, "available"), facts))
        self.assertFalse(facts.get(("688", "has_state_flag", "NAM_artel_surveyed"), False))

    def test_barter_charter_keeps_its_own_booking_and_refunds_only_its_cargo(self):
        order = self.decisions["NAM_pw_barter_charter"]
        for reserved in (False, True):
            for lost in (False, True):
                facts = self.postwar_facts()
                facts[("NAM", "has_completed_focus", "NAM_commercial_reserve")] = reserved
                facts[("NAM", "has_country_flag", "NAM_pw_civil_busy")] = reserved
                facts[("NAM", "controls_province", "16716")] = True
                facts[("NAM", "controls_province", "689")] = False
                fuel = ("NAM", "numeric", "has_fuel")
                pp = ("NAM", "numeric", "has_political_power")
                facts[fuel] = 59999.99
                self.assertFalse(self.matches(block(order, "custom_cost_trigger"), facts))
                self.apply(block(order, "complete_effect"), facts)
                self.assertEqual(facts[fuel], 59999.99)
                facts[fuel] = 60000
                initial_pp = facts[pp]
                self.assertTrue(self.matches(block(order, "available"), facts))
                self.apply(block(order, "complete_effect"), facts)
                self.apply(block(order, "complete_effect"), facts)
                self.assertEqual(facts[fuel], 0)
                self.assertEqual(facts[pp], initial_pp - 25)
                self.assertFalse(self.matches(block(order, "available"), facts))
                facts[("NAM", "has_completed_focus", "NAM_commercial_reserve")] = True
                facts[("NAM", "controls_province", "16716")] = False
                facts[("NAM", "controls_province", "689")] = not lost
                facts[("NAM", "fuel_capacity")] = 60000
                if lost:
                    facts[fuel] = 60000
                self.assertEqual(self.matches(block(order, "cancel_trigger"), facts), lost)
                self.apply(block(order, "remove_effect"), facts)
                self.apply(block(order, "cancel_effect"), facts)
                self.apply(block(order, "remove_effect"), facts)
                self.assertEqual(facts[("NAM", "has_country_flag", "NAM_pw_civil_busy")], reserved)
                self.assertEqual(facts.get(("NAM", "equipment", "convoy"), 0), 0 if lost else 24)
                self.assertEqual(facts.get(("NAM", "equipment", "motorized_equipment"), 0), 0 if lost else 200)
                self.assertEqual(facts.get(("NAM", "variable", "NAM_open_fuel_reserve"), 0), 60000 if lost else 0)
                self.assertEqual(facts[pp], initial_pp if lost else initial_pp - 25)

    def test_development_fund_delivers_rolling_stock_to_the_current_operator(self):
        order = self.decisions["NAM_program_development_fund"]
        for subject in (False, True):
            facts = self.postwar_facts()
            facts[("SHL", "is_subject_of", "NAM")] = not subject
            self.apply(block(order, "complete_effect"), facts)
            facts[("SHL", "is_subject_of", "NAM")] = subject
            self.apply(block(order, "remove_effect"), facts)
            self.apply(block(order, "remove_effect"), facts)
            self.assertEqual(facts.get(("NAM", "equipment", "train_equipment"), 0), 0 if subject else 25)
            self.assertEqual(facts.get(("SHL", "equipment", "train_equipment"), 0), 25 if subject else 0)

    def test_war_accounts_release_exactly_one_strategic_reserve_delivery(self):
        order = self.decisions["NAM_program_strategic_reserve"]
        advance = self.decisions["NAM_pw_release_reserve"]
        funds = ("NAM", "variable", "ADISCORD_economy_treasury")
        rifles = ("NAM", "equipment", "infantry_equipment")
        receipt = ("NAM", "has_country_flag", "NAM_program_strategic_reserve_paid")
        age = ("NAM", "flag_days", receipt[2])
        booking = ("NAM", "has_country_flag", "NAM_pw_military_busy")
        self.assertEqual((scalar(order, "days_remove"), scalar(order, "days_re_enable")), ("84", "180"))
        for route, expected in (("normal", 36000), ("advance", 18000), ("cancel", 0)):
            facts = self.postwar_facts()
            facts[funds] = 900
            self.assertFalse(self.matches(block(advance, "visible"), facts))
            self.apply(block(order, "complete_effect"), facts)
            self.assertEqual(facts[funds], 0)
            self.assertTrue(facts[receipt])
            facts[age] = 27
            self.assertTrue(self.matches(block(advance, "visible"), facts))
            self.assertFalse(self.matches(block(advance, "available"), facts))
            self.apply(block(advance, "complete_effect"), facts)
            self.assertEqual(facts.get(rifles, 0), 0)
            facts[age] = 28
            self.assertTrue(self.matches(block(advance, "available"), facts))
            if route == "advance":
                self.apply(block(advance, "complete_effect"), facts)
            elif route == "normal":
                self.apply(block(order, "remove_effect"), facts)
            else:
                facts[("NAM", "is_subject", "no")] = False
                self.assertFalse(self.matches(block(advance, "available"), facts))
                self.apply(block(advance, "complete_effect"), facts)
                self.apply(block(order, "cancel_effect"), facts)
            self.assertEqual(facts.get(rifles, 0), expected)
            self.assertEqual(facts[funds], 900 if route == "cancel" else 0)
            self.assertFalse(self.matches(block(advance, "visible"), facts))
            self.assertFalse(facts[booking])
            facts[booking] = True
            closed = dict(facts)
            self.apply(block(order, "remove_effect"), facts)
            self.apply(block(order, "cancel_effect"), facts)
            self.apply(block(advance, "complete_effect"), facts)
            self.assertEqual(facts, closed)

    def test_war_accounts_build_only_after_fund_commissioning_and_refund_lost_sites(self):
        fund = self.decisions["NAM_program_development_fund"]
        order = self.decisions["NAM_pw_harbour_slipway"]
        focus = block(self.postwar["NAM_pw_war_accounts"], "completion_reward")
        cash = ("NAM", "variable", "ADISCORD_economy_treasury")
        dockyard = ("700", "building", "dockyard")
        slots = ("700", "variable", "fixture_building_slots_dockyard_no")
        initial = self.postwar_facts()
        for military, civil, expected in (
                (True, False, ["NAM_pw_release_reserve"]), (False, True, ["NAM_pw_harbour_slipway"]),
                (False, False, ["NAM_pw_release_reserve", "NAM_pw_harbour_slipway"])):
            initial[("NAM", "has_completed_focus", "NAM_pw_strategic_reserve")] = military
            initial[("NAM", "has_completed_focus", "NAM_pw_development_fund")] = civil
            shown = [e.value for _, e in selected_effects(self.expand(focus), initial, "NAM")
                     if e.key == "unlock_decision_tooltip"]
            self.assertEqual(shown, expected)
        initial[("NAM", "has_completed_focus", "NAM_pw_development_fund")] = True
        initial[("700", "numeric", "naval_base")] = 1
        initial[slots] = 1
        initial[cash] = 1900
        self.assertFalse(self.matches(block(order, "available"), initial))
        self.apply(block(fund, "complete_effect"), initial)
        self.assertFalse(self.matches(block(order, "available"), initial))
        self.apply(block(fund, "remove_effect"), initial)
        self.assertTrue(self.matches(block(order, "available"), initial))
        self.assertFalse(self.matches(block(fund, "visible"), initial))
        self.assertEqual(initial[cash], 900)
        poor = {**initial, cash: 899.99}
        self.assertFalse(self.matches(block(order, "custom_cost_trigger"), poor))
        self.apply(block(order, "complete_effect"), poor)
        self.assertEqual(poor[cash], 899.99)
        cancelled = initial.copy()
        self.apply(block(order, "complete_effect"), cancelled)
        self.apply(block(order, "cancel_effect"), cancelled)
        self.assertEqual(cancelled[cash], 900)
        self.assertFalse(cancelled[("NAM", "has_country_flag", "NAM_pw_civil_busy")])
        cancelled[("NAM", "has_country_flag", "NAM_pw_civil_busy")] = True
        self.apply(block(order, "remove_effect"), cancelled)
        self.apply(block(order, "cancel_effect"), cancelled)
        self.assertTrue(cancelled[("NAM", "has_country_flag", "NAM_pw_civil_busy")])
        self.assertEqual(cancelled.get(dockyard, 0), 0)
        self.assertEqual(cancelled[cash], 900)
        for loss in (None, ("NAM", "controls_province", "16716"), ("NAM", "owns_state", "700"),
                     ("NAM", "controls_state", "700"), ("NAM", "is_subject", "no"),
                     ("700", "numeric", "naval_base"), slots):
            with self.subTest(loss=loss):
                facts = initial.copy()
                self.apply(block(order, "complete_effect"), facts)
                self.apply(block(order, "complete_effect"), facts)
                self.assertEqual(facts[cash], 0)
                self.assertFalse(self.matches(block(order, "available"), facts))
                if loss:
                    facts[loss] = 0
                self.assertEqual(self.matches(block(order, "cancel_trigger"), facts), bool(loss))
                self.apply(block(order, "remove_effect"), facts)
                self.assertEqual(facts.get(dockyard, 0), 0 if loss else 1)
                self.assertEqual(facts[cash], 900 if loss else 0)
                self.assertFalse(facts[("NAM", "has_country_flag", "NAM_pw_civil_busy")])
                self.assertEqual(facts[("700", "reward", "building_slots")], 2)
                self.assertEqual(facts[("NAM", "equipment", "train_equipment")], 25)
                closed = facts.copy()
                self.apply(block(order, "cancel_effect"), facts)
                self.apply(block(order, "remove_effect"), facts)
                self.assertEqual(facts, closed)

    def test_southern_civil_order_keeps_its_site_and_refunds_lost_subject(self):
        cash = ("NAM", "variable", "ADISCORD_economy_treasury")
        for failure in (None, "subject", "ownership", "control", "station", "capacity"):
            facts = self.postwar_facts()
            facts[cash] = 900
            facts[("SHL", "is_subject_of", "NAM")] = True
            facts[("699", "is_owned_by", "SHL")] = True
            facts[("699", "is_controlled_by", "SHL")] = True
            facts[("699", "fixture_free_building_slots", "industrial_complex:1:yes")] = True
            for province in ("16719", "16715", "16713"):
                facts[("SHL", "controls_province", province)] = True
            order = self.decisions["NAM_program_southern_local_offices"]
            self.assertTrue(self.matches(block(order, "available"), facts))
            self.apply(block(order, "complete_effect"), facts)
            self.assertEqual(facts[cash], 0)
            if failure == "subject":
                facts[("SHL", "is_subject_of", "NAM")] = False
            elif failure in ("ownership", "control"):
                facts[("699", "is_owned_by" if failure == "ownership" else "is_controlled_by", "SHL")] = False
            elif failure == "station":
                facts[("SHL", "controls_province", "16715")] = False
            elif failure == "capacity":
                facts[("699", "fixture_free_building_slots", "industrial_complex:1:yes")] = False
            self.apply(block(order, "remove_effect"), facts)
            delivered = failure in (None, "capacity")
            self.assertEqual(facts.get(("699", "reward", "building_slots"), 0), 2 if delivered else 0)
            self.assertEqual(facts.get(("SHL", "equipment", "motorized_equipment"), 0), 200 if delivered else 0)
            self.assertEqual(facts.get(("NAM", "equipment", "train_equipment"), 0), 16 if delivered else 0)
            self.assertEqual(facts[cash], 0 if delivered else 900)
            self.assertFalse(facts[("NAM", "has_country_flag", "NAM_pw_civil_busy")])
            snapshot = dict(facts)
            self.apply(block(order, "remove_effect"), facts)
            self.apply(block(order, "cancel_effect"), facts)
            self.assertEqual(facts, snapshot)

    def test_southern_rail_orders_use_continuous_owned_paths(self):
        from tools.builders import build_adiscord_strategic_regions as geography
        types, colours = geography.load_province_definitions()
        adjacency = geography.load_province_adjacency(types, colours, include_special_adjacencies=False)
        states = geography.load_states()
        for short, endpoint in (("rail_priority", 9016), ("logistics_depots", 9016), ("freight_depots", 6961), ("southern_corridor", 16716)):
            effect = self.expand(self.effects["NAM_program_" + short + "_settle"])
            railway = next(e.value for e in walk(effect) if e.key == "build_railway")
            path = [int(e.value) for e in block(railway, "path")]
            start = 16716 if short in ("logistics_depots", "freight_depots") else 16721
            self.assertEqual((path[0], path[-1]), (start, endpoint))
            for left, right in zip(path, path[1:]):
                self.assertIn(right, adjacency[left], (short, left, right))
            needed = {str(state) for state, provinces in states.items() if set(path) & provinces}
            owned = {e.value for e in walk(effect) if e.key == "owns_state"}
            self.assertTrue(needed <= owned, (short, needed - owned))
            for phase in ("available", "cancel_trigger", "complete_effect"):
                held = {e.value for e in walk(self.expand(block(self.decisions["NAM_program_" + short], phase))) if e.key == "controls_province"}
                self.assertTrue(set(map(str, path)) <= held, (short, phase))

    def test_expanded_orders_preserve_cash_slots_and_late_callbacks(self):
        cash_key = ("NAM", "variable", "ADISCORD_economy_treasury")
        cases = (
            ("reserve_centres", 850, "military", ("NAM", "equipment", "infantry_equipment"), 27000, None),
            ("rail_priority", 650, "civil", ("NAM", "equipment", "train_equipment"), 45, None),
            ("civil_engineering", 1000, "civil", ("700", "building", "industrial_complex"), 1, "700"),
        )
        for short, price, channel, result_key, amount, state in cases:
            name = "NAM_program_" + short
            decision = self.decisions[name]
            for outcome in ("delivery", "subjugation", "occupied", "full_site"):
                if state is None and outcome in ("occupied", "full_site"):
                    continue
                facts = self.postwar_facts()
                facts[("700", "fixture_free_building_slots", "industrial_complex:1:yes")] = True
                facts[cash_key] = price - 0.01
                before = dict(facts)
                self.assertFalse(self.matches(block(decision, "custom_cost_trigger"), facts))
                self.apply(block(decision, "complete_effect"), facts)
                self.assertEqual(facts, before, (name, "fractional shortage"))
                facts[cash_key] = price
                self.assertTrue(self.matches(block(decision, "available"), facts), name)
                self.apply(block(decision, "complete_effect"), facts)
                self.assertEqual(facts[cash_key], 0)
                paid = dict(facts)
                self.apply(block(decision, "complete_effect"), facts)
                self.assertEqual(facts, paid, (name, "double payment"))
                other = "NAM_pw_veteran_course" if channel == "military" else "NAM_pw_industrial_schedule"
                self.assertFalse(self.matches(block(self.decisions[other], "available"), facts))
                facts[("NAM", "has_war", "yes")] = True
                facts[("NAM", "has_war", "no")] = False
                self.assertFalse(self.matches(block(decision, "cancel_trigger"), facts))
                if outcome == "subjugation":
                    facts[("NAM", "is_subject", "no")] = False
                elif outcome == "occupied":
                    facts[("NAM", "controls_state", state)] = False
                elif outcome == "full_site":
                    facts[(state, "fixture_free_building_slots", "industrial_complex:1:yes")] = False
                self.apply(block(decision, "remove_effect"), facts)
                self.assertEqual(facts.get(result_key, 0), amount if outcome == "delivery" else 0)
                delivered = outcome in ("delivery", "full_site")
                self.assertEqual(facts[cash_key], 0 if delivered else price)
                if short == "civil_engineering":
                    self.assertEqual(facts.get(("NAM", "equipment", "motorized_equipment"), 0), 240 if delivered else 0)
                self.assertFalse(facts[("NAM", "has_country_flag", "NAM_pw_" + channel + "_busy")])
                settled = dict(facts)
                self.apply(block(decision, "remove_effect"), facts)
                self.apply(block(decision, "cancel_effect"), facts)
                self.assertEqual(facts, settled, (name, "late callbacks"))

    def test_postwar_ai_expansion_has_reachable_nonexclusive_prerequisites(self):
        plans = parsed("common/ai_strategy_plans/ADISCORD_NAM_plans.txt")
        for plan_name in ("NAM_postwar_plan", "NAM_postwar_vertical_plan", "NAM_postwar_pragmatic_plan"):
            completed = set()
            for entry in block(block(plans, plan_name), "ai_national_focuses"):
                name = entry.value
                for group in (e.value for e in self.postwar[name] if e.key == "prerequisite"):
                    self.assertTrue(any(p.value in completed for p in group), (plan_name, name))
                for group in (e.value for e in self.postwar[name] if e.key == "mutually_exclusive"):
                    self.assertFalse(any(p.value in completed for p in group), (plan_name, name))
                completed.add(name)

    def test_postwar_delivery_has_real_route_specific_results(self):
        checks = {
            "NAM_veteran_housing": (("700", "building", "industrial_complex"), 1),
            "NAM_postwar_rearmament": (("NAM", "equipment", "infantry_equipment"), 9000),
            "NAM_district_audit": (("NAM", "variable", "ADISCORD_economy_treasury"), 250),
            "NAM_pw_veteran_course": (("NAM", "numeric", "army_experience"), 25),
            "NAM_pw_garrison_order": (("NAM", "equipment", "support_equipment"), 60),
            "NAM_pw_fuel_quota": (("NAM", "numeric", "has_fuel"), 6000),
            "NAM_pw_state_arsenal": (("700", "building", "arms_factory"), 1),
            "NAM_pw_district_congress": (("NAM", "variable", "NAM_grp_dist_support"), 10),
            "NAM_pw_district_schools": (("NAM", "equipment", "support_equipment"), 60),
            "NAM_pw_militia_reserve": (("NAM", "numeric", "has_manpower"), 6000),
            "NAM_pw_district_cooperative": (("688", "building", "industrial_complex"), 1),
            "NAM_pw_export_shipment": (("NAM", "variable", "ADISCORD_economy_treasury"), 450),
        }
        with patch.dict(self.effects, {"NAM_groups_refresh": []}):
            for name, (key, amount) in checks.items():
                facts = self.postwar_facts()
                if name == "NAM_pw_export_shipment":
                    facts[("NAM", "numeric", "has_fuel")] = 60000
                decision = self.decisions[name]
                self.apply(block(decision, "complete_effect"), facts)
                before = facts.get(key, 0)
                self.apply(block(decision, "remove_effect"), facts)
                self.assertEqual(facts[key] - before, amount, name)
                delivered = dict(facts)
                self.apply(block(decision, "remove_effect"), facts)
                self.apply(block(decision, "cancel_effect"), facts)
                self.assertEqual(facts, delivered, (name, "duplicate delivery/refund"))

    def test_postwar_channels_share_payment_lifetime_and_sites_are_rechecked(self):
        for channel in ("civil", "military"):
            facts = self.postwar_facts()
            selected = [name for name, row in self.POSTWAR_ORDERS.items() if row[-1] == channel]
            self.apply(block(self.decisions[selected[0]], "complete_effect"), facts)
            for name, row in self.POSTWAR_ORDERS.items():
                self.assertEqual(self.matches(block(self.decisions[name], "available"), facts), row[-1] != channel, name)
                if row[-1] == channel:
                    before = dict(facts)
                    self.apply(block(self.decisions[name], "complete_effect"), facts)
                    self.assertEqual(facts, before, (name, "cannot overwrite channel receipt"))
            self.apply(block(self.decisions[selected[0]], "cancel_effect"), facts)
            for name in selected:
                self.assertTrue(self.matches(block(self.decisions[name], "available"), facts), name)
        for name, state, kind in (("NAM_veteran_housing", "700", "industrial_complex"),
                                  ("NAM_pw_state_arsenal", "700", "arms_factory"),
                                  ("NAM_pw_district_cooperative", "688", "industrial_complex")):
            for reason in ("owner", "controller", "full"):
                facts = self.postwar_facts()
                start = facts[("NAM", "variable", "ADISCORD_economy_treasury")]
                decision = self.decisions[name]
                self.apply(block(decision, "complete_effect"), facts)
                lost = (("NAM", "owns_state", state) if reason == "owner" else
                        ("NAM", "controls_state", state) if reason == "controller" else
                        (state, "variable", f"fixture_building_slots_{kind}_no"))
                facts[lost] = False
                if name == "NAM_pw_district_cooperative" and reason == "full":
                    facts[(state, "fixture_free_building_slots", f"{kind}:1:yes")] = False
                    self.assertFalse(self.matches(block(decision, "cancel_trigger"), facts))
                    self.apply(block(decision, "remove_effect"), facts)
                    self.assertEqual(facts[(state, "reward", "building_slots")], 1)
                    self.assertEqual(facts[("NAM", "variable", "ADISCORD_economy_treasury")], start - 450)
                    continue
                self.assertTrue(self.matches(block(decision, "cancel_trigger"), facts), (name, reason))
                self.apply(block(decision, "remove_effect"), facts)
                self.assertEqual(facts[("NAM", "variable", "ADISCORD_economy_treasury")], start)
                self.assertNotIn((state, "building", kind), facts)

    def test_postwar_trust_gates_and_successor_unlocks_are_visible(self):
        for name, support in (("NAM_pw_militia_reserve", 55), ("NAM_pw_district_cooperative", 50)):
            facts = self.postwar_facts()
            facts[("NAM", "variable", "NAM_grp_dist_support")] = support - 0.01
            self.assertTrue(self.matches(block(self.decisions[name], "visible"), facts))
            self.assertFalse(self.matches(block(self.decisions[name], "available"), facts))
            facts[("NAM", "variable", "NAM_grp_dist_support")] = support
            self.assertTrue(self.matches(block(self.decisions[name], "available"), facts))
        facts = self.postwar_facts()
        facts[("NAM", "has_completed_focus", "NAM_domestic_refining")] = False
        self.assertTrue(self.matches(block(self.decisions["NAM_econ_petrochemical_batch"], "visible"), facts))
        for name in self.POSTWAR_ORDERS:
            authorising_focuses = [e.value for e in walk(self.expand(block(self.decisions[name], "visible")))
                                  if e.key == "has_completed_focus"]
            self.assertTrue(authorising_focuses, name)
            for focus in authorising_focuses:
                self.assertIn(name, [e.value for e in walk(block({**self.postwar, **self.defeated}[focus], "completion_reward"))
                                     if e.key == "unlock_decision_tooltip"])

    def test_tribute_buyout_debits_only_current_creditors_and_preserves_overflow(self):
        focus = self.defeated["NAM_defeat_early_tribute"]
        reserve = "NAM_rw_tribute_fuel_reserve"
        for age, share in ((0, 45000), (121, 45000), (122, 30000), (243, 30000), (244, 15000)):
            for efl, azh in product(("peace", "war", "absent"), repeat=2):
                price = share * (int(efl == "peace") + int(azh == "peace"))
                facts = self.facts(fuel=price)
                facts[("NAM", "has_country_flag", "NAM_rw_tribute")] = True
                facts[("NAM", "flag_days", "NAM_rw_tribute")] = age
                for tag, status, room in (("EFL", efl, 2000), ("AZH", azh, 0)):
                    facts[(tag, "exists", "yes")] = status != "absent"
                    facts[(tag, "has_war_with", "NAM")] = status == "war"
                    facts[(tag, "fuel_capacity")] = 50000
                    facts[(tag, "numeric", "has_fuel")] = 50000 - room
                fuel = ("NAM", "numeric", "has_fuel")
                if price:
                    facts[fuel] -= 0.01
                    self.assertFalse(self.matches(block(focus, "available"), facts))
                    facts[fuel] = price
                self.assertEqual(self.matches(block(focus, "available"), facts), bool(price))
                with patch.dict(self.effects, {"NAM_oil_refresh": []}):
                    self.apply(block(focus, "completion_reward"), facts)
                    self.apply(block(focus, "completion_reward"), facts)
                self.assertEqual(facts[fuel], 0)
                self.assertEqual(facts[("NAM", "has_country_flag", "NAM_rw_tribute")], not price)
                for tag, status, room in (("EFL", efl, 2000), ("AZH", azh, 0)):
                    received = min(room, share) if status == "peace" else 0
                    self.assertEqual(facts[(tag, "numeric", "has_fuel")], 50000 - room + received)
                    self.assertEqual(facts.get((tag, "variable", reserve), 0),
                                     share - received if status == "peace" else 0)
                    if status == "peace":
                        facts[(tag, "numeric", "has_fuel")] = 0
                        self.apply(self.effects["NAM_rw_fill_tribute_tanks"], facts, tag)
                        self.assertEqual(facts[(tag, "numeric", "has_fuel")], share - received)
                        self.assertEqual(facts.get((tag, "variable", reserve), 0), 0)
        actions = block(parsed("common/on_actions/03_ADISCORD_nam_resource_war_on_actions.txt"), "on_actions")
        for tag in ("EFL", "AZH"):
            self.assertEqual(scalar(block(block(actions, f"on_monthly_{tag}"), "effect"),
                                    "NAM_rw_fill_tribute_tanks"), "yes")

    def test_diplomatic_fuel_batches_conserve_stock_at_exact_boundaries(self):
        for fuel in (14999.99, 15000, 29999.99, 30000):
            facts = self.facts(fuel=fuel)
            facts[("NAM", "has_country_flag", "NAM_rw_tribute")] = True
            for tag in ("EFL", "AZH"):
                facts[(tag, "exists", "yes")] = True
            self.apply(self.effects["NAM_rw_deliveries_monthly"], facts)
            delivered = sum(facts.get((tag, "numeric", "has_fuel"), 0) for tag in ("EFL", "AZH"))
            self.assertEqual(delivered, min(int(fuel // 15000), 2) * 15000)
            self.assertAlmostEqual(facts[("NAM", "numeric", "has_fuel")] + delivered, fuel)
        for fuel in (29999.99, 30000, 59999.99, 60000):
            facts = self.northern_facts(recipients=("EFL", "AZH"))
            facts[("NAM", "numeric", "has_fuel")] = fuel
            for tag in ("EFL", "AZH"):
                facts[(tag, "numeric", "has_fuel")] = 0
                self.apply(self.effects["NAM_rus_supply_member"], facts, current_scope=tag)
            delivered = sum(facts.get((tag, "numeric", "has_fuel"), 0) for tag in ("EFL", "AZH"))
            self.assertEqual(delivered, min(int(fuel // 30000), 2) * 30000)
            self.assertAlmostEqual(facts[("NAM", "numeric", "has_fuel")] + delivered, fuel)

    def test_fuel_transfer_tooltips_match_current_batch_sizes(self):
        amounts = {
            "NAM_rw_21_b_tt": 15000, "NAM_rw_21_c_tt": 120000,
            "NAM_defeat_early_tribute_tt": 15000, "NAM_bw_summary_tt": 15000,
            "NAM_charter_fuel_aid_tt": 25000, "NAM_south_allied_fuel_tt": 25000,
            "NAM_oil_10_b_tt": 30000, "NAM_pw_fuel_aid_cost": 25000,
            "NAM_pw_fuel_aid_cost_blocked": 25000, "NAM_pw_fuel_aid_cost_tooltip": 25000,
        }
        for language in ("russian", "english"):
            text = read(f"localisation/{language}/ADISCORD_nam_resource_war_l_{language}.yml")
            for key, amount in amounts.items():
                line = re.search(r"(?m)^ " + re.escape(key) + r":[^\n]*", text).group(0)
                self.assertRegex(line, rf"{amount}§! £fuel_texticon", (language, key))

    def test_postwar_fuel_aid_conserves_stocks_for_one_selected_recipient(self):
        southern = block(parsed(f"common/decisions/{BASE}_decisions.txt"), "ADISCORD_south_final_war_category")
        definitions = dict(self.decisions)
        definitions["NAM_south_allied_fuel"] = block(southern, "NAM_south_allied_fuel")
        for name, helper, predicate in (("NAM_charter_fuel_aid", "NAM_deliver_charter_fuel", "NAM_pw_charter_recipient"),
                                        ("NAM_south_allied_fuel", "NAM_south_allied_fuel_delivery", "NAM_south_fuel_recipient")):
            decision = self.bind_field(definitions[name], "EFL")
            # Native targeting binds FROM through the helper as well as the decision.
            with patch.dict(self.effects, {helper: self.bind_field(self.effects[helper], "EFL")}):
                for valid, fuel in product((False, True), (24999.99, 25000)):
                    facts = self.postwar_facts()
                    facts[("NAM", "has_completed_focus", "NAM_south_allied_fuel_office")] = True
                    facts[("NAM", "numeric", "has_political_power")] = 25
                    facts[("NAM", "numeric", "has_fuel")] = fuel
                    facts[("NAM", "ADISCORD_south_final_active", "yes")] = True
                    facts[("NAM", "has_country_flag", "ADISCORD_south_north_leader")] = True
                    facts[("EFL", "numeric", "has_fuel")] = 100
                    facts[("AZH", "numeric", "has_fuel")] = 100
                    facts[("EFL", "exists", "yes")] = valid
                    facts[("EFL", "has_capitulated", "no")] = True
                    facts[("EFL", "is_in_faction_with", "NAM")] = True
                    facts[("EFL", "ADISCORD_south_regional_country", "yes")] = True
                    facts[("EFL", "ADISCORD_south_on_north_side", "yes")] = True
                    self.apply(block(decision, "complete_effect"), facts)
                    success = valid and fuel == 25000
                    self.assertEqual(facts[("EFL", "numeric", "has_fuel")], 25100 if success else 100, name)
                    self.assertEqual(facts[("AZH", "numeric", "has_fuel")], 100, name)
                    self.assertEqual(facts[("NAM", "numeric", "has_political_power")], 0 if success else 25, name)
                    self.assertEqual(facts[("NAM", "numeric", "has_fuel")], 0 if success else fuel, name)

    def test_southern_heritage_opens_the_missing_reconstruction_programme(self):
        reward = block(self.postwar["NAM_south_heritage"], "completion_reward")
        for civilian in (False, True):
            with self.subTest(civilian=civilian):
                facts = self.postwar_facts()
                facts[("NAM", "has_completed_focus", "NAM_civil_dividend")] = civilian
                facts[("NAM", "has_completed_focus", "NAM_armed_peace")] = not civilian
                facts[("NAM", "has_completed_focus", "NAM_south_heritage")] = False
                facts[("NAM", "has_completed_focus", "NAM_pw_standard_projects")] = False
                missing = "NAM_postwar_rearmament" if civilian else "NAM_veteran_housing"
                decision = self.decisions[missing]
                self.assertFalse(self.matches(block(decision, "visible"), facts))
                before = facts.copy()
                self.apply(block(decision, "complete_effect"), facts)
                self.assertEqual(facts, before)
                shown = [entry.value for _, entry in selected_effects(self.expand(reward), facts, "NAM")
                         if entry.key == "unlock_decision_tooltip"]
                self.assertEqual(shown, [missing])
                facts[("NAM", "has_completed_focus", "NAM_south_heritage")] = True
                self.assertTrue(self.matches(block(decision, "visible"), facts))
                self.apply(block(decision, "complete_effect"), facts)
                self.assertTrue(facts[("NAM", "has_country_flag", missing + "_paid")])
                pp, treasury, _, _, _ = self.POSTWAR_ORDERS[missing]
                self.assertEqual(facts[("NAM", "numeric", "has_political_power")], before[("NAM", "numeric", "has_political_power")] - pp)
                self.assertEqual(facts[("NAM", "variable", "ADISCORD_economy_treasury")], before[("NAM", "variable", "ADISCORD_economy_treasury")] - treasury)
                self.apply(block(decision, "remove_effect"), facts)
                result = ("NAM", "equipment", "infantry_equipment") if civilian else ("700", "building", "industrial_complex")
                self.assertEqual(facts[result] - before.get(result, 0), 9000 if civilian else 1)
                self.assertEqual(facts[("NAM", "has_completed_focus", "NAM_civil_dividend")], civilian)
                self.assertEqual(facts[("NAM", "has_completed_focus", "NAM_armed_peace")], not civilian)

    def test_charter_aid_unlock_is_shown_only_for_an_actual_eligible_ally(self):
        reward = block(self.postwar["NAM_oil_fund"], "completion_reward")
        events = {scalar(e.value, "id"): e.value for e in parsed("events/ADISCORD_south_final_war_events.txt")
                  if e.key == "country_event"}
        answer = self.bind_field(block(events["ADISCORD_south.42"], "option"), "EFL")
        for allied in (False, True):
            facts = self.postwar_facts()
            facts[("NAM", "tag", "NAM")] = True
            facts[("EFL", "exists", "yes")] = True
            facts[("EFL", "has_capitulated", "no")] = True
            facts[("EFL", "is_in_faction_with", "NAM")] = allied
            for entries in (reward, answer):
                shown = [entry.value for _, entry in selected_effects(self.expand(entries), facts, "NAM")
                         if entry.key == "unlock_decision_tooltip"]
                self.assertEqual("NAM_charter_fuel_aid" in shown, allied)
            if not allied:
                shown = [entry.value for _, entry in selected_effects(self.expand(reward), facts, "NAM")
                         if entry.key == "custom_effect_tooltip"]
                self.assertIn("NAM_charter_fuel_aid_future_tt", shown)

    def test_veyran_invasion_needs_the_southern_settlement_and_one_imperial_preparation(self):
        local = "NAM_svetlogorsk_settlement"
        imperial = "NAM_veyran_union_charter"
        embarkation = "NAM_veyran_embarkation_staff"
        convoy = "NAM_veyran_convoy_charter"
        arsenal = "NAM_veyran_arsenal_contract"
        counterplan = "NAM_veyran_counterplan"
        invasion = "NAM_veyran_invasion"
        endings = {"NAM_ladder_ending_iron", "NAM_ladder_ending_service"}
        for first, second in ((local, imperial), (convoy, arsenal)):
            for name, excluded in ((first, second), (second, first)):
                self.assertIn(excluded, [e.value for e in block(self.postwar[name], "mutually_exclusive")])
        for blocked in ({"NAM_south_heritage"}, {imperial}, {embarkation}, {convoy, arsenal}, {counterplan}):
            self.assertNotIn(invasion, reachable(self.postwar, blocked), blocked)
        for ending, preparation in product(endings, (convoy, arsenal)):
            blocked = (endings - {ending}) | ({convoy, arsenal} - {preparation}) | {local}
            self.assertIn(invasion, reachable(self.postwar, blocked), (ending, preparation))
            route = (imperial, embarkation, preparation, counterplan, invasion)
            self.assertEqual(7 * sum(int(scalar(self.postwar[name], "cost")) for name in route), 91)
        self.assertIn(local, reachable(self.postwar, {imperial, convoy, arsenal}))
        for language in ("russian", "english"):
            loc = read(f"localisation/{language}/{BASE}_l_{language}.yml")
            keys = {match.group(1) for line in loc.splitlines() if (match := ENTRY.match(line))}
            for name in (local, imperial, embarkation, convoy, arsenal, counterplan, invasion):
                self.assertTrue({name, name + "_desc"} <= keys, (language, name))

    def test_veyran_governorate_has_an_exclusive_autonomy_real_icon_and_localised_identity(self):
        from PIL import Image

        autonomy_id = "autonomy_NAM_imperial_governorate"
        levels = [
            row.value for path in (ROOT / "common/autonomous_states").glob("*.txt")
            for row in parsed(path) if row.key == "autonomy_state" and scalar(row.value, "id") == autonomy_id
        ]
        self.assertEqual(len(levels), 1)
        level = levels[0]
        self.assertEqual(scalar(level, "is_puppet"), "yes")
        self.assertEqual([row.value for row in block(level, "allowed_levels_filter")], [autonomy_id])
        for name in ("cic_to_overlord_factor", "mic_to_overlord_factor", "resources_to_overlord_factor"):
            self.assertEqual(Decimal(scalar(block(level, "modifier"), name)), 1, name)

        sprites = block(parsed("interface/ADISCORD_autonomy_icons.gfx"), "spriteTypes")
        icon_name = "GFX_" + autonomy_id + "_icon"
        icon_paths = {
            scalar(row.value, "name"): next(e.value for e in row.value if e.key.lower() == "texturefile")
            for row in sprites if row.key == "spriteType"
        }
        own_icon = icon_paths.pop(icon_name)
        self.assertNotIn(own_icon, icon_paths.values())
        with Image.open(ROOT / own_icon) as icon:
            self.assertEqual(icon.size, (35, 36))
            pixels = icon.convert("RGBA")
            self.assertEqual(pixels.getchannel("A").getextrema(), (0, 255))
            self.assertGreater(sum(color[3] > 0 for _, color in pixels.getcolors(35 * 36)), 8)

        tags = [entry.value for path in (ROOT / "common/country_tags").glob("*.txt")
                for entry in parsed(path) if entry.key == "SNG"]
        self.assertEqual(len(tags), 1)
        self.assertTrue((ROOT / "common" / tags[0]).is_file())
        self.assertEqual(len(list((ROOT / "history/countries").glob("SNG - *.txt"))), 1)
        for language in ("russian", "english"):
            keys = {match[1] for path in (ROOT / "localisation" / language).glob("*.yml")
                    for line in read(path).splitlines() if (match := ENTRY.match(line)) and match[2]}
            self.assertTrue({autonomy_id, "SNG", "SNG_DEF", "SNG_ADJ"} <= keys, language)

    def veyran_facts(self):
        return {
            ("NAM", "exists", "yes"): True,
            ("NAM", "has_capitulated", "no"): True,
            ("NAM", "is_subject", "no"): True,
            ("NAM", "has_global_flag", BASE + "_nam_victory"): True,
            ("NAM", "has_global_flag", "ADISCORD_south_hegemon_NAM"): True,
            ("NAM", "has_government", "etatism"): True,
            ("NAM", "ruling_leader"): "NAM_Egor_Rom",
            ("NAM", "has_completed_focus", "NAM_service_state"): True,
            ("NAM", "has_completed_focus", "NAM_ladder_ending_iron"): True,
            ("NAM", "has_variable", "NAM_prewar_balance"): True,
            ("NAM", "variable", "NAM_prewar_balance"): -0.5,
        }

    def test_veyran_choice_only_opens_for_rom_after_both_wars(self):
        facts = self.veyran_facts()
        for name in ("NAM_svetlogorsk_settlement", "NAM_veyran_union_charter"):
            available = block(self.postwar[name], "available")
            self.assertTrue(self.matches(available, facts), name)
            service = {**facts, ("NAM", "has_completed_focus", "NAM_ladder_ending_iron"): False}
            self.assertFalse(self.matches(available, service), name)
            service["NAM", "has_completed_focus", "NAM_ladder_ending_service"] = True
            self.assertTrue(self.matches(available, service), name)
            for field, rejected in (
                (("is_subject", "no"), False),
                (("has_global_flag", BASE + "_nam_victory"), False),
                (("has_global_flag", BASE + "_standoff"), True),
                (("has_global_flag", "ADISCORD_south_hegemon_NAM"), False),
                (("has_government", "etatism"), False),
                (("ruling_leader",), "NAM_coup_governor"),
                (("variable", "NAM_prewar_balance"), -0.25),
            ):
                blocked = {**facts, ("NAM", *field): rejected}
                self.assertFalse(self.matches(available, blocked), (name, field))

    def test_veyran_expedition_pays_one_contract_and_prepares_for_the_actual_unifier(self):
        cash = ("NAM", "variable", "ADISCORD_economy_treasury")
        for contract, payload in (
            ("convoy_charter", {("equipment", "convoy"): 45, ("numeric", "has_fuel"): 35000}),
            ("arsenal_contract", {("equipment", "infantry_equipment"): 1600, ("equipment", "artillery_equipment"): 72}),
        ):
            focus = self.postwar["NAM_veyran_" + contract]
            facts = self.veyran_facts()
            for stock, ready in ((299.9, False), (300, True)):
                facts[cash] = stock
                self.assertEqual(self.matches(block(focus, "available"), facts), ready, contract)
            self.apply(block(focus, "completion_reward"), facts)
            self.assertEqual(facts[cash], 0)
            self.assertEqual(facts["NAM", "variable", "ADISCORD_economy_current_month_action_costs"], 300)
            for field, amount in payload.items():
                self.assertEqual(facts[("NAM", *field)], amount, contract)
        focus = self.postwar["NAM_veyran_counterplan"]
        west = parsed("common/scripted_triggers/ADISCORD_west_final_war_triggers.txt")
        deliveries = {
            "worker": ("add_intel", {"target": "WKR", "navy_intel": "25"}),
            "joint": ("add_equipment_to_stockpile", {"type": "support_equipment", "amount": "240", "producer": "NAM"}),
            "utilitarian": ("add_equipment_to_stockpile", {"type": "motorized_equipment", "amount": "180", "producer": "NAM"}),
        }
        with patch.dict(self.triggers, {e.key: e.value for e in west}):
            for route, nation in VORKERLAND_UNIFIERS:
                action, result = deliveries[route]
                facts = self.veyran_facts()
                facts.update({
                    ("event_target", VORKERLAND): nation,
                    ("NAM", "has_global_flag", "ADISCORD_vorkerland_collapse_finished"): True,
                    ("NAM", "has_global_flag", "ADISCORD_vorkerland_reunification_verified"): True,
                    (nation, "exists", "yes"): True,
                    (nation, "is_subject", "no"): True,
                    (nation, "has_capitulated", "no"): True,
                    (nation, "has_country_flag", "ADISCORD_vorkerland_central_unifier"): True,
                })
                self.assertFalse(self.matches(block(focus, "available"), facts))
                facts[nation, "has_country_flag", "ADISCORD_vorkerland_route_" + route] = True
                self.assertTrue(self.matches(block(focus, "available"), facts), route)
                # A claimant that is not the country target is not the unifier.
                for other in ("WRK", "WKR", "VAD", "TVA"):
                    if other != nation:
                        moved = {**facts, ("event_target", VORKERLAND): other}
                        self.assertFalse(self.matches(block(focus, "available"), moved), (route, other))
                reward = selected_effects(self.expand(block(focus, "completion_reward")), facts, "NAM")
                delivered = [
                    (scope, row.key, {
                        e.key: event_target(e.value, facts) if e.value == VORKERLAND_SCOPE else e.value
                        for e in row.value
                    })
                    for scope, row in reward if row.key in ("add_intel", "add_equipment_to_stockpile")
                ]
                self.assertEqual(delivered, [("NAM", action, result)], route)

    def test_veyran_domestic_route_opens_paid_construction_in_the_held_border_districts(self):
        focus = self.postwar["NAM_svetlogorsk_settlement"]
        decision = self.decisions["NAM_pw_regional_contracts"]
        domestic = ("NAM", "has_completed_focus", "NAM_svetlogorsk_settlement")
        facts = self.veyran_facts()
        self.assertIn("NAM_pw_regional_contracts", [e.value for e in walk(block(focus, "completion_reward"))
                                                   if e.key == "unlock_decision_tooltip"])
        self.assertFalse(self.matches(block(decision, "visible"), facts))
        facts[domestic] = True
        self.assertTrue(self.matches(block(decision, "visible"), facts))
        settle = self.effects["NAM_pw_regional_contracts_settle"]
        paid = ("NAM", "has_country_flag", "NAM_pw_regional_contracts_paid")
        for local, has_paid in product((False, True), repeat=2):
            result = list(selected_effects(self.expand(settle), {**facts, domestic: local, paid: has_paid}, "NAM"))
            sites = [e.value for scope, e in result if scope == "NAM" and e.key == "random_owned_controlled_state"]
            self.assertEqual(len(sites), int(local and has_paid))
            if sites:
                site = sites[0]
                for district, infrastructure, factory_slot, expected in (
                    ("720", 4, False, "infrastructure"), ("720", 5, True, "industrial_complex"),
                    ("720", 5, False, None), ("700", 4, True, None),
                ):
                    land = {(district, "numeric", "infrastructure"): infrastructure,
                            (district, "variable", "fixture_building_slots_industrial_complex_no"): int(factory_slot)}
                    gate = block(site, "limit")
                    self.assertEqual(matches_conditions(gate, land, district), expected is not None)
                    if expected:
                        selected = selected_effects([e for e in site if e.key != "limit"], land, district)
                        built = [(s, scalar(e.value, "type"), scalar(e.value, "level")) for s, e in selected
                                 if e.key == "add_building_construction"]
                        self.assertEqual(built, [(district, expected, "1")])

    def test_veyran_invasion_respects_reunification_and_previous_peace_terms(self):
        west = parsed("common/scripted_triggers/ADISCORD_west_final_war_triggers.txt")
        invasion = self.postwar["NAM_veyran_invasion"]
        start = block(self.effects["NAM_veyran_start_invasion"], "if")
        reward = block(invasion, "completion_reward")
        self.assertEqual(scalar(block(reward, "hidden_effect"), "NAM_veyran_start_invasion"), "yes")
        with patch.dict(self.triggers, {e.key: e.value for e in west}):
            for (route, nation), guard in product(
                    VORKERLAND_UNIFIERS, (block(invasion, "available"), block(start, "limit"))):
                facts = {
                    **self.veyran_facts(),
                    ("event_target", VORKERLAND): nation,
                    ("NAM", "has_completed_focus", "NAM_veyran_union_charter"): True,
                    ("NAM", "has_war", "no"): True,
                    ("NAM", "has_global_flag", "ADISCORD_vorkerland_collapse_finished"): True,
                    ("NAM", "has_global_flag", "ADISCORD_vorkerland_reunification_verified"): True,
                    (nation, "exists", "yes"): True,
                    (nation, "has_country_flag", "ADISCORD_vorkerland_central_unifier"): True,
                    (nation, "has_country_flag", "ADISCORD_vorkerland_route_" + route): True,
                    (nation, "is_subject", "no"): True,
                    (nation, "has_capitulated", "no"): True,
                    (nation, "has_war", "no"): True,
                    (nation, "owns_state", "32"): True,
                    (nation, "controls_state", "32"): True,
                }
                self.assertTrue(self.matches(guard, facts), route)
                for field, rejected in (
                    (("NAM", "has_completed_focus", "NAM_veyran_union_charter"), False),
                    (("NAM", "has_global_flag", "ADISCORD_vorkerland_reunification_verified"), False),
                    ((nation, "has_country_flag", "ADISCORD_vorkerland_central_unifier"), False),
                    ((nation, "is_subject", "no"), False),
                    ((nation, "owns_state", "32"), False),
                    ((nation, "controls_state", "32"), False),
                    (("NAM", "has_global_flag", "ADISCORD_west_final_started"), True),
                    ((nation, "has_variable", "ADISCORD_west_side"), True),
                    ((nation, "has_country_flag", "ADISCORD_vorkerland_pw_settlement_scheduled"), True),
                    (("NAM", "has_variable", "ADISCORD_south_side"), True),
                    (("NAM", "is_in_faction_with", nation), True),
                    (("NAM", "has_variable", "NAM_veyran_campaign"), True),
                    (("NAM", "country_exists", "SNG"), True),
                    # The order is given against the holder of the country target only.
                    (("event_target", VORKERLAND), "WRK"),
                ):
                    self.assertFalse(self.matches(guard, {**facts, field: rejected}), (route, field))
                concluded = {**facts, ("NAM", "has_global_flag", "ADISCORD_west_final_started"): True,
                             ("NAM", "has_global_flag", "ADISCORD_west_final_resolved"): True}
                self.assertTrue(self.matches(guard, concluded))

    def test_veyran_treaty_uses_two_ownership_snapshots_and_transfers_both_titles(self):
        start = block(self.effects["NAM_veyran_start_invasion"], "if")
        owned = block(start, "every_owned_state")
        self.assertEqual([e.key for e in owned], ["add_to_array"])
        homeland = scalar(block(owned, "add_to_array"), "array")
        self.assertEqual(scalar(block(owned, "add_to_array"), "value"), "THIS")
        self.assertTrue(homeland.startswith("global."))
        self.assertLess([e.key for e in start].index("every_owned_state"), [e.key for e in start].index("declare_war_on"))
        # The war, the land record and the annexation all address the unified country.
        self.assertEqual(scalar(block(start, "declare_war_on"), "target"), VORKERLAND_SCOPE)

        win = block(self.effects["NAM_veyran_settle_victory"], "if")
        order = [e.key for e in win]
        self.assertLess(order.index("set_variable"), order.index("white_peace"))
        self.assertLess(order.index(VORKERLAND_SCOPE), order.index("annex_country"))
        self.assertEqual(scalar(win, "white_peace"), VORKERLAND_SCOPE)
        enemy_land = block(block(win, VORKERLAND_SCOPE), "every_owned_state")
        self.assertEqual([e.key for e in enemy_land], ["add_to_temp_array"])
        record = block(enemy_land, "add_to_temp_array")
        self.assertEqual(scalar(record, "value"), "THIS")
        self.assertEqual(scalar(block(win, "annex_country"), "target"), VORKERLAND_SCOPE)
        self.assertFalse({"WRK", "WKR", "VAD", "TVA"} & {e.key for e in walk(start + win)})
        assignments = {scalar(e.value, "array"): e.value for e in win if e.key == "for_each_scope_loop"}
        captured = assignments[scalar(record, "array")]
        residual = block(captured, "if")
        for owner in ("WKR", "VAD", "TVA", "NAM"):
            self.assertEqual(self.matches(block(residual, "limit"), {("999", "is_owned_by", owner): True}, "999"),
                             owner != "NAM")
        self.assertEqual(scalar(block(residual, "NAM"), "transfer_state"), "PREV")
        self.assertEqual(scalar(captured, "set_state_controller_to"), "NAM")
        self.assertEqual(scalar(block(win, "set_capital"), "state"), "32")
        self.assertEqual(scalar(win, "set_cosmetic_tag"), "NAM_veyran_union")
        homeland_position = next(i for i, e in enumerate(win) if e.value == assignments[homeland])
        self.assertLess(order.index("set_capital"), homeland_position)
        governorate = assignments[homeland]
        self.assertEqual(scalar(governorate, "add_core_of"), "SNG")
        self.assertEqual(scalar(block(governorate, "SNG"), "transfer_state"), "PREV")
        self.assertEqual(scalar(governorate, "set_state_controller_to"), "SNG")
        self.assertEqual(scalar(block(win, "puppet"), "target"), "SNG")
        autonomy = block(win, "set_autonomy")
        self.assertEqual((scalar(autonomy, "target"), scalar(autonomy, "autonomy_state")),
                         ("SNG", "autonomy_NAM_imperial_governorate"))
        defeat = block(self.effects["NAM_veyran_settle_defeat"], "if")
        for outcome in (win, defeat):
            self.assertEqual(scalar(outcome, "clear_array"), homeland)
            gate = block(outcome, "limit")
            for stage in (0, 1, 2):
                self.assertEqual(self.matches(gate, {("NAM", "variable", "NAM_veyran_campaign"): stage}), stage == 1)
            self.assertEqual(scalar(block(outcome, "set_variable"), "value"), "2")
            self.assertFalse({"change_tag_from", "change_tag_from_and_set_country_leader",
                              "set_country_leader", "promote_character"} & {e.key for e in walk(outcome)})
        self.assertFalse({"annex_country", "puppet", "set_autonomy", "transfer_state"} & {e.key for e in walk(defeat)})

    def test_veyran_capitulation_only_credits_the_two_sides_and_never_repeats(self):
        def bind(entries, loser, victor):
            scopes = {"ROOT": loser, "FROM": victor}
            return [replace(e, key=scopes.get(e.key, e.key), value=bind(e.value, loser, victor)
                            if isinstance(e.value, list) else scopes.get(e.value, e.value)) for e in entries]

        hooks = block(parsed("common/on_actions/09_ADISCORD_scripted_peace_on_actions.txt"), "on_actions")
        for hook in ("on_capitulation_immediate", "on_capitulation"):
            self.assertEqual(sum(e.key == "NAM_veyran_handle_capitulation" for e in walk(block(hooks, hook))), 1)
        for hook in ("on_peace", "on_annex", "on_puppet"):
            self.assertEqual(sum(e.key == "NAM_veyran_close_external" for e in walk(block(hooks, hook))), 1)

        dispatch = self.expand(self.effects["NAM_veyran_handle_capitulation"])
        external = self.effects["NAM_veyran_close_external"]
        for _, nation in VORKERLAND_UNIFIERS:
            unified = {("event_target", VORKERLAND): nation}
            for loser, champion, result in ((nation, "NAM", "victory"), ("NAM", nation, "defeat")):
                for victor, same_side in ((champion, True), ("EFL", True), ("IVN", False)):
                    entries = bind(dispatch, loser, victor)
                    for stage in (1, 2):
                        facts = {
                            **unified,
                            ("NAM", "variable", "NAM_veyran_campaign"): stage,
                            ("NAM", "has_war_with", nation): True,
                            (victor, "has_war_with", loser): True,
                            (victor, "has_war_together_with", champion): same_side,
                            (champion, "exists", "yes"): True,
                            (champion, "is_subject", "no"): True,
                            (champion, "has_capitulated", "no"): True,
                            ("32", "is_owned_by", nation): True,
                        }
                        calls = [(scope, e.key) for scope, e in selected_effects(entries, facts, loser)
                                 if e.key.startswith("NAM_veyran_settle_")]
                        self.assertEqual(calls, [("NAM", "NAM_veyran_settle_" + result)]
                                         if stage == 1 and same_side else [], (loser, victor, stage))
            # A capitulating tag that is not the country target cannot hand NAM the victory.
            for bystander in {"WRK", "WKR", "VAD", "TVA"} - {nation}:
                facts = {
                    **unified,
                    ("NAM", "variable", "NAM_veyran_campaign"): 1,
                    ("NAM", "has_war_with", nation): True,
                    ("NAM", "has_war_with", bystander): True,
                    ("NAM", "exists", "yes"): True,
                    ("NAM", "is_subject", "no"): True,
                    ("NAM", "has_capitulated", "no"): True,
                    ("32", "is_owned_by", nation): True,
                }
                calls = [e.key for _, e in selected_effects(bind(dispatch, bystander, "NAM"), facts, bystander)
                         if e.key.startswith("NAM_veyran_settle_")]
                self.assertEqual(calls, [], (nation, bystander))
            at_war = {**unified, ("NAM", "variable", "NAM_veyran_campaign"): 1,
                      ("NAM", "country_exists", "NAM"): True,
                      (nation, "exists", "yes"): True, ("NAM", "has_war_with", nation): True}
            for change in ({}, {("NAM", "is_subject", "yes"): True}, {(nation, "is_subject", "yes"): True},
                           {("NAM", "has_war_with", nation): False}, {(nation, "exists", "yes"): False}):
                calls = [e.key for _, e in selected_effects(self.expand(external), {**at_war, **change}, "NAM")]
                self.assertEqual(calls, ["NAM_veyran_settle_defeat"] if change else [], change)

    def test_veyran_transfer_keeps_noncore_acquisitions_and_only_releases_the_original_homeland(self):
        from tools.tests.test_adiscord_rus_last_empire import RusCrisisFixture

        for _, nation in VORKERLAND_UNIFIERS:
            with self.subTest(nation=nation):
                world = RusCrisisFixture()
                world.countries.update({"SNG", "EFL", nation})
                # The claimant that unified Vorkerland holds the country target and its
                # land; the pre-collapse tag owns nothing.
                world.targets[VORKERLAND_SCOPE] = nation
                world.owners = {"700": "NAM", "719": "NAM", "32": nation, "330": nation, "90": "IVN", "690": "EFL"}
                world.controllers = dict(world.owners)
                world.controllers["690"] = "NAM"
                world.cores = {"700": {"NAM"}, "719": {"SLF"}, "32": {nation}, "330": {"IVN"},
                               "90": {nation}, "690": {"EFL"}}
                world.subjects = {"EFL": "NAM"}
                world.wars = set()
                world.peace_mode = "pair"
                world.rulers = {"NAM": "NAM_Egor_Rom"}
                world.effects.update({k: v for k, v in self.effects.items() if k.startswith("NAM_veyran_")})
                world.triggers["NAM_veyran_invasion_active"] = self.triggers["NAM_veyran_invasion_active"]
                # Start at the accepted invasion order. Entry and callbacks use separate native-trigger scenarios.
                order = block(world.effects["NAM_veyran_start_invasion"], "if")
                world.execute([e for e in order if e.key != "limit"], ["NAM"])
                self.assertEqual(world.declarations, [("NAM", nation)])
                self.assertCountEqual(world.arrays["global.NAM_veyran_homeland"], ["700", "719"])

                # Both sides gain one new possession, and Vorkerland occupies part of the old homeland.
                world.owners["95"] = nation
                world.owners["720"] = "NAM"
                world.controllers.update({"95": nation, "720": "NAM", "719": nation})
                for _ in range(2):
                    world.run("NAM_veyran_settle_victory", "NAM")
                    world.run("NAM_veyran_settle_defeat", "NAM")
                self.assertEqual(world.annexed, [("NAM", nation)])
                self.assertEqual(world.owners, {"700": "SNG", "719": "SNG", "32": "NAM", "330": "NAM",
                                                "90": "IVN", "690": "EFL", "95": "NAM", "720": "NAM"})
                for state in ("700", "719", "32", "330", "95"):
                    self.assertEqual(world.controllers[state], world.owners[state], state)
                self.assertEqual(world.subjects, {"EFL": "NAM", "SNG": "NAM"})
                self.assertEqual(world.autonomy["SNG"], "autonomy_NAM_imperial_governorate")
                self.assertEqual(scalar(world.country_settings["NAM", "set_capital"], "state"), "32")
                self.assertEqual(scalar(world.country_settings["SNG", "set_capital"], "state"), "700")
                self.assertEqual(world.cosmetic_tags["NAM"], "NAM_veyran_union")
                self.assertEqual(world.rulers["NAM"], "NAM_Egor_Rom")
                self.assertEqual(world.player_handoffs, [])
                self.assertEqual(world.arrays["global.NAM_veyran_homeland"], [])

    def test_khan_branch_follows_southern_victory_and_heritage(self):
        names = ("NAM_rus_crisis_watch", "NAM_rus_fuel_for_coalition",
                 "NAM_rus_demand_share", "NAM_rus_expedition_staff")
        root = self.postwar[names[0]]
        self.assertEqual([e.value for e in block(root, "prerequisite")], ["NAM_south_heritage"])
        heritage = self.postwar["NAM_south_heritage"]
        self.assertGreater(int(scalar(root, "x")), int(scalar(heritage, "x")))
        self.assertEqual(int(scalar(root, "y")), int(scalar(heritage, "y")) + 1)
        for resolved, nam_won in ((False, False), (True, False), (False, True), (True, True)):
            facts = self.postwar_facts()
            facts[("NAM", "has_global_flag", "ADISCORD_south_final_resolved")] = resolved
            facts[("NAM", "has_global_flag", "ADISCORD_south_hegemon_NAM")] = nam_won
            facts[("RUS", "RUS_crisis_project_active", "yes")] = True
            for name in names:
                focus = self.postwar[name]
                self.assertEqual(self.matches(block(focus, "allow_branch"), facts), resolved and nam_won, name)
                if not (resolved and nam_won):
                    self.assertFalse(self.matches(block(focus, "available"), facts), name)
            self.assertEqual(self.matches(block(root, "available"), facts), resolved and nam_won)
        facts[("RUS", "RUS_crisis_project_active", "yes")] = False
        self.assertFalse(self.matches(block(root, "available"), facts))
        outcomes = parsed("common/scripted_effects/ADISCORD_south_final_war_effects.txt")
        victory = block(outcomes, "ADISCORD_south_final_resolve_north_victory")
        self.assertTrue(any(e.key == "mark_focus_tree_layout_dirty" for e in walk(victory)))

    def northern_facts(self, focus=None, recipients=("FROM",)):
        facts = self.postwar_facts()
        facts[("fixture", "fuel_logistics")] = True
        facts[("NAM", "numeric", "has_fuel")] = 30000
        facts[("NAM", "equipment", "motorized_equipment")] = 100
        facts[("NAM", "equipment", "infantry_equipment")] = 1000
        facts[("NAM", "has_global_flag", "ADISCORD_south_final_resolved")] = True
        facts[("NAM", "has_global_flag", "ADISCORD_south_hegemon_NAM")] = True
        facts[("NAM", "is_subject", "no")] = True
        facts[("RUS", "variable", "RUS_crisis_phase")] = 2
        facts[("RUS", "RUS_crisis_project_active", "yes")] = True
        for name in ("NAM_rus_crisis_watch", "NAM_rus_fuel_for_coalition", "NAM_rus_demand_share",
                     "NAM_rus_expedition_staff"):
            facts[("NAM", "has_completed_focus", name)] = name == focus or (bool(focus) and name == "NAM_rus_crisis_watch")
        facts[("global", "array", "RUS_crisis_defenders")] = recipients
        for tag in recipients:
            facts[(tag, "exists", "yes")] = True
            facts[(tag, "has_capitulated", "no")] = True
            facts[(tag, "has_country_flag", "RUS_crisis_defender")] = True
            facts[(tag, "has_war_with", "RUS")] = True
            facts[(tag, "fuel_capacity")] = 80000
            facts[(tag, "numeric", "has_fuel")] = 50000
            facts[(tag, "equipment", "motorized_equipment")] = 100
            facts[(tag, "equipment", "infantry_equipment")] = 0
        return facts

    @staticmethod
    def northern_stocks(facts, recipient="FROM"):
        return tuple(facts.get((tag, kind, name), 0) for tag in ("NAM", recipient)
                     for kind, name in (("numeric", "has_fuel"), ("equipment", "motorized_equipment"),
                                        ("equipment", "infantry_equipment")))

    def northern_decision_ready(self, decision, facts):
        return all(self.matches(entry.value, facts) for entry in decision
                   if entry.key in ("target_trigger", "visible", "available", "custom_cost_trigger"))

    def test_northern_preparation_opens_trade_and_freight_before_coalition_entry(self):
        watch, relief, barter, staff = ("NAM_rus_crisis_watch", "NAM_rus_fuel_for_coalition",
                                        "NAM_rus_demand_share", "NAM_rus_expedition_staff")
        for policy, other in ((relief, barter), (barter, relief)):
            self.assertEqual(scalar(block(self.postwar[policy], "prerequisite"), "focus"), watch)
            self.assertEqual(scalar(block(self.postwar[policy], "mutually_exclusive"), "focus"), other)
        self.assertEqual([[e.value for e in entry.value] for entry in self.postwar[staff]
                          if entry.key == "prerequisite"], [[relief, barter]])

        export = self.bind_field(self.decisions["NAM_oil_contract_offer"], "EFL")
        charter = self.decisions["NAM_pw_barter_charter"]
        prior_export = ("NAM_supports_export_houses", "NAM_contract_bureau",
                        "NAM_defeat_oil_union", "NAM_normalisation")
        prior_freight = ("NAM_warehouse_receipts", "NAM_commercial_reserve")
        starts = ((-0.5, None, None), (0, None, None), (0.5, None, None),
                  (0, "NAM_contract_bureau", "NAM_commercial_reserve"),
                  (0.5, "NAM_normalisation", "NAM_warehouse_receipts"))
        for balance, old_export, old_freight in starts:
            facts = self.northern_facts(recipients=())
            facts[("RUS", "variable", "RUS_crisis_phase")] = 1
            facts[("NAM", "has_variable", "NAM_prewar_balance")] = True
            facts[("NAM", "variable", "NAM_prewar_balance")] = balance
            facts[("NAM", "numeric", "has_fuel")] = 60000
            facts[("NAM", "variable", "NAM_oil_free_land_units")] = 2
            facts[("NAM", "variable", "NAM_oil_free_units")] = 2
            for name in (*prior_export, *prior_freight):
                facts[("NAM", "has_completed_focus", name)] = name in (old_export, old_freight)
            facts[("EFL", "tag", "EFL")] = True
            facts[("EFL", "exists", "yes")] = True
            facts[("EFL", "has_capitulated", "no")] = True
            for name in (watch, relief, barter, staff):
                self.assertTrue(self.matches(block(self.postwar[name], "available"), facts), (balance, name))
            self.assertEqual(self.matches(block(export, "visible"), facts), bool(old_export))
            self.assertEqual(self.matches(block(charter, "visible"), facts), bool(old_freight))

            def shown(name):
                reward = block(self.postwar[name], "completion_reward")
                return [e.value for _, e in selected_effects(self.expand(reward), FuelLogistics(facts), "NAM")
                        if e.key == "unlock_decision_tooltip"]

            self.assertEqual(shown(watch), [] if old_export else ["NAM_oil_contract_offer"])
            self.assertEqual(shown(relief), ["NAM_rus_send_relief"])
            self.assertEqual(shown(barter), ["NAM_rus_offer_barter"])
            self.assertEqual(shown(staff), ["NAM_rus_send_column"] + ([] if old_freight else ["NAM_pw_barter_charter"]))
            capacity = ("NAM", "variable", "NAM_oil_throughput")
            facts[("NAM", "variable", "NAM_oil_bonus_units")] = 2
            with patch.dict(self.effects, {"NAM_field_update_units": []}):
                self.apply(self.effects["NAM_oil_refresh"], facts)
                before = facts[capacity]
                self.apply(block(self.postwar[watch], "completion_reward"), facts)
            self.assertEqual(facts[capacity], before + 1)
            facts[("NAM", "has_completed_focus", watch)] = True
            self.assertTrue(self.matches(block(export, "visible"), facts))
            self.assertTrue(self.matches(block(export, "available"), facts))
            facts[("NAM", "has_completed_focus", staff)] = True
            self.assertTrue(self.northern_decision_ready(charter, facts))

    def test_northern_relief_rechecks_both_stocks_and_the_real_front(self):
        decision = self.decisions["NAM_rus_send_relief"]
        self.assertEqual(scalar(decision, "target_array"), "global.RUS_crisis_defenders")
        complete = block(decision, "complete_effect")
        valid = self.northern_facts("NAM_rus_fuel_for_coalition")
        valid[("KDR", "has_country_flag", "RUS_crisis_defender")] = True
        self.assertTrue(self.northern_decision_ready(decision, valid))
        for key, value in (
            (("NAM", "numeric", "has_fuel"), 29999.99),
            (("FROM", "numeric", "has_fuel"), 50000.01),
            (("RUS", "variable", "RUS_crisis_phase"), 1),
            (("RUS", "variable", "RUS_crisis_phase"), 3),
            (("RUS", "RUS_crisis_project_active", "yes"), False),
            (("FROM", "has_war_with", "RUS"), False),
            (("FROM", "has_war_with", "NAM"), True),
            (("FROM", "is_subject_of", "RUS"), True),
            (("FROM", "is_in_faction_with", "RUS"), True),
            (("global", "array", "RUS_crisis_defenders"), ()),
            (("FROM", "has_country_flag", "RUS_crisis_defender"), False),
            (("FROM", "has_country_flag", "RUS_crisis_entry_pending"), True),
            (("FROM", "exists", "yes"), False),
            (("FROM", "has_capitulated", "no"), False),
            (("NAM", "is_in_faction_with", "RUS"), True),
            (("NAM", "has_war_with", "KDR"), True),
            (("FROM", "has_country_flag", "NAM_rus_received_fuel"), True),
        ):
            with self.subTest(key=key, value=value):
                facts = {**valid, key: value}
                self.assertFalse(self.northern_decision_ready(decision, facts))
                stocks = self.northern_stocks(facts)
                self.apply(complete, facts)
                self.assertEqual(self.northern_stocks(facts), stocks)
        self.apply(complete, valid)
        self.assertEqual(self.northern_stocks(valid), (0, 100, 1000, 80000, 100, 0))
        self.assertEqual(valid[("FROM", "flag_duration", "NAM_rus_received_fuel")], 45)
        valid[("NAM", "numeric", "has_fuel")] = 30000
        valid[("FROM", "numeric", "has_fuel")] = 0
        self.apply(complete, valid)
        self.assertEqual(self.northern_stocks(valid), (30000, 100, 1000, 0, 100, 0))

    def test_northern_column_moves_only_existing_equipment_independently_of_fuel(self):
        decision = self.decisions["NAM_rus_send_column"]
        self.assertEqual(scalar(decision, "target_array"), "global.RUS_crisis_defenders")
        complete = block(decision, "complete_effect")
        valid = self.northern_facts("NAM_rus_expedition_staff")
        valid[("NAM", "numeric", "has_fuel")] = 0
        valid[("FROM", "has_country_flag", "NAM_rus_received_fuel")] = True
        valid[("FROM", "numeric", "has_fuel")] = valid[("FROM", "fuel_capacity")]
        for missing, value in ((("NAM", "equipment", "motorized_equipment"), 99.99),
                               (("NAM", "equipment", "infantry_equipment"), 999.99),
                               (("FROM", "has_war_with", "RUS"), False)):
            facts = {**valid, missing: value}
            self.assertFalse(self.northern_decision_ready(decision, facts))
            stocks = self.northern_stocks(facts)
            self.apply(complete, facts)
            self.assertEqual(self.northern_stocks(facts), stocks)
        self.assertTrue(self.northern_decision_ready(decision, valid))
        self.apply(complete, valid)
        self.assertEqual(self.northern_stocks(valid), (0, 0, 0, 80000, 200, 1000))
        valid[("NAM", "equipment", "motorized_equipment")] = 100
        valid[("NAM", "equipment", "infantry_equipment")] = 1000
        stocks = self.northern_stocks(valid)
        self.assertFalse(self.northern_decision_ready(decision, valid))
        self.apply(complete, valid)
        self.assertEqual(self.northern_stocks(valid), stocks)
        self.assertEqual(valid[("FROM", "flag_duration", "NAM_rus_received_column")], 45)
        facts = self.northern_facts("NAM_rus_expedition_staff", ("VAL", "NOD"))
        facts[("NAM", "equipment", "motorized_equipment")] = 200
        facts[("NAM", "equipment", "infantry_equipment")] = 2000
        for recipient in ("VAL", "NOD"):
            facts[("fixture", "FROM")] = recipient
            target = self.bind_field(decision, recipient)
            self.assertTrue(self.northern_decision_ready(target, facts))
            self.apply(block(target, "complete_effect"), facts)
            self.assertEqual(facts[(recipient, "equipment", "motorized_equipment")], 200)
            self.assertEqual(facts[(recipient, "equipment", "infantry_equipment")], 1000)
            self.assertEqual(facts[(recipient, "flag_duration", "NAM_rus_received_column")], 45)
        self.assertEqual(self.northern_stocks(facts, "VAL")[:3], (30000, 0, 0))

    def test_northern_barter_waits_for_each_buyer_and_closes_stale_offers(self):
        decision = self.decisions["NAM_rus_offer_barter"]
        self.assertEqual(scalar(decision, "target_array"), "global.RUS_crisis_defenders")
        offer = block(decision, "complete_effect")
        event_id = "ADISCORD_nam_oil.11"
        options = [e.value for e in self.events[event_id] if e.key == "option"]
        refuse, accept, close = options
        pending = ("FROM", "has_country_flag", "NAM_rus_barter_pending")
        declined = ("FROM", "has_country_flag", "NAM_rus_barter_declined")
        sent = ("FROM", "scheduled_event", event_id)
        valid = self.northern_facts("NAM_rus_demand_share")
        opening = self.northern_stocks(valid)
        self.assertTrue(self.northern_decision_ready(decision, valid))
        self.apply(offer, valid)
        self.assertTrue(valid[pending])
        self.assertFalse(self.northern_decision_ready(decision, valid))
        self.apply(offer, valid)
        self.assertEqual(valid[sent], 1)
        self.assertEqual(self.northern_stocks(valid), opening)

        def visible(facts):
            return [option for option in options if self.matches(block(option, "trigger"), facts, "FROM")]

        self.assertEqual(visible(valid), [refuse, accept])
        # Native timeout selects the first available option.
        timed_out = dict(valid)
        self.apply(visible(timed_out)[0], timed_out, "FROM")
        self.assertFalse(timed_out[pending])
        self.assertTrue(timed_out[declined])
        self.assertEqual(self.northern_stocks(timed_out), opening)
        self.assertFalse(self.northern_decision_ready(decision, timed_out))
        self.apply(accept, timed_out, "FROM")
        self.assertEqual(self.northern_stocks(timed_out), opening)

        for key, changed in ((("FROM", "equipment", "motorized_equipment"), 99.99),
                             (("NAM", "numeric", "has_fuel"), 29999.99),
                             (("FROM", "numeric", "has_fuel"), 50000.01),
                             (("RUS", "variable", "RUS_crisis_phase"), 3),
                             (("global", "array", "RUS_crisis_defenders"), ()),
                             (("FROM", "has_war_with", "RUS"), False),
                             (("NAM", "has_completed_focus", "NAM_rus_demand_share"), False)):
            with self.subTest(changed=key):
                stale = {**valid, key: changed}
                before = self.northern_stocks(stale)
                self.assertEqual(visible(stale), [close])
                self.apply(accept, stale, "FROM")
                self.assertEqual(self.northern_stocks(stale), before)
                self.apply(close, stale, "FROM")
                self.assertFalse(stale[pending])
                self.assertFalse(stale.get(declined))
                stale[key] = valid[key]
                self.assertTrue(self.northern_decision_ready(decision, stale))
                self.apply(offer, stale)
                self.assertEqual(stale[sent], 2)

        self.apply(accept, valid, "FROM")
        self.assertEqual(self.northern_stocks(valid), (0, 200, 1000, 80000, 0, 0))
        self.assertFalse(valid[pending])
        self.assertFalse(valid.get(declined))
        self.assertEqual(valid[("FROM", "flag_duration", "NAM_rus_received_fuel")], 45)
        self.assertEqual(visible(valid), [close])
        self.apply(accept, valid, "FROM")
        self.assertEqual(self.northern_stocks(valid), (0, 200, 1000, 80000, 0, 0))

    def test_two_northern_buyers_cannot_spend_the_same_fuel(self):
        decision = self.decisions["NAM_rus_offer_barter"]
        options = [e.value for e in self.events["ADISCORD_nam_oil.11"] if e.key == "option"]
        facts = self.northern_facts("NAM_rus_demand_share", ("VAL", "NOD"))
        for buyer in ("VAL", "NOD"):
            offer = self.bind_field(block(decision, "complete_effect"), buyer)
            self.apply(offer, facts)
            self.assertTrue(facts[(buyer, "has_country_flag", "NAM_rus_barter_pending")])
        self.apply(options[1], facts, "VAL")
        self.assertEqual(self.northern_stocks(facts, "VAL"), (0, 200, 1000, 80000, 0, 0))
        self.assertFalse(self.matches(block(options[1], "trigger"), facts, "NOD"))
        self.assertTrue(self.matches(block(options[2], "trigger"), facts, "NOD"))
        self.apply(options[1], facts, "NOD")
        self.apply(options[2], facts, "NOD")
        self.assertEqual(self.northern_stocks(facts, "NOD"), (0, 200, 1000, 50000, 100, 0))

    def test_northern_emergency_offer_survives_a_failed_dispatch_and_rechecks_each_recipient(self):
        event_id = "ADISCORD_nam_oil.10"
        event = self.events[event_id]
        options = {scalar(e.value, "name"): e.value for e in event if e.key == "option"}
        monthly = self.effects["NAM_rus_coalition_check"]
        offered = ("NAM", "has_country_flag", "NAM_rus_oil_offered")
        roster = ("global", "array", "RUS_crisis_defenders")
        facts = self.northern_facts(recipients=("EFL", "AZH", "KDR"))
        facts[roster] = (*facts[roster], "NAM")
        facts[("NAM", "has_country_flag", "RUS_crisis_defender")] = True
        facts[("NAM", "has_war_with", "RUS")] = True
        facts[("NAM", "has_completed_focus", "NAM_contract_bureau")] = True

        def enabled(state):
            return {name.removeprefix(event_id + ".") for name, option in options.items()
                    if self.matches(block(option, "trigger"), state)}

        self.apply(monthly, facts)
        self.assertEqual(facts[("NAM", "scheduled_event", event_id)], 1)
        self.assertFalse(facts.get(offered))
        for key, value in ((roster, ("NAM",)), (roster, ("EFL",)), (("RUS", "variable", "RUS_crisis_phase"), 3),
                           (("NAM", "has_country_flag", "RUS_crisis_entry_pending"), True),
                           (("NAM", "has_completed_focus", "NAM_rus_crisis_watch"), True)):
            withdrawn = {**facts, key: value}
            self.assertFalse(self.matches(block(event, "trigger"), withdrawn))
            self.assertEqual(enabled(withdrawn), {"close"})
            self.apply(options[event_id + ".close"], withdrawn)
            self.assertFalse(withdrawn.get(offered))
        self.apply(monthly, facts)
        self.assertEqual(facts[("NAM", "scheduled_event", event_id)], 2)
        self.assertTrue(self.matches(block(event, "trigger"), facts))
        self.apply(block(event, "immediate"), facts)
        self.assertTrue(facts[offered])
        self.apply(monthly, facts)
        self.assertEqual(facts[("NAM", "scheduled_event", event_id)], 2)
        self.assertEqual(enabled(facts), {"a", "b", "c"})
        facts[("EFL", "numeric", "has_fuel")] += 0.01
        facts[("KDR", "has_war_with", "RUS")] = False
        self.apply(options[event_id + ".b"], facts)
        self.assertAlmostEqual(facts[("EFL", "numeric", "has_fuel")], 50000.01)
        self.assertEqual(facts[("KDR", "numeric", "has_fuel")], 50000)
        self.assertEqual(facts[("AZH", "numeric", "has_fuel")], 80000)
        self.assertEqual(facts[("AZH", "flag_duration", "NAM_rus_received_fuel")], 45)
        self.assertEqual(facts[("NAM", "numeric", "has_fuel")], 0)
        self.assertFalse(facts.get(("NAM", "has_country_flag", "NAM_rus_received_fuel")))
        self.assertNotIn("b", enabled(facts))
        facts[("EFL", "has_country_flag", "NAM_oil_offer_declined")] = True
        facts[("AZH", "has_country_flag", "NAM_oil_offer_pending")] = True
        self.assertEqual(enabled(facts), {"a"})
        facts[("NAM", "has_completed_focus", "NAM_rus_crisis_watch")] = True
        self.assertEqual(enabled(facts), {"close"})

    def test_postwar_development_previews_equal_aggregate_deltas(self):
        dynamic = block(parsed("common/dynamic_modifiers/ADISCORD_dynamic_modifiers_NAM.txt"),
                        "NAM_administration_dynamic")
        modifiers = {e.value: e.key for e in dynamic if isinstance(e.value, str)
                     and e.value.startswith("NAM_adm_")}
        ideas = block(block(parsed("common/ideas/ADISCORD_nam_resource_war_ideas.txt"), "ideas"), "country")
        verified = 0
        for name, focus in self.postwar.items():
            if not any(e.key == "allow_branch" for e in focus):
                continue
            reward = block(focus, "completion_reward")
            preview = [e.value for e in walk(reward) if e.key == "add_idea"
                       and e.value == "NAM_adm_" + name.removeprefix("NAM_") + "_idea"]
            if not preview:
                continue
            delta = {modifiers[scalar(e.value, "var")]: float(scalar(e.value, "value"))
                     for e in walk(reward) if e.key == "add_to_variable"
                     and scalar(e.value, "var") in modifiers}
            shown = {e.key: float(e.value) for e in block(block(ideas, preview[0]), "modifier")}
            self.assertEqual(delta, shown, name)
            self.assertTrue(any(e.key == "NAM_refresh_administration" for e in walk(reward)), name)
            verified += 1
        self.assertGreaterEqual(verified, 16)

    def test_completed_waterworks_share_paid_repairs_between_held_operating_fields(self):
        focus = self.postwar["NAM_water_boards"]
        self.assertFalse(any(entry.key == "bypass" for entry in focus))
        for field, neighbour in (("67", "690"), ("690", "67")):
            for scorched in (False, True):
                facts = self.postwar_facts()
                facts[(field, "state", field)] = True
                facts[(neighbour, "has_state_flag", "NAM_wells_scorched")] = scorched
                facts[(field, "numeric", "infrastructure")] = 5
                facts[(neighbour, "numeric", "infrastructure")] = 5
                with patch.dict(self.effects, {"NAM_oil_refresh": []}):
                    self.apply(block(focus, "completion_reward"), facts)
                    self.assertEqual(facts[(field, "variable", "NAM_field_condition")], 95)
                    self.assertEqual(facts[(neighbour, "variable", "NAM_field_condition")], 80 if scorched else 95)
                    facts[(field, "has_state_flag", "NAM_project_in_progress")] = True
                    facts[(field, "variable", "NAM_project_deposit")] = 150
                    facts[(field, "variable", "NAM_field_condition")] = 55
                    facts[(neighbour, "variable", "NAM_field_condition")] = 55
                    for _ in range(2):
                        self.apply(self.effects["NAM_project_complete_repair"], facts, field)
                    self.assertEqual(facts[(neighbour, "variable", "NAM_field_condition")], 55 if scorched else 70)

    def postwar_focus_position(self, focus, facts):
        x, y = int(scalar(focus, "x")), int(scalar(focus, "y"))
        anchor = next((e.value for e in focus if e.key == "relative_position_id"), None)
        if anchor:
            ax, ay = self.postwar_focus_position(self.postwar[anchor], facts)
            x += ax
            y += ay
        for offset in (e.value for e in focus if e.key == "offset"):
            if self.matches(block(offset, "trigger"), facts):
                x += int(next((e.value for e in offset if e.key == "x"), 0))
                y += int(next((e.value for e in offset if e.key == "y"), 0))
        return x, y

    def test_postwar_mandates_hide_other_courses_and_center_visible_nodes(self):
        routes = {"service": -0.5, "pragmatic": 0, "district": 0.5}
        roots = {"service": "NAM_service_state", "pragmatic": "NAM_pragmatic_compact",
                 "district": "NAM_federal_charter"}
        membership = {}
        for name, focus in self.postwar.items():
            gates = [e.value for e in focus if e.key == "allow_branch"]
            for route in routes:
                if gates and any(e.key == "NAM_prewar_" + route + "_mandate" for e in gates[0]):
                    membership[name] = route
        self.assertEqual(Counter(membership.values()), {"service": 77, "district": 34, "pragmatic": 34})
        for balance, course in ((-0.5, "service"), (-0.25, "pragmatic"),
                                (0, "pragmatic"), (0.25, "pragmatic"), (0.5, "district")):
            facts = self.postwar_facts()
            facts[("NAM", "has_variable", "NAM_prewar_balance")] = True
            facts[("NAM", "variable", "NAM_prewar_balance")] = balance
            facts[("NAM", "owns_state", "723")] = True
            facts[("NAM", "has_global_flag", "ADISCORD_south_hegemon_NAM")] = True
            facts[("NAM", "ruling_leader")] = "NAM_Egor_Rom"
            for name in self.postwar:
                facts[("NAM", "has_completed_focus", name)] = True
            coordinates = {}
            for name, focus in self.postwar.items():
                gates = [e.value for e in focus if e.key == "allow_branch"]
                visible = not gates or self.matches(gates[0], facts)
                if name in membership:
                    self.assertEqual(visible, membership[name] == course, (balance, name))
                if not visible:
                    continue
                x, y = self.postwar_focus_position(focus, facts)
                self.assertNotIn((x, y), coordinates, (name, coordinates.get((x, y))))
                coordinates[x, y] = name
                if name == roots[course]:
                    self.assertEqual((x, y), (43, 4))
            self.assertLessEqual(max(x for x, y in coordinates), 75)
            self.assertLessEqual(max(y for x, y in coordinates), 27)
            political_right = max(
                self.postwar_focus_position(self.postwar[name], facts)[0]
                for name, route in membership.items() if route == course
                and self.postwar_focus_position(self.postwar[name], facts)[1] < 22
            )
            military_left = min(
                self.postwar_focus_position(focus, facts)[0]
                for focus in self.postwar.values()
                if any(e.key == "relative_position_id" and e.value in (
                    "NAM_pw_army_review", "NAM_pw_naval_review", "NAM_pw_air_review",
                ) for e in focus)
            )
            self.assertGreaterEqual(military_left - political_right, 2)
            self.assertLessEqual(military_left - political_right, 4)

    def test_postwar_layout_keeps_connection_corridors_clear(self):
        mandate_keys = {"NAM_prewar_" + route + "_mandate"
                        for route in ("service", "district", "pragmatic")}
        for route in ("service", "district", "pragmatic"):
            facts = self.postwar_facts()
            facts[("NAM", "has_variable", "NAM_prewar_balance")] = True
            facts[("NAM", "variable", "NAM_prewar_balance")] = {
                "service": -0.5, "district": 0.5, "pragmatic": 0,
            }[route]
            for name in self.postwar:
                facts[("NAM", "has_completed_focus", name)] = True
            visible = {name: focus for name, focus in self.postwar.items()
                       if not any(e.key in mandate_keys
                                  and e.key != "NAM_prewar_" + route + "_mandate"
                                  for e in walk(focus))}
            positions = {name: self.postwar_focus_position(focus, facts) for name, focus in visible.items()}
            exclusive_pairs = [
                (name, other.value)
                for name, focus in visible.items()
                for entry in focus if entry.key == "mutually_exclusive"
                for other in entry.value if other.value in positions and name < other.value
            ]
            for name, focus in visible.items():
                x, y = positions[name]
                for entry in focus:
                    if entry.key not in ("prerequisite", "mutually_exclusive"):
                        continue
                    for target in entry.value:
                        if target.value not in positions:
                            continue
                        tx, ty = positions[target.value]
                        if entry.key == "prerequisite":
                            for left, right in exclusive_pairs:
                                if target.value in (left, right):
                                    continue
                                lx, ly = positions[left]
                                rx, _ = positions[right]
                                self.assertFalse(min(lx, rx) < x < max(lx, rx) and ty < ly < y,
                                                 (route, name, target.value, left, right))
                        for other, (ox, oy) in positions.items():
                            if other in (name, target.value):
                                continue
                            if entry.key == "prerequisite":
                                blocked = ox == x and ty < oy < y
                            else:
                                blocked = oy == y == ty and min(x, tx) < ox < max(x, tx)
                            self.assertFalse(blocked, (route, name, target.value, other))

    def test_postwar_chapters_only_require_mandatory_ancestors_and_refresh_layout(self):
        mandatory = {}

        def required(name):
            if name not in mandatory:
                result = set()
                for group in (e.value for e in self.postwar[name] if e.key == "prerequisite"):
                    result.update(set.intersection(*(required(p.value) | {p.value} for p in group)))
                mandatory[name] = result
            return mandatory[name]

        milestones = set()
        revealed_focuses = {}
        for name, focus in self.postwar.items():
            for gate in (e.value for e in focus if e.key == "allow_branch"):
                for condition in gate:
                    if condition.key == "has_completed_focus":
                        self.assertIn(condition.value, required(name), (name, condition.value))
                        milestones.add(condition.value)
                        revealed_focuses.setdefault(condition.value, set()).add(name)
            for offset in (e.value for e in focus if e.key == "offset"):
                milestones.update(e.value for e in walk(block(offset, "trigger"))
                                  if e.key == "has_completed_focus")
        self.assertGreaterEqual(len(milestones), 30)
        for name in milestones:
            reward = block(self.postwar[name], "completion_reward")
            self.assertNotIn("mark_focus_tree_layout_dirty", [e.key for e in walk(reward)], name)
            callbacks = [e.value for hidden in reward if hidden.key == "hidden_effect"
                         for e in walk(hidden.value) if e.key == "country_event"
                         and scalar(e.value, "id") == BASE + ".118"]
            self.assertEqual(len(callbacks), 1, name)
            self.assertEqual(scalar(callbacks[0], "hours"), "1", name)
            self.assertIn(name + "_reveal_tt", [e.value for e in reward if e.key == "custom_effect_tooltip"])
            for language in ("russian", "english"):
                loc = ROOT / f"localisation/{language}/{BASE}_l_{language}.yml"
                self.assertTrue(loc.read_bytes().startswith(b"\xef\xbb\xbf"))
                text = re.search(rf'(?m)^ {name}_reveal_tt:0 "([^"\n]+)"$',
                                 loc.read_text(encoding="utf-8-sig"))
                self.assertIsNotNone(text, (language, name))
                self.assertEqual(set(re.findall(r"\$(NAM_\w+)\$", text[1])),
                                 revealed_focuses[name], (language, name))
                heading = "ДЕРЕВО ФОКУСОВ" if language == "russian" else "FOCUS TREE"
                self.assertTrue(text[1].startswith(f"§G{heading}§!\\n§Y"), (language, name))

    def test_postwar_reveal_callback_reads_committed_focus_state_and_ignores_other_trees(self):
        callback = self.events[BASE + ".118"]
        self.assertEqual(scalar(callback, "hidden"), "yes")
        self.assertEqual(scalar(callback, "is_triggered_only"), "yes")
        self.assertFalse(any(e.key == "fire_only_once" for e in callback))
        self.assertEqual(scalar(block(callback, "trigger"), "has_focus_tree"), "NAM_postwar_focus")
        self.assertEqual([(e.key, e.value) for e in block(callback, "immediate")],
                         [("mark_focus_tree_layout_dirty", "yes")])
        facts = self.postwar_facts()
        for name in self.postwar:
            facts[("NAM", "has_completed_focus", name)] = False
        for entry, children in (
            ("NAM_veterans_return", ("NAM_pw_army_review", "NAM_pw_naval_review", "NAM_pw_air_review")),
            ("NAM_civil_repair", ("NAM_pw_industrial_recovery", "NAM_pw_energy_commission",
                                  "NAM_oil_ministry", "NAM_pw_transport_commission")),
        ):
            for child in children:
                self.assertFalse(self.matches(block(self.postwar[child], "allow_branch"), facts))
            facts[("NAM", "has_completed_focus", entry)] = True
            for child in children:
                self.assertTrue(self.matches(block(self.postwar[child], "allow_branch"), facts))
        for loaded in (False, True):
            facts[("NAM", "has_focus_tree", "NAM_postwar_focus")] = loaded
            self.assertEqual(self.matches(block(callback, "trigger"), facts), loaded)

    def test_postwar_chapter_stages_keep_visible_nodes_and_connections_separate(self):
        def ancestors(name):
            return {p.value for e in self.postwar[name] if e.key == "prerequisite" for p in e.value}

        def closure(names):
            result = set(names)
            while True:
                expanded = result | {p for n in result for p in ancestors(n)}
                if expanded == result:
                    return result
                result = expanded

        chapter_names = {e.value for f in self.postwar.values() for g in f if g.key == "allow_branch"
                         for e in g.value if e.key == "has_completed_focus"}
        entry = {"NAM_civil_repair", "NAM_law_after_war", "NAM_veterans_return"}
        stages = [set(), closure(entry), set(self.postwar)]
        stages.extend(closure({name}) for name in sorted(chapter_names))
        economic = ("NAM_pw_industrial_recovery", "NAM_pw_energy_commission",
                    "NAM_oil_ministry", "NAM_pw_transport_commission")
        military = ("NAM_pw_army_review", "NAM_pw_naval_review", "NAM_pw_air_review")
        chapters = economic + military
        for completed in product((False, True), repeat=len(chapters)):
            stages.append(closure(entry | {name for name, active in zip(chapters, completed) if active}))
        for balance in (-0.5, 0, 0.5):
            for complete in stages:
                facts = self.postwar_facts()
                facts[("NAM", "has_variable", "NAM_prewar_balance")] = True
                facts[("NAM", "variable", "NAM_prewar_balance")] = balance
                for flag in ("ADISCORD_south_final_started", "ADISCORD_south_final_resolved",
                             "ADISCORD_south_hegemon_NAM"):
                    facts[("NAM", "has_global_flag", flag)] = bool(complete)
                for name in self.postwar:
                    facts[("NAM", "has_completed_focus", name)] = name in complete
                visible = {n: f for n, f in self.postwar.items() if all(
                    self.matches(e.value, facts) for e in f if e.key == "allow_branch")}
                positions = {}
                for name, focus in visible.items():
                    x, y = self.postwar_focus_position(focus, facts)
                    self.assertNotIn((x, y), positions.values(), (balance, complete, name, positions))
                    for other, (ox, oy) in positions.items():
                        if oy == y:
                            self.assertGreaterEqual(abs(ox - x), 2, (balance, complete, name, other))
                    positions[name] = (x, y)
                for name in chapters:
                    if name in visible and name not in complete:
                        self.assertEqual(positions[name][1], 4, (complete, name))
                for left, right in ((economic[0], economic[1]), (economic[2], economic[3])):
                    if left in complete and right in complete:
                        self.assertLessEqual(abs(positions[left][1] - positions[right][1]), 3)
                for name, focus in visible.items():
                    anchor = next((e.value for e in focus if e.key == "relative_position_id"), None)
                    if anchor in economic:
                        self.assertLessEqual(positions[name][1], 14, (complete, name))
                    if anchor in military:
                        self.assertLessEqual(positions[name][1], 17, (complete, name))
                if not complete:
                    self.assertEqual(set(visible), entry | {"NAM_recognition"})
                    self.assertLessEqual(max(x for x, _ in positions.values())
                                         - min(x for x, _ in positions.values()), 16)
                pairs = [(n, p.value) for n, f in visible.items()
                         for e in f if e.key == "mutually_exclusive" for p in e.value
                         if p.value in positions and n < p.value]
                for name, focus in visible.items():
                    x, y = positions[name]
                    for group in (e.value for e in focus if e.key == "prerequisite"):
                        for parent in group:
                            if parent.value not in positions:
                                continue
                            _, py = positions[parent.value]
                            self.assertLess(py, y, (balance, complete, name, parent.value))
                            for left, right in pairs:
                                if parent.value in (left, right):
                                    continue
                                lx, ly = positions[left]
                                rx, _ = positions[right]
                                self.assertFalse(min(lx, rx) < x < max(lx, rx) and py < ly < y,
                                                 (balance, complete, name, parent.value, left, right))
                            for other, (ox, oy) in positions.items():
                                if other not in (name, parent.value):
                                    self.assertFalse(ox == x and py < oy < y,
                                                     (balance, complete, name, parent.value, other))

    def test_postwar_three_branches_and_compact_prerequisites(self):
        roots = {"NAM_civil_repair", "NAM_law_after_war", "NAM_veterans_return"}
        children = {name for name, focus in self.postwar.items() if any(
            e.key == "prerequisite" and any(p.value == "NAM_recognition" for p in e.value) for e in focus)}
        self.assertEqual(children, roots)
        for name in ("NAM_pw_army_review", "NAM_pw_naval_review", "NAM_pw_air_review"):
            self.assertEqual(scalar(block(self.postwar[name], "prerequisite"), "focus"), "NAM_veterans_return")
        for name in ("NAM_service_state", "NAM_federal_charter", "NAM_pragmatic_compact"):
            self.assertEqual(scalar(block(self.postwar[name], "prerequisite"), "focus"), "NAM_law_after_war")
        facts = self.postwar_facts()
        for name in self.postwar:
            facts[("NAM", "has_completed_focus", name)] = True
        for name, focus in self.postwar.items():
            _, y = self.postwar_focus_position(focus, facts)
            for entry in focus:
                if entry.key == "prerequisite":
                    for parent in entry.value:
                        self.assertLess(self.postwar_focus_position(self.postwar[parent.value], facts)[1],
                                        y, (name, parent.value))
                elif entry.key == "mutually_exclusive":
                    for other in entry.value:
                        self.assertEqual(self.postwar_focus_position(self.postwar[other.value], facts)[1],
                                         y, (name, other.value))
        for focus in self.postwar.values():
            reward = block(focus, "completion_reward")
            self.assertFalse(len(reward) == 1 and reward[0].key == "add_tech_bonus", scalar(focus, "id"))

    def test_postwar_new_orders_deliver_once_or_refund_a_lost_site(self):
        results = {
            "development_works": (("700", "building", "industrial_complex"), 1, "700"),
            "merchant_order": (("NAM", "equipment", "convoy"), 30, None),
            "rural_electrification": (("690", "reward", "building_slots"), 1, "690"),
        }
        for name, (output, amount, state) in results.items():
            decision = self.decisions["NAM_pw_" + name]
            for lost in (False, True) if state else (False,):
                facts = self.postwar_facts()
                money = facts[("NAM", "variable", "ADISCORD_economy_treasury")]
                self.apply(block(decision, "complete_effect"), facts)
                if lost:
                    facts[("NAM", "controls_state", state)] = False
                    self.assertTrue(self.matches(block(decision, "cancel_trigger"), facts))
                self.apply(block(decision, "remove_effect"), facts)
                self.assertEqual(facts.get(output, 0), 0 if lost else amount, name)
                if lost:
                    self.assertEqual(facts[("NAM", "variable", "ADISCORD_economy_treasury")], money)
                elif name == "merchant_order":
                    self.assertEqual(facts[("NAM", "equipment", "motorized_equipment")], 300)
                result = dict(facts)
                self.apply(block(decision, "remove_effect"), facts)
                self.apply(block(decision, "cancel_effect"), facts)
                self.assertEqual(facts, result, (name, "late callback"))
                self.assertFalse(facts[("NAM", "has_country_flag", "NAM_pw_civil_busy")])

    def test_land_register_settles_one_policy_and_refunds_an_interrupted_survey(self):
        lease = self.decisions["NAM_program_cadastre"]
        grants = self.decisions["NAM_program_land_allotments"]
        treasury = ("NAM", "variable", "ADISCORD_economy_treasury")
        for order, other in ((lease, grants), (grants, lease)):
            facts = self.postwar_facts()
            for state in ("689", "690", "700"):
                facts[(state, "numeric", "infrastructure")] = 5
            initial = facts[treasury]
            self.apply(block(order, "complete_effect"), facts)
            self.apply(block(other, "complete_effect"), facts)
            self.assertEqual(facts[treasury], initial - 500)
            self.apply(block(order, "remove_effect"), facts)
            self.assertTrue(facts[("NAM", "has_country_flag", "NAM_land_register_ratified")])
            self.assertFalse(self.matches(block(other, "visible"), facts))
            self.assertEqual(facts.get(("NAM", "variable", "NAM_adm_land_rent"), 0), 20 if order is lease else 0)
            for state in ("689", "690"):
                self.assertEqual(facts.get((state, "reward", "building_slots"), 0), 2 if order is grants else 0)
            result = dict(facts)
            self.apply(block(other, "complete_effect"), facts)
            self.apply(block(order, "remove_effect"), facts)
            self.assertEqual(facts, result)
        facts = self.postwar_facts()
        initial = facts[treasury]
        self.apply(block(grants, "complete_effect"), facts)
        facts[("NAM", "controls_state", "690")] = False
        self.apply(block(grants, "remove_effect"), facts)
        self.apply(block(grants, "cancel_effect"), facts)
        self.assertEqual(facts[treasury], initial)
        self.assertTrue(self.matches(block(lease, "available"), facts))

    def test_operational_upgrades_pay_only_with_a_completed_follow_up(self):
        orders = (
            ("NAM_program_road_priority", "NAM_basin_works_depot", ("NAM", "equipment", "motorized_equipment"), 120),
            ("NAM_pw_district_cooperative", "NAM_dryriver_power_cooperative",
             ("NAM", "variable", "ADISCORD_economy_treasury"), 150),
        )
        for name, flag, output, delta in orders:
            decision = self.decisions[name]
            amounts = []
            for active in (False, True):
                facts = self.postwar_facts()
                facts[("NAM", "has_country_flag", flag)] = active
                self.apply(block(decision, "complete_effect"), facts)
                self.apply(block(decision, "remove_effect"), facts)
                result = dict(facts)
                self.apply(block(decision, "remove_effect"), facts)
                self.assertEqual(result, facts)
                amounts.append(facts.get(output, 0))
            self.assertEqual(amounts[1] - amounts[0], delta, name)

    def test_commissioned_programmes_on_full_sites(self):
        for name, state, output, amount in (
            ("tool_reserve", "700", "support_equipment", 350),
            ("naval_workshops", "700", "convoy", 24),
            ("radar_posts", "700", "ADISCORD_fighter_airframe_2163", 36),
            ("power_reserve", "700", "anti_air_equipment", 120),
            ("airfield_network", "700", "ADISCORD_transport_airframe_2162", 24),
        ):
            decision = self.decisions["NAM_program_" + name]
            focus = self.postwar["NAM_pw_" + name]
            facts = self.postwar_facts()
            for kind, cap in (("dockyard", 12), ("radar_station", 6), ("air_base", 10), ("anti_air_building", 5)):
                facts[(state, "numeric", kind)] = cap
            self.assertFalse(any(entry.key == "bypass" for entry in focus), name)
            self.assertTrue(self.matches(block(decision, "available"), facts), name)
            initial = dict(facts)
            self.apply(block(decision, "complete_effect"), facts)
            facts[("NAM", "controls_state", state)] = False
            self.apply(block(decision, "remove_effect"), facts)
            cash = ("NAM", "variable", "ADISCORD_economy_treasury")
            self.assertEqual(facts[cash], initial[cash], name)
            self.assertFalse(facts.get(("NAM", "equipment", output), 0), name)
            facts[("NAM", "controls_state", state)] = True
            self.apply(block(decision, "complete_effect"), facts)
            for _ in range(2):
                self.apply(block(decision, "remove_effect"), facts)
            self.assertEqual(facts[("NAM", "equipment", output)], amount, name)
            if name in ("tool_reserve", "naval_workshops", "radar_posts"):
                self.assertFalse(self.matches(block(decision, "visible"), facts), name)
                paid = facts[cash]
                self.apply(block(decision, "complete_effect"), facts)
                self.assertEqual(facts[cash], paid, name)

    def test_route_commissions_deliver_on_built_up_sites(self):
        facts = self.postwar_facts()
        facts[("NAM", "has_completed_focus", "NAM_ladder_of_seals")] = False
        facts[("700", "variable", "fixture_building_slots_arms_factory_no")] = 0
        order = self.decisions["NAM_pw_state_arsenal"]
        self.assertFalse(self.matches(block(order, "visible"), facts))
        facts[("NAM", "has_completed_focus", "NAM_pw_industrial_commission")] = True
        self.assertTrue(self.matches(block(order, "visible"), facts))
        self.assertTrue(self.matches(block(order, "available"), facts))
        self.apply(block(order, "complete_effect"), facts)
        for _ in range(2):
            self.apply(block(order, "remove_effect"), facts)
        self.assertEqual(facts[("NAM", "equipment", "artillery_equipment")], 150)
        self.assertNotIn(("700", "building", "arms_factory"), facts)
        for hauliers, equipment, amount in ((True, "train_equipment", 24), (False, "artillery_equipment", 120)):
            facts = self.postwar_facts()
            facts[("688", "fixture_free_building_slots", "industrial_complex:1:yes")] = False
            facts[("NAM", "has_completed_focus", "NAM_district_fair")] = True
            facts[("NAM", "has_completed_focus", "NAM_haulage_cooperatives")] = hauliers
            facts[("NAM", "has_completed_focus", "NAM_tool_cooperatives")] = not hauliers
            coop = self.decisions["NAM_pw_district_cooperative"]
            self.apply(block(coop, "complete_effect"), facts)
            self.apply(block(coop, "remove_effect"), facts)
            self.assertEqual(facts[("NAM", "equipment", equipment)], amount)
            self.assertNotIn(("688", "building", "industrial_complex"), facts)

    def test_course_institutions_apply_to_paid_deliveries_once(self):
        cases = (
            ("pw_garrison_order", "pw_armament_inspectorate", ("NAM", "equipment", "artillery_equipment"), 96),
            ("pw_district_schools", "relief_register", ("NAM", "numeric", "has_manpower"), 800),
            ("pw_export_shipment", "freight_brokerage", ("NAM", "variable", "ADISCORD_economy_treasury"), 125),
        )
        for order, focus, key, delta in cases:
            decision = self.decisions["NAM_" + order]
            results = []
            for active in (False, True):
                facts = self.postwar_facts()
                facts[("NAM", "has_completed_focus", "NAM_" + focus)] = active
                facts[("NAM", "has_completed_focus", "NAM_regional_university")] = False
                facts[("NAM", "has_completed_focus", "NAM_pw_southern_schools")] = False
                facts[("NAM", "has_completed_focus", "NAM_oil_fund")] = False
                facts[("NAM", "has_completed_focus", "NAM_export_consortium")] = False
                if order != "pw_garrison_order":
                    self.assertEqual(self.matches(block(decision, "visible"), facts), active)
                facts[("NAM", "has_completed_focus", "NAM_oil_fund")] = not active
                facts[("NAM", "has_completed_focus", "NAM_export_consortium")] = not active
                facts[("NAM", "numeric", "has_fuel")] = 60000
                self.apply(block(decision, "complete_effect"), facts)
                before = facts.get(key, 0)
                for _ in range(2):
                    self.apply(block(decision, "remove_effect"), facts)
                results.append(facts.get(key, 0) - before)
            self.assertEqual(results[1] - results[0], delta, order)

    def test_pump_station_commission_expands_full_field_only_once(self):
        decision = self.decisions["NAM_program_oilfield_substations"]
        facts = self.postwar_facts()
        facts[("NAM", "variable", "NAM_oil_bonus_units")] = 0
        with patch.dict(self.effects, {"NAM_oil_refresh": []}):
            self.apply(self.effects["NAM_oil_initialize"], facts)
        for key in ("NAM_field_max_capacity", "NAM_field_capacity"):
            facts[("67", "has_variable", key)] = True
            facts[("67", "variable", key)] = 11
        facts[("67", "numeric", "infrastructure")] = 5
        self.apply(block(decision, "complete_effect"), facts)
        self.apply(block(decision, "remove_effect"), facts)
        self.apply(block(decision, "remove_effect"), facts)
        for key in ("NAM_field_max_capacity", "NAM_field_capacity"):
            self.assertEqual(facts[("67", "variable", key)], 13)
        self.assertFalse(self.matches(block(decision, "visible"), facts))

    def test_visible_decision_summaries_share_one_lead_in_across_trees(self):
        decisions = {entry.value for kind in TREES for focus in tree_focuses(kind)[1].values()
                     for entry in walk(block(focus, "completion_reward")) if entry.key == "unlock_decision_tooltip"}
        for lang, prefix in (("russian", "После применения решения: "), ("english", "After using the decision: ")):
            values = dict(re.findall(r'^ (\w+_unlock_tt):\d* "(.*)"$', read(
                f"localisation/{lang}/{BASE}_l_{lang}.yml"), re.M))
            for decision in decisions:
                self.assertTrue(values[decision + "_unlock_tt"].startswith(prefix), (lang, decision))

    def test_specialised_orders_deliver_only_on_success_and_only_once(self):
        cases = (
            ("district_cooperative", "haulage_cooperatives", "motorized_equipment", 150),
            ("district_cooperative", "tool_cooperatives", "support_equipment", 180),
            ("merchant_order", "chartered_tonnage", "convoy", 45),
            ("merchant_order", "tractor_leasing", "motorized_equipment", 540),
        )
        for order, focus, equipment, amount in cases:
            decision = self.decisions["NAM_pw_" + order]
            for cancel in (False, True):
                facts = self.postwar_facts()
                facts[("NAM", "has_completed_focus", "NAM_" + focus)] = True
                self.apply(block(decision, "complete_effect"), facts)
                if cancel:
                    self.apply(block(decision, "cancel_effect"), facts)
                self.apply(block(decision, "remove_effect"), facts)
                self.apply(block(decision, "remove_effect"), facts)
                self.assertEqual(facts.get(("NAM", "equipment", equipment), 0),
                                 0 if cancel else amount, (order, focus, cancel))

    def test_district_and_commercial_projects_use_existing_sites_when_full(self):
        projects = (
            ("district_fair", "689", "industrial_complex", "motorized_equipment", 180),
            ("relief_reserves", "690", "fuel_silo", "train_equipment", 16),
            ("bonded_terminal", "700", "fuel_silo", "convoy", 18),
            ("licensed_workshop", "688", "arms_factory", "support_equipment", 350),
        )
        for name, state, building, alternative, amount in projects:
            focus = self.postwar["NAM_" + name]
            for slots in (0, 1, 3):
                has_space = slots > 0
                facts = self.postwar_facts()
                facts[("NAM", "has_variable", "NAM_prewar_balance")] = True
                facts[("NAM", "variable", "NAM_prewar_balance")] = 0.5 if name in (
                    "district_fair", "relief_reserves") else 0
                facts[(state, "variable", "fixture_building_slots_" + building + "_no")] = slots
                self.assertTrue(self.matches(block(focus, "available"), facts), name)
                self.apply(block(focus, "completion_reward"), facts)
                self.assertEqual(facts.get((state, "building", building), 0), int(has_space), name)
                self.assertEqual(facts.get(("NAM", "equipment", alternative), 0),
                                 0 if has_space else amount, name)

    def test_postwar_ai_respects_inherited_political_course(self):
        plans = parsed("common/ai_strategy_plans/ADISCORD_NAM_plans.txt")
        names = ("NAM_postwar_vertical_plan", "NAM_postwar_pragmatic_plan", "NAM_postwar_plan")
        for balance, active in ((-0.5, 0), (-0.25, 1), (0, 1), (0.25, 1), (0.5, 2)):
            facts = self.postwar_facts()
            facts[("NAM", "is_ai", "yes")] = True
            facts[("NAM", "has_focus_tree", "NAM_postwar_focus")] = True
            facts[("NAM", "has_variable", "NAM_prewar_balance")] = True
            facts[("NAM", "variable", "NAM_prewar_balance")] = balance
            facts[("NAM", "has_completed_focus", "NAM_service_state")] = False
            for index, name in enumerate(names):
                plan = block(plans, name)
                self.assertEqual(self.matches(block(plan, "enable"), facts), index == active, (balance, name))
                ids = [e.value for e in block(plan, "ai_national_focuses")]
                self.assertEqual(len(ids), len(set(ids)))
                self.assertTrue(set(ids).issubset(self.postwar))
                for focus_id in ids:
                    for entry in self.postwar[focus_id]:
                        if entry.key == "mutually_exclusive":
                            self.assertFalse({e.value for e in entry.value}.intersection(ids), name)


    EXPANDED_POSTWAR_PROGRAMMES = {
        "industrial_schedule": (40, 450, 0, 35),
        "regional_contracts": (35, 400, 0, 35),
        "public_utilities": (40, 500, 0, 42),
        "municipal_services": (35, 350, 0, 35),
        "export_clearing": (30, 400, 60000, 28),
        "import_machine_tools": (40, 600, 0, 56),
        "contract_arbitration": (35, 350, 0, 35),
    }

    def expanded_programme_facts(self):
        facts = self.postwar_facts()
        facts[("700", "numeric", "naval_base")] = 1
        facts[("NAM", "numeric", "has_fuel")] = 100000
        return facts

    def test_inspectorate_registers_only_fees_paid_after_enactment(self):
        projects = (("repair_wells", "67", 25, 150), ("refinery", "67", 40, 300),
                    ("pipeline", "690", 35, 350), ("sea_terminal", "700", 30, 250))
        for short, state, price, fee in projects:
            order = self.bind_field(self.decisions["NAM_project_" + short], state)
            for insured in (False, True):
                facts = self.economy_facts()
                facts[("fixture", "previous_state")] = state
                facts[("NAM", "has_completed_focus", "NAM_pw_labour_inspection")] = insured
                self.apply(block(order, "complete_effect"), facts)
                cash = ("NAM", "variable", "ADISCORD_economy_treasury")
                pp = ("NAM", "numeric", "has_political_power")
                self.assertEqual((facts[cash], facts[pp]), (10000 - fee, 1000 - price), short)
                facts[("NAM", "has_completed_focus", "NAM_pw_labour_inspection")] = True
                facts[(state, "is_controlled_by", "NAM")] = False
                self.apply(block(order, "remove_effect"), facts)
                self.apply(block(order, "cancel_effect"), facts)
                self.assertEqual((facts[cash], facts[pp]), (10000, 1000 if insured else 1000 - price), short)
                self.assertEqual(facts[("NAM", "variable", "NAM_projects_in_progress")], 0)
                facts[(state, "has_state_flag", "NAM_project_in_progress")] = True
                facts[(state, "variable", "NAM_project_deposit")] = 1200
                facts[(state, "variable", "NAM_project_pp_deposit")] = 50
                old = dict(facts)
                self.apply(block(order, "remove_effect"), facts)
                self.apply(block(order, "cancel_effect"), facts)
                self.assertEqual(facts, old, short)

    def test_labour_arbitration_addresses_only_the_current_or_next_outstanding_dispute(self):
        order = self.decisions["NAM_agreement_settlement"]
        for number, active, qualified in product((1, 2, 3), (False, True), (False, True)):
            facts = self.agreement_facts(number)
            oil = ("NAM", "has_idea", "NAM_agreement_oil_failure")
            district = ("NAM", "has_idea", "NAM_agreement_dist_failure")
            facts[oil] = facts[district] = True
            facts[("NAM", "has_active_mission", "NAM_agreement_crisis")] = active
            facts[("NAM", "has_completed_focus", "NAM_pw_arbitration_commissions")] = qualified
            funds = ("NAM", "variable", "ADISCORD_economy_treasury")
            initial = facts[funds]
            self.assertEqual(self.matches(block(order, "visible"), facts), active or qualified)
            with patch.dict(self.effects, {"NAM_groups_refresh": [], "NAM_agreement_finish": []}):
                self.apply(block(order, "complete_effect"), facts)
            self.assertEqual(facts[funds], initial - (600 if active or qualified else 0))
            self.assertEqual(facts[oil], not (qualified and (not active or number == 2)))
            self.assertEqual(facts[district], not (qualified and active and number == 3))
            if not active and qualified:
                self.apply(block(order, "complete_effect"), facts)
                self.assertFalse(facts[district])
                self.assertFalse(self.matches(block(order, "visible"), facts))
                self.apply(block(order, "complete_effect"), facts)
                self.assertEqual(facts[funds], initial - 1200)

    def test_labour_shift_uses_one_paid_crew_and_returns_only_its_workers(self):
        order = self.decisions["NAM_hire_relief_shift"]
        displays = parsed(f"common/scripted_localisation/{BASE}_scripted_loc.txt")
        capacity = next(e.value for e in displays if e.key == "defined_text" and scalar(e.value, "name") == "NAMProjectSlots")
        for slots, workers, reading in ((1, 0, "base"), (2, 0, "base"), (1, 600, "two"), (2, 600, "three")):
            facts = {("NAM", "variable", "NAM_project_slots"): slots, ("NAM", "variable", "NAM_labour_shift_workers"): workers}
            key = next(scalar(option.value, "localization_key") for option in capacity if option.key == "text"
                       and self.matches(next((item.value for item in option.value if item.key == "trigger"), []), facts))
            self.assertEqual(key, f"NAM_labour_shift_{reading}_slots")
        for funded, cash, expected in ((False, 299, False), (False, 300, True), (True, 0, True), (True, 300, True)):
            facts = self.postwar_facts()
            treasury = ("NAM", "variable", "ADISCORD_economy_treasury")
            recruits = ("NAM", "numeric", "has_manpower")
            fund = ("NAM", "has_country_flag", "NAM_crisis_fund")
            facts.update({treasury: cash, recruits: 600, fund: funded,
                          ("NAM", "has_completed_focus", "NAM_pw_labour_code"): True,
                          ("NAM", "has_completed_focus", "NAM_pw_social_budget"): True,
                          ("NAM", "variable", "NAM_projects_in_progress"): 2})
            self.assertFalse(self.matches(block(order, "custom_cost_trigger"), {**facts, recruits: 599.99}))
            self.assertEqual(self.matches(block(order, "custom_cost_trigger"), facts), expected)
            self.assertFalse(self.matches(self.triggers["NAM_project_slot_free"], facts))
            self.apply(block(order, "complete_effect"), facts)
            self.apply(block(order, "complete_effect"), facts)
            self.assertEqual(facts[recruits], 0 if expected else 600)
            self.assertEqual(facts[treasury], cash - 300 if cash >= 300 else cash)
            self.assertEqual(facts[fund], funded and cash >= 300)
            self.assertEqual(self.matches(self.triggers["NAM_project_slot_free"], facts), expected)
            facts[("NAM", "variable", "NAM_projects_in_progress")] = 3
            self.assertFalse(self.matches(self.triggers["NAM_project_slot_free"], facts))
            self.apply(block(order, "cancel_effect"), facts)
            self.apply(block(order, "remove_effect"), facts)
            self.assertEqual(facts[recruits], 600)

        facts = self.postwar_facts()
        facts[("NAM", "has_completed_focus", "NAM_pw_labour_code")] = True
        facts[("NAM", "numeric", "has_manpower")] = 600
        self.apply(block(order, "complete_effect"), facts)
        for site in ("67", "688", "689"):
            project = self.bind_field(self.decisions["NAM_econ_deep_drilling"], site)
            self.apply(block(project, "complete_effect"), facts)
        self.assertEqual(facts[("NAM", "variable", "NAM_projects_in_progress")], 3)
        self.apply(block(order, "remove_effect"), facts)
        self.assertFalse(self.matches(self.triggers["NAM_project_slot_free"], facts))
        with patch.dict(self.effects, {"NAM_oil_refresh": []}):
            for count, site in enumerate(("67", "688", "689"), 1):
                facts[("fixture", "previous_state")] = site
                project = self.bind_field(self.decisions["NAM_econ_deep_drilling"], site)
                self.apply(block(project, "remove_effect"), facts)
                self.assertEqual(facts[(site, "variable", "NAM_field_capacity")], 10)
                self.assertEqual(facts[("NAM", "variable", "NAM_projects_in_progress")], 3 - count)
                self.assertEqual(self.matches(self.triggers["NAM_project_slot_free"], facts), count > 1)

    def test_standard_housing_series_requires_a_delivered_plan_and_both_real_sites(self):
        project = self.decisions["NAM_veteran_housing"]
        facts = self.postwar_facts()
        for name in ("NAM_civil_dividend", "NAM_south_heritage", "NAM_pw_standard_projects"):
            facts[("NAM", "has_completed_focus", name)] = False
        self.assertFalse(self.matches(block(project, "visible"), facts))
        facts[("NAM", "has_completed_focus", "NAM_pw_standard_projects")] = True
        self.assertTrue(self.matches(block(project, "visible"), facts))
        for name in ("NAM_south_heritage", "NAM_civil_dividend"):
            reward = self.expand(block(self.postwar[name], "completion_reward"))
            output = [e for _, e in selected_effects(reward, facts, "NAM")]
            self.assertNotIn("NAM_veteran_housing", [e.value for e in output if e.key == "unlock_decision_tooltip"])
            self.assertIn("add_to_variable", {e.key for e in output})
        capital = ("700", "building", "industrial_complex")
        district = ("688", "building", "industrial_complex")
        self.apply(block(project, "complete_effect"), facts)
        self.apply(block(project, "remove_effect"), facts)
        self.assertEqual((facts.get(capital, 0), facts.get(district, 0)), (1, 0))
        for failure in ("control", "capacity", None):
            campaign = dict(facts)
            funds = campaign[("NAM", "variable", "ADISCORD_economy_treasury")]
            pp = campaign[("NAM", "numeric", "has_political_power")]
            self.apply(block(project, "complete_effect"), campaign)
            if failure == "control":
                campaign[("NAM", "controls_state", "688")] = False
            if failure == "capacity":
                campaign[("688", "variable", "fixture_building_slots_industrial_complex_no")] = 0
            self.assertEqual(self.matches(block(project, "cancel_trigger"), campaign), bool(failure))
            self.apply(block(project, "remove_effect"), campaign)
            self.apply(block(project, "cancel_effect"), campaign)
            self.assertEqual((campaign.get(capital, 0), campaign.get(district, 0)), (1, 0) if failure else (2, 1))
            self.assertEqual(campaign[("NAM", "variable", "ADISCORD_economy_treasury")], funds - (0 if failure else 500))
            self.assertEqual(campaign[("NAM", "numeric", "has_political_power")], pp - (0 if failure else 35))

    def test_design_offices_develop_only_the_surveyed_mainland_mine(self):
        project = self.decisions["NAM_project_steel"]
        for state, permit in (("231", "NAM_island_accounts"), ("690", "NAM_pw_local_design_offices")):
            order = self.bind_field(project, state)
            facts = self.economy_facts()
            facts[("fixture", "previous_state")] = state
            facts[(state, "state", state)] = True
            facts[(state, "is_owned_by", "NAM")] = True
            facts[(state, "is_controlled_by", "NAM")] = True
            for name in ("NAM_island_accounts", "NAM_pw_local_design_offices"):
                facts[("NAM", "has_completed_focus", name)] = name != permit
            self.assertFalse(self.matches(block(order, "visible"), facts))
            self.apply(block(order, "complete_effect"), facts)
            cash = ("NAM", "variable", "ADISCORD_economy_treasury")
            self.assertEqual(facts[cash], 10000)
            facts[("NAM", "has_completed_focus", permit)] = True
            self.assertTrue(self.matches(block(order, "visible"), facts))
            self.apply(block(order, "complete_effect"), facts)
            self.assertEqual(facts[cash], 9400)
            for lost in (True, False):
                campaign = dict(facts)
                campaign[(state, "is_controlled_by", "NAM")] = not lost
                self.assertEqual(self.matches(block(order, "cancel_trigger"), campaign), lost)
                self.apply(block(order, "remove_effect"), campaign)
                self.apply(block(order, "cancel_effect"), campaign)
                self.assertEqual(campaign[cash], 10000 if lost else 9400)
                self.assertEqual(campaign.get((state, "has_state_flag", "NAM_steel_mine_expanded"), False), not lost)
                self.assertEqual(campaign.get((state, "resource", "steel"), 0), 0 if lost else 12)
                self.assertEqual(self.matches(block(order, "visible"), campaign), lost)

    def test_expanded_programmes_prices_shared_slot_delivery_and_refund(self):
        currencies = (("NAM", "numeric", "has_political_power"),
                      ("NAM", "variable", "ADISCORD_economy_treasury"),
                      ("NAM", "numeric", "has_fuel"))
        for short, (pp, cash, fuel, days) in self.EXPANDED_POSTWAR_PROGRAMMES.items():
            name = "NAM_pw_" + short
            decision = self.decisions[name]
            self.assertEqual(scalar(decision, "cost"), "0", name)
            self.assertEqual(scalar(decision, "days_remove"), str(days), name)
            for key, price in zip(currencies, (pp, cash, fuel)):
                if not price:
                    continue
                facts = self.expanded_programme_facts()
                facts[key] = price - 0.01
                self.assertFalse(self.matches(block(decision, "custom_cost_trigger"), facts), name)
                before = dict(facts)
                self.apply(block(decision, "complete_effect"), facts)
                self.assertEqual(facts, before, (name, "unaffordable stale click"))
            for cancel in (False, True):
                facts = self.expanded_programme_facts()
                for key, price in zip(currencies, (pp, cash, fuel)):
                    facts[key] = price
                self.assertTrue(self.matches(block(decision, "available"), facts), name)
                self.assertTrue(self.matches(block(decision, "custom_cost_trigger"), facts), name)
                self.apply(block(decision, "complete_effect"), facts)
                self.assertEqual([facts[key] for key in currencies], [0, 0, 0], name)
                paid = dict(facts)
                self.apply(block(decision, "complete_effect"), facts)
                self.assertEqual(facts, paid, (name, "duplicate payment"))
                for other in (*self.EXPANDED_POSTWAR_PROGRAMMES,):
                    self.assertFalse(self.matches(block(self.decisions["NAM_pw_" + other], "available"), facts), (name, other))
                self.assertFalse(self.matches(block(self.decisions["NAM_veteran_housing"], "available"), facts))
                self.apply(block(decision, "cancel_effect" if cancel else "remove_effect"), facts)
                if cancel:
                    self.assertEqual([facts[key] for key in currencies], [pp, cash, fuel], name)
                elif fuel:
                    self.assertEqual(facts[currencies[1]], 1000, name)
                else:
                    self.assertTrue(facts[("NAM", "has_idea", name + "_idea")], name)
                    expected = 270 if short in ("industrial_schedule", "regional_contracts") else 180
                    self.assertEqual(facts[("NAM", "idea_days", name + "_idea")], expected, name)
                self.assertFalse(facts[("NAM", "has_country_flag", "NAM_pw_civil_busy")])
                result = dict(facts)
                self.apply(block(decision, "remove_effect"), facts)
                self.apply(block(decision, "cancel_effect"), facts)
                self.assertEqual(facts, result, (name, "late callbacks"))

    def test_port_programmes_refund_lost_port_and_preserve_fuel_overflow(self):
        for short in ("export_clearing", "import_machine_tools"):
            decision = self.decisions["NAM_pw_" + short]
            facts = self.expanded_programme_facts()
            cash = facts[("NAM", "variable", "ADISCORD_economy_treasury")]
            self.apply(block(decision, "complete_effect"), facts)
            facts[("NAM", "controls_state", "700")] = False
            self.assertTrue(self.matches(block(decision, "cancel_trigger"), facts))
            facts[("NAM", "numeric", "has_fuel")] = 200000
            facts[("NAM", "fuel_capacity")] = 200000
            self.apply(block(decision, "remove_effect"), facts)
            self.assertEqual(facts[("NAM", "variable", "ADISCORD_economy_treasury")], cash)
            if short == "export_clearing":
                self.assertEqual(facts[("NAM", "variable", "NAM_open_fuel_reserve")], 60000)

    def run_postwar_budget(self, vertical, armed, export):
        """Source-derived focus/order queue, without passive treasury or factory income.

        Earmark 200 PP, 3500 treasury and 8000 fuel after the resource war,
        with 0.25 net PP/day and 1000 net fuel/day capped at 200000.
        This is a planning envelope, not a simulation of
        random events, weekly expenses, occupied slots or native decision timing.
        Diplomacy consumes its focus time; offer responses and story wars are
        not simulated, so the queue assumes the story gate remains open.
        """
        route = ["NAM_recognition", "NAM_law_after_war"]
        if vertical:
            route += ["NAM_service_state", "NAM_seal_registry", "NAM_namestnik_garrisons",
                      "NAM_oil_quotas", "NAM_state_plan", "NAM_unified_standards",
                      "NAM_ladder_of_seals", "NAM_ladder_ending_service"]
            wanted = ["NAM_district_audit", "NAM_pw_garrison_order", "NAM_pw_fuel_quota", "NAM_pw_state_arsenal"]
        else:
            route += ["NAM_federal_charter", "NAM_district_council", "NAM_oil_fund",
                      "NAM_district_militia", "NAM_public_utilities", "NAM_civic_audit",
                      "NAM_common_fuel_market", "NAM_charter_ending_federation"]
            wanted = ["NAM_pw_district_congress", "NAM_pw_district_schools",
                      "NAM_pw_militia_reserve", "NAM_pw_district_cooperative"]
        route += ["NAM_veterans_return", "NAM_civil_repair",
                  "NAM_armed_peace" if armed else "NAM_civil_dividend", "NAM_oil_ministry",
                  "NAM_export_consortium" if export else "NAM_state_refineries",
                  "NAM_oil_exchange", "NAM_national_university"]
        route += (["NAM_south_black_basin", "NAM_south_desert_offices"] if vertical else
                  ["NAM_south_oil_for_water", "NAM_south_fenn_guarantee"])
        route.append("NAM_svetlogorye")
        route += ["NAM_pw_transport_commission", "NAM_pw_road_priority", "NAM_pw_logistics_depots",
                  "NAM_pw_army_review", "NAM_pw_breakthrough_army", "NAM_pw_staff_exercises",
                  "NAM_pw_reserve_centres", "NAM_pw_southern_army",
                  "NAM_pw_transport_maintenance", "NAM_pw_freight_schedule"]
        wanted += ["NAM_program_road_priority", "NAM_program_logistics_depots"]
        wanted += ["NAM_pw_veteran_course", "NAM_postwar_rearmament" if armed else "NAM_veteran_housing",
                   "NAM_pw_export_shipment" if export else "NAM_econ_petrochemical_batch"]
        facts = self.postwar_facts()
        for focus in (*self.focuses, *self.postwar):
            facts[("NAM", "has_completed_focus", focus)] = False
        facts[("NAM", "has_completed_focus", "NAM_vertical" if vertical else "NAM_districts")] = True
        facts[("NAM", "has_variable", "NAM_prewar_balance")] = True
        facts[("NAM", "variable", "NAM_prewar_balance")] = -0.5 if vertical else 0.5
        facts[("NAM", "has_war", "yes")] = False
        facts[("NAM", "ADISCORD_south_nam_story_clear", "yes")] = True
        facts[("NAM", "numeric", "has_political_power")] = 200
        facts[("NAM", "numeric", "has_fuel")] = 8000
        facts[("NAM", "variable", "ADISCORD_economy_treasury")] = 3500
        facts[("NAM", "variable", "fixture_army_manpower")] = 18000
        facts[("NAM", "equipment", "infantry_equipment")] = 3000
        facts[("NAM", "equipment", "support_equipment")] = 200
        facts[("NAM", "variable", "NAM_grp_dist_support")] = 40
        accounting = {name: body for name, body in self.effects.items()
                      if name in ("NAM_add_treasury", "NAM_spend_treasury", "NAM_receive_250")
                      or any(name == order + suffix for order in (*self.POSTWAR_ORDERS, "NAM_program_road_priority", "NAM_program_logistics_depots") for suffix in ("_refund", "_settle"))}
        pending = {}
        finished = {}
        focus_days = {}
        index = 0
        due = int(scalar(self.postwar[route[0]], "cost")) * 7
        with patch.object(self, "effects", accounting):
            for day in range(730):
                if day:
                    facts[("NAM", "numeric", "has_political_power")] += 0.25
                    fuel_key = ("NAM", "numeric", "has_fuel")
                    facts[fuel_key] = min(200000, facts[fuel_key] + 1000)
                if index < len(route) and due is not None and day == due:
                    name = route[index]
                    focus = self.postwar[name]
                    self.assertTrue(self.matches(block(focus, "available"), facts), (day, name))
                    for entry in focus:
                        if entry.key == "prerequisite":
                            self.assertTrue(any(facts.get(("NAM", "has_completed_focus", e.value)) for e in entry.value), name)
                        elif entry.key == "mutually_exclusive":
                            self.assertFalse(any(facts.get(("NAM", "has_completed_focus", e.value)) for e in entry.value), name)
                    facts[("NAM", "has_completed_focus", name)] = True
                    self.apply(block(focus, "completion_reward"), facts)
                    focus_days[name] = day
                    index += 1
                    due = None
                for name, delivery in list(pending.items()):
                    if day == delivery:
                        self.assertFalse(self.matches(block(self.decisions[name], "cancel_trigger"), facts), (day, name))
                        self.apply(block(self.decisions[name], "remove_effect"), facts)
                        finished[name] = day
                        del pending[name]
                for name in wanted:
                    if name in pending or name in finished:
                        continue
                    decision = self.decisions[name]
                    if all(self.matches(block(decision, key), facts) for key in ("visible", "available", "custom_cost_trigger")):
                        self.apply(block(decision, "complete_effect"), facts)
                        pending[name] = day + int(scalar(decision, "days_remove"))
                for key in (("NAM", "numeric", "has_political_power"), ("NAM", "numeric", "has_fuel"),
                            ("NAM", "variable", "ADISCORD_economy_treasury")):
                    self.assertGreaterEqual(facts[key], 0, (day, key, vertical, armed, export))
                if index < len(route) and due is None and self.matches(block(self.postwar[route[index]], "available"), facts):
                    due = day + int(scalar(self.postwar[route[index]], "cost")) * 7
                if len(finished) == len(wanted) and index == len(route):
                    return day, focus_days, finished, facts
        self.fail(("Unfinished postwar programme", vertical, armed, export, set(wanted) - finished.keys()))

    def test_postwar_eight_routes_fit_the_documented_budget_and_parallel_channels(self):
        triggers = parsed("common/scripted_triggers/ADISCORD_south_final_war_triggers.txt")
        readiness = block(triggers, "ADISCORD_south_nam_focus_ready")
        for vertical, armed, export in product((False, True), repeat=3):
            day, focus_days, finished, facts = self.run_postwar_budget(vertical, armed, export)
            self.assertTrue(self.matches(readiness, facts), (vertical, armed, export))
            self.assertEqual(focus_days["NAM_seal_registry" if vertical else "NAM_district_council"], 70)
            self.assertEqual(finished["NAM_district_audit" if vertical else "NAM_pw_district_congress"], 84)
            self.assertEqual(day, 665)
            for channel in ("civil", "military"):
                self.assertFalse(facts[("NAM", "has_country_flag", f"NAM_pw_{channel}_busy")])
            offensive = self.postwar["NAM_south_seal_over_furnaces" if vertical else "NAM_south_oil_charter"]
            for prerequisite in (e.value for e in offensive if e.key == "prerequisite"):
                self.assertTrue(any(facts.get(("NAM", "has_completed_focus", e.value)) for e in prerequisite))
            offensive_days = int(scalar(offensive, "cost")) * 7
            self.assertEqual(day + offensive_days, 707)
            warning = block(block(parsed(f"common/decisions/{BASE}_decisions.txt"), "ADISCORD_south_final_war_category"), "ADISCORD_south_preparation")
            self.assertLessEqual(offensive_days, int(scalar(warning, "days_mission_timeout")))
        self.assertEqual(scalar(block(triggers, "ADISCORD_south_final_war_enabled"), "always"), "yes")
        calendar = block(triggers, "ADISCORD_south_preparation_elapsed")
        self.assertEqual([e.value for e in calendar if not e.key], ["date", ">", "2164.12.31"])

    def test_compromise_cabinet_assigns_one_shipment_and_can_rebook_after_loss(self):
        reward = block(self.defeated["NAM_defeat_rump_cabinet"], "completion_reward")
        project = self.decisions[scalar(reward, "unlock_decision_tooltip")]
        sites = {"700": "industrial_complex", "228": "dockyard"}
        self.assertEqual({e.value for e in block(project, "targets")}, set(sites))
        self.assertEqual(scalar(project, "days_remove"), "35")
        pp = ("NAM", "numeric", "has_political_power")
        treasury = ("NAM", "variable", "ADISCORD_economy_treasury")
        stock = ("NAM", "has_country_flag", "NAM_cabinet_machine_tools_in_store")
        for destination, building in sites.items():
            order = self.bind_field(project, destination)
            other = self.bind_field(project, next(state for state in sites if state != destination))
            facts = self.independent_facts()
            facts[("fixture", "previous_state")] = destination
            facts[("NAM", "has_completed_focus", "NAM_defeat_rump_cabinet")] = True
            tree = ("NAM", "has_focus_tree", "NAM_defeated_focus")
            facts[tree] = True
            for state, kind in sites.items():
                facts[(state, "state", state)] = True
                facts[(state, "is_owned_by", "NAM")] = True
                facts[(state, "is_controlled_by", "NAM")] = True
                facts[(state, "variable", f"fixture_building_slots_{kind}_yes")] = 1
            facts[("NAM", "variable", "NAM_project_slots")] = 2
            facts[("NAM", "variable", "NAM_projects_in_progress")] = 0
            facts[pp], facts[treasury] = 25, 500
            self.apply(reward, facts)
            self.assertTrue(self.matches(block(order, "visible"), facts))
            self.assertTrue(self.matches(block(order, "available"), facts))
            for resource in (pp, treasury):
                short = dict(facts)
                short[resource] -= 0.01
                self.assertFalse(self.matches(block(order, "custom_cost_trigger"), short))
                unchanged = dict(short)
                self.apply(block(order, "complete_effect"), short)
                self.assertEqual(short, unchanged)
            self.apply(block(order, "complete_effect"), facts)
            self.assertEqual((facts[pp], facts[treasury]), (0, 0))
            self.assertEqual(facts[("NAM", "variable", "NAM_projects_in_progress")], 1)
            self.assertFalse(facts[stock])
            self.assertFalse(self.matches(block(other, "visible"), facts))
            facts[pp], facts[treasury] = 25, 500
            paid = dict(facts)
            self.apply(block(other, "complete_effect"), facts)
            self.apply(block(other, "cancel_effect"), facts)
            self.assertEqual(facts, paid)
            for unavailable in (None, (destination, "is_owned_by", "NAM"), (destination, "is_controlled_by", "NAM"),
                                (destination, "variable", f"fixture_building_slots_{building}_yes"),
                                ("NAM", "is_subject", "no"), ("NAM", "has_capitulated", "no"), tree):
                with self.subTest(destination=destination, unavailable=unavailable):
                    result = dict(paid)
                    if unavailable:
                        result[unavailable] = False
                    self.assertEqual(self.matches(block(order, "cancel_trigger"), result), bool(unavailable))
                    self.apply(block(order, "remove_effect"), result)
                    self.assertEqual(result.get((destination, "building", building), 0), int(not unavailable))
                    self.assertEqual((result[pp], result[treasury]), (50, 1000) if unavailable else (25, 500))
                    self.assertEqual(result[stock], bool(unavailable))
                    self.assertEqual(result[("NAM", "variable", "NAM_projects_in_progress")], 0)
                    settled = dict(result)
                    self.apply(block(order, "cancel_effect"), result)
                    self.apply(block(order, "remove_effect"), result)
                    self.assertEqual(result, settled)
                    if unavailable:
                        result[unavailable] = True
                        self.assertTrue(self.matches(block(other, "visible"), result))
                        self.apply(block(other, "complete_effect"), result)
                        self.assertFalse(result[stock])
                    else:
                        self.assertFalse(self.matches(block(order, "visible"), result))
            cancelled = dict(paid)
            self.apply(block(order, "cancel_effect"), cancelled)
            self.assertTrue(cancelled[stock])
            self.assertEqual((cancelled[pp], cancelled[treasury]), (50, 1000))

    def test_compromise_return_orders_consume_real_stocks_once_and_close_at_settlement(self):
        orders = {d.key: d.value for category in parsed(f"common/decisions/{BASE}_decisions.txt")
                  for d in category.value if d.key in {"NAM_return_charter_freighters", "NAM_return_commission_yard"}}
        freight = orders["NAM_return_charter_freighters"]
        yard = self.bind_field(orders["NAM_return_commission_yard"], "228")
        facts = self.independent_facts()
        facts.update({
            ("NAM", "has_global_flag", BASE + "_compromise"): True,
            ("NAM", "has_completed_focus", "NAM_defeat_revenge"): True,
            ("NAM", "has_completed_focus", "NAM_defeat_hidden_reserve"): True,
            ("NAM", "has_country_flag", "NAM_return_yard_warrant"): True,
            ("NAM", "ADISCORD_has_operational_naval_base", "yes"): True,
            ("NAM", "variable", "ADISCORD_economy_treasury"): 450,
            ("228", "is_owned_by", "NAM"): True,
            ("228", "is_controlled_by", "NAM"): True,
            ("228", "numeric", "naval_base"): 1,
            ("228", "variable", "fixture_building_slots_dockyard_yes"): 1,
        })
        for reserve, fuel, expected in ((False, 29999, 0), (False, 30000, 12), (True, 30000, 18)):
            current = {**facts, ("NAM", "has_completed_focus", "NAM_concealed_reserve"): reserve,
                       ("NAM", "numeric", "has_fuel"): fuel}
            self.apply(block(freight, "complete_effect"), current)
            self.assertEqual(current.get(("NAM", "equipment", "convoy"), 0), expected)
            self.assertEqual(current[("NAM", "numeric", "has_fuel")], 0 if expected else fuel)
        for key, value in ((("NAM", "variable", "ADISCORD_economy_treasury"), 449.9),
                           (("228", "is_controlled_by", "NAM"), False),
                           (("228", "numeric", "dockyard"), 20),
                           (("228", "variable", "fixture_building_slots_dockyard_yes"), 0),
                           (("NAM", "is_subject", "no"), False),
                           (("NAM", "has_completed_focus", "NAM_defeat_revenge"), False),
                           (("NAM", "has_global_flag", "NAM_war_of_return_resolved"), True),
                           (("NAM", "has_global_flag", BASE + "_island_exile"), True)):
            current = {**facts, key: value}
            self.apply(block(yard, "complete_effect"), current)
            self.assertTrue(current[("NAM", "has_country_flag", "NAM_return_yard_warrant")])
            self.assertEqual(current.get(("228", "building", "dockyard"), 0), 0)
        facts[("NAM", "has_global_flag", "NAM_war_of_return_started")] = True
        self.apply(block(yard, "complete_effect"), facts)
        self.assertEqual(facts[("NAM", "variable", "ADISCORD_economy_treasury")], 0)
        self.assertEqual(facts[("228", "building", "dockyard")], 1)
        self.assertEqual(facts[("NAM", "equipment", "artillery_equipment")], 100)
        facts[("NAM", "variable", "ADISCORD_economy_treasury")] = 450
        self.apply(block(yard, "complete_effect"), facts)
        self.assertEqual(facts[("NAM", "variable", "ADISCORD_economy_treasury")], 450)
        self.assertEqual(facts[("228", "building", "dockyard")], 1)
        self.assertEqual(facts[("NAM", "equipment", "artillery_equipment")], 100)

    def test_return_officers_report_each_current_owner_and_only_compromise_belligerents(self):
        survey = self.effects["NAM_return_survey_field_owners"]
        self.assertEqual([entry.key for entry in survey if entry.key.isdigit()], ["67", "688", "689", "690", "719", "700"])
        contact = self.effects["NAM_return_record_contact"]
        self.assertIn(("NAM_wor_field_held_by_rival", "yes"), [(e.key, e.value) for e in walk(contact)])
        owner = block(block(block(contact, "if"), "owner"), "if")
        seen = block(block(block(owner, "limit"), "NOT"), "is_in_array")
        self.assertEqual(scalar(seen, "array"), "NAM_return_contacts")
        self.assertEqual(scalar(seen, "value"), "THIS")
        self.assertEqual(scalar(block(owner, "add_to_temp_array"), "array"), "NAM_return_contacts")
        loop = block(survey, "for_each_scope_loop")
        self.assertEqual(scalar(loop, "array"), "NAM_return_contacts")
        self.assertEqual(scalar(block(block(loop, "NAM"), "add_intel"), "target"), "PREV")
        report = next(e.value for e in block(self.effects["NAM_war_of_return_start"], "if")
                      if e.key == "if" and any(x.key == "add_intel" for x in walk(e.value)))
        self.assertEqual(scalar(block(report, "limit"), "has_completed_focus"), "NAM_defeat_officer_cadres")
        self.assertEqual(scalar(block(block(report, "limit"), "check_variable"), "NAM_wor_start_exile"), "0")
        front = block(report, "for_each_scope_loop")
        self.assertEqual(scalar(front, "array"), "global.NAM_wor_participants")
        self.assertEqual(scalar(block(block(front, "NAM"), "add_intel"), "army_intel"), "20")

    def test_compromise_harbour_restores_convoy_service_without_the_prewar_focus(self):
        service = self.decisions["NAM_island_convoy_service"]
        reward = block(self.defeated["NAM_defeat_harbour_economy"], "completion_reward")
        for prewar in (True, False):
            facts = self.island_facts()
            facts[("NAM", "has_completed_focus", "NAM_harbour_service")] = prewar
            facts[("NAM", "has_completed_focus", "NAM_defeat_harbour_economy")] = False
            self.assertEqual(self.matches(block(service, "visible"), facts), prewar)
            shown = [e.value for _, e in selected_effects(self.expand(reward), facts, "NAM")
                     if e.key == "unlock_decision_tooltip"]
            self.assertEqual(shown, [] if prewar else ["NAM_island_convoy_service"])
            facts[("NAM", "has_completed_focus", "NAM_defeat_harbour_economy")] = True
            self.assertTrue(self.matches(block(service, "visible"), facts))
            self.assertTrue(self.matches(block(service, "available"), facts))
            self.apply(block(service, "complete_effect"), facts)
            self.assertEqual(facts[("NAM", "equipment", "convoy")], 8)
            self.assertEqual(facts[("NAM", "variable", "ADISCORD_economy_treasury")], 9850)

    def test_defeat_oil_union_unlocks_trade_without_the_prewar_bureau(self):
        reward = block(self.defeated["NAM_defeat_oil_union"], "completion_reward")
        offer = self.bind_field(self.decisions["NAM_oil_contract_offer"], "EFL")
        for bureau in (False, True):
            facts = self.independent_facts()
            facts[("NAM", "has_completed_focus", "NAM_supports_export_houses")] = False
            facts[("NAM", "has_completed_focus", "NAM_contract_bureau")] = bureau
            facts[("NAM", "has_completed_focus", "NAM_defeat_oil_union")] = False
            facts[("EFL", "tag", "EFL")] = True
            facts[("EFL", "exists", "yes")] = True
            facts[("EFL", "has_capitulated", "no")] = True
            facts[("NAM", "variable", "NAM_oil_free_land_units")] = 1
            facts[("NAM", "variable", "NAM_oil_free_units")] = 1
            self.assertEqual(self.matches(block(offer, "visible"), facts), bureau)
            shown = [entry.value for _, entry in selected_effects(self.expand(reward), facts, "NAM")
                     if entry.key == "unlock_decision_tooltip"]
            self.assertEqual(shown, [] if bureau else ["NAM_oil_contract_offer"])
            funds = facts[("NAM", "numeric", "has_political_power")]
            treasury = facts[("NAM", "variable", "ADISCORD_economy_treasury")]
            facts[("NAM", "variable", "NAM_oil_bonus_units")] = 0
            # Isolate the treaty capacity from retained-field output; field
            # condition, ownership and PREV accounting have separate scenarios.
            with patch.dict(self.effects, {"NAM_field_update_units": []}):
                self.apply(reward, facts)
            self.assertEqual(facts[("NAM", "variable", "NAM_oil_bonus_units")], 2)
            self.assertEqual(facts[("NAM", "numeric", "has_political_power")], funds + 50)
            self.assertEqual(facts[("NAM", "variable", "ADISCORD_economy_treasury")], treasury + 250)
            facts[("NAM", "has_completed_focus", "NAM_defeat_oil_union")] = True
            self.assertTrue(self.matches(block(offer, "visible"), facts))
            self.assertTrue(self.matches(block(offer, "available"), facts))

    def test_postwar_border_choice_has_two_material_routes_and_keeps_the_archive(self):
        retired = {"NAM_aftermath_commission", "NAM_prisoner_exchange", "NAM_border_trade_posts",
                   "NAM_frontier_bunkers", "NAM_border_incidents", "NAM_aftermath_settled"}
        self.assertFalse(retired & self.postwar.keys())
        for name, other in (("NAM_normalisation", "NAM_border_revenge"), ("NAM_border_revenge", "NAM_normalisation")):
            focus = self.postwar[name]
            self.assertEqual(scalar(block(focus, "prerequisite"), "focus"), "NAM_law_after_war")
            self.assertEqual(scalar(block(focus, "mutually_exclusive"), "focus"), other)
            self.assertEqual(int(scalar(focus, "cost")) * 7, 35)
            reward = block(focus, "completion_reward")
            self.assertEqual(scalar(block(reward, "country_event"), "id"), "ADISCORD_nam_archive.6")
        trade = block(self.postwar["NAM_normalisation"], "completion_reward")
        self.assertEqual(scalar(trade, "add_manpower"), "4000")
        capacity = [e.value for e in walk(trade) if e.key == "add_to_variable" and scalar(e.value, "var") == "NAM_oil_bonus_units"]
        self.assertEqual([scalar(e, "value") for e in capacity], ["1"])
        arms = block(self.postwar["NAM_border_revenge"], "completion_reward")
        self.assertEqual(scalar(arms, "army_experience"), "20")
        self.assertEqual(scalar(block(arms, "add_equipment_to_stockpile"), "amount"), "80")
        self.assertIn("NAM_prepare_line", [e.value for e in walk(arms) if e.key == "unlock_decision_tooltip"])
        self.assertFalse(any(e.key == "add_claim_by" for e in walk(arms)))
        for selected in ("NAM_normalisation", "NAM_border_revenge"):
            facts = self.independent_facts()
            facts[("NAM", "has_completed_focus", "NAM_supports_export_houses")] = False
            facts[("NAM", "has_completed_focus", "NAM_contract_bureau")] = False
            facts[("NAM", "has_completed_focus", selected)] = True
            self.assertEqual(self.matches(self.triggers["NAM_oil_trade_authorized"], facts), selected == "NAM_normalisation")
            self.assertFalse(self.matches(block(self.decisions["NAM_pw_export_shipment"], "visible"), facts))

    def test_deterrence_opens_paid_lines_after_peace_without_unlocking_forward_depots(self):
        category = block(parsed(f"common/decisions/{BASE}_decisions.txt"), "NAM_mobilisation")
        raw = block(category, "NAM_prepare_line")
        self.assertEqual({e.value for e in block(raw, "targets")}, {"67", "688", "689", "690", "719", "700", "701", "720", "721", "722", "723", "727"})
        for state in ("67", "720"):
            for loss in (None, "is_owned_by", "is_controlled_by"):
                decision = self.bind_field(raw, state)
                _, facts = self.ordinary_line_fixture()
                facts[("NAM", "has_global_flag", BASE + "_scheduled")] = False
                facts[("NAM", "has_global_flag", BASE + "_started")] = False
                facts[("NAM", "has_global_flag", BASE + "_resolved")] = True
                facts[("NAM", "has_completed_focus", "NAM_line_survey")] = False
                facts[("NAM", "has_completed_focus", "NAM_border_revenge")] = True
                facts[(state, "is_owned_by", "NAM")] = True
                facts[(state, "is_controlled_by", "NAM")] = True
                facts[(state, "has_state_flag", "NAM_line_prepared")] = False
                facts[(state, "fixture_foreign_land_border", "yes")] = True
                self.assertTrue(self.matches(block(decision, "visible"), facts))
                self.assertTrue(self.matches(block(decision, "available"), facts))
                self.assertFalse(self.matches(block(self.bind_field(self.decisions["NAM_mil_forward_supply"]), "visible"), facts))
                self.apply(block(decision, "complete_effect"), facts)
                self.assertEqual(facts[("NAM", "numeric", "has_political_power")], 970)
                self.assertEqual(facts[("NAM", "variable", "ADISCORD_economy_treasury")], 9900)
                if loss:
                    facts[(state, loss, "NAM")] = False
                self.apply(block(decision, "remove_effect"), facts)
                self.assertEqual(facts.get((state, "building", "bunker"), 0), 0 if loss else 2)
                self.assertEqual(facts[("NAM", "variable", "ADISCORD_economy_treasury")], 10000 if loss else 9900)
                self.assertEqual(facts[("NAM", "variable", "NAM_lines_in_progress")], 0)
                settled = dict(facts)
                self.apply(block(decision, "remove_effect"), facts)
                self.apply(block(decision, "cancel_effect"), facts)
                self.assertEqual(facts, settled)

    def test_oil_peace_exports_work_after_compromise_and_refund_subjugation(self):
        decision = self.decisions["NAM_pw_export_shipment"]
        for interrupted in (False, True):
            facts = self.postwar_facts()
            facts[("NAM", "numeric", "has_fuel")] = 60000
            facts[("NAM", "has_global_flag", BASE + "_nam_victory")] = False
            facts[("NAM", "has_global_flag", BASE + "_compromise")] = True
            facts[("NAM", "has_completed_focus", "NAM_export_consortium")] = False
            facts[("NAM", "has_completed_focus", "NAM_defeat_oil_peace")] = True
            self.assertTrue(self.matches(block(decision, "visible"), facts))
            self.assertTrue(self.matches(block(decision, "available"), facts))
            pp = facts[("NAM", "numeric", "has_political_power")]
            fuel = facts[("NAM", "numeric", "has_fuel")]
            treasury = facts[("NAM", "variable", "ADISCORD_economy_treasury")]
            self.apply(block(decision, "complete_effect"), facts)
            self.assertEqual(facts[("NAM", "numeric", "has_political_power")], pp - 25)
            self.assertEqual(facts[("NAM", "numeric", "has_fuel")], fuel - 60000)
            if interrupted:
                facts[("NAM", "is_subject", "no")] = False
            self.apply(block(decision, "remove_effect"), facts)
            self.assertEqual(facts[("NAM", "variable", "ADISCORD_economy_treasury")], treasury + (0 if interrupted else 450))
            self.assertEqual(facts[("NAM", "numeric", "has_political_power")], pp if interrupted else pp - 25)
            self.assertEqual(facts[("NAM", "numeric", "has_fuel")], fuel if interrupted else fuel - 60000)
            settled = dict(facts)
            self.apply(block(decision, "remove_effect"), facts)
            self.apply(block(decision, "cancel_effect"), facts)
            self.assertEqual(facts, settled)

    def test_postwar_ai_can_finish_its_offensive_during_the_warning(self):
        plans = parsed("common/ai_strategy_plans/ADISCORD_NAM_plans.txt")
        triggers = parsed("common/scripted_triggers/ADISCORD_south_final_war_triggers.txt")
        readiness = block(triggers, "ADISCORD_south_nam_focus_ready")
        category = block(parsed(f"common/decisions/{BASE}_decisions.txt"), "ADISCORD_south_final_war_category")
        warning_days = int(scalar(block(category, "ADISCORD_south_preparation"), "days_mission_timeout"))
        for plan_name, tree, offensive in (
            ("NAM_postwar_plan", self.postwar, "NAM_south_oil_charter"),
            ("NAM_postwar_vertical_plan", self.postwar, "NAM_south_seal_over_furnaces"),
        ):
            with self.subTest(plan=plan_name):
                facts = self.postwar_facts()
                for name in (*self.focuses, *self.postwar, *self.defeated):
                    facts[("NAM", "has_completed_focus", name)] = False
                day = 0
                ready_day = None
                for entry in block(block(plans, plan_name), "ai_national_focuses"):
                    name = entry.value
                    for prerequisite in (entry.value for entry in tree[name] if entry.key == "prerequisite"):
                        self.assertTrue(any(facts.get(("NAM", "has_completed_focus", child.value), False)
                                            for child in prerequisite), name)
                    day += int(scalar(tree[name], "cost")) * 7
                    facts[("NAM", "has_completed_focus", name)] = True
                    if ready_day is None and self.matches(readiness, facts):
                        ready_day = day
                    if name == offensive:
                        self.assertIsNotNone(ready_day)
                        self.assertLessEqual(day - ready_day, warning_days)
                        break
                else:
                    self.fail(f"Missing offensive focus in {plan_name}")

    def test_defeated_ai_prepares_defence_and_chooses_economic_course(self):
        plans = parsed("common/ai_strategy_plans/ADISCORD_NAM_plans.txt")
        names = [entry.value for entry in block(block(plans, "NAM_defeated_plan"), "ai_national_focuses")]
        completed = set()
        for name in names:
            for prerequisite in (entry.value for entry in self.defeated[name] if entry.key == "prerequisite"):
                self.assertTrue(any(child.value in completed for child in prerequisite), name)
            for exclusive in (entry.value for entry in self.defeated[name] if entry.key == "mutually_exclusive"):
                self.assertFalse(any(child.value in completed for child in exclusive), name)
            completed.add(name)
        self.assertIn("NAM_defeat_road_south", completed)
        self.assertIn("NAM_defeat_oil_peace", completed)
        self.assertNotIn("NAM_defeat_southern_charter", completed)

    def test_postwar_localisation_prices_and_runtime_encodings(self):
        for language in ("russian", "english"):
            path = ROOT / f"localisation/{language}/{BASE}_l_{language}.yml"
            self.assertTrue(path.read_bytes().startswith(b"\xef\xbb\xbf"))
            values = dict(re.findall(r'^ ([A-Za-z0-9_]+):(?:\d+)? "([^"\r\n]*)"\s*$',
                                     path.read_text(encoding="utf-8-sig"), re.MULTILINE))
            for name, (pp, money, fuel, days, channel) in self.POSTWAR_ORDERS.items():
                for suffix in ("", "_desc", "_ready_tt", "_result_tt", "_cost", "_cost_blocked", "_cost_tooltip"):
                    self.assertIn(name + suffix, values)
                    self.assertNotIn("\ufffd", values[name + suffix])
                for amount, icon in ((pp, "political_power_texticon"), (money, "ADISCORD_economy_treasury_texticon"),
                                     (fuel, "fuel_texticon")):
                    if amount:
                        for suffix in ("_cost", "_cost_blocked", "_cost_tooltip"):
                            self.assertRegex(values[name + suffix], rf"{amount}§! £{icon}")
                self.assertEqual(scalar(self.decisions[name], "days_remove"), str(days))
                self.assertIn(name + "_result_tt", [
                    e.value for e in walk(block(self.decisions[name], "remove_effect"))
                    if e.key == "custom_effect_tooltip"
                ])
            self.assertIn("$STATE_700$", values["NAM_veteran_housing_result_tt"])
            self.assertIn("$STATE_688$", values["NAM_pw_district_cooperative_result_tt"])
        for kind in ("decisions", "scripted_effects", "scripted_triggers"):
            path = ROOT / f"common/{kind}/{BASE}_{kind.removeprefix('scripted_')}.txt"
            self.assertFalse(path.read_bytes().startswith(b"\xef\xbb\xbf"), path)

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

    def test_completed_inventory_chains_memory_to_payroll(self):
        focus = self.focuses["NAM_inventory"]
        self.assertNotIn("select_effect", [entry.key for entry in focus])
        memory = self.events[BASE + ".109"]
        self.assertEqual(scalar(memory, "fire_only_once"), "yes")
        self.assertGreater(float(scalar(memory, "timeout_days")), 0)
        options = [entry.value for entry in memory if entry.key == "option"]
        self.assertEqual(len(options), 1)
        continuation = block(options[0], "hidden_effect")
        self.assertEqual([entry.key for entry in continuation], ["country_event"])
        self.assertEqual(scalar(block(continuation, "country_event"), "id"), BASE + ".10")
        self.assertNotIn("immediate", [entry.key for entry in memory])
        reward = block(focus, "completion_reward")
        self.assertEqual(scalar(reward, "add_political_power"), "35")
        self.assertEqual(scalar(block(reward, "country_event"), "id"), BASE + ".109")
        self.assertEqual(scalar(block(reward, "country_event"), "hours"), "1")

    def test_intro_uses_the_actual_collapse_phase(self):
        descriptions = [e.value for e in self.events[BASE + ".10"] if e.key == "desc"]
        for collapsed in (False, True):
            facts = self.facts()
            facts[("NAM", "has_global_flag", "ADISCORD_vorkerland_collapse_wars_started")] = collapsed
            shown = [scalar(d, "text") for d in descriptions if self.matches(block(d, "trigger"), facts)]
            self.assertEqual(shown, [BASE + (".10.d" if collapsed else ".10.before")])

    def test_rom_story_uses_current_ruler_and_actual_peace_terms(self):
        event_ids = [f"{BASE}.{number}" for number in (11, 12, 13, 20, 21, 70, 80)]
        event_ids.append("ADISCORD_nam_groups.12")
        for event_id, leader, recognised in product(
            event_ids, ("NAM_Egor_Rom", "another_leader"), (False, True)
        ):
            with self.subTest(event=event_id, leader=leader, recognised=recognised):
                facts = self.facts()
                facts[("NAM", "ruling_leader")] = leader
                facts[("NAM", "has_country_flag", "NAM_treaty_independence_recognised")] = recognised
                descriptions = [entry.value for entry in self.events[event_id] if entry.key == "desc"]
                shown = [scalar(desc, "text") for desc in descriptions if self.matches(block(desc, "trigger"), facts)]
                suffix = ".d_standoff" if event_id == BASE + ".12" and not recognised else ".d"
                if leader != "NAM_Egor_Rom":
                    suffix += "_successor"
                self.assertEqual(shown, [event_id + suffix])
                if event_id == BASE + ".70":
                    titles = [entry.value for entry in self.events[event_id] if entry.key == "title"]
                    shown_titles = [scalar(title, "text") for title in titles if self.matches(block(title, "trigger"), facts)]
                    self.assertEqual(shown_titles, [event_id + (".t" if leader == "NAM_Egor_Rom" else ".t_successor")])

    def test_mission_never_succeeds_automatically_and_all_treaties_clean_up(self):
        mission = self.decisions["NAM_defend_fields"]
        self.assertFalse(self.matches(block(mission, "available"), self.facts()))
        self.assertEqual(scalar(mission, "days_mission_timeout"), "420")
        timeout = block(mission, "timeout_effect")
        self.assertEqual([entry.key for entry in timeout], ["custom_effect_tooltip"])
        self.assertEqual(scalar(timeout, "custom_effect_tooltip"), "NAM_defend_fields_resolution_tt")
        for outcome in ("resolve_nam_victory", "resolve_coalition_victory", "resolve_compromise", "resolve_standoff"):
            self.assertIn(BASE + "_clear_temporary_support", [e.key for e in walk(self.effects[BASE + "_" + outcome])])
        self.assertIn("NAM_close_war_programmes", [e.key for e in walk(self.effects[BASE + "_clear_temporary_support"])])
        cleanup = self.effects["NAM_close_war_programmes"]
        self.assertIn("NAM_defend_fields", [e.value for e in cleanup if e.key == "remove_mission"])
        self.assertEqual({e.value for e in cleanup if e.key == "remove_ideas"}, {
            "NAM_wartime_entrenchment", "NAM_counterstroke_staff", "NAM_rebel_depot_maps",
            "NAM_war_depot_network_idea", "NAM_war_mobile_workshops_idea",
            "NAM_war_factory_shifts_idea", "NAM_war_convoy_escort_idea",
            "NAM_war_interceptor_control_idea", "NAM_war_air_ground_liaison_idea",
            "NAM_war_joint_operations_idea",
            "NAM_war_short_training_idea", "NAM_war_veteran_cadres_idea",
            "NAM_war_fuel_discipline_idea", "NAM_war_extraction_surge_idea",
        })

    def test_border_archive_does_not_invent_recognition_after_standoff(self):
        event_id = "ADISCORD_nam_archive.6"
        descriptions = [entry.value for entry in self.events[event_id] if entry.key == "desc"]
        for recognised in (False, True):
            facts = self.facts()
            facts[("NAM", "has_country_flag", "NAM_treaty_independence_recognised")] = recognised
            shown = [scalar(desc, "text") for desc in descriptions if self.matches(block(desc, "trigger"), facts)]
            self.assertEqual(shown, [event_id + (".d" if recognised else ".d_standoff")])

    def test_memoir_pages_keep_full_exit_and_no_gameplay_settlement(self):
        for chapter in range(1, 6):
            first = self.events[f"ADISCORD_nam_memoir.{chapter}"]
            last = self.events[f"ADISCORD_nam_memoir.{chapter + 10}"]
            first_options = [entry.value for entry in first if entry.key == "option"]
            last_options = [entry.value for entry in last if entry.key == "option"]
            exit_options = [option for option in first_options if scalar(option, "name") == "ADISCORD_nam_memoir.put_away"]
            self.assertEqual(len(exit_options), 1)
            self.assertEqual([entry.key for entry in exit_options[0]], ["name"])
            self.assertEqual(len(last_options), 1)
            self.assertEqual([entry.key for entry in last_options[0]], ["name"])
            self.assertNotIn("immediate", [entry.key for entry in first + last])
            continuation = next(option for option in first_options if scalar(option, "name") == "ADISCORD_nam_memoir.read_on")
            effects = block(continuation, "hidden_effect")
            self.assertEqual([entry.key for entry in effects], ["country_event"])
            self.assertEqual(scalar(block(effects, "country_event"), "id"), f"ADISCORD_nam_memoir.{chapter + 10}")

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
            story_ids = [f"{BASE}.{number}" for number in (10, 11, 12, 13, 20, 21, 70, 80, 109)]
            story_ids.append("ADISCORD_nam_groups.12")
            story_ids.extend(f"ADISCORD_nam_memoir.{number}" for number in (*range(1, 6), *range(11, 16)))
            story_ids.extend(f"ADISCORD_nam_archive.{number}" for number in range(1, 7))
            for event_id in story_ids:
                descriptions = [e.value for e in self.events[event_id] if e.key == "desc"]
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
                bookkeeping = block(block(idea, hook), "hidden_effect")
                self.assertEqual(scalar(bookkeeping, "ADISCORD_economy_mark_dirty"), "yes", name)
        hooks = read("common/on_actions/03_ADISCORD_nam_resource_war_on_actions.txt")
        self.assertNotIn("on_daily", hooks)
        self.assertNotIn("every_country", hooks)


    def test_humanist_land_programmes_require_real_home_districts_and_rejoin(self):
        paths = {"NAM_municipal_land": "NAM_pw_municipal_workshop", "NAM_tenant_councils": "NAM_pw_tenant_petition"}
        self.assertEqual({e.value for e in block(self.postwar["NAM_water_boards"], "prerequisite")}, set(paths))
        for focus, decision in paths.items():
            body = self.postwar[focus]
            self.assertEqual(scalar(block(body, "mutually_exclusive"), "focus"), next(f for f in paths if f != focus))
            self.assertEqual({scalar(e.value, "focus") for e in body if e.key == "prerequisite"},
                             {"NAM_rural_grid", "NAM_returnee_offices"})
            self.assertEqual(scalar(block(body, "completion_reward"), "unlock_decision_tooltip"), decision)
            order = self.decisions[decision]
            self.assertEqual({e.value for e in block(order, "targets")}, {"67", "688", "689", "690", "700", "719"})
            facts = self.postwar_facts()
            for completed in (True, False):
                facts[("NAM", "has_completed_focus", focus)] = completed
                self.assertEqual(self.matches(self.bind_field(block(order, "visible"), "719"), facts), completed)

    def test_humanist_land_lease_reserves_factories_and_settles_one_construction_site(self):
        order = self.bind_field(self.decisions["NAM_pw_municipal_workshop"], "719")
        self.assertEqual(scalar(order, "days_remove"), "49")
        self.assertEqual(scalar(block(order, "modifier"), "civilian_factory_use"), "3")
        capacity = ("719", "variable", "fixture_building_slots_industrial_complex_yes")
        count = ("NAM", "variable", "NAM_projects_in_progress")
        for outcome in ("finish", "occupied", "subject", "full", "capped", "cancel"):
            with self.subTest(outcome=outcome):
                facts = self.postwar_facts()
                facts[capacity] = 2
                for factories in (2, 3):
                    facts[("NAM", "numeric", "num_of_civilian_factories_available_for_projects")] = factories
                    self.assertEqual(self.matches(block(order, "available"), facts), factories == 3)
                for _ in range(2):
                    self.apply(block(order, "complete_effect"), facts)
                self.assertEqual(facts[count], 1)
                self.assertFalse(self.matches(block(order, "available"), facts))
                if outcome == "occupied":
                    facts[("719", "is_controlled_by", "NAM")] = False
                elif outcome == "subject":
                    facts[("NAM", "is_subject", "no")] = False
                elif outcome == "full":
                    facts[capacity] = 1
                elif outcome == "capped":
                    facts[("719", "numeric", "industrial_complex")] = 20
                self.assertEqual(self.matches(block(order, "cancel_trigger"), facts), outcome not in ("finish", "cancel"))
                if outcome == "cancel":
                    self.apply(block(order, "cancel_effect"), facts)
                for callback in ("remove_effect", "cancel_effect", "remove_effect"):
                    self.apply(block(order, callback), facts)
                self.assertEqual(facts[count], 0)
                self.assertEqual(facts.get(("719", "building", "industrial_complex"), 0), int(outcome == "finish"))
                self.assertEqual(facts.get(("719", "reward", "building_slots"), 0), 2 if outcome == "finish" else 0)
                if outcome == "finish":
                    self.assertFalse(self.matches(block(order, "visible"), facts))

    def test_humanist_land_petition_uses_one_paid_congress_and_the_selected_district(self):
        congress = self.decisions["NAM_pw_district_congress"]
        petition = self.decisions["NAM_pw_tenant_petition"]
        order = self.bind_field(petition, "690")
        depot = "NAM_tenant_supply_depot"
        definition = block(parsed("common/dynamic_modifiers/ADISCORD_dynamic_modifiers_NAM.txt"), depot)
        self.assertEqual(float(scalar(definition, "local_supplies")), 1)
        self.assertEqual(float(scalar(definition, "state_repair_speed_infrastructure_factor")), 0.25)
        grants = [e.value for e in walk(self.effects["NAM_pw_district_congress_settle"])
                  if e.key == "add_dynamic_modifier" and scalar(e.value, "modifier") == depot]
        self.assertEqual([scalar(m, "days") for m in grants], ["90"])
        for outcome in ("funded", "roads_at_cap", "occupied", "transferred", "subject", "cancelled"):
            with self.subTest(outcome=outcome):
                facts = self.postwar_facts()
                facts[("690", "numeric", "infrastructure")] = 5 if outcome == "roads_at_cap" else 4
                facts[("NAM", "has_completed_focus", "NAM_workers_inspection")] = False
                self.assertFalse(self.matches(block(order, "available"), facts))
                old_trust = facts[("NAM", "variable", "NAM_grp_dist_support")]
                self.apply(block(congress, "complete_effect"), facts)
                self.assertTrue(self.matches(block(order, "available"), facts))
                self.apply(block(order, "complete_effect"), facts)
                self.assertFalse(self.matches(block(order, "available"), facts))
                self.apply(self.bind_field(block(petition, "complete_effect"), "719"), facts)
                self.assertEqual(facts[("event_target", "NAM_tenant_petition_site")], "690")
                if outcome == "occupied":
                    facts[("690", "is_controlled_by", "NAM")] = False
                elif outcome == "transferred":
                    facts[("690", "is_owned_by", "NAM")] = False
                elif outcome == "subject":
                    facts[("NAM", "is_subject", "no")] = False
                elif outcome == "cancelled":
                    self.apply(block(congress, "cancel_effect"), facts)
                for _ in range(2):
                    self.apply(block(congress, "remove_effect"), facts)
                self.assertNotIn(("event_target", "NAM_tenant_petition_site"), facts)
                self.assertEqual(facts.get(("690", "building", "infrastructure"), 0), int(outcome == "funded"))
                self.assertEqual(facts.get(("690", "has_dynamic_modifier", depot), False),
                                 outcome in ("funded", "roads_at_cap"))
                self.assertFalse(facts.get(("719", "has_dynamic_modifier", depot), False))
                self.assertEqual(facts[("NAM", "variable", "NAM_grp_dist_support")] - old_trust,
                                 0 if outcome in ("subject", "cancelled") else 10)

    def test_workers_inspection_restarts_only_available_fields_at_a_paid_congress(self):
        focus = self.postwar["NAM_workers_inspection"]
        congress = self.decisions["NAM_pw_district_congress"]
        facts = self.postwar_facts()
        key = "NAM_field_condition"
        inspector = ("NAM", "has_completed_focus", "NAM_workers_inspection")
        facts[inspector] = False
        for state, condition in (("67", 32), ("688", 12), ("689", 4), ("690", 60), ("719", 95)):
            facts[(state, "variable", key)] = condition
        facts[("688", "has_state_flag", "NAM_project_in_progress")] = True
        facts[("688", "variable", "NAM_project_deposit")] = 150
        facts[("689", "has_state_flag", "NAM_wells_scorched")] = True
        facts[("690", "is_controlled_by", "NAM")] = False
        refreshes = ("NAM", "variable", "fixture_oil_refreshes")
        refresh = parse_clausewitz("add_to_variable = { var = fixture_oil_refreshes value = 1 }")
        with patch.dict(self.effects, {"NAM_oil_refresh": refresh}):
            self.apply(block(congress, "complete_effect"), facts)
            self.apply(block(congress, "remove_effect"), facts)
            self.assertEqual(facts[("67", "variable", key)], 32)
            self.apply(block(focus, "completion_reward"), facts)
            self.assertEqual([facts[(s, "variable", key)] for s in ("67", "688", "689", "690", "719")],
                             [80, 12, 4, 60, 95])
            self.assertEqual(facts[("688", "variable", "NAM_project_deposit")], 150)
            self.assertEqual(facts[refreshes], 1)

            facts[inspector] = True
            facts[("690", "is_controlled_by", "NAM")] = True
            self.apply(block(congress, "complete_effect"), facts)
            facts[("67", "variable", key)] = 10
            facts[("67", "is_owned_by", "NAM")] = False
            self.apply(block(congress, "remove_effect"), facts)
            self.assertEqual(facts[("690", "variable", key)], 80)
            self.assertEqual(facts[("67", "variable", key)], 10)
            self.assertEqual(facts[refreshes], 2)
            facts[("67", "is_owned_by", "NAM")] = True
            self.apply(block(congress, "remove_effect"), facts)
            self.assertEqual(facts[("67", "variable", key)], 10)
            self.assertEqual(facts[refreshes], 2)

    def test_regional_university_teaches_one_unresearched_stage_per_paid_intake(self):
        school = self.decisions["NAM_pw_district_schools"]
        focus = self.postwar["NAM_regional_university"]
        curriculum = ("field_workshop_tools", "casualty_evacuation", "battlefield_medical_drones",
                      "trauma_registry_networks")
        keys = [("NAM", "has_tech", "ADISCORD_tech_" + stage) for stage in curriculum]
        techs = block(parsed("common/technologies/ADISCORD_logistics_trains.txt"), "technologies")
        for i, key in enumerate(keys):
            tech = block(techs, key[2])
            if i == 1:
                self.assertEqual(scalar(block(tech, "dependencies"), keys[0][2]), "1")
                self.assertIn("field_hospital", [e.value for e in block(tech, "enable_subunits")])
            if i in (1, 2):
                self.assertEqual(scalar(block(tech, "path"), "leads_to_tech"), keys[i + 1][2])
        for known in (0, 1, 3, 4):
            facts = self.postwar_facts()
            focus_key = ("NAM", "has_completed_focus", "NAM_regional_university")
            for name in ("NAM_regional_university", "NAM_oil_fund", "NAM_relief_register", "NAM_pw_southern_schools"):
                facts[("NAM", "has_completed_focus", name)] = False
            for i, key in enumerate(keys):
                facts[key] = i < known
            self.assertFalse(self.matches(block(school, "visible"), facts))
            self.apply(block(focus, "completion_reward"), facts)
            facts[focus_key] = True
            studied = min(known + 1, len(keys))
            self.assertEqual([facts[k] for k in keys], [i < studied for i in range(len(keys))])
            self.assertTrue(self.matches(block(school, "visible"), facts))
            self.apply(block(school, "complete_effect"), facts)
            self.apply(block(school, "cancel_effect"), facts)
            self.apply(block(school, "remove_effect"), facts)
            self.assertEqual(sum(facts[k] for k in keys), studied)
            for count in range(studied, len(keys) + 1):
                self.apply(block(school, "complete_effect"), facts)
                self.apply(block(school, "remove_effect"), facts)
                self.apply(block(school, "remove_effect"), facts)
                self.assertEqual([facts[k] for k in keys], [i <= count for i in range(len(keys))])

    def test_humanist_institutions_remain_reachable_from_each_district_policy(self):
        for service, land in product(("NAM_public_utilities", "NAM_municipal_services"),
                                     ("NAM_municipal_land", "NAM_tenant_councils")):
            completed = reachable(self.postwar, {service, land, "NAM_oil_fund", "NAM_relief_register"})
            self.assertTrue({"NAM_district_council", "NAM_workers_inspection", "NAM_regional_university"}
                            <= completed)
        for prerequisite in ("NAM_water_boards", "NAM_district_scholarships"):
            self.assertNotIn("NAM_regional_university", reachable(self.postwar, {prerequisite}))


    def test_returnee_offices_and_common_citizenship_place_each_family_once(self):
        offices = block(self.postwar["NAM_returnee_offices"], "completion_reward")
        final = block(self.postwar["NAM_common_citizenship"], "completion_reward")
        self.assertIn("NAM_house_returnees", [e.value for e in offices if e.key == "unlock_decision_tooltip"])
        balance = ("NAM", "variable", "NAM_returnee_register")
        facts = self.postwar_facts()
        facts.update({("NAM", "numeric", "has_manpower"): 0,
                      ("NAM", "has_completed_focus", "NAM_common_citizenship"): False})
        self.apply(offices, facts)
        self.assertEqual((facts[("NAM", "numeric", "has_manpower")], facts[balance]), (4000, 4000))
        for state in ("67", "688", "700", "720", "721"):
            facts[(state, "is_owned_by", "NAM")] = True
            facts[(state, "is_controlled_by", "NAM")] = True
        def place(state):
            order = self.bind_field(self.decisions["NAM_house_returnees"], state)
            self.apply(block(order, "complete_effect"), facts)
        place("720")
        place("67")
        place("67")
        place("688")
        place("700")
        self.assertEqual(facts[balance], 0)
        self.assertEqual([facts.get((s, "numeric", "has_manpower"), 0) for s in ("67", "688", "700", "720")],
                         [2000, 2000, 0, 0])
        self.apply(final, facts)
        facts[("NAM", "has_completed_focus", "NAM_common_citizenship")] = True
        self.assertEqual(facts[balance], 4000)
        facts[("720", "is_controlled_by", "NAM")] = False
        place("720")
        self.assertEqual(facts[balance], 4000)
        facts[("720", "is_controlled_by", "NAM")] = True
        place("720")
        place("700")
        place("721")
        self.assertEqual(facts[balance], 0)
        self.assertEqual([facts.get((s, "numeric", "has_manpower"), 0) for s in ("700", "720", "721")],
                         [2000, 2000, 0])
        self.assertFalse(facts.get(("720", "is_core_of", "NAM")))

    def test_audited_city_contracts_service_early_settlements_and_respect_lost_or_full_sites(self):
        for programme, asset, qty in (("public_utilities", "motorized_equipment", 30),
                                      ("municipal_services", "support_equipment", 60)):
            order = self.decisions["NAM_pw_" + programme]
            for before in (False, True):
                facts = self.postwar_facts()
                facts.update({("fixture", "returnee_sites"): ("67", "688", "689"),
                              ("NAM", "has_completed_focus", "NAM_returnee_offices"): True,
                              ("NAM", "has_completed_focus", "NAM_civic_audit"): before,
                              ("NAM", "has_completed_focus", "NAM_" + programme): True,
                              ("NAM", "variable", "NAM_returnee_register"): 6000,
                              ("NAM", "has_idea", "NAM_pw_" + programme + "_idea"): False})
                for state in ("67", "688", "689"):
                    facts[(state, "is_owned_by", "NAM")] = True
                    facts[(state, "is_controlled_by", "NAM")] = True
                    facts[(state, "numeric", "infrastructure")] = 3 if state != "688" else 5
                    facts[(state, "variable", "fixture_building_slots_industrial_complex_no")] = int(state != "688")
                for state in ("67", "689"):
                    self.apply(block(self.bind_field(self.decisions["NAM_house_returnees"], state), "complete_effect"), facts)
                facts[("689", "is_controlled_by", "NAM")] = False
                self.apply(block(order, "complete_effect"), facts)
                self.apply(block(order, "remove_effect"), facts)
                if not before:
                    self.assertEqual(facts[("67", "variable", "NAM_returnee_settlement")], 1)
                    self.apply(block(self.postwar["NAM_civic_audit"], "completion_reward"), facts)
                self.assertEqual(facts[("67", "variable", "NAM_returnee_settlement")], 2)
                self.assertEqual(facts[("689", "variable", "NAM_returnee_settlement")], 1)
                kind = "infrastructure" if programme == "public_utilities" else "industrial_complex"
                self.assertEqual(facts[("67", "building", kind)], 1)
                self.apply(block(self.bind_field(self.decisions["NAM_house_returnees"], "688"), "complete_effect"), facts)
                self.assertEqual(facts[("NAM", "equipment", asset)], qty)
                self.apply(self.effects["NAM_returnee_audit_rolls"], facts)
                self.assertEqual(facts[("NAM", "equipment", asset)], qty)
                self.assertEqual(facts[("67", "building", kind)], 1)
                facts[("689", "is_controlled_by", "NAM")] = True
                self.apply(self.effects["NAM_returnee_audit_rolls"], facts)
                self.assertEqual(facts[("689", "building", kind)], 1)

    def test_cancelled_city_work_leaves_the_returnee_claim_and_contract_price_intact(self):
        for programme in ("public_utilities", "municipal_services"):
            order = self.decisions["NAM_pw_" + programme]
            state = "690"
            money = ("NAM", "variable", "ADISCORD_economy_treasury")
            pp = ("NAM", "numeric", "has_political_power")
            balance = ("NAM", "variable", "NAM_returnee_register")
            claim = (state, "variable", "NAM_returnee_settlement")
            works = (state, "has_state_flag", "NAM_project_in_progress")
            facts = self.postwar_facts()
            facts.update({("fixture", "returnee_sites"): (state,), ("NAM", "has_completed_focus", "NAM_" + programme): True,
                          ("NAM", "has_completed_focus", "NAM_returnee_offices"): True, balance: 2000,
                          (state, "is_owned_by", "NAM"): True, (state, "is_controlled_by", "NAM"): True, works: True})
            place = self.bind_field(self.decisions["NAM_house_returnees"], state)
            self.apply(block(place, "complete_effect"), facts)
            self.assertEqual(facts[balance], 2000)
            facts[works] = False
            self.apply(block(place, "complete_effect"), facts)
            self.assertEqual((facts[balance], facts[claim]), (0, 1))
            cost = facts[money], facts[pp]
            self.apply(block(order, "complete_effect"), facts)
            self.assertLess(facts[money], cost[0])
            self.assertLess(facts[pp], cost[1])
            facts[("NAM", "has_capitulated", "no")] = False
            self.assertTrue(self.matches(block(order, "cancel_trigger"), facts))
            self.apply(block(order, "cancel_effect"), facts)
            self.apply(block(order, "remove_effect"), facts)
            self.assertEqual((facts[money], facts[pp]), cost)
            self.assertEqual(facts[claim], 1)
            self.assertFalse(facts.get(("NAM", "has_idea", "NAM_pw_" + programme + "_idea")))

    def federal_market_order(self, decision, state, district):
        decisions = block(parsed(f"common/decisions/{BASE}_decisions.txt"), "NAM_southern_lands")
        order = self.bind_field(block(decisions, decision), state)
        facts = self.postwar_facts()
        facts[("NAM", "has_country_flag", "NAM_exile_humanist")] = True
        facts[("NAM", "has_completed_focus", "NAM_hum_caravan_charter")] = True
        facts[("NAM", "has_completed_focus", "NAM_hum_union_currency")] = True
        facts[(state, "owner")] = district
        facts[(state, "is_owned_by", district)] = True
        facts[(state, "is_controlled_by", district)] = True
        facts[(state, "numeric", "infrastructure")] = 3
        facts[(state, "numeric", "arms_factory")] = 1
        for predicate, value in (("exists", "yes"), ("is_subject_of", "NAM"),
                                 ("has_country_flag", "NAM_federal_district"), ("has_capitulated", "no")):
            facts[(district, predicate, value)] = True
        return order, facts

    def resolve_federal_market_owner(self, entries, district):
        return [replace(e, key=district if e.key == "owner" else e.key,
                        value=self.resolve_federal_market_owner(e.value, district)
                        if isinstance(e.value, list) else e.value) for e in entries]

    def test_humanist_caravan_uses_the_held_rail_corridor_and_real_freight_stock(self):
        name = "NAM_hum_establish_caravan_depot"
        focus = self.exile_trees["exile_humanist"][1]["NAM_hum_caravan_charter"]
        self.assertIn(name, [e.value for e in walk(block(focus, "completion_reward"))
                             if e.key == "unlock_decision_tooltip"])
        for state, district in (("241", "KDR"), ("260", "SDR"), ("253", "RHM"),
                                ("701", "EFL"), ("69", "AZH")):
            order, facts = self.federal_market_order(name, state, district)
            cash = ("NAM", "variable", "ADISCORD_economy_treasury")
            trucks = ("NAM", "equipment", "motorized_equipment")
            facts[cash] = 250
            facts[trucks] = 60
            facts[("fixture", "fuel_logistics")] = True
            facts[("fixture", "PREV")] = district
            order = self.resolve_federal_market_owner(order, district)
            start = block(order, "complete_effect")
            self.assertTrue(self.matches(block(order, "visible"), facts))
            self.assertTrue(self.matches(block(order, "available"), facts))
            for key, insufficient in ((cash, 249.99), (trucks, 59.99), ((state, "numeric", "infrastructure"), 5),
                                      (("NAM", "controls_province", "4321"), False),
                                      ((district, "is_subject_of", "NAM"), False),
                                      ((state, "is_controlled_by", district), False)):
                invalid = {**facts, key: insufficient}
                before = dict(invalid)
                self.apply(start, invalid)
                self.assertEqual(invalid, before, (district, key))
            self.apply(start, facts)
            self.assertEqual((facts[cash], facts[trucks]), (0, 0))
            self.assertEqual(facts[(district, "equipment", "motorized_equipment")], 60)
            self.assertEqual(facts[(state, "building", "infrastructure")], 1)

    def test_union_currency_orders_pay_the_district_and_refund_a_lost_market_once(self):
        name = "NAM_hum_place_union_order"
        focus = self.exile_trees["exile_humanist"][1]["NAM_hum_union_currency"]
        self.assertIn(name, [e.value for e in walk(block(focus, "completion_reward"))
                             if e.key == "unlock_decision_tooltip"])
        self.assertEqual(scalar(block(focus, "mutually_exclusive"), "focus"), "NAM_hum_union_army")
        state, district = "253", "RHM"
        order, base = self.federal_market_order(name, state, district)
        base[("NAM", "has_completed_focus", "NAM_hum_caravan_charter")] = False
        base[("NAM", "controls_province", "4321")] = False
        cash = ("NAM", "variable", "ADISCORD_economy_treasury")
        treasury = (district, "variable", "ADISCORD_economy_treasury")
        stock = ("NAM", "equipment", "support_equipment")
        receipt = (state, "has_state_flag", "NAM_hum_union_order_paid")
        base[cash] = 300
        base[treasury] = 10
        base[stock] = 0
        self.assertTrue(self.matches(block(order, "visible"), base))
        self.assertFalse(self.matches(block(order, "custom_cost_trigger"), {**base, cash: 299.99}))
        self.assertEqual(scalar(order, "days_remove"), "35")
        settle = self.resolve_federal_market_owner(self.effects["NAM_hum_union_order_settle"], district)
        with patch.dict(self.effects, {"NAM_hum_union_order_settle": settle}):
            for loss in (None, (district, "is_subject_of", "NAM"), (state, "is_controlled_by", district),
                         (state, "is_owned_by", district), (state, "numeric", "arms_factory"),
                         ("NAM", "has_country_flag", "NAM_corp_takeover")):
                facts = dict(base)
                self.apply(block(order, "complete_effect"), facts)
                self.apply(block(order, "complete_effect"), facts)
                self.assertEqual((facts[cash], facts[receipt]), (0, True))
                self.assertFalse(self.matches(block(order, "available"), facts))
                if loss:
                    facts[loss] = loss[-1] == "NAM_corp_takeover"
                    self.assertTrue(self.matches(block(order, "cancel_trigger"), facts), loss)
                self.apply(block(order, "remove_effect"), facts)
                self.apply(block(order, "cancel_effect"), facts)
                self.apply(block(order, "remove_effect"), facts)
                self.assertFalse(facts.get(receipt))
                self.assertEqual((facts[cash], facts[treasury], facts[stock]),
                                 (300, 10, 0) if loss else (0, 190, 120))


    def test_two_federal_workshops_keep_separate_payments_across_a_border_change(self):
        name = "NAM_hum_place_union_order"
        rahma, facts = self.federal_market_order(name, "253", "RHM")
        sardan, other = self.federal_market_order(name, "260", "SDR")
        facts.update({key: value for key, value in other.items() if key[0] in ("260", "SDR")})
        cash = ("NAM", "variable", "ADISCORD_economy_treasury")
        stock = ("NAM", "equipment", "support_equipment")
        facts[cash] = 600
        facts[stock] = 0
        self.apply(block(rahma, "complete_effect"), facts)
        self.apply(block(rahma, "complete_effect"), facts)
        self.assertEqual(facts[cash], 300)
        self.apply(block(sardan, "complete_effect"), facts)
        self.assertEqual(facts[cash], 0)
        facts[("253", "owner")] = "SDR"
        facts[("253", "is_owned_by", "RHM")] = False
        facts[("253", "is_controlled_by", "RHM")] = False
        facts[("253", "is_owned_by", "SDR")] = True
        facts[("253", "is_controlled_by", "SDR")] = True
        self.assertTrue(self.matches(block(rahma, "cancel_trigger"), facts))
        self.apply(block(rahma, "cancel_effect"), facts)
        self.assertEqual(facts[cash], 300)
        self.assertTrue(facts[("260", "has_state_flag", "NAM_hum_union_order_paid")])
        settle = self.resolve_federal_market_owner(self.effects["NAM_hum_union_order_settle"], "SDR")
        with patch.dict(self.effects, {"NAM_hum_union_order_settle": settle}):
            self.apply(block(sardan, "remove_effect"), facts)
        self.assertEqual(facts[stock], 120)
        self.assertEqual(facts[("SDR", "variable", "ADISCORD_economy_treasury")], 180)
        self.assertEqual(facts[("SDR", "variable", "ADISCORD_economy_current_month_action_income")], 180)
        self.assertEqual(facts.get(("RHM", "variable", "ADISCORD_economy_treasury"), 0), 0)
        self.assertFalse(facts.get(("253", "has_state_flag", "NAM_hum_union_order_paid")))
        self.assertFalse(facts.get(("260", "has_state_flag", "NAM_hum_union_order_paid")))


    def test_kadir_charter_only_previews_and_builds_a_road_below_the_infrastructure_cap(self):
        focus = self.exile_trees["exile_humanist"][1]["NAM_hum_caravan_charter"]
        reward = block(focus, "completion_reward")
        self.assertFalse(any(entry.key == "hidden_effect" for entry in reward))
        self.assertNotIn("NAM_hum_caravan_charter_tt", [e.value for e in walk(reward)
                                                        if e.key == "custom_effect_tooltip"])
        for level in (4, 5):
            for federal in (True, False):
                facts = self.economy_facts()
                facts[("fixture", "track_units")] = True
                facts[("KDR", "exists", "yes")] = True
                facts[("KDR", "has_country_flag", "NAM_federal_district")] = True
                facts[("KDR", "is_subject_of", "NAM")] = federal
                facts[("KDR", "capital")] = "241"
                facts[("241", "is_owned_by", "KDR")] = True
                facts[("241", "is_controlled_by", "KDR")] = True
                facts[("241", "numeric", "infrastructure")] = level
                self.apply(reward, facts)
                self.assertEqual(facts.get(("241", "building", "infrastructure"), 0),
                                 int(federal and level < 5))
                self.assertEqual(facts.get(("KDR", "reward", "stability"), 0), 0.05 if federal else 0)


    def test_city_water_connections_choose_a_site_and_use_live_power_for_the_second_main(self):
        water = self.decisions["NAM_program_city_water"]
        power = self.decisions["NAM_program_regional_power"]
        focuses = self.postwar
        self.assertEqual(scalar(block(focuses["NAM_pw_water_intakes"], "mutually_exclusive"), "focus"),
                         "NAM_pw_irrigation_works")
        self.assertEqual(scalar(block(focuses["NAM_pw_irrigation_works"], "mutually_exclusive"), "focus"),
                         "NAM_pw_water_intakes")
        for excluded in ("NAM_pw_water_intakes", "NAM_pw_irrigation_works"):
            self.assertIn("NAM_pw_reservoir_survey", reachable(focuses, {excluded}))
        for states in (("688", "700"), ("700", "688")):
            orders = {state: self.bind_field(water, state) for state in states}
            firms = {"688": "industrial_complex", "700": "dockyard"}
            facts = self.postwar_facts()
            facts[("NAM", "has_completed_focus", "NAM_pw_irrigation_works")] = False
            cash = ("NAM", "variable", "ADISCORD_economy_treasury")
            busy = ("NAM", "has_country_flag", "NAM_pw_civil_busy")
            for state, building in firms.items():
                facts[(state, "variable", f"fixture_building_slots_{building}_yes")] = True
            for i, state in enumerate(states):
                order = orders[state]
                if i:
                    self.assertFalse(self.matches(block(order, "available"), facts))
                    self.apply(block(power, "complete_effect"), facts)
                    with patch.dict(self.effects, {"NAM_oil_refresh": []}):
                        self.apply(block(power, "remove_effect"), facts)
                    self.assertTrue(facts[("NAM", "has_country_flag", "NAM_program_regional_power_commissioned")])
                self.assertTrue(self.matches(block(order, "available"), facts))
                self.assertFalse(self.matches(block(order, "custom_cost_trigger"), {**facts, cash: 299.99}))
                cash_before = facts[cash]
                self.apply(block(order, "complete_effect"), facts)
                self.apply(block(order, "complete_effect"), facts)
                self.assertEqual(facts[cash], cash_before - 300)
                self.assertTrue(facts[busy])
                if not i:
                    self.apply(block(orders[states[1]], "complete_effect"), facts)
                    self.assertFalse(facts.get((states[1], "has_state_flag", "NAM_city_water_paid")))
                self.apply(block(order, "remove_effect"), facts)
                self.apply(block(order, "remove_effect"), facts)
                self.assertEqual(facts[(state, "building", firms[state])], 1)
                self.assertFalse(facts[busy])
                self.assertFalse(self.matches(block(order, "visible"), facts))
            self.assertFalse(self.matches(block(self.decisions["NAM_program_irrigation_works"], "visible"), facts))

    def test_city_water_refunds_the_receipt_after_losing_power_room_or_control(self):
        water = self.bind_field(self.decisions["NAM_program_city_water"], "700")
        for lost in (("NAM", "controls_state", "690"), ("700", "is_owned_by", "NAM"),
                     ("700", "is_controlled_by", "NAM"), ("700", "variable", "fixture_building_slots_dockyard_yes")):
            facts = self.postwar_facts()
            facts[("688", "has_state_flag", "NAM_city_water_connected")] = True
            facts[("NAM", "has_country_flag", "NAM_program_regional_power_commissioned")] = True
            facts[("700", "variable", "fixture_building_slots_dockyard_yes")] = True
            cash = ("NAM", "variable", "ADISCORD_economy_treasury")
            facts[cash] = 300
            self.apply(block(water, "complete_effect"), facts)
            self.assertEqual(facts[cash], 0)
            facts[lost] = False
            self.assertTrue(self.matches(block(water, "cancel_trigger"), facts))
            self.apply(block(water, "remove_effect"), facts)
            self.apply(block(water, "cancel_effect"), facts)
            self.assertEqual(facts[cash], 300)
            self.assertFalse(facts[("NAM", "has_country_flag", "NAM_pw_civil_busy")])
            self.assertFalse(facts[("700", "has_state_flag", "NAM_city_water_paid")])
            self.assertFalse(facts.get(("700", "has_state_flag", "NAM_city_water_connected")))
            self.assertFalse(facts.get(("700", "building", "dockyard")))
            facts[lost] = True
            self.assertTrue(self.matches(block(water, "available"), facts))

    def test_irrigation_provisions_the_south_coast_and_protects_only_its_held_oilfield(self):
        canal = self.decisions["NAM_program_irrigation_works"]
        name = "NAM_south_coast_irrigation"
        modifier = block(parsed("common/dynamic_modifiers/ADISCORD_dynamic_modifiers_NAM.txt"), name)
        self.assertEqual(float(scalar(modifier, "local_supplies")), 0.30)
        facts = self.postwar_facts()
        facts[("NAM", "has_completed_focus", "NAM_pw_water_intakes")] = False
        self.assertFalse(self.matches(block(self.bind_field(self.decisions["NAM_program_city_water"], "688"),
                                            "visible"), facts))
        self.apply(block(canal, "complete_effect"), facts)
        self.apply(block(canal, "remove_effect"), facts)
        self.apply(block(canal, "remove_effect"), facts)
        self.assertTrue(facts[("689", "has_dynamic_modifier", name)])
        self.assertFalse(self.matches(block(canal, "visible"), facts))
        for state, owned, controlled, condition in (("689", True, True, 65), ("689", True, False, 50),
                                                    ("689", False, True, 50), ("690", True, True, 50)):
            facts[(state, "is_owned_by", "NAM")] = owned
            facts[(state, "is_controlled_by", "NAM")] = controlled
            if state == "689":
                self.assertEqual(self.matches(block(modifier, "enable"), facts, state), owned and controlled)
            facts[(state, "has_variable", "NAM_field_condition")] = True
            facts[(state, "variable", "NAM_field_condition")] = 80
            facts[(state, "variable", "NAM_field_damage_amount")] = 30
            with patch.dict(self.effects, {"NAM_oil_refresh": []}):
                self.apply(self.effects["NAM_field_apply_damage"], facts, state)
            self.assertEqual(facts[(state, "variable", "NAM_field_condition")], condition)

    def test_common_market_uses_paid_local_lots_and_ignores_inaccessible_partners(self):
        south = block(parsed(f"common/decisions/{BASE}_decisions.txt"), "NAM_southern_lands")
        convoy = block(south, "NAM_hum_collect_market_freight")
        charter = "NAM_hum_establish_caravan_depot"
        rehab, facts = self.federal_market_order(charter, "253", "RHM")
        sardan, other = self.federal_market_order(charter, "260", "SDR")
        facts.update({key: value for key, value in other.items() if key[0] in ("260", "SDR")})
        common = ("NAM", "has_completed_focus", "NAM_hum_common_market")
        cash = ("NAM", "variable", "ADISCORD_economy_treasury")
        stock = ("NAM", "equipment", "support_equipment")

        def stockpile(state):
            return (state, "variable", "NAM_hum_market_lots")

        out = ("NAM", "has_country_flag", "NAM_hum_market_convoy_out")
        facts[("fixture", "market_owners")] = True
        facts[("fixture", "fuel_logistics")] = True
        facts[("NAM", "equipment", "motorized_equipment")] = 400
        facts[cash] = 2000
        facts[stock] = 0
        facts[common] = False
        facts[("NAM", "has_completed_focus", "NAM_hum_union_currency")] = False
        facts[("fixture", "PREV")] = "RHM"
        self.apply(block(rehab, "complete_effect"), facts)
        self.assertEqual(facts[stockpile("253")], 1)
        self.assertFalse(self.matches(block(convoy, "visible"), facts))
        self.apply(block(convoy, "complete_effect"), facts)
        self.assertEqual(facts[stock], 0)
        facts[common] = True
        facts[("260", "numeric", "infrastructure")] = 5
        self.assertTrue(self.matches(block(sardan, "available"), facts))
        facts[("fixture", "PREV")] = "SDR"
        self.apply(block(sardan, "complete_effect"), facts)
        self.assertEqual(facts[stockpile("260")], 1)
        self.assertEqual(facts.get(("260", "building", "infrastructure"), 0), 0)
        self.assertEqual(facts[cash], 1500)
        self.assertEqual(facts[("SDR", "equipment", "motorized_equipment")], 60)
        facts[stockpile("241")] = 3
        facts[("NAM", "controls_province", "4321")] = False
        self.apply(block(convoy, "complete_effect"), facts)
        self.assertEqual(facts[stock], 0)
        facts[("NAM", "controls_province", "4321")] = True
        self.apply(block(convoy, "complete_effect"), facts)
        self.assertEqual(facts[stock], 80)
        self.assertEqual([facts[stockpile(state)] for state in ("253", "260", "241")], [0, 0, 3])
        self.assertEqual(facts[("NAM", "flag_duration", "NAM_hum_market_convoy_out")], 30)
        facts[stockpile("253")] = 2
        facts[stockpile("260")] = 1
        facts[("RHM", "is_subject_of", "NAM")] = False
        self.apply(block(convoy, "complete_effect"), facts)
        self.assertEqual(facts[stock], 80)
        facts[out] = False
        self.apply(block(convoy, "complete_effect"), facts)
        self.assertEqual(facts[stock], 120)
        self.assertEqual([facts[stockpile(state)] for state in ("253", "260")], [2, 0])
        facts[out] = False
        self.assertFalse(self.matches(block(convoy, "available"), facts))
        facts[("RHM", "is_subject_of", "NAM")] = True
        self.apply(block(convoy, "complete_effect"), facts)
        self.assertEqual(facts[stock], 160)
        self.assertEqual(facts[stockpile("253")], 1)

    def test_common_market_workshops_reserve_just_their_own_lot_and_refund_it_at_its_site(self):
        name = "NAM_hum_place_union_order"
        order, template = self.federal_market_order(name, "253", "RHM")
        south = block(parsed(f"common/decisions/{BASE}_decisions.txt"), "NAM_southern_lands")
        convoy = block(south, "NAM_hum_collect_market_freight")
        _, other = self.federal_market_order(name, "260", "SDR")
        template.update({key: value for key, value in other.items() if key[0] in ("260", "SDR")})
        local = ("253", "variable", "NAM_hum_market_lots")
        spare = ("260", "variable", "NAM_hum_market_lots")
        reserved = ("253", "has_state_flag", "NAM_hum_order_reserved_lot")
        cash = ("NAM", "variable", "ADISCORD_economy_treasury")
        guns = ("NAM", "equipment", "artillery_equipment")
        parts = ("NAM", "equipment", "support_equipment")
        for market, quantity, lost in ((True, 1, False), (True, 1, True), (False, 1, False), (True, 0, False)):
            facts = {**template, ("fixture", "market_owners"): True, local: quantity, spare: 1,
                     cash: 600, guns: 0, parts: 0, ("NAM", "has_completed_focus", "NAM_hum_common_market"): market}
            self.apply(block(order, "complete_effect"), facts)
            self.apply(block(order, "complete_effect"), facts)
            expected = market and quantity == 1
            self.assertEqual(bool(facts.get(reserved)), expected)
            self.assertEqual((facts[local], facts[spare], facts[cash]), (quantity - expected, 1, 300))
            if lost:
                facts[("253", "is_owned_by", "RHM")] = False
            self.apply(block(convoy, "complete_effect"), facts)
            self.assertEqual(facts[parts], 40 if market else 0)
            self.apply(block(order, "remove_effect"), facts)
            self.apply(block(order, "cancel_effect"), facts)
            self.assertFalse(facts.get(reserved))
            self.assertEqual(facts[local], quantity if lost else quantity - expected)
            self.assertEqual(facts[spare], 0 if market else 1)
            self.assertEqual(facts[guns], 15 if expected and not lost else 0)
            self.assertEqual(facts[parts], (40 if market else 0) + (0 if lost else 120))
            self.assertEqual(facts[cash], 600 if lost else 300)

    def test_exile_federation_final_keeps_the_market_on_both_parliamentary_paths(self):
        tree = self.exile_trees["exile_humanist"][1]
        for blocked in ("NAM_hum_union_currency", "NAM_hum_union_army"):
            route = reachable(tree, {blocked})
            self.assertTrue({"NAM_hum_caravan_charter", "NAM_hum_common_market",
                             "NAM_hum_union_constitution"} <= route)
        self.assertNotIn("NAM_hum_union_constitution", reachable(tree, {"NAM_hum_common_market"}))
        self.assertNotIn("NAM_hum_common_market", reachable(tree, {"NAM_hum_caravan_charter"}))
        rewards = block(tree["NAM_hum_common_market"], "completion_reward")
        self.assertEqual(scalar(rewards, "unlock_decision_tooltip"), "NAM_hum_collect_market_freight")


    def war_share_issue(self):
        category = block(parsed(f"common/decisions/{BASE}_decisions.txt"), "NAM_free_zones")
        issue = block(category, "NAM_board_issue_war_shares")
        facts = self.board_facts()
        facts[("NAM", "has_completed_focus", "NAM_board_stock_mobilisation")] = True
        facts[("NAM", "array", "NAM_federal_districts")] = ("EFL", "AZH")
        facts[("NAM", "has_country_flag", "NAM_corp_dispute_cooldown")] = True
        for district, capital, company in (("EFL", "701", 1), ("AZH", "69", 6)):
            self.operating_board_district(facts, district, capital)
            facts[(district, "has_variable", "NAM_corp_district_owner")] = True
            facts[(district, "variable", "NAM_corp_district_owner")] = company
        return issue, facts

    def test_war_shares_sell_once_per_operating_concession_at_the_exact_price(self):
        issue, facts = self.war_share_issue()
        capital = ("NAM", "variable", "NAM_corp_capital")
        facts[capital] = 25
        order = self.bind_field(issue, "EFL")
        self.assertTrue(self.matches(block(order, "visible"), facts))
        self.assertTrue(self.matches(block(order, "available"), facts))
        self.assertTrue(self.matches(block(order, "custom_cost_trigger"), facts))
        for key, bad in ((capital, 24.99), (("NAM", "is_subject", "no"), False),
                         (("NAM", "has_completed_focus", "NAM_board_stock_mobilisation"), False),
                         (("EFL", "is_subject_of", "NAM"), False), (("EFL", "has_capitulated", "no"), False),
                         (("701", "is_controlled_by", "PREV"), False),
                         (("EFL", "has_country_flag", "NAM_corp_disputed"), True),
                         (("EFL", "has_variable", "NAM_corp_district_owner"), False)):
            with self.subTest(key=key):
                invalid = {**facts, key: bad}
                self.apply(block(order, "complete_effect"), invalid)
                self.assertEqual(invalid[capital], invalid.get(key) if key == capital else 25)
                self.assertFalse(invalid.get(("EFL", "has_variable", "NAM_board_stock_coupon")))
                self.assertFalse(invalid.get(("NAM", "equipment", "infantry_equipment")))
        self.apply(block(order, "complete_effect"), facts)
        self.apply(block(order, "complete_effect"), facts)
        self.assertEqual(facts[capital], 0)
        self.assertFalse(self.matches(block(order, "available"), facts))
        self.assertTrue(self.matches(block(self.bind_field(issue, "AZH"), "available"), facts))
        self.assertEqual(facts[("EFL", "variable", "NAM_board_stock_coupon")], 1)
        for equipment, quantity in (("infantry_equipment", 1800), ("artillery_equipment", 60), ("support_equipment", 50)):
            self.assertEqual(facts[("NAM", "equipment", equipment)], quantity)

    def test_district_shareholders_collect_three_actual_dividends_across_title_changes(self):
        issue, facts = self.war_share_issue()
        capital = ("NAM", "variable", "NAM_corp_capital")
        facts[capital] = 50
        coupon = ("EFL", "variable", "NAM_board_stock_coupon")
        net = ("NAM", "variable", "NAM_corp_last_dividend")
        monthly = self.effects["NAM_corp_districts_monthly"]
        self.apply(monthly, facts)
        self.assertEqual((facts[net], facts[capital]), (23, 73))
        order = self.bind_field(issue, "EFL")
        self.apply(block(order, "complete_effect"), facts)
        self.assertEqual(facts[capital], 48)
        self.apply(monthly, facts)
        self.assertEqual((facts[net], facts[coupon], facts[capital]), (15, 2, 63))
        for key, disabled in ((("EFL", "has_country_flag", "NAM_corp_disputed"), True),
                              (("EFL", "is_subject_of", "NAM"), False),
                              (("701", "is_controlled_by", "PREV"), False)):
            previous = facts.get(key, False)
            facts[key] = disabled
            self.apply(monthly, facts)
            self.assertEqual((facts[net], facts[coupon]), (15, 2))
            facts[key] = previous
        facts[("EFL", "variable", "NAM_corp_district_owner")] = 4
        self.apply(block(order, "complete_effect"), facts)
        self.apply(monthly, facts)
        self.assertEqual((facts[net], facts[coupon]), (15, 3))
        other = self.bind_field(issue, "AZH")
        self.apply(block(other, "complete_effect"), facts)
        self.apply(monthly, facts)
        self.assertEqual((facts[net], facts[coupon], facts[("AZH", "variable", "NAM_board_stock_coupon")]), (0, 4, 2))
        self.apply(monthly, facts)
        self.assertEqual((facts[net], facts[coupon]), (6, 4))
        cash_before = facts[capital]
        self.apply(block(order, "complete_effect"), facts)
        self.assertEqual(facts[capital], cash_before)
        self.assertEqual(facts[("NAM", "equipment", "infantry_equipment")], 3600)

    def test_corporate_stock_focus_can_open_the_southern_war_without_selling_rights(self):
        tree = self.exile_trees["exile_corporate"][1]
        name = "NAM_board_stock_mobilisation"
        war = tree["NAM_board_great_war"]
        self.assertTrue({name, "NAM_board_great_war"} <= reachable(tree, set()))
        self.assertIn(name, [e.value for e in block(war, "prerequisite")])
        reward = block(tree[name], "completion_reward")
        self.assertEqual(scalar(reward, "unlock_decision_tooltip"), "NAM_board_issue_war_shares")
        facts = self.board_facts()
        cohesion = ("NAM", "variable", "NAM_consolidation")
        facts[cohesion] = 60
        for flag in ("NAM_wor_exile_war", "NAM_war_of_return_won"):
            facts[("NAM", "has_global_flag", flag)] = True
        for key in ("exists", "has_capitulated", "is_subject"):
            facts[("RHM", key, "yes" if key == "exists" else "no")] = True
        self.assertFalse(self.matches(block(war, "available"), facts))
        self.apply(reward, facts)
        self.assertEqual(facts[cohesion], 70)
        self.assertTrue(self.matches(block(war, "available"), facts))
        self.assertFalse(facts.get(("NAM", "equipment", "infantry_equipment")))


    def southern_delegation(self, recipient):
        category = block(parsed(f"common/decisions/{BASE}_decisions.txt"), "NAM_southern_lands")
        decision = self.bind_field(block(category, "NAM_hum_send_southern_mandate"), recipient)
        facts = self.facts(treasury=300)
        facts.update({
            ("NAM", "has_country_flag", "NAM_exile_humanist"): True,
            ("NAM", "has_completed_focus", "NAM_hum_southern_offer"): True,
            ("NAM", "has_global_flag", "NAM_war_of_return_won"): True,
            ("NAM", "is_subject", "no"): True,
            ("fixture", "fuel_logistics"): True,
            ("fixture", "track_units"): True,
            ("fixture", "accession_country"): recipient,
        })
        for tag, state in (("RHM", "253"), ("SDR", "260"), ("EFL", "701")):
            self.operating_board_district(facts, tag, state)
            district = tag == "EFL"
            facts[(tag, "is_subject_of", "NAM")] = district
            facts[(tag, "has_country_flag", "NAM_federal_district")] = district
            facts[(tag, "is_subject", "no")] = not district
            facts[(tag, "has_war", "no")] = True
            facts[(tag, "is_in_faction", "no")] = True
            facts[(state, "variable", "fixture_building_slots_industrial_complex_yes")] = 1
        event = self.events["ADISCORD_nam_resource_war.113"]
        answers = {scalar(e.value, "name").split(".")[-1]: e.value for e in event if e.key == "option"}
        return decision, facts, answers

    def test_federal_charters_muster_their_own_districts_then_settle_only_the_campaign(self):
        allies = ("EFL", "AZH", "RHM")
        enemies = ("SDR", "KDR")
        category = block(parsed(f"common/decisions/{BASE}_decisions.txt"), "NAM_consolidation")
        treaty = self.bind_field(block(category, "NAM_hum_federal_treaty"), "EFL")
        routes = (("districts_charter", ("EFL",)), ("metropole_charter", ("EFL", "AZH")),
                  ("before_call", ()), ("board", ()), ("radical", ()))
        for route, expected in routes:
            with self.subTest(route=route):
                _, facts, _ = self.southern_delegation("RHM")
                facts[("fixture", "federal_front")] = {"NAM_wor_primary": "SDR"}
                facts[("fixture", "federal_calls")] = []
                facts["global.NAM_wor_participants"] = list(enemies)
                facts[("NAM", "array", "NAM_federal_districts")] = allies
                facts[("NAM", "has_completed_focus", "NAM_hum_union_call")] = route != "before_call"
                for member, capital in zip(allies, ("701", "69", "253")):
                    self.operating_board_district(facts, member, capital)
                    facts[(member, "has_war", "no")] = True
                    facts[(member, "is_in_faction", "no")] = True
                for enemy in enemies:
                    facts[(enemy, "exists", "yes")] = True
                facts[("RHM", "has_war", "no")] = False
                facts[("RHM", "has_war_with", "SDR")] = True
                facts[("SDR", "has_war_with", "RHM")] = True
                self.assertTrue(self.matches(block(treaty, "available"), facts))
                self.apply(block(treaty, "complete_effect"), facts)
                self.assertTrue(facts[("EFL", "has_country_flag", "NAM_hum_federal_treaty_signed")])
                facts[("NAM", "has_completed_focus", "NAM_hum_districts_charter")] = route != "metropole_charter"
                facts[("NAM", "has_completed_focus", "NAM_hum_metropole_charter")] = route == "metropole_charter"
                facts[("NAM", "has_country_flag", "NAM_corp_takeover")] = route == "board"
                facts[("NAM", "has_country_flag", "NAM_exile_humanist")] = route != "radical"
                self.apply(self.effects["NAM_hum_register_federal_army"], facts)
                self.assertEqual(facts["global.NAM_hum_federal_army"], list(expected))
                for _ in range(2):
                    self.apply(self.effects["NAM_hum_call_federal_army"], facts)
                self.assertEqual(facts[("fixture", "federal_calls")], list(expected))
                for member in allies[:2]:
                    for enemy in enemies:
                        self.assertEqual(facts.get((member, "has_war_with", enemy), False), member in expected)
                facts[("EFL", "has_war_with", "VAL")] = True
                self.apply(self.effects["NAM_hum_demobilise_federal_army"], facts)
                self.assertEqual(facts["global.NAM_hum_federal_army"], [])
                self.assertTrue(facts[("RHM", "has_war_with", "SDR")])
                self.assertTrue(facts[("EFL", "has_war_with", "VAL")])
                for member in expected:
                    for enemy in enemies:
                        self.assertFalse(facts[(member, "has_war_with", enemy)])

    def test_federal_call_needs_a_working_seat_and_an_independent_enemy_leader(self):
        _, facts, _ = self.southern_delegation("RHM")
        facts[("NAM", "has_completed_focus", "NAM_hum_metropole_charter")] = True
        qualified = self.triggers["NAM_hum_federal_muster_eligible"]
        self.assertTrue(self.matches(qualified, facts, "EFL"))
        for key in (("701", "is_controlled_by", "PREV"), ("701", "is_owned_by", "PREV"),
                    ("EFL", "has_capitulated", "no"), ("EFL", "is_subject_of", "NAM"),
                    ("EFL", "is_in_faction", "no"), ("EFL", "has_war", "no")):
            with self.subTest(key=key):
                self.assertFalse(self.matches(qualified, facts | {key: False}, "EFL"))
        facts[("RHM", "is_subject", "no")] = False
        facts[("SDR", "is_subject", "no")] = False
        facts[("RHM", "is_subject_of", "KDR")] = True
        self.assertTrue(self.matches(self.triggers["NAM_wor_target_valid"], facts, "RHM"))
        self.assertFalse(self.matches(self.triggers["NAM_great_war_target_left"], facts))
        facts[("SDR", "is_subject", "no")] = True
        self.assertTrue(self.matches(self.triggers["NAM_great_war_target_left"], facts))
        self.assertFalse(self.matches(self.triggers["NAM_wor_principal_standing"], facts))
        launch = [e.key for e in block(self.effects["NAM_great_war_start"], "if")]
        for before, after in zip(("NAM_hum_register_federal_army", "declare_war_on", "NAM_wor_call_participants"),
                                 ("declare_war_on", "NAM_wor_call_participants", "NAM_hum_call_federal_army")):
            self.assertLess(launch.index(before), launch.index(after))
        closure = [e.key for e in self.effects["NAM_great_war_close"]]
        self.assertLess(closure.index("set_global_flag"), closure.index("NAM_hum_demobilise_federal_army"))
        self.assertLess(closure.index("NAM_hum_demobilise_federal_army"), closure.index("NAM_wor_release_participants"))

    def test_voluntary_accession_spends_on_consent_and_leaves_a_real_southern_opponent(self):
        order, facts, answers = self.southern_delegation("RHM")
        cash = ("NAM", "variable", "ADISCORD_economy_treasury")
        schedule = ("RHM", "scheduled_event", "ADISCORD_nam_resource_war.113")
        self.assertTrue(self.matches(block(order, "available"), facts))
        self.apply(block(order, "complete_effect"), facts)
        self.apply(block(order, "complete_effect"), facts)
        self.assertEqual((facts[cash], facts[schedule]), (300, 1))
        self.assertFalse(self.matches(block(order, "visible"), facts))
        self.assertTrue(self.matches(block(answers["b"], "trigger"), facts, "RHM"))
        self.assertFalse(self.matches(block(answers["c"], "trigger"), facts, "RHM"))
        self.apply(block(answers["b"], "hidden_effect"), facts, "RHM")
        self.apply(block(answers["b"], "hidden_effect"), facts, "RHM")
        self.assertEqual((facts[cash], facts[("RHM", "variable", "ADISCORD_economy_treasury")]), (0, 300))
        self.assertTrue(facts[("RHM", "is_subject_of", "NAM")])
        self.assertTrue(facts[("RHM", "has_country_flag", "NAM_hum_federal_treaty_signed")])
        self.assertEqual(facts[("RHM", "autonomy")], "autonomy_NAM_federal_district")
        self.assertEqual(facts[("NAM", "array", "NAM_federal_districts")], ("RHM",))
        self.assertEqual(facts[("NAM", "scheduled_event", "ADISCORD_nam_resource_war.114")], 1)
        self.assertFalse(self.matches(self.triggers["NAM_wor_target_valid"], facts, "RHM"))
        self.assertTrue(self.matches(self.triggers["NAM_wor_target_valid"], facts, "SDR"))

    def test_stale_or_refused_southern_invitation_never_collects_or_subjugates(self):
        order, original, answers = self.southern_delegation("RHM")
        for key, changed in (
                (("NAM", "variable", "ADISCORD_economy_treasury"), 299.99),
                (("NAM", "has_completed_focus", "NAM_hum_union_call"), True),
                (("NAM", "has_global_flag", "NAM_great_war_started"), True),
                (("NAM", "has_country_flag", "NAM_corp_takeover"), True),
                (("RHM", "is_in_faction", "no"), False),
                (("SDR", "is_in_faction_with", "NAM"), True),
                (("RHM", "is_subject_of", "NAM"), True),
                (("253", "is_controlled_by", "PREV"), False),
                (("RHM", "has_country_flag", "NAM_hum_southern_letter"), False)):
            with self.subTest(key=key):
                facts = dict(original)
                self.apply(block(order, "complete_effect"), facts)
                facts[key] = changed
                cash = ("NAM", "variable", "ADISCORD_economy_treasury")
                before = facts[cash]
                self.assertTrue(self.matches(block(answers["close"], "trigger"), facts, "RHM"))
                self.assertFalse(self.matches(block(answers["b"], "trigger"), facts, "RHM"))
                self.apply(block(answers["b"], "hidden_effect"), facts, "RHM")
                self.apply(block(answers["close"], "hidden_effect"), facts, "RHM")
                self.assertEqual(facts[cash], before)
                self.assertNotIn(("RHM", "autonomy"), facts)
                self.assertFalse(facts.get(("RHM", "has_country_flag", "NAM_hum_southern_letter")))
        self.assertEqual(scalar(self.events["ADISCORD_nam_resource_war.113"], "timeout_days"), "7")
        self.assertEqual(next(iter(answers)), "a")
        self.apply(block(order, "complete_effect"), original)
        self.apply(block(answers["a"], "hidden_effect"), original, "RHM")
        self.apply(block(answers["a"], "hidden_effect"), original, "RHM")
        self.assertEqual(original[("NAM", "variable", "ADISCORD_economy_treasury")], 300)
        self.assertEqual(original[("NAM", "scheduled_event", "ADISCORD_nam_resource_war.115")], 1)
        other, _, _ = self.southern_delegation("EFL")
        self.apply(block(other, "complete_effect"), original)
        self.assertNotIn(("EFL", "scheduled_event", "ADISCORD_nam_resource_war.113"), original)

    def test_existing_federal_district_can_host_a_workshop_on_its_own_terms(self):
        order, facts, answers = self.southern_delegation("EFL")
        self.apply(block(order, "complete_effect"), facts)
        self.assertFalse(self.matches(block(answers["b"], "trigger"), facts, "EFL"))
        self.assertTrue(self.matches(block(answers["c"], "trigger"), facts, "EFL"))
        for lost in (("EFL", "is_subject_of", "NAM"), ("701", "is_controlled_by", "PREV"),
                     ("701", "variable", "fixture_building_slots_industrial_complex_yes")):
            closed = {**facts, lost: False}
            self.apply(block(answers["c"], "hidden_effect"), closed, "EFL")
            self.assertFalse(closed.get(("701", "building", "industrial_complex")))
            self.assertEqual(closed[("NAM", "variable", "ADISCORD_economy_treasury")], 300)
        self.apply(block(answers["c"], "hidden_effect"), facts, "EFL")
        self.apply(block(answers["c"], "hidden_effect"), facts, "EFL")
        self.assertEqual(facts[("701", "building", "industrial_complex")], 1)
        self.assertEqual(facts[("NAM", "variable", "ADISCORD_economy_treasury")], 0)
        self.assertNotIn(("EFL", "variable", "ADISCORD_economy_treasury"), facts)
        self.assertNotIn(("EFL", "autonomy"), facts)

    def test_last_opponent_and_absent_addresses_never_gate_the_union_call(self):
        order, facts, _ = self.southern_delegation("RHM")
        facts[("SDR", "exists", "yes")] = False
        self.assertFalse(self.matches(block(order, "available"), facts))
        self.apply(block(order, "complete_effect"), facts)
        self.assertFalse(facts.get(("NAM", "has_country_flag", "NAM_hum_southern_mandate_sent")))
        no_addresses = dict(facts)
        for tag in ("SDR", "RHM", "EFL"):
            no_addresses[(tag, "exists", "yes")] = False
        tree = self.exile_trees["exile_humanist"][1]
        name = "NAM_hum_southern_offer"
        self.assertTrue(self.matches(block(tree[name], "available"), no_addresses))
        self.apply(block(tree[name], "completion_reward"), no_addresses)
        self.assertEqual(no_addresses[("NAM", "variable", "NAM_consolidation")], 5)
        self.assertTrue(self.matches(block(tree["NAM_hum_union_call"], "available"), no_addresses))
        self.assertTrue({name, "NAM_hum_union_call", "NAM_hum_great_war"} <= reachable(tree, set()))
        self.assertNotIn("NAM_hum_union_call", reachable(tree, {name}))
        facts[("NAM", "has_global_flag", "NAM_wor_exile_war")] = True
        facts[("NAM", "variable", "NAM_consolidation")] = 70
        facts[("NAM", "has_completed_focus", "NAM_hum_union_call")] = True
        self.assertTrue(self.matches(block(tree["NAM_hum_great_war"], "available"), facts))


    def test_takeover_opens_three_public_tenders_through_the_normal_corporate_focus_chain(self):
        category = block(parsed(f"common/decisions/{BASE}_decisions.txt"), "NAM_free_zones")
        human_tree = self.exile_trees["exile_humanist"][1]
        board_tree = self.exile_trees["exile_corporate"][1]
        facts = self.facts()
        facts.update({("NAM", "is_subject", "no"): True, ("NAM", "capital"): "225",
                      ("225", "is_owned_by", "NAM"): True, ("225", "is_controlled_by", "NAM"): True,
                      ("NAM", "variable", "NAM_pirate_loot"): 0, ("fixture", "fuel_logistics"): True})
        human_choice = next(e.value for e in self.events[BASE + ".100"] if e.key == "option"
                            and scalar(e.value, "name") == BASE + ".100.b")
        investors = block(category, "NAM_corp_court_investors")
        self.assertEqual((scalar(investors, "cost"), scalar(investors, "days_re_enable")), ("25", "60"))
        def take_focus(tree, name):
            focus = tree[name]
            for entry in focus:
                if entry.key == "prerequisite":
                    self.assertTrue(any(facts.get(("NAM", "has_completed_focus", parent.value))
                                        for parent in entry.value), name)
            self.assertTrue(self.matches(block(focus, "available"), facts), name)
            self.apply(block(focus, "completion_reward"), facts)
            facts[("NAM", "has_completed_focus", name)] = True

        tenders = [block(category, "NAM_board_tender_" + lot) for lot in ("rail", "yards", "depots")]
        # Minister rosters, board vote arithmetic and group opinion have their own scenario tests.
        fixture_effects = ("NAM_activate_weber_commander", "NAM_party_representatives_exile_humanist",
                           "NAM_rom_step_down", "NAM_party_representatives_corporate", "NAM_board_recount",
                           "NAM_corp_refresh", "NAM_groups_refresh")
        with patch.dict(self.effects, {name: [] for name in fixture_effects}):
            self.apply(human_choice, facts)
            self.assertEqual(facts[("NAM", "variable", "NAM_corp_influence")], 20)
            take_focus(human_tree, "NAM_hum_free_zones")
            for _ in range(2):
                self.apply(self.effects["NAM_corp_monthly"], facts)
            take_focus(human_tree, "NAM_hum_open_doors")
            self.assertEqual(facts[("NAM", "variable", "NAM_corp_influence")], 38)
            self.assertTrue(self.matches(block(investors, "visible"), facts))
            answered = set()
            treasury = ("NAM", "numeric", "has_political_power")
            coup = ("NAM", "scheduled_event", BASE + ".103")
            for _ in range(9):
                self.assertGreaterEqual(facts[treasury], 25)
                facts[treasury] -= 25
                self.apply(block(investors, "complete_effect"), facts)
                for number in ("101", "102"):
                    if number not in answered and facts.get(("NAM", "scheduled_event", BASE + "." + number)):
                        concede = next(e.value for e in self.events[BASE + "." + number] if e.key == "option"
                                       and scalar(e.value, "name").endswith(".c"))
                        self.apply(concede, facts)
                        answered.add(number)
                if coup in facts:
                    break
                for _ in range(2):
                    self.apply(self.effects["NAM_corp_monthly"], facts)
                    if coup in facts:
                        break
                if coup in facts:
                    break
            self.assertEqual(answered, {"101", "102"})
            self.assertEqual(facts[("NAM", "scheduled_event", BASE + ".103")], 1)
            self.assertTrue(all(not self.matches(block(d, "visible"), facts) for d in tenders))
            takeover = self.events[BASE + ".103"]
            self.assertTrue(self.matches(block(takeover, "trigger"), facts))
            self.apply(block(takeover, "option"), facts)
            self.assertEqual([self.matches(block(d, "visible"), facts) for d in tenders], [True, False, False])
            for lot in ("rail", "yards", "depots"):
                self.assertEqual(facts[("NAM", "variable", "NAM_board_lot_" + lot)], 0)
            weeks = 0
            for name in ("NAM_hum_board_of_governors", "NAM_board_humanist_facade", "NAM_board_constitution",
                         "NAM_board_island_concessions", "NAM_board_shareholders"):
                take_focus(board_tree, name)
                weeks += int(scalar(board_tree[name], "cost"))
                self.assertEqual([self.matches(block(d, "visible"), facts) for d in tenders],
                                 [True, weeks >= 14, weeks >= 18])
            self.assertEqual(weeks, 18)

    def test_paid_harbour_reconstruction_respects_full_infrastructure_and_reserved_terminal_projects(self):
        _, _, initial = self.loren_cargo_contract()
        fund = block(block(parsed(f"common/decisions/{BASE}_decisions.txt"), "NAM_consolidation"),
                     "NAM_hum_reconstruction_fund")
        focus = self.exile_trees["exile_corporate"][1]["NAM_board_reconstruction_tenders"]
        cash = ("NAM", "variable", "NAM_corp_capital")
        initial.update({("NAM", "has_country_flag", "NAM_consolidation_started"): True,
                        ("NAM", "variable", "NAM_consolidation"): 20,
                        ("700", "is_owned_by", "NAM"): True, ("700", "is_controlled_by", "NAM"): True,
                        ("700", "numeric", "infrastructure"): 5,
                        ("700", "variable", "fixture_building_slots_industrial_complex_yes"): 0,
                        ("NAM", "has_completed_focus", "NAM_board_reconstruction_tenders"): True})
        self.apply(block(focus, "completion_reward"), initial)
        self.assertNotIn(("700", "building", "infrastructure"), initial)
        before = initial[("NAM", "variable", "NAM_consolidation")]
        for terminal, project, slots, dockyards, ships in ((False, False, 0, 0, 0), (True, False, 1, 1, 0),
                                                          (False, True, 1, 1, 0), (True, False, 0, 0, 6)):
            facts = {**initial, cash: 60, ("700", "has_state_flag", "NAM_sea_terminal_built"): terminal,
                     ("700", "has_state_flag", "NAM_project_in_progress"): project,
                     ("700", "variable", "fixture_building_slots_dockyard_no"): slots}
            self.assertTrue(self.matches(block(fund, "visible"), facts))
            self.apply(block(fund, "complete_effect"), facts)
            self.apply(block(fund, "complete_effect"), facts)
            self.assertEqual(facts[cash], 0)
            self.assertTrue(facts[("700", "has_state_flag", "NAM_board_harbour_contract")])
            self.apply(block(fund, "remove_effect"), facts)
            self.apply(block(fund, "remove_effect"), facts)
            self.assertEqual(facts[("NAM", "variable", "NAM_consolidation")], before + 10)
            self.assertEqual(facts[("700", "has_state_flag", "NAM_sea_terminal_built")], terminal or not project)
            self.assertEqual(facts[("700", "has_state_flag", "NAM_project_in_progress")], project)
            self.assertEqual(facts.get(("700", "building", "dockyard"), 0), dockyards)
            self.assertEqual(facts.get(("NAM", "equipment", "convoy"), 0), ships)
            if not terminal and not project:
                self.assertEqual(facts[("NAM", "variable", "NAM_oil_terminal_units")], 1)
            self.assertFalse(facts[("700", "has_state_flag", "NAM_board_harbour_contract")])

    def test_lost_corporate_harbour_refunds_once_and_a_prior_humanist_deposit_keeps_its_terms(self):
        _, _, facts = self.loren_cargo_contract()
        fund = block(block(parsed(f"common/decisions/{BASE}_decisions.txt"), "NAM_consolidation"),
                     "NAM_hum_reconstruction_fund")
        cash = ("NAM", "variable", "NAM_corp_capital")
        licence = ("NAM", "has_completed_focus", "NAM_board_reconstruction_tenders")
        control = ("700", "is_controlled_by", "NAM")
        facts.update({cash: 60, licence: True, control: True, ("700", "is_owned_by", "NAM"): True,
                      ("NAM", "has_country_flag", "NAM_consolidation_started"): True,
                      ("NAM", "variable", "NAM_consolidation"): 20})
        for missing in (control, ("700", "is_owned_by", "NAM"), ("NAM", "is_subject", "no")):
            lost = dict(facts)
            self.apply(block(fund, "complete_effect"), lost)
            lost[missing] = False
            self.assertTrue(self.matches(block(fund, "cancel_trigger"), lost))
            self.apply(block(fund, "remove_effect"), lost)
            self.apply(block(fund, "cancel_effect"), lost)
            self.assertEqual(lost[cash], 60)
            self.assertEqual(lost[("NAM", "variable", "NAM_consolidation")], 20)
            self.assertFalse(lost[("700", "has_state_flag", "NAM_board_harbour_contract")])
        facts.update({licence: False, ("NAM", "has_completed_focus", "NAM_hum_harbour_rebuilding"): True})
        self.apply(block(fund, "complete_effect"), facts)
        self.assertEqual(facts[cash], 0)
        facts[licence] = True
        facts[control] = False
        self.assertFalse(self.matches(block(fund, "cancel_trigger"), facts))
        self.apply(block(fund, "remove_effect"), facts)
        self.assertEqual(facts[("NAM", "variable", "NAM_consolidation")], 30)
        self.assertFalse(facts.get(("700", "has_state_flag", "NAM_sea_terminal_built")))

    def test_domestic_contract_guard_protects_a_live_field_and_escorts_one_shortfall(self):
        lease, cargo, facts = self.loren_cargo_contract()
        cat = block(parsed(f"common/decisions/{BASE}_decisions.txt"), "NAM_free_zones")
        guard = self.bind_field(block(cat, "NAM_board_post_contract_guard"), "67")
        focus = self.exile_trees["exile_corporate"][1]["NAM_board_security_contracts"]
        self.apply(block(focus, "completion_reward"), facts)
        self.apply(block(lease, "completion_reward"), facts)
        facts[("NAM", "has_completed_focus", "NAM_board_security_contracts")] = True
        facts[("NAM", "has_completed_focus", "NAM_board_homeland_concession")] = True
        self.assertTrue(self.matches(block(guard, "visible"), facts))
        rifles = ("NAM", "equipment", "infantry_equipment")
        trucks = ("NAM", "equipment", "motorized_equipment")
        self.assertEqual((facts[rifles], facts[trucks]), (600, 40))
        for key, shortage in ((rifles, 299.99), (trucks, 19.99)):
            poor = {**facts, key: shortage}
            self.apply(block(guard, "complete_effect"), poor)
            self.assertFalse(poor.get(("67", "has_state_flag", "NAM_board_guard_post")))
        self.apply(block(guard, "complete_effect"), facts)
        self.apply(block(guard, "complete_effect"), facts)
        self.assertEqual((facts[rifles], facts[trucks]), (300, 20))
        facts[("67", "has_variable", "NAM_field_condition")] = True
        facts[("67", "variable", "NAM_field_damage_amount")] = 20
        self.apply(self.effects["NAM_field_apply_damage"], facts, "67")
        self.assertEqual(facts[("67", "variable", "NAM_field_condition")], 70)
        self.apply(block(cargo, "complete_effect"), facts)
        for deficit, held, delivered in ((-2, True, False), (-1, False, False), (-1, True, True)):
            outcome = {**facts, ("NAM", "variable", "NAM_oil_free_land_units"): deficit,
                       ("67", "is_controlled_by", "NAM"): held}
            self.assertEqual(self.matches(block(cargo, "cancel_trigger"), outcome), not delivered)
            self.apply(block(cargo, "remove_effect"), outcome)
            self.assertEqual(outcome[("NAM", "numeric", "has_fuel")], 15000 if delivered else 30000)
            self.assertEqual(outcome[("NAM", "variable", "NAM_corp_capital")], 37 if delivered else 12)

    def test_escort_of_a_disputed_district_pays_actual_coupons_without_assigning_votes_or_title(self):
        _, facts = self.war_share_issue()
        cat = block(parsed(f"common/decisions/{BASE}_decisions.txt"), "NAM_free_zones")
        guard = self.bind_field(block(cat, "NAM_board_post_contract_guard"), "701")
        facts.update({("NAM", "has_completed_focus", "NAM_board_security_contracts"): True,
                      ("NAM", "equipment", "infantry_equipment"): 300,
                      ("NAM", "equipment", "motorized_equipment"): 20,
                      ("701", "owner"): "EFL", ("701", "is_owned_by", "EFL"): True,
                      ("701", "is_controlled_by", "EFL"): True, ("701", "is_capital", "yes"): True,
                      ("EFL", "has_variable", "NAM_corp_dispute_claimant"): True,
                      ("EFL", "has_country_flag", "NAM_corp_disputed"): True,
                      ("EFL", "variable", "NAM_board_stock_coupon"): 2,
                      ("EFL", "has_variable", "NAM_board_stock_coupon"): True})
        self.assertTrue(self.matches(block(guard, "visible"), facts))
        self.apply(block(guard, "complete_effect"), facts)
        self.assertTrue(facts[("701", "has_state_flag", "NAM_board_guard_post")])
        settle = self.effects["NAM_corp_district_dividend"]
        self.apply(settle, facts, "EFL")
        self.assertEqual(facts[("EFL", "variable", "NAM_board_stock_coupon")], 3)
        self.assertFalse(self.matches(self.triggers["NAM_board_current_concession"], facts, "EFL"))
        self.apply(settle, facts, "EFL")
        self.apply(settle, facts, "EFL")
        self.assertEqual(facts[("NAM", "variable", "NAM_corp_dividend")], 8)
        self.assertEqual(facts[("EFL", "variable", "NAM_corp_district_owner")], 1)
        self.assertTrue(facts[("EFL", "has_country_flag", "NAM_corp_disputed")])
        for lost in (("701", "has_state_flag", "NAM_board_guard_post"), ("701", "is_controlled_by", "EFL"),
                     ("EFL", "is_subject_of", "NAM")):
            paused = {**facts, lost: False}
            self.apply(settle, paused, "EFL")
            self.assertEqual(paused[("NAM", "variable", "NAM_corp_dividend")], 8)

    def loren_cargo_contract(self):
        category = block(parsed(f"common/decisions/{BASE}_decisions.txt"), "NAM_free_zones")
        contract = block(category, "NAM_loren_book_oil_cargo")
        focus = self.exile_trees["exile_corporate"][1]["NAM_board_homeland_concession"]
        facts = self.captured_field_facts()
        facts.update(self.board_facts())
        facts.update({
            ("NAM", "has_global_flag", "NAM_war_of_return_won"): True,
            ("NAM", "variable", "NAM_oil_bonus_units"): 0,
            ("NAM", "numeric", "has_fuel"): 30000,
            ("NAM", "variable", "NAM_corp_capital"): 12,
        })
        self.apply(self.effects["NAM_oil_refresh"], facts)
        return focus, contract, facts

    def test_loren_lease_tracks_real_klyuchevsk_output_even_before_the_focus_flag_commits(self):
        focus, contract, facts = self.loren_cargo_contract()
        capacity = ("NAM", "variable", "NAM_oil_free_land_units")
        initial = facts[capacity]
        self.assertTrue(self.matches(block(focus, "available"), facts))
        self.assertFalse(self.matches(block(contract, "visible"), facts))
        self.apply(block(focus, "completion_reward"), facts)
        self.assertEqual(facts[capacity], initial + 1)
        self.assertEqual(facts[("NAM", "variable", "NAM_oil_bonus_units")], 0)
        self.assertEqual(facts[("NAM", "variable", "NAM_corp_capital")], 12)
        facts[("NAM", "has_completed_focus", "NAM_board_homeland_concession")] = True
        self.assertTrue(self.matches(block(contract, "visible"), facts))
        for owned, held, burnt, condition, bonus in (
                (True, True, False, 19, 0), (True, True, False, 20, 1), (True, True, True, 80, 0),
                (False, True, False, 80, 0), (True, False, False, 80, 0), (True, True, False, 80, 1)):
            with self.subTest(owned=owned, held=held, burnt=burnt, condition=condition):
                state = dict(facts)
                state[("67", "is_owned_by", "NAM")] = owned
                state[("67", "is_controlled_by", "NAM")] = held
                state[("67", "has_state_flag", "NAM_wells_scorched")] = burnt
                state[("67", "variable", "NAM_field_condition")] = condition
                ordinary = {**state, ("67", "has_state_flag", "NAM_loren_lease"): False}
                for snapshot in (ordinary, state):
                    self.apply(self.effects["NAM_oil_refresh"], snapshot)
                self.assertEqual(state[capacity] - ordinary[capacity], bonus)
                self.assertEqual(self.matches(block(focus, "available"), state), bool(bonus))
                self.assertEqual(self.matches(block(contract, "available"), state), bool(bonus))

    def test_loren_cargo_locks_its_price_and_releases_exactly_one_land_route(self):
        focus, contract, initial = self.loren_cargo_contract()
        self.apply(block(focus, "completion_reward"), initial)
        initial[("NAM", "has_completed_focus", "NAM_board_homeland_concession")] = True
        quote = ("NAM", "variable", "NAM_loren_cargo_quote")
        title = ("NAM", "variable", "NAM_board_lot_depots")
        cash = ("NAM", "variable", "NAM_corp_capital")
        fuel = ("NAM", "numeric", "has_fuel")
        capacity = ("NAM", "variable", "NAM_oil_free_land_units")
        for owner, price in ((0, 25), (1, 35), (6, 25)):
            facts = {**initial, title: owner, cash: 100000 - price, fuel: 15000}
            self.assertTrue(self.matches(block(contract, "available"), facts))
            for key, shortage in ((cash, 100000-price+0.01), (fuel, 14999.99), (capacity, 0)):
                invalid = {**facts, key: shortage}
                self.assertFalse(self.matches(block(contract, "available"), invalid))
                self.apply(block(contract, "complete_effect"), invalid)
                self.assertNotIn(quote, invalid)
            self.apply(block(contract, "complete_effect"), facts)
            self.apply(block(contract, "complete_effect"), facts)
            self.assertEqual((facts[quote], facts[capacity]), (price, initial[capacity]-1))
            self.assertEqual((facts[fuel], facts[cash]), (15000, 100000-price))
            if not owner:
                facts[title] = 1
            self.apply(block(contract, "remove_effect"), facts)
            self.apply(block(contract, "remove_effect"), facts)
            self.apply(block(contract, "cancel_effect"), facts)
            self.assertEqual((facts[fuel], facts[cash], facts[capacity]), (0, 100000, initial[capacity]))
            self.assertFalse(facts[("NAM", "has_variable", "NAM_loren_cargo_quote")])

    def test_invalid_loren_contract_returns_its_route_without_debiting_fuel_or_capital(self):
        focus, contract, facts = self.loren_cargo_contract()
        self.apply(block(focus, "completion_reward"), facts)
        facts[("NAM", "has_completed_focus", "NAM_board_homeland_concession")] = True
        self.apply(block(contract, "complete_effect"), facts)
        fuel = ("NAM", "numeric", "has_fuel")
        cash = ("NAM", "variable", "NAM_corp_capital")
        for key, changed, cancelled in (
                (("67", "is_owned_by", "NAM"), False, True), (("67", "is_controlled_by", "NAM"), False, True),
                (("67", "has_state_flag", "NAM_wells_scorched"), True, True),
                (("NAM", "is_subject", "no"), False, True),
                (("NAM", "variable", "NAM_oil_free_land_units"), -1, True),
                (fuel, 14999.99, False), (cash, 99975.01, False)):
            with self.subTest(key=key):
                lost = {**facts, key: changed}
                self.assertEqual(self.matches(block(contract, "cancel_trigger"), lost), cancelled)
                before = (lost[fuel], lost[cash])
                if cancelled:
                    self.apply(block(contract, "cancel_effect"), lost)
                self.apply(block(contract, "remove_effect"), lost)
                self.apply(block(contract, "cancel_effect"), lost)
                self.assertEqual((lost[fuel], lost[cash]), before)
                self.assertEqual(lost[("NAM", "variable", "NAM_oil_committed")], 0)
                self.assertFalse(lost[("NAM", "has_variable", "NAM_loren_cargo_quote")])


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
        endings = [name for name in self.focuses if name.startswith(("NAM_ladder_ending_", "NAM_charter_ending_"))]
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
            "NAM_balanced_accounts": ("NAM_prag_ending_republic", "NAM_prag_ending_directorate"),
        }
        effects = {
            "NAM_ladder_ending_iron": "NAM_apply_ending_iron",
            "NAM_ladder_ending_service": "NAM_apply_ending_service",
            "NAM_charter_ending_federation": "NAM_apply_ending_federation",
            "NAM_charter_ending_oil_union": "NAM_apply_ending_oil_union",
            "NAM_prag_ending_republic": "NAM_apply_ending_prag_republic",
            "NAM_prag_ending_directorate": "NAM_apply_ending_prag_directorate",
        }
        endings = {}
        for final, pair in finals.items():
            for name in pair:
                focus = self.focuses[name]
                self.assertEqual([e.value for e in block(focus, "prerequisite")], [final], name)
                other = next(n for n in pair if n != name)
                self.assertEqual([e.value for e in block(focus, "mutually_exclusive")], [other], name)
                reward = block(focus, "completion_reward")
                self.assertIn((effects[name], "yes"), [(e.key, e.value) for e in reward], name)
                markers = [fields["value"] for fields in ({e.key: e.value for e in entry.value}
                                                          for entry in walk(reward) if entry.key == "set_variable")
                           if fields.get("var") == "NAM_prog_ending"]
                self.assertEqual(len(markers), 1, name)
                endings[name] = markers[0]
                self.assertIn("ADISCORD_nam_groups.11", repr(reward), name)
                settlement = repr(self.effects[effects[name]])
                self.assertIn("NAM_ladder_settled", settlement, name)
                self.assertIn("NAM_coup_succeeded", settlement, name)
                self.assertIn("NAM_spirit_", settlement, name)
        self.assertEqual(sorted(endings.values()), ["1", "2", "3", "4", "5", "6"])
        for name in finals["NAM_balanced_accounts"]:
            self.assertIn("NAM_refresh_administration", repr(block(self.focuses[name], "completion_reward")), name)
            self.assertIn("NAM_rom_take_pragmatism", repr(self.effects[effects[name]]), name)

        def described(event):
            checks = ({e.key: e.value for e in entry.value} for entry in walk(event) if entry.key == "check_variable")
            return {fields["value"] for fields in checks
                    if fields.get("var") == "NAM_prog_ending" and fields.get("compare") == "equals"}

        events = {scalar(e.value, "id"): e.value for e in parsed(f"events/{BASE}_events.txt")
                  if e.key == "country_event"}
        self.assertEqual(described(events["ADISCORD_nam_groups.11"]), set(endings.values()))
        # Rom writes the last note only where an ending leaves him in office.
        rom_keeps_office = {endings[name] for name in ("NAM_ladder_ending_iron", "NAM_ladder_ending_service",
                                                       *finals["NAM_balanced_accounts"])}
        self.assertEqual(described(events["ADISCORD_nam_story.40"]), rom_keeps_office)
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
            council = {"NAM_supports_oil_compact": "oil", "NAM_supports_export_houses": "trade",
                       "NAM_garrison_assembly": "garr"}
            expected = f"NAM_council_{council[name]}_trust_tt" if name in council else f"NAM_grp_{name[4:]}_tt"
            self.assertIn(expected, tooltips, name)
            self.assertIn("NAM_groups_refresh", [e.key for e in walk(reward)], name)
            for language, text in texts.items():
                self.assertIn(f" {expected}:", text, (language, name))
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
                self.assertEqual(calls["NAM_groups_check_events"], 0)
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
            self.assertEqual(calls["NAM_groups_check_events"], 0)
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

    def test_colonial_localised_condition_still_requires_the_metropole(self):
        from tools.validators.validate_adiscord_nam_resource_war import named_block

        path = f"common/scripted_triggers/{BASE}_triggers.txt"
        source = read(path)
        colony = named_block(source, "NAM_colony_phase")
        self.assertIn("custom_trigger_tooltip", colony)
        changed = colony.replace("has_country_flag = NAM_center_vanished", "always = yes")
        self.assertNotEqual(changed, colony)
        self.assert_rejected("colonial programmes must close with the centre",
                             sources={path: source.replace(colony, changed)})

    def front_ai_issues(self, source):
        from tools.validators import validate_adiscord_nam_resource_war as validator

        with patch.object(validator, "ISSUES", []):
            validator.check_front_ai(source)
            return list(validator.ISSUES)

    def test_front_ai_accepts_conditional_overrides_and_multiline_baselines(self):
        source = read("common/ai_strategy/ADISCORD_nam_resource_war_ai.txt")
        self.assertEqual(self.front_ai_issues(source), [])
        self.assertEqual(self.front_ai_issues(source.replace(" = ", "\n=\n")), [])

    def test_front_ai_rejects_each_missing_baseline_despite_difficulty_overrides(self):
        from tools.validators.validate_adiscord_nam_resource_war import typed_blocks

        source = read("common/ai_strategy/ADISCORD_nam_resource_war_ai.txt")
        baselines = [
            strategy for strategy in typed_blocks(source, "ai_strategy")
            if "type = front_control" in strategy and "country_trigger" not in strategy
        ]
        self.assertEqual(len(baselines), 9)
        for baseline in baselines:
            with self.subTest(baseline=baseline.strip()):
                issues = self.front_ai_issues(source.replace(baseline, "", 1))
                self.assertTrue(any("expected one baseline front_control" in issue for issue in issues), issues)

    def test_front_ai_rejects_wrong_target_priority_and_attack_policy(self):
        source = read("common/ai_strategy/ADISCORD_nam_resource_war_ai.txt")
        for original, replacement, field in (
            ("tag = NAM ratio", "tag = EFL ratio", "tag"),
            ("priority = 1500", "priority = 1200", "priority"),
            ("execution_type = rush ", "execution_type = careful ", "execution_type"),
            ("manual_attack = yes", "manual_attack = no", "manual_attack"),
        ):
            with self.subTest(field=field):
                issues = self.front_ai_issues(source.replace(original, replacement, 1))
                expected = f"ADISCORD_nam_resource_war_eflor_offensive: baseline front_control requires {field} ="
                self.assertTrue(any(expected in issue for issue in issues), issues)

    def test_front_ai_checks_nested_difficulty_coverage_ratios(self):
        source = read("common/ai_strategy/ADISCORD_nam_resource_war_ai.txt")
        for replacement in ("ratio = 1", "ratio = -0.1", "ratio = invalid", ""):
            with self.subTest(replacement=replacement):
                changed = source.replace("\t\tratio = 0.01", f"\t\t{replacement}", 1)
                self.assertNotEqual(changed, source)
                issues = self.front_ai_issues(changed)
                self.assertTrue(any("front_control needs one coverage ratio" in issue for issue in issues), issues)

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
        for tag, amount in (("SLF", 18000), ("NAM", 15000)):
            with self.subTest(tag=tag):
                token = f"type = infantry_equipment amount = {amount} producer = {tag}"
                self.assertEqual(source.count(token), 1)
                changed = source.replace(token, token.replace(str(amount), str(amount // 10)))
                message = "emergency defence" if tag == "NAM" else f"stockpile for {tag}"
                self.assert_rejected(message, sources={path: changed})

    def test_wrong_coalition_muster_reserves_still_fail(self):
        path = f"common/scripted_effects/{BASE}_effects.txt"
        source = read(path)
        for variable, amount in (("NAM_rw_rifle_reserve", 20000), ("NAM_rw_rifle_reserve", 12000)):
            token = f"var = {variable} value = {amount} "
            self.assertEqual(source.count(token), 1)
            changed = source.replace(token, token.replace(str(amount), str(amount // 10)))
            self.assert_rejected("coalition muster", sources={path: changed})

    def test_global_one_shot_news_still_fail(self):
        from tools.validators.validate_adiscord_nam_resource_war import typed_blocks

        path = f"events/{BASE}_events.txt"
        source = read(path)
        for event in typed_blocks(source, "news_event"):
            event_id = re.search(r"\bid\s*=\s*(\S+)", event)[1]
            with self.subTest(event=event_id):
                self.assertEqual(event.count("fire_only_once = no"), 1)
                changed = source.replace(event, event.replace("fire_only_once = no", "fire_only_once = yes"))
                self.assert_rejected(event_id, sources={path: changed})

    def test_return_war_news_require_each_terminal_dispatch(self):
        from tools.validators.validate_adiscord_nam_resource_war import named_block

        path = f"common/scripted_effects/{BASE}_effects.txt"
        source = read(path)
        for effect, event_id in (
            ("NAM_wor_annex_svetlogorye", "ADISCORD_nam_resource_news.8"),
            ("NAM_war_of_return_resolve_victory", "ADISCORD_nam_resource_news.9"),
            ("NAM_great_war_resolve_victory", "ADISCORD_nam_resource_news.9"),
        ):
            with self.subTest(effect=effect):
                body = named_block(source, effect)
                call = f"news_event = {{ id = {event_id} hours = 1 }}"
                self.assertEqual(body.count(call), 1)
                changed = source.replace(body, body.replace(call, ""))
                self.assert_rejected(effect, sources={path: changed})

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
            (67, "victory_points = { 6099 10 }", "victory_points = { 6099 10 }\n victory_points = { 1710 1 }"),
            (70, "victory_points = { 1198 10 }", ""),
            (70, "victory_points = { 16900 10 }", "victory_points = { 16900 5 }"),
            (70, "victory_points = { 16901 10 }", ""),
            (688, "victory_points = { 16721 25 }", "victory_points = { 689 5 }"),
            (689, "history = {", "history = {\n victory_points = { 2038 5 }"),
            (700, "victory_points = { 16716 20 }", "victory_points = { 16716 4 }"),
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

    def test_board_window_places_six_company_cards_in_three_nonoverlapping_rows(self):
        category = block(parsed(f"common/decisions/categories/{BASE}_categories.txt"), "NAM_free_zones")
        root = block(parsed("common/scripted_guis/ADISCORD_NAM_scripted_gui.txt"), "scripted_gui")
        panel = block(root, scalar(category, "scripted_gui"))
        for takeover in (True, False):
            facts = {("NAM", "has_country_flag", "NAM_corp_takeover"): takeover}
            self.assertEqual(matches_conditions(block(panel, "visible"), facts, "NAM"), takeover)
        gui = block(parsed("interface/ADISCORD_NAM_basin.gui"), "guiTypes")
        window = next(e.value for e in gui if scalar(e.value, "name") == scalar(panel, "window_name"))
        width = int(scalar(block(window, "size"), "width"))
        height = int(scalar(block(window, "size"), "height"))
        boxes = {scalar(e.value, "name"): e.value for e in window if e.key == "instantTextBoxType"}
        rows = {}
        for i in range(1, 7):
            key = f"NAM_board_seat_{i}"
            card = boxes[key]
            self.assertEqual(scalar(card, "text"), key)
            self.assertEqual(scalar(card, "pdx_tooltip"), key + "_tt")
            x, y = (int(scalar(block(card, "position"), coord)) for coord in ("x", "y"))
            right = x + int(scalar(card, "maxWidth"))
            bottom = y + int(scalar(card, "maxHeight"))
            self.assertTrue(0 <= x < right <= width and 0 <= y < bottom <= height)
            rows.setdefault(y, []).append((x, right, bottom))
        self.assertEqual([len(row) for _, row in sorted(rows.items())], [1, 2, 3])
        previous_bottom = 0
        for y, row in sorted(rows.items()):
            self.assertLess(previous_bottom, y)
            self.assertTrue(all(left[1] < right[0] for left, right in zip(row, row[1:])))
            previous_bottom = max(card[2] for card in row)
        for asset in ("oil", "coast", "labour", "rail", "yards", "depots"):
            name = "NAM_board_registry_" + asset
            self.assertEqual(scalar(boxes[name], "pdx_tooltip"), name + "_tt")

    def test_board_rank_selects_the_same_company_emblem_votes_minister_and_industrial_rates(self):
        gui = block(parsed("interface/ADISCORD_NAM_basin.gui"), "guiTypes")
        window = next(e.value for e in gui if scalar(e.value, "name") == "ADISCORD_NAM_board_window")
        icons = {scalar(e.value, "name"): e.value for e in window if e.key == "iconType"}
        scripted = block(parsed("common/scripted_guis/ADISCORD_NAM_scripted_gui.txt"), "scripted_gui")
        properties = block(block(scripted, "ADISCORD_NAM_board_panel"), "properties")
        for rank in range(1, 7):
            name = f"NAM_board_mark_{rank}"
            self.assertEqual(scalar(icons[name], "spriteType"), "GFX_NAM_board_company_marks")
            self.assertEqual(scalar(icons[name], "pdx_tooltip"), f"NAM_board_seat_{rank}_tt")
            self.assertEqual(scalar(block(properties, name), "frame"), f"NAM_board_rank_{rank}")
        texts = {scalar(e.value, "name"): e.value for e in parsed(
            f"common/scripted_localisation/{BASE}_scripted_loc.txt") if e.key == "defined_text"}
        for rank, kind in product(range(1, 7), ("Card", "Details")):
            branches = [e.value for e in texts[f"NAMBoardSeat{rank}{kind}"] if e.key == "text"]
            choices = {scalar(block(block(e, "trigger"), "check_variable"), f"NAM_board_rank_{rank}"):
                       scalar(e, "localization_key") for e in branches[:-1]}
            self.assertEqual(choices, {str(i): f"NAM_board_company_{i}_{kind.lower()}" for i in range(1, 7)})
            self.assertEqual(scalar(branches[-1], "localization_key"), "NAM_board_seat_empty")
        for i in range(1, 7):
            statuses = [e.value for e in texts[f"NAMBoardRepresentative{i}"] if e.key == "text"]
            self.assertEqual([scalar(s, "localization_key") for s in statuses],
                             ["NAM_board_rep_appointed", "NAM_board_rep_discontent",
                              "NAM_board_rep_waiting", "NAM_board_rep_absent"])
            self.assertEqual(scalar(block(statuses[0], "trigger"), f"NAM_board_minister_{i}"), "yes")
            condition = block(block(statuses[1], "trigger"), "check_variable")
            self.assertEqual([e.value for e in condition], [f"NAM_board_rate_a_{i}", "<", "0"])
            deadline = block(block(statuses[2], "trigger"), "check_variable")
            self.assertEqual(scalar(deadline, "var"), f"NAM_board_objection_days^{i}")
            self.assertEqual((scalar(deadline, "value"), scalar(deadline, "compare")), ("0", "greater_than"))
            waiting = block(statuses[2], "trigger")
            timer = "NAM_board_days_to_boycott"
            for operation, source in (("set_temp_variable", f"NAM_board_objection_days^{i}"),
                                      ("subtract_from_temp_variable", "global.num_days")):
                calculation = block(waiting, operation)
                self.assertEqual((scalar(calculation, "var"), scalar(calculation, "value")), (timer, source))
            self.assertNotIn("trigger", [e.key for e in statuses[3]])
        board_triggers = parsed(f"common/scripted_triggers/{BASE}_triggers.txt")
        for lang in ("russian", "english"):
            source = read(f"localisation/{lang}/{BASE}_l_{lang}.yml")
            loc = {m[1]: m[2] for line in source.splitlines() if (m := ENTRY.match(line))}
            self.assertIn("[?NAM_board_days_to_boycott|0]", loc["NAM_board_rep_waiting"])
            for i in range(1, 7):
                card = loc[f"NAM_board_company_{i}_card"]
                details = loc[f"NAM_board_company_{i}_details"]
                self.assertIn(f"£NAM_board_mark_texticon|{i} ", details)
                for value in (card, details):
                    self.assertIn(f"[?NAM_board_votes_{i}|0]", value)
                    self.assertIn(f"[?NAM_board_rate_a_{i}|=+1]%", value)
                    colour = "-" if i == 6 else "+"
                    self.assertIn(f"[?NAM_board_rate_b_{i}|={colour}1]%", value)
                    self.assertIn(f"[NAMBoardRepresentative{i}]", value)
                self.assertIn(f"[?NAM_board_sectors_{i}|0]", details)
                self.assertIn(f"[?NAM_board_districts_{i}|0]", details)
                profile = loc[f"NAM_board_profile_{i}"]
                tender = loc[f"NAM_board_tender_bid_{i}_tt"]
                minister = scalar(block(board_triggers, f"NAM_board_minister_{i}"), "has_idea")
                self.assertIn(f"${minister}$", tender)
                self.assertIn(f"${minister}$", details)
                self.assertIn(f"[NAMBoardRepresentative{i}]", tender)
                self.assertIn(f"$NAM_board_profile_{i}$", tender)
                pairs = re.findall(r"§G([+-][\d.,]+)%§! / §R([+-][\d.,]+)%§!", profile)
                self.assertEqual(len(pairs), 2, (lang, i))
                for (appointed, boycott), (_, bonus) in zip(pairs, BOARD_PROFILES[i - 1]):
                    self.assertEqual(float(appointed.replace(",", ".")), bonus)
                    self.assertEqual(float(boycott.replace(",", ".")), -bonus / 2)
            self.assertIn("$NAM_board_labor_nominee$", loc["NAM_board_company_5_details"])
            self.assertIn("$NAM_board_bank_nominee$", loc["NAM_board_company_6_details"])
        for asset, buyers in (("Rail", (2, 5)), ("Yards", (3, 4)), ("Depots", (1, 6))):
            branches = [e.value for e in texts["NAMBoardOwner" + asset] if e.key == "text"]
            self.assertEqual([scalar(e, "localization_key") for e in branches],
                             [*(f"NAM_board_short_{i}" for i in buyers), "NAM_board_public_owner"])

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
        roots = block(parse_clausewitz(gui), "guiTypes")
        window = next(e.value for e in roots if scalar(e.value, "name") == "ADISCORD_NAM_supports_window")
        width = int(scalar(block(window, "size"), "width"))
        height = int(scalar(block(window, "size"), "height"))
        rectangles = []
        for child in window:
            if child.key not in ("instantTextBoxType", "containerWindowType"):
                continue
            x = int(scalar(block(child.value, "position"), "x"))
            y = int(scalar(block(child.value, "position"), "y"))
            size = block(child.value, "size") if child.key == "containerWindowType" else child.value
            w = int(scalar(size, "width" if child.key == "containerWindowType" else "maxWidth"))
            h = int(scalar(size, "height" if child.key == "containerWindowType" else "maxHeight"))
            self.assertTrue(0 <= x < x + w <= width and 0 <= y < y + h <= height)
            for ox, oy, ow, oh in rectangles:
                self.assertFalse(x < ox + ow and ox < x + w and y < oy + oh and oy < y + h)
            rectangles.append((x, y, w, h))
        for language in ("russian", "english"):
            loc = read(f"localisation/{language}/{BASE}_l_{language}.yml")
            for group in ("nam", "oil", "dist", "garr", "trade"):
                self.assertIn(f'NAM_bw_support_{group}', gui)
                row = re.search(rf'^ NAM_bw_support_{group}:.*$', loc, re.M).group()
                self.assertIn(f"NAM_grp_{group}_support", row)
                self.assertIn(f"NAM_grp_{group}_influence", row)
            for key, values in (
                ("NAM_bw_support_rules", ("NAM_loyalty", "70", "25", "50")),
                ("NAM_bw_support_agreements_tt", ("90", "180", "365", "300", "+15", "-20", "-5")),
                ("NAM_bw_support_contracts_tt", ("120", "+12")),
                ("NAM_bw_support_crisis_tt", ("90", "40", "25", "-10%", "-50")),
            ):
                self.assertIn(f'pdx_tooltip = "{key}"', gui)
                row = re.search(rf'^ {key}:.*$', loc, re.M).group()
                self.assertLess(len(row), 1200)
                for value in values:
                    self.assertIn(value, row)
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
                ("NAM", "NAM_field_repair_unlocked", "yes"): True,
                ("NAM", "NAM_postwar_refinery_authorized", "yes"): True,
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

    def test_map_describes_the_delivered_repair_and_refinery_programme(self):
        source = parsed(f"common/scripted_localisation/{BASE}_scripted_loc.txt")
        definitions = {scalar(entry.value, "name"): entry.value for entry in source
                       if entry.key == "defined_text"}
        for widget, focus, expected in (
            ("Repair", "NAM_rescue_college", "100"),
            ("Refinery", "NAM_pw_refinery_engineering", "45000"),
        ):
            variants = [entry.value for entry in definitions["NAMBasin" + widget + "Body"]
                        if entry.key == "text"]
            self.assertEqual(scalar(block(variants[0], "trigger"), "has_completed_focus"), focus)
            self.assertFalse(any(entry.key == "trigger" for entry in variants[-1]))
            for language in ("russian", "english"):
                values = dict(re.findall(r'^ (\w+):\d* "(.*)"$', read(
                    f"localisation/{language}/{BASE}_l_{language}.yml"), re.M))
                self.assertIn(expected, values[scalar(variants[0], "localization_key")])

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
                for key in (f"NAM_council_{group}_trust_tt", f"NAM_favour_{group}_tt"):
                    self.assertRegex(values[key], rf'§[GRY][+-]\d+§! £NAM_support_{group}_texticon')
                self.assertIn(f"£NAM_support_{group}_texticon", values["NAM_grp_independence_day_tt"])
                contract = {"nam": "registrar_contract", "oil": "fuel_reserve",
                            "dist": "workshop_contract", "garr": "arsenal_contract",
                            "trade": "import_machinery"}[group]
                for phase in ("delivered", "result"):
                    self.assertIn(f"§G+12§! £NAM_support_{group}_texticon",
                                  values[f"NAM_council_{contract}_{phase}_tt"])


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
        for owned, prepared, authorized, foreign_neighbour in product((False, True), repeat=4):
            facts = {
                ("67", "is_owned_by", "NAM"): owned,
                ("67", "has_state_flag", "NAM_line_prepared"): prepared,
                ("NAM", "NAM_permanent_lines_authorized", "yes"): authorized,
                ("67", "any_neighbor_state", "yes"): foreign_neighbour,
            }
            self.assertEqual(matches_conditions(fixture, facts, "67"),
                             owned and not prepared and authorized and foreign_neighbour)
            if not authorized:
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
            elif entry.key == "NAM_piracy_open":
                self.assertEqual((gauge, entry.value), ("revenge", "yes"))
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
    def test_every_decision_unlock_has_a_summary_in_the_same_reward_scope(self):
        def check_scope(entries, context):
            for index, entry in enumerate(entries):
                if entry.key == "unlock_decision_tooltip":
                    with self.subTest(context=context, decision=entry.value):
                        self.assertLess(index + 1, len(entries))
                        summary = entries[index + 1]
                        self.assertEqual(summary.key, "custom_effect_tooltip")
                        expected = ("NAM_rescue_college_service_tt" if context[1] == "NAM_rescue_college"
                                    else entry.value + "_unlock_tt")
                        self.assertEqual(summary.value, expected)
                if isinstance(entry.value, list):
                    check_scope(entry.value, context)

        for kind in TREES:
            _, focuses = tree_focuses(kind)
            for name, focus in focuses.items():
                check_scope(block(focus, "completion_reward"), (kind, name))

    def test_unlock_summaries_load_in_both_languages_without_decision_target_scope(self):
        keys = set()
        for kind in TREES:
            _, focuses = tree_focuses(kind)
            for focus in focuses.values():
                keys.update(entry.value + "_unlock_tt"
                            for entry in walk(block(focus, "completion_reward"))
                            if entry.key == "unlock_decision_tooltip")

        for language in ("russian", "english"):
            path = ROOT / f"localisation/{language}/{BASE}_l_{language}.yml"
            self.assertTrue(path.read_bytes().startswith(b"\xef\xbb\xbf"))
            localisation = {}
            for line in path.read_text(encoding="utf-8-sig").splitlines():
                match = ENTRY.match(line)
                if match:
                    localisation[match[1]] = match[2]

            def expand(key, ancestors=()):
                self.assertNotIn(key, ancestors, "Cyclic localisation substitution")
                self.assertIn(key, localisation)
                value = localisation[key]
                self.assertNotIn("_desc$", value)
                return re.sub(r"\$(NAM_[\w.]+)\$",
                              lambda match: expand(match[1], ancestors + (key,)), value)

            for key in keys:
                with self.subTest(language=language, key=key):
                    value = expand(key)
                    self.assertTrue(value.strip())
                    self.assertNotIn("FROM.", value)
                    self.assertNotIn("\\n\\n", value)
                    self.assertLess(len(value), 650, "Keep unlock summaries compact")

    def test_agreements_replace_both_petition_channels_and_preserve_story_coup(self):
        effects = read(f"common/scripted_effects/{BASE}_effects.txt")
        events = read(f"events/{BASE}_events.txt")
        for obsolete in ("NAM_groups_check_events", "NAM_rival_demand", "NAM_political_petition_cooldown"):
            self.assertNotIn(obsolete, effects + events)
        self.assertNotRegex(events, r"id = ADISCORD_nam_groups\.[12]\s")
        parsed_effects = parse_clausewitz(effects)
        rivals = block(parsed_effects, "NAM_rivals_monthly")
        story = block(block(rivals, "if"), "limit")
        self.assertIn("NAM_coup_pending", repr(story))
        self.assertNotIn("NAM_agreement_cooldown", repr(story))
        monthly = block(parsed_effects, "NAM_ladder_monthly")
        self.assertIn("NAM_agreement_cancel", repr(next(e.value for e in monthly if e.key == "if")))
        finish = block(parsed_effects, "NAM_agreement_finish")
        self.assertEqual(scalar(block(finish, "set_country_flag"), "days"), "300")

    def test_underground_actions_explain_temporary_blockers(self):
        categories = parsed(f"common/decisions/categories/{BASE}_categories.txt")
        underground = block(categories, "NAM_underground")
        self.assertEqual(scalar(block(underground, "visible"), "has_variable"), "NAM_underground")
        for name in ("NAM_underground", "NAM_national_programmes", "NAM_treasury"):
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
                 (70, "bonus"), (84.5, "bonus"), (85, "bonus"))
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
