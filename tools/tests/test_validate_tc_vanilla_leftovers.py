"""Distinguish total-conversion references from ordinary words and unit labels."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.validators import validate_tc


class VanillaLeftoverTests(unittest.TestCase):
    def test_counts_script_and_localisation_references_in_context(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            units = root / "common/units/fixture.txt"
            units.parent.mkdir(parents=True)
            units.write_text(
                'abbreviation = "R-ENG" target = "ENG" # USA\n'
                'ruling_party = neutrality\n'
                'GER = { ideology = moderate }\n'
                'tag = ROM ideology = liberalism\n',
                encoding="utf-8",
            )
            loc = root / "localisation/fixture_l_english.yml"
            loc.parent.mkdir()
            loc.write_text(
                'l_english:\n'
                ' stance: "Armed neutrality, moderate costs and a quote about socialism."\n'
                ' neutrality: "Independent"\n'
                ' tooltip: "$socialism$ [USA.GetName] @GER $ENG_DEF$"\n'
                ' custom_diff_strong_usa: "Усилить страну"\n'
                ' label: "Strengthen §YUSA§!" # GER\n'
                ' local: "@ROM $liberalism$"\n',
                encoding="utf-8-sig",
            )
            with patch.object(validate_tc, "ROOT", root):
                counts, examples = validate_tc.scan_vanilla_leftovers({"ROM"}, {"liberalism"}, 1)

        self.assertEqual(counts, {
            "tag:ENG": 2, "tag:GER": 2, "tag:USA": 3,
            "ideology:neutrality": 2, "ideology:moderate": 1, "ideology:socialism": 1,
        })
        self.assertEqual(len(examples["tag:ENG"]), 1)
        self.assertIn("common/units/fixture.txt:1:", examples["tag:ENG"][0])
