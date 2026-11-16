"""Regression contract for Kefreyt's first defeat and the council's separate revanche."""

from pathlib import Path
from tools.lib.focus_sources import read_focus_source
import unittest

ROOT = Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    return read_focus_source(ROOT / path, encoding="utf-8-sig")


class StelanderDominionTests(unittest.TestCase):
    def evaluate(self, states, facts):
        from tools.tests.test_adiscord_stp_preparation import matches_conditions
        from tools.validators.validate_adiscord_division_templates import (
            parse_clausewitz,
        )

        body = next(
            e.value
            for e in parse_clausewitz(
                read("common/scripted_triggers/ADISCORD_VAL_rework_triggers.txt")
            )
            if e.key == "VAL_stelander_dominated"
        )
        visits = 0

        def evaluate(items, scope="VAL"):
            def match(entry):
                nonlocal visits
                key, value = entry.key, entry.value
                if key in ("any_state", "any_core_state"):
                    for state in states:
                        if key == "any_core_state" and not facts.get(
                            (state, "is_core_of", scope), False
                        ):
                            continue
                        visits += 1
                        if evaluate(value, state):
                            return True
                    return False
                if key == "NOT":
                    return not any(evaluate([e], scope) for e in value)
                if key == "OR":
                    return any(evaluate([e], scope) for e in value)
                if key == "AND":
                    return evaluate(value, scope)
                if key in ("STP", "STS", "SRP", "VAL"):
                    return evaluate(value, key)
                return matches_conditions([entry], facts, scope)

            return all(match(e) for e in items)

        return evaluate(body), visits

    def test_only_current_cores_are_visited_even_after_stp_disappears(self):
        facts = {
            ("STP", "exists", "no"): True,
            ("STS", "exists", "no"): True,
            ("999", "is_core_of", "STP"): True,
            ("999", "is_owned_by", "VAL"): True,
            ("999", "is_controlled_by", "VAL"): True,
        }
        result, visits = self.evaluate([str(i) for i in range(1, 1000)], facts)
        self.assertTrue(result)
        self.assertEqual(
            visits, 2, "Only the dynamically added core belongs in either scan"
        )
        facts["999", "is_core_of", "STP"] = False
        self.assertFalse(
            self.evaluate(["999"], facts)[0], "An empty core set is not victory"
        )

    def test_ownership_control_subjects_and_republic_exception(self):
        base = {
            ("STP", "exists", "no"): True,
            ("STS", "is_subject_of", "VAL"): True,
            ("1", "is_core_of", "STP"): True,
        }
        for owner, controller, subject, expected in (
            ("VAL", "VAL", False, True),
            ("VAL", "NOD", False, False),
            ("NKA", "NKA", True, True),
            ("NKA", "NOD", True, False),
            # A capitulated administration can stay occupied by its overlord.
            ("NKA", "VAL", True, True),
            ("VAL", "NKA", True, True),
            ("NKA", "VAL", False, False),
        ):
            facts = {
                **base,
                ("1", "owner"): owner,
                ("1", "controller"): controller,
                ("1", "is_owned_by", owner): True,
                ("1", "is_controlled_by", controller): True,
                ("NKA", "is_subject_of", "VAL"): subject,
            }
            with self.subTest(owner=owner, controller=controller):
                self.assertEqual(self.evaluate(["1"], facts)[0], expected)
        for state, war, expected in (
            ("29", False, True),
            ("29", True, False),
            ("1", False, False),
        ):
            facts = {
                **base,
                (state, "is_core_of", "STP"): True,
                (state, "is_core_of", "SRP"): True,
                (state, "is_owned_by", "SRP"): True,
                (state, "is_controlled_by", "SRP"): True,
                ("SRP", "is_subject", "no"): True,
                ("SRP", "has_war_with", "VAL"): war,
            }
            with self.subTest(state=state, war=war):
                self.assertEqual(self.evaluate([state], facts)[0], expected)
        self.assertFalse(
            self.evaluate(["1"], {**base, ("STS", "is_subject_of", "VAL"): False})[0]
        )


class ValStelanderDefeatTests(unittest.TestCase):
    def test_defeat_transition_replaces_solgalov_and_tree(self):
        effects = read("common/scripted_effects/ADISCORD_VAL_effects.txt")
        start = effects.index("VAL_enter_stelander_defeat = {")
        body = effects[start : start + 6000]
        for token in (
            "set_country_flag = VAL_stelander_defeated",
            "set_country_flag = VAL_cw_defeated",
            "set_country_flag = VAL_cw_settled",
            "retire_character = VAL_Valera_Solgalov",
            "has_character = VAL_Commanders_Council",
            "promote_character = { character = VAL_Commanders_Council ideology = contractual_etatism }",
            "load_focus_tree = { tree = VAL_defeated_focus keep_completed = no }",
            "mark_focus_tree_layout_dirty = yes",
        ):
            self.assertIn(token, body)

    def test_shabrat_victory_enters_defeat_state_before_white_peace(self):
        from tools.tests.test_adiscord_stp_hegemony_expansion import named_block

        effects = read("common/scripted_effects/ADISCORD_STP_scripted_effects.txt")
        settlement = named_block(effects, "STP_pc_begin_settlement")
        self.assertIn("STP_pc_settle_val_northern_conquests = yes", settlement)
        branch = named_block(effects, "STP_pc_settle_val_northern_conquests")
        self.assertLess(
            branch.index("VAL = { VAL_enter_stelander_defeat = yes }"),
            branch.index("white_peace = VAL"),
        )
        self.assertLess(
            branch.index("array = STP_pc_val_northern_subjects"),
            branch.index("VAL = { VAL_enter_stelander_defeat = yes }"),
        )

    def test_defeated_kefreyt_cannot_reopen_old_campaigns(self):
        triggers = (
            read("common/scripted_triggers/ADISCORD_STP_scripted_triggers.txt")
            + "\n"
            + read("common/scripted_triggers/ADISCORD_VAL_rework_triggers.txt")
        )
        self.assertGreaterEqual(
            triggers.count("NOT = { has_country_flag = VAL_stelander_defeated }"), 3
        )
        decisions = read("common/decisions/ADISCORD_VAL_decisions.txt")
        for decision in (
            "VAL_campaign_against_stelander",
            "VAL_campaign_against_nod",
            "VAL_cw_begin_mobilization",
        ):
            pos = decisions.index(decision + " = {")
            body = decisions[pos : pos + 2600]
            self.assertIn("VAL_stelander_defeated", body)

    def test_council_revanche_is_separate_from_old_campaigns(self):
        from tools.tests.test_adiscord_stp_preparation import entries, scalar, block

        trees = entries(
            "common/national_focus/ADISCORD_national_focus_VAL_defeated.txt"
        )
        tree = next(
            e.value
            for e in trees
            if e.key == "focus_tree" and scalar(e.value, "id") == "VAL_defeated_focus"
        )
        focuses = {scalar(e.value, "id"): e.value for e in tree if e.key == "focus"}
        self.assertIn("VAL_defeat_Revise_The_Settlement", focuses)
        peace = focuses["VAL_defeat_No_Second_Expedition"]
        revenge = focuses["VAL_defeat_Revise_The_Settlement"]
        self.assertEqual(
            scalar(block(peace, "mutually_exclusive"), "focus"),
            "VAL_defeat_Revise_The_Settlement",
        )
        self.assertEqual(
            scalar(block(revenge, "mutually_exclusive"), "focus"),
            "VAL_defeat_No_Second_Expedition",
        )
        final = focuses["VAL_defeat_Return_To_The_Passes"]
        self.assertIn("VAL_council_begin_revanche", str(final))
        self.assertIn("VAL_council_can_launch_revanche", str(block(final, "available")))
        text = read("common/national_focus/ADISCORD_national_focus_VAL_defeated.txt")
        for old in (
            "VAL_campaign_against_stelander",
            "VAL_campaign_against_nod",
            "VAL_cw_begin_mobilization",
        ):
            self.assertNotIn(old, text)

    def test_revanche_requires_post_defeat_council_and_living_shabrat(self):
        from tools.tests.test_adiscord_stp_preparation import (
            entries,
            block,
            matches_conditions,
        )
        from itertools import product

        triggers = entries("common/scripted_triggers/ADISCORD_VAL_rework_triggers.txt")
        gate = block(triggers, "VAL_council_can_prepare_revanche")
        for (defeated, shabrat, subject, target_exists), leader in product(
            product((False, True), repeat=4),
            ("VAL_Commanders_Council", "VAL_Eduard_Korsch", "VAL_Valera_Solgalov"),
        ):
            # The revanchist coup replaces the Council; both govern the revanche.
            council = leader != "VAL_Valera_Solgalov"
            facts = {
                ("VAL", "has_country_flag", "VAL_stelander_defeated"): defeated,
                ("VAL", "ruling_leader"): leader,
                ("VAL", "is_subject", "yes"): subject,
                ("VAL", "has_capitulated", "yes"): False,
                ("STS", "exists", "yes"): target_exists,
                ("STS", "STP_pc_founder_rules", "yes"): shabrat,
                ("STS", "has_capitulated", "yes"): False,
                ("STS", "is_subject", "yes"): False,
            }
            self.assertEqual(
                matches_conditions(gate, facts, "VAL"),
                defeated and council and shabrat and not subject and target_exists,
            )

    def test_war_entry_marks_the_current_revanche_before_declaring(self):
        from tools.tests.test_adiscord_stp_preparation import (
            entries,
            block,
            walk,
            scalar,
        )

        effects = entries("common/scripted_effects/ADISCORD_VAL_effects.txt")
        body = block(effects, "VAL_council_begin_revanche")
        ordered = list(walk(body))
        marker = next(
            i
            for i, e in enumerate(ordered)
            if e.key == "set_country_flag" and e.value == "VAL_council_revanche_active"
        )
        war = next(i for i, e in enumerate(ordered) if e.key == "declare_war_on")
        self.assertLess(marker, war)
        self.assertEqual(scalar(ordered[war].value, "target"), "STS")
        self.assertNotIn(
            "clr_country_flag = VAL_stelander_defeated",
            read("common/scripted_effects/ADISCORD_VAL_effects.txt"),
        )

    def test_first_defeat_and_revanche_select_different_settlements(self):
        from tools.tests.test_adiscord_stp_preparation import (
            entries,
            block,
            selected_effects,
        )

        body = block(
            entries("common/scripted_effects/ADISCORD_STP_scripted_effects.txt"),
            "STP_pc_begin_settlement",
        )
        for revanche in (False, True):
            facts = {
                ("STS", "variable", "STP_pc_cap_side"): 1,
                ("VAL", "has_country_flag", "VAL_council_revanche_active"): revanche,
                ("STS", "has_war_with", "VAL"): True,
            }
            effects = list(selected_effects(body, facts, "STS"))
            self.assertEqual(
                any(e.key == "STP_pc_annex_defeated_council" for _, e in effects),
                revanche,
            )
            self.assertEqual(
                any(e.key == "STP_pc_settle_val_northern_conquests" for _, e in effects),
                not revanche,
            )

    def test_revanche_defeat_annexes_val_without_making_foreign_states_core(self):
        from tools.tests.test_adiscord_stp_preparation import (
            entries,
            block,
            walk,
            scalar,
        )

        effects = entries("common/scripted_effects/ADISCORD_STP_scripted_effects.txt")
        body = block(effects, "STP_pc_annex_defeated_council")
        all_nodes = list(walk(body))
        annex = next(e for e in all_nodes if e.key == "annex_country")
        self.assertEqual(scalar(annex.value, "target"), "VAL")
        self.assertEqual(scalar(annex.value, "transfer_troops"), "no")
        self.assertNotIn("add_core_of", {e.key for e in all_nodes})
        self.assertIn("VAL_council_revanche_active", str(body))
        self.assertNotIn("VAL_enter_stelander_defeat", {e.key for e in all_nodes})

    def test_external_peace_clears_revanche_without_reopening_old_routes(self):
        from tools.tests.test_adiscord_stp_preparation import (
            entries,
            block,
            selected_effects,
        )

        body = block(
            entries("common/scripted_effects/ADISCORD_VAL_effects.txt"),
            "VAL_council_reconcile_revanche",
        )
        for war in (False, True):
            facts = {
                ("VAL", "has_country_flag", "VAL_council_revanche_active"): True,
                ("VAL", "has_war_with", "STS"): war,
            }
            selected = list(selected_effects(body, facts, "VAL"))
            self.assertEqual(
                any(
                    e.key == "clr_country_flag"
                    and e.value == "VAL_council_revanche_active"
                    for _, e in selected
                ),
                not war,
            )
        hooks = read("common/on_actions/09_ADISCORD_scripted_peace_on_actions.txt")
        self.assertIn(
            "VAL_council_reconcile_revanche = yes", hooks[hooks.index("on_peace = {") :]
        )

    def test_kefreyt_victory_closes_competing_nod_ultimatum(self):
        from tools.validators.validate_adiscord_vorkerland_collapse import named_block

        effects = read("common/scripted_effects/ADISCORD_VAL_effects.txt")
        install = named_block(effects, "VAL_install_stelander_administration")
        self.assertIn("STP_close_competing_ultimatum_wars_after_defeat = yes", install)
        self.assertLess(
            install.index("STP_close_competing_ultimatum_wars_after_defeat = yes"),
            install.index("set_autonomy"),
        )

    def test_new_administration_regains_land_held_by_kefreyt_side(self):
        from tools.validators.validate_adiscord_vorkerland_collapse import named_block

        effects = read("common/scripted_effects/ADISCORD_VAL_effects.txt")
        install = named_block(effects, "VAL_install_stelander_administration")
        self.assertLess(
            install.index("set_autonomy"),
            install.index("VAL_restore_administration_control = yes"),
        )
        restore = named_block(effects, "VAL_restore_administration_control")
        self.assertIn("NOT = { is_controlled_by = PREV }", restore)
        self.assertRegex(
            restore,
            r"controller = \{\s*OR = \{\s*tag = VAL\s*is_subject_of = VAL\s*\}\s*\}",
        )
        self.assertIn("set_state_controller_to = PREV", restore)

    def test_commanders_council_is_recruited_and_localised(self):
        chars = read("common/characters/VAL.txt")
        history = read("history/countries/VAL - ValeraLand.txt")
        ru = read("localisation/russian/nsb_characters_l_russian.yml")
        en = read("localisation/english/nsb_characters_l_english.yml")
        self.assertIn("VAL_Commanders_Council = {", chars)
        self.assertIn("recruit_character = VAL_Commanders_Council", history)
        self.assertIn('VAL_Commanders_Council: "Совет командиров"', ru)
        self.assertIn('VAL_Commanders_Council: "Council of Commanders"', en)


class ValPartyProtectorateRevancheTests(unittest.TestCase):
    """The Party's postwar victory leaves a Council protectorate with its own revanche."""

    def named(self, path, name):
        from tools.validators.validate_adiscord_vorkerland_collapse import named_block

        return named_block(read(path), name)

    def test_party_victory_enters_the_council_defeat_after_the_victory_flag(self):
        body = self.named(
            "common/scripted_effects/ADISCORD_STP_scripted_effects.txt",
            "STP_pw_party_finalize_kefreyt_subject",
        )
        self.assertLess(body.index("puppet = {"), body.index("VAL_enter_stelander_defeat = yes"))
        self.assertLess(
            body.index("set_country_flag = STP_pw_party_kefreyt_victory"),
            body.index("VAL_enter_stelander_defeat = yes"),
        )

    def test_protectorate_opens_the_council_tree_and_revanche_gates(self):
        path = "common/scripted_triggers/ADISCORD_VAL_rework_triggers.txt"
        route = self.named(path, "VAL_council_party_route")
        self.assertIn("has_country_flag = STP_pw_party_kefreyt_victory", route)
        protectorate = self.named(path, "VAL_council_party_protectorate")
        self.assertIn("is_subject_of = STP", protectorate)
        self.assertIn(
            "VAL_council_party_protectorate = yes",
            self.named(path, "VAL_council_can_prepare_revanche"),
        )
        self.assertIn(
            "VAL_council_party_protectorate = yes",
            self.named(path, "VAL_council_in_office"),
        )
        launch = self.named(path, "VAL_council_can_launch_revanche")
        for token in (
            "has_completed_focus = VAL_defeat_Double_Ledgers",
            "has_completed_focus = VAL_defeat_Wait_For_The_March",
            "NOT = { has_war_with = STP }",
            "STP_pw_party_northern_march_target = yes",
        ):
            self.assertIn(token, launch)

    def test_party_only_focuses_follow_the_revanche_choice(self):
        tree = read("focus_trees/VAL/defeated/focuses.txt")
        for focus_id, parent in (
            ("VAL_defeat_Double_Ledgers", "VAL_defeat_Revise_The_Settlement"),
            ("VAL_defeat_Wait_For_The_March", "VAL_defeat_Double_Ledgers"),
        ):
            with self.subTest(focus=focus_id):
                start = tree.index(f"id = {focus_id}")
                body = tree[start : tree.index("ai_will_do", start)]
                self.assertIn("allow_branch = { VAL_council_party_route = yes }", body)
                self.assertIn(f"prerequisite = {{ focus = {parent} }}", body)
        start = tree.index("id = VAL_defeat_Double_Ledgers")
        self.assertIn(
            "unlock_decision_tooltip = VAL_council_hidden_depot",
            tree[start : tree.index("ai_will_do", start)],
        )

    def test_break_releases_kefreyt_before_declaring_on_the_party(self):
        body = self.named(
            "common/scripted_effects/ADISCORD_VAL_effects.txt",
            "VAL_council_break_party_protectorate",
        )
        ordered = [
            "set_country_flag = VAL_council_revanche_active",
            "autonomy_state = autonomy_free",
            "white_peace = VAL",
            "VAL_council_deliver_hidden_depots = yes",
            "declare_war_on = { target = STP type = annex_everything }",
            "country_event = { id = ADISCORD_STP_pc.120 }",
        ]
        positions = [body.index(token) for token in ordered]
        self.assertEqual(positions, sorted(positions))
        begin = self.named(
            "common/scripted_effects/ADISCORD_VAL_effects.txt",
            "VAL_council_begin_revanche",
        )
        self.assertLess(
            begin.index("declare_war_on = { target = STS"),
            begin.index("VAL_council_break_party_protectorate = yes"),
        )

    def test_revanche_war_has_symmetric_terminal_settlements(self):
        hooks = read("common/on_actions/09_ADISCORD_scripted_peace_on_actions.txt")
        annex = hooks.index("STP = { STP_pc_annex_defeated_council = yes }")
        treaty = hooks.index("STP = { STP_pw_party_settle_kefreyt_victory = yes }")
        victory = hooks.index("VAL = { VAL_council_settle_party_revanche_victory = yes }")
        march = hooks.index("STP = { STP_pw_party_settle_northern_march_defeat = yes }")
        self.assertLess(annex, treaty)
        self.assertLess(treaty, victory)
        self.assertLess(victory, march)
        self.assertIn(
            "OR = { tag = STS tag = STP }",
            self.named(
                "common/scripted_effects/ADISCORD_STP_scripted_effects.txt",
                "STP_pc_annex_defeated_council",
            ),
        )
        settle = self.named(
            "common/scripted_effects/ADISCORD_VAL_effects.txt",
            "VAL_council_settle_party_revanche_victory",
        )
        self.assertIn("VAL_install_stelander_administration = yes", settle)
        self.assertIn("clr_country_flag = VAL_council_revanche_active", settle)
        reconcile = self.named(
            "common/scripted_effects/ADISCORD_VAL_effects.txt",
            "VAL_council_reconcile_revanche",
        )
        self.assertIn("NOT = { has_war_with = STP }", reconcile)

    def test_revanche_choice_schedules_the_chauvinist_coup_and_world_news(self):
        tree = read("focus_trees/VAL/defeated/focuses.txt")
        start = tree.index("id = VAL_defeat_Revise_The_Settlement")
        body = tree[start : tree.index("ai_will_do", start)]
        self.assertIn("country_event = { id = val_council.42 days = 90 }", body)
        self.assertIn("custom_effect_tooltip = VAL_council_revanchist_coup_tt", body)
        coup = self.named(
            "common/scripted_effects/ADISCORD_VAL_effects.txt",
            "VAL_council_revanchist_coup",
        )
        for token in (
            "VAL_council_revanchist_coup_current = yes",
            "character = VAL_Eduard_Korsch",
            "promote_leader = yes",
            "ideology = chauvinism_ideology",
            "ruling_party = chauvinism",
            "news_event = { id = val_council.43 days = 1 }",
        ):
            self.assertIn(token, coup)
        events = read("events/ADISCORD_VAL_contract_events.txt")
        country = events[events.index("id = val_council.42") :]
        self.assertIn("immediate = { VAL_council_revanchist_coup = yes }", country[:600])
        news = events[events.index("id = val_council.43") :]
        self.assertIn("major = yes", news[:300])
        triggers = "common/scripted_triggers/ADISCORD_VAL_rework_triggers.txt"
        for name in ("VAL_council_can_prepare_revanche", "VAL_council_defeat_government"):
            self.assertIn("character = VAL_Eduard_Korsch", self.named(triggers, name))
        self.assertIn("VAL_council_defeat_government = yes", self.named(triggers, "VAL_council_in_office"))
        characters = read("common/characters/VAL.txt")
        korsch = characters[characters.index("VAL_Eduard_Korsch = {") :][:400]
        self.assertIn("large = GFX_portrait_VAL_Eduard_Korsch", korsch)
        self.assertNotIn("country_leader", korsch[: korsch.index("\n\t}")])
        self.assertIn(
            "recruit_character = VAL_Eduard_Korsch",
            read("history/countries/VAL - ValeraLand.txt"),
        )
        self.assertIn(
            'texturefile = "gfx/leaders/VAL/portrait_VAL_Eduard_Korsch.png"',
            read("interface/ADISCORD_leader_portraits.gfx"),
        )
        self.assertTrue((ROOT / "gfx/leaders/VAL/portrait_VAL_Eduard_Korsch.png").is_file())

    def test_party_campaign_opens_from_the_army_branch(self):
        tree = read("focus_trees/STP/postwar/party/focuses.txt")
        start = tree.index("id = STP_pw_party_kefreyt_campaign")
        body = tree[start : tree.index("completion_reward", start)]
        self.assertIn("prerequisite = { focus = STP_pw_party_border_staff }", body)
        self.assertNotIn("STP_pw_party_external_mandate", body)

    def test_new_text_and_event_ids_exist(self):
        import json
        import re

        keys = {
            "ADISCORD_VAL_decisions": (
                "VAL_defeat_Double_Ledgers",
                "VAL_defeat_Double_Ledgers_desc",
                "VAL_defeat_Wait_For_The_March",
                "VAL_defeat_Wait_For_The_March_desc",
                "VAL_council_protectorate_category",
                "VAL_council_hidden_depot",
                "VAL_council_hidden_depot_desc",
                "VAL_council_hidden_depot_effect_tt",
                "VAL_council_march_window",
                "VAL_council_party_revanche_stakes_tt",
                "VAL_council_party_revanche_war_tt",
                "val_council.41.d",
                "VAL_council_revanchist_coup_tt",
                "val_council.42.d",
                "val_council.43.d",
            ),
            "nsb_characters": ("VAL_Eduard_Korsch",),
            "ADISCORD_STP": (
                "STP_pw_party_council_revanche_title",
                "STP_pw_party_council_revanche_desc",
                "STP_pw_party_council_revanche_stakes_tt",
            ),
        }
        for stem, names in keys.items():
            for lang in ("russian", "english"):
                text = read(f"localisation/{lang}/{stem}_l_{lang}.yml")
                for key in names:
                    with self.subTest(lang=lang, key=key):
                        self.assertEqual(
                            len(re.findall(r"^\s+" + re.escape(key) + r":\d* \"", text, re.M)),
                            1,
                        )
        registry = json.loads(read("tools/data/adiscord_event_ids.json"))
        registered = {entry["id"] for entry in registry["events"]}
        self.assertTrue(
            {"val_council.41", "val_council.42", "val_council.43", "ADISCORD_STP_pc.120"}
            <= registered
        )


if __name__ == "__main__":
    unittest.main()
