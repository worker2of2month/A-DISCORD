from pathlib import Path
import sys

TEST_PATH = Path('tools/tests/test_adiscord_stp_party_survival.py')
TESTS = r'''

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
                 'STP_ps_cancel_nod', 'STP_ps_nod_route_wait', 'STP_ps_evacuate_funds',
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
                     'STP_ps_build_hq_work', 'STP_ps_prepare_evacuation', 'STP_ps_prepare_evacuation_work'):
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
        unlocks = {e.value for e in one(focus, 'completion_reward') if e.key == 'unlock_decision_tooltip'}
        self.assertEqual(unlocks, {'STP_ps_val_intelligence', 'STP_ps_val_intercept', 'STP_ps_val_pressure'})
'''

if __name__ == '__main__':
    text = TEST_PATH.read_text(encoding='utf-8')
    assert 'class PartyUsabilityContracts' not in text
    TEST_PATH.write_text(text.rstrip() + TESTS + '\n', encoding='utf-8')
    from tools.validators.validate_adiscord_division_templates import parse_clausewitz
    text = Path('common/scripted_effects/ADISCORD_STP_scripted_effects.txt').read_text(encoding='utf-8')
    es = parse_clausewitz(text)
    lines = text.splitlines()
    for i, e in enumerate(es):
        if e.key in {'STP_ps_refresh_defence', 'STP_ps_finish_stage', 'STP_ps_val_pressure_finish'}:
            end = es[i+1].line-1 if i+1 < len(es) else len(lines)
            print('\nSOURCE ' + e.key + '\n' + '\n'.join(lines[e.line-1:end]))
