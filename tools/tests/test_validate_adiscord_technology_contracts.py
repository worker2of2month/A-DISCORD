from __future__ import annotations

import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from tools.validators import validate_adiscord_tech_doctrine as validator


class TechnologyValidatorNegativeTests(unittest.TestCase):
    """Prove that the focused validator rejects representative regressions."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.defined_techs, cls.tech_blocks = validator.collect_technologies()

    def test_generated_horizontal_tree_positions_match_the_validator_contract(self) -> None:
        issues = validator.check_technology_parser_constraints(self.tech_blocks)
        self.assertFalse(
            any("grid position" in issue for issue in issues),
            issues,
        )

    def test_transposed_horizontal_grid_position_is_reported(self) -> None:
        tech_id = "ADISCORD_tech_postwar_weapon_standardization"
        broken = dict(self.tech_blocks)
        broken[tech_id] = broken[tech_id].replace(
            "position = { x = 1 y = 0 }",
            "position = { x = 0 y = 1 }",
            1,
        )
        issues = validator.check_technology_parser_constraints(broken)
        self.assertTrue(
            any(tech_id in issue and "grid position (0, 1)" in issue for issue in issues),
            issues,
        )

    def test_horizontal_gridbox_using_up_format_is_reported(self) -> None:
        gui_path = validator.ROOT / "interface" / "countrytechtreeview.gui"
        gui = validator.read_text(gui_path)
        broken_gui = gui.replace('format = "LEFT"', 'format = "UP"', 1)
        with patch.object(validator, "read_text", return_value=broken_gui):
            issues = validator.check_technology_gridboxes(self.tech_blocks)
        self.assertTrue(
            any("infantry_folder" in issue and "horizontal LEFT" in issue for issue in issues),
            issues,
        )

    def test_mechanized_upgrades_target_the_custom_mechanized_battalion(self) -> None:
        for tech_id in (
            "ADISCORD_tech_armored_carrier_program",
            "ADISCORD_tech_infantry_combat_vehicle_program",
            "ADISCORD_tech_networked_mechanized_cells",
        ):
            block = self.tech_blocks[tech_id]
            self.assertNotRegex(block, r"(?m)^\s*mechanized\s*=\s*\{")
            self.assertRegex(
                block,
                r"(?m)^\s*ADISCORD_mechanized_infantry\s*=\s*\{",
            )

    def test_missing_generated_dependency_is_reported(self) -> None:
        tech_id = "ADISCORD_tech_teleoperated_scout_carts"
        broken = dict(self.tech_blocks)
        broken[tech_id] = broken[tech_id].replace(
            "\n\t\t\tADISCORD_tech_hardened_computers = 1",
            "",
            1,
        )
        issues = validator.check_technology_gridboxes(broken)
        self.assertTrue(
            any(tech_id in issue and "dependencies are" in issue for issue in issues),
            issues,
        )

    def test_shared_startup_requires_history_provenance_and_completion_order(self) -> None:
        history = "set_global_flag = ADISCORD_fresh_campaign_contract_v1\n"
        startup = """
on_actions = {
    on_startup = { effect = { if = {
        limit = {
            has_global_flag = ADISCORD_fresh_campaign_contract_v1
            NOT = { has_global_flag = ADISCORD_starting_technology_profiles_applied }
        }
        every_country = { ADISCORD_grant_starting_technology_profile = yes }
        every_country = { ADISCORD_initialize_default_country_development = yes }
        STP = { ADISCORD_STP_lock_regular_army_templates = yes }
        every_country = { ADISCORD_economy_initialize_country = yes }
        set_global_flag = ADISCORD_starting_technology_profiles_applied
    } } }
    on_monthly = { effect = { if = { limit = { has_global_flag = ADISCORD_fresh_campaign_contract_v1 } ADISCORD_tick_all_society_development_monthly = yes } } }
    on_yearly = { effect = { if = { limit = { has_global_flag = ADISCORD_fresh_campaign_contract_v1 } ADISCORD_tick_all_society_development_yearly = yes } } }
}
"""
        self.assertEqual(
            validator.fresh_campaign_startup_contract_issues(history, startup), []
        )
        self.assertTrue(
            validator.fresh_campaign_startup_contract_issues("", startup)
        )
        self.assertTrue(
            validator.fresh_campaign_startup_contract_issues(
                history,
                startup.replace(
                    "has_global_flag = ADISCORD_fresh_campaign_contract_v1\n",
                    "",
                    1,
                ),
            )
        )

    def test_missing_energy_price_is_reported(self) -> None:
        tech_id = "ADISCORD_tech_concentrated_industrial_zones"
        broken = dict(self.tech_blocks)
        broken[tech_id] = broken[tech_id].replace(
            "\n\t\tfactory_energy_consumption = 0.08",
            "",
            1,
        )
        issues = validator.check_post_2160_research_balance(broken)
        self.assertTrue(
            any(tech_id in issue and "energy" in issue for issue in issues),
            issues,
        )

    def test_ai_force_progression_accepts_reachable_field_baseline(self) -> None:
        check = getattr(validator, "ai_force_progression_contract_issues", None)
        self.assertIsNotNone(
            check,
            "AI progression validator must expose its source contract for fixture tests",
        )
        templates = """
ADISCORD_infantry_templates = {
    role = infantry
    ADISCORD_reconstruction_brigade = {
        can_upgrade_in_field = { always = yes }
        target_min_match = 0.65
        target_template = { regiments = { infantry = 6 } }
    }
    ADISCORD_line_brigade = {
        enable = {
            is_ai = yes
        }
        target_min_match = 0.75
        target_template = {
            regiments = { infantry = 8 ADISCORD_line_artillery = 1 }
        }
    }
}
"""
        default_strategy = """
ADISCORD_produce_support_equipment_low_stock = {
    enable = { num_of_military_factories > 1 }
    ai_strategy = {
        type = equipment_production_min_factories_archetype
        id = support_equipment
        value = 1
    }
}
ADISCORD_produce_artillery_low_stock = {
    enable = { num_of_military_factories > 2 }
    ai_strategy = {
        type = equipment_production_min_factories_archetype
        id = artillery_equipment
        value = 1
    }
}
"""
        self.assertEqual(check(templates, default_strategy), [])

    def test_ai_force_progression_rejects_unreachable_four_battalion_loop(self) -> None:
        check = getattr(validator, "ai_force_progression_contract_issues", None)
        self.assertIsNotNone(
            check,
            "AI progression validator must expose its source contract for fixture tests",
        )
        templates = """
ADISCORD_infantry_templates = {
    role = infantry
    ADISCORD_reconstruction_brigade = {
        target_template = { regiments = { infantry = 4 } }
    }
    ADISCORD_line_brigade = {
        enable = {
            num_of_military_factories > 3
            has_equipment = { support_equipment > 400 }
            has_equipment = { artillery_equipment > 250 }
        }
        target_template = { regiments = { infantry = 6 } }
    }
}
"""
        default_strategy = """
ADISCORD_produce_support_equipment_low_stock = {
    enable = { num_of_military_factories > 3 }
    ai_strategy = {
        type = equipment_production_min_factories_archetype
        id = support_equipment
        value = 1
    }
}
"""
        issues = check(templates, default_strategy)
        self.assertTrue(any("at least six battalions" in issue for issue in issues), issues)
        self.assertTrue(any("target_min_match" in issue for issue in issues), issues)
        self.assertTrue(any("supported line template" in issue for issue in issues), issues)
        self.assertTrue(any("eight infantry" in issue for issue in issues), issues)
        self.assertTrue(any("line artillery" in issue for issue in issues), issues)
        self.assertTrue(any("support production" in issue for issue in issues), issues)
        self.assertTrue(any("artillery production" in issue for issue in issues), issues)

    def test_modern_land_warfare_contract_accepts_mechanized_armored_force(self) -> None:
        check = getattr(validator, "modern_land_warfare_contract_issues", None)
        self.assertIsNotNone(check)
        equipment = """
equipments = {
    ADISCORD_armored_carrier_archetype = {
        is_archetype = yes
        type = { mechanized }
        is_buildable = no
    }
    ADISCORD_armored_carrier_2163 = {
        archetype = ADISCORD_armored_carrier_archetype
    }
    ADISCORD_ifv_2170 = {
        archetype = ADISCORD_armored_carrier_archetype
        parent = ADISCORD_armored_carrier_2163
    }
    ADISCORD_networked_ifv_2183 = {
        archetype = ADISCORD_armored_carrier_archetype
        parent = ADISCORD_ifv_2170
    }
}
"""
        units = """
sub_units = {
    ADISCORD_mechanized_infantry = {
        active = no
        type = { mechanized }
        transport = ADISCORD_armored_carrier_archetype
        essential = { infantry_equipment ADISCORD_armored_carrier_archetype }
        need = {
            infantry_equipment = 100
            ADISCORD_squad_weapons_equipment = 8
            ADISCORD_armored_carrier_archetype = 40
        }
    }
}
"""
        technology = """
ADISCORD_tech_armored_carrier_program = {
    enable_equipments = { ADISCORD_armored_carrier_2163 }
    enable_subunits = { ADISCORD_mechanized_infantry }
}
ADISCORD_tech_infantry_combat_vehicle_program = {
    enable_equipments = { ADISCORD_ifv_2170 }
}
ADISCORD_tech_networked_mechanized_cells = {
    enable_equipments = { ADISCORD_networked_ifv_2183 }
}
"""
        templates = """
ADISCORD_tank_battlegroup = {
    enable = {
        has_equipment = { ADISCORD_armored_carrier_archetype > 240 }
    }
    target_template = {
        regiments = {
            ADISCORD_mechanized_infantry = 6
            ADISCORD_combat_platform = 4
        }
    }
}
"""
        strategy = """
ADISCORD_produce_armored_carriers = {
    enable = {
        has_tech = ADISCORD_tech_armored_carrier_program
        num_of_military_factories > 6
    }
    ai_strategy = {
        type = equipment_production_min_factories_archetype
        id = ADISCORD_armored_carrier_archetype
        value = 1
    }
}
"""
        self.assertEqual(
            check(equipment, units, technology, templates, strategy), []
        )

    def test_modern_land_warfare_contract_rejects_foot_tank_force(self) -> None:
        check = getattr(validator, "modern_land_warfare_contract_issues", None)
        self.assertIsNotNone(check)
        issues = check(
            "equipments = { ADISCORD_armored_carrier_archetype = { is_archetype = yes } }",
            "sub_units = { ADISCORD_mechanized_infantry = { active = no } }",
            "ADISCORD_tech_armored_carrier_program = { }",
            "ADISCORD_tank_battlegroup = { target_template = { regiments = { infantry = 6 ADISCORD_combat_platform = 4 } } }",
            "ADISCORD_produce_armored_carriers = { enable = { num_of_military_factories > 12 } }",
        )
        for fragment in (
            "three carrier generations",
            "carrier archetype transport",
            "unlock generations",
            "six mechanized battalions",
            "carrier stock gate",
            "carrier production floor",
        ):
            self.assertTrue(any(fragment in issue for issue in issues), issues)

    def test_missing_equipment_unlock_is_reported(self) -> None:
        tech_id = "ADISCORD_tech_postwar_weapon_standardization"
        broken = dict(self.tech_blocks)
        broken[tech_id] = broken[tech_id].replace(
            "\n\t\tenable_equipments = { infantry_equipment_0 }",
            "",
            1,
        )
        issues = validator.check_equipment_unlocks(
            broken,
            validator.collect_equipment_keys(),
        )
        self.assertTrue(
            any(tech_id in issue and "equipment unlocks are" in issue for issue in issues),
            issues,
        )

    def test_broken_xor_block_is_reported(self) -> None:
        tech_id = "ADISCORD_tech_concentrated_industrial_zones"
        broken = dict(self.tech_blocks)
        broken[tech_id] = broken[tech_id].replace(
            "\n\t\t\tADISCORD_tech_distributed_workshop_networks",
            "",
            1,
        )
        issues = validator.check_technology_gridboxes(broken)
        self.assertTrue(
            any(tech_id in issue and "XOR is" in issue for issue in issues),
            issues,
        )

    def test_temporary_xor_that_never_rejoins_is_reported(self) -> None:
        graphs = dict(validator.GENERATED_BRANCH_GRAPHS)
        original = graphs["production"]
        successors = list(original.successors)
        successors[6] = ()
        graphs["production"] = replace(original, successors=tuple(successors))
        with patch.object(validator, "GENERATED_BRANCH_GRAPHS", graphs):
            issues = validator.check_technology_graph_quality(self.tech_blocks)
        self.assertTrue(
            any("temporary choice" in issue and "never rejoins" in issue for issue in issues),
            issues,
        )

    def test_legacy_reference_in_a_temp_tree_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            common = temp_root / "common"
            common.mkdir()
            (common / "bad_reference.txt").write_text(
                "trigger = { has_tech = ADISCORD_tech_state_debt_instruments }\n",
                encoding="utf-8",
            )
            with (
                patch.object(validator, "ROOT", temp_root),
                patch.object(validator, "LOCAL_TECH_REFERENCE_ROOTS", ["common"]),
            ):
                issues = validator.check_local_technology_references(self.defined_techs)
        self.assertTrue(
            any("ADISCORD_tech_state_debt_instruments" in issue for issue in issues),
            issues,
        )

    def test_retired_ai_strategy_id_in_a_temp_tree_is_reported(self) -> None:
        manifest_source = (
            validator.ROOT
            / "tools"
            / "data"
            / "adiscord_technology_id_migrations.json"
        ).read_text(encoding="utf-8")
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            common = temp_root / "common"
            manifest_dir = temp_root / "tools" / "data"
            common.mkdir()
            manifest_dir.mkdir(parents=True)
            (manifest_dir / "adiscord_technology_id_migrations.json").write_text(
                manifest_source,
                encoding="utf-8",
            )
            (common / "bad_ai_strategy.txt").write_text(
                "ai_strategy = { type = research_weight_factor "
                "id = ADISCORD_tech_state_debt_instruments value = 50 }\n",
                encoding="utf-8",
            )
            with (
                patch.object(validator, "ROOT", temp_root),
                patch.object(validator, "LOCAL_TECH_REFERENCE_ROOTS", ["common"]),
            ):
                issues = validator.check_technology_migration_contract(self.defined_techs)
        self.assertTrue(
            any("retired technology ID ADISCORD_tech_state_debt_instruments" in issue for issue in issues),
            issues,
        )

    def test_starting_profile_with_both_permanent_choices_is_reported(self) -> None:
        profiles = dict(validator.GENERATED_STARTING_TECH_PROFILES)
        profiles["common"] = (
            *profiles["common"],
            "ADISCORD_tech_concentrated_industrial_zones",
            "ADISCORD_tech_distributed_workshop_networks",
        )
        with patch.object(validator, "GENERATED_STARTING_TECH_PROFILES", profiles):
            issues = validator.check_campaign_technology_baseline(self.tech_blocks)
        self.assertTrue(
            any("grants both permanent XOR choices" in issue for issue in issues),
            issues,
        )


if __name__ == "__main__":
    unittest.main()
