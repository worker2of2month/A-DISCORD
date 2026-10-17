"""Static contracts of the western final war between Vorkerland and Itora.

The checks cover script wiring only: side lists, terminal cleanup, flag order,
path focuses and the Itoran focus aggregate. Engine war, faction and peace
behaviour needs a game run.
"""

from pathlib import Path
from collections import Counter
from dataclasses import replace
import json
import re
import unittest

from tools.tests.test_adiscord_south_final_war import body, flatten, focus_blocks, scope_calls
from tools.tests.test_adiscord_stp_preparation import block, scalar, matches_conditions, selected_effects
from tools.validators.validate_adiscord_division_templates import parse_clausewitz

ROOT = Path(__file__).resolve().parents[2]
EFFECTS = ROOT / "common/scripted_effects/ADISCORD_west_final_war_effects.txt"
TRIGGERS = ROOT / "common/scripted_triggers/ADISCORD_west_final_war_triggers.txt"
EVENTS = ROOT / "events/ADISCORD_west_final_war_events.txt"
PEACE = ROOT / "common/on_actions/09_ADISCORD_scripted_peace_on_actions.txt"
IVN_TREE = ROOT / "focus_trees/IVN/main/focuses.txt"
WRK_TREE = ROOT / "focus_trees/Vorkerland/civil_war/focuses.txt"
WORKER_TREE = ROOT / "focus_trees/Vorkerland/worker_confederation/focuses.txt"
TECHNICAL_TREE = ROOT / "focus_trees/Vorkerland/technical_directorate/focuses.txt"
EMPIRE_TREE = ROOT / "focus_trees/Vorkerland/world_empire/focuses.txt"
DECISIONS = ROOT / "common/decisions/ADISCORD_west_final_war_decisions.txt"
REGIONAL = ("WIT", "IIA", "IBA", "IBL", "PWR", "PSD", "ZAO", "WPA", "WPS", "ROM", "TRU")
CHAMPIONS = ("WRK", "IVN")
ROUTES = ("worker", "joint", "utilitarian")
CORRIDOR_STATES = {"90", "91", "93", "94"}
HOME_STATES = {"25", "92", "95", "96", "32"}


class WestFinalWarContractTests(unittest.TestCase):
    def test_every_itoran_settlement_subject_uses_its_overlords_color(self):
        source = parse_clausewitz(
            (ROOT / "common/autonomous_states/ADISCORD_west_final_war_subjects.txt").read_text(encoding="utf-8")
        )
        autonomies = {scalar(entry.value, "id"): entry.value for entry in source}
        for name in ("autonomy_IVN_guaranteed_confederation", "autonomy_IVN_emergency_trusteeship"):
            with self.subTest(autonomy=name):
                self.assertEqual(scalar(autonomies[name], "use_overlord_color"), "yes")
        ordinary = parse_clausewitz((ROOT / "common/autonomous_states/puppet.txt").read_text(encoding="utf-8"))
        self.assertEqual(scalar(block(ordinary, "autonomy_state"), "use_overlord_color"), "yes")

    def test_every_regional_state_is_bound_offered_and_settled(self):
        for name in (
            "ADISCORD_west_assign_bound_sides",
            "ADISCORD_west_offer_side_choices",
            "ADISCORD_west_faction_partners_follow",
        ):
            calls = set(re.findall(r"\b([A-Z]{3}) = \{", body(EFFECTS, name)))
            self.assertEqual(calls, set(REGIONAL), name)
        for name, effect in (
            ("ADISCORD_west_mark_losers", "ADISCORD_west_mark_loser"),
            ("ADISCORD_west_clear_participants", "ADISCORD_west_clear_participant"),
            ("ADISCORD_west_apply_settlement", "ADISCORD_west_settle_member"),
        ):
            self.assertEqual(scope_calls(body(EFFECTS, name), effect), set(REGIONAL) | set(CHAMPIONS), name)
        # WRK is the enemy every Itoran participant makes peace with.
        self.assertEqual(
            scope_calls(body(EFFECTS, "ADISCORD_west_end_final_wars"), "ADISCORD_west_end_member_wars"),
            set(REGIONAL) | {"IVN"},
        )
        regional = body(TRIGGERS, "ADISCORD_west_regional_country")
        self.assertEqual(set(re.findall(r"tag = ([A-Z]{3})", regional)), set(REGIONAL))

    def test_resolution_flag_precedes_every_white_peace(self):
        for name in (
            "ADISCORD_west_final_resolve_wrk_victory",
            "ADISCORD_west_final_resolve_ivn_victory",
            "ADISCORD_west_final_resolve_without_hegemon",
        ):
            source = body(EFFECTS, name)
            self.assertLess(
                source.index("set_global_flag = ADISCORD_west_final_resolved"),
                source.index("ADISCORD_west_end_final_wars = yes"),
                name,
            )
            self.assertIn("ADISCORD_west_close_campaign_state = yes", source, name)

    def test_settlement_variables_use_native_global_scope(self):
        source = EFFECTS.read_text(encoding="utf-8")
        self.assertNotIn("set_global_variable", source)
        for winner, side in (("wrk", "1"), ("ivn", "2")):
            with self.subTest(winner=winner):
                entries = parse_clausewitz(
                    body(EFFECTS, f"ADISCORD_west_final_resolve_{winner}_victory")
                )
                writes = [
                    {item.key: item.value for item in entry.value}
                    for entry in flatten(entries)
                    if entry.key == "set_variable"
                ]
                self.assertTrue(writes)
                self.assertTrue(all(w["var"].startswith("global.") for w in writes))
                self.assertEqual(
                    {w["var"] for w in writes},
                    {
                        "global.ADISCORD_west_winner_side",
                        "global.ADISCORD_west_terms",
                        "global.ADISCORD_west_subject_type",
                        "global.ADISCORD_west_transfer",
                    },
                )
                self.assertEqual(
                    [w["value"] for w in writes if w["var"].endswith("winner_side")],
                    [side],
                )

    def test_side_choices_precede_faction_teardown(self):
        for side in ("wrk", "ivn"):
            source = body(EFFECTS, f"ADISCORD_west_join_{side}_side")
            self.assertIn("set_variable = { var = ADISCORD_west_side", source)
            self.assertIn("country_event = { id = ADISCORD_west.11 hours = 1 }", source)
            for premature in ("white_peace", "leave_faction", "dismantle_faction", "add_to_war"):
                self.assertNotIn(premature, source)

    def test_entry_armistice_preserves_opponents_and_outside_wars(self):
        entries = parse_clausewitz(body(EFFECTS, "ADISCORD_west_prepare_side_entry"))
        enemies = block(entries, "every_enemy_country")
        limit = block(enemies, "limit")
        self.assertIn("has_variable", {entry.key for entry in limit})
        comparison = {entry.key: entry.value for entry in block(limit, "check_variable")}
        self.assertEqual(
            comparison,
            {
                "var": "ADISCORD_west_side",
                "value": "PREV.ADISCORD_west_side",
                "compare": "equals",
            },
        )
        self.assertIn(("white_peace", "PREV"), [(e.key, e.value) for e in enemies])
        source = body(EFFECTS, "ADISCORD_west_prepare_side_entry")
        self.assertNotIn("add_to_faction", source)
        self.assertNotIn("add_to_war", source)
        self.assertTrue(source.strip().endswith("country_event = { id = ADISCORD_west.12 hours = 1 }"))

    def test_entry_joins_exact_war_even_with_existing_enemy_relation(self):
        source = body(EFFECTS, "ADISCORD_west_complete_side_entry")
        self.assertNotIn("has_war_with", source)
        entries = parse_clausewitz(source)
        wars = [
            {item.key: item.value for item in entry.value}
            for entry in flatten(entries)
            if entry.key == "add_to_war"
        ]
        self.assertEqual(
            {(w["targeted_alliance"], w["enemy"]) for w in wars},
            {("WRK", "IVN"), ("IVN", "WRK")},
        )
        self.assertTrue(all(w["single_target_only"] == "yes" for w in wars))

    def test_delayed_entry_cannot_reopen_a_finished_campaign(self):
        events = parse_clausewitz(EVENTS.read_text(encoding="utf-8"))
        for number, effect in ((11, "prepare"), (12, "complete")):
            event = next(
                entry.value for entry in events
                if entry.key == "country_event"
                and any(e.key == "id" and e.value == f"ADISCORD_west.{number}" for e in entry.value)
            )
            trigger = block(event, "trigger")
            required = {(e.key, e.value) for e in trigger if isinstance(e.value, str)}
            self.assertTrue({
                ("ADISCORD_west_final_active", "yes"),
                ("exists", "yes"),
                ("has_variable", "ADISCORD_west_side"),
            }.issubset(required))
            self.assertEqual([(e.key, e.value) for e in block(trigger, "WRK")], [("has_war_with", "IVN")])
            self.assertEqual(
                [(e.key, e.value) for e in block(event, "immediate")],
                [(f"ADISCORD_west_{effect}_side_entry", "yes")],
            )

    def test_every_terminal_path_releases_campaign_status(self):
        close = body(EFFECTS, "ADISCORD_west_close_member_state")
        self.assertIn("RUS_crisis_release_other_major = yes", close)
        self.assertLess(close.index("clr_country_flag = ADISCORD_west_added_major"), close.index("RUS_crisis_release_other_major = yes"))
        self.assertIn("ADISCORD_west_remove_path_spirit = yes", close)
        self.assertEqual(
            scope_calls(body(EFFECTS, "ADISCORD_west_close_campaign_state"), "ADISCORD_west_close_member_state"),
            set(CHAMPIONS),
        )
        spirits = set(re.findall(r"add_ideas = (ADISCORD_west_\w+)", body(EFFECTS, "ADISCORD_west_add_path_spirit")))
        removed = set(re.findall(r"remove_ideas = (ADISCORD_west_\w+)", body(EFFECTS, "ADISCORD_west_remove_path_spirit")))
        self.assertEqual(len(spirits), 7)
        self.assertEqual(spirits, removed)

    def test_every_winner_path_has_terms(self):
        wrk = body(EFFECTS, "ADISCORD_west_final_resolve_wrk_victory")
        for route in ROUTES[:2]:
            self.assertIn(f"has_country_flag = ADISCORD_vorkerland_route_{route}", wrk)
        self.assertIn("var = global.ADISCORD_west_subject_type value = 5", wrk)
        self.assertNotIn("var = global.ADISCORD_west_terms value = 1", wrk)
        self.assertIn("var = global.ADISCORD_west_transfer value = 2", wrk)
        ivn = body(EFFECTS, "ADISCORD_west_final_resolve_ivn_victory")
        self.assertIn("ADISCORD_west_ivn_shield_course = yes", ivn)
        self.assertIn("ADISCORD_west_ivn_emergency_course = yes", ivn)
        self.assertIn("var = global.ADISCORD_west_transfer value = 1", ivn)
        types = body(EFFECTS, "ADISCORD_west_apply_subject_type")
        autonomies = set(re.findall(r"autonomy_state = (\w+)", types))
        subject_government = body(ROOT / "common/scripted_effects/ADISCORD_vorkerland_effects.txt", "ADISCORD_vorkerland_pw_apply_subject_government")
        autonomies.update(re.findall(r"autonomy_state = (\w+)", subject_government))
        defined = set(re.findall(r"\bid = (\w+)", (ROOT / "common/autonomous_states/ADISCORD_west_final_war_subjects.txt").read_text(encoding="utf-8")))
        self.assertEqual(autonomies - {"autonomy_puppet"}, defined)
        transfer = body(EFFECTS, "ADISCORD_west_transfer_to_root")
        self.assertIn("has_country_flag = ADISCORD_west_settlement_pending", transfer)

    def test_deadline_scores_only_occupied_enemy_land_and_a_tie_is_a_truce(self):
        source = body(EFFECTS, "ADISCORD_west_final_resolve_by_control")
        counted = set(re.findall(r"\b(\d+) = \{ ADISCORD_west_count_occupied_state = yes \}", source))
        self.assertEqual(counted, CORRIDOR_STATES | HOME_STATES)
        # A lost capital moves, so the federal capital is counted as a fixed state.
        self.assertNotIn("capital_scope", source)
        occupied = body(EFFECTS, "ADISCORD_west_count_occupied_state")
        self.assertIn("owner = { ADISCORD_west_on_ivn_side = yes }", occupied)
        self.assertIn("owner = { ADISCORD_west_on_wrk_side = yes }", occupied)
        effects = EFFECTS.read_text(encoding="utf-8")
        # Holding one's own corridor or declaring the war never decides the result.
        self.assertNotIn("ADISCORD_west_count_key_state", effects)
        self.assertNotIn("declarer_side", effects)
        tie = source[source.rindex("else = {"):]
        self.assertIn("ADISCORD_west_final_resolve_without_hegemon = yes", tie)
        self.assertIn("news_event = { id = ADISCORD_west.31 hours = 2 }", tie)
        self.assertNotIn("_victory", tie)
        events = EVENTS.read_text(encoding="utf-8")
        news = events[events.index("\tid = ADISCORD_west.31\n"):events.index("\tid = ADISCORD_west.40\n")]
        self.assertIn("ADISCORD_west.31.t_truce", news)
        self.assertIn("ADISCORD_west.31.d_truce", news)
        self.assertIn("ADISCORD_west.31.b", news)
        self.assertIn("country_event = { id = ADISCORD_west.20 days = 720 }", body(EFFECTS, "ADISCORD_west_final_war_start"))
        self.assertIn("days > 718", events)

    def test_champion_capitulation_owns_the_settlement(self):
        text = PEACE.read_text(encoding="utf-8")
        section = text[text.index("# BEGIN west_final:on_capitulation"):text.index("# END west_final:on_capitulation")]
        self.assertIn("set_global_flag = skip_default_capitulation", section)
        self.assertIn("ADISCORD_west_final_resolve_ivn_victory = yes", section)
        self.assertIn("ADISCORD_west_final_resolve_wrk_victory = yes", section)
        for hook in ("on_peace", "on_annex", "on_puppet"):
            section = text[text.index(f"# BEGIN west_final:{hook}"):text.index(f"# END west_final:{hook}")]
            self.assertIn("ADISCORD_west_final_close_external = yes", section, hook)

    def test_clock_has_one_periodic_driver(self):
        drivers = []
        for path in (ROOT / "common/on_actions").glob("*.txt"):
            if "ADISCORD_west_crisis_month = yes" in path.read_text(encoding="utf-8-sig"):
                drivers.append(path.name)
        self.assertEqual(drivers, ["01_ADISCORD_vorkerland_collapse_on_actions.txt"])
        source = (ROOT / "common/on_actions/01_ADISCORD_vorkerland_collapse_on_actions.txt").read_text(encoding="utf-8")
        hook = source[source.index("on_monthly_WRK = {"):]
        self.assertLess(hook.index("ADISCORD_west_crisis_open = yes"), hook.index("ADISCORD_west_crisis_month = yes"))

    def test_each_path_has_one_final_focus(self):
        ivn = focus_blocks(IVN_TREE)
        wrk = focus_blocks(WRK_TREE)
        worker = focus_blocks(WORKER_TREE)
        technical = focus_blocks(TECHNICAL_TREE)
        empire = focus_blocks(EMPIRE_TREE)
        finals = {
            "IVN_shield_over_the_west": ivn,
            "IVN_emergency_march_west": ivn,
            "IVN_revanche_march_on_vorkerland": ivn,
            "WRK_worker_west_mandate_for_itora": worker,
            "WRK_joint_west_return_of_the_marches": wrk,
            "WRK_utilitarian_west_engineering_border": technical,
            "WRK_empire_itora_must_fall": empire,
        }
        starters = set()
        for tree in (ivn, wrk, worker, technical, empire):
            for identifier, focus in tree.items():
                if "ADISCORD_west_final_war_start" in repr(focus):
                    starters.add(identifier)
        self.assertEqual(starters, set(finals))
        for identifier, tree in finals.items():
            available = repr(next(e.value for e in tree[identifier] if e.key == "available"))
            self.assertIn("ADISCORD_west_final_can_start", available, identifier)
        # The joint chain stays in the civil-war tree; the other routes own their trees.
        chain = [identifier for identifier in wrk if identifier.startswith("WRK_joint_west_")]
        self.assertEqual(len(chain), 4)
        for identifier in chain:
            allow = repr(next(e.value for e in wrk[identifier] if e.key == "allow_branch"))
            self.assertIn("ADISCORD_vorkerland_route_joint", allow, identifier)
        self.assertFalse([key for key in wrk if key.startswith(("WRK_worker_west_", "WRK_utilitarian_west_"))])

    def test_heritage_focuses_reward_the_western_settlement(self):
        heritage = {
            "WRK_worker_west_confederate_charter": (WORKER_TREE, "ADISCORD_west_hegemon_WRK"),
            "WRK_joint_west_imperial_settlement": (WRK_TREE, "ADISCORD_west_hegemon_WRK"),
            "WRK_utilitarian_west_technical_trusteeship": (TECHNICAL_TREE, "ADISCORD_west_hegemon_WRK"),
        }
        for identifier, (path, flag) in heritage.items():
            focus = focus_blocks(path)[identifier]
            self.assertIn(flag, repr(next(e.value for e in focus if e.key == "available")), identifier)
            self.assertNotIn("unlock_decision_tooltip", repr(focus), identifier)
            self.assertTrue(block(focus, "completion_reward"), identifier)
            # Heritage follows the course, not the final war focus: the rival may declare first.
            self.assertNotIn("final_war_start", repr(focus), identifier)

    def test_itora_keeps_only_the_northern_border_award(self):
        victory = parse_clausewitz(body(EFFECTS, "ADISCORD_west_final_resolve_ivn_victory"))
        terms = [
            {e.key: e.value for e in entry.value}
            for entry in flatten(victory)
            if entry.key == "set_variable"
        ]
        # Subjects by default; only the revanche annexes the defeated.
        self.assertEqual(
            [e["value"] for e in terms if e["var"] == "global.ADISCORD_west_terms"],
            ["2", "1"],
        )
        revanche = body(EFFECTS, "ADISCORD_west_final_resolve_ivn_victory")
        self.assertLess(revanche.index("ADISCORD_west_ivn_revanche_course = yes"), revanche.index("var = global.ADISCORD_west_terms value = 1"))
        settlement = parse_clausewitz(body(EFFECTS, "ADISCORD_west_apply_settlement"))
        corridor = block(settlement, "if")
        self.assertEqual({e.key for e in corridor if e.key.isdigit()}, {"90", "91", "93", "94"})
        self.assertIn("value='1'", repr(block(corridor, "limit")))
        transfer = body(EFFECTS, "ADISCORD_west_transfer_to_root")
        self.assertIn("owner = { has_country_flag = ADISCORD_west_settlement_pending }", transfer)
        heritage = focus_blocks(IVN_TREE)["IVN_west_heritage"]
        self.assertIn("ADISCORD_west_hegemon_IVN", repr(block(heritage, "available")))
        self.assertNotIn("unlock_decision_tooltip", repr(block(heritage, "completion_reward")))

    def test_humanist_shield_requires_humanism(self):
        ivn = focus_blocks(IVN_TREE)
        available = repr(next(e.value for e in ivn["IVN_humanist_shield"] if e.key == "available"))
        self.assertIn("key='has_government', value='humanism'", available)
        exclusive = repr(next(e.value for e in ivn["IVN_humanist_shield"] if e.key == "mutually_exclusive"))
        self.assertIn("IVN_emergency_order", exclusive)
        self.assertIn("IVN_adopt_emergency_order", repr(ivn["IVN_emergency_order"]))

    def test_league_answers_clear_the_pending_offer(self):
        source = EVENTS.read_text(encoding="utf-8")
        event = source[source.index("\tid = ADISCORD_west.40\n"):source.index("\tid = ADISCORD_west.41\n")]
        self.assertEqual(event.count("clr_country_flag = ADISCORD_west_league_offer_pending"), 2)
        self.assertIn("NOT = { has_country_flag = ADISCORD_west_league_offer_pending }", body(TRIGGERS, "ADISCORD_west_league_target_valid"))

    def test_vorkerland_treaties_mirror_the_league_and_let_the_target_answer(self):
        decisions = DECISIONS.read_text(encoding="utf-8")
        for name, unlock, lean in (
            ("ADISCORD_west_wrk_offer_front_treaty", "ADISCORD_west_wrk_treaties_unlocked", "ADISCORD_west_leans_to_wrk_ally"),
            ("ADISCORD_west_ivn_offer_league", "ADISCORD_west_ivn_league_unlocked", "ADISCORD_west_leans_to_ivn_ally"),
        ):
            start = decisions.index(f"\t{name} = {{")
            decision = decisions[start:decisions.index("\n\t}\n", start)]
            self.assertEqual(set(re.search(r"targets = \{ ([^}]*) \}", decision)[1].split()), set(REGIONAL))
            self.assertIn(f"{unlock} = yes", decision)
            self.assertIn("FROM = { ADISCORD_west_league_target_valid = yes }", decision)
            self.assertIn(f"FROM = {{ {lean} = yes }}", decision)
            self.assertNotIn("add_to_faction", decision)
        league = body(TRIGGERS, "ADISCORD_west_ivn_league_unlocked")
        for course in ("IVN_shield_league_of_republics", "IVN_emergency_protectorates", "IVN_revanche_iron_protectorate"):
            self.assertIn(f"has_completed_focus = {course}", league)
        source = EVENTS.read_text(encoding="utf-8")
        offer = source[source.index("\tid = ADISCORD_west.43\n"):source.index("\tid = ADISCORD_west.44\n")]
        self.assertEqual(offer.count("clr_country_flag = ADISCORD_west_league_offer_pending"), 2)
        accept = offer[:offer.index("name = ADISCORD_west.43.b")]
        for guard in ("is_in_faction = no", "NOT = { has_war_with = FROM }", "NOT = { has_global_flag = ADISCORD_west_final_started }"):
            self.assertIn(guard, accept)
        self.assertLess(accept.index("create_faction_from_template"), accept.index("add_to_faction = ROOT"))
        partners = body(EFFECTS, "ADISCORD_west_wrk_arm_front_partners")
        self.assertEqual(set(re.findall(r"\b([A-Z]{3}) = \{ ADISCORD_west_wrk_arm_front_partner = yes \}", partners)), set(REGIONAL))
        self.assertIn("is_in_faction_with = WRK", body(EFFECTS, "ADISCORD_west_wrk_arm_front_partner"))

    def test_events_are_registered_and_localised(self):
        source = EVENTS.read_text(encoding="utf-8")
        defined = set(re.findall(r"\bid = (ADISCORD_west\.\d+)", source))
        registry = json.loads((ROOT / "tools/data/adiscord_event_ids.json").read_text(encoding="utf-8"))
        registered = {e["id"] for e in registry["events"] if e["namespace"] == "ADISCORD_west"}
        self.assertEqual(defined, registered)
        keys = set(re.findall(r"(?:title|desc|name|text) = (ADISCORD_west\.[\w.]+)", source))
        keys |= set(re.findall(r"custom_effect_tooltip = (\w+)", source))
        for language in ("russian", "english"):
            path = ROOT / f"localisation/{language}/ADISCORD_west_final_war_l_{language}.yml"
            raw = path.read_bytes()
            self.assertTrue(raw.startswith(b"\xef\xbb\xbf"), language)
            present = set(re.findall(r"(?m)^ ([\w.]+):", raw.decode("utf-8-sig")))
            self.assertEqual(sorted(keys - present), [], language)

    def test_itoran_tree_is_localised(self):
        source = IVN_TREE.read_text(encoding="utf-8")
        focuses = set(focus_blocks(IVN_TREE))
        tooltips = set(re.findall(r"\btooltip = (IVN_\w+)", source))
        for language in ("russian", "english"):
            path = ROOT / f"localisation/{language}/ADISCORD_IVN_l_{language}.yml"
            raw = path.read_bytes()
            self.assertTrue(raw.startswith(b"\xef\xbb\xbf"), language)
            present = set(re.findall(r"(?m)^ ([\w.]+):", raw.decode("utf-8-sig")))
            expected = focuses | {f + "_desc" for f in focuses} | tooltips | {"IVN_order_dynamic"}
            self.assertEqual(sorted(expected - present), [], language)

    def test_ai_commits_both_champions(self):
        source = (ROOT / "common/ai_strategy/ADISCORD_west_final_war_ai.txt").read_text(encoding="utf-8")
        self.assertIn("ADISCORD_west_wrk_front_ivn = {", source)
        self.assertIn("ADISCORD_west_ivn_front_wrk = {", source)
        profiles = (
            ("ADISCORD_west_wrk_front_ivn", "ivn"),
            ("ADISCORD_west_wrk_hold_ivn", "ivn"),
            ("ADISCORD_west_ivn_front_wrk", "wrk"),
        )
        for name, enemy_side in profiles:
            profile = body(ROOT / "common/ai_strategy/ADISCORD_west_final_war_ai.txt", name)
            self.assertIn("abort_when_not_enabled = yes", profile)
            # The corridor separates the champions; requests cover the whole opposing side.
            self.assertEqual(profile.count(f"ADISCORD_west_on_{enemy_side}_side = yes"), 2, name)
        offensives = ("ADISCORD_west_wrk_front_ivn", "ADISCORD_west_ivn_front_wrk")
        manual = {
            re.search(r"manual_attack = (\w+)", body(ROOT / "common/ai_strategy/ADISCORD_west_final_war_ai.txt", name))[1]
            for name in offensives
        }
        self.assertEqual(manual, {"yes"})

    def test_every_wrk_route_seeds_its_own_constituency(self):
        seed = body(EFFECTS, "ADISCORD_west_seed_leans")
        for route in ROUTES[:2]:
            self.assertIn(f"has_country_flag = ADISCORD_vorkerland_route_{route}", seed, route)
        self.assertIn("has_global_flag = ADISCORD_vorkerland_free_republics_guaranteed_by_ivn", seed)
        self.assertNotIn("set_variable = { var = ADISCORD_west_lean", seed)
        self.assertEqual(set(re.findall(r"\b([A-Z]{3}) = \{ add_to_variable = \{ var = ADISCORD_west_lean", seed)) - {"WRK", "IVN"}, set(REGIONAL))
        recognition = (ROOT / "common/decisions/ADISCORD_vorkerland_decisions.txt").read_text(encoding="utf-8")
        recognition = recognition[recognition.index("ADISCORD_vorkerland_recognize_free_republics = {"):]
        recognition = recognition[:recognition.index("ai_will_do")]
        self.assertIn("ROM = { ADISCORD_west_push_lean = yes }", recognition)
        self.assertIn("TRU = { ADISCORD_west_push_lean = yes }", recognition)

    def test_gameplay_files_have_no_bom(self):
        for path in (EFFECTS, TRIGGERS, EVENTS, IVN_TREE):
            self.assertFalse(path.read_bytes().startswith(b"\xef\xbb\xbf"), path.name)


class WesternInfluenceTests(unittest.TestCase):
    """Static contracts of the lean scale, neutrality and transit."""

    INFLUENCE_DECISIONS = (
        "ADISCORD_west_send_envoys",
        "ADISCORD_west_ship_arms",
        "ADISCORD_west_wrk_offer_front_treaty",
        "ADISCORD_west_ivn_offer_league",
        "ADISCORD_west_ivn_humanitarian_convoys",
        "ADISCORD_west_ivn_ultimatum",
        "ADISCORD_west_call_to_arms",
    )

    @classmethod
    def setUpClass(cls):
        cls.effects = EFFECTS.read_text(encoding="utf-8")
        cls.events = EVENTS.read_text(encoding="utf-8")
        cls.decisions = DECISIONS.read_text(encoding="utf-8")

    def decision(self, name):
        start = self.decisions.index(f"\t{name} = {{")
        return self.decisions[start:self.decisions.index("\n\t}\n", start)]

    def test_seeding_runs_once_at_the_verified_reunification(self):
        finalize = body(ROOT / "common/scripted_effects/ADISCORD_vorkerland_effects.txt", "ADISCORD_vorkerland_finalize_reunified_wrk")
        call = finalize.index("ADISCORD_west_seed_leans = yes")
        guard = finalize.rindex("NOT = { has_global_flag = ADISCORD_vorkerland_collapse_finished }", 0, call)
        self.assertLess(guard, call)
        self.assertLess(call, finalize.index("set_global_flag = ADISCORD_vorkerland_collapse_finished"))
        seed = body(EFFECTS, "ADISCORD_west_seed_leans")
        self.assertIn("ADISCORD_west_clamp_all_leans = yes", seed)
        for tag in CHAMPIONS:
            self.assertIn(f"{tag} = {{ add_to_variable = {{ var = ADISCORD_west_influence_power value = 10 }} }}", seed)

    def test_push_follows_the_acting_champion_and_stays_bounded(self):
        push = body(EFFECTS, "ADISCORD_west_push_lean")
        self.assertIn("limit = { ROOT = { tag = WRK } }", push)
        self.assertIn("add_to_variable = { var = ADISCORD_west_lean value = ADISCORD_west_push }", push)
        self.assertIn("subtract_from_variable = { var = ADISCORD_west_lean value = ADISCORD_west_push }", push)
        self.assertIn("clamp_variable = { var = ADISCORD_west_lean min = -100 max = 100 }", push)
        self.assertIn("ADISCORD_west_refresh_transit = yes", push)
        everyone = body(EFFECTS, "ADISCORD_west_push_all_leans")
        self.assertEqual(set(re.findall(r"\b([A-Z]{3}) = \{ ADISCORD_west_push_lean = yes \}", everyone)), set(REGIONAL))

    def test_ai_side_choice_follows_the_lean_exactly(self):
        choice = self.events[self.events.index("\tid = ADISCORD_west.10\n"):self.events.index("\tid = ADISCORD_west.13\n")]
        options = choice.split("\toption = {")[1:]
        self.assertEqual(len(options), 3)
        expected = (
            ("ADISCORD_west_join_wrk_side = yes", "ADISCORD_west_leans_to_wrk_ally = yes"),
            ("ADISCORD_west_join_ivn_side = yes", "ADISCORD_west_leans_to_ivn_ally = yes"),
            ("ADISCORD_west_declare_neutrality = yes", "NOT = { ADISCORD_west_leans_to_wrk_ally = yes }"),
        )
        for option, (effect, condition) in zip(options, expected):
            self.assertIn(effect, option)
            self.assertIn("base = 0", option)
            self.assertIn(condition, option)
        self.assertIn("NOT = { ADISCORD_west_leans_to_ivn_ally = yes }", options[2])
        triggers = TRIGGERS.read_text(encoding="utf-8")
        self.assertIn("value = 50 compare = greater_than_or_equals", body(TRIGGERS, "ADISCORD_west_leans_to_wrk_ally"))
        self.assertIn("value = -50 compare = less_than_or_equals", body(TRIGGERS, "ADISCORD_west_leans_to_ivn_ally"))
        self.assertIn("value = 20 compare = greater_than_or_equals", body(TRIGGERS, "ADISCORD_west_grants_wrk_transit"))
        self.assertIn("value = -20 compare = less_than_or_equals", body(TRIGGERS, "ADISCORD_west_grants_ivn_transit"))
        self.assertIn("ADISCORD_west_leans_to_root_ally", triggers)

    def test_neutral_states_stay_out_of_the_settlement_and_lose_transit_on_every_end(self):
        loser = body(EFFECTS, "ADISCORD_west_mark_loser")
        self.assertIn("has_variable = ADISCORD_west_side", loser)
        declare = body(EFFECTS, "ADISCORD_west_declare_neutrality")
        self.assertNotIn("ADISCORD_west_side", declare)
        self.assertIn("country_event = { id = ADISCORD_west.13 days = 1 }", declare)
        settle = body(EFFECTS, "ADISCORD_west_settle_neutrality")
        self.assertIn("limit = { has_variable = ADISCORD_west_side }", settle)
        self.assertIn("white_peace = PREV", settle)
        clear = body(EFFECTS, "ADISCORD_west_clear_participant")
        self.assertIn("clr_country_flag = ADISCORD_west_neutral", clear)
        self.assertIn("ADISCORD_west_revoke_transit = yes", clear)
        for terminal in ("ADISCORD_west_apply_settlement", "ADISCORD_west_final_resolve_without_hegemon"):
            self.assertIn("ADISCORD_west_clear_participants = yes", body(EFFECTS, terminal), terminal)
        transit = body(EFFECTS, "ADISCORD_west_refresh_transit")
        self.assertLess(transit.index("ADISCORD_west_revoke_transit = yes"), transit.index("give_military_access = WRK"))
        self.assertIn("ADISCORD_west_final_active = yes", transit)
        revoke = body(EFFECTS, "ADISCORD_west_revoke_transit")
        for tag in CHAMPIONS:
            self.assertIn(f"limit = {{ {tag} = {{ has_military_access_to = PREV }} }}", revoke)
        follow = body(EFFECTS, "ADISCORD_west_follow_root")
        self.assertIn("ROOT = { has_country_flag = ADISCORD_west_neutral }", follow)

    def test_influence_decisions_target_the_western_states_and_price_exactly(self):
        for name in self.INFLUENCE_DECISIONS:
            decision = self.decision(name)
            self.assertEqual(set(re.search(r"targets = \{ ([^}]*) \}", decision)[1].split()), set(REGIONAL), name)
        arms = self.decision("ADISCORD_west_ship_arms")
        self.assertIn("NOT = { has_equipment = { infantry_equipment < 1000 } }", arms)
        shipment = body(EFFECTS, "ADISCORD_west_ship_arms")
        self.assertIn("amount = -1000", shipment)
        self.assertIn("amount = 1000", shipment)
        call = self.decision("ADISCORD_west_call_to_arms")
        self.assertIn("has_country_flag = ADISCORD_west_neutral", call)
        self.assertIn("FROM = { ADISCORD_west_leans_to_root_ally = yes }", call)
        ultimatum = self.decision("ADISCORD_west_ivn_ultimatum")
        self.assertIn("is_neighbor_of = ROOT", ultimatum)
        self.assertIn("ADISCORD_west_crisis_add = yes", ultimatum)

    def test_category_lists_every_western_state(self):
        for language in ("russian", "english"):
            text = (ROOT / f"localisation/{language}/ADISCORD_west_final_war_l_{language}.yml").read_text(encoding="utf-8-sig")
            desc = re.search(r'^ ADISCORD_west_influence_category_desc:0 "([^"]*)"$', text, re.M)[1]
            self.assertEqual(set(re.findall(r"\[([A-Z]{3})\.ADISCORDWestLean\]", desc)), set(REGIONAL), language)


class ItoranCourseTests(unittest.TestCase):
    """The three Itoran courses exclude each other and each leads to the war."""

    COURSES = ("IVN_humanist_shield", "IVN_emergency_order", "IVN_revanche_of_the_marches")

    @classmethod
    def setUpClass(cls):
        cls.focuses = focus_blocks(IVN_TREE)

    def test_courses_exclude_each_other_and_rejoin_for_the_heritage(self):
        for course in self.COURSES:
            exclusive = {e.value for item in self.focuses[course] if item.key == "mutually_exclusive" for e in item.value}
            self.assertEqual(exclusive, set(self.COURSES) - {course}, course)
        heritage = {e.value for item in self.focuses["IVN_west_heritage"] if item.key == "prerequisite" for e in item.value}
        self.assertEqual(heritage, set(self.COURSES))
        spirit = body(EFFECTS, "ADISCORD_west_add_path_spirit")
        self.assertIn("ADISCORD_west_ivn_revanche_course = yes", spirit)
        self.assertIn("has_completed_focus = IVN_revanche_of_the_marches", body(TRIGGERS, "ADISCORD_west_ivn_revanche_course"))

    def test_programmes_are_gated_by_their_focus_and_refund_a_lost_site(self):
        decisions = (ROOT / "common/decisions/ADISCORD_IVN_decisions.txt").read_text(encoding="utf-8")
        workshops = decisions[decisions.index("\tIVN_march_workshops = {"):decisions.index("\tIVN_reserve_call_up = {")]
        self.assertIn("visible = { has_completed_focus = IVN_march_reconstruction }", workshops)
        self.assertIn(("unlock_decision_tooltip", "IVN_march_workshops"), [(e.key, e.value) for e in flatten(self.focuses["IVN_march_reconstruction"])])
        remove = workshops[workshops.index("remove_effect"):]
        self.assertIn("IVN_march_workshop_site_exists = yes", remove)
        self.assertIn("add_political_power = 50", remove.split("else = {")[1])
        self.assertIn("cost = 50", workshops)
        self.assertIn("value = 3 compare = less_than", workshops)
        reserve = decisions[decisions.index("\tIVN_reserve_call_up = {"):]
        self.assertIn("visible = { has_completed_focus = IVN_citizen_reserve }", reserve)
        hold = (ROOT / "common/decisions/ADISCORD_west_final_war_decisions.txt").read_text(encoding="utf-8")
        hold = hold[hold.index("\tADISCORD_west_ivn_hold_the_marches = {"):]
        self.assertIn("has_completed_focus = IVN_west_war_council", hold[:hold.index("\n\t}\n")])

    def available(self, name):
        return repr(next(e.value for e in self.focuses[name] if e.key == "available"))

    def test_the_expedition_decides_which_course_is_open(self):
        shield = self.available("IVN_humanist_shield")
        self.assertIn("ADISCORD_vorkerland_ivanland_intervention_failed", shield)
        self.assertIn("IVN_northern_question_settled", shield)
        emergency = self.available("IVN_emergency_order")
        self.assertIn("ADISCORD_vorkerland_ivanland_intervention_succeeded", emergency)
        self.assertIn("IVN_marches_revolt_resolved", emergency)
        self.assertIn("value='chauvinism'", emergency)
        revanche = self.available("IVN_revanche_of_the_marches")
        self.assertIn("key='has_government', value='chauvinism'", revanche)
        self.assertIn("IVN_marches_revolt_active", revanche)
        settled = body(ROOT / "common/scripted_triggers/ADISCORD_IVN_scripted_triggers.txt", "IVN_northern_question_settled")
        self.assertIn("NOT = { has_global_flag = ADISCORD_vorkerland_ivanland_intervention_active }", settled)
        self.assertIn("has_global_flag = ADISCORD_vorkerland_ivanland_intervention_resolved", settled)
        self.assertIn("has_global_flag = ADISCORD_vorkerland_collapse_finished", settled)


class MarchesRevoltTests(unittest.TestCase):
    """The chauvinist revolt that follows a failed northern expedition."""

    IVN_EFFECTS = ROOT / "common/scripted_effects/ADISCORD_IVN_scripted_effects.txt"
    IVN_EVENTS = ROOT / "events/ADISCORD_IVN_events.txt"

    def test_a_failed_expedition_schedules_the_revolt_and_a_busy_itora_delays_it(self):
        failure = body(ROOT / "common/scripted_effects/ADISCORD_vorkerland_effects.txt", "ADISCORD_vorkerland_ivanland_intervention_failure")
        self.assertIn("IVN = { country_event = { id = ADISCORD_ivn.1 days = 30 } }", failure)
        events = self.IVN_EVENTS.read_text(encoding="utf-8")
        dispatcher = events[events.index("\tid = ADISCORD_ivn.1\n"):events.index("\tid = ADISCORD_ivn.2\n")]
        self.assertIn("IVN_marches_revolt_ready = yes", dispatcher)
        self.assertIn("country_event = { id = ADISCORD_ivn.1 days = 14 }", dispatcher)
        ready = body(ROOT / "common/scripted_triggers/ADISCORD_IVN_scripted_triggers.txt", "IVN_marches_revolt_ready")
        for condition in ("has_war = no", "is_subject = no", "owns_state = 95", "NOT = { country_exists = IVC }"):
            self.assertIn(condition, ready)

    def test_the_legion_takes_the_frontier_army_and_declares_the_war(self):
        start = body(self.IVN_EFFECTS, "IVN_start_marches_revolt")
        history = (ROOT / "history/countries/IVC - Marches Legion.txt").read_text(encoding="utf-8")
        self.assertIn("recruit_character = IVN_Rostislav_Karn", history)
        self.assertNotIn("recruit_character", start)
        self.assertIn("character = IVN_Rostislav_Karn", start)
        self.assertLess(start.index("set_global_flag = IVN_marches_revolt_active"), start.index("declare_war_on"))
        self.assertIn("IVN_adopt_emergency_order = yes", start)
        self.assertIn("transfer_units_fraction = {", start)
        self.assertIn("target = IVN", start)
        states = body(self.IVN_EFFECTS, "IVN_marches_revolt_states")
        self.assertEqual(set(re.findall(r"\b(\d+) = \{ IVN_marches_revolt_take_state = yes \}", states)), {"92", "95", "96", "97"})
        self.assertIn("is_controlled_by = IVN", body(self.IVN_EFFECTS, "IVN_marches_revolt_take_state"))

    def test_both_outcomes_keep_the_itoran_tag(self):
        resolve = body(self.IVN_EFFECTS, "IVN_resolve_marches_revolt")
        self.assertIn("target = IVC", resolve)
        self.assertIn("clr_global_flag = IVN_marches_revolt_active", resolve)
        self.assertIn("set_global_flag = IVN_marches_revolt_resolved", resolve)
        handover = body(self.IVN_EFFECTS, "IVN_hand_power_to_legion")
        self.assertIn("change_tag_from = IVC", handover)
        self.assertIn("ruling_party = chauvinism", handover)
        self.assertIn("target_country = IVN", handover)
        text = PEACE.read_text(encoding="utf-8")
        section = text[text.index("# BEGIN itora_revolt:on_capitulation"):text.index("# END itora_revolt:on_capitulation")]
        self.assertEqual(section.count("set_global_flag = skip_default_capitulation"), 2)
        self.assertEqual(section.count("IVN_resolve_marches_revolt = yes"), 2)
        self.assertLess(section.index("IVN_hand_power_to_legion = yes"), section.rindex("IVN_resolve_marches_revolt = yes"))
        peace = text[text.index("# BEGIN itora_revolt:on_peace"):text.index("# END itora_revolt:on_peace")]
        self.assertIn("IVN_resolve_marches_revolt = yes", peace)

    def test_the_revolt_pauses_the_western_question(self):
        self.assertIn("NOT = { has_global_flag = IVN_marches_revolt_active }", body(TRIGGERS, "ADISCORD_west_final_can_start"))
        month = body(EFFECTS, "ADISCORD_west_crisis_month")
        self.assertEqual(month.count("NOT = { has_global_flag = IVN_marches_revolt_active }"), 2)

    def test_revolt_events_are_registered_and_localised(self):
        source = self.IVN_EVENTS.read_text(encoding="utf-8")
        defined = set(re.findall(r"\bid = (ADISCORD_ivn\.\d+)", source))
        registry = json.loads((ROOT / "tools/data/adiscord_event_ids.json").read_text(encoding="utf-8"))
        self.assertEqual(defined, {e["id"] for e in registry["events"] if e["namespace"] == "ADISCORD_ivn"})
        keys = set(re.findall(r"(?:title|desc|name) = (ADISCORD_ivn\.[\w.]+)", source))
        keys |= set(re.findall(r"custom_effect_tooltip = (\S+)", source))
        keys |= {"IVC", "IVC_DEF", "IVC_ADJ"}
        for language in ("russian", "english"):
            text = (ROOT / f"localisation/{language}/ADISCORD_IVN_l_{language}.yml").read_text(encoding="utf-8-sig")
            present = set(re.findall(r"(?m)^ ([\w.]+):", text))
            self.assertEqual(sorted(keys - present), [], language)
        for path in ("common/countries/IVC.txt", "gfx/flags/IVC.tga", "gfx/flags/IVN_chauvinism.tga"):
            self.assertTrue((ROOT / path).is_file(), path)
        self.assertIn('IVC = "countries/IVC.txt"', (ROOT / "common/country_tags/02_ADISCORD_ivn_tags.txt").read_text(encoding="utf-8"))


class SubjectIntegrationRemovalTests(unittest.TestCase):
    def test_subject_annexation_decisions_are_absent_mod_wide(self):
        annexing = set()
        for path in (ROOT / "common/decisions").glob("*.txt"):
            for category in parse_clausewitz(path.read_text(encoding="utf-8-sig")):
                if not isinstance(category.value, list):
                    continue
                for decision in category.value:
                    if not isinstance(decision.value, list):
                        continue
                    if any(e.key == "annex_country" for e in flatten(decision.value)):
                        annexing.add(decision.key)
        # The island treaty joins a sovereign country, not an existing subject.
        self.assertEqual(annexing, {"VAL_Island_Treaty"})

    def test_retired_integration_ids_have_no_runtime_or_focus_references(self):
        retired = re.compile(
            r"ADISCORD_(?:west|south)_(?:integrate_subject|can_integrate)"
            r"|STP_heg_annex_"
            r"|STP_heg_(?:nod|ypr|tff|val)_integrated"
        )
        for directory in ("common", "events", "focus_trees", "localisation"):
            for path in (ROOT / directory).rglob("*"):
                if path.suffix not in {".txt", ".yml"}:
                    continue
                self.assertIsNone(
                    retired.search(path.read_text(encoding="utf-8-sig")),
                    str(path.relative_to(ROOT)),
                )

    def test_native_autonomy_ladders_stop_before_annexation(self):
        for filename in (
            "integrated_puppet.txt",
            "district_in_Vorkerland.txt",
            "Feodal_Baronage.txt",
            "supervised_state.txt",
            "lar_collaboration_government.txt",
        ):
            with self.subTest(filename=filename):
                path = ROOT / "common/autonomous_states" / filename
                autonomy = block(parse_clausewitz(path.read_text(encoding="utf-8")), "autonomy_state")
                gate = block(autonomy, "can_lose_level")
                self.assertEqual([(e.key, e.value) for e in gate], [("always", "no")])

    def test_southern_heritage_keeps_its_rewards_without_an_annexation_unlock(self):
        for country, identifier in (
            ("NAM", "NAM_south_heritage"),
            ("SHL", "SHL_south_crown_of_the_south"),
        ):
            with self.subTest(country=country):
                path = ROOT / f"focus_trees/{country}/main/focuses.txt"
                reward = block(focus_blocks(path)[identifier], "completion_reward")
                self.assertTrue(reward)
                self.assertNotIn("unlock_decision_tooltip", repr(reward))


class ItoranAggregateTests(unittest.TestCase):
    """The Itoran order aggregate shows exactly the variable change a focus applies."""

    def setUp(self):
        dynamic = parse_clausewitz((ROOT / "common/dynamic_modifiers/ADISCORD_dynamic_modifiers_IVN.txt").read_text(encoding="utf-8"))
        modifier = next(e.value for e in dynamic if e.key == "IVN_order_dynamic")
        self.fields = {e.value: e.key for e in modifier if e.key not in ("icon", "enable")}
        root = next(e.value for e in parse_clausewitz((ROOT / "common/ideas/ADISCORD_IVN_ideas.txt").read_text(encoding="utf-8")) if e.key == "ideas")
        self.display = {}
        for group in root:
            for idea in group.value:
                allowed = next(e.value for e in idea.value if e.key == "allowed")
                self.assertEqual([(e.key, e.value) for e in allowed], [("always", "no")], idea.key)
                modifier = next(e.value for e in idea.value if e.key == "modifier")
                self.display[idea.key] = {e.key: float(e.value) for e in modifier}

    def test_every_display_delta_matches_the_applied_change(self):
        checked = 0
        for identifier, focus in focus_blocks(IVN_TREE).items():
            reward = next(e.value for e in focus if e.key == "completion_reward")
            swaps = [e.value for e in flatten(reward) if e.key == "swap_ideas"]
            if not swaps:
                continue
            swap = {e.key: e.value for e in swaps[0]}
            self.assertEqual(self.display[swap["remove_idea"]], {}, identifier)
            hidden = [e.value for e in reward if e.key == "hidden_effect"][-1]
            applied = {}
            for entry in hidden:
                if entry.key == "add_to_variable":
                    values = {e.key: e.value for e in entry.value}
                    applied[self.fields[values["var"]]] = float(values["value"])
            self.assertEqual(applied, self.display[swap["add_idea"]], identifier)
            self.assertIn(("IVN_refresh_order", "yes"), [(e.key, e.value) for e in hidden], identifier)
            checked += 1
        self.assertEqual(checked, 27)

    def test_display_ideas_are_never_installed(self):
        text = IVN_TREE.read_text(encoding="utf-8")
        for name in self.display:
            self.assertNotIn(f"add_ideas = {name}", text)

    def test_refresh_attaches_and_updates_without_reset(self):
        source = body(ROOT / "common/scripted_effects/ADISCORD_IVN_scripted_effects.txt", "IVN_refresh_order")
        self.assertIn("add_dynamic_modifier = { modifier = IVN_order_dynamic }", source)
        self.assertIn("force_update_dynamic_modifier = yes", source)
        self.assertIn("ADISCORD_economy_mark_dirty = yes", source)
        self.assertNotIn("set_variable", source)


class WestReconstructionScenarios(unittest.TestCase):
    """Parsed boundary and reward scenarios; this does not emulate the engine."""

    @classmethod
    def setUpClass(cls):
        from tools.validators.validate_adiscord_vorkerland_civil_war_focus import (
            RECONSTRUCTION_ROUTE_FOCUSES,
            WEST_ROUTE_FOCUSES,
        )

        cls.routes = RECONSTRUCTION_ROUTE_FOCUSES
        cls.west = WEST_ROUTE_FOCUSES
        cls.focuses = focus_blocks(WRK_TREE)
        cls.triggers = {
            entry.key: entry.value
            for entry in parse_clausewitz(TRIGGERS.read_text(encoding="utf-8"))
        }

    def expand(self, entries):
        expanded = []
        for entry in entries:
            if entry.key in self.triggers:
                self.assertIn(entry.value, ("yes", "no"))
                expanded.append(replace(
                    entry,
                    key="AND" if entry.value == "yes" else "NOT",
                    value=self.expand(self.triggers[entry.key]),
                ))
            elif isinstance(entry.value, list):
                expanded.append(replace(entry, value=self.expand(entry.value)))
            else:
                expanded.append(entry)
        return expanded

    def crisis_facts(self, age, pressure=100):
        facts = {}
        for tag in CHAMPIONS:
            for key, value in (
                ("exists", "yes"), ("is_subject", "no"), ("has_capitulated", "no"),
                ("has_war", "no"),
                ("has_country_flag", "ADISCORD_vorkerland_central_unifier"),
                ("has_global_flag", "ADISCORD_fresh_campaign_contract_v1"),
                ("has_global_flag", "ADISCORD_vorkerland_collapse_finished"),
                ("has_global_flag", "ADISCORD_vorkerland_phase_postwar_integration"),
            ):
                facts[(tag, key, value)] = True
            facts[(tag, "flag_days", "ADISCORD_vorkerland_collapse_finished")] = age
            facts[(tag, "variable", "global.ADISCORD_west_crisis")] = pressure
        return facts

    def test_day_179_blocks_every_declarer_and_day_180_opens_the_gate(self):
        entry_guard = block(parse_clausewitz(body(EFFECTS, "ADISCORD_west_final_war_start")), "if")
        guard = self.expand(block(entry_guard, "limit"))
        for tag in CHAMPIONS:
            for age, expected in ((0, False), (179, False), (180, True), (181, True)):
                with self.subTest(tag=tag, age=age):
                    self.assertEqual(matches_conditions(guard, self.crisis_facts(age), tag), expected)
            missing_flag = self.crisis_facts(900)
            missing_flag[(tag, "has_global_flag", "ADISCORD_vorkerland_collapse_finished")] = False
            self.assertFalse(matches_conditions(guard, missing_flag, tag))

    def test_monthly_pressure_waits_even_at_the_war_threshold(self):
        month = self.expand(parse_clausewitz(body(EFFECTS, "ADISCORD_west_crisis_month")))
        for age, expected in ((179, []), (180, [5])):
            effects = list(selected_effects(month, self.crisis_facts(age), "WRK"))
            increments = [
                int(scalar(entry.value, "value")) for _, entry in effects
                if entry.key == "add_to_variable"
            ]
            self.assertEqual(increments, expected)
            self.assertEqual(
                any(entry.key == "ADISCORD_west_final_war_start" for _, entry in effects),
                age >= 180,
            )
        facts = self.crisis_facts(180, pressure=50)
        effects = list(selected_effects(month, facts, "WRK"))
        self.assertFalse(any(entry.key == "ADISCORD_west_final_war_start" for _, entry in effects))

    def test_war_presentation_follows_either_declarer_and_requires_new_campaign_start(self):
        start = self.expand(parse_clausewitz(body(EFFECTS, "ADISCORD_west_final_war_start")))
        presentation = "ADISCORD_vorkerland_show_itora_war_superevent"
        for declarer in CHAMPIONS:
            with self.subTest(declarer=declarer):
                facts = self.crisis_facts(180)
                facts[(declarer, "tag", declarer)] = True
                selected = list(selected_effects(start, facts, declarer))
                war = [(scope, row) for scope, row in selected if row.key == "declare_war_on"]
                shown = [(scope, row) for scope, row in selected if row.key == presentation]
                self.assertEqual(len(war), 1)
                self.assertEqual(scalar(war[0][1].value, "target"), "IVN" if declarer == "WRK" else "WRK")
                self.assertEqual([scope for scope, _ in shown], ["WRK"])
                self.assertLess(selected.index(war[0]), selected.index(shown[0]))
                for flag in ("ADISCORD_west_final_started", "ADISCORD_west_final_resolved"):
                    blocked = {**facts, (declarer, "has_global_flag", flag): True}
                    self.assertFalse(any(row.key == presentation for _, row in selected_effects(start, blocked, declarer)))
                self.assertFalse(any(row.key == presentation for _, row in selected_effects(start, self.crisis_facts(179), declarer)))

    def test_existing_intervention_and_terminal_guards_survive_the_pause(self):
        guard = self.expand(self.triggers["ADISCORD_west_final_can_start"])
        for blocker in (
            "ADISCORD_vorkerland_ivanland_intervention_active",
            "ADISCORD_west_final_started", "ADISCORD_west_final_resolved",
        ):
            facts = self.crisis_facts(900)
            facts[("WRK", "has_global_flag", blocker)] = True
            self.assertFalse(matches_conditions(guard, facts, "WRK"), blocker)
        for tag in CHAMPIONS:
            facts = self.crisis_facts(900)
            facts[(tag, "is_subject", "no")] = False
            self.assertFalse(matches_conditions(guard, facts, "WRK"), tag)

    def test_every_final_focus_shows_and_enforces_the_pause(self):
        count = 0
        for path, tag in ((WRK_TREE, "WRK"), (WORKER_TREE, "WRK"), (TECHNICAL_TREE, "WRK"), (EMPIRE_TREE, "WRK"), (IVN_TREE, "IVN")):
            for name, focus in focus_blocks(path).items():
                if "ADISCORD_west_final_war_start" not in repr(focus):
                    continue
                count += 1
                available = block(focus, "available")
                self.assertIn(f"{tag}_west_reconstruction_ready_tt", repr(available))
                # Only the joint route gates its war on a programme focus; the
                # other trees reach their final through prerequisites.
                drilled = name.startswith("WRK_joint_")
                for age, expected in ((179, False), (180, True)):
                    facts = self.crisis_facts(age)
                    if drilled:
                        facts[("WRK", "has_completed_focus", "WRK_joint_pw_field_exercises")] = True
                    self.assertEqual(
                        matches_conditions(self.expand(available), facts, tag),
                        expected, (name, age),
                    )
                    if drilled:
                        facts[("WRK", "has_completed_focus", "WRK_joint_pw_field_exercises")] = False
                        self.assertFalse(matches_conditions(self.expand(available), facts, tag))
        self.assertEqual(count, 7)

    def route_paths(self, names, completed):
        if names[-1] in completed:
            yield tuple(name for name in names if name in completed)
            return
        for name in names:
            if name in completed:
                continue
            focus = self.focuses[name]
            prerequisites = [entry.value for entry in focus if entry.key == "prerequisite"]
            if not all(any(entry.value in completed for entry in group) for group in prerequisites):
                continue
            exclusions = [entry.value for entry in focus if entry.key == "mutually_exclusive"]
            if any(entry.value in completed for group in exclusions for entry in group):
                continue
            yield from self.route_paths(names, completed | {name})

    def test_each_route_adds_two_reachable_140_day_paths_before_the_west(self):
        for route, names in self.routes.items():
            self.assertEqual(len(names), 6)
            tower = "WRK_" + route.removeprefix("ADISCORD_vorkerland_route_") + "_restore_unity_tower"
            self.assertEqual(list(self.route_paths(names, set())), [])
            paths = list(self.route_paths(names, {tower}))
            self.assertEqual(len(paths), 2)
            self.assertEqual(set().union(*(set(path) for path in paths)), set(names))
            for path in paths:
                self.assertEqual(len(path), 5)
                self.assertEqual(sum(int(scalar(self.focuses[name], "cost")) * 7 for name in path), 140)
            west_entry = self.focuses[self.west[route][0]]
            self.assertEqual(scalar(block(west_entry, "prerequisite"), "focus"), names[-1])

    def rewards(self, path):
        facts = {}
        totals = Counter()
        for name in path:
            reward = block(self.focuses[name], "completion_reward")
            for scope, entry in selected_effects(reward, facts, "WRK"):
                self.assertEqual(scope, "WRK")
                if entry.key in ("add_political_power", "add_stability", "army_experience"):
                    totals[entry.key] += float(entry.value)
                elif entry.key == "add_equipment_to_stockpile":
                    self.assertEqual(scalar(entry.value, "producer"), "WRK")
                    totals[scalar(entry.value, "type")] += int(scalar(entry.value, "amount"))
                elif entry.key == "random_owned_controlled_state":
                    build = block(entry.value, "add_building_construction")
                    self.assertEqual(scalar(build, "instant_build"), "yes")
                    totals[scalar(build, "type")] += int(scalar(build, "level"))
                elif entry.key == "add_tech_bonus":
                    self.assertEqual(scalar(entry.value, "category"), "industry")
                    self.assertEqual(scalar(entry.value, "bonus"), "0.5")
                    totals["industry_bonus_50"] += int(scalar(entry.value, "uses"))
                else:
                    self.assertEqual((entry.key, entry.value), ("ADISCORD_economy_mark_dirty", "yes"))
            facts[("WRK", "has_completed_focus", name)] = True
        return totals

    def test_both_choices_pay_the_exact_agreed_totals_without_double_awards(self):
        expected = {
            "joint": Counter(industrial_complex=1, army_experience=20, infantry_equipment=1000),
        }
        for route, names in self.routes.items():
            short = route.removeprefix("ADISCORD_vorkerland_route_")
            paths = list(self.route_paths(names, {f"WRK_{short}_restore_unity_tower"}))
            for path in paths:
                self.assertEqual(self.rewards(path), expected[short], path)
            # The choice changes when resources arrive, even though the final budget is equal.
            self.assertNotEqual(self.rewards(paths[0][:-1]), self.rewards(paths[1][:-1]))

    def test_factories_recheck_control_cores_and_slots_at_delivery(self):
        for names in self.routes.values():
            for name in names:
                focus = self.focuses[name]
                for entry in flatten(block(focus, "completion_reward")):
                    if entry.key != "random_owned_controlled_state":
                        continue
                    condition = block(entry.value, "limit")
                    self.assertEqual(scalar(condition, "is_core_of"), "ROOT")
                    slots = block(condition, "free_building_slots")
                    self.assertEqual(scalar(slots, "building"), "industrial_complex")
                    self.assertEqual(scalar(slots, "include_locked"), "no")
                    self.assertEqual([item.value for item in slots if not item.key], ["size", ">", "0"])
                    available = block(focus, "available")
                    self.assertIn("WRK_reconstruction_factory_site_tt", repr(available))
                    self.assertIn("is_controlled_by", repr(available))

    def test_reconstruction_is_route_scoped_and_ai_can_finish_either_choice(self):
        plans = (ROOT / "common/ai_strategy_plans/ADISCORD_vorkerland_plans.txt").read_text(encoding="utf-8")
        for route, names in self.routes.items():
            short = route.removeprefix("ADISCORD_vorkerland_route_")
            plan = body(ROOT / "common/ai_strategy_plans/ADISCORD_vorkerland_plans.txt", f"ADISCORD_vorkerland_wrk_postwar_{short}_plan")
            self.assertIn(route, plan)
            for name in names:
                focus = self.focuses[name]
                allow = block(focus, "allow_branch")
                self.assertEqual(scalar(allow, "tag"), "WRK")
                self.assertEqual(scalar(allow, "has_country_flag"), route)
                self.assertEqual(scalar(allow, "has_global_flag"), "ADISCORD_vorkerland_phase_postwar_integration")
                self.assertIn(name, plan)
                self.assertEqual(plans.count("\n\t\t" + name + "\n"), 1)


if __name__ == "__main__":
    unittest.main()
