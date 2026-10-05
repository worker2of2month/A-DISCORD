"""Static contracts of the western final war between Vorkerland and Itora.

The checks cover script wiring only: side lists, terminal cleanup, flag order,
path focuses and the Itoran focus aggregate. Engine war, faction and peace
behaviour needs a game run.
"""

from pathlib import Path
import json
import re
import unittest

from tools.tests.test_adiscord_south_final_war import body, flatten, focus_blocks, scope_calls
from tools.tests.test_adiscord_stp_preparation import block
from tools.validators.validate_adiscord_division_templates import parse_clausewitz

ROOT = Path(__file__).resolve().parents[2]
EFFECTS = ROOT / "common/scripted_effects/ADISCORD_west_final_war_effects.txt"
TRIGGERS = ROOT / "common/scripted_triggers/ADISCORD_west_final_war_triggers.txt"
EVENTS = ROOT / "events/ADISCORD_west_final_war_events.txt"
PEACE = ROOT / "common/on_actions/09_ADISCORD_scripted_peace_on_actions.txt"
IVN_TREE = ROOT / "focus_trees/IVN/main/focuses.txt"
WRK_TREE = ROOT / "focus_trees/Vorkerland/civil_war/focuses.txt"
REGIONAL = ("WIT", "IIA", "IBA", "IBL", "PWR", "PSD", "ZAO", "WPA", "WPS", "ROM", "TRU")
CHAMPIONS = ("WRK", "IVN")
ROUTES = ("worker", "joint", "utilitarian")
KEY_STATES = {"25", "92", "95", "96", "90", "91", "93", "94"}


class WestFinalWarContractTests(unittest.TestCase):
    def test_every_regional_state_is_bound_offered_and_settled(self):
        for name in (
            "ADISCORD_west_assign_bound_sides",
            "ADISCORD_west_offer_side_choices",
            "ADISCORD_west_faction_partners_follow",
        ):
            calls = set(re.findall(r"\b([A-Z]{3}) = \{", body(EFFECTS, name)))
            self.assertEqual(calls, set(REGIONAL), name)
        for name, effect in (
            ("ADISCORD_west_mark_losers", "ADISCORD_west_mark_loser"),
            ("ADISCORD_west_clear_participants", "ADISCORD_west_clear_participant"),
            ("ADISCORD_west_apply_settlement", "ADISCORD_west_settle_member"),
        ):
            self.assertEqual(scope_calls(body(EFFECTS, name), effect), set(REGIONAL) | set(CHAMPIONS), name)
        # WRK is the enemy every Itoran participant makes peace with.
        self.assertEqual(
            scope_calls(body(EFFECTS, "ADISCORD_west_end_final_wars"), "ADISCORD_west_end_member_wars"),
            set(REGIONAL) | {"IVN"},
        )
        regional = body(TRIGGERS, "ADISCORD_west_regional_country")
        self.assertEqual(set(re.findall(r"tag = ([A-Z]{3})", regional)), set(REGIONAL))

    def test_resolution_flag_precedes_every_white_peace(self):
        for name in (
            "ADISCORD_west_final_resolve_wrk_victory",
            "ADISCORD_west_final_resolve_ivn_victory",
            "ADISCORD_west_final_resolve_without_hegemon",
        ):
            source = body(EFFECTS, name)
            self.assertLess(
                source.index("set_global_flag = ADISCORD_west_final_resolved"),
                source.index("ADISCORD_west_end_final_wars = yes"),
                name,
            )
            self.assertIn("ADISCORD_west_close_campaign_state = yes", source, name)

    def test_every_terminal_path_releases_campaign_status(self):
        close = body(EFFECTS, "ADISCORD_west_close_member_state")
        self.assertIn("set_major = no", close)
        self.assertIn("ADISCORD_west_remove_path_spirit = yes", close)
        self.assertEqual(
            scope_calls(body(EFFECTS, "ADISCORD_west_close_campaign_state"), "ADISCORD_west_close_member_state"),
            set(CHAMPIONS),
        )
        spirits = set(re.findall(r"add_ideas = (ADISCORD_west_\w+)", body(EFFECTS, "ADISCORD_west_add_path_spirit")))
        removed = set(re.findall(r"remove_ideas = (ADISCORD_west_\w+)", body(EFFECTS, "ADISCORD_west_remove_path_spirit")))
        self.assertEqual(len(spirits), 6)
        self.assertEqual(spirits, removed)

    def test_every_winner_path_has_terms(self):
        wrk = body(EFFECTS, "ADISCORD_west_final_resolve_wrk_victory")
        for route in ROUTES[:2]:
            self.assertIn(f"has_country_flag = ADISCORD_vorkerland_route_{route}", wrk)
        self.assertIn("var = ADISCORD_west_terms value = 1", wrk)
        self.assertIn("var = ADISCORD_west_transfer value = 2", wrk)
        ivn = body(EFFECTS, "ADISCORD_west_final_resolve_ivn_victory")
        self.assertIn("ADISCORD_west_ivn_shield_course = yes", ivn)
        self.assertIn("ADISCORD_west_ivn_emergency_course = yes", ivn)
        self.assertIn("var = ADISCORD_west_transfer value = 1", ivn)
        types = body(EFFECTS, "ADISCORD_west_apply_subject_type")
        autonomies = set(re.findall(r"autonomy_state = (\w+)", types))
        defined = set(re.findall(r"\bid = (\w+)", (ROOT / "common/autonomous_states/ADISCORD_west_final_war_subjects.txt").read_text(encoding="utf-8")))
        self.assertEqual(autonomies - {"autonomy_puppet"}, defined)
        transfer = body(EFFECTS, "ADISCORD_west_transfer_to_root")
        self.assertIn("has_country_flag = ADISCORD_west_settlement_pending", transfer)

    def test_deadline_counts_the_documented_districts(self):
        source = body(EFFECTS, "ADISCORD_west_final_resolve_by_control")
        counted = set(re.findall(r"\b(\d+) = \{ ADISCORD_west_count_key_state = yes \}", source))
        self.assertEqual(counted, KEY_STATES)
        self.assertIn("capital_scope = { ADISCORD_west_count_key_state = yes }", source)
        events = EVENTS.read_text(encoding="utf-8")
        self.assertIn("country_event = { id = ADISCORD_west.20 days = 720 }", body(EFFECTS, "ADISCORD_west_final_war_start"))
        self.assertIn("days > 718", events)

    def test_champion_capitulation_owns_the_settlement(self):
        text = PEACE.read_text(encoding="utf-8")
        section = text[text.index("# BEGIN west_final:on_capitulation"):text.index("# END west_final:on_capitulation")]
        self.assertIn("set_global_flag = skip_default_capitulation", section)
        self.assertIn("ADISCORD_west_final_resolve_ivn_victory = yes", section)
        self.assertIn("ADISCORD_west_final_resolve_wrk_victory = yes", section)
        for hook in ("on_peace", "on_annex", "on_puppet"):
            section = text[text.index(f"# BEGIN west_final:{hook}"):text.index(f"# END west_final:{hook}")]
            self.assertIn("ADISCORD_west_final_close_external = yes", section, hook)

    def test_clock_has_one_periodic_driver(self):
        drivers = []
        for path in (ROOT / "common/on_actions").glob("*.txt"):
            if "ADISCORD_west_crisis_month = yes" in path.read_text(encoding="utf-8-sig"):
                drivers.append(path.name)
        self.assertEqual(drivers, ["01_ADISCORD_vorkerland_collapse_on_actions.txt"])
        source = (ROOT / "common/on_actions/01_ADISCORD_vorkerland_collapse_on_actions.txt").read_text(encoding="utf-8")
        hook = source[source.index("on_monthly_WRK = {"):]
        self.assertLess(hook.index("ADISCORD_west_crisis_open = yes"), hook.index("ADISCORD_west_crisis_month = yes"))

    def test_each_path_has_one_final_focus(self):
        ivn = focus_blocks(IVN_TREE)
        wrk = focus_blocks(WRK_TREE)
        finals = {
            "IVN_shield_over_the_west": ivn,
            "IVN_emergency_march_west": ivn,
            "WRK_worker_west_mandate_for_itora": wrk,
            "WRK_joint_west_return_of_the_marches": wrk,
            "WRK_utilitarian_west_engineering_border": wrk,
        }
        starters = set()
        for tree in (ivn, wrk):
            for identifier, focus in tree.items():
                if "ADISCORD_west_final_war_start" in repr(focus):
                    starters.add(identifier)
        self.assertEqual(starters, set(finals))
        for identifier, tree in finals.items():
            available = repr(next(e.value for e in tree[identifier] if e.key == "available"))
            self.assertIn("ADISCORD_west_final_can_start", available, identifier)
        for route in ROUTES:
            chain = [identifier for identifier in wrk if identifier.startswith(f"WRK_{route}_west_")]
            self.assertEqual(len(chain), 4, route)
            for identifier in chain:
                allow = repr(next(e.value for e in wrk[identifier] if e.key == "allow_branch"))
                self.assertIn(f"ADISCORD_vorkerland_route_{route}", allow, identifier)

    def test_heritage_focuses_reward_the_western_settlement(self):
        heritage = {
            "WRK_worker_west_confederate_charter": (WRK_TREE, "ADISCORD_west_hegemon_WRK"),
            "WRK_joint_west_imperial_settlement": (WRK_TREE, "ADISCORD_west_hegemon_WRK"),
            "WRK_utilitarian_west_technical_trusteeship": (WRK_TREE, "ADISCORD_west_hegemon_WRK"),
        }
        for identifier, (path, flag) in heritage.items():
            focus = focus_blocks(path)[identifier]
            self.assertIn(flag, repr(next(e.value for e in focus if e.key == "available")), identifier)
            self.assertNotIn("unlock_decision_tooltip", repr(focus), identifier)
            self.assertTrue(block(focus, "completion_reward"), identifier)
            # Heritage follows the course, not the final war focus: the rival may declare first.
            self.assertNotIn("final_war_start", repr(focus), identifier)

    def test_itora_keeps_only_the_northern_border_award(self):
        victory = parse_clausewitz(body(EFFECTS, "ADISCORD_west_final_resolve_ivn_victory"))
        terms = [
            {e.key: e.value for e in entry.value}
            for entry in flatten(victory)
            if entry.key == "set_global_variable"
        ]
        self.assertEqual(
            [e["value"] for e in terms if e["var"] == "ADISCORD_west_terms"],
            ["2"],
        )
        settlement = parse_clausewitz(body(EFFECTS, "ADISCORD_west_apply_settlement"))
        corridor = block(settlement, "if")
        self.assertEqual({e.key for e in corridor if e.key.isdigit()}, {"90", "91", "93", "94"})
        self.assertIn("value='1'", repr(block(corridor, "limit")))
        transfer = body(EFFECTS, "ADISCORD_west_transfer_to_root")
        self.assertIn("owner = { has_country_flag = ADISCORD_west_settlement_pending }", transfer)
        heritage = focus_blocks(IVN_TREE)["IVN_west_heritage"]
        self.assertIn("ADISCORD_west_hegemon_IVN", repr(block(heritage, "available")))
        self.assertNotIn("unlock_decision_tooltip", repr(block(heritage, "completion_reward")))

    def test_humanist_shield_requires_humanism(self):
        ivn = focus_blocks(IVN_TREE)
        available = repr(next(e.value for e in ivn["IVN_humanist_shield"] if e.key == "available"))
        self.assertIn("key='has_government', value='humanism'", available)
        exclusive = repr(next(e.value for e in ivn["IVN_humanist_shield"] if e.key == "mutually_exclusive"))
        self.assertIn("IVN_emergency_order", exclusive)
        self.assertIn("IVN_adopt_emergency_order", repr(ivn["IVN_emergency_order"]))

    def test_league_answers_clear_the_pending_offer(self):
        source = EVENTS.read_text(encoding="utf-8")
        event = source[source.index("\tid = ADISCORD_west.40\n"):source.index("\tid = ADISCORD_west.41\n")]
        self.assertEqual(event.count("clr_country_flag = ADISCORD_west_league_offer_pending"), 2)
        self.assertIn("NOT = { has_country_flag = ADISCORD_west_league_offer_pending }", body(TRIGGERS, "ADISCORD_west_league_target_valid"))

    def test_events_are_registered_and_localised(self):
        source = EVENTS.read_text(encoding="utf-8")
        defined = set(re.findall(r"\bid = (ADISCORD_west\.\d+)", source))
        registry = json.loads((ROOT / "tools/data/adiscord_event_ids.json").read_text(encoding="utf-8"))
        registered = {e["id"] for e in registry["events"] if e["namespace"] == "ADISCORD_west"}
        self.assertEqual(defined, registered)
        keys = set(re.findall(r"(?:title|desc|name|text) = (ADISCORD_west\.[\w.]+)", source))
        keys |= set(re.findall(r"custom_effect_tooltip = (\w+)", source))
        for language in ("russian", "english"):
            path = ROOT / f"localisation/{language}/ADISCORD_west_final_war_l_{language}.yml"
            raw = path.read_bytes()
            self.assertTrue(raw.startswith(b"\xef\xbb\xbf"), language)
            present = set(re.findall(r"(?m)^ ([\w.]+):", raw.decode("utf-8-sig")))
            self.assertEqual(sorted(keys - present), [], language)

    def test_itoran_tree_is_localised(self):
        source = IVN_TREE.read_text(encoding="utf-8")
        focuses = set(focus_blocks(IVN_TREE))
        tooltips = set(re.findall(r"\btooltip = (IVN_\w+)", source))
        for language in ("russian", "english"):
            path = ROOT / f"localisation/{language}/ADISCORD_IVN_l_{language}.yml"
            raw = path.read_bytes()
            self.assertTrue(raw.startswith(b"\xef\xbb\xbf"), language)
            present = set(re.findall(r"(?m)^ ([\w.]+):", raw.decode("utf-8-sig")))
            expected = focuses | {f + "_desc" for f in focuses} | tooltips | {"IVN_order_dynamic"}
            self.assertEqual(sorted(expected - present), [], language)

    def test_ai_commits_both_champions(self):
        source = (ROOT / "common/ai_strategy/ADISCORD_west_final_war_ai.txt").read_text(encoding="utf-8")
        self.assertIn("ADISCORD_west_wrk_front_ivn = {", source)
        self.assertIn("ADISCORD_west_ivn_front_wrk = {", source)
        self.assertEqual(source.count("abort_when_not_enabled = yes"), 2)

    def test_gameplay_files_have_no_bom(self):
        for path in (EFFECTS, TRIGGERS, EVENTS, IVN_TREE):
            self.assertFalse(path.read_bytes().startswith(b"\xef\xbb\xbf"), path.name)


class SubjectIntegrationRemovalTests(unittest.TestCase):
    def test_subject_annexation_decisions_are_absent_mod_wide(self):
        annexing = set()
        for path in (ROOT / "common/decisions").glob("*.txt"):
            for category in parse_clausewitz(path.read_text(encoding="utf-8-sig")):
                if not isinstance(category.value, list):
                    continue
                for decision in category.value:
                    if not isinstance(decision.value, list):
                        continue
                    if any(e.key == "annex_country" for e in flatten(decision.value)):
                        annexing.add(decision.key)
        # The island treaty joins a sovereign country, not an existing subject.
        self.assertEqual(annexing, {"VAL_Island_Treaty"})

    def test_retired_integration_ids_have_no_runtime_or_focus_references(self):
        retired = re.compile(
            r"ADISCORD_(?:west|south)_(?:integrate_subject|can_integrate)"
            r"|STP_heg_annex_"
            r"|STP_heg_(?:nod|ypr|tff|val)_integrated"
        )
        for directory in ("common", "events", "focus_trees", "localisation"):
            for path in (ROOT / directory).rglob("*"):
                if path.suffix not in {".txt", ".yml"}:
                    continue
                self.assertIsNone(
                    retired.search(path.read_text(encoding="utf-8-sig")),
                    str(path.relative_to(ROOT)),
                )

    def test_native_autonomy_ladders_stop_before_annexation(self):
        for filename in (
            "integrated_puppet.txt",
            "district_in_Vorkerland.txt",
            "Feodal_Baronage.txt",
            "supervised_state.txt",
            "lar_collaboration_government.txt",
        ):
            with self.subTest(filename=filename):
                path = ROOT / "common/autonomous_states" / filename
                autonomy = block(parse_clausewitz(path.read_text(encoding="utf-8")), "autonomy_state")
                gate = block(autonomy, "can_lose_level")
                self.assertEqual([(e.key, e.value) for e in gate], [("always", "no")])

    def test_southern_heritage_keeps_its_rewards_without_an_annexation_unlock(self):
        for country, identifier in (
            ("NAM", "NAM_south_heritage"),
            ("SHL", "SHL_south_crown_of_the_south"),
        ):
            with self.subTest(country=country):
                path = ROOT / f"focus_trees/{country}/main/focuses.txt"
                reward = block(focus_blocks(path)[identifier], "completion_reward")
                self.assertTrue(reward)
                self.assertNotIn("unlock_decision_tooltip", repr(reward))


class ItoranAggregateTests(unittest.TestCase):
    """The Itoran order aggregate shows exactly the variable change a focus applies."""

    def setUp(self):
        dynamic = parse_clausewitz((ROOT / "common/dynamic_modifiers/ADISCORD_dynamic_modifiers_IVN.txt").read_text(encoding="utf-8"))
        modifier = next(e.value for e in dynamic if e.key == "IVN_order_dynamic")
        self.fields = {e.value: e.key for e in modifier if e.key not in ("icon", "enable")}
        root = next(e.value for e in parse_clausewitz((ROOT / "common/ideas/ADISCORD_IVN_ideas.txt").read_text(encoding="utf-8")) if e.key == "ideas")
        self.display = {}
        for group in root:
            for idea in group.value:
                allowed = next(e.value for e in idea.value if e.key == "allowed")
                self.assertEqual([(e.key, e.value) for e in allowed], [("always", "no")], idea.key)
                modifier = next(e.value for e in idea.value if e.key == "modifier")
                self.display[idea.key] = {e.key: float(e.value) for e in modifier}

    def test_every_display_delta_matches_the_applied_change(self):
        checked = 0
        for identifier, focus in focus_blocks(IVN_TREE).items():
            reward = next(e.value for e in focus if e.key == "completion_reward")
            swaps = [e.value for e in flatten(reward) if e.key == "swap_ideas"]
            if not swaps:
                continue
            swap = {e.key: e.value for e in swaps[0]}
            self.assertEqual(self.display[swap["remove_idea"]], {}, identifier)
            hidden = [e.value for e in reward if e.key == "hidden_effect"][-1]
            applied = {}
            for entry in hidden:
                if entry.key == "add_to_variable":
                    values = {e.key: e.value for e in entry.value}
                    applied[self.fields[values["var"]]] = float(values["value"])
            self.assertEqual(applied, self.display[swap["add_idea"]], identifier)
            self.assertIn(("IVN_refresh_order", "yes"), [(e.key, e.value) for e in hidden], identifier)
            checked += 1
        self.assertEqual(checked, 24)

    def test_display_ideas_are_never_installed(self):
        text = IVN_TREE.read_text(encoding="utf-8")
        for name in self.display:
            self.assertNotIn(f"add_ideas = {name}", text)

    def test_refresh_attaches_and_updates_without_reset(self):
        source = body(ROOT / "common/scripted_effects/ADISCORD_IVN_scripted_effects.txt", "IVN_refresh_order")
        self.assertIn("add_dynamic_modifier = { modifier = IVN_order_dynamic }", source)
        self.assertIn("force_update_dynamic_modifier = yes", source)
        self.assertIn("ADISCORD_economy_mark_dirty = yes", source)
        self.assertNotIn("set_variable", source)


if __name__ == "__main__":
    unittest.main()
