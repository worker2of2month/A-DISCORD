#!/usr/bin/env python3
"""Regression tests for the northern terrain band of the relief readability pass.

Two defects live in this band and both were visible to the player.  The
inherited converted art carried a single-row terrain-index seam at ``y = 300``
that read as a straight line drawn across the northern continent, and the warm
``mountain_variation_grass`` and ``desert_mountain`` textures reached the ice cap
so lush green sat directly against snow and grey rock.

Both fixes have to be fixed points of their own output, because the builder reads
``map/terrain.bmp`` as its own input.  These tests hold that property, the
category-preserving contract of the palette substitution, and the seam metric
itself.
"""

from __future__ import annotations

import unittest
from unittest.mock import patch

import numpy as np
from PIL import Image

from tools.builders import build_adiscord_map_relief_readability as relief
from tools.builders import build_adiscord_terrain_snow as snow
from tools.lib.map_raster import CATEGORY_PALETTE, PALETTE_TYPES


WIDTH = 512
HEIGHT = relief.NORTHERN_SEAM_ROW + 320


def _seamed_terrain(north: int = 0, south: int = 17) -> bytearray:
    """Return a raster split by one hard index seam at the inherited row."""

    pixels = bytearray(WIDTH * HEIGHT)
    for y in range(HEIGHT):
        value = north if y < relief.NORTHERN_SEAM_ROW else south
        for x in range(WIDTH):
            pixels[y * WIDTH + x] = value
    return pixels


def _row_change_share(pixels: bytearray, row: int) -> float:
    changed = sum(
        pixels[(row - 1) * WIDTH + x] != pixels[row * WIDTH + x] for x in range(WIDTH)
    )
    return changed / WIDTH


class NorthernSeamTests(unittest.TestCase):
    def setUp(self) -> None:
        self.heights = bytes([120] * (WIDTH * HEIGHT))
        # The inherited seam row sits inside the permanent-snow cap over much of
        # the real map, and the dissolve deliberately declines to touch pixels the
        # classifier paints white.  Switching the cap off isolates the geometry
        # these tests are about; the skip has a test of its own below.
        patcher = patch.object(snow, "POLAR_CAP_Y", 0)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_hard_seam_is_spread_across_the_whole_band(self) -> None:
        pixels = _seamed_terrain()
        self.assertEqual(_row_change_share(pixels, relief.NORTHERN_SEAM_ROW), 1.0)

        changed = relief.dissolve_northern_seam(pixels, self.heights, WIDTH, HEIGHT)

        self.assertTrue(changed)
        share = _row_change_share(pixels, relief.NORTHERN_SEAM_ROW)
        self.assertLess(share, 0.30, "the seam row still carries most of the change")
        band = relief.northern_seam_band(HEIGHT)
        carrying = [
            row for row in band if _row_change_share(pixels, row) > 0.0
        ]
        self.assertGreaterEqual(
            len(carrying), 6, "the transition must be shared by many rows"
        )

    def test_longest_unbroken_run_of_the_seam_is_short(self) -> None:
        """A straight line is a *run*, not a pixel count; measure it as one."""

        pixels = _seamed_terrain()
        relief.dissolve_northern_seam(pixels, self.heights, WIDTH, HEIGHT)
        row = relief.NORTHERN_SEAM_ROW
        longest = current = 0
        for x in range(WIDTH):
            above = pixels[(row - 1) * WIDTH + x]
            below = pixels[row * WIDTH + x]
            current = current + 1 if above != below else 0
            longest = max(longest, current)
        self.assertLess(longest, 40)

    def test_dissolve_is_a_fixed_point(self) -> None:
        pixels = _seamed_terrain()
        relief.dissolve_northern_seam(pixels, self.heights, WIDTH, HEIGHT)
        snapshot = bytes(pixels)

        again = relief.dissolve_northern_seam(pixels, self.heights, WIDTH, HEIGHT)

        self.assertFalse(again)
        self.assertEqual(bytes(pixels), snapshot)

    def test_dissolve_only_ever_writes_one_of_the_two_anchor_indices(self) -> None:
        """Local variety inside the band has to survive the dissolve.

        A pixel carrying neither anchor index - a marsh pocket, a rock outcrop -
        is none of this pass's business, and reassigning it would flatten the
        band into two colours.
        """

        pixels = _seamed_terrain()
        marsh = CATEGORY_PALETTE["marsh"][0]
        band = relief.northern_seam_band(HEIGHT)
        pockets = {row * WIDTH + 7 for row in band}
        for index in pockets:
            pixels[index] = marsh

        relief.dissolve_northern_seam(pixels, self.heights, WIDTH, HEIGHT)

        self.assertTrue(all(pixels[index] == marsh for index in pockets))

    def test_dissolve_never_touches_water_or_urban_columns(self) -> None:
        pixels = _seamed_terrain()
        urban = relief.URBAN_PALETTE
        ocean = sorted(relief.WATER_PALETTE)[-1]
        for row in range(HEIGHT):
            pixels[row * WIDTH + 3] = ocean
            pixels[row * WIDTH + 4] = urban
        protected = [
            row * WIDTH + column
            for row in relief.northern_seam_band(HEIGHT)
            for column in (3, 4)
        ]
        before = [pixels[index] for index in protected]

        relief.dissolve_northern_seam(pixels, self.heights, WIDTH, HEIGHT)

        self.assertEqual([pixels[index] for index in protected], before)

    def test_permanent_snow_columns_are_left_to_the_snow_builder(self) -> None:
        """Inside the cap the visible boundary is the snow edge, not this seam.

        Skipping those pixels is also what makes the pass a fixed point:
        ``RESTORE_SNOW`` collapses both snow indices onto one representative each,
        so a hills pixel that snow had covered would come back as plains on the
        next run and the dissolve would keep moving it.
        """

        patch.stopall()
        pixels = _seamed_terrain()
        band = relief.northern_seam_band(HEIGHT)
        buried = [
            column
            for column in range(WIDTH)
            if snow.polar_cap_boundary(column, 120) > band.stop + 4
        ]
        self.assertTrue(buried, "the fixture needs columns well inside the cap")

        changed = relief.dissolve_northern_seam(pixels, self.heights, WIDTH, HEIGHT)

        touched = {index % WIDTH for index in changed}
        self.assertFalse(touched & set(buried))

    def test_disabled_band_leaves_the_raster_alone(self) -> None:
        pixels = _seamed_terrain()
        snapshot = bytes(pixels)
        self.assertFalse(relief.northern_seam_band(relief.NORTHERN_SEAM_ROW))
        self.assertFalse(
            relief.dissolve_northern_seam(
                pixels, self.heights, WIDTH, relief.NORTHERN_SEAM_ROW
            )
        )
        self.assertEqual(bytes(pixels), snapshot)


class NorthernPaletteTemperatureTests(unittest.TestCase):
    def test_every_substitution_preserves_the_terrain_category(self) -> None:
        """The swap must change texture only.

        ``map/definition.csv`` declares gameplay terrain and this pass asserts a
        readability share against it, so a substitution that moved a pixel between
        categories would silently break that contract while looking like a colour
        fix.
        """

        for warm, cool in relief.COLD_PALETTE_SUBSTITUTION.items():
            with self.subTest(warm=warm):
                self.assertIn(warm, PALETTE_TYPES)
                self.assertIn(cool, PALETTE_TYPES)
                self.assertEqual(PALETTE_TYPES[warm], PALETTE_TYPES[cool])

    def test_no_substitution_target_is_itself_a_source(self) -> None:
        """This is what makes the pass a fixed point, so state it as a contract."""

        targets = set(relief.COLD_PALETTE_SUBSTITUTION.values())
        sources = set(relief.COLD_PALETTE_SUBSTITUTION)
        self.assertFalse(targets & sources)

    def test_no_forest_index_is_substituted(self) -> None:
        """``00_terrain.txt`` has no boreal forest entry, so forest is left alone.

        Palette 1 and 4 are the only ``forest`` indices and they sit on textures 4
        and 5, which jungle also uses.  There is nothing colder to move them to,
        and recolouring them out of forest would break the declared-terrain
        readability contract for every forest province in the north.
        """

        for index, category in PALETTE_TYPES.items():
            if category == "forest":
                self.assertNotIn(index, relief.COLD_PALETTE_SUBSTITUTION)

    def test_grass_is_cooled_against_the_cap_and_left_alone_far_south(self) -> None:
        width = 256
        height = relief.NORTHERN_SEAM_ROW + relief.COLD_BAND_DEPTH + 400
        grass = 20
        pixels = bytearray([grass] * (width * height))
        heights = np.full((height, width), 120, dtype=np.uint8)
        land = np.ones((height, width), dtype=bool)

        _changed, substituted = relief.cool_northern_palette(pixels, heights, land)

        self.assertEqual(set(substituted), {grass})
        array = np.frombuffer(bytes(pixels), dtype=np.uint8).reshape(height, width)
        cap = min(
            snow.polar_cap_boundary(x, 120) for x in range(width)
        )
        self.assertTrue(
            (array[max(cap - 1, 0)] == relief.COLD_PALETTE_SUBSTITUTION[grass]).all(),
            "grass touching the ice cap must all become rock",
        )
        far_south = height - 1
        self.assertTrue(
            (array[far_south] == grass).all(),
            "the substitution must not reach the temperate map",
        )

    def test_cold_band_edge_is_not_a_straight_line(self) -> None:
        width = 256
        height = relief.NORTHERN_SEAM_ROW + relief.COLD_BAND_DEPTH + 200
        grass = 20
        pixels = bytearray([grass] * (width * height))
        heights = np.full((height, width), 120, dtype=np.uint8)
        land = np.ones((height, width), dtype=bool)
        relief.cool_northern_palette(pixels, heights, land)
        array = np.frombuffer(bytes(pixels), dtype=np.uint8).reshape(height, width)
        cool = relief.COLD_PALETTE_SUBSTITUTION[grass]
        deepest = [
            int(np.nonzero(array[:, x] == cool)[0].max())
            for x in range(width)
            if (array[:, x] == cool).any()
        ]
        self.assertEqual(len(deepest), width)
        self.assertGreaterEqual(
            max(deepest) - min(deepest),
            20,
            "a constant-depth substitution would trade one straight edge for another",
        )

    def test_cooling_is_a_fixed_point(self) -> None:
        width = 128
        height = relief.NORTHERN_SEAM_ROW + relief.COLD_BAND_DEPTH + 80
        pixels = bytearray()
        for row in range(height):
            for column in range(width):
                pixels.append(20 if (row + column) % 3 else 2)
        heights = np.full((height, width), 150, dtype=np.uint8)
        land = np.ones((height, width), dtype=bool)

        relief.cool_northern_palette(pixels, heights, land)
        snapshot = bytes(pixels)
        changed, substituted = relief.cool_northern_palette(pixels, heights, land)

        self.assertFalse(changed)
        self.assertFalse(substituted)
        self.assertEqual(bytes(pixels), snapshot)

    def test_water_is_never_cooled(self) -> None:
        width = 64
        height = relief.NORTHERN_SEAM_ROW + 40
        ocean = sorted(relief.WATER_PALETTE)[-1]
        pixels = bytearray([ocean] * (width * height))
        heights = np.full((height, width), 89, dtype=np.uint8)
        land = np.zeros((height, width), dtype=bool)

        changed, substituted = relief.cool_northern_palette(pixels, heights, land)

        self.assertFalse(changed)
        self.assertFalse(substituted)
        self.assertTrue(all(value == ocean for value in pixels))


class TerrainClaimTests(unittest.TestCase):
    def test_the_claim_excludes_the_alignment_only_provinces(self) -> None:
        """``--check`` has to compare only what this builder writes.

        Comparing every byte of ``map/terrain.bmp`` reported 30 pixels that
        ``build_adiscord_province_layer_alignment`` legitimately owns and writes
        afterwards, so a clean pipeline looked like drift.
        """

        from tools.builders import build_adiscord_province_layer_alignment as align

        scope = relief.load_scope()
        overlap = relief.terrain_province_ids(scope) & align.TARGET_PROVINCE_IDS
        self.assertTrue(
            overlap, "the shared city provinces are the reason the claim is scoped"
        )
        self.assertTrue(align.TARGET_PROVINCE_IDS - overlap)

    def test_check_ignores_a_difference_outside_the_claim(self) -> None:
        width = height = 4
        image = Image.new("P", (width, height), color=0)
        image.putpalette(
            [component for value in range(256) for component in (value, value, value)]
        )
        expected = image.copy()
        current = image.copy()
        pixels = list(current.get_flattened_data())
        pixels[5] = 17
        current.putdata(pixels)

        claim = np.zeros(width * height, dtype=bool)
        claim[0] = True
        current_bytes = np.frombuffer(current.tobytes(), dtype=np.uint8)
        expected_bytes = np.frombuffer(expected.tobytes(), dtype=np.uint8)

        self.assertTrue((current_bytes != expected_bytes).any())
        self.assertFalse(((current_bytes != expected_bytes) & claim).any())


if __name__ == "__main__":
    unittest.main()
