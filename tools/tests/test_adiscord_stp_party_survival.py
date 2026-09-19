"""Contracts for party recovery, scarce resources and exile settlement.

AST checks cover authored ordering and reachability, not native execution.
"""
import unittest

from tools.tests.test_adiscord_stp_party_route import read, children, one, walk, signature
from tools.validators.validate_adiscord_division_templates import parse_clausewitz

EFFECTS = 'common/scripted_effects/ADISCORD_STP_scripted_effects.txt'
DECISIONS = 'common/decisions/ADISCORD_STP_decisions.txt'


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
        self.assertIn('has_war_with', gate)
        self.assertIn('has_variable', gate)
        self.assertIn('STP_ps_stage', gate)


if __name__ == '__main__':
    unittest.main()
