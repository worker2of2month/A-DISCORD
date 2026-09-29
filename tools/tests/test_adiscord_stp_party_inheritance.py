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
        self.assertIn("recruit_character = STP_Cyan_Crowe", leader)

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


if __name__ == "__main__":
    unittest.main()
