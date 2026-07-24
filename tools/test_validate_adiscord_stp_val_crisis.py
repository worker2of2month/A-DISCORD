import unittest
import re
import struct
from pathlib import Path
from tempfile import TemporaryDirectory

from tools.stp_val_crisis_manifest import (
    CIVIL_WAR_STATE_MAP,
    DECISION_CATEGORIES,
    DEATH_CAMPAIGN_DAY,
    HEALTH_MISSIONS,
    HEALTH_STAGE_DAYS,
    LEADERS,
    NOD_LIMITED_TARGET_STATES,
    NOD_POSTURES,
    NODE_LIMITS,
    POSTWAR_FOCUS_IDS,
    RESOURCE_STATES,
    RESISTANCE_POSTURES,
    SECURITY_POSTURES,
    STP_CRISIS_FOCUS_REWARDS,
    STP_CRISIS_FOCUS_STAGES,
    STP_PARTY_FOCUSES,
    STP_SHABRAT_FOCUSES,
    STP_SPINE_FOCUS_STAGES,
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

    def test_task_three_manifest_is_exact_and_non_overlapping(self):
        self.assertEqual(
            HEALTH_MISSIONS,
            {
                "STP_health_stage_1_to_2": (70, "stp_crisis.1"),
                "STP_health_stage_2_to_3": (70, "stp_crisis.2"),
                "STP_health_stage_3_to_4": (63, "stp_crisis.3"),
                "STP_health_stage_4_to_death": (63, "stp_crisis.4"),
            },
        )
        self.assertEqual(len(STP_CRISIS_FOCUS_STAGES), 40)
        self.assertEqual(set(STP_CRISIS_FOCUS_STAGES), set(STP_CRISIS_FOCUS_REWARDS))
        self.assertFalse(set(STP_SHABRAT_FOCUSES) & set(STP_PARTY_FOCUSES))
        self.assertEqual(set(STP_SPINE_FOCUS_STAGES), {1, 2, 3, 4, 5})
        self.assertEqual(set(SECURITY_POSTURES), {1, 2, 3, 4, 5})
        self.assertEqual(set(RESISTANCE_POSTURES), {1, 2, 3, 4})

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
    def _block_with_assignment(self, text: str, block_name: str, assignment: str) -> str:
        masked_text = validator._mask_non_code(text)
        pattern = re.compile(rf"\b{re.escape(block_name)}\b\s*=\s*\{{")
        parsed_assignment = re.fullmatch(
            r"([A-Za-z0-9_]+)\s*=\s*(.+)", assignment
        )
        if parsed_assignment is None:
            self.fail(f"unsupported assignment lookup: {assignment}")
        key, value = parsed_assignment.groups()
        value_boundary = "" if value.startswith('"') else r"(?![A-Za-z0-9_.])"
        assignment_pattern = re.compile(
            rf"(?<![A-Za-z0-9_]){re.escape(key)}\s*=\s*"
            rf"{re.escape(value)}{value_boundary}"
        )
        matches = []
        for match in pattern.finditer(masked_text):
            opening_brace = masked_text.index("{", match.start())
            depth = 0
            closing_brace = None
            for index in range(opening_brace, len(masked_text)):
                if masked_text[index] == "{":
                    depth += 1
                elif masked_text[index] == "}":
                    depth -= 1
                    if depth == 0:
                        closing_brace = index
                        break
            if closing_brace is None:
                continue
            block = text[opening_brace : closing_brace + 1]
            masked = validator._mask_non_code(block)
            for assignment_match in assignment_pattern.finditer(block):
                index = assignment_match.start()
                if masked[:index].count("{") - masked[:index].count("}") == 1:
                    outer_depth = (
                        masked_text[: match.start()].count("{")
                        - masked_text[: match.start()].count("}")
                    )
                    matches.append((outer_depth, -len(block), block))
                    break
        return min(matches, default=(0, 0, ""))[2]

    def _assert_stp_modifier_contract(self, refresh: str) -> None:
        def direct_blocks(text: str, identifier: str) -> list[str]:
            masked = validator._mask_non_code(text)
            pattern = re.compile(rf"\b{re.escape(identifier)}\b\s*=\s*\{{")
            blocks = []
            for match in pattern.finditer(masked):
                prefix = masked[: match.start()]
                if prefix.count("{") - prefix.count("}") != 1:
                    continue
                opening = masked.index("{", match.start())
                depth = 0
                for index in range(opening, len(masked)):
                    if masked[index] == "{":
                        depth += 1
                    elif masked[index] == "}":
                        depth -= 1
                        if depth == 0:
                            blocks.append(text[opening : index + 1])
                            break
            return blocks

        def assignments(block: str, direct_only: bool = False) -> dict[str, float]:
            source = (
                direct_blocks(block, "set_variable")
                if direct_only
                else list(validator._iter_named_blocks(block, "set_variable"))
            )
            parsed = {}
            for assignment in source:
                masked = validator._mask_non_code(assignment)
                variable = re.search(r"\bvar\s*=\s*([A-Za-z0-9_]+)", masked)
                value = re.search(r"\bvalue\s*=\s*(-?\d+(?:\.\d+)?)", masked)
                if variable and value:
                    parsed[variable.group(1)] = float(value.group(1))
            return parsed

        def checks(block: str, driver: str) -> set[tuple[float, str]]:
            parsed = set()
            for check in validator._iter_named_blocks(block, "check_variable"):
                masked = validator._mask_non_code(check)
                variable = re.search(r"\bvar\s*=\s*([A-Za-z0-9_]+)", masked)
                value = re.search(r"\bvalue\s*=\s*(-?\d+(?:\.\d+)?)", masked)
                compare = re.search(r"\bcompare\s*=\s*([A-Za-z_]+)", masked)
                if variable and value and variable.group(1) == driver:
                    parsed.add(
                        (
                            float(value.group(1)),
                            compare.group(1) if compare else "equals",
                        )
                    )
            return parsed

        threshold_branches = direct_blocks(refresh, "if") + direct_blocks(refresh, "else_if")

        def branch_for(driver: str, expected_checks: set[tuple[float, str]]) -> str:
            matches = [
                branch
                for branch in threshold_branches
                if checks(branch, driver) == expected_checks
            ]
            self.assertEqual(
                len(matches),
                1,
                f"{driver} branch {sorted(expected_checks)} must exist exactly once",
            )
            return matches[0]

        baseline = assignments(refresh, direct_only=True)
        expected_baseline = {
            "STP_fading_pp_factor": 0.0,
            "STP_fading_stability_factor": 0.0,
            "STP_fading_command_power_factor": 0.0,
            "STP_fading_planning_factor": 0.0,
            "STP_fading_org_factor": 0.0,
            "STP_network_stability_factor": 0.0,
            "STP_network_consumer_goods_factor": 0.0,
            "STP_pressure_stability_factor": 0.0,
            "STP_pressure_pp_factor": 0.0,
            "STP_pressure_factory_output_factor": 0.0,
        }
        self.assertEqual(baseline, expected_baseline)

        table_contracts = (
            (
                "STP_leader_health_stage",
                {
                    frozenset({(2.0, "equals")}): {
                        "STP_fading_pp_factor": -0.05,
                        "STP_fading_stability_factor": -0.02,
                        "STP_fading_command_power_factor": -0.05,
                    },
                    frozenset({(3.0, "equals")}): {
                        "STP_fading_pp_factor": -0.10,
                        "STP_fading_stability_factor": -0.05,
                        "STP_fading_command_power_factor": -0.10,
                        "STP_fading_planning_factor": -0.05,
                    },
                    frozenset({(4.0, "greater_than_or_equals")}): {
                        "STP_fading_pp_factor": -0.20,
                        "STP_fading_stability_factor": -0.10,
                        "STP_fading_command_power_factor": -0.20,
                        "STP_fading_planning_factor": -0.10,
                        "STP_fading_org_factor": -0.05,
                    },
                },
            ),
            (
                "STP_resistance_readiness",
                {
                    frozenset(
                        {(25.0, "greater_than_or_equals"), (50.0, "less_than")}
                    ): {
                        "STP_network_stability_factor": -0.02,
                        "STP_network_consumer_goods_factor": 0.01,
                    },
                    frozenset(
                        {(50.0, "greater_than_or_equals"), (75.0, "less_than")}
                    ): {
                        "STP_network_stability_factor": -0.04,
                        "STP_network_consumer_goods_factor": 0.02,
                    },
                    frozenset(
                        {(75.0, "greater_than_or_equals"), (90.0, "less_than")}
                    ): {
                        "STP_network_stability_factor": -0.07,
                        "STP_network_consumer_goods_factor": 0.03,
                    },
                    frozenset({(90.0, "greater_than_or_equals")}): {
                        "STP_network_stability_factor": -0.10,
                        "STP_network_consumer_goods_factor": 0.04,
                    },
                },
            ),
            (
                "STP_party_suspicion",
                {
                    frozenset(
                        {(25.0, "greater_than_or_equals"), (50.0, "less_than")}
                    ): {
                        "STP_pressure_stability_factor": -0.02,
                        "STP_pressure_pp_factor": -0.05,
                    },
                    frozenset(
                        {(50.0, "greater_than_or_equals"), (75.0, "less_than")}
                    ): {
                        "STP_pressure_stability_factor": -0.05,
                        "STP_pressure_pp_factor": -0.10,
                        "STP_pressure_factory_output_factor": -0.03,
                    },
                    frozenset(
                        {(75.0, "greater_than_or_equals"), (90.0, "less_than")}
                    ): {
                        "STP_pressure_stability_factor": -0.10,
                        "STP_pressure_pp_factor": -0.15,
                        "STP_pressure_factory_output_factor": -0.05,
                    },
                    frozenset({(90.0, "greater_than_or_equals")}): {
                        "STP_pressure_stability_factor": -0.15,
                        "STP_pressure_pp_factor": -0.20,
                        "STP_pressure_factory_output_factor": -0.10,
                    },
                },
            ),
        )
        for driver, branches in table_contracts:
            for expected_checks, expected_assignments in branches.items():
                branch = branch_for(driver, set(expected_checks))
                self.assertEqual(assignments(branch), expected_assignments)

        lifecycle_contract = {
            "STP_fading_father": (
                "STP_main_campaign_side",
                "STP_ivanov_dead",
            ),
            "STP_underground_network": (
                "STP_main_campaign_side",
                "STP_internal_war_started",
            ),
            "STP_security_pressure": (
                "STP_main_campaign_side",
                "STP_internal_outcome_finalized",
            ),
        }
        top_level_if = direct_blocks(refresh, "if")
        top_level_else = direct_blocks(refresh, "else")
        dynamic = validator.read(
            validator.ROOT
            / "common/dynamic_modifiers/ADISCORD_STP_VAL_crisis_dynamic_modifiers.txt"
        ) or ""
        for modifier, (positive_flag, negative_flag) in lifecycle_contract.items():
            add_branches = [
                block
                for block in top_level_if
                if any(
                    re.search(
                        rf"\bmodifier\s*=\s*{re.escape(modifier)}\b",
                        validator._mask_non_code(operation),
                    )
                    for operation in validator._iter_named_blocks(
                        block, "add_dynamic_modifier"
                    )
                )
            ]
            self.assertEqual(len(add_branches), 1, f"{modifier} add lifecycle")
            add_branch = add_branches[0]
            limit = validator.extract_named_block(add_branch, "limit") or ""
            masked_limit = validator._mask_non_code(limit)
            self.assertEqual(
                set(re.findall(r"\bhas_country_flag\s*=\s*([A-Za-z0-9_]+)", masked_limit)),
                {positive_flag, negative_flag},
            )
            negative_blocks = list(validator._iter_named_blocks(limit, "NOT"))
            self.assertTrue(
                any(
                    re.search(
                        rf"\bhas_country_flag\s*=\s*{re.escape(negative_flag)}\b",
                        validator._mask_non_code(block),
                    )
                    for block in negative_blocks
                ),
                f"{modifier} must negate {negative_flag}",
            )
            self.assertFalse(
                any(
                    re.search(
                        rf"\bhas_country_flag\s*=\s*{re.escape(positive_flag)}\b",
                        validator._mask_non_code(block),
                    )
                    for block in negative_blocks
                ),
                f"{modifier} must require {positive_flag}",
            )
            self.assertTrue(
                any(
                    re.search(
                        rf"\bmodifier\s*=\s*{re.escape(modifier)}\b",
                        validator._mask_non_code(block),
                    )
                    for block in validator._iter_named_blocks(
                        add_branch, "has_dynamic_modifier"
                    )
                ),
                f"{modifier} add must be idempotently guarded",
            )

            remove_branches = [
                block
                for block in top_level_else
                if any(
                    re.search(
                        rf"\bmodifier\s*=\s*{re.escape(modifier)}\b",
                        validator._mask_non_code(operation),
                    )
                    for operation in validator._iter_named_blocks(
                        block, "remove_dynamic_modifier"
                    )
                )
            ]
            self.assertEqual(len(remove_branches), 1, f"{modifier} remove lifecycle")

            definition = validator.extract_named_block(dynamic, modifier) or ""
            enable = validator.extract_named_block(definition, "enable") or ""
            masked_enable = validator._mask_non_code(enable)
            self.assertEqual(
                set(re.findall(r"\bhas_country_flag\s*=\s*([A-Za-z0-9_]+)", masked_enable)),
                {positive_flag, negative_flag},
            )
            enable_not = list(validator._iter_named_blocks(enable, "NOT"))
            self.assertEqual(len(enable_not), 1)
            self.assertRegex(
                validator._mask_non_code(enable_not[0]),
                rf"\bhas_country_flag\s*=\s*{re.escape(negative_flag)}\b",
            )

    def _write_required_files(self, root: Path, text: str = "feature = { }") -> None:
        for files in validator.REQUIRED_FILES.values():
            for relative_path, _ in files:
                path = root / relative_path
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text, encoding="utf-8-sig")

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

    def test_every_country_requires_a_direct_limit_block(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_required_files(root)
            core = root / validator.REQUIRED_FILES["core"][0][0]

            core.write_text("every_country = { limit = { tag = STP } }", encoding="utf-8-sig")
            direct_limit_issues = validator.validate(root, "core")

            core.write_text("every_country = { if = { limit = { tag = STP } } }", encoding="utf-8-sig")
            nested_limit_issues = validator.validate(root, "core")

        self.assertFalse(any("unrestricted every_country" in issue for issue in direct_limit_issues))
        self.assertTrue(any("unrestricted every_country" in issue for issue in nested_limit_issues))

    def test_on_daily_identifier_in_an_event_id_is_allowed(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_required_files(root)
            core = root / validator.REQUIRED_FILES["core"][0][0]
            core.write_text("country_event = { id = on_daily.1 }", encoding="utf-8-sig")
            issues = validator.validate(root, "core")

        self.assertFalse(any("on_daily is forbidden" in issue for issue in issues))

    def test_full_validation_deduplicates_performance_findings(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_required_files(root)
            core = root / validator.REQUIRED_FILES["core"][0][0]
            core.write_text("on_daily = { }", encoding="utf-8-sig")
            issues = validator.validate(root)

        self.assertEqual(len(issues), len(set(issues)))
        self.assertEqual(sum("on_daily is forbidden" in issue for issue in issues), 1)

    def test_stp_validator_rejects_calendar_and_focus_window_mutations(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            for relative in (
                "common/decisions/categories/ADISCORD_STP_VAL_crisis_categories.txt",
                "common/decisions/ADISCORD_STP_crisis_decisions.txt",
                "events/ADISCORD_STP_crisis_events.txt",
                "common/national_focus/ADISCORD_national_focus_STP.txt",
                "common/on_actions/01_ADISCORD_STP_VAL_crisis_on_actions.txt",
                "common/scripted_effects/ADISCORD_STP_VAL_crisis_core_effects.txt",
                "common/focus_inlay_windows/ADISCORD_STP_state_face_inlay_window.txt",
                "common/scripted_localisation/ADISCORD_STP_leader_health_scripted_loc.txt",
                "common/scripted_localisation/ADISCORD_STP_state_face_scripted_loc.txt",
                "common/scripted_localisation/ADISCORD_STP_party_elections_scripted_loc.txt",
                "localisation/russian/ADISCORD_stp_state_face_l_russian.yml",
                "localisation/russian/ADISCORD_STP_party_elections_l_russian.yml",
            ):
                source = validator.ROOT / relative
                target = root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(source.read_bytes())

            decisions = root / "common/decisions/ADISCORD_STP_crisis_decisions.txt"
            decisions.write_text(
                decisions.read_text(encoding="utf-8-sig").replace(
                    "days_mission_timeout = 70", "days_mission_timeout = 71", 1
                ),
                encoding="utf-8-sig",
            )
            focuses = root / "common/national_focus/ADISCORD_national_focus_STP.txt"
            focus_text = focuses.read_text(encoding="utf-8-sig")
            focus_block = self._block_with_assignment(
                focus_text,
                "focus",
                "id = STP_Foreign_Guests_At_The_Banquet",
            )
            mutated_focus_block = focus_block.replace(
                "cancelable = no", "cancelable = yes", 1
            )
            self.assertNotEqual(focus_block, mutated_focus_block)
            focuses.write_text(
                focus_text.replace(focus_block, mutated_focus_block, 1),
                encoding="utf-8-sig",
            )
            issues = validator.validate(root, "stp")

        self.assertTrue(
            any("STP_health_stage_1_to_2 must last 70 days" in issue for issue in issues)
        )
        self.assertTrue(
            any("playable focus STP_Foreign_Guests_At_The_Banquet must be noncancelable" in issue
                for issue in issues)
        )

    def test_core_schema_owns_all_mutations(self):
        core = validator.read(
            validator.ROOT / "common/scripted_effects/ADISCORD_STP_VAL_crisis_core_effects.txt"
        ) or ""
        for effect in (
            "ADISCORD_STP_VAL_initialize_schema",
            "STP_set_health_stage",
            "STP_set_crisis_phase",
            "STP_change_readiness",
            "STP_change_suspicion",
            "STP_change_node_palace",
            "STP_change_node_officers",
            "STP_change_node_mountains",
            "STP_change_node_market",
            "STP_change_node_street",
            "STP_change_node_val_channel",
            "STP_refresh_crisis_modifier",
            "VAL_change_contract_authority",
            "VAL_change_stp_leverage",
            "VAL_refresh_contract_modifier",
        ):
            self.assertIsNotNone(validator.extract_named_block(core, effect), effect)
        self.assertNotIn("var = $value$", core)

    def test_core_validator_covers_dynamic_modifiers_and_sprite_aliases(self):
        core_paths = {path for path, _ in validator.REQUIRED_FILES["core"]}
        self.assertIn(
            "common/dynamic_modifiers/ADISCORD_STP_VAL_crisis_dynamic_modifiers.txt",
            core_paths,
        )
        self.assertIn("interface/ADISCORD_STP_VAL_crisis.gfx", core_paths)

    def test_canonical_variables_are_not_mutated_outside_core_api(self):
        root = validator.ROOT
        core_path = root / "common/scripted_effects/ADISCORD_STP_VAL_crisis_core_effects.txt"
        mutation = re.compile(
            r"(?:set_variable|add_to_variable|subtract_from_variable|multiply_variable|clamp_variable)"
            r"\s*=\s*\{(?:(?!\}).)*?\bvar\s*=\s*"
            r"(?:STP_resistance_readiness|STP_party_suspicion|VAL_contract_authority|VAL_STP_leverage)\b",
            re.DOTALL,
        )
        offenders = []
        for folder in ("common", "events", "history"):
            for path in (root / folder).rglob("*.txt"):
                if path == core_path:
                    continue
                if mutation.search(validator.read(path) or ""):
                    offenders.append(path.relative_to(root).as_posix())
        self.assertEqual(offenders, [])

    def test_schema_migrates_before_absent_defaults_and_assigns_version_last(self):
        core = validator.read(
            validator.ROOT / "common/scripted_effects/ADISCORD_STP_VAL_crisis_core_effects.txt"
        ) or ""
        initialization = validator.extract_named_block(core, "ADISCORD_STP_VAL_initialize_schema") or ""
        self.assertIn("multiply_variable = { var = STP_party_suspicion value = 100 }", initialization)
        self.assertIn("value = STP_state_face_stage", initialization)
        self.assertRegex(
            initialization,
            r"(?s)check_variable\s*=\s*\{\s*var\s*=\s*STP_state_face_stage\s+value\s*=\s*5"
            r".*?set_variable\s*=\s*\{\s*var\s*=\s*STP_leader_health_stage\s+value\s*=\s*4",
        )
        defaults = {
            "STP_leader_health_stage": 1,
            "STP_resistance_readiness": 10,
            "STP_party_suspicion": 5,
            "STP_crisis_phase": 1,
            "STP_side_commitment": 0,
            "STP_node_palace": 0,
            "STP_node_officers": 0,
            "STP_node_mountains": 0,
            "STP_node_market": 0,
            "STP_node_street": 0,
            "STP_node_val_channel": 0,
            "STP_security_posture": 0,
            "STP_resistance_posture": 0,
            "STP_security_adaptation_palace": 0,
            "STP_security_adaptation_officers": 0,
            "STP_security_adaptation_mountains": 0,
            "STP_security_adaptation_market": 0,
            "STP_security_adaptation_street": 0,
            "STP_security_adaptation_foreign": 0,
            "VAL_contract_authority": 35,
            "VAL_STP_leverage": 0,
            "VAL_negotiation_posture": 0,
            "VAL_CIN_influence": 0,
            "VAL_OSF_influence": 0,
            "VAL_APH_influence": 0,
            "VAL_CIN_contract_posture": 0,
            "VAL_OSF_contract_posture": 0,
            "VAL_APH_contract_posture": 0,
        }
        for variable, value in defaults.items():
            self.assertIn(f"NOT = {{ has_variable = {variable} }}", initialization)
            self.assertRegex(
                initialization,
                rf"set_variable\s*=\s*\{{\s*var\s*=\s*{re.escape(variable)}\s+value\s*=\s*{value}\s*\}}",
            )
        schema_assignments = list(
            re.finditer(
                r"set_variable\s*=\s*\{\s*var\s*=\s*ADISCORD_STP_VAL_crisis_schema_version"
                r"\s+value\s*=\s*1\s*\}",
                initialization,
            )
        )
        self.assertEqual(len(schema_assignments), 1)
        self.assertRegex(initialization[schema_assignments[0].end() :].strip(), r"^(?:\}\s*)+$")

    def test_literal_startup_scopes_only_stp_val_and_nod(self):
        on_actions = validator.read(
            validator.ROOT / "common/on_actions/01_ADISCORD_STP_VAL_crisis_on_actions.txt"
        ) or ""
        startup = validator.extract_named_block(on_actions, "on_startup") or ""
        for tag in ("STP", "VAL", "NOD"):
            self.assertRegex(
                startup,
                rf"\b{tag}\s*=\s*\{{[^{{}}]*ADISCORD_STP_VAL_initialize_schema\s*=\s*yes",
            )
        self.assertNotIn("every_country", startup)
        self.assertNotIn("random_country", startup)
        self.assertNotIn("on_daily", on_actions)
        self.assertIn("remove_power_balance", startup)
        self.assertIn("STP_inner_party_opinions_bop", startup)
        self.assertIn("remove_ideas = VAL_mercenary_state", startup)
        for task_3_token in (
            "STP_health_calendar_started",
            "complete_national_focus = STP_Nectar_of_the_Gods",
            "activate_mission = STP_health_stage_1_to_2",
        ):
            self.assertIn(task_3_token, startup)
        self.assertRegex(
            startup,
            r"(?s)NOT\s*=\s*\{\s*has_country_flag\s*=\s*STP_health_calendar_started\s*\}"
            r".*?set_country_flag\s*=\s*STP_health_calendar_started"
            r".*?complete_national_focus\s*=\s*STP_Nectar_of_the_Gods"
            r".*?activate_mission\s*=\s*STP_health_stage_1_to_2",
        )

    def test_four_canonical_health_missions_are_defined(self):
        decisions = validator.read(
            validator.ROOT / "common/decisions/ADISCORD_STP_crisis_decisions.txt"
        ) or ""
        events = validator.read(
            validator.ROOT / "events/ADISCORD_STP_crisis_events.txt"
        ) or ""
        expected = {
            "STP_health_stage_1_to_2": 70,
            "STP_health_stage_2_to_3": 70,
            "STP_health_stage_3_to_4": 63,
            "STP_health_stage_4_to_death": 63,
        }
        self.assertTrue(decisions, "Task 3 STP decisions file is missing")
        self.assertTrue(events, "Task 3 STP events file is missing")
        actual = {}
        for mission, days in expected.items():
            block = validator.extract_named_block(decisions, mission) or ""
            self.assertTrue(block, mission)
            self.assertRegex(block, rf"\bdays_mission_timeout\s*=\s*{days}\b")
            self.assertNotIn("cancel_effect", validator._mask_non_code(block))
            self.assertIn("selectable_mission = no", block)
            self.assertIn("activation = {\n\t\t\talways = no\n\t\t}", block)
            self.assertIn("has_country_flag = STP_main_campaign_side", block)
            actual[mission] = days
        self.assertEqual(actual, expected)

    def test_all_five_crisis_decision_categories_are_role_gated(self):
        categories = validator.read(
            validator.ROOT
            / "common/decisions/categories/ADISCORD_STP_VAL_crisis_categories.txt"
        ) or ""
        self.assertTrue(categories, "Task 3 decision categories file is missing")
        for category in DECISION_CATEGORIES:
            self.assertEqual(
                len(re.findall(rf"\b{re.escape(category)}\s*=\s*\{{", categories)),
                1,
                category,
            )
        stp = validator.extract_named_block(categories, "STP_crisis_operations") or ""
        self.assertIn("tag = STP", validator.extract_named_block(stp, "allowed") or "")
        self.assertIn("has_country_flag = STP_main_campaign_side", stp)
        val = validator.extract_named_block(categories, "VAL_contract_campaign") or ""
        self.assertIn("tag = VAL", validator.extract_named_block(val, "allowed") or "")
        self.assertIn("has_completed_focus = VAL_One_Ledger_One_Banner", val)
        nod = validator.extract_named_block(categories, "NOD_crisis_posture") or ""
        self.assertIn("tag = NOD", validator.extract_named_block(nod, "allowed") or "")
        self.assertIn("STP_main_campaign_side", nod)
        north = validator.extract_named_block(categories, "VAL_northern_campaign") or ""
        self.assertIn("tag = VAL", validator.extract_named_block(north, "allowed") or "")
        self.assertIn("has_completed_focus = VAL_Different_Views_On_Freedom", north)
        countdown = (
            validator.extract_named_block(categories, "STP_VAL_war_countdown_category")
            or ""
        )
        allowed = validator.extract_named_block(countdown, "allowed") or ""
        self.assertIn("tag = VAL", allowed)
        self.assertIn("STP_is_postwar_country = yes", allowed)
        for mission in WAR_COUNTDOWN_MISSIONS:
            self.assertIn(f"has_active_mission = {mission}", countdown)

    def test_health_events_chain_stages_and_use_the_day_140_probe(self):
        events = validator.read(
            validator.ROOT / "events/ADISCORD_STP_crisis_events.txt"
        ) or ""
        expected = (
            ("stp_crisis.1", 2, STP_SPINE_FOCUS_STAGES[2], "STP_health_stage_2_to_3"),
            ("stp_crisis.2", 3, STP_SPINE_FOCUS_STAGES[3], "STP_health_stage_3_to_4"),
            ("stp_crisis.3", 4, STP_SPINE_FOCUS_STAGES[4], "STP_health_stage_4_to_death"),
        )
        for event_id, stage, spine, next_mission in expected:
            block = self._block_with_assignment(
                events, "country_event", f"id = {event_id}"
            )
            self.assertIn("hidden = yes", block)
            self.assertIn(f"STP_set_health_stage = {{ value = {stage} }}", block)
            for focus in spine:
                self.assertIn(f"complete_national_focus = {focus}", block)
            self.assertIn(f"activate_mission = {next_mission}", block)
        stage_two = self._block_with_assignment(
            events, "country_event", "id = stp_crisis.1"
        )
        self.assertRegex(
            stage_two,
            r"(?s)country_event\s*=\s*\{\s*id\s*=\s*stp_crisis\.5\s+days\s*=\s*69\s*\}",
        )
        probe = self._block_with_assignment(
            events, "country_event", "id = stp_crisis.5"
        )
        self.assertIn("hidden = yes", probe)
        self.assertRegex(
            probe,
            r"check_variable\s*=\s*\{\s*var\s*=\s*STP_side_commitment"
            r"\s+value\s*=\s*0\s+compare\s*=\s*equals\s*\}",
        )
        self.assertIn("country_event = { id = stp_crisis.6 }", probe)
        self.assertNotIn("on_daily", events)

    def test_death_event_is_terminal_and_completes_the_spine(self):
        events = validator.read(
            validator.ROOT / "events/ADISCORD_STP_crisis_events.txt"
        ) or ""
        death = self._block_with_assignment(
            events, "country_event", "id = stp_crisis.4"
        )
        self.assertIn("set_country_flag = STP_ivanov_dead", death)
        self.assertIn("STP_set_health_stage = { value = 5 }", death)
        self.assertIn(
            "complete_national_focus = STP_The_Father_Of_Peace_Is_Gone", death
        )
        self.assertIn("STP_set_crisis_phase = { value = 2 }", death)
        self.assertIn("retire_character = STP_Petr_Ivanov", death)
        self.assertNotIn("activate_mission = STP_health_stage_", death)
        for focus in STP_CRISIS_FOCUS_STAGES:
            self.assertIn(f"clr_country_flag = STP_focus_active_{focus}", death)

    def test_commitment_apis_are_one_way_and_schedule_one_posture_choice(self):
        core = validator.read(
            validator.ROOT
            / "common/scripted_effects/ADISCORD_STP_VAL_crisis_core_effects.txt"
        ) or ""
        contracts = {
            "STP_commit_to_shabrat": (
                1,
                "STP_sided_with_Maksim_flag",
                "STP_sided_with_the_party_flag",
                "stp_crisis.10",
            ),
            "STP_commit_to_party": (
                2,
                "STP_sided_with_the_party_flag",
                "STP_sided_with_Maksim_flag",
                "stp_crisis.11",
            ),
        }
        for effect, (value, own_flag, opposite_flag, event_id) in contracts.items():
            block = validator.extract_named_block(core, effect) or ""
            self.assertTrue(block, effect)
            self.assertRegex(
                block,
                r"check_variable\s*=\s*\{\s*var\s*=\s*STP_side_commitment"
                r"\s+value\s*=\s*0\s+compare\s*=\s*equals\s*\}",
            )
            self.assertEqual(
                len(
                    re.findall(
                        rf"set_variable\s*=\s*\{{\s*var\s*=\s*STP_side_commitment"
                        rf"\s+value\s*=\s*{value}\s*\}}",
                        block,
                    )
                ),
                1,
            )
            self.assertIn(f"set_country_flag = {own_flag}", block)
            self.assertIn(f"clr_country_flag = {opposite_flag}", block)
            self.assertIn(f"country_event = {{ id = {event_id} days = 1 }}", block)

    def test_posture_selection_is_zero_guarded_and_never_rerolled(self):
        events = validator.read(
            validator.ROOT / "events/ADISCORD_STP_crisis_events.txt"
        ) or ""
        contracts = {
            "stp_crisis.10": ("STP_security_posture", set(SECURITY_POSTURES)),
            "stp_crisis.11": ("STP_resistance_posture", set(RESISTANCE_POSTURES)),
        }
        for event_id, (variable, expected_values) in contracts.items():
            block = self._block_with_assignment(events, "country_event", f"id = {event_id}")
            self.assertIn("hidden = yes", block)
            self.assertRegex(
                block,
                rf"check_variable\s*=\s*\{{\s*var\s*=\s*{variable}"
                r"\s+value\s*=\s*0\s+compare\s*=\s*equals\s*\}",
            )
            values = {
                int(match)
                for match in re.findall(
                    rf"set_variable\s*=\s*\{{\s*var\s*=\s*{variable}"
                    r"\s+value\s*=\s*(\d+)\s*\}",
                    block,
                )
            }
            self.assertEqual(values, expected_values)
            self.assertNotIn(f"var = {variable} value = 0", block)
        for token in (
            "hedonism",
            "is_subject_of = NOD",
            "has_stability",
            "has_equipment",
            "STP_focus_nodrul_observed",
            "STP_focus_kefreyt_observed",
            "STP_focus_palace_observed",
            "STP_focus_street_observed",
            "STP_focus_garrisons_observed",
            "STP_focus_mountains_open",
            "STP_focus_market_open",
            "STP_focus_val_supply_open",
            "STP_resistance_escrow_infantry",
        ):
            self.assertIn(token, events)

    def test_forced_choice_uses_normal_commit_without_focus_reward(self):
        events = validator.read(
            validator.ROOT / "events/ADISCORD_STP_crisis_events.txt"
        ) or ""
        forced = self._block_with_assignment(
            events, "country_event", "id = stp_crisis.6"
        )
        self.assertNotIn("hidden = yes", forced)
        for effect, focus, penalty in (
            ("STP_commit_to_shabrat", "STP_Show_Him_The_Truth", "STP_change_suspicion"),
            ("STP_commit_to_party", "STP_Govern_In_His_Name", "STP_change_readiness"),
        ):
            self.assertIn(f"{effect} = yes", forced)
            self.assertRegex(
                forced,
                rf"(?s)set_country_flag\s*=\s*STP_forced_commit_no_reward"
                rf".*?complete_national_focus\s*=\s*{re.escape(focus)}"
                rf".*?clr_country_flag\s*=\s*STP_forced_commit_no_reward",
            )
            self.assertIn(f"{penalty} = {{ value = 10 }}", forced)
        self.assertEqual(forced.count("add_political_power = -50"), 2)
        self.assertEqual(forced.count("flag = STP_crisis_late_choice_lock"), 2)
        self.assertEqual(forced.count("days = 35"), 2)

    def test_playable_crisis_focus_windows_are_exact_and_sticky(self):
        tree = validator.read(
            validator.ROOT / "common/national_focus/ADISCORD_national_focus_STP.txt"
        ) or ""
        sticky_flags = set()
        for focus, stage in STP_CRISIS_FOCUS_STAGES.items():
            block = self._block_with_assignment(tree, "focus", f"id = {focus}")
            self.assertTrue(block, focus)
            masked = validator._mask_non_code(block)
            self.assertRegex(masked, r"\bcost\s*=\s*5\b")
            self.assertRegex(masked, r"\bcancelable\s*=\s*no\b")
            self.assertRegex(masked, r"\bcancel_if_invalid\s*=\s*yes\b")
            self.assertRegex(masked, r"\bcontinue_if_invalid\s*=\s*no\b")
            self.assertNotIn("cancel_effect", masked)
            sticky = f"STP_focus_active_{focus}"
            sticky_flags.add(sticky)
            select = validator.extract_named_block(block, "select_effect") or ""
            self.assertIn(f"set_country_flag = {sticky}", select)
            available = validator.extract_named_block(block, "available") or ""
            self.assertIn("NOT = { has_country_flag = STP_ivanov_dead }", available)
            self.assertIn(
                "NOT = { has_country_flag = STP_crisis_late_choice_lock }", available
            )
            self.assertRegex(
                available,
                rf"check_variable\s*=\s*\{{\s*var\s*=\s*STP_leader_health_stage"
                rf"\s+value\s*=\s*{stage}\s+compare\s*=\s*equals\s*\}}",
            )
            self.assertIn(f"has_country_flag = {sticky}", available)
            reward = validator.extract_named_block(block, "completion_reward") or ""
            self.assertIn(f"clr_country_flag = {sticky}", reward)
            interface = STP_CRISIS_FOCUS_REWARDS[focus]
            if interface.startswith("STP_commit_to_"):
                self.assertIn(f"{interface} = yes", reward)
                self.assertIn("STP_forced_commit_no_reward", reward)
            else:
                self.assertIn(f"set_country_flag = {interface}", reward)
            if focus in STP_SHABRAT_FOCUSES:
                self.assertRegex(
                    available,
                    r"check_variable\s*=\s*\{\s*var\s*=\s*STP_side_commitment"
                    r"\s+value\s*=\s*1\s+compare\s*=\s*equals\s*\}",
                )
            elif focus in STP_PARTY_FOCUSES:
                self.assertRegex(
                    available,
                    r"check_variable\s*=\s*\{\s*var\s*=\s*STP_side_commitment"
                    r"\s+value\s*=\s*2\s+compare\s*=\s*equals\s*\}",
                )
        self.assertEqual(len(sticky_flags), len(STP_CRISIS_FOCUS_STAGES))

    def test_focus_prerequisite_deadlocks_are_repaired_without_new_ids(self):
        tree = validator.read(
            validator.ROOT / "common/national_focus/ADISCORD_national_focus_STP.txt"
        ) or ""
        prerequisites = {
            "STP_Foreign_Guests_At_The_Banquet": "STP_Nectar_of_the_Gods",
            "STP_Kefreite_Security_Offer": "STP_Foreign_Guests_At_The_Banquet",
            "STP_The_Old_Man_On_The_Balcony": "STP_Nectar_of_the_Gods",
            "STP_The_City_Still_Dances": "STP_Nectar_of_the_Gods",
            "STP_Count_The_Loyalists": "STP_Nectar_of_the_Gods",
            "STP_Show_Him_The_Truth": "STP_The_Old_Man_On_The_Balcony",
            "STP_Govern_In_His_Name": "STP_The_Old_Man_On_The_Balcony",
            "STP_The_Valirian_Advisers": "STP_Foreign_Guests_At_The_Banquet",
            "STP_Contractors_In_The_Passes": "STP_Kefreite_Security_Offer",
            "STP_Rumours_In_The_Highlands": "STP_Kefreite_Security_Offer",
            "STP_The_Lower_Market": "STP_The_City_Still_Dances",
            "STP_Renew_The_Cultural_Mandate": "STP_The_Valirian_Advisers",
        }
        for focus, prerequisite in prerequisites.items():
            block = self._block_with_assignment(tree, "focus", f"id = {focus}")
            prereq = validator.extract_named_block(block, "prerequisite") or ""
            self.assertRegex(prereq, rf"\bfocus\s*=\s*{re.escape(prerequisite)}\b")
        focus_ids = re.findall(r"\bid\s*=\s*(STP_[A-Za-z0-9_]+)", tree)
        self.assertEqual(len(focus_ids), len(set(focus_ids)))

    def test_state_face_and_party_suspicion_use_canonical_whole_values(self):
        root = validator.ROOT
        paths = (
            "common/focus_inlay_windows/ADISCORD_STP_state_face_inlay_window.txt",
            "common/scripted_localisation/ADISCORD_STP_leader_health_scripted_loc.txt",
            "common/scripted_localisation/ADISCORD_STP_state_face_scripted_loc.txt",
            "common/scripted_localisation/ADISCORD_STP_party_elections_scripted_loc.txt",
        )
        for relative in paths:
            text = validator.read(root / relative) or ""
            self.assertNotIn("original_tag = STP", text, relative)
            self.assertNotRegex(
                validator._mask_non_code(text),
                r"\bvar\s*=\s*STP_state_face_stage\b"
                r"|\bSTP_state_face_stage\s*(?:=|>|<)",
                relative,
            )
            self.assertIn("tag = STP", text, relative)
            self.assertIn("has_country_flag = STP_main_campaign_side", text, relative)
        for relative in (
            "localisation/russian/ADISCORD_stp_state_face_l_russian.yml",
            "localisation/russian/ADISCORD_STP_party_elections_l_russian.yml",
        ):
            self.assertTrue((root / relative).read_bytes().startswith(b"\xef\xbb\xbf"))
        party_loc = validator.read(
            root / "localisation/russian/ADISCORD_STP_party_elections_l_russian.yml"
        ) or ""
        self.assertIn("[?STP_party_suspicion|R0]%", party_loc)
        self.assertNotIn("[?STP_party_suspicion|R1%]", party_loc)
        self.assertNotIn(
            "STP_party_suspicion_political_power_gain_dynamic_var", party_loc
        )

    def test_legacy_stp_and_val_migration_paths_are_idempotent(self):
        core = validator.read(
            validator.ROOT / "common/scripted_effects/ADISCORD_STP_VAL_crisis_core_effects.txt"
        ) or ""
        initialization = validator.extract_named_block(core, "ADISCORD_STP_VAL_initialize_schema") or ""
        for role_flag in (
            "STP_internal_war_started",
            "STP_crisis_party_side",
            "STP_crisis_resistance_side",
            "STP_postwar_campaign_side",
            "STP_internal_outcome_finalized",
        ):
            self.assertIn(f"NOT = {{ has_country_flag = {role_flag} }}", initialization)
        self.assertIn("set_country_flag = STP_main_campaign_side", initialization)
        self.assertIn("has_character = STP_maksim_shabrat", initialization)
        self.assertIn("set_country_flag = STP_shabrat_available", initialization)
        self.assertIn("set_variable = { var = VAL_contract_authority value = 35 }", initialization)
        for focus, reward in VAL_AUTHORITY_FOCUS_REWARDS.items():
            self.assertEqual(initialization.count(f"has_completed_focus = {focus}"), 1)
            self.assertRegex(
                initialization,
                rf"(?s)has_completed_focus\s*=\s*{re.escape(focus)}.*?"
                rf"add_to_variable\s*=\s*\{{\s*var\s*=\s*VAL_contract_authority\s+value\s*=\s*{reward}\s*\}}",
            )
        for completed, expected in (
            (set(), 35),
            ({"VAL_The_Contract_State", "VAL_The_Weaponry_Baron"}, 50),
            (
                {
                    "VAL_The_Contract_State",
                    "VAL_The_Weaponry_Baron",
                    "VAL_Export_Rifles_Not_Promises",
                    "VAL_Different_Views_On_Freedom",
                },
                60,
            ),
        ):
            reconstructed = 35 + sum(
                reward for focus, reward in VAL_AUTHORITY_FOCUS_REWARDS.items() if focus in completed
            )
            self.assertEqual(reconstructed, expected)

    def test_dynamic_spirits_use_exact_variable_backing_and_manifest_bands(self):
        dynamic = validator.read(
            validator.ROOT
            / "common/dynamic_modifiers/ADISCORD_STP_VAL_crisis_dynamic_modifiers.txt"
        ) or ""
        expected_dynamic_keys = {
            "STP_fading_father": (
                "political_power_factor = STP_fading_pp_factor",
                "stability_factor = STP_fading_stability_factor",
                "command_power_gain_mult = STP_fading_command_power_factor",
                "planning_speed = STP_fading_planning_factor",
                "army_org_factor = STP_fading_org_factor",
            ),
            "STP_underground_network": (
                "stability_factor = STP_network_stability_factor",
                "consumer_goods_factor = STP_network_consumer_goods_factor",
            ),
            "STP_security_pressure": (
                "stability_factor = STP_pressure_stability_factor",
                "political_power_factor = STP_pressure_pp_factor",
                "industrial_capacity_factory = STP_pressure_factory_output_factor",
            ),
            "VAL_contract_state": (
                "army_attack_factor = VAL_contract_attack_factor",
                "army_defence_factor = VAL_contract_defence_factor",
                "army_org_factor = VAL_contract_org_factor",
                "army_org_regain = VAL_contract_org_regain",
                "equipment_capture_factor = VAL_contract_capture_factor",
                "supply_consumption_factor = VAL_contract_supply_factor",
                "planning_speed = VAL_contract_planning_factor",
                "political_power_gain = VAL_contract_pp_gain",
                "stability_factor = VAL_contract_stability_factor",
                "ADISCORD_economy_state_overload_gain_factor = VAL_contract_state_overload_factor",
                "ADISCORD_economy_trade_income_factor = VAL_contract_trade_income_factor",
                "ADISCORD_economy_military_industry_income_factor = VAL_contract_military_income_factor",
                "ADISCORD_economy_army_expense_factor = VAL_contract_army_expense_factor",
            ),
        }
        for modifier, assignments in expected_dynamic_keys.items():
            block = validator.extract_named_block(dynamic, modifier) or ""
            for assignment in assignments:
                self.assertIn(assignment, block)

        core = validator.read(
            validator.ROOT / "common/scripted_effects/ADISCORD_STP_VAL_crisis_core_effects.txt"
        ) or ""
        refresh = validator.extract_named_block(core, "VAL_refresh_contract_modifier") or ""
        backing = {
            "attack": "VAL_contract_attack_factor",
            "defence": "VAL_contract_defence_factor",
            "org": "VAL_contract_org_factor",
            "org_regain": "VAL_contract_org_regain",
            "capture": "VAL_contract_capture_factor",
            "supply": "VAL_contract_supply_factor",
            "planning": "VAL_contract_planning_factor",
            "daily_pp": "VAL_contract_pp_gain",
            "stability": "VAL_contract_stability_factor",
            "state_overload": "VAL_contract_state_overload_factor",
            "trade_income": "VAL_contract_trade_income_factor",
            "military_industry_income": "VAL_contract_military_income_factor",
            "army_expense": "VAL_contract_army_expense_factor",
        }
        for band in VAL_CONTRACT_BANDS:
            marker = f"# VAL contract band {band['minimum']}-{band['maximum']}"
            self.assertIn(marker, refresh)
            start = refresh.index(marker)
            following = [
                refresh.find(f"# VAL contract band {other['minimum']}-{other['maximum']}", start + 1)
                for other in VAL_CONTRACT_BANDS
                if refresh.find(
                    f"# VAL contract band {other['minimum']}-{other['maximum']}", start + 1
                )
                != -1
            ]
            chunk = refresh[start : min(following) if following else len(refresh)]
            for key, variable in backing.items():
                raw = band["modifiers"].get(key, 0)
                value = raw if key == "daily_pp" else raw / 100
                numeric = re.escape(str(value))
                if value == 0:
                    numeric = r"0(?:\.0)?"
                self.assertRegex(
                    chunk,
                    rf"set_variable\s*=\s*\{{\s*var\s*=\s*{variable}\s+value\s*=\s*{numeric}\s*\}}",
                )

    def test_stp_modifier_tables_and_lifecycles_are_exact(self):
        core = validator.read(
            validator.ROOT / "common/scripted_effects/ADISCORD_STP_VAL_crisis_core_effects.txt"
        ) or ""
        refresh = validator.extract_named_block(core, "STP_refresh_crisis_modifier") or ""
        self._assert_stp_modifier_contract(refresh)

    def test_stp_modifier_contract_rejects_behavioral_mutations(self):
        core = validator.read(
            validator.ROOT / "common/scripted_effects/ADISCORD_STP_VAL_crisis_core_effects.txt"
        ) or ""
        refresh = validator.extract_named_block(core, "STP_refresh_crisis_modifier") or ""
        mutations = {
            "backing assignment": (
                "set_variable = { var = STP_network_stability_factor value = -0.07 }",
                "set_variable = { var = STP_network_stability_factor value = -0.06 }",
            ),
            "threshold bound": (
                "STP_resistance_readiness value = 75 compare = greater_than_or_equals",
                "STP_resistance_readiness value = 76 compare = greater_than_or_equals",
            ),
            "lifecycle flag": (
                "NOT = { has_country_flag = STP_internal_war_started }",
                "NOT = { has_country_flag = STP_internal_war_finished }",
            ),
            "remove operation": (
                "remove_dynamic_modifier = { modifier = STP_security_pressure }",
                "remove_dynamic_modifier = { modifier = STP_security_pressure_mutated }",
            ),
        }
        for name, (before, after) in mutations.items():
            with self.subTest(name=name):
                mutated = refresh.replace(before, after, 1)
                self.assertNotEqual(mutated, refresh)
                with self.assertRaises(AssertionError):
                    self._assert_stp_modifier_contract(mutated)

    def test_successors_portraits_guard_and_history_bootstrap_are_exact(self):
        root = validator.ROOT
        characters = validator.read(root / "common/characters/STP.txt") or ""
        leaders = {
            "STP_maksim_shabrat": ("GFX_portrait_STP_Maksim_Shabrat", "chauvinism_ideology"),
            "STP_grigory_sotnikov": ("GFX_portrait_STP_Grigory_Sotnikov", "etatism_ideology"),
            "STP_rufus_hedersett": (
                "GFX_portrait_STP_Rufus_Hedersett",
                "aristocratic_hedonism",
            ),
        }
        for character, (portrait, ideology) in leaders.items():
            self.assertEqual(
                len(re.findall(rf"\b{re.escape(character)}\s*=\s*\{{", characters)),
                1,
            )
            block = validator.extract_named_block(characters, character) or ""
            self.assertIn(f"large = {portrait}", block)
            self.assertIn(f"ideology = {ideology}", block)
            self.assertIn('expire = "2200.1.1.1"', block)

        portrait_gfx = validator.read(root / "interface/ADISCORD_leader_portraits.gfx") or ""
        for sprite, path in (
            (
                "GFX_portrait_STP_Grigory_Sotnikov",
                "gfx/leaders/STP/portrait_STP_Grigory_Sotnikov.png",
            ),
            (
                "GFX_portrait_STP_Rufus_Hedersett",
                "gfx/leaders/STP/portrait_STP_Rufus_Hedersett.png",
            ),
        ):
            block = self._block_with_assignment(portrait_gfx, "spriteType", f'name = "{sprite}"')
            self.assertIn(path, block)
            png = root / path
            with png.open("rb") as stream:
                self.assertEqual(stream.read(8), b"\x89PNG\r\n\x1a\n")
                self.assertEqual(stream.read(4), b"\x00\x00\x00\r")
                self.assertEqual(stream.read(4), b"IHDR")
                dimensions = struct.unpack(">II", stream.read(8))
            self.assertEqual(dimensions, (156, 210))

        oob = validator.read(root / "history/units/STP.txt") or ""
        guard = self._block_with_assignment(oob, "division_template", 'name = "Capital Guard"')
        for line in ("is_locked = yes", "force_allow_recruiting = no", "division_cap = 1"):
            self.assertIn(line, guard)
        units = validator.extract_named_block(oob, "units") or ""
        self.assertEqual(len(re.findall(r"\bdivision\s*=\s*\{", units)), 14)
        self.assertEqual(units.count('division_template = "Capital Guard"'), 1)

        stp_history = validator.read(root / "history/countries/STP - StepanLand.txt") or ""
        self.assertIn("set_country_flag = STP_main_campaign_side", stp_history)
        self.assertIn("set_country_flag = STP_shabrat_available", stp_history)
        self.assertNotIn("set_power_balance", stp_history)

    def test_old_mercenary_idea_is_only_a_stub(self):
        idea = validator.read(validator.ROOT / "common/ideas/valeraland.txt") or ""
        history = validator.read(validator.ROOT / "history/countries/VAL - ValeraLand.txt") or ""
        bookmark = validator.read(validator.ROOT / "common/bookmarks/the_gathering_storm.txt") or ""
        stub = validator.extract_named_block(idea, "VAL_mercenary_state")
        self.assertIsNotNone(stub)
        self.assertNotIn("send_volunteer_size", stub)
        self.assertNotIn("army_attack_factor", stub)
        self.assertRegex(stub or "", r"modifier\s*=\s*\{\s*\}")
        self.assertNotIn("VAL_mercenary_state", history)
        self.assertNotIn("VAL_mercenary_state", bookmark)

    def test_legacy_callbacks_are_inert_or_forward_to_core(self):
        root = validator.ROOT
        state_face = validator.read(root / "common/scripted_effects/ADISCORD_stp_state_face_effects.txt") or ""
        for stage in range(1, 6):
            block = validator.extract_named_block(
                state_face, f"STP_set_state_face_stage_{stage}_silent"
            ) or ""
            self.assertIn(f"STP_set_health_stage = {{ value = {stage} }}", block)
            self.assertNotIn("set_variable", block)

        old_effect = validator.read(
            root / "common/scripted_effects/ADISCORD_scripted_effects_stelander.txt"
        ) or ""
        suspicion = validator.extract_named_block(old_effect, "STP_change_party_suspicion_rate") or ""
        self.assertIn("value = 100", suspicion)
        self.assertIn("STP_change_suspicion = { value = STP_party_suspicion_temp }", suspicion)
        self.assertNotIn("STP_party_suspicion_political_power_gain_dynamic_var", suspicion)

        old_dynamic = validator.read(
            root / "common/dynamic_modifiers/stelander_dynamic_modifiers.txt"
        ) or ""
        for modifier in (
            "stp_party_suspicion",
            "stp_bop_less_hedonism_radical_maksim",
            "stp_bop_less_hedonism_radical_hedersett",
            "stp_bop_more_hedonism_radical_maksim",
            "stp_bop_more_hedonism_radical_hedersett",
        ):
            block = validator.extract_named_block(old_dynamic, modifier) or ""
            self.assertIn("always = no", block)
            self.assertNotRegex(block, r"(stability|political_power)_factor\s*=")

        bop = validator.read(root / "common/bop/ADISCORD_bop_STP.txt") or ""
        for identifier in (
            "STP_inner_party_opinions_bop",
            "STP_less_hedonism",
            "STP_more_hedonism",
            "STP_IDK_who_wins",
            "STP_more_hedonism_non_radical",
            "STP_less_hedonism_non_radical",
            "STP_less_hedonism_radical",
            "STP_more_hedonism_radical",
        ):
            self.assertIn(identifier, bop)
        self.assertNotIn("on_activate", bop)
        self.assertNotIn("on_deactivate", bop)
        self.assertNotIn("set_power_balance_gfx", bop)
        self.assertNotIn("add_dynamic_modifier", bop)
        legacy_events = validator.read(root / "events/ADISCORD_events_STP.txt") or ""
        self.assertNotIn("STP_change_party_suspicion_rate", legacy_events)
        self.assertNotIn("stp_party_suspicion", legacy_events)

    def test_idea_sprites_are_exact_68_pixel_aliases(self):
        root = validator.ROOT
        gfx = validator.read(root / "interface/ADISCORD_STP_VAL_crisis.gfx") or ""
        aliases = {
            "GFX_idea_STP_fading_father": "gfx/interface/ideas/STP/idea_STP_deadman_rulling_the_country.png",
            "GFX_idea_STP_underground_network": "gfx/interface/ideas/STP/idea_STP_National_Strikes.png",
            "GFX_idea_STP_security_pressure": "gfx/interface/ideas/STP/idea_STP_hidden_slaves_trade.png",
            "GFX_idea_VAL_contract_state": "gfx/interface/ideas/VAL/idea_VAL_mercenary_state.png",
        }
        for sprite, path in aliases.items():
            block = self._block_with_assignment(gfx, "spriteType", f'name = "{sprite}"')
            self.assertIn(path, block)
            with (root / path).open("rb") as stream:
                self.assertEqual(stream.read(8), b"\x89PNG\r\n\x1a\n")
                self.assertEqual(stream.read(4), b"\x00\x00\x00\r")
                self.assertEqual(stream.read(4), b"IHDR")
                self.assertEqual(struct.unpack(">II", stream.read(8)), (68, 68))


if __name__ == "__main__":
    unittest.main()
