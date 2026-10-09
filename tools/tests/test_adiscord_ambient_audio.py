from __future__ import annotations

from pathlib import Path
import re
import tempfile
import unittest

import numpy as np

from tools.builders import build_adiscord_ambient_audio as builder
from tools.validators.validate_adiscord_division_templates import parse_clausewitz


ROOT = builder.ROOT


class AmbientPlacementTests(unittest.TestCase):
    def test_coasts_are_sea_pixels_beside_land_and_exclude_lakes(self):
        provinces = np.array([[2, 2, 2, 2], [2, 1, 3, 2], [2, 2, 2, 2]])
        mask = builder.coast_mask(provinces, {1: "land", 2: "sea", 3: "lake"})
        self.assertEqual(set(zip(*np.nonzero(mask))), {(0, 1), (1, 0), (2, 1)})

    def test_coast_spacing_covers_every_candidate_without_dense_overlaps(self):
        mask = np.zeros((23, 47), dtype=bool)
        mask[5, :] = True
        mask[15, :] = True
        points = builder.spaced_coast_pixels(mask, 9)
        for y, x in zip(*np.nonzero(mask)):
            distances = [min(abs(x - px), 47 - abs(x - px)) ** 2 + (y - py) ** 2
                         for px, py in points]
            self.assertLess(min(distances), 81)
        for i, (x, y) in enumerate(points):
            for px, py in points[i + 1:]:
                self.assertGreaterEqual(
                    min(abs(x - px), 47 - abs(x - px)) ** 2 + (y - py) ** 2, 81
                )

    def test_marked_rebuild_preserves_other_owners_and_is_idempotent(self):
        before = b'entity = { name = "authored" }\r\n'
        result = builder.replace_section(before, 'type = { type = "audio" }')
        self.assertTrue(result.startswith(before))
        self.assertEqual(builder.replace_section(result, 'type = { type = "audio" }'), result)
        with self.assertRaises(ValueError):
            builder.replace_section(result + result, "")

    def test_invalid_city_anchor_falls_back_inside_its_province(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "history/states").mkdir(parents=True)
            (root / "map").mkdir()
            (root / "history/states/1.txt").write_text(
                'state = { history = { victory_points = { 1 5 } victory_points = { 2 1 } } }'
            )
            (root / "history/states/3.txt").write_text(
                'state = { impassable = yes history = { victory_points = { 3 20 } } }'
            )
            (root / "map/unitstacks.txt").write_text('1;0;99;0;99;0;0\n')
            provinces = np.array([[1, 2], [3, 1]])
            heights = np.full((2, 2), 100)
            positions = builder.city_positions(root, provinces, heights, {1: "land", 2: "land", 3: "land"})
            self.assertEqual(len(positions), 1)
            name, x, y, z = positions[0]
            self.assertEqual(name, "ADISCORD_town_1")
            self.assertEqual(provinces[1 - int(z), int(x)], 1)
            self.assertEqual(y, 10.0)

    def test_city_clusters_keep_strongest_anchor_and_respect_map_seam(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "history/states").mkdir(parents=True)
            (root / "map").mkdir()
            state = root / "history/states/1.txt"
            victory_points = [(1, 5), (2, 30), (3, 10), (4, 30), (5, 5), (2, 5)]
            anchors = {1: 10, 2: 20, 3: 80, 4: 230, 5: 150}
            (root / "map/unitstacks.txt").write_text(
                "".join(f"{province};0;{x};0;0;0;0\n" for province, x in anchors.items())
            )
            provinces = np.zeros((1, 240), dtype=np.uint16)
            for province, x in anchors.items():
                provinces[0, x] = province
            heights = np.full(provinces.shape, 100)
            kinds = {province: "land" for province in anchors}

            for entries in (victory_points, list(reversed(victory_points))):
                state.write_text(
                    "state = { history = { "
                    + " ".join(
                        f"victory_points = {{ {province} {score} }}"
                        for province, score in entries
                    )
                    + " } }"
                )
                positions = builder.city_positions(root, provinces, heights, kinds)
                self.assertEqual(
                    [position[0] for position in positions],
                    ["ADISCORD_town_2", "ADISCORD_town_3", "ADISCORD_town_5"],
                )


class AmbientIntegrationTests(unittest.TestCase):
    def test_wind_has_exclusive_category_and_map_actor(self):
        source = (ROOT / "sound/assets_adiscord_soundeffects.asset").read_text(encoding="utf-8")
        entries = parse_clausewitz(source)
        categories = [e.value for e in entries if e.key == "category"]
        wind = [c for c in categories if any(e.key == "name" and e.value == "ADISCORD_Wind" for e in c)]
        self.assertEqual(len(wind), 1)
        sounds = next(e.value for e in wind[0] if e.key == "soundeffects")
        self.assertEqual([e.value for e in sounds], ["ADISCORD_ambient_wind"])
        defines = (ROOT / "common/defines/ADISCORD_defines_changes.lua").read_text()
        self.assertIn('NDefines_Graphics.NSound.HEIGHT_SOUND_CATEGORY = "ADISCORD_Wind"', defines)
        ambient = (ROOT / "map/ambient_object.txt").read_text()
        self.assertEqual(ambient.count('type="ADISCORD_ambient_wind_entity"'), 1)
        self.assertNotRegex(ambient, r'type\s*=\s*"ambient_wind_entity"')

    def test_generated_positions_match_inputs_and_remain_local(self):
        expected, coasts, cities = builder.build()
        self.assertEqual(expected, (ROOT / "map/ambient_object.txt").read_bytes())
        self.assertGreater(coasts, 4)
        self.assertGreater(cities, 0)
        text = expected.decode()
        section = text.split(builder.BEGIN, 1)[1].split(builder.END, 1)[0]
        self.assertNotIn("always_visible", section)
        self.assertEqual(len(re.findall(r'type\s*=\s*"ambient_water_entity"', text)), 1)
        parse_clausewitz(text)
        parse_clausewitz((ROOT / "gfx/entities/mapitems_custom.asset").read_text())


if __name__ == "__main__":
    unittest.main()
