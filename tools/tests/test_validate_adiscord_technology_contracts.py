from __future__ import annotations

import re
import shutil
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
            "position = { x = 2 y = 0 }",
            "position = { x = 0 y = 2 }",
            1,
        )
        issues = validator.check_technology_parser_constraints(broken)
        self.assertTrue(
            any(tech_id in issue and "grid position (0, 2)" in issue for issue in issues),
            issues,
        )

    def test_grid_step_larger_than_connector_is_reported(self) -> None:
        gui = validator.read_text(validator.ROOT / "interface/countrytechtreeview.gui")
        broken_gui = gui.replace(
            "slotsize = { width = 70 height = 70 }",
            "slotsize = { width = 70 height = 96 }",
            1,
        )
        self.assertNotEqual(gui, broken_gui)
        with patch.object(validator, "read_text", return_value=broken_gui):
            issues = validator.check_technology_gridboxes(self.tech_blocks)
        self.assertTrue(
            any("infantry_folder" in issue and "native connector" in issue for issue in issues),
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
        STP = { STP_initialize_core_mechanics = yes }
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

    def test_shared_startup_rejects_inline_stp_army_lock(self) -> None:
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
        STP = { %s }
        every_country = { ADISCORD_economy_initialize_country = yes }
        set_global_flag = ADISCORD_starting_technology_profiles_applied
    } } }
    on_monthly = { effect = { if = { limit = { has_global_flag = ADISCORD_fresh_campaign_contract_v1 } ADISCORD_tick_all_society_development_monthly = yes } } }
    on_yearly = { effect = { if = { limit = { has_global_flag = ADISCORD_fresh_campaign_contract_v1 } ADISCORD_tick_all_society_development_yearly = yes } } }
}
"""
        # The idea gate lives in the initializer, so an inline lock is a regression.
        issues = validator.fresh_campaign_startup_contract_issues(
            history,
            startup % "STP_initialize_core_mechanics = yes\n        ADISCORD_STP_lock_regular_army_templates = yes",
        )
        self.assertTrue(any("inline" in issue for issue in issues), issues)

        # Dropping the initializer leaves startup army state non-deterministic.
        issues = validator.fresh_campaign_startup_contract_issues(
            history, startup % "set_country_flag = STP_placeholder"
        )
        self.assertTrue(
            any("STP_initialize_core_mechanics" in issue for issue in issues), issues
        )

        issues = validator.fresh_campaign_startup_contract_issues(
            history,
            startup % "ADISCORD_STP_migrate_army_template_lock = yes\n        STP_initialize_core_mechanics = yes",
        )
        self.assertTrue(any("old-save migration" in issue for issue in issues), issues)

    def test_missing_energy_price_is_reported(self) -> None:
        tech_id = "ADISCORD_tech_concentrated_industrial_zones"
        broken = dict(self.tech_blocks)
        # Strip the line whatever its value, so rebalancing the industry band
        # cannot quietly turn this negative test into a no-op.
        broken[tech_id], removed = re.subn(
            r"\n\t\tfactory_energy_consumption = [0-9.]+",
            "",
            broken[tech_id],
            count=1,
        )
        self.assertEqual(removed, 1)
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

    def test_supply_motorization_has_real_unlocked_transport(self) -> None:
        equipment = validator.collect_equipment_blocks()
        trucks = [key for key, body in equipment.items() if re.search(r"\bsupply_truck\s*=\s*yes\b", body)]
        self.assertEqual(trucks, ["motorized_equipment"])
        self.assertIn("archetype = motorized_equipment", equipment["motorized_equipment_1"])
        self.assertNotIn("supply_truck", equipment["support_equipment"])
        self.assertIn("motorized_equipment_1", self.tech_blocks["ADISCORD_tech_restored_truck_fleets"])
        from tools.builders import build_adiscord_technology_system as builder
        for tag in ("STP", "NOD", "VAL", "WRK", "VAD", "YPR", "COF", "TFF"):
            technologies = set(builder.STARTING_TECH_PROFILES["common"])
            for profile in builder.STARTING_COUNTRY_TECH_PROFILES[tag]:
                technologies.update(builder.STARTING_TECH_PROFILES[profile])
            self.assertIn("ADISCORD_tech_restored_truck_fleets", technologies, tag)
            source = validator.read_text(validator.ROOT / f"history/units/{tag}.txt")
            self.assertRegex(source, r"add_equipment_to_stockpile\s*=\s*\{\s*type\s*=\s*motorized_equipment_1\s+amount\s*=\s*[1-9]\d*", tag)
        for claimant in ("WRK", "TVA"):
            source = validator.read_text(validator.ROOT / f"history/units/{claimant}_vorkerland_collapse_air.txt")
            self.assertRegex(source, r"type\s*=\s*motorized_equipment_1\s+amount\s*=\s*[1-9]\d*", claimant)
            self.assertRegex(source, r"type\s*=\s*train_equipment_1\s+amount\s*=\s*[1-9]\d*", claimant)

    def test_naval_ai_goal_replacement_retains_required_objectives(self) -> None:
        descriptor = validator.read_text(validator.ROOT / "descriptor.mod")
        self.assertRegex(descriptor, r'replace_path\s*=\s*"common/ai_navy/goals"')
        registered = set()
        for path in (validator.ROOT / "common/country_tags").glob("*.txt"):
            registered.update(re.findall(r"(?m)^\s*([A-Z0-9]{3})\s*=", validator.read_text(path)))
        objectives = set()
        paths = list((validator.ROOT / "common/ai_navy/goals").glob("*.txt"))
        self.assertTrue(paths, "Replacing naval goals must supply usable objectives")
        for path in paths:
            self.assertFalse(path.read_bytes().startswith(b"\xef\xbb\xbf"))
            source = validator.strip_comments(validator.read_text(path))
            for name in validator.top_level_keys(source):
                goal = validator.top_level_blocks(source, name)[0]
                for key in ("available_for", "blocked_for"):
                    for country_filter in validator.top_level_blocks(goal, key):
                        tags = set(country_filter.split())
                        self.assertTrue(tags, f"{name}: an empty filter disrupts native parsing")
                        self.assertFalse(tags - registered, f"{name}: unknown tags {tags - registered}")
                allowed = validator.top_level_blocks(goal, "available_for")
                self.assertEqual(len(allowed), 1, name)
                self.assertTrue({"STP", "STS", "NOD", "VAL"} <= set(allowed[0].split()), name)
                objective = re.search(r"\bobjective_type\s*=\s*(\w+)", goal)
                self.assertIsNotNone(objective, name)
                self.assertNotIn(objective[1], objectives, "Each objective needs one active policy")
                objectives.add(objective[1])
        self.assertEqual(objectives, {
            "naval_invasion_support", "naval_invasion_defense", "coast_defense",
            "convoy_protection", "convoy_raiding", "naval_dominance", "training",
            "mines_sweeping", "mines_planting", "naval_blockade",
        })

    def test_starting_naval_profile_opens_native_invasion_transport(self) -> None:
        from tools.builders import build_adiscord_technology_system as builder
        tech_id = "ADISCORD_tech_restored_dockyards"
        branch = next(branch for branch in builder.BRANCHES if branch.key == "naval_support")
        index = next(index for index, tech in enumerate(branch.techs) if tech.id == tech_id)
        for source in (self.tech_blocks[tech_id], builder.render_technology(branch, index)):
            self.assertRegex(source, r"\bnaval_invasion_capacity\s*=\s*100\b")
            self.assertNotRegex(source, r"\bnaval_invasion_(?:division|plan)_cap\s*=")
        for tag in ("STP", "NOD", "VAL"):
            technologies = set(builder.STARTING_TECH_PROFILES["common"])
            for profile in builder.STARTING_COUNTRY_TECH_PROFILES[tag]:
                technologies.update(builder.STARTING_TECH_PROFILES[profile])
            self.assertIn(tech_id, technologies, tag)

    def test_naval_fleets_can_use_the_real_starting_ship_composition(self) -> None:
        from collections import Counter

        descriptor = validator.read_text(validator.ROOT / "descriptor.mod")
        sources = {}
        for kind in ("taskforce", "fleet"):
            self.assertRegex(descriptor, rf'replace_path\s*=\s*"common/ai_navy/{kind}"')
            sources[kind] = {}
            for path in (validator.ROOT / f"common/ai_navy/{kind}").glob("*.txt"):
                self.assertFalse(path.read_bytes().startswith(b"\xef\xbb\xbf"))
                source = validator.strip_comments(validator.read_text(path))
                for name in validator.top_level_keys(source):
                    self.assertNotIn(name, sources[kind])
                    sources[kind][name] = validator.top_level_blocks(source, name)[0]
            self.assertTrue(sources[kind], f"{kind}: replacement must provide usable templates")

        registered = set()
        for path in (validator.ROOT / "common/country_tags").glob("*.txt"):
            registered.update(re.findall(r"(?m)^\s*([A-Z0-9]{3})\s*=", validator.read_text(path)))
        subunits = validator.collect_defined_subunits()
        missions, minimums = {}, {}
        for name, template in sources["taskforce"].items():
            allowed = validator.top_level_blocks(template, "allowed")[0]
            filters = validator.top_level_blocks(allowed, "OR")
            self.assertEqual(len(filters), 1, name)
            tags = set(re.findall(r"\boriginal_tag\s*=\s*(\w+)", filters[0]))
            self.assertTrue({"STP", "STS", "NOD", "VAL"} <= tags, name)
            self.assertFalse(tags - registered, name)
            missions[name] = set(validator.top_level_blocks(template, "mission")[0].split())
            self.assertEqual(len(missions[name]), 1, "Native taskforce templates select one mission")
            composition = {}
            for kind in ("min_composition", "optimal_composition"):
                body = validator.top_level_blocks(template, kind)[0]
                ships = validator.top_level_keys(body)
                self.assertTrue(ships, name)
                self.assertFalse(ships - subunits, f"{name}: nonexistent ship types {ships - subunits}")
                composition[kind] = {ship: int(re.search(r"\bamount\s*=\s*(\d+)",
                                        validator.top_level_blocks(body, ship)[0])[1]) for ship in ships}
            minimums[name] = composition["min_composition"]
            for ship, number in minimums[name].items():
                self.assertGreater(number, 0)
                self.assertGreaterEqual(composition["optimal_composition"].get(ship, 0), number)

        supported = set()
        for name, fleet in sources["fleet"].items():
            required = validator.top_level_blocks(fleet, "required_taskforces")[0]
            requirements = dict((key, int(value)) for key, value in re.findall(r"(\w+)\s*=\s*(\d+)", required))
            self.assertTrue(requirements, name)
            for kind in ("required_taskforces", "optional_taskforces"):
                for body in validator.top_level_blocks(fleet, kind):
                    for taskforce in re.findall(r"(\w+)\s*=", body):
                        self.assertIn(taskforce, minimums, name)
                        supported.update(missions[taskforce])
            needed = Counter()
            for taskforce, count in requirements.items():
                self.assertGreater(count, 0)
                needed.update({ship: number * count for ship, number in minimums[taskforce].items()})
            for tag in ("STP", "NOD", "VAL"):
                oob = validator.read_text(validator.ROOT / f"history/units/{tag}.txt")
                stock = Counter(re.findall(r"\bdefinition\s*=\s*(\w+)", oob))
                self.assertFalse(needed - stock, f"{tag} cannot assemble {name} from its real ships")
        self.assertTrue({"naval_patrol", "naval_strike", "convoy_escort", "convoy_raiding",
                         "naval_invasion_support"} <= supported)

    def test_supply_validator_rejects_missing_or_misassigned_trucks(self) -> None:
        equipment = validator.collect_equipment_blocks()
        for replacement in ("", "support_equipment"):
            broken = dict(equipment)
            broken["motorized_equipment"] = broken["motorized_equipment"].replace("supply_truck = yes", "")
            if replacement:
                broken[replacement] += "\n supply_truck = yes"
            with patch.object(validator, "collect_equipment_blocks", return_value=broken):
                issues = validator.check_equipment_parser_constraints()
            self.assertTrue(any("supply motorization" in issue for issue in issues), issues)

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

    def test_infantry_visual_contract_rejects_regressed_equipment_level(self) -> None:
        equipment_path = (
            validator.ROOT
            / "common/units/equipment/ADISCORD_infantry_equipment.txt"
        )
        equipment = validator.read_text(equipment_path)
        match = re.search(
            r"(?m)^\s*ADISCORD_infantry_equipment_2200\s*=\s*\{",
            equipment,
        )
        self.assertIsNotNone(match)
        start = match.start()
        block = validator.extract_block(equipment, start)
        self.assertIn("visual_level = 7", block)
        broken_block = block.replace("visual_level = 7", "visual_level = 3", 1)
        broken_equipment = (
            equipment[:start] + broken_block + equipment[start + len(block):]
        )

        original_read = validator.read_text

        def fake_read(path: Path) -> str:
            return broken_equipment if path == equipment_path else original_read(path)

        with patch.object(validator, "read_text", side_effect=fake_read):
            issues = validator.check_infantry_visual_model_chain()
        self.assertTrue(
            any("ADISCORD_infantry_equipment_2200" in issue for issue in issues),
            issues,
        )

    def test_infantry_visual_contract_rejects_missing_weapon_wrapper(self) -> None:
        progression_path = (
            validator.ROOT
            / "gfx/entities/zy_ADISCORD_infantry_weapon_progression.asset"
        )
        progression = validator.read_text(progression_path)
        broken_progression = progression.replace(
            'name = "ADISCORD_infantry_weapon_7_right_entity"',
            'name = "ADISCORD_infantry_weapon_7_right_entity_BROKEN"',
            1,
        )
        self.assertNotEqual(progression, broken_progression)
        original_read = validator.read_text

        def fake_read(path: Path) -> str:
            if path == progression_path:
                return broken_progression
            return original_read(path)

        with patch.object(validator, "read_text", side_effect=fake_read):
            issues = validator.check_infantry_visual_model_chain()
        self.assertTrue(
            any("ADISCORD_infantry_weapon_7_right_entity" in issue for issue in issues),
            issues,
        )

    def test_infantry_visual_contract_reports_missing_progression_asset_without_throwing(self) -> None:
        equipment_relative_path = Path(
            "common/units/equipment/ADISCORD_infantry_equipment.txt"
        )
        country_asset_relative_path = Path(
            "gfx/entities/zz_ADISCORD_country_infantry.asset"
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            for relative_path in (
                equipment_relative_path,
                country_asset_relative_path,
            ):
                target = temp_root / relative_path
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(validator.ROOT / relative_path, target)
            with patch.object(validator, "ROOT", temp_root):
                issues = validator.check_infantry_visual_model_chain()
        self.assertTrue(
            any("global infantry weapon progression asset missing" in issue for issue in issues),
            issues,
        )

    def test_infantry_visual_contract_rejects_regressed_generic_body_contract(self) -> None:
        progression_path = (
            validator.ROOT
            / "gfx/entities/zy_ADISCORD_infantry_weapon_progression.asset"
        )
        progression = validator.read_text(progression_path)
        regressions = {
            "parent": (
                'clone = "infantry_rifle_entity"\n\tname = "infantry_entity"',
                'clone = "infantry_2_entity"\n\tname = "infantry_entity"',
                "infantry_entity must clone infantry_rifle_entity",
            ),
            "scale": (
                'name = "infantry_entity"\n\tattach = { name = "rifle1"',
                'name = "infantry_entity"\n\tscale = 1.0\n\tattach = { name = "rifle1"',
                "infantry_entity scale is 1.0; expected 0.8",
            ),
            "prop": (
                'attach = { name = "lighter" Right_Hand_node_4 = "lighter_entity" }',
                'attach = { name = "lighter_BROKEN" Right_Hand_node_4 = "lighter_entity" }',
                "infantry_entity must preserve lighter attachment",
            ),
        }
        original_read = validator.read_text
        for regression, (old, new, expected_issue) in regressions.items():
            with self.subTest(regression=regression):
                broken_progression = progression.replace(old, new, 1)
                self.assertNotEqual(progression, broken_progression)

                def fake_read(path: Path) -> str:
                    return (
                        broken_progression
                        if path == progression_path
                        else original_read(path)
                    )

                with patch.object(validator, "read_text", side_effect=fake_read):
                    issues = validator.check_infantry_visual_model_chain()
                self.assertIn(expected_issue, issues)

    def test_infantry_visual_contract_rejects_regressed_custom_second_level_mesh(self) -> None:
        country_asset_path = (
            validator.ROOT / "gfx/entities/zz_ADISCORD_country_infantry.asset"
        )
        country_asset = validator.read_text(country_asset_path)
        broken_country_asset = country_asset.replace(
            'name = "STP_infantry_2_entity"\n\tpdxmesh = "STP_infantry_hedonist_mg_mesh"',
            'name = "STP_infantry_2_entity"\n\tpdxmesh = "STP_infantry_hedonist_mesh_BROKEN"',
            1,
        )
        self.assertNotEqual(country_asset, broken_country_asset)
        original_read = validator.read_text

        def fake_read(path: Path) -> str:
            return (
                broken_country_asset if path == country_asset_path else original_read(path)
            )

        with patch.object(validator, "read_text", side_effect=fake_read):
            issues = validator.check_infantry_visual_model_chain()
        self.assertIn(
            "STP_infantry_2_entity pdxmesh is STP_infantry_hedonist_mesh_BROKEN; "
            "expected STP_infantry_hedonist_mg_mesh",
            issues,
        )


if __name__ == "__main__":
    unittest.main()
