from __future__ import annotations

import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
FOCUS = ROOT / "common/national_focus/ADISCORD_national_focus_VAL.txt"
UNITS = ROOT / "common/units/ADISCORD_land_units.txt"
TECH = ROOT / "common/technologies/ADISCORD_VAL_marines.txt"
EFFECTS = ROOT / "common/scripted_effects/ADISCORD_VAL_effects.txt"
IDEAS = ROOT / "common/ideas/ADISCORD_VAL_marines_ideas.txt"
AUDIT = ROOT / "tools/data/division_template_audit.json"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def block(source: str, marker: str) -> str:
    pos = source.index(marker)
    start = source.rfind("focus = {", 0, pos) if marker.startswith("id = ") else source.rfind("\n", 0, pos) + 1
    opening = source.index("{", pos)
    depth = 0
    quoted = False
    escaped = False
    for index in range(opening, len(source)):
        char = source[index]
        if quoted:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quoted = False
            continue
        if char == '"':
            quoted = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return source[start:index + 1]
    raise AssertionError(f"unterminated block for {marker}")


class KefreytMarineBranchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.focuses = read(FOCUS)
        cls.units = read(UNITS)
        cls.tech = read(TECH)
        cls.effects = read(EFFECTS)
        cls.ideas = read(IDEAS)

    def test_marine_battalion_is_focus_locked_and_amphibious(self) -> None:
        marine = block(self.units, "ADISCORD_marine_infantry = {")
        self.assertIn("special_forces = yes", marine)
        self.assertIn("marines = yes", marine)
        self.assertIn("active = no", marine)
        self.assertIn("category_special_forces", marine)
        self.assertIn("category_marines", marine)
        self.assertRegex(marine, r"amphibious\s*=\s*\{[^}]*attack\s*=\s*0\.50")

        unlock = block(self.tech, "ADISCORD_tech_kefreyt_marine_corps = {")
        self.assertIn("enable_subunits = { ADISCORD_marine_infantry }", unlock)
        self.assertIn("factor = 0", unlock)

    def test_root_focus_unlocks_template_and_one_initial_division(self) -> None:
        root = block(self.focuses, "id = VAL_Marine_Contract_Corps")
        self.assertIn("prerequisite = { focus = VAL_Contracts_Outlive_Kings }", root)
        self.assertIn("VAL_raise_marine_contract_corps = yes", root)

        effect = block(self.effects, "VAL_raise_marine_contract_corps = {")
        self.assertIn("ADISCORD_tech_kefreyt_marine_corps = 1", effect)
        self.assertIn('name = "Kefreyt Marine Contract Group"', effect)
        self.assertEqual(effect.count("ADISCORD_marine_infantry = {"), 6)
        self.assertIn('division_template = \\"Kefreyt Marine Contract Group\\"', effect)
        self.assertIn("count = 1", effect)
        self.assertIn("force_allow_recruiting = yes", effect)

    def test_branch_splits_then_rejoins_before_final_corps(self) -> None:
        assault = block(self.focuses, "id = VAL_Assault_From_The_Sea")
        logistics = block(self.focuses, "id = VAL_Beachhead_Logistics")
        landing = block(self.focuses, "id = VAL_Contract_Landing_Craft")
        final = block(self.focuses, "id = VAL_Marines_Of_The_Ledger")
        for body in (assault, logistics):
            self.assertIn("prerequisite = { focus = VAL_Marine_Contract_Corps }", body)
        self.assertIn(
            "prerequisite = { focus = VAL_Assault_From_The_Sea focus = VAL_Beachhead_Logistics }",
            landing,
        )
        self.assertIn("prerequisite = { focus = VAL_Contract_Landing_Craft }", final)

        positions = {}
        for focus_id in (
            "VAL_Marine_Contract_Corps",
            "VAL_Assault_From_The_Sea",
            "VAL_Beachhead_Logistics",
            "VAL_Contract_Landing_Craft",
            "VAL_Marines_Of_The_Ledger",
        ):
            body = block(self.focuses, f"id = {focus_id}")
            x = int(re.search(r"(?m)^\s*x\s*=\s*(-?\d+)", body).group(1))
            y = int(re.search(r"(?m)^\s*y\s*=\s*(-?\d+)", body).group(1))
            positions[focus_id] = (x, y)
        self.assertEqual(len(positions), len(set(positions.values())))

    def test_branch_rewards_cover_assault_logistics_landing_and_force_size(self) -> None:
        self.assertIn("amphibious_invasion = 0.15", self.ideas)
        self.assertIn("invasion_preparation = -0.15", self.ideas)
        self.assertIn("extra_marine_supply_grace = 48", self.ideas)
        self.assertIn("naval_invasion_prep_speed = 0.10", self.ideas)
        self.assertIn("naval_invasion_capacity = 10", self.ideas)
        self.assertIn("special_forces_cap = 0.03", self.ideas)
        self.assertIn("special_forces_training_time_factor = -0.15", self.ideas)

    def test_template_and_spawn_are_registered_in_division_audit(self) -> None:
        audit = json.loads(read(AUDIT))
        template = next(row for row in audit["templates"] if row["key"] == "val_focus_marine_contract_group")
        self.assertEqual(template["technical_name"], "Kefreyt Marine Contract Group")
        self.assertEqual(len(template["regiments"]), 6)
        ref = next(row for row in audit["references"] if row["key"] == "val_focus_marine_contract_group_spawn")
        self.assertEqual(ref["technical_name"], "Kefreyt Marine Contract Group")
        self.assertEqual(ref["start_experience_factor"], 0.3)

    def test_russian_and_english_localisation_cover_branch_and_unit(self) -> None:
        keys = (
            "VAL_Marine_Contract_Corps",
            "VAL_Assault_From_The_Sea",
            "VAL_Beachhead_Logistics",
            "VAL_Contract_Landing_Craft",
            "VAL_Marines_Of_The_Ledger",
            "ADISCORD_marine_infantry",
            "VAL_marine_contract_corps",
        )
        for language in ("russian", "english"):
            loc = read(ROOT / "localisation" / language / f"ADISCORD_VAL_decisions_l_{language}.yml")
            for key in keys:
                self.assertRegex(loc, rf"(?m)^\s*{re.escape(key)}:")


if __name__ == "__main__":
    unittest.main()
