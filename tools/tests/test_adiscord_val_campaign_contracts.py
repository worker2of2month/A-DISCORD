"""Parsed route and payment scenarios; these do not simulate the HOI4 engine."""

from dataclasses import replace
from pathlib import Path
import re
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
    def test_frontier_protectorate_leaves_the_two_independent_northern_enemies_reachable(self):
        gate = block(entries(TRIGGERS), "VAL_can_attack_northern_coalition")
        facts = {("VAL", "has_completed_focus", "VAL_Northern_Settlement"): True}
        for tag in ("VAL", "YPR", "COF", "TFF"):
            for key, value in (("exists", "yes"), ("has_capitulated", "no"),
                               ("has_war", "no"), ("is_subject", "no"),
                               ("is_in_faction", "no")):
                facts[tag, key, value] = True
        facts["TFF", "is_subject", "no"] = False
        facts["TFF", "is_subject_of", "VAL"] = True
        facts["TFF", "is_in_faction", "no"] = False
        facts["TFF", "is_in_faction_with", "VAL"] = True
        for bordering, expected in (("YPR", True), ("COF", True), ("TFF", False)):
            with self.subTest(bordering=bordering):
                neighbors = {"YPR": (), "COF": (), "TFF": ()}
                neighbors[bordering] = ("VAL",) if bordering == "TFF" else ("TFF",)
                resolved = resolve_border_neighbors(gate, neighbors)
                self.assertEqual(matches_conditions(resolved, facts, "VAL"), expected)

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
        from tools.tests.test_adiscord_peace_coalition_lifecycle import NorthernWarEntryFixture

        for original_major in (False, True):
            with self.subTest(original_major=original_major):
                fixture = NorthernWarEntryFixture()
                initial = {"YPR", "COF", "TFF"} if original_major else set()
                fixture.majors = initial.copy()
                fixture.execute(fixture.effects["VAL_begin_northern_coalition_campaign"])
                self.assertEqual(fixture.majors, {"YPR", "COF", "TFF"})
                fixture.execute(fixture.effects["VAL_close_northern_coalition_campaign"])
                self.assertEqual(fixture.majors, initial)

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

    def test_nodrul_handoff_detaches_foreign_factions_but_preserves_val_membership(self):
        effects = entries(EFFECTS)
        scenarios = (
            ("old faction leader", True, False, True, "dismantle_faction"),
            ("old faction member", True, False, False, "remove_from_faction"),
            ("native join already applied", True, True, False, None),
            ("no faction", False, False, False, None),
        )
        for effect in ("VAL_install_nodrul_administration", "VAL_complete_nodrul_administration"):
            for name, in_faction, allied, leader, expected in scenarios:
                with self.subTest(effect=effect, scenario=name):
                    facts = {
                        ("VAL", "exists", "yes"): True,
                        ("VAL", "has_capitulated", "no"): True,
                        ("VAL", "is_subject", "no"): True,
                        ("NOD", "has_country_flag", "VAL_nodrul_administration_pending"): True,
                        ("NOD", "is_in_faction", "yes"): in_faction,
                        ("NOD", "is_in_faction_with", "VAL"): allied,
                        ("NOD", "is_faction_leader", "yes"): leader,
                    }
                    selected = list(selected_effects(block(effects, effect), facts, "NOD"))
                    detachments = [
                        item.key
                        for _, entry in selected if entry.key == "faction_leader"
                        for item in walk(entry.value)
                        if item.key in ("dismantle_faction", "remove_from_faction")
                    ]
                    self.assertEqual(detachments, [expected] if expected else [])
                    if effect == "VAL_complete_nodrul_administration":
                        autonomy = [
                            scalar(entry.value, "target")
                            for scope, entry in selected
                            if scope == "VAL" and entry.key == "set_autonomy"
                        ]
                        self.assertEqual(autonomy, [] if expected else ["NOD"])

    def test_nodrul_finalizer_joins_overlord_faction_before_announcing_settlement(self):
        finish = block(entries(EFFECTS), "VAL_finish_nodrul_administration")
        scenarios = (
            ("puppet outside existing pact", True, False, True, True),
            ("puppet already in pact", True, True, True, False),
            ("overlord without faction", True, False, False, False),
            ("foreign puppet", False, False, True, False),
        )
        for name, subject, in_faction, val_faction, expected in scenarios:
            with self.subTest(scenario=name):
                facts = {
                    ("VAL", "exists", "yes"): True,
                    ("VAL", "has_capitulated", "no"): True,
                    ("VAL", "is_subject", "no"): True,
                    ("VAL", "is_in_faction", "yes"): val_faction,
                    ("NOD", "is_subject_of", "VAL"): subject,
                    ("NOD", "is_in_faction", "no"): not in_faction,
                    ("NOD", "has_country_flag", "VAL_nodrul_administration_pending"): True,
                }
                selected = list(selected_effects(finish, facts, "NOD"))
                joins = [
                    (scope, item.value)
                    for scope, entry in selected if entry.key == "faction_leader"
                    for item in walk(entry.value) if item.key == "add_to_faction"
                ]
                self.assertEqual(joins, [("VAL", "NOD")] if expected else [])
                if expected:
                    join = next(i for i, (_, entry) in enumerate(selected) if entry.key == "faction_leader")
                    announcement = next(
                        i for i, (_, entry) in enumerate(selected)
                        if entry.key == "country_event" and scalar(entry.value, "id") == "val_contract.348"
                    )
                    completion = next(
                        i for i, (_, entry) in enumerate(selected)
                        if entry.key == "clr_country_flag" and entry.value == "VAL_nodrul_administration_pending"
                    )
                    self.assertLess(join, announcement)
                    self.assertLess(join, completion)

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

class ValLateStoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.events = {
            scalar(entry.value, "id"): entry.value
            for entry in entries("events/ADISCORD_VAL_contract_events.txt")
            if entry.key == "country_event"
        }

    def scene(self, number):
        event_id = f"val_rework.{number}"
        self.assertTrue(event_id in self.events, f"Missing scene: {event_id}")
        return self.events[event_id]

    def test_arms_scene_requires_delivery_and_a_surviving_independent_winner(self):
        scene = self.scene(151)
        facts = {
            ("VAL", "exists", "yes"): True,
            ("VAL", "has_capitulated", "no"): True,
            ("VAL", "is_subject", "no"): True,
            ("VAL", "ruling_leader"): "VAL_Valera_Solgalov",
            ("VAL", "has_country_flag", "VAL_cw_arms_contract_fulfilled"): True,
            ("STS", "exists", "yes"): True,
            ("STS", "has_capitulated", "no"): True,
            ("STS", "is_subject", "no"): True,
            ("STS", "ruling_leader"): "STP_maksim_shabrat",
            ("STS", "has_country_flag", "STP_cw_won_union_battle"): True,
        }
        gate = block(scene, "trigger")
        self.assertTrue(matches_conditions(gate, facts, "VAL"))
        changes = (
            (("VAL", "has_country_flag", "VAL_cw_arms_contract_fulfilled"), False),
            (("STS", "has_country_flag", "STP_cw_won_union_battle"), False),
            (("STS", "exists", "yes"), False),
            (("STS", "is_subject", "no"), False),
            (("STS", "has_capitulated", "no"), False),
            (("VAL", "has_war_with", "STS"), True),
            (("VAL", "ruling_leader"), "VAL_Commanders_Council"),
            (("STS", "ruling_leader"), "STP_Pavel_Lanskoy"),
        )
        for key, value in changes:
            with self.subTest(changed=key):
                self.assertFalse(matches_conditions(gate, {**facts, key: value}, "VAL"))

    def test_northern_outcomes_select_exactly_one_current_description(self):
        scene = self.scene(153)
        scenarios = (
            ({("NOD", "is_subject_of", "VAL"): True}, "dominated"),
            ({("VAL", "has_country_flag", "VAL_joint_nod_settlement_completed"): True}, "shared"),
            ({("VAL", "is_subject", "yes"): True}, "setback"),
            ({("VAL", "has_country_flag", "VAL_frontier_armistice_signed"): True}, "setback"),
            ({}, "agreement"),
            ({("NOD", "is_subject_of", "VAL"): True,
              ("VAL", "has_country_flag", "VAL_frontier_armistice_signed"): True}, "dominated"),
        )
        for facts, expected in scenarios:
            with self.subTest(expected=expected, facts=facts):
                descriptions = [
                    scalar(entry.value, "text") for entry in scene
                    if entry.key == "desc"
                    and matches_conditions(block(entry.value, "trigger"), facts, "VAL")
                ]
                self.assertEqual(descriptions, [f"val_rework.153.{expected}"])
        gate = block(scene, "trigger")
        facts = {("VAL", "exists", "yes"): True, ("NOD", "exists", "yes"): True}
        self.assertTrue(matches_conditions(gate, facts, "VAL"))
        self.assertFalse(matches_conditions(gate, {**facts, ("VAL", "has_war_with", "NOD"): True}, "VAL"))
        self.assertFalse(matches_conditions(gate, {**facts, ("NOD", "exists", "yes"): False}, "VAL"))

    def test_arms_story_dispatch_does_not_require_the_optional_support_programme(self):
        settlement = block(entries("common/scripted_effects/ADISCORD_STP_scripted_effects.txt"),
                           "STP_cw_settle_union_victory")
        dispatches = [entry for entry in settlement if entry.key == "if" and any(
            child.key == "country_event" and scalar(child.value, "id") == "val_rework.151"
            for child in walk(entry.value)
        )]
        self.assertEqual(len(dispatches), 1)
        for winner, delivered, expected in (("STS", True, True), ("STS", False, False), ("STP", True, False)):
            with self.subTest(winner=winner, delivered=delivered):
                facts = {
                    ("VAL", "exists", "yes"): True,
                    ("VAL", "has_country_flag", "VAL_cw_arms_contract_fulfilled"): delivered,
                }
                calls = [(scope, scalar(entry.value, "id"))
                         for scope, entry in selected_effects(dispatches, facts, winner)
                         if entry.key == "country_event"]
                self.assertEqual(calls, [("VAL", "val_rework.151")] if expected else [])

    def test_tribal_peace_only_dispatches_northern_story_for_its_actual_guarantor(self):
        for name in ("VAL_frontier_settle_victory", "VAL_frontier_settle_armistice"):
            settlement = block(block(entries(EFFECTS), name), "if")
            close = next(i for i, entry in enumerate(settlement) if entry.key == "VAL_frontier_close")
            dispatches = [(i, entry) for i, entry in enumerate(settlement) if entry.key == "if" and any(
                child.key == "country_event" and scalar(child.value, "id") == "val_rework.153"
                for child in walk(entry.value)
            )]
            self.assertEqual(len(dispatches), 1)
            index, dispatch = dispatches[0]
            self.assertLess(index, close)
            for guarantor in (True, False):
                facts = {("NOD", "has_country_flag", "VAL_frontier_guarantor"): guarantor}
                calls = [entry for _, entry in selected_effects([dispatch], facts) if entry.key == "country_event"]
                self.assertEqual(len(calls), int(guarantor))

    def test_propaganda_scene_requires_a_stelander_mobilisation_under_solgalov(self):
        gate = block(self.scene(152), "trigger")
        facts = {
            ("VAL", "exists", "yes"): True,
            ("VAL", "has_capitulated", "no"): True,
            ("VAL", "is_subject", "no"): True,
            ("VAL", "ruling_leader"): "VAL_Valera_Solgalov",
            ("VAL", "has_country_flag", "VAL_campaign_mobilizing"): True,
        }
        for target in ("STP", "STS", "NOD"):
            for mobilizing in (True, False):
                current = {
                    **facts,
                    (target, "exists", "yes"): True,
                    (target, "has_country_flag", "VAL_campaign_target"): True,
                    ("VAL", "has_country_flag", "VAL_campaign_mobilizing"): mobilizing,
                }
                self.assertEqual(matches_conditions(gate, current, "VAL"), target != "NOD" and mobilizing)
                current[("VAL", "ruling_leader")] = "VAL_Commanders_Council"
                self.assertFalse(matches_conditions(gate, current, "VAL"))

    def test_story_windows_are_once_only_and_close_without_gameplay_or_navigation(self):
        for number in range(149, 154):
            with self.subTest(event=number):
                scene = self.scene(number)
                self.assertEqual(scalar(scene, "is_triggered_only"), "yes")
                self.assertEqual(scalar(scene, "fire_only_once"), "yes")
                self.assertFalse(any(entry.key == "immediate" for entry in scene))
                options = [entry.value for entry in scene if entry.key == "option"]
                self.assertEqual(len(options), 1)
                self.assertEqual([entry.key for entry in options[0]], ["name"])

    def test_story_pages_have_complete_bounded_localisation_in_both_languages(self):
        root = Path(__file__).resolve().parents[2]
        for language in ("russian", "english"):
            path = root / f"localisation/{language}/ADISCORD_VAL_decisions_l_{language}.yml"
            data = path.read_bytes()
            self.assertTrue(data.startswith(b"\xef\xbb\xbf"))
            values = dict(re.findall(r'^\s*([^\s:#]+):\d*\s+"(.*)"\s*$', data.decode("utf-8-sig"), re.M))
            for number in range(149, 154):
                scene = self.scene(number)
                keys = [scalar(scene, "title"), scalar(block(scene, "option"), "name")]
                keys += [scalar(entry.value, "text") if isinstance(entry.value, list) else entry.value
                         for entry in scene if entry.key == "desc"]
                for key in keys:
                    with self.subTest(language=language, key=key):
                        self.assertIn(key, values)
                        text = values[key].replace("\\n", "\n")
                        self.assertNotRegex(text, r'[\u2013\u2014\u2022;$]')
                        self.assertLessEqual(len(text), 3000)
                        self.assertLessEqual(len(text.encode("utf-8")), 5500)


if __name__ == "__main__":
    unittest.main()
