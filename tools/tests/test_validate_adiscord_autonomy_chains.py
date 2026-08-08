import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

from tools.validators import validate_tc


class AutonomyChainTests(unittest.TestCase):
    def test_every_subject_type_stays_in_its_own_progression(self):
        issues, total = validate_tc.check_autonomy_chains(300)
        self.assertEqual(total, 0, "\n".join(issues))


if __name__ == "__main__":
    unittest.main()
