import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GUI_NODE_RE = re.compile(
    r'(?P<type>[A-Za-z_][A-Za-z0-9_]*Type)\s*=\s*\{'
    r'|(?P<name>name\s*=\s*"(?P<name_value>[^"]+)")'
    r'|(?P<open>\{)'
    r'|(?P<close>\})'
)


def named_gui_nodes(text):
    stack = []
    pending_type = None
    nodes = []

    for match in GUI_NODE_RE.finditer(text):
        if match.group('type'):
            pending_type = match.group('type')
            stack.append({'type': pending_type, 'name': None})
            pending_type = None
        elif match.group('open'):
            stack.append({'type': None, 'name': None})
        elif match.group('close'):
            if stack:
                stack.pop()
        elif match.group('name') and stack and stack[-1]['type']:
            stack[-1]['name'] = match.group('name_value')
            parent_names = tuple(
                node['name'] for node in stack[:-1] if node['type'] and node['name']
            )
            nodes.append((stack[-1]['type'], stack[-1]['name'], parent_names))

    return nodes


class CountryPoliticsGuiContractTests(unittest.TestCase):
    def test_hoi4_119_faction_widgets_have_required_types_and_parents(self):
        text = (ROOT / 'interface' / 'countrypoliticsview.gui').read_text(
            encoding='utf-8-sig'
        )
        nodes = set(named_gui_nodes(text))

        required = {
            ('iconType', 'pol_faction_icon', ('countrypoliticsview',)),
            ('containerWindowType', 'faction', ('countrypoliticsview', 'ruling_party_info')),
            (
                'containerWindowType',
                'no_faction',
                ('countrypoliticsview', 'ruling_party_info', 'faction'),
            ),
            (
                'containerWindowType',
                'original_in_faction',
                ('countrypoliticsview', 'ruling_party_info', 'faction'),
            ),
            (
                'containerWindowType',
                'in_faction',
                ('countrypoliticsview', 'ruling_party_info', 'faction'),
            ),
            (
                'instantTextboxType',
                'manage_exiled_collaborations_governments',
                ('countrypoliticsview',),
            ),
            (
                'iconType',
                'icon_exiled_collaborations_governments',
                ('countrypoliticsview',),
            ),
            ('iconType', 'icon_occupied_territories', ('countrypoliticsview',)),
            ('iconType', 'icon_manage_subjects', ('countrypoliticsview',)),
        }

        self.assertEqual(required - nodes, set())

    def test_development_panel_is_bottom_anchored_and_law_list_reserves_room(self):
        development_text = (
            ROOT / 'interface' / 'ADISCORD_CountryView.gui'
        ).read_text(encoding='utf-8-sig')
        politics_text = (
            ROOT / 'interface' / 'countrypoliticsview.gui'
        ).read_text(encoding='utf-8-sig')

        self.assertRegex(
            development_text,
            r'(?s)name\s*=\s*"ADISCORD_development_category_society_type"'
            r'.{0,500}?position\s*=\s*\{\s*x\s*=\s*-10\s+y\s*=\s*-315\s*\}'
            r'.{0,200}?size\s*=\s*\{\s*width\s*=\s*594\s+height\s*=\s*315\s*\}'
            r'.{0,200}?Orientation\s*=\s*LOWER_LEFT',
        )
        self.assertRegex(
            politics_text,
            r'(?s)name\s*=\s*"ideas"'
            r'.{0,500}?position\s*=\s*\{\s*x\s*=\s*0\s+y\s*=\s*545\s*\}'
            r'.{0,200}?size\s*=\s*\{\s*width\s*=\s*570\s+height\s*=\s*-315\s*\}',
        )


class DiplomacyGuiContractTests(unittest.TestCase):
    def test_national_spirit_row_reserves_full_idea_icon_height(self):
        text = (ROOT / 'interface' / 'countrydiplomacyview.gui').read_text(
            encoding='utf-8-sig'
        )

        self.assertRegex(
            text,
            r'(?s)name\s*=\s*"national_spirit_info"'
            r'.{0,200}?position\s*=\s*\{\s*x\s*=\s*17\s+y\s*=\s*285\s*\}'
            r'.{0,100}?size\s*=\s*\{\s*width\s*=\s*530\s+height\s*=\s*80\s*\}',
        )
        self.assertRegex(
            text,
            r'(?s)name\s*=\s*"national_spirit_container"'
            r'.{0,200}?position\s*=\s*\{\s*x\s*=\s*-380\s+y\s*=\s*-5\s*\}'
            r'.{0,100}?size\s*=\s*\{\s*width\s*=\s*375\s+height\s*=\s*84\s*\}',
        )
        self.assertRegex(
            text,
            r'(?s)name\s*=\s*"national_spirit_ideas_grid"'
            r'.{0,200}?position\s*=\s*\{\s*x\s*=\s*3\s+y\s*=\s*2\s*\}',
        )
        for grid_name, width in (
            ('national_spirit_ideas_grid', 360),
            ('nat_spirit_ideas_grid_over_defined', 330),
        ):
            self.assertRegex(
                text,
                rf'(?s)name\s*=\s*"{grid_name}"'
                rf'.{{0,200}}?size\s*=\s*\{{\s*width\s*=\s*{width}\s+height\s*=\s*80\s*\}}',
            )

        for pane_name, x in (('relations_info', 11), ('diplomatic_actions', 272)):
            self.assertRegex(
                text,
                rf'(?s)name\s*=\s*"{pane_name}"'
                rf'.{{0,200}}?position\s*=\s*\{{\s*x\s*=\s*{x}\s+y\s*=\s*365\s*\}}',
            )


class NationalFocusGuiContractTests(unittest.TestCase):
    def test_hoi4_119_focus_item_has_overlay_icon(self):
        text = (ROOT / 'interface' / 'nationalfocusview.gui').read_text(
            encoding='utf-8-sig'
        )
        nodes = set(named_gui_nodes(text))

        self.assertIn(
            ('iconType', 'overlay', ('national_focus_item',)),
            nodes,
        )


class EconomyDashboardGuiContractTests(unittest.TestCase):
    def setUp(self):
        self.gui = (ROOT / 'interface' / 'ADISCORD_economy.gui').read_text(
            encoding='utf-8-sig'
        )
        self.gfx = (ROOT / 'interface' / 'ADISCORD_economy.gfx').read_text(
            encoding='utf-8-sig'
        )
        self.scripted_gui = (
            ROOT / 'common' / 'scripted_guis' / 'ADISCORD_economy_scripted_gui.txt'
        ).read_text(encoding='utf-8-sig')
        self.scripted_loc = (
            ROOT
            / 'common'
            / 'scripted_localisation'
            / 'ADISCORD_economy_scripted_loc.txt'
        ).read_text(encoding='utf-8-sig')
        self.localisation = (
            ROOT / 'localisation' / 'russian' / 'ADISCORD_economy_l_russian.yml'
        ).read_text(encoding='utf-8-sig')
        self.nodes = set(named_gui_nodes(self.gui))

    def test_topbar_uses_icon_and_numeric_value(self):
        self.assertIn(
            (
                'iconType',
                'ADISCORD_economy_topbar_icon',
                ('ADISCORD_economy_topbar_window',),
            ),
            self.nodes,
        )
        self.assertIn(
            (
                'instantTextboxType',
                'ADISCORD_economy_topbar_value',
                ('ADISCORD_economy_topbar_window',),
            ),
            self.nodes,
        )
        self.assertNotRegex(
            self.gui,
            r'buttonText\s*=\s*"ADISCORD_economy_topbar_treasury_text"',
        )

    def test_treasury_sprite_has_a_real_temporary_asset(self):
        self.assertIn('name = "GFX_ADISCORD_treasury_icon"', self.gfx)
        self.assertIn(
            'texturefile = "gfx/interface/ADISCORD_economy_gui/treasury_icon.dds"',
            self.gfx,
        )
        self.assertTrue(
            (
                ROOT
                / 'gfx'
                / 'interface'
                / 'ADISCORD_economy_gui'
                / 'treasury_icon.dds'
            ).is_file()
        )

    def test_four_budget_rows_use_arrows_and_five_step_markers(self):
        for policy in ('tax', 'army', 'construction', 'social'):
            self.assertRegex(
                self.gui,
                rf'name\s*=\s*"ADISCORD_economy_{policy}_decrease"'
                rf'[\s\S]{{0,200}}spriteType\s*=\s*"button_left"',
            )
            self.assertRegex(
                self.gui,
                rf'name\s*=\s*"ADISCORD_economy_{policy}_increase"'
                rf'[\s\S]{{0,200}}spriteType\s*=\s*"button_right"',
            )
            for level in range(1, 6):
                self.assertIn(f'ADISCORD_economy_{policy}_step_{level}', self.gui)
            self.assertIn(f'ADISCORD_economy_{policy}_active_marker', self.gui)
        self.assertNotRegex(self.gui, r'buttonText\s*=\s*"[+-]"')

    def test_active_markers_bind_to_all_five_mode_positions(self):
        for policy in ('tax', 'army', 'construction', 'social'):
            self.assertIn(
                f'ADISCORD_economy_{policy}_active_marker_visible',
                self.scripted_gui,
            )
            self.assertIn(
                f'ADISCORD_economy_{policy}_active_marker_x_position',
                self.scripted_gui,
            )
            for position in (0, 24, 48, 72, 96):
                self.assertRegex(
                    self.scripted_gui,
                    rf'var\s*=\s*ADISCORD_economy_{policy}_active_marker_x_position'
                    rf'\s+value\s*=\s*{position}',
                )

    def test_each_budget_step_exposes_its_own_level_tooltip(self):
        contracts = {
            'tax': (
                'ADISCORD_economy_tax_burden_mode',
                'GetADISCORDTaxBurdenEffectsLoc',
            ),
            'army': (
                'ADISCORD_economy_army_spending_mode',
                'GetADISCORDArmySpendingEffectsLoc',
            ),
            'construction': (
                'ADISCORD_economy_construction_spending_mode',
                'GetADISCORDConstructionSpendingEffectsLoc',
            ),
            'social': (
                'ADISCORD_economy_social_spending_mode',
                'GetADISCORDSocialSpendingEffectsLoc',
            ),
        }
        for policy, (mode_var, effect_loc) in contracts.items():
            for level in range(1, 6):
                step_name = f'ADISCORD_economy_{policy}_step_{level}'
                step_line = next(
                    line
                    for line in self.gui.splitlines()
                    if f'name = "{step_name}"' in line
                )
                self.assertNotIn('alwaystransparent = yes', step_line)
                self.assertIn(
                    f'pdx_tooltip = "ADISCORD_economy_{policy}_level_{level}_tt"',
                    step_line,
                )
                tooltip_match = re.search(
                    rf'(?m)^\s*ADISCORD_economy_{policy}_level_{level}_tt:\d*\s+"([^"]*)"',
                    self.localisation,
                )
                self.assertIsNotNone(tooltip_match)
                self.assertIn(f'уровень {level}/5', tooltip_match.group(1))
                self.assertIn(
                    f'$ADISCORD_economy_{policy}_effects_{level}$',
                    tooltip_match.group(1),
                )

            marker_name = f'ADISCORD_economy_{policy}_active_marker'
            marker_line = next(
                line for line in self.gui.splitlines() if f'name = "{marker_name}"' in line
            )
            self.assertNotIn('alwaystransparent = yes', marker_line)
            self.assertIn(
                f'pdx_tooltip = "ADISCORD_economy_{policy}_controls_tt"',
                marker_line,
            )

            tooltip_match = re.search(
                rf'(?m)^\s*ADISCORD_economy_{policy}_controls_tt:\d*\s+"([^"]*)"',
                self.localisation,
            )
            self.assertIsNotNone(tooltip_match)
            tooltip = tooltip_match.group(1)
            self.assertIn(f'?{mode_var}|0', tooltip)
            self.assertIn(f'[{effect_loc}]', tooltip)
            self.assertNotIn('Сравнение 1–5', tooltip)
            self.assertIn(f'name = {effect_loc}', self.scripted_loc)

    def test_increase_arrows_use_visible_absolute_positioning(self):
        for policy in ('tax', 'army', 'construction', 'social'):
            increase_line = next(
                line
                for line in self.gui.splitlines()
                if f'name = "ADISCORD_economy_{policy}_increase"' in line
            )
            self.assertIn('spriteType = "button_right"', increase_line)
            self.assertIn('position = { x = 424 ', increase_line)
            self.assertNotIn('orientation = upper_right', increase_line)

    def test_compact_dashboard_exposes_manual_borrowing_actions(self):
        contracts = {
            'internal_bonds': (
                'ADISCORD_economy_gui_try_issue_internal_bonds',
                'ADISCORD_economy_can_issue_internal_bonds',
            ),
            'external_loan': (
                'ADISCORD_economy_gui_try_take_external_loan',
                'ADISCORD_economy_can_take_external_loan',
            ),
        }
        for action, (effect, trigger) in contracts.items():
            node_name = f'ADISCORD_economy_action_{action}'
            self.assertIn(
                (
                    'buttonType',
                    node_name,
                    ('ADISCORD_economy_dashboard_window', 'ADISCORD_economy_command_panel'),
                ),
                self.nodes,
            )
            self.assertIn(f'{node_name}_click = {{ {effect} = yes }}', self.scripted_gui)
            self.assertIn(
                f'{node_name}_click_enabled = {{ {trigger} = yes }}',
                self.scripted_gui,
            )
            self.assertIn(
                f'pdx_tooltip = "ADISCORD_economy_action_{action}_tt"',
                next(line for line in self.gui.splitlines() if f'name = "{node_name}"' in line),
            )

        internal_bonds_tt = re.search(
            r'(?m)^\s*ADISCORD_economy_action_internal_bonds_tt:\d*\s+"([^"]*)"',
            self.localisation,
        ).group(1)
        external_loan_tt = re.search(
            r'(?m)^\s*ADISCORD_economy_action_external_loan_tt:\d*\s+"([^"]*)"',
            self.localisation,
        ).group(1)
        for tooltip in (internal_bonds_tt, external_loan_tt):
            self.assertIn('?ADISCORD_economy_treasury|0', tooltip)
            self.assertIn('?ADISCORD_economy_treasury_cap|0', tooltip)
            self.assertIn('?ADISCORD_economy_debt|0', tooltip)
            self.assertIn('?ADISCORD_economy_debt_capacity|0', tooltip)
            self.assertIn('?ADISCORD_economy_debt_ratio|0', tooltip)
        self.assertIn('?ADISCORD_economy_creditworthiness|0', external_loan_tt)

    def test_left_panel_text_zones_do_not_overlap(self):
        self.assertNotIn('ADISCORD_economy_automation_note', self.gui)
        for name, y, height in (
            ('ADISCORD_economy_player_summary', 14, 126),
            ('ADISCORD_economy_player_advice', 154, 112),
            ('ADISCORD_economy_buildings_summary', 342, 58),
        ):
            self.assertRegex(
                self.gui,
                rf'name\s*=\s*"{name}"'
                rf'[\s\S]{{0,160}}position\s*=\s*\{{\s*x\s*=\s*14\s+y\s*=\s*{y}\s*\}}'
                rf'[\s\S]{{0,160}}maxHeight\s*=\s*{height}',
            )

    def test_treasury_hint_uses_cyrillic_capable_font(self):
        hint_line = next(
            line
            for line in self.gui.splitlines()
            if 'name = "ADISCORD_economy_emergency_hint"' in line
        )
        self.assertIn('font = "hoi_16mbs"', hint_line)
        self.assertNotIn('font = "hoi_14mbs"', hint_line)


class RuntimePulseTests(unittest.TestCase):
    def test_economy_weekly_pulse_uses_the_light_settlement(self):
        text = (ROOT / 'common' / 'on_actions' / '00_ADISCORD_on_actions.txt').read_text(
            encoding='utf-8-sig'
        )

        self.assertRegex(
            text,
            r'(?s)\bon_weekly\s*=\s*\{.*?ADISCORD_economy_should_weekly_update\s*=\s*yes'
            r'.*?ADISCORD_economy_weekly_update\s*=\s*yes',
        )
        self.assertNotRegex(
            text,
            r'(?s)\bon_weekly\s*=\s*\{.*?ADISCORD_economy_weekly_player_refresh\s*=\s*yes',
        )


if __name__ == '__main__':
    unittest.main()
