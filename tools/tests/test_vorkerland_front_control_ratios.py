from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
AI_FILES = (
    ROOT / "common/ai_strategy/ADISCORD_vorkerland_collapse_ai.txt",
    ROOT / "common/ai_strategy/ADISCORD_nam_resource_war_ai.txt",
)


class VorkerlandFrontControlRatioTests(unittest.TestCase):
    def test_front_control_thresholds_can_activate(self) -> None:
        for path in AI_FILES:
            source = path.read_text(encoding="utf-8-sig")
            ratios = [
                float(value)
                for value in re.findall(
                    r"type\s*=\s*front_control\b[^}\n]*\bratio\s*=\s*([0-9.]+)",
                    source,
                )
            ]
            self.assertTrue(ratios, path.name)
            self.assertTrue(
                all(0 <= ratio < 1 for ratio in ratios),
                f"{path.name}: impossible front coverage threshold in {ratios}",
            )

    def test_observed_mixed_fronts_use_a_low_coverage_threshold(self) -> None:
        collapse = AI_FILES[0].read_text(encoding="utf-8-sig")
        nam = AI_FILES[1].read_text(encoding="utf-8-sig")
        for tag in ("WKR", "VAD", "TVA"):
            self.assertRegex(
                collapse,
                rf"type\s*=\s*front_control\s+tag\s*=\s*{tag}\s+ratio\s*=\s*0\.01\b",
            )
        for tag in ("EFL", "AZH", "SLF", "NAM"):
            self.assertRegex(
                nam,
                rf"type\s*=\s*front_control\s+tag\s*=\s*{tag}\s+ratio\s*=\s*0\.01\b",
            )


if __name__ == "__main__":
    unittest.main()
