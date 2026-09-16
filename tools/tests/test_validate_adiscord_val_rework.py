import re
from itertools import permutations
import unittest
from dataclasses import dataclass
from pathlib import Path


from tools.lib.paths import source_section


ROOT = Path(__file__).resolve().parents[2]
EFFECTS_PATH = ROOT / "common" / "scripted_effects" / "ADISCORD_VAL_effects.txt"
IDEAS_PATH = ROOT / "common" / "ideas" / "ADISCORD_VAL_rework_ideas.txt"
FOCUSES_PATH = ROOT / "common" / "national_focus" / "ADISCORD_national_focus_VAL.txt"
ON_ACTIONS_PATH = ROOT / "common" / "on_actions" / "02_ADISCORD_VAL_rework_on_actions.txt"
FOREIGN_EFFECTS_PATH = (
    ROOT / "common" / "scripted_effects" / "ADISCORD_VAL_effects.txt"
)
DECISIONS_PATH = ROOT / "common" / "decisions" / "ADISCORD_VAL_decisions.txt"
LOCALISATION_PATH = ROOT / "localisation" / "russian" / "ADISCORD_VAL_decisions_l_russian.yml"
LEGACY_DECISIONS_PATH = ROOT / "common" / "decisions" / "ADISCORD_VAL_rework_decisions.txt"
LEGACY_LOCALISATION_PATH = (
    ROOT / "localisation" / "russian" / "ADISCORD_VAL_rework_l_russian.yml"
)

FAMILIES = {
    "administration": tuple(f"VAL_contract_administration_{n}" for n in range(1, 4)),
    "industry": tuple(f"VAL_contract_industry_{n}" for n in range(1, 4)),
    "army": tuple(f"VAL_contract_army_{n}" for n in range(1, 4)),
    "reputation": tuple(f"VAL_contract_reputation_{n}" for n in range(4)),
}

UPWARD_FAMILIES = ("administration", "industry", "army")
FRESH_CAMPAIGN_FLAG = "ADISCORD_fresh_campaign_contract_v1"
VAL_FRESH_FEATURE_FLAG = "ADISCORD_val_rework_fresh_campaign_v1"
TIER_MIGRATION_EFFECT = "VAL_migrate_contract_tier_levels"
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
        cls.effects = source_section(EFFECTS_PATH.read_text(encoding="utf-8-sig"), 'rework_effects')
        cls.ideas = IDEAS_PATH.read_text(encoding="utf-8-sig")
        cls.focuses = FOCUSES_PATH.read_text(encoding="utf-8-sig")
        cls.on_actions = ON_ACTIONS_PATH.read_text(encoding="utf-8-sig")
        cls.foreign_effects = source_section(FOREIGN_EFFECTS_PATH.read_text(encoding="utf-8-sig"), 'foreign_operation_effects')

    def effect(self, family: str, tier: int) -> str:
        return only_named_block(self, self.effects, f"VAL_apply_contract_{family}_{tier}")

    def test_decision_files_use_canonical_tag_names(self) -> None:
        self.assertTrue(DECISIONS_PATH.is_file())
        self.assertTrue(LOCALISATION_PATH.is_file())
        self.assertFalse(LEGACY_DECISIONS_PATH.exists())
        self.assertFalse(LEGACY_LOCALISATION_PATH.exists())
        self.assertTrue(LOCALISATION_PATH.read_bytes().startswith(b"\xef\xbb\xbf"))

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

    def test_machine_shop_infrastructure_reward_is_state_scoped(self) -> None:
        focus = next(
            block
            for block in named_blocks(self.focuses, "focus")
            if re.search(
                r"(?m)^\s*id\s*=\s*VAL_Mobilize_Machine_Shops\s*$",
                block,
            )
        )
        reward = only_named_block(self, focus, "completion_reward")
        capital = only_named_block(self, reward, "capital_scope")
        self.assertIn(
            "add_building_construction = { type = infrastructure level = 1 instant_build = yes }",
            capital,
        )
        direct_reward = re.sub(
            r"capital_scope\s*=\s*\{.*?\}",
            "",
            reward,
            flags=re.DOTALL,
        )
        self.assertNotIn("add_building_construction", direct_reward)

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
        setters = direct_named_blocks(branch.text, "set_variable", branch.start)
        for hidden in direct_named_blocks(branch.text, "hidden_effect", branch.start):
            setters += direct_named_blocks(hidden.text, "set_variable", hidden.start)
        return [setter for setter in setters if expected.search(mask_comments(setter.text))]

    def contract_tier_operands(self, effect: str) -> set[str]:
        idea_commands = (
            "add_idea",
            "add_ideas",
            "remove_idea",
            "remove_ideas",
            "swap_ideas",
        )
        operands = set(
            re.findall(
                r"\b(?:add_ideas?|remove_ideas?|swap_ideas)\s*=\s*"
                r"(VAL_contract_[A-Za-z0-9_]+)\b",
                mask_non_code(effect),
            )
        )
        for command in idea_commands:
            for block in named_blocks(effect, command):
                operands.update(
                    re.findall(r"\bVAL_contract_[A-Za-z0-9_]+\b", mask_non_code(block))
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
            (FOREIGN_EFFECTS_PATH, self.foreign_effects),
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

    def test_independent_foreign_operations_do_not_call_removed_stp_campaign_effects(self) -> None:
        engine_effects = mask_comments(self.foreign_effects)
        self.assertNotRegex(
            engine_effects,
            r"\bVAL_recalculate_stp_campaign_readiness\s*=\s*yes\b",
        )
        for target in ("cin", "osf", "aph"):
            resolver = only_named_block(
                self, self.foreign_effects, f"VAL_resolve_{target}_operation"
            )
            self.assertRegex(
                mask_comments(resolver),
                r"\bVAL_clear_foreign_operation\s*=\s*yes\b",
            )

    def test_each_contract_tier_is_declared_once_and_apply_effects_use_only_it(self) -> None:
        hidden_ideas = only_named_block(self, self.ideas, "hidden_ideas")
        declared = set().union(*map(set, FAMILIES.values()))

        for command in (
            "add_idea",
            "add_ideas",
            "remove_idea",
            "remove_ideas",
            "swap_ideas",
        ):
            for form, assignment, expected in (
                (
                    "scalar",
                    "VAL_contract_not_declared",
                    {"VAL_contract_not_declared"},
                ),
                (
                    "brace",
                    "{ VAL_contract_administration_1 VAL_contract_not_declared }",
                    {"VAL_contract_administration_1", "VAL_contract_not_declared"},
                ),
            ):
                with self.subTest(command=command, form=form):
                    probe = (
                        "VAL_apply_contract_probe = {\n"
                        f"\t{command} = {assignment}\n"
                        "\t# VAL_contract_ignored_comment\n"
                        '\tcustom_effect_tooltip = "VAL_contract_ignored_string"\n'
                        "}"
                    )
                    operands = self.contract_tier_operands(probe)
                    self.assertEqual(operands, expected)
                    self.assertFalse(operands <= declared)

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
                    for preview in named_blocks(engine_effect, "effect_tooltip"):
                        engine_effect = engine_effect.replace(preview, "")
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

    def test_startup_initialization_is_fresh_only_and_one_shot(self) -> None:
        startup = only_named_block(self, self.on_actions, "on_startup")
        branch = only_named_block(self, startup, "if")
        limit = only_named_block(self, branch, "limit")

        fresh_guard = f"has_global_flag = {FRESH_CAMPAIGN_FLAG}"
        feature_guard = f"NOT = {{ has_global_flag = {VAL_FRESH_FEATURE_FLAG} }}"
        feature_set = f"set_global_flag = {VAL_FRESH_FEATURE_FLAG}"
        initialize_call = "VAL_initialize_rework = yes"
        for token in (fresh_guard, feature_guard, "VAL = { exists = yes }"):
            self.assertEqual(limit.count(token), 1)
        for token in (feature_set, initialize_call):
            self.assertEqual(branch.count(token), 1)
        self.assertRegex(
            mask_comments(branch),
            r"VAL\s*=\s*\{\s*VAL_initialize_rework\s*=\s*yes\s*\}",
        )

        positions = tuple(
            branch.index(token)
            for token in (fresh_guard, feature_guard, feature_set, initialize_call)
        )
        self.assertEqual(positions, tuple(sorted(positions)))
        self.assertEqual(mask_comments(self.on_actions).count(initialize_call), 1)

    def test_dead_tier_migration_definition_covers_completed_focus_tiers(self) -> None:
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

        migration = only_named_block(self, self.effects, TIER_MIGRATION_EFFECT)

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

    def test_dead_tier_migration_has_zero_runtime_callers(self) -> None:
        call = re.compile(
            rf"(?m)^\s*{re.escape(TIER_MIGRATION_EFFECT)}\s*=\s*yes\b"
        )
        callers: list[str] = []
        for runtime_root in ("common", "events", "history"):
            for path in sorted((ROOT / runtime_root).rglob("*.txt")):
                source = path.read_text(encoding="utf-8-sig", errors="replace")
                if call.search(mask_comments(source)):
                    callers.append(path.relative_to(ROOT).as_posix())
        self.assertEqual(callers, [])


class ValStelanderContractTests(unittest.TestCase):
    def focus(self, focus_id):
        return next(item for item in named_blocks(FOCUSES_PATH.read_text(encoding="utf-8-sig"), "focus")
                    if re.search(r"\bid\s*=\s*" + re.escape(focus_id) + r"\b", item))

    def test_company_specialisations_survive_recalculation_without_stacking(self):
        from tools.validators.validate_adiscord_division_templates import parse_clausewitz

        effects = parse_clausewitz(EFFECTS_PATH.read_text(encoding="utf-8-sig"))
        refresh = next(item.value for item in effects if item.key == "VAL_refresh_contract_modifier")
        # Older event-based operation writers must invalidate the same new income consumer.
        for tag in ("cin", "osf"):
            resolver = next(item.value for item in effects if item.key == f"VAL_resolve_{tag}_operation")
            calls = [entry.key for entry in resolver]
            self.assertLess(calls.index("clamp_variable"), calls.index("VAL_refresh_contract_modifier"))
            self.assertLess(calls.index("VAL_refresh_contract_modifier"), calls.index("ADISCORD_economy_mark_dirty"))

        specialisations = {
            "VAL_company_rosters": {"VAL_contract_org_factor": 0.02},
            "VAL_contractor_officers": {"VAL_contract_org_factor": 0.03},
            "VAL_motorized_columns": {"VAL_contract_supply_factor": -0.03},
            "VAL_field_repair_corps": {"VAL_contract_org_regain": 0.03},
            "VAL_ministry_auditors": {"VAL_contract_trade_income_factor": 0.05},
            "VAL_contract_general_staff": {"VAL_contract_planning_factor": 0.05, "VAL_contract_capture_factor": 0.03},
            "VAL_border_survey_complete": {"VAL_contract_supply_factor": -0.03},
            "VAL_company_service_code": {"VAL_contract_org_regain": 0.03},
            "VAL_contract_nco_schools": {"VAL_contract_org_factor": 0.03},
            "VAL_provincial_brokers_network": {"VAL_contract_trade_income_factor": 0.03, "VAL_contract_pp_gain": 0.05},
            "VAL_doctrine_covert_intervention": {"VAL_contract_planning_factor": 0.05, "VAL_contract_capture_factor": 0.03},
            "VAL_doctrine_sustained_supply": {"VAL_contract_org_regain": 0.03, "VAL_contract_supply_factor": -0.05},
            "VAL_north_open_market": {"VAL_contract_trade_income_factor": 0.07, "VAL_contract_pp_gain": 0.10},
            "VAL_export_clearing_house": {"VAL_contract_trade_income_factor": 0.05},
        }

        def recalculate(authority, flags, previous=None):
            values = dict(previous or {}, VAL_contract_authority=authority)

            def number(value):
                return values[value] if value in values else float(value)

            def condition(item):
                if item.key == "NOT":
                    return not all(condition(child) for child in item.value)
                if item.key == "has_country_flag":
                    return item.value in flags
                if item.key == "has_variable":
                    return item.value in values
                if item.key == "has_dynamic_modifier":
                    return True
                if item.key == "check_variable":
                    fields = {child.key: child.value for child in item.value}
                    actual, expected = values.get(fields["var"], 0), number(fields["value"])
                    return {"equals": actual == expected, "less_than": actual < expected,
                            "greater_than_or_equals": actual >= expected}[fields.get("compare", "greater_than_or_equals")]
                raise AssertionError(f"unhandled refresh condition: {item.key}")

            def execute(items):
                matched = False
                for item in items:
                    if item.key in {"if", "else_if", "else"}:
                        limit = next((child.value for child in item.value if child.key == "limit"), [])
                        take = all(condition(child) for child in limit)
                        if item.key != "if":
                            take = take and not matched
                        else:
                            matched = False
                        if take:
                            execute([child for child in item.value if child.key != "limit"])
                            matched = True
                    elif item.key in {"set_variable", "set_temp_variable", "add_to_variable"}:
                        fields = {child.key: child.value for child in item.value}
                        value = number(fields["value"])
                        if item.key == "add_to_variable":
                            value += values.get(fields["var"], 0)
                        values[fields["var"]] = value
                    elif item.key not in {"force_update_dynamic_modifier", "add_dynamic_modifier"}:
                        raise AssertionError(f"unhandled refresh effect: {item.key}")
            execute(refresh)
            return values

        for focus_id, flag, tier in (("VAL_Contractor_Officers", "VAL_contractor_officers", "army_2"),
                                     ("VAL_Motorized_Columns", "VAL_motorized_columns", "army_2"),
                                     ("VAL_Field_Repair_Corps", "VAL_field_repair_corps", "army_2"),
                                     ("VAL_Ministry_Auditors", "VAL_ministry_auditors", "administration_1"),
                                     ("VAL_Contract_General_Staff", "VAL_contract_general_staff", "army_3")):
            reward = only_named_block(self, self.focus(focus_id), "completion_reward")
            self.assertIn("set_country_flag = " + flag, reward)
            self.assertIn("VAL_refresh_contract_modifier = yes", reward)
            self.assertIn("VAL_apply_contract_" + tier + " = yes", reward)

        for authority in (10, 35, 60, 80, 95):
            base = recalculate(authority, set())
            for flag, deltas in specialisations.items():
                with self.subTest(authority=authority, flag=flag):
                    actual = recalculate(authority, {flag})
                    for variable, delta in deltas.items():
                        self.assertAlmostEqual(actual[variable] - base[variable], delta)
                    self.assertEqual(recalculate(authority, {flag}, actual), actual)
            all_flags = set(specialisations)
            combined = recalculate(authority, all_flags)
            self.assertAlmostEqual(combined["VAL_contract_org_factor"] - base["VAL_contract_org_factor"], 0.08)
            self.assertEqual(recalculate(authority, all_flags, combined), combined)
            for cin in (0, 1, 2, 3, 4):
                for osf in (0, 1, 2, 3, 4):
                    previous = dict(base, VAL_CIN_influence=cin, VAL_OSF_influence=osf)
                    network = recalculate(authority, set(), previous)
                    self.assertAlmostEqual(network["VAL_contract_trade_income_factor"] - base["VAL_contract_trade_income_factor"], .02 * (min(cin, 3) + min(osf, 3)))
                    self.assertEqual(recalculate(authority, set(), network), network)

            reforms = ("VAL_contractor_officers", "VAL_motorized_columns", "VAL_field_repair_corps")
            for order in permutations(reforms):
                previous, flags = base, set()
                for flag in order:
                    flags.add(flag)
                    current = recalculate(authority, flags, previous)
                    for variable, delta in specialisations[flag].items():
                        self.assertAlmostEqual(current[variable] - previous[variable], delta)
                    self.assertEqual(recalculate(authority, flags, current), current)
                    previous = current



    def test_rifle_contract_consumers_require_exact_payment_before_success(self):
        from tools.validators.validate_adiscord_division_templates import parse_clausewitz

        decisions = parse_clausewitz(DECISIONS_PATH.read_text(encoding="utf-8-sig"))
        effects = parse_clausewitz(EFFECTS_PATH.read_text(encoding="utf-8-sig"))

        def body(items, key):
            matches = [item.value for item in items if item.key == key]
            self.assertEqual(len(matches), 1, key)
            return matches[0]

        sales = body(decisions, "VAL_military_operations")
        cases = [
            ("VAL_pay_quarterly_contract_norm", 4000, "VAL_quarterly_contract_paid"),
        ]
        for name, price, success_flag in cases:
            sale = name.startswith("VAL_ops_")
            complete = body(body(sales, name), "complete_effect") if sale else body(effects, name)
            removal = body(body(sales, name), "remove_effect") if sale else []
            for stock in (0, price - 0.5, price, price + 50):
                for own_stock in (0, min(stock, 100)):
                    with self.subTest(contract=name, total=stock, own=own_stock):
                        # The imported-stock case exposed the producer=VAL consumer bug.
                        pools = {"VAL": own_stock, "STP": stock - own_stock}
                        flags = {"VAL_quarterly_contract_active", "STP_cw_rifles_paid"}
                        values, payment_calls = {}, []
                        rewards = {"treasury": 0, "influence": 0}

                        def fields(item):
                            return {part.key: part.value for part in item.value}

                        def number(value):
                            return values[value] if value in values else float(value)

                        def condition(item):
                            if item.key == "NOT":
                                return not all(condition(child) for child in item.value)
                            if item.key == "has_country_flag":
                                return item.value in flags
                            if item.key == "VAL_can_pay_quarterly_contract_norm":
                                return ("VAL_quarterly_contract_active" in flags
                                        and "VAL_quarterly_contract_paid" not in flags
                                        and sum(pools.values()) > 3999)
                            raise AssertionError(f"unhandled consumer condition: {item.key}")

                        def execute(items):
                            for item in items:
                                if item.key == "if":
                                    limit = body(item.value, "limit")
                                    if all(condition(child) for child in limit):
                                        execute([child for child in item.value if child.key != "limit"])
                                elif item.key == "hidden_effect":
                                    execute(item.value)
                                elif item.key == "set_temp_variable":
                                    data = fields(item)
                                    values[data["var"]] = number(data["value"])
                                elif item.key == "STP_cw_pay_rifles":
                                    # Boundary of the existing, separately tested payment API.
                                    # VAL supplies a price; only its fresh receipt permits success.
                                    flags.discard("STP_cw_rifles_paid")
                                    amount = values["STP_cw_rifle_cost"]
                                    payment_calls.append(amount)
                                    self.assertEqual(amount, price)
                                    if sum(pools.values()) >= amount:
                                        for producer in pools:
                                            debit = min(pools[producer], amount)
                                            pools[producer] -= debit
                                            amount -= debit
                                        flags.add("STP_cw_rifles_paid")
                                elif item.key == "add_equipment_to_stockpile":
                                    data = fields(item)
                                    producer = data.get("producer", "VAL")
                                    pools[producer] = max(0, pools[producer] + number(data["amount"]))
                                elif item.key == "set_country_flag":
                                    flags.add(item.value)
                                elif item.key == "clr_country_flag":
                                    flags.discard(item.value)
                                elif item.key == "ADISCORD_economy_receive_15":
                                    rewards["treasury"] += 15
                                elif item.key == "add_to_variable":
                                    rewards["influence"] += number(fields(item)["value"])
                                elif item.key != "add_political_power":
                                    raise AssertionError(f"unhandled consumer effect: {item.key}")

                        execute(complete)
                        paid = stock >= price
                        self.assertEqual(success_flag in flags, paid)
                        self.assertEqual(sum(pools.values()), stock - (price if paid else 0))
                        if paid:
                            self.assertEqual(payment_calls, [price], "must reuse the producer-aware API")
                        if sale:
                            execute(removal)
                            execute(removal)
                            self.assertEqual(rewards, {"treasury": 15 if paid else 0,
                                                      "influence": 2 if paid else 0})
                            self.assertNotIn("VAL_foreign_operation_active", flags)
                            self.assertNotIn(success_flag, flags)
                        elif paid:
                            execute(complete)
                            self.assertEqual(payment_calls, [price], "paid norm must not debit twice")
                            self.assertEqual(sum(pools.values()), stock - price)

    def test_arms_contract_keeps_money_and_goods_inside_successful_payment(self):
        contract = only_named_block(self, EFFECTS_PATH.read_text(encoding="utf-8-sig"), "VAL_cw_complete_arms_contract")
        guarded = named_blocks(contract, "if")
        success = next(item for item in guarded if re.match(
            r"if\s*=\s*\{\s*limit\s*=\s*\{\s*has_country_flag\s*=\s*STP_cw_rifles_paid\s*check_variable", item))
        buyer = only_named_block(self, success, "STS")
        self.assertIn("ADISCORD_economy_spend_50 = yes", buyer)
        self.assertIn("amount = 3200 producer = VAL", buyer)
        self.assertNotIn("add_manpower", buyer)
        self.assertIn("add_manpower = var:VAL_cw_contract_manpower_debit", success)
        self.assertEqual(contract.count("add_manpower = var:VAL_cw_contract_manpower_debit"), 1)
        self.assertIn("NOT = { has_manpower < 12600 }", contract)
        self.assertIn("NOT = { has_equipment = { infantry_equipment < 3200 } }", contract)
        self.assertIn("ADISCORD_economy_receive_50 = yes", success)
        self.assertIn("set_country_flag = VAL_cw_arms_contract_fulfilled", success)
        self.assertIn("NOT = { has_country_flag = VAL_cw_arms_contract_fulfilled }", contract)
        self.assertLess(contract.index("STP_cw_pay_rifles = yes"), contract.index("ADISCORD_economy_spend_50 = yes"))
        self.assertNotRegex(contract, r"amount\s*=\s*-3200")
        # There must be no unconditional transfer after a failed stock check.
        without_success = contract.replace(success, "")
        for token in ("ADISCORD_economy_spend_50", "ADISCORD_economy_receive_50"):
            self.assertNotIn(token, without_success)

    def test_each_exclusive_course_can_reach_the_contract_finish(self):
        finish = self.focus("VAL_The_Steel_Contract")
        prerequisites = [set(re.findall(r"focus\s*=\s*(\w+)", group))
                         for group in named_blocks(finish, "prerequisite")]
        for course in ("VAL_Arms_For_The_Burning", "VAL_Seize_The_Northern_Passes", "VAL_Keep_The_Arsenals"):
            with self.subTest(course=course):
                self.assertTrue(all({course} & group for group in prerequisites),
                                "separate prerequisite blocks require both exclusive courses")

    def test_crisis_unlock_tracks_stelander_and_arms_focus_does_not_discard_stock(self):
        opener = self.focus("VAL_Stelander_Crisis_Opens")
        self.assertNotIn("TFF", opener)
        self.assertIn("STP_cw_started", opener)
        arms = self.focus("VAL_Arms_For_The_Burning")
        self.assertNotIn("amount = -2000", arms)
        self.assertIn("unlock_decision_tooltip = VAL_cw_sell_arms_to_resistance", arms)


class ValRewardValidatorTests(unittest.TestCase):
    def reward_issues(self, reward, effects=""):
        from tools.validators.validate_adiscord_val_rework import validate_supplemental_rewards
        return validate_supplemental_rewards(
            "focus_tree = { focus = { id = VAL_probe completion_reward = { " + reward + " } } }", effects)

    def test_supplemental_points_require_an_executable_result(self):
        for reward in (
            "add_political_power = 25 set_country_flag = VAL_unused",
            "army_experience = 5 custom_effect_tooltip = add_building_construction",
            "add_command_power = 20 effect_tooltip = { add_manpower = 500 }",
            "add_political_power = 25 add_equipment_to_stockpile = { type = infantry_equipment amount = 0 }",
            "army_experience = 5 unlock_decision_tooltip = VAL_nonexistent",
            "add_political_power = 25 VAL_missing_helper = yes",
        ):
            with self.subTest(reward=reward):
                self.assertTrue(self.reward_issues(reward))

    def test_native_and_nested_scripted_rewards_allow_supplemental_points(self):
        self.assertFalse(self.reward_issues("army_experience = 5 add_manpower = 500"))
        self.assertFalse(self.reward_issues(
            "add_political_power = 25 hidden_effect = { VAL_outer = yes }",
            "VAL_outer = { VAL_inner = yes } VAL_inner = { add_offsite_building = { type = arms_factory level = 1 } }"))
        self.assertTrue(self.reward_issues("army_experience = 5 VAL_cycle = yes", "VAL_cycle = { VAL_cycle = yes }"))

    def test_refresh_without_a_new_modifier_change_is_not_a_reward(self):
        self.assertTrue(self.reward_issues(
            "add_political_power = 25 set_country_flag = VAL_unused VAL_refresh_contract_modifier = yes",
            "VAL_refresh_contract_modifier = { add_dynamic_modifier = { modifier = VAL_contract_state } }"))

    def test_known_zero_variable_quantity_is_not_a_reward(self):
        for amount in (0, 500):
            reward = (f"add_political_power = 25 set_temp_variable = {{ var = QA_amount value = {amount} }} "
                      "add_equipment_to_stockpile = { type = infantry_equipment amount = QA_amount }")
            with self.subTest(amount=amount):
                self.assertEqual(bool(self.reward_issues(reward)), amount == 0)

    def test_modifier_addition_must_survive_later_refresh(self):
        from tools.validators.validate_adiscord_val_rework import validate_supplemental_rewards
        effects = EFFECTS_PATH.read_text(encoding="utf-8-sig")
        dynamic = (ROOT / "common/dynamic_modifiers/ADISCORD_VAL_contract_dynamic_modifier.txt").read_text(encoding="utf-8-sig")
        for addition in ("add_to_variable = { var = VAL_contract_org_factor value = 0.5 }", "VAL_probe_add = yes"):
            for before_refresh in (True, False):
                refresh = "VAL_refresh_contract_modifier = yes"
                reward = addition + " " + refresh if before_refresh else refresh + " " + addition
                with self.subTest(addition=addition, before_refresh=before_refresh):
                    issues = validate_supplemental_rewards(
                        "focus_tree = { focus = { id = VAL_probe completion_reward = { add_political_power = 25 " + reward + " } } }",
                        effects + "\nVAL_probe_add = { add_to_variable = { var = VAL_contract_org_factor value = 0.5 } }", dynamic)
                    self.assertEqual(bool(issues), before_refresh)

    def preview_sources(self):
        return {
            "focuses": FOCUSES_PATH.read_text(encoding="utf-8-sig"),
            "effects": EFFECTS_PATH.read_text(encoding="utf-8-sig"),
        }

    def preview_issues(self, ideas=None, sources=None, dynamic=None):
        from tools.validators.validate_adiscord_val_rework import validate_val_preview_ideas
        return validate_val_preview_ideas(
            ideas or IDEAS_PATH.read_text(encoding="utf-8-sig"),
            sources or self.preview_sources(),
            dynamic or (ROOT / "common/dynamic_modifiers/ADISCORD_VAL_contract_dynamic_modifier.txt").read_text(encoding="utf-8-sig"),
            EFFECTS_PATH.read_text(encoding="utf-8-sig"),
        )

    def test_production_preview_contracts_are_valid(self):
        accepted, issues = self.preview_issues()
        self.assertEqual(issues, [])
        self.assertIn("VAL_contract_delta_dummy", accepted)
        self.assertIn("VAL_industry_1_to_2_delta", accepted)

    def test_dummy_installation_is_rejected_even_in_hidden_effect(self):
        for effect in ("add_ideas = VAL_company_rosters_delta",
                       "hidden_effect = { swap_ideas = { remove_idea = VAL_contract_delta_dummy add_idea = VAL_company_rosters_delta } }",
                       "add_timed_idea = { idea = VAL_company_rosters_delta days = 30 }"):
            sources = self.preview_sources() | {"events/probe.txt": "country_event = { immediate = { " + effect + " } }"}
            with self.subTest(effect=effect):
                self.assertTrue(self.preview_issues(sources=sources)[1])

    def test_preview_cannot_be_hidden_from_the_player(self):
        sources = self.preview_sources()
        preview = "effect_tooltip = { swap_ideas = { remove_idea = VAL_contract_delta_dummy add_idea = VAL_company_rosters_delta } }"
        self.assertIn(preview, sources["focuses"])
        sources["focuses"] = sources["focuses"].replace(preview, "hidden_effect = { " + preview + " }")
        self.assertTrue(self.preview_issues(sources=sources)[1])

    def test_dummy_permission_name_and_delta_cannot_be_faked(self):
        original = IDEAS_PATH.read_text(encoding="utf-8-sig")
        dummy = named_blocks(original, "VAL_company_rosters_delta")[0]
        for changed in (dummy.replace("always = no", "always = yes"),
                        dummy.replace("name = VAL_contract_state", "name = VAL_contract_army_1"),
                        dummy.replace("army_org_factor = 0.02", "army_org_factor = 0.12")):
            with self.subTest(changed=changed):
                self.assertNotEqual(changed, dummy)
                self.assertTrue(self.preview_issues(ideas=original.replace(dummy, changed))[1])

    def test_preview_requires_its_real_focus_flag_and_native_mapping(self):
        sources = self.preview_sources()
        sources["focuses"] = sources["focuses"].replace("set_country_flag = VAL_company_rosters", "set_country_flag = VAL_unused_roster_marker")
        self.assertTrue(self.preview_issues(sources=sources)[1])
        dynamic = (ROOT / "common/dynamic_modifiers/ADISCORD_VAL_contract_dynamic_modifier.txt").read_text(encoding="utf-8-sig")
        self.assertTrue(self.preview_issues(dynamic=dynamic.replace("army_org_factor = VAL_contract_org_factor", "army_attack_factor = VAL_contract_org_factor"))[1])


class ValNativePreviewTests(unittest.TestCase):
    def test_doctrine_and_export_previews_match_real_modifier_deltas(self):
        from tools.tests.test_adiscord_stp_preparation import block, scalar, walk
        from tools.validators.validate_adiscord_division_templates import parse_clausewitz

        ideas = block(block(parse_clausewitz(IDEAS_PATH.read_text(encoding="utf-8-sig")), "ideas"), "country")
        cases = {
            "VAL_Vorons_Companies": ("VAL_vorons_delta", {"planning_speed": 0.05, "equipment_capture_factor": 0.03}),
            "VAL_Contractor_Officers": ("VAL_nco_schools_delta", {"army_org_factor": 0.03}),
            "VAL_Motorized_Columns": ("VAL_border_survey_delta", {"supply_consumption_factor": -0.03}),
            "VAL_Field_Repair_Corps": ("VAL_company_service_delta", {"army_org_regain": 0.03}),
            "VAL_Ministry_Auditors": ("VAL_export_clearing_delta", {"ADISCORD_economy_trade_income_factor": 0.05}),
            "VAL_Contract_General_Staff": ("VAL_vorons_delta", {"planning_speed": 0.05, "equipment_capture_factor": 0.03}),
            "VAL_Stahls_Schedules": ("VAL_stahls_delta", {"army_org_regain": 0.03, "supply_consumption_factor": -0.05}),
            "VAL_Trading_Partners": ("VAL_trading_partners_delta", {"ADISCORD_economy_trade_income_factor": 0.07, "political_power_gain": 0.10}),
            "VAL_Export_Clearing_House": ("VAL_export_clearing_delta", {"ADISCORD_economy_trade_income_factor": 0.05}),
        }
        focuses = FOCUSES_PATH.read_text(encoding="utf-8-sig")
        for focus_id, (idea_id, expected) in cases.items():
            with self.subTest(focus=focus_id):
                idea = block(ideas, idea_id)
                self.assertEqual(scalar(idea, "name"), "VAL_contract_state")
                self.assertEqual({e.key: float(e.value) for e in block(idea, "modifier")}, expected)
                focus = next(b for b in named_blocks(focuses, "focus") if re.search(r"\bid\s*=\s*" + focus_id + r"\b", b))
                preview = named_block_spans(focus, "effect_tooltip")
                self.assertEqual(len(preview), 1)
                self.assertIn("remove_idea = VAL_contract_delta_dummy", preview[0].text)
                self.assertIn("add_idea = " + idea_id, preview[0].text)
                self.assertIn("VAL_refresh_contract_modifier = yes", focus)
        export = next(b for b in named_blocks(focuses, "focus") if "id = VAL_Export_Clearing_House" in b)
        self.assertIn("VAL_refresh_contract_modifier = yes", export)
        self.assertGreater(export.index("ADISCORD_economy_mark_dirty = yes"), export.index("VAL_refresh_contract_modifier = yes"))

    def test_army_and_auditor_tier_previews_hide_bookkeeping_and_follow_current_level(self):
        from tools.validators.validate_adiscord_division_templates import parse_clausewitz
        from tools.tests.test_adiscord_stp_preparation import block

        effects = parse_clausewitz(EFFECTS_PATH.read_text(encoding="utf-8-sig"))
        for family, tier in (("army", 2), ("army", 3), ("administration", 1)):
            helper = block(effects, f"VAL_apply_contract_{family}_{tier}")
            for level in (None, 0, 1, 2, 3):
                def condition(entry):
                    if entry.key == "hidden_trigger": return all(condition(e) for e in entry.value)
                    if entry.key == "OR": return any(condition(e) for e in entry.value)
                    if entry.key == "NOT": return not all(condition(e) for e in entry.value)
                    if entry.key == "has_variable": return level is not None
                    if entry.key == "check_variable":
                        fields = {e.key: e.value for e in entry.value}
                        return (level or 0) < int(fields["value"]) if fields["compare"] == "less_than" else (level or 0) == int(fields["value"])
                    raise AssertionError(entry.key)

                def preview(items, inside=False):
                    result, matched = [], False
                    for entry in items:
                        if entry.key in ("if", "else_if", "else"):
                            if entry.key == "if": matched = False
                            limit = next((e.value for e in entry.value if e.key == "limit"), [])
                            if not matched and all(condition(e) for e in limit):
                                result += preview([e for e in entry.value if e.key != "limit"], inside); matched = True
                        elif entry.key == "hidden_effect": continue
                        elif entry.key == "effect_tooltip": result += preview(entry.value, True)
                        elif entry.key == "swap_ideas" and inside:
                            fields = {e.key: e.value for e in entry.value}; result.append((fields["remove_idea"], fields["add_idea"]))
                        elif entry.key == "add_ideas" and inside: result.append((None, entry.value))
                        else: self.fail("visible bookkeeping: " + entry.key)
                    return result

                expected = [] if (level or 0) >= tier else [(f"VAL_contract_{family}_{level}" if level else None, f"VAL_contract_{family}_{tier}")]
                with self.subTest(family=family, target=tier, current=level):
                    self.assertEqual(preview(helper), expected)

    def test_industry_preview_depends_on_current_tier(self):
        from tools.tests.test_adiscord_stp_preparation import block, matches_conditions, scalar
        from tools.validators.validate_adiscord_division_templates import parse_clausewitz

        ideas = block(block(parse_clausewitz(IDEAS_PATH.read_text(encoding="utf-8-sig")), "ideas"), "country")
        expected_modifiers = {
            "VAL_industry_1_dummy": ("VAL_contract_industry_1", {}),
            "VAL_industry_2_dummy": ("VAL_contract_industry_2", {}),
            "VAL_industry_1_delta": ("VAL_contract_industry_1", {"industrial_capacity_factory": 0.04, "production_factory_efficiency_gain_factor": 0.05}),
            "VAL_industry_2_delta": ("VAL_contract_industry_2", {"industrial_capacity_factory": 0.07, "production_factory_efficiency_gain_factor": 0.08, "production_factory_max_efficiency_factor": 0.05, "production_lack_of_resource_penalty_factor": -0.05}),
            "VAL_industry_1_to_2_delta": ("VAL_contract_industry_2", {"industrial_capacity_factory": 0.03, "production_factory_efficiency_gain_factor": 0.03, "production_factory_max_efficiency_factor": 0.05, "production_lack_of_resource_penalty_factor": -0.05}),
        }
        for idea_id, (name, modifiers) in expected_modifiers.items():
            idea = block(ideas, idea_id)
            self.assertEqual(scalar(idea, "name"), name)
            self.assertEqual({e.key: float(e.value) for e in block(idea, "modifier")}, modifiers)

        def previews(items, facts, inside_preview=False):
            result, matched = [], False
            for entry in items:
                if entry.key in ("if", "else_if", "else"):
                    limit = next((e.value for e in entry.value if e.key == "limit"), [])
                    take = matches_conditions(limit, facts, "VAL")
                    if entry.key == "if":
                        matched = False
                    if take and not matched:
                        result += previews([e for e in entry.value if e.key != "limit"], facts, inside_preview)
                        matched = True
                elif entry.key == "swap_ideas" and inside_preview:
                    result.append((scalar(entry.value, "remove_idea"), scalar(entry.value, "add_idea")))
                elif isinstance(entry.value, list) and entry.key != "limit":
                    result += previews(entry.value, facts, inside_preview or entry.key == "effect_tooltip")
            return result

        for focus_id in ("VAL_Contract_Accounting_Office", "VAL_Standardize_Rifle_Lots"):
            focus = next(b for b in named_blocks(FOCUSES_PATH.read_text(encoding="utf-8-sig"), "focus") if "id = " + focus_id in b)
            reward = block(block(parse_clausewitz(focus), "focus"), "completion_reward")
            for level in (None, 0, 1, 2, 3):
                facts = {("VAL", "variable", "VAL_contract_industry_level"): level or 0,
                         ("VAL", "has_variable", "VAL_contract_industry_level"): level is not None}
                expected = []
                if focus_id == "VAL_Contract_Accounting_Office" and (level or 0) < 1:
                    expected = [("VAL_industry_1_dummy", "VAL_industry_1_delta")]
                elif focus_id == "VAL_Standardize_Rifle_Lots" and (level or 0) < 2:
                    expected = [("VAL_industry_2_dummy", "VAL_industry_1_to_2_delta" if level == 1 else "VAL_industry_2_delta")]
                with self.subTest(focus=focus_id, level=level):
                    self.assertEqual(previews(reward, facts), expected)



class ValNorthernExportTests(unittest.TestCase):
    def test_custom_prices_include_native_blocked_and_hover_suffixes(self):
        values = dict(re.findall(r'^ ([\w.]+):\s*"(.*)"$', LOCALISATION_PATH.read_text(encoding="utf-8-sig"), re.M))
        price_keys = set(re.findall(r"custom_cost_text\s*=\s*(\w+)", DECISIONS_PATH.read_text(encoding="utf-8-sig")))
        for key in price_keys:
            with self.subTest(price=key):
                self.assertIn(key + "_blocked", values)
                self.assertIn(key + "_tooltip", values)
                self.assertEqual(values[key + "_blocked"], values[key].replace("§Y", "§R"))
                self.assertIn(values[key], values[key + "_tooltip"])
                self.assertEqual(re.findall(r"£\w+", values[key]), re.findall(r"£\w+", values[key + "_blocked"]))

    def test_three_export_focuses_open_usable_actions_without_redundant_markers(self):
        from tools.tests.test_adiscord_stp_preparation import block, matches_conditions, parse_clausewitz, scalar, walk

        focuses = {scalar(e.value, "id"): e.value for e in walk(parse_clausewitz(FOCUSES_PATH.read_text(encoding="utf-8-sig")))
                   if e.key == "focus" and isinstance(e.value, list)}
        decisions = block(parse_clausewitz(DECISIONS_PATH.read_text(encoding="utf-8-sig")), "VAL_military_operations")
        for focus_id, obsolete in (("VAL_Foreign_Broker_Licences", "VAL_foreign_broker_licences"),
                                   ("VAL_Northern_Clearing_House", "VAL_northern_clearing_house"),
                                   ("VAL_Contingency_Ledgers", "VAL_contingency_ledgers")):
            reward = block(focuses[focus_id], "completion_reward")
            self.assertFalse(any(e.key == "set_country_flag" and e.value == obsolete for e in walk(reward)))
            self.assertFalse(any(e.key == "set_temp_variable" for e in walk(reward)))
            self.assertFalse(any(e.key == "ADISCORD_economy_receive_15" for e in walk(reward)))
            self.assertEqual([e.value for e in walk(reward) if e.key == "set_country_flag"], ["VAL_operations_map_unlocked"])
            unlocks = [e.value for e in reward if e.key == "unlock_decision_tooltip"]
            self.assertEqual(unlocks, ["VAL_ops_sell_rifles_to_cin", "VAL_ops_sell_rifles_to_osf"])
            facts = {("VAL", "has_completed_focus", focus_id): True,
                     ("VAL", "has_country_flag", "VAL_northern_operations_unlocked"): focus_id == "VAL_Contingency_Ledgers"}
            for buyer in ("CIN", "OSF"):
                gate = block(block(decisions, "VAL_ops_sell_rifles_to_" + buyer.lower()), "visible")
                ready = {**facts, ("VAL", "country_exists", buyer): True}
                self.assertTrue(matches_conditions(gate, ready, "VAL"))
                self.assertFalse(matches_conditions(gate, facts, "VAL"))
                self.assertTrue(matches_conditions(gate, {**facts, ("VAL", "has_country_flag", "VAL_operation_sell_rifles_to_" + buyer.lower()): True}, "VAL"),
                                "an accepted shipment stays visible when its first buyer disappears")

    def test_northern_export_preserves_producers_and_settles_only_once(self):
        """Execute the small export callbacks, including dead buyers and stale callbacks."""
        from itertools import product
        from tools.validators.validate_adiscord_division_templates import parse_clausewitz
        from tools.tests.test_adiscord_stp_preparation import block

        def parse_source(path):
            # This repository parser keeps bare comparison tokens separately; retain
            # these two known operators explicitly for the bounded callback model.
            source = re.sub(r"\b(has_political_power|infantry_equipment)\s*<\s*([\d.]+)",
                            r"\1_less_than = \2", path.read_text(encoding="utf-8-sig"))
            source = re.sub(r"\bvalue\s*>\s*(\d+)", r"flag_value_greater_than = \1", source)
            return parse_clausewitz(source)

        effects = parse_source(EFFECTS_PATH)
        decisions = block(parse_source(DECISIONS_PATH), "VAL_military_operations")
        scripted_loc = parse_source(ROOT / "common/scripted_localisation/ADISCORD_VAL_contract_scripted_loc.txt")
        helpers = {entry.key: entry.value for entry in effects}
        tags = ("VAL", "STP", "CIN", "OSF")
        licences, clearing, contingency = "VAL_Foreign_Broker_Licences", "VAL_Northern_Clearing_House", "VAL_Contingency_Ledgers"
        # Both commercial branches are normally exclusive; the combined quote also
        # protects this transaction if a future focus graph permits both upgrades.
        sale_profiles = (((licences,), ()), ((), ()), ((clearing,), ()), ((licences, clearing), ()),
                         ((), (licences, clearing)), ((licences,), (clearing,)),
                         ((contingency,), ()), ((), (contingency,)))
        for kind in ("sale", "finance"):
            for buyer in ("CIN", "OSF"):
                decision = block(decisions, "VAL_ops_sell_rifles_to_" + buyer.lower() if kind == "sale" else "VAL_ops_finance_" + buyer.lower() + "_contacts")
                receipt = "VAL_operation_sell_rifles_to_" + buyer.lower() if kind == "sale" else "VAL_operation_finance_" + buyer.lower() + "_contacts"
                profiles = sale_profiles if kind == "sale" else (((), ()),)
                for initial, profile in product(((0, 2500), (100, 2500), (2500, 0), (100, 2399.5),
                                                  (0, 5000), (100, 4900), (100, 4899.5), (5000, 0)), profiles):
                    for settlement in ("expiry", "cancel"):
                        for outcome in ("success", "third_party_war", "war", "gone", "capitulated", "seller_capitulated", "busy", "poor_pp", "prewar", "pregone", "precapitulated", "cap", "poor_cash", "both_gone", "both_war", "both_capitulated", "backup_gone"):
                            with self.subTest(kind=kind, buyer=buyer, stock=initial, outcome=outcome, settlement=settlement, profile=profile):
                                stocks = {tag: {producer: 0.0 for producer in tags} for tag in tags}
                                stocks["VAL"].update(VAL=initial[0], STP=initial[1])
                                values = {tag: {} for tag in tags}
                                flags = {tag: set() for tag in tags}
                                flag_values = {tag: {} for tag in tags}
                                focuses = set(profile[0])
                                quantity = 5000 if licences in focuses else 2500
                                quoted_income = (40 if clearing in focuses else 30) if licences in focuses else (20 if clearing in focuses else 15)
                                backup = "OSF" if buyer == "CIN" else "CIN"
                                exists, capitulated, wars = set(tags), set(), set()
                                pp, revenue = 9.5 if outcome == "poor_pp" else 10.0, 0
                                treasury = 49.5 if outcome == "poor_cash" else 100.0
                                initial_treasury = treasury
                                refresh_calls = dirty_calls = 0
                                initial_influence = 3 if outcome == "cap" else 2
                                influence = "VAL_" + buyer + "_influence"
                                values["VAL"][influence] = initial_influence

                                if outcome == "prewar": wars.add(frozenset(("VAL", buyer)))
                                if outcome == "pregone": exists.remove(buyer)
                                if outcome == "precapitulated": capitulated.add(buyer)
                                if outcome == "busy":
                                    flags["VAL"].add("VAL_foreign_operation_active")

                                def fields(item):
                                    return {entry.key: entry.value for entry in item.value}

                                def number(value, scope, previous):
                                    if value == "num_equipment@infantry_equipment":
                                        return sum(stocks[scope].values())
                                    if "." in value and not value.replace(".", "", 1).lstrip("-").isdigit():
                                        owner, name = value.split(".", 1)
                                        return values[previous if owner == "PREV" else owner].get(name, 0)
                                    try:
                                        return float(value)
                                    except ValueError:
                                        return values[scope].get(value, 0)

                                def condition(item, scope, previous):
                                    key, value = item.key, item.value
                                    if key in ("NOT", "OR", "AND", "hidden_trigger"):
                                        checks = [condition(child, scope, previous) for child in value]
                                        return not any(checks) if key == "NOT" else any(checks) if key == "OR" else all(checks)
                                    if key in tags or key == "PREV":
                                        return all(condition(child, previous if key == "PREV" else key, scope) for child in value)
                                    if key == "has_country_flag":
                                        if isinstance(value, list):
                                            data = fields(item)
                                            self.assertEqual(set(data), {"flag", "flag_value_greater_than"})
                                            return data["flag"] in flags[scope] and flag_values[scope].get(data["flag"], 1) > int(data["flag_value_greater_than"])
                                        return value in flags[scope]
                                    if key == "has_completed_focus": return scope == "VAL" and value in focuses
                                    if key == "tag": return scope == value
                                    if key == "has_variable": return value in values[scope]
                                    if key == "exists": return (scope in exists) == (value == "yes")
                                    if key == "country_exists": return value in exists
                                    if key == "has_capitulated": return (scope in capitulated) == (value == "yes")
                                    if key == "has_war_with": return frozenset((scope, value)) in wars
                                    if key == "has_political_power_less_than": return pp < float(value)
                                    if key == "ADISCORD_economy_can_spend_50": return treasury >= 50
                                    if key == "has_equipment":
                                        self.assertEqual(value[0].key, "infantry_equipment_less_than")
                                        return sum(stocks[scope].values()) < float(value[0].value)
                                    if key == "check_variable":
                                        data = fields(item); actual = number(data["var"], scope, previous); expected = number(data["value"], scope, previous)
                                        return {"equals": actual == expected, "greater_than": actual > expected,
                                                "greater_than_or_equals": actual >= expected}[data.get("compare", "greater_than_or_equals")]
                                    raise AssertionError("unhandled export condition: " + key)

                                def execute(items, scope="VAL", previous=None):
                                    nonlocal pp, revenue, treasury, refresh_calls, dirty_calls
                                    matched = False
                                    for item in items:
                                        key, value = item.key, item.value
                                        if key in ("if", "else_if", "else"):
                                            limit = next((entry.value for entry in value if entry.key == "limit"), [])
                                            if key == "if": matched = False
                                            if not matched and all(condition(child, scope, previous) for child in limit):
                                                execute([entry for entry in value if entry.key != "limit"], scope, previous); matched = True
                                        elif key == "hidden_effect": execute(value, scope, previous)
                                        elif key == "effect_tooltip" or key == "custom_effect_tooltip": pass
                                        elif key in tags or key == "PREV": execute(value, previous if key == "PREV" else key, scope)
                                        elif key == "every_possible_country":
                                            limit = next((entry.value for entry in value if entry.key == "limit"), [])
                                            # Engine may collect all matching producers before entering the loop.
                                            selected = [tag for tag in tags if all(condition(child, tag, scope) for child in limit)]
                                            for tag in selected: execute([entry for entry in value if entry.key != "limit"], tag, scope)
                                        elif key in ("set_variable", "set_temp_variable", "add_to_variable", "subtract_from_temp_variable", "subtract_from_variable", "multiply_temp_variable"):
                                            data = fields(item); name = data["var"]; amount = number(data["value"], scope, previous)
                                            old = values[scope].get(name, 0)
                                            values[scope][name] = old + amount if key == "add_to_variable" else old - amount if key in ("subtract_from_temp_variable", "subtract_from_variable") else old * amount if key == "multiply_temp_variable" else amount
                                            if key == "add_to_variable" and name == "ADISCORD_economy_treasury": treasury += amount
                                            if key == "add_to_variable" and name == "ADISCORD_economy_current_month_action_income": revenue += amount
                                        elif key == "ADISCORD_economy_initialize_country": pass  # Initial treasury is an explicit test input.
                                        elif key == "clamp_variable":
                                            data = fields(item); name = data["var"]; values[scope][name] = max(float(data["min"]), min(float(data["max"]), values[scope].get(name, 0)))
                                        elif key == "VAL_refresh_contract_modifier": refresh_calls += 1
                                        elif key == "ADISCORD_economy_mark_dirty": dirty_calls += 1
                                        elif key == "ADISCORD_economy_spend_50": treasury -= 50
                                        elif key == "ADISCORD_economy_receive_50": treasury += 50
                                        elif key == "clear_variable": values[scope].pop(value, None)
                                        elif key == "set_country_flag":
                                            if isinstance(value, list):
                                                data = fields(item); flags[scope].add(data["flag"]); flag_values[scope][data["flag"]] = int(data["value"])
                                            else: flags[scope].add(value); flag_values[scope][value] = 1
                                        elif key == "clr_country_flag": flags[scope].discard(value); flag_values[scope].pop(value, None)
                                        elif key == "add_equipment_to_stockpile":
                                            data = fields(item); producer = previous if data["producer"] == "PREV" else data["producer"]
                                            stocks[scope][producer] = max(0, stocks[scope][producer] + number(data["amount"], scope, previous))
                                        elif key == "add_political_power": pp += float(value)
                                        elif key == "ADISCORD_economy_receive_15": revenue += 15; treasury += 15
                                        elif key == "STP_cw_pay_rifles":
                                            # Old-source RED: account for the already tested immediate payment API.
                                            flags[scope].discard("STP_cw_rifles_paid")
                                            amount = values[scope]["STP_cw_rifle_cost"]
                                            if sum(stocks[scope].values()) >= amount:
                                                for producer in tags:
                                                    debit = min(stocks[scope][producer], amount)
                                                    stocks[scope][producer] -= debit; amount -= debit
                                                flags[scope].add("STP_cw_rifles_paid")
                                        elif key in helpers: execute(helpers[key], scope, previous)
                                        else: raise AssertionError("unhandled export effect: " + key)

                                self.assertEqual(all(condition(e, "VAL", None) for e in block(decision, "custom_cost_trigger")),
                                                 pp >= 10 and (sum(initial) >= quantity if kind == "sale" else treasury >= 50))
                                def displayed_number(name):
                                    getter = next(e.value for e in scripted_loc if e.key == "defined_text"
                                                  and next(child.value for child in e.value if child.key == "name") == name)
                                    for text in (e.value for e in getter if e.key == "text"):
                                        gate = next((e.value for e in text if e.key == "trigger"), [])
                                        if all(condition(e, "VAL", None) for e in gate):
                                            return int(next(e.value for e in text if e.key == "localization_key").rsplit("_", 1)[1])
                                    self.fail("export quote getter has no fallback")
                                if kind == "sale":
                                    self.assertEqual(displayed_number("VALGetExportRifleQuantity"), quantity)
                                    self.assertEqual(displayed_number("VALGetExportIncome"), quoted_income)
                                execute(block(decision, "complete_effect"))
                                paid = outcome not in ("busy", "poor_pp", "prewar", "pregone", "precapitulated") and (sum(initial) >= quantity if kind == "sale" else outcome not in ("cap", "poor_cash"))
                                self.assertEqual(receipt in flags["VAL"], paid)
                                self.assertEqual(sum(stocks["VAL"].values()), sum(initial) - (quantity if paid and kind == "sale" else 0))
                                self.assertEqual(pp, (9.5 if outcome == "poor_pp" else 10) - (10 if paid else 0))
                                self.assertEqual(treasury, initial_treasury - (50 if paid and kind == "finance" else 0))
                                if paid and kind == "sale":
                                    self.assertEqual(flag_values["VAL"].get("VAL_export_rifles_reserved"), quoted_income)
                                focuses.update(profile[1])  # Finishing a focus cannot rewrite an accepted quote.
                                if paid and kind == "sale":
                                    self.assertEqual(displayed_number("VALGetExportRifleQuantity"), quantity)
                                    self.assertEqual(displayed_number("VALGetExportIncome"), quoted_income)
                                if outcome in ("war", "both_war"): wars.add(frozenset(("VAL", buyer)))
                                if outcome == "both_war": wars.add(frozenset(("VAL", backup)))
                                if outcome == "third_party_war": wars.add(frozenset((buyer, "STP")))
                                if outcome in ("gone", "both_gone"): exists.remove(buyer)
                                if outcome in ("both_gone", "backup_gone"): exists.remove(backup)
                                if outcome in ("capitulated", "both_capitulated"): capitulated.add(buyer)
                                if outcome == "both_capitulated": capitulated.add(backup)
                                if outcome == "seller_capitulated": capitulated.add("VAL")
                                primary_valid = buyer in exists and buyer not in capitulated and frozenset(("VAL", buyer)) not in wars
                                backup_valid = backup in exists and backup not in capitulated and frozenset(("VAL", backup)) not in wars
                                reroute = kind == "sale" and contingency in focuses and backup_valid
                                invalid = "VAL" in capitulated or (not primary_valid and not reroute) or (kind == "finance" and outcome == "cap")
                                recipient = buyer if primary_valid else backup
                                self.assertEqual(all(condition(e, "VAL", None) for e in block(decision, "cancel_trigger")), invalid)
                                if settlement == "cancel" and invalid:
                                    execute(block(decision, "cancel_effect"))
                                # Direct expiry must also recheck; a cancelled operation is already consumed.
                                execute(block(decision, "remove_effect"))
                                delivered = paid and not invalid
                                self.assertEqual(revenue, quoted_income if delivered and kind == "sale" else 0)
                                for destination in (buyer, backup):
                                    self.assertEqual(sum(stocks[destination].values()), quantity if delivered and kind == "sale" and destination == recipient else 0)
                                self.assertEqual(treasury, initial_treasury + (quoted_income if kind == "sale" else -50) * delivered)
                                for destination, initial_level in ((buyer, initial_influence), (backup, 0)):
                                    gained = (2 if kind == "sale" else 1) if delivered and destination == recipient else 0
                                    self.assertEqual(values["VAL"].get("VAL_" + destination + "_influence", 0), min(3, initial_level + gained))
                                self.assertEqual((refresh_calls, dirty_calls), (int(delivered), int(delivered)))
                                for producer, amount in zip(("VAL", "STP"), initial):
                                    self.assertEqual(sum(stocks[destination][producer] for destination in ("VAL", buyer, backup)), amount)
                                self.assertFalse(any("VAL_export_rifles" in values[tag] for tag in tags))
                                self.assertNotIn("VAL_export_rifles_removed", values["VAL"])
                                # Old remove/cancel callbacks must neither duplicate money/goods nor release a newer operation.
                                snapshot = repr((stocks, revenue, pp, treasury, values["VAL"].get(influence), refresh_calls, dirty_calls))
                                flags["VAL"].add("VAL_foreign_operation_active")
                                execute(block(decision, "cancel_effect")); execute(block(decision, "remove_effect"))
                                self.assertEqual(repr((stocks, revenue, pp, treasury, values["VAL"].get(influence), refresh_calls, dirty_calls)), snapshot)
                                self.assertIn("VAL_foreign_operation_active", flags["VAL"])



class ValContractFormationTests(unittest.TestCase):
    def test_donor_selects_the_package_and_buyer_cannot_upgrade_it(self):
        from tools.tests.test_adiscord_stp_preparation import block, scalar, walk
        from tools.validators.validate_adiscord_division_templates import parse_clausewitz
        decisions = parse_clausewitz(DECISIONS_PATH.read_text(encoding="utf-8-sig"))
        decisions = {entry.key: entry.value for entry in walk(decisions)
                     if entry.key in ("VAL_cw_sell_arms_to_resistance", "VAL_cw_offer_contract_formations")}
        self.assertEqual(set(decisions), {"VAL_cw_sell_arms_to_resistance", "VAL_cw_offer_contract_formations"})
        focus = next(e.value for e in walk(parse_clausewitz(FOCUSES_PATH.read_text(encoding="utf-8-sig")))
                     if e.key == "focus" and isinstance(e.value, list) and scalar(e.value, "id") == "VAL_Arms_For_The_Burning")
        self.assertEqual({e.value for e in block(focus, "completion_reward") if e.key == "unlock_decision_tooltip"},
                         {"VAL_cw_sell_arms_to_resistance", "VAL_cw_offer_contract_formations", "VAL_cw_begin_mobilization"})
        events = parse_clausewitz((ROOT / "events/ADISCORD_STP_events.txt").read_text(encoding="utf-8-sig"))
        course = next(e.value for e in events if e.key == "country_event" and scalar(e.value, "id") == "ADISCORD_STP_cw.20")
        trade = next(e.value for e in course if e.key == "option" and scalar(e.value, "name") == "ADISCORD_STP_cw.20.c")
        self.assertEqual({scalar(e.value, "decision") for e in trade if e.key == "unlock_decision_tooltip"},
                         {"VAL_cw_sell_arms_to_resistance", "VAL_cw_offer_contract_formations", "VAL_cw_begin_mobilization"})
        offer = next(e.value for e in events if e.key == "country_event" and scalar(e.value, "id") == "ADISCORD_STP_cw.50")
        options = {scalar(e.value, "name"): e.value for e in offer if e.key == "option"}
        for decision_id, tier, option_id, treasury, manpower, rifles in (
            ("VAL_cw_sell_arms_to_resistance", "1", "ADISCORD_STP_cw.50.a", "50", None, "3200"),
            ("VAL_cw_offer_contract_formations", "2", "ADISCORD_STP_cw.50.c", "100", "12600", "4420"),
        ):
            decision = decisions[decision_id]
            pending = next(e.value for e in walk(block(decision, "complete_effect"))
                           if e.key == "set_country_flag" and isinstance(e.value, list)
                           and scalar(e.value, "flag") == "VAL_cw_arms_offer_pending")
            self.assertEqual((scalar(pending, "value"), scalar(pending, "days")), (tier, "21"))
            for gate in (block(decision, "available"), block(options[option_id], "trigger")):
                self.assertTrue(any(e.key == f"ADISCORD_economy_can_spend_{treasury}" for e in walk(gate)))
                decision_text = only_named_block(self, DECISIONS_PATH.read_text(encoding="utf-8-sig"), decision_id)
                if manpower is None:
                    self.assertNotIn("has_manpower", decision_text)
                else:
                    self.assertIn(f"has_manpower < {manpower}", decision_text)
                self.assertTrue(any(e.key == "has_equipment" and [c.value for c in e.value] == ["infantry_equipment", "<", rifles]
                                    for e in walk(gate)))
            # The visible answer and its delayed payload must both preserve the donor's tier.
            for gate in (block(options[option_id], "trigger"), block(options[option_id], "hidden_effect")):
                flags = [e.value for e in walk(gate) if e.key == "has_country_flag" and isinstance(e.value, list)
                         and scalar(e.value, "flag") == "VAL_cw_arms_offer_pending"]
                expected = ["value", "<", "2"] if tier == "1" else ["value", ">", "1"]
                self.assertTrue(any([c.value for c in f if not c.key] == expected for f in flags))
        refusal = block(options["ADISCORD_STP_cw.50.b"], "hidden_effect")
        self.assertTrue(any(e.key == "clr_country_flag" and e.value == "VAL_cw_arms_offer_pending" for e in walk(refusal)))
        self.assertFalse(any(e.key.startswith("ADISCORD_economy_spend_") for e in walk(refusal)))

    def test_full_contract_consumes_real_mixed_stocks_and_conserves_contents(self):
        from collections import defaultdict
        from tools.tests.test_adiscord_stp_preparation import block, scalar
        from tools.validators.validate_adiscord_division_templates import parse_clausewitz
        effects = parse_clausewitz(EFFECTS_PATH.read_text(encoding="utf-8-sig"))
        rifle_effects = parse_clausewitz((ROOT / "common/scripted_effects/ADISCORD_STP_scripted_effects.txt").read_text(encoding="utf-8-sig"))
        scripts = {name: block(tree, name) for tree, name in (
            (effects, "VAL_cw_complete_arms_contract"), (effects, "VAL_cw_pay_contract_auxiliary"),
            (rifle_effects, "STP_cw_pay_rifles"))}
        self.assertTrue(scripts["VAL_cw_pay_contract_auxiliary"])
        subunits = {entry.key: entry.value for entry in block(parse_clausewitz(
            (ROOT / "common/units/ADISCORD_land_units.txt").read_text(encoding="utf-8-sig")), "sub_units")}
        rifle, squad, support = "infantry_equipment", "ADISCORD_squad_weapons_equipment", "support_equipment"
        full_equipment = {rifle: 4420, squad: 96, support: 60}
        for tier in (1, 2, 3, 99):
            full = tier > 1
            price, people = (100, 12600) if full else (50, 0)
            required = full_equipment if full else {rifle: 3200, squad: 0, support: 0}
            scenarios = ["exact", "mixed", "short_money", "short_people", "stale", "no_land", "unlisted_creator"]
            scenarios += ["short_" + equipment for equipment, amount in required.items() if amount]
            if full:
                scenarios += ["unlisted_squad", "unlisted_support"]
            else:
                scenarios.remove("no_land")
                scenarios.remove("short_people")
            for scenario in scenarios:
                with self.subTest(tier=tier, scenario=scenario):
                    stock = {tag: {equipment: {} for equipment in full_equipment} for tag in ("VAL", "STS")}
                    for equipment, amount in required.items():
                        if scenario in ("mixed", "unlisted_creator"):
                            stock["VAL"][equipment] = {"VAL": amount / 4, "NOD": amount / 4,
                                                       "UNKNOWN" if scenario == "unlisted_creator" else "STS": amount / 2}
                        else:
                            stock["VAL"][equipment] = {"VAL": float(amount)}
                    if scenario in ("unlisted_squad", "unlisted_support"):
                        equipment = squad if scenario == "unlisted_squad" else support
                        stock["VAL"][equipment] = {"VAL": required[equipment] / 2, "UNKNOWN": required[equipment] / 2}
                    if scenario.startswith("short_") and scenario[6:] in required:
                        stock["VAL"][scenario[6:]]["VAL"] -= .5
                    cash = {"VAL": 0.0, "STS": price - (.5 if scenario == "short_money" else 0)}
                    manpower = {"VAL": people - (.5 if scenario == "short_people" else 0), "STS": 0.0}
                    initial_stock = {equipment: sum(stock["VAL"][equipment].values()) for equipment in full_equipment}
                    initial_cash, initial_people = sum(cash.values()), sum(manpower.values())
                    flags = {("VAL", "VAL_cw_trade_course"): 1, ("VAL", "STP_cw_rifles_paid"): 1}
                    if scenario != "stale":
                        flags[("VAL", "VAL_cw_arms_offer_pending")] = tier
                    variables, templates = {}, {}
                    field_equipment = defaultdict(float)
                    field_people = units = experience_rewards = authority_rewards = 0
                    def number(value, scope):
                        value = value.removeprefix("var:")
                        if value.startswith("num_equipment@"):
                            return sum(stock[scope][value.split("@", 1)[1]].values())
                        try:
                            return float(value)
                        except ValueError:
                            self.assertIn((scope, value), variables, "Unknown contract operand")
                            return variables[(scope, value)]
                    def compare(left, operator, right):
                        self.assertIn(operator, ("<", ">", "="))
                        return {"<": left < right, ">": left > right, "=": left == right}[operator]
                    def conditions(items, scope, previous):
                        results, index = [], 0
                        while index < len(items):
                            entry = items[index]
                            if not entry.key:
                                name, operator, amount = [e.value for e in items[index:index + 3]]
                                self.assertEqual(name, "has_manpower")
                                results.append(compare(manpower[scope], operator, float(amount)))
                                index += 3
                                continue
                            key = entry.key
                            if key in ("VAL", "STS", "PREV"):
                                results.append(conditions(entry.value, previous if key == "PREV" else key, scope))
                            elif key in ("OR", "AND", "NOT"):
                                if key == "OR":
                                    results.append(any(conditions([e], scope, previous) for e in entry.value))
                                elif key == "NOT":
                                    results.append(not conditions(entry.value, scope, previous))
                                else:
                                    results.append(conditions(entry.value, scope, previous))
                            elif key == "has_country_flag":
                                if isinstance(entry.value, str):
                                    results.append((scope, entry.value) in flags)
                                else:
                                    name = scalar(entry.value, "flag")
                                    field, operator, amount = [e.value for e in entry.value if not e.key]
                                    self.assertEqual(field, "value")
                                    results.append((scope, name) in flags and compare(flags[(scope, name)], operator, float(amount)))
                            elif key == "check_variable":
                                operators = {"equals": "=", "greater_than": ">", "greater_than_or_equals": ">="}
                                operator = operators[scalar(entry.value, "compare")]
                                left, right = number(scalar(entry.value, "var"), scope), number(scalar(entry.value, "value"), scope)
                                results.append(left >= right if operator == ">=" else compare(left, operator, right))
                            elif key == "has_equipment":
                                equipment, operator, amount = [e.value for e in entry.value]
                                results.append(compare(sum(stock[scope][equipment].values()), operator, float(amount)))
                            elif key.startswith("ADISCORD_economy_can_spend_"):
                                results.append(cash[scope] >= int(key.rsplit("_", 1)[1]))
                            elif key == "any_owned_state":
                                self.assertEqual([(e.key, e.value) for e in entry.value], [("is_controlled_by", "PREV")])
                                results.append(scenario != "no_land")
                            elif key == "tag":
                                results.append(scope == entry.value)
                            elif key == "exists":
                                results.append(entry.value == "yes")
                            elif key == "has_capitulated":
                                results.append(entry.value == "no")
                            elif key == "has_war_with":
                                results.append(scope == "STS" and entry.value == "STP")
                            else:
                                self.fail(f"Unsupported contract condition: {key}")
                            index += 1
                        return all(results)
                    def execute(items, scope="VAL", previous=None):
                        nonlocal field_people, units, experience_rewards, authority_rewards
                        taken = False
                        for entry in items:
                            key = entry.key
                            if key in ("if", "else_if", "else"):
                                if key == "if":
                                    taken = False
                                if not taken and (key == "else" or conditions(block(entry.value, "limit"), scope, previous)):
                                    taken = True
                                    execute([e for e in entry.value if e.key != "limit"], scope, previous)
                            elif key in scripts:
                                execute(scripts[key], scope, previous)
                            elif key in ("VAL", "STS", "PREV"):
                                execute(entry.value, previous if key == "PREV" else key, scope)
                            elif key == "every_possible_country":
                                for creator in ("VAL", "NOD", "STS"):
                                    if conditions(block(entry.value, "limit"), creator, scope):
                                        execute([e for e in entry.value if e.key != "limit"], creator, scope)
                            elif key in ("set_temp_variable", "multiply_temp_variable", "subtract_from_temp_variable"):
                                variable, value = scalar(entry.value, "var"), number(scalar(entry.value, "value"), scope)
                                if key == "set_temp_variable":
                                    variables[(scope, variable)] = value
                                elif key == "multiply_temp_variable":
                                    variables[(scope, variable)] *= value
                                else:
                                    variables[(scope, variable)] -= value
                            elif key == "set_country_flag":
                                if isinstance(entry.value, str):
                                    flags[(scope, entry.value)] = 1
                                else:
                                    flags[(scope, scalar(entry.value, "flag"))] = int(scalar(entry.value, "value"))
                            elif key == "clr_country_flag":
                                flags.pop((scope, entry.value), None)
                            elif key == "add_equipment_to_stockpile":
                                equipment, amount = scalar(entry.value, "type"), number(scalar(entry.value, "amount"), scope)
                                producer = scalar(entry.value, "producer")
                                self.assertIsNotNone(producer, "Never debit every creator independently")
                                creator = previous if producer == "PREV" else producer
                                pool = stock[scope][equipment]
                                pool[creator] = max(0, pool.get(creator, 0) + amount)
                            elif key == "add_manpower":
                                manpower[scope] += number(entry.value, scope)
                            elif key.startswith("ADISCORD_economy_spend_"):
                                cash[scope] -= int(key.rsplit("_", 1)[1])
                            elif key.startswith("ADISCORD_economy_receive_"):
                                cash[scope] += int(key.rsplit("_", 1)[1])
                            elif key == "division_template":
                                templates[(scope, scalar(entry.value, "name"))] = entry.value
                            elif key == "random_owned_controlled_state":
                                self.assertNotEqual(scenario, "no_land")
                                execute(entry.value, "deployment_state", scope)
                            elif key == "create_unit":
                                self.assertEqual(scalar(entry.value, "owner"), "PREV")
                                self.assertEqual(previous, "STS")
                                self.assertEqual(scalar(entry.value, "allow_spawning_on_enemy_provs"), "no")
                                definition = parse_clausewitz(scalar(entry.value, "division"))
                                self.assertEqual((scalar(definition, "start_experience_factor"), scalar(definition, "start_equipment_factor"), scalar(definition, "start_manpower_factor")), ("0.5", "1.0", "1.0"))
                                count = int(scalar(entry.value, "count"))
                                template = templates[(previous, scalar(definition, "division_template"))]
                                units += count
                                for slot in block(template, "regiments") + block(template, "support"):
                                    field_people += count * float(scalar(subunits[slot.key], "manpower"))
                                    for need in block(subunits[slot.key], "need"):
                                        field_equipment[need.key] += count * float(need.value)
                            elif key == "army_experience":
                                experience_rewards += number(entry.value, scope)
                            elif key == "VAL_change_contract_authority":
                                authority_rewards += variables[(scope, "ADISCORD_VAL_effect_value")]
                            elif key not in ("log", "country_event"):
                                self.fail(f"Unsupported contract operation: {key}")
                    execute(scripts["VAL_cw_complete_arms_contract"])
                    paid = scenario in ("exact", "mixed")
                    self.assertEqual(("VAL", "VAL_cw_arms_contract_fulfilled") in flags, paid)
                    self.assertEqual(units, 2 if paid and full else 0)
                    self.assertEqual(field_people, 12600 if paid and full else 0)
                    self.assertEqual(dict(field_equipment), {rifle: 1220, squad: 96, support: 60} if paid and full else {})
                    self.assertEqual(manpower["STS"], 0)
                    self.assertEqual(sum(stock["STS"][rifle].values()), 3200 if paid else 0)
                    self.assertEqual(cash["VAL"], price if paid else 0)
                    self.assertEqual((experience_rewards, authority_rewards), (5, 5) if paid else (0, 0))
                    self.assertAlmostEqual(sum(manpower.values()) + field_people, initial_people)
                    self.assertAlmostEqual(sum(cash.values()), initial_cash)
                    for equipment in full_equipment:
                        final = sum(sum(stock[tag][equipment].values()) for tag in stock) + field_equipment[equipment]
                        self.assertAlmostEqual(final, initial_stock[equipment])
                    self.assertTrue(all(value >= 0 for value in manpower.values()))
                    self.assertTrue(all(value >= 0 for value in cash.values()))
                    snapshot = (repr(stock), dict(manpower), dict(cash), units, experience_rewards, authority_rewards)
                    self.assertNotIn(("VAL", "VAL_cw_arms_offer_pending"), flags)
                    execute(scripts["VAL_cw_complete_arms_contract"])
                    self.assertEqual((repr(stock), manpower, cash, units, experience_rewards, authority_rewards), snapshot,
                                     "A repeated or expired callback cannot pay twice")

    def test_contract_localisation_values_are_single_physical_lines(self):
        raw = LOCALISATION_PATH.read_bytes()
        self.assertTrue(raw.startswith(b"\xef\xbb\xbf"))
        lines = raw.decode("utf-8-sig").splitlines()
        keys = (
            "VAL_cw_offer_contract_formations", "VAL_cw_offer_contract_formations_desc",
            "VAL_cw_formations_offer_tt", "VAL_cw_buy_formations_tt",
            "ADISCORD_STP_cw.50.full", "ADISCORD_STP_cw.50.c",
            "ADISCORD_STP_cw.51.accepted_full", "ADISCORD_STP_cw.51.refused",
        )
        for key in keys:
            with self.subTest(key=key):
                entries = [line for line in lines if re.match(r"^\s*" + re.escape(key) + r":", line)]
                self.assertEqual(len(entries), 1)
                self.assertRegex(entries[0], r'^\s*' + re.escape(key) + r':\d* "[^\r\n]*"$')
                self.assertNotIn("\ufffd", entries[0])
                if key == "ADISCORD_STP_cw.50.full":
                    self.assertIn(r"\n\n", entries[0], "Paragraph breaks must stay inside one localisation row")



class ValReclamationTests(unittest.TestCase):
    def test_reclamation_projects_are_bounded_paid_and_share_a_receipt(self):
        decisions = DECISIONS_PATH.read_text(encoding="utf-8")
        for key in ("roads", "water", "settlement"):
            with self.subTest(stage=key):
                rows = named_blocks(decisions, "VAL_reclamation_" + key)
                self.assertEqual(len(rows), 1)
                script = rows[0]
                self.assertIn("targets = { 24 42 48 54 55 56 57 }", script)
                self.assertIn("days_remove = 90", script)
                self.assertIn("cost = 0", script)
                self.assertIn("ADISCORD_economy_can_spend_500 = yes", script)
                self.assertIn("NOT = { has_variable = VAL_reclamation_deposit }", script)
                self.assertIn("VAL_reclamation_begin_project = yes", script)
                self.assertIn("VAL_reclamation_finish_project = yes", script)
                self.assertIn("VAL_reclamation_refund_project = yes", named_blocks(script, "cancel_effect")[0])
                self.assertIn("is_controlled_by = ROOT", script)
                self.assertNotIn("has_decision", script)
        effects = EFFECTS_PATH.read_text(encoding="utf-8")
        self.assertEqual(len(named_blocks(effects, "VAL_reclamation_finish_project")), 1)



    def test_payment_capture_cancellation_and_three_material_stages(self):
        from collections import defaultdict
        from tools.tests.test_adiscord_stp_preparation import block, scalar
        from tools.validators.validate_adiscord_division_templates import parse_clausewitz
        effects = {e.key: e.value for e in parse_clausewitz(EFFECTS_PATH.read_text(encoding="utf-8"))}
        triggers = {e.key: e.value for e in parse_clausewitz((ROOT / "common/scripted_triggers/ADISCORD_VAL_rework_triggers.txt").read_text(encoding="utf-8"))}
        values = defaultdict(float, {("VAL", "ADISCORD_economy_treasury"): 1500})
        flags, modifiers = set(), {(24, "ADISCORD_vorkerland_dirty_state"), (57, "ADISCORD_vorkerland_dirty_state")}
        owned = {24: True, 57: True}
        control = dict(owned)
        buildings = defaultdict(float, {(24, "infrastructure"): 2})
        foci = {"VAL_reclamation_survey", "VAL_reclamation_clean_water", "VAL_reclamation_return_home"}
        target = 24
        def number(value, scope):
            try:
                return float(value)
            except ValueError:
                return values.get((scope, value), 0)
        def compare(left, op, right):
            return {"equals": left == right, "greater_than_or_equals": left >= right, "<": left < right}[op]
        def condition(rows, scope="VAL"):
            result = []
            for index, e in enumerate(rows):
                k, v = e.key, e.value
                if k == "":
                    if v in ("infrastructure", "industrial_complex"):
                        result.append(compare(buildings[(scope, v)], rows[index + 1].value, float(rows[index + 2].value)))
                    continue
                if k in ("AND", "hidden_trigger"):
                    ok = condition(v, scope)
                elif k == "OR":
                    ok = any(condition([item], scope) for item in v)
                elif k == "NOT":
                    ok = not condition(v, scope)
                elif k in ("ROOT", "FROM"):
                    ok = condition(v, "VAL" if k == "ROOT" else target)
                elif k == "check_variable":
                    ok = compare(values.get((scope, scalar(v, "var")), 0), scalar(v, "compare"), number(scalar(v, "value"), scope))
                elif k == "has_variable":
                    ok = (scope, v) in values
                elif k == "has_state_flag":
                    ok = (scope, v) in flags
                elif k == "has_dynamic_modifier":
                    ok = (scope, scalar(v, "modifier")) in modifiers
                elif k == "has_completed_focus":
                    ok = v in foci
                elif k == "tag":
                    ok = scope == v
                elif k == "has_capitulated":
                    ok = v == "no"
                elif k in ("is_owned_by", "is_controlled_by"):
                    self.assertEqual(v, "ROOT")
                    ok = (owned if k == "is_owned_by" else control)[scope]
                elif k in ("infrastructure", "industrial_complex"):
                    ok = compare(buildings[(scope, k)], e.operator, float(v))
                elif k == "ADISCORD_economy_can_spend_500":
                    ok = values[(scope, "ADISCORD_economy_treasury")] >= 500
                elif k in triggers:
                    ok = condition(triggers[k], scope)
                else:
                    self.fail("Unsupported reclamation condition: " + k)
                result.append(ok)
            return all(result)
        def execute(rows, scope="VAL"):
            selected = False
            for e in rows:
                k, v = e.key, e.value
                if k == "if":
                    selected = condition(block(v, "limit"), scope)
                    if selected:
                        execute([x for x in v if x.key != "limit"], scope)
                elif k == "else_if":
                    if not selected and condition(block(v, "limit"), scope):
                        selected = True
                        execute([x for x in v if x.key != "limit"], scope)
                elif k == "else":
                    if not selected:
                        execute(v, scope)
                    selected = True
                elif k == "FROM":
                    execute(v, target)
                elif k in ("set_variable", "add_to_variable", "multiply_variable"):
                    key = (scope, scalar(v, "var"))
                    amount = number(scalar(v, "value"), scope)
                    values[key] = amount if k == "set_variable" else values[key] + amount if k == "add_to_variable" else values[key] * amount
                elif k == "clear_variable":
                    values.pop((scope, v), None)
                elif k == "set_state_flag":
                    flags.add((scope, v))
                elif k == "clr_state_flag":
                    flags.discard((scope, v))
                elif k == "add_dynamic_modifier":
                    modifiers.add((scope, scalar(v, "modifier")))
                elif k == "add_extra_state_shared_building_slots":
                    buildings[(scope, "slots")] += float(v)
                elif k == "add_building_construction":
                    self.assertEqual(scalar(v, "instant_build"), "yes")
                    buildings[(scope, scalar(v, "type"))] += float(scalar(v, "level"))
                elif k == "ADISCORD_economy_spend_500":
                    values[(scope, "ADISCORD_economy_treasury")] -= 500
                elif k in ("ADISCORD_economy_mark_dirty", "force_update_dynamic_modifier"):
                    pass
                elif k in effects:
                    execute(effects[k], scope)
                else:
                    self.fail("Unsupported reclamation effect: " + k)
        def call(key):
            execute(effects["VAL_reclamation_" + key])
        call("begin_project")
        self.assertEqual(values[("VAL", "ADISCORD_economy_treasury")], 1000)
        target = 57
        call("begin_project")
        call("finish_project")
        call("refund_project")
        self.assertEqual(values[("VAL", "ADISCORD_economy_treasury")], 1000)
        self.assertEqual(values[("VAL", "VAL_reclamation_deposit")], 500)
        target = 24
        control[24] = False
        call("finish_project")
        call("refund_project")
        self.assertEqual(values[("VAL", "ADISCORD_economy_treasury")], 1500)
        self.assertNotIn(("VAL", "VAL_reclamation_deposit"), values)
        self.assertEqual(buildings[(24, "infrastructure")], 2)
        control[24] = True
        for stage in range(1, 4):
            call("begin_project")
            call("finish_project")
            call("finish_project")
            self.assertEqual(values[(24, "VAL_reclamation_stage")], stage)
            self.assertEqual(values[("VAL", "ADISCORD_economy_treasury")], 1500 - 500 * stage)
            self.assertAlmostEqual(values[(24, "VAL_reclamation_people")], stage * .25)
            self.assertAlmostEqual(values[(24, "VAL_reclamation_resources")], stage * .20)
        self.assertEqual(buildings[(24, "infrastructure")], 3)
        self.assertEqual(buildings[(24, "slots")], 3)
        self.assertEqual(buildings[(24, "industrial_complex")], 1)
        call("begin_project")
        self.assertNotIn(("VAL", "VAL_reclamation_deposit"), values)
        for key, penalty in (("people", -.75), ("resources", -.60), ("slots", -.40), ("construction", -.50), ("supply", .35)):
            self.assertAlmostEqual(values[(24, "VAL_reclamation_" + key)] + penalty, 0)
        self.assertFalse(flags)

    def test_focus_layout_and_localisation_contracts(self):
        from tools.tests.test_adiscord_stp_preparation import scalar, walk
        from tools.validators.validate_adiscord_division_templates import parse_clausewitz
        focuses = [e.value for e in walk(parse_clausewitz(FOCUSES_PATH.read_text(encoding="utf-8"))) if e.key == "focus" and isinstance(e.value, list)]
        added = [f for f in focuses if scalar(f, "id").startswith("VAL_reclamation_")]
        self.assertEqual(len(added), 6)
        survey = next(f for f in added if scalar(f, "id") == "VAL_reclamation_survey")
        self.assertFalse(any(e.key == "prerequisite" for e in survey), "The separate programme must not draw a line across the central tree")
        available = next(e.value for e in survey if e.key == "available")
        self.assertEqual(scalar(available, "has_completed_focus"), "VAL_The_Harvest_Of_Ash")
        states = [e for e in walk(available) if e.key in {"24", "42", "48", "54", "55", "56", "57"}]
        self.assertEqual(len(states), 7)
        for state in states:
            self.assertEqual(scalar(state.value, "is_owned_by"), "ROOT")
            self.assertEqual(scalar(state.value, "is_controlled_by"), "ROOT")
            self.assertTrue(any(e.key == "has_dynamic_modifier" for e in state.value))
        for focus in added:
            xy = (scalar(focus, "x"), scalar(focus, "y"))
            self.assertEqual(sum((scalar(f, "x"), scalar(f, "y")) == xy for f in focuses), 1)
        data = LOCALISATION_PATH.read_bytes()
        self.assertTrue(data.startswith(b"\xef\xbb\xbf"))
        lines = data.decode("utf-8-sig").splitlines()
        for suffix in ("", "_blocked", "_tooltip"):
            self.assertEqual(sum(line.startswith(" VAL_reclamation_cost" + suffix + ":") for line in lines), 1)



class ValFrontierCampaignTests(unittest.TestCase):
    def test_coalition_membership_preserves_old_alliances_and_cleans_only_receipts(self):
        from tools.tests.test_adiscord_stp_preparation import parse_clausewitz, scalar
        definitions = {entry.key: entry.value for entry in parse_clausewitz(EFFECTS_PATH.read_text(encoding="utf-8"))}

        def exercise(initial, *, subject=None, external_join=False):
            factions = {name: list(members) for name, members in initial.items()}
            original = {name: list(members) for name, members in initial.items()}
            flags = {tag: set() for tag in ("VAL", "CIN", "OSF", "APH", "NOD", "STP", "OTH")}
            flags["STP"].add("STP_cw_won_union_battle")
            variables, targets = {}, {}
            subjects = subject or {}

            def resolve(name, stack):
                if name.startswith("event_target:"):
                    return targets.get(name.split(":", 1)[1])
                if name.startswith("PREV"):
                    return stack[-1 - len(name.split("."))]
                return name

            def faction(tag):
                return next((name for name, members in factions.items() if tag in members), None)

            def condition(items, stack):
                current = stack[-1]
                result = []
                for e in items:
                    k, v = e.key, e.value
                    if k in ("AND", "OR", "NOT"):
                        values = [condition([child], stack) for child in v]
                        ok = all(values) if k == "AND" else any(values) if k == "OR" else not any(values)
                    elif k == "any_other_country":
                        ok = any(condition(v, stack + [tag]) for tag in flags if tag != current)
                    elif k == "overlord":
                        ok = current in subjects and condition(v, stack + [subjects[current]])
                    elif k in flags or k.startswith("event_target:"):
                        other = resolve(k, stack)
                        ok = other is not None and condition(v, stack + [other])
                    elif k == "check_variable":
                        self.assertEqual(scalar(v, "compare"), "equals")
                        ok = variables.get((current, scalar(v, "var")), 0) == int(scalar(v, "value"))
                    elif k == "has_event_target":
                        ok = v in targets
                    elif k == "exists":
                        ok = (current in flags) == (v == "yes")
                    elif k == "has_capitulated":
                        ok = v == "no"
                    elif k == "has_war_with":
                        ok = False
                    elif k == "is_subject":
                        ok = (current in subjects) == (v == "yes")
                    elif k == "is_subject_of":
                        ok = subjects.get(current) == resolve(v, stack)
                    elif k == "is_in_faction":
                        ok = (faction(current) is not None) == (v == "yes")
                    elif k == "is_in_faction_with":
                        ok = faction(current) is not None and faction(current) == faction(resolve(v, stack))
                    elif k == "is_faction_leader":
                        name = faction(current)
                        ok = (name is not None and factions[name][0] == current) == (v == "yes")
                    elif k == "has_country_flag":
                        ok = v in flags[current]
                    else:
                        self.fail(f"Unsupported coalition condition: {k}")
                    result.append(ok)
                return all(result)

            def execute(items, stack):
                current = stack[-1]
                branch_taken = False
                for e in items:
                    k, v = e.key, e.value
                    if k in ("if", "else_if", "else"):
                        if k == "if":
                            branch_taken = False
                        gate = next((child.value for child in v if child.key == "limit"), [])
                        if not branch_taken and condition(gate, stack):
                            execute([child for child in v if child.key != "limit"], stack)
                            branch_taken = True
                    elif k in definitions:
                        self.assertEqual(v, "yes")
                        execute(definitions[k], stack)
                    elif k in flags or k.startswith("event_target:"):
                        other = resolve(k, stack)
                        if other is not None:
                            execute(v, stack + [other])
                    elif k == "faction_leader":
                        name = faction(current)
                        if name is not None:
                            execute(v, stack + [factions[name][0]])
                    elif k == "set_temp_variable":
                        variables[current, scalar(v, "var")] = int(scalar(v, "value"))
                    elif k == "save_global_event_target_as":
                        targets[v] = current
                    elif k == "clear_global_event_target":
                        targets.pop(v, None)
                    elif k == "set_country_flag":
                        flags[current].add(v)
                    elif k == "clr_country_flag":
                        flags[current].discard(v)
                    elif k == "create_faction_from_template":
                        self.assertEqual(scalar(v, "template"), "faction_template_ADISCORD_standard")
                        self.assertIsNone(faction(current), "Existing alliances must never be replaced")
                        factions[scalar(v, "name")] = [current]
                    elif k == "add_to_faction":
                        member = resolve(v, stack)
                        self.assertIsNone(faction(member), "Existing faction membership must never be moved")
                        factions[faction(current)].append(member)
                    elif k == "remove_from_faction":
                        factions[faction(current)].remove(resolve(v, stack))
                    elif k == "dismantle_faction":
                        del factions[faction(current)]
                    else:
                        self.fail(f"Unsupported coalition effect: {k}")

            execute(definitions["VAL_frontier_release_coalition"], ["VAL"])
            execute(definitions["VAL_frontier_join_coalition"], ["VAL", "CIN"])
            self.assertEqual(factions, original, "Peaceful outcomes without an anchor must leave alliances alone")
            execute(definitions["VAL_frontier_assemble_coalition"], ["VAL", "CIN"])
            prepared = {tag: faction(tag) for tag in flags}
            if external_join:
                factions[faction("NOD")].append("OTH")
            execute(definitions["VAL_frontier_release_coalition"], ["VAL"])
            after = {name: list(members) for name, members in factions.items()}
            execute(definitions["VAL_frontier_release_coalition"], ["VAL"])
            self.assertEqual(factions, after, "A repeated close must not remove another alliance")
            self.assertFalse(targets)
            self.assertFalse(any(flag.startswith("VAL_frontier_") for values in flags.values() for flag in values))
            if not external_join:
                self.assertEqual(factions, original)
            return prepared, factions

        prepared, _ = exercise({})
        self.assertEqual(prepared["CIN"], prepared["NOD"])
        self.assertEqual(prepared["CIN"], prepared["STP"])
        self.assertIsNotNone(prepared["CIN"])
        prepared, _ = exercise({"existing": ["NOD", "STP", "OTH"]})
        self.assertEqual(prepared["CIN"], "existing")
        prepared, _ = exercise({"north": ["NOD"], "party": ["STP", "OTH"]})
        self.assertEqual(prepared["CIN"], "north")
        self.assertEqual(prepared["STP"], "party")
        prepared, _ = exercise({"local": ["CIN", "OTH"], "north": ["NOD", "STP"]})
        self.assertEqual(prepared["CIN"], "local")
        self.assertEqual(prepared["NOD"], "north")
        for party_faction in ({}, {"party": ["STP", "OTH"]}):
            prepared, _ = exercise({"attacker": ["VAL", "NOD"], **party_faction})
            self.assertEqual(prepared["NOD"], "attacker")
            self.assertNotEqual(prepared["CIN"], "attacker", "The target must never join the attacker's existing alliance")
            self.assertEqual(prepared["CIN"], prepared["STP"])
        prepared, _ = exercise({"attacker": ["VAL", "NOD", "STP"]})
        self.assertIsNone(prepared["CIN"], "With both guarantors allied to VAL the target must stay independent")
        for subject in ({"STP": "NOD"}, {"NOD": "STP"}):
            prepared, _ = exercise({}, subject=subject)
            self.assertEqual(prepared["CIN"], prepared["NOD"])
            self.assertEqual(prepared["CIN"], prepared["STP"])
        _, surviving = exercise({}, external_join=True)
        self.assertEqual(list(surviving.values()), [["NOD", "OTH"]], "A later unrelated member must not be expelled by campaign cleanup")

    def test_campaign_coalition_precedes_war_and_majors_outlive_peace(self):
        from tools.tests.test_adiscord_stp_preparation import block, parse_clausewitz, scalar, walk
        definitions = parse_clausewitz(EFFECTS_PATH.read_text(encoding="utf-8"))
        start = block(definitions, "VAL_frontier_start_war")
        for tag in ("CIN", "OSF", "APH"):
            route = next(e.value for e in walk(start) if e.key == "if" and any(c.key == "declare_war_on" and scalar(c.value, "target") == tag for c in e.value))
            assemblies = [i for i, e in enumerate(route) if any(c.key == "VAL_frontier_assemble_coalition" for c in walk([e]))]
            self.assertEqual(len(assemblies), 1, "Every defended target must have exactly one coalition assembly")
            assembly = assemblies[0]
            declaration = next(i for i, e in enumerate(route) if e.key == "declare_war_on")
            self.assertLess(assembly, declaration)
            for guarantor in ("NOD", "STP"):
                call = next(e.value for e in walk(route) if e.key == "if" and any(c.key == guarantor and any(n.key == "add_to_war" for n in c.value) for c in e.value))
                self.assertEqual(scalar(block(block(call, "limit"), guarantor), "is_in_faction_with"), tag)
                self.assertEqual(scalar(block(block(block(call, "limit"), guarantor), "NOT"), "is_in_faction_with"), "VAL")
                self.assertEqual(scalar(block(block(call, guarantor), "add_to_war"), "single_target_only"), "yes")
        close = list(walk(block(definitions, "VAL_frontier_close")))
        last_peace = max(i for i, e in enumerate(close) if e.key == "white_peace")
        first_major_cleanup = min(i for i, e in enumerate(close) if e.key == "set_major" and e.value == "no")
        coalition_cleanup = next(i for i, e in enumerate(close) if e.key == "VAL_frontier_release_coalition")
        self.assertLess(last_peace, first_major_cleanup)
        self.assertLess(last_peace, coalition_cleanup)

    def test_each_guarantor_configuration_requires_the_named_military_result(self):
        from tools.tests.test_adiscord_stp_preparation import block, matches_conditions, parse_clausewitz
        source = parse_clausewitz((ROOT / "common/scripted_triggers/ADISCORD_VAL_rework_triggers.txt").read_text(encoding="utf-8"))
        gate = block(source, "VAL_frontier_guarantors_beaten")
        for nod, party, nod_loss, party_loss, expected in (
            (False, False, 0, 0, True),
            (True, False, 0, 0, False),
            (True, False, .26, 0, True),
            (False, True, 0, 0, False),
            (False, True, 0, .26, True),
            (True, True, .26, 0, False),
            (True, True, 0, .26, True),
        ):
            with self.subTest(nod=nod, party=party, nod_loss=nod_loss, party_loss=party_loss):
                facts = {
                    ("NOD", "has_country_flag", "VAL_frontier_guarantor"): nod,
                    ("STP", "has_country_flag", "VAL_frontier_guarantor"): party,
                    ("NOD", "numeric", "surrender_progress"): nod_loss,
                    ("STP", "numeric", "surrender_progress"): party_loss,
                }
                self.assertEqual(matches_conditions(gate, facts, "VAL"), expected)



    def frontier_matches(self, rows, facts, scope="VAL"):
        from tools.tests.test_adiscord_stp_preparation import matches_conditions, parse_clausewitz
        triggers = {e.key: e.value for e in parse_clausewitz((ROOT / "common/scripted_triggers/ADISCORD_VAL_rework_triggers.txt").read_text(encoding="utf-8"))}
        def groups(items):
            index = 0
            while index < len(items):
                count = 3 if not items[index].key else 1
                yield items[index:index + count]
                index += count
        def check(items, current):
            result = []
            for group in groups(items):
                entry = group[0]
                k, v = entry.key, entry.value
                if not k:
                    ok = matches_conditions(group, facts, current)
                elif k in ("AND", "hidden_trigger"):
                    ok = check(v, current)
                elif k in ("OR", "NOT"):
                    any_true = any(check(g, current) for g in groups(v))
                    ok = any_true if k == "OR" else not any_true
                elif k == "any_owned_state":
                    ok = any(check(v, str(state)) for state in facts.get((current, "owned_states"), ()))
                elif k.startswith("event_target:"):
                    target = facts.get(("event_target", k.split(":", 1)[1]))
                    ok = target is not None and check(v, target)
                elif k == "capital_scope":
                    ok = (current, "capital") in facts and check(v, facts[(current, "capital")])
                elif k == "controller":
                    ok = (current, "controller") in facts and check(v, facts[(current, "controller")])
                elif isinstance(v, list) and re.fullmatch(r"[A-Z]{3}|[0-9]+|ROOT", k):
                    ok = check(v, scope if k == "ROOT" else k)
                elif k in triggers:
                    ok = check(triggers[k], current) == (v == "yes")
                else:
                    ok = matches_conditions([entry], facts, current)
                result.append(ok)
            return all(result)
        return check(rows, scope)

    def test_commissariat_does_not_subordinate_foreign_land_or_third_party_occupation(self):
        from tools.tests.test_adiscord_stp_preparation import block, scalar, walk, parse_clausewitz
        effects = parse_clausewitz(EFFECTS_PATH.read_text(encoding="utf-8"))
        victory = block(effects, "VAL_frontier_settle_victory")
        for tag, states in (("CIN", (58, 59, 60)), ("OSF", (61, 62, 63)), ("APH", (64, 65))):
            candidates = [e.value for e in walk(victory) if e.key == "if" and any(x.key == "puppet" and scalar(x.value, "target") == tag for x in e.value)]
            self.assertEqual(len(candidates), 1)
            gate = block(candidates[0], "limit")
            facts = {
                ("VAL", "has_completed_focus", "VAL_frontier_commissioners"): True,
                (tag, "exists", "yes"): True,
                (tag, "is_subject", "no"): True,
                (tag, "owned_states"): states,
            }
            for state in states:
                facts[(str(state), "is_owned_by", tag)] = True
                facts[(str(state), "is_controlled_by", tag)] = True
            self.assertTrue(self.frontier_matches(gate, facts))
            foreign_land = {**facts, (tag, "owned_states"): (*states, 999)}
            self.assertFalse(self.frontier_matches(gate, foreign_land), "Extra foreign ownership must choose the bounded transfer instead of whole-country subordination")
            occupied = {**facts, (str(states[-1]), "is_controlled_by", tag): False}
            self.assertFalse(self.frontier_matches(gate, occupied), "The capitulation of a capital cannot award a third party's occupation")
            for state in states:
                transfers = [e.value for e in walk(victory) if e.key == "if" and any(x.key == "transfer_state" and x.value == str(state) for x in e.value)]
                self.assertEqual(len(transfers), 1)
                transfer_gate = block(transfers[0], "limit")
                self.assertTrue(self.frontier_matches(transfer_gate, facts))
                occupied_elsewhere = {**facts, (str(state), "is_controlled_by", tag): False}
                self.assertFalse(self.frontier_matches(transfer_gate, occupied_elsewhere), "The direct-transfer fallback must preserve third-party control too")

    def test_capitulation_proof_requires_the_current_target_and_its_still_occupied_capital(self):
        from tools.tests.test_adiscord_stp_preparation import block, parse_clausewitz
        triggers = parse_clausewitz((ROOT / "common/scripted_triggers/ADISCORD_VAL_rework_triggers.txt").read_text(encoding="utf-8"))
        gate = block(triggers, "VAL_frontier_target_occupied")
        for target, tag, capital in ((1, "CIN", "58"), (2, "OSF", "61"), (3, "APH", "64"), (4, "ERT", "167")):
            facts = {("VAL", "variable", "VAL_frontier_target"): target,
                     (tag, "has_country_flag", "VAL_frontier_defeated"): True,
                     (tag, "capital"): capital,
                     (capital, "is_controlled_by", "VAL"): True}
            self.assertTrue(self.frontier_matches(gate, facts), "A recorded defeat settles before automatic state-controller changes")
            self.assertFalse(self.frontier_matches(gate, {**facts, (capital, "is_controlled_by", "VAL"): False}), "A liberated capital invalidates the old defeat")
            self.assertFalse(self.frontier_matches(gate, {**facts, (tag, "has_country_flag", "VAL_frontier_defeated"): False}), "Capital occupation without a capitulation is insufficient")
            other_target = target % 4 + 1
            other_tag = {1: "CIN", 2: "OSF", 3: "APH", 4: "ERT"}[other_target]
            stale = {**facts, ("VAL", "variable", "VAL_frontier_target"): other_target, (other_tag, "capital"): "999"}
            self.assertFalse(self.frontier_matches(gate, stale), "Defeating another country does not satisfy this ultimatum")

    def test_unrelated_capitulator_cannot_install_nods_administration(self):
        from tools.tests.test_adiscord_stp_preparation import block, scalar, walk, parse_clausewitz
        actions = block(parse_clausewitz(ON_ACTIONS_PATH.read_text(encoding="utf-8")), "on_actions")
        immediate = block(block(actions, "on_capitulation_immediate"), "effect")
        handler = next(e.value for e in immediate if e.key == "if" and any(x.key == "set_country_flag" and x.value == "VAL_frontier_capitulation_pending" for x in e.value))
        gate = block(handler, "limit")
        facts = {("VAL", "variable", "VAL_frontier_stage"): 3,
                 ("VAL", "variable", "VAL_frontier_target"): 1,
                 ("VAL", "capital"): "24",
                 ("24", "controller"): "CIN",
                 ("CIN", "has_war_with", "VAL"): True,
                 ("APH", "has_war_with", "VAL"): True,
                 ("NOD", "exists", "yes"): True,
                 ("NOD", "has_country_flag", "VAL_frontier_guarantor"): True,
                 ("NOD", "has_war_with", "VAL"): True,
                 ("NOD", "has_capitulated", "no"): True}
        self.assertTrue(self.frontier_matches(gate, facts))
        self.assertFalse(self.frontier_matches(gate, {**facts, ("24", "controller"): "APH"}), "An unrelated war must retain its own capitulation route")
        self.assertTrue(self.frontier_matches(gate, {**facts, ("24", "controller"): "NOD"}))
        defeat = block(parse_clausewitz(EFFECTS_PATH.read_text(encoding="utf-8")), "VAL_frontier_settle_defeat")
        administration = next(e.value for e in walk(defeat) if e.key == "if" and any(x.key == "NOD" and any(y.key == "puppet" and scalar(y.value, "target") == "VAL" for y in x.value) for x in e.value))
        rule = block(administration, "limit")
        self.assertFalse(self.frontier_matches(rule, facts), "NOD cannot receive the country conquered by the local target")
        self.assertTrue(self.frontier_matches(rule, {**facts, ("24", "controller"): "NOD"}))



    def test_old_refusal_and_armistice_replies_cannot_change_another_ultimatum(self):
        from tools.tests.test_adiscord_stp_preparation import block, scalar, parse_clausewitz
        events = parse_clausewitz((ROOT / "events/ADISCORD_VAL_contract_events.txt").read_text(encoding="utf-8"))
        events = {scalar(e.value, "id"): e.value for e in events if e.key == "country_event"}
        refusal = {scalar(e.value, "name"): e.value for e in events["val_rework.111"] if e.key == "option"}
        armistice = {scalar(e.value, "name"): e.value for e in events["val_rework.113"] if e.key == "option"}
        for target, tag, states in ((1, "CIN", (58, 59, 60)), (2, "OSF", (61, 62, 63)), (3, "APH", (64, 65)), (4, "ERT", (168,))):
            facts = {("VAL", "variable", "VAL_frontier_target"): target,
                     ("VAL", "variable", "VAL_frontier_stage"): 2,
                     ("VAL", "has_global_flag", "STP_cw_union_wars_finished"): True,
                     ("VAL", "has_capitulated", "no"): True,
                     ("VAL", "is_subject", "no"): True,
                     ("VAL", "has_war", "no"): True,
                     (tag, "exists", "yes"): True,
                     (tag, "has_capitulated", "no"): True,
                     (tag, "is_subject", "no"): True,
                     ("event_target", "VAL_frontier_quoted_target"): tag}
            for state in states:
                facts[(str(state), "is_owned_by", tag)] = True
                facts[(str(state), "is_controlled_by", tag)] = True
            for changed, stage in ((False, 2), (True, 2), (False, 0), (False, 3)):
                scenario = {**facts, ("VAL", "variable", "VAL_frontier_stage"): stage,
                            ("VAL", "variable", "VAL_frontier_target"): target % 4 + 1 if changed else target}
                expected = not changed and stage == 2
                with self.subTest(event=111, target=tag, changed=changed, stage=stage):
                    for name in ("val_rework.111.withdraw", "val_rework.111.war"):
                        self.assertEqual(self.frontier_matches(block(refusal[name], "trigger"), scenario), expected)
                    self.assertEqual(self.frontier_matches(block(refusal["val_rework.closed"], "trigger"), scenario), not expected)
            peace = {**facts, ("VAL", "variable", "VAL_frontier_stage"): 3,
                     ("VAL", "has_country_flag", "VAL_frontier_armistice_offered"): True,
                     ("VAL", "numeric", "surrender_progress"): .70,
                     ("NOD", "has_country_flag", "VAL_frontier_guarantor"): True,
                     ("NOD", "has_war_with", "VAL"): True}
            for changed, stage, losses in ((False, 3, .70), (True, 3, .70), (False, 0, .70), (False, 3, .50)):
                scenario = {**peace, ("VAL", "variable", "VAL_frontier_stage"): stage,
                            ("VAL", "variable", "VAL_frontier_target"): target % 4 + 1 if changed else target,
                            ("VAL", "numeric", "surrender_progress"): losses}
                expected = not changed and stage == 3 and losses > .65
                with self.subTest(event=113, target=tag, changed=changed, stage=stage, losses=losses):
                    for name in ("val_rework.113.accept", "val_rework.113.refuse"):
                        self.assertEqual(self.frontier_matches(block(armistice[name], "trigger"), scenario, "NOD"), expected)
                    self.assertEqual(self.frontier_matches(block(armistice["val_rework.closed"], "trigger"), scenario, "NOD"), not expected)
        for options in (refusal, armistice):
            self.assertEqual({e.key for e in options["val_rework.closed"]}, {"name", "trigger"}, "A stale close-only answer cannot settle or withdraw the current campaign")

    def test_both_refusal_callers_capture_the_addressed_country_before_dispatch(self):
        from tools.tests.test_adiscord_stp_preparation import block, scalar, walk, parse_clausewitz
        effects = parse_clausewitz(EFFECTS_PATH.read_text(encoding="utf-8"))
        save = block(effects, "VAL_frontier_save_quoted_target")
        for target, tag in enumerate(("CIN", "OSF", "APH", "ERT"), 1):
            branch = next(e.value for e in save if e.key == "if" and any(x.key == tag for x in e.value))
            gate = block(branch, "limit")
            for current in range(1, 5):
                self.assertEqual(self.frontier_matches(gate, {("VAL", "variable", "VAL_frontier_target"): current}), current == target)
            self.assertEqual(scalar(block(branch, tag), "save_event_target_as"), "VAL_frontier_quoted_target")
        show = block(effects, "VAL_frontier_show_refusal")
        ordered = list(walk(show))
        save_index = next(i for i, e in enumerate(ordered) if e.key == "VAL_frontier_save_quoted_target")
        send_index = next(i for i, e in enumerate(ordered) if e.key == "country_event" and scalar(e.value, "id") == "val_rework.111")
        self.assertLess(save_index, send_index)
        self.assertTrue(any(e.key == "VAL_frontier_show_refusal" for e in walk(block(effects, "VAL_frontier_refuse"))))
        decisions = block(parse_clausewitz(DECISIONS_PATH.read_text(encoding="utf-8")), "VAL_frontier")
        timeout = block(block(decisions, "VAL_frontier_ultimatum_deadline"), "timeout_effect")
        self.assertTrue(any(e.key == "VAL_frontier_show_refusal" for e in walk(timeout)))
        weekly = block(effects, "VAL_frontier_weekly")
        peace_branch = next(e.value for e in walk(weekly) if e.key in ("if", "else_if") and any(x.key == "NOD" and any(y.key == "country_event" and scalar(y.value, "id") == "val_rework.113" for y in x.value) for x in e.value))
        self.assertLess(next(i for i, e in enumerate(peace_branch) if e.key == "VAL_frontier_save_quoted_target"), next(i for i, e in enumerate(peace_branch) if e.key == "NOD"))

    def test_armistice_compensates_only_the_party_that_actually_entered_the_war(self):
        from tools.tests.test_adiscord_stp_preparation import block, scalar, parse_clausewitz
        effect = block(parse_clausewitz(EFFECTS_PATH.read_text(encoding="utf-8")), "VAL_frontier_settle_armistice")
        for guarantor, at_war in ((False, False), (True, True), (True, False)):
            facts = {("VAL", "variable", "VAL_frontier_stage"): 3,
                     ("STP", "exists", "yes"): True,
                     ("STP", "has_country_flag", "STP_cw_won_union_battle"): True,
                     ("STP", "has_country_flag", "VAL_frontier_guarantor"): guarantor,
                     ("STP", "has_war_with", "VAL"): at_war}
            for state in (42, 55):
                facts[(str(state), "is_owned_by", "VAL")] = True
                facts[(str(state), "is_controlled_by", "VAL")] = True
            received = []
            closed = False
            def execute(rows, current="VAL"):
                nonlocal closed
                for e in rows:
                    if e.key == "if":
                        if self.frontier_matches(block(e.value, "limit"), facts, current):
                            execute([x for x in e.value if x.key != "limit"], current)
                    elif e.key == "set_temp_variable":
                        facts[(current, "variable", scalar(e.value, "var"))] = float(scalar(e.value, "value"))
                    elif e.key == "VAL_frontier_close":
                        closed = True
                        facts[("STP", "has_country_flag", "VAL_frontier_guarantor")] = False
                        facts[("STP", "has_war_with", "VAL")] = False
                        facts[("VAL", "variable", "VAL_frontier_stage")] = 0
                    elif e.key == "STP":
                        execute(e.value, "STP")
                    elif e.key == "transfer_state":
                        self.assertTrue(closed, "Snapshot participation before closing; transfer after peace")
                        received.append((current, int(e.value)))
                    elif e.key not in ("set_country_flag", "add_stability", "country_event"):
                        self.fail("Unsupported armistice operation: " + e.key)
            execute(effect)
            with self.subTest(guarantor=guarantor, at_war=at_war):
                self.assertEqual(received, [("STP", 42), ("STP", 55)] if guarantor and at_war else [])
                self.assertTrue(closed)

class ValNumericPreviewChainTests(unittest.TestCase):
    def test_native_unlock_requires_its_existing_paid_focus_gated_action(self):
        from tools.validators.validate_adiscord_val_rework import validate_supplemental_rewards
        focus = """focus_tree = { focus = { id = VAL_probe completion_reward = {
            unlock_decision_tooltip = VAL_probe_order add_political_power = 50
        } } }"""
        effects = "VAL_fulfill_order = { add_manpower = 100 }"
        decision = """VAL_orders = { VAL_probe_order = {
            visible = { has_completed_focus = VAL_probe }
            cost = 75 complete_effect = { VAL_fulfill_order = yes }
        } }"""
        self.assertEqual(validate_supplemental_rewards(focus, effects, decisions_text=decision), [])
        for broken in ("",
                       decision.replace("VAL_probe_order =", "VAL_other_order ="),
                       decision.replace("has_completed_focus = VAL_probe", "has_completed_focus = VAL_other_focus"),
                       decision.replace("has_completed_focus = VAL_probe", "NOT = { has_completed_focus = VAL_probe }"),
                       decision.replace("has_completed_focus = VAL_probe", "OR = { has_completed_focus = VAL_probe always = yes }"),
                       decision.replace("cost = 75", "cost = 0"),
                       decision.replace("cost = 75", "cost = 75 custom_cost_text = VAL_fake_price"),
                       decision.replace("VAL_fulfill_order = yes", "custom_effect_tooltip = VAL_fulfill_order"),
                       decision.replace("VAL_fulfill_order = yes", "VAL_missing_helper = yes")):
            with self.subTest(decision=broken):
                self.assertTrue(validate_supplemental_rewards(focus, effects, decisions_text=broken))

    def test_supplemental_points_follow_the_numeric_input_consumer(self):
        from tools.validators.validate_adiscord_val_rework import validate_supplemental_rewards
        dynamic = "VAL_contract_state = { army_org_factor = VAL_probe_output }"
        effects = """VAL_refresh_contract_modifier = {
            set_variable = { var = VAL_probe_output value = 0 }
            if = { limit = { has_variable = VAL_probe_input }
                add_to_variable = { var = VAL_probe_output value = VAL_probe_input } }
        }"""
        for variable, expected_error in (("VAL_probe_input", False), ("VAL_unused_input", True)):
            focus = ("focus_tree = { focus = { id = VAL_probe completion_reward = { army_experience = 20 "
                     "add_to_variable = { var = " + variable + " value = 0.10 } VAL_refresh_contract_modifier = yes } } }")
            self.assertEqual(bool(validate_supplemental_rewards(focus, effects, dynamic)), expected_error)

    def validate_chain(self, reward=None, refresh=None, dynamic=None):
        from tools.validators.validate_adiscord_val_rework import validate_val_preview_ideas
        ideas = """ideas = { country = {
            VAL_probe_base = { name = VAL_contract_state allowed = { always = no } modifier = {} }
            VAL_probe_delta = { name = VAL_contract_state allowed = { always = no }
                modifier = { ADISCORD_economy_trade_income_factor = 0.10 } }
        } }"""
        if reward is None:
            reward = "add_to_variable = { var = VAL_probe_input value = 0.10 } VAL_refresh_contract_modifier = yes"
        if refresh is None:
            refresh = """VAL_refresh_contract_modifier = {
                set_variable = { var = VAL_probe_output value = 0.03 }
                if = { limit = { has_variable = VAL_probe_input }
                    add_to_variable = { var = VAL_probe_output value = VAL_probe_input } }
                if = { limit = { has_dynamic_modifier = { modifier = VAL_contract_state } }
                    force_update_dynamic_modifier = yes }
                else = { add_dynamic_modifier = { modifier = VAL_contract_state } }
            }"""
        dynamic = dynamic or "VAL_contract_state = { ADISCORD_economy_trade_income_factor = VAL_probe_output }"
        focus = """focus_tree = { focus = { id = VAL_probe completion_reward = {
            effect_tooltip = { swap_ideas = { remove_idea = VAL_probe_base add_idea = VAL_probe_delta } }
            hidden_effect = { REWARD }
        } } }""".replace("REWARD", reward)
        return validate_val_preview_ideas(ideas, {"focuses": focus, "effects": refresh}, dynamic, refresh)

    def test_numeric_input_delta_follows_the_real_refresh_and_native_mapping(self):
        for reward in (None,
                       "add_to_variable = { var = VAL_probe_input value = 0.04 } "
                       "add_to_variable = { var = VAL_probe_input value = 0.06 } VAL_refresh_contract_modifier = yes",
                       "add_to_variable = { var = VAL_probe_input value = 0.10 } "
                       "VAL_refresh_contract_modifier = yes VAL_refresh_contract_modifier = yes"):
            with self.subTest(reward=reward):
                accepted, issues = self.validate_chain(reward=reward)
                self.assertEqual(issues, [])
                self.assertEqual(accepted, {"VAL_probe_base", "VAL_probe_delta"})

    def test_wrong_input_amount_and_unexecuted_refresh_are_rejected(self):
        addition = "add_to_variable = { var = VAL_probe_input value = 0.10 }"
        for reward in (
                addition.replace("VAL_probe_input", "VAL_wrong_input") + " VAL_refresh_contract_modifier = yes",
                addition.replace("0.10", "0.20") + " VAL_refresh_contract_modifier = yes",
                addition + " VAL_refresh_contract_modifier = no",
                addition + " effect_tooltip = { VAL_refresh_contract_modifier = yes }",
                addition + " if = { limit = { always = no } VAL_refresh_contract_modifier = yes }",
                "VAL_refresh_contract_modifier = yes " + addition,
                addition + " VAL_refresh_contract_modifier = yes " + addition,
                "STS = { " + addition + " } VAL_refresh_contract_modifier = yes"):
            with self.subTest(reward=reward):
                self.assertTrue(self.validate_chain(reward=reward)[1])

    def test_wrong_refresh_consumer_or_native_field_is_rejected(self):
        original = """VAL_refresh_contract_modifier = {
            set_variable = { var = VAL_probe_output value = 0.03 }
            if = { limit = { has_variable = VAL_probe_input }
                add_to_variable = { var = VAL_probe_output value = VAL_probe_input } }
            if = { limit = { has_dynamic_modifier = { modifier = VAL_contract_state } }
                force_update_dynamic_modifier = yes }
            else = { add_dynamic_modifier = { modifier = VAL_contract_state } }
        }"""
        for refresh in (
                original.replace("value = VAL_probe_input", "value = VAL_wrong_input"),
                original.replace("var = VAL_probe_output value = VAL_probe_input", "var = VAL_wrong_output value = VAL_probe_input"),
                original.replace("has_variable = VAL_probe_input", "has_variable = VAL_wrong_gate"),
                original.replace("set_variable = { var = VAL_probe_output value = 0.03 }", ""),
                original.replace("value = VAL_probe_input }", "value = VAL_probe_input } multiply_variable = { var = VAL_probe_output value = 2 }"),
                original.replace("VAL_refresh_contract_modifier = {", "VAL_refresh_contract_modifier = { set_variable = { var = VAL_probe_input value = 0 }"),
                original.replace("force_update_dynamic_modifier = yes", "force_update_dynamic_modifier = no"),
                original.replace("add_dynamic_modifier = { modifier = VAL_contract_state }", "add_dynamic_modifier = { modifier = VAL_wrong_dynamic }")):
            with self.subTest(refresh=refresh):
                self.assertTrue(self.validate_chain(refresh=refresh)[1])
        self.assertTrue(self.validate_chain(dynamic="VAL_contract_state = { army_org_factor = VAL_probe_output }")[1])


if __name__ == "__main__":
    unittest.main()
