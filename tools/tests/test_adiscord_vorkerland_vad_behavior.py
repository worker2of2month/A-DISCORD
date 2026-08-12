from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
AI_PATH = ROOT / "common/ai_strategy/ADISCORD_vorkerland_collapse_ai.txt"
ACTIVE_FLAG = "ADISCORD_vorkerland_vad_solar_intervention_active"
CASES = {
    "sra": ("SRA", "ADISCORD_vorkerland_vad_solar_intervention_target_sra"),
    "csl": ("CSL", "ADISCORD_vorkerland_vad_solar_intervention_target_csl"),
}


def without_comments(source: str) -> str:
    return "\n".join(line.split("#", 1)[0] for line in source.splitlines())


def named_blocks(source: str, name: str) -> list[str]:
    blocks: list[str] = []
    pattern = re.compile(rf"(?m)^\s*{re.escape(name)}\s*=\s*\{{")
    for match in pattern.finditer(source):
        depth = 0
        for index in range(match.end() - 1, len(source)):
            if source[index] == "{":
                depth += 1
            elif source[index] == "}":
                depth -= 1
                if depth == 0:
                    blocks.append(source[match.start() : index + 1])
                    break
        else:
            raise AssertionError(f"unterminated block: {name}")
    return blocks


def named_block(source: str, name: str) -> str:
    blocks = named_blocks(source, name)
    if len(blocks) != 1:
        raise AssertionError(f"expected one {name} block, found {len(blocks)}")
    return blocks[0]


def compact(source: str) -> str:
    return " ".join(source.split())


class VorkerlandVadSolarBehaviorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.ai = without_comments(AI_PATH.read_text(encoding="utf-8-sig"))

    def test_solar_intervention_fronts_have_exact_bounded_contracts(self) -> None:
        for slug, (target, target_flag) in CASES.items():
            with self.subTest(target=target):
                name = f"ADISCORD_vorkerland_vad_solar_intervention_front_{slug}"
                block = named_block(self.ai, name)
                self.assertEqual(compact(named_block(block, "allowed")), "allowed = { tag = VAD }")

                enable = named_block(block, "enable")
                self.assertEqual(
                    re.findall(r"has_global_flag\s*=\s*([A-Za-z0-9_]+)", enable),
                    [ACTIVE_FLAG, target_flag],
                )
                self.assertEqual(re.findall(r"country_exists\s*=\s*([A-Z]{3})", enable), [target])
                self.assertEqual(re.findall(r"has_war_with\s*=\s*([A-Z]{3})", enable), [target])
                self.assertNotIn("OR =", enable)
                self.assertEqual(block.count("abort_when_not_enabled = yes"), 1)

                self.assertEqual(
                    {compact(strategy) for strategy in named_blocks(block, "ai_strategy")},
                    {
                        f"ai_strategy = {{ type = front_unit_request tag = {target} value = 100 }}",
                        f"ai_strategy = {{ type = front_control tag = {target} ratio = 1.00 priority = 1500 ordertype = front execution_type = rush execute_order = yes manual_attack = yes }}",
                        f"ai_strategy = {{ type = conquer id = {target} value = 250 }}",
                    },
                )

    def test_no_vad_solar_attack_profile_activates_outside_intervention(self) -> None:
        expected_names = {
            f"ADISCORD_vorkerland_vad_solar_intervention_front_{slug}"
            for slug in CASES
        }
        found_names: set[str] = set()
        for match in re.finditer(r"(?m)^([A-Za-z0-9_]+)\s*=\s*\{", self.ai):
            name = match.group(1)
            block = named_block(self.ai, name)
            allowed = named_block(block, "allowed") if named_blocks(block, "allowed") else ""
            if not re.search(r"\btag\s*=\s*VAD\b", allowed):
                continue
            strategies = "\n".join(named_blocks(block, "ai_strategy"))
            targets = set(re.findall(r"\b(?:tag|id)\s*=\s*(SRA|CSL)\b", strategies))
            if not targets:
                continue

            found_names.add(name)
            enable = named_block(block, "enable")
            self.assertIn(f"has_global_flag = {ACTIVE_FLAG}", compact(enable), name)
            for target in targets:
                slug = target.lower()
                self.assertIn(
                    f"has_global_flag = {CASES[slug][1]}",
                    compact(enable),
                    name,
                )
                self.assertIn(f"has_war_with = {target}", compact(enable), name)

        self.assertEqual(found_names, expected_names)

    def test_solar_winners_receive_target_specific_defence_profiles(self) -> None:
        for slug, (target, target_flag) in CASES.items():
            with self.subTest(target=target):
                name = f"ADISCORD_vorkerland_{slug}_defend_vad_intervention"
                block = named_block(self.ai, name)
                self.assertEqual(
                    compact(named_block(block, "allowed")),
                    f"allowed = {{ tag = {target} }}",
                )
                enable = compact(named_block(block, "enable"))
                for token in (
                    f"has_global_flag = {ACTIVE_FLAG}",
                    f"has_global_flag = {target_flag}",
                    "country_exists = VAD",
                    "has_war_with = VAD",
                ):
                    self.assertIn(token, enable)
                self.assertEqual(block.count("abort_when_not_enabled = yes"), 1)
                strategies = {compact(strategy) for strategy in named_blocks(block, "ai_strategy")}
                self.assertIn(
                    "ai_strategy = { type = front_unit_request tag = VAD value = 100 }",
                    strategies,
                )
                self.assertIn(
                    "ai_strategy = { type = front_control tag = VAD ratio = 1.00 priority = 1400 ordertype = front execution_type = careful execute_order = yes manual_attack = no }",
                    strategies,
                )


if __name__ == "__main__":
    unittest.main()
