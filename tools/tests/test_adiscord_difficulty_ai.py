"""Execute difficulty policy gates; native recruitment and combat need game checks."""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from tools.tests.test_adiscord_ai_production_lifecycle import OPS, child, parse
from tools.tests.test_adiscord_generic_wartime_fronts import named_block, named_blocks


ROOT = Path(__file__).resolve().parents[2]
PREFIX = "ADISCORD_difficulty_"


class DifficultyAIBehaviorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.policies = {}
        cls.campaigns = {}
        for path in (ROOT / "common/ai_strategy").glob("*.txt"):
            source = path.read_text(encoding="utf-8-sig")
            if path.name not in ("default.txt", "ADISCORD_difficulty_ai.txt"):
                for name in re.findall(r"(?m)^(\w+)\s*=\s*\{", source):
                    block = named_block(source, name)
                    controls = [part for part in named_blocks(block, "ai_strategy")
                                if re.search(r"type\s*=\s*front_control\b", part)]
                    if controls:
                        cls.campaigns[name] = parse("\n".join(
                            [named_block(block, "allowed"), named_block(block, "enable")] + controls))
            for name in re.findall(r"(?m)^(ADISCORD_difficulty_\w+)\s*=", source):
                if name in cls.policies:
                    raise AssertionError(f"duplicate difficulty policy: {name}")
                cls.policies[name] = parse(named_block(source, name))[0][2]
        cls.triggers = {}
        for path in (ROOT / "common/scripted_triggers").glob("*.txt"):
            source = path.read_text(encoding="utf-8-sig")
            for name in re.findall(r"(?m)^(ADISCORD_difficulty_\w+)\s*=", source):
                cls.triggers[name] = parse(named_block(source, name))[0][2]

    def context(self, tag="STS", difficulty=3, **changes):
        context = {
            "tag": tag,
            "difficulty": difficulty,
            "is_ai": True,
            "exists": True,
            "has_capitulated": False,
            "is_subject": False,
            "has_war": True,
            "has_manpower": 20000,
            "amount_manpower_in_deployment_queue": 0,
            "num_of_military_factories": 12,
            "num_of_supply_nodes": 1,
            "num_divisions": 16,
            "equipment": {"infantry_equipment": 6000, "motorized_equipment": 60},
            "has_tech": {
                "ADISCORD_tech_restored_truck_fleets",
                "ADISCORD_tech_improvised_air_defense",
                "ADISCORD_tech_semi_autonomous_combat_modules",
            },
            "has_idea": set(),
            "controls_province": set(),
            "stockpile": {"infantry_equipment": 0.1},
            "has_country_flag": set(),
            "has_global_flag": set(),
            "wars": {"STP"},
            "allies": set(),
            "countries": {},
            "scopes": {},
            "army_ratios": {},
            "variables": {},
            "ADISCORD_economy_ai_is_healthy": True,
            "ADISCORD_economy_ai_can_fund_advanced_forces": True,
            "ADISCORD_ai_has_adjacent_war_preparation": False,
            "ADISCORD_ai_army_replacement_pressure_cleared": True,
            "ADISCORD_ai_rifle_replacement_emergency": False,
            "ADISCORD_economy_nod_army_at_capacity": False,
            "ADISCORD_has_operational_naval_base": True,
            "ADISCORD_has_marine_training": True,
            "NOD_ai_northern_preparation": False,
            "NOD_ai_stelander_preparation": False,
            "VAL_ai_republics_preparation": False,
            "STP_pc_ai_preparing_val_war": False,
            "STP_pc_ai_preparing_nod_war": False,
            "ADISCORD_vorkerland_is_main_claimant": False,
            "ADISCORD_vorkerland_is_regional_combatant": False,
            "ADISCORD_nam_resource_war_preparation": False,
            "ADISCORD_nam_resource_war_active": False,
            "NAM_war_of_return_active": False,
            "ADISCORD_west_final_active": False,
            "ADISCORD_west_crisis_open": False,
            "ADISCORD_south_final_war_enabled": False,
            "ADISCORD_south_final_active": False,
            "ADISCORD_south_crisis_open": False,
            "ADISCORD_south_final_can_start": False,
            "convoys": 30,
        }
        context.update(changes)
        return context

    def evaluate(self, nodes, context):
        def predicate(key, op, value):
            if key in ("AND", "OR", "NOT"):
                results = (predicate(*node) for node in value)
                if key == "AND":
                    return all(results)
                if key == "OR":
                    return any(results)
                return not any(results)
            if key in self.triggers:
                return self.evaluate(self.triggers[key], context) == (value == "yes")
            if key in context["scopes"]:
                return self.evaluate(value, context["scopes"][key])
            if key in context["countries"]:
                return self.evaluate(value, context["countries"][key])
            if key in ("tag", "original_tag"):
                return context["tag"] == value
            if key in ("has_country_flag", "has_global_flag", "has_tech", "has_idea"):
                return value in context[key]
            if key == "controls_province":
                return int(value) in context[key]
            if key == "country_exists":
                return context["countries"][value]["exists"]
            if key == "stockpile_ratio":
                fields = {name: val for name, _, val in value}
                comparison = next(op for name, op, _ in value if name == "ratio")
                return OPS[comparison](context["stockpile"][fields["archetype"]], float(fields["ratio"]))
            if key == "has_variable":
                return value in context["variables"]
            if key == "has_war_with":
                target = context["scopes"].get(value, {}).get("tag", value)
                return target in context["wars"]
            if key == "is_controlled_by":
                return context["controller"] == context["scopes"][value]["tag"]
            if key == "fighting_army_strength_ratio":
                fields = {name: val for name, _, val in value}
                target = context["scopes"].get(fields["tag"], {}).get("tag", fields["tag"])
                comparison = next(op for name, op, _ in value if name == "ratio")
                return OPS[comparison](context["army_ratios"][target], float(fields["ratio"]))
            if key == "any_province_building_level":
                self.assertEqual(child(value, "province"), [("all_provinces", "=", "yes")])
                self.assertIn(("building", "=", "bunker"), value)
                _, comparison, threshold = next(node for node in value if node[0] == "level")
                return any(OPS[comparison](level, float(threshold)) for level in context["forts"])
            if key == "is_in_faction_with":
                return value in context["allies"]
            if key == "has_equipment":
                return all(OPS[comparison](context["equipment"].get(name, 0), float(amount))
                           for name, comparison, amount in value)
            if key == "check_variable":
                fields = {name: val for name, _, val in value}
                if "var" in fields:
                    name = fields["var"]
                    operand = fields["value"]
                    op = {"equals": "=", "less_than": "<", "greater_than": ">",
                          "greater_than_or_equals": ">=", "less_than_or_equals": "<="}[fields["compare"]]
                else:
                    name, op, operand = value[0]
                actual = context["variables"].get(name, context.get(name, 0))
                expected = context["variables"].get(operand)
                if expected is None:
                    expected = float(operand)
                return OPS[op](actual, expected)
            if key == "has_navy_size":
                fields = {name: val for name, _, val in value}
                self.assertEqual(fields["type"], "convoy")
                comparison = next(comparison for name, comparison, _ in value if name == "size")
                return OPS[comparison](context["convoys"], float(fields["size"]))
            if key in context:
                expected = {"yes": True, "no": False}.get(value)
                if expected is None:
                    expected = float(value)
                return OPS[op](context[key], expected)
            raise AssertionError(f"unsupported difficulty predicate: {key}")

        return all(predicate(*node) for node in nodes)

    def enabled(self, name, context):
        policy = self.policies.get(name)
        if policy is None:
            return False
        allowed = [body for key, _, body in policy if key == "allowed"]
        return (not allowed or self.evaluate(allowed[0], context)) and self.evaluate(child(policy, "enable"), context)

    def strategies(self, context):
        return [dict((key, value) for key, _, value in body)
                for name, policy in self.policies.items() if self.enabled(name, context)
                for kind, _, body in policy if kind == "ai_strategy"]

    def total(self, context, kind, identifier=None):
        return sum(float(strategy["value"]) for strategy in self.strategies(context)
                   if strategy["type"] == kind and strategy.get("id") == identifier)

    def test_levels_change_desired_recruitment_without_stacking(self):
        for difficulty, expected in enumerate((-20, -10, 0, 15, 30)):
            with self.subTest(difficulty=difficulty):
                self.assertEqual(self.total(self.context(difficulty=difficulty), "ai_wanted_divisions_factor"), expected)

    def test_middle_level_has_no_behavior_overlay(self):
        for tag in ("STP", "STS", "SRP", "NOD", "VAL", "RUS", "WKR", "NAM", "WRK", "SHL"):
            self.assertEqual(self.strategies(self.context(tag, 2)), [], tag)

    def test_peace_closes_pressure_and_a_new_threat_reopens_it(self):
        context = self.context(has_war=False, wars=set())
        self.assertEqual(self.strategies(context), [])
        context["ADISCORD_ai_has_adjacent_war_preparation"] = True
        self.assertEqual(self.total(context, "ai_wanted_divisions_factor"), 15)
        context["ADISCORD_ai_has_adjacent_war_preparation"] = False
        self.assertEqual(self.strategies(context), [])

    def test_handoff_capitulation_subjecthood_and_terminal_state_close_all_policies(self):
        for changes in (
            {"is_ai": False}, {"exists": False}, {"has_capitulated": True},
            {"is_subject": True}, {"has_country_flag": {"ADISCORD_non_participating_minor_optimized"}},
            {"has_global_flag": {"RUS_crisis_world_ended"}},
        ):
            for difficulty in (0, 1, 3, 4):
                with self.subTest(changes=changes, difficulty=difficulty):
                    self.assertEqual(self.strategies(self.context(difficulty=difficulty, **changes)), [])

    def test_expansion_respects_fractional_manpower_equipment_and_training(self):
        for changes, expected in (
            ({"has_manpower": 11999.9}, 0), ({"has_manpower": 12000}, 15),
            ({"amount_manpower_in_deployment_queue": 11999}, 15),
            ({"amount_manpower_in_deployment_queue": 12000}, 0),
            ({"equipment": {"infantry_equipment": 5999.9, "motorized_equipment": 60}}, 0),
            ({"equipment": {"infantry_equipment": 6000, "motorized_equipment": 59.9}}, 0),
            ({"equipment": {"infantry_equipment": 6000, "motorized_equipment": 60}}, 15),
        ):
            with self.subTest(changes=changes):
                self.assertEqual(self.total(self.context(**changes), "ai_wanted_divisions_factor"), expected)

    def test_existing_replenishment_and_budget_guards_win(self):
        for guard in ("ADISCORD_economy_ai_is_healthy", "ADISCORD_ai_army_replacement_pressure_cleared"):
            self.assertEqual(self.total(self.context(**{guard: False}), "ai_wanted_divisions_factor"), 0)
        context = self.context(ADISCORD_ai_army_replacement_pressure_cleared=False)
        self.assertGreater(self.total(context, "equipment_stockpile_surplus_ratio"), 0)

    def test_nod_recruitment_brake_is_not_cancelled_by_difficulty(self):
        for divisions, expected in ((19, 30), (20, 0), (25, 0)):
            context = self.context("NOD", 4, num_divisions=divisions,
                                   variables={"ADISCORD_economy_nod_recruitment_brake": 20})
            self.assertEqual(self.total(context, "ai_wanted_divisions_factor"), expected)
        context["ADISCORD_economy_nod_army_at_capacity"] = True
        context["num_divisions"] = 10
        self.assertEqual(self.total(context, "ai_wanted_divisions_factor"), 0)

    def test_stelander_settlement_keeps_srp_own_war(self):
        context = self.context("SRP", wars={"VAL"}, has_global_flag={"STP_cw_union_wars_finished"})
        self.assertTrue(self.enabled(PREFIX + "stelander_arms", context))
        context.update(has_war=False, wars=set())
        self.assertFalse(self.enabled(PREFIX + "stelander_arms", context))

    def test_nod_maritime_preparation_needs_current_threat_and_port(self):
        context = self.context("NOD", has_war=False, wars=set(), NOD_ai_stelander_preparation=True)
        name = PREFIX + "nod_landing_preparation"
        self.assertTrue(self.enabled(name, context))
        for changes in ({"NOD_ai_stelander_preparation": False}, {"convoys": 19},
                        {"ADISCORD_has_operational_naval_base": False}, {"ADISCORD_has_marine_training": False}):
            self.assertFalse(self.enabled(name, dict(context, **changes)), changes)

    def test_val_air_defence_needs_technology_factories_and_current_campaign(self):
        context = self.context("VAL", wars={"SRP"})
        name = PREFIX + "val_air_defence"
        self.assertTrue(self.enabled(name, context))
        for changes in ({"has_tech": set()}, {"num_of_military_factories": 7},
                        {"ADISCORD_ai_rifle_replacement_emergency": True},
                        {"has_war": False, "wars": set()}, {"wars": {"SHL"}}):
            self.assertFalse(self.enabled(name, dict(context, **changes)), changes)

    def test_rus_armor_and_coalition_logistics_use_separate_actors(self):
        context = self.context("RUS", has_war=False, wars=set(), variables={"RUS_crisis_phase": 1})
        self.assertTrue(self.enabled(PREFIX + "rus_armored_campaign", context))
        context["variables"]["RUS_crisis_phase"] = 3
        self.assertFalse(self.enabled(PREFIX + "rus_armored_campaign", context))
        defender = self.context("VAL", wars={"RUS"}, has_country_flag={"RUS_crisis_defender"})
        self.assertTrue(self.enabled(PREFIX + "rus_coalition_logistics", defender))
        defender.update(has_war=False, wars=set())
        self.assertFalse(self.enabled(PREFIX + "rus_coalition_logistics", defender))

    def test_resource_war_preparation_closes_without_disabling_later_wars(self):
        context = self.context("NAM", has_war=False, wars=set(), ADISCORD_nam_resource_war_preparation=True)
        name = PREFIX + "nam_resource_logistics"
        self.assertTrue(self.enabled(name, context))
        context["ADISCORD_nam_resource_war_preparation"] = False
        self.assertFalse(self.enabled(name, context))
        context.update(has_war=True, wars={"EFL"}, NAM_war_of_return_active=True)
        self.assertTrue(self.enabled(name, context))
        context["wars"] = {"RUS"}
        self.assertFalse(self.enabled(name, context))

    def test_disabled_south_cannot_acquire_war_preparation(self):
        context = self.context("SHL", wars={"NAM"}, ADISCORD_south_crisis_open=True, ADISCORD_south_final_active=True)
        name = PREFIX + "south_campaign_supply"
        self.assertFalse(self.enabled(name, context))
        context.update(ADISCORD_south_final_war_enabled=True)
        self.assertTrue(self.enabled(name, context))

    def test_west_preparation_expires_if_the_other_champion_is_unavailable(self):
        for tag, opponent in (("WRK", "IVN"), ("IVN", "WRK")):
            context = self.context(tag, has_war=False, wars=set(), ADISCORD_west_crisis_open=True,
                                   has_global_flag={"ADISCORD_west_crisis_warned"})
            context["countries"] = {name: self.context(name) for name in ("WRK", "IVN")}
            name = PREFIX + "west_campaign_supply"
            self.assertTrue(self.enabled(name, context), tag)
            for field, value in (("exists", False), ("has_capitulated", True), ("is_subject", True)):
                context["countries"][opponent][field] = value
                self.assertFalse(self.enabled(name, context), (tag, field))
                context["countries"][opponent][field] = not value
            context["countries"]["IVN"]["allies"] = {"WRK"}
            self.assertFalse(self.enabled(name, context), tag)

    def test_west_warning_and_live_war_are_separate_paths(self):
        context = self.context("WRK", has_war=False, wars=set(), ADISCORD_west_crisis_open=True)
        name = PREFIX + "west_campaign_supply"
        self.assertFalse(self.enabled(name, context))
        context.update(has_war=True, wars={"IVN"}, ADISCORD_west_final_active=True,
                       ADISCORD_west_crisis_open=False)
        self.assertTrue(self.enabled(name, context))
        context["wars"] = {"RUS"}
        self.assertFalse(self.enabled(name, context))

    def test_vorkerland_profile_uses_live_preparation_and_closes_at_reunification(self):
        context = self.context("WKR", has_war=False, wars=set(),
                               has_global_flag={"ADISCORD_vorkerland_collapse_wars_started"})
        name = PREFIX + "vorkerland_field_supply"
        self.assertFalse(self.enabled(name, context))
        context["ADISCORD_ai_has_adjacent_war_preparation"] = True
        self.assertTrue(self.enabled(name, context))
        context["has_global_flag"].add("ADISCORD_vorkerland_collapse_finished")
        self.assertFalse(self.enabled(name, context))

    def test_easy_modes_retain_production_and_never_remove_existing_troops(self):
        for difficulty in (0, 1):
            policies = self.strategies(self.context(difficulty=difficulty))
            self.assertEqual({policy["type"] for policy in policies}, {"ai_wanted_divisions_factor"})

    def test_advanced_campaign_profiles_drop_on_budget_and_control_changes(self):
        cases = [
            ("stelander_arms", self.context("STS")),
            ("nod_northern_logistics", self.context("NOD", wars={"YPR"})),
            ("nod_landing_preparation", self.context("NOD", wars={"STS"})),
            ("val_air_defence", self.context("VAL", wars={"SRP"})),
            ("rus_armored_campaign", self.context("RUS")),
            ("rus_coalition_logistics", self.context("VAL", wars={"RUS"}, has_country_flag={"RUS_crisis_defender"})),
            ("vorkerland_field_supply", self.context("VAD", has_global_flag={"ADISCORD_vorkerland_collapse_wars_started"})),
            ("nam_resource_logistics", self.context("AZH", wars={"NAM"}, ADISCORD_nam_resource_war_active=True)),
            ("west_campaign_supply", self.context("IVN", wars={"WRK"}, ADISCORD_west_final_active=True)),
            ("south_campaign_supply", self.context("SHL", wars={"NAM"}, ADISCORD_south_final_active=True,
                                                  ADISCORD_south_final_war_enabled=True)),
        ]
        for suffix, context in cases:
            name = PREFIX + suffix
            self.assertTrue(self.enabled(name, context), name)
            for changes in ({"is_ai": False}, {"ADISCORD_economy_ai_is_healthy": False},
                            {"has_capitulated": True}, {"is_subject": True}, {"difficulty": 2},
                            {"has_global_flag": {"RUS_crisis_world_ended"}}):
                self.assertFalse(self.enabled(name, dict(context, **changes)), (name, changes))

    def test_specializations_do_not_add_factory_floors_or_force_new_wars(self):
        self.assertGreaterEqual(len(self.policies), 12)
        forbidden = {"equipment_production_min_factories", "equipment_production_min_factories_archetype",
                     "force_build_armies", "declare_war", "prepare_for_war", "conquer"}
        for name, policy in self.policies.items():
            self.assertIn(("abort_when_not_enabled", "=", "yes"), policy, name)
            for key, _, body in policy:
                if key == "ai_strategy":
                    fields = {field: value for field, _, value in body}
                    self.assertNotIn(fields["type"], forbidden, name)

    def front_strategies(self, actor, enemy):
        enemy = dict(enemy, scopes={"FROM": actor})
        return [strategy for strategy in self.strategies(actor)
                if "country_trigger" in strategy
                and self.evaluate(strategy["country_trigger"], enemy)]

    def test_abyss_front_adapts_to_strength_and_replenishment(self):
        actor = self.context("SRP", 4, wars={"VAL"})
        for ratio, ready, execution, manual, concentration in (
            (0.79, True, "balanced", "yes", 30),
            (0.8, True, None, None, 0),
            (1.25, True, None, None, 0),
            (1.26, True, "careful", "no", -25),
            (0.79, False, "careful", "no", 0),
        ):
            with self.subTest(ratio=ratio, ready=ready):
                actor["ADISCORD_ai_army_replacement_pressure_cleared"] = ready
                enemy = self.context("VAL", wars={"SRP"}, army_ratios={"SRP": ratio})
                strategies = self.front_strategies(actor, enemy)
                orders = [s for s in strategies if s["type"] == "front_control"]
                self.assertEqual([s["execution_type"] for s in orders], [execution] if execution else [])
                if orders:
                    self.assertEqual(orders[0]["manual_attack"], manual)
                    self.assertEqual(orders[0]["execute_order"], "yes")
                self.assertEqual(sum(float(s["value"]) for s in strategies
                                     if s["type"] == "force_concentration_front_factor"), concentration)

    def test_front_rules_exclude_rift_peace_and_neutral_targets(self):
        actor = self.context("SRP", 4, wars={"VAL"})
        enemy = self.context("VAL", wars={"SRP"}, army_ratios={"SRP": 0.5})
        self.assertTrue(self.front_strategies(actor, enemy))
        for changes in ({"difficulty": 3}, {"has_war": False, "wars": set()}):
            self.assertEqual(self.front_strategies(dict(actor, **changes), enemy), [])
        self.assertEqual(self.front_strategies(actor, dict(enemy, wars=set())), [])
        actor["ADISCORD_economy_ai_is_healthy"] = False
        orders = [s for s in self.front_strategies(actor, enemy) if s["type"] == "front_control"]
        self.assertEqual([s["execution_type"] for s in orders], ["careful"])
        self.assertFalse(any("state_trigger" in s for s in self.strategies(actor)))

    def test_objectives_use_enemy_control_and_respect_fortification(self):
        actor = self.context("STS", 4)
        enemy = self.context("STP", wars={"STS"}, scopes={"FROM.FROM": actor})
        targets = [s for s in self.strategies(actor) if "state_trigger" in s]
        self.assertEqual(len(targets), 2)
        for capital, forts, controller, expected in (
            (True, [0], "STP", 35), (False, [3], "STP", 0),
            (False, [4], "STP", -40), (True, [4], "STP", -5),
            (True, [4], "STS", 0), (True, [4], "VAL", 0),
        ):
            state = self.context(is_capital=capital, forts=forts, controller=controller,
                                 scopes={"FROM": enemy, "FROM.FROM": actor})
            actual = sum(float(s["value"]) for s in targets if self.evaluate(s["state_trigger"], state))
            self.assertEqual(actual, expected, (capital, forts, controller))
        enemy["wars"] = set()
        state["controller"] = "STP"
        self.assertFalse(any(self.evaluate(s["state_trigger"], state) for s in targets))

    def test_all_campaign_orders_outrank_abyss_fallback(self):
        controls = [s for s in self.strategies(self.context(difficulty=4)) if s["type"] == "front_control"]
        self.assertEqual(len(controls), 2)
        fallback_priority = max(int(s["priority"]) for s in controls)
        checked = 0
        for path in (ROOT / "common/ai_strategy").glob("*.txt"):
            if path.name in ("default.txt", "ADISCORD_difficulty_ai.txt"):
                continue
            for block in named_blocks(path.read_text(encoding="utf-8-sig"), "ai_strategy"):
                if not re.search(r"type\s*=\s*front_control\b", block):
                    continue
                priority = re.search(r"priority\s*=\s*(\d+)", block)
                self.assertIsNotNone(priority, str(path))
                self.assertGreater(int(priority.group(1)), fallback_priority, str(path))
                checked += 1
        self.assertGreater(checked, 30)
        for strategy in controls:
            self.assertEqual(strategy["ordertype"], "front")
        for strategy in self.strategies(self.context(difficulty=4)):
            self.assertNotIn(strategy["type"], {"force_concentration_factor", "put_unit_buffers",
                                               "front_unit_request", "invasion_unit_request"})

    def campaign_orders(self, names, actor, enemy, state=None):
        enemy = dict(enemy, scopes={"FROM": actor, "FROM.FROM": actor})
        if state is not None:
            state = dict(state, scopes={"FROM": enemy, "FROM.FROM": actor})
        orders = []
        for name in names:
            profile = self.campaigns[name]
            if not self.evaluate(child(profile, "allowed"), actor):
                continue
            if not self.evaluate(child(profile, "enable"), actor):
                continue
            for key, _, body in profile:
                if key != "ai_strategy":
                    continue
                fields = {key: value for key, _, value in body}
                if "tag" in fields and fields["tag"] != enemy["tag"]:
                    continue
                if "country_trigger" in fields and not self.evaluate(fields["country_trigger"], enemy):
                    continue
                if "state_trigger" in fields:
                    if state is None or not self.evaluate(fields["state_trigger"], state):
                        continue
                orders.append(fields)
        return sorted(orders, key=lambda order: int(order["priority"]))

    def test_scenario_variants_stay_inside_parent_and_preserve_target(self):
        adapted = 0
        protected = {
            "STP_cw_hold_fada_front", "STS_shabrat_cautious_party_front",
            "STS_shabrat_cautious_nod_front", "STP_ps_cautious_counterattack",
            "STP_ps_local_counterattacks", "ADISCORD_west_wrk_hold_ivn",
        }
        for name, profile in self.campaigns.items():
            controls = [dict((key, value) for key, _, value in body)
                        for key, _, body in profile if key == "ai_strategy"]
            base = controls[0]
            if base["execute_order"] == "no" or name in protected:
                self.assertEqual(len(controls), 2 if name == "ADISCORD_west_wrk_hold_ivn" else 1, name)
                continue
            adapted += 1
            self.assertEqual(len(controls), 2 if base["execution_type"] == "careful" else 3, name)
            target_key = "state_trigger" if "state_trigger" in base else "country_trigger"
            original_target = base.get(target_key, [("tag", "=", base.get("tag"))])
            for variant in controls[1:]:
                target = variant[target_key]
                self.assertEqual(target[:-1], original_target, name)
                self.assertRegex(target[-1][0], r"^ADISCORD_difficulty_(enemy|state)_(allows_push|requires_caution)$")
                self.assertEqual(target[-1][1:], ("=", "yes"))
                offset = 2 if name.startswith("ADISCORD_vorkerland_auxiliary_of_") else 1
                self.assertEqual(int(variant["priority"]), int(base["priority"]) + offset, name)
                self.assertEqual(variant["ratio"], base["ratio"], name)
                self.assertEqual(variant["ordertype"], base["ordertype"], name)
                self.assertEqual(variant["execute_order"], base["execute_order"], name)
        self.assertGreaterEqual(adapted, 161)

    def test_nam_scenario_changes_tactics_only_on_abyss(self):
        name = "ADISCORD_nam_resource_war_eflor_offensive"
        for difficulty, ratio, ready, expected in (
            (3, 0.5, True, "rush"), (3, 2, False, "rush"),
            (4, 0.5, True, "rush_weak"), (4, 2, True, "careful"),
            (4, 0.5, False, "careful"), (4, 1, True, "rush"),
        ):
            actor = self.context("EFL", difficulty, wars={"NAM"}, ADISCORD_nam_resource_war_active=True,
                                 ADISCORD_ai_army_replacement_pressure_cleared=ready)
            enemy = self.context("NAM", wars={"EFL"}, army_ratios={"EFL": ratio})
            self.assertEqual(self.campaign_orders([name], actor, enemy)[-1]["execution_type"], expected)
        actor["ADISCORD_nam_resource_war_active"] = False
        self.assertEqual(self.campaign_orders([name], actor, enemy), [])

    def test_nod_simultaneous_fronts_adapt_against_their_own_opponents(self):
        names = ["NOD_cw_northern_front_ypr", "NOD_cw_stelander_intervention_army"]
        actor = self.context("NOD", 4, wars={"YPR", "STS"})
        north = self.context("YPR", wars={"NOD"}, army_ratios={"NOD": 2})
        south = self.context("STS", wars={"NOD"}, army_ratios={"NOD": 0.5})
        self.assertEqual(self.campaign_orders(names, actor, north)[-1]["execution_type"], "careful")
        self.assertEqual(self.campaign_orders(names, actor, south)[-1]["execution_type"], "rush_weak")
        actor["wars"].remove("YPR")
        self.assertEqual(self.campaign_orders(names, actor, north), [])
        self.assertEqual(self.campaign_orders(names, actor, south)[-1]["priority"], "1801")

    def test_congress_target_and_recovery_phase_remain_authoritative(self):
        names = ["STS_shabrat_take_congress", "STS_shabrat_recover_party_front"]
        enemy = self.context("STP", wars={"STS"}, controls_province={145}, army_ratios={"STS": 0.5})
        actor = self.context("STS", 4, countries={"STP": enemy}, STP_cw_fada_battle_active=True)
        state = self.context(state=28)
        self.assertEqual(self.campaign_orders(names, actor, enemy, state)[-1]["priority"], "1651")
        self.assertEqual(self.campaign_orders(names, actor, enemy, dict(state, state=29)), [])
        actor["ADISCORD_ai_army_replacement_pressure_cleared"] = False
        self.assertEqual(self.campaign_orders(names, actor, enemy, state)[-1]["execution_type"], "careful")
        actor["has_country_flag"].add("STS_ai_regroup")
        order = self.campaign_orders(names, actor, enemy, state)[-1]
        self.assertEqual((order["priority"], order["execute_order"]), ("1700", "no"))
        actor["has_country_flag"].clear()
        actor["STP_cw_fada_battle_active"] = False
        self.assertEqual(self.campaign_orders(names, actor, enemy, state), [])

    def test_party_defence_does_not_unlock_attacks_before_its_phase(self):
        names = ["STP_ps_defensive_front", "STP_ps_local_counterattacks"]
        actor = self.context("STP", 4, wars={"STS"}, STP_ps_war_active=True,
                             STP_ps_can_local_counterattack=False, STP_ps_can_counterattack=False)
        enemy = self.context("STS", wars={"STP"}, army_ratios={"STP": 0.1})
        self.assertEqual(self.campaign_orders(names, actor, enemy)[-1]["execute_order"], "no")
        actor["STP_ps_can_local_counterattack"] = True
        order = self.campaign_orders(names, actor, enemy)[-1]
        self.assertEqual((order["execution_type"], order["execute_order"], order["manual_attack"]),
                         ("careful", "yes", "no"))

    def test_west_coalition_adapts_to_actual_front_enemy(self):
        name = "ADISCORD_west_wrk_front_ivn"
        actor = self.context("WRK", 4, wars={"IVN", "VAD"}, army_ratios={"IVN": 1},
                             ADISCORD_west_final_active=True)
        enemy = self.context("VAD", wars={"WRK"}, army_ratios={"WRK": 2}, ADISCORD_west_on_ivn_side=True)
        self.assertEqual(self.campaign_orders([name], actor, enemy)[-1]["execution_type"], "careful")
        enemy["army_ratios"]["WRK"] = 0.5
        self.assertEqual(self.campaign_orders([name], actor, enemy)[-1]["execution_type"], "rush_weak")
        enemy["ADISCORD_west_on_ivn_side"] = False
        self.assertEqual(self.campaign_orders([name], actor, enemy), [])

    def test_vorkerland_breakthrough_remains_inside_timed_window(self):
        name = "ADISCORD_vorkerland_central_breakthrough_eyr"
        enemy = self.context("EYR", wars={"WKR"}, army_ratios={"WKR": 0.5})
        actor = self.context("WKR", 4, wars={"EYR"}, countries={"EYR": enemy}, army_ratios={"EYR": 2},
                             has_country_flag={"ADISCORD_vorkerland_central_breakthrough_window_active"})
        self.assertEqual(self.campaign_orders([name], actor, enemy)[-1]["priority"], "2001")
        actor["has_country_flag"].clear()
        self.assertEqual(self.campaign_orders([name], actor, enemy), [])

    def test_auxiliary_push_wins_over_simultaneous_minor_defence(self):
        for leader in ("WKR", "VAD", "TVA"):
            for opponent in {"WKR", "VAD", "TVA"} - {leader}:
                names = [f"ADISCORD_vorkerland_central_minor_defense_against_{opponent.lower()}",
                         f"ADISCORD_vorkerland_auxiliary_of_{leader.lower()}_against_{opponent.lower()}"]
                actor = self.context("EYR", 4, wars={opponent}, allies={leader},
                                     has_global_flag={"ADISCORD_vorkerland_collapse_wars_started"},
                                     has_country_flag={"ADISCORD_vorkerland_regional_auxiliary"},
                                     ADISCORD_vorkerland_is_local_bracket_member=True,
                                     countries={opponent: self.context(opponent)})
                for ratio, expected in ((0.5, "rush_weak"), (2, "careful")):
                    enemy = self.context(opponent, wars={"EYR"}, army_ratios={"EYR": ratio})
                    orders = self.campaign_orders(names, actor, enemy)
                    self.assertEqual(orders[-1]["execution_type"], expected)
                    self.assertEqual(orders[-1]["priority"], "1252")
                    self.assertGreater(int(orders[-1]["priority"]), int(orders[-2]["priority"]))

    def test_west_hold_wins_over_overlapping_expedition(self):
        names = ["ADISCORD_west_wrk_front_ivn", "ADISCORD_west_wrk_hold_ivn",
                 "ADISCORD_wrk_postwar_expedition_front"]
        actor = self.context("WRK", 4, wars={"IVN", "PIV"}, army_ratios={"IVN": 0.4},
                             ADISCORD_west_final_active=True,
                             has_country_flag={"ADISCORD_vorkerland_pw_campaign_active"})
        enemy = self.context("PIV", wars={"WRK"}, army_ratios={"WRK": 0.5},
                             ADISCORD_west_on_ivn_side=True,
                             has_country_flag={"ADISCORD_vorkerland_pw_campaign_member"})
        orders = self.campaign_orders(names, actor, enemy)
        self.assertEqual((orders[-1]["priority"], orders[-1]["execution_type"], orders[-1]["manual_attack"]),
                         ("1502", "careful", "no"))
        actor["army_ratios"]["IVN"] = 1
        self.assertEqual(self.campaign_orders(names, actor, enemy)[-1]["execution_type"], "rush_weak")

    def test_variants_cannot_jump_the_next_scenario_priority_tier(self):
        base_priorities = {int(next(dict((k, v) for k, _, v in body)["priority"]
                                    for key, _, body in profile if key == "ai_strategy"))
                           for profile in self.campaigns.values()}
        for name, profile in self.campaigns.items():
            controls = [dict((k, v) for k, _, v in body)
                        for key, _, body in profile if key == "ai_strategy"]
            base = int(controls[0]["priority"])
            higher = [priority for priority in base_priorities if priority > base]
            for variant in controls[1:]:
                self.assertGreater(int(variant["priority"]), base, name)
                if higher:
                    self.assertLess(int(variant["priority"]), min(higher), name)

    def test_every_adapted_profile_selects_one_variant_when_its_target_matches(self):
        # Parent gates and target prefixes are checked separately. This exercises
        # each attached predicate, including the extra scope of state targets.
        checked = 0
        for name, profile in self.campaigns.items():
            controls = [dict((k, v) for k, _, v in body)
                        for key, _, body in profile if key == "ai_strategy"]
            if len(controls) < 2 or name == "ADISCORD_west_wrk_hold_ivn":
                continue
            checked += 1
            base = controls[0]
            for difficulty, ratio, ready in ((3, 0.5, True), (3, 2, False),
                                             (4, 0.5, True), (4, 0.8, True),
                                             (4, 1.25, True), (4, 2, True), (4, 0.5, False)):
                actor = self.context("STS", difficulty, ADISCORD_ai_army_replacement_pressure_cleared=ready)
                enemy = self.context("STP", wars={"STS"}, army_ratios={"STS": ratio},
                                     scopes={"FROM": actor, "FROM.FROM": actor})
                state = self.context(scopes={"FROM": enemy, "FROM.FROM": actor})
                matching = []
                for variant in controls[1:]:
                    target = variant.get("state_trigger", variant.get("country_trigger"))
                    scope = state if "state_trigger" in variant else enemy
                    if self.evaluate(target[-1:], scope):
                        matching.append(variant)
                with self.subTest(profile=name, difficulty=difficulty, ratio=ratio, ready=ready):
                    self.assertLessEqual(len(matching), 1)
                    winner = max([base, *matching], key=lambda control: int(control["priority"]))
                    if difficulty < 4 or (ready and 0.8 <= ratio <= 1.25):
                        self.assertIs(winner, base)
                    elif not ready or ratio > 1.25:
                        self.assertEqual((winner["execution_type"], winner["manual_attack"]), ("careful", "no"))
                    else:
                        expected = "careful" if base["execution_type"] == "careful" else "rush_weak"
                        self.assertEqual((winner["execution_type"], winner["manual_attack"]), (expected, "yes"))
        self.assertEqual(checked, 161)


if __name__ == "__main__":
    unittest.main()
