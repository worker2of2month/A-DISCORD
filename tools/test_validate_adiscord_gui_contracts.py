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


class RuntimePulseTests(unittest.TestCase):
    def test_economy_has_no_weekly_full_player_refresh(self):
        text = (ROOT / 'common' / 'on_actions' / '00_ADISCORD_on_actions.txt').read_text(
            encoding='utf-8-sig'
        )

        self.assertNotRegex(
            text,
            r'(?s)\bon_weekly\s*=\s*\{.*?ADISCORD_economy_weekly_player_refresh\s*=\s*yes',
        )


if __name__ == '__main__':
    unittest.main()
