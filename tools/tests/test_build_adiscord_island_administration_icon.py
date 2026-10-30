from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from PIL import Image

from tools.builders import build_adiscord_island_administration_icon as builder


class IslandAdministrationIconBuilderTests(unittest.TestCase):
    def test_runtime_icon_is_current_and_has_transparent_padding(self) -> None:
        self.assertEqual(builder.drift(), [])
        with Image.open(builder.ICON) as icon:
            self.assertEqual(icon.mode, "RGBA")
            self.assertEqual(icon.size, (35, 36))
            self.assertEqual(icon.getpixel((0, 0))[3], 0)

    def test_political_and_island_flags_are_distinct_at_every_size(self) -> None:
        for folder, size in builder.FLAG_SIZES.items():
            textures = []
            for tag in (*builder.FLAG_IDS, *builder.IMPORTED_FLAGS):
                path = builder.ROOT / "gfx/flags" / folder / f"{tag}.tga"
                with self.subTest(flag=path):
                    textures.append(path.read_bytes())
                    with Image.open(path) as flag:
                        self.assertEqual(flag.size, size)
                        self.assertEqual(flag.mode, "RGBA")
                        self.assertEqual(flag.getchannel("A").getextrema(), (255, 255))
            self.assertEqual(len(set(textures)), len(textures))

    def test_imported_flags_rebuild_without_external_originals(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "external.png"
            Image.new("RGBA", (164, 104), (31, 53, 71, 255)).save(source)
            imports = {tag: source for tag in builder.IMPORTED_FLAGS}
            with patch.object(builder, "ROOT", root):
                planned = builder.render_flags(imports)
                for path, data in planned.items():
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(data)
                source.unlink()
                self.assertEqual(builder.render_flags(), planned)


if __name__ == "__main__":
    unittest.main()
