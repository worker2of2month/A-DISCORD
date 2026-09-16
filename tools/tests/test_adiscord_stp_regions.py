from __future__ import annotations

import re
import subprocess
import sys
import unittest
from pathlib import Path

from PIL import Image, ImageChops

from tools.builders import build_adiscord_new_states as state_builder
from tools.builders import build_adiscord_stp_regions_map as regions_map_builder
from tools.lib.adiscord_core_state_balance_manifest import EXPECTED_RESOURCES, TARGET_STATES


ROOT = Path(__file__).resolve().parents[2]
EFFECTS = ROOT / "common/scripted_effects/ADISCORD_STP_scripted_effects.txt"
TRIGGERS = ROOT / "common/scripted_triggers/ADISCORD_STP_scripted_triggers.txt"
DECISIONS = ROOT / "common/decisions/ADISCORD_STP_decisions.txt"
LEGACY_REGIONS_DECISIONS = ROOT / "common/decisions/ADISCORD_STP_region_decisions.txt"
EVENTS = ROOT / "events/ADISCORD_STP_events.txt"
CATEGORIES = ROOT / "common/decisions/categories/ADISCORD_decision_categories_STP.txt"
SCRIPTED_GUI = ROOT / "common/scripted_guis/ADISCORD_STP_regions_scripted_gui.txt"
GUI = ROOT / "interface/ADISCORD_STP_regions.gui"
GFX = ROOT / "interface/ADISCORD_STP_regions.gfx"
LOCALISATION = ROOT / "localisation/russian/ADISCORD_STP_l_russian.yml"
LEGACY_REGIONS_LOCALISATION = ROOT / "localisation/russian/ADISCORD_STP_regions_l_russian.yml"
SHARED_ACTION_EFFECTS = ROOT / "common/scripted_effects/ADISCORD_shared_action_effects.txt"
SHARED_ACTION_TRIGGERS = ROOT / "common/scripted_triggers/ADISCORD_shared_action_triggers.txt"
POLITICS_LOCALISATION = ROOT / "localisation/russian/politics_l_russian.yml"
MAPICONS_GUI = ROOT / "interface/mapicons.gui"
TEXTICON_GFX = ROOT / "interface/modifiericons_texticons.gfx"
COMPACT_INFANTRY_TEXTICON = ROOT / "gfx/texticons/infantry_equipment_texticon.dds"

PARTICIPATING_STATES = (1, 2, 3, 28, 29, 43, 44, 45, 46, 53, 88)
OPERABLE_STATES = (2, 3, 29, 45, 46, 53)
LOCKED_STATES = (1, 28, 43, 44, 88)
LOCAL_FORCE_STATES = (43, 44, 45, 88)
REGIONAL_OPERATION_IDS = (
    "STP_recruit_regional_official",
    "STP_bargain_with_local_councils",
    "STP_prepare_false_trail",
    *(f"STP_region_unique_operation_{state_id}" for state_id in OPERABLE_STATES),
    "STP_cw_sabotage_capital",
    "STP_cw_sabotage_party_industry",
)
INITIAL_BALANCE = {
    1: (100, 0, 0),
    2: (30, 70, 0),
    3: (40, 60, 0),
    28: (0, 100, 0),
    29: (35, 65, 0),
    43: (0, 0, 100),
    44: (0, 0, 100),
    45: (25, 35, 40),
    46: (35, 65, 0),
    53: (55, 45, 0),
    88: (0, 0, 100),
}
STELANDER_RESOURCE_PACKAGE = {
    "steel": 18,
    "aluminium": 3,
    "tungsten": 3,
    "chromium": 2,
}
STELANDER_POPULATION = {
    43: 1_200_000,
    44: 900_000,
    45: 1_200_000,
    88: 650_000,
}
STATUS_FRAMES = (
    "contested",
    "resistance_leaning",
    "resistance_entrenched",
    "party_leaning",
    "party_entrenched",
    "local_leaning",
    "local_dominant",
)


def read(path: Path) -> str:
    if not path.is_file():
        raise AssertionError(f"missing file: {path.relative_to(ROOT)}")
    return path.read_text(encoding="utf-8-sig")


def named_block(text: str, name: str) -> str:
    match = re.search(rf"(?m)^\s*{re.escape(name)}\s*=\s*\{{", text)
    if match is None:
        raise AssertionError(f"missing block: {name}")
    opening = text.find("{", match.start())
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
                return text[match.start() : index + 1]
    raise AssertionError(f"unterminated block: {name}")


def defined_text_block(text: str, name: str) -> str:
    matches: list[str] = []
    for match in re.finditer(r"(?m)^\s*defined_text\s*=\s*\{", text):
        opening = text.find("{", match.start())
        depth = 0
        for index in range(opening, len(text)):
            if text[index] == "{":
                depth += 1
            elif text[index] == "}":
                depth -= 1
                if depth == 0:
                    body = text[match.start() : index + 1]
                    if re.search(rf"(?m)^\s*name\s*=\s*{re.escape(name)}\s*$", body):
                        matches.append(body)
                    break
    if len(matches) != 1:
        raise AssertionError(f"expected one defined_text {name}, found {len(matches)}")
    return matches[0]


def state_scope(block: str, state_id: int) -> str:
    return named_block(block, str(state_id))


def assigned_value(block: str, variable: str) -> int:
    match = re.search(
        rf"set_variable\s*=\s*\{{\s*var\s*=\s*{re.escape(variable)}\s+value\s*=\s*(-?\d+)\s*\}}",
        block,
        re.S,
    )
    if match is None:
        raise AssertionError(f"missing assignment for {variable}")
    return int(match.group(1))


class STPRegionalMechanicsTests(unittest.TestCase):
    def test_late_false_trail_cannot_protect_a_different_inspection(self) -> None:
        operation = named_block(read(DECISIONS), "STP_prepare_false_trail")
        self.assertIn("STP_party_inspection_active", named_block(operation, "cancel_trigger"))
        completion = named_block(operation, "remove_effect")
        self.assertIn("has_state_flag = STP_party_inspection_active", named_block(completion, "limit"))
        self.assertIn("STP_false_trail_in_progress", named_block(operation, "complete_effect"))
        self.assertIn("clr_state_flag = STP_false_trail_in_progress", named_block(operation, "cancel_effect"))
        self.assertIn("clr_state_flag = STP_false_trail_in_progress", completion)

    def test_concession_surrenders_the_administrator_without_destroying_military_assets(self) -> None:
        decision = named_block(read(DECISIONS), "STP_cw_sacrifice_local_contact")
        self.assertIn("has_state_flag = STP_resistance_administration_asset", named_block(decision, "available"))
        paid = named_block(decision, "complete_effect")
        self.assertIn("clr_state_flag = STP_resistance_administration_asset", paid)
        self.assertIn("set_state_flag = STP_inspection_concession_prepared", paid)
        self.assertIn("value = -0.02", paid)
        for asset in ("garrison", "supply", "sabotage"):
            self.assertNotIn(f"clr_state_flag = STP_resistance_{asset}_asset", paid)
        self.assertNotIn("STP_cw_return_preparation_reserves", paid)
        resolver = named_block(read(EFFECTS), "STP_resolve_party_inspection")
        first_guard = named_block(resolver, "limit")
        self.assertIn("NOT = { has_state_flag = STP_inspection_concession_prepared }", first_guard)
        self.assertIn("var = STP_last_party_response value = 9", resolver)
        self.assertIn("clr_state_flag = STP_inspection_concession_prepared", resolver)
        self.assertIn("clr_state_flag = STP_inspection_concession_prepared", named_block(read(EFFECTS), "STP_clear_region_runtime"))

    def test_delay_extends_only_the_existing_inspection_with_a_cooldown(self) -> None:
        decision = named_block(read(DECISIONS), "STP_cw_delay_inspection")
        self.assertIn("cost = 35", decision)
        self.assertIn("days_re_enable = 60", decision)
        reward = named_block(decision, "complete_effect")
        self.assertEqual(reward.count("add_days_mission_timeout"), len(OPERABLE_STATES))
        self.assertEqual(reward.count("days = 14"), len(OPERABLE_STATES))
        self.assertNotIn("activate_mission", reward)
        for state in OPERABLE_STATES:
            self.assertIn(f"has_active_mission = STP_party_inspection_state_{state}", reward)

    def test_counterintelligence_blocks_work_and_lost_assets_can_be_rebuilt(self) -> None:
        gate = named_block(read(TRIGGERS), "STP_region_is_operable")
        self.assertIn("NOT = { has_state_flag = STP_party_counterintelligence_asset }", gate)
        self.assertIn("NOT = { has_state_flag = STP_inspection_concession_prepared }", gate)
        decisions = read(DECISIONS)
        party_check = named_block(decisions, "STP_cw_check_district_command")
        for phase in ("available", "cancel_trigger", "remove_effect"):
            self.assertIn("STP_region_is_operable", named_block(party_check, phase), phase)
            self.assertIn("is_owned_by = ROOT", named_block(party_check, phase), phase)
        for state, asset in ((2, "garrison"), (3, "supply"), (29, "garrison"),
                             (45, "administration"), (46, "supply"), (53, "sabotage")):
            operation = named_block(decisions, f"STP_region_unique_operation_{state}")
            self.assertNotIn("STP_region_unique_operation_done", operation)
            self.assertIn(f"NOT = {{ has_state_flag = STP_resistance_{asset}_asset }}", named_block(operation, "visible"))
            for phase in ("available", "cancel_trigger", "remove_effect"):
                self.assertIn("STP_region_is_operable", named_block(operation, phase), (state, phase))

    def test_supply_depots_give_one_short_army_bonus_before_assets_are_cleared(self) -> None:
        from tools.tests.test_adiscord_stp_preparation import block, parse_clausewitz, scalar, selected_effects

        effects = read(EFFECTS)
        start = named_block(effects, "STP_cw_start")
        begin = named_block(effects, "STP_cw_begin_hostilities")
        materialize = named_block(effects, "STP_cw_materialize_region_assets")
        self.assertNotIn("STP_end_battle_for_stelander = yes", start)
        self.assertNotIn("clr_state_flag = STP_resistance_supply_asset", materialize)
        self.assertEqual(begin.count("idea = STP_cw_prepared_supply_lines"), 1)
        self.assertLess(begin.index("idea = STP_cw_prepared_supply_lines"),
                        begin.index("STP_end_battle_for_stelander = yes"))
        cleanup = named_block(effects, "STP_clear_region_runtime")
        self.assertIn("clr_state_flag = STP_resistance_supply_asset", cleanup)
        body = block(parse_clausewitz(effects), "STP_cw_begin_hostilities")
        base = {("STP", "has_country_flag", "STP_cw_participant"): True,
                ("STS", "exists", "yes"): True}
        for depots in ((), (3,), (46,), (3, 46)):
            for owned in ((), (3,), (46,), (3, 46)):
                for started in (False, True):
                    facts = {**base, ("STP", "has_global_flag", "STP_cw_started"): started}
                    facts.update({(str(state), "has_state_flag", "STP_resistance_supply_asset"): state in depots
                                  for state in (3, 46)})
                    facts.update({(str(state), "is_owned_by", "STS"): state in owned for state in (3, 46)})
                    grants = [(scope, scalar(e.value, "days")) for scope, e in selected_effects(body, facts)
                              if e.key == "add_timed_idea" and scalar(e.value, "idea") == "STP_cw_prepared_supply_lines"]
                    with self.subTest(depots=depots, owned=owned, started=started):
                        self.assertEqual(grants, [("STS", "21")] if set(depots) & set(owned) and not started else [])

    def test_influence_math_handles_requested_edge_balances(self) -> None:
        def shift(balance: tuple[int, int, int], recipient: int, amount: int) -> tuple[int, int, int]:
            values = list(balance)
            donor_order = {
                0: (1, 2),
                1: (0, 2),
                2: (1, 0),
            }[recipient]
            remaining = amount
            for donor in donor_order:
                moved = min(values[donor], remaining)
                values[donor] -= moved
                values[recipient] += moved
                remaining -= moved
            return tuple(values)

        edge_balances = (
            (100, 0, 0),
            (0, 100, 0),
            (0, 0, 100),
            (98, 1, 1),
            (1, 98, 1),
            (1, 1, 98),
            (34, 33, 33),
            (50, 50, 0),
        )
        for balance in edge_balances:
            for recipient in range(3):
                for amount in (1, 3, 6, 8, 10, 12, 100):
                    with self.subTest(balance=balance, recipient=recipient, amount=amount):
                        result = shift(balance, recipient, amount)
                        self.assertEqual(sum(result), 100)
                        self.assertTrue(all(0 <= value <= 100 for value in result))

    def test_regional_decisions_use_existing_stp_file_and_categories(self) -> None:
        self.assertFalse(
            LEGACY_REGIONS_DECISIONS.exists(),
            "regional decisions must not be split into a second STP decisions file",
        )
        decisions = read(DECISIONS)
        elections = named_block(decisions, "STP_elections_in_the_party")
        entry_debug = named_block(elections, "STP_debug_start_battle_for_stelander")
        self.assertIn("country_event = { id = ADISCORD_STP_regions.1 }", entry_debug)

        battle = named_block(decisions, "STP_battle_for_stelander")
        for decision_id in (
            "STP_debug_reset_battle_for_stelander",
            "STP_debug_end_battle_for_stelander",
        ):
            self.assertIn(f"{decision_id} = {{", battle)

        categories = read(CATEGORIES)
        self.assertNotIn("STP_region_debug = {", categories)

        events = read(EVENTS)
        entry = next(
            candidate
            for match in re.finditer(r"(?m)^country_event\s*=", events)
            if "id = ADISCORD_STP_regions.1" in (candidate := named_block(events[match.start():], "country_event"))
        )
        self.assertIn("id = ADISCORD_STP_regions.1", entry)
        self.assertIn("STP_initialize_battle_for_stelander = yes", entry)

    def test_initial_balances_cover_every_stp_state_and_sum_to_one_hundred(self) -> None:
        effects = read(EFFECTS)
        initializer = named_block(effects, "STP_initialize_battle_for_stelander")
        for state_id, expected in INITIAL_BALANCE.items():
            with self.subTest(state=state_id):
                block = state_scope(initializer, state_id)
                actual = tuple(
                    assigned_value(block, variable)
                    for variable in (
                        "STP_resistance_influence",
                        "STP_party_influence",
                        "STP_local_forces_influence",
                    )
                )
                self.assertEqual(actual, expected)
                self.assertEqual(sum(actual), 100)
                self.assertIn("set_state_flag = STP_region_participates", block)

        self.assertEqual(set(INITIAL_BALANCE), set(PARTICIPATING_STATES))
        self.assertEqual(INITIAL_BALANCE[1], (100, 0, 0))
        self.assertEqual(INITIAL_BALANCE[28], (0, 100, 0))
        for state_id in (43, 44, 88):
            self.assertEqual(INITIAL_BALANCE[state_id], (0, 0, 100))
        for state_id in set(PARTICIPATING_STATES) - set(LOCAL_FORCE_STATES):
            self.assertEqual(INITIAL_BALANCE[state_id][2], 0)

    def test_influence_mutators_preserve_the_three_way_invariant(self) -> None:
        effects = read(EFFECTS)
        normalize = named_block(effects, "STP_normalize_region_influence")
        self.assertIn("value = 100", normalize)
        self.assertIn("STP_local_forces_influence", normalize)
        for effect_id, preferred_donor, fallback_donor in (
            ("STP_add_resistance_influence", "STP_party_influence", "STP_local_forces_influence"),
            ("STP_add_party_influence", "STP_resistance_influence", "STP_local_forces_influence"),
            ("STP_add_local_forces_influence", "STP_party_influence", "STP_resistance_influence"),
        ):
            with self.subTest(effect=effect_id):
                block = named_block(effects, effect_id)
                self.assertIn("STP_region_influence_change", block)
                self.assertLess(block.find(preferred_donor), block.rfind(fallback_donor))
                self.assertIn("STP_normalize_region_influence = yes", block)

    def test_status_model_uses_both_lead_and_margin(self) -> None:
        from tools.tests.test_adiscord_stp_preparation import matches_conditions, parse_clausewitz, scalar, walk

        triggers = parse_clausewitz(read(TRIGGERS))
        regional = {entry.key: entry.value for entry in triggers if entry.key.startswith("STP_region_")}
        # Native scripted triggers accept boolean calls, never effect-style macro arguments.
        for body in regional.values():
            for entry in walk(body):
                if entry.key in regional:
                    self.assertIn(entry.value, ("yes", "no"))
        for side, status in (("resistance", 2), ("party", 4), ("local_forces", 6)):
            strongest_id = f"STP_region_{side}_strongest"
            strongest = regional[strongest_id]
            entrenched = regional[f"STP_region_{side}_entrenched"]
            self.assertEqual(scalar(entrenched, strongest_id), "yes")
            rivals = [name for name in ("resistance", "party", "local_forces") if name != side]
            values = {f"STP_{side}_influence": 55,
                      f"STP_{rivals[0]}_influence": 40, f"STP_{rivals[1]}_influence": 5}
            # Compare both rival variables from source, including ties and fractional margins.
            for rival in (name for name in ("resistance", "party", "local_forces") if name != side):
                for rival_value, margin, expected in ((54, 1, True), (55, 0, False), (56, 1, False), (54.5, .5, False)):
                    facts = {("2", "variable", key): value for key, value in values.items()}
                    facts[("2", "variable", f"STP_{rival}_influence")] = rival_value
                    facts[("2", "variable", "STP_region_margin")] = margin
                    with self.subTest(side=side, rival=rival, value=rival_value, margin=margin):
                        self.assertEqual(matches_conditions(strongest, facts, "2"), expected)
            values.update(STP_region_lead=55, STP_region_runner_up=40, STP_region_margin=15, STP_region_status=status)
            facts = {("2", "variable", key): value for key, value in values.items()}
            facts[("2", strongest_id, "yes")] = matches_conditions(strongest, facts, "2")
            self.assertTrue(matches_conditions(entrenched, facts, "2"))
            for key, value in (("STP_region_lead", 54.5), ("STP_region_runner_up", 40.5),
                               ("STP_region_margin", 14.5), ("STP_region_status", status - 1)):
                with self.subTest(side=side, rejected=key):
                    self.assertFalse(matches_conditions(entrenched, {**facts, ("2", "variable", key): value}, "2"))
            self.assertFalse(matches_conditions(entrenched, {**facts, ("2", strongest_id, "yes"): False}, "2"))
        for status in range(7):
            facts = {("2", "variable", "STP_region_status"): status}
            for side, states in (("resistance", (1, 2)), ("party", (3, 4)), ("local_forces", (5, 6))):
                trigger = f"STP_region_{side}_leaning"
                result = matches_conditions(regional[trigger], facts, "2")
                self.assertEqual(result, status in states)
                facts[("2", trigger, "yes")] = result
            self.assertEqual(matches_conditions(regional["STP_region_contested"], facts, "2"), status == 0)

    def test_local_forces_exist_only_in_the_four_agreed_states(self) -> None:
        decisions = read(DECISIONS)
        for decision_id in (
            "STP_recruit_regional_official",
            "STP_prepare_false_trail",
        ):
            block = named_block(decisions, decision_id)
            self.assertIn("state_target = yes", block)
            targets = {int(value) for value in re.findall(r"\b\d+\b", named_block(block, "targets"))}
            expected = set(OPERABLE_STATES) - ({45} if decision_id == "STP_recruit_regional_official" else set())
            self.assertEqual(targets, expected)
            for state_id in LOCKED_STATES:
                self.assertNotRegex(block, rf"(?m)^\s*{state_id}\s*$")

        local_bargain = named_block(decisions, "STP_bargain_with_local_councils")
        targets = {int(value) for value in re.findall(r"\b\d+\b", named_block(local_bargain, "targets"))}
        self.assertEqual(targets, {45})
        self.assertNotIn("STP_add_local_forces_influence", decisions.replace(local_bargain, "", 1))

        for state_id in OPERABLE_STATES:
            self.assertIn(f"STP_region_unique_operation_{state_id} = {{", decisions)

    def test_party_checks_start_with_a_hidden_event_then_chain_forty_day_missions(self) -> None:
        decisions = read(DECISIONS)
        effects = read(EFFECTS)
        events = read(EVENTS)
        self.assertNotIn("on_daily", decisions + effects + events)

        initializer = named_block(effects, "STP_initialize_battle_for_stelander")
        self.assertNotIn("STP_schedule_next_party_inspection = yes", initializer)
        self.assertIn(
            "country_event = { id = ADISCORD_STP_regions.2 days = 21 }",
            initializer,
        )
        self.assertNotIn("STP_initial_party_inspection_delay", decisions + effects)

        initial_delay_event = re.search(
            r"(?ms)^country_event\s*=\s*\{\s*"
            r"id\s*=\s*ADISCORD_STP_regions\.2\b"
            r"(?P<body>.*?)(?=^country_event\s*=|\Z)",
            events,
        )
        self.assertIsNotNone(initial_delay_event)
        initial_delay_body = initial_delay_event.group("body")
        self.assertIn("hidden = yes", initial_delay_body)
        self.assertIn("is_triggered_only = yes", initial_delay_body)
        self.assertIn("has_country_flag = STP_battle_for_stelander_active", initial_delay_body)
        for state_id in OPERABLE_STATES:
            self.assertRegex(
                initial_delay_body,
                rf"NOT\s*=\s*\{{\s*has_active_mission\s*=\s*"
                rf"STP_party_inspection_state_{state_id}\s*\}}",
            )
        self.assertIn("STP_schedule_next_party_inspection = yes", initial_delay_body)

        shutdown = named_block(effects, "STP_end_battle_for_stelander")
        for state_id in OPERABLE_STATES:
            mission = named_block(decisions, f"STP_party_inspection_state_{state_id}")
            self.assertIn("days_mission_timeout = 40", mission)
            self.assertIn("selectable_mission = no", mission)
            self.assertIn(f"var = STP_last_inspection_state value = {state_id}", mission)
            self.assertIn(f"{state_id} = {{ STP_resolve_party_inspection = yes }}", mission)
            self.assertIn(
                "STP_schedule_next_party_inspection = yes",
                named_block(named_block(mission, "timeout_effect"), "hidden_effect"),
            )
        scheduler = named_block(effects, "STP_schedule_next_party_inspection")
        opener = named_block(effects, "STP_cw_open_one_party_inspection")
        self.assertIn("STP_cw_open_one_party_inspection = yes", scheduler)
        self.assertIn("STP_cw_second_inspection_unlocked = yes", scheduler)
        self.assertEqual(scheduler.count("STP_cw_open_one_party_inspection = yes"), 2)
        self.assertIn("set_country_flag = STP_cw_inspection_chain_open", initial_delay_body)
        for state_id in OPERABLE_STATES:
            self.assertIn(f"activate_mission = STP_party_inspection_state_{state_id}", opener)
            self.assertIn(
                f"var = STP_last_inspection_state value = {state_id} compare = equals",
                opener,
            )
            self.assertIn(f"{state_id} = {{ STP_region_has_detectable_assets = yes }}", opener)
            self.assertIn(f"has_active_mission = STP_party_inspection_state_{state_id}", opener)
            self.assertIn(
                f"{state_id} = {{ has_state_flag = STP_party_inspection_active }}",
                opener,
            )

    def test_inspections_wait_for_timeout_and_highlight_their_fixed_district(self) -> None:
        from tools.tests.test_adiscord_stp_preparation import block, matches_conditions, parse_clausewitz, walk

        category = block(parse_clausewitz(read(DECISIONS)), "STP_battle_for_stelander")
        facts = {
            ("STP", "has_country_flag", "STP_sided_with_Maksim_flag"): True,
            ("STP", "has_country_flag", "STP_battle_for_stelander_active"): True,
        }
        for state_id in OPERABLE_STATES:
            mission = block(category, f"STP_party_inspection_state_{state_id}")
            goal = next((entry.value for entry in mission if entry.key == "available"), [])
            with self.subTest(state=state_id, contract="timeout owns the result"):
                self.assertFalse(matches_conditions(goal, facts),
                                 "an empty or satisfied mission goal completes before timeout and stops the inspection chain")
            with self.subTest(state=state_id, contract="fixed map target"):
                targets = [entry.value for entry in walk(mission) if entry.key == "highlight_state_targets"]
                self.assertEqual(len(targets), 1)
                self.assertEqual([(entry.key, entry.value) for entry in targets[0]], [("state", str(state_id))])

    def test_regional_operations_use_expandable_variable_slots(self) -> None:
        decisions = read(DECISIONS)
        effects = read(EFFECTS)
        triggers = read(TRIGGERS)

        slot_trigger = named_block(triggers, "STP_has_political_action_slot")
        self.assertIn("var = STP_political_action_slots_available", slot_trigger)
        self.assertIn("value = 1", slot_trigger)
        self.assertIn("compare = greater_than_or_equals", slot_trigger)

        grant = named_block(effects, "STP_political_action_slot_grant")
        self.assertIn("var = STP_political_action_slots_total value = 1", grant)
        self.assertIn("var = STP_political_action_slots_available value = 1", grant)
        consume = named_block(effects, "STP_political_action_slot_consume")
        self.assertIn("STP_has_political_action_slot = yes", consume)
        self.assertIn("var = STP_political_action_slots_available value = -1", consume)
        release = named_block(effects, "STP_political_action_slot_release")
        self.assertIn("var = STP_political_action_slots_available value = 1", release)
        self.assertIn("STP_political_action_slots_total", release)

        initializer = named_block(effects, "STP_initialize_battle_for_stelander")
        self.assertIn("var = STP_political_action_slots_total value = 1", initializer)
        self.assertIn("var = STP_political_action_slots_available value = 1", initializer)
        shutdown = named_block(effects, "STP_end_battle_for_stelander")
        self.assertIn("clear_variable = STP_political_action_slots_total", shutdown)
        self.assertIn("clear_variable = STP_political_action_slots_available", shutdown)

        localisation = read(LOCALISATION)
        battle_description = re.search(
            r'(?m)^\s*STP_battle_for_stelander_desc:\s*"([^"]*)"',
            localisation,
        )
        self.assertIsNotNone(battle_description)
        self.assertIn("[?STP_political_action_slots_available|0]", battle_description.group(1))
        self.assertIn("[?STP_political_action_slots_total|0]", battle_description.group(1))

        for decision_id in REGIONAL_OPERATION_IDS:
            with self.subTest(decision=decision_id):
                operation = named_block(decisions, decision_id)
                self.assertIn(
                    "STP_has_political_action_slot = yes",
                    named_block(operation, "available"),
                )
                self.assertIn(
                    "STP_political_action_slot_consume = yes",
                    named_block(operation, "complete_effect"),
                )
                self.assertIn(
                    "STP_political_action_slot_release = yes",
                    named_block(operation, "cancel_effect"),
                )
                self.assertIn(
                    "STP_political_action_slot_release = yes",
                    named_block(operation, "remove_effect"),
                )
        self.assertNotIn("STP_regional_operation_active", decisions)

    def test_regional_treasury_costs_keep_standard_tiers_with_explicit_pp(self) -> None:
        decisions = read(DECISIONS)
        expected_costs = {
            "STP_bargain_with_local_councils": 100,
            "STP_prepare_false_trail": 50,
            "STP_region_unique_operation_3": 100,
            "STP_region_unique_operation_45": 200,
            "STP_region_unique_operation_46": 100,
        }
        for decision_id, amount in expected_costs.items():
            block = named_block(decisions, decision_id)
            self.assertIn(f"ADISCORD_economy_can_spend_{amount} = yes", block)
            pp = {"STP_bargain_with_local_councils": 10, "STP_prepare_false_trail": 15,
                  "STP_region_unique_operation_3": 10, "STP_region_unique_operation_45": 15,
                  "STP_region_unique_operation_46": 20}[decision_id]
            self.assertIn(f"custom_cost_text = STP_cost_pp{pp}_t{amount}", block)
            self.assertIn(f"add_political_power = -{pp}", block)
            self.assertIn(f"ADISCORD_economy_spend_{amount} = yes", block)
            self.assertNotIn("ADISCORD_economy_can_spend_25", block)

        shared_triggers = read(SHARED_ACTION_TRIGGERS)
        shared_effects = read(SHARED_ACTION_EFFECTS)
        politics_loc = read(POLITICS_LOCALISATION)
        for amount in (50, 100, 200, 500):
            self.assertIn(f"ADISCORD_economy_can_spend_{amount} = {{", shared_triggers)
            spend = named_block(shared_effects, f"ADISCORD_economy_spend_{amount}")
            self.assertIn(f"value = -{amount}", spend)
            self.assertIn(f"value = {amount}", spend)
            self.assertRegex(
                politics_loc,
                rf'(?m)^\s*ADISCORD_cost_t{amount}:\s*"£ADISCORD_economy_treasury_texticon §Y{amount}§!"',
            )
        self.assertNotIn("ADISCORD_economy_can_spend_25", shared_triggers)
        self.assertNotIn("ADISCORD_economy_spend_25", shared_effects)
        self.assertNotRegex(politics_loc, r'(?m)^\s*ADISCORD_cost_t\d+:\s*"[^"]*казн')

    def test_rifle_costs_use_the_existing_compact_texticon(self) -> None:
        politics_loc = read(POLITICS_LOCALISATION)
        rifle_cost_lines = [
            line
            for line in politics_loc.splitlines()
            if line.lstrip().startswith("ADISCORD_") and "infantry_equipment" in line
        ]
        self.assertGreater(len(rifle_cost_lines), 0)
        for line in rifle_cost_lines:
            self.assertIn("£infantry_equipment_texticon", line)
            self.assertNotIn("£infantry_equipment_text_icon", line)

        texticon_gfx = read(TEXTICON_GFX)
        self.assertIn('name = "GFX_infantry_equipment_texticon"', texticon_gfx)
        self.assertIn(
            'texturefile = "gfx/texticons/infantry_equipment_texticon.dds"',
            texticon_gfx,
        )
        with Image.open(COMPACT_INFANTRY_TEXTICON) as compact_icon:
            self.assertEqual(compact_icon.size, (16, 16))

    def test_map_decision_icons_use_compact_safe_spacing(self) -> None:
        mapicons = read(MAPICONS_GUI)
        self.assertRegex(
            mapicons,
            r'name\s*=\s*"decision_mapicon_container"[\s\S]*?'
            r'name\s*=\s*"decisions_gridbox"[\s\S]*?'
            r"slotsize\s*=\s*\{\s*width\s*=\s*55\s+height\s*=\s*40\s*\}",
        )

    def test_disputed_stelander_states_have_population_and_equal_resources(self) -> None:
        self.assertEqual(set(state_builder.STELANDER_REGIONAL_PROFILES), set(LOCAL_FORCE_STATES))
        self.assertEqual(set(state_builder.STELANDER_REGIONAL_RESOURCES), set(LOCAL_FORCE_STATES))
        for state_id in LOCAL_FORCE_STATES:
            self.assertEqual(
                int(state_builder.STELANDER_REGIONAL_PROFILES[state_id]["population"]),
                STELANDER_POPULATION[state_id],
            )
            self.assertEqual(state_builder.STELANDER_REGIONAL_RESOURCES[state_id], STELANDER_RESOURCE_PACKAGE)
            self.assertEqual(TARGET_STATES[state_id][2], STELANDER_POPULATION[state_id])
            self.assertEqual(EXPECTED_RESOURCES[state_id], STELANDER_RESOURCE_PACKAGE)

    def test_category_combines_a_scripted_map_with_map_targeted_actions(self) -> None:
        categories = read(CATEGORIES)
        category = named_block(categories, "STP_battle_for_stelander")
        self.assertIn("scripted_gui = ADISCORD_STP_regions_panel", category)
        self.assertIn("has_country_flag = STP_battle_for_stelander_active", category)

        scripted_gui = read(SCRIPTED_GUI)
        gui = read(GUI)
        gfx = read(GFX)
        for state_id in PARTICIPATING_STATES:
            self.assertIn(f"GFX_STP_regions_state_{state_id}", gfx)
            for frame in STATUS_FRAMES:
                control = f"STP_regions_{state_id}_{frame}"
                self.assertIn(f'name = "{control}"', gui)
                self.assertIn(f"{control}_visible", scripted_gui)
        self.assertEqual(gfx.count("noOfFrames = 7"), len(PARTICIPATING_STATES))

    def test_region_map_builder_is_registered_and_current(self) -> None:
        registry = read(ROOT / "tools/data/generated_output_owners.json")
        self.assertIn('"id": "stp_regions_map"', registry)
        result = subprocess.run(
            [sys.executable, "-B", "-m", "tools.builders.build_adiscord_stp_regions_map", "--check"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_region_overlay_uses_one_pixel_inner_border(self) -> None:
        mask = Image.new("L", (regions_map_builder.WIDTH, regions_map_builder.HEIGHT), 0)
        mask.paste(255, (100, 80, 140, 120))

        overlay = regions_map_builder.state_overlay(mask, (49, 154, 225))
        outside_mask = ImageChops.subtract(overlay.getchannel("A"), mask)

        self.assertIsNone(outside_mask.getbbox())
        self.assertIsNotNone(overlay.getbbox())
        self.assertEqual(overlay.getpixel((101, 100)), (49, 154, 225, 214))

    def test_russian_localisation_has_bom_and_player_facing_region_data(self) -> None:
        self.assertTrue(LOCALISATION.is_file(), f"missing file: {LOCALISATION.relative_to(ROOT)}")
        self.assertFalse(
            LEGACY_REGIONS_LOCALISATION.exists(),
            f"regional localisation must be merged into {LOCALISATION.relative_to(ROOT)}",
        )
        self.assertTrue(LOCALISATION.read_bytes().startswith(b"\xef\xbb\xbf"))
        localisation = read(LOCALISATION)
        battle_description = re.search(
            r'(?m)^\s*STP_battle_for_stelander_desc:\s*"([^"]*)"',
            localisation,
        )
        self.assertIsNotNone(battle_description)
        self.assertNotIn("STP_display_party_suspicion", battle_description.group(1))
        self.assertNotRegex(localisation, r"(?m)^\s*STP_region_debug:")
        for key in (
            "STP_battle_for_stelander",
            "STP_region_forces_header",
            "STP_region_assets_header",
            "STP_region_party_measures_header",
            "STP_region_last_party_response_header",
        ):
            self.assertRegex(localisation, rf"(?m)^\s*{re.escape(key)}:")
        self.assertNotRegex(localisation, r"(?m)^\s*STP_region_strategic_value_header:")
        self.assertNotIn("СТРАТЕГИЧЕСКОЕ ЗНАЧЕНИЕ", localisation)
        scripted_localisation = read(
            ROOT / "common/scripted_localisation/ADISCORD_STP_scripted_loc.txt"
        )
        expected_value_getters = {
            "STPGetResistanceInfluence": "STP_REGION_RESISTANCE_INFLUENCE_VALUE",
            "STPGetPartyInfluence": "STP_REGION_PARTY_INFLUENCE_VALUE",
            "STPGetLocalForcesInfluence": "STP_REGION_LOCAL_FORCES_INFLUENCE_VALUE",
        }
        for getter, localisation_key in expected_value_getters.items():
            getter_body = defined_text_block(scripted_localisation, getter)
            self.assertIn(f"localization_key = {localisation_key}", getter_body)
        self.assertRegex(
            localisation,
            r'(?m)^\s*STP_REGION_RESISTANCE_INFLUENCE_VALUE:\s*"\[\?STP_resistance_influence\|0\]%"',
        )
        self.assertRegex(
            localisation,
            r'(?m)^\s*STP_REGION_PARTY_INFLUENCE_VALUE:\s*"\[\?STP_party_influence\|0\]%"',
        )
        self.assertRegex(
            localisation,
            r'(?m)^\s*STP_REGION_LOCAL_FORCES_INFLUENCE_VALUE:\s*"\[\?STP_local_forces_influence\|0\]%"',
        )
        for state_id in PARTICIPATING_STATES:
            tooltip = re.search(
                rf'(?m)^\s*STP_region_{state_id}_map_tt:\s*"([^"]*)"',
                localisation,
            )
            self.assertIsNotNone(tooltip)
            tooltip_text = tooltip.group(1)
            self.assertNotIn("%%", tooltip_text)
            self.assertNotRegex(tooltip_text, r"\[\?\d+[:.]")
            self.assertIn(
                f"[{state_id}.STPGetResistanceInfluence]",
                tooltip_text,
            )
            self.assertIn(
                f"[{state_id}.STPGetPartyInfluence]",
                tooltip_text,
            )
            self.assertIn("§CСопротивление:§!", tooltip_text)
            self.assertIn("§0Партия:§!", tooltip_text)
            self.assertNotIn("§1Партия:§!", tooltip_text)
            self.assertNotIn("§OПартия:§!", tooltip_text)
            self.assertNotIn("§5Партия:§!", tooltip_text)
            if state_id in LOCAL_FORCE_STATES:
                self.assertIn("§YМестные силы:§!", tooltip_text)
                self.assertIn(
                    f"[{state_id}.STPGetLocalForcesInfluence]",
                    tooltip_text,
                )
            else:
                self.assertNotIn("Местные силы:", tooltip_text)

    def test_map_and_split_use_the_same_transfer_forecast(self) -> None:
        gui = read(SCRIPTED_GUI)
        triggers = read(TRIGGERS)
        effects = read(EFFECTS)
        decisions = read(DECISIONS)
        loc = read(LOCALISATION)
        goes_to = named_block(triggers, "STP_cw_region_goes_to_resistance")
        self.assertIn("has_state_flag = { flag = STP_resistance_administration_asset days > 20 }", goes_to)
        self.assertIn("STP_cw_high_shabrat_legitimacy = yes", goes_to)
        self.assertIn("value > 0.55", named_block(triggers, "STP_cw_high_shabrat_legitimacy"))
        self.assertIn("STP_region_has_ready_administration", triggers)
        self.assertIn("STP_cw_second_inspection_unlocked", triggers)
        self.assertIn("value = 50 compare = greater_than_or_equals", named_block(triggers, "STP_cw_second_inspection_unlocked"))
        for state_id in PARTICIPATING_STATES:
            self.assertIn(f"STP_regions_{state_id}_resistance_entrenched_visible = {{ {state_id} = {{ STP_region_map_shows_resistance_held = yes }} }}", gui)
            self.assertIn(f"STP_regions_{state_id}_local_dominant_visible = {{ {state_id} = {{ STP_region_map_shows_republics_held = yes }} }}", gui)
        self.assertNotIn("every_owned_state = {", named_block(effects, "STP_cw_start").split("every_owned_state = { set_state_controller_to")[0])
        for state_id in OPERABLE_STATES:
            self.assertIn(f"STS = {{ transfer_state = {state_id} }}", named_block(effects, "STP_cw_start"))
        self.assertIn("set_temp_variable = { var = STP_region_influence_change value = 15 }", named_block(decisions, "STP_region_unique_operation_2"))
        self.assertIn("set_temp_variable = { var = STP_region_influence_change value = 15 }", named_block(decisions, "STP_region_unique_operation_29"))
        self.assertNotIn("value = 35 }", named_block(decisions, "STP_region_unique_operation_2"))
        self.assertIn("бросает кубик", loc)
        self.assertIn("Легитимность выше §Y55%§!", loc)
        self.assertIn("STP_cw_inspection_chain_open", named_block(effects, "STP_change_party_suspicion"))
        change = named_block(effects, "STP_change_party_suspicion")
        self.assertIn("STP_schedule_next_party_inspection = yes", change)
        self.assertEqual(regions_map_builder.INITIAL_STATUS_FRAME[2], 4)
        self.assertEqual(regions_map_builder.INITIAL_STATUS_FRAME[45], 6)
        self.assertEqual(regions_map_builder.INITIAL_STATUS_FRAME[53], 1)


if __name__ == "__main__":
    unittest.main()
