#!/usr/bin/env python3
"""Validate the nine-resource trade layout and docked economy entry point."""

from __future__ import annotations

import re
from pathlib import Path

from PIL import Image

from tools.builders.build_adiscord_resource_assets import expected_outputs, validate as validate_assets
from tools.lib.paths import repository_root


ROOT = repository_root()

VANILLA_TOPBAR_BUTTONS = {
    "GFX_topbar_decisionview_button": ("gfx/interface/topbar/toolbar/topbar_decisionview_button.dds", (110, 41)),
    "GFX_topbar_intelligence": ("gfx/interface/topbar/toolbar/intelligence_button.dds", (110, 41)),
    "GFX_topbar_technology": ("gfx/interface/topbar/toolbar/science_button.dds", (110, 41)),
    "GFX_topbar_diplomacy": ("gfx/interface/topbar/toolbar/diplomacy_button.dds", (110, 41)),
    "GFX_topbar_trade_button": ("gfx/interface/topbar/toolbar/trade_button.dds", (110, 41)),
    "GFX_construction_button": ("gfx/interface/topbar/toolbar/construction_button.dds", (110, 41)),
    "GFX_topbar_production": ("gfx/interface/topbar/toolbar/production_button.dds", (110, 41)),
    "GFX_deployment_button": ("gfx/interface/topbar/toolbar/deployment_button.dds", (110, 41)),
    "GFX_ledger_button": ("gfx/interface/topbar/toolbar/ledger_button.dds", (110, 41)),
    "GFX_staff_office_button": ("gfx/interface/topbar/toolbar/staff_office_button.dds", (110, 41)),
    "GFX_armyoverview_button": ("gfx/interface/topbar/armyoverview_button.dds", (76, 38)),
    "GFX_navyoverview_button": ("gfx/interface/topbar/navyoverview_button.dds", (76, 38)),
    "GFX_airoverview_button": ("gfx/interface/topbar/airoverview_button.dds", (76, 38)),
}

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


def _read(root: Path, relative: str) -> str:
    path = root / relative
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8-sig")


def _require(text: str, pattern: str, source: str, message: str, issues: list[str]) -> None:
    if not re.search(pattern, text, re.MULTILINE | re.DOTALL):
        issues.append(f"{source}: {message}")


def _require_image_size(root: Path, relative: str, expected: tuple[int, int], issues: list[str]) -> None:
    path = root / relative
    if not path.is_file():
        issues.append(f"{relative}: generated texture is missing")
        return
    try:
        with Image.open(path) as image:
            if image.size != expected:
                issues.append(f"{relative}: expected {expected[0]}x{expected[1]}, found {image.width}x{image.height}")
    except OSError as exc:
        issues.append(f"{relative}: cannot read generated texture: {exc}")


def validate(root: Path = ROOT) -> list[str]:
    issues: list[str] = []
    resources = _read(root, "common/resources/00_resources.txt")
    synchronized_tokens = _read(root, "common/synchronized_dynamic_tokens/ADISCORD_tokens.txt")
    for resource, frame in (("rare_components", 8), ("rare_alloys", 9)):
        _require(
            resources,
            rf"\b{resource}\s*=\s*\{{(?:(?!\n\s*\w+\s*=\s*\{{).)*?\bicon_frame\s*=\s*{frame}\b",
            "common/resources/00_resources.txt",
            f"{resource} must own icon frame {frame}",
            issues,
        )
        if len(re.findall(rf"(?m)^\s*{resource}\s*$", synchronized_tokens)) != 1:
            issues.append(
                "common/synchronized_dynamic_tokens/ADISCORD_tokens.txt: "
                f"{resource} must be registered exactly once for deterministic runtime parsing"
            )

    buildings = _read(root, "common/buildings/00_buildings.txt")
    for token in (
        "ADISCORD_rare_components_plant = {",
        "local_resources_rare_components = 4",
        "ADISCORD_rare_alloy_foundry = {",
        "local_resources_rare_alloys = 3",
        "group_by = ADISCORD_advanced_material_plants",
    ):
        if token not in buildings:
            issues.append(f"common/buildings/00_buildings.txt: missing strategic-resource source {token}")
    for legacy_name in ("synthetic_refinery", "ADISCORD_metallurgical_complex", "ADISCORD_electrolysis_complex"):
        match = re.search(
            rf"(?ms)^\s*{legacy_name}\s*=\s*\{{(.*?)(?=^\s*[A-Za-z0-9_]+\s*=\s*\{{|^\}})",
            buildings,
        )
        if match and re.search(r"local_resources_rare_(?:components|alloys)", match.group(1)):
            issues.append(f"common/buildings/00_buildings.txt: {legacy_name} must not produce advanced materials")

    state_history = "\n".join(
        path.read_text(encoding="utf-8-sig")
        for path in (root / "history/states").glob("*.txt")
    )
    for building in ("ADISCORD_rare_components_plant", "ADISCORD_rare_alloy_foundry"):
        if building in state_history:
            issues.append(f"history/states: {building} is placed before its technology integration")

    equipment_sources = (
        "common/units/equipment/ADISCORD_support_equipment.txt",
        "common/units/equipment/ADISCORD_armor_equipment.txt",
        "common/units/equipment/ADISCORD_artillery_equipment.txt",
        "common/units/equipment/ADISCORD_train_equipment.txt",
    )
    equipment = "\n".join(_read(root, source) for source in equipment_sources)
    for resource in ("rare_components", "rare_alloys"):
        if len(re.findall(rf"\b{resource}\s*=\s*[12]\b", equipment)) < 4:
            issues.append(f"common/units/equipment: {resource} lacks four bounded late-equipment consumers")

    topbar = _read(root, "interface/topbar.gui")
    for name, x in (("trade_button", 61), ("construction_button", 171), ("production_button", 226)):
        _require(
            topbar,
            rf'name\s*=\s*"{name}"(?:(?!\n\s*\w+Type\s*=).)*?position\s*=\s*\{{\s*x\s*=\s*{x}\s+y\s*=\s*0',
            "interface/topbar.gui",
            f"{name} is not at the nine-resource toolbar position x={x}",
            issues,
        )
    _require(
        topbar,
        r'name\s*=\s*"ADISCORD_economy_topbar_anchor"[\s\S]*?'
        r'position\s*=\s*\{\s*x\s*=\s*116\s+y\s*=\s*0',
        "interface/topbar.gui",
        "economy toolbar anchor must follow the DLC-dependent intelligence container",
        issues,
    )
    for sprite, (relative, dimensions) in VANILLA_TOPBAR_BUTTONS.items():
        _require(
            topbar,
            rf'quadTextureSprite\s*=\s*"{re.escape(sprite)}"',
            "interface/topbar.gui",
            f"original engine sprite reference {sprite} is not used",
            issues,
        )
        _require_image_size(root, relative, dimensions, issues)
    for relative, dimensions in RIGHT_TOPBAR_ASSETS.items():
        _require_image_size(root, relative, dimensions, issues)
    for name, x, y in (
        ("player_flag", 12, 14),
        ("observer_flag_overlay", 11, 15),
        ("ADISCORD_player_flag_frame", 9, 11),
    ):
        _require(
            topbar,
            rf'name\s*=\s*"{name}"[\s\S]*?'
            rf'position\s*=\s*\{{\s*x\s*=\s*{x}\s+y\s*=\s*{y}\s*\}}',
            "interface/topbar.gui",
            f"{name} must be inset into the custom flag bay",
            issues,
        )
    topbar_gfx = _read(root, "interface/ADISCORD_topbar.gfx")
    _require(
        topbar_gfx,
        r'maskedShieldType\s*=\s*\{[\s\S]*?'
        r'name\s*=\s*"GFX_ADISCORD_topbar_flag"[\s\S]*?'
        r'textureFile1\s*=\s*"gfx/interface/topbar/ADISCORD_flag_overlay\.dds"[\s\S]*?'
        r'textureFile2\s*=\s*"gfx/interface/topbar/ADISCORD_flag_alpha_mask\.tga"[\s\S]*?'
        r'effectFile\s*=\s*"gfx/FX/maskedflag\.lua"',
        "interface/ADISCORD_topbar.gfx",
        "the full-size topbar flag alpha mask is not registered as a masked shield",
        issues,
    )
    _require(
        topbar_gfx,
        r'name\s*=\s*"GFX_ADISCORD_flag_frame_overlay"[\s\S]*?'
        r'texturefile\s*=\s*"gfx/interface/topbar/ADISCORD_flag_frame_overlay\.dds"',
        "interface/ADISCORD_topbar.gfx",
        "the full-size topbar flag frame overlay is not registered",
        issues,
    )
    for name, x, y in (
        ("army_button", -238, 8),
        ("navy_button", -189, 8),
        ("air_button", -143, 8),
        ("threat_button", -91, 20),
        ("threat_value", -93, 70),
        ("menu_button", -32, 7),
        ("help_button", -32, 34),
        ("dismissed_alerts_button", -32, 62),
        ("achievements_button", -274, 52),
    ):
        _require(
            topbar,
            rf'name\s*=\s*"{name}"[\s\S]*?position\s*=\s*\{{\s*x\s*=\s*{x}\s+y\s*=\s*{y}\s*\}}',
            "interface/topbar.gui",
            f"{name} is not centred on the custom right-cluster socket",
            issues,
        )

    economy_gui = _read(root, "interface/ADISCORD_economy.gui")
    economy_script = _read(root, "common/scripted_guis/ADISCORD_economy_scripted_gui.txt")
    economy_effects = _read(root, "common/scripted_effects/ADISCORD_economy_effects.txt")
    for required in (
        'name = "ADISCORD_economy_topbar_button"',
        'quadTextureSprite = "GFX_ADISCORD_economy_topbar_button"',
        'name = "ADISCORD_economy_dashboard_window"',
        'name = "ADISCORD_economy_treasury_topbar_window"',
        'spriteType = "GFX_ADISCORD_treasury_icon"',
        'text = "ADISCORD_economy_topbar_treasury_value"',
        'quadTextureSprite = "GFX_generic_box_smallest"',
    ):
        if required not in economy_gui:
            issues.append(f"interface/ADISCORD_economy.gui: missing {required}")
    _require(
        economy_script,
        r'window_name\s*=\s*"ADISCORD_economy_topbar_window"[\s\S]*?'
		r'parent_window_token\s*=\s*top_bar',
        "common/scripted_guis/ADISCORD_economy_scripted_gui.txt",
		"economy topbar window must be attached to the reliable top_bar token",
        issues,
    )
    economy_gfx = _read(root, "interface/ADISCORD_economy.gfx")
    _require(
        economy_gfx,
        r'name\s*=\s*"GFX_ADISCORD_treasury_icon"[\s\S]*?'
        r'texturefile\s*=\s*"gfx/interface/ADISCORD_economy_gui/treasury_icon\.dds"',
        "interface/ADISCORD_economy.gfx",
        "treasury icon sprite is not registered",
        issues,
    )
    _require_image_size(root, "gfx/interface/ADISCORD_economy_gui/treasury_icon.dds", (24, 24), issues)
    for action in (
        "internal_bonds",
        "external_loan",
        "repay_debt",
        "restructure_debt",
        "stabilization",
        "war_taxes",
    ):
        if economy_gui.count(f'name = "ADISCORD_economy_action_{action}"') != 1:
            issues.append(f"interface/ADISCORD_economy.gui: action {action} must appear exactly once")
    retired = "\n".join((economy_gui, economy_script, economy_effects))
    for token in ("ADISCORD_economy_operations_panel", "ADISCORD_economy_show_operations"):
        if token in retired:
            issues.append(f"economy UI: retired treasury overlay token remains live: {token}")

    trade = _read(root, "interface/countrytradeview.gui")
    diplomacy = _read(root, "interface/countrydiplomacyview.gui")
    if len(re.findall(r"max_slots\s*=\s*\{\s*x\s*=\s*9\s+y\s*=\s*1", trade)) < 2:
        issues.append("interface/countrytradeview.gui: resource and filter grids must expose nine columns")
    if not re.search(r'name\s*=\s*"countrytradeview"(?:(?!\n\s*\w+Type\s*=).)*?size\s*=\s*\{\s*width\s*=\s*847\b', trade, re.DOTALL):
        issues.append("interface/countrytradeview.gui: trade window must be 847 pixels wide")
    if not re.search(r'name\s*=\s*"trade_info"[\s\S]*?max_slots\s*=\s*\{\s*x\s*=\s*9\s+y\s*=\s*1', diplomacy):
        issues.append("interface/countrydiplomacyview.gui: diplomacy resource row must expose nine columns")
    _require(
        trade,
        r'name\s*=\s*"country_trade_entry"[\s\S]*?size\s*=\s*\{\s*width\s*=\s*806\s+height\s*=\s*45'
        r'[\s\S]*?quadTextureSprite\s*=\s*"GFX_ADISCORD_country_trade_entry_bg_wide"',
        "interface/countrytradeview.gui",
        "the 806px country row must use the custom three-state background",
        issues,
    )

    gfx = _read(root, "interface/general_stuff.gfx")
    for sprite in ("GFX_resources_strip", "GFX_missing_resources_strip"):
        _require(
            gfx,
            rf'name\s*=\s*"{sprite}"(?:(?!spriteType\s*=).)*?noOfFrames\s*=\s*9\b',
            "interface/general_stuff.gfx",
            f"{sprite} must declare nine frames",
            issues,
        )
    _require(
        gfx,
        r'name\s*=\s*"GFX_ADISCORD_country_trade_entry_bg_wide"(?:(?!spriteType\s*=).)*?'
        r'texturefile\s*=\s*"gfx/interface/ADISCORD_trade_gui/country_trade_entry_bg\.dds"'
        r'(?:(?!spriteType\s*=).)*?noOfFrames\s*=\s*3\b',
        "interface/general_stuff.gfx",
        "widened trade row sprite must use three 806px frames",
        issues,
    )
    _require_image_size(root, "gfx/interface/resources_strip.dds", (234, 27), issues)
    _require_image_size(root, "gfx/interface/missing_resources_strip.dds", (234, 28), issues)
    _require_image_size(root, "gfx/interface/ADISCORD_trade_gui/country_trade_entry_bg.dds", (2418, 45), issues)

    for language in ("russian", "english"):
        relative = f"localisation/{language}/ADISCORD_resources_l_{language}.yml"
        path = root / relative
        if not path.is_file() or not path.read_bytes().startswith(b"\xef\xbb\xbf"):
            issues.append(f"{relative}: UTF-8 BOM is missing")
            continue
        localisation = path.read_text(encoding="utf-8-sig")
        visible_energy = "Электроэнергия" if language == "russian" else "Electricity"
        for key in (
            "PRODUCTION_MATERIALS_COAL",
            "state_resource_coal",
            "temporary_state_resource_coal",
            "country_resource_coal",
        ):
            if not re.search(rf'(?m)^\s*{key}:\s*"{visible_energy}"\s*$', localisation):
                issues.append(f"{relative}: {key} must be displayed as {visible_energy}")
        visible_values = "\n".join(
            match.group(1)
            for match in re.finditer(r'(?m)^\s*[A-Za-z0-9_]+:\d*\s*"([^"]*)"', localisation)
        )
        visible_values = re.sub(r"\$[A-Z0-9_]+(?:\|[^$]+)?\$", "", visible_values)
        retired_pattern = r"(?iu)\bуголь\b" if language == "russian" else r"(?iu)\bcoal\b"
        if re.search(retired_pattern, visible_values):
            retired_name = "Уголь" if language == "russian" else "Coal"
            issues.append(f"{relative}: retired player-facing resource name {retired_name} remains visible")
        for key in ("PRODUCTION_MATERIALS_RARE_COMPONENTS", "PRODUCTION_MATERIALS_RARE_ALLOYS"):
            if len(re.findall(rf"(?m)^\s*{key}:", localisation)) != 1:
                issues.append(f"{relative}: expected exactly one {key} key")

        regions_relative = f"localisation/replace/ADISCORD_trade_regions_l_{language}.yml"
        regions_path = root / regions_relative
        if not regions_path.is_file() or not regions_path.read_bytes().startswith(b"\xef\xbb\xbf"):
            issues.append(f"{regions_relative}: UTF-8 BOM is missing")
        else:
            regions = regions_path.read_text(encoding="utf-8-sig")
            for key, expected in TRADE_REGION_NAMES[language].items():
                matches = re.findall(rf'(?m)^\s*{key}:\d*\s*"([^"]*)"\s*$', regions)
                if matches != [expected]:
                    issues.append(f"{regions_relative}: {key} must be displayed as {expected}")

    if root.resolve() == ROOT.resolve():
        try:
            issues.extend(validate_assets(expected_outputs()))
        except (OSError, RuntimeError) as exc:
            issues.append(f"strategic-resource asset builder: {exc}")
    return issues


def main() -> int:
    issues = validate()
    if issues:
        for issue in issues:
            print(f"ERROR: {issue}")
        return 1
    print("Strategic resource and docked economy UI contracts pass.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
