import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from tools.stp_val_crisis_manifest import (
    CIVIL_WAR_STATE_MAP,
    DECISION_CATEGORIES,
    DEATH_CAMPAIGN_DAY,
    HEALTH_STAGE_DAYS,
    LEADERS,
    NOD_LIMITED_TARGET_STATES,
    NOD_POSTURES,
    NODE_LIMITS,
    POSTWAR_FOCUS_IDS,
    RESOURCE_STATES,
    VAL_AUTHORITY_FOCUS_REWARDS,
    VAL_CONTRACT_BANDS,
    VAL_STP_INTEL_STATES,
    WAR_COUNTDOWN_MISSIONS,
)


class CrisisManifestTests(unittest.TestCase):
    def test_health_calendar_reaches_day_267(self):
        self.assertEqual(HEALTH_STAGE_DAYS, (70, 70, 63, 63))
        self.assertEqual(DEATH_CAMPAIGN_DAY, 267)
        self.assertEqual(sum(HEALTH_STAGE_DAYS), DEATH_CAMPAIGN_DAY - 1)

    def test_successors_have_distinct_ideology_groups(self):
        self.assertEqual(LEADERS["shabrat"], ("STP_maksim_shabrat", "chauvinism_ideology", "chauvinism"))
        self.assertEqual(LEADERS["sotnikov"], ("STP_grigory_sotnikov", "etatism_ideology", "etatism"))
        self.assertEqual(LEADERS["hedersett"], ("STP_rufus_hedersett", "aristocratic_hedonism", "hedonism"))
        self.assertEqual(len({group for _, _, group in LEADERS.values()}), 3)

    def test_node_limits_and_resource_states_are_fixed(self):
        self.assertEqual(NODE_LIMITS["palace"], 2)
        self.assertEqual(NODE_LIMITS["officers"], 3)
        self.assertEqual(NODE_LIMITS["mountains"], 3)
        self.assertEqual(NODE_LIMITS["market"], 2)
        self.assertEqual(NODE_LIMITS["street"], 2)
        self.assertEqual(NODE_LIMITS["val_channel"], 2)
        self.assertEqual(RESOURCE_STATES, (45, 88))
        self.assertEqual(VAL_STP_INTEL_STATES, (43, 44, 45, 88))
        self.assertEqual(len(POSTWAR_FOCUS_IDS), 15)

    def test_cross_file_ids_are_canonical(self):
        self.assertEqual(len(DECISION_CATEGORIES), 5)
        self.assertEqual(len(NOD_POSTURES), 5)
        self.assertEqual(NOD_LIMITED_TARGET_STATES["YPR"], (15, 19))
        self.assertEqual(WAR_COUNTDOWN_MISSIONS[-1], "STP_VAL_war_countdown_breached")
        self.assertEqual(set().union(*CIVIL_WAR_STATE_MAP.values()), {1, 2, 3, 28, 29, 43, 44, 45, 46, 53, 88})

    def test_val_authority_focus_rewards_are_complete(self):
        self.assertEqual(
            VAL_AUTHORITY_FOCUS_REWARDS,
            {
                "VAL_The_Contract_State": 5,
                "VAL_The_Weaponry_Baron": 10,
                "VAL_Export_Rifles_Not_Promises": 5,
                "VAL_Morns_Supply_Trains": 5,
                "VAL_Dead_Villages_Still_Count": 5,
                "VAL_Different_Views_On_Freedom": 5,
            },
        )
        self.assertEqual(sum(VAL_AUTHORITY_FOCUS_REWARDS.values()), 35)

    def test_val_contract_bands_cover_the_full_authority_range(self):
        self.assertEqual(
            VAL_CONTRACT_BANDS,
            (
                {"minimum": 0, "maximum": 24, "modifiers": {"org": 3, "org_regain": 2, "daily_pp": -0.10}},
                {
                    "minimum": 25,
                    "maximum": 49,
                    "modifiers": {"attack": 3, "defence": 3, "org": 5, "org_regain": 3, "capture": 2, "planning": -5, "daily_pp": -0.10},
                },
                {
                    "minimum": 50,
                    "maximum": 74,
                    "modifiers": {"attack": 6, "defence": 5, "org": 8, "org_regain": 5, "capture": 5, "supply": -3, "planning": -5, "state_overload": 3, "trade_income": 3, "military_industry_income": 3, "army_expense": -3},
                },
                {
                    "minimum": 75,
                    "maximum": 89,
                    "modifiers": {"attack": 10, "defence": 8, "org": 10, "org_regain": 8, "capture": 8, "supply": -5, "planning": -10, "daily_pp": -0.20, "state_overload": 5, "trade_income": 5, "military_industry_income": 5, "army_expense": -5},
                },
                {
                    "minimum": 90,
                    "maximum": 100,
                    "modifiers": {"attack": 12, "defence": 10, "org": 12, "org_regain": 10, "capture": 10, "supply": -7, "planning": -15, "daily_pp": -0.25, "stability": -5, "state_overload": 8, "trade_income": 7, "military_industry_income": 7, "army_expense": -7},
                },
            ),
        )


from tools import validate_adiscord_stp_val_crisis as validator


class CrisisValidatorTests(unittest.TestCase):
    def test_empty_root_reports_each_feature_layer(self):
        with TemporaryDirectory() as tmp:
            issues = validator.validate(Path(tmp))
        self.assertTrue(any("core scripted effects" in issue for issue in issues))
        self.assertTrue(any("STP crisis decisions" in issue for issue in issues))
        self.assertTrue(any("VAL contract events" in issue for issue in issues))
        self.assertTrue(any("crisis GUI" in issue for issue in issues))

    def test_unknown_section_is_rejected(self):
        with TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                validator.validate(Path(tmp), "unknown")

    def test_feature_file_checks_are_brace_aware_and_performance_safe(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            for files in validator.REQUIRED_FILES.values():
                for relative_path, _ in files:
                    path = root / relative_path
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text("outer = { # } in comment\n value = { }\n", encoding="utf-8-sig")

            core = root / validator.REQUIRED_FILES["core"][0][0]
            core.write_text("outer = {\n on_daily = { }\n every_country = { }\n", encoding="utf-8-sig")
            issues = validator.validate(root, "core")

        self.assertTrue(any("unbalanced braces" in issue for issue in issues))
        self.assertTrue(any("on_daily" in issue for issue in issues))
        self.assertTrue(any("unrestricted every_country" in issue for issue in issues))

    def test_extract_named_block_ignores_braces_in_comments(self):
        text = "target = { value = { } # }\n }\nother = { }"
        self.assertEqual(validator.extract_named_block(text, "target"), "{ value = { } # }\n }")


if __name__ == "__main__":
    unittest.main()
