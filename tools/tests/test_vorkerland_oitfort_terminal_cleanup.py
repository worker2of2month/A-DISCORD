"""Regression contract: Oitfort is wartime-only and is absorbed by terminal WRK."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]


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
                return text[start:index + 1]
    raise AssertionError(f"unclosed block {name}")


class OitfortTerminalCleanupTests(unittest.TestCase):
    def test_terminal_wrk_absorbs_oitfort_in_all_routes(self):
        effects = read("common/scripted_effects/ADISCORD_vorkerland_effects.txt")
        absorb = named_block(effects, "ADISCORD_vorkerland_absorb_wtd_after_reunification")
        for token in (
            "country_exists = WTD",
            "WTD = { is_ai = no }",
            "change_tag_from = WTD",
            "annex_country = { target = WTD transfer_troops = yes }",
            "34 = { remove_core_of = WTD",
            "set_state_controller_to = WRK",
        ):
            self.assertIn(token, absorb)

        for suffix in ("wkr", "vad", "tva"):
            formation = named_block(effects, f"ADISCORD_vorkerland_form_wrk_from_{suffix}")
            self.assertIn("ADISCORD_vorkerland_absorb_wtd_after_reunification = yes", formation)
            self.assertLess(
                formation.index("ADISCORD_vorkerland_absorb_wtd_after_reunification = yes"),
                formation.index("ADISCORD_vorkerland_finalize_wrk_formation = yes"),
            )

    def test_tva_no_longer_recreates_oitfort_puppet(self):
        effects = read("common/scripted_effects/ADISCORD_vorkerland_effects.txt")
        formation = named_block(effects, "ADISCORD_vorkerland_form_wrk_from_tva")
        self.assertNotIn("puppet = WTD", formation)
        self.assertNotIn("target = WTD autonomy_state = autonomy_puppet", formation)

    def test_reunification_requires_wtd_to_be_gone(self):
        triggers = read("common/scripted_triggers/ADISCORD_vorkerland_triggers.txt")
        reunified = named_block(triggers, "ADISCORD_vorkerland_reunification_verified")
        self.assertIn("NOT = { country_exists = WTD }", reunified)

    def test_old_save_reconciles_wtd_on_startup(self):
        on_actions = read("common/on_actions/01_ADISCORD_vorkerland_collapse_on_actions.txt")
        startup = named_block(on_actions, "on_startup")
        for token in (
            "has_global_flag = ADISCORD_vorkerland_reunification_verified",
            "country_exists = WRK",
            "country_exists = WTD",
            "WRK = { ADISCORD_vorkerland_absorb_wtd_after_reunification = yes }",
            "ADISCORD_vorkerland_wtd_terminal_cleanup_v1",
        ):
            self.assertIn(token, startup)

    def test_postwar_core_decision_describes_automatic_absorption(self):
        decisions = read("common/decisions/ADISCORD_vorkerland_decisions.txt")
        decision = named_block(decisions, "ADISCORD_vorkerland_restore_core_oitfort")
        self.assertIn("owns_state = 34", decision)
        self.assertIn("34 = { add_core_of = WRK }", decision)
        localisation = read("localisation/russian/ADISCORD_vorkerland_l_russian.yml")
        self.assertIn("Ойтфорт уже включён в объединённый Воркерланд", localisation)


if __name__ == "__main__":
    unittest.main()
