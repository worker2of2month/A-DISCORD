from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import os, re, signal, subprocess, sys, json

ROOT = Path.cwd()
sys.path.insert(0, str(ROOT))
from tools.tests.test_val_contract_ui import named_block

OUT = Path('.superpowers/observer-val-inspection')
REPORT = {'base': '0c52cb91cd23bf0a29ca3ee7c264eee35ec978a5', 'checks': {}}
BRANCH = 'fix/observer-val-progression'

def run(name, command, timeout=120):
    path = OUT / (name + '.log')
    with path.open('w') as log:
        p = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT, text=True, start_new_session=True)
        try:
            code = p.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            os.killpg(p.pid, signal.SIGKILL)
            p.wait()
            code = 124
    text = path.read_text(errors='replace')
    problems = re.findall(r'(?m)^(?:FAIL|ERROR): .+$', text)
    partial = re.findall(r'(?m)^test_[^\n]+\.\.\. (?:FAIL|ERROR)\s*$', text)
    result = {'returncode': code, 'problems': problems, 'partial_problems': partial,
              'summary': text[-15000:], 'lines': len(text.splitlines())}
    REPORT['checks'][name] = result
    print(name, code, text[-2000:], flush=True)
    return result

def replace_once(text, old, new):
    assert text.count(old) == 1, (old[:100], text.count(old))
    return text.replace(old, new, 1)

def source(path):
    return Path(path).read_bytes().decode('utf-8')

def write(path, text):
    Path(path).write_bytes(text.encode('utf-8'))

def focus(text, name):
    markers = list(re.finditer(rf'\bid\s*=\s*{re.escape(name)}\b', text))
    assert len(markers) == 1, name
    starts = list(re.finditer(r'(?m)^[ \t]*focus\s*=\s*\{', text[:markers[0].start()]))
    return named_block(text[starts[-1].start():], 'focus')

def identified_block(text, kind, key, name):
    for m in re.finditer(rf'(?m)^[ \t]*{kind}\s*=\s*\{{', text):
        body = named_block(text[m.start():], kind)
        if re.search(rf'\b{key}\s*=\s*{re.escape(name)}\b', body):
            return body
    raise AssertionError(name)

def loc_value(text, key, value=None, suffix=''):
    pattern = re.compile(rf'(?m)^ {re.escape(key)}:[^\r\n]*$')
    found = list(pattern.finditer(text))
    assert len(found) == 1, (key, len(found))
    line = found[0].group()
    first, last = line.index('"'), line.rindex('"')
    old = line[first+1:last]
    return replace_once(text, line, line[:first+1] + (old + suffix if value is None else value) + line[last:])

FOCUS = 'common/national_focus/ADISCORD_national_focus_VAL.txt'
VE = 'common/scripted_effects/ADISCORD_VAL_effects.txt'
VT = 'common/scripted_triggers/ADISCORD_VAL_rework_triggers.txt'
VD = 'common/decisions/ADISCORD_VAL_decisions.txt'
VO = 'common/on_actions/02_ADISCORD_VAL_rework_on_actions.txt'
VC = 'common/decisions/categories/ADISCORD_VAL_rework_categories.txt'
EV = 'events/ADISCORD_VAL_contract_events.txt'
SE = 'common/scripted_effects/ADISCORD_vorkerland_effects.txt'
OA = 'common/on_actions/00_ADISCORD_on_actions.txt'
TESTS = ['tools/tests/test_adiscord_superevents_stp_empire.py', 'tools/tests/test_val_contract_ui.py']
LOCS = [f'localisation/{lang}/ADISCORD_VAL_decisions_l_{lang}.yml' for lang in ('russian', 'english')]
PATHS = [FOCUS, VE, VT, VD, VO, VC, EV, SE, OA, *TESTS, *LOCS]
REGRESSION = ['python', '-B', '-m', 'unittest', 'tools.tests.test_adiscord_superevents_stp_empire.SupereventObserverTests', 'tools.tests.test_val_contract_ui.TestValProgression', '-v']
FOCUSED = ['python', '-B', '-m', 'unittest', 'tools.tests.test_adiscord_superevents_stp_empire', 'tools.tests.test_val_contract_ui', '-v']

try:
    # Keep failing-test diagnostics bounded; assertions still exercise the same contracts.
    path = TESTS[0]
    text = source(path)
    text = text.replace("self.assertIn('ADISCORD_superevent_observer_tick', definitions)", "self.assertTrue('ADISCORD_superevent_observer_tick' in definitions, 'missing observer timeout effect')")
    write(path, text)
    path = TESTS[1]
    text = source(path)
    addition = '''    def test_event_withdrawal_uses_the_same_deferral_and_revalidates_its_quote(self):
        events = read('events/ADISCORD_VAL_contract_events.txt')
        position = events.index('name = val_rework.111.withdraw')
        start = events.rfind('option = {', 0, position)
        option = named_block(events[start:], 'option')
        hidden = named_block(option, 'hidden_effect')
        self.assertIn('VAL_defer_frontier_expansion = yes', hidden)
        self.assertIn('VAL_frontier_reply_is_current = yes', named_block(hidden, 'limit'))
        self.assertIn('custom_effect_tooltip = VAL_frontier_withdraw_tt', option)

'''
    text = replace_once(text, 'class TestValProgression(unittest.TestCase):\n', 'class TestValProgression(unittest.TestCase):\n' + addition)
    old_ai_test = text[text.index('    def test_ai_can_withdraw_when_unready'):text.index('    def test_deferral_and_map_proclamation')]
    new_ai_test = """    def test_ai_can_withdraw_when_unready_and_prefers_a_viable_northern_campaign_when_ready(self):
        from tools.tests.test_adiscord_stp_preparation import block, scalar, matches_conditions
        _, _, decisions, _ = self.data()
        withdrawal = block(block(decisions, 'VAL_frontier'), 'VAL_frontier_withdraw_demand')
        ai = block(withdrawal, 'ai_will_do')
        base = float(scalar(ai, 'base'))
        self.assertGreater(base, 0)
        for stage in (0, 2):
            for ready in (False, True):
                for viable in (False, True):
                    facts = {('VAL', 'VAL_ai_frontier_force_ready', 'yes'): ready,
                             ('VAL', 'variable', 'VAL_frontier_stage'): stage,
                             ('VAL', 'VAL_frontier_idle', 'yes'): stage == 0,
                             ('VAL', 'VAL_frontier_prewar_eligible', 'yes'): stage == 2 and viable,
                             ('CIN', 'VAL_frontier_bloc_target_eligible', 'yes'): viable if stage == 0 else True}
                    weight = base
                    for modifier in [e.value for e in ai if e.key == 'modifier']:
                        if matches_conditions([e for e in modifier if e.key != 'factor'], facts, 'VAL'):
                            weight *= float(scalar(modifier, 'factor'))
                    self.assertEqual(weight > 0, not (ready and viable), (stage, ready, viable))

"""
    text = replace_once(text, old_ai_test, new_ai_test)
    text = replace_once(text, "('VAL', 'VAL_frontier_idle', 'yes'): idle}", "('VAL', 'VAL_frontier_idle', 'yes'): idle, ('VAL', 'has_completed_focus', 'VAL_frontier_security_plan'): True}")
    write(path, text)
    red = run('regression_red_compact', REGRESSION)
    assert red['returncode'] == 1 and red['problems'] and not any(p.startswith('ERROR:') for p in red['problems'])
    # The complete first RED transcript is kept in the run log, not in the deliverable.
    previous_red = (OUT/'regression-red.txt').read_text()
    REPORT['initial_red_failures'] = re.findall(r'(?m)^FAIL: .+$', previous_red)
    (OUT/'regression-red.txt').write_text('\n'.join(REPORT['initial_red_failures']) + '\n' + previous_red[-500:])

    # Global observer timeout follows existing flag dates and the FIFO dispatcher.
    flags = list(dict.fromkeys(re.findall(r'has_global_flag = (superevent_\w+)', source('common/scripted_guis/superevents.txt'))))
    assert len(flags) == 11
    expired = '\n'.join(f'\t\t\t\thas_global_flag = {{ flag = {flag} days > 6 }}' for flag in flags)
    cleanup = '\n'.join(f'\t\tif = {{\n\t\t\tlimit = {{ has_global_flag = {{ flag = {flag} days > 6 }} }}\n\t\t\tclr_global_flag = {flag}\n\t\t}}' for flag in flags)
    observer = '''# on_daily is country-scoped. The shared one-day latch admits only one caller.
# Existing presentation flag ages survive saves, early clicks and country annexation.
# A human country prevents global dismissal in mixed multiplayer sessions.
ADISCORD_superevent_observer_tick = {
\tset_global_flag = { flag = ADISCORD_superevent_observer_day_checked days = 1 }
\tif = {
\t\tlimit = {
\t\t\tOR = {
''' + expired + '''
\t\t\t}
\t\t\tNOT = { any_country = { is_ai = no } }
\t\t}
''' + cleanup + '''
\t\tADISCORD_superevent_dispatch_next = yes
\t}
}

'''
    text = source(SE)
    text = replace_once(text, '# Requests and button clicks are the only dispatch points; no periodic polling.', '# Player clicks and the guarded observer timeout advance the queue.')
    text = replace_once(text, 'ADISCORD_superevent_enqueue = {', observer + 'ADISCORD_superevent_enqueue = {')
    write(SE, text)
    text = source(OA)
    assert not re.search(r'(?m)^\s*on_daily\s*=', text)
    daily = '''\ton_daily = {
\t\teffect = {
\t\t\tif = {
\t\t\t\tlimit = { NOT = { has_global_flag = ADISCORD_superevent_observer_day_checked } }
\t\t\t\tADISCORD_superevent_observer_tick = yes
\t\t\t}
\t\t}
\t}
'''
    text = replace_once(text, '\ton_weekly = {', daily + '\ton_weekly = {')
    write(OA, text)

    # One explicit choice closes an unstarted/refused campaign, not a live war.
    text = source(VT)
    defer_gate = '''# COUNTRY VAL: withdraw a refused demand or defer it before issuing one.
VAL_can_defer_frontier_expansion = {
\ttag = VAL
\tVAL_frontier_postwar = yes
\thas_war = no
\tOR = {
\t\tcheck_variable = { var = VAL_frontier_stage value = 2 compare = equals }
\t\tAND = {
\t\t\tVAL_frontier_idle = yes
\t\t\thas_completed_focus = VAL_frontier_security_plan
\t\t\tNOT = { has_completed_focus = VAL_frontier_treaty_offices }
\t\t\tNOT = { has_country_flag = VAL_frontier_treaty_signed }
\t\t\tNOT = { has_country_flag = VAL_frontier_expansion_deferred }
\t\t}
\t}
}

'''
    text = replace_once(text, 'VAL_frontier_offer_is_current = {', defer_gate + 'VAL_frontier_offer_is_current = {')
    write(VT, text)
    text = source(VE)
    closing = named_block(text, 'VAL_frontier_close')
    defer_effect = '''

# The deferral authorizes a focus bypass, never a successful territorial settlement.
VAL_defer_frontier_expansion = {
\tif = {
\t\tlimit = { VAL_can_defer_frontier_expansion = yes }
\t\tif = {
\t\t\tlimit = {
\t\t\t\tNOT = { has_country_flag = VAL_frontier_treaty_signed }
\t\t\t\tNOT = { has_completed_focus = VAL_frontier_treaty_offices }
\t\t\t}
\t\t\tset_country_flag = VAL_frontier_expansion_deferred
\t\t}
\t\tif = {
\t\t\tlimit = { check_variable = { var = VAL_frontier_stage value = 2 compare = equals } }
\t\t\tVAL_frontier_close = yes
\t\t}
\t}
}
'''
    text = replace_once(text, closing, closing + defer_effect)
    portrait_sync = '''# Reconcile presentation from the actual formable, including pre-proclamation saves.
VAL_sync_solgalov_portrait = {
\tif = {
\t\tlimit = { has_character = VAL_Valera_Solgalov }
\t\tif = {
\t\t\tlimit = { has_cosmetic_tag = VAL_commonwealth }
\t\t\tset_portraits = {
\t\t\t\tcharacter = VAL_Valera_Solgalov
\t\t\t\tcivilian = { large = GFX_portrait_VAL_Valera_Solgalov_contracts }
\t\t\t}
\t\t}
\t\telse = {
\t\t\tset_portraits = {
\t\t\t\tcharacter = VAL_Valera_Solgalov
\t\t\t\tcivilian = { large = GFX_portrait_VAL_Valera_Solgalov }
\t\t\t}
\t\t}
\t}
}

'''
    text = replace_once(text, 'VAL_adopt_commonwealth = {', portrait_sync + 'VAL_adopt_commonwealth = {')
    adoption = named_block(text, 'VAL_adopt_commonwealth')
    text = replace_once(text, adoption, replace_once(adoption, '        set_cosmetic_tag = VAL_commonwealth', '        set_cosmetic_tag = VAL_commonwealth\n        VAL_sync_solgalov_portrait = yes'))
    write(VE, text)
    text = source(VO)
    text = replace_once(text, '\t\t\t\t\tVAL_grant_contract_warlord = yes', '\t\t\t\t\tVAL_grant_contract_warlord = yes\n\t\t\t\t\tVAL_sync_solgalov_portrait = yes')
    write(VO, text)

    text = source(FOCUS)
    old = focus(text, 'VAL_Contracts_Outlive_Kings')
    portrait = '''\t\t\t\tif = {
\t\t\t\t\tlimit = { has_character = VAL_Valera_Solgalov }
\t\t\t\t\tset_portraits = {
\t\t\t\t\t\tcharacter = VAL_Valera_Solgalov
\t\t\t\t\t\tcivilian = { large = GFX_portrait_VAL_Valera_Solgalov_contracts }
\t\t\t\t\t}
\t\t\t\t}
'''
    text = replace_once(text, old, replace_once(old, portrait, ''))
    old = focus(text, 'VAL_frontier_treaty_offices')
    prerequisite = '        prerequisite = { focus = VAL_frontier_security_plan }'
    bypass = '''
        bypass = {
            custom_trigger_tooltip = {
                tooltip = VAL_frontier_deferred_tt
                has_country_flag = VAL_frontier_expansion_deferred
                has_completed_focus = VAL_frontier_security_plan
                VAL_frontier_idle = yes
            }
        }'''
    text = replace_once(text, old, replace_once(old, prerequisite, prerequisite+bypass))
    old = focus(text, 'VAL_frontier_security_plan')
    unlock = '            unlock_decision_tooltip = { decision = VAL_frontier_demand_CIN show_effect_tooltip = yes }'
    text = replace_once(text, old, replace_once(old, unlock, unlock+'\n            unlock_decision_tooltip = { decision = VAL_frontier_withdraw_demand show_effect_tooltip = yes }'))
    write(FOCUS, text)

    text = source(VD)
    old = named_block(text, 'VAL_frontier_withdraw_demand')
    withdrawal = '''
    VAL_frontier_withdraw_demand = {
        icon = generic_political_pressure
        allowed = { tag = VAL }
        visible = {
            OR = {
                check_variable = { var = VAL_frontier_stage value = 2 compare = equals }
                AND = {
                    has_completed_focus = VAL_frontier_security_plan
                    NOT = { has_completed_focus = VAL_frontier_treaty_offices }
                    NOT = { has_country_flag = VAL_frontier_treaty_signed }
                    NOT = { has_country_flag = VAL_frontier_expansion_deferred }
                }
            }
        }
        available = {
            custom_trigger_tooltip = { tooltip = VAL_frontier_can_defer_tt VAL_can_defer_frontier_expansion = yes }
        }
        cost = 0
        complete_effect = {
            custom_effect_tooltip = VAL_frontier_withdraw_tt
            hidden_effect = { VAL_defer_frontier_expansion = yes }
        }
        ai_will_do = {
            base = 25
            modifier = {
                factor = 0
                VAL_ai_frontier_force_ready = yes
                OR = {
                    AND = {
                        check_variable = { var = VAL_frontier_stage value = 2 compare = equals }
                        VAL_frontier_prewar_eligible = yes
                    }
                    AND = {
                        VAL_frontier_idle = yes
                        OR = {
                            CIN = { VAL_frontier_bloc_target_eligible = yes }
                            OSF = { VAL_frontier_bloc_target_eligible = yes }
                            APH = { VAL_frontier_bloc_target_eligible = yes }
                        }
                    }
                }
            }
        }
    }'''
    text = replace_once(text, old, withdrawal)
    old = named_block(text, 'VAL_proclaim_commonwealth')
    new = replace_once(old, '\t\tallowed = { tag = VAL }', '''\t\tallowed = { tag = VAL }
\t\tstate_target = yes
\t\ttarget_trigger = { FROM = { is_owned_by = ROOT is_capital = yes } }
\t\ton_map_mode = map_and_decisions_view
\t\thighlight_states = {
\t\t\thighlight_state_targets = {
\t\t\t\tOR = {
\t\t\t\t\tstate = FROM
\t\t\t\t\tis_core_of = STP
\t\t\t\t\tstate = 29
\t\t\t\t\tstate = 46
\t\t\t\t\tstate = 58
\t\t\t\t\tstate = 59
\t\t\t\t\tstate = 60
\t\t\t\t\tstate = 61
\t\t\t\t\tstate = 62
\t\t\t\t\tstate = 63
\t\t\t\t\tstate = 64
\t\t\t\t\tstate = 65
\t\t\t\t\tstate = 10
\t\t\t\t\tstate = 11
\t\t\t\t\tstate = 12
\t\t\t\t\tstate = 13
\t\t\t\t\tstate = 17
\t\t\t\t\tstate = 18
\t\t\t\t\tstate = 30
\t\t\t\t}
\t\t\t}
\t\t}''')
    new = replace_once(new, '\t\tvisible = { NOT = { has_cosmetic_tag = VAL_commonwealth } }', '\t\tvisible = { has_completed_focus = VAL_Contracts_Outlive_Kings NOT = { has_cosmetic_tag = VAL_commonwealth } }')
    text = replace_once(text, old, new)
    write(VD, text)
    text = source(VC)
    old = named_block(text, 'VAL_postwar_administration')
    new = replace_once(old, 'visible = { has_completed_focus = VAL_frontier_conference }', 'visible = { OR = { has_completed_focus = VAL_frontier_conference has_completed_focus = VAL_Contracts_Outlive_Kings } }')
    write(VC, replace_once(text, old, new))

    text = source(EV)
    event = identified_block(text, 'country_event', 'id', 'val_rework.111')
    old = identified_block(event, 'option', 'name', 'val_rework.111.withdraw')
    new = replace_once(old, 'VAL_frontier_close = yes', 'VAL_defer_frontier_expansion = yes')
    new = replace_once(new, '\t\thidden_effect = {', '\t\tcustom_effect_tooltip = VAL_frontier_withdraw_tt\n\t\thidden_effect = {')
    new = replace_once(new, 'limit = { check_variable = { var = VAL_frontier_stage value = 2 compare = equals } }', 'limit = { check_variable = { var = VAL_frontier_stage value = 2 compare = equals } VAL_frontier_reply_is_current = yes }')
    write(EV, replace_once(text, event, replace_once(event, old, new)))

    translations = {
        'russian': {
            'VAL_frontier_withdraw_demand': 'Отложить северную экспансию',
            'VAL_frontier_withdraw_demand_desc': 'Отозвать уже отклонённые требования или отложить северные ультиматумы до их отправки. Если пограничный договор ещё не заключён, фокус «$VAL_frontier_treaty_offices$» будет пропущен без наград: можно продолжить подготовку против Нодрула и Стеландера. Северные решения останутся доступны; для ресурсных наград и Содружества по-прежнему нужны реальные территории. Во время переговоров или войны это решение недоступно. Оплаченная подготовка не возмещается, срок повторного ультиматума не сбрасывается.',
            'VAL_frontier_deferred_tt': 'Северная экспансия отложена отдельным решением; активный пограничный кризис завершён',
            'VAL_frontier_can_defer_tt': 'Кефрейт независим, не капитулировал, не потерпел окончательного поражения от Стеландера и находится в мире. Можно отозвать отклонённый ультиматум либо после плана пограничной безопасности отложить ещё не начатую экспансию, пока договор не заключён и фокус его исполнения не завершён.',
            'withdraw_suffix': ' Если договор ещё не заключён, фокус «$VAL_frontier_treaty_offices$» будет пропущен без наград. Территории, ресурсные награды и условия Содружества этим не выдаются и не отменяются.',
            'treaty_suffix': r'\n\nЧтобы продолжить без предварительной северной экспансии, используйте «$VAL_frontier_withdraw_demand$» в разделе «$VAL_frontier$». Этот фокус будет пропущен без наград; решения против Нодрула и Стеландера можно открыть следующими фокусами. Реальное владение севером по-прежнему требуется для ресурсных наград и провозглашения Содружества.',
            'portrait_suffix': ' Портрет Валеры Сольгалова сменится именно при успешном провозглашении, а не при открытии решения.',
            'map_suffix': r'\n\nРешение отмечено в текущей столице Кефрейта. Наведите на него курсор, чтобы подсветить регионы из территориальных требований; невыполненные условия не скрывают решение.'
        },
        'english': {
            'VAL_frontier_withdraw_demand': 'Defer Northern Expansion',
            'VAL_frontier_withdraw_demand_desc': 'Withdraw rejected demands or defer northern ultimatums before issuing them. Without a concluded frontier treaty, $VAL_frontier_treaty_offices$ is bypassed without rewards, allowing preparations against Nodrul and Stelander to continue. Northern decisions remain available; resource rewards and the Commonwealth still require the actual territories. This decision is unavailable during negotiations or war. Preparation costs are not refunded and the ultimatum cooldown is not reset.',
            'VAL_frontier_deferred_tt': 'Northern expansion was explicitly deferred and the active frontier crisis has ended',
            'VAL_frontier_can_defer_tt': 'Kefreyt is independent, has not capitulated or suffered its final defeat by Stelander, and is at peace. Withdraw a rejected ultimatum, or defer an unstarted expansion after the frontier security plan while no treaty is signed and its implementation focus remains unfinished.',
            'withdraw_suffix': ' Without a concluded treaty, $VAL_frontier_treaty_offices$ is bypassed without rewards. This neither grants territories or resource rewards nor waives the Commonwealth requirements.',
            'treaty_suffix': r'\n\nTo continue without preliminary northern expansion, use $VAL_frontier_withdraw_demand$ in $VAL_frontier$. This focus is bypassed without rewards; subsequent focuses can still authorize operations against Nodrul and Stelander. Actual northern ownership remains necessary for resource rewards and the Commonwealth proclamation.',
            'portrait_suffix': " Valera Solgalov's portrait changes upon the successful proclamation, not when the decision is unlocked.",
            'map_suffix': r"\n\nThe decision is marked in Kefreyt's current capital. Hover over it to highlight the states covered by territorial requirements; unmet conditions do not hide the decision."
        }
    }
    for language, values in translations.items():
        path = f'localisation/{language}/ADISCORD_VAL_decisions_l_{language}.yml'
        text = source(path)
        assert text.startswith('\ufeff')
        for key in ('VAL_frontier_withdraw_demand', 'VAL_frontier_withdraw_demand_desc'):
            text = loc_value(text, key, value=values[key])
        text = loc_value(text, 'VAL_frontier_withdraw_tt', suffix=values['withdraw_suffix'])
        text = loc_value(text, 'VAL_frontier_treaty_offices_desc', suffix=values['treaty_suffix'])
        text = loc_value(text, 'VAL_commonwealth_proclaimed_tt', suffix=values['portrait_suffix'])
        text = loc_value(text, 'VAL_proclaim_commonwealth_desc', suffix=values['map_suffix'] + values['portrait_suffix'])
        for key in ('VAL_frontier_deferred_tt', 'VAL_frontier_can_defer_tt'):
            assert not re.search(rf'(?m)^ {key}:', text)
            text += f'\n {key}:0 "{values[key]}"\n'
        write(path, text)
        assert Path(path).read_bytes().startswith(b'\xef\xbb\xbf')

    assert run('regression_green', REGRESSION)['returncode'] == 0
    focused = run('focused_green', FOCUSED)
    baseline = (OUT/'baseline.txt').read_text()
    baseline_failures = re.findall(r'(?m)^(?:FAIL|ERROR): .+$', baseline)
    REPORT['baseline_focused_failures'] = baseline_failures
    REPORT['new_focused_failures'] = sorted(set(focused['problems']) - set(baseline_failures))
    assert not REPORT['new_focused_failures'], REPORT['new_focused_failures']
    with ThreadPoolExecutor(max_workers=2) as pool:
        tc = pool.submit(run, 'validate_tc', ['python', '-B', 'tools/validate_tc.py', '--limit', '300'], 180)
        suite = pool.submit(run, 'full_suite', ['python', '-B', '-m', 'unittest', 'discover', '-s', 'tools/tests', '-p', 'test_*.py', '-v'], 180)
        tc.result(); suite.result()
    assert run('diff_check', ['git', 'diff', '--check'])['returncode'] == 0
    assert run('regression_final', REGRESSION)['returncode'] == 0
    REPORT['paths'] = {p: subprocess.check_output(['git', 'hash-object', p], text=True).strip() for p in PATHS}
    REPORT['diff_stat'] = subprocess.check_output(['git', 'diff', '--stat', '--', *PATHS], text=True)
    REPORT['status'] = 'targeted_checks_passed'
    # Only explicit feature paths are staged; inspection scripts never enter the final PR tree.
    subprocess.run(['git', 'add', '--', *PATHS], check=True)
    subprocess.run(['git', 'commit', '-m', 'fix: observer timeout and Kefreyt deferral and proclamation lifecycle'], check=True)
except Exception as error:
    REPORT['status'] = 'failed'
    REPORT['error'] = repr(error)
    raise
finally:
    (OUT/'report.json').write_text(json.dumps(REPORT, ensure_ascii=False, indent=2)+'\n')
    subprocess.run(['git', 'add', '--', str(OUT/'report.json'), str(OUT/'regression-red.txt')], check=True)
    if subprocess.run(['git', 'diff', '--cached', '--quiet']).returncode:
        subprocess.run(['git', 'commit', '-m', 'ci: record observer and Kefreyt verification results'], check=True)
    subprocess.run(['git', 'push', 'origin', f'HEAD:{BRANCH}'], check=True)
