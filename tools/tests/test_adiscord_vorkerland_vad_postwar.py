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

    def test_joint_council_gets_specific_victory_text_before_vlad_fallback(
        self,
    ) -> None:
        scripted = read(
            "common/scripted_localisation/ADISCORD_scripted_loc_superevents.txt"
        )
        for suffix in ("title", "quote", "comment"):
            joint_key = f"superevent_vorkerland_joint_victory_{suffix}"
            vlad_key = f"superevent_vorkerland_vlad_victory_{suffix}"
            self.assertEqual(scripted.count(f"localization_key = {joint_key}"), 1)
            self.assertLess(scripted.index(joint_key), scripted.index(vlad_key))

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
            while pending:
                ready = {
                    key for key in pending
                    if set(re.findall(r"\b(?:focus|has_completed_focus) = (WRK_\w+)", self.focuses[key])) <= reachable
                }
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
            self.assertEqual(sum(map(int, factory_levels)), 3)
            self.assertRegex(source, r"add_manpower = (10000|12000|16000)")

    def test_full_routes_have_distinct_manpower_and_weapon_budgets(self):
        for route, manpower, rifles in (("worker", 24000, 12000), ("joint", 30000, 15000), ("utilitarian", 18000, 9000)):
            source = "\n".join(self.focuses[key] for key in POSTWAR_EXPANSION_IDS if key.startswith(f"WRK_{route}_"))
            self.assertEqual(sum(map(int, re.findall(r"add_manpower = (\d+)", source))), manpower)
            self.assertEqual(sum(map(int, re.findall(r"type = infantry_equipment\s+amount = (\d+)", source))), rifles)
            self.assertEqual(sum(map(int, re.findall(r"type = arms_factory\s+level = (\d+)", source))), 4)

    def test_reform_values_accumulate_once_and_dummy_ideas_are_preview_only(self):
        for route, defence, supply, attack in (("worker", 0.08, -0.05, 0), ("joint", 0.06, -0.05, 0.05), ("utilitarian", 0.09, -0.10, 0)):
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
        for name, mode in (("ADISCORD_west_wrk_front_ivn", "balanced"), ("ADISCORD_west_wrk_hold_ivn", "careful")):
            front = named_block(source, name)
            self.assertIn(f"execution_type = {mode}", front)
            self.assertIn("manual_attack = no", front)
            self.assertIn("ratio < 0.67", front)
        production = named_block(source, "ADISCORD_wrk_postwar_production")
        self.assertNotIn("production_min_factories", production)
        self.assertIn("equipment_production_factor", production)

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


if __name__ == "__main__":
    unittest.main()
