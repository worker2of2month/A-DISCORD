from __future__ import annotations

import re
import unittest
from pathlib import Path

from PIL import Image

from tools.validate_adiscord_vorkerland_collapse import SECTIONS, named_block, validate
from tools.vorkerland_collapse_manifest import CAPITALS, TAGS


ROOT = Path(__file__).resolve().parents[1]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8-sig")


class VorkerlandCollapseValidatorTests(unittest.TestCase):
    def test_every_validator_section_passes(self) -> None:
        for section in SECTIONS:
            with self.subTest(section=section):
                self.assertEqual(validate(ROOT, section), [])

    def test_manifest_covers_new_political_map(self) -> None:
        self.assertEqual(len(TAGS), 20)
        self.assertEqual(len(set(TAGS)), 20)
        self.assertEqual(set(TAGS), set(CAPITALS))
        self.assertTrue({"TGD", "IBA", "IBL", "CSL"} <= set(TAGS))


class BorderWarArchitectureTests(unittest.TestCase):
    def test_day_one_event_declares_no_wars(self) -> None:
        events = read("events/ADISCORD_vorkerland_collapse_events.txt")
        match = re.search(
            r"(?ms)^country_event\s*=\s*\{\s*id\s*=\s*ADISCORD_vorkerland_collapse\.2\b(.*?)(?=^country_event|\Z)",
            events,
        )
        self.assertIsNotNone(match)
        self.assertNotIn("declare_war_on", match.group(1))
        self.assertIn("ADISCORD_vorkerland_collapse.31", match.group(1))
        self.assertIn("days = 21", match.group(1))
        self.assertRegex(match.group(1), r"WRK\s*=\s*\{[^{}]*country_event\s*=\s*\{")

    def test_mobilisation_pause_unlocks_ai_border_decisions(self) -> None:
        events = read("events/ADISCORD_vorkerland_collapse_events.txt")
        authorization = re.search(
            r"(?ms)^country_event\s*=\s*\{\s*id\s*=\s*ADISCORD_vorkerland_collapse\.31\b"
            r"(.*?)(?=^country_event\s*=\s*\{|\Z)",
            events,
        )
        self.assertIsNotNone(authorization)
        self.assertIn("tag = WRK", authorization.group(1))
        self.assertEqual(
            authorization.group(1).count(
                "set_global_flag = ADISCORD_vorkerland_claim_wars_authorized"
            ),
            1,
        )
        self.assertNotIn("declare_war_on", authorization.group(1))
        for event_id in (32, 33, 34, 35):
            self.assertNotIn(f"ADISCORD_vorkerland_collapse.{event_id}", events)

        decisions = read("common/decisions/ADISCORD_vorkerland_collapse_decisions.txt")
        decision = named_block(decisions, "ADISCORD_vorkerland_consolidate_central_border")
        self.assertIn("has_global_flag = ADISCORD_vorkerland_claim_wars_authorized", decision)
        self.assertIn("declare_war_on", decision)
        self.assertIn("ai_will_do", decision)
        self.assertNotIn("ADISCORD_vorkerland_settle_regional_border", decisions)

    def test_border_wars_are_declared_by_decisions_not_hidden_seed_events(self) -> None:
        events = read("events/ADISCORD_vorkerland_collapse_events.txt")
        on_actions = read("common/on_actions/01_ADISCORD_vorkerland_collapse_on_actions.txt")
        decisions = read("common/decisions/ADISCORD_vorkerland_collapse_decisions.txt")

        for event_id in (32, 33, 34, 35):
            self.assertNotIn(
                f"id = ADISCORD_vorkerland_collapse.{event_id}", events
            )
        self.assertNotIn("ADISCORD_vorkerland_seed_watchdog_scheduled", events)
        self.assertNotIn("ADISCORD_vorkerland_seed_watchdog_scheduled", on_actions)
        self.assertNotIn("declare_war_on", events)

        for decision in (
            "ADISCORD_vorkerland_consolidate_central_border",
            "ADISCORD_vorkerland_continue_reunification",
        ):
            self.assertIn("declare_war_on", named_block(decisions, decision), decision)

    def test_main_claimants_can_open_their_mandatory_front_while_already_at_war(self) -> None:
        triggers = read("common/scripted_triggers/ADISCORD_vorkerland_collapse_triggers.txt")
        decisions = read("common/decisions/ADISCORD_vorkerland_collapse_decisions.txt")

        rival = named_block(
            triggers, "ADISCORD_vorkerland_is_main_claimant_rival_for_ROOT"
        )
        main_claimant = named_block(triggers, "ADISCORD_vorkerland_is_main_claimant")
        self.assertEqual(
            set(re.findall(r"tag\s*=\s*([A-Z]{3})", main_claimant)),
            {"WRK", "VAD", "TVA"},
        )
        self.assertGreaterEqual(
            rival.count("ADISCORD_vorkerland_is_main_claimant = yes"), 2
        )
        self.assertNotIn("has_war = no", rival)

        central = named_block(decisions, "ADISCORD_vorkerland_consolidate_central_border")
        available = named_block(central, "available")
        complete = named_block(central, "complete_effect")
        for tag in ("WRK", "VAD", "TVA"):
            self.assertIn(f"tag = {tag}", available)
        for target in ("WRK", "VAD", "TVA"):
            self.assertIn(f"declare_war_on = {{ target = {target}", complete)
        self.assertIn("random_neighbor_country", complete)

    def test_post_opening_regional_neighbor_war_decision_is_removed(self) -> None:
        triggers = read("common/scripted_triggers/ADISCORD_vorkerland_collapse_triggers.txt")
        decisions = read("common/decisions/ADISCORD_vorkerland_collapse_decisions.txt")
        self.assertNotIn("ADISCORD_vorkerland_settle_regional_border", decisions)
        self.assertNotIn("ADISCORD_vorkerland_is_local_rival_for_ROOT", triggers)

    def test_dynamic_regional_front_fallback_is_removed(self) -> None:
        ai = read("common/ai_strategy/ADISCORD_vorkerland_collapse_ai.txt")
        self.assertNotIn("ADISCORD_vorkerland_dynamic_regional_front_commitment", ai)
        self.assertNotIn("country_trigger = {", ai)

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

    def test_reunification_requires_neighbors_but_central_claimants_cannot_deadlock(self) -> None:
        decisions = read("common/decisions/ADISCORD_vorkerland_collapse_decisions.txt")
        reunification = named_block(decisions, "ADISCORD_vorkerland_continue_reunification")
        self.assertIn("random_neighbor_country", reunification)
        self.assertIn("declare_war_on", reunification)
        self.assertIn("ai_will_do", reunification)

        central = named_block(decisions, "ADISCORD_vorkerland_consolidate_central_border")
        for target in ("WRK", "VAD", "TVA"):
            self.assertIn(f"declare_war_on = {{ target = {target}", central)
        self.assertIn("ai_will_do", central)

    def test_war_targets_cannot_be_dogpiled_into_a_mega_war(self) -> None:
        triggers = read("common/scripted_triggers/ADISCORD_vorkerland_collapse_triggers.txt")
        for key in (
            "ADISCORD_vorkerland_is_central_target_for_ROOT",
            "ADISCORD_vorkerland_is_reunification_target_for_ROOT",
        ):
            self.assertIn("has_war = no", named_block(triggers, key), key)

    def test_collapse_opening_news_is_immediate_and_single_shot(self) -> None:
        events = read("events/ADISCORD_vorkerland_collapse_events.txt")
        outbreak = named_block(events, "country_event")
        self.assertEqual(events.count("id = news.0"), 1)
        self.assertIn("NOT = { has_global_flag = ADISCORD_vorkerland_collapse_news_shown }", outbreak)
        self.assertIn("set_global_flag = ADISCORD_vorkerland_collapse_news_shown", outbreak)
        opening = named_block(outbreak, "news_event")
        for delayed in ("hours =", "days =", "random_hours", "random_days"):
            self.assertNotIn(delayed, opening)
        self.assertLess(
            outbreak.find("ADISCORD_vorkerland_apply_claimant_cosmetics = yes"),
            outbreak.find("news_event = { id = news.0 }"),
        )
        news_loc = read("localisation/russian/ADISORD_news_l_russian.yml")
        self.assertIn('news.0.t: "Конец единого Воркерланда"', news_loc)
        superevent_loc = read("localisation/russian/ADISCORD_superevents_l_russian.yml")
        self.assertNotIn(
            'superevent_vorkerland_fragmented_title: "Конец единого Воркерланда"',
            superevent_loc,
        )

    def test_central_claimants_must_finish_the_core_first(self) -> None:
        triggers = read("common/scripted_triggers/ADISCORD_vorkerland_collapse_triggers.txt")
        main = named_block(triggers, "ADISCORD_vorkerland_is_main_claimant")
        self.assertEqual(set(re.findall(r"tag\s*=\s*([A-Z]{3})", main)), {"WRK", "VAD", "TVA"})
        for candidate in ("worker", "vlad", "dorian"):
            block = named_block(triggers, f"ADISCORD_vorkerland_{candidate}_victory_candidate")
            for defeated in ("eyr", "egc"):
                self.assertIn(f"ADISCORD_vorkerland_{defeated}_defeated = yes", block)
            self.assertNotIn("ADISCORD_vorkerland_tgd_defeated", block)
            self.assertIn("controls_state = 40", block)
        central = named_block(triggers, "ADISCORD_vorkerland_is_central_claimant")
        self.assertNotIn("tag = TGD", central)
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
        decisions = read("common/decisions/ADISCORD_vorkerland_collapse_decisions.txt")
        recognition = named_block(decisions, "ADISCORD_vorkerland_recognize_free_republics")
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
        self.assertNotIn("ADISCORD_vorkerland_settle_regional_border", decisions)

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
        for stale in ("stalemate", "war_weariness", "to_the_last", "vorkerland_phase_"):
            self.assertNotIn(stale, combined)

    def test_ai_fronts_keep_pressure_without_supply_blind_local_attacks(self) -> None:
        ai = read("common/ai_strategy/ADISCORD_vorkerland_collapse_ai.txt")
        economy = named_block(ai, "ADISCORD_vorkerland_collapse_war_economy")
        self.assertIn("type = ai_wanted_divisions_factor value = 8", economy)
        self.assertNotIn("ADISCORD_vorkerland_collapse_front_commitment", ai)
        for strategy in re.findall(r"ai_strategy\s*=\s*\{([^{}]*)\}", ai, re.DOTALL):
            if "type = front_control" in strategy or "type = front_unit_request" in strategy:
                self.assertEqual(len(re.findall(r"\btag\s*=", strategy)), 1, strategy)
        for attacker, defender in (
            ("VLA", "EBA"), ("EBA", "VLA"),
            ("VLA", "TGD"), ("TGD", "VLA"), ("EBA", "TGD"), ("TGD", "EBA"),
            ("SOL", "SRA"), ("SRA", "SOL"),
        ):
            front = named_block(ai, f"ADISCORD_vorkerland_front_{attacker.lower()}_{defender.lower()}")
            self.assertIn(f"has_war_with = {defender}", front)
            self.assertIn(f"front_control tag = {defender}", front)
            self.assertIn("manual_attack = yes", front)

        for attacker, defender in (
            ("PWR", "PSD"), ("PSD", "PWR"),
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
        wrk = named_block(initial, "WRK")
        self.assertRegex(wrk, r"transfer_state\s*=\s*32\b")
        self.assertNotRegex(wrk, r"transfer_state\s*=\s*105\b")

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
            self.assertEqual(oob.count("division = {"), 3, tag)
            equipment = [
                float(value)
                for value in re.findall(r"start_equipment_factor\s*=\s*([\d.]+)", oob)
            ]
            self.assertEqual(len(equipment), 3, tag)
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
        for tag in ("TVA", "EYR", "EGC", "TGD", "EBA", "PSD", "DVA", "ZTA", "WPA", "WPS"):
            block = named_block(effects, f"ADISCORD_vorkerland_setup_{tag.lower()}")
            manpower = re.search(r"add_manpower\s*=\s*(\d+)", block)
            rifles = re.search(r"add_equipment_to_stockpile\s*=\s*\{[^{}]*amount\s*=\s*(\d+)", block)
            self.assertIsNotNone(manpower, tag)
            self.assertGreaterEqual(int(manpower.group(1)), 3000, tag)
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
        self.assertEqual(tva_oob.count("division = {"), 5)

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
        for tag in ("NAM", "DAN", "VAD", "ZAO", "PWR", "VLA", "ROM", "SOL", "TRU", "TVA", "TGD", "IBA", "IBL"):
            block = named_block(teardown, tag)
            self.assertIn("is_subject = yes", block, tag)
            self.assertIn("overlord =", block, tag)
            self.assertIn(f"target = {tag}", block, tag)
            self.assertIn("autonomy_state = autonomy_free", block, tag)
            self.assertIn("leave_faction = yes", block, tag)

    def test_only_regional_superloyalists_can_restore_district_status(self) -> None:
        decisions = read("common/decisions/ADISCORD_vorkerland_collapse_decisions.txt")
        decision = named_block(decisions, "ADISCORD_vorkerland_restore_loyalist_district")
        allowed = named_block(decision, "allowed")
        self.assertEqual(set(re.findall(r"tag\s*=\s*([A-Z]{3})", allowed)), {"ZAO", "PWR", "VLA"})
        for excluded in ("ROM", "TRU", "SOL"):
            self.assertNotIn(f"tag = {excluded}", allowed)
        self.assertIn("autonomy_state = autonomy_district_in_Vorkerland", decision)
        self.assertIn("drop_cosmetic_tag = yes", decision)


class CharactersAndPoliticsTests(unittest.TestCase):
    def test_dynamic_successors_promote_predeclared_country_leaders(self) -> None:
        effects = read("common/scripted_effects/ADISCORD_vorkerland_collapse_effects.txt")
        expected = {
            "tva": ("TVA_Dorian_Worx", "technocracy_ideology"),
            "eyr": ("EYR_Irina_Koval", "humanism_ideology"),
            "egc": ("EGC_Ruslan_Pike", "etatism_ideology"),
            "csl": ("CSL_Miron_Rudakov", "pragmatism_ideology"),
            "wpa": ("WPA_Oliver_Larry_Gates", "humanism_ideology"),
            "wps": ("WPS_Karim_Dol", "technocracy_ideology"),
            "psd": ("PSD_Marta_Cinder", "etatism_ideology"),
            "eba": ("EBA_Vlad_Mecra", "hedonism_ideology"),
            "dva": ("DVA_Severin_Mark", "etatism_ideology"),
            "sra": ("SRA_Helio_Marr", "humanism_ideology"),
            "zta": ("ZTA_Viktor_Holt", "chauvinism_ideology"),
            "tgd": ("TGD_Ted_Cuttle", "technocracy_ideology"),
            "ibl": ("IBL_Anton_Selevyostrov", "chauvinism_ideology"),
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
        on_actions = read("common/on_actions/01_ADISCORD_vorkerland_collapse_on_actions.txt")
        monthly = named_block(on_actions, "on_monthly")

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
        self.assertIn("ADISCORD_vorkerland_appoint_joint_council = yes", monthly)
        self.assertIn("has_country_leader", monthly)
        self.assertIn("character = WRK_VAD_Joint_Council", monthly)
        self.assertIn("ruling_only = yes", monthly)

    def test_joint_government_starts_with_reduced_frontier(self) -> None:
        effects = read("common/scripted_effects/ADISCORD_vorkerland_collapse_effects.txt")
        joint = named_block(effects, "ADISCORD_vorkerland_form_joint_government")

        self.assertLess(
            joint.find("annex_country = { target = VAD transfer_troops = yes }"),
            joint.find("transfer_state = 27"),
        )
        self.assertRegex(joint, r"TVA\s*=\s*\{[^{}]*transfer_state\s*=\s*27[^{}]*\}")
        self.assertRegex(
            joint,
            r"EYR\s*=\s*\{[^{}]*transfer_state\s*=\s*82"
            r"[^{}]*transfer_state\s*=\s*123[^{}]*\}",
        )
        for state, tag in ((27, "TVA"), (82, "EYR"), (123, "EYR")):
            self.assertRegex(
                joint,
                rf"{state}\s*=\s*\{{[^{{}}]*add_core_of\s*=\s*{tag}"
                rf"[^{{}}]*set_state_controller_to\s*=\s*{tag}[^{{}}]*\}}",
            )

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
            "SRA_Helio_Marr": "GFX_portrait_SRA_Helio_Marr",
            "ZTA_Viktor_Holt": "GFX_portrait_ZTA_Viktor_Holt",
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

    def test_worker_death_installs_utilitarian_successor_and_supplied_flag(self) -> None:
        effects = read("common/scripted_effects/ADISCORD_vorkerland_collapse_effects.txt")
        cosmetics = read("common/countries/cosmetic.txt")
        loc = read("localisation/russian/countries_cosmetic_l_russian.yml")
        claimant_setup = named_block(effects, "ADISCORD_vorkerland_apply_claimant_cosmetics")
        successor = named_block(effects, "ADISCORD_vorkerland_promote_anton_bagley")

        self.assertIn("has_global_flag = ADISCORD_vorkerland_worker_safe_with_loyalists", claimant_setup)
        self.assertIn("ruling_party = utilitarism", claimant_setup)
        self.assertIn("elections_allowed = no", claimant_setup)
        self.assertIn("set_cosmetic_tag = WRK_vorkerland_utilitarian_republic", claimant_setup)
        self.assertIn("ideology = utilitarism_ideology", successor)
        self.assertIn("WRK_vorkerland_utilitarian_republic = {", cosmetics)
        self.assertIn(
            'WRK_vorkerland_utilitarian_republic: "Утилитарная Республика Воркерланда"',
            loc,
        )
        for directory, size in (("", (82, 52)), ("medium", (41, 26)), ("small", (10, 7))):
            path = ROOT / "gfx" / "flags" / directory / "WRK_vorkerland_utilitarian_republic.tga"
            self.assertTrue(path.is_file(), path)
            with Image.open(path) as flag:
                self.assertEqual(flag.size, size, path)

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
        self.assertEqual(effects.count("add_ideas = ADISCORD_vorkerland_erased_nations"), 1)
        initial = named_block(effects, "ADISCORD_vorkerland_prepare_initial_combatants")
        self.assertRegex(initial, r"WRK\s*=\s*\{[^{}]*add_ideas\s*=\s*ADISCORD_vorkerland_erased_nations")

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
            "TVA", "EYR", "EGC", "PSD", "DVA", "SRA", "IBL", "IBA",
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
                "VLA_national_spirit",
                "ADISCORD_vorkerland_erased_nations",
                "ADISCORD_vorkerland_piv_macri_volunteer_mission",
                "ADISCORD_vorkerland_tgd_grid_collapse",
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
    def test_ivanland_puppet_is_led_by_mateusk(self) -> None:
        effects = read("common/scripted_effects/ADISCORD_vorkerland_collapse_effects.txt")
        mandate = named_block(effects, "ADISCORD_vorkerland_setup_ivanland_mandate")
        appointment = named_block(effects, "ADISCORD_vorkerland_appoint_mateusk")
        on_actions = read("common/on_actions/01_ADISCORD_vorkerland_collapse_on_actions.txt")
        monthly = named_block(on_actions, "on_monthly")

        self.assertIn("puppet = IBA", mandate)
        self.assertIn("ADISCORD_vorkerland_appoint_mateusk = yes", mandate)
        self.assertLess(
            mandate.find("ADISCORD_vorkerland_appoint_mateusk = yes"),
            mandate.find("puppet = IBA"),
        )
        self.assertNotIn("create_country_leader", appointment)
        self.assertNotIn("recruit_character", appointment)
        self.assertIn("promote_character", appointment)
        self.assertIn("character = IBA_Matvey_Mateusk", appointment)
        self.assertIn("portrait = GFX_portrait_IBA_Matvey_Mateusk", appointment)
        self.assertIn("ideology = pragmatism_ideology", appointment)
        self.assertIn("ADISCORD_vorkerland_mateusk_character_repair_v2", appointment)
        self.assertIn("ADISCORD_vorkerland_appoint_mateusk = yes", monthly)
        self.assertIn("ADISCORD_vorkerland_end_ivanland_intervention_wars = yes", monthly)
        self.assertIn("character = IBA_Matvey_Mateusk", monthly)
        self.assertIn("ruling_only = yes", monthly)

    def test_ivanland_has_one_timed_puppet_outcome(self) -> None:
        decisions = read("common/decisions/ADISCORD_vorkerland_collapse_decisions.txt")
        mission = named_block(decisions, "ADISCORD_ivanland_limited_intervention")
        self.assertIn("selectable_mission = yes", mission)
        self.assertIn("days_mission_timeout = 240", mission)
        self.assertEqual(mission.count("type = take_state_focus"), 2)
        self.assertIn("generator = { 91 }", mission)
        self.assertIn("generator = { 90 }", mission)
        self.assertNotIn("annex_everything", mission)
        effects = read("common/scripted_effects/ADISCORD_vorkerland_collapse_effects.txt")
        mandate = named_block(effects, "ADISCORD_vorkerland_setup_ivanland_mandate")
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
        self.assertNotIn("transfer_state = 71", mandate)
        ivn_history = read("history/countries/IVN - IvanLand.txt")
        iba_history = read("history/countries/IBA - Ivanland Northern Mandate.txt")
        self.assertNotIn("recruit_character = IBA_Matvey_Mateusk", ivn_history)
        self.assertIn("recruit_character = IBA_Matvey_Mateusk", iba_history)
        focus = read("common/national_focus/ADISCORD_vorkerland_collapse_focus.txt")
        self.assertIn("tag = IBA", focus)
        self.assertIn("id = IBA_organize_transitional_council", focus)
        self.assertNotIn("GFX_goal_unknown", focus)
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
        self.assertIn("transfer_state = 90", failure)
        self.assertIn("transfer_state = 91", failure)
        self.assertIn("ADISCORD_vorkerland_vadim_etatist_role_added", failure)
        self.assertIn("Ivanland intervention resolved: FAILURE", failure)
        self.assertIn("clr_global_flag = ADISCORD_vorkerland_ivanland_intervention_succeeded", failure)
        on_actions = read("common/on_actions/01_ADISCORD_vorkerland_collapse_on_actions.txt")
        capitulation = named_block(on_actions, "on_capitulation")
        self.assertIn("set_global_flag = skip_default_capitulation", capitulation)
        self.assertIn("ROOT = { OR = { tag = IBL tag = PWR } }", capitulation)
        self.assertIn("ROOT = { tag = IVN }", capitulation)
        self.assertIn("ADISCORD_vorkerland_ivanland_intervention_success = yes", capitulation)
        self.assertIn("ADISCORD_vorkerland_ivanland_intervention_failure = yes", capitulation)
        self.assertIn("IVN = { white_peace = ROOT }", capitulation)
        proclamation = named_block(decisions, "ADISCORD_ivanland_proclaim_norvane")
        self.assertIn("controls_state = 90", proclamation)
        self.assertIn("controls_state = 91", proclamation)
        self.assertIn("ADISCORD_vorkerland_setup_ivanland_mandate = yes", proclamation)
        self.assertIn("factor = 400", proclamation)

    def test_ivanland_outcome_news_has_one_guarded_immediate_route(self) -> None:
        effects = read("common/scripted_effects/ADISCORD_vorkerland_collapse_effects.txt")
        events = read("events/ADISCORD_vorkerland_collapse_events.txt")
        loc = read("localisation/russian/ADISORD_news_l_russian.yml")
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
            for token in ("hidden = yes", "is_triggered_only = yes", "fire_only_once = yes"):
                self.assertIn(token, definition.group(1), news_id)
            self.assertIn(f"NOT = {{ has_global_flag = {shown_flag} }}", outcome, news_id)
            self.assertIn(f"set_global_flag = {shown_flag}", outcome, news_id)
            self.assertLess(outcome.find(completion), outcome.find(f"news_event = {{ id = {news_id} }}"), news_id)
            call = named_block(outcome, "news_event")
            for delayed in ("hours =", "days =", "random_hours", "random_days"):
                self.assertNotIn(delayed, call, news_id)
            for suffix in ("t", "d", "a"):
                self.assertIn(f"  {news_id}.{suffix}:", loc, news_id)

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
        for token in (
            "ROM = { ADISCORD_vorkerland_sync_independence_cosmetic = yes }",
            "TRU = { ADISCORD_vorkerland_sync_independence_cosmetic = yes }",
            "ZAO = { ADISCORD_vorkerland_sync_independence_cosmetic = yes }",
            "PWR = { set_cosmetic_tag = PWR_rimat_republic }",
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
        for hook in ("on_puppet", "on_release_as_puppet", "on_release_as_free", "on_monthly"):
            self.assertIn(
                "ADISCORD_vorkerland_sync_independence_cosmetic = yes",
                named_block(on_actions, hook),
            )
        loc = read("localisation/russian/countries_cosmetic_l_russian.yml")
        self.assertIn('PWR_rimat_republic: "Риматская республика"', loc)
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
        for expected in ("Республика Норвен", "Хольденский синдикат", "Зшатская хунта", "Республика Эберн", "Техград"):
            self.assertIn(expected, loc)


if __name__ == "__main__":
    unittest.main()
