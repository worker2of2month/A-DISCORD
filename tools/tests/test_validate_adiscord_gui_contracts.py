import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
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
                # HOI4 does not recursively resolve $KEY$ aliases in these
                # scripted-GUI icon tooltips. Keep the hovered level fully
                # self-contained so the player never sees a raw loc key.
                self.assertNotIn('$ADISCORD_', tooltip_match.group(1))
                self.assertIn('§W', tooltip_match.group(1))

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

    def test_compact_dashboard_keeps_manual_borrowing_in_treasury_operations(self):
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
                    ('ADISCORD_economy_dashboard_window', 'ADISCORD_economy_operations_panel'),
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
            self.assertIn('?ADISCORD_economy_interest_rate|1', tooltip)
            self.assertIn('?ADISCORD_economy_debt_service|2', tooltip)
            self.assertIn('40/70/100/140%', tooltip)
            self.assertIn('инфляц', tooltip.lower())
        self.assertIn('?ADISCORD_economy_creditworthiness|0', external_loan_tt)
        self.assertIn('[GetADISCORDInternalBondsAvailabilityLoc]', internal_bonds_tt)
        self.assertIn('[GetADISCORDExternalLoanAvailabilityLoc]', external_loan_tt)
        for name in (
            'GetADISCORDInternalBondsAvailabilityLoc',
            'GetADISCORDExternalLoanAvailabilityLoc',
        ):
            self.assertIn(f'name = {name}', self.scripted_loc)
        for key in (
            'ADISCORD_economy_loan_blocked_ratio',
            'ADISCORD_economy_loan_blocked_cooldown',
            'ADISCORD_economy_loan_blocked_treasury_room',
            'ADISCORD_economy_loan_blocked_debt_room',
            'ADISCORD_economy_loan_blocked_creditworthiness',
            'ADISCORD_economy_loan_blocked_default',
            'ADISCORD_economy_loan_available_internal',
            'ADISCORD_economy_loan_available_external',
        ):
            self.assertRegex(self.localisation, rf'(?m)^\s*{key}:')

        triggers = (
            ROOT / 'common' / 'scripted_triggers' / 'ADISCORD_economy_triggers.txt'
        ).read_text(encoding='utf-8-sig')
        for trigger_name in (
            'ADISCORD_economy_can_issue_internal_bonds',
            'ADISCORD_economy_can_take_external_loan',
        ):
            match = re.search(
                rf'(?ms)^\s*{trigger_name}\s*=\s*\{{(.*?)^\}}',
                triggers,
            )
            self.assertIsNotNone(match)
            self.assertNotIn('has_tech =', match.group(1))
        self.assertNotIn('ADISCORD_economy_loan_blocked_technology', self.scripted_loc)
        self.assertNotRegex(
            self.localisation,
            r'(?m)^\s*ADISCORD_economy_loan_blocked_technology:',
        )

    def test_rare_treasury_actions_are_hidden_behind_one_explicit_second_layer(self):
        self.assertIn(
            (
                'buttonType',
                'ADISCORD_economy_operations_open',
                ('ADISCORD_economy_dashboard_window', 'ADISCORD_economy_command_panel'),
            ),
            self.nodes,
        )
        self.assertIn(
            (
                'containerWindowType',
                'ADISCORD_economy_operations_panel',
                ('ADISCORD_economy_dashboard_window',),
            ),
            self.nodes,
        )

        actions = (
            'internal_bonds',
            'external_loan',
            'repay_debt',
            'restructure_debt',
            'stabilization',
            'war_taxes',
        )
        for action in actions:
            node_name = f'ADISCORD_economy_action_{action}'
            self.assertIn(
                (
                    'buttonType',
                    node_name,
                    ('ADISCORD_economy_dashboard_window', 'ADISCORD_economy_operations_panel'),
                ),
                self.nodes,
            )
            self.assertNotIn(
                (
                    'buttonType',
                    node_name,
                    ('ADISCORD_economy_dashboard_window', 'ADISCORD_economy_command_panel'),
                ),
                self.nodes,
            )

        self.assertRegex(
            self.scripted_gui,
            r'ADISCORD_economy_operations_open_click\s*=\s*\{'
            r'[\s\S]*?ADISCORD_economy_show_operations\s+value\s*=\s*1'
            r'[\s\S]*?ADISCORD_economy_update_gui\s*=\s*yes',
        )
        self.assertRegex(
            self.scripted_gui,
            r'ADISCORD_economy_operations_close_click\s*=\s*\{'
            r'[\s\S]*?ADISCORD_economy_show_operations\s+value\s*=\s*0'
            r'[\s\S]*?ADISCORD_economy_update_gui\s*=\s*yes',
        )
        self.assertRegex(
            self.scripted_gui,
            r'ADISCORD_economy_operations_panel_visible\s*=\s*\{'
            r'[\s\S]*?ADISCORD_economy_show_operations\s+value\s*=\s*1',
        )

    def test_headline_kpis_show_cash_flow_before_secondary_risks(self):
        for node, text_key, tooltip in (
            ('ADISCORD_economy_kpi_treasury', 'ADISCORD_economy_kpi_treasury', 'ADISCORD_economy_treasury_tt'),
            ('ADISCORD_economy_kpi_income', 'ADISCORD_economy_kpi_income', 'ADISCORD_economy_income_tt'),
            ('ADISCORD_economy_kpi_expenses', 'ADISCORD_economy_kpi_expenses', 'ADISCORD_economy_expenses_tt'),
            ('ADISCORD_economy_kpi_balance', 'ADISCORD_economy_kpi_balance', 'ADISCORD_economy_budget_breakdown_tt'),
        ):
            line = next(
                line for line in self.gui.splitlines() if f'name = "{node}"' in line
            )
            self.assertIn(f'text = "{text_key}"', line)
            self.assertIn(f'pdx_tooltip = "{tooltip}"', line)

        self.assertNotIn('name = "ADISCORD_economy_kpi_debt"', self.gui)
        self.assertNotIn('name = "ADISCORD_economy_kpi_risk"', self.gui)

    def test_secondary_risks_have_visible_rows_and_dedicated_explanations(self):
        for node, text_key, tooltip in (
            ('ADISCORD_economy_risk_debt', 'ADISCORD_economy_risk_debt', 'ADISCORD_economy_debt_tt'),
            ('ADISCORD_economy_risk_inflation', 'ADISCORD_economy_risk_inflation', 'ADISCORD_economy_inflation_tt'),
            ('ADISCORD_economy_risk_overload', 'ADISCORD_economy_risk_overload', 'ADISCORD_economy_stretched_tt'),
            ('ADISCORD_economy_risk_war_fatigue', 'ADISCORD_economy_risk_war_fatigue', 'ADISCORD_economy_war_fatigue_tt'),
        ):
            line = next(
                line for line in self.gui.splitlines() if f'name = "{node}"' in line
            )
            self.assertIn(f'text = "{text_key}"', line)
            self.assertIn(f'pdx_tooltip = "{tooltip}"', line)

        summary_line = next(
            line
            for line in self.gui.splitlines()
            if 'name = "ADISCORD_economy_player_summary"' in line
        )
        self.assertIn('pdx_tooltip = "ADISCORD_economy_summary_tt"', summary_line)

        debt_tt = re.search(
            r'(?m)^\s*ADISCORD_economy_debt_tt:\d*\s+"([^"]*)"',
            self.localisation,
        ).group(1)
        for required in (
            '?ADISCORD_economy_debt|0',
            '?ADISCORD_economy_debt_capacity|0',
            '?ADISCORD_economy_debt_ratio|0',
            '?ADISCORD_economy_interest_rate|1',
            '?ADISCORD_economy_debt_service|2',
            '[GetADISCORDDebtEffectsLoc]',
            '40/70/100/140%',
        ):
            self.assertIn(required, debt_tt)

        inflation_tt = re.search(
            r'(?m)^\s*ADISCORD_economy_inflation_tt:\d*\s+"([^"]*)"',
            self.localisation,
        ).group(1)
        for required in (
            '?ADISCORD_economy_inflation|1',
            '?ADISCORD_economy_inflation_delta_temp|=+2',
            'эмиссия',
            'дефицитное давление',
            'ценовые шоки',
            '[GetADISCORDInflationEffectsLoc]',
            '10/25/50/75%',
        ):
            self.assertIn(required, inflation_tt)

        self.assertIn('name = GetADISCORDDebtEffectsLoc', self.scripted_loc)
        self.assertIn('name = GetADISCORDInflationEffectsLoc', self.scripted_loc)

        overload_tt = re.search(
            r'(?m)^\s*ADISCORD_economy_stretched_tt:\d*\s+"([^"]*)"',
            self.localisation,
        ).group(1)
        for required in (
            '?ADISCORD_economy_stretched_score|0',
            '?ADISCORD_economy_debt_pressure|0',
            '?ADISCORD_economy_demographic_fatigue_score|0',
            '?ADISCORD_economy_workforce_drain_level|0',
            '?ADISCORD_economy_fiscal_stress|0',
            '[GetADISCORDStateLoadEffectsLoc]',
            '20/40/60/80',
        ):
            self.assertIn(required, overload_tt)

        fatigue_tt = re.search(
            r'(?m)^\s*ADISCORD_economy_war_fatigue_tt:\d*\s+"([^"]*)"',
            self.localisation,
        ).group(1)
        for required in (
            '?ADISCORD_economy_war_fatigue_score|0',
            '?ADISCORD_economy_monthly_casualties_delta_k|0',
            '[GetADISCORDWarFatigueEffectsLoc]',
            '[GetADISCORDDemobilizationStatusLoc]',
            '15/30/50/75',
        ):
            self.assertIn(required, fatigue_tt)
        self.assertIn('name = GetADISCORDStateLoadEffectsLoc', self.scripted_loc)
        self.assertIn('name = GetADISCORDWarFatigueEffectsLoc', self.scripted_loc)
        self.assertIn('name = GetADISCORDDemobilizationStatusLoc', self.scripted_loc)

    def test_left_panel_text_zones_do_not_overlap(self):
        self.assertNotIn('ADISCORD_economy_automation_note', self.gui)
        for name, y, height in (
            ('ADISCORD_economy_player_summary', 14, 86),
            ('ADISCORD_economy_player_advice', 108, 94),
            ('ADISCORD_economy_risk_title', 214, 22),
            ('ADISCORD_economy_risk_debt', 242, 24),
            ('ADISCORD_economy_risk_inflation', 270, 24),
            ('ADISCORD_economy_risk_overload', 298, 24),
            ('ADISCORD_economy_risk_war_fatigue', 326, 24),
            ('ADISCORD_economy_buildings_summary', 378, 24),
        ):
            self.assertRegex(
                self.gui,
                rf'name\s*=\s*"{name}"'
                rf'[\s\S]{{0,160}}position\s*=\s*\{{\s*x\s*=\s*14\s+y\s*=\s*{y}\s*\}}'
                rf'[\s\S]{{0,160}}maxHeight\s*=\s*{height}',
            )

    def test_removed_tab_layout_localisation_does_not_return(self):
        for dead_key in (
            'ADISCORD_economy_tab_overview',
            'ADISCORD_economy_tab_budget',
            'ADISCORD_economy_tab_operations',
            'ADISCORD_economy_dashboard_accounting_block',
            'ADISCORD_economy_dashboard_budget_block',
            'ADISCORD_economy_dashboard_income_block',
            'ADISCORD_economy_dashboard_expenses_block',
            'ADISCORD_economy_debt_operations_title',
            'ADISCORD_economy_monetary_operations_title',
            'ADISCORD_economy_investment_operations_title',
            'ADISCORD_economy_dashboard_buildings_block',
            'ADISCORD_economy_last_month_accounting_tt',
            'ADISCORD_economy_tax_burden_tt',
            'ADISCORD_economy_army_spending_tt',
            'ADISCORD_economy_construction_spending_tt',
            'ADISCORD_economy_emergency_title',
            'ADISCORD_economy_emergency_hint',
        ):
            self.assertNotRegex(self.localisation, rf'(?m)^\s*{dead_key}:')

    def test_treasury_guidance_uses_cyrillic_capable_fonts(self):
        for hint_name in (
            'ADISCORD_economy_main_help',
            'ADISCORD_economy_operations_main_hint',
            'ADISCORD_economy_operations_hint',
        ):
            hint_line = next(
                line
                for line in self.gui.splitlines()
                if f'name = "{hint_name}"' in line
            )
            self.assertIn('font = "hoi_16mbs"', hint_line)
            self.assertNotIn('font = "hoi_14mbs"', hint_line)

    def test_treasury_operations_hint_is_actionable_and_read_only(self):
        self.assertRegex(
            self.localisation,
            r'(?m)^\s*ADISCORD_economy_operations_main_hint:\d*\s+"\[GetADISCORDTreasuryOperationsHintLoc\]"',
        )
        self.assertIn('name = GetADISCORDTreasuryOperationsHintLoc', self.scripted_loc)
        for key in (
            'ADISCORD_economy_operations_hint_deficit',
            'ADISCORD_economy_operations_hint_debt',
            'ADISCORD_economy_operations_hint_inflation',
            'ADISCORD_economy_operations_hint_reserve',
            'ADISCORD_economy_operations_hint_safe',
        ):
            self.assertRegex(self.localisation, rf'(?m)^\s*{key}:')
            self.assertIn(f'localization_key = {key}', self.scripted_loc)
        self.assertIn('ADISCORD_economy_safe_reserve', self.scripted_loc)
        for forbidden in ('every_country', 'every_owned_state', 'all_owned_state'):
            self.assertNotIn(forbidden, self.scripted_loc)


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
