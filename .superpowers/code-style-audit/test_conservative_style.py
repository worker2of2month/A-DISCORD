import unittest
from conservative_style import format_clausewitz
from style_formatter import token_signature

class ConservativeStyleTests(unittest.TestCase):
    def stable(self, source, expected, **kwargs):
        result = format_clausewitz(source, **kwargs)
        self.assertEqual(result, expected)
        self.assertEqual(token_signature(source), token_signature(result))
        self.assertEqual(result, format_clausewitz(result, **kwargs))
    def test_fixes_indentation_without_expanding_inline_contracts(self):
        self.stable('x = {\n    OR = { tag = A tag = B }\n}\n', 'x = {\n\tOR = { tag = A tag = B }\n}\n')
    def test_preserves_internal_spacing(self):
        self.stable('x={\n   a=3  b=4\n}\n', 'x={\n\ta=3  b=4\n}\n')
    def test_preserves_multiline_strings_and_comments(self):
        self.stable('x={\n  code="hello  \n  { world # }  \n" other=yes\n}\n', 'x={\n\tcode="hello  \n  { world # }  \n" other=yes\n}\n')
    def test_preserves_empty_lines_and_trims_trailing_whitespace(self):
        self.stable('x={\n\n \t\n a=yes  \n}\n\n', 'x={\n\n\n\ta=yes\n}\n\n')
    def test_comment_and_quoted_braces_do_not_change_depth(self):
        self.stable('x={ # {\n a="}" # }\n b=yes\n}\n', 'x={ # {\n\ta="}" # }\n\tb=yes\n}\n')
    def test_fragment_keeps_directive_column_zero(self):
        self.stable('# @section foo\n focus = {\n id=bar\n }\n', '# @section foo\n\tfocus = {\n\t\tid=bar\n\t}\n', base_indent=1)
    def test_multiple_closing_braces(self):
        self.stable('x = {\n a = {\n b=yes\n } }\n', 'x = {\n\ta = {\n\t\tb=yes\n} }\n')
    def test_invalid_input_is_rejected(self):
        for value in ['x={', 'x=}', 'x="unfinished']:
            with self.assertRaises(ValueError): format_clausewitz(value)
    def test_empty_file(self):
        self.stable('', '')
