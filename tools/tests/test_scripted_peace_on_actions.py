"""Ownership and native callback order for the shared scripted-peace bus."""
from pathlib import Path
import re
import unittest
from tools.validators.validate_adiscord_division_templates import parse_clausewitz

ROOT = Path(__file__).resolve().parents[2]
DIRECTORY = ROOT / 'common/on_actions'
SHARED = DIRECTORY / '09_ADISCORD_scripted_peace_on_actions.txt'
GENERIC = DIRECTORY / 'ZZ_ADISCORD_default_capitulation_on_actions.txt'
ORDER = {
    'on_capitulation_immediate': ['stelander', 'kefreyt', 'northern_reservation'],
    'on_capitulation': ['vorkerland_collapse', 'stelander', 'kefreyt', 'rin', 'nam', 'vorkerland_diplomacy', 'northern_reservation', 'livonn'],
    'on_peace': ['vorkerland_collapse', 'rin', 'vorkerland_diplomacy'],
    'on_peaceconference_ended': ['stelander'],
    'on_weekly_VAL': ['livonn'],
}

def native_hooks(source):
    roots = [e.value for e in parse_clausewitz(source) if e.key == 'on_actions']
    if len(roots) != 1:
        raise AssertionError('Expected exactly one on_actions root')
    return roots[0]

class ScriptedPeaceOwnershipTests(unittest.TestCase):
    def source(self):
        self.assertTrue(SHARED.is_file(), 'Scripted peace has no shared owner')
        return SHARED.read_text(encoding='utf-8')

    def test_one_definition_for_each_shared_native_hook(self):
        names = [e.key for e in native_hooks(self.source())]
        self.assertEqual(len(names), len(set(names)))
        self.assertEqual(set(names), set(ORDER))

    def test_country_sections_preserve_dispatch_order(self):
        source = self.source()
        for hook, expected in ORDER.items():
            with self.subTest(hook=hook):
                actual = re.findall(r'(?m)^\s*# BEGIN ([a-z_]+):' + re.escape(hook) + r'\s*$', source)
                ends = re.findall(r'(?m)^\s*# END ([a-z_]+):' + re.escape(hook) + r'\s*$', source)
                self.assertEqual(actual, expected)
                self.assertEqual(ends, expected)

    def test_capitulation_has_no_remaining_country_owner(self):
        self.source()
        for path in DIRECTORY.glob('*.txt'):
            if path in (SHARED, GENERIC):
                continue
            names = {e.key for e in native_hooks(path.read_text(encoding='utf-8-sig'))}
            self.assertFalse(names & {'on_capitulation', 'on_capitulation_immediate', 'on_peaceconference_ended'}, path.name)

    def test_generic_fallback_is_separate_and_last(self):
        self.source()
        self.assertTrue(GENERIC.is_file())
        self.assertLess(SHARED.name, GENERIC.name)
        generic = GENERIC.read_text(encoding='utf-8')
        self.assertIn('NOT = { has_global_flag = skip_default_capitulation }', generic)
        self.assertIn('clr_global_flag = skip_default_capitulation', generic)

    def test_obsolete_guard_and_livonn_files_are_removed(self):
        self.source()
        for name in ('04_ADISCORD_STP_northern_capitulation_guard_on_actions.txt', '09_ADISCORD_VAL_livonn_settlement_on_actions.txt'):
            self.assertFalse((DIRECTORY / name).exists(), name)

    def test_no_war_state_mirrors_or_global_periodic_scan(self):
        source = self.source()
        for flag in ('STP_pc_war_val', 'STP_pc_war_nod', 'STP_pc_war_with_sts'):
            self.assertNotIn(flag, source)
        names = {e.key for e in native_hooks(source)}
        self.assertNotIn('on_weekly', names)
        self.assertNotIn('on_daily', names)
        self.assertFalse(SHARED.read_bytes().startswith(b'\xef\xbb\xbf'))

if __name__ == '__main__':
    unittest.main()
