"""Exercise editorial reward lint through parsed, isolated Clausewitz sources."""

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from tools.validators import validate_focus_rewards as rewards


class LoadedFocusRewardTests(unittest.TestCase):
    def test_loaded_mod_has_no_known_weak_standalone_rewards(self):
        self.assertEqual(rewards.collect_issues(), [])


class FocusRewardTests(unittest.TestCase):
    def setUp(self):
        self.workspace = TemporaryDirectory()
        self.addCleanup(self.workspace.cleanup)
        self.root = Path(self.workspace.name)

    def write(self, path, source):
        destination = self.root / path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(source, encoding="utf-8")

    def focus(self, reward, cost=3, focus_id="sample", kind="focus"):
        self.write(
            "common/national_focus/sample.txt",
            f"focus_tree = {{ {kind} = {{ id = {focus_id} cost = {cost} "
            f"completion_reward = {{ {reward} }} }} }}",
        )
        return rewards.audit(self.root).focuses[0]

    def test_small_hidden_equipment_and_experience_remain_weak(self):
        result = self.focus(
            "hidden_effect = { add_equipment_to_stockpile = "
            "{ type = support_equipment amount = 100 } army_experience = 5 }"
        )
        self.assertEqual(result.classification, "weak")
        self.assertAlmostEqual(result.score, 0.4583333333)
        self.assertEqual(len(rewards.collect_issues(self.root)), 1)

    def test_threshold_tracks_28_day_cost(self):
        result = self.focus("add_political_power = 25", cost=4)
        self.assertEqual(result.classification, "weak")
        self.assertAlmostEqual(result.threshold, 4 / 3)

    def test_preview_and_tooltip_are_not_executed_rewards(self):
        result = self.focus(
            "effect_tooltip = { add_ideas = giant_bonus add_manpower = 100000 } "
            "custom_effect_tooltip = looks_strong unlock_decision_tooltip = nonexistent"
        )
        self.assertEqual(result.classification, "weak")
        self.assertEqual(result.score, 0)

    def test_consumable_bundle_passes_at_exact_boundary(self):
        result = self.focus("add_political_power = 37.5 army_experience = 20")
        self.assertEqual(result.classification, "consumable")
        self.assertEqual(result.score, 1)

    def test_negative_rewards_never_inflate_the_score(self):
        result = self.focus("add_manpower = -9000 add_political_power = 25")
        self.assertEqual(result.classification, "weak")
        self.assertAlmostEqual(result.score, 1 / 3)

    def test_same_currency_debit_cancels_plain_reward(self):
        result = self.focus("add_political_power = -75 add_political_power = 75")
        self.assertEqual(result.classification, "weak")
        self.assertEqual(result.score, 0)

    def test_same_currency_debit_cancels_hidden_reward(self):
        result = self.focus("add_political_power = -75 hidden_effect = { add_political_power = 75 }")
        self.assertEqual(result.classification, "weak")
        self.assertEqual(result.score, 0)

    def test_same_currency_debit_cancels_scripted_reward(self):
        self.write("common/scripted_effects/sample.txt", "grant = { add_political_power = 75 }")
        result = self.focus("add_political_power = -75 grant = yes")
        self.assertEqual(result.classification, "weak")
        self.assertEqual(result.score, 0)

    def test_canceled_currency_does_not_erase_a_useful_different_currency(self):
        result = self.focus("add_political_power = -75 add_political_power = 75 army_experience = 40")
        self.assertEqual(result.classification, "consumable")
        self.assertEqual(result.score, 1)

    def test_equipment_aliases_cancel_as_one_resource(self):
        result = self.focus(
            "add_equipment_to_stockpile = { type = support_equipment amount = -300 } "
            "hidden_effect = { add_equipment_to_stockpile = "
            "{ type = support_equipment_1 amount = 300 } }"
        )
        self.assertEqual(result.classification, "weak")
        self.assertEqual(result.score, 0)

    def test_cash_cancellation_ignores_monthly_bookkeeping(self):
        self.write(
            "common/scripted_effects/sample.txt",
            "grant = { add_to_variable = { var = ADISCORD_economy_treasury value = 600 } "
            "add_to_variable = { var = ADISCORD_economy_current_month_action_income value = 600 } }",
        )
        result = self.focus(
            "hidden_effect = { subtract_from_variable = "
            "{ var = ADISCORD_economy_treasury value = 600 } grant = yes }"
        )
        self.assertEqual(result.classification, "weak")
        self.assertEqual(result.score, 0)

    def test_equipment_aliases_have_same_real_threshold(self):
        for equipment, amount in (
            ("support_equipment_1", 300),
            ("infantry_equipment_1", 9000),
            ("ADISCORD_infantry_equipment_3", 9000),
        ):
            with self.subTest(equipment=equipment):
                result = self.focus(
                    "add_equipment_to_stockpile = "
                    f"{{ type = {equipment} amount = {amount} }}"
                )
                self.assertEqual(result.classification, "consumable")
                self.assertEqual(result.score, 1)

    def test_research_permanent_events_and_native_buildings_are_not_scored(self):
        for reward in (
            "add_tech_bonus = { bonus = 0.5 uses = 1 category = industry }",
            "add_ideas = permanent_spirit",
            "country_event = { id = story.1 days = 1 }",
            "add_extra_state_shared_building_slots = 1",
        ):
            with self.subTest(reward=reward):
                self.assertEqual(self.focus(reward).classification, "substantive")

    def test_unresolved_effect_is_explicit_semantic_review(self):
        result = self.focus("new_unknown_script = yes add_political_power = 5")
        self.assertEqual(result.classification, "semantic_review")
        self.assertIn("new_unknown_script", result.review_effects)
        self.assertEqual(rewards.collect_issues(self.root), [])

    def test_conditional_rewards_are_not_summed_as_guaranteed(self):
        result = self.focus(
            "if = { limit = { has_war = yes } add_political_power = 75 } "
            "else = { army_experience = 40 }"
        )
        self.assertEqual(result.classification, "semantic_review")
        self.assertEqual(result.score, 0)

    def test_real_external_completed_focus_consumer_exempts_milestone(self):
        self.write(
            "common/decisions/sample.txt",
            "category = { operation = { visible = { has_completed_focus = sample } "
            "complete_effect = { add_manpower = 4000 } } }",
        )
        result = self.focus("add_political_power = 5")
        self.assertEqual(result.classification, "external_milestone")

    def test_category_visibility_is_a_real_focus_unlock(self):
        self.write(
            "common/decisions/categories/sample.txt",
            "category = { visible = { has_completed_focus = sample } }",
        )
        self.assertEqual(self.focus("unlock_decision_tooltip = operation").classification, "external_milestone")

    def test_selection_effect_is_not_mistaken_for_an_empty_completion(self):
        self.write(
            "common/national_focus/sample.txt",
            "focus_tree = { focus = { id = sample cost = 3 "
            "select_effect = { country_event = { id = story.1 } } "
            "completion_reward = { custom_effect_tooltip = story_tt } } }",
        )
        result = rewards.audit(self.root).focuses[0]
        self.assertEqual(result.classification, "substantive")

    def test_ai_and_focus_prerequisites_are_not_gameplay_milestone_consumers(self):
        self.write(
            "common/decisions/sample.txt",
            "category = { operation = { ai_will_do = { modifier = "
            "{ has_completed_focus = sample factor = 2 } } } }",
        )
        self.write(
            "common/ai_strategy/sample.txt",
            "strategy = { enable = { has_completed_focus = sample } }",
        )
        self.assertEqual(self.focus("add_political_power = 5").classification, "weak")

    def test_external_country_flag_reader_exempts_real_capability(self):
        self.write(
            "common/decisions/sample.txt",
            "category = { operation = { visible = { has_country_flag = capability } "
            "complete_effect = { add_manpower = 4000 } } }",
        )
        result = self.focus("set_country_flag = capability add_political_power = 5")
        self.assertEqual(result.classification, "external_milestone")

    def test_flag_gated_diplomatic_relation_is_a_real_decision_unlock(self):
        self.write(
            "common/decisions/sample.txt",
            "category = { recognition = { visible = { has_country_flag = recognition_ready } "
            "complete_effect = { if = { limit = { ROM = { exists = yes } } "
            "diplomatic_relation = { country = ROM relation = non_aggression_pact active = yes } "
            "} } } }",
        )
        result = self.focus(
            "add_political_power = 10 add_stability = 0.01 "
            "unlock_decision_tooltip = recognition "
            "hidden_effect = { set_country_flag = recognition_ready }",
            cost=2,
        )
        self.assertEqual(result.classification, "external_milestone")
        self.assertEqual(rewards.collect_issues(self.root), [])

    def test_writers_and_self_guarding_flags_cannot_fake_a_capability(self):
        self.write(
            "common/scripted_effects/sample.txt",
            "guard = { if = { limit = { NOT = { has_country_flag = bookkeeping } } "
            "set_country_flag = bookkeeping clamp_variable = "
            "{ var = counter min = 0 max = 10 } } }",
        )
        result = self.focus("set_country_flag = bookkeeping add_political_power = 5")
        self.assertEqual(result.classification, "weak")

    def test_marker_reader_in_unrelated_guard_does_not_borrow_another_effect_reward(self):
        self.write(
            "common/scripted_effects/sample.txt",
            "guard = { if = { limit = { NOT = { has_country_flag = bookkeeping } } "
            "set_country_flag = bookkeeping } add_political_power = 75 }",
        )
        result = self.focus("set_country_flag = bookkeeping add_political_power = 5")
        self.assertEqual(result.classification, "weak")

    def test_transparent_script_cash_does_not_double_count_the_monthly_ledger(self):
        self.write(
            "common/scripted_effects/sample.txt",
            "grant = { hidden_effect = { add_to_variable = "
            "{ var = ADISCORD_economy_treasury value = 300 } add_to_variable = "
            "{ var = ADISCORD_economy_current_month_action_income value = 300 } "
            "ADISCORD_economy_mark_dirty = yes } }",
        )
        result = self.focus("grant = yes")
        self.assertEqual(result.classification, "weak")
        self.assertEqual(result.score, 0.5)

    def test_resource_cap_requires_review_instead_of_guaranteeing_full_payment(self):
        result = self.focus(
            "add_to_variable = { var = ADISCORD_economy_treasury value = 600 } "
            "clamp_variable = { var = ADISCORD_economy_treasury min = 0 max = 300 }"
        )
        self.assertEqual(result.classification, "semantic_review")

    def test_only_live_scripted_trigger_consumers_exempt_a_focus(self):
        self.write(
            "common/scripted_triggers/sample.txt",
            "milestone_ready = { has_completed_focus = sample }",
        )
        self.assertEqual(self.focus("add_political_power = 5").classification, "weak")
        self.write(
            "common/decisions/sample.txt",
            "category = { operation = { visible = { milestone_ready = yes } "
            "complete_effect = { add_manpower = 4000 } } }",
        )
        self.assertEqual(self.focus("add_political_power = 5").classification, "external_milestone")

    def test_bookkeeping_focus_reader_cannot_fake_a_gameplay_consumer(self):
        self.write(
            "common/scripted_effects/sample.txt",
            "unused = { if = { limit = { has_completed_focus = sample } "
            "set_country_flag = marker } }",
        )
        self.assertEqual(self.focus("add_political_power = 5").classification, "weak")

    def test_native_equipment_and_unit_transfers_are_meaningful_focus_consumers(self):
        for payload in (
            "send_equipment = { type = ADISCORD_fighter_archetype amount = airframes target = STP }",
            "transfer_units_fraction = { target = STP air_ratio = 0.25 }",
        ):
            with self.subTest(payload=payload):
                self.write(
                    "common/scripted_effects/sample.txt",
                    "transfer = { if = { limit = { has_completed_focus = sample } "
                    f"{payload} }} }}",
                )
                self.assertEqual(self.focus("custom_effect_tooltip = transfer_tt").classification, "external_milestone")

    def test_focus_guarding_opaque_state_mutation_requires_semantic_review(self):
        self.write(
            "common/scripted_effects/sample.txt",
            "production_cycle = { if = { limit = { NOT = { has_completed_focus = sample } } "
            "add_to_variable = { var = unrest value = 4 } } }",
        )
        result = self.focus("custom_effect_tooltip = unrest_tt")
        self.assertEqual(result.classification, "semantic_review")
        self.assertIn("external_state_consumer", result.review_effects)

    def test_preview_only_focus_reader_cannot_fake_a_gameplay_consumer(self):
        self.write(
            "common/scripted_effects/sample.txt",
            "preview = { if = { limit = { has_completed_focus = sample } "
            "effect_tooltip = { add_manpower = 4000 } } }",
        )
        self.assertEqual(self.focus("add_political_power = 5").classification, "weak")

    def test_native_event_trigger_remains_a_story_consumer(self):
        self.write(
            "events/sample.txt",
            "country_event = { id = story.1 trigger = { has_completed_focus = sample } "
            "option = { name = close } }",
        )
        self.assertEqual(self.focus("add_political_power = 5").classification, "external_milestone")

    def test_macro_and_recursive_script_calls_require_semantic_review(self):
        self.write("common/scripted_effects/sample.txt", "loop = { loop = yes }")
        for call in ("loop = yes", "loop = { AMOUNT = 600 }"):
            with self.subTest(call=call):
                self.assertEqual(self.focus(call).classification, "semantic_review")

    def test_shared_definitions_are_audited_and_bookmark_preview_is_explicitly_excluded(self):
        self.write(
            "common/national_focus/ADISCORD_national_focus_bookmark.txt",
            "focus_tree = { focus = { id = preview cost = 3 completion_reward = {} } }",
        )
        result = self.focus("add_political_power = 5", kind="shared_focus")
        report = rewards.audit(self.root)
        self.assertEqual(result.classification, "weak")
        self.assertEqual(report.counts["excluded_preview"], 1)
        self.assertEqual(report.counts["weak"], 1)
        self.assertEqual(len(report.focuses), 1)


if __name__ == "__main__":
    unittest.main()
