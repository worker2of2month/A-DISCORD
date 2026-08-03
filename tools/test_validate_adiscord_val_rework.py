import re
import unittest
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


def named_blocks(text: str, name: str) -> list[str]:
    masked = mask_comments(text)
    pattern = re.compile(rf"(?m)^\s*{re.escape(name)}\s*=\s*\{{")
    blocks = []
    for match in pattern.finditer(masked):
        opening = masked.index("{", match.start(), match.end())
        blocks.append(text[match.start() : closing_brace(masked, opening) + 1])
    return blocks


def only_named_block(test: unittest.TestCase, text: str, name: str) -> str:
    blocks = named_blocks(text, name)
    test.assertEqual(len(blocks), 1, f"expected exactly one brace-aware {name} block")
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

    def assert_authoritative_guard(self, effect: str, variable: str, tier: int) -> None:
        checks = named_blocks(effect, "check_variable")
        expected = re.compile(
            rf"\bvar\s*=\s*{re.escape(variable)}\b.*?\bvalue\s*=\s*{tier}\b"
            rf".*?\bcompare\s*=\s*less_than\b",
            re.DOTALL,
        )
        self.assertTrue(
            any(expected.search(mask_comments(check)) for check in checks),
            f"tier {tier} needs a {variable} less_than guard",
        )

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
            r"(?m)^\s*(VAL_apply_contract_[a-z]+_\d+)\s*=\s*\{", mask_comments(self.effects)
        )
        self.assertTrue(apply_effect_names, "expected VAL contract apply effects")
        for effect_name in apply_effect_names:
            with self.subTest(effect=effect_name):
                effect = only_named_block(self, self.effects, effect_name)
                used_tiers = set(
                    re.findall(
                        r"\bVAL_contract_(?:administration|industry|army|reputation)_\d+\b",
                        mask_comments(effect),
                    )
                )
                self.assertTrue(used_tiers, "each apply effect must name a contract tier")
                self.assertTrue(used_tiers <= declared, used_tiers - declared)

    def test_upward_apply_effects_rebuild_from_authoritative_levels(self) -> None:
        for family in UPWARD_FAMILIES:
            variable = LEVEL_VARIABLES[family]
            for tier, target in enumerate(FAMILIES[family], start=1):
                with self.subTest(family=family, tier=tier):
                    effect = self.effect(family, tier)
                    engine_effect = mask_comments(effect)
                    self.assertNotRegex(engine_effect, r"\bhas_idea\s*=")
                    self.assertNotRegex(engine_effect, r"\bswap_ideas\s*=")
                    successful = named_blocks(effect, "if")[0]
                    self.assertRegex(
                        successful,
                        rf"\bset_variable\s*=\s*\{{\s*var\s*=\s*{variable}\s+value\s*=\s*{tier}\s*\}}",
                    )
                    self.assert_hidden_rebuild(successful, family, target)
                    if tier < 3:
                        self.assert_authoritative_guard(effect, variable, tier)
                    if family in {"administration", "industry"}:
                        self.assertRegex(
                            successful,
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
                self.assertRegex(refresh, rf"\b{effect_name}\s*=\s*yes\b")

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
                    for branch_name in ("if", "else_if")
                    for branch in named_blocks(migration, branch_name)
                    if re.search(rf"\b{effect_name}\s*=\s*yes\b", mask_comments(branch))
                ]
                self.assertTrue(branches, f"migration needs a {effect_name} branch")
                tier_positions[tier] = min(migration.index(branch) for branch in branches)
                for focus_id in caller_focuses[(family, tier)]:
                    with self.subTest(family=family, tier=tier, focus=focus_id):
                        self.assertTrue(
                            any(
                                re.search(
                                    rf"\bhas_completed_focus\s*=\s*{re.escape(focus_id)}\b",
                                    mask_comments(branch),
                                )
                                for branch in branches
                            ),
                            f"{focus_id} is missing from the {effect_name} migration branch",
                        )
            with self.subTest(family=family, order="descending"):
                self.assertLess(tier_positions[3], tier_positions[2])
                self.assertLess(tier_positions[2], tier_positions[1])


if __name__ == "__main__":
    unittest.main()
