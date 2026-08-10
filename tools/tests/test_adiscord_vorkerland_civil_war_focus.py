from __future__ import annotations

import unittest

from tools.validators.validate_adiscord_vorkerland_civil_war_focus import (
    ACTIVE_PHASE_FLAGS,
    CENTRAL_CAPSTONES,
    CORE_DECISIONS,
    DIPLOMACY_DECISIONS_FILE,
    FINAL_FOCUS,
    FOCUS_DECISIONS_FILE,
    FOCUS_FILE,
    FOCUS_IDS,
    POSTWAR_PHASE,
    POSTWAR_ROUTE_FOCUSES,
    PREWAR_PHASE,
    PREWAR_VAD_FOCUSES,
    PREWAR_WRK_FOCUSES,
    RETREAT_HOOKS,
    ROOT,
    RUSSIAN_LOCALISATION,
    SHINE_FILE,
    SHARED_WARTIME_FOCUSES,
    WARTIME_ROUTE_FOCUSES,
    WARTIME_CONVERGENCE,
    _phase_flags,
    _prerequisites,
    collect_issues,
    focus_blocks,
    read,
)


class VorkerlandLifecycleFocusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = read(FOCUS_FILE)
        cls.blocks = focus_blocks(cls.source)

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

    def test_fortification_is_one_minor_redoubt_per_claimant(self) -> None:
        fortify = self.blocks["ADISCORD_vorkerland_fortify_home_region"]
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

    def test_russian_localisation_keeps_utf8_bom(self) -> None:
        self.assertTrue((ROOT / RUSSIAN_LOCALISATION).read_bytes().startswith(b"\xef\xbb\xbf"))


if __name__ == "__main__":
    unittest.main()
