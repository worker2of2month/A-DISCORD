"""Roster availability and presentation contracts; not a native HOI4 playtest."""
from pathlib import Path
import unittest
from tools.validators.validate_adiscord_division_templates import parse_clausewitz

ROOT = Path(__file__).resolve().parents[2]


def read(path):
    file = ROOT / path
    return file.read_text(encoding='utf-8-sig') if file.exists() else ''


def children(nodes, key):
    return [n.value for n in nodes if n.key == key]


def one(nodes, key):
    values = children(nodes, key)
    if len(values) != 1:
        raise AssertionError(f'Expected one {key}, found {len(values)}')
    return values[0]


class PlayableRosterContracts(unittest.TestCase):
    def test_named_mios_exist_for_both_featured_countries(self):
        definitions = parse_clausewitz(read('common/military_industrial_organization/organizations/ADISCORD_playable_organizations.txt'))
        for tag in ('VAL', 'STP'):
            for company in ('arms_workshops', 'motor_works', 'aviation_bureau', 'advanced_arsenal'):
                with self.subTest(tag=tag, company=company):
                    key = f'{tag}_{company}_organization'
                    self.assertEqual(len(children(definitions, key)), 1, key)

    def test_stelander_roster_has_a_postwar_gate(self):
        source = read('common/scripted_triggers/ADISCORD_STP_scripted_triggers.txt')
        definitions = parse_clausewitz(source)
        gate = children(definitions, 'STP_roster_postwar_available')
        self.assertEqual(len(gate), 1, 'All new Stelander appointments need an explicit postwar gate')
        self.assertIn('STP_cw_postwar', [n.value for n in gate[0] if n.key == 'has_country_flag'])

    def test_sotnikov_and_shabrat_have_live_prewar_party_label_resolvers(self):
        definitions = parse_clausewitz(read('common/scripted_localisation/ADISCORD_STP_scripted_loc.txt'))
        names = [one(body, 'name') for body in children(definitions, 'defined_text')]
        for name in ('GetSTPPrewarHumanistLeader', 'GetSTPPrewarChauvinistLeader'):
            self.assertIn(name, names)


if __name__ == '__main__':
    unittest.main()
