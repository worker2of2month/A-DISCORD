from __future__ import annotations

import json
import re
from collections import Counter
import unittest
from pathlib import Path

from tools.tests.test_adiscord_stp_preparation import (
    block as ast_block,
    entries as relative_entries,
    matches_conditions,
    scalar as prep_scalar,
    selected_effects,
    walk as prep_walk,
)
from tools.validators.validate_adiscord_division_templates import Entry, parse_clausewitz


ROOT = Path(__file__).resolve().parents[2]
FOCUS = ROOT / "common/national_focus/ADISCORD_national_focus_STP.txt"
EFFECTS = ROOT / "common/scripted_effects/ADISCORD_STP_scripted_effects.txt"
TRIGGERS = ROOT / "common/scripted_triggers/ADISCORD_STP_scripted_triggers.txt"
EVENTS = ROOT / "events/ADISCORD_STP_events.txt"
ON_ACTIONS = ROOT / "common/on_actions/02_ADISCORD_STP_on_actions.txt"
LOC = ROOT / "localisation/russian/ADISCORD_STP_l_russian.yml"
LEDGER = ROOT / "tools/data/adiscord_event_ids.json"

PERSONAL_FOCUS_IDS = (
    "STP_pc_shabrat_cabinet",
    "STP_pc_shabrat_politics",
    "STP_pc_hegemony_open",
    "STP_pc_freedom_open",
    "STP_pc_heg_person",
    "STP_pc_lib_competition",
    "STP_pc_lib_succession",
)
HEGEMONY_COURSE_IDS = (
    "STP_pc_heg_unity",
    "STP_pc_heg_emergency",
    "STP_pc_heg_subordinate",
    "STP_pc_heg_limit_parties",
    "STP_pc_heg_lock",
    "STP_pc_heg_regional_system",
    "STP_pc_heg_val_audit",
    "STP_pc_heg_val_terms",
    "STP_pc_heg_val_force",
    "STP_pc_heg_nod_break",
    "STP_pc_heg_nod_force",
    "STP_pc_heg_clients",
    "STP_pc_heg_burden",
)
FREEDOM_COURSE_IDS = (
    "STP_pc_lib_assembly",
    "STP_pc_lib_institutions",
    "STP_pc_lib_civil_army",
    "STP_pc_lib_lock",
    "STP_pc_lib_emergency_limit",
    "STP_pc_lib_prepare_neighbors",
    "STP_pc_lib_local_contacts",
    "STP_pc_lib_crisis",
    "STP_pc_lib_war",
    "STP_pc_lib_transition",
    "STP_pc_lib_independent_gov",
    "STP_pc_lib_coalition",
)
BARCHEL_CHAIN = ("STP_pc_sot_chain", "STP_pc_sot_two_threats", "STP_pc_sot_keep_command")


def read(path: str | Path) -> str:
    path = Path(path)
    if not path.is_absolute():
        path = ROOT / path
    return path.read_text(encoding="utf-8-sig" if path.suffix == ".yml" else "utf-8")


def entries(path: Path):
    return parse_clausewitz(path.read_text(encoding="utf-8-sig"))


def scalar(items, name):
    found = [entry.value for entry in items if entry.key == name]
    if len(found) != 1 or isinstance(found[0], list):
        raise AssertionError(f"Expected one scalar {name}")
    return found[0]


def block(items, name):
    found = [entry.value for entry in items if entry.key == name]
    if len(found) != 1 or not isinstance(found[0], list):
        raise AssertionError(f"Expected one block {name}")
    return found[0]


def walk(items):
    for entry in items:
        yield entry
        if isinstance(entry.value, list):
            yield from walk(entry.value)


def event_block(text: str, event_id: str) -> str:
    marker = f"\tid = {event_id}\n"
    start = text.index(marker)
    next_event = text.find("\ncountry_event = {", start + len(marker))
    candidates = [pos for pos in (next_event,) if pos != -1]
    end = min(candidates) if candidates else len(text)
    return text[start:end]


def expand(items, parameters=None):
    parameters = parameters or {}
    definitions = {e.key: e.value for e in entries(TRIGGERS)}
    result = []
    for entry in items:
        key = parameters.get(entry.key, entry.key)
        value = (
            expand(entry.value, parameters) if isinstance(entry.value, list)
            else parameters.get(entry.value, entry.value)
        )
        if key in definitions:
            if entry.value not in ("yes", "no"):
                raise AssertionError(f"Unsupported native scripted trigger call: {key}")
            value = expand(definitions[key], parameters)
            if entry.value == "no":
                value = [Entry("AND", value, entry.line)]
            result.append(Entry("AND" if entry.value != "no" else "NOT", value, entry.line))
        else:
            result.append(Entry(key, value, entry.line, entry.quoted))
    return result


def war_focuses():
    war = next(entry.value for entry in entries(FOCUS) if entry.key == "focus_tree" and scalar(entry.value, "id") == "STP_cw_focus")
    return {scalar(entry.value, "id"): entry.value for entry in war if entry.key == "focus"}


def parsed_event(event_id: str):
    return block(parse_clausewitz("country_event = {\n" + event_block(read(EVENTS), event_id)), "country_event")


def option_names(event_id: str):
    return [scalar(option, "name") for option in (e.value for e in parsed_event(event_id) if e.key == "option")]


def option_by_name(event_id: str, name: str):
    event = parsed_event(event_id)
    for option in (e.value for e in event if e.key == "option"):
        if scalar(option, "name") == name:
            return option
    raise AssertionError(name)


def visible_option_names(event_id: str, facts, scope="STS"):
    event = parsed_event(event_id)
    names = []
    for option in (e.value for e in event if e.key == "option"):
        trigger = next((e.value for e in option if e.key == "trigger"), [])
        if not trigger or matches_conditions(expand(trigger), facts, scope):
            names.append(scalar(option, "name"))
    return names


def execute_package_effects(items, facts, dispatched, scope="STS"):
    """Execute only the parsed package protocol; unknown effects fail closed."""
    definitions = {entry.key: entry.value for entry in entries(EFFECTS)}
    definitions.update({entry.key: entry.value for entry in relative_entries("common/scripted_effects/ADISCORD_shared_action_effects.txt")})
    taken = False
    for entry in items:
        key, value = entry.key, entry.value
        if key in {"if", "else_if", "else"}:
            if key == "if":
                taken = False
            condition = next((child.value for child in value if child.key == "limit"), [])
            if not taken and (key == "else" or matches_conditions(expand(condition), facts, scope)):
                taken = True
                execute_package_effects([child for child in value if child.key != "limit"], facts, dispatched, scope)
        elif key in {"name", "trigger", "ai_chance", "custom_effect_tooltip", "effect_tooltip"}:
            continue
        elif key == "hidden_effect":
            execute_package_effects(value, facts, dispatched, scope)
        elif key in {"STP", "STS", "VAL", "NOD"}:
            execute_package_effects(value, facts, dispatched, key)
        elif key in {"set_country_flag", "clr_country_flag"}:
            fact = (scope, "has_country_flag", value)
            if key == "set_country_flag":
                facts[fact] = True
            else:
                facts.pop(fact, None)
        elif key in {"set_variable", "add_to_variable", "subtract_from_variable"}:
            name, amount = scalar(value, "var"), scalar(value, "value")
            try:
                amount = float(amount)
            except ValueError:
                amount = facts.get((scope, "variable", amount), 0)
            if key != "set_variable":
                amount = facts.get((scope, "variable", name), 0) + amount * (-1 if key == "subtract_from_variable" else 1)
            facts[(scope, "variable", name)] = amount
            facts[(scope, "has_variable", name)] = True
        elif key == "clear_variable":
            facts.pop((scope, "variable", value), None)
            facts.pop((scope, "has_variable", value), None)
        elif key == "country_event":
            dispatched.append((scope, scalar(value, "id")))
        elif key == "send_equipment":
            equipment, amount, recipient = scalar(value, "equipment"), float(scalar(value, "amount")), scalar(value, "target")
            facts[(scope, "equipment", equipment)] = facts.get((scope, "equipment", equipment), 0) - amount
            facts[(recipient, "equipment", equipment)] = facts.get((recipient, "equipment", equipment), 0) + amount
        elif key == "add_ideas":
            facts[(scope, "has_idea", value)] = True
        elif key == "add_timed_idea":
            facts[(scope, "has_idea", scalar(value, "idea"))] = True
        elif key == "diplomatic_relation":
            facts[(scope, scalar(value, "relation"), scalar(value, "country"))] = scalar(value, "active") == "yes"
        elif key in {"ADISCORD_economy_mark_dirty", "mark_focus_tree_layout_dirty", "ADISCORD_economy_initialize_country"}:
            continue
        elif key == "set_cosmetic_tag":
            facts[(scope, "cosmetic_tag")] = value
        elif key in definitions:
            if value != "yes":
                raise AssertionError(f"Unsupported effect call: {key}")
            execute_package_effects(definitions[key], facts, dispatched, scope)
        else:
            raise AssertionError(f"Unhandled package effect: {key}")


def package_facts():
    facts = {("STS", "variable", "STP_pc_course"): 2}
    for tag in ("STS", "VAL", "NOD"):
        facts[(tag, "exists", "yes")] = True
        facts[(tag, "has_capitulated", "no")] = True
        facts[(tag, "is_subject", "no")] = True
    return facts


class PostwarContinuationContracts(unittest.TestCase):
    def test_negative_scripted_trigger_negates_the_whole_definition(self) -> None:
        for pending in (False, True):
            facts = package_facts()
            facts[("STS", "has_country_flag", "STP_pc_lib_package_pending")] = pending
            facts[("STS", "variable", "STP_pc_lib_package_tag")] = 1
            positive = matches_conditions(expand(parse_clausewitz("STP_pc_liberation_reply_is_current = yes")), facts, "VAL")
            negative = matches_conditions(expand(parse_clausewitz("STP_pc_liberation_reply_is_current = no")), facts, "VAL")
            self.assertEqual(positive, pending)
            self.assertEqual(negative, not positive)

    def test_event_descriptions_and_answers_never_share_a_localisation_key(self) -> None:
        for number in range(1, 17):
            event_id = f"ADISCORD_STP_pc.{number}"
            event = parsed_event(event_id)
            description = scalar(event, "desc")
            self.assertNotIn(description, option_names(event_id), event_id)

    def test_canonical_stp_localisation_has_no_duplicate_keys(self) -> None:
        counts = Counter(re.findall(r"(?m)^\s*([\w.]+):", read(LOC)))
        self.assertEqual({key: count for key, count in counts.items() if count > 1}, {})

    def test_every_postwar_event_description_variant_is_one_complete_localisation_line(self) -> None:
        self.assertTrue(LOC.read_bytes().startswith(b"\xef\xbb\xbf"))
        lines = read(LOC).splitlines()
        for event in (e.value for e in entries(EVENTS) if e.key == "country_event"):
            if not scalar(event, "id").startswith("ADISCORD_STP_pc."):
                continue
            for desc in (e.value for e in event if e.key == "desc"):
                key = scalar(desc, "text") if isinstance(desc, list) else desc
                found = [line for line in lines if re.match(r"^\s*" + re.escape(key) + r":", line)]
                self.assertEqual(len(found), 1, key)
                self.assertRegex(found[0], r'^\s*' + re.escape(key) + r':\d* "(?:[^"\\]|\\.)*"\s*$')

    def test_stale_package_close_cannot_consume_the_other_country_receipt(self) -> None:
        facts = package_facts()
        facts.update({
            ("STS", "has_country_flag", "STP_pc_lib_package_pending"): True,
            ("STS", "variable", "STP_pc_lib_package_tag"): 2,
            ("STS", "has_variable", "STP_pc_lib_package_tag"): True,
            ("STS", "has_country_flag", "STP_pc_lib_nod_won"): True,
        })
        before, dispatched = dict(facts), []
        close = option_by_name("ADISCORD_STP_pc.11", "ADISCORD_STP_pc.11.c")
        execute_package_effects(close, facts, dispatched, "VAL")
        self.assertEqual(facts, before)
        self.assertEqual(dispatched, [], "a stale VAL card must not reopen NOD's active offer")

    def test_package_answers_recheck_the_receipt_before_changing_the_recipient(self) -> None:
        for recipient, address in (("VAL", 1), ("NOD", 2)):
            for suffix in ("a", "b"):
                with self.subTest(recipient=recipient, answer=suffix):
                    facts = package_facts()
                    facts[("STS", "variable", "STP_pc_lib_package_tag")] = address
                    before, dispatched = dict(facts), []
                    self.assertEqual(visible_option_names("ADISCORD_STP_pc.11", facts, recipient), ["ADISCORD_STP_pc.11.c"])
                    answer = option_by_name("ADISCORD_STP_pc.11", f"ADISCORD_STP_pc.11.{suffix}")
                    execute_package_effects(answer, facts, dispatched, recipient)
                    self.assertEqual(facts, before)
                    self.assertEqual(dispatched, [])

    def test_replayed_acceptance_does_not_duplicate_the_next_offer(self) -> None:
        facts = package_facts()
        for country in ("val", "nod"):
            facts[("STS", "has_country_flag", f"STP_pc_lib_{country}_won")] = True
        dispatched = []
        offer = block(entries(EFFECTS), "STP_pc_offer_liberation_package")
        accept = option_by_name("ADISCORD_STP_pc.11", "ADISCORD_STP_pc.11.a")
        execute_package_effects(offer, facts, dispatched)
        execute_package_effects(accept, facts, dispatched, "VAL")
        self.assertEqual(dispatched, [("VAL", "ADISCORD_STP_pc.11"), ("NOD", "ADISCORD_STP_pc.11")])
        before = dict(facts)
        execute_package_effects(accept, facts, dispatched, "VAL")
        self.assertEqual(facts, before)
        self.assertEqual(len(dispatched), 2)
        execute_package_effects(accept, facts, dispatched, "NOD")
        self.assertNotIn(("STS", "has_country_flag", "STP_pc_lib_package_pending"), facts)
        self.assertNotIn(("STS", "variable", "STP_pc_lib_package_tag"), facts)
        self.assertTrue(facts[("NOD", "has_idea", "NOD_mandate_broken")])

    def test_late_second_victory_delivers_an_already_unlocked_package(self) -> None:
        facts = package_facts()
        facts.update({
            ("STS", "has_completed_focus", "STP_pc_lib_transition"): True,
            ("STS", "has_country_flag", "STP_pc_lib_val_won"): True,
            ("STS", "has_country_flag", "STP_pc_lib_nod_won"): True,
            ("VAL", "has_idea", "VAL_liberated_settlement"): True,
            ("STS", "variable", "STP_pc_settle_opponent"): 2,
            ("STS", "variable", "STP_pc_settle_result"): 1,
        })
        dispatched = []
        execute_package_effects(block(entries(EFFECTS), "STP_pc_clear_settlement"), facts, dispatched)
        self.assertEqual(dispatched, [("NOD", "ADISCORD_STP_pc.11")])
        self.assertEqual(facts[("STS", "variable", "STP_pc_lib_package_tag")], 2)

    def test_vanished_pending_recipient_cannot_block_the_surviving_neighbor(self) -> None:
        facts = package_facts()
        facts.update({
            ("STS", "has_country_flag", "STP_pc_lib_package_pending"): True,
            ("STS", "variable", "STP_pc_lib_package_tag"): 1,
            ("STS", "has_country_flag", "STP_pc_lib_val_won"): True,
            ("STS", "has_country_flag", "STP_pc_lib_nod_won"): True,
            ("VAL", "exists", "yes"): False,
        })
        dispatched = []
        execute_package_effects(block(entries(EFFECTS), "STP_pc_offer_liberation_package"), facts, dispatched)
        self.assertEqual(dispatched, [("NOD", "ADISCORD_STP_pc.11")])
        self.assertEqual(facts[("STS", "variable", "STP_pc_lib_package_tag")], 2)

    def test_nod_crisis_has_one_truthful_acknowledgement(self) -> None:
        event = parsed_event("ADISCORD_STP_pc.10")
        self.assertEqual(option_names("ADISCORD_STP_pc.10"), ["ADISCORD_STP_pc.10.a"])
        answer = block(event, "option")
        self.assertEqual({entry.key for entry in answer}, {"name", "custom_effect_tooltip"})
        self.assertEqual(scalar(answer, "custom_effect_tooltip"), "STP_pc_nod_crisis_opened_tt")
        localisation = read(LOC)
        for obsolete in ("ADISCORD_STP_pc.10.b", "ADISCORD_STP_pc.10.c"):
            self.assertNotRegex(localisation, rf"(?m)^\s*{re.escape(obsolete)}:")
        self.assertRegex(localisation, r"(?m)^ STP_pc_nod_crisis_opened_tt:")

    def test_delayed_nod_notice_rechecks_both_participants_and_postwar_state(self) -> None:
        event = parsed_event("ADISCORD_STP_pc.10")
        gate = expand(block(event, "trigger"))
        facts = package_facts()
        for flag in ("STP_cw_won_union_battle", "STP_cw_postwar"):
            facts[("STS", "has_country_flag", flag)] = True
        facts[("STS", "has_global_flag", "STP_cw_union_wars_finished")] = True
        self.assertTrue(matches_conditions(gate, facts, "NOD"))
        for tag, kind, value in (
            ("NOD", "exists", "yes"),
            ("NOD", "has_capitulated", "no"),
            ("STS", "exists", "yes"),
            ("STS", "has_capitulated", "no"),
            ("STS", "has_country_flag", "STP_cw_postwar"),
        ):
            with self.subTest(tag=tag, condition=kind, value=value):
                self.assertFalse(matches_conditions(gate, {**facts, (tag, kind, value): False}, "NOD"))
        self.assertFalse(matches_conditions(gate, {
            **facts, ("STS", "has_country_flag", "STP_pc_nod_crisis"): True,
        }, "NOD"))

    def test_nod_notice_preserves_the_default_outcome_without_starting_a_war(self) -> None:
        event = parsed_event("ADISCORD_STP_pc.10")
        self.assertEqual(scalar(event, "fire_only_once"), "yes")
        effects = list(selected_effects(block(event, "immediate"), {}, "NOD"))
        self.assertEqual([(scope, effect.key) for scope, effect in effects], [
            ("STS", "set_country_flag"), ("STS", "country_event"),
        ])
        self.assertEqual(effects[0][1].value, "STP_pc_nod_crisis")
        self.assertEqual(scalar(effects[1][1].value, "id"), "ADISCORD_STP_pc.15")
        self.assertEqual(scalar(effects[1][1].value, "days"), "0")
        answer = option_by_name("ADISCORD_STP_pc.10", "ADISCORD_STP_pc.10.a")
        # The outcome belongs to event delivery; closing or timing out does not repeat it.
        facts, dispatched = package_facts(), []
        before = dict(facts)
        execute_package_effects(answer, facts, dispatched, "NOD")
        execute_package_effects(answer, facts, dispatched, "NOD")
        self.assertEqual(facts, before)
        self.assertEqual(dispatched, [])

    def test_nod_notification_keeps_existing_crisis_focus_routes_reachable(self) -> None:
        focuses = war_focuses()
        for focus_id in ("STP_pc_lib_crisis", "STP_pc_lib_war", "STP_pc_army_limited_offense"):
            gate = block(focuses[focus_id], "available")
            facts = {("STS", "STP_pc_focus_available", "yes"): True, ("STS", "STP_pc_can_confront_nod", "yes"): True}
            self.assertFalse(matches_conditions(gate, facts, "STS"), focus_id)
            facts[("STS", "has_country_flag", "STP_pc_nod_crisis")] = True
            self.assertTrue(matches_conditions(gate, facts, "STS"), focus_id)

    def test_pending_package_recovers_after_all_focus_and_settlement_callers_finished(self) -> None:
        periodic = block(block(entries(ON_ACTIONS), "on_actions"), "on_weekly_STS")
        facts = package_facts()
        facts.update({
            ("STS", "has_completed_focus", "STP_pc_lib_transition"): True,
            ("STS", "has_completed_focus", "STP_pc_lib_independent_gov"): True,
            ("STS", "has_country_flag", "STP_pc_lib_package_pending"): True,
            ("STS", "variable", "STP_pc_lib_package_tag"): 1,
            ("STS", "has_variable", "STP_pc_lib_package_tag"): True,
            ("STS", "has_country_flag", "STP_pc_lib_val_won"): True,
            ("STS", "has_country_flag", "STP_pc_lib_nod_won"): True,
            ("STS", "variable", "STP_pc_settle_opponent"): 2,
            ("STS", "variable", "STP_pc_settle_result"): 1,
        })
        dispatched = []
        execute_package_effects(block(entries(EFFECTS), "STP_pc_clear_settlement"), facts, dispatched)
        self.assertEqual(dispatched, [], "VAL still owns the open offer when NOD settles")
        facts[("VAL", "exists", "yes")] = False
        # Only the native periodic entry point remains; no focus or answer is forced.
        execute_package_effects(block(periodic, "effect"), facts, dispatched)
        self.assertEqual(dispatched, [("NOD", "ADISCORD_STP_pc.11")])
        self.assertEqual(facts[("STS", "variable", "STP_pc_lib_package_tag")], 2)
        execute_package_effects(block(periodic, "effect"), facts, dispatched)
        self.assertEqual(len(dispatched), 1, "a live NOD card must not be reissued")
        execute_package_effects(option_by_name("ADISCORD_STP_pc.11", "ADISCORD_STP_pc.11.a"), facts, dispatched, "NOD")
        before = dict(facts)
        execute_package_effects(block(periodic, "effect"), facts, dispatched)
        self.assertEqual(facts, before)
        self.assertEqual(len(dispatched), 1)
        self.assertNotIn(("STS", "has_country_flag", "STP_pc_lib_package_pending"), facts)

    def test_package_recovery_is_scoped_to_an_existing_sts_with_a_pending_receipt(self) -> None:
        periodic = block(block(entries(ON_ACTIONS), "on_actions"), "on_weekly_STS")
        self.assertFalse(any(entry.key in {"every_country", "every_possible_country"} for entry in walk(periodic)))
        for exists, pending in ((True, False), (False, False), (False, True)):
            with self.subTest(exists=exists, pending=pending):
                facts = package_facts()
                facts.update({
                    ("STS", "exists", "yes"): exists,
                    ("STS", "has_country_flag", "STP_pc_lib_package_pending"): pending,
                    ("STS", "has_country_flag", "STP_pc_lib_val_won"): True,
                })
                before, dispatched = dict(facts), []
                execute_package_effects(block(periodic, "effect"), facts, dispatched)
                self.assertEqual(facts, before)
                self.assertEqual(dispatched, [])

    def test_postwar_focuses_are_unique_and_linked_on_the_resistance_war_tree(self) -> None:
        trees = [entry.value for entry in entries(FOCUS) if entry.key == "focus_tree"]
        war = next(tree for tree in trees if scalar(tree, "id") == "STP_cw_focus")
        prep = next(tree for tree in trees if scalar(tree, "id") == "STP_focus")
        war_ids = [scalar(entry.value, "id") for entry in war if entry.key == "focus"]
        prep_ids = [scalar(entry.value, "id") for entry in prep if entry.key == "focus"]
        pc_ids = [focus_id for focus_id in war_ids if focus_id.startswith("STP_pc_")]
        self.assertEqual(len(set(pc_ids)), len(pc_ids))
        self.assertTrue(set(PERSONAL_FOCUS_IDS + HEGEMONY_COURSE_IDS + FREEDOM_COURSE_IDS).issubset(pc_ids))
        for focus in (e.value for e in war if e.key == "focus"):
            for prerequisite in (e.value for e in focus if e.key == "prerequisite"):
                self.assertTrue(all(e.value in war_ids for e in prerequisite), scalar(focus, "id"))
        self.assertFalse(any(focus_id.startswith("STP_pc_") for focus_id in prep_ids))
        self.assertEqual(scalar(next(entry.value for entry in war if entry.key == "focus" and scalar(entry.value, "id") == "STP_pc_after_victory"), "x"), "16")

    def test_shabrat_cabinet_names_the_union_and_installs_ministers(self) -> None:
        focus = war_focuses()["STP_pc_shabrat_cabinet"]
        self.assertEqual(scalar(focus, "x"), "14")
        self.assertEqual(scalar(focus, "y"), "4")
        self.assertEqual(
            [e.value for e in block(focus, "prerequisite") if e.key == "focus"],
            ["STP_pc_after_victory"],
        )
        reward = block(focus, "completion_reward")
        party = block(reward, "set_party_name")
        self.assertEqual(scalar(party, "ideology"), "chauvinism")
        self.assertEqual(scalar(party, "name"), "STS_chauvinism_party")
        self.assertEqual(scalar(party, "long_name"), "STS_chauvinism_party_long")
        ministers = {e.value or e.key for e in block(reward, "add_ideas")} - {""}
        self.assertEqual(
            ministers,
            {
                "minister_STS_Marta_Eirich",
                "minister_STS_Leonid_Barchel",
                "minister_STS_Ignat_Forel",
                "minister_STS_Nika_Volgina",
                "minister_STS_Tomas_Krey",
                "minister_STS_Lia_Verst",
            },
        )
        loc = read(LOC)
        self.assertIn('STP_pc_shabrat_cabinet: "Кабинет основателя"', loc)
        parties = (ROOT / "localisation/russian/parties_l_russian.yml").read_text(encoding="utf-8-sig")
        self.assertIn(
            'STS_chauvinism_party: "£GFX_STS_steland_union_party_texticon Стеландский союз"',
            parties,
        )
        self.assertIn(
            'STS_chauvinism_party_long: "£GFX_STS_steland_union_party_texticon Стеландский союз восстановления"',
            parties,
        )

    def test_personal_fork_stays_with_the_founder(self) -> None:
        focuses = war_focuses()
        founder = ast_block(entries(TRIGGERS), "STP_pc_founder_rules")
        successor = ast_block(entries(TRIGGERS), "STP_pc_named_successor_rules")
        self.assertIn("STP_maksim_shabrat", {e.value for e in walk(founder) if e.key == "character"})
        self.assertEqual({e.value for e in walk(successor) if e.key == "character"}, {"STP_ilya_gornin", "STP_vera_tikh"})
        self.assertNotIn("STP_grigory_sotnikov", {e.value for e in walk(successor) if e.key == "character"})
        self.assertNotIn("STP_Leonid_Barchel", {e.value for e in walk(successor) if e.key == "character"})
        for focus_id in PERSONAL_FOCUS_IDS:
            allow = " ".join(f"{e.key}={e.value}" if not isinstance(e.value, list) else e.key for e in walk(block(focuses[focus_id], "allow_branch")))
            self.assertIn("STP_pc_founder_rules=yes", allow, focus_id)
            self.assertNotIn("STP_pc_freedom_continues", allow, focus_id)
            self.assertNotIn("STP_pc_hegemony_continues", allow, focus_id)
            self.assertNotIn("STP_grigory_sotnikov", allow, focus_id)

    def test_successors_keep_the_locked_course_not_the_rivals(self) -> None:
        focuses = war_focuses()
        freedom = ast_block(entries(TRIGGERS), "STP_pc_freedom_continues")
        hegemony = ast_block(entries(TRIGGERS), "STP_pc_hegemony_continues")
        gornin_freedom = {
            ("STS", "STP_pc_founder_rules", "yes"): False,
            ("STS", "STP_pc_named_successor_rules", "yes"): True,
            ("STS", "has_country_flag", "STP_pc_course_locked"): True,
            ("STS", "variable", "STP_pc_course"): 2,
        }
        self.assertTrue(matches_conditions(freedom, gornin_freedom, "STS"))
        self.assertFalse(matches_conditions(hegemony, gornin_freedom, "STS"))
        self.assertFalse(matches_conditions(freedom, {**gornin_freedom, ("STS", "variable", "STP_pc_course"): 1}, "STS"))
        self.assertTrue(matches_conditions(hegemony, {**gornin_freedom, ("STS", "variable", "STP_pc_course"): 1}, "STS"))
        self.assertFalse(matches_conditions(freedom, {
            ("STS", "STP_pc_founder_rules", "yes"): False,
            ("STS", "STP_pc_named_successor_rules", "yes"): False,
            ("STS", "has_country_flag", "STP_pc_course_locked"): True,
            ("STS", "variable", "STP_pc_course"): 2,
        }, "STS"), "Sotnikov or Barchel must not inherit the freedom course")
        self.assertTrue(matches_conditions(freedom, {("STS", "STP_pc_founder_rules", "yes"): True}, "STS"))
        founder_freedom = {
            ("STS", "STP_pc_founder_rules", "yes"): True,
            ("STS", "has_country_flag", "STP_pc_course_locked"): True,
            ("STS", "variable", "STP_pc_course"): 2,
        }
        self.assertTrue(matches_conditions(freedom, founder_freedom, "STS"))
        self.assertFalse(matches_conditions(hegemony, founder_freedom, "STS"), "locked freedom must close the hegemony course")
        self.assertTrue(matches_conditions(hegemony, {("STS", "STP_pc_founder_rules", "yes"): True}, "STS"))
        for focus_id in FREEDOM_COURSE_IDS:
            allow = " ".join(f"{e.key}={e.value}" if not isinstance(e.value, list) else e.key for e in walk(block(focuses[focus_id], "allow_branch")))
            self.assertIn("STP_pc_freedom_continues=yes", allow, focus_id)
            self.assertNotIn("STP_pc_founder_rules=yes", allow, focus_id)
            self.assertNotIn("STP_grigory_sotnikov", allow, focus_id)
        for focus_id in HEGEMONY_COURSE_IDS:
            allow = " ".join(f"{e.key}={e.value}" if not isinstance(e.value, list) else e.key for e in walk(block(focuses[focus_id], "allow_branch")))
            self.assertIn("STP_pc_hegemony_continues=yes", allow, focus_id)
            self.assertNotIn("STP_pc_founder_rules=yes", allow, focus_id)
        archive = " ".join(f"{e.key}={e.value}" if not isinstance(e.value, list) else e.key for e in walk(block(focuses["STP_pc_shared_archive_policy"], "allow_branch")))
        self.assertIn("STP_pc_course_continues=yes", archive)

    def test_barchel_reaches_directory_lock_without_sotnikov_field_steps(self) -> None:
        focuses = war_focuses()
        for focus_id in BARCHEL_CHAIN:
            allow = " ".join(
                f"{entry.key}={entry.value}" if not isinstance(entry.value, list) else entry.key
                for entry in walk(block(focuses[focus_id], "allow_branch"))
            )
            self.assertIn("STP_Leonid_Barchel", allow, focus_id)
        keep = focuses["STP_pc_sot_keep_command"]
        prereqs = [entry.value for entry in keep if entry.key == "prerequisite"]
        self.assertTrue(any(any(child.value == "STP_pc_sot_two_threats" for child in group) for group in prereqs))
        self.assertNotIn("STP_pc_sot_field", {child.value for group in prereqs for child in group if child.key == "focus"})

    def test_arrest_follows_the_clamp_and_excludes_postwar_head_of_state(self) -> None:
        change = "".join(
            line for line in read(EFFECTS).split("STP_change_party_suspicion = {", 1)[1].split("\n}")[0].splitlines()
        )
        self.assertIn("STP_refresh_party_suspicion = yes", change)
        self.assertIn("STP_pc_update_suspicion_crisis = yes", change)
        self.assertLess(change.index("STP_refresh_party_suspicion = yes"), change.index("STP_pc_update_suspicion_crisis = yes"))
        crisis = read(TRIGGERS)
        self.assertIn("STP_cw_sotnikov_available = {", crisis)
        update = read(EFFECTS).split("STP_pc_update_suspicion_crisis = {", 1)[1]
        self.assertIn("ADISCORD_STP_pc.3", update)
        self.assertIn("NOT = { has_country_flag = STP_cw_elections_finished }", update)
        self.assertIn("NOT = { has_country_flag = STP_cw_postwar }", update)
        events = read(EVENTS)
        self.assertIn("STP_pc_install_resistance_successor = yes", event_block(events, "ADISCORD_STP_pc.3"))
        self.assertIn("STP_pc_install_resistance_successor = yes", event_block(events, "ADISCORD_STP_pc.6"))
        install = read(EFFECTS).split("STP_pc_install_resistance_successor = {", 1)[1]
        self.assertIn("STP_cw_establish_resistance_command = yes", install)
        self.assertIn("STP_pc_align_resistance_ruling_party = yes", install)

    def test_split_copies_sotnikov_without_making_him_party_head(self) -> None:
        start = read(EFFECTS).split("STP_cw_start = {", 1)[1].split("STP_cw_begin_hostilities", 1)[0]
        self.assertIn("set_nationality = { character = STP_grigory_sotnikov target_country = STS }", start)
        self.assertIn("STP_cw_release_resistance_officeholders = yes", start)
        self.assertLess(start.index("STP_cw_release_resistance_officeholders = yes"),
                        start.index("set_nationality = { character = STP_grigory_sotnikov target_country = STS }"))
        self.assertNotIn("promote_character = STP_grigory_sotnikov", start)
        self.assertIn("STP_pc_copy_split_flags = yes", start)

    def test_events_are_registered_once(self) -> None:
        events = read(EVENTS)
        ledger = {entry["id"] for entry in json.loads(read(LEDGER))["events"]}
        loc = read(LOC)
        self.assertTrue(LOC.read_bytes().startswith(b"\xef\xbb\xbf"))
        self.assertIn("add_namespace = ADISCORD_STP_pc", events)
        for number in range(1, 17):
            event_id = f"ADISCORD_STP_pc.{number}"
            self.assertEqual(events.count(f"\tid = {event_id}\n"), 1, event_id)
            self.assertIn(event_id, ledger)
            self.assertIn(f" {event_id}.t:", loc)
            self.assertIn(f" {event_id}.d:", loc)
            self.assertIn(f"name = {event_id}.", event_block(events, event_id))
        self.assertEqual(loc.count(" ADISCORD_STP_pc.16.d:"), 1)
        self.assertIn(" ADISCORD_STP_pc.16.da:", loc)
        self.assertIn(" ADISCORD_STP_pc.16.o:", loc)
        names = option_names("ADISCORD_STP_pc.16")
        self.assertIn("ADISCORD_STP_pc.16.da", names)
        self.assertNotIn("ADISCORD_STP_pc.16.d", names)
        page = loc[loc.index("ADISCORD_STP_pc.16.t"):loc.index("ADISCORD_STP_pc.16.o")]
        self.assertNotIn("скрипт", page)
        self.assertNotIn("ванильн", page)

    def test_postwar_wars_use_native_relations_without_marker_flags(self) -> None:
        gameplay = "\n".join((
            read("common/on_actions/02_ADISCORD_STP_on_actions.txt"),
            read("common/scripted_effects/ADISCORD_STP_scripted_effects.txt"),
            read("common/scripted_triggers/ADISCORD_STP_scripted_triggers.txt"),
            read("events/ADISCORD_STP_events.txt"),
            read("common/decisions/ADISCORD_VAL_decisions.txt"),
        ))
        for obsolete in ("STP_pc_war_val", "STP_pc_war_nod", "STP_pc_war_with_sts"):
            self.assertNotIn(obsolete, gameplay)

        on_actions = read("common/on_actions/02_ADISCORD_STP_on_actions.txt")
        self.assertNotIn("Heal postwar opponent markers", on_actions)
        self.assertIn("ROOT = { tag = VAL has_war_with = STS }", on_actions)
        self.assertIn("ROOT = { tag = NOD has_war_with = STS }", on_actions)
        self.assertIn("ROOT = { tag = STS has_war_with = VAL }", on_actions)
        self.assertIn("ROOT = { tag = STS has_war_with = NOD }", on_actions)

        effects = read("common/scripted_effects/ADISCORD_STP_scripted_effects.txt")
        self.assertIn("declare_war_on = { target = VAL type = annex_everything }", effects)
        self.assertIn("declare_war_on = { target = NOD type = annex_everything }", effects)

    def test_postwar_settlement_is_a_sibling_of_the_nod_defeat_router(self) -> None:
        effect = ast_block(ast_block(relative_entries("common/on_actions/02_ADISCORD_STP_on_actions.txt"), "on_actions"), "on_capitulation")
        top = ast_block(effect, "effect")
        branches = [e for e in top if e.key in ("if", "else_if", "else")]
        nod = next(e for e in branches if any(c.key == "set_country_flag" and c.value == "NOD_cw_defeated" for c in prep_walk(e.value)))
        postwar = next(e for e in branches if any(c.key == "STP_pc_begin_settlement" for c in prep_walk(e.value)))
        self.assertIsNot(nod, postwar)
        self.assertFalse(any(c.key == "STP_pc_begin_settlement" for c in prep_walk(nod.value)))
        self.assertFalse(any(c.key == "white_peace" for c in prep_walk(postwar.value)))
        self.assertTrue(any(c.key == "var" and c.value == "STP_pc_cap_side" for c in prep_walk(postwar.value)))
        immediate = ast_block(ast_block(relative_entries("common/on_actions/02_ADISCORD_STP_on_actions.txt"), "on_actions"), "on_capitulation_immediate")
        snapshot = next(e.value for e in ast_block(immediate, "effect") if e.key == "else_if" and any(c.key == "STP_cw_snapshot_capitulation_occupier" for c in prep_walk(e.value)))
        root = ast_block(ast_block(snapshot, "limit"), "ROOT")
        val = next(e.value for e in ast_block(root, "OR") if e.key == "AND" and any(c.key == "tag" and c.value == "VAL" for c in prep_walk(e.value)))
        nod_root = next(e.value for e in ast_block(root, "OR") if e.key == "AND" and any(c.key == "tag" and c.value == "NOD" for c in prep_walk(e.value)))
        for opponent, branch in (("VAL", val), ("NOD", nod_root)):
            with self.subTest(opponent=opponent):
                self.assertTrue(any(c.key == "has_war_with" and c.value == "STS" for c in prep_walk(branch)))
                self.assertFalse(any(c.key == "has_country_flag" and c.value.startswith("STP_pc_war_") for c in prep_walk(branch)))

        immediate_text = read("common/on_actions/02_ADISCORD_STP_on_actions.txt")
        for opponent in ("VAL", "NOD"):
            marker = f"ROOT = {{ tag = {opponent} has_war_with = STS }}"
            start = immediate_text.index(marker)
            fallback = immediate_text[start:start + 600]
            self.assertIn("FROM = { tag = STS }", fallback, opponent)
            self.assertIn("var = STP_cw_capitulation_occupier value = 2", fallback, opponent)

    def test_settlement_freezes_the_snapshot_and_closes_only_that_war(self) -> None:
        begin = ast_block(relative_entries("common/scripted_effects/ADISCORD_STP_scripted_effects.txt"), "STP_pc_begin_settlement")
        self.assertFalse(any(e.key == "ROOT" for e in walk(begin)))
        val_win = {
            ("STS", "tag", "STS"): True,
            ("STS", "variable", "STP_pc_cap_side"): 1,
            ("VAL", "variable", "STP_cw_capitulation_occupier"): 2,
            ("STS", "has_war_with", "VAL"): True,
            ("STS", "has_war_with", "NOD"): True,
        }
        chosen = list(selected_effects(begin, val_win, "STS"))
        peaces = [e.value for _, e in chosen if e.key == "white_peace"]
        self.assertEqual(peaces, ["VAL"])
        results = [(scope, prep_scalar(e.value, "var"), prep_scalar(e.value, "value")) for scope, e in chosen if e.key == "set_variable"]
        self.assertIn(("STS", "STP_pc_this_opponent", "1"), results)
        self.assertIn(("STS", "STP_pc_this_result", "1"), results)
        self.assertIn(("STS", "STP_pc_settle_opponent", "STP_pc_this_opponent"), results)
        self.assertIn(("STS", "STP_pc_settle_result", "STP_pc_this_result"), results)
        self.assertTrue(any(e.key == "country_event" for _, e in chosen))
        self.assertTrue(any(e.key == "set_country_flag" and e.value == "STP_pc_settlement_pending" for _, e in chosen))

        # Once the reserved VAL capitulation router has selected cap_side=1,
        # the military result is final. A stale capital-controller snapshot must
        # not downgrade Shabrat's victory to an empty settlement.
        stale_val = {**val_win, ("VAL", "variable", "STP_cw_capitulation_occupier"): 5}
        stale = list(selected_effects(begin, stale_val, "STS"))
        self.assertEqual([e.value for _, e in stale if e.key == "white_peace"], ["VAL"])
        stale_vars = [(s, prep_scalar(e.value, "var"), prep_scalar(e.value, "value")) for s, e in stale if e.key == "set_variable"]
        self.assertIn(("STS", "STP_pc_this_opponent", "1"), stale_vars)
        self.assertIn(("STS", "STP_pc_this_result", "1"), stale_vars)

        sts_loss = {
            ("STS", "tag", "STS"): True,
            ("STS", "variable", "STP_pc_cap_side"): 3,
            ("STS", "variable", "STP_cw_capitulation_occupier"): 5,
            ("STS", "has_war_with", "VAL"): True,
            ("STS", "has_war_with", "NOD"): True,
        }
        lost = list(selected_effects(begin, sts_loss, "STS"))
        self.assertEqual([e.value for _, e in lost if e.key == "white_peace"], ["VAL"])
        lost_vars = [(s, prep_scalar(e.value, "var"), prep_scalar(e.value, "value")) for s, e in lost if e.key == "set_variable"]
        self.assertIn(("STS", "STP_pc_this_opponent", "1"), lost_vars)
        self.assertIn(("STS", "STP_pc_this_result", "2"), lost_vars)

        unknown = {**sts_loss, ("STS", "variable", "STP_cw_capitulation_occupier"): 7}
        leftover = list(selected_effects(begin, unknown, "STS"))
        self.assertFalse(any(e.key == "white_peace" for _, e in leftover))

        queued = {
            ("STS", "tag", "STS"): True,
            ("STS", "variable", "STP_pc_cap_side"): 2,
            ("STS", "has_country_flag", "STP_pc_settlement_pending"): True,
            ("NOD", "variable", "STP_cw_capitulation_occupier"): 2,
            ("STS", "has_war_with", "NOD"): True,
            ("STS", "has_war_with", "VAL"): True,
        }
        held = list(selected_effects(begin, queued, "STS"))
        self.assertEqual([e.value for _, e in held if e.key == "white_peace"], ["NOD"])
        self.assertFalse(any(e.key == "country_event" for _, e in held))
        queued_vars = [(scope, prep_scalar(e.value, "var"), prep_scalar(e.value, "value")) for scope, e in held if e.key == "set_variable"]
        self.assertIn(("STS", "STP_pc_queued_opponent", "STP_pc_this_opponent"), queued_vars)
        self.assertNotIn(("STS", "STP_pc_settle_opponent", "STP_pc_this_opponent"), queued_vars)
        blocked = list(selected_effects(begin, {
            **queued,
            ("STS", "has_variable", "STP_pc_queued_opponent"): True,
        }, "STS"))
        self.assertFalse(any(e.key == "country_event" for _, e in blocked))
        self.assertNotIn(("STS", "STP_pc_settle_opponent", "STP_pc_this_opponent"),
                         [(s, prep_scalar(e.value, "var"), prep_scalar(e.value, "value")) for s, e in blocked if e.key == "set_variable"])

    def test_kefreyt_defeat_returns_all_stelander_cores_before_white_peace(self) -> None:
        effects = relative_entries("common/scripted_effects/ADISCORD_STP_scripted_effects.txt")
        recovery = ast_block(effects, "STP_pc_recover_stelander_cores_from_val")
        self.assertTrue(any(e.key == "every_state" for e in prep_walk(recovery)))
        recovery_text = read("common/scripted_effects/ADISCORD_STP_scripted_effects.txt")
        recovery_text = recovery_text[recovery_text.index("STP_pc_recover_stelander_cores_from_val = {"):]
        recovery_text = recovery_text[:recovery_text.index("\nSTP_pc_begin_settlement = {")]
        for token in ("is_core_of = STS", "is_core_of = STP", "state = 42", "state = 52", "state = 55",
                      "is_owned_by = VAL", "is_subject_of = VAL", "transfer_state_to = STS",
                      "add_core_of = STS", "set_state_controller_to = STS"):
            self.assertIn(token, recovery_text)

        begin_text = read("common/scripted_effects/ADISCORD_STP_scripted_effects.txt")
        begin_text = begin_text[begin_text.index("STP_pc_begin_settlement = {"):]
        begin_text = begin_text[:begin_text.index("\nSTP_pc_clear_settlement = {")]
        win = begin_text[begin_text.index("STP_pc_this_opponent value = 1"):]
        self.assertLess(win.index("STP_pc_recover_stelander_cores_from_val = yes"),
                        win.index("white_peace = VAL"))

    def test_pc16_uses_the_frozen_result_not_capitulation_after_peace(self) -> None:
        event = event_block(read(EVENTS), "ADISCORD_STP_pc.16")
        self.assertNotIn("has_capitulated", event)
        liberation = option_by_name("ADISCORD_STP_pc.16", "ADISCORD_STP_pc.16.i")
        self.assertFalse(any(e.key == "country_event" for e in walk(liberation)))
        continue_nod = option_by_name("ADISCORD_STP_pc.16", "ADISCORD_STP_pc.16.m")
        self.assertTrue(any(e.key == "set_country_flag" and e.value == "STP_pc_lib_val_won" for e in walk(continue_nod)))
        continue_val = option_by_name("ADISCORD_STP_pc.16", "ADISCORD_STP_pc.16.n")
        self.assertTrue(any(e.key == "set_country_flag" and e.value == "STP_pc_lib_nod_won" for e in walk(continue_val)))
        facts_win_val = {
            ("STS", "variable", "STP_pc_course"): 2,
            ("STS", "variable", "STP_pc_settle_opponent"): 1,
            ("STS", "variable", "STP_pc_settle_result"): 1,
        }
        visible = visible_option_names("ADISCORD_STP_pc.16", facts_win_val)
        self.assertIn("ADISCORD_STP_pc.16.i", visible)
        self.assertNotIn("ADISCORD_STP_pc.16.a", visible)
        self.assertNotIn("ADISCORD_STP_pc.16.o", visible)
        defeat = visible_option_names("ADISCORD_STP_pc.16", {
            ("STS", "variable", "STP_pc_course"): 2,
            ("STS", "variable", "STP_pc_settle_opponent"): 1,
            ("STS", "variable", "STP_pc_settle_result"): 2,
        })
        self.assertIn("ADISCORD_STP_pc.16.l", defeat)
        self.assertNotIn("ADISCORD_STP_pc.16.i", defeat)
        stale = visible_option_names("ADISCORD_STP_pc.16", {
            ("STS", "variable", "STP_pc_course"): 2,
            ("STS", "variable", "STP_pc_settle_opponent"): 1,
            ("STS", "variable", "STP_pc_settle_result"): 0,
            ("NOD", "exists", "yes"): True,
        })
        self.assertEqual(stale, ["ADISCORD_STP_pc.16.o"])
        self.assertNotIn("ADISCORD_STP_pc.16.m", stale)
        for name in option_names("ADISCORD_STP_pc.16"):
            option = option_by_name("ADISCORD_STP_pc.16", name)
            self.assertTrue(any(e.key == "STP_pc_clear_settlement" for e in walk(option)), name)

    def test_transition_offers_the_package_instead_of_reopening_settlement(self) -> None:
        focuses = war_focuses()
        reward = ast_block(focuses["STP_pc_lib_transition"], "completion_reward")
        self.assertTrue(any(e.key == "STP_pc_offer_liberation_package" for e in walk(reward)))
        self.assertFalse(any(e.key == "id" and e.value == "ADISCORD_STP_pc.16" for e in walk(reward)))
        independent = ast_block(focuses["STP_pc_lib_independent_gov"], "completion_reward")
        self.assertFalse(any(e.key == "STP_pc_offer_liberation_package" for e in walk(independent)))
        self.assertTrue(any(e.key == "add_to_variable" for e in walk(independent)))

    def test_package_queue_handles_both_neighbors_refuse_and_reentry(self) -> None:
        offer = ast_block(relative_entries("common/scripted_effects/ADISCORD_STP_scripted_effects.txt"), "STP_pc_offer_liberation_package")
        both = {
            **package_facts(),
            ("STS", "has_country_flag", "STP_pc_lib_package_pending"): False,
            ("STS", "has_country_flag", "STP_pc_lib_val_won"): True,
            ("STS", "has_country_flag", "STP_pc_lib_nod_won"): True,
            ("VAL", "exists", "yes"): True,
            ("NOD", "exists", "yes"): True,
        }
        first = list(selected_effects(expand(offer), both, "STS"))
        self.assertEqual([(s, prep_scalar(e.value, "var"), prep_scalar(e.value, "value")) for s, e in first if e.key == "set_variable"],
                         [("STS", "STP_pc_lib_package_tag", "1")])
        self.assertTrue(any(scope == "VAL" and e.key == "country_event" for scope, e in first))
        self.assertFalse(any(scope == "STS" and e.key == "country_event" for scope, e in first))
        after_val = {**both, ("VAL", "has_idea", "VAL_liberated_settlement"): True}
        second = list(selected_effects(expand(offer), after_val, "STS"))
        self.assertEqual([(s, prep_scalar(e.value, "var"), prep_scalar(e.value, "value")) for s, e in second if e.key == "set_variable"],
                         [("STS", "STP_pc_lib_package_tag", "2")])
        refused_val = {**both, ("VAL", "has_country_flag", "STP_pc_val_refused_package"): True}
        after_refuse = list(selected_effects(expand(offer), refused_val, "STS"))
        self.assertEqual([(s, prep_scalar(e.value, "var"), prep_scalar(e.value, "value")) for s, e in after_refuse if e.key == "set_variable"],
                         [("STS", "STP_pc_lib_package_tag", "2")])
        pending = list(selected_effects(expand(offer), {**both, ("STS", "has_country_flag", "STP_pc_lib_package_pending"): True}, "STS"))
        self.assertFalse(any(e.key in {"country_event", "set_variable"} for _, e in pending))
        done = list(selected_effects(expand(offer), {
            **after_val,
            ("NOD", "has_idea", "NOD_mandate_broken"): True,
        }, "STS"))
        self.assertFalse(any(e.key == "country_event" for _, e in done))
        self.assertTrue(any(e.key == "clear_variable" and e.value == "STP_pc_lib_package_tag" for _, e in done))
        accept = option_by_name("ADISCORD_STP_pc.11", "ADISCORD_STP_pc.11.a")
        refuse = option_by_name("ADISCORD_STP_pc.11", "ADISCORD_STP_pc.11.b")
        self.assertTrue(any(e.key == "STP_pc_finish_liberation_package" for e in walk(accept)))
        self.assertTrue(any(e.key == "STP_pc_finish_liberation_package" for e in walk(refuse)))
        self.assertFalse(any(e.key == "id" and e.value == "ADISCORD_STP_pc.11" for e in walk(accept)))
        stale_close = option_by_name("ADISCORD_STP_pc.11", "ADISCORD_STP_pc.11.c")
        self.assertTrue(any(e.key == "STP_pc_finish_liberation_package" for e in walk(stale_close)))
        refusal = package_facts()
        refusal.update({
            ("STS", "variable", "STP_pc_lib_package_tag"): 2,
            ("STS", "has_country_flag", "STP_pc_lib_package_pending"): True,
        })
        dispatched = []
        execute_package_effects(refuse, refusal, dispatched, "NOD")
        self.assertTrue(refusal[("NOD", "has_country_flag", "STP_pc_nod_refused_package")])
        self.assertNotIn(("VAL", "has_country_flag", "STP_pc_nod_refused_package"), refusal)
        self.assertNotIn(("STS", "has_country_flag", "STP_pc_lib_package_pending"), refusal)
        self.assertEqual(dispatched, [])

    def test_late_liberated_members_join_an_already_formed_coalition(self) -> None:
        form = ast_block(relative_entries("common/scripted_effects/ADISCORD_STP_scripted_effects.txt"), "STP_pc_form_liberation_coalition")
        created = list(selected_effects(form, {("STS", "tag", "STS"): True}, "STS"))
        self.assertTrue(any(e.key == "create_faction_from_template" for _, e in created))
        late = {
            ("STS", "tag", "STS"): True,
            ("STS", "has_country_flag", "STP_pc_liberation_coalition"): True,
            ("VAL", "exists", "yes"): True,
            ("VAL", "has_idea", "VAL_liberated_settlement"): True,
            ("VAL", "is_in_faction_with", "STS"): False,
            ("NOD", "exists", "yes"): True,
            ("NOD", "has_idea", "NOD_mandate_broken"): True,
            ("NOD", "is_in_faction_with", "STS"): True,
        }
        admitted = list(selected_effects(form, late, "STS"))
        self.assertFalse(any(e.key == "create_faction_from_template" for _, e in admitted))
        self.assertEqual([e.value for _, e in admitted if e.key == "add_to_faction"], ["VAL"])
        league = ast_block(relative_entries("common/scripted_effects/ADISCORD_STP_scripted_effects.txt"), "STP_pc_form_hegemony_league")
        heg_late = {
            ("STS", "tag", "STS"): True,
            ("STS", "has_country_flag", "STP_pc_hegemony_league"): True,
            ("NOD", "exists", "yes"): True,
            ("NOD", "has_idea", "STP_pc_nod_client"): True,
            ("NOD", "is_in_faction_with", "STS"): False,
        }
        heg = list(selected_effects(league, heg_late, "STS"))
        self.assertFalse(any(e.key == "create_faction_from_template" for _, e in heg))
        self.assertEqual([e.value for _, e in heg if e.key == "add_to_faction"], ["NOD"])
        self.assertTrue(any(e.key == "template" and e.value == "faction_template_ADISCORD_standard" for e in walk(form)))
        self.assertFalse(any(e.key == "create_faction" for e in walk(form)))

    def test_scripted_advisor_role_contains_no_database_triggers(self) -> None:
        reward = block(war_focuses()["STP_pc_lib_civil_army"], "completion_reward")
        role = next(e.value for e in walk(reward) if e.key == "add_advisor_role")
        advisor = block(role, "advisor")
        self.assertFalse({"allowed", "visible", "available", "ai_will_do", "on_add", "on_remove"} & {e.key for e in advisor})
        self.assertEqual(scalar(advisor, "slot"), "high_command")

    def test_false_promises_are_removed_or_tied_to_existing_actions(self) -> None:
        focuses = war_focuses()
        competition = ast_block(focuses["STP_pc_lib_competition"], "completion_reward")
        self.assertTrue(any(e.key == "id" and e.value == "ADISCORD_STP_pc.13" for e in walk(competition)))
        self.assertTrue(any(e.key == "id" and e.value == "ADISCORD_STP_pc.14" for e in walk(competition)))
        prepare = ast_block(focuses["STP_pc_lib_prepare_neighbors"], "completion_reward")
        self.assertFalse(any(e.key == "set_country_flag" and e.value == "STP_pc_lib_neighbors_prepared" for e in walk(prepare)))
        self.assertNotIn("STP_pc_lib_neighbors_prepared", read(EFFECTS))
        self.assertNotIn("STP_pc_lib_neighbors_prepared", read(TRIGGERS))
        loc = read(LOC)
        self.assertNotIn("Наблюдатели, оружие, корпус", loc)
        self.assertNotIn("Флаги местных сил", loc)
        crisis = ast_block(focuses["STP_pc_lib_crisis"], "completion_reward")
        self.assertFalse(any(e.key in {"add_equipment_to_stockpile", "create_unit", "declare_war_on"} for e in walk(crisis)))
        civil = ast_block(focuses["STP_pc_lib_civil_army"], "completion_reward")
        self.assertTrue(any(e.key == "add_advisor_role" for e in walk(civil)))
        self.assertFalse(any(e.key == "add_political_power" for e in walk(civil)))
        self.assertTrue(any(e.key == "add_to_variable" for e in walk(civil)))
        regional = [entry.value for entry in focuses["STP_pc_heg_regional_system"] if entry.key == "prerequisite"]
        self.assertTrue(any(any(child.value == "STP_pc_heg_lock" for child in group) for group in regional))
        self.assertFalse(any(any(child.value == "STP_pc_heg_person" for child in group) for group in regional))
        declare = ast_block(relative_entries("common/scripted_effects/ADISCORD_STP_scripted_effects.txt"), "STP_pc_declare_liberation_war")
        self.assertFalse(any(e.key == "else_if" for e in declare))
        self.assertEqual(sum(1 for e in declare if e.key == "if"), 2)



def recovery_conditions(items, facts, scope="STS"):
    # Capital ownership is an explicit fixture input; the remaining conditions
    # are read from the scripts, including receipt and completion boundaries.
    def translate(values):
        result = []
        for entry in values:
            if entry.key == "capital_scope":
                result.append(Entry("capital_secure", "yes", entry.line))
            else:
                result.append(Entry(entry.key, translate(entry.value) if isinstance(entry.value, list) else entry.value, entry.line))
        return result
    return matches_conditions(translate(items), facts, scope)


def execute_recovery(items, facts, rewards, scope="STS"):
    definitions = {entry.key: entry.value for entry in entries(EFFECTS)}
    taken = False
    for entry in items:
        key, value = entry.key, entry.value
        if key in {"if", "else_if", "else"}:
            if key == "if":
                taken = False
            condition = next((e.value for e in value if e.key == "limit"), [])
            if not taken and (key == "else" or recovery_conditions(condition, facts, scope)):
                taken = True
                execute_recovery([e for e in value if e.key != "limit"], facts, rewards, scope)
        elif key == "hidden_effect":
            execute_recovery(value, facts, rewards, scope)
        elif key in {"set_variable", "set_temp_variable", "add_to_variable", "subtract_from_variable"}:
            name, amount = scalar(value, "var"), scalar(value, "value")
            try:
                amount = float(amount)
            except ValueError:
                amount = facts.get((scope, "variable", amount), 0)
            address = (scope, "variable", name)
            if key == "add_to_variable":
                amount += facts.get(address, 0)
            elif key == "subtract_from_variable":
                amount = facts.get(address, 0) - amount
            facts[address] = amount
            facts[(scope, "has_variable", name)] = True
        elif key == "clear_variable":
            facts.pop((scope, "variable", value), None)
            facts.pop((scope, "has_variable", value), None)
        elif key in {"STP_pw_update_recovery", "STP_pw_refresh_modifier", "ADISCORD_economy_mark_dirty"}:
            rewards.append(key)
        elif key in {"add_stability", "army_experience", "add_offsite_building", "add_political_power", "add_equipment_to_stockpile", "random_owned_controlled_state"}:
            rewards.append((key, value))
        elif key in {"custom_effect_tooltip", "effect_tooltip"}:
            continue
        elif key in {"STP_pw_finish_project", "STP_pw_party_finish_project", "STP_pw_cancel_project"}:
            execute_recovery(definitions[key], facts, rewards, scope)
        else:
            raise AssertionError(f"Unhandled recovery effect: {key}")


class PartyRecoveryTransactions(unittest.TestCase):
    def setUp(self):
        self.decisions = block(relative_entries("common/decisions/ADISCORD_STP_decisions.txt"), "STP_cw_war_council")
        self.projects = (("restore_ministries", "services", 60, "new_republic"),
                         ("reopen_port", "industry", 120, "homes_for_returnees"),
                         ("refit_guard", "army", 100, "army_register"))

    def facts(self, treasury=300):
        return {("STP", "STP_pw_can_reconstruct", "yes"): True,
                ("STP", "capital_secure", "yes"): True,
                ("STP", "STP_pw_party_has_port_capacity", "yes"): True,
                ("STP", "variable", "ADISCORD_economy_treasury"): treasury,
                **{("STP", "has_completed_focus", "STP_pw_party_" + focus): True
                   for _, _, _, focus in self.projects}}

    def test_paid_projects_deliver_once_or_refund_exactly_and_release_shared_slot(self):
        for name, pillar, price, focus in self.projects:
            decision = block(self.decisions, "STP_pw_party_" + name)
            for amount, paid in ((price - .01, False), (price, True)):
                facts, rewards = self.facts(amount), []
                execute_recovery(block(decision, "complete_effect"), facts, rewards, "STP")
                self.assertEqual(facts[("STP", "variable", "ADISCORD_economy_treasury")], 0 if paid else amount)
            for outcome in ("delivered", "cancelled", "capital_lost", "port_lost"):
                if outcome == "port_lost" and pillar != "industry":
                    continue
                facts, rewards = self.facts(), []
                execute_recovery(block(decision, "complete_effect"), facts, rewards, "STP")
                for other, _, _, _ in self.projects:
                    candidate = block(self.decisions, "STP_pw_party_" + other)
                    self.assertFalse(recovery_conditions(block(candidate, "available"), facts, "STP"))
                    execute_recovery(block(candidate, "complete_effect"), facts, rewards, "STP")
                self.assertEqual(facts[("STP", "variable", "ADISCORD_economy_treasury")], 300 - price)
                if outcome == "capital_lost": facts[("STP", "capital_secure", "yes")] = False
                if outcome == "port_lost": facts[("STP", "STP_pw_party_has_port_capacity", "yes")] = False
                callback = "cancel_effect" if outcome == "cancelled" else "remove_effect"
                execute_recovery(block(decision, callback), facts, rewards, "STP")
                expected = 300 - price if outcome == "delivered" else 300
                self.assertEqual(facts[("STP", "variable", "ADISCORD_economy_treasury")], expected)
                self.assertEqual(facts.get(("STP", "variable", "STP_pw_recovery_progress"), 0), int(outcome == "delivered"))
                self.assertFalse(facts.get(("STP", "has_variable", "STP_pw_project_deposit")))
                previous = (dict(facts), list(rewards))
                for callback in ("remove_effect", "cancel_effect"):
                    execute_recovery(block(decision, callback), facts, rewards, "STP")
                self.assertEqual((facts, rewards), previous)

    def test_party_finale_requires_completed_projects_and_border_program(self):
        final = war_focuses()["STP_pw_party_settled_state"]
        for progress in (0, 1, 2, 3):
            facts = {**self.facts(), ("STP", "variable", "STP_pw_recovery_progress"): progress}
            self.assertEqual(matches_conditions(block(final, "available"), facts, "STP"), progress == 3)
        self.assertIn("STP_pw_party_southern_defence", [e.value for e in walk(final) if e.key == "focus"])

    def test_nod_contract_requires_consent_resources_and_current_protectorate(self):
        base = {("NOD", "exists", "yes"): True, ("NOD", "has_capitulated", "no"): True,
                ("NOD", "is_subject", "no"): True, ("NOD", "equipment", "infantry_equipment"): 1000,
                ("NOD", "equipment", "support_equipment"): 100,
                ("STP", "exists", "yes"): True, ("STP", "has_capitulated", "no"): True,
                ("STP", "has_country_flag", "STP_cw_postwar"): True,
                ("STP", "has_country_flag", "STP_cw_won_union_battle"): True,
                ("STP", "has_global_flag", "STP_cw_union_wars_finished"): True,
                ("STP", "is_subject_of", "NOD"): True,
                ("STP", "has_country_flag", "STP_pw_party_nod_arms_pending"): True,
                ("STP", "ADISCORD_economy_can_spend_50", "yes"): True,
                ("STP", "variable", "ADISCORD_economy_treasury"): 50}
        for change in (None, (("NOD", "equipment", "infantry_equipment"), 999.99),
                       (("NOD", "equipment", "support_equipment"), 99.99),
                       (("STP", "ADISCORD_economy_can_spend_50", "yes"), False),
                       (("STP", "is_subject_of", "NOD"), False),
                       (("STP", "has_war_with", "NOD"), True),
                       (("STP", "has_country_flag", "STP_pw_party_nod_arms_pending"), False)):
            facts, events = dict(base), []
            if change: facts[change[0]] = change[1]
            effect = block(entries(EFFECTS), "STP_pw_party_settle_nod_arms")
            execute_package_effects(effect, facts, events, "NOD")
            paid = change is None
            self.assertEqual(facts[("STP", "variable", "ADISCORD_economy_treasury")], 0 if paid else 50)
            self.assertEqual(facts.get(("STP", "equipment", "infantry_equipment"), 0), 1000 if paid else 0)
            self.assertEqual(facts.get(("NOD", "variable", "ADISCORD_economy_treasury"), 0), 50 if paid else 0)
            prior = (dict(facts), list(events))
            execute_package_effects(effect, facts, events, "NOD")
            self.assertEqual((facts, events), prior)
        facts, events = dict(base), []
        execute_package_effects(option_by_name("ADISCORD_STP_pc.22", "ADISCORD_STP_pc.22.refuse"), facts, events, "NOD")
        self.assertEqual(facts[("STP", "variable", "ADISCORD_economy_treasury")], 50)
        self.assertEqual(facts[("NOD", "equipment", "infantry_equipment")], 1000)
        self.assertNotIn(("STP", "has_country_flag", "STP_pw_party_nod_arms_pending"), facts)


class PostwarRecoveryTransactions(unittest.TestCase):
    def setUp(self):
        self.effects = {e.key: e.value for e in entries(EFFECTS)}
        decisions = relative_entries("common/decisions/ADISCORD_STP_decisions.txt")
        self.decisions = block(decisions, "STP_cw_war_council")
        self.projects = (("STP_pw_restore_services", "services", 80),
                         ("STP_pw_restart_workshops", "industry", 120),
                         ("STP_pw_integrate_veterans", "army", 60))

    def facts(self, treasury=300):
        return {("STS", "STP_pw_can_reconstruct", "yes"): True,
                ("STS", "capital_secure", "yes"): True,
                ("STS", "variable", "ADISCORD_economy_treasury"): treasury}

    def test_fractional_affordability_and_shared_slot(self):
        for name, _, price in self.projects:
            decision = block(self.decisions, name)
            for balance, expected in ((price - .01, False), (price, True)):
                facts = self.facts(balance)
                self.assertEqual(recovery_conditions(block(decision, "custom_cost_trigger"), facts), expected)
            facts, rewards = self.facts(), []
            execute_recovery(block(decision, "complete_effect"), facts, rewards)
            self.assertEqual(facts[("STS", "variable", "ADISCORD_economy_treasury")], 300 - price)
            for other, _, _ in self.projects:
                self.assertFalse(recovery_conditions(block(block(self.decisions, other), "available"), facts))
                execute_recovery(block(block(self.decisions, other), "complete_effect"), facts, rewards)
            self.assertEqual(facts[("STS", "variable", "ADISCORD_economy_treasury")], 300 - price)
            self.assertEqual(facts[("STS", "variable", "STP_pw_project_deposit")], price)

    def test_cancel_refunds_once_across_month_end(self):
        for name, _, price in self.projects:
            facts, rewards = self.facts(), []
            decision = block(self.decisions, name)
            execute_recovery(block(decision, "complete_effect"), facts, rewards)
            facts[("STS", "variable", "ADISCORD_economy_current_month_action_costs")] = 0
            facts[("STS", "capital_secure", "yes")] = False
            execute_recovery(block(decision, "remove_effect"), facts, rewards)
            execute_recovery(block(decision, "cancel_effect"), facts, rewards)
            self.assertEqual(facts[("STS", "variable", "ADISCORD_economy_treasury")], 300)
            self.assertEqual(facts[("STS", "variable", "ADISCORD_economy_current_month_action_costs")], 0)
            self.assertEqual(facts[("STS", "variable", "ADISCORD_economy_current_month_action_income")], price)
            self.assertNotIn(("STS", "has_variable", "STP_pw_project_deposit"), facts)
            self.assertEqual(facts.get(("STS", "variable", "STP_pw_recovery_progress"), 0), 0)

    def test_completion_replay_and_wrong_project_callback(self):
        facts, rewards = self.facts(1000), []
        for index, (name, field, _) in enumerate(self.projects, 1):
            decision = block(self.decisions, name)
            execute_recovery(block(decision, "complete_effect"), facts, rewards)
            other = self.projects[index % 3][0]
            execute_recovery(block(block(self.decisions, other), "remove_effect"), facts, rewards)
            self.assertIn(("STS", "has_variable", "STP_pw_project_deposit"), facts)
            execute_recovery(block(decision, "remove_effect"), facts, rewards)
            snapshot = dict(facts), list(rewards)
            execute_recovery(block(decision, "remove_effect"), facts, rewards)
            execute_recovery(block(decision, "cancel_effect"), facts, rewards)
            self.assertEqual((facts, rewards), snapshot)
            self.assertEqual(facts[("STS", "variable", "STP_pw_recovery_" + field)], 1)
            self.assertEqual(facts[("STS", "variable", "STP_pw_recovery_progress")], index)
        self.assertEqual(facts[("STS", "variable", "ADISCORD_economy_treasury")], 740)

    def test_illegal_targets_cannot_start_native_campaign_wars(self):
        for tag in ("VAL", "NOD"):
            helper = expand(self.effects[f"STP_pc_declare_war_{tag.lower()}"])
            gate = expand(parse_clausewitz(f"STP_pc_can_confront_{tag.lower()} = yes"))
            facts = package_facts()
            self.assertTrue(matches_conditions(gate, facts, "STS"))
            scenarios = [("legal", facts, True)]
            for key in ((tag, "exists", "yes"), (tag, "has_capitulated", "no"),
                        ("STS", "is_subject", "no")):
                invalid = {**facts, key: False}
                self.assertFalse(matches_conditions(gate, invalid, "STS"), (tag, key))
                scenarios.append((str(key), invalid, False))
            allied = {**facts, ("STS", "is_in_faction_with", tag): True}
            self.assertFalse(matches_conditions(gate, allied, "STS"))
            scenarios.append(("allied", allied, False))
            existing = {**facts, ("STS", "has_war_with", tag): True}
            self.assertTrue(matches_conditions(gate, existing, "STS"))
            scenarios.append(("already at war", existing, False))
            for label, scenario, should_declare in scenarios:
                with self.subTest(target=tag, scenario=label):
                    chosen = list(selected_effects(helper, scenario, "STS"))
                    declarations = [prep_scalar(effect.value, "target")
                                    for _, effect in chosen if effect.key == "declare_war_on"]
                    self.assertEqual(declarations, [tag] if should_declare else [])
                    self.assertFalse(any(effect.key == "set_country_flag"
                                         and effect.value.startswith("STP_pc_war_")
                                         for _, effect in chosen))

    def test_invalid_recipient_releases_only_its_receipt_and_advances_queue(self):
        offer = block(entries(EFFECTS), "STP_pc_offer_liberation_package")
        accept = option_by_name("ADISCORD_STP_pc.11", "ADISCORD_STP_pc.11.a")
        close = option_by_name("ADISCORD_STP_pc.11", "ADISCORD_STP_pc.11.c")
        for invalid in ("war", "subject", "capitulated", "course"):
            facts, dispatched = package_facts(), []
            facts.update({("STS", "has_country_flag", "STP_pc_lib_package_pending"): True,
                          ("STS", "variable", "STP_pc_lib_package_tag"): 1,
                          ("STS", "has_country_flag", "STP_pc_lib_val_won"): True,
                          ("STS", "has_country_flag", "STP_pc_lib_nod_won"): True})
            if invalid == "war":
                facts[("STS", "has_war_with", "VAL")] = True
            elif invalid == "subject":
                facts[("VAL", "is_subject", "no")] = False
            elif invalid == "capitulated":
                facts[("VAL", "has_capitulated", "no")] = False
            else:
                facts[("STS", "variable", "STP_pc_course")] = 1
            before = dict(facts)
            execute_package_effects(accept, facts, dispatched, "VAL")
            self.assertEqual(facts, before, invalid)
            execute_package_effects(close, facts, dispatched, "VAL")
            self.assertNotIn(("VAL", "has_idea", "VAL_liberated_settlement"), facts)
            self.assertEqual(dispatched, [] if invalid == "course" else [("NOD", "ADISCORD_STP_pc.11")])
            execute_package_effects(offer, facts, dispatched)
            self.assertLessEqual(len(dispatched), 1, "the periodic recovery must not repeat an open offer")

    def test_withdrawn_kefreyt_terms_only_allow_closing(self):
        facts = package_facts()
        facts.update({("STS", "STP_pw_can_reconstruct", "yes"): True,
                      ("STS", "variable", "STP_pc_course"): 1})
        # Use the unexpanded predicate's explicit scenario facts for the event;
        # its diplomatic guard is separately covered by the target tests.
        options = [e.value for e in parsed_event("ADISCORD_STP_pc.9") if e.key == "option"]
        for valid in (False, True):
            available = []
            snapshot = {**facts, ("VAL", "STP_pw_kefreyt_terms_current", "yes"): valid,
                        ("VAL", "STP_pw_kefreyt_terms_current", "no"): not valid}
            for option in options:
                if matches_conditions(block(option, "trigger"), snapshot, "VAL"):
                    available.append(scalar(option, "name"))
            self.assertEqual(available, ["ADISCORD_STP_pc.9.b", "ADISCORD_STP_pc.9.c"] if valid else ["STP_pc_offer_closed"])


class PostwarDiplomacyTransactions(unittest.TestCase):
    def facts(self, tag, treasury=200, paid=False):
        facts = package_facts()
        facts.update({("STS", "variable", "STP_pc_course"): 1,
                      ("STS", "has_country_flag", "STP_cw_postwar"): True,
                      ("STS", "has_country_flag", "STP_cw_won_union_battle"): True,
                      ("STS", "has_global_flag", "STP_cw_union_wars_finished"): True,
                      ("STS", "variable", "ADISCORD_economy_treasury"): treasury,
                      ("STS", "has_country_flag", "STP_pw_kefreyt_accounts_settled"): paid,
                      ("STS", "has_variable", f"STP_pc_{tag.lower()}_offer_kind"): True,
                      ("STS", "variable", f"STP_pc_{tag.lower()}_offer_kind"): 1})
        return facts

    def test_recipient_acceptance_conserves_money_and_replay_cannot_pay_twice(self):
        for tag, number, paid, price in (("VAL", 17, False, 200), ("VAL", 17, True, 100), ("NOD", 18, False, 150)):
            option = option_by_name(f"ADISCORD_STP_pc.{number}", "STP_pc_accept_compact")
            for balance in (price - .01, price, price + 100):
                facts, events = self.facts(tag, balance, paid), []
                execute_package_effects(option, facts, events, tag)
                accepted = balance >= price
                self.assertEqual(facts[("STS", "variable", "ADISCORD_economy_treasury")], balance - price if accepted else balance)
                self.assertEqual(facts.get((tag, "variable", "ADISCORD_economy_treasury"), 0), price if accepted else 0)
                self.assertEqual(facts.get(("STS", "variable", "ADISCORD_economy_current_month_action_costs"), 0), price if accepted else 0)
                self.assertEqual(facts.get((tag, "variable", "ADISCORD_economy_current_month_action_income"), 0), price if accepted else 0)
                for country in ("STS", tag):
                    self.assertEqual(facts.get((country, "has_idea", f"STP_pc_{tag.lower()}_compact"), False), accepted)
                snapshot = dict(facts), list(events)
                execute_package_effects(option, facts, events, tag)
                self.assertEqual((facts, events), snapshot)

    def test_changed_country_or_course_closes_offer_without_payment(self):
        for tag, number in (("VAL", 17), ("NOD", 18)):
            option = option_by_name(f"ADISCORD_STP_pc.{number}", "STP_pc_accept_compact")
            for changed in ({(tag, "exists", "yes"): False}, {(tag, "is_subject", "no"): False},
                            {("STS", "has_war_with", tag): True}, {("STS", "variable", "STP_pc_course"): 2}):
                facts = {**self.facts(tag), **changed}
                snapshot = dict(facts)
                execute_package_effects(option, facts, [], tag)
                self.assertEqual(facts, snapshot)
                self.assertEqual(visible_option_names(f"ADISCORD_STP_pc.{number}", facts, tag), ["STP_pc_offer_closed"])

    def test_paid_campaign_is_idempotent_and_cancelled_preparation_never_delivers(self):
        council = block(relative_entries("common/decisions/ADISCORD_STP_decisions.txt"), "STP_cw_war_council")
        for tag in ("VAL", "NOD"):
            decision = block(council, f"STP_pw_prepare_{tag.lower()}_campaign")
            for balance in (99.99, 100, 240):
                facts, events = self.facts(tag, balance), []
                execute_package_effects(block(decision, "complete_effect"), facts, events)
                execute_package_effects(block(decision, "complete_effect"), facts, events)
                paid = balance >= 100
                self.assertEqual(facts[("STS", "variable", "ADISCORD_economy_treasury")], balance - 100 if paid else balance)
                self.assertEqual(events, [(tag, "ADISCORD_STP_pc.20")] if paid else [])
                execute_package_effects(block(decision, "cancel_effect"), facts, events)
                execute_package_effects(block(decision, "remove_effect"), facts, events)
                self.assertNotIn(("STS", "has_idea", f"STP_pc_{tag.lower()}_campaign_ready"), facts)
                self.assertNotIn(("STS", "has_variable", f"STP_pc_{tag.lower()}_campaign_deposit"), facts)

    def test_campaign_completion_consumes_receipt_and_invalid_target_cancels_readiness(self):
        council = block(relative_entries("common/decisions/ADISCORD_STP_decisions.txt"), "STP_cw_war_council")
        ideas = block(block(relative_entries("common/ideas/ADISCORD_STP_civil_war_ideas.txt"), "ideas"), "country")
        for tag in ("VAL", "NOD"):
            decision = block(council, f"STP_pw_prepare_{tag.lower()}_campaign")
            for valid in (False, True):
                facts, events = self.facts(tag), []
                execute_package_effects(block(decision, "complete_effect"), facts, events)
                facts[(tag, "exists", "yes")] = valid
                execute_package_effects(block(decision, "remove_effect"), facts, events)
                ready = f"STP_pc_{tag.lower()}_campaign_ready"
                self.assertEqual(facts.get(("STS", "has_idea", ready), False), valid)
                self.assertNotIn(("STS", "has_variable", f"STP_pc_{tag.lower()}_campaign_deposit"), facts)
                cancel = expand(block(block(ideas, ready), "cancel"))
                self.assertEqual(matches_conditions(cancel, facts, "STS"), not valid)


if __name__ == "__main__":
    unittest.main()
