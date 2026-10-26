"""Party UI and transaction contracts; these do not simulate the HOI4 engine."""

import re
import unittest
from pathlib import Path
from tools.lib.focus_sources import read_focus_source

from tools.tests.test_adiscord_stp_preparation import (
    block,
    scalar,
    walk,
    matches_conditions,
    selected_effects,
)
from tools.validators.validate_adiscord_division_templates import parse_clausewitz

ROOT = Path(__file__).resolve().parents[2]
DECISIONS = 'common/decisions/ADISCORD_STP_decisions.txt'
CATEGORIES = 'common/decisions/categories/ADISCORD_decision_categories_STP.txt'
EFFECTS = 'common/scripted_effects/ADISCORD_STP_scripted_effects.txt'
TRIGGERS = 'common/scripted_triggers/ADISCORD_STP_scripted_triggers.txt'
FOCUSES = 'common/national_focus/ADISCORD_national_focus_STP.txt'
FOREIGN = (
    'STP_ps_fund_nod',
    'STP_ps_arm_nod',
    'STP_ps_engineers_nod',
    'STP_ps_expedition_nod',
    'STP_ps_nod_dispatch',
    'STP_ps_nod_delivery',
    'STP_ps_cancel_nod',
    'STP_ps_nod_route_wait',
    'STP_ps_val_intelligence',
    'STP_ps_val_intelligence_work',
    'STP_ps_val_intercept',
    'STP_ps_val_intercept_work',
    'STP_ps_val_pressure',
    'STP_ps_val_pressure_work',
    'STP_ps_evacuate_funds',
)
GOVERNMENT = (
    'STP_ps_build_radio',
    'STP_ps_build_radio_work',
    'STP_ps_build_hq',
    'STP_ps_build_hq_work',
    'STP_ps_prepare_evacuation',
    'STP_ps_prepare_evacuation_work',
)
POLICIES = ('STP_ps_operational_reserve', 'STP_ps_route_security')


def read(path):
    return read_focus_source(ROOT / path, encoding='utf-8-sig')


def localization(language):
    return dict(
        re.findall(
            r'^ ([\w.]+):\d*\s*"((?:[^"\\]|\\.)*)"\s*$',
            read(f'localisation/{language}/ADISCORD_STP_l_{language}.yml'),
            re.M,
        )
    )


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
        cls.focuses = {
            scalar(e.value, 'id'): e.value
            for e in walk(parse_clausewitz(read(FOCUSES)))
            if e.key == 'focus' and isinstance(e.value, list)
        }

    def test_wartime_faction_selector_shows_one_payment_method_without_filtering_ai(self):
        factions = ('conservatives', 'borons', 'security', 'army',
                    'advisers', 'merchants', 'radicals')
        for war in (False, True):
            for ai in (False, True):
                for funding in (False, True):
                    facts = {
                        ('STP', 'is_ai', 'yes'): ai,
                        ('STP', 'is_ai', 'no'): not ai,
                        ('STP', 'STP_ps_war_active', 'yes'): war,
                        ('STP', 'STP_ps_war_active', 'no'): not war,
                        ('STP', 'STP_pv_war_current', 'yes'): war,
                        ('STP', 'STP_cw_preparation_open', 'yes'): not war,
                        ('STP', 'STP_pf_active', 'yes'): True,
                        ('STP', 'has_country_flag', 'STP_pf_initialized'): True,
                        ('STP', 'has_country_flag', 'STP_pm_faction_funding_selected'): funding,
                    }
                    for kind in ('funding', 'negotiations'):
                        trigger = 'STP_pm_faction_' + kind + '_visible'
                        facts[('STP', trigger, 'yes')] = matches_conditions(self.triggers[trigger], facts)
                    counts = []
                    for prefix in ('STP_pm_fund_', 'STP_pf_negotiate_'):
                        counts.append(sum(matches_conditions(
                            block(self.decisions[prefix + faction], 'visible'), facts
                        ) for faction in factions))
                    expected = [7, 7] if ai or not war else ([7, 0] if funding else [0, 7])
                    self.assertEqual(counts, expected, (war, ai, funding))

    def test_rear_programs_fold_without_changing_purchases_or_ai_access(self):
        names = ('wavering_officials', 'commissar_pay', 'front_gala', 'front_bonuses',
                 'paid_recruiters', 'smuggler_rifles', 'hired_instructors', 'widow_pensions')
        for ai in (False, True):
            for expanded in (False, True):
                facts = {
                    ('STP', 'is_ai', 'yes'): ai,
                    ('STP', 'is_ai', 'no'): not ai,
                    ('STP', 'has_country_flag', 'STP_pm_rear_programs_expanded'): expanded,
                    ('STP', 'STP_pv_war_current', 'yes'): True,
                    ('STP', 'variable', 'STP_pv_strain'): 10,
                }
                facts[('STP', 'STP_pm_rear_programs_visible', 'yes')] = matches_conditions(
                    self.triggers['STP_pm_rear_programs_visible'], facts
                )
                count = sum(matches_conditions(block(self.decisions['STP_pm_' + name], 'visible'), facts)
                            for name in names)
                self.assertEqual(count, 8 if ai or expanded else 0)
                controls = sum(matches_conditions(block(self.decisions[name], 'visible'), facts)
                               for name in ('STP_pm_show_rear_programs', 'STP_pm_hide_rear_programs'))
                self.assertEqual(controls, 0 if ai else 1)
        for name in ('STP_pm_show_rear_programs', 'STP_pm_hide_rear_programs',
                     'STP_pm_show_faction_funding', 'STP_pm_show_faction_negotiations'):
            decision = self.decisions[name]
            self.assertEqual(scalar(decision, 'cost'), '0')
            effects = [e for e in walk(block(decision, 'complete_effect')) if e.key != 'hidden_effect']
            self.assertEqual(len(effects), 1)
            self.assertIn(effects[0].key, ('set_country_flag', 'clr_country_flag'))
            self.assertIn(effects[0].value, ('STP_pm_rear_programs_expanded', 'STP_pm_faction_funding_selected'))
            for language in ('russian', 'english'):
                self.assertIn(name, localization(language))
                self.assertIn(name + '_desc', localization(language))

    def test_northern_context_hides_new_orders_but_preserves_pending_delivery(self):
        for name, program, context in (
            ('STP_ps_fund_nod', 'credit', ('STP', 'STP_ps_nod_credit_useful', 'yes')),
            ('STP_ps_arm_nod', 'arms', ('NOD', 'STP_ps_northern_front_active', 'yes')),
            ('STP_ps_engineers_nod', 'engineers', ('NOD', 'STP_ps_northern_front_active', 'yes')),
            ('STP_ps_expedition_nod', 'expedition', ('NOD', 'NOD_cw_intervention_possible', 'yes')),
        ):
            facts = {('STP', 'STP_ps_' + program + '_program_unlocked', 'yes'): True,
                     ('STP', 'STP_ps_can_aid_nod', 'yes'): True, context: True}
            visible = block(self.decisions[name], 'visible')
            self.assertTrue(matches_conditions(visible, facts))
            self.assertFalse(matches_conditions(visible, facts | {context: False}))
            self.assertFalse(matches_conditions(visible, facts | {('STP', 'STP_ps_can_aid_nod', 'yes'): False}))
        for name in ('STP_ps_nod_dispatch', 'STP_ps_nod_route_wait', 'STP_ps_nod_delivery'):
            self.assertTrue(matches_conditions(block(self.decisions[name], 'visible'),
                                              {('STP', 'has_active_mission', name): True}))

    def test_air_and_port_orders_follow_local_assets_without_hiding_prices(self):
        for name, focus, context in (
            ('STP_pm_order_fighters', 'STP_pm_factory_air_cover', 'STP_pm_air_program_available'),
            ('STP_pm_order_attack_aircraft', 'STP_pm_front_air_support', 'STP_pm_air_program_available'),
            ('STP_pm_air_sortie_order', 'STP_pm_airfield_shifts', 'STP_pm_air_program_available'),
            ('STP_pm_charter_convoys', 'STP_pm_port_workshops', 'STP_pm_port_program_available'),
            ('STP_pm_land_freight', 'STP_pm_army_freight', 'STP_pm_port_program_available'),
        ):
            facts = {('STP', 'has_completed_focus', focus): True,
                     ('STP', 'STP_ps_war_active', 'yes'): True, ('STP', context, 'yes'): True}
            visible = block(self.decisions[name], 'visible')
            self.assertTrue(matches_conditions(visible, facts))
            self.assertFalse(matches_conditions(visible, facts | {('STP', context, 'yes'): False}))
            self.assertNotIn('custom_cost_trigger', [e.key for e in walk(visible)])

    def test_northern_arms_small_package_conserves_payment_delivery_and_refund(self):
        price = block(self.decisions['STP_ps_arm_nod'], 'custom_cost_trigger')
        stocks = {'infantry_equipment': 3000, 'artillery_equipment': 25,
                  'support_equipment': 15}
        facts = {('STP', 'equipment', name): value for name, value in stocks.items()}
        facts[('STP', 'variable', 'ADISCORD_economy_treasury')] = 100
        self.assertTrue(matches_conditions(price, facts))
        for resource, balance in facts.items():
            with self.subTest(resource=resource):
                self.assertFalse(matches_conditions(price, facts | {resource: balance - 0.001}))
        for effect in ('STP_ps_refund_nod', 'STP_ps_deliver_nod'):
            equipment = {
                scalar(e.value, 'type'): int(scalar(e.value, 'amount'))
                for e in walk(self.effects[effect]) if e.key == 'add_equipment_to_stockpile'
            }
            self.assertEqual(equipment, stocks)
        payment = self.effects['STP_ps_pay_nod_arms']
        inputs = {
            scalar(e.value, 'var'): scalar(e.value, 'value')
            for e in payment if e.key == 'set_temp_variable'
        }
        self.assertEqual(inputs['STP_cw_rifle_cost'], '3000')
        self.assertEqual(inputs['STP_ps_artillery_remaining'], '25')
        self.assertEqual(inputs['STP_ps_support_remaining'], '15')
        for key, variable in (
            ('subtract_from_variable', 'ADISCORD_economy_treasury'),
            ('add_to_variable', 'ADISCORD_economy_current_month_action_costs'),
            ('set_variable', 'STP_ps_nod_receipt_money'),
        ):
            values = [scalar(e.value, 'value') for e in walk(payment)
                      if e.key == key and scalar(e.value, 'var') == variable]
            self.assertEqual(values, ['100'])

    def test_party_entry_funds_actions_and_matches_the_daily_gain_preview(self):
        reward = block(self.focuses['STP_Govern_In_His_Name'], 'completion_reward')
        self.assertEqual(scalar(reward, 'add_political_power'), '100')
        gain = [scalar(e.value, 'value') for e in walk(reward)
                if e.key == 'add_to_variable'
                and scalar(e.value, 'var') == 'STP_cw_party_political_power_gain']
        ideas = list(walk(parse_clausewitz(read('common/ideas/ADISCORD_STP_civil_war_ideas.txt'))))
        preview = next(e.value for e in ideas if e.key == 'STP_cw_presidium_mandate_delta')
        self.assertEqual(gain, [scalar(block(preview, 'modifier'), 'political_power_gain')])
        self.assertEqual(gain, ['0.50'])
        temporary = [scalar(e.value, 'value') for e in walk(reward)
                     if e.key == 'set_variable'
                     and scalar(e.value, 'var') == 'STP_cw_party_preparation_political_power_gain']
        self.assertEqual(temporary, gain)
        credit = block(self.focuses['STP_ps_northern_credit'], 'completion_reward')
        funding = [scalar(e.value, 'value') for e in walk(credit)
                   if e.key == 'add_to_variable' and scalar(e.value, 'var')
                   in ('ADISCORD_economy_treasury', 'ADISCORD_economy_current_month_action_income')]
        self.assertEqual(funding, ['300', '300'])
        self.assertIn('ADISCORD_economy_mark_dirty', [e.key for e in walk(credit)])

    def test_preparation_mandate_expires_once_without_removing_other_rewards(self):
        from tools.tests.test_adiscord_stp_party_route import PartyFactionContracts

        effect = 'STP_cw_end_party_preparation_mandate'
        aggregate = 'STP_cw_party_political_power_gain'
        temporary = 'STP_cw_party_preparation_political_power_gain'
        for permanent in (-0.05, 0, 0.15, 0.40):
            with self.subTest(permanent=permanent):
                values = {aggregate: permanent + 0.5, temporary: 0.5}
                PartyFactionContracts.simulate(self, effect, values)
                self.assertAlmostEqual(float(values[aggregate]), permanent)
                self.assertNotIn(temporary, values)
                PartyFactionContracts.simulate(self, effect, values)
                self.assertAlmostEqual(float(values[aggregate]), permanent)
        values = {}
        PartyFactionContracts.simulate(self, effect, values)
        self.assertEqual(values, {})
        for terminal in ('STP_cw_finish_elections', 'STP_cw_start',
                         'STP_cw_clear_political_modifiers'):
            self.assertIn(effect, [e.key for e in walk(self.effects[terminal])])
        for language in ('russian', 'english'):
            self.assertIn('STP_cw_presidium_mandate_duration_tt', localization(language))

    def test_election_category_stays_visible_until_the_election_is_resolved(self):
        category = self.categories['STP_elections_in_the_party']
        self.assertEqual(scalar(category, 'visible_when_empty'), 'yes')
        visible = block(category, 'visible')
        self.assertIn('STP_cw_started', str(visible))
        self.assertIn('STP_cw_elections_finished', str(visible))

    def test_military_operations_prewar_requires_an_unlocked_programme(self):
        visible = block(self.categories['STP_military_operations'], 'visible')
        prewar = {
            ('STP', 'has_country_flag', 'STP_sided_with_the_party_flag'): True,
            ('STP', 'STP_cw_preparation_open', 'yes'): True,
            ('VAL', 'exists', 'yes'): True,
        }
        self.assertFalse(matches_conditions(visible, prewar))
        programme = {
            **prewar,
            ('STP', 'STP_ps_supply_program_unlocked', 'yes'): True,
        }
        self.assertTrue(matches_conditions(visible, programme))
        self.assertTrue(matches_conditions(
            block(self.decisions['STP_ps_val_pressure'], 'visible'), programme
        ))
        self.assertFalse(matches_conditions(
            visible, {**programme, ('VAL', 'exists', 'yes'): False}
        ))
        for receipt in (
            'STP_ps_nod_receipt_type',
            'STP_ps_val_intelligence_deposit',
            'STP_ps_val_intercept_deposit',
            'STP_ps_val_pressure_deposit',
        ):
            with self.subTest(receipt=receipt):
                self.assertTrue(matches_conditions(
                    visible, {('STP', 'has_variable', receipt): True}
                ))
        for phase in ('STP_cw_participant', 'STP_cw_postwar'):
            with self.subTest(phase=phase):
                self.assertTrue(matches_conditions(
                    visible, {('STP', 'has_country_flag', phase): True}
                ))

    def test_chapter_nominee_selection_closes_all_other_choices_and_stale_callbacks(self):
        for selected in range(6):
            facts = {('STP', 'STP_ch_campaigning', 'yes'): True,
                     ('STP', 'variable', 'STP_ch_nominee'): selected}
            shown = [candidate for candidate in range(1, 6)
                     if matches_conditions(block(self.decisions[f'STP_ch_nominate_{candidate}'], 'visible'), facts)]
            self.assertEqual(shown, list(range(1, 6)) if selected == 0 else [])
            for candidate in range(1, 6):
                decision = self.decisions[f'STP_ch_nominate_{candidate}']
                self.assertEqual(matches_conditions(block(decision, 'available'), facts), selected == 0)
                writes = [entry.value for _, entry in selected_effects(block(decision, 'complete_effect'), facts)
                          if entry.key == 'set_variable' and scalar(entry.value, 'var') == 'STP_ch_nominee']
                self.assertEqual([scalar(value, 'value') for value in writes],
                                 [str(candidate)] if selected == 0 else [])

    def test_chapter_initialization_leaves_the_human_choice_open(self):
        facts = {('STP', 'STP_pf_active', 'yes'): True,
                 ('STP', 'STP_pw_can_reconstruct', 'yes'): True}
        writes = [entry.value for _, entry in selected_effects(self.effects['STP_ch_initialize'], facts)
                  if entry.key == 'set_variable' and scalar(entry.value, 'var') == 'STP_ch_nominee']
        self.assertEqual([scalar(value, 'value') for value in writes], ['0'])
        for candidate in range(1, 6):
            facts = {('STP', 'is_ai', 'yes'): True,
                     ('STP', 'variable', 'STP_ch_nominee'): candidate}
            self.assertFalse(list(selected_effects(self.effects['STP_ch_select_ai_nominee'], facts)))

    def test_chapter_agreements_cannot_record_an_unselected_nominee(self):
        for group in ('conservatives', 'borons', 'security', 'army', 'advisers', 'merchants', 'radicals'):
            decision = self.decisions['STP_ch_pledge_' + group]
            facts = {('STP', 'STP_ch_campaigning', 'yes'): True,
                     ('STP', 'variable', 'STP_ch_nominee'): 0,
                     ('STP', 'variable', f'STP_pf_{group}_support'): 100,
                     ('STP', 'numeric', 'has_political_power'): 100}
            self.assertFalse(matches_conditions(block(decision, 'visible'), facts))
            self.assertFalse(matches_conditions(block(decision, 'available'), facts))
            # The player-facing tooltip is display-only; no mechanical write may run.
            self.assertFalse([entry for _, entry in selected_effects(block(decision, 'complete_effect'), facts)
                              if entry.key != 'custom_effect_tooltip'])

    def test_chapter_agreements_appear_at_the_support_boundary_and_hide_after_signing(self):
        for group in ('conservatives', 'borons', 'security', 'army', 'advisers', 'merchants', 'radicals'):
            visible = block(self.decisions['STP_ch_pledge_' + group], 'visible')
            for support, signed, expected in ((39.999, False, False), (40, False, True),
                                               (60, False, True), (60, True, False)):
                with self.subTest(group=group, support=support, signed=signed):
                    facts = {('STP', 'STP_ch_campaigning', 'yes'): True,
                             ('STP', 'variable', 'STP_ch_nominee'): 2,
                             ('STP', 'variable', f'STP_pf_{group}_support'): support,
                             ('STP', 'has_variable', 'STP_ch_pledge_' + group): signed}
                    self.assertEqual(matches_conditions(visible, facts), expected)

    def test_chapter_preparation_keeps_paid_countdowns_visible_until_settlement(self):
        for institution in ('army', 'economy', 'party'):
            decision = self.decisions['STP_ch_train_' + institution]
            for completed, paid, expected in ((False, False, True), (False, True, True),
                                               (True, True, True), (True, False, False)):
                with self.subTest(institution=institution, completed=completed, paid=paid):
                    facts = {('STP', 'STP_ch_current', 'yes'): True,
                             ('STP', 'has_capitulated', 'no'): True,
                             ('STP', 'has_country_flag', f'STP_ch_{institution}_institution'): completed,
                             ('STP', 'has_variable', f'STP_ch_train_{institution}_deposit'): paid}
                    self.assertEqual(matches_conditions(block(decision, 'visible'), facts), expected)
                    self.assertEqual(matches_conditions(block(decision, 'available'), facts),
                                     not completed and not paid)

    def test_chapter_pressure_actions_hide_when_the_threat_closes_but_show_resource_shortages(self):
        decision = self.decisions['STP_ch_trade_delay']
        for current in (False, True):
            facts = {('STP', 'STP_ch_cold', 'yes'): True,
                     ('STP', 'STP_ch_pressure_current', 'yes'): current}
            self.assertEqual(matches_conditions(block(decision, 'visible'), facts), current)
            self.assertFalse(matches_conditions(block(decision, 'custom_cost_trigger'), facts))
            for institution in ('army', 'economy', 'party'):
                facts[('STP', 'has_country_flag', f'STP_ch_{institution}_access')] = True
                removal = self.decisions['STP_ch_remove_' + institution]
                self.assertEqual(matches_conditions(block(removal, 'visible'), facts), current)
        facts[('STP', 'has_country_flag', 'STP_ch_trade_delay_used')] = True
        self.assertFalse(matches_conditions(block(decision, 'visible'), facts))

    def test_chapter_summary_uses_three_paragraphs_in_both_languages(self):
        for language in ('russian', 'english'):
            path = ROOT / f'localisation/{language}/ADISCORD_STP_l_{language}.yml'
            self.assertTrue(path.read_bytes().startswith(b'\xef\xbb\xbf'))
            summary = localization(language)['STP_ch_chapters_desc']
            paragraphs = summary.split(r'\n\n')
            self.assertEqual(len(paragraphs), 3)
            # Stage and live pressure first, then the three foundations one per
            # line, then the congress arithmetic.
            self.assertIn('[STPGetChapterPhaseHint]', paragraphs[0])
            self.assertIn('[STPGetChapterPressureLine]', paragraphs[0])
            for area in ('Army', 'Economy', 'Party'):
                self.assertIn(f'[STPGetChapter{area}Foundation]', paragraphs[1])
            self.assertIn('[STPGetChapterNominee]', paragraphs[2])
            self.assertIn('[?STP_ch_votes_5|1]', paragraphs[2])
            line = localization(language)['STP_ch_pressure_line_1']
            self.assertIn('[STPGetChapterPressureTarget]', line)

    def test_pressure_affects_the_current_shipment_on_purchase(self):
        start = list(
            walk(block(self.decisions['STP_ps_val_pressure'], 'complete_effect'))
        )
        self.assertIn('STP_ps_val_pressure_finish', [e.key for e in start])
        self.assertNotIn(
            'STP_ps_val_pressure_work',
            [e.value for e in start if e.key == 'activate_mission'],
        )
        finish = self.effects['STP_ps_val_pressure_finish']
        extensions = [
            e.value for e in walk(finish) if e.key == 'add_days_mission_timeout'
        ]
        self.assertEqual(
            [(scalar(e, 'mission'), scalar(e, 'days')) for e in extensions],
            [('STP_ps_val_departure', '14')],
        )
        self.assertIn('STP_ps_val_pressure_cooldown', str(finish))
        self.assertIn('STP_ps_val_pressure_active', str(finish))

    def test_duplicate_recon_and_interception_cannot_charge_again(self):
        for action, marker in (
            ('STP_ps_val_intelligence', 'STP_ps_val_known_sequence'),
            ('STP_ps_val_intercept', 'STP_ps_val_intercepted_sequence'),
        ):
            gate = block(self.decisions[action], 'available')
            self.assertTrue(
                any(e.key == 'NOT' and marker in str(e.value) for e in walk(gate))
            )

    def test_nod_stale_delivery_refunds_instead_of_consuming_the_order(self):
        selected = list(
            selected_effects(
                self.effects['STP_ps_deliver_nod'],
                {
                    ('STP', 'variable', 'STP_ps_nod_receipt_stage'): 2,
                    ('STP', 'STP_ps_nod_order_current', 'yes'): False,
                },
            )
        )
        self.assertIn('STP_ps_refund_nod', [e.key for _, e in selected])
        self.assertNotIn('STP_ps_clear_nod_receipt', [e.key for _, e in selected])

    def test_nod_refund_accepts_transit_and_is_idempotent(self):
        for stage in (1, 2):
            facts = {
                ('STP', 'variable', 'STP_ps_nod_receipt_stage'): stage,
                ('STP', 'variable', 'STP_ps_receipt_type'): 2,
            }
            effects = list(selected_effects(self.effects['STP_ps_refund_nod'], facts))
            clears = [e for _, e in effects if e.key == 'STP_ps_clear_nod_receipt']
            self.assertEqual(len(clears), 1, stage)
            self.assertTrue(
                any(
                    e.key == 'add_to_variable'
                    and scalar(e.value, 'var') == 'ADISCORD_economy_treasury'
                    for _, e in effects
                )
            )
            facts[('STP', 'variable', 'STP_ps_nod_receipt_stage')] = 0
            self.assertEqual(
                list(selected_effects(self.effects['STP_ps_refund_nod'], facts)), []
            )

    def test_war_policy_is_a_real_choice_without_blocking_the_directorate(self):
        for chosen, alternative, idea in (
            (POLICIES[0], POLICIES[1], 'STP_ps_reserve_idea'),
            (POLICIES[1], POLICIES[0], 'STP_ps_route_guard_idea'),
        ):
            focus = self.focuses[chosen]
            self.assertIn(
                alternative, [e.value for e in block(focus, 'mutually_exclusive')]
            )
            self.assertIn(idea, str(block(focus, 'completion_reward')))
            self.assertIn('STP_pf_shift', str(block(focus, 'completion_reward')))
        prerequisites = [
            e.value
            for e in self.focuses['STP_party_war_directorate']
            if e.key == 'prerequisite'
        ]
        self.assertTrue(
            any(set(POLICIES).issubset({e.value for e in p}) for p in prerequisites)
        )
        self.assertEqual(
            scalar(block(self.focuses[POLICIES[1]], 'prerequisite'), 'focus'),
            'STP_cw_unified_headquarters',
        )

    def test_four_faction_focuses_do_not_also_reward_every_faction(self):
        for name in (
            'STP_GUARANTEE_MINISTERS',
            'STP_ROTATE_DISTRICT_COMMAND',
            'STP_cw_security_collegium',
            'STP_cw_capital_oath',
        ):
            reward = list(walk(block(self.focuses[name], 'completion_reward')))
            self.assertIn('STP_pf_shift', [e.key for e in reward])
            self.assertNotIn(
                'STP_change_apparatus_loyalty', [e.key for e in reward], name
            )

    def test_counter_supply_focus_identifies_a_real_current_cargo(self):
        reward = str(block(self.focuses['STP_ps_counter_supply'], 'completion_reward'))
        self.assertIn('STP_ps_val_receipt_rifles', reward)
        self.assertIn('STP_ps_val_known_sequence', reward)
        self.assertIn('STP_ps_val_sequence', reward)
        self.assertIn('add_intel', reward)
        desk = str(
            block(self.focuses['STP_ps_foreign_supply_desk'], 'completion_reward')
        )
        for action in ('intelligence', 'intercept', 'pressure'):
            self.assertIn('STP_ps_val_' + action, desk)


    def test_foreign_programmes_survive_tree_replacement_and_close_at_peace(self):
        programmes = {
            'credit': 'northern_credit',
            'arms': 'northern_arms',
            'engineers': 'northern_engineers',
            'expedition': 'expedition_logistics',
            'supply': 'foreign_supply_desk',
        }
        preserve = self.effects['STP_ps_preserve_preparation_programs']
        for kind, focus in programmes.items():
            flag = 'STP_ps_' + kind + '_program'
            trigger = self.triggers['STP_ps_' + kind + '_program_unlocked']
            for completed, retained, expected in ((False, False, False), (True, False, True),
                                                  (False, True, True), (True, True, True)):
                facts = {('STP', 'has_completed_focus', 'STP_ps_' + focus): completed,
                         ('STP', 'has_country_flag', flag): retained}
                self.assertEqual(matches_conditions(trigger, facts), expected)
                writes = [e.value for _, e in selected_effects(preserve, facts)
                          if e.key == 'set_country_flag' and e.value == flag]
                self.assertEqual(writes, [flag] if completed else [])
            self.assertIn(flag, str(self.effects['STP_cw_clear_wartime_modifiers']))
        source = read(EFFECTS)
        split = source[source.index('STP_cw_secure_party_assault_equipment = yes'):]
        self.assertLess(split.index('STP_ps_preserve_preparation_programs = yes'),
                        split.index('load_focus_tree = { tree = STP_cw_focus'))

    def test_northern_finales_offer_expedition_or_a_working_contingency(self):
        for chosen, other in (('STP_ps_expedition_logistics', 'STP_ps_asylum_protocol'),
                              ('STP_ps_asylum_protocol', 'STP_ps_expedition_logistics')):
            self.assertIn(other, [e.value for e in block(self.focuses[chosen], 'mutually_exclusive')])
            self.assertEqual(scalar(block(self.focuses[chosen], 'prerequisite'), 'focus'),
                             'STP_ps_joint_staff')
        self.assertNotIn('STP_ps_nod_can_host_exiles',
                         str(block(self.focuses['STP_ps_asylum_protocol'], 'available')))
        bypass = block(self.focuses['STP_party_northern_lesson'], 'bypass')
        self.assertTrue(matches_conditions(bypass, {('STP', 'has_idea', 'STP_cw_nodrul_collapse_eased'): True}))
        self.assertIn('STP_party_northern_lesson', str(block(self.focuses['STP_party_without_patrons'], 'prerequisite')))

    def test_northern_shock_is_once_per_war_and_contingency_changes_actual_spirit(self):
        for prepared in (False, True):
            for full, eased, overcome in ((False, False, False), (True, False, False),
                                          (False, True, False), (False, False, True)):
                facts = {('STP', 'STP_ps_war_active', 'yes'): True,
                         ('STP', 'has_country_flag', 'STP_ps_northern_contingency'): prepared,
                         ('STP', 'has_idea', 'STP_cw_nodrul_collapse'): full,
                         ('STP', 'has_idea', 'STP_cw_nodrul_collapse_eased'): eased,
                         ('STP', 'has_completed_focus', 'STP_party_northern_lesson'): overcome}
                ideas = [e.value for _, e in selected_effects(self.effects['STP_cw_party_loses_nodrul_support'], facts)
                         if e.key == 'add_ideas']
                expected = [] if full or eased or overcome else [
                    'STP_cw_nodrul_collapse_eased' if prepared else 'STP_cw_nodrul_collapse']
                self.assertEqual(ideas, expected)
        self.assertFalse([e for _, e in selected_effects(self.effects['STP_cw_party_loses_nodrul_support'], {})
                          if e.key == 'add_ideas'])
        hostilities = str(self.effects['STP_cw_begin_hostilities'])
        self.assertIn('STP_cw_northern_campaign_status', hostilities)
        self.assertIn('STP_cw_party_loses_nodrul_support', hostilities)

    def test_northern_loan_purchase_and_refund_keep_money_and_rifles_consistent(self):
        for decision, price in (('STP_ps_fund_nod', 750), ('STP_ps_nod_rifle_purchase', 750),
                                ('STP_ps_engineers_nod', 300), ('STP_ps_expedition_nod', 600),
                                ('STP_ps_val_intelligence', 150), ('STP_ps_val_intercept', 600),
                                ('STP_ps_val_pressure', 500)):
            body = self.decisions[decision]
            self.assertEqual(scalar(body, 'cost'), '0')
            for balance, affordable in ((price - 0.001, False), (price, True), (price + 0.001, True)):
                self.assertEqual(matches_conditions(block(body, 'custom_cost_trigger'),
                                 {('STP', 'variable', 'ADISCORD_economy_treasury'): balance}), affordable)
            for effect in ('subtract_from_variable', 'add_to_variable'):
                amounts = [scalar(e.value, 'value') for e in walk(block(body, 'complete_effect'))
                           if e.key == effect and scalar(e.value, 'var') in
                           ('ADISCORD_economy_treasury', 'ADISCORD_economy_current_month_action_costs')]
                self.assertEqual(amounts, [str(price)], decision)
            for language in ('russian', 'english'):
                loc = localization(language)
                for suffix in ('', '_blocked', '_tooltip'):
                    self.assertIn(str(price), loc[scalar(body, 'custom_cost_text') + suffix])
        delivery = self.effects['STP_ps_deliver_nod']
        money = [scalar(e.value, 'value') for e in walk(delivery)
                 if e.key == 'add_to_variable' and scalar(e.value, 'var') == 'ADISCORD_economy_treasury']
        self.assertEqual(money, ['750'])
        rifles = [scalar(e.value, 'amount') for e in walk(self.effects['STP_ps_nod_rifle_purchase_finish'])
                  if e.key == 'add_equipment_to_stockpile']
        self.assertEqual(rifles, ['10000'])
        for name in ('STP_ps_engineers_nod', 'STP_ps_expedition_nod'):
            extra = [scalar(e.value, 'days') for e in walk(self.decisions[name])
                     if e.key == 'add_days_mission_timeout']
            self.assertEqual(extra, ['6'])
        self.assertEqual(scalar(self.decisions['STP_ps_nod_dispatch'], 'days_mission_timeout'), '1')
        self.assertEqual(scalar(self.decisions['STP_ps_nod_delivery'], 'days_mission_timeout'), '7')

    def test_supply_desk_reward_preview_matches_party_staff_and_warning_is_conditional(self):
        reward = block(self.focuses['STP_ps_foreign_supply_desk'], 'completion_reward')
        values = [scalar(e.value, 'value') for e in walk(reward) if e.key == 'add_to_variable'
                  and scalar(e.value, 'var') == 'STP_cw_army_supply_consumption_factor']
        self.assertEqual(values, ['-0.05'])
        ideas = list(walk(parse_clausewitz(read('common/ideas/ADISCORD_STP_civil_war_ideas.txt'))))
        dummy = next(e.value for e in ideas if e.key == 'STP_ps_foreign_supply_preparation_delta')
        self.assertEqual(scalar(block(dummy, 'modifier'), 'supply_consumption_factor'), values[0])
        warning = block(self.focuses['STP_ps_northern_partner'], 'completion_reward')
        self.assertIn('STP_ps_northern_defeat_warning_tt', str(warning))
        self.assertIn('STP_cw_nodrul_collapse', str(block(warning, 'effect_tooltip')))
        self.assertFalse([e for e in warning if e.key == 'add_ideas'])

    def party_plans(self):
        return {
            entry.key: entry.value
            for entry in parse_clausewitz(read('common/ai_strategy_plans/ADISCORD_STP_plans.txt'))
            if entry.key.startswith('STP_party_')
        }

    def test_party_ai_plans_choose_one_side_and_reach_every_listed_focus(self):
        external = {
            'STP_party_preparation_plan': {'STP_Govern_In_His_Name'},
            'STP_party_reconstruction_plan': {'STP_cw_last_banquet'},
        }
        for name, plan in self.party_plans().items():
            queue = [entry.value for entry in block(plan, 'ai_national_focuses')]
            self.assertEqual(len(queue), len(set(queue)), name)
            completed = set(external.get(name, ()))
            if name.endswith('_programme_plan'):
                completed.add('STP_pw_party_new_republic')
            for focus_id in queue:
                with self.subTest(plan=name, focus=focus_id):
                    self.assertIn(focus_id, self.focuses)
                    focus = self.focuses[focus_id]
                    excluded = {
                        entry.value
                        for group in focus if group.key == 'mutually_exclusive'
                        for entry in group.value
                    }
                    self.assertFalse(excluded & set(queue))
                    for group in focus:
                        if group.key == 'prerequisite':
                            self.assertTrue(
                                completed & {entry.value for entry in group.value},
                                (focus_id, [entry.value for entry in group.value]),
                            )
                    completed.add(focus_id)

    def test_party_ai_covers_the_current_government_and_its_second_act(self):
        plans = self.party_plans()
        endings = (
            ('houses', 'STP_party_houses_compact'),
            ('festival', 'STP_party_festival_charter'),
            ('staff', 'STP_party_service_constitution'),
            ('trade', 'STP_party_trade_republic'),
            ('security', 'STP_party_security_settlement'),
            ('regent', 'STP_party_regent_settlement'),
        )
        for leader, (route, terminal) in enumerate(endings, 1):
            plan = plans[f'STP_party_{route}_programme_plan']
            enabled = block(plan, 'enable')
            self.assertEqual(scalar(enabled, f'STP_party_leader_{leader}'), 'yes')
            queue = [entry.value for entry in block(plan, 'ai_national_focuses')]
            self.assertIn(terminal, queue)
            self.assertEqual(queue[-1], f'STP_pe_{route}_ending_a')
            if leader != 6:
                self.assertIn('STP_ch_rules', [entry.value for entry in enabled
                                             if entry.key == 'has_completed_focus'])
                self.assertLess(queue.index(terminal), queue.index('STP_ch_program_settlement'))
                self.assertLess(queue.index('STP_ch_institutional_review'),
                                queue.index(f'STP_pe_{route}_opening'))
            else:
                self.assertEqual(scalar(enabled, 'STP_ch_protectorate'), 'yes')
            abort = block(plan, 'abort')
            for current, finished, expected in ((True, False, False), (False, False, True),
                                                 (True, True, True)):
                facts = {('STP', f'STP_party_leader_{leader}', 'no'): not current,
                         ('STP', 'has_completed_focus', queue[-1]): finished}
                self.assertEqual(matches_conditions(abort, facts), expected)

    def test_party_ai_prioritizes_northern_response_and_chapter_progress(self):
        plans = self.party_plans()
        queue = [entry.value for entry in block(plans['STP_party_reconstruction_plan'],
                                                'ai_national_focuses')]
        for focus in ('STP_ch_congress', 'STP_ch_cabinet', 'STP_ch_first_promises',
                      'STP_ch_rules', 'STP_ch_program_settlement', 'STP_ch_institutional_review'):
            self.assertIn(focus, queue)
        response = queue[:queue.index('STP_pw_party_sovereignty') + 1]
        days = sum(float(scalar(self.focuses[focus], 'cost')) * 7 for focus in response)
        self.assertLess(days, float(scalar(self.decisions['STP_ch_pressure_1'],
                                          'days_mission_timeout')))
        war = [entry.value for entry in block(plans['STP_party_civil_war_plan'],
                                              'ai_national_focuses')]
        self.assertLess(war.index('STP_party_northern_lesson'), war.index('STP_party_without_patrons'))


if __name__ == '__main__':
    unittest.main()
