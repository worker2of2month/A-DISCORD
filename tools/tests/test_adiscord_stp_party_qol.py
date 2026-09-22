"""Party UI and transaction contracts; these do not simulate the HOI4 engine."""
import re
import unittest
from pathlib import Path

from tools.tests.test_adiscord_stp_preparation import block, scalar, walk, matches_conditions, selected_effects
from tools.validators.validate_adiscord_division_templates import parse_clausewitz

ROOT = Path(__file__).resolve().parents[2]
DECISIONS = 'common/decisions/ADISCORD_STP_decisions.txt'
CATEGORIES = 'common/decisions/categories/ADISCORD_decision_categories_STP.txt'
EFFECTS = 'common/scripted_effects/ADISCORD_STP_scripted_effects.txt'
TRIGGERS = 'common/scripted_triggers/ADISCORD_STP_scripted_triggers.txt'
FOCUSES = 'common/national_focus/ADISCORD_national_focus_STP.txt'
FOREIGN = ('STP_ps_fund_nod', 'STP_ps_arm_nod', 'STP_ps_engineers_nod',
           'STP_ps_expedition_nod', 'STP_ps_nod_dispatch', 'STP_ps_nod_delivery',
           'STP_ps_cancel_nod', 'STP_ps_nod_route_wait', 'STP_ps_val_intelligence',
           'STP_ps_val_intelligence_work', 'STP_ps_val_intercept',
           'STP_ps_val_intercept_work', 'STP_ps_val_pressure', 'STP_ps_val_pressure_work',
           'STP_ps_evacuate_funds')
GOVERNMENT = ('STP_ps_build_radio', 'STP_ps_build_radio_work', 'STP_ps_build_hq',
              'STP_ps_build_hq_work', 'STP_ps_prepare_evacuation', 'STP_ps_prepare_evacuation_work')
POLICIES = ('STP_ps_operational_reserve', 'STP_ps_route_security')


def read(path):
    return (ROOT / path).read_text(encoding='utf-8-sig')


def localization(language):
    return dict(re.findall(r'^ ([\w.]+):\d*\s*"((?:[^"\\]|\\.)*)"\s*$',
                           read(f'localisation/{language}/ADISCORD_STP_l_{language}.yml'), re.M))


class PartyQualityOfLifeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.decisions = {}
        cls.owners = {}
        for category in parse_clausewitz(read(DECISIONS)):
            for entry in category.value:
                if isinstance(entry.value, list):
                    if entry.key in cls.decisions:
                        raise AssertionError('Duplicate decision: ' + entry.key)
                    cls.decisions[entry.key] = entry.value
                    cls.owners[entry.key] = category.key
        cls.categories = {e.key: e.value for e in parse_clausewitz(read(CATEGORIES))}
        cls.effects = {e.key: e.value for e in parse_clausewitz(read(EFFECTS))}
        cls.triggers = {e.key: e.value for e in parse_clausewitz(read(TRIGGERS))}
        cls.focuses = {scalar(e.value, 'id'): e.value for e in walk(parse_clausewitz(read(FOCUSES)))
                       if e.key == 'focus' and isinstance(e.value, list)}

    def test_foreign_operations_have_one_destination(self):
        for name in FOREIGN:
            with self.subTest(decision=name):
                self.assertEqual(self.owners[name], 'STP_cw_external_intervention')

    def test_government_preparation_is_with_the_apparatus(self):
        for name in GOVERNMENT:
            self.assertEqual(self.owners[name], 'STP_party_factions', name)

    def test_nod_ultimatum_uses_the_existing_foreign_category(self):
        for name in ('STP_pw_party_nod_invasion_countdown', 'STP_pw_party_nod_emergency_mobilization',
                     'STP_pw_party_nod_fortify_border', 'STP_pw_party_nod_staff_readiness'):
            self.assertEqual(self.owners[name], 'STP_cw_external_intervention')
        self.assertNotIn('STP_postwar_nod_ultimatum', self.categories)
        visible = str(block(self.categories['STP_cw_external_intervention'], 'visible'))
        for flag in ('STP_pw_party_nod_threat_active', 'STP_pw_party_nod_invasion_active'):
            self.assertIn(flag, visible)

    def test_empty_election_and_war_panels_do_not_linger(self):
        for name in ('STP_elections_in_the_party', 'STP_cw_war_council'):
            self.assertEqual(scalar(self.categories[name], 'visible_when_empty'), 'no')
        visible = block(self.categories['STP_elections_in_the_party'], 'visible')
        for war, finished in ((True, False), (False, True), (True, True)):
            facts = {('STP', 'has_global_flag', 'STP_cw_started'): war,
                     ('STP', 'has_country_flag', 'STP_cw_elections_finished'): finished,
                     ('STP', 'has_country_flag', 'STP_sided_with_the_party_flag'): True,
                     ('STP', 'has_variable', 'STP_ps_nod_receipt_type'): True}
            self.assertFalse(matches_conditions(visible, facts))

    def test_pressure_affects_the_current_shipment_on_purchase(self):
        start = list(walk(block(self.decisions['STP_ps_val_pressure'], 'complete_effect')))
        self.assertIn('STP_ps_val_pressure_finish', [e.key for e in start])
        self.assertNotIn('STP_ps_val_pressure_work', [e.value for e in start if e.key == 'activate_mission'])
        finish = self.effects['STP_ps_val_pressure_finish']
        extensions = [e.value for e in walk(finish) if e.key == 'add_days_mission_timeout']
        self.assertEqual([(scalar(e, 'mission'), scalar(e, 'days')) for e in extensions],
                         [('STP_ps_val_departure', '14')])
        self.assertIn('STP_ps_val_pressure_cooldown', str(finish))
        self.assertIn('STP_ps_val_pressure_active', str(finish))

    def test_pressure_keeps_a_live_route_and_a_legacy_refund_path(self):
        self.assertIn('STP_ps_val_pressure_available', self.triggers)
        context = self.triggers['STP_ps_val_pressure_available']
        self.assertIn('STP_ps_val_supply_open', str(context))
        self.assertIn('STP_ps_val_pressure_available', str(self.decisions['STP_ps_val_pressure']))
        self.assertIn('STP_ps_val_pressure_refund', str(self.effects['STP_ps_val_pressure_finish']))
        self.assertIn('STP_ps_val_pressure_finish', str(self.decisions['STP_ps_val_pressure_work']))

    def test_recon_and_intercept_reject_impossible_deadlines(self):
        for name, days in (('STP_ps_val_recon_window', 22), ('STP_ps_val_intercept_window', 15)):
            self.assertIn(name, self.triggers)
            body = self.triggers[name]
            for remaining in (0, days - 1, days, days + 1):
                facts = {('VAL', 'has_active_mission', 'STP_ps_val_departure'): True,
                         ('VAL', 'variable', 'days_mission_timeout@STP_ps_val_departure'): remaining}
                self.assertEqual(matches_conditions(body, facts), remaining >= days, (name, remaining))
            self.assertFalse(matches_conditions(body, {
                ('VAL', 'variable', 'days_mission_timeout@STP_ps_val_departure'): 99}))
        for action, trigger in (('STP_ps_val_intelligence', 'STP_ps_val_recon_window'),
                                ('STP_ps_val_intercept', 'STP_ps_val_intercept_window')):
            self.assertIn(trigger, str(block(self.decisions[action], 'available')))
            self.assertIn(trigger, str(block(self.decisions[action], 'complete_effect')))
            self.assertNotIn(trigger, str(block(self.decisions[action], 'visible')))
            # The remaining-time entry gate must not cancel work already paid for.
            work = self.decisions[action + '_work']
            self.assertNotIn(trigger, str(block(work, 'cancel_trigger')))

    def test_duplicate_recon_and_interception_cannot_charge_again(self):
        for action, marker in (('STP_ps_val_intelligence', 'STP_ps_val_known_sequence'),
                               ('STP_ps_val_intercept', 'STP_ps_val_intercepted_sequence')):
            gate = block(self.decisions[action], 'available')
            self.assertTrue(any(e.key == 'NOT' and marker in str(e.value) for e in walk(gate)))

    def test_nod_stale_delivery_refunds_instead_of_consuming_the_order(self):
        selected = list(selected_effects(self.effects['STP_ps_deliver_nod'], {
            ('STP', 'variable', 'STP_ps_nod_receipt_stage'): 2,
            ('STP', 'STP_ps_nod_order_current', 'yes'): False}))
        self.assertIn('STP_ps_refund_nod', [e.key for _, e in selected])
        self.assertNotIn('STP_ps_clear_nod_receipt', [e.key for _, e in selected])

    def test_nod_refund_accepts_transit_and_is_idempotent(self):
        for stage in (1, 2):
            facts = {('STP', 'variable', 'STP_ps_nod_receipt_stage'): stage,
                     ('STP', 'variable', 'STP_ps_receipt_type'): 2}
            effects = list(selected_effects(self.effects['STP_ps_refund_nod'], facts))
            clears = [e for _, e in effects if e.key == 'STP_ps_clear_nod_receipt']
            self.assertEqual(len(clears), 1, stage)
            self.assertTrue(any(e.key == 'add_to_variable' and scalar(e.value, 'var') == 'ADISCORD_economy_treasury'
                                for _, e in effects))
            facts[('STP', 'variable', 'STP_ps_nod_receipt_stage')] = 0
            self.assertEqual(list(selected_effects(self.effects['STP_ps_refund_nod'], facts)), [])

    def test_war_policy_is_a_real_choice_without_blocking_the_directorate(self):
        for chosen, alternative, idea in ((POLICIES[0], POLICIES[1], 'STP_ps_reserve_idea'),
                                           (POLICIES[1], POLICIES[0], 'STP_ps_route_guard_idea')):
            focus = self.focuses[chosen]
            self.assertIn(alternative, [e.value for e in block(focus, 'mutually_exclusive')])
            self.assertIn(idea, str(block(focus, 'completion_reward')))
            self.assertIn('STP_pf_shift', str(block(focus, 'completion_reward')))
        prerequisites = [e.value for e in self.focuses['STP_party_war_directorate'] if e.key == 'prerequisite']
        self.assertTrue(any(set(POLICIES).issubset({e.value for e in p}) for p in prerequisites))
        self.assertEqual(scalar(block(self.focuses[POLICIES[1]], 'prerequisite'), 'focus'), 'STP_cw_unified_headquarters')

    def test_four_faction_focuses_do_not_also_reward_every_faction(self):
        for name in ('STP_GUARANTEE_MINISTERS', 'STP_ROTATE_DISTRICT_COMMAND',
                     'STP_cw_security_collegium', 'STP_cw_capital_oath'):
            reward = list(walk(block(self.focuses[name], 'completion_reward')))
            self.assertIn('STP_pf_shift', [e.key for e in reward])
            self.assertNotIn('STP_change_apparatus_loyalty', [e.key for e in reward], name)

    def test_counter_supply_focus_identifies_a_real_current_cargo(self):
        reward = str(block(self.focuses['STP_ps_counter_supply'], 'completion_reward'))
        self.assertIn('STP_ps_val_receipt_rifles', reward)
        self.assertIn('STP_ps_val_known_sequence', reward)
        self.assertIn('STP_ps_val_sequence', reward)
        self.assertIn('add_intel', reward)
        desk = str(block(self.focuses['STP_ps_foreign_supply_desk'], 'completion_reward'))
        for action in ('intelligence', 'intercept', 'pressure'):
            self.assertIn('STP_ps_val_' + action, desk)

    def test_party_briefings_are_bounded_and_bilingual(self):
        keys = ('STP_PARTY_ELECTION_BRIEFING', 'STP_party_factions_desc',
                'STP_ps_preparation_report', 'STP_PARTY_WAR_BRIEFING', 'STP_PARTY_FOREIGN_BRIEFING')
        for language in ('russian', 'english'):
            loc = localization(language)
            for key in keys:
                self.assertIn(key, loc)
                self.assertLessEqual(len(loc[key]), 650, (language, key))
            self.assertNotIn('STPGetPartyPreparationReport', loc['STP_PARTY_ELECTION_BRIEFING'])
            self.assertNotIn('STPGetPartyHandoff', loc['STP_ps_preparation_report'])
            for action in ('intelligence', 'intercept', 'pressure'):
                self.assertIn('STP_ps_val_' + action + '_result_tt', loc)

    def test_both_selected_roots_recenter_and_save_load_invalidates_layout(self):
        for name, flag in (('STP_Show_Him_The_Truth', 'STP_sided_with_Maksim_flag'),
                           ('STP_Govern_In_His_Name', 'STP_sided_with_the_party_flag')):
            focus = self.focuses[name]
            offset = block(focus, 'offset')
            self.assertEqual(int(scalar(focus, 'x')) + int(scalar(offset, 'x')), 12)
            self.assertIn(flag, str(block(offset, 'trigger')))
        actions = parse_clausewitz(read('common/on_actions/02_ADISCORD_STP_on_actions.txt'))
        root = block(actions, 'on_actions')
        startups = [e.value for e in root if e.key == 'on_startup']
        self.assertTrue(any('mark_focus_tree_layout_dirty' in str(s) for s in startups))
        for startup in startups:
            self.assertNotIn('load_focus_tree', [e.key for e in walk(startup)])

    def test_new_timer_reads_are_registered_for_multiplayer(self):
        text = read(TRIGGERS) + read('common/scripted_localisation/ADISCORD_STP_scripted_loc.txt')
        tokens = set(read('common/synchronized_dynamic_tokens/ADISCORD_tokens.txt').splitlines())
        for mission in re.findall(r'days_mission_timeout@(STP_ps_\w+)', text):
            self.assertIn(mission, tokens)
        self.assertIn('STP_ps_val_departure', tokens)


if __name__ == '__main__':
    unittest.main()
