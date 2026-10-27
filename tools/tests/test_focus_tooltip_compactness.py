from pathlib import Path
import re
import unittest

from tools.validators.validate_adiscord_division_templates import parse_clausewitz
from tools.tests.test_adiscord_stp_preparation import walk


ROOT = Path(__file__).resolve().parents[2]
FOCUS_DIR = ROOT / "common" / "national_focus"


class FocusTooltipCompactnessTests(unittest.TestCase):
    def test_focus_descriptions_do_not_repeat_quantified_rewards(self) -> None:
        focus_ids = set()
        for path in FOCUS_DIR.glob("*.txt"):
            for entry in walk(parse_clausewitz(path.read_text(encoding="utf-8-sig"))):
                if entry.key in ("focus", "shared_focus") and isinstance(entry.value, list):
                    focus_ids.update(item.value for item in entry.value if item.key == "id")
        mechanics = re.compile(
            r"£|[+-]?\d+(?:[.,]\d+)?\s*%|"
            r"\b\d+[ -]?(?:дн(?:я|ей|ев)|дивизи|человек|days?\b|day-|divisions?\b|personnel\b)",
            re.I,
        )
        offenders = []
        for language in ("russian", "english"):
            for path in (ROOT / "localisation" / language).glob("*.yml"):
                for line in path.read_text(encoding="utf-8-sig").splitlines():
                    match = re.match(r'\s*([^:\s]+)_desc:\d*\s+"(.*)"\s*$', line)
                    if match and match[1] in focus_ids:
                        prose = re.sub(r"\[[^\]]*\]", "", match[2])
                        if mechanics.search(prose):
                            offenders.append((language, match[1]))
        self.assertEqual(offenders, [])

    def test_decision_unlocks_use_scalar_form(self) -> None:
        offenders = []
        pattern = re.compile(r"unlock_decision_tooltip\s*=\s*\{")
        for path in sorted(FOCUS_DIR.glob("*.txt")):
            text = path.read_text(encoding="utf-8-sig")
            if pattern.search(text):
                offenders.append(path.name)
        self.assertEqual(offenders, [])

    def test_decision_unlocks_do_not_inline_full_decision_effects(self) -> None:
        offenders = []
        pattern = re.compile(
            r"unlock_decision_tooltip\s*=\s*\{[^{}]*"
            r"show_effect_tooltip\s*=\s*yes[^{}]*\}",
            re.S,
        )
        for path in sorted(FOCUS_DIR.glob("*.txt")):
            text = path.read_text(encoding="utf-8-sig")
            if pattern.search(text):
                offenders.append(path.name)
        self.assertEqual(offenders, [])

    def test_decision_unlocks_do_not_repeat_the_decision_description(self) -> None:
        offenders = []
        pattern = re.compile(
            r"unlock_decision_tooltip\s*=\s*([A-Za-z0-9_]+)"
            r"[ \t\r\n]+custom_effect_tooltip\s*=\s*\1_desc\b"
        )
        for path in sorted(FOCUS_DIR.glob("*.txt")):
            text = path.read_text(encoding="utf-8-sig")
            if pattern.search(text):
                offenders.append(path.name)
        self.assertEqual(offenders, [])


if __name__ == "__main__":
    unittest.main()
