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
        self.assertIn(
            'texturefile = "gfx/leaders/TFF/portrait_TFF_Colt_Ardent.png"', gfx
        )
        self.assertTrue((ROOT / PORTRAIT).is_file())
        self.assertFalse((ROOT / "gfx/leaders/TFF/portrait.png").exists())
        self.assertIn(
            "GFX_portrait_TFF_Colt_Ardent",
            named_block(read(CHARACTERS), "TFF_Colt_Ardent"),
        )

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
        self.assertEqual(
            tuple(re.findall(r"province\s*=\s*(\d+)", forts)), BORDER_PROVINCES
        )
        self.assertIn("83 = {", forts)
        self.assertNotIn("province = 30", forts)
        self.assertNotIn("province = 16533", forts)


class TFFKefreytCampaignTests(unittest.TestCase):
    def setUp(self):
        from tools.tests.test_adiscord_stp_preparation import parse_clausewitz

        self.effects = {e.key: e.value for e in parse_clausewitz(read(EFFECTS))}
        self.facts = {
            ("TFF", "exists", "yes"): True,
            ("TFF", "has_capitulated", "no"): True,
            ("TFF", "is_subject", "no"): True,
            ("VAL", "has_country_flag", "VAL_nod_frontier_agreement"): True,
        }
        self.ideas, self.news = set(), []

    def apply(self, name):
        from tools.tests.test_adiscord_stp_preparation import selected_effects, scalar

        for scope, entry in selected_effects(self.effects[name], self.facts, "TFF"):
            if entry.key in self.effects:
                self.apply(entry.key)
            elif entry.key in ("set_country_flag", "clr_country_flag"):
                self.facts[scope, "has_country_flag", entry.value] = (
                    entry.key == "set_country_flag"
                )
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
        self.facts.update(
            {
                ("VAL", "has_war_with", "NOD"): True,
                ("TFF", "has_war_with", "NOD"): True,
                ("VAL", "has_country_flag", "VAL_nod_frontier_agreement"): False,
            }
        )
        self.apply("ADISCORD_TFF_begin_kefreyt_campaign")
        self.assertFalse(self.ideas or self.news)

    def test_coalition_war_keeps_bonus_until_last_enemy_and_then_removes_only_it(self):
        self.facts.update(
            {("VAL", "has_war_with", "NOD"): True, ("TFF", "has_war_with", "NOD"): True}
        )
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
        self.assertFalse(
            self.facts["TFF", "has_country_flag", "TFF_kefreyt_northern_campaign"]
        )

    def test_defeat_or_subject_status_of_either_partner_ends_bonus(self):
        for country in ("VAL", "TFF"):
            for condition in ("has_capitulated", "is_subject"):
                self.setUp()
                self.facts.update(
                    {
                        ("VAL", "has_war_with", "NOD"): True,
                        ("TFF", "has_war_with", "NOD"): True,
                    }
                )
                self.apply("ADISCORD_TFF_begin_kefreyt_campaign")
                self.facts[country, condition, "yes"] = True
                self.apply("ADISCORD_TFF_reconcile_kefreyt_campaign")
                self.assertFalse(self.ideas, (country, condition))


class TFFCapitulationSettlementTests(unittest.TestCase):
    def setUp(self):
        from tools.lib.on_actions import scripted_peace_entries
        from tools.tests.test_adiscord_stp_preparation import block

        self.hooks = block(
            scripted_peace_entries(
                "common/on_actions/09_ADISCORD_scripted_peace_on_actions.txt",
                "frontier",
            ),
            "on_actions",
        )

    def resolved(self, items, captor="NOD"):
        from dataclasses import replace

        return [
            replace(
                e,
                key={"ROOT": "TFF", "FROM": captor}.get(e.key, e.key),
                value=(
                    self.resolved(e.value, captor)
                    if isinstance(e.value, list)
                    else e.value
                ),
            )
            for e in items
        ]

    def test_second_war_requires_actual_nod_capture_and_excludes_first_campaign(self):
        from tools.tests.test_adiscord_stp_preparation import block, matches_conditions

        branch = next(e.value for e in block(block(self.hooks, "on_capitulation_immediate"), "effect")
                      if e.key == "if" and "ADISCORD_TFF_become_nod_subject" in repr(e))
        facts = {
            ("TFF", "is_subject", "no"): True,
            ("TFF", "has_war_with", "NOD"): True,
            ("NOD", "exists", "yes"): True,
            ("NOD", "is_subject", "no"): True,
            ("NOD", "has_capitulated", "no"): True,
            ("NOD", "variable", "STP_cw_northern_campaign_status"): 2,
        }
        gate = block(branch, "limit")
        self.assertTrue(matches_conditions(self.resolved(gate), facts))
        self.assertFalse(matches_conditions(self.resolved(gate, "VAL"), facts))
        for key, value in (
            (("NOD", "variable", "STP_cw_northern_campaign_status"), 1),
            (("TFF", "is_subject", "no"), False),
            (("TFF", "has_war_with", "NOD"), False),
            (("NOD", "has_capitulated", "no"), False),
        ):
            self.assertFalse(
                matches_conditions(self.resolved(gate), {**facts, key: value}), key
            )
        facts.update({("TFF", "capital"): "83", ("83", "controller"): "NOD"})
        self.assertTrue(matches_conditions(self.resolved(gate, "VAL"), facts))

    def test_late_callback_consumes_reservation_without_suppressing_later_defeats(self):
        from tools.tests.test_adiscord_stp_preparation import (
            block,
            selected_effects,
            scalar,
            walk,
        )

        immediate = block(block(self.hooks, "on_capitulation_immediate"), "effect")
        receipt = next(e.value for e in walk(immediate) if e.key == "set_country_flag" and isinstance(e.value, list) and scalar(e.value, "flag") == "TFF_nod_capitulation_reserved")
        marker = scalar(receipt, "flag")
        self.assertEqual(scalar(receipt, "days"), "1")
        late = self.resolved(block(block(self.hooks, "on_capitulation"), "effect"))
        facts = {("TFF", "has_country_flag", marker): True}
        outputs = list(selected_effects(late, facts))
        self.assertIn(
            ("set_global_flag", "skip_default_capitulation"),
            [(e.key, e.value) for _, e in outputs],
        )
        for scope, entry in outputs:
            if entry.key == "clr_country_flag":
                facts[scope, "has_country_flag", entry.value] = False
        self.assertEqual(list(selected_effects(late, facts)), [])

    def test_nonfaction_campaign_subjects_leave_the_war_before_puppeting(self):
        from tools.tests.test_adiscord_stp_preparation import (
            parse_clausewitz,
            block,
            selected_effects,
        )

        effect = block(
            parse_clausewitz(read(EFFECTS)), "ADISCORD_TFF_become_nod_subject"
        )
        facts = {
            ("TFF", "exists", "yes"): True,
            ("TFF", "is_subject", "no"): True,
            ("NOD", "exists", "yes"): True,
            ("NOD", "is_subject", "no"): True,
            ("NOD", "has_capitulated", "no"): True,
            ("TFF", "has_war_with", "NOD"): True,
        }
        for relation in ("is_subject_of", "has_country_flag"):
            for tag in ("STP", "STS"):
                scenario = {
                    **facts,
                    ("TFF", "has_war_with", tag): True,
                    (
                        tag,
                        relation,
                        (
                            "NOD"
                            if relation == "is_subject_of"
                            else "VAL_final_war_member"
                        ),
                    ): True,
                }
                output = list(selected_effects(effect, scenario, "TFF"))
                peace = [e.value for _, e in output if e.key == "white_peace"]
                self.assertEqual(peace, ["NOD", tag])
                self.assertLess(
                    next(
                        i
                        for i, (_, e) in enumerate(output)
                        if e.key == "white_peace" and e.value == tag
                    ),
                    next(i for i, (_, e) in enumerate(output) if e.key == "puppet"),
                )

    def test_subject_settlement_preserves_country_and_val_war(self):
        from tools.tests.test_adiscord_stp_preparation import (
            parse_clausewitz,
            block,
            walk,
            scalar,
        )

        effect = block(
            parse_clausewitz(read(EFFECTS)), "ADISCORD_TFF_become_nod_subject"
        )
        self.assertFalse(any(e.key == "annex_country" for e in walk(effect)))
        puppet = next(e.value for e in walk(effect) if e.key == "puppet")
        self.assertEqual(scalar(puppet, "target"), "TFF")
        self.assertEqual(scalar(puppet, "end_wars"), "no")
        self.assertNotIn(
            "VAL", [e.value for e in walk(effect) if e.key == "white_peace"]
        )


class TFFFreedomNegotiationTests(unittest.TestCase):
    """Select real treaty branches; native war and autonomy hooks remain boundaries."""

    def setUp(self):
        from tools.tests.test_adiscord_stp_preparation import entries, scalar

        self.effects = {
            e.key: e.value
            for e in entries("common/scripted_effects/ADISCORD_VAL_effects.txt")
        }
        self.triggers = {
            e.key: e.value
            for e in entries(
                "common/scripted_triggers/ADISCORD_VAL_rework_triggers.txt"
            )
        }
        self.events = {
            scalar(e.value, "id"): e.value
            for e in entries("events/ADISCORD_VAL_contract_events.txt")
            if e.key == "country_event"
        }
        self.facts = {}
        for tag in ("VAL", "TFF", "NOD"):
            self.facts[tag, "exists", "yes"] = True
            self.facts[tag, "has_capitulated", "no"] = True
            self.facts[tag, "is_subject", "no"] = True
        self.facts.update(
            {
                ("VAL", "has_completed_focus", "VAL_Northern_Settlement"): True,
                ("NOD", "variable", "STP_cw_northern_campaign_status"): 2,
                ("YPR", "is_subject_of", "NOD"): True,
                ("DCA", "exists", "no"): True,
                ("20", "owner"): "NOD",
                ("15", "owner"): "NOD",
            }
        )
        self.outputs = []

    def expanded(self, rows):
        from dataclasses import replace
        from tools.tests.test_adiscord_stp_preparation import parse_clausewitz, scalar

        result = []
        for e in rows:
            if e.key in self.triggers and isinstance(e.value, str):
                self.assertIn(e.value, ("yes", "no"))
                result.append(
                    replace(
                        e,
                        key="AND" if e.value == "yes" else "NOT",
                        value=self.expanded(self.triggers[e.key]),
                    )
                )
            elif e.key == "has_country_flag" and isinstance(e.value, list):
                flag = scalar(e.value, "flag")
                field, op, value = [x.value for x in e.value if not x.key]
                self.assertEqual(field, "value")
                comparison = {"<": "less_than", ">": "greater_than"}[op]
                result.extend(
                    parse_clausewitz(
                        f"AND = {{ has_country_flag = {flag} check_variable = {{ var = flag_value_{flag} value = {value} compare = {comparison} }} }}"
                    )
                )
            else:
                result.append(
                    replace(
                        e,
                        value=(
                            self.expanded(e.value)
                            if isinstance(e.value, list)
                            else e.value
                        ),
                    )
                )
        return result

    def flag(self, tag, name, value=1):
        self.facts[tag, "has_country_flag", name] = bool(value)
        self.facts[tag, "variable", "flag_value_" + name] = value

    def execute(self, rows, scope="VAL"):
        from tools.tests.test_adiscord_stp_preparation import selected_effects, scalar

        for tag, e in selected_effects(self.expanded(rows), self.facts, scope):
            if e.key in ("set_country_flag", "clr_country_flag"):
                name = scalar(e.value, "flag") if isinstance(e.value, list) else e.value
                value = (
                    next((float(x.value) for x in e.value if x.key == "value"), 1)
                    if isinstance(e.value, list)
                    else 1
                )
                self.flag(tag, name, value if e.key == "set_country_flag" else 0)
            elif e.key == "set_autonomy":
                target = scalar(e.value, "target")
                self.outputs.append((tag, "subject", target))
                self.facts[target, "is_subject_of", "VAL"] = tag == "VAL"
                self.facts[target, "is_subject_of", "TFF"] = tag == "TFF"
            elif e.key in ("set_temp_variable", "set_variable"):
                self.facts[tag, "variable", scalar(e.value, "var")] = float(scalar(e.value, "value"))
            elif e.key == "country_event":
                self.outputs.append((tag, "event", scalar(e.value, "id")))
            elif e.key in (
                "VAL_open_nod_frontier_offer",
                "VAL_accept_nod_frontier_offer",
                "VAL_transfer_yubora_administrations",
                "VAL_offer_frontier_protectorate",
                "VAL_accept_frontier_protectorate",
                "VAL_finish_frontier_protectorate",
                "VAL_final_crisis_join_war",
                "VAL_final_crisis_register_member",
            ):
                self.execute(self.effects[e.key], tag)
            elif e.key not in ("name", "trigger", "ai_chance", "custom_effect_tooltip"):
                self.outputs.append((tag, e.key, e.value))

    def option(self, event, name):
        from tools.tests.test_adiscord_stp_preparation import scalar

        self.assertTrue(
            event in self.events,
            "The focus must have an authored diplomatic choice: " + event,
        )
        return next(
            e.value
            for e in self.events[event]
            if e.key == "option" and scalar(e.value, "name") == name
        )

    def test_firm_agreement_transfers_only_iskhait_and_keeps_duchebia(self):
        for terms, expected in ((1, ["YPR", "DCA"]), (2, ["YPR"]), (0, ["YPR", "DCA"])):
            self.setUp()
            self.flag("VAL", "VAL_nod_frontier_agreement", terms)
            self.facts["YPR", "is_subject_of", "VAL"] = True
            self.facts["DCA", "is_subject_of", "VAL"] = True
            self.facts["DCA", "has_war_with", "TFF"] = True
            self.execute(self.effects["VAL_transfer_yubora_administrations"])
            self.assertEqual(
                [x[2] for x in self.outputs if x[:2] == ("TFF", "subject")], expected
            )
            self.assertIn(
                ("DCA", "white_peace", "TFF"),
                self.outputs,
                "Retained Duchebia must also leave its inherited enemy war",
            )
            self.outputs.clear()
            self.execute(self.effects["VAL_transfer_yubora_administrations"])
            self.assertFalse(
                any(x[1] == "subject" for x in self.outputs),
                "A treaty must not transfer twice",
            )

    def test_final_signature_uses_quoted_terms_not_a_later_quote(self):
        self.flag("VAL", "VAL_nod_frontier_offer_pending", 2)
        self.facts["VAL", "variable", "VAL_nod_quote_tier"] = 1
        self.execute(self.option("val_contract.350", "val_contract.350.accept"), "TFF")
        self.assertEqual(
            self.facts["VAL", "variable", "flag_value_VAL_nod_frontier_agreement"], 2
        )
        self.assertFalse(
            self.facts["VAL", "has_country_flag", "VAL_nod_frontier_offer_pending"]
        )
        self.outputs.clear()
        self.execute(self.option("val_contract.350", "val_contract.350.refuse"), "TFF")
        self.execute(self.option("val_contract.350", "val_contract.350.accept"), "TFF")
        self.assertEqual(
            self.outputs,
            [],
            "Obsolete answers must not dispatch or rewrite a signed treaty",
        )

    def test_war_or_missing_offer_prevents_late_signature(self):
        for pending, at_war in ((0, False), (1, True), (2, True)):
            self.setUp()
            self.flag("VAL", "VAL_nod_frontier_offer_pending", pending)
            self.facts["VAL", "has_war_with", "TFF"] = at_war
            self.execute(
                self.option("val_contract.350", "val_contract.350.accept"), "TFF"
            )
            self.assertFalse(
                self.facts.get(
                    ("VAL", "has_country_flag", "VAL_nod_frontier_agreement"), False
                )
            )
            self.assertEqual(self.outputs, [])

    def test_current_quote_is_selected_at_military_negotiations_and_cannot_be_overwritten(self):
        for choice, tier in (("compromise", 1), ("firm", 2)):
            self.setUp()
            self.execute(self.option("val_contract.380", "val_contract.380." + choice))
            self.assertEqual(self.facts["VAL", "variable", "flag_value_VAL_nod_frontier_offer_pending"], tier)
            self.assertEqual(self.outputs, [("TFF", "event", "val_contract.350")])
            self.execute(self.option("val_contract.380", "val_contract.380." + ("firm" if tier == 1 else "compromise")))
            self.assertEqual(self.facts["VAL", "variable", "flag_value_VAL_nod_frontier_offer_pending"], tier)
            self.assertEqual(len(self.outputs), 1)

    def test_protectorate_negotiation_blocks_a_competing_partition_quote(self):
        self.flag("VAL", "VAL_frontier_protectorate_pending", 1)
        for choice in ("firm", "compromise"):
            self.execute(self.option("val_contract.380", "val_contract.380." + choice))
        self.assertEqual(self.outputs, [])
        self.assertFalse(self.facts.get(("VAL", "has_country_flag", "VAL_nod_frontier_offer_pending"), False))

    def test_partition_consumes_signed_terms_after_delivering_the_right_share(self):
        for terms, expected in ((1, ["YPR", "DCA"]), (2, ["YPR"])):
            self.setUp()
            self.flag("VAL", "VAL_nod_frontier_agreement", terms)
            for tag in ("YPR", "DCA"):
                self.facts[tag, "exists", "yes"] = True
                self.facts["VAL", "variable", f"VAL_nod_{tag}_states^num"] = 1
            self.execute(self.effects["VAL_partition_nodrul_settlement"])
            self.assertEqual(
                [x[2] for x in self.outputs if x[:2] == ("TFF", "subject")], expected
            )
            self.assertFalse(
                self.facts["VAL", "has_country_flag", "VAL_nod_frontier_agreement"]
            )
            self.assertFalse(
                any(x[1:] == ("event", "val_contract.352") for x in self.outputs)
            )


class TFFProtectorateRouteTests(unittest.TestCase):
    """Evaluate the new route against current relations, not historical promises."""

    expanded = TFFFreedomNegotiationTests.expanded
    flag = TFFFreedomNegotiationTests.flag
    execute = TFFFreedomNegotiationTests.execute
    option = TFFFreedomNegotiationTests.option

    def setUp(self):
        TFFFreedomNegotiationTests.setUp(self)
        self.facts.update({
            ("VAL", "has_war", "no"): True,
            ("VAL", "is_in_faction", "no"): True,
            ("TFF", "has_war", "no"): True,
            ("STP", "exists", "yes"): True,
            ("STP", "has_capitulated", "no"): True,
            ("STP", "is_subject_of", "NOD"): True,
            ("TFF", "capital"): "83",
            ("83", "is_owned_by", "TFF"): True,
            ("83", "is_controlled_by", "TFF"): True,
        })

    def matches(self, name, scope="VAL"):
        from tools.tests.test_adiscord_stp_preparation import matches_conditions

        self.assertTrue(name in self.triggers, name)
        return matches_conditions(self.expanded(self.triggers[name]), self.facts, scope)

    def test_joint_campaign_requires_a_living_stelander_member_of_nodruls_bloc(self):
        for tag in ("STP", "STS"):
            for relation in ("is_subject_of", "is_in_faction_with"):
                with self.subTest(tag=tag, relation=relation):
                    self.setUp()
                    self.facts["VAL", "has_completed_focus", "VAL_Different_Views_On_Freedom"] = True
                    self.facts["TFF", "is_subject_of", "VAL"] = True
                    self.facts["STP", "is_subject_of", "NOD"] = False
                    self.facts[tag, "exists", "yes"] = True
                    self.facts[tag, "has_capitulated", "no"] = True
                    self.facts[tag, relation, "NOD"] = True
                    self.assertTrue(self.matches("VAL_frontier_joint_campaign_ready"))
                    self.facts[tag, relation, "NOD"] = False
                    self.assertFalse(self.matches("VAL_frontier_joint_campaign_ready"))

    def test_foreign_subject_enemy_and_competing_offer_cannot_be_subjugated(self):
        for fact in (
            ("TFF", "is_subject", "no"),
            ("VAL", "is_subject", "no"),
            ("TFF", "has_capitulated", "no"),
        ):
            self.setUp()
            self.facts[fact] = False
            self.assertFalse(self.matches("VAL_frontier_protectorate_available"))
        for fact in (
            ("TFF", "has_war_with", "VAL"),
            ("TFF", "is_in_faction_with", "NOD"),
            ("VAL", "has_country_flag", "VAL_nod_frontier_offer_pending"),
            ("VAL", "has_country_flag", "VAL_nod_frontier_agreement"),
        ):
            self.setUp()
            self.facts[fact] = True
            self.assertFalse(self.matches("VAL_frontier_protectorate_available"))

    def test_subject_route_replaces_prior_stelander_victory_only_while_bloc_exists(self):
        self.facts["VAL", "has_completed_focus", "VAL_Different_Views_On_Freedom"] = True
        self.facts["TFF", "is_subject_of", "VAL"] = True
        self.facts["TFF", "is_subject", "no"] = False
        self.assertTrue(self.matches("VAL_frontier_joint_campaign_ready"))
        self.assertTrue(self.matches("VAL_nod_campaign_stelander_ready"))
        self.facts["STP", "is_subject_of", "NOD"] = False
        self.assertFalse(self.matches("VAL_frontier_joint_campaign_ready"))
        self.assertFalse(self.matches("VAL_nod_campaign_stelander_ready"))

    def test_liberated_or_capitulated_frontier_cannot_supply_the_route(self):
        for free, capitulated in ((True, False), (False, True)):
            self.setUp()
            self.facts["VAL", "has_completed_focus", "VAL_Different_Views_On_Freedom"] = True
            self.facts["TFF", "is_subject_of", "VAL"] = not free
            self.facts["TFF", "has_capitulated", "no"] = not capitulated
            self.assertFalse(self.matches("VAL_frontier_joint_campaign_ready"))

    def test_native_war_callback_registers_the_early_campaign_and_delayed_enemy_join(self):
        from tools.tests.test_adiscord_stp_preparation import block, entries, walk

        hooks = block(entries("common/on_actions/02_ADISCORD_VAL_rework_on_actions.txt"), "on_actions")
        callback = block(block(hooks, "on_war_relation_added"), "effect")
        paths = [e.value for e in walk(callback) if e.key == "if"
                 and any(child.key == "VAL_final_crisis_join_war" for child in e.value)]
        self.assertEqual(len(paths), 1)
        self.facts["VAL", "has_completed_focus", "VAL_Northern_Settlement"] = False
        self.facts["VAL", "has_completed_focus", "VAL_Different_Views_On_Freedom"] = True
        self.facts["TFF", "is_subject_of", "VAL"] = True
        self.execute([next(e for e in walk(callback) if e.key == "if" and e.value == paths[0])])
        self.assertFalse(self.facts.get(("NOD", "has_country_flag", "VAL_final_war_member")))
        self.facts["VAL", "has_war_with", "NOD"] = True
        self.execute([next(e for e in walk(callback) if e.key == "if" and e.value == paths[0])])
        self.assertEqual(self.facts["VAL", "variable", "VAL_final_crisis_phase"], 2)
        self.assertTrue(self.facts["NOD", "has_country_flag", "VAL_final_war_member"])
        self.assertTrue(any(row[0:2] == ("STP", "add_to_war") for row in self.outputs))
        self.facts["STP", "has_war_with", "VAL"] = True
        self.execute(self.effects["VAL_final_crisis_join_war"])
        self.assertTrue(self.facts["STP", "has_country_flag", "VAL_final_war_member"])
        self.assertTrue(any(row[1] == "VAL_call_subjects_to_wars" for row in self.outputs))

    def test_focus_unlocks_the_existing_campaign_and_sends_a_protectorate_offer(self):
        from tools.tests.test_adiscord_stp_preparation import block, entries, scalar

        tree = block(entries("focus_trees/VAL/main/focuses.txt"), "focus_tree")
        focus = next(e.value for e in tree if e.key == "focus"
                     and scalar(e.value, "id") == "VAL_Different_Views_On_Freedom")
        self.execute(block(focus, "completion_reward"))
        self.assertIn(("VAL", "unlock_decision_tooltip", "VAL_campaign_against_nod"), self.outputs)
        self.assertIn(("TFF", "event", "val_contract.381"), self.outputs)
        self.assertFalse(any(e[1] == "subject" for e in self.outputs))

    def test_refusal_or_timeout_does_not_subjugate_and_closes_pending_offer(self):
        self.flag("VAL", "VAL_frontier_protectorate_pending", 1)
        self.execute(self.option("val_contract.381", "val_contract.381.refuse"), "TFF")
        self.assertFalse(self.facts["VAL", "has_country_flag", "VAL_frontier_protectorate_pending"])
        self.assertFalse(any(e[1] == "subject" for e in self.outputs))

    def test_ai_consent_tracks_northern_result_and_delivered_aid(self):
        from tools.tests.test_adiscord_stp_preparation import block, scalar, matches_conditions

        def weight(option):
            rows = block(option, "ai_chance")
            result = float(scalar(rows, "base"))
            for modifier in (e.value for e in rows if e.key == "modifier"):
                if matches_conditions(self.expanded([e for e in modifier if e.key != "factor"]), self.facts, "TFF"):
                    result *= float(scalar(modifier, "factor"))
            return result

        for outcome, rifles, expected in ((3, 50000, .90), (3, 0, .10),
                                           (2, 50000, .60), (2, 0, .25),
                                           (4, 50000, .75), (4, 0, .25)):
            with self.subTest(outcome=outcome, rifles=rifles):
                self.facts["NOD", "variable", "STP_cw_northern_campaign_status"] = outcome
                self.facts["VAL", "variable", "VAL_northern_aid_rifles"] = rifles
                yes = weight(self.option("val_contract.381", "val_contract.381.accept"))
                no = weight(self.option("val_contract.381", "val_contract.381.refuse"))
                self.assertAlmostEqual(yes / (yes + no), expected)

    def test_protectorate_waits_for_consent_then_converts_once_on_the_delayed_callback(self):
        self.flag("VAL", "VAL_frontier_protectorate_pending", 1)
        self.execute(self.option("val_contract.381", "val_contract.381.accept"), "TFF")
        self.assertIn(("VAL", "event", "val_contract.383"), self.outputs)
        self.assertFalse(any(row[1] == "subject" for row in self.outputs))
        self.outputs.clear()
        self.execute(self.effects["VAL_finish_frontier_protectorate"])
        self.assertIn(("VAL", "subject", "TFF"), self.outputs)
        self.assertFalse(self.facts["VAL", "has_country_flag", "VAL_frontier_protectorate_pending"])
        self.outputs.clear()
        self.execute(self.effects["VAL_finish_frontier_protectorate"])
        self.execute(self.option("val_contract.381", "val_contract.381.refuse"), "TFF")
        self.assertEqual(self.outputs, [])

    def test_foreign_subjugation_before_delayed_conversion_cancels_without_stealing_subject(self):
        self.flag("VAL", "VAL_frontier_protectorate_pending", 2)
        self.facts["TFF", "is_subject", "no"] = False
        self.execute(self.effects["VAL_finish_frontier_protectorate"])
        self.assertFalse(any(row[1] == "subject" for row in self.outputs))
        self.assertFalse(self.facts["VAL", "has_country_flag", "VAL_frontier_protectorate_pending"])

    def test_northern_partners_reform_their_faction_after_native_detachment(self):
        self.flag("VAL", "VAL_frontier_protectorate_pending", 1)
        self.facts["TFF", "is_in_faction", "yes"] = True
        self.facts["TFF", "is_faction_leader", "yes"] = True
        for tag in ("YPR", "COF"):
            self.facts[tag, "exists", "yes"] = True
            self.facts[tag, "is_subject", "no"] = True
            self.facts[tag, "has_war", "no"] = True
            self.facts[tag, "is_in_faction_with", "TFF"] = True
        self.execute(self.effects["VAL_accept_frontier_protectorate"])
        self.assertIn(("TFF", "dismantle_faction", "yes"), self.outputs)
        self.assertFalse(any(row[1] == "create_faction_from_template" for row in self.outputs))
        self.facts["TFF", "is_in_faction", "yes"] = False
        for tag in ("YPR", "COF"):
            self.facts[tag, "is_in_faction_with", "TFF"] = False
            self.facts[tag, "is_in_faction", "no"] = True
        self.execute(self.effects["VAL_finish_frontier_protectorate"])
        self.assertIn(("YPR", "add_to_faction", "COF"), self.outputs)
        self.assertIn(("VAL", "subject", "TFF"), self.outputs)

    def test_campaign_is_visible_without_the_late_focus_and_cancels_when_the_bloc_breaks(self):
        from tools.tests.test_adiscord_stp_preparation import block, entries, matches_conditions, scalar, walk

        decision = block(block(entries("common/decisions/ADISCORD_VAL_decisions.txt"), "VAL_military_operations"), "VAL_campaign_against_nod")
        self.facts["VAL", "has_completed_focus", "VAL_Northern_Settlement"] = False
        self.facts["VAL", "has_completed_focus", "VAL_Different_Views_On_Freedom"] = True
        self.facts["TFF", "is_subject_of", "VAL"] = True
        self.facts["VAL", "FROM"] = "NOD"
        from dataclasses import replace
        def target(rows):
            return [replace(e, key="NOD" if e.key == "FROM" else e.key,
                            value=target(e.value) if isinstance(e.value, list) else e.value) for e in rows]
        self.assertTrue(matches_conditions(target(block(decision, "visible")), self.facts, "VAL"))
        self.assertEqual(scalar(decision, "cost"), "60")
        self.assertEqual(scalar(decision, "days_remove"), "30")
        gate = target(self.expanded(block(decision, "cancel_trigger")))
        self.assertFalse(matches_conditions(gate, self.facts, "VAL"))
        self.facts["STP", "is_subject_of", "NOD"] = False
        self.assertTrue(matches_conditions(gate, self.facts, "VAL"))



if __name__ == "__main__":
    unittest.main()
