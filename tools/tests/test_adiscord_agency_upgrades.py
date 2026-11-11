"""Agency upgrades preserve native bonuses while using mod technologies and artwork."""

import hashlib
import json
from pathlib import Path
import re
import unittest

from PIL import Image

from tools.validators.validate_adiscord_division_templates import parse_clausewitz
from tools.tests.test_adiscord_intelligence_ui import named_block


ROOT = Path(__file__).resolve().parents[2]
NATIVE = Path(r"Z:/SteamLibrary/steamapps/common/Hearts of Iron IV")
CATALOGUE = "common/intelligence_agency_upgrades/intelligence_agency_upgrades.txt"


def entries(path):
    return parse_clausewitz(path.read_text(encoding="utf-8-sig"))


def upgrades(root):
    return {upgrade.key: upgrade.value for branch in entries(root / CATALOGUE) for upgrade in branch.value}


def canonical(items):
    return [(item.key, canonical(item.value) if isinstance(item.value, list) else item.value) for item in items]


class AgencyUpgradeTests(unittest.TestCase):
    def test_native_mechanics_with_field_radio_network_bonus(self):
        native = upgrades(NATIVE)
        actual = upgrades(ROOT)
        self.assertEqual(len(actual), 21)
        self.assertEqual(set(native), set(actual))
        for key, source in native.items():
            def mechanics(block):
                return [item for item in block if item.key in {"modifier", "modifiers_during_progress", "level"}]
            source_mechanics = mechanics(source)
            actual_mechanics = mechanics(actual[key])
            # This total conversion has no native local-recruitment decision category.
            for block in (source_mechanics, actual_mechanics):
                for item in block:
                    if item.key == "level":
                        item.value[:] = [child for child in item.value if child.key != "complete_effect"]
            expected = canonical(source_mechanics)
            if key == "upgrade_portable_radios":
                expected = [
                    (name, [("modifier", [("intel_network_gain_factor", "0.2")])])
                    if name == "level" else (name, value)
                    for name, value in expected
                ]
            self.assertEqual(expected, canonical(actual_mechanics), key)

    def test_requirements_reference_existing_mod_technologies(self):
        techs = {entry.key for path in (ROOT / "common/technologies").glob("*.txt")
                 for group in entries(path) if isinstance(group.value, list) for entry in group.value}
        def check(block):
            for entry in block:
                if entry.key == "has_tech":
                    self.assertIn(entry.value, techs)
                elif isinstance(entry.value, list):
                    check(entry.value)
        for block in upgrades(ROOT).values():
            check(block)

    def test_art_is_unique_transparent_and_fits_native_card(self):
        manifest = json.loads((ROOT / "tools/assets/source/intelligence_upgrades/upgrade_art_prompts.json").read_text(encoding="utf-8"))
        records = manifest["assets"]
        self.assertEqual(len(records), 21)
        self.assertEqual(len({row["runtime_sha256"] for row in records}), 21)
        for row in records:
            path = ROOT / row["runtime_file"]
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), row["runtime_sha256"])
            with Image.open(path) as image:
                self.assertEqual(image.size, (168, 70))
                self.assertEqual(image.mode, "RGBA")
                self.assertEqual(hashlib.sha256(image.tobytes()).hexdigest(), row["runtime_rgba_sha256"])
                self.assertEqual(image.getchannel("A").getextrema(), (0, 255))
                left, top, right, bottom = image.getchannel("A").getbbox()
                self.assertGreaterEqual(left, 4)
                self.assertLessEqual(right, 164)
                self.assertGreaterEqual(top, 0)
                self.assertLessEqual(bottom, 54)

    def test_catalogue_icons_resolve_to_the_recorded_exports(self):
        manifest = json.loads((ROOT / "tools/assets/source/intelligence_upgrades/upgrade_art_prompts.json").read_text(encoding="utf-8"))
        sprites = {}
        for group in entries(ROOT / "interface/ADISCORD_intelligence_upgrades.gfx"):
            for sprite in group.value:
                fields = {field.key.lower(): field.value for field in sprite.value}
                self.assertNotIn(fields["name"], sprites)
                sprites[fields["name"]] = fields["texturefile"]
        catalogue = upgrades(ROOT)
        self.assertEqual({row["native_id"] for row in manifest["assets"]}, set(catalogue))
        for row in manifest["assets"]:
            picture = next(item.value for item in catalogue[row["native_id"]] if item.key == "picture")
            self.assertEqual(sprites[picture], row["runtime_file"])

    def test_icon_content_stops_above_upgrade_name(self):
        gui = (ROOT / "interface/countryintelligenceagencyview.gui").read_text(encoding="utf-8")
        card = named_block(gui, "containerWindowType", "upgrade_entry")
        icon = named_block(card, "buttonType", "upgrade_icon")
        label = named_block(card, "instantTextboxType", "upgrade_name")
        icon_x, icon_y = map(int, re.search(r"position\s*=\s*\{\s*x\s*=\s*(-?\d+)\s*y\s*=\s*(-?\d+)", icon).groups())
        label_y = int(re.search(r"position\s*=\s*\{\s*x\s*=\s*-?\d+\s*y\s*=\s*(-?\d+)", label)[1])
        self.assertEqual(icon_x, 10)
        self.assertEqual(icon_y, -13)
        levels = named_block(card, "OverlappingElementsBoxType", "repetitions_icons")
        levels_y = int(re.search(r"position\s*=\s*\{\s*x\s*=\s*-?\d+\s*y\s*=\s*(-?\d+)", levels)[1])
        label_height = int(re.search(r"maxHeight\s*=\s*(\d+)", label)[1])
        self.assertLessEqual(label_y + label_height, levels_y)
        for path in (ROOT / "gfx/interface/intelligence/upgrades").glob("*.dds"):
            with Image.open(path) as image:
                self.assertLessEqual(icon_y + image.getchannel("A").getbbox()[3], label_y, path.name)

    def test_localisation_has_all_names_and_descriptions(self):
        for language in ("russian", "english"):
            path = ROOT / f"localisation/replace/ADISCORD_intelligence_upgrades_l_{language}.yml"
            self.assertTrue(path.read_bytes().startswith(b"\xef\xbb\xbf"))
            text = path.read_text(encoding="utf-8-sig")
            for key in upgrades(ROOT):
                for token in (key, f"{key}_desc"):
                    matches = re.findall(rf'^ {re.escape(token)}:(?:\d+)?\s+"(?:[^"\\\r\n]|\\.)+"\s*$', text, re.MULTILINE)
                    self.assertEqual(len(matches), 1, token)


if __name__ == "__main__":
    unittest.main()
