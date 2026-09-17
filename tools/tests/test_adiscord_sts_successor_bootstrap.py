from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ON_ACTION = ROOT / "common/on_actions/02_ADISCORD_STP_on_actions.txt"
STP_OOB = ROOT / "history/units/STP.txt"
OLD_FADA = ROOT / "history/states/53-Old-Fada.txt"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def named_block(source: str, name: str) -> str:
    match = re.search(rf"(?m)^\s*{re.escape(name)}\s*=\s*\{{", source)
    if not match:
        return ""
    opening = source.find("{", match.start())
    depth = 0
    in_string = False
    escaped = False
    for index in range(opening, len(source)):
        char = source[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return source[match.start() : index + 1]
    raise AssertionError(f"unclosed block: {name}")


class StsSuccessorBootstrapTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.on_action = read(ON_ACTION)
        cls.hook = named_block(cls.on_action, "on_war_relation_added")

    def test_sts_reinherits_live_stp_technology_and_starts_bounded_production(self) -> None:
        self.assertTrue(self.hook, "missing STP/STS war-edge successor bootstrap")
        self.assertIn("has_global_flag = STP_cw_started", self.hook)
        self.assertRegex(self.hook, r"ROOT\s*=\s*\{\s*tag\s*=\s*STP\s*\}")
        self.assertRegex(self.hook, r"FROM\s*=\s*\{\s*tag\s*=\s*STS\s*\}")
        self.assertRegex(self.hook, r"ROOT\s*=\s*\{\s*tag\s*=\s*STS\s*\}")
        self.assertRegex(self.hook, r"FROM\s*=\s*\{\s*tag\s*=\s*STP\s*\}")

        self.assertIn("inherit_technology = STP", self.hook)
        self.assertIn("mark_technology_tree_layout_dirty = yes", self.hook)
        self.assertNotIn("set_technology =", self.hook,
                         "successor must inherit STP's live research, not a frozen baseline")
        self.assertIn("STP_cw_sts_runtime_bootstrap_applied", self.hook)

        self.assertEqual(self.hook.count("add_equipment_production ="), 2)
        self.assertIn("type = infantry_equipment_0 creator = \"STS\"", self.hook)
        self.assertIn(
            "type = ADISCORD_squad_weapons_equipment_0 creator = \"STS\"",
            self.hook,
        )
        self.assertEqual(
            [int(value) for value in re.findall(r"requested_factories\s*=\s*(\d+)", self.hook)],
            [1, 1],
            "newborn STS has a two-factory bootstrap, not an oversized production queue",
        )

    def test_old_fada_repositions_one_existing_paid_territorial_brigade(self) -> None:
        state = read(OLD_FADA)
        oob = read(STP_OOB)
        self.assertRegex(state, r"provinces\s*=\s*\{[^}]*\b70\b", "state 53 must contain province 70")
        self.assertRegex(
            oob,
            r"location\s*=\s*70[\s\S]{0,180}?division_template\s*=\s*\"Police division\"",
            "Old Fada starts with a local police formation before the split",
        )

        self.assertTrue(self.hook, "missing STP/STS war-edge successor bootstrap")
        self.assertIn("STP_cw_old_fada_guard_positioned", self.hook)
        self.assertRegex(
            self.hook,
            r"53\s*=\s*\{\s*is_owned_by\s*=\s*STS\s*\}",
        )
        self.assertIn("any_country_division", self.hook)
        self.assertIn("random_country_division", self.hook)
        self.assertIn("division_has_battalion_in_template = ADISCORD_territorial", self.hook)
        self.assertIn("unit_strength > 0.99", self.hook)
        self.assertEqual(self.hook.count("destroy_unit = yes"), 1)
        self.assertEqual(self.hook.count("create_unit ="), 1)
        self.assertIn(
            'division = "division_template = \\"Stelander Territorial Brigade\\" '
            'start_experience_factor = 0.1 start_equipment_factor = 1.0 '
            'start_manpower_factor = 1.0"',
            self.hook,
        )
        self.assertIn("owner = STS", self.hook)
        self.assertIn("allow_spawning_on_enemy_provs = yes", self.hook)
        self.assertNotIn("add_manpower =", self.hook)
        self.assertNotIn("add_equipment_to_stockpile =", self.hook)


if __name__ == "__main__":
    unittest.main()
