import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import validate_tc


def read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8-sig")


class NcnsFactionCompatibilityTests(unittest.TestCase):
    def test_total_conversion_owns_faction_database(self):
        self.assertIn('replace_path="common/factions"', read("descriptor.mod"))

    def test_starting_factions_use_explicit_adiscord_template(self):
        for relative_path in (
            "history/countries/WRK - WorkerLand.txt",
            "history/countries/BJK - Besjaysk.txt",
            "history/countries/NOD - Nodral.txt",
        ):
            text = read(relative_path)
            self.assertNotRegex(text, r"(?m)^\s*create_faction\s*=")
            self.assertIn("create_faction_from_template", text)
            self.assertIn("template = faction_template_ADISCORD_standard", text)

    def test_faction_template_is_mod_native(self):
        template = read("common/factions/templates/ADISCORD_faction_templates.txt")
        manifest = read("common/factions/goals/ADISCORD_faction_manifests.txt")
        leadership_rule = read("common/factions/rules/ADISCORD_change_leader_rules.txt")
        rule_group = read("common/factions/rules/groups/ADISCORD_rule_groups.txt")
        self.assertIn("faction_template_ADISCORD_standard", template)
        self.assertIn("ADISCORD_faction_manifest_continuity", template)
        self.assertIn("ADISCORD_faction_manifest_continuity", manifest)
        self.assertIn("ratio_progress", manifest)
        self.assertIn("total_amount = 1", manifest)
        self.assertIn("completed_amount = 1", manifest)
        self.assertIn("change_leader_rule_influence", leadership_rule)
        self.assertIn("change_leader_rule_influence", rule_group)
        self.assertNotRegex(template + manifest + leadership_rule + rule_group, r"\b(?:democratic|fascism|communism|neutrality)\b")

    def test_campaign_slots_use_scripted_variable(self):
        effects = read("common/scripted_effects/ADISCORD_shared_action_effects.txt")
        triggers = read("common/scripted_triggers/ADISCORD_shared_action_triggers.txt")
        decisions = read("common/decisions/ADISCORD_VAL_rework_decisions.txt")
        combined = effects + triggers + decisions
        self.assertNotRegex(combined, r"\b(?:has|add|remove)_campaign_slot\b")
        self.assertIn("ADISCORD_available_campaign_slots", effects)
        self.assertIn("ADISCORD_available_campaign_slots", triggers)
        self.assertIn("ADISCORD_has_campaign_slot = yes", decisions)
        self.assertNotRegex(decisions, r"\bstability\s*[<>]")

    def test_main_validator_accepts_ncns_contract(self):
        issues, total = validate_tc.check_ncns_and_campaign_compatibility(300)
        self.assertEqual([], issues)
        self.assertEqual(0, total)


if __name__ == "__main__":
    unittest.main()
