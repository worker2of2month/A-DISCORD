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
        }

        self.assertEqual(required - nodes, set())


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


if __name__ == '__main__':
    unittest.main()
