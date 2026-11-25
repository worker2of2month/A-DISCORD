from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
import json
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Iterator
import unittest

import numpy as np
from PIL import Image
from scipy.ndimage import binary_dilation, distance_transform_edt, label

from tools.builders import build_adiscord_ivn_geography as builder
from tools.builders import build_adiscord_terrain_snow as terrain_builder
from tools.lib import coastal_clearance as clearance


HEIGHT_OUTSIDE_ISLAND_SHA256 = (
    "3E54C54318E0F7E60B4D16DBF69D3B95C5E3A0531039D4396017DC8DEA99772D"
)
NORMAL_OUTSIDE_FEATHER_SHA256 = (
    "3E4AC178A9E07613AD7F16F2A5B77F590929844C73A76A34B33A0EA71E994518"
)


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
        province_by_state = {
            state_id: 9000 + index for index, state_id in enumerate(state_ids)
        }
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
                provinces = Image.new("L", (6, 2), 0)
            else:
                definition_colors = {
                    province_id: (index + 1, 0, 0)
                    for index, province_id in enumerate(province_by_state.values())
                }
                provinces = Image.new("RGB", (6, 2), (0, 0, 0))
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
            masks = builder.landscape_masks(
                fixture.provinces, fixture.definition_colors
            )
        self.assertEqual(masks.north, bytearray([1] * 11 + [0]))
        self.assertEqual(
            [index for index, value in enumerate(masks.island) if value],
            [1, 7, 8, 10],
        )
        self.assertEqual(masks.island_bbox, (1, 0, 4, 1))

    def test_landscape_masks_accepts_grayscale_fixture(self) -> None:
        with self.landscape_fixture(grayscale=True) as fixture:
            masks = builder.landscape_masks(
                fixture.provinces, fixture.definition_colors
            )
        self.assertEqual(masks.north, bytearray([1] * 11 + [0]))
        self.assertEqual(masks.island_bbox, (1, 0, 4, 1))

    def test_landscape_masks_rejects_definition_missing_state_province(self) -> None:
        with self.landscape_fixture() as fixture:
            definition_colors = dict(fixture.definition_colors)
            del definition_colors[fixture.province_by_state[127]]
            with self.assertRaisesRegex(
                RuntimeError, "missing northern landscape provinces"
            ):
                builder.landscape_masks(fixture.provinces, definition_colors)

    def test_landscape_masks_rejects_vanished_non_island_province(self) -> None:
        with self.landscape_fixture(absent_from_bitmap=frozenset({127})) as fixture:
            with self.assertRaisesRegex(
                RuntimeError, "missing northern landscape bitmap provinces"
            ):
                builder.landscape_masks(fixture.provinces, fixture.definition_colors)

    def test_landscape_masks_rejects_empty_island(self) -> None:
        with self.landscape_fixture(
            absent_from_bitmap=builder.ISLAND_HEIGHT_STATE_IDS
        ) as fixture:
            with self.assertRaisesRegex(RuntimeError, "no island landscape pixels"):
                builder.landscape_masks(fixture.provinces, fixture.definition_colors)

    def test_landscape_masks_rejects_rgb_conversion_failure(self) -> None:
        with self.landscape_fixture() as fixture:
            with self.assertRaisesRegex(RuntimeError, "cannot convert to RGB"):
                builder.landscape_masks(ConversionFailure(), fixture.definition_colors)

    def test_landscape_scope_is_exact(self) -> None:
        self.assertEqual(builder.ISLAND_HEIGHT_STATE_IDS, frozenset({128, 693, 694, 739}))
        self.assertEqual(
            builder.NORTHERN_LANDSCAPE_STATE_IDS,
            frozenset({127, 128, 129, 130, 131, 132, 164, 693, 694, 715, 739}),
        )

    def test_distance_from_edge_increases_inward(self) -> None:
        mask = bytearray(
            [
                0,
                0,
                0,
                0,
                0,
                0,
                1,
                1,
                1,
                0,
                0,
                1,
                1,
                1,
                0,
                0,
                1,
                1,
                1,
                0,
                0,
                0,
                0,
                0,
                0,
            ]
        )
        distances = builder.distance_from_edge(mask, 5, 5)
        self.assertEqual(distances[2 * 5 + 2], 1)
        self.assertEqual(distances[1 * 5 + 1], 0)

    def test_scalar_fields_are_bounded_and_repeatable(self) -> None:
        ys, xs = np.mgrid[100:140, 2600:2650].astype(float)
        first = builder.lattice_noise(xs, ys, 7.0, 41)
        np.testing.assert_array_equal(first, builder.lattice_noise(xs, ys, 7.0, 41))
        self.assertGreaterEqual(float(first.min()), 0.0)
        self.assertLessEqual(float(first.max()), 1.0)
        self.assertGreater(float(first.std()), 0.05)
        self.assertEqual(
            builder.stable_unit_hash(41, 73, 19), builder.stable_unit_hash(41, 73, 19)
        )

    def test_tree_probabilities_are_ordered(self) -> None:
        self.assertEqual(builder.tree_probability("mountain"), 0.0)
        self.assertEqual(builder.tree_probability("urban"), 0.0)
        self.assertEqual(builder.tree_probability("ocean"), 0.0)
        self.assertLess(
            builder.tree_probability("hills"), builder.tree_probability("plains")
        )
        self.assertLess(
            builder.tree_probability("plains"), builder.tree_probability("forest")
        )

    def test_tree_probability_values(self) -> None:
        self.assertEqual(builder.tree_probability("forest"), 0.62)
        self.assertEqual(builder.tree_probability("plains"), 0.04)
        self.assertEqual(builder.tree_probability("hills"), 0.025)
        self.assertEqual(builder.tree_probability("marsh"), 0.08)

    def test_render_northern_terrain_uses_relief_shoulders_forests_and_preserves_specials(
        self,
    ) -> None:
        width = height = 6
        source = Image.new("P", (width, height), 0)
        source.putpalette(
            [value for index in range(256) for value in (index, index, index)]
        )
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
        state_by_pixel = [127] * (width * height)
        state_by_pixel[marsh] = 164

        rendered = builder.render_northern_terrain(
            source,
            heightmap,
            north,
            state_by_pixel,
            {},
        )
        pixels = list(rendered.get_flattened_data())
        self.assertEqual(pixels[summit], 20)
        self.assertEqual(pixels[urban], 13)
        self.assertEqual(pixels[marsh], 9)
        self.assertIn(17, pixels)
        self.assertEqual(pixels.count(4), 8)

    def test_render_northern_terrain_leaves_island_forests_to_the_province_table(
        self,
    ) -> None:
        width = height = 6
        source = Image.new("P", (width, height), 0)
        source.putpalette(
            [value for index in range(256) for value in (index, index, index)]
        )
        heightmap = Image.new("L", (width, height), 110)
        rendered = builder.render_northern_terrain(
            source,
            heightmap,
            bytearray([1] * (width * height)),
            [128] * (width * height),
            {},
        )
        self.assertNotIn(builder.FOREST_PALETTE, rendered.get_flattened_data())

    def test_generated_mountains_have_connected_hill_shoulders_and_no_interior_plain_edge(
        self,
    ) -> None:
        width = height = 9
        source = Image.new("P", (width, height), 0)
        source.putpalette(
            [value for index in range(256) for value in (index, index, index)]
        )
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
            [127] * (width * height),
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

    def test_tree_cell_sampling_uses_full_rectangles_strict_majority_and_priority(
        self,
    ) -> None:
        width = height = 8
        terrain = Image.new("P", (width, height), 0)
        terrain.putpalette(
            [value for index in range(256) for value in (index, index, index)]
        )
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
        tied_scope = builder.tree_cell_sample(
            1, 0, 2, 2, terrain, state_by_pixel, palette
        )
        water = builder.tree_cell_sample(0, 1, 2, 2, terrain, state_by_pixel, palette)
        urban = builder.tree_cell_sample(1, 1, 2, 2, terrain, state_by_pixel, palette)
        self.assertEqual((forest.state_id, forest.terrain_type), (128, "forest"))
        self.assertIsNone(tied_scope.state_id)
        self.assertEqual(water.terrain_type, "ocean")
        self.assertEqual(urban.terrain_type, "urban")

        tree_source = Image.new("P", (2, 2))
        tree_source.putpalette(
            [value for index in range(256) for value in (index, 0, 255 - index)]
        )
        tree_source.putdata([1, 2, 3, 4])
        rendered = builder.render_trees(tree_source, terrain, state_by_pixel, palette)
        self.assertEqual(list(rendered.get_flattened_data()), [6, 2, 0, 0])
        self.assertEqual(rendered.getpalette(), tree_source.getpalette())

    def test_render_island_heights_follow_declared_terrain(self) -> None:
        heights = np.full((30, 40), 89, np.uint8)
        terrain = np.full(heights.shape, -1, np.int8)
        types = list(builder.ISLAND_RELIEF)
        terrain[5:25, 5:20] = types.index("plains")
        terrain[5:25, 20:35] = types.index("hills")
        rivers = np.full(heights.shape, builder.RIVER_LAND_PALETTE, np.uint8)
        bbox = (5, 5, 34, 24)
        rendered = builder.render_island_heights(heights, terrain, bbox, rivers)
        np.testing.assert_array_equal(
            rendered, builder.render_island_heights(heights, terrain, bbox, rivers)
        )
        land = terrain >= 0
        np.testing.assert_array_equal(rendered[~land], heights[~land])
        self.assertGreaterEqual(int(rendered[land].min()), builder.HEIGHT_MIN)
        plains_level, plains_relief = builder.ISLAND_RELIEF["plains"]
        plains = rendered[5:25, 5:20]
        hills = rendered[5:25, 20:35]
        # The lowland stays level up to its border with the upland.
        self.assertLessEqual(int(plains.max()), round(plains_level + plains_relief + 1))
        self.assertGreater(float(hills[4:-4, 4:-4].mean()), float(plains.mean()) + 15)
        self.assertGreater(
            float(hills[4:-4, 4:-4].std()), float(plains[4:-4, 4:-4].std())
        )

    def test_render_island_heights_put_a_town_on_the_surrounding_level(self) -> None:
        heights = np.full((30, 30), 89, np.uint8)
        types = list(builder.ISLAND_RELIEF)
        terrain = np.full(heights.shape, -1, np.int8)
        terrain[3:27, 3:27] = types.index("hills")
        terrain[12:18, 12:18] = types.index("urban")
        rivers = np.full(heights.shape, builder.RIVER_LAND_PALETTE, np.uint8)
        rendered = builder.render_island_heights(heights, terrain, (3, 3, 26, 26), rivers)
        town = rendered[12:18, 12:18].astype(float)
        hills_level, _relief = builder.ISLAND_RELIEF["hills"]
        self.assertGreater(town.mean(), hills_level - 6)
        self.assertLess(town.std(), 3.0)

    def test_render_island_heights_cut_a_valley_along_rivers(self) -> None:
        heights = np.full((30, 30), 89, np.uint8)
        hills = list(builder.ISLAND_RELIEF).index("hills")
        terrain = np.full(heights.shape, -1, np.int8)
        terrain[3:27, 3:27] = hills
        rivers = np.full(heights.shape, builder.RIVER_LAND_PALETTE, np.uint8)
        bbox = (3, 3, 26, 26)
        dry = builder.render_island_heights(heights, terrain, bbox, rivers)
        rivers[3:27, 15] = 3
        wet = builder.render_island_heights(heights, terrain, bbox, rivers)
        self.assertLess(float(wet[8:22, 15].mean()), float(dry[8:22, 15].mean()) - 8)
        self.assertGreaterEqual(int(wet[8:22, 15].min()), builder.HEIGHT_MIN)

    def test_height_slope_does_not_wrap_rows(self) -> None:
        pixels = [0, 0, 0, 200, 0, 0]
        self.assertEqual(builder.height_slope(pixels, 3, 2, 2), 0)

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
        self.assertEqual(metrics.mountain_provinces_without_foothills, ())
        occupancy = metrics.tree_occupancy
        self.assertGreaterEqual(occupancy["forest"], 0.50)
        self.assertLessEqual(occupancy["forest"], 0.72)
        self.assertGreaterEqual(occupancy["plains"], 0.02)
        self.assertLessEqual(occupancy["plains"], 0.07)
        self.assertGreaterEqual(occupancy["hills"], 0.01)
        self.assertLessEqual(occupancy["hills"], 0.05)
        self.assertLess(occupancy["hills"], occupancy["plains"])
        self.assertLessEqual(occupancy["hills"], occupancy["forest"] / 5)
        self.assertEqual(metrics.forbidden_tree_cells, 0)
        self.assertEqual(metrics.terrain_changes_outside_scope, 0)
        self.assertEqual(metrics.tree_changes_outside_scope, 0)

    def test_generated_height_and_normals_are_scoped_and_distributed(self) -> None:
        outputs = builder.expected()
        self.assertEqual(
            (outputs.heightmap.mode, outputs.heightmap.size), ("L", (5632, 2048))
        )
        self.assertEqual(
            (outputs.world_normal.mode, outputs.world_normal.size),
            ("RGB", (2816, 1024)),
        )

        _lines, _newline, _bom, definition_colors, _declared = (
            builder.definition_contract()
        )
        with Image.open(builder.PROVINCES_PATH) as provinces_source:
            masks = builder.landscape_masks(provinces_source, definition_colors)
        with Image.open(builder.HEIGHTMAP_PATH) as height_source:
            source_height_bytes = height_source.tobytes()
        with Image.open(builder.WORLD_NORMAL_PATH) as normal_source:
            source_normal_bytes = normal_source.tobytes()

        height_bytes = outputs.heightmap.tobytes()
        island_values = [
            height_bytes[index]
            for index, included in enumerate(masks.island)
            if included
        ]
        self.assertGreaterEqual(min(island_values), 97)
        self.assertLess(max(island_values), 180)
        self.assertGreaterEqual(len(set(island_values)), 35)
        changed_height_outside_island = sum(
            before != after
            for index, (before, after) in enumerate(
                zip(source_height_bytes, height_bytes)
            )
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
                coarse_island[ny * normal_width + nx] = any(
                    masks.island[index] for index in full_indices
                )
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
            source_normal_bytes[index * 3 : index * 3 + 3]
            != rendered_normal_bytes[index * 3 : index * 3 + 3]
            for index, included in enumerate(feathered)
            if not included
        )
        self.assertEqual(changed_normal_outside_feathered_mask, 0)

    def test_island_relief_follows_declared_terrain(self) -> None:
        outputs = builder.expected()
        _lines, _newline, _bom, colours, _declared = builder.definition_contract()
        with Image.open(builder.PROVINCES_PATH) as provinces:
            packed = builder.packed_rgb(np.asarray(provinces.convert("RGB")))
        heights = np.asarray(outputs.heightmap).astype(int)
        island = builder.province_mask(
            packed, colours, frozenset(builder.ISLAND_PROVINCE_TERRAIN)
        )
        coast_distance = distance_transform_edt(island)
        # Upland relief is authored per original province; Stage 2 parts
        # share it, so the spread is measured over the province and its parts.
        parents = builder.stage2_parents(builder.PROVINCE_MANIFEST)
        families: dict[int, set[int]] = {}
        for province_id in builder.ISLAND_PROVINCE_TERRAIN:
            families.setdefault(builder.stage2_root(province_id, parents), set()).add(province_id)
        means: dict[str, list[float]] = {}
        for province_id, terrain_type in builder.ISLAND_PROVINCE_TERRAIN.items():
            mask = builder.province_mask(packed, colours, frozenset({province_id}))
            values = heights[mask]
            means.setdefault(terrain_type, []).append(float(values.mean()))
            with self.subTest(province=province_id, terrain=terrain_type):
                self.assertGreaterEqual(int(values.min()), builder.HEIGHT_MIN)
                if terrain_type in builder.ISLAND_UPLAND_TYPES:
                    family = families[builder.stage2_root(province_id, parents)]
                    upland = frozenset(
                        member
                        for member in family
                        if builder.ISLAND_PROVINCE_TERRAIN[member] in builder.ISLAND_UPLAND_TYPES
                    )
                    spread = heights[builder.province_mask(packed, colours, upland)]
                    self.assertGreaterEqual(float(spread.std()), 3.5)
                elif terrain_type == "urban":
                    # A town stands at the level of the land around it.
                    ring = binary_dilation(mask, iterations=3) & ~mask & island
                    self.assertLessEqual(
                        abs(float(values.mean()) - float(heights[ring].mean())), 6.0
                    )
                    # A port slopes down to its waterfront; inland it is level.
                    inland = mask & (coast_distance > builder.ISLAND_COAST_RAMP)
                    if inland.any():
                        self.assertLessEqual(float(heights[inland].std()), 4.5)
                else:
                    self.assertLessEqual(int(values.max()), 115)
                    self.assertLessEqual(float(values.std()), 4.5)
        lowland = [*means["plains"], *means["forest"]]
        self.assertGreater(min(means["hills"]), max(lowland) + 5)
        self.assertGreater(
            sum(means["forest"]) / len(means["forest"]),
            sum(means["plains"]) / len(means["plains"]),
        )

    def test_generated_maps_preserve_stable_outside_scope_streams(self) -> None:
        _lines, _newline, _bom, definition_colors, _declared = (
            builder.definition_contract()
        )
        with Image.open(builder.PROVINCES_PATH) as provinces_source:
            masks = builder.landscape_masks(provinces_source, definition_colors)
            relief = builder.province_mask(
                builder.packed_rgb(np.asarray(provinces_source.convert("RGB"))),
                definition_colors,
                builder.relief_province_ids(builder.RELIEF_STATE_IDS),
            ).reshape(-1)
        # The generated surface covers the IIA islands and the IVN mainland.
        scope = bytes(
            np.frombuffer(bytes(masks.island), dtype=np.uint8).astype(bool) | relief
        )
        with Image.open(builder.HEIGHTMAP_PATH) as height_source:
            height_bytes = height_source.tobytes()
            height_width = height_source.width
            height_height = height_source.height
        height_outside = bytes(
            value for index, value in enumerate(height_bytes) if not scope[index]
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
                    scope[index]
                    for index in (
                        top + left,
                        top + left + 1,
                        bottom + left,
                        bottom + left + 1,
                    )
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
                normal_outside.extend(normal_bytes[index * 3 : index * 3 + 3])
        self.assertEqual(
            hashlib.sha256(normal_outside).hexdigest().upper(),
            NORMAL_OUTSIDE_FEATHER_SHA256,
        )

    def test_atomic_save_bmp_replaces_target_without_leaving_temporary_file(
        self,
    ) -> None:
        with TemporaryDirectory() as temporary_directory:
            target = Path(temporary_directory) / "test.bmp"
            Image.new("L", (2, 2), 10).save(target, format="BMP")
            builder.atomic_save_bmp(Image.new("L", (2, 2), 42), target)
            with Image.open(BytesIO(target.read_bytes())) as current:
                self.assertEqual(list(current.get_flattened_data()), [42] * 4)
            self.assertFalse(target.with_suffix(".bmp.tmp").exists())

    def test_every_settlement_is_urban_in_its_entirety(self) -> None:
        outputs = builder.expected()
        self.assertEqual(set(outputs.footprints), set(builder.SETTLEMENT_PROVINCES))
        self.assertLessEqual(
            builder.ISLAND_URBAN_PROVINCES, builder.SETTLEMENT_PROVINCES
        )
        for province_id, footprint in outputs.footprints.items():
            with self.subTest(province=province_id):
                self.assertEqual(outputs.desired[province_id], "urban")
                self.assertEqual(
                    len(footprint), sum(outputs.counts[province_id].values())
                )

    def test_island_provinces_are_painted_in_their_declared_terrain(self) -> None:
        outputs = builder.expected()
        _lines, _newline, _bom, colours, declared = builder.definition_contract()
        self.assertEqual(
            set(builder.ISLAND_PROVINCE_TERRAIN),
            builder.province_ids_for_states(builder.ISLAND_HEIGHT_STATE_IDS),
        )
        with Image.open(builder.PROVINCES_PATH) as provinces:
            province_rgb = np.asarray(provinces.convert("RGB"))
        packed = builder.packed_rgb(province_rgb)
        water = clearance.water_mask(
            province_rgb, clearance.water_colours(builder.DEFINITION_PATH)
        )
        shore = clearance.urban_blocked(water, province_rgb, builder.DEFINITION_PATH)
        terrain = np.asarray(outputs.terrain)
        for province_id, terrain_type in builder.ISLAND_PROVINCE_TERRAIN.items():
            with self.subTest(province=province_id):
                self.assertEqual(outputs.desired[province_id], terrain_type)
                self.assertEqual(declared[province_id], terrain_type)
                mask = builder.province_mask(packed, colours, frozenset({province_id}))
                expected = np.full(
                    mask.shape, builder.ISLAND_TERRAIN_PALETTES[terrain_type], np.uint8
                )
                if terrain_type == "urban":
                    expected[shore] = clearance.URBAN_FALLBACK_PALETTE
                np.testing.assert_array_equal(terrain[mask], expected[mask])

    def test_mainland_provinces_are_painted_in_one_terrain(self) -> None:
        outputs = builder.expected()
        _lines, _newline, _bom, colours, _declared = builder.definition_contract()
        with Image.open(builder.PROVINCES_PATH) as provinces:
            packed = builder.packed_rgb(np.asarray(provinces.convert("RGB")))
        terrain = np.asarray(outputs.terrain)
        types = builder.palette_types()
        # City-model mask pixels belong to the shared cities layer.
        with Image.open(terrain_builder.CITIES_PATH) as cities:
            city_mask = np.isin(
                np.asarray(cities), list(terrain_builder.CITY_PALETTE_INDICES)
            )
        for province_id in sorted(
            builder.relief_province_ids(builder.RELIEF_STATE_IDS)
            - builder.SETTLEMENT_PROVINCES
        ):
            with self.subTest(province=province_id):
                mask = builder.province_mask(packed, colours, frozenset({province_id}))
                mask &= ~city_mask
                painted = [types[int(value)] for value in terrain[mask]]
                matching = painted.count(outputs.desired[province_id])
                self.assertGreaterEqual(matching / len(painted), 0.9)

    def test_city_mask_pixels_remain_urban_inside_ivn_scope(self) -> None:
        outputs = builder.expected()
        _lines, _newline, _bom, scoped_colours, _declared = (
            builder.definition_contract()
        )
        with (
            Image.open(terrain_builder.CITIES_PATH) as cities,
            Image.open(builder.PROVINCES_PATH) as provinces,
        ):
            city_pixels = list(cities.get_flattened_data())
            province_rgb = np.asarray(provinces.convert("RGB"))
            province_bytes = province_rgb.tobytes()
        water = clearance.water_mask(
            province_rgb, clearance.water_colours(builder.DEFINITION_PATH)
        )
        shore = clearance.urban_blocked(
            water, province_rgb, builder.DEFINITION_PATH
        ).reshape(-1)
        generated = list(outputs.terrain.get_flattened_data())
        offenders = []
        for index, city_value in enumerate(city_pixels):
            colour = tuple(province_bytes[index * 3 : index * 3 + 3])
            if (
                not shore[index]
                and city_value == terrain_builder.CITY_PALETTE_INDEX
                and colour in scoped_colours.values()
                and generated[index] != builder.URBAN_PALETTE
            ):
                offenders.append(index)
        self.assertEqual(offenders, [])

    def test_reviewed_states_are_never_replanned(self) -> None:
        manifest = builder.PROVINCE_MANIFEST_PATH.read_bytes()
        geometry = builder.PROVINCE_GEOMETRY_PATH.read_bytes()
        for state_ids, settlements in (
            (builder.IIA_STATE_IDS, builder.ISLAND_CITY_SETTLEMENTS),
            (builder.IVN_STATE_IDS, frozenset()),
        ):
            with self.subTest(states=sorted(state_ids)):
                with self.assertRaisesRegex(RuntimeError, "already have reviewed"):
                    builder.plan_province_geometry(state_ids, settlements)
        # A stored Stage 2 plan is never replanned either.
        planned = json.loads(manifest.decode("utf-8"))
        planned["stage2"] = {"provinces": [{"province": 1, "parent": 2, "state": 25, "kind": "part"}]}
        with self.assertRaisesRegex(RuntimeError, "Stage 2 plan exists"):
            builder.plan_stage2(planned)
        self.assertEqual(builder.PROVINCE_MANIFEST_PATH.read_bytes(), manifest)
        self.assertEqual(builder.PROVINCE_GEOMETRY_PATH.read_bytes(), geometry)

    def test_island_port_towns_keep_a_coast(self) -> None:
        _lines, _newline, _bom, colours, declared = builder.definition_contract()
        rows = {
            int(row[0]): row
            for row in (
                line.split(";")
                for line in builder.DEFINITION_PATH.read_text(encoding="utf-8-sig").splitlines()
            )
            if row[0].isdigit()
        }
        for parent in builder.ISLAND_CITY_SETTLEMENTS:
            city = int(builder.PROVINCE_MANIFEST["cities"][str(parent)])
            with self.subTest(parent=parent, city=city):
                self.assertEqual(declared[city], "urban")
                self.assertEqual(rows[city][5], "true")

    def test_province_geometry_is_unchanged(self) -> None:
        self.assertEqual(builder.province_geometry_issues(), [])



def synthetic_manifest() -> dict:
    """A Stage 1 split of 10675 and of an island parent, then Stage 2 parts, a town and a city."""
    return {
        "schema": 1,
        "origin": [0, 0],
        "provinces": [
            {"province": 900, "parent": 10675, "state": 714, "kind": "split", "rgb": [1, 1, 1]},
            {"province": 901, "parent": 1191, "state": 693, "kind": "split", "rgb": [2, 2, 2]},
            {"province": 902, "parent": 1304, "state": 696, "kind": "split", "rgb": [3, 3, 3]},
        ],
        "cities": {"579": 18993},
        "stage2": {
            "origin": [0, 0],
            "sheet_row": 2,
            "first_id": 950,
            "provinces": [
                {"province": 950, "parent": 10675, "state": 714, "kind": "part", "rgb": [4, 4, 4]},
                {"province": 951, "parent": 900, "state": 714, "kind": "part", "rgb": [5, 5, 5]},
                {"province": 952, "parent": 901, "state": 693, "kind": "part", "rgb": [6, 6, 6]},
                {"province": 953, "parent": 952, "state": 693, "kind": "part", "rgb": [7, 7, 7]},
                {"province": 954, "parent": 6928, "state": 693, "kind": "town", "rgb": [8, 8, 8]},
                {"province": 955, "parent": 1304, "state": 696, "kind": "remainder", "rgb": [9, 9, 9]},
                {"province": 956, "parent": 955, "state": 696, "kind": "part", "rgb": [10, 10, 10]},
            ],
            "cities": {"1304": 1304},
            "towns": {"6928": 954},
        },
    }


class Stage2ManifestTests(unittest.TestCase):
    def test_tables_without_a_stage2_plan_match_the_reviewed_stage1(self) -> None:
        manifest = json.loads(builder.PROVINCE_MANIFEST_PATH.read_text(encoding="utf-8"))
        if builder.has_stage2_plan(manifest):
            self.skipTest("the manifest holds a Stage 2 plan")
        tables = builder.manifest_tables(manifest)
        stage1 = {
            int(entry["province"]): (
                "urban"
                if entry["kind"] == "city"
                else builder.ISLAND_PARENT_TERRAIN[int(entry["parent"])]
            )
            for entry in manifest["provinces"]
            if int(entry["parent"]) in builder.ISLAND_PARENT_TERRAIN
        }
        self.assertEqual(tables.island_terrain, {**builder.ISLAND_PARENT_TERRAIN, **stage1})
        self.assertEqual(
            tables.city_provinces,
            frozenset(int(city) for city in manifest["cities"].values()),
        )
        self.assertEqual(tables.relief_excluded, frozenset({8885, 9037, 10675, 11000}))
        self.assertEqual(builder.stage2_children({694, 16568}), set())
        sheet = np.zeros((5, 4, 4), np.uint8)
        layers = builder.geometry_layers(manifest, sheet)
        self.assertEqual(len(layers), 1)
        self.assertIs(layers[0][1], sheet)

    def test_plan_states_follow_the_state_files(self) -> None:
        manifest = json.loads(builder.PROVINCE_MANIFEST_PATH.read_text(encoding="utf-8"))
        plan = builder.stage2_plan(manifest)
        state_of = builder.province_state_contract(builder.SCOPED_STATE_IDS)
        entries = [*manifest["provinces"], *plan.get("provinces", []), *plan.get("settlements", [])]
        stale = [
            (entry["province"], entry["state"], state_of[int(entry["province"])])
            for entry in entries
            if state_of.get(int(entry["province"]), entry["state"]) != entry["state"]
        ]
        self.assertEqual(stale, [])

    def test_stage2_tables_resolve_through_the_root_before_stage2(self) -> None:
        tables = builder.manifest_tables(synthetic_manifest())
        # A Stage 1 split of an excluded parent stays in the relief; Stage 2 parts follow their root.
        self.assertIn(950, tables.relief_excluded)
        self.assertNotIn(900, tables.relief_excluded)
        self.assertNotIn(951, tables.relief_excluded)
        # Island parts take the terrain of their root; the town and the city are urban.
        self.assertEqual(tables.island_terrain[952], builder.ISLAND_PARENT_TERRAIN[1191])
        self.assertEqual(tables.island_terrain[953], builder.ISLAND_PARENT_TERRAIN[1191])
        self.assertEqual(tables.island_terrain[954], "urban")
        self.assertIn(954, tables.island_urban)
        # A city keeps its parent id; its remainder and that remainder's parts keep authored rivers.
        self.assertIn(1304, tables.city_provinces)
        self.assertTrue({902, 955, 956} <= tables.authored_rivers)

    def test_geometry_layers_split_the_raster_at_its_sheet_row(self) -> None:
        manifest = synthetic_manifest()
        sheet = np.arange(5 * 3 * 4, dtype=np.uint8).reshape(5, 3, 4)
        (first_origin, first), (second_origin, second) = builder.geometry_layers(manifest, sheet)
        self.assertEqual((first_origin, second_origin), ([0, 0], [0, 0]))
        np.testing.assert_array_equal(first, sheet[:2])
        np.testing.assert_array_equal(second, sheet[2:])

    def test_stamp_layer_refuses_land_outside_the_scope(self) -> None:
        rgb = np.zeros((2, 3, 3), np.uint8)
        rgb[0, 0] = (1, 1, 1)
        rgb[0, 1] = (9, 9, 9)
        layer = np.zeros((1, 2, 4), np.uint8)
        layer[0, 0] = (2, 2, 2, 255)
        colours = {1: (1, 1, 1), 2: (2, 2, 2), 3: (9, 9, 9)}
        builder.stamp_layer(rgb, layer, (0, 0), colours, frozenset({1, 2}))
        self.assertEqual(tuple(rgb[0, 0]), (2, 2, 2))
        layer[0, 1] = (2, 2, 2, 255)
        with self.assertRaisesRegex(RuntimeError, "outside its scope"):
            builder.stamp_layer(rgb, layer, (0, 0), colours, frozenset({1, 2}))

    def test_planned_settlements_cover_every_state_with_unique_names(self) -> None:
        towns = [entry.state for entry in builder.STAGE2_SETTLEMENTS if entry.kind == "town"]
        self.assertEqual(len(towns), len(set(towns)))
        # A split half counts its centre as its settlement.
        centres = builder.split_centres()
        self.assertEqual(set(towns) | (set(centres) & builder.SCOPED_STATE_IDS), set(builder.SCOPED_STATE_IDS))
        state_of = builder.province_state_contract(builder.SCOPED_STATE_IDS)
        for state_id in set(centres) & builder.SCOPED_STATE_IDS:
            self.assertEqual(state_of[centres[state_id]], state_id)
        names = [entry.name for entry in builder.STAGE2_SETTLEMENTS]
        english = [entry.name_en for entry in builder.STAGE2_SETTLEMENTS]
        self.assertEqual(len(names), len(set(names)))
        self.assertEqual(len(english), len(set(english)))
        for entry in builder.STAGE2_SETTLEMENTS:
            with self.subTest(settlement=entry.name_en):
                low, high = (3, 5) if entry.kind == "city" else (1, 2)
                self.assertTrue(low <= entry.value <= high)
                self.assertTrue(entry.name_en.isascii())
                self.assertNotIn("\u2014", entry.name + entry.name_en)
        self.assertEqual(
            builder.settlement_name_collisions(builder.REPOSITORY_ROOT, builder.STAGE2_SETTLEMENTS), []
        )


def river_canvas(width: int = 12, height: int = 8) -> np.ndarray:
    return np.full((height, width), builder.RIVER_LAND_PALETTE, np.uint8)


class Stage2RiverRuleTests(unittest.TestCase):
    """The drawing rules on a receiver running east into the sea and a tributary from the north."""

    def network(self) -> tuple[np.ndarray, np.ndarray]:
        rivers = river_canvas()
        water = np.zeros(rivers.shape, bool)
        water[:, 11] = True
        rivers[5, 1] = builder.RIVER_SOURCE_PALETTE
        rivers[5, 2:11] = (3, 3, 4, 4, 6, 6, 6, 7, 7)
        # A tributary with a source at its head, too wide and shrinking downstream.
        rivers[1, 5] = builder.RIVER_SOURCE_PALETTE
        rivers[2, 5] = 9
        rivers[3, 5] = 7
        rivers[4, 5] = builder.RIVER_FLOW_IN_PALETTE
        return rivers, water

    def test_settling_gives_tributaries_widths_no_wider_than_their_receiver(self) -> None:
        rivers, water = self.network()
        inside = np.ones(rivers.shape, bool)
        self.assertTrue(builder.course_rule_issues(rivers, inside, water, (0, 0)))
        builder.settle_course_widths(rivers, inside, water)
        self.assertEqual(builder.course_rule_issues(rivers, inside, water, (0, 0)), [])
        tributary = [int(rivers[y, 5]) for y in (1, 2, 3)]
        self.assertNotIn(builder.RIVER_SOURCE_PALETTE, tributary)
        self.assertEqual(tributary, sorted(tributary))
        self.assertLessEqual(max(tributary), int(rivers[5, 5]))
        self.assertEqual(rivers[5, 1], builder.RIVER_SOURCE_PALETTE)
        self.assertEqual(rivers[4, 5], builder.RIVER_FLOW_IN_PALETTE)
        body = [int(value) for value in rivers[5, 2:11]]
        self.assertEqual(body, sorted(body))
        self.assertFalse(set(body) - set(builder.NATIVE_RIVER_WIDTHS))

    def test_settling_leaves_pixels_outside_the_editable_area(self) -> None:
        rivers, water = self.network()
        editable = np.zeros(rivers.shape, bool)
        before = rivers.copy()
        builder.settle_course_widths(rivers, editable, water)
        np.testing.assert_array_equal(rivers, before)

    def test_state_line_turns_are_corners_beside_foreign_land_only(self) -> None:
        ids = np.array(
            [
                [1, 1, 1, 1, 9, 9],
                [1, 1, 1, 9, 9, 9],
                [1, 1, 1, 9, 9, 9],
                [1, 2, 1, 9, 9, 9],
                [1, 1, 1, 1, 9, 9],
            ]
        )
        inside = ids != 9
        turns = builder.state_line_turns(ids, inside)
        # (0, 2) touches province 9 only at a corner; (4, 2) also touches province 2
        # at a corner, and (2, 2) touches 9 across an edge.
        self.assertTrue(turns[0, 2])
        self.assertFalse(turns[4, 2])
        self.assertFalse(turns[2, 2])


SMOOTHING_STATES = {1: 10, 2: 10, 3: 20, 4: 20}
SMOOTHING_SCOPE = frozenset({10, 20})


def smoothing_canvas() -> np.ndarray:
    """State 10 (provinces 1 and 2) west of state 20 (3 and 4); their inner lines are offset."""
    labels = np.zeros((30, 30), np.int32)
    labels[:15, :15] = 1
    labels[15:, :15] = 2
    labels[:12, 15:] = 3
    labels[12:, 15:] = 4
    return labels


def four_province_squares(labels: np.ndarray) -> int:
    a, b, c, d = labels[:-1, :-1], labels[:-1, 1:], labels[1:, :-1], labels[1:, 1:]
    return int(((a != b) & (a != c) & (a != d) & (b != c) & (b != d) & (c != d)).sum())


class StateBorderSmoothingTests(unittest.TestCase):
    """The state-line smoothing of spec 13.3 on small synthetic windows."""

    def smooth(self, labels: np.ndarray, **options) -> builder.StateSmoothing:
        land = options.pop("land", np.ones(labels.shape, bool))
        river = options.pop("river", np.zeros(labels.shape, bool))
        return builder.smooth_state_borders(labels, SMOOTHING_STATES, SMOOTHING_SCOPE, land, river, **options)

    def assert_contracts(self, before: np.ndarray, result: builder.StateSmoothing) -> None:
        after = result.labels
        self.assertEqual(set(np.unique(after).tolist()), set(np.unique(before).tolist()))
        for province in np.unique(after).tolist():
            mask = after == province
            self.assertEqual(label(mask)[1], 1, f"province {province} split")
            self.assertGreaterEqual(int(mask.sum()), min(builder.STATE_SMOOTHING_MIN_PIXELS, int((before == province).sum())))
        self.assertLessEqual(four_province_squares(after), four_province_squares(before))
        self.assertEqual(result.rail_lost, ())

    def test_a_tooth_rejoins_the_state_round_it_and_the_line_shortens(self) -> None:
        labels = smoothing_canvas()
        labels[5:8, 12:15] = 3
        result = self.smooth(labels)
        self.assertTrue(result.stable)
        self.assertGreater(result.moved, 0)
        self.assertLess(result.state_edges_after, result.state_edges_before)
        self.assertEqual(result.labels[6, 12], 1)
        self.assertEqual(sum(result.transfers.values()), result.moved)
        self.assert_contracts(labels, result)
        # Every moved pixel joined a province that it touches across a pixel edge.
        for y, x in np.argwhere(result.labels != labels).tolist():
            beside = {int(result.labels[y + dy, x + dx]) for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1))}
            self.assertIn(int(result.labels[y, x]), beside)

    def test_a_straight_line_stays(self) -> None:
        labels = smoothing_canvas()
        result = self.smooth(labels)
        self.assertEqual(result.moved, 0)
        self.assertTrue(result.stable)

    def test_a_second_run_moves_nothing(self) -> None:
        labels = smoothing_canvas()
        labels[5:8, 12:15] = 3
        labels[18:21, 15:18] = 2
        first = self.smooth(labels)
        second = self.smooth(first.labels)
        self.assertGreater(first.moved, 0)
        self.assertTrue(first.stable)
        self.assertEqual(second.moved, 0)
        self.assertEqual(second.pass_moves, ())
        np.testing.assert_array_equal(second.labels, first.labels)

    def test_protected_pixels_never_move(self) -> None:
        labels = smoothing_canvas()
        labels[5:8, 12:15] = 3
        eight = np.ones((3, 3), bool)
        river = np.zeros(labels.shape, bool)
        river[4:9, 13] = True
        frozen = np.zeros(labels.shape, bool)
        frozen[5:8, 12:15] = True
        water = np.zeros(labels.shape, bool)
        water[3, 10:15] = True
        cases = (
            ({"river": river}, binary_dilation(river, eight)),
            ({"frozen": frozen}, frozen),
            ({"settlements": frozenset({1})}, binary_dilation(labels == 1, eight)),
            ({"land": ~water}, binary_dilation(water, eight)),
        )
        for options, protected in cases:
            with self.subTest(protection=sorted(options)):
                result = self.smooth(labels, **options)
                np.testing.assert_array_equal(result.labels[protected], labels[protected])
                self.assert_contracts(labels, result)
        self.assertGreater(self.smooth(labels, frozen=frozen).moved, 0)

    def test_a_province_keeps_its_minimum_size(self) -> None:
        labels = smoothing_canvas()
        labels[3:12, 12:15] = 5
        states = {**SMOOTHING_STATES, 5: 20}
        land = np.ones(labels.shape, bool)
        river = np.zeros(labels.shape, bool)
        result = builder.smooth_state_borders(labels, states, SMOOTHING_SCOPE, land, river)
        self.assertEqual(int((labels == 5).sum()), 27)
        self.assertGreaterEqual(int((result.labels == 5).sum()), builder.STATE_SMOOTHING_MIN_PIXELS)
        self.assertGreater(result.moved, 0)
        self.assert_contracts(labels, result)
        larger = builder.smooth_state_borders(labels, states, SMOOTHING_SCOPE, land, river, min_pixels={5: 27})
        self.assertEqual(int((larger.labels == 5).sum()), 27)

    def test_area_limits_hold_for_provinces_and_groups(self) -> None:
        labels = smoothing_canvas()
        labels[5:8, 12:15] = 3
        size = int((labels == 1).sum())
        capped = self.smooth(labels, area_limits={1: (0, size)})
        self.assertLessEqual(int((capped.labels == 1).sum()), size)
        # Provinces 3 and 4 as one group that may not shrink.
        group = int(np.isin(labels, [3, 4]).sum())
        kept = self.smooth(labels, group_of={3: 3, 4: 3}, area_limits={3: (group, 10_000)})
        self.assertGreaterEqual(int(np.isin(kept.labels, [3, 4]).sum()), group)
        self.assert_contracts(labels, kept)

    def test_a_province_is_never_cut_in_two(self) -> None:
        labels = smoothing_canvas()
        # A blob of province 3 inside state 10, held only by a one-pixel neck.
        labels[4:11, 3:9] = 3
        labels[7, 9:15] = 3
        result = self.smooth(labels)
        self.assertGreater(result.moved, 0)
        self.assert_contracts(labels, result)
        self.assertTrue((result.labels[7, 9:15] == 3).all())

    def test_railway_segments_keep_their_contact(self) -> None:
        labels = smoothing_canvas()
        # A tooth of 3 holds the contact between 1 and 4; the smoothing would close it.
        labels[8:13, 11:15] = 3
        self.assertIn(4, builder.province_adjacency(labels)[1])
        free = self.smooth(labels)
        self.assertNotIn(4, builder.province_adjacency(free.labels)[1])
        kept = self.smooth(labels, rail_pairs={(4, 1)})
        self.assertIn(4, builder.province_adjacency(kept.labels)[1])
        self.assertEqual(kept.rail_segments, 1)
        self.assertGreater(kept.moved, 0)
        self.assert_contracts(labels, kept)

    def test_no_move_closes_a_four_province_square(self) -> None:
        labels = np.array(
            [
                [1, 1, 3],
                [1, 2, 4],
                [2, 2, 4],
            ]
        )
        self.assertTrue(builder._closes_four_corner(labels, 1, 1, 5))
        self.assertFalse(builder._closes_four_corner(labels, 1, 1, 1))

    def test_interior_river_pixels_are_counted_per_state(self) -> None:
        states = np.array(
            [
                [10, 10, 10, 20],
                [10, 10, 10, 20],
                [0, 0, 0, 0],
            ]
        )
        land = states > 0
        river = np.zeros(states.shape, bool)
        river[0, 1] = True
        river[1, 2] = True
        river[1, 3] = True
        counts = builder.interior_river_pixels_by_state(river, states, land, SMOOTHING_SCOPE)
        # (1, 2) and (1, 3) lie on the state line; (0, 1) has only state 10 round it.
        self.assertEqual(counts, {10: 1})

    def test_a_course_prefers_a_state_line_where_one_runs_beside_it(self) -> None:
        # Two equally long ways round a block; only the lower one is a state line.
        allowed = np.zeros((7, 9), bool)
        allowed[1, 1:8] = True
        allowed[5, 1:8] = True
        allowed[1:6, 1] = True
        allowed[1:6, 7] = True
        heights = np.zeros(allowed.shape, np.uint8)
        packed = np.zeros(allowed.shape, np.int64)
        preferred = np.zeros(allowed.shape, bool)
        preferred[5, 1:8] = True
        path = builder._route_river((1, 3), [(7, 3)], allowed, heights, packed, preferred)
        self.assertIn((4, 5), path)
        self.assertNotIn((4, 1), path)
        plain = builder._route_river((1, 3), [(7, 3)], allowed, heights, packed)
        self.assertEqual(len(plain), len(path))

    def test_moved_pixels_join_the_stage2_layer(self) -> None:
        manifest = {"stage2": {"origin": [4, 4], "sheet_row": 2}}
        sheet = np.zeros((5, 6, 4), np.uint8)
        sheet[:2] = 7
        sheet[2:, :3] = (1, 1, 1, 255)
        sheet[3, 1, 3] = 0
        window = builder._mon().Window(0, 10, 0, 10)
        moved = np.zeros((10, 10), bool)
        moved[2, 5] = True
        labels = np.zeros((10, 10), np.int32)
        labels[2, 5] = 9
        origin, combined = builder.stage2_sheet_with_moves(manifest, sheet, moved, labels, window, {9: (9, 8, 7)})
        self.assertEqual(origin, [4, 2])
        np.testing.assert_array_equal(combined[:2, :6], sheet[:2])
        layer = combined[2:]
        self.assertEqual(tuple(layer[0, 1]), (9, 8, 7, 255))
        # The earlier layer keeps its pixels, now two rows lower; its transparent pixel stays transparent.
        np.testing.assert_array_equal(layer[2:5, 0:3][..., 3] > 0, sheet[2:, :3][..., 3] > 0)


class Stage2DryRunTests(unittest.TestCase):
    """Plan Stage 2 on the current map and apply it to copies outside the repository."""

    @classmethod
    def setUpClass(cls) -> None:
        manifest = json.loads(builder.PROVINCE_MANIFEST_PATH.read_text(encoding="utf-8"))
        if builder.has_stage2_plan(manifest):
            raise unittest.SkipTest("the manifest holds a Stage 2 plan; its own checks apply")
        cls.directory = TemporaryDirectory()
        cls.root = Path(cls.directory.name)
        cls.stored = (
            builder.PROVINCE_MANIFEST_PATH.read_bytes(),
            builder.PROVINCE_GEOMETRY_PATH.read_bytes(),
        )
        cls.report = builder.write_stage2_plan(cls.root)
        cls.manifest_bytes = (cls.root / "tools/data/adiscord_ivn_provinces.json").read_bytes()
        cls.plan = json.loads(cls.manifest_bytes.decode("utf-8"))["stage2"]
        cls.result = builder.dry_run_stage2(cls.root)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.directory.cleanup()

    def test_the_repository_plan_files_stay_untouched(self) -> None:
        self.assertEqual(
            (builder.PROVINCE_MANIFEST_PATH.read_bytes(), builder.PROVINCE_GEOMETRY_PATH.read_bytes()),
            self.stored,
        )
        self.assertEqual(builder.MAP_ROOT, builder.REPOSITORY_ROOT)

    def test_stage1_of_the_manifest_and_raster_stays_byte_for_byte(self) -> None:
        manifest = json.loads(self.manifest_bytes.decode("utf-8"))
        del manifest["stage2"]
        newline = b"\r\n" if b"\r\n" in self.stored[0] else b"\n"
        dumped = (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        self.assertEqual(dumped.replace(b"\n", newline), self.stored[0])
        with Image.open(BytesIO(self.stored[1])) as source:
            first = np.asarray(source.convert("RGBA"))
        with Image.open(self.root / "tools/data/adiscord_ivn_province_geometry.png") as source:
            sheet = np.asarray(source.convert("RGBA"))
        self.assertEqual(self.plan["sheet_row"], first.shape[0])
        np.testing.assert_array_equal(sheet[: first.shape[0], : first.shape[1]], first)

    def test_new_ids_follow_the_definition_and_keep_the_border_margin(self) -> None:
        rows = builder.DEFINITION_PATH.read_text(encoding="utf-8-sig").splitlines()
        last = max(int(line.split(";")[0]) for line in rows if line[:1].isdigit())
        ids = [int(entry["province"]) for entry in self.plan["provinces"]]
        self.assertEqual(ids, list(range(last + 1, last + 1 + len(ids))))
        self.assertGreaterEqual(builder.BORDER_BUDGET - self.report["borders"], builder.BORDER_MARGIN)
        self.assertEqual(self.result["after"]["borders"], self.report["borders"])

    def test_parts_cities_and_towns_have_their_sizes_and_shapes(self) -> None:
        low, high = self.report["part_pixels"]
        self.assertGreaterEqual(low, builder.STAGE2_PART_MIN_PIXELS)
        irregular = set(self.report["irregular_parts"])
        for parent, ids in self.report["splits"].items():
            self.assertEqual(int(parent), ids[0])
        self.assertTrue(irregular <= {province for ids in self.report["splits"].values() for province in ids})
        for city, size in self.report["city_pixels"].items():
            self.assertTrue(builder.STAGE2_CITY_SIZE[0] <= size <= builder.STAGE2_CITY_SIZE[1], city)
        for town, size in self.report["town_pixels"].items():
            self.assertTrue(builder.STAGE2_TOWN_SIZE[0] <= size <= builder.STAGE2_TOWN_SIZE[1], town)
        states = {entry["state"] for entry in self.plan["settlements"] if entry["kind"] == "town"}
        self.assertEqual(states, set(builder.SCOPED_STATE_IDS))

    def test_one_pass_settles_the_geometry_and_the_rules(self) -> None:
        issues = self.result["issues_after_one_pass"]
        self.assertEqual([issue for issue in issues if "drifted" in issue or "not adjacent" in issue], [])
        self.assertEqual([issue for issue in issues if issue.startswith("Stage 2") or "named by id" in issue], [])
        self.assertEqual([issue for issue in issues if "naval base" in issue], [])
        river = [issue for issue in issues if issue.startswith("map/rivers.bmp")]
        for rule in ("cut IVN/IIA provinces", "palette 5 or 8", "2x2", "third course", "source pixel", "shrink", "wider than", "settlements"):
            self.assertEqual([issue for issue in river if rule in issue], [], rule)

    def test_rivers_leave_fewer_interior_pixels_and_no_forbidden_widths(self) -> None:
        before, after = self.result["before"], self.result["after"]
        genuine_before = before["off_border_river_pixels"] - before["state_line_turn_pixels"]
        genuine_after = after["off_border_river_pixels"] - after["state_line_turn_pixels"]
        self.assertLess(genuine_after, genuine_before)
        self.assertFalse({"5", "8"} & set(after["river_palettes"]))
        self.assertEqual(after["provinces"], before["provinces"] + len(self.plan["provinces"]))


if __name__ == "__main__":
    unittest.main()
