"""Source-backed civil-war scenarios; native war/UI behaviour needs a game run."""

from itertools import combinations, product
from pathlib import Path
import re
import unittest

from tools.tests.test_adiscord_stp_preparation import block, scalar, walk
from tools.validators.validate_adiscord_division_templates import parse_clausewitz


ROOT = Path(__file__).resolve().parents[2]
TAGS = ("IVN", "IVC", "IMD", "IFC", "IAM")
EFFECTS = "common/scripted_effects/ADISCORD_IVN_scripted_effects.txt"
TRIGGERS = "common/scripted_triggers/ADISCORD_IVN_scripted_triggers.txt"
EVENTS = "events/ADISCORD_IVN_events.txt"
PARTITIONS = {
    "IVC": {92, 95, 96, 97},
    "IMD": {127, 132, 715},
    "IFC": {100, 101},
    "IAM": {129, 130, 131, 164},
}


def read(path):
    return (ROOT / path).read_text(encoding="utf-8-sig")


def definitions(path):
    return {entry.key: entry.value for entry in parse_clausewitz(read(path))}


def conditions(rows, facts, triggers, scope, root, sender=None):
    """Evaluate only the native boolean subset used by the lifecycle guards.

    Unsupported syntax fails the fixture instead of inventing engine behaviour.
    """
    results = []
    index = 0
    while index < len(rows):
        entry = rows[index]
        key, value = entry.key, entry.value
        if not key:
            field, operator, number = (item.value for item in rows[index:index + 3])
            left = facts.get((scope, field), 0)
            right = float(number)
            results.append({"<": left < right, ">": left > right}[operator])
            index += 3
            continue
        index += 1
        if key in ("OR", "AND", "NOT"):
            groups = []
            cursor = 0
            while cursor < len(value):
                size = 3 if not value[cursor].key else 1
                groups.append(conditions(value[cursor:cursor + size], facts, triggers, scope, root, sender))
                cursor += size
            results.append(any(groups) if key == "OR" else not any(groups) if key == "NOT" else all(groups))
        elif key in TAGS or key in ("ROOT", "FROM"):
            target = root if key == "ROOT" else sender if key == "FROM" else key
            results.append(conditions(value, facts, triggers, target, root, sender))
        elif key in triggers:
            results.append(conditions(triggers[key], facts, triggers, scope, root, sender) == (value == "yes"))
        elif key == "tag":
            target = root if value == "ROOT" else sender if value == "FROM" else value
            results.append(scope == target)
        elif key in ("exists", "has_capitulated", "has_war", "is_subject", "always"):
            actual = True if key == "always" else facts.get((scope, key), False)
            results.append(actual == (value == "yes"))
        elif key in ("has_country_flag", "has_global_flag"):
            results.append(facts.get(("global" if key == "has_global_flag" else scope, value), False))
        elif key == "has_completed_focus":
            results.append(facts.get((scope, value), False))
        elif key == "power_balance_value":
            comparison = [item.value for item in value if not item.key]
            self_value = facts.get((scope, scalar(value, "id")), 0)
            results.append(self_value > float(comparison[2]) if comparison[1] == ">" else self_value < float(comparison[2]))
        else:
            raise AssertionError(f"Unsupported lifecycle predicate: {entry}")
    return all(results)


class ItoraCivilWarTests(unittest.TestCase):
    def setUp(self):
        self.effects = definitions(EFFECTS)
        self.triggers = definitions(TRIGGERS)

    def effect(self, name):
        self.assertTrue(name in self.effects, f"Missing gameplay effect {name}")
        return self.effects[name]

    def test_partition_assigns_disjoint_existing_home_states(self):
        partition = self.effect("IVN_cw_partition")
        actual = {}
        for country in partition:
            actual[country.key] = {
                int(entry.value) for entry in country.value if entry.key == "transfer_state"
            }
        self.assertEqual(actual, PARTITIONS)
        assigned = set()
        for tag, states in actual.items():
            self.assertFalse(assigned & states, tag)
            assigned |= states
            for state in states:
                source = next((ROOT / "history/states").glob(f"{state}-*.txt")).read_text(encoding="utf-8")
                self.assertRegex(source, r"\bowner\s*=\s*IVN\b")
        self.assertNotIn(25, assigned)

    def test_every_pair_fights_and_only_after_side_choice(self):
        wars = self.effect("IVN_cw_declare_wars")
        actual = []
        for country in wars:
            for entry in walk(country.value):
                if entry.key == "declare_war_on":
                    actual.append(frozenset((country.key, scalar(entry.value, "target"))))
        self.assertCountEqual(actual, [frozenset(pair) for pair in combinations(TAGS, 2)])
        events = parse_clausewitz(read(EVENTS))
        choice = next(e.value for e in events if e.key == "country_event" and scalar(e.value, "id") == "ADISCORD_ivn.2")
        self.assertEqual(scalar(choice, "timeout_days"), "7")
        options = [e.value for e in choice if e.key == "option"]
        self.assertEqual(len(options), 5)
        for option in options:
            calls = [e for e in walk(option) if e.key == "IVN_cw_begin_hostilities"]
            self.assertEqual(len(calls), 1)
        start = self.effect("IVN_start_marches_revolt")
        self.assertNotIn("declare_war_on", {e.key for e in walk(start)})

    def test_partial_defeat_does_not_resolve_or_award_other_participants(self):
        absorb = self.effect("IVN_cw_absorb_defeated")
        annexes = [scalar(e.value, "target") for e in walk(absorb) if e.key == "annex_country"]
        self.assertEqual(annexes, ["ROOT"])
        self.assertNotIn("IVN_resolve_marches_revolt", {e.key for e in walk(absorb)})
        self.assertNotIn("clr_global_flag", {e.key for e in walk(absorb)})

    def test_every_other_existing_participant_blocks_final_victory(self):
        self.assertIn("IVN_cw_last_participant", self.triggers)
        predicate = self.triggers["IVN_cw_last_participant"]
        for winner in TAGS:
            others = [tag for tag in TAGS if tag != winner]
            for alive in product((False, True), repeat=4):
                facts = {(winner, "exists"): True}
                facts.update({(tag, "exists"): state for tag, state in zip(others, alive)})
                actual = conditions(predicate, facts, self.triggers, winner, winner)
                self.assertEqual(actual, not any(alive), (winner, alive))
                for other in others:
                    facts[(other, "has_capitulated")] = True
                self.assertEqual(conditions(predicate, facts, self.triggers, winner, winner), actual)

    def test_external_war_delays_canonical_tag_handoff(self):
        for winner in TAGS:
            facts = {(winner, "exists"): True, (winner, "has_war"): True}
            self.assertFalse(conditions(self.triggers["IVN_cw_last_participant"], facts, self.triggers, winner, winner))

    def test_offer_acceptance_boundaries_and_stale_sender(self):
        for minor in TAGS[2:]:
            for principal, marker in (("IVN", "committee"), ("IVC", "legion")):
                facts = {
                    ("global", "IVN_marches_revolt_active"): True,
                    (minor, "exists"): True,
                    (principal, "exists"): True,
                    (minor, "IVN_cw_offer_pending"): True,
                    (minor, f"IVN_cw_offer_{marker}"): True,
                    (principal, "has_political_power"): 75,
                }
                predicate = self.triggers["IVN_cw_offer_valid"]
                self.assertTrue(conditions(predicate, facts, self.triggers, minor, minor, principal))
                for changed, value in (
                    ((principal, "has_political_power"), 74.999),
                    ((principal, "exists"), False),
                    ((principal, "has_capitulated"), True),
                    ((minor, "exists"), False),
                    ((minor, "has_capitulated"), True),
                    ((minor, "IVN_cw_offer_pending"), False),
                    ((minor, f"IVN_cw_offer_{marker}"), False),
                    (("global", "IVN_marches_revolt_active"), False),
                ):
                    self.assertFalse(conditions(predicate, {**facts, changed: value}, self.triggers, minor, minor, principal), changed)

    def test_treasury_and_debt_are_split_without_newborn_money(self):
        source = self.effect("IVN_marches_revolt_transfer_units")
        for tag in TAGS:
            country = block(source, tag)
            assignments = [scalar(e.value, "var") for e in country if e.key == "set_variable"]
            self.assertIn("ADISCORD_economy_treasury", assignments, tag)
            self.assertIn("ADISCORD_economy_debt", assignments, tag)

    def test_army_reserve_and_budget_shares_conserve_the_original_pools(self):
        for balance, promoted, dismissed, directory in (
            (0.35, False, False, 0.10),
            (0.351, False, False, 0.15),
            (-0.5, True, False, 0.15),
            (0.8, False, True, 0.05),
        ):
            facts = {
                ("IVN", "IVN_command_bop"): balance,
                ("IVN", "IVN_command_promote_karn"): promoted,
                ("IVN", "IVN_command_sideline_karn"): dismissed,
            }
            values = {tag: {"manpower": 133.75} for tag in TAGS}
            values["IVN"].update(IVN_cw_recruits=70000, IVN_cw_start_treasury=750, IVN_cw_start_debt=900)
            army = {"IVN": 1.0}

            def number(value, scope):
                value = value.removeprefix("var:")
                try:
                    return float(value)
                except ValueError:
                    if value.startswith("IVN."):
                        return values["IVN"][value.removeprefix("IVN.")]
                    return values[scope][value]

            def execute(rows, scope="IVN"):
                selected = False
                for entry in rows:
                    key, value = entry.key, entry.value
                    if key in ("if", "else_if"):
                        if key == "if":
                            selected = False
                        if not selected and conditions(block(value, "limit"), facts, self.triggers, scope, "IVN"):
                            selected = True
                            execute([e for e in value if e.key != "limit"], scope)
                    elif key in TAGS:
                        execute(value, key)
                    elif key in ("set_variable", "set_temp_variable", "multiply_variable", "multiply_temp_variable", "divide_variable", "subtract_from_variable"):
                        name, amount = scalar(value, "var"), number(scalar(value, "value"), scope)
                        if key.startswith("set_"):
                            values[scope][name] = amount
                        elif key.startswith("multiply_"):
                            values[scope][name] *= amount
                        elif key == "divide_variable":
                            values[scope][name] /= amount
                        else:
                            values[scope][name] -= amount
                    elif key == "add_manpower":
                        values[scope]["manpower"] += number(value, scope)
                    elif key == "clear_variable":
                        values[scope].pop(value, None)
                    elif key == "transfer_units_fraction":
                        ratio = number(scalar(value, "size"), scope)
                        recipient = scalar(value, "target")
                        army[recipient] = army["IVN"] * ratio
                        army["IVN"] -= army[recipient]
                        self.assertAlmostEqual(ratio, number(scalar(value, "stockpile_ratio"), scope))
                    else:
                        self.fail(f"Unsupported allocation effect: {entry}")

            execute(self.effect("IVN_marches_revolt_transfer_units"))
            expected = {"IVN": 0.5 - directory, "IVC": 0.35, "IMD": directory, "IFC": 0.08, "IAM": 0.07}
            for tag, share in expected.items():
                self.assertAlmostEqual(army[tag], share)
                for resource, total in (("manpower", 70000), ("ADISCORD_economy_treasury", 750), ("ADISCORD_economy_debt", 900)):
                    self.assertAlmostEqual(values[tag][resource], total * share, msg=(tag, resource, facts))

    def test_final_handoff_restores_country_before_moving_its_resources(self):
        finish = self.effect("IVN_cw_finish")
        branch = block(block(finish, "if"), "else")
        keys = [e.key for e in branch]
        self.assertLess(keys.index("capital_scope"), keys.index("IVN_cw_transfer_reserves"))
        inherit = [e.value for e in walk(branch) if e.key == "inherit_technology"]
        self.assertEqual(inherit, ["ROOT"])

    def test_subject_captures_are_awarded_to_their_participating_overlord(self):
        source = self.effect("IVN_cw_absorb_defeated")
        sender = block(source, "FROM")
        branch = block(sender, "if")
        self.assertEqual(scalar(block(branch, "OVERLORD"), "save_event_target_as"), "IVN_cw_recipient")
        recipient = block(source, "event_target:IVN_cw_recipient")
        self.assertEqual(scalar(block(recipient, "annex_country"), "target"), "ROOT")

    def test_paid_targeted_callbacks_require_and_consume_their_receipt(self):
        closed = self.effect("IVN_cw_close_programmes")
        removed = [e.value for e in walk(closed) if e.key == "remove_decision"]
        for category in parse_clausewitz(read("common/decisions/ADISCORD_IVN_decisions.txt")):
            for decision in category.value:
                if not isinstance(decision.value, list):
                    continue
                data = {e.key: e.value for e in decision.value}
                if "days_remove" not in data or "remove_effect" not in data:
                    continue
                self.assertEqual(removed.count(decision.key), 1, decision.key)
                if data.get("state_target") != "yes":
                    continue
                receipt = "IVN_paid_" + decision.key
                for callback in ("cancel_effect", "remove_effect"):
                    if callback not in data:
                        continue
                    guard = block(block(data[callback], "if"), "limit")
                    self.assertEqual(scalar(block(guard, "FROM"), "has_variable"), receipt)
                    self.assertEqual(sum(e.key == "clear_variable" and e.value == receipt for e in walk(data[callback])), 1)

    def test_refund_scan_cannot_collect_another_participants_receipts(self):
        closed = self.effect("IVN_cw_close_programmes")
        for scan in (entry.value for entry in walk(closed) if entry.key == "every_state"):
            limit = block(scan, "limit")
            receipt = scalar(limit, "has_variable")
            payer = "IVC" if receipt.startswith("IVN_paid_IVC_") else "IVN"
            self.assertEqual(scalar(block(limit, "event_target:IVN_cw_closing_country"), "tag"), payer)

    def test_offers_recheck_both_parties_and_have_no_upfront_payment(self):
        self.assertIn("IVN_cw_offer_valid", self.triggers)
        valid = repr(self.triggers["IVN_cw_offer_valid"])
        for token in ("IVN_cw_offer_pending", "has_capitulated", "exists", "has_political_power", "IVN_marches_revolt_active"):
            self.assertIn(token, valid)
        decisions = definitions("common/decisions/ADISCORD_IVN_decisions.txt")
        self.assertIn("IVN_cw_diplomacy_category", decisions)
        offer = block(decisions["IVN_cw_diplomacy_category"], "IVN_cw_send_offer")
        self.assertEqual(scalar(offer, "cost"), "0")
        self.assertNotIn("add_political_power", {e.key for e in walk(block(offer, "complete_effect"))})
        accept = self.effect("IVN_cw_accept_offer")
        charges = [e.value for e in walk(accept) if e.key == "add_political_power"]
        self.assertEqual(charges, ["-75"])
        guard = block(block(accept, "if"), "limit")
        self.assertEqual(scalar(guard, "IVN_cw_offer_valid"), "yes")

    def test_leader_portrait_and_all_participants_registered(self):
        tags = read("common/country_tags/02_ADISCORD_ivn_tags.txt")
        for tag in TAGS[1:]:
            self.assertIn(f'{tag} = "countries/{tag}.txt"', tags)
            self.assertTrue(list((ROOT / "history/countries").glob(f"{tag} - *.txt")))
        self.assertIn("IVN_Leonid_Stalk", read("common/characters/IVN.txt"))
        self.assertIn('texturefile = "gfx/leaders/IVN/portrait_IVN_Leonid_Stalk.png"', read("interface/ADISCORD_leader_portraits.gfx"))

    def test_imperial_aggregates_preserve_sources_without_stacking(self):
        from tools.tests.test_adiscord_stp_preparation import selected_effects

        aggregate = self.effect("IVN_refresh_imperium")
        facts = {
            ("IVN", "has_dynamic_modifier", "IVN_order_dynamic"): True,
            ("IVN", "has_dynamic_modifier", "IVC_legion_dynamic"): True,
        }
        values = {"IVN_ord_attack": 0.13, "IVC_leg_attack": 0.07,
                  "IVN_ord_factory_output": 0.12, "IVC_leg_factory_output": 0.06,
                  "IVN_imp_air_efficiency": 0.05, "IVN_imp_navy_org": 0.05}
        for _ in range(3):
            selected = list(selected_effects(aggregate, facts, "IVN"))
            for _, entry in selected:
                if entry.key in ("set_variable", "add_to_variable"):
                    target = scalar(entry.value, "var")
                    source = scalar(entry.value, "value")
                    try:
                        value = float(source)
                    except ValueError:
                        value = values.get(source, 0)
                    values[target] = value if entry.key == "set_variable" else values.get(target, 0) + value
            self.assertAlmostEqual(values["IVN_imp_attack"], 0.20)
            self.assertAlmostEqual(values["IVN_imp_factory_output"], 0.18)
            self.assertAlmostEqual(values["IVN_imp_air_efficiency"], 0.05)
            self.assertAlmostEqual(values["IVN_imp_navy_org"], 0.05)
        removals = [scalar(e.value, "modifier") for _, e in selected if e.key == "remove_dynamic_modifier"]
        additions = [scalar(e.value, "modifier") for _, e in selected if e.key == "add_dynamic_modifier"]
        self.assertEqual(set(removals), {"IVN_order_dynamic", "IVC_legion_dynamic"})
        self.assertEqual(set(additions), {"IVN_exercitus_imperialis", "IVN_oeconomia_solis_nigri"})
        self.assertIn("ADISCORD_economy_mark_dirty", {e.key for _, e in selected})

    def test_postwar_focus_refreshes_select_imperial_aggregates(self):
        from tools.tests.test_adiscord_stp_preparation import selected_effects

        for tag, won in (("IVN", True), ("IVN", False), ("IVC", False)):
            facts = {(tag, "has_global_flag", "IVN_civil_war_won_by_legion"): won}
            for effect in ("IVN_refresh_order", "IVC_refresh_legion"):
                selected = list(selected_effects(self.effect(effect), facts, tag))
                self.assertEqual(sum(e.key == "IVN_refresh_imperium" for _, e in selected), int(tag == "IVN" and won))

    def test_authored_encodings(self):
        for path in (EFFECTS, TRIGGERS, EVENTS, "common/decisions/ADISCORD_IVN_decisions.txt"):
            self.assertFalse((ROOT / path).read_bytes().startswith(b"\xef\xbb\xbf"), path)
        self.assertTrue((ROOT / "localisation/russian/ADISCORD_IVN_l_russian.yml").read_bytes().startswith(b"\xef\xbb\xbf"))


if __name__ == "__main__":
    unittest.main()
