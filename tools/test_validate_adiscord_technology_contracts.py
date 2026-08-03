from __future__ import annotations

import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from tools import validate_adiscord_tech_doctrine as validator


class TechnologyValidatorNegativeTests(unittest.TestCase):
    """Prove that the focused validator rejects representative regressions."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.defined_techs, cls.tech_blocks = validator.collect_technologies()

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
