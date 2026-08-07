import unittest

from tools.validate_adiscord_exclusion_zone_boundaries import validate


class ExclusionZoneBoundaryContractsTest(unittest.TestCase):
    def test_exclusion_zone_boundary_contract(self):
        self.assertEqual([], validate())


if __name__ == "__main__":
    unittest.main()
