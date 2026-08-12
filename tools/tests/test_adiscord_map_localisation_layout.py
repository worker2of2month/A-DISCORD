from __future__ import annotations

import codecs
import re
import tempfile
import unittest
from pathlib import Path

from tools.lib.localisation import replace_generated_localisation_block


ROOT = Path(__file__).resolve().parents[2]
RUSSIAN = ROOT / "localisation" / "russian"
STATE_LOCALISATION = RUSSIAN / "state_names_l_russian.yml"
VP_LOCALISATION = RUSSIAN / "victory_points_l_russian.yml"


class MapLocalisationLayoutTests(unittest.TestCase):
    def test_numeric_map_keys_live_only_in_canonical_files(self) -> None:
        misplaced: list[str] = []
        for path in sorted(RUSSIAN.glob("*.yml")):
            source = path.read_text(encoding="utf-8-sig", errors="strict")
            if path != STATE_LOCALISATION and re.search(r"(?m)^\s*STATE_\d+\s*:", source):
                misplaced.append(f"numeric STATE keys in {path.name}")
            if path != VP_LOCALISATION and re.search(r"(?m)^\s*VICTORY_POINTS_\d+\s*:", source):
                misplaced.append(f"numeric VICTORY_POINTS keys in {path.name}")
        self.assertEqual(misplaced, [])

    def test_canonical_files_keep_bom_and_unique_numeric_keys(self) -> None:
        for path, prefix in (
            (STATE_LOCALISATION, "STATE"),
            (VP_LOCALISATION, "VICTORY_POINTS"),
        ):
            with self.subTest(path=path.name):
                self.assertTrue(path.read_bytes().startswith(codecs.BOM_UTF8))
                source = path.read_text(encoding="utf-8-sig", errors="strict")
                keys = re.findall(rf"(?m)^\s*({prefix}_\d+)\s*:", source)
                duplicates = sorted({key for key in keys if keys.count(key) > 1})
                self.assertEqual(duplicates, [])

    def test_generated_blocks_update_without_touching_unrelated_keys(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "shared_l_russian.yml"
            path.write_text(
                'l_russian:\n KEEP: "Сохранить"\n',
                encoding="utf-8-sig",
                newline="\n",
            )
            marker = "tools.builders.example"
            replace_generated_localisation_block(path, marker, {"STATE_1": "Первый"})
            replace_generated_localisation_block(path, marker, {"STATE_2": "Второй"})

            self.assertTrue(path.read_bytes().startswith(codecs.BOM_UTF8))
            source = path.read_text(encoding="utf-8-sig", errors="strict")
            self.assertIn(' KEEP: "Сохранить"', source)
            self.assertNotIn("STATE_1:", source)
            self.assertEqual(source.count(' STATE_2: "Второй"'), 1)
            self.assertEqual(source.count(f" # BEGIN GENERATED: {marker}"), 1)
            self.assertEqual(source.count(f" # END GENERATED: {marker}"), 1)


if __name__ == "__main__":
    unittest.main()
