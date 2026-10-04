"""Static contracts of the southern final war between Svetlogorye and Shahrabad.

The checks cover script wiring only: side lists, terminal cleanup, flag order
and path focuses. Engine war, faction and peace behaviour needs a game run.
"""

from pathlib import Path
import json
import re
import unittest

from tools.validators.validate_adiscord_division_templates import parse_clausewitz

ROOT = Path(__file__).resolve().parents[2]
EFFECTS = ROOT / "common/scripted_effects/ADISCORD_south_final_war_effects.txt"
TRIGGERS = ROOT / "common/scripted_triggers/ADISCORD_south_final_war_triggers.txt"
EVENTS = ROOT / "events/ADISCORD_south_final_war_events.txt"
PEACE = ROOT / "common/on_actions/09_ADISCORD_scripted_peace_on_actions.txt"
REGIONAL = ("EFL", "AZH", "WEF", "KDR", "RHM", "SDR", "MZR", "KYZ", "GLP")
CHAMPIONS = ("NAM", "SHL")


def definitions(path):
    return {e.key: e.value for e in parse_clausewitz(path.read_text(encoding="utf-8"))}


def body(path, name):
    text = path.read_text(encoding="utf-8")
    start = re.search(rf"(?m)^{re.escape(name)} = \{{", text)
    if start is None:
        raise AssertionError("Missing definition: " + name)
    depth = 0
    for index in range(start.end() - 1, len(text)):
        depth += {"{": 1, "}": -1}.get(text[index], 0)
        if depth == 0:
            return text[start.end():index]
    raise AssertionError("Unbalanced definition: " + name)


def scope_calls(source, effect):
    return set(re.findall(rf"\b([A-Z]{{3}}) = \{{ {re.escape(effect)} = yes \}}", source))


def focus_blocks(path):
    tree = next(e.value for e in parse_clausewitz(path.read_text(encoding="utf-8")) if e.key == "focus_tree")
    result = {}
    for entry in tree:
        if entry.key == "focus":
            identifier = next(e.value for e in entry.value if e.key == "id")
            result[identifier] = entry.value
    return result


def flatten(items):
    for item in items:
        yield item
        if isinstance(item.value, list):
            yield from flatten(item.value)


class SouthFinalWarContractTests(unittest.TestCase):
    def test_every_regional_state_is_woken_bound_offered_and_settled(self):
        for name in (
            "ADISCORD_south_wake_regional_countries",
            "ADISCORD_south_assign_bound_sides",
            "ADISCORD_south_offer_side_choices",
            "ADISCORD_south_faction_partners_follow",
        ):
            calls = set(re.findall(r"\b([A-Z]{3}) = \{", body(EFFECTS, name)))
            self.assertEqual(calls, set(REGIONAL), name)
        for name, effect in (
            ("ADISCORD_south_end_final_wars", "ADISCORD_south_end_member_wars"),
            ("ADISCORD_south_mark_losers", "ADISCORD_south_mark_loser"),
            ("ADISCORD_south_clear_participants", "ADISCORD_south_clear_participant"),
            ("ADISCORD_south_apply_settlement", "ADISCORD_south_settle_member"),
        ):
            self.assertEqual(scope_calls(body(EFFECTS, name), effect), set(REGIONAL) | set(CHAMPIONS), name)
        regional = body(TRIGGERS, "ADISCORD_south_regional_country")
        self.assertEqual(set(re.findall(r"tag = ([A-Z]{3})", regional)), set(REGIONAL))

    def test_minors_are_released_before_any_side_or_war(self):
        for name in ("ADISCORD_south_join_shl_side", "ADISCORD_south_join_north_side", "ADISCORD_south_prepare_champion"):
            source = body(EFFECTS, name).strip()
            self.assertTrue(source.startswith("ADISCORD_release_non_participating_minor_optimization = yes"), name)
        start = body(EFFECTS, "ADISCORD_south_final_war_start")
        self.assertLess(start.index("ADISCORD_south_wake_regional_countries = yes"), start.index("declare_war_on"))

    def test_resolution_flag_precedes_every_white_peace(self):
        for name in ("ADISCORD_south_final_resolve_shl_victory", "ADISCORD_south_final_resolve_north_victory", "ADISCORD_south_final_resolve_without_hegemon"):
            source = body(EFFECTS, name)
            self.assertLess(source.index("set_global_flag = ADISCORD_south_final_resolved"), source.index("ADISCORD_south_end_final_wars = yes"), name)
        repel = body(EFFECTS, "ADISCORD_south_final_repel")
        self.assertLess(repel.index("clr_global_flag = ADISCORD_south_final_started"), repel.index("ADISCORD_south_end_final_wars = yes"))

    def test_every_terminal_path_releases_campaign_status(self):
        for name in (
            "ADISCORD_south_final_resolve_shl_victory",
            "ADISCORD_south_final_resolve_north_victory",
            "ADISCORD_south_final_repel",
            "ADISCORD_south_final_resolve_without_hegemon",
        ):
            self.assertIn("ADISCORD_south_close_campaign_state = yes", body(EFFECTS, name), name)
        close = body(EFFECTS, "ADISCORD_south_close_member_state")
        self.assertIn("set_major = no", close)
        self.assertIn("ADISCORD_south_remove_path_spirit = yes", close)
        self.assertEqual(scope_calls(body(EFFECTS, "ADISCORD_south_close_campaign_state"), "ADISCORD_south_close_member_state"), {"NAM", "SHL", "EFL", "AZH"})
        spirits = set(re.findall(r"add_ideas = (ADISCORD_south_\w+)", body(EFFECTS, "ADISCORD_south_add_path_spirit")))
        removed = set(re.findall(r"remove_ideas = (ADISCORD_south_\w+)", body(EFFECTS, "ADISCORD_south_remove_path_spirit")))
        self.assertEqual(spirits, removed)

    def test_only_svetlogorye_can_win_the_north_side(self):
        north = body(EFFECTS, "ADISCORD_south_final_resolve_north_victory")
        self.assertIn("ADISCORD_south_north_is_nam = yes", north)
        self.assertIn("ADISCORD_south_final_repel = yes", north)
        self.assertNotIn("ADISCORD_south_hegemon_EFL", EFFECTS.read_text(encoding="utf-8"))
        self.assertNotIn("ADISCORD_south_hegemon_AZH", EFFECTS.read_text(encoding="utf-8"))

    def test_uprising_never_survives_the_settlement(self):
        settlement = body(EFFECTS, "ADISCORD_south_apply_settlement")
        self.assertIn("annex_country = { target = SLF transfer_troops = no }", settlement)

    def test_each_course_has_one_final_focus(self):
        shl = focus_blocks(ROOT / "focus_trees/SHL/main/focuses.txt")
        expected = {
            "SHL_south_oil_for_furnaces": ("1", "SHL_south_great_road"),
            "SHL_south_war_of_charters": ("2", "SHL_south_free_road"),
            "SHL_south_last_pour": ("3", "SHL_south_iron_march"),
            "SHL_south_war_of_arms": ("4", "SHL_south_veyr_debt"),
            "SHL_south_oil_uprising": ("5", "SHL_south_oil_underground"),
        }
        for identifier, (course, parent) in expected.items():
            focus = shl[identifier]
            text = repr(focus)
            prerequisites = [e.value for e in focus if e.key == "prerequisite"]
            self.assertEqual([[(i.key, i.value) for i in p] for p in prerequisites], [[("focus", parent)]], identifier)
            courses = [
                next(i.value for i in e.value if i.key == "value")
                for e in flatten(next(e.value for e in focus if e.key == "available"))
                if e.key == "check_variable" and any(i.key == "var" and i.value == "SHL_political_course" for i in e.value)
            ]
            self.assertEqual(courses, [course], identifier)
            self.assertIn("ADISCORD_south_final_war_start", text, identifier)
        nam = focus_blocks(ROOT / "focus_trees/NAM/main/focuses.txt")
        for identifier, path in (("NAM_south_seal_over_furnaces", "NAM_service_state"), ("NAM_south_oil_charter", "NAM_federal_charter")):
            available = repr(next(e.value for e in nam[identifier] if e.key == "available"))
            self.assertIn(path, available, identifier)
            self.assertIn("ADISCORD_south_final_can_start", available, identifier)

    def test_champion_capitulation_owns_the_settlement(self):
        text = PEACE.read_text(encoding="utf-8")
        section = text[text.index("# BEGIN south_final:on_capitulation"):text.index("# END south_final:on_capitulation")]
        self.assertIn("set_global_flag = skip_default_capitulation", section)
        self.assertIn("ADISCORD_south_final_resolve_north_victory = yes", section)
        self.assertIn("ADISCORD_south_final_resolve_shl_victory = yes", section)
        for hook in ("on_peace", "on_annex", "on_puppet"):
            section = text[text.index(f"# BEGIN south_final:{hook}"):text.index(f"# END south_final:{hook}")]
            self.assertIn("ADISCORD_south_final_close_external = yes", section, hook)

    def test_clock_has_one_periodic_driver(self):
        shl = (ROOT / "common/scripted_effects/ADISCORD_SHL_scripted_effects.txt").read_text(encoding="utf-8")
        self.assertEqual(shl.count("ADISCORD_south_crisis_cycle = yes"), 1)
        self.assertIn("ADISCORD_south_crisis_cycle = yes", body(ROOT / "common/scripted_effects/ADISCORD_SHL_scripted_effects.txt", "SHL_run_cycle"))
        self.assertEqual(shl.count("ADISCORD_south_crisis_add_campaign = yes"), 3)
        for path in (ROOT / "common/on_actions").glob("*.txt"):
            self.assertNotIn("ADISCORD_south_crisis", path.read_text(encoding="utf-8-sig"), path.name)

    def test_events_are_registered_and_localised(self):
        source = EVENTS.read_text(encoding="utf-8")
        defined = set(re.findall(r"\bid = (ADISCORD_south\.\d+)", source))
        registry = json.loads((ROOT / "tools/data/adiscord_event_ids.json").read_text(encoding="utf-8"))
        registered = {e["id"] for e in registry["events"] if e["namespace"] == "ADISCORD_south"}
        self.assertEqual(defined, registered)
        keys = set(re.findall(r"(?:title|desc|name|text) = (ADISCORD_south\.[\w.]+)", source))
        for language in ("russian", "english"):
            path = ROOT / f"localisation/{language}/ADISCORD_south_final_war_l_{language}.yml"
            raw = path.read_bytes()
            self.assertTrue(raw.startswith(b"\xef\xbb\xbf"), language)
            present = set(re.findall(r"(?m)^ ([\w.]+):", raw.decode("utf-8-sig")))
            self.assertEqual(sorted(keys - present), [], language)

    def test_campaign_focuses_bypass_exactly_their_targets(self):
        offers = ("ADISCORD_south_demand_submission", "ADISCORD_south_demand_annexation", "ADISCORD_south_offer_alliance")
        checked = 0
        for path in (ROOT / "focus_trees/SHL/main/focuses.txt", ROOT / "focus_trees/NAM/main/focuses.txt"):
            for identifier, focus in focus_blocks(path).items():
                reward = next(e.value for e in focus if e.key == "completion_reward")
                targets = {e.key for e in flatten(reward) if isinstance(e.value, list) and any(i.key in offers for i in e.value)}
                if not targets:
                    continue
                checked += 1
                bypass = next(e.value for e in focus if e.key == "bypass")
                self.assertEqual({e.key for e in bypass}, targets, identifier)
                available = repr(next(e.value for e in focus if e.key == "available"))
                self.assertIn("ADISCORD_south_final_started", available, identifier)
        self.assertEqual(checked, 15)

    def test_answers_always_clear_the_pending_offer(self):
        for name in ("ADISCORD_south_accept_offer", "ADISCORD_south_refuse_offer"):
            self.assertTrue(body(EFFECTS, name).rstrip().endswith("clear_variable = ADISCORD_south_offer_kind"), name)
        refuse = body(EFFECTS, "ADISCORD_south_refuse_offer")
        self.assertIn("NOT = { check_variable = { var = ADISCORD_south_offer_kind value = 3 compare = equals } }", refuse)
        self.assertIn("NOT = { ADISCORD_south_final_active = yes }", refuse)
        text = PEACE.read_text(encoding="utf-8")
        section = text[text.index("# BEGIN south_final:on_annex"):text.index("# END south_final:on_annex")]
        self.assertIn("ADISCORD_south_note_campaign_annexation = yes", section)

    def test_commune_uprising_joins_shahrabad_at_war_start(self):
        start = body(EFFECTS, "ADISCORD_south_final_war_start")
        self.assertLess(start.index("ADISCORD_south_offer_side_choices = yes"), start.index("ADISCORD_south_raise_oil_uprising = yes"))
        uprising = body(EFFECTS, "ADISCORD_south_raise_oil_uprising")
        self.assertIn("set_variable = { var = ADISCORD_south_side value = 1 }", uprising)
        self.assertIn("targeted_alliance = SHL", uprising)
        self.assertIn("NAM_district_compact", uprising)

    def test_course_mandates_and_wartime_programmes_serve_the_final_war(self):
        shl = body(ROOT / "common/scripted_triggers/ADISCORD_SHL_scripted_triggers.txt", "SHL_campaign_open")
        self.assertIn("ADISCORD_south_final_active = yes", shl)
        start = body(EFFECTS, "ADISCORD_south_final_war_start")
        self.assertIn("SHL_use_campaign_reserve = yes", start)
        self.assertIn("SHL_clean_campaign = yes", body(EFFECTS, "ADISCORD_south_close_campaign_state"))
        nam = body(ROOT / "common/scripted_triggers/ADISCORD_nam_resource_war_triggers.txt", "NAM_wartime_programmes_open")
        self.assertIn("ADISCORD_south_final_active = yes", nam)
        self.assertIn("ADISCORD_south_north_leader", nam)
        decisions = (ROOT / "common/decisions/ADISCORD_nam_resource_war_decisions.txt").read_text(encoding="utf-8")
        self.assertEqual(decisions.count("NAM_wartime_programmes_open = yes"), 6)

    def test_ai_commits_every_champion_pair(self):
        source = (ROOT / "common/ai_strategy/ADISCORD_south_final_war_ai.txt").read_text(encoding="utf-8")
        for leader in ("NAM", "EFL", "AZH"):
            self.assertIn(f"ADISCORD_south_shl_front_{leader.lower()} = {{", source)
            self.assertIn(f"ADISCORD_south_{leader.lower()}_front_shl = {{", source)
        self.assertEqual(source.count("abort_when_not_enabled = yes"), 7)

    def test_effect_files_have_no_bom(self):
        for path in (EFFECTS, TRIGGERS, EVENTS):
            self.assertFalse(path.read_bytes().startswith(b"\xef\xbb\xbf"), path.name)


class FocusAggregateTests(unittest.TestCase):
    """TFR-style display pairs must show exactly the variable change a focus applies."""

    DYNAMICS = (
        ROOT / "common/dynamic_modifiers/ADISCORD_dynamic_modifiers_NAM.txt",
        ROOT / "common/dynamic_modifiers/ADISCORD_dynamic_modifiers_SHL.txt",
    )
    IDEAS = (
        ROOT / "common/ideas/ADISCORD_nam_resource_war_ideas.txt",
        ROOT / "common/ideas/ADISCORD_southern_desert_ideas.txt",
    )
    TREES = (ROOT / "focus_trees/NAM/main/focuses.txt", ROOT / "focus_trees/SHL/main/focuses.txt")
    REFRESH = {
        "NAM_administration_dynamic": "NAM_refresh_administration",
        "NAM_garrison_dynamic": "NAM_refresh_garrison",
        "SHL_conclave_power_dynamic": "SHL_refresh_conclave_power",
    }

    def setUp(self):
        self.fields = {}
        for path in self.DYNAMICS:
            for entry in parse_clausewitz(path.read_text(encoding="utf-8")):
                if entry.key in self.REFRESH:
                    self.fields[entry.key] = {e.value: e.key for e in entry.value if e.key not in ("icon", "enable")}
        self.display = {}
        for path in self.IDEAS:
            root = next(e.value for e in parse_clausewitz(path.read_text(encoding="utf-8")) if e.key == "ideas")
            for group in root:
                for idea in group.value:
                    name = next((e.value for e in idea.value if e.key == "name"), None)
                    if name in self.REFRESH:
                        modifier = next(e.value for e in idea.value if e.key == "modifier")
                        allowed = next(e.value for e in idea.value if e.key == "allowed")
                        self.assertEqual([(e.key, e.value) for e in allowed], [("always", "no")], idea.key)
                        self.display[idea.key] = (name, {e.key: float(e.value) for e in modifier})

    def test_every_display_delta_matches_the_applied_change(self):
        checked = 0
        for tree in self.TREES:
            for identifier, focus in focus_blocks(tree).items():
                reward = next(e.value for e in focus if e.key == "completion_reward")
                swaps = [e.value for e in flatten(reward) if e.key == "swap_ideas"]
                if not swaps:
                    continue
                swap = {e.key: e.value for e in swaps[0]}
                base_name, base = self.display[swap["remove_idea"]]
                delta_name, delta = self.display[swap["add_idea"]]
                self.assertEqual(base, {}, identifier)
                self.assertEqual(base_name, delta_name, identifier)
                hidden = next(e.value for e in reward if e.key == "hidden_effect")
                applied = {}
                for entry in hidden:
                    if entry.key == "add_to_variable":
                        values = {e.key: e.value for e in entry.value}
                        applied[self.fields[delta_name][values["var"]]] = float(values["value"])
                self.assertEqual(applied, delta, identifier)
                self.assertIn((self.REFRESH[delta_name], "yes"), [(e.key, e.value) for e in hidden], identifier)
                checked += 1
        self.assertEqual(checked, 114)

    def test_display_ideas_are_never_installed(self):
        names = set(self.display)
        for tree in self.TREES:
            text = tree.read_text(encoding="utf-8")
            for name in names:
                self.assertNotIn(f"add_ideas = {name}", text)
                self.assertNotIn(f"add_timed_idea = {{ idea = {name}", text)

    def test_refresh_attaches_and_updates_without_reset(self):
        for name, refresh in self.REFRESH.items():
            path = ROOT / ("common/scripted_effects/ADISCORD_nam_resource_war_effects.txt" if name.startswith("NAM") else "common/scripted_effects/ADISCORD_SHL_scripted_effects.txt")
            source = body(path, refresh)
            self.assertIn(f"add_dynamic_modifier = {{ modifier = {name} }}", source)
            self.assertIn("force_update_dynamic_modifier = yes", source)
            self.assertIn("ADISCORD_economy_mark_dirty = yes", source)
            self.assertNotIn("set_variable", source)


if __name__ == "__main__":
    unittest.main()
