from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RUSSIAN = ROOT / "localisation" / "russian"
ENGLISH = ROOT / "localisation" / "english"
REPLACE = ROOT / "localisation" / "replace"

# Historical/internal file stems and scripted identifiers may still contain old
# compatibility names. These aliases must not survive in effective localisation.
FORBIDDEN_ALIASES = (
    "Иванланд",
    "иванланд",
    "Ivanland",
    "Наместникленд",
    "Namestnikland",
    "Витланд",
    "Witland",
    "Workerland",
    "Данияленд",
    "даниаленд",
    "Daniyaland",
    "Danialand",
    "DaniaLand",
)

LOCALISATION_LINE = re.compile(r'^\s*([^#\s][^:]*)\s*:\s*(?:0\s*)?"(.*)"\s*$')


def localisation_entries(root: Path) -> dict[str, str]:
    entries: dict[str, str] = {}
    if not root.exists():
        return entries
    for path in root.rglob("*.yml"):
        for line in path.read_text(encoding="utf-8-sig").splitlines():
            match = LOCALISATION_LINE.match(line)
            if match:
                entries[match.group(1).strip()] = match.group(2)
    return entries


class CanonicalCountryNameTests(unittest.TestCase):
    def test_legacy_aliases_are_absent_from_effective_localisation(self) -> None:
        replacements = localisation_entries(REPLACE)
        failures: list[str] = []

        for language_root in (RUSSIAN, ENGLISH):
            for path in language_root.rglob("*.yml"):
                for line in path.read_text(encoding="utf-8-sig").splitlines():
                    match = LOCALISATION_LINE.match(line)
                    if not match:
                        continue
                    key, value = match.group(1).strip(), match.group(2)
                    if not any(alias in value for alias in FORBIDDEN_ALIASES):
                        continue
                    replacement = replacements.get(key)
                    if replacement is None or any(alias in replacement for alias in FORBIDDEN_ALIASES):
                        failures.append(f"{path.relative_to(ROOT)}: {key}")

        for key, value in replacements.items():
            if any(alias in value for alias in FORBIDDEN_ALIASES):
                failures.append(f"localisation/replace: {key}")

        self.assertEqual(failures, [], "legacy country aliases remain in effective localisation")

    def test_dan_is_explicitly_expeditionary_group_42(self) -> None:
        tag_map = (ROOT / "common/country_tags/00_countries.txt").read_text(encoding="utf-8-sig")
        self.assertIn('DAN = "countries/ExpeditionaryGroup42.txt"', tag_map)
        self.assertNotIn("DaniaLand", tag_map)

        self.assertTrue((ROOT / "common/countries/ExpeditionaryGroup42.txt").is_file())
        self.assertFalse((ROOT / "common/countries/DaniaLand.txt").exists())
        self.assertTrue((ROOT / "history/countries/DAN - Expeditionary Group 42.txt").is_file())
        self.assertFalse((ROOT / "history/countries/DAN - DaniaLand.txt").exists())

        english = localisation_entries(ENGLISH)
        russian = localisation_entries(RUSSIAN)
        self.assertEqual(english["DAN"], "Expeditionary Group #42")
        self.assertEqual(english["DAN_DEF"], "Expeditionary Group #42")
        self.assertEqual(russian["DAN"], "Экспедиционная группа #42")
        self.assertEqual(russian["DAN_DEF"], "Экспедиционная группа #42")
        self.assertIn("not a civilian state but a military formation", english["DAN_national_spirit_desc"])
        self.assertIn("не гражданское государство, а военное формирование", russian["DAN_national_spirit_desc"])

    def test_svetlogorye_localisation_does_not_show_internal_nam_tag(self) -> None:
        path = RUSSIAN / "ADISCORD_nam_resource_war_l_russian.yml"
        text = path.read_text(encoding="utf-8-sig")
        visible_values = "\n".join(
            match.group(2)
            for line in text.splitlines()
            if (match := LOCALISATION_LINE.match(line))
        )
        self.assertNotRegex(visible_values, r"\bNAM\b")


if __name__ == "__main__":
    unittest.main()
