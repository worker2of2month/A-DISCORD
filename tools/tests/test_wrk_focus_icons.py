from __future__ import annotations

import re
import unittest

from tools.lib.paths import source_section
from tools.validators.validate_adiscord_vorkerland_civil_war_focus import (
    CONFEDERATION_EXECUTIVE_FOCUSES,
    CONFEDERATION_EXECUTIVE_TEXTURES,
    CONFEDERATION_FILE,
    EXECUTIVE_TEXTURES,
    FOCUS_FALLBACK_TEXTURE,
    FOCUS_FILE,
    FOCUS_GFX_FILE,
    POSTWAR_EXECUTIVE_FOCUSES,
    POSTWAR_EXECUTIVE_TEXTURES,
    SHINE_FILE,
    WRK_TREE_FOCUSES,
    _check_focus_gfx,
    _sprite_texture,
    focus_blocks,
    read,
    wrk_focus_icon_name,
    wrk_focus_texture_path,
)


class WrkFocusIconSlotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.blocks = focus_blocks(source_section(read(FOCUS_FILE), 'civil_war_focus'))
        cls.focus_gfx = read(FOCUS_GFX_FILE)
        cls.shine = read(SHINE_FILE)

    def test_manifest_covers_prewar_and_postwar_wrk_only(self) -> None:
        self.assertEqual(len(WRK_TREE_FOCUSES), 139)
        self.assertTrue(
            all(focus_id.startswith("WRK_") for focus_id in WRK_TREE_FOCUSES)
        )
        self.assertEqual(len(set(WRK_TREE_FOCUSES)), 139)

    def test_committee_focuses_bind_their_own_native_art(self) -> None:
        self.assertEqual(set(POSTWAR_EXECUTIVE_TEXTURES), set(POSTWAR_EXECUTIVE_FOCUSES))
        self.assertEqual(
            set(CONFEDERATION_EXECUTIVE_TEXTURES), set(CONFEDERATION_EXECUTIVE_FOCUSES)
        )
        # Different actions are not drawn with one picture, in either tree.
        self.assertEqual(len(EXECUTIVE_TEXTURES), 22)
        self.assertEqual(len(set(EXECUTIVE_TEXTURES.values())), 22)
        confederation = read(CONFEDERATION_FILE)
        for focus_id in CONFEDERATION_EXECUTIVE_FOCUSES:
            self.assertEqual(
                confederation.count(f"icon = {wrk_focus_icon_name(focus_id)}\n"), 1, focus_id
            )
        for focus_id, texture in EXECUTIVE_TEXTURES.items():
            with self.subTest(focus_id=focus_id):
                sprite = wrk_focus_icon_name(focus_id)
                self.assertRegex(texture, r"^gfx/interface/goals/[a-z_0-9]+\.dds$")
                self.assertNotEqual(texture, FOCUS_FALLBACK_TEXTURE)
                self.assertEqual(wrk_focus_texture_path(focus_id), texture)
                self.assertEqual(_sprite_texture(self.focus_gfx, sprite), texture)
                self.assertEqual(_sprite_texture(self.shine, f"{sprite}_shine"), texture)
                # The shine mask has to be the same picture as the icon.
                shine = self.shine[self.shine.index(f'name = "{sprite}_shine"'):]
                shine = shine[: shine.index("legacy_lazy_load")]
                self.assertIn(f'animationmaskfile = "{texture}"', shine)

    def test_sprite_binding_rejects_a_swapped_texture(self) -> None:
        focus_id = POSTWAR_EXECUTIVE_FOCUSES[0]
        texture = POSTWAR_EXECUTIVE_TEXTURES[focus_id]
        mutated = self.focus_gfx.replace(
            f'name = "{wrk_focus_icon_name(focus_id)}"\n\t\ttexturefile = "{texture}"',
            f'name = "{wrk_focus_icon_name(focus_id)}"\n\t\ttexturefile = "{FOCUS_FALLBACK_TEXTURE}"',
            1,
        )
        self.assertNotEqual(mutated, self.focus_gfx)
        issues = _check_focus_gfx(mutated, self.shine)
        self.assertIn(
            f"{wrk_focus_icon_name(focus_id)} in {FOCUS_GFX_FILE.as_posix()} must use {texture}",
            issues,
        )
        self.assertEqual(_check_focus_gfx(self.focus_gfx, self.shine), [])

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

    def test_registered_wrk_focus_sprites_cover_the_prewar_manifest(self) -> None:
        sprite_names = set(
            re.findall(r'name = "(GFX_focus_WRK_[A-Za-z0-9_]+)"', self.focus_gfx)
        )
        expected = {wrk_focus_icon_name(focus_id) for focus_id in WRK_TREE_FOCUSES}
        self.assertTrue(expected <= sprite_names, expected - sprite_names)


if __name__ == "__main__":
    unittest.main()
