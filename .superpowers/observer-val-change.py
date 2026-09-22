from pathlib import Path
import json
import os
import re
import signal
import subprocess
import sys

BASE = '0c52cb91cd23bf0a29ca3ee7c264eee35ec978a5'
REPORT = Path('/tmp/observer-val-report.json')
report = {'base': BASE, 'checks': {}, 'runtime_tested': False}
original = {}

def read(path):
    return Path(path).read_bytes().decode('utf-8-sig')

def write(path, text):
    p = Path(path)
    original.setdefault(path, p.read_bytes())
    data = original[path]
    p.write_bytes(text.encode('utf-8-sig' if data.startswith(b'\xef\xbb\xbf') else 'utf-8'))

def block(text, name):
    m = re.search(r'(?m)^[ \t]*' + re.escape(name) + r'\s*=\s*\{', text)
    assert m, name
    start = m.start()
    brace = text.index('{', m.start())
    depth = 0
    in_string = escaped = comment = False
    for i in range(brace, len(text)):
        ch = text[i]
        if comment:
            if ch == '\n': comment = False
            continue
        if in_string:
            if escaped: escaped = False
            elif ch == '\\': escaped = True
            elif ch == '"': in_string = False
            continue
        if ch == '#': comment = True
        elif ch == '"': in_string = True
        elif ch == '{': depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0: return text[start:i+1]
    raise AssertionError('Unclosed ' + name)

def replace_block(path, name, transform):
    text = read(path)
    old = block(text, name)
    new = transform(old)
    assert new != old, name
    assert text.count(old) == 1, name
    write(path, text.replace(old, new, 1))

def focus_block(text, name):
    m = re.search(r'\bid\s*=\s*' + re.escape(name) + r'\s', text)
    assert m, name
    starts = list(re.finditer(r'(?m)^[ \t]*focus\s*=\s*\{', text[:m.start()]))
    assert starts, name
    return block(text[starts[-1].start():], 'focus')

def edit_focus(name, transform):
    path = 'common/national_focus/ADISCORD_national_focus_VAL.txt'
    text = read(path)
    old = focus_block(text, name)
    new = transform(old)
    assert new != old, name
    write(path, text.replace(old, new, 1))

def run(name, command, timeout=90):
    logfile = Path('/tmp/' + name + '.log')
    with logfile.open('w', encoding='utf-8') as out:
        process = subprocess.Popen(command, stdout=out, stderr=subprocess.STDOUT, start_new_session=True)
        try:
            code = process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()
            code = 124
            out.write('\nTIMEOUT\n')
    output = logfile.read_text(encoding='utf-8', errors='replace')
    failures = re.findall(r'(?m)^(?:FAIL|ERROR): .+$', output)
    early = re.findall(r'(?m)^test_.*(?:FAIL|ERROR).*$', output)
    report['checks'][name] = {'returncode': code, 'failures': failures, 'early_failures': early, 'tail': output[-5000:]}
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(name, code, output[-1500:], flush=True)
    return code, output

VALTEST = 'tools/tests/test_val_contract_ui.py'
SUPERTEST = 'tools/tests/test_adiscord_superevents_stp_empire.py'
VAL_TESTS = r'''

class TestValProgressionChoices(unittest.TestCase):
    def focus(self, name):
        source = read("common/national_focus/ADISCORD_national_focus_VAL.txt")
        marker = re.search(r"\bid\s*=\s*" + re.escape(name) + r"\s", source)
        self.assertIsNotNone(marker, name)
        starts = list(re.finditer(r"(?m)^\s*focus\s*=\s*\{", source[:marker.start()]))
        return named_block(source[starts[-1].start():], "focus")

    def test_portrait_belongs_to_proclamation_not_unlock(self):
        focus = self.focus("VAL_Contracts_Outlive_Kings")
        self.assertNotIn("set_portraits", focus)
        effects = read("common/scripted_effects/ADISCORD_VAL_effects.txt")
        adopt = named_block(effects, "VAL_adopt_commonwealth")
        self.assertIn("VAL_can_proclaim_commonwealth = yes", adopt)
        self.assertLess(adopt.index("set_cosmetic_tag = VAL_commonwealth"),
                        adopt.index("VAL_sync_solgalov_portrait = yes"))
        sync = named_block(effects, "VAL_sync_solgalov_portrait")
        self.assertIn("has_character = VAL_Valera_Solgalov", sync)
        self.assertIn("has_cosmetic_tag = VAL_commonwealth", sync)
        self.assertIn("large = GFX_portrait_VAL_Valera_Solgalov_contracts", sync)
        self.assertIn("large = GFX_portrait_VAL_Valera_Solgalov }", sync)
        self.assertNotIn("recruit_character", sync)
        startup = named_block(read("common/on_actions/02_ADISCORD_VAL_rework_on_actions.txt"), "on_startup")
        self.assertEqual(startup.count("VAL_sync_solgalov_portrait = yes"), 1)

    def test_proclamation_has_one_map_marker_and_keeps_real_requirements(self):
        decision = named_block(read("common/decisions/ADISCORD_VAL_decisions.txt"), "VAL_proclaim_commonwealth")
        for token in ("state_target = yes", "targets = { 48 }", "on_map_mode = map_and_decisions_view", "highlight_states", "cost = 150", "VAL_can_proclaim_commonwealth = yes"):
            self.assertIn(token, decision)
        self.assertIn("has_completed_focus = VAL_Contracts_Outlive_Kings", named_block(decision, "visible"))
        self.assertNotIn("VAL_can_proclaim_commonwealth", named_block(decision, "visible"))
        trigger = named_block(read("common/scripted_triggers/ADISCORD_VAL_rework_triggers.txt"), "VAL_can_proclaim_commonwealth")
        self.assertIn("VAL_campaign_objectives_met = yes", trigger)
        self.assertNotIn("deferred", trigger)

    def test_frontier_bypass_requires_explicit_choice_and_an_idle_peace(self):
        focus = self.focus("VAL_frontier_treaty_offices")
        bypass = named_block(focus, "bypass")
        self.assertIn("VAL_northern_expansion_deferred = yes", bypass)
        triggers = read("common/scripted_triggers/ADISCORD_VAL_rework_triggers.txt")
        gate = named_block(triggers, "VAL_northern_expansion_deferred")
        for token in ("has_country_flag = VAL_frontier_expansion_deferred", "has_completed_focus = VAL_frontier_security_plan", "VAL_frontier_idle = yes", "has_war = no", "has_capitulated = no", "is_subject = no"):
            self.assertIn(token, gate)
        self.assertNotIn("is_ai", gate)
        decisions = read("common/decisions/ADISCORD_VAL_decisions.txt")
        defer = named_block(decisions, "VAL_defer_northern_expansion")
        self.assertIn("VAL_can_defer_northern_expansion = yes", named_block(defer, "available"))
        self.assertIn("ai_will_do", defer)
        reward = named_block(defer, "complete_effect")
        for forbidden in ("transfer_state", "annex_country", "add_core_of", "set_cosmetic_tag", "VAL_frontier_treaty_signed"):
            self.assertNotIn(forbidden, reward)
        self.assertIn("set_country_flag = VAL_frontier_expansion_deferred", reward)

    def test_declining_then_reopening_does_not_leave_a_stale_opt_out(self):
        decisions = read("common/decisions/ADISCORD_VAL_decisions.txt")
        withdraw = named_block(decisions, "VAL_frontier_withdraw_demand")
        self.assertIn("VAL_frontier_withdraw_and_defer = yes", withdraw)
        effects = read("common/scripted_effects/ADISCORD_VAL_effects.txt")
        withdraw_effect = named_block(effects, "VAL_frontier_withdraw_and_defer")
        self.assertIn("value = 2 compare = equals", withdraw_effect)
        self.assertIn("has_war = no", withdraw_effect)
        self.assertIn("VAL_frontier_close = yes", withdraw_effect)
        self.assertIn("set_country_flag = VAL_frontier_expansion_deferred", withdraw_effect)
        demand = named_block(decisions, "VAL_frontier_demand_CIN")
        self.assertIn("clr_country_flag = VAL_frontier_expansion_deferred", named_block(demand, "complete_effect"))
        self.assertIn("VAL_ai_frontier_force_ready", named_block(demand, "ai_will_do"))
        self.assertIn("has_country_flag = VAL_frontier_expansion_deferred", named_block(demand, "ai_will_do"))

    def test_economic_route_does_not_require_bypassed_military_rewards(self):
        reopen = self.focus("VAL_Reopen_Trade_Routes")
        debts = self.focus("VAL_Settle_Industrial_Debts")
        self.assertIn("focus = VAL_Campaign_Secured focus = VAL_Returning_Buyers", reopen)
        self.assertIn("focus = VAL_New_Supply_Base focus = VAL_Contingency_Ledgers", reopen)
        self.assertIn("focus = VAL_Campaign_Secured focus = VAL_Returning_Buyers", debts)
        for name in ("VAL_Reopen_Trade_Routes", "VAL_Settle_Industrial_Debts", "VAL_Return_To_World_Market"):
            with self.subTest(name=name):
                focus = self.focus(name)
                self.assertIn("VAL_economic_settlement_ready = yes", named_block(focus, "available"))
                self.assertNotIn("bypass", focus)
        gate = named_block(read("common/scripted_triggers/ADISCORD_VAL_rework_triggers.txt"), "VAL_economic_settlement_ready")
        for token in ("VAL_campaign_objectives_met = yes", "VAL_northern_expansion_deferred = yes", "has_completed_focus = VAL_Returning_Buyers", "has_completed_focus = VAL_Contingency_Ledgers"):
            self.assertIn(token, gate)
        for name in ("VAL_Campaign_Secured", "VAL_New_Supply_Base", "VAL_Veterans_Of_The_Campaign"):
            self.assertNotIn("bypass", self.focus(name))

    def test_choice_and_economic_conditions_are_localised_in_both_languages(self):
        for language in ("russian", "english"):
            path = ROOT / f"localisation/{language}/ADISCORD_VAL_decisions_l_{language}.yml"
            self.assertTrue(path.read_bytes().startswith(b"\xef\xbb\xbf"))
            text = path.read_text(encoding="utf-8-sig")
            for key in ("VAL_defer_northern_expansion", "VAL_defer_northern_expansion_desc", "VAL_defer_northern_expansion_tt", "VAL_defer_northern_expansion_ready_tt", "VAL_economic_settlement_ready_tt", "VAL_northern_expansion_deferred_tt"):
                self.assertRegex(text, rf'(?m)^ {key}:\d* "[^\r\n]*"$')
'''
SUPER_TESTS = r'''

class ObserverSupereventTimeoutTests(unittest.TestCase):
    def test_timeout_covers_every_registered_presentation_and_starts_at_seven_days(self):
        source = read(ROOT / "common/scripted_effects/ADISCORD_vorkerland_effects.txt")
        tick = named_block(source, "ADISCORD_superevent_observer_tick")
        guis = read(ROOT / "common/scripted_guis/superevents.txt")
        flags = set(re.findall(r"window_name\s*=\s*\"(superevent_[a-z_]+)\"", guis))
        self.assertTrue(flags)
        ages = re.findall(r"has_global_flag\s*=\s*\{\s*flag\s*=\s*(superevent_[a-z_]+)\s+days\s*>\s*(\d+)\s*\}", tick)
        self.assertEqual({name for name, _ in ages}, flags)
        for name, threshold in ages:
            with self.subTest(presentation=name):
                self.assertEqual(int(threshold), 6)
                self.assertFalse(6 > int(threshold))
                self.assertTrue(7 > int(threshold))
                self.assertIn(f"clr_global_flag = {name}", tick)
        self.assertNotIn("ADISCORD_vorkerland_clear_superevent_flags = yes", tick)
        self.assertNotIn("clear_array", tick)
        self.assertNotIn("set_global_flag = superevent_", tick)
        self.assertEqual(tick.count("ADISCORD_superevent_dispatch_next = yes"), 1)
        self.assertLess(tick.rindex("clr_global_flag"), tick.index("ADISCORD_superevent_dispatch_next = yes"))

    def test_observer_timeout_is_globally_guarded_and_never_closes_a_human_session(self):
        tick = named_block(read(ROOT / "common/scripted_effects/ADISCORD_vorkerland_effects.txt"), "ADISCORD_superevent_observer_tick")
        self.assertIn("NOT = { any_country = { is_ai = no } }", tick)
        self.assertIn("NOT = { has_global_flag = ADISCORD_superevent_observer_checked_today }", tick)
        self.assertIn("set_global_flag = { flag = ADISCORD_superevent_observer_checked_today days = 1 }", tick)
        self.assertLess(tick.index("set_global_flag"), tick.index("any_country"))
        self.assertNotIn("every_country", tick)
        actions = read(ROOT / "common/on_actions/00_ADISCORD_on_actions.txt")
        daily = named_block(actions, "on_daily")
        self.assertEqual(daily.count("ADISCORD_superevent_observer_tick = yes"), 1)
        self.assertNotIn("every_country", daily)
        self.assertNotIn("is_ai = no", daily)
'''

write(VALTEST, read(VALTEST) + VAL_TESTS)
write(SUPERTEST, read(SUPERTEST) + SUPER_TESTS)
regression = [sys.executable, '-B', '-m', 'unittest', 'tools.tests.test_val_contract_ui.TestValProgressionChoices', 'tools.tests.test_adiscord_superevents_stp_empire.ObserverSupereventTimeoutTests', '-v']
code, out = run('observer_val_red', regression)
assert code == 1 and 'FAILED (' in out and 'ERROR:' not in out, out
assert len(report['checks']['observer_val_red']['failures']) == 8, report

focus = 'common/national_focus/ADISCORD_national_focus_VAL.txt'
effects = 'common/scripted_effects/ADISCORD_VAL_effects.txt'
triggers = 'common/scripted_triggers/ADISCORD_VAL_rework_triggers.txt'
decisions = 'common/decisions/ADISCORD_VAL_decisions.txt'

def remove_early_portrait(old):
    portrait = re.search(r'\n[ \t]*if = \{\s*limit = \{ has_character = VAL_Valera_Solgalov \}\s*set_portraits = \{\s*character = VAL_Valera_Solgalov\s*civilian = \{ large = GFX_portrait_VAL_Valera_Solgalov_contracts \}\s*\}\s*\}', old)
    assert portrait, 'early portrait'
    return old[:portrait.start()] + old[portrait.end():]
edit_focus('VAL_Contracts_Outlive_Kings', remove_early_portrait)
replace_block(effects, 'VAL_adopt_commonwealth', lambda s: s.replace('set_cosmetic_tag = VAL_commonwealth', 'set_cosmetic_tag = VAL_commonwealth\n        VAL_sync_solgalov_portrait = yes'))
write(effects, read(effects) + '''

# The cosmetic state is authoritative, including when repairing an older save.
VAL_sync_solgalov_portrait = {
    if = {
        limit = { has_character = VAL_Valera_Solgalov }
        if = {
            limit = { has_cosmetic_tag = VAL_commonwealth }
            set_portraits = {
                character = VAL_Valera_Solgalov
                civilian = { large = GFX_portrait_VAL_Valera_Solgalov_contracts }
            }
        }
        else = {
            set_portraits = {
                character = VAL_Valera_Solgalov
                civilian = { large = GFX_portrait_VAL_Valera_Solgalov }
            }
        }
    }
}

# Only an explicit prewar withdrawal selects the alternative route.
# The bilateral Irem claim does not determine the northern policy.
VAL_frontier_withdraw_and_defer = {
    if = {
        limit = {
            has_war = no
            check_variable = { var = VAL_frontier_stage value = 2 compare = equals }
        }
        if = {
            limit = { check_variable = { var = VAL_frontier_target value = 4 compare = less_than } }
            set_country_flag = VAL_frontier_expansion_deferred
        }
        VAL_frontier_close = yes
    }
}
''')
replace_block('common/on_actions/02_ADISCORD_VAL_rework_on_actions.txt', 'on_startup', lambda s: s.replace('VAL_grant_contract_warlord = yes', 'VAL_grant_contract_warlord = yes\n\t\t\t\t\tVAL_sync_solgalov_portrait = yes', 1))

def map_proclamation(s):
    s = s.replace('visible = { NOT = { has_cosmetic_tag = VAL_commonwealth } }', 'visible = { has_completed_focus = VAL_Contracts_Outlive_Kings NOT = { has_cosmetic_tag = VAL_commonwealth } }')
    return s.replace('allowed = { tag = VAL }', '''allowed = { tag = VAL }
        state_target = yes
        targets = { 48 }
        target_trigger = { FROM = { state = 48 } }
        on_map_mode = map_and_decisions_view
        highlight_states = {
            highlight_state_targets = {
                OR = {
                    state = 48 state = 29 state = 46
                    state = 58 state = 59 state = 60 state = 61
                    state = 62 state = 63 state = 64 state = 65
                    state = 10 state = 11 state = 12 state = 13
                    state = 17 state = 18 state = 30
                    is_core_of = STP
                }
            }
        }''', 1)
replace_block(decisions, 'VAL_proclaim_commonwealth', map_proclamation)

write(triggers, read(triggers) + '''

# Policy is explicit; merely not researching the military branch is not a choice.
VAL_can_defer_northern_expansion = {
    tag = VAL
    has_completed_focus = VAL_frontier_security_plan
    VAL_frontier_postwar = yes
    VAL_frontier_idle = yes
    has_war = no
    NOT = { has_country_flag = VAL_frontier_expansion_deferred }
    NOT = { has_country_flag = VAL_frontier_treaty_signed }
    NOT = { has_country_flag = VAL_campaign_mobilizing }
}

VAL_northern_expansion_deferred = {
    has_country_flag = VAL_frontier_expansion_deferred
    has_completed_focus = VAL_frontier_security_plan
    has_capitulated = no
    is_subject = no
    has_war = no
    VAL_frontier_idle = yes
    NOT = { has_country_flag = VAL_campaign_mobilizing }
    NOT = { has_country_flag = VAL_stelander_defeated }
}

# Commercial recovery does not certify territorial victory or remove a resource shortage.
VAL_economic_settlement_ready = {
    OR = {
        VAL_campaign_objectives_met = yes
        AND = {
            VAL_northern_expansion_deferred = yes
            has_completed_focus = VAL_Returning_Buyers
            has_completed_focus = VAL_Contingency_Ledgers
        }
    }
}
''')
new_decision = '''
    VAL_defer_northern_expansion = {
        icon = generic_political_pressure
        allowed = { tag = VAL }
        visible = {
            has_completed_focus = VAL_frontier_security_plan
            NOT = { has_country_flag = VAL_frontier_expansion_deferred }
            NOT = { has_country_flag = VAL_frontier_treaty_signed }
        }
        available = {
            custom_trigger_tooltip = {
                tooltip = VAL_defer_northern_expansion_ready_tt
                VAL_can_defer_northern_expansion = yes
            }
        }
        cost = 0
        complete_effect = {
            custom_effect_tooltip = VAL_defer_northern_expansion_tt
            hidden_effect = {
                if = {
                    limit = { VAL_can_defer_northern_expansion = yes }
                    set_country_flag = VAL_frontier_expansion_deferred
                }
            }
        }
        ai_will_do = {
            base = 5
            modifier = { factor = 10 has_completed_focus = VAL_Trading_Partners }
            modifier = {
                factor = 0
                VAL_ai_frontier_force_ready = yes
                NOT = { has_completed_focus = VAL_Trading_Partners }
                OR = {
                    CIN = { VAL_frontier_bloc_target_eligible = yes }
                    OSF = { VAL_frontier_bloc_target_eligible = yes }
                    APH = { VAL_frontier_bloc_target_eligible = yes }
                }
            }
        }
    }
'''
replace_block(decisions, 'VAL_frontier', lambda s: s[:s.index('{')+1] + '\n' + new_decision + s[s.index('{')+1:])
replace_block(decisions, 'VAL_frontier_withdraw_demand', lambda s: s.replace('VAL_frontier_close = yes', 'VAL_frontier_withdraw_and_defer = yes'))
replace_block(decisions, 'VAL_frontier_demand_CIN', lambda s: s.replace('VAL_frontier_record_ultimatum = yes', 'clr_country_flag = VAL_frontier_expansion_deferred\n                VAL_frontier_record_ultimatum = yes').replace('ai_will_do = { base = 20', 'ai_will_do = { base = 20 modifier = { factor = 0 has_country_flag = VAL_frontier_expansion_deferred }'))
edit_focus('VAL_frontier_treaty_offices', lambda s: s.replace('prerequisite = { focus = VAL_frontier_security_plan }', '''prerequisite = { focus = VAL_frontier_security_plan }
        bypass = {
            custom_trigger_tooltip = {
                tooltip = VAL_northern_expansion_deferred_tt
                VAL_northern_expansion_deferred = yes
            }
        }'''))
edit_focus('VAL_frontier_security_plan', lambda s: s.replace('unlock_decision_tooltip = { decision = VAL_frontier_demand_CIN show_effect_tooltip = yes }', 'unlock_decision_tooltip = { decision = VAL_frontier_demand_CIN show_effect_tooltip = yes }\n            unlock_decision_tooltip = { decision = VAL_defer_northern_expansion show_effect_tooltip = yes }'))
for name in ('VAL_Reopen_Trade_Routes', 'VAL_Settle_Industrial_Debts', 'VAL_Return_To_World_Market'):
    def update_economic(s, name=name):
        s = s.replace('tooltip = VAL_campaign_objectives_tt VAL_campaign_objectives_met = yes', 'tooltip = VAL_economic_settlement_ready_tt VAL_economic_settlement_ready = yes')
        if name != 'VAL_Return_To_World_Market':
            s = s.replace('prerequisite = { focus = VAL_Campaign_Secured }', 'prerequisite = { focus = VAL_Campaign_Secured focus = VAL_Returning_Buyers }')
        if name == 'VAL_Reopen_Trade_Routes':
            s = s.replace('prerequisite = { focus = VAL_New_Supply_Base }', 'prerequisite = { focus = VAL_New_Supply_Base focus = VAL_Contingency_Ledgers }')
        return s
    edit_focus(name, update_economic)

super_effects = 'common/scripted_effects/ADISCORD_vorkerland_effects.txt'
flags = re.findall(r'window_name\s*=\s*"(superevent_[a-z_]+)"', read('common/scripted_guis/superevents.txt'))
assert len(flags) == len(set(flags)) == 11
checks = '\n'.join('                has_global_flag = { flag = ' + flag + ' days > 6 }' for flag in flags)
clears = '\n'.join('            if = { limit = { has_global_flag = { flag = ' + flag + ' days > 6 } } clr_global_flag = ' + flag + ' }' for flag in flags)
write(super_effects, read(super_effects).replace('# Requests and button clicks are the only dispatch points; no periodic polling.', '# Requests, button clicks and observer expiry advance the shared queue.') + '''

# The daily hook is country-scoped. The global guard permits at most one human
# scan per day, only while a presentation is overdue. No request-country or
# client-local state is used, so annexation and mixed human sessions stay safe.
ADISCORD_superevent_observer_tick = {
    if = {
        limit = {
            NOT = { has_global_flag = ADISCORD_superevent_observer_checked_today }
            OR = {
''' + checks + '''
            }
        }
        set_global_flag = { flag = ADISCORD_superevent_observer_checked_today days = 1 }
        if = {
            limit = { NOT = { any_country = { is_ai = no } } }
''' + clears + '''
            ADISCORD_superevent_dispatch_next = yes
        }
    }
}
''')
path = 'common/on_actions/00_ADISCORD_on_actions.txt'
assert not re.search(r'(?m)^\s*on_daily\s*=', read(path))
write(path, read(path).replace('on_actions = {', '''on_actions = {
    on_daily = {
        effect = {
            ADISCORD_superevent_observer_tick = yes
        }
    }
''', 1))

loc_values = {
    'russian': {
        'VAL_defer_northern_expansion': 'Отложить северную экспансию',
        'VAL_defer_northern_expansion_desc': 'Пограничные приобретения не должны останавливать торговлю и восстановление. Отложим поход против северных племён и продолжим работу через возвращение покупателей и внешние расчёты. К северному ультиматуму можно вернуться позднее.',
        'VAL_defer_northern_expansion_ready_tt': 'План пограничной безопасности завершён; Кефрейт независим, не капитулировал и не воюет. Нет активного пограничного ультиматума, кампании или мобилизации. Северное соглашение ещё не заключено.',
        'VAL_defer_northern_expansion_tt': 'Фокус «$VAL_frontier_treaty_offices$» будет пропущен без его наград. Дальнейшие фокусы Нодрула и Стеландера доступны без завоевания северных племён. Экономическое восстановление можно продолжить после фокусов «$VAL_Returning_Buyers$» и «$VAL_Contingency_Ledgers$». Обход не даёт территорий, ресурсов, военных наград или права провозгласить новое государство. Новый северный ультиматум отменяет этот выбор.',
        'VAL_northern_expansion_deferred_tt': 'Северная экспансия явно отложена; план пограничной безопасности завершён, нет войны, активного ультиматума или мобилизации.',
        'VAL_economic_settlement_ready_tt': 'Выполнены реальные цели военной кампании либо северная экспансия отложена и завершены «$VAL_Returning_Buyers$» и «$VAL_Contingency_Ledgers$» при независимом мирном Кефрейте.',
    },
    'english': {
        'VAL_defer_northern_expansion': 'Defer Northern Expansion',
        'VAL_defer_northern_expansion_desc': 'Territorial acquisitions must not stop trade and recovery. We will defer the campaign against the northern tribes and proceed through returning buyers and foreign clearing houses. The northern ultimatum remains an option later.',
        'VAL_defer_northern_expansion_ready_tt': 'The frontier security plan is complete; Kefreyt is independent, has not capitulated and is at peace. No frontier ultimatum, campaign or mobilisation is active. No northern settlement has been signed.',
        'VAL_defer_northern_expansion_tt': 'Bypass $VAL_frontier_treaty_offices$ without receiving its rewards. The subsequent Nodrul and Stelander focuses do not require conquering the northern tribes first. Economic recovery can continue after $VAL_Returning_Buyers$ and $VAL_Contingency_Ledgers$. This route grants no territory, resources, military victory rewards or right to proclaim a new state. Issuing another northern ultimatum cancels this choice.',
        'VAL_northern_expansion_deferred_tt': 'Northern expansion was explicitly deferred; the frontier security plan is complete and no war, ultimatum or mobilisation is active.',
        'VAL_economic_settlement_ready_tt': 'The actual military campaign objectives are met, or northern expansion was deferred and both $VAL_Returning_Buyers$ and $VAL_Contingency_Ledgers$ are complete while Kefreyt is independent and at peace.',
    },
}
for language, values in loc_values.items():
    path = f'localisation/{language}/ADISCORD_VAL_decisions_l_{language}.yml'
    text = read(path)
    assert Path(path).read_bytes().startswith(b'\xef\xbb\xbf')
    for key, value in values.items():
        assert not re.search(r'(?m)^\s*' + re.escape(key) + r':', text), key
        text += f'\n {key}:0 "{value}"'
    text += '\n'
    for key in ('VAL_Reopen_Trade_Routes_desc', 'VAL_Settle_Industrial_Debts_desc', 'VAL_Return_To_World_Market_desc'):
        pat = r'(?m)^(\s*' + re.escape(key) + r':\d*\s*"[^\r\n]*)"$'
        text, count = re.subn(pat, lambda m: m.group(1) + r'\n\n$VAL_economic_settlement_ready_tt$"', text)
        assert count == 1, key
    pat = r'(?m)^(\s*VAL_frontier_withdraw_tt:\d*\s*"[^\r\n]*)"$'
    suffix = (' Отзыв требования к северным племенам также открывает путь без северной экспансии; это не считается победой.' if language == 'russian' else ' Withdrawing a northern-tribe demand also opens the non-expansion route; this is not a victory.')
    text, count = re.subn(pat, lambda m: m.group(1) + suffix + '"', text)
    assert count == 1
    write(path, text)

code, out = run('observer_val_green', regression)
assert code == 0, out
focused = [sys.executable, '-B', '-m', 'unittest', 'tools.tests.test_val_contract_ui', 'tools.tests.test_adiscord_superevents_stp_empire', '-v']
run('focused_changed', focused, timeout=100)
changed_data = {path: Path(path).read_bytes() for path in original}
for path, data in original.items(): Path(path).write_bytes(data)
run('focused_baseline', focused, timeout=100)
for path, data in changed_data.items(): Path(path).write_bytes(data)
assert report['checks']['focused_changed']['failures'] == report['checks']['focused_baseline']['failures'], 'new focused failures'
report['new_focused_failures'] = []
run('validate_tc', [sys.executable, '-B', 'tools/validate_tc.py', '--limit', '300'], timeout=150)
run('full_suite', [sys.executable, '-B', '-m', 'unittest', 'discover', '-s', 'tools/tests', '-p', 'test_*.py', '-v'], timeout=120)
for path, data in changed_data.items():
    assert Path(path).read_bytes() == data, 'test modified ' + path
assert run('regression_final', regression)[0] == 0
assert run('diff_check', ['git', 'diff', '--check'])[0] == 0
actual = subprocess.check_output(['git', 'diff', '--name-only'], text=True).splitlines()
assert set(actual) == set(original), actual
assert block(original[triggers].decode('utf-8-sig'), 'VAL_can_proclaim_commonwealth') == block(read(triggers), 'VAL_can_proclaim_commonwealth')
report['paths'] = actual
report['blobs'] = {p: subprocess.check_output(['git', 'hash-object', p], text=True).strip() for p in actual}
report['diff'] = subprocess.check_output(['git', 'diff', '--', *actual], text=True)
REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2))
subprocess.run(['git', 'config', 'user.name', 'github-actions[bot]'], check=True)
subprocess.run(['git', 'config', 'user.email', '41898282+github-actions[bot]@users.noreply.github.com'], check=True)
subprocess.run(['git', 'read-tree', BASE], check=True)
subprocess.run(['git', 'add', '--', *actual], check=True)
tree = subprocess.check_output(['git', 'write-tree'], text=True).strip()
commit = subprocess.check_output(['git', 'commit-tree', tree, '-p', BASE, '-m', 'fix: observer superevent timeout and Kefreyt progression choices'], text=True).strip()
subprocess.run(['git', 'push', 'origin', commit + ':refs/heads/fix/observer-val-ready'], check=True)
report['commit'] = commit
REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2))
short = {k:v for k,v in report.items() if k != 'diff'}
Path('.superpowers/observer-val-result.json').write_text(json.dumps(short, ensure_ascii=False, indent=2))
subprocess.run(['git', 'read-tree', 'HEAD'], check=True)
subprocess.run(['git', 'add', '.superpowers/observer-val-result.json'], check=True)
subprocess.run(['git', 'commit', '-m', 'ci: record observer and Kefreyt verification results'], check=True)
subprocess.run(['git', 'push', 'origin', 'HEAD'], check=True)
print('RESULT', commit, flush=True)
