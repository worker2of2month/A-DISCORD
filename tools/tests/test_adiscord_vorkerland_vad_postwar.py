from __future__ import annotations

import re
import unittest
from collections import Counter
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from tools.lib.focus_sources import read_focus_source
from tools.validators.validate_adiscord_division_templates import parse_clausewitz
from tools.validators.validate_adiscord_vorkerland_civil_war_focus import (
    POSTWAR_EXPANSION_CHOICES,
    POSTWAR_EXPANSION_IDS,
    POSTWAR_EXPANSION_ROUTES,
    focus_blocks,
    resolved_positions,
)
from tools.tests.test_adiscord_stp_preparation import block, scalar, matches_conditions


from tools.lib.paths import source_section


ROOT = Path(__file__).resolve().parents[2]


def read(relative: str) -> str:
    return read_focus_source(ROOT / relative, encoding="utf-8-sig")


def named_block(source: str, name: str) -> str:
    match = re.search(rf"(?m)^\s*{re.escape(name)}\s*=\s*\{{", source)
    if not match:
        return ""
    start = source.find("{", match.start())
    depth = 0
    for index in range(start, len(source)):
        character = source[index]
        if character == "{":
            depth += 1
        elif character == "}":
            depth -= 1
            if depth == 0:
                return source[match.start() : index + 1]
    return ""


class VadPostwarContractTests(unittest.TestCase):
    def test_restored_and_voluntary_sol_remain_subjects_after_handoff(
        self,
    ) -> None:
        source = source_section(
            read("common/scripted_effects/ADISCORD_vorkerland_effects.txt"),
            'phase_effects',
        )
        formation = named_block(source, "ADISCORD_vorkerland_form_wrk_from_vad")
        self.assertTrue(formation)

        restored = re.search(
            r"(?s)if\s*=\s*\{\s*limit\s*=\s*\{[^{}]*"
            r"has_global_flag\s*=\s*ADISCORD_vorkerland_sol_restoration_verified"
            r".*?\n\s*\}\s*\n\s*else_if\s*=",
            formation,
        )
        self.assertIsNotNone(restored)
        restored_block = restored.group(0)
        self.assertIn("puppet = SOL", restored_block)
        self.assertIn("autonomy_state = autonomy_puppet", restored_block)
        self.assertIn("add_to_faction = SOL", restored_block)

        voluntary = formation[restored.end() - len("else_if =") :]
        self.assertIn(
            "has_global_flag = ADISCORD_vorkerland_vad_sol_alliance_accepted", voluntary
        )
        self.assertIn("add_to_faction = SOL", voluntary)
        self.assertIn("puppet = SOL", voluntary)
        self.assertIn("autonomy_state = autonomy_puppet", voluntary)
        detach = formation.index("autonomy_state = autonomy_free")
        annex = formation.index("annex_country = { target = VAD")
        rebind = formation.index("puppet = SOL")
        self.assertLess(detach, annex)
        self.assertLess(annex, rebind)

    def test_destroyed_sol_returns_as_administration_with_velin_and_overlord_colour(self) -> None:
        effects = read("common/scripted_effects/ADISCORD_vorkerland_effects.txt")
        restoration = named_block(effects, "ADISCORD_vorkerland_restore_sol_as_vad_puppet")
        self.assertIn("104 = { add_core_of = SOL }", restoration)
        self.assertIn("transfer_state = 104", restoration)
        self.assertIn("set_cosmetic_tag = SOL_vorkerland_restoration_administration", restoration)
        self.assertIn("autonomy_state = autonomy_puppet", restoration)
        self.assertIn("use_overlord_color = yes", read("common/autonomous_states/puppet.txt"))
        verification = named_block(effects, "ADISCORD_vorkerland_verify_sol_restoration")
        self.assertIn("owns_state = 104 controls_state = 104", verification)
        self.assertIn("ADISCORD_vorkerland_sync_independence_cosmetic = yes", verification)
        cosmetics = named_block(effects, "ADISCORD_vorkerland_sync_independence_cosmetic")
        self.assertIn("is_subject_of = VAD", cosmetics)
        self.assertIn("WRK = { has_country_flag = ADISCORD_vorkerland_route_joint }", cosmetics)
        self.assertIn("has_country_flag = ADISCORD_vorkerland_restored_by_vad", cosmetics)
        self.assertLess(
            cosmetics.index("set_cosmetic_tag = SOL_vorkerland_restoration_administration"),
            cosmetics.index("set_cosmetic_tag = SOL_vorkerland_worker_protectorate"),
        )

    def test_sol_acceptance_subordinates_only_with_its_choice(self) -> None:
        events = read("events/ADISCORD_vorkerland_events.txt")
        start = events.index("id = ADISCORD_vorkerland_diplomacy.2\n")
        end = events.index("\ncountry_event = {", start)
        event = events[start:end]
        acceptance = named_block(event, "option")
        self.assertIn("puppet = SOL", acceptance)
        self.assertIn("autonomy_state = autonomy_puppet", acceptance)
        decline = event[event.index("name = ADISCORD_vorkerland_diplomacy.2.b"):]
        self.assertNotIn("puppet =", decline)
        self.assertNotIn("set_autonomy", decline)

    def test_vlad_capstone_keeps_empire_while_joint_council_drops_temporary_cosmetic(
        self,
    ) -> None:
        source = source_section(
            read("common/national_focus/ADISCORD_vorkerland_focus.txt"),
            'civil_war_focus',
        )
        match = re.search(
            r"(?ms)^\s*focus\s*=\s*\{\s*id\s*=\s*WRK_joint_impose_reunification_settlement\b",
            source,
        )
        self.assertIsNotNone(match)
        focus = named_block(source[match.start() :], "focus")
        reward = named_block(focus, "completion_reward")
        self.assertEqual(reward.count("drop_cosmetic_tag = yes"), 1)
        self.assertIn(
            "has_global_flag = ADISCORD_vorkerland_joint_government_formed", reward
        )
        self.assertIn("set_cosmetic_tag = VAD_vorkerland_restoration", reward)
        self.assertIn("character = WRK_Vlad_Petrichev", reward)
        self.assertIn("civilian = { large = GFX_portrait_WRK_Vlad_Petrichev }", reward)
        self.assertIn("portrait = GFX_portrait_WRK_Vlad_Petrichev\n", reward)
        self.assertNotIn("GFX_portrait_WRK_Vlad_Petrichev_civilwar", reward)
        self.assertIn(
            "add_ideas = ADISCORD_vorkerland_reunification_settlement", reward
        )

    def test_vlad_postwar_route_unlocks_sequential_imperial_reclamation(self) -> None:
        focuses = source_section(
            read("common/national_focus/ADISCORD_vorkerland_focus.txt"),
            'civil_war_focus',
        )
        match = re.search(
            r"(?ms)^\s*focus\s*=\s*\{\s*id\s*=\s*WRK_joint_issue_integration_warrants\b",
            focuses,
        )
        self.assertIsNotNone(match)
        warrants = named_block(focuses[match.start() :], "focus")
        self.assertIn(
            "unlock_decision_tooltip = ADISCORD_vorkerland_vad_continue_imperial_reunification",
            warrants,
        )
        self.assertIn(
            "set_country_flag = ADISCORD_vorkerland_vad_imperial_reclamation_unlocked",
            warrants,
        )

        decisions = read("common/decisions/ADISCORD_vorkerland_decisions.txt")
        reclaim = named_block(
            decisions, "ADISCORD_vorkerland_vad_continue_imperial_reunification"
        )
        self.assertTrue(reclaim)
        self.assertIn("has_country_flag = ADISCORD_vorkerland_route_joint", reclaim)
        self.assertIn(
            "NOT = { has_global_flag = ADISCORD_vorkerland_joint_government_formed }",
            reclaim,
        )
        self.assertIn("has_war = no", reclaim)
        self.assertIn("days_re_enable = 14", reclaim)
        self.assertIn("fire_only_once = no", reclaim)
        self.assertIn(
            "ADISCORD_vorkerland_continue_imperial_reunification = yes", reclaim
        )
        dispatch = named_block(
            read("common/scripted_effects/ADISCORD_vorkerland_effects.txt"),
            "ADISCORD_vorkerland_continue_imperial_reunification",
        )
        for tag in ("EYR", "EGC", "VLA", "ROM", "ZTA", "TGD"):
            self.assertIn(
                f"declare_war_on = {{ target = {tag} type = annex_everything }}",
                dispatch,
            )

    def test_reunified_vlad_keeps_empire_unless_the_rare_council_formed(self) -> None:
        source = source_section(
            read("common/scripted_effects/ADISCORD_vorkerland_effects.txt"),
            "phase_effects",
        )
        formation = named_block(source, "ADISCORD_vorkerland_form_wrk_from_vad")
        identity = re.search(
            r"(?s)if\s*=\s*\{\s*limit\s*=\s*\{(?P<limit>[^{}]*)\}\s*"
            r"set_cosmetic_tag\s*=\s*WRK_vorkerland_joint_government\s*"
            r"ADISCORD_vorkerland_appoint_joint_council\s*=\s*yes\s*\}"
            r"\s*else\s*=\s*\{(?P<else>.*?portrait\s*=\s*GFX_portrait_WRK_Vlad_Petrichev)\s",
            formation,
        )
        self.assertIsNotNone(identity)
        self.assertIn(
            "ADISCORD_vorkerland_joint_government_formed", identity.group("limit")
        )
        self.assertNotIn(
            "ADISCORD_vorkerland_worker_rescued_by_vlad", identity.group("limit")
        )
        self.assertIn(
            "set_cosmetic_tag = VAD_vorkerland_restoration", identity.group("else")
        )
        self.assertIn("character = WRK_Vlad_Petrichev", identity.group("else"))
        self.assertIn(
            "NOT = { has_global_flag = ADISCORD_vorkerland_joint_government_formed }",
            formation,
        )
        self.assertIn("character = WRK_Vlad_Petrichev", formation)
        self.assertIn("character = WRK_Nikita_Worcker", formation)
        self.assertIn("civilian = { large = GFX_portrait_WRK_Vlad_Petrichev }", formation)
        self.assertNotIn("GFX_portrait_WRK_Vlad_Petrichev_civilwar", formation)

    def test_joint_council_gets_specific_victory_text_before_inactive_fallback(
        self,
    ) -> None:
        scripted = read(
            "common/scripted_localisation/ADISCORD_scripted_loc_superevents.txt"
        )
        for suffix in ("title", "quote", "comment"):
            joint_key = f"superevent_vorkerland_joint_victory_{suffix}"
            fallback = f"superevent_inactive_{suffix}"
            self.assertEqual(scripted.count(f"localization_key = {joint_key}"), 1)
            self.assertLess(scripted.index(joint_key), scripted.index(fallback))

        for path in (
            "localisation/english/ADISCORD_superevents_l_english.yml",
            "localisation/russian/ADISCORD_superevents_l_russian.yml",
        ):
            localisation = read(path)
            for suffix in ("title", "quote", "comment"):
                self.assertIn(
                    f"superevent_vorkerland_joint_victory_{suffix}:", localisation
                )

        russian = ROOT / "localisation/russian/ADISCORD_superevents_l_russian.yml"
        self.assertTrue(russian.read_bytes().startswith(b"\xef\xbb\xbf"))

    def test_joint_council_ai_prefers_chancery_over_commandantures(self) -> None:
        source = source_section(
            read("common/national_focus/ADISCORD_vorkerland_focus.txt"),
            'civil_war_focus',
        )

        def focus(focus_id: str) -> str:
            match = re.search(
                rf"(?ms)^\s*focus\s*=\s*\{{\s*id\s*=\s*{re.escape(focus_id)}\b",
                source,
            )
            self.assertIsNotNone(match)
            return named_block(source[match.start() :], "focus")

        registers_ai = named_block(focus("VAD_open_imperial_registers"), "ai_will_do")
        command_ai = named_block(focus("VAD_form_field_commandantures"), "ai_will_do")
        flag = "has_global_flag = ADISCORD_vorkerland_joint_government_formed"
        self.assertIn(flag, registers_ai)
        self.assertIn("factor = 2", registers_ai)
        self.assertIn(flag, command_ai)
        self.assertIn("factor = 0.5", command_ai)


class PostwarExpansionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.focuses = focus_blocks(read("focus_trees/Vorkerland/civil_war/focuses.txt"))
        cls.effects = read("common/scripted_effects/ADISCORD_vorkerland_effects.txt")
        cls.triggers = read("common/scripted_triggers/ADISCORD_vorkerland_triggers.txt")
        cls.plans = read("common/ai_strategy_plans/ADISCORD_vorkerland_plans.txt")
        cls.peace = read("common/on_actions/09_ADISCORD_scripted_peace_on_actions.txt")

    def effect(self, name):
        return named_block(self.effects, "ADISCORD_vorkerland_pw_" + name)

    def expanded_trigger(self, name):
        definitions = {
            entry.key: entry.value
            for entry in parse_clausewitz(self.triggers)
            if isinstance(entry.value, list)
        }

        def expand(entries):
            result = []
            for entry in entries:
                if entry.key in definitions:
                    self.assertIn(entry.value, ("yes", "no"))
                    children = expand(definitions[entry.key])
                    result.append(replace(entry, key="AND" if entry.value == "yes" else "NOT", value=children))
                elif isinstance(entry.value, list):
                    result.append(replace(entry, value=expand(entry.value)))
                else:
                    result.append(entry)
            return result

        return expand(definitions["ADISCORD_vorkerland_pw_" + name])

    def campaign_facts(self):
        facts = {
            ("WRK", "exists", "yes"): True,
            ("WRK", "is_subject", "no"): True,
            ("WRK", "has_capitulated", "no"): True,
            ("WRK", "has_global_flag", "ADISCORD_vorkerland_phase_postwar_integration"): True,
            ("WRK", "has_country_flag", "ADISCORD_vorkerland_pw_campaign_active"): True,
        }
        for tag in ("EBA", "PIV"):
            facts[(tag, "exists", "yes")] = True
            facts[(tag, "has_war_with", "WRK")] = True
            facts[(tag, "has_country_flag", "ADISCORD_vorkerland_pw_campaign_member")] = True
        return facts

    def expedition_world(self):
        world = {}
        for tag in ("WRK", "EBA", "PIV", "VLA", "TGD", "VAL"):
            world[tag] = {
                "exists": tag not in ("VLA", "TGD"),
                "capitulated": False,
                "wars": set(),
                "overlord": None,
                "faction": None,
                "faction_leader": False,
                "neighbors": set(),
                "owned": set(),
                "controlled": set(),
                "flags": set(),
                "leader": None,
            }
        world["EBA"].update(
            leader="EBA_Vlad_Mecra",
            neighbors={"WRK"},
            owned={74, 105, 197, 311, 312, 313, 314},
            controlled={74, 105, 197, 311, 312, 313, 314},
        )
        return world

    def expedition_entry_matches(self, name, world):
        """Evaluate authored conditions with explicit faction and subject scopes."""
        facts = {
            ("WRK", "has_global_flag", "ADISCORD_vorkerland_phase_postwar_integration"): True,
        }
        for tag, country in world.items():
            booleans = {
                "exists": country["exists"],
                "has_capitulated": country["capitulated"],
                "is_subject": country["overlord"] is not None,
                "has_war": bool(country["wars"]),
                "is_in_faction": country["faction"] is not None,
                "is_faction_leader": country["faction_leader"],
            }
            for key, value in booleans.items():
                facts[(tag, key, "yes")] = value
                facts[(tag, key, "no")] = not value
            facts[(tag, "ruling_leader")] = country["leader"]
            for state in country["owned"]:
                facts[(tag, "owns_state", str(state))] = True
            for state in country["controlled"]:
                facts[(tag, "controls_state", str(state))] = True
            for flag in country["flags"]:
                facts[(tag, "has_country_flag", flag)] = True
            for other, partner in world.items():
                facts[(tag, "country_exists", other)] = partner["exists"]
                facts[(tag, "has_war_with", other)] = other in country["wars"]
                facts[(tag, "is_subject_of", other)] = country["overlord"] == other
                facts[(tag, "is_neighbor_of", other)] = other in country["neighbors"] or tag in partner["neighbors"]
                facts[(tag, "is_in_faction_with", other)] = (
                    country["faction"] is not None
                    and country["faction"] == partner["faction"]
                )

        def resolve_iterators(entries, scope, previous=None):
            resolved = []
            for entry in entries:
                if entry.key in ("any_allied_country", "any_subject_country"):
                    candidates = []
                    for tag, country in world.items():
                        if tag == scope or not country["exists"]:
                            continue
                        if entry.key == "any_allied_country":
                            included = facts[(scope, "is_in_faction_with", tag)]
                        else:
                            included = country["overlord"] == scope
                        if included:
                            candidates.append(replace(
                                entry, key=tag,
                                value=resolve_iterators(entry.value, tag, scope),
                            ))
                    resolved.append(replace(entry, key="OR", value=candidates))
                elif isinstance(entry.value, list):
                    nested_scope = entry.key if entry.key in world else scope
                    nested_previous = scope if entry.key in world else previous
                    resolved.append(replace(
                        entry,
                        value=resolve_iterators(entry.value, nested_scope, nested_previous),
                    ))
                else:
                    resolved.append(replace(entry, value=previous) if entry.value == "PREV" else entry)
            return resolved

        conditions = resolve_iterators(self.expanded_trigger(name), "WRK")
        return matches_conditions(conditions, facts, "WRK")

    def test_macri_victory_opens_ebern_alone_and_with_afrela(self):
        world = self.expedition_world()
        self.assertTrue(self.expedition_entry_matches("can_attack_ebern", world))
        world["EBA"]["faction"] = "southern_pact"
        world["PIV"]["faction"] = "southern_pact"
        self.assertTrue(self.expedition_entry_matches("can_attack_ebern", world))
        world["VAL"]["faction"] = "southern_pact"
        self.assertFalse(self.expedition_entry_matches("can_attack_ebern", world))

    def test_macri_route_rejects_each_material_blocker(self):
        baseline = self.expedition_world()
        blockers = (
            ("EBA", "leader", "VLA_Dima_Volch"),
            ("EBA", "neighbors", set()),
            ("EBA", "owned", {74, 105, 197}),
            ("EBA", "controlled", {74, 105, 197}),
            ("VLA", "exists", True),
            ("TGD", "exists", True),
            ("EBA", "exists", False),
            ("EBA", "overlord", "PIV"),
            ("EBA", "capitulated", True),
            ("WRK", "overlord", "VAL"),
            ("WRK", "capitulated", True),
            ("WRK", "wars", {"VAL"}),
            ("EBA", "wars", {"VAL"}),
            ("WRK", "faction", "external_command"),
            ("WRK", "flags", {"ADISCORD_vorkerland_pw_campaign_active"}),
            ("WRK", "flags", {"ADISCORD_vorkerland_pw_settlement_scheduled"}),
            ("VAL", "overlord", "EBA"),
        )
        for tag, field, value in blockers:
            with self.subTest(tag=tag, field=field, value=value):
                world = deepcopy(baseline)
                world[tag][field] = value
                self.assertFalse(self.expedition_entry_matches("can_attack_ebern", world))

    def test_allied_afrela_must_be_free_of_wars_and_subjects(self):
        baseline = self.expedition_world()
        baseline["EBA"]["faction"] = "southern_pact"
        baseline["PIV"]["faction"] = "southern_pact"
        for tag, field, value in (
            ("PIV", "wars", {"VAL"}),
            ("PIV", "overlord", "VAL"),
            ("PIV", "capitulated", True),
            ("VAL", "overlord", "PIV"),
        ):
            with self.subTest(tag=tag, field=field):
                world = deepcopy(baseline)
                world[tag][field] = value
                self.assertFalse(self.expedition_entry_matches("can_attack_ebern", world))

    def test_afrela_requires_a_current_ebern_outcome_and_land_access(self):
        world = self.expedition_world()
        self.assertFalse(self.expedition_entry_matches("can_attack_afrela", world))
        world["EBA"]["overlord"] = "WRK"
        self.assertTrue(self.expedition_entry_matches("can_attack_afrela", world))
        world["EBA"]["overlord"] = None
        world["EBA"]["exists"] = False
        world["WRK"]["owned"] = {74, 105, 197}
        world["WRK"]["controlled"] = {74, 105, 197}
        self.assertFalse(self.expedition_entry_matches("can_attack_afrela", world))
        world["PIV"]["neighbors"] = {"WRK"}
        self.assertTrue(self.expedition_entry_matches("can_attack_afrela", world))
        world["WRK"]["controlled"].remove(197)
        self.assertFalse(self.expedition_entry_matches("can_attack_afrela", world))

    def test_afrela_rejects_external_coalitions_and_unsettled_operations(self):
        baseline = self.expedition_world()
        baseline["EBA"]["overlord"] = "WRK"
        for tag, field, value in (
            ("PIV", "exists", False),
            ("PIV", "overlord", "VAL"),
            ("PIV", "wars", {"VAL"}),
            ("WRK", "wars", {"VAL"}),
            ("WRK", "overlord", "VAL"),
            ("WRK", "flags", {"ADISCORD_vorkerland_pw_campaign_active"}),
            ("WRK", "flags", {"ADISCORD_vorkerland_pw_settlement_scheduled"}),
        ):
            with self.subTest(tag=tag, field=field, value=value):
                world = deepcopy(baseline)
                world[tag][field] = value
                self.assertFalse(self.expedition_entry_matches("can_attack_afrela", world))
        baseline["PIV"]["faction"] = "outside_pact"
        baseline["VAL"]["faction"] = "outside_pact"
        self.assertFalse(self.expedition_entry_matches("can_attack_afrela", baseline))

    def test_ninety_definitions_are_reachable_without_other_winner_focuses(self):
        actual = {key for key in self.focuses if re.fullmatch(r"WRK_\w+_pw_\w+", key)}
        self.assertEqual(actual, set(POSTWAR_EXPANSION_IDS))
        self.assertEqual(len(actual), 90)
        for flag, ids in POSTWAR_EXPANSION_ROUTES.items():
            route = flag.removeprefix("ADISCORD_vorkerland_route_")
            self.assertEqual(len(ids), 30)
            reachable = {key for key in self.focuses if key.startswith(f"WRK_{route}_") and key not in ids}
            pending = set(ids)

            def ready_for(key):
                source = self.focuses[key]
                # A prerequisite block is one OR group; an exclusive sibling is not a parent.
                groups = [
                    set(re.findall(r"focus = (WRK_\w+)", group))
                    for group in re.findall(r"prerequisite = \{([^}]*)\}", source)
                ]
                completed = set(re.findall(r"has_completed_focus = (WRK_\w+)", source))
                return all(group & reachable for group in groups) and completed <= reachable

            while pending:
                ready = {key for key in pending if ready_for(key)}
                self.assertTrue(ready, pending)
                pending -= ready
                reachable |= ready

    def test_only_co_visible_winner_nodes_are_checked_for_overlap(self):
        grid = resolved_positions(self.focuses)
        for route in ("worker", "joint", "utilitarian"):
            points = [grid[key] for key in self.focuses if key.startswith(f"WRK_{route}_")]
            self.assertEqual(len(points), len(set(points)), route)

    def test_ai_equips_and_drills_army_before_the_western_grace_expires(self):
        for route in ("worker", "joint", "utilitarian"):
            plan = named_block(self.plans, f"ADISCORD_vorkerland_wrk_postwar_{route}_plan")
            order = re.findall(r"WRK_\w+", named_block(plan, "ai_national_focuses"))
            terminal = f"WRK_{route}_pw_field_exercises"
            prefix = order[:order.index(terminal) + 1]
            days = sum(int(scalar(parse_clausewitz(self.focuses[key])[0].value, "cost")) * 7 for key in prefix)
            self.assertEqual(days, 140, route)
            self.assertLess(days, 180)
            source = "\n".join(self.focuses[key] for key in prefix)
            self.assertIn(f"WRK_{route}_pw_rearmament", prefix)
            self.assertIn(f"WRK_{route}_pw_defence_cluster", prefix)
            factory_levels = re.findall(r"type = arms_factory\s+level = (\d+)", source)
            self.assertEqual(sum(map(int, factory_levels)), 5)
            self.assertRegex(source, r"add_manpower = (20000|30000|40000)")

    def test_full_routes_have_distinct_manpower_and_weapon_budgets(self):
        # Totals cover every definition, including both answers of each paired choice.
        for route, manpower, rifles in (("worker", 140000, 38000), ("joint", 110000, 43000), ("utilitarian", 70000, 28000)):
            source = "\n".join(self.focuses[key] for key in POSTWAR_EXPANSION_IDS if key.startswith(f"WRK_{route}_"))
            self.assertEqual(sum(map(int, re.findall(r"add_manpower = (\d+)", source))), manpower)
            self.assertEqual(sum(map(int, re.findall(r"type = infantry_equipment\s+amount = (\d+)", source))), rifles)
            self.assertEqual(sum(map(int, re.findall(r"type = arms_factory\s+level = (\d+)", source))), 7)
            self.assertEqual(sum(map(int, re.findall(r"type = industrial_complex\s+level = (\d+)", source))), 8)
            self.assertEqual(source.count("add_research_slot = 1"), 1)

    def test_each_column_offers_one_exclusive_choice_that_rejoins(self):
        for route in ("worker", "joint", "utilitarian"):
            for left, right, merge in POSTWAR_EXPANSION_CHOICES:
                left_id, right_id, merge_id = (f"WRK_{route}_pw_{slug}" for slug in (left, right, merge))
                self.assertIn(f"mutually_exclusive = {{ focus = {right_id} }}", self.focuses[left_id])
                self.assertIn(f"mutually_exclusive = {{ focus = {left_id} }}", self.focuses[right_id])
                self.assertIn(f"prerequisite = {{ focus = {left_id} focus = {right_id} }}", self.focuses[merge_id])
                parents = {
                    tuple(re.findall(r"prerequisite = \{ ([^}]*) \}", self.focuses[key]))
                    for key in (left_id, right_id)
                }
                self.assertEqual(len(parents), 1, (route, left))

    def test_reform_values_accumulate_once_and_dummy_ideas_are_preview_only(self):
        for route, defence, supply, attack in (("worker", 0.12, -0.10, 0), ("joint", 0.02, -0.10, 0.13), ("utilitarian", 0.13, -0.15, 0)):
            totals = Counter()
            for key in POSTWAR_EXPANSION_IDS:
                if not key.startswith(f"WRK_{route}_"):
                    continue
                source = self.focuses[key]
                for field, value in re.findall(r"add_to_variable = \{\s*var = ADISCORD_vorkerland_pw_(\w+)\s*value = (-?[\d.]+)", source):
                    totals[field] += float(value)
                for match in re.finditer(r"add_ideas = ADISCORD_vorkerland_pw_delta_", source):
                    self.assertIn("effect_tooltip", source[:match.start()])
                hidden = named_block(source, "hidden_effect")
                self.assertNotIn("add_ideas = ADISCORD_vorkerland_pw_delta_", hidden)
            self.assertAlmostEqual(totals["org"], 0.07)
            self.assertAlmostEqual(totals["defence"], defence)
            self.assertAlmostEqual(totals["supply"], supply)
            self.assertAlmostEqual(totals["attack"], attack)
            self.assertAlmostEqual(totals["output"], 0.08)
        ensure = self.effect("ensure_institutions")
        self.assertIn("NOT = { has_dynamic_modifier", ensure)
        self.assertNotIn("set_variable", ensure)
        self.assertNotIn("clear_variable", ensure)

    def test_all_factory_rewards_require_a_current_site(self):
        for key in POSTWAR_EXPANSION_IDS:
            source = self.focuses[key]
            if "add_building_construction" not in source:
                continue
            available = named_block(source, "available")
            self.assertIn("any_owned_state", available, key)
            self.assertIn("is_controlled_by = ROOT", available, key)
            self.assertIn("free_building_slots", available, key)

    def test_both_coalition_members_must_fall_and_liberation_blocks_again(self):
        conditions = self.expanded_trigger("expedition_won")
        facts = self.campaign_facts()
        self.assertFalse(matches_conditions(conditions, facts, "WRK"))
        facts[("EBA", "has_capitulated", "yes")] = True
        self.assertFalse(matches_conditions(conditions, facts, "WRK"))
        facts[("PIV", "has_capitulated", "yes")] = True
        self.assertTrue(matches_conditions(conditions, facts, "WRK"))
        facts[("EBA", "has_capitulated", "yes")] = False
        self.assertFalse(matches_conditions(conditions, facts, "WRK"))
        liberation = named_block(self.peace, "on_uncapitulation")
        self.assertIn("clr_country_flag = ADISCORD_vorkerland_pw_capitulation_reserved", liberation)

    def test_immediate_capitulation_receipt_and_single_target_campaign(self):
        conditions = self.expanded_trigger("expedition_won")
        facts = self.campaign_facts()
        facts[("EBA", "has_country_flag", "ADISCORD_vorkerland_pw_campaign_member")] = False
        facts[("PIV", "has_country_flag", "ADISCORD_vorkerland_pw_capitulation_reserved")] = True
        self.assertTrue(matches_conditions(conditions, facts, "WRK"))
        facts[("PIV", "has_country_flag", "ADISCORD_vorkerland_pw_capitulation_reserved")] = False
        self.assertFalse(matches_conditions(conditions, facts, "WRK"))

    def test_annexed_target_and_subjugated_winner_cannot_claim_victory(self):
        conditions = self.expanded_trigger("expedition_won")
        facts = self.campaign_facts()
        for tag in ("EBA", "PIV"):
            facts[(tag, "has_capitulated", "yes")] = True
        facts[("EBA", "exists", "yes")] = False
        self.assertFalse(matches_conditions(conditions, facts, "WRK"))
        facts[("EBA", "exists", "yes")] = True
        facts[("WRK", "is_subject", "no")] = False
        self.assertFalse(matches_conditions(conditions, facts, "WRK"))

    def test_coalition_joins_the_same_war_and_all_temporary_majors_are_removed(self):
        source = self.effect("start_ebern_campaign")
        self.assertLess(source.index("EBA = { ADISCORD_vorkerland_pw_prepare_member"), source.index("declare_war_on"))
        self.assertIn("targeted_alliance = EBA", source)
        self.assertIn("enemy = WRK", source)
        self.assertIn("single_target_only = yes", source)
        self.assertIn("is_major = no", self.effect("prepare_member"))
        self.assertIn("set_major = no", self.effect("clear_member"))
        close = self.effect("close_expedition")
        self.assertLess(close.index("clr_country_flag = ADISCORD_vorkerland_pw_campaign_active"), close.index("ADISCORD_vorkerland_pw_end_member_wars"))
        for tag in ("EBA", "PIV"):
            self.assertIn(f"{tag} = {{ ADISCORD_vorkerland_pw_clear_member = yes }}", close)

    def test_delayed_settlement_rechecks_both_parties_and_closes_pending_state(self):
        finish = self.effect("finish_expedition")
        self.assertLess(finish.index("pw_prepare_settlement"), finish.index("pw_close_expedition"))
        self.assertRegex(finish, r"id = ADISCORD_vorkerland_postwar\.2\s+days = 1")
        settlement = self.effect("create_subject")
        for guard in ("exists = yes", "is_subject = no", "is_in_faction = no", "WRK = { ADISCORD_vorkerland_pw_sovereign = yes }"):
            self.assertIn(guard, settlement)
        self.assertIn("clr_country_flag = ADISCORD_vorkerland_pw_subject_pending", settlement)
        external = self.effect("close_external")
        self.assertIn("clr_country_flag = ADISCORD_vorkerland_pw_settlement_scheduled", external)
        for tag in ("EBA", "PIV"):
            self.assertIn(f"{tag} = {{ clr_country_flag = ADISCORD_vorkerland_pw_subject_pending }}", external)

    def test_campaign_can_be_retried_without_repeating_focus_rewards(self):
        decisions = read("common/decisions/ADISCORD_vorkerland_decisions.txt")
        for target in ("ebern", "afrela"):
            decision = named_block(decisions, f"ADISCORD_vorkerland_pw_{target}_campaign")
            self.assertNotIn("fire_only_once", decision)
            self.assertIn(f"ADISCORD_vorkerland_pw_can_attack_{target} = yes", decision)
            self.assertIn("has_war = no", decision)
            self.assertIn("cost = 50", decision)
            self.assertNotIn("add_political_power", decision)
            for route in ("worker", "joint", "utilitarian"):
                focus = self.focuses[f"WRK_{route}_pw_{target}_campaign"]
                self.assertIn(f"unlock_decision_tooltip = ADISCORD_vorkerland_pw_{target}_campaign", focus)
                self.assertNotIn("pw_start_", focus)

    def test_losing_wrk_keeps_the_war_for_the_final_capitulation_router(self):
        handler = self.effect("handle_capitulation")
        defeat = named_block(handler, "else_if")
        self.assertIn("ROOT = { tag = WRK }", defeat)
        self.assertIn("clr_country_flag = ADISCORD_vorkerland_pw_campaign_active", defeat)
        self.assertNotIn("pw_close_expedition", defeat)
        self.assertNotIn("white_peace", defeat)
        for tag in ("EBA", "PIV"):
            self.assertIn(f"{tag} = {{ ADISCORD_vorkerland_pw_clear_member = yes }}", defeat)

    def test_immediate_settlement_restores_the_late_callback_receipt(self):
        handler = self.effect("handle_capitulation")
        victory = named_block(handler, "if")
        finish = victory.index("ADISCORD_vorkerland_pw_finish_expedition = yes")
        receipt = "flag = ADISCORD_vorkerland_pw_capitulation_reserved"
        self.assertIn(receipt, victory[:finish])
        self.assertIn(receipt, victory[finish:])

    def test_subject_obligations_and_governments_follow_the_winner(self):
        source = self.effect("apply_subject_government")
        for autonomy in ("autonomy_WRK_confederate_republic", "autonomy_WRK_military_administration", "autonomy_WRK_technical_trusteeship"):
            self.assertIn(autonomy, source)
        for government in ("humanism", "utilitarism", "chauvinism", "pragmatism", "anarchism", "technocracy", "etatism", "hedonism"):
            self.assertIn(f"WRK = {{ has_government = {government} }}", source)
            self.assertIn(f"ruling_party = {government}", source)
        self.assertIn("is_subject_of = WRK", source)
        self.assertNotIn("set_rule", source)

    def test_western_front_preserves_readiness_and_production_budget(self):
        source = read("common/ai_strategy/ADISCORD_west_final_war_ai.txt")
        # The offensive profile mirrors Itora's manual pokes; a depleted army holds.
        for name, mode, manual in (
            ("ADISCORD_west_wrk_front_ivn", "balanced", "yes"),
            ("ADISCORD_west_wrk_hold_ivn", "careful", "no"),
        ):
            front = named_block(source, name)
            self.assertIn(f"execution_type = {mode}", front)
            self.assertIn(f"manual_attack = {manual}", front)
            self.assertIn("ratio < 0.67", front)
        production = named_block(source, "ADISCORD_wrk_postwar_production")
        self.assertNotIn("production_min_factories", production)
        self.assertIn("equipment_production_factor", production)

    def test_reconstruction_reserves_a_slot_until_completion_or_cancellation(self):
        decisions = read("common/decisions/ADISCORD_vorkerland_decisions.txt")
        decision = named_block(decisions, "ADISCORD_vorkerland_pw_rebuild_district")
        self.assertIn("ADISCORD_vorkerland_pw_rebuild_slot_free = yes", decision)
        self.assertIn("FROM = { ADISCORD_vorkerland_pw_begin_rebuild = yes }", named_block(decision, "complete_effect"))
        self.assertIn("FROM = { ADISCORD_vorkerland_pw_finish_rebuild = yes }", named_block(decision, "remove_effect"))
        self.assertIn("FROM = { ADISCORD_vorkerland_pw_release_rebuild = yes }", named_block(decision, "cancel_effect"))
        self.assertIn("ADISCORD_vorkerland_pw_rebuild_site = yes", named_block(decision, "target_trigger"))
        begin = self.effect("begin_rebuild")
        release = self.effect("release_rebuild")
        finish = self.effect("finish_rebuild")
        self.assertIn("value = 1", begin)
        self.assertIn("value = -1", release)
        self.assertIn("limit = { has_state_flag = ADISCORD_vorkerland_pw_rebuild_in_progress }", release)
        # The slot is released before the delivery check, so a lost district never holds it.
        self.assertLess(finish.index("ADISCORD_vorkerland_pw_release_rebuild = yes"), finish.index("ADISCORD_vorkerland_pw_rebuild_site = yes"))
        self.assertLess(finish.index("ADISCORD_vorkerland_pw_rebuild_reward = yes"), finish.index("set_state_flag = ADISCORD_vorkerland_pw_district_rebuilt"))
        triggers = read("common/scripted_triggers/ADISCORD_vorkerland_triggers.txt")
        slots = named_block(triggers, "ADISCORD_vorkerland_pw_rebuild_slot_free")
        self.assertEqual(sorted(map(int, re.findall(r"rebuild_active value = (\d+)", slots))), [1, 2, 3])
        for route in ("worker", "joint", "utilitarian"):
            self.assertIn(f"has_completed_focus = WRK_{route}_pw_census", named_block(triggers, "ADISCORD_vorkerland_pw_reconstruction_open"))
            self.assertIn(f"has_completed_focus = WRK_{route}_pw_repair_crews", slots)
            self.assertIn(f"has_completed_focus = WRK_{route}_pw_municipal_network", slots)

    def test_no_new_periodic_scans_or_legacy_recovery(self):
        source = self.effects[self.effects.index("ADISCORD_vorkerland_pw_ensure_institutions = {"):]
        for token in ("every_country", "every_possible_country", "on_daily", "on_monthly", "while_loop", "legacy"):
            self.assertNotIn(token, source)
        peace = self.peace
        for hook in ("on_capitulation_immediate", "on_capitulation"):
            self.assertIn("ADISCORD_vorkerland_pw_handle_capitulation = yes", named_block(peace, hook))
        for hook in ("on_peace", "on_puppet", "on_annex"):
            self.assertIn("ADISCORD_vorkerland_pw_close_external = yes", named_block(peace, hook))

    def test_localisation_is_complete_bom_encoded_and_physically_bounded(self):
        for language in ("english", "russian"):
            path = ROOT / f"localisation/{language}/ADISCORD_vorkerland_l_{language}.yml"
            self.assertTrue(path.read_bytes().startswith(b"\xef\xbb\xbf"))
            text = path.read_text(encoding="utf-8-sig")
            section = text.split(f"# --- postwar_expansion_l_{language} ---", 1)[1]
            section = section.split(f"# --- end_postwar_expansion_l_{language} ---", 1)[0]
            for line in section.splitlines():
                if not line.strip():
                    continue
                self.assertRegex(line, r'^ [A-Za-z0-9_.]+: "[^"\r\n]*"$')
            for key in POSTWAR_EXPANSION_IDS:
                self.assertIn(f' {key}: "', section)
                self.assertIn(f' {key}_desc: "', section)



class WorldEmpireTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = read("focus_trees/Vorkerland/world_empire/focuses.txt")
        cls.tree = block(parse_clausewitz(cls.source), "focus_tree")
        cls.focuses = {
            scalar(entry.value, "id"): entry.value
            for entry in cls.tree if entry.key == "focus"
        }
        cls.effects = read("common/scripted_effects/ADISCORD_vorkerland_effects.txt")

    @staticmethod
    def executable_entries(entries):
        for entry in entries:
            if entry.key == "effect_tooltip":
                continue
            yield entry
            if isinstance(entry.value, list):
                yield from WorldEmpireTests.executable_entries(entry.value)

    def test_guard_requires_joint_council_and_rejects_second_transition(self):
        triggers = parse_clausewitz(read("common/scripted_triggers/ADISCORD_vorkerland_triggers.txt"))
        guard = block(triggers, "ADISCORD_vorkerland_world_empire_can_form")
        facts = {
            ("WRK", "is_subject", "no"): True,
            ("WRK", "has_capitulated", "no"): True,
            ("WRK", "has_global_flag", "ADISCORD_vorkerland_reunification_verified"): True,
            ("WRK", "has_global_flag", "ADISCORD_vorkerland_collapse_finished"): True,
            ("WRK", "has_global_flag", "ADISCORD_vorkerland_joint_government_formed"): True,
            ("WRK", "has_country_flag", "ADISCORD_vorkerland_route_joint"): True,
            ("WRK", "has_cosmetic_tag", "WRK_vorkerland_joint_government"): True,
            ("WRK", "has_character", "WRK_Nikita_Worcker"): True,
            ("WRK", "ruling_leader"): "WRK_VAD_Joint_Council",
        }
        self.assertTrue(matches_conditions(guard, facts, "WRK"))
        for key in facts:
            with self.subTest(missing=key):
                invalid = dict(facts)
                invalid.pop(key)
                self.assertFalse(matches_conditions(guard, invalid, "WRK"))
        ordinary_vlad = dict(facts)
        ordinary_vlad[("WRK", "ruling_leader")] = "WRK_Vlad_Petrichev"
        self.assertFalse(matches_conditions(guard, ordinary_vlad, "WRK"))
        after = dict(facts)
        after.pop(("WRK", "has_cosmetic_tag", "WRK_vorkerland_joint_government"))
        after[("WRK", "has_cosmetic_tag", "WRK_vorkerland_world_empire")] = True
        after[("WRK", "ruling_leader")] = "WRK_Nikita_Worcker"
        self.assertFalse(matches_conditions(guard, after, "WRK"))
        self.assertFalse(matches_conditions(guard, facts, "VAD"))

    def test_hidden_transition_installs_etatist_role_portrait_and_news(self):
        change = named_block(self.effects, "ADISCORD_vorkerland_establish_world_empire")
        payload = block(block(parse_clausewitz(change), "ADISCORD_vorkerland_establish_world_empire"), "if")
        self.assertEqual(scalar(block(payload, "limit"), "ADISCORD_vorkerland_world_empire_can_form"), "yes")
        self.assertEqual(scalar(payload, "set_cosmetic_tag"), "WRK_vorkerland_world_empire")
        self.assertEqual(scalar(block(payload, "set_politics"), "ruling_party"), "etatism")
        role = block(payload, "add_country_leader_role")
        self.assertEqual(scalar(role, "character"), "WRK_Nikita_Worcker")
        self.assertEqual(scalar(block(role, "country_leader"), "ideology"), "etatism_ideology")
        self.assertEqual(scalar(role, "promote_leader"), "yes")
        self.assertLess(change.index("add_country_leader_role"), change.index("set_politics"))
        portrait = block(block(payload, "set_portraits"), "civilian")
        self.assertEqual(scalar(portrait, "large"), "GFX_portrait_WRK_Nikita_Worcker_victory")
        self.assertIn("retire_character = WRK_VAD_Joint_Council", change)
        self.assertEqual(change.count("retire_character = WRK_Vlad_Petrichev"), 2)
        self.assertEqual(scalar(block(payload, "load_focus_tree"), "tree"), "ADISCORD_vorkerland_world_empire_focus")
        events = parse_clausewitz(read("events/ADISCORD_vorkerland_events.txt"))
        callback = next(e.value for e in events if isinstance(e.value, list) and scalar(e.value, "id") == "ADISCORD_vorkerland_postwar.4")
        self.assertEqual(scalar(callback, "hidden"), "yes")
        self.assertEqual(scalar(block(callback, "immediate"), "ADISCORD_vorkerland_establish_world_empire"), "yes")
        self.assertNotIn("option", [e.key for e in callback])
        self.assertEqual(scalar(block(payload, "news_event"), "id"), "ADISCORD_vorkerland_postwar.5")

    def test_approved_resource_package_and_exact_delta_previews(self):
        from decimal import Decimal
        totals = Counter()
        variables = Counter()
        equipment = Counter()
        buildings = Counter()
        ideas = block(block(parse_clausewitz(read("common/ideas/ADISCORD_vorkerland_ideas.txt")), "ideas"), "country")
        variable_modifiers = {
            "WRK_empire_attack": "army_attack_factor",
            "WRK_empire_defence": "army_defence_factor",
            "WRK_empire_org": "army_org_factor",
            "WRK_empire_supply": "supply_consumption_factor",
            "WRK_empire_output": "industrial_capacity_factory",
        }
        for focus_id, focus in self.focuses.items():
            reward = block(focus, "completion_reward")
            applied = Counter()
            for entry in self.executable_entries(reward):
                if entry.key == "add_manpower":
                    totals[entry.key] += int(entry.value)
                elif entry.key == "add_to_variable":
                    variable = scalar(entry.value, "var")
                    amount = Decimal(scalar(entry.value, "value"))
                    variables[variable] += amount
                    applied[variable_modifiers[variable]] += amount
                elif entry.key == "add_equipment_to_stockpile":
                    equipment[scalar(entry.value, "type")] += int(scalar(entry.value, "amount"))
                elif entry.key == "add_building_construction":
                    buildings[scalar(entry.value, "type")] += int(scalar(entry.value, "level"))
                elif entry.key == "add_ideas":
                    self.fail(f"Delta preview is installed by {focus_id}")
            preview = Counter()
            for item in reward:
                if item.key == "effect_tooltip":
                    for idea in item.value:
                        for modifier in block(block(ideas, idea.value), "modifier"):
                            preview[modifier.key] += Decimal(modifier.value)
            self.assertEqual(dict(applied), dict(preview), focus_id)
        self.assertEqual(totals["add_manpower"], 150000)
        self.assertEqual(dict(buildings), {"arms_factory": 12, "industrial_complex": 6})
        self.assertEqual(dict(equipment), {
            "infantry_equipment": 40000,
            "artillery_equipment": 2000,
            "support_equipment": 3000,
            "motorized_equipment_1": 2500,
            "train_equipment_1": 200,
            "ADISCORD_fighter_airframe_2163": 400,
            "ADISCORD_cas_airframe_2170": 200,
        })
        self.assertEqual(dict(variables), {
            "WRK_empire_output": Decimal("0.35"),
            "WRK_empire_org": Decimal("0.20"),
            "WRK_empire_defence": Decimal("0.30"),
            "WRK_empire_attack": Decimal("0.30"),
            "WRK_empire_supply": Decimal("-0.20"),
        })

    def test_every_preparation_precedes_war_and_remains_available_during_war(self):
        self.assertEqual(len(self.focuses), 23)
        requirements = {
            key: {scalar(item.value, "focus") for item in focus if item.key == "prerequisite"}
            for key, focus in self.focuses.items()
        }
        visited = set()
        def visit(key, stack):
            self.assertNotIn(key, stack, "Focus dependency cycle")
            self.assertIn(key, self.focuses)
            if key in visited:
                return
            for parent in requirements[key]:
                visit(parent, stack | {key})
            visited.add(key)
        visit("WRK_empire_itora_must_fall", set())
        self.assertEqual(visited, set(self.focuses))
        positions = [(scalar(f, "x"), scalar(f, "y")) for f in self.focuses.values()]
        self.assertEqual(len(positions), len(set(positions)))
        self.assertTrue(all(2 <= int(scalar(f, "cost")) <= 5 for f in self.focuses.values()))
        self.assertEqual(sum(int(scalar(f, "cost")) for f in self.focuses.values()) * 7, 469)
        for key, focus in self.focuses.items():
            if key != "WRK_empire_itora_must_fall":
                text = str(block(focus, "available"))
                self.assertNotIn("has_war", text, key)
                self.assertNotIn("ADISCORD_west_final_active", text, key)
        war = self.focuses["WRK_empire_itora_must_fall"]
        hidden = block(block(war, "completion_reward"), "hidden_effect")
        self.assertEqual(scalar(hidden, "ADISCORD_west_final_war_start"), "yes")
        self.assertNotIn("declare_war_on", [e.key for e in hidden])
        self.assertTrue(block(war, "bypass"))

    def test_factories_check_same_site_and_capacity_at_delivery(self):
        for key, focus in self.focuses.items():
            reward = block(focus, "completion_reward")
            targets = [e.value for e in reward if e.key == "random_owned_controlled_state"]
            for target in targets:
                available = block(block(block(focus, "available"), "custom_trigger_tooltip"), "any_owned_state")
                self.assertEqual(scalar(available, "is_controlled_by"), "ROOT")
                required_slots = block(available, "free_building_slots")
                delivered_slots = block(block(target, "limit"), "free_building_slots")
                self.assertEqual(
                    [(entry.key, entry.value) for entry in required_slots],
                    [(entry.key, entry.value) for entry in delivered_slots],
                    key,
                )
                self.assertEqual(scalar(available, "is_core_of"), scalar(block(target, "limit"), "is_core_of"))
                self.assertEqual(scalar(target, "add_extra_state_shared_building_slots"), scalar(block(target, "add_building_construction"), "level"))

    def test_news_localisation_and_flag_outputs(self):
        from tools.builders.build_adiscord_vorkerland_original_flags import expected_outputs, validate_outputs
        for language in ("russian", "english"):
            path = ROOT / f"localisation/{language}/ADISCORD_vorkerland_l_{language}.yml"
            self.assertTrue(path.read_bytes().startswith(b"\xef\xbb\xbf"))
            text = path.read_text(encoding="utf-8-sig")
            for key in self.focuses:
                for loc_key in (key, key + "_desc"):
                    self.assertEqual(len(re.findall(rf'^ {loc_key}:0 "[^"\r\n]*"$', text, re.M)), 1)
            news = re.findall(r'^ ADISCORD_vorkerland_postwar\.5\.d:0 "([^"\r\n]*)"$', text, re.M)
            self.assertEqual(len(news), 1)
            expanded = news[0].replace(r"\n", "\n")
            self.assertLessEqual(len(expanded), 3000)
            self.assertLessEqual(len(expanded.encode("utf-8")), 5500)
        outputs = expected_outputs({"WRK_vorkerland_world_empire"})
        self.assertEqual(len(outputs), 4)
        self.assertEqual(validate_outputs(outputs), [])


if __name__ == "__main__":
    unittest.main()
