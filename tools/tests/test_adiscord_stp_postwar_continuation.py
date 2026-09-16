from __future__ import annotations

import json
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


def read(path: Path) -> str:
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


class PostwarContinuationContracts(unittest.TestCase):
    def test_eighty_focuses_sit_on_the_resistance_war_tree(self) -> None:
        trees = [entry.value for entry in entries(FOCUS) if entry.key == "focus_tree"]
        war = next(tree for tree in trees if scalar(tree, "id") == "STP_cw_focus")
        prep = next(tree for tree in trees if scalar(tree, "id") == "STP_focus")
        war_ids = [scalar(entry.value, "id") for entry in war if entry.key == "focus"]
        prep_ids = [scalar(entry.value, "id") for entry in prep if entry.key == "focus"]
        pc_ids = [focus_id for focus_id in war_ids if focus_id.startswith("STP_pc_")]
        self.assertEqual(len(pc_ids), 80)
        self.assertEqual(len(set(pc_ids)), 80)
        self.assertFalse(any(focus_id.startswith("STP_pc_") for focus_id in prep_ids))
        self.assertEqual(scalar(next(entry.value for entry in war if entry.key == "focus" and scalar(entry.value, "id") == "STP_pc_after_victory"), "x"), "16")

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

    def test_split_copies_sotnikov_without_making_him_party_head(self) -> None:
        start = read(EFFECTS).split("STP_cw_start = {", 1)[1].split("STP_cw_begin_hostilities", 1)[0]
        self.assertIn("set_nationality = { character = STP_grigory_sotnikov target_country = STS }", start)
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
        val = next(e.value for e in ast_block(root, "OR") if e.key == "AND" and any(c.key == "tag" and c.value == "VAL" for c in e.value))
        nod_root = next(e.value for e in ast_block(root, "OR") if e.key == "AND" and any(c.key == "tag" and c.value == "NOD" for c in e.value))
        self.assertTrue(any(c.key == "has_country_flag" and c.value == "STP_pc_war_with_sts" for c in prep_walk(val)))
        self.assertTrue(any(c.key == "has_country_flag" and c.value == "STP_pc_war_with_sts" for c in prep_walk(nod_root)))

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

        stale_val = {**val_win, ("VAL", "variable", "STP_cw_capitulation_occupier"): 5}
        stale = list(selected_effects(begin, stale_val, "STS"))
        self.assertEqual([e.value for _, e in stale if e.key == "white_peace"], ["VAL"])
        stale_vars = [(s, prep_scalar(e.value, "var"), prep_scalar(e.value, "value")) for s, e in stale if e.key == "set_variable"]
        self.assertIn(("STS", "STP_pc_this_opponent", "1"), stale_vars)
        self.assertIn(("STS", "STP_pc_this_result", "0"), stale_vars)

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
        self.assertEqual(sorted(e.value for _, e in leftover if e.key == "white_peace"), ["NOD", "VAL"])

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
        self.assertTrue(any(e.key == "STP_pc_offer_liberation_package" for e in walk(independent)))

    def test_package_queue_handles_both_neighbors_refuse_and_reentry(self) -> None:
        offer = ast_block(relative_entries("common/scripted_effects/ADISCORD_STP_scripted_effects.txt"), "STP_pc_offer_liberation_package")
        both = {
            ("STS", "has_country_flag", "STP_pc_lib_package_pending"): False,
            ("STS", "has_country_flag", "STP_pc_lib_val_won"): True,
            ("STS", "has_country_flag", "STP_pc_lib_nod_won"): True,
            ("VAL", "exists", "yes"): True,
            ("NOD", "exists", "yes"): True,
        }
        first = list(selected_effects(offer, both, "STS"))
        self.assertEqual([(s, prep_scalar(e.value, "var"), prep_scalar(e.value, "value")) for s, e in first if e.key == "set_variable"],
                         [("STS", "STP_pc_lib_package_tag", "1")])
        self.assertTrue(any(scope == "VAL" and e.key == "country_event" for scope, e in first))
        self.assertFalse(any(scope == "STS" and e.key == "country_event" for scope, e in first))
        after_val = {**both, ("VAL", "has_idea", "VAL_liberated_settlement"): True}
        second = list(selected_effects(offer, after_val, "STS"))
        self.assertEqual([(s, prep_scalar(e.value, "var"), prep_scalar(e.value, "value")) for s, e in second if e.key == "set_variable"],
                         [("STS", "STP_pc_lib_package_tag", "2")])
        refused_val = {**both, ("VAL", "has_country_flag", "STP_pc_val_refused_package"): True}
        after_refuse = list(selected_effects(offer, refused_val, "STS"))
        self.assertEqual([(s, prep_scalar(e.value, "var"), prep_scalar(e.value, "value")) for s, e in after_refuse if e.key == "set_variable"],
                         [("STS", "STP_pc_lib_package_tag", "2")])
        pending = list(selected_effects(offer, {**both, ("STS", "has_country_flag", "STP_pc_lib_package_pending"): True}, "STS"))
        self.assertFalse(any(e.key in {"country_event", "set_variable"} for _, e in pending))
        done = list(selected_effects(offer, {
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
        refuse_nod = list(selected_effects(refuse, {("STS", "variable", "STP_pc_lib_package_tag"): 2}, "NOD"))
        self.assertIn(("NOD", "set_country_flag", "STP_pc_nod_refused_package"),
                      [(scope, e.key, e.value) for scope, e in refuse_nod])
        self.assertNotIn(("VAL", "set_country_flag", "STP_pc_nod_refused_package"),
                         [(scope, e.key, e.value) for scope, e in refuse_nod])
        self.assertTrue(any(scope == "STS" and e.key == "STP_pc_finish_liberation_package" for scope, e in refuse_nod))

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
        self.assertTrue(any(e.key == "add_political_power" for e in walk(civil)))
        regional = [entry.value for entry in focuses["STP_pc_heg_regional_system"] if entry.key == "prerequisite"]
        self.assertTrue(any(any(child.value == "STP_pc_heg_lock" for child in group) for group in regional))
        self.assertFalse(any(any(child.value == "STP_pc_heg_person" for child in group) for group in regional))
        declare = ast_block(relative_entries("common/scripted_effects/ADISCORD_STP_scripted_effects.txt"), "STP_pc_declare_liberation_war")
        self.assertFalse(any(e.key == "else_if" for e in declare))
        self.assertEqual(sum(1 for e in declare if e.key == "if"), 2)


if __name__ == "__main__":
    unittest.main()
