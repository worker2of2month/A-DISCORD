"""Coverage checks must distinguish native fallbacks from authored overrides."""

from pathlib import Path
from contextlib import redirect_stdout
import io
import sys
import tempfile
import unittest
from unittest.mock import patch

from tools.validators.validate_adiscord_english_localisation import ENTRY, audit


class LocalisationGlyphTests(unittest.TestCase):
    def setUp(self):
        from tools.validators import validate_tc

        self.validator = validate_tc
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        root_patch = patch.object(validate_tc, "ROOT", self.root)
        root_patch.start()
        self.addCleanup(root_patch.stop)

    def write(self, entries, language="russian", filename="ADISCORD_test"):
        path = self.root / "localisation" / language / f"{filename}_l_{language}.yml"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"l_{language}:\n{entries}\n", encoding="utf-8-sig")
        return path

    def test_missing_glyphs_report_key_line_code_and_replacement(self):
        cases = {
            "\u2212": "-",
            "\u2022": "-",
            "\u2192": "->",
            "\u2026": "...",
            "\u2116": "N",
            "\u0219": "s",
        }
        for character, replacement in cases.items():
            with self.subTest(code=ord(character)):
                path = self.write(f' SAMPLE:0 "{character}"')
                issues, count = self.validator.check_localisation(100)
                self.assertEqual(count, 1)
                self.assertIn(f"{path.name}:2: SAMPLE:", issues[0])
                self.assertIn(f"U+{ord(character):04X}", issues[0])
                self.assertIn(f"use {replacement!r}", issues[0])

    def test_unseen_symbols_and_hidden_characters_are_rejected(self):
        for character in ("\U0001f600", "\u200b", "\ufeff", "\ufffd", "\t", "\u2028"):
            with self.subTest(code=ord(character)):
                self.write(f' SAMPLE:0 "before{character}after"')
                issues, count = self.validator.check_localisation(100)
                self.assertEqual(count, 1)
                self.assertIn(f"U+{ord(character):04X}", issues[0])

    def test_supported_text_and_native_markup_are_accepted(self):
        self.write(
            ' SAMPLE:0 "Ёж, ёлка, \u00abкавычки\u00bb, à ä ç Æ, ±50, 2 × 3, ·, ’, „text“'
            r'\n\n§G+10%§! £political_power_texticon $NAME|H$ '
            r'''[?FROM.amount|0] [GetText] @STP 'quoted' \"quoted\""'''
        )
        self.assertEqual(self.validator.check_localisation(100), ([], 0))

    def test_comments_are_not_checked_but_all_catalogues_are(self):
        self.write('# \u2022 comment\n GOOD: "Valid" # \u2212 comment')
        for language in ("russian", "english"):
            self.write(' BAD: "\u2022"', language, "vanilla_override")
        issues, count = self.validator.check_localisation(100)
        self.assertEqual(count, 2)
        self.assertTrue(all("vanilla_override" in issue for issue in issues))

    def test_limit_does_not_hide_total_or_duplicate_glyphs_within_a_value(self):
        self.write(' FIRST: "\u2022\u2022"\n SECOND: "\u2212"')
        issues, count = self.validator.check_localisation(1)
        self.assertEqual((len(issues), count), (1, 2))
        self.assertIn("FIRST", issues[0])
        self.assertEqual(self.validator.check_localisation(0), ([], 2))

    def test_invalid_utf8_is_not_silently_read_as_another_encoding(self):
        path = self.write(' BAD: "text"')
        path.write_bytes(b'l_russian:\n BAD: "\xff"\n')
        issues, count = self.validator.check_localisation(100)
        self.assertEqual(count, 1)
        self.assertIn("invalid UTF-8 localisation", issues[0])

    def test_focused_cli_fails_even_when_examples_are_hidden_and_never_writes(self):
        path = self.write(' BAD: "\u2022"')
        before = path.read_bytes()
        output = io.StringIO()
        with patch.object(sys, "argv", ["validate_tc", "--localisation-only", "--limit", "0"]):
            with redirect_stdout(output):
                status = self.validator.main()
        self.assertEqual(status, 1)
        self.assertIn("Localisation: 1", output.getvalue())
        self.assertEqual(path.read_bytes(), before)
        self.write(' GOOD: "Correct - text"')
        with patch.object(sys, "argv", ["validate_tc", "--localisation-only"]):
            with redirect_stdout(io.StringIO()):
                self.assertEqual(self.validator.main(), 0)


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
