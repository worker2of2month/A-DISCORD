"""Regression contract: Oitfort is wartime-only and is absorbed by unified Vorkerland."""

from tools.lib.on_actions import read_country_on_actions
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
# The country that currently is Vorkerland: WRK until a claimant unifies it.
NATION_TARGET = "event_target:ADISCORD_vorkerland_nation"


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8-sig")


def named_block(text: str, name: str) -> str:
    start = text.index(name + " =")
    brace = text.index("{", start)
    depth = 0
    for index in range(brace, len(text)):
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    raise AssertionError(f"unclosed block {name}")


class OitfortTerminalCleanupTests(unittest.TestCase):
    def test_unified_country_absorbs_oitfort_in_all_routes(self):
        effects = read("common/scripted_effects/ADISCORD_vorkerland_effects.txt")
        absorb = named_block(
            effects, "ADISCORD_vorkerland_absorb_wtd_after_reunification"
        )
        for token in (
            "country_exists = WTD",
            "annex_country = { target = WTD transfer_troops = yes }",
            "34 = { remove_core_of = WTD",
            f"set_state_owner_to = {NATION_TARGET}",
            f"set_state_controller_to = {NATION_TARGET}",
            f"is_owned_by = {NATION_TARGET}",
            f"white_peace = {NATION_TARGET}",
        ):
            self.assertIn(token, absorb)
        # The settlement runs in the winner's own scope; the retired tag
        # receives neither Oitfort's land nor its peace.
        self.assertNotIn("WRK", absorb)

        for suffix in ("wkr", "vad", "tva"):
            formation = named_block(
                effects, f"ADISCORD_vorkerland_settle_unification_under_{suffix}"
            )
            self.assertIn(
                "ADISCORD_vorkerland_absorb_wtd_after_reunification = yes", formation
            )
            self.assertLess(
                formation.index(
                    "ADISCORD_vorkerland_absorb_wtd_after_reunification = yes"
                ),
                formation.index("ADISCORD_vorkerland_finalize_unified_territory = yes"),
            )

    def test_tva_no_longer_recreates_oitfort_puppet(self):
        effects = read("common/scripted_effects/ADISCORD_vorkerland_effects.txt")
        formation = named_block(effects, "ADISCORD_vorkerland_settle_unification_under_tva")
        self.assertNotIn("puppet = WTD", formation)
        self.assertNotIn("target = WTD autonomy_state = autonomy_puppet", formation)

    def test_reunification_requires_wtd_to_be_gone(self):
        triggers = read("common/scripted_triggers/ADISCORD_vorkerland_triggers.txt")
        reunified = named_block(triggers, "ADISCORD_vorkerland_reunification_verified")
        self.assertIn("NOT = { country_exists = WTD }", reunified)

    def test_startup_does_not_migrate_old_reunifications(self):
        on_actions = read_country_on_actions(
            "common/on_actions/01_ADISCORD_vorkerland_collapse_on_actions.txt",
            'vorkerland_collapse',
        )
        startup = named_block(on_actions, "on_startup")
        self.assertNotIn("ADISCORD_vorkerland_absorb_wtd_after_reunification", startup)
        self.assertNotIn("ADISCORD_vorkerland_wtd_terminal_cleanup_v1", startup)

    def test_postwar_core_decision_describes_automatic_absorption(self):
        decisions = read("common/decisions/ADISCORD_vorkerland_decisions.txt")
        decision = named_block(decisions, "ADISCORD_vorkerland_restore_core_oitfort")
        self.assertIn("owns_state = 34", decision)
        self.assertIn(f"34 = {{ add_core_of = {NATION_TARGET} }}", decision)
        # `allowed` admits the claimant tags because any of them can become
        # the unified country; `visible` keeps a wartime claimant out.
        self.assertIn(
            "allowed = { OR = { tag = WRK tag = WKR tag = VAD tag = TVA } }", decision
        )
        visible = named_block(decision, "visible")
        self.assertIn("ADISCORD_vorkerland_is_not_wartime_claimant = yes", visible)
        self.assertIn(
            "has_global_flag = ADISCORD_vorkerland_reunification_verified", visible
        )
        localisation = read("localisation/russian/ADISCORD_vorkerland_l_russian.yml")
        self.assertIn("Ойтфорт уже включён в объединённый Воркерланд", localisation)


if __name__ == "__main__":
    unittest.main()
