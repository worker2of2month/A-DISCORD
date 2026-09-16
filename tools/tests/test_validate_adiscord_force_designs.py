from __future__ import annotations

import re
import unittest
from pathlib import Path


from tools.lib.paths import source_section
from tools.validators.validate_adiscord_division_templates import parse_clausewitz


ROOT = Path(__file__).resolve().parents[2]
BASE_GAME = Path(r"Z:\SteamLibrary\steamapps\common\Hearts of Iron IV")


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8-sig")


def named_block(text: str, name: str) -> str:
    match = re.search(rf"(?m)^\s*{re.escape(name)}\s*=\s*\{{", text)
    if not match:
        raise AssertionError(f"missing block {name}")
    opening = text.find("{", match.start())
    depth = 0
    in_quote = False
    escaped = False
    for index in range(opening, len(text)):
        char = text[index]
        if char == "\\" and in_quote and not escaped:
            escaped = True
            continue
        if char == '"' and not escaped:
            in_quote = not in_quote
        if not in_quote:
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    return text[opening + 1 : index]
        escaped = False
    raise AssertionError(f"unterminated block {name}")


def named_blocks(text: str, name: str) -> list[str]:
    blocks: list[str] = []
    pattern = re.compile(rf"(?m)^\s*{re.escape(name)}\s*=\s*\{{")
    for match in pattern.finditer(text):
        opening = text.find("{", match.start())
        depth = 0
        in_quote = False
        escaped = False
        for index in range(opening, len(text)):
            char = text[index]
            if char == "\\" and in_quote and not escaped:
                escaped = True
                continue
            if char == '"' and not escaped:
                in_quote = not in_quote
            if not in_quote:
                if char == "{":
                    depth += 1
                elif char == "}":
                    depth -= 1
                    if depth == 0:
                        blocks.append(text[opening + 1 : index])
                        break
            escaped = False
        else:
            raise AssertionError(f"unterminated block {name}")
    return blocks


def event_block(text: str, event_id: str) -> str:
    for block in named_blocks(text, "country_event"):
        if re.search(rf"\bid\s*=\s*{re.escape(event_id)}\b", block):
            return block
    raise AssertionError(f"missing event {event_id}")


class VorkerlandForceDesignTests(unittest.TestCase):
    def test_ai_role_templates_have_unambiguous_country_filters(self) -> None:
        entries = parse_clausewitz(read("common/ai_templates/ADISCORD_land_templates.txt"))
        country_tags = {
            entry.key
            for path in (ROOT / "common/country_tags").glob("*.txt")
            for entry in parse_clausewitz(path.read_text(encoding="utf-8-sig"))
            if re.fullmatch(r"[A-Z0-9]{3}", entry.key)
        }
        roles = []
        for entry in entries:
            role = [e.value for e in entry.value if e.key == "role"]
            self.assertEqual(len(role), 1, entry.key)
            filters = [e for e in entry.value if e.key in ("available_for", "blocked_for")]
            self.assertEqual(len(filters), 1, entry.key)
            self.assertIsInstance(filters[0].value, list, entry.key)
            self.assertTrue(filters[0].value, f"{entry.key}: native tag lists must not be empty")
            for tag in filters[0].value:
                self.assertEqual(tag.key, "", entry.key)
                self.assertIn(tag.value, country_tags, entry.key)
            roles.extend(role)
        self.assertEqual(len(roles), len(set(roles)), "a country must not select two competing targets for one role")

    def test_combat_readiness_retains_native_supply_and_strength_safeguards(self) -> None:
        custom = read("common/defines/ADISCORD_defines_changes.lua")
        native = (BASE_GAME / "common/defines/00_defines.lua").read_text(encoding="utf-8-sig")
        for field in (
            "PLAN_ATTACK_MIN_ORG_FACTOR_LOW", "PLAN_ATTACK_MIN_STRENGTH_FACTOR_LOW",
            "PLAN_ATTACK_MIN_ORG_FACTOR_MED", "PLAN_ATTACK_MIN_STRENGTH_FACTOR_MED",
            "PLAN_ATTACK_MIN_ORG_FACTOR_HIGH", "PLAN_ATTACK_MIN_STRENGTH_FACTOR_HIGH",
            "FRONT_EVAL_UNIT_SUPPLY_AND_ORG_LACK_IMPACT", "AI_THEATRE_SUPPLY_CRISIS_LIMIT",
            "MAX_UNITS_FACTOR_FRONT_ORDER", "DESIRED_UNITS_FACTOR_FRONT_ORDER",
            "MIN_UNITS_FACTOR_FRONT_ORDER", "FALLBACK_LOSING_FACTOR",
        ):
            expected = re.search(rf"(?m)^\s*{field}\s*=\s*([\d.]+)", native)
            assigned = re.findall(rf"(?m)^\s*NDefines\.\w+\.{field}\s*=\s*([\d.]+)", custom)
            self.assertIsNotNone(expected, field)
            with self.subTest(field=field):
                if assigned:
                    self.assertEqual(float(assigned[-1]), float(expected[1]))

    def test_combined_production_minima_leave_capacity_for_rifles(self) -> None:
        policies = "\n".join(read(f"common/ai_strategy/{name}") for name in (
            "default.txt", "ADISCORD_technology_doctrine_ai.txt",
            "ADISCORD_vorkerland_ai.txt",
        ))

        def factory_condition(block: str, factories: int) -> bool:
            matches = re.findall(r"\bnum_of_military_factories\s*([<>]=?)\s*(\d+)", block)
            if not matches:
                return True
            self.assertEqual(len(matches), 1, block)
            operator, threshold = matches[0]
            threshold = int(threshold)
            return {
                ">": factories > threshold,
                ">=": factories >= threshold,
                "<": factories < threshold,
                "<=": factories <= threshold,
            }[operator]

        minimums = []
        for name in re.findall(r"(?m)^(ADISCORD_\w+)\s*=\s*\{", policies):
            block = named_block(policies, name)
            for strategy in named_blocks(block, "ai_strategy"):
                if not re.search(r"\btype\s*=\s*equipment_production_min_factories(?:_archetype)?\b", strategy):
                    continue
                equipment = re.search(r"\bid\s*=\s*(\w+)", strategy).group(1)
                if equipment == "convoy":
                    continue  # Dockyards are a separate pool from military factories.
                requested = int(re.search(r"\bvalue\s*=\s*(\d+)", strategy).group(1))
                minimums.append((name, equipment, requested, block))
        self.assertTrue({"ADISCORD_squad_weapons_equipment", "support_equipment", "artillery_equipment", "fighter"} <= {equipment for _, equipment, _, _ in minimums})

        # Worst-case simultaneous low stocks, with technology/budget eligibility met
        # during the collapse, both before and after the optional WKR air focus.
        # This checks requested capacity, not the engine's final factory allocation.
        for tag in ("NOD", "WKR", "VAD", "TVA"):
            for air_focus in (False, True):
                for factories in range(20):
                    requests = []
                    for name, equipment, requested, block in minimums:
                        if re.search(r"\ballowed\s*=\s*\{", block):
                            tags = re.findall(r"\btag\s*=\s*(\w+)", named_block(block, "allowed"))
                            if tags and tag not in tags:
                                continue
                        enable = named_block(block, "enable")
                        if "has_country_flag = ADISCORD_vorkerland_focus_wkr_air_sustainment" in enable and not air_focus:
                            continue
                        enabled = factory_condition(enable, factories)
                        if re.search(r"\babort\s*=\s*\{", block):
                            aborted = factory_condition(named_block(block, "abort"), factories)
                            with self.subTest(policy=name, factories=factories, lifecycle="lost capacity"):
                                self.assertEqual(enabled, not aborted)
                        else:
                            self.assertIn("abort_when_not_enabled = yes", block)
                        if enabled:
                            requests.append((name, equipment, requested))
                    with self.subTest(tag=tag, air_focus=air_focus, factories=factories, requests=requests):
                        self.assertLessEqual(sum(value for _, _, value in requests), max(factories - 1, 0))


    def test_auxiliary_factory_minima_yield_to_rifle_shortage_with_hysteresis(self) -> None:
        policies = read("common/ai_strategy/default.txt")

        def parse_gate(text: str):
            # The structural parser does not retain comparison operators.
            normalized = re.sub(
                r"\b(\w+)\s*([<>]=?)\s*(-?\d+(?:\.\d+)?)",
                lambda match: (
                    f'comparison = {{ field = {match[1]} '
                    f'operator = "{match[2]}" threshold = {match[3]} }}'
                ),
                text,
            )
            return parse_clausewitz(normalized)

        def evaluate(nodes, *, war, rifle_ratio, auxiliary_ratio, equipment, stock=50, factories=5):
            ratios = {"infantry_equipment": rifle_ratio, equipment: auxiliary_ratio}

            def results(entries, ratio=None):
                values = []
                for entry in entries:
                    key, payload = entry.key, entry.value
                    if key in ("AND", "OR", "NOT"):
                        children = results(payload, ratio)
                        values.append(all(children) if key == "AND" else
                                      any(children) if key == "OR" else not any(children))
                    elif key == "stockpile_ratio":
                        archetype = next(item.value for item in payload if item.key == "archetype")
                        values.append(all(results([item for item in payload if item.key != "archetype"], ratios[archetype])))
                    elif key == "has_equipment":
                        values.append(all(results(payload)))
                    elif key == "comparison":
                        fields = {item.key: item.value for item in payload}
                        field = fields["field"]
                        if field == "num_of_military_factories":
                            actual = factories
                        elif field == "ratio":
                            self.assertIsNotNone(ratio)
                            actual = ratio
                        elif field == equipment:
                            actual = stock
                        else:
                            self.fail(f"unsupported comparison field {field}")
                        threshold = float(fields["threshold"])
                        values.append({
                            "<": actual < threshold, ">": actual > threshold,
                            "<=": actual <= threshold, ">=": actual >= threshold,
                        }[fields["operator"]])
                    elif key == "has_war":
                        self.assertIn(payload, ("yes", "no"))
                        values.append(war == (payload == "yes"))
                    else:
                        self.fail(f"unsupported policy trigger {key}")
                return values

            return all(results(nodes))

        cases = (
            # name, war, rifle ratio, auxiliary ratio, stock, factories, enable, abort
            ("critical rifles", True, 0.0, 0.20, 50, 5, False, True),
            ("both depleted", True, 0.0, 0.0, 50, 5, True, False),
            ("peace reserve", False, 0.0, 0.20, 50, 5, True, False),
            ("rifles recovered", True, 0.10, 0.20, 50, 5, True, False),
            ("hysteresis lower edge", True, 0.03, 0.20, 50, 5, False, False),
            ("hysteresis middle", True, 0.06, 0.20, 50, 5, False, False),
            ("hysteresis upper edge", True, 0.099, 0.20, 50, 5, False, False),
            ("auxiliary still healthy", True, 0.029, 0.101, 50, 5, False, True),
            ("auxiliary release boundary", True, 0.0, 0.10, 50, 5, False, False),
            ("auxiliary restart boundary", True, 0.0, 0.05, 50, 5, False, False),
            ("auxiliary needs restart", True, 0.0, 0.049, 50, 5, True, False),
            ("lost factories", False, 0.20, 0.20, 50, 0, False, True),
            ("reserve ceiling", False, 0.20, 0.20, 2000, 5, False, True),
        )
        for name, equipment in (
            ("ADISCORD_produce_squad_weapons_low_stock", "ADISCORD_squad_weapons_equipment"),
            ("ADISCORD_produce_support_equipment_low_stock", "support_equipment"),
            ("ADISCORD_produce_artillery_low_stock", "artillery_equipment"),
        ):
            policy = named_block(policies, name)
            enable = parse_gate(named_block(policy, "enable"))
            abort = parse_gate(named_block(policy, "abort"))
            for label, war, rifle_ratio, auxiliary_ratio, stock, factories, expected_enable, expected_abort in cases:
                with self.subTest(policy=name, case=label):
                    world = dict(war=war, rifle_ratio=rifle_ratio, auxiliary_ratio=auxiliary_ratio,
                                 equipment=equipment, stock=stock, factories=factories)
                    starts = evaluate(enable, **world)
                    stops = evaluate(abort, **world)
                    self.assertEqual((starts, stops), (expected_enable, expected_abort))
            active = False
            history = []
            for rifle_ratio in (0.10, 0.06, 0.029, 0.06, 0.10):
                world = dict(war=True, rifle_ratio=rifle_ratio, auxiliary_ratio=0.20, equipment=equipment)
                active = not evaluate(abort, **world) if active else evaluate(enable, **world)
                history.append(active)
            self.assertEqual(history, [True, True, False, False, True], name)

    def test_ai_has_an_immediately_reachable_eight_plus_one_line_template(self) -> None:
        templates = read("common/ai_templates/ADISCORD_land_templates.txt")
        block = named_block(templates, "ADISCORD_line_brigade")
        enable = named_block(block, "enable")
        target = named_block(block, "target_template")

        self.assertIn("is_ai = yes", enable)
        self.assertNotIn("num_of_military_factories", enable)
        self.assertNotIn("has_equipment", enable)
        self.assertRegex(target, r"regiments\s*=\s*\{[^{}]*infantry\s*=\s*8")
        self.assertRegex(
            target,
            r"regiments\s*=\s*\{[^{}]*ADISCORD_line_artillery\s*=\s*1",
        )

    def test_collapse_has_a_reachable_20_width_armored_template(self) -> None:
        templates = read("common/ai_templates/ADISCORD_land_templates.txt")
        block = named_block(templates, "ADISCORD_vorkerland_mobile_reserve")
        for token in (
            "tag = WKR",
            "tag = VAD",
            "tag = TVA",
            "has_global_flag = ADISCORD_vorkerland_collapse_wars_started",
            "NOT = { has_global_flag = ADISCORD_vorkerland_collapse_finished }",
            "has_tech = ADISCORD_tech_semi_autonomous_combat_modules",
            "num_of_military_factories > 2",
        ):
            self.assertIn(token, block)
        target = named_block(block, "target_template")
        self.assertRegex(
            target,
            r"regiments\s*=\s*\{[^{}]*ADISCORD_mechanized_infantry\s*=\s*6",
        )
        self.assertRegex(
            target,
            r"regiments\s*=\s*\{[^{}]*ADISCORD_combat_platform\s*=\s*4",
        )
        for support in ("engineer", "artillery", "maintenance_company", "signal_company"):
            self.assertRegex(target, rf"\b{support}\s*=\s*1")

    def test_all_ai_armored_designs_use_20_width_line_battalions(self) -> None:
        templates = read("common/ai_templates/ADISCORD_land_templates.txt")
        expected = {
            "ADISCORD_vorkerland_mobile_reserve": "ADISCORD_combat_platform",
            "ADISCORD_tank_battlegroup": "ADISCORD_combat_platform",
            "ADISCORD_networked_tank_battlegroup": "ADISCORD_combat_platform",
            "ADISCORD_heavy_tank_battlegroup": "ADISCORD_heavy_platform",
        }
        for design, platform in expected.items():
            target = named_block(named_block(templates, design), "target_template")
            self.assertRegex(
                target,
                r"regiments\s*=\s*\{[^{}]*ADISCORD_mechanized_infantry\s*=\s*6",
            )
            self.assertRegex(
                target,
                rf"regiments\s*=\s*\{{[^{{}}]*{platform}\s*=\s*4",
            )

    def test_all_claimants_start_with_the_same_full_armored_group(self) -> None:
        expected = {
            "history/units/WRK.txt": "Workerland Mobile Group",
            "history/units/VAD.txt": "Armi Mobile Group",
            "history/units/TVA_vorkerland_collapse.txt": "TVA Mobile Test Group",
        }
        for relative, template_name in expected.items():
            templates = named_blocks(read(relative), "division_template")
            block = next(
                (
                    candidate
                    for candidate in templates
                    if f'name = "{template_name}"' in candidate
                ),
                None,
            )
            self.assertIsNotNone(block, f"missing {template_name} in {relative}")
            self.assertEqual(block.count("ADISCORD_combat_platform = {"), 4)
            self.assertEqual(block.count("ADISCORD_mechanized_infantry = {"), 6)
            for support in (
                "engineer",
                "artillery",
                "maintenance_company",
                "signal_company",
            ):
                self.assertEqual(block.count(f"{support} = {{"), 1)

    def test_collapse_deliveries_can_equip_the_armored_groups(self) -> None:
        effects = source_section(read("common/scripted_effects/ADISCORD_vorkerland_effects.txt"), 'collapse_effects')
        setup = named_block(effects, "ADISCORD_vorkerland_prepare_initial_combatants")
        for tag in ("WKR", "VAD"):
            claimant = named_block(setup, tag)
            for delivery in (
                f"type = ADISCORD_combat_platform_2170 amount = 180 producer = {tag}",
                f"type = ADISCORD_armored_carrier_2163 amount = 260 producer = {tag}",
                f"type = ADISCORD_squad_weapons_equipment_0 amount = 60 producer = {tag}",
                f"type = support_equipment_1 amount = 100 producer = {tag}",
                f"type = artillery_equipment_1 amount = 24 producer = {tag}",
            ):
                self.assertIn(delivery, claimant)

        tva = named_block(effects, "ADISCORD_vorkerland_setup_tva")
        self.assertIn(
            "type = ADISCORD_combat_platform_2170 amount = 180 producer = TVA",
            tva,
        )
        self.assertIn(
            "type = ADISCORD_armored_carrier_2163 amount = 260 producer = TVA",
            tva,
        )
        self.assertIn(
            "type = ADISCORD_squad_weapons_equipment_0 amount = 60 producer = TVA",
            tva,
        )

    def test_collapse_ai_sustains_armor_and_fighter_production(self) -> None:
        strategies = source_section(read(
            "common/ai_strategy/ADISCORD_vorkerland_ai.txt"
        ), 'force_design_ai')
        armor = named_block(
            strategies, "ADISCORD_vorkerland_armored_reserve_program"
        )
        air = named_block(strategies, "ADISCORD_vorkerland_air_denial_program")
        wkr_air = named_block(
            strategies, "ADISCORD_vorkerland_wkr_air_denial_program"
        )
        operations = named_block(
            strategies, "ADISCORD_vorkerland_active_air_operations"
        )
        for tag in ("WKR", "VAD", "TVA"):
            self.assertIn(f"tag = {tag}", armor)
            self.assertIn(f"tag = {tag}", operations)
        self.assertNotIn("tag = WKR", air)
        for tag in ("VAD", "TVA"):
            self.assertIn(f"tag = {tag}", air)
        self.assertIn("allowed = { tag = WKR }", wkr_air)
        self.assertNotIn("tag = VAD", wkr_air)
        self.assertNotIn("tag = TVA", wkr_air)
        self.assertIn(
            "equipment_variant_production_factor id = "
            "ADISCORD_combat_platform_archetype value = 35",
            armor,
        )
        self.assertIn(
            "equipment_variant_production_factor id = "
            "ADISCORD_armored_carrier_archetype value = 35",
            armor,
        )
        for profile in (air, wkr_air):
            self.assertIn("equipment_production_factor id = fighter value = 28", profile)
            self.assertIn("equipment_production_factor id = cas value = 10", profile)
        self.assertIn(
            "equipment_variant_production_factor id = ADISCORD_fighter_archetype",
            air,
        )
        self.assertIn(
            "equipment_variant_production_factor id = ADISCORD_fighter_archetype",
            wkr_air,
        )
        self.assertIn(
            "type = strategic_air_importance id = 12 value = 100000", operations
        )
        self.assertIn(
            "type = strategic_air_importance id = 9 value = 100000", operations
        )
        self.assertIn("has_war = yes", operations)
        self.assertNotIn("num_of_military_factories", operations)
        self.assertNotIn("has_tech", operations)
        self.assertNotIn("strategic_air_importance", air)

    def test_wkr_air_focus_adds_demand_without_reserving_more_factories(self) -> None:
        policies = read("common/ai_strategy/ADISCORD_vorkerland_ai.txt")
        focus = named_block(policies, "ADISCORD_vorkerland_wkr_focus_air_sustainment")
        self.assertIn("has_country_flag = ADISCORD_vorkerland_focus_wkr_air_sustainment", focus)
        self.assertIn("abort_when_not_enabled = yes", focus)
        self.assertNotIn("equipment_production_min_factories", focus)
        strategies = named_blocks(focus, "ai_strategy")
        for equipment, archetype in (("fighter", "ADISCORD_fighter_archetype"), ("cas", "ADISCORD_cas_archetype")):
            for kind, identifier in (
                ("unit_ratio", equipment),
                ("equipment_production_factor", equipment),
                ("equipment_variant_production_factor", archetype),
            ):
                matching = [strategy for strategy in strategies if re.search(
                    rf"\btype\s*=\s*{kind}\s+id\s*=\s*{identifier}\b", strategy
                )]
                self.assertEqual(len(matching), 1, (kind, identifier))
                self.assertGreater(int(re.search(r"\bvalue\s*=\s*(\d+)", matching[0])[1]), 0)

    def test_air_subunit_roles_use_the_engine_scalar_contract(self) -> None:
        air_units = read("common/units/ADISCORD_air_units.txt")
        expected = {
            "fighter": "fighter",
            "cas": "cas",
            "tac_bomber": "tactical_bomber",
        }
        for subunit, role in expected.items():
            block = named_block(air_units, subunit)
            self.assertRegex(block, rf"(?m)^\s*type\s*=\s*{role}\s*$")
            self.assertNotRegex(block, rf"type\s*=\s*\{{\s*{role}\s*\}}")

    def test_custom_aircraft_have_personnel_and_combat_missions(self) -> None:
        equipment = read("common/units/equipment/ADISCORD_air_equipment.txt")
        archetypes = {
            "ADISCORD_fighter_archetype": 20,
            "ADISCORD_cas_archetype": 20,
            "ADISCORD_rocket_strike_archetype": 40,
        }
        for archetype, manpower in archetypes.items():
            block = named_block(equipment, archetype)
            self.assertRegex(block, rf"(?m)^\s*manpower\s*=\s*{manpower}\s*$")
            self.assertRegex(
                block, r"(?m)^\s*allow_mission_type\s*=\s*training\s*$"
            )

        missions = {
            "ADISCORD_fighter_airframe_2163": {"air_superiority", "interception"},
            "ADISCORD_cas_airframe_2170": {"cas", "attack_logistics"},
            "ADISCORD_rocket_strike_platform_2183": {"strategic_bomber"},
        }
        for model, expected in missions.items():
            mission_block = named_block(
                named_block(equipment, model), "allow_mission_type"
            )
            self.assertEqual(set(re.findall(r"\b[A-Za-z_]+\b", mission_block)), expected)

    def test_claimants_receive_visible_fighter_and_cas_wings(self) -> None:
        expected = {
            "WKR": (
                "history/units/WRK_vorkerland_collapse_air.txt",
                "WRK_vorkerland_collapse_air",
                "32",
                2,
                2,
            ),
            "VAD": (
                "history/units/VAD_vorkerland_collapse_air.txt",
                "VAD_vorkerland_collapse_air",
                "75",
                1,
                1,
            ),
            "TVA": (
                "history/units/TVA_vorkerland_collapse_air.txt",
                "TVA_vorkerland_collapse_air",
                "38",
                1,
                1,
            ),
        }
        for tag, (relative, _, state, fighter_wings, cas_wings) in expected.items():
            wings = named_block(read(relative), "air_wings")
            airfield = named_block(wings, state)
            self.assertEqual(
                airfield.count(
                    f'ADISCORD_fighter_airframe_2163 = {{ owner = "{tag}" amount = 100 }}'
                ),
                fighter_wings,
            )
            self.assertEqual(
                airfield.count(
                    f'ADISCORD_cas_airframe_2170 = {{ owner = "{tag}" amount = 50 }}'
                ),
                cas_wings,
            )

        collapse = source_section(read("common/scripted_effects/ADISCORD_vorkerland_effects.txt"), 'collapse_effects')
        initial = named_block(collapse, "ADISCORD_vorkerland_prepare_initial_combatants")
        wkr = named_block(initial, "WKR")
        vad = named_block(initial, "VAD")
        self.assertIn('load_oob = "WRK_vorkerland_collapse_air"', wkr)
        self.assertIn('load_oob = "VAD_vorkerland_collapse_air"', vad)
        self.assertIn("add_fuel = 15000", wkr)
        self.assertIn("add_fuel = 7500", vad)
        self.assertIn(
            "type = ADISCORD_fighter_airframe_2163 amount = 60 producer = WKR",
            wkr,
        )
        self.assertIn(
            "type = ADISCORD_cas_airframe_2170 amount = 30 producer = WKR",
            wkr,
        )
        self.assertIn(
            "set_country_flag = ADISCORD_vorkerland_wkr_air_sustainment_v1_applied",
            wkr,
        )
        self.assertNotIn("add_equipment_production", wkr)
        for technology in (
            "ADISCORD_tech_semi_autonomous_combat_modules = 1",
            "ADISCORD_tech_reclaimed_jet_platforms = 1",
            "ADISCORD_tech_battlefield_attack_aircraft = 1",
        ):
            self.assertIn(technology, wkr)
            self.assertLess(
                wkr.index(technology),
                wkr.index(
                    "type = ADISCORD_fighter_airframe_2163 amount = 60 producer = WKR"
                ),
            )
            self.assertLess(
                wkr.index(technology),
                wkr.index('load_oob = "WRK_vorkerland_collapse_air"'),
            )
        tva_setup = named_block(collapse, "ADISCORD_vorkerland_setup_tva")
        self.assertIn('load_oob = "TVA_vorkerland_collapse_air"', tva_setup)
        self.assertIn("add_fuel = 7500", tva_setup)
        for setup in (wkr, vad, tva_setup):
            self.assertIn(
                "set_country_flag = ADISCORD_vorkerland_air_mission_contract_v2_applied",
                setup,
            )

        force_design_effects = source_section(read(
            "common/scripted_effects/ADISCORD_vorkerland_effects.txt"
        ), 'force_design_effects')
        for legacy_repair in (
            "ADISCORD_vorkerland_deploy_missing_claimant_air_wings",
            "ADISCORD_vorkerland_redeploy_air_wings_after_mission_fix",
        ):
            self.assertNotIn(legacy_repair, force_design_effects)

    def test_fresh_outbreak_runs_one_bounded_ai_bootstrap_per_claimant(self) -> None:
        effects = source_section(read(
            "common/scripted_effects/ADISCORD_vorkerland_effects.txt"
        ), 'force_design_effects')
        block = named_block(effects, "ADISCORD_vorkerland_bootstrap_ai_force_designs")
        self.assertIn("is_ai = yes", block)
        self.assertIn(
            "NOT = { has_country_flag = ADISCORD_vorkerland_force_designs_bootstrapped }",
            block,
        )
        self.assertEqual(
            block.count(
                "set_country_flag = ADISCORD_vorkerland_force_designs_bootstrapped"
            ),
            1,
        )
        self.assertIn("ADISCORD_tech_semi_autonomous_combat_modules = 1", block)
        self.assertIn("ADISCORD_tech_armored_carrier_program = 1", block)
        self.assertIn("ADISCORD_tech_reclaimed_jet_platforms = 1", block)
        self.assertIn("ADISCORD_tech_battlefield_attack_aircraft = 1", block)
        self.assertIn("type = ADISCORD_combat_platform_2170", block)
        self.assertIn("ADISCORD_combat_platform_archetype < 120", block)
        self.assertIn("amount = 160", block)
        self.assertIn("type = ADISCORD_armored_carrier_2163", block)
        self.assertIn("ADISCORD_armored_carrier_archetype < 200", block)
        self.assertIn("amount = 260", block)
        for equipment_id, amount in (
            ("infantry_equipment_0", 500),
            ("ADISCORD_squad_weapons_equipment_0", 40),
            ("support_equipment_1", 80),
            ("artillery_equipment_1", 12),
        ):
            self.assertIn(f"type = {equipment_id}", block)
            self.assertIn(f"amount = {amount}", block)
        self.assertIn("type = ADISCORD_fighter_airframe_2163", block)
        self.assertIn("type = ADISCORD_cas_airframe_2170", block)
        on_actions = read(
            "common/on_actions/01_ADISCORD_vorkerland_collapse_on_actions.txt"
        )
        self.assertNotIn("on_weekly =", on_actions)
        events = source_section(read("events/ADISCORD_vorkerland_events.txt"), 'collapse_events')
        outbreak = event_block(events, "ADISCORD_vorkerland_collapse.2")
        wartime = outbreak.index(
            "set_global_flag = ADISCORD_vorkerland_collapse_wars_started"
        )
        for tag in ("WKR", "VAD", "TVA"):
            call = (
                f"{tag} = {{ ADISCORD_vorkerland_bootstrap_ai_force_designs = yes }}"
            )
            self.assertEqual(outbreak.count(call), 1)
            self.assertLess(wartime, outbreak.index(call))


class StartingCoastalFleetTests(unittest.TestCase):
    def test_patrol_platform_is_available_before_startup_technology_grants(self) -> None:
        equipment = read("common/units/equipment/ADISCORD_convoy_equipment.txt")
        hull = named_block(equipment, "ADISCORD_coastal_patrol_ship_1")
        self.assertRegex(hull, r"\bactive\s*=\s*yes\b")
        self.assertRegex(hull, r"\barchetype\s*=\s*ADISCORD_coastal_patrol_ship\b")
        subunit = named_block(
            read("common/units/ADISCORD_naval_units.txt"),
            "ADISCORD_coastal_patrol_vessel",
        )
        self.assertRegex(subunit, r"\bactive\s*=\s*yes\b")
        self.assertRegex(
            named_block(subunit, "need"), r"\bADISCORD_coastal_patrol_ship\s*=\s*1\b"
        )
        self.assertNotIn("module_slots", equipment)

    def test_starting_fleets_use_owned_coastal_ports_and_complete_hulls(self) -> None:
        countries = {
            "NOD": (6, 12434, "30-Cussington.txt"),
            "STP": (4, 16366, "28-Fada.txt"),
            "VAL": (4, 16535, "48-Depoitodron.txt"),
        }
        provinces = {
            row.split(";")[0]: row.split(";")
            for row in read("map/definition.csv").splitlines()
        }
        names: set[str] = set()
        for tag, (count, port, state_file) in countries.items():
            with self.subTest(tag=tag):
                country_file = next((ROOT / "history/countries").glob(f"{tag} - *.txt"))
                self.assertRegex(country_file.read_text(encoding="utf-8-sig"), rf'oob\s*=\s*"{tag}"')
                fleets = named_blocks(named_block(read(f"history/units/{tag}.txt"), "units"), "fleet")
                self.assertEqual(len(fleets), 1)
                self.assertRegex(fleets[0], rf"naval_base\s*=\s*{port}\b")
                forces = named_blocks(fleets[0], "task_force")
                self.assertEqual(len(forces), 1)
                self.assertRegex(forces[0], rf"location\s*=\s*{port}\b")
                ships = named_blocks(forces[0], "ship")
                self.assertEqual(len(ships), count)
                for ship in ships:
                    values = {entry.key: entry.value for entry in parse_clausewitz(ship)}
                    self.assertEqual(values["definition"], "ADISCORD_coastal_patrol_vessel")
                    self.assertNotIn(values["name"], names)
                    names.add(values["name"])
                    equipment = values["equipment"]
                    self.assertEqual([entry.key for entry in equipment], ["ADISCORD_coastal_patrol_ship_1"])
                    hull = {entry.key: entry.value for entry in equipment[0].value}
                    self.assertEqual(hull, {"amount": "1", "owner": tag})
                state = named_block(read(f"history/states/{state_file}"), "state")
                self.assertRegex(named_block(state, "provinces"), rf"\b{port}\b")
                history = named_block(state, "history")
                self.assertRegex(history, rf"owner\s*=\s*{tag}\b")
                base = named_block(named_block(history, "buildings"), str(port))
                self.assertRegex(base, r"naval_base\s*=\s*[1-9]\d*\b")
                self.assertEqual(provinces[str(port)][4:6], ["land", "true"])


class EquipmentPictureTests(unittest.TestCase):
    def test_every_custom_subunit_has_designer_and_onmap_icons(self) -> None:
        units = read("common/units/ADISCORD_land_units.txt")
        subunit_keys = set(
            re.findall(r"(?m)^\s*(ADISCORD_[A-Za-z0-9_]+)\s*=\s*\{", units)
        )
        sprites = read("interface/ADISCORD_subuniticons.gfx")
        sprite_blocks = {
            name: block
            for block, name in re.findall(
                r'spriteType\s*=\s*\{([^{}]*?name\s*=\s*"([^"]+)"[^{}]*?)\}',
                sprites,
                flags=re.DOTALL,
            )
        }

        missing: list[str] = []
        missing_textures: list[str] = []
        for key in sorted(subunit_keys):
            for suffix in ("medium", "medium_white"):
                sprite_name = f"GFX_unit_{key}_icon_{suffix}"
                block = sprite_blocks.get(sprite_name)
                if block is None:
                    missing.append(sprite_name)
                    continue
                texture_match = re.search(
                    r'texturefile\s*=\s*"([^"]+)"', block, flags=re.IGNORECASE
                )
                self.assertIsNotNone(texture_match, sprite_name)
                texture = Path(texture_match.group(1).replace("/", "\\"))
                if not (ROOT / texture).exists() and not (BASE_GAME / texture).exists():
                    missing_textures.append(f"{sprite_name}: {texture_match.group(1)}")

        self.assertEqual(missing, [], f"missing custom subunit sprites: {missing}")
        self.assertEqual(
            missing_textures,
            [],
            f"missing custom subunit textures: {missing_textures}",
        )

        combat = sprite_blocks["GFX_unit_ADISCORD_combat_platform_icon_medium"]
        self.assertIn("unit_medium_tank_icon.dds", combat)
        combat_white = sprite_blocks[
            "GFX_unit_ADISCORD_combat_platform_icon_medium_white"
        ]
        self.assertIn("onmap_unit_medium_tank_icon.dds", combat_white)

    def test_every_custom_equipment_picture_has_a_case_exact_sprite(self) -> None:
        picture_keys: set[str] = set()
        for path in (ROOT / "common" / "units" / "equipment").glob(
            "ADISCORD_*.txt"
        ):
            picture_keys.update(
                re.findall(r"\bpicture\s*=\s*([A-Za-z0-9_]+)", path.read_text(encoding="utf-8-sig"))
            )

        gfx_text = "\n".join(
            path.read_text(encoding="utf-8-sig", errors="ignore")
            for path in (ROOT / "interface").rglob("*.gfx")
        )
        if BASE_GAME.exists():
            gfx_text += "\n" + (
                BASE_GAME / "interface" / "Technologies.gfx"
            ).read_text(encoding="utf-8-sig", errors="ignore")
        sprite_names = set(
            re.findall(r'\bname\s*=\s*"(GFX_[A-Za-z0-9_]+_medium)"', gfx_text)
        )
        missing = sorted(
            key for key in picture_keys if f"GFX_{key}_medium" not in sprite_names
        )
        self.assertEqual(missing, [], f"unresolved equipment picture keys: {missing}")

    def test_buildable_air_and_armor_models_have_explicit_pictures(self) -> None:
        expected = {
            "ADISCORD_fighter_airframe_2163": "archetype_fighter_equipment",
            "ADISCORD_interceptor_airframe_2183": "archetype_fighter_equipment",
            "ADISCORD_cas_airframe_2170": "archetype_CAS_equipment",
            "ADISCORD_vtol_airframe_2170": "archetype_CAS_equipment",
            "ADISCORD_drone_airframe_2183": "archetype_CAS_equipment",
            "ADISCORD_combat_platform_2170": "archetype_medium_tank_equipment",
            "ADISCORD_combat_platform_2183": "archetype_medium_tank_equipment",
            "ADISCORD_combat_platform_2200": "archetype_medium_tank_equipment",
        }
        equipment = read("common/units/equipment/ADISCORD_air_equipment.txt")
        equipment += "\n" + read("common/units/equipment/ADISCORD_armor_equipment.txt")
        for equipment_id, picture in expected.items():
            self.assertIn(f"picture = {picture}", named_block(equipment, equipment_id))

    def test_economy_interface_textures_exist_and_are_valid_dds(self) -> None:
        directory = ROOT / "gfx" / "interface" / "ADISCORD_economy_gui"
        expected = {
            "economy_button.dds",
            "economy_expenses_bg.dds",
            "economy_header_bg.dds",
            "economy_income_bg.dds",
            "economy_loans_bg.dds",
            "economy_slider_button.dds",
            "economy_topbar_button.dds",
            "economy_command_bg.dds",
            "economy_dashboard_bg.dds",
            "economy_kpi_balance_bg.dds",
            "economy_kpi_expenses_bg.dds",
            "economy_kpi_income_bg.dds",
            "economy_kpi_treasury_bg.dds",
            "economy_status_bg.dds",
            "treasury_icon.dds",
        }
        self.assertEqual({path.name for path in directory.glob("*.dds")}, expected)
        for name in expected:
            data = (directory / name).read_bytes()[:20]
            self.assertGreaterEqual(len(data), 20, name)
            self.assertEqual(data[:4], b"DDS ", name)
            self.assertGreater(int.from_bytes(data[12:16], "little"), 0, name)
            self.assertGreater(int.from_bytes(data[16:20], "little"), 0, name)


class NorthernStartingForceTests(unittest.TestCase):
    @staticmethod
    def value(entries, key, default=None):
        return next((entry.value for entry in entries if entry.key == key), default)

    def test_starting_air_forces_have_technology_airfields_fuel_and_replacement_lines(self) -> None:
        states = {}
        for path in (ROOT / "history/states").glob("*.txt"):
            state = self.value(parse_clausewitz(path.read_text(encoding="utf-8-sig")), "state")
            states[int(self.value(state, "id"))] = self.value(state, "history", [])
        air_profile = named_block(read("common/scripted_effects/ADISCORD_technology_baseline_effects.txt"), "ADISCORD_grant_technology_profile_air")
        self.assertIn("ADISCORD_tech_reclaimed_jet_platforms = 1", air_profile)
        technology = named_block(read("common/technologies/ADISCORD_air.txt"), "ADISCORD_tech_reclaimed_jet_platforms")
        self.assertIn("ADISCORD_fighter_airframe_2163", named_block(technology, "enable_equipments"))

        for tag, expected in {"NOD": 500, "STP": 300, "VAL": 800}.items():
            with self.subTest(tag=tag):
                country_path = next((ROOT / "history/countries").glob(f"{tag} - *.txt"))
                country = country_path.read_text(encoding="utf-8-sig")
                self.assertLess(country.index("ADISCORD_grant_technology_profile_air = yes"), country.index(f'oob = "{tag}"'))
                entries = parse_clausewitz(read(f"history/units/{tag}.txt"))
                total = 0
                for base in self.value(entries, "air_wings", []):
                    history = states[int(base.key)]
                    self.assertEqual(self.value(history, "owner"), tag)
                    capacity = int(self.value(self.value(history, "buildings", []), "air_base", "0")) * 200
                    aircraft = 0
                    for wing in base.value:
                        self.assertEqual(wing.key, "ADISCORD_fighter_airframe_2163")
                        self.assertEqual(self.value(wing.value, "owner"), tag)
                        aircraft += int(self.value(wing.value, "amount"))
                    self.assertLessEqual(aircraft, capacity)
                    total += aircraft
                self.assertEqual(total, expected)
                effect = self.value(entries, "instant_effect", [])
                fuel = float(self.value(effect, "add_fuel", "0"))
                self.assertGreaterEqual(fuel, 30000)
                self.assertLessEqual(fuel, 50000)
                self.assertTrue(any(
                    self.value(self.value(entry.value, "equipment", []), "type") == "ADISCORD_fighter_airframe_2163"
                    for entry in effect if entry.key == "add_equipment_production"
                ))

    def test_northern_armies_have_owned_spawns_and_a_bounded_material_advantage(self) -> None:
        # Compare actual template equipment needs, not just the number of divisions.
        subunits = {
            entry.key: entry.value
            for entry in self.value(parse_clausewitz(read("common/units/ADISCORD_land_units.txt")), "sub_units")
        }
        province_owner = {}
        province_state = {}
        for path in (ROOT / "history/states").glob("*.txt"):
            state = self.value(parse_clausewitz(path.read_text(encoding="utf-8-sig")), "state")
            owner = self.value(self.value(state, "history", []), "owner")
            for province in self.value(state, "provinces", []):
                province_owner[int(province.value)] = owner
                province_state[int(province.value)] = int(self.value(state, "id"))

        issued_rifles = {}
        nod_readiness = {
            "Cussington Guard": .80,
            "Nodral Line Infantry": .70,
            "Cussington Security": .60,
            "Nodral Armored Group": .80,
            "Nodral Mountain Infantry": .80,
        }
        for tag, count in {"NOD": 38, "YPR": 18, "COF": 8, "TFF": 16}.items():
            entries = parse_clausewitz(read(f"history/units/{tag}.txt"))
            templates = {
                self.value(entry.value, "name"): entry.value
                for entry in entries if entry.key == "division_template"
            }
            divisions = [entry.value for entry in self.value(entries, "units") if entry.key == "division"]
            self.assertEqual(len(divisions), count, tag)
            locations = [int(self.value(division, "location")) for division in divisions]
            self.assertLessEqual(max(locations.count(location) for location in locations), 2, tag)
            self.assertFalse({province_state[location] for location in locations} & {303, 304})
            issued_rifles[tag] = 0
            for division in divisions:
                template_name = self.value(division, "division_template")
                template = templates[template_name]
                regiments = self.value(template, "regiments")
                factor = float(self.value(division, "start_equipment_factor"))
                # Guards, line infantry and local militia retain different readiness.
                expected = (
                    nod_readiness[template_name]
                    if tag == "NOD"
                    else {9: .80, 6: .75, 3: .65}[len(regiments)]
                )
                self.assertAlmostEqual(factor, expected)
                self.assertEqual(province_owner[int(self.value(division, "location"))], tag)
                for slot in regiments + self.value(template, "support", []):
                    needs = self.value(subunits[slot.key], "need", [])
                    issued_rifles[tag] += float(self.value(needs, "infantry_equipment", "0")) * factor
        ratio = issued_rifles["NOD"] / sum(issued_rifles[tag] for tag in ("YPR", "COF", "TFF"))
        self.assertGreater(ratio, 1.0)
        self.assertLess(ratio, 1.45)

    def test_northern_coalition_can_prepare_from_day_one_with_real_recruitment_laws(self) -> None:
        dormant = named_block(read("common/scripted_triggers/ADISCORD_minor_optimization_triggers.txt"), "ADISCORD_is_non_participating_minor")
        dormant_tags = set(re.findall(r"\btag\s*=\s*([A-Z0-9]{3})\b", dormant))
        self.assertIn("AIN", dormant_tags)
        for tag, filename in {
            "YPR": "YPR - YuboraPeopleRepublic.txt",
            "COF": "COF - CultOfTheForest.txt",
            "TFF": "TFF - TheFreeFrontier.txt",
        }.items():
            with self.subTest(tag=tag):
                self.assertNotIn(tag, dormant_tags)
                history = read(f"history/countries/{filename}")
                ideas = named_block(history, "add_ideas")
                self.assertRegex(ideas, r"\bextensive_conscription\b")
                if tag in {"COF", "TFF"}:
                    self.assertIn("ADISCORD_military_organization_militia_autonomy", ideas)
                self.assertNotIn("add_manpower", history)
        laws = read("common/ideas/_manpower.txt")
        self.assertIn("conscription = 0.025", named_block(laws, "limited_conscription"))
        self.assertIn("conscription = 0.01", named_block(read("common/ideas/ADISCORD_laws.txt"), "ADISCORD_military_organization_militia_autonomy"))

    def test_northern_starts_keep_people_and_equipment_for_replacements(self) -> None:
        # Derive the recruitment pool from current laws and state populations.
        ideas = {}
        default_laws = {}
        for path in (ROOT / "common/ideas").glob("*.txt"):
            for category in self.value(parse_clausewitz(path.read_text(encoding="utf-8-sig")), "ideas", []):
                if not isinstance(category.value, list):
                    continue
                is_law = self.value(category.value, "law") == "yes"
                for idea in category.value:
                    if not isinstance(idea.value, list):
                        continue
                    ideas[idea.key] = (category.key, idea.value)
                    if is_law and self.value(idea.value, "default") == "yes":
                        default_laws[category.key] = idea.key
        populations = {tag: 0 for tag in ("NOD", "YPR", "COF", "TFF")}
        factories = dict.fromkeys(populations, 0)
        for path in (ROOT / "history/states").glob("*.txt"):
            state = self.value(parse_clausewitz(path.read_text(encoding="utf-8-sig")), "state")
            history = self.value(state, "history", [])
            owner = self.value(history, "owner")
            if owner not in populations:
                continue
            self.assertIn(owner, [e.value for e in history if e.key == "add_core_of"])
            populations[owner] += float(self.value(state, "manpower", "0"))
            factories[owner] += int(self.value(self.value(history, "buildings", []), "arms_factory", "0"))
        subunits = {}
        for relative in ("common/units/ADISCORD_land_units.txt", "common/units/ADISCORD_naval_units.txt"):
            subunits.update({e.key: e.value for e in self.value(parse_clausewitz(read(relative)), "sub_units")})

        for tag in populations:
            with self.subTest(tag=tag):
                history_path = next((ROOT / "history/countries").glob(f"{tag} - *.txt"))
                history = parse_clausewitz(history_path.read_text(encoding="utf-8-sig"))
                selected = default_laws.copy()
                country_ideas = []
                for entry in self.value(history, "add_ideas", []):
                    if entry.value not in ideas:
                        continue
                    category, _ = ideas[entry.value]
                    if category in default_laws:
                        selected[category] = entry.value
                    else:
                        country_ideas.append(entry.value)
                rate = factor = 0
                for idea_id in list(selected.values()) + country_ideas:
                    modifiers = self.value(ideas[idea_id][1], "modifier", [])
                    rate += float(self.value(modifiers, "conscription", "0"))
                    factor += float(self.value(modifiers, "conscription_factor", "0"))
                pool = populations[tag] * rate * (1 + factor)
                entries = parse_clausewitz(read(f"history/units/{tag}.txt"))
                templates = {self.value(e.value, "name"): e.value for e in entries if e.key == "division_template"}
                units = self.value(entries, "units")
                army_manpower = rifle_deficit = 0
                equipment_needs = {}
                equipment_deficits = {}
                for division in [e.value for e in units if e.key == "division"]:
                    template = templates[self.value(division, "division_template")]
                    equipment_factor = float(self.value(division, "start_equipment_factor", "1"))
                    for slot in self.value(template, "regiments") + self.value(template, "support", []):
                        subunit = subunits[slot.key]
                        army_manpower += float(self.value(subunit, "manpower", "0"))
                        rifles = float(self.value(self.value(subunit, "need", []), "infantry_equipment", "0"))
                        rifle_deficit += rifles * (1 - equipment_factor)
                        for need in self.value(subunit, "need", []):
                            amount = float(need.value)
                            equipment_needs[need.key] = equipment_needs.get(need.key, 0) + amount
                            equipment_deficits[need.key] = equipment_deficits.get(need.key, 0) + amount * (1 - equipment_factor)

                def navy_manpower(block):
                    total = 0
                    for entry in block:
                        if entry.key == "ship":
                            definition = self.value(entry.value, "definition")
                            total += float(self.value(subunits[definition], "manpower", "0"))
                        elif isinstance(entry.value, list):
                            total += navy_manpower(entry.value)
                    return total

                reserve_share = .2 if tag in {"YPR", "COF"} else .1
                air_manpower = sum(
                    float(self.value(wing.value, "amount", "0")) * 20
                    for base in self.value(entries, "air_wings", [])
                    for wing in base.value
                )
                self.assertGreaterEqual(pool - army_manpower - navy_manpower(units) - air_manpower, army_manpower * reserve_share)
                effect = self.value(entries, "instant_effect")
                stocks = [e.value for e in effect if e.key == "add_equipment_to_stockpile" and self.value(e.value, "type") == "infantry_equipment_0"]
                self.assertEqual(len(stocks), 1)
                self.assertEqual(self.value(stocks[0], "producer"), tag)
                self.assertGreaterEqual(float(self.value(stocks[0], "amount")) - rifle_deficit, 610)
                available = {
                    "ADISCORD_squad_weapons_equipment": 400 if factories[tag] > 6 else 200,
                    "support_equipment": 300 if factories[tag] > 6 else 150,
                }
                variants = {
                    "infantry_equipment_0": "infantry_equipment",
                    "ADISCORD_squad_weapons_equipment_0": "ADISCORD_squad_weapons_equipment",
                    "support_equipment_1": "support_equipment",
                    "artillery_equipment_1": "artillery_equipment",
                    "train_equipment_1": "train_equipment",
                    "motorized_equipment_1": "motorized_equipment",
                    "ADISCORD_anti_air_equipment_2163": "anti_air_equipment",
                    "ADISCORD_combat_platform_2170": "ADISCORD_combat_platform_archetype",
                }
                for stock in [e.value for e in effect if e.key == "add_equipment_to_stockpile"]:
                    archetype = variants[self.value(stock, "type")]
                    available[archetype] = available.get(archetype, 0) + float(self.value(stock, "amount"))
                for archetype, need in equipment_needs.items():
                    self.assertGreaterEqual(available.get(archetype, 0) - equipment_deficits[archetype], need * .25, (tag, archetype))
                self.assertGreaterEqual(available.get("train_equipment", 0), 8, tag)
                self.assertGreaterEqual(available.get("motorized_equipment", 0), 60, tag)
                lines = [e.value for e in effect if e.key == "add_equipment_production"]
                requested = sum(int(self.value(line, "requested_factories")) for line in lines)
                self.assertLessEqual(requested, factories[tag])
                self.assertGreater(requested, 0)
                self.assertTrue(any(self.value(self.value(line, "equipment"), "type") == "infantry_equipment_0" for line in lines))
                self.assertNotIn("add_manpower", read(f"history/units/{tag}.txt"))

    def test_starting_production_has_domestic_inputs_after_exports(self) -> None:
        equipment = {}
        for path in (ROOT / "common/units/equipment").glob("*.txt"):
            equipment.update({entry.key: entry.value for entry in self.value(parse_clausewitz(path.read_text(encoding="utf-8-sig")), "equipments", [])})
        resources = {tag: {} for tag in ("NOD", "YPR", "COF", "TFF", "STP", "VAL")}
        factories = dict.fromkeys(resources, 0)
        for path in (ROOT / "history/states").glob("*.txt"):
            state = self.value(parse_clausewitz(path.read_text(encoding="utf-8-sig")), "state")
            history = self.value(state, "history", [])
            owner = self.value(history, "owner")
            if owner not in resources:
                continue
            factories[owner] += int(self.value(self.value(history, "buildings", []), "arms_factory", "0"))
            for resource in self.value(state, "resources", []):
                resources[owner][resource.key] = resources[owner].get(resource.key, 0) + float(resource.value)
            refineries = int(self.value(self.value(history, "buildings", []), "synthetic_refinery", "0"))
            resources[owner]["rubber"] = resources[owner].get("rubber", 0) + refineries
        trade_laws = self.value(self.value(parse_clausewitz(read("common/ideas/_economic.txt")), "ideas"), "trade_laws")
        export_share = float(self.value(self.value(self.value(trade_laws, "export_focus"), "modifier"), "min_export"))
        for tag in resources:
            inputs = {}
            entries = parse_clausewitz(read(f"history/units/{tag}.txt"))
            for line in [e.value for e in self.value(entries, "instant_effect") if e.key == "add_equipment_production"]:
                model = equipment[self.value(self.value(line, "equipment"), "type")]
                needs = self.value(model, "resources")
                if needs is None:
                    needs = self.value(equipment[self.value(model, "archetype")], "resources", [])
                for need in needs:
                    inputs[need.key] = inputs.get(need.key, 0) + float(need.value) * int(self.value(line, "requested_factories"))
            for resource, need in inputs.items():
                self.assertGreaterEqual(resources[tag].get(resource, 0) * (1 - export_share), need, (tag, resource))
        self.assertEqual(sum(factories[tag] for tag in ("YPR", "COF", "TFF")), factories["NOD"])


    def test_northern_technology_uses_existing_profiles_without_duplicated_history_grants(self) -> None:
        import ast

        module = ast.parse(read("tools/builders/build_adiscord_technology_system.py"))
        assignment = next(
            node for node in module.body
            if isinstance(node, ast.Assign)
            and any(isinstance(target, ast.Name) and target.id == "STARTING_COUNTRY_TECH_PROFILES" for target in node.targets)
        )
        profiles = ast.literal_eval(assignment.value)
        expected = {
            "NOD": ("industrial", "energy", "institutional", "land", "air", "naval"),
            "YPR": ("fragment_low_tech", "land", "field_air_defense"),
            "COF": ("fragment_low_tech", "field_air_defense"),
            "TFF": ("fragment_low_tech", "land", "field_air_defense"),
        }
        for tag, profile in expected.items():
            with self.subTest(tag=tag):
                self.assertEqual(profiles[tag], profile)
                history_path = next((ROOT / "history/countries").glob(f"{tag} - *.txt"))
                self.assertNotIn("set_technology", history_path.read_text(encoding="utf-8-sig"))



if __name__ == "__main__":
    unittest.main()
