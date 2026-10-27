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

    def test_development_branch_layout_respects_other_route_nodes(self):
        from tools.tests.test_adiscord_stp_preparation import entries, scalar

        focuses = {scalar(e.value, "id"): e.value for e in entries(
            "focus_trees/STP/postwar/shabrat/focuses.txt") if e.key == "focus"}

        def position(focus_id):
            focus = focuses[focus_id]
            x, y = int(scalar(focus, "x")), int(scalar(focus, "y"))
            relative_to = next((e.value for e in focus if e.key == "relative_position_id"), None)
            if relative_to:
                parent_x, parent_y = position(relative_to)
                x += parent_x
                y += parent_y
            return x, y

        positions = {focus_id: position(focus_id) for focus_id in focuses}
        prefix = "STP_pc_development_"
        anchor_x, anchor_y = positions[prefix + "country_must_live"]
        for suffix, dx, dy in (
            ("posters_on_ruins", 0, 1),
            ("rebuild_as_duty", -2, 2),
            ("engineers_on_radio", 2, 2),
            ("generation_reconstruction", 0, 3),
        ):
            self.assertEqual(positions[prefix + suffix], (anchor_x + dx, anchor_y + dy))
        development = {name: xy for name, xy in positions.items() if name.startswith(prefix)}
        economy_right = max(x for name, (x, _) in positions.items()
                            if name.startswith(("STP_pc_economy_", "STP_pc_investment_")))
        self.assertGreaterEqual(min(x for x, _ in development.values()) - economy_right, 2)
        for focus_id, (x, y) in development.items():
            for other_id, (other_x, other_y) in positions.items():
                if other_id == focus_id or other_y != y:
                    continue
                self.assertGreaterEqual(abs(x - other_x), 2,
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


class ShabratCivicProgrammeTests(unittest.TestCase):
    PRICES = {
        "district_staff": (100, 0),
        "district_clinics": (35, 540),
        "research_grants": (50, 900),
        "veteran_instructors": (75, 360),
        "district_roads": (75, 900),
        "civil_enterprises": (100, 1800),
    }

    @classmethod
    def setUpClass(cls):
        from tools.tests.test_adiscord_stp_preparation import block, entries

        cls.decisions = {
            entry.key: entry.value
            for entry in block(
                entries("common/decisions/ADISCORD_STP_decisions.txt"),
                "STP_pw_programme",
            )
        }
        cls.triggers = {
            entry.key: entry.value
            for entry in entries("common/scripted_triggers/ADISCORD_STP_scripted_triggers.txt")
        }

    def test_exact_prices_and_fractional_shortfalls_are_atomic(self):
        from tools.tests.test_adiscord_stp_preparation import (
            block, matches_conditions, scalar, selected_effects,
        )

        for suffix, (power, money) in self.PRICES.items():
            key = "STP_pw_civic_" + suffix
            decision = self.decisions[key]
            self.assertEqual(scalar(decision, "cost"), "0")
            for power_delta, money_delta, current in (
                (0, 0, True), (-0.01, 0, True), (0, -0.01, True),
                (100, 1000, True), (0, 0, False),
            ):
                if not money and money_delta:
                    continue
                facts = {
                    ("STS", "numeric", "has_political_power"): power + power_delta,
                    ("STS", "variable", "ADISCORD_economy_treasury"): money + money_delta,
                    ("STS", key + "_ready", "yes"): current,
                }
                affordable = power_delta >= 0 and money_delta >= 0
                with self.subTest(programme=suffix, facts=facts):
                    self.assertEqual(matches_conditions(
                        block(decision, "custom_cost_trigger"), facts, "STS"
                    ), affordable)
                    applied = list(selected_effects(
                        block(decision, "complete_effect"), facts, "STS"
                    ))
                    if not (affordable and current):
                        self.assertEqual(applied, [])
                        continue
                    power_changes = [
                        float(entry.value) for scope, entry in applied
                        if entry.key == "add_political_power"
                    ]
                    self.assertEqual(power_changes, [-power])
                    treasury = [
                        float(scalar(entry.value, "value")) for scope, entry in applied
                        if entry.key == "subtract_from_variable"
                        and scalar(entry.value, "var") == "ADISCORD_economy_treasury"
                    ]
                    ledger = [
                        float(scalar(entry.value, "value")) for scope, entry in applied
                        if entry.key == "add_to_variable"
                        and scalar(entry.value, "var") == "ADISCORD_economy_current_month_action_costs"
                    ]
                    self.assertEqual(treasury, [money] if money else [])
                    self.assertEqual(ledger, treasury)
                    self.assertIn("ADISCORD_economy_mark_dirty", [e.key for _, e in applied])

    def test_development_blocks_wasted_purchases_at_maximum_or_pending_level(self):
        from tools.tests.test_adiscord_stp_preparation import matches_conditions

        for suffix, axis, focus in (
            ("district_staff", "state", "STP_pc_after_victory"),
            ("district_clinics", "social_system", "STP_pc_after_victory"),
            ("research_grants", "science", "STP_pc_development_reopen_universities"),
        ):
            trigger = self.triggers["STP_pw_civic_" + suffix + "_ready"]
            for level, progress, expected in ((4, 99, True), (5, 0, False), (4, 100, False)):
                facts = {
                    ("STS", "STP_pw_can_reconstruct", "yes"): True,
                    ("STS", "has_completed_focus", focus): True,
                    ("STS", "variable", f"ADISCORD_{axis}_development_level"): level,
                    ("STS", "variable", f"ADISCORD_{axis}_development_progress"): progress,
                }
                with self.subTest(programme=suffix, level=level, progress=progress):
                    self.assertEqual(matches_conditions(trigger, facts, "STS"), expected)
                    facts[("STS", "STP_pw_can_reconstruct", "yes")] = False
                    self.assertFalse(matches_conditions(trigger, facts, "STS"))

    def test_roads_recheck_live_state_before_payment_and_preserve_capacity(self):
        from tools.tests.test_adiscord_stp_preparation import block, matches_conditions, walk

        key = "STP_pw_civic_district_roads"
        trigger = self.triggers[key + "_ready"]
        facts = {
            ("STS", "STP_pw_can_reconstruct", "yes"): True,
            ("STS", "has_completed_focus", "STP_pw_republic_restore_roads"): True,
            ("FROM", "is_owned_by", "ROOT"): True,
            ("FROM", "is_controlled_by", "ROOT"): True,
            ("FROM", "is_core_of", "STP"): True,
            ("FROM", "numeric", "infrastructure"): 4,
        }
        self.assertTrue(matches_conditions(trigger, facts, "STS"))
        for changed, value in (
            (("FROM", "is_owned_by", "ROOT"), False),
            (("FROM", "is_controlled_by", "ROOT"), False),
            (("FROM", "is_core_of", "STP"), False),
            (("FROM", "numeric", "infrastructure"), 5),
        ):
            self.assertFalse(matches_conditions(trigger, {**facts, changed: value}, "STS"))
        for suffix in ("district_roads", "civil_enterprises"):
            decision = self.decisions["STP_pw_civic_" + suffix]
            targets = block(decision, "target_trigger")
            self.assertFalse(any(e.key in ("check_variable", "free_building_slots") for e in walk(targets)))
            self.assertFalse(any(e.key == "add_extra_state_shared_building_slots" for e in walk(decision)))
        factory = self.triggers["STP_pw_civic_civil_enterprises_ready"]
        slots = block(block(factory, "FROM"), "free_building_slots")
        self.assertIn(("include_locked", "no"), [(e.key, e.value) for e in slots])

    def test_instructors_do_not_waste_experience_above_the_mod_cap(self):
        from tools.tests.test_adiscord_stp_preparation import matches_conditions

        trigger = self.triggers["STP_pw_civic_veteran_instructors_ready"]
        for experience, expected in ((975, True), (975.01, False), (1000, False)):
            facts = {
                ("STS", "STP_pw_can_reconstruct", "yes"): True,
                ("STS", "has_completed_focus", "STP_pw_republic_army_register"): True,
                ("STS", "numeric", "has_army_experience"): experience,
            }
            self.assertEqual(matches_conditions(trigger, facts, "STS"), expected)

    def test_programmes_survive_first_plan_and_have_focus_unlocks_and_localisation(self):
        import re
        from tools.tests.test_adiscord_stp_preparation import block, entries, matches_conditions, scalar

        category = block(entries("common/decisions/categories/ADISCORD_decision_categories_STP.txt"), "STP_pw_programme")
        facts = {
            ("STS", "has_country_flag", "STP_cw_postwar"): True,
            ("STS", "has_completed_focus", "STP_pc_after_victory"): True,
            ("STS", "has_country_flag", "STP_pw_reconstruction_drive_completed"): True,
        }
        self.assertTrue(matches_conditions(block(category, "allowed"), facts, "STS"))
        self.assertTrue(matches_conditions(block(category, "visible"), facts, "STS"))
        source = read("focus_trees/STP/postwar/shabrat/focuses.txt")
        for suffix in self.PRICES:
            key = "STP_pw_civic_" + suffix
            self.assertIn("unlock_decision_tooltip = " + key, source)
            self.assertEqual(scalar(self.decisions[key], "fire_only_once"), "no")
        for language in ("russian", "english"):
            path = ROOT / f"localisation/{language}/ADISCORD_STP_l_{language}.yml"
            self.assertTrue(path.read_bytes().startswith(b"\xef\xbb\xbf"))
            values = dict(re.findall(r'^ ([\w.]+):(?:\d+)? "([^"\r\n]*)"$', path.read_text(encoding="utf-8-sig"), re.M))
            for suffix, (power, money) in self.PRICES.items():
                key = "STP_pw_civic_" + suffix
                for ending in ("", "_desc", "_ready_tt", "_cost", "_cost_blocked", "_cost_tooltip"):
                    self.assertIn(key + ending, values)
                for ending in ("_cost", "_cost_blocked", "_cost_tooltip"):
                    self.assertIn(str(power) + "§! £political_power_texticon", values[key + ending])
                    if money:
                        self.assertIn(str(money) + "§! £ADISCORD_economy_treasury_texticon", values[key + ending])


if __name__ == "__main__":
    unittest.main()
