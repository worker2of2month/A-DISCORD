import re
import unittest
from pathlib import Path

from PIL import Image

from tools.validators.validate_adiscord_division_templates import parse_clausewitz


ROOT = Path(__file__).resolve().parents[2]
IDEAS_PATH = ROOT / "common" / "ideas" / "_economic.txt"
GFX_PATH = ROOT / "interface" / "ADISCORD_ideas.gfx"
TRIGGERS_PATH = ROOT / "common" / "scripted_triggers" / "ADISCORD_economy_triggers.txt"
EFFECTS_PATH = ROOT / "common" / "scripted_effects" / "ADISCORD_economy_effects.txt"
RU_LOC_PATH = ROOT / "localisation" / "russian" / "ADISCORD_economy_l_russian.yml"
EN_LOC_PATH = ROOT / "localisation" / "english" / "ADISCORD_economy_l_english.yml"

SYSTEM_SUFFIXES = (
    "agrarian",
    "industrializing",
    "free_market",
    "mixed",
    "state_coordinated",
    "planned_bureaucratic",
    "syndicalist",
    "oligarchic_clan",
    "technocratic",
)
SYSTEM_IDS = tuple(f"ADISCORD_economic_system_{suffix}" for suffix in SYSTEM_SUFFIXES)
EXPECTED_TEXTURES = {
    system_id: f"gfx/interface/ideas/laws/economic_system/{system_id}.png"
    for system_id in SYSTEM_IDS
}


def unique_child(entries, key):
    matches = [entry for entry in entries if entry.key == key]
    if len(matches) != 1 or not isinstance(matches[0].value, list):
        raise AssertionError(f"expected one block {key}, found {len(matches)}")
    return matches[0].value


def scalar(entries, key):
    matches = [
        entry.value
        for entry in entries
        if entry.key == key and isinstance(entry.value, str)
    ]
    if len(matches) != 1:
        raise AssertionError(f"expected one scalar {key}, found {len(matches)}")
    return matches[0]


def block(text, name):
    match = re.search(rf"(?m)^\s*{re.escape(name)}\s*=\s*\{{", text)
    if not match:
        raise AssertionError(f"missing block: {name}")
    opening = text.find("{", match.start())
    depth = 0
    for index in range(opening, len(text)):
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
            if depth == 0:
                return text[opening + 1 : index]
    raise AssertionError(f"unclosed block: {name}")


def localisation_value(text, key):
    match = re.search(rf'(?m)^\s*{re.escape(key)}:\d*\s+"([^"]*)"', text)
    if not match:
        raise AssertionError(f"missing localisation key: {key}")
    return match.group(1)


class EconomicSystemLawContracts(unittest.TestCase):
    def test_economic_system_sprites_resolve_to_dedicated_pngs(self):
        parsed = parse_clausewitz(GFX_PATH.read_text(encoding="utf-8-sig"))
        sprite_types = unique_child(parsed, "spriteTypes")
        actual = {}
        for entry in sprite_types:
            if entry.key != "spriteType" or not isinstance(entry.value, list):
                continue
            name = scalar(entry.value, "name")
            if name.startswith("GFX_idea_ADISCORD_economic_system_"):
                system_id = name.removeprefix("GFX_idea_")
                actual[system_id] = scalar(entry.value, "texturefile")

        self.assertEqual(EXPECTED_TEXTURES, actual)
        for system_id, relative_path in EXPECTED_TEXTURES.items():
            with self.subTest(system_id=system_id), Image.open(
                ROOT / relative_path
            ) as image:
                self.assertEqual("PNG", image.format)
                self.assertEqual((64, 64), image.size)
                self.assertIn("A", image.getbands())


if __name__ == "__main__":
    unittest.main()
