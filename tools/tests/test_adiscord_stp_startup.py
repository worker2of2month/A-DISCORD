from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
EFFECTS = ROOT / "common/scripted_effects/ADISCORD_scripted_effects_STP.txt"
ON_ACTIONS = ROOT / "common/on_actions/01_ADISCORD_STP_suspicion_on_actions.txt"


def named_block(text: str, name: str) -> str:
    match = re.search(rf"(?m)^{re.escape(name)}\s*=\s*\{{", text)
    if match is None:
        raise AssertionError(f"missing block: {name}")

    depth = 0
    for index in range(match.end() - 1, len(text)):
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
            if depth == 0:
                return text[match.start() : index + 1]
    raise AssertionError(f"unterminated block: {name}")


class STPStartupContractTests(unittest.TestCase):
    def test_startup_initializers_have_one_consolidated_definition_each(self) -> None:
        definitions: dict[str, list[str]] = {
            "STP_initialize_party_suspicion": [],
            "STP_initialize_leader_health": [],
        }
        for path in sorted((ROOT / "common/scripted_effects").glob("*.txt")):
            source = path.read_text(encoding="utf-8-sig")
            for name in definitions:
                matches = re.findall(rf"(?m)^{re.escape(name)}\s*=\s*\{{", source)
                definitions[name].extend([path.name] * len(matches))

        for name, paths in definitions.items():
            self.assertEqual(
                [EFFECTS.name],
                paths,
                f"{name} must have exactly one definition in the consolidated STP effects file",
            )

        self.assertFalse(
            (ROOT / "common/scripted_effects/ADISCORD_scripted_effects_stelander.txt").exists()
        )
        self.assertFalse(
            (ROOT / "common/scripted_effects/ADISCORD_stp_state_face_effects.txt").exists()
        )

    def test_initializers_use_current_normalized_rate_schema(self) -> None:
        source = EFFECTS.read_text(encoding="utf-8-sig")
        suspicion = named_block(source, "STP_initialize_party_suspicion")
        health = named_block(source, "STP_initialize_leader_health")

        self.assertIn("has_variable = STP_party_suspicion_rate", suspicion)
        self.assertIn("var = STP_party_suspicion_rate value = 0.05", suspicion)
        self.assertIn("var = STP_party_suspicion_rate min = 0 max = 1", suspicion)
        self.assertIn("var = STP_party_suspicion_rate_temp value = 0", suspicion)
        self.assertIn("STP_change_party_suspicion = yes", suspicion)

        self.assertIn("has_variable = STP_leader_health_rate", health)
        self.assertIn("var = STP_leader_health_rate value = 1", health)
        self.assertIn("var = STP_leader_health_rate min = 0 max = 1", health)
        self.assertIn("var = STP_leader_health_rate_temp value = 0", health)
        self.assertIn("STP_leader_health = yes", health)

    def test_startup_calls_both_initializers_in_stp_scope(self) -> None:
        source = ON_ACTIONS.read_text(encoding="utf-8-sig")
        startup = named_block(source, "on_actions")
        self.assertIn("limit = { STP = { exists = yes } }", startup)
        self.assertRegex(
            startup,
            r"STP\s*=\s*\{[^{}]*STP_initialize_party_suspicion\s*=\s*yes"
            r"[^{}]*STP_initialize_leader_health\s*=\s*yes[^{}]*\}",
        )


if __name__ == "__main__":
    unittest.main()
