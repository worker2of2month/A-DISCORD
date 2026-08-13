from __future__ import annotations

import re
import unittest
from pathlib import Path

from PIL import Image

from tools.builders.build_adiscord_diplomacy_ui_assets import (
    FLAG_OVERLAY,
    LEADER_OVERLAY,
    PARTIES_OVERLAY,
    expected_outputs,
)


ROOT = Path(__file__).resolve().parents[2]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8-sig")


def named_block_span(text: str, name: str) -> tuple[int, int]:
    """Return the brace span of a uniquely named GUI element."""
    parsed = re.sub(r"(?m)#.*$", lambda match: " " * len(match.group()), text)
    match = re.search(rf'name\s*=\s*"{re.escape(name)}"', parsed)
    if match is None:
        raise AssertionError(f'GUI element "{name}" was not found')

    start = parsed.rfind("{", 0, match.start())
    if start < 0:
        raise AssertionError(f'GUI element "{name}" has no opening brace')

    depth = 0
    for index in range(start, len(parsed)):
        if parsed[index] == "{":
            depth += 1
        elif parsed[index] == "}":
            depth -= 1
            if depth == 0:
                return start, index
    raise AssertionError(f'GUI element "{name}" has no closing brace')


class RecallVolunteersContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.action = read(
            "common/scripted_diplomatic_actions/ADISCORD_recall_volunteers.txt"
        )

    def test_action_uses_native_recall_effect(self) -> None:
        self.assertIn("recall_volunteers = {", self.action)
        self.assertIn("has_volunteers_amount_from = {", self.action)
        self.assertIn("ROOT = { recall_volunteers_from = PREV }", self.action)
        self.assertIn("show_acceptance_on_action_button = no", self.action)

    def test_action_excludes_both_sides_of_exclusion_zone_pair(self) -> None:
        visible = re.search(
            r"(?s)visible\s*=\s*\{(.{0,300}?)\n\s*\}", self.action
        )
        self.assertIsNotNone(visible)
        body = visible.group(1)
        self.assertGreaterEqual(body.count("original_tag = EXZ"), 2)
        self.assertIn("ROOT = { NOT = { original_tag = EXZ } }", body)

    def test_localisation_exists_in_both_languages(self) -> None:
        required = (
            "RECALL_VOLUNTEERS_TITLE",
            "RECALL_VOLUNTEERS_ACTION_DESC",
            "RECALL_VOLUNTEERS_TOOLTIP",
            "RECALL_VOLUNTEERS_TOOLTIP_G",
        )
        for relative in (
            "localisation/russian/ADISCORD_vorkerland_diplomacy_l_russian.yml",
            "localisation/english/ADISCORD_vorkerland_diplomacy_l_english.yml",
        ):
            text = read(relative)
            for key in required:
                self.assertRegex(text, rf"(?m)^ {key}: \"")


class DiplomacyLayoutContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.gui = read("interface/countrydiplomacyview.gui")
        self.dirty = read("interface/ADISCORD_dirty_zone.gui")
        self.dirty_gfx = read("interface/ADISCORD_dirty_zone.gfx")
        self.diplomacy_gfx = read("interface/ADISCORD_diplomacy.gfx")

    def test_selected_country_layout_uses_adiscord_panels(self) -> None:
        self.assertIn(
            'quadTextureSprite = "GFX_ADISCORD_constructions_window_bg"', self.gui
        )
        self.assertGreaterEqual(
            self.gui.count(
                'quadTextureSprite = "GFX_ADISCORD_constructions_panel_bg"'
            ),
            5,
        )
        self.assertIn('text = "ADISCORD_DIPLOMACY_RELATIONS_HEADER"', self.gui)
        self.assertIn('text = "ADISCORD_DIPLOMACY_ACTIONS_HEADER"', self.gui)

    def test_actions_are_wider_and_resources_expose_all_nine_slots(self) -> None:
        self.assertRegex(
            self.gui,
            r'(?s)name\s*=\s*"diplomatic_actions".{0,220}?'
            r'position\s*=\s*\{\s*x\s*=\s*260\s+y\s*=\s*466\s*\}.'
            r'{0,260}?size\s*=\s*\{\s*width\s*=\s*410\s+height\s*=\s*-50\s*\}',
        )
        self.assertRegex(
            self.gui,
            r'(?s)name\s*=\s*"diplomacy_action_entry".{0,180}?'
            r'size\s*=\s*\{\s*width\s*=\s*395\s+height\s*=\s*33\s*\}',
        )
        self.assertRegex(
            self.gui,
            r'(?s)name\s*=\s*"cost".{0,260}?maxWidth\s*=\s*94'
            r'.{0,100}?fixedsize\s*=\s*yes',
        )
        self.assertRegex(
            self.gui,
            r'(?s)name\s*=\s*"trade_grid".{0,260}?'
            r'max_slots\s*=\s*\{\s*x\s*=\s*9\s+y\s*=\s*1\s*\}',
        )

    def test_active_focus_reserves_a_dedicated_art_column(self) -> None:
        self.assertRegex(
            self.gui,
            r'(?s)name\s*=\s*"active_national_focus_info".{0,220}?'
            r'position\s*=\s*\{\s*x\s*=\s*145\s+y\s*=\s*88\s*\}.'
            r'{0,100}?size\s*=\s*\{\s*width\s*=\s*527\s+height\s*=\s*120\s*\}',
        )
        self.assertRegex(
            self.gui,
            r'(?s)name\s*=\s*"goal_icon".{0,220}?'
            r'position\s*=\s*\{\s*x\s*=\s*66\s+y\s*=\s*80\s*\}.'
            r'{0,180}?scale\s*=\s*0\.9',
        )

    def test_no_focus_state_does_not_expose_the_error_placeholder(self) -> None:
        start, end = named_block_span(self.gui, "goal_icon")
        block = self.gui[start : end + 1]
        self.assertIn(
            'spriteType = "GFX_goal_generic_political_pressure"', block
        )
        self.assertNotIn("GFX_goal_unknown", block)

    def test_engine_bound_widgets_keep_their_required_direct_parents(self) -> None:
        for parent_name, child_names in (
            ("country_info", ("diplo_country_flag", "ideology_icon")),
            (
                "diplomacy_tab_top",
                ("leader_portrait", "political_pie_chart", "ruling_party_info"),
            ),
            ("active_national_focus_info", ("goal_icon",)),
        ):
            parent_start, parent_end = named_block_span(self.gui, parent_name)
            for child_name in child_names:
                child_start, child_end = named_block_span(self.gui, child_name)
                self.assertLess(parent_start, child_start)
                self.assertLess(child_end, parent_end)

                between = self.gui[parent_start + 1 : child_start]
                between = re.sub(
                    r"(?m)#.*$", lambda match: " " * len(match.group()), between
                )
                depth = between.count("{") - between.count("}")
                self.assertEqual(
                    depth,
                    0,
                    f'{child_name} must be an immediate child of {parent_name}',
                )

    def test_upper_cards_do_not_reintroduce_vanilla_chrome(self) -> None:
        for forbidden in (
            "GFX_diplo_flag_frame",
            "GFX_diplo_opinion_bg",
            "GFX_diplo_unity_bg",
            "GFX_tab_intel_ledger",
            "GFX_diplo_leader_frame",
            "GFX_pol_piechart_overlay",
            "GFX_diplo_goal_button",
            "GFX_diplo_nat_spirits_bg",
            "GFX_win_header_short",
        ):
            self.assertNotIn(forbidden, self.gui)
        self.assertIn('scale = 0.22', self.gui)
        self.assertRegex(
            self.gui,
            r'(?s)name\s*=\s*"diplo_country_flag".{0,180}?'
            r'position\s*=\s*\{\s*x\s*=\s*35\s+y\s*=\s*15\s*\}',
        )
        self.assertRegex(
            self.gui,
            r'(?s)name\s*=\s*"ADISCORD_politics_card".{0,180}?'
            r'size\s*=\s*\{\s*width\s*=\s*527\s+height\s*=\s*76\s*\}',
        )
        self.assertRegex(
            self.gui,
            r'(?s)name\s*=\s*"ADISCORD_party_popularity_frame".{0,180}?'
            r'position\s*=\s*\{\s*x\s*=\s*149\s+y\s*=\s*10\s*\}.'
            r'{0,100}?size\s*=\s*\{\s*width\s*=\s*124\s+height\s*=\s*68\s*\}',
        )
        self.assertRegex(
            self.gui,
            r'(?s)name\s*=\s*"ADISCORD_ruling_party_frame".{0,180}?'
            r'position\s*=\s*\{\s*x\s*=\s*277\s+y\s*=\s*10\s*\}.'
            r'{0,100}?size\s*=\s*\{\s*width\s*=\s*389\s+height\s*=\s*68\s*\}',
        )
        self.assertGreaterEqual(
            self.gui.count(
                'quadTextureSprite = "GFX_ADISCORD_diplomacy_thin_frame"'
            ),
            6,
        )
        self.assertRegex(
            self.diplomacy_gfx,
            r'(?s)name\s*=\s*"GFX_ADISCORD_diplomacy_thin_frame"'
            r'.{0,180}?textureFile\s*=\s*"gfx/interface/buildings/'
            r'ADISCORD_constructions_queue_tile\.dds"'
            r'.{0,120}?borderSize\s*=\s*\{\s*x\s*=\s*16\s+y\s*=\s*16\s*\}',
        )
        self.assertIn('name = "ADISCORD_focus_art_frame"', self.gui)
        self.assertIn(
            'quadTextureSprite = "GFX_ADISCORD_diplomacy_item_bg"',
            self.gui,
        )

    def test_custom_art_overlays_are_click_through_siblings(self) -> None:
        for name, sprite, x, y in (
            ("ADISCORD_diplo_flag_overlay", "GFX_ADISCORD_diplomacy_flag_overlay", 14, 2),
            ("ADISCORD_diplo_leader_overlay", "GFX_ADISCORD_diplomacy_leader_overlay", 10, 0),
            ("ADISCORD_party_popularity_overlay", "GFX_ADISCORD_diplomacy_parties_overlay", 149, 10),
        ):
            start, end = named_block_span(self.gui, name)
            block = self.gui[start : end + 1]
            self.assertIn(f'spriteType = "{sprite}"', block)
            self.assertIn(f'name = "{sprite}"', self.diplomacy_gfx)
            self.assertRegex(
                block,
                rf'position\s*=\s*\{{\s*x\s*=\s*{x}\s+y\s*=\s*{y}\s*\}}',
            )
            self.assertIn("alwaystransparent = yes", block)

    def test_native_leader_name_sits_in_the_portrait_dossier_plate(self) -> None:
        start, end = named_block_span(self.gui, "leader_name")
        block = self.gui[start : end + 1]
        self.assertRegex(
            block,
            r'position\s*=\s*\{\s*x\s*=\s*10\s+y\s*=\s*318\s*\}',
        )
        self.assertIn('font = "hoi_16mbs"', block)
        self.assertRegex(block, r'maxWidth\s*=\s*124')
        self.assertRegex(block, r'format\s*=\s*center')
        self.assertIn("alwaystransparent = yes", block)

        # Keep the binding in country_info even though it is drawn over the
        # lower plate of the nested diplomacy_tab_top card.
        parent_start, parent_end = named_block_span(self.gui, "country_info")
        self.assertLess(parent_start, start)
        self.assertLess(end, parent_end)
        between = re.sub(
            r"(?m)#.*$",
            lambda match: " " * len(match.group()),
            self.gui[parent_start + 1 : start],
        )
        self.assertEqual(between.count("{") - between.count("}"), 0)

    def test_custom_art_overlays_are_current_and_keep_clear_viewports(self) -> None:
        outputs = expected_outputs()
        expected_sizes = {
            LEADER_OVERLAY: (128, 216),
            PARTIES_OVERLAY: (124, 68),
            FLAG_OVERLAY: (126, 80),
        }
        for path, size in expected_sizes.items():
            self.assertIn(path, outputs)
            self.assertTrue(path.is_file(), path)
            self.assertEqual(path.read_bytes(), outputs[path], path)
            with Image.open(path) as image:
                rgba = image.convert("RGBA")
            self.assertEqual(rgba.size, size)
            self.assertEqual(rgba.getpixel((size[0] // 2, size[1] // 4))[3], 0)

        with Image.open(PARTIES_OVERLAY) as image:
            self.assertEqual(image.convert("RGBA").getpixel((62, 34))[3], 0)
        with Image.open(FLAG_OVERLAY) as image:
            self.assertEqual(image.convert("RGBA").getpixel((63, 40))[3], 0)

    def test_focus_button_uses_a_fixed_width_three_state_hover_atlas(self) -> None:
        self.assertEqual(
            self.gui.count(
                'quadTextureSprite = "GFX_ADISCORD_diplomacy_item_bg"'
            ),
            3,
        )
        self.assertNotIn(
            'quadTextureSprite = "GFX_ADISCORD_decisions_item_bg"', self.gui
        )
        self.assertRegex(
            self.diplomacy_gfx,
            r'(?s)corneredTileSpriteType\s*=\s*\{.{0,160}?'
            r'name\s*=\s*"GFX_ADISCORD_diplomacy_item_bg".{0,120}?'
            r'size\s*=\s*\{\s*x\s*=\s*512\s+y\s*=\s*40\s*\}.{0,220}?'
            r'borderSize\s*=\s*\{\s*x\s*=\s*64\s+y\s*=\s*12\s*\}.{0,120}?'
            r'noOfFrames\s*=\s*3',
        )
        self.assertRegex(
            self.gui,
            r'(?s)name\s*=\s*"show_national_goal_button".{0,180}?'
            r'quadTextureSprite\s*=\s*"GFX_ADISCORD_diplomacy_focus_button"'
            r'.{0,100}?size\s*=\s*\{\s*x\s*=\s*388\s+y\s*=\s*40\s*\}',
        )
        self.assertRegex(
            self.diplomacy_gfx,
            r'(?s)spriteType\s*=\s*\{.{0,100}?'
            r'name\s*=\s*"GFX_ADISCORD_diplomacy_focus_button"'
            r'.{0,180}?textureFile\s*=\s*"gfx/interface/diplomacy/'
            r'ADISCORD_diplomacy_focus_button\.dds"'
            r'.{0,80}?noOfFrames\s*=\s*3',
        )
        self.assertNotIn('name = "ADISCORD_focus_button_frame"', self.gui)

    def test_exclusion_zone_is_a_full_width_quarantine_dossier(self) -> None:
        for name in (
            "ADISCORD_Dirty_Zone_Header",
            "ADISCORD_Dirty_Zone_Wallpaper_Container",
            "ADISCORD_Dirty_Zone_Protocol",
            "ADISCORD_Dirty_Zone_Signal_Panel",
            "ADISCORD_Dirty_Zone_Lock_Status",
        ):
            self.assertIn(f'name = "{name}"', self.dirty)
        self.assertIn('name = "ADISCORD_Dirty_Zone_Animation_Clip"', self.dirty)
        self.assertIn('name = "ADISCORD_Dirty_Zone_Terminal_Frame"', self.dirty)
        self.assertIn(
            'quadTextureSprite = "GFX_tiled_window_1b_border_adiscord"',
            self.dirty,
        )
        self.assertIn(
            'quadTextureSprite = "GFX_ADISCORD_Dirty_Zone_Animation"',
            self.dirty,
        )
        self.assertNotIn('ADISCORD_Dirty_Zone_Relations_Block', self.dirty)
        self.assertNotIn('relations_block.dds', self.dirty_gfx)
        self.assertNotIn('scrollbar_block.dds', self.dirty_gfx)
        self.assertIn('name = "GFX_ADISCORD_Dirty_Zone_Animation"', self.dirty_gfx)
        self.assertIn('noOfFrames = 17', self.dirty_gfx)
        self.assertRegex(
            self.dirty,
            r'(?s)name\s*=\s*"ADISCORD_Dirty_Zone_Diplomacy_Container"'
            r'.{0,120}?position\s*=\s*\{\s*x\s*=\s*0\s+y\s*=\s*0\s*\}'
            r'.{0,100}?size\s*=\s*\{\s*width\s*=\s*680\s+'
            r'height\s*=\s*100%%\s*\}.{0,80}?clipping\s*=\s*yes',
        )
        self.assertRegex(
            self.dirty,
            r'(?s)name\s*=\s*"ADISCORD_Dirty_Zone_Header"'
            r'.{0,100}?position\s*=\s*\{\s*x\s*=\s*12\s+y\s*=\s*0\s*\}'
            r'.{0,100}?size\s*=\s*\{\s*width\s*=\s*656\s+height\s*=\s*53\s*\}',
        )
        self.assertRegex(
            self.dirty,
            r'(?s)name\s*=\s*"ADISCORD_Dirty_Zone_Header_Title"'
            r'.{0,100}?position\s*=\s*\{\s*x\s*=\s*18\s+y\s*=\s*15\s*\}'
            r'.{0,180}?maxWidth\s*=\s*370',
        )
        self.assertRegex(
            self.dirty,
            r'(?s)name\s*=\s*"ADISCORD_Dirty_Zone_Header_Status"'
            r'.{0,100}?position\s*=\s*\{\s*x\s*=\s*438\s+y\s*=\s*16\s*\}'
            r'.{0,180}?maxWidth\s*=\s*180.{0,100}?format\s*=\s*right',
        )
        for name, y, height in (
            ("ADISCORD_Dirty_Zone_Protocol", 347, "104"),
            ("ADISCORD_Dirty_Zone_Signal_Panel", 459, "-56"),
        ):
            self.assertRegex(
                self.dirty,
                rf'(?s)name\s*=\s*"{name}"'
                rf'.{{0,100}}?position\s*=\s*\{{\s*x\s*=\s*12\s+y\s*=\s*{y}\s*\}}'
                rf'.{{0,100}}?size\s*=\s*\{{\s*width\s*=\s*656\s+height\s*=\s*{height}\s*\}}',
            )
        self.assertRegex(
            self.dirty,
            r'(?s)name\s*=\s*"ADISCORD_Dirty_Zone_Wallpaper_Container"'
            r'.{0,100}?position\s*=\s*\{\s*x\s*=\s*76\s+y\s*=\s*61\s*\}'
            r'.{0,100}?size\s*=\s*\{\s*width\s*=\s*528\s+height\s*=\s*278\s*\}',
        )
        self.assertRegex(
            self.dirty,
            r'(?s)name\s*=\s*"ADISCORD_Dirty_Zone_Terminal_Frame"'
            r'.{0,100}?position\s*=\s*\{\s*x\s*=\s*387\s+y\s*=\s*8\s*\}',
        )
        self.assertGreaterEqual(self.dirty.count("maxWidth = 355"), 3)
        self.assertIn("maxWidth = 616", self.dirty)

    def test_header_tabs_form_one_continuous_wide_band(self) -> None:
        self.assertRegex(
            self.gui,
            r'(?s)name\s*=\s*"relations_tab_button".{0,220}?'
            r'position\s*=\s*\{\s*x\s*=\s*10\s+y\s*=\s*94\s*\}.'
            r'{0,100}?size\s*=\s*\{\s*x\s*=\s*330\s+y\s*=\s*38\s*\}',
        )
        self.assertRegex(
            self.gui,
            r'(?s)name\s*=\s*"info_tab_button".{0,220}?'
            r'position\s*=\s*\{\s*x\s*=\s*340\s+y\s*=\s*94\s*\}.'
            r'{0,100}?size\s*=\s*\{\s*x\s*=\s*330\s+y\s*=\s*38\s*\}',
        )
        self.assertIn('name = "ADISCORD_relations_tab_label"', self.gui)
        self.assertIn('name = "ADISCORD_info_tab_label"', self.gui)
        self.assertNotIn('buttonText = "DIPLOMACY_RELATIONS_TAB"', self.gui)
        self.assertNotIn('buttonText = "DIPLOMACY_INFO_TAB"', self.gui)

    def test_stretched_decorations_are_container_backgrounds(self) -> None:
        for name in (
            "diplo_upper_win_bg",
            "tabs_background",
            "top_bg",
            "diplomacy_bottom",
            "production_header_bg",
        ):
            self.assertRegex(
                self.gui,
                rf'(?s)containerWindowType\s*=\s*\{{.{{0,120}}?'
                rf'name\s*=\s*"{name}".{{0,220}}?'
                r'background\s*=\s*\{',
            )

    def test_russian_localisation_keeps_bom(self) -> None:
        for relative in (
            "localisation/russian/ADISCORD_vorkerland_diplomacy_l_russian.yml",
            "localisation/russian/ADISCORD_vorkerland_collapse_l_russian.yml",
        ):
            self.assertTrue((ROOT / relative).read_bytes().startswith(b"\xef\xbb\xbf"))


if __name__ == "__main__":
    unittest.main()
