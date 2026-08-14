from __future__ import annotations

import unittest

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


if __name__ == "__main__":
    unittest.main()
