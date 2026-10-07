"""Coverage checks must distinguish native fallbacks from authored overrides."""

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools.validators.validate_adiscord_english_localisation import ENTRY, audit


class EnglishLocalisationTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name) / 'mod'
        self.game = Path(self.directory.name) / 'game'
        self.write(self.game, 'russian', 'KEY: "Обычный регион"')
        self.write(self.game, 'english', 'KEY: "Ordinary State"')

    def write(self, root, language, entries, folder=None):
        path = root / 'localisation' / (folder or language) / f'test_l_{language}.yml'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f'l_{language}:\n {entries}\n', encoding='utf-8-sig')
        return path

    def test_unchanged_vanilla_can_fall_back(self):
        self.write(self.root, 'russian', 'KEY: "Обычный регион"')
        result = audit(self.root, self.game)
        self.assertEqual(result['missing_count'], 0)
        self.assertEqual(result['inherited_unchanged'], 1)

    def test_mod_state_name_cannot_fall_back_to_vanilla(self):
        self.write(self.root, 'russian', 'KEY: "Абилия"')
        self.assertIn('KEY', audit(self.root, self.game)['missing'])

    def test_replace_folder_wins_and_tokens_are_checked(self):
        self.write(self.root, 'russian', 'KEY: "Казна [?money|0]"')
        self.write(self.root, 'english', 'KEY: "Treasury [?money|0]"')
        self.write(self.root, 'english', 'KEY: "Treasury [?debt|0]"', folder='replace')
        self.assertTrue(
            any(
                'token mismatch' in issue
                for issue in audit(self.root, self.game)['issues']
            )
        )

    def test_empty_translation_is_not_coverage(self):
        self.write(self.root, 'russian', 'KEY: "Абилия"')
        self.write(self.root, 'english', 'KEY: ""')
        self.assertTrue(
            any(
                'empty English' in issue
                for issue in audit(self.root, self.game)['issues']
            )
        )

    def test_debug_content_also_requires_english_translation(self):
        self.write(self.root, 'russian', 'ADISCORD_debug_action: "Проверка"')
        self.assertIn(
            'ADISCORD_debug_action', audit(self.root, self.game)['missing']
        )

    def test_bom_and_physical_line_syntax_are_checked(self):
        self.write(self.root, 'russian', 'KEY: "Абилия"')
        path = self.write(self.root, 'english', 'KEY: "Abilia"')
        path.write_text('l_english:\n KEY: "unfinished\n prose"\n', encoding='utf-8')
        issues = audit(self.root, self.game)['issues']
        self.assertTrue(any('missing UTF-8 BOM' in issue for issue in issues))
        self.assertTrue(any('malformed' in issue for issue in issues))

    def test_total_conversion_validator_rejects_split_authored_values(self):
        from tools.validators import validate_tc

        path = self.write(self.root, 'russian', 'KEY: "unfinished\n prose"')
        path.rename(path.with_name('ADISCORD_test_l_russian.yml'))
        with patch.object(validate_tc, 'ROOT', self.root):
            issues, count = validate_tc.check_localisation(100)
        self.assertEqual(count, 2)
        self.assertTrue(all('malformed localisation entry' in issue for issue in issues))

    def test_campaign_briefing_and_southern_settlement_files_are_single_line(self):
        root = Path(__file__).resolve().parents[2]
        for language in ('russian', 'english'):
            for stem in ('ADISCORD_VAL_decisions', 'ADISCORD_south_final_war'):
                path = root / f'localisation/{language}/{stem}_l_{language}.yml'
                self.assertTrue(path.read_bytes().startswith(b'\xef\xbb\xbf'))
                entries = {}
                for number, line in enumerate(path.read_text(encoding='utf-8-sig').splitlines()[1:], 2):
                    if not line.strip() or line.lstrip().startswith('#'):
                        continue
                    match = ENTRY.fullmatch(line)
                    self.assertIsNotNone(match, f'{path}:{number}')
                    entries[match[1]] = match[2]
                if stem == 'ADISCORD_VAL_decisions':
                    self.assertGreater(len(entries['VAL_startup_country']), 500)
                    self.assertIn(r'\n', entries['VAL_secure_perimeter_tt'])
                else:
                    self.assertIn(r'\n\n', entries['ADISCORD_south.31.d_shl_unopposed'])

    def test_closed_texticon_can_touch_translated_prose(self):
        self.write(self.root, 'russian', 'KEY: "£trigger_no£Недостаточно инициативы"')
        self.write(self.root, 'english', 'KEY: "£trigger_no£Insufficient initiative"')
        issues = audit(self.root, self.game)['issues']
        self.assertFalse(any('token mismatch' in issue for issue in issues), issues)

    def test_texticon_frame_is_preserved(self):
        self.write(
            self.root, 'russian', 'KEY: "£operative_mission_icons_small|1£ Разведка"'
        )
        self.write(
            self.root,
            'english',
            'KEY: "£operative_mission_icons_small|2£ Intelligence"',
        )
        issues = audit(self.root, self.game)['issues']
        self.assertTrue(any('token mismatch' in issue for issue in issues), issues)

    def test_native_static_alias_difference_is_accepted_only_for_native_pair(self):
        self.write(self.game, 'russian', 'KEY: "Скорость строительства укреплений"')
        self.write(self.game, 'english', 'KEY: "$bunker$ construction speed"')
        self.write(self.root, 'russian', 'KEY: "Скорость строительства укреплений"')
        self.write(self.root, 'english', 'KEY: "$bunker$ construction speed"')
        self.assertFalse(audit(self.root, self.game)['issues'])
        self.write(self.root, 'russian', 'KEY: "Казна [?money|0]"')
        self.assertTrue(
            any(
                'token mismatch' in issue
                for issue in audit(self.root, self.game)['issues']
            )
        )


class EnglishCatalogueCompletenessTests(unittest.TestCase):
    """The distributed mod must not depend on vanilla for authored Russian text."""

    def test_ordinary_catalogues_do_not_disagree_on_duplicate_keys(self):
        from collections import defaultdict

        root = Path(__file__).resolve().parents[2] / 'localisation'
        values = defaultdict(set)
        for path in root.rglob('*_l_english.yml'):
            if 'replace' in path.relative_to(root).parts:
                continue
            for line in path.read_text(encoding='utf-8-sig').splitlines():
                match = ENTRY.fullmatch(line)
                if match:
                    values[match[1]].add(match[2])
        conflicts = sorted(key for key, variants in values.items() if len(variants) > 1)
        self.assertEqual(conflicts, [])

    def test_generated_new_state_english_names_are_current(self):
        from tools.lib.localisation import sync_builder_english_localisation

        root = Path(__file__).resolve().parents[2]
        self.assertEqual(
            sync_builder_english_localisation(
                root, 'tools.builders.build_adiscord_new_states', apply=False
            ),
            0,
        )

    def test_every_russian_key_has_an_english_entry(self):
        import os
        from tools.validators.validate_adiscord_english_localisation import (
            audit,
        )

        game_root = os.environ.get('HOI4_GAME_DIR')
        if not game_root:
            self.skipTest('Set HOI4_GAME_DIR to check inherited vanilla translations')
        root = Path(__file__).resolve().parents[2]
        missing = sorted(audit(root, Path(game_root))['missing'])
        self.assertEqual(missing, [], '\n'.join(missing))

    def test_all_english_catalogues_are_well_formed_and_translated(self):
        from tools.validators.validate_adiscord_english_localisation import (
            CYRILLIC,
            read_entries,
        )

        root = Path(__file__).resolve().parents[2] / 'localisation'
        english, issues = read_entries(root, 'english')
        self.assertEqual(issues, [])
        cyrillic = [
            key for key, entry in english.items() if CYRILLIC.search(entry['value'])
        ]
        self.assertEqual(cyrillic, [])

    def test_nonempty_russian_text_has_nonempty_english_text(self):
        from tools.validators.validate_adiscord_english_localisation import (
            EXCLUDED_KEYS,
            read_entries,
        )

        root = Path(__file__).resolve().parents[2] / 'localisation'
        russian, _ = read_entries(root, 'russian')
        english, _ = read_entries(root, 'english')
        empty = [
            key
            for key in russian.keys() & english.keys()
            if key not in EXCLUDED_KEYS
            and russian[key]['value'].strip()
            and not english[key]['value'].strip()
        ]
        self.assertEqual(sorted(empty), [])

    def test_authored_catalogues_preserve_dynamic_tokens(self):
        from collections import Counter
        from tools.validators.validate_adiscord_english_localisation import (
            TOKENS,
            read_entries,
        )

        root = Path(__file__).resolve().parents[2] / 'localisation'
        russian, _ = read_entries(root, 'russian')
        english, _ = read_entries(root, 'english')
        differences = []
        for key in sorted(russian.keys() & english.keys()):
            source = russian[key]
            if not Path(source['file']).name.startswith('ADISCORD_'):
                continue
            if Counter(TOKENS.findall(source['value'])) != Counter(
                TOKENS.findall(english[key]['value'])
            ):
                differences.append(key)
        self.assertEqual(differences, [])


if __name__ == '__main__':
    unittest.main()
