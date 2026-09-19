"""Cross-file contracts for the playable preparation, not a Clausewitz emulator."""

from pathlib import Path
import re
import unittest

from tools.validators.validate_adiscord_division_templates import parse_clausewitz


ROOT = Path(__file__).resolve().parents[2]


def entries(relative):
    path = ROOT / relative
    if not path.is_file():
        raise AssertionError(f"Missing gameplay consumer: {relative}")
    return parse_clausewitz(path.read_text(encoding="utf-8-sig"))


def block(items, name):
    found = [entry.value for entry in items if entry.key == name]
    if len(found) != 1 or not isinstance(found[0], list):
        raise AssertionError(f"Expected one block {name}")
    return found[0]


def scalar(items, name):
    found = [entry.value for entry in items if entry.key == name]
    if len(found) != 1 or isinstance(found[0], list):
        raise AssertionError(f"Expected one scalar {name}")
    return found[0]


def walk(items):
    for entry in items:
        yield entry
        if isinstance(entry.value, list):
            yield from walk(entry.value)


def matches_conditions(items, facts, scope="STP"):
    """Select parsed branches from explicit scenario facts, not a game simulation."""
    def condition_groups(children):
        index = 0
        while index < len(children):
            length = 3 if not children[index].key else 1
            yield children[index:index + length]
            index += length

    def compare(left, operator, right):
        return {">": left > right, "<": left < right, ">=": left >= right,
                "<=": left <= right, "=": left == right}[operator]
    def matches(entry):
        if entry.key == "custom_trigger_tooltip":
            return matches_conditions([child for child in entry.value if child.key != "tooltip"], facts, scope)
        if entry.key in ("AND", "hidden_trigger"):
            return matches_conditions(entry.value, facts, scope)
        if entry.key in ("owner", "controller"):
            country = facts.get((scope, entry.key))
            return country is not None and matches_conditions(entry.value, facts, country)
        if entry.key == "any_other_country":
            countries = {key[0] for key in facts if re.fullmatch(r"[A-Z]{3}", key[0])}
            return any(country != scope and facts.get((country, "exists", "yes"), False)
                       and matches_conditions(entry.value, facts, country) for country in countries)
        if entry.key == "any_owned_state":
            extras = [e for e in entry.value if e.key != "is_controlled_by"]
            if not any(e.key == "is_controlled_by" and e.value == "PREV" for e in entry.value):
                raise AssertionError("Unsupported owned-state fixture")
            owned = any(key[0] == scope and key[1] == "owns_state" and owned
                        and facts.get((scope, "controls_state", key[2]), False)
                        for key, owned in facts.items())
            return owned and (not extras or matches_conditions(extras, facts, scope))
        if entry.key == "OR":
            return any(matches_conditions(group, facts, scope) for group in condition_groups(entry.value))
        if entry.key == "NOT":
            return not any(matches_conditions(group, facts, scope) for group in condition_groups(entry.value))
        if re.fullmatch(r"[A-Z]{3}|\d+|ROOT|FROM|STP_Edmund_Ravel|STP_maksim_shabrat", entry.key) and isinstance(entry.value, list):
            return matches_conditions(entry.value, facts, "STP" if entry.key == "ROOT" else entry.key)
        if entry.key == "power_balance_value":
            balance = scalar(entry.value, "id")
            comparison = [child.value for child in entry.value if not child.key]
            if len(comparison) != 3 or comparison[0] != "value" or comparison[1] not in ("<", ">"):
                raise AssertionError(f"Unsupported BOP comparison: {comparison}")
            return compare(facts[(scope, "power_balance_value", balance)], comparison[1], float(comparison[2]))
        if entry.key == "has_dynamic_modifier":
            modifier = scalar(entry.value, "modifier") if isinstance(entry.value, list) else entry.value
            return facts.get((scope, "has_dynamic_modifier", modifier), False)
        if entry.key == "has_country_leader":
            if scalar(entry.value, "ruling_only") != "yes" or {e.key for e in entry.value} != {"character", "ruling_only"}:
                raise AssertionError("Only an explicit ruling character is supported in this fixture")
            return facts.get((scope, "ruling_leader")) == scalar(entry.value, "character")
        if entry.key == "has_equipment":
            equipment, operator, amount = (child.value for child in entry.value)
            return compare(facts.get((scope, "equipment", equipment), 0), operator, float(amount))
        if entry.key == "stockpile_ratio":
            equipment = scalar(entry.value, "archetype")
            field, operator, amount = (child.value for child in entry.value if not child.key)
            if field != "ratio":
                raise AssertionError(f"Unsupported stockpile comparison: {field}")
            return compare(facts[(scope, "stockpile_ratio", equipment)], operator, float(amount))
        if entry.key in ("has_global_flag", "has_country_flag", "has_state_flag") and isinstance(entry.value, list):
            flag = scalar(entry.value, "flag")
            comparison = [child.value for child in entry.value if not child.key]
            if len(comparison) != 3 or comparison[:2] != ["days", ">"]:
                raise AssertionError(f"Unsupported flag-age comparison: {comparison}")
            return (facts.get((scope, entry.key, flag), False)
                    and facts.get((scope, "flag_days", flag), 0) > int(comparison[2]))
        if entry.key == "tag":
            return scope == entry.value
        if entry.key == "state":
            return scope == entry.value
        if entry.key == "check_variable":
            value = facts.get((scope, "variable", scalar(entry.value, "var")), 0)
            operator = {"greater_than": ">", "greater_than_or_equals": ">=", "less_than": "<",
                        "less_than_or_equals": "<=", "equals": "="}[scalar(entry.value, "compare")]
            reference = scalar(entry.value, "value")
            try:
                threshold = float(reference)
            except ValueError:
                threshold = facts.get((scope, "variable", reference), 0)
            return compare(value, operator, threshold)
        if entry.key == "always":
            return entry.value == "yes"
        if isinstance(entry.value, list):
            raise AssertionError(f"Unsupported scenario condition: {entry.key}")
        if entry.key in ("has_war_with", "is_in_faction_with"):
            # These engine relations are symmetric; each fixture records one edge.
            return facts.get((scope, entry.key, entry.value), facts.get((entry.value, entry.key, scope), False))
        return facts.get((scope, entry.key, entry.value), False)
    results = []
    index = 0
    while index < len(items):
        entry = items[index]
        if not entry.key:
            name, operator, value = (e.value for e in items[index:index + 3])
            results.append(compare(facts.get((scope, "numeric", name), 0), operator, float(value)))
            index += 3
        else:
            results.append(matches(entry))
            index += 1
    return all(results)


def selected_effects(items, facts, scope="STP"):
    """Keep country scope and the actual if/else selection for contract checks."""
    taken = False
    for entry in items:
        if entry.key == "effect_tooltip":
            continue
        if entry.key in ("if", "else_if", "else"):
            if entry.key == "if":
                taken = False
            if not taken and (entry.key == "else" or matches_conditions(block(entry.value, "limit"), facts, scope)):
                taken = True
                yield from selected_effects([e for e in entry.value if e.key != "limit"], facts, scope)
        elif entry.key == "hidden_effect":
            yield from selected_effects(entry.value, facts, scope)
        elif entry.key == "for_loop_effect":
            # Literal bounded deployment loops, using the documented defaults
            # start=0/end exclusive/add=1. Reject unsupported forms explicitly.
            controls = {e.key: e.value for e in entry.value if e.key in ("start", "end", "add", "compare", "value")}
            if set(controls) != {"end", "value"}:
                raise AssertionError(f"Unsupported deployment loop: {controls}")
            count = int(controls["end"])
            if not 0 <= count <= 64:
                raise AssertionError(f"Unbounded deployment loop: {count}")
            for _ in range(count):
                yield from selected_effects([e for e in entry.value if e.key not in controls], facts, scope)
        elif entry.key == "faction_leader":
            yield from selected_effects(entry.value, facts, facts[(scope, "faction_leader")])
        elif re.fullmatch(r"[A-Z]{3}|\d+|ROOT|FROM", entry.key) and isinstance(entry.value, list):
            yield from selected_effects(entry.value, facts, "STP" if entry.key == "ROOT" else entry.key)
        else:
            yield scope, entry


class StelanderPreparationTests(unittest.TestCase):
    def test_ai_preserves_electoral_mandate_and_paid_work_before_early_uprising(self):
        decisions = block(entries("common/decisions/ADISCORD_STP_decisions.txt"), "STP_battle_for_stelander")
        weights = block(block(decisions, "STP_cw_start_uprising"), "ai_will_do")
        for busy, mandate, paid, free in ((True, .1, False, 2), (False, .1, False, 2),
                                         (True, .1001, False, 2), (True, -.2, True, 2),
                                         (True, -.2, False, 1)):
            facts = {("STP", "STP_cw_nod_busy_in_north", "yes"): busy,
                     ("STP", "power_balance_value", "STP_shabrat_election_legitimacy"): mandate,
                     ("STP", "has_country_flag", "STP_cw_assault_training_reserved"): paid,
                     ("STP", "variable", "STP_political_action_slots_available"): free,
                     ("STP", "variable", "STP_political_action_slots_total"): 2}
            weight = float(scalar(weights, "base"))
            for modifier in (e.value for e in weights if e.key == "modifier"):
                if matches_conditions([e for e in modifier if e.key != "factor"], facts):
                    weight *= float(scalar(modifier, "factor"))
            self.assertEqual(weight > 0, busy and mandate <= .1 and not paid and free == 2)

    def test_ai_recruitment_keeps_people_and_rifles_for_field_replacements(self):
        decisions = block(entries("common/decisions/ADISCORD_STP_decisions.txt"), "STP_cw_war_council")
        for name, threshold in (("STP_cw_raise_territorial_brigade", 18000),
                                ("STP_cw_train_reserve_brigades", 24000)):
            stop = block(block(block(decisions, name), "ai_will_do"), "modifier")
            for manpower, reserve, expected in ((threshold, .1001, False), (threshold - .01, .2, True),
                                               (threshold * 2, .1, True), (threshold * 2, -.2, True)):
                facts = {("STP", "numeric", "has_manpower"): manpower,
                         ("STP", "stockpile_ratio", "infantry_equipment"): reserve}
                self.assertEqual(matches_conditions([e for e in stop if e.key != "factor"], facts), expected,
                                 (name, manpower, reserve))

    def test_territorial_ai_targets_cover_northern_armies_without_downgrading_stp(self):
        roles = entries("common/ai_templates/ADISCORD_land_templates.txt")
        militia = block(roles, "ADISCORD_territorial_templates")
        garrison = block(block(roles, "ADISCORD_garrison_templates"), "ADISCORD_garrison_levy")
        targets = [(e.key, e.value) for e in militia if isinstance(e.value, list)
                   and any(v.key == "target_template" for v in e.value)]
        for tag in ("STP", "STS", "SRP", "ZAO", "WPA", "WPS", "PWR", "PSD",
                    "NOD", "YPR", "COF", "TFF", "VAL"):
            for war in (False, True):
                facts = {(tag, "is_ai", "yes"): True, (tag, "has_war", "yes"): war,
                         (tag, "has_global_flag", "STP_cw_started"): war,
                         (tag, "has_global_flag", "ADISCORD_vorkerland_collapse_wars_started"): war}
                eligible = [target for _, target in targets if matches_conditions(block(target, "enable"), facts, tag)]
                self.assertEqual(len(eligible), int(war), (tag, war))
                self.assertEqual(matches_conditions(block(garrison, "enable"), facts, tag), not war)
                if war:
                    battalions = block(block(eligible[0], "target_template"), "regiments")
                    if tag in ("STP", "STS", "SRP"):
                        self.assertEqual(scalar(battalions, "ADISCORD_territorial"), "6")
                    else:
                        self.assertEqual(scalar(battalions, "ADISCORD_militia"),
                                         "3" if tag in ("NOD", "YPR", "COF", "TFF", "VAL") else "4")
        after_union = {("SRP", "is_ai", "yes"): True, ("SRP", "has_war", "yes"): True,
                       ("SRP", "has_global_flag", "STP_cw_started"): True,
                       ("SRP", "has_global_flag", "STP_cw_union_wars_finished"): True}
        eligible = [target for _, target in targets if matches_conditions(block(target, "enable"), after_union, "SRP")]
        self.assertEqual(len(eligible), 1, "the separate VAL war survives the STP peace")
        self.assertFalse(matches_conditions(block(garrison, "enable"), after_union, "SRP"))
        strategy = block(entries("common/ai_strategy/ADISCORD_STP_civil_war.txt"), "STP_cw_territorial_army")
        self.assertTrue(matches_conditions(block(strategy, "enable"), after_union, "SRP"))

    def test_nod_category_status_prioritizes_closed_routes_over_northern_war(self):
        texts = next(e.value for e in entries("common/scripted_localisation/ADISCORD_STP_scripted_loc.txt")
                     if e.key == "defined_text" and scalar(e.value, "name") == "STPGetNodStatus")
        scenarios = [({}, "northern_war"),
                     ({("NOD", "has_country_flag", "NOD_cw_refused"): True}, "neutral"),
                     ({("NOD", "has_country_flag", "NOD_cw_defeated"): True}, "closed"),
                     ({("STP", "has_global_flag", "STP_cw_union_wars_finished"): True}, "closed")]
        for extra, expected in scenarios:
            facts = {("STP", "STP_cw_nod_busy_in_north", "yes"): True, **extra}
            selected = next(e.value for e in texts if e.key == "text" and
                            (not any(t.key == "trigger" for t in e.value) or
                             matches_conditions(block(e.value, "trigger"), facts)))
            self.assertEqual(scalar(selected, "localization_key"), "STP_nod_status_" + expected)

    def test_kefreyt_volunteers_are_paid_earmarked_and_not_split_with_party_reserves(self):
        effects = entries("common/scripted_effects/ADISCORD_STP_scripted_effects.txt")
        reserve = block(block(effects, "STP_cw_reserve_kefreyt_volunteers"), "if")
        settlement = next(e.value for e in reserve if e.key == "if")
        delivered = block(block(settlement, "else"), "STP")
        self.assertEqual(scalar(delivered, "set_country_flag"), "STP_cw_kefreyt_shipment_received")
        self.assertEqual(scalar(block(delivered, "country_event"), "id"), "ADISCORD_STP_preparation.8")
        ledger_gate = block(block(settlement, "limit"), "1")
        self.assertFalse(matches_conditions(ledger_gate, {}, "1"))
        self.assertFalse(matches_conditions(ledger_gate, {("1", "variable", "STP_cw_kefreyt_volunteers"): 2}, "1"))
        self.assertTrue(matches_conditions(ledger_gate, {("1", "variable", "STP_cw_kefreyt_volunteers"): 3}, "1"))
        materialize = block(block(effects, "STP_cw_materialize_region_assets"), "if")
        self.assertEqual(sum(e.key == "STP_cw_deploy_kefreyt_volunteers" for e in materialize), 1)
        self.assertFalse(any(e.key == "add_manpower" for e in walk(materialize)))
        start = block(block(effects, "STP_cw_start"), "if")
        last_split = max(e.line for e in walk(start) if e.key == "transfer_units_fraction")
        delivery = next(e for e in walk(start) if e.key == "STP_cw_materialize_region_assets")
        self.assertLess(last_split, delivery.line, "foreign formations must not enter the shared percentage split")

    def test_kefreyt_consent_is_available_without_stocks_and_queues_only_once(self):
        event = next(e.value for e in entries("events/ADISCORD_STP_events.txt")
                     if e.key == "country_event" and scalar(e.value, "id") == "ADISCORD_STP_preparation.6")
        options = [e.value for e in event if e.key == "option"]
        accept = next(o for o in options if scalar(o, "name").endswith(".6.a"))
        refuse = next(o for o in options if scalar(o, "name").endswith(".6.b"))
        facts = {("VAL", "STP_cw_kefreyt_aid_open", "yes"): True}
        self.assertTrue(matches_conditions(block(accept, "trigger"), facts, "VAL"))
        accepted = block(block(accept, "hidden_effect"), "if")
        self.assertEqual(scalar(accepted, "set_country_flag"), "VAL_cw_volunteers_pending")
        facts[("VAL", "has_country_flag", "VAL_cw_volunteers_pending")] = True
        self.assertFalse(matches_conditions(block(accepted, "limit"), facts, "VAL"))
        self.assertEqual((scalar(block(accept, "ai_chance"), "factor"),
                          scalar(block(refuse, "ai_chance"), "factor")), ("99", "1"))
        callbacks = [e.value for e in walk(accepted) if e.key == "country_event"
                     and scalar(e.value, "id") == "ADISCORD_STP_preparation.22"]
        self.assertEqual(len(callbacks), 1)
        self.assertEqual(scalar(callbacks[0], "days"), "14")

    def test_kefreyt_delivery_requires_every_full_price_and_preserves_fractional_boundaries(self):
        condition = block(entries("common/scripted_triggers/ADISCORD_STP_scripted_triggers.txt"),
                          "STP_cw_can_fund_kefreyt_volunteers")
        prices = {"infantry_equipment": 1830, "ADISCORD_squad_weapons_equipment": 144,
                  "support_equipment": 90, "artillery_equipment": 180, "anti_air_equipment": 60}
        facts = {("VAL", "equipment", key): value for key, value in prices.items()}
        facts[("VAL", "numeric", "has_manpower")] = 23700
        self.assertTrue(matches_conditions(condition, facts, "VAL"))
        for key, value in facts.items():
            with self.subTest(resource=key):
                self.assertFalse(matches_conditions(condition, {**facts, key: value - 0.25}, "VAL"))
        self.assertFalse(matches_conditions(condition, {}, "VAL"))

    def test_kefreyt_pending_offer_follows_resistance_and_stops_after_settlement(self):
        trigger = block(entries("common/scripted_triggers/ADISCORD_STP_scripted_triggers.txt"),
                        "STP_cw_kefreyt_aid_open")
        donor = {("VAL", "exists", "yes"): True, ("VAL", "has_capitulated", "no"): True}
        before = {**donor, ("STP", "exists", "yes"): True,
                  ("STP", "has_capitulated", "no"): True,
                  ("STP", "has_country_flag", "STP_sided_with_Maksim_flag"): True}
        self.assertTrue(matches_conditions(trigger, before, "VAL"))
        during = {**donor, ("VAL", "has_global_flag", "STP_cw_started"): True,
                  ("STS", "exists", "yes"): True, ("STS", "has_capitulated", "no"): True,
                  ("STS", "has_country_flag", "STP_cw_participant"): True}
        self.assertTrue(matches_conditions(trigger, during, "VAL"))
        for change in ({("VAL", "has_global_flag", "STP_cw_union_wars_finished"): True},
                       {("STS", "has_country_flag", "STP_cw_kefreyt_shipment_received"): True},
                       {("STS", "has_war_with", "VAL"): True},
                       {("STS", "has_capitulated", "no"): False}):
            self.assertFalse(matches_conditions(trigger, {**during, **change}, "VAL"))
        effects = entries("common/scripted_effects/ADISCORD_STP_scripted_effects.txt")
        reserve = block(block(effects, "STP_cw_reserve_kefreyt_volunteers"), "if")
        success = next(e.value for e in reserve if e.key == "if")
        wartime = block(success, "if")
        self.assertEqual(scalar(block(wartime, "STS"), "set_country_flag"), "STP_cw_kefreyt_shipment_received")
        self.assertEqual(scalar(block(wartime, "1"), "STP_cw_deploy_kefreyt_volunteers"), "yes")
        self.assertEqual(scalar(success, "clr_country_flag"), "VAL_cw_volunteers_pending")
        finish = block(block(effects, "STP_cw_check_union_wars_finished"), "if")
        self.assertEqual(scalar(block(finish, "VAL"), "clr_country_flag"), "VAL_cw_volunteers_pending")

    def test_kefreyt_retry_does_not_repeat_after_delivery_or_cancelled_agreement(self):
        event = next(e.value for e in entries("events/ADISCORD_STP_events.txt")
                     if e.key == "country_event" and scalar(e.value, "id") == "ADISCORD_STP_preparation.22")
        facts = {("VAL", "has_country_flag", "VAL_cw_volunteers_pending"): True,
                 ("VAL", "STP_cw_kefreyt_aid_open", "yes"): True}
        self.assertTrue(matches_conditions(block(event, "trigger"), facts, "VAL"))
        facts[("VAL", "has_country_flag", "VAL_cw_volunteers_pending")] = False
        self.assertFalse(matches_conditions(block(event, "trigger"), facts, "VAL"))
        immediate = block(event, "immediate")
        self.assertEqual(scalar(block(immediate, "else"), "clr_country_flag"), "VAL_cw_volunteers_pending")
        repeated = list(selected_effects(immediate, {}, "VAL"))
        self.assertFalse(any(e.key == "country_event" for _, e in repeated))

    def test_completed_val_route_leaves_one_safe_close_option_on_an_open_offer(self):
        triggers = entries("common/scripted_triggers/ADISCORD_STP_scripted_triggers.txt")
        committed_id = "VAL_cw_route_focus_completed"
        committed = next((e.value for e in triggers if e.key == committed_id), None)
        events = entries("events/ADISCORD_STP_events.txt")
        offer = next(e.value for e in events if e.key == "country_event"
                     and scalar(e.value, "id") == "ADISCORD_STP_cw.20")
        options = [e.value for e in offer if e.key == "option"]
        neutral = next(o for o in options if scalar(o, "name") == "ADISCORD_STP_cw.20.b")
        focus_ids = {"VAL_Arms_For_The_Burning", "VAL_Seize_The_Northern_Passes", "VAL_Keep_The_Arsenals"}
        focuses = {scalar(e.value, "id"): e.value for e in walk(entries("common/national_focus/ADISCORD_national_focus_VAL.txt"))
                   if e.key == "focus" and isinstance(e.value, list) and scalar(e.value, "id") in focus_ids}
        base = {("VAL", "exists", "yes"): True, ("VAL", "has_global_flag", "STP_cw_started"): True,
                ("VAL", "has_capitulated", "no"): True, ("VAL", "has_war", "no"): True,
                ("VAL", "is_subject", "no"): True, ("VAL", "is_in_faction", "no"): True,
                ("VAL", "is_neighbor_of", "SRP"): True,
                ("SRP", "exists", "yes"): True, ("SRP", "has_capitulated", "no"): True,
                ("SRP", "has_war", "no"): True, ("SRP", "is_subject", "no"): True,
                ("SRP", "is_in_faction", "no"): True,
                ("STS", "exists", "yes"): True, ("STS", "has_capitulated", "no"): True,
                ("STS", "has_war_with", "STP"): True}
        def resolve(facts):
            facts = dict(facts)
            facts[("VAL", committed_id, "yes")] = committed is not None and matches_conditions(committed, facts, "VAL")
            facts[("VAL", "VAL_cw_external_course_available", "yes")] = matches_conditions(
                block(triggers, "VAL_cw_external_course_available"), facts, "VAL")
            return facts
        def visible(facts):
            return [o for o in options if not any(e.key == "trigger" for e in o)
                    or matches_conditions(block(o, "trigger"), facts, "VAL")]
        self.assertEqual({scalar(o, "name") for o in visible(resolve(base))},
                         {"ADISCORD_STP_cw.20.a", "ADISCORD_STP_cw.20.b", "ADISCORD_STP_cw.20.c"})
        self.assertEqual(set(focuses), focus_ids)
        for focus_id, focus in focuses.items():
            completed = dict(base)
            for scope, effect in selected_effects(block(focus, "completion_reward"), completed, "VAL"):
                if effect.key == "set_country_flag" and not isinstance(effect.value, list):
                    completed[(scope, "has_country_flag", effect.value)] = True
            completed[("VAL", "has_completed_focus", focus_id)] = True
            for busy in (False, True):
                facts = resolve({**completed, ("VAL", "has_country_flag", "VAL_foreign_operation_active"): busy})
                with self.subTest(focus=focus_id, busy=busy, phase="open card"):
                    available = visible(facts)
                    self.assertEqual([scalar(o, "name") for o in available], ["ADISCORD_STP_cw.20.committed"])
                    for option in available:
                        payload = [e for e in option if e.key not in ("name", "trigger", "ai_chance")]
                        self.assertEqual(list(selected_effects(payload, facts, "VAL")), [], "closing preserves the earned route")
                with self.subTest(focus=focus_id, busy=busy, phase="old neutral payload"):
                    self.assertEqual(list(selected_effects(block(neutral, "hidden_effect"), facts, "VAL")), [],
                                     "an old neutral response must not revoke a completed focus")
        self.assertIsNotNone(committed)
        self.assertEqual({e.value for e in walk(committed) if e.key == "has_completed_focus"}, focus_ids)
        self.assertFalse(any(e.key == "has_country_flag" for e in walk(committed)), "focus completion is the authoritative fact")

    def test_val_trade_offer_rechecks_a_neutral_focus_completed_while_open(self):
        events = entries("events/ADISCORD_STP_events.txt")
        offer = next(e.value for e in events if e.key == "country_event"
                     and scalar(e.value, "id") == "ADISCORD_STP_cw.20")
        trade = next(e.value for e in offer if e.key == "option"
                     and scalar(e.value, "name") == "ADISCORD_STP_cw.20.c")
        tree = entries("common/national_focus/ADISCORD_national_focus_VAL.txt")
        neutral = next(e.value for e in walk(tree) if e.key == "focus" and isinstance(e.value, list)
                       and scalar(e.value, "id") == "VAL_Keep_The_Arsenals")
        eligible = {("STS", "exists", "yes"): True,
                    ("STS", "has_capitulated", "no"): True,
                    ("STS", "has_war_with", "STP"): True}
        after_neutral_focus = dict(eligible)
        for scope, effect in selected_effects(block(neutral, "completion_reward"), eligible, "VAL"):
            if effect.key == "set_country_flag" and not isinstance(effect.value, list):
                after_neutral_focus[(scope, "has_country_flag", effect.value)] = True
        self.assertTrue(after_neutral_focus[("VAL", "has_country_flag", "VAL_cw_refused")])
        scenarios = (("eligible", eligible, True),
                     ("neutral focus completed", after_neutral_focus, False),
                     ("military selected", {**eligible, ("VAL", "has_country_flag", "VAL_cw_military_course"): True}, False),
                     ("resistance gone", {**eligible, ("STS", "exists", "yes"): False}, False),
                     ("resistance capitulated", {**eligible, ("STS", "has_capitulated", "no"): False}, False),
                     ("civil war ended", {**eligible, ("STS", "has_war_with", "STP"): False}, False),
                     ("buyer became enemy", {**eligible, ("STS", "has_war_with", "VAL"): True}, False))
        for name, facts, expected in scenarios:
            with self.subTest(scenario=name, phase="visible option"):
                self.assertEqual(matches_conditions(block(trade, "trigger"), facts, "VAL"), expected)
            with self.subTest(scenario=name, phase="stale executable response"):
                effects = list(selected_effects(block(trade, "hidden_effect"), facts, "VAL"))
                self.assertEqual(any(scope == "VAL" and e.key == "set_country_flag"
                                     and e.value == "VAL_cw_trade_course" for scope, e in effects), expected)
                if not expected:
                    self.assertEqual(effects, [], "a stale offer must not change the course or the republics")

    def test_nectar_native_events_preserve_every_paragraph_without_a_timer(self):
        import hashlib
        loc_path = ROOT / "localisation/russian/ADISCORD_STP_l_russian.yml"
        self.assertTrue(loc_path.read_bytes().startswith(b"\xef\xbb\xbf"))
        values = dict(re.findall(r'^ ([\w.]+):\s*"(.*)"$', loc_path.read_text(encoding="utf-8-sig"), re.M))
        events = {scalar(e.value, "id"): e.value for e in entries("events/ADISCORD_STP_events.txt")
                  if e.key == "country_event"}
        tree = next(e.value for e in entries("common/national_focus/ADISCORD_national_focus_STP.txt")
                    if e.key == "focus_tree" and scalar(e.value, "id") == "STP_focus")
        focuses = {scalar(e.value, "id"): e.value for e in tree if e.key == "focus"}
        chapters = []
        for focus, number in (("STP_NECTAR_OF_GODS", 15), ("STP_2160_budget", 16)):
            event_id = f"ADISCORD_STP_preparation.{number}"
            call = block(block(focuses[focus], "completion_reward"), "country_event")
            self.assertEqual([(e.key, e.value) for e in call], [("id", event_id)])
            event = events[event_id]
            self.assertFalse(any(e.key in ("hidden", "fire_only_once") for e in event))
            self.assertEqual(scalar(event, "picture"), "GFX_event_adiscord_nectar_of_the_gods")
            self.assertIn(scalar(event, "title"), values)
            self.assertTrue(matches_conditions(block(event, "trigger"), {}))
            self.assertFalse(matches_conditions(block(event, "trigger"), {}, "VAL"))
            self.assertFalse(matches_conditions(block(event, "trigger"),
                             {("STP", "has_global_flag", "STP_cw_started"): True}))
            text = values[scalar(event, "desc")]
            chapters.append(text)
            rendered = text.replace(r"\n", "\n")
            self.assertLessEqual(len(rendered), 3000)
            self.assertLessEqual(len(rendered.encode("utf-8")), 5500)
            self.assertEqual([(e.key, e.value) for e in block(event, "immediate")],
                             [("clear_variable", "STP_nectar_story_page")])
            option = block(event, "option")
            self.assertIn(scalar(option, "name"), values)
            self.assertEqual(len(option), 1, "closing must not schedule another event or settle focus rewards")
        self.assertEqual(hashlib.sha256(r"\n\n".join(chapters).encode("utf-8")).hexdigest(),
                         "b87894acba07ebab1224274870aef30f77c8c13f2591cce43785dd665a39f8ba")
        self.assertEqual(scalar(block(focuses["STP_NECTAR_OF_GODS"], "completion_reward"), "add_political_power"), "35")
        self.assertEqual(scalar(block(focuses["STP_2160_budget"], "completion_reward"), "STP_receive_1200"), "yes")
        for path in ("interface/ADISCORD_STP_regions.gui", "common/scripted_guis/ADISCORD_STP_regions_scripted_gui.txt"):
            self.assertNotIn("ADISCORD_STP_nectar_story", (ROOT / path).read_text(encoding="utf-8-sig"))
        self.assertFalse(any(key.startswith("STP_nectar_") for key in values))

    def test_regional_preparation_appears_after_its_focus_and_restores_lost_assets(self):
        decisions = block(entries("common/decisions/ADISCORD_STP_decisions.txt"), "STP_battle_for_stelander")
        tree = next(e.value for e in entries("common/national_focus/ADISCORD_national_focus_STP.txt")
                    if e.key == "focus_tree" and scalar(e.value, "id") == "STP_focus")
        focuses = {scalar(e.value, "id"): e.value for e in tree if e.key == "focus"}
        specs = {
            "STP_cw_raise_district_network": ("STP_Count_The_Loyalists", None, None),
            "STP_recruit_regional_official": ("STP_Call_For_Shabrat", None, "STP_resistance_administration_asset"),
            "STP_bargain_with_local_councils": ("STP_cw_local_council_envoys", None, "STP_local_deal_asset"),
            "STP_region_unique_operation_2": ("STP_cw_officer_contacts", None, "STP_resistance_garrison_asset"),
            "STP_region_unique_operation_29": ("STP_cw_officer_contacts", None, "STP_resistance_garrison_asset"),
            "STP_region_unique_operation_3": ("STP_cw_port_budget", None, "STP_resistance_supply_asset"),
            "STP_region_unique_operation_46": ("STP_cw_supply_officers", None, "STP_resistance_supply_asset"),
            "STP_region_unique_operation_53": ("STP_cw_officer_contacts", None, "STP_resistance_sabotage_asset"),
            "STP_cw_sabotage_capital": ("STP_cw_prepare_capital_sabotage", None, "STP_resistance_sabotage_asset"),
            "STP_cw_sabotage_party_industry": ("STP_cw_prepare_industry_sabotage", None, "STP_resistance_sabotage_asset"),
            "STP_cw_agree_with_commander": ("STP_PARTY_DISCIPLINE", None, "STP_party_reinforced_garrison_asset"),
            "STP_cw_check_district_command": ("STP_PARTY_DISCIPLINE", None, None),
        }
        facts = {("STP", "has_country_flag", "STP_sided_with_Maksim_flag"): True,
                 ("STP", "has_country_flag", "STP_sided_with_the_party_flag"): True,
                 ("STP", "has_country_flag", "STP_battle_for_stelander_active"): True,
                 ("STP", "STP_cw_preparation_open", "yes"): True,
                 ("FROM", "is_owned_by", "ROOT"): True,
                 ("FROM", "STP_region_is_operable", "yes"): True,
                 ("FROM", "STP_region_resistance_leaning", "yes"): True}
        for decision_id, (focus_id, flag, asset) in specs.items():
            with self.subTest(decision=decision_id):
                visible = block(block(decisions, decision_id), "visible")
                self.assertFalse(matches_conditions(visible, facts), "future operations should not crowd the map")
                unlocked = {**facts, ("STP", "has_completed_focus", focus_id): True}
                if flag:
                    unlocked[("STP", "has_country_flag", flag)] = True
                self.assertTrue(matches_conditions(visible, unlocked), "a lack of money or a free slot must disable, not hide, an unlocked action")
                if asset:
                    self.assertFalse(matches_conditions(visible, {**unlocked, ("FROM", "has_state_flag", asset): True}))
                    self.assertTrue(matches_conditions(visible, {**unlocked, ("FROM", "has_state_flag", asset): False}))
                target = block(block(decisions, decision_id), "target_trigger")
                for operable in (True, False):
                    current = {**unlocked, ("FROM", "STP_region_is_operable", "yes"): operable}
                    self.assertEqual(matches_conditions(target, current), matches_conditions(target, unlocked),
                                     "daily target caching must not retain an expired local restriction")
                reward = block(focuses[focus_id], "completion_reward")
                self.assertIn(decision_id, {e.value for e in reward if e.key == "unlock_decision_tooltip"})

    def test_native_focus_completion_owns_the_three_persistent_unlocks(self):
        trees = [e.value for e in entries("common/national_focus/ADISCORD_national_focus_STP.txt") if e.key == "focus_tree"]
        focuses = {scalar(e.value, "id"): e.value for tree in trees for e in tree if e.key == "focus"}
        marker_focus = {
            "STP_cw_headquarters_ready": "STP_Call_For_Shabrat",
            "STP_cw_garrison_program": "STP_cw_officer_contacts",
            "STP_cw_recruitment_program": "STP_cw_mobilization_register",
        }
        prewar = {("STP", "STP_cw_preparation_open", "yes"): True,
                  ("STP", "has_country_flag", "STP_sided_with_Maksim_flag"): True}
        headquarters = block(focuses["STP_THE_MOUNTAIN_WINDOW"], "available")
        self.assertTrue(matches_conditions(headquarters, {**prewar, ("STP", "STP_cw_nod_busy_in_north", "yes"): True}),
                        "the military route must not require the separate political headquarters")
        self.assertNotIn(("has_completed_focus", "STP_Call_For_Shabrat"),
                         [(e.key, e.value) for e in walk(headquarters)])
        self.assertEqual(scalar(block(focuses["STP_THE_MOUNTAIN_WINDOW"], "prerequisite"), "focus"),
                         "STP_Garrisons_Hesitate")
        regions = block(entries("common/decisions/ADISCORD_STP_decisions.txt"), "STP_battle_for_stelander")
        district = {**prewar, ("FROM", "STP_region_is_operable", "yes"): True,
                    ("FROM", "is_owned_by", "ROOT"): True, ("STP", "STP_has_political_action_slot", "yes"): True}
        for operation in ("STP_region_unique_operation_2", "STP_region_unique_operation_29"):
            gate = block(block(regions, operation), "available")
            self.assertFalse(matches_conditions(gate, district))
            self.assertTrue(matches_conditions(gate, {**district, ("STP", "has_completed_focus", "STP_cw_officer_contacts"): True}))
        war_tree = next(tree for tree in trees if scalar(tree, "id") == "STP_cw_focus")
        self.assertIn("STP_cw_mobilization_register", {scalar(e.value, "id") for e in war_tree if e.key == "focus"},
                      "the post-split unlock belongs to the current war tree, not discarded prewar history")
        war_decisions = next(e.value for e in entries("common/decisions/ADISCORD_STP_decisions.txt")
                             if isinstance(e.value, list) and any(d.key == "STP_cw_raise_territorial_brigade" for d in e.value))
        recruitment = block(block(war_decisions, "STP_cw_raise_territorial_brigade"), "available")
        for tag, state in (("STP", "28"), ("STS", "1"), ("SRP", "43")):
            resources = {(tag, "numeric", "has_manpower"): 6000, (tag, "equipment", "infantry_equipment"): 600,
                         (tag, "owns_state", state): True, (tag, "controls_state", state): True}
            self.assertFalse(matches_conditions(recruitment, resources, tag))
            unlocked = {**resources, (tag, "has_completed_focus", "STP_cw_mobilization_register"): True}
            self.assertTrue(matches_conditions(recruitment, unlocked, tag))
            self.assertFalse(matches_conditions(recruitment, {**unlocked, (tag, "equipment", "infantry_equipment"): 599.5}, tag),
                             "replacing the unlock marker must preserve the actual equipment requirement")
        for marker, focus in marker_focus.items():
            with self.subTest(marker=marker):
                reward = block(focuses[focus], "completion_reward")
                self.assertFalse(any(e.key == "set_country_flag" and e.value == marker for e in walk(reward)))
                self.assertFalse(any(e.key == "hidden_effect" and e.value == [] for e in walk(reward)))

    def test_administration_follows_local_support_and_livonin_keeps_its_early_agreement(self):
        decisions = block(entries("common/decisions/ADISCORD_STP_decisions.txt"), "STP_battle_for_stelander")
        recruit = block(decisions, "STP_recruit_regional_official")
        self.assertEqual({e.value for e in block(recruit, "targets")}, {"2", "3", "29", "46", "53"})
        facts = {("STP", "has_country_flag", "STP_sided_with_Maksim_flag"): True,
                 ("STP", "has_country_flag", "STP_battle_for_stelander_active"): True,
                 ("STP", "has_completed_focus", "STP_Call_For_Shabrat"): True,
                 ("FROM", "STP_region_is_operable", "yes"): True}
        self.assertFalse(matches_conditions(block(recruit, "visible"), facts))
        self.assertTrue(matches_conditions(block(recruit, "visible"), {**facts, ("FROM", "STP_region_resistance_leaning", "yes"): True}))
        livonin = block(decisions, "STP_region_unique_operation_45")
        self.assertEqual({e.value for e in block(livonin, "targets")}, {"45"})
        self.assertTrue(matches_conditions(block(livonin, "visible"), {**facts, ("FROM", "has_state_flag", "STP_local_deal_asset"): True}))
        self.assertFalse(matches_conditions(block(livonin, "visible"), facts))
        self.assertFalse(any(e.key == "has_completed_focus" for e in walk(block(livonin, "visible"))), "the local agreement must remain an early route, not require late administration")

    def test_inspection_responses_reuse_targets_cached_before_commission_starts(self):
        decisions = block(entries("common/decisions/ADISCORD_STP_decisions.txt"), "STP_battle_for_stelander")
        before = {("STP", "has_country_flag", "STP_sided_with_Maksim_flag"): True,
                  ("STP", "STP_cw_preparation_open", "yes"): True,
                  ("STP", "has_completed_focus", "STP_Call_For_Shabrat"): True,
                  ("STP", "has_completed_focus", "STP_cw_national_mandate"): True,
                  ("STP", "has_completed_focus", "STP_cw_officer_contacts"): True,
                  ("FROM", "STP_region_is_operable", "yes"): True,
                  ("FROM", "is_owned_by", "ROOT"): True,
                  ("FROM", "is_controlled_by", "ROOT"): True,
                  ("FROM", "has_state_flag", "STP_resistance_administration_asset"): True,
                  ("FROM", "has_state_flag", "STP_resistance_garrison_asset"): True}
        for name in ("STP_cw_sacrifice_local_contact", "STP_cw_open_civil_registers", "STP_cw_evacuate_garrison_officers"):
            with self.subTest(decision=name):
                action = block(decisions, name)
                cached_target = matches_conditions(block(action, "target_trigger"), before)
                self.assertTrue(cached_target, "owned target must exist before the commission")
                visible = block(action, "visible")
                self.assertFalse(matches_conditions(visible, before))
                commission = {**before, ("FROM", "has_state_flag", "STP_party_inspection_active"): True}
                self.assertTrue(cached_target and matches_conditions(visible, commission))
                self.assertFalse(cached_target and matches_conditions(visible, before))
                self.assertFalse(matches_conditions(block(action, "target_trigger"), {**before, ("FROM", "is_owned_by", "ROOT"): False}))
                if name in ("STP_cw_sacrifice_local_contact", "STP_cw_open_civil_registers"):
                    for flag in ("STP_false_trail_prepared", "STP_false_trail_in_progress"):
                        self.assertFalse(matches_conditions(visible, {**commission, ("FROM", "has_state_flag", flag): True}))
                    self.assertFalse(matches_conditions(visible, {**commission, ("FROM", "has_state_flag", "STP_resistance_administration_asset"): False}))
                    if name == "STP_cw_open_civil_registers":
                        self.assertTrue(matches_conditions(block(action, "available"), commission))
                        for condition in (("FROM", "is_owned_by", "ROOT"), ("FROM", "is_controlled_by", "ROOT"),
                                          ("FROM", "has_state_flag", "STP_party_inspection_active"),
                                          ("FROM", "has_state_flag", "STP_resistance_administration_asset"),
                                          ("FROM", "STP_region_is_operable", "yes")):
                            self.assertFalse(matches_conditions(block(action, "available"), {**commission, condition: False}), condition)
                else:
                    self.assertFalse(matches_conditions(visible, {**commission, ("FROM", "has_state_flag", "STP_cw_garrison_evacuated"): True}))

    def test_civil_registers_keep_the_administration_and_surrender_only_military_preparation(self):
        decisions = block(entries("common/decisions/ADISCORD_STP_decisions.txt"), "STP_battle_for_stelander")
        action = block(decisions, "STP_cw_open_civil_registers")
        self.assertEqual(scalar(action, "cost"), "25")
        self.assertNotIn("days_remove", {e.key for e in action})
        payload = block(action, "complete_effect")
        self.assertEqual(scalar(block(payload, "add_power_balance_value"), "value"), "-0.02")
        state = block(block(payload, "hidden_effect"), "FROM")
        self.assertEqual([e.value for e in state if e.key == "clr_state_flag"], [
            "STP_resistance_garrison_asset", "STP_resistance_supply_asset", "STP_resistance_sabotage_asset",
            "STP_cw_garrison_evacuation_in_progress"])
        self.assertEqual(scalar(state, "set_state_flag"), "STP_inspection_concession_prepared")
        self.assertEqual(scalar(state, "STP_cw_return_preparation_reserves"), "yes")
        self.assertFalse({"add_manpower", "create_unit", "add_political_power", "STP_political_action_slot_consume",
                          "STP_political_action_slot_release", "remove_mission", "set_country_flag"} & {e.key for e in walk(payload)})
        self.assertNotIn("STP_cw_garrison_evacuated", [e.value for e in walk(payload) if isinstance(e.value, str)])

        effects = entries("common/scripted_effects/ADISCORD_STP_scripted_effects.txt")
        resolution = block(effects, "STP_resolve_party_inspection")
        operable = block(entries("common/scripted_triggers/ADISCORD_STP_scripted_triggers.txt"), "STP_region_is_operable")
        reports = next(e.value for e in entries("common/scripted_localisation/ADISCORD_STP_scripted_loc.txt")
                       if e.key == "defined_text" and scalar(e.value, "name") == "STPGetLastPartyResponse")
        for administration, expected_report, label in ((True, "12", "STP_PARTY_RESPONSE_CIVIL_REGISTERS"),
                                                       (False, "9", "STP_PARTY_RESPONSE_CONCESSION")):
            facts = {("2", "has_state_flag", "STP_inspection_concession_prepared"): True,
                     ("2", "has_state_flag", "STP_resistance_administration_asset"): administration,
                     ("2", "has_state_flag", "STP_region_player_operations_allowed"): True}
            self.assertFalse(matches_conditions(operable, facts, "2"))
            selected = list(selected_effects(resolution, facts, "2"))
            self.assertNotIn("STP_resistance_administration_asset", [e.value for _, e in selected if e.key == "clr_state_flag"])
            self.assertFalse({"STP_cw_return_preparation_reserves", "STP_cw_assess_search_evidence", "set_state_flag"}
                             & {e.key for _, e in selected}, "the completed concession must not confiscate reserves or restart counterintelligence")
            self.assertEqual([(scope, scalar(e.value, "value")) for scope, e in selected if e.key == "set_variable"
                              and scalar(e.value, "var") == "STP_last_party_response"], [("STP", expected_report)])
            for scope, entry in selected:
                if entry.key == "clr_state_flag":
                    facts[(scope, "has_state_flag", entry.value)] = False
            self.assertTrue(matches_conditions(operable, facts, "2"), "military assets may be rebuilt after the commission closes")
            report_facts = {("STP", "variable", "STP_last_party_response"): int(expected_report)}
            displayed = next(scalar(e.value, "localization_key") for e in reports if e.key == "text" and
                             (not any(v.key == "trigger" for v in e.value) or matches_conditions(block(e.value, "trigger"), report_facts)))
            self.assertEqual(displayed, label)
        sacrifice = block(block(block(decisions, "STP_cw_sacrifice_local_contact"), "complete_effect"), "hidden_effect")
        self.assertIn(("clr_state_flag", "STP_resistance_administration_asset"),
                      [(e.key, e.value) for e in block(sacrifice, "FROM")])
        command = block(entries("common/scripted_triggers/ADISCORD_STP_scripted_triggers.txt"), "STP_cw_public_command_available")
        negotiation = block(decisions, "STP_cw_secure_election_result")
        for target, other in (("2", "29"), ("29", "2")):
            for second_garrison in (False, True):
                backing = {("STP", "has_character", "STP_Edmund_Ravel"): True,
                           **{(district, key, "STP"): True for district in (target, other)
                              for key in ("is_owned_by", "is_controlled_by")},
                           (target, "has_state_flag", "STP_resistance_garrison_asset"): True,
                           (other, "has_state_flag", "STP_resistance_garrison_asset"): second_garrison}
                self.assertTrue(matches_conditions(command, backing))
                for entry in state:
                    if entry.key == "clr_state_flag":
                        backing[(target, "has_state_flag", entry.value)] = False
                still_backed = matches_conditions(command, backing)
                self.assertEqual(still_backed, second_garrison)
                pending = {("STP", "STP_cw_preparation_open", "yes"): True,
                           ("STP", "STP_cw_public_command_available", "yes"): still_backed}
                self.assertEqual(matches_conditions(block(negotiation, "cancel_trigger"), pending), not second_garrison)
                cancelled = list(selected_effects(block(negotiation, "cancel_effect"), pending))
                self.assertEqual([entry.key for _, entry in cancelled], ["STP_political_action_slot_release"])
        self.assertEqual(scalar(negotiation, "cost"), "75")
        loc_path = ROOT / "localisation/russian/ADISCORD_STP_l_russian.yml"
        self.assertTrue(loc_path.read_bytes().startswith(b"\xef\xbb\xbf"))
        loc = loc_path.read_text(encoding="utf-8-sig")
        warning = next(line for line in loc.splitlines() if line.startswith(" STP_cw_civil_registers_command_risk_tt:"))
        for phrase in ("последний", "[2.GetName]", "[29.GetName]", "75", "без возврата", "мандат", "ограниченный мятеж"):
            self.assertIn(phrase, warning)

    def test_civil_registers_refund_the_existing_ledger_before_cancelled_sabotage_can_refund_again(self):
        from fractions import Fraction
        effects = entries("common/scripted_effects/ADISCORD_STP_scripted_effects.txt")
        refund = block(effects, "STP_cw_return_preparation_reserves")
        inputs = [scalar(e.value, "value") for e in refund if e.key in ("set_temp_variable", "add_to_temp_variable")]
        self.assertEqual(inputs, ["STP_cw_cached_rifles", "STP_cw_pending_rifles", "STP_cw_sabotage_rifles"])
        cleared = [e.value for e in refund if e.key == "clear_variable"]
        self.assertEqual(cleared, inputs)
        payment = next(e.value for e in refund if e.key == "if" and any(v.key == "owner" for v in e.value))
        credit = block(block(payment, "owner"), "add_equipment_to_stockpile")
        self.assertEqual((scalar(credit, "type"), scalar(credit, "amount")), ("infantry_equipment", "PREV.STP_cw_returned_rifles"))
        self.assertLess(max(e.line for e in refund if e.key == "clear_variable"), min(e.line for e in walk(payment) if e.key == "add_equipment_to_stockpile"))
        sabotage = block(block(entries("common/decisions/ADISCORD_STP_decisions.txt"), "STP_battle_for_stelander"), "STP_region_unique_operation_53")
        for amounts in ((0, 0, 0), (1600, 1600, 240), (Fraction(1, 4), Fraction(3, 4), Fraction(239999, 1000))):
            ledger = dict(zip(inputs, amounts))
            paid = []
            for _ in range(2):
                amount = sum(ledger[name] for name in inputs)
                facts = {("2", "variable", "STP_cw_returned_rifles"): amount}
                if matches_conditions(block(payment, "limit"), facts, "2"):
                    paid.append(amount)
                for name in cleared:
                    ledger[name] = 0
            self.assertEqual(sum(paid), sum(amounts))
            late = list(selected_effects(block(sabotage, "cancel_effect"), {
                ("FROM", "has_variable", name): bool(amount) for name, amount in ledger.items()}))
            self.assertFalse(any(e.key == "add_equipment_to_stockpile" for _, e in late))
            self.assertEqual(sum(e.key == "STP_political_action_slot_release" for _, e in late), 1)
        self.assertEqual(refund[0].key, "STP_cw_refund_kefreyt_volunteers")
        volunteers = block(effects, "STP_cw_refund_kefreyt_volunteers")
        self.assertEqual(scalar(volunteers, "clear_variable"), "STP_cw_kefreyt_volunteers")
        self.assertFalse(any(e.key == "owner" for e in walk(volunteers)))

    def test_inspection_delay_reserves_one_slot_for_fourteen_days_and_releases_on_either_terminal_path(self):
        decision = block(block(entries("common/decisions/ADISCORD_STP_decisions.txt"), "STP_battle_for_stelander"), "STP_cw_delay_inspection")
        self.assertEqual(tuple(scalar(decision, key) for key in ("cost", "days_remove", "days_re_enable")), ("35", "14", "60"))
        self.assertEqual(scalar(decision, "state_target"), "yes")
        self.assertEqual({int(e.value) for e in block(decision, "targets")}, {2, 3, 29, 45, 46, 53})
        for state in (2, 3, 29, 45, 46, 53):
            mission = f"STP_party_inspection_state_{state}"
            for has_slot in (False, True):
                facts = {("STP", "has_completed_focus", "STP_Count_The_Loyalists"): True,
                         ("STP", "has_active_mission", mission): True,
                         ("STP", "STP_has_political_action_slot", "yes"): has_slot,
                         ("STP", "STP_cw_from_inspection_mission_active", "yes"): True,
                         ("FROM", "is_owned_by", "ROOT"): True,
                         ("FROM", "is_controlled_by", "ROOT"): True,
                         ("FROM", "has_state_flag", "STP_party_inspection_active"): True,
                         ("FROM", "STP_region_is_operable", "yes"): True}
                self.assertEqual(matches_conditions(block(decision, "available"), facts), has_slot)
            live = {("FROM", "has_state_flag", "STP_party_inspection_active"): True,
                    ("FROM", "STP_region_is_operable", "yes"): True,
                    ("FROM", "is_owned_by", "ROOT"): True,
                    ("FROM", "is_controlled_by", "ROOT"): True,
                    ("STP", "STP_cw_from_inspection_mission_active", "yes"): True,
                    ("STP", "has_active_mission", mission): True,
                    ("FROM", "state", str(state)): True}
            started = list(selected_effects(block(decision, "complete_effect"), live))
            self.assertEqual(sum(e.key == "STP_political_action_slot_consume" for _, e in started), 1)
            self.assertFalse(any(e.key == "add_political_power" for _, e in started), "native cost must be charged only once")
            adjustments = [(scalar(e.value, "mission"), scalar(e.value, "days"))
                           for _, e in started if e.key == "add_days_mission_timeout"]
            self.assertTrue(all(days == "14" for _, days in adjustments))
            self.assertLessEqual(len(adjustments), 1)
        vanished = list(selected_effects(block(decision, "complete_effect"), {
            ("FROM", "has_state_flag", "STP_party_inspection_active"): False}))
        self.assertEqual([e.value for _, e in vanished if e.key == "add_political_power"], ["35"])
        for open_preparation, escrow in ((False, True), (True, True), (True, False)):
            facts = {("STP", "STP_cw_preparation_open", "yes"): open_preparation,
                     ("FROM", "has_state_flag", "STP_cw_inspection_delay_escrow"): escrow}
            self.assertEqual(matches_conditions(block(decision, "cancel_trigger"), facts),
                             (not open_preparation) or (not escrow))
        for terminal in ("cancel_effect", "remove_effect"):
            released = list(selected_effects(block(decision, terminal), {
                ("FROM", "has_state_flag", "STP_cw_inspection_delay_escrow"): True}))
            self.assertEqual(sum(e.key == "STP_political_action_slot_release" for _, e in released), 1)
            idle = list(selected_effects(block(decision, terminal), {}))
            self.assertEqual(sum(e.key == "STP_political_action_slot_release" for _, e in idle), 0)

    def test_technical_cancellation_is_hidden_but_slot_and_district_blockers_are_named(self):
        decisions = block(entries("common/decisions/ADISCORD_STP_decisions.txt"), "STP_battle_for_stelander")
        loc = (ROOT / "localisation/russian/ADISCORD_STP_l_russian.yml").read_text(encoding="utf-8-sig")
        for name in ("STP_cw_raise_district_network", "STP_cw_prepare_rifle_cache", "STP_recruit_regional_official",
                     "STP_prepare_false_trail", "STP_cw_agree_with_commander", "STP_cw_evacuate_garrison_officers",
                     *(f"STP_region_unique_operation_{s}" for s in (2, 3, 29, 45, 46, 53)),
                     "STP_cw_sabotage_capital", "STP_cw_sabotage_party_industry"):
            with self.subTest(decision=name):
                action = block(decisions, name)
                self.assertEqual([e.key for e in block(action, "cancel_trigger")], ["hidden_trigger"])
                available = block(action, "available")
                labels = [scalar(e.value, "tooltip") for e in walk(available) if e.key == "custom_trigger_tooltip"]
                self.assertIn("STP_preparation_slot_available_tt", labels)
                for label in labels:
                    self.assertRegex(loc, r"(?m)^ " + label + r':\s*"[^"\r\n]+"')
                self.assertNotIn("hidden_trigger", {e.key for e in available}, "availability needs a player-readable reason")
        for key in ("STP_party_inspection_active", "STP_resistance_garrison_asset"):
            self.assertRegex(loc, r"(?m)^ " + key + r':\s*"[^"\r\n]+"')

    def test_false_trail_shows_only_current_band_and_remains_readable_after_preparation(self):
        definitions = entries("common/scripted_localisation/ADISCORD_STP_scripted_loc.txt")
        odds = next(e.value for e in definitions if e.key == "defined_text" and scalar(e.value, "name") == "STPGetFalseTrailOdds")
        for suspicion, expected in ((0, "HIDDEN"), (24.999, "HIDDEN"), (25, "LOW"), (49.999, "LOW"),
                                    (50, "MEDIUM"), (69.999, "MEDIUM"), (70, "HIGH"), (100, "HIGH")):
            with self.subTest(suspicion=suspicion):
                facts = {("STP", "variable", "STP_party_suspicion"): suspicion}
                chosen = next(e.value for e in odds if e.key == "text" and
                              (not any(v.key == "trigger" for v in e.value) or matches_conditions(block(e.value, "trigger"), facts)))
                self.assertEqual(scalar(chosen, "localization_key"), "STP_FALSE_TRAIL_ODDS_" + expected)
        loc = (ROOT / "localisation/russian/ADISCORD_STP_l_russian.yml").read_text(encoding="utf-8-sig")
        for key in ("STP_prepare_false_trail_desc", "STP_REGION_INSPECTION_FALSE_TRAIL_READY"):
            line = next(line for line in loc.splitlines() if line.startswith(" " + key + ":"))
            self.assertIn("[STP.STPGetFalseTrailOdds]", line)
        self.assertNotIn("шансы указаны в решении", loc)

    def test_rifle_reserve_focuses_require_full_stock_and_shared_cache_capacity(self):
        tree = next(e.value for e in entries("common/national_focus/ADISCORD_national_focus_STP.txt")
                    if e.key == "focus_tree" and scalar(e.value, "id") == "STP_focus")
        focuses = {scalar(e.value, "id"): e.value for e in tree if e.key == "focus"}
        facts = {("STP", "STP_cw_preparation_open", "yes"): True,
                 ("STP", "has_country_flag", "STP_sided_with_Maksim_flag"): True,
                 ("STP", "has_active_mission", "STP_cw_election_window"): True}
        for focus_id, price in (("STP_cw_abila_reserve", 16000),):
            available = block(focuses[focus_id], "available")
            for stock in (price - 1, price - 0.5, price - 0.001, price, price + 0.5):
                with self.subTest(focus=focus_id, stock=stock):
                    self.assertEqual(matches_conditions(available, {
                        **facts, ("STP", "equipment", "infantry_equipment"): stock,
                    }), stock >= price)
            for pending in (0, 16000):
                for delta in (-0.5, 0, 0.5):
                    cached = 96000 - price - pending + delta
                    scenario = {**facts, ("STP", "equipment", "infantry_equipment"): price,
                                ("1", "variable", "STP_cw_cached_rifles"): cached,
                                ("1", "has_variable", "STP_cw_pending_rifles"): bool(pending),
                                ("1", "variable", "STP_cw_pending_rifles"): pending}
                    with self.subTest(focus=focus_id, cached=cached, pending=pending):
                        self.assertEqual(matches_conditions(available, scenario), delta <= 0)
                        reward = block(focuses[focus_id], "completion_reward")
                        selected = [e for _, e in selected_effects(reward, scenario)]
                        self.assertEqual(any(e.key == "STP_cw_pay_rifles" for e in selected), delta <= 0,
                                         "completion must recheck capacity before debiting stock")

    def test_warehouse_service_remains_useful_with_empty_stocks_and_a_full_cache(self):
        tree = next(e.value for e in entries("common/national_focus/ADISCORD_national_focus_STP.txt")
                    if e.key == "focus_tree" and scalar(e.value, "id") == "STP_focus")
        focus = next(e.value for e in tree if e.key == "focus"
                     and scalar(e.value, "id") == "STP_cw_warehouse_inventory")
        facts = {("STP", "STP_cw_preparation_open", "yes"): True,
                 ("STP", "has_country_flag", "STP_sided_with_Maksim_flag"): True,
                 ("STP", "has_active_mission", "STP_cw_election_window"): True,
                 ("STP", "equipment", "infantry_equipment"): 0,
                 ("1", "variable", "STP_cw_cached_rifles"): 96000}
        self.assertTrue(matches_conditions(block(focus, "available"), facts))
        delivered = list(selected_effects(block(focus, "completion_reward"), facts))
        self.assertEqual([(scope, scalar(e.value, "var"), float(scalar(e.value, "value")))
                          for scope, e in delivered if e.key == "add_to_variable"],
                         [("STP", "STP_cw_pending_army_supply_consumption_factor", -.08)])
        self.assertFalse(any(e.key in ("STP_cw_pay_rifles", "add_political_power", "add_ideas")
                             for _, e in delivered))

    def test_preparation_consumes_focus_time_without_rewriting_the_election_deadline(self):
        tree = next(e.value for e in entries("common/national_focus/ADISCORD_national_focus_STP.txt")
                    if e.key == "focus_tree" and scalar(e.value, "id") == "STP_focus")
        focuses = {scalar(e.value, "id"): e.value for e in tree if e.key == "focus"}
        facts = {("STP", "STP_cw_preparation_open", "yes"): True,
                 ("STP", "has_country_flag", "STP_sided_with_Maksim_flag"): True,
                 ("STP", "equipment", "infantry_equipment"): 20000}
        specs = {"STP_cw_warehouse_inventory": 28, "STP_cw_abila_reserve": 14,
                 "STP_cw_expose_the_cabinet": 21, "STP_cw_buy_silence": 21}
        for focus_id, duration in specs.items():
            with self.subTest(focus=focus_id):
                focus = focuses[focus_id]
                self.assertEqual(float(scalar(focus, "cost")) * 7, duration)
                self.assertFalse(matches_conditions(block(focus, "available"), facts),
                                 "military rewards must not bypass the deadline before elections begin")
                self.assertTrue(matches_conditions(block(focus, "available"), {
                    **facts, ("STP", "has_active_mission", "STP_cw_election_window"): True}))
                timers = [e.value for e in walk(block(focus, "completion_reward"))
                          if e.key == "add_days_mission_timeout"]
                self.assertEqual(timers, [], "resource preparation must not silently move the announced election date")
        gate = block(focuses["STP_THE_MOUNTAIN_WINDOW"], "prerequisite")
        self.assertEqual([e.value for e in gate if e.key == "focus"],
                         ["STP_Garrisons_Hesitate"])
        for name in ("STP_cw_district_printing", "STP_The_Silent_Mountain_March", "STP_THE_MOUNTAIN_WINDOW"):
            self.assertFalse(any(e.key == "has_active_mission" and e.value == "STP_cw_election_window"
                                 for e in walk(block(focuses[name], "available"))))
        for name, price in (("STP_cw_abila_reserve", 16000),):
            reward = block(focuses[name], "completion_reward")
            payments = [e.value for e in walk(reward) if e.key == "set_temp_variable"
                        and scalar(e.value, "var") == "STP_cw_rifle_cost"]
            self.assertEqual(len(payments), 1, "one exact payment must fund the reserved shipment")
            self.assertEqual(int(scalar(payments[0], "value")), price)
            for paid in (False, True):
                scenario = {**facts, ("STP", "has_active_mission", "STP_cw_election_window"): True,
                            ("STP", "has_country_flag", "STP_cw_rifles_paid"): paid}
                effects = list(selected_effects(reward, scenario))
                credited = [(scope, e) for scope, e in effects if e.key == "add_to_variable"
                            and scalar(e.value, "var") == "STP_cw_cached_rifles"]
                self.assertEqual([(scope, int(scalar(e.value, "value"))) for scope, e in credited],
                                 [("1", price)] if paid else [])
                self.assertFalse(any(e.key == "add_days_mission_timeout" for _, e in effects),
                                 "neither successful nor failed payment moves the election deadline")
                if name == "STP_cw_abila_reserve":
                    self.assertEqual(any(e.key == "set_country_flag" and e.value == "STP_cw_abila_reserve_ready"
                                         for _, e in effects), paid)

    def test_custom_prices_check_and_charge_political_power_with_the_second_resource(self):
        specs = {
            "STP_bargain_with_local_councils": (10, "treasury", 1200),
            "STP_prepare_false_trail": (15, "treasury", 600),
            "STP_region_unique_operation_3": (10, "treasury", 1200),
            "STP_region_unique_operation_45": (15, "treasury", 2400),
            "STP_region_unique_operation_46": (20, "treasury", 1200),
            "STP_region_unique_operation_53": (10, "equipment", 240),
            "STP_cw_agree_with_commander": (45, "command_power", 20),
            "VAL_ops_finance_cin_contacts": (10, "treasury", 50),
            "VAL_ops_finance_osf_contacts": (10, "treasury", 50),
            "VAL_ops_sell_rifles_to_cin": (10, "equipment", 2500),
            "VAL_ops_sell_rifles_to_osf": (10, "equipment", 2500),
            "VAL_pay_quarterly_contract_norm": (10, "equipment", 4000),
        }
        shared = entries("common/scripted_triggers/ADISCORD_shared_action_triggers.txt") + entries("common/scripted_triggers/ADISCORD_STP_scripted_triggers.txt")
        for tag, localisation_name in (
            ("STP", "ADISCORD_STP_l_russian.yml"),
            ("VAL", "ADISCORD_VAL_decisions_l_russian.yml"),
        ):
            categories = entries(f"common/decisions/ADISCORD_{tag}_decisions.txt")
            actions = {e.key: e.value for category in categories for e in category.value
                       if isinstance(e.value, list)}
            loc = (ROOT / "localisation/russian" / localisation_name).read_text(encoding="utf-8-sig")
            for name, (pp_price, resource, resource_price) in specs.items():
                if not name.startswith(tag + "_"):
                    continue
                with self.subTest(decision=name):
                    action = actions[name]
                    self.assertEqual(scalar(action, "cost"), "0", "custom prices must not rely on a suppressed automatic PP debit")
                    # No second PP charge on expiry or cancellation.
                    payments = [e.value for e in walk(action) if e.key == "add_political_power"]
                    self.assertEqual(payments, [str(-pp_price)])
                    self.assertIn(str(-pp_price), [e.value for e in walk(block(action, "complete_effect"))
                                                   if e.key == "add_political_power"])
                    northern_sale = name in ("VAL_ops_sell_rifles_to_cin", "VAL_ops_sell_rifles_to_osf")
                    price_cases = ((False, 2500), (True, 5000)) if northern_sale else ((False, resource_price),)
                    for licensed, charged_price in price_cases:
                        for pp, stock, expected in ((pp_price - .5, charged_price, False),
                                                    (pp_price, charged_price - .5, False),
                                                    (pp_price, charged_price, True),
                                                    (pp_price + .5, charged_price + .5, True)):
                            facts = {(tag, "numeric", "has_political_power"): pp,
                                     (tag, "has_completed_focus", "VAL_Foreign_Broker_Licences"): licensed}
                            if resource == "equipment":
                                facts[(tag, "equipment", "infantry_equipment")] = stock
                            elif resource == "command_power":
                                facts[(tag, "numeric", "command_power")] = stock
                            else:
                                guard = f"STP_cw_can_spend_{resource_price}" if tag == "STP" else f"ADISCORD_economy_can_spend_{resource_price}"
                                treasury = {(tag, "variable", "ADISCORD_economy_treasury"): stock}
                                facts[(tag, guard, "yes")] = matches_conditions(block(shared, guard), treasury, tag)
                            self.assertEqual(matches_conditions(block(action, "custom_cost_trigger"), facts, tag), expected,
                                             (name, licensed, pp, stock))
                    price_key = scalar(action, "custom_cost_text")
                    price_line = re.search(rf"(?m)^ {re.escape(price_key)}:.*$", loc)
                    self.assertIsNotNone(price_line, price_key)
                    shown = price_line.group(0)
                    self.assertIn(f"£political_power_texticon §Y{pp_price}§!", shown)
                    icon = {"treasury": "ADISCORD_economy_treasury_texticon", "equipment": "infantry_equipment_texticon",
                            "command_power": "command_power_texticon"}[resource]
                    if northern_sale:
                        self.assertIn(f"£{icon} §Y[VALGetExportRifleQuantity]§!", shown)
                        getter = next(e.value for e in entries("common/scripted_localisation/ADISCORD_VAL_contract_scripted_loc.txt")
                                      if scalar(e.value, "name") == "VALGetExportRifleQuantity")
                        # Paid quote precedes current focus state, including old boolean receipts.
                        for licensed, receipt, expected in ((False, 0, 2500), (True, 0, 5000),
                                                            (True, 1, 2500), (True, 15, 2500), (True, 20, 2500),
                                                            (False, 30, 5000), (True, 30, 5000), (True, 40, 5000)):
                            facts = {("VAL", "has_completed_focus", "VAL_Foreign_Broker_Licences"): licensed,
                                     ("VAL", "has_country_flag", "VAL_export_rifles_reserved"): bool(receipt)}
                            for option in (e.value for e in getter if e.key == "text"):
                                checks = []
                                for condition in next((e.value for e in option if e.key == "trigger"), []):
                                    if condition.key == "has_country_flag" and isinstance(condition.value, list):
                                        self.assertEqual(scalar(condition.value, "flag"), "VAL_export_rifles_reserved")
                                        comparison = [e.value for e in condition.value if not e.key]
                                        self.assertEqual(comparison[:2], ["value", ">"])
                                        self.assertEqual(len(comparison), 3)
                                        checks.append(bool(receipt) and receipt > int(comparison[2]))
                                    else:
                                        checks.append(matches_conditions([condition], facts, "VAL"))
                                if all(checks):
                                    key = scalar(option, "localization_key")
                                    value = re.search(rf'(?m)^ {re.escape(key)}:(?:0)? "(\d+)"$', loc)
                                    self.assertIsNotNone(value, key)
                                    self.assertEqual(int(value.group(1)), expected, (name, licensed, receipt))
                                    break
                            else:
                                self.fail("Export quantity getter has no matching text")
                    else:
                        self.assertIn(f"£{icon} §Y{resource_price}§!", shown)

    def test_native_stp_custom_prices_have_affordable_blocked_and_hover_labels(self):
        categories = entries("common/decisions/ADISCORD_STP_decisions.txt")
        actions = {a.key: a.value for c in categories for a in c.value if isinstance(a.value, list)}
        price_keys = {e.value for action in actions.values() for e in action if e.key == "custom_cost_text"}
        localisation = (ROOT / "localisation/russian/ADISCORD_STP_l_russian.yml").read_text(encoding="utf-8-sig")
        values = dict(re.findall(r'^ ([\w.]+):\s*"(.*)"$', localisation, re.M))
        for key in price_keys:
            with self.subTest(price=key):
                self.assertIn(key, values)
                self.assertIn(key + "_blocked", values, "native custom_cost_text automatically requests this suffix")
                self.assertIn(key + "_tooltip", values)
                base, blocked, tooltip = (values[key + suffix] for suffix in ("", "_blocked", "_tooltip"))
                self.assertEqual(blocked, base.replace("§Y", "§R"))
                prices = re.findall(r"(£\w+)\s+§Y([0-9.]+)§!", base)
                self.assertTrue(prices, "the price needs readable currency amounts")
                self.assertEqual(prices, re.findall(r"(£\w+)\s+§Y([0-9.]+)§!", tooltip))
                self.assertTrue(re.findall(r"£\w+", base), "preserve the existing currency texticons")
                self.assertEqual(re.findall(r"£\w+", base), re.findall(r"£\w+", blocked))
        commander = actions["STP_cw_agree_with_commander"]
        key = scalar(commander, "custom_cost_text")
        for pp, cp, suffix in ((45, 18, "_blocked"), (44.5, 20, "_blocked"),
                               (45, 19.5, "_blocked"), (45, 20, ""), (100, 100, "")):
            facts = {("STP", "numeric", "has_political_power"): pp,
                     ("STP", "numeric", "command_power"): cp}
            affordable = matches_conditions(block(commander, "custom_cost_trigger"), facts)
            selected_key = key + ("" if affordable else "_blocked")
            self.assertEqual(selected_key, key + suffix)
            self.assertIn(selected_key, values)
        self.assertEqual(values["STP_cw_agree_with_commander"], "Договориться с командиром: [FROM.GetName]")
        self.assertEqual(scalar(commander, "state_target"), "yes")
        self.assertEqual({e.value for e in block(commander, "targets")}, {"2", "29", "45"})

    def test_preparation_prices_reject_fractional_shortfalls(self):
        decisions = entries("common/decisions/ADISCORD_STP_decisions.txt")
        actions = {entry.key: entry.value for category in decisions for entry in category.value
                   if isinstance(entry.value, list)}
        for price in (16000, 2400, 240):
            # Cover every consuming decision, including multiple purchases at one price.
            guards = [entry for action in actions.values() for entry in walk(action)
                      if entry.key == "has_equipment"
                      and any(child.value in (str(price), str(price - 1)) for child in entry.value)]
            self.assertTrue(guards, price)
            for guard in guards:
                parent = next(entry for action in actions.values() for entry in walk(action)
                              if isinstance(entry.value, list) and guard in entry.value)
                for stock, expected in ((price - .5, False), (price, True), (price + .5, True)):
                    with self.subTest(price=price, line=guard.line, stock=stock):
                        condition = [parent] if parent.key == "NOT" else [guard]
                        self.assertEqual(matches_conditions(condition, {("STP", "equipment", "infantry_equipment"): stock}), expected)

    def test_first_opposition_deadline_allows_the_natural_countermeasure_route(self):
        tree = next(e.value for e in entries("common/national_focus/ADISCORD_national_focus_STP.txt")
                    if e.key == "focus_tree" and scalar(e.value, "id") == "STP_focus")
        focuses = {scalar(e.value, "id"): e.value for e in tree if e.key == "focus"}
        decisions = block(entries("common/decisions/ADISCORD_STP_decisions.txt"), "STP_battle_for_stelander")
        raid = block(decisions, "STP_cw_check_district_command")
        unlock = scalar(next(e.value for e in walk(raid)
                             if e.key == "visible"), "has_completed_focus")
        # The side's root is completed by the choice event, not by focus progress.
        route = []
        current = unlock
        while current != "STP_Govern_In_His_Name":
            self.assertNotIn(current, route, "cyclic countermeasure route")
            route.append(current)
            current = scalar(block(focuses[current], "prerequisite"), "focus")
        focus_days = sum(float(scalar(focuses[name], "cost")) * 7 for name in route)
        response_days = int(scalar(raid, "days_remove"))
        recurring_days = int(scalar(block(decisions, "STP_cw_opposition_preparation"), "days_mission_timeout"))
        schedule = block(block(entries("common/scripted_effects/ADISCORD_STP_scripted_effects.txt"),
                               "STP_cw_schedule_opposition"), "if")
        facts = {("STP", "tag", "STP"): True,
                 ("STP", "STP_cw_preparation_open", "yes"): True,
                 ("STP", "has_country_flag", "STP_battle_for_stelander_active"): True,
                 ("STP", "has_country_flag", "STP_sided_with_the_party_flag"): True}
        self.assertTrue(matches_conditions(block(schedule, "limit"), facts))
        payload = [e for e in schedule if e.key != "limit"]
        first = [e for _, e in selected_effects(payload, facts)]
        extension = sum(int(scalar(e.value, "days")) for e in first
                        if e.key == "add_days_mission_timeout"
                        and scalar(e.value, "mission") == "STP_cw_opposition_preparation")
        self.assertGreaterEqual(recurring_days + extension, focus_days + response_days + 1,
                                "first target expires before its unlock and paid response can finish")
        flags = [e.value for e in first if e.key == "set_country_flag"]
        self.assertEqual(len(flags), 1, "initial breathing room must be granted only once")
        later = [e for _, e in selected_effects(payload, {**facts, ("STP", "has_country_flag", flags[0]): True})]
        self.assertFalse(any(e.key == "add_days_mission_timeout" for e in later),
                         "later operations must retain their shorter cadence")
        self.assertLess(response_days, recurring_days)
        active = {**facts, ("STP", "has_active_mission", "STP_cw_opposition_preparation"): True}
        self.assertFalse(matches_conditions(block(schedule, "limit"), active),
                         "repeated scheduling must not extend a running operation")

    def test_opposition_announces_one_target_before_the_timer_and_raid_interrupts_it(self):
        effects = entries("common/scripted_effects/ADISCORD_STP_scripted_effects.txt")
        schedule = block(block(effects, "STP_cw_schedule_opposition"), "if")
        target = block(schedule, "random_owned_state")
        self.assertEqual(scalar(target, "set_state_flag"), "STP_cw_opposition_target")
        self.assertLess(next(i for i, e in enumerate(schedule) if e.key == "random_owned_state"),
                        next(i for i, e in enumerate(schedule) if e.key == "activate_mission"))
        finish = block(block(effects, "STP_cw_prepare_opposition"), "if")
        self.assertNotIn("random_owned_state", {e.key for e in walk(finish)})
        district = block(finish, "every_owned_state")
        facts = {("2", "has_state_flag", "STP_cw_opposition_target"): True,
                 ("2", "STP_region_is_operable", "yes"): True,
                 ("2", "is_controlled_by", "STP"): True}
        self.assertTrue(matches_conditions(block(district, "limit"), facts, "2"))
        for failed in facts:
            self.assertFalse(matches_conditions(block(district, "limit"), {**facts, failed: False}, "2"))
        raid = block(effects, "STP_cw_secure_party_district")
        self.assertIn(("clr_state_flag", "STP_cw_opposition_target"), [(e.key, e.value) for e in raid])
        evidence = block(effects, "STP_cw_assess_search_evidence")
        response = next(e.value for e in entries("common/scripted_localisation/ADISCORD_STP_scripted_loc.txt")
                        if e.key == "defined_text" and scalar(e.value, "name") == "STPGetLastPartyResponse")
        localisation = (ROOT / "localisation/russian/ADISCORD_STP_l_russian.yml").read_text(encoding="utf-8-sig")
        evidence_cases = (
            {("2", "has_state_flag", "STP_cw_opposition_target"): True},
            {("2", "STP_region_has_detectable_assets", "yes"): True},
            {("2", "variable", "STP_cw_cached_rifles"): 1},
            {("2", "variable", "STP_cw_pending_rifles"): 1},
            {},
        )
        for present in evidence_cases:
            with self.subTest(evidence=present):
                expected, report, label = ((-.04, "10", "STP_PARTY_RESPONSE_EVIDENCE_FOUND") if present else
                                           (.02, "11", "STP_PARTY_RESPONSE_EMPTY_SEARCH"))
                facts = {("STP", "STP_cw_preparation_open", "yes"): True, **present}
                selected = list(selected_effects(evidence, facts, "2"))
                changes = [(scope, float(scalar(e.value, "value"))) for scope, e in selected
                           if e.key == "add_power_balance_value"]
                self.assertEqual(changes, [("STP", expected)], "evidence and an empty raid have opposite legitimacy outcomes")
                reports = [(scope, scalar(e.value, "value")) for scope, e in selected
                           if e.key == "set_variable" and scalar(e.value, "var") == "STP_last_party_response"]
                self.assertEqual(reports, [("STP", report)], "write the existing country report beside its actual BOP result")
                report_facts = {("STP", "variable", "STP_last_party_response"): float(report)}
                selected_label = next(scalar(e.value, "localization_key") for e in response if e.key == "text" and
                                      (not any(t.key == "trigger" for t in e.value) or
                                       matches_conditions(block(e.value, "trigger"), report_facts)))
                self.assertEqual(selected_label, label, "a completed raid must not render the NONE fallback")
                self.assertRegex(localisation, rf'(?m)^ {label}:(?:0)? ".+"$')
                self.assertEqual(list(selected_effects(evidence, {**facts, ("STP", "STP_cw_preparation_open", "yes"): False}, "2")), [],
                                 "after preparation closes, a late callback must preserve the previous report and legitimacy")
        events = entries("events/ADISCORD_STP_events.txt")
        for event_id in ("ADISCORD_STP_preparation.1", "ADISCORD_STP_preparation.5"):
            event = next(e.value for e in events if e.key == "country_event" and scalar(e.value, "id") == event_id)
            self.assertIn("STP_cw_schedule_opposition", {e.key for e in walk(event)})

    def test_commander_agreement_has_a_finite_cost_and_keeps_the_opposition_network(self):
        decisions = block(entries("common/decisions/ADISCORD_STP_decisions.txt"), "STP_battle_for_stelander")
        action = block(decisions, "STP_cw_agree_with_commander")
        self.assertEqual((scalar(action, "cost"), scalar(action, "days_remove")), ("0", "14"))
        self.assertEqual(scalar(block(action, "complete_effect"), "add_command_power"), "-20")
        for power, expected in ((19.5, False), (20, True)):
            self.assertEqual(matches_conditions(block(action, "custom_cost_trigger"),
                                                {("STP", "numeric", "command_power"): power,
                                                 ("STP", "numeric", "has_political_power"): 45}), expected)
        reward = block(action, "remove_effect")
        self.assertIn("STP_party_reinforced_garrison_asset", {e.value for e in walk(reward) if e.key == "set_state_flag"})
        self.assertNotIn("clr_state_flag", {e.key for e in walk(reward)})
        self.assertNotIn("STP_cw_pay_rifles", {e.key for e in walk(action)})
        self.assertNotIn("add_manpower", {e.key for e in walk(action)})

    def test_evacuated_cadres_replace_one_garrison_and_survive_as_two_paid_brigades(self):
        decisions = block(entries("common/decisions/ADISCORD_STP_decisions.txt"), "STP_battle_for_stelander")
        action = block(decisions, "STP_cw_evacuate_garrison_officers")
        self.assertEqual({e.value for e in block(action, "targets")}, {"2", "29"})
        self.assertEqual((scalar(action, "cost"), scalar(action, "days_remove")), ("35", "7"))
        finish = block(action, "remove_effect")
        result = block(block(finish, "hidden_effect"), "if")
        self.assertIn("STP_party_inspection_active", {e.value for e in walk(block(result, "limit")) if e.key == "has_state_flag"})
        removed = {e.value for e in walk(finish) if e.key == "clr_state_flag"}
        created = {e.value for e in walk(finish) if e.key == "set_state_flag"}
        self.assertIn("STP_resistance_garrison_asset", removed)
        self.assertIn("STP_cw_garrison_evacuated", created)
        transfer = block(result, "FROM")
        self.assertEqual(scalar(block(transfer, "set_temp_variable"), "value"), "12")
        self.assertEqual(scalar(transfer, "STP_add_party_influence"), "yes", "the influence helper clamps negative shifts to zero")
        facts = {("STP", "STP_cw_preparation_open", "yes"): True,
                 ("STP", "has_country_flag", "STP_battle_for_stelander_active"): True,
                 ("FROM", "STP_region_is_operable", "yes"): True,
                 ("FROM", "is_owned_by", "ROOT"): True,
                 ("FROM", "is_controlled_by", "ROOT"): True,
                 ("FROM", "has_state_flag", "STP_party_inspection_active"): True,
                 ("FROM", "has_state_flag", "STP_resistance_garrison_asset"): True,
                 ("FROM", "has_state_flag", "STP_cw_garrison_evacuation_in_progress"): True}
        condition = block(result, "limit")
        self.assertTrue(matches_conditions(condition, facts))
        for failed in facts:
            with self.subTest(delayed_callback_lost=failed):
                self.assertFalse(matches_conditions(condition, {**facts, failed: False}))
        for scope, entry in selected_effects(block(finish, "hidden_effect"), facts):
            if entry.key in ("set_state_flag", "clr_state_flag"):
                facts[(scope, "has_state_flag", entry.value)] = entry.key == "set_state_flag"
        self.assertFalse(matches_conditions(condition, facts), "a repeated completion cannot save the same officers twice")
        effects = entries("common/scripted_effects/ADISCORD_STP_scripted_effects.txt")
        start = block(block(effects, "STP_cw_start"), "if")
        successor = next(e.value for e in start if e.key == "STS"
                         and any(c.key == "STP_cw_mobilize_brigade" for c in walk(e.value)))
        for state in ("2", "29"):
            cases = [e.value for e in successor if e.key == "if"
                     and any(c.key == state for c in block(e.value, "limit"))]
            self.assertEqual(len(cases), 1)
            for owned, garrison, evacuated, expected in ((True, True, False, 2), (False, False, True, 2),
                                                        (True, True, True, 2), (False, True, False, 0)):
                facts = {(state, "is_owned_by", "STS"): owned,
                         (state, "has_state_flag", "STP_resistance_garrison_asset"): garrison,
                         (state, "has_state_flag", "STP_cw_garrison_evacuated"): evacuated}
                self.assertEqual(sum(e.key == "STP_cw_mobilize_brigade" for _, e in selected_effects([next(e for e in successor if e.value == cases[0])], facts, "STS")), expected)
            visible = block(block(decisions, f"STP_region_unique_operation_{state}"), "visible")
            self.assertIn("STP_cw_garrison_evacuated", {e.value for e in walk(visible) if e.key == "has_state_flag"})
        cleanup = block(effects, "STP_clear_region_runtime")
        self.assertEqual(sum(e.key == "clr_state_flag" and e.value == "STP_cw_garrison_evacuated" for e in cleanup), 1)

    def test_paid_brigades_require_control_and_full_fractional_resource_prices(self):
        effects = entries("common/scripted_effects/ADISCORD_STP_scripted_effects.txt")
        condition = block(block(block(effects, "STP_cw_mobilize_brigade"), "if"), "limit")
        for rifles, people, controlled, expected in ((600, 6000, True, True), (599.5, 6000, True, False),
                                                     (600, 5999.5, True, False), (600, 6000, False, False)):
            facts = {("STS", "equipment", "infantry_equipment"): rifles,
                     ("STS", "numeric", "has_manpower"): people,
                     ("STS", "owns_state", "1"): True,
                     ("STS", "controls_state", "1"): controlled}
            with self.subTest(rifles=rifles, people=people, controlled=controlled):
                self.assertEqual(matches_conditions(condition, facts, "STS"), expected)

    def test_starting_health_preview_matches_the_first_decline_and_shows_its_event(self):
        tree = next(e.value for e in entries("common/national_focus/ADISCORD_national_focus_STP.txt")
                    if scalar(e.value, "id") == "STP_focus")
        focus = next(e.value for e in tree if e.key == "focus"
                     and scalar(e.value, "id") == "STP_STATE_OF_THE_REPUBLIC")
        reward = block(focus, "completion_reward")
        preview = block(reward, "effect_tooltip")
        swap = block(preview, "swap_ideas")
        ideas = block(block(entries("common/ideas/ADISCORD_STP_civil_war_ideas.txt"), "ideas"), "country")
        old = block(ideas, scalar(swap, "remove_idea"))
        new = block(ideas, scalar(swap, "add_idea"))
        for idea in (old, new):
            self.assertEqual(scalar(idea, "name"), "STP_fading_father")
            self.assertEqual(scalar(block(idea, "allowed"), "always"), "no")
        self.assertEqual(block(old, "modifier"), [])
        self.assertEqual(scalar(block(new, "modifier"), "stability_factor"), "-0.05")
        self.assertEqual(scalar(block(preview, "country_event"), "id"), "ADISCORD_STP_preparation.1")
        self.assertEqual({e.key for e in reward}, {"effect_tooltip", "hidden_effect"})
        self.assertEqual(scalar(block(reward, "hidden_effect"), "STP_cw_first_health_decline"), "yes")
        effects = entries("common/scripted_effects/ADISCORD_STP_scripted_effects.txt")
        first_decline = block(block(effects, "STP_cw_first_health_decline"), "if")
        self.assertEqual(scalar(block(first_decline, "set_temp_variable"), "var"), "STP_requested_health_stage")
        self.assertEqual(scalar(block(first_decline, "set_temp_variable"), "value"), "2")
        self.assertEqual(scalar(first_decline, "STP_set_leader_health_stage"), "yes")
        self.assertEqual(scalar(block(first_decline, "country_event"), "id"), "ADISCORD_STP_preparation.1")
        stage_two = next(e.value for e in block(effects, "STP_refresh_leader_health")
                         if e.key in ("if", "else_if")
                         and any(v.key == "check_variable" and scalar(v.value, "var") == "STP_leader_health_stage"
                                 and scalar(v.value, "value") == "2" for v in walk(block(e.value, "limit"))))
        actual = block(stage_two, "set_variable")
        self.assertEqual(scalar(actual, "var"), "STP_fading_father_stability_factor")
        self.assertEqual(scalar(actual, "value"), scalar(block(new, "modifier"), "stability_factor"))
        dynamic = block(entries("common/dynamic_modifiers/ADISCORD_dynamic_modifiers_STP.txt"), "STP_fading_father")
        self.assertEqual(scalar(dynamic, "stability_factor"), scalar(actual, "var"))

    def test_focus_rewards_hide_technical_flag_writes(self):
        def shown(items):
            for entry in items:
                if entry.key == "hidden_effect":
                    continue
                yield entry
                if isinstance(entry.value, list):
                    yield from shown(entry.value)
        for tree in entries("common/national_focus/ADISCORD_national_focus_STP.txt"):
            for focus in (e.value for e in tree.value if e.key == "focus"):
                self.assertFalse(any(e.key == "set_country_flag" for e in shown(block(focus, "completion_reward"))),
                                 scalar(focus, "id"))

    def test_war_plans_wait_for_a_paid_repeatable_player_order(self):
        tree = next(e.value for e in entries("common/national_focus/ADISCORD_national_focus_STP.txt")
                    if scalar(e.value, "id") == "STP_cw_focus")
        focuses = {scalar(e.value, "id"): e.value for e in tree if e.key == "focus"}
        decisions = block(entries("common/decisions/ADISCORD_STP_decisions.txt"), "STP_cw_war_council")
        for focus_id, decision_id, tag, state, idea, days, opponents in (
            ("STP_cw_last_banquet", "STP_cw_launch_last_banquet", "STS", "3", "STP_cw_deliberate_offensive", "21", {"STP"}),
            ("STP_cw_guard_the_pier", "STP_cw_hold_the_pier", "STP", "28", "STP_cw_static_defence", "35", {"STS"}),
        ):
            with self.subTest(focus=focus_id):
                reward = block(focuses[focus_id], "completion_reward")
                self.assertNotIn("add_timed_idea", {e.key for e in walk(reward)}, "preparing a plan must not start its clock")
                preview = block(reward, "unlock_decision_tooltip")
                self.assertEqual(scalar(preview, "decision"), decision_id)
                self.assertEqual(scalar(preview, "show_effect_tooltip"), "yes")
                decision = block(decisions, decision_id)
                self.assertEqual(scalar(block(decision, "allowed"), "tag"), tag)
                self.assertEqual(scalar(block(decision, "visible"), "has_completed_focus"), focus_id)
                self.assertEqual(scalar(decision, "fire_only_once"),
                                 "yes" if decision_id == "STP_cw_launch_last_banquet" else "no")
                available = block(decision, "available")
                self.assertIn(state, {e.value for e in available if e.key == "controls_state"})
                self.assertEqual({e.value for e in walk(available) if e.key == "has_war_with"}, opponents)
                self.assertIn(idea, {e.value for e in block(available, "NOT") if e.key == "has_idea"},
                              "do not overwrite a still-active prewar preparation bonus")
                # This structural parser represents bare comparison tokens as unnamed entries.
                self.assertEqual([e.value for e in block(block(decision, "custom_cost_trigger"), "NOT")],
                                 ["command_power", "<", "25"])
                executed = block(decision, "complete_effect")
                self.assertEqual(scalar(executed, "add_command_power"), "-25")
                timed = block(executed, "add_timed_idea")
                self.assertEqual((scalar(timed, "idea"), scalar(timed, "days")), (idea, days))
                if decision_id == "STP_cw_launch_last_banquet":
                    self.assertFalse(any(e.key == "days_re_enable" for e in decision))
                    self.assertEqual(sum(e.key == "activate_mission" and e.value == "STP_cw_last_banquet_deadline"
                                         for e in walk(executed)), 1)
                if tag in {"STP", "STS"}:
                    bypass = block(focuses[focus_id], "bypass")
                    self.assertFalse(matches_conditions(bypass, {}, tag))
                    self.assertTrue(matches_conditions(bypass, {
                        (tag, "has_global_flag", "STP_cw_union_wars_finished"): True,
                    }, tag), "a plan for a finished war must not consume focus time")

    def test_focus_packages_keep_material_results_and_unlock_related_counterplay(self):
        tree = next(e.value for e in entries("common/national_focus/ADISCORD_national_focus_STP.txt")
                    if scalar(e.value, "id") == "STP_focus")
        rewards = {scalar(e.value, "id"): block(e.value, "completion_reward") for e in tree if e.key == "focus"}
        repair = rewards["STP_cw_repair_niansas"]
        construction = block(block(repair, "3"), "add_building_construction")
        self.assertEqual((scalar(construction, "type"), scalar(construction, "level")), ("infrastructure", "1"))
        self.assertEqual(scalar(repair, "add_stability"), "0.02")
        for name, delta in (("STP_cw_repair_niansas", .05), ("STP_cw_district_administration", .10)):
            with self.subTest(focus=name):
                mandate = block(rewards[name], "add_power_balance_value")
                self.assertEqual(scalar(mandate, "id"), "STP_shabrat_election_legitimacy")
                self.assertEqual(float(scalar(mandate, "value")), delta)
        for name, decision in (("STP_Count_The_Loyalists", "STP_cw_delay_inspection"),
                               ("STP_Call_For_Shabrat", "STP_cw_sacrifice_local_contact"),
                               ("STP_cw_national_mandate", "STP_cw_open_civil_registers"),
                               ("STP_cw_supply_officers", "STP_region_unique_operation_46"),
                               ("STP_PARTY_DISCIPLINE", "STP_cw_check_district_command"),
                               ("STP_cw_security_collegium", "STP_cw_interrupt_opposition"),
                               ("STP_cw_press_office", "STP_cw_publish_directive"),
                               ("STP_cw_protocol_office", "STP_cw_seal_protocol"),
                               ("STP_cw_prepare_capital_sabotage", "STP_cw_sabotage_capital"),
                               ("STP_cw_prepare_industry_sabotage", "STP_cw_sabotage_party_industry")):
            with self.subTest(focus=name):
                unlocked = {e.value if isinstance(e.value, str) else scalar(e.value, "decision")
                            for e in rewards[name] if e.key == "unlock_decision_tooltip"}
                self.assertIn(decision, unlocked)
        for name, budget in (("STP_Count_The_Loyalists", "50"), ("STP_Call_For_Shabrat", "75"),
                             ("STP_Garrisons_Hesitate", "100"), ("STP_PARTY_DISCIPLINE", "25")):
            self.assertEqual(scalar(rewards[name], "add_political_power"), budget)
        district_check = block(rewards["STP_PARTY_DISCIPLINE"], "3")
        live = {("3", "is_owned_by", "ROOT"): True, ("3", "is_controlled_by", "ROOT"): True,
                ("3", "STP_region_is_operable", "yes"): True}
        self.assertEqual(scalar([e for _, e in selected_effects(district_check, live, "3")], "STP_cw_secure_party_district"), "yes")
        self.assertFalse(list(selected_effects(district_check, {}, "3")), "lost districts are not silently purged")
        administration = block(block(rewards["STP_cw_district_administration"], "hidden_effect"), "3")
        self.assertEqual(scalar([e for _, e in selected_effects(administration, {}, "3")], "set_state_flag"),
                         "STP_resistance_administration_asset")
        self.assertEqual(scalar(block(administration, "set_temp_variable"), "value"), "12")
        supply = rewards["STP_cw_supply_officers"]
        district = block(supply, "46")
        self.assertEqual(scalar(block(district, "set_temp_variable"), "value"), "10")
        self.assertEqual(scalar(district, "STP_add_resistance_influence"), "yes")
        self.assertNotIn("set_state_flag", {e.key for e in walk(district)}, "the supply depot is earned by its unlocked operation")
        pending = {scalar(e.value, "var"): float(scalar(e.value, "value")) for e in walk(block(supply, "hidden_effect"))
                   if e.key == "add_to_variable"}
        self.assertEqual(pending, {"STP_cw_pending_army_planning_speed": .20,
                                   "STP_cw_pending_army_supply_consumption_factor": -.15})
        self.assertNotIn("STP_cw_refresh_army_modifier", {e.key for e in walk(supply)}, "the future STS army receives this package")

    def test_prepared_supply_lines_is_a_real_temporary_spirit(self):
        ideas = block(block(entries("common/ideas/ADISCORD_STP_civil_war_ideas.txt"), "ideas"), "country")
        supply = block(ideas, "STP_cw_prepared_supply_lines")
        self.assertFalse(any(e.key == "name" for e in supply), "the timed result must not impersonate a dummy aggregate")
        self.assertEqual(scalar(block(supply, "allowed"), "always"), "no")
        self.assertEqual(scalar(supply, "removal_cost"), "-1")
        self.assertEqual({e.key: float(e.value) for e in block(supply, "modifier")},
                         {"supply_consumption_factor": -.10, "army_org_regain": .05})

        effects = entries("common/scripted_effects/ADISCORD_STP_scripted_effects.txt")
        start = block(block(effects, "STP_cw_begin_hostilities"), "if")
        first_time = next(e for e in start if e.key == "if"
                         and any(v.key == "set_global_flag" and v.value == "STP_cw_started" for v in walk(e.value)))
        delivery = next(e for e in first_time.value if e.key == "if"
                        and any(v.key == "add_timed_idea" and scalar(v.value, "idea") == "STP_cw_prepared_supply_lines"
                                for v in walk(e.value)))
        cleanup_index = next(i for i, e in enumerate(first_time.value) if e.key == "STP_end_battle_for_stelander")
        self.assertLess(first_time.value.index(delivery), cleanup_index, "read depot ownership before the war-start cleanup")
        self.assertNotIn("STP_resistance_supply_asset", {e.value for e in walk(block(effects, "STP_cw_materialize_region_assets"))
                                                        if e.key == "clr_state_flag"})
        for owned, ready, expected in (((), (), 0), (("3", "46"), (), 0),
                                       ((), ("3", "46"), 0), (("3",), ("46",), 0),
                                       (("3",), ("3",), 1), (("46",), ("46",), 1),
                                       (("3", "46"), ("3", "46"), 1)):
            with self.subTest(owned=owned, ready=ready):
                facts = {(state, "is_owned_by", "STS"): True for state in owned}
                facts.update({(state, "has_state_flag", "STP_resistance_supply_asset"): True for state in ready})
                issued = [(scope, scalar(e.value, "idea"), scalar(e.value, "days"))
                          for scope, e in selected_effects([delivery], facts) if e.key == "add_timed_idea"]
                self.assertEqual(issued, [("STS", "STP_cw_prepared_supply_lines", "21")] * expected)

    def test_related_operations_require_the_focus_that_unlocks_them(self):
        decisions = block(entries("common/decisions/ADISCORD_STP_decisions.txt"), "STP_battle_for_stelander")
        for name, focus in (("STP_cw_delay_inspection", "STP_Count_The_Loyalists"),
                            ("STP_cw_sacrifice_local_contact", "STP_Call_For_Shabrat"),
                            ("STP_cw_open_civil_registers", "STP_cw_national_mandate"),
                            ("STP_region_unique_operation_46", "STP_cw_supply_officers"),
                            ("STP_cw_check_district_command", "STP_PARTY_DISCIPLINE"),
                            ("STP_cw_interrupt_opposition", "STP_cw_security_collegium"),
                            ("STP_cw_publish_directive", "STP_cw_press_office"),
                            ("STP_cw_seal_protocol", "STP_cw_protocol_office"),
                            ("STP_cw_sabotage_capital", "STP_cw_prepare_capital_sabotage"),
                            ("STP_cw_sabotage_party_industry", "STP_cw_prepare_industry_sabotage")):
            with self.subTest(decision=name):
                decision = block(decisions, name)
                gates = {e.value for section in decision if section.key in ("visible", "available")
                         for e in walk(section.value) if e.key == "has_completed_focus"}
                self.assertIn(focus, gates, "a native unlock preview alone does not gate an operation")

    def test_operational_orders_deliver_training_and_a_timed_plan_to_sts(self):
        start = block(block(entries("common/scripted_effects/ADISCORD_STP_scripted_effects.txt"), "STP_cw_begin_hostilities"), "if")
        orders = next(e.value for e in walk(start) if e.key == "if"
                      and any(v.key == "has_country_flag" and v.value == "STP_cw_early_orders_ready"
                              for v in walk(block(e.value, "limit"))))
        recipient = block(orders, "STS")
        timed = block(recipient, "add_timed_idea")
        self.assertEqual((scalar(timed, "idea"), scalar(timed, "days")), ("STP_cw_offensive_preparation", "35"))
        self.assertEqual((scalar(recipient, "army_experience"), scalar(recipient, "add_command_power")), ("10", "15"))

    def test_dummy_deltas_match_the_actual_dynamic_variable_writes(self):
        dynamics = {e.key: e.value for e in entries("common/dynamic_modifiers/ADISCORD_dynamic_modifiers_STP.txt")
                    if e.key.startswith("STP_cw_")}
        bindings = {e.value: (name, e.key) for name, body in dynamics.items() for e in body
                    if isinstance(e.value, str) and e.value.startswith("STP_cw_")}
        ideas = {e.key: e.value for e in block(block(entries("common/ideas/ADISCORD_STP_civil_war_ideas.txt"), "ideas"), "country")}
        checked = set()
        for tree in entries("common/national_focus/ADISCORD_national_focus_STP.txt"):
            for focus in (e.value for e in tree.value if e.key == "focus"):
                reward = block(focus, "completion_reward")
                shown = {}
                actual = {}
                for section in reward:
                    if section.key == "effect_tooltip":
                        for swap in (e.value for e in walk(section.value) if e.key == "swap_ideas"):
                            old, new = scalar(swap, "remove_idea"), scalar(swap, "add_idea")
                            if old not in ideas or not old.endswith("_dummy_idea"):
                                continue
                            aggregate = scalar(ideas[old], "name")
                            if aggregate not in dynamics:
                                self.assertEqual(aggregate, "STP_fading_father", "add a contract for this preview")
                                continue  # The starting health setter has its own stage-to-stage contract.
                            self.assertEqual(scalar(ideas[new], "name"), aggregate)
                            for idea, sign in ((old, -1), (new, 1)):
                                modifiers = next((e.value for e in ideas[idea] if e.key == "modifier"), [])
                                for modifier in modifiers:
                                    key = (aggregate, modifier.key)
                                    shown[key] = shown.get(key, 0) + sign * float(modifier.value)
                    elif section.key == "hidden_effect":
                        for effect in walk(section.value):
                            if effect.key != "add_to_variable":
                                continue
                            variable = scalar(effect.value, "var")
                            variable = variable.replace("STP_cw_pending_army_", "STP_cw_army_")
                            if variable in bindings:
                                key = bindings[variable]
                                actual[key] = actual.get(key, 0) + float(scalar(effect.value, "value"))
                if shown or actual:
                    self.assertEqual(shown, actual, scalar(focus, "id"))
                    checked.add(scalar(focus, "id"))
        self.assertEqual(len(checked), 29, "every persistent focus reward needs a checked delta preview")
        self.assertTrue({"STP_cw_frontline_relief", "STP_cw_route_columns"} <= checked)

    def test_dummy_ideas_are_never_installed_as_gameplay_spirits(self):
        definitions = block(block(entries("common/ideas/ADISCORD_STP_civil_war_ideas.txt"), "ideas"), "country")
        dynamics = {e.key for e in entries("common/dynamic_modifiers/ADISCORD_dynamic_modifiers_STP.txt")}
        dummy_ids = {e.key for e in definitions if any(v.key == "name" and isinstance(v.value, str)
                                                     and v.value in dynamics for v in e.value)}
        self.assertTrue(dummy_ids)
        def executed(items):
            for entry in items:
                if entry.key == "effect_tooltip":
                    continue
                yield entry
                if isinstance(entry.value, list):
                    yield from executed(entry.value)
        for path in ("common/national_focus/ADISCORD_national_focus_STP.txt",
                     "common/scripted_effects/ADISCORD_STP_scripted_effects.txt"):
            for entry in executed(entries(path)):
                if entry.key in ("add_ideas", "remove_ideas", "add_idea", "remove_idea", "idea"):
                    if isinstance(entry.value, str):
                        self.assertNotIn(entry.value, dummy_ids, path)

    def test_dynamic_vectors_initialize_once_and_refresh_without_reset(self):
        effects = entries("common/scripted_effects/ADISCORD_STP_scripted_effects.txt")
        initialize = block(block(effects, "STP_cw_initialize_focus_modifiers"), "if")
        self.assertEqual(scalar(block(block(initialize, "limit"), "NOT"), "has_country_flag"),
                         "STP_cw_focus_modifiers_initialized")
        initialized = {scalar(e.value, "var") for e in initialize if e.key == "set_variable"
                       and scalar(e.value, "value") == "0"}
        self.assertIn("STP_cw_pending_army_supply_consumption_factor", initialized)
        dynamics = [e for e in entries("common/dynamic_modifiers/ADISCORD_dynamic_modifiers_STP.txt")
                    if e.key in ("STP_cw_resistance_network_dynamic", "STP_cw_party_administration_dynamic",
                                 "STP_cw_military_staff_dynamic")]
        for dynamic in dynamics:
            variables = {e.value for e in dynamic.value if isinstance(e.value, str) and e.value.startswith("STP_cw_")}
            self.assertTrue(variables <= initialized, dynamic.key)
        for name in ("STP_cw_refresh_network_modifier", "STP_cw_refresh_party_modifier", "STP_cw_refresh_army_modifier"):
            refresh = block(effects, name)
            self.assertEqual(scalar(refresh, "force_update_dynamic_modifier"), "yes")
            self.assertFalse(any(e.key in ("set_variable", "clear_variable") for e in walk(refresh)), name)

    def test_each_independent_army_preparation_survives_handoff_exactly_once(self):
        effects = entries("common/scripted_effects/ADISCORD_STP_scripted_effects.txt")
        transfer = block(effects, "STP_cw_transfer_preparation_modifiers")
        cleanup = block(effects, "STP_cw_clear_resistance_modifiers")
        stats = ("org_factor", "planning_speed", "org_regain", "supply_consumption_factor")
        scenarios = ((0, 0, 0, 0), (0, 0, 0, -.08), (0, 0, .15, 0), (.13, .30, .25, -.16))
        for values in scenarios:
            with self.subTest(pending=values):
                facts = {("STP", "variable", "STP_cw_pending_army_" + stat): value
                         for stat, value in zip(stats, values)}
                inherited = {}
                for attempt in range(2):
                    selected = list(selected_effects(transfer, facts))
                    army = [(scope, e) for scope, e in selected if e.key == "set_variable"
                            and scalar(e.value, "var").startswith("STP_cw_army_")]
                    self.assertEqual(len(army), 4 if any(values) and attempt == 0 else 0)
                    refreshed = [(scope, e.value) for scope, e in selected if e.key == "STP_cw_refresh_army_modifier"]
                    self.assertEqual(refreshed, [("STS", "yes")] if army else [])
                    for scope, entry in army:
                        self.assertEqual(scope, "STS")
                        donor, variable = scalar(entry.value, "value").split(".", 1)
                        inherited[scalar(entry.value, "var")] = facts[(donor, "variable", variable)]
                    self.assertTrue(any(e.key == "STP_cw_clear_resistance_modifiers" for _, e in selected))
                    for entry in cleanup:
                        if entry.key == "clear_variable":
                            facts.pop(("STP", "variable", entry.value), None)
                self.assertEqual(inherited, {"STP_cw_army_" + stat: value for stat, value in zip(stats, values)}
                                 if any(values) else {})

    def test_resistance_receives_the_network_and_pending_army_vector(self):
        effects = entries("common/scripted_effects/ADISCORD_STP_scripted_effects.txt")
        start = block(block(effects, "STP_cw_start"), "if")
        calls = [e.key for e in start]
        self.assertLess(calls.index("STP_cw_transfer_preparation_modifiers"), calls.index("load_focus_tree"))
        transfer = block(effects, "STP_cw_transfer_preparation_modifiers")
        sts = [e.value for e in walk(transfer) if e.key == "STS"]
        copied = {scalar(e.value, "var"): scalar(e.value, "value") for scope in sts for e in walk(scope)
                  if e.key == "set_variable"}
        self.assertEqual(copied, {
            "STP_cw_network_political_power_gain": "STP.STP_cw_network_political_power_gain",
            "STP_cw_army_org_factor": "STP.STP_cw_pending_army_org_factor",
            "STP_cw_army_planning_speed": "STP.STP_cw_pending_army_planning_speed",
            "STP_cw_army_org_regain": "STP.STP_cw_pending_army_org_regain",
            "STP_cw_army_supply_consumption_factor": "STP.STP_cw_pending_army_supply_consumption_factor",
            "STP_cw_mandate_org_regain": "STP.STP_cw_mandate_org_regain",
            "STP_cw_mandate_core_defence": "STP.STP_cw_mandate_core_defence",
            "STP_cw_mandate_training_time": "STP.STP_cw_mandate_training_time",
            "STP_cw_mandate_mobilization": "STP.STP_cw_mandate_mobilization",
        })
        self.assertIn("STP_cw_clear_resistance_modifiers", {e.key for e in transfer})
        cleanup = block(entries("common/scripted_effects/ADISCORD_STP_scripted_effects.txt"), "STP_cw_clear_resistance_modifiers")
        removed = {scalar(e.value, "modifier") for e in walk(cleanup) if e.key == "remove_dynamic_modifier"}
        self.assertEqual(removed, {"STP_cw_resistance_network_dynamic"})
        for dynamic in entries("common/dynamic_modifiers/ADISCORD_dynamic_modifiers_STP.txt"):
            if dynamic.key in ("STP_cw_resistance_network_dynamic", "STP_cw_military_staff_dynamic"):
                tags = {e.value for e in walk(block(dynamic.value, "enable")) if e.key == "tag"}
                self.assertIn("STS", tags)

    def test_supply_focus_transfers_its_army_package_without_officer_contacts(self):
        transfer = block(entries("common/scripted_effects/ADISCORD_STP_scripted_effects.txt"), "STP_cw_transfer_preparation_modifiers")
        army = next(e for e in transfer if e.key == "if"
                    and any(v.key == "set_variable" and scalar(v.value, "var") == "STP_cw_army_planning_speed"
                            for v in walk(e.value)))
        tree = next(e.value for e in entries("common/national_focus/ADISCORD_national_focus_STP.txt")
                    if e.key == "focus_tree" and scalar(e.value, "id") == "STP_focus")
        for focus_id in ("STP_cw_supply_officers", "STP_cw_warehouse_inventory",
                         "STP_No_Mercenaries_In_Our_Mountains", "STP_cw_officer_contacts"):
            with self.subTest(route=focus_id):
                focus = next(e.value for e in tree if e.key == "focus" and scalar(e.value, "id") == focus_id)
                pending = {("STP", "variable", scalar(e.value, "var")): float(scalar(e.value, "value"))
                           for _, e in selected_effects(block(focus, "completion_reward"), {})
                           if e.key == "add_to_variable" and scalar(e.value, "var").startswith("STP_cw_pending_army_")}
                self.assertTrue(pending, "the focus itself must earn the transferred package")
                chosen = list(selected_effects([army], pending))
                copied = {scalar(e.value, "var"): scalar(e.value, "value")
                          for scope, e in chosen if scope == "STS" and e.key == "set_variable"}
                self.assertEqual(copied.get("STP_cw_army_planning_speed"), "STP.STP_cw_pending_army_planning_speed")
                self.assertEqual(copied.get("STP_cw_army_supply_consumption_factor"), "STP.STP_cw_pending_army_supply_consumption_factor")
                self.assertIn(("STS", "STP_cw_refresh_army_modifier"), [(scope, e.key) for scope, e in chosen])
        self.assertEqual(list(selected_effects([army], {})), [], "no unearned army package")

    def test_preparation_installs_native_legitimacy_once_without_reset_at_death(self):
        effects = entries("common/scripted_effects/ADISCORD_STP_scripted_effects.txt")
        opening = block(block(effects, "STP_cw_open_preparation"), "if")
        installs = [e.value for e in walk(opening) if e.key == "if"
                    and any(v.key == "set_power_balance" for v in e.value)]
        self.assertEqual(len(installs), 1)
        install = installs[0]
        self.assertEqual(scalar(block(block(install, "limit"), "NOT"), "has_country_flag"),
                         "STP_cw_legitimacy_initialized")
        self.assertEqual(scalar(block(install, "set_power_balance"), "id"), "STP_shabrat_election_legitimacy")
        self.assertIn(("set_country_flag", "STP_cw_legitimacy_initialized"),
                      [(e.key, e.value) for e in install if isinstance(e.value, str)])
        begin = block(effects, "STP_cw_begin_elections")
        self.assertIn("STP_cw_open_preparation", {e.key for e in walk(begin)})
        self.assertNotIn("set_power_balance", {e.key for e in walk(begin)})

    def test_election_timeout_cannot_remove_its_own_active_mission(self):
        effects = {e.key: e.value for e in entries("common/scripted_effects/ADISCORD_STP_scripted_effects.txt")}
        mission = block(block(entries("common/decisions/ADISCORD_STP_decisions.txt"), "STP_battle_for_stelander"), "STP_cw_election_window")
        def expand_calls(items, chain=()):
            for e in items:
                if e.key in effects and e.value == "yes":
                    self.assertNotIn(e.key, chain)
                    yield from expand_calls(effects[e.key], (*chain, e.key))
                elif isinstance(e.value, list):
                    yield from expand_calls(e.value, chain)
                else:
                    yield e
        immediate = list(expand_calls(block(mission, "timeout_effect")))
        self.assertNotIn("remove_mission", {e.key for e in immediate})
        self.assertNotIn("load_focus_tree", {e.key for e in immediate})
        deferred = next(e.value for e in entries("events/ADISCORD_STP_events.txt") if e.key == "country_event" and scalar(e.value, "id") == "ADISCORD_STP_cw.10")
        self.assertEqual(scalar(block(deferred, "trigger"), "STP_cw_can_start"), "yes")
        self.assertEqual(scalar(block(deferred, "immediate"), "STP_cw_start"), "yes")

    def test_election_deadline_freezes_native_result_before_starting_war(self):
        effects = entries("common/scripted_effects/ADISCORD_STP_scripted_effects.txt")
        finish = block(block(effects, "STP_cw_finish_elections"), "if")
        gate = block(finish, "limit")
        facts = {("STP", "has_country_flag", "STP_cw_elections_started"): True}
        self.assertTrue(matches_conditions(gate, facts))
        self.assertFalse(matches_conditions(gate, {}), "an event before elections cannot announce a result")
        for key, flag in (("has_country_flag", "STP_cw_elections_finished"), ("has_global_flag", "STP_cw_started")):
            self.assertFalse(matches_conditions(gate, {**facts, ("STP", key, flag): True}), flag)
        body = [e for e in finish if e.key != "limit"]
        for value, winner in ((-1, "party"), (0.1, "party"), (0.1001, "shabrat"), (1, "shabrat")):
            with self.subTest(legitimacy=value):
                scenario = {**facts, ("STP", "power_balance_value", "STP_shabrat_election_legitimacy"): value}
                result = list(selected_effects(body, scenario))
                flags = [e.value for scope, e in result if scope == "STP" and e.key == "set_country_flag"]
                self.assertEqual(set(flags) & {"STP_cw_party_election_victory", "STP_cw_shabrat_election_victory"},
                                 {f"STP_cw_{winner}_election_victory"})
                self.assertIn("STP_cw_elections_finished", flags)
                self.assertNotIn("STP_cw_postwar", flags)
                calls = [e.key for _, e in result]
                self.assertNotIn("STP_cw_start", calls)
                split = next(e.value for _, e in result if e.key == "country_event" and scalar(e.value, "id") == "ADISCORD_STP_cw.10")
                self.assertEqual(scalar(split, "hours"), "1")
                last_result = max(i for i, (_, e) in enumerate(result) if e.key == "set_country_flag"
                                  and e.value in {"STP_cw_elections_finished", f"STP_cw_{winner}_election_victory"})
                self.assertLess(last_result, calls.index("country_event"))
        self.assertFalse({"STP_end_battle_for_stelander", "STP_cw_return_preparation_reserves",
                          "STP_cw_clear_resistance_modifiers", "load_focus_tree", "load_oob"}
                         & {e.key for e in walk(finish)}, "the split owns payouts, assets and the wartime tree")
        mission = block(block(entries("common/decisions/ADISCORD_STP_decisions.txt"), "STP_battle_for_stelander"),
                        "STP_cw_election_window")
        self.assertEqual(scalar(mission, "days_mission_timeout"), "140")
        self.assertEqual(scalar(block(mission, "timeout_effect"), "STP_cw_finish_elections"), "yes")

    def test_resistance_cleanup_clears_only_its_preparation_vector(self):
        effects = entries("common/scripted_effects/ADISCORD_STP_scripted_effects.txt")
        clear = block(effects, "STP_cw_clear_resistance_modifiers")
        cleared = {e.value for e in clear if e.key == "clear_variable"}
        self.assertEqual(cleared, {"STP_cw_network_political_power_gain", "STP_cw_pending_army_org_factor",
                                  "STP_cw_pending_army_planning_speed", "STP_cw_pending_army_org_regain",
                                  "STP_cw_pending_army_supply_consumption_factor"})
        removed = [scalar(e.value, "modifier") for e in walk(clear) if e.key == "remove_dynamic_modifier"]
        self.assertEqual(removed, ["STP_cw_resistance_network_dynamic"])

    def test_resistance_cleanup_skips_absent_modifier_but_always_clears_its_vector(self):
        clear = block(entries("common/scripted_effects/ADISCORD_STP_scripted_effects.txt"),
                      "STP_cw_clear_resistance_modifiers")
        vector = {"STP_cw_network_political_power_gain", "STP_cw_pending_army_org_factor",
                  "STP_cw_pending_army_planning_speed", "STP_cw_pending_army_org_regain",
                  "STP_cw_pending_army_supply_consumption_factor"}
        for present in (False, True):
            for value in (0, .15):
                with self.subTest(modifier_present=present, value=value):
                    facts = {("STP", "has_dynamic_modifier", "STP_cw_resistance_network_dynamic"): present}
                    facts.update({("STP", "variable", name): value for name in vector})
                    executed = list(selected_effects(clear, facts))
                    removed = [scalar(e.value, "modifier") for _, e in executed if e.key == "remove_dynamic_modifier"]
                    self.assertEqual(removed, ["STP_cw_resistance_network_dynamic"] if present else [],
                                     "the party route and repeated cleanup must not remove an absent modifier")
                    self.assertEqual({e.value for _, e in executed if e.key == "clear_variable"}, vector,
                                     "zero and stale values must clear even when no modifier is attached")
                    self.assertIn(("STP", "force_update_dynamic_modifier", "yes"),
                                  [(scope, e.key, e.value) for scope, e in executed if isinstance(e.value, str)])

    def test_other_cleanup_skips_each_absent_modifier_without_skipping_resets(self):
        effects = entries("common/scripted_effects/ADISCORD_STP_scripted_effects.txt")
        cases = (
            ("STP_cw_clear_political_modifiers", ("STP_cw_party_administration_dynamic", "STP_fading_father"),
             {"STP_cw_party_political_power_gain", "STP_cw_party_stability_factor", "STP_cw_party_command_power_gain_mult"},
             {"STP_fading_father_stability_factor": "0"}),
            ("STP_end_battle_for_stelander", ("STP_party_suspicion_dynamic_modifier",),
             {"STP_sus_political_power_factor"}, {}),
        )
        for name, modifiers, cleared_variables, resets in cases:
            for mask in range(1 << len(modifiers)):
                present = {modifier for index, modifier in enumerate(modifiers) if mask & (1 << index)}
                with self.subTest(helper=name, present=present):
                    facts = {("STP", "has_global_flag", "STP_cw_started"): True}
                    facts.update({("STP", "has_dynamic_modifier", modifier): modifier in present for modifier in modifiers})
                    facts.update({("STP", "variable", variable): 0 for variable in cleared_variables})
                    executed = list(selected_effects(block(effects, name), facts))
                    self.assertEqual({scalar(e.value, "modifier") for _, e in executed if e.key == "remove_dynamic_modifier"}, present)
                    self.assertTrue(cleared_variables <= {e.value for _, e in executed if e.key == "clear_variable"})
                    actual_resets = {scalar(e.value, "var"): scalar(e.value, "value")
                                     for _, e in executed if e.key == "set_variable"}
                    self.assertEqual(actual_resets, resets)
                    self.assertTrue(any(e.key == "force_update_dynamic_modifier" for _, e in executed))

    def test_election_campaigns_release_their_slot_once_and_cancel_without_late_rewards(self):
        category = block(entries("common/decisions/ADISCORD_STP_decisions.txt"), "STP_shabrat_election_bop_category")
        for name, cost, days, delta in (("STP_cw_negotiate_with_delegates", "25", "14", .06),
                                       ("STP_cw_open_election_campaign", "50", "21", .12)):
            decision = block(category, name)
            self.assertEqual((scalar(decision, "cost"), scalar(decision, "days_remove")), (cost, days))
            started = list(selected_effects(block(decision, "complete_effect"), {}))
            self.assertEqual(sum(e.key == "STP_political_action_slot_consume" for _, e in started), 1)
            flag = next(e.value for _, e in started if e.key == "set_country_flag")
            reserved = {("STP", "has_country_flag", flag): True}
            live = {**reserved, ("STP", "has_active_mission", "STP_cw_election_window"): True,
                    ("STP", "STP_cw_preparation_open", "yes"): True,
                    ("STP", "STP_cw_public_campaign_basis", "yes"): True}
            for side, sign in (("STP_sided_with_Maksim_flag", 1), ("STP_sided_with_the_party_flag", -1)):
                with self.subTest(decision=name, side=side):
                    facts = {**live, ("STP", "has_country_flag", side): True}
                    self.assertFalse(matches_conditions(block(decision, "cancel_trigger"), facts))
                    delivered = list(selected_effects(block(decision, "remove_effect"), facts))
                    shifts = [e.value for _, e in delivered if e.key == "add_power_balance_value"]
                    self.assertEqual(len(shifts), 1)
                    self.assertEqual(scalar(shifts[0], "id"), "STP_shabrat_election_legitimacy")
                    self.assertAlmostEqual(float(scalar(shifts[0], "value")), sign * delta)
                    preview = block(block(decision, "remove_effect"), "effect_tooltip")
                    shown = list(selected_effects(preview, {("STP", "has_country_flag", side): True}))
                    shown_shifts = [e.value for _, e in shown if e.key == "add_power_balance_value"]
                    self.assertEqual(len(shown_shifts), 1, "preview must work before the player owns a campaign slot")
                    self.assertEqual(scalar(shown_shifts[0], "id"), scalar(shifts[0], "id"))
                    self.assertEqual(scalar(shown_shifts[0], "value"), scalar(shifts[0], "value"))
                    actual_stability = [e.value for _, e in delivered if e.key == "add_stability"]
                    self.assertEqual([e.value for _, e in shown if e.key == "add_stability"], actual_stability)
                    self.assertEqual(actual_stability, ["-0.02"] if name == "STP_cw_open_election_campaign" else [])
                    self.assertEqual(sum(e.key == "STP_political_action_slot_release" for _, e in delivered), 1)
                    self.assertIn(("clr_country_flag", flag), [(e.key, e.value) for _, e in delivered if isinstance(e.value, str)])
            self.assertTrue(matches_conditions(block(decision, "cancel_trigger"), reserved))
            for phase in ("cancel_effect", "remove_effect"):
                closed = list(selected_effects(block(decision, phase), reserved))
                self.assertEqual(sum(e.key == "STP_political_action_slot_release" for _, e in closed), 1)
                self.assertFalse({"add_power_balance_value", "add_stability"} & {e.key for _, e in closed})
                self.assertIn(("clr_country_flag", flag), [(e.key, e.value) for _, e in closed if isinstance(e.value, str)])
                repeated = list(selected_effects(block(decision, phase), live | {("STP", "has_country_flag", flag): False}))
                self.assertFalse({"STP_political_action_slot_release", "add_power_balance_value", "add_stability"}
                                 & {e.key for _, e in repeated}, "a late second callback owns neither a slot nor a reward")

    def test_civil_authority_clears_politics_and_preserves_the_army_vector(self):
        effects = entries("common/scripted_effects/ADISCORD_STP_scripted_effects.txt")
        clear = block(effects, "STP_cw_clear_political_modifiers")
        self.assertIn("STP_cw_clear_resistance_modifiers", {e.key for e in clear})
        removed = {scalar(e.value, "modifier") for e in walk(clear) if e.key == "remove_dynamic_modifier"}
        self.assertEqual(removed, {"STP_cw_party_administration_dynamic", "STP_fading_father"})
        self.assertFalse(any(e.key == "clear_variable" and e.value.startswith("STP_cw_army_") for e in clear))
        self.assertFalse(any(e.key == "clr_country_flag" and e.value == "STP_ivanov_dead" for e in clear))
        changed_variables = {scalar(e.value, "var") for e in clear if e.key == "set_variable"}
        changed_variables.update(e.value for e in clear if e.key == "clear_variable")
        self.assertNotIn("STP_leader_health_stage", changed_variables)
        tree = next(e.value for e in entries("common/national_focus/ADISCORD_national_focus_STP.txt")
                    if scalar(e.value, "id") == "STP_cw_focus")
        focus = next(e.value for e in tree if e.key == "focus" and scalar(e.value, "id") == "STP_cw_restore_civil_authority")
        self.assertIn("STP_cw_clear_political_modifiers", {e.key for e in walk(block(focus, "completion_reward"))})

    def test_closed_preparation_removes_suspicion_and_its_display(self):
        finish = block(entries("common/scripted_effects/ADISCORD_STP_scripted_effects.txt"), "STP_end_battle_for_stelander")
        closure = block(finish, "if")
        closed_phases = {(e.key, e.value) for e in block(block(closure, "limit"), "OR")}
        self.assertEqual(closed_phases, {("has_global_flag", "STP_cw_started"),
                                         ("has_country_flag", "STP_cw_elections_finished")},
                         "a preparation-map debug reset must preserve the active suspicion modifier")
        removed = {scalar(e.value, "modifier") for e in walk(closure) if e.key == "remove_dynamic_modifier"}
        self.assertIn("STP_party_suspicion_dynamic_modifier", removed)
        self.assertIn("STP_sus_political_power_factor", {e.value for e in closure if e.key == "clear_variable"})
        category = block(entries("common/decisions/categories/ADISCORD_decision_categories_STP.txt"), "STP_elections_in_the_party")
        excluded = {(e.key, e.value) for condition in block(category, "visible") if condition.key == "NOT"
                    for e in condition.value if isinstance(e.value, str)}
        self.assertEqual(excluded, {("has_global_flag", "STP_cw_started"),
                                    ("has_country_flag", "STP_cw_elections_finished")})

    def test_dynamic_and_dummy_display_names_and_icons_resolve(self):
        definitions = block(block(entries("common/ideas/ADISCORD_STP_civil_war_ideas.txt"), "ideas"), "country")
        localization = "\n".join((ROOT / path).read_text(encoding="utf-8-sig") for path in (
            "localisation/russian/ADISCORD_STP_l_russian.yml",
            "localisation/russian/ADISCORD_ideas_l_russian.yml",
        ))
        keys = set(re.findall(r"(?m)^\s*([^\s:#]+):", localization))
        gfx = (ROOT / "interface/ADISCORD_ideas.gfx").read_text(encoding="utf-8-sig")
        for idea in definitions:
            name = next((e.value for e in idea.value if e.key == "name"), idea.key)
            self.assertIn(name, keys)
            self.assertIn(f"{name}_desc", keys)
            picture = next((e.value for e in idea.value if e.key == "picture"), None)
            if picture:
                sprite = picture if picture.startswith("GFX_idea_") else f"GFX_idea_{picture}"
                self.assertIn(f'"{sprite}"', gfx)
        for dynamic in entries("common/dynamic_modifiers/ADISCORD_dynamic_modifiers_STP.txt"):
            if dynamic.key.startswith("STP_cw_"):
                self.assertIn(dynamic.key, keys)
                self.assertIn(f'"{scalar(dynamic.value, "icon")}"', gfx)

    def test_independent_focus_routes_fit_the_preparation_calendar(self):
        tree = next(e.value for e in entries("common/national_focus/ADISCORD_national_focus_STP.txt")
                    if e.key == "focus_tree" and scalar(e.value, "id") == "STP_focus")
        focuses = {scalar(e.value, "id"): e.value for e in tree if e.key == "focus"}
        root = "STP_Show_Him_The_Truth"

        def required_paths(name, ancestors=frozenset()):
            self.assertNotIn(name, ancestors, "focus prerequisite cycle")
            if name == root:
                return [frozenset()]
            paths = [frozenset({name})]
            for group in (e.value for e in focuses[name] if e.key == "prerequisite"):
                alternatives = [route for ref in group for route in required_paths(ref.value, ancestors | {name})]
                paths = [path | route for path in paths for route in alternatives]
            return paths

        def days(path):
            return sum(float(scalar(focuses[name], "cost")) * 7 for name in path)

        route = min(required_paths("STP_THE_MOUNTAIN_WINDOW"), key=days)
        self.assertEqual(route, {"STP_cw_officer_contacts", "STP_Garrisons_Hesitate", "STP_THE_MOUNTAIN_WINDOW"})
        self.assertEqual(days(route), 70)
        for name in route:
            self.assertNotIn("STP_Call_For_Shabrat", {e.value for e in walk(block(focuses[name], "available"))
                                                     if e.key == "has_completed_focus"})
        for name in ("STP_ADRESS_PARTY_CRISIS", "STP_cw_officer_contacts", "STP_cw_northern_dossier"):
            self.assertEqual(scalar(block(focuses[name], "prerequisite"), "focus"), root)
            self.assertEqual(scalar(focuses[name], "y"), "1")

        decisions = block(entries("common/decisions/ADISCORD_STP_decisions.txt"), "STP_battle_for_stelander")
        events = entries("common/decisions/ADISCORD_STP_decisions.txt")
        health = next(e.value for category in events for e in category.value if e.key == "ivanov_health_is_getting_worse")
        schedule = block(entries("common/scripted_effects/ADISCORD_STP_scripted_effects.txt"), "STP_cw_schedule_health")
        adjustment = block(schedule, "add_days_mission_timeout")
        stage_days = int(scalar(health, "days_mission_timeout")) + int(scalar(adjustment, "days"))
        preparation_days = 3 * stage_days + int(scalar(block(decisions, "STP_cw_election_window"), "days_mission_timeout"))
        self.assertEqual(preparation_days, 287)


        for name, decision in (("STP_cw_defensive_lines", "STP_cw_prepare_defensive_line"),
                               ("STP_cw_heavy_reserve", "STP_cw_prepare_assault_group")):
            self.assertLessEqual(min(map(days, required_paths(name))) + int(scalar(block(decisions, decision), "days_remove")), preparation_days,
                                 "a focus must leave time to finish its paid operation")
        mandate = min(required_paths("STP_cw_national_mandate"), key=days)
        self.assertEqual(days(mandate), 91)
        public_ready = days(mandate | {"STP_cw_officer_contacts"}) + int(scalar(block(decisions, "STP_cw_secure_election_result"), "days_remove"))
        self.assertLessEqual(public_ready, preparation_days)
        all_military = min(required_paths("STP_cw_abila_reserve"), key=days) | route
        funded_political = set().union(*(min(required_paths(name), key=days) for name in (
            "STP_cw_national_mandate", "STP_cw_courier_service", "STP_cw_pay_officials")))
        self.assertEqual(days(funded_political | all_military), 336)
        self.assertGreater(days(funded_political | all_military), preparation_days,
                           "the funded political route and deep military route cannot both finish before the election")
        courier_reward = block(focuses["STP_cw_courier_service"], "completion_reward")
        self.assertEqual(sum(e.key == "STP_political_action_slot_grant" for e in walk(courier_reward)), 1)

    def test_credentials_review_reads_real_administrations_and_stops_with_elections(self):
        groups = entries("common/decisions/ADISCORD_STP_decisions.txt")
        mission = block(block(groups, "STP_shabrat_election_bop_category"), "STP_cw_credentials_review")
        self.assertEqual(scalar(mission, "days_mission_timeout"), "35")
        self.assertFalse(matches_conditions(block(mission, "available"), {}))
        active = {("STP", "STP_cw_preparation_open", "yes"): True,
                  ("STP", "has_active_mission", "STP_cw_election_window"): True}
        for first in (False, True):
            for second in (False, True):
                facts = dict(active)
                for state, exists in (("2", first), ("3", second)):
                    for key, value in (("is_owned_by", "ROOT"), ("is_controlled_by", "ROOT"),
                                       ("has_state_flag", "STP_resistance_administration_asset")):
                        facts[(state, key, value)] = exists
                writes = list(selected_effects(block(mission, "timeout_effect"), facts))
                losses = [float(scalar(e.value, "value")) for _, e in writes if e.key == "add_power_balance_value"]
                self.assertAlmostEqual(sum(losses), -.08 * (2 - first - second))
                self.assertFalse(matches_conditions(block(mission, "cancel_trigger"), facts))
                for missing in active:
                    self.assertTrue(matches_conditions(block(mission, "cancel_trigger"), {**facts, missing: False}))
                    late = list(selected_effects(block(mission, "timeout_effect"), {**facts, missing: False}))
                    self.assertFalse(any(e.key == "add_power_balance_value" for _, e in late),
                                     "an election ending on the same tick must not lose its frozen mandate")
        event = next(e.value for e in entries("events/ADISCORD_STP_events.txt") if e.key == "country_event"
                     and scalar(e.value, "id") == "ADISCORD_STP_preparation.17")
        facts = {**active, ("STP", "has_country_flag", "STP_sided_with_Maksim_flag"): True}
        self.assertTrue(matches_conditions(block(event, "trigger"), facts))
        for missing in facts:
            self.assertFalse(matches_conditions(block(event, "trigger"), {**facts, missing: False}))
        self.assertFalse(matches_conditions(block(event, "trigger"), {**facts, ("STP", "has_active_mission", "STP_cw_credentials_review"): True}))

    def test_early_uprising_requires_the_current_northern_war_but_elections_do_not(self):
        gate = block(entries("common/scripted_triggers/ADISCORD_STP_scripted_triggers.txt"), "STP_cw_can_start")
        anchors = {("STP", "owns_state", str(state)): True for state in (1, 28, 43, 44, 88)}
        prepared = {**anchors, ("STP", "has_active_mission", "STP_cw_election_window"): True,
                    ("STP", "has_country_flag", "STP_cw_uprising_prepared"): True}
        for status in range(5):
            for busy in (False, True):
                facts = {**prepared, ("NOD", "variable", "STP_cw_northern_campaign_status"): status,
                         ("STP", "STP_cw_nod_busy_in_north", "yes"): busy}
                self.assertEqual(matches_conditions(gate, facts), busy, (status, busy))
                self.assertTrue(matches_conditions(gate, {**facts, ("STP", "has_country_flag", "STP_cw_elections_finished"): True}))
        for required in prepared:
            self.assertFalse(matches_conditions(gate, {**prepared, ("STP", "STP_cw_nod_busy_in_north", "yes"): True, required: False}), required)
        for forbidden in (("STP", "has_global_flag", "STP_cw_started"),
                          ("STP", "has_country_flag", "STP_cw_participant"),
                          ("STS", "exists", "yes"), ("SRP", "exists", "yes")):
            self.assertFalse(matches_conditions(gate, {**prepared, ("STP", "STP_cw_nod_busy_in_north", "yes"): True, forbidden: True}), forbidden)

    def test_limited_revolt_route_fits_shared_slots_and_focus_funding(self):
        tree = next(e.value for e in entries("common/national_focus/ADISCORD_national_focus_STP.txt")
                    if e.key == "focus_tree" and scalar(e.value, "id") == "STP_focus")
        focuses = {scalar(e.value, "id"): e.value for e in tree if e.key == "focus"}
        decision_groups = entries("common/decisions/ADISCORD_STP_decisions.txt")
        decisions = {e.key: e.value for group in decision_groups for e in group.value if isinstance(e.value, list)}
        effects = entries("common/scripted_effects/ADISCORD_STP_scripted_effects.txt")
        health = int(scalar(decisions["ivanov_health_is_getting_worse"], "days_mission_timeout"))
        adjustment = int(scalar(block(block(effects, "STP_cw_schedule_health"), "add_days_mission_timeout"), "days"))
        election_start = 3 * (health + adjustment)
        deadline = election_start + int(scalar(decisions["STP_cw_election_window"], "days_mission_timeout"))
        route = ("STP_ADRESS_PARTY_CRISIS", "STP_Count_The_Loyalists", "STP_cw_officer_contacts",
                 "STP_Call_For_Shabrat", "STP_cw_district_printing", "STP_cw_cabinet_archives",
                 "STP_cw_port_budget", "STP_cw_pay_officials",
                 "STP_cw_expose_the_cabinet", "STP_cw_national_mandate",
                 "STP_The_Silent_Mountain_March", "STP_cw_district_administration", "STP_cw_courier_service")
        completed = {"STP_Show_Him_The_Truth": 0}
        transactions = []
        time = 0
        bop = float(scalar(block(entries("common/bop/STP.txt"), "STP_shabrat_election_legitimacy"), "initial_value"))
        for name in route:
            focus = focuses[name]
            self.assertTrue(all(any(ref.value in completed for ref in group.value)
                                for group in focus if group.key == "prerequisite"), name)
            self.assertFalse(any(ref.value in completed for group in focus
                                 if group.key == "mutually_exclusive" for ref in group.value), name)
            if any(e.key == "has_active_mission" and e.value == "STP_cw_election_window"
                   for e in walk(block(focus, "available"))):
                time = max(time, election_start)
            facts = {("STP", "STP_cw_preparation_open", "yes"): True,
                     ("STP", "has_country_flag", "STP_sided_with_Maksim_flag"): True,
                     ("STP", "has_active_mission", "STP_cw_election_window"): time >= election_start}
            self.assertTrue(matches_conditions(block(focus, "available"), facts), name)
            time += int(float(scalar(focus, "cost")) * 7)
            completed[name] = time
            for effect in block(focus, "completion_reward"):
                if effect.key == "add_political_power":
                    transactions.append((time, float(effect.value)))
                elif effect.key == "add_power_balance_value":
                    bop += float(scalar(effect.value, "value"))
        self.assertEqual(time, 238)
        self.assertLess(time, deadline, "do not rely on delayed election callbacks for focus completion")

        intervals = []
        initial_reserve = 75
        treasury_expenses = []
        def operation(name, start):
            action = decisions[name]
            end = start + int(scalar(action, "days_remove"))
            if name != "STP_cw_delay_inspection":
                self.assertLessEqual(end, deadline, name)
            occupied = sum(begin <= start < finish for begin, finish, _ in intervals)
            slots = 1 + (start >= completed["STP_cw_district_printing"])
            facts = {("STP", "STP_cw_preparation_open", "yes"): True,
                     ("STP", "has_country_flag", "STP_sided_with_Maksim_flag"): True,
                     ("STP", "has_country_flag", "STP_battle_for_stelander_active"): True,
                     ("STP", "has_active_mission", "STP_cw_election_window"): start >= election_start,
                     ("STP", "STP_has_political_action_slot", "yes"): occupied < slots,
                     ("FROM", "is_owned_by", "ROOT"): True,
                     ("FROM", "is_controlled_by", "ROOT"): True,
                     ("FROM", "STP_region_is_operable", "yes"): True,
                     ("FROM", "STP_region_resistance_leaning", "yes"): sum(
                         task == "STP_cw_raise_district_network" and finish <= start for _, finish, task in intervals) >= 2,
                     ("FROM", "has_state_flag", "STP_party_inspection_active"): name == "STP_prepare_false_trail",
                     ("STP", "numeric", "has_political_power"): initial_reserve + sum(amount for day, amount in transactions if day <= start),
                     ("STP", "STP_cw_can_spend_600", "yes"): 1200 + 1200 * (start >= completed["STP_cw_port_budget"]) - sum(amount for day, amount in treasury_expenses if day <= start) >= 600,
                     ("STP", "has_character", "STP_Edmund_Ravel"): start >= completed["STP_cw_officer_contacts"],
                     ("2", "is_owned_by", "STP"): True, ("2", "is_controlled_by", "STP"): True,
                     ("2", "has_state_flag", "STP_resistance_garrison_asset"): any(
                         finish <= start and task == "STP_region_unique_operation_2" for _, finish, task in intervals),
                     **{("STP", "has_completed_focus", focus): when <= start for focus, when in completed.items()}}
            facts[("STP", "variable", "days_mission_timeout@STP_cw_election_window")] = deadline - start
            facts[("STP", "variable", "STP_cw_completed_public_campaigns")] = sum(
                finish <= start and task == "STP_cw_open_election_campaign" for _, finish, task in intervals)
            for state, focus, paid in (("2", "STP_The_Silent_Mountain_March", "STP_region_unique_operation_2"),
                                       ("3", "STP_cw_district_administration", "STP_recruit_regional_official")):
                built = min([completed[focus]] + [finish for _, finish, task in intervals if task == paid])
                facts[(state, "is_owned_by", "STP")] = True
                facts[(state, "is_controlled_by", "STP")] = True
                facts[(state, "has_state_flag", "STP_resistance_administration_asset")] = built <= start
                facts[(state, "flag_days", "STP_resistance_administration_asset")] = start - built
            current_bop = -.20 + sum(float(scalar(e.value, "value")) for focus, day in completed.items()
                if day <= start for e in block(focuses[focus], "completion_reward") if e.key == "add_power_balance_value")
            for _, finish, task in intervals:
                if finish <= start:
                    current_bop += sum(float(scalar(e.value, "value")) for _, e in
                        selected_effects(block(decisions[task], "remove_effect"), facts) if e.key == "add_power_balance_value")
            facts[("STP", "power_balance_value", "STP_shabrat_election_legitimacy")] = current_bop
            for predicate in ("STP_cw_public_campaign_basis", "STP_cw_delegate_support_available"):
                definition = block(entries("common/scripted_triggers/ADISCORD_STP_scripted_triggers.txt"), predicate)
                facts[("STP", predicate, "yes")] = matches_conditions(definition, facts)
            command = block(entries("common/scripted_triggers/ADISCORD_STP_scripted_triggers.txt"), "STP_cw_public_command_available")
            facts[("STP", "STP_cw_public_command_available", "yes")] = matches_conditions(command, facts)
            if name == "STP_cw_delay_inspection":
                facts[("STP", "has_active_mission", "STP_party_inspection_state_2")] = True
                facts[("STP", "STP_cw_from_inspection_mission_active", "yes")] = True
                facts[("FROM", "has_state_flag", "STP_party_inspection_active")] = True
                facts[("FROM", "has_state_flag", "STP_cw_inspection_delay_escrow")] = True
            for condition in ("visible", "available"):
                self.assertTrue(matches_conditions(block(action, condition), facts), (name, condition, start))
            if any(e.key == "custom_cost_trigger" for e in action):
                self.assertTrue(matches_conditions(block(action, "custom_cost_trigger"), facts), name)
            self.assertFalse(matches_conditions(block(action, "cancel_trigger"), facts), name)
            intervals.append((start, end, name))
            transactions.append((start, -float(scalar(action, "cost"))))
            transactions.extend((start, float(e.value)) for _, e in selected_effects(block(action, "complete_effect"), facts)
                                if e.key == "add_political_power")
            treasury_expenses.extend((start, 600) for _, e in selected_effects(block(action, "complete_effect"), facts)
                                     if e.key == "STP_cw_spend_600")
            return end

        first_network_done = operation("STP_cw_raise_district_network", completed["STP_Count_The_Loyalists"])
        second_network_done = operation("STP_cw_raise_district_network", first_network_done)
        operation("STP_cw_delay_inspection", second_network_done)
        garrison_done = operation("STP_region_unique_operation_2", completed["STP_cw_district_printing"])
        first_cover_done = operation("STP_prepare_false_trail", completed["STP_cw_cabinet_archives"])
        administration_done = operation("STP_recruit_regional_official", first_cover_done)
        operation("STP_prepare_false_trail", 134)
        campaign_done = operation("STP_cw_open_election_campaign", election_start)
        delegates_done = operation("STP_cw_negotiate_with_delegates", campaign_done)
        for stage in (1, 2):
            campaign_done = operation("STP_cw_open_election_campaign", max(campaign_done, election_start + stage * 35))
        operation("STP_prepare_false_trail", 184)
        operation("STP_prepare_false_trail", 226)
        agreement_done = operation("STP_cw_secure_election_result", max(delegates_done, completed["STP_cw_courier_service"]))
        self.assertLessEqual(garrison_done, completed["STP_cw_national_mandate"])
        self.assertGreaterEqual(deadline - garrison_done, 21)
        self.assertGreaterEqual(deadline - administration_done, 21)
        agreement_flag = next(e.value for e in walk(block(decisions["STP_cw_secure_election_result"], "remove_effect"))
                              if e.key == "set_country_flag")
        self.assertGreaterEqual(agreement_done + int(scalar(agreement_flag, "days")), deadline)
        # The final delay changes the current deadline immediately; split releases its slot.
        operation("STP_cw_delay_inspection", 266)
        balance = initial_reserve
        for day in sorted({day for day, _ in transactions}):
            balance += sum(amount for when, amount in transactions if when == day)
            self.assertGreaterEqual(balance, 0, f"day {day}: route exceeded the explicit 75 PP opening reserve")
        self.assertEqual(balance, 10)
        self.assertEqual(sum(amount for _, amount in treasury_expenses), 2400)
        for day in range(deadline):
            occupied = sum(start <= day < end for start, end, _ in intervals)
            slots = 1 + (day >= completed["STP_cw_district_printing"])
            self.assertLessEqual(occupied, slots, f"day {day}: paid operations overlap beyond available staff")
        side_facts = {("STP", "has_country_flag", "STP_sided_with_Maksim_flag"): True}
        for name, count in (("STP_recruit_regional_official", 1), ("STP_cw_open_election_campaign", 3), ("STP_cw_negotiate_with_delegates", 1)):
            preview = block(block(decisions[name], "remove_effect"), "effect_tooltip")
            bop += count * sum(float(scalar(e.value, "value")) for _, e in selected_effects(preview, side_facts)
                               if e.key == "add_power_balance_value")
        self.assertGreaterEqual(bop, .80, "the route must not require a BOP reward from a randomly empty search")
        self.assertAlmostEqual(bop, .81)

        first_inspection = next(e.value for e in block(effects, "STP_initialize_battle_for_stelander")
                                if e.key == "country_event" and scalar(e.value, "id") == "ADISCORD_STP_regions.2")
        first_deadline = int(scalar(first_inspection, "days")) + int(scalar(decisions["STP_party_inspection_state_2"], "days_mission_timeout"))
        response_unlock = completed["STP_Count_The_Loyalists"]
        self.assertGreaterEqual(first_deadline - response_unlock, 7)
        self.assertGreaterEqual(initial_reserve + sum(amount for day, amount in transactions if day <= response_unlock),
                                float(scalar(decisions["STP_cw_delay_inspection"], "cost")))

    def test_limited_revolt_requires_a_live_command_and_both_civil_administrations(self):
        triggers = entries("common/scripted_triggers/ADISCORD_STP_scripted_triggers.txt")
        command = block(triggers, "STP_cw_public_command_available")
        commander = {("STP", "has_character", "STP_Edmund_Ravel"): True,
                     ("2", "is_owned_by", "STP"): True, ("2", "is_controlled_by", "STP"): True,
                     ("2", "has_state_flag", "STP_resistance_garrison_asset"): True}
        self.assertTrue(matches_conditions(command, commander))
        for fact in (("STP", "has_character", "STP_Edmund_Ravel"),
                     ("2", "is_owned_by", "STP"), ("2", "is_controlled_by", "STP"),
                     ("2", "has_state_flag", "STP_resistance_garrison_asset")):
            self.assertFalse(matches_conditions(command, {**commander, fact: False}), fact)
        self.assertFalse(matches_conditions(command, {**commander, ("STP_Edmund_Ravel", "has_character_flag", "STP_cw_arrested"): True}))
        alternative = {k: v for k, v in commander.items() if k[0] != "2"}
        alternative.update({("29", key, value): True for _, key, value in commander if _ == "2"})
        self.assertTrue(matches_conditions(command, alternative), "either current garrison can back the public agreement")

        ready = block(triggers, "STP_cw_limited_party_revolt_ready")
        facts = {("STP", "has_country_flag", "STP_sided_with_Maksim_flag"): True,
                 ("STP", "STP_cw_shabrat_available", "yes"): True,
                 ("STP", "STP_cw_public_command_available", "yes"): True,
                 ("STP", "has_country_flag", "STP_cw_public_command_agreement"): True,
                 ("STP", "power_balance_value", "STP_shabrat_election_legitimacy"): .8}
        for state in ("2", "3"):
            facts.update({(state, "is_owned_by", "STP"): True, (state, "is_controlled_by", "STP"): True,
                          (state, "flag_days", "STP_resistance_administration_asset"): 21,
                          (state, "has_state_flag", "STP_resistance_administration_asset"): True})
        self.assertTrue(matches_conditions(ready, facts))
        for state in ("2", "3"):
            for days in (0, 16, 20, 21, 50):
                self.assertEqual(matches_conditions(ready, {**facts, (state, "flag_days", "STP_resistance_administration_asset"): days}), days >= 21)
        self.assertFalse(matches_conditions(ready, {**facts, ("STP", "power_balance_value", "STP_shabrat_election_legitimacy"): .7999}))
        for key in [k for k, value in facts.items() if value is True]:
            self.assertFalse(matches_conditions(ready, {**facts, key: False}), key)
        status = next(e.value for e in entries("common/scripted_localisation/ADISCORD_STP_scripted_loc.txt")
                      if e.key == "defined_text" and scalar(e.value, "name") == "STPGetAdministrationAsset")
        for state in ("2", "3", "29"):
            for present, age in ((False, 50), (True, 0), (True, 20), (True, 21)):
                case = {(state, "has_state_flag", "STP_resistance_administration_asset"): present,
                        (state, "flag_days", "STP_resistance_administration_asset"): age}
                shown = next(scalar(e.value, "localization_key") for e in status if e.key == "text"
                             and (not any(v.key == "trigger" for v in e.value)
                                  or matches_conditions(block(e.value, "trigger"), case, state)))
                expected = "STP_REGION_EMPTY_LINE" if not present else "STP_REGION_ASSET_ADMINISTRATION"
                if present:
                    expected += "_READY" if age >= 21 else "_RECENT"
                self.assertEqual(shown, expected)

    def test_existing_administrations_keep_their_age_when_other_work_finishes(self):
        for path in ("common/national_focus/ADISCORD_national_focus_STP.txt",
                     "common/decisions/ADISCORD_STP_decisions.txt",
                     "common/scripted_effects/ADISCORD_STP_scripted_effects.txt"):
            source = entries(path)
            flag = "STP_resistance_administration_asset"
            writes = [e for e in walk(source) if e.key == "set_state_flag" and e.value == flag]
            guards = [e.value for e in walk(source) if e.key == "if"
                      and any(v.key == "set_state_flag" and v.value == flag for v in e.value)]
            self.assertEqual(sum(len([v for v in guard if v.key == "set_state_flag" and v.value == flag])
                                 for guard in guards), len(writes), path)
            for guard in guards:
                for present in (False, True):
                    facts = {("2", "has_state_flag", flag): present}
                    self.assertEqual(matches_conditions(block(guard, "limit"), facts, "2"), not present)
                    assigned = [e for _, e in selected_effects([e for e in guard if e.key != "limit"], facts, "2")
                                if e.key == "set_state_flag" and e.value == flag]
                    self.assertEqual(len(assigned), 1)

    def test_public_command_agreement_is_paid_timed_and_rechecked_on_delivery(self):
        decision = block(block(entries("common/decisions/ADISCORD_STP_decisions.txt"), "STP_battle_for_stelander"), "STP_cw_secure_election_result")
        self.assertEqual((scalar(decision, "cost"), scalar(decision, "days_remove")), ("75", "35"))
        self.assertIn(("has_completed_focus", "STP_cw_national_mandate"), [(e.key, e.value) for e in walk(block(decision, "visible"))])
        start = list(selected_effects(block(decision, "complete_effect"), {}))
        self.assertEqual([e.key for _, e in start], ["STP_political_action_slot_consume"])
        for open_preparation in (False, True):
            for commander_ready in (False, True):
                facts = {("STP", "STP_cw_preparation_open", "yes"): open_preparation,
                         ("STP", "STP_cw_public_command_available", "yes"): commander_ready}
                self.assertEqual(matches_conditions(block(decision, "cancel_trigger"), facts), not (open_preparation and commander_ready))
                delivered = list(selected_effects(block(decision, "remove_effect"), facts))
                flags = [e.value for _, e in delivered if e.key == "set_country_flag"]
                self.assertEqual(len(flags), int(open_preparation and commander_ready))
                if flags:
                    self.assertEqual((scalar(flags[0], "flag"), scalar(flags[0], "days"), scalar(flags[0], "value")),
                                     ("STP_cw_public_command_agreement", "50", "1"))
                self.assertEqual(sum(e.key == "STP_political_action_slot_release" for _, e in delivered), 1)

    def test_election_mandate_keeps_its_bonuses_when_the_limited_revolt_conditions_fail(self):
        effects = entries("common/scripted_effects/ADISCORD_STP_scripted_effects.txt")
        finish = block(block(effects, "STP_cw_finish_elections"), "if")
        vector_names = ("STP_cw_mandate_org_regain", "STP_cw_mandate_core_defence",
                        "STP_cw_mandate_training_time", "STP_cw_mandate_mobilization")
        for balance, expected in ((.1, None), (.1001, (.20, .10, -.15, .20)),
                                  (.55, (.20, .10, -.15, .20)), (.5501, (.30, .15, -.20, .30)),
                                  (.8, (.30, .15, -.20, .30))):
            for limited_ready in (False, True):
                facts = {("STP", "power_balance_value", "STP_shabrat_election_legitimacy"): balance,
                         ("STP", "STP_cw_limited_party_revolt_ready", "yes"): limited_ready}
                result = list(selected_effects([e for e in finish if e.key != "limit"], facts))
                vector = {scalar(e.value, "var"): float(scalar(e.value, "value"))
                          for _, e in result if e.key == "set_variable"}
                self.assertEqual(vector, {} if expected is None else dict(zip(vector_names, expected)))
                flags = [e.value for _, e in result if e.key == "set_country_flag"]
                self.assertEqual("STP_cw_limited_party_revolt" in flags, limited_ready and expected is not None)
                self.assertFalse(any(e.key == "STP_cw_start" for _, e in result))
                self.assertEqual(sum(e.key == "country_event" and scalar(e.value, "id") == "ADISCORD_STP_cw.10" for _, e in result), 1, "the revolt must be queued outside the expiring mission")
        dynamic = block(entries("common/dynamic_modifiers/ADISCORD_dynamic_modifiers_STP.txt"), "STP_cw_election_mandate_dynamic")
        self.assertEqual(scalar(block(dynamic, "enable"), "tag"), "STS")
        self.assertEqual(scalar(block(dynamic, "enable"), "has_war"), "yes")
        self.assertEqual({e.value for e in dynamic if isinstance(e.value, str) and e.value.startswith("STP_cw_")}, set(vector_names))
        transfer = block(effects, "STP_cw_transfer_preparation_modifiers")
        mandate = next(e.value for e in transfer if e.key == "if"
                       and any(v.key == "add_dynamic_modifier" and scalar(v.value, "modifier") == "STP_cw_election_mandate_dynamic" for v in walk(e.value)))
        self.assertEqual(scalar(block(mandate, "limit"), "has_country_flag"), "STP_cw_shabrat_election_victory")
        recipient = block(mandate, "STS")
        self.assertEqual({scalar(e.value, "var"): scalar(e.value, "value") for e in recipient if e.key == "set_variable"},
                         {name: "STP." + name for name in vector_names})
        ideas = block(block(entries("common/ideas/ADISCORD_STP_civil_war_ideas.txt"), "ideas"), "country")
        bindings = {e.key: e.value for e in dynamic if isinstance(e.value, str) and e.value in vector_names}
        previews = {"STP_cw_mandate_majority_idea": (.20, .10, -.15, .20),
                    "STP_cw_mandate_strong_idea": (.30, .15, -.20, .30)}
        for idea, values in previews.items():
            modifiers = block(block(ideas, idea), "modifier")
            self.assertEqual({bindings[e.key]: float(e.value) for e in modifiers}, dict(zip(vector_names, values)))
        ranges = [e.value for e in walk(entries("common/bop/STP.txt")) if e.key == "range"
                  and scalar(e.value, "id").startswith("STP_shabrat_election_")]
        self.assertEqual(len(ranges), 4)
        for tier in ranges:
            activation = block(tier, "on_activate")
            self.assertEqual([e.key for e in activation], ["effect_tooltip"], "BOP hover previews must never install dummy ideas")
            swap = block(block(activation, "effect_tooltip"), "swap_ideas")
            self.assertEqual(scalar(swap, "remove_idea"), "STP_cw_mandate_dummy_idea")
            self.assertEqual(scalar(swap, "add_idea"), "STP_cw_mandate_strong_idea" if float(scalar(tier, "min")) >= .55 else "STP_cw_mandate_majority_idea")

    def test_public_command_agreement_strengthens_any_winning_mandate_only_while_its_backing_survives(self):
        from decimal import Decimal
        effects = entries("common/scripted_effects/ADISCORD_STP_scripted_effects.txt")
        finish = block(block(effects, "STP_cw_finish_elections"), "if")
        payload = [e for e in finish if e.key != "limit"]
        command = block(entries("common/scripted_triggers/ADISCORD_STP_scripted_triggers.txt"), "STP_cw_public_command_available")
        intact = {("STP", "has_character", "STP_Edmund_Ravel"): True,
                  ("2", "is_owned_by", "STP"): True, ("2", "is_controlled_by", "STP"): True,
                  ("2", "has_state_flag", "STP_resistance_garrison_asset"): True}
        command_states = [("intact", intact, True)]
        for fact in intact:
            command_states.append((str(fact), {**intact, fact: False}, False))
        command_states.append(("arrested", {**intact, ("STP_Edmund_Ravel", "has_character_flag", "STP_cw_arrested"): True}, False))
        alternative = {("29" if scope == "2" else scope, key, value): present
                       for (scope, key, value), present in intact.items()}
        command_states.append(("alternative garrison", alternative, True))
        delta = {"STP_cw_mandate_org_regain": Decimal(".10"), "STP_cw_mandate_core_defence": Decimal(".05")}
        names = ("STP_cw_mandate_org_regain", "STP_cw_mandate_core_defence",
                 "STP_cw_mandate_training_time", "STP_cw_mandate_mobilization")
        for balance in (.1, .1001, .55, .5501, .79, .8):
            for active_agreement in (False, True):
                for label, commander_facts, command_survives in command_states:
                    self.assertEqual(matches_conditions(command, commander_facts), command_survives)
                    facts = {("STP", "power_balance_value", "STP_shabrat_election_legitimacy"): balance,
                             ("STP", "has_country_flag", "STP_cw_public_command_agreement"): active_agreement,
                             ("STP", "STP_cw_public_command_available", "yes"): command_survives,
                             ("STP", "STP_cw_limited_party_revolt_ready", "yes"): False}
                    chosen = list(selected_effects(payload, facts))
                    vector, additions = {}, {}
                    for scope, entry in chosen:
                        if entry.key in ("set_variable", "add_to_variable"):
                            self.assertEqual(scope, "STP")
                            name, amount = scalar(entry.value, "var"), Decimal(scalar(entry.value, "value"))
                            if entry.key == "set_variable":
                                vector[name] = amount
                            else:
                                self.assertIn(name, vector, "command backing augments an already established electoral mandate")
                                vector[name] += amount
                                additions[name] = additions.get(name, Decimal(0)) + amount
                    receives = balance > .1 and active_agreement and command_survives
                    base = (".30", ".15", "-.20", ".30") if balance > .55 else (".20", ".10", "-.15", ".20")
                    expected = dict(zip(names, map(Decimal, base))) if balance > .1 else {}
                    if receives:
                        for name, amount in delta.items():
                            expected[name] += amount
                    with self.subTest(balance=balance, agreement=active_agreement, command=label):
                        self.assertEqual(additions, delta if receives else {})
                        self.assertEqual(vector, expected)
                        self.assertNotIn("STP_cw_limited_party_revolt", [e.value for _, e in chosen if e.key == "set_country_flag"])
                        self.assertEqual([e.value for _, e in chosen if e.key == "clr_country_flag"], ["STP_cw_public_command_agreement"])
        decision = block(block(entries("common/decisions/ADISCORD_STP_decisions.txt"), "STP_battle_for_stelander"), "STP_cw_secure_election_result")
        preview = block(block(block(decision, "remove_effect"), "effect_tooltip"), "swap_ideas")
        self.assertEqual(scalar(preview, "remove_idea"), "STP_cw_mandate_dummy_idea")
        self.assertEqual(scalar(preview, "add_idea"), "STP_cw_mandate_command_agreement_idea")
        ideas = block(block(entries("common/ideas/ADISCORD_STP_civil_war_ideas.txt"), "ideas"), "country")
        dummy = block(block(ideas, scalar(preview, "add_idea")), "modifier")
        dynamic = block(entries("common/dynamic_modifiers/ADISCORD_dynamic_modifiers_STP.txt"), "STP_cw_election_mandate_dynamic")
        bindings = {e.key: e.value for e in dynamic if isinstance(e.value, str) and e.value in names}
        self.assertEqual({bindings[e.key]: Decimal(e.value) for e in dummy}, delta)
        delivered = selected_effects(block(decision, "remove_effect"), {
            ("STP", "STP_cw_preparation_open", "yes"): True,
            ("STP", "STP_cw_public_command_available", "yes"): True})
        self.assertFalse(any(e.key in ("add_ideas", "swap_ideas") for _, e in delivered), "the decision's delta preview must not install a spirit")

    def test_assault_division_payment_covers_its_actual_template_and_fractional_stock(self):
        template = next(e.value for e in entries("history/units/ADISCORD_STP_civil_war_templates.txt")
                        if e.key == "division_template" and scalar(e.value, "name") == "Stelander Assault Division")
        units = block(entries("common/units/ADISCORD_land_units.txt"), "sub_units")
        manpower, equipment = 0, {}
        for group in ("regiments", "support"):
            for unit in block(template, group):
                definition = block(units, unit.key)
                manpower += int(scalar(definition, "manpower"))
                for item in block(definition, "need"):
                    equipment[item.key] = equipment.get(item.key, 0) + int(item.value)
        self.assertEqual(manpower, 7900)
        self.assertEqual(set(equipment), {"infantry_equipment", "ADISCORD_squad_weapons_equipment",
                                         "support_equipment", "artillery_equipment", "anti_air_equipment"})
        gate = block(entries("common/scripted_triggers/ADISCORD_STP_scripted_triggers.txt"), "STP_cw_can_pay_assault_division")
        facts = {("STP", "numeric", "has_manpower"): manpower,
                 **{("STP", "equipment", kind): amount for kind, amount in equipment.items()}}
        self.assertTrue(matches_conditions(gate, facts), "the exact full template price is affordable")
        for key, amount in facts.items():
            self.assertFalse(matches_conditions(gate, {**facts, key: amount - .001}), key)

        effects = entries("common/scripted_effects/ADISCORD_STP_scripted_effects.txt")
        payer = block(effects, "STP_cw_pay_assault_division")
        self.assertEqual(scalar(payer, "clr_country_flag"), "STP_cw_assault_division_paid")
        paid = block(payer, "if")
        self.assertEqual(scalar(block(paid, "limit"), "STP_cw_can_pay_assault_division"), "yes")
        prices = {scalar(e.value, "var"): int(scalar(e.value, "value")) for e in paid if e.key == "set_temp_variable"}
        self.assertEqual(prices, {"STP_cw_payment_" + kind: amount for kind, amount in equipment.items()})
        producer_loop = block(block(paid, "every_possible_country"), "PREV")
        for kind in equipment:
            debit = next(e.value for e in producer_loop if e.key == "if"
                         and any(v.key == "add_equipment_to_stockpile" and scalar(v.value, "type") == kind for v in e.value))
            self.assertEqual(scalar(block(debit, "add_equipment_to_stockpile"), "producer"), "PREV")
            reads = [(scalar(e.value, "var"), scalar(e.value, "value")) for e in debit if e.key == "set_temp_variable"]
            self.assertIn(("STP_cw_payment_before", "num_equipment@" + kind), reads)
            subtractions = [(scalar(e.value, "var"), scalar(e.value, "value")) for e in debit if e.key == "subtract_from_temp_variable"]
            self.assertEqual(subtractions, [("STP_cw_payment_before", "num_equipment@" + kind),
                                            ("STP_cw_payment_" + kind, "STP_cw_payment_before")],
                             "each producer pays only its actual stock change, leaving the remainder for the next producer")
        success = block(paid, "if")
        self.assertEqual({(scalar(e.value, "var"), scalar(e.value, "value"), scalar(e.value, "compare"))
                          for e in block(success, "limit")},
                         {("STP_cw_payment_" + kind, "0", "equals") for kind in equipment})
        self.assertEqual(int(scalar(success, "add_manpower")), -manpower)
        self.assertEqual(scalar(success, "set_country_flag"), "STP_cw_assault_division_paid")
        failure = block(paid, "else")
        self.assertNotIn("add_manpower", {e.key for e in walk(failure)}, "failed equipment payment never debits or refunds unpaid recruits")
        groups = [failure[index:index + 3] for index in range(0, len(failure), 3)]
        refunded = set()
        for initial, subtraction, refund in groups:
            kind = scalar(refund.value, "type")
            refunded.add(kind)
            self.assertEqual(initial.key, "set_temp_variable")
            self.assertEqual(int(scalar(initial.value, "value")), equipment[kind])
            self.assertEqual((subtraction.key, scalar(subtraction.value, "value")),
                             ("subtract_from_temp_variable", "STP_cw_payment_" + kind))
            self.assertEqual(scalar(refund.value, "amount"), "STP_cw_payment_refund")
        self.assertEqual(refunded, set(equipment))
        refund = block(effects, "STP_cw_refund_assault_division")
        self.assertEqual(int(scalar(refund, "add_manpower")), manpower)
        self.assertEqual({scalar(e.value, "type"): int(scalar(e.value, "amount"))
                          for e in refund if e.key == "add_equipment_to_stockpile"}, equipment)

    def test_assault_training_delivers_or_refunds_one_paid_receipt(self):
        decision = block(block(entries("common/decisions/ADISCORD_STP_decisions.txt"), "STP_battle_for_stelander"), "STP_cw_prepare_assault_group")
        effects = entries("common/scripted_effects/ADISCORD_STP_scripted_effects.txt")
        receipt = "STP_cw_assault_training_reserved"
        self.assertEqual((scalar(decision, "cost"), scalar(decision, "days_remove")), ("0", "28"))
        self.assertEqual([(e.key, e.value) for e in block(decision, "custom_cost_trigger")], [("STP_cw_can_spend_6000", "yes")])
        for affordable in (False, True):
            for pending in (False, True):
                facts = {("STP", "STP_cw_can_spend_6000", "yes"): affordable,
                         ("STP", "has_country_flag", receipt): pending}
                started = [e for _, e in selected_effects(block(decision, "complete_effect"), facts)]
                accepted = affordable and not pending
                self.assertEqual(sum(e.key == "STP_cw_spend_6000" for e in started), int(accepted))
                self.assertEqual(sum(e.key == "STP_political_action_slot_consume" for e in started), int(accepted))
                self.assertFalse({"STP_cw_pay_assault_division", "add_political_power", "add_manpower"} & {e.key for e in started})
        for open_preparation in (False, True):
            facts = {("STP", "has_country_flag", receipt): True,
                     ("STP", "STP_cw_preparation_open", "yes"): open_preparation}
            settled = [e for _, e in selected_effects(block(decision, "remove_effect"), facts)]
            self.assertEqual(sum(e.key == "add_to_variable" for e in settled), int(open_preparation))
            self.assertEqual(sum(e.key == "STP_cw_cancel_assault_training" for e in settled), int(not open_preparation))
        refund = block(effects, "STP_cw_cancel_assault_training")
        facts = {("STP", "has_country_flag", receipt): True}
        result = [e for _, e in selected_effects(refund, facts)]
        credits = {(scalar(e.value, "var"), scalar(e.value, "value")) for e in result if e.key == "add_to_variable"}
        self.assertEqual(credits, {("ADISCORD_economy_treasury", "STP_cw_cash_refund"), ("ADISCORD_economy_current_month_action_income", "STP_cw_cash_refund")})
        self.assertEqual(sum(e.key == "STP_political_action_slot_release" for e in result), 1)
        facts[("STP", "has_country_flag", receipt)] = False
        self.assertEqual(list(selected_effects(refund, facts)), [])
        self.assertIn("STP_cw_cancel_assault_training", [e.key for e in walk(block(effects, "STP_cw_start"))])

    def test_defensive_works_cancel_on_control_loss_and_materialize_once_at_the_split(self):
        decision = block(block(entries("common/decisions/ADISCORD_STP_decisions.txt"), "STP_battle_for_stelander"), "STP_cw_prepare_defensive_line")
        self.assertEqual({e.value for e in block(decision, "targets")}, {"1", "2", "3"})
        self.assertEqual((scalar(decision, "cost"), scalar(decision, "days_remove")), ("0", "21"))
        start = list(selected_effects(block(decision, "complete_effect"), {}))
        self.assertEqual([e.value for _, e in start if e.key == "add_political_power"], ["-50"])
        self.assertEqual(sum(e.key == "STP_cw_spend_1200" for _, e in start), 1)
        for open_preparation, owned, controlled in ((True, True, True), (False, True, True), (True, False, True), (True, True, False)):
            facts = {("STP", "STP_cw_preparation_open", "yes"): open_preparation,
                     ("FROM", "is_owned_by", "ROOT"): owned, ("FROM", "is_controlled_by", "ROOT"): controlled}
            expected = open_preparation and owned and controlled
            self.assertEqual(matches_conditions(block(decision, "cancel_trigger"), facts), not expected)
            result = list(selected_effects(block(decision, "remove_effect"), facts))
            self.assertEqual([(s, e.value) for s, e in result if e.key == "set_state_flag"],
                             [("FROM", "STP_cw_defensive_line_prepared")] if expected else [])
            self.assertEqual(sum(e.key == "STP_political_action_slot_release" for _, e in result), 1)
        materialize = block(block(entries("common/scripted_effects/ADISCORD_STP_scripted_effects.txt"), "STP_cw_materialize_region_assets"), "if")
        self.assertEqual(scalar(block(block(materialize, "limit"), "NOT"), "has_state_flag"), "STP_cw_assets_consumed")
        defence = next(e.value for e in materialize if e.key == "if"
                       and any(v.key == "has_state_flag" and v.value == "STP_cw_defensive_line_prepared" for v in block(e.value, "limit")))
        building = block(defence, "add_building_construction")
        self.assertEqual((scalar(building, "type"), scalar(building, "level"), scalar(building, "instant_build")), ("bunker", "2", "yes"))
        self.assertEqual(scalar(block(building, "province"), "limit_to_border"), "yes")
        self.assertEqual(scalar(defence, "clr_state_flag"), "STP_cw_defensive_line_prepared")

    def test_timed_preparation_flags_have_a_nonzero_value(self):
        for path in ("common/scripted_effects/ADISCORD_STP_scripted_effects.txt",
                     "common/decisions/ADISCORD_STP_decisions.txt", "events/ADISCORD_STP_events.txt"):
            for entry in walk(entries(path)):
                if entry.key in ("set_state_flag", "set_country_flag") and isinstance(entry.value, list):
                    if any(e.key == "days" for e in entry.value):
                        self.assertGreater(int(scalar(entry.value, "value")), 0,
                                           "a zero flag is saved but has_state/country_flag cannot see it")

    def test_failed_northern_preparation_releases_the_pending_request(self):
        events = entries("events/ADISCORD_STP_events.txt")
        event = next(e.value for e in events if e.key == "country_event"
                     and scalar(e.value, "id") == "ADISCORD_STP_preparation.11")
        failure = block(block(event, "immediate"), "else")
        selected = list(selected_effects(failure, {}, "NOD"))
        self.assertIn(("NOD", "clr_country_flag", "STP_cw_northern_crisis_pending"),
                      [(s, e.key, e.value) for s, e in selected])
        self.assertEqual([(s, scalar(e.value, "id")) for s, e in selected if e.key == "country_event"],
                         [("STP", "ADISCORD_STP_preparation.14")])

    def test_focus_variable_rewards_have_visible_tooltips(self):
        def visible_effects(items):
            for effect in items:
                if effect.key in ("hidden_effect", "effect_tooltip"):
                    continue
                yield effect
                if isinstance(effect.value, list):
                    yield from visible_effects(effect.value)
        for tree in entries("common/national_focus/ADISCORD_national_focus_STP.txt"):
            if tree.key != "focus_tree":
                continue
            for focus in (e.value for e in tree.value if e.key == "focus"):
                reward_body = block(focus, "completion_reward")
                reward = list(walk(reward_body))
                calls = {e.key for e in reward}
                tooltips = {e.value for e in reward if e.key == "custom_effect_tooltip"}
                for amount, tooltip in ((1200, "STP_cw_treasury_1200_tt"), (3000, "STP_cw_treasury_3000_tt")):
                    if "STP_receive_" + str(amount) in calls:
                        self.assertIn(tooltip, tooltips, scalar(focus, "id"))
                if "STP_change_party_suspicion" in {e.key for e in visible_effects(reward_body)}:
                    amount = next(scalar(e.value, "value") for e in reward if e.key == "set_temp_variable"
                                  and scalar(e.value, "var") == "STP_party_suspicion_change")
                    suffix = amount.replace("-", "minus_")
                    self.assertIn(f"STP_cw_suspicion_{suffix}_tt", tooltips, scalar(focus, "id"))

    def test_national_cache_needs_elections_full_payment_and_room_for_one_shipment(self):
        cache = block(block(entries("common/decisions/ADISCORD_STP_decisions.txt"),
                            "STP_battle_for_stelander"), "STP_cw_prepare_rifle_cache")
        self.assertEqual(scalar(cache, "cost"), "35")
        self.assertEqual(scalar(cache, "days_remove"), "28")
        facts = {("STP", "has_country_flag", "STP_sided_with_Maksim_flag"): True,
                 ("STP", "has_country_flag", "STP_battle_for_stelander_active"): True,
                 ("STP", "STP_cw_preparation_open", "yes"): True,
                 ("STP", "STP_has_political_action_slot", "yes"): True,
                 ("STP", "owns_state", "1"): True}
        self.assertFalse(matches_conditions(block(cache, "visible"), facts))
        facts[("STP", "has_active_mission", "STP_cw_election_window")] = True
        self.assertTrue(matches_conditions(block(cache, "visible"), facts))
        for stock in (15999.5, 16000):
            for cached in (79999.5, 80000, 80000.5):
                for pending in (False, True):
                    case = {**facts, ("STP", "equipment", "infantry_equipment"): stock,
                            ("1", "variable", "STP_cw_cached_rifles"): cached,
                            ("1", "has_variable", "STP_cw_pending_rifles"): pending}
                    expected = stock >= 16000 and cached <= 80000 and not pending
                    with self.subTest(stock=stock, cached=cached, pending=pending):
                        self.assertEqual(matches_conditions(block(cache, "available"), case), expected)
                        selected = [e for _, e in selected_effects(block(cache, "complete_effect"), case)]
                        self.assertEqual(any(e.key == "STP_cw_pay_rifles" for e in selected), expected)
        for paid in (False, True):
            case = {**facts, ("STP", "equipment", "infantry_equipment"): 16000,
                    ("STP", "has_country_flag", "STP_cw_rifles_paid"): paid}
            effects = [e for _, e in selected_effects(block(cache, "complete_effect"), case)]
            ledger = [e.value for e in effects if e.key == "set_variable"
                      and scalar(e.value, "var") == "STP_cw_pending_rifles"]
            self.assertEqual([int(scalar(e, "value")) for e in ledger], [16000] if paid else [])
            self.assertEqual(any(e.key == "STP_political_action_slot_consume" for e in effects), paid)

    def test_national_cache_delivery_requires_time_and_capacity_or_refunds_the_payer(self):
        cache = block(block(entries("common/decisions/ADISCORD_STP_decisions.txt"),
                            "STP_battle_for_stelander"), "STP_cw_prepare_rifle_cache")
        for active, cached, pending in ((True, 80000, True), (True, 80000.5, True),
                                       (False, 0, True), (False, 0, False)):
            facts = {("STP", "has_country_flag", "STP_battle_for_stelander_active"): active,
                     ("STP", "has_active_mission", "STP_cw_election_window"): active,
                     ("STP", "STP_cw_preparation_open", "yes"): active,
                     ("STP", "owns_state", "1"): True,
                     ("1", "has_variable", "STP_cw_pending_rifles"): pending,
                     ("1", "variable", "STP_cw_cached_rifles"): cached}
            with self.subTest(active=active, cached=cached, pending=pending):
                selected = list(selected_effects(block(cache, "remove_effect"), facts))
                credits = [(scope, e) for scope, e in selected if e.key == "add_to_variable"
                           and scalar(e.value, "var") == "STP_cw_cached_rifles"]
                refunds = [(scope, e) for scope, e in selected if e.key == "add_equipment_to_stockpile"]
                delivered = active and cached <= 80000 and pending
                self.assertEqual(len(credits), int(delivered))
                self.assertEqual([scope for scope, _ in refunds], ["STP"] if pending and not delivered else [])
                self.assertEqual(sum(e.key == "clear_variable" and e.value == "STP_cw_pending_rifles"
                                     for _, e in selected), int(pending))
                for _, refund in refunds:
                    self.assertEqual(scalar(refund.value, "amount"), "PREV.STP_cw_pending_rifles")

    def test_repeat_inspection_pace_uses_suspicion_without_shortening_the_first_response(self):
        definitions = entries("common/scripted_effects/ADISCORD_STP_scripted_effects.txt")
        effects_text = (ROOT / "common/scripted_effects/ADISCORD_STP_scripted_effects.txt").read_text(encoding="utf-8-sig")
        opener = block(definitions, "STP_cw_open_one_party_inspection")
        scheduler = block(definitions, "STP_schedule_next_party_inspection")
        decisions = block(entries("common/decisions/ADISCORD_STP_decisions.txt"), "STP_battle_for_stelander")
        self.assertTrue(any(e.key == "add_days_mission_timeout" for e in walk(opener)))
        self.assertFalse(any(e.key == "add_days_mission_timeout" for e in walk(scheduler)))
        self.assertIn("var = STP_last_inspection_state value = 0 compare = greater_than", effects_text)
        for state in (2, 3, 29, 45, 46, 53):
            mission = "STP_party_inspection_state_" + str(state)
            self.assertEqual(int(scalar(block(decisions, mission), "days_mission_timeout")), 40)
            self.assertIn(f"mission = {mission} days = -16", effects_text)
            self.assertIn(f"mission = {mission} days = -8", effects_text)
        initial = block(definitions, "STP_initialize_battle_for_stelander")
        first_event = next(e.value for e in initial if e.key == "country_event"
                           and scalar(e.value, "id") == "ADISCORD_STP_regions.2")
        self.assertEqual(scalar(first_event, "days"), "21")

    def test_inspections_detect_active_local_operations_before_their_reward(self):
        triggers = entries("common/scripted_triggers/ADISCORD_STP_scripted_triggers.txt")
        detectable = block(triggers, "STP_region_has_detectable_assets")
        effects = entries("common/scripted_effects/ADISCORD_STP_scripted_effects.txt")
        assess = block(effects, "STP_cw_assess_search_evidence")
        resolve = block(effects, "STP_resolve_party_inspection")
        decisions = block(entries("common/decisions/ADISCORD_STP_decisions.txt"), "STP_battle_for_stelander")
        states = (2, 3, 29, 45, 46, 53)
        for target in states:
            decision_id = f"STP_region_unique_operation_{target}"
            for inspected in states:
                with self.subTest(operation=target, inspected=inspected):
                    facts = {("STP", "STP_cw_preparation_open", "yes"): True}
                    if target == 53:
                        facts[(str(target), "variable", "STP_cw_sabotage_rifles")] = 240
                    else:
                        facts[(str(target), "has_state_flag", "STP_cw_district_operation_in_progress")] = True
                    found = matches_conditions(detectable, facts, str(inspected))
                    self.assertEqual(found, target == inspected,
                                     "a pending operation is evidence only in its own district")
                    facts[(str(inspected), "STP_region_has_detectable_assets", "yes")] = found
                    changes = [float(scalar(e.value, "value")) for _, e in selected_effects(assess, facts, str(inspected))
                               if e.key == "add_power_balance_value"]
                    self.assertEqual(changes, [-0.04 if found else 0.02])
                    blocked = any(e.key == "set_state_flag" and isinstance(e.value, list)
                                  and scalar(e.value, "flag") == "STP_party_counterintelligence_asset"
                                  for _, e in selected_effects(resolve, facts, str(inspected)))
                    self.assertEqual(blocked, found)
                    if found:
                        resolution = [e for _, e in selected_effects(resolve, facts, str(inspected))]
                        self.assertEqual(sum(e.key == "STP_cw_return_preparation_reserves" for e in resolution), 1)
                        cancelled = {("STP", "has_country_flag", "STP_battle_for_stelander_active"): True,
                                     ("FROM", "is_owned_by", "ROOT"): True,
                                     ("FROM", "STP_region_is_operable", "yes"): False}
                        operation = block(decisions, decision_id)
                        self.assertTrue(matches_conditions(block(operation, "cancel_trigger"), cancelled))
                        cancellation = [e for _, e in selected_effects(block(operation, "cancel_effect"), cancelled)]
                        self.assertEqual(sum(e.key == "STP_political_action_slot_release" for e in cancellation), 1)
                        self.assertFalse(any(e.key == "add_equipment_to_stockpile" for e in cancellation),
                                         "inspection already returned and cleared the local escrow")
            if target != 53:
                operation = block(decisions, decision_id)
                marker = "STP_cw_district_operation_in_progress"
                paid = list(selected_effects(block(operation, "complete_effect"), {}))
                self.assertEqual(sum(scope == "FROM" and e.key == "set_state_flag" and e.value == marker
                                     for scope, e in paid), 1)
                for callback in ("cancel_effect", "remove_effect"):
                    ending = list(selected_effects(block(operation, callback), {}))
                    self.assertEqual(sum(scope == "FROM" and e.key == "clr_state_flag" and e.value == marker
                                         for scope, e in ending), 1)
        self.assertFalse(any(e.key == "has_decision" for e in walk(detectable)))
        cleanup = block(effects, "STP_clear_region_runtime")
        self.assertIn("STP_cw_district_operation_in_progress", [e.value for e in cleanup if e.key == "clr_state_flag"])
        for amount in (0, 0.5, 240):
            facts = {("53", "variable", "STP_cw_sabotage_rifles"): amount}
            self.assertEqual(matches_conditions(detectable, facts, "53"), amount > 0)
        for state in states:
            self.assertFalse(matches_conditions(detectable, {("STP", "has_decision", "STP_recruit_regional_official"): True}, str(state)),
                             "a multi-target decision cannot expose every district")
        for protected in ("STP_false_trail_prepared", "STP_inspection_concession_prepared"):
            facts = {("2", "has_state_flag", protected): True,
                     ("2", "STP_region_has_detectable_assets", "yes"): True}
            selected = [e for _, e in selected_effects(resolve, facts, "2")]
            self.assertFalse(any(e.key in ("STP_cw_assess_search_evidence", "STP_cw_return_preparation_reserves") for e in selected))
        for result in ("STP_false_trail_clean_redirect", "STP_false_trail_noisy_redirect"):
            self.assertFalse(any(e.key in ("clr_state_flag", "STP_cw_return_preparation_reserves")
                                 for _, e in selected_effects(block(effects, result), {}, "2")),
                             "a successful diversion preserves both completed and pending assets")

    def test_severe_counterintelligence_failure_removes_supply_and_unratified_deals(self):
        failure = block(entries("common/scripted_effects/ADISCORD_STP_scripted_effects.txt"),
                        "STP_false_trail_counterintelligence_breakthrough")
        for state in (2, 45, 46):
            for ratified in (False, True):
                with self.subTest(state=state, ratified=ratified):
                    facts = {("STP", "has_completed_focus", "STP_cw_autonomy_guarantees"): ratified}
                    selected = [e for _, e in selected_effects(failure, facts, str(state))]
                    removed = {e.value for e in selected if e.key == "clr_state_flag"}
                    self.assertTrue({"STP_resistance_administration_asset", "STP_resistance_garrison_asset",
                                     "STP_resistance_supply_asset", "STP_resistance_sabotage_asset"} <= removed)
                    self.assertEqual("STP_local_deal_asset" in removed, not (state == 45 and ratified))
                    self.assertEqual(sum(e.key == "STP_cw_return_preparation_reserves" for e in selected), 1)

    def test_cache_delivery_preserves_concurrent_focus_and_foreign_shipments(self):
        decisions = entries("common/decisions/ADISCORD_STP_decisions.txt")
        cache = block(block(decisions, "STP_battle_for_stelander"), "STP_cw_prepare_rifle_cache")
        delivery = block(cache, "remove_effect")
        writes = [e for e in walk(delivery) if e.key in ("set_variable", "add_to_variable")
                  and scalar(e.value, "var") == "STP_cw_cached_rifles"]
        self.assertEqual(len(writes), 1)
        self.assertEqual(writes[0].key, "add_to_variable", "a pending delivery must preserve rifles already deposited by a focus or foreign donor")

    def test_rifle_procurement_is_one_national_order_with_one_escrow(self):
        decisions = entries("common/decisions/ADISCORD_STP_decisions.txt")
        cache = block(block(decisions, "STP_battle_for_stelander"), "STP_cw_prepare_rifle_cache")
        self.assertFalse({"state_target", "targets", "target_trigger", "on_map_mode"} & {e.key for e in cache})
        self.assertFalse(any(e.key == "FROM" or (isinstance(e.value, str) and e.value.startswith("FROM."))
                             for e in walk(cache)), "national orders must not depend on a selected state")
        for phase in ("complete_effect", "cancel_effect", "remove_effect"):
            self.assertTrue(any(e.key == "1" for e in walk(block(cache, phase))), phase)
        self.assertIn("STP_cw_pay_rifles", {e.key for e in walk(block(cache, "complete_effect"))})

    def test_cancelled_rifle_order_returns_its_actual_escrow_to_the_payer_once(self):
        decisions = entries("common/decisions/ADISCORD_STP_decisions.txt")
        cache = block(block(decisions, "STP_battle_for_stelander"), "STP_cw_prepare_rifle_cache")
        cancel = block(cache, "cancel_effect")
        pending = "STP_cw_pending_rifles"

        def scoped_steps(items, facts, scopes=("STP",)):
            for entry in items:
                if entry.key == "custom_effect_tooltip":
                    continue
                if entry.key == "hidden_effect":
                    yield from scoped_steps(entry.value, facts, scopes)
                elif entry.key == "if":
                    if matches_conditions(block(entry.value, "limit"), facts, scopes[-1]):
                        yield from scoped_steps([e for e in entry.value if e.key != "limit"], facts, scopes)
                elif re.fullmatch(r"[A-Z]{3}|\d+|ROOT", entry.key) and isinstance(entry.value, list):
                    target = scopes[0] if entry.key == "ROOT" else entry.key
                    yield from scoped_steps(entry.value, facts, scopes + (target,))
                else:
                    yield scopes, entry

        # None also represents a late cancellation after split/cleanup consumed the ledger.
        for escrow in (None, 0, 120, 480, 1600):
            with self.subTest(escrow=escrow):
                variables = {("STP", pending): 999, ("2", pending): 777}
                if escrow is not None:
                    variables[("1", pending)] = escrow
                for callback in range(2):
                    facts = {(scope, "has_variable", name): True for scope, name in variables}
                    results = []
                    for scopes, effect in scoped_steps(cancel, facts):
                        scope = scopes[-1]
                        if effect.key == "add_equipment_to_stockpile":
                            self.assertEqual(scalar(effect.value, "type"), "infantry_equipment")
                            amount = scalar(effect.value, "amount")
                            self.assertRegex(amount, r"^(?:(?:PREV|ROOT)\.)?[A-Za-z_]\w*$",
                                             "escrow must use a valid scoped variable, never a numeric-state token or fixed grant")
                            source, name = amount.split(".") if "." in amount else ("THIS", amount)
                            source_scope = {"THIS": scope, "ROOT": scopes[0], "PREV": scopes[-2]}[source]
                            self.assertIn((source_scope, name), variables, "read the ledger before clearing it")
                            results.append(("refund", scope, variables[(source_scope, name)]))
                        elif effect.key == "clear_variable":
                            variables.pop((scope, effect.value), None)
                            results.append(("clear", scope, effect.value))
                        elif effect.key == "STP_political_action_slot_release":
                            results.append(("release", scope))
                        else:
                            self.fail(f"Unexpected cancellation effect: {effect.key}")
                    expected = []
                    if callback == 0 and escrow is not None:
                        expected = [("refund", "STP", escrow), ("clear", "1", pending), ("release", "STP")]
                    self.assertEqual(results, expected)
                    self.assertNotIn(("1", pending), variables)
                    self.assertEqual(variables, {("STP", pending): 999, ("2", pending): 777})

    def test_intro_ends_in_a_real_exclusive_side_choice(self):
        effects = entries("common/scripted_effects/ADISCORD_STP_scripted_effects.txt")
        calendar = block(effects, "STP_cw_initialize_preparation")
        initialized = block(calendar, "if")
        self.assertEqual(scalar(initialized, "activate_mission"), "ivanov_health_is_getting_worse")
        self.assertEqual(scalar(block(block(initialized, "limit"), "NOT"), "has_country_flag"), "STP_cw_calendar_initialized")
        advance = block(effects, "STP_cw_advance_health")
        self.assertEqual(scalar(block(advance, "if"), "STP_cw_first_health_decline"), "yes",
                         "ignoring the intro must still open the real side choice at the first health deadline")
        decline = block(block(effects, "STP_cw_first_health_decline"), "if")
        self.assertEqual(scalar(decline, "remove_mission"), "ivanov_health_is_getting_worse")
        events = entries("events/ADISCORD_STP_events.txt")
        choice = next(e.value for e in events if e.key == "country_event" and scalar(e.value, "id") == "ADISCORD_STP_preparation.1")
        options = [e.value for e in choice if e.key == "option"]
        self.assertEqual(len(options), 2, "the first illness event must offer Shabrat and the party")
        selected = set()
        for option in options:
            selected.update(e.value for e in walk(option) if e.key == "set_country_flag")
            self.assertTrue(any(e.key == "complete_national_focus" for e in walk(option)))
            self.assertIn(("mark_focus_tree_layout_dirty", "yes"), [(e.key, e.value) for e in walk(option)])
        self.assertIn("STP_sided_with_Maksim_flag", selected)
        self.assertIn("STP_sided_with_the_party_flag", selected)

    def test_shabrat_choice_plays_the_registered_theme(self):
        tree = next(e.value for e in entries("common/national_focus/ADISCORD_national_focus_STP.txt")
                    if e.key == "focus_tree" and scalar(e.value, "id") == "STP_focus")
        focus = next(e.value for e in tree if e.key == "focus" and scalar(e.value, "id") == "STP_Show_Him_The_Truth")
        reward = block(focus, "completion_reward")
        self.assertEqual(scalar(reward, "custom_effect_tooltip"), "STP_cw_branch_choice_tt")
        self.assertEqual(scalar(block(reward, "hidden_effect"), "scoped_play_song"), "ADISCORD_stp_shabrat")
        events = entries("events/ADISCORD_STP_events.txt")
        choice = next(e.value for e in events if e.key == "country_event" and scalar(e.value, "id") == "ADISCORD_STP_preparation.1")
        shabrat = next(option for option in choice if option.key == "option"
                       and any(e.key == "set_country_flag" and e.value == "STP_sided_with_Maksim_flag"
                               for e in walk(option.value)))
        self.assertEqual(scalar(shabrat.value, "complete_national_focus"), "STP_Show_Him_The_Truth")
        party = next(option for option in choice if option.key == "option"
                     and any(e.key == "set_country_flag" and e.value == "STP_sided_with_the_party_flag"
                             for e in walk(option.value)))
        self.assertNotIn("scoped_play_song", {e.key for e in walk(party.value)})
        assets = entries("music/music.asset")
        song = next(e.value for e in assets if e.key == "music" and scalar(e.value, "name") == "ADISCORD_stp_shabrat")
        self.assertEqual(scalar(song, "file"), "ADISCORD_stp_shabrat.ogg")
        self.assertTrue((ROOT / "music" / "ADISCORD_stp_shabrat.ogg").is_file())
        station = entries("music/_songs.txt")
        playlist = next(e.value for e in station if e.key == "music" and scalar(e.value, "song") == "ADISCORD_stp_shabrat")
        chance = block(playlist, "chance")
        self.assertEqual(scalar(chance, "base"), "10")
        modifiers = [e.value for e in chance if e.key == "modifier"]
        self.assertEqual(scalar(block(modifiers[0], "NOT"), "has_country_flag"), "STP_sided_with_Maksim_flag")
        self.assertEqual(scalar(modifiers[1], "has_global_flag"), "STP_cw_started")
        self.assertIn('ADISCORD_stp_shabrat: "3TEETH - Pumped Up Kicks"',
                      (ROOT / "localisation" / "russian" / "ADISCORD_music_l_russian.yml").read_text(encoding="utf-8-sig"))
        self.assertIn('ADISCORD_stp_shabrat: "3TEETH - Pumped Up Kicks"',
                      (ROOT / "localisation" / "english" / "ADISCORD_music_l_english.yml").read_text(encoding="utf-8-sig"))

    def test_focus_flags_have_gameplay_consumers(self):
        trees = entries("common/national_focus/ADISCORD_national_focus_STP.txt")
        written = {e.value for e in walk(trees) if e.key == "set_country_flag" and isinstance(e.value, str) and e.value.startswith("STP_cw_")}
        read = set()
        for directory in ("common", "events"):
            for path in (ROOT / directory).rglob("*STP*.txt"):
                read.update(e.value for e in walk(parse_clausewitz(path.read_text(encoding="utf-8-sig")))
                            if e.key == "has_country_flag" and isinstance(e.value, str))
        self.assertFalse(written - read, f"focus rewards with no consumer: {sorted(written - read)}")

    def test_prewar_branches_close_when_the_elections_finish(self):
        trees = entries("common/national_focus/ADISCORD_national_focus_STP.txt")
        tree = next(e.value for e in trees if e.key == "focus_tree" and scalar(e.value, "id") == "STP_focus")
        intro = {"STP_NECTAR_OF_GODS", "STP_2160_budget", "STP_STATE_OF_THE_REPUBLIC"}
        for focus in (e.value for e in tree if e.key == "focus"):
            focus_id = scalar(focus, "id")
            if focus_id not in intro:
                availability = block(focus, "available")
                self.assertIn(("STP_cw_preparation_open", "yes"), [(e.key, e.value) for e in walk(availability)], focus_id)

    def test_selected_focus_layout_stays_centered_without_overlapping_nodes(self):
        trees = entries("common/national_focus/ADISCORD_national_focus_STP.txt")
        tree = next(e.value for e in trees if e.key == "focus_tree" and scalar(e.value, "id") == "STP_focus")
        focuses = {scalar(e.value, "id"): e.value for e in tree if e.key == "focus"}
        for root in ("STP_Show_Him_The_Truth", "STP_Govern_In_His_Name"):
            root_focus = focuses[root]
            offset = block(root_focus, "offset")
            root_x = int(scalar(root_focus, "x")) + int(scalar(offset, "x"))
            root_y = int(scalar(root_focus, "y")) + int(scalar(offset, "y"))
            self.assertEqual(root_x, int(scalar(focuses["STP_STATE_OF_THE_REPUBLIC"], "x")))
            occupied = {(root_x, root_y): root}
            for focus_id, focus in focuses.items():
                relatives = [e.value for e in focus if e.key == "relative_position_id"]
                if relatives != [root]:
                    continue
                position = (root_x + int(scalar(focus, "x")), root_y + int(scalar(focus, "y")))
                self.assertNotIn(position, occupied, f"{focus_id} overlaps {occupied.get(position)}")
                occupied[position] = focus_id
            positions = {focus_id: position for position, focus_id in occupied.items()}
            for focus_id, (focus_x, focus_y) in positions.items():
                exclusions = [child.value for group in focuses[focus_id]
                              if group.key == "mutually_exclusive" for child in group.value
                              if child.key == "focus"]
                for other_id in exclusions:
                    if other_id not in positions or focus_id >= other_id:
                        continue
                    other_x, other_y = positions[other_id]
                    if focus_y != other_y:
                        continue
                    left, right = sorted((focus_x, other_x))
                    crossed = [name for name, (x, y) in positions.items()
                               if y == focus_y and left < x < right]
                    self.assertFalse(crossed, f"{focus_id} / {other_id} mutual-exclusion line crosses {crossed}")

    def test_party_preparation_keeps_shared_map_but_owns_separate_actions(self):
        categories = entries("common/decisions/categories/ADISCORD_decision_categories_STP.txt")
        visible = block(block(categories, "STP_battle_for_stelander"), "visible")
        self.assertNotIn("STP_sided_with_Maksim_trigger", {e.key for e in walk(visible)})
        decisions = block(entries("common/decisions/ADISCORD_STP_decisions.txt"), "STP_battle_for_stelander")
        party_action = block(decisions, "STP_cw_check_district_command")
        self.assertIn(("has_country_flag", "STP_sided_with_the_party_flag"), [(e.key, e.value) for e in walk(block(party_action, "visible"))])
        interrupt = block(decisions, "STP_cw_interrupt_opposition")
        self.assertIn(("has_completed_focus", "STP_cw_security_collegium"),
                      [(e.key, e.value) for e in walk(block(interrupt, "visible"))])
        self.assertIn(("has_country_flag", "STP_sided_with_the_party_flag"),
                      [(e.key, e.value) for e in walk(block(interrupt, "visible"))])
        for name in ("STP_cw_raise_district_network", "STP_cw_start_uprising", "STP_recruit_regional_official"):
            action = block(decisions, name)
            self.assertIn(("has_country_flag", "STP_sided_with_Maksim_flag"), [(e.key, e.value) for e in walk(block(action, "visible"))], name)

    def test_party_budget_choice_keeps_both_routes_and_shared_security_reachable(self):
        tree = next(e.value for e in entries("common/national_focus/ADISCORD_national_focus_STP.txt")
                    if scalar(e.value, "id") == "STP_focus")
        focuses = {scalar(e.value, "id"): e.value for e in tree if e.key == "focus"}
        cabinet = {"STP_GUARANTEE_MINISTERS", "STP_party_budget_reserve"}
        military = {"STP_defense_budget", "STP_party_guard_workshops"}
        shared = {"STP_PARTY_DISCIPLINE", "STP_ROTATE_DISTRICT_COMMAND", "STP_EMERGENCY_PRESIDIUM",
                  "STP_THE_PARTY_CLOSES_RANKS", "STP_cw_security_collegium", "STP_cw_counter_network",
                  "STP_cw_protocol_office", "STP_cw_party_mandate", "STP_DISTRICT_GOVERNMENT",
                  "STP_party_civil_register", "STP_cw_press_office", "STP_cw_capital_reserve",
                  "STP_cw_protect_congress", "STP_cw_capital_oath"}
        for selected, excluded, own_route, other_route in (
            ("STP_GUARANTEE_MINISTERS", "STP_defense_budget", cabinet, military),
            ("STP_defense_budget", "STP_GUARANTEE_MINISTERS", military, cabinet),
        ):
            with self.subTest(route=selected):
                self.assertEqual(scalar(block(focuses[selected], "mutually_exclusive"), "focus"), excluded)
                reached = {"STP_Govern_In_His_Name", "STP_PRESIDENT_REMAINS_IN_OFFICE", selected}
                remaining = (cabinet | military | shared) - reached
                while True:
                    ready = {name for name in remaining
                             if all(any(child.value in reached for child in prerequisite.value)
                                    for prerequisite in focuses[name] if prerequisite.key == "prerequisite")
                             and not any(child.value in reached for group in focuses[name]
                                         if group.key == "mutually_exclusive" for child in group.value)}
                    if not ready:
                        break
                    reached |= ready
                    remaining -= ready
                self.assertTrue((own_route | shared) <= reached)
                self.assertFalse(other_route & reached, "a downstream focus bypasses the budget choice")

    def test_northern_supply_and_evidence_use_the_chosen_capability_after_the_split(self):
        decisions = block(entries("common/decisions/ADISCORD_STP_decisions.txt"), "STP_cw_external_intervention")
        supply = block(decisions, "STP_cw_supply_the_north")
        self.assertEqual(scalar(supply, "days_remove"), "21")
        self.assertEqual(scalar(supply, "days_re_enable"), "42")
        self.assertEqual(scalar(supply, "fire_only_once"), "no")
        self.assertEqual({e.value for e in block(supply, "targets")}, {"YPR", "COF", "TFF"})
        payload = list(walk(block(supply, "remove_effect")))
        self.assertFalse({"STP_cw_launch_northern_crisis", "declare_war_on", "add_days_mission_timeout"}
                         & {e.key for e in payload}, "equipment must hold the real front, not change a timer")
        for donor in ("STP", "STS"):
            for capable in (False, True):
                facts = {(donor, "has_country_flag", "STP_cw_northern_strategy_supply"): capable,
                         (donor, "has_capitulated", "no"): True,
                         (donor, "has_country_flag", "STP_battle_for_stelander_active"): donor == "STP",
                         ("FROM", "STP_cw_northern_target_valid", "yes"): True,
                         ("FROM", "has_war_with", "NOD"): True}
                self.assertEqual(matches_conditions(block(supply, "visible"), facts, donor), capable)
        evidence = block(decisions, "STP_cw_trigger_northern_incident")
        self.assertEqual({e.value for e in walk(block(evidence, "allowed")) if e.key == "tag"}, {"STP", "STS"})
        self.assertEqual(scalar(evidence, "cost"), "35")
        self.assertEqual(scalar(evidence, "fire_only_once"), "yes")
        facts = {("STS", "has_country_flag", "STP_cw_northern_strategy_evidence"): True,
                 ("STS", "has_active_mission", "STP_cw_nod_warning"): True,
                 ("NOD", "has_active_mission", "NOD_cw_intervention_preparation"): True}
        self.assertTrue(matches_conditions(block(evidence, "visible"), facts, "STS"))
        self.assertTrue(matches_conditions(block(evidence, "available"), facts, "STS"))
        self.assertFalse(matches_conditions(block(evidence, "available"), {
            **facts, ("NOD", "has_active_mission", "NOD_cw_intervention_preparation"): False}, "STS"),
            "an expired readiness countdown cannot be restarted through diplomatic evidence")
        selected = []
        for scope, entry in selected_effects(block(evidence, "complete_effect"), facts, "STS"):
            selected.append((scope, entry))
            if entry.key == "clr_country_flag":
                facts[(scope, "has_country_flag", entry.value)] = False
        self.assertEqual([scalar(e.value, "value") for _, e in selected
                          if e.key == "set_temp_variable" and scalar(e.value, "var") == "STP_cw_nod_prep_delta"],
                         ["56"])
        self.assertEqual(sum(e.key == "STP_cw_adjust_nod_intervention_days" for _, e in selected), 1)
        self.assertFalse(any(e.key == "add_days_mission_timeout" for _, e in selected))
        self.assertFalse(matches_conditions(block(evidence, "visible"), facts, "STS"),
                         "consuming the evidence prevents a second or restarted-warning purchase")
        self.assertFalse(matches_conditions(block(evidence, "visible"),
                          {**facts, ("STS", "has_country_flag", "STP_cw_northern_strategy_evidence"): True,
                           ("STS", "has_active_mission", "STP_cw_nod_warning"): False}, "STS"))

    def test_opposition_preparation_cannot_preempt_the_election_deadline(self):
        effects = entries("common/scripted_effects/ADISCORD_STP_scripted_effects.txt")
        opposition = block(effects, "STP_cw_prepare_opposition")
        self.assertNotIn("STP_cw_start", {e.key for e in walk(opposition)})
        self.assertIn("STP_add_resistance_influence", {e.key for e in walk(opposition)})
        def shown(items):
            for entry in items:
                if entry.key == "hidden_effect":
                    continue
                yield entry
                if isinstance(entry.value, list):
                    yield from shown(entry.value)
        self.assertNotIn("country_event", {e.key for e in shown(opposition)},
                         "the technical rearm event has no title and must not display event 0")
        self.assertIn("add_power_balance_value", {e.key for e in shown(opposition)},
                      "hide only the dispatch, not the real political reward")
        dispatch = [e.value for e in walk(opposition) if e.key == "country_event"]
        self.assertEqual([scalar(e, "id") for e in dispatch], ["ADISCORD_STP_preparation.5"])


    def test_northern_observers_refresh_intel_once_and_hand_it_to_the_playable_successor(self):
        events = entries("events/ADISCORD_STP_events.txt")
        confirmation = next(e.value for e in events if e.key == "country_event"
                            and scalar(e.value, "id") == "ADISCORD_STP_preparation.12")
        for war, prepared, verified, expected in ((True, True, False, 1), (True, True, True, 0),
                                                 (False, True, False, 0), (True, False, False, 0)):
            facts = {("STP", "STP_cw_nod_busy_in_north", "yes"): war,
                     ("STP", "has_completed_focus", "STP_cw_northern_dossier"): prepared,
                     ("STP", "has_country_flag", "STP_cw_northern_war_verified"): verified}
            with self.subTest(war=war, prepared=prepared, verified=verified):
                selected = list(selected_effects(block(confirmation, "immediate"), facts, "NOD"))
                intel = [(scope, e) for scope, e in selected if e.key == "add_intel"]
                self.assertEqual(len(intel), expected)
                for scope, award in intel:
                    self.assertEqual((scope, scalar(award.value, "target"), scalar(award.value, "army_intel")),
                                     ("STP", "NOD", "15"))
                failed = [e for _, e in selected if e.key == "country_event"
                          and scalar(e.value, "id") == "ADISCORD_STP_preparation.14"]
                self.assertEqual(bool(failed), not war, "repeat confirmation of a real war is not a failed operation")
                if intel:
                    award_index = next(i for i, (_, e) in enumerate(selected) if e.key == "add_intel")
                    marker_index = next(i for i, (_, e) in enumerate(selected)
                                        if e.key == "set_country_flag" and e.value == "STP_cw_northern_war_verified")
                    self.assertLess(award_index, marker_index)
        effects = entries("common/scripted_effects/ADISCORD_STP_scripted_effects.txt")
        transfer = block(effects, "STP_cw_transfer_preparation_modifiers")
        observer_branches = [e for e in transfer if e.key == "if" and any(v.key == "add_intel" for v in walk(e.value))]
        self.assertEqual(len(observer_branches), 2)
        for dossier, desk, exists, expected in (
                (True, False, True, [("STS", "15")]),
                (False, True, True, [("STS", "10")]),
                (True, True, True, [("STS", "15"), ("STS", "10")]),
                (True, True, False, []),
                (False, False, True, []),
        ):
            facts = {("STP", "has_completed_focus", "STP_cw_northern_dossier"): dossier,
                     ("STP", "has_completed_focus", "STP_cw_northern_desk"): desk,
                     ("STS", "exists", "yes"): True,
                     ("NOD", "exists", "yes"): exists}
            intel = [(scope, scalar(e.value, "army_intel"))
                     for scope, e in selected_effects(observer_branches, facts) if e.key == "add_intel"]
            self.assertEqual(intel, expected, (dossier, desk, exists))
            for scope, award in ((scope, e) for scope, e in selected_effects(observer_branches, facts)
                                 if e.key == "add_intel"):
                self.assertEqual(scalar(award.value, "target"), "NOD")
                self.assertEqual(scope, "STS")

    def test_revolt_countries_resolve_history_names_and_flags_without_starting_land(self):
        tags = {}
        for path in (ROOT / "common/country_tags").glob("*.txt"):
            for entry in parse_clausewitz(path.read_text(encoding="utf-8-sig")):
                if entry.key in ("STS", "SRP"):
                    self.assertNotIn(entry.key, tags, "ambiguous fixed-tag registry")
                    tags[entry.key] = entry.value
        self.assertEqual(set(tags), {"STS", "SRP"}, "both dormant war sides must be registered")
        for tag, definition in tags.items():
            self.assertTrue((ROOT / "common" / definition).is_file())
            self.assertEqual(len(list((ROOT / "history/countries").glob(f"{tag} - *.txt"))), 1)
            for size in ("", "medium", "small"):
                self.assertTrue((ROOT / "gfx/flags" / size / f"{tag}.tga").is_file())
        for path in (ROOT / "history/states").glob("*.txt"):
            owners = {entry.value for entry in walk(parse_clausewitz(path.read_text(encoding="utf-8-sig"))) if entry.key == "owner"}
            self.assertFalse(owners & tags.keys(), f"war side exists before the split: {path.name}")

    def test_template_only_mobilization_has_the_priced_real_resource_requirements(self):
        oob = entries("history/units/ADISCORD_STP_civil_war_templates.txt")
        self.assertFalse(any(entry.key in ("units", "division") for entry in walk(oob)), "loading templates must not spawn unpriced units")
        template = next(e.value for e in oob if e.key == "division_template"
                        and scalar(e.value, "name") == "Stelander Territorial Brigade")
        units = block(entries("common/units/ADISCORD_land_units.txt"), "sub_units")
        manpower = 0
        rifles = 0
        for regiment in block(template, "regiments"):
            definition = block(units, regiment.key)
            manpower += int(scalar(definition, "manpower"))
            need = block(definition, "need")
            self.assertEqual({item.key for item in need}, {"infantry_equipment"}, "mobilization price omits an equipment type")
            rifles += int(scalar(need, "infantry_equipment"))
        self.assertEqual((manpower, rifles), (6000, 600))

    def test_death_opens_elections_without_directly_starting_war(self):
        effects = entries("common/scripted_effects/ADISCORD_STP_scripted_effects.txt")
        death = block(effects, "STP_cw_begin_elections")
        calls = [(entry.key, entry.value) for entry in walk(death) if not isinstance(entry.value, list)]
        self.assertIn(("activate_mission", "STP_cw_election_window"), calls)
        self.assertNotIn(("STP_cw_start", "yes"), calls)
        decisions = entries("common/decisions/ADISCORD_STP_decisions.txt")
        mission = block(block(decisions, "STP_battle_for_stelander"), "STP_cw_election_window")
        self.assertEqual(int(scalar(mission, "days_mission_timeout")), 140)
        expiry = [(e.key, e.value) for e in walk(block(mission, "timeout_effect")) if not isinstance(e.value, list)]
        self.assertIn(("STP_cw_finish_elections", "yes"), expiry)
        self.assertNotIn(("STP_cw_start", "yes"), expiry)

    def test_northern_diversion_requires_a_real_war_declaration(self):
        effects = entries("common/scripted_effects/ADISCORD_STP_scripted_effects.txt")
        intervention = block(effects, "STP_cw_start_northern_war")
        declarations = [entry.value for entry in walk(intervention) if entry.key == "declare_war_on"]
        self.assertTrue(declarations, "a busy flag cannot substitute for northern war")
        self.assertTrue(any(scalar(declaration, "target") in ("YPR", "COF") for declaration in declarations))

    def test_preparation_focus_rewards_resolve_public_script_api_and_localisation(self):
        definitions = set()
        for directory in ("common/scripted_effects", "common/scripted_triggers"):
            for path in (ROOT / directory).glob("*.txt"):
                definitions.update(entry.key for entry in parse_clausewitz(path.read_text(encoding="utf-8-sig")))
        trees = entries("common/national_focus/ADISCORD_national_focus_STP.txt")
        for entry in walk(trees):
            if entry.key.startswith(("STP_", "ADISCORD_")):
                self.assertIn(entry.key, definitions, f"unresolved focus reward: {entry.key}")
        localisation = set()
        for path in (ROOT / "localisation/russian").glob("*STP*.yml"):
            self.assertTrue(path.read_bytes().startswith(b"\xef\xbb\xbf"), path.name)
            localisation.update(re.findall(r"(?m)^\s*([^\s:#]+):", path.read_text(encoding="utf-8-sig")))
        focus_ids = {scalar(entry.value, "id") for entry in walk(trees) if entry.key == "focus" and isinstance(entry.value, list)}
        for focus_id in focus_ids:
            self.assertIn(focus_id, localisation)
            self.assertIn(f"{focus_id}_desc", localisation)
        for entry in walk(trees):
            if entry.key == "custom_effect_tooltip":
                self.assertIn(entry.value, localisation, "focus tooltip has no localisation")
            if entry.key in ("prerequisite", "mutually_exclusive"):
                for reference in entry.value:
                    self.assertIn(reference.value, focus_ids, "focus path contains a removed predecessor")

    def test_shabrat_can_postpone_the_live_election_commission_once(self):
        tree = next(e.value for e in entries("common/national_focus/ADISCORD_national_focus_STP.txt")
                    if e.key == "focus_tree" and scalar(e.value, "id") == "STP_focus")
        focus = next(e.value for e in tree if e.key == "focus" and scalar(e.value, "id") == "STP_cw_delay_election_commission")
        self.assertEqual((scalar(focus, "x"), scalar(focus, "y"), scalar(focus, "cost")), ("-14", "4", "2"))
        self.assertEqual(scalar(focus, "cancel_if_invalid"), "yes")
        self.assertEqual(scalar(block(focus, "prerequisite"), "focus"), "STP_Call_For_Shabrat")
        available = block(focus, "available")
        facts = {("STP", "STP_cw_preparation_open", "yes"): True,
                 ("STP", "has_country_flag", "STP_sided_with_Maksim_flag"): True,
                 ("STP", "has_active_mission", "STP_cw_election_window"): True}
        self.assertTrue(matches_conditions(available, facts))
        self.assertFalse(matches_conditions(available, {**facts, ("STP", "has_active_mission", "STP_cw_election_window"): False}))
        reward = block(focus, "completion_reward")
        self.assertEqual({e.key for e in reward}, {"custom_effect_tooltip", "hidden_effect"})
        shown = [e.value for e in reward if e.key == "custom_effect_tooltip"]
        self.assertEqual(shown, ["STP_cw_delay_election_tt", "STP_cw_suspicion_15_tt"])
        both = {("STP", "has_active_mission", "STP_cw_election_window"): True,
                ("STP", "has_active_mission", "STP_cw_credentials_review"): True}
        extensions = [(scalar(e.value, "mission"), scalar(e.value, "days"))
                      for _, e in selected_effects(reward, both) if e.key == "add_days_mission_timeout"]
        self.assertEqual(extensions, [("STP_cw_election_window", "80"), ("STP_cw_credentials_review", "80")])
        only_vote = list(selected_effects(reward, {("STP", "has_active_mission", "STP_cw_election_window"): True}))
        self.assertEqual([(scalar(e.value, "mission"), scalar(e.value, "days"))
                          for _, e in only_vote if e.key == "add_days_mission_timeout"],
                         [("STP_cw_election_window", "80")])
        self.assertEqual([scalar(e.value, "value") for _, e in only_vote if e.key == "set_temp_variable"], ["15"])
        missed = list(selected_effects(reward, {}))
        self.assertFalse(any(e.key == "add_days_mission_timeout" for _, e in missed))
        self.assertFalse(any(e.key == "set_temp_variable" for _, e in missed))
        loc = (ROOT / "localisation/russian/ADISCORD_STP_l_russian.yml").read_text(encoding="utf-8-sig")
        self.assertIn("откладывает текущую сверку на §Y80 дней§!", loc)
        self.assertNotIn("откладывает текущую сверку на §Y14 дней§!", loc)
        tokens = (ROOT / "common/synchronized_dynamic_tokens/ADISCORD_tokens.txt").read_text(encoding="utf-8")
        self.assertIn("STP_cw_credentials_review", tokens.splitlines())

    def test_vorkerland_collapse_opens_dynamic_shabrat_asset_focuses(self):
        tree = next(e.value for e in entries("common/national_focus/ADISCORD_national_focus_STP.txt")
                    if e.key == "focus_tree" and scalar(e.value, "id") == "STP_focus")
        focuses = {scalar(e.value, "id"): e.value for e in tree if e.key == "focus"}
        for name, position, stock, treasury in (
            ("STP_cw_seize_vorkerland_stores", ("14", "3"), "1200", None),
            ("STP_cw_seize_vorkerland_accounts", ("14", "4"), None, "100"),
        ):
            with self.subTest(focus=name):
                focus = focuses[name]
                self.assertEqual(scalar(focus, "dynamic"), "yes")
                self.assertEqual((scalar(focus, "x"), scalar(focus, "y")), position)
                allow = block(focus, "allow_branch")
                self.assertIn(("has_country_flag", "STP_sided_with_Maksim_flag"),
                              [(e.key, e.value) for e in walk(allow)])
                self.assertIn(("has_global_flag", "ADISCORD_vorkerland_collapse_started"),
                              [(e.key, e.value) for e in walk(allow)])
                available = block(focus, "available")
                base = {("STP", "STP_cw_preparation_open", "yes"): True,
                        ("STP", "has_country_flag", "STP_sided_with_Maksim_flag"): True}
                self.assertFalse(matches_conditions(available, base))
                self.assertTrue(matches_conditions(available, {
                    **base, ("STP", "has_global_flag", "ADISCORD_vorkerland_collapse_started"): True}))
                reward = block(focus, "completion_reward")
                if stock:
                    self.assertEqual(scalar(block(focus, "prerequisite"), "focus"), "STP_cw_northern_dossier")
                    self.assertEqual(scalar(block(reward, "add_equipment_to_stockpile"), "amount"), stock)
                if treasury:
                    self.assertEqual(scalar(block(focus, "prerequisite"), "focus"), "STP_cw_seize_vorkerland_stores")
                    self.assertEqual(scalar(reward, "STP_receive_3000"), "yes")
                    self.assertIn("STP_cw_treasury_3000_tt",
                                  [e.value for e in reward if e.key == "custom_effect_tooltip"])
        outbreak = next(e.value for e in entries("events/ADISCORD_vorkerland_events.txt")
                        if e.key == "country_event" and scalar(e.value, "id") == "ADISCORD_vorkerland_collapse.1")
        immediate = [e for e in walk(block(outbreak, "immediate"))]
        flag_index = next(i for i, e in enumerate(immediate)
                          if e.key == "set_global_flag" and e.value == "ADISCORD_vorkerland_collapse_started")
        dirty = next(i for i, e in enumerate(immediate)
                     if e.key == "mark_focus_tree_layout_dirty" and e.value == "yes")
        self.assertLess(flag_index, dirty)
        refresh = block(entries("common/scripted_effects/ADISCORD_vorkerland_effects.txt"),
                        "ADISCORD_vorkerland_refresh_focus_lifecycle")
        self.assertTrue(any(e.key == "STP" and any(child.key == "mark_focus_tree_layout_dirty" for child in e.value)
                            for e in walk(refresh)))

    def test_capital_sabotage_stays_outside_ordinary_district_operations(self):
        decisions = block(entries("common/decisions/ADISCORD_STP_decisions.txt"), "STP_battle_for_stelander")
        capital = block(decisions, "STP_cw_sabotage_capital")
        industry = block(decisions, "STP_cw_sabotage_party_industry")
        self.assertEqual(scalar(capital, "days_remove"), "14")
        self.assertEqual(scalar(industry, "days_remove"), "14")
        self.assertEqual({e.value for e in block(capital, "targets")}, {"28"})
        self.assertEqual({e.value for e in block(industry, "targets")}, {"29"})
        tree = next(e.value for e in entries("common/national_focus/ADISCORD_national_focus_STP.txt")
                    if e.key == "focus_tree" and scalar(e.value, "id") == "STP_focus")
        focuses = {scalar(e.value, "id"): e.value for e in tree if e.key == "focus"}
        self.assertEqual((scalar(focuses["STP_cw_prepare_capital_sabotage"], "x"),
                          scalar(focuses["STP_cw_prepare_capital_sabotage"], "y")), ("5", "3"))
        self.assertEqual((scalar(focuses["STP_cw_prepare_industry_sabotage"], "x"),
                          scalar(focuses["STP_cw_prepare_industry_sabotage"], "y")), ("4", "4"))
        self.assertEqual(scalar(block(focuses["STP_cw_prepare_industry_sabotage"], "prerequisite"), "focus"),
                         "STP_cw_officer_contacts")
        for name, pp, suspicion in (("STP_cw_prepare_capital_sabotage", "75", "STP_cw_suspicion_8_tt"),
                                    ("STP_cw_prepare_industry_sabotage", "75", "STP_cw_suspicion_5_tt")):
            reward = block(focuses[name], "completion_reward")
            self.assertEqual(scalar(focuses[name], "cost"), "1")
            self.assertEqual(scalar(reward, "add_political_power"), pp)
            self.assertEqual(scalar(reward, "add_command_power"), "10")
            self.assertIn(suspicion, [e.value for e in reward if e.key == "custom_effect_tooltip"])
        self.assertNotIn("STP_region_is_operable", {e.key for e in walk(capital)})
        self.assertIn("STP_region_is_operable", {e.key for e in walk(industry)})
        initializer = block(entries("common/scripted_effects/ADISCORD_STP_scripted_effects.txt"),
                            "STP_initialize_battle_for_stelander")
        capital_start = block(initializer, "28")
        self.assertNotIn("STP_region_player_operations_allowed",
                         [e.value for e in capital_start if e.key == "set_state_flag"])
        self.assertIn("STP_region_player_operations_allowed",
                      [e.value for e in block(initializer, "29") if e.key == "set_state_flag"])

    def test_northern_aid_desk_stays_open_for_sts_and_does_not_use_preparation_slots(self):
        tree = next(e.value for e in entries("common/national_focus/ADISCORD_national_focus_STP.txt")
                    if e.key == "focus_tree" and scalar(e.value, "id") == "STP_focus")
        focus = next(e.value for e in tree if e.key == "focus" and scalar(e.value, "id") == "STP_cw_northern_desk")
        self.assertEqual((scalar(focus, "x"), scalar(focus, "y"), scalar(focus, "cost")), ("10", "3", "2"))
        self.assertEqual({e.value for e in block(focus, "prerequisite") if e.key == "focus"},
                         {"STP_cw_arm_the_north", "STP_cw_border_evidence"})
        arm = next(e.value for e in tree if e.key == "focus" and scalar(e.value, "id") == "STP_cw_arm_the_north")
        arm_reward = block(arm, "completion_reward")
        self.assertEqual(scalar(block(arm_reward, "add_equipment_to_stockpile"), "amount"), "7200")
        self.assertEqual(scalar(arm_reward, "add_political_power"), "60")
        dossier = next(e.value for e in tree if e.key == "focus" and scalar(e.value, "id") == "STP_cw_northern_dossier")
        dossier_reward = block(dossier, "completion_reward")
        self.assertEqual(scalar(dossier_reward, "add_political_power"), "25")
        self.assertEqual(scalar(block(dossier_reward, "add_intel"), "army_intel"), "15")
        self.assertEqual(scalar(block(dossier_reward, "add_intel"), "civilian_intel"), "10")
        evidence = next(e.value for e in tree if e.key == "focus" and scalar(e.value, "id") == "STP_cw_border_evidence")
        evidence_reward = block(evidence, "completion_reward")
        self.assertEqual(scalar(evidence_reward, "add_political_power"), "75")
        self.assertEqual(scalar(evidence_reward, "add_command_power"), "15")
        self.assertEqual(scalar(block(evidence_reward, "add_intel"), "army_intel"), "20")
        self.assertEqual(scalar(block(evidence_reward, "add_intel"), "civilian_intel"), "15")
        reward = block(focus, "completion_reward")
        self.assertEqual({e.value for e in reward if e.key == "unlock_decision_tooltip"},
                         {"STP_cw_fund_northern_forts", "STP_cw_send_northern_engineers", "STP_cw_sabotage_nodrul"})
        self.assertEqual(scalar(reward, "add_political_power"), "50")
        self.assertEqual(scalar(reward, "add_command_power"), "15")
        self.assertEqual(scalar(block(reward, "add_intel"), "army_intel"), "10")
        self.assertIn("STP_cw_northern_aid_open",
                      {e.value for e in walk(block(reward, "hidden_effect")) if e.key == "set_country_flag"})
        categories = entries("common/decisions/categories/ADISCORD_decision_categories_STP.txt")
        category = block(categories, "STP_cw_northern_aid")
        self.assertEqual(scalar(category, "visible_when_empty"), "yes")
        self.assertEqual(scalar(category, "priority"), "34")
        desk = block(entries("common/decisions/ADISCORD_STP_decisions.txt"), "STP_cw_northern_aid")
        for name in ("STP_cw_fund_northern_forts", "STP_cw_send_northern_engineers", "STP_cw_sabotage_nodrul"):
            decision = block(desk, name)
            self.assertEqual(scalar(decision, "cost"), "0")
            self.assertNotIn("STP_has_political_action_slot", {e.key for e in walk(decision)})
            self.assertNotIn("STP_cw_preparation_open", {e.key for e in walk(decision)})
            visible = block(decision, "visible")
            self.assertFalse(matches_conditions(visible, {}, "STS"))
            wartime = {("STS", "has_country_flag", "STP_cw_northern_aid_open"): True,
                       ("FROM", "has_state_flag", "STP_cw_northern_fort_built"): False,
                       ("FROM", "has_state_flag", "STP_cw_nod_rear_sabotaged"): False,
                       ("FROM", "STP_cw_northern_fort_state", "yes"): True,
                       ("FROM", "STP_cw_northern_target_valid", "yes"): True,
                       ("FROM", "has_war_with", "NOD"): True}
            self.assertTrue(matches_conditions(visible, wartime, "STS"), name)
        forts = block(desk, "STP_cw_fund_northern_forts")
        self.assertEqual(scalar(forts, "custom_cost_text"), "STP_cw_northern_fort_cost")
        self.assertEqual({e.key for e in block(forts, "complete_effect")}, {"hidden_effect"})
        busy = {("STP", "STP_cw_can_run_northern_aid", "yes"): True,
                ("STP", "has_variable", "STP_cw_northern_fort_deposit"): True,
                ("FROM", "STP_cw_northern_fort_state", "yes"): True}
        self.assertFalse(matches_conditions(block(forts, "available"), busy))
        self.assertTrue(matches_conditions(block(forts, "available"),
                                          {**busy, ("STP", "has_variable", "STP_cw_northern_fort_deposit"): False}))
        engineers = block(desk, "STP_cw_send_northern_engineers")
        self.assertEqual({e.key for e in block(engineers, "complete_effect")}, {"hidden_effect"})
        sabotage = block(desk, "STP_cw_sabotage_nodrul")
        self.assertEqual(scalar(sabotage, "days_remove"), "28")
        preview = block(block(sabotage, "remove_effect"), "effect_tooltip")
        self.assertEqual(scalar(block(block(preview, "NOD"), "add_timed_idea"), "idea"), "STP_cw_nod_disrupted_rear")
        self.assertEqual({scalar(e.value, "days") for e in walk(block(sabotage, "remove_effect"))
                          if e.key == "add_timed_idea" and scalar(e.value, "idea") == "STP_cw_nod_disrupted_rear"},
                         {"42"})
        self.assertEqual({e.value for e in block(sabotage, "targets")}, {"10", "11", "12", "13", "17", "18", "30"})
        transfer = block(entries("common/scripted_effects/ADISCORD_STP_scripted_effects.txt"),
                         "STP_cw_transfer_preparation_modifiers")
        paid = {("STP", "has_variable", "STP_cw_northern_fort_deposit"): True,
                ("STP", "has_variable", "STP_cw_northern_engineer_deposit"): True}
        self.assertEqual([(scope, scalar(e.value, "value")) for scope, e in selected_effects(transfer, paid)
                          if e.key == "add_to_variable" and scalar(e.value, "var") == "ADISCORD_economy_treasury"],
                         [("STS", "PREV.STP_cw_northern_fort_deposit"), ("STS", "PREV.STP_cw_northern_engineer_deposit")])
        start = block(entries("common/scripted_effects/ADISCORD_STP_scripted_effects.txt"), "STP_cw_start")
        self.assertNotIn("ADISCORD_economy_receive_100", {e.key for e in walk(start)
                                                          if e.key.startswith("ADISCORD_economy_receive")})
        loc = (ROOT / "localisation/russian/ADISCORD_STP_l_russian.yml").read_text(encoding="utf-8-sig")
        self.assertIn("STP_cw_northern_fort_cost_blocked:", loc)
        self.assertIn("объём военного производства §R-20%§!", loc)

    def test_campaign_stages_require_current_administrations_and_stop_after_three_successes(self):
        from itertools import product
        trigger = block(entries("common/scripted_triggers/ADISCORD_STP_scripted_triggers.txt"), "STP_cw_public_campaign_basis")
        for count, remaining, age2, age3, party in product(range(4), (140, 106, 105, 71, 70, 25), (0, 20, 21), (0, 20, 21), (False, True)):
            facts = {("STP", "has_active_mission", "STP_cw_election_window"): True,
                     ("STP", "variable", "STP_cw_completed_public_campaigns"): count,
                     ("STP", "variable", "days_mission_timeout@STP_cw_election_window"): remaining,
                     ("STP", "has_country_flag", "STP_sided_with_the_party_flag"): party}
            for state, age in (("2", age2), ("3", age3)):
                facts.update({(state, "is_owned_by", "STP"): True, (state, "is_controlled_by", "STP"): True,
                              (state, "has_state_flag", "STP_resistance_administration_asset"): age > 0,
                              (state, "flag_days", "STP_resistance_administration_asset"): age})
            expected = count == 0 or count == 1 and remaining <= 105 and (party or max(age2, age3) >= 21) or count == 2 and remaining <= 70 and (party or min(age2, age3) >= 21)
            self.assertEqual(matches_conditions(trigger, facts), expected, (count, remaining, age2, age3, party))
            self.assertFalse(matches_conditions(trigger, facts | {("STP", "has_active_mission", "STP_cw_election_window"): False}))
        base = {("STP", "has_active_mission", "STP_cw_election_window"): True,
                ("STP", "variable", "STP_cw_completed_public_campaigns"): 2,
                ("STP", "variable", "days_mission_timeout@STP_cw_election_window"): 70}
        for state in ("2", "3"):
            base.update({(state, "is_owned_by", "STP"): True, (state, "is_controlled_by", "STP"): True,
                         (state, "has_state_flag", "STP_resistance_administration_asset"): True,
                         (state, "flag_days", "STP_resistance_administration_asset"): 21})
        for state in ("2", "3"):
            for field in ("is_owned_by", "is_controlled_by"):
                self.assertFalse(matches_conditions(trigger, base | {(state, field, "STP"): False}))

    def test_campaign_count_is_earned_on_success_and_cleared_at_split(self):
        groups = entries("common/decisions/ADISCORD_STP_decisions.txt")
        campaign = block(block(groups, "STP_shabrat_election_bop_category"), "STP_cw_open_election_campaign")
        variable = "STP_cw_completed_public_campaigns"
        for reserved, basis, phase_open in ((True, True, True), (True, False, True), (True, True, False), (False, True, True)):
            facts = {("STP", "has_country_flag", "STP_cw_open_campaign_active"): reserved,
                     ("STP", "STP_cw_public_campaign_basis", "yes"): basis,
                     ("STP", "STP_cw_preparation_open", "yes"): phase_open,
                     ("STP", "has_active_mission", "STP_cw_election_window"): phase_open,
                     ("STP", "has_country_flag", "STP_sided_with_Maksim_flag"): True}
            success = reserved and basis and phase_open
            result = list(selected_effects(block(campaign, "remove_effect"), facts))
            writes = [e for _, e in result if e.key == "add_to_variable" and scalar(e.value, "var") == variable]
            self.assertEqual(len(writes), int(success))
            self.assertEqual(sum(e.key == "add_power_balance_value" for _, e in result), int(success))
            self.assertEqual(sum(e.key == "STP_political_action_slot_release" for _, e in result), int(reserved))
            for phase in ("complete_effect", "cancel_effect"):
                self.assertFalse(any(e.key == "add_to_variable" and scalar(e.value, "var") == variable
                                     for e in walk(block(campaign, phase))))
        effects = entries("common/scripted_effects/ADISCORD_STP_scripted_effects.txt")
        init = [e.value for e in walk(block(effects, "STP_cw_begin_elections"))
                if e.key == "set_variable" and scalar(e.value, "var") == variable]
        self.assertEqual([scalar(e, "value") for e in init], ["0"])
        self.assertIn(variable, [e.value for e in walk(block(effects, "STP_cw_start")) if e.key == "clear_variable"])

    def test_delegate_deals_cannot_repeat_past_a_strong_mandate(self):
        trigger = block(entries("common/scripted_triggers/ADISCORD_STP_scripted_triggers.txt"), "STP_cw_delegate_support_available")
        for side, sign in (("STP_sided_with_Maksim_flag", 1), ("STP_sided_with_the_party_flag", -1)):
            for support in (-.8, 0, .549, .55, .8):
                facts = {("STP", "has_country_flag", side): True,
                         ("STP", "power_balance_value", "STP_shabrat_election_legitimacy"): support * sign}
                self.assertEqual(matches_conditions(trigger, facts), support < .55)

    def test_election_operations_reject_late_starts_without_cancelling_paid_work(self):
        category = block(entries("common/decisions/ADISCORD_STP_decisions.txt"), "STP_shabrat_election_bop_category")
        for name, duration, predicate in (("STP_cw_open_election_campaign", 21, "STP_cw_public_campaign_basis"),
                                           ("STP_cw_negotiate_with_delegates", 14, "STP_cw_delegate_support_available")):
            action = block(category, name)
            facts = {("STP", "STP_has_political_action_slot", "yes"): True, ("STP", predicate, "yes"): True,
                     ("STP", "STP_cw_preparation_open", "yes"): True,
                     ("STP", "has_active_mission", "STP_cw_election_window"): True}
            for remaining in (1, duration, duration + 1, 140):
                current = facts | {("STP", "variable", "days_mission_timeout@STP_cw_election_window"): remaining}
                self.assertEqual(matches_conditions(block(action, "available"), current), remaining > duration)
                self.assertFalse(matches_conditions(block(action, "cancel_trigger"), current))

    def test_command_ai_and_timing_advice_share_the_actual_election_deadline(self):
        groups = entries("common/decisions/ADISCORD_STP_decisions.txt")
        decision = block(block(groups, "STP_battle_for_stelander"), "STP_cw_secure_election_result")
        veto = block(block(decision, "ai_will_do"), "modifier")
        condition = [e for e in veto if e.key != "factor"]
        text = next(e.value for e in entries("common/scripted_localisation/ADISCORD_STP_scripted_loc.txt")
                    if e.key == "defined_text" and scalar(e.value, "name") == "STPGetPublicAgreementTiming")
        for live in (False, True):
            for remaining in (0, 35, 36, 39, 40, 80, 81, 84, 85, 140):
                facts = {("STP", "has_active_mission", "STP_cw_election_window"): live,
                         ("STP", "variable", "days_mission_timeout@STP_cw_election_window"): remaining}
                self.assertEqual(matches_conditions(condition, facts), not live or not 40 <= remaining <= 80)
                selected = next(e.value for e in text if e.key == "text" and
                                (not any(x.key == "trigger" for x in e.value) or matches_conditions(block(e.value, "trigger"), facts)))
                expected = "no_election" if not live else "early" if remaining >= 85 else "late" if remaining <= 35 else "ready"
                self.assertEqual(scalar(selected, "localization_key"), "STP_cw_command_timing_" + expected)
                if live and 40 <= remaining <= 80:
                    self.assertLess(35, remaining)
                    self.assertGreater(35 + 50, remaining)

    def test_military_fund_ai_reserves_time_for_focus_and_paid_training(self):
        tree = next(e.value for e in entries("common/national_focus/ADISCORD_national_focus_STP.txt")
                    if e.key == "focus_tree" and scalar(e.value, "id") == "STP_focus")
        focus = next(e.value for e in tree if e.key == "focus" and scalar(e.value, "id") == "STP_cw_military_committee_fund")
        ai = block(focus, "ai_will_do")
        for remaining in (1, 35, 50, 70, 71, 90, 140):
            facts = {("STP", "has_active_mission", "STP_cw_election_window"): True,
                     ("STP", "variable", "days_mission_timeout@STP_cw_election_window"): remaining,
                     ("STP", "power_balance_value", "STP_shabrat_election_legitimacy"): 0}
            veto = any(matches_conditions([x for x in m.value if x.key != "factor"], facts)
                       for m in ai if m.key == "modifier" and scalar(m.value, "factor") == "0")
            self.assertEqual(veto, remaining <= 56, remaining)

    def test_new_prewar_branches_extend_downward_and_rewards_reach_resistance(self):
        tree = next(e.value for e in entries("common/national_focus/ADISCORD_national_focus_STP.txt")
                    if e.key == "focus_tree" and scalar(e.value, "id") == "STP_focus")
        focuses = {scalar(e.value, "id"): e.value for e in tree if e.key == "focus"}
        expected = {
            "STP_cw_reserve_commanders": ({"STP_cw_military_committee_fund", "STP_cw_abila_workshops"}, -3, 7),
            "STP_cw_casualty_routes": ({"STP_cw_supply_officers"}, 0, 6),
        }
        effects = entries("common/scripted_effects/ADISCORD_STP_scripted_effects.txt")
        transfer = block(effects, "STP_cw_transfer_preparation_modifiers")
        transferred = {scalar(e.value, "value") for e in walk(transfer) if e.key == "set_variable"}
        for name, (parents, x, y) in expected.items():
            focus = focuses[name]
            self.assertEqual({e.value for e in block(focus, "prerequisite")}, parents)
            self.assertEqual((int(scalar(focus, "x")), int(scalar(focus, "y"))), (x, y))
            for other, peer in focuses.items():
                if other == name or not any(e.key == "relative_position_id" and e.value == "STP_Show_Him_The_Truth" for e in peer):
                    continue
                if int(scalar(peer, "y")) == y:
                    self.assertGreaterEqual(abs(int(scalar(peer, "x")) - x), 2, (name, other))
            for write in (e.value for e in walk(block(focus, "completion_reward")) if e.key == "add_to_variable"):
                self.assertIn("STP." + scalar(write, "var"), transferred)

    def test_military_funding_choice_leaves_time_to_deliver_a_real_formation(self):
        tree = next(e.value for e in entries("common/national_focus/ADISCORD_national_focus_STP.txt")
                    if e.key == "focus_tree" and scalar(e.value, "id") == "STP_focus")
        focuses = {scalar(e.value, "id"): e.value for e in tree if e.key == "focus"}
        fund, workshops = (focuses[name] for name in ("STP_cw_military_committee_fund", "STP_cw_abila_workshops"))
        self.assertEqual(scalar(block(fund, "mutually_exclusive"), "focus"), scalar(workshops, "id"))
        self.assertEqual(scalar(block(workshops, "mutually_exclusive"), "focus"), scalar(fund, "id"))
        for focus in (fund, workshops):
            self.assertEqual(scalar(block(focus, "prerequisite"), "focus"), "STP_cw_abila_reserve")
            self.assertEqual(scalar(focus, "cost"), "4" if focus is fund else "3")
        reward = block(fund, "completion_reward")
        income = {scalar(e.value, "var"): float(scalar(e.value, "value")) for e in walk(reward) if e.key == "add_to_variable"}
        self.assertEqual(income, {"ADISCORD_economy_treasury": 18000, "ADISCORD_economy_current_month_action_income": 18000})
        self.assertEqual(float(scalar(block(reward, "add_power_balance_value"), "value")), -.10)
        self.assertFalse(any(e.key in {"create_unit", "add_manpower", "add_equipment_to_stockpile"} for e in walk(reward)))
        workshop_reward = block(block(workshops, "completion_reward"), "1")
        self.assertEqual(scalar(workshop_reward, "add_extra_state_shared_building_slots"), "4")
        factory = block(workshop_reward, "add_building_construction")
        self.assertEqual((scalar(factory, "type"), scalar(factory, "level")), ("arms_factory", "4"))
        preparation = block(entries("common/decisions/ADISCORD_STP_decisions.txt"), "STP_battle_for_stelander")
        train = block(preparation, "STP_cw_prepare_assault_group")
        capacity = next(e.value for e in walk(block(train, "available"))
                        if e.key == "check_variable" and scalar(e.value, "var") == "STP_cw_prepared_assault_divisions")
        self.assertEqual((scalar(capacity, "value"), scalar(capacity, "compare")), ("4", "less_than"))
        remaining = int(scalar(block(preparation, "STP_cw_election_window"), "days_mission_timeout"))
        reserve_days = int(scalar(focuses["STP_cw_abila_reserve"], "cost")) * 7
        self.assertGreater(remaining - reserve_days - int(scalar(fund, "cost")) * 7 - int(scalar(train, "days_remove")), 0)



if __name__ == "__main__":
    unittest.main()
