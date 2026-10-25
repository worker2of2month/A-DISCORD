"""Contracts for party recovery, scarce resources and exile settlement.

AST checks cover authored ordering and reachability, not native execution.
"""

import unittest
from itertools import product
from pathlib import Path
import re

from tools.tests.test_adiscord_stp_party_route import (
    read,
    children,
    one,
    walk,
    signature,
)
from tools.tests.test_adiscord_stp_preparation import (
    matches_conditions,
    selected_effects,
)
from tools.validators.validate_adiscord_division_templates import (
    Entry,
    parse_clausewitz,
)

EFFECTS = 'common/scripted_effects/ADISCORD_STP_scripted_effects.txt'
DECISIONS = 'common/decisions/ADISCORD_STP_decisions.txt'
TRIGGERS = 'common/scripted_triggers/ADISCORD_STP_scripted_triggers.txt'


def expand_survival_gates(items):
    """Expand only the new gates; pre-existing predicates are explicit scenario facts."""
    definitions = {e.key: e.value for e in parse_clausewitz(read(TRIGGERS))}
    names = {
        'STP_ps_nod_order_current',
        'STP_ps_can_launch_return',
        'STP_ps_val_sale_buyer_ready',
        'STP_ps_val_sale_open',
    }

    def expand(nodes):
        expanded = []
        for entry in nodes:
            if entry.key in names:
                if entry.value not in ('yes', 'no'):
                    raise AssertionError('Scripted triggers require boolean calls')
                body = expand(definitions[entry.key])
                expanded.append(
                    Entry('AND' if entry.value == 'yes' else 'NOT', body, entry.line)
                )
            else:
                value = (
                    expand(entry.value)
                    if isinstance(entry.value, list)
                    else entry.value
                )
                expanded.append(Entry(entry.key, value, entry.line, entry.quoted))
        return expanded

    return expand(items)


class CongressDefenceContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.effects = {e.key: e.value for e in parse_clausewitz(read(EFFECTS))}
        cls.decisions = {
            d.key: d.value
            for c in parse_clausewitz(read(DECISIONS))
            for d in c.value
            if isinstance(d.value, list)
        }

    def test_fortifications_finish_only_while_party_holds_congress(self):
        name = 'STP_cw_fortify_congress'
        self.assertIn(name, list(self.decisions))
        decision = self.decisions[name]
        self.assertEqual(one(decision, 'cost'), '0')
        self.assertEqual(one(decision, 'days_remove'), '15')
        self.assertEqual(one(decision, 'fire_only_once'), 'yes')
        for war, owner, controller, flanks in product((False, True), repeat=4):
            facts = {
                ('STP', 'STP_ps_war_active', 'yes'): war,
                ('STP', 'owns_state', '28'): owner,
                ('STP', 'controls_province', '145'): controller,
                ('STP', 'controls_province', '16374'): flanks,
                ('STP', 'controls_province', '16386'): flanks,
            }
            valid = war and owner and controller
            self.assertEqual(matches_conditions(one(decision, 'visible'), facts), valid)
            self.assertEqual(matches_conditions(one(decision, 'cancel_trigger'), facts), not valid)
            effects = [e for _, e in selected_effects(one(decision, 'remove_effect'), facts)]
            buildings = {
                one(e.value, 'province'): (one(e.value, 'type'), one(e.value, 'level'))
                for e in walk(effects) if e.key == 'add_building_construction'
            }
            expected = {}
            if valid:
                expected['145'] = ('bunker', '3')
                if flanks:
                    expected['16374'] = ('bunker', '2')
                    expected['16386'] = ('bunker', '2')
            self.assertEqual(buildings, expected)
        self.assertFalse(children(decision, 'complete_effect'))
        self.assertFalse(children(decision, 'cancel_effect'))

    def test_ai_starts_real_decision_once_and_after_player_handoff(self):
        name = 'STP_cw_ai_fortify_congress'
        self.assertIn(name, list(self.effects))
        for ai, active, war in product((False, True), repeat=3):
            facts = {
                ('STP', 'is_ai', 'yes'): ai,
                ('STP', 'has_decision', 'STP_cw_fortify_congress'): active,
                ('STP', 'STP_ps_war_active', 'yes'): war,
                ('STP', 'owns_state', '28'): True,
                ('STP', 'controls_province', '145'): True,
            }
            effects = [e for _, e in selected_effects(self.effects[name], facts)]
            self.assertEqual(
                [e.value for e in effects if e.key == 'activate_decision'],
                ['STP_cw_fortify_congress'] if ai and war and not active else [],
            )
        self.assertIn(name, str(signature(self.effects['STP_cw_begin_hostilities'])))
        events = parse_clausewitz(read('events/ADISCORD_STP_events.txt'))
        event = next(
            e.value for e in events
            if e.key == 'country_event' and one(e.value, 'id') == 'ADISCORD_STP_cw.94'
        )
        self.assertEqual(one(one(event, 'immediate'), name), 'yes')

    def test_guard_is_a_complete_starting_package_with_duplicate_protection(self):
        name = 'STP_cw_raise_congress_guard'
        self.assertIn(name, list(self.effects))
        gate = one(one(self.effects[name], 'if'), 'limit')
        for party, owner, controller, template in product((False, True), repeat=4):
            scope = 'STP' if party else 'STS'
            facts = {
                (scope, 'owns_state', '28'): owner,
                (scope, 'controls_province', '145'): controller,
                (scope, 'numeric', 'has_manpower'): 0,
                (scope, 'equipment', 'infantry_equipment'): 0,
                (scope, 'has_template', 'Congress Infantry Guard'): template,
            }
            valid = party and owner and controller and not template
            self.assertEqual(matches_conditions(gate, facts, scope), valid)
            effects = [e for _, e in selected_effects(self.effects[name], facts, scope)]
            self.assertEqual(sum(e.key == 'create_unit' for e in effects), 2 if valid else 0)
            self.assertFalse([
                e for e in effects
                if e.key in ('add_manpower', 'add_equipment_to_stockpile', 'STP_cw_pay_rifles')
            ])
        body = one(self.effects[name], 'if')
        template = one(body, 'division_template')
        regiments = one(template, 'regiments')
        support = one(template, 'support')
        units = one(parse_clausewitz(read('common/units/ADISCORD_land_units.txt')), 'sub_units')
        self.assertEqual(len(regiments), 6)
        self.assertTrue(all(e.key == 'infantry' for e in regiments))
        self.assertEqual([e.key for e in support], ['engineer'])
        self.assertEqual(one(template, 'priority'), '2')
        self.assertEqual(one(template, 'is_locked'), 'yes')
        self.assertEqual(one(template, 'force_allow_recruiting'), 'no')
        loop = one(one(body, '28'), 'for_loop_effect')
        count = int(one(loop, 'end'))
        self.assertEqual(count, 2)
        manpower = 0
        equipment = {}
        for slot in regiments + support:
            battalion = one(units, slot.key)
            manpower += count * int(one(battalion, 'manpower'))
            for need in one(battalion, 'need'):
                equipment[need.key] = equipment.get(need.key, 0) + count * int(need.value)
        self.assertEqual(manpower, 12600)
        self.assertEqual(equipment, {
            'infantry_equipment': 11340,
            'ADISCORD_squad_weapons_equipment': 96,
            'support_equipment': 60,
        })
        unit = one(loop, 'create_unit')
        division = parse_clausewitz(one(unit, 'division'))
        self.assertEqual(one(division, 'location'), '145')
        self.assertEqual(one(division, 'start_experience_factor'), '0.3')
        self.assertEqual(one(division, 'start_equipment_factor'), '1.0')
        self.assertEqual(one(division, 'start_manpower_factor'), '1.0')
        self.assertEqual(one(unit, 'owner'), 'STP')
        self.assertEqual(one(unit, 'allow_spawning_on_enemy_provs'), 'no')
        start = one(self.effects['STP_cw_start'], 'if')
        calls = [e.key for e in start]
        self.assertEqual(calls.count(name), 1)
        index = calls.index(name)
        before = str(signature(start[:index]))
        after = str(signature(start[index + 1:]))
        self.assertIn('STP_party_reinforced_garrison_asset', before)
        self.assertNotIn('STP_cw_mobilize_assault_division', before)
        self.assertIn('STP_cw_mobilize_assault_division', after)

    def test_guard_uses_standard_equipment_without_special_unlocks(self):
        body = one(self.effects['STP_cw_raise_congress_guard'], 'if')
        self.assertFalse([
            e for e in walk(body)
            if e.key in (
                'create_equipment_variant', 'complete_special_project',
                'set_technology', 'unlock_subunit',
            )
        ])
        loop = one(one(body, '28'), 'for_loop_effect')
        division = parse_clausewitz(one(one(loop, 'create_unit'), 'division'))
        self.assertFalse(children(division, 'force_equipment_variants'))

    def test_localisation_and_script_encoding(self):
        root = Path(__file__).resolve().parents[2]
        for language in ('russian', 'english'):
            path = root / f'localisation/{language}/ADISCORD_STP_l_{language}.yml'
            raw = path.read_bytes()
            self.assertTrue(raw.startswith(b'\xef\xbb\xbf'))
            lines = raw.decode('utf-8-sig').splitlines()
            for key in ('STP_cw_fortify_congress', 'STP_cw_fortify_congress_desc'):
                matches = [line for line in lines if line.startswith(f' {key}:')]
                self.assertEqual(len(matches), 1)
                self.assertRegex(matches[0], rf'^ {key}: "[^"\r\n]+"$')
            report = next(
                line for line in lines
                if line.startswith(' STP_battle_for_stelander_desc:')
            )
            self.assertIn('§Y2§!', report)
            self.assertIn('§Y6§!', report)
            self.assertNotIn('щит', report.lower())
            self.assertNotIn('shield', report.lower())
            self.assertNotIn('§Y6000§! £manpower_texticon', report)
            self.assertNotIn('§Y5400§! £infantry_equipment_texticon', report)
        for path in (EFFECTS, DECISIONS, 'events/ADISCORD_STP_events.txt'):
            self.assertFalse((root / path).read_bytes().startswith(b'\xef\xbb\xbf'))


class CivilWarAIReadinessContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ai = {
            e.key: e.value for e in parse_clausewitz(
                read('common/ai_strategy/ADISCORD_STP_civil_war.txt')
            )
        }

    def test_congress_guard_has_a_garrison_role_without_field_conversion(self):
        templates = parse_clausewitz(read('common/ai_templates/ADISCORD_land_templates.txt'))
        roles = [e.value for e in templates if children(e.value, 'role') == ['garrison']]
        self.assertEqual(len(roles), 1)
        targets = {e.key: e.value for e in roles[0] if isinstance(e.value, list)}
        self.assertIn('STP_congress_guard', list(targets))
        target = targets['STP_congress_guard']
        self.assertEqual(one(one(target, 'can_upgrade_in_field'), 'always'), 'no')
        self.assertEqual(
            signature(one(one(target, 'target_template'), 'regiments')),
            [('infantry', '6')],
        )
        self.assertEqual(
            signature(one(one(target, 'target_template'), 'support')),
            [('engineer', '1')],
        )
        for party, war, congress in product((False, True), repeat=3):
            scope = 'STP' if party else 'STS'
            facts = {
                (scope, 'is_ai', 'yes'): True,
                (scope, 'STP_ps_war_active', 'yes'): war,
                (scope, 'controls_province', '145'): congress,
                (scope, 'has_template', 'Congress Infantry Guard'): True,
            }
            self.assertEqual(
                matches_conditions(one(target, 'enable'), facts, scope),
                party and war and congress,
            )
        defence = self.ai['STP_cw_defend_fada']
        types = [one(e.value, 'type') for e in defence if e.key == 'ai_strategy']
        self.assertIn('garrison', types)
        self.assertIn('put_unit_buffers', types)

    def test_party_readiness_overrides_full_attack_but_not_initial_recovery(self):
        name = 'STP_ps_cautious_counterattack'
        self.assertIn(name, list(self.ai))
        policy = self.ai[name]
        for ready, stock, strength in product((False, True), (0.049, 0.05), (0.79, 0.8)):
            facts = {
                ('STP', 'is_ai', 'yes'): True,
                ('STP', 'STP_ps_can_counterattack', 'yes'): ready,
                ('STP', 'stockpile_ratio', 'infantry_equipment'): stock,
                ('STP', 'fighting_army_strength_ratio', 'STS'): strength,
            }
            self.assertEqual(
                matches_conditions(one(policy, 'enable'), facts),
                ready and (stock < 0.05 or strength < 0.8),
            )
        front = one(policy, 'ai_strategy')
        self.assertGreater(int(one(front, 'priority')), 1500)
        self.assertEqual(one(front, 'execution_type'), 'careful')
        self.assertEqual(one(front, 'execute_order'), 'yes')

    def test_shabrat_shortages_override_nod_assault_without_abandoning_front(self):
        name = 'STS_shabrat_cautious_nod_front'
        self.assertIn(name, list(self.ai))
        policy = self.ai[name]
        for war, stock, strength in product((False, True), (0.049, 0.05), (0.79, 0.8)):
            facts = {
                ('STS', 'is_ai', 'yes'): True,
                ('STS', 'has_capitulated', 'no'): True,
                ('STS', 'has_war_with', 'NOD'): war,
                ('STS', 'stockpile_ratio', 'infantry_equipment'): stock,
                ('STS', 'fighting_army_strength_ratio', 'NOD'): strength,
            }
            self.assertEqual(
                matches_conditions(one(policy, 'enable'), facts, 'STS'),
                war and (stock < 0.05 or strength < 0.8),
            )
        front = one(policy, 'ai_strategy')
        self.assertGreater(int(one(front, 'priority')), 1800)
        self.assertEqual(one(front, 'tag'), 'NOD')
        self.assertEqual(one(front, 'execute_order'), 'yes')
        self.assertEqual(one(front, 'manual_attack'), 'no')

    def test_shabrat_army_profile_does_not_duplicate_front_demand(self):
        army = self.ai['STS_shabrat_civil_war_army']
        self.assertFalse([
            e for e in army if e.key == 'ai_strategy'
            and one(e.value, 'type') == 'front_unit_request'
        ])
        front = self.ai['STS_cw_front_against_stp']
        self.assertTrue([
            e for e in front if e.key == 'ai_strategy'
            and one(e.value, 'type') == 'front_unit_request'
        ])


class PartySurvivalContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.effects = {e.key: e.value for e in parse_clausewitz(read(EFFECTS))}
        cls.decisions = {
            d.key: d.value
            for c in parse_clausewitz(read(DECISIONS))
            for d in c.value
            if isinstance(d.value, list)
        }

    def test_exile_precedes_peace_and_annexation(self):
        body = list(walk(self.effects['STP_cw_settle_union_victory']))
        positions = lambda key: [i for i, e in enumerate(body) if e.key == key]
        self.assertEqual(len(positions('STP_ps_prepare_exile')), 1)
        self.assertLess(
            positions('STP_ps_prepare_exile')[0], positions('white_peace')[0]
        )
        self.assertLess(
            positions('STP_ps_prepare_exile')[0], positions('annex_country')[0]
        )

    def test_recovery_missions_cannot_succeed_on_activation(self):
        for stage in (1, 2, 3):
            mission = self.decisions[f'STP_ps_reorg_{stage}']
            available = one(mission, 'available')
            self.assertEqual(one(one(available, 'hidden_trigger'), 'always'), 'no')
            self.assertEqual(one(mission, 'fire_only_once'), 'no')
            self.assertIn(
                'STP_ps_finish_stage', str(signature(one(mission, 'timeout_effect')))
            )

    def test_every_stage_has_a_free_escape_from_insolvency(self):
        for stage in (1, 2, 3):
            action = self.decisions[f'STP_ps_reorg_{stage}_administrative']
            self.assertEqual(one(action, 'cost'), '0')
            self.assertNotIn('ADISCORD_economy_treasury', str(signature(action)))

    def test_pause_saves_time_before_removing_mission(self):
        body = list(walk(self.effects['STP_ps_pause_reorganisation']))
        saves = [
            i
            for i, e in enumerate(body)
            if e.key == 'set_variable' and one(e.value, 'var') == 'STP_ps_paused_days'
        ]
        removes = [i for i, e in enumerate(body) if e.key == 'remove_mission']
        self.assertEqual(len(saves), 3)
        self.assertTrue(all(a < b for a, b in zip(saves, removes)))

    def test_reorganisation_initialization_is_guarded(self):
        body = one(self.effects['STP_ps_begin_defence'], 'if')
        gate = str(signature(one(body, 'limit')))
        self.assertIn('STP_ps_war_active', gate)
        self.assertIn('has_variable', gate)
        self.assertIn('STP_ps_stage', gate)

    def test_all_preparation_and_payment_combinations_respect_minimum_duration(self):
        base = [
            int(one(self.decisions[f'STP_ps_reorg_{s}'], 'days_mission_timeout'))
            for s in (1, 2, 3)
        ]
        self.assertEqual(base, [21, 21, 28])
        for radio, hq, *free in product((False, True), repeat=5):
            expected = 70 - 7 * (radio + hq) + 14 * sum(free)
            actual = sum(base)
            for stage in (1, 2, 3):
                decision = self.decisions[
                    f'STP_ps_reorg_{stage}_'
                    + ('administrative' if free[stage - 1] else 'funded')
                ]
                changes = [
                    e.value
                    for e in walk(decision)
                    if e.key == 'add_days_mission_timeout'
                ]
                self.assertEqual(
                    [one(c, 'days') for c in changes],
                    (['-7'] if stage < 3 else []) + (['14'] if free[stage - 1] else []),
                )
                actual += 14 * free[stage - 1]
                if stage < 3:
                    actual -= 7 * (radio if stage == 1 else hq)
            self.assertEqual(actual, expected)
            self.assertGreaterEqual(actual, 56)

    def test_credit_affordability_includes_fractional_boundary(self):
        gate = one(self.decisions['STP_ps_fund_nod'], 'custom_cost_trigger')
        for money, expected in ((749.9, False), (750, True), (750.1, True)):
            self.assertEqual(
                matches_conditions(
                    gate, {('STP', 'variable', 'ADISCORD_economy_treasury'): money}
                ),
                expected,
            )

    def test_receipts_are_cleared_before_delivery_or_refund(self):
        for name, clear, reward in (
            (
                'STP_ps_deliver_nod',
                'STP_ps_clear_nod_receipt',
                'add_equipment_to_stockpile',
            ),
            ('STP_ps_refund_nod', 'STP_ps_clear_nod_receipt', 'add_to_variable'),
            (
                'STP_ps_resolve_val_supply',
                'STP_ps_clear_val_receipt',
                'add_equipment_to_stockpile',
            ),
            (
                'STP_ps_refund_val_supply',
                'STP_ps_clear_val_receipt',
                'add_equipment_to_stockpile',
            ),
        ):
            keys = [e.key for e in walk(self.effects[name])]
            self.assertLess(keys.index(clear), keys.index(reward), name)

    def test_prewar_rifle_sale_shares_the_receipt_and_settles_each_payer(self):
        decision = self.decisions['STP_ps_val_sell_rifles']
        self.assertEqual(one(decision, 'cost'), '0')
        price = str(signature(one(decision, 'custom_cost_trigger')))
        self.assertIn('infantry_equipment', price)
        self.assertIn('25000', price)
        calls = [
            e
            for e in walk(one(decision, 'complete_effect'))
            if e.key == 'STP_ps_begin_val_sale'
        ]
        self.assertEqual(len(calls), 1)

        begin = list(walk(self.effects['STP_ps_begin_val_sale']))
        keys = [e.key for e in begin]
        self.assertEqual(keys[1:3], ['limit', 'STP_ps_val_sale_open'])
        self.assertLess(keys.index('STP_cw_pay_rifles'), keys.index('set_variable'))
        contracts = [
            one(e.value, 'value')
            for e in begin
            if e.key == 'set_variable' and one(e.value, 'var') == 'STP_ps_val_receipt_contract'
        ]
        self.assertEqual(contracts, ['5', '4'])
        self.assertIn('ADISCORD_STP_preparation.32', str(signature(begin)))

        accept = self.effects['STP_ps_accept_val_sale']
        paid = [e.key for e in walk(children(accept, 'if')[0])]
        self.assertLess(paid.index('ADISCORD_economy_spend_500'), paid.index('STP_ps_start_val_departure'))
        self.assertIn('STP_ps_cancel_val_sale', [e.key for e in walk(children(accept, 'else')[0])])

        refund = [e.key for e in walk(self.effects['STP_ps_refund_val_supply'])]
        self.assertLess(refund.index('STP_ps_clear_val_receipt'), refund.index('STP'))
        self.assertLess(refund.index('STP'), refund.index('STS'))

        resolve = signature(self.effects['STP_ps_resolve_val_supply'])
        self.assertIn("('var', 'STP_ps_val_shabrat_credit')", str(resolve))
        self.assertIn("('var', 'STP_ps_cargo_intercepted'), ('value', '0')", str(resolve))

        settle = list(walk(self.effects['STP_ps_settle_val_credit']))
        settle_keys = [e.key for e in settle]
        self.assertIn(('has_global_flag', 'STP_cw_started'), [(e.key, e.value) for e in settle])
        self.assertLess(settle_keys.index('clear_variable'), settle_keys.index('subtract_from_variable'))
        hostilities = [e.key for e in walk(self.effects['STP_cw_begin_hostilities'])]
        self.assertIn('STP_ps_settle_val_credit', hostilities)

    def test_prewar_sale_reserves_and_charges_the_quoted_package(self):
        begin = list(walk(self.effects['STP_ps_begin_val_sale']))
        for variable in ('STP_cw_rifle_cost', 'STP_ps_val_receipt_rifles'):
            amounts = [
                one(e.value, 'value')
                for e in begin
                if e.key in ('set_variable', 'set_temp_variable')
                and one(e.value, 'var') == variable
            ]
            self.assertEqual(amounts, ['25000'])

        facts = {
            ('STP', 'STP_cw_preparation_open', 'yes'): True,
            ('VAL', 'STP_ps_val_supply_open', 'yes'): True,
            ('VAL', 'STP_ps_val_sale_awaits_payment', 'yes'): True,
        }
        events = parse_clausewitz(read('events/ADISCORD_STP_events.txt'))
        event = next(
            e.value for e in events
            if e.key == 'country_event'
            and one(e.value, 'id') == 'ADISCORD_STP_preparation.32'
        )
        answer = next(
            option for option in children(event, 'option')
            if one(option, 'name') == 'ADISCORD_STP_preparation.32.a'
        )
        for money, affordable in ((499.9, False), (500, True), (500.1, True)):
            with self.subTest(money=money):
                facts[('STP', 'variable', 'ADISCORD_economy_treasury')] = money
                self.assertEqual(
                    matches_conditions(one(answer, 'trigger'), facts), affordable
                )
                selected = list(selected_effects(
                    self.effects['STP_ps_accept_val_sale'], facts
                ))
                payments = [
                    scope for scope, entry in selected
                    if entry.key == 'ADISCORD_economy_spend_500'
                ]
                self.assertEqual(payments, ['STP'] if affordable else [])
                receipts = [
                    (scope, one(entry.value, 'value'))
                    for scope, entry in selected
                    if entry.key == 'set_variable'
                    and one(entry.value, 'var') == 'STP_ps_val_receipt_money'
                ]
                self.assertEqual(receipts, [('VAL', '500')] if affordable else [])

        credits = [
            one(e.value, 'value')
            for e in walk(self.effects['STP_ps_resolve_val_supply'])
            if e.key == 'add_to_variable'
            and one(e.value, 'var') == 'STP_ps_val_shabrat_credit'
        ]
        self.assertEqual(credits, ['500'])

    def test_prewar_sale_stock_and_cooldown_gate_every_new_offer(self):
        triggers = {e.key: e.value for e in parse_clausewitz(read(TRIGGERS))}
        decision = self.decisions['STP_ps_val_sell_rifles']
        facts = {
            ('VAL', 'STP_ps_val_supply_open', 'yes'): True,
            ('VAL', 'has_country_flag', 'STP_ps_val_authorized'): True,
            ('STP', 'STP_cw_preparation_open', 'yes'): True,
            ('STP', 'STP_ps_val_sale_buyer_ready', 'yes'): True,
        }
        for rifles, affordable in ((24999.9, False), (25000, True), (25000.1, True)):
            for paused in (False, True):
                with self.subTest(rifles=rifles, paused=paused):
                    facts[('VAL', 'equipment', 'infantry_equipment')] = rifles
                    facts[('VAL', 'has_country_flag', 'STP_ps_val_sale_cooldown')] = paused
                    self.assertEqual(
                        matches_conditions(triggers['STP_ps_val_sale_open'], facts, 'VAL'),
                        affordable and not paused,
                    )
                    self.assertEqual(
                        matches_conditions(one(decision, 'custom_cost_trigger'), facts, 'VAL'),
                        affordable,
                    )
                    self.assertEqual(
                        matches_conditions(one(decision, 'available'), facts, 'VAL'),
                        not paused,
                    )

    def test_prewar_sale_checks_buyer_before_reserving_rifles(self):
        decision = self.decisions['STP_ps_val_sell_rifles']
        facts = {
            ('VAL', 'STP_ps_val_supply_open', 'yes'): True,
            ('VAL', 'has_country_flag', 'STP_ps_val_authorized'): True,
            ('VAL', 'equipment', 'infantry_equipment'): 25000,
            ('STP', 'STP_cw_preparation_open', 'yes'): True,
        }
        available = expand_survival_gates(one(decision, 'available'))
        begin = expand_survival_gates(self.effects['STP_ps_begin_val_sale'])
        for party, declined, money in product(
            (False, True), (False, True), (-100, 0, 499.9, 500, 500.1)
        ):
            with self.subTest(party=party, declined=declined, money=money):
                facts[('STP', 'has_country_flag', 'STP_sided_with_the_party_flag')] = party
                facts[('VAL', 'has_country_flag', 'STP_ps_val_sale_declined')] = declined
                facts[('STP', 'variable', 'ADISCORD_economy_treasury')] = money
                expected = not declined and (party or money >= 500)
                self.assertEqual(matches_conditions(available, facts, 'VAL'), expected)
                selected = list(selected_effects(begin, facts, 'VAL'))
                self.assertEqual(
                    any(e.key == 'STP_cw_pay_rifles' for _, e in selected), expected
                )

    def test_prewar_sale_refusal_closes_future_offers_only_while_pending(self):
        events = parse_clausewitz(read('events/ADISCORD_STP_events.txt'))
        event = next(
            e.value for e in events
            if e.key == 'country_event'
            and one(e.value, 'id') == 'ADISCORD_STP_preparation.32'
        )
        refusal = children(event, 'option')[0]
        self.assertEqual(one(refusal, 'name'), 'ADISCORD_STP_preparation.32.b')
        self.assertIn('STP_ps_decline_val_sale', [e.key for e in walk(refusal)])
        decline = self.effects['STP_ps_decline_val_sale']
        for pending in (False, True):
            selected = list(selected_effects(
                decline, {('VAL', 'STP_ps_val_sale_awaits_payment', 'yes'): pending}, 'VAL'
            ))
            self.assertEqual(
                [(scope, e.value) for scope, e in selected if e.key == 'set_country_flag'],
                [('VAL', 'STP_ps_val_sale_declined')] if pending else [],
            )
            self.assertEqual(
                [e.key for _, e in selected if e.key == 'STP_ps_cancel_val_sale'],
                ['STP_ps_cancel_val_sale'] if pending else [],
            )
        self.assertNotIn(
            'STP_ps_val_sale_declined', str(signature(self.effects['STP_ps_cancel_val_sale']))
        )

    def test_prewar_sale_pause_applies_to_both_sales_only_at_settlement(self):
        clear = self.effects['STP_ps_clear_val_receipt']
        for contract in range(6):
            facts = {('VAL', 'variable', 'STP_ps_val_receipt_contract'): contract}
            selected = list(selected_effects(clear, facts, 'VAL'))
            flags = {
                one(entry.value, 'flag'): one(entry.value, 'days')
                for scope, entry in selected if entry.key == 'set_country_flag'
            }
            self.assertEqual(flags['STP_ps_val_supply_cooldown'], '7')
            self.assertEqual(
                flags.get('STP_ps_val_sale_cooldown'),
                '90' if contract in (4, 5) else None,
            )
            if contract in (4, 5):
                keys = [entry.key for scope, entry in selected]
                self.assertLess(keys.index('set_country_flag'), keys.index('clear_variable'))

        for effect in ('STP_ps_resolve_val_supply', 'STP_ps_refund_val_supply'):
            self.assertIn('STP_ps_clear_val_receipt', [e.key for e in walk(self.effects[effect])])
        self.assertIn(
            'STP_ps_refund_val_supply',
            [e.key for e in walk(self.effects['STP_ps_cancel_val_sale'])],
        )

    def test_government_deadline_reads_current_control(self):
        triggers = {
            e.key: e.value
            for e in parse_clausewitz(
                read('common/scripted_triggers/ADISCORD_STP_scripted_triggers.txt')
            )
        }
        congress = triggers['STP_ps_holds_congress']
        self.assertEqual(signature(congress), [('controls_province', '145')])
        for owned in (False, True):
            for controlled in (False, True):
                self.assertEqual(
                    matches_conditions(
                        congress,
                        {
                            ('STP', 'controls_state', '28'): owned,
                            ('STP', 'controls_province', '145'): controlled,
                        },
                    ),
                    controlled,
                )
        self.assertIn(
            'STP_ps_government_operational',
            str(signature(self.effects['STP_ps_finish_stage'])),
        )
        self.assertIn(
            'STP_ps_government_operational',
            str(signature(self.effects['STP_ps_congress_timeout'])),
        )

    def test_congress_historical_penalty_cannot_repeat(self):
        first = next(
            e.value
            for e in walk(self.effects['STP_ps_open_congress_crisis'])
            if e.key == 'if'
            and 'STP_ps_congress_fell' in str(signature(one(e.value, 'limit')))
        )
        self.assertEqual(one(first, 'add_stability'), '-0.15')
        self.assertEqual(one(first, 'add_war_support'), '-0.10')
        self.assertIn(
            ('NOT', [('has_country_flag', 'STP_ps_congress_fell')]),
            signature(one(first, 'limit')),
        )

    def test_asylum_is_not_blocked_by_a_northern_defeat_or_human_host(self):
        triggers = {
            e.key: e.value
            for e in parse_clausewitz(
                read('common/scripted_triggers/ADISCORD_STP_scripted_triggers.txt')
            )
        }
        host = triggers['STP_ps_nod_can_host_exiles']
        for status, ai in product(range(5), (False, True)):
            facts = {
                ('NOD', 'tag', 'NOD'): True,
                ('NOD', 'exists', 'yes'): True,
                ('NOD', 'has_capitulated', 'no'): True,
                ('NOD', 'is_subject', 'no'): True,
                ('NOD', 'variable', 'STP_cw_northern_campaign_status'): status,
                ('NOD', 'is_ai', 'yes'): ai,
            }
            self.assertTrue(matches_conditions(host, facts, 'NOD'))
        self.assertNotIn("STP_ps_exile_handoff", self.effects)
        self.assertNotIn("STP_ps_handoff_accept", self.decisions)
        self.assertNotIn("NOD = { change_tag_from = STP }", read(EFFECTS))

    def test_no_paid_program_marks_a_military_victory(self):
        for name, effect in self.effects.items():
            if name.startswith('STP_ps_') and name.endswith('_finish'):
                self.assertNotIn(
                    'STP_cw_won_union_battle', str(signature(effect)), name
                )
                self.assertNotIn('transfer_state', {e.key for e in walk(effect)}, name)

    def test_interception_is_bound_to_the_paid_sequence(self):
        for action in ('val_intelligence', 'val_intercept'):
            name = 'STP_ps_' + action
            decision = str(signature(self.decisions[name]))
            finish = str(signature(self.effects[name + '_finish']))
            self.assertIn(name + '_sequence', decision)
            self.assertIn(name + '_sequence', finish)
            self.assertIn('VAL.STP_ps_val_sequence', finish)

    def test_unconnected_val_supply_waits_instead_of_delivering(self):
        branches = list(walk(self.effects['STP_ps_dispatch_val_supply']))
        route = next(e.value for e in branches if e.key == 'else_if')
        self.assertIn(('STP_ps_val_land_route', 'yes'), signature(one(route, 'limit')))
        self.assertIn(
            'STP_ps_val_route_wait',
            str(signature(self.effects['STP_ps_dispatch_val_supply'])),
        )

    def test_new_foci_resolve_and_exile_is_attached_without_tree_replacement(self):
        trees = parse_clausewitz(
            read('common/national_focus/ADISCORD_national_focus_STP.txt')
        )
        focuses = {
            one(e.value, 'id'): e.value
            for e in walk(trees)
            if e.key in ('focus', 'shared_focus') and isinstance(e.value, list)
        }
        new = {key for key in focuses if key.startswith('STP_ps_')}
        self.assertEqual(len(new), 29)
        for key in new:
            for block in children(focuses[key], 'prerequisite'):
                for entry in block:
                    self.assertIn(entry.value, focuses)
        shared = [e.value for e in trees if e.key == 'shared_focus']
        self.assertEqual(len(shared), 6)
        for f in shared:
            self.assertIn(('tag', 'NOD'), signature(one(f, 'allow_branch')))
            self.assertIn(
                ('has_country_flag', 'STP_ps_exile_received'),
                signature(one(f, 'allow_branch')),
            )
        self.assertNotIn(
            'load_focus_tree',
            {e.key for e in walk(self.effects['STP_ps_accept_exile'])},
        )

    def test_return_requires_real_capitulation_and_only_transfers_stp_cores(self):
        effect = self.effects['STP_ps_settle_return']
        self.assertIn(
            'has_capitulated', str(signature(one(one(effect, 'if'), 'limit')))
        )
        states = next(
            e.value
            for e in walk(effect)
            if e.key == 'every_owned_state' and any(c.key == 'limit' for c in e.value)
        )
        self.assertEqual(signature(one(states, 'limit')), [('is_core_of', 'STP')])
        self.assertNotIn('annex_country', {e.key for e in walk(effect)})

    def test_second_opposition_slot_never_clears_the_first(self):
        effect = self.effects['STP_cw_prepare_opposition_second']
        self.assertNotIn(
            ('clr_state_flag', 'STP_cw_opposition_target'),
            [(e.key, e.value) for e in walk(effect) if isinstance(e.value, str)],
        )
        gate = one(
            one(self.effects['STP_cw_schedule_opposition_second'], 'if'), 'limit'
        )
        self.assertIn(
            'days_mission_timeout@STP_cw_election_window', str(signature(gate))
        )
        self.assertIn('56', str(signature(gate)))

    def test_node_polling_is_bounded_to_five_points(self):
        effect = self.effects['STP_ps_poll_nodes']
        nodes = {e.value for e in walk(effect) if e.key == 'controls_province'}
        self.assertEqual(nodes, {'145', '16366', '45', '16345', '16445'})
        self.assertFalse(
            {'every_country', 'every_possible_country'} & {e.key for e in walk(effect)}
        )

    def test_local_towns_gate_only_their_party_owned_state(self):
        trigger = next(
            e.value
            for e in parse_clausewitz(read(TRIGGERS))
            if e.key == 'STP_ps_local_program_open'
        )
        for state, town in ((2, 16445), (29, 16345), (3, 45)):
            for owner, control in product(('STP', 'STS'), (False, True)):
                facts = {
                    (str(state), 'is_owned_by', 'STP'): owner == 'STP',
                    ('FROM', 'state', str(state)): True,
                    ('STP', 'controls_province', str(town)): control,
                }
                self.assertEqual(
                    matches_conditions(trigger, facts, str(state)),
                    owner != 'STP' or state == 3 or control,
                )

    def test_restored_party_reconstruction_does_not_fabricate_a_civil_war_win(self):
        trigger = next(
            e.value
            for e in parse_clausewitz(read(TRIGGERS))
            if e.key == 'STP_pw_can_reconstruct'
        )
        facts = {
            ('STP', 'has_capitulated', 'no'): True,
            ('STP', 'has_country_flag', 'STP_cw_postwar'): True,
            ('STP', 'has_global_flag', 'STP_cw_union_wars_finished'): True,
            ('STP', 'has_country_flag', 'STP_ps_restored_dependency'): True,
            ('STP', 'is_subject_of', 'NOD'): True,
        }
        self.assertTrue(matches_conditions(trigger, facts, 'STP'))
        self.assertFalse(
            matches_conditions(
                trigger, {**facts, ('STP', 'is_subject_of', 'NOD'): False}, 'STP'
            )
        )
        self.assertNotIn(
            'STP_cw_won_union_battle',
            str(signature(self.effects['STP_ps_settle_return'])),
        )

    def test_exile_orders_close_before_missions_and_cannot_outlive_the_route(self):
        close = self.effects['STP_ps_close_exile']
        keys = [e.key for e in close]
        self.assertLess(
            keys.index('STP_ps_exile_formation_refund'), keys.index('remove_mission')
        )
        self.assertIn(('clr_country_flag', 'STP_ps_exile_received'), signature(close))
        self.assertIn(
            'STP_ps_close_exile', str(signature(self.effects['STP_ps_settle_return']))
        )
        brigade = self.decisions['STP_ps_exile_formation']
        for gate in (
            one(brigade, 'custom_cost_trigger'),
            one(
                one(one(brigade, 'complete_effect'), 'hidden_effect')[0].value, 'limit'
            ),
        ):
            text = str(signature(gate))
            self.assertIn('6000', text)
            self.assertIn('600', text)

    def test_preparation_reuses_existing_categories_without_extra_tabs(self):
        categories = {e.key: e.value for e in parse_clausewitz(read(DECISIONS))}
        definitions = {
            e.key
            for e in parse_clausewitz(
                read('common/decisions/categories/ADISCORD_decision_categories_STP.txt')
            )
        }
        for old in (
            'STP_ps_party_programs',
            'STP_ps_northern_support',
            'STP_ps_supply_routes',
            'STP_cw_war_council',
            'STP_cw_external_intervention',
        ):
            self.assertNotIn(old, categories)
            self.assertNotIn(old, definitions)
        elections = {e.key for e in categories['STP_elections_in_the_party']}
        domestic = {
            'STP_ps_build_radio',
            'STP_ps_build_hq',
            'STP_ps_prepare_evacuation',
        }
        foreign = {
            'STP_ps_fund_nod',
            'STP_ps_arm_nod',
            'STP_ps_val_intelligence',
            'STP_ps_val_intercept',
        }
        self.assertTrue(domestic <= {e.key for e in categories['STP_party_factions']})
        self.assertTrue(
            foreign <= {e.key for e in categories['STP_military_operations']}
        )
        self.assertFalse((domestic | foreign) & elections)
        council = {e.key for e in categories['STP_military_operations']}
        self.assertTrue(
            {'STP_ps_reorg_1_funded', 'STP_ps_ammunition', 'STP_ps_transport'}
            <= council
        )

    def test_new_localisation_preserves_native_encoding_and_single_line_values(self):
        root = Path(__file__).resolve().parents[2]
        raw = (root / 'localisation/russian/ADISCORD_STP_l_russian.yml').read_bytes()
        self.assertTrue(raw.startswith(b'\xef\xbb\xbf'))
        keys = []
        for line in raw.decode('utf-8-sig').splitlines():
            if line.lstrip().startswith('STP_ps_'):
                self.assertRegex(line, r'^ STP_ps_\w+:\d* "(?:[^"\\]|\\.)*"$')
                keys.append(line.split(':', 1)[0])
        self.assertEqual(len(keys), len(set(keys)))
        for path in (EFFECTS, DECISIONS):
            self.assertFalse((root / path).read_bytes().startswith(b'\xef\xbb\xbf'))

    def test_nod_predeparture_refunds_a_stale_purpose_without_shipping(self):
        # A still-friendly host is not enough once the northern war or intervention ends.
        dispatcher = expand_survival_gates(self.effects['STP_ps_dispatch_nod'])
        for kind, north, possible, entered, war, route, host in product(
            range(1, 5),
            (False, True),
            (False, True),
            (False, True),
            (False, True),
            (False, True),
            (False, True),
        ):
            facts = {
                ('STP', 'variable', 'STP_ps_nod_receipt_stage'): 1,
                ('STP', 'variable', 'STP_ps_nod_receipt_type'): kind,
                ('STP', 'STP_ps_can_aid_nod', 'yes'): host,
                ('STP', 'STP_ps_nod_supply_route', 'yes'): route,
                ('NOD', 'STP_ps_northern_front_active', 'yes'): north,
                ('NOD', 'NOD_cw_intervention_possible', 'yes'): possible,
                ('NOD', 'has_country_flag', 'NOD_cw_entered'): entered,
                ('NOD', 'has_war_with', 'STS'): war,
            }
            current = host and (
                kind == 1
                or kind in (2, 3)
                and north
                or kind == 4
                and (possible or entered and war)
            )
            effects = list(selected_effects(dispatcher, facts))
            calls = [
                (scope, e.key, e.value)
                for scope, e in effects
                if e.key in {'activate_mission', 'STP_ps_refund_nod'}
            ]
            expected = (
                (
                    'activate_mission',
                    'STP_ps_nod_delivery' if route else 'STP_ps_nod_route_wait',
                )
                if current
                else ('STP_ps_refund_nod', 'yes')
            )
            self.assertEqual(
                calls,
                [('STP', *expected)],
                (kind, north, possible, entered, war, route, host),
            )

    def test_nod_wait_and_dispatch_cancel_on_the_same_current_purpose(self):
        definitions = {e.key: e.value for e in parse_clausewitz(read(TRIGGERS))}
        self.assertIn('STP_ps_nod_order_current', set(definitions))
        for name in ('STP_ps_nod_dispatch', 'STP_ps_nod_route_wait'):
            gate = one(self.decisions[name], 'cancel_trigger')
            self.assertEqual(signature(gate), [('STP_ps_nod_order_current', 'no')])
        # Revocation before departure returns the original deposit, never a fixed new price.
        refund = list(walk(self.effects['STP_ps_refund_nod']))
        save = next(
            e.value
            for e in refund
            if e.key == 'set_temp_variable' and one(e.value, 'var') == 'STP_ps_refund'
        )
        self.assertEqual(one(save, 'value'), 'STP_ps_nod_receipt_money')

    def test_return_requires_training_and_a_live_nonallied_target(self):
        definitions = {e.key: e.value for e in parse_clausewitz(read(TRIGGERS))}
        self.assertIn('STP_ps_can_launch_return', set(definitions))
        gate = definitions['STP_ps_can_launch_return']
        for training, alive, allied, own_subject, active, closed, war in product(
            (False, True), repeat=7
        ):
            facts = {
                ('NOD', 'STP_ps_nod_can_host_exiles', 'yes'): True,
                ('NOD', 'has_country_flag', 'STP_ps_exile_received'): True,
                ('NOD', 'has_completed_focus', 'STP_ps_return_campaign_focus'): True,
                ('NOD', 'has_country_flag', 'STP_ps_return_terms_accepted'): True,
                (
                    'NOD',
                    'has_country_flag',
                    'STP_ps_exile_training_completed',
                ): training,
                ('NOD', 'has_country_flag', 'STP_ps_return_campaign'): active,
                ('NOD', 'has_country_flag', 'STP_ps_return_closed'): closed,
                ('NOD', 'has_war_with', 'STS'): war,
                ('NOD', 'is_in_faction_with', 'STS'): allied,
                ('STP', 'exists', 'no'): True,
                ('STS', 'exists', 'yes'): True,
                ('STS', 'has_capitulated', 'no'): alive,
                ('STS', 'is_subject_of', 'NOD'): own_subject,
            }
            self.assertEqual(
                matches_conditions(gate, facts, 'NOD'),
                training and alive and not (allied or own_subject or active or closed),
            )

    def test_return_declaration_and_ui_share_the_same_gate(self):
        gate = one(one(self.effects['STP_ps_begin_return'], 'if'), 'limit')
        self.assertEqual(signature(gate), [('STP_ps_can_launch_return', 'yes')])
        ui = one(
            one(self.decisions['STP_ps_launch_return'], 'available'),
            'custom_trigger_tooltip',
        )
        self.assertIn(('STP_ps_can_launch_return', 'yes'), signature(ui))
        # A failed native declaration may not leave a campaign marked as running.
        branches = children(one(self.effects['STP_ps_begin_return'], 'if'), 'if')
        receipt = next(
            (
                b
                for b in branches
                if any(
                    e.key == 'set_country_flag' and e.value == 'STP_ps_return_campaign'
                    for e in b
                )
            ),
            None,
        )
        self.assertIsNotNone(receipt)
        self.assertEqual(signature(one(receipt, 'limit')), [('has_war_with', 'STS')])
        for war in (False, True):
            facts = {
                ('NOD', 'STP_ps_can_launch_return', 'yes'): True,
                ('NOD', 'has_war_with', 'STS'): war,
            }
            payload = list(
                selected_effects(self.effects['STP_ps_begin_return'], facts, 'NOD')
            )
            self.assertEqual(
                sum(e.key == 'declare_war_on' for _, e in payload), int(not war)
            )

    def test_arrested_hedersett_cannot_escape_or_be_restored(self):
        definitions = {e.key: e.value for e in parse_clausewitz(read(TRIGGERS))}
        self.assertIn('STP_ps_hedersett_available', set(definitions))
        gate = definitions['STP_ps_hedersett_available']
        self.assertEqual(one(gate, 'has_character'), 'STP_rufus_hedersett')
        character_gate = one(gate, 'STP_rufus_hedersett')
        for arrested in (False, True):
            facts = {
                (
                    'STP_rufus_hedersett',
                    'has_character_flag',
                    'STP_cw_arrested',
                ): arrested
            }
            self.assertEqual(
                matches_conditions(character_gate, facts, 'STP_rufus_hedersett'),
                not arrested,
            )
        for name in ('STP_ps_accept_exile', 'STP_ps_settle_return'):
            guarded = [
                e.value
                for e in walk(self.effects[name])
                if e.key == 'if' and any(c.key == 'set_nationality' for c in e.value)
            ]
            self.assertEqual(len(guarded), 1, name)
            self.assertIn(
                ('STP_ps_hedersett_available', 'yes'),
                signature(one(guarded[0], 'limit')),
            )


class PartyWartimeFocusContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        tree = parse_clausewitz(
            read('common/national_focus/ADISCORD_national_focus_STP.txt')
        )
        cls.foci = {
            one(e.value, 'id'): e.value
            for e in walk(tree)
            if e.key == 'focus' and isinstance(e.value, list)
        }
        cls.decisions = {
            e.key: e.value
            for e in walk(parse_clausewitz(read(DECISIONS)))
            if isinstance(e.value, list)
        }

    def reachable(self, *, congress, port, niansas, stage, government=True, fell=True):
        facts = {
            ('STP', 'STP_ps_war_active', 'yes'): True,
            ('STP', 'STP_ps_government_operational', 'yes'): government,
            ('STP', 'STP_ps_can_counterattack', 'yes'): stage == 4 and government,
            ('STP', 'has_country_flag', 'STP_ps_congress_fell'): fell,
            ('STP', 'variable', 'STP_ps_stage'): stage,
            ('STP', 'owns_state', '28'): True,
            ('STP', 'controls_province', '145'): congress,
            ('STP', 'controls_province', '16366'): port,
            ('STP', 'controls_province', '45'): niansas,
            ('STP', 'controls_province', '16351'): congress,
        }
        done = {'STP_cw_unified_headquarters'}
        changed = True
        while changed:
            changed = False
            for name, focus in self.foci.items():
                if name in done:
                    continue
                # Only the party-only wartime branches are under review here.
                branch = next((e.value for e in focus if e.key == 'allow_branch'), [])
                if ('tag', 'STP') not in signature(branch) or (
                    'NOT',
                    [('has_country_flag', 'STP_cw_postwar')],
                ) not in signature(branch):
                    continue
                groups = children(focus, 'prerequisite')
                if not all(any(e.value in done for e in group) for group in groups):
                    continue
                if matches_conditions(
                    next((e.value for e in focus if e.key == 'available'), []),
                    facts,
                    'STP',
                ):
                    done.add(name)
                    changed = True
        return done

    def test_lost_capital_and_niansas_do_not_cut_off_staff_or_intelligence(self):
        for stage in (1, 2, 3, 4):
            done = self.reachable(
                congress=False, port=False, niansas=False, stage=stage
            )
            self.assertTrue(
                {
                    'STP_ps_temporary_presidium',
                    'STP_ps_restore_couriers',
                    'STP_party_rear_administration',
                    'STP_ps_counter_supply',
                }
                <= done
            )
            self.assertNotIn('STP_ps_route_security', done)
            self.assertEqual('STP_party_war_directorate' in done, stage >= 2)
            self.assertEqual('STP_cw_capital_counteroffensive' in done, stage == 4)
            self.assertEqual('STP_cw_assault_columns' in done, stage == 4)

    def test_port_can_be_defended_while_the_government_is_displaced(self):
        done = self.reachable(
            congress=False, port=True, niansas=False, stage=1, government=False
        )
        self.assertTrue({'STP_cw_guard_the_pier', 'STP_cw_harbour_batteries'} <= done)
        self.assertNotIn('STP_party_war_directorate', done)
        gate = one(self.decisions['STP_cw_hold_the_pier'], 'available')
        self.assertIn(('controls_province', '16366'), signature(gate))
        self.assertNotIn(('controls_state', '28'), signature(gate))

    def test_supply_is_usable_inside_the_defensive_phase(self):
        headquarters = float(one(self.foci['STP_cw_unified_headquarters'], 'cost')) * 7
        transport = float(one(self.foci['STP_party_war_transport'], 'cost')) * 7
        delivery = int(
            one(self.decisions['STP_ps_transport_work'], 'days_mission_timeout')
        )
        self.assertEqual(headquarters + transport + delivery, 49)
        self.assertLess(headquarters + transport + delivery, 56)
        groups = children(self.foci['STP_ps_ammunition_board'], 'prerequisite')
        self.assertEqual(
            [set(e.value for e in group) for group in groups],
            [{'STP_party_war_transport', 'STP_cw_wartime_arsenals'}],
        )

    def test_first_paid_cabinet_response_fits_deadline_and_free_response_stays_open(
        self,
    ):
        focus_days = float(one(self.foci['STP_ps_temporary_presidium'], 'cost')) * 7
        mission_days = int(
            one(self.decisions['STP_ps_cabinet_work'], 'days_mission_timeout')
        )
        paid = self.decisions['STP_ps_emergency_cabinet']
        delta = next(
            int(one(e.value, 'days'))
            for e in walk(paid)
            if e.key == 'add_days_mission_timeout'
        )
        deadline = int(
            one(self.decisions['STP_ps_congress_deadline'], 'days_mission_timeout')
        )
        reward = one(self.foci['STP_ps_temporary_presidium'], 'completion_reward')
        extension = next(
            e.value for e in walk(reward) if e.key == 'add_days_mission_timeout'
        )
        self.assertEqual(one(extension, 'mission'), 'STP_ps_congress_deadline')
        self.assertLess(
            focus_days + mission_days + delta, deadline + int(one(extension, 'days'))
        )
        for gate in (
            one(paid, 'visible'),
            one(paid, 'available'),
            one(paid, 'complete_effect'),
        ):
            self.assertIn('STP_ps_temporary_presidium', str(signature(gate)))
        for name in (
            'STP_ps_emergency_cabinet_administrative',
            'STP_ps_emergency_cabinet_prepared',
        ):
            self.assertNotIn(
                'STP_ps_temporary_presidium', str(signature(self.decisions[name]))
            )

    def test_restored_couriers_unlock_a_real_order_with_its_command_price(self):
        reward = one(self.foci['STP_ps_restore_couriers'], 'completion_reward')
        self.assertEqual(one(reward, 'add_command_power'), '25')
        order = self.decisions['STP_cw_regroup_the_front']
        visible = one(order, 'visible')
        self.assertTrue(
            matches_conditions(
                visible,
                {('STP', 'has_completed_focus', 'STP_ps_restore_couriers'): True,
                 ('STP', 'has_war', 'yes'): True},
            )
        )
        self.assertEqual(one(one(order, 'complete_effect'), 'add_command_power'), '-25')

    def test_returning_government_needs_actual_recapture(self):
        for held, lost in product((False, True), repeat=2):
            gate = one(self.foci['STP_ps_retake_congress'], 'available')
            facts = {
                ('STP', 'STP_ps_war_active', 'yes'): True,
                ('STP', 'controls_province', '145'): held,
                ('STP', 'has_country_flag', 'STP_ps_congress_fell'): lost,
            }
            self.assertEqual(matches_conditions(gate, facts), held and lost)
        reward = one(self.foci['STP_ps_retake_congress'], 'completion_reward')
        self.assertFalse(
            {'transfer_state', 'set_state_controller_to', 'add_timed_idea'}
            & {e.key for e in walk(reward)}
        )

    def test_inner_ring_builds_only_in_held_city_nodes(self):
        from tools.tests.test_adiscord_stp_preparation import selected_effects

        reward = one(self.foci['STP_cw_inner_ring'], 'completion_reward')
        for left, right in product((False, True), repeat=2):
            facts = {
                ('STP', 'controls_province', '16351'): left,
                ('STP', 'controls_province', '16377'): right,
            }
            output = list(selected_effects(reward, facts))
            provinces = {
                one(e.value, 'province')
                for _, e in output
                if e.key == 'add_building_construction'
            }
            self.assertEqual(
                provinces,
                {p for p, held in [('16351', left), ('16377', right)] if held},
            )


if __name__ == '__main__':
    unittest.main()


class PartyUsabilityContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.effects = {e.key: e.value for e in parse_clausewitz(read(EFFECTS))}
        cls.triggers = {e.key: e.value for e in parse_clausewitz(read(TRIGGERS))}
        cls.owners = {}
        cls.decisions = {}
        for category in parse_clausewitz(read(DECISIONS)):
            for entry in category.value:
                if isinstance(entry.value, list):
                    if entry.key in cls.owners:
                        raise AssertionError('Duplicate decision: ' + entry.key)
                    cls.owners[entry.key] = category.key
                    cls.decisions[entry.key] = entry.value
        cls.categories = {
            e.key: e.value
            for e in parse_clausewitz(
                read('common/decisions/categories/ADISCORD_decision_categories_STP.txt')
            )
        }

    def test_recovery_stage_has_a_real_but_defence_safe_penalty(self):
        for active in (False, True):
            for stage, expected in ((1, -0.45), (2, -0.3), (3, -0.15), (4, 0)):
                facts = {
                    ('STP', 'STP_ps_war_active', 'yes'): active,
                    ('STP', 'variable', 'STP_ps_stage'): stage,
                }
                values = {}
                for _, e in selected_effects(
                    self.effects['STP_ps_refresh_defence'], facts
                ):
                    if e.key == 'set_variable':
                        values[one(e.value, 'var')] = float(one(e.value, 'value'))
                self.assertEqual(
                    values.get('STP_ps_breakthrough'), expected if active else 0
                )
                self.assertNotIn('STP_ps_stage', values)
        dynamic = one(
            parse_clausewitz(
                read('common/dynamic_modifiers/ADISCORD_dynamic_modifiers_STP.txt')
            ),
            'STP_ps_defence_dynamic',
        )
        self.assertEqual(one(dynamic, 'breakthrough_factor'), 'STP_ps_breakthrough')
        self.assertNotIn('army_defence_factor', {e.key for e in dynamic})

    def test_foreign_operations_share_the_military_category(self):
        names = [
            'STP_ps_fund_nod',
            'STP_ps_arm_nod',
            'STP_ps_engineers_nod',
            'STP_ps_expedition_nod',
            'STP_ps_nod_dispatch',
            'STP_ps_nod_delivery',
            'STP_ps_cancel_nod',
            'STP_ps_nod_route_wait',
            'STP_ps_evacuate_funds',
            'STP_ps_val_intelligence',
            'STP_ps_val_intelligence_work',
            'STP_ps_val_intercept',
            'STP_ps_val_intercept_work',
            'STP_ps_val_pressure',
            'STP_ps_val_pressure_work',
            'STP_pw_party_nod_invasion_countdown',
            'STP_pw_party_nod_emergency_mobilization',
            'STP_pw_party_nod_fortify_border',
            'STP_pw_party_nod_staff_readiness',
        ]
        for name in names:
            self.assertEqual(self.owners[name], 'STP_military_operations', name)
        self.assertNotIn('STP_postwar_nod_ultimatum', self.categories)

    def test_domestic_preparation_sits_with_the_party_apparatus(self):
        for name in (
            'STP_ps_build_radio',
            'STP_ps_build_radio_work',
            'STP_ps_build_hq',
            'STP_ps_build_hq_work',
            'STP_ps_prepare_evacuation',
            'STP_ps_prepare_evacuation_work',
        ):
            self.assertEqual(self.owners[name], 'STP_party_factions', name)

    def test_elections_close_and_external_work_remains_visible(self):
        election = one(self.categories['STP_elections_in_the_party'], 'visible')
        self.assertFalse(
            matches_conditions(
                election,
                {
                    ('STP', 'has_global_flag', 'STP_cw_started'): True,
                    ('STP', 'has_country_flag', 'STP_sided_with_the_party_flag'): True,
                    ('STP', 'has_variable', 'STP_ps_nod_receipt_type'): True,
                },
            )
        )
        external = one(self.categories['STP_military_operations'], 'visible')
        self.assertTrue(
            matches_conditions(
                external,
                {
                    ('STP', 'tag', 'STP'): True,
                    ('STP', 'has_country_flag', 'STP_sided_with_the_party_flag'): True,
                    ('STP', 'STP_cw_preparation_open', 'yes'): True,
                },
            )
        )
        self.assertTrue(
            matches_conditions(
                external, {('STP', 'has_variable', 'STP_ps_nod_receipt_type'): True}
            )
        )
        self.assertEqual(
            one(self.categories['STP_military_operations'], 'visible_when_empty'), 'yes'
        )

    def test_current_supply_deadline_is_checked_before_both_payments(self):
        for action, threshold in (('val_intelligence', 22), ('val_intercept', 15)):
            name = 'STP_ps_' + action
            trigger = name + '_time_available'
            self.assertIn(trigger, self.triggers)
            gate = self.triggers[trigger]
            for days in (0, threshold - 0.01, threshold, threshold + 1):
                facts = {
                    ('VAL', 'has_active_mission', 'STP_ps_val_departure'): True,
                    (
                        'VAL',
                        'variable',
                        'days_mission_timeout@STP_ps_val_departure',
                    ): days,
                }
                self.assertEqual(matches_conditions(gate, facts), days >= threshold)
                facts[('VAL', 'has_active_mission', 'STP_ps_val_departure')] = False
                self.assertFalse(matches_conditions(gate, facts))
            for phase in ('available', 'complete_effect'):
                self.assertIn(trigger, str(signature(one(self.decisions[name], phase))))
        tokens = read(
            'common/synchronized_dynamic_tokens/ADISCORD_tokens.txt'
        ).splitlines()
        self.assertIn('STP_ps_val_departure', tokens)

    def test_pressure_delays_the_current_departure_not_only_future_cargo(self):
        body = self.effects['STP_ps_val_pressure_finish']
        changes = [
            (scope, one(e.value, 'mission'), one(e.value, 'days'))
            for scope, e in selected_effects(
                body,
                {
                    ('STP', 'has_variable', 'STP_ps_val_pressure_deposit'): True,
                    ('STP', 'tag', 'STP'): True,
                    ('STP', 'STP_cw_preparation_open', 'yes'): True,
                    ('STP', 'STP_ps_supply_program_unlocked', 'yes'): True,
                    ('VAL', 'exists', 'yes'): True,
                    ('VAL', 'has_active_mission', 'STP_ps_val_departure'): True,
                },
            )
            if e.key == 'add_days_mission_timeout'
        ]
        self.assertEqual(changes, [('VAL', 'STP_ps_val_departure', '14')])
        self.assertIn('STP_ps_val_pressure_deposit', str(signature(body)))

    def test_nod_credit_requires_a_live_military_purpose(self):
        name = 'STP_ps_nod_credit_useful'
        self.assertIn(name, self.triggers)
        gate = self.triggers[name]
        self.assertFalse(matches_conditions(gate, {}))
        for condition in (
            'STP_ps_northern_front_active',
            'NOD_cw_intervention_possible',
        ):
            self.assertTrue(matches_conditions(gate, {('NOD', condition, 'yes'): True}))
        for phase in ('available', 'complete_effect'):
            self.assertIn(
                name, str(signature(one(self.decisions['STP_ps_fund_nod'], phase)))
            )

    def test_briefings_are_compact_and_keep_operational_status(self):
        for lang in ('russian', 'english'):
            loc = read('localisation/' + lang + '/ADISCORD_STP_l_' + lang + '.yml')
            values = dict(re.findall(r'^ ([\w.]+):(?:\d+)?\s*"(.*)"$', loc, re.M))
            for key in (
                'STP_PARTY_ELECTION_BRIEFING',
                'STP_ps_preparation_report',
                'STP_ps_war_report',
                'STP_party_factions_desc',
                'STP_military_operations_desc',
            ):
                self.assertLessEqual(len(values[key]), 560, key)
            for report in (
                'STPGetPartySurvival',
                'STPGetRecoveryReport',
                'STPGetKefreytArmyCommitment',
                'STPGetCoalitionReport',
                'STPGetWarStrainReport',
                'STPGetStalledWarReport',
                'STPGetPartyForeignReport',
            ):
                self.assertIn(f'[{report}]', values['STP_military_operations_desc'])
            self.assertIn(
                '[STPGetPartyPreparationReport]', values['STP_party_factions_desc']
            )
            self.assertNotIn(
                '[STPGetPartyHandoff]', values['STP_ps_preparation_report']
            )

    def test_layout_refresh_is_deferred_and_runs_on_loading_a_save(self):
        events = parse_clausewitz(read('events/ADISCORD_STP_events.txt'))
        refresh = [
            e.value
            for e in events
            if e.key == 'country_event'
            and one(e.value, 'id') == 'ADISCORD_STP_preparation.26'
        ]
        self.assertEqual(len(refresh), 1)
        self.assertEqual(
            signature(one(refresh[0], 'immediate')),
            [('mark_focus_tree_layout_dirty', 'yes')],
        )
        choice = next(
            e.value
            for e in events
            if e.key == 'country_event'
            and one(e.value, 'id') == 'ADISCORD_STP_preparation.1'
        )
        for option in children(choice, 'option'):
            calls = [
                e.value
                for e in walk(option)
                if e.key == 'country_event'
                and one(e.value, 'id') == 'ADISCORD_STP_preparation.26'
            ]
            self.assertEqual(len(calls), 1)
            self.assertEqual(one(calls[0], 'hours'), '1')
        hooks = one(
            parse_clausewitz(read('common/on_actions/02_ADISCORD_STP_on_actions.txt')),
            'on_actions',
        )
        startup = one(hooks, 'on_startup')
        self.assertIn('ADISCORD_STP_preparation.26', str(signature(startup)))
        self.assertIn('STP_ps_refresh_defence', str(signature(startup)))
        self.assertNotIn('set_variable', {e.key for e in walk(startup)})

    def test_supply_focus_advertises_all_three_actual_tools(self):
        trees = parse_clausewitz(
            read('common/national_focus/ADISCORD_national_focus_STP.txt')
        )
        focus = next(
            f.value
            for t in trees
            if t.key == 'focus_tree'
            for f in t.value
            if f.key == 'focus' and one(f.value, 'id') == 'STP_ps_foreign_supply_desk'
        )
        unlocks = {
            one(e.value, 'decision') if isinstance(e.value, list) else e.value
            for e in one(focus, 'completion_reward')
            if e.key == 'unlock_decision_tooltip'
        }
        self.assertEqual(
            unlocks,
            {'STP_ps_val_intelligence', 'STP_ps_val_intercept', 'STP_ps_val_pressure'},
        )


class FadaMissionContracts(unittest.TestCase):
    """Read actual mission gates and the loser-scoped settlement dispatcher."""

    @classmethod
    def setUpClass(cls):
        cls.triggers = {e.key: e.value for e in parse_clausewitz(read(TRIGGERS))}
        cls.effects = {e.key: e.value for e in parse_clausewitz(read(EFFECTS))}
        cls.missions = {
            d.key: d.value
            for c in parse_clausewitz(read(DECISIONS))
            for d in c.value
            if isinstance(d.value, list)
        }

    def expand(self, nodes):
        result = []
        for e in nodes:
            if e.key in {
                'STP_cw_fada_battle_active',
                'STP_cw_fada_captured',
                'STP_cw_party_government_defeated',
                'STP_ps_government_operational',
                'STP_ps_holds_congress',
                'STP_ps_war_active',
                'STP_ps_can_local_counterattack',
                'STP_ps_can_counterattack',
            }:
                self.assertIn(e.value, ('yes', 'no'))
                self.assertIn(e.key, self.triggers)
                body = Entry('AND', self.expand(self.triggers[e.key]), e.line)
                result.append(body if e.value == 'yes' else Entry('NOT', [body], e.line))
            else:
                result.append(
                    Entry(
                        e.key,
                        self.expand(e.value) if isinstance(e.value, list) else e.value,
                        e.line,
                        e.quoted,
                    )
                )
        return result

    def test_both_sides_get_long_automatic_high_priority_fada_missions(self):
        for tag, name in [('STS', 'STP_cw_take_fada'), ('STP', 'STP_cw_hold_fada')]:
            with self.subTest(tag=tag):
                self.assertIn(name, self.missions)
                mission = self.missions[name]
                self.assertEqual(one(one(mission, 'allowed'), 'tag'), tag)
                self.assertEqual(
                    one(one(mission, 'activation'), 'STP_cw_fada_battle_active'), 'yes'
                )
                self.assertGreaterEqual(int(one(mission, 'days_mission_timeout')), 365)
                self.assertGreaterEqual(int(one(mission, 'priority')), 100)
                self.assertEqual(one(mission, 'fire_only_once'), 'no')
                self.assertEqual(one(mission, 'selectable_mission'), 'no')
                self.assertNotIn('has_completed_focus', str(signature(mission)))
                self.assertEqual(
                    one(
                        one(
                            one(mission, 'highlight_states'), 'highlight_state_targets'
                        ),
                        'state',
                    ),
                    '28',
                )
                self.assertNotIn(
                    'annex_country', str(signature(one(mission, 'timeout_effect')))
                )
                self.assertNotIn(
                    'STP_cw_resolve_fada_capture',
                    str(signature(one(mission, 'timeout_effect'))),
                )

    def test_fada_outcome_requires_current_capture_and_a_live_civil_war(self):
        self.assertIn('STP_cw_fada_captured', self.triggers)
        gate = self.expand(self.triggers['STP_cw_fada_captured'])
        for tag, captured, at_war, finished, sts_exists in product(
            ('STP', 'STS'), (False, True), (False, True), (False, True), (False, True)
        ):
            facts = {
                (tag, 'has_global_flag', 'STP_cw_started'): True,
                (tag, 'has_global_flag', 'STP_cw_union_wars_finished'): finished,
                ('STP', 'exists', 'yes'): True,
                ('STS', 'exists', 'yes'): sts_exists,
                ('STP', 'has_war_with', 'STS'): at_war,
                ('STS', 'controls_province', '145'): captured,
            }
            actual = matches_conditions(gate, facts, tag)
            self.assertEqual(
                actual,
                captured and at_war and not finished and sts_exists,
                (tag, captured, at_war, finished, sts_exists),
            )

    def test_both_missions_call_the_same_rechecked_loser_scoped_dispatcher(self):
        for name in ('STP_cw_take_fada', 'STP_cw_hold_fada'):
            self.assertIn(name, self.missions)
            mission = self.missions[name]
            self.assertIn(
                'STP_cw_party_government_defeated',
                str(signature(one(mission, 'available'))),
            )
            self.assertIn(
                'STP_cw_resolve_fada_capture',
                str(signature(one(mission, 'complete_effect'))),
            )
        self.assertIn('STP_cw_resolve_fada_capture', self.effects)
        dispatch = self.effects['STP_cw_resolve_fada_capture']
        self.assertIn(
            'STP_cw_party_government_defeated',
            str(signature(one(one(dispatch, 'if'), 'limit'))),
        )
        receiver = one(one(dispatch, 'if'), 'STP')
        self.assertEqual(
            one(one(receiver, 'country_event'), 'id'), 'ADISCORD_STP_cw.205'
        )
        events = parse_clausewitz(read('events/ADISCORD_STP_events.txt'))
        handlers = [
            e.value
            for e in events
            if e.key == 'country_event' and one(e.value, 'id') == 'ADISCORD_STP_cw.205'
        ]
        self.assertEqual(len(handlers), 1)
        handler = handlers[0]
        self.assertEqual(one(handler, 'hidden'), 'yes')
        self.assertIn(
            'STP_cw_party_government_defeated',
            str(signature(one(handler, 'immediate'))),
        )
        winner = one(one(one(handler, 'immediate'), 'if'), 'STS')
        self.assertIn('STP_cw_resolve_last_banquet_success', str(signature(winner)))
        self.assertEqual(one(winner, 'STP_cw_settle_union_victory'), 'yes')

    def test_capture_alone_never_defeats_party_and_relocated_seat_is_required(self):
        gate = self.expand(self.triggers['STP_cw_party_government_defeated'])
        for tag, at_war, finished, congress, relocated, seat_held, expired in product(
            ('STP', 'STS'), *(6 * [(False, True)])
        ):
            facts = {
                (tag, 'has_global_flag', 'STP_cw_started'): True,
                (tag, 'has_global_flag', 'STP_cw_union_wars_finished'): finished,
                ('STP', 'exists', 'yes'): True,
                ('STS', 'exists', 'yes'): True,
                ('STP', 'has_war_with', 'STS'): at_war,
                ('STP', 'controls_province', '145'): congress,
                ('STP', 'has_country_flag', 'STP_ps_temporary_government'): relocated,
                ('STP', 'STP_ps_cabinet_site_held', 'yes'): seat_held,
                ('STP', 'has_country_flag', 'STP_ps_government_collapsed'): expired,
            }
            expected = (
                at_war and not finished and not congress
                and not (relocated and seat_held) and (expired or relocated)
            )
            self.assertEqual(matches_conditions(gate, facts, tag), expected, facts)

    def test_deadline_failure_enters_shared_settlement_but_live_government_survives(self):
        timeout = self.effects['STP_ps_congress_timeout']
        for active, government in product((False, True), repeat=2):
            payload = [entry for _, entry in selected_effects(timeout, {
                ('STP', 'STP_ps_war_active', 'yes'): active,
                ('STP', 'STP_ps_government_operational', 'no'): not government,
            })]
            events = [one(e.value, 'id') for e in payload if e.key == 'country_event']
            self.assertEqual(events, ['ADISCORD_STP_cw.205'] if active and not government else [])
        self.assertNotIn('STP_ps_district_concessions', str(signature(timeout)))

    def test_relocated_seat_cannot_be_replaced_and_is_owned_and_controlled(self):
        held = one(self.triggers['STP_ps_cabinet_site_held'], 'event_target:STP_ps_cabinet_seat')
        self.assertEqual(signature(held), [('is_owned_by', 'STP'), ('is_controlled_by', 'STP')])
        gate = self.triggers['STP_ps_can_relocate_government']
        for relocated, pending, held_district in product((False, True), repeat=3):
            facts = {
                ('STP', 'STP_ps_war_active', 'yes'): True,
                ('STP', 'STP_ps_government_operational', 'no'): True,
                ('STP', 'STP_ps_cabinet_site_available', 'yes'): held_district,
                ('STP', 'has_country_flag', 'STP_ps_temporary_government'): relocated,
                ('STP', 'has_variable', 'STP_ps_cabinet_deposit'): pending,
            }
            self.assertEqual(matches_conditions(gate, facts), held_district and not relocated and not pending)
        finish = self.effects['STP_ps_finish_cabinet']
        for held_district in (False, True):
            facts = {
                ('STP', 'STP_ps_war_active', 'yes'): True,
                ('STP', 'STP_ps_government_operational', 'no'): True,
                ('STP', 'STP_ps_cabinet_site_held', 'yes'): held_district,
                ('STP', 'has_variable', 'STP_ps_cabinet_deposit'): True,
            }
            payload = [entry for _, entry in selected_effects(finish, facts)]
            completed = [e.value for e in payload if e.key == 'set_country_flag']
            self.assertEqual('STP_ps_temporary_government' in completed, held_district)
            self.assertEqual('STP_ps_refund_cabinet' in [e.key for e in payload], not held_district)
        cleanup = str(signature(self.effects['STP_ps_close_defence']))
        self.assertIn("('clear_global_event_target', 'STP_ps_cabinet_seat')", cleanup)
        self.assertIn("('clear_variable', 'STP_ps_congress_days_left')", cleanup)

    def test_retake_pauses_deadline_without_resetting_elapsed_days(self):
        resolve = list(walk(self.effects['STP_ps_resolve_congress_crisis']))
        save = next(i for i, e in enumerate(resolve) if e.key == 'set_variable' and one(e.value, 'var') == 'STP_ps_congress_days_left')
        remove = next(i for i, e in enumerate(resolve) if e.key == 'remove_mission')
        self.assertLess(save, remove)
        self.assertEqual(one(resolve[save].value, 'value'), 'days_mission_timeout@STP_ps_congress_deadline')
        reopened = str(signature(self.effects['STP_ps_open_congress_crisis']))
        self.assertIn('STP_ps_congress_days_left', reopened)
        self.assertIn('add_days_mission_timeout', reopened)
        self.assertEqual(
            signature(one(self.missions['STP_ps_congress_deadline'], 'cancel_trigger')),
            [('STP_ps_war_active', 'no')],
        )
        tokens = read('common/synchronized_dynamic_tokens/ADISCORD_tokens.txt').split()
        self.assertEqual(tokens.count('STP_ps_congress_deadline'), 1)

    def test_initial_split_keeps_congress_even_for_limited_party_revolt(self):
        start = list(walk(self.effects['STP_cw_start']))
        self.assertNotIn('28', [e.value for e in start if e.key == 'transfer_state'])
        capitals = [one(e.value, 'state') for e in start if e.key == 'set_capital']
        self.assertIn('28', capitals)
        state = one(parse_clausewitz(read('history/states/28-Fada.txt')), 'state')
        self.assertIn('145', [e.value for e in one(state, 'provinces')])
        self.assertEqual(one(one(state, 'history'), 'owner'), 'STP')

    def test_all_cabinet_routes_fit_crisis_and_cancel_when_the_chosen_seat_is_lost(self):
        deadline = int(one(self.missions['STP_ps_congress_deadline'], 'days_mission_timeout'))
        base_days = int(one(self.missions['STP_ps_cabinet_work'], 'days_mission_timeout'))
        self.assertEqual(deadline, 21)
        for name, expected in (
            ('STP_ps_emergency_cabinet', 7),
            ('STP_ps_emergency_cabinet_administrative', 14),
            ('STP_ps_emergency_cabinet_prepared', 7),
        ):
            action = self.missions[name]
            deltas = [int(one(e.value, 'days')) for e in walk(action) if e.key == 'add_days_mission_timeout']
            self.assertEqual(base_days + sum(deltas), expected)
            self.assertLess(expected, deadline)
            complete = list(walk(one(action, 'complete_effect')))
            keys = [e.key for e in complete]
            self.assertLess(keys.index('STP_ps_select_cabinet_site'), keys.index('activate_mission'))
        cancel = str(signature(one(self.missions['STP_ps_cabinet_work'], 'cancel_trigger')))
        self.assertIn("('STP_ps_cabinet_site_held', 'no')", cancel)

    def test_limited_counterattacks_start_at_stage_two_full_offensive_at_four(self):
        ai = {e.key: e.value for e in parse_clausewitz(read('common/ai_strategy/ADISCORD_STP_civil_war.txt'))}
        for stage, government in product(range(1, 5), (False, True)):
            facts = {
                ('STP', 'has_war_with', 'STS'): True,
                ('STP', 'has_capitulated', 'no'): True,
                ('STP', 'controls_province', '145'): government,
                ('STP', 'variable', 'STP_ps_stage'): stage,
            }
            limited = matches_conditions(self.expand(one(ai['STP_ps_local_counterattacks'], 'enable')), facts)
            full = matches_conditions(self.expand(self.triggers['STP_ps_can_counterattack']), facts)
            self.assertEqual(limited, government and stage in (2, 3))
            self.assertEqual(full, government and stage == 4)
        local_policy = next(e.value for e in ai['STP_ps_local_counterattacks'] if e.key == 'ai_strategy' and one(e.value, 'type') == 'front_control')
        self.assertEqual(one(local_policy, 'execution_type'), 'careful')
        self.assertEqual(one(local_policy, 'execute_order'), 'yes')

    def test_union_cleanup_removes_both_fada_missions(self):
        cleanup = str(signature(self.effects['STP_cw_check_union_wars_finished']))
        for name in ('STP_cw_take_fada', 'STP_cw_hold_fada'):
            self.assertIn(name, cleanup)

    def test_fada_mission_text_exists_in_both_languages(self):
        for language in ('russian', 'english'):
            text = read(f'localisation/{language}/ADISCORD_STP_l_{language}.yml')
            for name in (
                'STP_cw_take_fada',
                'STP_cw_hold_fada',
                'STP_cw_fada_captured_tt',
                'STP_cw_fada_timeout_tt',
            ):
                self.assertRegex(text, rf'(?m)^ {name}:')


class CongressSiegeContracts(unittest.TestCase):
    """The first loss of province 145 is a seven-day siege, not an instant crisis."""

    @classmethod
    def setUpClass(cls):
        cls.effects = {e.key: e.value for e in parse_clausewitz(read(EFFECTS))}
        cls.triggers = {e.key: e.value for e in parse_clausewitz(read(TRIGGERS))}
        cls.decisions = {
            d.key: d.value
            for c in parse_clausewitz(read(DECISIONS))
            for d in c.value
            if isinstance(d.value, list)
        }
        cls.events = {
            one(e.value, 'id'): e.value
            for e in parse_clausewitz(read('events/ADISCORD_STP_events.txt'))
            if e.key == 'country_event'
        }

    @staticmethod
    def calls(effect, facts):
        return [(scope, e) for scope, e in selected_effects(effect, facts)]

    def test_daily_poll_routes_the_congress_through_the_siege(self):
        keys = [e.key for e in walk(self.effects['STP_ps_poll_nodes'])]
        self.assertIn('STP_ps_begin_congress_siege', keys)
        self.assertIn('STP_ps_lift_congress_siege', keys)
        self.assertNotIn('STP_ps_open_congress_crisis', keys)

    def test_only_a_congress_that_never_fell_gets_a_siege(self):
        effect = self.effects['STP_ps_begin_congress_siege']
        for fell, siege, crisis in product((False, True), repeat=3):
            facts = {
                ('STP', 'STP_ps_war_active', 'yes'): True,
                ('STP', 'STP_ps_holds_congress', 'no'): True,
                ('STP', 'has_country_flag', 'STP_ps_congress_fell'): fell,
                ('STP', 'has_country_flag', 'STP_ps_congress_siege'): siege,
                ('STP', 'has_country_flag', 'STP_ps_congress_crisis'): crisis,
            }
            calls = self.calls(effect, facts)
            keys = [e.key for _, e in calls]
            opens = not (fell or siege or crisis)
            self.assertEqual('activate_mission' in keys, opens)
            self.assertEqual('STP_ps_raise_fada_militia' in keys, opens)
            self.assertEqual(
                sorted(
                    scope for scope, e in calls
                    if e.key == 'country_event'
                    and one(e.value, 'id') == 'ADISCORD_STP_cw.230'
                ),
                ['STP', 'STS'] if opens else [],
            )
            self.assertEqual(
                'STP_ps_open_congress_crisis' in keys, not opens and not siege
            )

    def test_siege_mission_is_timeout_only_and_registered(self):
        mission = self.decisions['STP_ps_congress_siege']
        self.assertEqual(one(mission, 'days_mission_timeout'), '7')
        self.assertEqual(one(one(one(mission, 'available'), 'hidden_trigger'), 'always'), 'no')
        self.assertEqual(one(mission, 'selectable_mission'), 'no')
        self.assertIn(
            'STP_ps_congress_siege_timeout',
            str(signature(one(mission, 'timeout_effect'))),
        )
        tokens = read('common/synchronized_dynamic_tokens/ADISCORD_tokens.txt').split()
        self.assertEqual(tokens.count('STP_ps_congress_siege'), 1)

    def test_timeout_settles_by_current_control(self):
        effect = self.effects['STP_ps_congress_siege_timeout']
        for holds in (False, True):
            facts = {
                ('STP', 'has_country_flag', 'STP_ps_congress_siege'): True,
                ('STP', 'STP_ps_war_active', 'yes'): True,
                ('STP', 'STP_ps_holds_congress', 'no'): not holds,
                ('STP', 'STP_ps_holds_congress', 'yes'): holds,
            }
            calls = self.calls(effect, facts)
            keys = [e.key for _, e in calls]
            self.assertEqual('STP_ps_open_congress_crisis' in keys, not holds)
            self.assertEqual('STP_ps_lift_congress_siege' in keys, holds)
            fell = [
                scope for scope, e in calls
                if e.key == 'country_event' and one(e.value, 'id') == 'ADISCORD_STP_cw.232'
            ]
            self.assertEqual(sorted(fell), [] if holds else ['STP', 'STS'])
            if not holds:
                # The crisis reads government_operational, which the flag still satisfies.
                self.assertLess(
                    keys.index('clr_country_flag'), keys.index('STP_ps_open_congress_crisis')
                )

    def test_government_keeps_working_during_the_siege(self):
        gate = self.triggers['STP_ps_government_operational']
        facts = {('STP', 'has_country_flag', 'STP_ps_congress_siege'): True}
        self.assertTrue(matches_conditions(gate, facts))
        self.assertFalse(matches_conditions(gate, {}))

    def test_militia_pays_the_standard_price_once(self):
        effect = self.effects['STP_ps_raise_fada_militia']
        for raised, manpower, rifles in product(
            (False, True), (5999, 6000), (5399, 5400)
        ):
            facts = {
                ('STP', 'STP_ps_war_active', 'yes'): True,
                ('STP', 'owns_state', '28'): True,
                ('STP', 'has_country_flag', 'STP_ps_fada_militia_raised'): raised,
                ('STP', 'controls_province', '16374'): True,
                ('STP', 'numeric', 'has_manpower'): manpower,
                ('STP', 'equipment', 'infantry_equipment'): rifles,
                ('STP', 'has_country_flag', 'STP_cw_rifles_paid'): True,
            }
            keys = [e.key for _, e in self.calls(effect, facts)]
            paid = not raised and manpower >= 6000 and rifles >= 5400
            self.assertEqual(keys.count('STP_cw_pay_rifles'), 3 if paid else 0)
            self.assertEqual(keys.count('STP_ps_create_fada_militia'), 3 if paid else 0)
            self.assertEqual(keys.count('set_country_flag'), 0 if raised else 1)
        payment = [
            e for e in walk(effect)
            if e.key == 'add_manpower' or (e.key == 'set_temp_variable' and one(e.value, 'var') == 'STP_cw_rifle_cost')
        ]
        self.assertEqual(
            [e.value if e.key == 'add_manpower' else one(e.value, 'value') for e in payment],
            ['5400', '-6000'],
        )
        create = self.effects['STP_ps_create_fada_militia']
        locations = {
            one(parse_clausewitz(one(e.value, 'division')), 'location')
            for e in walk(create) if e.key == 'create_unit'
        }
        self.assertEqual(locations, {'16374', '16386', '16377', '16366', '16351', '16368'})

    def test_war_end_clears_siege_and_capital_defence(self):
        cleanup = str(signature(self.effects['STP_ps_close_defence']))
        for entry in (
            "('clr_country_flag', 'STP_ps_congress_siege')",
            "('remove_mission', 'STP_ps_congress_siege')",
            "('clr_country_flag', 'STP_ps_fada_militia_raised')",
            "('clear_variable', 'STP_ps_capital_defence')",
        ):
            self.assertIn(entry, cleanup)
        self.assertIn('STP_ps_capital_defence_dynamic', cleanup)

    def test_capital_defence_follows_stage_and_siege(self):
        effect = self.effects['STP_ps_refresh_capital_defence']
        for holds, siege, stage in product((False, True), (False, True), (1, 2, 3, 4)):
            facts = {
                ('STP', 'STP_ps_war_active', 'yes'): True,
                ('STP', 'STP_ps_holds_congress', 'yes'): holds,
                ('STP', 'has_country_flag', 'STP_ps_congress_siege'): siege,
                ('STP', 'variable', 'STP_ps_stage'): stage,
            }
            values = [
                float(one(e.value, 'value'))
                for _, e in self.calls(effect, facts)
                if e.key == 'set_variable' and one(e.value, 'var') == 'STP_ps_capital_defence'
            ]
            expected = 0.2 if siege else (0.1 if holds and stage < 3 else 0)
            self.assertEqual(values[-1], expected)
        dynamic = one(
            parse_clausewitz(read('common/dynamic_modifiers/ADISCORD_dynamic_modifiers_STP.txt')),
            'STP_ps_capital_defence_dynamic',
        )
        self.assertEqual(one(dynamic, 'army_defence_factor'), 'STP_ps_capital_defence')

    def test_capital_slots_place_only_the_party_start_divisions(self):
        deploy = self.effects['STP_cw_deploy_assault_division']
        gate = signature(one(one(deploy, 'if'), 'limit'))
        self.assertIn(('tag', 'STP'), gate)
        self.assertIn('STP_cw_capital_assault_slots', str(gate))
        start = one(self.effects['STP_cw_start'], 'if')
        keys = [e.key for e in start]
        slots = [
            i for i, e in enumerate(start)
            if e.key == 'set_temp_variable' and one(e.value, 'var') == 'STP_cw_capital_assault_slots'
        ]
        self.assertEqual(len(slots), 1)
        self.assertEqual(one(start[slots[0]].value, 'value'), '3')
        self.assertLess(keys.index('STP_cw_raise_congress_guard'), slots[0])
        self.assertNotIn('STP_cw_capital_assault_slots', str(signature(start[:slots[0]])))

    def test_siege_events_reach_both_sides(self):
        for number in (230, 231, 232):
            event = self.events[f'ADISCORD_STP_cw.{number}']
            self.assertEqual(signature(one(event, 'trigger')), [('OR', [('tag', 'STP'), ('tag', 'STS')])])
            options = children(event, 'option')
            self.assertEqual(len(options), 2)
            for language in ('russian', 'english'):
                text = read(f'localisation/{language}/ADISCORD_STP_l_{language}.yml')
                for suffix in ('t', 'd_party', 'd_resistance', 'a', 'b'):
                    self.assertRegex(
                        text, rf'(?m)^ ADISCORD_STP_cw\.{number}\.{suffix}: "[^"\r\n]+"\r?$'
                    )
        registry = read('tools/data/adiscord_event_ids.json')
        for number in (230, 231, 232):
            self.assertIn(f'"ADISCORD_STP_cw.{number}"', registry)

    def test_party_ai_holds_the_fada_front(self):
        ai = {
            e.key: e.value
            for e in parse_clausewitz(read('common/ai_strategy/ADISCORD_STP_civil_war.txt'))
        }
        profile = ai['STP_cw_hold_fada_front']
        control = next(
            e.value for e in profile
            if e.key == 'ai_strategy' and one(e.value, 'type') == 'front_control'
        )
        self.assertEqual(signature(one(control, 'state_trigger')), [('state', '28'), ('FROM', [('tag', 'STS')])])
        self.assertEqual(one(control, 'execute_order'), 'yes')
        self.assertEqual(one(control, 'execution_type'), 'careful')
        self.assertTrue(1500 < int(one(control, 'priority')) < 1600)
        defend = str(signature(one(ai['STP_cw_defend_fada'], 'enable')))
        self.assertIn('STP_ps_congress_siege', defend)


class PartyAssaultEquipmentContracts(unittest.TestCase):
    """The party's assault core keeps first claim on its non-rifle package."""

    TYPES = {
        '1': ('ADISCORD_squad_weapons_equipment', 'STP_cw_payment_ADISCORD_squad_weapons_equipment'),
        '2': ('support_equipment', 'STP_cw_payment_support_equipment'),
        '3': ('artillery_equipment', 'STP_cw_payment_artillery_equipment'),
        '4': ('anti_air_equipment', 'STP_cw_payment_anti_air_equipment'),
    }

    @classmethod
    def setUpClass(cls):
        cls.effects = {e.key: e.value for e in parse_clausewitz(read(EFFECTS))}

    def test_top_up_runs_after_transfers_and_before_party_payments(self):
        start = one(self.effects['STP_cw_start'], 'if')
        keys = [e.key for e in start]
        secure = keys.index('STP_cw_secure_party_assault_equipment')
        self.assertEqual(keys.count('STP_cw_secure_party_assault_equipment'), 1)
        self.assertLess(keys.index('STP_cw_divide_air_reserves'), secure)
        self.assertLess(secure, keys.index('load_oob'))
        first_payment = min(
            i for i, e in enumerate(start)
            if 'STP_cw_mobilize_assault_division' in str(signature([e]))
        )
        self.assertLess(secure, first_payment)

    def test_package_matches_the_assault_payment(self):
        payment = {
            one(e.value, 'var'): one(e.value, 'value')
            for e in walk(self.effects['STP_cw_pay_assault_division'])
            if e.key == 'set_temp_variable'
        }
        helper = self.effects['STP_cw_secure_core_equipment_type']
        needs = {'1': one(helper[0].value, 'value')}
        holdings = {'1': one(helper[1].value, 'value')}
        for branch in (e.value for e in helper if e.key == 'if'):
            limit = signature(one(branch, 'limit'))
            if 'STP_cw_core_equipment_type' not in str(limit):
                continue
            number = one(one(one(branch, 'limit'), 'check_variable'), 'value')
            values = {one(e.value, 'var'): one(e.value, 'value') for e in branch if e.key == 'set_temp_variable'}
            needs[number] = values['STP_cw_core_shortfall']
            holdings[number] = values['STP_cw_core_holding']
        for number, (archetype, payment_var) in self.TYPES.items():
            self.assertEqual(needs[number], payment[payment_var], archetype)
            self.assertEqual(holdings[number], f'num_equipment@{archetype}')
        secure = self.effects['STP_cw_secure_party_assault_equipment']
        types = [
            one(e.value, 'value') for e in secure
            if e.key == 'set_temp_variable' and one(e.value, 'var') == 'STP_cw_core_equipment_type'
        ]
        self.assertEqual(types, ['1', '2', '3', '4'])
        counts = [
            one(e.value, 'value') for e in walk(secure)
            if e.key == 'set_temp_variable' and one(e.value, 'var') == 'STP_cw_core_assault_divisions'
        ]
        self.assertEqual(counts, ['6', '3'])

    def test_donors_send_only_the_capped_shortfall_to_the_party(self):
        donor = self.effects['STP_cw_return_core_equipment']
        sends = [e.value for e in walk(donor) if e.key == 'send_equipment']
        self.assertEqual(
            sorted(one(s, 'type') for s in sends),
            sorted(archetype for archetype, _ in self.TYPES.values()),
        )
        for send in sends:
            self.assertEqual(one(send, 'target'), 'STP')
            self.assertEqual(one(send, 'amount'), 'STP_cw_core_transfer')
        cap = next(
            e.value for e in donor
            if e.key == 'if' and 'STP_cw_core_shortfall' in str(signature(one(e.value, 'limit')))
        )
        capped = one(cap, 'set_temp_variable')
        self.assertEqual(one(capped, 'var'), 'STP_cw_core_transfer')
        self.assertEqual(one(capped, 'value'), 'STP_cw_core_shortfall')
        keys = [e.key for e in donor]
        # Rounding happens after the cap and before the send.
        self.assertLess(keys.index('round_temp_variable'), len(keys) - 1)
        helper = self.effects['STP_cw_secure_core_equipment_type']
        donors = [
            child.key
            for branch in helper if branch.key == 'if'
            for child in branch.value if child.key in ('STS', 'SRP')
        ]
        self.assertEqual(donors, ['STS', 'SRP'])
