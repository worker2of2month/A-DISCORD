from __future__ import annotations

import re
import unittest

from tools.validators.validate_adiscord_vorkerland_civil_war_focus import (
    FOCUS_FILE,
    FOCUS_GFX_FILE,
    SHINE_FILE,
    WRK_TREE_FOCUSES,
    focus_blocks,
    read,
    wrk_focus_icon_name,
    wrk_focus_texture_path,
)


class WrkFocusIconSlotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.blocks = focus_blocks(read(FOCUS_FILE))
        cls.focus_gfx = read(FOCUS_GFX_FILE)
        cls.shine = read(SHINE_FILE)

    def test_manifest_covers_prewar_and_postwar_wrk_only(self) -> None:
        self.assertEqual(len(WRK_TREE_FOCUSES), 40)
        self.assertTrue(all(focus_id.startswith("WRK_") for focus_id in WRK_TREE_FOCUSES))
        self.assertEqual(len(set(WRK_TREE_FOCUSES)), 40)

    def test_each_wrk_focus_uses_its_drop_in_sprite(self) -> None:
        for focus_id in WRK_TREE_FOCUSES:
            with self.subTest(focus_id=focus_id):
                sprite = wrk_focus_icon_name(focus_id)
                texture = wrk_focus_texture_path(focus_id)
                icon_line = next(
                    line.strip()
                    for line in self.blocks[focus_id].splitlines()
                    if line.strip().startswith("icon = ")
                )
                self.assertEqual(icon_line, f"icon = {sprite}")
                self.assertIn(f'name = "{sprite}"', self.focus_gfx)
                self.assertIn(f'texturefile = "{texture}"', self.focus_gfx)
                self.assertIn(f'name = "{sprite}_shine"', self.shine)
                self.assertIn(f'texturefile = "{texture}"', self.shine)

    def test_registered_wrk_focus_sprites_match_the_manifest(self) -> None:
        sprite_names = set(
            re.findall(r'name = "(GFX_focus_WRK_[A-Za-z0-9_]+)"', self.focus_gfx)
        )
        self.assertEqual(
            sprite_names,
            {wrk_focus_icon_name(focus_id) for focus_id in WRK_TREE_FOCUSES},
        )


if __name__ == "__main__":
    unittest.main()
