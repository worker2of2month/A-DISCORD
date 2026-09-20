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

    def test_native_static_alias_difference_is_accepted_only_for_native_pair(self):
        self.write(self.game, 'russian', 'KEY: "Скорость строительства укреплений"')
        self.write(self.game, 'english', 'KEY: "$bunker$ construction speed"')
        self.write(self.root, 'russian', 'KEY: "Скорость строительства укреплений"')
        self.write(self.root, 'english', 'KEY: "$bunker$ construction speed"')
        self.assertFalse(audit(self.root, self.game)['issues'])
        self.write(self.root, 'russian', 'KEY: "Казна [?money|0]"')
        self.assertTrue(any('token mismatch' in issue for issue in audit(self.root, self.game)['issues']))


if __name__ == '__main__':
    unittest.main()
