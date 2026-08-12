from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8-sig")


def named_block(source: str, name: str) -> str:
    match = re.search(rf"(?m)^\s*{re.escape(name)}\s*=\s*\{{", source)
    if not match:
        return ""
    start = source.find("{", match.start())
    depth = 0
    for index in range(start, len(source)):
        character = source[index]
        if character == "{":
            depth += 1
        elif character == "}":
            depth -= 1
            if depth == 0:
                return source[match.start() : index + 1]
    return ""


class VadPostwarContractTests(unittest.TestCase):
    def test_restored_sol_remains_protectorate_but_voluntary_ally_is_sovereign(self) -> None:
        source = read("common/scripted_effects/ADISCORD_vorkerland_phase_effects.txt")
        formation = named_block(source, "ADISCORD_vorkerland_form_wrk_from_vad")
        self.assertTrue(formation)

        restored = re.search(
            r"(?s)if\s*=\s*\{\s*limit\s*=\s*\{[^{}]*"
            r"has_global_flag\s*=\s*ADISCORD_vorkerland_sol_restoration_verified"
            r".*?\n\s*\}\s*\n\s*else_if\s*=",
            formation,
        )
        self.assertIsNotNone(restored)
        restored_block = restored.group(0)
        self.assertIn("puppet = SOL", restored_block)
        self.assertIn("autonomy_state = autonomy_puppet", restored_block)
        self.assertIn("add_to_faction = SOL", restored_block)

        voluntary = formation[restored.end() - len("else_if =") :]
        self.assertIn("has_global_flag = ADISCORD_vorkerland_vad_sol_alliance_accepted", voluntary)
        self.assertIn("add_to_faction = SOL", voluntary)
        self.assertNotIn("puppet = SOL", voluntary)
        self.assertNotIn("autonomy_state = autonomy_puppet", voluntary)

    def test_joint_route_capstone_ends_temporary_cosmetic(self) -> None:
        source = read("common/national_focus/ADISCORD_vorkerland_civil_war_focus.txt")
        focus = named_block(source, "focus")
        # Locate the exact focus assignment rather than accepting another focus's reward.
        match = re.search(
            r"(?ms)^\s*focus\s*=\s*\{\s*id\s*=\s*WRK_joint_impose_reunification_settlement\b",
            source,
        )
        self.assertIsNotNone(match)
        start = match.start()
        focus = named_block(source[start:], "focus")
        reward = named_block(focus, "completion_reward")
        self.assertEqual(reward.count("drop_cosmetic_tag = yes"), 1)
        self.assertIn("add_ideas = ADISCORD_vorkerland_reunification_settlement", reward)

    def test_joint_council_gets_specific_victory_text_before_vlad_fallback(self) -> None:
        scripted = read("common/scripted_localisation/ADISCORD_scripted_loc_superevents.txt")
        for suffix in ("title", "quote", "comment"):
            joint_key = f"superevent_vorkerland_joint_victory_{suffix}"
            vlad_key = f"superevent_vorkerland_vlad_victory_{suffix}"
            self.assertEqual(scripted.count(f"localization_key = {joint_key}"), 1)
            self.assertLess(scripted.index(joint_key), scripted.index(vlad_key))

        for path in (
            "localisation/english/ADISCORD_superevents_l_english.yml",
            "localisation/russian/ADISCORD_superevents_l_russian.yml",
        ):
            localisation = read(path)
            for suffix in ("title", "quote", "comment"):
                self.assertIn(f"superevent_vorkerland_joint_victory_{suffix}:", localisation)

        russian = ROOT / "localisation/russian/ADISCORD_superevents_l_russian.yml"
        self.assertTrue(russian.read_bytes().startswith(b"\xef\xbb\xbf"))

    def test_joint_council_ai_prefers_chancery_over_commandantures(self) -> None:
        source = read("common/national_focus/ADISCORD_vorkerland_civil_war_focus.txt")

        def focus(focus_id: str) -> str:
            match = re.search(
                rf"(?ms)^\s*focus\s*=\s*\{{\s*id\s*=\s*{re.escape(focus_id)}\b",
                source,
            )
            self.assertIsNotNone(match)
            return named_block(source[match.start() :], "focus")

        registers_ai = named_block(focus("VAD_open_imperial_registers"), "ai_will_do")
        command_ai = named_block(focus("VAD_form_field_commandantures"), "ai_will_do")
        flag = "has_global_flag = ADISCORD_vorkerland_joint_government_formed"
        self.assertIn(flag, registers_ai)
        self.assertIn("factor = 2", registers_ai)
        self.assertIn(flag, command_ai)
        self.assertIn("factor = 0.5", command_ai)


if __name__ == "__main__":
    unittest.main()
