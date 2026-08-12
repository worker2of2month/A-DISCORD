from __future__ import annotations

from collections import Counter
import re
import unittest

from tools.validators.validate_adiscord_vorkerland_civil_war_focus import (
    ACTIVE_PHASE_FLAGS,
    CENTRAL_CAPSTONES,
    CENTRAL_PREPARED_FLAG,
    CENTRAL_PREPARED_TOOLTIP,
    CHARACTER_FILE,
    COLLAPSE_IDEAS_FILE,
    CORE_DECISIONS,
    DIPLOMACY_DECISIONS_FILE,
    DORMANT_WRK_CRISIS_IDEAS,
    DORMANT_WRK_SCRUB_EFFECT,
    ENGLISH_LOCALISATION,
    ENGLISH_POSTWAR_IDEA_LOCALISATION,
    FINAL_FOCUS,
    FOCUS_DECISIONS_FILE,
    FOCUS_FILE,
    FOCUS_IDS,
    IVANLAND_EXPEDITIONARY_IDEA,
    LAND_REPAIR_IDEAS,
    MOBILE_REPAIR_IDEA,
    PHASE_EFFECTS_FILE,
    POSTWAR_PHASE,
    POSTWAR_IDEA_LOCALISATION_IDS,
    POSTWAR_ROUTE_FOCUSES,
    POSTWAR_SETTLEMENT_IDEAS,
    PREWAR_CARRYOVER_EFFECT,
    PREWAR_CARRYOVER_FLAG,
    PREWAR_PHASE,
    PREWAR_VAD_FOCUSES,
    PREWAR_WRK_FOCUSES,
    RETREAT_HOOKS,
    ROOT,
    RUSSIAN_LOCALISATION,
    RUSSIAN_POSTWAR_IDEA_LOCALISATION,
    SHINE_FILE,
    SHARED_WARTIME_FOCUSES,
    WARTIME_ROUTE_FOCUSES,
    WARTIME_CONVERGENCE,
    WORX_POSTWAR_PROVISIONAL_IDEAS,
    WORX_WARTIME_TIMED_IDEAS,
    WORKER_REFORM_INHERIT_EFFECT,
    WORKER_REFORM_STAGE_IDEAS,
    WRK_FORMATION_EFFECTS,
    _blocks,
    _phase_flags,
    _prerequisites,
    collect_issues,
    focus_blocks,
    localisation_entries,
    read,
)


class VorkerlandLifecycleFocusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = read(FOCUS_FILE)
        cls.blocks = focus_blocks(cls.source)
        cls.phase_effects = read(PHASE_EFFECTS_FILE)
        cls.collapse_ideas = read(COLLAPSE_IDEAS_FILE)

    def test_integrated_focus_contract(self) -> None:
        self.assertEqual(collect_issues(), [])

    def test_one_tree_follows_all_four_lifecycle_tags(self) -> None:
        selector = self.source.split("default = no", maxsplit=1)[0]
        for tag in ("WRK", "WKR", "VAD", "TVA"):
            self.assertEqual(selector.count(f"tag = {tag}"), 1)
        self.assertNotIn("original_tag", selector)

    def test_manifest_has_sixty_five_bounded_definitions(self) -> None:
        self.assertEqual(tuple(self.blocks), FOCUS_IDS)
        self.assertEqual(len(self.blocks), 65)
        self.assertEqual(len(PREWAR_WRK_FOCUSES), 6)
        self.assertEqual(len(PREWAR_VAD_FOCUSES), 6)
        self.assertEqual(len(SHARED_WARTIME_FOCUSES), 5)
        self.assertTrue(all(len(route) == 9 for route in WARTIME_ROUTE_FOCUSES.values()))
        self.assertTrue(all(len(route) == 7 for route in POSTWAR_ROUTE_FOCUSES.values()))

    def test_each_claimant_has_a_twenty_one_focus_authored_route(self) -> None:
        routes = (
            ("WKR", "ADISCORD_vorkerland_route_worker"),
            ("VAD", "ADISCORD_vorkerland_route_joint"),
            ("TVA", "ADISCORD_vorkerland_route_utilitarian"),
        )
        for tag, route_flag in routes:
            with self.subTest(tag=tag):
                authored = (
                    len(SHARED_WARTIME_FOCUSES)
                    + len(WARTIME_ROUTE_FOCUSES[tag])
                    + len(POSTWAR_ROUTE_FOCUSES[route_flag])
                )
                self.assertEqual(authored, 21)

    def test_prewar_blocks_are_separate_and_phase_bounded(self) -> None:
        for tag, focus_ids in (("WRK", PREWAR_WRK_FOCUSES), ("VAD", PREWAR_VAD_FOCUSES)):
            for focus_id in focus_ids:
                with self.subTest(focus_id=focus_id):
                    block = self.blocks[focus_id]
                    self.assertEqual(_phase_flags(block), {PREWAR_PHASE})
                    self.assertIn(f"allow_branch = {{ tag = {tag}", block)

    def test_prewar_wrk_rewards_cross_once_into_the_materialized_wkr(self) -> None:
        definitions = _blocks(self.phase_effects, PREWAR_CARRYOVER_EFFECT)
        self.assertEqual(len(definitions), 1)
        carryover = definitions[0]
        self.assertIn("tag = WKR", carryover)
        self.assertRegex(
            carryover,
            rf"NOT\s*=\s*\{{\s*has_country_flag\s*=\s*{PREWAR_CARRYOVER_FLAG}\s*\}}",
        )
        self.assertEqual(
            carryover.count(f"set_country_flag = {PREWAR_CARRYOVER_FLAG}"), 1
        )
        for focus_id in PREWAR_WRK_FOCUSES:
            with self.subTest(focus_id=focus_id):
                self.assertEqual(
                    carryover.count(f"has_completed_focus = {focus_id}"), 1
                )

        verify = _blocks(
            self.phase_effects, "ADISCORD_vorkerland_verify_collapse_materialized"
        )[0]
        wkr_tree_scopes = [
            scope for scope in _blocks(verify, "WKR") if "load_focus_tree" in scope
        ]
        self.assertEqual(len(wkr_tree_scopes), 1)
        self.assertIn(f"{PREWAR_CARRYOVER_EFFECT} = yes", wkr_tree_scopes[0])

    def test_all_winner_formations_normalize_the_dormant_wrk_before_annex(self) -> None:
        scrub = _blocks(self.phase_effects, DORMANT_WRK_SCRUB_EFFECT)[0]
        scrubbed_ideas = Counter(
            re.findall(r"\bremove_ideas\s*=\s*([A-Za-z0-9_]+)", scrub)
        )
        for idea_id in DORMANT_WRK_CRISIS_IDEAS:
            with self.subTest(scrubbed_idea=idea_id):
                self.assertEqual(scrubbed_ideas[idea_id], 1)

        worker_inheritance = _blocks(
            self.phase_effects, WORKER_REFORM_INHERIT_EFFECT
        )[0]
        self.assertEqual(
            worker_inheritance.count(f"{DORMANT_WRK_SCRUB_EFFECT} = yes"), 1
        )

        for winner_tag, formation_name in WRK_FORMATION_EFFECTS.items():
            with self.subTest(winner_tag=winner_tag):
                formation = _blocks(self.phase_effects, formation_name)[0]
                route_bridge = (
                    WORKER_REFORM_INHERIT_EFFECT
                    if winner_tag == "WKR"
                    else DORMANT_WRK_SCRUB_EFFECT
                )
                bridge_token = f"{route_bridge} = yes"
                annex_token = (
                    f"annex_country = {{ target = {winner_tag} transfer_troops = yes }}"
                )
                self.assertEqual(formation.count(bridge_token), 1)
                self.assertEqual(formation.count(annex_token), 1)
                self.assertLess(formation.index(bridge_token), formation.index(annex_token))

    def test_worker_formation_inherits_one_exact_stage_from_each_reform_chain(self) -> None:
        inheritance = _blocks(self.phase_effects, WORKER_REFORM_INHERIT_EFFECT)[0]
        self.assertEqual(len(_blocks(inheritance, "if")), 2)
        self.assertEqual(len(_blocks(inheritance, "else_if")), 4)
        inherited_ideas = Counter(
            re.findall(r"\badd_ideas\s*=\s*([A-Za-z0-9_]+)", inheritance)
        )
        self.assertEqual(inherited_ideas, Counter(WORKER_REFORM_STAGE_IDEAS))
        for idea_id in WORKER_REFORM_STAGE_IDEAS:
            with self.subTest(idea_id=idea_id):
                self.assertEqual(
                    inheritance.count(f"WKR = {{ has_idea = {idea_id} }}"), 1
                )

        formation = _blocks(
            self.phase_effects, WRK_FORMATION_EFFECTS["WKR"]
        )[0]
        self.assertLess(
            formation.index(f"{WORKER_REFORM_INHERIT_EFFECT} = yes"),
            formation.index("annex_country = { target = WKR transfer_troops = yes }"),
        )

    def test_wartime_routes_are_isolated_and_bounded(self) -> None:
        for tag, focus_ids in WARTIME_ROUTE_FOCUSES.items():
            for focus_id in focus_ids:
                with self.subTest(focus_id=focus_id):
                    block = self.blocks[focus_id]
                    self.assertEqual(_phase_flags(block), ACTIVE_PHASE_FLAGS)
                    self.assertIn(f"tag = {tag}", block)
                    for other in {"WKR", "VAD", "TVA"} - {tag}:
                        self.assertNotIn(f"tag = {other}", block)

    def test_alternate_wartime_paths_both_unlock_retreat_levies(self) -> None:
        for tag, hook in RETREAT_HOOKS.items():
            route = "\n".join(self.blocks[focus_id] for focus_id in WARTIME_ROUTE_FOCUSES[tag])
            self.assertEqual(route.count(f"set_country_flag = {hook}"), 2)
            capstone, central_hook = CENTRAL_CAPSTONES[tag]
            self.assertIn(f"set_country_flag = {central_hook}", self.blocks[capstone])

    def test_expanded_wartime_routes_converge_before_central_unlock(self) -> None:
        for tag, (convergence, capstone) in WARTIME_CONVERGENCE.items():
            with self.subTest(tag=tag):
                self.assertEqual(_prerequisites(self.blocks[capstone]), {convergence})

    def test_mutually_exclusive_wartime_paths_or_converge_in_one_block(self) -> None:
        convergence_tails = {
            "WKR_open_free_republics_channel": {
                "WKR_form_revolutionary_supply_commission",
                "WKR_train_shopfloor_officers",
            },
            "VAD_balance_council_and_command": {
                "VAD_dispatch_solland_liaison_mission",
                "VAD_standardize_district_logistics",
            },
            "TVA_publish_operational_metrics": {
                "TVA_issue_emergency_output_norms",
                "TVA_build_mobile_repair_trains",
            },
        }
        for focus_id, tails in convergence_tails.items():
            with self.subTest(focus_id=focus_id):
                prerequisite = _blocks(self.blocks[focus_id], "prerequisite")
                self.assertEqual(len(prerequisite), 1)
                self.assertEqual(_prerequisites(self.blocks[focus_id]), tails)

    def test_worx_engineering_programmes_remain_jointly_completable(self) -> None:
        for focus_id in (
            "TVA_reroute_city_grid",
            "TVA_deploy_field_laboratories",
            "TVA_raise_technical_battalions",
            "TVA_seal_the_approaches",
        ):
            with self.subTest(focus_id=focus_id):
                self.assertNotIn("mutually_exclusive", self.blocks[focus_id])

        for focus_id, (idea_id, days) in WORX_WARTIME_TIMED_IDEAS.items():
            with self.subTest(focus_id=focus_id):
                self.assertIn(
                    f"add_timed_idea = {{ idea = {idea_id} days = {days} }}",
                    self.blocks[focus_id],
                )
                self.assertEqual(len(_blocks(self.collapse_ideas, idea_id)), 1)

    def test_each_wartime_route_has_political_military_and_economic_rewards(self) -> None:
        reward_classes = (
            ("add_political_power", "add_stability"),
            ("army_experience", "add_command_power", "add_manpower", "add_war_support"),
            ("add_equipment_to_stockpile", "add_building_construction", "add_timed_idea"),
        )
        for tag, focus_ids in WARTIME_ROUTE_FOCUSES.items():
            source = "\n".join(self.blocks[focus_id] for focus_id in focus_ids)
            for tokens in reward_classes:
                with self.subTest(tag=tag, tokens=tokens):
                    self.assertTrue(any(token in source for token in tokens))

    def test_mobile_repair_train_focus_grants_a_concrete_timed_spirit(self) -> None:
        focus = self.blocks["TVA_build_mobile_repair_trains"]
        reward = f"add_timed_idea = {{ idea = {MOBILE_REPAIR_IDEA} days = 35 }}"
        self.assertEqual(focus.count(reward), 1)
        self.assertEqual(len(_blocks(self.collapse_ideas, MOBILE_REPAIR_IDEA)), 1)

    def test_focus_land_repair_spirits_do_not_use_ship_repair_modifier(self) -> None:
        for idea_id in LAND_REPAIR_IDEAS:
            with self.subTest(idea_id=idea_id):
                definitions = _blocks(self.collapse_ideas, idea_id)
                self.assertEqual(len(definitions), 1)
                self.assertEqual(
                    definitions[0].count("industry_repair_factor = 0.20"), 1
                )
                self.assertNotRegex(definitions[0], r"\brepair_speed_factor\s*=")

    def test_vad_sol_policy_is_wartime_hook_only(self) -> None:
        hook = "ADISCORD_vorkerland_focus_vad_sol_invitation_intent"
        focus = self.blocks["VAD_invite_sol_delegation"]
        self.assertEqual(_phase_flags(focus), ACTIVE_PHASE_FLAGS)
        self.assertIn(f"set_country_flag = {hook}", focus)
        self.assertEqual(self.source.count(f"set_country_flag = {hook}"), 1)
        for forbidden in ("declare_war_on", "create_wargoal", "puppet", "set_autonomy"):
            self.assertNotIn(forbidden, focus)

    def test_focuses_feed_visible_diplomacy_and_support_decisions(self) -> None:
        diplomacy = read(DIPLOMACY_DECISIONS_FILE)
        support = read(FOCUS_DECISIONS_FILE)
        for hook in (
            "ADISCORD_vorkerland_focus_vad_sol_invitation_intent",
            "ADISCORD_vorkerland_focus_wkr_vla_invitation_intent",
        ):
            self.assertIn(hook, self.source)
            self.assertIn(hook, diplomacy)
        for flag in (
            "ADISCORD_vorkerland_wkr_vla_alliance_accepted",
            "ADISCORD_vorkerland_vad_sol_alliance_accepted",
        ):
            self.assertIn(flag, support)

    def test_postwar_routes_need_phase_and_exact_route_flag(self) -> None:
        for route_flag, focus_ids in POSTWAR_ROUTE_FOCUSES.items():
            root = self.blocks[focus_ids[0]]
            self.assertEqual(_prerequisites(root), set())
            for focus_id in focus_ids:
                with self.subTest(focus_id=focus_id):
                    block = self.blocks[focus_id]
                    self.assertEqual(_phase_flags(block), {POSTWAR_PHASE})
                    self.assertIn("tag = WRK", block)
                    self.assertIn(f"has_country_flag = {route_flag}", block)
                    self.assertNotIn(f"focus = {FINAL_FOCUS}", block)

    def test_postwar_capstones_install_one_mutually_exclusive_lasting_settlement(self) -> None:
        for capstone_id, (settlement_idea, incompatible_ideas) in POSTWAR_SETTLEMENT_IDEAS.items():
            with self.subTest(capstone_id=capstone_id):
                capstone = self.blocks[capstone_id]
                self.assertEqual(capstone.count(f"add_ideas = {settlement_idea}"), 1)
                self.assertNotIn(f"remove_ideas = {settlement_idea}", capstone)
                for incompatible_idea in incompatible_ideas:
                    self.assertEqual(
                        capstone.count(f"remove_ideas = {incompatible_idea}"), 1
                    )

                definitions = _blocks(self.collapse_ideas, settlement_idea)
                self.assertEqual(len(definitions), 1)
                self.assertRegex(definitions[0], r"\bremoval_cost\s*=\s*-1\b")

    def test_worx_postwar_programmes_build_and_consolidate_real_institutions(self) -> None:
        capstone = self.blocks["WRK_utilitarian_build_measurable_republic"]
        for focus_id, idea_id in WORX_POSTWAR_PROVISIONAL_IDEAS.items():
            with self.subTest(focus_id=focus_id):
                self.assertIn(f"add_ideas = {idea_id}", self.blocks[focus_id])
                self.assertIn(f"remove_ideas = {idea_id}", capstone)
                idea = _blocks(self.collapse_ideas, idea_id)
                self.assertEqual(len(idea), 1)
                self.assertIn("removal_cost = -1", idea[0])

        route = "\n".join(
            self.blocks[focus_id]
            for focus_id in POSTWAR_ROUTE_FOCUSES[
                "ADISCORD_vorkerland_route_utilitarian"
            ]
        )
        bonuses = _blocks(route, "add_tech_bonus")
        self.assertEqual(len(bonuses), 2)
        categories = {
            re.search(r"\bcategory\s*=\s*([A-Za-z0-9_]+)", bonus).group(1)
            for bonus in bonuses
        }
        self.assertEqual(categories, {"industry", "electronics"})

    def test_dorian_worx_is_the_existing_technocrat_with_authored_portrait(self) -> None:
        definitions = _blocks(read(CHARACTER_FILE), "TVA_Dorian_Worx")
        self.assertEqual(len(definitions), 1)
        worx = definitions[0]
        self.assertIn("ideology = technocracy_ideology", worx)
        self.assertIn("large = GFX_portrait_WRK_Dorian_Worx", worx)

        english = localisation_entries(read(ENGLISH_LOCALISATION))
        russian = localisation_entries(read(RUSSIAN_LOCALISATION))
        self.assertIn(
            "Technical Directorate", english["TVA_codify_utilitarian_directorate"]
        )
        self.assertIn(
            "Technocratic Republic",
            english["WRK_utilitarian_build_measurable_republic"],
        )
        self.assertIn(
            "техническую директорию",
            russian["TVA_codify_utilitarian_directorate"],
        )
        self.assertIn(
            "технократическую республику",
            russian["WRK_utilitarian_build_measurable_republic"],
        )

    def test_focus_tooltip_references_have_exact_bilingual_keys(self) -> None:
        references = set(
            re.findall(
                r"\b(?:custom_effect_tooltip|tooltip)\s*=\s*([A-Za-z0-9_]+)",
                self.source,
            )
        )
        for localisation in (ENGLISH_LOCALISATION, RUSSIAN_LOCALISATION):
            with self.subTest(localisation=localisation):
                entries = localisation_entries(read(localisation))
                self.assertEqual(references - set(entries), set())

    def test_vorkerland_idea_localisation_and_ivanland_expedition_exist(self) -> None:
        expected_keys = {
            key
            for idea_id in POSTWAR_IDEA_LOCALISATION_IDS
            for key in (idea_id, f"{idea_id}_desc")
        }
        for localisation in (
            ENGLISH_POSTWAR_IDEA_LOCALISATION,
            RUSSIAN_POSTWAR_IDEA_LOCALISATION,
        ):
            with self.subTest(localisation=localisation):
                self.assertEqual(
                    set(localisation_entries(read(localisation))), expected_keys
                )

        definitions = _blocks(self.collapse_ideas, IVANLAND_EXPEDITIONARY_IDEA)
        self.assertEqual(len(definitions), 1)
        for token in (
            "army_attack_factor = 0.08",
            "army_org_regain = 0.08",
            "planning_speed = 0.10",
            "supply_consumption_factor = -0.08",
        ):
            self.assertIn(token, definitions[0])

    def test_each_postwar_route_unlocks_public_core_packages(self) -> None:
        hook = "ADISCORD_vorkerland_focus_postwar_core_decisions_unlocked"
        postwar = "\n".join(
            self.blocks[focus_id]
            for focus_ids in POSTWAR_ROUTE_FOCUSES.values()
            for focus_id in focus_ids
        )
        self.assertEqual(postwar.count(f"set_country_flag = {hook}"), 3)
        decisions = read(FOCUS_DECISIONS_FILE)
        for decision_id in CORE_DECISIONS:
            with self.subTest(decision_id=decision_id):
                start = decisions.index(f"\t{decision_id} = {{")
                next_block = decisions.find("\n\tADISCORD_", start + 1)
                block = decisions[start : next_block if next_block != -1 else len(decisions)]
                self.assertIn(f"has_country_flag = {hook}", block)

    def test_showdown_focus_cannot_own_the_war_or_outcome(self) -> None:
        final = self.blocks[FINAL_FOCUS]
        self.assertEqual(_phase_flags(final), {"ADISCORD_vorkerland_phase_central_showdown"})
        self.assertIn("focus = ADISCORD_vorkerland_prepare_central_front", final)
        for token in (
            "declare_war_on",
            "start_civil_war",
            "create_wargoal",
            "annex_country",
            "set_global_flag",
            "country_event",
        ):
            self.assertNotIn(token, self.source)
        for token in ("every_country", "random_country", "on_monthly", "monthly_pulse", "Lucas", "lucas"):
            self.assertNotIn(token, self.source)

    def test_central_front_keeps_or_arrows_and_requires_the_current_claimant_hook(self) -> None:
        prepare = self.blocks["ADISCORD_vorkerland_prepare_central_front"]
        hooks = {
            "WKR": ("WKR_republic_fights_as_one", "ADISCORD_vorkerland_focus_wkr_central_war_unlocked"),
            "VAD": ("VAD_assemble_joint_general_staff", "ADISCORD_vorkerland_focus_vad_central_war_unlocked"),
            "TVA": ("TVA_close_operational_loop", "ADISCORD_vorkerland_focus_tva_central_war_unlocked"),
        }
        for tag, (capstone, hook) in hooks.items():
            with self.subTest(tag=tag):
                self.assertIn(f"AND = {{ tag = {tag} has_country_flag = {hook} }}", prepare)
                self.assertIn(f"set_country_flag = {hook}", self.blocks[capstone])
                self.assertEqual(prepare.count(f"focus = {capstone}"), 1)
        prerequisite = _blocks(prepare, "prerequisite")
        self.assertEqual(len(prerequisite), 1)
        for capstone, _hook in hooks.values():
            self.assertIn(f"focus = {capstone}", prerequisite[0])
        for payload in (
            "add_command_power = 10",
            "add_war_support = 0.02",
            "army_experience = 5",
            "type = support_equipment amount = 75",
        ):
            self.assertIn(payload, prepare)
        self.assertEqual(
            prepare.count(f"set_country_flag = {CENTRAL_PREPARED_FLAG}"), 1
        )
        self.assertEqual(
            prepare.count(f"custom_effect_tooltip = {CENTRAL_PREPARED_TOOLTIP}"), 1
        )

    def test_fortification_is_one_minor_redoubt_per_claimant(self) -> None:
        fortify = self.blocks["ADISCORD_vorkerland_fortify_home_region"]
        self.assertEqual(fortify.count("add_command_power = 5"), 1)
        self.assertEqual(fortify.count("type = bunker level = 1"), 3)
        for tag, state, province in (("WKR", 32, 6713), ("VAD", 75, 6192), ("TVA", 36, 12227)):
            self.assertIn(f"limit = {{ tag = {tag} controls_state = {state} }}", fortify)
            self.assertIn(f"province = {province}", fortify)

    def test_every_focus_icon_has_an_explicit_shine_sprite(self) -> None:
        shine = read(SHINE_FILE)
        for focus_id, block in self.blocks.items():
            icon_line = next(line.strip() for line in block.splitlines() if line.strip().startswith("icon = "))
            icon = icon_line.split("=", maxsplit=1)[1].strip()
            with self.subTest(focus_id=focus_id, icon=icon):
                self.assertIn(f'name = "{icon}_shine"', shine)

    def test_route_signature_focuses_have_distinct_icons(self) -> None:
        expected = {
            "WKR_republic_fights_as_one": "GFX_goal_generic_allies_build_infantry",
            "VAD_proclaim_joint_charter": "GFX_goal_generic_military_sphere",
            "TVA_codify_utilitarian_directorate": "GFX_goal_generic_production",
            "TVA_close_operational_loop": "GFX_goal_generic_scientific_exchange",
            "ADISCORD_vorkerland_prepare_central_front": "GFX_goal_generic_construct_infrastructure",
            "WRK_joint_impose_reunification_settlement": "GFX_goal_generic_political_pressure",
            "WRK_utilitarian_build_measurable_republic": "GFX_goal_generic_production",
        }
        for focus_id, expected_icon in expected.items():
            icon_line = next(
                line.strip()
                for line in self.blocks[focus_id].splitlines()
                if line.strip().startswith("icon = ")
            )
            with self.subTest(focus_id=focus_id):
                self.assertEqual(icon_line, f"icon = {expected_icon}")

    def test_russian_localisation_keeps_utf8_bom(self) -> None:
        self.assertTrue((ROOT / RUSSIAN_LOCALISATION).read_bytes().startswith(b"\xef\xbb\xbf"))


if __name__ == "__main__":
    unittest.main()
