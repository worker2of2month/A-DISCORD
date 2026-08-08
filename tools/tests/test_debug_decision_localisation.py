from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DEBUG_BLOCK = re.compile(r"(?mi)^\s*([A-Za-z0-9_]*debug[A-Za-z0-9_]*)\s*=\s*\{")
LOCALISATION = re.compile(r'^\s*([A-Za-z0-9_.-]+):(?:\d+)?\s*"([^"]*)"', re.MULTILINE)


class DebugDecisionLocalisationTests(unittest.TestCase):
    def test_every_debug_decision_and_category_has_red_prefix(self) -> None:
        keys: set[str] = set()
        for directory in (ROOT / "common" / "decisions", ROOT / "common" / "decisions" / "categories"):
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
