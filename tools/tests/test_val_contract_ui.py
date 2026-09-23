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


class ValNorthernCoalitionAidTests(unittest.TestCase):
    """Evaluate authored aid branches; native callbacks still need campaign QA."""

    @classmethod
    def setUpClass(cls):
        from tools.tests.test_adiscord_stp_preparation import parse_clausewitz
        cls.effects = {e.key: e.value for e in parse_clausewitz(read("common/scripted_effects/ADISCORD_VAL_effects.txt"))}
        cls.triggers = {e.key: e.value for e in parse_clausewitz(read("common/scripted_triggers/ADISCORD_VAL_rework_triggers.txt"))}

    def facts(self, campaign=1, state=2):
        facts = {("VAL", "has_variable", "VAL_northern_aid_state"): True,
                 ("VAL", "variable", "VAL_northern_aid_state"): state,
                 ("NOD", "variable", "STP_cw_northern_campaign_status"): campaign,
                 ("VAL", "has_capitulated", "no"): True,
                 ("VAL", "is_subject", "no"): True}
        for tag in ("YPR", "COF", "TFF"):
            facts.update({(tag, "exists", "yes"): True, (tag, "has_capitulated", "no"): True,
                          (tag, "is_subject", "no"): True, (tag, "has_war_with", "NOD"): True})
        return facts

    def test_resource_side_choices_have_native_country_admission(self):
        from tools.tests.test_adiscord_stp_preparation import parse_clausewitz, block, matches_conditions
        category = block(parse_clausewitz(read("common/decisions/ADISCORD_VAL_decisions.txt")), "VAL_resource_war_aid")
        for name in ("VAL_negotiate_nam_metals", "VAL_negotiate_efl_metals"):
            with self.subTest(decision=name):
                admission = block(block(category, name), "allowed")
                self.assertTrue(admission, "Native decision admission must be explicit")
                self.assertTrue(matches_conditions(admission, {}, "VAL"))
                self.assertFalse(matches_conditions(admission, {}, "STP"))

    def expand(self, rows, facts, scope="VAL"):
        from dataclasses import replace
        from tools.tests.test_adiscord_stp_preparation import scalar
        result = []
        for row in rows:
            if row.key in self.triggers:
                result.append(replace(row, key="AND" if row.value == "yes" else "NOT",
                                      value=self.expand(self.triggers[row.key], facts, scope)))
            elif row.key == "has_volunteers_amount_from":
                self.assertEqual(scalar(row.value, "tag"), "VAL")
                field, operator, threshold = [e.value for e in row.value if not e.key]
                self.assertEqual((field, operator), ("count", ">"))
                result.append(replace(row, key="always", value="yes" if facts.get((scope, "volunteers"), 0) > int(threshold) else "no"))
            elif isinstance(row.value, list):
                child_scope = row.key if row.key in ("YPR", "COF", "TFF", "NOD", "FROM") else scope
                result.append(replace(row, value=self.expand(row.value, facts, child_scope)))
            else:
                result.append(row)
        return result

    def test_missing_partner_reference_or_individual_defeat_does_not_settle_live_campaign(self):
        from tools.tests.test_adiscord_stp_preparation import selected_effects
        for defeated in (None, "YPR", "COF", "TFF"):
            facts = self.facts()
            if defeated:
                facts[defeated, "has_capitulated", "yes"] = True
                facts[defeated, "has_capitulated", "no"] = False
            selected = [e.key for _, e in selected_effects(self.effects["VAL_northern_aid_daily"], facts, "VAL")]
            with self.subTest(defeated=defeated):
                self.assertFalse(any(key in selected for key in ("VAL_settle_northern_aid_defeat", "VAL_settle_northern_aid_victory", "VAL_close_northern_aid")))

    def test_campaign_outcomes_select_one_settlement(self):
        from tools.tests.test_adiscord_stp_preparation import selected_effects
        for campaign, expected in ((2, "VAL_settle_northern_aid_defeat"), (3, "VAL_settle_northern_aid_victory"), (4, "VAL_close_northern_aid")):
            facts = self.facts(campaign=campaign)
            selected = [e.key for _, e in selected_effects(self.effects["VAL_northern_aid_daily"], facts, "VAL")]
            self.assertEqual(selected, [expected])

    def test_all_three_recipients_remain_eligible_after_obligations_are_met(self):
        from tools.tests.test_adiscord_stp_preparation import block, matches_conditions
        for state in (1, 2, 3, -1):
            for tag in ("YPR", "COF", "TFF", "STS"):
                facts = self.facts(state=state)
                facts.update({("FROM", "exists", "yes"): True, ("FROM", "has_capitulated", "no"): True,
                              ("FROM", "is_subject", "no"): True, ("FROM", "has_war_with", "NOD"): True,
                              ("VAL", "numeric", "has_manpower"): 2000, ("VAL", "numeric", "command_power"): 25})
                from dataclasses import replace
                def target(rows):
                    return [replace(e, value=target(e.value) if isinstance(e.value, list) else ("FROM" if e.key == "tag" and e.value == tag else e.value)) for e in rows]
                gate = block(block(self.effects["VAL_deliver_northern_aid_personnel"], "if"), "limit")
                expanded = target(self.expand(gate, facts))
                with self.subTest(state=state, recipient=tag):
                    self.assertEqual(matches_conditions(expanded, facts, "VAL"), state in (1, 2) and tag != "STS")

    def test_volunteers_count_across_recipients_but_exclude_defeated_hosts(self):
        from tools.tests.test_adiscord_stp_preparation import matches_conditions
        for counts, expected in (((0, 0, 0), False), ((1, 0, 0), False), ((2, 0, 0), True), ((1, 1, 0), True), ((1, 0, 1), True), ((0, 1, 1), True)):
            facts = self.facts()
            for tag, count in zip(("YPR", "COF", "TFF"), counts):
                facts[tag, "volunteers"] = count
            rule = self.triggers["VAL_northern_aid_volunteers_present"]
            self.assertEqual(matches_conditions(self.expand(rule, facts), facts, "VAL"), expected)
        facts = self.facts()
        facts["COF", "volunteers"] = 2
        facts["COF", "has_capitulated", "no"] = False
        self.assertFalse(matches_conditions(self.expand(rule, facts), facts, "VAL"))

    def test_volunteer_days_continue_after_deliveries_without_reopening_contract(self):
        from tools.tests.test_adiscord_stp_preparation import selected_effects, scalar

        def tick(facts, name="VAL_northern_aid_daily"):
            for _, row in selected_effects(self.expand(self.effects[name], facts), facts, "VAL"):
                if row.key in ("add_to_variable", "set_variable"):
                    key = ("VAL", "variable", scalar(row.value, "var"))
                    amount = float(scalar(row.value, "value"))
                    facts[key] = facts.get(key, 0) + amount if row.key == "add_to_variable" else amount
                elif row.key == "VAL_complete_northern_aid":
                    tick(facts, row.key)
                else:
                    self.fail(f"Unexpected daily effect: {row.key}")

        days = ("VAL", "variable", "VAL_northern_aid_volunteer_days")
        for state, mission, expected in ((1, True, 1), (1, False, 0), (2, False, 1), (-1, False, 0), (3, False, 0)):
            with self.subTest(state=state, mission=mission):
                facts = self.facts(state=state)
                facts["VAL", "has_active_mission", "VAL_northern_aid_deadline"] = mission
                facts["COF", "volunteers"] = 2
                tick(facts)
                self.assertEqual(facts.get(days, 0), expected)

        facts = self.facts(state=2)
        facts[days] = 0
        facts["COF", "volunteers"] = 2
        for _ in range(30):
            tick(facts)
        self.assertEqual(facts[days], 30)
        facts["COF", "volunteers"] = 1
        tick(facts)
        self.assertEqual(facts[days], 0)
        self.assertEqual(facts["VAL", "variable", "VAL_northern_aid_state"], 2)

    def test_rifle_shipments_share_one_ledger_without_duplicate_payment(self):
        from tools.tests.test_adiscord_stp_preparation import selected_effects, scalar
        facts = self.facts(state=1)
        facts["VAL", "equipment", "infantry_equipment"] = 7500
        delivered = {tag: 0 for tag in ("YPR", "COF", "TFF")}

        def execute(name, recipient):
            for _, row in selected_effects(self.expand(self.effects[name], facts), facts, "VAL"):
                if row.key == "send_equipment":
                    self.assertEqual(scalar(row.value, "target"), "FROM")
                    amount = int(scalar(row.value, "amount"))
                    facts["VAL", "equipment", "infantry_equipment"] -= amount
                    delivered[recipient] += amount
                elif row.key in ("add_to_variable", "set_variable"):
                    key = ("VAL", "variable", scalar(row.value, "var"))
                    amount = float(scalar(row.value, "value"))
                    facts[key] = facts.get(key, 0) + amount if row.key == "add_to_variable" else amount
                elif row.key == "VAL_complete_northern_aid":
                    execute(row.key, recipient)
                else:
                    self.fail(f"Unmodelled rifle delivery effect: {row.key}")

        for recipient, expected_state in (("YPR", 1), ("COF", 2), ("TFF", 2)):
            # Recipient eligibility is independently exercised for every tag above.
            facts["FROM", "VAL_northern_aid_recipient", "yes"] = True
            original = self.triggers.pop("VAL_northern_aid_recipient")
            try:
                execute("VAL_deliver_northern_aid_arms", recipient)
            finally:
                self.triggers["VAL_northern_aid_recipient"] = original
            self.assertEqual(facts["VAL", "variable", "VAL_northern_aid_state"], expected_state)
        self.assertEqual(delivered, {"YPR": 2500, "COF": 2500, "TFF": 2500})
        self.assertEqual(facts["VAL", "variable", "VAL_northern_aid_rifles"], 7500)
        self.assertEqual(facts["VAL", "equipment", "infantry_equipment"], 0)

    def test_paid_legacy_defeat_reopens_only_during_the_live_campaign(self):
        from tools.tests.test_adiscord_stp_preparation import selected_effects, scalar
        self.assertIn("VAL_restore_fulfilled_northern_aid", self.effects)
        for campaign, state, penalty, paid, expected in ((1, 3, True, 2000, True), (2, 3, True, 2000, False),
                (1, 2, True, 2000, False), (1, 3, False, 2000, False), (1, 3, True, 0, False)):
            facts = self.facts(campaign=campaign, state=state)
            facts["VAL", "has_idea", "VAL_northern_aid_failure"] = penalty
            facts["VAL", "variable", "VAL_northern_aid_personnel"] = paid
            rows = list(selected_effects(self.expand(self.effects["VAL_restore_fulfilled_northern_aid"], facts), facts, "VAL"))
            with self.subTest(campaign=campaign, state=state, penalty=penalty, paid=paid):
                self.assertEqual(bool(rows), expected)
                if expected:
                    self.assertEqual([e.key for _, e in rows], ["remove_ideas", "set_variable", "ADISCORD_economy_mark_dirty"])
                    self.assertEqual(rows[0][1].value, "VAL_northern_aid_failure")
                    self.assertEqual(scalar(rows[1][1].value, "value"), "2")


class ValPartnerSettlementTests(unittest.TestCase):
    """Execute the authored transaction branches; this is not native-engine proof."""

    @classmethod
    def setUpClass(cls):
        from tools.validators.validate_adiscord_division_templates import parse_clausewitz
        cls.triggers = {e.key: e.value for e in parse_clausewitz(read("common/scripted_triggers/ADISCORD_VAL_rework_triggers.txt"))}
        cls.effects = {e.key: e.value for e in parse_clausewitz(read("common/scripted_effects/ADISCORD_VAL_effects.txt"))}

    def matches(self, name, facts, scope):
        from tools.tests.test_validate_adiscord_val_rework import ValExpandedCampaignTests
        return ValExpandedCampaignTests.match(self, name, facts, scope, root=scope)

    def execute(self, name, facts, buyer="CIN"):
        from tools.tests.test_adiscord_stp_preparation import scalar, block
        from tools.tests.test_validate_adiscord_val_rework import ValExpandedCampaignTests

        def run(rows, scope):
            taken = False
            for row in rows:
                key, value = row.key, row.value
                if key in ("if", "else_if", "else"):
                    if key == "if":
                        taken = False
                    if key != "else":
                        self.triggers["test_partner_condition"] = block(value, "limit")
                    if not taken and (key == "else" or ValExpandedCampaignTests.match(self, "test_partner_condition", facts, scope, root=buyer)):
                        taken = True
                        run([e for e in value if e.key != "limit"], scope)
                elif key in ("VAL", "ROOT"):
                    run(value, "VAL" if key == "VAL" else buyer)
                elif key in ("ADISCORD_economy_initialize_country", "ADISCORD_economy_mark_dirty", "log"):
                    continue
                elif key == "add_dynamic_modifier":
                    facts[scope, "has_dynamic_modifier", scalar(value, "modifier")] = True
                elif key == "force_update_dynamic_modifier":
                    continue
                elif key in self.effects:
                    self.assertEqual(value, "yes")
                    run(self.effects[key], scope)
                elif key == "set_variable":
                    facts[scope, "variable", scalar(value, "var")] = float(scalar(value, "value"))
                elif key == "clamp_variable":
                    field = (scope, "variable", scalar(value, "var"))
                    facts[field] = max(float(scalar(value, "min")), min(float(scalar(value, "max")), facts.get(field, 0)))
                elif key == "add_political_power":
                    field = (scope, "numeric", "has_political_power")
                    facts[field] = facts.get(field, 0) + float(value)
                elif key == "country_event":
                    field = (scope, "scheduled", scalar(value, "id"))
                    facts[field] = facts.get(field, ()) + (float(scalar(value, "days")),)
                elif key in ("add_to_variable", "subtract_from_variable"):
                    field = (scope, "variable", scalar(value, "var"))
                    facts[field] = facts.get(field, 0) + float(scalar(value, "value")) * (1 if key == "add_to_variable" else -1)
                elif key in ("set_country_flag", "clr_country_flag"):
                    flag = scalar(value, "flag") if isinstance(value, list) else value
                    facts[scope, "has_country_flag", flag] = key == "set_country_flag"
                elif key in ("add_ideas", "add_timed_idea", "remove_ideas"):
                    idea = scalar(value, "idea") if isinstance(value, list) else value
                    facts[scope, "has_idea", idea] = key != "remove_ideas"
                elif key == "send_equipment":
                    self.assertEqual(scalar(value, "target"), "ROOT")
                    amount = float(scalar(value, "amount"))
                    equipment = scalar(value, "equipment")
                    facts[scope, "equipment", equipment] -= amount
                    facts[buyer, "equipment", equipment] = facts.get((buyer, "equipment", equipment), 0) + amount
                elif key == "add_manpower":
                    facts[scope, "numeric", "has_manpower"] = facts.get((scope, "numeric", "has_manpower"), 0) + float(value)
                else:
                    self.fail(f"Unmodelled transaction effect: {key}")
        run(self.effects[name], buyer)

    def facts(self, kind, quantity=25000, price=500, buyer="CIN"):
        return {
            ("VAL", "exists", "yes"): True,
            ("VAL", "has_capitulated", "no"): True,
            (buyer, "exists", "yes"): True,
            (buyer, "has_capitulated", "no"): True,
            (buyer, "has_war", "no"): True,
            ("VAL", "has_country_flag", "VAL_partner_offer_pending"): True,
            ("VAL", "has_country_flag", "VAL_export_offer_pending"): True,
            (buyer, "has_country_flag", "VAL_partner_offer_" + kind): True,
            ("VAL", "equipment", "infantry_equipment"): quantity,
            (buyer, "variable", "ADISCORD_economy_treasury"): price,
            ("VAL", "variable", "ADISCORD_economy_treasury"): 1000,
        }

    def test_sales_conserve_cash_and_weapons_and_settle_only_once(self):
        for kind, quantity, price in (("arms", 25000, 500), ("bulk", 50000, 1000), ("arsenal", 100000, 2250), ("strategic", 200000, 5000)):
            for buyer in ("CIN", "OSF", "APH", "COF", "TFF", "YPR"):
                with self.subTest(kind=kind, buyer=buyer):
                    facts = self.facts(kind, quantity, price, buyer)
                    self.assertTrue(self.matches(f"VAL_partner_{kind}_can_accept", facts, buyer))
                    self.execute(f"VAL_settle_partner_{kind}", facts, buyer)
                    self.assertEqual(facts[buyer, "variable", "ADISCORD_economy_treasury"], 0)
                    self.assertEqual(facts["VAL", "variable", "ADISCORD_economy_treasury"], 1000 + price)
                    self.assertEqual(facts["VAL", "equipment", "infantry_equipment"], 0)
                    self.assertEqual(facts[buyer, "equipment", "infantry_equipment"], quantity)
                    self.assertEqual(facts[buyer, "variable", "ADISCORD_economy_current_month_action_costs"], price)
                    self.assertEqual(facts["VAL", "variable", "ADISCORD_economy_current_month_action_income"], price)
                    after = dict(facts)
                    self.execute(f"VAL_settle_partner_{kind}", facts, buyer)
                    self.assertEqual(facts, after)

    def test_invalid_or_fractionally_short_sales_never_pay(self):
        for kind, quantity, price in (("arms", 25000, 500), ("bulk", 50000, 1000), ("arsenal", 100000, 2250), ("strategic", 200000, 5000)):
            changes = [
                {("VAL", "equipment", "infantry_equipment"): quantity - .01},
                {("CIN", "variable", "ADISCORD_economy_treasury"): price - .01},
                {("CIN", "exists", "yes"): False},
                {("CIN", "has_capitulated", "no"): False},
                {("VAL", "has_capitulated", "no"): False},
                {("CIN", "has_war_with", "VAL"): True},
                {("CIN", "has_country_flag", "VAL_partner_offer_" + kind): False},
                {("VAL", "has_country_flag", "VAL_partner_offer_pending"): False},
                {("VAL", "has_idea", "VAL_export_income_1"): True},
                {("VAL", "variable", "STP_ps_val_receipt_contract"): 3},
            ]
            for change in changes:
                with self.subTest(kind=kind, change=change):
                    facts = {**self.facts(kind, quantity, price), **change}
                    before = dict(facts)
                    self.execute(f"VAL_settle_partner_{kind}", facts)
                    self.assertEqual(facts, before)

    def test_second_export_slot_requires_focus_and_is_consumed(self):
        facts = self.facts("bulk", 50000, 1000)
        facts["VAL", "has_idea", "VAL_export_income_1"] = True
        self.assertFalse(self.matches("VAL_partner_bulk_can_accept", facts, "CIN"))
        facts["VAL", "has_completed_focus", "VAL_Northern_Clearing_House"] = True
        self.execute("VAL_settle_partner_bulk", facts)
        self.assertTrue(facts["VAL", "has_idea", "VAL_export_income_2"])

    def test_all_order_sizes_count_as_nam_concession_aid(self):
        for kind, quantity, price in (("arms", 25000, 500), ("bulk", 50000, 1000), ("arsenal", 100000, 2250), ("strategic", 200000, 5000)):
            with self.subTest(kind=kind):
                facts = self.facts(kind, quantity, price, "NAM")
                facts["NAM", "has_war", "yes"] = True
                facts["NAM", "ADISCORD_nam_resource_war_active", "yes"] = True
                facts["NAM", "has_war_with", "EFL"] = True
                facts["VAL", "has_completed_focus", "VAL_Resource_War_Contracts"] = True
                facts["VAL", "variable", "VAL_resource_aid_side"] = 1
                facts["VAL", "variable", "VAL_resource_aid_state"] = 1
                facts["VAL", "has_active_mission", "VAL_resource_aid_deadline"] = True
                self.execute(f"VAL_settle_partner_{kind}", facts, "NAM")
                self.assertEqual(facts["VAL", "variable", "VAL_resource_aid_rifles"], quantity)
                self.assertEqual(bool(facts.get(("VAL", "has_country_flag", "VAL_nam_aid_delivered"))), quantity >= 50000)

    def test_sale_after_aid_deadline_does_not_restore_concession_credit(self):
        facts = self.facts("bulk", 50000, 1000, "NAM")
        facts.update({("NAM", "has_war", "yes"): True,
                      ("NAM", "has_war_with", "EFL"): True,
                      ("NAM", "ADISCORD_nam_resource_war_active", "yes"): True,
                      ("VAL", "has_completed_focus", "VAL_Resource_War_Contracts"): True,
                      ("VAL", "variable", "VAL_resource_aid_side"): 1,
                      ("VAL", "variable", "VAL_resource_aid_state"): -1})
        self.execute("VAL_settle_partner_bulk", facts, "NAM")
        self.assertEqual(facts["NAM", "equipment", "infantry_equipment"], 50000)
        self.assertNotIn(("VAL", "variable", "VAL_resource_aid_rifles"), facts)

    def test_partner_market_income_is_a_dynamic_modifier_not_an_idea(self):
        effects = read("common/scripted_effects/ADISCORD_VAL_effects.txt")
        dynamic = read("common/dynamic_modifiers/ADISCORD_VAL_contract_dynamic_modifier.txt")
        ideas = read("common/ideas/ADISCORD_VAL_rework_ideas.txt")
        self.assertNotIn("VAL_partner_market_access = {", ideas)
        self.assertIn("VAL_partner_market_income = {", dynamic)
        self.assertIn("ADISCORD_economy_weekly_income = VAL_partner_market_weekly_income", dynamic)
        ending = named_block(effects, "VAL_end_partner_market_income")
        self.assertIn("set_variable = { var = VAL_partner_market_weekly_income value = 0 }", ending)
        self.assertIn("has_dynamic_modifier = { modifier = VAL_partner_market_income }", ending)

    def test_recruitment_transfers_real_manpower_and_money(self):
        for buyer, men, price in ((tag, 5000, 500) for tag in ("CIN", "OSF", "APH", "COF", "TFF", "YPR")):
            for available in (men - .01, men):
                with self.subTest(buyer=buyer, available=available):
                    facts = self.facts("hire", buyer=buyer)
                    facts[buyer, "numeric", "has_manpower"] = available
                    before = dict(facts)
                    self.execute("VAL_settle_partner_hire", facts, buyer)
                    if available < men:
                        for key, value in before.items():
                            if key[1] in ("numeric", "variable"):
                                self.assertEqual(facts[key], value)
                        self.assertEqual(facts["VAL", "scheduled", "val_contract.423"], (1,))
                    else:
                        self.assertEqual(facts[buyer, "numeric", "has_manpower"], 0)
                        self.assertEqual(facts["VAL", "numeric", "has_manpower"], men)
                        self.assertEqual(facts["VAL", "variable", "ADISCORD_economy_treasury"], 1000 - price)
                        self.assertEqual(facts[buyer, "variable", "ADISCORD_economy_treasury"], 500 + price)
                        after = dict(facts)
                        self.execute("VAL_settle_partner_hire", facts, buyer)
                        self.assertEqual(facts, after)

    def test_trade_charges_once_at_exact_political_power_boundary(self):
        for buyer in ("CIN", "OSF", "APH", "COF", "TFF", "YPR"):
            facts = self.facts("trade", buyer=buyer)
            facts["VAL", "numeric", "has_political_power"] = 99.99
            before = dict(facts)
            self.execute("VAL_settle_partner_trade", facts, buyer)
            self.assertEqual(facts, before)
            facts["VAL", "numeric", "has_political_power"] = 100
            self.execute("VAL_settle_partner_trade", facts, buyer)
            self.assertEqual(facts["VAL", "numeric", "has_political_power"], 0)
            self.assertEqual(facts["VAL", "variable", "ADISCORD_economy_treasury"], 1000)
            self.assertEqual(facts[buyer, "variable", "ADISCORD_economy_treasury"], 500)
            self.assertTrue(facts["VAL", "has_country_flag", "VAL_market_contract_" + buyer + "_active"])
            self.assertEqual(facts[buyer, "variable", "VAL_partner_market_weekly_income"], 1)
            self.assertTrue(facts[buyer, "has_dynamic_modifier", "VAL_partner_market_income"])
            self.assertEqual(facts["VAL", "scheduled", "val_contract.411"], (365,))
            facts["VAL", "has_country_flag", "VAL_partner_offer_pending"] = True
            facts[buyer, "has_country_flag", "VAL_partner_offer_trade"] = True
            facts["VAL", "numeric", "has_political_power"] = 100
            after = dict(facts)
            self.execute("VAL_settle_partner_trade", facts, buyer)
            self.assertEqual(facts, after)
            self.execute("VAL_start_market_year", facts, buyer)
            self.assertEqual(facts, after, "reload must not renew the timer")

    def test_successful_annual_trade_hides_then_reopens_only_after_term_expiry(self):
        facts = self.facts("trade", buyer="CIN")
        facts["VAL", "numeric", "has_political_power"] = 100
        self.execute("VAL_settle_partner_trade", facts, "CIN")

        self.assertEqual(facts["VAL", "scheduled", "val_contract.411"], (365,))
        self.assertFalse(self.matches("VAL_trade_recipient_ready", facts, "CIN"))
        self.assertFalse(self.matches("VAL_partner_trade_can_offer", facts, "CIN"))

        # The annual flags and dynamic modifier are removed at the one-year boundary.
        facts["CIN", "has_country_flag", "VAL_market_term_started"] = False
        facts["CIN", "has_country_flag", "VAL_partner_contact_cooldown"] = False
        facts["CIN", "variable", "VAL_partner_market_weekly_income"] = 0
        facts["CIN", "has_dynamic_modifier", "VAL_partner_market_income"] = False
        facts["VAL", "has_country_flag", "VAL_market_contract_CIN_active"] = False
        facts["VAL", "numeric", "has_political_power"] = 100

        self.assertTrue(self.matches("VAL_trade_recipient_ready", facts, "CIN"))
        self.assertTrue(self.matches("VAL_partner_trade_can_offer", facts, "CIN"))

    def test_trade_decline_refunds_and_queues_one_failure_notice(self):
        facts = self.facts("trade", buyer="CIN")
        facts["CIN", "has_country_flag", "VAL_trade_fee_paid"] = True
        facts["VAL", "numeric", "has_political_power"] = 0
        self.execute("VAL_decline_partner_trade", facts, "CIN")

        self.assertEqual(facts["VAL", "numeric", "has_political_power"], 100)
        self.assertFalse(facts["CIN", "has_country_flag", "VAL_trade_fee_paid"])
        self.assertEqual(facts["VAL", "scheduled", "val_contract.425"], (1,))
        settled = dict(facts)
        self.execute("VAL_decline_partner_trade", facts, "CIN")
        self.assertEqual(facts, settled)

    def test_valid_ai_trade_receipt_settles_after_offer_marker_expires(self):
        facts = self.facts("trade", buyer="TFF")
        facts["TFF", "has_country_flag", "VAL_trade_fee_paid"] = True
        facts["TFF", "has_country_flag", "VAL_partner_offer_trade"] = False
        facts["TFF", "is_ai", "yes"] = True
        facts["VAL", "numeric", "has_political_power"] = 0

        self.assertTrue(self.matches("VAL_partner_trade_can_accept", facts, "TFF"))
        self.execute("VAL_reconcile_partner_trade_fee", facts, "TFF")

        self.assertTrue(facts["VAL", "has_country_flag", "VAL_market_contract_TFF_active"])
        self.assertFalse(facts["TFF", "has_country_flag", "VAL_trade_fee_paid"])
        self.assertEqual(facts["VAL", "numeric", "has_political_power"], 0)
        self.assertEqual(facts["VAL", "scheduled", "val_contract.411"], (365,))
        self.assertNotIn(("VAL", "scheduled", "val_contract.425"), facts)

    def test_refusal_and_expired_reply_do_not_debit_or_close_another_offer(self):
        facts = self.facts("strategic", 20000, 5000)
        self.execute("VAL_close_partner_offer", facts)
        self.assertEqual(facts["VAL", "equipment", "infantry_equipment"], 20000)
        self.assertEqual(facts["CIN", "variable", "ADISCORD_economy_treasury"], 5000)
        facts["VAL", "has_country_flag", "VAL_partner_offer_pending"] = True
        after = dict(facts)
        self.execute("VAL_close_partner_offer", facts)
        self.assertEqual(facts, after)


class TestValContractUi(unittest.TestCase):
    def test_partner_menus_fit_four_answers(self):
        from tools.validators.validate_adiscord_division_templates import parse_clausewitz
        from tools.tests.test_adiscord_stp_preparation import scalar

        events = parse_clausewitz(read("events/ADISCORD_VAL_contract_events.txt"))
        for event_id in ("val_contract.10", "val_contract.11", "val_contract.12", "val_contract.361"):
            event = next((e.value for e in events if e.key == "country_event" and scalar(e.value, "id") == event_id), None)
            self.assertIsNotNone(event, event_id)
            options = [e.value for e in event if e.key == "option"]
            self.assertLessEqual(len(options), 4, event_id)
            self.assertIn("val_contract.family.cancel", [scalar(o, "name") for o in options])

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
        self.assertNotIn("VAL_mercenary_state", history)

        english = read("localisation/english/ADISCORD_VAL_decisions_l_english.yml")
        russian = read("localisation/russian/ADISCORD_VAL_decisions_l_russian.yml")
        self.assertIn('VAL_contract_state: "$VAL_mercenary_state$"', english)
        self.assertIn('VAL_contract_state: "$VAL_mercenary_state$"', russian)
        for localisation in (english, russian):
            self.assertIn("[?VAL_contract_authority|0]/100", localisation)
            self.assertIn("[VALGetContractAuthorityBand]", localisation)

    def test_supply_crisis_is_named_in_the_visible_dynamic_spirit(self):
        for language, supply_name in (("russian", "разрыв поставок"), ("english", "Disrupted Supplies")):
            text = read(f"localisation/{language}/ADISCORD_VAL_decisions_l_{language}.yml")
            label = re.search(r'^ VAL_economic_collapse:[^\n]*', text, re.M).group()
            self.assertIn(supply_name, label)
            self.assertRegex(text, r'VAL_vorkerland_contract_disruptions_desc:[^\n]*"\$VAL_economic_collapse_desc\$"')
            self.assertIn("[?VAL_economic_recovery_steps|0]/9", text)

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
            "VAL_subcontract_quarterly_norm",
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
        triggers = read("common/scripted_triggers/ADISCORD_VAL_rework_triggers.txt")
        nationalise = named_block(decisions, "VAL_nationalise_region")
        for token in (
            "state_target = yes",
            "VAL_regional_integration_state_valid = yes",
            "set_country_flag = VAL_regional_integration_active",
            "add_core_of = ROOT",
            "fire_only_once = no",
        ):
            self.assertIn(token, nationalise)
        state_gate = named_block(triggers, "VAL_regional_integration_state_valid")
        for token in (
            "any_neighbor_state = {",
            "is_core_of = VAL",
            "is_owned_by = VAL",
            "is_controlled_by = VAL",
            "NOT = { is_core_of = VAL }",
        ):
            self.assertIn(token, state_gate)
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
                from tools.validators.validate_adiscord_division_templates import parse_clausewitz
                rewards = parse_clausewitz(reward)[0].value
                unlocked = [entry.value if isinstance(entry.value, str)
                            else next(child.value for child in entry.value if child.key == "decision")
                            for entry in rewards if entry.key == "unlock_decision_tooltip"]
                self.assertEqual(unlocked.count(decision_id), 1)
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
        self.assertIn("VAL_contract_obligations_decisions_visible = yes", alternatives)
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

    def test_quarterly_settlement_actions_follow_live_order_not_focus(self) -> None:
        decisions = named_block(read("common/decisions/ADISCORD_VAL_decisions.txt"), "VAL_contract_management")
        triggers = read("common/scripted_triggers/ADISCORD_VAL_rework_triggers.txt")
        live = named_block(triggers, "VAL_contract_obligations_decisions_visible")
        self.assertIn("has_country_flag = VAL_quarterly_contract_active", live)
        self.assertNotIn("has_completed_focus", live)

        for decision_id in (
            "VAL_quarterly_contract_deadline",
            "VAL_pay_quarterly_contract_norm",
            "VAL_subcontract_quarterly_norm",
        ):
            with self.subTest(decision=decision_id):
                visible = named_block(named_block(decisions, decision_id), "visible")
                self.assertIn("VAL_contract_obligations_decisions_visible = yes", visible)
                self.assertNotIn("has_completed_focus", visible)

        for language in ("russian", "english"):
            text = read(f"localisation/{language}/ADISCORD_VAL_decisions_l_{language}.yml")
            deadline = re.search(r'(?m)^\s*VAL_quarterly_contract_deadline_desc:0\s+"([^"\r\n]*)"', text)
            subcontract = re.search(r'(?m)^\s*VAL_subcontract_quarterly_norm_desc:0\s+"([^"\r\n]*)"', text)
            self.assertIsNotNone(deadline, language)
            self.assertIsNotNone(subcontract, language)
            if language == "russian":
                self.assertIn("Сразу после начала квартала", deadline.group(1))
                self.assertIn("сразу", subcontract.group(1).lower())
                self.assertIn("не ускоряет", deadline.group(1))
            else:
                self.assertIn("As soon as the quarter begins", deadline.group(1))
                self.assertIn("Immediately", subcontract.group(1))
                self.assertIn("does not bring the next quarter forward", deadline.group(1))

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


class TestValReclamationCompletion(unittest.TestCase):
    states = (24, 42, 48, 54, 55, 56, 57)

    def test_paid_reclamation_matches_the_actual_starting_contamination(self):
        from tools.validators.validate_adiscord_division_templates import parse_clausewitz
        from tools.tests.test_adiscord_stp_preparation import matches_conditions
        text = read("common/scripted_triggers/ADISCORD_VAL_rework_triggers.txt")
        gate = parse_clausewitz(named_block(text, "VAL_reclamation_complete"))[0].value
        self.assertEqual({e.key for e in gate if e.key.isdigit()}, {str(n) for n in self.states})
        pollution = named_block(read("common/scripted_effects/ADISCORD_vorkerland_effects.txt"),
                                "ADISCORD_vorkerland_apply_dirty_modifiers")
        initially_dirty = {int(e.key) for e in parse_clausewitz(pollution)[0].value if e.key.isdigit()} & set(self.states)
        self.assertEqual(initially_dirty, {24, 57}, "Review the paid objective when starting contamination changes")
        complete = {("VAL", "has_completed_focus", "VAL_reclamation_return_home"): True}
        for state in self.states:
            complete.update({
                (str(state), "variable", "VAL_reclamation_stage"): 3 if state in initially_dirty else 0,
                (str(state), "is_owned_by", "VAL"): True,
                (str(state), "is_controlled_by", "VAL"): True,
            })
        self.assertTrue(matches_conditions(gate, complete, "VAL"), "Clean home regions have no paid reclamation decision")
        self.assertFalse(matches_conditions(gate, {}, "VAL"), "No completion before paid reclamation")
        self.assertFalse(matches_conditions(gate, complete | {("VAL", "has_variable", "VAL_reclamation_deposit"): True}, "VAL"))
        for state in self.states:
            for stage in (0, 1, 2, 3, 4):
                expected = stage >= 3 or (stage == 0 and state not in initially_dirty)
                with self.subTest(state=state, stage=stage):
                    self.assertEqual(matches_conditions(gate, complete | {(str(state), "variable", "VAL_reclamation_stage"): stage}, "VAL"), expected)
            for key in ("is_owned_by", "is_controlled_by"):
                self.assertFalse(matches_conditions(gate, complete | {(str(state), key, "VAL"): False}, "VAL"))
            for modifier in ("ADISCORD_vorkerland_dirty_state", "VAL_reclamation_stage_1_modifier", "VAL_reclamation_stage_2_modifier"):
                self.assertFalse(matches_conditions(gate, complete | {(str(state), "has_dynamic_modifier", modifier): True}, "VAL"))
        self.assertTrue(matches_conditions(gate, complete | {("999", "variable", "VAL_reclamation_stage"): 0}, "VAL"))

    def test_spirit_removal_is_one_time_and_does_not_revoke_earned_focus_bonuses(self):
        from tools.validators.validate_adiscord_division_templates import parse_clausewitz
        effect = parse_clausewitz(named_block(read("common/scripted_effects/ADISCORD_VAL_effects.txt"), "VAL_complete_reclamation"))[0].value
        self.assertEqual(len(effect), 1)
        branch = effect[0]
        self.assertEqual(branch.key, "if")
        limit = next(e.value for e in branch.value if e.key == "limit")
        self.assertEqual({(e.key, e.value) for e in limit}, {("has_idea", "VAL_harvest_of_ash"), ("VAL_reclamation_complete", "yes")})
        body = [(e.key, e.value) for e in branch.value if e.key != "limit"]
        self.assertEqual(body, [("remove_ideas", "VAL_harvest_of_ash"), ("ADISCORD_economy_mark_dirty", "yes")])
        for completed in (False, True):
            ideas = {"VAL_harvest_of_ash"}
            invalidations = 0
            for _ in range(2):
                ready = all((e.value in ideas) if e.key == "has_idea" else completed for e in limit)
                if ready:
                    for key, value in body:
                        if key == "remove_ideas": ideas.discard(value)
                        elif key == "ADISCORD_economy_mark_dirty": invalidations += 1
            self.assertEqual("VAL_harvest_of_ash" in ideas, not completed)
            self.assertEqual(invalidations, int(completed))

    def test_reclamation_callbacks_resolve_explicit_state_receipts(self):
        effects = read("common/scripted_effects/ADISCORD_VAL_effects.txt")
        for action in ("finish", "refund"):
            callback = named_block(effects, f"VAL_reclamation_{action}_project")
            self.assertNotIn("FROM =", callback)
            self.assertIn("var = VAL_reclamation_deposit value = 500 compare = equals", callback)
            for state in (24, 42, 48, 54, 55, 56, 57):
                self.assertIn(f"{state} = {{ VAL_reclamation_{action}_state_project = yes }}", callback)

    def test_final_paid_result_checks_completion_without_save_migration(self):
        text = read("common/scripted_effects/ADISCORD_VAL_effects.txt")
        finish = named_block(text, "VAL_reclamation_finish_state_project")
        self.assertIn("VAL_complete_reclamation = yes", finish)
        self.assertLess(finish.index("add_to_variable = { var = VAL_reclamation_stage"), finish.index("VAL_complete_reclamation = yes"))
        self.assertIn("VAL = { VAL_complete_reclamation = yes", finish)
        self.assertNotIn("VAL_complete_reclamation", named_block(text, "VAL_reclamation_refund_state_project"))
        actions = read("common/on_actions/02_ADISCORD_VAL_rework_on_actions.txt")
        startup = named_block(actions, "on_startup")
        self.assertNotIn("VAL_migrate_reclamation_modifiers", startup)
        self.assertNotIn("VAL_complete_reclamation", startup)
        self.assertNotIn("VAL_complete_reclamation", named_block(actions, "on_weekly_VAL"))
        focuses = read("common/national_focus/ADISCORD_national_focus_VAL.txt")
        self.assertNotIn("remove_ideas = VAL_harvest_of_ash", focuses)
        self.assertNotIn("VAL_complete_reclamation = yes", focuses)

    def test_reclamation_goal_is_visible_in_both_languages_and_the_spirit(self):
        for language in ("russian", "english"):
            text = read(f"localisation/{language}/ADISCORD_VAL_decisions_l_{language}.yml")
            keys = dict(re.findall(r'(?m)^\s*([\w.]+):(?:\d+)?\s*"(.*)"$', text))
            for key in ("VAL_reclamation_desc", "VAL_reclamation_settlement_result_tt"):
                self.assertIn("$VAL_reclamation_completion_tt$", keys[key])
            self.assertIn("$VAL_harvest_of_ash$", keys["VAL_reclamation_completion_tt"])
            for state in self.states:
                self.assertIn(f"[{state}.GetName]", keys["VAL_reclamation_completion_tt"])
            ideas = read(f"localisation/{language}/ADISCORD_ideas_l_{language}.yml")
            desc = re.search(r'(?m)^\s*VAL_harvest_of_ash_desc:(?:\d+)?\s*"(.*)"$', ideas).group(1)
            self.assertIn("$VAL_reclamation_completion_tt$", desc)


class TestValExpansionRoute(unittest.TestCase):
    def test_north_policy_does_not_wait_for_someone_elses_civil_war(self):
        from tools.validators.validate_adiscord_division_templates import parse_clausewitz
        text = read("common/scripted_triggers/ADISCORD_VAL_rework_triggers.txt")
        gate = named_block(text, "VAL_frontier_postwar")
        self.assertNotIn("STP_cw_union_wars_finished", gate)
        self.assertNotIn("VAL_stelander_civil_war_active", gate)
        for check in ("has_capitulated = no", "is_subject = no", "NOT = { has_country_flag = VAL_stelander_defeated }"):
            self.assertIn(check, gate)
        entries = parse_clausewitz(gate)[0].value
        def matches(facts):
            return all(not facts.get(child.value, False) if e.key == "NOT" else facts.get(e.key, "no") == e.value
                       for e in entries for child in (e.value if e.key == "NOT" else [e]))
        self.assertTrue(matches({"STP_cw_union_wars_finished": False, "VAL_stelander_civil_war_active": True}))
        for blocked in ("has_capitulated", "is_subject"):
            self.assertFalse(matches({blocked: "yes"}))
        self.assertFalse(matches({"VAL_stelander_defeated": True}))
        decisions = named_block(read("common/decisions/ADISCORD_VAL_decisions.txt"), "VAL_military_operations")
        for name in ("VAL_frontier_demand_CIN", "VAL_frontier_demand_ERT", "VAL_frontier_begin_offensive"):
            self.assertIn("has_war = no", named_block(named_block(decisions, name), "available"))
        self.assertIn("STP_cw_union_wars_finished", named_block(text, "VAL_stelander_ultimatum_target"))

    def test_military_operations_owns_offensive_campaigns_and_stays_on_top(self):
        categories = read("common/decisions/categories/ADISCORD_VAL_rework_categories.txt")
        military_category = named_block(categories, "VAL_military_operations")
        self.assertIn("priority = 1000", military_category)
        decisions = read("common/decisions/ADISCORD_VAL_decisions.txt")
        military = named_block(decisions, "VAL_military_operations")
        frontier = named_block(decisions, "VAL_frontier")
        for name in (
            "VAL_frontier_demand_CIN",
            "VAL_frontier_demand_ERT",
            "VAL_frontier_begin_offensive",
            "VAL_campaign_against_nod",
            "VAL_campaign_against_stelander",
            "VAL_stelander_ultimatum",
            "VAL_nod_ultimatum",
        ):
            self.assertIn(name + " = {", military)
            self.assertNotIn(name + " = {", frontier)

    def test_expansion_is_split_into_early_war_bands_and_late_continuation(self):
        from tools.validators.validate_adiscord_division_templates import parse_clausewitz
        tree = parse_clausewitz(read("common/national_focus/ADISCORD_national_focus_VAL.txt"))[0].value
        def get(entries, key):
            return next(e.value for e in entries if e.key == key)
        focuses = {get(e.value, "id"): e.value for e in tree if e.key == "focus"}

        continuation_y = float(get(focuses["VAL_Contracts_Outlive_Kings"], "y"))
        for name in (
            "VAL_The_Harvest_Of_Ash",
            "VAL_Stelander_Crisis_Opens",
            "VAL_The_Steel_Contract",
            "VAL_frontier_conference",
            "VAL_frontier_security_plan",
        ):
            self.assertLess(float(get(focuses[name], "y")), continuation_y, name)
        for name in (
            "VAL_Bezhaysk_Operation",
            "VAL_Return_Southern_Tsaygen",
            "VAL_Wasteland_Charter",
            "VAL_Southern_Expansion",
            "VAL_Eastern_Expansion",
        ):
            self.assertGreater(float(get(focuses[name], "y")), continuation_y, name)

        harvest = focuses["VAL_The_Harvest_Of_Ash"]
        self.assertEqual(
            {entry.value for group in harvest if group.key == "prerequisite" for entry in group.value},
            {"VAL_The_Contract_State"},
        )

        frontier = focuses["VAL_frontier_conference"]
        groups = [
            {entry.value for entry in group.value}
            for group in frontier
            if group.key == "prerequisite"
        ]
        self.assertEqual(groups, [{"VAL_One_Ledger_One_Banner"}, {"VAL_Trading_Partners", "VAL_October_Of_2160"}])
        self.assertNotIn("VAL_Different_Views_On_Freedom", {item for group in groups for item in group})
        self.assertNotIn("VAL_The_Steel_Contract", {item for group in groups for item in group})

        coords = [(get(f, "x"), get(f, "y")) for f in focuses.values()]
        self.assertEqual(len(coords), len(set(coords)))
        done, active = set(), set()
        def visit(name):
            self.assertNotIn(name, active, f"Cyclic focus route at {name}")
            if name in done:
                return
            active.add(name)
            for block in focuses[name]:
                if block.key == "prerequisite":
                    for parent in block.value:
                        visit(parent.value)
            active.remove(name)
            done.add(name)
        for name in focuses:
            visit(name)


class TestValReclamationFollowThrough(unittest.TestCase):
    def test_paid_deadline_matches_the_native_decision_duration(self):
        effects = read("common/scripted_effects/ADISCORD_VAL_effects.txt")
        fallback = named_block(effects, "VAL_reclamation_reconcile_state_project")
        age = int(re.search(r"days\s*>\s*(\d+)", fallback).group(1))
        for suffix in ("roads", "water", "settlement"):
            decision = named_block(read("common/decisions/ADISCORD_VAL_decisions.txt"), "VAL_reclamation_" + suffix)
            days = int(re.search(r"days_remove\s*=\s*(\d+)", decision).group(1))
            self.assertEqual(age + 1, days)

    def test_recapturing_the_last_restored_home_region_rechecks_the_spirit(self):
        actions = read("common/on_actions/02_ADISCORD_VAL_rework_on_actions.txt")
        hook = named_block(actions, "on_state_control_changed")
        self.assertIn("ROOT = { tag = VAL has_idea = VAL_harvest_of_ash }", hook)
        self.assertIn("ROOT = { VAL_complete_reclamation = yes }", hook)
        for state in (24, 42, 48, 54, 55, 56, 57):
            self.assertIn("state = " + str(state), hook)
        self.assertNotIn("VAL_complete_reclamation", named_block(actions, "on_weekly_VAL"))

    def test_legacy_compensation_is_disabled_without_save_migration(self):
        effects = read("common/scripted_effects/ADISCORD_VAL_effects.txt")
        refresh = named_block(effects, "VAL_reclamation_refresh_state")
        self.assertIn("has_dynamic_modifier = { modifier = VAL_reclamation_recovered_land }", refresh)
        self.assertIn("remove_dynamic_modifier = { modifier = VAL_reclamation_recovered_land }", refresh)
        self.assertNotIn("add_dynamic_modifier = { modifier = VAL_reclamation_recovered_land }", effects)
        legacy = named_block(read("common/dynamic_modifiers/ADISCORD_VAL_contract_dynamic_modifier.txt"), "VAL_reclamation_recovered_land")
        self.assertIn("enable = { always = no }", legacy)
        startup = named_block(read("common/on_actions/02_ADISCORD_VAL_rework_on_actions.txt"), "on_startup")
        self.assertNotIn("VAL_reclamation_modifier_migrated_v3", startup)

    def test_balchansk_branch_has_localised_names_and_descriptions(self):
        for language in ("russian", "english"):
            text = read(f"localisation/{language}/ADISCORD_VAL_decisions_l_{language}.yml")
            for name in ("VAL_Balchansk_Charter", "VAL_Balchansk_Clearing_House"):
                for key in (name, name + "_desc"):
                    self.assertEqual(len(re.findall(rf'(?m)^\s*{key}:\d*\s+"[^"\r\n]+"\s*$', text)), 1, (language, key))

    def test_reclamation_and_route_copy_preserve_localisation_references(self):
        from collections import Counter
        catalogues = {}
        for language in ("russian", "english"):
            text = read(f"localisation/{language}/ADISCORD_VAL_decisions_l_{language}.yml")
            catalogues[language] = dict(re.findall(r'(?m)^\s*(\w+):\d*\s*"(.*)"$', text))
        for key in ("VAL_reclamation_completion_tt", "VAL_startup_guide", "VAL_reclamation_desc",
                    "VAL_reclamation_settlement_result_tt", "VAL_Balchansk_Charter_desc", "VAL_Balchansk_Clearing_House_desc"):
            tokens = {language: Counter(re.findall(r'\$[A-Za-z0-9_]+\$|\[[^\]]+\]', values[key]))
                      for language, values in catalogues.items()}
            self.assertEqual(tokens["russian"], tokens["english"], key)


class KefreytOpeningThemeTests(unittest.TestCase):
    def test_first_focus_plays_registered_theme_for_human_country(self):
        from tools.validators.validate_adiscord_division_templates import parse_clausewitz
        tree = parse_clausewitz((ROOT / "common/national_focus/ADISCORD_national_focus_VAL.txt").read_text())[0].value
        focus = next(e.value for e in tree if e.key == "focus" and any(c.key == "id" and c.value == "VAL_The_Contract_State" for c in e.value))
        reward = next(e.value for e in focus if e.key == "completion_reward")
        hidden = next(e.value for e in reward if e.key == "hidden_effect")
        guarded = [e.value for e in hidden if e.key == "if" and any(c.key == "scoped_play_song" for c in e.value)]
        self.assertEqual(len(guarded), 1, "The opening focus must start Kefreyt's theme exactly once")
        limit = next(e.value for e in guarded[0] if e.key == "limit")
        self.assertEqual([(e.key, e.value) for e in limit], [("is_ai", "no")])
        self.assertEqual([e.value for e in guarded[0] if e.key == "scoped_play_song"], ["ADISCORD_val_theme"])
        self.assertFalse(any(e.key == "play_song" for e in reward + hidden + guarded[0]))
        assets = parse_clausewitz((ROOT / "music/ADISCORD_music.asset").read_text())
        theme = [e.value for e in assets if e.key == "music" and any(c.key == "name" and c.value == "ADISCORD_val_theme" for c in e.value)]
        self.assertEqual(len(theme), 1)
        self.assertIn(("file", "ADISCORD_val_theme.ogg"), [(e.key, e.value) for e in theme[0]])
        self.assertIn('song = "ADISCORD_val_theme"', (ROOT / "music/ADISCORD_songs.txt").read_text())

if __name__ == "__main__":
    unittest.main()


class TestValProgressionChoices(unittest.TestCase):
    def focus(self, name):
        source = read("common/national_focus/ADISCORD_national_focus_VAL.txt")
        marker = re.search(r"\bid\s*=\s*" + re.escape(name) + r"\s", source)
        self.assertIsNotNone(marker, name)
        starts = list(re.finditer(r"(?m)^\s*focus\s*=\s*\{", source[:marker.start()]))
        return named_block(source[starts[-1].start():], "focus")

    def test_portrait_belongs_to_proclamation_not_unlock(self):
        focus = self.focus("VAL_Contracts_Outlive_Kings")
        self.assertNotIn("set_portraits", focus)
        effects = read("common/scripted_effects/ADISCORD_VAL_effects.txt")
        adopt = named_block(effects, "VAL_adopt_commonwealth")
        self.assertIn("VAL_can_proclaim_commonwealth = yes", adopt)
        self.assertLess(adopt.index("set_cosmetic_tag = VAL_commonwealth"),
                        adopt.index("VAL_sync_solgalov_portrait = yes"))
        sync = named_block(effects, "VAL_sync_solgalov_portrait")
        self.assertIn("has_character = VAL_Valera_Solgalov", sync)
        self.assertIn("has_cosmetic_tag = VAL_commonwealth", sync)
        self.assertIn("large = GFX_portrait_VAL_Valera_Solgalov_contracts", sync)
        self.assertIn("large = GFX_portrait_VAL_Valera_Solgalov }", sync)
        self.assertNotIn("recruit_character", sync)
        startup = named_block(read("common/on_actions/02_ADISCORD_VAL_rework_on_actions.txt"), "on_startup")
        self.assertEqual(startup.count("VAL_sync_solgalov_portrait = yes"), 1)

    def test_proclamation_has_one_map_marker_and_keeps_real_requirements(self):
        decision = named_block(read("common/decisions/ADISCORD_VAL_decisions.txt"), "VAL_proclaim_commonwealth")
        for token in ("state_target = yes", "targets = { 48 }", "on_map_mode = map_and_decisions_view", "highlight_states", "cost = 150", "VAL_can_proclaim_commonwealth = yes"):
            self.assertIn(token, decision)
        self.assertIn("has_completed_focus = VAL_Contracts_Outlive_Kings", named_block(decision, "visible"))
        self.assertNotIn("VAL_can_proclaim_commonwealth", named_block(decision, "visible"))
        trigger = named_block(read("common/scripted_triggers/ADISCORD_VAL_rework_triggers.txt"), "VAL_can_proclaim_commonwealth")
        self.assertIn("VAL_campaign_objectives_met = yes", trigger)
        self.assertNotIn("deferred", trigger)

    def test_frontier_bypass_requires_explicit_choice_and_an_idle_peace(self):
        focus = self.focus("VAL_frontier_treaty_offices")
        bypass = named_block(focus, "bypass")
        self.assertIn("VAL_northern_expansion_deferred = yes", bypass)
        triggers = read("common/scripted_triggers/ADISCORD_VAL_rework_triggers.txt")
        gate = named_block(triggers, "VAL_northern_expansion_deferred")
        for token in ("has_country_flag = VAL_frontier_expansion_deferred", "has_completed_focus = VAL_frontier_security_plan", "VAL_frontier_idle = yes", "has_war = no", "has_capitulated = no", "is_subject = no"):
            self.assertIn(token, gate)
        self.assertNotIn("is_ai", gate)
        decisions = read("common/decisions/ADISCORD_VAL_decisions.txt")
        defer = named_block(decisions, "VAL_defer_northern_expansion")
        self.assertIn("VAL_can_defer_northern_expansion = yes", named_block(defer, "available"))
        self.assertIn("ai_will_do", defer)
        reward = named_block(defer, "complete_effect")
        for forbidden in ("transfer_state", "annex_country", "add_core_of", "set_cosmetic_tag", "VAL_frontier_treaty_signed"):
            self.assertNotIn(forbidden, reward)
        self.assertIn("set_country_flag = VAL_frontier_expansion_deferred", reward)

    def test_declining_then_reopening_does_not_leave_a_stale_opt_out(self):
        decisions = read("common/decisions/ADISCORD_VAL_decisions.txt")
        withdraw = named_block(decisions, "VAL_frontier_withdraw_demand")
        self.assertIn("VAL_frontier_withdraw_and_defer = yes", withdraw)
        effects = read("common/scripted_effects/ADISCORD_VAL_effects.txt")
        withdraw_effect = named_block(effects, "VAL_frontier_withdraw_and_defer")
        self.assertIn("value = 2 compare = equals", withdraw_effect)
        self.assertIn("has_war = no", withdraw_effect)
        self.assertIn("VAL_frontier_close = yes", withdraw_effect)
        self.assertIn("set_country_flag = VAL_frontier_expansion_deferred", withdraw_effect)
        demand = named_block(decisions, "VAL_frontier_demand_CIN")
        self.assertIn("clr_country_flag = VAL_frontier_expansion_deferred", named_block(demand, "complete_effect"))
        self.assertIn("VAL_ai_frontier_force_ready", named_block(demand, "ai_will_do"))
        self.assertIn("has_country_flag = VAL_frontier_expansion_deferred", named_block(demand, "ai_will_do"))

    def test_nodrul_campaign_waits_for_a_real_northern_foothold(self):
        triggers = read("common/scripted_triggers/ADISCORD_VAL_rework_triggers.txt")
        foothold = named_block(triggers, "VAL_northern_foothold_secured")
        for group in (("58", "59", "60"), ("61", "62", "63"), ("64", "65")):
            for state in group:
                self.assertIn(f"{state} = {{", foothold)
        self.assertIn("OR =", foothold)

        northern = self.focus("VAL_Northern_Settlement")
        available = named_block(northern, "available")
        self.assertIn("VAL_northern_foothold_secured = yes", available)
        self.assertIn("VAL_nod_campaign_foothold_tt", available)

        decisions = read("common/decisions/ADISCORD_VAL_decisions.txt")
        nod = named_block(decisions, "VAL_campaign_against_nod")
        self.assertIn("VAL_stelander_dominated = yes", named_block(nod, "available"))
        self.assertIn("VAL_nod_requires_stelander_victory_tt", named_block(nod, "available"))
        self.assertIn("VAL_northern_foothold_secured = yes", named_block(nod, "available"))
        self.assertIn("NOT = { VAL_stelander_dominated = yes }", named_block(nod, "cancel_trigger"))
        self.assertIn("NOT = { VAL_northern_foothold_secured = yes }", named_block(nod, "cancel_trigger"))
        self.assertIn("VAL_stelander_dominated = yes", named_block(nod, "remove_effect"))
        self.assertIn("VAL_northern_foothold_secured = yes", named_block(nod, "remove_effect"))

        final_crisis = named_block(triggers, "VAL_final_crisis_available")
        self.assertIn("VAL_stelander_dominated = yes", final_crisis)

        stelander = self.focus("VAL_Stelander_Ultimatum")
        if "available = {" in stelander:
            self.assertNotIn("VAL_northern_foothold_secured", named_block(stelander, "available"))

        effects = read("common/scripted_effects/ADISCORD_VAL_effects.txt")
        nod_intervention = named_block(effects, "VAL_frontier_issue_nod_ultimatum")
        self.assertNotIn("VAL_northern_foothold_secured", nod_intervention)
        self.assertIn("VAL_stelander_dominated = yes", nod_intervention)

        frontier_join = named_block(effects, "VAL_frontier_join_existing_war")
        self.assertEqual(frontier_join.count("VAL = { VAL_stelander_dominated = yes }"), 3)

        guarantor_ai = named_block(triggers, "VAL_ai_frontier_guarantor_preparation")
        self.assertIn("tag = NOD", guarantor_ai)
        self.assertIn("VAL = { VAL_stelander_dominated = yes }", guarantor_ai)

    def test_ai_strongly_prefers_occidian_invasion_course(self):
        military = self.focus("VAL_Seize_The_Northern_Passes")
        trade = self.focus("VAL_Arms_For_The_Burning")
        neutral = self.focus("VAL_Keep_The_Arsenals")

        def ai_base(focus):
            ai = named_block(focus, "ai_will_do")
            match = re.search(r"\bbase\s*=\s*([0-9.]+)", ai)
            self.assertIsNotNone(match)
            return float(match.group(1))

        self.assertGreaterEqual(ai_base(military), 5 * ai_base(trade))
        self.assertGreaterEqual(ai_base(military), 10 * ai_base(neutral))

        mobilization = named_block(read("common/decisions/ADISCORD_VAL_decisions.txt"), "VAL_cw_begin_mobilization")
        ai = named_block(mobilization, "ai_will_do")
        self.assertIn("factor = 5 has_country_flag = VAL_cw_military_course", ai)
        self.assertIn("factor = 2 has_country_flag = VAL_cw_trade_course", ai)

        stelander_campaign = named_block(read("common/decisions/ADISCORD_VAL_decisions.txt"), "VAL_campaign_against_stelander")
        self.assertIn("base = 30", named_block(stelander_campaign, "ai_will_do"))

    def test_economic_route_does_not_require_bypassed_military_rewards(self):
        reopen = self.focus("VAL_Reopen_Trade_Routes")
        debts = self.focus("VAL_Settle_Industrial_Debts")
        self.assertIn("focus = VAL_Campaign_Secured focus = VAL_Returning_Buyers", reopen)
        self.assertIn("focus = VAL_New_Supply_Base focus = VAL_Contingency_Ledgers", reopen)
        self.assertIn("focus = VAL_Campaign_Secured focus = VAL_Returning_Buyers", debts)
        for name in ("VAL_Reopen_Trade_Routes", "VAL_Settle_Industrial_Debts", "VAL_Return_To_World_Market"):
            with self.subTest(name=name):
                focus = self.focus(name)
                self.assertIn("VAL_economic_settlement_ready = yes", named_block(focus, "available"))
                self.assertNotIn("bypass", focus)
        gate = named_block(read("common/scripted_triggers/ADISCORD_VAL_rework_triggers.txt"), "VAL_economic_settlement_ready")
        for token in ("VAL_campaign_objectives_met = yes", "VAL_northern_expansion_deferred = yes", "has_completed_focus = VAL_Returning_Buyers", "has_completed_focus = VAL_Contingency_Ledgers"):
            self.assertIn(token, gate)
        for name in ("VAL_Campaign_Secured", "VAL_New_Supply_Base", "VAL_Veterans_Of_The_Campaign"):
            self.assertNotIn("bypass", self.focus(name))

    def test_choice_and_economic_conditions_are_localised_in_both_languages(self):
        for language in ("russian", "english"):
            path = ROOT / f"localisation/{language}/ADISCORD_VAL_decisions_l_{language}.yml"
            self.assertTrue(path.read_bytes().startswith(b"\xef\xbb\xbf"))
            text = path.read_text(encoding="utf-8-sig")
            for key in ("VAL_defer_northern_expansion", "VAL_defer_northern_expansion_desc", "VAL_defer_northern_expansion_tt", "VAL_defer_northern_expansion_ready_tt", "VAL_economic_settlement_ready_tt", "VAL_northern_expansion_deferred_tt", "VAL_nod_campaign_foothold_tt", "VAL_nod_requires_stelander_victory_tt"):
                self.assertRegex(text, rf'(?m)^ {key}:\d* "[^\r\n]*"$')
            self.assertIn("VAL_nod_campaign_foothold_tt", text)


class TestValProgressionContinuation(unittest.TestCase):
    def refusal(self):
        source = read("events/ADISCORD_VAL_contract_events.txt")
        marker = source.index("id = val_rework.111\n")
        return named_block(source[source.rfind("country_event", 0, marker):], "country_event")

    def test_proclamation_category_is_visible_from_its_unlock(self):
        category = named_block(read("common/decisions/categories/ADISCORD_VAL_rework_categories.txt"), "VAL_postwar_administration")
        visible = named_block(category, "visible")
        for focus in ("VAL_frontier_conference", "VAL_Contracts_Outlive_Kings"):
            self.assertIn("has_completed_focus = " + focus, visible)
        self.assertIn("OR =", visible)

    def test_refusal_event_selects_the_same_safe_withdrawal_as_the_decision(self):
        event = self.refusal()
        marker = event.index("name = val_rework.111.withdraw")
        option = named_block(event[event.rfind("option", 0, marker):], "option")
        reward = named_block(option, "hidden_effect")
        self.assertIn("VAL_frontier_reply_is_current = yes", reward)
        self.assertIn("VAL_frontier_withdraw_and_defer = yes", reward)
        self.assertNotIn("VAL_frontier_close = yes", reward)
        self.assertIn("custom_effect_tooltip = VAL_frontier_withdraw_tt", option)

    def test_ai_refusal_event_uses_the_same_force_gate_as_decisions(self):
        event = self.refusal()
        marker = event.index("name = val_rework.111.war")
        option = named_block(event[event.rfind("option", 0, marker):], "option")
        chance = named_block(option, "ai_chance")
        self.assertIn("VAL_ai_frontier_force_ready = no", chance)
        self.assertNotIn("num_divisions < 24", chance)

    def test_opt_out_and_recovery_evaluate_the_real_trigger_graph(self):
        from tools.validators.validate_adiscord_division_templates import parse_clausewitz
        definitions = {e.key: e.value for e in parse_clausewitz(read("common/scripted_triggers/ADISCORD_VAL_rework_triggers.txt"))}
        flags, focuses = set(), {"VAL_frontier_security_plan"}
        facts = {"has_war": False, "is_subject": False, "has_capitulated": False,
                 "VAL_frontier_stage": 0, "VAL_campaign_objectives_met": False}

        def evaluate(entry):
            key, value = entry.key, entry.value
            if key in ("OR", "AND", "NOT"):
                result = [evaluate(e) for e in value]
                return any(result) if key == "OR" else (not all(result) if key == "NOT" else all(result))
            if key == "has_country_flag": return value in flags
            if key == "has_completed_focus": return value in focuses
            if key == "tag": return value == "VAL"
            if key in ("has_war", "is_subject", "has_capitulated", "VAL_campaign_objectives_met"):
                return facts[key] == (value == "yes")
            if key == "check_variable":
                data = {e.key: e.value for e in value}
                self.assertEqual(data["compare"], "greater_than")
                return facts.get(data["var"], 0) > float(data["value"])
            if key in definitions:
                self.assertIn(value, ("yes", "no"))
                return all(evaluate(e) for e in definitions[key]) == (value == "yes")
            self.fail("Unimplemented trigger in this fixture: " + key)

        def check(name): return all(evaluate(e) for e in definitions[name])
        self.assertTrue(check("VAL_can_defer_northern_expansion"))
        self.assertFalse(check("VAL_northern_expansion_deferred"))
        flags.add("VAL_frontier_expansion_deferred")
        self.assertFalse(check("VAL_can_defer_northern_expansion"))
        self.assertTrue(check("VAL_northern_expansion_deferred"))
        self.assertFalse(check("VAL_economic_settlement_ready"))
        focuses.add("VAL_Returning_Buyers")
        self.assertFalse(check("VAL_economic_settlement_ready"))
        focuses.add("VAL_Contingency_Ledgers")
        self.assertTrue(check("VAL_economic_settlement_ready"))
        for key in ("has_war", "is_subject", "has_capitulated"):
            with self.subTest(blocker=key):
                facts[key] = True
                self.assertFalse(check("VAL_northern_expansion_deferred"))
                self.assertFalse(check("VAL_economic_settlement_ready"))
                facts[key] = False
        for stage in (1, 2, 3):
            facts["VAL_frontier_stage"] = stage
            self.assertFalse(check("VAL_northern_expansion_deferred"))
        facts["VAL_frontier_stage"] = 0
        for flag in ("VAL_campaign_mobilizing", "VAL_stelander_defeated"):
            flags.add(flag)
            self.assertFalse(check("VAL_economic_settlement_ready"))
            flags.remove(flag)
        focuses.remove("VAL_frontier_security_plan")
        self.assertFalse(check("VAL_northern_expansion_deferred"))
        flags.clear()
        facts["VAL_campaign_objectives_met"] = True
        self.assertTrue(check("VAL_economic_settlement_ready"))


class TestValReclamationCategory(unittest.TestCase):
    def setUp(self):
        from tools.validators.validate_adiscord_division_templates import parse_clausewitz
        self.category = next(e.value for e in parse_clausewitz(read(
            "common/decisions/categories/ADISCORD_VAL_rework_categories.txt"))
            if e.key == "VAL_reclamation")
        categories = parse_clausewitz(read("common/decisions/ADISCORD_VAL_decisions.txt"))
        self.decisions = {e.key: e.value for e in next(
            c.value for c in categories if c.key == "VAL_reclamation")}
        self.triggers = {e.key: e.value for e in parse_clausewitz(read(
            "common/scripted_triggers/ADISCORD_VAL_rework_triggers.txt"))}
        self.steps = (
            ("VAL_reclamation_roads", "VAL_reclamation_survey"),
            ("VAL_reclamation_water", "VAL_reclamation_clean_water"),
            ("VAL_reclamation_settlement", "VAL_reclamation_return_home"),
            ("VAL_reclamation_industry", "VAL_reclamation_industrial_sites"),
        )

    def expand(self, items):
        from dataclasses import replace
        expanded = []
        for entry in items:
            if entry.key in self.triggers:
                self.assertIn(entry.value, ("yes", "no"))
                expanded.append(replace(entry, key="AND" if entry.value == "yes" else "NOT",
                                        value=self.expand(self.triggers[entry.key])))
            elif isinstance(entry.value, list):
                expanded.append(replace(entry, value=self.expand(entry.value)))
            else:
                expanded.append(entry)
        return expanded

    def facts(self, stage, *, survey=True, owned=True, controlled=True, dirty=True):
        facts = {
            ("VAL", "has_completed_focus", "VAL_reclamation_survey"): survey,
            ("VAL", "has_capitulated", "no"): True,
            ("FROM", "is_owned_by", "ROOT"): owned,
            ("FROM", "is_owned_by", "VAL"): owned,
            ("FROM", "is_controlled_by", "ROOT"): controlled,
            ("FROM", "is_controlled_by", "VAL"): controlled,
            ("FROM", "variable", "VAL_reclamation_stage"): stage,
        }
        modifiers = ("ADISCORD_vorkerland_dirty_state", "VAL_reclamation_stage_1_modifier",
                     "VAL_reclamation_stage_2_modifier")
        if dirty and stage < len(modifiers):
            facts[("FROM", "has_dynamic_modifier", modifiers[stage])] = True
        return facts

    def matches(self, items, facts):
        from tools.tests.test_adiscord_stp_preparation import matches_conditions
        return matches_conditions(self.expand(items), facts, "VAL")

    def decision_condition(self, decision, condition, facts):
        from tools.tests.test_adiscord_stp_preparation import block
        return self.matches(block(self.decisions[decision], condition), facts)

    def visible_rows(self, facts):
        return [name for name in self.decisions if self.decision_condition(name, "visible", facts)]

    def test_empty_reclamation_category_is_not_forced_into_the_list(self):
        from tools.tests.test_adiscord_stp_preparation import scalar
        self.assertEqual(scalar(self.category, "visible_when_empty"), "no")
        self.assertEqual(self.visible_rows(self.facts(0, dirty=False)), [])
        self.assertEqual(self.visible_rows(self.facts(4)), [])
        self.assertEqual(self.visible_rows(self.facts(0, owned=False)), [])

    def test_each_local_stage_has_one_visible_followup_after_survey(self):
        for stage, (name, _) in enumerate(self.steps):
            with self.subTest(stage=stage):
                self.assertEqual(self.visible_rows(self.facts(stage)), [name])
                self.assertEqual(self.visible_rows(self.facts(stage, survey=False)), [])

    def test_missing_followup_focus_blocks_execution_without_hiding_the_project(self):
        from tools.tests.test_adiscord_stp_preparation import block, scalar
        for stage, (name, focus) in enumerate(self.steps[1:], 1):
            with self.subTest(stage=stage):
                facts = self.facts(stage)
                self.assertTrue(self.decision_condition(name, "visible", facts))
                available = block(self.decisions[name], "available")
                self.assertEqual(scalar(available, "has_completed_focus"), focus)
                self.assertFalse(self.matches(available, facts))
                facts[("VAL", "has_completed_focus", focus)] = True
                self.assertTrue(self.matches(available, facts))

    def test_occupation_and_busy_work_keep_the_current_stage_readable(self):
        for stage, (name, focus) in enumerate(self.steps):
            with self.subTest(stage=stage):
                facts = self.facts(stage, controlled=False)
                facts[("VAL", "has_completed_focus", focus)] = True
                self.assertTrue(self.decision_condition(name, "visible", facts))
                self.assertFalse(self.decision_condition(name, "available", facts))
                facts = self.facts(stage)
                facts[("VAL", "has_completed_focus", focus)] = True
                if stage == 3:
                    facts[("FROM", "has_variable", "VAL_reclamation_industry_deposit")] = True
                else:
                    facts[("VAL", "has_variable", "VAL_reclamation_deposit")] = True
                self.assertTrue(self.decision_condition(name, "visible", facts))
                self.assertFalse(self.decision_condition(name, "available", facts))

    def test_clean_and_foreign_states_do_not_gain_fake_reclamation_projects(self):
        facts = self.facts(0, dirty=False)
        for _, focus in self.steps:
            facts[("VAL", "has_completed_focus", focus)] = True
        self.assertEqual(self.visible_rows(facts), [])
        for stage in range(4):
            with self.subTest(stage=stage):
                self.assertEqual(self.visible_rows(self.facts(stage, owned=False)), [])

    def test_projects_stay_in_their_category_with_both_map_and_list_entries(self):
        from tools.tests.test_adiscord_stp_preparation import block, scalar
        self.assertEqual(set(self.decisions), {name for name, _ in self.steps})
        for name, _ in self.steps:
            body = self.decisions[name]
            self.assertEqual(scalar(body, "on_map_mode"), "map_and_decisions_view")
            self.assertEqual(scalar(body, "cost"), "0")
            targets = block(body, "targets")
            self.assertEqual({e.value for e in targets}, {"24", "42", "48", "54", "55", "56", "57"})
            self.assertEqual(scalar(body, "days_remove"), "60" if name.endswith("industry") else "90")


class ValAnnualMarketTests(unittest.TestCase):
    def test_menu_pages_have_no_nested_options_and_at_most_four_answers(self):
        from tools.validators.validate_adiscord_division_templates import parse_clausewitz
        from tools.tests.test_adiscord_stp_preparation import scalar
        events = parse_clausewitz(read("events/ADISCORD_VAL_contract_events.txt"))
        ids = {361, 406, 407, 408, 409, 412, 413, 414, 416, 417, 418, 419}
        seen = set()
        def nested(rows):
            return any(e.key == "option" or (isinstance(e.value, list) and nested(e.value)) for e in rows)
        for e in events:
            if e.key != "country_event": continue
            eid = scalar(e.value, "id")
            if eid not in {f"val_contract.{i}" for i in ids}: continue
            seen.add(int(eid.split(".")[-1]))
            options = [o.value for o in e.value if o.key == "option"]
            self.assertLessEqual(len(options), 4, eid)
            self.assertFalse(any(nested(o) for o in options), eid)
            self.assertIn("val_contract.family.cancel", [scalar(o, "name") for o in options])
        self.assertEqual(seen, ids)

    def test_market_charges_political_power_and_schedules_one_year(self):
        effects = read("common/scripted_effects/ADISCORD_VAL_effects.txt")
        settle = named_block(effects, "VAL_settle_partner_trade")
        self.assertIn("add_political_power = -100", settle)
        self.assertNotIn("ADISCORD_economy_treasury", settle)
        term = named_block(effects, "VAL_start_market_year")
        self.assertEqual(term.count("days = 365"), 2)
        self.assertIn("NOT = { has_country_flag = VAL_market_term_started }", term)
        self.assertNotIn("add_timed_idea", term)
        trigger = named_block(read("common/scripted_triggers/ADISCORD_VAL_rework_triggers.txt"), "VAL_partner_trade_terms_valid")
        self.assertIn("NOT = { has_political_power < 100 }", trigger)
        self.assertIn("NOT = { has_country_flag = VAL_market_term_started }", trigger)

    def test_cannibal_income_is_lowest_and_cache_invalidated(self):
        ideas = read("common/ideas/ADISCORD_VAL_rework_ideas.txt")
        dynamic = read("common/dynamic_modifiers/ADISCORD_VAL_contract_dynamic_modifier.txt")
        contract_state = named_block(dynamic, "VAL_contract_state")
        self.assertIn("ADISCORD_economy_weekly_income = VAL_contract_market_weekly_income", contract_state)
        incomes = {"CIN": 5, "OSF": 8, "APH": 2, "COF": 10, "TFF": 12, "YPR": 15}
        for tag, amount in incomes.items():
            self.assertNotIn("VAL_market_" + tag + " = {", ideas)
        self.assertEqual(incomes["APH"], 2)
        self.assertTrue(all(incomes["APH"] < v <= 15 for k,v in incomes.items() if k != "APH"))
        effects = read("common/scripted_effects/ADISCORD_VAL_effects.txt")
        income_total = named_block(effects, "VAL_recalculate_market_contract_income")
        for tag, amount in incomes.items():
            self.assertIn(f"has_country_flag = VAL_market_contract_{tag}_active", income_total)
            self.assertRegex(income_total, rf"add_to_variable = \{{ var = VAL_contract_market_weekly_income value = {amount} \}}")
        self.assertIn("ADISCORD_economy_mark_dirty = yes", named_block(effects, "VAL_refresh_market_contract_modifier"))
        category_ru = read("localisation/russian/ADISCORD_VAL_decisions_l_russian.yml")
        category_desc = re.search(r"(?m)^\s*VAL_foreign_sales_desc:0 \"(.*)\"$", category_ru)[1]
        self.assertIn("§G+[?VAL_contract_market_weekly_income|0]§!", category_desc)
        spirit_desc = re.search(r"(?m)^\s*VAL_contract_state_desc: \"(.*)\"$", category_ru)[1]
        self.assertNotIn("VAL_contract_market_weekly_income", spirit_desc)

    def test_market_income_rebuild_uses_flags_and_the_yearly_event(self):
        effects = read("common/scripted_effects/ADISCORD_VAL_effects.txt")
        initializer = named_block(effects, "VAL_recalculate_market_contract_income")
        for tag in ("CIN", "OSF", "APH", "COF", "TFF", "YPR"):
            self.assertIn(f"has_country_flag = VAL_market_contract_{tag}_active", initializer)
        self.assertIn("set_variable = { var = VAL_contract_market_weekly_income value = 0 }", initializer)
        self.assertIn("clamp_variable = { var = VAL_contract_market_weekly_income min = 0 max = 52 }", initializer)
        self.assertIn("VAL_refresh_market_contract_modifier = yes", initializer)
        startup = named_block(read("common/on_actions/02_ADISCORD_VAL_rework_on_actions.txt"), "on_startup")
        self.assertIn("VAL_recalculate_market_contract_income = yes", startup)
        self.assertNotIn("VAL_migrate_market_years", startup)
        start_year = named_block(effects, "VAL_start_market_year")
        self.assertEqual(start_year.count("days = 365"), 2)
        self.assertIn("set_country_flag = VAL_market_contract_CIN_active", start_year)
        self.assertIn("VAL_refresh_partner_market_modifier = yes", start_year)
        contract_events = read("events/ADISCORD_VAL_contract_events.txt")
        expiry_start = contract_events.index("id = val_contract.411")
        expiry = contract_events[contract_events.rfind("country_event = {", 0, expiry_start):]
        self.assertIn("VAL_recalculate_market_contract_income = yes", expiry)
        self.assertIn("clr_country_flag = VAL_market_contract_YPR_active", expiry)
        self.assertIn("VAL_end_partner_market_income = yes", expiry)

    def test_market_contract_flags_survive_load_and_end_through_scripted_lifecycle(self):
        ideas = named_block(named_block(read("common/ideas/ADISCORD_VAL_rework_ideas.txt"), "ideas"), "country")
        effects = read("common/scripted_effects/ADISCORD_VAL_effects.txt")
        lifecycle = named_block(effects, "VAL_reconcile_market_contract_lifecycle")
        for tag in ("CIN", "OSF", "APH", "COF", "TFF", "YPR"):
            self.assertNotIn("VAL_market_" + tag, str(ideas))
            self.assertIn("has_country_flag = VAL_market_contract_" + tag + "_active", lifecycle)
            self.assertIn("has_war_with = " + tag, lifecycle)
            self.assertIn("clr_country_flag = VAL_market_contract_" + tag + "_active", lifecycle)

        on_actions = read("common/on_actions/02_ADISCORD_VAL_rework_on_actions.txt")
        startup_hook = named_block(named_block(on_actions, "on_startup"), "effect")
        war_hook = named_block(named_block(on_actions, "on_war_relation_added"), "effect")
        monthly_hook = named_block(named_block(on_actions, "on_monthly_VAL"), "effect")
        self.assertNotIn("VAL_reconcile_market_contract_lifecycle = yes", startup_hook)
        self.assertIn("VAL_reconcile_market_contract_lifecycle = yes", war_hook)
        self.assertIn("VAL_reconcile_market_contract_lifecycle = yes", monthly_hook)


    def test_signed_partner_row_is_hidden_and_expiry_cleans_before_choice(self):
        decision = named_block(read("common/decisions/ADISCORD_VAL_decisions.txt"), "VAL_sign_annual_trade")
        visible = named_block(decision, "visible")
        self.assertIn("VAL_trade_recipient_ready = yes", visible)
        target_trigger = named_block(decision, "target_trigger")
        self.assertIn("NOT = { has_country_flag = VAL_market_term_started }", target_trigger)
        self.assertIn("NOT = { has_country_flag = VAL_partner_contact_cooldown }", target_trigger)
        self.assertNotIn("VAL_partner_trade_can_offer", target_trigger)
        for tag in ("CIN", "OSF", "APH", "COF", "TFF", "YPR"):
            active_flag = "NOT = { has_country_flag = VAL_market_contract_" + tag + "_active }"
            target_clause = "FROM = { tag = " + tag + " } " + active_flag
            self.assertIn(target_clause, target_trigger)
            self.assertIn(target_clause, visible)
        recipient = named_block(read("common/scripted_triggers/ADISCORD_VAL_rework_triggers.txt"), "VAL_trade_recipient_ready")
        self.assertIn("NOT = { has_country_flag = VAL_market_term_started }", recipient)
        source = read("events/ADISCORD_VAL_contract_events.txt")
        start = re.search(r"country_event = \{\s*id = val_contract\.411\b", source).start()
        expiry = named_block(source[start:], "country_event")
        immediate = named_block(expiry, "immediate")
        self.assertIn("clr_country_flag = VAL_market_term_started", immediate)
        self.assertIn("VAL_end_partner_market_income = yes", immediate)
        self.assertIn("remove_dynamic_modifier = { modifier = VAL_partner_market_income }", read("common/scripted_effects/ADISCORD_VAL_effects.txt"))
        for tag in ("CIN", "OSF", "APH", "COF", "TFF", "YPR"):
            self.assertIn("clr_country_flag = VAL_market_contract_" + tag + "_active", immediate)
        self.assertNotIn("add_political_power", expiry)


class ValQuarterlySupplyTests(unittest.TestCase):
    def test_quarterly_cycle_preserves_legacy_orders_and_blocks_duplicate_delivery(self):
        effects = read("common/scripted_effects/ADISCORD_VAL_effects.txt")
        triggers = read("common/scripted_triggers/ADISCORD_VAL_rework_triggers.txt")
        for slot in (1, 2):
            self.assertIn(f"VAL_order_{slot}_legacy_dispatch", effects)
            body = named_block(effects, f"VAL_accept_quarterly_order_{slot}")
            self.assertIn("add_political_power = -100", body)
            self.assertNotIn("subtract_from_variable", body)
            self.assertIn(f"var = VAL_order_{slot}_completed value = 0", body)
            gate = named_block(triggers, f"VAL_order_{slot}_can_dispatch")
            self.assertIn(f"NOT = {{ has_country_flag = VAL_order_{slot}_quarter_paid }}", gate)
            cycle = named_block(effects, f"VAL_order_{slot}_quarterly_reconcile")
            self.assertIn("value = 4 compare = greater_than_or_equals", cycle)
            self.assertIn("days = -15", cycle)
            self.assertIn(f"VAL_order_{slot}_legacy_cancel", effects)

    def test_regular_export_does_not_require_war(self):
        gate = named_block(read("common/scripted_triggers/ADISCORD_VAL_rework_triggers.txt"), "VAL_export_customer")
        self.assertNotIn("has_war = yes", gate)


    def test_authored_quarter_cycle_no_duplicate_cash_and_one_grace(self):
        from tools.validators.validate_adiscord_division_templates import parse_clausewitz
        from tools.tests.test_adiscord_stp_preparation import scalar, block
        effects = {e.key: e.value for e in parse_clausewitz(read("common/scripted_effects/ADISCORD_VAL_effects.txt"))}
        for slot in (1, 2):
            prefix = f"VAL_order_{slot}"
            flags = {prefix+"_quarterly"}
            values = {prefix+"_state": 1, prefix+"_completed": 0, prefix+"_remaining": 500, prefix+"_quantity": 25000}
            cash = {"VAL": 0, "buyer": 2000}
            equipment = {"VAL": 100000, "buyer": 0}
            events = []
            timer = [90]
            def number(value):
                key = value.removeprefix("VAL.")
                return values[key] if key in values else float(value)
            def matches(rows):
                result = []
                for e in rows:
                    if e.key == "OR": answer = any(matches([x]) for x in e.value)
                    elif e.key == "NOT": answer = not matches(e.value)
                    elif e.key == "AND": answer = matches(e.value)
                    elif e.key == "has_country_flag": answer = e.value in flags
                    elif e.key == "has_capitulated": answer = False
                    elif e.key.startswith("event_target:"): answer = True
                    elif e.key == prefix+"_can_dispatch": answer = prefix+"_quarter_paid" not in flags and prefix+"_expired" not in flags and cash["buyer"] >= 500 and equipment["VAL"] >= 25000
                    elif e.key == "check_variable":
                        a=values.get(scalar(e.value,"var"),0);b=number(scalar(e.value,"value"));op=scalar(e.value,"compare")
                        answer={"equals":a==b,"greater_than_or_equals":a>=b}[op]
                    else: self.fail("Unmodelled condition: "+e.key)
                    result.append(answer)
                return all(result)
            def run(rows, scope="VAL"):
                taken=False
                for e in rows:
                    key,val=e.key,e.value
                    if key in ("if","else_if","else"):
                        if key=="if": taken=False
                        if not taken and (key=="else" or matches(block(val,"limit"))):
                            taken=True;run([x for x in val if x.key!="limit"],scope)
                    elif key.startswith("event_target:"): run(val,"buyer")
                    elif key in ("set_country_flag","clr_country_flag"):
                        if key=="set_country_flag": flags.add(val)
                        else: flags.discard(val)
                    elif key in ("set_variable","add_to_variable","subtract_from_variable"):
                        var=scalar(val,"var");delta=number(scalar(val,"value"))
                        if var=="ADISCORD_economy_treasury": cash[scope]+=delta*(1 if key=="add_to_variable" else -1)
                        elif var.startswith("ADISCORD_economy_current_month"): pass
                        else: values[var]=delta if key=="set_variable" else values.get(var,0)+delta
                    elif key=="send_equipment":
                        qty=number(scalar(val,"amount"));equipment["VAL"]-=qty;equipment["buyer"]+=qty
                    elif key=="activate_mission": timer[0]=30
                    elif key=="add_days_mission_timeout": timer[0]+=number(scalar(val,"days"))
                    elif key=="country_event": events.append(scalar(val,"id"))
                    elif key in ("VAL_refresh_order_summary","ADISCORD_economy_initialize_country","ADISCORD_economy_mark_dirty","VAL_contract_record_success","save_event_target_as","remove_mission"): pass
                    elif key in effects: run(effects[key],scope)
                    else: self.fail("Unmodelled effect: "+key)
            for quarter in range(4):
                run(effects[prefix+"_dispatch"])
                self.assertEqual(values[prefix+"_completed"],quarter+1)
                snapshot=(dict(cash),dict(equipment))
                run(effects[prefix+"_dispatch"])
                self.assertEqual((cash,equipment),snapshot)
                flags.add(prefix+"_expired")
                run(effects[prefix+"_quarterly_reconcile"])
                if quarter<3: self.assertEqual(timer[0],95 if quarter==2 else 90)
            self.assertEqual(cash,{"VAL":2000,"buyer":0})
            self.assertEqual(equipment,{"VAL":0,"buyer":100000})
            self.assertEqual(events,["val_contract.420"])
            self.assertEqual(values[prefix+"_state"],0)
            # A missed quarter grants exactly 15 days, then cancellation frees the slot.
            values.update({prefix+"_state":1,prefix+"_completed":0,prefix+"_advance":0})
            flags.update({prefix+"_quarterly",prefix+"_expired"})
            run(effects[prefix+"_quarterly_reconcile"])
            self.assertEqual(timer[0],15)
            self.assertIn(prefix+"_grace_used",flags)
            flags.add(prefix+"_expired")
            run(effects[prefix+"_quarterly_reconcile"])
            self.assertEqual(values[prefix+"_state"],0)
            self.assertEqual(events[-1],"val_contract.421")
            self.assertEqual(cash,{"VAL":2000,"buyer":0})

    def test_quarterly_orders_auto_dispatch_and_use_literal_cash_tariffs(self):
        effects = read("common/scripted_effects/ADISCORD_VAL_effects.txt")
        reconcile = named_block(effects, "VAL_contract_reconcile")
        self.assertIn("VAL_order_1_can_dispatch = yes", reconcile)
        self.assertIn("VAL_order_1_dispatch = yes", reconcile)
        self.assertIn("VAL_order_2_can_dispatch = yes", reconcile)
        self.assertIn("VAL_order_2_dispatch = yes", reconcile)
        for slot in (1, 2):
            helper = named_block(effects, f"VAL_order_{slot}_settle_payment")
            for amount in ("375", "500", "750", "1000", "1687.5", "2250", "3750", "5000"):
                self.assertIn(f"ADISCORD_economy_treasury value = {amount}", helper)
            dispatch = named_block(effects, f"VAL_order_{slot}_dispatch")
            legacy = named_block(effects, f"VAL_order_{slot}_legacy_dispatch")
            self.assertIn(f"VAL_order_{slot}_settle_payment = yes", dispatch)
            self.assertIn(f"VAL_order_{slot}_settle_payment = yes", legacy)
            self.assertNotIn(f"VAL.VAL_order_{slot}_remaining", dispatch)
            self.assertNotIn(f"VAL.VAL_order_{slot}_remaining", legacy)


class ValPartnerVisibilityTests(unittest.TestCase):
    def test_country_visibility_uses_capabilities_not_affordability(self):
        from tools.tests.test_validate_adiscord_val_rework import ValExpandedCampaignTests
        from tools.validators.validate_adiscord_division_templates import parse_clausewitz
        self.triggers={e.key:e.value for e in parse_clausewitz(read("common/scripted_triggers/ADISCORD_VAL_rework_triggers.txt"))}
        self.assertIn("VAL_partner_has_visible_contracts",self.triggers.keys())
        facts={("STP","exists","yes"):True,("STP","has_capitulated","no"):True}
        self.assertFalse(ValExpandedCampaignTests.match(self,"VAL_partner_has_visible_contracts",facts,"STP"))
        facts["VAL","has_completed_focus","VAL_Foreign_Broker_Licences"]=True
        self.assertTrue(ValExpandedCampaignTests.match(self,"VAL_partner_has_visible_contracts",facts,"STP"))
        self.assertFalse(ValExpandedCampaignTests.match(self,"VAL_partner_commerce_visible",facts,"STP"))
        facts["VAL","has_country_flag","VAL_partner_offer_pending"]=True
        facts["VAL","variable","VAL_order_1_state"]=1
        self.assertTrue(ValExpandedCampaignTests.match(self,"VAL_partner_has_visible_contracts",facts,"STP"))


    def test_abstract_arms_market_is_not_partner_targeted(self):
        decision=named_block(read("common/decisions/ADISCORD_VAL_decisions.txt"),"VAL_sell_surplus_arms_market")
        self.assertNotIn("targets =",decision)
        self.assertNotIn("target_trigger",decision)
        self.assertIn("any_country = { VAL_abstract_arms_buyer = yes }",named_block(decision,"available"))
    def test_unaffordable_options_recheck_before_effects_and_do_not_loop_ai(self):
        from tools.validators.validate_adiscord_division_templates import parse_clausewitz
        from tools.tests.test_adiscord_stp_preparation import scalar, block
        events=parse_clausewitz(read("events/ADISCORD_VAL_contract_events.txt"))
        checked=0
        for e in events:
            if e.key!="country_event":continue
            for option in [x.value for x in e.value if x.key=="option"]:
                statuses=[x.value for x in option if x.key=="custom_effect_tooltip" and isinstance(x.value,str) and x.value.startswith("VAL_offer_status_")]
                if not statuses:continue
                checked+=1
                payload=block(option,"hidden_effect")
                self.assertEqual([x.key for x in payload],["if","else"])
                self.assertTrue(block(block(payload,"if"),"limit"))
                self.assertEqual(scalar(block(block(payload,"else"),"country_event"),"id"),scalar(e.value,"id"))
                modifier=block(block(option,"ai_chance"),"modifier")
                self.assertEqual(scalar(modifier,"factor"),"0")
                self.assertTrue(block(modifier,"NOT"))
        self.assertGreaterEqual(checked,18)


class ValOfferButtonStateTests(unittest.TestCase):
    def test_trade_fee_is_on_decision_not_event_button(self):
        self.assertNotIn("name = VAL_partner_trade_button", read("events/ADISCORD_VAL_contract_events.txt"))
        self.assertIn("cost = 100", named_block(read("common/decisions/ADISCORD_VAL_decisions.txt"), "VAL_sign_annual_trade"))

    def test_every_guarded_offer_has_a_dynamic_button_name(self):
        from tools.validators.validate_adiscord_division_templates import parse_clausewitz
        from tools.tests.test_adiscord_stp_preparation import scalar
        events=parse_clausewitz(read("events/ADISCORD_VAL_contract_events.txt"))
        count=0
        for e in events:
            if e.key!="country_event":continue
            for option in [o.value for o in e.value if o.key=="option"]:
                if any(o.key=="custom_effect_tooltip" and isinstance(o.value,str) and o.value.startswith("VAL_offer_status_") for o in option):
                    self.assertTrue(scalar(option,"name").endswith("_button"))
                    count+=1
        self.assertGreaterEqual(count,18)


class ValNativeTradeFeeTests(unittest.TestCase):
    def test_decision_has_native_cost_and_receipt_before_offer(self):
        decision=named_block(read("common/decisions/ADISCORD_VAL_decisions.txt"),"VAL_sign_annual_trade")
        self.assertIn("cost = 100",decision)
        self.assertNotIn("custom_cost_text",decision)
        self.assertIn("set_country_flag = VAL_trade_fee_paid",decision)
        self.assertIn("VAL_dispatch_partner_trade_offer = yes",decision)
        self.assertNotIn("add_political_power = -100",decision)
        self.assertNotIn("save_event_target_as = VAL_trade_recipient", decision)
        self.assertNotIn("event_target:VAL_trade_recipient", decision)

    def test_ai_trade_is_automatic_and_human_partner_gets_the_reply_event(self):
        effects=read("common/scripted_effects/ADISCORD_VAL_effects.txt")
        dispatch=named_block(effects,"VAL_dispatch_partner_trade_offer")
        self.assertIn("limit = { VAL_partner_trade_can_accept = no }",dispatch)
        self.assertLess(dispatch.index("VAL_partner_trade_can_accept = no"),dispatch.index("country_event = { id = val_contract.362 }"))
        self.assertIn("limit = { is_ai = yes }",dispatch)
        self.assertIn("VAL_resolve_partner_trade_reply = yes",dispatch)
        self.assertIn("country_event = { id = val_contract.362 }",dispatch)
        events=read("events/ADISCORD_VAL_contract_events.txt")
        self.assertEqual(events.count("VAL_dispatch_partner_trade_offer = yes"),3)
        self.assertNotIn("country_event = { id = val_contract.362 }",events)

    def test_prepaid_trade_does_not_charge_twice_and_refund_is_guarded(self):
        effects=read("common/scripted_effects/ADISCORD_VAL_effects.txt")
        settle=named_block(effects,"VAL_settle_partner_trade")
        self.assertIn("has_country_flag = VAL_trade_fee_paid",settle)
        refund=named_block(effects,"VAL_refund_trade_fee")
        self.assertIn("limit = { has_country_flag = VAL_trade_fee_paid }",refund)
        self.assertIn("add_political_power = 100",refund)
        self.assertIn("clr_country_flag = VAL_trade_fee_paid",refund)


    def test_periodic_reconciliation_only_refunds_stale_receipts(self):
        effects=read("common/scripted_effects/ADISCORD_VAL_effects.txt")
        reconcile=named_block(effects,"VAL_reconcile_trade_fees")
        self.assertEqual(reconcile.count("VAL_reconcile_partner_trade_fee = yes"),6)
        self.assertNotIn("VAL_reconcile_stale_trade_fee = yes",reconcile)
        self.assertNotIn("has_country_flag = VAL_trade_fee_paid",reconcile)
        stale=named_block(effects,"VAL_reconcile_stale_trade_fee")
        self.assertIn("VAL_refund_trade_fee = yes",stale)

    def test_prepaid_acceptance_and_refusal_settle_only_once(self):
        model=ValPartnerSettlementTests()
        model.setUpClass()
        for outcome in ("accept","decline","expired"):
            facts=model.facts("trade",buyer="CIN")
            facts["VAL","numeric","has_political_power"]=0
            facts["CIN","has_country_flag","VAL_trade_fee_paid"]=True
            if outcome=="accept":
                model.execute("VAL_settle_partner_trade",facts,"CIN")
                self.assertTrue(facts["VAL","has_country_flag","VAL_market_contract_CIN_active"])
            else:
                if outcome=="expired": facts["CIN","has_country_flag","VAL_partner_offer_trade"]=False
                model.execute("VAL_close_partner_offer",facts,"CIN")
            self.assertEqual(facts["VAL","numeric","has_political_power"],0 if outcome=="accept" else 100)
            self.assertFalse(facts["CIN","has_country_flag","VAL_trade_fee_paid"])
            self.assertTrue(facts["CIN","has_country_flag","VAL_partner_contact_cooldown"])
            reply = "val_contract.424" if outcome == "accept" else "val_contract.425"
            self.assertEqual(facts["VAL","scheduled",reply], (1,))
            after=dict(facts)
            model.execute("VAL_refund_trade_fee",facts,"CIN")
            self.assertEqual(facts,after)


class ValDirectContractDecisionTests(unittest.TestCase):

    def test_hire_and_abstract_arms_market_have_direct_entry_points(self):
        source=read("common/decisions/ADISCORD_VAL_decisions.txt")
        hire=named_block(source,"VAL_hire_partner_volunteers")
        self.assertIn("VAL_partner_hire_can_offer = yes",hire)
        self.assertIn("VAL_dispatch_partner_hire_offer = yes",hire)
        self.assertNotIn("subtract_from_variable",hire)

        market=named_block(source,"VAL_sell_surplus_arms_market")
        self.assertIn("has_completed_focus = VAL_Foreign_Broker_Licences",named_block(market,"visible"))
        available=named_block(market,"available")
        self.assertIn("VAL_export_slot_free = yes",available)
        self.assertIn("infantry_equipment < 25000",available)
        self.assertIn("any_country = { VAL_abstract_arms_buyer = yes }",available)

        complete=named_block(market,"complete_effect")
        for rifles,price in ((25000,500),(50000,1000),(100000,2250),(200000,5000)):
            self.assertIn(f"amount = {rifles}",complete)
            self.assertIn(f"value = {price}",complete)
        self.assertIn("VAL_record_instant_export = yes",complete)
        self.assertIn("VAL_contract_record_success = yes",complete)
    def test_ai_hire_settles_in_the_offer_scope_without_a_delayed_dispatch(self):
        effects = read("common/scripted_effects/ADISCORD_VAL_effects.txt")
        dispatch = named_block(effects, "VAL_dispatch_partner_hire_offer")
        self.assertIn("limit = { is_ai = yes }", dispatch)
        self.assertIn("VAL_settle_partner_hire = yes", dispatch)
        self.assertNotIn("days = 1", dispatch)
        self.assertIn("country_event = { id = val_contract.364 }", dispatch)
        self.assertNotIn("id = val_contract.426", read("events/ADISCORD_VAL_contract_events.txt"))


    def test_legacy_special_agreement_is_hidden_but_kept_for_save_compatibility(self):
        source=read("common/decisions/ADISCORD_VAL_decisions.txt")
        special=named_block(source,"VAL_partner_contract")
        self.assertEqual(named_block(special,"visible").strip(),"visible = { always = no }")
        self.assertIn("id = val_contract.414",special)
        self.assertNotIn("id = val_contract.361",special)
class ValReplacementReserveTests(unittest.TestCase):
    def test_recruitment_brake_releases_at_exact_reserve_boundary(self):
        from tools.tests.test_adiscord_stp_preparation import block, matches_conditions, parse_clausewitz
        policy = block(parse_clausewitz(read("common/ai_strategy/VAL.txt")), "VAL_preserve_replacement_reserve")
        for people, ai, capitulated, expected in ((0, True, False, True), (14999.9, True, False, True),
                                                  (15000, True, False, False), (30000, True, False, False),
                                                  (0, False, False, False), (0, True, True, False)):
            facts = {("VAL", "numeric", "has_manpower"): people,
                     ("VAL", "is_ai", "yes"): ai, ("VAL", "has_capitulated", "no"): not capitulated}
            self.assertEqual(matches_conditions(block(policy, "enable"), facts, "VAL"), expected)

    def test_paid_recruitment_priority_stops_at_sufficient_reserve(self):
        from tools.tests.test_adiscord_stp_preparation import block, matches_conditions, parse_clausewitz, scalar
        for path, decision_id in (("common/decisions/ADISCORD_VAL_decisions.txt", "VAL_hire_partner_volunteers"),
                                  ("common/decisions/ADISCORD_VAL_logistics_market_decisions.txt", "VAL_recruit_local_volunteers")):
            decision = parse_clausewitz(named_block(read(path), decision_id))[0].value
            policy = block(decision, "ai_will_do")
            weights = []
            for people in (0, 15000, 30000):
                weight = float(scalar(policy, "base"))
                for modifier in (e.value for e in policy if e.key == "modifier"):
                    conditions = [e for e in modifier if e.key != "factor"]
                    if matches_conditions(conditions, {("VAL", "numeric", "has_manpower"): people}, "VAL"):
                        weight *= float(scalar(modifier, "factor"))
                weights.append(weight)
            self.assertGreater(weights[0], weights[1])
            self.assertGreater(weights[1], 0)
            self.assertEqual(weights[2], 0)


class ValHireReceiptTests(unittest.TestCase):
    setUpClass = classmethod(ValPartnerSettlementTests.setUpClass.__func__)
    matches = ValPartnerSettlementTests.matches
    execute = ValPartnerSettlementTests.execute
    facts = ValPartnerSettlementTests.facts

    def test_reserved_hire_fee_is_settled_once_and_reply_is_sent(self):
        for buyer, people, price in ((tag, 5000, 500) for tag in ("CIN", "OSF", "APH", "COF", "TFF", "YPR")):
            with self.subTest(buyer=buyer):
                facts = self.facts("hire", buyer=buyer)
                facts[buyer,"numeric","has_manpower"] = people
                facts["VAL","variable","ADISCORD_economy_treasury"] = price
                before = facts[buyer,"variable","ADISCORD_economy_treasury"]
                self.execute("VAL_reserve_partner_hire_fee", facts, buyer)
                self.assertEqual(facts["VAL","variable","ADISCORD_economy_treasury"], 0)
                self.assertTrue(self.matches("VAL_partner_hire_can_accept", facts, buyer))
                self.execute("VAL_settle_partner_hire", facts, buyer)
                self.assertEqual(facts["VAL","numeric","has_manpower"], people)
                self.assertEqual(facts[buyer,"variable","ADISCORD_economy_treasury"], before + price)
                self.assertEqual(facts["VAL","variable","ADISCORD_economy_treasury"], 0)
                self.assertEqual(facts["VAL","scheduled","val_contract.422"], (1,))
                after = dict(facts)
                self.execute("VAL_settle_partner_hire", facts, buyer)
                self.execute("VAL_decline_partner_hire", facts, buyer)
                self.assertEqual(after, facts)

    def test_refusal_expiry_and_failed_settlement_refund_once(self):
        for reason in ("refusal", "expired", "short_reserve"):
            facts = self.facts("hire", buyer="CIN")
            facts["CIN","numeric","has_manpower"] = 5000
            self.execute("VAL_reserve_partner_hire_fee", facts)
            if reason == "expired":
                facts["CIN","has_country_flag","VAL_partner_offer_hire"] = False
            if reason == "short_reserve":
                facts["CIN","numeric","has_manpower"] = 4999.9
                self.execute("VAL_settle_partner_hire", facts)
            else:
                self.execute("VAL_decline_partner_hire", facts)
            self.assertEqual(facts["VAL","variable","ADISCORD_economy_treasury"], 1000)
            self.assertEqual(facts["VAL","scheduled","val_contract.423"], (1,))
            self.assertFalse(facts["VAL","has_country_flag","VAL_partner_offer_pending"])
            self.assertFalse(facts["CIN","has_country_flag","VAL_hire_fee_500_paid"])
            after = dict(facts)
            self.execute("VAL_decline_partner_hire", facts)
            self.assertEqual(after, facts)

    def test_player_consent_settles_valid_reserved_quote_after_offer_marker_expires(self):
        facts = self.facts("hire", buyer="TFF")
        facts["TFF","numeric","has_manpower"] = 5000
        self.execute("VAL_reserve_partner_hire_fee", facts, "TFF")
        facts["TFF","has_country_flag","VAL_partner_offer_hire"] = False
        self.assertTrue(self.matches("VAL_partner_hire_can_accept", facts, "TFF"))
        self.execute("VAL_settle_partner_hire", facts, "TFF")
        self.assertEqual(facts["TFF","numeric","has_manpower"], 0)
        self.assertEqual(facts["VAL","numeric","has_manpower"], 5000)
        self.assertEqual(facts["TFF","variable","ADISCORD_economy_treasury"], 1000)
        self.assertFalse(facts["TFF","has_country_flag","VAL_hire_fee_500_paid"])
        self.assertNotIn(("TFF","scheduled","val_contract.423"), facts)

    def test_reconciliation_auto_accepts_valid_ai_quote_when_offer_marker_expires(self):
        facts = self.facts("hire", buyer="YPR")
        facts["YPR","numeric","has_manpower"] = 5000
        facts["YPR","is_ai","yes"] = True
        self.execute("VAL_reserve_partner_hire_fee", facts, "YPR")
        facts["YPR","has_country_flag","VAL_partner_offer_hire"] = False
        self.execute("VAL_reconcile_partner_hire_fee", facts, "YPR")
        self.assertEqual(facts["YPR","numeric","has_manpower"], 0)
        self.assertEqual(facts["VAL","numeric","has_manpower"], 5000)
        self.assertEqual(facts["YPR","variable","ADISCORD_economy_treasury"], 1000)
        self.assertFalse(facts["YPR","has_country_flag","VAL_hire_fee_500_paid"])
        self.assertNotIn(("YPR","scheduled","val_contract.423"), facts)

    def test_custom_price_and_expiry_reconciliation_are_wired(self):
        decision = named_block(read("common/decisions/ADISCORD_VAL_decisions.txt"), "VAL_hire_partner_volunteers")
        self.assertIn("custom_cost_text = VAL_hire_decision_cost", decision)
        self.assertIn("cost = 0", decision)
        self.assertIn("value = 500 compare = greater_than_or_equals", named_block(decision, "custom_cost_trigger"))
        self.assertIn("VAL_reserve_partner_hire_fee = yes", named_block(decision, "complete_effect"))
        effects = read("common/scripted_effects/ADISCORD_VAL_effects.txt")
        self.assertIn("VAL_reconcile_hire_fees = yes", named_block(effects, "VAL_contract_reconcile"))
        self.assertIn("VAL_reconcile_partner_hire_fee = yes", named_block(effects, "VAL_reconcile_hire_fees"))
        for language in ("russian", "english"):
            loc = read(f"localisation/{language}/ADISCORD_VAL_decisions_l_{language}.yml")
            for suffix in ("", "_blocked", "_tooltip"):
                self.assertIn("VAL_hire_decision_cost_500" + suffix + ":0", loc)

    def test_every_hire_offer_path_reserves_the_fee_before_dispatch(self):
        import re
        paths = (
            "common/decisions/ADISCORD_VAL_decisions.txt",
            "events/ADISCORD_VAL_contract_events.txt",
        )
        offers = []
        for path in paths:
            source = read(path)
            for match in re.finditer(r"set_country_flag\s*=\s*\{\s*flag\s*=\s*VAL_partner_offer_hire\b", source):
                offers.append((path, source[max(0, match.start() - 500):match.start()]))
        self.assertEqual(len(offers), 5)
        for path, prefix in offers:
            self.assertIn("VAL_reserve_partner_hire_fee = yes", prefix, path)


class ValHireFixedCostTests(unittest.TestCase):
    def test_fixed_quotes_cover_each_partner_once_and_match_exact_affordability(self):
        from tools.tests.test_adiscord_stp_preparation import parse_clausewitz, block, matches_conditions
        decisions = read("common/decisions/ADISCORD_VAL_decisions.txt")
        expected = {500: {"CIN", "COF", "APH", "OSF", "TFF", "YPR"}}
        covered = set()
        for price, targets in expected.items():
            name = "VAL_hire_partner_volunteers"
            decision = named_block(decisions, name)
            actual = set(re.findall(r"\b[A-Z]{3}\b", named_block(decision, "targets")))
            self.assertEqual(actual, targets)
            self.assertFalse(covered & actual)
            covered |= actual
            self.assertIn(f"custom_cost_text = VAL_hire_decision_cost_{price}", decision)
            guard = block(parse_clausewitz(decision)[0].value, "custom_cost_trigger")
            for balance, enabled in ((price - .01, False), (price, True), (price + 1, True)):
                self.assertEqual(matches_conditions(guard, {("VAL", "variable", "ADISCORD_economy_treasury"): balance}, "VAL"), enabled)
            for language in ("russian", "english"):
                loc = read(f"localisation/{language}/ADISCORD_VAL_decisions_l_{language}.yml")
                for suffix in ("", "_blocked", "_tooltip"):
                    value = re.search(rf'^ VAL_hire_decision_cost_{price}{suffix}:0 "(.*)"$', loc, re.M).group(1)
                    self.assertIn(str(price), value)
                    self.assertIn("£ADISCORD_economy_treasury_texticon", value)
                    self.assertNotIn("[", value)
        self.assertEqual(covered, {"CIN", "COF", "APH", "OSF", "TFF", "YPR"})


class ValHireReplyTests(ValHireReceiptTests):
    def test_superseded_prepaid_quote_refunds_original_price_once(self):
        for buyer, price in (("CIN",300),("COF",300),("OSF",400),("TFF",400),("APH",200),("YPR",500)):
            facts = self.facts("hire", buyer=buyer)
            facts[buyer,"has_country_flag","VAL_hire_fee_paid"] = True
            facts[buyer,"numeric","has_manpower"] = 5000
            facts["VAL","variable","ADISCORD_economy_treasury"] = 1000-price
            self.assertFalse(self.matches("VAL_partner_hire_can_accept", facts, buyer))
            self.execute("VAL_decline_partner_hire", facts, buyer)
            self.assertEqual(facts["VAL","variable","ADISCORD_economy_treasury"],1000)
            after=dict(facts)
            self.execute("VAL_decline_partner_hire", facts, buyer)
            self.assertEqual(facts,after)

    def test_actual_recipient_event_accepts_valid_offer_and_routes_refusal(self):
        from tools.tests.test_adiscord_stp_preparation import parse_clausewitz, block, scalar
        events = parse_clausewitz(read("events/ADISCORD_VAL_contract_events.txt"))
        event = next(e.value for e in events if e.key=="country_event" and scalar(e.value,"id")=="val_contract.364")
        options = {scalar(e.value,"name"):e.value for e in event if e.key=="option"}
        refusal = options["VAL_export_decline"]
        self.assertEqual(scalar(block(refusal,"hidden_effect"),"VAL_decline_partner_hire"),"yes")
        self.assertEqual(scalar(block(refusal,"trigger"),"is_ai"),"no")
        self.assertEqual(scalar(block(refusal,"ai_chance"),"base"),"0")
        self.assertEqual(scalar(block(options["VAL_export_accept"],"ai_chance"),"base"),"100")
        self.assertEqual(scalar(block(options["VAL_export_accept"],"trigger"),"VAL_partner_hire_can_accept"),"yes")
        self.assertEqual(scalar(block(options["VAL_export_accept"],"hidden_effect"),"VAL_settle_partner_hire"),"yes")

    def test_partner_offer_replies_are_player_decline_and_deterministic_ai_accept(self):
        from tools.tests.test_adiscord_stp_preparation import parse_clausewitz, block, scalar
        events = parse_clausewitz(read("events/ADISCORD_VAL_contract_events.txt"))
        event_ids = ("val_contract.362", "val_contract.363", "val_contract.364", "val_contract.365", "val_contract.366", "val_contract.367")
        indexed = {scalar(e.value,"id"):e.value for e in events if e.key=="country_event" and scalar(e.value,"id") in event_ids}
        for event_id in event_ids:
            with self.subTest(event=event_id):
                options = {scalar(e.value,"name"):e.value for e in indexed[event_id] if e.key=="option"}
                decline = options["VAL_export_decline"]
                accept = options["VAL_export_accept"]
                self.assertEqual(scalar(block(decline,"trigger"),"is_ai"),"no")
                if event_id == "val_contract.362":
                    self.assertEqual(scalar(block(decline,"ai_chance"),"base"),"100")
                    self.assertEqual(scalar(block(accept,"ai_chance"),"base"),"0")
                else:
                    self.assertEqual(scalar(block(decline,"ai_chance"),"base"),"0")
                    self.assertEqual(scalar(block(accept,"ai_chance"),"base"),"100")
                if event_id == "val_contract.362":
                    self.assertEqual(scalar(block(accept,"trigger"),"VAL_partner_trade_can_accept"),"yes")
                elif event_id == "val_contract.364":
                    self.assertEqual(scalar(block(accept,"trigger"),"VAL_partner_hire_can_accept"),"yes")
                else:
                    self.assertFalse(any(entry.key=="trigger" for entry in accept))

    def test_legacy_contract_replies_also_leave_decline_to_players(self):
        from tools.tests.test_adiscord_stp_preparation import parse_clausewitz, block, scalar
        events = parse_clausewitz(read("events/ADISCORD_VAL_contract_events.txt"))
        event_ids = tuple(f"val_contract.{event_id}" for event_id in (340, 341, 401, 402, 403, 404, 405, 410))
        indexed = {scalar(e.value,"id"):e.value for e in events if e.key=="country_event" and scalar(e.value,"id") in event_ids}
        for event_id in event_ids:
            with self.subTest(event=event_id):
                options = {scalar(e.value,"name"):e.value for e in indexed[event_id] if e.key=="option"}
                decline = options["VAL_export_decline"]
                accept = options["VAL_export_accept"]
                self.assertEqual(scalar(block(decline,"trigger"),"is_ai"),"no")
                self.assertEqual(scalar(block(decline,"ai_chance"),"base"),"0")
                self.assertEqual(scalar(block(accept,"ai_chance"),"base"),"100")
                self.assertFalse(any(entry.key=="trigger" for entry in accept))


class ValHirePeaceTests(ValHireReceiptTests):
    def test_partner_war_blocks_acceptance_and_refunds_pending_payment(self):
        facts=self.facts("hire",buyer="CIN")
        facts["CIN","numeric","has_manpower"]=5000
        self.execute("VAL_reserve_partner_hire_fee",facts)
        self.assertTrue(self.matches("VAL_partner_hire_can_accept",facts,"CIN"))
        facts["CIN","has_war","no"]=False
        self.assertFalse(self.matches("VAL_partner_hire_can_accept",facts,"CIN"))
        self.execute("VAL_settle_partner_hire",facts)
        self.assertEqual(facts["VAL","variable","ADISCORD_economy_treasury"],1000)
        self.assertEqual(facts["CIN","numeric","has_manpower"],5000)
        self.assertEqual(facts["VAL","scheduled","val_contract.423"],(1,))

    def test_kefreyt_war_does_not_block_a_peaceful_partner(self):
        facts=self.facts("hire",buyer="CIN")
        facts["CIN","numeric","has_manpower"]=5000
        facts["VAL","has_war","no"]=False
        facts["VAL","has_war","yes"]=True
        self.assertTrue(self.matches("VAL_partner_hire_can_accept",facts,"CIN"))


class ValAnnualDecisionVisibilityTests(unittest.TestCase):

    def test_partner_rows_keep_readiness_checks_while_legacy_export_rows_stay_hidden(self):
        source=read("common/decisions/ADISCORD_VAL_decisions.txt")
        pairs={"VAL_sign_annual_trade":"VAL_trade_recipient_ready",
               "VAL_hire_partner_volunteers":"VAL_hire_recipient_ready"}
        for key,predicate in pairs.items():
            decision=named_block(source,key)
            visible=named_block(decision,"visible")
            self.assertIn(predicate+" = yes",visible)
            self.assertNotIn("custom_trigger_tooltip",visible)
            self.assertNotIn("has_political_power",visible)
            target_trigger=named_block(decision,"target_trigger")
            if key=="VAL_sign_annual_trade":
                self.assertIn("VAL_partner_commerce_visible = yes",target_trigger)
                self.assertIn("NOT = { has_country_flag = VAL_market_term_started }",target_trigger)
                self.assertIn("NOT = { has_country_flag = VAL_partner_contact_cooldown }",target_trigger)
            else:
                self.assertEqual(target_trigger.strip(),"target_trigger = { FROM = { exists = yes } }")
            self.assertNotIn("days_re_enable = 365",decision)

        for key in ("VAL_quarterly_partner_supply","VAL_ready_partner_supply","VAL_partner_contract"):
            self.assertEqual(named_block(named_block(source,key),"visible").strip(),"visible = { always = no }")

    def test_foreign_sales_ui_uses_one_abstract_arms_market_row(self):
        decisions=read("common/decisions/ADISCORD_VAL_decisions.txt")

        trade=named_block(decisions,"VAL_sign_annual_trade")
        self.assertIn("VAL_partner_trade_can_offer = yes",named_block(trade,"visible"))

        hire=named_block(decisions,"VAL_hire_partner_volunteers")
        self.assertIn("VAL_partner_hire_can_offer = yes",named_block(hire,"visible"))

        market=named_block(decisions,"VAL_sell_surplus_arms_market")
        self.assertNotIn("targets =",market)
        self.assertNotIn("target_trigger",market)
        self.assertIn("has_completed_focus = VAL_Foreign_Broker_Licences",named_block(market,"visible"))
        self.assertIn("VAL_abstract_arms_buyer = yes",named_block(market,"available"))

        for legacy in ("VAL_quarterly_partner_supply","VAL_ready_partner_supply","VAL_partner_contract"):
            self.assertEqual(named_block(named_block(decisions,legacy),"visible").strip(),"visible = { always = no }")
    def test_success_year_helper_is_separate_from_refusal_handling(self):
        effects=read("common/scripted_effects/ADISCORD_VAL_effects.txt")
        self.assertIn("flag = VAL_partner_contact_cooldown days = 365",named_block(effects,"VAL_begin_partner_contract_year"))
        for key in ("VAL_settle_partner_trade","VAL_settle_partner_hire","VAL_settle_partner_arms","VAL_settle_partner_bulk","VAL_settle_partner_arsenal","VAL_settle_partner_strategic","VAL_accept_order_1","VAL_accept_order_2","VAL_accept_quarterly_order_1","VAL_accept_quarterly_order_2","VAL_accept_military_contract","VAL_record_advisor_conflict"):
            self.assertEqual(named_block(effects,key).count("VAL_begin_partner_contract_year = yes"),1,key)
        for key in ("VAL_decline_partner_hire","VAL_close_partner_offer","VAL_close_order_offer","VAL_refund_trade_fee"):
            self.assertNotIn("VAL_begin_partner_contract_year",named_block(effects,key))


class ValRecipientVisibilityTests(ValHireReceiptTests):
    def test_our_shortage_does_not_hide_a_willing_hire_partner(self):
        facts=self.facts("hire",buyer="CIN")
        facts["CIN","numeric","has_manpower"]=5000
        facts["VAL","variable","ADISCORD_economy_treasury"]=0
        self.assertTrue(self.matches("VAL_hire_recipient_ready",facts,"CIN"))
        self.assertFalse(self.matches("VAL_partner_hire_funds_ready",facts,"CIN"))
        for condition in ("war","people","cooldown"):
            scenario=dict(facts)
            if condition=="war":scenario["CIN","has_war","no"]=False
            if condition=="people":scenario["CIN","numeric","has_manpower"]=4999.9
            if condition=="cooldown":scenario["CIN","has_country_flag","VAL_partner_contact_cooldown"]=True
            self.assertFalse(self.matches("VAL_hire_recipient_ready",scenario,"CIN"),condition)

    def test_refusal_hides_partner_and_stale_reply_cannot_restart_cooldown(self):
        facts=self.facts("hire",buyer="CIN")
        facts["CIN","numeric","has_manpower"]=5000
        self.execute("VAL_decline_partner_hire",facts)
        self.assertFalse(self.matches("VAL_hire_recipient_ready",facts,"CIN"))
        self.assertTrue(facts["CIN","has_country_flag","VAL_partner_contact_cooldown"])
        facts["CIN","has_country_flag","VAL_partner_contact_cooldown"]=False
        self.assertTrue(self.matches("VAL_hire_recipient_ready",facts,"CIN"))
        after=dict(facts)
        self.execute("VAL_record_partner_refusal",facts)
        self.assertEqual(facts,after)
        self.assertIn("flag = VAL_partner_contact_cooldown days = 365",named_block(read("common/scripted_effects/ADISCORD_VAL_effects.txt"),"VAL_record_partner_refusal"))


class ValTradeReplyTests(unittest.TestCase):
    def test_player_timeout_refuses_trade_and_ai_settles_without_reply_event(self):
        source = read("events/ADISCORD_VAL_contract_events.txt")
        start = re.search(r"(?m)^country_event = \{\s*id = val_contract\.362\b", source).start()
        event = named_block(source[start:], "country_event")
        decline = named_block(event, "option")
        self.assertIn("ai_chance = { base = 100 }", decline)
        self.assertNotIn("immediate = { VAL_resolve_partner_trade_reply = yes }", event)
        self.assertIn("VAL_decline_partner_trade = yes", decline)
        self.assertNotIn("timeout_effect", event)
        dispatcher = named_block(read("common/scripted_effects/ADISCORD_VAL_effects.txt"), "VAL_dispatch_partner_trade_offer")
        self.assertIn("limit = { is_ai = yes }", dispatcher)
        self.assertIn("VAL_resolve_partner_trade_reply = yes", dispatcher)
        self.assertIn("country_event = { id = val_contract.362 }", dispatcher)

    def test_expired_paid_trade_hides_for_a_year_and_refunds_once(self):
        model = ValPartnerSettlementTests()
        model.setUpClass()
        facts = model.facts("trade", buyer="CIN")
        facts["CIN", "has_country_flag", "VAL_trade_fee_paid"] = True
        facts["CIN", "has_country_flag", "VAL_partner_offer_trade"] = False
        facts["VAL", "numeric", "has_political_power"] = 0
        model.execute("VAL_reconcile_partner_trade_fee", facts, "CIN")
        self.assertFalse(model.matches("VAL_trade_recipient_ready", facts, "CIN"))
        self.assertEqual(facts["VAL", "scheduled", "val_contract.425"], (1,))
        self.assertEqual(facts["VAL", "numeric", "has_political_power"], 100)
        settled = dict(facts)
        model.execute("VAL_reconcile_partner_trade_fee", facts, "CIN")
        self.assertEqual(facts, settled)


class ValFailureReasonTests(ValHireReceiptTests):
    def test_failure_reason_is_captured_before_refund_clears_evidence(self):
        for outcome, reason in (("decline", 1), ("expiry", 6), ("lost_pending", 7), ("war", 4)):
            facts = self.facts("trade")
            facts["CIN", "has_country_flag", "VAL_trade_fee_paid"] = True
            if outcome == "expiry": facts["CIN", "has_country_flag", "VAL_partner_offer_trade"] = False
            if outcome == "lost_pending": facts["VAL", "has_country_flag", "VAL_partner_offer_pending"] = False
            if outcome == "war": facts["CIN", "has_war_with", "VAL"] = True
            self.execute("VAL_refund_trade_fee", facts)
            self.assertEqual(facts["CIN", "variable", "VAL_partner_failure_reason"], reason, outcome)
            after = dict(facts)
            self.execute("VAL_refund_trade_fee", facts)
            self.assertEqual(after, facts)


class ValParallelOfferTests(ValHireReceiptTests):
    def test_recipient_offer_does_not_depend_on_shared_desk_flag(self):
        source = read("common/scripted_triggers/ADISCORD_VAL_rework_triggers.txt")
        current = named_block(source, "VAL_partner_offer_current")
        self.assertNotIn("has_country_flag = VAL_partner_offer_pending", current)
        self.assertIn("has_country_flag = VAL_partner_offer_trade", named_block(source, "VAL_partner_trade_can_accept"))

    def test_closing_one_contract_preserves_other_recipient_offers(self):
        effects = read("common/scripted_effects/ADISCORD_VAL_effects.txt")
        events = read("events/ADISCORD_VAL_contract_events.txt")
        closers = {
            "trade": "VAL_close_partner_trade_offer",
            "hire": "VAL_close_partner_hire_offer",
            "arms": "VAL_close_partner_arms_offer",
            "bulk": "VAL_close_partner_bulk_offer",
            "arsenal": "VAL_close_partner_arsenal_offer",
            "strategic": "VAL_close_partner_strategic_offer",
        }
        for kind, closer in closers.items():
            block = named_block(effects, closer)
            self.assertIn(f"clr_country_flag = VAL_partner_offer_{kind}", block)
            for other_kind in closers.keys() - {kind}:
                self.assertNotIn(f"clr_country_flag = VAL_partner_offer_{other_kind}", block)
        self.assertIn("VAL_close_partner_hire_offer = yes", named_block(effects, "VAL_settle_partner_hire"))
        for kind in ("arms", "bulk", "arsenal", "strategic"):
            self.assertIn(f"VAL_close_partner_{kind}_offer = yes", events)
