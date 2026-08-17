from __future__ import annotations

import re
import unittest
from pathlib import Path

from tools.validators import validate_adiscord_tech_doctrine as validator


ROOT = Path(__file__).resolve().parents[2]
PROGRESSION_ASSET = ROOT / "gfx/entities/zy_ADISCORD_infantry_weapon_progression.asset"
COUNTRY_ASSET = ROOT / "gfx/entities/zz_ADISCORD_country_infantry.asset"

SOURCE_PREFIXES = (
    "HOL_infantry_weapon_rifle",
    "SHX_infantry_weapon_rifle",
    "MEX_infantry_weapon_rifle",
    "XSM_infantry_weapon_mg",
    "HOL_infantry_weapon_mg",
    "YUN_infantry_weapon_mg",
    "PRC_infantry_weapon_mg",
    "MEX_infantry_weapon_mg",
)
POSES = ("right", "left", "long_idle")
ATTACHMENTS = (
    ("rifle1", "Right_Hand_node", "right"),
    ("rifle2", "Left_Hand_node", "left"),
    ("rifle3", "mid_back_node", "long_idle"),
    ("rifle4", "Root_node_2", "right"),
)


def entity_blocks(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    blocks: dict[str, str] = {}
    for match in re.finditer(r"(?m)^\s*entity\s*=\s*\{", text):
        block = validator.extract_block(text, match.start())
        name = re.search(r'\bname\s*=\s*"([A-Za-z0-9_]+)"', block)
        if name:
            blocks[name.group(1)] = block
    return blocks


def generic_entity_name(level: int) -> str:
    return "infantry_entity" if level == 0 else f"generic_infantry_{level + 1}_entity"


def custom_entity_name(prefix: str, level: int) -> str:
    return f"{prefix}_entity" if level == 0 else f"{prefix}_{level + 1}_entity"


class GlobalInfantryWeaponProgressionTests(unittest.TestCase):
    def test_all_weapon_wrappers_clone_the_approved_vanilla_entities(self) -> None:
        blocks = entity_blocks(PROGRESSION_ASSET)
        wrapper_names = [
            name
            for name in re.findall(
                r'(?m)^\s*name\s*=\s*"([A-Za-z0-9_]+)"',
                PROGRESSION_ASSET.read_text(encoding="utf-8"),
            )
            if re.fullmatch(
                r"ADISCORD_infantry_weapon_[A-Za-z0-9_]+_entity",
                name,
            )
        ]
        expected_wrapper_names = {
            f"ADISCORD_infantry_weapon_{level}_{pose}_entity"
            for level in range(8)
            for pose in POSES
        }
        self.assertCountEqual(wrapper_names, expected_wrapper_names)
        for level, source_prefix in enumerate(SOURCE_PREFIXES):
            for pose in POSES:
                wrapper = f"ADISCORD_infantry_weapon_{level}_{pose}_entity"
                source = f"{source_prefix}_{pose}_entity"
                with self.subTest(level=level, pose=pose):
                    self.assertIn(wrapper, blocks)
                    self.assertRegex(
                        blocks[wrapper],
                        rf'\bclone\s*=\s*"{re.escape(source)}"',
                    )
                    for field in (
                        "pdxmesh",
                        "scale",
                        "transform",
                        "animation",
                        "state",
                    ):
                        self.assertNotRegex(
                            blocks[wrapper], rf"\b{field}\s*=",
                        )

    def test_generic_entity_chain_attaches_the_matching_wrapper_level(self) -> None:
        blocks = entity_blocks(PROGRESSION_ASSET)
        expected_props = (
            ("lighter", "Right_Hand_node_4", "lighter_entity"),
            ("cigarette1", "Right_Hand_node_2", "cigarette_entity"),
            ("cigarette_package1", "Right_Hand_node_3", "cigarette_package_entity"),
            ("cigarette_package2", "Left_Hand_node_2", "cigarette_package_entity"),
            ("cigarette2", "Root_node_1", "cigarette_entity"),
        )
        for level in range(8):
            entity = generic_entity_name(level)
            with self.subTest(level=level, entity=entity):
                self.assertIn(entity, blocks)
                expected_parent = (
                    "infantry_rifle_entity" if level == 0 else "infantry_2_entity"
                )
                self.assertRegex(
                    blocks[entity],
                    rf'\bclone\s*=\s*"{re.escape(expected_parent)}"',
                )
                self.assertRegex(blocks[entity], r"\bscale\s*=\s*0\.8\b")
                for attachment, node, pose in ATTACHMENTS:
                    wrapper = f"ADISCORD_infantry_weapon_{level}_{pose}_entity"
                    self.assertRegex(
                        blocks[entity],
                        rf'attach\s*=\s*\{{\s*name\s*=\s*"{attachment}"\s+'
                        rf'{node}\s*=\s*"{wrapper}"\s*\}}',
                    )
                for attachment, node, prop_entity in expected_props:
                    self.assertRegex(
                        blocks[entity],
                        rf'attach\s*=\s*\{{\s*name\s*=\s*"{attachment}"\s+'
                        rf'{node}\s*=\s*"{prop_entity}"\s*\}}',
                    )

    def test_custom_uniform_families_cover_every_visual_level(self) -> None:
        blocks = entity_blocks(COUNTRY_ASSET)
        families = (
            "STP_infantry",
            "NOD_infantry",
            "VAL_infantry",
            "CIN_infantry",
            "OSF_infantry",
            "APH_infantry",
            "APH_mountaineers",
        )
        for prefix in families:
            for level in range(8):
                entity = custom_entity_name(prefix, level)
                with self.subTest(prefix=prefix, level=level):
                    self.assertIn(entity, blocks)
                    for attachment, node, pose in ATTACHMENTS:
                        wrapper = f"ADISCORD_infantry_weapon_{level}_{pose}_entity"
                        self.assertRegex(
                            blocks[entity],
                            rf'attach\s*=\s*\{{\s*name\s*=\s*"{attachment}"\s+'
                            rf'{node}\s*=\s*"{wrapper}"\s*\}}',
                        )

    def test_custom_uniform_asset_has_no_legacy_regional_weapon_attach(self) -> None:
        text = COUNTRY_ASSET.read_text(encoding="utf-8")
        self.assertNotRegex(text, r'"(?:ENG|USA)_infantry_weapon_')

    def test_custom_family_body_meshes_remain_unchanged(self) -> None:
        blocks = entity_blocks(COUNTRY_ASSET)
        expected_meshes = {
            "STP_infantry_entity": "STP_infantry_hedonist_mesh",
            "STP_infantry_2_entity": "STP_infantry_hedonist_mesh",
            "VAL_infantry_entity": "VAL_infantry_mesh",
            "VAL_infantry_2_entity": "VAL_infantry_mesh",
            "CIN_infantry_entity": "ETH_irregular_infantry_mesh",
            "CIN_infantry_2_entity": "ETH_irregular_infantry_mesh",
            "OSF_infantry_entity": "ETH_irregular_infantry_mesh",
            "OSF_infantry_2_entity": "ETH_irregular_infantry_mesh",
            "APH_infantry_entity": "APH_irregular_infantry_mesh",
            "APH_infantry_2_entity": "APH_irregular_infantry_mesh",
            "APH_mountaineers_entity": "APH_afg_militia_rifle_mesh",
            "APH_mountaineers_2_entity": "APH_afg_militia_mg_mesh",
        }
        for entity, mesh in expected_meshes.items():
            with self.subTest(entity=entity):
                self.assertRegex(
                    blocks[entity],
                    rf'\bpdxmesh\s*=\s*"{re.escape(mesh)}"',
                )

    def test_custom_uniform_family_clone_bodies_remain_preserved(self) -> None:
        blocks = entity_blocks(COUNTRY_ASSET)
        for level in range(8):
            suffix = "" if level == 0 else f"_{level + 1}"
            entity = f"NOD_infantry{suffix}_entity"
            expected_parent = f"STP_infantry{suffix}_entity"
            with self.subTest(entity=entity):
                self.assertRegex(
                    blocks[entity],
                    rf'\bclone\s*=\s*"{re.escape(expected_parent)}"',
                )

        for prefix in (
            "STP_infantry",
            "VAL_infantry",
            "CIN_infantry",
            "OSF_infantry",
            "APH_infantry",
            "APH_mountaineers",
        ):
            for level in range(2, 8):
                entity = custom_entity_name(prefix, level)
                expected_parent = f"{prefix}_2_entity"
                with self.subTest(entity=entity):
                    self.assertRegex(
                        blocks[entity],
                        rf'\bclone\s*=\s*"{re.escape(expected_parent)}"',
                    )
