"""Static front-allocation contracts; native AI movement needs an in-game check."""

from __future__ import annotations
from tools.lib.on_actions import country_on_actions_entries

import re
import unittest
from pathlib import Path

from tools.tests.test_adiscord_generic_wartime_fronts import named_block, named_blocks


ROOT = Path(__file__).resolve().parents[2]
AI_PATH = ROOT / "common/ai_strategy/ADISCORD_STP_civil_war.txt"
NEUTRAL = "STS_cw_deprioritize_neutral_borders"
RESERVE = "STS_cw_defend_abilia"


def compact(source: str) -> str:
    return " ".join(re.sub(r"(?m)#.*$", "", source).split())


class ShabratFrontTests(unittest.TestCase):
    def setUp(self) -> None:
        self.source = re.sub(r"(?m)#.*$", "", AI_PATH.read_text(encoding="utf-8"))

    def profile(self, name: str) -> str:
        result = named_block(self.source, name)
        self.assertTrue(result, f"missing AI profile: {name}")
        return result

    def test_neutral_demand_has_one_shared_owner(self) -> None:
        self.assertFalse(named_block(self.source, NEUTRAL))
        shared = (ROOT / "common/ai_strategy/default.txt").read_text(encoding="utf-8")
        profile = named_block(shared, "ADISCORD_wartime_neutral_borders")
        self.assertTrue(profile)
        self.assertIn("ADISCORD_ai_front_has_prewar_threat = no", profile)
        self.assertNotIn("original_tag", profile)
        self.assertNotIn("enemies^num", profile)

    def test_reserve_requires_a_live_civil_war_and_control_of_abilia(self) -> None:
        profile = self.profile(RESERVE)
        self.assertEqual(
            compact(named_block(profile, "allowed")), "allowed = { original_tag = STS }"
        )
        enable = named_block(profile, "enable")
        nod = named_block(enable, "NOD")
        self.assertTrue(nod, "reserve must track the external threat")
        self.assertEqual(
            compact(enable.replace(nod, "")),
            "enable = { is_ai = yes has_capitulated = no "
            "has_global_flag = STP_cw_started "
            "NOT = { has_global_flag = STP_cw_union_wars_finished } "
            "has_war_with = STP controls_state = 1 }",
        )

    def test_reserve_requires_approved_eligible_intervention_and_peace_with_nod(
        self,
    ) -> None:
        enable = named_block(self.profile(RESERVE), "enable")
        self.assertEqual(
            compact(named_block(enable, "NOD")),
            "NOD = { NOD_cw_intervention_possible = yes "
            "has_country_flag = NOD_cw_intervention_approved "
            "NOT = { has_war_with = STS } }",
        )

    def test_reserve_is_five_percent_in_abilia(self) -> None:
        strategies = named_blocks(self.profile(RESERVE), "ai_strategy")
        self.assertEqual(len(strategies), 1)
        self.assertEqual(
            compact(strategies[0]),
            "ai_strategy = { type = put_unit_buffers ratio = 0.05 "
            "states = { 1 } subtract_invasions_from_need = yes "
            "subtract_fronts_from_need = no }",
        )

    def test_shabrat_profiles_cannot_stack_additional_buffers(self) -> None:
        buffers = []
        for name in re.findall(r"(?m)^(\w+)\s*=\s*\{", self.source):
            profile = self.profile(name)
            allowed = named_block(profile, "allowed")
            if not re.search(r"\boriginal_tag\s*=\s*STS\b", allowed):
                continue
            buffers.extend(
                name
                for strategy in named_blocks(profile, "ai_strategy")
                if re.search(r"\btype\s*=\s*put_unit_buffers\b", strategy)
            )
        self.assertEqual(buffers, [RESERVE])

    def test_temporary_profiles_abort_after_peace_or_threat_cancellation(self) -> None:
        for name in (RESERVE, "STS_prepare_against_NOD"):
            with self.subTest(profile=name):
                self.assertIn("abort_when_not_enabled = yes", self.profile(name))

    def test_actual_external_fronts_do_not_depend_on_the_party_war(self) -> None:
        for name, enemy, enable in (
            ("STP_cw_front_against_nod", "NOD", "enable = { has_war_with = NOD }"),
            (
                "STS_shabrat_val_front",
                "VAL",
                "enable = { is_ai = yes has_war_with = VAL }",
            ),
        ):
            with self.subTest(enemy=enemy):
                profile = self.profile(name)
                self.assertEqual(compact(named_block(profile, "enable")), enable)
                self.assertIn("abort_when_not_enabled = yes", profile)
                self.assertRegex(
                    profile,
                    rf"type = front_unit_request tag = {enemy} value = [1-9]\d*",
                )
                self.assertIn(f"type = front_control tag = {enemy}", profile)

    def test_shabrat_commits_decisively_against_live_nod_front(self) -> None:
        profile = self.profile("STS_shabrat_nod_front")
        self.assertEqual(
            compact(named_block(profile, "allowed")), "allowed = { original_tag = STS }"
        )
        self.assertEqual(
            compact(named_block(profile, "enable")),
            "enable = { is_ai = yes has_capitulated = no has_war_with = NOD }",
        )
        self.assertIn("abort_when_not_enabled = yes", profile)
        self.assertIn("type = consider_weak id = NOD value = 120", profile)
        self.assertIn("type = front_unit_request tag = NOD value = 220", profile)
        self.assertIn("priority = 1800", profile)
        self.assertIn("execution_type = rush_weak", profile)
        self.assertIn("type = conquer id = NOD value = 250", profile)
        self.assertIn("type = force_concentration_factor value = 80", profile)

    def test_party_front_requests_are_not_inflated_to_mask_neutral_demand(self) -> None:
        for name, demand in (
            ("STS_cw_front_against_stp", 100),
            ("STS_shabrat_civil_war_army", 120),
        ):
            with self.subTest(profile=name):
                profile = self.profile(name)
                self.assertIn(
                    f"type = front_unit_request tag = STP value = {demand}", profile
                )
                self.assertIn("execution_type = rush_weak", profile)

    def test_gameplay_source_is_utf8_without_bom_and_has_unique_profiles(self) -> None:
        self.assertFalse(AI_PATH.read_bytes().startswith(b"\xef\xbb\xbf"))
        names = re.findall(r"(?m)^(\w+)\s*=\s*\{", self.source)
        self.assertEqual(len(names), len(set(names)))
        for name in names:
            self.profile(name)


class CivilWarVictorFallbackTests(unittest.TestCase):
    def setUp(self):
        from tools.tests.test_adiscord_stp_preparation import entries, block, walk

        hooks = block(
            country_on_actions_entries(
                "common/on_actions/02_ADISCORD_STP_on_actions.txt", 'stelander'
            ),
            "on_actions",
        )
        immediate = block(block(hooks, "on_capitulation_immediate"), "effect")
        self.block = block
        candidates = [
            e.value
            for e in walk(immediate)
            if e.key == "if"
            and any(x.key == "else_if" for x in e.value)
            and "STP_cw_capitulation_occupier" in str(block(e.value, "limit"))
        ]
        self.assertEqual(len(candidates), 1)
        self.fallback = candidates[0]

    def outcome(self, loser, victor, enemies, flags=(), snapshot=0, exists=True):
        from tools.tests.test_adiscord_stp_preparation import scalar

        def matches(items, scope):
            def one(e):
                if e.key == "OR":
                    return any(one(x) for x in e.value)
                if e.key == "AND":
                    return matches(e.value, scope)
                if e.key == "NOT":
                    return not matches(e.value, scope)
                if e.key in ("ROOT", "FROM"):
                    return matches(e.value, loser if e.key == "ROOT" else victor)
                if e.key == "any_enemy_country":
                    return any(matches(e.value, enemy) for enemy in enemies)
                if e.key == "tag":
                    return scope == e.value
                if e.key == "exists":
                    return exists
                if e.key == "has_capitulated":
                    return e.value == "no"
                if e.key == "has_war_with":
                    return victor in enemies
                if e.key == "has_country_flag":
                    return (scope, e.value) in flags
                if e.key == "check_variable":
                    self.assertEqual(
                        scalar(e.value, "var"), "STP_cw_capitulation_occupier"
                    )
                    return snapshot == float(scalar(e.value, "value"))
                raise AssertionError(f"Unsupported test predicate: {e.key}")

            return all(one(e) for e in items)

        if not matches(self.block(self.fallback, "limit"), loser):
            return snapshot
        for branch in self.fallback:
            if branch.key in ("if", "else_if") and matches(
                self.block(branch.value, "limit"), loser
            ):
                return int(
                    scalar(
                        self.block(self.block(branch.value, "ROOT"), "set_variable"),
                        "value",
                    )
                )
        return snapshot

    def test_isolated_fronts_settle_without_original_capital_capture(self):
        cases = (
            ("STS", "STP", 1),
            ("STP", "STS", 2),
            ("SRP", "VAL", 5),
            ("VAL", "SRP", 3),
        )
        for loser, victor, code in cases:
            with self.subTest(loser=loser):
                self.assertEqual(
                    self.outcome(
                        loser, victor, [victor], flags={("VAL", "VAL_cw_entered")}
                    ),
                    code,
                )

    def test_nod_participation_is_required_and_has_distinct_credit(self):
        flags = {("NOD", "NOD_cw_entered")}
        self.assertEqual(self.outcome("STS", "STP", ["STP", "NOD"], flags), 1)
        self.assertEqual(self.outcome("STS", "NOD", ["STP", "NOD"], flags), 4)
        self.assertEqual(self.outcome("STS", "NOD", ["STP", "NOD"]), 0)

    def test_conflicting_war_or_snapshot_never_gets_overwritten(self):
        self.assertEqual(self.outcome("STS", "STP", ["STP", "VAL"]), 0)
        self.assertEqual(
            self.outcome("SRP", "VAL", ["VAL", "STS"], {("VAL", "VAL_cw_entered")}), 0
        )
        self.assertEqual(self.outcome("STS", "STP", ["STP"], snapshot=5), 5)
        self.assertEqual(self.outcome("STS", "STP", [], exists=True), 0)
        self.assertEqual(self.outcome("STS", "STP", ["STP"], exists=False), 0)


if __name__ == "__main__":
    unittest.main()


class ShabratCongressPriorityTests(unittest.TestCase):
    def test_capital_priority_tracks_the_actual_congress_and_only_live_ai_war(self):
        from tools.tests.test_adiscord_stp_preparation import (
            entries,
            block,
            matches_conditions,
            scalar,
        )

        profile = block(
            entries("common/ai_strategy/ADISCORD_STP_civil_war.txt"),
            "STS_shabrat_take_congress",
        )
        self.assertEqual(scalar(profile, "abort_when_not_enabled"), "yes")
        self.assertEqual(scalar(block(profile, "allowed"), "original_tag"), "STS")
        guard = block(profile, "enable")
        facts = {
            ("STS", "is_ai", "yes"): True,
            ("STS", "has_capitulated", "no"): True,
            ("STS", "STP_cw_fada_battle_active", "yes"): True,
            ("STP", "controls_province", "145"): True,
        }
        self.assertTrue(matches_conditions(guard, facts, "STS"))
        for key in facts:
            self.assertFalse(
                matches_conditions(guard, {**facts, key: False}, "STS"), key
            )
        self.assertNotIn("has_completed_focus", str(guard))
        self.assertNotIn("controls_state", str(guard))

    def test_congress_push_uses_local_native_targets_and_yields_to_recovery(self):
        from tools.tests.test_adiscord_stp_preparation import (
            entries,
            block,
            scalar,
            matches_conditions,
        )

        profiles = entries("common/ai_strategy/ADISCORD_STP_civil_war.txt")
        profile = block(profiles, "STS_shabrat_take_congress")
        strategies = {
            scalar(e.value, "type"): e.value for e in profile if e.key == "ai_strategy"
        }
        self.assertEqual(
            set(strategies),
            {
                "front_unit_request",
                "front_control",
                "force_concentration_front_factor",
                "force_concentration_target_weight",
            },
        )
        for strategy in strategies.values():
            target = block(strategy, "state_trigger")
            self.assertEqual(scalar(target, "state"), "28")
            self.assertFalse(matches_conditions(target, {}, "29"))
            self.assertEqual(scalar(block(target, "FROM"), "tag"), "STP")
        control = strategies["front_control"]
        self.assertEqual(scalar(control, "execute_order"), "yes")
        self.assertEqual(scalar(control, "manual_attack"), "yes")
        self.assertEqual(scalar(control, "execution_type"), "rush_weak")
        recovery = block(profiles, "STS_shabrat_recover_party_front")
        recovery_control = next(
            e.value
            for e in recovery
            if e.key == "ai_strategy" and scalar(e.value, "type") == "front_control"
        )
        self.assertLess(
            int(scalar(control, "priority")), int(scalar(recovery_control, "priority"))
        )
        self.assertGreater(
            int(scalar(strategies["force_concentration_target_weight"], "value")), 100
        )


class ShabratAssaultWaveAndAirTests(unittest.TestCase):
    """Shabrat attacks in waves, rests when outmatched and opens with CAS."""

    EFFECTS = ROOT / "common/scripted_effects/ADISCORD_STP_scripted_effects.txt"
    ON_ACTIONS = ROOT / "common/on_actions/02_ADISCORD_STP_on_actions.txt"

    def text(self, path: Path) -> str:
        return re.sub(r"(?m)#.*$", "", path.read_text(encoding="utf-8-sig"))

    def test_shortages_allow_careful_attacks_and_only_temporary_recovery_stops_them(self):
        from tools.tests.test_adiscord_stp_preparation import block, entries, scalar

        profiles = entries("common/ai_strategy/ADISCORD_STP_civil_war.txt")

        def enabled(conditions, reserve, strength, regroup, disorganized):
            def matches(condition):
                key, value = condition.key, condition.value
                if key == "OR":
                    return any(matches(child) for child in value)
                if key in ("stockpile_ratio", "fighting_army_strength_ratio"):
                    comparison = [child.value for child in value if not child.key]
                    self.assertEqual(comparison[1], "<")
                    actual = reserve if key == "stockpile_ratio" else strength
                    return actual < float(comparison[2])
                facts = {
                    ("is_ai", "yes"): True,
                    ("has_war_with", "STP"): True,
                    ("has_global_flag", "STP_cw_started"): True,
                    ("has_country_flag", "STS_ai_regroup"): regroup,
                    ("has_idea", "STP_cw_operation_disorganization"): disorganized,
                }
                return facts[(key, value)]

            return all(matches(condition) for condition in conditions)

        names = {
            "STS_cw_front_against_stp",
            "STS_shabrat_civil_war_army",
            "STS_shabrat_cautious_party_front",
            "STS_shabrat_recover_party_front",
        }
        for reserve, strength, regroup, disorganized, mode, execute in (
            (0.0, 1.0, False, False, "careful", "yes"),
            (0.1, 0.7, False, False, "careful", "yes"),
            (0.0, 0.7, True, False, "careful", "no"),
            (0.0, 0.7, False, True, "careful", "no"),
            (0.0, 0.7, False, False, "careful", "yes"),
            (0.05, 0.8, False, False, "rush_weak", "yes"),
        ):
            with self.subTest(reserve=reserve, strength=strength, regroup=regroup,
                              disorganized=disorganized):
                controls = [
                    strategy.value
                    for profile in profiles if profile.key in names
                    if enabled(block(profile.value, "enable"), reserve, strength,
                               regroup, disorganized)
                    for strategy in profile.value
                    if strategy.key == "ai_strategy"
                    and scalar(strategy.value, "type") == "front_control"
                ]
                control = max(controls, key=lambda c: int(scalar(c, "priority")))
                self.assertEqual(scalar(control, "execution_type"), mode)
                self.assertEqual(scalar(control, "execute_order"), execute)

    def test_waves_alternate_with_regroups_unless_ground_was_taken(self) -> None:
        tick = compact(named_block(self.text(self.EFFECTS), "STP_cw_ai_shabrat_offensive_tick"))
        self.assertIn("set_country_flag = { flag = STS_ai_assault_wave value = 1 days = 42 }", tick)
        self.assertIn("set_country_flag = { flag = STS_ai_regroup value = 1 days = 21 }", tick)
        # The regroup branch requires that the party kept at least as many states.
        regroup = tick[tick.index("has_variable = STS_ai_wave_start_states"):tick.index("STS_ai_regroup value")]
        self.assertIn("compare = greater_than_or_equals", regroup)
        self.assertIn("NOT = { fighting_army_strength_ratio = { tag = STP ratio > 1.5 } }", regroup)
        self.assertIn("every_controlled_state", tick)
        self.assertNotIn("every_state", tick.replace("every_controlled_state", ""))

    def test_wave_tick_runs_weekly_only_for_the_ai_resistance_at_war(self) -> None:
        weekly = compact(named_block(self.text(self.ON_ACTIONS), "on_weekly_STS"))
        call = weekly.index("STP_cw_ai_shabrat_offensive_tick = yes")
        guard = weekly[weekly.rindex("limit", 0, call):call]
        for condition in ("tag = STS", "is_ai = yes", "has_capitulated = no", "has_war_with = STP"):
            self.assertIn(condition, guard)
        self.assertIn("STP_cw_ai_shabrat_clear_offensive = yes", weekly)

    def test_party_starts_with_ground_attack_wings_inside_base_capacity(self) -> None:
        oob = (ROOT / "history/units/STP.txt").read_text(encoding="utf-8")
        wings = named_block(oob, "air_wings")
        bases = {"28": 2, "1": 1}
        for state, level in bases.items():
            body = named_block(wings, state)
            amounts = [int(value) for value in re.findall(r"amount = (\d+)", body)]
            # Air base capacity is 200 aircraft per level in this mod.
            self.assertLessEqual(sum(amounts), level * 200, state)
            self.assertIn("ADISCORD_cas_airframe_2170", body, state)

    def test_ai_resistance_gets_cas_only_against_a_player_party(self) -> None:
        arm = compact(named_block(self.text(self.EFFECTS), "STP_cw_sts_ai_air_arm"))
        self.assertIn("limit = { is_ai = yes STP = { is_ai = no } }", arm)
        self.assertIn("type = ADISCORD_cas_airframe_2170", arm)
        bootstrap = compact(self.text(self.ON_ACTIONS))
        self.assertLess(
            bootstrap.index("inherit_technology = STP"),
            bootstrap.index("STP_cw_sts_ai_air_arm = yes"),
        )

    def test_shabrat_air_focuses_grant_cas_and_the_plan_takes_them(self) -> None:
        source = (ROOT / "focus_trees/STP/civil_war/focuses.txt").read_text(encoding="utf-8-sig")
        plan = (ROOT / "common/ai_strategy_plans/ADISCORD_STP_plans.txt").read_text(encoding="utf-8")
        war_plan = named_block(plan, "STS_shabrat_civil_war_plan")
        for focus in ("STP_cw_strike_squadrons", "STP_cw_forward_airstrips", "STP_cw_assault_air_cover"):
            body = source[source.index(f"id = {focus}\n"):]
            body = body[:body.index("\n\t}\n")]
            self.assertIn("tag = STS", body, focus)
            self.assertIn("type = ADISCORD_cas_airframe_2170", body, focus)
            self.assertIn(focus, war_plan)
        # The air branch follows the Last Banquet so the decisive window keeps its clock.
        self.assertLess(war_plan.index("STP_cw_last_banquet"), war_plan.index("STP_cw_strike_squadrons"))

    def test_worn_units_do_not_join_planned_attacks(self) -> None:
        defines = (ROOT / "common/defines/ADISCORD_defines_changes.lua").read_text(encoding="utf-8")
        for level, floor in (("LOW", 0.85), ("MED", 0.65), ("HIGH", 0.5)):
            for kind in ("ORG", "STRENGTH"):
                value = re.search(rf"PLAN_ATTACK_MIN_{kind}_FACTOR_{level} = ([\d.]+)", defines)
                self.assertIsNotNone(value, (kind, level))
                self.assertGreaterEqual(float(value.group(1)), floor)
