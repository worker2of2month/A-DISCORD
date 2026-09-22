from pathlib import Path

path = Path('tools/tests/test_adiscord_stp_party_route.py')
text = path.read_text(encoding='utf-8')
assert 'class PartySecondPackageContracts' not in text
addition = r'''

class PartySecondPackageContracts(unittest.TestCase):
    """Authored-script contracts, not a native HOI4 playtest."""

    KEYS = PartyFactionContracts.KEYS
    simulate = PartyFactionContracts.simulate
    TARGETED = {
        'STP_PRESIDENT_REMAINS_IN_OFFICE': {'conservatives': 8},
        'STP_PARTY_DISCIPLINE': {'security': 10},
        'STP_EMERGENCY_PRESIDIUM': {'conservatives': 6, 'security': 6},
        'STP_THE_PARTY_CLOSES_RANKS': {'conservatives': 8, 'army': 4},
        'STP_cw_protocol_office': {'conservatives': 8},
        'STP_cw_press_office': {'radicals': 8},
        'STP_cw_party_mandate': {'conservatives': 10, 'borons': 10},
        'STP_cw_quiet_registers': {'conservatives': 10, 'borons': 6},
    }
    SPECIALIZATIONS = {
        'STP_GUARANTEE_MINISTERS': (1, -4),
        'STP_defense_budget': (2, -4),
        'STP_cw_protect_congress': (1, -3),
        'STP_cw_capital_oath': (3, -7),
    }

    @classmethod
    def setUpClass(cls):
        cls.effects = {e.key: e.value for e in parse_clausewitz(read(EFFECTS))}
        cls.triggers = {e.key: e.value for e in parse_clausewitz(read('common/scripted_triggers/ADISCORD_STP_scripted_triggers.txt'))}
        cls.focus = {one(f.value, 'id'): f.value for tree in parse_clausewitz(read(FOCUS))
                     if tree.key == 'focus_tree' for f in tree.value if f.key == 'focus'}
        cls.decisions = {d.key: d.value for c in parse_clausewitz(read(DECISIONS))
                         for d in c.value if isinstance(d.value, list)}

    def test_institutional_rewards_support_named_factions_not_everyone(self):
        for fid, targets in self.TARGETED.items():
            with self.subTest(focus=fid):
                reward = one(self.focus[fid], 'completion_reward')
                self.assertNotIn('STP_change_apparatus_loyalty', {e.key for e in walk(reward)})
                support = {one(e.value, 'var'): float(one(e.value, 'value'))
                           for e in walk(reward) if e.key == 'add_to_variable'
                           and one(e.value, 'var').endswith('_support')}
                self.assertEqual(support, {'STP_pf_' + k + '_support': v for k, v in targets.items()})
                self.assertIn('STP_refresh_apparatus_loyalty', {e.key for e in walk(reward)})

    def test_concessions_do_not_cancel_their_own_rival_penalty(self):
        for fid, selector in (('STP_GUARANTEE_MINISTERS', 1), ('STP_ROTATE_DISTRICT_COMMAND', 3), ('STP_cw_capital_oath', 4)):
            reward = one(self.focus[fid], 'completion_reward')
            self.assertNotIn('STP_change_apparatus_loyalty', {e.key for e in walk(reward)}, fid)
            self.assertEqual(sum(e.key == 'STP_pf_shift' for e in walk(reward)), 1)

    def test_strategic_courses_have_real_persistent_duration_budgets(self):
        for fid, (stage, days) in self.SPECIALIZATIONS.items():
            variable = f'STP_ps_reorg_{stage}_specialization_days'
            writes = [float(one(e.value, 'value')) for e in walk(one(self.focus[fid], 'completion_reward'))
                      if e.key == 'add_to_variable' and one(e.value, 'var') == variable]
            self.assertEqual(writes, [days], fid)
            close = str(signature(self.effects['STP_ps_close_defence']))
            self.assertIn(variable, close)
        startup = read('common/on_actions/02_ADISCORD_STP_on_actions.txt')
        self.assertNotIn('specialization_days', startup)

    def test_recovery_time_reads_current_faction_support_with_exact_boundary(self):
        for stage, faction, bonus in ((1, 'conservatives', -7), (2, 'merchants', -4), (3, 'army', -7)):
            name = f'STP_ps_adjust_reorg_{stage}'
            self.assertIn(name, self.effects)
            for support in (0, 34.999, 35, 100):
                facts = {('STP', 'STP_ps_war_active', 'yes'): True,
                         ('STP', 'has_active_mission', f'STP_ps_reorg_{stage}'): True,
                         ('STP', 'has_country_flag', 'STP_pf_initialized'): True,
                         ('STP', 'has_variable', f'STP_ps_reorg_{stage}_specialization_days'): True,
                         ('STP', 'variable', f'STP_pf_{faction}_support'): support}
                selected = list(selected_effects(self.effects[name], facts))
                delta = 0
                for scope, entry in selected:
                    if entry.key == 'add_days_mission_timeout':
                        self.assertEqual(scope, 'STP')
                        self.assertEqual(one(entry.value, 'mission'), f'STP_ps_reorg_{stage}')
                        value = one(entry.value, 'days')
                        delta += bonus if value == f'STP_ps_reorg_{stage}_specialization_days' else float(value)
                self.assertEqual(delta, bonus + (7 if support < 35 else 0))
                facts[('STP', 'STP_ps_war_active', 'yes')] = False
                self.assertFalse(list(selected_effects(self.effects[name], facts)))

    def test_time_adjustments_run_only_on_new_orders_not_load_or_resume(self):
        for stage in (1, 2, 3):
            name = f'STP_ps_adjust_reorg_{stage}'
            for mode in ('funded', 'administrative'):
                reward = one(self.decisions[f'STP_ps_reorg_{stage}_{mode}'], 'complete_effect')
                keys = [e.key for e in walk(reward)]
                self.assertEqual(keys.count(name), 1)
                self.assertLess(keys.index('activate_mission'), keys.index(name))
            self.assertNotIn(name, str(signature(self.effects['STP_ps_resume_reorganisation'])))
            self.assertNotIn(name, read('common/on_actions/02_ADISCORD_STP_on_actions.txt'))

    def test_every_faction_caps_new_concessions_without_losing_support_recovery(self):
        for faction in self.KEYS:
            for influence in (59, 59.999, 60, 65, 99, 100):
                with self.subTest(faction=faction, influence=influence):
                    values, flags = self.simulate('STP_pf_initialize')
                    other = next(k for k in self.KEYS if k != faction)
                    for key in self.KEYS:
                        values[f'STP_pf_{key}_influence'] = 0
                    values[f'STP_pf_{other}_influence'] = 100 - influence
                    values[f'STP_pf_{faction}_influence'] = influence
                    values[f'STP_pf_{faction}_support'] = 0
                    values['STP_pf_selected'] = self.KEYS.index(faction) + 1
                    self.simulate('STP_pf_shift', values, flags)
                    self.assertAlmostEqual(float(values[f'STP_pf_{faction}_influence']), min(60, influence + 5) if influence < 60 else influence)
                    self.assertEqual(values[f'STP_pf_{faction}_support'], 12)
                    self.assertAlmostEqual(float(sum(values[f'STP_pf_{k}_influence'] for k in self.KEYS)), 100)
                    self.assertTrue(all(values[f'STP_pf_{k}_influence'] >= 0 for k in self.KEYS))

    def test_recovery_keeps_all_free_paths_and_original_escrow_prices(self):
        for stage, price in ((1, 900), (2, 1800), (3, 2500)):
            free = self.decisions[f'STP_ps_reorg_{stage}_administrative']
            funded = self.decisions[f'STP_ps_reorg_{stage}_funded']
            self.assertEqual(one(free, 'cost'), '0')
            self.assertNotIn('custom_cost_trigger', {e.key for e in free})
            for phase in ('custom_cost_trigger', 'complete_effect'):
                self.assertIn(str(price), str(signature(one(funded, phase))))
            self.assertNotIn('support', str(signature(one(free, 'available'))))
            writes = [e for e in walk(one(funded, 'complete_effect')) if e.key == 'subtract_from_variable'
                      and one(e.value, 'var') == 'ADISCORD_economy_treasury']
            self.assertEqual(len(writes), 1)
            self.assertEqual(one(writes[0].value, 'value'), str(price))

    def test_strategy_tooltips_are_bilingual_and_not_a_new_decision_category(self):
        for lang in ('russian', 'english'):
            loc = dict(re.findall(r'^\s*([^#\s:]+):(?:\d+)?\s*"(.*)"\s*$', read(f'localisation/{lang}/ADISCORD_STP_l_{lang}.yml'), re.M))
            for fid in (*self.TARGETED, *self.SPECIALIZATIONS):
                key = fid + '_strategy_tt'
                self.assertIn(key, loc)
                self.assertIn(key, str(signature(one(self.focus[fid], 'completion_reward'))))
            for stage in (1, 2, 3):
                for mode in ('funded', 'administrative'):
                    self.assertIn('35', loc[f'STP_ps_reorg_{stage}_{mode}_desc'])
        categories = read('common/decisions/categories/ADISCORD_decision_categories_STP.txt')
        self.assertNotIn('STP_party_strategy', categories)

    def test_sovereignty_initializer_is_idempotent_and_does_not_depend_on_itself(self):
        start = str(signature(self.effects['STP_pw_party_start_nod_invasion_threat']))
        self.assertNotIn('STP_pw_party_sovereignty', start)
        self.assertIn('STP_pw_party_nod_threat_active', start)
        self.assertIn('STP_pw_party_nod_invasion_active', start)
        self.assertIn('STP_pw_party_nod_invasion_defeated', start)
'''
marker = "if __name__ == \"__main__\":"
if marker in text:
    text = text.replace(marker, addition + '\n\n' + marker)
else:
    text = text.rstrip() + addition
path.write_text(text.rstrip() + '\n', encoding='utf-8')
print('SECOND_PACKAGE_TESTS_INSTALLED')
