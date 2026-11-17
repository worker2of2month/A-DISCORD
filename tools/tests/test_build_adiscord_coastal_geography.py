"""Colourmap generation preserves authored ground outside new islands."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
import unittest

import numpy as np
from PIL import Image

from tools.builders import build_adiscord_coastal_geography as geography


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "tools/assets/source/map/colormap_rgb_cityemissivemask_a.dds"


class CoastalColourmapTests(unittest.TestCase):
    def test_river_bmp_uses_implicit_colour_counts_and_preserves_every_index(self) -> None:
        with Image.open(ROOT / "map/rivers.bmp") as source:
            river = source.crop((0, 0, 16, 16))
        river.putdata(range(256))
        encoded = BytesIO()
        river.save(encoded, format="BMP")
        original = encoded.getvalue()
        result = geography.native_river_bmp(original)
        self.assertEqual(result[:46], original[:46])
        self.assertEqual(result[46:54], bytes(8))
        self.assertEqual(result[54:], original[54:])
        self.assertEqual(geography.native_river_bmp(result), result)
        with Image.open(BytesIO(result)) as decoded:
            self.assertEqual(decoded.getpalette(), river.getpalette())
            self.assertEqual(decoded.tobytes(), bytes(range(256)))

    def test_runtime_preserves_base_except_island_blocks(self) -> None:
        definitions = {
            int(fields[0]): tuple(map(int, fields[1:4]))
            for line in (ROOT / "map/definition.csv").read_text().splitlines()
            if len(fields := line.split(";")) >= 8
        }
        with Image.open(ROOT / "map/provinces.bmp") as source:
            provinces = np.asarray(source.convert("RGB"))
        islands = np.zeros(provinces.shape[:2], dtype=bool)
        for province in geography.ISLANDS:
            islands |= np.all(provinces == definitions[province], axis=2)
        expected = geography.patch_colourmap(SOURCE.read_bytes(), islands)
        actual = (ROOT / geography.COLOURMAP).read_bytes()
        self.assertEqual(actual[:128], expected[:128])
        self.assertEqual(len(actual), len(expected))
        differing_blocks = sum(
            actual[offset:offset + 16] != expected[offset:offset + 16]
            for offset in range(128, len(actual), 16)
        )
        self.assertEqual(differing_blocks, 0)

    def test_island_patch_preserves_other_compressed_blocks(self) -> None:
        encoded = BytesIO()
        Image.new("RGBA", (8, 8), (45, 65, 35, 75)).save(
            encoded, format="DDS", pixel_format="DXT5"
        )
        original = encoded.getvalue()
        mask = np.zeros((16, 16), dtype=bool)
        mask[2, 2] = True
        patched = geography.patch_colourmap(original, mask)
        self.assertEqual(patched[:128], original[:128])
        self.assertNotEqual(patched[128:144], original[128:144])
        self.assertEqual(patched[144:], original[144:])
        self.assertEqual(geography.patch_colourmap(patched, mask), patched)


if __name__ == "__main__":
    unittest.main()
