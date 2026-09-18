from __future__ import annotations

import unittest

from tools.validators.validate_adiscord_stp_shabrat_ai import (
    SCORE_TOTAL,
    collect_issues,
    run_checks,
    score,
    validate,
)


class ShabratAIContractTests(unittest.TestCase):
    def test_contract_defines_one_hundred_checks(self) -> None:
        self.assertEqual(len(run_checks()), SCORE_TOTAL)
        self.assertEqual(SCORE_TOTAL, 101)

    def test_live_contract(self) -> None:
        self.assertEqual(validate(), [])
        self.assertEqual(collect_issues(), [])
        self.assertEqual(score(), (101, 101))


if __name__ == "__main__":
    unittest.main()
