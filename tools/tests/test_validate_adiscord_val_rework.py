from tools.lib.on_actions import read_country_on_actions
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


class ValOrderLedgerTests(unittest.TestCase):
    def test_ready_orders_respect_previously_commissioned_route_loss(self):
        from tools.tests.test_adiscord_stp_preparation import parse_clausewitz, block, matches_conditions
        source = (ROOT / "common/scripted_triggers/ADISCORD_VAL_rework_triggers.txt").read_text(encoding="utf-8")
        self.assertTrue(bool(named_blocks(source,"VAL_ready_delivery_route_open")))
        predicate = block(parse_clausewitz(source),"VAL_ready_delivery_route_open")
        facts = {("CIN","tag","CIN"):True}
        self.assertTrue(matches_conditions(predicate,facts,"CIN"))
        facts["VAL","has_country_flag","VAL_route_occidia_commissioned"] = True
        self.assertFalse(matches_conditions(predicate,facts,"CIN"))
        facts["VAL","VAL_trade_route_occidia_open","yes"] = True
        self.assertTrue(matches_conditions(predicate,facts,"CIN"))

    def test_military_quote_rechecks_target_control_at_acceptance(self):
        source = (ROOT / "common/scripted_triggers/ADISCORD_VAL_rework_triggers.txt").read_text(encoding="utf-8")
        predicate = only_named_block(self,source,"VAL_military_offer_valid")
        self.assertIn("is_controlled_by = event_target:VAL_military_enemy",predicate)
        self.assertIn("VAL_military_target_secured = yes",predicate)

    def test_route_prices_and_names_are_valid_bom_localisation(self):
        data=LOCALISATION_PATH.read_bytes()
        self.assertTrue(data.startswith(b"\xef\xbb\xbf"))
        text=data.decode("utf-8-sig").replace("\r\n", "\n")
        for route in ("occidia","north","stelander","vorkerland"):
            self.assertRegex(text,rf'(?m)^ VAL_upgrade_{route}_route:0 "[^"\n]+"$')
        for price in (250,500,750,1000):
            for suffix in ("","_blocked","_tooltip"):
                self.assertRegex(text,rf'(?m)^ VAL_route_cost_{price}{suffix}:0 "[^"\n]+"$')

    def test_instant_export_does_not_reuse_a_reserved_order_slot(self):
        text = EFFECTS_PATH.read_text(encoding="utf-8")
        for kind in ("arms", "bulk", "arsenal", "strategic"):
            body = only_named_block(self,text,"VAL_settle_partner_"+kind)
            self.assertIn("VAL_record_instant_export = yes",body)
            self.assertNotIn("add_timed_idea",body)

    def test_military_settlement_uses_escrow_and_specific_enemy(self):
        text = EFFECTS_PATH.read_text(encoding="utf-8")
        self.assertTrue(bool(named_blocks(text,"VAL_military_settle")))
        body = only_named_block(self,text,"VAL_military_settle")
        self.assertIn("VAL_military_escrow",body)
        self.assertIn("VAL_military_state value = 0",body)
        triggers = (ROOT / "common/scripted_triggers/ADISCORD_VAL_rework_triggers.txt").read_text(encoding="utf-8")
        gate = only_named_block(self,triggers,"VAL_military_conflict_open")
        self.assertIn("has_war_with = event_target:VAL_military_enemy",gate)
        self.assertNotIn("has_war = yes",gate)

    def test_order_refund_preserves_fractional_debt_and_frees_slot(self):
        from tools.tests.test_adiscord_stp_preparation import parse_clausewitz, block, scalar
        effects = parse_clausewitz(EFFECTS_PATH.read_text(encoding="utf-8"))
        self.assertTrue(any(e.key == "VAL_order_1_cancel" for e in effects), "orders need a cancellation ledger")
        cancel = block(effects, "VAL_order_1_legacy_cancel")
        # Execute the cancellation's arithmetic in the real scripted body.
        values = {"VAL": {"VAL_order_1_advance": 562.5, "VAL_order_1_state": 1},
                  "partner": {"VAL_refund_due": 125}}
        def execute(items, scope):
            for e in items:
                if e.key == "event_target:VAL_order_1_partner":
                    execute(e.value, "partner")
                elif e.key in ("set_variable", "add_to_variable"):
                    name, raw = scalar(e.value, "var"), scalar(e.value, "value")
                    try:
                        amount = float(raw)
                    except ValueError:
                        country, var = raw.split(".", 1) if "." in raw else (scope, raw)
                        amount = values[country].get(var, 0)
                    values[scope][name] = amount if e.key == "set_variable" else values[scope].get(name, 0)+amount
                elif e.key == "if":
                    condition = block(e.value, "limit")
                    checks = [c for c in condition if c.key == "check_variable"]
                    if all(values[scope].get(scalar(c.value,"var"),0) == float(scalar(c.value,"value")) for c in checks):
                        execute([c for c in e.value if c.key != "limit"],scope)
                elif e.key not in ("clr_country_flag", "remove_mission", "clear_variable", "clear_global_event_target", "VAL_refresh_order_summary"):
                    self.fail(f"Unmodelled cancellation effect: {e.key}")
        execute(cancel,"VAL")
        self.assertEqual(values["partner"]["VAL_refund_due"],687.5)
        self.assertEqual(values["VAL"]["VAL_order_1_state"],0)
        execute(cancel,"VAL")
        self.assertEqual(values["partner"]["VAL_refund_due"],687.5)

    def test_timeout_missions_cannot_complete_automatically(self):
        from tools.tests.test_adiscord_stp_preparation import parse_clausewitz, block, scalar
        decisions = parse_clausewitz(DECISIONS_PATH.read_text(encoding="utf-8"))
        self.assertTrue(any(e.key == "VAL_contract_obligations" for e in decisions))
        category = block(decisions,"VAL_contract_obligations")
        for slot in (1,2):
            mission = block(category,f"VAL_order_{slot}_deadline")
            available = block(block(mission,"available"),"hidden_trigger")
            self.assertEqual(scalar(available,"always"),"no")
            self.assertTrue(block(mission,"timeout_effect"))


class ValTradeMapTests(unittest.TestCase):
    def test_rail_path_does_not_bridge_disconnected_nodes(self):
        from tools.builders import build_adiscord_val_operations_map as builder
        self.assertTrue(hasattr(builder, "rail_path"), "trade map needs a rail graph path")
        graph = {1: {2}, 2: {1}, 3: set()}
        self.assertEqual(builder.rail_path(graph, 1, 2), [1, 2])
        self.assertIsNone(builder.rail_path(graph, 1, 3))

    def test_trade_routes_share_the_runtime_nodes(self):
        from tools.builders import build_adiscord_val_operations_map as builder
        self.assertTrue(hasattr(builder, "trade_route_states"), "route geometry must read runtime nodes")
        self.assertEqual(builder.trade_route_states()["occidia"], (43, 44, 88))
        self.assertEqual(builder.trade_route_states()["west"], (59, 60, 61))
        self.assertEqual(builder.trade_route_states()["north"], ())
        self.assertEqual(builder.trade_route_states()["vorkerland"], (33,))
        self.assertEqual(builder.trade_route_states()["south"], (68, 691, 70))

    def test_debug_category_exposes_south_route_controls_only_in_debug_mode(self):
        source = (ROOT / "common/decisions/ADISCORD_scenario_debug_decisions.txt").read_text(encoding="utf-8")
        for decision in ("ADISCORD_debug_val_open_south_route", "ADISCORD_debug_val_close_south_route", "ADISCORD_debug_val_upgrade_south_route", "ADISCORD_debug_val_reset_corridor_project", "ADISCORD_debug_val_fund_treasury"):
            start = source.index(f"\n\t{decision} = {{")
            end = source.index("\n\t}", start) + 3
            block = source[start:end]
            self.assertIn("is_debug = yes", block)
            self.assertIn("tag = VAL", block)
        self.assertIn("ADISCORD_debug_val_open_south_route", source)
        self.assertIn("VAL_refresh_trade_network = yes", source)

    def test_trade_panel_keeps_legend_below_all_route_rows(self):
        from tools.builders import build_adiscord_val_operations_map as builder
        boxes = {state: (0, 0, 10, 10) for state in builder.STATE_IDS}
        gui = builder.interface_outputs(boxes)["interface/ADISCORD_VAL_operations.gui"]
        self.assertIn("size = { width = 460 height = 570 }", gui)
        self.assertIn('name = "legend" position = { x = 20 y = 515 }', gui)

    def test_trade_map_tooltip_does_not_render_localisation_reference_literally(self):
        for language, marker in (("russian", "Серый рынок"), ("english", "grey market")):
            path = ROOT / f"localisation/{language}/ADISCORD_VAL_decisions_l_{language}.yml"
            text = path.read_text(encoding="utf-8-sig")
            tooltip = next(line for line in text.splitlines() if line.startswith(" VAL_trade_map_tt:0 "))
            self.assertNotIn("$VAL_trade_grey_market_tt$", tooltip)
            self.assertIn(marker, tooltip)
            self.assertIn("0-24", tooltip)

    def test_southern_route_uses_common_second_wave_corridor_unlock(self):
        from tools.builders import build_adiscord_val_operations_map as builder
        boxes = {state: (0, 0, 10, 10) for state in builder.STATE_IDS}
        script = builder.interface_outputs(boxes)["common/scripted_guis/ADISCORD_VAL_operations_scripted_gui.txt"]
        south = script[script.index("trade_south_1_visible"):script.index("trade_south_4_label_visible")]
        self.assertIn("VAL_trade_corridors_unlocked = yes", south)
        self.assertNotIn("has_completed_focus = VAL_Southern_Trade_Charter", south)
        self.assertNotIn("ADISCORD_debug_val_south_route_active", south)
        self.assertIn("trade_north_map_visible = { always = yes }", script)

    def test_russian_trade_localisation_distinguishes_west_and_standing_north(self):
        text = (ROOT / "localisation/russian/ADISCORD_VAL_decisions_l_russian.yml").read_text(encoding="utf-8-sig")
        self.assertIn('VAL_trade_west_1:0 "§L2. Запад:', text)
        self.assertIn('VAL_trade_north_1:0 "§L6. Север:', text)
        self.assertIn('VAL_upgrade_north_route:0 "Модернизировать западный коридор"', text)

    def test_trade_panel_replaces_static_aid_map_without_removing_operations(self):
        from tools.builders import build_adiscord_val_operations_map as builder
        boxes = {state: (0, 0, 10, 10) for state in builder.STATE_IDS}
        outputs = builder.interface_outputs(boxes)
        gui = outputs["interface/ADISCORD_VAL_operations.gui"]
        script = outputs["common/scripted_guis/ADISCORD_VAL_operations_scripted_gui.txt"]
        self.assertIn("ADISCORD_VAL_trade_routes_window", gui)
        self.assertNotIn("ADISCORD_VAL_vorkerland_aid_window", gui)
        self.assertIn("ADISCORD_VAL_operations_panel", script)
        self.assertIn("ADISCORD_STP_operations_panel", script)
        self.assertIn("trade_north_map_visible = { always = yes }", script)
        for route in ("occidia", "west", "stelander", "vorkerland", "north"):
            self.assertIn(f"VAL_trade_route_{route}_open", script)
            self.assertIn(f"VAL_route_{route}_commissioned", script)


class ValTierTransitionContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.effects = source_section(EFFECTS_PATH.read_text(encoding="utf-8-sig"), 'rework_effects')
        cls.ideas = IDEAS_PATH.read_text(encoding="utf-8-sig")
        cls.focuses = FOCUSES_PATH.read_text(encoding="utf-8-sig")
        cls.on_actions = read_country_on_actions(ON_ACTIONS_PATH, 'kefreyt')
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

    def test_each_contract_tier_is_declared_once_and_upward_apply_effects_do_not_install_it(self) -> None:
        hidden_ideas = only_named_block(self, self.ideas, "hidden_ideas")
        declared = set().union(*map(set, FAMILIES.values()))

        for family in FAMILIES.values():
            for idea in family:
                with self.subTest(idea=idea):
                    self.assertEqual(len(named_blocks(hidden_ideas, idea)), 1)

        for family in UPWARD_FAMILIES:
            for tier in range(1, 4):
                effect_name = f"VAL_apply_contract_{family}_{tier}"
                effect = only_named_block(self, self.effects, effect_name)
                engine = effect
                for preview in named_blocks(engine, "effect_tooltip"):
                    engine = engine.replace(preview, "")
                self.assertEqual(
                    self.contract_tier_operands(engine),
                    set(),
                    f"{effect_name} must use level variables + VAL_contract_state, not runtime tier ideas",
                )
                self.assertEqual(engine.count("VAL_refresh_contract_modifier = yes"), 1)

        for tier in range(4):
            effect = only_named_block(self, self.effects, f"VAL_apply_contract_reputation_{tier}")
            self.assertTrue(self.contract_tier_operands(effect) <= declared)

    def test_upward_apply_effects_refresh_dynamic_modifier_from_authoritative_levels(self) -> None:
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
                    self.assert_authoritative_guard(successful, variable, tier)
                    self.assertEqual(
                        self.contract_tier_operands(engine_effect),
                        set(),
                        "specialization tiers must not be installed as runtime ideas",
                    )
                    self.assertEqual(
                        engine_effect.count("VAL_refresh_contract_modifier = yes"),
                        1,
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
        branch = next(span.text for span in named_block_spans(startup, "if") if "VAL_initialize_rework = yes" in span.text)
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
        for tag in ("cin", "osf", "aph"):
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
            "VAL_hire_out_war": {"VAL_contract_military_income_factor": 0.05},
            "VAL_paid_loyalty": {"VAL_contract_army_expense_factor": -0.03},
            "VAL_closed_ledgers": {"VAL_contract_pp_gain": 0.05},
            "VAL_state_above_captains": {"VAL_contract_command_power_factor": 0.05},
            "VAL_captains_cannot_veto": {"VAL_contract_org_factor": 0.03},
            "VAL_front_stories": {"VAL_contract_stability_factor": 0.03},
            "VAL_army_of_the_ledger": {"VAL_contract_org_factor": 0.02, "VAL_contract_planning_factor": 0.03},
            "VAL_contract_throne": {"VAL_contract_pp_gain": 0.05},
            "VAL_weaponry_baron": {"VAL_contract_military_income_factor": 0.03},
            "VAL_mercenary_state": {"VAL_contract_org_regain": 0.02},
            "VAL_harvest_of_ash": {"VAL_contract_stability_factor": 0.02},
            "VAL_provincial_courts": {"VAL_contract_trade_income_factor": 0.03},
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
                    elif item.key not in {"force_update_dynamic_modifier", "add_dynamic_modifier", "ADISCORD_economy_mark_dirty"}:
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
            expected_org = sum(delta.get("VAL_contract_org_factor", 0) for delta in specialisations.values())
            self.assertAlmostEqual(combined["VAL_contract_org_factor"] - base["VAL_contract_org_factor"], expected_org)
            self.assertEqual(recalculate(authority, all_flags, combined), combined)
            for cin in (0, 1, 2, 3, 4):
                for osf in (0, 1, 2, 3, 4):
                    for aph in (0, 1, 2, 3, 4):
                        previous = dict(base, VAL_CIN_influence=cin, VAL_OSF_influence=osf, VAL_APH_influence=aph)
                        network = recalculate(authority, set(), previous)
                        self.assertAlmostEqual(network["VAL_contract_trade_income_factor"] - base["VAL_contract_trade_income_factor"], .02 * (min(cin, 3) + min(osf, 3) + min(aph, 3)))
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
            ("VAL_pay_quarterly_contract_norm", 40000, "VAL_quarterly_contract_paid"),
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
                        flags = {"VAL_quarterly_contract_active", "VAL_contract_rifles_paid"}
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
                                        and sum(pools.values()) > 39999)
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
                                elif item.key == "VAL_pay_contract_rifles":
                                    # Boundary of the existing, separately tested payment API.
                                    # VAL supplies a price; only its fresh receipt permits success.
                                    flags.discard("VAL_contract_rifles_paid")
                                    amount = values["VAL_contract_rifle_cost"]
                                    payment_calls.append(amount)
                                    self.assertEqual(amount, price)
                                    if sum(pools.values()) >= amount:
                                        for producer in pools:
                                            debit = min(pools[producer], amount)
                                            pools[producer] -= debit
                                            amount -= debit
                                        flags.add("VAL_contract_rifles_paid")
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
            r"if\s*=\s*\{\s*limit\s*=\s*\{\s*has_country_flag\s*=\s*VAL_contract_rifles_paid\s*check_variable", item))
        buyer = only_named_block(self, success, "STS")
        self.assertIn("ADISCORD_economy_spend_50 = yes", buyer)
        self.assertNotIn("add_equipment_to_stockpile", buyer)
        survival = (ROOT / "common/scripted_effects/ADISCORD_STP_scripted_effects.txt").read_text(encoding="utf-8-sig")
        delivery = only_named_block(self, survival, "STP_ps_deliver_val_contract")
        resolution = only_named_block(self, survival, "STP_ps_resolve_val_supply")
        self.assertIn("amount = 32000 producer = VAL", delivery)
        self.assertIn("set_variable = { var = STP_ps_val_receipt_money", buyer)
        self.assertIn("has_variable = STP_ps_val_receipt_rifles", resolution)
        self.assertLess(resolution.index("STP_ps_clear_val_receipt = yes"), resolution.index("STP_ps_deliver_val_contract = yes"))
        self.assertNotIn("add_manpower", buyer)
        self.assertIn("add_manpower = var:VAL_cw_contract_manpower_debit", success)
        self.assertEqual(contract.count("add_manpower = var:VAL_cw_contract_manpower_debit"), 1)
        self.assertIn("NOT = { has_manpower < 12600 }", contract)
        self.assertIn("NOT = { has_equipment = { infantry_equipment < 32000 } }", contract)
        self.assertIn("ADISCORD_economy_receive_50 = yes", resolution)
        self.assertNotIn("ADISCORD_economy_receive_50 = yes", success)
        self.assertIn("set_country_flag = VAL_cw_arms_contract_fulfilled", success)
        self.assertIn("NOT = { has_country_flag = VAL_cw_arms_contract_fulfilled }", contract)
        self.assertLess(contract.index("VAL_pay_contract_rifles = yes"), contract.index("ADISCORD_economy_spend_50 = yes"))
        self.assertNotRegex(contract, r"amount\s*=\s*-3200")
        # There must be no unconditional transfer after a failed stock check.
        without_success = contract.replace(success, "")
        for token in ("ADISCORD_economy_spend_50", "ADISCORD_economy_receive_50"):
            self.assertNotIn(token, without_success)

    def test_occidian_conquest_bypasses_neutrality_without_granting_its_reward(self):
        from tools.tests.test_adiscord_stp_preparation import matches_conditions
        from tools.validators.validate_adiscord_division_templates import parse_clausewitz
        triggers = {e.key: e.value for e in parse_clausewitz((ROOT / "common/scripted_triggers/ADISCORD_VAL_rework_triggers.txt").read_text(encoding="utf-8-sig"))}
        facts = {}
        for state in ("43", "44", "88"):
            facts[(state, "is_controlled_by", "VAL")] = True
        self.assertFalse(matches_conditions(triggers["VAL_occidia_secured"], facts, "VAL"))
        for state in ("43", "44", "88"):
            facts[(state, "is_owned_by", "VAL")] = True
        self.assertTrue(matches_conditions(triggers["VAL_occidia_secured"], facts, "VAL"))
        facts[("44", "is_controlled_by", "VAL")] = False
        self.assertFalse(matches_conditions(triggers["VAL_occidia_secured"], facts, "VAL"))
        facts = {("VAL", "VAL_occidian_administration_secured", "yes"): True}
        self.assertTrue(matches_conditions(triggers["VAL_occidia_secured"], facts, "VAL"))
        focus = self.focus("VAL_Keep_The_Arsenals")
        self.assertEqual(" ".join(named_blocks(focus, "bypass")[0].split()), "bypass = { VAL_occidia_secured = yes }")
        finish = self.focus("VAL_The_Steel_Contract")
        self.assertIn("VAL_occidia_secured = yes", named_blocks(finish, "available")[0])
        self.assertIn("OR = { has_country_flag = VAL_cw_military_course VAL_occidia_secured = yes }", finish)

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

    def test_named_selectable_staff_and_designers_are_not_country_spirit_previews(self):
        original = IDEAS_PATH.read_text(encoding="utf-8-sig")
        additions = """
        political_advisor_head_of_state = {
            VAL_named_advisor = { name = VAL_named_advisor allowed = { tag = VAL } cost = 75 }
        }
        industrial_concern = {
            VAL_named_concern = { name = VAL_concern_name allowed = { tag = VAL } cost = 75 }
        }
        materiel_manufacturer = {
            VAL_named_designer = { name = VAL_designer_name allowed = { tag = VAL } cost = 75 }
        }
        """
        augmented = original[:original.rfind("}")] + additions + original[original.rfind("}"):]
        accepted, issues = self.preview_issues(ideas=augmented)
        self.assertEqual(issues, [])
        self.assertTrue({"VAL_named_advisor", "VAL_named_concern", "VAL_named_designer"}.isdisjoint(accepted))
        self.assertIn("VAL_contract_delta_dummy", accepted)

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
                        dummy.replace("army_org_factor = 0.06", "army_org_factor = 0.12")):
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
            "VAL_Contractor_Officers": ("VAL_contractor_officers_delta", {"army_org_factor": 0.03}),
            "VAL_Motorized_Columns": ("VAL_motorized_columns_delta", {"supply_consumption_factor": -0.03}),
            "VAL_Gromovs_Assault_Tables": ("VAL_gromovs_delta", {"army_attack_factor": 0.04, "equipment_capture_factor": 0.05, "army_defence_factor": -0.02}),
            "VAL_Price_Of_Loyalty": ("VAL_captain_retainers_delta", {"command_power_gain_mult": 0.10}),
            "VAL_Count_The_Captains": ("VAL_negotiation_posture_delta", {"political_power_gain": 0.10}),
            "VAL_Ballistics_Schools": ("VAL_quality_arsenal_delta", {"industrial_capacity_factory": 0.05, "equipment_capture_factor": 0.02}),
            "VAL_Brokered_Steel": ("VAL_broad_resource_delta", {"supply_consumption_factor": -0.03, "ADISCORD_economy_trade_income_factor": 0.05}),
            "VAL_Export_Rifles_Not_Promises": ("VAL_supply_contracts_delta", {"ADISCORD_economy_military_industry_income_factor": 0.05, "ADISCORD_economy_army_expense_factor": -0.03}),
            "VAL_Field_Surgeons": ("VAL_ash_manpower_delta", {"conscription_factor": 0.05, "army_org_regain": 0.02}),
            "VAL_Bread_From_Barracks": ("VAL_ash_rear_delta", {"industrial_capacity_factory": 0.05, "consumer_goods_factor": -0.03}),
            "VAL_October_Of_2160": ("VAL_north_coercive_delta", {"ADISCORD_economy_military_industry_income_factor": 0.07, "army_attack_factor": 0.02, "stability_factor": -0.02}),
            "VAL_Field_Repair_Corps": ("VAL_field_repair_delta", {"army_org_regain": 0.03}),
            "VAL_Ministry_Auditors": ("VAL_ministry_auditors_delta", {"ADISCORD_economy_trade_income_factor": 0.05}),
            "VAL_Contract_General_Staff": ("VAL_general_staff_delta", {"planning_speed": 0.05, "equipment_capture_factor": 0.03}),
            "VAL_Stahls_Schedules": ("VAL_stahls_delta", {"army_org_regain": 0.03, "supply_consumption_factor": -0.05}),
            "VAL_Trading_Partners": ("VAL_trading_partners_delta", {"ADISCORD_economy_trade_income_factor": 0.07, "political_power_gain": 0.10}),
            "VAL_Export_Clearing_House": ("VAL_export_clearing_delta", {"ADISCORD_economy_trade_income_factor": 0.05, "ADISCORD_economy_overall_income_factor": 0.10, "ADISCORD_economy_admin_expense_factor": -0.05}),
            "VAL_Hire_Out_War": ("VAL_hire_out_war_delta", {"ADISCORD_economy_military_industry_income_factor": 0.05}),
            "VAL_Paid_Loyalty": ("VAL_paid_loyalty_delta", {"ADISCORD_economy_army_expense_factor": -0.03}),
            "VAL_Closed_Ledgers": ("VAL_closed_ledgers_delta", {"political_power_gain": 0.05}),
            "VAL_State_Above_Captains": ("VAL_state_above_captains_delta", {"command_power_gain_mult": 0.05}),
            "VAL_Captains_Cannot_Veto": ("VAL_captains_cannot_veto_delta", {"army_org_factor": 0.03}),
            "VAL_Stories_From_The_Front": ("VAL_front_stories_delta", {"stability_factor": 0.03}),
            "VAL_Army_Of_The_Ledger": ("VAL_army_of_the_ledger_delta", {"army_org_factor": 0.02, "planning_speed": 0.03}),
            "VAL_The_Contract_State": ("VAL_contract_throne_delta", {"political_power_gain": 0.05}),
            "VAL_The_Weaponry_Baron": ("VAL_weaponry_baron_delta", {"ADISCORD_economy_military_industry_income_factor": 0.03}),
            "VAL_The_Mercenary_State": ("VAL_mercenary_state_delta", {"army_org_regain": 0.02}),
            "VAL_The_Harvest_Of_Ash": ("VAL_harvest_ash_delta", {"stability_factor": 0.02}),
            "VAL_Provincial_Contract_Courts": ("VAL_provincial_courts_delta", {"ADISCORD_economy_trade_income_factor": 0.03}),
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
        for family, tier in (("army", 1), ("army", 2), ("army", 3), ("administration", 1), ("administration", 2), ("administration", 3)):
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

                expected = [] if (level or 0) >= tier else [(f"VAL_{family}_{level}_preview" if level else None, f"VAL_{family}_{tier}_preview")]
                with self.subTest(family=family, target=tier, current=level):
                    self.assertEqual(preview(helper), expected)

    def test_specialization_preview_validator_rejects_dynamic_drift(self):
        effects = EFFECTS_PATH.read_text(encoding="utf-8-sig")
        source = (
            "limit = { check_variable = { var = VAL_contract_army_level value = 3 compare = equals } }\n"
            "\t\tadd_to_variable = { var = VAL_contract_org_factor value = 0.07 }"
        )
        changed = source.replace("value = 0.07", "value = 0.071")
        self.assertIn(source, effects)
        drifted = effects.replace(source, changed, 1)
        sources = self.preview_sources()
        sources["effects"] = drifted
        accepted, issues = self.preview_issues(sources=sources)
        self.assertEqual(accepted, set())
        self.assertTrue(
            any(
                "VAL_contract_army_3 differs from VAL_contract_state" in issue
                for issue in issues
            ),
            issues,
        )

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
            "VAL_industry_3_dummy": ("VAL_contract_industry_3", {}),
            "VAL_industry_3_delta": ("VAL_contract_industry_3", {"industrial_capacity_factory": 0.10, "production_factory_efficiency_gain_factor": 0.12, "production_factory_max_efficiency_factor": 0.08, "production_lack_of_resource_penalty_factor": -0.10, "ADISCORD_economy_military_industry_income_factor": 0.08}),
            "VAL_industry_1_to_3_delta": ("VAL_contract_industry_3", {"industrial_capacity_factory": 0.06, "production_factory_efficiency_gain_factor": 0.07, "production_factory_max_efficiency_factor": 0.08, "production_lack_of_resource_penalty_factor": -0.10, "ADISCORD_economy_military_industry_income_factor": 0.08}),
            "VAL_industry_2_to_3_delta": ("VAL_contract_industry_3", {"industrial_capacity_factory": 0.03, "production_factory_efficiency_gain_factor": 0.04, "production_factory_max_efficiency_factor": 0.03, "production_lack_of_resource_penalty_factor": -0.05, "ADISCORD_economy_military_industry_income_factor": 0.08}),
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

        for focus_id in ("VAL_Contract_Accounting_Office", "VAL_Munitions_Board", "VAL_Standardize_Rifle_Lots",
                         "VAL_Standard_Cartridges", "VAL_Three_Shift_Arsenals", "VAL_Industrial_Mobilization_Plan"):
            focus = next(b for b in named_blocks(FOCUSES_PATH.read_text(encoding="utf-8-sig"), "focus") if "id = " + focus_id in b)
            reward = block(block(parse_clausewitz(focus), "focus"), "completion_reward")
            for level in (None, 0, 1, 2, 3):
                facts = {("VAL", "variable", "VAL_contract_industry_level"): level or 0,
                         ("VAL", "has_variable", "VAL_contract_industry_level"): level is not None}
                expected = []
                if focus_id in {"VAL_Contract_Accounting_Office", "VAL_Munitions_Board"} and (level or 0) < 1:
                    expected = [("VAL_industry_1_dummy", "VAL_industry_1_delta")]
                elif focus_id in {"VAL_Standardize_Rifle_Lots", "VAL_Standard_Cartridges", "VAL_Three_Shift_Arsenals"} and (level or 0) < 2:
                    expected = [("VAL_industry_2_dummy", "VAL_industry_1_to_2_delta" if level == 1 else "VAL_industry_2_delta")]
                elif focus_id == "VAL_Industrial_Mobilization_Plan" and (level or 0) < 3:
                    expected = [("VAL_industry_3_dummy", "VAL_industry_3_delta" if (level or 0) < 1 else "VAL_industry_1_to_3_delta" if level == 1 else "VAL_industry_2_to_3_delta")]
                if focus_id in {"VAL_Contract_Accounting_Office", "VAL_Industrial_Mobilization_Plan"}:
                    expected.append(("VAL_contract_delta_dummy", "VAL_fiscal_administration_delta"))
                with self.subTest(focus=focus_id, level=level):
                    self.assertEqual(previews(reward, facts), expected)



class ValIndustrialRecoveryTests(unittest.TestCase):
    """Execute the country-scoped economic lifecycle without inventing engine syntax."""

    recovery_focuses = (
        "VAL_Vorkerland_Contracts_Burn", "VAL_Inventory_The_Empty_Yards",
        "VAL_Mobilize_Machine_Shops", "VAL_Three_Shift_Arsenals",
        "VAL_Reserve_Accounting", "VAL_Industrial_Mobilization_Plan",
    )

    def setUp(self):
        from tools.validators.validate_adiscord_division_templates import parse_clausewitz
        self.effects = {e.key: e.value for e in parse_clausewitz(EFFECTS_PATH.read_text(encoding="utf-8-sig"))}
        self.facts = {}
        self.variables = {}
        self.modifiers = set()
        self.dirty = 0
        self.layout_updates = 0
        self.removed_rights = []
        self.installed_ideas = set()
        self.temporary = {}
        self.events = []

    def run_effect(self, name):
        from tools.tests.test_adiscord_stp_preparation import matches_conditions, scalar

        def number(value):
            try:
                return float(value)
            except ValueError:
                return self.temporary.get(value, self.variables.get(value, 0))

        def execute(items):
            matched = False
            for e in items:
                key, value = e.key, e.value
                if key in ("if", "else_if", "else"):
                    if key == "if":
                        matched = False
                    guard = next((c.value for c in value if c.key == "limit"), [])
                    facts = dict(self.facts)
                    for var, amount in {**self.variables, **self.temporary}.items():
                        facts[("VAL", "variable", var)] = amount
                        facts[("VAL", "has_variable", var)] = True
                    for idea in self.installed_ideas:
                        facts[("VAL", "has_idea", idea)] = True
                    for modifier in self.modifiers:
                        facts[("VAL", "has_dynamic_modifier", modifier)] = True
                    if not matched and matches_conditions(guard, facts, "VAL"):
                        execute([c for c in value if c.key != "limit"])
                        matched = True
                elif key == "hidden_effect":
                    execute(value)
                elif key == "set_temp_variable":
                    self.temporary[scalar(value, "var")] = number(scalar(value, "value"))
                elif key in ("set_variable", "add_to_variable", "multiply_variable"):
                    var, amount = scalar(value, "var"), number(scalar(value, "value"))
                    old = self.variables.get(var, 0)
                    self.variables[var] = amount if key == "set_variable" else old + amount if key == "add_to_variable" else old * amount
                elif key == "clamp_variable":
                    var = scalar(value, "var")
                    self.variables[var] = min(number(scalar(value, "max")), max(number(scalar(value, "min")), self.variables.get(var, 0)))
                elif key in ("set_country_flag", "clr_country_flag"):
                    self.facts[("VAL", "has_country_flag", value)] = key == "set_country_flag"
                elif key == "add_dynamic_modifier":
                    self.modifiers.add(scalar(value, "modifier"))
                elif key == "remove_dynamic_modifier":
                    modifier = scalar(value, "modifier")
                    self.assertIn(modifier, self.modifiers, "removal must be guarded")
                    self.modifiers.remove(modifier)
                elif key == "remove_resource_rights":
                    self.removed_rights.append(str(value))
                elif key == "add_ideas":
                    self.installed_ideas.add(value)
                elif key == "remove_ideas":
                    names = [e.value for e in value] if isinstance(value, list) else [value]
                    self.installed_ideas.difference_update(names)
                elif key == "country_event":
                    self.events.append(scalar(value, "id"))
                elif key == "mark_focus_tree_layout_dirty":
                    self.layout_updates += 1
                elif key == "ADISCORD_economy_mark_dirty":
                    self.dirty += 1
                elif key in self.effects and value == "yes":
                    execute(self.effects[key])
                elif key not in {"effect_tooltip", "custom_effect_tooltip", "remove_ideas", "country_event", "force_update_dynamic_modifier"}:
                    self.fail(f"Unsupported economic effect: {key}")
        execute(self.effects[name])

    def test_mercenary_spirit_combines_existing_base_and_authority_without_stacking(self):
        self.installed_ideas.add("VAL_mercenary_state")
        self.run_effect("VAL_initialize_contract_authority")
        self.assertNotIn("VAL_mercenary_state", self.installed_ideas)
        self.assertIn("VAL_contract_state", self.modifiers)
        expected = {"volunteer_size": 2, "war_stability": .1, "org_factor": .08,
                    "capture_factor": .04, "planning_factor": -.25, "pp_gain": -.15}
        for suffix, value in expected.items():
            self.assertAlmostEqual(self.variables["VAL_contract_" + suffix], value, msg=suffix)
        snapshot = dict(self.variables)
        self.run_effect("VAL_initialize_contract_authority")
        self.assertEqual(self.variables, snapshot)
        self.variables["VAL_contract_authority"] = 95
        self.facts[("VAL", "has_country_flag", "VAL_mercenary_state")] = True
        self.run_effect("VAL_initialize_contract_authority")
        self.assertAlmostEqual(self.variables["VAL_contract_org_factor"], .15)
        self.assertAlmostEqual(self.variables["VAL_contract_pp_gain"], 0)
        self.assertAlmostEqual(self.variables["VAL_contract_org_regain"], .12)
        self.modifiers.remove("VAL_contract_state")
        snapshot = dict(self.variables)
        self.run_effect("VAL_initialize_contract_authority")
        self.assertEqual(self.variables, snapshot)
        self.assertIn("VAL_contract_state", self.modifiers)

    def test_missing_reputation_consumer_is_rebuilt_at_saved_stage(self):
        self.variables["VAL_arsenal_reputation_stage"] = 5
        self.facts[("VAL", "has_country_flag", "VAL_vorkerland_resource_access_initialized")] = True
        self.run_effect("VAL_initialize_arsenal_recovery")
        self.assertIn("VAL_arsenal_reputation", self.modifiers)
        self.assertEqual(self.variables["VAL_arsenal_reputation_stage"], 5)
        self.assertAlmostEqual(self.variables["VAL_arsenal_quality"], .1)

    def test_refresh_cannot_drop_active_collapse_when_local_flag_is_lost(self):
        self.facts[("VAL", "has_country_flag", "VAL_vorkerland_contracts_disrupted")] = True
        self.variables.update(VAL_economic_recovery_steps=4, VAL_arsenal_reputation_stage=2)
        self.run_effect("VAL_refresh_industrial_economy")
        expected_output = self.variables["VAL_industrial_output"]
        self.facts.pop(("VAL", "has_country_flag", "VAL_vorkerland_contracts_disrupted"), None)
        self.run_effect("VAL_refresh_industrial_economy")
        self.assertTrue(self.facts.get(("VAL", "has_country_flag", "VAL_vorkerland_contracts_disrupted"), False))
        self.assertIn("VAL_economic_collapse", self.modifiers)
        self.assertNotIn("VAL_contract_industry", self.modifiers)
        self.assertAlmostEqual(self.variables["VAL_industrial_output"], expected_output)

    def test_stage_nine_stays_in_collapse_until_final_recovery_receipt(self):
        self.facts[("VAL", "has_country_flag", "VAL_vorkerland_contracts_disrupted")] = True
        self.variables.update(VAL_economic_recovery_steps=9, VAL_arsenal_reputation_stage=4)
        self.run_effect("VAL_refresh_industrial_economy")
        self.assertIn("VAL_economic_collapse", self.modifiers)
        self.assertNotIn("VAL_economic_miracle", self.modifiers)
        self.facts[("VAL", "has_country_flag", "VAL_economic_recovery_completed")] = True
        self.run_effect("VAL_refresh_industrial_economy")
        self.assertIn("VAL_economic_miracle", self.modifiers)
        self.assertNotIn("VAL_economic_collapse", self.modifiers)

    def test_peacetime_reconciliation_does_not_invent_a_supply_crisis(self):
        self.run_effect("VAL_reconcile_supply_crisis")
        self.assertNotIn("VAL_economic_collapse", self.modifiers)
        self.assertNotIn("VAL_economic_recovery_steps", self.variables)
        self.assertFalse(self.events)

    def test_outbreak_recovery_and_late_callbacks_preserve_final_state(self):
        self.run_effect("VAL_invest_arsenal_industry")
        self.assertEqual(self.modifiers, {"VAL_contract_industry"})
        self.run_effect("VAL_handle_vorkerland_war_outbreak")
        self.assertEqual(self.modifiers, {"VAL_economic_collapse", "VAL_arsenal_reputation"})
        self.assertAlmostEqual(self.variables["VAL_industrial_output"], -.73)
        self.assertEqual(self.layout_updates, 1)
        expected = {"output": (-.75, .09), "construction": (-.57, .07),
                    "efficiency": (-.57, .07), "trade": (-.85, .10),
                    "income": (-.57, .07), "consumer": (.18, -.02)}
        for stage in range(1, 10):
            if stage == 9:
                self.facts[("VAL", "has_country_flag", "VAL_economic_recovery_completed")] = True
            self.run_effect("VAL_advance_economic_recovery")
            for field, (base, increment) in expected.items():
                self.assertAlmostEqual(self.variables[f"VAL_industrial_{field}"], base + stage * increment + (.02 if field == "output" else 0))
            self.assertEqual(self.modifiers, {"VAL_economic_miracle" if stage == 9 else "VAL_economic_collapse", "VAL_arsenal_reputation"})
            snapshot = dict(self.variables)
            self.run_effect("VAL_handle_vorkerland_war_outbreak")
            self.run_effect("VAL_reconcile_supply_crisis")
            self.assertEqual(self.variables, snapshot)
        self.run_effect("VAL_advance_economic_recovery")
        self.assertEqual(self.variables["VAL_economic_recovery_steps"], 9)
        self.assertGreaterEqual(self.dirty, 8)

    def test_loading_active_crisis_refreshes_branch_and_preserves_penalty(self):
        for flag in ("VAL_vorkerland_contracts_disrupted", "VAL_vorkerland_resource_access_initialized"):
            self.facts[("VAL", "has_country_flag", flag)] = True
        self.variables.update(VAL_economic_recovery_steps=2, VAL_arsenal_reputation_stage=0)
        self.run_effect("VAL_initialize_arsenal_recovery")
        self.assertEqual(self.layout_updates, 1)
        self.assertEqual(self.variables["VAL_economic_recovery_steps"], 2)
        self.assertIn("VAL_economic_collapse", self.modifiers)
        self.assertAlmostEqual(self.variables["VAL_industrial_output"], -.57)

    def test_recovery_cannot_start_early_and_factory_grants_are_removed(self):
        self.run_effect("VAL_advance_economic_recovery")
        self.assertFalse(self.variables)
        focuses = FOCUSES_PATH.read_text(encoding="utf-8-sig")
        self.assertNotIn("add_offsite_building", focuses)
        self.assertEqual(focuses.count("VAL_advance_economic_recovery = yes"), 9)
        for focus_id in ("VAL_Mobilize_Machine_Shops", "VAL_Reserve_Accounting"):
            focus = next(f for f in named_blocks(focuses, "focus") if f"id = {focus_id}" in f)
            self.assertIn("prerequisite = { focus = VAL_Inventory_The_Empty_Yards }", focus)
        final = next(f for f in named_blocks(focuses, "focus") if "id = VAL_Industrial_Mobilization_Plan" in f)
        for prerequisite in ("VAL_Three_Shift_Arsenals", "VAL_Reserve_Accounting"):
            self.assertIn(f"prerequisite = {{ focus = {prerequisite} }}", final)
        supply_base = next(f for f in named_blocks(focuses, "focus") if "id = VAL_New_Supply_Base" in f)
        self.assertIn("remove_ideas = VAL_vorkerland_metal_shortage", supply_base)

    def test_base_vorkerland_metal_access_loss_creates_shortage_without_optional_concession(self):
        self.facts[("VAL", "has_country_flag", "VAL_vorkerland_resource_access_active")] = True
        self.variables["VAL_arsenal_reputation_stage"] = 4
        self.run_effect("VAL_handle_vorkerland_war_outbreak")
        self.assertEqual(self.removed_rights, ["33"])
        self.assertIn("VAL_vorkerland_metal_shortage", self.installed_ideas)
        self.assertTrue(self.facts.get(("VAL", "has_country_flag", "VAL_westerholm_metal_lost"), False))

        dirty = self.dirty
        self.run_effect("VAL_reconcile_supply_crisis")
        self.assertIn("VAL_vorkerland_metal_shortage", self.installed_ideas)
        self.assertEqual(self.dirty, dirty, "A healthy shortage consumer must not dirty the economy every week")

    def test_reconcile_repairs_missing_metal_shortage_during_supply_crisis(self):
        self.facts[("VAL", "has_country_flag", "VAL_vorkerland_contracts_disrupted")] = True
        self.variables.update(VAL_economic_recovery_steps=2, VAL_arsenal_reputation_stage=0)
        self.run_effect("VAL_reconcile_supply_crisis")
        self.assertIn("VAL_vorkerland_metal_shortage", self.installed_ideas)
        self.assertTrue(self.facts.get(("VAL", "has_country_flag", "VAL_westerholm_metal_lost"), False))

    def test_reputation_and_resource_loss_are_once_only(self):
        for flag in ("VAL_vorkerland_resource_access_active", "VAL_westerholm_resource_rights_active"):
            self.facts[("VAL", "has_country_flag", flag)] = True
        self.variables["VAL_arsenal_reputation_stage"] = 4
        self.run_effect("VAL_handle_vorkerland_war_outbreak")
        self.assertEqual(set(self.removed_rights), {"33", "38", "202"})
        self.assertEqual(self.variables["VAL_arsenal_reputation_stage"], 0)
        self.assertAlmostEqual(self.variables["VAL_arsenal_trade"], -.20)
        for stage in range(1, 6):
            self.run_effect("VAL_restore_arsenal_reputation")
            snapshot = dict(self.variables)
            self.run_effect("VAL_handle_vorkerland_war_outbreak")
            self.assertEqual(self.variables, snapshot)
            self.assertEqual(len(self.removed_rights), 3)
            self.assertEqual(self.variables["VAL_arsenal_quality"], .10 if stage == 5 else 0)
        self.assertAlmostEqual(self.variables["VAL_arsenal_trade"], .05)
        self.assertAlmostEqual(self.variables["VAL_arsenal_credit"], .025)

    def test_final_recovery_and_veterans_require_actual_victory(self):
        text = FOCUSES_PATH.read_text(encoding="utf-8-sig")
        for focus_id in ("VAL_Reopen_Trade_Routes", "VAL_Settle_Industrial_Debts", "VAL_Return_To_World_Market", "VAL_Veterans_Of_The_Campaign"):
            focus = next(f for f in named_blocks(text, "focus") if f"id = {focus_id}" in f)
            self.assertIn("VAL_campaign_objectives_met = yes", only_named_block(self, focus, "available"))
            self.assertIn("cancel_if_invalid = yes", focus)
        final = next(f for f in named_blocks(text, "focus") if "id = VAL_Return_To_World_Market" in f)
        self.assertIn("prerequisite = { focus = VAL_Returning_Buyers }", final)
        self.assertIn("set_country_flag = VAL_economic_recovery_completed", final)
        self.assertLess(final.index("set_country_flag = VAL_economic_recovery_completed"),
                        final.index("VAL_advance_economic_recovery = yes"))

    def test_starting_commanders_and_trait_are_earned(self):
        history = (ROOT / "history/countries/VAL - ValeraLand.txt").read_text(encoding="utf-8-sig")
        characters = (ROOT / "common/characters/VAL.txt").read_text(encoding="utf-8-sig")
        focus_text = FOCUSES_PATH.read_text(encoding="utf-8-sig")
        for name in ("Kirill_Voron", "Erika_Stahl", "Boris_Gromov", "Renata_Morn"):
            definition = only_named_block(self, characters, "VAL_" + name)
            self.assertRegex(definition, r"(?m)^\s*skill = 2$")
            self.assertIn("recruit_character = VAL_" + name, history)
        unlocks = {"Aleksei_Veyr": "VAL_Contractor_Officers", "Maksim_Korvin": "VAL_Army_Of_The_Ledger",
                   "Dmitri_Karsov": "VAL_Contract_General_Staff", "Leonid_Vargan": "VAL_New_Supply_Base",
                   "Sergei_Volkov": "VAL_Veterans_Of_The_Campaign"}
        for name, focus_id in unlocks.items():
            self.assertNotIn("recruit_character = VAL_" + name, history)
            focus = next(f for f in named_blocks(focus_text, "focus") if f"id = {focus_id}" in f)
            self.assertIn("recruit_character = VAL_" + name, focus)
        self.assertNotIn("The_Weaponry_Baron", only_named_block(self, characters, "VAL_Valera_Solgalov"))
        baron = next(f for f in named_blocks(focus_text, "focus") if "id = VAL_The_Weaponry_Baron" in f)
        self.assertIn("VAL_Valera_Solgalov = { add_country_leader_trait", baron)
        self.assertIn("trait = The_Weaponry_Baron", baron)
        self.assertNotIn("VAL_worldwide_famous_weponry", history)


class ValNorthernExportTests(unittest.TestCase):
    def test_finance_answers_revalidate_and_consume_the_receipt_once(self):
        from tools.validators.validate_adiscord_division_templates import parse_clausewitz
        from tools.tests.test_adiscord_stp_preparation import block

        effects = parse_clausewitz(EFFECTS_PATH.read_text(encoding="utf-8-sig"))
        for buyer in ("CIN", "OSF"):
            receipt = f"VAL_operation_finance_{buyer.lower()}_contacts"
            for outcome in ("accept", "war", "gone", "capitulated", "seller_capitulated", "cap", "refuse"):
                with self.subTest(buyer=buyer, outcome=outcome):
                    flags = {receipt, "VAL_foreign_operation_active"}
                    cash, influence = 0, (3 if outcome == "cap" else 0)

                    def condition(item, scope="VAL"):
                        key, value = item.key, item.value
                        if key == "NOT":
                            return not any(condition(child, scope) for child in value)
                        if key == buyer:
                            return all(condition(child, buyer) for child in value)
                        if key == "has_country_flag":
                            return value in flags
                        if key == "exists":
                            return scope != buyer or outcome != "gone"
                        if key == "has_capitulated":
                            return not (outcome == "capitulated" and scope == buyer or
                                        outcome == "seller_capitulated" and scope == "VAL")
                        if key == "has_war_with":
                            return outcome == "war"
                        if key == "check_variable":
                            return influence >= 3
                        self.fail(f"Unmodelled finance condition: {key}")

                    def execute(items):
                        nonlocal cash, influence
                        matched = False
                        for item in items:
                            key, value = item.key, item.value
                            if key == "if":
                                matched = all(condition(child) for child in block(value, "limit"))
                                if matched:
                                    execute([child for child in value if child.key != "limit"])
                            elif key == "else":
                                if not matched:
                                    execute(value)
                            elif key == "add_to_variable":
                                influence += 1
                            elif key == "ADISCORD_economy_receive_50":
                                cash += 50
                            elif key == "clr_country_flag":
                                flags.discard(value)
                            elif key.startswith("VAL_refuse_finance_"):
                                execute(block(effects, key))
                            elif key not in ("clamp_variable", "VAL_refresh_contract_modifier", "ADISCORD_economy_mark_dirty"):
                                self.fail(f"Unmodelled finance effect: {key}")

                    callback = block(effects, f"VAL_{'refuse' if outcome == 'refuse' else 'accept'}_finance_{buyer.lower()}")
                    execute(callback)
                    self.assertEqual(influence, 1 if outcome == "accept" else 3 if outcome == "cap" else 0)
                    self.assertEqual(cash, 0 if outcome == "accept" else 50)
                    self.assertFalse(flags)
                    settled = cash, influence
                    execute(callback)
                    self.assertEqual((cash, influence), settled)
                    self.assertFalse(flags)

    def test_custom_prices_include_native_blocked_and_hover_suffixes(self):
        sources = (LOCALISATION_PATH, ROOT / "localisation/russian/politics_l_russian.yml")
        values = dict(entry for path in sources for entry in re.findall(
            r'^ ([\w.]+):(?:[0-9]+)?\s*"(.*)"$', path.read_text(encoding="utf-8-sig"), re.M
        ))
        price_keys = set(re.findall(r"custom_cost_text\s*=\s*(\w+)", DECISIONS_PATH.read_text(encoding="utf-8-sig")))
        for key in price_keys:
            with self.subTest(price=key):
                self.assertIn(key + "_blocked", values)
                self.assertIn(key + "_tooltip", values)
                self.assertEqual(values[key + "_blocked"], values[key].replace("§Y", "§R"))
                self.assertIn(values[key], values[key + "_tooltip"])
                self.assertEqual(re.findall(r"£\w+", values[key]), re.findall(r"£\w+", values[key + "_blocked"]))


    def test_export_focuses_feed_one_abstract_arms_market(self):
        from tools.tests.test_adiscord_stp_preparation import block, parse_clausewitz, scalar, walk
        focuses = {scalar(e.value, "id"): e.value for e in walk(parse_clausewitz(FOCUSES_PATH.read_text(encoding="utf-8")))
                   if e.key == "focus" and isinstance(e.value, list)}
        expectations = {"VAL_Foreign_Broker_Licences": ["VAL_sell_surplus_arms_market"],
                        "VAL_Northern_Clearing_House": [],
                        "VAL_Contingency_Ledgers": []}
        sales = block(parse_clausewitz(DECISIONS_PATH.read_text(encoding="utf-8")), "VAL_foreign_sales")
        for focus, unlock in expectations.items():
            reward = block(focuses[focus], "completion_reward")
            self.assertFalse(any(e.key == "set_country_flag" for e in walk(reward)))
            self.assertEqual([scalar(e.value, "decision") if isinstance(e.value, list) else e.value
                              for e in reward if e.key == "unlock_decision_tooltip"], unlock)
            for decision_id in unlock:
                self.assertTrue(block(block(sales, decision_id), "visible"))

        for focus_id, tooltip in (
            ("VAL_Bulk_Arms_Contracts", "VAL_abstract_arms_upgrade_50k_tt"),
            ("VAL_Army_Arsenal_Orders", "VAL_abstract_arms_upgrade_100k_tt"),
            ("VAL_Strategic_Arms_Exports", "VAL_abstract_arms_upgrade_200k_tt"),
        ):
            reward = block(focuses[focus_id], "completion_reward")
            self.assertIn(tooltip, [e.value for e in reward if e.key == "custom_effect_tooltip"])

        for legacy in ("VAL_quarterly_partner_supply", "VAL_ready_partner_supply", "VAL_partner_contract"):
            visible = block(block(sales, legacy), "visible")
            self.assertEqual([(e.key, e.value) for e in visible], [("always", "no")])

        market = block(sales, "VAL_sell_surplus_arms_market")
        self.assertFalse(any(e.key in {"targets", "target_trigger"} for e in market))
        complete = block(market, "complete_effect")
        market_text = named_block_spans(DECISIONS_PATH.read_text(encoding="utf-8"), "VAL_sell_surplus_arms_market")[0].text
        for amount, price in ((25000,500),(50000,1000),(100000,2250),(200000,5000)):
            self.assertIn(f"amount = {amount}", market_text)
            self.assertIn(f"value = {price}", market_text)
        self.assertIn("VAL_record_instant_export = yes", market_text)

        triggers = (ROOT / "common/scripted_triggers/ADISCORD_VAL_rework_triggers.txt").read_text(encoding="utf-8")
        self.assertIn("has_completed_focus = VAL_Northern_Clearing_House", named_block_spans(triggers, "VAL_export_slot_free")[0].text)
        buyer = named_block_spans(triggers, "VAL_abstract_arms_buyer")[0].text
        self.assertIn("NOT = { has_war_with = VAL }", buyer)
        for tag in ("CIN","OSF","APH","COF","TFF","YPR","WRK","WKR","VAD","TVA","STP","STS","SRP","NOD"):
            self.assertIn(f"tag = {tag}", buyer)
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
        decisions = block(parse_source(DECISIONS_PATH), "VAL_military_operations") + block(parse_source(DECISIONS_PATH), "VAL_foreign_sales")
        scripted_loc = parse_source(ROOT / "common/scripted_localisation/ADISCORD_VAL_contract_scripted_loc.txt")
        displayed_numbers = {}
        for language in ("russian", "english"):
            localisation = (ROOT / f"localisation/{language}/ADISCORD_VAL_decisions_l_{language}.yml").read_text(encoding="utf-8-sig")
            displayed_numbers[language] = {
                key: int(value) for key, value in re.findall(
                    r'^\s*(VAL_EXPORT_(?:RIFLES|INCOME)_\w+):\d*\s*"(\d+)"', localisation, re.M
                )
            }
        self.assertEqual(displayed_numbers["russian"], displayed_numbers["english"])
        helpers = {entry.key: entry.value for entry in effects}
        event_by_id = {}
        for entry in parse_source(ROOT / "events/ADISCORD_VAL_contract_events.txt"):
            if entry.key == "country_event" and isinstance(entry.value, list):
                event_id = next((child.value for child in entry.value if child.key == "id"), None)
                if event_id:
                    event_by_id[event_id] = entry.value
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
                for initial, profile in product(((0, 25000), (1000, 25000), (25000, 0), (1000, 23999.5),
                                                  (0, 50000), (1000, 49000), (1000, 48999.5), (50000, 0)), profiles):
                    for settlement in ("expiry", "cancel"):
                        for outcome in ("success", "third_party_war", "war", "gone", "capitulated", "seller_capitulated", "busy", "poor_pp", "prewar", "pregone", "precapitulated", "cap", "poor_cash", "both_gone", "both_war", "both_capitulated", "backup_gone"):
                            with self.subTest(kind=kind, buyer=buyer, stock=initial, outcome=outcome, settlement=settlement, profile=profile):
                                stocks = {tag: {producer: 0.0 for producer in tags} for tag in tags}
                                stocks["VAL"].update(VAL=initial[0], STP=initial[1])
                                values = {tag: {} for tag in tags}
                                flags = {tag: set() for tag in tags}
                                flag_values = {tag: {} for tag in tags}
                                focuses = set(profile[0])
                                quantity = 50000 if licences in focuses else 25000
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
                                        elif key in ("effect_tooltip", "custom_effect_tooltip", "name", "ai_chance", "trigger"): pass
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
                                        elif key == "VAL_pay_contract_rifles":
                                            # Old-source RED: account for the already tested immediate payment API.
                                            flags[scope].discard("VAL_contract_rifles_paid")
                                            amount = values[scope]["VAL_contract_rifle_cost"]
                                            if sum(stocks[scope].values()) >= amount:
                                                for producer in tags:
                                                    debit = min(stocks[scope][producer], amount)
                                                    stocks[scope][producer] -= debit; amount -= debit
                                                flags[scope].add("VAL_contract_rifles_paid")
                                        elif key == "country_event":
                                            event_id = value if isinstance(value, str) else fields(item)["id"]
                                            accept = next(child for child in event_by_id[event_id] if child.key == "option")
                                            execute(accept.value, scope, previous)
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
                                            key = next(e.value for e in text if e.key == "localization_key")
                                            return displayed_numbers["russian"][key]
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
    def test_shabrat_prices_match_offer_and_settlement(self):
        from tools.tests.test_adiscord_stp_preparation import block, scalar, walk
        from tools.validators.validate_adiscord_division_templates import parse_clausewitz
        decisions = DECISIONS_PATH.read_text(encoding="utf-8-sig")
        effects = EFFECTS_PATH.read_text(encoding="utf-8-sig")
        events = (ROOT / "events/ADISCORD_STP_events.txt").read_text(encoding="utf-8-sig")
        offer = next(e.value for e in parse_clausewitz(events) if e.key == "country_event" and scalar(e.value, "id") == "ADISCORD_STP_cw.50")
        for decision, option, price in (("VAL_cw_sell_arms_to_resistance", "ADISCORD_STP_cw.50.a", 500), ("VAL_cw_offer_contract_formations", "ADISCORD_STP_cw.50.c", 1000)):
            gate = next(e.value for e in offer if e.key == "option" and scalar(e.value, "name") == option)
            decision_block = only_named_block(self, decisions, decision)
            available = block(parse_clausewitz(decision_block)[0].value, "available")
            if price == 500:
                self.assertFalse(any(e.key == "ADISCORD_economy_can_spend_500" for e in walk(available)))
                self.assertTrue(any(e.key == "ADISCORD_economy_can_spend_500" for e in walk(block(gate, "trigger"))))
            else:
                self.assertFalse(any(e.key == "check_variable" and scalar(e.value, "var") == "ADISCORD_economy_treasury" and scalar(e.value, "value") == "1000" for e in walk(available)))
                self.assertTrue(any(e.key == "check_variable" and scalar(e.value, "var") == "ADISCORD_economy_treasury" and scalar(e.value, "value") == "1000" for e in walk(block(gate, "trigger"))))
        payment = only_named_block(self, effects, "VAL_cw_complete_arms_contract")
        self.assertIn("ADISCORD_economy_spend_500 = yes ADISCORD_economy_spend_500 = yes", payment)
        resolver = only_named_block(self, (ROOT / "common/scripted_effects/ADISCORD_STP_scripted_effects.txt").read_text(encoding="utf-8"), "STP_ps_resolve_val_supply")
        self.assertIn("value = STP_ps_val_receipt_money", resolver)
        self.assertIn("var = ADISCORD_economy_treasury value = STP_ps_cargo_payment", resolver)

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
            ("VAL_cw_sell_arms_to_resistance", "1", "ADISCORD_STP_cw.50.a", "500", None, "32000"),
            ("VAL_cw_offer_contract_formations", "2", "ADISCORD_STP_cw.50.c", "1000", "12600", "43340"),
        ):
            decision = decisions[decision_id]
            pending = next(e.value for e in walk(block(decision, "complete_effect"))
                           if e.key == "set_country_flag" and isinstance(e.value, list)
                           and scalar(e.value, "flag") == "VAL_cw_arms_offer_pending")
            self.assertEqual((scalar(pending, "value"), scalar(pending, "days")), (tier, "35" if tier == "2" else "21"))
            decision_gate = block(decision, "available")
            acceptance_gate = block(options[option_id], "trigger")
            if treasury == "1000":
                self.assertFalse(any(e.key == "check_variable" and scalar(e.value, "var") == "ADISCORD_economy_treasury" and scalar(e.value, "value") == treasury for e in walk(decision_gate)))
                self.assertTrue(any(e.key == "check_variable" and scalar(e.value, "var") == "ADISCORD_economy_treasury" and scalar(e.value, "value") == treasury and scalar(e.value, "compare") == "greater_than_or_equals" for e in walk(acceptance_gate)))
            else:
                self.assertFalse(any(e.key == f"ADISCORD_economy_can_spend_{treasury}" for e in walk(decision_gate)))
                self.assertTrue(any(e.key == f"ADISCORD_economy_can_spend_{treasury}" for e in walk(acceptance_gate)))
            decision_text = only_named_block(self, DECISIONS_PATH.read_text(encoding="utf-8-sig"), decision_id)
            if manpower is None:
                self.assertNotIn("has_manpower", decision_text)
            else:
                self.assertIn(f"has_manpower < {manpower}", decision_text)
            for gate in (decision_gate, acceptance_gate):
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
            (effects, "VAL_pay_contract_rifles"),
            *[(rifle_effects, name) for name in ("STP_ps_dispatch_val_supply", "STP_ps_resolve_val_supply",
              "STP_ps_clear_val_receipt", "STP_ps_deliver_val_contract", "STP_ps_refund_val_supply")])}
        self.assertTrue(scripts["VAL_cw_pay_contract_auxiliary"])
        subunits = {entry.key: entry.value for entry in block(parse_clausewitz(
            (ROOT / "common/units/ADISCORD_land_units.txt").read_text(encoding="utf-8-sig")), "sub_units")}
        rifle, squad, support = "infantry_equipment", "ADISCORD_squad_weapons_equipment", "support_equipment"
        full_equipment = {rifle: 43340, squad: 96, support: 60}
        for tier in (1, 2, 3, 99):
            full = tier > 1
            price, people = (1000, 12600) if full else (500, 0)
            required = full_equipment if full else {rifle: 32000, squad: 0, support: 0}
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
                    flags = {("VAL", "VAL_cw_trade_course"): 1, ("VAL", "VAL_contract_rifles_paid"): 1}
                    if scenario != "stale":
                        flags[("VAL", "VAL_cw_arms_offer_pending")] = tier
                    variables, templates = {}, {}
                    previous_scope = [None]
                    missions = set()
                    field_equipment = defaultdict(float)
                    field_people = units = experience_rewards = authority_rewards = 0
                    def number(value, scope):
                        value = value.removeprefix("var:")
                        if value == "ADISCORD_economy_treasury":
                            return cash[scope]
                        if value.startswith("PREV."):
                            return variables[(previous_scope[0], value[5:])]
                        if value.startswith("num_equipment@"):
                            return sum(stock[scope][value.split("@", 1)[1]].values())
                        try:
                            return float(value)
                        except ValueError:
                            return variables.get((scope, value), 0)
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
                            if key in ("VAL", "STS", "STP", "PREV"):
                                results.append(conditions(entry.value, previous if key == "PREV" else key, scope))
                            elif key in ("OR", "AND", "NOT"):
                                if key == "OR":
                                    results.append(any(conditions([e], scope, previous) for e in entry.value))
                                elif key == "NOT":
                                    results.append(not conditions(entry.value, scope, previous))
                                else:
                                    results.append(conditions(entry.value, scope, previous))
                            elif key == "has_variable":
                                results.append((scope, entry.value) in variables)
                            elif key in ("STP_ps_val_supply_open", "STP_ps_val_land_route"):
                                # This matrix exercises a live, connected STS front; route loss is tested separately.
                                results.append(entry.value == "yes")
                            elif key == "has_country_flag":
                                if isinstance(entry.value, str):
                                    results.append((scope, entry.value) in flags)
                                else:
                                    name = scalar(entry.value, "flag")
                                    field, operator, amount = [e.value for e in entry.value if not e.key]
                                    self.assertEqual(field, "value")
                                    results.append((scope, name) in flags and compare(flags[(scope, name)], operator, float(amount)))
                            elif key == "check_variable":
                                operators = {"equals": "=", "greater_than": ">", "greater_than_or_equals": ">=", "less_than": "<"}
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
                        previous_scope[0] = previous
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
                            elif key in ("VAL", "STS", "STP", "PREV"):
                                execute(entry.value, previous if key == "PREV" else key, scope)
                            elif key == "every_possible_country":
                                for creator in ("VAL", "NOD", "STS"):
                                    if conditions(block(entry.value, "limit"), creator, scope):
                                        execute([e for e in entry.value if e.key != "limit"], creator, scope)
                            elif key in ("set_variable", "add_to_variable", "set_temp_variable", "multiply_temp_variable", "subtract_from_temp_variable"):
                                variable, value = scalar(entry.value, "var"), number(scalar(entry.value, "value"), scope)
                                if variable == "ADISCORD_economy_treasury" and key == "add_to_variable":
                                    cash[scope] += value
                                elif key in ("set_temp_variable", "set_variable"):
                                    variables[(scope, variable)] = value
                                elif key == "add_to_variable":
                                    variables[(scope, variable)] = variables.get((scope, variable), 0) + value
                                elif key == "multiply_temp_variable":
                                    variables[(scope, variable)] *= value
                                else:
                                    variables[(scope, variable)] -= value
                            elif key == "clear_variable":
                                variables.pop((scope, entry.value), None)
                            elif key == "activate_mission":
                                missions.add((scope, entry.value))
                            elif key == "remove_mission":
                                missions.discard((scope, entry.value))
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
                            elif key not in ("log", "country_event", "ADISCORD_economy_mark_dirty"):
                                self.fail(f"Unsupported contract operation: {key}")
                    execute(scripts["VAL_cw_complete_arms_contract"])
                    paid = scenario in ("exact", "mixed")
                    self.assertEqual(units, 0, "No formation before its paid convoy arrives")
                    self.assertEqual(cash["VAL"], 0, "The donor is paid only at settlement")
                    self.assertEqual(sum(stock["STS"][rifle].values()), 0)
                    self.assertEqual(("VAL", "STP_ps_val_departure") in missions, paid)
                    execute(scripts["STP_ps_dispatch_val_supply"])
                    self.assertNotIn(("VAL", "STP_ps_val_receipt_rifles"), variables)
                    self.assertEqual(("VAL", "VAL_cw_arms_contract_fulfilled") in flags, paid)
                    self.assertEqual(units, 2 if paid and full else 0)
                    self.assertEqual(field_people, 12600 if paid and full else 0)
                    self.assertEqual(dict(field_equipment), {rifle: 11340, squad: 96, support: 60} if paid and full else {})
                    self.assertEqual(manpower["STS"], 0)
                    self.assertEqual(sum(stock["STS"][rifle].values()), 32000 if paid else 0)
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
                    execute(scripts["STP_ps_dispatch_val_supply"])
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
                elif k == "remove_dynamic_modifier":
                    modifiers.discard((scope, scalar(v, "modifier")))
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
            state_modifiers = {modifier for state, modifier in modifiers if state == 24}
            self.assertEqual(state_modifiers, {f"VAL_reclamation_stage_{stage}_modifier"})
            self.assertNotIn((24, "ADISCORD_vorkerland_dirty_state"), modifiers)
            self.assertNotIn((24, "VAL_reclamation_recovered_land"), modifiers)
        self.assertEqual(buildings[(24, "infrastructure")], 3)
        self.assertEqual(buildings[(24, "slots")], 3)
        self.assertEqual(buildings[(24, "industrial_complex")], 1)
        call("begin_project")
        self.assertNotIn(("VAL", "VAL_reclamation_deposit"), values)
        for legacy in ("VAL_reclamation_people", "VAL_reclamation_resources", "VAL_reclamation_slots",
                       "VAL_reclamation_construction", "VAL_reclamation_supply"):
            self.assertNotIn((24, legacy), values)
        self.assertEqual({modifier for state, modifier in modifiers if state == 24},
                         {"VAL_reclamation_stage_3_modifier"})
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
    def test_workshop_receipts_survive_parallel_targets_and_settle_once(self):
        from collections import defaultdict
        from tools.tests.test_adiscord_stp_preparation import block, parse_clausewitz, scalar
        definitions = {e.key: e.value for e in parse_clausewitz(EFFECTS_PATH.read_text(encoding="utf-8"))}
        definitions.update({e.key: e.value for e in parse_clausewitz((ROOT / "common/scripted_effects/ADISCORD_shared_action_effects.txt").read_text(encoding="utf-8"))})
        variables = defaultdict(float, {("VAL", "ADISCORD_economy_treasury"): 1500})
        valid = {58: True, 61: True}
        owners = {58: "VAL", 61: "OSF"}
        factories, slots, dirty = defaultdict(int), defaultdict(int), set()
        target = 58

        def gate(rows, scope):
            results = []
            for e in rows:
                k, v = e.key, e.value
                if k == "FROM":
                    ok = gate(v, target)
                elif k == "NOT":
                    ok = not any(gate([item], scope) for item in v)
                elif k == "has_variable":
                    ok = (scope, v) in variables
                elif k == "check_variable":
                    self.assertEqual(scalar(v, "compare"), "equals")
                    ok = variables.get((scope, scalar(v, "var")), 0) == float(scalar(v, "value"))
                elif k == "ADISCORD_economy_can_spend_500":
                    ok = variables[scope, "ADISCORD_economy_treasury"] >= 500
                elif k == "VAL_frontier_workshop_target_valid":
                    ok = valid[target]
                else:
                    self.fail("Unsupported workshop payment condition: " + k)
                results.append(ok)
            return all(results)

        def execute(rows, scope="VAL"):
            taken = False
            for e in rows:
                k, v = e.key, e.value
                if k == "if":
                    taken = gate(block(v, "limit"), scope)
                    if taken:
                        execute([x for x in v if x.key != "limit"], scope)
                elif k == "else":
                    if not taken:
                        execute(v, scope)
                elif k == "FROM":
                    execute(v, target)
                elif k == "owner":
                    execute(v, owners[scope])
                elif k in ("set_variable", "add_to_variable"):
                    key = scope, scalar(v, "var")
                    amount = float(scalar(v, "value"))
                    variables[key] = amount if k == "set_variable" else variables[key] + amount
                elif k == "clear_variable":
                    variables.pop((scope, v), None)
                elif k == "add_extra_state_shared_building_slots":
                    slots[scope] += int(v)
                elif k == "add_building_construction":
                    self.assertEqual(scalar(v, "type"), "arms_factory")
                    self.assertEqual(scalar(v, "instant_build"), "yes")
                    factories[scope] += int(scalar(v, "level"))
                elif k == "ADISCORD_economy_mark_dirty":
                    dirty.add(scope)
                elif k == "ADISCORD_economy_initialize_country":
                    pass  # The fixture starts with an initialized treasury.
                elif k in definitions:
                    execute(definitions[k], scope)
                else:
                    self.fail("Unsupported workshop payment effect: " + k)

        def call(suffix):
            execute(definitions["VAL_frontier_" + suffix + "_workshop"])

        call("begin")
        call("begin")
        self.assertEqual(variables["VAL", "ADISCORD_economy_treasury"], 1000)
        target = 61
        call("begin")
        self.assertEqual(variables[58, "VAL_frontier_workshop_deposit"], 500)
        self.assertEqual(variables[61, "VAL_frontier_workshop_deposit"], 500)
        target = 58
        valid[target] = False
        call("finish")
        call("refund")
        self.assertEqual(variables["VAL", "ADISCORD_economy_treasury"], 1000)
        self.assertEqual(factories[58], 0)
        target = 61
        call("finish")
        call("finish")
        call("refund")
        self.assertEqual((factories[61], slots[61]), (1, 1))
        self.assertEqual(variables["VAL", "ADISCORD_economy_treasury"], 1000)
        self.assertEqual(variables["VAL", "ADISCORD_economy_current_month_action_costs"], 1000)
        self.assertEqual(variables["VAL", "ADISCORD_economy_current_month_action_income"], 500)
        self.assertIn("OSF", dirty)
        self.assertNotIn((61, "VAL_frontier_workshop_deposit"), variables)
        variables["VAL", "ADISCORD_economy_treasury"] = 499.99
        call("begin")
        self.assertNotIn((61, "VAL_frontier_workshop_deposit"), variables)

    def test_all_enrolled_tribes_must_fall_and_liberation_reopens_the_war(self):
        from itertools import product
        from tools.tests.test_adiscord_stp_preparation import block, parse_clausewitz
        triggers = parse_clausewitz((ROOT / "common/scripted_triggers/ADISCORD_VAL_rework_triggers.txt").read_text(encoding="utf-8"))
        gate = block(triggers, "VAL_frontier_members_beaten")
        tags = ("CIN", "OSF", "APH")
        capitals = ("58", "61", "64")
        for joined in product((False, True), repeat=3):
            for defeated in product((False, True), repeat=3):
                facts = {}
                for tag, capital, member, lost in zip(tags, capitals, joined, defeated):
                    facts[tag, "has_country_flag", "VAL_frontier_member"] = member
                    facts[tag, "has_country_flag", "VAL_frontier_defeated"] = lost
                    facts[tag, "capital"] = capital
                    facts[capital, "is_controlled_by", "VAL"] = lost
                with self.subTest(joined=joined, defeated=defeated):
                    expected = all(not member or lost for member, lost in zip(joined, defeated))
                    self.assertEqual(self.frontier_matches(gate, facts), expected)
                    for tag, capital, member in zip(tags, capitals, joined):
                        if expected and member:
                            liberated = {**facts, (capital, "is_controlled_by", "VAL"): False}
                            self.assertFalse(self.frontier_matches(gate, liberated))

    def test_capitulation_handler_reserves_each_member_not_just_the_addressee(self):
        from tools.tests.test_adiscord_stp_preparation import block, parse_clausewitz, walk
        actions = block(parse_clausewitz(read_country_on_actions(ON_ACTIONS_PATH, 'kefreyt')), "on_actions")
        immediate = block(block(actions, "on_capitulation_immediate"), "effect")
        handler = next(e.value for e in immediate if e.key == "if" and any(x.key == "set_country_flag" and isinstance(x.value, list) and any(f.key == "flag" and f.value == "VAL_frontier_capitulation_pending" for f in x.value) for x in e.value))
        for target in (1, 2, 3):
            for tag in ("CIN", "OSF", "APH"):
                facts = {
                    ("VAL", "variable", "VAL_frontier_stage"): 3,
                    ("VAL", "variable", "VAL_frontier_target"): target,
                    (tag, "has_country_flag", "VAL_frontier_member"): True,
                    (tag, "has_war_with", "VAL"): True,
                    (tag, "capital"): "999",
                    ("999", "is_controlled_by", "VAL"): True,
                }
                self.assertTrue(self.frontier_matches(block(handler, "limit"), facts, tag))
                self.assertFalse(self.frontier_matches(block(handler, "limit"), {**facts, ("999", "is_controlled_by", "VAL"): False}, tag))
        effects = parse_clausewitz(EFFECTS_PATH.read_text(encoding="utf-8"))
        weekly = list(walk(block(effects, "VAL_frontier_reconcile")))
        self.assertTrue(any(e.key == "VAL_frontier_members_beaten" and e.value == "yes" for e in weekly))

    def test_same_war_calls_and_cleanup_cover_all_actual_members(self):
        from tools.tests.test_adiscord_stp_preparation import block, parse_clausewitz, scalar, walk
        effects = parse_clausewitz(EFFECTS_PATH.read_text(encoding="utf-8"))
        calls = block(effects, "VAL_frontier_call_members")
        for tag in ("CIN", "OSF", "APH"):
            member = block(calls, tag)
            entry = next(e.value for e in member if e.key == "if")
            call = block(entry, "add_to_war")
            self.assertEqual(scalar(call, "targeted_alliance"), "event_target:VAL_frontier_war_target")
            self.assertEqual(scalar(call, "enemy"), "VAL")
            self.assertEqual(scalar(call, "single_target_only"), "yes")
            self.assertEqual(scalar(block(entry, "limit"), "is_in_faction_with"), "event_target:VAL_frontier_war_target")
            closing = block(effects, "VAL_frontier_close")
            tagged = [e for e in closing if e.key == tag]
            self.assertTrue(any(e.key == "white_peace" for e in walk(tagged)))
            self.assertTrue(any(e.key == "clr_country_flag" and e.value == "VAL_frontier_member" for e in walk(tagged)))
            self.assertTrue(any(e.key == "set_major" and e.value == "no" for e in walk(tagged)))

    def test_ai_tribes_refuse_but_eastern_territory_can_negotiate(self):
        from tools.tests.test_adiscord_stp_preparation import block, parse_clausewitz, scalar, matches_conditions
        events = parse_clausewitz((ROOT / "events/ADISCORD_VAL_contract_events.txt").read_text(encoding="utf-8"))
        offer = next(e.value for e in events if e.key == "country_event" and scalar(e.value, "id") == "val_rework.110")
        accept = next(e.value for e in offer if e.key == "option" and scalar(e.value, "name") == "val_rework.110.yes")
        chance = block(accept, "ai_chance")
        zero = next(e.value for e in chance if e.key == "modifier" and scalar(e.value, "factor") == "0")
        for tag in ("CIN", "OSF", "APH", "ERT"):
            self.assertEqual(matches_conditions([e for e in zero if e.key != "factor"], {}, tag), tag != "ERT")

    def test_transport_price_exact_boundaries_and_one_debit(self):
        from tools.tests.test_adiscord_stp_preparation import block, parse_clausewitz, scalar, walk
        decisions = block(parse_clausewitz(DECISIONS_PATH.read_text(encoding="utf-8")), "VAL_military_operations")
        contract = block(decisions, "VAL_frontier_transport_contract")
        self.assertEqual(scalar(contract, "cost"), "0")
        price = block(contract, "custom_cost_trigger")
        equipment = block(block(price, "NOT"), "has_equipment")
        # Evaluate the authored comparison at fractional and exact stock levels.
        tokens = [e.value for e in equipment]
        self.assertEqual(tokens, ["motorized_equipment", "<", "100"])
        for stock, expected in ((99, False), (99.9, False), (100, True), (100.1, True)):
            self.assertEqual(not stock < float(tokens[2]), expected)
        paid = list(walk(block(contract, "complete_effect")))
        self.assertEqual(sum(e.key == "ADISCORD_economy_spend_50" for e in paid), 1)
        debit = next(e.value for e in paid if e.key == "add_equipment_to_stockpile")
        self.assertEqual(scalar(debit, "amount"), "-100")
        effects = parse_clausewitz(EFFECTS_PATH.read_text(encoding="utf-8"))
        self.assertTrue(any(e.key == "remove_ideas" and e.value == "VAL_frontier_transport_columns" for e in block(effects, "VAL_frontier_close")))

    def test_coalition_membership_preserves_old_alliances_and_cleans_only_receipts(self):
        from tools.tests.test_adiscord_stp_preparation import parse_clausewitz, scalar
        definitions = {entry.key: entry.value for entry in parse_clausewitz(EFFECTS_PATH.read_text(encoding="utf-8"))}

        triggers = {e.key: e.value for e in parse_clausewitz((ROOT / "common/scripted_triggers/ADISCORD_VAL_rework_triggers.txt").read_text(encoding="utf-8"))}
        minor_effects = parse_clausewitz((ROOT / "common/scripted_effects/ADISCORD_minor_optimization_effects.txt").read_text(encoding="utf-8"))
        definitions.update({e.key: e.value for e in minor_effects})

        def exercise(initial, *, subject=None, external_join=False, recover=False):
            factions = {name: list(members) for name, members in initial.items()}
            original = {name: list(members) for name, members in initial.items()}
            flags = {tag: set() for tag in ("VAL", "CIN", "OSF", "APH", "NOD", "STP", "OTH")}
            flags["STP"].add("STP_cw_won_union_battle")
            variables, targets = {}, {}
            local_targets, wars, majors = set(), set(), set()
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
                        ok = frozenset((current, resolve(v, stack))) in wars
                    elif k == "is_major":
                        ok = (current in majors) == (v == "yes")
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
                    elif k in triggers:
                        self.assertIn(v, ("yes", "no"))
                        ok = condition(triggers[k], stack) == (v == "yes")
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
                    elif k == "save_event_target_as":
                        targets[v] = current
                        local_targets.add(v)
                    elif k == "add_to_war":
                        target = resolve(scalar(v, "targeted_alliance"), stack)
                        enemy = resolve(scalar(v, "enemy"), stack)
                        self.assertIn(frozenset((target, enemy)), wars)
                        self.assertEqual(faction(current), faction(target))
                        wars.add(frozenset((current, enemy)))
                    elif k == "set_major":
                        if v == "yes":
                            majors.add(current)
                        else:
                            majors.discard(current)
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
            if recover:
                wars.update((frozenset(("VAL", "CIN")), frozenset(("VAL", "NOD"))))
                for tag in ("OSF", "APH"):
                    factions[faction(tag)].remove(tag)
                    flags[tag].clear()
                execute(definitions["VAL_frontier_reconcile_members"], ["VAL", "CIN"])
                for tag in ("CIN", "OSF", "APH"):
                    self.assertIn(frozenset(("VAL", tag)), wars)
                    self.assertIn("VAL_frontier_member", flags[tag])
                    self.assertIn(tag, majors)
                flags["OSF"].discard("VAL_frontier_member")
                execute(definitions["VAL_frontier_reconcile_members"], ["VAL", "CIN"])
                self.assertIn("VAL_frontier_member", flags["OSF"])
                snapshot = (repr(factions), repr(flags), set(wars), set(majors))
                execute(definitions["VAL_frontier_reconcile_members"], ["VAL", "CIN"])
                self.assertEqual(snapshot, (repr(factions), repr(flags), set(wars), set(majors)))
            prepared = {tag: faction(tag) for tag in flags}
            if external_join:
                factions[faction("NOD")].append("OTH")
            execute(definitions["VAL_frontier_release_coalition"], ["VAL"])
            after = {name: list(members) for name, members in factions.items()}
            execute(definitions["VAL_frontier_release_coalition"], ["VAL"])
            self.assertEqual(factions, after, "A repeated close must not remove another alliance")
            self.assertFalse(set(targets) - local_targets)
            self.assertFalse(any(flag in {"VAL_frontier_created_coalition", "VAL_frontier_added_to_coalition"} for values in flags.values() for flag in values))
            if not external_join:
                self.assertEqual(factions, original)
            return prepared, factions

        exercise({}, recover=True)
        prepared, _ = exercise({})
        self.assertEqual(prepared["CIN"], prepared["NOD"])
        self.assertEqual(prepared["CIN"], prepared["STP"])
        self.assertEqual(prepared["CIN"], prepared["OSF"])
        self.assertEqual(prepared["CIN"], prepared["APH"])
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
        self.assertIsNotNone(prepared["CIN"], "The tribes must form their own bloc without outside guarantors")
        self.assertEqual(prepared["CIN"], prepared["OSF"])
        self.assertEqual(prepared["CIN"], prepared["APH"])
        self.assertNotEqual(prepared["CIN"], prepared["VAL"])
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
            invitations = block(definitions, "VAL_frontier_join_existing_war")
            invited = next(e.value for e in invitations if e.key == "if" and scalar(block(e.value, "limit"), "has_war_with") == tag)
            self.assertTrue(any(e.key == "VAL_frontier_join_existing_war" for e in walk(start)))
            for guarantor in ("NOD", "STP"):
                call = next(e.value for e in walk(invited) if e.key == "if" and any(c.key == guarantor and any(n.key == "add_to_war" for n in c.value) for c in e.value))
                self.assertEqual(scalar(block(block(call, "limit"), guarantor), "is_in_faction_with"), tag)
                self.assertEqual(scalar(block(block(block(call, "limit"), guarantor), "NOT"), "is_in_faction_with"), "VAL")
                self.assertEqual(scalar(block(block(call, guarantor), "add_to_war"), "single_target_only"), "yes")
        close = list(walk(block(definitions, "VAL_frontier_close")))
        last_peace = max(i for i, e in enumerate(close) if e.key == "white_peace")
        first_major_cleanup = min(i for i, e in enumerate(close) if e.key == "set_major" and e.value == "no")
        coalition_cleanup = next(i for i, e in enumerate(close) if e.key == "VAL_frontier_release_coalition")
        self.assertLess(last_peace, first_major_cleanup)
        self.assertLess(last_peace, coalition_cleanup)

    def test_last_tribe_ends_campaign_without_invading_guarantors(self):
        from itertools import permutations, product
        from tools.tests.test_adiscord_stp_preparation import block, parse_clausewitz, walk
        effects = parse_clausewitz(EFFECTS_PATH.read_text(encoding="utf-8"))
        weekly = block(effects, "VAL_frontier_reconcile")
        gate = next(block(e.value, "limit") for e in walk(weekly)
                    if e.key == "else_if" and any(x.key == "VAL_frontier_settle_victory" for x in e.value))
        for target, order, guarantors, occupier in product(range(1, 4), permutations(("CIN", "OSF", "APH")),
                                                         product((False, True), repeat=2), ("VAL", "SUB")):
            facts = {("VAL", "variable", "VAL_frontier_target"): target,
                     ("SUB", "is_subject_of", "VAL"): True}
            for tag, active in zip(("NOD", "STP"), guarantors):
                facts[tag, "has_country_flag", "VAL_frontier_guarantor"] = active
                facts[tag, "numeric", "surrender_progress"] = 0
            for tag, capital in zip(("CIN", "OSF", "APH"), ("58", "61", "64")):
                facts[tag, "has_country_flag", "VAL_frontier_member"] = True
                facts[tag, "capital"] = capital
            for index, tag in enumerate(order):
                capital = facts[tag, "capital"]
                facts[tag, "has_country_flag", "VAL_frontier_defeated"] = True
                facts[capital, "is_controlled_by", occupier] = True
                facts[capital, "controller"] = occupier
                self.assertEqual(self.frontier_matches(gate, facts), index == 2)
            for tag in order:
                capital = facts[tag, "capital"]
                liberated = {**facts, (capital, "is_controlled_by", occupier): False,
                             (capital, "controller"): tag}
                self.assertFalse(self.frontier_matches(gate, liberated))
        victory = list(walk(block(effects, "VAL_frontier_settle_victory")))
        self.assertFalse(any(e.key == "every_state" for e in victory), "Guarantors pay no territorial indemnity")

    def test_eastern_claim_requires_live_campaign_and_our_control(self):
        from tools.tests.test_adiscord_stp_preparation import block, parse_clausewitz
        source = parse_clausewitz((ROOT / "common/scripted_triggers/ADISCORD_VAL_rework_triggers.txt").read_text(encoding="utf-8"))
        gate = block(source, "VAL_frontier_eastern_claim_ready")
        facts = {("VAL", "exists", "yes"): True, ("VAL", "has_capitulated", "no"): True,
                 ("VAL", "is_subject", "no"): True, ("VAL", "has_war_with", "ERT"): True,
                 ("VAL", "variable", "VAL_frontier_stage"): 3,
                 ("VAL", "variable", "VAL_frontier_target"): 4,
                 ("168", "is_owned_by", "ERT"): True, ("SUB", "is_subject_of", "VAL"): True}
        for controller, expected in (("VAL", True), ("SUB", True), ("RUS", False), ("ERT", False)):
            occupied = {**facts, ("168", "is_controlled_by", controller): True, ("168", "controller"): controller}
            self.assertEqual(self.frontier_matches(gate, occupied), expected)
            for key, value in ((("VAL", "variable", "VAL_frontier_stage"), 0),
                               (("VAL", "has_war_with", "ERT"), False),
                               (("168", "is_owned_by", "ERT"), False),
                               (("VAL", "has_capitulated", "no"), False)):
                self.assertFalse(self.frontier_matches(gate, {**occupied, key: value}))

    def settlement_fixture(self, commissioners=False, eastern=False):
        """Execute the authored territorial settlement; native callback timing needs game QA.

        Coalition enrolment is independently exercised above. This fixture starts
        with its receipts and models bilateral white peace, state transfer and annex.
        UI, economy and character effects are explicitly outside the state model.
        """
        from types import SimpleNamespace
        from tools.tests.test_adiscord_stp_preparation import block, scalar, parse_clausewitz
        fixture = SimpleNamespace()
        fixture.owners = {str(n): t for t, states in (("VAL", (24,)), ("NOD", (70,)),
                          ("CIN", (58, 59, 60)), ("OSF", (61, 62, 63)), ("APH", (64, 65)),
                          ("ERT", (167, 168, 169)), ("RUS", (170,))) for n in states}
        fixture.controllers = dict(fixture.owners)
        fixture.flags = {t: set() for t in ("VAL", "CIN", "OSF", "APH", "ERT", "RUS", "NOD", "STP", "NKA", "SUB")}
        fixture.subjects = {"SUB": "VAL"}
        fixture.vars = {("VAL", "VAL_frontier_stage"): 3, ("VAL", "VAL_frontier_target"): 4 if eastern else 1}
        fixture.capitals = {"CIN": "58", "OSF": "61", "APH": "64", "VAL": "24", "ERT": "167", "NOD": "70"}
        fixture.wars = {frozenset(("VAL", t)) for t in (("ERT",) if eastern else ("CIN", "OSF", "APH", "NOD"))}
        fixture.majors = set()
        fixture.events = []
        fixture.stability = 0
        for tag in (() if eastern else ("CIN", "OSF", "APH")):
            fixture.flags[tag].update(("VAL_frontier_member", "VAL_frontier_added_major"))
            fixture.majors.add(tag)
        if not eastern:
            fixture.flags["NOD"].update(("VAL_frontier_guarantor", "VAL_frontier_added_major"))
            fixture.majors.add("NOD")
        effects = {e.key: e.value for e in parse_clausewitz(EFFECTS_PATH.read_text(encoding="utf-8"))}
        rus = parse_clausewitz((ROOT / "common/scripted_effects/ADISCORD_vorkerland_effects.txt").read_text(encoding="utf-8"))
        effects["ADISCORD_vorkerland_rus_annex_dirty_target"] = block(rus, "ADISCORD_vorkerland_rus_annex_dirty_target")
        def facts():
            result = {}
            for tag in fixture.flags:
                exists = tag in fixture.owners.values()
                result[tag, "exists", "yes"] = exists
                result[tag, "exists", "no"] = not exists
                result[tag, "has_capitulated", "no"] = True
                result[tag, "is_subject", "no"] = tag not in fixture.subjects
                result[tag, "has_war", "yes"] = any(tag in w for w in fixture.wars)
                result[tag, "has_war", "no"] = not result[tag, "has_war", "yes"]
                result[tag, "variable", "num_owned_states"] = sum(t == tag for t in fixture.owners.values())
                result[tag, "owned_states"] = tuple(n for n, t in fixture.owners.items() if t == tag)
                for target in fixture.flags:
                    result[tag, "country_exists", target] = target in fixture.owners.values()
                    result[tag, "has_war_with", target] = frozenset((tag, target)) in fixture.wars
                for flag in fixture.flags[tag]: result[tag, "has_country_flag", flag] = True
            for tag, capital in fixture.capitals.items(): result[tag, "capital"] = capital
            for tag, overlord in fixture.subjects.items(): result[tag, "is_subject_of", overlord] = True
            for (tag, name), value in fixture.vars.items(): result[tag, "variable", name] = value
            for state, owner in fixture.owners.items():
                result[state, "is_owned_by", owner] = True
                result[state, "owner"] = owner
                result[state, "controller"] = fixture.controllers[state]
                result[state, "is_controlled_by", fixture.controllers[state]] = True
            result["VAL", "has_completed_focus", "VAL_frontier_commissioners"] = commissioners
            return result
        def transfer(state, recipient):
            fixture.owners[state] = recipient
            fixture.controllers[state] = recipient
        ignored = {"remove_mission", "remove_ideas", "ADISCORD_economy_mark_dirty", "ADISCORD_economy_initialize_country",
                   "set_cosmetic_tag", "set_politics", "promote_character", "set_rule", "inherit_technology",
                   "add_core_of", "remove_core_of", "VAL_frontier_reconcile_active_members", "VAL_frontier_release_coalition"}
        def execute(rows, scope="VAL"):
            taken = False
            for entry in rows:
                key, value = entry.key, entry.value
                if key in ("if", "else_if", "else"):
                    if key == "if": taken = False
                    if not taken and (key == "else" or self.frontier_matches(block(value, "limit"), facts(), scope)):
                        taken = True
                        execute([e for e in value if e.key != "limit"], scope)
                elif key in fixture.flags or key.isdigit(): execute(value, key)
                elif key in ("hidden_effect",): execute(value, scope)
                elif key in ignored: pass
                elif key in effects: execute(effects[key], scope)
                elif key in ("set_temp_variable", "set_variable"):
                    fixture.vars[scope, scalar(value, "var")] = float(scalar(value, "value"))
                elif key in ("set_country_flag", "clr_country_flag"):
                    flag = scalar(value, "flag") if isinstance(value, list) else value
                    if key == "set_country_flag": fixture.flags[scope].add(flag)
                    else: fixture.flags[scope].discard(flag)
                elif key in ("set_global_flag", "clr_global_flag"): pass
                elif key == "set_major":
                    if value == "yes": fixture.majors.add(scope)
                    else: fixture.majors.discard(scope)
                elif key == "white_peace":
                    fixture.wars.discard(frozenset((scope, value)))
                    for n, owner in fixture.owners.items():
                        if {owner, fixture.controllers[n]} == {scope, value}: fixture.controllers[n] = owner
                elif key == "transfer_state": transfer(value, scope)
                elif key == "set_state_controller_to": fixture.controllers[scope] = value
                elif key == "set_autonomy": fixture.subjects[scalar(value, "target")] = scope
                elif key == "annex_country":
                    target = scalar(value, "target")
                    for n in list(fixture.owners):
                        if fixture.owners[n] == target: transfer(n, scope)
                    fixture.wars = {w for w in fixture.wars if target not in w}
                elif key == "set_capital": fixture.capitals[scope] = scalar(value, "state")
                elif key == "country_event": fixture.events.append(scalar(value, "id"))
                elif key == "add_stability": fixture.stability += float(value)
                else: self.fail("Unsupported settlement effect: " + key)
        fixture.run = lambda name: execute(effects[name], "RUS" if name.startswith("ADISCORD_vorkerland_rus") else "VAL")
        fixture.execute = execute
        return fixture

    def test_final_capitulation_delivers_all_tribes_after_receipts_are_cleared(self):
        from itertools import permutations, product
        from tools.tests.test_adiscord_stp_preparation import block, parse_clausewitz
        actions = block(parse_clausewitz(read_country_on_actions(ON_ACTIONS_PATH, "kefreyt")), "on_actions")
        immediate = block(block(actions, "on_capitulation_immediate"), "effect")
        handler = next(e for e in immediate if e.key == "if" and any(x.key == "set_country_flag" and isinstance(x.value, list)
                       and any(f.key == "flag" and f.value == "VAL_frontier_capitulation_pending" for f in x.value) for x in e.value))
        for commissioners, order in product((False, True), permutations(("CIN", "OSF", "APH"))):
            model = self.settlement_fixture(commissioners)
            for index, tag in enumerate(order):
                model.controllers[model.capitals[tag]] = "VAL"
                model.execute([handler], tag)
                self.assertEqual(model.vars["VAL", "VAL_frontier_stage"], 0 if index == 2 else 3)
                if index < 2: self.assertNotIn("NKA", model.owners.values())
            for state in (58, 62, 63, 64, 65):
                self.assertEqual(model.owners[str(state)], "NKA")
                self.assertEqual(model.controllers[str(state)], "NKA")
            for state in (59, 60, 61): self.assertEqual(model.owners[str(state)], "VAL")
            self.assertEqual(model.subjects["NKA"], "VAL")
            self.assertEqual(model.owners["70"], "NOD")
            self.assertFalse(model.wars)
            self.assertFalse(model.majors)
            for tag in ("CIN", "OSF", "APH"):
                self.assertNotIn("VAL_frontier_member", model.flags[tag])
            snapshot = (dict(model.owners), dict(model.controllers), list(model.events), model.stability)
            model.run("VAL_frontier_settle_victory")
            self.assertEqual(snapshot, (model.owners, model.controllers, model.events, model.stability))

    def test_eastern_award_precedes_rus_annex_without_taking_its_remaining_country(self):
        for occupier, expected in (("VAL", "VAL"), ("SUB", "VAL"), ("RUS", "RUS")):
            model = self.settlement_fixture(eastern=True)
            model.controllers["168"] = occupier
            model.controllers["167"] = "RUS"
            model.vars["RUS", "ADISCORD_vorkerland_rus_campaign_target"] = 4
            model.wars.add(frozenset(("RUS", "ERT")))
            model.run("ADISCORD_vorkerland_rus_annex_dirty_target")
            self.assertEqual(model.owners["168"], expected)
            self.assertEqual(model.controllers["168"], expected)
            for state in (167, 169): self.assertEqual(model.owners[str(state)], "RUS")
            self.assertNotIn("ERT", model.owners.values())
            before = (dict(model.owners), list(model.events))
            model.run("ADISCORD_vorkerland_rus_annex_dirty_target")
            self.assertEqual(before, (model.owners, model.events))

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
                elif k in ("controller", "owner"):
                    ok = (current, k) in facts and check(v, facts[(current, k)])
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
            candidates = [e.value for e in walk(victory) if e.key == "if" and any(x.key == "set_autonomy" and scalar(x.value, "target") == tag for x in e.value)]
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
            if tag == "ERT":
                facts["168", "is_owned_by", "ERT"] = True
                facts["168", "is_controlled_by", "ERT"] = True
                foreign = {**facts, ("168", "is_controlled_by", "ERT"): False, ("168", "controller"): "RUS"}
                self.assertFalse(self.frontier_matches(gate, foreign), "A foreign-held eastern claim cannot give a false victory")
            self.assertTrue(self.frontier_matches(gate, facts), "A recorded defeat settles before automatic state-controller changes")
            self.assertFalse(self.frontier_matches(gate, {**facts, (capital, "is_controlled_by", "VAL"): False}), "A liberated capital invalidates the old defeat")
            self.assertFalse(self.frontier_matches(gate, {**facts, (tag, "has_country_flag", "VAL_frontier_defeated"): False}), "Capital occupation without a capitulation is insufficient")
            other_target = target % 4 + 1
            other_tag = {1: "CIN", 2: "OSF", 3: "APH", 4: "ERT"}[other_target]
            stale = {**facts, ("VAL", "variable", "VAL_frontier_target"): other_target, (other_tag, "capital"): "999"}
            self.assertFalse(self.frontier_matches(gate, stale), "Defeating another country does not satisfy this ultimatum")

    def test_unrelated_capitulator_cannot_install_nods_administration(self):
        from tools.tests.test_adiscord_stp_preparation import block, scalar, walk, parse_clausewitz
        actions = block(parse_clausewitz(read_country_on_actions(ON_ACTIONS_PATH, 'kefreyt')), "on_actions")
        immediate = block(block(actions, "on_capitulation_immediate"), "effect")
        handler = next(e.value for e in immediate if e.key == "if" and any(x.key == "set_country_flag" and isinstance(x.value, list) and any(f.key == "flag" and f.value == "VAL_frontier_capitulation_pending" for f in x.value) for x in e.value))
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



class ValExpandedCampaignTests(unittest.TestCase):
    def test_resource_war_focus_visibility_follows_the_war_without_hiding_irem(self):
        from tools.tests.test_adiscord_stp_preparation import matches_conditions, walk
        tree = self.parse((ROOT / "common/national_focus/ADISCORD_national_focus_VAL.txt").read_text(encoding="utf-8"))
        focuses = {self.scalar(e.value, "id"): e.value for e in walk(tree) if e.key == "focus" and isinstance(e.value, list) and any(c.key == "id" for c in e.value)}
        focus = focuses["VAL_Resource_War_Contracts"]
        self.assertEqual(self.scalar(focus, "dynamic"), "yes")
        self.assertEqual(self.scalar(focus, "cancel_if_invalid"), "yes")
        self.assertEqual(self.scalar(self.getblock(focus, "prerequisite"), "focus"), "VAL_Ministry_Auditors")
        allow = self.getblock(focus, "allow_branch")
        self.assertNotIn("has_completed_focus", [e.key for e in walk(allow)])
        self.assertIn("ADISCORD_nam_resource_war_active", [e.key for e in walk(allow)])
        auditors = focuses["VAL_Ministry_Auditors"]
        self.assertEqual(self.scalar(focus, "x"), self.scalar(auditors, "x"))
        self.assertGreater(int(self.scalar(focus, "y")), int(self.scalar(auditors, "y")))
        position = (self.scalar(focus, "x"), self.scalar(focus, "y"))
        for other, body in focuses.items():
            if other != "VAL_Resource_War_Contracts":
                self.assertNotEqual(position, (self.scalar(body, "x"), self.scalar(body, "y")), other)
        for active in (False, True):
            facts = {("VAL", "ADISCORD_nam_resource_war_active", "yes"): active}
            for gate in ("allow_branch", "available"):
                self.assertEqual(matches_conditions(self.getblock(focus, gate), facts, "VAL"), active)
        southern_trade_dependencies = [e.value for e in walk(focuses["VAL_Southern_Trade_Charter"]) if e.key == "focus"]
        self.assertIn("VAL_Resource_War_Contracts", southern_trade_dependencies)
        for name, body in focuses.items():
            if name not in ("VAL_Resource_War_Contracts", "VAL_Support_The_Viceroy", "VAL_Southern_Trade_Charter"):
                dependencies = [e.value for e in walk(body) if e.key == "focus"]
                self.assertNotIn("VAL_Resource_War_Contracts", dependencies, name)
        tsaygen_prerequisites = [self.scalar(entry.value, "focus") for entry in focuses["VAL_Return_Southern_Tsaygen"] if entry.key == "prerequisite"]
        self.assertEqual(tsaygen_prerequisites, ["VAL_Contracts_Outlive_Kings", "VAL_Foreign_Broker_Licences"])
        self.assertEqual(self.scalar(self.getblock(focuses["VAL_frontier_return_irem"], "prerequisite"), "focus"), "VAL_Return_Southern_Tsaygen")

    def test_viceroy_support_focus_commits_to_existing_resource_aid_system(self):
        from tools.tests.test_adiscord_stp_preparation import walk
        tree = self.parse((ROOT / "common/national_focus/ADISCORD_national_focus_VAL.txt").read_text(encoding="utf-8"))
        focuses = {self.scalar(e.value, "id"): e.value for e in walk(tree)
                   if e.key == "focus" and isinstance(e.value, list) and any(c.key == "id" for c in e.value)}
        support = focuses["VAL_Support_The_Viceroy"]
        self.assertEqual(self.scalar(support, "dynamic"), "yes")
        self.assertEqual(self.scalar(support, "cancel_if_invalid"), "yes")
        self.assertEqual(self.scalar(self.getblock(support, "prerequisite"), "focus"), "VAL_Resource_War_Contracts")
        allow = self.getblock(support, "allow_branch")
        self.assertIn("VAL_Resource_War_Contracts", str(allow))
        self.assertIn("ADISCORD_nam_resource_war_active", str(allow))
        available = self.getblock(support, "available")
        self.assertIn("VAL_nam_concession_negotiable", str(available))
        reward = self.getblock(support, "completion_reward")
        reward_text = str(reward)
        self.assertIn("VAL_nam_concession_negotiable", reward_text)
        self.assertIn("VAL_nam_concession_agreed", reward_text)
        self.assertIn("VAL_resource_aid_side", reward_text)
        self.assertIn("VAL_start_resource_aid", reward_text)
        self.assertIn("VAL_begin_partner_contract_year", reward_text)
        self.assertNotIn("VAL_commit_nam_resource_aid", reward_text)

        effects_text = EFFECTS_PATH.read_text(encoding="utf-8")
        self.assertNotIn("VAL_commit_nam_resource_aid", effects_text)

        events = (ROOT / "events/ADISCORD_VAL_contract_events.txt").read_text(encoding="utf-8")
        nam_offer = events[events.index("id = val_contract.349"):events.index("id = val_contract.353")]
        self.assertNotIn("VAL_commit_nam_resource_aid", nam_offer)
        self.assertIn("VAL_nam_concession_agreed", nam_offer)
        self.assertIn("VAL_resource_aid_side", nam_offer)
        self.assertIn("VAL_start_resource_aid = yes", nam_offer)
        self.assertIn("VAL_begin_partner_contract_year = yes", nam_offer)

    def test_viceroy_support_has_no_new_scripted_effect_dependency(self):
        focus_text = (ROOT / "common/national_focus/ADISCORD_national_focus_VAL.txt").read_text(encoding="utf-8")
        events_text = (ROOT / "events/ADISCORD_VAL_contract_events.txt").read_text(encoding="utf-8")
        effects_text = EFFECTS_PATH.read_text(encoding="utf-8")
        for text in (focus_text, events_text, effects_text):
            self.assertNotIn("VAL_commit_nam_resource_aid", text)
        self.assertIn("VAL_start_resource_aid = yes", focus_text)
        self.assertIn("VAL_start_resource_aid = yes", events_text)

    def test_resource_war_transitions_invalidate_the_focus_layout_without_an_aid_contract(self):
        from tools.tests.test_adiscord_stp_preparation import walk
        effects = self.parse((ROOT / "common/scripted_effects/ADISCORD_nam_resource_war_effects.txt").read_text(encoding="utf-8"))
        for suffix in ("begin_hostilities", "resolve_peaceful_withdrawal", "resolve_coalition_victory", "resolve_nam_victory"):
            effect = self.getblock(effects, "ADISCORD_nam_resource_war_" + suffix)
            refresh = [e for e in walk(effect) if e.key == "VAL" and isinstance(e.value, list)
                       and any(child.key == "mark_focus_tree_layout_dirty" for child in walk(e.value))]
            self.assertEqual(len(refresh), 1, suffix)
            self.assertFalse(any(e.key in ("has_country_flag", "check_variable") for e in walk(refresh[0].value)), suffix)
        hooks = self.getblock(self.parse(ON_ACTIONS_PATH.read_text(encoding="utf-8")), "on_actions")
        self.assertTrue(any(e.key == "mark_focus_tree_layout_dirty" for e in walk(self.getblock(hooks, "on_startup"))))

    def test_aid_delivery_rechecks_fractional_stock_and_current_recipient(self):
        from tools.tests.test_adiscord_stp_preparation import selected_effects
        effects = self.parse(EFFECTS_PATH.read_text(encoding="utf-8"))
        for campaign in ("resource", "northern"):
            for mode, currency, boundary in (("arms", "equipment", 25000), ("personnel", "numeric", 2000)):
                payload = self.getblock(effects, f"VAL_deliver_{campaign}_aid_{mode}")
                for amount, expected in ((boundary - .1, False), (boundary, True)):
                    facts = {("VAL", "variable", f"VAL_{campaign}_aid_state"): 1,
                             ("VAL", "has_active_mission", f"VAL_{campaign}_aid_deadline"): True,
                             ("VAL", "VAL_northern_aid_deliveries_open", "yes"): True,
                             ("VAL", "has_capitulated", "no"): True, ("VAL", "is_subject", "no"): True,
                             ("FROM", f"VAL_{campaign}_aid_recipient", "yes"): True,
                             ("VAL", "numeric", "command_power"): 25,
                             ("VAL", currency, "infantry_equipment" if mode == "arms" else "has_manpower"): amount}
                    selected = [e for _, e in selected_effects(payload, facts, "VAL")]
                    key = "send_equipment" if mode == "arms" else "add_manpower"
                    debits = [e for e in selected if e.key == key and (mode == "arms" or e.value == "-2000")]
                    self.assertEqual(len(debits), int(expected), (campaign, mode, amount))
                    delivery_gate = (("VAL", "VAL_northern_aid_deliveries_open", "yes") if campaign == "northern"
                                     else ("VAL", "has_active_mission", "VAL_resource_aid_deadline"))
                    for blocker in (("FROM", f"VAL_{campaign}_aid_recipient", "yes"), delivery_gate):
                        self.assertFalse(list(selected_effects(payload, {**facts, blocker: False}, "VAL")))

    def test_northern_victory_requires_fulfilled_aid_and_settles_only_once(self):
        from tools.tests.test_adiscord_stp_preparation import selected_effects
        effects = self.parse(EFFECTS_PATH.read_text(encoding="utf-8"))
        victory = self.getblock(effects, "VAL_settle_northern_aid_victory")
        defeat = self.getblock(effects, "VAL_settle_northern_aid_defeat")
        for state in (1, 2, -1, 3):
            facts = {("VAL", "has_variable", "VAL_northern_aid_state"): True,
                     ("VAL", "variable", "VAL_northern_aid_state"): state,
                     ("VAL", "has_capitulated", "no"): True, ("VAL", "is_subject", "no"): True}
            for payload, expected in ((victory, state == 2), (defeat, state != 3)):
                rewards = [e for _, e in selected_effects(payload, facts, "VAL") if e.key == "add_timed_idea"]
                self.assertEqual(len(rewards), int(expected), state)
                if rewards:
                    self.assertEqual(self.scalar(rewards[0].value, "days"), "180")
        close = self.getblock(effects, "VAL_close_northern_aid")
        self.assertEqual(self.scalar(self.getblock(close, "set_variable"), "value"), "3")

    def test_resource_rights_require_the_chosen_victor_and_completed_aid(self):
        from tools.tests.test_adiscord_stp_preparation import selected_effects
        effects = self.parse(EFFECTS_PATH.read_text(encoding="utf-8"))
        settlement = self.getblock(effects, "VAL_settle_resource_aid")
        for side in (1, 2):
            for winner in ("nam", "coalition", "peaceful_partition"):
                for state in (1, 2, -1, 3):
                    facts = {("VAL", "has_variable", "VAL_resource_aid_state"): True,
                             ("VAL", "variable", "VAL_resource_aid_state"): state,
                             ("VAL", "variable", "VAL_resource_aid_side"): side,
                             ("VAL", "has_global_flag", f"ADISCORD_nam_resource_war_{winner}_victory"): True,
                             ("VAL", "has_capitulated", "no"): True, ("VAL", "is_subject", "no"): True,
                             ("EFL", "exists", "yes"): True, ("EFL", "has_capitulated", "no"): True,
                             ("EFL", "is_subject", "no"): True,
                             ("230", "is_owned_by", "EFL"): True, ("230", "is_controlled_by", "EFL"): True}
                    selected = [e for _, e in selected_effects(settlement, facts, "VAL")]
                    grants = [e for e in selected if e.key in ("give_resource_rights", "VAL_deliver_nam_concession")]
                    self.assertEqual(len(grants), int(state == 2 and winner == ("nam" if side == 1 else "coalition")), (side, winner, state))
                    if winner == "peaceful_partition":
                        self.assertFalse(any(e.key == "VAL_fail_resource_aid" for e in selected))

    def test_war_aid_requires_a_complete_alternative_not_a_token_shipment(self):
        for campaign in ("resource", "northern"):
            name = f"VAL_{campaign}_aid_sufficient"
            self.assertTrue(name in self.triggers, name)
            for rifles, personnel, days, expected in (
                (0, 0, 0, False), (49999.9, 0, 0, False),
                (50000, 0, 0, True), (0, 1999.9, 0, False),
                (0, 2000, 0, True), (0, 0, 29, False), (0, 0, 30, True),
            ):
                facts = {("VAL", "variable", f"VAL_{campaign}_aid_rifles"): rifles,
                         ("VAL", "variable", f"VAL_{campaign}_aid_personnel"): personnel,
                         ("VAL", "variable", f"VAL_{campaign}_aid_volunteer_days"): days}
                self.assertEqual(self.match(name, facts), expected, (campaign, rifles, personnel, days))

    def test_war_aid_deadlines_stay_active_while_pledge_is_pending(self):
        decisions = self.parse(DECISIONS_PATH.read_text(encoding="utf-8"))
        for campaign in ("resource", "northern"):
            category = self.getblock(decisions, f"VAL_{campaign}_war_aid")
            mission = self.getblock(category, f"VAL_{campaign}_aid_deadline")
            available = self.getblock(mission, "available")
            cancel = self.getblock(mission, "cancel_trigger")
            self.assertEqual(self.scalar(available, "always"), "yes")
            self.assertNotIn(f"VAL_{campaign}_aid_sufficient", str(available))
            self.assertIn(f"VAL_{campaign}_aid_state", str(cancel))
            self.assertNotIn("complete_effect", [entry.key for entry in mission])

    def test_war_categories_close_without_an_active_conflict_and_keep_volunteers_together(self):
        from tools.tests.test_adiscord_stp_preparation import matches_conditions
        categories = self.parse((ROOT / "common/decisions/categories/ADISCORD_VAL_rework_categories.txt").read_text(encoding="utf-8"))
        decisions = self.parse(DECISIONS_PATH.read_text(encoding="utf-8"))
        for category, trigger in (("VAL_resource_war_aid", "ADISCORD_nam_resource_war_active"),
                                  ("VAL_northern_war_aid", "VAL_northern_volunteer_front_open")):
            self.assertIn(category, [e.key for e in categories])
            visible = self.getblock(self.getblock(categories, category), "visible")
            self.assertFalse(matches_conditions(visible, {}, "VAL"))
            self.assertTrue(matches_conditions(visible, {("VAL", trigger, "yes"): True}, "VAL"))
        north = self.getblock(decisions, "VAL_northern_war_aid")
        self.assertIn("VAL_northern_volunteers", [e.key for e in north])
        self.assertNotIn("VAL_northern_volunteers", [e.key for e in self.getblock(decisions, "VAL_military_operations")])

    @classmethod
    def setUpClass(cls):
        from tools.tests.test_adiscord_stp_preparation import parse_clausewitz, block, scalar
        cls.parse, cls.getblock, cls.scalar = staticmethod(parse_clausewitz), staticmethod(block), staticmethod(scalar)
        cls.triggers = {e.key: e.value for e in parse_clausewitz(
            (ROOT / "common/scripted_triggers/ADISCORD_VAL_rework_triggers.txt").read_text(encoding="utf-8"))}
        cls.events = {scalar(e.value, "id"): e.value for e in parse_clausewitz(
            (ROOT / "events/ADISCORD_VAL_contract_events.txt").read_text(encoding="utf-8")) if e.key == "country_event"}

    def match(self, name, facts, scope="VAL", root="VAL"):
        from dataclasses import replace
        from tools.tests.test_adiscord_stp_preparation import matches_conditions
        def expand(items):
            result = []
            for entry in items:
                if entry.key in self.triggers and isinstance(entry.value, str):
                    self.assertIn(entry.value, ("yes", "no"), "scripted triggers use boolean calls")
                    result.append(replace(entry, key="AND" if entry.value == "yes" else "NOT",
                                          value=expand(self.triggers[entry.key])))
                elif entry.key == "tag" and entry.value == "ROOT":
                    result.append(replace(entry, value=root))
                elif isinstance(entry.value, list):
                    result.append(replace(entry, value=expand(entry.value)))
                else:
                    result.append(entry)
            return result
        return matches_conditions(expand(self.triggers[name]), facts, scope)

    def customer_facts(self):
        return {("VAL", "exists", "yes"): True, ("VAL", "has_capitulated", "no"): True,
                ("VAL", "has_country_flag", "VAL_export_offer_pending"): True,
                ("VAL", "equipment", "infantry_equipment"): 25000,
                ("VAL", "numeric", "command_power"): 25,
                ("WKR", "exists", "yes"): True, ("WKR", "has_capitulated", "no"): True,
                ("WKR", "has_war", "yes"): True,
                ("WKR", "ADISCORD_economy_can_spend_100", "yes"): True,
                ("WKR", "has_country_flag", "VAL_export_offer_arms"): True,
                ("WKR", "has_country_flag", "VAL_export_offer_advisors"): True,
                ("WKR", "has_war_with", "event_target:VAL_advisor_enemy"): True}

    def test_quarterly_order_cash_gates_use_literal_tariffs(self):
        triggers = (ROOT / "common/scripted_triggers/ADISCORD_VAL_rework_triggers.txt").read_text(encoding="utf-8")
        effects = EFFECTS_PATH.read_text(encoding="utf-8")
        for slot in (1, 2):
            gate = named_block_spans(triggers, f"VAL_order_{slot}_can_dispatch")[0].text
            self.assertIn(f"VAL_order_{slot}_partner_can_pay = yes", gate)
            self.assertNotIn(f"VAL.VAL_order_{slot}_remaining", gate)
            payable = named_block_spans(triggers, f"VAL_order_{slot}_partner_can_pay")[0].text
            for amount in ("375", "500", "750", "1000", "1687.5", "2250", "3750", "5000"):
                self.assertIn(f"value = {amount}", payable)
            payment = named_block_spans(effects, f"VAL_order_{slot}_settle_payment")[0].text
            self.assertNotIn(f"VAL.VAL_order_{slot}_remaining", payment)

    def test_offer_acceptance_rechecks_exact_stock_and_command_boundaries(self):
        facts = self.customer_facts()
        for amount in (24999, 24999.9, 25000, 25001):
            facts["VAL", "equipment", "infantry_equipment"] = amount
            self.assertEqual(self.match("VAL_export_arms_can_accept", facts, "WKR"), amount >= 25000)
        for amount in (24, 24.9, 25, 26):
            facts["VAL", "numeric", "command_power"] = amount
            self.assertEqual(self.match("VAL_export_advisors_can_accept", facts, "WKR"), amount >= 25)

    def test_expired_refused_and_unaffordable_offers_cannot_settle_again(self):
        for kind in ("arms", "advisors"):
            name = "VAL_export_" + kind + "_can_accept"
            self.assertTrue(self.match(name, self.customer_facts(), "WKR"))
            for key, value in (
                (("WKR", "has_country_flag", "VAL_export_offer_" + kind), False),
                (("VAL", "has_country_flag", "VAL_export_offer_pending"), False),
                (("WKR", "ADISCORD_economy_can_spend_100", "yes"), False),
                (("WKR", "has_war_with", "VAL"), True),
                (("WKR", "has_capitulated", "no"), False),
                (("VAL", "has_capitulated", "no"), False),
                (("WKR", "has_war", "yes"), False),
            ):
                facts = self.customer_facts(); facts[key] = value
                self.assertFalse(self.match(name, facts, "WKR"), (kind, key))

    def test_export_slots_do_not_overwrite_an_active_income_idea(self):
        from itertools import product
        for first, second, clearing in product((False, True), repeat=3):
            facts = {("VAL", "has_idea", "VAL_export_income_1"): first,
                     ("VAL", "has_idea", "VAL_export_income_2"): second,
                     ("VAL", "has_completed_focus", "VAL_Northern_Clearing_House"): clearing}
            self.assertEqual(self.match("VAL_export_slot_free", facts), not first or clearing and not second)

    def test_buyer_payment_and_native_equipment_transfer_share_authenticated_branch(self):
        from tools.tests.test_adiscord_stp_preparation import walk
        for num, kind in ((340, "arms"), (341, "advisors")):
            event = self.events[f"val_contract.{num}"]
            options = [e.value for e in event if e.key == "option"]
            self.assertEqual(self.scalar(options[0], "name"), "VAL_export_decline")
            accept = next(o for o in options if self.scalar(o, "name") == "VAL_export_accept")
            branch = self.getblock(self.getblock(accept, "hidden_effect"), "if")
            self.assertEqual(self.scalar(self.getblock(branch, "limit"), f"VAL_export_{kind}_can_accept"), "yes")
            self.assertEqual(sum(e.key == "ADISCORD_economy_spend_100" for e in walk(branch)), 1)
            self.assertEqual(sum(e.key == "ADISCORD_economy_receive_100" for e in walk(branch)), 1)
            self.assertIn("VAL_export_offer_" + kind, [e.value for e in walk(branch) if e.key == "clr_country_flag"])
            if kind == "arms":
                transfer = next(e.value for e in walk(branch) if e.key == "send_equipment")
                self.assertEqual(self.scalar(transfer, "equipment"), "infantry_equipment")
                self.assertEqual(self.scalar(transfer, "amount"), "25000")
                self.assertEqual(self.scalar(transfer, "target"), "ROOT")
                self.assertFalse(any(e.key == "add_equipment_to_stockpile" for e in walk(branch)))

    def test_export_slots_are_capacity_markers_not_deferred_income(self):
        from tools.tests.test_adiscord_stp_preparation import parse_clausewitz, block, scalar
        country = block(block(parse_clausewitz(IDEAS_PATH.read_text(encoding="utf-8")), "ideas"), "country")
        for idea in ("VAL_export_income_1", "VAL_export_income_2"):
            declaration = block(country, idea)
            self.assertFalse(any(e.key == "on_add" for e in declaration))
            self.assertFalse(any(e.key == "on_remove" for e in declaration))
            self.assertFalse(block(declaration, "modifier"))
        advisers = block(country, "VAL_advisors_income")
        self.assertFalse(any(e.key == "on_add" for e in advisers))
        self.assertFalse(any(e.key == "on_remove" for e in advisers))
        self.assertEqual(scalar(block(advisers, "modifier"), "planning_speed"), "-0.05")
        self.assertFalse(any(e.key == "ADISCORD_economy_weekly_income" for e in block(advisers, "modifier")))

    def test_supply_recovery_requires_occidia_and_all_eight_northern_states(self):
        facts = {("VAL", "VAL_cannibal_sphere_secured", "yes"): True}
        for state in (43, 44, 88, 58, 59, 60, 61, 62, 63, 64, 65):
            for key in ("is_owned_by", "is_controlled_by"):
                facts[str(state), key, "VAL"] = True
        self.assertTrue(self.match("VAL_supply_base_secured", facts))
        for state in (43, 44, 88, 58, 59, 60, 61, 62, 63, 64, 65):
            for key in ("is_owned_by", "is_controlled_by"):
                lost = dict(facts); lost[str(state), key, "VAL"] = False
                self.assertFalse(self.match("VAL_supply_base_secured", lost), (state, key))
        self.assertNotIn("168", [e.key for e in self.triggers["VAL_supply_base_secured"]])

    def test_disappearing_nod_does_not_credit_third_party_conquest(self):
        facts = {("NOD", "exists", "no"): True}
        self.assertFalse(self.match("VAL_nod_dominated", facts))
        for state in (10, 11, 12, 13, 17, 18, 30):
            facts[str(state), "is_owned_by", "VAL"] = True
            facts[str(state), "is_controlled_by", "VAL"] = True
        self.assertTrue(self.match("VAL_nod_dominated", facts))
        facts["12", "is_controlled_by", "VAL"] = False
        self.assertFalse(self.match("VAL_nod_dominated", facts))

    def test_operations_map_covers_all_requested_starting_countries(self):
        from tools.builders import build_adiscord_val_operations_map as builder
        tags = {"NOD", "BJK", "COF", "TFF", "YPR"}
        expected = set()
        for path in (ROOT / "history/states").glob("*.txt"):
            source = path.read_text(encoding="utf-8-sig")
            if re.search(r"\bowner\s*=\s*(?:" + "|".join(tags) + r")\b", source):
                expected.add(int(re.search(r"\bid\s*=\s*(\d+)", source)[1]))
        self.assertTrue(expected.issubset(builder.STATE_IDS), expected - set(builder.STATE_IDS))
        self.assertTrue(tags.issubset(builder.MAP_TAGS))

    def test_stelander_operations_share_assets_and_require_postwar(self):
        from tools.builders import build_adiscord_val_operations_map as builder
        outputs = builder.interface_outputs({state: (0, 0, 1, 1) for state in builder.STATE_IDS})
        gui = outputs["interface/ADISCORD_VAL_operations.gui"]
        script = outputs["common/scripted_guis/ADISCORD_VAL_operations_scripted_gui.txt"]
        self.assertIn('name = "ADISCORD_STP_operations_panel_window"', gui)
        self.assertIn('pdx_tooltip = "STP_operations_map_tt"', gui)
        self.assertIn('ADISCORD_STP_operations_panel = {', script)
        self.assertIn('STP_ops_41_border_visible = { 41 = { controller = { tag = STS', script)
        categories = (ROOT / "common/decisions/categories/ADISCORD_decision_categories_STP.txt").read_text(encoding="utf-8")
        category = named_block_spans(categories, "STP_military_operations")[0].text
        self.assertIn("allowed = { tag = STS }", category)
        self.assertIn("has_country_flag = STP_cw_postwar", category)
        self.assertIn("scripted_gui = ADISCORD_STP_operations_panel", category)

    def test_map_controller_layers_are_exhaustive_and_exclusive(self):
        from tools.tests.test_adiscord_stp_preparation import parse_clausewitz, block, scalar, matches_conditions
        from tools.builders import build_adiscord_val_operations_map as builder
        boxes = {state: (0, 0, 10, 10) for state in builder.STATE_IDS}
        outputs = builder.interface_outputs(boxes)
        script = parse_clausewitz(outputs["common/scripted_guis/ADISCORD_VAL_operations_scripted_gui.txt"])
        panel = block(block(script, "scripted_gui"), "ADISCORD_VAL_operations_panel")
        triggers = {entry.key: entry.value for entry in block(panel, "triggers")}
        properties = {entry.key: entry.value for entry in block(panel, "properties")}
        effects = parse_clausewitz(outputs["common/scripted_effects/ADISCORD_VAL_operations_map_effects.txt"])
        cache = block(effects, "VAL_operations_map_refresh_cache")
        gui_text = outputs["interface/ADISCORD_VAL_operations.gui"]
        self.assertTrue(set(builder.VAL_STATES).issubset(builder.STATE_IDS))
        self.assertNotIn(168, builder.VAL_STATES)
        self.assertIn(118, builder.STATE_IDS)
        self.assertIn(119, builder.STATE_IDS)
        self.assertNotIn(186, builder.STATE_IDS)
        self.assertNotIn("RZA", builder.MAP_TAGS)
        expected_frames = {tag: frame for frame, tag in enumerate(builder.MAP_TAGS, 1)}
        for state in builder.STATE_IDS:
            widget = f"VAL_ops_{state}_controller"
            frame_variable = f"operations_state_{state}_frame"
            self.assertTrue(matches_conditions(triggers[f"{widget}_visible"], {}, "VAL"))
            self.assertEqual(scalar(properties[widget], "frame"), frame_variable)
            self.assertEqual(gui_text.count(f'name = "{widget}"'), 1)
            self.assertIn(f'quadTextureSprite = "GFX_VAL_ops_state_{state}"', gui_text)
            self.assertNotIn(f'spriteType = "GFX_VAL_ops_state_{state}"', gui_text)
            state_cache = next(entry.value for entry in cache
                               if entry.key == "set_variable" and scalar(entry.value, "var") == frame_variable)
            state_branches = [entry for entry in cache if entry.key in ("if", "else_if")
                              and any(child.key == str(state) for child in block(entry.value, "limit"))]
            for controller, cosmetic, expected in (
                *((tag, None, frame) for tag, frame in expected_frames.items()),
                ("STP", "STL_VAL_administration", expected_frames["STP"]),
                ("UNKNOWN", None, builder.FRAME_COUNT),
            ):
                facts = {(str(state), "controller"): controller}
                if cosmetic:
                    facts[controller, "has_cosmetic_tag", cosmetic] = True
                selected_frame = int(scalar(state_cache, "value"))
                for branch in state_branches:
                    if matches_conditions(block(branch.value, "limit"), facts, "VAL"):
                        assignment = block(branch.value, "set_variable")
                        selected_frame = int(scalar(assignment, "value"))
                        break
                self.assertEqual(selected_frame, expected, (state, controller, cosmetic))

            for puppet in ("BLD", "BHG", "BGT", "BBV", "BCM"):
                facts = {(str(state), "controller"): puppet,
                         (puppet, "is_subject_of", "BJK"): True}
                selected_frame = int(scalar(state_cache, "value"))
                for branch in state_branches:
                    if matches_conditions(block(branch.value, "limit"), facts, "VAL"):
                        assignment = block(branch.value, "set_variable")
                        selected_frame = int(scalar(assignment, "value"))
                        break
                self.assertEqual(selected_frame, expected_frames["BJK"], (state, puppet))

    def test_map_marks_partial_control_before_state_controller_changes(self):
        from tools.tests.test_adiscord_stp_preparation import parse_clausewitz, block, matches_conditions
        from tools.builders.build_adiscord_val_operations_map import STATE_IDS, state_provinces
        script = parse_clausewitz((ROOT / "common/scripted_guis/ADISCORD_VAL_operations_scripted_gui.txt").read_text(encoding="utf-8"))
        for prefix, viewer in (("VAL", "VAL"), ("STP", "STS")):
            layers = {e.key: e.value for e in block(block(block(script, "scripted_gui"), f"ADISCORD_{prefix}_operations_panel"), "triggers")}
            for state in STATE_IDS:
                provinces = sorted(state_provinces(state))
                facts = {(str(state), "controller"): viewer}
                facts.update({(viewer, "controls_province", str(p)): True for p in provinces})
                layer = layers[f"{prefix}_ops_{state}_contested_visible"]
                border = layers[f"{prefix}_ops_{state}_border_visible"]
                self.assertTrue(matches_conditions(border, facts, viewer), (viewer, state))
                self.assertFalse(matches_conditions(layer, facts, viewer), (viewer, state))
                facts[viewer, "controls_province", str(provinces[0])] = False
                self.assertTrue(matches_conditions(layer, facts, viewer), (viewer, state))
                facts[str(state), "controller"] = "NOD"
                self.assertFalse(matches_conditions(layer, facts, viewer), (viewer, state))
                self.assertFalse(matches_conditions(border, facts, viewer), (viewer, state))

    def test_foreign_map_colors_are_solid_and_cropped_layers_preserve_pixels(self):
        from tools.builders import build_adiscord_val_operations_map as builder
        outputs, _, _, _ = builder.render_outputs()
        compact, boxes = builder.compact_overlays(outputs)
        colors = builder.country_colors()
        for state in builder.STATE_IDS:
            source = outputs[f"VAL_ops_state_{state}.png"]
            strip = compact[f"VAL_ops_state_{state}.png"]
            left, top, right, bottom = boxes[state]
            width = right - left
            for index, color in enumerate(colors):
                original = source.crop((index * builder.WIDTH + left, top, index * builder.WIDTH + right, bottom))
                cropped = strip.crop((index * width, 0, (index + 1) * width, bottom - top))
                self.assertEqual(original.tobytes(), cropped.tobytes())
                self.assertEqual({pixel[:3] for pixel in cropped.getdata() if pixel[3]}, {color})

    def test_full_tier_mirror_detects_wrong_modifier_even_if_id_is_valid(self):
        check = ValRewardValidatorTests()
        source = IDEAS_PATH.read_text(encoding="utf-8")
        old = named_block_spans(source, "VAL_administration_3_preview")[0]
        wrong = old.text.replace("political_power_gain = 0.25", "political_power_gain = 9")
        if wrong == old.text:
            wrong = old.text.replace("modifier = {", "modifier = { army_attack_factor = 9", 1)
        mutated = source[:old.start] + wrong + source[old.end:]
        self.assertTrue(check.preview_issues(ideas=mutated)[1])

    def test_military_settlement_precedes_both_immediate_and_queued_event_paths(self):
        source = (ROOT / "common/scripted_effects/ADISCORD_STP_scripted_effects.txt").read_text(encoding="utf-8")
        body = named_block_spans(source, "STP_pc_begin_settlement")[0].text
        self.assertEqual(body.count("VAL_enforce_stelander_defeat = yes"), 1)
        self.assertLess(body.index("VAL_enforce_stelander_defeat = yes"), body.index("STP_pc_clear_settlement = yes"))
        enforcement = named_block_spans(EFFECTS_PATH.read_text(encoding="utf-8"), "VAL_enforce_stelander_defeat")[0].text
        self.assertIn("STP_cw_capitulation_occupier value = 5 compare = equals", enforcement)
        self.assertIn("VAL_install_stelander_administration = yes", enforcement)
        install = named_block_spans(EFFECTS_PATH.read_text(encoding="utf-8"), "VAL_install_stelander_administration")[0].text
        self.assertIn("end_wars = no end_civil_wars = no", install)



    def test_joint_shabrat_nod_campaign_uses_one_war_and_controlled_settlement(self):
        decisions = DECISIONS_PATH.read_text(encoding="utf-8")
        campaign = named_block_spans(decisions, "VAL_campaign_against_nod")[0].text
        self.assertIn("set_country_flag = VAL_joint_nod_campaign_with_sts", campaign)
        self.assertIn("targeted_alliance = STS enemy = NOD", campaign)
        self.assertIn("character = STP_maksim_shabrat ruling_only = yes", campaign)
        self.assertIn("STP_cw_release_tff_to_northern_war = yes", campaign)

        settlement = named_block_spans(EFFECTS_PATH.read_text(encoding="utf-8"),
                                       "VAL_settle_joint_nod_shabrat_victory")[0].text
        for state in ("10", "11", "12", "13", "17", "18", "30"):
            self.assertIn(f"{state} = {{", settlement)
            self.assertIn(f"VAL = {{ transfer_state = {state} }}", settlement)
            self.assertIn(f"STS = {{ transfer_state = {state} }}", settlement)
        self.assertIn("STP_pc_begin_settlement = yes", settlement)
        self.assertIn("white_peace = VAL", settlement)
        self.assertNotIn("VAL_install_nodrul_administration", settlement)

        source = (ROOT / "common/on_actions/09_ADISCORD_scripted_peace_on_actions.txt").read_text()
        immediate = source.split("# BEGIN kefreyt:on_capitulation_immediate", 1)[1].split("# END kefreyt:on_capitulation_immediate", 1)[0]
        self.assertLess(immediate.index("VAL_settle_joint_nod_shabrat_victory = yes"),
                        immediate.index("set_country_flag = VAL_final_defeat_pending"))
        self.assertIn("has_country_flag = VAL_joint_nod_campaign_with_sts", immediate)
        self.assertIn("has_war_with = STS", immediate)

    def test_final_settlement_waits_for_allies_and_rejects_liberation(self):
        facts = {
            ("NOD", "has_country_flag", "VAL_final_defeat_pending"): True,
            ("NOD", "has_capitulated", "yes"): True,
            ("VAL", "exists", "yes"): True,
            ("VAL", "has_capitulated", "no"): True,
            ("VAL", "is_subject", "no"): True,
        }
        self.assertTrue(self.match("VAL_final_settlement_ready", facts, "NOD"))
        facts.update({("STP", "exists", "yes"): True,
                      ("STP", "is_in_faction_with", "PREV"): True,
                      ("STP", "has_war_with", "VAL"): True,
                      ("STP", "has_capitulated", "no"): True})
        self.assertFalse(self.match("VAL_final_settlement_ready", facts, "NOD"))
        facts["STP", "has_capitulated", "no"] = False
        self.assertTrue(self.match("VAL_final_settlement_ready", facts, "NOD"))
        facts["NOD", "has_capitulated", "yes"] = False
        self.assertFalse(self.match("VAL_final_settlement_ready", facts, "NOD"))

    def test_final_settlement_accepts_transient_immediate_capitulation_without_root_scope(self):
        for tag in ("STP", "STS", "NOD"):
            facts = {
                (tag, "has_country_flag", "VAL_final_defeat_pending"): True,
                (tag, "has_country_flag", "VAL_final_capitulation_immediate"): True,
                ("VAL", "exists", "yes"): True,
                ("VAL", "has_capitulated", "no"): True,
                ("VAL", "is_subject", "no"): True,
            }
            self.assertTrue(self.match("VAL_final_settlement_ready", facts, tag))
            self.assertTrue(self.match("VAL_final_settlement_ready", facts, tag, root="VAL"))

        trigger = named_block_spans(
            (ROOT / "common/scripted_triggers/ADISCORD_VAL_rework_triggers.txt").read_text(encoding="utf-8"),
            "VAL_final_settlement_ready",
        )[0].text
        finalizer = named_block_spans(
            EFFECTS_PATH.read_text(encoding="utf-8"),
            "VAL_finalize_reserved_settlements",
        )[0].text
        self.assertNotIn("tag = ROOT has_country_flag = VAL_final_capitulation_immediate", trigger)
        self.assertNotIn("tag = ROOT has_country_flag = VAL_final_capitulation_immediate", finalizer)

    def test_last_ally_immediate_capitulation_unblocks_reserved_country(self):
        facts = {
            ("STP", "has_country_flag", "VAL_final_defeat_pending"): True,
            ("STP", "has_capitulated", "yes"): True,
            ("VAL", "exists", "yes"): True,
            ("VAL", "has_capitulated", "no"): True,
            ("VAL", "is_subject", "no"): True,
            ("NOD", "exists", "yes"): True,
            ("NOD", "is_in_faction_with", "PREV"): True,
            ("NOD", "has_war_with", "VAL"): True,
            ("NOD", "has_capitulated", "no"): True,
        }
        self.assertFalse(self.match("VAL_final_settlement_ready", facts, "STP"))
        facts["NOD", "has_country_flag", "VAL_final_capitulation_immediate"] = True
        self.assertTrue(self.match("VAL_final_settlement_ready", facts, "STP"))

    def test_final_settlement_runs_before_native_conference(self):
        source = (ROOT / "common/on_actions/09_ADISCORD_scripted_peace_on_actions.txt").read_text()
        immediate = source.split("# BEGIN kefreyt:on_capitulation_immediate", 1)[1].split("# END kefreyt:on_capitulation_immediate", 1)[0]
        self.assertLess(immediate.index("set_country_flag = VAL_final_defeat_pending"),
                        immediate.index("VAL_finalize_reserved_settlements = yes"))
        self.assertIn("flag = VAL_final_capitulation_immediate days = 1", immediate)
        late = source.split("# BEGIN kefreyt:on_capitulation\n", 1)[1].split("# END kefreyt:on_capitulation", 1)[0]
        self.assertIn("clr_country_flag = VAL_final_capitulation_immediate", late)
        self.assertIn("set_global_flag = skip_default_capitulation", late)

    def test_stelander_border_cession_routes_hosheit_to_oca_and_kreyden_to_val(self):
        from tools.tests.test_adiscord_stp_preparation import block, parse_clausewitz, walk
        effect = block(parse_clausewitz(EFFECTS_PATH.read_text(encoding="utf-8")), "VAL_cede_stelander_border")
        regions = {e.key: e.value for e in walk(effect) if e.key.isdigit()}
        self.assertEqual(set(regions), {"46", "29"})

        hosheit = block(regions["46"], "if")
        hosheit_text = str([(e.key, e.value) for e in walk(hosheit)])
        self.assertIn("is_subject_of', 'VAL", hosheit_text)
        self.assertIn("add_core_of', 'OCA", hosheit_text)
        self.assertEqual([e.value for e in walk(hosheit) if e.key == "transfer_state"].count("46"), 2)
        self.assertIn("OCA", [e.key for e in walk(hosheit)])
        self.assertIn("VAL", [e.key for e in walk(hosheit)])

        kreyden = block(regions["29"], "if")
        kreyden_text = str([(e.key, e.value) for e in walk(kreyden)])
        self.assertIn("transfer_state', '29", kreyden_text)
        self.assertIn("set_state_controller_to', 'VAL", kreyden_text)

        install = block(parse_clausewitz(EFFECTS_PATH.read_text(encoding="utf-8")), "VAL_install_stelander_administration")
        self.assertFalse(any(e.key in {"annex_country", "change_tag_from"} for e in walk(install)))

    def test_bop_and_autonomy_images_fit_native_slots(self):
        from PIL import Image
        for filename in ("VAL_bop_general_staff.png", "VAL_bop_solgalov.png"):
            with Image.open(ROOT / "gfx/interface/bop" / filename) as image:
                self.assertEqual(image.size, (78, 88))
        with Image.open(ROOT / "gfx/interface/autonomy/autonomy_VAL_contract_administration_icon.png") as image:
            self.assertEqual(image.size, (35, 35))
        gfx = (ROOT / "interface/countrypoliticsview.gfx").read_text(encoding="utf-8")
        self.assertIn('name = "GFX_autonomy_VAL_contract_administration_icon"', gfx)
        for name in ("VAL_commonwealth", "STL_VAL_administration", "NOD_VAL_administration"):
            for folder, size in (("", (82, 52)), ("medium/", (41, 26)), ("small/", (10, 7))):
                with Image.open(ROOT / f"gfx/flags/{folder}{name}.tga") as image:
                    self.assertEqual(image.size, size)

    def test_northern_administration_keeps_bounded_land_and_native_technology(self):
        from tools.tests.test_adiscord_stp_preparation import block, walk, parse_clausewitz, scalar
        formation = block(parse_clausewitz(EFFECTS_PATH.read_text(encoding="utf-8")), "VAL_form_northern_administration")
        self.assertEqual({e.value for e in walk(formation) if e.key == "transfer_state"}, {str(n) for n in range(58, 66)})
        annexations = [e.value for e in walk(formation) if e.key == "annex_country"]
        self.assertEqual({scalar(e, "target") for e in annexations}, {"CIN", "OSF", "APH"})
        for entry in annexations:
            self.assertEqual(scalar(entry, "transfer_troops"), "yes")
        parents = [e.value for e in walk(formation) if e.key == "if"
                   and any(x.key == "NKA" and any(y.key == "annex_country" for y in x.value) for x in e.value)]
        self.assertEqual(len(parents), 3)
        for parent in parents:
            guards = list(walk(block(parent, "limit")))
            self.assertIn("VAL", [e.value for e in guards if e.key == "is_subject_of"])
            self.assertIn("VAL_frontier_has_only_claimed_states", [e.key for e in guards])
        self.assertIn("inherit_technology", [e.key for e in walk(formation)])
        self.assertNotIn("copy_tech_from", [e.key for e in walk(formation)])
        autonomy = [e.value for e in walk(formation) if e.key == "set_autonomy"]
        self.assertEqual(len(autonomy), 1)
        self.assertEqual(scalar(autonomy[0], "target"), "NKA")
        self.assertEqual(scalar(autonomy[0], "autonomy_state"), "autonomy_VAL_contract_administration")

    def test_new_autonomy_keeps_distinct_color_and_isolated_levels(self):
        from tools.tests.test_adiscord_stp_preparation import block, parse_clausewitz, scalar
        rows = parse_clausewitz((ROOT / "common/autonomous_states/ADISCORD_contract_clients.txt").read_text(encoding="utf-8"))
        body = next(e.value for e in rows if scalar(e.value, "id") == "autonomy_VAL_contract_administration")
        self.assertEqual(scalar(body, "use_overlord_color"), "no")
        self.assertEqual([e.value for e in block(body, "allowed_levels_filter")], ["autonomy_VAL_contract_administration"])
        mods = block(body, "modifier")
        self.assertEqual(scalar(mods, "cic_to_overlord_factor"), "0.15")
        self.assertEqual(scalar(mods, "mic_to_overlord_factor"), "0.30")
        self.assertIn("151 43 29", (ROOT / "common/countries/NorthernContractAdministration.txt").read_text(encoding="utf-8"))
        for folder in ("", "medium/", "small/"):
            self.assertTrue((ROOT / f"gfx/flags/{folder}NKA.tga").is_file())

    def test_map_check_detects_rgb_changes_with_unchanged_alpha(self):
        import tempfile
        from unittest.mock import patch
        from PIL import Image
        from tools.builders import build_adiscord_val_operations_map as builder
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); output = root / "images"; output.mkdir()
            expected = Image.new("RGBA", (2, 2), (100, 100, 100, 255))
            Image.new("RGBA", (2, 2), (101, 100, 100, 255)).save(output / "VAL_ops_test.png")
            with patch.object(builder, "ROOT", root), patch.object(builder, "OUT", output):
                self.assertTrue(builder.validate_outputs({"VAL_ops_test.png": expected}))
                builder.apply({"VAL_ops_test.png": expected})
                self.assertEqual(builder.validate_outputs({"VAL_ops_test.png": expected}), [])

    def test_volunteers_use_existing_divisions_and_recall_for_the_named_war(self):
        from tools.tests.test_adiscord_stp_preparation import walk
        hosts = self.triggers["VAL_northern_volunteer_host"]
        self.assertEqual([e.value for e in hosts if e.key == "has_war_with"], ["NOD"])
        self.assertEqual({e.value for e in walk(hosts) if e.key == "tag"}, {"YPR", "COF", "TFF", "STS", "STP"})
        decisions = self.getblock(self.parse(DECISIONS_PATH.read_text(encoding="utf-8")), "VAL_northern_war_aid")
        self.assertFalse(any(e.key in ("create_unit", "add_manpower", "add_equipment_to_stockpile")
                             for e in walk(self.getblock(decisions, "VAL_northern_volunteers"))))
        recall = self.getblock(self.parse(EFFECTS_PATH.read_text(encoding="utf-8")), "VAL_reconcile_northern_volunteers")
        for branch in recall:
            if branch.key != "if": continue
            guard = self.getblock(branch.value, "limit")
            self.assertIn("VAL_northern_volunteer_host", [e.key for e in walk(guard)])
            self.assertFalse(any(e.key == "has_war" for e in walk(guard)))

    def test_northern_partition_keeps_resource_states_out_of_subject(self):
        from tools.tests.test_adiscord_stp_preparation import walk
        effect = self.getblock(self.parse(EFFECTS_PATH.read_text(encoding="utf-8")), "VAL_form_northern_administration")
        # Find the post-creation branch; seed branches contain no state scopes.
        body = next(e.value for e in self.getblock(effect, "if")
                    if e.key == "if" and any(x.key == "58" for x in e.value))
        for state in (58, 59, 60, 61, 62, 63, 64, 65):
            district = self.getblock(body, str(state))
            recipient = "VAL" if state in (59, 60, 61) else "NKA"
            self.assertEqual(self.scalar(district, "set_state_controller_to"), recipient)
            transfer = self.getblock(self.getblock(district, "if"), recipient)
            self.assertEqual(self.scalar(transfer, "transfer_state"), str(state))
            self.assertEqual(self.scalar(district, "remove_core_of" if recipient == "VAL" else "add_core_of"), "NKA")
        subject_transfers = [self.scalar(e.value, "transfer_state") for e in walk(effect)
                             if e.key == "NKA" and isinstance(e.value, list)
                             and any(child.key == "transfer_state" for child in e.value)]
        self.assertFalse(set(subject_transfers) & {"59", "60", "61"})
        capital = self.getblock(self.getblock(body, "NKA"), "set_capital")
        self.assertEqual(self.scalar(capital, "state"), "64")

    def test_resource_belt_requires_direct_ownership_and_control(self):
        facts = {(str(state), key, "VAL"): True for state in (59, 60, 61)
                 for key in ("is_owned_by", "is_controlled_by")}
        self.assertTrue(self.match("VAL_northern_resource_belt_owned", facts))
        for state in (59, 60, 61):
            for key in ("is_owned_by", "is_controlled_by"):
                changed = dict(facts)
                changed[str(state), key, "VAL"] = False
                changed[str(state), key, "NKA"] = True
                changed["NKA", "is_subject_of", "VAL"] = True
                self.assertFalse(self.match("VAL_northern_resource_belt_owned", changed))

    def test_northern_peace_does_not_force_war_against_aided_yapert(self):
        facts = {("NOD", "exists", "no"): True}
        for state in (10, 11, 12, 13, 30):
            for key in ("is_owned_by", "is_controlled_by"):
                facts[str(state), key, "VAL"] = True
        for state in (17, 18):
            for key in ("is_owned_by", "is_controlled_by"):
                facts[str(state), key, "YPR"] = True
        facts["YPR", "is_subject", "no"] = True
        self.assertFalse(self.match("VAL_nod_dominated", facts))
        facts["NOD", "variable", "STP_cw_northern_campaign_status"] = 3
        self.assertTrue(self.match("VAL_nod_dominated", facts))
        for changed_key in (("YPR", "has_war_with", "VAL"), ("12", "is_controlled_by", "VAL")):
            changed = dict(facts)
            changed[changed_key] = changed_key[0] == "YPR"
            self.assertFalse(self.match("VAL_nod_dominated", changed))

    def test_independent_republic_exception_cannot_cover_shabrat_capital(self):
        from tools.tests.test_adiscord_stp_preparation import walk, matches_conditions
        exceptions = [e.value for e in walk(self.triggers["VAL_stelander_dominated"])
                      if e.key == "AND" and any(child.key == "is_owned_by" and child.value == "SRP" for child in e.value)]
        self.assertEqual(len(exceptions), 1)
        for state in (1, 2, 3, 28, 29, 43, 44, 45, 46, 53, 88):
            facts = {(str(state), "is_core_of", "SRP"): True,
                     (str(state), "is_owned_by", "SRP"): True,
                     (str(state), "is_controlled_by", "SRP"): True,
                     ("SRP", "is_subject", "no"): True}
            self.assertEqual(matches_conditions(exceptions[0], facts, str(state)),
                             state in (2, 3, 29, 45, 46, 53))
            facts["SRP", "has_war_with", "VAL"] = True
            self.assertFalse(matches_conditions(exceptions[0], facts, str(state)))

    def test_nam_concession_requires_agreement_delivery_and_victory(self):
        facts = {("VAL", "exists", "yes"): True, ("VAL", "has_capitulated", "no"): True,
                 ("VAL", "is_subject", "no"): True,
                 ("VAL", "has_country_flag", "VAL_nam_concession_agreed"): True,
                 ("VAL", "has_country_flag", "VAL_nam_aid_delivered"): True,
                 ("VAL", "has_global_flag", "ADISCORD_nam_resource_war_nam_victory"): True,
                 ("NAM", "exists", "yes"): True, ("NAM", "has_capitulated", "no"): True,
                 ("NAM", "is_subject", "no"): True,
                 ("230", "is_owned_by", "NAM"): True, ("230", "is_controlled_by", "NAM"): True}
        self.assertTrue(self.match("VAL_nam_concession_deliverable", facts))
        for key in facts:
            self.assertFalse(self.match("VAL_nam_concession_deliverable", {**facts, key: False}), key)
        for key in (("VAL", "has_war_with", "NAM"), ("VAL", "has_country_flag", "VAL_nam_concession_granted")):
            self.assertFalse(self.match("VAL_nam_concession_deliverable", {**facts, key: True}))
        from tools.builders.build_adiscord_new_states import REGIONAL_STATE_RESOURCES
        self.assertEqual(REGIONAL_STATE_RESOURCES[230], {"steel": 16})
        self.assertEqual(REGIONAL_STATE_RESOURCES[231], {"steel": 16})
        effects = self.parse(EFFECTS_PATH.read_text(encoding="utf-8"))
        from tools.tests.test_adiscord_stp_preparation import walk
        grant = self.getblock(effects, "VAL_deliver_nam_concession")
        rights = next(e.value for e in walk(grant) if e.key == "give_resource_rights")
        self.assertEqual(self.scalar(rights, "state"), "230")
        self.assertEqual(self.scalar(rights, "receiver"), "VAL")
        self.assertFalse(any(e.key == "transfer_state" for e in walk(grant)))
        events = self.parse((ROOT / "events/ADISCORD_VAL_contract_events.txt").read_text(encoding="utf-8"))
        for eid, gate in (("val_contract.340", "VAL_export_arms_can_accept"), ("val_contract.341", "VAL_export_advisors_can_accept")):
            event = next(e.value for e in events if e.key == "country_event" and self.scalar(e.value, "id") == eid)
            accept = next(e.value for e in event if e.key == "option" and self.scalar(e.value, "name") == "VAL_export_accept")
            self.assertTrue(any(e.key == gate for e in walk(accept)))
            self.assertTrue(any(e.key == "VAL_complete_resource_aid" for e in walk(accept)))
            self.assertFalse(any(e.key == "set_country_flag" and e.value == "VAL_nam_aid_delivered" for e in walk(accept)))

    def test_northern_ultimatum_is_single_and_nod_forecast_respects_alliances(self):
        from dataclasses import replace
        from tools.tests.test_adiscord_stp_preparation import matches_conditions
        decisions = self.parse(DECISIONS_PATH.read_text(encoding="utf-8"))
        frontier = self.getblock(decisions, "VAL_frontier")
        names = {e.key for e in frontier}
        self.assertIn("VAL_frontier_demand_CIN", names)
        self.assertNotIn("VAL_frontier_demand_OSF", names)
        self.assertNotIn("VAL_frontier_demand_APH", names)
        def scope_target(items):
            return [replace(e, value=scope_target(e.value) if isinstance(e.value, list) else "CIN" if e.value == "PREV" else e.value) for e in items]
        gate = scope_target(self.triggers["VAL_frontier_nod_support_possible"])
        facts = {("NOD", "exists", "yes"): True, ("NOD", "has_capitulated", "no"): True,
                 ("NOD", "is_subject", "no"): True, ("CIN", "is_in_faction", "no"): True}
        self.assertTrue(matches_conditions(gate, facts, "CIN"))
        for key in (("NOD", "has_war_with", "CIN"), ("NOD", "is_in_faction_with", "VAL")):
            self.assertFalse(matches_conditions(gate, {**facts, key: True}, "CIN"))
        rival = {**facts, ("CIN", "is_in_faction", "no"): False}
        self.assertFalse(matches_conditions(gate, rival, "CIN"))
        self.assertTrue(matches_conditions(gate, {**rival, ("CIN", "is_in_faction_with", "NOD"): True}, "CIN"))

    def test_resource_war_contracts_require_focus_consent_and_actual_personnel(self):
        for tag in ("NAM", "EFL"):
            facts = {(tag, "exists", "yes"): True, (tag, "has_capitulated", "no"): True,
                     (tag, "has_war", "yes"): True, (tag, "ADISCORD_economy_can_spend_100", "yes"): True,
                     (tag, "has_country_flag", "VAL_export_offer_advisors"): True,
                     (tag, "has_war_with", "event_target:VAL_advisor_enemy"): True,
                     ("VAL", "exists", "yes"): True, ("VAL", "has_capitulated", "no"): True,
                     ("VAL", "has_country_flag", "VAL_export_offer_pending"): True,
                     ("VAL", "numeric", "command_power"): 25,
                     ("VAL", "numeric", "has_manpower"): 2000,
                     ("VAL", "has_completed_focus", "VAL_Resource_War_Contracts"): True}
            self.assertTrue(self.match("VAL_export_advisors_can_accept", facts, tag))
            for amount in (0, 1999.9, 2000, 2001):
                self.assertEqual(self.match("VAL_export_advisors_can_accept", {**facts, ("VAL", "numeric", "has_manpower"): amount}, tag), amount >= 2000)
            for key in (("VAL", "has_completed_focus", "VAL_Resource_War_Contracts"), (tag, "ADISCORD_economy_can_spend_100", "yes"), (tag, "has_country_flag", "VAL_export_offer_advisors")):
                self.assertFalse(self.match("VAL_export_advisors_can_accept", {**facts, key: False}, tag))
        from tools.tests.test_adiscord_stp_preparation import walk
        events = self.parse((ROOT / "events/ADISCORD_VAL_contract_events.txt").read_text(encoding="utf-8"))
        event = next(e.value for e in events if e.key == "country_event" and self.scalar(e.value, "id") == "val_contract.341")
        manpower = [e.value for e in walk(event) if e.key == "add_manpower"]
        self.assertEqual(sorted(manpower), ["-2000", "2000"])
        self.assertTrue(any(e.key == "VAL_export_advisors_can_accept" for e in walk(event)))

    def test_subjects_join_existing_val_wars_without_declarations(self):
        from tools.tests.test_adiscord_stp_preparation import walk
        effects = self.parse(EFFECTS_PATH.read_text(encoding="utf-8"))
        call = self.getblock(effects, "VAL_call_subjects_to_wars")
        dispatch = self.getblock(call, "if")
        self.assertIn("VAL_subject_war_dispatch_active", [e.value for e in walk(self.getblock(dispatch, "limit"))])
        self.assertEqual(self.scalar(dispatch, "set_country_flag"), "VAL_subject_war_dispatch_active")
        self.assertEqual(self.scalar(dispatch, "clr_country_flag"), "VAL_subject_war_dispatch_active")

        joins = [e.value for e in walk(call) if e.key == "add_to_war"]
        pairs = {(self.scalar(j, "targeted_alliance"), self.scalar(j, "enemy")) for j in joins}
        self.assertIn(("event_target:VAL_subject_war_leader", "event_target:VAL_subject_war_enemy"), pairs)
        self.assertIn(("VAL", "event_target:VAL_subject_war_enemy"), pairs)
        self.assertFalse(any(e.key == "declare_war_on" for e in walk(call)))

        decisions = self.parse(DECISIONS_PATH.read_text(encoding="utf-8"))
        campaign = next(e.value for e in walk(decisions) if e.key == "VAL_campaign_against_stelander")
        self.assertTrue(any(e.key == "VAL_call_subjects_to_wars" for e in walk(campaign)))
        revanche = self.getblock(effects, "VAL_council_begin_revanche")
        self.assertTrue(any(e.key == "VAL_call_subjects_to_wars" for e in walk(revanche)))

        hooks = self.getblock(self.parse(ON_ACTIONS_PATH.read_text(encoding="utf-8")), "on_actions")
        relation = self.getblock(hooks, "on_war_relation_added")
        relation_text = str([(e.key, e.value) for e in walk(relation)])
        self.assertIn("is_subject_of', 'VAL", relation_text)
        self.assertIn("VAL_call_subjects_to_wars", [e.key for e in walk(relation)])
        for hook_name in ("on_startup", "on_puppet"):
            self.assertTrue(any(e.key == "VAL_call_subjects_to_wars" for e in walk(self.getblock(hooks, hook_name))), hook_name)

    def test_vorkerland_uses_paid_orders_instead_of_gifts(self):
        trigger_source = (ROOT / "common/scripted_triggers/ADISCORD_VAL_rework_triggers.txt").read_text(encoding="utf-8")
        decision_source = DECISIONS_PATH.read_text(encoding="utf-8")
        category_source = (ROOT / "common/decisions/categories/ADISCORD_VAL_rework_categories.txt").read_text(encoding="utf-8")
        event_source = (ROOT / "events/ADISCORD_VAL_contract_events.txt").read_text(encoding="utf-8")
        self.assertNotIn("VAL_can_aid_vorkerland", trigger_source)
        self.assertNotIn("VAL_partner_gifts_visible", trigger_source)
        self.assertNotIn("VAL_vorkerland_aid", decision_source)
        self.assertNotIn("VAL_vorkerland_aid", category_source)
        self.assertNotIn("val_contract.409", event_source)
        self.assertNotIn("VAL_aid_wrk_", event_source)
        self.assertIn("tag = WRK", trigger_source)
        self.assertIn("VAL_trade_route_vorkerland_open", trigger_source)
        self.assertIn("VAL_order_can_offer", event_source)
        self.assertIn("VAL_order_can_accept", event_source)
        gui = self.parse((ROOT / "common/scripted_guis/ADISCORD_VAL_operations_scripted_gui.txt").read_text(encoding="utf-8"))
        self.assertFalse(any(e.key == "ADISCORD_VAL_vorkerland_aid_panel" for e in self.getblock(gui, "scripted_gui")))
        self.assertTrue(any(e.key == "ADISCORD_VAL_trade_routes_panel" for e in self.getblock(gui, "scripted_gui")))

    def test_bezhaysk_operation_requires_stelander_defeat_and_a_valid_target(self):
        facts = {("VAL", "tag", "VAL"): True,
                 ("VAL", "has_capitulated", "no"): True,
                 ("VAL", "is_subject", "no"): True,
                 ("VAL", "has_war", "no"): True,
                 ("VAL", "VAL_stelander_dominated", "yes"): True,
                 ("BJK", "exists", "yes"): True,
                 ("BJK", "has_capitulated", "no"): True,
                 ("BJK", "is_subject", "no"): True}
        from tools.tests.test_adiscord_stp_preparation import matches_conditions
        gate = self.triggers["VAL_can_attack_bezhaysk"]
        self.assertTrue(matches_conditions(gate, facts, "VAL"))
        for key in facts:
            if key == ("VAL", "tag", "VAL"):
                continue
            changed = dict(facts); changed[key] = False
            self.assertFalse(matches_conditions(gate, changed, "VAL"), key)
        self.assertFalse(matches_conditions(gate, {**facts, ("BJK", "is_in_faction_with", "VAL"): True}, "VAL"))
        tree = self.getblock(self.parse(FOCUSES_PATH.read_text(encoding="utf-8")), "focus_tree")
        focuses = {self.scalar(e.value, "id"): e.value for e in tree if e.key == "focus"}
        focus = focuses["VAL_Bezhaysk_Operation"]
        self.assertEqual(self.scalar(self.getblock(focus, "prerequisite"), "focus"), "VAL_Contracts_Outlive_Kings")
        self.assertEqual(self.scalar(focus, "cancel_if_invalid"), "yes")
        reward = self.getblock(self.getblock(focus, "completion_reward"), "if")
        self.assertEqual(self.scalar(self.getblock(reward, "limit"), "VAL_can_attack_bezhaysk"), "yes")
        self.assertEqual(self.scalar(self.getblock(reward, "declare_war_on"), "target"), "BJK")
        positions = [(self.scalar(b, "x"), self.scalar(b, "y")) for b in focuses.values()]
        self.assertEqual(len(positions), len(set(positions)))
        self.assertLessEqual(max(int(y) for x, y in positions), 28)

    def test_occidian_sources_require_an_unsettled_award_or_our_territory(self):
        for state in (43, 44, 45, 88):
            facts = {(str(state), "is_owned_by", "SRP"): True,
                     (str(state), "is_controlled_by", "SRP"): True,
                     ("SRP", "has_war", "no"): True, ("SRP", "is_subject", "no"): True}
            self.assertFalse(self.match("VAL_occidian_state_available", facts, str(state)))
            facts["VAL", "has_country_flag", "VAL_cw_settled"] = True
            self.assertFalse(self.match("VAL_occidian_state_available", facts, str(state)))
            facts["VAL", "has_country_flag", "VAL_cw_entered"] = True
            self.assertFalse(self.match("VAL_occidian_state_available", facts, str(state)))
            facts["VAL", "has_country_flag", "VAL_occidian_settlement_pending"] = True
            facts["VAL", "has_country_flag", "VAL_cw_entered"] = False
            self.assertTrue(self.match("VAL_occidian_state_available", facts, str(state)))
            facts["SRP", "has_war", "no"] = False
            self.assertFalse(self.match("VAL_occidian_state_available", facts, str(state)))
            facts["SRP", "has_war", "no"] = True
            self.assertTrue(self.match("VAL_occidian_state_available", facts, str(state)))
            facts[str(state), "is_controlled_by", "SRP"] = False
            facts[str(state), "is_controlled_by", "NOD"] = True
            self.assertFalse(self.match("VAL_occidian_state_available", facts, str(state)))

    def test_occidian_integration_stops_on_war_loss_or_independence(self):
        facts = {("VAL", "has_capitulated", "no"): True, ("VAL", "is_subject", "no"): True,
                 ("OCA", "exists", "yes"): True, ("OCA", "is_subject_of", "VAL"): True,
                 ("OCA", "has_capitulated", "no"): True, ("OCA", "has_war", "no"): True}
        for state in (43, 44, 45, 88):
            for key in ("is_owned_by", "is_controlled_by"):
                facts[str(state), key, "OCA"] = True
        self.assertTrue(self.match("VAL_occidian_administration_secured", facts))
        for key in facts:
            changed = dict(facts)
            changed[key] = False
            self.assertEqual(self.match("VAL_occidian_administration_secured", changed),
                             key == ("45", "is_owned_by", "OCA"), key)

        for owner in ("STP", "STS"):
            changed = dict(facts)
            changed["45", "is_owned_by", "OCA"] = False
            changed["45", "is_controlled_by", "OCA"] = False
            changed["45", "is_owned_by", owner] = True
            changed["45", "is_controlled_by", owner] = True
            self.assertTrue(self.match("VAL_occidian_administration_secured", changed))

    def test_pending_occidian_settlement_reopens_after_external_war(self):
        from tools.tests.test_adiscord_stp_preparation import matches_conditions, walk
        facts = {("VAL", "has_capitulated", "no"): True, ("VAL", "is_subject", "no"): True,
                 ("VAL", "has_country_flag", "VAL_occidian_settlement_pending"): True,
                 ("VAL", "has_completed_focus", "VAL_The_Steel_Contract"): True,
                 ("OCA", "exists", "no"): True, ("SRP", "is_subject", "no"): True,
                 ("SRP", "variable", "num_owned_states"): 4}
        for state in (43, 44, 45, 88):
            facts[str(state), "owner"] = "SRP"
            facts[str(state), "is_owned_by", "SRP"] = True
            facts[str(state), "is_controlled_by", "SRP"] = True
        self.assertFalse(self.match("VAL_can_form_occidian_administration", facts))
        facts["SRP", "has_war", "no"] = True
        self.assertTrue(self.match("VAL_can_form_occidian_administration", facts))
        decisions = self.parse(DECISIONS_PATH.read_text(encoding="utf-8"))
        decision = next(e.value for e in walk(decisions) if e.key == "VAL_create_occidian_administration")
        self.assertTrue(matches_conditions(self.getblock(decision, "visible"), facts, "VAL"))
        categories = self.parse((ROOT / "common/decisions/categories/ADISCORD_VAL_rework_categories.txt").read_text(encoding="utf-8"))
        category = self.getblock(categories, "VAL_frontier")
        self.assertTrue(matches_conditions(self.getblock(category, "visible"), facts, "VAL"))
        facts["VAL", "has_country_flag", "VAL_occidian_settlement_pending"] = False
        self.assertFalse(self.match("VAL_can_form_occidian_administration", facts))
        self.assertFalse(matches_conditions(self.getblock(decision, "visible"), facts, "VAL"))
        formation = self.getblock(self.parse(EFFECTS_PATH.read_text(encoding="utf-8")), "VAL_form_occidian_administration")
        clearing = [e.value for e in walk(formation) if e.key == "clr_country_flag"]
        self.assertIn("VAL_occidian_settlement_pending", clearing)
        on_actions = read_country_on_actions(ON_ACTIONS_PATH, 'kefreyt')
        self.assertRegex(on_actions, r"limit\s*=\s*\{\s*tag\s*=\s*VAL\s*\}\s*clr_country_flag\s*=\s*VAL_occidian_settlement_pending")

    def test_occidian_lifecycle_bounds_land_preserves_armies_and_takes_time(self):
        from tools.tests.test_adiscord_stp_preparation import walk
        effects = self.parse(EFFECTS_PATH.read_text(encoding="utf-8"))
        rights = self.getblock(effects, "VAL_reconcile_occidian_resource_rights")
        grants = [
            (self.scalar(e.value, "receiver"), self.scalar(e.value, "state"))
            for e in walk(rights)
            if e.key == "give_resource_rights"
        ]
        self.assertEqual(
            {state for receiver, state in grants if receiver == "VAL"},
            {"43", "44", "45", "88"},
        )
        self.assertEqual(
            {e.value for e in walk(rights) if e.key == "remove_resource_rights"},
            {"43", "44", "45", "88"},
        )
        formation = self.getblock(effects, "VAL_form_occidian_administration")
        integration = self.getblock(effects, "VAL_integrate_occidia")
        honor_livonn = self.getblock(effects, "VAL_cw_honor_livonn_agreement")
        for body in (formation, integration, honor_livonn):
            self.assertIn(
                "VAL_reconcile_occidian_resource_rights",
                [e.key for e in walk(body)],
            )
        on_actions = read_country_on_actions(ON_ACTIONS_PATH, "kefreyt")
        self.assertIn("VAL_reconcile_occidian_resource_rights = yes", on_actions)
        self.assertIn("OR = { state = 43 state = 44 state = 45 state = 88 }", on_actions)

        for name, target in (("VAL_form_occidian_administration", "SRP"), ("VAL_integrate_occidia", "OCA")):
            body = self.getblock(effects, name)
            transfers = {e.value for e in walk(body) if e.key == "transfer_state"}
            self.assertEqual(transfers, {"43", "44", "45", "88"})
            annex = next(e.value for e in walk(body) if e.key == "annex_country")
            self.assertEqual(self.scalar(annex, "target"), target)
            self.assertEqual(self.scalar(annex, "transfer_troops"), "yes")
            guards = [self.getblock(e.value, "limit") for e in walk(body) if e.key == "if"]
            self.assertTrue(any(e.key == "VAL_only_occidian_states" for guard in guards for e in walk(guard)))
        tree = self.getblock(self.parse(FOCUSES_PATH.read_text(encoding="utf-8")), "focus_tree")
        focuses = {self.scalar(e.value, "id"): e.value for e in tree if e.key == "focus"}
        claims = focuses["VAL_Occidian_Claims_Commission"]
        self.assertEqual(self.scalar(claims, "cost"), "3")
        self.assertEqual(self.scalar(claims, "cancel_if_invalid"), "yes")
        claims_available = self.getblock(claims, "available")
        self.assertIn("VAL_occidia_secured", [e.key for e in walk(claims_available)])
        self.assertIn(
            "VAL_cw_livonn_settlement_pending",
            [e.value for e in walk(claims_available) if e.key == "has_country_flag"],
        )
        reward = self.getblock(claims, "completion_reward")
        for state_id in ("43", "44", "88"):
            state = next(e.value for e in reward if e.key == state_id)
            self.assertIn("VAL", [e.value for e in walk(state) if e.key == "add_claim_by"], state_id)
        livonn = next(e.value for e in reward if e.key == "45")
        self.assertIn("VAL_livonn_available_for_administration", [e.key for e in walk(livonn)])
        self.assertIn("VAL", [e.value for e in walk(livonn) if e.key == "add_claim_by"])

        for name in ("VAL_Occidian_Registries", "VAL_Integrate_Occidia"):
            self.assertEqual(self.scalar(focuses[name], "cost"), "5")
            self.assertEqual(self.scalar(focuses[name], "cancel_if_invalid"), "yes")
            self.assertIn("VAL_occidian_administration_secured", [e.key for e in walk(self.getblock(focuses[name], "available"))])
        self.assertEqual(self.scalar(self.getblock(focuses["VAL_Occidian_Registries"], "prerequisite"), "focus"), "VAL_Occidian_Claims_Commission")
        self.assertEqual(self.scalar(self.getblock(focuses["VAL_Integrate_Occidia"], "prerequisite"), "focus"), "VAL_Occidian_Registries")

    def test_subject_capital_capture_counts_only_for_an_actual_val_war(self):
        from dataclasses import replace
        from tools.tests.test_adiscord_stp_preparation import selected_effects
        source = self.parse((ROOT / "common/scripted_effects/ADISCORD_STP_scripted_effects.txt").read_text(encoding="utf-8"))
        def root_sts(items):
            return [replace(e, key="STS" if e.key == "ROOT" else e.key,
                            value=root_sts(e.value) if isinstance(e.value, list) else "STS" if e.value == "ROOT" else e.value)
                    for e in items]
        snapshot = root_sts(self.getblock(source, "STP_cw_cache_state_occupier"))
        for subject, participant, val_war in ((True, True, True), (False, True, True), (True, False, True), (True, True, False)):
            facts = {("1", "controller"): "NKA", ("NKA", "is_subject_of", "VAL"): subject,
                     ("NKA", "has_war_with", "STS"): participant, ("VAL", "has_war_with", "STS"): val_war}
            assignments = [(scope, self.scalar(e.value, "value")) for scope, e in selected_effects(snapshot, facts, "1") if e.key == "set_variable"]
            self.assertEqual(assignments, [("STS", "5")] if subject and participant and val_war else [])


class ValRegionalIntegrationTests(unittest.TestCase):
    def test_nationalisation_expands_one_adjacent_core_at_a_time(self):
        from tools.tests.test_adiscord_stp_preparation import block, parse_clausewitz

        definitions = parse_clausewitz(DECISIONS_PATH.read_text(encoding="utf-8"))
        postwar = block(definitions, "VAL_frontier")
        nationalise = block(postwar, "VAL_nationalise_region")
        self.assertTrue(nationalise)
        self.assertFalse(any(e.key == "VAL_establish_regional_administration" for e in postwar))

        decisions_text = DECISIONS_PATH.read_text(encoding="utf-8")
        trigger_text = (ROOT / "common/scripted_triggers/ADISCORD_VAL_rework_triggers.txt").read_text(encoding="utf-8")
        focus_text = FOCUSES_PATH.read_text(encoding="utf-8")

        decision_block = only_named_block(self, decisions_text, "VAL_nationalise_region")
        target = only_named_block(self, decision_block, "target_trigger")
        self.assertIn("VAL_regional_integration_state_valid = yes", target)
        self.assertNotIn("is_owned_by = ROOT", target)
        self.assertNotIn("is_controlled_by = ROOT", target)

        available = only_named_block(self, decision_block, "available")
        self.assertIn("VAL_regional_integration_target_valid = yes", available)
        self.assertIn("VAL_regional_integration_state_valid = yes", available)
        self.assertIn("NOT = { has_country_flag = VAL_regional_integration_active }", available)
        self.assertNotIn("compliance", decision_block)
        self.assertNotIn("resistance", decision_block)
        self.assertIn("cost = 50", decision_block)
        self.assertIn("days_remove = 120", decision_block)
        self.assertIn("fire_only_once = no", decision_block)
        self.assertIn("add_core_of = ROOT", decision_block)
        self.assertIn("set_country_flag = VAL_regional_integration_active", decision_block)
        self.assertIn("clr_country_flag = VAL_regional_integration_active", decision_block)

        country_trigger = only_named_block(self, trigger_text, "VAL_regional_integration_target_valid")
        self.assertIn("has_war = no", country_trigger)
        self.assertNotIn("FROM =", country_trigger)
        for token in ("is_owned_by", "is_controlled_by", "is_core_of", "any_neighbor_state"):
            self.assertNotIn(token, country_trigger)

        state_trigger = only_named_block(self, trigger_text, "VAL_regional_integration_state_valid")
        for token in ("any_neighbor_state = {", "is_core_of = VAL",
                      "is_owned_by = VAL", "is_controlled_by = VAL",
                      "NOT = { is_core_of = VAL }"):
            self.assertIn(token, state_trigger)

        cancel = only_named_block(self, decision_block, "cancel_trigger")
        self.assertIn("VAL_regional_integration_target_valid = no", cancel)
        self.assertIn("VAL_regional_integration_state_valid = no", cancel)

        conference = next(entry.text for entry in named_block_spans(focus_text, "focus")
                          if re.search(r"\bid\s*=\s*VAL_frontier_conference\b", entry.text))
        reward = only_named_block(self, conference, "completion_reward")
        self.assertRegex(reward, r"unlock_decision_tooltip\s*=\s*\{\s*decision\s*=\s*VAL_nationalise_region\b")
        self.assertNotIn("VAL_establish_regional_administration", reward)


class ValFormationAndCommandTests(unittest.TestCase):
    def test_core_losses_and_returns_do_not_duplicate_rewards(self):
        from dataclasses import replace
        from tools.tests.test_adiscord_stp_preparation import parse_clausewitz, block, scalar, selected_effects
        actions = block(parse_clausewitz(ON_ACTIONS_PATH.read_text(encoding="utf-8")), "on_actions")
        handlers = block(block(actions, "on_state_control_changed"), "effect")[:2]
        facts = {("VAL", "has_country_flag", "fixture_bop_active"): True,
                 ("VAL", "has_war_with", "NOD"): True,
                 ("58", "is_owned_by", "VAL"): True, ("58", "is_core_of", "VAL"): True}
        balance = 0.0

        def callback(new_controller, old_controller):
            nonlocal balance
            scopes = {"ROOT": new_controller, "FROM": old_controller, "FROM.FROM": "58"}
            def expand(items):
                result = []
                for e in items:
                    if e.key == "has_power_balance":
                        result.append(replace(e, key="has_country_flag", value="fixture_bop_active"))
                    else:
                        result.append(replace(e, key=scopes.get(e.key, e.key),
                            value=expand(e.value) if isinstance(e.value, list) else scopes.get(e.value, e.value)))
                return result
            for scope, e in list(selected_effects(expand(handlers), facts, new_controller)):
                if e.key == "add_power_balance_value":
                    self.assertEqual(scope, "VAL")
                    balance += float(scalar(e.value, "value"))
                elif e.key in ("set_state_flag", "clr_state_flag"):
                    facts[scope, "has_state_flag", e.value] = e.key == "set_state_flag"
                else:
                    self.fail("Unexpected callback effect: " + e.key)
        callback("NOD", "VAL")
        self.assertAlmostEqual(balance, -.10)
        callback("NOD", "VAL")
        self.assertAlmostEqual(balance, -.10)
        callback("VAL", "NOD")
        self.assertAlmostEqual(balance, -.05)
        callback("VAL", "NOD")
        self.assertAlmostEqual(balance, -.05)
        facts["VAL", "has_war_with", "NOD"] = False
        callback("NOD", "VAL")
        self.assertAlmostEqual(balance, -.05)

    def test_formation_requires_campaign_and_actual_border_ownership(self):
        from tools.tests.test_adiscord_stp_preparation import parse_clausewitz, block, matches_conditions
        source = (ROOT / "common/scripted_triggers/ADISCORD_VAL_rework_triggers.txt").read_text(encoding="utf-8")
        gate = block(parse_clausewitz(source), "VAL_can_proclaim_commonwealth")
        facts = {("VAL", "has_completed_focus", "VAL_Contracts_Outlive_Kings"): True,
                 ("VAL", "VAL_campaign_objectives_met", "yes"): True,
                 ("VAL", "numeric", "stability"): 0.50,
                 **{(state, check, "VAL"): True for state in ("29", "46") for check in ("is_owned_by", "is_controlled_by")}}
        self.assertTrue(matches_conditions(gate, facts, "VAL"))
        for key, value in [(key, False) for key in facts if key[1] != "numeric"] + [
                (("VAL", "numeric", "stability"), 0.499),
                (("VAL", "has_cosmetic_tag", "VAL_commonwealth"), True)]:
            self.assertFalse(matches_conditions(gate, {**facts, key: value}, "VAL"), key)
        effects = EFFECTS_PATH.read_text(encoding="utf-8")
        self.assertNotIn("VAL_adopt_commonwealth = yes", effects, "Settlement must not form the country automatically")
        decisions = DECISIONS_PATH.read_text(encoding="utf-8")
        self.assertEqual(decisions.count("VAL_adopt_commonwealth = yes"), 1)

    def test_command_ranges_cover_scale_and_crises_have_costs(self):
        from tools.tests.test_adiscord_stp_preparation import parse_clausewitz, block, scalar, walk
        bop = parse_clausewitz((ROOT / "common/bop/VAL.txt").read_text(encoding="utf-8"))
        ranges = [e.value for e in walk(bop) if e.key == "range"]
        intervals = sorted((float(scalar(r, "min")), float(scalar(r, "max"))) for r in ranges)
        self.assertEqual(len(intervals), 7)
        self.assertEqual(intervals[0][0], -1)
        self.assertEqual(intervals[-1][1], 1)
        for left, right in zip(intervals, intervals[1:]):
            self.assertEqual(left[1], right[0])
        for r in ranges:
            if scalar(r, "id").endswith("dominance"):
                self.assertLess(float(scalar(block(r, "modifier"), "stability_factor")), 0)
        decisions = block(parse_clausewitz(DECISIONS_PATH.read_text(encoding="utf-8")), "VAL_command_balance_category")
        for decision in decisions:
            self.assertGreater(float(scalar(decision.value, "cost")), 0)
            self.assertGreater(float(scalar(decision.value, "days_re_enable")), 0)
        init = only_named_block(self, EFFECTS_PATH.read_text(encoding="utf-8"), "VAL_initialize_arsenal_recovery")
        self.assertIn("VAL_refresh_industrial_economy = yes", init)


class ValFocusRewardBalanceTests(unittest.TestCase):
    """Validate authored rewards and lifecycle branches, not native spawning."""

    PACKAGES = (
        ("VAL_Border_Survey_Corps", "VAL_raise_mountain_contractors",
         "VAL_mountain_contractors_raised", "Kefreyt Mountain Contractors", "mountaineers"),
        ("VAL_Reserve_Battalions", "VAL_raise_reserve_battalions",
         "VAL_reserve_battalions_raised", "Kefreyt Reserve Infantry", "infantry"),
    )

    @classmethod
    def setUpClass(cls):
        from tools.tests.test_adiscord_stp_preparation import parse_clausewitz, block, scalar
        cls.effects = parse_clausewitz(EFFECTS_PATH.read_text(encoding="utf-8"))
        tree = block(parse_clausewitz(FOCUSES_PATH.read_text(encoding="utf-8")), "focus_tree")
        cls.focuses = {scalar(e.value, "id"): e.value for e in tree if e.key == "focus"}

    def test_manpower_rewards_support_real_formation_scale(self):
        from tools.tests.test_adiscord_stp_preparation import block, walk
        expected = {"VAL_Gromovs_Assault_Tables": 6000, "VAL_Morns_Supply_Trains": 4000,
                    "VAL_Field_Surgeons": 8000, "VAL_Dead_Villages_Still_Count": 5000,
                    "VAL_Reserve_Battalions": 4000, "VAL_Operational_Reserves": 10000}
        for focus, amount in expected.items():
            with self.subTest(focus=focus):
                rewards = block(self.focuses[focus], "completion_reward")
                self.assertEqual([int(e.value) for e in walk(rewards) if e.key == "add_manpower"], [amount])

    def test_logistics_rewards_deliver_actual_transport_and_replacements(self):
        from tools.tests.test_adiscord_stp_preparation import block, scalar, walk
        for focus, expected in (
            ("VAL_Motorized_Columns", {"motorized_equipment": 500}),
            ("VAL_Logistics_Command", {"support_equipment": 600, "motorized_equipment": 200}),
            ("VAL_Operational_Reserves", {"infantry_equipment": 45000,
                "ADISCORD_squad_weapons_equipment": 144, "support_equipment": 120}),
        ):
            with self.subTest(focus=focus):
                actual = {scalar(e.value, "type"): int(scalar(e.value, "amount"))
                          for e in walk(block(self.focuses[focus], "completion_reward"))
                          if e.key == "add_equipment_to_stockpile"}
                self.assertEqual(actual, expected)

    def test_civilian_alternative_keeps_a_material_reward(self):
        from tools.tests.test_adiscord_stp_preparation import block, selected_effects
        for focus, flags in (("VAL_Price_Of_Loyalty", {}),
                             ("VAL_Dead_Villages_Still_Count", {
                                 ("VAL", "has_country_flag", "VAL_ash_rear_mobilization"): True})):
            selected = list(selected_effects(block(self.focuses[focus], "completion_reward"), flags, "VAL"))
            self.assertIn("ADISCORD_economy_receive_100", [e.key for _, e in selected])
            self.assertNotIn("ADISCORD_economy_receive_15", [e.key for _, e in selected])

    def test_grant_focuses_have_live_territory_gate_and_unchanged_duration(self):
        from tools.tests.test_adiscord_stp_preparation import block, scalar, matches_conditions
        facts = {("VAL", "has_capitulated", "no"): True,
                 ("VAL", "owns_state", "54"): True, ("VAL", "controls_state", "54"): True}
        for focus, effect, _, _, _ in self.PACKAGES:
            with self.subTest(focus=focus):
                self.assertEqual(scalar(block(self.focuses[focus], "completion_reward"), effect), "yes")
                self.assertEqual(scalar(self.focuses[focus], "cost"),
                                 "2" if focus == "VAL_Border_Survey_Corps" else "5")
                available = block(self.focuses[focus], "available")
                self.assertTrue(matches_conditions(available, facts, "VAL"))
                self.assertFalse(matches_conditions(available, facts | {("VAL", "controls_state", "54"): False}, "VAL"))
                self.assertFalse(matches_conditions(available, facts | {("VAL", "has_capitulated", "no"): False}, "VAL"))

    def test_formations_are_once_only_and_do_not_depend_on_stockpile_or_capital(self):
        from tools.tests.test_adiscord_stp_preparation import block, scalar, selected_effects, walk
        for _, effect, receipt, _, _ in self.PACKAGES:
            with self.subTest(effect=effect):
                facts = {("VAL", "has_capitulated", "no"): True,
                         ("VAL", "owns_state", "54"): True, ("VAL", "controls_state", "54"): True}
                body = block(self.effects, effect)
                grants = []
                for _ in range(2):
                    for scope, e in selected_effects(body, facts, "VAL"):
                        if e.key == "set_country_flag":
                            facts[scope, "has_country_flag", e.value] = True
                        elif e.key == "random_owned_controlled_state":
                            grants.append(e)
                self.assertEqual(len(grants), 1)
                spawn = block(grants[0].value, "create_unit")
                self.assertEqual(scalar(spawn, "owner"), "PREV")
                self.assertEqual(scalar(spawn, "count"), "2")
                self.assertEqual(scalar(spawn, "allow_spawning_on_enemy_provs"), "no")
                self.assertTrue(facts.get(("VAL", "has_country_flag", receipt)))
                self.assertFalse(any(e.key in {"add_manpower", "add_equipment_to_stockpile", "capital_scope"}
                                     for e in walk(body)))
                for change in ({("VAL", "controls_state", "54"): False},
                               {("VAL", "has_capitulated", "no"): False}):
                    failed = facts | {("VAL", "has_country_flag", receipt): False} | change
                    selected = list(selected_effects(body, failed, "VAL"))
                    self.assertFalse(any(e.key in {"random_owned_controlled_state", "set_country_flag"}
                                         for _, e in selected))
                self.assertFalse(any(e.key == "random_owned_controlled_state"
                                     for _, e in selected_effects(body, facts, "STP")))

    def test_fixed_templates_match_personnel_and_equipment_promised(self):
        from tools.tests.test_adiscord_stp_preparation import parse_clausewitz, block, scalar, walk
        units = block(parse_clausewitz((ROOT / "common/units/ADISCORD_land_units.txt").read_text()), "sub_units")
        for _, effect, _, name, battalion in self.PACKAGES:
            with self.subTest(effect=effect):
                body = block(self.effects, effect)
                template = next((e.value for e in walk(body) if e.key == "division_template"), None)
                self.assertIsNotNone(template, "the reward must create its template in existing saves")
                self.assertEqual(scalar(template, "name"), name)
                self.assertEqual(scalar(template, "is_locked"), "yes")
                self.assertEqual(scalar(template, "force_allow_recruiting"), "yes")
                regiments, support = block(template, "regiments"), block(template, "support")
                self.assertEqual([e.key for e in regiments], [battalion] * 6)
                self.assertEqual([e.key for e in support], ["engineer"])
                manpower = 0
                equipment = {}
                for company in regiments + support:
                    definition = block(units, company.key)
                    manpower += int(scalar(definition, "manpower"))
                    for need in block(definition, "need"):
                        equipment[need.key] = equipment.get(need.key, 0) + int(need.value)
                self.assertEqual(manpower, 6300)
                self.assertEqual(equipment, {"infantry_equipment": 5670,
                    "ADISCORD_squad_weapons_equipment": 36 if battalion == "mountaineers" else 48,
                    "support_equipment": 30})
                spawning = next(e.value for e in walk(body) if e.key == "create_unit")
                definition = parse_clausewitz(scalar(spawning, "division"))
                self.assertEqual(scalar(definition, "division_template"), name)
                self.assertEqual(float(scalar(definition, "start_manpower_factor")), 1.0)
                self.assertEqual(float(scalar(definition, "start_equipment_factor")), 1.0)
                self.assertGreaterEqual(float(scalar(definition, "start_experience_factor")), .2)
                self.assertIn("ADISCORD_economy_mark_dirty", [e.key for e in walk(body)])

    def test_formation_replays_cannot_be_scheduled_from_startup(self):
        from tools.tests.test_adiscord_stp_preparation import block, scalar, walk
        on_actions = ON_ACTIONS_PATH.read_text(encoding="utf-8")
        for focus, effect, receipt, _, _ in self.PACKAGES:
            body = block(self.effects, effect)
            self.assertNotIn(effect + " = yes", on_actions)
            self.assertEqual(scalar(body, "custom_effect_tooltip"), effect + "_tt")
            self.assertEqual([e.value for e in walk(body) if e.key == "set_country_flag"], [receipt])
            self.assertFalse(any(e.key in {"country_event", "clr_country_flag"} for e in walk(body)))
            # One real caller, no bonus on each monthly pulse or country initializer.
            self.assertEqual(FOCUSES_PATH.read_text().count(effect + " = yes"), 1, focus)

    def test_mountain_reward_has_matching_persistent_special_forces_capacity(self):
        from tools.tests.test_adiscord_stp_preparation import parse_clausewitz, block, scalar, selected_effects
        source = EFFECTS_PATH.read_text(encoding="utf-8")
        refresh = block(parse_clausewitz(source), "VAL_refresh_contract_modifier")
        field = "VAL_contract_special_forces_min"
        resets = [e for e in refresh if e.key == "set_variable" and scalar(e.value, "var") == field]
        self.assertEqual(len(resets), 1)
        self.assertEqual(scalar(resets[0].value, "value"), "0")
        branches = [e for e in refresh if e.key == "if" and any(
            c.key == "has_country_flag" and c.value == "VAL_border_survey_complete"
            for c in block(e.value, "limit"))]
        self.assertEqual(len(branches), 1)
        for active in (False, True):
            chosen = selected_effects(branches, {("VAL", "has_country_flag", "VAL_border_survey_complete"): active}, "VAL")
            delta = sum(float(scalar(e.value, "value")) for _, e in chosen
                        if e.key == "add_to_variable" and scalar(e.value, "var") == field)
            self.assertEqual(delta, 12 if active else 0)
        dynamic = parse_clausewitz((ROOT / "common/dynamic_modifiers/ADISCORD_VAL_contract_dynamic_modifier.txt").read_text())
        self.assertEqual(scalar(block(dynamic, "VAL_contract_state"), "special_forces_min"), field)
        preview = only_named_block(self, IDEAS_PATH.read_text(), "VAL_border_survey_delta")
        self.assertEqual(scalar(block(block(parse_clausewitz(preview), "VAL_border_survey_delta"), "modifier"),
                                "special_forces_min"), "12")

    def test_new_templates_and_spawn_sites_are_covered_by_the_force_audit(self):
        import json
        audit = json.loads((ROOT / "tools/data/division_template_audit.json").read_text())
        for _, _, _, name, _ in self.PACKAGES:
            rows = [row for row in audit["templates"] if row["technical_name"] == name]
            self.assertEqual(len(rows), 1, name)
            self.assertEqual(rows[0]["computed"]["manpower"], 6300)
            self.assertEqual(rows[0]["source"]["path"], "common/scripted_effects/ADISCORD_VAL_effects.txt")
            refs = [row for row in audit["references"] if row["technical_name"] == name]
            self.assertEqual(len(refs), 1, name)
            self.assertEqual(refs[0]["kind"], "create_unit")
            self.assertEqual(refs[0]["count"], 1)

    def test_formation_tooltips_are_localized_and_match_both_packages(self):
        for language in ("russian", "english"):
            path = ROOT / f"localisation/{language}/ADISCORD_VAL_decisions_l_{language}.yml"
            self.assertTrue(path.read_bytes().startswith(b"\xef\xbb\xbf"))
            source = path.read_text(encoding="utf-8-sig")
            for _, effect, _, _, _ in self.PACKAGES:
                values = re.findall(r'^\s*' + effect + r'_tt:\d*\s+"([^"\n]*)"\s*$', source, re.M)
                self.assertEqual(len(values), 1, effect)
                self.assertIn("6300", values[0])
                self.assertIn("100%", values[0])
                self.assertIn("§Y2", values[0])
                self.assertNotIn(";", values[0])
                self.assertNotIn("—", values[0])


if __name__ == "__main__":
    unittest.main()
