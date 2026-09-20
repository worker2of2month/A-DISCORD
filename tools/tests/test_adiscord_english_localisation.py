"""Coverage checks must distinguish native fallbacks from authored overrides."""

from pathlib import Path
import tempfile
import unittest

from tools.validators.validate_adiscord_english_localisation import audit


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
        self.assertTrue(any('token mismatch' in issue for issue in audit(self.root, self.game)['issues']))

    def test_empty_translation_is_not_coverage(self):
        self.write(self.root, 'russian', 'KEY: "Абилия"')
        self.write(self.root, 'english', 'KEY: ""')
        self.assertTrue(any('empty English' in issue for issue in audit(self.root, self.game)['issues']))

    def test_bom_and_physical_line_syntax_are_checked(self):
        self.write(self.root, 'russian', 'KEY: "Абилия"')
        path = self.write(self.root, 'english', 'KEY: "Abilia"')
        path.write_text('l_english:\n KEY: "unfinished\n prose"\n', encoding='utf-8')
        issues = audit(self.root, self.game)['issues']
        self.assertTrue(any('missing UTF-8 BOM' in issue for issue in issues))
        self.assertTrue(any('malformed' in issue for issue in issues))

    def test_closed_texticon_can_touch_translated_prose(self):
        self.write(self.root, 'russian', 'KEY: "£trigger_no£Недостаточно инициативы"')
        self.write(self.root, 'english', 'KEY: "£trigger_no£Insufficient initiative"')
        issues = audit(self.root, self.game)['issues']
        self.assertFalse(any('token mismatch' in issue for issue in issues), issues)

    def test_texticon_frame_is_preserved(self):
        self.write(self.root, 'russian', 'KEY: "£operative_mission_icons_small|1£ Разведка"')
        self.write(self.root, 'english', 'KEY: "£operative_mission_icons_small|2£ Intelligence"')
        issues = audit(self.root, self.game)['issues']
        self.assertTrue(any('token mismatch' in issue for issue in issues), issues)

    def test_native_static_alias_difference_is_accepted_only_for_native_pair(self):
        self.write(self.game, 'russian', 'KEY: "Скорость строительства укреплений"')
        self.write(self.game, 'english', 'KEY: "$bunker$ construction speed"')
        self.write(self.root, 'russian', 'KEY: "Скорость строительства укреплений"')
        self.write(self.root, 'english', 'KEY: "$bunker$ construction speed"')
        self.assertFalse(audit(self.root, self.game)['issues'])
        self.write(self.root, 'russian', 'KEY: "Казна [?money|0]"')
        self.assertTrue(any('token mismatch' in issue for issue in audit(self.root, self.game)['issues']))


class EnglishCatalogueCompletenessTests(unittest.TestCase):
    """The distributed mod must not depend on vanilla for authored Russian text."""

    def test_every_russian_key_has_an_english_entry(self):
        from tools.validators.validate_adiscord_english_localisation import (
            EXCLUDED_KEYS, read_entries,
        )
        root = Path(__file__).resolve().parents[2] / 'localisation'
        russian, _ = read_entries(root, 'russian')
        english, _ = read_entries(root, 'english')
        missing = sorted(set(russian) - set(english) - EXCLUDED_KEYS)
        self.assertEqual(missing, [], '\n'.join(missing))

    def test_all_english_catalogues_are_well_formed_and_translated(self):
        from tools.validators.validate_adiscord_english_localisation import (
            CYRILLIC, read_entries,
        )
        root = Path(__file__).resolve().parents[2] / 'localisation'
        english, issues = read_entries(root, 'english')
        self.assertEqual(issues, [])
        cyrillic = [key for key, entry in english.items() if CYRILLIC.search(entry['value'])]
        self.assertEqual(cyrillic, [])

    def test_nonempty_russian_text_has_nonempty_english_text(self):
        from tools.validators.validate_adiscord_english_localisation import (
            EXCLUDED_KEYS, read_entries,
        )
        root = Path(__file__).resolve().parents[2] / 'localisation'
        russian, _ = read_entries(root, 'russian')
        english, _ = read_entries(root, 'english')
        empty = [key for key in russian.keys() & english.keys()
                 if key not in EXCLUDED_KEYS and russian[key]['value'].strip()
                 and not english[key]['value'].strip()]
        self.assertEqual(sorted(empty), [])

    def test_authored_catalogues_preserve_dynamic_tokens(self):
        from collections import Counter
        from tools.validators.validate_adiscord_english_localisation import (
            TOKENS, read_entries,
        )
        root = Path(__file__).resolve().parents[2] / 'localisation'
        russian, _ = read_entries(root, 'russian')
        english, _ = read_entries(root, 'english')
        differences = []
        for key in sorted(russian.keys() & english.keys()):
            source = russian[key]
            if not Path(source['file']).name.startswith('ADISCORD_'):
                continue
            if Counter(TOKENS.findall(source['value'])) != Counter(TOKENS.findall(english[key]['value'])):
                differences.append(key)
        self.assertEqual(differences, [])

    def test_starting_unit_display_names_use_the_shared_latin_script(self):
        import re
        from tools.validators.validate_adiscord_english_localisation import CYRILLIC
        root = Path(__file__).resolve().parents[2]
        untranslated = []
        for path in sorted((root / 'history/units').rglob('*.txt')):
            for number, line in enumerate(path.read_text(encoding='utf-8-sig').splitlines(), 1):
                if line.lstrip().startswith('#'):
                    continue
                for name in re.findall(r'\bname\s*=\s*"([^"\n]*)"', line):
                    if CYRILLIC.search(name):
                        untranslated.append(f'{path.name}:{number}: {name}')
        self.assertEqual(untranslated, [])


if __name__ == '__main__':
    unittest.main()
