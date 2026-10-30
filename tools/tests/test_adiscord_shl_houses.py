"""Static checks for the SHL character registry; the native loader and UI need a fresh game."""

import re
import unittest
from pathlib import Path

from tools.validators.validate_adiscord_division_templates import parse_clausewitz

ROOT = Path(__file__).resolve().parents[2]
CHARACTERS = ROOT / "common/characters/SHL.txt"
SHARED_CHARACTERS = ROOT / "common/characters/ADISCORD_southern_desert_characters.txt"
HISTORY = ROOT / "history/countries/SHL - Shahrabad League.txt"
RUSSIAN = ROOT / "localisation/russian"
STATE_NAMES = {
    "russian": RUSSIAN / "state_names_l_russian.yml",
    "english": ROOT / "localisation/replace/state_names_l_english.yml",
}
HOUSE_HEADS = {
    "SHL_Khosrow_Arbin": "287",
    "SHL_Darius_Safir": "288",
    "SHL_Golshan_Loran": "289",
    "SHL_Kamran_Nur": "290",
    "SHL_Tahmuras_Bayrat": "291",
    "SHL_Fereydun_Kerdan": "292",
    "SHL_Shirin_Sharim": "293",
    "SHL_Rauf_Darban": "294",
    "SHL_Behruz_Veyran": "295",
}
COURSE_HEADS = ("SHL_Mariam_Arbin", "SHL_Rauf_Darban", "SHL_Salima_Darzi", "SHL_Amin_Rashad")
DEFINITION = re.compile(r"^\t(\w+) = \{", re.M)
LOCALISATION_KEY = re.compile(r"^\s+(\S+?):\d*\s+\"", re.M)


def read(path):
    return path.read_text(encoding="utf-8-sig")


def block(items, key):
    return next((e.value for e in items if e.key == key and isinstance(e.value, list)), [])


def scalar(items, key, default=None):
    return next((e.value for e in items if e.key == key), default)


def characters():
    return {entry.key: entry.value for entry in block(parse_clausewitz(read(CHARACTERS)), "characters")}


def sprite_names():
    names = set()
    for path in (ROOT / "interface").glob("*.gfx"):
        names.update(re.findall(r"name\s*=\s*\"(GFX_\w+)\"", read(path)))
    return names


class ShlHouseCharacterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.characters = characters()
        cls.russian_keys = set()
        for path in RUSSIAN.glob("*.yml"):
            cls.russian_keys.update(LOCALISATION_KEY.findall(read(path)))

    def test_every_character_has_a_russian_name(self):
        for name, body in self.characters.items():
            with self.subTest(character=name):
                self.assertIn(scalar(body, "name", name), self.russian_keys)

    def test_shared_southern_file_keeps_no_shl_character(self):
        remaining = [
            name for name in DEFINITION.findall(read(SHARED_CHARACTERS))
            if name.startswith("SHL_") or name.startswith("ADISCORD_staff_SHL_")
        ]
        self.assertEqual(remaining, [])

    def test_every_recruited_character_is_defined_exactly_once(self):
        recruited = re.findall(r"^recruit_character = (\w+)\s*$", read(HISTORY), re.M)
        self.assertTrue(recruited)
        definitions = {}
        for path in (ROOT / "common/characters").glob("*.txt"):
            for name in DEFINITION.findall(read(path)):
                definitions.setdefault(name, []).append(path.name)
        for name in recruited:
            with self.subTest(character=name):
                self.assertEqual(definitions.get(name), ["SHL.txt"])
        self.assertEqual(len(recruited), len(set(recruited)))
        for name in (*HOUSE_HEADS, *COURSE_HEADS):
            self.assertIn(name, recruited)

    def test_house_heads_read_their_own_furnace_state(self):
        for name, state in HOUSE_HEADS.items():
            with self.subTest(character=name):
                advisor = block(self.characters[name], "advisor")
                self.assertTrue(advisor)
                furnace = block(block(advisor, "available"), state)
                self.assertTrue(furnace, state)
                self.assertEqual(scalar(furnace, "is_owned_by"), "SHL")
                checks = {
                    scalar(e.value, "var"): scalar(e.value, "value")
                    for e in furnace if e.key == "check_variable"
                }
                self.assertEqual(checks, {"SHL_furnace_owner": "0", "SHL_furnace_running": "1"})
                other_states = [
                    e.key for e in block(advisor, "available")
                    if e.key.isdigit() and e.key != state
                ]
                self.assertEqual(other_states, [])

    def test_advisor_seats_use_registered_slots_tokens_and_sprites(self):
        slots = set(re.findall(r"slot = (\w+)", read(ROOT / "common/idea_tags/00_idea.txt")))
        sprites = sprite_names()
        tokens = []
        for name, body in self.characters.items():
            portraits = block(body, "portraits")
            for group in portraits:
                for entry in group.value:
                    # Staff icons named GFX_idea_* are inherited from the base game.
                    if entry.value.startswith("GFX_idea_"):
                        continue
                    with self.subTest(character=name, sprite=entry.value):
                        self.assertIn(entry.value, sprites)
            advisor = block(body, "advisor")
            if not advisor:
                continue
            with self.subTest(character=name):
                self.assertIn(scalar(advisor, "slot"), slots)
                tokens.append(scalar(advisor, "idea_token"))
                self.assertEqual(scalar(advisor, "removal_cost"), "0")
                self.assertTrue(any(scalar(group.value, "small") for group in portraits), name)
        self.assertEqual(len(tokens), len(set(tokens)))

    def test_course_heads_keep_their_cabinet_ideas_as_the_course_seat(self):
        ministers = read(ROOT / "common/ideas/ADISCORD_ministers_all_countries.txt")
        for name in COURSE_HEADS:
            with self.subTest(character=name):
                idea = "minister_" + name
                self.assertIn(idea + " = {", ministers)
                available = block(block(self.characters[name], "advisor"), "available")
                guards = [
                    scalar(e.value, "has_idea") for e in available
                    if e.key == "NOT" and scalar(e.value, "has_idea")
                ]
                self.assertEqual(guards, [idea])
        leader = block(self.characters["SHL_Mariam_Arbin"], "country_leader")
        self.assertEqual(scalar(leader, "ideology"), "pragmatism_ideology")

    def test_state_290_is_named_nuran(self):
        for language, path in STATE_NAMES.items():
            with self.subTest(language=language):
                text = read(path)
                self.assertTrue(path.read_bytes().startswith(b"\xef\xbb\xbf"), path.name)
                value = re.search(r"^ STATE_290: \"([^\"]+)\"", text, re.M).group(1)
                self.assertNotEqual(value, "Хазар")
                self.assertNotEqual(value, "Khazar")
                self.assertEqual(value, "Нуран" if language == "russian" else "Nuran")


if __name__ == "__main__":
    unittest.main()
