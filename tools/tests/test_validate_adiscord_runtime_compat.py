import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class RuntimeCompatibilityTests(unittest.TestCase):
    def test_event_picture_extension_keeps_the_vanilla_database(self):
        self.assertFalse((ROOT / "interface" / "eventpictures.gfx").exists())
        extension = (
            ROOT / "interface" / "ADISCORD_eventpictures.gfx"
        ).read_text(encoding="utf-8-sig")
        event_window = (
            ROOT / "interface" / "eventwindow.gui"
        ).read_text(encoding="utf-8-sig")

        self.assertIn('name = "GFX_report_event_generic_diplomacy"', extension)
        self.assertIn('name = "GFX_report_event_political"', extension)
        self.assertIn('spriteType = "GFX_report_event_001"', event_window)

    def test_diplomacy_override_contains_no_generator_markers(self):
        diplomacy = (
            ROOT / "interface" / "countrydiplomacyview.gui"
        ).read_text(encoding="utf-8-sig")

        self.assertNotIn("__ADISCORD_DIPLOMACY_GUI_APPEND_MARKER_019F__", diplomacy)
        self.assertEqual(diplomacy.count("{"), diplomacy.count("}"))

    def test_ncns_tactic_subunits_and_dynamic_tokens_exist(self):
        units = (
            ROOT / "common" / "units" / "ADISCORD_ncns_unit_compat.txt"
        ).read_text(encoding="utf-8-sig")
        tokens = set(
            (ROOT / "common" / "synchronized_dynamic_tokens" / "ADISCORD_tokens.txt")
            .read_text(encoding="utf-8-sig")
            .split()
        )

        for subunit in (
            "light_flame_tank",
            "medium_flame_tank",
            "heavy_flame_tank",
            "pioneer_support",
        ):
            self.assertRegex(units, rf"(?m)^\s*{subunit}\s*=\s*\{{")
        for token in (
            "ADISCORD_squad_weapons_equipment",
            "revoke_guarantee",
            "milacc",
            "offer_milacc",
            "nonaggressionpact",
            "improverelation",
            "release_nation",
            "international_market_access_rights",
        ):
            self.assertIn(token, tokens)

    def test_state_27_shared_factories_fit_its_category(self):
        state = next((ROOT / "history" / "states").glob("27-*.txt"))
        text = state.read_text(encoding="utf-8-sig")
        self.assertRegex(text, r"(?m)^\s*state_category\s*=\s*town\s*$")
        self.assertEqual(
            sum(
                int(level)
                for level in re.findall(
                    r"(?m)^\s*(?:industrial_complex|arms_factory|dockyard)\s*=\s*(\d+)",
                    text,
                )
            ),
            3,
        )


if __name__ == "__main__":
    unittest.main()
