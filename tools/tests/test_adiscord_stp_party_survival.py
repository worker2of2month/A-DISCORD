"""Contracts for party recovery, scarce resources and exile settlement.

AST checks cover authored ordering and reachability, not native execution.
"""
import unittest
from itertools import product
from pathlib import Path
import re

from tools.tests.test_adiscord_stp_party_route import read, children, one, walk, signature
from tools.tests.test_adiscord_stp_preparation import matches_conditions, selected_effects
from tools.validators.validate_adiscord_division_templates import Entry, parse_clausewitz

EFFECTS = 'common/scripted_effects/ADISCORD_STP_scripted_effects.txt'
DECISIONS = 'common/decisions/ADISCORD_STP_decisions.txt'
TRIGGERS = 'common/scripted_triggers/ADISCORD_STP_scripted_triggers.txt'


def expand_survival_gates(items):
    """Expand only the new gates; pre-existing predicates are explicit scenario facts."""
    definitions = {e.key: e.value for e in parse_clausewitz(read(TRIGGERS))}
    names = {'STP_ps_nod_order_current', 'STP_ps_can_launch_return'}

    def expand(nodes):
        expanded = []
        for entry in nodes:
            if entry.key in names:
                if entry.value not in ('yes', 'no'):
                    raise AssertionError('Scripted triggers require boolean calls')
                body = expand(definitions[entry.key])
                expanded.append(Entry('AND' if entry.value == 'yes' else 'NOT', body, entry.line))
            else:
                value = expand(entry.value) if isinstance(entry.value, list) else entry.value
                expanded.append(Entry(entry.key, value, entry.line, entry.quoted))
        return expanded

    return expand(items)


class PartySurvivalContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.effects = {e.key: e.value for e in parse_clausewitz(read(EFFECTS))}
        cls.decisions = {d.key: d.value for c in parse_clausewitz(read(DECISIONS))
                         for d in c.value if isinstance(d.value, list)}

    def test_exile_precedes_peace_and_annexation(self):
        body = list(walk(self.effects['STP_cw_settle_union_victory']))
        positions = lambda key: [i for i, e in enumerate(body) if e.key == key]
        self.assertEqual(len(positions('STP_ps_prepare_exile')), 1)
        self.assertLess(positions('STP_ps_prepare_exile')[0], positions('white_peace')[0])
        self.assertLess(positions('STP_ps_prepare_exile')[0], positions('annex_country')[0])

    def test_recovery_missions_cannot_succeed_on_activation(self):
        for stage in (1, 2, 3):
            mission = self.decisions[f'STP_ps_reorg_{stage}']
            available = one(mission, 'available')
            self.assertEqual(one(one(available, 'hidden_trigger'), 'always'), 'no')
            self.assertEqual(one(mission, 'fire_only_once'), 'no')
            self.assertIn('STP_ps_finish_stage', str(signature(one(mission, 'timeout_effect'))))

    def test_every_stage_has_a_free_escape_from_insolvency(self):
        for stage in (1, 2, 3):
            action = self.decisions[f'STP_ps_reorg_{stage}_administrative']
            self.assertEqual(one(action, 'cost'), '0')
            self.assertNotIn('ADISCORD_economy_treasury', str(signature(action)))

    def test_pause_saves_time_before_removing_mission(self):
        body = list(walk(self.effects['STP_ps_pause_reorganisation']))
        saves = [i for i, e in enumerate(body) if e.key == 'set_variable'
                 and one(e.value, 'var') == 'STP_ps_paused_days']
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
        base = [int(one(self.decisions[f'STP_ps_reorg_{s}'], 'days_mission_timeout')) for s in (1, 2, 3)]
        self.assertEqual(base, [21, 21, 28])
        for radio, hq, *free in product((False, True), repeat=5):
            expected = 70 - 7 * (radio + hq) + 14 * sum(free)
            actual = sum(base)
            for stage in (1, 2, 3):
                decision = self.decisions[f'STP_ps_reorg_{stage}_' + ('administrative' if free[stage-1] else 'funded')]
                changes = [e.value for e in walk(decision) if e.key == 'add_days_mission_timeout']
                self.assertEqual([one(c, 'days') for c in changes],
                                 (['-7'] if stage < 3 else []) + (['14'] if free[stage-1] else []))
                actual += 14 * free[stage-1]
                if stage < 3:
                    actual -= 7 * (radio if stage == 1 else hq)
            self.assertEqual(actual, expected)
            self.assertGreaterEqual(actual, 56)

    def test_credit_affordability_includes_fractional_boundary(self):
        gate = one(self.decisions['STP_ps_fund_nod'], 'custom_cost_trigger')
        for money, expected in ((1499.9, False), (1500, True), (1500.1, True)):
            self.assertEqual(matches_conditions(gate, {('STP', 'variable', 'ADISCORD_economy_treasury'): money}), expected)

    def test_receipts_are_cleared_before_delivery_or_refund(self):
        for name, clear, reward in (
            ('STP_ps_deliver_nod', 'STP_ps_clear_nod_receipt', 'add_equipment_to_stockpile'),
            ('STP_ps_refund_nod', 'STP_ps_clear_nod_receipt', 'add_to_variable'),
            ('STP_ps_resolve_val_supply', 'STP_ps_clear_val_receipt', 'add_equipment_to_stockpile'),
            ('STP_ps_refund_val_supply', 'STP_ps_clear_val_receipt', 'add_equipment_to_stockpile'),
        ):
            keys = [e.key for e in walk(self.effects[name])]
            self.assertLess(keys.index(clear), keys.index(reward), name)

    def test_government_deadline_reads_current_control(self):
        triggers = {e.key: e.value for e in parse_clausewitz(read('common/scripted_triggers/ADISCORD_STP_scripted_triggers.txt'))}
        congress = triggers['STP_ps_holds_congress']
        self.assertEqual(signature(congress), [('controls_province', '145')])
        for owned in (False, True):
            for controlled in (False, True):
                self.assertEqual(matches_conditions(congress, {
                    ('STP', 'controls_state', '28'): owned,
                    ('STP', 'controls_province', '145'): controlled,
                }), controlled)
        self.assertIn('STP_ps_government_operational', str(signature(self.effects['STP_ps_finish_stage'])))
        self.assertIn('STP_ps_government_operational', str(signature(self.effects['STP_ps_congress_timeout'])))

    def test_congress_historical_penalty_cannot_repeat(self):
        first = next(e.value for e in walk(self.effects['STP_ps_open_congress_crisis'])
                     if e.key == 'if' and 'STP_ps_congress_fell' in str(signature(one(e.value, 'limit'))))
        self.assertEqual(one(first, 'add_stability'), '-0.15')
        self.assertEqual(one(first, 'add_war_support'), '-0.10')
        self.assertIn(('NOT', [('has_country_flag', 'STP_ps_congress_fell')]), signature(one(first, 'limit')))

    def test_asylum_is_not_blocked_by_a_northern_defeat_or_human_host(self):
        triggers = {e.key: e.value for e in parse_clausewitz(read('common/scripted_triggers/ADISCORD_STP_scripted_triggers.txt'))}
        host = triggers['STP_ps_nod_can_host_exiles']
        for status, ai in product(range(5), (False, True)):
            facts = {('NOD', 'tag', 'NOD'): True, ('NOD', 'exists', 'yes'): True,
                     ('NOD', 'has_capitulated', 'no'): True, ('NOD', 'is_subject', 'no'): True,
                     ('NOD', 'variable', 'STP_cw_northern_campaign_status'): status,
                     ('NOD', 'is_ai', 'yes'): ai}
            self.assertTrue(matches_conditions(host, facts, 'NOD'))
        handoff = str(signature(self.effects['STP_ps_exile_handoff']))
        self.assertIn("('NOD', [('is_ai', 'yes')", handoff)
        self.assertIn('STP_ps_decline_handoff', handoff)

    def test_no_paid_program_marks_a_military_victory(self):
        for name, effect in self.effects.items():
            if name.startswith('STP_ps_') and name.endswith('_finish'):
                self.assertNotIn('STP_cw_won_union_battle', str(signature(effect)), name)
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
        self.assertIn('STP_ps_val_route_wait', str(signature(self.effects['STP_ps_dispatch_val_supply'])))

    def test_new_foci_resolve_and_exile_is_attached_without_tree_replacement(self):
        trees = parse_clausewitz(read('common/national_focus/ADISCORD_national_focus_STP.txt'))
        focuses = {one(e.value, 'id'): e.value for e in walk(trees)
                   if e.key in ('focus', 'shared_focus') and isinstance(e.value, list)}
        new = {key for key in focuses if key.startswith('STP_ps_')}
        self.assertEqual(len(new), 28)
        for key in new:
            for block in children(focuses[key], 'prerequisite'):
                for entry in block:
                    self.assertIn(entry.value, focuses)
        shared = [e.value for e in trees if e.key == 'shared_focus']
        self.assertEqual(len(shared), 6)
        for f in shared:
            self.assertIn(('tag', 'NOD'), signature(one(f, 'allow_branch')))
            self.assertIn(('has_country_flag', 'STP_ps_exile_received'), signature(one(f, 'allow_branch')))
        self.assertNotIn('load_focus_tree', {e.key for e in walk(self.effects['STP_ps_accept_exile'])})

    def test_return_requires_real_capitulation_and_only_transfers_stp_cores(self):
        effect = self.effects['STP_ps_settle_return']
        self.assertIn('has_capitulated', str(signature(one(one(effect, 'if'), 'limit'))))
        states = next(e.value for e in walk(effect) if e.key == 'every_owned_state' and any(c.key == 'limit' for c in e.value))
        self.assertEqual(signature(one(states, 'limit')), [('is_core_of', 'STP')])
        self.assertNotIn('annex_country', {e.key for e in walk(effect)})

    def test_second_opposition_slot_never_clears_the_first(self):
        effect = self.effects['STP_cw_prepare_opposition_second']
        self.assertNotIn(('clr_state_flag', 'STP_cw_opposition_target'), [(e.key, e.value) for e in walk(effect) if isinstance(e.value, str)])
        gate = one(one(self.effects['STP_cw_schedule_opposition_second'], 'if'), 'limit')
        self.assertIn('days_mission_timeout@STP_cw_election_window', str(signature(gate)))
        self.assertIn('56', str(signature(gate)))

    def test_node_polling_is_bounded_to_five_points(self):
        effect = self.effects['STP_ps_poll_nodes']
        nodes = {e.value for e in walk(effect) if e.key == 'controls_province'}
        self.assertEqual(nodes, {'145', '16366', '45', '16345', '16445'})
        self.assertFalse({'every_country', 'every_possible_country'} & {e.key for e in walk(effect)})

    def test_local_towns_gate_only_their_party_owned_state(self):
        trigger = next(e.value for e in parse_clausewitz(read(TRIGGERS)) if e.key == 'STP_ps_local_program_open')
        for state, town in ((2, 16445), (29, 16345), (3, 45)):
            for owner, control in product(('STP', 'STS'), (False, True)):
                facts = {(str(state), 'is_owned_by', 'STP'): owner == 'STP',
                         ('FROM', 'state', str(state)): True,
                         ('STP', 'controls_province', str(town)): control}
                self.assertEqual(matches_conditions(trigger, facts, str(state)),
                                 owner != 'STP' or state == 3 or control)

    def test_restored_party_reconstruction_does_not_fabricate_a_civil_war_win(self):
        trigger = next(e.value for e in parse_clausewitz(read(TRIGGERS)) if e.key == 'STP_pw_can_reconstruct')
        facts = {('STP', 'has_capitulated', 'no'): True,
                 ('STP', 'has_country_flag', 'STP_cw_postwar'): True,
                 ('STP', 'has_global_flag', 'STP_cw_union_wars_finished'): True,
                 ('STP', 'has_country_flag', 'STP_ps_restored_dependency'): True,
                 ('STP', 'is_subject_of', 'NOD'): True}
        self.assertTrue(matches_conditions(trigger, facts, 'STP'))
        self.assertFalse(matches_conditions(trigger, {**facts, ('STP', 'is_subject_of', 'NOD'): False}, 'STP'))
        self.assertNotIn('STP_cw_won_union_battle', str(signature(self.effects['STP_ps_settle_return'])))

    def test_exile_orders_close_before_missions_and_cannot_outlive_the_route(self):
        close = self.effects['STP_ps_close_exile']
        keys = [e.key for e in close]
        self.assertLess(keys.index('STP_ps_exile_formation_refund'), keys.index('remove_mission'))
        self.assertIn(('clr_country_flag', 'STP_ps_exile_received'), signature(close))
        self.assertIn('STP_ps_close_exile', str(signature(self.effects['STP_ps_settle_return'])))
        brigade = self.decisions['STP_ps_exile_formation']
        for gate in (one(brigade, 'custom_cost_trigger'), one(one(one(brigade, 'complete_effect'), 'hidden_effect')[0].value, 'limit')):
            text = str(signature(gate))
            self.assertIn('6000', text)
            self.assertIn('600', text)

    def test_preparation_uses_existing_election_category_without_extra_tabs(self):
        categories = {e.key: e.value for e in parse_clausewitz(read(DECISIONS))}
        definitions = {e.key for e in parse_clausewitz(read('common/decisions/categories/ADISCORD_decision_categories_STP.txt'))}
        for old in ('STP_ps_party_programs', 'STP_ps_northern_support', 'STP_ps_supply_routes'):
            self.assertNotIn(old, categories)
            self.assertNotIn(old, definitions)
        elections = {e.key for e in categories['STP_elections_in_the_party']}
        self.assertTrue({'STP_ps_build_radio', 'STP_ps_build_hq', 'STP_ps_prepare_evacuation',
                         'STP_ps_fund_nod', 'STP_ps_arm_nod', 'STP_ps_val_intelligence', 'STP_ps_val_intercept'} <= elections)
        council = {e.key for e in categories['STP_cw_war_council']}
        self.assertTrue({'STP_ps_reorg_1_funded', 'STP_ps_ammunition', 'STP_ps_transport'} <= council)

    def test_new_localisation_preserves_native_encoding_and_single_line_values(self):
        root = Path(__file__).resolve().parents[2]
        raw = (root / 'localisation/russian/ADISCORD_STP_l_russian.yml').read_bytes()
        self.assertTrue(raw.startswith(b'\xef\xbb\xbf'))
        keys = []
        for line in raw.decode('utf-8-sig').splitlines():
            if line.lstrip().startswith('STP_ps_'):
                self.assertRegex(line, r'^ STP_ps_\w+: ".*"$')
                keys.append(line.split(':', 1)[0])
        self.assertEqual(len(keys), len(set(keys)))
        for path in (EFFECTS, DECISIONS):
            self.assertFalse((root / path).read_bytes().startswith(b'\xef\xbb\xbf'))


    def test_nod_predeparture_refunds_a_stale_purpose_without_shipping(self):
        # A still-friendly host is not enough once the northern war or intervention ends.
        dispatcher = expand_survival_gates(self.effects['STP_ps_dispatch_nod'])
        for kind, north, possible, entered, war, route, host in product(
                range(1, 5), (False, True), (False, True), (False, True),
                (False, True), (False, True), (False, True)):
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
            current = host and (kind == 1 or kind in (2, 3) and north or
                                kind == 4 and (possible or entered and war))
            effects = list(selected_effects(dispatcher, facts))
            calls = [(scope, e.key, e.value) for scope, e in effects if e.key in
                     {'activate_mission', 'STP_ps_refund_nod'}]
            expected = ('activate_mission', 'STP_ps_nod_delivery' if route else 'STP_ps_nod_route_wait') if current else ('STP_ps_refund_nod', 'yes')
            self.assertEqual(calls, [('STP', *expected)],
                             (kind, north, possible, entered, war, route, host))

    def test_nod_wait_and_dispatch_cancel_on_the_same_current_purpose(self):
        definitions = {e.key: e.value for e in parse_clausewitz(read(TRIGGERS))}
        self.assertIn('STP_ps_nod_order_current', set(definitions))
        for name in ('STP_ps_nod_dispatch', 'STP_ps_nod_route_wait'):
            gate = one(self.decisions[name], 'cancel_trigger')
            self.assertEqual(signature(gate), [('STP_ps_nod_order_current', 'no')])
        # Revocation before departure returns the original deposit, never a fixed new price.
        refund = list(walk(self.effects['STP_ps_refund_nod']))
        save = next(e.value for e in refund if e.key == 'set_temp_variable' and one(e.value, 'var') == 'STP_ps_refund')
        self.assertEqual(one(save, 'value'), 'STP_ps_nod_receipt_money')

    def test_return_requires_training_and_a_live_nonallied_target(self):
        definitions = {e.key: e.value for e in parse_clausewitz(read(TRIGGERS))}
        self.assertIn('STP_ps_can_launch_return', set(definitions))
        gate = definitions['STP_ps_can_launch_return']
        for training, alive, allied, own_subject, active, closed, war in product((False, True), repeat=7):
            facts = {
                ('NOD', 'STP_ps_nod_can_host_exiles', 'yes'): True,
                ('NOD', 'has_country_flag', 'STP_ps_exile_received'): True,
                ('NOD', 'has_completed_focus', 'STP_ps_return_campaign_focus'): True,
                ('NOD', 'has_country_flag', 'STP_ps_return_terms_accepted'): True,
                ('NOD', 'has_country_flag', 'STP_ps_exile_training_completed'): training,
                ('NOD', 'has_country_flag', 'STP_ps_return_campaign'): active,
                ('NOD', 'has_country_flag', 'STP_ps_return_closed'): closed,
                ('NOD', 'has_war_with', 'STS'): war,
                ('NOD', 'is_in_faction_with', 'STS'): allied,
                ('STP', 'exists', 'no'): True,
                ('STS', 'exists', 'yes'): True,
                ('STS', 'has_capitulated', 'no'): alive,
                ('STS', 'is_subject_of', 'NOD'): own_subject,
            }
            self.assertEqual(matches_conditions(gate, facts, 'NOD'),
                             training and alive and not (allied or own_subject or active or closed))

    def test_return_declaration_and_ui_share_the_same_gate(self):
        gate = one(one(self.effects['STP_ps_begin_return'], 'if'), 'limit')
        self.assertEqual(signature(gate), [('STP_ps_can_launch_return', 'yes')])
        ui = one(one(self.decisions['STP_ps_launch_return'], 'available'), 'custom_trigger_tooltip')
        self.assertIn(('STP_ps_can_launch_return', 'yes'), signature(ui))
        # A failed native declaration may not leave a campaign marked as running.
        branches = children(one(self.effects['STP_ps_begin_return'], 'if'), 'if')
        receipt = next((b for b in branches if any(e.key == 'set_country_flag' and e.value == 'STP_ps_return_campaign' for e in b)), None)
        self.assertIsNotNone(receipt)
        self.assertEqual(signature(one(receipt, 'limit')), [('has_war_with', 'STS')])
        for war in (False, True):
            facts = {('NOD', 'STP_ps_can_launch_return', 'yes'): True,
                     ('NOD', 'has_war_with', 'STS'): war}
            payload = list(selected_effects(self.effects['STP_ps_begin_return'], facts, 'NOD'))
            self.assertEqual(sum(e.key == 'declare_war_on' for _, e in payload), int(not war))

    def test_arrested_hedersett_cannot_escape_or_be_restored(self):
        definitions = {e.key: e.value for e in parse_clausewitz(read(TRIGGERS))}
        self.assertIn('STP_ps_hedersett_available', set(definitions))
        gate = definitions['STP_ps_hedersett_available']
        self.assertEqual(one(gate, 'has_character'), 'STP_rufus_hedersett')
        character_gate = one(gate, 'STP_rufus_hedersett')
        for arrested in (False, True):
            facts = {('STP_rufus_hedersett', 'has_character_flag', 'STP_cw_arrested'): arrested}
            self.assertEqual(matches_conditions(character_gate, facts, 'STP_rufus_hedersett'), not arrested)
        for name in ('STP_ps_accept_exile', 'STP_ps_settle_return'):
            guarded = [e.value for e in walk(self.effects[name]) if e.key == 'if'
                       and any(c.key == 'set_nationality' for c in e.value)]
            self.assertEqual(len(guarded), 1, name)
            self.assertIn(('STP_ps_hedersett_available', 'yes'), signature(one(guarded[0], 'limit')))


if __name__ == '__main__':
    unittest.main()
