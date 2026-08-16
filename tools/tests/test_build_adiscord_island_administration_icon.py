from __future__ import annotations

import unittest

from PIL import Image

from tools.builders import build_adiscord_island_administration_icon as builder


class IslandAdministrationIconBuilderTests(unittest.TestCase):
    def test_runtime_icon_is_current_and_has_transparent_padding(self) -> None:
        self.assertEqual(builder.drift(), [])
        with Image.open(builder.ICON) as icon:
            self.assertEqual(icon.mode, "RGBA")
            self.assertEqual(icon.size, (35, 36))
            self.assertEqual(icon.getpixel((0, 0))[3], 0)

    def test_iia_placeholder_flags_are_byte_identical_to_ivn(self) -> None:
        for source, target in builder.FLAG_PAIRS:
            with self.subTest(flag=target):
                self.assertEqual(target.read_bytes(), source.read_bytes())


if __name__ == "__main__":
    unittest.main()
