import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BUYERS = ("WRK", "STP", "NOD", "IVN", "WIT", "NAM")


def named_blocks(text: str, key: str) -> list[str]:
    blocks: list[str] = []
    for match in re.finditer(rf"(?m)^\s*{re.escape(key)}\s*=\s*\{{", text):
        depth = 0
        start = match.start()
        in_string = False
        escaped = False
        for index in range(match.end() - 1, len(text)):
            char = text[index]
            if in_string:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    in_string = False
                continue
            if char == '"':
                in_string = True
            elif char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    blocks.append(text[start : index + 1])
                    break
    return blocks


class ValExportMarketTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ai_text = (ROOT / "common" / "ai_strategy" / "VAL.txt").read_text(
            encoding="utf-8-sig"
        )

    def only_block(self, key: str) -> str:
        blocks = named_blocks(self.ai_text, key)
        self.assertEqual(len(blocks), 1, f"expected exactly one {key} block")
        return blocks[0]

    def assert_ai_strategy(self, block: str, **expected: str) -> None:
        matches = []
        for strategy in named_blocks(block, "ai_strategy"):
            if all(
                re.search(
                    rf"(?m)^\s*{re.escape(key)}\s*=\s*{re.escape(value)}\s*$",
                    strategy,
                )
                for key, value in expected.items()
            ):
                matches.append(strategy)
        self.assertEqual(len(matches), 1, expected)

    def test_buyers_prefer_val_market_access(self):
        for buyer in BUYERS:
            with self.subTest(buyer=buyer):
                buyer_block = self.only_block(f"ADISCORD_VAL_export_buyer_{buyer}")
                self.assertIn(f"original_tag = {buyer}", buyer_block)
                self.assertIn('has_dlc = "Arms Against Tyranny"', buyer_block)
                self.assertIn("country_exists = VAL", buyer_block)
                self.assertRegex(buyer_block, r"NOT\s*=\s*\{\s*has_war_with\s*=\s*VAL\s*\}")
                self.assertIn("abort_when_not_enabled = yes", buyer_block)
                self.assert_ai_strategy(
                    buyer_block,
                    type="diplo_action_desire",
                    id="VAL",
                    target="market_access_rights",
                    value="150",
                )
                self.assert_ai_strategy(
                    buyer_block,
                    type="equipment_market_trade_desire",
                    id="VAL",
                    value="100",
                )

    def test_val_accepts_each_buyers_market_access_request(self):
        for buyer in BUYERS:
            with self.subTest(buyer=buyer):
                accept_block = self.only_block(f"ADISCORD_VAL_export_accept_{buyer}")
                self.assertIn("original_tag = VAL", accept_block)
                self.assertIn('has_dlc = "Arms Against Tyranny"', accept_block)
                self.assertIn(f"country_exists = {buyer}", accept_block)
                self.assertRegex(
                    accept_block,
                    rf"NOT\s*=\s*\{{\s*has_war_with\s*=\s*{buyer}\s*\}}",
                )
                self.assertIn("abort_when_not_enabled = yes", accept_block)
                self.assert_ai_strategy(
                    accept_block,
                    type="diplo_action_acceptance",
                    id=buyer,
                    target="market_access_rights",
                    value="200",
                )

    def test_export_block_prefixes_cover_exactly_the_supported_buyers(self):
        buyer_tags = set(
            re.findall(
                r"(?m)^\s*ADISCORD_VAL_export_buyer_([A-Z]{3})\s*=\s*\{",
                self.ai_text,
            )
        )
        accept_tags = set(
            re.findall(
                r"(?m)^\s*ADISCORD_VAL_export_accept_([A-Z]{3})\s*=\s*\{",
                self.ai_text,
            )
        )
        with self.subTest(layer="buyer"):
            self.assertEqual(buyer_tags, set(BUYERS))
        with self.subTest(layer="accept"):
            self.assertEqual(accept_tags, set(BUYERS))

    def test_val_market_layer_only_lists_equipment_for_sale(self):
        market_layer = self.only_block("VAL_Wants_To_Sell_Stuff")
        strategy_types = {
            match.group(1)
            for strategy in named_blocks(market_layer, "ai_strategy")
            for match in re.finditer(r"(?m)^\s*type\s*=\s*([^\s#]+)", strategy)
        }
        self.assertEqual(strategy_types, {"equipment_market_for_sale_factor"})
        self.assertNotIn("give_market_access", self.ai_text)
        self.assertNotRegex(self.ai_text, r"(?i)\bon_[A-Za-z0-9_]*market[A-Za-z0-9_]*\b")


if __name__ == "__main__":
    unittest.main()
