from __future__ import annotations

import re
import unittest
from pathlib import Path

from tools.validators.validate_adiscord_tff_wartime import (
    BORDER_PROVINCES,
    CHARACTERS,
    COUNTRY_TAGS,
    DECISIONS,
    EFFECTS,
    EVENTS,
    HISTORY,
    ON_ACTIONS,
    PORTRAIT,
    PORTRAITS_GFX,
    collect_issues,
    event_block,
    named_block,
    read,
)


ROOT = Path(__file__).resolve().parents[2]


class TFFWartimeContractTests(unittest.TestCase):
    def test_integrated_validator_contract(self) -> None:
        self.assertEqual(collect_issues(), [])

    def test_war_hook_covers_both_directions_once(self) -> None:
        war = named_block(read(ON_ACTIONS), "on_war_relation_added")
        self.assertIn("ROOT = { tag = TFF }", war)
        self.assertIn("FROM = { tag = NOD }", war)
        self.assertIn("ROOT = { tag = NOD }", war)
        self.assertIn("FROM = { tag = TFF }", war)
        self.assertEqual(war.count("TFF_nodrul_war_crisis_started"), 2)
        self.assertLess(
            war.find("set_country_flag = TFF_nodrul_war_crisis_started"),
            war.find("country_event = { id = ADISCORD_TFF.1 }"),
        )
        self.assertNotIn("tag = VAL", war)
        self.assertNotIn("tag = YPR", war)

    def test_scripted_effect_sets_cosmetic_tag_and_promotes_colt(self) -> None:
        form = named_block(read(EFFECTS), "ADISCORD_TFF_form_wartime_confederation")
        self.assertIn("set_cosmetic_tag = TFF_frontier_defense_confederation", form)
        self.assertIn(
            "promote_character = { character = TFF_Colt_Ardent ideology = tff_emergency_war_coordinator }",
            form,
        )
        self.assertIn("set_country_flag = TFF_wartime_confederation_formed", form)
        self.assertIn("set_country_flag = TFF_wartime_command_active", form)
        self.assertNotIn("clr_country_flag = TFF_wartime_confederation_formed", form)

    def test_no_new_real_country_tag(self) -> None:
        tags = read(COUNTRY_TAGS)
        self.assertRegex(tags, r'(?m)^TFF\s*=\s*"countries/TheFreeFrontier.txt"\s*$')
        for path in (ROOT / "common/country_tags").glob("*.txt"):
            extras = re.findall(
                r'(?m)^(TFF_[A-Za-z0-9_]+)\s*=\s*"countries/',
                path.read_text(encoding="utf-8-sig"),
            )
            self.assertEqual(extras, [], path)

    def test_colt_portrait_gfx_points_at_renamed_asset(self) -> None:
        gfx = read(PORTRAITS_GFX)
        self.assertIn('name = "GFX_portrait_TFF_Colt_Ardent"', gfx)
        self.assertIn('texturefile = "gfx/leaders/TFF/portrait_TFF_Colt_Ardent.png"', gfx)
        self.assertTrue((ROOT / PORTRAIT).is_file())
        self.assertFalse((ROOT / "gfx/leaders/TFF/portrait.png").exists())
        self.assertIn("GFX_portrait_TFF_Colt_Ardent", named_block(read(CHARACTERS), "TFF_Colt_Ardent"))

    def test_start_keeps_absent_government_and_recruits_colt(self) -> None:
        history = read(HISTORY)
        self.assertIn("recruit_character = The_Absent_Government", history)
        self.assertIn("recruit_character = TFF_Colt_Ardent", history)
        self.assertIn(
            "promote_character = { character = The_Absent_Government ideology = anarchism_ideology }",
            history,
        )
        self.assertIn("The_Absent_Government = {", read(CHARACTERS))

    def test_empty_chair_transforms_in_immediate(self) -> None:
        event = event_block(read(EVENTS), "ADISCORD_TFF.1")
        immediate = named_block(event, "immediate")
        self.assertIn("hidden_effect = {", immediate)
        self.assertIn("ADISCORD_TFF_form_wartime_confederation = yes", immediate)
        option = named_block(event, "option")
        self.assertNotIn("ADISCORD_TFF_form_wartime_confederation = yes", option)

    def test_border_forts_stay_on_the_odar_esnos_line(self) -> None:
        forts = named_block(read(DECISIONS), "TFF_fortify_the_nodrul_border")
        self.assertEqual(tuple(re.findall(r"province\s*=\s*(\d+)", forts)), BORDER_PROVINCES)
        self.assertIn("83 = {", forts)
        self.assertNotIn("province = 30", forts)
        self.assertNotIn("province = 16533", forts)



class TFFKefreytCampaignTests(unittest.TestCase):
    def setUp(self):
        from tools.tests.test_adiscord_stp_preparation import parse_clausewitz
        self.effects = {e.key: e.value for e in parse_clausewitz(read(EFFECTS))}
        self.facts = {("TFF", "exists", "yes"): True, ("TFF", "has_capitulated", "no"): True,
                      ("TFF", "is_subject", "no"): True,
                      ("VAL", "has_country_flag", "VAL_nod_frontier_agreement"): True}
        self.ideas, self.news = set(), []

    def apply(self, name):
        from tools.tests.test_adiscord_stp_preparation import selected_effects, scalar
        for scope, entry in selected_effects(self.effects[name], self.facts, "TFF"):
            if entry.key in self.effects:
                self.apply(entry.key)
            elif entry.key in ("set_country_flag", "clr_country_flag"):
                self.facts[scope, "has_country_flag", entry.value] = entry.key == "set_country_flag"
            elif entry.key == "set_global_flag":
                self.facts[scope, "has_global_flag", entry.value] = True
            elif entry.key == "add_ideas":
                self.ideas.add(entry.value)
            elif entry.key == "remove_ideas":
                self.ideas.discard(entry.value)
            elif entry.key == "news_event":
                self.news.append(scalar(entry.value, "id"))
            else:
                self.fail(f"Unhandled TFF campaign effect: {entry.key}")

    def test_acceptance_alone_does_not_publish_news_and_real_entry_is_idempotent(self):
        self.apply("ADISCORD_TFF_begin_kefreyt_campaign")
        self.assertFalse(self.ideas or self.news)
        self.facts["VAL", "has_war_with", "NOD"] = True
        self.apply("ADISCORD_TFF_begin_kefreyt_campaign")
        self.assertFalse(self.ideas or self.news)
        self.facts["TFF", "has_war_with", "NOD"] = True
        for _ in range(3):
            self.apply("ADISCORD_TFF_begin_kefreyt_campaign")
        self.assertEqual(self.ideas, {"TFF_kefreyt_northern_campaign"})
        self.assertEqual(self.news, ["ADISCORD_TFF.11"])

    def test_refused_agreement_cannot_grant_bonus_or_news(self):
        self.facts.update({("VAL", "has_war_with", "NOD"): True, ("TFF", "has_war_with", "NOD"): True,
                           ("VAL", "has_country_flag", "VAL_nod_frontier_agreement"): False})
        self.apply("ADISCORD_TFF_begin_kefreyt_campaign")
        self.assertFalse(self.ideas or self.news)

    def test_coalition_war_keeps_bonus_until_last_enemy_and_then_removes_only_it(self):
        self.facts.update({("VAL", "has_war_with", "NOD"): True, ("TFF", "has_war_with", "NOD"): True})
        self.apply("ADISCORD_TFF_begin_kefreyt_campaign")
        self.ideas.add("TFF_emergency_frontier_command")
        self.facts["TFF", "has_war_with", "NOD"] = False
        self.facts["TFF", "has_war_with", "STP"] = True
        self.apply("ADISCORD_TFF_reconcile_kefreyt_campaign")
        self.assertIn("TFF_kefreyt_northern_campaign", self.ideas)
        self.facts["TFF", "has_war_with", "STP"] = False
        for _ in range(2):
            self.apply("ADISCORD_TFF_reconcile_kefreyt_campaign")
        self.assertEqual(self.ideas, {"TFF_emergency_frontier_command"})
        self.assertFalse(self.facts["TFF", "has_country_flag", "TFF_kefreyt_northern_campaign"])

    def test_defeat_or_subject_status_of_either_partner_ends_bonus(self):
        for country in ("VAL", "TFF"):
            for condition in ("has_capitulated", "is_subject"):
                self.setUp()
                self.facts.update({("VAL", "has_war_with", "NOD"): True, ("TFF", "has_war_with", "NOD"): True})
                self.apply("ADISCORD_TFF_begin_kefreyt_campaign")
                self.facts[country, condition, "yes"] = True
                self.apply("ADISCORD_TFF_reconcile_kefreyt_campaign")
                self.assertFalse(self.ideas, (country, condition))


class TFFCapitulationSettlementTests(unittest.TestCase):
    def setUp(self):
        from tools.lib.on_actions import scripted_peace_entries
        from tools.tests.test_adiscord_stp_preparation import block
        self.hooks = block(scripted_peace_entries(
            "common/on_actions/09_ADISCORD_scripted_peace_on_actions.txt", "frontier"), "on_actions")

    def resolved(self, items, captor="NOD"):
        from dataclasses import replace
        return [replace(e, key={"ROOT": "TFF", "FROM": captor}.get(e.key, e.key),
                        value=self.resolved(e.value, captor) if isinstance(e.value, list) else e.value)
                for e in items]

    def test_second_war_requires_actual_nod_capture_and_excludes_first_campaign(self):
        from tools.tests.test_adiscord_stp_preparation import block, matches_conditions
        branch = block(block(block(self.hooks, "on_capitulation_immediate"), "effect"), "if")
        facts = {("TFF", "is_subject", "no"): True, ("TFF", "has_war_with", "NOD"): True,
                 ("NOD", "exists", "yes"): True, ("NOD", "is_subject", "no"): True,
                 ("NOD", "has_capitulated", "no"): True,
                 ("NOD", "variable", "STP_cw_northern_campaign_status"): 2}
        gate = block(branch, "limit")
        self.assertTrue(matches_conditions(self.resolved(gate), facts))
        self.assertFalse(matches_conditions(self.resolved(gate, "VAL"), facts))
        for key, value in ((("NOD", "variable", "STP_cw_northern_campaign_status"), 1),
                           (("TFF", "is_subject", "no"), False),
                           (("TFF", "has_war_with", "NOD"), False),
                           (("NOD", "has_capitulated", "no"), False)):
            self.assertFalse(matches_conditions(self.resolved(gate), {**facts, key: value}), key)
        facts.update({("TFF", "capital"): "83", ("83", "controller"): "NOD"})
        self.assertTrue(matches_conditions(self.resolved(gate, "VAL"), facts))

    def test_late_callback_consumes_reservation_without_suppressing_later_defeats(self):
        from tools.tests.test_adiscord_stp_preparation import block, selected_effects, scalar, walk
        immediate = block(block(self.hooks, "on_capitulation_immediate"), "effect")
        receipt = next(e.value for e in walk(immediate) if e.key == "set_country_flag")
        marker = scalar(receipt, "flag")
        self.assertEqual(scalar(receipt, "days"), "1")
        late = self.resolved(block(block(self.hooks, "on_capitulation"), "effect"))
        facts = {("TFF", "has_country_flag", marker): True}
        outputs = list(selected_effects(late, facts))
        self.assertIn(("set_global_flag", "skip_default_capitulation"), [(e.key, e.value) for _, e in outputs])
        for scope, entry in outputs:
            if entry.key == "clr_country_flag":
                facts[scope, "has_country_flag", entry.value] = False
        self.assertEqual(list(selected_effects(late, facts)), [])

    def test_nonfaction_campaign_subjects_leave_the_war_before_puppeting(self):
        from tools.tests.test_adiscord_stp_preparation import parse_clausewitz, block, selected_effects
        effect = block(parse_clausewitz(read(EFFECTS)), "ADISCORD_TFF_become_nod_subject")
        facts = {("TFF", "exists", "yes"): True, ("TFF", "is_subject", "no"): True,
                 ("NOD", "exists", "yes"): True, ("NOD", "is_subject", "no"): True,
                 ("NOD", "has_capitulated", "no"): True,
                 ("TFF", "has_war_with", "NOD"): True}
        for relation in ("is_subject_of", "has_country_flag"):
            for tag in ("STP", "STS"):
                scenario = {**facts, ("TFF", "has_war_with", tag): True,
                            (tag, relation, "NOD" if relation == "is_subject_of" else "VAL_final_war_member"): True}
                output = list(selected_effects(effect, scenario, "TFF"))
                peace = [e.value for _, e in output if e.key == "white_peace"]
                self.assertEqual(peace, ["NOD", tag])
                self.assertLess(next(i for i, (_, e) in enumerate(output) if e.key == "white_peace" and e.value == tag),
                                next(i for i, (_, e) in enumerate(output) if e.key == "puppet"))

    def test_subject_settlement_preserves_country_and_val_war(self):
        from tools.tests.test_adiscord_stp_preparation import parse_clausewitz, block, walk, scalar
        effect = block(parse_clausewitz(read(EFFECTS)), "ADISCORD_TFF_become_nod_subject")
        self.assertFalse(any(e.key == "annex_country" for e in walk(effect)))
        puppet = next(e.value for e in walk(effect) if e.key == "puppet")
        self.assertEqual(scalar(puppet, "target"), "TFF")
        self.assertEqual(scalar(puppet, "end_wars"), "no")
        self.assertNotIn("VAL", [e.value for e in walk(effect) if e.key == "white_peace"])


if __name__ == "__main__":
    unittest.main()
