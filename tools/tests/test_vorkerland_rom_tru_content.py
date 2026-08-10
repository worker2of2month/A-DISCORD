from __future__ import annotations

import codecs
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8-sig", errors="strict")


def named_block(source: str, name: str) -> str:
    match = re.search(rf"(?m)^\s*{re.escape(name)}\s*=\s*\{{", source)
    if not match:
        raise AssertionError(f"missing block {name}")
    opening = source.find("{", match.start(), match.end())
    depth = 0
    in_string = False
    escaped = False
    for index in range(opening, len(source)):
        char = source[index]
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
                return source[match.start():index + 1]
    raise AssertionError(f"unclosed block {name}")


def scalar(relative: str, key: str) -> float:
    match = re.search(rf"(?m)^\s*{re.escape(key)}\s*=\s*(-?[\d.]+)\s*$", read(relative))
    if not match:
        raise AssertionError(f"missing {key} in {relative}")
    return float(match.group(1))


class RomTruContentTests(unittest.TestCase):
    def test_post_split_population_contract_is_generated_and_applied(self) -> None:
        builder = read("tools/builders/build_adiscord_new_states.py")
        expected = {
            73: 1_300_000,
            80: 1_350_000,
            315: 550_000,
            316: 500_000,
            317: 700_000,
            318: 750_000,
        }
        paths = {
            73: "history/states/73-73.txt",
            80: "history/states/80-80.txt",
            315: "history/states/315-315.txt",
            316: "history/states/316-316.txt",
            317: "history/states/317-317.txt",
            318: "history/states/318-318.txt",
        }
        for state_id, population in expected.items():
            self.assertRegex(
                builder,
                rf"{state_id}: \{{\"population\": {population:_}".replace("_", "_?"),
            )
            self.assertEqual(scalar(paths[state_id], "manpower"), population)
        self.assertEqual(expected[73], 1_300_000)
        self.assertEqual(sum(expected[state] for state in (80, 315, 316, 317, 318)), 3_850_000)

    def test_country_histories_start_with_playable_stability(self) -> None:
        self.assertEqual(scalar("history/countries/ROM - RomelLand.txt", "set_stability"), 0.40)
        self.assertEqual(scalar("history/countries/TRU - TrumanLand.txt", "set_stability"), 0.25)

    def test_initialization_is_idempotent_and_adds_only_reserve_deltas(self) -> None:
        effects = read("common/scripted_effects/ADISCORD_vorkerland_rom_tru_effects.txt")
        rom = named_block(effects, "ADISCORD_vorkerland_rom_initialize_war_content")
        tru = named_block(effects, "ADISCORD_vorkerland_tru_initialize_war_content")
        for block, tag, support, idea in (
            (rom, "ROM", 20, "ADISCORD_vorkerland_rom_desert_eagle_staff"),
            (tru, "TRU", 24, "ADISCORD_vorkerland_tru_emergency_river_council"),
        ):
            self.assertIn("add_manpower = 3000", block)
            self.assertIn(f"amount = 400 producer = {tag}", block)
            self.assertIn(f"amount = {support} producer = {tag}", block)
            self.assertIn(f"amount = 48 producer = {tag}", block)
            self.assertIn(f"add_ideas = {idea}", block)
            self.assertEqual(block.count("set_country_flag ="), 1)
        self.assertIn("etatism = 45", rom)
        self.assertIn("chauvinism = 42", tru)

    def test_each_country_has_a_bounded_three_step_chain(self) -> None:
        decisions = read("common/decisions/ADISCORD_vorkerland_rom_tru_decisions.txt")
        rom_mission = named_block(decisions, "ADISCORD_vorkerland_rom_break_valley_administration")
        tru_mission = named_block(decisions, "ADISCORD_vorkerland_tru_break_zlatorech_administration")
        self.assertIn("days_mission_timeout = 180", rom_mission)
        self.assertIn("DVA = { has_capitulated = yes }", rom_mission)
        self.assertIn("days_mission_timeout = 150", tru_mission)
        self.assertIn("ZTA = { has_capitulated = yes }", tru_mission)
        for decision in (
            "ADISCORD_vorkerland_rom_assemble_valley_columns",
            "ADISCORD_vorkerland_tru_arm_river_battalions",
        ):
            block = named_block(decisions, decision)
            self.assertIn("days_remove = 21", block)
            self.assertIn("cost = 25", block)
        for decision in (
            "ADISCORD_vorkerland_rom_charter_valley_councils",
            "ADISCORD_vorkerland_tru_convene_river_congress",
        ):
            block = named_block(decisions, decision)
            self.assertIn("days_remove = 30", block)
            self.assertIn("cost = 40", block)

    def test_visible_events_are_fired_only_on_pair_war_edges(self) -> None:
        events = read("events/ADISCORD_vorkerland_rom_tru_events.txt")
        self.assertIn("add_namespace = ADISCORD_vorkerland_rom_tru", events)
        self.assertEqual(events.count("country_event = {"), 2)
        for event_id, tag, target, mission in (
            (1, "ROM", "DVA", "ADISCORD_vorkerland_rom_break_valley_administration"),
            (2, "TRU", "ZTA", "ADISCORD_vorkerland_tru_break_zlatorech_administration"),
        ):
            block = named_block(events, "country_event") if event_id == 1 else events[events.find("country_event = {", events.find("country_event = {") + 1):]
            self.assertIn(f"id = ADISCORD_vorkerland_rom_tru.{event_id}", block)
            self.assertIn(f"tag = {tag}", block)
            self.assertIn(f"has_war_with = {target}", block)
            self.assertIn(f"activate_mission = {mission}", block)

        on_actions = read("common/on_actions/02_ADISCORD_vorkerland_rom_tru_on_actions.txt")
        self.assertIn("on_war = {", on_actions)
        self.assertIn("on_startup = {", on_actions)
        for forbidden in ("on_monthly", "on_daily", "every_country", "every_state", "random_country"):
            self.assertNotIn(forbidden, on_actions)
        self.assertEqual(on_actions.count("ADISCORD_vorkerland_rom_tru.1"), 2)
        self.assertEqual(on_actions.count("ADISCORD_vorkerland_rom_tru.2"), 2)

    def test_pair_scoped_ai_overrides_are_offensive(self) -> None:
        ai = read("common/ai_strategy/ADISCORD_vorkerland_rom_tru_ai.txt")
        for key, tag, target in (
            ("ADISCORD_vorkerland_rom_tru_rom_offensive", "ROM", "DVA"),
            ("ADISCORD_vorkerland_rom_tru_tru_offensive", "TRU", "ZTA"),
        ):
            block = named_block(ai, key)
            self.assertIn(f"allowed = {{ tag = {tag} }}", block)
            self.assertIn(f"has_war_with = {target}", block)
            self.assertIn("value = 100", block)
            self.assertIn("priority = 1400", block)
            self.assertIn("execution_type = rush", block)
            self.assertIn("manual_attack = yes", block)
            self.assertIn(f"type = conquer id = {target} value = 200", block)

    def test_owned_scripts_do_not_touch_ivanland_or_use_global_polling(self) -> None:
        owned = "\n".join(read(path) for path in (
            "common/ideas/ADISCORD_vorkerland_rom_tru_ideas.txt",
            "common/decisions/ADISCORD_vorkerland_rom_tru_decisions.txt",
            "common/decisions/categories/ADISCORD_vorkerland_rom_tru_categories.txt",
            "common/scripted_effects/ADISCORD_vorkerland_rom_tru_effects.txt",
            "events/ADISCORD_vorkerland_rom_tru_events.txt",
            "common/on_actions/02_ADISCORD_vorkerland_rom_tru_on_actions.txt",
            "common/ai_strategy/ADISCORD_vorkerland_rom_tru_ai.txt",
        ))
        self.assertNotRegex(owned, r"\b(?:IVN|RIN)\b")
        for forbidden in ("on_monthly", "on_daily", "every_country", "random_country"):
            self.assertNotIn(forbidden, owned)

    def test_russian_localisation_is_bom_encoded_and_complete(self) -> None:
        path = ROOT / "localisation/russian/ADISCORD_vorkerland_rom_tru_l_russian.yml"
        self.assertTrue(path.read_bytes().startswith(codecs.BOM_UTF8))
        loc = read("localisation/russian/ADISCORD_vorkerland_rom_tru_l_russian.yml")
        for key in (
            "ADISCORD_vorkerland_rom_tru_category",
            "ADISCORD_vorkerland_rom_assemble_valley_columns",
            "ADISCORD_vorkerland_rom_break_valley_administration",
            "ADISCORD_vorkerland_rom_charter_valley_councils",
            "ADISCORD_vorkerland_tru_arm_river_battalions",
            "ADISCORD_vorkerland_tru_break_zlatorech_administration",
            "ADISCORD_vorkerland_tru_convene_river_congress",
            "ADISCORD_vorkerland_rom_tru.1.t",
            "ADISCORD_vorkerland_rom_tru.2.t",
        ):
            self.assertIn(f"{key}:", loc)


if __name__ == "__main__":
    unittest.main()
