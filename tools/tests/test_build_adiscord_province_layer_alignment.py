from __future__ import annotations

import json
import unittest
from pathlib import Path

from PIL import Image

from tools.builders import build_adiscord_map_relief_readability as relief
from tools.builders import build_adiscord_province_layer_alignment as builder


ROOT = Path(__file__).resolve().parents[2]


def _registry_entry() -> dict:
    payload = json.loads(
        (ROOT / "tools" / "data" / "generated_output_owners.json").read_text(
            encoding="utf-8"
        )
    )
    for entry in payload["families"]:
        if entry["id"] == "province_layer_alignment":
            return entry
    raise AssertionError("province_layer_alignment is not registered as an owner")


def _declared_outputs() -> list[str]:
    return _registry_entry()["output_globs"]


def _declared_sources() -> list[str]:
    return _registry_entry()["source_inputs"]


PALETTE = {
    0: "plains",
    3: "desert",
    4: "forest",
    9: "marsh",
    13: "urban",
    15: "ocean",
    17: "hills",
    20: "mountain",
}


def paletted(values: list[int], size: tuple[int, int]) -> Image.Image:
    image = Image.new("P", size)
    image.putpalette([component for index in range(256) for component in (index, index, index)])
    image.putdata(values)
    return image


class ProvinceLayerAlignmentTests(unittest.TestCase):
    def test_scope_contract_covers_uploaded_province_delta(self) -> None:
        self.assertEqual(builder.NEW_PROVINCE_IDS, frozenset(range(16654, 16707)))
        self.assertEqual(
            builder.TERRAIN_CHANGED_PROVINCE_IDS,
            frozenset({
                579, 5245, 5636, 5772, 6905, 6928, 7678, 8877, 9664,
                11209, 11392, 11443, 12189, 12250, 12296, 12955, 16563,
                16611, 16612,
            }),
        )

    def test_nonurban_alignment_clears_stale_urban_and_reaches_target_share(self) -> None:
        width = height = 5
        terrain = bytearray([
            15, 15, 15, 15, 15,
            15, 13, 0, 0, 15,
            15, 0, 17, 0, 15,
            15, 0, 0, 4, 15,
            15, 15, 15, 15, 15,
        ])
        heights = bytes([100] * (width * height))
        indices = [6, 7, 8, 11, 12, 13, 16, 17, 18]

        result = builder.align_province_terrain(
            terrain,
            heights,
            width,
            height,
            indices,
            desired_type="forest",
            province_id=16659,
            palette_types=PALETTE,
            target_share=0.70,
        )

        self.assertNotIn(13, [terrain[index] for index in indices])
        forest = sum(PALETTE.get(terrain[index]) == "forest" for index in indices)
        self.assertGreaterEqual(forest / len(indices), 0.70)
        self.assertEqual(result.after_counts["forest"], forest)
        self.assertTrue(result.changed_indices <= set(indices))

    def test_urban_alignment_paints_the_complete_province(self) -> None:
        terrain = bytearray([0, 4, 17, 3])
        result = builder.align_province_terrain(
            terrain,
            bytes([100, 100, 100, 100]),
            2,
            2,
            [0, 1, 2, 3],
            desired_type="urban",
            province_id=16689,
            palette_types=PALETTE,
            target_share=1.0,
        )
        self.assertEqual(terrain, bytearray([13, 13, 13, 13]))
        self.assertEqual(result.changed_indices, {0, 1, 2, 3})

    def test_alignment_is_idempotent(self) -> None:
        terrain = bytearray([0, 0, 17, 4, 4, 4, 4, 4, 4])
        heights = bytes([100] * 9)
        first = builder.align_province_terrain(
            terrain, heights, 3, 3, list(range(9)), "forest", 16659, PALETTE, 0.70
        )
        snapshot = bytes(terrain)
        second = builder.align_province_terrain(
            terrain, heights, 3, 3, list(range(9)), "forest", 16659, PALETTE, 0.70
        )
        self.assertEqual(bytes(terrain), snapshot)
        self.assertFalse(second.changed_indices)
        self.assertTrue(first.changed_indices)

    def test_relief_is_not_owned_here(self) -> None:
        """This pass must never write relief again.

        Every part of its old per-province height and normal-map pass was a defect
        generator - a guaranteed 20 unit wall at each province rim, interiors that
        saturated into a tabletop, and an axis-aligned sinusoid that printed a
        cross-hatch mesh across the whole map.  Relief now belongs to
        ``build_adiscord_map_relief_readability``, which sculpts continuously
        across province borders, and these assertions keep it from creeping back.
        """

        for removed in ("align_province_height", "render_world_normal_patch"):
            self.assertFalse(hasattr(builder, removed), removed)
        self.assertNotIn("map/heightmap.bmp", _declared_outputs())
        self.assertNotIn("map/world_normal.bmp", _declared_outputs())
        self.assertIn("map/heightmap.bmp", _declared_sources())

    def test_urban_alignment_keeps_the_shared_river_corridor_clear(self) -> None:
        terrain = bytearray([0, 4, 17, 3])
        bank = relief.CATEGORY_PALETTE[relief.CORRIDOR_BANK_CATEGORY][0]
        result = builder.align_province_terrain(
            terrain,
            bytes([100, 100, 100, 100]),
            2,
            2,
            [0, 1, 2, 3],
            desired_type="urban",
            province_id=16698,
            palette_types=PALETTE,
            target_share=1.0,
            corridor=frozenset({1, 2}),
        )
        self.assertEqual(terrain, bytearray([13, bank, bank, 13]))
        self.assertEqual(result.changed_indices, {0, 1, 2, 3})

        snapshot = bytes(terrain)
        again = builder.align_province_terrain(
            terrain, bytes([100] * 4), 2, 2, [0, 1, 2, 3], "urban", 16698,
            PALETTE, 1.0, frozenset({1, 2}),
        )
        self.assertEqual(bytes(terrain), snapshot)
        self.assertFalse(again.changed_indices)

    def test_tree_patch_preserves_cells_outside_target_footprint(self) -> None:
        terrain = paletted([
            4, 4, 0, 0,
            4, 4, 0, 0,
            13, 13, 20, 20,
            13, 13, 20, 20,
        ], (4, 4))
        trees = paletted([28, 28, 28, 28], (2, 2))
        target = bytearray([
            1, 1, 0, 0,
            1, 1, 0, 0,
            1, 1, 0, 0,
            1, 1, 0, 0,
        ])
        result, changed = builder.render_tree_patch(
            trees, terrain, target, PALETTE
        )
        values = list(result.get_flattened_data())
        self.assertEqual(values[1], 28)
        self.assertEqual(values[3], 28)
        self.assertTrue(changed <= {0, 2})
        self.assertEqual(values[2], 0)


if __name__ == "__main__":
    unittest.main()
