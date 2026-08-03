import re
import unittest
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EFFECTS_PATH = ROOT / "common" / "scripted_effects" / "ADISCORD_VAL_rework_effects.txt"
IDEAS_PATH = ROOT / "common" / "ideas" / "ADISCORD_VAL_rework_ideas.txt"
FOCUSES_PATH = ROOT / "common" / "national_focus" / "ADISCORD_national_focus_VAL.txt"

FAMILIES = {
    "administration": tuple(f"VAL_contract_administration_{n}" for n in range(1, 4)),
    "industry": tuple(f"VAL_contract_industry_{n}" for n in range(1, 4)),
    "army": tuple(f"VAL_contract_army_{n}" for n in range(1, 4)),
    "reputation": tuple(f"VAL_contract_reputation_{n}" for n in range(4)),
}

UPWARD_FAMILIES = ("administration", "industry", "army")
LEVEL_VARIABLES = {
    "administration": "VAL_contract_administration_level",
    "industry": "VAL_contract_industry_level",
    "army": "VAL_contract_army_level",
}


def mask_comments(text: str) -> str:
    """Replace comments with spaces without changing brace and line positions."""
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
            continue
        if in_string:
            result.append(character)
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                in_string = False
            continue
        if character == "#":
            in_comment = True
            result.append(" ")
        else:
            result.append(character)
            if character == '"':
                in_string = True
    return "".join(result)


def mask_non_code(text: str) -> str:
    """Mask comments and quoted strings while keeping all source offsets stable."""
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
            continue
        if in_string:
            result.append(" " if character not in "\r\n" else character)
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                in_string = False
            continue
        if character == "#":
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
    in_string = False
    escaped = False
    for index in range(opening, len(text)):
        character = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                in_string = False
            continue
        if character == '"':
            in_string = True
        elif character == "{":
            depth += 1
        elif character == "}":
            depth -= 1
            if depth == 0:
                return index
            if depth < 0:
                raise ValueError(f"unexpected closing brace at index {index}")
    raise ValueError(f"unclosed brace at index {opening}")


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
        blocks.append(
            Block(
                name=name,
                start=offset + match.start(),
                end=offset + closing,
                text=text[match.start() : closing],
            )
        )
    return blocks


def brace_depth_before(text: str, position: int) -> int:
    depth = 0
    in_string = False
    escaped = False
    for character in text[:position]:
        if in_string:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                in_string = False
            continue
        if character == '"':
            in_string = True
        elif character == "{":
            depth += 1
        elif character == "}":
            depth -= 1
    return depth


def direct_named_blocks(text: str, name: str, offset: int = 0) -> list[Block]:
    masked = mask_non_code(text)
    return [
        block
        for block in named_block_spans(text, name, offset)
        if brace_depth_before(masked, block.start - offset) == 1
    ]


def named_blocks(text: str, name: str) -> list[str]:
    return [block.text for block in named_block_spans(text, name)]


def only_named_block(test: unittest.TestCase, text: str, name: str) -> str:
    blocks = named_blocks(text, name)
    test.assertEqual(len(blocks), 1, f"expected exactly one brace-aware {name} block")
    return blocks[0]


def only_direct_named_block(
    test: unittest.TestCase, text: str, name: str, offset: int = 0
) -> Block:
    blocks = direct_named_blocks(text, name, offset)
    test.assertEqual(len(blocks), 1, f"expected exactly one direct {name} block")
    return blocks[0]


def direct_values(text: str, key: str) -> list[str]:
    return re.findall(
        rf"(?m)^\s*{re.escape(key)}\s*=\s*([A-Za-z0-9_]+)\s*(?:#.*)?$",
        mask_comments(text),
    )


class ValTierTransitionContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.effects = EFFECTS_PATH.read_text(encoding="utf-8-sig")
        cls.ideas = IDEAS_PATH.read_text(encoding="utf-8-sig")
        cls.focuses = FOCUSES_PATH.read_text(encoding="utf-8-sig")

    def effect(self, family: str, tier: int) -> str:
        return only_named_block(self, self.effects, f"VAL_apply_contract_{family}_{tier}")

    def assert_hidden_rebuild(self, effect: str, family: str, target: str) -> None:
        hidden = only_named_block(self, effect, "hidden_effect")
        family_ids = set(FAMILIES[family])
        removals = set(direct_values(hidden, "remove_idea")) | set(
            direct_values(hidden, "remove_ideas")
        )
        additions = direct_values(hidden, "add_idea") + direct_values(hidden, "add_ideas")
        self.assertEqual(removals & family_ids, family_ids)
        self.assertEqual(additions, [target])

        removal_positions = [
            match.start()
            for idea in family_ids
            for key in ("remove_idea", "remove_ideas")
            for match in re.finditer(
                rf"(?m)^\s*{key}\s*=\s*{re.escape(idea)}\s*$", mask_comments(hidden)
            )
        ]
        addition_positions = [
            match.start()
            for key in ("add_idea", "add_ideas")
            for match in re.finditer(
                rf"(?m)^\s*{key}\s*=\s*{re.escape(target)}\s*$", mask_comments(hidden)
            )
        ]
        self.assertTrue(removal_positions, "tier rebuild must remove every family idea")
        self.assertTrue(addition_positions, "tier rebuild must add its target idea")
        self.assertLess(max(removal_positions), min(addition_positions))

    def transition_branch(self, effect: str, variable: str, tier: int) -> Block:
        branches = [
            branch
            for branch in direct_named_blocks(effect, "if")
            if len(self.direct_level_setters(branch, variable, tier)) == 1
            and len(direct_named_blocks(branch.text, "limit", branch.start)) == 1
            and len(direct_named_blocks(branch.text, "hidden_effect", branch.start)) == 1
        ]
        self.assertEqual(
            len(branches),
            1,
            f"expected one if branch that sets {variable} to tier {tier} and rebuilds hidden ideas",
        )
        return branches[0]

    def direct_level_setters(self, branch: Block, variable: str, tier: int) -> list[Block]:
        expected = re.compile(
            rf"\bvar\s*=\s*{re.escape(variable)}\b.*?\bvalue\s*=\s*{tier}\b",
            re.DOTALL,
        )
        return [
            setter
            for setter in direct_named_blocks(branch.text, "set_variable", branch.start)
            if expected.search(mask_comments(setter.text))
        ]

    def contract_tier_operands(self, effect: str) -> set[str]:
        operands = set(
            re.findall(
                r"\b(?:add_ideas?|remove_ideas?)\s*=\s*"
                r"(VAL_contract_[A-Za-z0-9_]+)\b",
                mask_comments(effect),
            )
        )
        operands.update(
            re.findall(
                r"\bswap_ideas\s*=\s*(VAL_contract_[A-Za-z0-9_]+)\b",
                mask_comments(effect),
            )
        )
        for swap in named_blocks(effect, "swap_ideas"):
            operands.update(
                re.findall(r"\bVAL_contract_[A-Za-z0-9_]+\b", mask_comments(swap))
            )
        return operands

    def assert_authoritative_guard(self, branch: Block, variable: str, tier: int) -> None:
        limit = only_direct_named_block(self, branch.text, "limit", branch.start)
        checks = named_blocks(limit.text, "check_variable")
        expected = re.compile(
            rf"\bvar\s*=\s*{re.escape(variable)}\b.*?\bvalue\s*=\s*{tier}\b"
            rf".*?\bcompare\s*=\s*less_than\b",
            re.DOTALL,
        )
        self.assertTrue(
            any(expected.search(mask_comments(check)) for check in checks),
            f"tier {tier} needs a {variable} less_than guard",
        )

    def renderer_calls(self, block: str) -> list[int]:
        return [
            int(tier)
            for tier in re.findall(
                r"\bVAL_apply_contract_reputation_([0-3])\s*=\s*yes\b",
                mask_comments(block),
            )
        ]

    def assert_reputation_refresh_selection(self, refresh: str) -> None:
        conditional_branches = sorted(
            [
                *direct_named_blocks(refresh, "if"),
                *direct_named_blocks(refresh, "else_if"),
            ],
            key=lambda branch: branch.start,
        )
        self.assertEqual(
            [branch.name for branch in conditional_branches],
            ["if", "else_if", "else_if"],
        )
        for tier, branch in zip((3, 2, 1), conditional_branches):
            with self.subTest(refresh_tier=tier):
                limit = only_direct_named_block(self, branch.text, "limit", branch.start)
                checks = named_blocks(limit.text, "check_variable")
                self.assertEqual(len(checks), 1, "each reputation branch needs one level check")
                self.assertRegex(
                    mask_comments(checks[0]),
                    rf"\bvar\s*=\s*VAL_contract_reputation_level\b.*?\bvalue\s*=\s*{tier}\b"
                    r".*?\bcompare\s*=\s*greater_than_or_equals\b",
                )
                self.assertEqual(self.renderer_calls(branch.text), [tier])

        fallback = only_direct_named_block(self, refresh, "else")
        self.assertGreater(fallback.start, conditional_branches[-1].start)
        self.assertEqual(self.renderer_calls(fallback.text), [0])
        self.assertEqual(named_blocks(fallback.text, "check_variable"), [])

    def test_sources_have_balanced_clausewitz_blocks(self) -> None:
        for path, text in (
            (EFFECTS_PATH, self.effects),
            (IDEAS_PATH, self.ideas),
            (FOCUSES_PATH, self.focuses),
        ):
            with self.subTest(path=path):
                masked = mask_comments(text)
                depth = 0
                for index, character in enumerate(masked):
                    if character == "{":
                        depth += 1
                    elif character == "}":
                        depth -= 1
                        self.assertGreaterEqual(depth, 0, f"unexpected closing brace at {index}")
                self.assertEqual(depth, 0, "unclosed Clausewitz block")

    def test_each_contract_tier_is_declared_once_and_apply_effects_use_only_it(self) -> None:
        hidden_ideas = only_named_block(self, self.ideas, "hidden_ideas")
        declared = set().union(*map(set, FAMILIES.values()))
        for family in FAMILIES.values():
            for idea in family:
                with self.subTest(idea=idea):
                    self.assertEqual(len(named_blocks(hidden_ideas, idea)), 1)

        apply_effect_names = re.findall(
            r"(?m)^\s*(VAL_apply_contract_[A-Za-z0-9_]+)\s*=\s*\{",
            mask_comments(self.effects),
        )
        self.assertTrue(apply_effect_names, "expected VAL contract apply effects")
        referenced_tiers: set[str] = set()
        for effect_name in apply_effect_names:
            with self.subTest(effect=effect_name):
                effect = only_named_block(self, self.effects, effect_name)
                used_tiers = self.contract_tier_operands(effect)
                referenced_tiers.update(used_tiers)
                self.assertTrue(used_tiers <= declared, used_tiers - declared)
        self.assertTrue(referenced_tiers, "expected tier ideas in VAL apply effects")

    def test_upward_apply_effects_rebuild_from_authoritative_levels(self) -> None:
        for family in UPWARD_FAMILIES:
            variable = LEVEL_VARIABLES[family]
            for tier, target in enumerate(FAMILIES[family], start=1):
                with self.subTest(family=family, tier=tier):
                    effect = self.effect(family, tier)
                    engine_effect = mask_comments(effect)
                    self.assertNotRegex(engine_effect, r"\bhas_idea\s*=")
                    self.assertNotRegex(engine_effect, r"\bswap_ideas\s*=")
                    successful = self.transition_branch(effect, variable, tier)
                    self.assert_hidden_rebuild(successful.text, family, target)
                    if tier < 3:
                        self.assert_authoritative_guard(successful, variable, tier)
                    if family in {"administration", "industry"}:
                        self.assertRegex(
                            successful.text,
                            r"\bADISCORD_economy_mark_dirty\s*=\s*yes\b",
                        )

    def test_reputation_apply_effects_rebuild_selected_authoritative_tier(self) -> None:
        refresh = only_named_block(self, self.effects, "VAL_refresh_contract_reputation")
        for tier, target in enumerate(FAMILIES["reputation"]):
            with self.subTest(tier=tier):
                effect_name = f"VAL_apply_contract_reputation_{tier}"
                effect = only_named_block(self, self.effects, effect_name)
                engine_effect = mask_comments(effect)
                self.assertNotRegex(engine_effect, r"\bhas_idea\s*=")
                self.assertNotRegex(engine_effect, r"\bswap_ideas\s*=")
                self.assert_hidden_rebuild(effect, "reputation", target)
        self.assert_reputation_refresh_selection(refresh)

    def test_old_save_migration_replays_every_completed_tier_focus_in_descending_order(self) -> None:
        caller_focuses: dict[tuple[str, int], set[str]] = {
            (family, tier): set()
            for family in UPWARD_FAMILIES
            for tier in range(1, 4)
        }
        for focus in named_blocks(self.focuses, "focus"):
            focus_id = direct_values(focus, "id")
            self.assertEqual(len(focus_id), 1, "focus needs exactly one id")
            reward = only_named_block(self, focus, "completion_reward")
            for family in UPWARD_FAMILIES:
                for tier in range(1, 4):
                    effect_name = f"VAL_apply_contract_{family}_{tier}"
                    if re.search(rf"\b{effect_name}\s*=\s*yes\b", mask_comments(reward)):
                        caller_focuses[(family, tier)].add(focus_id[0])

        for family, tier in caller_focuses:
            self.assertTrue(
                caller_focuses[(family, tier)],
                f"expected a focus caller for VAL_apply_contract_{family}_{tier}",
            )

        migration = only_named_block(self, self.effects, "VAL_migrate_contract_tier_levels")
        initialize = only_named_block(self, self.effects, "VAL_initialize_rework")
        self.assertRegex(
            mask_comments(initialize), r"\bVAL_migrate_contract_tier_levels\s*=\s*yes\b"
        )

        for family in UPWARD_FAMILIES:
            tier_positions: dict[int, int] = {}
            for tier in (1, 2, 3):
                effect_name = f"VAL_apply_contract_{family}_{tier}"
                branches = [
                    branch
                    for branch in [
                        *named_block_spans(migration, "if"),
                        *named_block_spans(migration, "else_if"),
                    ]
                    if re.search(
                        rf"\b{effect_name}\s*=\s*yes\b", mask_comments(branch.text)
                    )
                ]
                owning_branches = [
                    branch
                    for branch in branches
                    if not any(
                        nested.start > branch.start and nested.end < branch.end
                        for nested in branches
                    )
                ]
                self.assertEqual(
                    len(owning_branches),
                    1,
                    f"migration needs one owning {effect_name} branch",
                )
                branch = owning_branches[0]
                tier_positions[tier] = branch.start
                limit = only_direct_named_block(self, branch.text, "limit", branch.start)
                for focus_id in caller_focuses[(family, tier)]:
                    with self.subTest(family=family, tier=tier, focus=focus_id):
                        self.assertRegex(
                            mask_comments(limit.text),
                            rf"\bhas_completed_focus\s*=\s*{re.escape(focus_id)}\b",
                            f"{focus_id} is missing from the {effect_name} migration branch limit",
                        )
            with self.subTest(family=family, order="descending"):
                self.assertLess(tier_positions[3], tier_positions[2])
                self.assertLess(tier_positions[2], tier_positions[1])


if __name__ == "__main__":
    unittest.main()
