import re
import unittest
from collections import Counter
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BUYERS = ("WRK", "STP", "NOD", "IVN", "WIT", "NAM")
AAT = '"Arms Against Tyranny"'


def mask_comments(text: str) -> str:
    """Mask Clausewitz comments while preserving every source offset."""
    result: list[str] = []
    in_string = False
    escaped = False
    in_comment = False
    for character in text:
        if in_comment:
            if character in "\r\n":
                in_comment = False
                result.append(character)
            else:
                result.append(" ")
        elif in_string:
            result.append(character)
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                in_string = False
        elif character == "#":
            in_comment = True
            result.append(" ")
        else:
            result.append(character)
            if character == '"':
                in_string = True
    return "".join(result)


def mask_non_code(text: str) -> str:
    """Mask comments and quoted strings while preserving every source offset."""
    result: list[str] = []
    in_string = False
    escaped = False
    in_comment = False
    for character in text:
        if in_comment:
            if character in "\r\n":
                in_comment = False
                result.append(character)
            else:
                result.append(" ")
        elif in_string:
            result.append(character if character in "\r\n" else " ")
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                in_string = False
        elif character == "#":
            in_comment = True
            result.append(" ")
        elif character == '"':
            in_string = True
            result.append(" ")
        else:
            result.append(character)
    return "".join(result)


def closing_brace(text: str, opening: int) -> int:
    depth = 0
    for index in range(opening, len(text)):
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
            if depth == 0:
                return index
            if depth < 0:
                raise ValueError(f"unexpected closing brace at {index}")
    raise ValueError(f"unclosed brace at {opening}")


def brace_depth_before(text: str, position: int) -> int:
    return text[:position].count("{") - text[:position].count("}")


@dataclass(frozen=True)
class Block:
    name: str
    start: int
    end: int
    text: str


def named_block_spans(text: str, name: str, offset: int = 0) -> list[Block]:
    masked = mask_non_code(text)
    pattern = re.compile(rf"(?<![A-Za-z0-9_]){re.escape(name)}\s*=\s*\{{")
    blocks: list[Block] = []
    for match in pattern.finditer(masked):
        opening = masked.index("{", match.start(), match.end())
        closing = closing_brace(masked, opening) + 1
        blocks.append(Block(name, offset + match.start(), offset + closing, text[match.start():closing]))
    return blocks


def direct_named_blocks(text: str, name: str, offset: int = 0) -> list[Block]:
    masked = mask_non_code(text)
    return [
        block
        for block in named_block_spans(text, name, offset)
        if brace_depth_before(masked, block.start - offset) == 1
    ]


def top_level_named_blocks(text: str, name: str) -> list[Block]:
    masked = mask_non_code(text)
    return [
        block
        for block in named_block_spans(text, name)
        if brace_depth_before(masked, block.start) == 0
    ]


def only_top_level_block(text: str, name: str) -> Block:
    blocks = top_level_named_blocks(text, name)
    if len(blocks) != 1:
        raise AssertionError(f"expected exactly one top-level {name} block, got {len(blocks)}")
    return blocks[0]


def only_direct_block(parent: Block, name: str) -> Block:
    blocks = direct_named_blocks(parent.text, name, parent.start)
    if len(blocks) != 1:
        raise AssertionError(f"{parent.name} needs exactly one direct {name} block, got {len(blocks)}")
    return blocks[0]


def direct_scalar_assignments(block: Block) -> list[tuple[str, str]]:
    comment_masked = mask_comments(block.text)
    structure_masked = mask_non_code(block.text)
    scalar = re.compile(
        r'(?<![A-Za-z0-9_])([A-Za-z0-9_]+)\s*=\s*'
        r'("(?:[^"\\]|\\.)*"|[A-Za-z0-9_]+)(?![A-Za-z0-9_])'
    )
    return [
        (match.group(1), match.group(2))
        for match in scalar.finditer(comment_masked)
        if structure_masked[match.start() : match.start() + len(match.group(1))]
        == match.group(1)
        and brace_depth_before(structure_masked, match.start()) == 1
    ]


def require_direct_scalar(block: Block, key: str, value: str) -> None:
    actual = [operand for operand_key, operand in direct_scalar_assignments(block) if operand_key == key]
    if actual != [value]:
        raise AssertionError(
            f"{block.name} needs exactly one direct {key} = {value}, got {actual}"
        )


def validate_relationship(
    text: str,
    name: str,
    original_tag: str,
    other_tag: str,
    strategies: tuple[dict[str, str], ...],
) -> None:
    relationship = only_top_level_block(text, name)
    allowed = only_direct_block(relationship, "allowed")
    enable = only_direct_block(relationship, "enable")
    require_direct_scalar(allowed, "original_tag", original_tag)
    require_direct_scalar(allowed, "has_dlc", AAT)
    require_direct_scalar(enable, "country_exists", other_tag)

    war_guards = direct_named_blocks(enable.text, "NOT", enable.start)
    if len(war_guards) != 1:
        raise AssertionError(f"{name} needs exactly one direct NOT war guard, got {len(war_guards)}")
    require_direct_scalar(war_guards[0], "has_war_with", other_tag)
    require_direct_scalar(relationship, "abort_when_not_enabled", "yes")

    direct_strategies = direct_named_blocks(relationship.text, "ai_strategy", relationship.start)
    if len(direct_strategies) != len(strategies):
        raise AssertionError(
            f"{name} needs {len(strategies)} direct ai_strategy blocks, got {len(direct_strategies)}"
        )
    actual = Counter(
        tuple(sorted(direct_scalar_assignments(strategy))) for strategy in direct_strategies
    )
    expected = Counter(tuple(sorted(strategy.items())) for strategy in strategies)
    if actual != expected:
        raise AssertionError(f"{name} direct ai strategies {actual} do not equal {expected}")


def validate_export_relationships(text: str) -> None:
    for buyer in BUYERS:
        validate_relationship(
            text,
            f"ADISCORD_VAL_export_buyer_{buyer}",
            buyer,
            "VAL",
            (
                {
                    "type": "diplo_action_desire",
                    "id": "VAL",
                    "target": "market_access_rights",
                    "value": "150",
                },
                {
                    "type": "equipment_market_trade_desire",
                    "id": "VAL",
                    "value": "100",
                },
            ),
        )
        validate_relationship(
            text,
            f"ADISCORD_VAL_export_accept_{buyer}",
            "VAL",
            buyer,
            (
                {
                    "type": "diplo_action_acceptance",
                    "id": buyer,
                    "target": "market_access_rights",
                    "value": "200",
                },
            ),
        )


def top_level_prefixed_tags(text: str, prefix: str) -> set[str]:
    masked = mask_non_code(text)
    pattern = re.compile(rf"(?m)^\s*{re.escape(prefix)}([A-Z]{{3}})\s*=\s*\{{")
    return {
        match.group(1)
        for match in pattern.finditer(masked)
        if brace_depth_before(masked, match.start()) == 0
    }


class ValExportMarketTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.ai_text = (ROOT / "common" / "ai_strategy" / "VAL.txt").read_text(
            encoding="utf-8-sig"
        )

    def replace_relationship(self, text: str, name: str, replacement: str) -> str:
        relationship = only_top_level_block(text, name)
        return text[:relationship.start] + replacement + text[relationship.end:]

    def test_buyers_prefer_val_market_access(self) -> None:
        for buyer in BUYERS:
            with self.subTest(buyer=buyer):
                validate_relationship(
                    self.ai_text,
                    f"ADISCORD_VAL_export_buyer_{buyer}",
                    buyer,
                    "VAL",
                    (
                        {
                            "type": "diplo_action_desire",
                            "id": "VAL",
                            "target": "market_access_rights",
                            "value": "150",
                        },
                        {
                            "type": "equipment_market_trade_desire",
                            "id": "VAL",
                            "value": "100",
                        },
                    ),
                )

    def test_val_accepts_each_buyers_market_access_request(self) -> None:
        for buyer in BUYERS:
            with self.subTest(buyer=buyer):
                validate_relationship(
                    self.ai_text,
                    f"ADISCORD_VAL_export_accept_{buyer}",
                    "VAL",
                    buyer,
                    (
                        {
                            "type": "diplo_action_acceptance",
                            "id": buyer,
                            "target": "market_access_rights",
                            "value": "200",
                        },
                    ),
                )

    def test_export_block_prefixes_cover_exactly_the_supported_buyers(self) -> None:
        self.assertEqual(
            top_level_prefixed_tags(self.ai_text, "ADISCORD_VAL_export_buyer_"), set(BUYERS)
        )
        self.assertEqual(
            top_level_prefixed_tags(self.ai_text, "ADISCORD_VAL_export_accept_"), set(BUYERS)
        )

    def test_val_market_layer_only_lists_equipment_for_sale(self) -> None:
        market_layer = only_top_level_block(self.ai_text, "VAL_Wants_To_Sell_Stuff")
        strategy_types = {
            value
            for strategy in direct_named_blocks(market_layer.text, "ai_strategy", market_layer.start)
            for key, value in direct_scalar_assignments(strategy)
            if key == "type"
        }
        self.assertEqual(strategy_types, {"equipment_market_for_sale_factor"})
        code = mask_non_code(self.ai_text)
        self.assertNotIn("give_market_access", code)
        self.assertNotRegex(code, r"(?i)\bon_[A-Za-z0-9_]*market[A-Za-z0-9_]*\b")

    def test_checker_rejects_commented_aat_gates(self) -> None:
        mutated = re.sub(
            r'(?m)^(\s*)(has_dlc = "Arms Against Tyranny")\s*$',
            r"\1# \2",
            self.ai_text,
        )
        with self.assertRaises(AssertionError):
            validate_export_relationships(mutated)

    def test_checker_rejects_war_guard_misplaced_outside_enable(self) -> None:
        name = "ADISCORD_VAL_export_buyer_WRK"
        relationship = only_top_level_block(self.ai_text, name)
        moved = relationship.text.replace(
            "\t\tNOT = { has_war_with = VAL }\n\t}\n\tabort_when_not_enabled = yes",
            "\t}\n\tNOT = { has_war_with = VAL }\n\tabort_when_not_enabled = yes",
            1,
        )
        self.assertNotEqual(moved, relationship.text, "war-guard mutation must apply")
        with self.assertRaises(AssertionError):
            validate_relationship(
                self.replace_relationship(self.ai_text, name, moved),
                name,
                "WRK",
                "VAL",
                (
                    {
                        "type": "diplo_action_desire",
                        "id": "VAL",
                        "target": "market_access_rights",
                        "value": "150",
                    },
                    {"type": "equipment_market_trade_desire", "id": "VAL", "value": "100"},
                ),
            )

    def test_checker_rejects_strategy_misplaced_inside_enable(self) -> None:
        name = "ADISCORD_VAL_export_buyer_WRK"
        relationship = only_top_level_block(self.ai_text, name)
        desire = (
            "\tai_strategy = {\n"
            "\t\ttype = diplo_action_desire\n"
            "\t\tid = VAL\n"
            "\t\ttarget = market_access_rights\n"
            "\t\tvalue = 150\n"
            "\t}\n"
        )
        nested_desire = "".join(f"\t{line}\n" for line in desire.rstrip().splitlines())
        moved = relationship.text.replace(desire, "", 1).replace(
            "\tenable = {\n", "\tenable = {\n" + nested_desire, 1
        )
        self.assertNotEqual(moved, relationship.text, "strategy mutation must apply")
        with self.assertRaises(AssertionError):
            validate_relationship(
                self.replace_relationship(self.ai_text, name, moved),
                name,
                "WRK",
                "VAL",
                (
                    {
                        "type": "diplo_action_desire",
                        "id": "VAL",
                        "target": "market_access_rights",
                        "value": "150",
                    },
                    {"type": "equipment_market_trade_desire", "id": "VAL", "value": "100"},
                ),
            )


if __name__ == "__main__":
    unittest.main()
