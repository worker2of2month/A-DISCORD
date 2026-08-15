from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Iterator
import unittest

from PIL import Image

from tools.builders import build_adiscord_ivn_geography as builder


@dataclass(frozen=True)
class LandscapeFixture:
    provinces: Image.Image
    definition_colors: dict[int, tuple[int, int, int]]
    province_by_state: dict[int, int]


@dataclass(frozen=True)
class ConversionFailure:
    width: int = 3
    height: int = 3

    def convert(self, _mode: str) -> Image.Image:
        raise ValueError("fixture conversion failed")


class IvanlandGeographyBuilderTests(unittest.TestCase):
    @contextmanager
    def landscape_fixture(
        self,
        *,
        absent_from_bitmap: frozenset[int] = frozenset(),
        grayscale: bool = False,
    ) -> Iterator[LandscapeFixture]:
        state_ids = tuple(sorted(builder.NORTHERN_LANDSCAPE_STATE_IDS))
        province_by_state = {state_id: 9000 + index for index, state_id in enumerate(state_ids)}
        original_state_dir = builder.STATE_DIR
        with TemporaryDirectory() as temporary_directory:
            state_dir = Path(temporary_directory)
            for state_id, province_id in province_by_state.items():
                (state_dir / f"{state_id}-fixture.txt").write_text(
                    f"state = {{ id = {state_id} provinces = {{ {province_id} }} }}",
                    encoding="utf-8",
                )
            if grayscale:
                definition_colors = {
                    province_id: (index + 1, index + 1, index + 1)
                    for index, province_id in enumerate(province_by_state.values())
                }
                provinces = Image.new("L", (3, 3), 0)
            else:
                definition_colors = {
                    province_id: (index + 1, 0, 0)
                    for index, province_id in enumerate(province_by_state.values())
                }
                provinces = Image.new("RGB", (3, 3), (0, 0, 0))
            pixels = list(provinces.get_flattened_data())
            for index, state_id in enumerate(state_ids):
                if state_id not in absent_from_bitmap:
                    color = definition_colors[province_by_state[state_id]]
                    pixels[index] = color[0] if grayscale else color
            provinces.putdata(pixels)
            builder.STATE_DIR = state_dir
            try:
                yield LandscapeFixture(provinces, definition_colors, province_by_state)
            finally:
                builder.STATE_DIR = original_state_dir

    def test_province_ids_for_states_reads_fixture_manifests(self) -> None:
        with self.landscape_fixture() as fixture:
            self.assertEqual(
                builder.province_ids_for_states(builder.NORTHERN_LANDSCAPE_STATE_IDS),
                frozenset(fixture.province_by_state.values()),
            )

    def test_landscape_masks_rgb_scope_and_inclusive_bbox(self) -> None:
        with self.landscape_fixture() as fixture:
            masks = builder.landscape_masks(fixture.provinces, fixture.definition_colors)
        self.assertEqual(masks.north, bytearray([1] * 9))
        self.assertEqual(
            [index for index, value in enumerate(masks.island) if value],
            [1, 7, 8],
        )
        self.assertEqual(masks.island_bbox, (1, 0, 2, 2))

    def test_landscape_masks_accepts_grayscale_fixture(self) -> None:
        with self.landscape_fixture(grayscale=True) as fixture:
            masks = builder.landscape_masks(fixture.provinces, fixture.definition_colors)
        self.assertEqual(masks.north, bytearray([1] * 9))
        self.assertEqual(masks.island_bbox, (1, 0, 2, 2))

    def test_landscape_masks_rejects_definition_missing_state_province(self) -> None:
        with self.landscape_fixture() as fixture:
            definition_colors = dict(fixture.definition_colors)
            del definition_colors[fixture.province_by_state[127]]
            with self.assertRaisesRegex(RuntimeError, "missing northern landscape provinces"):
                builder.landscape_masks(fixture.provinces, definition_colors)

    def test_landscape_masks_rejects_vanished_non_island_province(self) -> None:
        with self.landscape_fixture(absent_from_bitmap=frozenset({127})) as fixture:
            with self.assertRaisesRegex(RuntimeError, "missing northern landscape bitmap provinces"):
                builder.landscape_masks(fixture.provinces, fixture.definition_colors)

    def test_landscape_masks_rejects_empty_island(self) -> None:
        with self.landscape_fixture(absent_from_bitmap=builder.ISLAND_HEIGHT_STATE_IDS) as fixture:
            with self.assertRaisesRegex(RuntimeError, "no island landscape pixels"):
                builder.landscape_masks(fixture.provinces, fixture.definition_colors)

    def test_landscape_masks_rejects_rgb_conversion_failure(self) -> None:
        with self.landscape_fixture() as fixture:
            with self.assertRaisesRegex(RuntimeError, "cannot convert to RGB"):
                builder.landscape_masks(ConversionFailure(), fixture.definition_colors)

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
