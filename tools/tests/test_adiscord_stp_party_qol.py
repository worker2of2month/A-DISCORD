"""Party UI and transaction contracts; these do not simulate the HOI4 engine."""
import re
import unittest
from pathlib import Path
from tools.lib.focus_sources import read_focus_source

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
    return read_focus_source(ROOT / path, encoding='utf-8-sig')


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





    def test_election_category_stays_visible_until_the_election_is_resolved(self):
        category = self.categories['STP_elections_in_the_party']
        self.assertEqual(scalar(category, 'visible_when_empty'), 'yes')
        visible = block(category, 'visible')
        self.assertIn('STP_cw_started', str(visible))
        self.assertIn('STP_cw_elections_finished', str(visible))

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





if __name__ == '__main__':
    unittest.main()
