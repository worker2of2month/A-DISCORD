from __future__ import annotations

import re
import unittest
from pathlib import Path

from tools.validators.validate_adiscord_vorkerland_collapse import named_block
from tools.validators.validate_adiscord_vorkerland_recovery import event_block

ROOT = Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8-sig")


class VorkerlandCentralWarVarianceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.effects = read("common/scripted_effects/ADISCORD_vorkerland_effects.txt")
        cls.triggers = read("common/scripted_triggers/ADISCORD_vorkerland_triggers.txt")
        cls.decisions = read("common/decisions/ADISCORD_vorkerland_decisions.txt")
        cls.events = read("events/ADISCORD_vorkerland_events.txt")

    def test_no_hidden_random_claimant_combat_roll(self) -> None:
        controller = read("common/on_actions/05_ADISCORD_vorkerland_stalemate_on_actions.txt")
        self.assertIn("on_war_relation_added", controller)
        self.assertNotIn("random_list", controller)
        for forbidden in ("annex_country", "white_peace", "set_capitulation"):
            self.assertNotIn(forbidden, controller)

    def test_start_has_four_autonomies_and_no_vad_territory(self) -> None:
        owners = {}
        for path in (ROOT / "history/states").glob("*.txt"):
            source = path.read_text(encoding="utf-8-sig")
            match = re.search(r"owner\s*=\s*([A-Z0-9]{3})", source)
            if match:
                owners[int(re.search(r"id\s*=\s*(\d+)", source)[1])] = match[1]
        self.assertNotIn("VAD", owners.values())
        wrk = read("history/countries/WRK - WorkerLand.txt")
        for tag in ("EYR", "EGC", "RIV", "YOR"):
            self.assertIn(tag, owners.values())
            self.assertIn(f"target = {tag}", wrk)
            path = next((ROOT / "history/countries").glob(tag + " - *.txt"))
            history = path.read_text(encoding="utf-8-sig")
            self.assertIn(f'oob = "{tag}_vorkerland_collapse"', history)
            setup = named_block(self.effects, f"ADISCORD_vorkerland_setup_{tag.lower()}")
            self.assertIn("NOT = { has_country_flag = ADISCORD_vorkerland_prewar_garrison_initialized }", setup)
        self.assertNotIn('oob = "VAD"', read("history/countries/VAD - VadlLand.txt"))

    def test_each_prewar_infantry_role_uses_worker_mesh_at_all_tiers(self) -> None:
        entities = read("gfx/entities/zz_ADISCORD_country_infantry.asset")
        for tag in ("WRK", "NAM", "DAN", "ZAO", "PWR", "VLA", "ROM", "SOL", "TRU", "WCG", "EYR", "EGC", "RIV", "YOR"):
            history = next((ROOT / "history/countries").glob(tag + " - *.txt")).read_text(encoding="utf-8-sig")
            self.assertIn(f"set_cosmetic_tag = {tag}_confederation", history)
            for tier in range(8):
                suffix = f"_{tier + 1}" if tier else ""
                for role in ("infantry", "ADISCORD_militia", "mountaineers"):
                    binding = f'clone = "ADISCORD_WRK_line_infantry{suffix}_entity" name = "{tag}_confederation_{role}{suffix}_entity"'
                    self.assertEqual(entities.count(binding), 1)

    def test_consolidation_clock_is_one_shot_and_survives_a_lost_host(self) -> None:
        start = named_block(self.effects, "ADISCORD_vorkerland_begin_central_preparation")
        self.assertIn("NOT = { has_global_flag = ADISCORD_vorkerland_consolidation_clock_started }", start)
        for tag in ("WKR", "VAD", "TVA"):
            self.assertIn("ADISCORD_vorkerland_phase.4 days = 180", named_block(start, tag))
        mission = named_block(self.decisions, "ADISCORD_vorkerland_consolidation_deadline")
        self.assertIn("available = { hidden_trigger = { always = no } }", mission)
        self.assertIn("days_mission_timeout = 180", mission)
        self.assertIn("cancel_trigger", mission)
        self.assertNotIn("annex_country", mission)
        self.assertNotIn("white_peace", mission)

    def test_victory_rechecks_liberation_and_protects_neutral_capital(self) -> None:
        gate = named_block(self.triggers, "ADISCORD_vorkerland_coalition_victory_ready")
        capital = named_block(self.triggers, "ADISCORD_vorkerland_central_districts_owned_and_controlled")
        for caller in (named_block(self.effects, "ADISCORD_vorkerland_begin_reunification"), event_block(self.events, "ADISCORD_vorkerland_phase.6")):
            self.assertIn("ADISCORD_vorkerland_coalition_victory_ready = yes", caller)
        self.assertEqual(gate.count("ADISCORD_vorkerland_central_districts_owned_and_controlled = yes"), 3)
        self.assertNotIn("is_core_of", gate)
        self.assertIn("NOT = { any_enemy_country = { NOT = { has_capitulated = yes } } }", capital)
        self.assertIn("owner = { is_in_faction_with = PREV.PREV }", capital)
        self.assertIn("controller = { is_in_faction_with = PREV.PREV }", capital)
        self.assertNotIn("country_exists = EYR", gate)

    def test_join_has_immediate_host_recheck_and_event_root(self) -> None:
        decision = named_block(self.decisions, "ADISCORD_vorkerland_join_claimant_coalition")
        self.assertIn("ADISCORD_vorkerland_is_coalition_host_for_ROOT = yes", named_block(decision, "available"))
        self.assertNotIn("has_war", named_block(decision, "target_trigger"))
        dispatch = named_block(self.effects, "ADISCORD_vorkerland_join_regional_allies_to_showdown")
        self.assertNotIn("ADISCORD_vorkerland_splice_into_coalition_host_war = yes", dispatch)
        self.assertIn("ADISCORD_vorkerland_collapse.93 days = 1", dispatch)
        callback = event_block(self.events, "ADISCORD_vorkerland_collapse.93")
        self.assertLess(callback.index("ADISCORD_vorkerland_splice_into_coalition_host_war"), callback.index("ADISCORD_vorkerland_verify_coalition_membership"))

    def test_integration_receipt_settles_once_and_survives_tag_handoff(self) -> None:
        ids = re.findall(r"^\s*(ADISCORD_vorkerland_integrate_\w+_district) = \{", self.decisions, re.M)
        self.assertEqual(len(ids), 9)
        refund = named_block(self.effects, "ADISCORD_vorkerland_refund_integrations_to_successor")
        for key in ids:
            block = named_block(self.decisions, key)
            self.assertIn("ADISCORD_vorkerland_district_integration_available = yes", block)
            cost = 10 if key in {"ADISCORD_vorkerland_integrate_ndn_district", "ADISCORD_vorkerland_integrate_swb_district"} else 15
            self.assertIn(f"cost = {cost}", block)
            self.assertIn(f"set_country_flag = {key}_paid", named_block(block, "complete_effect"))
            remove = named_block(block, "remove_effect")
            self.assertLess(remove.index(f"clr_country_flag = {key}_paid"), remove.index("add_core_of"))
            self.assertIn(f"add_political_power = {cost}", remove)
            self.assertIn(f"remove_decision = {key}", refund)
        for tag in ("wkr", "vad", "tva"):
            formation = named_block(self.effects, "ADISCORD_vorkerland_form_wrk_from_" + tag)
            self.assertLess(formation.index("ADISCORD_vorkerland_refund_integrations_to_successor"), formation.index(f"annex_country = {{ target = {tag.upper()}"))
            self.assertLess(formation.index("ADISCORD_vorkerland_reunification_ally"), formation.index("ADISCORD_vorkerland_prepare_claimants_for_formation"))
            self.assertGreater(formation.index("ADISCORD_vorkerland_restore_reunification_allies"), formation.rindex("annex_country"))

    def test_theatre_has_all_claimant_homes_without_impassable_state(self) -> None:
        attrition = named_block(self.effects, "ADISCORD_vorkerland_apply_central_attrition")
        states = set(map(int, re.findall(r"(\d+) = \{ set_state_flag = ADISCORD_vorkerland_central_theatre", attrition)))
        self.assertEqual(len(states), 37)
        self.assertTrue({32, 33, 200, 201, 75, 106, 107, 121, 36, 37, 38, 39, 324} <= states)
        self.assertNotIn(40, states)
        for name in ("ADISCORD_vorkerland_recount_central_control", "ADISCORD_vorkerland_retire_civil_war_modifiers"):
            self.assertIn("has_state_flag = ADISCORD_vorkerland_central_theatre", named_block(self.effects, name))

    def test_legacy_relief_always_improves_every_penalty(self) -> None:
        ideas = read("common/ideas/ADISCORD_vorkerland_ideas.txt")
        stages = [named_block(ideas, key) for key in ("ADISCORD_vorkerland_erased_nations", "ADISCORD_vorkerland_erased_nations_relief_1", "ADISCORD_vorkerland_erased_nations_relief_2")]
        axes = ("stability_factor", "war_support_factor", "recruitable_population_factor", "industrial_capacity_factory", "consumer_goods_factor", "political_power_gain", "army_org_factor")
        for axis in axes:
            values = [abs(float(re.search(rf"{axis} = (-?[0-9.]+)", stage)[1])) for stage in stages]
            self.assertGreater(values[0], values[1], axis)
            self.assertGreater(values[1], values[2], axis)
        self.assertIn("ADISCORD_economy_mark_dirty = yes", named_block(self.effects, "ADISCORD_vorkerland_refresh_war_economy_dynamic_state"))

    def test_paid_intervention_cannot_attack_a_new_coalition_or_charge_twice(self) -> None:
        decision = named_block(self.decisions, "ADISCORD_vorkerland_vad_restore_sol_by_force")
        self.assertIn("ADISCORD_vorkerland_vad_has_unaligned_solar_target = yes", named_block(decision, "available"))
        self.assertIn("ADISCORD_vorkerland_vad_has_unaligned_solar_target = no", named_block(decision, "cancel_trigger"))
        for key in ("ADISCORD_vorkerland_attempt_vad_solar_intervention", "ADISCORD_vorkerland_verify_vad_solar_intervention"):
            body = named_block(self.effects, key)
            for tag in ("SRA", "CSL"):
                self.assertIn(f"{tag} = {{ exists = yes is_subject = no is_in_faction = no", body)
        paid = "ADISCORD_vorkerland_vad_solar_intervention_paid"
        reserve = named_block(self.effects, "ADISCORD_vorkerland_reserve_vad_solar_intervention")
        self.assertNotIn(f"set_country_flag = {paid}", reserve)
        self.assertIn(f"set_country_flag = {paid}", named_block(decision, "complete_effect"))
        self.assertNotIn(f"set_country_flag = {paid}", self.events)
        for key in ("ADISCORD_vorkerland_cancel_vad_solar_intervention_reservation", "ADISCORD_vorkerland_clear_failed_vad_solar_intervention"):
            body = named_block(self.effects, key)
            self.assertIn(f"has_country_flag = {paid}", body)
            self.assertLess(body.index(f"clr_country_flag = {paid}"), body.index("add_political_power = 50"))
        success = named_block(named_block(self.effects, "ADISCORD_vorkerland_verify_vad_solar_intervention"), "if")
        self.assertIn(f"clr_country_flag = {paid}", success)

    def test_special_fronts_respect_shared_outbreak_and_allied_districts(self) -> None:
        counter = named_block(self.effects, "ADISCORD_vorkerland_attempt_vad_solyarino_counter")
        self.assertIn("has_war_with = WKR", named_block(counter, "limit"))
        self.assertNotIn("target = WKR type = annex_everything", counter)
        verifier = named_block(self.effects, "ADISCORD_vorkerland_verify_central_showdown")
        self.assertIn("ADISCORD_vorkerland_attempt_vad_solyarino_counter = yes", verifier)
        remaining = named_block(self.effects, "ADISCORD_vorkerland_attempt_remaining_central_fronts")
        self.assertEqual(remaining.count("has_global_flag = ADISCORD_vorkerland_phase_central_showdown"), 3)
        self.assertEqual(remaining.count("is_in_faction = no"), 27)
        for target in ("sol", "sra", "csl"):
            self.assertIn("is_in_faction = no", named_block(self.triggers, "ADISCORD_vorkerland_wkr_valid_" + target + "_target"))

    def test_native_event_timeout_uses_first_complete_choice(self) -> None:
        choice = event_block(self.events, "ADISCORD_vorkerland_phase.1")
        self.assertIn("timeout_days = 14", choice)
        self.assertNotIn("timeout_effect", choice)
        first = named_block(choice, "option")
        self.assertIn("set_global_flag = ADISCORD_vorkerland_preference_worker", first)
        self.assertEqual(first.count("ADISCORD_vorkerland_collapse.1"), 1)


if __name__ == "__main__":
    unittest.main()
