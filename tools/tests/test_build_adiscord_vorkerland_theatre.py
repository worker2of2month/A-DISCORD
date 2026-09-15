from __future__ import annotations

import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch

from tools.builders import build_adiscord_vorkerland_theatre as theatre


class VorkerlandTheatreBuilderTests(unittest.TestCase):
    def test_current_generated_rail_record_is_valid(self) -> None:
        self.assertEqual(theatre.validate(), [])

    def test_update_is_idempotent_and_preserves_unmanaged_lines(self) -> None:
        unmanaged = "1 2 100 101\n"
        first = theatre.update_source(unmanaged)
        second = theatre.update_source(first)
        self.assertEqual(second, first)
        self.assertTrue(first.startswith(unmanaged))
        self.assertEqual(first.splitlines().count(theatre.render_managed_line()), 1)
        self.assertNotIn("#", first)

    def test_supply_update_is_idempotent_and_preserves_unmanaged_lines(self) -> None:
        unmanaged = "1 100 \n"
        first = theatre.update_supply_source(unmanaged)
        second = theatre.update_supply_source(first)
        self.assertEqual(second, first)
        self.assertTrue(first.startswith(unmanaged))
        for province_id in theatre.VORKERLAND_SUPPLY_HUB_STATES:
            self.assertEqual(
                first.splitlines().count(theatre.render_supply_node(province_id)), 1
            )

    def test_starting_supply_routes_preserve_the_existing_network(self) -> None:
        self.assertTrue(hasattr(theatre, "STARTING_SUPPLY_RAILS"))
        source = theatre.RAILWAYS_PATH.read_text(encoding="utf-8")
        updated = theatre.update_source(source)
        for tag in ("STP", "YPR"):
            line = theatre.render_supply_connection(tag)
            self.assertEqual(updated.splitlines().count(line), 1)
        self.assertEqual(theatre.update_source(updated), updated)
        self.assertEqual(
            {line for line in source.splitlines() if line.strip()},
            {line for line in updated.splitlines() if line.strip()},
        )

    def test_missing_supply_link_is_reported(self) -> None:
        source = theatre.RAILWAYS_PATH.read_text(encoding="utf-8")
        for tag in ("STP", "YPR"):
            with self.subTest(tag=tag), tempfile.TemporaryDirectory() as directory:
                line = theatre.render_supply_connection(tag)
                broken = source.replace(line + "\n", "")
                self.assertNotEqual(broken, source)
                path = Path(directory) / "railways.txt"
                path.write_text(broken, encoding="utf-8")
                with patch.object(theatre, "RAILWAYS_PATH", path):
                    issues = theatre.validate()
                self.assertTrue(any(tag in issue and "disconnected" in issue for issue in issues), issues)

    def test_rail_apply_preserves_unchanged_supply_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            rails = Path(directory) / "railways.txt"
            hubs = Path(directory) / "supply_nodes.txt"
            rails.write_text(theatre.update_source("1 2 100 101\n"), encoding="utf-8")
            source = theatre.update_supply_source("1 100\n").replace("1 2539\n", "1 2539\r\n").encode("utf-8")
            hubs.write_bytes(source)
            with patch.object(theatre, "RAILWAYS_PATH", rails), patch.object(theatre, "SUPPLY_NODES_PATH", hubs):
                theatre.apply()
            self.assertEqual(hubs.read_bytes(), source)


if __name__ == "__main__":
    unittest.main()
