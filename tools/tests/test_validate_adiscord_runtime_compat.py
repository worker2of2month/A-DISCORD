import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class RuntimeCompatibilityTests(unittest.TestCase):
    def test_val_focus_unlocks_and_ultimatum_resolve(self):
        from tools.tests.test_adiscord_stp_preparation import entries

        decisions = {
            entry.key
            for category in entries("common/decisions/ADISCORD_VAL_decisions.txt")
            for entry in category.value
        }
        required = {
            "VAL_subcontract_quarterly_norm", "VAL_negotiate_yubora", "VAL_nod_ultimatum",
            "VAL_final_register_reserves", "VAL_final_stockpile_supplies", "VAL_final_reconnaissance",
        }
        self.assertFalse(required - decisions, sorted(required - decisions))

    def test_stp_decision_effects_and_categories_resolve(self):
        effects = (ROOT / "common/scripted_effects/ADISCORD_STP_scripted_effects.txt").read_text(encoding="utf-8-sig")
        for name in (
            "STP_cw_raise_rear_cell", "STP_cw_mobilize_volunteer_brigade",
            "NOD_cw_exhaust_northern_push", "STP_receive_6000",
        ):
            with self.subTest(effect=name):
                self.assertTrue(re.search(rf"(?m)^{name}\s*=\s*\{{", effects), name)
        categories = "\n".join(p.read_text(encoding="utf-8-sig") for p in (ROOT / "common/decisions/categories").glob("*.txt"))
        self.assertTrue(re.search(r"(?m)^STP_hegemony_administration\s*=\s*\{", categories))

    def test_highlight_state_targets_are_flat_state_lists(self):
        from tools.tests.test_adiscord_stp_preparation import entries, walk

        for path in (ROOT / "common/decisions").glob("ADISCORD*.txt"):
            for item in walk(entries(str(path.relative_to(ROOT)))):
                if item.key == "highlight_state_targets":
                    with self.subTest(file=path.name):
                        self.assertTrue(all(
                            child.key == "state"
                            and isinstance(child.value, str)
                            and (child.value.isdigit() or child.value in ("FROM", "ROOT", "PREV"))
                            for child in item.value
                        ))

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
        self.assertRegex(text, r"(?m)^\s*state_category\s*=\s*large_town\s*$")
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
