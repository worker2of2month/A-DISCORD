#!/usr/bin/env python3
"""Build the A-Discord intelligence-agency and operative surface set."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import re

from tools.lib.adiscord_ui_surfaces import (
    PALETTES,
    apply_or_check,
    dds_bytes,
    framed_panel,
    load_surface_source,
    replace_counted,
)
from tools.lib.paths import repository_root


ROOT = repository_root()
BASE_GAME = Path(r"Z:\SteamLibrary\steamapps\common\Hearts of Iron IV")
BASE_INTERFACE = BASE_GAME / "interface"
SOURCE = ROOT / "gfx/interface/production/source/production_surface_source.png"
OUTPUT_DIR = ROOT / "gfx/interface/intelligence/ui"
GFX_OUTPUT = ROOT / "interface/ADISCORD_intelligence_ui.gfx"

WINDOW = OUTPUT_DIR / "ADISCORD_intelligence_window.dds"
PANEL = OUTPUT_DIR / "ADISCORD_intelligence_panel.dds"
CARD = OUTPUT_DIR / "ADISCORD_intelligence_card.dds"
SELECTED = OUTPUT_DIR / "ADISCORD_intelligence_selected.dds"

VANILLA_FILES = {
    "countryintelligenceagencyview.gui": "00153f0968113c3f29d914bda227c729ba5d95f5888135c0dd98db89748ef3e5",
    "countryintelligenceagencyview.gfx": "5c4eb6c934654ff9d8c188c2560d51656b084d8b0de61d18fa4fb16b00c3d7da",
    "operative.gui": "bcdfa922932131db91c26dab7323e24456ae094b65c2aa2e7b77478c8dc5aa22",
    "operativeleader.gui": "cd80a14a5e2b70d11511eadf52a89b15be5188e4e03dce2e1acbc0040ecd79e0",
    "operativeleader.gfx": "f3ff58f344a1dcae6db664bcea70d3fe44ec1e64571f7165f5a135d927218f0f",
}

FILE_REPLACEMENTS = {
    "countryintelligenceagencyview.gui": {
        "GFX_tiled_window2_1b_border": ("GFX_ADISCORD_intelligence_window", 1),
        "GFX_tiled_window_1b_thin_border": ("GFX_ADISCORD_intelligence_panel", 1),
        "GFX_tiled_bg": ("GFX_ADISCORD_intelligence_panel", 1),
        "GFX_tiled_paper_bg": ("GFX_ADISCORD_intelligence_panel", 2),
        "GFX_tiled_paper_flat_bg": ("GFX_ADISCORD_intelligence_panel", 1),
        "GFX_tiled_paper_w_frame_bg": ("GFX_ADISCORD_intelligence_panel", 1),
        "GFX_tiled_window_insigna": ("GFX_ADISCORD_intelligence_panel", 1),
        "GFX_tiled_window_transparent": ("GFX_ADISCORD_intelligence_panel", 1),
        "GFX_agency_branch_upgrades_popup_bg": ("GFX_ADISCORD_intelligence_panel", 1),
        "GFX_operatives_bg": ("GFX_ADISCORD_intelligence_panel", 1),
        "GFX_create_agency_bg": ("GFX_ADISCORD_intelligence_card", 1),
        "GFX_agency_branch_upgrade_entry_bg": ("GFX_ADISCORD_intelligence_card", 1),
        "GFX_agency_upgrade_cost_background": ("GFX_ADISCORD_intelligence_card", 1),
        "GFX_cryptology_country_entry_bg": ("GFX_ADISCORD_intelligence_card", 1),
        "GFX_operation_entry_bg": ("GFX_ADISCORD_intelligence_card", 1),
        "GFX_operatives_required_bg": ("GFX_ADISCORD_intelligence_card", 2),
        "GFX_cryptology_country_entry_selected_bg": ("GFX_ADISCORD_intelligence_selected", 1),
        "GFX_decrypt_active_bg": ("GFX_ADISCORD_intelligence_selected", 2),
    },
    "operative.gui": {
        "GFX_tiled_paper_bg2": ("GFX_ADISCORD_intelligence_panel", 1),
    },
    "operativeleader.gui": {
        "GFX_tiled_bg": ("GFX_ADISCORD_intelligence_panel", 3),
        "GFX_tiled_window": ("GFX_ADISCORD_intelligence_window", 1),
        "GFX_tiled_window_small_small": ("GFX_ADISCORD_intelligence_panel", 1),
        "GFX_tiled_window_transparent": ("GFX_ADISCORD_intelligence_panel", 1),
        "GFX_group_add_operative_bg": ("GFX_ADISCORD_intelligence_card", 1),
        "GFX_operative_missionbar_bg": ("GFX_ADISCORD_intelligence_selected", 1),
    },
}


def _verified_source(name: str) -> bytes:
    path = BASE_INTERFACE / name
    data = path.read_bytes()
    actual = hashlib.sha256(data).hexdigest()
    expected = VANILLA_FILES[name]
    if actual != expected:
        raise RuntimeError(
            f"vanilla interface mismatch for {name}: expected {expected}, found {actual}"
        )
    return data


def render_gui_files() -> dict[Path, bytes]:
    for name in VANILLA_FILES:
        _verified_source(name)
    outputs: dict[Path, bytes] = {}
    for name, replacements in FILE_REPLACEMENTS.items():
        text = _verified_source(name).decode("utf-8-sig")
        for old, (new, expected) in replacements.items():
            text = replace_counted(text, old, new, expected)
        text = "\n".join(line.rstrip() for line in text.splitlines()) + "\n"
        text = re.sub(r"(?m)^ +(?=\t)", "", text)
        outputs[ROOT / "interface" / name] = text.encode("utf-8")
    return outputs


def _cornered(name: str, filename: str, size: tuple[int, int], border: int) -> str:
    return f"""    corneredTileSpriteType = {{
        name = "{name}"
        size = {{ x = {size[0]} y = {size[1]} }}
        textureFile = "gfx/interface/intelligence/ui/{filename}"
        borderSize = {{ x = {border} y = {border} }}
        tilingCenter = yes
    }}
"""


def render_gfx() -> str:
    entries = (
        _cornered("GFX_ADISCORD_intelligence_window", WINDOW.name, (192, 192), 32)
        + _cornered("GFX_ADISCORD_intelligence_panel", PANEL.name, (192, 192), 24)
        + _cornered("GFX_ADISCORD_intelligence_card", CARD.name, (256, 72), 12)
        + _cornered("GFX_ADISCORD_intelligence_selected", SELECTED.name, (256, 72), 12)
    )
    return f"spriteTypes = {{\n{entries}}}\n"


def expected_outputs() -> dict[Path, bytes]:
    source = load_surface_source(SOURCE)
    palette = PALETTES["intelligence"]
    outputs = render_gui_files()
    outputs.update(
        {
            GFX_OUTPUT: render_gfx().encode("utf-8"),
            WINDOW: dds_bytes(framed_panel(source, (192, 192), palette, 0.76)),
            PANEL: dds_bytes(framed_panel(source, (192, 192), palette, 0.65)),
            CARD: dds_bytes(framed_panel(source, (256, 72), palette, 0.73)),
            SELECTED: dds_bytes(framed_panel(source, (256, 72), palette, 0.94)),
        }
    )
    return outputs


def main() -> int:
    parser = argparse.ArgumentParser(description="Build A-Discord intelligence UI assets.")
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument("--check", action="store_true")
    actions.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    return apply_or_check(expected_outputs(), args.apply, "Intelligence UI")


if __name__ == "__main__":
    raise SystemExit(main())
