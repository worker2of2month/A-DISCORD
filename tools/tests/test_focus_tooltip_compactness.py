from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[2]
FOCUS_DIR = ROOT / "common" / "national_focus"


class FocusTooltipCompactnessTests(unittest.TestCase):
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
