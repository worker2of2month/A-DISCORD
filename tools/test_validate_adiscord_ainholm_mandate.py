from __future__ import annotations

import unittest

from tools.validate_adiscord_ainholm_mandate import validate


class AinholmMandateContractTests(unittest.TestCase):
    def test_live_contract(self) -> None:
        self.assertEqual(validate(), [])


if __name__ == "__main__":
    unittest.main()
