from pathlib import Path
import re
import unittest

from tools.tests.test_adiscord_stp_party_route import one
from tools.tests.test_adiscord_stp_preparation import matches_conditions, selected_effects
from tools.validators.validate_adiscord_division_templates import parse_clausewitz

ROOT = Path(__file__).resolve().parents[2]

IDEAS = ROOT / "common/ideas/ADISCORD_STP_civil_war_ideas.txt"
EFFECTS = ROOT / "common/scripted_effects/ADISCORD_STP_scripted_effects.txt"
DECISIONS = ROOT / "common/decisions/ADISCORD_STP_decisions.txt"
LOC = ROOT / "localisation/russian/ADISCORD_STP_l_russian.yml"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def named_block(text: str, name: str) -> str:
    match = re.search(r"(?m)^\s*" + re.escape(name) + r"\s*=\s*\{", text)
    if match is None:
        raise AssertionError(f"missing block {name}")
    start = match.start()
    brace = text.find("{", match.start())
    depth = 0
    for index in range(brace, len(text)):
        char = text[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start:index + 1]
    raise AssertionError(f"unterminated block {name}")


class StelanderPartyBalanceContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.ideas = read(IDEAS)
        cls.effects = read(EFFECTS)
        cls.decisions = read(DECISIONS)
        cls.loc = read(LOC)

    def test_faction_negotiations_remain_bounded_and_expensive(self) -> None:
        for faction in ("conservatives", "borons", "security", "army", "advisers", "merchants", "radicals"):
            block = named_block(self.decisions, f"STP_pf_negotiate_{faction}")
            self.assertRegex(block, r"(?m)^\s*cost\s*=\s*35\s*$")
            self.assertRegex(
                block,
                rf"check_variable\s*=\s*\{{\s*var\s*=\s*STP_pf_{faction}_influence\s+value\s*=\s*60\s+compare\s*=\s*less_than\s*\}}",
            )
            self.assertRegex(
                block,
                r"flag\s*=\s*STP_pf_negotiation_cooldown\s+value\s*=\s*1\s+days\s*=\s*30",
            )

        shift = named_block(self.effects, "STP_pf_shift")
        self.assertRegex(
            shift,
            r"set_temp_variable\s*=\s*\{\s*var\s*=\s*STP_pf_gain\s+value\s*=\s*5\s*\}",
        )
    def test_party_route_requires_staged_defensive_recovery(self) -> None:
        actions = read(ROOT / "common/on_actions/02_ADISCORD_STP_on_actions.txt")
        self.assertIn("STP_ps_begin_defence = yes", actions)
        begin = named_block(self.effects, "STP_ps_begin_defence")
        self.assertIn("NOT = { has_variable = STP_ps_stage }", begin)
        recovery = named_block(self.effects, "STP_ps_refresh_defence")
        for value in ("-0.45", "-0.3", "-0.15"):
            self.assertIn("var = STP_ps_breakthrough value = " + value, recovery)
        self.assertNotIn("army_defence_factor = -", recovery)
        self.assertNotIn("STP_cw_party_initial_disarray", self.effects)
        for stage in (1, 2, 3):
            funded = named_block(self.decisions, f"STP_ps_reorg_{stage}_funded")
            self.assertIn("STP_ps_reorg_deposit", funded)
            self.assertIn("activate_mission", funded)

    def test_congress_crisis_depends_on_the_city_and_penalizes_once(self) -> None:
        crisis = named_block(self.effects, "STP_ps_open_congress_crisis")
        self.assertIn("STP_ps_holds_congress = no", crisis)
        self.assertIn("NOT = { has_country_flag = STP_ps_congress_fell }", crisis)
        self.assertIn("add_war_support = -0.10", crisis)
        self.assertIn("add_stability = -0.15", crisis)
        self.assertIn("var = STP_apparatus_loyalty_change value = -20", crisis)
        self.assertIn("STP_change_apparatus_loyalty = yes", crisis)
        self.assertIn("STP_ps_pause_reorganisation = yes", crisis)
        banquet = named_block(self.effects, "STP_cw_resolve_last_banquet_success")
        self.assertNotIn("STP_cw_congress_fall_crisis_applied", banquet)

    def test_balance_mechanics_have_player_facing_localisation(self) -> None:
        for key in ("STP_ps_reorg_1:", "STP_ps_reorg_1_desc:",
                    "STP_ps_congress_deadline:", "STP_ps_congress_deadline_desc:"):
            self.assertIn(key, self.loc)

    def test_northern_preparation_charges_both_currencies(self) -> None:
        for action, pp, cash in (("emergency_mobilization", 50, 900),
                                 ("fortify_border", 35, 1080),
                                 ("staff_readiness", 35, 720)):
            block = named_block(self.decisions, f"STP_pw_party_nod_{action}")
            self.assertRegex(block, r"(?m)^\s*cost = 0\s*$")
            price = named_block(block, "custom_cost_trigger")
            reward = named_block(block, "complete_effect")
            self.assertIn(f"has_political_power < {pp}", price)
            self.assertIn(f"value = {cash}", price)
            self.assertEqual(reward.count(f"add_political_power = -{pp}"), 1)
            self.assertIn("STP_pw_party_nod_threat_current = yes", reward)
            key = f"STP_pw_party_nod_{action}_cost"
            for suffix in ("", "_blocked", "_tooltip"):
                self.assertIn(key + suffix + ":", self.loc)

    def test_sovereignty_dispatch_does_not_read_its_own_completion(self) -> None:
        start = named_block(self.effects, "STP_pw_party_start_nod_invasion_threat")
        self.assertNotIn("has_completed_focus = STP_pw_party_sovereignty", start)
        self.assertIn("STP_pw_party_nod_threat_active", named_block(start, "limit"))

    def test_reform_capstones_require_delivered_recovery(self) -> None:
        focus = read(ROOT / "common/national_focus/ADISCORD_national_focus_STP.txt")
        parsed = parse_clausewitz(focus)
        focuses = {one(f.value, "id"): f.value for tree in parsed
                   if tree.key == "focus_tree" for f in tree.value if f.key == "focus"}
        for fid, requirement in (("STP_pw_party_civil_charter", "STP_pw_recovery_services"),
                                 ("STP_party_technical_institutes", "STP_pw_recovery_services"),
                                 ("STP_pw_party_industrial_settlement", "STP_pw_recovery_industry")):
            self.assertIn(requirement, str(one(focuses[fid], "available")))

    def test_northern_timeout_distinguishes_war_defeat_and_absent_enemy(self) -> None:
        effect = one(parse_clausewitz(self.effects), "STP_pw_party_launch_nod_invasion")
        base = {("STP", "tag", "STP"): True,
                ("STP", "has_country_flag", "STP_pw_party_nod_threat_active"): True,
                ("NOD", "exists", "yes"): True,
                ("NOD", "has_capitulated", "no"): True,
                ("NOD", "is_subject", "no"): True}
        scenarios = [({}, "active", True),
                     ({("STP", "has_war_with", "NOD"): True}, "active", False),
                     ({("NOD", "exists", "yes"): False}, "defeated", False),
                     ({("NOD", "has_capitulated", "no"): False}, "defeated", False),
                     ({("STP", "has_capitulated", "yes"): True}, "lost", False),
                     ({("STP", "is_subject", "yes"): True}, "lost", False)]
        for changes, outcome, declaration in scenarios:
            with self.subTest(changes=changes):
                effects = list(selected_effects(effect, base | changes))
                marks = [e.value for scope, e in effects if scope == "STP" and e.key == "set_country_flag"]
                self.assertEqual(marks, ["STP_pw_party_nod_invasion_" + outcome])
                self.assertEqual(any(e.key == "declare_war_on" for _, e in effects), declaration)
        self.assertEqual(list(selected_effects(effect, base | {
            ("STP", "has_country_flag", "STP_pw_party_nod_threat_active"): False})), [])

    def test_northern_payments_reject_fractional_shortfalls(self) -> None:
        for action, pp, cash in (("emergency_mobilization", 50, 900),
                                 ("fortify_border", 35, 1080), ("staff_readiness", 35, 720)):
            parsed = one(parse_clausewitz(named_block(self.decisions, "STP_pw_party_nod_" + action)),
                         "STP_pw_party_nod_" + action)
            price = one(parsed, "custom_cost_trigger")
            for actual_pp, actual_cash, expected in ((pp, cash, True), (pp - .01, cash, False),
                                                   (pp, cash - .01, False), (pp + 1, cash + 1, True)):
                facts = {("STP", "numeric", "has_political_power"): actual_pp,
                         ("STP", "variable", "ADISCORD_economy_treasury"): actual_cash}
                self.assertEqual(matches_conditions(price, facts), expected)

    def test_prewar_settlement_eases_but_does_not_lock_postwar_course(self) -> None:
        parsed = parse_clausewitz(read(ROOT / "common/national_focus/ADISCORD_national_focus_STP.txt"))
        focuses = {one(f.value, "id"): f.value for tree in parsed
                   if tree.key == "focus_tree" for f in tree.value if f.key == "focus"}
        for fid, faction, preparation in (
                ("STP_pw_party_district_congress", "borons", "STP_party_district_compact"),
                ("STP_pw_party_executive_secretariat", "security", "STP_ROTATE_DISTRICT_COMMAND")):
            for prepared, support, expected in ((False, 49.99, False), (False, 50, True),
                                                (True, 34.99, False), (True, 35, True)):
                facts = {("STP", "STP_pw_can_reconstruct", "yes"): True,
                         ("STP", "has_completed_focus", preparation): prepared,
                         ("STP", "variable", f"STP_pf_{faction}_support"): support}
                self.assertEqual(matches_conditions(one(focuses[fid], "available"), facts), expected)
        for fid in ("STP_pw_party_northern_protocol", "STP_pw_party_protectorate"):
            self.assertTrue(matches_conditions(one(focuses[fid], "bypass"), {
                ("STP", "is_subject_of", "NOD"): True}))

    def test_ai_negotiates_for_the_pending_reform_only_until_consent(self) -> None:
        for faction, prerequisite, capstone, threshold in (
                ("borons", "STP_party_local_cadres", "STP_pw_party_district_congress", 50),
                ("security", "STP_party_chain_of_command", "STP_pw_party_executive_secretariat", 50),
                ("merchants", "STP_party_port_contracts", "STP_pw_party_commercial_recovery", 45),
                ("army", "STP_party_industrial_board", "STP_pw_party_defence_combine", 45)):
            name = "STP_pf_negotiate_" + faction
            decision = one(parse_clausewitz(named_block(self.decisions, name)), name)
            priority = next(e.value for e in one(decision, "ai_will_do")
                            if e.key == "modifier" and one(e.value, "factor") == "50")
            conditions = [e for e in priority if e.key != "factor"]
            facts = {("STP", "STP_pw_can_reconstruct", "yes"): True,
                     ("STP", "has_completed_focus", prerequisite): True,
                     ("STP", "variable", f"STP_pf_{faction}_support"): threshold - .01}
            self.assertTrue(matches_conditions(conditions, facts))
            for changes in ({("STP", "has_completed_focus", prerequisite): False},
                            {("STP", "has_completed_focus", capstone): True},
                            {("STP", "variable", f"STP_pf_{faction}_support"): threshold}):
                self.assertFalse(matches_conditions(conditions, facts | changes))

    def test_settlement_event_left_open_cannot_spend_after_charter(self) -> None:
        events = parse_clausewitz(read(ROOT / "events/ADISCORD_STP_events.txt"))
        for number in (26, 27):
            event = next(e.value for e in events if e.key == "country_event"
                         and one(e.value, "id") == f"ADISCORD_STP_pc.{number}")
            self.assertEqual(one(event, "fire_only_once"), "yes")
            options = [e.value for e in event if e.key == "option"]
            self.assertFalse(any(e.key == "trigger" for e in options[0]))
            paid = options[1]
            facts = {("STP", "STP_pw_can_reconstruct", "yes"): True,
                     ("STP", "STP_pf_active", "yes"): True,
                     ("STP", "variable", "ADISCORD_economy_treasury"): 540}
            self.assertTrue(matches_conditions(one(paid, "trigger"), facts))
            payload = [e for e in paid if e.key == "if"]
            for changes in ({("STP", "has_completed_focus", "STP_pw_party_civil_charter"): True},
                            {("STP", "variable", "ADISCORD_economy_treasury"): 539.99},
                            {("STP", "STP_pf_active", "yes"): False}):
                self.assertEqual(list(selected_effects(payload, facts | changes)), [])


class FactionProgramContracts(unittest.TestCase):
    """Execute the authored arithmetic; UI and native engine remain separate checks."""
    from tools.tests.test_adiscord_stp_party_route import PartyFactionContracts as _Fixture
    simulate = _Fixture.simulate
    KEYS = _Fixture.KEYS
    PROGRAMS = {
        'conservatives': ('STP_pw_party_civil_records', 'STP_pw_party_civil_charter'),
        'borons': ('STP_party_district_charters', 'STP_pw_party_district_congress'),
        'security': ('STP_party_personnel_commissions', 'STP_pw_party_executive_secretariat'),
        'army': ('STP_pw_party_officer_school', 'STP_pw_party_field_staff'),
        'advisers': ('STP_pw_party_nod_military_mission', 'STP_pw_party_joint_defence_board'),
        'merchants': ('STP_party_port_contracts', 'STP_pw_party_commercial_recovery'),
        'radicals': ('STP_pw_party_open_settlement', 'STP_pw_party_district_congress'),
    }
    # Actual modifier magnitudes at 20 influence and 70 support, by program level.
    EXPECTED = {
        'conservatives': (-.03, -.04, -.05), 'borons': (.03, .04, .05),
        'security': (.016, .020, .026), 'army': (.03, .04, .05),
        'advisers': (.05, .07, .09), 'merchants': (.04, .06, .08),
        'radicals': (-.05, -.07, -.09),
    }
    CAPS = {'conservatives': (.12,.15,.18), 'borons': (.12,.15,.18),
            'security': (.06,.08,.10), 'army': (.10,.13,.16),
            'advisers': (.20,.25,.30), 'merchants': (.15,.22,.30),
            'radicals': (.20,.25,.30)}
    PENALTIES = dict(zip(KEYS, (.06,.06,.03,.06,.12,.09,.09)))

    @classmethod
    def setUpClass(cls):
        from tools.tests.test_adiscord_stp_preparation import scalar, walk
        cls.effects = {e.key:e.value for e in parse_clausewitz(read(EFFECTS))}
        cls.triggers = {e.key:e.value for e in parse_clausewitz(read(ROOT/'common/scripted_triggers/ADISCORD_STP_scripted_triggers.txt'))}
        cls.focuses = {scalar(e.value,'id'):e.value for e in walk(parse_clausewitz(read(ROOT/'common/national_focus/ADISCORD_national_focus_STP.txt')))
                       if e.key=='focus' and isinstance(e.value,list)}

    def state(self, faction='army', support=70, influence=20):
        values, flags = self.simulate('STP_pf_initialize')
        for k in self.KEYS:
            values[f'STP_pf_{k}_support'] = 50
            values[f'STP_pf_{k}_influence'] = 0
        other = 'borons' if faction != 'borons' else 'army'
        values[f'STP_pf_{other}_influence'] = 100-influence
        values[f'STP_pf_{faction}_support'] = support
        values[f'STP_pf_{faction}_influence'] = influence
        return values, flags

    def test_later_focus_programs_improve_real_output_without_changing_political_shares(self):
        for faction, stages in self.PROGRAMS.items():
            for level in range(3):
                values, flags = self.state(faction)
                before = {k:v for k,v in values.items() if k.endswith(('_support','_influence'))}
                self.simulate('STP_refresh_apparatus_loyalty', values, flags, focuses=stages[:level])
                self.assertAlmostEqual(float(values[f'STP_pf_{faction}_effect']),self.EXPECTED[faction][level],places=6)
                self.assertEqual({k:v for k,v in values.items() if k in before},before)
                self.assertEqual(float(values[f'STP_pf_{faction}_program']),level)

    def test_caps_grow_with_programs_but_discontent_does_not(self):
        for faction, stages in self.PROGRAMS.items():
            for level in range(3):
                values, flags=self.state(faction,100,100)
                self.simulate('STP_refresh_apparatus_loyalty',values,flags,focuses=stages[:level],quantize=True)
                self.assertAlmostEqual(abs(float(values[f'STP_pf_{faction}_effect'])),self.CAPS[faction][level],places=3)
                values[f'STP_pf_{faction}_support']=0
                self.simulate('STP_refresh_apparatus_loyalty',values,flags,focuses=stages[:level],quantize=True)
                self.assertAlmostEqual(abs(float(values[f'STP_pf_{faction}_effect'])),self.PENALTIES[faction],places=3)
            values, flags=self.state(faction,30)
            self.simulate('STP_refresh_apparatus_loyalty',values,flags)
            penalty=values[f'STP_pf_{faction}_effect']
            self.simulate('STP_refresh_apparatus_loyalty',values,flags,focuses=stages)
            self.assertEqual(values[f'STP_pf_{faction}_effect'],penalty)

    def test_neutral_support_zero_influence_and_disconnected_advisers_have_no_bonus(self):
        for faction, stages in self.PROGRAMS.items():
            for support,influence in ((50,20),(100,0),(0,0)):
                values,flags=self.state(faction,support,influence)
                self.simulate('STP_refresh_apparatus_loyalty',values,flags,focuses=stages)
                self.assertEqual(values[f'STP_pf_{faction}_effect'],0)
        values,flags=self.state('advisers',100)
        self.simulate('STP_refresh_apparatus_loyalty',values,flags,focuses=self.PROGRAMS['advisers'],nod=False)
        self.assertEqual(values['STP_pf_advisers_effect'],0)
        self.assertEqual(values['STP_pf_advisers_support'],100)
        self.assertEqual(values['STP_pf_advisers_influence'],20)
        self.assertEqual(values['STP_pf_nod_connected'],0)

    def test_focus_reward_applies_before_its_completion_flag_without_persistent_unlock_flags(self):
        from tools.tests.test_adiscord_stp_preparation import walk, scalar
        for faction,stages in self.PROGRAMS.items():
            for level,fid in enumerate(stages,1):
                reward=one(self.focuses[fid],'completion_reward')
                calls=[e for e in walk(reward) if e.key=='STP_pf_apply_focus_program']
                self.assertEqual(len(calls),1,fid)
                pending=[e for e in walk(reward) if e.key=='set_temp_variable' and scalar(e.value,'var')=='STP_pf_finishing_program']
                self.assertEqual(len(pending),1,fid)
                values,flags=self.state(faction)
                values['STP_pf_finishing_program']=scalar(pending[0].value,'value')
                self.simulate('STP_pf_apply_focus_program',values,flags)
                self.assertEqual(float(values[f'STP_pf_{faction}_program']),level)
                self.assertAlmostEqual(float(values[f'STP_pf_{faction}_effect']),self.EXPECTED[faction][level],places=6)
                self.assertEqual(values['STP_pf_finishing_program'],0)
                self.simulate('STP_refresh_apparatus_loyalty',values,flags,focuses=stages[:level])
                self.assertEqual(float(values[f'STP_pf_{faction}_program']),level)
        authored=' '.join(str(self.effects[n]) for n in ('STP_pf_refresh_programs','STP_pf_apply_focus_program'))
        self.assertNotIn('set_country_flag',authored)
        self.assertNotIn('set_global_flag',authored)

    def test_program_receipt_survives_other_effects_in_the_same_focus_reward(self):
        from tools.tests.test_adiscord_stp_preparation import walk
        for fid in {fid for group in self.PROGRAMS.values() for fid in group}:
            payload = list(walk(one(self.focuses[fid], 'completion_reward')))
            calls = [e.key for e in payload if e.key.startswith('STP_pf_') or e.key == 'STP_refresh_apparatus_loyalty']
            self.assertTrue(calls, fid)
            self.assertEqual(calls[-1], 'STP_pf_apply_focus_program', fid)

    def test_fortress_and_field_armies_both_receive_the_military_program(self):
        for fid in ('STP_pw_party_field_staff','STP_pw_party_fortress_corps'):
            values,flags=self.state('army')
            self.simulate('STP_refresh_apparatus_loyalty',values,flags,focuses=(fid,))
            self.assertIn('STP_pf_army_program', values)
            self.assertEqual(values['STP_pf_army_program'],2)
            self.assertAlmostEqual(float(values['STP_pf_army_effect']),.05,places=6)

    def test_startup_refresh_preserves_old_campaign_and_cleanup_removes_program_caches(self):
        from tools.tests.test_adiscord_stp_preparation import walk
        actions=one(parse_clausewitz(read(ROOT/'common/on_actions/02_ADISCORD_STP_on_actions.txt')),'on_actions')
        self.assertTrue(any(e.key=='STP_pf_refresh_on_load' for e in walk(one(actions,'on_startup'))))
        values,flags=self.state('army',73,28)
        before={k:v for k,v in values.items() if k.endswith(('_support','_influence'))}
        self.assertIn('STP_pf_refresh_on_load',self.effects)
        for _ in range(2):
            self.simulate('STP_pf_refresh_on_load',values,flags,focuses=self.PROGRAMS['army'])
            self.assertEqual({k:v for k,v in values.items() if k in before},before)
            self.assertEqual(values['STP_pf_army_program'],2)
        self.simulate('STP_pf_clear',values,flags)
        self.assertFalse(any(k.endswith(('_program','_capacity')) and k.startswith('STP_pf_') for k in values))
        for node in actions:
            if node.key!='on_startup':
                self.assertFalse(any(e.key=='STP_pf_refresh_on_load' for e in walk(node.value)))

    def test_bonus_artwork_aliases_resolve_bundled_stat_symbols(self):
        gfx = read(ROOT / 'interface/ADISCORD_STP_regions.gfx')
        for sprite, path in (
                ('GFX_STP_pf_stability_effect', 'gfx/interface/stability_icon.dds'),
                ('GFX_STP_pf_organization_effect', 'gfx/texticons/organization_gain_texticon.dds')):
            self.assertIn('name = "' + sprite + '"', gfx)
            self.assertIn('texturefile = "' + path + '"', gfx)
            self.assertTrue((ROOT / path).is_file(), path)

    def test_card_bonus_icons_and_values_fit_below_emblems_and_read_actual_modifier_variables(self):
        from tools.tests.test_adiscord_stp_preparation import walk,scalar
        gui=next(e.value for e in walk(parse_clausewitz(read(ROOT/'interface/ADISCORD_STP_regions.gui')))
                 if e.key=='containerWindowType' and scalar(e.value,'name')=='ADISCORD_STP_party_factions_window')
        widgets={scalar(e.value,'name'):e.value for e in gui if isinstance(e.value,list) and any(x.key=='name' for x in e.value)}
        consumers=one(parse_clausewitz(read(ROOT/'common/dynamic_modifiers/ADISCORD_dynamic_modifiers_STP.txt')),'STP_pf_balance_dynamic')
        for faction in self.KEYS:
            base='STP_pf_'+faction
            self.assertIn(base+'_effect_icon',widgets)
            self.assertIn(base+'_effect_value',widgets)
            icon,text,emblem,card=[widgets[base+s] for s in ('_effect_icon','_effect_value','_emblem','_card')]
            for widget in (icon,text):
                y=float(scalar(one(widget,'position'),'y'))
                self.assertGreaterEqual(y,float(scalar(one(emblem,'position'),'y'))+56)
                self.assertLessEqual(y+20,float(scalar(one(card,'position'),'y'))+92)
                self.assertEqual(scalar(widget,'pdx_tooltip'),base+'_tt')
            self.assertTrue(any(e.value==base+'_effect' for e in consumers))
            for language in ('russian','english'):
                loc=read(ROOT/f'localisation/{language}/ADISCORD_STP_l_{language}.yml')
                self.assertRegex(loc,rf'(?m)^ {base}_effect_value:.*\[\?{base}_effect\|=')
                self.assertIn(base+'_program',loc)
                for fid in self.PROGRAMS[faction]:self.assertIn('$'+fid+'$',loc)
        for language in ('russian','english'):
            loc=read(ROOT/f'localisation/{language}/ADISCORD_STP_l_{language}.yml')
            self.assertIn('STP_pf_advisers_disconnected',loc)

if __name__ == "__main__":
    unittest.main()
