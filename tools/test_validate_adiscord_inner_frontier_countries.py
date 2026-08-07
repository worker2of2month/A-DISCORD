import unittest

from tools.validate_adiscord_inner_frontier_countries import validate


class InnerFrontierCountryContractsTest(unittest.TestCase):
    def test_inner_frontier_country_contract(self):
        self.assertEqual([], validate())


if __name__ == "__main__":
    unittest.main()
