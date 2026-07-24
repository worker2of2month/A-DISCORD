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


class DirtyStateTests(unittest.TestCase):
    SPAWN_STATES = set().union(*map(set, DIRTY_GROUPS.values()))
    CAPITALS = {
        49: (16639, 3, 'industrial_complex'),
        152: (9806, 3, 'industrial_complex'),
        169: (10693, 3, 'arms_factory'),
        173: (6015, 3, 'arms_factory'),
        177: (2952, 3, 'arms_factory'),
        181: (2226, 3, 'industrial_complex'),
    }

    def test_apply_effect_enumerates_every_contaminated_state_once(self):
        effects_path = validator.ROOT / 'common' / 'scripted_effects' / 'ADISCORD_vorkerland_collapse_dirty_effects.txt'
        effects = effects_path.read_text(encoding='utf-8-sig')
        apply_text = effects.split('ADISCORD_vorkerland_apply_dirty_modifiers = {', 1)[1]
        apply_text = apply_text.split('\n\nADISCORD_vorkerland_apply_dirty_state_modifier = {', 1)[0]
        state_ids = re.findall(
            r'(?m)^\s*(\d+)\s*=\s*\{\s*ADISCORD_vorkerland_apply_dirty_state_modifier\s*=\s*yes\s*\}',
            apply_text,
        )
        self.assertEqual([int(state_id) for state_id in state_ids], sorted(CONTAMINATED_STATES))
        self.assertNotRegex(apply_text, r'(?m)^\s*state\s*=')

        helper = effects.split('ADISCORD_vorkerland_apply_dirty_state_modifier = {', 1)[1]
        self.assertRegex(
            helper,
            r'has_dynamic_modifier\s*=\s*\{\s*modifier\s*=\s*ADISCORD_vorkerland_dirty_state\s*\}',
        )
        self.assertRegex(
            helper,
            r'add_dynamic_modifier\s*=\s*\{\s*modifier\s*=\s*ADISCORD_vorkerland_dirty_state\s*\}',
        )

    def test_dirty_modifier_is_permanent_and_never_removed(self):
        modifier_path = validator.ROOT / 'common' / 'dynamic_modifiers' / 'ADISCORD_vorkerland_collapse_dynamic_modifiers.txt'
        modifier = modifier_path.read_text(encoding='utf-8-sig')
        self.assertIn('ADISCORD_vorkerland_dirty_state', modifier)
        self.assertNotIn('remove_trigger', modifier)

        removals = []
        for path in validator.ROOT.rglob('*.txt'):
            text = path.read_text(encoding='utf-8-sig')
            if re.search(r'remove_dynamic_modifier\s*=\s*\{[^}]*ADISCORD_vorkerland_dirty_state', text, re.DOTALL):
                removals.append(path.relative_to(validator.ROOT).as_posix())
        self.assertEqual(removals, [])

    def test_spawn_states_are_playable_and_ownerless(self):
        for state_id in self.SPAWN_STATES:
            path = validator.state_file(validator.ROOT, state_id)
            self.assertIsNotNone(path, f'missing spawn state {state_id}')
            text = Path(path).read_text(encoding='utf-8-sig')
            self.assertRegex(text, r'\bmanpower\s*=\s*[1-9]\d*\b', f'state {state_id} needs positive manpower')
            self.assertRegex(text, r'\bstate_category\s*=\s*\w+', f'state {state_id} needs a category')
            self.assertRegex(text, r'\blocal_supplies\s*=\s*0\.[0-9]*[1-9]\d*', f'state {state_id} needs local supplies')
            self.assertNotRegex(text, r'(?m)^\s*(owner|add_core_of|add_state_core|controller)\s*=', f'state {state_id} must stay ownerless')

    def test_capital_states_have_exact_vp_and_buildings(self):
        for state_id, (province, vp, building) in self.CAPITALS.items():
            path = validator.state_file(validator.ROOT, state_id)
            text = Path(path).read_text(encoding='utf-8-sig')
            self.assertRegex(text, rf'victory_points\s*=\s*\{{\s*{province}\s+{vp}\s*\}}')
            self.assertRegex(text, r'\bstate_category\s*=\s*town\b')
            self.assertRegex(text, r'\blocal_supplies\s*=\s*0\.5\b')
            self.assertRegex(text, r'\binfrastructure\s*=\s*1\b')
            self.assertRegex(text, rf'\b{building}\s*=\s*1\b')


class EventOrchestrationTests(unittest.TestCase):
    """The collapse is a single delayed cascade; presentation never changes the map."""

    ROOT = validator.ROOT
    EVENT_PATH = ROOT / 'events' / 'ADISCORD_vorkerland_collapse_events.txt'
    EFFECTS_PATH = ROOT / 'common' / 'scripted_effects' / 'ADISCORD_vorkerland_collapse_effects.txt'
    TRIGGERS_PATH = ROOT / 'common' / 'scripted_triggers' / 'ADISCORD_vorkerland_collapse_triggers.txt'
    ON_ACTIONS_PATH = ROOT / 'common' / 'on_actions' / '01_ADISCORD_vorkerland_collapse_on_actions.txt'

    INITIAL_MAP = {
        'WRK': (27, 32, 33, 34, 35, 40, 79, 82, 105),
        'TVA': (36, 37, 38, 39), 'VAD': (75, 106, 107, 121, 123),
        'EYR': (102, 108, 109, 111, 122), 'EGC': (81, 104, 110, 124),
        'ZAO': (72,), 'WPA': (195,), 'WPS': (196,), 'PWR': (71, 90, 91),
        'PSD': (194, 93, 94), 'VLA': (74,), 'EBA': (197,), 'ROM': (73,),
        'DVA': (144, 145), 'SOL': (76,), 'SRA': (198,), 'TRU': (80,), 'ZTA': (199,),
    }
    NEW_TAGS = ('TVA', 'EYR', 'EGC', 'WPA', 'WPS', 'PSD', 'EBA', 'DVA', 'SRA', 'ZTA')
    CAPITALS = {'TVA': 36, 'EYR': 102, 'EGC': 81, 'WPA': 195, 'WPS': 196,
                'PSD': 194, 'EBA': 197, 'DVA': 145, 'SRA': 198, 'ZTA': 199}
    WARS = (('WRK', 'TVA'), ('WRK', 'VAD'), ('TVA', 'VAD'), ('VAD', 'EYR'),
            ('VAD', 'EGC'), ('EYR', 'EGC'), ('ZAO', 'WPA'), ('WPA', 'WPS'),
            ('WPS', 'ZAO'), ('PWR', 'PSD'), ('VLA', 'EBA'), ('ROM', 'DVA'),
            ('SOL', 'SRA'), ('TRU', 'ZTA'))

    @staticmethod
    def named_block(text, identifier):
        match = re.search(rf'(?m)^\s*{re.escape(identifier)}\s*=\s*\{{', text)
        if match is None:
            raise AssertionError(f'missing block {identifier}')
        depth = 0
        for index in range(match.end() - 1, len(text)):
            if text[index] == '{':
                depth += 1
            elif text[index] == '}':
                depth -= 1
                if depth == 0:
                    return text[match.start():index + 1]
        raise AssertionError(f'unbalanced block {identifier}')

    def assert_dotall(self, text, pattern):
        self.assertIsNotNone(re.search(pattern, text, re.DOTALL), f'pattern not found: {pattern}')

    def test_collapse_event_layers_exist_with_hidden_one_shot_namespace(self):
        for path in (self.EVENT_PATH, self.EFFECTS_PATH, self.TRIGGERS_PATH, self.ON_ACTIONS_PATH):
            self.assertTrue(path.exists(), f'missing Task 5 layer: {path.relative_to(self.ROOT)}')
        events = self.EVENT_PATH.read_text(encoding='utf-8-sig')
        self.assertRegex(events, r'(?m)^\s*add_namespace\s*=\s*ADISCORD_vorkerland_collapse\s*$')
        self.assertEqual(len(re.findall(r'(?m)^country_event\s*=\s*\{\s*\n\tid\s*=\s*ADISCORD_vorkerland_collapse\.1\s*$', events)), 1)
        self.assertEqual(len(re.findall(r'(?m)^country_event\s*=\s*\{\s*\n\tid\s*=\s*ADISCORD_vorkerland_collapse\.2\s*$', events)), 1)
        self.assertEqual(events.count('fire_only_once = yes'), 2)
        self.assertEqual(events.count('is_triggered_only = yes'), 2)
        self.assertEqual(events.count('hidden = yes'), 2)

    def test_startup_schedules_once_and_applies_dirty_modifiers(self):
        self.assertTrue(self.ON_ACTIONS_PATH.exists())
        startup = self.named_block(self.ON_ACTIONS_PATH.read_text(encoding='utf-8-sig'), 'on_startup')
        self.assertRegex(startup, r'NOT\s*=\s*\{\s*has_global_flag\s*=\s*ADISCORD_vorkerland_collapse_scheduled\s*\}')
        self.assertIn('set_global_flag = ADISCORD_vorkerland_collapse_scheduled', startup)
        self.assertIn('ADISCORD_vorkerland_apply_dirty_modifiers = yes', startup)
        self.assert_dotall(startup, r'WRK\s*=\s*\{.*?country_event\s*=\s*\{\s*id\s*=\s*ADISCORD_vorkerland_collapse\.1\s+days\s*=\s*120\s+random_days\s*=\s*60\s*\}')

    def test_news_zero_is_presentation_only_and_one_shot(self):
        news = (self.ROOT / 'events' / 'ADISCORD_news.txt').read_text(encoding='utf-8-sig')
        event = self.named_block(news, 'news_event')
        self.assertIn('id = news.0', event)
        self.assertIn('fire_only_once = yes', event)
        for forbidden in ('every_country', 'launch_nuke', 'damage_building', 'transfer_state'):
            self.assertNotIn(forbidden, event)

    def test_first_event_explodes_once_then_calls_teardown_and_initial_map(self):
        self.assertTrue(self.EVENT_PATH.exists())
        events = self.EVENT_PATH.read_text(encoding='utf-8-sig')
        event = self.named_block(events, 'country_event')
        self.assertIn('id = ADISCORD_vorkerland_collapse.1', event)
        trigger = self.named_block(
            self.TRIGGERS_PATH.read_text(encoding='utf-8-sig'),
            'ADISCORD_vorkerland_collapse_not_started',
        )
        self.assertRegex(trigger, r'NOT\s*=\s*\{\s*has_global_flag\s*=\s*ADISCORD_vorkerland_collapse_started\s*\}')
        self.assertIn('set_global_flag = ADISCORD_vorkerland_collapse_started', event)
        self.assertEqual(len(re.findall(r'launch_nuke\s*=\s*\{\s*province\s*=\s*16428\s+use_nuke\s*=\s*no\s*\}', event)), 1)
        self.assertEqual(event.count('damage_building = {'), 3)
        self.assert_dotall(event, r'32\s*=\s*\{\s*.*?damage_building')
        self.assertIn('ADISCORD_vorkerland_teardown_confederation = yes', event)
        self.assertIn('ADISCORD_vorkerland_apply_initial_map = yes', event)
        self.assertLess(event.index('ADISCORD_vorkerland_teardown_confederation = yes'), event.index('ADISCORD_vorkerland_apply_initial_map = yes'))
        self.assertRegex(event, r'country_event\s*=\s*\{\s*id\s*=\s*ADISCORD_vorkerland_collapse\.2\s+days\s*=\s*1\s*\}')
        self.assertRegex(event, r'news_event\s*=\s*\{\s*id\s*=\s*news\.0\s+hours\s*=\s*1\s*\}')
        self.assertNotIn('start_civil_war', event)

    def test_teardown_precedes_faction_dismantling_and_setups_precede_oobs(self):
        self.assertTrue(self.EFFECTS_PATH.exists())
        effects = self.EFFECTS_PATH.read_text(encoding='utf-8-sig')
        teardown = self.named_block(effects, 'ADISCORD_vorkerland_teardown_confederation')
        for tag in ('NAM', 'DAN', 'VAD', 'ZAO', 'PWR', 'VLA', 'ROM', 'SOL', 'TRU'):
            self.assertRegex(teardown, rf'WRK\s*=\s*\{{\s*end_puppet\s*=\s*{tag}\s*\}}')
        self.assertLess(teardown.rindex('end_puppet ='), teardown.index('dismantle_faction = yes'))
        initial_map = self.named_block(effects, 'ADISCORD_vorkerland_apply_initial_map')
        for tag, states in self.INITIAL_MAP.items():
            if tag in self.NEW_TAGS:
                continue
            for state_id in states:
                self.assert_dotall(initial_map, rf'{tag}\s*=\s*\{{.*?transfer_state\s*=\s*{state_id}')
        self.assert_dotall(initial_map, r'WRK\s*=\s*\{.*?transfer_state\s*=\s*32.*?transfer_state\s*=\s*40')
        for tag in self.NEW_TAGS:
            setup = self.named_block(effects, f'ADISCORD_vorkerland_setup_{tag.lower()}')
            for state_id in self.INITIAL_MAP[tag]:
                self.assert_dotall(setup, rf'{tag}\s*=\s*\{{.*?transfer_state\s*=\s*{state_id}')
                self.assertRegex(setup, rf'{state_id}\s*=\s*\{{\s*add_core_of\s*=\s*{tag}\s+set_state_controller_to\s*=\s*{tag}\s*\}}')
            self.assertRegex(setup, rf'set_capital\s*=\s*\{{\s*state\s*=\s*{self.CAPITALS[tag]}\s*\}}')
            self.assertIn('ADISCORD_grant_2150_technology_baseline = yes', setup)
            self.assertIn('ADISCORD_economy_initialize_country = yes', setup)
            self.assertIn(f'load_oob = "{tag}_vorkerland_collapse"', setup)
            self.assertLess(setup.index('ADISCORD_economy_initialize_country = yes'), setup.index('load_oob ='))

    def test_second_event_alone_starts_every_guarded_war(self):
        self.assertTrue(self.EVENT_PATH.exists())
        events = self.EVENT_PATH.read_text(encoding='utf-8-sig')
        definition = re.search(
            r'(?m)^country_event\s*=\s*\{\s*\n\tid\s*=\s*ADISCORD_vorkerland_collapse\.2\s*$',
            events,
        )
        self.assertIsNotNone(definition)
        second_start = definition.start()
        second = self.named_block(events[second_start:], 'country_event')
        first = events[:second_start]
        self.assertIn('set_global_flag = ADISCORD_vorkerland_collapse_wars_started', second)
        self.assertNotIn('declare_war_on', first)
        self.assertNotRegex(second, r'\bexists\s*=\s*[A-Z]{3}\b')
        self.assertEqual(second.count('declare_war_on = {'), len(self.WARS))
        for attacker, target in self.WARS:
            self.assert_dotall(second, rf'{attacker}\s*=\s*\{{.*?country_exists\s*=\s*{target}.*?NOT\s*=\s*\{{\s*has_war_with\s*=\s*{target}\s*\}}.*?declare_war_on\s*=\s*\{{\s*target\s*=\s*{target}\s+type\s*=\s*annex_everything\s*\}}')
        self.assertNotIn('start_civil_war', second)
