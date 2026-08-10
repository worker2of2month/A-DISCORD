import re
import unittest
from pathlib import Path

from PIL import Image

from tools.builders.build_adiscord_resource_assets import expected_outputs as expected_asset_outputs
from tools.validators.validate_adiscord_division_templates import Entry, parse_clausewitz


ROOT = Path(__file__).resolve().parents[2]

RESOURCES = ROOT / "common/resources/00_resources.txt"
SYNCHRONIZED_TOKENS = ROOT / "common/synchronized_dynamic_tokens/ADISCORD_tokens.txt"
BUILDINGS = ROOT / "common/buildings/00_buildings.txt"
ECONOMY_EFFECTS = ROOT / "common/scripted_effects/ADISCORD_economy_effects.txt"
ECONOMY_GUI_SCRIPT = ROOT / "common/scripted_guis/ADISCORD_economy_scripted_gui.txt"
TOPBAR = ROOT / "interface/topbar.gui"
ALERTS = ROOT / "interface/alerts.gui"
ECONOMY_GUI = ROOT / "interface/ADISCORD_economy.gui"
TRADE_GUI = ROOT / "interface/countrytradeview.gui"
DIPLOMACY_GUI = ROOT / "interface/countrydiplomacyview.gui"
RESOURCE_GFX = ROOT / "interface/general_stuff.gfx"
ECONOMY_GFX = ROOT / "interface/ADISCORD_economy.gfx"
RU_RESOURCES = ROOT / "localisation/russian/ADISCORD_resources_l_russian.yml"
EN_RESOURCES = ROOT / "localisation/english/ADISCORD_resources_l_english.yml"
RU_TRADE_REGIONS = ROOT / "localisation/replace/ADISCORD_trade_regions_l_russian.yml"
EN_TRADE_REGIONS = ROOT / "localisation/replace/ADISCORD_trade_regions_l_english.yml"
RESOURCE_DOC = ROOT / "docs/economy/strategic-resources.md"

RESOURCE_SOURCE = ROOT / "gfx/interface/ADISCORD_trade_gui/source/strategic_resources_source.png"
TRADE_ENTRY_SOURCE = ROOT / "gfx/interface/ADISCORD_trade_gui/source/country_trade_entry_source.png"
TOPBAR_SOURCE = ROOT / "gfx/interface/ADISCORD_trade_gui/source/topbar_glyphs_source.png"
INDICATOR_SOURCE = ROOT / "gfx/interface/ADISCORD_trade_gui/source/topbar_indicators_source.png"
MARKET_SOURCE = ROOT / "gfx/interface/ADISCORD_trade_gui/source/international_market_source.png"
COMMAND_POWER_SOURCE = ROOT / "gfx/interface/ADISCORD_trade_gui/source/command_power_phone_source.png"
TOPBAR_BACKGROUND_SOURCE = ROOT / "gfx/interface/ADISCORD_trade_gui/source/topbar_background_extended_source.png"
TREASURY_SOURCE = ROOT / "gfx/interface/ADISCORD_economy_gui/source/treasury_topbar_source.png"
TOPBAR_GFX = ROOT / "interface/ADISCORD_topbar.gfx"
TRADE_ENTRY_TEXTURE = ROOT / "gfx/interface/ADISCORD_trade_gui/country_trade_entry_bg.dds"
WORLD_TENSION_TEXTURE = ROOT / "gfx/interface/world_tension_icon_big_strip.dds"
WORLD_TENSION_SOURCE = ROOT / "gfx/interface/ADISCORD_trade_gui/source/world_tension_defcon_tfr.dds"

RIGHT_TOPBAR_ASSETS = {
    "gfx/interface/topbar/armyoverview_buttons_bg.dds": (403, 101),
    "gfx/interface/date_pause_button_bg.dds": (206, 28),
    "gfx/interface/date_pause_button.dds": (412, 28),
    "gfx/interface/topbar/zoom_out.dds": (27, 27),
    "gfx/interface/topbar/zoom_in.dds": (27, 27),
    "gfx/interface/topbar/speed_step.dds": (84, 10),
    "gfx/interface/topbar/button_menu.dds": (24, 24),
    "gfx/interface/topbar/button_help.dds": (24, 24),
    "gfx/interface/topbar/achievements_button.dds": (24, 24),
    "gfx/interface/topbar/musicplayer/playlist_button.dds": (33, 33),
    "gfx/interface/topbar/show_dismissed_alerts_icon.dds": (24, 24),
    "gfx/interface/topbar/ADISCORD_flag_frame_overlay.dds": (88, 58),
    "gfx/interface/topbar/ADISCORD_flag_overlay.dds": (82, 52),
    "gfx/interface/topbar/ADISCORD_flag_alpha_mask.tga": (82, 52),
}

VANILLA_TOPBAR_BUTTONS = {
    "decisions": ("GFX_topbar_decisionview_button", "gfx/interface/topbar/toolbar/topbar_decisionview_button.dds", (110, 41)),
    "intelligence": ("GFX_topbar_intelligence", "gfx/interface/topbar/toolbar/intelligence_button.dds", (110, 41)),
    "technology": ("GFX_topbar_technology", "gfx/interface/topbar/toolbar/science_button.dds", (110, 41)),
    "diplomacy": ("GFX_topbar_diplomacy", "gfx/interface/topbar/toolbar/diplomacy_button.dds", (110, 41)),
    "trade": ("GFX_topbar_trade_button", "gfx/interface/topbar/toolbar/trade_button.dds", (110, 41)),
    "international_market": ("GFX_topbar_international_market", "gfx/interface/topbar/toolbar/international_market_button.dds", (110, 41)),
    "construction": ("GFX_construction_button", "gfx/interface/topbar/toolbar/construction_button.dds", (110, 41)),
    "production": ("GFX_topbar_production", "gfx/interface/topbar/toolbar/production_button.dds", (110, 41)),
    "deployment": ("GFX_deployment_button", "gfx/interface/topbar/toolbar/deployment_button.dds", (110, 41)),
    "logistics": ("GFX_ledger_button", "gfx/interface/topbar/toolbar/ledger_button.dds", (110, 41)),
    "officer_corp": ("GFX_staff_office_button", "gfx/interface/topbar/toolbar/staff_office_button.dds", (110, 41)),
    "army": ("GFX_armyoverview_button", "gfx/interface/topbar/armyoverview_button.dds", (76, 38)),
    "navy": ("GFX_navyoverview_button", "gfx/interface/topbar/navyoverview_button.dds", (76, 38)),
    "air": ("GFX_airoverview_button", "gfx/interface/topbar/airoverview_button.dds", (76, 38)),
}

TRADE_REGION_NAMES = {
    "russian": {
        "europe": "Восточный Форул",
        "asia": "Западный Форул",
        "africa": "Воркерланд",
        "north_america": "Зона отчуждения",
        "south_america": "Южные пустыни",
        "australia": "Племенная дуга",
        "middle_east": "Внешние земли",
    },
    "english": {
        "europe": "Eastern Forul",
        "asia": "Western Forul",
        "africa": "Vorkerland",
        "north_america": "Exclusion Zone",
        "south_america": "Southern Deserts",
        "australia": "Tribal Arc",
        "middle_east": "Outer Lands",
    },
}


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def direct(entries: list[Entry], key: str) -> list[Entry]:
    return [entry for entry in entries if entry.key == key]


def direct_scalar(entries: list[Entry], key: str) -> str | None:
    matches = direct(entries, key)
    if len(matches) != 1 or isinstance(matches[0].value, list):
        return None
    return matches[0].value


def named_clausewitz_block(text: str, name: str) -> list[Entry]:
    matches = [entry for entry in parse_clausewitz(text) if entry.key == name]
    if len(matches) != 1 or not isinstance(matches[0].value, list):
        raise AssertionError(f"expected one Clausewitz block {name}, found {len(matches)}")
    return matches[0].value


def named_gui_body(text: str, name: str) -> str:
    matches: list[str] = []
    for start in re.finditer(r"[A-Za-z_][A-Za-z0-9_]*Type\s*=\s*\{", text):
        opening = text.find("{", start.start())
        depth = 0
        quoted = False
        escaped = False
        for index in range(opening, len(text)):
            char = text[index]
            if quoted:
                if char == "\\" and not escaped:
                    escaped = True
                    continue
                if char == '"' and not escaped:
                    quoted = False
                escaped = False
                continue
            if char == '"':
                quoted = True
            elif char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    body = text[opening + 1 : index]
                    own_name = re.search(r'\bname\s*=\s*"([^"]+)"', body)
                    if own_name and own_name.group(1) == name:
                        matches.append(body)
                    break
        else:
            raise AssertionError(f"unclosed GUI node while looking for {name}")
    if len(matches) != 1:
        raise AssertionError(f"expected one GUI node {name}, found {len(matches)}")
    return matches[0]


def gui_parent_map(text: str) -> dict[str, tuple[str, ...]]:
    token = re.compile(
        r'(?P<type>[A-Za-z_][A-Za-z0-9_]*Type)\s*=\s*\{'
        r'|(?P<name>name\s*=\s*"(?P<name_value>[^"]+)")'
        r'|(?P<open>\{)|(?P<close>\})'
    )
    stack: list[dict[str, str | None]] = []
    parents: dict[str, tuple[str, ...]] = {}
    for match in token.finditer(text):
        if match.group("type"):
            stack.append({"type": match.group("type"), "name": None})
        elif match.group("open"):
            stack.append({"type": None, "name": None})
        elif match.group("close"):
            if stack:
                stack.pop()
        elif match.group("name") and stack and stack[-1]["type"]:
            name = match.group("name_value")
            stack[-1]["name"] = name
            parents[name] = tuple(
                str(node["name"])
                for node in stack[:-1]
                if node["type"] and node["name"]
            )
    return parents


def assignment_position(text: str, name: str) -> tuple[int, int]:
    body = named_gui_body(text, name)
    match = re.search(r"\bposition\s*=\s*\{\s*x\s*=\s*(-?\d+)\s+y\s*=\s*(-?\d+)", body)
    if not match:
        raise AssertionError(f"GUI node {name} has no direct position")
    return int(match.group(1)), int(match.group(2))


def equipment_block(path: Path, name: str) -> list[Entry]:
    equipments = named_clausewitz_block(read(path), "equipments")
    matches = [entry for entry in equipments if entry.key == name]
    if len(matches) != 1 or not isinstance(matches[0].value, list):
        raise AssertionError(f"expected one equipment {name}")
    return matches[0].value


def building_block(text: str, name: str) -> list[Entry]:
    buildings = named_clausewitz_block(text, "buildings")
    matches = [entry for entry in buildings if entry.key == name]
    if len(matches) != 1 or not isinstance(matches[0].value, list):
        raise AssertionError(f"expected one building {name}")
    return matches[0].value


class StrategicResourcesUIContracts(unittest.TestCase):
    def test_rare_resources_are_registered_after_electricity_and_localised(self) -> None:
        root = named_clausewitz_block(read(RESOURCES), "resources")
        self.assertEqual(
            [entry.key for entry in root],
            [
                "oil",
                "aluminium",
                "rubber",
                "tungsten",
                "steel",
                "chromium",
                "coal",
                "rare_components",
                "rare_alloys",
            ],
        )
        for resource, frame in (("rare_components", "8"), ("rare_alloys", "9")):
            block = direct(root, resource)[0].value
            self.assertIsInstance(block, list)
            self.assertEqual(direct_scalar(block, "icon_frame"), frame)
            self.assertEqual(direct_scalar(block, "cic"), "0.25")
            self.assertEqual(direct_scalar(block, "convoys"), "0.1")

        synchronized_tokens = read(SYNCHRONIZED_TOKENS)
        for resource in ("rare_components", "rare_alloys"):
            self.assertEqual(
                len(re.findall(rf"(?m)^\s*{resource}\s*$", synchronized_tokens)),
                1,
                resource,
            )

        for path, language in ((RU_RESOURCES, "russian"), (EN_RESOURCES, "english")):
            data = path.read_bytes()
            self.assertTrue(data.startswith(b"\xef\xbb\xbf"), language)
            text = data.decode("utf-8-sig")
            self.assertEqual(len(re.findall(r"(?m)^\s*PRODUCTION_MATERIALS_RARE_COMPONENTS:" , text)), 1)
            self.assertEqual(len(re.findall(r"(?m)^\s*PRODUCTION_MATERIALS_RARE_ALLOYS:" , text)), 1)
            for resource in ("rare_components", "rare_alloys"):
                for prefix in ("state_resource_", "temporary_state_resource_", "country_resource_"):
                    self.assertRegex(text, rf"(?m)^\s*{prefix}{resource}:")
            visible_energy = "Электроэнергия" if language == "russian" else "Electricity"
            for key in (
                "PRODUCTION_MATERIALS_COAL",
                "state_resource_coal",
                "temporary_state_resource_coal",
                "country_resource_coal",
            ):
                energy_name = re.search(rf'(?m)^\s*{key}:\s*"([^"]*)"', text)
                self.assertIsNotNone(energy_name, key)
                self.assertEqual(energy_name.group(1), visible_energy, key)
            visible_values = "\n".join(
                match.group(1)
                for match in re.finditer(r'(?m)^\s*[A-Za-z0-9_]+:\d*\s*"([^"]*)"', text)
            )
            visible_values = re.sub(r"\$[A-Z0-9_]+(?:\|[^$]+)?\$", "", visible_values)
            retired_pattern = r"(?iu)\bуголь\b" if language == "russian" else r"(?iu)\bcoal\b"
            self.assertNotRegex(visible_values, retired_pattern)

    def test_resources_have_real_sources_and_late_equipment_consumers(self) -> None:
        buildings = read(BUILDINGS)
        synthetic = building_block(buildings, "synthetic_refinery")
        metallurgy = building_block(buildings, "ADISCORD_metallurgical_complex")
        electrolysis = building_block(buildings, "ADISCORD_electrolysis_complex")
        components_plant = building_block(buildings, "ADISCORD_rare_components_plant")
        alloy_foundry = building_block(buildings, "ADISCORD_rare_alloy_foundry")
        for legacy_source in (synthetic, metallurgy, electrolysis):
            self.assertIsNone(direct_scalar(legacy_source, "local_resources_rare_components"))
            self.assertIsNone(direct_scalar(legacy_source, "local_resources_rare_alloys"))
        self.assertEqual(direct_scalar(components_plant, "local_resources_rare_components"), "4")
        self.assertEqual(direct_scalar(alloy_foundry, "local_resources_rare_alloys"), "3")
        for factory in (components_plant, alloy_foundry):
            level_cap = direct(factory, "level_cap")
            self.assertEqual(len(level_cap), 1)
            self.assertEqual(direct_scalar(level_cap[0].value, "state_max"), "1")
            self.assertEqual(
                direct_scalar(level_cap[0].value, "group_by"),
                "ADISCORD_advanced_material_plants",
            )

        state_history = "\n".join(
            path.read_text(encoding="utf-8-sig")
            for path in (ROOT / "history/states").glob("*.txt")
        )
        self.assertNotIn("ADISCORD_rare_components_plant", state_history)
        self.assertNotIn("ADISCORD_rare_alloy_foundry", state_history)

        technology_plan = read(RESOURCE_DOC)
        self.assertIn("ADISCORD_tech_rare_components_industry", technology_plan)
        self.assertIn("ADISCORD_tech_rare_alloy_metallurgy", technology_plan)
        current_technology = "\n".join(
            path.read_text(encoding="utf-8-sig")
            for path in (ROOT / "common/technologies").glob("*.txt")
        )
        self.assertNotIn("ADISCORD_tech_rare_components_industry", current_technology)
        self.assertNotIn("ADISCORD_tech_rare_alloy_metallurgy", current_technology)

        contracts = {
            ROOT / "common/units/equipment/ADISCORD_support_equipment.txt": {
                "ADISCORD_support_equipment_2170": {"rare_components": "1"},
                "ADISCORD_support_equipment_2200": {"rare_components": "2"},
            },
            ROOT / "common/units/equipment/ADISCORD_armor_equipment.txt": {
                "ADISCORD_recon_drone_carrier_2170": {"rare_components": "1"},
                "ADISCORD_combat_platform_2183": {"rare_alloys": "1"},
                "ADISCORD_heavy_combat_platform_2200": {"rare_alloys": "2"},
            },
            ROOT / "common/units/equipment/ADISCORD_artillery_equipment.txt": {
                "ADISCORD_artillery_equipment_2183": {"rare_alloys": "1"},
                "ADISCORD_anti_air_equipment_2183": {"rare_components": "1"},
            },
            ROOT / "common/units/equipment/ADISCORD_train_equipment.txt": {
                "ADISCORD_autonomous_train_equipment_2183": {"rare_components": "1"},
                "ADISCORD_hardened_train_equipment_2183": {"rare_alloys": "1"},
            },
        }
        for path, equipments in contracts.items():
            for equipment, expected in equipments.items():
                block = equipment_block(path, equipment)
                resources = direct(block, "resources")
                self.assertEqual(len(resources), 1, equipment)
                self.assertIsInstance(resources[0].value, list)
                for resource, amount in expected.items():
                    self.assertEqual(direct_scalar(resources[0].value, resource), amount, equipment)

        effects = read(ECONOMY_EFFECTS)
        recount = named_clausewitz_block(effects, "ADISCORD_economy_recount_economic_buildings")
        rendered = " ".join(str(entry) for entry in recount)
        self.assertIn("resource@rare_components", rendered)
        self.assertIn("resource@rare_alloys", rendered)

    def test_trade_window_expands_to_nine_resource_columns(self) -> None:
        self.assertTrue(TRADE_GUI.exists(), "the mod must own the expanded trade layout")
        trade = read(TRADE_GUI)
        country_view = named_gui_body(trade, "countrytradeview")
        self.assertRegex(country_view, r"size\s*=\s*\{\s*width\s*=\s*847\b")
        self.assertGreaterEqual(len(re.findall(r"max_slots\s*=\s*\{\s*x\s*=\s*9\s+y\s*=\s*1", trade)), 1)
        self.assertRegex(trade, r"name\s*=\s*\"resources_grid\"[\s\S]*?size\s*=\s*\{\s*width\s*=\s*711\b")

        diplomacy = read(DIPLOMACY_GUI)
        trade_info = named_gui_body(diplomacy, "trade_info")
        self.assertRegex(trade_info, r"max_slots\s*=\s*\{\s*x\s*=\s*9\s+y\s*=\s*1")

        country_entry = named_gui_body(trade, "country_trade_entry")
        self.assertRegex(country_entry, r"size\s*=\s*\{\s*width\s*=\s*806\s+height\s*=\s*45")
        self.assertIn('quadTextureSprite ="GFX_ADISCORD_country_trade_entry_bg_wide"', country_entry)

        sprite_types = named_clausewitz_block(read(RESOURCE_GFX), "spriteTypes")
        trade_sprites = [
            entry.value
            for entry in sprite_types
            if entry.key == "spriteType"
            and isinstance(entry.value, list)
            and direct_scalar(entry.value, "name") == "GFX_ADISCORD_country_trade_entry_bg_wide"
        ]
        self.assertEqual(len(trade_sprites), 1)
        self.assertEqual(direct_scalar(trade_sprites[0], "noOfFrames"), "3")
        self.assertEqual(
            direct_scalar(trade_sprites[0], "texturefile"),
            "gfx/interface/ADISCORD_trade_gui/country_trade_entry_bg.dds",
        )
        with Image.open(TRADE_ENTRY_TEXTURE) as image:
            self.assertEqual(image.size, (2418, 45))

    def test_economy_button_is_immediately_right_of_trade(self) -> None:
        topbar = read(TOPBAR)
        self.assertEqual(assignment_position(topbar, "trade_button"), (61, 0))
        self.assertEqual(assignment_position(topbar, "ADISCORD_economy_topbar_anchor"), (116, 0))
        self.assertEqual(assignment_position(topbar, "construction_button"), (171, 0))
        self.assertEqual(assignment_position(topbar, "production_button"), (226, 0))
        self.assertEqual(assignment_position(topbar, "deployment_button"), (281, 0))
        self.assertEqual(assignment_position(topbar, "logistics_button"), (336, 0))
        self.assertEqual(assignment_position(topbar, "officer_corp_button"), (391, 0))
        self.assertEqual(assignment_position(topbar, "army_button"), (-238, 8))
        self.assertEqual(assignment_position(topbar, "navy_button"), (-189, 8))
        self.assertEqual(assignment_position(topbar, "air_button"), (-143, 8))
        self.assertEqual(assignment_position(topbar, "cp"), (781, 5))

        economy = read(ECONOMY_GUI)
        self.assertEqual(assignment_position(economy, "ADISCORD_economy_topbar_window"), (405, 36))
        self.assertEqual(
            assignment_position(economy, "ADISCORD_economy_treasury_topbar_window"),
            (708, 5),
        )
        button = named_gui_body(economy, "ADISCORD_economy_topbar_button")
        self.assertIn('quadTextureSprite = "GFX_ADISCORD_economy_topbar_button"', button)
        self.assertRegex(button, r"size\s*=\s*\{\s*x\s*=\s*55\s+y\s*=\s*41\s*\}")

        scripted = named_clausewitz_block(read(ECONOMY_GUI_SCRIPT), "scripted_gui")
        for owner_name in (
            "ADISCORD_economy_treasury_topbar_script",
            "ADISCORD_economy_topbar_script",
        ):
            owner = direct(scripted, owner_name)
            self.assertEqual(len(owner), 1, owner_name)
            self.assertIsInstance(owner[0].value, list)
            visible = direct(owner[0].value, "visible")
            self.assertEqual(len(visible), 1, owner_name)
            self.assertEqual(direct_scalar(visible[0].value, "always"), "yes", owner_name)
        economy_owner = direct(scripted, "ADISCORD_economy_topbar_script")[0].value
        self.assertEqual(
            direct_scalar(economy_owner, "parent_window_token"),
            "top_bar",
        )
        treasury_owner = direct(scripted, "ADISCORD_economy_treasury_topbar_script")[0].value
        self.assertEqual(direct_scalar(treasury_owner, "parent_window_token"), "top_bar")
        treasury_effects = direct(treasury_owner, "effects")
        self.assertEqual(len(treasury_effects), 1)
        open_click = direct(
            treasury_effects[0].value,
            "ADISCORD_economy_treasury_topbar_open_click",
        )
        self.assertEqual(len(open_click), 1)
        self.assertEqual(
            direct_scalar(open_click[0].value, "ADISCORD_economy_open_window"),
            "yes",
        )

        dashboard = direct(scripted, "ADISCORD_economy_dashboard_script")[0].value
        trigger_blocks = direct(dashboard, "triggers")
        self.assertEqual(len(trigger_blocks), 1)
        mutation_controls = (
            "tax_decrease",
            "tax_increase",
            "army_decrease",
            "army_increase",
            "research_decrease",
            "research_increase",
            "social_decrease",
            "social_increase",
            "action_internal_bonds",
            "action_external_loan",
            "action_repay_debt",
            "action_restructure_debt",
            "action_stabilization",
            "action_war_taxes",
        )
        for control in mutation_controls:
            enabled = direct(trigger_blocks[0].value, f"ADISCORD_economy_{control}_click_enabled")
            self.assertEqual(len(enabled), 1, control)
            self.assertEqual(
                direct_scalar(enabled[0].value, "ADISCORD_economy_should_show_player_ui"),
                "yes",
                control,
            )

        open_effect = named_clausewitz_block(
            read(ECONOMY_EFFECTS),
            "ADISCORD_economy_open_window",
        )
        refresh_owner = direct(open_effect, "if")
        self.assertEqual(len(refresh_owner), 1)
        self.assertIsInstance(refresh_owner[0].value, list)
        refresh_limit = direct(refresh_owner[0].value, "limit")
        self.assertEqual(len(refresh_limit), 1)
        self.assertEqual(
            direct_scalar(
                refresh_limit[0].value,
                "ADISCORD_economy_should_show_player_ui",
            ),
            "yes",
        )
        for mutation in (
            "ADISCORD_economy_initialize_country",
            "ADISCORD_economy_full_refresh",
            "ADISCORD_economy_update_model_and_cycle",
            "ADISCORD_economy_recalculate_policy_modifiers",
            "ADISCORD_economy_light_update",
            "ADISCORD_economy_refresh_policy_previews",
            "ADISCORD_economy_calculate_development_multiplier",
        ):
            self.assertEqual(direct_scalar(refresh_owner[0].value, mutation), "yes", mutation)
            self.assertIsNone(direct_scalar(open_effect, mutation), mutation)

    def test_alert_strip_and_defcon_topbar_contract(self) -> None:
        alerts = read(ALERTS)
        self.assertEqual(assignment_position(alerts, "alerticon_startposition"), (717, 35))
        self.assertEqual(assignment_position(alerts, "alerticon_startposition_extended"), (773, 35))
        self.assertEqual(assignment_position(alerts, "alerticon_offset"), (48, 44))
        self.assertEqual(assignment_position(alerts, "alerticon_endposition"), (370, 0))

        topbar = read(TOPBAR)
        self.assertNotIn("ADISCORD_defcon_display", topbar)
        self.assertNotIn("GetADISCORDDefconLevelLoc", topbar)
        self.assertEqual(assignment_position(topbar, "player_flag"), (12, 14))
        self.assertEqual(assignment_position(topbar, "observer_flag_overlay"), (11, 15))
        self.assertEqual(assignment_position(topbar, "ADISCORD_player_flag_frame"), (9, 11))
        player_flag = named_gui_body(topbar, "player_flag")
        self.assertIn('quadTextureSprite ="GFX_ADISCORD_topbar_flag"', player_flag)
        self.assertNotRegex(player_flag, r"\bscale\s*=")
        flag_frame = named_gui_body(topbar, "ADISCORD_player_flag_frame")
        self.assertIn('spriteType = "GFX_ADISCORD_flag_frame_overlay"', flag_frame)
        self.assertIn("alwaystransparent = yes", flag_frame)
        self.assertRegex(
            read(TOPBAR_GFX),
            r'maskedShieldType\s*=\s*\{[\s\S]*?'
            r'name\s*=\s*"GFX_ADISCORD_topbar_flag"[\s\S]*?'
            r'textureFile1\s*=\s*"gfx/interface/topbar/ADISCORD_flag_overlay\.dds"[\s\S]*?'
            r'textureFile2\s*=\s*"gfx/interface/topbar/ADISCORD_flag_alpha_mask\.tga"[\s\S]*?'
            r'effectFile\s*=\s*"gfx/FX/maskedflag\.lua"',
        )
        self.assertRegex(
            read(TOPBAR_GFX),
            r'name\s*=\s*"GFX_ADISCORD_flag_frame_overlay"[\s\S]*?'
            r'texturefile\s*=\s*"gfx/interface/topbar/ADISCORD_flag_frame_overlay\.dds"',
        )
        self.assertEqual(assignment_position(topbar, "threat_button"), (-91, 20))
        self.assertEqual(assignment_position(topbar, "threat_value"), (-93, 70))
        self.assertEqual(assignment_position(topbar, "menu_button"), (-32, 7))
        self.assertEqual(assignment_position(topbar, "help_button"), (-32, 34))
        self.assertEqual(assignment_position(topbar, "dismissed_alerts_button"), (-32, 62))
        self.assertEqual(assignment_position(topbar, "achievements_button"), (-274, 52))
        self.assertEqual(WORLD_TENSION_TEXTURE.read_bytes(), WORLD_TENSION_SOURCE.read_bytes())

    def test_topbar_art_replaces_vanilla_texture_paths_and_treasury_has_an_icon(self) -> None:
        topbar = read(TOPBAR)
        for button, (sprite, relative, dimensions) in VANILLA_TOPBAR_BUTTONS.items():
            if button != "international_market":
                self.assertRegex(
                    topbar,
                    rf'quadTextureSprite\s*=\s*"{re.escape(sprite)}"',
                    f"{button} must keep the engine's original GFX reference",
                )
            texture = ROOT / relative
            self.assertTrue(texture.is_file(), f"missing replacement texture: {relative}")
            with Image.open(texture) as image:
                self.assertEqual(image.size, dimensions, button)
        with Image.open(ROOT / "gfx/interface/topbar/background_extended.dds") as image:
            self.assertEqual(image.size, (2346, 87))
            alpha = image.convert("RGBA").getchannel("A")
            self.assertIsNotNone(alpha.crop((0, 20, 1117, 21)).getbbox())
            self.assertIsNone(alpha.crop((1117, 20, image.width, 21)).getbbox())
            expected_shelf_ends = {45: 1115, 60: 1100, 70: 1089, 80: 1079}
            for y, expected_end in expected_shelf_ends.items():
                occupied = alpha.crop((0, y, image.width, y + 1)).getbbox()
                self.assertIsNotNone(occupied, y)
                self.assertEqual(occupied[2], expected_end, y)
        for relative, dimensions in RIGHT_TOPBAR_ASSETS.items():
            with Image.open(ROOT / relative) as image:
                self.assertEqual(image.size, dimensions, relative)
        for relative, dimensions in (
            ("gfx/interface/command_power_icon.dds", (24, 22)),
            ("gfx/texticons/command_power.dds", (22, 20)),
        ):
            with Image.open(ROOT / relative) as image:
                icon = image.convert("RGBA")
                self.assertEqual(icon.size, dimensions)
                coloured = [
                    pixel
                    for pixel in icon.get_flattened_data()
                    if pixel[3] >= 96 and pixel[0] > pixel[1] * 1.35
                ]
                self.assertGreater(len(coloured), 20, f"{relative} must visibly read as a red telephone")

        economy_gfx = read(ECONOMY_GFX)
        self.assertRegex(
            economy_gfx,
            r'name\s*=\s*"GFX_ADISCORD_treasury_icon"[\s\S]*?'
            r'texturefile\s*=\s*"gfx/interface/ADISCORD_economy_gui/treasury_icon\.dds"',
        )
        economy = read(ECONOMY_GUI)
        treasury = named_gui_body(economy, "ADISCORD_economy_treasury_topbar_window")
        self.assertIn('quadTextureSprite = "GFX_generic_box_smallest"', treasury)
        self.assertIn('spriteType = "GFX_ADISCORD_treasury_icon"', treasury)
        self.assertIn('text = "ADISCORD_economy_topbar_treasury_value"', treasury)
        with Image.open(ROOT / "gfx/interface/ADISCORD_economy_gui/treasury_icon.dds") as image:
            self.assertEqual(image.size, (24, 24))

    def test_trade_filter_labels_use_lore_regions(self) -> None:
        for path, language in ((RU_TRADE_REGIONS, "russian"), (EN_TRADE_REGIONS, "english")):
            data = path.read_bytes()
            self.assertTrue(data.startswith(b"\xef\xbb\xbf"), language)
            text = data.decode("utf-8-sig")
            for key, expected in TRADE_REGION_NAMES[language].items():
                matches = re.findall(rf'(?m)^\s*{key}:\d*\s*"([^"]*)"\s*$', text)
                self.assertEqual(matches, [expected], key)

            values = set(re.findall(r'(?m)^\s*[A-Za-z0-9_]+:\d*\s*"([^"]*)"\s*$', text))
            retired = (
                {"Европа", "Азия", "Африка", "Северная Америка", "Южная Америка", "Океания", "Ближний Восток"}
                if language == "russian"
                else {"Europe", "Asia", "Africa", "North America", "South America", "Oceania", "Middle East"}
            )
            self.assertTrue(values.isdisjoint(retired), f"{language} keeps vanilla trade-region names")

    def test_economy_is_docked_and_treasury_actions_are_not_an_overlay(self) -> None:
        economy = read(ECONOMY_GUI)
        self.assertEqual(assignment_position(economy, "ADISCORD_economy_dashboard_window"), (6, 78))
        parents = gui_parent_map(economy)
        actions = (
            "internal_bonds",
            "external_loan",
            "repay_debt",
            "restructure_debt",
            "stabilization",
            "war_taxes",
        )
        for action in actions:
            self.assertEqual(
                parents[f"ADISCORD_economy_action_{action}"],
                ("ADISCORD_economy_dashboard_window", "ADISCORD_economy_command_panel"),
            )
        for retired in (
            "ADISCORD_economy_operations_panel",
            "ADISCORD_economy_operations_open",
            "ADISCORD_economy_operations_close",
            "ADISCORD_economy_operations_snapshot",
        ):
            self.assertNotIn(f'name = "{retired}"', economy)
        self.assertNotIn("ADISCORD_economy_show_operations", read(ECONOMY_GUI_SCRIPT))
        self.assertNotIn("ADISCORD_economy_show_operations", read(ECONOMY_EFFECTS))

    def test_resource_sprites_have_nine_frames_and_generated_dimensions(self) -> None:
        self.assertTrue(RESOURCE_GFX.exists(), "resource sprite override is missing")
        gfx = read(RESOURCE_GFX)
        for sprite in ("GFX_resources_strip", "GFX_missing_resources_strip"):
            block = named_clausewitz_block(gfx, "spriteTypes")
            candidates = [
                entry.value
                for entry in block
                if entry.key == "spriteType"
                and isinstance(entry.value, list)
                and direct_scalar(entry.value, "name") == sprite
            ]
            self.assertEqual(len(candidates), 1, sprite)
            self.assertEqual(direct_scalar(candidates[0], "noOfFrames"), "9", sprite)

        with Image.open(ROOT / "gfx/interface/resources_strip.dds") as image:
            self.assertEqual(image.size, (234, 27))
            strip = image.convert("RGBA")
            for frame in range(9):
                alpha_box = strip.crop((frame * 26, 0, (frame + 1) * 26, 27)).getchannel("A").getbbox()
                self.assertIsNotNone(alpha_box, f"resource icon frame {frame + 1} is empty")
                self.assertAlmostEqual((alpha_box[0] + alpha_box[2] - 1) / 2, 12.5, delta=0.5)
        with Image.open(ROOT / "gfx/interface/missing_resources_strip.dds") as image:
            self.assertEqual(image.size, (234, 28))
            strip = image.convert("RGBA")
            for frame in range(9):
                alpha_box = strip.crop((frame * 26, 0, (frame + 1) * 26, 28)).getchannel("A").getbbox()
                self.assertIsNotNone(alpha_box, f"deficit icon frame {frame + 1} is empty")
                self.assertAlmostEqual((alpha_box[0] + alpha_box[2] - 1) / 2, 12.5, delta=0.5)
        with Image.open(ROOT / "gfx/interface/ADISCORD_economy_gui/economy_topbar_button.dds") as image:
            self.assertEqual(image.size, (110, 41))

        for source in (
            RESOURCE_SOURCE,
            TRADE_ENTRY_SOURCE,
            TOPBAR_SOURCE,
            INDICATOR_SOURCE,
            MARKET_SOURCE,
            COMMAND_POWER_SOURCE,
            TOPBAR_BACKGROUND_SOURCE,
            TREASURY_SOURCE,
        ):
            self.assertTrue(source.is_file(), f"missing approved source art: {source.relative_to(ROOT)}")
            with Image.open(source) as image:
                self.assertIn(image.mode, ("RGB", "RGBA"), source.name)
                self.assertIsNotNone(image.convert("RGBA").getchannel("A").getbbox(), source.name)

        for path, expected in expected_asset_outputs().items():
            self.assertTrue(path.is_file(), f"missing generated asset: {path.relative_to(ROOT)}")
            self.assertEqual(path.read_bytes(), expected, f"stale generated asset: {path.relative_to(ROOT)}")


if __name__ == "__main__":
    unittest.main()
