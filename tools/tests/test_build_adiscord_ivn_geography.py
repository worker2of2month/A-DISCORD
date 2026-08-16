from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
from io import BytesIO
from math import floor, sqrt
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Iterator
import unittest

from PIL import Image

from tools.builders import build_adiscord_ivn_geography as builder


HEIGHT_OUTSIDE_ISLAND_SHA256 = "4BF5E6E4DC65377E0979EE4BA6E5240A603947FCA7E2CE82453BCB36CC668D93"
NORMAL_OUTSIDE_FEATHER_SHA256 = "8D39567B4CC990FC1A34AAFD5FE9023301454582C5018C386851EE8430C01076"


def island_height_slopes(
    pixels: bytes | bytearray,
    width: int,
    height: int,
    island_mask: bytearray,
) -> dict[int, int]:
    slopes: dict[int, int] = {}
    for index, included in enumerate(island_mask):
        if not included:
            continue
        x = index % width
        y = index // width
        neighbours = (
            index - 1 if x else None,
            index + 1 if x + 1 < width else None,
            index - width if y else None,
            index + width if y + 1 < height else None,
        )
        slopes[index] = max(
            (
                abs(pixels[index] - pixels[neighbour])
                for neighbour in neighbours
                if neighbour is not None and island_mask[neighbour]
            ),
            default=0,
        )
    return slopes


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

    def test_tree_probabilities_are_ordered(self) -> None:
        self.assertEqual(builder.tree_probability("mountain"), 0.0)
        self.assertEqual(builder.tree_probability("urban"), 0.0)
        self.assertEqual(builder.tree_probability("ocean"), 0.0)
        self.assertLess(builder.tree_probability("hills"), builder.tree_probability("plains"))
        self.assertLess(builder.tree_probability("plains"), builder.tree_probability("forest"))

    def test_tree_probability_values(self) -> None:
        self.assertEqual(builder.tree_probability("forest"), 0.62)
        self.assertEqual(builder.tree_probability("plains"), 0.11)
        self.assertEqual(builder.tree_probability("hills"), 0.04)
        self.assertEqual(builder.tree_probability("marsh"), 0.08)

    def test_render_northern_terrain_uses_relief_shoulders_forests_and_preserves_specials(self) -> None:
        width = height = 6
        source = Image.new("P", (width, height), 0)
        source.putpalette([value for index in range(256) for value in (index, index, index)])
        source_pixels = [0] * (width * height)
        urban = 5 * width
        marsh = 5 * width + 5
        source_pixels[urban] = 13
        source_pixels[marsh] = 9
        source.putdata(source_pixels)

        heights = [125] * (width * height)
        summit = 2 * width + 2
        heights[summit] = 160
        heightmap = Image.new("L", (width, height))
        heightmap.putdata(heights)
        north = bytearray([1] * (width * height))
        island = bytearray([1] * (width * height))
        island[marsh] = 0
        state_by_pixel = [128] * (width * height)
        state_by_pixel[marsh] = 164

        rendered = builder.render_northern_terrain(
            source,
            heightmap,
            north,
            island,
            state_by_pixel,
            {},
        )
        pixels = list(rendered.get_flattened_data())
        self.assertEqual(pixels[summit], 20)
        self.assertEqual(pixels[urban], 13)
        self.assertEqual(pixels[marsh], 9)
        self.assertIn(17, pixels)
        self.assertEqual(pixels.count(4), 9)

    def test_generated_mountains_have_connected_hill_shoulders_and_no_interior_plain_edge(self) -> None:
        width = height = 9
        source = Image.new("P", (width, height), 0)
        source.putpalette([value for index in range(256) for value in (index, index, index)])
        heightmap = Image.new("L", (width, height), 125)
        summit = 4 * width + 4
        heights = [125] * (width * height)
        heights[summit] = 160
        heightmap.putdata(heights)
        north = bytearray([1] * (width * height))
        rendered = builder.render_northern_terrain(
            source,
            heightmap,
            north,
            bytearray(north),
            [128] * (width * height),
            {},
        )
        pixels = list(rendered.get_flattened_data())
        mountains = {index for index, value in enumerate(pixels) if value == 20}
        shoulders = {index for index, value in enumerate(pixels) if value == 17}
        self.assertTrue(mountains)
        self.assertTrue(shoulders)

        def neighbours(index: int) -> set[int]:
            x = index % width
            y = index // width
            return {
                (y + dy) * width + x + dx
                for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1))
                if 0 <= x + dx < width and 0 <= y + dy < height
            }

        for index in mountains:
            for neighbour in neighbours(index):
                self.assertIn(pixels[neighbour], (17, 20))

        connected = {next(iter(shoulders))}
        frontier = list(connected)
        while frontier:
            index = frontier.pop()
            for neighbour in neighbours(index) & shoulders - connected:
                connected.add(neighbour)
                frontier.append(neighbour)
        self.assertEqual(connected, shoulders)

    def test_compact_footprint_is_deterministic_connected_and_organic(self) -> None:
        width = 15
        province = list(range(width * 10))
        first = builder.compact_footprint(province, width, 4242)
        second = builder.compact_footprint(province, width, 4242)
        self.assertEqual(first, second)
        self.assertTrue(first <= set(province))
        self.assertGreaterEqual(len(first), builder.MIN_URBAN_PIXELS)
        self.assertLessEqual(len(first), floor(len(province) * builder.MAX_URBAN_SHARE))

        connected = {next(iter(first))}
        frontier = list(connected)
        while frontier:
            index = frontier.pop()
            x = index % width
            neighbours = {
                index - 1 if x else -1,
                index + 1 if x + 1 < width else -1,
                index - width,
                index + width,
            }
            for neighbour in neighbours & first - connected:
                connected.add(neighbour)
                frontier.append(neighbour)
        self.assertEqual(connected, first)

        xs = [index % width for index in first]
        ys = [index // width for index in first]
        bounding_area = (max(xs) - min(xs) + 1) * (max(ys) - min(ys) + 1)
        self.assertNotEqual(len(first), bounding_area)
        maximum_run = floor(round(sqrt(len(first))) / 2)
        self.assertLessEqual(builder.straight_boundary_run(first, width), maximum_run)

    def test_tree_cell_sampling_uses_full_rectangles_strict_majority_and_priority(self) -> None:
        width = height = 8
        terrain = Image.new("P", (width, height), 0)
        terrain.putpalette([value for index in range(256) for value in (index, index, index)])
        terrain_pixels = [0] * (width * height)
        state_by_pixel = [0] * (width * height)

        cells = {
            (0, 0): [(x, y) for y in range(4) for x in range(4)],
            (1, 0): [(x, y) for y in range(4) for x in range(4, 8)],
            (0, 1): [(x, y) for y in range(4, 8) for x in range(4)],
            (1, 1): [(x, y) for y in range(4, 8) for x in range(4, 8)],
        }
        for offset, (x, y) in enumerate(cells[(0, 0)]):
            state_by_pixel[y * width + x] = 128 if offset >= 7 else 0
            terrain_pixels[y * width + x] = 4 if offset % 2 == 0 else 0
        for offset, (x, y) in enumerate(cells[(1, 0)]):
            state_by_pixel[y * width + x] = 129 if offset >= 8 else 0
            terrain_pixels[y * width + x] = 4
        for offset, (x, y) in enumerate(cells[(0, 1)]):
            state_by_pixel[y * width + x] = 130 if offset >= 7 else 0
            terrain_pixels[y * width + x] = 15
        for offset, (x, y) in enumerate(cells[(1, 1)]):
            state_by_pixel[y * width + x] = 131 if offset >= 7 else 0
            terrain_pixels[y * width + x] = 13 if offset < 9 else 0
        terrain.putdata(terrain_pixels)
        palette = {0: "plains", 4: "forest", 13: "urban", 15: "ocean"}

        forest = builder.tree_cell_sample(0, 0, 2, 2, terrain, state_by_pixel, palette)
        tied_scope = builder.tree_cell_sample(1, 0, 2, 2, terrain, state_by_pixel, palette)
        water = builder.tree_cell_sample(0, 1, 2, 2, terrain, state_by_pixel, palette)
        urban = builder.tree_cell_sample(1, 1, 2, 2, terrain, state_by_pixel, palette)
        self.assertEqual((forest.state_id, forest.terrain_type), (128, "forest"))
        self.assertIsNone(tied_scope.state_id)
        self.assertEqual(water.terrain_type, "ocean")
        self.assertEqual(urban.terrain_type, "urban")

        tree_source = Image.new("P", (2, 2))
        tree_source.putpalette([value for index in range(256) for value in (index, 0, 255 - index)])
        tree_source.putdata([1, 2, 3, 4])
        rendered = builder.render_trees(tree_source, terrain, state_by_pixel, palette)
        self.assertEqual(list(rendered.get_flattened_data()), [6, 2, 0, 0])
        self.assertEqual(rendered.getpalette(), tree_source.getpalette())

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
        pixels = [0, 0, 0, 200, 0, 0]
        self.assertEqual(builder.height_slope(pixels, 3, 2, 2), 0)

    def test_island_slope_gate_ignores_coastline_to_water(self) -> None:
        mask = bytearray([
            0, 0, 0, 0, 0,
            0, 1, 1, 1, 0,
            0, 1, 1, 1, 0,
            0, 1, 1, 1, 0,
            0, 0, 0, 0, 0,
        ])
        pixels = bytearray(100 if included else 0 for included in mask)
        self.assertEqual(set(island_height_slopes(pixels, 5, 5, mask).values()), {0})

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

    def test_expected_returns_named_task_3_outputs(self) -> None:
        outputs = builder.expected()
        self.assertIsInstance(outputs, builder.GeographyOutputs)
        self.assertIsNotNone(outputs.trees)
        self.assertEqual((outputs.trees.mode, outputs.trees.size), ("P", (1650, 600)))

    def test_generated_forest_and_tree_coverage_meets_exact_contract(self) -> None:
        metrics = builder.expected().metrics
        self.assertGreaterEqual(metrics.island_forest_share, 0.25)
        self.assertLessEqual(metrics.island_forest_share, 0.30)
        self.assertEqual(
            set(metrics.mainland_forest_shares),
            set(builder.MAINLAND_FOREST_STATE_IDS),
        )
        for state_id, share in metrics.mainland_forest_shares.items():
            with self.subTest(state=state_id):
                self.assertGreaterEqual(share, 0.20)
                self.assertLessEqual(share, 0.25)
        occupancy = metrics.tree_occupancy
        self.assertGreaterEqual(occupancy["forest"], 0.50)
        self.assertLessEqual(occupancy["forest"], 0.72)
        self.assertGreaterEqual(occupancy["plains"], 0.06)
        self.assertLessEqual(occupancy["plains"], 0.16)
        self.assertGreaterEqual(occupancy["hills"], 0.01)
        self.assertLessEqual(occupancy["hills"], 0.07)
        self.assertLess(occupancy["hills"], occupancy["plains"])
        self.assertLessEqual(occupancy["hills"], occupancy["forest"] / 5)
        self.assertEqual(metrics.forbidden_tree_cells, 0)
        self.assertEqual(metrics.terrain_changes_outside_scope, 0)
        self.assertEqual(metrics.tree_changes_outside_scope, 0)

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

    def test_generated_height_has_downstream_terrain_eligibility(self) -> None:
        outputs = builder.expected()
        _lines, _newline, _bom, definition_colors, _declared = builder.definition_contract()
        with Image.open(builder.PROVINCES_PATH) as provinces_source:
            masks = builder.landscape_masks(provinces_source, definition_colors)
        height_bytes = outputs.heightmap.tobytes()
        island_indices = [index for index, included in enumerate(masks.island) if included]
        island_values = [height_bytes[index] for index in island_indices]
        slopes = list(
            island_height_slopes(
                height_bytes,
                outputs.heightmap.width,
                outputs.heightmap.height,
                masks.island,
            ).values()
        )
        self.assertGreaterEqual(max(slopes), 12)
        self.assertGreaterEqual(sum(slope >= 8 for slope in slopes), 250)
        self.assertGreaterEqual(sum(slope >= 12 for slope in slopes), 40)
        self.assertGreaterEqual(sum(value >= 158 for value in island_values), 150)
        self.assertLess(max(island_values), 180)

    def test_steep_height_cells_form_coherent_ridge_shoulders(self) -> None:
        outputs = builder.expected()
        _lines, _newline, _bom, definition_colors, _declared = builder.definition_contract()
        with Image.open(builder.PROVINCES_PATH) as provinces_source:
            masks = builder.landscape_masks(provinces_source, definition_colors)
        height_bytes = outputs.heightmap.tobytes()
        width = outputs.heightmap.width
        height = outputs.heightmap.height
        slopes = island_height_slopes(height_bytes, width, height, masks.island)
        steep = {index for index, slope in slopes.items() if slope >= 12}
        shoulders = {index for index, slope in slopes.items() if slope >= 8}
        self.assertGreaterEqual(len(steep), 40)
        for index in steep:
            x = index % width
            y = index // width
            neighbours = {
                (y + dy) * width + x + dx
                for dy in (-1, 0, 1)
                for dx in (-1, 0, 1)
                if (
                    (dx or dy)
                    and 0 <= x + dx < width
                    and 0 <= y + dy < height
                    and masks.island[(y + dy) * width + x + dx]
                )
            }
            self.assertTrue(neighbours & shoulders, f"steep height pixel {index} is an isolated spike")

    def test_generated_maps_preserve_stable_outside_scope_streams(self) -> None:
        _lines, _newline, _bom, definition_colors, _declared = builder.definition_contract()
        with Image.open(builder.PROVINCES_PATH) as provinces_source:
            masks = builder.landscape_masks(provinces_source, definition_colors)
        with Image.open(builder.HEIGHTMAP_PATH) as height_source:
            height_bytes = height_source.tobytes()
            height_width = height_source.width
            height_height = height_source.height
        height_outside = bytes(
            value for index, value in enumerate(height_bytes) if not masks.island[index]
        )
        self.assertEqual(
            hashlib.sha256(height_outside).hexdigest().upper(),
            HEIGHT_OUTSIDE_ISLAND_SHA256,
        )

        normal_width = height_width // 2
        normal_height = height_height // 2
        coarse_island = bytearray(normal_width * normal_height)
        for ny in range(normal_height):
            top = ny * 2 * height_width
            bottom = top + height_width
            for nx in range(normal_width):
                left = nx * 2
                coarse_island[ny * normal_width + nx] = any(
                    masks.island[index]
                    for index in (top + left, top + left + 1, bottom + left, bottom + left + 1)
                )
        feathered = bytearray(coarse_island)
        for index, included in enumerate(coarse_island):
            if not included:
                continue
            nx = index % normal_width
            ny = index // normal_width
            for neighbour in (
                index - 1 if nx else None,
                index + 1 if nx + 1 < normal_width else None,
                index - normal_width if ny else None,
                index + normal_width if ny + 1 < normal_height else None,
            ):
                if neighbour is not None:
                    feathered[neighbour] = 1
        with Image.open(builder.WORLD_NORMAL_PATH) as normal_source:
            normal_bytes = normal_source.tobytes()
        normal_outside = bytearray()
        for index, included in enumerate(feathered):
            if not included:
                normal_outside.extend(normal_bytes[index * 3:index * 3 + 3])
        self.assertEqual(
            hashlib.sha256(normal_outside).hexdigest().upper(),
            NORMAL_OUTSIDE_FEATHER_SHA256,
        )

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
