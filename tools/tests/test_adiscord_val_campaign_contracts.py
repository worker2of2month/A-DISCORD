"""Parsed route and payment scenarios; these do not simulate the HOI4 engine."""

from dataclasses import replace
import unittest

from tools.tests.test_adiscord_stp_preparation import (
    block,
    entries,
    matches_conditions,
    scalar,
    walk,
)


EFFECTS = "common/scripted_effects/ADISCORD_VAL_effects.txt"
TRIGGERS = "common/scripted_triggers/ADISCORD_VAL_rework_triggers.txt"
FOCUSES = "focus_trees/VAL/main/focuses.txt"
HOOKS = "common/on_actions/02_ADISCORD_VAL_rework_on_actions.txt"


def selected_effects(items, facts, scope="VAL"):
    """Follow the authored conditional paths without evaluating native effects."""
    previous_branch = False
    for entry in items:
        if entry.key in {"if", "else_if", "else"}:
            if entry.key == "if":
                previous_branch = False
            active = not previous_branch and (
                entry.key == "else"
                or matches_conditions(block(entry.value, "limit"), facts, scope)
            )
            previous_branch |= active
            if active:
                yield from selected_effects(
                    [child for child in entry.value if child.key != "limit"], facts, scope
                )
        elif entry.key in {"VAL", "STP", "STS", "NOD", "YPR", "COF", "TFF"}:
            yield from selected_effects(entry.value, facts, entry.key)
        else:
            yield scope, entry


def resolve_border_neighbors(items, neighbors, scope="VAL"):
    """Expand native country adjacency from explicit scenario fixtures."""
    resolved = []
    for entry in items:
        if entry.key == "any_neighbor_country":
            countries = [
                replace(entry, key=country, value=entry.value)
                for country in neighbors.get(scope, ())
            ]
            resolved.append(replace(entry, key="OR", value=countries))
        elif isinstance(entry.value, list):
            country_scope = entry.key if entry.key in neighbors else scope
            resolved.append(replace(
                entry,
                value=resolve_border_neighbors(entry.value, neighbors, country_scope),
            ))
        else:
            resolved.append(entry)
    return resolved


class ValCampaignContractsTests(unittest.TestCase):
    def test_northern_campaign_requires_a_current_border_for_focus_and_war(self):
        gate = block(entries(TRIGGERS), "VAL_can_attack_northern_coalition")
        focuses = block(entries(FOCUSES), "focus_tree")
        focus = next(
            entry.value for entry in focuses
            if entry.key == "focus"
            and scalar(entry.value, "id") == "VAL_Break_The_Northern_Coalition"
        )
        launch = block(entries(EFFECTS), "VAL_begin_northern_coalition_campaign")
        facts = {
            ("VAL", "has_completed_focus", "VAL_Northern_Settlement"): True,
        }
        for country in ("VAL", "YPR", "COF", "TFF", "NOD"):
            for condition, value in (
                ("exists", "yes"),
                ("has_capitulated", "no"),
                ("is_subject", "no"),
                ("has_war", "no"),
                ("is_in_faction", "no"),
            ):
                facts[(country, condition, value)] = True

        scenarios = (
            ("no border", None, None, False, False, False),
            ("neutral Nodrul blocks access", "YPR", "NOD", False, False, False),
            ("Yubora border", "YPR", "VAL", False, False, True),
            ("Forest border", "COF", "VAL", False, False, True),
            ("Frontier border", "TFF", "VAL", False, False, True),
            ("subject border", "YPR", "NOD", True, False, True),
            ("capitulated subject", "YPR", "NOD", True, True, False),
        )
        for name, target, neighbor, subject, capitulated, expected in scenarios:
            with self.subTest(scenario=name):
                neighbors = {country: () for country in ("VAL", "YPR", "COF", "TFF", "NOD")}
                if target is not None:
                    neighbors[target] = (neighbor,)
                    neighbors[neighbor] = (target,)
                current = {
                    **facts,
                    ("NOD", "is_subject_of", "VAL"): subject,
                    ("NOD", "has_capitulated", "no"): not capitulated,
                }
                allowed = matches_conditions(
                    resolve_border_neighbors(gate, neighbors), current, "VAL"
                )
                self.assertEqual(allowed, expected)
                current[("VAL", "VAL_can_attack_northern_coalition", "yes")] = allowed
                self.assertEqual(
                    matches_conditions(block(focus, "available"), current, "VAL"),
                    expected,
                )
                declarations = [
                    scalar(entry.value, "target")
                    for scope, entry in selected_effects(launch, current)
                    if scope == "VAL" and entry.key == "declare_war_on"
                ]
                self.assertEqual(declarations, ["YPR"] if expected else [])

    def test_each_quarterly_tier_can_pay_its_quoted_price_in_both_slots(self):
        effects = entries(EFFECTS)
        triggers = entries(TRIGGERS)
        for slot in (1, 2):
            order = block(effects, f"VAL_accept_quarterly_order_{slot}")
            for tier, price in ((1, 500), (2, 1000), (3, 2250), (4, 5000)):
                with self.subTest(slot=slot, tier=tier):
                    facts = {("CIN", "variable", "VAL_order_quote_tier"): tier}
                    writes = {
                        scalar(entry.value, "var"): float(scalar(entry.value, "value"))
                        for scope, entry in selected_effects(order, facts, "CIN")
                        if scope == "VAL" and entry.key == "set_variable"
                        and scalar(entry.value, "var") in {
                            f"VAL_order_{slot}_price", f"VAL_order_{slot}_remaining"
                        }
                    }
                    self.assertEqual(writes[f"VAL_order_{slot}_price"], price)
                    facts[("VAL", "variable", f"VAL_order_{slot}_remaining")] = writes[
                        f"VAL_order_{slot}_remaining"
                    ]
                    payment = block(triggers, f"VAL_order_{slot}_partner_can_pay")
                    for treasury, affordable in ((price - 0.01, False), (price, True)):
                        facts[("CIN", "variable", "ADISCORD_economy_treasury")] = treasury
                        self.assertEqual(matches_conditions(payment, facts, "CIN"), affordable)

    def test_refused_pact_does_not_permanently_block_military_settlement(self):
        focuses = block(entries(FOCUSES), "focus_tree")
        campaign = next(
            entry.value for entry in focuses
            if entry.key == "focus" and scalar(entry.value, "id") == "VAL_Campaign_Secured"
        )
        facts = {
            ("VAL", "has_completed_focus", "VAL_Equal_Powers_Pact"): True,
            ("VAL", "has_country_flag", "VAL_stelander_alliance_refused"): True,
            ("VAL", "VAL_campaign_objectives_met", "yes"): True,
        }
        excluded = [entry for entry in campaign if entry.key == "mutually_exclusive"]
        for exclusion in excluded:
            self.assertFalse(any(
                facts.get(("VAL", "has_completed_focus", entry.value), False)
                for entry in exclusion.value
            ), "A rejected offer must not commit the country to a nonexistent alliance")
        self.assertTrue(matches_conditions(block(campaign, "available"), facts, "VAL"))
        for flag in ("VAL_stelander_alliance_offer_pending", "VAL_stelander_equal_alliance"):
            with self.subTest(flag=flag):
                pending = dict(facts)
                pending[("VAL", "has_country_flag", flag)] = True
                self.assertFalse(matches_conditions(block(campaign, "available"), pending, "VAL"))

    def test_future_war_calls_partner_in_both_native_hook_orientations(self):
        hook = block(block(block(entries(HOOKS), "on_actions"), "on_war_relation_added"), "effect")

        def resolve(items, root, sender):
            return [replace(
                entry,
                key={"ROOT": root, "FROM": sender}.get(entry.key, entry.key),
                value=resolve(entry.value, root, sender) if isinstance(entry.value, list) else entry.value,
            ) for entry in items]

        for root, sender in (("VAL", "NOD"), ("NOD", "VAL")):
            with self.subTest(root=root, sender=sender):
                calls = list(selected_effects(resolve(hook, root, sender), {}))
                self.assertIn(
                    ("VAL", "VAL_call_stelander_partner_to_wars"),
                    [(scope, entry.key) for scope, entry in calls],
                )

    def test_alliance_acceptance_rechecks_recipient_and_current_offer(self):
        gate = block(entries(TRIGGERS), "VAL_stelander_equal_offer_can_accept")
        facts = {
            ("STS", "VAL_stelander_equal_recipient_available", "yes"): True,
            ("STS", "has_country_flag", "VAL_stelander_alliance_offer_received"): True,
            ("VAL", "has_country_flag", "VAL_stelander_alliance_offer_pending"): True,
            ("VAL", "VAL_stelander_equal_partner_available", "yes"): True,
        }
        self.assertTrue(matches_conditions(gate, facts, "STS"))
        for key in facts:
            with self.subTest(missing=key):
                stale = dict(facts)
                stale[key] = False
                self.assertFalse(matches_conditions(gate, stale, "STS"))

    def test_coalition_cleanup_only_releases_majors_created_by_this_campaign(self):
        effects = entries(EFFECTS)
        cleanup = block(effects, "VAL_close_northern_coalition_campaign")
        for original_major in (False, True):
            with self.subTest(original_major=original_major):
                facts = {("VAL", "VAL_can_attack_northern_coalition", "yes"): True}
                for country in ("YPR", "COF", "TFF"):
                    facts[(country, "is_major", "yes")] = original_major
                    facts[(country, "is_major", "no")] = not original_major
                startup = list(selected_effects(block(effects, "VAL_begin_northern_coalition_campaign"), facts))
                for scope, entry in startup:
                    if entry.key == "set_country_flag" and isinstance(entry.value, str):
                        facts[(scope, "has_country_flag", entry.value)] = True
                changes = [
                    (scope, entry.value) for scope, entry in selected_effects(cleanup, facts)
                    if entry.key == "set_major"
                ]
                self.assertEqual(changes, [] if original_major else [(tag, "no") for tag in ("YPR", "COF", "TFF")])

    def test_military_final_closes_new_alliance_offers(self):
        gate = block(entries(TRIGGERS), "VAL_stelander_equal_partner_available")
        facts = {
            ("VAL", "exists", "yes"): True,
            ("VAL", "has_country_flag", "VAL_stelander_equal_recognition"): True,
            ("VAL", "is_subject", "no"): True,
            ("VAL", "has_capitulated", "no"): True,
            ("VAL", "has_war", "no"): True,
            ("VAL", "is_in_faction", "no"): True,
            ("STS", "VAL_stelander_equal_recipient_available", "yes"): True,
        }
        self.assertTrue(matches_conditions(gate, facts, "VAL"))
        facts[("VAL", "has_completed_focus", "VAL_Campaign_Secured")] = True
        self.assertFalse(matches_conditions(gate, facts, "VAL"))

    def test_southern_corridor_loss_uses_the_same_pressure_as_other_routes(self):
        weekly = block(entries("common/scripted_effects/ADISCORD_VAL_logistics_market_effects.txt"), "VAL_update_black_market_weekly")
        for route in ("occidia", "west", "north", "stelander", "vorkerland", "south"):
            facts = {
                ("VAL", "VAL_trade_corridors_unlocked", "yes"): True,
                ("VAL", "has_country_flag", f"VAL_route_{route}_commissioned"): True,
                ("VAL", "variable", "VAL_trade_corridors_capacity"): 6,
            }
            with self.subTest(route=route):
                additions = [
                    float(scalar(entry.value, "value"))
                    if scalar(entry.value, "value").lstrip("-").isdigit()
                    else facts.get((scope, "variable", scalar(entry.value, "value")), 0)
                    for scope, entry in selected_effects(weekly, facts)
                    if entry.key == "add_to_temp_variable"
                    and scalar(entry.value, "var") == "VAL_black_market_weekly_delta"
                ]
                self.assertEqual(sum(additions), 3)

    def test_operation_family_selects_exactly_one_success_result(self):
        effects = entries(EFFECTS)
        for partner in ("CIN", "OSF", "APH"):
            operation = block(effects, f"VAL_resolve_{partner.lower()}_operation")
            for family, outcome in enumerate(("market", "arms", "infrastructure", "captain", "terms"), 1):
                with self.subTest(partner=partner, family=family):
                    facts = {("VAL", "variable", "ADISCORD_VAL_family_code"): family}
                    awarded = [
                        entry.value for scope, entry in selected_effects(operation, facts)
                        if entry.key == "set_country_flag" and isinstance(entry.value, str)
                        and entry.value.startswith(f"VAL_{partner}_success_")
                    ]
                    self.assertEqual(awarded, [f"VAL_{partner}_success_{outcome}"])

    def test_nodrul_cosmetic_change_does_not_skip_administration_content(self):
        finish = block(entries(EFFECTS), "VAL_finish_nodrul_administration")

        def gates_for(items, key, gates=()):
            for entry in items:
                if entry.key == key:
                    yield gates
                elif entry.key == "if":
                    yield from gates_for(entry.value, key, gates + (block(entry.value, "limit"),))
                elif isinstance(entry.value, list) and entry.key != "limit":
                    yield from gates_for(entry.value, key, gates)

        facts = {
            ("NOD", "has_country_flag", "VAL_nodrul_administration_pending"): True,
            ("NOD", "has_cosmetic_tag", "NOD_VAL_administration"): True,
            ("NOD", "is_subject_of", "VAL"): True,
            ("VAL", "exists", "yes"): True,
            ("VAL", "has_capitulated", "no"): True,
            ("VAL", "is_subject", "no"): True,
        }
        for reward in ("set_politics", "promote_character", "load_focus_tree"):
            paths = list(gates_for(finish, reward))
            with self.subTest(reward=reward):
                self.assertTrue(any(all(matches_conditions(gate, facts, "NOD") for gate in path) for path in paths))
                settled = dict(facts)
                settled[("NOD", "has_country_flag", "VAL_nodrul_administration_pending")] = False
                self.assertFalse(any(all(matches_conditions(gate, settled, "NOD") for gate in path) for path in paths))

    def test_restored_countries_release_from_the_actual_owner_then_join_val(self):
        restoration = block(entries(EFFECTS), "VAL_restore_stelander_conquered_administrations")

        def native_calls(items, scope="VAL"):
            for entry in items:
                if entry.key in {"release_autonomy", "set_autonomy"}:
                    yield scope, entry.key, scalar(entry.value, "target")
                elif isinstance(entry.value, list):
                    child_scope = entry.key if entry.key in {"STS", "VAL"} else scope
                    yield from native_calls(entry.value, child_scope)

        calls = list(native_calls(restoration))
        for country in ("BJK", "BLD", "BHG", "BGT", "BBV", "BCM", "YPR"):
            with self.subTest(country=country):
                self.assertIn(("STS", "release_autonomy", country), calls)
                self.assertIn(("VAL", "set_autonomy", country), calls)
                self.assertLess(calls.index(("STS", "release_autonomy", country)), calls.index(("VAL", "set_autonomy", country)))

    def test_transit_acceptance_requires_live_offer_and_current_corridor(self):
        gate = block(entries(TRIGGERS), "VAL_transit_charter_can_accept")
        facts = {
            ("CIN", "exists", "yes"): True,
            ("CIN", "has_capitulated", "no"): True,
            ("CIN", "has_country_flag", "VAL_transit_offer"): True,
            ("CIN", "variable", "VAL_completed_contracts"): 2,
            ("CIN", "VAL_has_transit_corridor_foothold", "yes"): True,
            ("VAL", "exists", "yes"): True,
            ("VAL", "has_capitulated", "no"): True,
            ("VAL", "has_country_flag", "VAL_partner_offer_pending"): True,
        }
        self.assertTrue(matches_conditions(gate, facts, "CIN"))
        for change in (
            {("CIN", "has_country_flag", "VAL_transit_offer"): False},
            {("VAL", "has_country_flag", "VAL_partner_offer_pending"): False},
            {("CIN", "has_war_with", "VAL"): True},
            {("CIN", "VAL_has_transit_corridor_foothold", "yes"): False},
            {("CIN", "variable", "VAL_completed_contracts"): 1},
            {("VAL", "exists", "yes"): False},
        ):
            with self.subTest(change=change):
                self.assertFalse(matches_conditions(gate, {**facts, **change}, "CIN"))

    def test_southern_settlement_preserves_third_party_owner_not_occupation(self):
        # Kefreyt's fixed claim survives a third party's occupation; only a state
        # that someone else already owns stays outside the settlement.
        settlement = block(entries(EFFECTS), "VAL_settle_wasteland_capitulation")
        south = [
            entry.value for entry in walk(settlement)
            if entry.key == "168" and any(child.key == "VAL" for child in walk(entry.value))
        ]
        self.assertTrue(south)
        for owner in ("ERT", "VAL", "WCA", "OCA", "STP"):
            for controller in ("ERT", "VAL", "WCA", "OCA", "STP"):
                with self.subTest(owner=owner, controller=controller):
                    facts = {
                        ("168", "owner"): owner,
                        ("168", "controller"): controller,
                        ("168", "is_owned_by", "ERT"): owner == "ERT",
                        ("WCA", "is_subject_of", "VAL"): True,
                        ("OCA", "is_subject_of", "VAL"): True,
                    }
                    transfers = [
                        entry for scope, entry in selected_effects(south[0], facts, "168")
                        if scope == "VAL" and entry.key == "transfer_state"
                    ]
                    self.assertEqual(bool(transfers), owner == "ERT")

if __name__ == "__main__":
    unittest.main()
