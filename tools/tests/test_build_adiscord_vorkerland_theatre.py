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

    def test_khan_campaign_spines_are_level_two_and_idempotent(self) -> None:
        source = theatre.RAILWAYS_PATH.read_text(encoding="utf-8")
        updated = theatre.update_source(source)
        self.assertEqual(theatre.update_source(updated), updated)
        for level, route in theatre.KHAN_CAMPAIGN_RAIL_UPGRADES:
            self.assertEqual(level, 2)
            self.assertEqual(
                updated.splitlines().count(theatre.render_khan_campaign_rail(level, route)),
                1,
            )

    def test_dirty_zone_has_multiple_managed_supply_hubs_per_campaign_belt(self) -> None:
        belt_states = (
            {49, 50, 51, 155, 176, 187, 191, 233, 329, 461},
            {125, 177, 186, 188, 192, 208, 213, 214, 215, 216, 217, 220},
            {152, 153, 154, 189, 190, 219, 221, 222, 224},
            {167, 168, 169, 170, 171, 184, 185, 203},
            {178, 180, 181, 182, 183, 193, 206, 207, 330},
            {165, 166, 172, 173, 204, 205, 209, 210, 211, 212},
        )
        hubs_by_state = theatre.VORKERLAND_SUPPLY_HUB_STATES
        for states in belt_states:
            self.assertGreaterEqual(
                sum(state in states for state in hubs_by_state.values()),
                2,
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

    def test_missing_khan_link_disconnects_the_border_hub(self) -> None:
        source = theatre.RAILWAYS_PATH.read_text(encoding="utf-8")
        broken = source.replace(theatre.render_khan_connection() + "\n", "")
        self.assertNotEqual(broken, source)
        with tempfile.TemporaryDirectory() as directory:
            rails = Path(directory) / "railways.txt"
            rails.write_text(broken, encoding="utf-8")
            with patch.object(theatre, "RAILWAYS_PATH", rails):
                issues = theatre.validate()
        self.assertTrue(any("RUS" in issue and "7445 is disconnected" in issue for issue in issues), issues)


if __name__ == "__main__":
    unittest.main()
