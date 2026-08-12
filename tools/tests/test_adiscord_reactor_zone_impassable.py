from __future__ import annotations

import unittest

from tools.builders import build_adiscord_new_states as builder


class ReactorZoneImpassableContract(unittest.TestCase):
    def test_reactor_zone_remains_impassable_after_legacy_regeneration(self) -> None:
        self.assertIn(125, builder.IMPASSABLE_LEGACY_STATE_IDS)
        source = builder.state_path(125).read_text(encoding="utf-8-sig", errors="strict")
        self.assertIn("impassable = yes", source)


if __name__ == "__main__":
    unittest.main()
