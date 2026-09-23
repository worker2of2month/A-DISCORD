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

    def test_prerelease_runtime_gfx_contracts(self):
        technologies = (ROOT / "interface" / "ADISCORD_technologies.gfx").read_text(encoding="utf-8-sig")
        self.assertNotRegex(technologies, r"(?m)^\s*scale\s*=")

        mio = (ROOT / "interface" / "ADISCORD_mio_equipment_groups.gfx").read_text(encoding="utf-8-sig")
        for sprite in (
            "GFX_military_industrial_organization_ADISCORD_squad_weapons_equipment",
            "GFX_military_industrial_organization_ADISCORD_fighter_archetype",
            "GFX_military_industrial_organization_ADISCORD_cas_archetype",
        ):
            self.assertIn(f'name = "{sprite}"', mio)

        subunit_icons = (ROOT / "interface" / "ADISCORD_subuniticons.gfx").read_text(encoding="utf-8-sig")
        self.assertIn('name = "GFX_unit_ADISCORD_tactical_bomber_icon_small"', subunit_icons)
        self.assertIn('texturefile = "gfx/texticons/unit_tactical_bomber_icon_small.dds"', subunit_icons)

    def test_viceroy_focus_has_no_hot_reload_only_scripted_effect(self):
        focus = (ROOT / "common" / "national_focus" / "ADISCORD_national_focus_VAL.txt").read_text(encoding="utf-8-sig")
        effects = (ROOT / "common" / "scripted_effects" / "ADISCORD_VAL_effects.txt").read_text(encoding="utf-8-sig")
        events = (ROOT / "events" / "ADISCORD_VAL_contract_events.txt").read_text(encoding="utf-8-sig")
        for text in (focus, effects, events):
            self.assertNotIn("VAL_commit_nam_resource_aid", text)
        self.assertIn("VAL_start_resource_aid = yes", focus)
        self.assertIn("VAL_start_resource_aid = yes", events)

    def test_reclamation_ui_does_not_call_state_only_trigger_from_country_refresh(self):
        decisions = (ROOT / "common" / "decisions" / "ADISCORD_VAL_decisions.txt").read_text(encoding="utf-8-sig")
        self.assertNotIn(
            "hidden_trigger = { VAL_reclamation_project_target_valid = yes }",
            decisions,
        )
        self.assertGreaterEqual(decisions.count("FROM = { is_owned_by = ROOT is_controlled_by = ROOT }"), 3)

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
