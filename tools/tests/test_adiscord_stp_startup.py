from __future__ import annotations

import re
import struct
import unittest
from pathlib import Path

from tools.tests.test_adiscord_stp_preparation import block, scalar, selected_effects
from tools.validators.validate_adiscord_division_templates import parse_clausewitz


ROOT = Path(__file__).resolve().parents[2]
EFFECTS = ROOT / "common/scripted_effects/ADISCORD_STP_scripted_effects.txt"
DECISIONS = ROOT / "common/decisions/ADISCORD_STP_decisions.txt"
DECISION_CATEGORIES = ROOT / "common/decisions/categories/ADISCORD_decision_categories_STP.txt"
BOP = ROOT / "common/bop/STP.txt"
DYNAMIC_MODIFIERS = ROOT / "common/dynamic_modifiers/ADISCORD_dynamic_modifiers_STP.txt"
INLAY = ROOT / "common/focus_inlay_windows/ADISCORD_STP_state_face_inlay_window.txt"
SCRIPTED_LOC = ROOT / "common/scripted_localisation/ADISCORD_STP_scripted_loc.txt"
LOCALISATION = ROOT / "localisation/russian/ADISCORD_STP_l_russian.yml"
HISTORY = ROOT / "history/countries/STP - StepanLand.txt"
ON_ACTIONS = ROOT / "common/on_actions/00_ADISCORD_on_actions.txt"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def named_block(text: str, name: str) -> str:
    match = re.search(rf"(?m)^\s*{re.escape(name)}\s*=\s*\{{", text)
    if match is None:
        raise AssertionError(f"missing block: {name}")

    opening = text.find("{", match.start())
    depth = 0
    for index in range(opening, len(text)):
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
            if depth == 0:
                return text[match.start() : index + 1]
    raise AssertionError(f"unterminated block: {name}")


class STPCoreContractTests(unittest.TestCase):
    def test_suspicion_has_one_0_to_100_state_and_linear_pp_mapping(self) -> None:
        effects = read(EFFECTS)
        refresh = named_block(effects, "STP_refresh_party_suspicion")
        change = named_block(effects, "STP_change_party_suspicion")

        self.assertIn("var = STP_party_suspicion", refresh)
        self.assertIn("min = 0", refresh)
        self.assertIn("max = 100", refresh)
        self.assertIn("var = STP_sus_political_power_factor", refresh)
        self.assertIn("value = -0.007", refresh)
        self.assertIn("value = 0.35", refresh)
        self.assertIn("force_update_dynamic_modifier = yes", refresh)
        self.assertIn("value = STP_party_suspicion_change", change)
        self.assertIn("STP_refresh_party_suspicion = yes", change)

        history = read(HISTORY)
        self.assertRegex(history, r"set_variable\s*=\s*\{\s*var\s*=\s*STP_party_suspicion\s+value\s*=\s*5\s*\}")
        self.assertNotIn("var = STP_sus_political_power_factor", history)

        modifier = named_block(read(DYNAMIC_MODIFIERS), "STP_party_suspicion_dynamic_modifier")
        self.assertIn("political_power_factor = STP_sus_political_power_factor", modifier)

    def test_apparatus_loyalty_has_one_0_to_100_state_and_linear_pp_mapping(self) -> None:
        effects = read(EFFECTS)
        refresh = named_block(effects, "STP_refresh_apparatus_loyalty")
        change = named_block(effects, "STP_change_apparatus_loyalty")
        init = named_block(effects, "STP_cw_init_apparatus_loyalty")

        self.assertIn("var = STP_apparatus_loyalty", refresh)
        self.assertIn("min = 0", refresh)
        self.assertIn("max = 100", refresh)
        self.assertIn("var = STP_loy_political_power_factor", refresh)
        self.assertIn("value = 0.004", refresh)
        self.assertIn("value = -0.20", refresh)
        self.assertIn("var = STP_loy_stability_factor", refresh)
        self.assertIn("value = 0.001", refresh)
        self.assertIn("value = -0.05", refresh)
        self.assertIn("force_update_dynamic_modifier = yes", refresh)
        self.assertIn("value = STP_apparatus_loyalty_change", change)
        self.assertIn("STP_refresh_apparatus_loyalty = yes", change)
        self.assertIn("value = 40", init)
        self.assertIn("STP_party_suspicion_dynamic_modifier", init)
        self.assertIn("STP_apparatus_loyalty_dynamic_modifier", init)
        self.assertIn("STP_cw_init_apparatus_loyalty = yes", named_block(effects, "STP_cw_open_preparation"))

        modifier = named_block(read(DYNAMIC_MODIFIERS), "STP_apparatus_loyalty_dynamic_modifier")
        self.assertIn("political_power_factor = STP_loy_political_power_factor", modifier)
        self.assertIn("stability_factor = STP_loy_stability_factor", modifier)
        display = read(SCRIPTED_LOC)
        self.assertIn("name = STP_display_party_suspicion", display)
        self.assertLess(display.index("STP_sided_with_the_party_flag"),
                        display.index("STP_display_apparatus_loyalty_loc"))
        self.assertIn("STP_display_party_suspicion_loc", display)

    def test_health_has_one_discrete_five_stage_state_shared_with_inlay(self) -> None:
        effects = read(EFFECTS)
        refresh = named_block(effects, "STP_refresh_leader_health")
        setter = named_block(effects, "STP_set_leader_health_stage")

        self.assertIn("var = STP_leader_health_stage", refresh)
        self.assertIn("min = 1", refresh)
        self.assertIn("max = 5", refresh)
        for value in ("-0.05", "-0.10", "-0.20", "-0.30"):
            self.assertIn(f"value = {value}", refresh)
        self.assertIn("set_country_flag = STP_ivanov_dead", refresh)
        self.assertIn("clr_country_flag = STP_ivanov_dead", refresh)
        self.assertIn("force_update_dynamic_modifier = yes", refresh)
        self.assertIn("value = STP_requested_health_stage", setter)
        self.assertIn("STP_refresh_leader_health = yes", setter)

        history = read(HISTORY)
        self.assertRegex(history, r"set_variable\s*=\s*\{\s*var\s*=\s*STP_leader_health_stage\s+value\s*=\s*1\s*\}")
        self.assertNotIn("var = STP_fading_father_stability_factor", history)

        inlay = read(INLAY)
        for stage in range(2, 6):
            self.assertIn(f"check_variable = {{ STP_leader_health_stage = {stage} }}", inlay)

        stability = named_block(read(DYNAMIC_MODIFIERS), "STP_fading_father")
        self.assertIn("stability_factor = STP_fading_father_stability_factor", stability)
        self.assertNotIn("political_power", stability)

    def test_runtime_has_no_abandoned_mirror_or_rate_variables(self) -> None:
        runtime_sources = "\n".join(
            read(path)
            for path in (
                EFFECTS,
                DECISIONS,
                DYNAMIC_MODIFIERS,
                INLAY,
                SCRIPTED_LOC,
                LOCALISATION,
                HISTORY,
            )
        )
        for legacy in (
            "STP_party_suspicion_rate",
            "STP_leader_health_rate",
            "STP_leader_health_temp",
        ):
            with self.subTest(legacy=legacy):
                self.assertNotIn(legacy, runtime_sources)

        self.assertNotRegex(runtime_sources, r"\bvar\s*=\s*STP_state_face_stage\b")
        self.assertNotIn("check_variable = { STP_state_face_stage =", runtime_sources)

    def test_ivanov_death_portrait_remains_until_the_election_split(self) -> None:
        effects = parse_clausewitz(read(EFFECTS))
        refresh = block(effects, "STP_refresh_leader_health")
        for stage in range(1, 6):
            for present in (False, True):
                facts = {("STP", "variable", "STP_leader_health_stage"): stage,
                         ("STP", "has_character", "STP_Petr_Ivanov"): present}
                changes = [e.value for _, e in selected_effects(refresh, facts) if e.key == "set_portraits"]
                self.assertEqual(len(changes), int(present), (stage, present))
                if present:
                    self.assertEqual(scalar(changes[0], "character"), "STP_Petr_Ivanov")
                    suffix = "_animated" if stage == 5 else ""
                    self.assertEqual(scalar(block(changes[0], "civilian"), "large"),
                                     "GFX_portrait_STP_Petr_Ivanov" + suffix)

        election = named_block(read(EFFECTS), "STP_cw_begin_elections")
        self.assertNotIn("retire_character", election)
        self.assertNotIn("promote_character", election)
        start = named_block(read(EFFECTS), "STP_cw_start")
        self.assertIn("retire_character = STP_Petr_Ivanov", start)
        self.assertIn("promote_character = STP_rufus_hedersett", start)

    def test_ivanov_animation_frames_match_the_portrait_width(self) -> None:
        portrait = (ROOT / "gfx/leaders/STP/portrait_STP_Petr_Ivanov.png").read_bytes()
        self.assertEqual(portrait[:8], b"\x89PNG\r\n\x1a\n")
        width, height = struct.unpack_from(">II", portrait, 16)
        for path, name in (
            ("interface/ADISCORD_leader_portraits.gfx", "GFX_portrait_STP_Petr_Ivanov_animated"),
            ("interface/ADISCORD_stp_state_face.gfx", "GFX_STP_state_face_dead"),
        ):
            with self.subTest(sprite=name):
                sprites = block(parse_clausewitz(read(ROOT / path)), "spriteTypes")
                animation = next(entry.value for entry in sprites
                                 if entry.key == "frameAnimatedSpriteType"
                                 and scalar(entry.value, "name") == name)
                texture = (ROOT / scalar(animation, "texturefile")).read_bytes()
                self.assertEqual(texture[:4], b"DDS ")
                atlas_height, atlas_width = struct.unpack_from("<II", texture, 12)
                self.assertEqual(atlas_height, height)
                self.assertEqual(atlas_width, width * int(scalar(animation, "noOfFrames")),
                                 "animation must advance by a complete portrait, not a slice of its neighbours")

    def test_debug_decisions_replace_disposable_test_decision(self) -> None:
        decisions = read(DECISIONS)
        self.assertNotIn("STP_test = {", decisions)
        for decision in (
            "STP_debug_increase_suspicion",
            "STP_debug_decrease_suspicion",
            "STP_debug_worsen_ivanov",
            "STP_debug_improve_ivanov",
        ):
            self.assertIn(f"{decision} = {{", decisions)

        localisation = read(LOCALISATION)
        for decision in (
            "STP_debug_increase_suspicion",
            "STP_debug_decrease_suspicion",
            "STP_debug_worsen_ivanov",
            "STP_debug_improve_ivanov",
        ):
            self.assertRegex(localisation, rf"(?m)^\s*{decision}:\s+\"§RDEBUG:§!")

    def test_scenario_debug_skips_the_civil_war_through_production_effects(self) -> None:
        categories = named_block(read(DECISION_CATEGORIES), "STP_scenario_debug")
        self.assertIn("visible = { is_debug = yes }", categories)
        self.assertIn("tag = STP", categories)
        self.assertIn("tag = STS", categories)
        self.assertIn("visible_when_empty = yes", categories)

        debug = named_block(read(DECISIONS), "STP_scenario_debug")
        start = named_block(debug, "STP_debug_start_civil_war")
        party = named_block(debug, "STP_debug_resolve_party_victory")
        shabrat = named_block(debug, "STP_debug_resolve_shabrat_victory")
        self.assertIn("STP_debug_start_civil_war = yes", start)
        self.assertIn("STP_debug_resolve_party_victory = yes", party)
        self.assertIn("STP_debug_resolve_shabrat_victory = yes", shabrat)
        for block in (start, party, shabrat):
            self.assertIn("is_debug = yes", named_block(block, "visible"))
            self.assertIn("ai_will_do = { factor = 0 }", block)
            self.assertIn("hidden_effect", block)

        effects = read(EFFECTS)
        ensure = named_block(effects, "STP_debug_ensure_union_war")
        self.assertIn("STP_cw_open_preparation = yes", ensure)
        self.assertIn("set_country_flag = STP_cw_elections_finished", ensure)
        self.assertIn("STP_cw_start = yes", ensure)
        self.assertIn("STP_cw_begin_hostilities = yes", ensure)
        self.assertNotIn("STP_cw_can_start = yes", ensure)

        party_effect = named_block(effects, "STP_debug_resolve_party_victory")
        shabrat_effect = named_block(effects, "STP_debug_resolve_shabrat_victory")
        self.assertIn("set_country_flag = STP_cw_party_election_victory", party_effect)
        self.assertIn("STS = { country_event = { id = ADISCORD_STP_cw.93 hours = 1 } }", party_effect)
        self.assertIn("set_country_flag = STP_cw_shabrat_election_victory", shabrat_effect)
        self.assertIn("STP = { country_event = { id = ADISCORD_STP_cw.93 hours = 1 } }", shabrat_effect)
        self.assertIn("change_tag_from = STS", party_effect)
        self.assertIn("change_tag_from = STP", shabrat_effect)

        events = read(ROOT / "events/ADISCORD_STP_events.txt")
        dispatcher = next(
            candidate
            for match in re.finditer(r"(?m)^country_event\s*=", events)
            if "id = ADISCORD_STP_cw.93" in (candidate := named_block(events[match.start():], "country_event"))
        )
        self.assertIn("hidden = yes", dispatcher)
        self.assertIn("STP_cw_settle_union_victory = yes", dispatcher)
        self.assertIn("if = { limit = { tag = STS } STP = { STP_cw_settle_union_victory = yes } }", dispatcher)
        self.assertIn("else_if = { limit = { tag = STP } STS = { STP_cw_settle_union_victory = yes } }", dispatcher)

        localisation = read(LOCALISATION)
        for key in (
            "STP_scenario_debug",
            "STP_debug_start_civil_war",
            "STP_debug_resolve_party_victory",
            "STP_debug_resolve_shabrat_victory",
        ):
            self.assertRegex(localisation, rf"(?m)^\s*{key}:\s+\"§RDEBUG:§!")

    def test_debug_controls_cannot_bypass_the_normal_election_campaign(self) -> None:
        decisions = read(DECISIONS)
        names = re.findall(r"^\s*(STP_debug_\w+)\s*=\s*\{", decisions, re.MULTILINE)
        self.assertTrue(names)
        for name in names:
            self.assertIn("is_debug = yes", named_block(named_block(decisions, name), "visible"), name)

    def test_bop_debug_decisions_shift_election_legitimacy_in_hidden_bop_category(self) -> None:
        bop = named_block(read(BOP), "STP_shabrat_election_legitimacy")
        self.assertIn("decision_category = STP_shabrat_election_bop_category", bop)

        categories = read(DECISION_CATEGORIES)
        category = named_block(categories, "STP_shabrat_election_bop_category")
        self.assertIn("allowed = { tag = STP }", category)
        for ordinary_category_field in (
            "visible =",
            "visible_when_empty =",
            "picture =",
            "priority =",
        ):
            self.assertNotIn(ordinary_category_field, category)

        decisions = named_block(read(DECISIONS), "STP_shabrat_election_bop_category")
        expected_values = {
            "STP_debug_increase_party_bop": "-0.25",
            "STP_debug_increase_shabrat_bop": "0.25",
        }
        for decision, value in expected_values.items():
            with self.subTest(decision=decision):
                block = named_block(decisions, decision)
                self.assertIn("id = STP_shabrat_election_legitimacy", block)
                self.assertIn(f"value = {value}", block)

        localisation = read(LOCALISATION)
        required_keys = (
            "STP_shabrat_election_legitimacy",
            "STP_party_election_legitimacy_side",
            "STP_shabrat_election_legitimacy_side",
            "STP_election_legitimacy_contested_range",
            "STP_party_election_low_control_range",
            "STP_party_election_medium_control_range",
            "STP_party_election_high_control_range",
            "STP_party_election_total_control_range",
            "STP_shabrat_election_low_control_range",
            "STP_shabrat_election_medium_control_range",
            "STP_shabrat_election_high_control_range",
            "STP_shabrat_election_total_control_range",
            "STP_shabrat_election_bop_category",
            "STP_cw_bop_shabrat_majority_preview_tt",
            "STP_cw_bop_shabrat_strong_preview_tt",
        )
        for key in required_keys:
            with self.subTest(key=key):
                self.assertRegex(localisation, rf"(?m)^\s*{key}:")

        for decision in expected_values:
            self.assertRegex(
                localisation,
                rf'(?m)^\s*{decision}:\s+"§RDEBUG:§! BOP:',
            )
        self.assertTrue(LOCALISATION.read_bytes().startswith(b"\xef\xbb\xbf"))

    def test_startup_uses_one_core_initializer_for_mechanics_and_army_lock(self) -> None:
        effects = read(EFFECTS)
        initializer = named_block(effects, "STP_initialize_core_mechanics")
        self.assertIn("STP_refresh_party_suspicion = yes", initializer)
        self.assertIn("STP_refresh_leader_health = yes", initializer)
        self.assertIn("STP_party_suspicion_dynamic_modifier", initializer)
        self.assertIn("STP_fading_father", initializer)
        self.assertIn("ADISCORD_STP_lock_regular_army_templates = yes", initializer)

        startup = read(ON_ACTIONS)
        self.assertEqual(startup.count("STP_initialize_core_mechanics = yes"), 1)
        self.assertNotIn("ADISCORD_STP_lock_regular_army_templates = yes", startup)

    def test_preparation_starts_with_party_advantage_without_erasing_campaign_progress(self) -> None:
        opening = block(parse_clausewitz(read(EFFECTS)), "STP_cw_open_preparation")
        for guard, current, expected in (
            (None, 0.0, -0.20),
            (("has_country_flag", "STP_cw_legitimacy_initialized"), 0.36, 0.36),
            (("has_country_flag", "STP_cw_elections_finished"), 0.36, 0.36),
            (("has_global_flag", "STP_cw_started"), 0.36, 0.36),
        ):
            with self.subTest(guard=guard):
                facts = {("STP", *guard): True} if guard else {}
                result = current
                for scope, effect in selected_effects(opening, facts):
                    if (scope == "STP" and effect.key == "set_power_balance"
                            and scalar(effect.value, "id") == "STP_shabrat_election_legitimacy"):
                        # set_power_balance only assigns progress through set_value.
                        for parameter in effect.value:
                            if parameter.key == "set_value":
                                result = float(parameter.value)
                self.assertAlmostEqual(result, expected)

    def test_mission_deadline_tokens_are_synchronized_for_multiplayer(self) -> None:
        registered = set()
        for path in (ROOT / "common/synchronized_dynamic_tokens").glob("*.txt"):
            registered.update(re.findall(r"(?m)^\s*([A-Za-z_][A-Za-z0-9_]*)\s*$", read(path)))
        references = set()
        for path in (EFFECTS, DECISIONS,
                     ROOT / "common/scripted_triggers/ADISCORD_STP_scripted_triggers.txt"):
            references.update(re.findall(r"\bdays_mission_timeout@([A-Za-z_][A-Za-z0-9_]*)", read(path)))
        self.assertTrue(references, "The intervention must read the existing deadline")
        self.assertFalse(references - registered, f"Unsynchronized mission tokens: {references - registered}")

    def test_scripted_localisation_is_limited_to_status_and_inlay_contracts(self) -> None:
        scripted_loc = read(SCRIPTED_LOC)
        for retained in (
            "STPGetSuspicionValue",
            "STPGetSuspicionBand",
            "STPGetSuspicionExplanation",
            "STPGetLoyaltyValue",
            "STPGetLoyaltyBand",
            "STPGetLoyaltyExplanation",
            "STP_display_party_suspicion",
            "STPGetStateFaceStageName",
            "STPGetStateFaceTooltip",
        ):
            self.assertIn(f"name = {retained}", scripted_loc)

        for removed in (
            "name = PeterHealth",
            "name = STPGetLeaderHealthStageName",
            "name = STPGetLeaderHealthTooltip",
        ):
            self.assertNotIn(removed, scripted_loc)


if __name__ == "__main__":
    unittest.main()
