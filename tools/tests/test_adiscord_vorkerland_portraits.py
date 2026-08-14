from __future__ import annotations

import re
import struct
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PORTRAIT_IDS = tuple(f"GFX_Portrait_WRK_Generic_land_{index}" for index in range(1, 4))


def named_block(source: str, name: str) -> str:
    match = re.search(rf"(?m)^\s*{re.escape(name)}\s*=\s*\{{", source)
    if not match:
        return ""
    start = match.start()
    opening = source.find("{", match.start(), match.end())
    depth = 0
    for index in range(opening, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[start : index + 1]
    return ""


class VorkerlandRandomPortraitTests(unittest.TestCase):
    def test_worker_claimant_uses_the_wrk_commander_pool(self) -> None:
        pools = (ROOT / "portraits" / "00_portraits.txt").read_text(encoding="utf-8-sig")
        expected = set(PORTRAIT_IDS)
        for tag in ("WRK", "WKR"):
            block = named_block(pools, tag)
            self.assertTrue(block, f"missing {tag} portrait pool")
            actual = set(re.findall(r'"(GFX_Portrait_WRK_Generic_land_\d+)"', block))
            self.assertEqual(actual, expected)

    def test_wrk_commander_sprites_resolve_to_valid_large_portraits(self) -> None:
        sprites = (ROOT / "interface" / "_random_portraits.gfx").read_text(
            encoding="utf-8-sig"
        )
        for index, portrait_id in enumerate(PORTRAIT_IDS, start=1):
            self.assertIn(f'name = "{portrait_id}"', sprites)
            relative = Path(
                f"gfx/leaders/WRK/default/portrait_WRK_generic_land_{index}.png"
            )
            self.assertIn(f'texturefile = "{relative.as_posix()}"', sprites)
            data = (ROOT / relative).read_bytes()
            self.assertEqual(data[:8], b"\x89PNG\r\n\x1a\n")
            width, height = struct.unpack(">II", data[16:24])
            self.assertEqual((width, height), (156, 210))


if __name__ == "__main__":
    unittest.main()
