"""Western-country boundaries, closed diplomacy and localized message animation."""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from PIL import Image, ImageChops

from tools.builders import build_adiscord_outer_states as geography
from tools.builders import build_adiscord_western_diplomacy_assets as assets
from tools.validators.validate_adiscord_division_templates import parse_clausewitz

ROOT = Path(__file__).resolve().parents[2]
CLOSED = {"RSV"}


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8-sig")


class WesternContinentTests(unittest.TestCase):
    def test_country_capitals_and_state_partition_match_generated_history(self):
        source = geography.western_source()
        self.assertEqual(set(source["countries"]), CLOSED)
        self.assertEqual(geography.check_western_outputs(), [])
        states = source["states"]
        assigned = []
        for state_id, row in states.items():
            self.assertIn(row["owner"], CLOSED)
            self.assertIn(row["anchor"], row["provinces"])
            assigned.extend(row["provinces"])
        self.assertEqual(len(assigned), len(set(assigned)))
        other_provinces = set()
        for path in (ROOT / "history/states").glob("*.txt"):
            state_id, provinces, _ = geography.parse_state(path)
            if str(state_id) not in states:
                other_provinces.update(provinces)
        self.assertFalse(set(assigned) & other_provinces)
        for tag, country in source["countries"].items():
            capital = country["capital"]
            self.assertEqual(states[str(capital)]["owner"], tag)
            histories = list((ROOT / "history/countries").glob(f"{tag} - *.txt"))
            self.assertEqual(len(histories), 1)
            text = histories[0].read_text(encoding="utf-8")
            self.assertRegex(text, rf"\bcapital\s*=\s*{capital}\b")
            self.assertNotRegex(text, r"\b(oob|recruit_character|create_country_leader)\s*=")

    def test_diplomacy_guards_are_symmetric_and_preserve_other_countries(self):
        definitions = {
            entry.key: entry.value
            for entry in parse_clausewitz(read("common/scripted_triggers/ADISCORD_dirty_zone_triggers.txt"))
        }

        def evaluate(items, current, root, sender):
            def match(entry):
                key, value = entry.key, entry.value
                if key == "original_tag":
                    return current == value
                if key == "ROOT":
                    return evaluate(value, root, root, sender)
                if key == "FROM":
                    return evaluate(value, sender, root, sender)
                if key == "OR":
                    return any(match(child) for child in value)
                if key == "NOT":
                    return not all(match(child) for child in value)
                if key in definitions:
                    return evaluate(definitions[key], current, root, sender) == (value == "yes")
                raise AssertionError(f"Unexpected predicate: {key}")

            return all(match(entry) for entry in items)

        for initiator in (*CLOSED, "DAN", "STP", "EXZ"):
            for target in (*CLOSED, "DAN", "STP", "EXZ"):
                with self.subTest(initiator=initiator, target=target):
                    self.assertEqual(
                        evaluate(definitions["ADISCORD_diplomacy_not_dirty_zone_pair"], target, initiator, initiator),
                        not ({initiator, target} & (CLOSED | {"EXZ"})),
                    )
                    self.assertEqual(
                        evaluate(definitions["ADISCORD_western_diplomacy_pair_open"], initiator, initiator, target),
                        not ({initiator, target} & CLOSED),
                    )
        native = {
            entry.key: entry.value
            for entry in parse_clausewitz(read("common/scripted_triggers/diplomacy_scripted_triggers.txt"))
        }
        for action in ("WAR", "EMBARGO", "REVOKE_EMBARGO", "CANCEL_FOREIGN_MANPOWER", "CANCEL_GENERATE_WARGOAL", "LEND_LEASE_CANCEL", "LEND_LEASE_EXISTING", "CALL_ALLY"):
            entries = native[f"DIPLOMACY_{action}_ENABLE_TRIGGER"]
            self.assertTrue(any(entry.key == "ADISCORD_western_diplomacy_pair_open" and entry.value == "yes" for entry in entries))

    def test_english_terminal_uses_opaque_frames_and_holds_complete_message(self):
        gui = read("interface/ADISCORD_western_continent.gui")
        gfx = read("interface/ADISCORD_western_continent.gfx")
        self.assertNotIn("terminal_line_", gui)
        self.assertNotIn("terminal_reveal", gui)
        self.assertIn('name = "terminal_display"', gui)
        self.assertIn(f"noOfFrames = {assets.FRAME_COUNT}", gfx)
        self.assertIn(
            f"size = {{ width = {assets.FRAME_SIZE[0]} height = {assets.FRAME_SIZE[1]} }}",
            gui,
        )
        self.assertTrue(all(text.isascii() for _, text, _ in assets.TERMINAL_MESSAGES))
        with Image.open(assets.OUTPUT / "reservation_terminal.dds") as texture:
            atlas = texture.convert("RGBA")
        width, height = assets.FRAME_SIZE
        self.assertEqual(atlas.size, (width * assets.FRAME_COUNT, height))
        self.assertEqual(atlas.getchannel("A").getextrema(), (255, 255))
        frames = [
            atlas.crop((index * width, 0, (index + 1) * width, height))
            for index in range(assets.FRAME_COUNT)
        ]
        # All four transmissions remain visible for nine seconds. Only the
        # cursor blinks; DXT alignment must not make stationary glyphs shimmer.
        for index in range(8, assets.FRAME_COUNT):
            reference = frames[8 + index % 2]
            difference = ImageChops.difference(reference, frames[index]).convert("RGB")
            self.assertIsNone(difference.getbbox())
        for index in range(1, 9):
            difference = ImageChops.difference(frames[index - 1], frames[index])
            self.assertIsNotNone(difference.convert("RGB").getbbox())
        # The broad gaps between messages must be a single uninterrupted color.
        for frame in frames:
            for box in ((0, 125, width, 264), (0, 405, width, height)):
                for low, high in frame.crop(box).getextrema():
                    self.assertEqual(low, high)
        for path, expected in assets.terminal_outputs().items():
            self.assertEqual(path.read_bytes(), expected, path)

    def test_main_dossier_remains_localized_in_both_languages(self):
        gui = read("interface/ADISCORD_western_continent.gui")
        for language in ("russian", "english"):
            path = ROOT / f"localisation/{language}/ADISCORD_western_continent_l_{language}.yml"
            self.assertTrue(path.read_bytes().startswith(b"\xef\xbb\xbf"))
            text = path.read_text(encoding="utf-8-sig")
            for key in re.findall(r'text\s*=\s*"([A-Z0-9_]+)"', gui):
                self.assertRegex(text, rf'(?m)^ {key}:0? "[^"\r\n]+"$')
            self.assertNotIn("ADISCORD_RESERVATION_TERMINAL_", text)


if __name__ == "__main__":
    unittest.main()
