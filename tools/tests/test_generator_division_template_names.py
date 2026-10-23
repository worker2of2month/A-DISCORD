from __future__ import annotations

import re
import unittest

from tools.builders import build_adiscord_ainholm_mandate as ainholm
from tools.builders import build_adiscord_inner_frontier_countries as inner
from tools.builders import build_adiscord_northern_countries as northern
from tools.lib import adiscord_remainder_countries as remainder


CYRILLIC = re.compile(r"[\u0400-\u04ff]")
TEMPLATE_DEFINITION = re.compile(
    r'division_template\s*=\s*\{\s*name\s*=\s*"([^"]+)"',
    re.MULTILINE,
)
TEMPLATE_REFERENCE = re.compile(r'division_template\s*=\s*"([^"]+)"')


class GeneratorDivisionTemplateNameTests(unittest.TestCase):
    def test_remainder_countries_reuse_a_tag_free_role_name(self) -> None:
        for tag, row in remainder.COUNTRIES.items():
            with self.subTest(tag=tag):
                oob = remainder.country_oob(tag, row)
                self.assertEqual(TEMPLATE_DEFINITION.findall(oob), ["Территориальная бригада"])
                self.assertEqual(set(TEMPLATE_REFERENCE.findall(oob)), {"Территориальная бригада"})
                self.assertIn("template_counter = 12", oob)

    def assert_russian_name(self, name: str) -> None:
        self.assertTrue(name.isprintable())
        self.assertRegex(name, CYRILLIC)
        self.assertNotRegex(name, r"[A-Za-z]")

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
            northern.render_oob(
                "MON", {**infantry, "divisions": 36, "line_divisions": 28}, principal_provinces
            ),
            northern.render_oob("BRN", infantry, principal_provinces),
            northern.render_oob("VRA", militia, principal_provinces),
        )

    def test_generator_template_constants_are_russian(self) -> None:
        constants = (
            getattr(ainholm, "DIVISION_TEMPLATE_NAMES", ()),
            getattr(inner, "DIVISION_TEMPLATE_NAMES", ()),
            getattr(northern, "DIVISION_TEMPLATE_NAMES", ()),
        )
        self.assertTrue(
            all(constants),
            "each OOB generator must expose its player-visible template names",
        )
        names = tuple(name for group in constants for name in group)
        self.assertEqual(
            set(names),
            {
                "Лицензированный охранный батальон",
                "Палатинская линейная дивизия",
                "Фильтрационный батальон",
                "Пограничная бригада",
                "Ополчение поселенцев",
                "Имперская линейная дивизия",
                "Имперская пограничная бригада",
                "Северная линейная бригада",
                "Северное ополчение",
            },
        )
        for name in names:
            with self.subTest(name=name):
                self.assert_russian_name(name)

    def test_rendered_template_definitions_and_references_are_russian(
        self,
    ) -> None:
        observed: set[str] = set()
        for oob in self.rendered_oobs():
            names = TEMPLATE_DEFINITION.findall(oob) + TEMPLATE_REFERENCE.findall(oob)
            self.assertTrue(names)
            for name in names:
                with self.subTest(name=name):
                    self.assert_russian_name(name)
                    observed.add(name)
        self.assertEqual(
            observed,
            {
                "Лицензированный охранный батальон",
                "Палатинская линейная дивизия",
                "Фильтрационный батальон",
                "Пограничная бригада",
                "Ополчение поселенцев",
                "Имперская линейная дивизия",
                "Имперская пограничная бригада",
                "Северная линейная бригада",
                "Северное ополчение",
            },
        )


if __name__ == "__main__":
    unittest.main()
