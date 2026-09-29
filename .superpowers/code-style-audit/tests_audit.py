import unittest
from style_formatter import format_clausewitz, token_signature, format_localisation, format_lua_defines

class StyleTests(unittest.TestCase):
    def assert_stable(self, source, expected=None, **kwargs):
        formatted = format_clausewitz(source, **kwargs)
        if expected is not None:
            self.assertEqual(formatted, expected)
        self.assertEqual(token_signature(source), token_signature(formatted))
        self.assertEqual(formatted, format_clausewitz(formatted, **kwargs))
        return formatted

    def test_compound_conditions_are_separate_lines(self):
        self.assert_stable('x = { OR = { tag = A tag = B } }\n', 'x = {\n\tOR = {\n\t\ttag = A\n\t\ttag = B\n\t}\n}\n')

    def test_documentation_comment_stays_attached_to_definition(self):
        source = 'first = { x = yes }\n\n# Documents second.\nsecond = { y = no }\n'
        self.assert_stable(source, source)

    def test_atomic_conditions_remain_compact(self):
        self.assert_stable('NOT={has_country_flag=foo}\n', 'NOT = { has_country_flag = foo }\n')

    def test_atomic_parameter_payload_remains_compact(self):
        self.assert_stable('country_event={id=foo.1 days=7}\n', 'country_event = { id = foo.1 days = 7 }\n')

    def test_nested_scopes_and_inline_comment(self):
        self.assert_stable('x={if={limit={tag=A has_war=yes} a=yes} # scope\n}\n', 'x = {\n\tif = {\n\t\tlimit = {\n\t\t\ttag = A\n\t\t\thas_war = yes\n\t\t}\n\t\ta = yes\n\t} # scope\n}\n')

    def test_quoted_braces_comments_and_escapes(self):
        self.assert_stable('x = { text = "a # { } \\" c" other = "one  two" }\n')

    def test_multiline_literal_is_byte_preserved(self):
        source = 'x={code="foo\n  bar { baz } # x\n" y=yes}\n'
        self.assertIn('"foo\n  bar { baz } # x\n"', self.assert_stable(source))

    def test_comments_blank_lines_and_top_level_spacing(self):
        self.assert_stable('# head  \n\n\nx={a=yes}\ny={b=no}\n', '# head\n\nx = { a = yes }\n\ny = { b = no }\n')

    def test_focus_fragment_and_column_zero_directives(self):
        result = self.assert_stable('# @section first\n    focus={id=one x=2}\n', base_indent=1)
        self.assertTrue(result.startswith('# @section first\n\tfocus = {\n'))

    def test_comparison_operators_and_rgb(self):
        self.assert_stable('x={a>=2 b<3 c!=4 color=rgb{0 1 2}}\n')

    def test_already_multiline_atomic_is_not_collapsed(self):
        source = 'NOT = {\n\thas_country_flag = foo\n}\n'
        self.assert_stable(source, source)

    def test_empty_and_bom(self):
        self.assert_stable('')
        self.assert_stable('\ufeffx={a=yes}\r\n')

    def test_rejects_unbalanced_and_unterminated(self):
        for source in ['x = {', 'x = }', 'x = "unfinished']:
            with self.assertRaises(ValueError):
                format_clausewitz(source)

    def test_line_break_ends_comment(self):
        self.assertIn('\n\tb = no\n', self.assert_stable('x = { a = yes # hide no tokens\n b = no }\n'))

    def test_localisation_preserves_strings(self):
        source = ' l_russian:\n\tkey:0   "Текст  с  пробелами \\n и # знаком"   \n'
        expected = 'l_russian:\n key:0 "Текст  с  пробелами \\n и # знаком"\n'
        self.assertEqual(format_localisation(source), expected)
        self.assertEqual(format_localisation(expected), expected)

    def test_localisation_bom_and_empty(self):
        self.assertEqual(format_localisation(''), '')
        self.assertEqual(format_localisation('\ufeffl_english:\n key: "x"\n'), 'l_english:\n key: "x"\n')

    def test_localisation_rejects_multiline_values(self):
        with self.assertRaises(ValueError):
            format_localisation('l_english:\n key: "unfinished\nvalue"\n')

    def test_lua_top_level_assignments_and_nested_table(self):
        source = ' NDefines.X = "2160.1.1.1";\n\t-- comment\n\tNDefines.Y = {\n        0.1,\n\t\t0.2,\n\t}\n'
        expected = 'NDefines.X = "2160.1.1.1";\n-- comment\nNDefines.Y = {\n\t0.1,\n\t0.2,\n}\n'
        self.assertEqual(format_lua_defines(source), expected)
        self.assertEqual(format_lua_defines(expected), expected)

    def test_lua_quote_and_comment_do_not_change_depth(self):
        source = '  NDefines.X = "{ -- }" -- { comment\n\tNDefines.Y = 2\n'
        self.assertEqual(format_lua_defines(source), 'NDefines.X = "{ -- }" -- { comment\nNDefines.Y = 2\n')
