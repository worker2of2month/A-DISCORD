"""Contract tests for the modifier field validator.

The validator exists because an unknown modifier field is invisible: the parser
aborts the file and discards every definition after it without logging
anything. These tests therefore do more than confirm the repository is clean -
each one injects a defect of a class that has actually shipped and asserts the
validator refuses it, because a screening rule nobody has proved can fail is
indistinguishable from no rule at all.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from tools.validators import validate_adiscord_modifier_fields as validator


DYNAMIC_MODIFIERS = (
    REPOSITORY_ROOT
    / "common/dynamic_modifiers/ADISCORD_vorkerland_collapse_dynamic_modifiers.txt"
)
LEGITIMACY_MODIFIERS = (
    REPOSITORY_ROOT
    / "common/dynamic_modifiers/ADISCORD_vorkerland_legitimacy_dynamic_modifiers.txt"
)
COLLAPSE_IDEAS = REPOSITORY_ROOT / "common/ideas/ADISCORD_vorkerland_collapse_ideas.txt"


class MutationTestCase(unittest.TestCase):
    """Rewrite a covered file, run the validator, and always put it back."""

    @staticmethod
    def _read(path: Path) -> str:
        with open(path, encoding="utf-8", newline="") as handle:
            return handle.read()

    @staticmethod
    def _write(path: Path, text: str) -> None:
        with open(path, "w", encoding="utf-8", newline="") as handle:
            handle.write(text)

    def assert_rejects(self, path: Path, old: str, new: str, expected: str) -> None:
        original = self._read(path)
        self.assertIn(old, original, f"mutation anchor missing in {path.name}")
        try:
            self._write(path, original.replace(old, new, 1))
            failures = validator.validate()
        finally:
            self._write(path, original)
        self.assertTrue(failures, f"validator accepted a defect it must reject: {expected}")
        self.assertTrue(
            any(expected in failure for failure in failures),
            f"expected a failure mentioning {expected!r}, got:\n" + "\n".join(failures),
        )

    def assert_accepts(self, path: Path, old: str, new: str) -> None:
        original = self._read(path)
        self.assertIn(old, original, f"mutation anchor missing in {path.name}")
        try:
            self._write(path, original.replace(old, new, 1))
            failures = validator.validate()
        finally:
            self._write(path, original)
        self.assertEqual([], failures)


class RepositoryIsClean(unittest.TestCase):
    def test_every_covered_file_passes(self) -> None:
        self.assertEqual([], validator.validate())

    def test_coverage_includes_both_dynamic_modifier_files(self) -> None:
        covered = {path.name for path in validator.covered_files(REPOSITORY_ROOT)}
        self.assertIn("ADISCORD_vorkerland_collapse_dynamic_modifiers.txt", covered)
        self.assertIn("ADISCORD_vorkerland_legitimacy_dynamic_modifiers.txt", covered)
        self.assertIn("ADISCORD_vorkerland_collapse_ideas.txt", covered)
        self.assertIn("ADISCORD_vorkerland_focus_expansion_ideas.txt", covered)

    def test_every_dynamic_modifier_declares_a_scope_with_a_reason(self) -> None:
        for name, (scope, reason) in validator.DYNAMIC_MODIFIER_SCOPES.items():
            with self.subTest(modifier=name):
                self.assertIn(scope, (validator.COUNTRY, validator.STATE))
                self.assertGreater(
                    len(reason), 20, "a scope declaration needs a stated reason"
                )

    def test_harvest_snapshot_is_substantial(self) -> None:
        snapshot = validator.load_snapshot()
        self.assertGreater(len(snapshot["existence"]), 700)
        self.assertGreater(len(snapshot["country"]), 500)
        self.assertLess(
            len(snapshot["country"]),
            len(snapshot["existence"]),
            "if every field were country-attested the scope check would be inert",
        )

    def test_the_scope_split_separates_the_field_that_proved_it_matters(self) -> None:
        snapshot = validator.load_snapshot()
        self.assertIn("enemy_army_speed_factor", snapshot["existence"])
        self.assertNotIn("enemy_army_speed_factor", snapshot["country"])


class ExistenceAndScope(MutationTestCase):
    def test_rejects_a_field_the_engine_does_not_have(self) -> None:
        self.assert_rejects(
            DYNAMIC_MODIFIERS,
            "stability_factor = ADISCORD_vorkerland_war_economy_unrest",
            "stability_facter = ADISCORD_vorkerland_war_economy_unrest",
            "not a modifier field the engine accepts",
        )

    def test_rejects_a_state_scope_field_on_a_country_modifier(self) -> None:
        self.assert_rejects(
            DYNAMIC_MODIFIERS,
            "consumer_goods_factor = ADISCORD_vorkerland_war_economy_goods\n\tstability_factor",
            "enemy_army_speed_factor = -0.1\n\tstability_factor",
            "not attested in country scope",
        )

    def test_accepts_a_drift_field_for_an_ideology_this_mod_declares(self) -> None:
        # The engine synthesises <ideology>_drift from common/ideologies/, and
        # this mod replaces vanilla's ideologies with its own, so no harvest of
        # base-game files can contain the name.
        self.assert_accepts(
            DYNAMIC_MODIFIERS,
            "\tstability_factor = ADISCORD_vorkerland_war_economy_unrest",
            "\ttechnocracy_drift = 0.05\n\tstability_factor = ADISCORD_vorkerland_war_economy_unrest",
        )

    def test_rejects_a_modifier_reading_a_variable_nothing_writes(self) -> None:
        self.assert_rejects(
            DYNAMIC_MODIFIERS,
            "industrial_capacity_factory = ADISCORD_vorkerland_war_economy_output",
            "industrial_capacity_factory = ADISCORD_vorkerland_war_economy_ouput",
            "which no owned script writes",
        )


class StructuralShapes(MutationTestCase):
    """The two shapes that cost a live campaign."""

    def test_rejects_enable_inside_an_attacker_modifier(self) -> None:
        self.assert_rejects(
            DYNAMIC_MODIFIERS,
            "\tattacker_modifier = yes\n",
            "\tattacker_modifier = yes\n\tenable = { always = yes }\n",
            "takes no 'enable' block",
        )

    def test_rejects_remove_trigger_inside_an_attacker_modifier(self) -> None:
        self.assert_rejects(
            DYNAMIC_MODIFIERS,
            "\tattacker_modifier = yes\n",
            "\tattacker_modifier = yes\n\tremove_trigger = { always = no }\n",
            "takes no 'remove_trigger' block",
        )

    def test_rejects_enable_inside_a_targeted_modifier(self) -> None:
        self.assert_rejects(
            COLLAPSE_IDEAS,
            "targeted_modifier = { tag = EYR",
            "targeted_modifier = { enable = { always = yes } tag = EYR",
            "not accepted inside a 'targeted_modifier' block",
        )


class ReferenceIntegrity(MutationTestCase):
    def test_rejects_an_icon_that_resolves_to_no_sprite(self) -> None:
        self.assert_rejects(
            DYNAMIC_MODIFIERS,
            "icon = GFX_idea_generic_production_bonus",
            "icon = GFX_idea_generic_production_bonuss",
            "resolves to no sprite",
        )

    def test_rejects_a_tooltip_key_that_is_not_localised(self) -> None:
        self.assert_rejects(
            LEGITIMACY_MODIFIERS,
            "custom_modifier_tooltip = ADISCORD_vorkerland_legitimacy_score_tt",
            "custom_modifier_tooltip = ADISCORD_vorkerland_legitimacy_score_ttt",
            "is not defined in any English localisation file",
        )

    def test_rejects_a_dynamic_modifier_with_no_declared_scope(self) -> None:
        self.assert_rejects(
            DYNAMIC_MODIFIERS,
            "ADISCORD_vorkerland_wkr_war_economy = {",
            "ADISCORD_vorkerland_undeclared_probe = {\n\tstability_factor = 0.1\n}\n\n"
            "ADISCORD_vorkerland_wkr_war_economy = {",
            "has no scope declaration",
        )


if __name__ == "__main__":
    unittest.main()
