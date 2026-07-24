import unittest
import re
from pathlib import Path
from unittest.mock import patch

from tools import validate_adiscord_vorkerland_collapse as validator
from tools.vorkerland_collapse_manifest import (
    CAPITALS,
    CONTAMINATED_STATES,
    DIRTY_GROUPS,
    STATE_PARTITIONS,
    TAGS,
)


class ManifestTests(unittest.TestCase):
    def test_manifest_is_unique_and_complete(self):
        self.assertEqual(len(TAGS), len(set(TAGS)))
        self.assertEqual(len(TAGS), 16)
        self.assertEqual(len(CONTAMINATED_STATES), 37)
        self.assertEqual(
            set().union(*map(set, DIRTY_GROUPS.values())),
            CONTAMINATED_STATES - {23, 24, 57, 59, 60},
        )
        self.assertEqual(set(STATE_PARTITIONS), {71, 72, 74, 76, 80})
        self.assertEqual(set(CAPITALS), set(TAGS))

    def test_manifest_rejects_state_in_two_dirty_groups(self):
        duplicate_groups = dict(DIRTY_GROUPS)
        duplicate_groups['RZA'] = (49, *duplicate_groups['RZA'])
        issues = []

        with patch.object(validator, 'DIRTY_GROUPS', duplicate_groups):
            validator.validate_manifest(issues)

        self.assertIn(
            'dirty groups must cover every transferable contaminated state exactly once',
            issues,
        )

    def test_province_parser_ignores_hash_comments(self):
        text = '''provinces = {
            1 # province 999 was removed
            2
        }'''

        self.assertEqual(validator.provinces(text), {1, 2})


class StatePartitionTests(unittest.TestCase):
    def test_partitions_conserve_all_provinces_and_hold_new_capitals(self):
        expected_new_states = {194, 195, 196, 197, 198, 199}
        expected_capitals = {
            194: 2339,
            195: 8032,
            196: 7129,
            197: 10016,
            198: 9104,
            199: 12930,
        }

        self.assertEqual(
            {state_id for partition in STATE_PARTITIONS.values() for state_id in partition}
            - set(STATE_PARTITIONS),
            expected_new_states,
        )

        for source_state, partition in STATE_PARTITIONS.items():
            expected_provinces = [province for provinces in partition.values() for province in provinces]
            self.assertEqual(len(expected_provinces), len(set(expected_provinces)))

            actual_provinces = set()
            for state_id, expected in partition.items():
                state_path = validator.state_file(validator.ROOT, state_id)
                self.assertIsNotNone(state_path, f'missing state {state_id} from partition {source_state}')
                actual = validator.provinces(Path(state_path).read_text(encoding='utf-8-sig'))
                self.assertEqual(actual, set(expected))
                actual_provinces.update(actual)

            self.assertEqual(actual_provinces, set(expected_provinces))

        for state_id, capital in expected_capitals.items():
            state_path = validator.state_file(validator.ROOT, state_id)
            self.assertIn(capital, validator.provinces(Path(state_path).read_text(encoding='utf-8-sig')))


class CountryRosterTests(unittest.TestCase):
    """The fixed country roster remains dormant until collapse events activate it."""

    def test_fixed_roster_has_dormant_countries_leaders_flags_and_oobs(self):
        root = validator.ROOT
        tag_text = (root / 'common' / 'country_tags' / '01_ADISCORD_vorkerland_collapse_tags.txt').read_text(
            encoding='utf-8-sig'
        )
        characters = (root / 'common' / 'characters' / 'ADISCORD_vorkerland_collapse_characters.txt').read_text(
            encoding='utf-8-sig'
        )
        localisation = (root / 'localisation' / 'russian' / 'ADISCORD_vorkerland_collapse_l_russian.yml').read_text(
            encoding='utf-8-sig'
        )

        for tag, (state_id, capital) in CAPITALS.items():
            self.assertRegex(tag_text, rf'(?m)^\s*{tag}\s*=\s*"countries/{tag}\.txt"\s*$')

            country = (root / 'common' / 'countries' / f'{tag}.txt').read_text(encoding='utf-8-sig')
            self.assertIn('graphical_culture = western_european_gfx', country)
            self.assertIn('graphical_culture_2d = western_european_2d', country)

            histories = list((root / 'history' / 'countries').glob(f'{tag} - *.txt'))
            self.assertEqual(len(histories), 1, f'{tag} must have one dormant history')
            history = histories[0].read_text(encoding='utf-8-sig')
            self.assertRegex(history, rf'(?m)^\s*capital\s*=\s*{state_id}\s*$')
            self.assertNotRegex(history, r'(?m)^\s*(oob|add_state_core|transfer_state|create_faction|add_to_faction|set_autonomy)\s*=')

            self.assertRegex(characters, rf'(?m)^\s*{tag}_[A-Za-z0-9_]+\s*=\s*\{{')
            ruling_party = 'technocracy' if tag == 'TVA' else 'pragmatism'
            for key in (tag, f'{tag}_DEF', f'{tag}_ADJ', f'{tag}_{ruling_party}', f'{tag}_{ruling_party}_party'):
                self.assertRegex(localisation, rf'(?m)^\s*{re.escape(key)}:\s*".+"')

            self.assertRegex(history, rf'\bruling_party\s*=\s*{ruling_party}\b')
            if tag == 'TVA':
                self.assertRegex(
                    characters,
                    r'TVA_Dorian_Worx\s*=\s*\{.*?country_leader\s*=\s*\{\s*ideology\s*=\s*technocracy_ideology',
                )

            for size in ('', 'medium', 'small'):
                flag = root / 'gfx' / 'flags' / size / f'{tag}.tga' if size else root / 'gfx' / 'flags' / f'{tag}.tga'
                self.assertTrue(flag.exists(), f'missing {size or "large"} flag for {tag}')

            oob = (root / 'history' / 'units' / f'{tag}_vorkerland_collapse.txt').read_text(encoding='utf-8-sig')
            locations = re.findall(r'\blocation\s*=\s*(\d+)', oob)
            self.assertEqual(len(locations), 2 if tag in TAGS[:10] else 1, f'unexpected division count for {tag}')
            self.assertEqual({int(location) for location in locations}, {capital})
            self.assertIn('ADISCORD_militia = { x = 0 y = 0 }', oob)
            self.assertIn('ADISCORD_militia = { x = 0 y = 1 }', oob)
