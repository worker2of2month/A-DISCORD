from __future__ import annotations

import re
import unittest

from tools.validators.validate_adiscord_division_templates import parse_clausewitz
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
AI_PATH = ROOT / "common/ai_strategy/default.txt"


def named_block(source: str, name: str) -> str:
    match = re.search(rf"(?m)^\s*{re.escape(name)}\s*=\s*\{{", source)
    if match is None:
        return ""
    opening = source.find("{", match.start())
    depth = 0
    for index in range(opening, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[match.start() : index + 1]
    raise AssertionError(f"unterminated block: {name}")


def named_blocks(source: str, name: str) -> list[str]:
    blocks: list[str] = []
    pattern = re.compile(rf"(?m)^\s*{re.escape(name)}\s*=\s*\{{")
    position = 0
    while True:
        match = pattern.search(source, position)
        if match is None:
            return blocks
        opening = source.find("{", match.start())
        depth = 0
        for index in range(opening, len(source)):
            if source[index] == "{":
                depth += 1
            elif source[index] == "}":
                depth -= 1
                if depth == 0:
                    blocks.append(source[match.start() : index + 1])
                    position = index + 1
                    break
        else:
            raise AssertionError(f"unterminated block: {name}")


class GenericWartimeFrontTests(unittest.TestCase):
    def test_every_war_gets_a_dynamic_front_request(self) -> None:
        source = AI_PATH.read_text(encoding="utf-8-sig")
        profile = named_block(source, "ADISCORD_active_enemy_front_concentration")
        self.assertTrue(profile, "missing generic wartime front policy")

        enable = named_block(profile, "enable")
        self.assertIn("is_ai = yes", enable)
        self.assertIn("has_war = yes", enable)
        self.assertNotIn("enemies^num", enable)
        self.assertIn("abort_when_not_enabled = yes", profile)

        requests = [
            block
            for block in named_blocks(profile, "ai_strategy")
            if re.search(r"\btype\s*=\s*front_unit_request\b", block)
        ]
        self.assertEqual(len(requests), 1)
        request = requests[0]
        country_trigger = named_block(request, "country_trigger")
        self.assertIn("has_war_with = FROM", country_trigger)
        self.assertNotIn("has_capitulated", country_trigger)
        self.assertRegex(request, r"\bvalue\s*=\s*50\b")

    def test_generic_fallback_changes_allocation_not_campaign_behavior(self) -> None:
        source = AI_PATH.read_text(encoding="utf-8-sig")
        profile = named_block(source, "ADISCORD_active_enemy_front_concentration")
        self.assertTrue(profile)
        self.assertNotIn("type = front_control", profile)
        self.assertNotIn("type = dont_defend_ally_borders", profile)
        self.assertNotIn("type = put_unit_buffers", profile)
        self.assertNotIn("type = role_ratio id = garrison", profile)


class FrontAllocationLifecycleTests(unittest.TestCase):
    """Evaluate the actual shared predicates; this does not simulate engine movement."""

    def setUp(self) -> None:
        self.profiles = {entry.key: entry.value for entry in parse_clausewitz(
            AI_PATH.read_text(encoding="utf-8"))}
        path = ROOT / "common/scripted_triggers/ADISCORD_scripted_triggers_generic.txt"
        self.triggers = {entry.key: entry.value for entry in parse_clausewitz(
            path.read_text(encoding="utf-8"))}
        self.countries = {tag: {"ai": True, "capitulated": False, "faction": None}
                          for tag in ("STS", "STP", "NOD", "VAL", "SRP")}
        self.wars = {frozenset(("STS", "STP"))}
        self.goals = set()
        self.justifying = set()
        self.preparation = {}
        self.neighbors = {tag: set(self.countries) - {tag} for tag in self.countries}

    def evaluate(self, entries, scope, actor, previous=None):
        def target(value):
            return {"THIS": scope, "FROM": actor, "PREV": previous}.get(value, value)

        def matches(entry):
            key, value = entry.key, entry.value
            if key in ("AND", "OR", "NOT"):
                results = [self.evaluate([child], scope, actor, previous) for child in value]
                return {"AND": all(results), "OR": any(results), "NOT": not any(results)}[key]
            if key in self.triggers:
                return self.evaluate(self.triggers[key], scope, actor, previous) == (value == "yes")
            if key == "FROM":
                return self.evaluate(value, actor, actor, scope)
            if key == "PREV":
                return self.evaluate(value, previous, actor, scope)
            if key == "any_neighbor_country":
                return any(self.evaluate(value, neighbor, actor, scope)
                           for neighbor in self.neighbors[scope])
            if key == "has_war_with":
                return frozenset((scope, target(value))) in self.wars
            if key == "has_wargoal_against":
                return (scope, target(value)) in self.goals
            if key == "is_justifying_wargoal_against":
                return (scope, target(value)) in self.justifying
            if key == "is_in_faction_with":
                faction = self.countries[scope]["faction"]
                return faction is not None and faction == self.countries[target(value)]["faction"]
            if key == "check_variable":
                fields = {child.key: child.value for child in value}
                variable = fields["var"]
                owner = (actor if variable.startswith("FROM.") else
                         previous if variable.startswith("PREV.") else scope)
                other = target(variable.split("@")[1])
                self.assertEqual(fields["compare"], "greater_than")
                return self.preparation.get((owner, other), 0) > float(fields["value"])
            if key in ("is_ai", "has_war", "has_capitulated", "exists"):
                actual = {"is_ai": self.countries[scope]["ai"],
                          "has_war": any(scope in pair for pair in self.wars),
                          "has_capitulated": self.countries[scope]["capitulated"],
                          "exists": True}[key]
                return actual == (value == "yes")
            raise AssertionError(f"Unsupported front predicate: {key}")

        return all(matches(entry) for entry in entries)

    def request(self, actor, target):
        total = 0
        names = ("ADISCORD_active_enemy_front_concentration",
                 "ADISCORD_wartime_neutral_borders", "ADISCORD_prewar_front_concentration")
        for name in names:
            profile = self.profiles[name]
            enable = next(entry.value for entry in profile if entry.key == "enable")
            if not self.evaluate(enable, actor, actor):
                continue
            for entry in profile:
                if entry.key != "ai_strategy":
                    continue
                fields = {child.key: child.value for child in entry.value}
                if self.evaluate(fields["country_trigger"], target, actor):
                    total += int(fields["value"])
        return total

    def test_second_enemy_does_not_release_neutral_border_or_first_front(self):
        self.assertEqual(self.request("STS", "STP"), 50)
        self.assertEqual(self.request("STS", "VAL"), -100)
        self.wars.add(frozenset(("STS", "NOD")))
        self.assertEqual(self.request("STS", "STP"), 50)
        self.assertEqual(self.request("STS", "NOD"), 50)
        self.assertEqual(self.request("STS", "VAL"), -100)

    def test_capitulated_enemy_retains_front_and_liberation_needs_no_reset(self):
        self.countries["STP"]["capitulated"] = True
        self.assertEqual(self.request("STS", "STP"), 50)
        self.countries["STP"]["capitulated"] = False
        self.assertEqual(self.request("STS", "STP"), 50)

    def test_preparation_from_either_side_is_protected_and_releases_on_cancel(self):
        for pair in (("STS", "NOD"), ("NOD", "STS")):
            with self.subTest(pair=pair):
                self.preparation[pair] = 100
                self.assertEqual(self.request("STS", "NOD"), 50)
                self.preparation.clear()
                self.assertEqual(self.request("STS", "NOD"), -100)

    def test_human_wargoals_and_justification_protect_defensive_front(self):
        self.countries["NOD"]["ai"] = False
        for collection in (self.goals, self.justifying):
            for pair in (("NOD", "STS"), ("STS", "NOD")):
                with self.subTest(pair=pair, collection=type(collection)):
                    collection.add(pair)
                    self.assertEqual(self.request("STS", "NOD"), 50)
                    collection.clear()
                    self.assertEqual(self.request("STS", "NOD"), -100)

    def test_threat_becomes_war_without_stacking_prewar_request(self):
        self.preparation[("STS", "NOD")] = 100
        self.wars.add(frozenset(("STS", "NOD")))
        self.assertEqual(self.request("STS", "NOD"), 50)

    def test_peace_releases_neutral_reduction_but_allows_new_preparation(self):
        self.wars.clear()
        self.assertEqual(self.request("STS", "NOD"), 0)
        self.preparation[("STS", "NOD")] = 100
        self.assertEqual(self.request("STS", "NOD"), 50)
        self.preparation.clear()
        self.assertEqual(self.request("STS", "NOD"), 0)

    def test_adjacent_preparation_releases_other_peaceful_borders_until_cancelled(self):
        self.wars.clear()
        for collection in (self.preparation, self.goals, self.justifying):
            for pair in (("STS", "NOD"), ("NOD", "STS")):
                with self.subTest(pair=pair, collection=type(collection)):
                    if isinstance(collection, dict):
                        collection[pair] = 100
                    else:
                        collection.add(pair)
                    self.assertEqual(self.request("STS", "NOD"), 50)
                    self.assertEqual(self.request("STS", "VAL"), -100)
                    collection.clear()
                    self.assertEqual(self.request("STS", "VAL"), 0)

    def test_remote_or_allied_preparation_does_not_empty_peaceful_borders(self):
        self.wars.clear()
        self.preparation[("NOD", "STS")] = 100
        self.neighbors["STS"].remove("NOD")
        self.assertEqual(self.request("STS", "VAL"), 0)
        self.neighbors["STS"].add("NOD")
        self.countries["NOD"]["faction"] = "allies"
        self.countries["STS"]["faction"] = "allies"
        self.assertEqual(self.request("STS", "VAL"), 0)
        self.countries["NOD"]["faction"] = None
        self.countries["NOD"]["capitulated"] = True
        self.assertEqual(self.request("STS", "VAL"), 0)

    def test_srp_independent_war_survives_end_of_party_war(self):
        self.wars = {frozenset(("SRP", "VAL"))}
        self.assertEqual(self.request("SRP", "VAL"), 50)
        self.assertEqual(self.request("SRP", "STP"), -100)

    def test_human_armies_receive_no_shared_allocation_override(self):
        self.countries["STS"]["ai"] = False
        self.assertEqual(self.request("STS", "STP"), 0)
        self.assertEqual(self.request("STS", "NOD"), 0)


class PreparationLifecycleTests(unittest.TestCase):
    """Exercise authored preparation gates with explicit campaign snapshots.

    Complex pre-existing territorial predicates are fixture inputs. These tests
    check our routing and lifecycle; they cannot establish native AI movement.
    """

    def setUp(self):
        ai_paths = ("ADISCORD_STP_civil_war", "ADISCORD_vorkerland_ai",
                    "ADISCORD_nam_resource_war_ai", "VAL")
        trigger_paths = ("ADISCORD_STP_scripted_triggers", "ADISCORD_vorkerland_triggers",
                         "ADISCORD_nam_resource_war_triggers", "ADISCORD_VAL_rework_triggers")
        self.profiles = {e.key: e.value for name in ai_paths for e in parse_clausewitz(
            (ROOT / f"common/ai_strategy/{name}.txt").read_text(encoding="utf-8"))}
        self.triggers = {e.key: e.value for name in trigger_paths for e in parse_clausewitz(
            (ROOT / f"common/scripted_triggers/{name}.txt").read_text(encoding="utf-8"))}
        self.tags = set("NOD STP STS SRP VAL YPR COF TFF NAM EFL AZH IVN PWR ZAO WPA WPS PSD VAD SRA CSL CIN OSF APH ERT WKR TVA EYR EGC RIV REV YOR NDN SWB VHV OSV SOL".split())
        self.flags = {tag: set() for tag in self.tags}
        self.globals = set()
        self.subjects = {}
        self.factions = {}
        self.capitulated = set()
        self.humans = set()
        self.wars = set()
        self.decisions = set()
        self.focuses = {}
        self.completed = set()
        self.variables = {}
        self.stats = {"num_divisions": 20, "has_manpower": 15000,
                      "has_stability": 0.5, "has_war_support": 0.6}
        self.facts = {}

    def evaluate(self, entries, scope, root):
        # The repository parser preserves comparison triples as anonymous tokens.
        # Interpret those operators explicitly instead of rewriting game syntax.
        def compare(left, op, right):
            return {">": left > right, "<": left < right, "=": left == right}[op]

        def one(entry):
            key, value = entry.key, entry.value
            if key in ("AND", "OR", "NOT"):
                outcomes = [self.evaluate([child], scope, root) for child in value]
                return {"AND": all(outcomes), "OR": any(outcomes), "NOT": not any(outcomes)}[key]
            if key in self.tags and isinstance(value, list):
                return self.evaluate(value, key, root)
            if key in self.facts:
                return self.facts[key] == (value == "yes")
            if key in self.triggers:
                return self.evaluate(self.triggers[key], scope, root) == (value == "yes")
            if key == "tag":
                return scope == value
            if key == "has_country_flag":
                return value in self.flags[scope]
            if key == "has_global_flag":
                return value in self.globals
            if key == "country_exists":
                return value in self.tags
            if key == "has_war_with":
                target = root if value == "ROOT" else value
                return frozenset((scope, target)) in self.wars
            if key == "is_subject_of":
                return self.subjects.get(scope) == value
            if key == "is_in_faction_with":
                return scope in self.factions and self.factions[scope] == self.factions.get(value)
            if key == "has_decision":
                return (scope, value) in self.decisions
            if key == "has_completed_focus":
                return (scope, value) in self.completed
            if key == "focus_progress":
                focus = next(child.value for child in value if child.key == "focus")
                tokens = [child.value for child in value if not child.key]
                self.assertEqual(tokens, ["progress", ">", "0"])
                return self.focuses.get(scope) == focus
            if key == "check_variable":
                fields = {child.key: child.value for child in value}
                op = {"greater_than": ">", "less_than": "<", "equals": "="}[fields["compare"]]
                return compare(self.variables.get((scope, fields["var"]), 0), op, float(fields["value"]))
            if key in ("exists", "is_ai", "has_capitulated", "is_subject", "has_war", "is_in_faction"):
                actual = {"exists": scope in self.tags, "is_ai": scope not in self.humans,
                          "has_capitulated": scope in self.capitulated,
                          "is_subject": scope in self.subjects,
                          "has_war": any(scope in pair for pair in self.wars),
                          "is_in_faction": scope in self.factions}[key]
                return actual == (value == "yes")
            raise AssertionError(f"Unsupported preparation predicate: {key}")

        results = []
        index = 0
        while index < len(entries):
            entry = entries[index]
            if entry.key:
                results.append(one(entry))
                index += 1
            else:
                name, op, amount = (item.value for item in entries[index:index + 3])
                results.append(compare(self.stats[name], op, float(amount)))
                index += 3
        return all(results)

    def active(self, name, actor):
        profile = self.profiles[name]
        return all(self.evaluate(e.value, actor, actor) for e in profile if e.key in ("allowed", "enable"))

    def test_human_northern_mobilization_warns_all_defenders_and_cancels(self):
        self.humans.add("NOD")
        self.flags["NOD"].add("STP_cw_northern_crisis_pending")
        for defender in ("YPR", "COF", "TFF"):
            self.assertTrue(self.active(f"{defender}_prepare_against_NOD", defender))
        self.flags["NOD"].clear()
        self.assertFalse(self.active("YPR_prepare_against_NOD", "YPR"))

    def test_nod_redeploys_only_after_northern_war_and_stops_on_entry(self):
        self.facts["NOD_cw_intervention_possible"] = True
        self.flags["NOD"].add("NOD_cw_intervention_approved")
        self.wars = {frozenset(("STS", "STP")), frozenset(("NOD", "YPR"))}
        self.assertFalse(self.active("NOD_prepare_against_STS", "NOD"))
        self.wars.remove(frozenset(("NOD", "YPR")))
        self.assertTrue(self.active("NOD_prepare_against_STS", "NOD"))
        self.assertTrue(self.active("STS_prepare_against_NOD", "STS"))
        self.wars.add(frozenset(("STS", "NOD")))
        self.assertFalse(self.active("NOD_prepare_against_STS", "NOD"))
        self.assertFalse(self.active("STS_prepare_against_NOD", "STS"))

    def test_val_ultimatum_does_not_survive_settlement(self):
        self.flags["VAL"].add("VAL_cw_mobilizing")
        self.humans.add("VAL")
        self.assertTrue(self.active("SRP_prepare_against_VAL", "SRP"))
        self.flags["VAL"].add("VAL_cw_settled")
        self.assertFalse(self.active("SRP_prepare_against_VAL", "SRP"))

    def test_resource_war_schedule_releases_on_cancellation_or_invalid_target(self):
        self.globals.add("ADISCORD_nam_resource_war_scheduled")
        self.facts["ADISCORD_nam_resource_war_ready"] = True
        self.assertTrue(self.active("ADISCORD_EFL_prepare_against_NAM", "EFL"))
        self.facts["ADISCORD_nam_resource_war_ready"] = False
        self.assertFalse(self.active("ADISCORD_EFL_prepare_against_NAM", "EFL"))
        self.facts["ADISCORD_nam_resource_war_ready"] = True
        self.globals.clear()
        self.assertFalse(self.active("ADISCORD_EFL_prepare_against_NAM", "EFL"))

    def test_ivanland_readiness_keeps_ivanland_scope_from_a_warring_defender(self):
        self.globals.add("ADISCORD_vorkerland_ivanland_planning_unlocked_v4")
        self.wars.add(frozenset(("PWR", "ZAO")))
        self.decisions.add(("IVN", "ADISCORD_ivanland_prepare_northern_expedition"))
        self.humans.add("IVN")
        self.assertTrue(self.active("ADISCORD_prepare_ZAO_IVN", "ZAO"))
        self.subjects["ZAO"] = "VAD"
        self.assertFalse(self.active("ADISCORD_prepare_ZAO_IVN", "ZAO"))
        self.subjects.clear()
        self.decisions.clear()
        self.assertFalse(self.active("ADISCORD_prepare_ZAO_IVN", "ZAO"))

    def test_vad_reservation_tracks_winner_and_both_sovereignties(self):
        self.globals.update(("ADISCORD_vorkerland_vad_solar_intervention_reserved",
                             "ADISCORD_vorkerland_phase_central_preparation",
                             "ADISCORD_vorkerland_solar_winner_sra"))
        self.facts["ADISCORD_vorkerland_vad_has_solar_intervention_border"] = True
        self.assertTrue(self.active("ADISCORD_prepare_SRA_VAD", "SRA"))
        self.assertFalse(self.active("ADISCORD_prepare_CSL_VAD", "CSL"))
        self.subjects["SRA"] = "WKR"
        self.assertFalse(self.active("ADISCORD_prepare_SRA_VAD", "SRA"))
        self.assertFalse(self.active("ADISCORD_prepare_VAD_SRA", "VAD"))
        self.subjects.clear()
        self.globals.remove("ADISCORD_vorkerland_vad_solar_intervention_reserved")
        self.assertFalse(self.active("ADISCORD_prepare_SRA_VAD", "SRA"))

    def test_postwar_focus_cancel_and_completion_release_threat(self):
        self.facts["STP_pc_focus_available"] = True
        self.humans.add("STS")
        self.focuses["STS"] = "STP_pc_heg_val_force"
        self.assertTrue(self.active("STP_pc_prepare_VAL_STS", "VAL"))
        self.focuses.clear()
        self.assertFalse(self.active("STP_pc_prepare_VAL_STS", "VAL"))
        self.focuses["STS"] = "STP_pc_heg_val_force"
        self.completed.add(("STS", "STP_pc_heg_val_force"))
        self.assertFalse(self.active("STP_pc_prepare_VAL_STS", "VAL"))

    def test_frontier_guarantees_follow_target_and_allow_only_named_subjects(self):
        self.facts["VAL_frontier_prewar_eligible"] = True
        self.variables[("VAL", "VAL_frontier_stage")] = 1
        self.variables[("VAL", "VAL_frontier_target")] = 1
        self.subjects["NOD"] = "STP"
        self.assertTrue(self.active("VAL_frontier_prepare_NOD_VAL", "NOD"))
        self.assertTrue(self.active("VAL_frontier_prepare_VAL_NOD", "VAL"))
        self.subjects["NOD"] = "WKR"
        self.assertFalse(self.active("VAL_frontier_prepare_NOD_VAL", "NOD"))
        self.subjects.clear()
        self.variables[("VAL", "VAL_frontier_target")] = 4
        self.assertFalse(self.active("VAL_frontier_prepare_NOD_VAL", "NOD"))
        self.variables[("VAL", "VAL_frontier_target")] = 1
        self.flags["STS"].add("STP_cw_won_union_battle")
        self.assertTrue(self.active("VAL_frontier_prepare_NOD_VAL", "NOD"))

    def test_preparation_producers_cannot_read_their_own_native_score(self):
        def visit(entries, seen):
            for entry in entries:
                if entry.key in self.triggers and entry.key not in seen:
                    seen.add(entry.key)
                    visit(self.triggers[entry.key], seen)
                if isinstance(entry.value, list):
                    visit(entry.value, seen)
                else:
                    self.assertNotIn("ai_strategy_prepare_for_war@", entry.value)
        for name, entries in self.profiles.items():
            if not any(e.key == "ai_strategy" and any(c.value == "prepare_for_war" for c in e.value)
                       for e in entries):
                continue
            with self.subTest(profile=name):
                self.assertTrue(any(e.key == "abort_when_not_enabled" and e.value == "yes" for e in entries))
                for entry in entries:
                    if entry.key == "enable":
                        visit(entry.value, set())


if __name__ == "__main__":
    unittest.main()
