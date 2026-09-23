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
    def test_contract_check_count(self) -> None:
        self.assertEqual(len(run_checks()), SCORE_TOTAL)
        self.assertEqual(SCORE_TOTAL, 104)

    def test_live_contract(self) -> None:
        self.assertEqual(validate(), [])
        self.assertEqual(collect_issues(), [])
        self.assertEqual(score(), (104, 104))


if __name__ == "__main__":
    unittest.main()
