"""Political map geometry, owner bindings and native status boundary contracts."""

from __future__ import annotations

from dataclasses import replace
import importlib.util
import unittest
from pathlib import Path

import numpy as np

from tools.tests.test_adiscord_stp_preparation import block, scalar, selected_effects
from tools.tests.test_build_adiscord_vorkerland_capital_map import named_blocks
from tools.validators.validate_adiscord_division_templates import parse_clausewitz


ROOT = Path(__file__).resolve().parents[2]
MODULE = "tools.builders.build_adiscord_west_influence_map"
REGIONAL = ("PWR", "PSD", "ZAO", "WIT", "IIA", "IBA", "IBL", "WPA", "WPS", "ROM", "TRU")


class WestInfluenceMapTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if importlib.util.find_spec(MODULE):
            from tools.builders import build_adiscord_west_influence_map as builder

            cls.builder = builder
            cls.images, cls.geometry = builder.render_images()

    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec(MODULE), "western political map builder missing")

    def test_state_masks_are_disjoint_and_all_frames_can_be_hovered(self):
        coverage = np.zeros((300, 436), dtype=np.uint8)
        for state, info in self.geometry["states"].items():
            x, y, right, bottom = info["box"]
            width, height = right - x, bottom - y
            image = self.images[f"state_{state}.png"]
            self.assertEqual(image.size, (width * 8, height))
            mask = np.asarray(info["mask"]) > 0
            coverage += mask
            for frame in range(8):
                alpha = np.asarray(image.crop((frame * width, 0, (frame + 1) * width, height)).getchannel("A"))
                np.testing.assert_array_equal(alpha > 0, mask[y:bottom, x:right])
        self.assertEqual(int(coverage.max()), 1)
        self.assertTrue({90, 91, 93, 94, 194, 195, 196, 322, 328} <= set(self.geometry["states"]))

    def test_each_state_reads_its_current_owner_and_every_country_has_a_tooltip(self):
        source = self.builder.scripted_gui(self.geometry)
        gui = named_blocks(self.builder.gui_block(self.geometry))
        for state in self.geometry["states"]:
            name = f"ADISCORD_west_map_state_{state}"
            self.assertEqual(gui[name]["pdx_tooltip"], name + "_tt")
            trigger = block(block(block(parse_clausewitz(source), "scripted_gui"), "ADISCORD_west_influence_panel"), "triggers")
            body = block(trigger, name + "_visible")
            owner = block(block(body, str(state)), "owner")
            self.assertEqual(scalar(owner, "ADISCORD_west_map_set_country_frame"), "yes")
        for tag in REGIONAL:
            self.assertEqual(gui[f"ADISCORD_west_map_country_{tag}"]["pdx_tooltip"], f"ADISCORD_west_map_{tag}_tt")
        self.assertNotIn("every_country", source)
        self.assertNotIn("dirty =", source)

    def country_frame(self, tag="PWR", lean=0, **options):
        definitions = {entry.key: entry.value for entry in parse_clausewitz(
            (ROOT / "common/scripted_triggers/ADISCORD_west_final_war_triggers.txt").read_text(encoding="utf-8-sig"))}

        def expand(entries):
            result = []
            for entry in entries:
                if isinstance(entry.value, str) and entry.value in ("yes", "no") and entry.key in definitions:
                    result.append(replace(entry, key="AND" if entry.value == "yes" else "NOT", value=expand(definitions[entry.key])))
                elif isinstance(entry.value, list):
                    result.append(replace(entry, value=expand(entry.value)))
                else:
                    result.append(entry)
            return result

        facts = {
            ("event_target", "ADISCORD_vorkerland_nation"): options.get("successor", "WKR"),
            (tag, "exists", "yes"): options.get("exists", True),
            (tag, "exists", "no"): not options.get("exists", True),
            (tag, "is_subject", "yes"): options.get("subject", False),
            (tag, "has_country_flag", "ADISCORD_west_neutral"): options.get("neutral", False),
            (tag, "variable", "ADISCORD_west_lean"): lean,
            (tag, "variable", "ADISCORD_west_side"): options.get("side", 0),
        }
        body = block(parse_clausewitz(self.builder.frame_trigger()), "ADISCORD_west_map_set_country_frame")
        frame = None
        for _, entry in selected_effects(expand(body), facts, tag):
            self.assertEqual(entry.key, "set_temp_variable")
            self.assertEqual(scalar(entry.value, "var"), "ADISCORD_west_map_frame")
            frame = int(scalar(entry.value, "value"))
        return frame

    def test_exact_thresholds_and_priority_match_the_existing_status(self):
        for lean, frame in ((-100, 6), (-50, 6), (-49, 5), (-20, 5), (-19, 2),
                            (0, 2), (19, 2), (20, 3), (49, 3), (50, 4), (100, 4)):
            self.assertEqual(self.country_frame(lean=lean), frame, lean)
        self.assertEqual(self.country_frame(lean=100, neutral=True), 7)
        self.assertEqual(self.country_frame(lean=100, subject=True), 8)
        self.assertEqual(self.country_frame(lean=100, subject=True, neutral=True), 7)
        self.assertEqual(self.country_frame(lean=-100, subject=True, neutral=True, side=1), 4)
        self.assertEqual(self.country_frame(lean=100, side=2), 6)
        self.assertEqual(self.country_frame(lean=100, exists=False), 1)
        for tag in ("WKR", "VAD", "TVA"):
            self.assertEqual(self.country_frame(tag=tag, successor=tag), 4)
        self.assertEqual(self.country_frame(tag="IVN"), 6)
        self.assertEqual(self.country_frame(tag="NAM", lean=100), 1)


if __name__ == "__main__":
    unittest.main()
