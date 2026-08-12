from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

from PIL import Image

from tools.validators.validate_adiscord_vorkerland_collapse import (
    CENTRAL_MINOR_TARGETS,
    SECTIONS,
    named_block,
    validate,
)
from tools.lib.vorkerland_collapse_manifest import CAPITALS, TAGS


ROOT = Path(__file__).resolve().parents[2]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8-sig")


def event_block(text: str, event_id: str, event_type: str = "country_event") -> str:
    for match in re.finditer(
        rf"(?m)^{re.escape(event_type)}\s*=\s*\{{",
        text,
    ):
        start = match.start()
        depth = 0
        for index in range(match.end() - 1, len(text)):
            if text[index] == "{":
                depth += 1
            elif text[index] == "}":
                depth -= 1
                if depth == 0:
                    block = text[start : index + 1]
                    header = re.match(
                        rf"(?ms)^{re.escape(event_type)}\s*=\s*\{{[^\r\n]*\r?\n\s*"
                        r"id\s*=\s*([^\s}]+)",
                        block,
                    )
                    if header and header.group(1) == event_id:
                        return block
                    break
    raise AssertionError(f"missing event: {event_id}")


class VorkerlandCollapseValidatorTests(unittest.TestCase):
    def test_event_helper_uses_the_declared_id_not_a_nested_scheduled_id(self) -> None:
        source = """
country_event = {
    id = ADISCORD_vorkerland_collapse.47
    immediate = {
        marker_47 = yes
        country_event = { id = ADISCORD_vorkerland_collapse.67 days = 1 }
    }
}
country_event = {
    id = ADISCORD_vorkerland_collapse.67
    immediate = { marker_67 = yes }
}
"""
        retry = event_block(source, "ADISCORD_vorkerland_collapse.67")
        self.assertIn("marker_67 = yes", retry)
        self.assertNotIn("marker_47 = yes", retry)

    def test_every_validator_section_passes(self) -> None:
        for section in SECTIONS:
            with self.subTest(section=section):
                self.assertEqual(validate(ROOT, section), [])

    def test_manifest_covers_new_political_map(self) -> None:
        self.assertEqual(len(TAGS), 28)
        self.assertEqual(len(set(TAGS)), 28)
        self.assertEqual(set(TAGS), set(CAPITALS))
        self.assertTrue({"RIV", "REV", "YOR", "NDN", "SWB", "VHV", "OSV", "TGD", "IBA", "IBL", "CSL"} <= set(TAGS))

    def test_every_vorkerland_superevent_route_plays_audible_sound(self) -> None:
        map_effects = read("common/scripted_effects/ADISCORD_vorkerland_collapse_map_effects.txt")
        for name in ("dirty_opening", "worker_victory", "vlad_victory", "dorian_victory"):
            show_effect = named_block(map_effects, f"ADISCORD_vorkerland_show_{name}_superevent")
            self.assertIn(
                "ADISCORD_vorkerland_play_local_superevent_audio = yes",
                show_effect,
                name,
            )

        news = read("events/ADISCORD_news.txt")
        for news_id, title_id, audio_id, sound_effect in (
            (
                "ADISCORD_superevent_news.1",
                "news.0",
                "ADISCORD_superevent_audio.1",
                "superevent_vorkerland_civilwar_sound_e",
            ),
            (
                "ADISCORD_superevent_news.2",
                "news.1",
                "ADISCORD_superevent_audio.2",
                "superevent_stelander_empire_sound_e",
            ),
        ):
            definition = event_block(news, news_id, "news_event")
            self.assertIn(f"title = {title_id}.t", definition)
            self.assertIn(f"desc = {title_id}.d", definition)
            self.assertIn("major = yes", definition)
            self.assertIn("is_triggered_only = yes", definition)
            self.assertNotIn("hidden = yes", definition)
            self.assertIn(f"country_event = {{ id = {audio_id} }}", definition)
            audio_proxy = event_block(news, audio_id)
            self.assertIn("limit = { is_ai = no }", audio_proxy)
            self.assertIn(f"scoped_sound_effect = {sound_effect}", audio_proxy)

        sound_effects = read("sound/superevents_effects.asset")
        self.assertEqual(sound_effects.count("volume = 1.0"), 2)
        for effect_name in (
            "superevent_vorkerland_civilwar_sound_e",
            "superevent_stelander_empire_sound_e",
        ):
            self.assertIn(f"name = {effect_name}", sound_effects)

    def test_wrk_border_countries_keep_plain_geographic_names(self) -> None:
        loc = read("localisation/russian/ADISCORD_vorkerland_collapse_l_russian.yml")
        self.assertIn('NDN: "Норден"', loc)
        self.assertIn('SWB: "Старый Воркенсберг"', loc)
        self.assertIn('VHV: "Верховье"', loc)
        self.assertIn('OSV: "Оствин"', loc)
        for verbose in (
            "Норденская чрезвычайная администрация",
            "Временная директория Старого Воркенсберга",
            "Северная чрезвычайная администрация",
            "Оствинский переходный совет",
        ):
            self.assertNotIn(verbose, loc)


class BorderWarArchitectureTests(unittest.TestCase):
    def test_day_one_event_declares_no_wars(self) -> None:
        events = read("events/ADISCORD_vorkerland_collapse_events.txt")
        match = re.search(
            r"(?ms)^country_event\s*=\s*\{\s*id\s*=\s*ADISCORD_vorkerland_collapse\.2\b(.*?)(?=^country_event|\Z)",
            events,
        )
        self.assertIsNotNone(match)
        self.assertNotIn("declare_war_on", match.group(1))
        self.assertIn("ADISCORD_vorkerland_teardown_confederation = yes", match.group(1))
        self.assertIn("ADISCORD_vorkerland_collapse.31", match.group(1))
        self.assertIn("days = 21", match.group(1))
        self.assertRegex(match.group(1), r"WKR\s*=\s*\{[^{}]*country_event\s*=\s*\{")

    def test_mobilisation_pause_unlocks_ai_regional_decision(self) -> None:
        events = read("events/ADISCORD_vorkerland_collapse_events.txt")
        authorization = re.search(
            r"(?ms)^country_event\s*=\s*\{\s*id\s*=\s*ADISCORD_vorkerland_collapse\.31\b"
            r"(.*?)(?=^country_event\s*=\s*\{|\Z)",
            events,
        )
        self.assertIsNotNone(authorization)
        self.assertIn("tag = WKR", authorization.group(1))
        self.assertEqual(
            authorization.group(1).count(
                "set_global_flag = ADISCORD_vorkerland_claim_wars_authorized"
            ),
            1,
        )
        self.assertNotIn("declare_war_on", authorization.group(1))
        self.assertIn(
            "ADISCORD_vorkerland_teardown_confederation = yes",
            authorization.group(1),
        )
        for event_id in (32, 33, 34, 35):
            self.assertNotIn(f"ADISCORD_vorkerland_collapse.{event_id}", events)

        decisions = read("common/decisions/ADISCORD_vorkerland_collapse_decisions.txt")
        self.assertNotIn(
            "ADISCORD_vorkerland_consolidate_central_border", decisions
        )
        regional = named_block(decisions, "ADISCORD_vorkerland_open_regional_fronts")
        self.assertNotIn("declare_war_on", named_block(regional, "complete_effect"))
        self.assertIn("ADISCORD_vorkerland_collapse.63 days = 1", regional)
        self.assertNotIn("add_to_war", regional)
        self.assertIn("ai_will_do", regional)

    def test_border_wars_use_decisions_without_recurring_seed_watchdogs(self) -> None:
        events = read("events/ADISCORD_vorkerland_collapse_events.txt")
        on_actions = read("common/on_actions/01_ADISCORD_vorkerland_collapse_on_actions.txt")
        decisions = read("common/decisions/ADISCORD_vorkerland_collapse_decisions.txt")
        focus_decisions = read("common/decisions/ADISCORD_vorkerland_focus_decisions.txt")

        for event_id in (32, 33, 34, 35):
            self.assertNotIn(
                f"id = ADISCORD_vorkerland_collapse.{event_id}", events
            )
        self.assertNotIn("ADISCORD_vorkerland_seed_watchdog_scheduled", events)
        self.assertNotIn("ADISCORD_vorkerland_seed_watchdog_scheduled", on_actions)
        self.assertIn(
            "declare_war_on",
            named_block(decisions, "ADISCORD_vorkerland_continue_reunification"),
        )
        for target in CENTRAL_MINOR_TARGETS:
            decision_id = f"ADISCORD_vorkerland_consolidate_{target.lower()}"
            self.assertIn(
                f"ADISCORD_vorkerland_focus_launch_minor_{target.lower()} = yes",
                named_block(focus_decisions, decision_id),
                decision_id,
            )
        regional = named_block(decisions, "ADISCORD_vorkerland_open_regional_fronts")
        self.assertNotIn("declare_war_on", named_block(regional, "complete_effect"))
        self.assertIn("ADISCORD_vorkerland_collapse.63 days = 1", regional)

    def test_central_minor_wars_are_early_one_front_decisions(self) -> None:
        triggers = read("common/scripted_triggers/ADISCORD_vorkerland_collapse_triggers.txt")
        collapse_decisions = read(
            "common/decisions/ADISCORD_vorkerland_collapse_decisions.txt"
        )
        focus_decisions = read("common/decisions/ADISCORD_vorkerland_focus_decisions.txt")

        rival = named_block(
            triggers, "ADISCORD_vorkerland_is_main_claimant_rival_for_ROOT"
        )
        main_claimant = named_block(triggers, "ADISCORD_vorkerland_is_main_claimant")
        self.assertEqual(
            set(re.findall(r"tag\s*=\s*([A-Z]{3})", main_claimant)),
            {"WKR", "VAD", "TVA"},
        )
        self.assertGreaterEqual(
            rival.count("ADISCORD_vorkerland_is_main_claimant = yes"), 2
        )
        self.assertNotIn("has_war = no", rival)
        self.assertNotIn(
            "ADISCORD_vorkerland_consolidate_central_border", collapse_decisions
        )
        self.assertNotIn(
            "ADISCORD_vorkerland_is_central_target_for_ROOT = yes",
            collapse_decisions,
        )
        actual = set(
            re.findall(
                r"(?m)^\s*(ADISCORD_vorkerland_consolidate_[a-z0-9_]+)\s*=\s*\{",
                focus_decisions,
            )
        )
        expected = {
            f"ADISCORD_vorkerland_consolidate_{target.lower()}"
            for target in CENTRAL_MINOR_TARGETS
        }
        self.assertEqual(actual, expected)
        self.assertEqual(len(expected), 9)
        for target in CENTRAL_MINOR_TARGETS:
            suffix = target.lower()
            decision_id = f"ADISCORD_vorkerland_consolidate_{suffix}"
            decision = named_block(focus_decisions, decision_id)
            visible = named_block(decision, "visible")
            complete = named_block(decision, "complete_effect")
            remove = named_block(decision, "remove_effect")
            for claimant in ("wkr", "vad", "tva"):
                self.assertNotIn(
                    f"ADISCORD_vorkerland_focus_{claimant}_central_war_unlocked",
                    visible,
                    decision_id,
                )
            self.assertNotIn(
                "ADISCORD_vorkerland_focus_central_front_prepared",
                visible,
            )
            self.assertIn(
                "ADISCORD_vorkerland_central_minor_campaign_phase_available = yes",
                visible,
            )
            self.assertIn(f"any_neighbor_country = {{ tag = {target} }}", visible)
            self.assertIn(
                f"set_country_flag = ADISCORD_vorkerland_focus_central_minor_target_{suffix}",
                complete,
            )
            self.assertIn(
                f"ADISCORD_vorkerland_focus_launch_minor_{suffix} = yes", remove
            )
            self.assertNotIn("declare_war_on", decision)
            self.assertEqual(
                decision.count(
                    "set_country_flag = ADISCORD_vorkerland_focus_central_minor_target_"
                ),
                1,
            )
            self.assertEqual(
                decision.count("ADISCORD_vorkerland_focus_launch_minor_"), 1
            )

    def test_worker_doctor_showdown_uses_phase_queue_and_sovereign_wtd_join(self) -> None:
        triggers = read("common/scripted_triggers/ADISCORD_vorkerland_collapse_triggers.txt")
        decisions = read("common/decisions/ADISCORD_vorkerland_collapse_decisions.txt")
        ai = read("common/ai_strategy/ADISCORD_vorkerland_collapse_ai.txt")
        effects = read("common/scripted_effects/ADISCORD_vorkerland_collapse_effects.txt")
        events = read("events/ADISCORD_vorkerland_collapse_events.txt")
        on_actions = read("common/on_actions/01_ADISCORD_vorkerland_collapse_on_actions.txt")

        rival = named_block(
            triggers, "ADISCORD_vorkerland_is_main_claimant_rival_for_ROOT"
        )
        for token in (
            "AND = { tag = TVA ROOT = { tag = WKR } }",
            "AND = { tag = WKR ROOT = { tag = TVA } }",
        ):
            self.assertIn(token, rival)

        self.assertFalse(named_block(decisions, "ADISCORD_vorkerland_prepare_worker_doctor_showdown"))
        self.assertFalse(named_block(effects, "ADISCORD_vorkerland_detach_worker_doctor_factions"))
        self.assertFalse(named_block(effects, "ADISCORD_vorkerland_launch_worker_doctor_war"))
        for event_id in (48, 49):
            self.assertNotRegex(
                events,
                rf"(?m)^\s*id\s*=\s*ADISCORD_vorkerland_collapse\.{event_id}\b",
            )

        phase_events = read("events/ADISCORD_vorkerland_phase_events.txt")
        phase_four = event_block(phase_events, "ADISCORD_vorkerland_phase.4")
        phase_five = event_block(phase_events, "ADISCORD_vorkerland_phase.5")
        self.assertIn("ADISCORD_vorkerland_initialize_showdown_edge_queue = yes", phase_four)
        self.assertIn("ADISCORD_vorkerland_advance_showdown_launch = yes", phase_five)

        phase_effects = read("common/scripted_effects/ADISCORD_vorkerland_phase_effects.txt")
        queue = named_block(phase_effects, "ADISCORD_vorkerland_initialize_showdown_edge_queue")
        self.assertIn("ADISCORD_vorkerland_detach_showdown_claimants = yes", queue)
        self.assertIn(
            "set_global_flag = ADISCORD_vorkerland_showdown_edge_wkr_tva_required", queue
        )
        attempt = named_block(phase_effects, "ADISCORD_vorkerland_attempt_showdown_edge_wkr_tva")
        self.assertIn("WKR = { declare_war_on = { target = TVA type = annex_everything } }", attempt)
        verify = named_block(phase_effects, "ADISCORD_vorkerland_verify_showdown_edge_wkr_tva")
        self.assertIn("WKR = { has_war_with = TVA }", verify)
        self.assertIn("ADISCORD_vorkerland_schedule_wtd_tva_temporary_alliance_check = yes", verify)

        join = event_block(events, "ADISCORD_vorkerland_collapse.47")
        for token in (
            "tag = WTD",
            "is_subject = no",
            "TVA = { exists = yes has_war_with = WKR }",
            "NOT = { has_war_with = WKR }",
            "targeted_alliance = TVA",
            "enemy = WKR",
            "country_event = { id = ADISCORD_vorkerland_collapse.67 days = 1 }",
        ):
            self.assertIn(token, join)
        retry = event_block(events, "ADISCORD_vorkerland_collapse.67")
        self.assertIn("limit = { has_war_with = WKR }", retry)
        self.assertIn("set_country_flag = ADISCORD_vorkerland_wtd_fighting_for_worx", retry)
        self.assertIn("set_country_flag = ADISCORD_vorkerland_wtd_join_failed", retry)
        self.assertEqual(
            retry.count("country_event = { id = ADISCORD_vorkerland_collapse.67 days = 1 }"),
            1,
        )
        monthly = named_block(on_actions, "on_monthly")
        for forbidden in (
            "ADISCORD_vorkerland_schedule_wtd_tva_temporary_alliance_check",
            "ADISCORD_vorkerland_collapse.47",
            "ADISCORD_vorkerland_collapse.67",
        ):
            self.assertNotIn(forbidden, monthly)
        self.assertNotIn("ADISCORD_vorkerland_worker_doctor_front_preparation", ai)

    def test_peripheral_decision_opens_northern_three_sided_campaign(self) -> None:
        decisions = read("common/decisions/ADISCORD_vorkerland_collapse_decisions.txt")
        effects = read("common/scripted_effects/ADISCORD_vorkerland_collapse_effects.txt")
        events = read("events/ADISCORD_vorkerland_collapse_events.txt")
        on_actions = read("common/on_actions/01_ADISCORD_vorkerland_collapse_on_actions.txt")
        regional = named_block(decisions, "ADISCORD_vorkerland_open_regional_fronts")
        self.assertEqual(
            set(re.findall(r"tag\s*=\s*([A-Z]{3})", named_block(regional, "allowed"))),
            {"ZAO", "VLA", "ROM", "SOL", "TRU"},
        )
        complete = named_block(regional, "complete_effect")
        self.assertIn("ADISCORD_vorkerland_detach_regional_war_factions = yes", complete)
        self.assertIn("ADISCORD_vorkerland_collapse.63 days = 1", complete)
        self.assertNotIn("declare_war_on", complete)
        self.assertNotIn("add_to_war", complete)
        repair = named_block(effects, "ADISCORD_vorkerland_repair_regional_wars")
        for attacker, defender in (("ZAO", "WPA"), ("ZAO", "PSD"), ("VLA", "EBA"), ("SOL", "SRA")):
            self.assertIn(f"target = {defender}", repair, attacker)
        for attacker, defender in (
            ("WPS", "ZAO"), ("PWR", "ZAO"),
            ("WPA", "PSD"), ("WPA", "PWR"),
            ("WPS", "PSD"), ("WPS", "PWR"), ("PWR", "PSD"),
            ("TGD", "EBA"),
        ):
            self.assertRegex(
                repair,
                rf"{attacker}\s*=\s*\{{\s*declare_war_on\s*=\s*\{{\s*target\s*=\s*{defender}",
            )
        self.assertRegex(repair, r"SRA\s*=\s*\{\s*declare_war_on\s*=\s*\{\s*target\s*=\s*CSL")
        self.assertEqual(repair.count("declare_war_on ="), 17)
        self.assertEqual(repair.count("is_subject = no"), 34)
        self.assertEqual(repair.count("has_capitulated = yes"), 34)
        self.assertNotIn("add_to_war", repair)
        self.assertIn("target = TGD", repair)
        self.assertIn("target = CSL", repair)
        self.assertIn("factor = 1000", regional)
        launch = named_block(effects, "ADISCORD_vorkerland_open_regional_fronts_after_detach")
        self.assertIn("ADISCORD_vorkerland_repair_regional_wars = yes", launch)
        self.assertIn("ADISCORD_vorkerland_collapse.64 days = 1", launch)
        launch_success_tokens = (
            "set_global_flag = ADISCORD_vorkerland_northern_wars_began",
            "set_global_flag = ADISCORD_vorkerland_ivanland_planning_unlocked_v4",
            "clr_global_flag = ADISCORD_vorkerland_regional_war_launch_scheduled",
        )
        for token in launch_success_tokens:
            self.assertNotIn(token, launch)

        phase_effects = read("common/scripted_effects/ADISCORD_vorkerland_phase_effects.txt")
        verifier = named_block(
            phase_effects, "ADISCORD_vorkerland_verify_regional_war_launch"
        )
        self.assertIn("ADISCORD_vorkerland_repair_regional_wars = yes", verifier)
        self.assertIn("ADISCORD_vorkerland_regional_war_graph_active_or_terminal = yes", verifier)
        for token in launch_success_tokens:
            self.assertIn(token, verifier)

        launch_event = event_block(events, "ADISCORD_vorkerland_collapse.63")
        verify_event = event_block(events, "ADISCORD_vorkerland_collapse.64")
        self.assertIn("ADISCORD_vorkerland_open_regional_fronts_after_detach = yes", launch_event)
        self.assertIn("ADISCORD_vorkerland_verify_regional_war_launch = yes", verify_event)
        self.assertNotIn("ADISCORD_vorkerland_repair_regional_wars = yes", verify_event)
        startup = named_block(on_actions, "on_startup")
        self.assertIn("ADISCORD_vorkerland_collapse.64 days = 1", startup)
        self.assertNotIn("ADISCORD_vorkerland_repair_regional_wars = yes", startup)

    def test_doctor_worx_metropolitan_states_have_named_victory_points(self) -> None:
        expected = {
            36: {12227: 60, 16417: 20, 5907: 10},
            37: {16400: 30, 16413: 15, 754: 10},
            38: {16398: 30, 6790: 20, 16425: 10},
            39: {16397: 40, 12985: 20, 16404: 10},
        }
        for state_id, victory_points in expected.items():
            source = read(f"history/states/{state_id}-{state_id}.txt")
            actual = {
                int(province): int(value)
                for province, value in re.findall(
                    r"victory_points\s*=\s*\{\s*(\d+)\s+(\d+)\s*\}", source
                )
            }
            self.assertEqual(actual, victory_points, state_id)

        loc = read("localisation/russian/victory_points_l_russian.yml")
        for province in set().union(*(set(points) for points in expected.values())):
            self.assertRegex(loc, rf"(?m)^\s*VICTORY_POINTS_{province}:\s*\"[^\"]+\"")
        for forbidden in ("\u0443\u0437\u0435\u043b", "\u043f\u0435\u0440\u0438\u043c\u0435\u0442\u0440"):
            self.assertNotRegex(
                loc.lower(), rf"(?m)^\s*VICTORY_POINTS_\d+:[^\n]*{forbidden}"
            )

    def test_dynamic_regional_front_fallback_is_removed(self) -> None:
        ai = read("common/ai_strategy/ADISCORD_vorkerland_collapse_ai.txt")
        self.assertNotIn("ADISCORD_vorkerland_dynamic_regional_front_commitment", ai)
        self.assertNotIn("country_trigger = {", ai)

    def test_central_wars_have_target_specific_ai_fronts(self) -> None:
        ai = read("common/ai_strategy/ADISCORD_vorkerland_collapse_ai.txt")
        minors = {"EYR", "EGC", "RIV", "REV", "YOR", "NDN", "SWB", "VHV", "OSV"}
        contracts = {
            "wrk": ("WKR", {"VAD", "TVA", *minors}, {"WTD"}, 100, "careful", "no"),
            "vad": ("VAD", {"WKR", "TVA", *minors}, {"WTD"}, 65, "rush", "yes"),
            "tva": ("TVA", {"WKR", "VAD", *minors}, set(), 100, "careful", "no"),
            **{
                tag.lower(): (tag, {"WKR", "VAD", "TVA"}, set(), 100, "rush", "no")
                for tag in minors
            },
        }
        for slug, (defender, required, optional, request, execution, manual) in contracts.items():
            front = named_block(
                ai, f"ADISCORD_vorkerland_front_central_against_{slug}"
            )
            allowed = named_block(front, "allowed")
            actual = set(re.findall(r"tag\s*=\s*([A-Z]{3})", allowed))
            self.assertLessEqual(required, actual)
            self.assertLessEqual(actual, required | optional)
            self.assertIn(f"has_war_with = {defender}", front)
            self.assertIn(f"front_unit_request tag = {defender} value = {request}", front)
            self.assertIn(f"front_control tag = {defender}", front)
            self.assertIn("priority = 1250", front)
            self.assertIn(f"execution_type = {execution}", front)
            self.assertIn(f"manual_attack = {manual}", front)

    def test_main_claimants_are_smaller_and_new_countries_form_connected_belts(self) -> None:
        effects = read("common/scripted_effects/ADISCORD_vorkerland_collapse_effects.txt")
        initial = named_block(effects, "ADISCORD_vorkerland_apply_initial_map")

        expected_states = {
            "WKR": {32, 33, 40, 200, 201},
            "WTD": {34},
            "VAD": {75, 106, 107, 121},
            "PWR": {71, 90, 91, 202},
            "TVA": {36, 37, 38, 39, 324},
            "EYR": {102, 109, 111, 325},
            "EGC": {81, 110, 124},
            "RIV": {79, 306, 308, 309, 327},
            "REV": {82, 323},
            "YOR": {108, 122, 123},
            "NDN": {27},
            "SWB": {35},
            "VHV": {315, 316, 317},
            "OSV": {318, 320},
            "ZTA": {199},
        }
        for tag, states in expected_states.items():
            if tag in {"WKR", "VAD", "PWR"}:
                block = named_block(initial, tag)
            else:
                block = named_block(effects, f"ADISCORD_vorkerland_setup_{tag.lower()}")
            self.assertEqual(
                {int(value) for value in re.findall(r"transfer_state\s*=\s*(\d+)", block)},
                states,
                tag,
            )

        for tag in ("RIV", "REV", "YOR", "NDN", "SWB", "VHV", "OSV"):
            self.assertIn(f"ADISCORD_vorkerland_setup_{tag.lower()} = yes", initial)

    def test_legacy_claimant_armies_are_split_among_the_new_states(self) -> None:
        self.assertEqual(read("history/units/WRK.txt").count("division = {"), 12)
        self.assertEqual(read("history/units/VAD.txt").count("division = {"), 12)
        effects = named_block(
            read("common/scripted_effects/ADISCORD_vorkerland_collapse_effects.txt"),
            "ADISCORD_vorkerland_prepare_initial_combatants",
        )
        for tag in ("VAD",):
            claimant = named_block(effects, tag)
            self.assertIn("create_unit =", claimant)
            self.assertIn(f"owner = {tag}", claimant)
            self.assertIn("ADISCORD_combat_platform_2170", claimant)
            self.assertIn("ADISCORD_fighter_airframe_2163", claimant)
        central_minor_oobs = {
            "EYR": 6,
            "EGC": 5,
            "RIV": 6,
            "REV": 5,
            "YOR": 5,
            "NDN": 4,
            "SWB": 4,
            "VHV": 5,
            "OSV": 4,
        }
        for tag, divisions in central_minor_oobs.items():
            self.assertEqual(
                read(f"history/units/{tag}_vorkerland_collapse.txt").count("division = {"),
                divisions,
                tag,
            )
        self.assertEqual(
            read("history/units/ZTA_vorkerland_collapse.txt").count("division = {"),
            3,
        )

    def test_minor_emergency_levies_are_bounded_and_decision_driven(self) -> None:
        triggers = read("common/scripted_triggers/ADISCORD_vorkerland_collapse_triggers.txt")
        minor = named_block(triggers, "ADISCORD_vorkerland_is_minor_combatant")
        for tag in ("EYR", "EGC", "RIV", "REV", "YOR", "NDN", "SWB", "VHV", "OSV"):
            self.assertIn(f"tag = {tag}", minor)
        self.assertIn("ADISCORD_vorkerland_is_regional_combatant = yes", minor)
        for tag in ("WRK", "VAD", "TVA", "IVN", "EXZ"):
            self.assertNotIn(f"tag = {tag}", minor)

        effects = read("common/scripted_effects/ADISCORD_vorkerland_collapse_effects.txt")
        reserves = {
            "EYR": (6500, 800),
            "EGC": (5500, 650),
            "RIV": (7000, 850),
            "REV": (5500, 650),
            "YOR": (5500, 650),
            "NDN": (4500, 550),
            "SWB": (4500, 550),
            "VHV": (5500, 650),
            "OSV": (4500, 550),
        }
        for tag, (manpower, rifles) in reserves.items():
            setup = named_block(effects, f"ADISCORD_vorkerland_setup_{tag.lower()}")
            self.assertIn(f"add_manpower = {manpower}", setup, tag)
            self.assertIn(f"amount = {rifles} producer = {tag}", setup, tag)
        levies = named_block(effects, "ADISCORD_vorkerland_raise_emergency_levies")
        for token in (
            "add_manpower = 1800",
            "amount = 360 producer = ROOT",
            'division_template = \\"Emergency Militia\\"',
            "count = 2",
        ):
            self.assertIn(token, levies)
        self.assertNotIn("every_country", levies)
        self.assertNotIn("every_state", levies)

        decisions = read("common/decisions/ADISCORD_vorkerland_collapse_decisions.txt")
        decision = named_block(decisions, "ADISCORD_vorkerland_raise_emergency_levies")
        for token in (
            "allowed = { ADISCORD_vorkerland_is_minor_combatant = yes }",
            "has_war = yes",
            "cost = 25",
            "days_remove = 21",
            "fire_only_once = yes",
            "remove_effect = { ADISCORD_vorkerland_raise_emergency_levies = yes }",
        ):
            self.assertIn(token, decision)
        on_actions = read("common/on_actions/01_ADISCORD_vorkerland_collapse_on_actions.txt")
        self.assertNotIn("ADISCORD_vorkerland_raise_emergency_levies", on_actions)

    def test_ivanland_starts_as_a_major_with_a_field_army(self) -> None:
        history = read("history/countries/IVN - IvanLand.txt")
        self.assertIn("set_major = yes", history)
        self.assertIn("set_research_slots = 5", history)

        oob = read("history/units/IVN.txt")
        units = named_block(oob, "units")
        self.assertEqual(units.count("division = {"), 16)
        self.assertEqual(units.count('division_template = "Capital Guard"'), 2)
        self.assertEqual(units.count('division_template = "Line Infantry Brigade"'), 10)
        self.assertEqual(units.count('division_template = "Local Security Detachment"'), 4)
        self.assertEqual(
            {int(value) for value in re.findall(r"location\s*=\s*(\d+)", units)},
            {16568, 9327, 3462, 3318, 888, 838, 2448, 882, 702, 595, 1971, 3447, 579, 2262, 423, 4217},
        )
        self.assertGreaterEqual(
            min(float(value) for value in re.findall(r"start_equipment_factor\s*=\s*([0-9.]+)", units)),
            0.70,
        )
        self.assertIn("requested_factories = 6", oob)
        self.assertGreaterEqual(oob.count("requested_factories = 2"), 2)

        profiles = json.loads(read("tools/data/adiscord_starting_technology_profiles.json"))
        ivn_profile = profiles["countries"]["IVN"]
        self.assertEqual(ivn_profile["evidence"]["research_slots"], 5)
        self.assertEqual(ivn_profile["evidence"]["oob_divisions"], 16)
        self.assertIn("five research slots", ivn_profile["rationale"])

        effects = read("common/scripted_effects/ADISCORD_vorkerland_collapse_effects.txt")
        intervention = named_block(effects, "ADISCORD_vorkerland_begin_ivanland_intervention")
        for token in (
            "ADISCORD_vorkerland_ivanland_expedition_supplied",
            "add_manpower = 8000",
            "amount = 1600 producer = IVN",
            "type = support_equipment amount = 120 producer = IVN",
            "type = artillery_equipment amount = 48 producer = IVN",
            "add_fuel = 5000",
        ):
            self.assertIn(token, intervention)

    def test_partition_evacuates_legacy_armies_to_owned_capitals(self) -> None:
        effects = read("common/scripted_effects/ADISCORD_vorkerland_collapse_effects.txt")
        relocation = named_block(effects, "ADISCORD_vorkerland_relocate_legacy_armies")
        self.assertIn("every_state", relocation)
        for tag, capital in {
            "WRK": 32,
            "VAD": 75,
            "ZAO": 72,
            "PWR": 71,
            "VLA": 74,
            "ROM": 73,
            "SOL": 76,
            "TRU": 80,
        }.items():
            self.assertRegex(
                relocation,
                rf"teleport_armies\s*=\s*\{{\s*limit\s*=\s*\{{\s*tag\s*=\s*{tag}\s*\}}\s*to_state\s*=\s*{capital}\s*\}}",
                tag,
            )
        initial = named_block(effects, "ADISCORD_vorkerland_apply_initial_map")
        self.assertIn("ADISCORD_vorkerland_relocate_legacy_armies = yes", initial)
        self.assertGreater(
            initial.find("ADISCORD_vorkerland_relocate_legacy_armies = yes"),
            initial.find("ADISCORD_vorkerland_prepare_initial_combatants = yes"),
        )

    def test_reunification_requires_neighbors_and_legacy_central_producer_is_retired(self) -> None:
        decisions = read("common/decisions/ADISCORD_vorkerland_collapse_decisions.txt")
        reunification = named_block(decisions, "ADISCORD_vorkerland_continue_reunification")
        self.assertIn("every_neighbor_country", reunification)
        self.assertIn("declare_war_on", reunification)
        self.assertIn("ai_will_do", reunification)

        self.assertNotIn(
            "ADISCORD_vorkerland_consolidate_central_border", decisions
        )

    def test_unrelated_wars_do_not_freeze_new_fronts(self) -> None:
        triggers = read("common/scripted_triggers/ADISCORD_vorkerland_collapse_triggers.txt")
        for key in (
            "ADISCORD_vorkerland_is_main_claimant_rival_for_ROOT",
            "ADISCORD_vorkerland_is_central_target_for_ROOT",
            "ADISCORD_vorkerland_is_reunification_target_for_ROOT",
        ):
            self.assertNotIn("has_war = no", named_block(triggers, key), key)

    def test_central_winners_receive_a_short_recovery_window(self) -> None:
        on_actions = read("common/on_actions/01_ADISCORD_vorkerland_collapse_on_actions.txt")
        capitulation = named_block(on_actions, "on_capitulation")
        self.assertIn("ADISCORD_vorkerland_is_central_claimant = yes", capitulation)
        self.assertIn("ADISCORD_vorkerland_is_main_claimant = yes", capitulation)
        self.assertIn("ADISCORD_vorkerland_settle_central_capitulation = yes", capitulation)
        effects = read("common/scripted_effects/ZZ_ADISCORD_capitulation_distribution_effects.txt")
        settlement = named_block(effects, "ADISCORD_vorkerland_settle_central_capitulation")
        self.assertIn("flag = ADISCORD_vorkerland_central_recovery", settlement)
        self.assertIn("days = 35", settlement)
        self.assertIn("add_manpower = 1500", settlement)
        self.assertIn("ADISCORD_vorkerland_central_minor_winner_wrk", settlement)
        self.assertIn("ADISCORD_vorkerland_phase_postwar_integration", capitulation)
        self.assertIn("ADISCORD_vorkerland_reunification_verified", capitulation)
        finalizer = named_block(
            effects, "ADISCORD_vorkerland_finalize_central_minor_settlement"
        )
        self.assertIn(
            "has_country_flag = ADISCORD_vorkerland_central_minor_winner_wrk",
            finalizer,
        )
        self.assertIn("WRK = { exists = yes is_subject = no", finalizer)
        self.assertIn("annex_country = { target = ROOT transfer_troops = no }", finalizer)
        retry = event_block(
            read("events/ADISCORD_vorkerland_collapse_events.txt"),
            "ADISCORD_vorkerland_collapse.66",
        )
        self.assertIn(
            "set_country_flag = ADISCORD_vorkerland_central_minor_settlement_force_transfer",
            retry,
        )
        for tag in ("WKR", "VAD", "TVA", "WRK"):
            self.assertIn(
                f"every_owned_state = {{ {tag} = {{ transfer_state = PREV }} }}",
                finalizer,
            )

    def test_collapse_opening_news_is_immediate_and_single_shot(self) -> None:
        events = read("events/ADISCORD_vorkerland_collapse_events.txt")
        news = read("events/ADISCORD_news.txt")
        outbreak = named_block(events, "country_event")
        self.assertEqual(events.count("id = ADISCORD_superevent_news.1"), 1)
        self.assertIn("NOT = { has_global_flag = ADISCORD_vorkerland_collapse_news_shown }", outbreak)
        self.assertIn("set_global_flag = ADISCORD_vorkerland_collapse_news_shown", outbreak)
        opening = named_block(outbreak, "news_event")
        for delayed in ("hours =", "days =", "random_hours", "random_days"):
            self.assertNotIn(delayed, opening)
        self.assertLess(
            outbreak.find("ADISCORD_vorkerland_apply_claimant_cosmetics = yes"),
            outbreak.find("news_event = { id = ADISCORD_superevent_news.1 }"),
        )
        opening_definition = re.search(
            r"(?ms)^news_event\s*=\s*\{\s*#vorkerland civilwar\b(.*?)(?=^news_event\s*=|\Z)",
            news,
        )
        self.assertIsNotNone(opening_definition)
        self.assertIn("major = yes", opening_definition.group(1))
        self.assertNotIn("hidden = yes", opening_definition.group(1))
        self.assertIn("id = ADISCORD_superevent_news.1", opening_definition.group(0))
        self.assertIn(
            "country_event = { id = ADISCORD_superevent_audio.1 }",
            opening_definition.group(1),
        )
        self.assertIn("every_country", opening_definition.group(1))
        self.assertNotIn("scoped_sound_effect", opening_definition.group(1))
        news_loc = read("localisation/russian/events_l_russian.yml")
        self.assertIn('news.0.t: "Конец единого Воркерланда"', news_loc)
        superevent_loc = read("localisation/russian/ADISCORD_superevents_l_russian.yml")
        self.assertNotIn(
            'superevent_vorkerland_fragmented_title: "Конец единого Воркерланда"',
            superevent_loc,
        )

    def test_tower_is_one_shot_and_dirty_zone_waits_three_years(self) -> None:
        events = read("events/ADISCORD_vorkerland_collapse_events.txt")
        on_actions = read("common/on_actions/01_ADISCORD_vorkerland_collapse_on_actions.txt")
        outbreak = event_block(events, "ADISCORD_vorkerland_collapse.1")
        legacy = event_block(events, "ADISCORD_vorkerland_collapse.10")
        reveal = event_block(events, "ADISCORD_vorkerland_collapse.85")

        tower_guard = "ADISCORD_vorkerland_unity_tower_destruction_resolved"
        self.assertIn(f"NOT = {{ has_global_flag = {tower_guard} }}", outbreak)
        self.assertEqual(outbreak.count(f"set_global_flag = {tower_guard}"), 1)
        self.assertEqual(events.count("launch_nuke = {"), 1)
        self.assertLess(
            outbreak.find(f"set_global_flag = {tower_guard}"),
            outbreak.find("launch_nuke = {"),
        )
        self.assertIn(f"set_global_flag = {tower_guard}", on_actions)

        reveal_flag = "ADISCORD_vorkerland_dirty_reveal_v2_scheduled"
        self.assertIn(f"set_global_flag = {reveal_flag}", outbreak)
        self.assertIn("id = ADISCORD_vorkerland_collapse.85", outbreak)
        self.assertIn("days = 1095", outbreak)
        self.assertNotIn("random_days", outbreak)
        self.assertIn("trigger = { always = no }", legacy)
        self.assertNotIn("ADISCORD_vorkerland_dirty_opened", legacy)
        self.assertIn(f"has_global_flag = {reveal_flag}", reveal)
        self.assertIn("set_global_flag = ADISCORD_vorkerland_dirty_opened", reveal)
        self.assertIn("ADISCORD_vorkerland_show_dirty_opening_superevent = yes", reveal)
        self.assertIn(
            "country_event = { id = ADISCORD_vorkerland_collapse.85 days = 1095 }",
            on_actions,
        )

    def test_central_claimants_must_finish_the_core_first(self) -> None:
        triggers = read("common/scripted_triggers/ADISCORD_vorkerland_collapse_triggers.txt")
        main = named_block(triggers, "ADISCORD_vorkerland_is_main_claimant")
        self.assertEqual(set(re.findall(r"tag\s*=\s*([A-Z]{3})", main)), {"WKR", "VAD", "TVA"})
        for candidate in ("worker", "vlad", "dorian"):
            block = named_block(triggers, f"ADISCORD_vorkerland_{candidate}_victory_candidate")
            for defeated in ("eyr", "egc", "riv", "rev", "yor", "ndn", "swb", "vhv", "osv"):
                self.assertIn(f"ADISCORD_vorkerland_{defeated}_defeated = yes", block)
            self.assertNotIn("ADISCORD_vorkerland_tgd_defeated", block)
            self.assertIn("controls_state = 40", block)
        central = named_block(triggers, "ADISCORD_vorkerland_is_central_claimant")
        self.assertNotIn("tag = TGD", central)
        self.assertEqual(
            set(re.findall(r"tag\s*=\s*([A-Z]{3})", central)),
            {"WKR", "VAD", "TVA", "EYR", "EGC", "RIV", "REV", "YOR", "NDN", "SWB", "VHV", "OSV"},
        )
        regional = named_block(triggers, "ADISCORD_vorkerland_is_regional_combatant")
        for tag in ("VLA", "EBA", "TGD"):
            self.assertIn(f"tag = {tag}", regional)
        self.assertNotIn("ADISCORD_vorkerland_is_local_rival_for_ROOT", triggers)

    def test_central_victory_does_not_annex_the_periphery(self) -> None:
        maps = read("common/scripted_effects/ADISCORD_vorkerland_collapse_map_effects.txt")
        for candidate in ("worker", "vlad", "dorian"):
            block = named_block(maps, f"ADISCORD_vorkerland_apply_{candidate}_map")
            for forbidden in ("transfer_state", "annex_country", "puppet =", "set_autonomy"):
                self.assertNotIn(forbidden, block, f"{candidate}: {forbidden}")
            self.assertIn("ADISCORD_vorkerland_central_unifier", block)

    def test_rom_and_tru_coexist_with_wrk_but_not_vad(self) -> None:
        triggers = read("common/scripted_triggers/ADISCORD_vorkerland_collapse_triggers.txt")
        targets = named_block(triggers, "ADISCORD_vorkerland_is_reunification_target_for_ROOT")
        self.assertIn("tag = ROM", targets)
        self.assertIn("tag = TRU", targets)
        self.assertIn("ROOT = { tag = VAD }", targets)
        decisions = read("common/decisions/ADISCORD_vorkerland_focus_decisions.txt")
        recognition = named_block(decisions, "ADISCORD_vorkerland_recognize_free_republics")
        self.assertIn("has_country_flag = ADISCORD_vorkerland_focus_worker_free_republics", recognition)
        self.assertEqual(recognition.count("is_subject = no"), 4)
        self.assertIn("country = ROM", recognition)
        self.assertIn("country = TRU", recognition)

    def test_central_sloboda_is_an_independent_local_target(self) -> None:
        effects = read("common/scripted_effects/ADISCORD_vorkerland_collapse_effects.txt")
        egc = named_block(effects, "ADISCORD_vorkerland_setup_egc")
        csl = named_block(effects, "ADISCORD_vorkerland_setup_csl")
        self.assertNotIn("transfer_state = 104", egc)
        self.assertIn("transfer_state = 104", csl)
        self.assertIn("104 = { add_core_of = CSL", csl)
        self.assertIn("set_capital = { state = 104 }", csl)

        triggers = read("common/scripted_triggers/ADISCORD_vorkerland_collapse_triggers.txt")
        regional = named_block(triggers, "ADISCORD_vorkerland_is_regional_combatant")
        for tag in ("SOL", "SRA", "CSL"):
            self.assertIn(f"tag = {tag}", regional)

        decisions = read("common/decisions/ADISCORD_vorkerland_collapse_decisions.txt")
        regional_war = named_block(decisions, "ADISCORD_vorkerland_open_regional_fronts")
        effects = read("common/scripted_effects/ADISCORD_vorkerland_collapse_effects.txt")
        repair = named_block(effects, "ADISCORD_vorkerland_repair_regional_wars")
        self.assertIn("tag = SOL", regional_war)
        self.assertIn("target = CSL", repair)
        self.assertNotIn("add_to_war", regional_war)

    def test_worker_victory_has_no_reunification_war_decision(self) -> None:
        decisions = read("common/decisions/ADISCORD_vorkerland_collapse_decisions.txt")
        reunification = named_block(decisions, "ADISCORD_vorkerland_continue_reunification")
        allowed = named_block(reunification, "allowed")
        self.assertIn("ADISCORD_vorkerland_is_main_claimant = yes", allowed)
        self.assertIn("NOT = { tag = WRK }", allowed)

    def test_no_timeout_fragmentation_outcome_exists(self) -> None:
        combined = "\n".join(
            read(path)
            for path in (
                "events/ADISCORD_vorkerland_collapse_events.txt",
                "common/scripted_effects/ADISCORD_vorkerland_collapse_map_effects.txt",
                "common/scripted_guis/superevents.txt",
                "common/scripted_localisation/ADISCORD_scripted_loc_superevents.txt",
                "interface/superevents.gfx",
                "interface/superevents.gui",
                "localisation/russian/ADISCORD_superevents_l_russian.yml",
            )
        )
        for forbidden in (
            "ADISCORD_vorkerland_collapse.23",
            "ADISCORD_vorkerland_apply_fragmented_map",
            "superevent_vorkerland_fragmented",
            "ADISCORD_vorkerland_fragmented",
            "Фронты стали границами",
        ):
            self.assertNotIn(forbidden, combined)


class FrontAndSupplyTests(unittest.TestCase):
    def test_dead_stalemate_system_is_gone(self) -> None:
        combined = "\n".join(read(path) for path in (
            "common/ai_strategy/ADISCORD_vorkerland_collapse_ai.txt",
            "common/decisions/ADISCORD_vorkerland_collapse_decisions.txt",
            "common/ideas/ADISCORD_vorkerland_collapse_ideas.txt",
            "common/scripted_effects/ADISCORD_vorkerland_collapse_effects.txt",
            "events/ADISCORD_vorkerland_collapse_events.txt",
            "localisation/russian/ADISCORD_vorkerland_collapse_l_russian.yml",
        ))
        for stale in ("stalemate", "war_weariness", "to_the_last"):
            self.assertNotIn(stale, combined)
        self.assertIn("ADISCORD_vorkerland_phase.", combined)

    def test_ai_fronts_keep_pressure_without_supply_blind_local_attacks(self) -> None:
        ai = read("common/ai_strategy/ADISCORD_vorkerland_collapse_ai.txt")
        economy = named_block(ai, "ADISCORD_vorkerland_collapse_war_economy")
        self.assertIn("type = ai_wanted_divisions_factor value = 8", economy)
        self.assertNotIn("ADISCORD_vorkerland_collapse_front_commitment", ai)
        for strategy in re.findall(r"ai_strategy\s*=\s*\{([^{}]*)\}", ai, re.DOTALL):
            if "type = front_control" in strategy or "type = front_unit_request" in strategy:
                self.assertEqual(len(re.findall(r"\btag\s*=", strategy)), 1, strategy)
        for attacker, defender in (
            ("ZAO", "WPA"), ("WPA", "ZAO"), ("WPS", "ZAO"), ("ZAO", "WPS"),
            ("ZAO", "PSD"), ("PSD", "ZAO"), ("ZAO", "PWR"), ("PWR", "ZAO"),
            ("WPA", "PSD"), ("PSD", "WPA"), ("WPA", "PWR"), ("PWR", "WPA"),
            ("WPS", "PSD"), ("PSD", "WPS"), ("WPS", "PWR"), ("PWR", "WPS"),
            ("PWR", "PSD"), ("PSD", "PWR"),
        ):
            front = named_block(ai, f"ADISCORD_vorkerland_front_{attacker.lower()}_{defender.lower()}")
            self.assertIn(f"has_war_with = {defender}", front)
            request = 33 if attacker in {"WPA", "WPS"} else 25
            self.assertIn(f"front_unit_request tag = {defender} value = {request}", front)
            self.assertIn("execution_type = careful", front)
            self.assertIn("manual_attack = no", front)
            self.assertNotIn("value = 80", front)
            self.assertNotIn("execution_type = rush", front)

        for attacker, defender in (
            ("VLA", "EBA"), ("EBA", "VLA"),
            ("VLA", "TGD"), ("TGD", "VLA"), ("EBA", "TGD"), ("TGD", "EBA"),
            ("SOL", "SRA"), ("SRA", "SOL"),
            ("SOL", "CSL"), ("CSL", "SOL"),
            ("SRA", "CSL"), ("CSL", "SRA"),
        ):
            front = named_block(ai, f"ADISCORD_vorkerland_front_{attacker.lower()}_{defender.lower()}")
            self.assertIn(f"has_war_with = {defender}", front)
            self.assertIn(f"front_control tag = {defender}", front)
            self.assertIn("manual_attack = yes", front)

        for attacker, defender in (
            ("ROM", "DVA"), ("DVA", "ROM"),
            ("TRU", "ZTA"), ("ZTA", "TRU"),
        ):
            front = named_block(ai, f"ADISCORD_vorkerland_front_{attacker.lower()}_{defender.lower()}")
            self.assertIn(f"front_unit_request tag = {defender} value = 75", front)
            self.assertIn("execution_type = careful", front)
            self.assertIn("manual_attack = no", front)
            self.assertNotIn("execution_type = rush", front)
            self.assertNotIn("manual_attack = yes", front)

    def test_global_ai_thresholds_keep_small_collapse_fronts_moving(self) -> None:
        defines = read("common/defines/ADISCORD_defines_changes.lua")
        for token in (
            "NDefines.NMilitary.PLAN_EXECUTE_RUSH = -200",
            "NDefines.NAI.PLAN_ATTACK_MIN_ORG_FACTOR_HIGH = 0.15",
            "NDefines.NAI.PLAN_ATTACK_MIN_STRENGTH_FACTOR_HIGH = 0.25",
            "NDefines.NAI.FRONT_EVAL_UNIT_SUPPLY_AND_ORG_LACK_IMPACT = 0.2",
            "NDefines.NAITheatre.AI_THEATRE_SUPPLY_CRISIS_LIMIT = 0.0",
        ):
            self.assertIn(token, defines)

    def test_technograd_is_a_supplied_megalopolis(self) -> None:
        state_paths = list((ROOT / "history" / "states").glob("105-*.txt"))
        self.assertEqual(len(state_paths), 1)
        state = state_paths[0].read_text(encoding="utf-8-sig")
        for token in ("manpower = 9800000", "state_category = megalopolis", "infrastructure = 5", "local_supplies = 10.0"):
            self.assertIn(token, state)
        self.assertNotIn("impassable = yes", state)

    def test_technograd_uses_the_real_vla_eba_border_region(self) -> None:
        effects = read("common/scripted_effects/ADISCORD_vorkerland_collapse_effects.txt")
        tgd = named_block(effects, "ADISCORD_vorkerland_setup_tgd")
        self.assertIn("transfer_state = 105", tgd)
        self.assertIn("105 = { add_core_of = TGD", tgd)
        self.assertIn("set_capital = { state = 105 }", tgd)
        self.assertNotIn("transfer_state = 32", tgd)
        self.assertNotIn("transfer_state = 40", tgd)
        initial = named_block(effects, "ADISCORD_vorkerland_apply_initial_map")
        wkr = named_block(initial, "WKR")
        self.assertRegex(wkr, r"transfer_state\s*=\s*32\b")
        self.assertRegex(wkr, r"transfer_state\s*=\s*40\b")
        self.assertIn("40 = { set_state_controller_to = WKR }", initial)
        self.assertNotRegex(wkr, r"transfer_state\s*=\s*105\b")

    def test_technograd_starts_crippled_and_has_one_120_day_recovery(self) -> None:
        effects = read("common/scripted_effects/ADISCORD_vorkerland_collapse_effects.txt")
        setup = named_block(effects, "ADISCORD_vorkerland_setup_tgd")
        self.assertIn("add_ideas = ADISCORD_vorkerland_tgd_grid_collapse", setup)
        self.assertNotIn("add_ideas = ADISCORD_vorkerland_tgd_living_grid", setup)

        ideas = read("common/ideas/ADISCORD_vorkerland_collapse_ideas.txt")
        collapse = named_block(ideas, "ADISCORD_vorkerland_tgd_grid_collapse")
        for penalty in (
            "industrial_capacity_factory = -0.35",
            "production_factory_efficiency_gain_factor = -0.30",
            "army_org_factor = -0.15",
            "repair_speed_factor = -0.40",
            "supply_consumption_factor = 0.20",
        ):
            self.assertIn(penalty, collapse)

        decisions = read("common/decisions/ADISCORD_vorkerland_collapse_decisions.txt")
        recovery = named_block(decisions, "ADISCORD_vorkerland_tgd_rebuild_grid")
        self.assertIn("days_remove = 120", recovery)
        self.assertIn("has_war = no", recovery)
        for rival in ("VLA", "EBA"):
            self.assertIn(f"NOT = {{ country_exists = {rival} }}", recovery)
        self.assertIn("remove_ideas = ADISCORD_vorkerland_tgd_grid_collapse", recovery)
        self.assertIn("add_ideas = ADISCORD_vorkerland_tgd_living_grid", recovery)

        on_actions = read("common/on_actions/01_ADISCORD_vorkerland_collapse_on_actions.txt")
        self.assertNotIn("ADISCORD_vorkerland_tgd_rebuild_grid", on_actions)

    def test_border_states_are_not_demilitarized(self) -> None:
        for state_id in (90, 91, 93):
            paths = list((ROOT / "history" / "states").glob(f"{state_id}-*.txt"))
            self.assertEqual(len(paths), 1)
            state = paths[0].read_text(encoding="utf-8-sig")
            self.assertNotIn("set_demilitarized_zone = yes", state)
            supply = float(re.search(r"local_supplies\s*=\s*([\d.]+)", state).group(1))
            self.assertGreaterEqual(supply, 1.5)

    def test_remote_local_wars_have_three_supplied_formations_per_side(self) -> None:
        oob_paths = {
            "PWR": "history/units/PWR.txt",
            "PSD": "history/units/PSD_vorkerland_collapse.txt",
            "ROM": "history/units/ROM.txt",
            "DVA": "history/units/DVA_vorkerland_collapse.txt",
            "TRU": "history/units/TRU.txt",
            "ZTA": "history/units/ZTA_vorkerland_collapse.txt",
        }
        for tag, path in oob_paths.items():
            oob = read(path)
            expected = 5 if tag in {"PWR", "PSD"} else 3
            self.assertEqual(oob.count("division = {"), expected, tag)
            equipment = [
                float(value)
                for value in re.findall(r"start_equipment_factor\s*=\s*([\d.]+)", oob)
            ]
            self.assertEqual(len(equipment), expected, tag)
            self.assertGreaterEqual(min(equipment), 0.55, tag)

    def test_remote_local_capitals_have_industry_and_supply_nodes(self) -> None:
        capitals = {
            "PWR": (71, "16591"),
            "PSD": (194, "2339"),
            "ROM": (73, "16571"),
            "DVA": (145, "6729"),
            "TRU": (80, "3083"),
            "ZTA": (199, "12930"),
        }
        supply_nodes = {
            line.split()[1]
            for line in read("map/supply_nodes.txt").splitlines()
            if len(line.split()) == 2
        }
        railway_provinces = set(re.findall(r"\b\d+\b", read("map/railways.txt")))
        for tag, (state_id, hub) in capitals.items():
            paths = list((ROOT / "history" / "states").glob(f"{state_id}-*.txt"))
            self.assertEqual(len(paths), 1, tag)
            state = paths[0].read_text(encoding="utf-8-sig")
            supply = float(re.search(r"local_supplies\s*=\s*([\d.]+)", state).group(1))
            self.assertGreaterEqual(supply, 3.0, tag)
            self.assertRegex(state, r"arms_factory\s*=\s*2\b", tag)
            self.assertIn(hub, supply_nodes, tag)
            self.assertIn(hub, railway_provinces, tag)

    def test_selected_armies_receive_finite_starting_reserves(self) -> None:
        effects = read("common/scripted_effects/ADISCORD_vorkerland_collapse_effects.txt")
        for tag in ("TVA", "EYR", "EGC", "RIV", "REV", "YOR", "NDN", "SWB", "VHV", "OSV", "TGD", "EBA", "PSD", "DVA", "ZTA", "WPA", "WPS"):
            block = named_block(effects, f"ADISCORD_vorkerland_setup_{tag.lower()}")
            manpower = re.search(r"add_manpower\s*=\s*(\d+)", block)
            rifles = re.search(r"add_equipment_to_stockpile\s*=\s*\{[^{}]*amount\s*=\s*(\d+)", block)
            self.assertIsNotNone(manpower, tag)
            self.assertGreaterEqual(int(manpower.group(1)), 2000 if tag == "NDN" else 3000, tag)
            self.assertIsNotNone(rifles, tag)
            self.assertGreaterEqual(int(rifles.group(1)), 160, tag)
        initial = named_block(effects, "ADISCORD_vorkerland_prepare_initial_combatants")
        for tag, manpower, rifles in (
            ("ZAO", 4000, 850), ("PWR", 8000, 1600), ("VLA", 8000, 1800),
            ("ROM", 6000, 1200), ("SOL", 3000, 500), ("TRU", 7000, 1400),
        ):
            block = named_block(initial, tag)
            self.assertIn(f"add_manpower = {manpower}", block, tag)
            self.assertIn(f"amount = {rifles}", block, tag)
        tva_oob = read("history/units/TVA_vorkerland_collapse.txt")
        self.assertEqual(tva_oob.count("division = {"), 15)
        self.assertIn("TVA Mobile Test Group", tva_oob)
        self.assertIn("TVA Infiltration Cell", tva_oob)

    def test_eba_receives_the_approved_finite_reserve(self) -> None:
        effects = read("common/scripted_effects/ADISCORD_vorkerland_collapse_effects.txt")
        eba = named_block(effects, "ADISCORD_vorkerland_setup_eba")
        self.assertIn("add_manpower = 10000", eba)
        self.assertIn("amount = 1100", eba)

    def test_eba_militia_cover_the_capital_and_two_secondary_cities(self) -> None:
        self.assertEqual(CAPITALS["EBA"], (197, 16623))
        oob = read("history/units/EBA_vorkerland_collapse.txt")
        self.assertEqual(oob.count("division = {"), 4)
        locations = [int(value) for value in re.findall(r"location\s*=\s*(\d+)", oob)]
        self.assertCountEqual(locations, [16623, 16623, 16617, 16637])

    def test_vla_can_cover_both_local_fronts_without_an_auto_win_stack(self) -> None:
        oob = read("history/units/VLA.txt")
        self.assertEqual(oob.count("division = {"), 4)
        self.assertEqual(oob.count('division_template = "Line Infantry Brigade"'), 2)
        self.assertEqual(oob.count('division_template = "Local Security Detachment"'), 2)
        self.assertGreaterEqual(oob.count("start_equipment_factor = 0.55"), 2)

        effects = read("common/scripted_effects/ADISCORD_vorkerland_collapse_effects.txt")
        initial = named_block(effects, "ADISCORD_vorkerland_prepare_initial_combatants")
        vla = named_block(initial, "VLA")
        self.assertIn("add_manpower = 8000", vla)
        self.assertIn("amount = 1800", vla)

    def test_collapse_frees_actual_subjects_and_factions_after_spawn(self) -> None:
        effects = read("common/scripted_effects/ADISCORD_vorkerland_collapse_effects.txt")
        events = read("events/ADISCORD_vorkerland_collapse_events.txt")
        outbreak = named_block(events, "country_event")
        self.assertLess(
            outbreak.find("ADISCORD_vorkerland_apply_initial_map = yes"),
            outbreak.find("ADISCORD_vorkerland_teardown_confederation = yes"),
        )
        teardown = named_block(effects, "ADISCORD_vorkerland_teardown_confederation")
        self.assertNotIn("is_subject_of = WRK", teardown)
        self.assertNotIn("create_faction", outbreak)
        self.assertNotIn("add_to_faction", outbreak)
        for tag in ("NAM", "DAN", "VAD", "ZAO", "PWR", "VLA", "ROM", "SOL", "TRU", "TVA", "RIV", "REV", "YOR", "NDN", "SWB", "VHV", "OSV", "TGD", "IBA", "IBL"):
            block = named_block(teardown, tag)
            self.assertIn("is_subject = yes", block, tag)
            self.assertIn("overlord =", block, tag)
            self.assertIn(f"target = {tag}", block, tag)
            self.assertIn("autonomy_state = autonomy_free", block, tag)
            self.assertIn("leave_faction = yes", block, tag)

    def test_only_zao_and_volnograd_can_restore_district_status(self) -> None:
        decisions = read("common/decisions/ADISCORD_vorkerland_collapse_decisions.txt")
        decision = named_block(decisions, "ADISCORD_vorkerland_restore_loyalist_district")
        allowed = named_block(decision, "allowed")
        self.assertEqual(set(re.findall(r"tag\s*=\s*([A-Z]{3})", allowed)), {"ZAO", "VLA"})
        for excluded in ("PWR", "ROM", "TRU", "SOL"):
            self.assertNotIn(f"tag = {excluded}", allowed)
        self.assertIn("autonomy_state = autonomy_district_in_Vorkerland", decision)
        self.assertIn("drop_cosmetic_tag = yes", decision)
        on_actions = read("common/on_actions/01_ADISCORD_vorkerland_collapse_on_actions.txt")
        self.assertNotIn("ADISCORD_vorkerland_northern_loyalist_district_restored", decisions + on_actions)


class CharactersAndPoliticsTests(unittest.TestCase):
    def test_dynamic_successors_promote_predeclared_country_leaders(self) -> None:
        effects = read("common/scripted_effects/ADISCORD_vorkerland_collapse_effects.txt")
        expected = {
            "tva": ("TVA_Dorian_Worx", "technocracy_ideology"),
            "eyr": ("EYR_Irina_Koval", "humanism_ideology"),
            "egc": ("EGC_Ruslan_Pike", "etatism_ideology"),
            "riv": ("RIV_Mikhail_Arsenyev", "pragmatism_ideology"),
            "rev": ("REV_Elena_Rudenko", "etatism_ideology"),
            "yor": ("YOR_Pavel_Korin", "humanism_ideology"),
            "ndn": ("NDN_Anna_Lind", "humanism_ideology"),
            "swb": ("SWB_Oskar_Renn", "etatism_ideology"),
            "vhv": ("VHV_Sergey_Melnik", "pragmatism_ideology"),
            "osv": ("OSV_Marina_Volkova", "humanism_ideology"),
            "csl": ("CSL_Miron_Rudakov", "pragmatism_ideology"),
            "wpa": ("WPA_Oliver_Larry_Gates", "humanism_ideology"),
            "wps": ("WPS_Karim_Dol", "technocracy_ideology"),
            "psd": ("PSD_Marta_Cinder", "etatism_ideology"),
            "eba": ("EBA_Vlad_Mecra", "hedonism_ideology"),
            "dva": ("DVA_Severin_Mark", "etatism_ideology"),
            "sra": ("SRA_Helio_Marr", "humanism_ideology"),
            "zta": ("ZTA_Viktor_Holt", "chauvinism_ideology"),
            "tgd": ("TGD_Ted_Cuttle", "technocracy_ideology"),
        }
        for tag, (character, ideology) in expected.items():
            setup = named_block(effects, f"ADISCORD_vorkerland_setup_{tag}")
            promotions = re.findall(r"promote_character\s*=\s*\{([^{}]*)\}", setup)
            self.assertTrue(
                any(
                    f"character = {character}" in promotion
                    and f"ideology = {ideology}" in promotion
                    for promotion in promotions
                ),
                character,
            )

    def test_joint_government_appoints_temp_government_portrait(self) -> None:
        characters = read("common/characters/ADISCORD_vorkerland_collapse_characters.txt")
        effects = read("common/scripted_effects/ADISCORD_vorkerland_collapse_effects.txt")
        council = named_block(characters, "WRK_VAD_Joint_Council")
        joint = named_block(effects, "ADISCORD_vorkerland_form_joint_government")
        appointment = named_block(effects, "ADISCORD_vorkerland_appoint_joint_council")
        claimant_cosmetics = named_block(
            effects, "ADISCORD_vorkerland_apply_claimant_cosmetics"
        )
        vad_cosmetics = named_block(claimant_cosmetics, "VAD")
        preserved_joint = named_block(vad_cosmetics, "if")
        ordinary_vad = named_block(vad_cosmetics, "else")
        on_actions = read("common/on_actions/01_ADISCORD_vorkerland_collapse_on_actions.txt")
        startup = named_block(on_actions, "on_startup")
        monthly = named_block(on_actions, "on_monthly")
        events = read("events/ADISCORD_vorkerland_collapse_events.txt")
        repair = re.search(
            r"(?ms)^country_event\s*=\s*\{\s*id\s*=\s*ADISCORD_vorkerland_collapse\.62\b"
            r"(.*?)(?=^country_event\s*=\s*\{|^add_namespace\s*=|\Z)",
            events,
        )

        self.assertIn("GFX_portrait_WRK_Temporary_Government", council)
        self.assertIn("country_leader", council)
        self.assertIn("ideology = pragmatism_ideology", council)
        self.assertIn("traits = { Emergency_Powers }", council)
        self.assertIn("ADISCORD_vorkerland_appoint_joint_council = yes", joint)
        self.assertNotIn("create_country_leader", appointment)
        self.assertNotIn("recruit_character", appointment)
        self.assertIn("promote_character", appointment)
        self.assertIn("character = WRK_VAD_Joint_Council", appointment)
        self.assertIn("portrait = GFX_portrait_WRK_Temporary_Government", appointment)
        self.assertIn("ADISCORD_vorkerland_joint_council_character_repair_v2", appointment)
        self.assertIn("ADISCORD_vorkerland_collapse.62 days = 1", joint)
        self.assertIn("ADISCORD_vorkerland_collapse.62 days = 1", startup)
        self.assertIsNotNone(repair)
        self.assertIn("ADISCORD_vorkerland_appoint_joint_council = yes", repair.group(1))
        self.assertIn("character = WRK_VAD_Joint_Council", repair.group(1))
        self.assertIn("ruling_only = yes", repair.group(1))
        self.assertNotIn("ADISCORD_vorkerland_appoint_joint_council = yes", monthly)
        self.assertIn(
            "has_global_flag = ADISCORD_vorkerland_joint_government_formed",
            preserved_joint,
        )
        self.assertIn(
            "set_cosmetic_tag = WRK_vorkerland_joint_government", preserved_joint
        )
        self.assertIn(
            "ADISCORD_vorkerland_appoint_joint_council = yes", preserved_joint
        )
        self.assertNotIn("VAD_vorkerland_restoration", preserved_joint)
        self.assertNotIn("GFX_portrait_WRK_Vlad_Petrichev_civilwar", preserved_joint)
        self.assertIn("set_cosmetic_tag = VAD_vorkerland_restoration", ordinary_vad)
        self.assertIn("GFX_portrait_WRK_Vlad_Petrichev_civilwar", ordinary_vad)

    def test_rimat_is_a_named_technocratic_directorate(self) -> None:
        characters = read("common/characters/ADISCORD_vorkerland_collapse_characters.txt")
        history = read("history/countries/PWR - PostWarZone.txt")
        effects = read("common/scripted_effects/ADISCORD_vorkerland_collapse_effects.txt")
        appointment = named_block(effects, "ADISCORD_vorkerland_appoint_pwr_technocrat")
        loc = read("localisation/russian/countries_l_russian.yml")
        collapse_loc = read("localisation/russian/ADISCORD_vorkerland_collapse_l_russian.yml")

        self.assertIn("PWR_Alexey_Lange", characters)
        self.assertIn("recruit_character = PWR_Alexey_Lange", history)
        self.assertIn("ruling_party = pragmatism", history)
        self.assertNotIn("ruling_party = technocracy", history)
        self.assertIn("ruling_party = technocracy", appointment)
        self.assertIn("character = PWR_Alexey_Lange", appointment)
        self.assertIn("ideology = technocracy_ideology", appointment)
        self.assertIn("portrait = GFX_Portrait_Forul_Generic_4", appointment)
        self.assertNotIn("recruit_character", appointment)
        self.assertIn('PWR_rimat_republic: "Риматская инженерная директория"', loc)
        self.assertIn('PWR_Alexey_Lange: "Алексей Ланге"', collapse_loc)

    def test_republic_wartime_ideologies_are_applied_only_by_collapse_events(self) -> None:
        effects = read("common/scripted_effects/ADISCORD_vorkerland_collapse_effects.txt")
        events = read("events/ADISCORD_vorkerland_collapse_events.txt")
        startup = named_block(
            read("common/on_actions/01_ADISCORD_vorkerland_collapse_on_actions.txt"),
            "on_startup",
        )
        histories = {
            "PWR": read("history/countries/PWR - PostWarZone.txt"),
            "ROM": read("history/countries/ROM - RomelLand.txt"),
            "TRU": read("history/countries/TRU - TrumanLand.txt"),
        }
        self.assertIn("ruling_party = pragmatism", histories["PWR"])
        self.assertIn("ruling_party = pragmatism", histories["ROM"])
        self.assertIn("ruling_party = pragmatism", histories["TRU"])
        for effect_id, ruling_party, character, event_id in (
            ("ADISCORD_vorkerland_appoint_pwr_technocrat", "technocracy", "PWR_Alexey_Lange", 44),
            ("ADISCORD_vorkerland_appoint_rom_etatist", "etatism", "ROM_Erwin_Von_Romanovskiy", 60),
            ("ADISCORD_vorkerland_appoint_tru_chauvinist", "chauvinism", "TRU_Nikita_Truman", 61),
        ):
            appointment = named_block(effects, effect_id)
            self.assertIn(f"ruling_party = {ruling_party}", appointment)
            self.assertIn(f"character = {character}", appointment)
            self.assertIn(f"ideology = {ruling_party}_ideology", appointment)
            self.assertNotIn("recruit_character", appointment)
            self.assertEqual(events.count(f"id = ADISCORD_vorkerland_collapse.{event_id}"), 1)
            self.assertIn(f"ADISCORD_vorkerland_collapse.{event_id} days = 1", startup)

    def test_joint_government_starts_with_reduced_frontier(self) -> None:
        effects = read("common/scripted_effects/ADISCORD_vorkerland_collapse_effects.txt")
        joint = named_block(effects, "ADISCORD_vorkerland_form_joint_government")

        self.assertIn("has_global_flag = ADISCORD_vorkerland_worker_rescued_by_vlad", joint)
        self.assertNotIn("annex_country = { target = VAD transfer_troops = yes }", joint)
        self.assertNotIn("transfer_state = 27", joint)
        self.assertNotIn("transfer_state = 82", joint)
        self.assertNotIn("transfer_state = 123", joint)
        self.assertNotIn("add_core_of = TVA", joint)

    def test_supplied_portraits_belong_to_country_leaders(self) -> None:
        characters = read("common/characters/ADISCORD_vorkerland_collapse_characters.txt")
        expected = {
            "EBA_Vlad_Mecra": "GFX_portrait_WRK_Vlad_Mecra",
            "TGD_Ted_Cuttle": "GFX_portrait_WRK_Ted_Cuttle",
            "IBA_Matvey_Mateusk": "GFX_portrait_IBA_Matvey_Mateusk",
            "IBL_Anton_Selevyostrov": "GFX_portrait_IBL_Anton_Selevyostrov",
            "WPA_Oliver_Larry_Gates": "GFX_portrait_WPA_Oliver_Larry_Gates",
            "DVA_Severin_Mark": "GFX_portrait_DVA_Severin_Mark",
            "EGC_Ruslan_Pike": "GFX_portrait_EGC_Ruslan_Pike",
            "WPS_Karim_Dol": "GFX_portrait_WPS_Karim_Dol",
            "PWR_Alexey_Lange": "GFX_Portrait_Forul_Generic_4",
            "SRA_Helio_Marr": "GFX_portrait_SRA_Helio_Marr",
            "ZTA_Viktor_Holt": "GFX_portrait_ZTA_Viktor_Holt",
            "RIV_Mikhail_Arsenyev": "GFX_portrait_RIV_Mikhail_Arsenyev",
            "REV_Elena_Rudenko": "GFX_portrait_REV_Elena_Rudenko",
            "YOR_Pavel_Korin": "GFX_portrait_YOR_Pavel_Korin",
            "NDN_Anna_Lind": "GFX_portrait_NDN_Anna_Lind",
            "SWB_Oskar_Renn": "GFX_portrait_SWB_Oskar_Renn",
            "VHV_Sergey_Melnik": "GFX_portrait_VHV_Sergey_Melnik",
            "OSV_Marina_Volkova": "GFX_portrait_OSV_Marina_Volkova",
        }
        for character, portrait in expected.items():
            block = named_block(characters, character)
            self.assertIn("country_leader", block, character)
            self.assertIn(portrait, block, character)
            self.assertNotIn("corps_commander", block, character)

    def test_civil_war_switches_all_requested_portraits(self) -> None:
        events = read("events/ADISCORD_vorkerland_collapse_events.txt")
        effects = read("common/scripted_effects/ADISCORD_vorkerland_collapse_effects.txt")
        for portrait in (
            "GFX_portrait_WRK_Nikita_Worcker_civilwar",
            "GFX_portrait_WRK_Vlad_Petrichev_civilwar",
            "GFX_portrait_ROM_Erwin_Von_Romanovskiy_civilwar",
            "GFX_portrait_TRU_Nikita_Truman_civilwar",
            "GFX_portrait_WRK_Temporary_Government",
        ):
            self.assertIn(portrait, events + effects)

    def test_dorian_worx_keeps_his_original_suited_identity_and_technocratic_state(self) -> None:
        characters = read("common/characters/ADISCORD_vorkerland_collapse_characters.txt")
        portraits = read("interface/ADISCORD_leader_portraits.gfx")
        collapse_effects = read("common/scripted_effects/ADISCORD_vorkerland_collapse_effects.txt")
        phase_effects = read("common/scripted_effects/ADISCORD_vorkerland_phase_effects.txt")
        recovery_en = read("localisation/english/ADISCORD_vorkerland_recovery_l_english.yml")
        recovery_ru = read("localisation/russian/ADISCORD_vorkerland_recovery_l_russian.yml")

        dorian = named_block(characters, "TVA_Dorian_Worx")
        self.assertIn("GFX_portrait_WRK_Dorian_Worx", dorian)
        self.assertIn("ideology = technocracy_ideology", dorian)
        self.assertRegex(
            portraits,
            r'(?s)name\s*=\s*"GFX_portrait_WRK_Dorian_Worx"'
            r'(?:(?!spriteType\s*=).)*portrait_WRK_Dorian_Worx\.png',
        )

        tva_setup = named_block(collapse_effects, "ADISCORD_vorkerland_setup_tva")
        for token in (
            "ruling_party = technocracy",
            "character = TVA_Dorian_Worx",
            "ideology = technocracy_ideology",
            "portrait = GFX_portrait_WRK_Dorian_Worx",
        ):
            self.assertIn(token, tva_setup)
        self.assertNotIn("ruling_party = utilitarism", tva_setup)
        self.assertNotIn("GFX_portrait_WRK_Anton_Bagley", tva_setup)

        formation = named_block(phase_effects, "ADISCORD_vorkerland_form_wrk_from_tva")
        for token in (
            "set_country_flag = ADISCORD_vorkerland_route_utilitarian",
            "drop_cosmetic_tag = yes",
            "ruling_party = technocracy",
            "character = TVA_Dorian_Worx",
            "ideology = technocracy_ideology",
        ):
            self.assertIn(token, formation)
        self.assertNotIn("ruling_party = utilitarism", formation)
        self.assertNotIn("set_cosmetic_tag = WRK_vorkerland_utilitarian_republic", formation)
        self.assertNotIn("GFX_portrait_WRK_Anton_Bagley", formation)
        self.assertIn("Control Dorian Worx's technical administration.", recovery_en)
        self.assertNotIn("Control the utilitarian directorate.", recovery_en)
        self.assertIn("Играть за техническую администрацию Дориана Воркса.", recovery_ru)
        self.assertNotIn("Играть за утилитарный директорат.", recovery_ru)
        self.assertIn(
            'WRK_technocracy: "Technocratic Republic of Vorkerland"',
            recovery_en,
        )
        self.assertIn(
            'WRK_technocracy: "Технократическая республика Воркерланда"',
            recovery_ru,
        )

    def test_worker_death_installs_cowboy_utilitarian_anton_bagley(self) -> None:
        effects = read("common/scripted_effects/ADISCORD_vorkerland_collapse_effects.txt")
        characters = read("common/characters/ADISCORD_vorkerland_collapse_characters.txt")
        portraits = read("interface/ADISCORD_leader_portraits.gfx")
        claimant_setup = named_block(effects, "ADISCORD_vorkerland_apply_claimant_cosmetics")
        wkr_setup = named_block(claimant_setup, "WKR")
        anton_path = named_block(wkr_setup, "else")
        successor = named_block(effects, "ADISCORD_vorkerland_promote_anton_bagley")
        phase_effects = read("common/scripted_effects/ADISCORD_vorkerland_phase_effects.txt")
        worker_formation = named_block(phase_effects, "ADISCORD_vorkerland_form_wrk_from_wkr")
        recovery_en = read("localisation/english/ADISCORD_vorkerland_recovery_l_english.yml")
        cosmetic_loc = read("localisation/russian/countries_l_russian.yml")

        self.assertIn("has_global_flag = ADISCORD_vorkerland_worker_safe_with_loyalists", claimant_setup)
        self.assertIn("GFX_portrait_WRK_Anton_Bagley", named_block(characters, "WRK_Anton_Bagley"))
        self.assertRegex(
            portraits,
            r'(?s)name\s*=\s*"GFX_portrait_WRK_Anton_Bagley"'
            r'(?:(?!spriteType\s*=).)*portrait_WRK_Anton_Bagley\.png',
        )
        self.assertIn("ruling_party = utilitarism", anton_path)
        self.assertIn("elections_allowed = no", anton_path)
        self.assertIn("set_cosmetic_tag = WRK_vorkerland_utilitarian_republic", anton_path)
        self.assertIn("portrait = GFX_portrait_WRK_Anton_Bagley", anton_path)
        self.assertIn("ideology = utilitarism_ideology", successor)
        for token in (
            "set_cosmetic_tag = WRK_vorkerland_utilitarian_republic",
            "ruling_party = utilitarism",
            "ADISCORD_vorkerland_promote_anton_bagley = yes",
        ):
            self.assertIn(token, worker_formation)
        self.assertIn(
            'WRK_vorkerland_utilitarian_republic: "Utilitarian Republic of Vorkerland"',
            recovery_en,
        )
        self.assertIn(
            'WRK_vorkerland_utilitarian_republic: "Утилитарная Республика Воркерланда"',
            cosmetic_loc,
        )
        for directory, size in (("", (82, 52)), ("medium", (41, 26)), ("small", (10, 7))):
            path = ROOT / "gfx" / "flags" / directory / "WRK_vorkerland_utilitarian_republic.tga"
            self.assertTrue(path.is_file(), path)
            with Image.open(path) as flag:
                self.assertEqual(flag.size, size, path)

    def test_vlad_keeps_imperial_identity_except_for_the_survivor_joint_government(self) -> None:
        effects = read("common/scripted_effects/ADISCORD_vorkerland_collapse_effects.txt")
        claimant_setup = named_block(effects, "ADISCORD_vorkerland_apply_claimant_cosmetics")
        vad_setup = named_block(claimant_setup, "VAD")
        joint = named_block(vad_setup, "if")
        imperial = named_block(vad_setup, "else")
        phase_effects = read("common/scripted_effects/ADISCORD_vorkerland_phase_effects.txt")
        formation = named_block(phase_effects, "ADISCORD_vorkerland_form_wrk_from_vad")
        characters = read("common/characters/ADISCORD_vorkerland_collapse_characters.txt")
        cosmetic_loc = read("localisation/russian/countries_l_russian.yml")

        self.assertIn("has_global_flag = ADISCORD_vorkerland_joint_government_formed", joint)
        self.assertIn("set_cosmetic_tag = WRK_vorkerland_joint_government", joint)
        self.assertIn("ADISCORD_vorkerland_appoint_joint_council = yes", joint)
        self.assertNotIn("VAD_vorkerland_restoration", joint)
        self.assertNotIn("GFX_portrait_WRK_Vlad_Petrichev_civilwar", joint)
        self.assertIn("set_cosmetic_tag = VAD_vorkerland_restoration", imperial)
        self.assertIn("portrait = GFX_portrait_WRK_Vlad_Petrichev_civilwar", imperial)
        self.assertIn("has_global_flag = ADISCORD_vorkerland_worker_rescued_by_vlad", formation)
        self.assertIn("set_cosmetic_tag = WRK_vorkerland_joint_government", formation)
        self.assertIn("set_cosmetic_tag = VAD_vorkerland_restoration", formation)
        self.assertIn("character = WRK_Vlad_Petrichev", formation)
        self.assertIn("GFX_portrait_WRK_Temporary_Government", named_block(characters, "WRK_VAD_Joint_Council"))
        self.assertIn('VAD_vorkerland_restoration: "Воркерландская Империя"', cosmetic_loc)

    def test_successor_ideologies_are_diverse(self) -> None:
        characters = read("common/characters/ADISCORD_vorkerland_collapse_characters.txt")
        ideologies = set(re.findall(r"ideology\s*=\s*([a-z_]+)_ideology", characters))
        self.assertTrue({"humanism", "etatism", "technocracy", "hedonism", "chauvinism", "pragmatism"} <= ideologies)

    def test_cultural_erasure_has_a_national_spirit(self) -> None:
        ideas = read("common/ideas/ADISCORD_vorkerland_collapse_ideas.txt")
        effects = read("common/scripted_effects/ADISCORD_vorkerland_collapse_effects.txt")
        loc = read("localisation/russian/ADISCORD_vorkerland_collapse_l_russian.yml")
        self.assertIn("ADISCORD_vorkerland_erased_nations", ideas)
        self.assertIn(
            "picture = generic_oppression",
            named_block(ideas, "ADISCORD_vorkerland_erased_nations"),
        )
        self.assertIn("Стёртые народы Империи", loc)
        prepare = named_block(effects, "ADISCORD_vorkerland_prepare_conflict_country")
        self.assertNotIn("add_ideas = ADISCORD_vorkerland_erased_nations", prepare)
        self.assertEqual(effects.count("add_ideas = ADISCORD_vorkerland_erased_nations"), 2)
        initial = named_block(effects, "ADISCORD_vorkerland_prepare_initial_combatants")
        self.assertRegex(initial, r"WKR\s*=\s*\{[^{}]*add_ideas\s*=\s*ADISCORD_vorkerland_erased_nations")

    def test_initial_partition_grants_owned_state_cores_once(self) -> None:
        effects = read("common/scripted_effects/ADISCORD_vorkerland_collapse_effects.txt")
        prepare = named_block(effects, "ADISCORD_vorkerland_prepare_conflict_country")
        self.assertEqual(prepare.count("every_owned_state"), 1)
        self.assertRegex(
            prepare,
            r"every_owned_state\s*=\s*\{\s*add_core_of\s*=\s*ROOT\s*\}",
        )

    def test_main_claimants_have_repeatable_wartime_decisions(self) -> None:
        decisions = read("common/decisions/ADISCORD_vorkerland_collapse_decisions.txt")
        ideas = read("common/ideas/ADISCORD_vorkerland_collapse_ideas.txt")
        expected = {
            "ADISCORD_vorkerland_wrk_activate_front_committees": ("WKR", "ADISCORD_vorkerland_wrk_front_committees"),
            "ADISCORD_vorkerland_wrk_requisition_rail_stock": ("WKR", "ADISCORD_vorkerland_wrk_rail_requisition"),
            "ADISCORD_vorkerland_vad_open_imperial_registers": ("VAD", "ADISCORD_vorkerland_vad_imperial_registers"),
            "ADISCORD_vorkerland_vad_form_field_commandantures": ("VAD", "ADISCORD_vorkerland_vad_field_commandantures"),
            "ADISCORD_vorkerland_tva_reroute_city_grid": ("TVA", "ADISCORD_vorkerland_tva_grid_rerouting"),
            "ADISCORD_vorkerland_tva_deploy_field_laboratories": ("TVA", "ADISCORD_vorkerland_tva_field_laboratories"),
        }
        for decision_id, (tag, spirit) in expected.items():
            block = named_block(decisions, decision_id)
            self.assertIn(f"allowed = {{ tag = {tag} }}", block, decision_id)
            self.assertIn("has_war = yes", block, decision_id)
            self.assertIn("fire_only_once = no", block, decision_id)
            self.assertIn("days_re_enable =", block, decision_id)
            self.assertIn(f"add_timed_idea = {{ idea = {spirit}", block, decision_id)
            self.assertIn(f"{spirit} = {{", ideas, spirit)
        vad_routes = {
            "ADISCORD_vorkerland_vad_open_imperial_registers": (
                "ADISCORD_vorkerland_focus_vad_registers_opened",
                "ADISCORD_vorkerland_focus_vad_commandantures_formed",
            ),
            "ADISCORD_vorkerland_vad_form_field_commandantures": (
                "ADISCORD_vorkerland_focus_vad_commandantures_formed",
                "ADISCORD_vorkerland_focus_vad_registers_opened",
            ),
        }
        for decision_id, (selected_flag, rejected_flag) in vad_routes.items():
            block = named_block(decisions, decision_id)
            for section_name in ("visible", "available"):
                section = named_block(block, section_name)
                self.assertIn(f"has_country_flag = {selected_flag}", section)
                self.assertIn(
                    f"NOT = {{ has_country_flag = {rejected_flag} }}", section
                )
        field_labs = named_block(
            decisions, "ADISCORD_vorkerland_tva_deploy_field_laboratories"
        )
        self.assertIn("army_experience = 5", field_labs)
        self.assertNotIn("add_army_experience", field_labs)

    def test_doctor_worx_starts_as_a_real_third_claimant(self) -> None:
        effects = read("common/scripted_effects/ADISCORD_vorkerland_collapse_effects.txt")
        ideas = read("common/ideas/ADISCORD_vorkerland_collapse_ideas.txt")
        setup = named_block(effects, "ADISCORD_vorkerland_setup_tva")
        for token in (
            "add_ideas = ADISCORD_vorkerland_tva_field_directorate",
            "add_ideas = ADISCORD_vorkerland_tva_ideological_fanaticism",
            "add_manpower = 11000",
            "type = infantry_equipment_0 amount = 1800 producer = TVA",
            "type = support_equipment amount = 120 producer = TVA",
            "type = artillery_equipment amount = 72 producer = TVA",
        ):
            self.assertIn(token, setup)
        directorate = named_block(ideas, "ADISCORD_vorkerland_tva_field_directorate")
        for modifier in (
            "research_speed_factor = 0.05",
            "industrial_capacity_factory = 0.10",
            "army_org_factor = 0.06",
            "supply_consumption_factor = -0.08",
        ):
            self.assertIn(modifier, directorate)
        fanaticism = named_block(ideas, "ADISCORD_vorkerland_tva_ideological_fanaticism")
        for modifier in (
            "surrender_limit = 0.25",
            "war_support_factor = 0.10",
            "army_org_regain = 0.05",
        ):
            self.assertIn(modifier, fanaticism)
        state_36 = read("history/states/36-36.txt")
        self.assertRegex(state_36, r"victory_points\s*=\s*\{\s*12227\s+60\s*\}")

        decisions = read("common/decisions/ADISCORD_vorkerland_collapse_decisions.txt")
        battalions = named_block(decisions, "ADISCORD_vorkerland_tva_raise_technical_battalions")
        self.assertEqual(battalions.count("create_unit ="), 4)
        self.assertIn("36 = {", battalions)
        self.assertIn("owner = WPS", battalions)
        self.assertIn("owner = TGD", battalions)
        wrk_cells = named_block(decisions, "ADISCORD_vorkerland_tva_infiltrate_wrk_rear")
        vad_cells = named_block(decisions, "ADISCORD_vorkerland_tva_infiltrate_vad_rear")
        for state in (33, 34):
            self.assertIn(f"{state} = {{", wrk_cells)
        for state in (75, 106):
            self.assertIn(f"{state} = {{", vad_cells)
        for island in (200, 201):
            self.assertNotIn(f"{island} = {{", wrk_cells)

    def test_regional_winners_can_join_a_main_claimant_as_puppets(self) -> None:
        decisions = read("common/decisions/ADISCORD_vorkerland_collapse_decisions.txt")
        expected = {
            "ADISCORD_vorkerland_tva_integrate_wps": ("TVA", "WPS", "196"),
            "ADISCORD_vorkerland_tva_integrate_tgd": ("TVA", "TGD", "105"),
        }
        for decision_id, (claimant, target, state) in expected.items():
            block = named_block(decisions, decision_id)
            self.assertIn(f"allowed = {{ tag = {claimant} }}", block, decision_id)
            self.assertIn(f"controls_state = {state}", block, decision_id)
            self.assertIn(f"puppet = {target}", block, decision_id)
            autonomy = "autonomy_district_in_Vorkerland" if target == "VLA" else "autonomy_puppet"
            self.assertIn(f"set_autonomy = {{ target = {target} autonomy_state = {autonomy}", block, decision_id)

    def test_btl_and_kefreyt_choose_only_one_claimant_to_support(self) -> None:
        decisions = read("common/decisions/ADISCORD_vorkerland_collapse_decisions.txt")
        ideas = read("common/ideas/ADISCORD_vorkerland_collapse_ideas.txt")
        for patron, flag, spirit, rifles in (
            ("btl", "ADISCORD_vorkerland_btl_contract_signed", "ADISCORD_vorkerland_btl_contract_support", "250"),
            ("val", "ADISCORD_vorkerland_val_contract_signed", "ADISCORD_vorkerland_val_contract_support", "400"),
        ):
            self.assertIn(f"{spirit} = {{", ideas)
            for claimant in ("wrk", "vad", "tva"):
                decision_id = f"ADISCORD_vorkerland_{patron}_support_{claimant}"
                block = named_block(decisions, decision_id)
                self.assertIn(f"NOT = {{ has_global_flag = {flag} }}", block, decision_id)
                self.assertIn(f"set_global_flag = {flag}", block, decision_id)
                self.assertIn(f"add_ideas = {spirit}", block, decision_id)
                self.assertIn(f"amount = {rifles}", block, decision_id)
                if patron == "val":
                    self.assertIn("type = support_equipment amount = 60 producer = VAL", block)
                else:
                    self.assertIn("add_ideas = ADISCORD_vorkerland_btl_volunteer_contract", block)
                    self.assertIn(f"ADISCORD_vorkerland_btl_supports_{claimant}", block)
        btl_contract = named_block(ideas, "ADISCORD_vorkerland_btl_volunteer_contract")
        self.assertIn("can_send_volunteers = yes", btl_contract)
        self.assertIn("send_volunteer_divisions_required = -0.90", btl_contract)
        self.assertIn(
            'BTL_Paul_Dorini: "Пауль Дорини"',
            read("localisation/russian/countries_l_russian.yml"),
        )

    def test_fallback_spirit_pictures_use_registered_idea_sprites(self) -> None:
        ideas = read("common/ideas/ADISCORD_vorkerland_collapse_ideas.txt")
        mission = named_block(
            ideas, "ADISCORD_vorkerland_piv_macri_volunteer_mission"
        )
        self.assertIn("picture = generic_volunteer_expedition_bonus", mission)

    def test_selected_sides_have_unique_moderate_spirits(self) -> None:
        ideas = read("common/ideas/ADISCORD_vorkerland_collapse_ideas.txt")
        effects = read("common/scripted_effects/ADISCORD_vorkerland_collapse_effects.txt")
        decisions = read("common/decisions/ADISCORD_vorkerland_collapse_decisions.txt")
        loc = read("localisation/russian/ADISCORD_vorkerland_collapse_l_russian.yml")
        spirits = (
            "ADISCORD_vorkerland_vad_imperial_chancery",
            "ADISCORD_vorkerland_republics_from_the_ruins",
            "ADISCORD_vorkerland_mobilized_periphery",
            "ADISCORD_vorkerland_tgd_living_grid",
            "ADISCORD_vorkerland_eba_free_quays",
            "ADISCORD_vorkerland_zta_golden_river_order",
            "ADISCORD_vorkerland_wpa_municipal_compact",
            "ADISCORD_vorkerland_wps_factory_councils",
        )
        for spirit in spirits:
            block = named_block(ideas, spirit)
            self.assertIn("picture =", block, spirit)
            self.assertIn("modifier =", block, spirit)
            self.assertIn(f"add_ideas = {spirit}", effects + decisions, spirit)
            self.assertIn(f" {spirit}:", loc, spirit)
            self.assertIn(f" {spirit}_desc:", loc, spirit)

    def test_collapse_spirit_cleanup_is_tag_guarded_and_has_replacements(self) -> None:
        effects = read("common/scripted_effects/ADISCORD_vorkerland_collapse_effects.txt")
        prepare = named_block(effects, "ADISCORD_vorkerland_prepare_conflict_country")
        self.assertNotIn("every_country", prepare)
        self.assertNotIn("every_other_country", prepare)
        self.assertNotIn("swap_ideas", prepare)
        self.assertEqual(
            set(re.findall(r"remove_ideas\s*=\s*([A-Za-z0-9_]+)", prepare)),
            {
                "WRK_ashes_of_the_crown",
                "WRK_hourglass_of_discord",
                "WRK_constitution_of_the_republic",
                "VLA_national_spirit",
                "ADISCORD_vorkerland_erased_nations",
            },
        )
        for tag in (
            "WRK", "VAD", "VLA", "ZAO", "PWR", "ROM", "SOL", "TRU",
            "TVA", "EYR", "EGC", "RIV", "REV", "YOR", "NDN", "SWB", "VHV", "OSV", "PSD", "DVA", "SRA", "IBL", "IBA",
        ):
            self.assertIn(f"tag = {tag}", prepare, tag)
        self.assertIn("add_ideas = ADISCORD_vorkerland_republics_from_the_ruins", prepare)
        self.assertIn("add_ideas = ADISCORD_vorkerland_mobilized_periphery", prepare)

    def test_collapse_runtime_cannot_remove_unrelated_national_spirits(self) -> None:
        paths = (
            "common/scripted_effects/ADISCORD_vorkerland_collapse_effects.txt",
            "common/scripted_effects/ADISCORD_vorkerland_collapse_map_effects.txt",
            "common/on_actions/01_ADISCORD_vorkerland_collapse_on_actions.txt",
            "events/ADISCORD_vorkerland_collapse_events.txt",
            "common/decisions/ADISCORD_vorkerland_collapse_decisions.txt",
        )
        runtime = "\n".join(read(path) for path in paths)
        removals = set(re.findall(r"remove_ideas\s*=\s*([A-Za-z0-9_]+)", runtime))
        self.assertEqual(
            removals,
            {
                "WRK_ashes_of_the_crown",
                "WRK_hourglass_of_discord",
                "WRK_constitution_of_the_republic",
                "WRK_birthplace_of_the_first_revolution",
                "WRK_birthplace_of_the_first_revolution_front_republic",
                "VLA_national_spirit",
                "ADISCORD_vorkerland_erased_nations",
                "ADISCORD_vorkerland_piv_macri_volunteer_mission",
                "ADISCORD_vorkerland_tgd_grid_collapse",
                "ADISCORD_vorkerland_erased_nations_relief_1",
                "ADISCORD_vorkerland_erased_nations_relief_2",
                "ADISCORD_vorkerland_republics_from_the_ruins",
                "ADISCORD_vorkerland_tva_field_directorate",
                "ADISCORD_vorkerland_tva_field_directorate_2",
                "ADISCORD_vorkerland_ivanland_expeditionary_command",
                "ADISCORD_vorkerland_northern_defense_front",
            },
        )
        for spirit in (
            "IVN_national_spirit", "RUS_national_spirit", "PIV_national_spirit",
            "NAM_national_spirit", "NOD_home_of_hedonist_revolution",
            "STP_hedonism_with_no_bondaries", "VAL_worldwide_famous_weponry",
        ):
            self.assertNotIn(spirit, removals)

    def test_new_leaders_have_names_but_no_game_biographies(self) -> None:
        characters = read("common/characters/ADISCORD_vorkerland_collapse_characters.txt")
        loc = read("localisation/russian/ADISCORD_vorkerland_collapse_l_russian.yml")
        self.assertNotRegex(characters, r"\bdesc\s*=\s*[A-Za-z0-9_]+_desc\b")
        for leader in re.findall(r"(?m)^\s*([A-Z]{3}_[A-Za-z0-9_]+)\s*=", characters):
            self.assertNotIn(f"{leader}_desc:", loc, leader)
        self.assertIn("ZTA_Viktor_Holt", characters)
        self.assertIn("GFX_portrait_ZTA_Viktor_Holt", characters)
        self.assertNotIn("ZTA_Vera_Holt", characters + loc)


class InterventionAndVisualTests(unittest.TestCase):
    def test_krait_is_led_by_selevyostrov_before_and_after_puppeting(self) -> None:
        effects = read("common/scripted_effects/ADISCORD_vorkerland_collapse_effects.txt")
        appointment = named_block(effects, "ADISCORD_vorkerland_appoint_selevyostrov")
        setup = named_block(effects, "ADISCORD_vorkerland_setup_ibl")
        events = read("events/ADISCORD_vorkerland_collapse_events.txt")
        repair = re.search(
            r"(?ms)^country_event\s*=\s*\{\s*id\s*=\s*ADISCORD_vorkerland_collapse\.42\b"
            r"(.*?)(?=^country_event\s*=\s*\{|^add_namespace\s*=|\Z)",
            events,
        )
        on_actions = read("common/on_actions/01_ADISCORD_vorkerland_collapse_on_actions.txt")
        startup = named_block(on_actions, "on_startup")
        monthly = named_block(on_actions, "on_monthly")

        for token in (
            "ruling_party = chauvinism",
            "promote_character = {",
            "character = IBL_Anton_Selevyostrov",
            "ideology = chauvinism_ideology",
            "portrait = GFX_portrait_IBL_Anton_Selevyostrov",
            "ADISCORD_vorkerland_selevyostrov_character_repair_v1",
        ):
            self.assertIn(token, appointment)
        self.assertNotIn("create_country_leader", appointment)
        self.assertNotIn("recruit_character", appointment)
        self.assertIn("ADISCORD_vorkerland_appoint_selevyostrov = yes", setup)
        self.assertIn("ADISCORD_vorkerland_collapse.42 days = 1", setup)
        self.assertIn("ADISCORD_vorkerland_collapse.42 days = 1", startup)
        self.assertNotIn("ADISCORD_vorkerland_appoint_selevyostrov = yes", monthly)
        self.assertIsNotNone(repair)
        self.assertIn("character = IBL_Anton_Selevyostrov", repair.group(1))
        self.assertIn("ruling_only = yes", repair.group(1))
        self.assertIn("ADISCORD_vorkerland_appoint_selevyostrov = yes", repair.group(1))

    def test_ivanland_puppet_is_led_by_mateusk(self) -> None:
        effects = read("common/scripted_effects/ADISCORD_vorkerland_collapse_effects.txt")
        mandate = named_block(effects, "ADISCORD_vorkerland_setup_ivanland_mandate")
        appointment = named_block(effects, "ADISCORD_vorkerland_appoint_mateusk")
        on_actions = read("common/on_actions/01_ADISCORD_vorkerland_collapse_on_actions.txt")
        startup = named_block(on_actions, "on_startup")
        monthly = named_block(on_actions, "on_monthly")
        events = read("events/ADISCORD_vorkerland_collapse_events.txt")
        repair = re.search(
            r"(?ms)^country_event\s*=\s*\{\s*id\s*=\s*ADISCORD_vorkerland_collapse\.40\b"
            r"(.*?)(?=^country_event\s*=\s*\{|^add_namespace\s*=|\Z)",
            events,
        )

        self.assertIn("puppet = IBA", mandate)
        self.assertIn("ADISCORD_vorkerland_appoint_mateusk = yes", mandate)
        self.assertGreater(
            mandate.find("ADISCORD_vorkerland_appoint_mateusk = yes"),
            mandate.find("puppet = IBA"),
        )
        self.assertIn("ADISCORD_vorkerland_collapse.40 days = 1", mandate)
        self.assertNotIn("create_country_leader", appointment)
        self.assertNotIn("recruit_character", appointment)
        self.assertIn("promote_character", appointment)
        self.assertIn("character = IBA_Matvey_Mateusk", appointment)
        self.assertIn("portrait = GFX_portrait_IBA_Matvey_Mateusk", appointment)
        self.assertIn("ideology = pragmatism_ideology", appointment)
        self.assertIn("ADISCORD_vorkerland_mateusk_character_repair_v2", appointment)
        self.assertNotIn("ADISCORD_vorkerland_appoint_mateusk = yes", monthly)
        self.assertIn("ADISCORD_vorkerland_collapse.40 days = 1", startup)
        self.assertIsNotNone(repair)
        self.assertIn("ADISCORD_vorkerland_appoint_mateusk = yes", repair.group(1))
        self.assertIn("ADISCORD_vorkerland_end_ivanland_intervention_wars = yes", repair.group(1))
        self.assertIn("character = IBA_Matvey_Mateusk", repair.group(1))
        self.assertIn("ruling_only = yes", repair.group(1))

    def test_ivanland_front_launch_is_postcondition_verified_and_bounded(self) -> None:
        events = read("events/ADISCORD_vorkerland_collapse_events.txt")
        effects = read("common/scripted_effects/ADISCORD_vorkerland_collapse_effects.txt")
        triggers = read("common/scripted_triggers/ADISCORD_vorkerland_collapse_triggers.txt")
        on_actions = read("common/on_actions/01_ADISCORD_vorkerland_collapse_on_actions.txt")

        cache_event = event_block(events, "ADISCORD_vorkerland_collapse.77")
        launch = named_block(effects, "ADISCORD_vorkerland_open_ivanland_intervention_front")
        verifier_call = "country_event = { id = ADISCORD_vorkerland_collapse.82 days = 1 }"
        self.assertIn("ADISCORD_vorkerland_open_ivanland_intervention_front = yes", cache_event)
        self.assertIn(
            "clr_country_flag = ADISCORD_vorkerland_ivanland_front_launch_pending",
            launch,
        )
        self.assertIn(
            "set_country_flag = { flag = ADISCORD_vorkerland_ivanland_front_verification_pending days = 3 }",
            launch,
        )
        self.assertIn(verifier_call, launch)
        with self.assertRaises(AssertionError):
            event_block(events, "ADISCORD_vorkerland_collapse.79")

        postcondition = named_block(
            triggers, "ADISCORD_vorkerland_ivanland_intervention_front_verified"
        )
        self.assertIn("tag = IVN", postcondition)
        self.assertIn("has_war_with = PWR", postcondition)
        for defender in ("ZAO", "WPA", "WPS", "PSD"):
            self.assertIn(
                f"OR = {{ NOT = {{ country_exists = {defender} }} "
                f"{defender} = {{ is_subject = yes }} "
                f"{defender} = {{ has_capitulated = yes }} "
                f"{defender} = {{ has_war_with = IVN }} }}",
                postcondition,
            )
        for state in (90, 91, 93, 94):
            self.assertIn(
                f"{state} = {{ controller = {{ OR = {{ tag = IVN has_war_with = IVN }} }} }}",
                postcondition,
            )

        verifier = event_block(events, "ADISCORD_vorkerland_collapse.82")
        self.assertIn(
            "limit = { ADISCORD_vorkerland_ivanland_intervention_front_verified = yes }",
            verifier,
        )
        war_retry = "ADISCORD_vorkerland_ivanland_front_war_retry"
        join_retry = "ADISCORD_vorkerland_ivanland_front_join_retry"
        self.assertEqual(verifier.count(f"set_country_flag = {war_retry}"), 1)
        self.assertIn(f"NOT = {{ has_country_flag = {war_retry} }}", verifier)
        self.assertEqual(
            verifier.count(
                "declare_war_on = { target = PWR type = take_state_focus generator = { 90 91 } }"
            ),
            1,
        )
        self.assertEqual(verifier.count(f"set_country_flag = {join_retry}"), 1)
        self.assertIn(f"NOT = {{ has_country_flag = {join_retry} }}", verifier)
        live_join_guard = (
            "exists = yes is_subject = no NOT = { has_capitulated = yes } "
            "NOT = { has_war_with = IVN }"
        )
        for defender in ("ZAO", "WPA", "WPS", "PSD"):
            defender_scope = named_block(verifier, defender)
            self.assertIn(live_join_guard, defender_scope)
            self.assertIn(
                "targeted_alliance = PWR enemy = IVN hostility_reason = asked_to_join",
                defender_scope,
            )
        self.assertEqual(verifier.count(verifier_call), 2)
        self.assertEqual(
            verifier.count("ADISCORD_vorkerland_ivanland_intervention_failure = yes"),
            3,
        )

        startup = named_block(on_actions, "on_startup")
        verifier_index = startup.find(verifier_call)
        ivn_scope_start = startup.rfind("IVN = {", 0, verifier_index)
        startup_bridge = named_block(startup[ivn_scope_start:], "IVN")
        for token in (
            "NOT = { has_country_flag = ADISCORD_vorkerland_ivanland_front_verified_v1 }",
            "NOT = { has_country_flag = ADISCORD_vorkerland_ivanland_front_launch_pending }",
            "NOT = { has_country_flag = ADISCORD_vorkerland_ivanland_front_verification_pending }",
            "set_country_flag = { flag = ADISCORD_vorkerland_ivanland_front_verification_pending days = 3 }",
            verifier_call,
        ):
            self.assertIn(token, startup_bridge)

        cleanup = named_block(effects, "ADISCORD_vorkerland_end_ivanland_intervention_wars")
        cleanup_ivn = named_block(cleanup, "IVN")
        for flag in (
            "ADISCORD_vorkerland_ivanland_front_launch_pending",
            "ADISCORD_vorkerland_ivanland_front_verification_pending",
            war_retry,
            join_retry,
            "ADISCORD_vorkerland_ivanland_front_verified_v1",
        ):
            self.assertIn(f"clr_country_flag = {flag}", cleanup_ivn)
        for defender in ("PWR", "ZAO", "WPA", "WPS", "PSD"):
            self.assertIn(
                "remove_ideas = ADISCORD_vorkerland_northern_defense_front",
                named_block(cleanup, defender),
            )

    def test_ivanland_keeps_krait_and_norvane_as_separate_puppets(self) -> None:
        decisions = read("common/decisions/ADISCORD_vorkerland_collapse_decisions.txt")
        preparation = named_block(
            decisions, "ADISCORD_ivanland_prepare_northern_expedition"
        )
        self.assertIn("has_global_flag = ADISCORD_vorkerland_ivanland_planning_unlocked_v4", preparation)
        self.assertIn("available = { ADISCORD_ivanland_intervention_start_ready = yes }", preparation)
        self.assertIn("cost = 75", preparation)
        self.assertIn("days_remove = 120", preparation)
        self.assertIn("civilian_factory_use = 2", preparation)
        self.assertIn(
            "ADISCORD_vorkerland_activate_ivanland_intervention_mission = yes",
            named_block(preparation, "remove_effect"),
        )

        mission = named_block(decisions, "ADISCORD_ivanland_limited_intervention")
        self.assertIn("activation = { always = no }", mission)
        self.assertIn("available = { always = no }", mission)
        self.assertIn("selectable_mission = no", mission)
        self.assertIn("days_mission_timeout = 240", mission)
        cancel_trigger = named_block(mission, "cancel_trigger")
        cancel_effect = named_block(mission, "cancel_effect")
        self.assertIn("has_capitulated = yes", cancel_trigger)
        self.assertNotIn("NOT = { has_war_with = PWR }", cancel_trigger)
        self.assertIn("ADISCORD_vorkerland_ivanland_intervention_success = yes", cancel_effect)
        self.assertIn("ADISCORD_vorkerland_ivanland_intervention_failure = yes", cancel_effect)
        self.assertIn(
            "timeout_effect = { ADISCORD_vorkerland_ivanland_intervention_failure = yes }",
            mission,
        )
        effects = read("common/scripted_effects/ADISCORD_vorkerland_collapse_effects.txt")
        activation = named_block(
            effects, "ADISCORD_vorkerland_activate_ivanland_intervention_mission"
        )
        intervention_start = named_block(effects, "ADISCORD_vorkerland_begin_ivanland_intervention")
        for token in (
            "set_global_flag = ADISCORD_vorkerland_ivanland_intervention_active",
            "add_timed_idea = { idea = ADISCORD_vorkerland_ivanland_expeditionary_command days = 260 }",
            "activate_mission = ADISCORD_ivanland_limited_intervention",
            "ADISCORD_vorkerland_begin_ivanland_intervention = yes",
        ):
            self.assertIn(token, activation)
        self.assertNotIn("ADISCORD_vorkerland_begin_ivanland_intervention = yes", mission)
        self.assertIn("ADISCORD_vorkerland_restore_pwr_psd", intervention_start)
        self.assertIn("ADISCORD_vorkerland_collapse.77 days = 1", intervention_start)
        self.assertNotIn("declare_war_on =", intervention_start)
        self.assertNotIn("puppet = IBL", intervention_start)
        self.assertNotIn("puppet = IBA", intervention_start)
        for state in (90, 91, 93, 94):
            self.assertIn(f"controls_state = {state}", mission)
        cache_event = event_block(events := read("events/ADISCORD_vorkerland_collapse_events.txt"), "ADISCORD_vorkerland_collapse.77")
        self.assertIn("ADISCORD_vorkerland_open_ivanland_intervention_front = yes", cache_event)
        intervention_front = named_block(
            effects, "ADISCORD_vorkerland_open_ivanland_intervention_front"
        )
        self.assertIn(
            "target = PWR type = take_state_focus generator = { 90 91 }",
            intervention_front,
        )
        for member in ("ZAO", "WPA", "WPS", "PSD"):
            self.assertIn(f"add_to_faction = {member}", intervention_front)
        self.assertNotIn("target = IBL", intervention_front)
        self.assertNotIn("target = IBA", intervention_front)
        mandate = named_block(effects, "ADISCORD_vorkerland_setup_ivanland_mandate")
        krait_setup = named_block(effects, "ADISCORD_vorkerland_setup_ibl")
        krait_expansion = named_block(effects, "ADISCORD_vorkerland_expand_krait_client")
        self.assertEqual(mandate.count("puppet ="), 1)
        self.assertIn("puppet = IBA", mandate)
        self.assertNotIn("set_nationality = IBA", mandate)
        self.assertNotIn("add_country_leader_role", mandate)
        self.assertIn("ADISCORD_vorkerland_appoint_mateusk = yes", mandate)
        self.assertIn("71 = { add_claim_by = IBA }", mandate)
        appointment = named_block(effects, "ADISCORD_vorkerland_appoint_mateusk")
        self.assertIn("ADISCORD_vorkerland_mateusk_character_repair_v2", appointment)
        self.assertNotIn("create_country_leader", appointment)
        self.assertNotIn("recruit_character", appointment)
        self.assertIn("promote_character", appointment)
        self.assertIn("portrait = GFX_portrait_IBA_Matvey_Mateusk", appointment)
        self.assertEqual(set(re.findall(r"transfer_state\s*=\s*(\d+)", mandate)), {"90", "91"})
        self.assertIn("91 = { remove_core_of = IBL add_core_of = IBA", mandate)
        self.assertEqual(set(re.findall(r"transfer_state\s*=\s*(\d+)", krait_setup)), {"93", "94"})
        self.assertIn("puppet = IBL", krait_setup)
        self.assertIn("ADISCORD_vorkerland_appoint_selevyostrov = yes", krait_setup)
        self.assertIn("ADISCORD_vorkerland_setup_ibl = yes", mandate)
        self.assertIn("ADISCORD_vorkerland_setup_ibl = yes", krait_expansion)
        self.assertNotIn("transfer_state = 71", mandate)
        ivn_history = read("history/countries/IVN - IvanLand.txt")
        iba_history = read("history/countries/IBA - Ivanland Northern Mandate.txt")
        self.assertNotIn("recruit_character = IBA_Matvey_Mateusk", ivn_history)
        self.assertIn("recruit_character = IBA_Matvey_Mateusk", iba_history)
        focus = read("common/national_focus/ADISCORD_vorkerland_collapse_focus.txt")
        self.assertIn("tag = IBA", focus)
        self.assertIn("id = IBA_organize_transitional_council", focus)
        self.assertNotIn("GFX_goal_unknown", focus)
        english_focus_loc = read("localisation/english/ADISCORD_vorkerland_collapse_l_english.yml")
        self.assertIn("IBA_organize_transitional_council:", english_focus_loc)
        self.assertIn("IBA_organize_transitional_council_desc:", english_focus_loc)
        success = named_block(effects, "ADISCORD_vorkerland_ivanland_intervention_success")
        self.assertGreaterEqual(success.count("ADISCORD_vorkerland_end_ivanland_intervention_wars = yes"), 2)
        self.assertIn("NOT = { has_global_flag = ADISCORD_vorkerland_ivanland_intervention_resolved }", success)
        self.assertIn("Ivanland intervention resolved: SUCCESS", success)
        self.assertIn("clr_global_flag = ADISCORD_vorkerland_ivanland_intervention_failed", success)
        failure = named_block(effects, "ADISCORD_vorkerland_ivanland_intervention_failure")
        self.assertIn("NOT = { has_global_flag = ADISCORD_vorkerland_ivanland_intervention_resolved }", failure)
        self.assertIn("ruling_party = etatism", failure)
        self.assertIn("GFX_portrait_IVN_Vadim_Ivanchik_after_retreat", failure)
        self.assertIn("annex_country = { target = IBA", failure)
        self.assertIn("PWR = { transfer_state = 90 transfer_state = 91 }", failure)
        self.assertIn("PSD = { transfer_state = 93 transfer_state = 94 }", failure)
        self.assertIn("91 = { remove_core_of = IBA", failure)
        self.assertIn("91 = { add_core_of = PWR set_state_controller_to = PWR }", failure)
        self.assertIn("93 = { set_state_controller_to = PSD }", failure)
        self.assertIn("94 = { set_state_controller_to = PSD }", failure)
        self.assertIn("ADISCORD_vorkerland_vadim_etatist_role_added", failure)
        self.assertIn("Ivanland intervention resolved: FAILURE", failure)
        self.assertIn("clr_global_flag = ADISCORD_vorkerland_ivanland_intervention_succeeded", failure)
        on_actions = read("common/on_actions/01_ADISCORD_vorkerland_collapse_on_actions.txt")
        capitulation = named_block(on_actions, "on_capitulation")
        self.assertIn("set_global_flag = skip_default_capitulation", capitulation)
        self.assertIn("tag = PWR", capitulation)
        self.assertIn("ROOT = { tag = IVN }", capitulation)
        self.assertIn("ADISCORD_vorkerland_ivanland_intervention_success = yes", capitulation)
        self.assertIn("ADISCORD_vorkerland_ivanland_intervention_failure = yes", capitulation)
        self.assertIn("IVN = { white_peace = ROOT }", capitulation)

    def test_late_ivanland_and_frealor_interventions_are_one_shot_and_state_bound(self) -> None:
        decisions = read("common/decisions/ADISCORD_vorkerland_collapse_decisions.txt")
        effects = read("common/scripted_effects/ADISCORD_vorkerland_collapse_effects.txt")
        maps = read("common/scripted_effects/ADISCORD_vorkerland_collapse_map_effects.txt")
        on_actions = read("common/on_actions/01_ADISCORD_vorkerland_collapse_on_actions.txt")
        ai = read("common/ai_strategy/ADISCORD_vorkerland_collapse_ai.txt")

        second = named_block(decisions, "ADISCORD_ivanland_second_intervention")
        self.assertEqual(second.count("value = 100"), 3)
        self.assertIn("NOT = { country_exists = TVA }", second)
        self.assertIn("WKR = {", second)
        self.assertIn("VAD = {", second)
        self.assertEqual(second.count("declare_war_on ="), 2)
        self.assertNotIn("add_to_war", second)
        self.assertIn("target = PSD", second)
        self.assertIn("target = PWR", second)

        islands = named_block(decisions, "ADISCORD_ivanland_occupy_wrk_islands")
        self.assertIn("cost = 50", islands)
        self.assertIn("NOT = { has_war_with = WKR }", islands)
        self.assertIn("transfer_state = 200", islands)
        self.assertIn("transfer_state = 201", islands)

        zao = named_block(effects, "ADISCORD_vorkerland_ivanland_secure_zaozersk")
        self.assertIn("NOT = { country_exists = ZAO }", zao)
        self.assertIn("release_autonomy =", zao)
        self.assertIn("puppet = ZAO", zao)
        self.assertIn("transfer_state = 72", zao)
        success = named_block(effects, "ADISCORD_vorkerland_ivanland_intervention_success")
        self.assertIn("ADISCORD_vorkerland_ivanland_secure_zaozersk = yes", success)
        self.assertIn("ADISCORD_vorkerland_ivanland_secure_zaozersk = yes", named_block(on_actions, "on_startup"))

        frealor = named_block(decisions, "ADISCORD_vorkerland_rom_northern_intervention")
        self.assertIn("is_subject = no", frealor)
        self.assertIn("has_war = no", frealor)
        self.assertIn("generator = { 72 }", frealor)
        self.assertIn("generator = { 196 322 }", frealor)
        self.assertEqual(frealor.count("declare_war_on ="), 2)
        frealor_success = named_block(effects, "ADISCORD_vorkerland_rom_northern_intervention_success")
        for state in (72, 196, 322):
            self.assertIn(f"transfer_state = {state}", frealor_success)

        guarantee = named_block(decisions, "ADISCORD_ivanland_guarantee_free_republics")
        self.assertIn("cost = 100", guarantee)
        self.assertIn("ROM = { is_neighbor_of = ROOT }", guarantee)
        self.assertIn("country = ROM relation = guarantee", guarantee)
        self.assertIn("country = TRU relation = guarantee", guarantee)
        settlement = named_block(effects, "ADISCORD_vorkerland_resolve_unguaranteed_free_republics")
        self.assertEqual(settlement.count("random_list ="), 2)
        self.assertIn("puppet = ROM", settlement)
        self.assertIn("puppet = TRU", settlement)
        self.assertIn("target = ROM type = annex_everything", settlement)
        self.assertIn("target = TRU type = annex_everything", settlement)
        phase = read("common/scripted_effects/ADISCORD_vorkerland_phase_effects.txt")
        finalizer = named_block(phase, "ADISCORD_vorkerland_finalize_reunified_wrk")
        self.assertIn("ADISCORD_vorkerland_resolve_unguaranteed_free_republics = yes", finalizer)
        for route in ("worker", "vlad", "dorian"):
            outcome = named_block(maps, f"ADISCORD_vorkerland_apply_{route}_map")
            self.assertIn("ADISCORD_vorkerland_begin_reunification = yes", outcome)
            self.assertNotIn("ADISCORD_vorkerland_central_war_finished", outcome)
            self.assertNotIn("ADISCORD_vorkerland_collapse_finished", outcome)
            self.assertNotIn("victory_superevent = yes", outcome)
            self.assertNotIn("ADISCORD_vorkerland_split_external_gate = yes", outcome)

        for key in (
            "ADISCORD_vorkerland_ivn_second_front_psd",
            "ADISCORD_vorkerland_ivn_second_front_pwr",
            "ADISCORD_vorkerland_rom_intervention_front_zao",
            "ADISCORD_vorkerland_rom_intervention_front_wps",
        ):
            self.assertIn("front_control", named_block(ai, key), key)

    def test_ivanland_outcome_news_has_one_guarded_immediate_route(self) -> None:
        effects = read("common/scripted_effects/ADISCORD_vorkerland_collapse_effects.txt")
        events = read("events/ADISCORD_vorkerland_collapse_events.txt")
        loc = read("localisation/russian/events_l_russian.yml")
        routes = (
            (
                "ADISCORD_vorkerland_news.1",
                named_block(effects, "ADISCORD_vorkerland_ivanland_intervention_success"),
                "ADISCORD_vorkerland_ivanland_success_news_shown",
                "ADISCORD_vorkerland_setup_ivanland_mandate = yes",
            ),
            (
                "ADISCORD_vorkerland_news.2",
                named_block(effects, "ADISCORD_vorkerland_ivanland_intervention_failure"),
                "ADISCORD_vorkerland_ivanland_failure_news_shown",
                "portrait = GFX_portrait_IVN_Vadim_Ivanchik_after_retreat",
            ),
        )
        for news_id, outcome, shown_flag, completion in routes:
            self.assertEqual(events.count(f"id = {news_id}"), 1, news_id)
            self.assertEqual(effects.count(f"news_event = {{ id = {news_id} }}"), 1, news_id)
            definition = re.search(
                rf"(?ms)^news_event\s*=\s*\{{\s*id\s*=\s*{re.escape(news_id)}\b"
                rf"(.*?)(?=^news_event\s*=\s*\{{|\Z)",
                events,
            )
            self.assertIsNotNone(definition, news_id)
            for token in ("major = yes", "is_triggered_only = yes", "fire_only_once = yes"):
                self.assertIn(token, definition.group(1), news_id)
            self.assertNotIn("hidden = yes", definition.group(1), news_id)
            self.assertIn(f"NOT = {{ has_global_flag = {shown_flag} }}", outcome, news_id)
            self.assertIn(f"set_global_flag = {shown_flag}", outcome, news_id)
            self.assertLess(outcome.find(completion), outcome.find(f"news_event = {{ id = {news_id} }}"), news_id)
            call = named_block(outcome, "news_event")
            for delayed in ("hours =", "days =", "random_hours", "random_days"):
                self.assertNotIn(delayed, call, news_id)
            for suffix in ("t", "d", "a"):
                self.assertIn(f"  {news_id}.{suffix}:", loc, news_id)

    def test_legacy_diplomacy_bypasses_are_owned_by_the_focus_flow(self) -> None:
        collapse = read("common/decisions/ADISCORD_vorkerland_collapse_decisions.txt")
        diplomacy = read("common/decisions/ADISCORD_vorkerland_diplomacy_decisions.txt")
        loc = read("localisation/russian/ADISCORD_vorkerland_collapse_l_russian.yml")

        for legacy_id in (
            "ADISCORD_vorkerland_wrk_integrate_vla",
            "ADISCORD_vorkerland_vad_recognize_sol",
        ):
            self.assertFalse(named_block(collapse, legacy_id), legacy_id)
            self.assertNotIn(f" {legacy_id}:", loc)
            self.assertNotIn(f" {legacy_id}_desc:", loc)

        canonical = {
            "ADISCORD_vorkerland_wkr_invite_victorious_vla": (
                "allowed = { tag = WKR }",
                "has_country_flag = ADISCORD_vorkerland_focus_wkr_vla_invitation_intent",
                "has_global_flag = ADISCORD_vorkerland_volnograd_terminal_verified",
                "has_global_flag = ADISCORD_vorkerland_volnograd_winner_vla",
                "complete_effect = { ADISCORD_vorkerland_offer_wkr_vla_alliance = yes }",
            ),
            "ADISCORD_vorkerland_vad_invite_victorious_sol": (
                "allowed = { tag = VAD }",
                "has_country_flag = ADISCORD_vorkerland_focus_vad_sol_invitation_intent",
                "has_country_flag = ADISCORD_vorkerland_focus_vad_solland_liaison_prepared",
                "has_global_flag = ADISCORD_vorkerland_solar_terminal_verified",
                "has_global_flag = ADISCORD_vorkerland_solar_winner_sol",
                "complete_effect = { ADISCORD_vorkerland_offer_vad_sol_alliance = yes }",
            ),
        }
        for decision_id, tokens in canonical.items():
            block = named_block(diplomacy, decision_id)
            self.assertTrue(block, decision_id)
            for token in tokens:
                self.assertIn(token, block, decision_id)
            for bypass in ("controls_state =", "puppet =", "set_autonomy =", "declare_war_on ="):
                self.assertNotIn(bypass, block, decision_id)

    def test_ivanland_has_paid_norvane_and_wit_diplomatic_decisions(self) -> None:
        decisions = read("common/decisions/ADISCORD_vorkerland_collapse_decisions.txt")
        alliance = named_block(decisions, "ADISCORD_ivanland_form_norvane_alliance")
        self.assertRegex(alliance, r"\bcost\s*=\s*(?:[5-9]\d|\d{3,})\b")
        self.assertIn("create_faction_from_template", alliance)
        self.assertIn("name = faction_ivanland_norvane_alliance", alliance)
        self.assertIn("add_to_faction = IBA", alliance)
        self.assertIn("ADISCORD_vorkerland_ivanland_intervention_succeeded", alliance)

        invitation = named_block(decisions, "ADISCORD_ivanland_invite_wit")
        self.assertRegex(invitation, r"\bcost\s*=\s*(?:[3-9]\d|\d{3,})\b")
        self.assertIn("is_in_faction = yes", invitation)
        self.assertIn("WIT = { exists = yes", invitation)
        self.assertIn("add_to_faction = WIT", invitation)

        loc = read("localisation/russian/ADISCORD_vorkerland_collapse_l_russian.yml")
        for key in (
            "ADISCORD_ivanland_form_norvane_alliance",
            "ADISCORD_ivanland_invite_wit",
            "faction_ivanland_norvane_alliance",
        ):
            self.assertIn(f" {key}:", loc)

    def test_piv_supports_macri_without_puppeting_him(self) -> None:
        ai = read("common/ai_strategy/ADISCORD_vorkerland_collapse_ai.txt")
        piv = named_block(ai, "ADISCORD_vorkerland_piv_support_macri")
        self.assertIn("send_volunteers_desire", piv)
        self.assertIn("id = EBA", piv)
        self.assertIn("is_subject = no", piv)
        all_collapse = read("common/scripted_effects/ADISCORD_vorkerland_collapse_effects.txt")
        eba_setup = named_block(all_collapse, "ADISCORD_vorkerland_setup_eba")
        self.assertNotIn("puppet", eba_setup)
        decisions = read("common/decisions/ADISCORD_vorkerland_collapse_decisions.txt")
        pact = named_block(decisions, "ADISCORD_vorkerland_macri_piv_pact")
        for token in (
            "controls_state = 74", "controls_state = 105", "controls_state = 197",
            "NOT = { country_exists = VLA }", "NOT = { country_exists = TGD }",
            "available = { has_war = no }",
        ):
            self.assertIn(token, pact)

    def test_wrk_and_vad_flags_are_distinct(self) -> None:
        wrk_path = ROOT / "gfx" / "flags" / "WRK_vorkerland_emergency.tga"
        vad_path = ROOT / "gfx" / "flags" / "VAD_vorkerland_restoration.tga"
        with Image.open(wrk_path) as wrk, Image.open(vad_path) as vad:
            self.assertEqual(wrk.size, (82, 52))
            self.assertEqual(vad.size, (82, 52))
            self.assertNotEqual(wrk.convert("RGB").tobytes(), vad.convert("RGB").tobytes())

    def test_new_flags_are_original_and_have_complete_triplets(self) -> None:
        flag_ids = (
            "EBA",
            "TGD",
            "IBA",
            "IBL",
            "SLF",
            "CSL",
            "PWR_rimat_republic",
            "ROM_frealor_republic",
            "TRU_zolotorevsk_republic",
            "VLA_volnograd_republic",
            "ZAO_zaozersk_republic",
            "SLF_svetlogorsk_republic",
            "WRK_vorkerland_utilitarian_republic",
        )
        variants = (("", (82, 52)), ("medium", (41, 26)), ("small", (10, 7)))
        vanilla_root = Path(r"Z:\SteamLibrary\steamapps\common\Hearts of Iron IV\gfx\flags")

        for directory, size in variants:
            decoded: dict[bytes, str] = {}
            vanilla_pixels: set[bytes] = set()
            vanilla_dir = vanilla_root / directory
            if vanilla_dir.is_dir():
                for vanilla_path in vanilla_dir.glob("*.tga"):
                    with Image.open(vanilla_path) as vanilla:
                        if vanilla.size == size:
                            vanilla_pixels.add(vanilla.convert("RGBA").tobytes())

            for flag_id in flag_ids:
                path = ROOT / "gfx" / "flags" / directory / f"{flag_id}.tga"
                self.assertTrue(path.is_file(), path)
                with Image.open(path) as image:
                    self.assertEqual(image.size, size, path)
                    pixels = image.convert("RGBA").tobytes()
                self.assertNotIn(pixels, decoded, f"{flag_id} duplicates {decoded.get(pixels)}")
                self.assertNotIn(pixels, vanilla_pixels, f"{flag_id} reuses a vanilla flag")
                decoded[pixels] = flag_id

    def test_legacy_administrations_receive_republican_cosmetics(self) -> None:
        effects = read("common/scripted_effects/ADISCORD_vorkerland_collapse_effects.txt")
        cosmetics = named_block(effects, "ADISCORD_vorkerland_apply_claimant_cosmetics")
        for tag in ("ROM", "TRU", "ZAO"):
            self.assertIn(
                "ADISCORD_vorkerland_sync_independence_cosmetic = yes",
                named_block(cosmetics, tag),
                tag,
            )
        for token in (
            "set_cosmetic_tag = PWR_rimat_republic",
            "VLA = { set_cosmetic_tag = VLA_volnograd_republic }",
        ):
            self.assertIn(token, cosmetics)
        sync = named_block(effects, "ADISCORD_vorkerland_sync_independence_cosmetic")
        for token in (
            "is_subject = yes", "drop_cosmetic_tag = yes",
            "set_cosmetic_tag = ROM_frealor_republic",
            "set_cosmetic_tag = TRU_zolotorevsk_republic",
            "set_cosmetic_tag = ZAO_zaozersk_republic",
        ):
            self.assertIn(token, sync)
        on_actions = read("common/on_actions/01_ADISCORD_vorkerland_collapse_on_actions.txt")
        for hook in ("on_puppet", "on_release_as_puppet", "on_release_as_free"):
            self.assertIn(
                "ADISCORD_vorkerland_sync_independence_cosmetic = yes",
                named_block(on_actions, hook),
            )
        self.assertNotIn(
            "ADISCORD_vorkerland_sync_independence_cosmetic = yes",
            named_block(on_actions, "on_monthly"),
        )
        loc = read("localisation/russian/countries_l_russian.yml")
        self.assertIn('PWR_rimat_republic: "Риматская инженерная директория"', loc)
        self.assertIn('ZAO_zaozersk_republic: "Заозерская республика"', loc)
        self.assertIn('VLA_volnograd_republic: "Вольноградская республика"', loc)
        self.assertIn('ROM_frealor_republic: "Республика Фреалор"', loc)
        self.assertIn('TRU_zolotorevsk_republic: "Золоторевская республика"', loc)
        with Image.open(ROOT / "gfx/flags/PWR_rimat_republic.tga") as republic, Image.open(ROOT / "gfx/flags/PWR.tga") as administration:
            self.assertEqual(republic.size, (82, 52))
            self.assertNotEqual(republic.convert("RGB").tobytes(), administration.convert("RGB").tobytes())

    def test_claimant_map_colours_are_strongly_separated(self) -> None:
        cosmetics = read("common/countries/cosmetic.txt")
        self.assertIn("color = rgb { 72 61 57 }", named_block(cosmetics, "WRK_vorkerland_emergency"))
        self.assertIn("color = rgb { 19 45 105 }", named_block(cosmetics, "VAD_vorkerland_restoration"))

    def test_wrk_characters_are_recruited_in_history_not_runtime_effects(self) -> None:
        effects = read("common/scripted_effects/ADISCORD_vorkerland_collapse_effects.txt")
        history = read("history/countries/WRK - WorkerLand.txt")
        for character in ("WRK_Anton_Bagley", "WRK_VAD_Joint_Council"):
            self.assertIn(f"recruit_character = {character}", history)
            self.assertNotIn(f"recruit_character = {character}", effects)

    def test_player_facing_names_are_short_and_not_legacy_cringe(self) -> None:
        loc = read("localisation/russian/ADISCORD_vorkerland_collapse_l_russian.yml")
        for banned in ("Западный союз", "Норвенская береговая республика", "Восточное содружество"):
            self.assertNotIn(banned, loc)
        for expected in (
            "Республика Норвен",
            "Хольденский синдикат",
            "Зшатская хунта",
            "Республика Эберн",
            "Фирнов-Техлар",
        ):
            self.assertIn(expected, loc)
        geography = "\n".join(
            (
                loc,
                read("localisation/russian/state_names_l_russian.yml"),
                read("localisation/russian/victory_points_l_russian.yml"),
            )
        )
        self.assertNotIn("Техград", geography)
        self.assertIn('STATE_40: "Башня Единства"', geography)
        self.assertIn('VICTORY_POINTS_16428: "Башня Единства"', geography)
        self.assertIn('VICTORY_POINTS_6713: "Гранд-Воркенсберг"', geography)


if __name__ == "__main__":
    unittest.main()
