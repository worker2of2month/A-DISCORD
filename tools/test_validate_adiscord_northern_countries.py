import unittest

from tools.validate_adiscord_northern_countries import validate


class NorthernCountryContractsTest(unittest.TestCase):
    def test_northern_country_contract(self):
        self.assertEqual([], validate())


if __name__ == "__main__":
    unittest.main()
