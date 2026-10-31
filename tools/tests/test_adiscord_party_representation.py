"""Party coverage and collapse support contracts; native UI needs manual checking."""

from collections import Counter
from pathlib import Path
import re
import unittest

from tools.tests.test_adiscord_stp_preparation import block, scalar, matches_conditions, walk
from tools.validators.validate_adiscord_division_templates import parse_clausewitz
from tools.validators.validate_adiscord_english_localisation import ENTRY


ROOT = Path(__file__).resolve().parents[2]
TAGS = (
    "NAM", "STP", "STS", "SRP", "VAL", "SHL", "RUS", "IVN", "IVC",
    "WRK", "WKR", "TVA", "VAD", "NOD", "AZH", "EFL", "SLF",
)


def parsed(path):
    return parse_clausewitz(path.read_text(encoding="utf-8-sig"))


class PartyRepresentationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        groups = block(parsed(ROOT / "common/ideologies/00_ideologies.txt"), "ideologies")
        cls.groups = {entry.key for entry in groups}
        cls.ideology_groups = {
            subtype.key: group.key
            for group in groups
            for subtype in block(group.value, "types")
        }
        cls.characters = {}
        cls.character_paths = {}
        for path in (ROOT / "common/characters").glob("*.txt"):
            for character in block(parsed(path), "characters"):
                cls.characters[character.key] = character.value
                cls.character_paths[character.key] = path
        cls.histories = {
            tag: parsed(next((ROOT / "history/countries").glob(f"{tag} - *.txt")))
            for tag in TAGS
        }
        cls.localisation = {}
        for language in ("russian", "english"):
            entries = {}
            for path in (ROOT / "localisation" / language).glob("*.yml"):
                for line in path.read_text(encoding="utf-8-sig").splitlines():
                    match = ENTRY.fullmatch(line)
                    if match:
                        entries.setdefault(match[1], []).append((path, match[2]))
            cls.localisation[language] = entries

    def test_every_party_has_a_recruited_leader_or_scripted_resistance_leader(self):
        for tag, history in self.histories.items():
            with self.subTest(tag=tag):
                recruited = [entry.value for entry in history if entry.key == "recruit_character"]
                self.assertEqual(len(recruited), len(set(recruited)))
                represented = {
                    self.ideology_groups[scalar(role.value, "ideology")]
                    for character in recruited
                    for role in self.characters[character]
                    if role.key == "country_leader"
                }
                if tag == "STS":
                    effects = parsed(ROOT / "common/scripted_effects/ADISCORD_STP_scripted_effects.txt")
                    command = block(effects, "STP_cw_establish_resistance_command")
                    self.assertIn("STP_maksim_shabrat", str(command))
                    represented.add("chauvinism")
                self.assertEqual(represented, self.groups)

    def test_representatives_have_unique_recruitment_valid_portraits_and_localised_names(self):
        sprites = set()
        for path in (ROOT / "interface").glob("*.gfx"):
            sprites.update(re.findall(r'\bname\s*=\s*"(GFX_Portrait_Forul_Generic_\d+)"', path.read_text(encoding="utf-8-sig")))
        recruitment = Counter(
            entry.value
            for history in self.histories.values()
            for entry in history
            if entry.key == "recruit_character"
        )
        for name, character in self.characters.items():
            if "_party_representative_" not in name:
                continue
            with self.subTest(character=name):
                self.assertEqual(recruitment[name], 1)
                tag = name.split("_", 1)[0]
                role = block(character, "country_leader")
                group = self.ideology_groups[scalar(role, "ideology")]
                ruling = scalar(block(self.histories[tag], "set_politics"), "ruling_party")
                self.assertNotEqual(group, ruling)
                self.assertNotIn("advisor", {entry.key for entry in character})
                portrait = scalar(block(block(character, "portraits"), "civilian"), "large")
                self.assertIn(portrait, sprites)
                self.assertFalse(self.character_paths[name].read_bytes().startswith(b"\xef\xbb\xbf"))
                for language, entries in self.localisation.items():
                    self.assertEqual(len(entries.get(name, [])), 1, (language, name))
                    path, value = entries[name][0]
                    self.assertTrue(value.strip())
                    self.assertTrue(path.read_bytes().startswith(b"\xef\xbb\xbf"))

    def test_party_short_and_long_names_are_complete_in_both_languages(self):
        for language, entries in self.localisation.items():
            for tag in TAGS:
                for group in self.groups:
                    for suffix in ("", "_long"):
                        key = f"{tag}_{group}_party{suffix}"
                        with self.subTest(language=language, key=key):
                            self.assertEqual(len(entries.get(key, [])), 1)
                            self.assertTrue(entries[key][0][1].strip())

    def test_initial_support_sums_to_one_hundred_without_unanimous_rule(self):
        for tag, history in self.histories.items():
            with self.subTest(tag=tag):
                support = {entry.key: float(entry.value) for entry in block(history, "set_popularities")}
                self.assertEqual(sum(support.values()), 100)
                self.assertTrue(all(0 <= value < 100 for value in support.values()))

    def test_route_names_only_target_non_story_representatives_and_have_callers(self):
        effects = {}
        for path in (ROOT / "common/scripted_effects").glob("*.txt"):
            effects.update({entry.key: entry.value for entry in parsed(path)})
        profiles = {
            key: body for key, body in effects.items()
            if re.fullmatch(r"[A-Z]{3}_party_representatives_\w+", key)
        }
        self.assertEqual(len(profiles), 41)
        names_by_country = {}
        for name, body in profiles.items():
            tag = name[:3]
            with self.subTest(profile=name):
                self.assertEqual(scalar(block(block(body, "if"), "limit"), "tag"), tag)
                callers = [key for key, value in effects.items() if key != name and any(entry.key == name for entry in walk(value))]
                self.assertTrue(callers, name)
                calls = [entry.value for entry in walk(body) if entry.key == "ADISCORD_rename_party_representative"]
                self.assertTrue(calls)
                for call in calls:
                    character = scalar(call, "CHARACTER")
                    self.assertTrue(character.startswith(tag + "_party_representative_"))
                    self.assertIn(character, self.characters)
                    key = scalar(call, "NAME")
                    for language, entries in self.localisation.items():
                        self.assertEqual(len(entries.get(key, [])), 1, (language, key))
                    value = self.localisation["russian"][key][0][1]
                    self.assertNotIn(value, names_by_country.setdefault(tag, set()))
                    names_by_country[tag].add(value)
        helper = block(effects["ADISCORD_rename_party_representative"], "if")
        guard = block(helper, "limit")
        self.assertEqual(scalar(guard, "has_character"), "$CHARACTER$")
        ruling = block(block(guard, "NOT"), "has_country_leader")
        self.assertEqual(scalar(ruling, "character"), "$CHARACTER$")
        self.assertEqual(scalar(ruling, "ruling_only"), "yes")
        self.assertEqual({entry.key for entry in helper}, {"limit", "set_character_name"})

    def test_nam_collapse_reduces_support_once_before_the_announcement(self):
        effects = parsed(ROOT / "common/scripted_effects/ADISCORD_nam_resource_war_effects.txt")
        declaration = block(effects, "NAM_ladder_declare_independence")
        facts = {
            ("NAM", "exists", "yes"): True,
            ("NAM", "has_global_flag", "ADISCORD_fresh_campaign_contract_v1"): True,
        }
        first = block(declaration, "if")
        self.assertTrue(matches_conditions(block(first, "limit"), facts, "NAM"))
        support = {entry.key: float(entry.value) for entry in block(first, "set_popularities")}
        initial = float(scalar(block(self.histories["NAM"], "set_popularities"), "etatism"))
        self.assertEqual(initial, 65)
        self.assertEqual(support["etatism"], 45)
        self.assertEqual(sum(support.values()), 100)
        self.assertLess([entry.key for entry in first].index("set_popularities"), [entry.key for entry in first].index("country_event"))
        self.assertTrue(any(
            entry.key == "set_country_flag" and entry.value == "NAM_independence_declared"
            for entry in first
        ))
        facts[("NAM", "has_country_flag", "NAM_independence_declared")] = True
        self.assertFalse(matches_conditions(block(first, "limit"), facts, "NAM"))


if __name__ == "__main__":
    unittest.main()
