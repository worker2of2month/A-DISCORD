import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class RuntimeCompatibilityTests(unittest.TestCase):
    def test_civil_war_relative_positions_resolve_in_load_order(self):
        from tools.validators.validate_adiscord_division_templates import parse_clausewitz

        source = (ROOT / "common/national_focus/ADISCORD_STP_civil_war.txt").read_text(encoding="utf-8")
        tree = next(entry.value for entry in parse_clausewitz(source) if entry.key == "focus_tree")
        loaded = set()
        for entry in tree:
            if entry.key != "focus":
                continue
            fields = {field.key: field.value for field in entry.value}
            if "relative_position_id" in fields:
                self.assertIn(fields["relative_position_id"], loaded, fields["id"])
            loaded.add(fields["id"])

    def test_nod_revolutionary_character_is_dormant_until_the_settlement(self):
        from tools.validators.validate_adiscord_division_templates import parse_clausewitz

        history = (ROOT / "history/countries/NOD - Nodral.txt").read_text(encoding="utf-8")
        recruits = [entry.value for entry in parse_clausewitz(history) if entry.key == "recruit_character"]
        self.assertEqual(recruits.count("NOD_Edgar_Renner"), 1)
        self.assertIn("NOD_Tobis_Bentlix", recruits)
        characters = (ROOT / "common/characters/NOD.txt").read_text(encoding="utf-8")
        definitions = {entry.key: entry.value for entry in parse_clausewitz(characters)[0].value}
        self.assertNotIn("country_leader", {entry.key for entry in definitions["NOD_Edgar_Renner"]})
        self.assertIn("country_leader", {entry.key for entry in definitions["NOD_Tobis_Bentlix"]})
        effects = (ROOT / "common/scripted_effects/ADISCORD_STP_scripted_effects.txt").read_text(encoding="utf-8")
        self.assertNotIn("recruit_character = NOD_Edgar_Renner", effects)
        self.assertIn("character = NOD_Edgar_Renner", effects)

    def test_used_subunit_modifiers_are_registered_after_vanilla_replacement(self):
        from tools.validators.validate_adiscord_division_templates import parse_clausewitz

        registered = set()
        for path in (ROOT / "common/units/unit_modifiers").glob("*.txt"):
            for container in parse_clausewitz(path.read_text(encoding="utf-8-sig")):
                if container.key == "sub_unit_modifiers":
                    registered.update(entry.value for entry in container.value)
        used = set()
        for path in (ROOT / "common").rglob("*.txt"):
            text = re.sub(r"#[^\n]*", "", path.read_text(encoding="utf-8-sig"))
            used.update(re.findall(r"\b(modifier_army_sub_unit_\w+)\s*=", text))
        self.assertFalse(used - registered, sorted(used - registered))

    def test_idea_tokens_cannot_be_parsed_as_scoped_variables(self):
        from tools.validators.validate_adiscord_division_templates import parse_clausewitz
        from tools.tests.test_adiscord_stp_preparation import walk

        invalid = []
        defined = set()
        for path in (ROOT / "common/ideas").glob("*.txt"):
            for root in parse_clausewitz(path.read_text(encoding="utf-8-sig")):
                if root.key != "ideas":
                    continue
                for category in root.value:
                    if not isinstance(category.value, list):
                        continue
                    for idea in category.value:
                        if isinstance(idea.value, list):
                            defined.add(idea.key)
                            if "." in idea.key:
                                invalid.append(f"{path.name}: {idea.key}")
        self.assertFalse(invalid, invalid)
        events = (ROOT / "events/ADISCORD_STP_events.txt").read_text(encoding="utf-8")
        for entry in walk(parse_clausewitz(events)):
            if entry.key == "add_idea" and isinstance(entry.value, str):
                self.assertIn(entry.value, defined)

    def test_small_country_oobs_receive_common_equipment_before_loading(self):
        for tag in ("IVN", "WIT", "BTL", "RUS"):
            path = next((ROOT / "history/countries").glob(f"{tag} - *.txt"))
            history = path.read_text(encoding="utf-8-sig")
            grant = "ADISCORD_grant_technology_profile_common = yes"
            self.assertIn(grant, history, tag)
            self.assertLess(history.index(grant), history.index("oob ="), tag)

    def test_land_unit_map_icons_use_native_categories(self):
        from tools.validators.validate_adiscord_division_templates import parse_clausewitz

        path = ROOT / "common/units/ADISCORD_land_units.txt"
        units = next(
            entry.value for entry in parse_clausewitz(path.read_text(encoding="utf-8"))
            if entry.key == "sub_units"
        )
        for unit in units:
            for field in unit.value:
                if field.key == "map_icon_category":
                    self.assertIn(field.value, {"infantry", "armored", "other"}, unit.key)

    def test_rus_starting_air_wings_have_an_owned_state_air_base(self):
        from tools.validators.validate_adiscord_division_templates import parse_clausewitz

        air_bases = set()
        for path in (ROOT / "history/states").glob("*.txt"):
            state = next(
                entry.value for entry in parse_clausewitz(path.read_text(encoding="utf-8-sig"))
                if entry.key == "state"
            )
            fields = {entry.key: entry.value for entry in state}
            history = {entry.key: entry.value for entry in fields.get("history", [])}
            buildings = {entry.key: entry.value for entry in history.get("buildings", [])}
            if history.get("owner") == "RUS" and int(buildings.get("air_base", 0)) > 0:
                air_bases.add(fields["id"])
        source = (ROOT / "history/units/RUS.txt").read_text(encoding="utf-8")
        wings = next(entry.value for entry in parse_clausewitz(source) if entry.key == "air_wings")
        self.assertTrue(wings)
        for location in wings:
            self.assertIn(location.key, air_bases)

    def test_nam_starting_fleet_uses_a_built_nam_port(self):
        ports = set()
        for path in (ROOT / "history/states").glob("*.txt"):
            text = path.read_text(encoding="utf-8-sig")
            if re.search(r"\bowner\s*=\s*NAM\b", text):
                ports.update(
                    re.findall(r"\b(\d+)\s*=\s*\{\s*naval_base\s*=\s*[1-9]", text)
                )
        oob = (ROOT / "history/units/NAM.txt").read_text(encoding="utf-8")
        for port in re.findall(r"\bnaval_base\s*=\s*(\d+)", oob):
            self.assertIn(port, ports)

    def test_main_menu_music_resolves_inside_music_replacement(self):
        assets = "\n".join(
            path.read_text(encoding="utf-8-sig")
            for path in (ROOT / "music").glob("*.asset")
        )
        theme = re.search(r'name\s*=\s*"maintheme"\s+file\s*=\s*"([^"]+)"', assets)
        self.assertIsNotNone(
            theme, "native main-menu music must have an explicit asset"
        )
        self.assertTrue((ROOT / "music" / theme[1]).is_file())

    def test_operation_phase_references_resolve_in_effective_database(self):
        from tools.tests.test_adiscord_stp_preparation import entries, walk

        base = Path(r"Z:\SteamLibrary\steamapps\common\Hearts of Iron IV")
        descriptor = (ROOT / "descriptor.mod").read_text(encoding="utf-8")
        phases = {}
        if 'replace_path="common/operation_phases"' not in descriptor:
            phases.update(
                {
                    path.name: path
                    for path in (base / "common/operation_phases").glob("*.txt")
                }
            )
        phases.update(
            {
                path.name: path
                for path in (ROOT / "common/operation_phases").glob("*.txt")
            }
        )
        defined = {
            entry.key for path in phases.values() for entry in entries(str(path))
        }
        used = {
            child.key
            for path in (ROOT / "common/operations").glob("*.txt")
            for entry in walk(entries(str(path)))
            if entry.key == "phases"
            for child in entry.value
        }
        self.assertFalse(used - defined, sorted(used - defined))

    def test_val_focus_unlocks_and_ultimatum_resolve(self):
        from tools.tests.test_adiscord_stp_preparation import entries

        decisions = {
            entry.key
            for category in entries("common/decisions/ADISCORD_VAL_decisions.txt")
            for entry in category.value
        }
        required = {
            "VAL_subcontract_quarterly_norm",
            "VAL_negotiate_yubora",
            "VAL_nod_ultimatum",
            "VAL_final_register_reserves",
            "VAL_final_stockpile_supplies",
            "VAL_final_reconnaissance",
        }
        self.assertFalse(required - decisions, sorted(required - decisions))

    def test_stp_decision_effects_and_categories_resolve(self):
        effects = (
            ROOT / "common/scripted_effects/ADISCORD_STP_scripted_effects.txt"
        ).read_text(encoding="utf-8-sig")
        for name in (
            "STP_cw_raise_rear_cell",
            "STP_cw_mobilize_volunteer_brigade",
            "NOD_cw_exhaust_northern_push",
            "STP_receive_6000",
        ):
            with self.subTest(effect=name):
                self.assertTrue(re.search(rf"(?m)^{name}\s*=\s*\{{", effects), name)
        categories = "\n".join(
            p.read_text(encoding="utf-8-sig")
            for p in (ROOT / "common/decisions/categories").glob("*.txt")
        )
        self.assertTrue(
            re.search(r"(?m)^STP_hegemony_administration\s*=\s*\{", categories)
        )

    def test_highlight_state_targets_are_flat_state_lists(self):
        from tools.tests.test_adiscord_stp_preparation import entries, walk

        for path in (ROOT / "common/decisions").glob("ADISCORD*.txt"):
            for item in walk(entries(str(path.relative_to(ROOT)))):
                if item.key == "highlight_state_targets":
                    with self.subTest(file=path.name):
                        self.assertTrue(
                            all(
                                child.key == "state"
                                and isinstance(child.value, str)
                                and (
                                    child.value.isdigit()
                                    or child.value in ("FROM", "ROOT", "PREV")
                                )
                                for child in item.value
                            )
                        )

    def test_event_picture_extension_keeps_the_vanilla_database(self):
        self.assertFalse((ROOT / "interface" / "eventpictures.gfx").exists())
        extension = (ROOT / "interface" / "ADISCORD_eventpictures.gfx").read_text(
            encoding="utf-8-sig"
        )
        event_window = (ROOT / "interface" / "eventwindow.gui").read_text(
            encoding="utf-8-sig"
        )

        self.assertIn('name = "GFX_report_event_generic_diplomacy"', extension)
        self.assertIn('name = "GFX_report_event_political"', extension)
        self.assertIn('spriteType = "GFX_report_event_001"', event_window)

    def test_diplomacy_override_contains_no_generator_markers(self):
        diplomacy = (ROOT / "interface" / "countrydiplomacyview.gui").read_text(
            encoding="utf-8-sig"
        )

        self.assertNotIn("__ADISCORD_DIPLOMACY_GUI_APPEND_MARKER_019F__", diplomacy)
        self.assertEqual(diplomacy.count("{"), diplomacy.count("}"))

    def test_ncns_tactic_subunits_and_dynamic_tokens_exist(self):
        units = (ROOT / "common" / "units" / "ADISCORD_ncns_unit_compat.txt").read_text(
            encoding="utf-8-sig"
        )
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
        technologies = (ROOT / "interface" / "ADISCORD_technologies.gfx").read_text(
            encoding="utf-8-sig"
        )
        self.assertNotRegex(technologies, r"(?m)^\s*scale\s*=")

        mio = (ROOT / "interface" / "ADISCORD_mio_equipment_groups.gfx").read_text(
            encoding="utf-8-sig"
        )
        for sprite in (
            "GFX_military_industrial_organization_ADISCORD_squad_weapons_equipment",
            "GFX_military_industrial_organization_ADISCORD_fighter_archetype",
            "GFX_military_industrial_organization_ADISCORD_cas_archetype",
        ):
            self.assertIn(f'name = "{sprite}"', mio)

        subunit_icons = (ROOT / "interface" / "ADISCORD_subuniticons.gfx").read_text(
            encoding="utf-8-sig"
        )
        self.assertIn(
            'name = "GFX_unit_ADISCORD_tactical_bomber_icon_small"', subunit_icons
        )
        self.assertIn(
            'texturefile = "gfx/texticons/unit_tactical_bomber_icon_small.dds"',
            subunit_icons,
        )

    def test_viceroy_focus_has_no_hot_reload_only_scripted_effect(self):
        focus = (
            ROOT / "common" / "national_focus" / "ADISCORD_national_focus_VAL.txt"
        ).read_text(encoding="utf-8-sig")
        effects = (
            ROOT / "common" / "scripted_effects" / "ADISCORD_VAL_effects.txt"
        ).read_text(encoding="utf-8-sig")
        events = (ROOT / "events" / "ADISCORD_VAL_contract_events.txt").read_text(
            encoding="utf-8-sig"
        )
        for text in (focus, effects, events):
            self.assertNotIn("VAL_commit_nam_resource_aid", text)
        self.assertIn("VAL_start_resource_aid = yes", focus)
        self.assertIn("VAL_start_resource_aid = yes", events)

    def test_reclamation_ui_does_not_call_state_only_trigger_from_country_refresh(self):
        decisions = (
            ROOT / "common" / "decisions" / "ADISCORD_VAL_decisions.txt"
        ).read_text(encoding="utf-8-sig")
        self.assertNotIn(
            "hidden_trigger = { VAL_reclamation_project_target_valid = yes }",
            decisions,
        )
        self.assertGreaterEqual(
            decisions.count("FROM = { is_owned_by = ROOT is_controlled_by = ROOT }"), 3
        )

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
