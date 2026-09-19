"""Structural and truth-table contracts for the imperial campaign.

The evaluator below covers only the five native target predicates and boolean
composition. It is not a substitute for a Clausewitz campaign or UI test.
"""
from __future__ import annotations

import itertools
import random
import re
import unittest
from pathlib import Path

from tools.validators.validate_adiscord_division_templates import Entry, parse_clausewitz

ROOT = Path(__file__).resolve().parents[2]
EFFECTS = "common/scripted_effects/ADISCORD_vorkerland_effects.txt"
TRIGGERS = "common/scripted_triggers/ADISCORD_vorkerland_triggers.txt"
DECISIONS = "common/decisions/ADISCORD_vorkerland_decisions.txt"
IDEAS = "common/ideas/ADISCORD_vorkerland_ideas.txt"
PREFIX = "ADISCORD_vorkerland_"
TARGET = PREFIX + "is_imperial_reclamation_target"
AVAILABLE = PREFIX + "has_imperial_reclamation_target"
DISPATCH = PREFIX + "continue_imperial_reunification"
DECISION = PREFIX + "vad_continue_imperial_reunification"
TARGETS = tuple("EYR EGC RIV REV YOR NDN SWB VHV OSV ZAO PWR VLA ROM TRU WPA WPS PSD EBA DVA SRA ZTA CSL IBA IBL TGD".split())
FIELDS = ("exists", "is_subject", "has_capitulated", "has_war_with", "is_in_faction_with")


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8-sig")


def walk(entries: list[Entry]):
    for entry in entries:
        yield entry
        if isinstance(entry.value, list):
            yield from walk(entry.value)


def one(entries, key: str) -> Entry:
    found = [entry for entry in entries if entry.key == key]
    if len(found) != 1:
        raise AssertionError(f"Expected exactly one {key}; found {len(found)}")
    return found[0]


def body(entries, key: str) -> list[Entry]:
    value = one(entries, key).value
    if not isinstance(value, list):
        raise AssertionError(f"Expected a block for {key}")
    return value


def canonical(entries: list[Entry]):
    return [(e.key, canonical(e.value) if isinstance(e.value, list) else e.value) for e in entries]


def evaluate(entries, facts, scope, definitions):
    def check(entry):
        key, value = entry.key, entry.value
        if key == "NOT":
            return not evaluate(value, facts, scope, definitions)
        if key == "OR":
            return any(check(child) for child in value)
        if key == "AND":
            return evaluate(value, facts, scope, definitions)
        if key in definitions:
            assert value in ("yes", "no"), "Only native boolean trigger calls are supported"
            return evaluate(definitions[key], facts, scope, definitions) == (value == "yes")
        if isinstance(value, list) and key in TARGETS:
            return evaluate(value, facts, key, definitions)
        if key not in FIELDS:
            raise AssertionError(f"Unexpected target predicate: {key}")
        actual = facts[scope][key]
        if value in ("yes", "no"):
            return actual == (value == "yes")
        if value != "WRK":
            raise AssertionError(f"Unexpected relation target: {value}")
        return actual
    return all(check(entry) for entry in entries)


class ImperialReclamationContracts(unittest.TestCase):
    def definitions(self):
        parsed = parse_clausewitz(read(TRIGGERS))
        return {name: body(parsed, name) for name in (TARGET, AVAILABLE)}

    def decision(self):
        return body(walk(parse_clausewitz(read(DECISIONS))), DECISION)

    def dispatch(self):
        return body(parse_clausewitz(read(EFFECTS)), DISPATCH)

    def test_candidate_predicate_preserves_all_five_conditions(self):
        expected = parse_clausewitz("exists = yes is_subject = no NOT = { has_capitulated = yes } NOT = { has_war_with = WRK } NOT = { is_in_faction_with = WRK }")
        self.assertEqual(canonical(self.definitions()[TARGET]), canonical(expected))

    def test_candidate_truth_table(self):
        definitions = self.definitions()
        for values in itertools.product((False, True), repeat=len(FIELDS)):
            facts = {"EYR": dict(zip(FIELDS, values))}
            with self.subTest(values=values):
                expected = values[0] and not any(values[1:])
                self.assertEqual(evaluate(definitions[TARGET], facts, "EYR", definitions), expected)

    def test_decision_keeps_price_cooldown_and_actor(self):
        decision = self.decision()
        self.assertEqual(one(body(decision, "allowed"), "tag").value, "WRK")
        self.assertEqual(one(decision, "cost").value, "25")
        self.assertEqual(one(decision, "days_re_enable").value, "14")
        self.assertEqual(one(decision, "fire_only_once").value, "no")
        self.assertEqual(one(body(decision, "available"), "has_war").value, "no")
        self.assertEqual(one(body(decision, "available"), AVAILABLE).value, "yes")
        self.assertEqual(canonical(body(decision, "complete_effect")), [(DISPATCH, "yes")])

    def test_decision_keeps_postwar_unlock_and_joint_council_exclusion(self):
        expected = parse_clausewitz("has_global_flag = ADISCORD_vorkerland_phase_postwar_integration has_global_flag = ADISCORD_vorkerland_reunification_verified has_country_flag = ADISCORD_vorkerland_route_joint has_country_flag = ADISCORD_vorkerland_vad_imperial_reclamation_unlocked NOT = { has_global_flag = ADISCORD_vorkerland_joint_government_formed }")
        self.assertEqual(canonical(body(self.decision(), "visible")), canonical(expected))

    def test_availability_and_dispatch_share_exact_order(self):
        definitions = self.definitions()
        alternatives = body(definitions[AVAILABLE], "OR")
        self.assertEqual(tuple(e.key for e in alternatives), TARGETS)
        dispatch = self.dispatch()
        self.assertEqual([e.key for e in dispatch], ["if"] + ["else_if"] * (len(TARGETS) - 1))
        for target, candidate, branch in zip(TARGETS, alternatives, dispatch):
            with self.subTest(target=target):
                self.assertEqual(canonical(candidate.value), [(TARGET, "yes")])
                expected_limit = [(target, [(TARGET, "yes")])]
                self.assertEqual(canonical(body(branch.value, "limit")), expected_limit)
                self.assertEqual(canonical(body(branch.value, "declare_war_on")), [("target", target), ("type", "annex_everything")])
                self.assertEqual(len(branch.value), 2)
        self.assertNotIn("SOL", TARGETS)
        self.assertNotIn("WRK", TARGETS)

    def test_first_eligible_target_and_availability_agree(self):
        definitions, dispatch = self.definitions(), self.dispatch()
        rng = random.Random(2160)
        eligible_sets = [set(), set(TARGETS)] + [{t} for t in TARGETS]
        eligible_sets += [set(rng.sample(TARGETS, rng.randrange(len(TARGETS) + 1))) for _ in range(200)]
        for eligible in eligible_sets:
            facts = {t: dict(zip(FIELDS, (t in eligible, False, False, False, False))) for t in TARGETS}
            chosen = None
            for branch in dispatch:
                if evaluate(body(branch.value, "limit"), facts, "WRK", definitions):
                    chosen = one(body(branch.value, "declare_war_on"), "target").value
                    break
            self.assertEqual(chosen, next((t for t in TARGETS if t in eligible), None))
            self.assertEqual(evaluate(definitions[AVAILABLE], facts, "WRK", definitions), chosen is not None)

    def test_helpers_have_one_owner_and_no_world_scans(self):
        for directory, names in (("common/scripted_triggers", (TARGET, AVAILABLE)), ("common/scripted_effects", (DISPATCH,))):
            for name in names:
                owners = [p for p in (ROOT / directory).glob("*.txt") if re.search(rf"(?m)^{name}\s*=\s*\{{", p.read_text(encoding="utf-8-sig"))]
                self.assertEqual(len(owners), 1, name)
        for text in (str(canonical(self.dispatch())), str(self.definitions())):
            for forbidden in ("every_country", "any_country", "random_country", "save_event_target_as", "$TARGET$"):
                self.assertNotIn(forbidden, text)

    def test_hidden_ideas_keep_all_targets_and_amounts(self):
        ideas = body(parse_clausewitz(read(IDEAS)), "ideas")
        hidden = body(ideas, "hidden_ideas")
        theatre = body(hidden, PREFIX + "theatre_priority")
        targets = [e.value for e in theatre if e.key == "targeted_modifier"]
        self.assertEqual(tuple(one(t, "tag").value for t in targets), TARGETS[:9])
        for modifiers in targets:
            for key in ("attack_bonus_against", "defense_bonus_against", "breakthrough_bonus_against"):
                self.assertEqual(one(modifiers, key).value, "0.40")
        for tag in ("wkr", "vad", "tva"):
            coalition = body(hidden, PREFIX + "coalition_against_" + tag)
            self.assertEqual(one(body(coalition, "available"), "is_ai").value, "yes")
            modifiers = body(coalition, "targeted_modifier")
            self.assertEqual(one(modifiers, "tag").value, tag.upper())
            for key in ("attack_bonus_against", "defense_bonus_against"):
                self.assertEqual(one(modifiers, key).value, "0.20")

    def test_theatre_count_and_early_lead_threshold_are_not_confused(self):
        effects = parse_clausewitz(read(EFFECTS))
        attrition = body(effects, PREFIX + "apply_central_attrition")
        states = {e.key for e in walk(attrition) if e.key.isdigit() and isinstance(e.value, list)}
        self.assertEqual(len(states), 37)
        coalition = body(effects, PREFIX + "refresh_claimant_coalition")
        thresholds = [e.value for e in walk(coalition) if e.key == "check_variable" and one(e.value, "var").value == PREFIX + "central_control_score"]
        self.assertEqual(len(thresholds), 3)
        for check in thresholds:
            self.assertEqual(one(check, "value").value, "8")
            self.assertEqual(one(check, "compare").value, "greater_than")
        self.assertNotIn("seventeen central states", read(EFFECTS))



    def test_postwar_dispatch_is_separate_from_wartime_wave_section(self):
        from tools.lib.paths import source_section
        effects = read(EFFECTS)
        self.assertIn(DISPATCH + " = {", source_section(effects, "phase_effects"))
        self.assertNotIn(DISPATCH + " = {", source_section(effects, "focus_decision_effects"))


if __name__ == "__main__":
    unittest.main()
