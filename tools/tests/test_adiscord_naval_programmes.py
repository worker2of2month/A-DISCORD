"""Fleet conservation, usable focus rewards and bounded naval production."""

from collections import Counter
from pathlib import Path
import re
import unittest

from tools.builders.build_adiscord_focus_trees import render_source
from tools.tests.test_build_adiscord_focus_trees import semantic
from tools.tests.test_adiscord_stp_preparation import block, scalar, walk
from tools.validators.validate_adiscord_division_templates import parse_clausewitz
from tools.validators.validate_adiscord_economy_ai import marine_recruitment_contract_issues


ROOT = Path(__file__).resolve().parents[2]


def entries(path):
    return parse_clausewitz((ROOT / path).read_text(encoding="utf-8-sig"))


def focus_map(source):
    tree = block(parse_clausewitz(render_source(source)), "focus_tree")
    return {
        scalar(row.value, "id"): row.value for row in tree if row.key == "focus"
    }


def formation_requirements(composition):
    units = block(entries("common/units/ADISCORD_land_units.txt"), "sub_units")
    manpower = 0
    equipment = Counter()
    for unit, count in composition.items():
        definition = block(units, unit)
        manpower += count * int(scalar(definition, "manpower"))
        for need in block(definition, "need"):
            equipment[need.key] += count * int(need.value)
    return manpower, equipment


class NavalProgrammeTests(unittest.TestCase):
    def test_starting_fleet_composition_and_technology_before_oob(self):
        grants = entries("common/scripted_effects/ADISCORD_technology_baseline_effects.txt")
        techs = {}
        for path in (ROOT / "common/technologies").glob("*.txt"):
            for row in block(parse_clausewitz(path.read_text(encoding="utf-8-sig")), "technologies"):
                techs[row.key] = row.value
        for tag, expected in {
            "STP": (2, 4, 10, 4),
            "VAL": (1, 3, 8, 4),
            "NOD": (2, 4, 10, 4),
        }.items():
            country = next((ROOT / "history/countries").glob(f"{tag} - *.txt"))
            history = parse_clausewitz(country.read_text(encoding="utf-8-sig"))
            researched = set()
            for row in history:
                if row.key == "oob":
                    break
                if row.key.startswith("ADISCORD_grant_technology_profile_"):
                    researched.update(
                        item.key for item in block(block(grants, row.key), "set_technology")
                        if item.key != "popup"
                    )
            enabled_models = {
                item.value
                for tech in researched
                for row in techs[tech] if row.key == "enable_equipments"
                for item in row.value
            }
            units = block(entries(f"history/units/{tag}.txt"), "units")
            ships = [row.value for row in walk(units) if row.key == "ship"]
            actual = Counter(scalar(ship, "definition") for ship in ships)
            self.assertEqual(
                tuple(actual[unit] for unit in (
                    "heavy_cruiser", "light_cruiser",
                    "ADISCORD_coastal_patrol_vessel", "submarine",
                )), expected,
            )
            for ship in ships:
                self.assertIn(block(ship, "equipment")[0].key, enabled_models, tag)
            for force in block(units, "fleet"):
                if force.key != "task_force":
                    continue
                composition = Counter(
                    scalar(row.value, "definition") for row in force.value if row.key == "ship"
                )
                if composition["heavy_cruiser"]:
                    self.assertGreaterEqual(
                        composition["ADISCORD_coastal_patrol_vessel"],
                        3 * composition["heavy_cruiser"],
                    )

    def test_shabrat_guaranteed_start_has_a_coastal_port(self):
        state = block(entries("history/states/1-Ablia.txt"), "state")
        port = block(block(block(state, "history"), "buildings"), "16344")
        self.assertEqual(scalar(port, "naval_base"), "2")
        definition = (ROOT / "map/definition.csv").read_text(encoding="utf-8-sig")
        province = next(line.split(";") for line in definition.splitlines() if line.startswith("16344;"))
        self.assertEqual(province[4:6], ["land", "true"])
        start = block(entries("common/scripted_effects/ADISCORD_STP_scripted_effects.txt"), "STP_cw_start")
        payload = block(start, "if")
        grant = next(row.value for row in payload if row.key == "STS")
        self.assertEqual(scalar(grant, "transfer_state"), "1")

    def test_starting_dockyards_fit_all_shared_buildings_without_slot_bonuses(self):
        definitions = block(entries("common/buildings/00_buildings.txt"), "buildings")
        shared_buildings = {
            row.key for row in definitions
            if isinstance(row.value, list)
            and any(
                field.key == "shares_slots" and field.value == "yes"
                for field in block(row.value, "level_cap")
            )
        }
        self.assertIn("ADISCORD_business_center", shared_buildings)
        self.assertIn("ADISCORD_industrial_cluster", shared_buildings)
        for filename, category, base_slots, dockyards in (
            ("30-Cussington.txt", "large_city", 8, 3),
            ("48-Depoitodron.txt", "megalopolis", 12, 2),
        ):
            with self.subTest(state=filename):
                state = block(entries(f"history/states/{filename}"), "state")
                self.assertEqual(scalar(state, "state_category"), category)
                history = block(state, "history")
                buildings = block(history, "buildings")
                self.assertEqual(int(scalar(buildings, "dockyard")), dockyards)
                occupied = sum(
                    int(row.value) for row in buildings if row.key in shared_buildings
                )
                extra_slots = int(scalar(history, "add_extra_state_shared_building_slots"))
                self.assertEqual(extra_slots, 2)
                self.assertLessEqual(occupied, base_slots + extra_slots)

    def test_fleet_split_does_not_recreate_ships_or_move_other_resources(self):
        effects = entries("common/scripted_effects/ADISCORD_STP_scripted_effects.txt")
        split = block(effects, "STP_cw_divide_navy")
        transfer = block(split, "transfer_units_fraction")
        self.assertEqual(scalar(transfer, "target"), "STS")
        for field in ("size", "army_ratio", "air_ratio", "stockpile_ratio"):
            self.assertEqual(scalar(transfer, field), "0")
        self.assertEqual(scalar(transfer, "navy_ratio"), "var:STP_cw_navy_share")
        self.assertEqual(scalar(block(split, "set_temp_variable"), "value"), "0.5")
        limited = block(split, "if")
        self.assertEqual(
            scalar(block(limited, "limit"), "has_country_flag"),
            "STP_cw_limited_party_revolt",
        )
        self.assertEqual(scalar(block(limited, "set_temp_variable"), "value"), "1")
        self.assertFalse(any(row.key in ("create_ship", "load_oob") for row in walk(split)))
        start = block(effects, "STP_cw_start")
        self.assertEqual(sum(row.key == "STP_cw_divide_navy" for row in walk(start)), 1)
        self.assertIn("STP_cw_can_start", [row.key for row in walk(block(block(start, "if"), "limit"))])

    def test_four_programmes_have_exact_base_escorts_convoys_and_dockyards(self):
        stp = focus_map("STP/civil_war/focuses.txt")
        val = focus_map("VAL/main/focuses.txt")
        nod = focus_map("NOD/main/focuses.txt")
        programmes = [
            (stp, "STP_pc_navy_yards", ["STP_pc_navy_coast", "STP_pc_navy_escorts"]),
            (stp, "STP_pw_party_naval_yards", ["STP_pw_party_naval_escorts"]),
            (val, "VAL_Depoitodron_Naval_Yards", ["VAL_Expedition_Escorts"]),
            (nod, "NOD_Cussington_Naval_Yards", ["NOD_Sea_Lane_Escorts"]),
        ]
        for focuses, yards, escorts in programmes:
            yard = focuses[yards]
            self.assertIn("ADISCORD_can_expand_naval_yards", [r.key for r in walk(block(yard, "available"))])
            self.assertEqual(scalar(block(yard, "completion_reward"), "ADISCORD_expand_naval_yards"), "yes")
            ships = 0
            convoys = 0
            for focus in escorts:
                for row in walk(block(focuses[focus], "completion_reward")):
                    if row.key == "create_ship" and scalar(row.value, "type") == "ADISCORD_escort_ship_2155":
                        ships += int(scalar(row.value, "amount"))
                    if row.key == "add_equipment_to_stockpile" and scalar(row.value, "type") == "convoy_1":
                        convoys += int(scalar(row.value, "amount"))
            self.assertEqual((ships, convoys), (4, 40), yards)
        effect = block(entries("common/scripted_effects/ADISCORD_scripted_effects_generic.txt"), "ADISCORD_expand_naval_yards")
        state = block(effect, "random_owned_controlled_state")
        self.assertEqual(scalar(block(state, "add_building_construction"), "level"), "2")
        trigger = block(entries("common/scripted_triggers/ADISCORD_scripted_triggers_generic.txt"), "ADISCORD_can_expand_naval_yards")
        eligibility = block(trigger, "any_owned_state")
        self.assertEqual(scalar(eligibility, "is_controlled_by"), "ROOT")
        self.assertEqual(
            semantic(block(state, "limit")),
            semantic([r for r in eligibility if r.key != "is_controlled_by"]),
        )

    def test_additive_naval_minimums_fit_even_when_every_line_is_needed(self):
        ai = entries("common/ai_strategy/default.txt")
        lines = [row.value for row in ai if row.key.startswith("ADISCORD_regional_navy_") and row.key != "ADISCORD_regional_navy_research"]
        self.assertEqual(len(lines), 4)
        for yards in range(1, 11):
            reserved = 1  # The independent convoy reserve may be active too.
            for line in lines:
                tokens = [row.value for row in block(line, "enable") if row.key == ""]
                self.assertEqual(tokens[:2], ["num_of_naval_factories", ">"])
                if yards > int(tokens[2]):
                    reserved += int(scalar(block(line, "ai_strategy"), "value"))
            self.assertLessEqual(reserved, yards)
        patrol = block(ai, "ADISCORD_coastal_patrol_replacement")
        self.assertEqual(scalar(block(patrol, "enable"), "ADISCORD_is_regional_naval_power"), "no")

    def test_new_focus_localisation_has_bom_and_single_line_values(self):
        for language in ("russian", "english"):
            catalog = {}
            for stem in ("ADISCORD_STP", "ADISCORD_VAL_decisions", "ADISCORD_NOD", "ADISCORD_ideas"):
                path = ROOT / f"localisation/{language}/{stem}_l_{language}.yml"
                self.assertTrue(path.read_bytes().startswith(b"\xef\xbb\xbf"), path)
                catalog.update(re.findall(r'^\s*([\w]+):(?:\d+)?\s*"([^"\r\n]*)"\s*$', path.read_text(encoding="utf-8-sig"), re.M))
            for source, prefix in (
                ("STP/civil_war/focuses.txt", "STP_pw_party_naval_"),
                ("VAL/main/focuses.txt", "VAL_Expedition_"),
                ("NOD/main/focuses.txt", "NOD_"),
            ):
                for focus_id in focus_map(source):
                    if focus_id.startswith(prefix):
                        self.assertIn(focus_id, catalog)
                        self.assertIn(focus_id + "_desc", catalog)

    def test_marine_requests_reject_missing_role_training_or_supplies(self):
        source = (ROOT / "common/ai_strategy/default.txt").read_text(encoding="utf-8")
        templates = (ROOT / "common/ai_templates/ADISCORD_land_templates.txt").read_text(encoding="utf-8")
        self.assertEqual(marine_recruitment_contract_issues(source, templates), [])
        self.assertTrue(marine_recruitment_contract_issues(source, ""))
        role_request = "type = role_ratio id = marines"
        self.assertIn(role_request, source)
        self.assertTrue(marine_recruitment_contract_issues(
            source.replace(role_request, "type = unit_ratio id = marines"), templates
        ))
        self.assertTrue(marine_recruitment_contract_issues(
            source.replace("id = marines", "id = infantry"), templates
        ))
        for token in ("ADISCORD_has_marine_training", "ADISCORD_has_operational_naval_base", "has_manpower", "ADISCORD_squad_weapons_equipment"):
            with self.subTest(token=token):
                self.assertTrue(marine_recruitment_contract_issues(source.replace(token, "missing_guard"), templates))

    def test_nodrul_marine_focus_unlocks_its_template_without_free_units(self):
        reward = block(focus_map("NOD/main/focuses.txt")["NOD_Landing_Staff"], "completion_reward")
        granted = {
            field.key for grant in reward if grant.key == "set_technology"
            for field in grant.value if field.value == "1"
        }
        self.assertTrue({
            "ADISCORD_tech_amphibious_formation_organization",
            "ADISCORD_tech_amphibious_staff_sections",
            "ADISCORD_tech_nodrul_marine_corps",
        } <= granted)
        technologies = block(entries("common/technologies/ADISCORD_NOD_technologies.txt"), "technologies")
        unlock = block(technologies, "ADISCORD_tech_nodrul_marine_corps")
        self.assertEqual(
            [row.value for row in block(unlock, "enable_subunits")],
            ["ADISCORD_marine_infantry"],
        )
        template = block(reward, "division_template")
        composition = Counter(row.key for section in ("regiments", "support") for row in block(template, section))
        self.assertEqual(composition, {"ADISCORD_marine_infantry": 6, "engineer": 1})
        self.assertEqual(formation_requirements(composition), (6300, {
            "infantry_equipment": 5670,
            "ADISCORD_squad_weapons_equipment": 288,
            "support_equipment": 30,
        }))
        units = block(entries("common/units/ADISCORD_land_units.txt"), "sub_units")
        self.assertEqual(scalar(block(units, "engineer"), "active"), "yes")
        self.assertFalse(any(row.key in ("create_unit", "load_oob") for row in walk(reward)))

    def test_ai_marine_resource_gates_cover_the_actual_role_composition(self):
        roles = block(entries("common/ai_templates/ADISCORD_land_templates.txt"), "ADISCORD_marine_templates")
        brigade = block(roles, "ADISCORD_marine_brigade")
        composition = {
            row.key: int(row.value)
            for row in block(block(brigade, "target_template"), "regiments")
        }
        manpower, equipment = formation_requirements(composition)
        self.assertEqual(manpower, 6000)
        self.assertEqual(equipment, {"infantry_equipment": 5400, "ADISCORD_squad_weapons_equipment": 288})
        strategy = block(entries("common/ai_strategy/default.txt"), "ADISCORD_marine_recruitment")
        for policy in (brigade, strategy):
            guards = [row.value for row in block(policy, "enable") if row.key == "NOT"]
            self.assertIn(semantic(parse_clausewitz(f"has_manpower < {manpower}")), [semantic(guard) for guard in guards])
            for archetype, amount in equipment.items():
                self.assertIn(
                    semantic(parse_clausewitz(f"has_equipment = {{ {archetype} < {amount} }}")),
                    [semantic(guard) for guard in guards],
                )


if __name__ == "__main__":
    unittest.main()
