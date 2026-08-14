#!/usr/bin/env python3
"""Tests for deterministic Vorkerland city-model masks."""

from __future__ import annotations

import hashlib
from io import BytesIO
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from PIL import Image

from tools.builders import build_adiscord_vorkerland_cities as cities


TARGET = 1
TARGET_RGB = (10, 20, 30)
OTHER_RGB = (40, 50, 60)


def write_fixture(root: Path, *, target_type: str = "land", include_mask: bool = True) -> None:
    definition = root / "definition.csv"
    definition.write_text(
        "0;0;0;0;sea;false;ocean;0\n"
        f"1;10;20;30;{target_type};false;urban;1\n"
        "2;40;50;60;land;false;plains;1\n",
        encoding="utf-8",
    )
    provinces = Image.new("RGB", (4, 2), OTHER_RGB)
    if include_mask:
        provinces.putpixel((0, 0), TARGET_RGB)
        provinces.putpixel((1, 1), TARGET_RGB)
    provinces.save(root / "provinces.bmp", format="BMP")
    city_map = Image.new("P", (4, 2))
    palette = []
    for index in range(256):
        palette.extend(((index * 3) % 256, (index * 5) % 256, (index * 7) % 256))
    city_map.putpalette(palette)
    city_map.putdata([1, 2, 3, 4, 5, 6, 7, 8])
    city_map.save(root / "cities.bmp", format="BMP")


class VorkerlandCitiesTests(unittest.TestCase):
    def fixture_patches(self, root: Path):
        return (
            patch.object(cities, "ROOT", root),
            patch.object(cities, "CITIES_PATH", root / "cities.bmp"),
            patch.object(cities, "PROVINCES_PATH", root / "provinces.bmp"),
            patch.object(cities, "DEFINITION_PATH", root / "definition.csv"),
            patch.object(cities, "TARGET_PROVINCES", frozenset({TARGET})),
        )

    def test_render_sets_exact_target_mask_and_preserves_unmanaged_bytes(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            write_fixture(root)
            source = (root / "cities.bmp").read_bytes()
            with self.fixture_patches(root)[-1]:
                colours, issues = cities.target_colours(root / "definition.csv")
                self.assertEqual(issues, [])
                with Image.open(root / "provinces.bmp") as provinces:
                    generated, counts, positions = cities.render_bytes(source, provinces, colours)
            self.assertEqual(counts, {TARGET: 2})
            self.assertEqual(cities.unmanaged_difference_count(source, generated, positions), 0)
            layout = cities.bitmap_layout(generated)
            target_positions = {
                layout.pixel_position(0, 0),
                layout.pixel_position(1, 1),
            }
            self.assertEqual(positions, target_positions)
            self.assertTrue(all(generated[position] == cities.CITY_PALETTE_INDEX for position in positions))
            self.assertTrue(
                all(
                    source[index] == generated[index]
                    for index in range(len(source))
                    if index not in positions
                )
            )

    def test_apply_preserves_mode_size_palette_and_is_byte_idempotent(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            write_fixture(root)
            with Image.open(BytesIO((root / "cities.bmp").read_bytes())) as before:
                original_mode = before.mode
                original_size = before.size
                original_palette = before.getpalette()
            patches = self.fixture_patches(root)
            with patches[0], patches[1], patches[2], patches[3], patches[4]:
                cities.apply()
                first = (root / "cities.bmp").read_bytes()
                first_hash = hashlib.sha256(first).hexdigest()
                self.assertEqual(cities.validate(), [])
                cities.apply()
                second = (root / "cities.bmp").read_bytes()
                self.assertEqual(hashlib.sha256(second).hexdigest(), first_hash)
            with Image.open(BytesIO(second)) as after:
                self.assertEqual(after.mode, original_mode)
                self.assertEqual(after.size, original_size)
                self.assertEqual(after.getpalette(), original_palette)
                self.assertEqual(
                    list(after.get_flattened_data()), [15, 2, 3, 4, 5, 15, 7, 8]
                )

    def test_validate_rejects_non_land_target(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            write_fixture(root, target_type="sea")
            patches = self.fixture_patches(root)
            with patches[0], patches[1], patches[2], patches[3], patches[4]:
                issues = cities.validate()
            self.assertTrue(any("is not land" in issue for issue in issues))

    def test_validate_rejects_empty_target_mask(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            write_fixture(root, include_mask=False)
            patches = self.fixture_patches(root)
            with patches[0], patches[1], patches[2], patches[3], patches[4]:
                issues = cities.validate()
            self.assertTrue(any("empty mask" in issue for issue in issues))

    def test_apply_replace_failure_preserves_original_and_cleans_temp(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            write_fixture(root)
            original = (root / "cities.bmp").read_bytes()
            patches = self.fixture_patches(root)
            with (
                patches[0], patches[1], patches[2], patches[3], patches[4],
                patch.object(os, "replace", side_effect=OSError("replace denied")),
            ):
                with self.assertRaisesRegex(OSError, "replace denied"):
                    cities.apply()
            self.assertEqual((root / "cities.bmp").read_bytes(), original)
            self.assertFalse((root / "cities.bmp.tmp").exists())


if __name__ == "__main__":
    unittest.main()
