"""Static contracts of the southern final war between Svetlogorye and Shahrabad.

The checks cover script wiring only: side lists, terminal cleanup, flag order
and path focuses. Engine war, faction and peace behaviour needs a game run.
"""

from pathlib import Path
from dataclasses import replace
import json
import re
import unittest

from tools.validators.validate_adiscord_division_templates import parse_clausewitz
from tools.tests.test_adiscord_stp_preparation import block, scalar, matches_conditions, selected_effects

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
    def test_shared_settlement_variables_have_native_global_writers(self):
        entries = list(flatten(parse_clausewitz(EFFECTS.read_text(encoding="utf-8"))))
        self.assertFalse(any(entry.key == "set_global_variable" for entry in entries))
        written = {
            field.value
            for entry in entries
            if entry.key == "set_variable"
            for field in entry.value
            if field.key == "var"
        }
        for name in ("declarer_side", "winner_side", "terms", "subject_type"):
            self.assertIn(f"global.ADISCORD_south_{name}", written)
            self.assertNotIn(f"ADISCORD_south_{name}", written)

    def test_every_regional_state_is_woken_bound_offered_and_settled(self):
        for name in (
            "ADISCORD_south_wake_regional_countries",
            "ADISCORD_south_offer_side_choices",
            "ADISCORD_south_faction_partners_follow",
        ):
            calls = set(re.findall(r"\b([A-Z]{3}) = \{", body(EFFECTS, name)))
            self.assertEqual(calls, set(REGIONAL), name)
        bound = scope_calls(body(EFFECTS, "ADISCORD_south_assign_bound_sides"), "ADISCORD_south_bind_to_champion")
        self.assertEqual(bound, set(REGIONAL) | {"NAM"})
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
        self.assertIn("RUS_crisis_release_other_major = yes", close)
        self.assertLess(close.index("clr_country_flag = ADISCORD_south_added_major"), close.index("RUS_crisis_release_other_major = yes"))
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
            self.assertIn("ADISCORD_south_prepare_offensive", text, identifier)
        nam = focus_blocks(ROOT / "focus_trees/NAM/postwar/focuses.txt")
        for identifier, path in (("NAM_south_seal_over_furnaces", "NAM_service_state"), ("NAM_south_oil_charter", "NAM_federal_charter")):
            available = repr(next(e.value for e in nam[identifier] if e.key == "available"))
            self.assertIn(path, available, identifier)
            self.assertIn("ADISCORD_south_final_focus_available", available, identifier)

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
        self.assertNotIn("ADISCORD_south_crisis_add_campaign", shl)
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
        for path in (
            ROOT / "focus_trees/SHL/main/focuses.txt",
            ROOT / "focus_trees/NAM/postwar/focuses.txt",
            ROOT / "focus_trees/NAM/defeated/focuses.txt",
        ):
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
        self.assertEqual(checked, 16)

    def test_answers_always_clear_the_pending_offer(self):
        for name in ("ADISCORD_south_accept_offer", "ADISCORD_south_refuse_offer"):
            self.assertTrue(body(EFFECTS, name).rstrip().endswith("clear_variable = ADISCORD_south_offer_kind"), name)
        refuse = body(EFFECTS, "ADISCORD_south_refuse_offer")
        self.assertIn("NOT = { check_variable = { var = ADISCORD_south_offer_kind value = 3 compare = equals } }", refuse)
        self.assertIn("ADISCORD_south_offer_answer_valid = yes", refuse)
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
        decisions = definitions(ROOT / "common/decisions/ADISCORD_nam_resource_war_decisions.txt")
        national = {e.key: e.value for e in decisions["NAM_national_programmes"]}
        for name in ("NAM_emergency_arsenal", "NAM_counterinsurgency", "NAM_relief_batch"):
            self.assertIn("NAM_wartime_programmes_open", repr(block(national[name], "available")))

    def test_ai_commits_every_champion_pair(self):
        source = (ROOT / "common/ai_strategy/ADISCORD_south_final_war_ai.txt").read_text(encoding="utf-8")
        for leader in ("NAM", "EFL", "AZH"):
            self.assertIn(f"ADISCORD_south_shl_front_{leader.lower()} = {{", source)
            self.assertIn(f"ADISCORD_south_{leader.lower()}_front_shl = {{", source)
        for name, entries in definitions(ROOT / "common/ai_strategy/ADISCORD_south_final_war_ai.txt").items():
            self.assertEqual(scalar(entries, "abort_when_not_enabled"), "yes", name)

    def test_effect_files_have_no_bom(self):
        for path in (EFFECTS, TRIGGERS, EVENTS):
            self.assertFalse(path.read_bytes().startswith(b"\xef\xbb\xbf"), path.name)


class SouthLifecycleTests(unittest.TestCase):
    """Execute bounded clock/objective accounting; native war and event UI remain manual."""

    def setUp(self):
        self.triggers = definitions(TRIGGERS)
        self.triggers.update(definitions(ROOT / "common/scripted_triggers/ADISCORD_nam_resource_war_triggers.txt"))
        self.effects = definitions(EFFECTS)
        self.facts = {}
        self.arrays = {}
        self.calls = []
        self.start_scopes = []
        self.event_root = "SHL"
        self.event_sender = "SHL"
        self.targets = {}
        for tag in ("NAM", "SHL", "EFL", "AZH"):
            self.facts.update({(tag, "exists", "yes"): True, (tag, "is_subject", "no"): True,
                               (tag, "has_capitulated", "no"): True, (tag, "has_war", "no"): True,
                               (tag, "is_in_faction", "no"): True})
            self.facts[(tag, "numeric", "date")] = 21650101
        for tag, names in {
            "SHL": ("SHL_conclave_army", "SHL_metal_market", "SHL_conclave_rules"),
            "NAM": ("NAM_svetlogorye", "NAM_oil_exchange", "NAM_ladder_of_seals"),
        }.items():
            for name in names:
                self.facts[(tag, "has_completed_focus", name)] = True
        self.facts[("SHL", "has_country_flag", "SHL_furnaces_initialized")] = True
        for flag in ("ADISCORD_fresh_campaign_contract_v1", "ADISCORD_nam_resource_war_resolved"):
            self.flag(flag)

    def flag(self, name, present=True, age=0):
        self.facts[("GLB", "has_global_flag", name)] = present
        self.facts[("GLB", "flag_days", name)] = age

    def variable(self, name, value, scope="GLB"):
        self.facts[(scope, "variable", name)] = value
        self.facts[(scope, "has_variable", name)] = True

    def expand(self, entries):
        result = []
        for index, entry in enumerate(entries):
            if index >= 2 and entries[index - 2].key == "" and entries[index - 2].value == "date":
                year, month, day = entry.value.split(".")
                entry = replace(entry, value=str(int(year) * 10000 + int(month) * 100 + int(day)))
            if entry.key in self.triggers:
                self.assertIn(entry.value, ("yes", "no"))
                predicate = replace(entry, key="AND", value=self.expand(self.triggers[entry.key]))
                result.append(predicate if entry.value == "yes" else replace(entry, key="NOT", value=[predicate]))
            elif entry.key == "has_global_flag":
                result.append(replace(entry, key="GLB", value=[entry]))
            elif entry.key == "check_variable" and scalar(entry.value, "var").startswith("global."):
                fields = [replace(e, value=e.value.removeprefix("global.")) if isinstance(e.value, str) else e
                          for e in entry.value]
                result.append(replace(entry, key="GLB", value=[replace(entry, value=fields)]))
            elif entry.key == "check_variable" and scalar(entry.value, "value").startswith("global."):
                fields = [
                    replace(field, value=str(self.facts.get(("GLB", "variable", field.value.removeprefix("global.")), 0)))
                    if field.key == "value" else field
                    for field in entry.value
                ]
                result.append(replace(entry, value=fields))
            elif entry.key in ("ROOT", "FROM") or entry.key.startswith("event_target:"):
                target = (self.event_root if entry.key == "ROOT" else self.event_sender if entry.key == "FROM"
                          else self.targets[entry.key.split(":", 1)[1]])
                result.append(replace(entry, key=target, value=self.expand(entry.value)))
            elif isinstance(entry.value, list):
                result.append(replace(entry, value=self.expand(entry.value)))
            elif entry.value in ("ROOT", "FROM"):
                result.append(replace(entry, value=self.event_root if entry.value == "ROOT" else self.event_sender))
            else:
                result.append(entry)
        return result

    def matches(self, entries, scope="SHL"):
        return matches_conditions(self.expand(entries), self.facts, scope)

    def trigger_matches(self, name, scope="SHL"):
        return self.matches(self.triggers[name], scope)

    def execute(self, name, scope="SHL"):
        self.execute_entries(self.effects[name], scope)

    def execute_entries(self, entries, scope):
        terminals = {"ADISCORD_south_final_resolve_shl_victory", "ADISCORD_south_final_resolve_north_victory",
                     "ADISCORD_south_final_resolve_without_hegemon", "ADISCORD_south_final_repel",
                     "ADISCORD_south_final_war_start"}
        for current, entry in selected_effects(self.expand(entries), self.facts, scope):
            if entry.key == "ADISCORD_south_final_war_start":
                if self.trigger_matches("ADISCORD_south_final_can_start", current) and self.trigger_matches("ADISCORD_south_declarer_valid", current):
                    self.calls.append(entry.key)
                    self.start_scopes.append(current)
            elif entry.key in terminals:
                self.calls.append(entry.key)
            elif entry.key in self.effects:
                self.execute(entry.key, current)
            elif entry.key in ("set_global_flag", "clr_global_flag"):
                self.flag(entry.value, entry.key == "set_global_flag")
            elif entry.key in ("set_country_flag", "clr_country_flag"):
                self.facts[(current, "has_country_flag", entry.value)] = entry.key == "set_country_flag"
            elif entry.key in ("set_variable", "add_to_variable", "clamp_variable"):
                name = scalar(entry.value, "var")
                holder = "GLB" if name.startswith("global.") else current
                name = name.removeprefix("global.")
                old = self.facts.get((holder, "variable", name), 0)
                if entry.key == "clamp_variable":
                    value = min(float(scalar(entry.value, "max")), max(float(scalar(entry.value, "min")), old))
                else:
                    value = float(scalar(entry.value, "value"))
                    if entry.key == "add_to_variable":
                        value += old
                self.variable(name, value, holder)
            elif entry.key == "clear_variable":
                holder = "GLB" if entry.value.startswith("global.") else current
                name = entry.value.removeprefix("global.")
                self.facts.pop((holder, "variable", name), None)
                self.facts[(holder, "has_variable", name)] = False
            elif entry.key == "add_to_array":
                self.assertEqual(scalar(entry.value, "value"), "THIS")
                self.arrays.setdefault(scalar(entry.value, "array"), []).append(current)
            elif entry.key == "clear_array":
                self.arrays[entry.value] = []
            elif entry.key == "for_each_scope_loop":
                for target in list(self.arrays.get(scalar(entry.value, "array"), [])):
                    self.execute_entries([e for e in entry.value if e.key != "array"], target)
            elif entry.key == "capital_scope":
                self.execute_entries(entry.value, self.facts[(current, "capital")])
            elif entry.key in ("activate_mission", "remove_mission"):
                self.facts[(current, "mission", entry.value)] = entry.key == "activate_mission"
                self.calls.append((current, entry.key, entry.value))
            elif entry.key == "save_event_target_as":
                self.targets[entry.value] = current
            elif entry.key == "country_event":
                self.calls.append((current, "country_event", scalar(entry.value, "id"), self.event_root, dict(self.targets)))
            elif entry.key == "add_to_war":
                self.calls.append((current, "add_to_war", scalar(entry.value, "targeted_alliance"), scalar(entry.value, "enemy")))
            else:
                self.assertIn(entry.key, ("news_event", "mark_focus_tree_layout_dirty", "ADISCORD_release_non_participating_minor_optimization"), entry.key)

    def test_date_and_focus_readiness_block_every_starter(self):
        self.variable("ADISCORD_south_crisis", 100)
        self.execute("ADISCORD_south_begin_preparation")
        self.flag("ADISCORD_south_crisis_warned", age=84)
        for date, expected in ((21641231, False), (21650101, True)):
            for tag in ("NAM", "SHL", "EFL", "AZH"):
                self.facts[(tag, "numeric", "date")] = date
                self.assertEqual(self.trigger_matches("ADISCORD_south_final_can_start", tag), expected)
            self.calls.clear()
            self.execute("ADISCORD_south_crisis_cycle")
            self.assertEqual("ADISCORD_south_final_war_start" in self.calls, expected)
        for tag, focus in (("NAM", "NAM_svetlogorye"), ("NAM", "NAM_oil_exchange"), ("SHL", "SHL_conclave_army"), ("SHL", "SHL_metal_market")):
            self.facts[(tag, "has_completed_focus", focus)] = False
            for declarer in ("NAM", "SHL", "EFL", "AZH"):
                self.assertFalse(self.trigger_matches("ADISCORD_south_final_can_start", declarer), (tag, focus, declarer))
            self.facts[(tag, "has_completed_focus", focus)] = True

    def test_focus_completion_opens_warning_without_new_postwar_timer(self):
        self.execute("ADISCORD_south_begin_preparation")
        self.execute("ADISCORD_south_crisis_cycle")
        self.assertTrue(self.facts[("GLB", "has_global_flag", "ADISCORD_south_crisis_warned")])
        self.assertNotIn("ADISCORD_south_final_war_start", self.calls)
        for age in (0, 55, 56):
            self.flag("ADISCORD_south_crisis_warned", age=age)
            self.assertEqual(self.trigger_matches("ADISCORD_south_final_can_start"), age >= 56)

    def test_cancelled_resource_entry_has_attainable_main_tree_milestones(self):
        for key in list(self.facts):
            if key[0] == "NAM" and key[1] == "has_completed_focus":
                self.facts[key] = False
        self.flag("ADISCORD_nam_resource_war_resolved", False)
        self.flag("ADISCORD_nam_resource_war_retry_used")
        for name in ("NAM_seal_courts", "NAM_civilian_combine", "NAM_officer_courses"):
            self.facts[("NAM", "has_completed_focus", name)] = True
        self.assertTrue(self.trigger_matches("ADISCORD_south_nam_focus_ready", "NAM"))
        self.flag("ADISCORD_nam_resource_war_scheduled")
        self.assertFalse(self.trigger_matches("ADISCORD_south_nam_focus_ready", "NAM"))

    def test_offensive_focus_fits_warning_and_selects_northern_declarer(self):
        self.execute("ADISCORD_south_begin_preparation")
        self.execute("ADISCORD_south_crisis_cycle")
        for tree in ("NAM/postwar", "NAM/defeated", "SHL/main"):
            for name, focus in focus_blocks(ROOT / f"focus_trees/{tree}/focuses.txt").items():
                if "ADISCORD_south_prepare_offensive" not in repr(block(focus, "completion_reward")):
                    continue
                self.assertIn("ADISCORD_south_final_focus_available", repr(block(focus, "available")), name)
                self.assertLessEqual(float(scalar(focus, "cost")) * 7, 56, name)
        self.assertTrue(self.trigger_matches("ADISCORD_south_final_focus_available", "NAM"))
        self.assertFalse(self.trigger_matches("ADISCORD_south_final_can_start", "NAM"))
        self.execute("ADISCORD_south_prepare_offensive", "NAM")
        self.assertTrue(self.facts[("NAM", "has_country_flag", "ADISCORD_south_offensive_order")])
        for age in (42, 55, 56):
            self.calls.clear()
            self.flag("ADISCORD_south_crisis_warned", age=age)
            self.execute("ADISCORD_south_crisis_cycle")
            self.assertEqual("ADISCORD_south_final_war_start" in self.calls, age >= 56)
        dispatcher = body(EFFECTS, "ADISCORD_south_dispatch_prepared_war")
        self.assertIn("has_country_flag = ADISCORD_south_offensive_order", dispatcher)
        self.assertIn("NAM = { ADISCORD_south_final_war_start = yes }", dispatcher)
        self.assertEqual(self.start_scopes, ["NAM"])
        self.execute("ADISCORD_south_suspend_preparation")
        self.assertFalse(self.facts[("NAM", "has_country_flag", "ADISCORD_south_offensive_order")])
        self.execute("ADISCORD_south_begin_preparation")
        self.flag("ADISCORD_south_crisis_warned", age=56)
        self.start_scopes.clear()
        self.execute("ADISCORD_south_crisis_cycle")
        self.assertEqual(self.start_scopes, [])
        self.flag("ADISCORD_south_crisis_warned", age=84)
        self.execute("ADISCORD_south_crisis_cycle")
        self.assertEqual(self.start_scopes, ["SHL"], "A historical or bypassed focus cannot repeat an expired order")

    def test_shl_order_starts_after_warning_instead_of_waiting_for_automatic_attack(self):
        self.execute("ADISCORD_south_begin_preparation")
        self.execute("ADISCORD_south_crisis_cycle")
        self.execute("ADISCORD_south_prepare_offensive", "SHL")
        self.assertEqual(self.start_scopes, [])
        self.flag("ADISCORD_south_crisis_warned", age=56)
        self.execute("ADISCORD_south_crisis_cycle")
        self.assertEqual(self.start_scopes, ["SHL"])

    def test_missing_focus_is_not_replaced_by_a_date_or_spare_equipment(self):
        self.execute("ADISCORD_south_begin_preparation")
        self.facts[("SHL", "has_completed_focus", "SHL_conclave_army")] = False
        self.variable("ADISCORD_south_crisis", 100)
        self.facts[("SHL", "numeric", "date")] = 21700101
        self.flag("ADISCORD_south_preparation_started", age=3000)
        self.execute("ADISCORD_south_crisis_cycle")
        self.assertFalse(self.facts.get(("GLB", "has_global_flag", "ADISCORD_south_crisis_warned"), False))
        self.facts[("SHL", "has_completed_focus", "SHL_conclave_army")] = True
        self.facts[("NAM", "numeric", "has_manpower")] = 0
        self.facts[("SHL", "equipment", "infantry_equipment")] = 0
        self.execute("ADISCORD_south_crisis_cycle")
        self.assertTrue(self.facts[("GLB", "has_global_flag", "ADISCORD_south_crisis_warned")])

    def test_focus_routes_and_successors_have_reachable_alternatives(self):
        self.facts[("NAM", "has_completed_focus", "NAM_ladder_of_seals")] = False
        self.facts[("NAM", "has_completed_focus", "NAM_common_fuel_market")] = True
        self.assertTrue(self.trigger_matches("ADISCORD_south_nam_focus_ready", "NAM"))
        for key in list(self.facts):
            if key[0] == "NAM" and key[1] == "has_completed_focus":
                self.facts[key] = False
        for focus in ("NAM_rad_great_war_plan", "NAM_hum_union_call", "NAM_board_stock_mobilisation"):
            self.facts[("NAM", "has_completed_focus", focus)] = True
            self.assertTrue(self.trigger_matches("ADISCORD_south_nam_focus_ready", "NAM"), focus)
            self.facts[("NAM", "has_completed_focus", focus)] = False
        for focus in ("NAM_defeat_revenge", "NAM_defeat_second_chapter"):
            self.facts[("NAM", "has_completed_focus", focus)] = True
        self.assertTrue(self.trigger_matches("ADISCORD_south_nam_focus_ready", "NAM"))
        self.facts[("NAM", "has_completed_focus", "NAM_defeat_second_chapter")] = False
        for focus in ("NAM_defeat_rump_cabinet", "NAM_defeat_harbour_economy", "NAM_defeat_road_south"):
            self.facts[("NAM", "has_completed_focus", focus)] = True
        self.assertTrue(self.trigger_matches("ADISCORD_south_nam_focus_ready", "NAM"))
        self.facts[("NAM", "exists", "yes")] = False
        self.assertTrue(self.trigger_matches("ADISCORD_south_both_focus_ready"))
        self.facts[("EFL", "exists", "yes")] = False
        self.assertTrue(self.trigger_matches("ADISCORD_south_both_focus_ready"))
        self.facts[("AZH", "exists", "yes")] = False
        self.assertFalse(self.trigger_matches("ADISCORD_south_both_focus_ready"))

    def test_compromise_preparation_waits_for_diplomacy_before_the_warning(self):
        for key in list(self.facts):
            if key[0] == "NAM" and key[1] == "has_completed_focus":
                self.facts[key] = False
        for name in ("NAM_defeat_rump_cabinet", "NAM_defeat_harbour_economy",
                     "NAM_defeat_open_border", "NAM_defeat_oil_union", "NAM_defeat_oil_peace"):
            self.facts[("NAM", "has_completed_focus", name)] = True
        self.assertFalse(self.trigger_matches("ADISCORD_south_nam_focus_ready", "NAM"))
        self.facts[("NAM", "has_completed_focus", "NAM_defeat_road_south")] = True
        self.assertTrue(self.trigger_matches("ADISCORD_south_nam_focus_ready", "NAM"))
        tree = focus_blocks(ROOT / "focus_trees/NAM/defeated/focuses.txt")
        offensive = tree["NAM_defeat_southern_charter"]
        for prerequisite in (entry.value for entry in offensive if entry.key == "prerequisite"):
            self.assertTrue(any(self.facts.get(("NAM", "has_completed_focus", child.value), False)
                                for child in prerequisite))
        self.assertLessEqual(float(scalar(offensive, "cost")) * 7, 56)

    def test_northern_successors_require_resource_war_settlement(self):
        self.facts[("NAM", "exists", "yes")] = False
        self.flag("ADISCORD_nam_resource_war_resolved", False)
        self.flag("ADISCORD_nam_resource_war_retry_used")
        for leader in ("EFL", "AZH"):
            with self.subTest(leader=leader):
                self.facts[("EFL", "exists", "yes")] = leader == "EFL"
                self.assertTrue(self.trigger_matches("ADISCORD_south_declarer_valid", leader))
                self.assertFalse(self.trigger_matches("ADISCORD_south_north_focus_ready", leader))
                self.flag("ADISCORD_nam_resource_war_resolved")
                self.assertTrue(self.trigger_matches("ADISCORD_south_north_focus_ready", leader))
                self.flag("ADISCORD_nam_resource_war_resolved", False)

    def test_northern_successors_wait_for_2165_and_every_shl_milestone(self):
        self.facts[("NAM", "exists", "yes")] = False
        self.execute("ADISCORD_south_begin_preparation")
        self.flag("ADISCORD_south_crisis_warned", age=84)
        for leader in ("EFL", "AZH"):
            with self.subTest(leader=leader):
                self.facts[("EFL", "exists", "yes")] = leader == "EFL"
                for date, expected in ((21641231, False), (21650101, True)):
                    for starter in (leader, "SHL"):
                        self.facts[(starter, "numeric", "date")] = date
                        self.assertEqual(self.trigger_matches("ADISCORD_south_final_focus_available", starter), expected)
                        self.assertEqual(self.trigger_matches("ADISCORD_south_final_can_start", starter), expected)
                    self.calls.clear()
                    self.execute("ADISCORD_south_crisis_cycle")
                    self.assertEqual("ADISCORD_south_final_war_start" in self.calls, expected)
                for focus in ("SHL_conclave_rules", "SHL_metal_market", "SHL_conclave_army"):
                    self.facts[("SHL", "has_completed_focus", focus)] = False
                    for starter in (leader, "SHL"):
                        self.assertFalse(self.trigger_matches("ADISCORD_south_final_focus_available", starter), focus)
                        self.assertFalse(self.trigger_matches("ADISCORD_south_final_can_start", starter), focus)
                    self.calls.clear()
                    self.execute("ADISCORD_south_crisis_cycle")
                    self.assertNotIn("ADISCORD_south_final_war_start", self.calls, focus)
                    self.facts[("SHL", "has_completed_focus", focus)] = True

    def test_repeated_initialization_preserves_age_and_does_not_reactivate_missions(self):
        self.execute("ADISCORD_south_begin_preparation")
        self.flag("ADISCORD_south_preparation_started", age=200)
        self.calls.clear()
        self.execute("ADISCORD_south_begin_preparation")
        self.assertEqual(self.facts[("GLB", "flag_days", "ADISCORD_south_preparation_started")], 200)
        self.assertEqual(self.calls, [])
        self.execute("ADISCORD_south_suspend_preparation")
        for tag in ("NAM", "SHL", "EFL", "AZH"):
            self.assertFalse(self.facts[(tag, "mission", "ADISCORD_south_preparation")])
        self.execute("ADISCORD_south_begin_preparation")
        self.assertEqual(self.facts[("GLB", "flag_days", "ADISCORD_south_preparation_started")], 0)

    def test_exile_return_and_great_war_block_every_clock_and_first_strike(self):
        self.flag("ADISCORD_nam_resource_war_island_exile")
        self.flag("ADISCORD_south_preparation_started", age=2000)
        self.flag("ADISCORD_south_crisis_warned", age=84)
        self.variable("ADISCORD_south_crisis", 100)
        self.facts.update({("RHM", "exists", "yes"): True, ("RHM", "is_subject", "no"): True,
                           ("RHM", "has_capitulated", "no"): True})
        for phase in ("islands", "return", "consolidation", "great_war", "complete"):
            self.flag("NAM_war_of_return_started", phase == "return")
            self.flag("NAM_war_of_return_won", phase in ("consolidation", "great_war", "complete"))
            self.flag("NAM_great_war_started", phase == "great_war")
            self.flag("NAM_great_war_won", phase == "complete")
            self.calls.clear()
            for tag in ("NAM", "SHL"):
                self.assertEqual(self.trigger_matches("ADISCORD_south_final_can_start", tag), phase == "complete", phase)
            self.execute("ADISCORD_south_crisis_cycle")
            self.assertEqual("ADISCORD_south_final_war_start" in self.calls, phase == "complete", phase)
        self.flag("NAM_great_war_won", False)
        self.facts[("RHM", "exists", "yes")] = False
        self.facts[("EFL", "exists", "yes")] = False
        self.facts[("AZH", "exists", "yes")] = False
        self.assertTrue(self.trigger_matches("ADISCORD_south_crisis_open"), "No remaining great-war opponents")

    def test_dead_exile_releases_fallback_but_living_capitulated_exile_does_not(self):
        self.flag("ADISCORD_nam_resource_war_island_exile")
        self.facts[("NAM", "has_capitulated", "no")] = False
        self.assertFalse(self.trigger_matches("ADISCORD_south_crisis_open"))
        self.facts[("NAM", "exists", "yes")] = False
        self.execute("ADISCORD_south_begin_preparation")
        self.assertTrue(self.trigger_matches("ADISCORD_south_crisis_open"))
        self.execute("ADISCORD_south_select_north_leader")
        self.assertTrue(self.facts[("EFL", "has_country_flag", "ADISCORD_south_north_leader")])
        self.assertFalse(self.facts[("NAM", "has_country_flag", "ADISCORD_south_north_leader")])
        self.assertFalse(self.trigger_matches("ADISCORD_south_final_can_start"))
        self.flag("ADISCORD_south_preparation_started", age=1460)
        self.flag("ADISCORD_south_crisis_warned", age=56)
        self.assertTrue(self.trigger_matches("ADISCORD_south_final_can_start"))

    def objectives(self, north="NAM", capital="700"):
        self.facts[(north, "has_country_flag", "ADISCORD_south_north_leader")] = True
        self.variable("ADISCORD_south_side", 2, north)
        self.variable("ADISCORD_south_side", 1, "SHL")
        self.facts[(north, "capital")] = capital
        self.facts[("SHL", "capital")] = "699"
        for state in ("67", "688", capital):
            self.facts[(state, "controller")] = north
        for state in ("699", "707"):
            self.facts[(state, "controller")] = "SHL"
        self.execute("ADISCORD_south_record_key_states")

    def test_subjugated_nam_joins_its_champion_and_counts_for_objectives_and_settlement(self):
        for north, capital in (("EFL", "68"), ("AZH", "69")):
            for overlord in (north, "SHL"):
                for already_fighting in (False, True):
                    with self.subTest(north=north, overlord=overlord, already_fighting=already_fighting):
                        self.setUp()
                        self.facts[("NAM", "is_subject", "no")] = False
                        self.facts[("NAM", "is_subject", "yes")] = True
                        self.facts[("NAM", "is_subject_of", overlord)] = True
                        self.objectives(north, capital)
                        enemy = north if overlord == "SHL" else "SHL"
                        side = 1 if overlord == "SHL" else 2
                        self.facts[("NAM", "has_war_with", enemy)] = already_fighting
                        self.execute("ADISCORD_south_assign_bound_sides")
                        self.assertEqual(self.facts.get(("NAM", "variable", "ADISCORD_south_side")), side)
                        expected_calls = [] if already_fighting else [("NAM", "add_to_war", overlord, enemy)]
                        self.assertEqual(self.calls, expected_calls)
                        self.calls.clear()
                        self.execute("ADISCORD_south_assign_bound_sides")
                        self.assertEqual(self.calls, [], "An assigned participant must not join again")

                        self.facts[("688", "controller")] = "NAM"
                        self.execute("ADISCORD_south_record_key_states")
                        self.assertEqual(self.facts[("688", "variable", "ADISCORD_south_initial_side")], side)
                        for winner in (1, 2):
                            self.variable("ADISCORD_south_winner_side", winner)
                            selected = list(selected_effects(self.expand(self.effects["ADISCORD_south_mark_loser"]), self.facts, "NAM"))
                            pending = [(tag, item.value) for tag, item in selected if item.key == "set_country_flag"]
                            expected = [] if winner == side else [("NAM", "ADISCORD_south_settlement_pending")]
                            self.assertEqual(pending, expected)
                            release = [item.value for _, item in selected if item.key == "overlord"]
                            self.assertEqual(len(release), int(winner != side))
                            if release:
                                autonomy = block(release[0], "set_autonomy")
                                self.assertEqual(scalar(autonomy, "target"), "PREV")
                                self.assertEqual(scalar(autonomy, "autonomy_state"), "autonomy_free")

    def test_bound_assignment_preserves_nam_leadership_and_ignores_absent_nam(self):
        for exists in (False, True):
            with self.subTest(exists=exists):
                self.setUp()
                self.facts[("NAM", "exists", "yes")] = exists
                if exists:
                    self.objectives()
                else:
                    self.objectives("EFL", "68")
                self.execute("ADISCORD_south_assign_bound_sides")
                self.assertEqual(self.calls, [])
                self.assertEqual(self.facts.get(("NAM", "variable", "ADISCORD_south_side")), 2 if exists else None)

    def test_static_front_never_creates_a_hegemon_for_either_declarer(self):
        for north, capital in (("NAM", "700"), ("EFL", "688"), ("AZH", "69")):
            for declarer in (1, 2):
                self.setUp()
                self.objectives(north, capital)
                self.variable("ADISCORD_south_declarer_side", declarer)
                self.execute("ADISCORD_south_final_resolve_by_control")
                self.assertEqual(self.calls, ["ADISCORD_south_final_repel"], (north, declarer))
                roster = self.arrays["global.ADISCORD_south_key_states"]
                self.assertEqual(len(roster), len(set(roster)))

    def test_only_enemy_key_captures_score_and_recovery_removes_the_point(self):
        self.objectives()
        for state, controller, result in (("67", "SHL", "shl_victory"), ("699", "NAM", "north_victory")):
            original = self.facts[(state, "controller")]
            self.facts[(state, "controller")] = controller
            self.calls.clear()
            self.execute("ADISCORD_south_final_resolve_by_control")
            self.assertEqual(self.calls, ["ADISCORD_south_final_resolve_" + result])
            self.facts[(state, "controller")] = original
            self.calls.clear()
            self.execute("ADISCORD_south_final_resolve_by_control")
            self.assertEqual(self.calls, ["ADISCORD_south_final_repel"])
        self.facts[("67", "controller")] = "SHL"
        self.facts[("699", "controller")] = "NAM"
        self.calls.clear()
        self.execute("ADISCORD_south_final_resolve_by_control")
        self.assertEqual(self.calls, ["ADISCORD_south_final_repel"], "Equal captures")

    def test_neutral_key_and_late_alliance_cannot_manufacture_progress(self):
        self.objectives()
        self.facts[("688", "controller")] = "WEF"
        self.execute("ADISCORD_south_record_key_states")
        self.assertNotIn("688", self.arrays["global.ADISCORD_south_key_states"])
        self.variable("ADISCORD_south_side", 1, "WEF")
        self.execute("ADISCORD_south_final_resolve_by_control")
        self.assertEqual(self.calls, ["ADISCORD_south_final_repel"])
        roster = list(self.arrays["global.ADISCORD_south_key_states"])
        self.execute("ADISCORD_south_clear_key_states")
        self.assertEqual(self.arrays["global.ADISCORD_south_key_states"], [])
        for state in roster:
            self.assertFalse(self.facts[(state, "has_variable", "ADISCORD_south_initial_side")])

    def test_mission_cannot_succeed_early_or_lose_its_clock_on_liberation(self):
        decisions = definitions(ROOT / "common/decisions/ADISCORD_nam_resource_war_decisions.txt")
        mission = block(decisions["ADISCORD_south_final_war_category"], "ADISCORD_south_preparation")
        self.assertEqual(scalar(mission, "days_mission_timeout"), "56")
        self.assertFalse(self.matches(block(mission, "available")))
        self.flag("ADISCORD_south_preparation_started", age=150)
        self.flag("ADISCORD_nam_resource_war_island_exile")
        self.assertFalse(self.matches(block(mission, "visible")))
        self.assertFalse(self.matches(block(mission, "cancel_trigger")))
        self.flag("ADISCORD_south_final_started")
        self.assertTrue(self.matches(block(mission, "cancel_trigger")))

    def test_every_diplomatic_focus_and_delayed_reply_respects_the_story_gate(self):
        for relative in ("NAM/postwar/focuses.txt", "NAM/defeated/focuses.txt", "SHL/main/focuses.txt"):
            for name, focus in focus_blocks(ROOT / "focus_trees" / relative).items():
                reward = repr(block(focus, "completion_reward"))
                if any(effect in reward for effect in ("ADISCORD_south_demand_submission", "ADISCORD_south_offer_alliance", "ADISCORD_south_demand_annexation")):
                    self.assertIn("ADISCORD_south_nam_story_clear", repr(block(focus, "available")), name)
                if "ADISCORD_south_prepare_offensive" in reward:
                    self.assertIn("ADISCORD_south_final_started", repr(block(focus, "bypass")), name)
        for name in ("ADISCORD_south_accept_offer", "ADISCORD_south_refuse_offer", "ADISCORD_south_finalize_submission"):
            self.assertIn("ADISCORD_south_nam_story_clear", body(EFFECTS, name))
        events = {scalar(e.value, "id"): e.value for e in parse_clausewitz(EVENTS.read_text(encoding="utf-8"))
                  if e.key in ("country_event", "news_event")}
        self.assertIn("ADISCORD_south_offer_target", repr(events["ADISCORD_south.46"]))
        self.assertIn("ADISCORD_south_nam_story_clear", repr(events["ADISCORD_south.46"]))
        self.assertIn("28", repr(events["ADISCORD_south.41"]))

    def test_deferred_offers_preserve_each_recipient_sender_and_unattended_exit(self):
        events = {scalar(e.value, "id"): e.value for e in parse_clausewitz(EVENTS.read_text(encoding="utf-8"))
                  if e.key in ("country_event", "news_event")}
        self.execute("ADISCORD_south_queue_offer", "EFL")
        self.execute("ADISCORD_south_queue_offer", "AZH")
        first, second = self.calls
        self.assertEqual(first[-1]["ADISCORD_south_offer_target"], "EFL")
        self.assertEqual(second[-1]["ADISCORD_south_offer_target"], "AZH")
        for packet in (first, second):
            self.targets = dict(packet[-1])
            recipient = self.targets["ADISCORD_south_offer_target"]
            self.variable("ADISCORD_south_offer_kind", 1, recipient)
            self.flag("ADISCORD_nam_resource_war_island_exile")
            self.event_root = "SHL"
            self.calls.clear()
            self.execute_entries(block(events["ADISCORD_south.46"], "immediate"), "SHL")
            self.assertEqual(self.calls[0][:4], ("SHL", "country_event", "ADISCORD_south.46", "SHL"))
            self.assertEqual(self.calls[0][-1], packet[-1])
            self.assertTrue(self.facts[(recipient, "has_variable", "ADISCORD_south_offer_kind")])
            self.flag("ADISCORD_nam_resource_war_island_exile", False)
            self.calls.clear()
            self.execute_entries(block(events["ADISCORD_south.46"], "immediate"), "SHL")
            self.assertEqual(self.calls[0][:4], (recipient, "country_event", "ADISCORD_south.40", "SHL"))
            # If the story changes while the visible event is open, both an
            # immediate click and an unattended choice have one safe response.
            self.flag("ADISCORD_nam_resource_war_island_exile")
            self.event_root = recipient
            options = [e.value for e in events["ADISCORD_south.40"] if e.key == "option"
                       and self.matches(block(e.value, "trigger"), recipient)]
            self.assertEqual([scalar(o, "name") for o in options], ["ADISCORD_south.40.closed"])
            self.calls.clear()
            self.execute_entries(block(options[0], "hidden_effect"), recipient)
            self.assertEqual(self.calls[0][:3], ("SHL", "country_event", "ADISCORD_south.46"))
            self.assertTrue(self.facts[(recipient, "has_variable", "ADISCORD_south_offer_kind")])

    def test_accepted_submission_waits_without_erasing_its_choice(self):
        events = {scalar(e.value, "id"): e.value for e in parse_clausewitz(EVENTS.read_text(encoding="utf-8"))
                  if e.key in ("country_event", "news_event")}
        self.flag("ADISCORD_nam_resource_war_island_exile")
        self.facts[("EFL", "has_country_flag", "ADISCORD_south_submits_to_SHL")] = True
        self.execute_entries(block(events["ADISCORD_south.41"], "immediate"), "EFL")
        self.assertEqual(self.calls[0][:3], ("EFL", "country_event", "ADISCORD_south.41"))
        self.assertTrue(self.facts[("EFL", "has_country_flag", "ADISCORD_south_submits_to_SHL")])

    def test_accepted_contract_blocks_replacement_and_expires_on_new_settlement(self):
        events = {scalar(e.value, "id"): e.value for e in parse_clausewitz(EVENTS.read_text(encoding="utf-8"))
                  if e.key == "country_event"}
        for sender in ("SHL", "NAM"):
            for invalid in ("foreign_faction", "subject", "capitulated", "sender_gone", "war"):
                self.setUp()
                self.event_root = sender
                receipt = "ADISCORD_south_submits_to_" + sender
                self.facts[("EFL", "has_country_flag", receipt)] = True
                self.assertFalse(self.trigger_matches("ADISCORD_south_campaign_target_valid", "EFL"))
                self.flag("ADISCORD_nam_resource_war_island_exile")
                if invalid == "foreign_faction":
                    self.facts[("EFL", "is_in_faction", "no")] = False
                elif invalid == "subject":
                    self.facts[("EFL", "is_subject", "no")] = False
                elif invalid == "capitulated":
                    self.facts[("EFL", "has_capitulated", "no")] = False
                elif invalid == "sender_gone":
                    self.facts[(sender, "exists", "yes")] = False
                else:
                    self.facts[("EFL", "has_war_with", sender)] = True
                self.assertFalse(self.trigger_matches("ADISCORD_south_submission_pending_valid", "EFL"), (sender, invalid))
                self.execute_entries(block(events["ADISCORD_south.41"], "immediate"), "EFL")
                self.assertEqual(self.calls, [], (sender, invalid))
                self.assertFalse(self.facts[("EFL", "has_country_flag", receipt)])
        self.setUp()
        self.facts[("EFL", "has_country_flag", "ADISCORD_south_submits_to_SHL")] = True
        self.assertFalse(self.trigger_matches("ADISCORD_south_campaign_target_valid", "EFL"))
        self.facts[("EFL", "has_country_flag", "ADISCORD_south_submits_to_SHL")] = False
        self.assertTrue(self.trigger_matches("ADISCORD_south_campaign_target_valid", "EFL"))

    def test_stale_offers_close_at_dispatch_and_at_visible_answer(self):
        events = {scalar(e.value, "id"): e.value for e in parse_clausewitz(EVENTS.read_text(encoding="utf-8"))
                  if e.key == "country_event"}
        for invalid in ("subject", "capitulated", "ally", "war", "sender_gone", "resolved"):
            for kind in (1, 2, 3):
                self.setUp()
                self.targets["ADISCORD_south_offer_target"] = "EFL"
                self.variable("ADISCORD_south_offer_kind", kind, "EFL")
                if invalid in ("subject", "capitulated"):
                    key = "is_subject" if invalid == "subject" else "has_capitulated"
                    self.facts[("EFL", key, "no")] = False
                elif invalid in ("ally", "war"):
                    key = "is_in_faction_with" if invalid == "ally" else "has_war_with"
                    self.facts[("EFL", key, "SHL")] = True
                elif invalid == "sender_gone":
                    self.facts[("SHL", "exists", "yes")] = False
                else:
                    self.flag("ADISCORD_south_final_resolved")
                self.execute_entries(block(events["ADISCORD_south.46"], "immediate"), "SHL")
                self.assertEqual(self.calls, [], (invalid, kind))
                self.assertFalse(self.facts[("EFL", "has_variable", "ADISCORD_south_offer_kind")])
                self.variable("ADISCORD_south_offer_kind", kind, "EFL")
                self.event_root = "EFL"
                options = [e.value for e in events["ADISCORD_south.40"] if e.key == "option"
                           and self.matches(block(e.value, "trigger"), "EFL")]
                self.assertEqual([scalar(o, "name") for o in options], ["ADISCORD_south.40.closed"])
                self.execute_entries(block(options[0], "hidden_effect"), "EFL")
                self.assertEqual(self.calls, [], (invalid, kind))
                self.assertFalse(self.facts[("EFL", "has_variable", "ADISCORD_south_offer_kind")])
                for effect in ("ADISCORD_south_accept_offer", "ADISCORD_south_refuse_offer"):
                    self.variable("ADISCORD_south_offer_kind", kind, "EFL")
                    self.execute(effect, "EFL")
                    self.assertEqual(self.calls, [], (effect, invalid, kind))

    def test_submission_finalizer_uses_the_same_current_contract_guard(self):
        finalizer = self.effects["ADISCORD_south_finalize_submission"]
        branches = [e.value for e in finalizer if e.key in ("if", "else_if")]
        for branch, sender in zip(branches, ("SHL", "NAM")):
            self.assertIn("ADISCORD_south_submission_to_" + sender.lower() + "_valid", repr(block(branch, "limit")))


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
    TREES = (
        ROOT / "focus_trees/NAM/main/focuses.txt",
        ROOT / "focus_trees/NAM/wartime/focuses.txt",
        ROOT / "focus_trees/NAM/postwar/focuses.txt",
        ROOT / "focus_trees/NAM/defeated/focuses.txt",
        ROOT / "focus_trees/SHL/main/focuses.txt",
    )
    REFRESH = {
        "NAM_administration_dynamic": "NAM_refresh_administration",
        "NAM_garrison_dynamic": "NAM_refresh_garrison",
        "NAM_navy_dynamic": "NAM_refresh_navy",
        "NAM_air_dynamic": "NAM_refresh_air",
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
        self.assertEqual(checked, 69)

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
            if name not in ("NAM_navy_dynamic", "NAM_air_dynamic"):
                self.assertIn("ADISCORD_economy_mark_dirty = yes", source)
            self.assertNotIn("set_variable", source)


if __name__ == "__main__":
    unittest.main()
