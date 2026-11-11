from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[2]


def read(path):
    return (ROOT / path).read_text(encoding="utf-8-sig")


def block(text, name):
    marker = name + " ="
    start = text.index(marker)
    opening = text.index("{", start)
    depth = 0
    in_string = False
    escaped = False
    for index in range(opening, len(text)):
        character = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                in_string = False
            continue
        if character == '"':
            in_string = True
        elif character == "{":
            depth += 1
        elif character == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    raise AssertionError(f"unterminated block: {name}")


class StelanderStalemateRegressionTests(unittest.TestCase):
    def test_repeatable_civil_war_orders_stop_ai_at_frontage_saturation(self):
        decisions = read("common/decisions/ADISCORD_STP_decisions.txt")
        for name in (
            "STP_cw_raise_territorial_brigade",
            "STP_cw_train_reserve_brigades",
            "STP_party_form_assault_column",
        ):
            with self.subTest(decision=name):
                order = block(decisions, name)
                self.assertIn("NOT = { num_divisions < 24 }", order)

        strategies = read("common/ai_strategy/ADISCORD_STP_civil_war.txt")
        for name, enemy in (
            ("STP_cw_ai_force_saturation", "STS"),
            ("STS_cw_ai_force_saturation", "STP"),
        ):
            with self.subTest(strategy=name):
                profile = block(strategies, name)
                self.assertIn("is_ai = yes", profile)
                self.assertIn(f"has_war_with = {enemy}", profile)
                self.assertIn("NOT = { num_divisions < 24 }", profile)
                self.assertIn(
                    "type = ai_wanted_divisions_factor value = -1000", profile
                )

    def test_ai_war_replacements_stay_below_the_recruitment_brake(self):
        strategies = read("common/ai_strategy/ADISCORD_STP_civil_war.txt")
        brake = block(strategies, "STP_cw_ai_preserve_replacement_reserve")
        for tag in ("STP", "STS", "NOD"):
            self.assertIn(f"original_tag = {tag}", brake)
        self.assertIn("is_ai = yes", brake)
        self.assertIn("has_war = yes", brake)
        reserve = int(re.search(r"has_manpower < (\d+)", brake).group(1))
        self.assertIn("type = ai_wanted_divisions_factor value = -1000", brake)

        effects = read("common/scripted_effects/ADISCORD_STP_scripted_effects.txt")
        tick = block(effects, "STP_cw_ai_war_replacements_tick")
        self.assertIn("is_ai = yes", tick)
        self.assertIn("has_capitulated = no", tick)
        ceiling = int(re.search(r"has_manpower < (\d+)", tick).group(1))
        grant = int(re.search(r"add_manpower = (\d+)", tick).group(1))
        # A grant that crosses the brake would fund new formations.
        self.assertLessEqual(ceiling + grant, reserve)
        self.assertNotIn("has_war_with = STS", tick)
        self.assertNotIn("has_war_with = STP", tick)

        hooks = read("common/on_actions/02_ADISCORD_STP_on_actions.txt")
        for tag in ("STP", "STS", "NOD"):
            with self.subTest(hook=tag):
                weekly = block(hooks, f"on_weekly_{tag}")
                self.assertEqual(
                    weekly.count("STP_cw_ai_war_replacements_tick = yes"), 1
                )

    def test_ai_kefreyt_prepares_from_the_party_external_mandate(self):
        triggers = read("common/scripted_triggers/ADISCORD_VAL_rework_triggers.txt")
        threat = block(triggers, "VAL_ai_party_campaign_threat")
        self.assertIn("has_completed_focus = STP_pw_party_external_mandate", threat)
        self.assertIn("NOT = { has_war_with = VAL }", threat)
        self.assertIn("NOT = { is_in_faction_with = VAL }", threat)
        for flag in (
            "STP_pw_party_kefreyt_subject_pending",
            "STP_pw_party_kefreyt_victory",
        ):
            self.assertIn(f"NOT = {{ has_country_flag = {flag} }}", threat)
        focuses = read("common/national_focus/ADISCORD_STP_civil_war.txt")
        campaign = focuses.index("id = STP_pw_party_kefreyt_campaign")
        self.assertIn(
            "prerequisite = { focus = STP_pw_party_external_mandate }",
            focuses[campaign : campaign + 300],
        )

        strategies = read("common/ai_strategy/VAL.txt")
        for name, target, extra in (
            ("VAL_prepare_against_party_campaign", "STP", None),
            ("VAL_prepare_against_party_patron", "NOD", "is_in_faction_with = STP"),
        ):
            with self.subTest(strategy=name):
                profile = block(strategies, name)
                self.assertIn("allowed = { tag = VAL }", profile)
                self.assertIn("is_ai = yes", profile)
                self.assertIn("VAL_ai_party_campaign_threat = yes", profile)
                self.assertIn("type = prepare_for_war", profile)
                self.assertIn(f"id = {target}", profile)
                if extra:
                    self.assertIn(extra, profile)

        recruitment = block(
            read("common/ai_strategy/ADISCORD_STP_civil_war.txt"),
            "VAL_cw_republics_war_recruitment",
        )
        self.assertIn("difficulty > 2", recruitment)
        self.assertIn("VAL_ai_party_campaign_threat = yes", recruitment)
        for enemy in ("SRP", "STS", "STP", "NOD"):
            self.assertIn(f"has_war_with = {enemy}", recruitment)
        self.assertIn("NOT = { has_manpower < 15000 }", recruitment)

        command = block(
            read("common/ideas/ADISCORD_VAL_rework_ideas.txt"),
            "VAL_ai_scripted_war_command",
        )
        self.assertIn("army_core_defence_factor = 0.10", command)

    def test_party_kefreyt_campaign_warns_kefreyt_when_the_focus_is_selected(self):
        call = "select_effect = { hidden_effect = { STP_pw_party_warn_kefreyt = yes } }"
        for path in (
            "focus_trees/STP/postwar/party/focuses.txt",
            "common/national_focus/ADISCORD_STP_civil_war.txt",
        ):
            with self.subTest(path=path):
                focuses = read(path)
                start = focuses.index("id = STP_pw_party_kefreyt_campaign")
                reward = focuses.index("completion_reward", start)
                self.assertIn(call, focuses[start:reward])
                self.assertEqual(focuses.count(call), 1)

        effects = read("common/scripted_effects/ADISCORD_STP_scripted_effects.txt")
        warn = block(effects, "STP_pw_party_warn_kefreyt")
        self.assertIn("tag = STP", warn)
        self.assertIn("NOT = { has_war_with = STP }", warn)
        self.assertIn("NOT = { has_idea = STP_pw_party_kefreyt_defence_ready }", warn)
        self.assertIn("STP_pw_party_kefreyt_warning_expired = no", warn)
        self.assertIn("country_event = { id = ADISCORD_STP_pc.112 hours = 1 }", warn)

        events = read("events/ADISCORD_STP_events.txt")
        start = events.index("id = ADISCORD_STP_pc.112")
        event = events[start : events.index("country_event = {", start)]
        self.assertIn("is_triggered_only = yes", event)
        self.assertIn("tag = VAL", event)
        self.assertIn("STP_pw_party_kefreyt_warning_expired = no", event)
        self.assertIn(
            "immediate = { add_ideas = STP_pw_party_kefreyt_defence_ready }", event
        )

        expired = block(
            read("common/scripted_triggers/ADISCORD_STP_scripted_triggers.txt"),
            "STP_pw_party_kefreyt_warning_expired",
        )
        for clause in (
            "is_subject = yes",
            "STP = { exists = no }",
            "STP = { is_in_faction_with = VAL }",
            "hidden_trigger = {",
            "has_country_flag = STP_pw_party_kefreyt_subject_pending",
            "has_country_flag = STP_pw_party_kefreyt_victory",
        ):
            self.assertIn(clause, expired)

        ideas = read("common/ideas/ADISCORD_STP_civil_war_ideas.txt")
        ready = block(ideas, "STP_pw_party_kefreyt_defence_ready")
        self.assertIn("NOT = { has_war_with = STP }", ready)
        self.assertIn("STP_pw_party_kefreyt_warning_expired = yes", ready)
        shabrat = block(ideas, "STP_pc_campaign_defence")
        party = block(ideas, "STP_pw_party_kefreyt_defence")
        bonus = "modifier = { army_defence_factor = 0.08 }"
        self.assertIn(bonus, shabrat)
        self.assertIn(bonus, party)

        hooks = read("common/on_actions/02_ADISCORD_STP_on_actions.txt")
        self.assertEqual(
            hooks.count("FROM = { STP_pw_party_apply_kefreyt_defence = yes }"), 1
        )
        self.assertEqual(hooks.count("STP_pw_party_apply_kefreyt_defence = yes"), 2)

        for language in ("russian", "english"):
            text = read(f"localisation/{language}/ADISCORD_STP_l_{language}.yml")
            for key in (
                "ADISCORD_STP_pc.112.t",
                "ADISCORD_STP_pc.112.d",
                "ADISCORD_STP_pc.112.a",
                "STP_pw_party_kefreyt_defence_ready",
                "STP_pw_party_kefreyt_defence_ready_desc",
                "STP_pw_party_kefreyt_defence",
                "STP_pw_party_kefreyt_defence_desc",
            ):
                with self.subTest(language=language, key=key):
                    self.assertRegex(text, r'(?m)^ ' + re.escape(key) + r':\d* "[^\n]+"\r?$')

    def test_battle_for_stelander_backs_shabrat_only(self):
        triggers = read("common/scripted_triggers/ADISCORD_VAL_rework_triggers.txt")
        host = block(triggers, "VAL_stelander_volunteer_host")
        self.assertIn("tag = STS", host)
        self.assertIn("has_war_with = STP", host)
        self.assertNotIn("tag = STP", host)
        self.assertIn("NOT = { has_war_with = VAL }", host)

        diplo = block(
            read("common/scripted_triggers/00_diplo_action_valid_triggers.txt"),
            "is_diplomatic_action_valid_send_volunteers",
        )
        self.assertIn("VAL_stelander_volunteer_mandate", diplo)
        self.assertIn("VAL_stelander_volunteer_host = yes", diplo)

        decisions = read("common/decisions/ADISCORD_VAL_decisions.txt")
        category = block(decisions, "VAL_stelander_war_aid")
        for decision_id in (
            "VAL_back_shabrat",
            "VAL_stelander_volunteers",
            "VAL_stelander_rifle_aid",
            "VAL_stelander_staff_fund",
        ):
            self.assertIn(decision_id + " =", category)

        back = block(decisions, "VAL_back_shabrat")
        self.assertIn("VAL_start_stelander_support = yes", back)
        self.assertIn("ai_will_do = { base = 0 }", back)

        volunteers = block(decisions, "VAL_stelander_volunteers")
        self.assertIn("VAL_stelander_support_active = yes", volunteers)
        self.assertIn("add_ideas = VAL_stelander_volunteer_mandate", volunteers)

    def test_material_support_is_paid_and_counted_once(self):
        decisions = read("common/decisions/ADISCORD_VAL_decisions.txt")

        rifles = block(decisions, "VAL_stelander_rifle_aid")
        self.assertIn("custom_cost_text = VAL_stelander_rifle_aid_cost", rifles)
        self.assertIn("has_equipment = { infantry_equipment < 20000 }", rifles)
        self.assertIn("add_political_power = -25", rifles)
        self.assertIn("amount = 20000", rifles)
        self.assertIn("target = STS", rifles)
        self.assertIn("set_country_flag = VAL_stelander_rifle_aid_sent", rifles)
        self.assertEqual(rifles.count("VAL_add_stelander_support_point = yes"), 1)

        staff = block(decisions, "VAL_stelander_staff_fund")
        self.assertIn("custom_cost_text = VAL_stelander_staff_fund_cost", staff)
        self.assertIn("ADISCORD_economy_can_spend_500 = yes", staff)
        self.assertIn("add_political_power = -35", staff)
        self.assertIn("ADISCORD_economy_spend_500 = yes", staff)
        self.assertIn("var = ADISCORD_economy_treasury value = 500", staff)
        self.assertIn("army_experience = 10", staff)
        self.assertIn("add_command_power = 15", staff)
        self.assertEqual(staff.count("VAL_add_stelander_support_point = yes"), 1)

        effects = read("common/scripted_effects/ADISCORD_VAL_effects.txt")
        weekly = block(effects, "VAL_stelander_support_weekly")
        self.assertIn("has_volunteers_amount_from = { tag = VAL count > 0 }", weekly)
        self.assertIn(
            "NOT = { has_country_flag = VAL_stelander_volunteer_contribution }", weekly
        )
        self.assertIn("set_country_flag = VAL_stelander_volunteer_contribution", weekly)

    def test_shabrat_victory_pays_scaled_dividends(self):
        effects = read("common/scripted_effects/ADISCORD_VAL_effects.txt")
        payout = block(effects, "VAL_settle_stelander_support_victory")
        self.assertIn("value = 2 compare = greater_than_or_equals", payout)
        self.assertIn("idea = VAL_stelander_shabrat_major_dividend days = 365", payout)
        self.assertIn("value = 0 compare = greater_than", payout)
        self.assertIn("idea = VAL_stelander_shabrat_dividend days = 270", payout)
        self.assertIn("country_event = { id = val_contract.374 }", payout)
        self.assertIn("VAL_close_stelander_support = yes", payout)

        ideas = read("common/ideas/ADISCORD_VAL_rework_ideas.txt")
        major = block(ideas, "VAL_stelander_shabrat_major_dividend")
        self.assertIn("ADISCORD_economy_trade_income_factor = 0.15", major)
        self.assertIn("industrial_capacity_factory = 0.05", major)
        self.assertIn("production_factory_max_efficiency_factor = 0.03", major)
        partial = block(ideas, "VAL_stelander_shabrat_dividend")
        self.assertIn("ADISCORD_economy_trade_income_factor = 0.08", partial)

        settlement = block(
            read("common/scripted_effects/ADISCORD_STP_scripted_effects.txt"),
            "STP_cw_settle_union_victory",
        )
        self.assertIn("VAL_settle_stelander_support_victory = yes", settlement)
        self.assertIn("VAL_close_stelander_support = yes", settlement)

        nod = block(
            read("common/scripted_effects/ADISCORD_STP_scripted_effects.txt"),
            "STP_cw_settle_nod_victory",
        )
        self.assertIn("VAL_close_stelander_support = yes", nod)

    def test_custom_costs_and_battle_text_exist_in_both_languages(self):
        for language in ("english", "russian"):
            loc = read(
                f"localisation/{language}/ADISCORD_VAL_decisions_l_{language}.yml"
            )
            self.assertIn('VAL_stelander_war_aid:0 "', loc)
            for key in (
                "VAL_stelander_rifle_aid_cost",
                "VAL_stelander_staff_fund_cost",
            ):
                for suffix in ("", "_blocked", "_tooltip"):
                    self.assertIn(key + suffix + ":0", loc)
            self.assertIn("val_contract.374.t:0", loc)
            self.assertIn("VAL_stelander_shabrat_major_dividend:0", loc)


if __name__ == "__main__":
    unittest.main()
