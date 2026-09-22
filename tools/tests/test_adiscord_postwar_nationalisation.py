"""Parsed-script contracts for postwar integration and the council's recovery.

These fixtures evaluate explicit scopes and callback effects, not the HOI4 runtime.
"""
from dataclasses import replace
from itertools import product
from pathlib import Path
import re
import unittest

from tools.tests.test_adiscord_stp_preparation import (
    block, entries, scalar, walk, matches_conditions, selected_effects,
)
from tools.validators.validate_adiscord_division_templates import Entry

ROOT = Path(__file__).resolve().parents[2]
STP_FOCUS = 'common/national_focus/ADISCORD_national_focus_STP.txt'
VAL_FOCUS = 'common/national_focus/ADISCORD_national_focus_VAL_defeated.txt'
STP_NEW = (
    'STP_pw_regional_citizenship', 'STP_pw_cadastral_commissions',
    'STP_pw_regional_connections', 'STP_pw_workshop_contracts',
    'STP_pw_local_officer_courses', 'STP_pw_common_market',
    'STP_pw_kefreyt_settlement',
)
VAL_NEW = (
    'VAL_defeat_Rebuild_The_Registry', 'VAL_defeat_Repair_The_Workshops',
    'VAL_defeat_Restore_Freight_Routes', 'VAL_defeat_Veterans_Register',
    'VAL_defeat_Staff_College', 'VAL_defeat_Civilian_Contracts',
    'VAL_defeat_Technical_Institute', 'VAL_defeat_Mountain_Exercises',
    'VAL_defeat_Frontline_Arsenals', 'VAL_defeat_Supply_For_The_Return',
    'VAL_defeat_Recovered_State',
)


def focuses(path, tree_id):
    tree = next(e.value for e in entries(path)
                if e.key == 'focus_tree' and scalar(e.value, 'id') == tree_id)
    return {scalar(e.value, 'id'): e.value for e in tree if e.key == 'focus'}


class PostwarNationalisationTests(unittest.TestCase):
    def setUp(self):
        self.triggers = {e.key: e.value for e in entries('common/scripted_triggers/ADISCORD_STP_scripted_triggers.txt')}
        self.decisions = {d.key: d.value for c in entries('common/decisions/ADISCORD_STP_decisions.txt')
                          for d in c.value if isinstance(d.value, list)}
        self.adjacency = {'1': ['2'], '2': ['1', '3'], '3': ['2'], '4': []}

    def decision(self):
        self.assertIn('STP_pw_nationalise_region', self.decisions.keys())
        return self.decisions['STP_pw_nationalise_region']

    def expand(self, nodes, country='STS', target='2', scope=None):
        scope = scope or country
        result = []
        for e in nodes:
            if e.key in self.triggers:
                self.assertIn(e.value, ('yes', 'no'))
                body = self.expand(self.triggers[e.key], country, target, scope)
                result.append(Entry('AND', body, e.line) if e.value == 'yes' else
                              Entry('NOT', [Entry('AND', body, e.line)], e.line))
            elif e.key == 'any_neighbor_state':
                result.append(Entry('OR', [Entry(n, self.expand(e.value, country, target, n), e.line)
                                          for n in self.adjacency.get(scope, [])], e.line))
            else:
                key = {'ROOT': country, 'FROM': target}.get(e.key, e.key)
                if isinstance(e.value, list):
                    new_scope = key if re.fullmatch(r'[A-Z]{3}|\d+', key) else scope
                    value = self.expand(e.value, country, target, new_scope)
                else:
                    value = {'ROOT': country, 'FROM': target}.get(e.value, e.value)
                result.append(replace(e, key=key, value=value))
        return result

    def facts(self, country='STS'):
        return {
            (country, 'has_capitulated', 'no'): True,
            (country, 'is_subject', 'no'): True,
            (country, 'has_war', 'no'): True,
            (country, 'has_country_flag', 'STP_cw_won_union_battle'): True,
            (country, 'has_country_flag', 'STP_cw_postwar'): True,
            (country, 'has_global_flag', 'STP_cw_union_wars_finished'): True,
            (country, 'has_completed_focus', 'STP_pw_regional_citizenship'): True,
            **{(n, key, country): True for n in self.adjacency
               for key in ('is_owned_by', 'is_controlled_by')},
            ('1', 'is_core_of', country): True,
        }

    def eligible(self, facts, country='STS', target='2'):
        return matches_conditions(self.expand(block(self.decision(), 'available'), country, target), facts, country)

    def apply(self, callback, facts, country='STS', target='2'):
        totals = {'power': 0, 'cores': 0}
        script = self.expand(block(self.decision(), callback), country, target)
        for scope, e in selected_effects(script, facts, country):
            if e.key == 'set_variable':
                key = scalar(e.value, 'var')
                facts[scope, 'variable', key] = float(scalar(e.value, 'value'))
                facts[scope, 'has_variable', key] = True
            elif e.key == 'clear_variable':
                facts[scope, 'has_variable', e.value] = False
                facts[scope, 'variable', e.value] = 0
            elif e.key in ('set_state_flag', 'clr_state_flag'):
                facts[scope, 'has_state_flag', e.value] = e.key == 'set_state_flag'
            elif e.key == 'add_core_of':
                self.assertEqual(e.value, country)
                facts[scope, 'is_core_of', country] = True
                totals['cores'] += 1
            elif e.key == 'add_political_power':
                totals['power'] += float(e.value)
            elif e.key not in ('add_stability', 'custom_effect_tooltip', 'ADISCORD_economy_mark_dirty'):
                self.fail('Unexpected callback effect: ' + e.key)
        return totals

    def test_map_program_matches_kefreyt_cost_duration_and_repeatability(self):
        d = self.decision()
        for key, value in {'cost': '50', 'days_remove': '120', 'fire_only_once': 'no',
                           'state_target': 'yes', 'on_map_mode': 'map_and_decisions_view',
                           'cancel_if_not_visible': 'yes'}.items():
            self.assertEqual(scalar(d, key), value)
        self.assertIn('any_neighbor_state', {e.key for e in walk(block(d, 'target_trigger'))})

    def test_only_the_winning_independent_stelander_can_integrate(self):
        for country, won, peace, independent, alive in product(('STP', 'STS', 'SRP'), (False, True), (False, True), (False, True), (False, True)):
            f = self.facts(country)
            for key, value in [('has_war', peace), ('is_subject', independent), ('has_capitulated', alive)]:
                f[country, key, 'no'] = value
            f[country, 'has_country_flag', 'STP_cw_won_union_battle'] = won
            self.assertEqual(self.eligible(f, country), country in ('STP', 'STS') and won and peace and independent and alive)

    def test_noncore_owned_controlled_neighbor_chain_is_required(self):
        for country in ('STP', 'STS'):
            f = self.facts(country)
            self.assertTrue(self.eligible(f, country, '2'))
            self.assertFalse(self.eligible(f, country, '3'))
            self.assertFalse(self.eligible(f, country, '4'))
            for key in [('2', 'is_owned_by', country), ('2', 'is_controlled_by', country),
                        ('1', 'is_core_of', country), ('1', 'is_owned_by', country), ('1', 'is_controlled_by', country)]:
                changed = dict(f); changed[key] = False
                self.assertFalse(self.eligible(changed, country), key)
            f['2', 'is_core_of', country] = True
            self.assertFalse(self.eligible(f, country, '2'))
            self.assertTrue(self.eligible(f, country, '3'))

    def test_payment_locks_other_targets_and_success_opens_next_neighbor(self):
        for country in ('STP', 'STS'):
            f = self.facts(country)
            self.apply('complete_effect', f, country)
            self.assertFalse(self.eligible(f, country, '2'))
            done = self.apply('remove_effect', f, country)
            self.assertEqual(done, {'power': 0, 'cores': 1})
            self.assertTrue(self.eligible(f, country, '3'))
            self.assertEqual(self.apply('remove_effect', f, country), {'power': 0, 'cores': 0})
            self.assertEqual(self.apply('cancel_effect', f, country), {'power': 0, 'cores': 0})

    def test_war_loss_and_annexation_by_another_owner_refund_once(self):
        for country, failure in product(('STP', 'STS'), ('war', 'ownership', 'control', 'neighbor', 'already_core')):
            f = self.facts(country)
            self.apply('complete_effect', f, country)
            if failure == 'war': f[country, 'has_war', 'no'] = False
            elif failure == 'neighbor': f['1', 'is_core_of', country] = False
            elif failure == 'already_core': f['2', 'is_core_of', country] = True
            else: f['2', 'is_owned_by' if failure == 'ownership' else 'is_controlled_by', country] = False
            cancel = self.expand(block(self.decision(), 'cancel_trigger'), country)
            self.assertTrue(matches_conditions(cancel, f, country))
            for callback in ('cancel_effect', 'remove_effect'):
                copied = dict(f)
                self.assertEqual(self.apply(callback, copied, country), {'power': 50, 'cores': 0})
                self.assertEqual(self.apply('cancel_effect', copied, country), {'power': 0, 'cores': 0})
                self.assertEqual(self.apply('remove_effect', copied, country), {'power': 0, 'cores': 0})

    def test_stale_target_cannot_clear_another_projects_payment(self):
        f = self.facts()
        self.apply('complete_effect', f)
        self.assertEqual(self.apply('cancel_effect', f, target='3'), {'power': 0, 'cores': 0})
        self.assertTrue(f['STS', 'has_variable', 'STP_pw_integration_deposit'])
        self.assertEqual(self.apply('remove_effect', f), {'power': 0, 'cores': 1})

    def test_unlock_and_category_work_for_both_postwar_paths(self):
        fs = focuses(STP_FOCUS, 'STP_cw_focus')
        self.assertTrue(set(STP_NEW) <= fs.keys(), set(STP_NEW) - fs.keys())
        root = fs[STP_NEW[0]]
        alternatives = block(root, 'prerequisite')
        self.assertEqual({e.value for e in alternatives}, {'STP_pc_after_victory', 'STP_pw_party_new_republic'})
        self.assertIn('STP_pw_nationalise_region', str(block(root, 'completion_reward')))
        self.assertFalse(any(e.key == 'is_completed_by_event' for e in walk(root)))
        cat = block(entries('common/decisions/categories/ADISCORD_decision_categories_STP.txt'), 'STP_postwar_administration')
        for tag in ('STP', 'STS'):
            self.assertTrue(matches_conditions(block(cat, 'allowed'), {}, tag))
        for name in STP_NEW[1:]:
            self.assertEqual(scalar(fs[name], 'relative_position_id'), STP_NEW[0])

    def test_foreign_core_capstone_requires_actual_kefreyt_ownership(self):
        fs = focuses(STP_FOCUS, 'STP_cw_focus')
        self.assertIn(STP_NEW[-1], fs)
        gate = str(block(fs[STP_NEW[-1]], 'available'))
        for key in ('any_owned_state', 'is_core_of', 'VAL', 'is_controlled_by'):
            self.assertIn(key, gate)
        self.assertNotIn('add_core_of', {e.key for e in walk(block(fs[STP_NEW[-1]], 'completion_reward'))})


class CouncilExpansionTests(unittest.TestCase):
    def test_council_unlocks_existing_nationalisation_without_old_conquest_focus(self):
        d = block(block(entries('common/decisions/ADISCORD_VAL_decisions.txt'), 'VAL_postwar_administration'), 'VAL_nationalise_region')
        gate = block(d, 'visible')
        for old, council in product((False, True), repeat=2):
            facts = {('VAL', 'has_completed_focus', 'VAL_frontier_conference'): old,
                     ('VAL', 'has_completed_focus', VAL_NEW[0]): council,
                     ('VAL', 'VAL_regional_integration_target_valid', 'yes'): True}
            self.assertEqual(matches_conditions(gate, facts, 'VAL'), old or council)
        category = block(entries('common/decisions/categories/ADISCORD_VAL_rework_categories.txt'), 'VAL_postwar_administration')
        self.assertTrue(matches_conditions(block(category, 'visible'), {('VAL', 'has_completed_focus', VAL_NEW[0]): True}, 'VAL'))

    def test_council_has_recovery_and_peace_as_well_as_real_war_preparation(self):
        fs = focuses(VAL_FOCUS, 'VAL_defeated_focus')
        self.assertTrue(set(VAL_NEW) <= fs.keys(), set(VAL_NEW) - fs.keys())
        for name in VAL_NEW:
            self.assertTrue(block(fs[name], 'completion_reward'))
            self.assertTrue([e for e in fs[name] if e.key == 'prerequisite'])
        gate = block(entries('common/scripted_triggers/ADISCORD_VAL_rework_triggers.txt'), 'VAL_council_can_launch_revanche')
        for name in ('VAL_defeat_Mountain_Exercises', 'VAL_defeat_Frontline_Arsenals', 'VAL_defeat_Supply_For_The_Return'):
            self.assertIn(name, str(gate))
        self.assertIn('VAL_council_begin_revanche', str(fs['VAL_defeat_Return_To_The_Passes']))

    def test_neither_exclusive_path_locks_common_recovery(self):
        fs = focuses(VAL_FOCUS, 'VAL_defeated_focus')
        self.assertIn('VAL_defeat_Recovered_State', fs)
        for choice, other in [('VAL_defeat_No_Second_Expedition', 'VAL_defeat_Revise_The_Settlement'),
                              ('VAL_defeat_Revise_The_Settlement', 'VAL_defeat_No_Second_Expedition')]:
            reached = set()
            while True:
                newly = {name for name, body in fs.items() if name != other and name not in reached
                         and all(any(e.value in reached for e in p.value if e.key == 'focus')
                                 for p in body if p.key == 'prerequisite')}
                if not newly: break
                reached |= newly
            self.assertIn(choice, reached)
            self.assertTrue(set(VAL_NEW[:5]) <= reached)
            self.assertIn('VAL_defeat_Recovered_State', reached)
            self.assertEqual('VAL_defeat_Return_To_The_Passes' in reached, choice.endswith('Revise_The_Settlement'))

    def test_new_focus_coordinates_rewards_and_localisation_are_complete(self):
        for path, tree, new, loc in [(STP_FOCUS, 'STP_cw_focus', STP_NEW, 'ADISCORD_STP'),
                                    (VAL_FOCUS, 'VAL_defeated_focus', VAL_NEW, 'ADISCORD_VAL_decisions')]:
            fs = focuses(path, tree)
            self.assertTrue(set(new) <= fs.keys())
            for name in new:
                body = fs[name]
                self.assertTrue(block(body, 'completion_reward'))
                self.assertTrue(block(body, 'ai_will_do'))
                expected_filters = {
                    'STP_pw_local_officer_courses': {'FOCUS_FILTER_ARMY', 'FOCUS_FILTER_RESEARCH'},
                    'VAL_defeat_Mountain_Exercises': {'FOCUS_FILTER_ARMY'},
                    'VAL_defeat_Staff_College': {'FOCUS_FILTER_ARMY', 'FOCUS_FILTER_RESEARCH'},
                    'VAL_defeat_Technical_Institute': {'FOCUS_FILTER_RESEARCH', 'FOCUS_FILTER_INDUSTRY'},
                }
                if name in expected_filters:
                    self.assertEqual({e.value for e in block(body, 'search_filters')}, expected_filters[name])
                for lang in ('russian', 'english'):
                    p = ROOT / f'localisation/{lang}/{loc}_l_{lang}.yml'
                    self.assertTrue(p.read_bytes().startswith(b'\xef\xbb\xbf'))
                    text = p.read_text(encoding='utf-8-sig')
                    for key in (name, name+'_desc'):
                        self.assertEqual(len(re.findall(r'^ '+re.escape(key)+r':', text, re.M)), 1, key)
        fs = focuses(VAL_FOCUS, 'VAL_defeated_focus')
        positions = [(scalar(f, 'x'), scalar(f, 'y')) for f in fs.values()]
        self.assertEqual(len(positions), len(set(positions)), 'Council focuses overlap')


if __name__ == '__main__':
    unittest.main()
