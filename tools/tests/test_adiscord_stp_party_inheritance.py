"""Party war inheritance contracts: heirs, strain, front crises and the victor.

These tests inspect authored scripts, not the Clausewitz runtime.
"""

from pathlib import Path
import json
import re
import unittest

from tools.lib.focus_sources import read_focus_source
from tools.validators.validate_adiscord_division_templates import parse_clausewitz

ROOT = Path(__file__).resolve().parents[2]
PREPARATION = "focus_trees/STP/preparation/focuses.txt"
CIVIL_WAR = "focus_trees/STP/civil_war/focuses.txt"
EFFECTS = "common/scripted_effects/ADISCORD_STP_scripted_effects.txt"
TRIGGERS = "common/scripted_triggers/ADISCORD_STP_scripted_triggers.txt"
DECISIONS = "common/decisions/ADISCORD_STP_decisions.txt"
EVENTS = "events/ADISCORD_STP_events.txt"
IDEAS = "common/ideas/ADISCORD_STP_civil_war_ideas.txt"
DYNAMIC = "common/dynamic_modifiers/ADISCORD_dynamic_modifiers_STP.txt"
SCRIPTED_LOC = "common/scripted_localisation/ADISCORD_STP_scripted_loc.txt"
SUPEREVENT_LOC = "common/scripted_localisation/ADISCORD_scripted_loc_superevents.txt"
CHARACTERS = "common/characters/STP.txt"
PORTRAITS = "interface/ADISCORD_leader_portraits.gfx"
ON_ACTIONS = "common/on_actions/02_ADISCORD_STP_on_actions.txt"
REGISTRY = "tools/data/adiscord_event_ids.json"
RU = "localisation/russian/ADISCORD_STP_l_russian.yml"
EN = "localisation/english/ADISCORD_STP_l_english.yml"
SUPER_RU = "localisation/russian/ADISCORD_superevents_l_russian.yml"
SUPER_EN = "localisation/english/ADISCORD_superevents_l_english.yml"

HEIR_FOCUSES = (
    "STP_ph_six_chairs",
    "STP_ph_pen_of_staff",
    "STP_ph_pen_of_silence",
    "STP_ph_pen_of_houses",
    "STP_ph_last_signature",
    "STP_ph_heirs_pact",
    "STP_ph_empty_chair",
)
WAR_FOCUSES = (
    "STP_pv_war_budget",
    "STP_pv_lower_market_ledgers",
    "STP_pv_loyalty_tribunal",
    "STP_pv_victory_committee",
    "STP_pv_glory_staff",
    "STP_pv_glory_silence",
    "STP_pv_glory_festival",
    "STP_pv_glory_wallets",
)
OUTCOMES = {
    1: ("STP_pv_outcome_houses", "houses", "STP_ch_leader_1"),
    2: ("STP_pv_outcome_festival", "festival", "STP_ch_leader_2"),
    3: ("STP_pv_outcome_staff", "staff", "STP_ch_leader_3"),
    4: ("STP_pv_outcome_wallets", "wallets", "STP_ch_leader_4"),
    5: ("STP_pv_outcome_silence", "silence", "STP_ch_leader_5"),
    6: ("STP_pv_outcome_regent", "regent", "STP_ch_leader_6"),
}


def text(path):
    return (ROOT / path).read_text(encoding="utf-8-sig")


def loc_keys(path):
    keys = {}
    for line in text(path).splitlines():
        match = re.match(r'^\s+([A-Za-z0-9_.\-]+):\d*\s*"(.*)"\s*$', line)
        if match:
            keys[match.group(1)] = match.group(2)
    return keys


def top_level(path):
    return {entry.key: entry.value for entry in parse_clausewitz(text(path))}


def definition(path, name):
    source = text(path)
    start = re.search(rf"(?m)^{re.escape(name)} = {{", source)
    if not start:
        raise AssertionError(f"{name} is not defined in {path}")
    depth = 0
    for index in range(start.end() - 1, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[start.start():index + 1]
    raise AssertionError(f"{name} is not closed")


def focus_blocks(path):
    source = read_focus_source(ROOT / path)
    blocks = {}
    for match in re.finditer(r"\n\tfocus = \{", source):
        depth = 0
        for index in range(match.start() + 1, len(source)):
            if source[index] == "{":
                depth += 1
            elif source[index] == "}":
                depth -= 1
                if depth == 0:
                    body = source[match.start():index + 1]
                    focus_id = re.search(r"id = (\S+)", body).group(1)
                    blocks[focus_id] = body
                    break
    return blocks


class PartyInheritanceFocusTests(unittest.TestCase):
    def test_new_focuses_exist_and_are_localised_in_both_languages(self):
        preparation = focus_blocks(PREPARATION)
        civil_war = focus_blocks(CIVIL_WAR)
        ru = loc_keys(RU)
        en = loc_keys(EN)
        for focus_id in HEIR_FOCUSES:
            self.assertIn(focus_id, preparation)
        for focus_id in WAR_FOCUSES:
            self.assertIn(focus_id, civil_war)
        for focus_id in HEIR_FOCUSES + WAR_FOCUSES:
            for key in (focus_id, f"{focus_id}_desc"):
                self.assertTrue(ru.get(key), key)
                self.assertTrue(en.get(key), key)

    def test_heir_branch_is_party_only_and_the_pens_exclude_each_other(self):
        preparation = focus_blocks(PREPARATION)
        pens = ("STP_ph_pen_of_staff", "STP_ph_pen_of_silence", "STP_ph_pen_of_houses")
        for focus_id in HEIR_FOCUSES:
            body = preparation[focus_id]
            self.assertIn("NOT = { has_country_flag = STP_sided_with_Maksim_flag }", body)
            self.assertIn("has_country_flag = STP_sided_with_the_party_flag", body)
        for pen in pens:
            others = [other for other in pens if other != pen]
            exclusion = re.search(r"mutually_exclusive = \{([^}]*)\}", preparation[pen]).group(1)
            for other in others:
                self.assertIn(other, exclusion)
        signature = re.search(r"prerequisite = \{([^}]*)\}", preparation["STP_ph_last_signature"]).group(1)
        for pen in pens:
            self.assertIn(pen, signature)

    def test_glory_focuses_are_one_exclusive_choice_after_the_committee(self):
        civil_war = focus_blocks(CIVIL_WAR)
        glories = [focus_id for focus_id in WAR_FOCUSES if "_glory_" in focus_id]
        for glory in glories:
            body = civil_war[glory]
            self.assertIn("prerequisite = { focus = STP_pv_victory_committee }", body)
            self.assertIn("STP_pv_refresh_claims = yes", body)
            exclusion = re.search(r"mutually_exclusive = \{([^}]*)\}", body).group(1)
            for other in glories:
                if other != glory:
                    self.assertIn(other, exclusion)

    def test_war_branch_keeps_the_two_column_grid_of_the_party_war_tree(self):
        # Neighbouring focuses in this tree sit two columns apart; one column overlaps.
        civil_war = focus_blocks(CIVIL_WAR)
        positions = {}
        for focus_id, body in civil_war.items():
            if not (focus_id.startswith(("STP_pv_", "STP_ps_", "STP_party_"))):
                continue
            x = int(re.search(r"\n\t\tx = (-?\d+)", body).group(1))
            y = int(re.search(r"\n\t\ty = (-?\d+)", body).group(1))
            positions[focus_id] = (x, y)
        for focus_id in WAR_FOCUSES:
            x, y = positions[focus_id]
            for other, (other_x, other_y) in positions.items():
                if other != focus_id and other_y == y:
                    self.assertGreaterEqual(abs(other_x - x), 2, f"{focus_id} overlaps {other}")

    def test_promised_decisions_exist_and_are_localised(self):
        decisions = text(DECISIONS)
        ru = loc_keys(RU)
        en = loc_keys(EN)
        sources = focus_blocks(CIVIL_WAR)
        promised = set()
        for focus_id in WAR_FOCUSES:
            promised.update(re.findall(r"unlock_decision_tooltip = (\S+)", sources[focus_id]))
        self.assertTrue(promised)
        for decision in promised | {"STP_pv_front_1", "STP_pv_front_2", "STP_pv_front_3"}:
            self.assertRegex(decisions, rf"(?m)^\t{re.escape(decision)} = {{")
            self.assertTrue(ru.get(decision), decision)
            self.assertTrue(en.get(decision), decision)


class PartyInheritanceScriptTests(unittest.TestCase):
    def test_new_effects_and_triggers_are_defined_once(self):
        effects = text(EFFECTS)
        triggers = text(TRIGGERS)
        for name in (
            "STP_pv_begin_war",
            "STP_pv_refresh_strain",
            "STP_pv_change_strain",
            "STP_pv_monthly",
            "STP_pv_check_strain_thresholds",
            "STP_pv_check_bloc_crisis",
            "STP_pv_count_heartland",
            "STP_pv_schedule_front",
            "STP_pv_start_front",
            "STP_pv_resolve_front",
            "STP_pv_front_success",
            "STP_pv_front_failure",
            "STP_pv_refresh_claims",
            "STP_pv_resolve_victory",
            "STP_pv_install_victor",
            "STP_pv_apply_victory_terms",
            "STP_pv_close_war",
        ):
            self.assertEqual(len(re.findall(rf"(?m)^{name} = {{", effects)), 1, name)
        for name in (
            "STP_pv_war_current",
            "STP_pv_front_active",
            "STP_pv_advisers_have_voice",
            "STP_pv_kefreyt_offer_possible",
        ):
            self.assertEqual(len(re.findall(rf"(?m)^{name} = {{", triggers)), 1, name)

    def test_prewar_choices_survive_the_civil_war_tree_replacement(self):
        # STP_cw_start loads the civil-war tree without keeping prewar completions.
        self.assertIn(
            "load_focus_tree = { tree = STP_cw_focus keep_completed = no }",
            definition(EFFECTS, "STP_cw_start"),
        )
        for path in (EFFECTS, TRIGGERS, DECISIONS, EVENTS, CIVIL_WAR):
            self.assertNotIn("has_completed_focus = STP_ph_", text(path), path)
        preparation = focus_blocks(PREPARATION)
        for focus_id, marker in (
            ("STP_ph_pen_of_staff", "set_variable = { var = STP_ph_heir value = 3 }"),
            ("STP_ph_pen_of_silence", "set_variable = { var = STP_ph_heir value = 5 }"),
            ("STP_ph_pen_of_houses", "set_variable = { var = STP_ph_heir value = 1 }"),
            ("STP_ph_last_signature", "set_country_flag = STP_ph_heir_signed"),
            ("STP_ph_heirs_pact", "set_variable = { var = STP_ph_heir_settlement value = 1 }"),
            ("STP_ph_empty_chair", "set_variable = { var = STP_ph_heir_settlement value = 2 }"),
        ):
            self.assertIn(marker, preparation[focus_id], focus_id)
        close = definition(EFFECTS, "STP_pv_close_war")
        for cleanup in (
            "clr_country_flag = STP_ph_heir_signed",
            "clear_variable = STP_ph_heir",
            "clear_variable = STP_ph_heir_settlement",
        ):
            self.assertIn(cleanup, close)

    def test_war_start_monthly_tick_and_both_victories_are_wired(self):
        self.assertIn("STP_pv_begin_war = yes", definition(EFFECTS, "STP_ps_begin_defence"))
        self.assertIn("STP_pv_monthly = yes", text(ON_ACTIONS))
        for settlement in ("STP_cw_settle_union_victory", "STP_cw_settle_nod_victory"):
            body = definition(EFFECTS, settlement)
            resolve = body.index("STP_pv_resolve_victory = yes")
            report = body.index("ADISCORD_STP_cw.71")
            self.assertLess(resolve, report, settlement)
        union = definition(EFFECTS, "STP_cw_settle_union_victory")
        self.assertLess(union.index("annex_country"), union.index("STP_pv_resolve_victory"))

    def test_every_outcome_has_a_leader_an_idea_and_a_super_event_variant(self):
        install = definition(EFFECTS, "STP_pv_install_victor")
        terms = definition(EFFECTS, "STP_pv_apply_victory_terms")
        ideas = text(IDEAS)
        superevent_loc = text(SUPEREVENT_LOC)
        ru = loc_keys(RU)
        en = loc_keys(EN)
        super_ru = loc_keys(SUPER_RU)
        super_en = loc_keys(SUPER_EN)
        for outcome, (idea, name, leader) in OUTCOMES.items():
            self.assertIn(f"{leader} = yes", install)
            self.assertIn(f"idea = {idea}", terms)
            self.assertRegex(ideas, rf"(?m)^\t\t{idea} = {{")
            self.assertTrue(ru.get(idea) and en.get(idea), idea)
            for kind in ("title", "quote", "comment"):
                key = f"superevent_stelander_party_victory_{name}_{kind}"
                self.assertIn(f"localization_key = {key}", superevent_loc)
                self.assertTrue(super_ru.get(key) and super_en.get(key), key)
            self.assertIn(
                f"STP = {{ check_variable = {{ var = STP_pv_outcome value = {outcome} compare = equals }} }}",
                superevent_loc,
            )
            for key in (f"ADISCORD_STP_pv.50.t{outcome}", f"ADISCORD_STP_pv.50.d{outcome}"):
                self.assertTrue(ru.get(key) and en.get(key), key)

    def test_congress_reads_the_victory_mandate(self):
        recount = definition(EFFECTS, "STP_ch_recount")
        for candidate in range(1, 6):
            self.assertIn(f"add_to_variable = {{ var = STP_ch_votes_{candidate} value = 10 }}", recount)
        leader = definition(EFFECTS, "STP_ch_leader_1")
        self.assertIn("character = STP_Cyan_Crowe", leader)

    def test_future_party_leaders_are_dormant_until_their_outcome(self):
        history = text("history/countries/STP - StepanLand.txt")
        effects = text(EFFECTS)
        characters = {
            entry.key: entry.value for entry in top_level(CHARACTERS)["characters"]
        }
        for candidate, character in (
            (1, "STP_Cyan_Crowe"),
            (4, "STP_Pavel_Lanskoy"),
            (5, "STP_Vera_Korvina"),
            (6, "STP_Edgar_Renner"),
        ):
            with self.subTest(character=character):
                self.assertEqual(history.count(f"recruit_character = {character}"), 1)
                self.assertNotIn(f"recruit_character = {character}", effects)
                self.assertNotIn(
                    "country_leader", {entry.key for entry in characters[character]}
                )
                leader = definition(EFFECTS, f"STP_ch_leader_{candidate}")
                self.assertIn("add_country_leader_role = {", leader)
                self.assertIn(
                    f"NOT = {{ has_country_leader = {{ character = {character} }} }}",
                    leader,
                )
                self.assertIn("promote_character = {", leader)
                self.assertLess(
                    leader.index("add_country_leader_role = {"),
                    leader.index("promote_character = {"),
                )

    def test_new_portraits_and_character_resolve_to_files(self):
        portraits = text(PORTRAITS)
        for sprite in (
            "GFX_portrait_STP_Cyan_Crowe",
            "GFX_portrait_STP_Rufus_Hedersett_marshal",
            "GFX_portrait_STP_Rufus_Hedersett_uniform",
        ):
            match = re.search(rf'name = "{sprite}"\s*texturefile = "([^"]+)"', portraits)
            self.assertIsNotNone(match, sprite)
            self.assertTrue((ROOT / match.group(1)).is_file(), match.group(1))
        self.assertRegex(text(CHARACTERS), r"(?m)^\tSTP_Cyan_Crowe = \{")

    def test_close_war_clears_every_transient_flag_it_owns(self):
        effects = text(EFFECTS)
        close = definition(EFFECTS, "STP_pv_close_war")
        section = effects[effects.index("# PARTY WAR: INHERITANCE OF THE FESTIVAL"):]
        flags = set(re.findall(r"set_country_flag = (?:\{ flag = )?(STP_pv_[A-Za-z_]+)", section))
        flags.update(re.findall(r"set_country_flag = (?:\{ flag = )?(STP_pv_[A-Za-z_]+)", text(EVENTS)))
        flags.update(re.findall(r"set_country_flag = (?:\{ flag = )?(STP_pv_[A-Za-z_]+)", text(DECISIONS)))
        self.assertTrue(flags)
        for flag in flags:
            self.assertIn(f"clr_country_flag = {flag}", close, flag)

    def test_strain_modifier_uses_the_refreshed_variables(self):
        dynamic = text(DYNAMIC)
        block = dynamic[dynamic.index("STP_pv_strain_dynamic = {"):]
        block = block[:block.index("\n}") + 2]
        for variable in (
            "STP_pv_strain_political_power",
            "STP_pv_strain_stability",
            "STP_pv_strain_income",
        ):
            self.assertIn(variable, block)
            self.assertIn(f"var = {variable}", definition(EFFECTS, "STP_pv_refresh_strain"))


class PartyInheritanceEventTests(unittest.TestCase):
    def test_events_are_registered_and_every_displayed_key_is_localised(self):
        events = text(EVENTS)
        section = events[events.index("add_namespace = ADISCORD_STP_pv"):]
        ids = re.findall(r"id = (ADISCORD_STP_pv\.\d+)", section)
        registry = {
            entry["id"]
            for entry in json.loads(text(REGISTRY))["events"]
        }
        self.assertTrue(ids)
        for event_id in ids:
            self.assertIn(event_id, registry)
        keys = set(re.findall(r"(?:title|desc|name|text) = (ADISCORD_STP_pv\.[A-Za-z0-9_.]+)", section))
        keys.update(re.findall(r"custom_effect_tooltip = (ADISCORD_STP_pv\.[A-Za-z0-9_.]+)", section))
        ru = loc_keys(RU)
        en = loc_keys(EN)
        for key in keys:
            self.assertTrue(ru.get(key), key)
            self.assertTrue(en.get(key), key)

    def test_custom_tooltips_and_scripted_texts_resolve(self):
        ru = loc_keys(RU)
        en = loc_keys(EN)
        sources = "\n".join(
            text(path)
            for path in (EFFECTS, DECISIONS, EVENTS, PREPARATION, CIVIL_WAR)
        )
        for key in set(re.findall(r"custom_effect_tooltip = (STP_p[hv]_[A-Za-z0-9_]+)", sources)):
            self.assertTrue(ru.get(key), key)
            self.assertTrue(en.get(key), key)
        scripted = text(SCRIPTED_LOC)
        for name in ("STPGetWarStrainReport", "STPGetVictoryClaimant", "STPGetVictoryAftertaste"):
            self.assertIn(f"name = {name}", scripted)
        for key in set(re.findall(r"localization_key = (STP_pv_[A-Za-z0-9_]+)", scripted)):
            self.assertIn(key, ru)
            self.assertIn(key, en)

    def test_russian_values_stay_within_the_editorial_ceiling(self):
        for key, value in loc_keys(RU).items():
            if not (key.startswith("ADISCORD_STP_pv.") or key.startswith("STP_pv_") or key.startswith("STP_ph_")):
                continue
            rendered = value.replace("\\n", "\n")
            self.assertLessEqual(len(rendered), 3000, key)
            self.assertLessEqual(len(rendered.encode("utf-8")), 5500, key)


class PostwarLeaderProgrammeTests(unittest.TestCase):
    """Evaluate authored route predicates and focus graphs for current campaigns."""

    @classmethod
    def setUpClass(cls):
        from tools.tests.test_adiscord_stp_party_route import one

        cls.one = staticmethod(one)
        cls.triggers = top_level(TRIGGERS)
        cls.effects = top_level(EFFECTS)
        cls.focus = {
            one(entry.value, "id"): entry.value
            for entry in parse_clausewitz(text("focus_trees/STP/postwar/party/focuses.txt"))
            if entry.key == "focus"
        }

    def expanded(self, entries):
        from dataclasses import replace

        result = []
        for entry in entries:
            if entry.key.startswith("STP_party_leader_"):
                self.assertIn(entry.key, self.triggers)
                body = self.expanded(self.triggers[entry.key])
                result.append(replace(entry, key="AND" if entry.value == "yes" else "NOT", value=body))
            elif isinstance(entry.value, list):
                result.append(replace(entry, value=self.expanded(entry.value)))
            else:
                result.append(entry)
        return result

    def facts(self, victor, government=None, protectorate=False):
        facts = {
            ("STP", "STP_pf_active", "yes"): True,
            ("STP", "STP_pw_can_reconstruct", "yes"): True,
            ("STP", "has_country_flag", "STP_cw_postwar"): True,
            ("STP", "has_country_flag", "STP_ch_protectorate_leader"): protectorate,
            ("STP", "is_subject_of", "NOD"): protectorate,
            ("STP", "has_variable", "STP_pv_outcome"): True,
            ("STP", "variable", "STP_pv_outcome"): victor,
            ("STP", "has_variable", "STP_ch_government"): government is not None,
            ("STP", "variable", "STP_ch_government"): government or 0,
        }
        return facts

    def visible(self, facts):
        from tools.tests.test_adiscord_stp_preparation import matches_conditions

        result = {}
        for focus_id, focus in self.focus.items():
            branches = [entry.value for entry in focus if entry.key == "allow_branch"]
            if branches and any(entry.key.startswith("STP_party_leader_") for entry in branches[0]):
                if matches_conditions(self.expanded(branches[0]), facts):
                    result[focus_id] = focus
        return result

    def test_war_victor_opens_a_complete_programme_before_congress(self):
        roots = (
            "STP_pw_party_high_houses", "STP_pw_party_unbound_revolution",
            "STP_ch_service_act", "STP_ch_production_agreements",
            "STP_ch_security_directorate", "STP_party_regent_mandate",
        )
        for victor, root in enumerate(roots, 1):
            with self.subTest(victor=victor):
                shown = self.visible(self.facts(victor))
                self.assertIn(root, shown)
                self.assertGreaterEqual(len(shown), 10)
                # Constitutional policy and practical programmes occupy parallel lanes.
                self.assertLess(int(self.one(shown[root], "x")), 0)

    def test_congress_result_replaces_victor_and_protectorate_overrides_both(self):
        from tools.tests.test_adiscord_stp_preparation import matches_conditions

        for victor in range(1, 7):
            for government in range(1, 6):
                for protectorate in (False, True):
                    facts = self.facts(victor, government, protectorate)
                    actual = []
                    for route in range(1, 7):
                        key = f"STP_party_leader_{route}"
                        self.assertIn(key, self.triggers)
                        if matches_conditions(self.expanded(self.triggers[key]), facts):
                            actual.append(route)
                    self.assertEqual(actual, [6 if protectorate else government])

    def test_visible_programmes_have_reachable_parents_and_nonoverlapping_columns(self):
        for route in range(1, 7):
            shown = self.visible(self.facts(route))
            self.assertTrue(shown)
            positions = {}
            reached = {"STP_pw_party_new_republic"}
            for _ in range(len(shown)):
                for name, focus in shown.items():
                    parents = [entry.value for entry in focus if entry.key == "prerequisite"]
                    if all(any(e.value in reached for e in group if e.key == "focus") for group in parents):
                        reached.add(name)
            self.assertFalse(set(shown) - reached, f"route {route} has hidden or unreachable parents")
            for name, focus in shown.items():
                x, y = int(self.one(focus, "x")), int(self.one(focus, "y"))
                for other, (ox, oy) in positions.items():
                    if y == oy:
                        self.assertGreaterEqual(abs(x - ox), 2, f"{name} overlaps {other}")
                positions[name] = (x, y)

    def test_hedersett_laws_are_separate_actions_and_slavery_has_an_alternative(self):
        from tools.tests.test_adiscord_stp_preparation import selected_effects

        expected = {
            "STP_party_public_orgies": "STP_law_public_orgies",
            "STP_party_hard_drugs": "STP_law_hard_drugs",
            "STP_party_slave_market": "STP_law_slavery",
        }
        for name, law in expected.items():
            self.assertIn(name, self.focus)
            reward = self.one(self.focus[name], "completion_reward")
            payload = [entry for _, entry in selected_effects(reward, self.facts(2))]
            self.assertIn(law, [entry.value for entry in payload if entry.key == "add_ideas"])
            self.assertTrue(any(entry.key == "country_event" for entry in payload))
        for left, right in (("STP_party_slave_market", "STP_ch_free_labour"), ("STP_ch_free_labour", "STP_party_slave_market")):
            exclusions = self.one(self.focus[left], "mutually_exclusive")
            self.assertIn(right, [entry.value for entry in exclusions])
        recovery = self.one(self.focus["STP_pw_party_new_republic"], "completion_reward")
        self.assertNotIn("STP_law_slavery", [entry.value for _, entry in selected_effects(recovery, {})])

    def test_elections_preserve_policy_laws_and_paid_programme_state(self):
        from tools.tests.test_adiscord_stp_preparation import selected_effects

        laws = {"STP_law_public_orgies", "STP_law_hard_drugs", "STP_law_slavery"}
        for route in range(1, 6):
            facts = self.facts(2, route)
            facts[("STP", f"STP_ch_candidate_{route}_wins", "yes")] = True
            payload = [entry for _, entry in selected_effects(self.effects[f"STP_ch_elect_{route}"], facts)]
            removed = set()
            for entry in payload:
                if entry.key == "remove_ideas":
                    removed.update([entry.value] if isinstance(entry.value, str) else [e.value for e in entry.value])
                if entry.key in ("clear_variable", "clr_country_flag"):
                    self.assertFalse(str(entry.value).startswith("STP_party_"))
            self.assertFalse(removed & laws)

    def test_required_leader_roots_cannot_replace_existing_cultural_or_drug_laws(self):
        from tools.tests.test_adiscord_stp_preparation import selected_effects

        for route, root in ((1, "STP_pw_party_high_houses"), (2, "STP_pw_party_unbound_revolution")):
            reward = self.one(self.focus[root], "completion_reward")
            laws = [entry.value for _, entry in selected_effects(reward, self.facts(2, route))
                    if entry.key == "add_ideas"]
            self.assertNotIn("STP_law_private_societies", laws)
            self.assertNotIn("STP_law_light_drugs", laws)

    def test_liberation_replaces_the_regent_with_the_restored_leader(self):
        from tools.tests.test_adiscord_stp_preparation import matches_conditions

        for government in (None, 1, 2, 3, 4, 5):
            facts = self.facts(6, government)
            facts[("STP", "has_country_flag", "STP_ch_liberated")] = True
            actual = [route for route in range(1, 7) if matches_conditions(
                self.expanded(self.triggers[f"STP_party_leader_{route}"]), facts)]
            self.assertEqual(actual, [government or 2])

    def test_complete_postwar_layout_including_emergency_branch_has_no_overlaps(self):
        from itertools import product
        from tools.tests.test_adiscord_stp_preparation import matches_conditions

        tree = self.one(parse_clausewitz(text(CIVIL_WAR)), "focus_tree")
        focuses = {self.one(e.value, "id"): e.value for e in tree if e.key == "focus"}
        for route, phase, subject in product(range(1, 7), range(1, 8), (False, True)):
            facts = self.facts(route, route if route < 6 else None, subject)
            facts.update({("STP", "variable", "STP_ch_phase"): phase,
                          ("STP", "STP_kc_threat_current", "yes"): True,
                          ("STP", "has_country_flag", "STP_cw_party_victory"): True,
                          ("STP", "is_subject", "no"): not subject,
                          ("STP", "is_subject", "yes"): subject})

            def position(name):
                focus = focuses[name]
                x, y = float(self.one(focus, "x")), float(self.one(focus, "y"))
                for e in focus:
                    if e.key == "relative_position_id":
                        px, py = position(e.value)
                        x, y = x + px, y + py
                    elif e.key == "offset" and matches_conditions(self.one(e.value, "trigger"), facts):
                        x += sum(float(v.value) for v in e.value if v.key == "x")
                        y += sum(float(v.value) for v in e.value if v.key == "y")
                return x, y

            shown = {}
            for name, focus in focuses.items():
                gates = [e.value for e in focus if e.key == "allow_branch"]
                if not gates or matches_conditions(self.expanded(gates[0]), facts):
                    shown[name] = position(name)
            for name, (x, y) in shown.items():
                for other, (ox, oy) in shown.items():
                    if name < other and y == oy:
                        self.assertGreaterEqual(abs(x - ox), 2,
                            f"route={route}, phase={phase}, subject={subject}: {name} overlaps {other}")

    def test_delayed_social_crises_follow_laws_after_a_leadership_change(self):
        from tools.tests.test_adiscord_stp_preparation import matches_conditions, selected_effects

        events = {self.one(e.value, "id"): e.value for e in parse_clausewitz(text(EVENTS))
                  if e.key == "country_event"}
        for number, law in ((28, "STP_law_hard_drugs"), (29, "STP_law_slavery")):
            event = events[f"ADISCORD_STP_ch.{number}"]
            facts = self.facts(2, 1)
            facts[("STP", "has_idea", law)] = True
            self.assertTrue(matches_conditions(self.one(event, "trigger"), facts))
            facts[("STP", "has_idea", law)] = False
            self.assertFalse(matches_conditions(self.one(event, "trigger"), facts))
            # A window already open when its law changes offers only a no-effect close.
            options = [e.value for e in event if e.key == "option"]
            available = [o for o in options if matches_conditions(self.one(o, "trigger"), facts)]
            self.assertEqual(len(available), 1)
            changes = [e for _, e in selected_effects(available[0], facts)
                       if e.key in ("add_to_variable", "add_political_power", "add_ideas", "remove_ideas")]
            self.assertFalse(changes)
            facts[("STP", "STP_pf_active", "yes")] = False
            available = [o for o in options if matches_conditions(self.one(o, "trigger"), facts)]
            self.assertEqual([self.one(o, "name") for o in available], [f"ADISCORD_STP_ch.{number}.z"])

    def test_programme_aggregate_rewards_have_real_modifier_consumers(self):
        from tools.tests.test_adiscord_stp_party_route import walk

        dynamic = top_level("common/dynamic_modifiers/ADISCORD_dynamic_modifiers_STP.txt")["STP_pw_party_dynamic"]
        consumers = {e.value for e in dynamic if isinstance(e.value, str)}
        for route in range(1, 7):
            for name, focus in self.visible(self.facts(route)).items():
                reward = self.one(focus, "completion_reward")
                for entry in walk(reward):
                    if entry.key == "add_to_variable":
                        variable = self.one(entry.value, "var")
                        if variable.startswith("STP_pw_"):
                            self.assertIn(variable, consumers, f"{name} grants an unconnected bonus")


class PostwarDebugControlsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tools.tests.test_adiscord_stp_party_route import one

        cls.one = staticmethod(one)
        cls.decisions = {e.key: e.value for e in top_level(DECISIONS)["STP_scenario_debug"]}
        cls.triggers = top_level(TRIGGERS)
        cls.effects = top_level(EFFECTS)

    def test_programme_controls_require_a_human_debug_postwar_country(self):
        from itertools import product
        from tools.tests.test_adiscord_stp_preparation import matches_conditions

        self.assertIn("STP_debug_party_current", self.triggers)
        gate = self.triggers["STP_debug_party_current"]
        for debug, human, current, capitulated in product((False, True), repeat=4):
            facts = {("STP", "is_debug", "yes"): debug,
                     ("STP", "is_ai", "no"): human,
                     ("STP", "STP_ch_current", "yes"): current,
                     ("STP", "has_capitulated", "no"): not capitulated}
            self.assertEqual(matches_conditions(gate, facts), debug and human and current and not capitulated)
        for candidate in range(1, 6):
            name = f"STP_debug_party_leader_{candidate}"
            self.assertIn(name, self.decisions)
            decision = self.decisions[name]
            self.assertEqual(self.one(decision, "cost"), "0")
            self.assertEqual(self.one(self.one(decision, "ai_will_do"), "factor"), "0")

    def test_debug_leader_switch_preserves_laws_and_focus_progress(self):
        from tools.tests.test_adiscord_stp_preparation import selected_effects
        from tools.tests.test_adiscord_stp_party_route import walk

        self.assertIn("STP_debug_party_select_leader", self.effects)
        body = self.effects["STP_debug_party_select_leader"]
        for debug, independent in ((True, True), (False, True), (True, False)):
            facts = {("STP", "STP_debug_party_current", "yes"): debug,
                     ("STP", "is_subject", "no"): independent,
                     ("STP", "variable", "STP_debug_party_choice"): 2}
            payload = [e for _, e in selected_effects(body, facts)]
            writes = [self.one(e.value, "var") for e in payload if e.key == "set_variable"]
            self.assertEqual("STP_ch_government" in writes, debug and independent)
        for entry in walk(body):
            self.assertNotIn(entry.key, ("uncomplete_national_focus", "complete_national_focus"))
            if entry.key == "set_variable":
                self.assertEqual(self.one(entry.value, "var"), "STP_ch_government")
            if entry.key == "remove_ideas":
                self.assertNotIn("STP_law_", str(entry.value))

    def test_debug_crisis_shortcuts_respect_active_laws_and_health_protection(self):
        from tools.tests.test_adiscord_stp_preparation import matches_conditions

        for suffix, law in (("hospital_crisis", "STP_law_hard_drugs"),
                            ("labour_crisis", "STP_law_slavery")):
            name = "STP_debug_party_" + suffix
            self.assertIn(name, self.decisions)
            gate = self.one(self.decisions[name], "available")
            for law_active in (False, True):
                facts = {("STP", "STP_debug_party_current", "yes"): True,
                         ("STP", "has_idea", law): law_active}
                self.assertEqual(matches_conditions(gate, facts), law_active)
            if suffix == "hospital_crisis":
                facts[("STP", "has_completed_focus", "STP_party_festival_clinics")] = True
                self.assertFalse(matches_conditions(gate, facts))


class FrontReportTests(unittest.TestCase):
    def test_report_titles_distinguish_each_deadline_and_result(self):
        from tools.tests.test_adiscord_stp_preparation import matches_conditions, scalar

        selector = next(
            entry.value
            for entry in parse_clausewitz(text(SCRIPTED_LOC))
            if entry.key == "defined_text"
            and scalar(entry.value, "name") == "STPGetFrontResultTitle"
        )
        for stage in (1, 2, 3):
            for result in (0, 1):
                facts = {
                    ("STP", "variable", "STP_pv_front_stage"): stage,
                    ("STP", "variable", "STP_pv_front_result"): result,
                }
                selected = None
                for entry in selector:
                    if entry.key != "text":
                        continue
                    gates = [item.value for item in entry.value if item.key == "trigger"]
                    if not gates or matches_conditions(gates[0], facts, "STP"):
                        selected = scalar(entry.value, "localization_key")
                        break
                outcome = "win" if result else "loss"
                with self.subTest(stage=stage, result=result):
                    self.assertEqual(selected, f"ADISCORD_STP_pv.31.t_{outcome}{stage}")
                    for language in (RU, EN):
                        self.assertTrue(loc_keys(language).get(selected), language)


if __name__ == "__main__":
    unittest.main()
