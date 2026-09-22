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

    def test_partner_aid_is_not_blocked_by_a_northern_defeat_or_human_recipient(self):
        triggers = {e.key: e.value for e in parse_clausewitz(read('common/scripted_triggers/ADISCORD_STP_scripted_triggers.txt'))}
        host = triggers['STP_ps_nod_partner_available']
        for status, ai in product(range(5), (False, True)):
            facts = {('NOD', 'tag', 'NOD'): True, ('NOD', 'exists', 'yes'): True,
                     ('NOD', 'has_capitulated', 'no'): True, ('NOD', 'is_subject', 'no'): True,
                     ('NOD', 'variable', 'STP_cw_northern_campaign_status'): status,
                     ('NOD', 'is_ai', 'yes'): ai}
            self.assertTrue(matches_conditions(host, facts, 'NOD'))
        self.assertNotIn("STP_ps_exile_handoff", self.effects)
        self.assertNotIn("STP_ps_handoff_accept", self.decisions)
        self.assertNotIn("NOD = { change_tag_from = STP }", read(EFFECTS))

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

    def test_domestic_foci_resolve_without_attaching_an_exile_tree(self):
        trees = parse_clausewitz(read('common/national_focus/ADISCORD_national_focus_STP.txt'))
        focuses = {one(e.value, 'id'): e.value for e in walk(trees)
                   if e.key in ('focus', 'shared_focus') and isinstance(e.value, list)}
        new = {key for key in focuses if key.startswith('STP_ps_')}
        self.assertEqual(len(new), 22)
        for key in new:
            for block in children(focuses[key], 'prerequisite'):
                for entry in block:
                    self.assertIn(entry.value, focuses)
        self.assertFalse([e for e in trees if e.key == 'shared_focus'])
        self.assertNotIn('load_focus_tree', {e.key for e in walk(self.effects['STP_ps_close_exile'])})

    def test_retired_return_cannot_transfer_territory_or_create_a_country(self):
        self.assertNotIn('STP_ps_settle_return', self.effects)
        self.assertNotIn('STP_ps_begin_return', self.effects)
        keys = {e.key for e in walk(self.effects['STP_ps_close_exile'])}
        self.assertFalse({'annex_country', 'transfer_state', 'set_autonomy', 'declare_war_on',
                          'create_dynamic_country', 'change_tag_from'} & keys)

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
        self.assertNotIn('STP_ps_settle_return', self.effects)

    def test_legacy_orders_refund_before_mission_cleanup_and_cannot_restart(self):
        close = self.effects['STP_ps_close_exile']
        keys = [e.key for e in close]
        self.assertLess(keys.index('STP_ps_exile_formation_refund'), keys.index('remove_mission'))
        self.assertLess(keys.index('STP_ps_exile_training_refund'), keys.index('remove_mission'))
        self.assertIn(('clr_country_flag', 'STP_ps_exile_received'), signature(close))
        for program in ('STP_ps_exile_training', 'STP_ps_exile_formation'):
            self.assertNotIn(program, self.decisions)
            mission = self.decisions[program + '_work']
            self.assertEqual(signature(one(mission, 'activation')), [('always', 'no')])
            self.assertEqual(signature(one(mission, 'visible')), [('always', 'no')])
            self.assertEqual(signature(one(mission, 'cancel_trigger')), [('always', 'yes')])
            for phase in ('cancel_effect', 'timeout_effect'):
                self.assertIn(program + '_refund', str(signature(one(mission, phase))))

    def test_preparation_reuses_existing_categories_without_extra_tabs(self):
        categories = {e.key: e.value for e in parse_clausewitz(read(DECISIONS))}
        definitions = {e.key for e in parse_clausewitz(read('common/decisions/categories/ADISCORD_decision_categories_STP.txt'))}
        for old in ('STP_ps_party_programs', 'STP_ps_northern_support', 'STP_ps_supply_routes'):
            self.assertNotIn(old, categories)
            self.assertNotIn(old, definitions)
        elections = {e.key for e in categories['STP_elections_in_the_party']}
        domestic = {'STP_ps_build_radio', 'STP_ps_build_hq', 'STP_ps_prepare_evacuation'}
        foreign = {'STP_ps_fund_nod', 'STP_ps_arm_nod', 'STP_ps_val_intelligence', 'STP_ps_val_intercept'}
        self.assertTrue(domestic <= {e.key for e in categories['STP_party_factions']})
        self.assertTrue(foreign <= {e.key for e in categories['STP_cw_external_intervention']})
        self.assertFalse((domestic | foreign) & elections)
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

    def test_legacy_return_gate_is_closed_even_with_all_old_permissions(self):
        definitions = {e.key: e.value for e in parse_clausewitz(read(TRIGGERS))}
        gate = definitions['STP_ps_can_launch_return']
        self.assertEqual(signature(gate), [('always', 'no')])
        for training, alive, allied, own_subject, active, closed in product((False, True), repeat=6):
            facts = {('NOD', 'has_country_flag', 'STP_ps_exile_received'): True,
                     ('NOD', 'has_country_flag', 'STP_ps_return_terms_accepted'): True,
                     ('NOD', 'has_country_flag', 'STP_ps_exile_training_completed'): training,
                     ('NOD', 'has_country_flag', 'STP_ps_return_campaign'): active,
                     ('NOD', 'has_country_flag', 'STP_ps_return_closed'): closed,
                     ('NOD', 'is_in_faction_with', 'STS'): allied,
                     ('STP', 'exists', 'no'): True,
                     ('STS', 'has_capitulated', 'no'): alive,
                     ('STS', 'is_subject_of', 'NOD'): own_subject}
            self.assertFalse(matches_conditions(gate, facts, 'NOD'))

    def test_legacy_return_has_no_clickable_declaration_or_callback(self):
        self.assertNotIn('STP_ps_launch_return', self.decisions)
        self.assertNotIn('STP_ps_begin_return', self.effects)
        self.assertNotIn('STP_ps_settle_return', read('common/on_actions/09_ADISCORD_scripted_peace_on_actions.txt'))

    def test_retired_exile_does_not_move_or_restore_a_character(self):
        definitions = {e.key: e.value for e in parse_clausewitz(read(TRIGGERS))}
        character_gate = one(definitions['STP_ps_hedersett_available'], 'STP_rufus_hedersett')
        for arrested in (False, True):
            facts = {('STP_rufus_hedersett', 'has_character_flag', 'STP_cw_arrested'): arrested}
            self.assertEqual(matches_conditions(character_gate, facts, 'STP_rufus_hedersett'), not arrested)
        for name in ('STP_ps_accept_exile', 'STP_ps_settle_return'):
            self.assertNotIn(name, self.effects)
        for name in ('STP_ps_prepare_exile', 'STP_ps_close_exile'):
            self.assertNotIn('set_nationality', {e.key for e in walk(self.effects[name])})


class PartyWartimeFocusContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        tree = parse_clausewitz(read('common/national_focus/ADISCORD_national_focus_STP.txt'))
        cls.foci = {one(e.value, 'id'): e.value for e in walk(tree)
                    if e.key == 'focus' and isinstance(e.value, list)}
        cls.decisions = {e.key: e.value for e in walk(parse_clausewitz(read(DECISIONS)))
                         if isinstance(e.value, list)}

    def reachable(self, *, congress, port, niansas, stage, government=True, fell=True):
        facts = {('STP', 'STP_ps_war_active', 'yes'): True,
                 ('STP', 'STP_ps_government_operational', 'yes'): government,
                 ('STP', 'STP_ps_can_counterattack', 'yes'): stage == 4 and government,
                 ('STP', 'has_country_flag', 'STP_ps_congress_fell'): fell,
                 ('STP', 'variable', 'STP_ps_stage'): stage,
                 ('STP', 'owns_state', '28'): True,
                 ('STP', 'controls_province', '145'): congress,
                 ('STP', 'controls_province', '16366'): port,
                 ('STP', 'controls_province', '45'): niansas,
                 ('STP', 'controls_province', '16351'): congress}
        done = {'STP_cw_unified_headquarters'}
        changed = True
        while changed:
            changed = False
            for name, focus in self.foci.items():
                if name in done:
                    continue
                # Only the party-only wartime branches are under review here.
                branch = next((e.value for e in focus if e.key == 'allow_branch'), [])
                if ('tag', 'STP') not in signature(branch) or ('NOT', [('has_country_flag', 'STP_cw_postwar')]) not in signature(branch):
                    continue
                groups = children(focus, 'prerequisite')
                if not all(any(e.value in done for e in group) for group in groups):
                    continue
                if matches_conditions(next((e.value for e in focus if e.key == 'available'), []), facts, 'STP'):
                    done.add(name)
                    changed = True
        return done

    def test_lost_capital_and_niansas_do_not_cut_off_staff_or_intelligence(self):
        for stage in (1, 2, 3, 4):
            done = self.reachable(congress=False, port=False, niansas=False, stage=stage)
            self.assertTrue({'STP_ps_temporary_presidium', 'STP_ps_restore_couriers',
                             'STP_party_rear_administration', 'STP_ps_counter_supply'} <= done)
            self.assertNotIn('STP_ps_route_security', done)
            self.assertEqual('STP_party_war_directorate' in done, stage >= 2)
            self.assertEqual('STP_cw_capital_counteroffensive' in done, stage == 4)
            self.assertEqual('STP_cw_assault_columns' in done, stage == 4)

    def test_port_can_be_defended_while_the_government_is_displaced(self):
        done = self.reachable(congress=False, port=True, niansas=False, stage=1, government=False)
        self.assertTrue({'STP_cw_guard_the_pier', 'STP_cw_harbour_batteries'} <= done)
        self.assertNotIn('STP_party_war_directorate', done)
        gate = one(self.decisions['STP_cw_hold_the_pier'], 'available')
        self.assertIn(('controls_province', '16366'), signature(gate))
        self.assertNotIn(('controls_state', '28'), signature(gate))

    def test_supply_is_usable_inside_the_defensive_phase(self):
        headquarters = float(one(self.foci['STP_cw_unified_headquarters'], 'cost')) * 7
        transport = float(one(self.foci['STP_party_war_transport'], 'cost')) * 7
        delivery = int(one(self.decisions['STP_ps_transport_work'], 'days_mission_timeout'))
        self.assertEqual(headquarters + transport + delivery, 49)
        self.assertLess(headquarters + transport + delivery, 56)
        groups = children(self.foci['STP_ps_ammunition_board'], 'prerequisite')
        self.assertEqual([set(e.value for e in group) for group in groups],
                         [{'STP_party_war_transport', 'STP_cw_wartime_arsenals'}])

    def test_first_paid_cabinet_response_fits_deadline_and_free_response_stays_open(self):
        focus_days = float(one(self.foci['STP_ps_temporary_presidium'], 'cost')) * 7
        mission_days = int(one(self.decisions['STP_ps_cabinet_work'], 'days_mission_timeout'))
        paid = self.decisions['STP_ps_emergency_cabinet']
        delta = next(int(one(e.value, 'days')) for e in walk(paid) if e.key == 'add_days_mission_timeout')
        deadline = int(one(self.decisions['STP_ps_congress_deadline'], 'days_mission_timeout'))
        reward = one(self.foci['STP_ps_temporary_presidium'], 'completion_reward')
        extension = next(e.value for e in walk(reward) if e.key == 'add_days_mission_timeout')
        self.assertEqual(one(extension, 'mission'), 'STP_ps_congress_deadline')
        self.assertLess(focus_days + mission_days + delta, deadline + int(one(extension, 'days')))
        for gate in (one(paid, 'visible'), one(paid, 'available'), one(paid, 'complete_effect')):
            self.assertIn('STP_ps_temporary_presidium', str(signature(gate)))
        for name in ('STP_ps_emergency_cabinet_administrative', 'STP_ps_emergency_cabinet_prepared'):
            self.assertNotIn('STP_ps_temporary_presidium', str(signature(self.decisions[name])))

    def test_restored_couriers_unlock_a_real_order_with_its_command_price(self):
        reward = one(self.foci['STP_ps_restore_couriers'], 'completion_reward')
        self.assertEqual(one(reward, 'add_command_power'), '25')
        order = self.decisions['STP_cw_regroup_the_front']
        visible = one(order, 'visible')
        self.assertTrue(matches_conditions(visible, {('STP', 'has_completed_focus', 'STP_ps_restore_couriers'): True}))
        self.assertEqual(one(one(order, 'complete_effect'), 'add_command_power'), '-25')

    def test_returning_government_needs_actual_recapture(self):
        for held, lost in product((False, True), repeat=2):
            gate = one(self.foci['STP_ps_retake_congress'], 'available')
            facts = {('STP', 'STP_ps_war_active', 'yes'): True,
                     ('STP', 'controls_province', '145'): held,
                     ('STP', 'has_country_flag', 'STP_ps_congress_fell'): lost}
            self.assertEqual(matches_conditions(gate, facts), held and lost)
        reward = one(self.foci['STP_ps_retake_congress'], 'completion_reward')
        self.assertFalse({'transfer_state', 'set_state_controller_to', 'add_timed_idea'} & {e.key for e in walk(reward)})

    def test_inner_ring_builds_only_in_held_city_nodes(self):
        from tools.tests.test_adiscord_stp_preparation import selected_effects
        reward = one(self.foci['STP_cw_inner_ring'], 'completion_reward')
        for left, right in product((False, True), repeat=2):
            facts = {('STP', 'controls_province', '16351'): left,
                     ('STP', 'controls_province', '16377'): right}
            output = list(selected_effects(reward, facts))
            provinces = {one(e.value, 'province') for _, e in output if e.key == 'add_building_construction'}
            self.assertEqual(provinces, {p for p, held in [('16351', left), ('16377', right)] if held})


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
        cls.categories = {e.key: e.value for e in parse_clausewitz(read('common/decisions/categories/ADISCORD_decision_categories_STP.txt'))}

    def test_recovery_stage_has_a_real_but_defence_safe_penalty(self):
        for active in (False, True):
            for stage, expected in ((1, -.45), (2, -.3), (3, -.15), (4, 0)):
                facts = {('STP', 'STP_ps_war_active', 'yes'): active,
                         ('STP', 'variable', 'STP_ps_stage'): stage}
                values = {}
                for _, e in selected_effects(self.effects['STP_ps_refresh_defence'], facts):
                    if e.key == 'set_variable':
                        values[one(e.value, 'var')] = float(one(e.value, 'value'))
                self.assertEqual(values.get('STP_ps_breakthrough'), expected if active else 0)
                self.assertNotIn('STP_ps_stage', values)
        dynamic = one(parse_clausewitz(read('common/dynamic_modifiers/ADISCORD_dynamic_modifiers_STP.txt')), 'STP_ps_defence_dynamic')
        self.assertEqual(one(dynamic, 'breakthrough_factor'), 'STP_ps_breakthrough')
        self.assertNotIn('army_defence_factor', {e.key for e in dynamic})

    def test_foreign_operations_share_the_external_category(self):
        names = ['STP_ps_fund_nod', 'STP_ps_arm_nod', 'STP_ps_engineers_nod',
                 'STP_ps_expedition_nod', 'STP_ps_nod_dispatch', 'STP_ps_nod_delivery',
                 'STP_ps_cancel_nod', 'STP_ps_nod_route_wait',
                 'STP_ps_val_intelligence', 'STP_ps_val_intelligence_work',
                 'STP_ps_val_intercept', 'STP_ps_val_intercept_work',
                 'STP_ps_val_pressure', 'STP_ps_val_pressure_work',
                 'STP_pw_party_nod_invasion_countdown', 'STP_pw_party_nod_emergency_mobilization',
                 'STP_pw_party_nod_fortify_border', 'STP_pw_party_nod_staff_readiness']
        for name in names:
            self.assertEqual(self.owners[name], 'STP_cw_external_intervention', name)
        self.assertNotIn('STP_postwar_nod_ultimatum', self.categories)

    def test_domestic_preparation_sits_with_the_party_apparatus(self):
        for name in ('STP_ps_build_radio', 'STP_ps_build_radio_work', 'STP_ps_build_hq',
                     'STP_ps_build_hq_work', 'STP_ps_prepare_evacuation', 'STP_ps_prepare_evacuation_work',
                     'STP_ps_evacuate_funds', 'STP_ps_release_government_reserve'):
            self.assertEqual(self.owners[name], 'STP_party_factions', name)

    def test_elections_close_and_external_work_remains_visible(self):
        election = one(self.categories['STP_elections_in_the_party'], 'visible')
        self.assertFalse(matches_conditions(election, {
            ('STP', 'has_global_flag', 'STP_cw_started'): True,
            ('STP', 'has_country_flag', 'STP_sided_with_the_party_flag'): True,
            ('STP', 'has_variable', 'STP_ps_nod_receipt_type'): True,
        }))
        external = one(self.categories['STP_cw_external_intervention'], 'visible')
        self.assertTrue(matches_conditions(external, {
            ('STP', 'tag', 'STP'): True,
            ('STP', 'has_country_flag', 'STP_sided_with_the_party_flag'): True,
            ('STP', 'STP_cw_preparation_open', 'yes'): True,
        }))
        self.assertTrue(matches_conditions(external, {('STP', 'has_variable', 'STP_ps_nod_receipt_type'): True}))
        self.assertEqual(one(self.categories['STP_cw_war_council'], 'visible_when_empty'), 'no')

    def test_current_supply_deadline_is_checked_before_both_payments(self):
        for action, threshold in (('val_intelligence', 22), ('val_intercept', 15)):
            name = 'STP_ps_' + action
            trigger = name + '_time_available'
            self.assertIn(trigger, self.triggers)
            gate = self.triggers[trigger]
            for days in (0, threshold - .01, threshold, threshold + 1):
                facts = {('VAL', 'has_active_mission', 'STP_ps_val_departure'): True,
                         ('VAL', 'variable', 'days_mission_timeout@STP_ps_val_departure'): days}
                self.assertEqual(matches_conditions(gate, facts), days >= threshold)
                facts[('VAL', 'has_active_mission', 'STP_ps_val_departure')] = False
                self.assertFalse(matches_conditions(gate, facts))
            for phase in ('available', 'complete_effect'):
                self.assertIn(trigger, str(signature(one(self.decisions[name], phase))))
        tokens = read('common/synchronized_dynamic_tokens/ADISCORD_tokens.txt').splitlines()
        self.assertIn('STP_ps_val_departure', tokens)

    def test_pressure_delays_the_current_departure_not_only_future_cargo(self):
        body = self.effects['STP_ps_val_pressure_finish']
        changes = [(scope, one(e.value, 'mission'), one(e.value, 'days'))
                   for scope, e in selected_effects(body, {
                       ('STP', 'has_variable', 'STP_ps_val_pressure_deposit'): True,
                       ('STP', 'tag', 'STP'): True,
                       ('STP', 'STP_cw_preparation_open', 'yes'): True,
                       ('STP', 'has_completed_focus', 'STP_ps_foreign_supply_desk'): True,
                       ('VAL', 'exists', 'yes'): True,
                       ('VAL', 'has_active_mission', 'STP_ps_val_departure'): True,
                   }) if e.key == 'add_days_mission_timeout']
        self.assertEqual(changes, [('VAL', 'STP_ps_val_departure', '14')])
        self.assertIn('STP_ps_val_pressure_deposit', str(signature(body)))

    def test_nod_credit_requires_a_live_military_purpose(self):
        name = 'STP_ps_nod_credit_useful'
        self.assertIn(name, self.triggers)
        gate = self.triggers[name]
        self.assertFalse(matches_conditions(gate, {}))
        for condition in ('STP_ps_northern_front_active', 'NOD_cw_intervention_possible'):
            self.assertTrue(matches_conditions(gate, {('NOD', condition, 'yes'): True}))
        for phase in ('available', 'complete_effect'):
            self.assertIn(name, str(signature(one(self.decisions['STP_ps_fund_nod'], phase))))

    def test_briefings_are_compact_and_keep_operational_status(self):
        for lang in ('russian', 'english'):
            loc = read('localisation/' + lang + '/ADISCORD_STP_l_' + lang + '.yml')
            values = dict(re.findall(r'^ ([\w.]+):(?:\d+)?\s*"(.*)"$', loc, re.M))
            for key in ('STP_PARTY_ELECTION_BRIEFING', 'STP_ps_preparation_report',
                        'STP_ps_war_report', 'STP_party_factions_desc', 'STP_cw_war_council_desc'):
                self.assertLessEqual(len(values[key]), 560, key)
            self.assertIn('[STPGetPartySurvival]', values['STP_cw_war_council_desc'])
            self.assertIn('[STPGetRecoveryReport]', values['STP_cw_war_council_desc'])
            self.assertIn('[STPGetPartyPreparationReport]', values['STP_party_factions_desc'])
            self.assertNotIn('[STPGetPartyHandoff]', values['STP_ps_preparation_report'])

    def test_layout_refresh_is_deferred_and_runs_on_loading_a_save(self):
        events = parse_clausewitz(read('events/ADISCORD_STP_events.txt'))
        refresh = [e.value for e in events if e.key == 'country_event'
                   and one(e.value, 'id') == 'ADISCORD_STP_preparation.26']
        self.assertEqual(len(refresh), 1)
        self.assertEqual(signature(one(refresh[0], 'immediate')), [('mark_focus_tree_layout_dirty', 'yes')])
        choice = next(e.value for e in events if e.key == 'country_event' and one(e.value, 'id') == 'ADISCORD_STP_preparation.1')
        for option in children(choice, 'option'):
            calls = [e.value for e in walk(option) if e.key == 'country_event'
                     and one(e.value, 'id') == 'ADISCORD_STP_preparation.26']
            self.assertEqual(len(calls), 1)
            self.assertEqual(one(calls[0], 'hours'), '1')
        hooks = one(parse_clausewitz(read('common/on_actions/02_ADISCORD_STP_on_actions.txt')), 'on_actions')
        startup = one(hooks, 'on_startup')
        self.assertIn('ADISCORD_STP_preparation.26', str(signature(startup)))
        self.assertIn('STP_ps_refresh_defence', str(signature(startup)))
        self.assertNotIn('set_variable', {e.key for e in walk(startup)})

    def test_supply_focus_advertises_all_three_actual_tools(self):
        trees = parse_clausewitz(read('common/national_focus/ADISCORD_national_focus_STP.txt'))
        focus = next(f.value for t in trees if t.key == 'focus_tree' for f in t.value
                     if f.key == 'focus' and one(f.value, 'id') == 'STP_ps_foreign_supply_desk')
        unlocks = {one(e.value, 'decision') if isinstance(e.value, list) else e.value for e in one(focus, 'completion_reward') if e.key == 'unlock_decision_tooltip'}
        self.assertEqual(unlocks, {'STP_ps_val_intelligence', 'STP_ps_val_intercept', 'STP_ps_val_pressure'})


class PartyAdviserRedesignContracts(unittest.TestCase):
    """Authored-script behaviour; native save loading still requires a game check."""

    @classmethod
    def setUpClass(cls):
        cls.effects = {e.key: e.value for e in parse_clausewitz(read(EFFECTS))}
        cls.triggers = {e.key: e.value for e in parse_clausewitz(read(TRIGGERS))}
        cls.categories = {e.key: e.value for e in parse_clausewitz(read(DECISIONS))}
        cls.decisions = {e.key: e.value for entries in cls.categories.values() for e in entries if isinstance(e.value, list)}
        cls.foci = {one(e.value, 'id'): e.value for e in walk(parse_clausewitz(read('common/national_focus/ADISCORD_national_focus_STP.txt'))) if e.key in ('focus', 'shared_focus') and isinstance(e.value, list)}

    def test_visible_country_names_not_engine_tags(self):
        root = Path(__file__).resolve().parents[2]
        for lang in ('russian', 'english'):
            for file in ('ADISCORD_STP_l_', 'ADISCORD_VAL_decisions_l_', 'ADISCORD_vorkerland_l_', 'ADISCORD_scenario_debug_l_'):
                path = root / 'localisation' / lang / (file + lang + '.yml')
                for line in path.read_text(encoding='utf-8-sig').splitlines():
                    match = re.match(r'^\s*[^#\s:]+:\d*\s*"(.*)"\s*$', line)
                    if match:
                        plain = re.sub(r'\[[^\]]*\]|\$[^$]*\$', '', match.group(1))
                        self.assertNotRegex(plain, r'\b(?:NOD|VAL|STP|STS|SRP|VAD|WRK|TVA|TFF|EYR|EGC|RIV|REV|YOR|NDN|SWB|VHV|OSV)\b', str(path) + ': ' + line[:90])

    def test_exile_route_is_not_playable(self):
        self.assertNotIn('STP_ps_exile', self.categories)
        for name in ('STP_ps_exile_office', 'STP_ps_exile_survivors', 'STP_ps_host_agreement', 'STP_ps_exile_formations', 'STP_ps_return_terms', 'STP_ps_return_campaign_focus'):
            self.assertNotIn(name, self.foci)
        for name in ('STP_ps_accept_return_terms', 'STP_ps_launch_return', 'STP_ps_exile_training', 'STP_ps_exile_formation'):
            self.assertNotIn(name, self.decisions)
        self.assertNotIn('STP_ps_exile_office', read('common/national_focus/generic.txt'))
        self.assertNotIn('STP_ps_exile_plan', read('common/ai_strategy_plans/ADISCORD_STP_plans.txt'))
        self.assertNotIn('STP_ps_settle_return', read('common/on_actions/09_ADISCORD_scripted_peace_on_actions.txt'))

    def test_queued_exile_events_only_close_legacy_state(self):
        events = {one(e.value, 'id'): e.value for e in parse_clausewitz(read('events/ADISCORD_STP_events.txt')) if e.key == 'country_event'}
        for number in range(201, 205):
            body = events[f'ADISCORD_STP_cw.{number}']
            self.assertEqual(one(body, 'hidden'), 'yes')
            self.assertEqual(signature(one(body, 'immediate')), [('STP_ps_close_exile', 'yes')])
            self.assertNotIn('option', {e.key for e in body})
        for name in ('STP_ps_prepare_exile', 'STP_ps_close_exile'):
            self.assertFalse({'set_nationality', 'change_tag_from', 'declare_war_on', 'transfer_state'} & {e.key for e in walk(self.effects[name])})
        self.assertNotIn('STP_ps_accept_exile', self.effects)

    def test_defeat_settles_orders_without_exporting_government(self):
        effect = self.effects['STP_ps_prepare_exile']
        keys = {e.key for e in walk(effect)}
        self.assertIn('STP_ps_refund_government_reserve', keys)
        self.assertNotIn('country_event', keys)
        self.assertNotIn('NOD', keys)
        self.assertIn('STP_ps_transport_refund', keys)
        self.assertIn('STP_ps_val_intercept_refund', keys)

    def test_adviser_pressure_is_influence_cost_not_negative_help(self):
        from tools.tests.test_adiscord_stp_party_route import PartyFactionContracts
        harness = PartyFactionContracts()
        harness.effects, harness.triggers = self.effects, self.triggers
        for influence in (0, 8, 30, 60, 100):
            for support in (0, 40, 50, 75, 100):
                for connected in (False, True):
                    values, flags = harness.simulate('STP_pf_initialize')
                    values['STP_pf_advisers_influence'] = influence
                    values['STP_pf_advisers_support'] = support
                    harness.simulate('STP_pf_calculate', values, flags, nod=connected)
                    self.assertIn('STP_pf_advisers_pressure', values)
                    self.assertAlmostEqual(float(values['STP_pf_advisers_pressure']), -influence * .002 if connected else 0)
                    self.assertAlmostEqual(float(values['STP_pf_advisers_effect']), max(0, support - 50) * influence * .004 / 100 if connected else 0)
        dynamic = {e.key: e.value for e in parse_clausewitz(read('common/dynamic_modifiers/ADISCORD_dynamic_modifiers_STP.txt'))}
        self.assertEqual(one(dynamic['STP_pf_balance_dynamic'], 'political_power_factor'), 'STP_pf_advisers_pressure')
        self.assertIn(('clear_variable', 'STP_pf_advisers_pressure'), signature(list(walk(self.effects['STP_pf_clear']))))

    def test_sovereignty_clears_both_adviser_outputs_before_its_own_completion(self):
        reward = one(self.foci['STP_pw_party_sovereignty'], 'completion_reward')
        zeroed = {one(e.value, 'var') for e in walk(reward)
                  if e.key == 'set_variable' and one(e.value, 'value') == '0'}
        self.assertTrue({'STP_pf_advisers_effect', 'STP_pf_advisers_pressure'} <= zeroed)

    def test_limit_transfers_only_existing_influence_and_cannot_touch_other_countries(self):
        from tools.tests.test_adiscord_stp_party_route import PartyFactionContracts
        name = 'STP_pf_limit_adviser_influence'
        self.assertIn(name, self.effects)
        harness = PartyFactionContracts()
        harness.effects, harness.triggers = self.effects, self.triggers
        for influence in (0, .001, 4.999, 5, 8, 60, 100):
            values, flags = harness.simulate('STP_pf_initialize')
            for key in harness.KEYS:
                values[f'STP_pf_{key}_influence'] = 0
            values['STP_pf_advisers_influence'] = influence
            values['STP_pf_army_influence'] = 100 - influence
            harness.simulate(name, values, flags)
            self.assertAlmostEqual(float(values['STP_pf_advisers_influence']), max(0, influence - 5))
            self.assertAlmostEqual(float(sum(values[f'STP_pf_{key}_influence'] for key in harness.KEYS)), 100)
        self.assertFalse({'NOD', 'set_autonomy', 'declare_war_on', 'change_tag_from'} & {e.key for e in walk(self.effects[name])})

    def test_mandate_focus_unlocks_a_real_shared_cooldown_choice(self):
        decision = 'STP_pf_limit_advisers'
        self.assertIn(decision, self.decisions)
        action = self.decisions[decision]
        self.assertEqual(one(action, 'cost'), '35')
        self.assertIn('STP_pf_can_negotiate', str(signature(one(action, 'available'))))
        self.assertIn('STP_ps_asylum_protocol', str(signature(one(action, 'visible'))))
        reward = one(self.foci['STP_ps_asylum_protocol'], 'completion_reward')
        self.assertIn(decision, str(signature(reward)))
        self.assertNotIn('STP_ps_request_asylum', str(signature(reward)))
        self.assertIn('STP_pf_negotiation_cooldown', str(signature(one(action, 'complete_effect'))))

    def test_reserve_is_domestic_and_remains_refundable(self):
        reserve = self.decisions['STP_ps_evacuate_funds']
        self.assertIn('STP_ps_evacuate_funds', {e.key for e in self.categories['STP_party_factions']})
        self.assertNotIn('NOD', {e.key for e in walk(reserve)})
        self.assertIn('STP_ps_holds_congress', str(signature(one(reserve, 'available'))))
        self.assertIn('STP_ps_release_government_reserve', self.decisions)
        self.assertIn('STP_ps_refund_government_reserve', self.effects)
        writes = list(walk(self.effects['STP_ps_refund_government_reserve']))
        keys = [e.key for e in writes]
        self.assertLess(keys.index('clear_variable'), keys.index('add_to_variable'))
        self.assertIn('STP_ps_evacuated_money', str(signature(writes)))

    def test_paid_reserve_starts_only_a_domestic_working_cabinet(self):
        name = 'STP_ps_use_government_reserve'
        self.assertIn(name, self.effects)
        for war, working, land, amount in product((False, True), (False, True), (False, True), (0, 2999.999, 3000)):
            facts = {('STP', 'STP_ps_war_active', 'yes'): war,
                     ('STP', 'STP_ps_government_operational', 'no'): not working,
                     ('STP', 'has_variable', 'STP_ps_evacuated_money'): amount > 0,
                     ('STP', 'variable', 'STP_ps_evacuated_money'): amount,
                     ('STP', 'owns_state', '2'): True, ('STP', 'controls_state', '2'): land}
            output = list(selected_effects(self.effects[name], facts))
            flags = [(scope, e.value) for scope, e in output if e.key == 'set_country_flag']
            expected = war and not working and land and amount >= 3000
            self.assertEqual(flags, [('STP', 'STP_ps_temporary_government')] if expected else [])
            self.assertFalse(any(e.key in ('transfer_state', 'change_tag_from', 'set_nationality', 'add_manpower') for _, e in output))
        crisis = [e.key for e in walk(self.effects['STP_ps_open_congress_crisis'])]
        self.assertLess(crisis.index(name), crisis.index('STP_ps_pause_reorganisation'))
        startup = read('common/on_actions/02_ADISCORD_STP_on_actions.txt')
        self.assertIn('STP_ps_close_exile', startup)
        self.assertNotIn('STP_ps_settle_return', startup)

    def test_bilingual_text_and_encoding_match_new_mechanics(self):
        root = Path(__file__).resolve().parents[2]
        for lang in ('russian', 'english'):
            raw = (root / 'localisation' / lang / f'ADISCORD_STP_l_{lang}.yml').read_bytes()
            self.assertTrue(raw.startswith(b'\xef\xbb\xbf'))
            loc = dict(re.findall(r'^\s*([^#\s:]+):(?:\d+)?\s*"(.*)"\s*$', raw.decode('utf-8-sig'), re.M))
            for key in ('STP_pf_limit_advisers', 'STP_pf_limit_advisers_desc', 'STP_pf_limit_advisers_tt', 'STP_ps_reserve_used_tt'):
                self.assertIn(key, loc)
            self.assertIn('STP_pf_advisers_pressure', loc['STP_pf_advisers_tt'])
            self.assertNotIn('STP_ps_asylum_scope_tt', loc)
