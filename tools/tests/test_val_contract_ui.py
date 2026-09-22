from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def named_block(text: str, name: str) -> str:
    match = re.search(rf"(?m)^\s*{re.escape(name)}\s*=\s*\{{", text)
    if not match:
        raise AssertionError(f"missing block {name}")
    start = match.start()
    brace = text.find("{", match.start(), match.end())
    depth = 0
    in_string = False
    escaped = False
    for index in range(brace, len(text)):
        char = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start:index + 1]
    raise AssertionError(f"unclosed block {name}")


class TestValContractUi(unittest.TestCase):
    def test_contract_state_is_visible_and_reports_live_authority(self) -> None:
        dynamic = read("common/dynamic_modifiers/ADISCORD_VAL_contract_dynamic_modifier.txt")
        contract_state = named_block(dynamic, "VAL_contract_state")
        self.assertIn("icon = GFX_idea_VAL_contract_state", contract_state)

        on_actions = read("common/on_actions/02_ADISCORD_VAL_rework_on_actions.txt")
        startup = named_block(on_actions, "on_startup")
        weekly = named_block(on_actions, "on_weekly_VAL")
        self.assertEqual(startup.count("VAL_initialize_contract_authority = yes"), 1)
        self.assertNotIn("NOT = { has_dynamic_modifier = { modifier = VAL_contract_state } }", startup)
        self.assertIn("has_dynamic_modifier = { modifier = VAL_contract_state }", weekly)
        self.assertIn("VAL_initialize_contract_authority = yes", weekly)

        history = read("history/countries/VAL - ValeraLand.txt")
        self.assertIn("VAL_mercenary_state", history)

        english = read("localisation/english/ADISCORD_VAL_decisions_l_english.yml")
        russian = read("localisation/russian/ADISCORD_VAL_decisions_l_russian.yml")
        self.assertIn('VAL_contract_state: "Contract System Authority"', english)
        self.assertIn('VAL_contract_state: "Авторитет контрактной системы"', russian)
        for localisation in (english, russian):
            self.assertIn("[?VAL_contract_authority|0]/100", localisation)
            self.assertIn("[VALGetContractAuthorityBand]", localisation)

    def test_authority_labels_match_modifier_bands(self) -> None:
        scripted = read("common/scripted_localisation/ADISCORD_VAL_contract_scripted_loc.txt")
        band = named_block(scripted, "defined_text")
        marker = scripted.index("name = VALGetContractAuthorityBand")
        start = scripted.rfind("defined_text", 0, marker)
        authority_band = named_block(scripted[start:], "defined_text")

        expected = (
            ("90", "VAL_CONTRACT_AUTHORITY_DOMINANT"),
            ("75", "VAL_CONTRACT_AUTHORITY_CENTRALIZED"),
            ("50", "VAL_CONTRACT_AUTHORITY_COHERENT"),
            ("25", "VAL_CONTRACT_AUTHORITY_BROKERED"),
        )
        for value, key in expected:
            self.assertIn(f"value = {value} compare = greater_than_or_equals", authority_band)
            self.assertIn(f"localization_key = {key}", authority_band)
        self.assertIn("localization_key = VAL_CONTRACT_AUTHORITY_FRAGMENTED", authority_band)

    def test_decision_categories_are_consolidated_without_losing_decisions(self) -> None:
        categories = read("common/decisions/categories/ADISCORD_VAL_rework_categories.txt")
        decisions = read("common/decisions/ADISCORD_VAL_decisions.txt")

        for current in ("VAL_contract_management", "VAL_postwar_administration"):
            self.assertIn(f"{current} = {{", categories)
            self.assertIn(f"{current} = {{", decisions)

        for obsolete in (
            "VAL_propaganda_campaigns",
            "VAL_contract_obligations",
            "VAL_regional_integration",
            "VAL_commonwealth_formation",
        ):
            self.assertNotRegex(categories, rf"(?m)^\s*{obsolete}\s*=\s*\{{")
            self.assertNotRegex(decisions, rf"(?m)^\s*{obsolete}\s*=\s*\{{")

        contract = named_block(decisions, "VAL_contract_management")
        for decision in (
            "VAL_campaign_rifles_and_bread",
            "VAL_campaign_contracts_feed_families",
            "VAL_campaign_no_promise_without_payment",
            "VAL_campaign_the_mine_was_stolen",
            "VAL_quarterly_contract_deadline",
            "VAL_pay_quarterly_contract_norm",
        ):
            self.assertIn(f"{decision} = {{", contract)

        postwar = named_block(decisions, "VAL_postwar_administration")
        for decision in ("VAL_nationalise_region", "VAL_proclaim_commonwealth"):
            self.assertIn(f"{decision} = {{", postwar)
        self.assertNotIn("VAL_establish_regional_administration =", postwar)

    def test_sparse_contract_unlock_focuses_are_short_or_have_immediate_value(self) -> None:
        focuses = read("common/national_focus/ADISCORD_national_focus_VAL.txt")
        for focus_id in (
            "VAL_Foreign_Broker_Licences",
            "VAL_Northern_Clearing_House",
            "VAL_Contingency_Ledgers",
            "VAL_econ_automation",
            "VAL_econ_logistics",
            "VAL_econ_computing",
            "VAL_Resource_War_Contracts",
            "VAL_frontier_return_irem",
        ):
            block = named_block(focuses[focuses.index(f"id = {focus_id}") - 80:], "focus")
            cost = re.search(r"(?m)^\s*cost\s*=\s*([0-9.]+)", block)
            self.assertIsNotNone(cost, focus_id)
            self.assertLessEqual(float(cost.group(1)), 3, focus_id)

        licences = focuses[focuses.index("id = VAL_Foreign_Broker_Licences"):]
        self.assertIn("add_political_power = 25", licences[:1800])
        self.assertIn("VAL_change_contract_authority = yes", licences[:1800])

        clearing = focuses[focuses.index("id = VAL_Northern_Clearing_House"):]
        self.assertIn("ADISCORD_economy_receive_15 = yes", clearing[:1200])

        advisers = focuses[focuses.index("id = VAL_Contingency_Ledgers"):]
        self.assertIn("add_command_power = 15", advisers[:1200])

    def test_contract_authority_improves_political_cashflow(self) -> None:
        effects = read("common/scripted_effects/ADISCORD_VAL_effects.txt")
        refresh = named_block(effects, "VAL_refresh_contract_modifier")
        base_assignments = re.findall(r"set_variable = \{ var = VAL_contract_pp_gain value = (-?\d+(?:\.\d+)?) \}", refresh)
        self.assertGreaterEqual(len(base_assignments), 5)
        self.assertEqual(base_assignments[:5], ["-0.05", "0.05", "0.10", "0.15", "0.20"])

        decisions = read("common/decisions/ADISCORD_VAL_decisions.txt")
        chancery = named_block(decisions, "VAL_fund_contract_chancery")
        self.assertIn("ADISCORD_economy_can_spend_100 = yes", chancery)
        self.assertIn("ADISCORD_economy_spend_100 = yes", chancery)
        self.assertIn("add_political_power = 75", chancery)
        self.assertIn("days_re_enable = 90", chancery)

    def test_nationalisation_is_a_repeatable_adjacent_core_chain(self) -> None:
        decisions = read("common/decisions/ADISCORD_VAL_decisions.txt")
        nationalise = named_block(decisions, "VAL_nationalise_region")
        for token in (
            "state_target = yes",
            "any_neighbor_state = {",
            "is_core_of = ROOT",
            "is_owned_by = ROOT",
            "is_controlled_by = ROOT",
            "NOT = { is_core_of = ROOT }",
            "set_country_flag = VAL_regional_integration_active",
            "add_core_of = ROOT",
            "fire_only_once = no",
        ):
            self.assertIn(token, nationalise)
        self.assertNotIn("compliance", nationalise)
        self.assertNotIn("resistance", nationalise)


class TestValPropagandaRewards(unittest.TestCase):
    campaigns = (
        "VAL_campaign_rifles_and_bread",
        "VAL_campaign_contracts_feed_families",
        "VAL_campaign_no_promise_without_payment",
        "VAL_campaign_the_mine_was_stolen",
    )

    def focus(self, focus_id: str) -> str:
        text = read("common/national_focus/ADISCORD_national_focus_VAL.txt")
        matches = list(re.finditer(rf"\bid\s*=\s*{re.escape(focus_id)}\b", text))
        self.assertEqual(len(matches), 1, focus_id)
        starts = list(re.finditer(r"(?m)^\s*focus\s*=\s*\{", text[:matches[0].start()]))
        self.assertTrue(starts, focus_id)
        return named_block(text[starts[-1].start():], "focus")

    def decision(self, decision_id: str) -> str:
        category = named_block(read("common/decisions/ADISCORD_VAL_decisions.txt"), "VAL_contract_management")
        return named_block(category, decision_id)

    def number(self, text: str, key: str) -> float:
        values = re.findall(rf"(?m)^\s*{re.escape(key)}\s*=\s*(-?\d+(?:\.\d+)?)\s*$", text)
        self.assertEqual(len(values), 1, key)
        return float(values[0])

    def test_ministry_funds_any_initial_campaign_and_lists_its_unlocks(self) -> None:
        reward = named_block(self.focus("VAL_Ministry_Of_Contract_Memory"), "completion_reward")
        self.assertRegex(reward, r"(?m)^\t{3}add_political_power = 50$")
        funds = self.number(reward, "add_political_power")
        for decision_id in self.campaigns[:3]:
            with self.subTest(decision=decision_id):
                self.assertEqual(reward.count(f"unlock_decision_tooltip = {decision_id}"), 1)
                self.assertGreaterEqual(funds, self.number(self.decision(decision_id), "cost"))
        self.assertIn("custom_effect_tooltip = VAL_campaign_mine_unlock_tt", reward)
        self.assertNotIn("unlock_decision_tooltip = VAL_campaign_the_mine_was_stolen", reward)

    def test_slot_rewards_hide_bookkeeping_and_preserve_one_time_grants(self) -> None:
        for focus_id, flag, tooltip in (
            ("VAL_Ministry_Of_Contract_Memory", "VAL_propaganda_slot_granted", "VAL_campaign_slot_granted_tt"),
            ("VAL_Two_Concurrent_Narratives", "VAL_second_propaganda_slot_granted", "VAL_campaign_second_slot_tt"),
        ):
            with self.subTest(focus=focus_id):
                reward = named_block(self.focus(focus_id), "completion_reward")
                self.assertIn(f"custom_effect_tooltip = {tooltip}", reward)
                hidden = named_block(reward, "hidden_effect")
                guarded = named_block(hidden, "if")
                self.assertIn(f"NOT = {{ has_country_flag = {flag} }}", named_block(guarded, "limit"))
                self.assertEqual(guarded.count("ADISCORD_campaign_slot_grant = yes"), 1)
                self.assertEqual(guarded.count(f"set_country_flag = {flag}"), 1)
                visible = reward.replace(hidden, "")
                self.assertNotIn("ADISCORD_campaign_slot_grant", visible)
                self.assertNotIn("set_country_flag", visible)
        self.assertLessEqual(self.number(self.focus("VAL_Two_Concurrent_Narratives"), "cost"), self.number(self.focus("VAL_Ministry_Of_Contract_Memory"), "cost"))

    def test_campaign_unlock_is_independent_of_quarterly_category_visibility(self) -> None:
        category = named_block(read("common/decisions/categories/ADISCORD_VAL_rework_categories.txt"), "VAL_contract_management")
        alternatives = named_block(named_block(category, "visible"), "OR")
        self.assertIn("has_completed_focus = VAL_Ministry_Of_Contract_Memory", alternatives)
        self.assertIn("has_completed_focus = VAL_Quarterly_Contract_Norm", alternatives)
        for decision_id in self.campaigns:
            with self.subTest(decision=decision_id):
                decision = self.decision(decision_id)
                visible = named_block(decision, "visible")
                self.assertIn("has_completed_focus = VAL_Ministry_Of_Contract_Memory", visible)
                self.assertNotIn("OR =", visible)
                self.assertNotIn("ADISCORD_has_campaign_slot", visible)
                available = named_block(decision, "available")
                self.assertIn("tooltip = VAL_campaign_slot_available_tt", available)
                self.assertIn("ADISCORD_has_campaign_slot = yes", available)
        mine = named_block(self.decision(self.campaigns[-1]), "visible")
        self.assertIn("has_country_flag = VAL_westerholm_metal_lost", mine)

    def test_political_campaign_has_a_positive_base_return_and_refreshes_income(self) -> None:
        decision = self.decision("VAL_campaign_no_promise_without_payment")
        cost = self.number(decision, "cost")
        days = self.number(decision, "days_remove")
        modifier = named_block(decision, "modifier")
        gain = self.number(modifier, "political_power_gain")
        self.assertGreater(cost, 0)
        self.assertGreater(days * gain, cost)
        self.assertLessEqual(days * gain - cost, 15)
        self.assertGreaterEqual(self.number(decision, "days_re_enable"), days)
        self.assertEqual(self.number(modifier, "ADISCORD_economy_trade_income_factor"), 0.08)
        for effect in ("complete_effect", "remove_effect"):
            self.assertEqual(named_block(decision, effect).count("ADISCORD_economy_mark_dirty = yes"), 1)

    def test_every_campaign_uses_and_returns_one_shared_slot(self) -> None:
        for decision_id in self.campaigns:
            with self.subTest(decision=decision_id):
                decision = self.decision(decision_id)
                self.assertEqual(named_block(decision, "complete_effect").count("ADISCORD_campaign_slot_consume = yes"), 1)
                self.assertEqual(named_block(decision, "remove_effect").count("ADISCORD_campaign_slot_release = yes"), 1)
                self.assertNotIn("ADISCORD_campaign_slot_grant", decision)
                self.assertGreater(self.number(decision, "days_remove"), 0)

    def test_campaign_tooltips_and_free_slot_display_exist_in_both_languages(self) -> None:
        keys = ("VAL_campaign_slot_granted_tt", "VAL_campaign_second_slot_tt", "VAL_campaign_mine_unlock_tt", "VAL_campaign_slot_available_tt", "VAL_contract_management_desc", "VAL_Ministry_Of_Contract_Memory_desc", "VAL_Two_Concurrent_Narratives_desc", "VAL_campaign_no_promise_without_payment_desc")
        for language in ("russian", "english"):
            path = ROOT / f"localisation/{language}/ADISCORD_VAL_decisions_l_{language}.yml"
            self.assertTrue(path.read_bytes().startswith(b"\xef\xbb\xbf"))
            text = path.read_text(encoding="utf-8-sig")
            for key in keys:
                with self.subTest(language=language, key=key):
                    entries = re.findall(rf'(?m)^\s*{re.escape(key)}:(?:\d+)?\s+"([^"\r\n]*)"\s*$', text)
                    self.assertEqual(len(entries), 1, key)
                    self.assertTrue(entries[0])
                    if key in ("VAL_contract_management_desc", "VAL_campaign_slot_available_tt"):
                        self.assertIn("[?ADISCORD_available_campaign_slots|0]", entries[0])

    def test_campaign_files_have_no_merge_markers_or_duplicate_definitions(self) -> None:
        for path in ("common/national_focus/ADISCORD_national_focus_VAL.txt", "common/decisions/ADISCORD_VAL_decisions.txt", "common/decisions/categories/ADISCORD_VAL_rework_categories.txt"):
            text = read(path)
            self.assertNotRegex(text, r"(?m)^(?:<{7}|={7}(?:\r?$)|>{7})(?: |$)")
        decisions = read("common/decisions/ADISCORD_VAL_decisions.txt")
        for decision_id in self.campaigns:
            self.assertEqual(len(re.findall(rf"(?m)^\s*{re.escape(decision_id)}\s*=\s*\{{", decisions)), 1)



class TestValMergedContractFlows(unittest.TestCase):
    def test_quarterly_payment_debits_pp_only_after_the_val_rifle_receipt(self):
        decisions = read("common/decisions/ADISCORD_VAL_decisions.txt")
        decision = named_block(named_block(decisions, "VAL_contract_management"), "VAL_pay_quarterly_contract_norm")
        self.assertNotIn("add_political_power", named_block(decision, "complete_effect"))
        effect = named_block(read("common/scripted_effects/ADISCORD_VAL_effects.txt"), "VAL_pay_quarterly_contract_norm")
        self.assertNotIn("STP_cw_rifles_paid", effect)
        self.assertEqual(effect.count("add_political_power = -10"), 1)
        receipt = effect.index("has_country_flag = VAL_contract_rifles_paid")
        self.assertLess(receipt, effect.index("add_political_power = -10"))
        self.assertLess(effect.index("add_political_power = -10"), effect.index("set_country_flag = VAL_quarterly_contract_paid"))

    def test_export_capacity_is_defined_once_and_is_not_a_second_payment(self):
        ideas = read("common/ideas/ADISCORD_VAL_rework_ideas.txt")
        for name in ("VAL_export_income_1", "VAL_export_income_2", "VAL_advisors_income", "VAL_paid_military_advisors"):
            with self.subTest(idea=name):
                self.assertEqual(len(re.findall(r"(?m)^\s*" + name + r"\s*=\s*\{", ideas)), 1)
                self.assertNotIn("ADISCORD_economy_weekly_income", named_block(ideas, name))

    def test_reclamation_state_and_industry_use_distinct_stage_gates(self):
        text = read("common/scripted_triggers/ADISCORD_VAL_rework_triggers.txt")
        state = named_block(text, "VAL_reclamation_state_project_valid")
        for name in ("ADISCORD_vorkerland_dirty_state", "VAL_reclamation_stage_1_modifier", "VAL_reclamation_stage_2_modifier"):
            self.assertIn("modifier = " + name, state)
        self.assertNotIn("ROOT", state)
        industry = named_block(text, "VAL_reclamation_industry_target_valid")
        self.assertIn("value = 3 compare = equals", industry)
        self.assertIn("industrial_complex < 19", industry)
        self.assertNotIn("VAL_reclamation_clean_water", industry)
        self.assertNotIn("ADISCORD_vorkerland_dirty_state", industry)

    def test_reclamation_refresh_preserves_untreated_states_and_is_idempotent(self):
        from tools.validators.validate_adiscord_division_templates import parse_clausewitz
        text = read("common/scripted_effects/ADISCORD_VAL_effects.txt")
        raw = named_block(text, "VAL_reclamation_refresh_state")
        self.assertNotIn("<<<<<<<", raw)
        body = parse_clausewitz(raw)[0].value
        def field(entry, key):
            return next(e.value for e in entry.value if e.key == key)
        for stage in (0, 1, 2, 3, 4):
            modifiers = {"ADISCORD_vorkerland_dirty_state"}
            values = {"VAL_reclamation_stage": stage}
            def condition(e):
                if e.key == "check_variable":
                    actual = values.get(field(e, "var"), 0)
                    target = float(field(e, "value"))
                    return actual >= target
                if e.key == "has_dynamic_modifier":
                    return field(e, "modifier") in modifiers
                raise AssertionError(e.key)
            def execute(entries):
                matched = False
                for e in entries:
                    if e.key in ("if", "else_if", "else"):
                        if e.key == "if": matched = False
                        limit = next((v.value for v in e.value if v.key == "limit"), [])
                        if not matched and all(condition(v) for v in limit):
                            execute([v for v in e.value if v.key != "limit"])
                            matched = True
                    elif e.key == "remove_dynamic_modifier": modifiers.discard(field(e, "modifier"))
                    elif e.key == "add_dynamic_modifier": modifiers.add(field(e, "modifier"))
                    elif e.key == "clear_variable": values.pop(e.value, None)
                    else: raise AssertionError(e.key)
            for repeat in range(2):
                execute(body)
                expected = {"ADISCORD_vorkerland_dirty_state"} if stage == 0 else {f"VAL_reclamation_stage_{min(stage, 3)}_modifier"}
                with self.subTest(stage=stage, repeat=repeat): self.assertEqual(modifiers, expected)

    def test_merge_preserves_corridor_ui_and_native_paid_program_previews(self):
        for language in ("russian", "english"):
            text = read(f"localisation/{language}/ADISCORD_VAL_decisions_l_{language}.yml")
            self.assertIn("$VAL_trade_corridors_desc$", text)
            self.assertIn("VAL_focus_paid_program_authorization_tt", text)
            self.assertNotRegex(text, r"(?m)^(?:<<<<<<<|=======|>>>>>>>)")
        focuses = read("common/national_focus/ADISCORD_national_focus_VAL.txt")
        for decision in ("ADISCORD_economy_automated_industry", "ADISCORD_economy_logistics_contract", "ADISCORD_economy_national_computing"):
            self.assertIn("unlock_decision_tooltip = { decision = " + decision + " show_effect_tooltip = yes }", focuses)

if __name__ == "__main__":
    unittest.main()
