"""Regression contract for Shabrat's postwar economy and development branches."""

from pathlib import Path
from tools.lib.focus_sources import read_focus_source
import unittest

ROOT = Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    return read_focus_source(ROOT / path, encoding="utf-8-sig")


def focus_block(text: str, focus_id: str) -> str:
    marker = f"id = {focus_id}"
    pos = text.index(marker)
    start = text.rfind("\n\tfocus = {", 0, pos) + 1
    brace = text.index("{", start)
    depth = 0
    for index in range(brace, len(text)):
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    raise AssertionError(f"unclosed focus {focus_id}")


class ShabratPostwarEconomyTests(unittest.TestCase):
    def test_development_choices_rejoin_and_campaigns_follow_their_own_focus(self):
        from tools.tests.test_adiscord_stp_preparation import block, entries, scalar

        focuses = {scalar(e.value, "id"): e.value for e in entries(
            "focus_trees/STP/postwar/shabrat/focuses.txt") if e.key == "focus"}
        left = "STP_pc_development_rebuild_as_duty"
        right = "STP_pc_development_engineers_on_radio"
        for chosen, excluded in ((left, right), (right, left)):
            self.assertEqual(scalar(block(focuses[chosen], "mutually_exclusive"), "focus"), excluded)
        merge = focuses["STP_pc_development_generation_reconstruction"]
        self.assertEqual({e.value for e in block(merge, "prerequisite")}, {left, right})
        campaigns = block(entries("common/decisions/ADISCORD_STP_decisions.txt"),
                          "STP_postwar_propaganda_campaigns")
        mapping = {
            "STP_pw_campaign_victory_means_normal_life": "STP_pw_republic_new_republic",
            "STP_pw_campaign_country_is_being_built": "STP_pw_republic_restore_roads",
            "STP_pw_campaign_engineers_of_peace": "STP_pc_economy_repair_workshops",
            "STP_pw_campaign_one_steland": "STP_pc_two_borders",
        }
        for decision, focus_id in mapping.items():
            self.assertEqual(scalar(block(block(campaigns, decision), "visible"),
                                    "has_completed_focus"), focus_id)
            rewards = block(focuses[focus_id], "completion_reward")
            self.assertIn(decision, [e.value for e in rewards if e.key == "unlock_decision_tooltip"])
        for focus_id, direction in (
            ("STP_pw_republic_civil_records", "state"),
            ("STP_pw_republic_civil_workshops", "economic"),
            ("STP_pc_two_borders", "state"),
        ):
            body = focus_block(read("common/national_focus/ADISCORD_national_focus_STP.txt"), focus_id)
            self.assertIn("ADISCORD_increase_" + direction + "_development_monthly_growth = yes", body)

    def test_central_reconstruction_space_respects_other_route_nodes(self):
        from tools.tests.test_adiscord_stp_preparation import entries, scalar

        focuses = {scalar(e.value, "id"): e.value for e in entries(
            "focus_trees/STP/postwar/shabrat/focuses.txt") if e.key == "focus"}
        moved = ["STP_pc_development_" + suffix for suffix in (
            "country_must_live", "posters_on_ruins", "rebuild_as_duty",
            "engineers_on_radio", "generation_reconstruction")]
        for focus_id in moved:
            x = int(scalar(focuses[focus_id], "x"))
            y = int(scalar(focuses[focus_id], "y"))
            self.assertTrue(20 <= x <= 24)
            for other_id, other in focuses.items():
                if other_id == focus_id or int(scalar(other, "y")) != y:
                    continue
                self.assertGreaterEqual(abs(x - int(scalar(other, "x"))), 2,
                                        (focus_id, other_id))

    def test_unification_rebuilds_economy_after_annexation(self):
        effects = read("common/scripted_effects/ADISCORD_STP_scripted_effects.txt")
        self.assertIn("STP_pw_rebuild_economy_after_unification = {", effects)
        start = effects.index("STP_pw_rebuild_economy_after_unification = {")
        body = effects[start : start + 4000]
        for token in (
            "ADISCORD_economy_initialize_country = yes",
            "ADISCORD_economy_mark_dirty = yes",
            "ADISCORD_economy_full_refresh = yes",
            "ADISCORD_economy_light_update = yes",
            "ADISCORD_economy_update_gui = yes",
            "ADISCORD_economy_receive_50 = yes",
        ):
            self.assertIn(token, body)

        settlement = effects[effects.index("STP_cw_settle_union_victory = {") :]
        settlement = settlement[: settlement.index("\nSTP_cw_settle_nod_victory = {")]
        self.assertLess(
            settlement.index("annex_country = { target = ROOT transfer_troops = no }"),
            settlement.index("STP_pw_rebuild_economy_after_unification = yes"),
        )

    def test_republic_dynamic_exposes_economic_and_development_recovery(self):
        dynamic = read("common/dynamic_modifiers/ADISCORD_dynamic_modifiers_STP.txt")
        republic = dynamic[dynamic.index("STP_pw_republic_dynamic = {") :]
        republic = republic[: republic.index("\nSTP_pw_party_dynamic = {")]
        for token in (
            "ADISCORD_economy_overall_income_factor = STP_pw_ADISCORD_economy_overall_income_factor",
            "ADISCORD_economy_treasury_capacity_factor = STP_pw_ADISCORD_economy_treasury_capacity_factor",
            "ADISCORD_economy_creditworthiness_factor = STP_pw_ADISCORD_economy_creditworthiness_factor",
            "ADISCORD_country_development_global_growth_factor = STP_pw_ADISCORD_country_development_global_growth_factor",
            "ADISCORD_country_development_economic_growth_factor = STP_pw_ADISCORD_country_development_economic_growth_factor",
            "ADISCORD_country_development_state_growth_factor = STP_pw_ADISCORD_country_development_state_growth_factor",
            "ADISCORD_country_development_society_growth_factor = STP_pw_ADISCORD_country_development_society_growth_factor",
        ):
            self.assertIn(token, republic)

    def test_economy_branch_is_separate_and_material(self):
        focus = read("common/national_focus/ADISCORD_national_focus_STP.txt")
        ids = (
            "STP_pc_economy_count_the_cost",
            "STP_pc_economy_reopen_tax_offices",
            "STP_pc_economy_repair_workshops",
            "STP_pc_economy_stabilize_currency",
            "STP_pc_economy_recovery_budget",
        )
        for focus_id in ids:
            self.assertIn(f"id = {focus_id}", focus)
        self.assertIn("prerequisite = { focus = STP_pc_after_victory }", focus)
        for token in (
            "STP_pw_ADISCORD_economy_overall_income_factor",
            "STP_pw_ADISCORD_economy_treasury_capacity_factor",
            "STP_pw_ADISCORD_economy_creditworthiness_factor",
            "STP_receive_900 = yes",
        ):
            self.assertIn(token, focus)

    def test_development_propaganda_branch_grows_country(self):
        focus = read("common/national_focus/ADISCORD_national_focus_STP.txt")
        ids = (
            "STP_pc_development_country_must_live",
            "STP_pc_development_posters_on_ruins",
            "STP_pc_development_rebuild_as_duty",
            "STP_pc_development_engineers_on_radio",
            "STP_pc_development_generation_reconstruction",
        )
        for focus_id in ids:
            self.assertIn(f"id = {focus_id}", focus)
        for token in (
            "ADISCORD_increase_society_development_monthly_growth = yes",
            "ADISCORD_increase_state_development_monthly_growth = yes",
            "ADISCORD_increase_economic_development_monthly_growth = yes",
            "STP_pw_ADISCORD_country_development_global_growth_factor",
            "STP_pw_ADISCORD_country_development_economic_growth_factor",
            "STP_pw_ADISCORD_country_development_state_growth_factor",
            "STP_pw_ADISCORD_country_development_society_growth_factor",
        ):
            self.assertIn(token, focus)

    def test_postwar_research_slots_are_unlocked_by_two_distinct_focuses(self):
        focus = read("common/national_focus/ADISCORD_national_focus_STP.txt")
        first_id = "STP_pc_development_reopen_universities"
        second_id = "STP_pc_development_national_research_institutes"
        for focus_id in (first_id, second_id):
            self.assertIn(f"id = {focus_id}", focus)

        first_block = focus_block(focus, first_id)
        second_block = focus_block(focus, second_id)
        self.assertEqual(first_block.count("add_research_slot = 1"), 1)
        self.assertEqual(second_block.count("add_research_slot = 1"), 1)
        self.assertIn(
            "prerequisite = { focus = STP_pc_development_generation_reconstruction }",
            first_block,
        )
        self.assertIn(
            "prerequisite = { focus = STP_pc_development_generation_reconstruction }",
            second_block,
        )
        self.assertIn(
            "prerequisite = { focus = STP_pc_economy_recovery_budget }", second_block
        )
        self.assertIn(
            "prerequisite = { focus = STP_pc_development_reopen_universities }",
            second_block,
        )

        ai = read("common/ai_strategy_plans/ADISCORD_STP_plans.txt")
        self.assertIn(first_id, ai)
        self.assertIn(second_id, ai)

    def test_new_focuses_have_russian_localisation(self):
        focus = read("common/national_focus/ADISCORD_national_focus_STP.txt")
        loc = read("localisation/russian/ADISCORD_STP_l_russian.yml")
        for focus_id in (
            "STP_pc_economy_count_the_cost",
            "STP_pc_economy_reopen_tax_offices",
            "STP_pc_economy_repair_workshops",
            "STP_pc_economy_stabilize_currency",
            "STP_pc_economy_recovery_budget",
            "STP_pc_development_country_must_live",
            "STP_pc_development_posters_on_ruins",
            "STP_pc_development_rebuild_as_duty",
            "STP_pc_development_engineers_on_radio",
            "STP_pc_development_generation_reconstruction",
            "STP_pc_development_reopen_universities",
            "STP_pc_development_national_research_institutes",
        ):
            self.assertIn(f"id = {focus_id}", focus)
            self.assertIn(f"{focus_id}:", loc)
            self.assertIn(f"{focus_id}_desc:", loc)


if __name__ == "__main__":
    unittest.main()
