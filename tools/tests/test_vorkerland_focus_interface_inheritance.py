from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
VANILLA_ROOT = Path("Z:/SteamLibrary/steamapps/common/Hearts of Iron IV")
ADDITIVE_SHINES = ROOT / "interface/ADISCORD_focus_shines.gfx"
NATIONAL_FOCUS_GFX = ROOT / "interface/ADISCORD_national_focus.gfx"
VANILLA_SHINES = VANILLA_ROOT / "interface/goals_shine.gfx"
EXPECTED_CUSTOM_ONLY_SPRITES = 254
CONTINUOUS_FOCUS_PALETTE = ROOT / "common/continuous_focus/generic.txt"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def sprite_blocks(source: str) -> list[str]:
    blocks: list[str] = []
    for match in re.finditer(r"(?m)^[ \t]*SpriteType\s*=\s*\{", source):
        depth = 0
        for index in range(match.start(), len(source)):
            char = source[index]
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    blocks.append(source[match.start() : index + 1])
                    break
        else:
            raise AssertionError("unbalanced SpriteType block")
    return blocks


def sprite_names(source: str) -> list[str]:
    names: list[str] = []
    for block in sprite_blocks(source):
        match = re.search(r'\bname\s*=\s*"([^"]+)"', block)
        if match:
            names.append(match.group(1))
    return names


def texture_paths(source: str) -> list[str]:
    return re.findall(
        r'\b(?:texturefile|animationmaskfile)\s*=\s*"([^"]+)"',
        source,
    )


def texture_resolves(relative: str) -> bool:
    return (ROOT / relative).is_file() or (VANILLA_ROOT / relative).is_file()


class VorkerlandFocusInterfaceInheritanceTests(unittest.TestCase):
    def test_focus_interface_does_not_shadow_current_vanilla(self) -> None:
        self.assertFalse((ROOT / "interface/nationalfocusview.gui").exists())
        self.assertFalse((ROOT / "interface/goals_shine.gfx").exists())
        self.assertTrue(ADDITIVE_SHINES.is_file())

    def test_additive_shines_are_unique_and_do_not_overlap_vanilla(self) -> None:
        self.assertTrue(VANILLA_SHINES.is_file())
        custom_names = sprite_names(read(ADDITIVE_SHINES))
        vanilla_names = set(sprite_names(read(VANILLA_SHINES)))
        self.assertEqual(len(custom_names), EXPECTED_CUSTOM_ONLY_SPRITES)
        self.assertEqual(len(custom_names), len(set(custom_names)))
        self.assertEqual(set(custom_names) & vanilla_names, set())

    def test_custom_focus_and_shine_textures_resolve(self) -> None:
        missing: list[str] = []
        for gfx_file in (NATIONAL_FOCUS_GFX, ADDITIVE_SHINES):
            for relative in texture_paths(read(gfx_file)):
                if not texture_resolves(relative):
                    missing.append(f"{gfx_file.name}: {relative}")
        self.assertEqual(missing, [])

    def test_custom_mechanized_small_icon_exists(self) -> None:
        source = read(ROOT / "interface/ADISCORD_subuniticons.gfx")
        self.assertIn(
            'name = "GFX_unit_ADISCORD_mechanized_infantry_icon_small"',
            source,
        )
        self.assertIn(
            'texturefile = "gfx/texticons/unit_mechanized_icon_small.dds"',
            source,
        )

    def test_mod_continuous_focus_palette_remains_empty(self) -> None:
        source = read(CONTINUOUS_FOCUS_PALETTE)
        self.assertIn("continuous_focus_palette = {", source)
        self.assertIn("id = generic_focus", source)
        self.assertIn("default = yes", source)
        self.assertNotRegex(source, r"(?m)^\s*focus\s*=")


if __name__ == "__main__":
    unittest.main()
