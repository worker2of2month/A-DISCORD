from __future__ import annotations

import hashlib
import unittest

from tools.builders import build_adiscord_ivn_geography as builder


class IvanlandGeographyBuilderTests(unittest.TestCase):
    def test_landscape_scope_is_exact(self) -> None:
        self.assertEqual(builder.ISLAND_HEIGHT_STATE_IDS, frozenset({128, 693, 694}))
        self.assertEqual(
            builder.NORTHERN_LANDSCAPE_STATE_IDS,
            frozenset({127, 128, 129, 130, 131, 132, 164, 693, 694}),
        )

    def test_distance_from_edge_increases_inward(self) -> None:
        mask = bytearray([
            0, 0, 0, 0, 0,
            0, 1, 1, 1, 0,
            0, 1, 1, 1, 0,
            0, 1, 1, 1, 0,
            0, 0, 0, 0, 0,
        ])
        distances = builder.distance_from_edge(mask, 5, 5)
        self.assertEqual(distances[2 * 5 + 2], 1)
        self.assertEqual(distances[1 * 5 + 1], 0)

    def test_scalar_fields_are_bounded_and_repeatable(self) -> None:
        first = builder.island_height_value(0.52, 0.45, 8)
        self.assertEqual(first, builder.island_height_value(0.52, 0.45, 8))
        self.assertGreaterEqual(first, 97)
        self.assertLess(first, 180)
        self.assertEqual(builder.stable_unit_hash(41, 73, 19), builder.stable_unit_hash(41, 73, 19))

    def test_generated_geography_is_current(self) -> None:
        self.assertEqual(builder.validate(), [])

    def test_every_settlement_has_a_bounded_connected_urban_footprint(self) -> None:
        _terrain, _definition, desired, counts, footprints = builder.expected()
        self.assertEqual(set(footprints), set(builder.SETTLEMENT_PROVINCES))
        for province_id, footprint in footprints.items():
            with self.subTest(province=province_id):
                self.assertGreaterEqual(len(footprint), builder.MIN_URBAN_PIXELS)
                self.assertLessEqual(len(footprint), sum(counts[province_id].values()) * builder.MAX_URBAN_SHARE)
                self.assertEqual(desired[province_id], "urban")

    def test_province_geometry_is_unchanged(self) -> None:
        digest = hashlib.sha256(builder.PROVINCES_PATH.read_bytes()).hexdigest().upper()
        self.assertEqual(digest, "4CE9521BD3ADB7966E951B534D9DEA31D0C995441CDE60E99DEC3A2D3A530511")


if __name__ == "__main__":
    unittest.main()
