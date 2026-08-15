from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
from io import BytesIO
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

    def test_render_heightmap_changes_only_island_mask(self) -> None:
        source = Image.new("L", (5, 5), 110)
        mask = bytearray(25)
        mask[2 * 5 + 2] = 1
        rendered = builder.render_heightmap(source, mask, (2, 2, 2, 2))
        changed = [
            index
            for index, (before, after) in enumerate(
                zip(source.get_flattened_data(), rendered.get_flattened_data())
            )
            if before != after
        ]
        self.assertEqual(changed, [12])

    def test_height_slope_does_not_wrap_rows(self) -> None:
        pixels = [0, 0, 100, 200, 0, 0]
        self.assertEqual(builder.height_slope(pixels, 3, 2, 2), 100)

    def test_normal_channels_follow_existing_orientation(self) -> None:
        flat = Image.new("L", (6, 6), 120)
        normal = builder.normal_from_height(
            flat,
            Image.new("RGB", (3, 3), (127, 127, 253)),
            bytearray([1] * 36),
        )
        self.assertEqual(normal.getpixel((1, 1)), (127, 127, 253))

    def test_normal_red_decreases_for_rising_east_height(self) -> None:
        height = Image.new("L", (6, 6))
        height.putdata([100 + 10 * x for y in range(6) for x in range(6)])
        normal = builder.normal_from_height(
            height,
            Image.new("RGB", (3, 3), (127, 127, 253)),
            bytearray([1] * 36),
        )
        self.assertLess(normal.getpixel((1, 1))[0], builder.NORMAL_CENTER)

    def test_normal_green_increases_for_rising_south_height(self) -> None:
        height = Image.new("L", (6, 6))
        height.putdata([100 + 10 * y for y in range(6) for x in range(6)])
        normal = builder.normal_from_height(
            height,
            Image.new("RGB", (3, 3), (127, 127, 253)),
            bytearray([1] * 36),
        )
        self.assertGreater(normal.getpixel((1, 1))[1], builder.NORMAL_CENTER)

    def test_generated_geography_is_current(self) -> None:
        self.assertEqual(builder.validate(), [])

    def test_expected_returns_named_task_2_outputs(self) -> None:
        outputs = builder.expected()
        self.assertIsInstance(outputs, builder.GeographyOutputs)
        self.assertIsNone(outputs.trees)

    def test_generated_height_and_normals_are_scoped_and_distributed(self) -> None:
        outputs = builder.expected()
        self.assertEqual((outputs.heightmap.mode, outputs.heightmap.size), ("L", (5632, 2048)))
        self.assertEqual((outputs.world_normal.mode, outputs.world_normal.size), ("RGB", (2816, 1024)))

        _lines, _newline, _bom, definition_colors, _declared = builder.definition_contract()
        with Image.open(builder.PROVINCES_PATH) as provinces_source:
            masks = builder.landscape_masks(provinces_source, definition_colors)
        with Image.open(builder.HEIGHTMAP_PATH) as height_source:
            source_height_bytes = height_source.tobytes()
        with Image.open(builder.WORLD_NORMAL_PATH) as normal_source:
            source_normal_bytes = normal_source.tobytes()

        height_bytes = outputs.heightmap.tobytes()
        island_values = [height_bytes[index] for index, included in enumerate(masks.island) if included]
        self.assertGreaterEqual(min(island_values), 97)
        self.assertLess(max(island_values), 180)
        self.assertGreaterEqual(len(set(island_values)), 45)
        self.assertGreaterEqual(sum(value >= 145 for value in island_values), 250)
        changed_height_outside_island = sum(
            before != after
            for index, (before, after) in enumerate(zip(source_height_bytes, height_bytes))
            if not masks.island[index]
        )
        self.assertEqual(changed_height_outside_island, 0)

        normal_width, normal_height = outputs.world_normal.size
        coarse_island = bytearray(normal_width * normal_height)
        for ny in range(normal_height):
            for nx in range(normal_width):
                full_x = nx * 2
                full_y = ny * 2
                full_indices = (
                    full_y * outputs.heightmap.width + full_x,
                    full_y * outputs.heightmap.width + full_x + 1,
                    (full_y + 1) * outputs.heightmap.width + full_x,
                    (full_y + 1) * outputs.heightmap.width + full_x + 1,
                )
                coarse_island[ny * normal_width + nx] = any(masks.island[index] for index in full_indices)
        feathered = bytearray(coarse_island)
        for index, included in enumerate(coarse_island):
            if not included:
                continue
            nx = index % normal_width
            ny = index // normal_width
            if nx:
                feathered[index - 1] = 1
            if nx + 1 < normal_width:
                feathered[index + 1] = 1
            if ny:
                feathered[index - normal_width] = 1
            if ny + 1 < normal_height:
                feathered[index + normal_width] = 1
        rendered_normal_bytes = outputs.world_normal.tobytes()
        changed_normal_outside_feathered_mask = sum(
            source_normal_bytes[index * 3:index * 3 + 3]
            != rendered_normal_bytes[index * 3:index * 3 + 3]
            for index, included in enumerate(feathered)
            if not included
        )
        self.assertEqual(changed_normal_outside_feathered_mask, 0)

    def test_atomic_save_bmp_replaces_target_without_leaving_temporary_file(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            target = Path(temporary_directory) / "test.bmp"
            Image.new("L", (2, 2), 10).save(target, format="BMP")
            builder.atomic_save_bmp(Image.new("L", (2, 2), 42), target)
            with Image.open(BytesIO(target.read_bytes())) as current:
                self.assertEqual(list(current.get_flattened_data()), [42] * 4)
            self.assertFalse(target.with_suffix(".bmp.tmp").exists())

    def test_every_settlement_has_a_bounded_connected_urban_footprint(self) -> None:
        outputs = builder.expected()
        self.assertEqual(set(outputs.footprints), set(builder.SETTLEMENT_PROVINCES))
        for province_id, footprint in outputs.footprints.items():
            with self.subTest(province=province_id):
                self.assertGreaterEqual(len(footprint), builder.MIN_URBAN_PIXELS)
                self.assertLessEqual(
                    len(footprint),
                    sum(outputs.counts[province_id].values()) * builder.MAX_URBAN_SHARE,
                )
                self.assertEqual(outputs.desired[province_id], "urban")

    def test_province_geometry_is_unchanged(self) -> None:
        digest = hashlib.sha256(builder.PROVINCES_PATH.read_bytes()).hexdigest().upper()
        self.assertEqual(digest, "4CE9521BD3ADB7966E951B534D9DEA31D0C995441CDE60E99DEC3A2D3A530511")


if __name__ == "__main__":
    unittest.main()
