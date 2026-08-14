from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BASE_GAME = Path(r"Z:\SteamLibrary\steamapps\common\Hearts of Iron IV")


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8-sig")


def named_block(text: str, name: str) -> str:
    match = re.search(rf"(?m)^\s*{re.escape(name)}\s*=\s*\{{", text)
    if not match:
        raise AssertionError(f"missing block {name}")
    opening = text.find("{", match.start())
    depth = 0
    in_quote = False
    escaped = False
    for index in range(opening, len(text)):
        char = text[index]
        if char == "\\" and in_quote and not escaped:
            escaped = True
            continue
        if char == '"' and not escaped:
            in_quote = not in_quote
        if not in_quote:
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    return text[opening + 1 : index]
        escaped = False
    raise AssertionError(f"unterminated block {name}")


def named_blocks(text: str, name: str) -> list[str]:
    blocks: list[str] = []
    pattern = re.compile(rf"(?m)^\s*{re.escape(name)}\s*=\s*\{{")
    for match in pattern.finditer(text):
        opening = text.find("{", match.start())
        depth = 0
        in_quote = False
        escaped = False
        for index in range(opening, len(text)):
            char = text[index]
            if char == "\\" and in_quote and not escaped:
                escaped = True
                continue
            if char == '"' and not escaped:
                in_quote = not in_quote
            if not in_quote:
                if char == "{":
                    depth += 1
                elif char == "}":
                    depth -= 1
                    if depth == 0:
                        blocks.append(text[opening + 1 : index])
                        break
            escaped = False
        else:
            raise AssertionError(f"unterminated block {name}")
    return blocks


def event_block(text: str, event_id: str) -> str:
    for block in named_blocks(text, "country_event"):
        if re.search(rf"\bid\s*=\s*{re.escape(event_id)}\b", block):
            return block
    raise AssertionError(f"missing event {event_id}")


class VorkerlandForceDesignTests(unittest.TestCase):
    def test_collapse_has_a_reachable_20_width_armored_template(self) -> None:
        templates = read("common/ai_templates/ADISCORD_land_templates.txt")
        block = named_block(templates, "ADISCORD_vorkerland_mobile_reserve")
        for token in (
            "tag = WKR",
            "tag = VAD",
            "tag = TVA",
            "has_global_flag = ADISCORD_vorkerland_collapse_wars_started",
            "NOT = { has_global_flag = ADISCORD_vorkerland_collapse_finished }",
            "has_tech = ADISCORD_tech_semi_autonomous_combat_modules",
            "num_of_military_factories > 2",
        ):
            self.assertIn(token, block)
        target = named_block(block, "target_template")
        self.assertRegex(target, r"regiments\s*=\s*\{[^{}]*infantry\s*=\s*6")
        self.assertRegex(
            target,
            r"regiments\s*=\s*\{[^{}]*ADISCORD_combat_platform\s*=\s*4",
        )
        for support in ("engineer", "artillery", "maintenance_company", "signal_company"):
            self.assertRegex(target, rf"\b{support}\s*=\s*1")

    def test_all_ai_armored_designs_use_20_width_line_battalions(self) -> None:
        templates = read("common/ai_templates/ADISCORD_land_templates.txt")
        expected = {
            "ADISCORD_vorkerland_mobile_reserve": "ADISCORD_combat_platform",
            "ADISCORD_tank_battlegroup": "ADISCORD_combat_platform",
            "ADISCORD_networked_tank_battlegroup": "ADISCORD_combat_platform",
            "ADISCORD_heavy_tank_battlegroup": "ADISCORD_heavy_platform",
        }
        for design, platform in expected.items():
            target = named_block(named_block(templates, design), "target_template")
            self.assertRegex(target, r"regiments\s*=\s*\{[^{}]*infantry\s*=\s*6")
            self.assertRegex(
                target,
                rf"regiments\s*=\s*\{{[^{{}}]*{platform}\s*=\s*4",
            )

    def test_all_claimants_start_with_the_same_full_armored_group(self) -> None:
        expected = {
            "history/units/WRK.txt": "Workerland Mobile Group",
            "history/units/VAD.txt": "Armi Mobile Group",
            "history/units/TVA_vorkerland_collapse.txt": "TVA Mobile Test Group",
        }
        for relative, template_name in expected.items():
            templates = named_blocks(read(relative), "division_template")
            block = next(
                (
                    candidate
                    for candidate in templates
                    if f'name = "{template_name}"' in candidate
                ),
                None,
            )
            self.assertIsNotNone(block, f"missing {template_name} in {relative}")
            self.assertEqual(block.count("ADISCORD_combat_platform = {"), 4)
            self.assertEqual(block.count("infantry = {"), 6)
            for support in (
                "engineer",
                "artillery",
                "maintenance_company",
                "signal_company",
            ):
                self.assertEqual(block.count(f"{support} = {{"), 1)

    def test_collapse_deliveries_can_equip_the_armored_groups(self) -> None:
        effects = read("common/scripted_effects/ADISCORD_vorkerland_collapse_effects.txt")
        setup = named_block(effects, "ADISCORD_vorkerland_prepare_initial_combatants")
        for tag in ("WKR", "VAD"):
            claimant = named_block(setup, tag)
            for delivery in (
                f"type = ADISCORD_combat_platform_2170 amount = 180 producer = {tag}",
                f"type = ADISCORD_squad_weapons_equipment_0 amount = 60 producer = {tag}",
                f"type = support_equipment_1 amount = 100 producer = {tag}",
                f"type = artillery_equipment_1 amount = 24 producer = {tag}",
            ):
                self.assertIn(delivery, claimant)

        tva = named_block(effects, "ADISCORD_vorkerland_setup_tva")
        self.assertIn(
            "type = ADISCORD_combat_platform_2170 amount = 180 producer = TVA",
            tva,
        )
        self.assertIn(
            "type = ADISCORD_squad_weapons_equipment_0 amount = 60 producer = TVA",
            tva,
        )

    def test_collapse_ai_sustains_armor_and_fighter_production(self) -> None:
        strategies = read(
            "common/ai_strategy/ADISCORD_vorkerland_force_design_ai.txt"
        )
        armor = named_block(
            strategies, "ADISCORD_vorkerland_armored_reserve_program"
        )
        air = named_block(strategies, "ADISCORD_vorkerland_air_denial_program")
        wkr_air = named_block(
            strategies, "ADISCORD_vorkerland_wkr_air_denial_program"
        )
        operations = named_block(
            strategies, "ADISCORD_vorkerland_active_air_operations"
        )
        for tag in ("WKR", "VAD", "TVA"):
            self.assertIn(f"tag = {tag}", armor)
            self.assertIn(f"tag = {tag}", operations)
        self.assertNotIn("tag = WKR", air)
        for tag in ("VAD", "TVA"):
            self.assertIn(f"tag = {tag}", air)
        self.assertIn("allowed = { tag = WKR }", wkr_air)
        self.assertNotIn("tag = VAD", wkr_air)
        self.assertNotIn("tag = TVA", wkr_air)
        self.assertIn(
            "equipment_production_min_factories_archetype id = "
            "ADISCORD_combat_platform_archetype value = 1",
            armor,
        )
        self.assertIn("equipment_production_min_factories id = fighter value = 1", air)
        self.assertIn("equipment_production_min_factories id = cas value = 1", air)
        self.assertIn(
            "equipment_production_min_factories id = fighter value = 2", wkr_air
        )
        self.assertIn(
            "equipment_production_min_factories id = cas value = 1", wkr_air
        )
        self.assertIn(
            "equipment_variant_production_factor id = ADISCORD_fighter_archetype",
            air,
        )
        self.assertIn(
            "equipment_variant_production_factor id = ADISCORD_fighter_archetype",
            wkr_air,
        )
        self.assertIn(
            "type = strategic_air_importance id = 12 value = 100000", operations
        )
        self.assertIn(
            "type = strategic_air_importance id = 9 value = 100000", operations
        )
        self.assertIn("has_war = yes", operations)
        self.assertNotIn("num_of_military_factories", operations)
        self.assertNotIn("has_tech", operations)
        self.assertNotIn("strategic_air_importance", air)

    def test_air_subunit_roles_use_the_engine_scalar_contract(self) -> None:
        air_units = read("common/units/ADISCORD_air_units.txt")
        expected = {
            "fighter": "fighter",
            "cas": "cas",
            "tac_bomber": "tactical_bomber",
        }
        for subunit, role in expected.items():
            block = named_block(air_units, subunit)
            self.assertRegex(block, rf"(?m)^\s*type\s*=\s*{role}\s*$")
            self.assertNotRegex(block, rf"type\s*=\s*\{{\s*{role}\s*\}}")

    def test_custom_aircraft_have_personnel_and_combat_missions(self) -> None:
        equipment = read("common/units/equipment/ADISCORD_air_equipment.txt")
        archetypes = {
            "ADISCORD_fighter_archetype": 20,
            "ADISCORD_cas_archetype": 20,
            "ADISCORD_rocket_strike_archetype": 40,
        }
        for archetype, manpower in archetypes.items():
            block = named_block(equipment, archetype)
            self.assertRegex(block, rf"(?m)^\s*manpower\s*=\s*{manpower}\s*$")
            self.assertRegex(
                block, r"(?m)^\s*allow_mission_type\s*=\s*training\s*$"
            )

        missions = {
            "ADISCORD_fighter_airframe_2163": {"air_superiority", "interception"},
            "ADISCORD_cas_airframe_2170": {"cas", "attack_logistics"},
            "ADISCORD_rocket_strike_platform_2183": {"strategic_bomber"},
        }
        for model, expected in missions.items():
            mission_block = named_block(
                named_block(equipment, model), "allow_mission_type"
            )
            self.assertEqual(set(re.findall(r"\b[A-Za-z_]+\b", mission_block)), expected)

    def test_claimants_receive_visible_fighter_and_cas_wings(self) -> None:
        expected = {
            "WKR": (
                "history/units/WRK_vorkerland_collapse_air.txt",
                "WRK_vorkerland_collapse_air",
                "32",
                2,
                2,
            ),
            "VAD": (
                "history/units/VAD_vorkerland_collapse_air.txt",
                "VAD_vorkerland_collapse_air",
                "75",
                1,
                1,
            ),
            "TVA": (
                "history/units/TVA_vorkerland_collapse_air.txt",
                "TVA_vorkerland_collapse_air",
                "38",
                1,
                1,
            ),
        }
        for tag, (relative, _, state, fighter_wings, cas_wings) in expected.items():
            wings = named_block(read(relative), "air_wings")
            airfield = named_block(wings, state)
            self.assertEqual(
                airfield.count(
                    f'ADISCORD_fighter_airframe_2163 = {{ owner = "{tag}" amount = 100 }}'
                ),
                fighter_wings,
            )
            self.assertEqual(
                airfield.count(
                    f'ADISCORD_cas_airframe_2170 = {{ owner = "{tag}" amount = 50 }}'
                ),
                cas_wings,
            )

        collapse = read("common/scripted_effects/ADISCORD_vorkerland_collapse_effects.txt")
        initial = named_block(collapse, "ADISCORD_vorkerland_prepare_initial_combatants")
        wkr = named_block(initial, "WKR")
        vad = named_block(initial, "VAD")
        self.assertIn('load_oob = "WRK_vorkerland_collapse_air"', wkr)
        self.assertIn('load_oob = "VAD_vorkerland_collapse_air"', vad)
        self.assertIn("add_fuel = 15000", wkr)
        self.assertIn("add_fuel = 7500", vad)
        self.assertIn(
            "type = ADISCORD_fighter_airframe_2163 amount = 60 producer = WKR",
            wkr,
        )
        self.assertIn(
            "type = ADISCORD_cas_airframe_2170 amount = 30 producer = WKR",
            wkr,
        )
        self.assertIn(
            "set_country_flag = ADISCORD_vorkerland_wkr_air_sustainment_v1_applied",
            wkr,
        )
        self.assertNotIn("add_equipment_production", wkr)
        for technology in (
            "ADISCORD_tech_semi_autonomous_combat_modules = 1",
            "ADISCORD_tech_reclaimed_jet_platforms = 1",
            "ADISCORD_tech_battlefield_attack_aircraft = 1",
        ):
            self.assertIn(technology, wkr)
            self.assertLess(
                wkr.index(technology),
                wkr.index(
                    "type = ADISCORD_fighter_airframe_2163 amount = 60 producer = WKR"
                ),
            )
            self.assertLess(
                wkr.index(technology),
                wkr.index('load_oob = "WRK_vorkerland_collapse_air"'),
            )
        tva_setup = named_block(collapse, "ADISCORD_vorkerland_setup_tva")
        self.assertIn('load_oob = "TVA_vorkerland_collapse_air"', tva_setup)
        self.assertIn("add_fuel = 7500", tva_setup)
        for setup in (wkr, vad, tva_setup):
            self.assertIn(
                "set_country_flag = ADISCORD_vorkerland_air_mission_contract_v2_applied",
                setup,
            )

        force_design_effects = read(
            "common/scripted_effects/ADISCORD_vorkerland_force_design_effects.txt"
        )
        for legacy_repair in (
            "ADISCORD_vorkerland_deploy_missing_claimant_air_wings",
            "ADISCORD_vorkerland_redeploy_air_wings_after_mission_fix",
        ):
            self.assertNotIn(legacy_repair, force_design_effects)

    def test_fresh_outbreak_runs_one_bounded_ai_bootstrap_per_claimant(self) -> None:
        effects = read(
            "common/scripted_effects/ADISCORD_vorkerland_force_design_effects.txt"
        )
        block = named_block(effects, "ADISCORD_vorkerland_bootstrap_ai_force_designs")
        self.assertIn("is_ai = yes", block)
        self.assertIn(
            "NOT = { has_country_flag = ADISCORD_vorkerland_force_designs_bootstrapped }",
            block,
        )
        self.assertEqual(
            block.count(
                "set_country_flag = ADISCORD_vorkerland_force_designs_bootstrapped"
            ),
            1,
        )
        self.assertIn("ADISCORD_tech_semi_autonomous_combat_modules = 1", block)
        self.assertIn("ADISCORD_tech_reclaimed_jet_platforms = 1", block)
        self.assertIn("ADISCORD_tech_battlefield_attack_aircraft = 1", block)
        self.assertIn("type = ADISCORD_combat_platform_2170", block)
        self.assertIn("ADISCORD_combat_platform_archetype < 120", block)
        self.assertIn("amount = 160", block)
        for equipment_id, amount in (
            ("infantry_equipment_0", 500),
            ("ADISCORD_squad_weapons_equipment_0", 40),
            ("support_equipment_1", 80),
            ("artillery_equipment_1", 12),
        ):
            self.assertIn(f"type = {equipment_id}", block)
            self.assertIn(f"amount = {amount}", block)
        self.assertIn("type = ADISCORD_fighter_airframe_2163", block)
        self.assertIn("type = ADISCORD_cas_airframe_2170", block)
        on_actions = read(
            "common/on_actions/01_ADISCORD_vorkerland_collapse_on_actions.txt"
        )
        self.assertNotIn("on_weekly =", on_actions)
        events = read("events/ADISCORD_vorkerland_collapse_events.txt")
        outbreak = event_block(events, "ADISCORD_vorkerland_collapse.2")
        wartime = outbreak.index(
            "set_global_flag = ADISCORD_vorkerland_collapse_wars_started"
        )
        for tag in ("WKR", "VAD", "TVA"):
            call = (
                f"{tag} = {{ ADISCORD_vorkerland_bootstrap_ai_force_designs = yes }}"
            )
            self.assertEqual(outbreak.count(call), 1)
            self.assertLess(wartime, outbreak.index(call))


class EquipmentPictureTests(unittest.TestCase):
    def test_every_custom_subunit_has_designer_and_onmap_icons(self) -> None:
        units = read("common/units/ADISCORD_land_units.txt")
        subunit_keys = set(
            re.findall(r"(?m)^\s*(ADISCORD_[A-Za-z0-9_]+)\s*=\s*\{", units)
        )
        sprites = read("interface/ADISCORD_subuniticons.gfx")
        sprite_blocks = {
            name: block
            for block, name in re.findall(
                r'spriteType\s*=\s*\{([^{}]*?name\s*=\s*"([^"]+)"[^{}]*?)\}',
                sprites,
                flags=re.DOTALL,
            )
        }

        missing: list[str] = []
        missing_textures: list[str] = []
        for key in sorted(subunit_keys):
            for suffix in ("medium", "medium_white"):
                sprite_name = f"GFX_unit_{key}_icon_{suffix}"
                block = sprite_blocks.get(sprite_name)
                if block is None:
                    missing.append(sprite_name)
                    continue
                texture_match = re.search(
                    r'texturefile\s*=\s*"([^"]+)"', block, flags=re.IGNORECASE
                )
                self.assertIsNotNone(texture_match, sprite_name)
                texture = Path(texture_match.group(1).replace("/", "\\"))
                if not (ROOT / texture).exists() and not (BASE_GAME / texture).exists():
                    missing_textures.append(f"{sprite_name}: {texture_match.group(1)}")

        self.assertEqual(missing, [], f"missing custom subunit sprites: {missing}")
        self.assertEqual(
            missing_textures,
            [],
            f"missing custom subunit textures: {missing_textures}",
        )

        combat = sprite_blocks["GFX_unit_ADISCORD_combat_platform_icon_medium"]
        self.assertIn("unit_medium_tank_icon.dds", combat)
        combat_white = sprite_blocks[
            "GFX_unit_ADISCORD_combat_platform_icon_medium_white"
        ]
        self.assertIn("onmap_unit_medium_tank_icon.dds", combat_white)

    def test_every_custom_equipment_picture_has_a_case_exact_sprite(self) -> None:
        picture_keys: set[str] = set()
        for path in (ROOT / "common" / "units" / "equipment").glob(
            "ADISCORD_*.txt"
        ):
            picture_keys.update(
                re.findall(r"\bpicture\s*=\s*([A-Za-z0-9_]+)", path.read_text(encoding="utf-8-sig"))
            )

        gfx_text = "\n".join(
            path.read_text(encoding="utf-8-sig", errors="ignore")
            for path in (ROOT / "interface").rglob("*.gfx")
        )
        if BASE_GAME.exists():
            gfx_text += "\n" + (
                BASE_GAME / "interface" / "Technologies.gfx"
            ).read_text(encoding="utf-8-sig", errors="ignore")
        sprite_names = set(
            re.findall(r'\bname\s*=\s*"(GFX_[A-Za-z0-9_]+_medium)"', gfx_text)
        )
        missing = sorted(
            key for key in picture_keys if f"GFX_{key}_medium" not in sprite_names
        )
        self.assertEqual(missing, [], f"unresolved equipment picture keys: {missing}")

    def test_buildable_air_and_armor_models_have_explicit_pictures(self) -> None:
        expected = {
            "ADISCORD_fighter_airframe_2163": "archetype_fighter_equipment",
            "ADISCORD_interceptor_airframe_2183": "archetype_fighter_equipment",
            "ADISCORD_cas_airframe_2170": "archetype_CAS_equipment",
            "ADISCORD_vtol_airframe_2170": "archetype_CAS_equipment",
            "ADISCORD_drone_airframe_2183": "archetype_CAS_equipment",
            "ADISCORD_combat_platform_2170": "archetype_medium_tank_equipment",
            "ADISCORD_combat_platform_2183": "archetype_medium_tank_equipment",
            "ADISCORD_combat_platform_2200": "archetype_medium_tank_equipment",
        }
        equipment = read("common/units/equipment/ADISCORD_air_equipment.txt")
        equipment += "\n" + read("common/units/equipment/ADISCORD_armor_equipment.txt")
        for equipment_id, picture in expected.items():
            self.assertIn(f"picture = {picture}", named_block(equipment, equipment_id))

    def test_economy_interface_textures_exist_and_are_valid_dds(self) -> None:
        directory = ROOT / "gfx" / "interface" / "ADISCORD_economy_gui"
        expected = {
            "economy_button.dds",
            "economy_expenses_bg.dds",
            "economy_header_bg.dds",
            "economy_income_bg.dds",
            "economy_loans_bg.dds",
            "economy_slider_button.dds",
            "economy_topbar_button.dds",
            "economy_command_bg.dds",
            "economy_dashboard_bg.dds",
            "economy_kpi_balance_bg.dds",
            "economy_kpi_expenses_bg.dds",
            "economy_kpi_income_bg.dds",
            "economy_kpi_treasury_bg.dds",
            "economy_status_bg.dds",
            "treasury_icon.dds",
        }
        self.assertEqual({path.name for path in directory.glob("*.dds")}, expected)
        for name in expected:
            data = (directory / name).read_bytes()[:20]
            self.assertGreaterEqual(len(data), 20, name)
            self.assertEqual(data[:4], b"DDS ", name)
            self.assertGreater(int.from_bytes(data[12:16], "little"), 0, name)
            self.assertGreater(int.from_bytes(data[16:20], "little"), 0, name)


if __name__ == "__main__":
    unittest.main()
