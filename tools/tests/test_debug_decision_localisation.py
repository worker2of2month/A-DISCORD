from __future__ import annotations

import re
import unittest
from pathlib import Path

from tools.validators.validate_adiscord_division_templates import parse_clausewitz


ROOT = Path(__file__).resolve().parents[2]
DEBUG_BLOCK = re.compile(r"(?mi)^\s*([A-Za-z0-9_]*debug[A-Za-z0-9_]*)\s*=\s*\{")
LOCALISATION = re.compile(r'^\s*([A-Za-z0-9_.-]+):(?:\d+)?\s*"([^"]*)"', re.MULTILINE)


class DebugDecisionLocalisationTests(unittest.TestCase):
    def test_debug_decisions_use_dedicated_categories(self) -> None:
        for path in (ROOT / "common" / "decisions").glob("*.txt"):
            for category in parse_clausewitz(path.read_text(encoding="utf-8-sig")):
                if not isinstance(category.value, list):
                    continue
                for decision in category.value:
                    if isinstance(decision.value, list) and "debug" in decision.key.lower():
                        self.assertIn("debug", category.key.lower(), f"{path.name}: {decision.key}")

    def test_every_debug_decision_and_category_has_red_prefix(self) -> None:
        keys: set[str] = set()
        for directory in (
            ROOT / "common" / "decisions",
            ROOT / "common" / "decisions" / "categories",
        ):
            for path in directory.glob("*.txt"):
                keys.update(DEBUG_BLOCK.findall(path.read_text(encoding="utf-8-sig")))

        localised: dict[str, str] = {}
        for path in (ROOT / "localisation" / "russian").glob("*.yml"):
            localised.update(LOCALISATION.findall(path.read_text(encoding="utf-8-sig")))

        self.assertTrue(keys, "expected at least one debug decision/category")
        for key in sorted(keys):
            self.assertIn(key, localised, f"missing Russian localisation for {key}")
            self.assertTrue(
                localised[key].startswith("§RDEBUG:§! "),
                f"{key} must start with the red §RDEBUG:§! prefix",
            )


if __name__ == "__main__":
    unittest.main()
