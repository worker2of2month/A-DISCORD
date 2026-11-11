"""Contracts that catch map leakage, destructive regeneration and frame drift."""

from __future__ import annotations

import importlib.util
from contextlib import redirect_stdout
import hashlib
import io
import re
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

from tools.validators.validate_adiscord_division_templates import parse_clausewitz


ROOT = Path(__file__).resolve().parents[2]
MODULE = "tools.builders.build_adiscord_vorkerland_capital_map"


def named_blocks(source):
    blocks = {}

    def visit(entries):
        for entry in entries:
            if isinstance(entry.value, list):
                fields = {child.key: child.value for child in entry.value}
                if "name" in fields:
                    blocks[fields["name"]] = fields
                visit(entry.value)

    visit(parse_clausewitz(source))
    return blocks


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

    def test_district_selection_and_actions_keep_native_decisions_authoritative(self):
        self.assertTrue(hasattr(self.builder, 'interaction_sections'))
        effects, triggers = self.builder.interaction_sections()
        for state in range(32, 41):
            self.assertIn(f'WRK_capital_{state}_select_click', effects)
            self.assertIn(f'WRK_capital_{state}_detail_visible', triggers)
            self.assertIn(f'WRK_capital_{state}_selected_visible', triggers)
        self.assertNotIn('add_political_power', effects)
        self.assertNotIn('complete_effect', effects)
        self.assertNotIn('every_country', triggers)
        for state in range(32, 40):
            self.assertIn(f'target = {state} decision = WRK_issue_capital_rations', effects)
            self.assertIn(f'target = {state} decision = WRK_cell_plant', effects)
        self.assertNotIn('target = 40 decision', effects)
        self.assertIn('has_political_power < 35', triggers)
        self.assertIn('WRK_unrest_measure_recent', triggers)
        self.assertIn('WRK_cells_work_free = yes', triggers)

    def test_selection_hitmaps_share_the_disjoint_tooltip_areas(self):
        for state in range(32, 41):
            self.assertIn(f'WRK_capital_select_{state}.png', self.images)
            strip = self.images[f'WRK_capital_select_{state}.png']
            mask = np.asarray(self.images[f'WRK_capital_hit_{state}.png'].getchannel('A')) > 0
            for frame in range(3):
                alpha = np.asarray(strip.crop((frame * 330, 0, (frame + 1) * 330, 290)).getchannel('A'))
                np.testing.assert_array_equal(alpha > 0, mask)
        self.assertEqual(self.images['WRK_capital_panel.png'].getpixel((0, 0))[3], 0)

    def test_action_guards_preserve_every_native_condition_and_recheck_on_click(self):
        from tools.tests.test_vorkerland_preparation import fields, parse

        effects, triggers = self.builder.interaction_sections()
        handlers = fields(parse(effects))
        guards = fields(parse(triggers))
        categories = fields(parse((ROOT / self.builder.DECISIONS).read_text(encoding='utf-8-sig')))
        decisions = {key: fields(body) for category in categories.values()
                     for key, _, body in category if isinstance(body, list)}

        def bind(entries, state):
            return [(str(state) if key == 'FROM' else key, operator,
                     bind(value, state) if isinstance(value, list) else str(state) if value == 'FROM' else value)
                    for key, operator, value in entries]

        for state in range(32, 40):
            for decision, _, _, _ in self.builder.ACTIONS:
                original = decisions[decision]
                expected = bind(original.get('visible', []) + original.get('target_trigger', [])
                                + original.get('available', []), state)
                expected += [('NOT', '=', [('has_political_power', '<', original['cost'])])]
                name = f'WRK_capital_{state}_{decision}'
                self.assertEqual(guards[name + '_click_enabled'], expected, name)
                handler = fields(fields(handlers[name + '_click'])['if'])
                self.assertEqual(handler['limit'], parse(self.builder.selection_condition(state)) + expected)
                self.assertEqual(fields(handler['activate_targeted_decision']),
                                 {'target': str(state), 'decision': decision})

    def test_native_click_binding_and_topmost_input_layers(self):
        from tools.tests.test_vorkerland_preparation import fields, parse

        effects, triggers = self.builder.interaction_sections()
        effects, triggers = fields(parse(effects)), fields(parse(triggers))
        gui = self.builder.gui_block(self.geometry)
        last_marker = max(gui.index(f'name = "WRK_capital_{state}_marker"') for state in range(32, 41))
        for state in range(32, 41):
            for suffix in ('select', 'marker_select'):
                name = f'WRK_capital_{state}_{suffix}'
                self.assertEqual(fields(fields(effects[name + '_click'])['set_variable']),
                                 {'var': 'WRK_capital_selected_state', 'value': str(state)})
                self.assertEqual(triggers[name + '_click_enabled'], [('always', '=', 'yes')])
                self.assertGreater(gui.index(f'name = "{name}"'), last_marker)
        self.assertFalse(any(name.endswith('_enable') for name in triggers))
        for n in range(1, 4):
            self.assertEqual(triggers[f'WRK_capital_legend_text_{n}_visible'], [('always', '=', 'no')])

    def test_legend_is_hidden_and_help_is_not_an_empty_variable(self):
        from tools.tests.test_vorkerland_preparation import fields, parse

        panels = fields(fields(parse(self.builder.interaction_gui().decode('utf-8')))['scripted_gui'])
        triggers = fields(fields(panels['ADISCORD_vorkerland_capital_panel'])['triggers'])
        for n in range(1, 4):
            self.assertIn(('always', '=', 'no'), triggers[f'WRK_capital_legend_icon_{n}_visible'])
        for language in ('russian', 'english'):
            _, data = self.builder.interaction_localisation(language)
            self.assertNotIn('[?]', data.decode('utf-8-sig'))
            self.assertEqual(data.count(b'$WRK_capital_symbols_tt$'), 0)
            text = data.decode('utf-8-sig')
            symbols = re.search(r'(?m)^ WRK_capital_symbols_tt:0 "(.*)"$', text)[1]
            for state in range(32, 41):
                tooltip = re.search(rf'(?m)^ WRK_capital_{state}_tt:0 "(.*)"$', text)[1]
                self.assertTrue(tooltip.endswith('\\n\\n' + symbols))
                self.assertEqual(tooltip.count(symbols), 1)

    def test_default_check_never_writes_and_apply_is_idempotent(self):
        def snapshot(root):
            return {p.relative_to(root): (hashlib.sha256(p.read_bytes()).hexdigest(), p.stat().st_mtime_ns)
                    for p in root.rglob('*') if p.is_file()}

        with tempfile.TemporaryDirectory(prefix="adiscord-capital-test-") as directory:
            root = Path(directory)
            sources = [ROOT / 'map/provinces.bmp', ROOT / 'map/definition.csv',
                       ROOT / 'interface/ADISCORD_vorkerland.gui', ROOT / 'interface/ADISCORD_vorkerland.gfx',
                       ROOT / self.builder.SGUI, ROOT / self.builder.DECISIONS,
                       ROOT / 'gfx/interface/decisions/ui/ADISCORD_decisions_category_desc_tile.dds',
                       ROOT / 'localisation/russian/ADISCORD_vorkerland_l_russian.yml',
                       ROOT / 'localisation/english/ADISCORD_vorkerland_l_english.yml']
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

    def test_hit_silhouettes_cover_every_state_pixel_without_overlap(self):
        coverage = np.zeros((290, 330), dtype=np.uint8)
        tower_hit = np.asarray(self.images["WRK_capital_hit_40.png"].getchannel("A")) > 0
        for state in range(32, 41):
            name = f"WRK_capital_hit_{state}.png"
            self.assertIn(name, self.images)
            image = self.images[name]
            self.assertEqual(image.size, (330, 290))
            alpha = np.asarray(image.getchannel("A"))
            expected = np.asarray(self.geometry["masks"][state]) > 0
            if state == 40:
                self.assertTrue(np.all(tower_hit[expected]))
            else:
                np.testing.assert_array_equal(alpha > 0, expected & ~tower_hit)
            self.assertLessEqual(int(alpha.max()), 16)
            coverage += alpha > 0
        self.assertLessEqual(int(coverage.max()), 1)

    def test_tower_hit_covers_icon_and_two_pixel_margin(self):
        x, y = self.geometry["anchors"][40]
        hit = np.asarray(self.images["WRK_capital_hit_40.png"].getchannel("A")) > 0
        # The visible tower backing spans x-17..x-7, y-27..y-7 inclusive.
        self.assertTrue(np.all(hit[y - 29:y - 4, x - 19:x - 4]))
        self.assertTrue(hit[y, x])

    def test_hover_bindings_and_pass_through_layers(self):
        source = self.builder.gui_block(self.geometry)
        gui = named_blocks(source)
        gfx = named_blocks(self.builder.gfx_block(self.images))
        hits = {name for name in gui if name.endswith("_hit")}
        self.assertEqual(hits, {f"WRK_capital_{state}_hit" for state in range(32, 41)})
        last_hit = max(source.index(f'name = "{name}"') for name in hits)
        background = source.index('name = "WRK_capital_map"')
        tooltip_bindings = {}
        for state in range(32, 41):
            tooltip = f"WRK_capital_{state}_tt"
            for suffix in ("hit", "marker"):
                name = f"WRK_capital_{state}_{suffix}"
                tooltip_bindings[name] = tooltip
                self.assertNotEqual(gui[name].get("alwaystransparent"), "yes")
            hit = gui[f"WRK_capital_{state}_hit"]
            self.assertEqual({p.key: p.value for p in hit["position"]}, {"x": "65", "y": "48"})
            self.assertEqual(hit["quadTextureSprite"], f"GFX_WRK_capital_hit_{state}")
            sprite = gfx[hit["quadTextureSprite"]]
            self.assertEqual(sprite["noOfFrames"], "1")
            self.assertEqual(sprite["transparencecheck"], "yes")
            self.assertLess(background, source.index(f'name = "WRK_capital_{state}_hit"'))
            self.assertLess(last_hit, source.index(f'name = "WRK_capital_{state}_state"'))
            self.assertEqual(gui[f"WRK_capital_{state}_state"]["alwaystransparent"], "yes")
        self.assertEqual(gui["WRK_capital_route"]["alwaystransparent"], "yes")
        for number in range(1, 7):
            prefix = f"WRK_intrigue_{number}"
            tooltip_bindings[prefix + "_card"] = prefix + "_tt"
            self.assertNotEqual(gui[prefix + "_card"].get("alwaystransparent"), "yes")
            for suffix in ("portrait", "name", "status"):
                self.assertEqual(gui[prefix + "_" + suffix]["alwaystransparent"], "yes")
        actual = {name: block["pdx_tooltip"] for name, block in gui.items() if "pdx_tooltip" in block}
        for name, key in tooltip_bindings.items():
            self.assertEqual(actual[name], key)
        for state in range(32, 41):
            for suffix in ('select', 'marker_select', 'detail'):
                self.assertEqual(actual[f'WRK_capital_{state}_{suffix}'], f'WRK_capital_{state}_tt')


if __name__ == "__main__":
    unittest.main()
