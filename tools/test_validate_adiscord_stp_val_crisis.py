import unittest
import re
import struct
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
    def _block_with_assignment(self, text: str, block_name: str, assignment: str) -> str:
        return next(
            (block for block in validator._iter_named_blocks(text, block_name) if assignment in block),
            "",
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
        stp_scope = self._block_with_assignment(
            startup, "STP", "ADISCORD_STP_VAL_initialize_schema = yes"
        )
        for guard in (
            "has_country_flag = STP_main_campaign_side",
            "check_variable = { var = STP_leader_health_stage value = 1",
            "NOT = { has_country_flag = STP_health_calendar_started }",
            "set_country_flag = STP_health_calendar_started",
            "complete_national_focus = STP_Nectar_of_the_Gods",
            "activate_mission = STP_health_stage_1_to_2",
        ):
            self.assertIn(guard, stp_scope)

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
        for marker in (
            "# Fading father stage 1: 0 0 0 0 0",
            "# Fading father stage 2: -0.05 -0.02 -0.05 0 0",
            "# Fading father stage 3: -0.10 -0.05 -0.10 -0.05 0",
            "# Fading father stage 4: -0.20 -0.10 -0.20 -0.10 -0.05",
            "# Underground network 0-24: 0 0",
            "# Underground network 25-49: -0.02 0.01",
            "# Underground network 50-74: -0.04 0.02",
            "# Underground network 75-89: -0.07 0.03",
            "# Underground network 90-100: -0.10 0.04",
            "# Security pressure 0-24: 0 0 0",
            "# Security pressure 25-49: -0.02 -0.05 0",
            "# Security pressure 50-74: -0.05 -0.10 -0.03",
            "# Security pressure 75-89: -0.10 -0.15 -0.05",
            "# Security pressure 90-100: -0.15 -0.20 -0.10",
        ):
            self.assertIn(marker, refresh)
        for modifier in ("STP_fading_father", "STP_underground_network", "STP_security_pressure"):
            self.assertIn(f"add_dynamic_modifier = {{ modifier = {modifier} }}", refresh)
            self.assertIn(f"remove_dynamic_modifier = {{ modifier = {modifier} }}", refresh)

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
