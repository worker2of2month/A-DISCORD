from __future__ import annotations

from array import array
from io import BytesIO
import unittest

from PIL import Image

from tools.builders import build_adiscord_province_layer_alignment as builder


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

    def test_low_mountain_height_is_raised_without_touching_boundary(self) -> None:
        width = height = 7
        indices = [y * width + x for y in range(1, 6) for x in range(1, 6)]
        heights = bytearray([110] * (width * height))
        before = bytes(heights)
        changed = builder.align_province_height(
            heights, width, height, indices, desired_type="mountain", province_id=16679
        )
        boundary = {
            y * width + x
            for y in range(1, 6)
            for x in range(1, 6)
            if x in (1, 5) or y in (1, 5)
        }
        self.assertTrue(changed)
        self.assertTrue(all(heights[index] == before[index] for index in boundary))
        self.assertGreater(heights[3 * width + 3], 145)

    def test_extreme_plain_height_is_flattened_and_idempotent(self) -> None:
        width = height = 7
        indices = [y * width + x for y in range(1, 6) for x in range(1, 6)]
        heights = bytearray([110] * (width * height))
        for y in range(1, 6):
            for x in range(1, 6):
                heights[y * width + x] = 170 if (x + y) % 2 else 140
        builder.align_province_height(
            heights, width, height, indices, desired_type="plains", province_id=16688
        )
        interior = [heights[y * width + x] for y in range(2, 5) for x in range(2, 5)]
        self.assertLess(max(interior) - min(interior), 25)
        snapshot = bytes(heights)
        second = builder.align_province_height(
            heights, width, height, indices, desired_type="plains", province_id=16688
        )
        self.assertEqual(bytes(heights), snapshot)
        self.assertFalse(second)

    def test_world_normal_patch_changes_only_affected_cells_and_neighbours(self) -> None:
        heightmap = Image.new("L", (8, 8), 110)
        pixels = list(heightmap.get_flattened_data())
        pixels[4 * 8 + 4] = 160
        heightmap.putdata(pixels)
        source = Image.new("RGB", (4, 4), (127, 127, 253))
        result, changed = builder.render_world_normal_patch(
            heightmap, source, {4 * 8 + 4}
        )
        self.assertTrue(changed)
        self.assertTrue(changed <= {6, 9, 10, 11, 14})
        self.assertEqual(result.getpixel((0, 0)), (127, 127, 253))

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
