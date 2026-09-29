"""Island ownership, independence and treaty contracts; not engine simulation."""

import unittest

from tools.tests.test_adiscord_stp_preparation import (
    block,
    entries,
    matches_conditions,
    scalar,
    selected_effects,
    walk,
)


class StelanderIslandsTests(unittest.TestCase):
    def test_starting_mandate_has_its_own_state(self):
        state = block(entries("history/states/709-Stelander-Islands.txt"), "state")
        self.assertEqual(scalar(block(state, "history"), "owner"), "SLI")
        self.assertEqual(
            {int(item.value) for item in block(state, "provinces")},
            set(range(16802, 16809)),
        )
        history = entries("history/countries/NOD - Nodral.txt")
        mandates = [entry.value for entry in history if entry.key == "set_autonomy"]
        mandate = next(item for item in mandates if scalar(item, "target") == "SLI")
        self.assertEqual(
            scalar(mandate, "autonomy_state"), "autonomy_NOD_protected_administration"
        )

    def test_independence_releases_nod_mandate_and_changes_flag_once(self):
        effect = block(
            entries("common/scripted_effects/ADISCORD_SLI_effects.txt"),
            "SLI_declare_independence",
        )
        facts = {
            ("SLI", "exists", "yes"): True,
            ("SLI", "has_cosmetic_tag", "SLI_mandate"): True,
            ("SLI", "is_subject_of", "NOD"): True,
        }
        result = list(selected_effects(effect, facts, "SLI"))
        release = next(
            item.value for scope, item in result
            if scope == "NOD" and item.key == "set_autonomy"
        )
        self.assertEqual(scalar(release, "autonomy_state"), "autonomy_free")
        self.assertEqual(scalar(release, "target"), "SLI")
        self.assertEqual(scalar(release, "end_wars"), "yes")
        self.assertTrue(any(
            scope == "SLI" and item.key == "drop_cosmetic_tag"
            for scope, item in result
        ))
        facts[("SLI", "has_cosmetic_tag", "SLI_mandate")] = False
        self.assertEqual(list(selected_effects(effect, facts, "SLI")), [])
        facts[("SLI", "has_cosmetic_tag", "SLI_mandate")] = True
        facts[("SLI", "is_subject_of", "NOD")] = False
        self.assertEqual(list(selected_effects(effect, facts, "SLI")), [])
        start = block(
            entries("common/scripted_effects/ADISCORD_STP_scripted_effects.txt"),
            "STP_cw_begin_hostilities",
        )
        calls = sum(item.key == "SLI_declare_independence" for item in walk(start))
        self.assertEqual(calls, 1)

    def test_treaty_rechecks_subject_war_and_ownership(self):
        trigger = block(
            entries("common/scripted_triggers/ADISCORD_VAL_rework_triggers.txt"),
            "VAL_island_treaty_available",
        )
        facts = {
            ("VAL", "exists", "yes"): True,
            ("VAL", "is_subject", "no"): True,
            ("VAL", "has_capitulated", "no"): True,
            ("VAL", "has_global_flag", "STP_cw_started"): True,
            ("SLI", "exists", "yes"): True,
            ("SLI", "is_subject", "no"): True,
            ("SLI", "is_in_faction", "no"): True,
            ("SLI", "has_war", "no"): True,
            ("SLI", "owns_state", "709"): True,
            ("SLI", "controls_state", "709"): True,
        }
        self.assertTrue(matches_conditions(trigger, facts, "VAL"))
        for key in facts:
            changed = {**facts, key: False}
            with self.subTest(key=key):
                self.assertFalse(matches_conditions(trigger, changed, "VAL"))

    def test_decision_annexes_immediately_without_council_choice(self):
        category = block(entries("common/decisions/ADISCORD_VAL_decisions.txt"), "VAL_frontier")
        decision = block(category, "VAL_Island_Treaty")
        self.assertEqual(scalar(decision, "cost"), "0")
        self.assertEqual(scalar(block(decision, "visible"), "has_completed_focus"), "VAL_Contracts_Outlive_Kings")
        self.assertEqual(scalar(block(block(decision, "available"), "custom_trigger_tooltip"), "VAL_island_treaty_available"), "yes")
        for eligible in (False, True):
            effects = list(selected_effects(
                block(decision, "complete_effect"),
                {("VAL", "VAL_island_treaty_available", "yes"): eligible},
                "VAL",
            ))
            annexations = [item.value for scope, item in effects if scope == "VAL" and item.key == "annex_country"]
            self.assertEqual(len(annexations), int(eligible))
            if eligible:
                self.assertEqual(scalar(annexations[0], "target"), "SLI")
                self.assertEqual(scalar(annexations[0], "transfer_troops"), "yes")
            self.assertFalse(any(item.key == "declare_war_on" for _, item in effects))
        events = entries("events/ADISCORD_SLI_events.txt")
        self.assertFalse(any(scalar(item.value, "id") == "ADISCORD_SLI.2" for item in events if isinstance(item.value, list)))


if __name__ == "__main__":
    unittest.main()
