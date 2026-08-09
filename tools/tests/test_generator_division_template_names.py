from __future__ import annotations

import re
import unittest

from tools.builders import build_adiscord_ainholm_mandate as ainholm
from tools.builders import build_adiscord_inner_frontier_countries as inner
from tools.builders import build_adiscord_northern_countries as northern


PRINTABLE_ASCII = re.compile(r"^[\x20-\x7e]+$")
CYRILLIC = re.compile(r"[\u0400-\u04ff]")
TEMPLATE_DEFINITION = re.compile(
    r'division_template\s*=\s*\{\s*name\s*=\s*"([^"]+)"',
    re.MULTILINE,
)
TEMPLATE_REFERENCE = re.compile(r'division_template\s*=\s*"([^"]+)"')


class GeneratorDivisionTemplateNameTests(unittest.TestCase):
    def assert_printable_ascii(self, name: str) -> None:
        self.assertRegex(name, PRINTABLE_ASCII)
        self.assertNotRegex(name, CYRILLIC)

    def rendered_oobs(self) -> tuple[str, ...]:
        principal_provinces = {1: 101, 2: 102}
        infantry = {
            "states": (1, 2),
            "capital": 1,
            "divisions": 2,
            "unit_type": "infantry",
        }
        militia = {
            "states": (1, 2),
            "capital": 1,
            "divisions": 2,
            "unit_type": "ADISCORD_militia",
        }
        return (
            ainholm.render_oob(),
            inner.render_oob("RIN", infantry, principal_provinces),
            inner.render_oob(inner.PROTECTORATE_TAG, infantry, principal_provinces),
            inner.render_oob("BOR", infantry, principal_provinces),
            inner.render_oob("DOL", militia, principal_provinces),
            northern.render_oob("MON", {**infantry, "divisions": 14}, principal_provinces),
            northern.render_oob("BRN", infantry, principal_provinces),
            northern.render_oob("VRA", militia, principal_provinces),
        )

    def test_generator_template_constants_are_printable_ascii(self) -> None:
        constants = (
            getattr(ainholm, "DIVISION_TEMPLATE_NAMES", ()),
            getattr(inner, "DIVISION_TEMPLATE_NAMES", ()),
            getattr(northern, "DIVISION_TEMPLATE_NAMES", ()),
        )
        self.assertTrue(all(constants), "each OOB generator must expose its technical template names")
        names = tuple(name for group in constants for name in group)
        self.assertEqual(
            set(names),
            {
                "Licensed Security Battalion",
                "Palatine Line Division",
                "Filtration Battalion",
                "Frontier Brigade",
                "Settler Militia",
                "Imperial Line Division",
                "Imperial Frontier Brigade",
                "Northern Line Brigade",
                "Northern Militia",
            },
        )
        for name in names:
            with self.subTest(name=name):
                self.assert_printable_ascii(name)

    def test_rendered_template_definitions_and_references_are_printable_ascii(self) -> None:
        observed: set[str] = set()
        for oob in self.rendered_oobs():
            names = TEMPLATE_DEFINITION.findall(oob) + TEMPLATE_REFERENCE.findall(oob)
            self.assertTrue(names)
            for name in names:
                with self.subTest(name=name):
                    self.assert_printable_ascii(name)
                    observed.add(name)
        self.assertEqual(
            observed,
            {
                "Licensed Security Battalion",
                "Palatine Line Division",
                "Filtration Battalion",
                "Frontier Brigade",
                "Settler Militia",
                "Imperial Line Division",
                "Imperial Frontier Brigade",
                "Northern Line Brigade",
                "Northern Militia",
            },
        )


if __name__ == "__main__":
    unittest.main()
