"""Apply the reviewed, bounded Party changes to a fresh checkout."""
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path.cwd()))
from tools.validators.validate_adiscord_division_templates import parse_clausewitz

D = 'common/decisions/ADISCORD_STP_decisions.txt'
C = 'common/decisions/categories/ADISCORD_decision_categories_STP.txt'
E = 'common/scripted_effects/ADISCORD_STP_scripted_effects.txt'
T = 'common/scripted_triggers/ADISCORD_STP_scripted_triggers.txt'
F = 'common/national_focus/ADISCORD_national_focus_STP.txt'
L = 'common/scripted_localisation/ADISCORD_STP_scripted_loc.txt'
A = 'common/on_actions/02_ADISCORD_STP_on_actions.txt'
S = 'common/synchronized_dynamic_tokens/ADISCORD_tokens.txt'
changed = []


def read(path):
    return Path(path).read_text(encoding='utf-8-sig')


def write(path, text):
    raw = Path(path).read_bytes()
    encoding = 'utf-8-sig' if raw.startswith(b'\xef\xbb\xbf') else 'utf-8'
    Path(path).write_text(text, encoding=encoding, newline='')
    if path not in changed:
        changed.append(path)


def mask(text):
    return re.sub(r'"(?:[^"\\]|\\.)*"|#[^\n]*',
                  lambda m: ''.join('\n' if c == '\n' else ' ' for c in m.group()), text)


def spans(text, name):
    clean = mask(text)
    result = []
    for m in re.finditer(r'\b' + re.escape(name) + r'\s*=\s*\{', clean):
        opening = m.end() - 1
        depth = 1
        end = opening + 1
        while depth and end < len(clean):
            depth += (clean[end] == '{') - (clean[end] == '}')
            end += 1
        assert depth == 0, name
        result.append((m.start(), opening, end))
    return result


def span(text, name, first=False):
    found = spans(text, name)
    assert found and (first or len(found) == 1), (name, len(found))
    return found[0]


def edit(text, name, transform, first=False):
    start, opening, end = span(text, name, first)
    return text[:opening + 1] + transform(text[opening + 1:end - 1]) + text[end - 1:]


def replace_block(text, name, replacement):
    start, _, end = span(text, name)
    return text[:start] + replacement + text[end:]


def append_body(body, payload, indent='\t\t'):
    return body.rstrip() + '\n' + indent + payload + '\n' + indent[:-1]


def add(text, name, payload, first=False):
    return edit(text, name, lambda b: append_body(b, payload), first)


def substitute(text, pattern, replacement, count=1):
    result, n = re.subn(pattern, replacement, text)
    assert n == count, (pattern, n, count)
    return result


def edit_focus(text, focus_id, transform):
    found = [(a, b, c) for a, b, c in spans(text, 'focus')
             if re.match(r'\s*id\s*=\s*' + re.escape(focus_id) + r'\b', text[b + 1:c - 1])]
    assert len(found) == 1, (focus_id, len(found))
    a, b, c = found[0]
    return text[:a] + transform(text[a:c]) + text[c:]


def move_decisions(text, names, destination):
    extracted = []
    for name in names:
        start, _, end = span(text, name)
        line_start = text.rfind('\n', 0, start) + 1
        assert not text[line_start:start].strip(), name
        extracted.append(text[line_start:end])
        text = text[:line_start] + text[end:]
    start, opening, end = span(text, destination)
    return text[:end - 1].rstrip() + '\n\n' + '\n\n'.join(extracted) + '\n' + text[end - 1:]


def decision_ids(text):
    return [d.key for c in parse_clausewitz(text) if isinstance(c.value, list)
            for d in c.value if isinstance(d.value, list)]


# Preserve every operative ID while relocating its UI owner.
decisions = read(D)
before_ids = decision_ids(decisions)
foreign = ('STP_ps_fund_nod', 'STP_ps_arm_nod', 'STP_ps_engineers_nod',
           'STP_ps_expedition_nod', 'STP_ps_nod_dispatch', 'STP_ps_nod_delivery',
           'STP_ps_cancel_nod', 'STP_ps_nod_route_wait', 'STP_ps_val_intelligence',
           'STP_ps_val_intelligence_work', 'STP_ps_val_intercept',
           'STP_ps_val_intercept_work', 'STP_ps_val_pressure', 'STP_ps_val_pressure_work',
           'STP_ps_evacuate_funds')
government = ('STP_ps_build_radio', 'STP_ps_build_radio_work', 'STP_ps_build_hq',
              'STP_ps_build_hq_work', 'STP_ps_prepare_evacuation', 'STP_ps_prepare_evacuation_work')
ultimatum = ('STP_pw_party_nod_invasion_countdown', 'STP_pw_party_nod_emergency_mobilization',
             'STP_pw_party_nod_fortify_border', 'STP_pw_party_nod_staff_readiness')
decisions = move_decisions(decisions, foreign + ultimatum, 'STP_cw_external_intervention')
decisions = move_decisions(decisions, government, 'STP_party_factions')
start, opening, end = span(decisions, 'STP_postwar_nod_ultimatum')
assert not mask(decisions[opening + 1:end - 1]).strip()
decisions = decisions[:start] + decisions[end:]
assert sorted(before_ids) == sorted(decision_ids(decisions))

# Entry checks are separate from completion checks: the clock naturally runs down during work.
for action, window, marker in (
        ('STP_ps_val_intelligence', 'STP_ps_val_recon_window', 'STP_ps_val_known_sequence'),
        ('STP_ps_val_intercept', 'STP_ps_val_intercept_window', 'STP_ps_val_intercepted_sequence')):
    guard = ('custom_trigger_tooltip = { tooltip = ' + window + '_tt ' + window + ' = yes }\n'
             '\t\t\tcustom_trigger_tooltip = { tooltip = ' + action + '_fresh_tt '
             'VAL = { NOT = { check_variable = { var = ' + marker + ' value = STP_ps_val_sequence compare = equals } } } }')
    def modify_action(body, guard=guard, window=window, marker=marker, action=action):
        body = add(body, 'available', guard)
        body = edit(body, 'complete_effect', lambda payload: add(
            payload, 'limit', window + ' = yes\n\t\t\t\tVAL = { NOT = { check_variable = { var = ' + marker + ' value = STP_ps_val_sequence compare = equals } } }', first=True))
        return add(body, 'complete_effect', 'custom_effect_tooltip = ' + action + '_result_tt')
    decisions = edit(decisions, action, modify_action)

def pressure_action(body):
    body = add(body, 'available', 'custom_trigger_tooltip = { tooltip = STP_ps_val_pressure_available_tt STP_ps_val_pressure_available = yes }')
    body = edit(body, 'complete_effect', lambda payload: add(payload, 'limit', 'STP_ps_val_pressure_available = yes', first=True))
    body = substitute(body, r'activate_mission\s*=\s*STP_ps_val_pressure_work\b', 'STP_ps_val_pressure_finish = yes')
    return add(body, 'complete_effect', 'custom_effect_tooltip = STP_ps_val_pressure_result_tt')
decisions = edit(decisions, 'STP_ps_val_pressure', pressure_action)
for action in ('fund', 'arm', 'engineers', 'expedition'):
    decisions = edit(decisions, 'STP_ps_' + action + '_nod', lambda body, action=action:
                     add(body, 'complete_effect', 'custom_effect_tooltip = STP_ps_' + action + '_nod_result_tt'))
write(D, decisions)

categories = read(C)
categories = edit(categories, 'STP_elections_in_the_party', lambda b: edit(
    b, 'visible', lambda _: '\n\t\tNOT = { has_global_flag = STP_cw_started }\n\t\tNOT = { has_country_flag = STP_cw_elections_finished }\n\t'))
for category in ('STP_elections_in_the_party', 'STP_cw_war_council'):
    categories = edit(categories, category, lambda b: substitute(b, r'visible_when_empty\s*=\s*yes', 'visible_when_empty = no'))
categories = replace_block(categories, 'STP_postwar_nod_ultimatum', '')
extra_visibility = '''AND = {
                tag = STP
                has_country_flag = STP_sided_with_the_party_flag
                NOT = { has_global_flag = STP_cw_union_wars_finished }
                OR = {
                    has_completed_focus = STP_ps_foreign_supply_desk
                    has_completed_focus = STP_ps_northern_credit
                    has_completed_focus = STP_ps_northern_arms
                    has_completed_focus = STP_ps_northern_engineers
                    has_completed_focus = STP_ps_expedition_request
                    has_country_flag = STP_ps_prepare_evacuation_completed
                }
            }
            AND = {
                tag = STP
                OR = {
                    has_variable = STP_ps_nod_receipt_type
                    has_variable = STP_ps_val_intelligence_deposit
                    has_variable = STP_ps_val_intercept_deposit
                    has_variable = STP_ps_val_pressure_deposit
                    has_country_flag = STP_pw_party_nod_threat_active
                    has_country_flag = STP_pw_party_nod_invasion_active
                }
            }'''
categories = edit(categories, 'STP_cw_external_intervention', lambda b: edit(b, 'visible', lambda v: add(v, 'OR', extra_visibility, first=True)))
write(C, categories)

triggers = read(T)
assert not spans(triggers, 'STP_ps_val_recon_window')
triggers += '''
# COUNTRY STP: entry windows include the entire paid operation and a one-day margin.
STP_ps_val_recon_window = {
    VAL = {
        has_active_mission = STP_ps_val_departure
        check_variable = { var = days_mission_timeout@STP_ps_val_departure value = 22 compare = greater_than_or_equals }
    }
}
STP_ps_val_intercept_window = {
    VAL = {
        has_active_mission = STP_ps_val_departure
        check_variable = { var = days_mission_timeout@STP_ps_val_departure value = 15 compare = greater_than_or_equals }
    }
}
STP_ps_val_pressure_available = {
    tag = STP
    exists = yes
    has_capitulated = no
    has_country_flag = STP_sided_with_the_party_flag
    OR = { STP_cw_preparation_open = yes STP_ps_war_active = yes }
    OR = { has_completed_focus = STP_ps_foreign_supply_desk has_completed_focus = STP_ps_counter_supply }
    VAL = { STP_ps_val_supply_open = yes }
}
'''
write(T, triggers)

effects = read(E)
pressure_payload = '''STP_ps_val_pressure_finish = {
    if = {
        limit = { has_variable = STP_ps_val_pressure_deposit }
        if = {
            limit = {
                STP_ps_val_pressure_available = yes
                NOT = { has_country_flag = STP_ps_val_pressure_cooldown }
            }
            clear_variable = STP_ps_val_pressure_deposit
            set_country_flag = { flag = STP_ps_val_pressure_cooldown value = 1 days = 60 }
            VAL = {
                set_country_flag = { flag = STP_ps_val_pressure_active value = 1 days = 60 }
                if = {
                    limit = { has_active_mission = STP_ps_val_departure }
                    add_days_mission_timeout = { mission = STP_ps_val_departure days = 14 }
                }
            }
            ADISCORD_economy_mark_dirty = yes
        }
        else = { STP_ps_val_pressure_refund = yes }
    }
}'''
effects = replace_block(effects, 'STP_ps_val_pressure_finish', pressure_payload)
effects = edit(effects, 'STP_ps_refund_nod', lambda b: edit(b, 'limit', lambda _: '''
            OR = {
                check_variable = { var = STP_ps_nod_receipt_stage value = 1 compare = equals }
                check_variable = { var = STP_ps_nod_receipt_stage value = 2 compare = equals }
            }
        ''', first=True))

def guard_delivery(body):
    def wrap(outer):
        start, opening, end = span(outer, 'limit', first=True)
        limit = outer[start:end]
        payload = outer[end:].strip()
        return '\n        ' + limit + '\n        if = {\n            limit = { STP_ps_nod_order_current = yes }\n' + payload + '\n        }\n        else = { STP_ps_refund_nod = yes }\n    '
    return edit(body, 'if', wrap, first=True)
effects = edit(effects, 'STP_ps_deliver_nod', guard_delivery)
write(E, effects)

focuses = read(F)
for name, amount in (('STP_GUARANTEE_MINISTERS', 5), ('STP_ROTATE_DISTRICT_COMMAND', 5),
                     ('STP_cw_security_collegium', 8), ('STP_cw_capital_oath', 6)):
    def remove_blanket(focus, amount=amount):
        focus = substitute(focus, r'set_temp_variable\s*=\s*\{\s*var\s*=\s*STP_apparatus_loyalty_change\s+value\s*=\s*' + str(amount) + r'\s*\}', '')
        focus = substitute(focus, r'STP_change_apparatus_loyalty\s*=\s*yes', '')
        focus = substitute(focus, r'custom_effect_tooltip\s*=\s*STP_cw_loyalty_plus_' + str(amount) + r'_tt\b', '')
        return focus
    focuses = edit_focus(focuses, name, remove_blanket)

for chosen, alternative, idea, faction in (
        ('STP_ps_operational_reserve', 'STP_ps_route_security', 'STP_ps_reserve_idea', 4),
        ('STP_ps_route_security', 'STP_ps_operational_reserve', 'STP_ps_route_guard_idea', 3)):
    def policy(focus, alternative=alternative, idea=idea, faction=faction):
        assert 'mutually_exclusive' not in focus
        focus = edit(focus, 'prerequisite', lambda _: ' focus = STP_cw_unified_headquarters ')
        insert = ('\n\t\tmutually_exclusive = { focus = ' + alternative + ' }\n\t')
        focus = focus[:-1].rstrip() + insert + '}'
        focus = add(focus, 'completion_reward', 'add_timed_idea = { idea = ' + idea + ' days = 42 }\n\t\t\t'
                    'custom_effect_tooltip = STP_ps_policy_faction_' + str(faction) + '_tt\n\t\t\t'
                    'hidden_effect = { set_temp_variable = { var = STP_pf_selected value = ' + str(faction) + ' } STP_pf_shift = yes }')
        return focus
    focuses = edit_focus(focuses, chosen, policy)
focuses = edit_focus(focuses, 'STP_party_war_directorate', lambda b: substitute(b,
    r'prerequisite\s*=\s*\{\s*focus\s*=\s*STP_ps_operational_reserve\s*\}',
    'prerequisite = { focus = STP_ps_operational_reserve focus = STP_ps_route_security }'))
focuses = edit_focus(focuses, 'STP_ps_foreign_supply_desk', lambda b: add(b, 'completion_reward',
    'unlock_decision_tooltip = STP_ps_val_intercept\n\t\t\tunlock_decision_tooltip = STP_ps_val_pressure'))
focuses = edit_focus(focuses, 'STP_ps_counter_supply', lambda b: add(b, 'completion_reward', '''if = {
                limit = { VAL = { exists = yes } }
                add_intel = { target = VAL army_intel = 10 }
            }
            custom_effect_tooltip = STP_ps_counter_supply_current_tt
            hidden_effect = {
                VAL = {
                    if = {
                        limit = { has_variable = STP_ps_val_receipt_rifles }
                        set_variable = { var = STP_ps_val_known_sequence value = STP_ps_val_sequence }
                    }
                }
            }'''))
write(F, focuses)

on_actions = read(A)
assert not spans(on_actions, 'on_startup'), 'Merge with existing startup rather than duplicate it'
on_actions = edit(on_actions, 'on_actions', lambda b: '''
    # The selected root offset must be reevaluated on a save load without replacing an active tree.
    on_startup = {
        effect = {
            STP = {
                if = {
                    limit = {
                        exists = yes
                        NOT = { has_global_flag = STP_cw_started }
                        OR = {
                            has_country_flag = STP_sided_with_Maksim_flag
                            has_country_flag = STP_sided_with_the_party_flag
                        }
                    }
                    mark_focus_tree_layout_dirty = yes
                }
            }
        }
    }
''' + b)
write(A, on_actions)

tokens = read(S)
if 'STP_ps_val_departure' not in tokens.splitlines():
    write(S, tokens.rstrip() + '\nSTP_ps_val_departure\n')

scripted_loc = read(L)
scripted_loc += '''
# Country-specific briefings keep foreign and government reports out of the election panel.
defined_text = {
    name = STPGetWarCouncilBriefing
    text = { trigger = { tag = STP } localization_key = STP_PARTY_WAR_BRIEFING }
    text = { localization_key = STP_GENERAL_WAR_BRIEFING }
}
defined_text = {
    name = STPGetForeignBriefing
    text = { trigger = { tag = STP has_country_flag = STP_sided_with_the_party_flag } localization_key = STP_PARTY_FOREIGN_BRIEFING }
    text = { localization_key = STP_GENERAL_FOREIGN_BRIEFING }
}
defined_text = {
    name = STPGetPartyCargoStatus
    text = { trigger = { has_variable = STP_ps_val_intercept_deposit } localization_key = STP_ps_cargo_intercept_work }
    text = { trigger = { has_variable = STP_ps_val_intelligence_deposit } localization_key = STP_ps_cargo_recon_work }
    text = {
        trigger = { VAL = { has_variable = STP_ps_val_receipt_rifles check_variable = { var = STP_ps_val_intercepted_sequence value = STP_ps_val_sequence compare = equals } } }
        localization_key = STP_ps_cargo_intercept_ready
    }
    text = { trigger = { VAL = { has_active_mission = STP_ps_val_departure } } localization_key = STP_ps_cargo_departure }
    text = { trigger = { VAL = { has_variable = STP_ps_val_receipt_rifles } } localization_key = STP_ps_cargo_wait }
    text = { localization_key = STP_ps_cargo_none }
}
defined_text = {
    name = STPGetPartyAidStatus
    text = { trigger = { check_variable = { var = STP_ps_nod_receipt_stage value = 2 compare = equals } } localization_key = STP_ps_aid_transit }
    text = { trigger = { has_variable = STP_ps_nod_receipt_type } localization_key = STP_ps_aid_preparing }
    text = { trigger = { NOD = { STP_ps_nod_can_host_exiles = yes has_country_flag = STP_ps_aid_agreement } } localization_key = STP_ps_aid_confirmed }
    text = { localization_key = STP_ps_aid_unconfirmed }
}
defined_text = {
    name = STPGetPartyRadioStatus
    text = { trigger = { has_country_flag = STP_ps_build_radio_completed } localization_key = STP_ps_project_ready }
    text = { trigger = { has_variable = STP_ps_build_radio_deposit } localization_key = STP_ps_project_running }
    text = { localization_key = STP_ps_project_not_ready }
}
defined_text = {
    name = STPGetPartyHQStatus
    text = { trigger = { has_country_flag = STP_ps_build_hq_completed } localization_key = STP_ps_project_ready }
    text = { trigger = { has_variable = STP_ps_build_hq_deposit } localization_key = STP_ps_project_running }
    text = { localization_key = STP_ps_project_not_ready }
}
'''
write(L, scripted_loc)

LOC = {
'russian': {
'STP_party_factions': 'Президиум и аппарат',
'STP_cw_external_intervention': 'Внешние связи',
'STP_PARTY_ELECTION_BRIEFING': '[STP_display_party_suspicion]\\n\\n§YЗадача: удержать мандат партии.§! Следите за сроком выборов и объявленными операциями подполья. Проверяйте отмеченный округ, а не проводите обыски вслепую.\\n\\nАппарат и подготовка правительства - в §Y«Президиуме и аппарате»§!. Помощь Нодрулу и поставки Кефрейта - во §Y«Внешних связях»§!. Победа на выборах не отменяет гражданскую войну.',
'STP_party_factions_desc': 'Влияние фракций в сумме равно 100%; их поддержка определяет верность аппарата. Усиление выбранной группы меняет баланс, а не покупает лояльность всех остальных. Соглашения доступны раз в 30 дней.[STPGetPartyPreparationReport]',
'STP_ps_preparation_report': '\\n\\n§YПодготовка правительства§!\\nРадиосеть: [STPGetPartyRadioStatus]. Резервный штаб: [STPGetPartyHQStatus].\\nЗавершите проекты до раскола; незаконченная подготовка возвращает свой резерв. Внешние поставки показаны отдельно.',
'STP_PARTY_WAR_BRIEFING': '§YЗадача: сохранить управление и подготовить контрудар.§! Оперативный резерв усиливает армию; охрана сообщений - службу безопасности и снабжение. Это альтернативные курсы. Повторные программы оплачиваются отдельно.\\n\\nПравительство: [STPGetPartyGovernment].[STPGetPartySurvival][STPGetRecoveryReport]',
'STP_PARTY_FOREIGN_BRIEFING': '§YНодрул:§! [STPGetNodStatus]\\nПомощь: [STPGetPartyAidStatus]. Деньги и вооружение не гарантируют его вступление в войну.\\n\\n§YКефрейт:§! [STPGetPartyCargoStatus]\\nРазведка и перехват требуют 7 + 14 дней. Давление сразу задерживает ещё не отправленный груз. Цены и условия возврата указаны в решениях.',
'STP_ps_cargo_intercept_work': 'готовится перехват текущей поставки; срок указан в миссии.',
'STP_ps_cargo_recon_work': 'разведка изучает текущую поставку; срок указан в миссии.',
'STP_ps_cargo_intercept_ready': 'перехват подготовлен: оружие будет изъято при отправке этого груза.',
'STP_ps_cargo_departure': 'до отправки §Y[?VAL.days_mission_timeout@STP_ps_val_departure|0]§! дн. Проверьте, хватает ли времени на выбранную операцию.',
'STP_ps_cargo_wait': 'груз зарезервирован, но маршрут закрыт; срока отправки пока нет.',
'STP_ps_cargo_none': 'активной поставки нет.',
'STP_ps_aid_transit': 'груз в пути',
'STP_ps_aid_preparing': 'заказ готовится или ожидает маршрута',
'STP_ps_aid_confirmed': 'соглашение подтверждено, нового заказа нет',
'STP_ps_aid_unconfirmed': 'соглашение не подтверждено',
'STP_ps_project_ready': '§Gготов§!',
'STP_ps_project_running': '§Yработы идут§!',
'STP_ps_project_not_ready': 'не готов',
'STP_ps_val_recon_window_tt': 'До отправки осталось не менее §Y22 дней§!: 7 дней разведки, 14 дней перехвата и запас в 1 день.',
'STP_ps_val_intercept_window_tt': 'До отправки осталось не менее §Y15 дней§!: 14 дней подготовки и запас в 1 день.',
'STP_ps_val_intelligence_fresh_tt': 'Эта поставка ещё не изучена.',
'STP_ps_val_intercept_fresh_tt': 'Для этой поставки ещё не подготовлен перехват.',
'STP_ps_val_pressure_available_tt': 'Партийное правительство действует, а Кефрейт ещё может снабжать сопротивление.',
'STP_ps_val_intelligence_desc': 'Изучить текущую поставку за §Y7 дней§!. Затем станет возможен отдельный платный перехват. Начать можно, когда до отправки остаётся хотя бы 22 дня. Если поставка исчезнет или сменится, резерв возвращается.',
'STP_ps_val_intercept_desc': 'Подготовить за §Y14 дней§! изъятие уже изученной поставки. Её оружие попадёт партии при отправке груза, а не в момент оплаты. Нужен открытый сухопутный маршрут и не менее 15 дней до отправки. При отмене подготовки резерв возвращается.',
'STP_ps_val_pressure_desc': '§YДействует сразу.§! Текущая подготовка отправки продлится на §Y14 дней§!. В течение 60 дней следующие грузы также готовятся на 14 дней дольше. Без активного таймера эффект касается только будущих отправок. Повторная оплата через 60 дней.',
'STP_ps_val_intelligence_result_tt': 'Через §Y7 дней§! станет известен текущий груз. Перехват оплачивается отдельно; исчезновение этой поставки возвращает резерв.',
'STP_ps_val_intercept_result_tt': 'Через §Y14 дней§! будет подготовлен перехват. Оружие текущего груза поступит партии при его отправке. Отмена подготовки возвращает резерв.',
'STP_ps_val_pressure_result_tt': '§GНемедленно:§! +14 дней к активной подготовке отправки. Следующие отправки замедлены на 60 дней; повторное давление в этот срок недоступно.',
'STP_ps_fund_nod_desc': 'Подготовка 14 дней и доставка 7 дней после открытия маршрута. Нодрул получает §Y1500§! казны и доступ к закупке оружия. Это помощь его армии, а не гарантированное вступление. Если соглашение утратит силу до доставки, резерв возвращается.',
'STP_ps_arm_nod_desc': 'Передать Нодрулу §Y1200§! винтовок, §Y100§! орудий и §Y60§! оснащения для северного фронта. Цена включает перевозку. Если северная война закончится до доставки или соглашение утратит силу, оплаченный резерв возвращается.',
'STP_ps_engineers_nod_desc': 'Подготовить инженерную помощь действующему северному фронту Нодрула. После доставки инженерный эффект действует §Y60 дней§!. Если северная война закончится до доставки, денежный резерв возвращается.',
'STP_ps_expedition_nod_desc': 'Подготовить усиление нодрульской экспедиции. Эффект на §Y42 дня§! включится только после её реального вступления против Шабрата. Оплата не объявляет войну. Если маршрут вмешательства закроется до доставки, резерв возвращается.',
'STP_ps_fund_nod_result_tt': 'Нодрул получит §Y1500§! казны после подготовки и доставки. Недействующее соглашение возвращает резерв; вступление в войну не гарантируется.',
'STP_ps_arm_nod_result_tt': 'После доставки Нодрул получит §Y1200§! винтовок, §Y100§! орудий и §Y60§! оснащения. Закрытие северного фронта до доставки возвращает резерв.',
'STP_ps_engineers_nod_result_tt': 'После доставки действующий северный фронт получит инженерную помощь на §Y60 дней§!. При утрате цели до доставки резерв возвращается.',
'STP_ps_expedition_nod_result_tt': 'Подготавливает усиление экспедиции на §Y42 дня§! после её реального вступления. При закрытии вмешательства до доставки резерв возвращается.',
'STP_ps_operational_reserve_desc': 'Сделаем армию опорой контрудара: немедленно введём программу оперативного резерва на 42 дня и откроем её платное продолжение. Армейская фракция усилится. Этот курс исключает приоритет охраны сообщений.',
'STP_ps_route_security_desc': 'Отдадим приоритет охране Конгресса и сообщений через Ниансас: немедленно введём охрану маршрутов на 42 дня и откроем платное продолжение. Усилится служба безопасности. Этот курс исключает оперативный резерв.',
'STP_ps_policy_faction_4_tt': 'Военный курс усиливает армейскую фракцию и перераспределяет влияние остальных групп.',
'STP_ps_policy_faction_3_tt': 'Приоритет безопасности усиливает службу безопасности и перераспределяет влияние остальных групп.',
'STP_ps_counter_supply_desc': 'Штаб получит сведения о вооружённых силах Кефрейта и сразу изучит уже подготовляемую поставку сопротивлению. После этого можно оплатить перехват или немедленно задержать отправку давлением. Будущие грузы требуют новой разведки.',
'STP_ps_foreign_supply_desk_desc': 'Откроем разведку, перехват и задержку кефрейтских поставок во «Внешних связях». Решения работают с конкретным грузом: сначала проверьте срок его отправки и выберите выполнимую операцию.',
'STP_ps_counter_supply_current_tt': 'Текущая поставка Кефрейта, если она существует, будет изучена немедленно. Будущие поставки не раскрываются автоматически.'
},
'english': {
'STP_party_factions': 'Presidium and Apparatus',
'STP_cw_external_intervention': 'Foreign Relations',
'STP_PARTY_ELECTION_BRIEFING': '[STP_display_party_suspicion]\\n\\n§YObjective: preserve the Party mandate.§! Watch the election deadline and announced underground operations. Inspect the marked district instead of searching blindly.\\n\\nGovernment preparation is under §YPresidium and Apparatus§!. Nodrul aid and Kefreyt shipments are under §YForeign Relations§!. Winning the election does not prevent the civil war.',
'STP_party_factions_desc': 'Faction influence totals 100%; their support determines apparatus loyalty. Strengthening one faction shifts the balance rather than buying every other faction\'s loyalty. Agreements are available every 30 days.[STPGetPartyPreparationReport]',
'STP_ps_preparation_report': '\\n\\n§YGovernment preparation§!\\nRadio network: [STPGetPartyRadioStatus]. Reserve headquarters: [STPGetPartyHQStatus].\\nComplete these projects before the split; unfinished preparation refunds its reserve. Foreign shipments have their own section.',
'STP_PARTY_WAR_BRIEFING': '§YObjective: preserve government and prepare the counterattack.§! The operational reserve strengthens the army; route security prioritises the security service and supply. These are alternative courses. Further programmes are paid separately.\\n\\nGovernment: [STPGetPartyGovernment].[STPGetPartySurvival][STPGetRecoveryReport]',
'STP_PARTY_FOREIGN_BRIEFING': '§YNodrul:§! [STPGetNodStatus]\\nAid: [STPGetPartyAidStatus]. Money and equipment do not guarantee intervention.\\n\\n§YKefreyt:§! [STPGetPartyCargoStatus]\\nReconnaissance and interception take 7 + 14 days. Pressure immediately delays a shipment that has not departed. Decisions show prices and refund terms.',
'STP_ps_cargo_intercept_work': 'interception of the current shipment is being prepared; see its mission timer.',
'STP_ps_cargo_recon_work': 'reconnaissance is examining the current shipment; see its mission timer.',
'STP_ps_cargo_intercept_ready': 'interception is ready: this cargo will be seized when dispatched.',
'STP_ps_cargo_departure': 'departure in §Y[?VAL.days_mission_timeout@STP_ps_val_departure|0]§! days. Check whether the selected operation can finish in time.',
'STP_ps_cargo_wait': 'cargo is reserved, but its route is blocked; departure is not yet scheduled.',
'STP_ps_cargo_none': 'no active shipment.',
'STP_ps_aid_transit': 'cargo in transit',
'STP_ps_aid_preparing': 'order preparing or awaiting a route',
'STP_ps_aid_confirmed': 'agreement confirmed; no new order',
'STP_ps_aid_unconfirmed': 'agreement not confirmed',
'STP_ps_project_ready': '§Gready§!',
'STP_ps_project_running': '§Yin progress§!',
'STP_ps_project_not_ready': 'not ready',
'STP_ps_val_recon_window_tt': 'At least §Y22 days§! remain before departure: 7 for reconnaissance, 14 for interception and a one-day margin.',
'STP_ps_val_intercept_window_tt': 'At least §Y15 days§! remain before departure: 14 for preparation and a one-day margin.',
'STP_ps_val_intelligence_fresh_tt': 'This shipment has not been examined yet.',
'STP_ps_val_intercept_fresh_tt': 'Interception has not already been prepared for this shipment.',
'STP_ps_val_pressure_available_tt': 'The Party government is operating and Kefreyt can still supply the resistance.',
'STP_ps_val_intelligence_desc': 'Examine the current shipment over §Y7 days§!, enabling a separately paid interception. Start with at least 22 days remaining before departure. A cancelled or replaced shipment refunds the reserve.',
'STP_ps_val_intercept_desc': 'Spend §Y14 days§! preparing to seize an examined shipment. Its weapons reach the Party when the cargo departs, not when you pay. Requires an open land route and at least 15 days before departure. Cancelled preparation refunds the reserve.',
'STP_ps_val_pressure_desc': '§YApplies immediately.§! Extends the current departure preparation by §Y14 days§!. For 60 days, subsequent shipments also take 14 days longer to prepare. With no active departure timer, only future shipments are affected. Available again after 60 days.',
'STP_ps_val_intelligence_result_tt': 'After §Y7 days§!, the current cargo is identified. Interception is paid separately; disappearance of this shipment refunds the reserve.',
'STP_ps_val_intercept_result_tt': 'Interception will be ready in §Y14 days§!. The current cargo\'s weapons reach the Party when dispatched. Cancelled preparation refunds the reserve.',
'STP_ps_val_pressure_result_tt': '§GImmediately:§! adds 14 days to active departure preparation. Subsequent departures are delayed for 60 days; pressure cannot be purchased again during this period.',
'STP_ps_fund_nod_desc': 'Preparation takes 14 days, followed by 7 days of delivery once a route is open. Nodrul receives §Y1500§! treasury funds and access to arms procurement. This helps its army but does not guarantee intervention. An invalidated agreement before delivery refunds the reserve.',
'STP_ps_arm_nod_desc': 'Send Nodrul §Y1200§! rifles, §Y100§! artillery pieces and §Y60§! support equipment for its northern front. The price includes transport. If that war ends or the agreement becomes invalid before delivery, the paid reserve is refunded.',
'STP_ps_engineers_nod_desc': 'Prepare engineering aid for Nodrul\'s active northern front. The engineering effect lasts §Y60 days§! after delivery. If the northern war ends before delivery, the cash reserve is refunded.',
'STP_ps_expedition_nod_desc': 'Prepare reinforcement for Nodrul\'s expedition. Its §Y42-day§! effect activates only after actual intervention against Shabrat. Payment does not declare war. If intervention closes before delivery, the reserve is refunded.',
'STP_ps_fund_nod_result_tt': 'Nodrul receives §Y1500§! treasury funds after preparation and delivery. An invalid agreement refunds the reserve; war entry is not guaranteed.',
'STP_ps_arm_nod_result_tt': 'Nodrul receives §Y1200§! rifles, §Y100§! artillery pieces and §Y60§! support equipment on delivery. Closure of the northern front beforehand refunds the reserve.',
'STP_ps_engineers_nod_result_tt': 'On delivery, the active northern front receives engineering aid for §Y60 days§!. Loss of the purpose before delivery refunds the reserve.',
'STP_ps_expedition_nod_result_tt': 'Prepares a §Y42-day§! expedition bonus after actual war entry. Closure of intervention before delivery refunds the reserve.',
'STP_ps_operational_reserve_desc': 'Make the army the foundation of the counterattack: activate the operational reserve programme immediately for 42 days and unlock its paid continuation. The army faction gains influence. This course excludes the route-security priority.',
'STP_ps_route_security_desc': 'Prioritise security of Congress and the Niansas communications route: activate route guards immediately for 42 days and unlock paid continuation. The security service gains influence. This course excludes the operational reserve.',
'STP_ps_policy_faction_4_tt': 'The military course strengthens the army faction and redistributes the other factions\' influence.',
'STP_ps_policy_faction_3_tt': 'The security priority strengthens the security service and redistributes the other factions\' influence.',
'STP_ps_counter_supply_desc': 'Headquarters gains intelligence on Kefreyt\'s armed forces and immediately examines its current resistance shipment. You may then pay for interception or delay departure with immediate pressure. Future shipments require fresh reconnaissance.',
'STP_ps_foreign_supply_desk_desc': 'Unlock reconnaissance, interception and delays of Kefreyt shipments under Foreign Relations. These decisions act on a specific cargo: check its departure deadline and choose an operation that can finish in time.',
'STP_ps_counter_supply_current_tt': 'Kefreyt\'s current shipment, if any, is identified immediately. Future shipments are not automatically revealed.'
}}

for language, updates in LOC.items():
    path = f'localisation/{language}/ADISCORD_STP_l_{language}.yml'
    text = read(path)
    values = dict(re.findall(r'^ ([\w.]+):\d*\s*"((?:[^"\\]|\\.)*)"\s*$', text, re.M))
    updates['STP_GENERAL_WAR_BRIEFING'] = values['STP_cw_war_council_desc']
    updates['STP_GENERAL_FOREIGN_BRIEFING'] = values['STP_cw_external_intervention_desc']
    updates['STP_cw_war_council_desc'] = '[STPGetWarCouncilBriefing]'
    updates['STP_cw_external_intervention_desc'] = '[STPGetForeignBriefing]'
    for key, value in updates.items():
        assert '\n' not in value and '"' not in value, key
        pattern = r'^([ \t]*' + re.escape(key) + r':\d*)[^\n]*$'
        found = re.findall(pattern, text, re.M)
        if found:
            assert len(found) == 1, (language, key)
            text = re.sub(pattern, lambda m: m.group(1) + ' "' + value + '"', text, flags=re.M)
        else:
            text = text.rstrip() + '\n ' + key + ': "' + value + '"\n'
    write(path, text)

# Category contracts change their destination, not the underlying action set.
p = 'tools/tests/test_adiscord_stp_party_survival.py'
text = read(p)
old = '''        elections = {e.key for e in categories['STP_elections_in_the_party']}
        self.assertTrue({'STP_ps_build_radio', 'STP_ps_build_hq', 'STP_ps_prepare_evacuation',
                         'STP_ps_fund_nod', 'STP_ps_arm_nod', 'STP_ps_val_intelligence', 'STP_ps_val_intercept'} <= elections)'''
new = '''        government = {e.key for e in categories['STP_party_factions']}
        foreign = {e.key for e in categories['STP_cw_external_intervention']}
        self.assertTrue({'STP_ps_build_radio', 'STP_ps_build_hq', 'STP_ps_prepare_evacuation'} <= government)
        self.assertTrue({'STP_ps_fund_nod', 'STP_ps_arm_nod', 'STP_ps_val_intelligence', 'STP_ps_val_intercept'} <= foreign)'''
assert text.count(old) == 1
text = text.replace(old, new).replace('test_preparation_uses_existing_election_category_without_extra_tabs',
                                     'test_preparation_uses_existing_context_categories_without_extra_tabs')
write(p, text)

# Validate all touched native scripts and the exact operation inventory.
for path in changed:
    if path.endswith('.txt') and path != S:
        parse_clausewitz(read(path))
    if path.startswith('common/'):
        assert not Path(path).read_bytes().startswith(b'\xef\xbb\xbf'), path
    if path.endswith('.yml'):
        lines = read(path).splitlines()
        keys = [m.group(1) for line in lines if (m := re.match(r'^ ([\w.]+):', line))]
        assert len(keys) == len(set(keys)), path
        if '/russian/' in path:
            assert Path(path).read_bytes().startswith(b'\xef\xbb\xbf'), path
assert sorted(before_ids) == sorted(decision_ids(read(D)))
print('PARTY_PATCH_FILES', '\n'.join(changed))
