"""Contracts that catch map leakage, destructive regeneration and frame drift."""

from __future__ import annotations

import importlib.util
from contextlib import redirect_stdout
import hashlib
import io
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np


ROOT = Path(__file__).resolve().parents[2]
MODULE = "tools.builders.build_adiscord_vorkerland_capital_map"


class CapitalMapTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if importlib.util.find_spec(MODULE) is not None:
            from tools.builders import build_adiscord_vorkerland_capital_map

            cls.builder = build_adiscord_vorkerland_capital_map
            cls.images, cls.geometry = cls.builder.render_images()

    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec(MODULE), "capital builder missing")

    def test_empty_frames_and_strip_dimensions(self):
        for state in (32, 33, 34, 35, 36, 37, 38, 39, 40):
            strip = self.images[f"WRK_capital_state_{state}.png"]
            self.assertEqual(strip.size, (1980, 290))
            self.assertIsNone(strip.crop((0, 0, 330, 290)).getbbox())
        for name, width, height, frames in (
            ("WRK_capital_marker", 28, 28, 6),
            ("WRK_capital_route", 330, 290, 3),
        ):
            strip = self.images[name + ".png"]
            self.assertEqual(strip.size, (width * frames, height))
            self.assertIsNone(strip.crop((0, 0, width, height)).getbbox())
            for frame in range(1, frames):
                self.assertIsNotNone(strip.crop((width * frame, 0, width * (frame + 1), height)).getbbox())
        self.assertEqual(self.images["WRK_intrigue_card.png"].size, (660, 100))

    def test_highlights_only_touch_streets_in_their_own_state(self):
        for state in (32, 33, 34, 35, 36, 37, 38, 39, 40):
            strip = self.images[f"WRK_capital_state_{state}.png"]
            mask = np.asarray(self.geometry["masks"][state]) > 0
            for frame in range(1, 6):
                alpha = np.asarray(strip.crop((330 * frame, 0, 330 * (frame + 1), 290)))[:, :, 3]
                self.assertFalse(np.any(alpha[~mask]), f"state {state}, frame {frame + 1} leaks")
                self.assertGreater(np.count_nonzero(alpha), 0)
                self.assertLess(np.count_nonzero(alpha > 180), np.count_nonzero(mask) * 0.5)

    def test_routes_start_at_tower_and_visit_different_districts(self):
        routes = self.geometry["routes"]
        tower = self.geometry["anchors"][40]
        visited = []
        for points in routes:
            self.assertEqual(points[0], tower)
            x, y = points[-1]
            self.assertTrue(x <= 12 or x >= 317 or y <= 12 or y >= 277)
            states = set()
            for x, y in points:
                for state, mask in self.geometry["masks"].items():
                    if mask.getpixel((round(x), round(y))):
                        states.add(state)
            self.assertIn(40, states)
            self.assertGreaterEqual(len(states), 3)
            visited.append(states)
        self.assertNotEqual(*visited)

    def test_generated_section_preserves_unowned_bytes_and_is_idempotent(self):
        source = b'guiTypes = {\r\n\t# user window\r\n}\r\n'
        updated = self.builder.replace_section(source, '\tcontainerWindowType = {\n\t}\n')
        self.assertTrue(updated.startswith(source[:-3]))
        self.assertTrue(updated.endswith(b'}\r\n'))
        self.assertEqual(updated, self.builder.replace_section(updated, '\tcontainerWindowType = {\n\t}\n'))
        with self.assertRaises(ValueError):
            self.builder.replace_section(updated + updated, '')

    def test_gui_layer_order_and_contract(self):
        gui = self.builder.gui_block(self.geometry)
        route = gui.index('name = "WRK_capital_route"')
        for state in (32, 33, 34, 35, 36, 37, 38, 39, 40):
            self.assertLess(gui.index(f'name = "WRK_capital_{state}_state"'), route)
            self.assertGreater(gui.index(f'name = "WRK_capital_{state}_marker"'), route)
        for n in range(1, 7):
            for part in ('card', 'portrait', 'name', 'status'):
                self.assertEqual(gui.count(f'name = "WRK_intrigue_{n}_{part}"'), 1)

    def test_default_check_never_writes_and_apply_is_idempotent(self):
        def snapshot(root):
            return {p.relative_to(root): (hashlib.sha256(p.read_bytes()).hexdigest(), p.stat().st_mtime_ns)
                    for p in root.rglob('*') if p.is_file()}

        with tempfile.TemporaryDirectory(prefix="adiscord-capital-test-") as directory:
            root = Path(directory)
            sources = [ROOT / 'map/provinces.bmp', ROOT / 'map/definition.csv',
                       ROOT / 'interface/ADISCORD_vorkerland.gui', ROOT / 'interface/ADISCORD_vorkerland.gfx']
            for state in (32, 33, 34, 35, 36, 37, 38, 39, 40):
                sources.extend((ROOT / 'history/states').glob(f'{state}-*.txt'))
            for source in sources:
                target = root / source.relative_to(ROOT)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, target)
            sentinel = root / 'gfx/interface/vorkerland_capital/keep.txt'
            sentinel.parent.mkdir(parents=True)
            sentinel.write_bytes(b'owned by another author')
            before = snapshot(root)
            with patch.object(self.builder, 'ROOT', root), redirect_stdout(io.StringIO()):
                self.assertEqual(self.builder.main([]), 1)
                self.assertEqual(snapshot(root), before)
                self.assertEqual(self.builder.main(['--apply']), 0)
                applied = snapshot(root)
                self.assertEqual(self.builder.main(['--check']), 0)
                self.assertEqual(self.builder.main(['--apply']), 0)
                self.assertEqual(snapshot(root), applied)
            self.assertEqual(sentinel.read_bytes(), b'owned by another author')

    def test_all_nine_markers_fit_without_overlapping(self):
        markers = self.geometry['markers']
        self.assertEqual(set(markers), set(range(32, 41)))
        for state, (x, y) in markers.items():
            self.assertTrue(14 <= x <= 316 and 14 <= y <= 276, state)
            for other, (ox, oy) in markers.items():
                if state < other:
                    self.assertGreaterEqual((x - ox) ** 2 + (y - oy) ** 2, 30 ** 2, (state, other))


if __name__ == "__main__":
    unittest.main()
