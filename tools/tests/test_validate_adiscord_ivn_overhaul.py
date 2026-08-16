from __future__ import annotations

import re
import unittest
from pathlib import Path

from PIL import Image

from tools.builders import build_adiscord_ivn_geography as geography_builder
from tools.builders import build_adiscord_map_buildings as map_buildings
from tools.validators import validate_adiscord_ivn_overhaul as validator


ROOT = Path(__file__).resolve().parents[2]

EXPECTED_PROVINCES = {
    128: {579, 7125, 8423, 9072},
    693: {1191, 1744, 2219, 2991, 4334, 6905, 6928, 7678, 8048, 10730},
    694: {2553, 5448, 11841, 12189},
    695: {157, 217, 482, 1105, 1763, 2736, 3038, 3181, 3304, 3541, 3579, 4572, 5016, 6146, 6345, 8068, 8505, 8615, 9608, 10158, 10668, 10769, 10810, 10879, 11487, 12017, 12054},
    696: {722, 1304, 2025, 2157, 2211, 3847, 4037, 5521, 5540, 5573, 5729, 6622, 7911, 8515, 9133, 9344, 11115, 11132, 12317, 12880, 12914},
    697: {401, 1385, 1429, 3273, 4277, 4646, 5055, 5273, 6350, 6827, 6979, 6991, 7263, 8885, 9037, 9132, 9150, 9160, 9418, 9778, 11000, 12383},
    25: {694, 932, 1634, 1861, 1862, 3017, 3302, 3503, 3648, 3714, 4503, 4534, 4909, 5611, 6580, 7508, 7654, 8717, 9066, 9236, 9598, 9614, 10539, 10675, 10835, 10885, 11124, 11612, 11653, 12313, 12410, 12790, 12899, 16568},
    698: {1768, 1890, 2380, 3828, 3919, 5798, 6971, 8328, 8371, 9611, 10313, 10357, 10403, 10548, 12076, 12122},
}

EXPECTED_VPS = {
    25: {16568: 10}, 92: {3462: 1}, 95: {3318: 3}, 96: {888: 3},
    97: {838: 3}, 98: {2448: 5}, 99: {882: 7}, 100: {702: 5},
    101: {9327: 3}, 127: {595: 3}, 128: {579: 1}, 129: {1971: 1},
    130: {3447: 2}, 131: {2262: 2}, 132: {423: 2}, 164: {4217: 1},
    693: {6905: 5}, 694: {11841: 3}, 695: {1763: 3}, 696: {5573: 3},
    697: {9160: 3}, 698: {12076: 3},
}


def state_text(state_id: int) -> str:
    matches = tuple((ROOT / "history/states").glob(f"{state_id}-*.txt"))
    if len(matches) != 1:
        raise AssertionError(f"state {state_id}: expected one file, found {len(matches)}")
    return matches[0].read_text(encoding="utf-8-sig")


def provinces(source: str) -> set[int]:
    match = re.search(r"\bprovinces\s*=\s*\{([^}]*)\}", source, re.DOTALL)
    if match is None:
        raise AssertionError("missing provinces block")
    return {int(value) for value in re.findall(r"\d+", match.group(1))}


def victory_points(source: str) -> dict[int, int]:
    return {
        int(province): int(value)
        for province, value in re.findall(
            r"\bvictory_points\s*=\s*\{\s*(\d+)\s+(\d+)\s*\}", source
        )
    }


class IvanlandOverhaulContractTests(unittest.TestCase):
    def test_integrated_validator_accepts_reviewed_city_split_hash(self) -> None:
        self.assertTrue(hasattr(validator, "province_geometry_issue"))
        self.assertIsNone(validator.province_geometry_issue())

    def test_integrated_validator_passes(self) -> None:
        self.assertEqual(validator.collect_issues(), [])

    def test_geography_contract_covers_real_terrain_and_tree_outputs(self) -> None:
        outputs = geography_builder.expected()
        self.assertIsNotNone(outputs.trees)
        self.assertEqual(outputs.metrics.forbidden_tree_cells, 0)
        self.assertEqual(outputs.metrics.terrain_changes_outside_scope, 0)
        self.assertEqual(outputs.metrics.tree_changes_outside_scope, 0)
        self.assertEqual(geography_builder.coverage_issues(outputs), [])

    def test_state_partitions_are_exact_and_lossless(self) -> None:
        actual = {state_id: provinces(state_text(state_id)) for state_id in EXPECTED_PROVINCES}
        self.assertEqual(actual, EXPECTED_PROVINCES)
        flattened = [province for values in actual.values() for province in values]
        self.assertEqual(len(flattened), len(set(flattened)))
        self.assertEqual(len(flattened), 138)

    def test_exact_ivn_and_iia_victory_points(self) -> None:
        for state_id, expected in EXPECTED_VPS.items():
            with self.subTest(state=state_id):
                self.assertEqual(victory_points(state_text(state_id)), expected)

    def test_split_preserves_old_march_and_island_totals(self) -> None:
        expected = {
            "population": 4_360_000,
            "industrial_complex": 7,
            "arms_factory": 4,
            "air_base": 3,
            "local_supplies": 12.0,
            "steel": 24,
        }
        sources = [state_text(state_id) for state_id in EXPECTED_PROVINCES]
        actual = {
            "population": sum(int(re.search(r"\bmanpower\s*=\s*(\d+)", source).group(1)) for source in sources),
            "industrial_complex": sum(int(value) for source in sources for value in re.findall(r"\bindustrial_complex\s*=\s*(\d+)", source)),
            "arms_factory": sum(int(value) for source in sources for value in re.findall(r"\barms_factory\s*=\s*(\d+)", source)),
            "air_base": sum(int(value) for source in sources for value in re.findall(r"\bair_base\s*=\s*(\d+)", source)),
            "local_supplies": sum(float(re.search(r"\blocal_supplies\s*=\s*([\d.]+)", source).group(1)) for source in sources),
            "steel": sum(int(value) for source in sources for value in re.findall(r"\bsteel\s*=\s*(\d+)", source)),
        }
        self.assertEqual(actual, expected)

    def test_iia_is_ivn_subject_with_exact_autonomy(self) -> None:
        ivn = (ROOT / "history/countries/IVN - IvanLand.txt").read_text(encoding="utf-8-sig")
        autonomy = (ROOT / "common/autonomous_states/ADISCORD_island_administration.txt").read_text(encoding="utf-8-sig")
        self.assertRegex(ivn, r"set_autonomy\s*=\s*\{[^}]*target\s*=\s*IIA[^}]*autonomy_state\s*=\s*autonomy_island_administration[^}]*freedom_level\s*=\s*0\.00")
        self.assertIn("id = autonomy_island_administration", autonomy)
        self.assertIn("use_overlord_color = yes", autonomy)
        self.assertIn("default = no", autonomy)

    def test_iia_country_leader_uses_dedicated_portrait_and_oob_exists(self) -> None:
        country = (ROOT / "history/countries/IIA - Itoran Island Administration.txt").read_text(encoding="utf-8-sig")
        character = (ROOT / "common/characters/IIA.txt").read_text(encoding="utf-8-sig")
        portraits = (ROOT / "interface/ADISCORD_leader_portraits.gfx").read_text(encoding="utf-8-sig")
        localisation = (ROOT / "localisation/russian/nsb_characters_l_russian.yml").read_text(encoding="utf-8-sig")
        portrait = ROOT / "gfx/leaders/IIA/portrait_IIA_Artem_Severin.png"
        oob = (ROOT / "history/units/IIA.txt").read_text(encoding="utf-8-sig")
        self.assertIn("capital = 693", country)
        self.assertIn('oob = "IIA"', country)
        self.assertIn("recruit_character = IIA_Artem_Severin", country)
        self.assertIn("GFX_portrait_IIA_Artem_Severin", character)
        self.assertIn('name = "GFX_portrait_IIA_Artem_Severin"', portraits)
        self.assertIn('texturefile = "gfx/leaders/IIA/portrait_IIA_Artem_Severin.png"', portraits)
        self.assertIn('IIA_Artem_Severin: "Артём Северин"', localisation)
        self.assertTrue(portrait.is_file())
        self.assertEqual(portrait.read_bytes()[16:24], bytes.fromhex("0000009c000000d2"))
        self.assertEqual(len(re.findall(r"\bdivision\s*=\s*\{", oob)), 1)
        self.assertIn("location = 579", oob)

    def test_ivn_keeps_sixteen_divisions_outside_iia(self) -> None:
        oob = (ROOT / "history/units/IVN.txt").read_text(encoding="utf-8-sig")
        self.assertEqual(len(re.findall(r"\bdivision\s*=\s*\{", oob)), 16)
        self.assertNotIn("location = 579", oob)

    def test_split_states_have_valid_map_building_anchors(self) -> None:
        affected = {25, 128, 693, 694, 695, 696, 697, 698}
        issues = [
            issue for issue in map_buildings.validate(ROOT)
            if any(f"state {state_id} " in issue for state_id in affected)
        ]
        self.assertEqual(issues, [])

    def test_autonomy_icon_is_exact_runtime_asset(self) -> None:
        icon_path = ROOT / "gfx/interface/autonomy/autonomy_island_administration_icon.png"
        with Image.open(icon_path) as icon:
            self.assertEqual(icon.size, (35, 36))
            self.assertEqual(icon.mode, "RGBA")
            self.assertLess(icon.getextrema()[3][0], 255)
        gfx = (ROOT / "interface/ADISCORD_autonomy_icons.gfx").read_text(encoding="utf-8-sig")
        self.assertIn("GFX_autonomy_island_administration_icon", gfx)
        self.assertIn("autonomy_island_administration_icon.png", gfx)
        for directory in ("gfx/flags", "gfx/flags/medium", "gfx/flags/small"):
            self.assertEqual(
                (ROOT / directory / "IIA.tga").read_bytes(),
                (ROOT / directory / "IVN.tga").read_bytes(),
            )


if __name__ == "__main__":
    unittest.main()
