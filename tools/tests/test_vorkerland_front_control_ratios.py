from __future__ import annotations

import re
import unittest
from pathlib import Path


from tools.lib.paths import source_section


ROOT = Path(__file__).resolve().parents[2]
AI_FILES = (
    ROOT / "common/ai_strategy/ADISCORD_vorkerland_ai.txt",
    ROOT / "common/ai_strategy/ADISCORD_nam_resource_war_ai.txt",
)


class VorkerlandFrontControlRatioTests(unittest.TestCase):
    def test_front_control_thresholds_can_activate(self) -> None:
        for path in AI_FILES:
            source = path.read_text(encoding="utf-8-sig")
            ratios = [
                float(value)
                for value in re.findall(
                    r"type\s*=\s*front_control\b[^}]*?\bratio\s*=\s*([0-9.]+)",
                    source,
                )
            ]
            self.assertTrue(ratios, path.name)
            self.assertTrue(
                all(0 <= ratio < 1 for ratio in ratios),
                f"{path.name}: impossible front coverage threshold in {ratios}",
            )

    def test_all_fronts_preserve_native_local_attack_checks(self) -> None:
        from tools.tests.test_adiscord_vorkerland_vad_behavior import named_block, named_blocks

        source = AI_FILES[0].read_text(encoding="utf-8-sig")
        checked = 0
        for name in re.findall(r"(?m)^(ADISCORD_vorkerland_\w+)\s*=\s*\{", source):
            profile = named_block(source, name)
            for strategy in named_blocks(profile, "ai_strategy"):
                if not re.search(r"\btype\s*=\s*front_control\b", strategy):
                    continue
                checked += 1
                with self.subTest(profile=name):
                    self.assertIn("manual_attack = no", strategy)
                    self.assertNotRegex(strategy, r"\bexecution_type\s*=\s*rush\b")
                    if "execution_type = rush_weak" in strategy:
                        self.assertTrue(
                            name.startswith("ADISCORD_vorkerland_escalation_")
                            or "_breakthrough_" in name,
                            "selective offensive policy needs an explicit campaign phase",
                        )
        self.assertGreater(checked, 100)

    def test_central_campaigns_do_not_force_permanent_rush_orders(self) -> None:
        from tools.tests.test_adiscord_vorkerland_vad_behavior import named_block

        source = AI_FILES[0].read_text(encoding="utf-8-sig")
        for target in ("EYR", "EGC", "RIV", "REV", "YOR", "NDN", "SWB", "VHV", "OSV"):
            front = named_block(source, f"ADISCORD_vorkerland_front_central_against_{target.lower()}")
            with self.subTest(target=target):
                self.assertIn("execution_type = balanced", front)
                self.assertIn("manual_attack = no", front)
                self.assertIn("execute_order = yes", front)
        for slug in ("rom", "tru"):
            front = named_block(source, f"ADISCORD_vorkerland_rom_tru_{slug}_offensive")
            with self.subTest(slug=slug):
                self.assertIn("execution_type = balanced", front)
                self.assertIn("manual_attack = no", front)

    def test_breakthrough_orders_require_a_live_window_and_reserves(self) -> None:
        from tools.tests.test_adiscord_vorkerland_vad_behavior import named_block

        source = AI_FILES[0].read_text(encoding="utf-8-sig")
        for group, targets in (
            ("central", ("EYR", "EGC", "RIV", "REV", "YOR", "NDN", "SWB", "VHV", "OSV")),
            ("solarino", ("SRA", "CSL")),
        ):
            for target in targets:
                front = named_block(source, f"ADISCORD_vorkerland_{group}_breakthrough_{target.lower()}")
                enabled = named_block(front, "enable")
                with self.subTest(group=group, target=target):
                    self.assertIn(f"has_country_flag = ADISCORD_vorkerland_{group}_breakthrough_window_active", enabled)
                    self.assertIn("has_manpower > 1000", enabled)
                    self.assertIn("stockpile_ratio = { archetype = infantry_equipment ratio > 0.05 }", enabled)
                    self.assertIn(f"fighting_army_strength_ratio = {{ tag = {target} ratio > 1.15 }}", enabled)
                    self.assertIn("execution_type = rush_weak", front)
                    self.assertIn("manual_attack = no", front)
                    self.assertIn("abort_when_not_enabled = yes", front)

    def test_collapse_offensives_do_not_use_careful_stare_or_high_coverage(self) -> None:
        from tools.tests.test_adiscord_vorkerland_vad_behavior import named_block, named_blocks

        source = AI_FILES[0].read_text(encoding="utf-8-sig")
        keep_careful = {
            "ADISCORD_vorkerland_central_minor_defense_against_wkr",
            "ADISCORD_vorkerland_central_minor_defense_against_vad",
            "ADISCORD_vorkerland_central_minor_defense_against_tva",
            "ADISCORD_vorkerland_northern_defense_against_ivanland",
            "ADISCORD_vorkerland_sra_defend_vad_intervention",
            "ADISCORD_vorkerland_csl_defend_vad_intervention",
            "ADISCORD_vorkerland_zao_defend_rom_intervention",
            "ADISCORD_vorkerland_wps_defend_rom_intervention",
        }
        field = named_block(source, "ADISCORD_vorkerland_collapse_field_army")
        self.assertIn("role_ratio id = garrison value = -80", field)
        self.assertIn("dont_defend_ally_borders value = 1", field)
        checked = 0
        for name in re.findall(r"(?m)^(ADISCORD_vorkerland_\w+)\s*=\s*\{", source):
            profile = named_block(source, name)
            for strategy in named_blocks(profile, "ai_strategy"):
                if not re.search(r"\btype\s*=\s*front_control\b", strategy):
                    continue
                checked += 1
                with self.subTest(profile=name):
                    self.assertRegex(strategy, r"\bratio\s*=\s*0\.01\b")
                    if name in keep_careful:
                        self.assertIn("execution_type = careful", strategy)
                    else:
                        self.assertNotIn("execution_type = careful", strategy)
        self.assertGreater(checked, 100)

    def test_observed_mixed_fronts_use_a_low_coverage_threshold(self) -> None:
        collapse = source_section(AI_FILES[0].read_text(encoding="utf-8-sig"), 'collapse_ai')
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
