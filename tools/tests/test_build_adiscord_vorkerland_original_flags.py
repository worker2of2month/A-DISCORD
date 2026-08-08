from __future__ import annotations

import hashlib
import subprocess
import sys
import unittest
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[2]
FLAG_ROOT = ROOT / "gfx" / "flags"
GENERATOR = ROOT / "tools" / "build_adiscord_vorkerland_original_flags.py"

EXPECTED = {
    "ROM": {
        "source": (656, 416, "f514c6536cff405f6600ac8c1054c46cef4594c00ec3ce81c19cf9044eb5812f"),
        "regular": (82, 52, "8db3dc6798518273266ff2cf5ba7b642379ba4a27978f3c9aadf8c613d38ca90"),
        "medium": (41, 26, "b4368011bc71055dee87f1617ba0c2967ea041e27af9e4f7a105819b38f6f751"),
        "small": (10, 7, "b77f5c5adcc104b666bb8bbaf335a14cf5792adf21185ad6faa3315007e6fae1"),
    },
    "TRU": {
        "source": (656, 416, "9f8def60c62e8046973d68592a582eacef2106195041f34aa2751791af9e676d"),
        "regular": (82, 52, "241145a9e73b90ac15e685837aabb5d71a7d7735472107961b75efed869ff4e5"),
        "medium": (41, 26, "1aade5603ff8dd7fd7d777cc0fdaf03521f8a26bd428aa31c1a6c413abfe3aa9"),
        "small": (10, 7, "7286154b5d916266d74a17d73c197ea8e352b9eb57165687946eafe5da87b678"),
    },
    "IBA": {
        "source": (656, 416, "5cf0bd6cc6e50def2705b8489322f23c0c26d520a4c0e110cdaea8d4e0fabc09"),
        "regular": (82, 52, "48b91367638695388934aa0263b26f395fea3fa16a3597d0b343f50863806e77"),
        "medium": (41, 26, "7a9fbb40d0829f7f050420fc36b49b49becdb5385432c2d80fcc2cd031e347cb"),
        "small": (10, 7, "c4dd1da11baf31287dd8f6804dcc1131e7a4a282b8c6a3f5feeb16b385b99bf2"),
    },
}


def image_digest(path: Path, mode: str) -> tuple[int, int, str]:
    with Image.open(path) as image:
        converted = image.convert(mode)
        width, height = converted.size
        digest = hashlib.sha256(converted.tobytes()).hexdigest()
    return width, height, digest


class SuppliedSuccessorFlagTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.result = subprocess.run(
            [sys.executable, "-B", str(GENERATOR)],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )

    def test_generator_runs_from_canonical_sources(self) -> None:
        self.assertEqual(self.result.returncode, 0, self.result.stdout + self.result.stderr)

    def test_supplied_artwork_survives_generation(self) -> None:
        directories = {
            "source": (FLAG_ROOT / "source", "RGB"),
            "regular": (FLAG_ROOT, "RGBA"),
            "medium": (FLAG_ROOT / "medium", "RGBA"),
            "small": (FLAG_ROOT / "small", "RGBA"),
        }
        for flag_id, expected_assets in EXPECTED.items():
            for asset_kind, expected in expected_assets.items():
                directory, mode = directories[asset_kind]
                suffix = ".png" if asset_kind == "source" else ".tga"
                with self.subTest(flag_id=flag_id, asset_kind=asset_kind):
                    self.assertEqual(image_digest(directory / f"{flag_id}{suffix}", mode), expected)

    def test_temporary_supplied_images_are_removed(self) -> None:
        for filename in ("interesting flag 3.png", "ROM NEW.png", "TRU NEW.png"):
            with self.subTest(filename=filename):
                self.assertFalse((FLAG_ROOT / filename).exists())

    def test_joint_government_uses_base_wrk_flag_triplet(self) -> None:
        for directory in (FLAG_ROOT, FLAG_ROOT / "medium", FLAG_ROOT / "small"):
            with self.subTest(directory=directory.name):
                self.assertEqual(
                    (directory / "WRK_vorkerland_joint_government.tga").read_bytes(),
                    (directory / "WRK.tga").read_bytes(),
                )

if __name__ == "__main__":
    unittest.main()
