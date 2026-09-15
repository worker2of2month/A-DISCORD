from __future__ import annotations

import re
import unittest
from pathlib import Path

from tools.validators import validate_adiscord_tech_doctrine as validator


ROOT = Path(__file__).resolve().parents[2]
PROGRESSION_ASSET = ROOT / "gfx/entities/zy_ADISCORD_infantry_weapon_progression.asset"
COUNTRY_ASSET = ROOT / "gfx/entities/zz_ADISCORD_country_infantry.asset"

SOURCE_PREFIXES = (
    "BEL_infantry_weapon_rifle",
    "GER_infantry_weapon_mg_2",
    "BEL_infantry_weapon_mg_2",
    "BEL_infantry_weapon_mg_2",
    "BEL_infantry_weapon_mg_2",
    "BEL_infantry_weapon_mg_2",
    "BEL_infantry_weapon_mg_2",
    "BEL_infantry_weapon_mg_2",
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
    def test_nod_field_poses_preserve_weapon_family_without_smoking_or_prone_drills(self) -> None:
        entities = entity_blocks(COUNTRY_ASSET)
        for level in range(8):
            with self.subTest(level=level):
                body = entities[custom_entity_name("NOD_infantry", level)]
                states = [validator.extract_block(body, match.start())
                          for match in re.finditer(r"\bstate\s*=\s*\{", body)]
                idle = [state for state in states if re.search(r'name\s*=\s*"idle"', state)]
                training = [state for state in states if re.search(r'name\s*=\s*"training"', state)]
                self.assertEqual(len(idle), 4)
                self.assertEqual(len(training), 2)
                self.assertNotIn('"long_idle03"', "\n".join(idle))
                self.assertEqual({re.search(r'animation\s*=\s*"([^"]+)"', state)[1]
                                  for state in training}, {"idle", "aim_exercise"})
                self.assertIn(f'clone = "{custom_entity_name("STP_infantry", level)}"', body)

    def test_weapon_grip_uses_the_matching_body_animation_family(self) -> None:
        entities = entity_blocks(COUNTRY_ASSET)
        text = (ROOT / "gfx/entities/ADISCORD_country_infantry.gfx").read_text(encoding="utf-8")
        meshes = {}
        for match in re.finditer(r"\bpdxmesh\s*=\s*\{", text):
            block = validator.extract_block(text, match.start())
            name = re.search(r'\bname\s*=\s*"([^"]+)"', block)[1]
            meshes[name] = dict(re.findall(r'animation\s*=\s*\{\s*id\s*=\s*"([^"]+)"\s+type\s*=\s*"([^"]+)"', block))

        def body_animations(entity: str) -> dict[str, str]:
            seen = set()
            while entity not in seen:
                seen.add(entity)
                block = entities[entity]
                mesh = re.search(r'\bpdxmesh\s*=\s*"([^"]+)"', block)
                if mesh:
                    return meshes[mesh[1]]
                entity = re.search(r'\bclone\s*=\s*"([^"]+)"', block)[1]
            self.fail("Entity clone cycle")

        expected = {}
        for prefix in ("STP", "STS", "NOD", "VAL", "CIN", "OSF", "APH"):
            for level in range(8):
                expected[custom_entity_name(prefix + "_infantry", level)] = "rifle" if level == 0 else "mg"
        for name in ("ADISCORD_STP_party_entity", "ADISCORD_STS_regular_entity", "ADISCORD_VAL_regular_entity"):
            expected[name] = "mg"
        for entity, family in expected.items():
            with self.subTest(entity=entity):
                animations = body_animations(entity)
                for state, clip in (("idle", "idle"), ("move", "moving"), ("attack", "attack"), ("support_attack", "support_attack")):
                    self.assertEqual(animations[state], f"GER_infantry_{family}_{clip}_animation")
                if entity.startswith("NOD_infantry"):
                    aim = "GER_infantry_aim_exercise_animation" if family == "rifle" else "GER_infantry_aim_exercise_mg_animation"
                    self.assertEqual(animations["aim_exercise"], aim)

    def test_val_smoke_uses_each_body_head_locator(self) -> None:
        blocks = entity_blocks(COUNTRY_ASSET)
        cases=[("VAL_infantry_entity", "head"),
               ("VAL_infantry_2_entity", "head"),
               ("ADISCORD_VAL_regular_entity", "head")]
        cases += [(custom_entity_name("VAL_ADISCORD_militia", level), "back_mid|head|head")
                  for level in range(8)]
        for entity, node in cases:
            self.assertIn(f'node="{node}"', blocks[entity])
            self.assertEqual(len(re.findall(r'name\s*=\s*"idle"', blocks[entity])), 5)

    def test_weapon_generations_keep_native_attachment_contracts(self) -> None:
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
                    self.assertRegex(
                        blocks[wrapper],
                        rf'\bpdxmesh\s*=\s*"ADISCORD_infantry_weapon_{level}_mesh"',
                    )
                    for field in (
                        "scale",
                        "transform",
                    ):
                        self.assertNotRegex(
                            blocks[wrapper], rf"\b{field}\s*=",
                        )
                    for state in ("idle", "move"):
                        self.assertRegex(blocks[wrapper],rf'state\s*=\s*\{{\s*name\s*=\s*"{state}"\s+animation\s*=\s*"idle"')

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

    def test_country_body_meshes_use_their_selected_forms(self) -> None:
        blocks = entity_blocks(COUNTRY_ASSET)
        text = (ROOT / "gfx/entities/ADISCORD_country_infantry.gfx").read_text(encoding="utf-8")
        mesh_files = {}
        for match in re.finditer(r"\bpdxmesh\s*=\s*\{", text):
            block = validator.extract_block(text, match.start())
            name = re.search(r'\bname\s*=\s*"([^"]+)"', block)[1]
            mesh_files[name] = re.search(r'\bfile\s*=\s*"([^"]+)"', block)[1]
        expected_meshes = {
            "STP_infantry_entity": "ADISCORD_STP_party_rifle_mesh",
            "STP_infantry_2_entity": "ADISCORD_STP_party_mesh",
            "VAL_infantry_entity": "ADISCORD_VAL_regular_rifle_mesh",
            "VAL_infantry_2_entity": "ADISCORD_VAL_regular_mesh",
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
                    r'\bpdxmesh\s*=\s*"[^"]+"',
                )
                actual_mesh = re.search(r'\bpdxmesh\s*=\s*"([^"]+)"', blocks[entity])[1]
                self.assertEqual(mesh_files[actual_mesh], mesh_files[mesh])

    def test_militia_and_regular_forms_remain_distinct_at_every_weapon_tier(self) -> None:
        blocks = entity_blocks(COUNTRY_ASSET)
        families={"STP":("STP_party","STP_infantry_hedonist_mesh","STP_infantry_hedonist_mg_mesh"),
                  "STS":("STS_regular","STP_shabrat_infantry_mesh","STP_shabrat_mg_infantry_mesh"),
                  "VAL":("VAL_regular","VAL_infantry_mesh","VAL_infantry_mg_mesh")}
        for tag,(regular,rifle,mg) in families.items():
            for level in range(8):
                with self.subTest(tag=tag,level=level):
                    strong=custom_entity_name(tag+"_infantry",level)
                    weak=custom_entity_name(tag+"_ADISCORD_militia",level)
                    strong_mesh=f"ADISCORD_{regular}"+("_mesh" if level else "_rifle_mesh")
                    self.assertIn(f'pdxmesh = "{strong_mesh}"',blocks[strong])
                    self.assertIn(f'pdxmesh = "{mg if level else rifle}"',blocks[weak])
                    self.assertIn(f'clone = "{strong}"',blocks[weak])

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
                mesh="ADISCORD_NOD_line_mesh" if level else "ADISCORD_NOD_line_rifle_mesh"
                self.assertIn(f'pdxmesh = "{mesh}"',blocks[entity])

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

    def test_highland_infantry_covers_normal_militia_and_mountaineer_selection(self) -> None:
        blocks = entity_blocks(COUNTRY_ASSET)
        for level in range(8):
            suffix = "" if level == 0 else f"_{level + 1}"
            for role in ("infantry", "ADISCORD_militia", "mountaineers"):
                name = f"SRP_{role}{suffix}_entity"
                with self.subTest(entity=name):
                    self.assertTrue(name in blocks, name)
                    family = f"ADISCORD_SRP_highland_infantry{suffix}_entity"
                    self.assertIn(f'clone = "{family}"', blocks[name])
