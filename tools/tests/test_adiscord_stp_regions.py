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
EFFECTS = ROOT / "common/scripted_effects/ADISCORD_STP_region_effects.txt"
TRIGGERS = ROOT / "common/scripted_triggers/ADISCORD_STP_region_triggers.txt"
DECISIONS = ROOT / "common/decisions/ADISCORD_STP_decisions.txt"
LEGACY_REGIONS_DECISIONS = ROOT / "common/decisions/ADISCORD_STP_region_decisions.txt"
EVENTS = ROOT / "events/ADISCORD_STP_region_events.txt"
CATEGORIES = ROOT / "common/decisions/categories/ADISCORD_decision_categories_STP.txt"
SCRIPTED_GUI = ROOT / "common/scripted_guis/ADISCORD_STP_regions_scripted_gui.txt"
GUI = ROOT / "interface/ADISCORD_STP_regions.gui"
GFX = ROOT / "interface/ADISCORD_STP_regions.gfx"
LOCALISATION = ROOT / "localisation/russian/ADISCORD_STP_decisions_l_russian.yml"
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
        entry = named_block(events, "country_event")
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
        triggers = read(TRIGGERS)
        for side in ("resistance", "party", "local_forces"):
            threshold = named_block(triggers, f"STP_region_{side}_at_least")
            self.assertIn("value = $value$", threshold)
        for side in ("resistance", "party", "local_forces"):
            strongest = named_block(triggers, f"STP_region_{side}_strongest")
            entrenched = named_block(triggers, f"STP_region_{side}_entrenched")
            self.assertIn("compare = greater_than_or_equals", strongest)
            self.assertIn("STP_region_lead", entrenched)
            self.assertIn("STP_region_runner_up", entrenched)
        contested = named_block(triggers, "STP_region_contested")
        self.assertIn("NOT = { STP_region_resistance_leaning = yes }", contested)
        self.assertIn("NOT = { STP_region_party_leaning = yes }", contested)
        self.assertIn("NOT = { STP_region_local_forces_leaning = yes }", contested)

    def test_local_forces_exist_only_in_the_four_agreed_states(self) -> None:
        decisions = read(DECISIONS)
        for decision_id in (
            "STP_recruit_regional_official",
            "STP_prepare_false_trail",
        ):
            block = named_block(decisions, decision_id)
            self.assertIn("state_target = yes", block)
            targets = {int(value) for value in re.findall(r"\b\d+\b", named_block(block, "targets"))}
            self.assertEqual(targets, set(OPERABLE_STATES))
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
            "country_event = { id = ADISCORD_STP_regions.2 days = 40 }",
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
            self.assertRegex(
                mission,
                r"hidden_effect\s*=\s*\{\s*STP_schedule_next_party_inspection\s*=\s*yes\s*\}",
            )
        scheduler = named_block(effects, "STP_schedule_next_party_inspection")
        for state_id in OPERABLE_STATES:
            self.assertIn(f"activate_mission = STP_party_inspection_state_{state_id}", scheduler)
            self.assertIn(
                f"var = STP_last_inspection_state value = {state_id} compare = equals",
                scheduler,
            )
            self.assertIn(f"{state_id} = {{ STP_region_has_detectable_assets = yes }}", scheduler)

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

    def test_regional_treasury_costs_use_icon_only_standard_tiers(self) -> None:
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
            self.assertIn(f"custom_cost_text = ADISCORD_cost_t{amount}", block)
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
        for state_id in PARTICIPATING_STATES:
            tooltip = re.search(
                rf'(?m)^\s*STP_region_{state_id}_map_tt:\s*"([^"]*)"',
                localisation,
            )
            self.assertIsNotNone(tooltip)
            tooltip_text = tooltip.group(1)
            self.assertNotIn("%%", tooltip_text)
            self.assertIn("§CСопротивление:§!", tooltip_text)
            self.assertIn("§0Партия:§!", tooltip_text)
            self.assertNotIn("§1Партия:§!", tooltip_text)
            self.assertNotIn("§OПартия:§!", tooltip_text)
            self.assertNotIn("§5Партия:§!", tooltip_text)
            if state_id in LOCAL_FORCE_STATES:
                self.assertIn("§YМестные силы:§!", tooltip_text)
            else:
                self.assertNotIn("Местные силы:", tooltip_text)


if __name__ == "__main__":
    unittest.main()
