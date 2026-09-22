"""Apply the reviewed, bounded STP usability patch to a clean checkout."""
from pathlib import Path
import re
from tools.validators.validate_adiscord_division_templates import parse_clausewitz

DEC = 'common/decisions/ADISCORD_STP_decisions.txt'
CAT = 'common/decisions/categories/ADISCORD_decision_categories_STP.txt'
EFF = 'common/scripted_effects/ADISCORD_STP_scripted_effects.txt'
TRI = 'common/scripted_triggers/ADISCORD_STP_scripted_triggers.txt'
FOC = 'common/national_focus/ADISCORD_national_focus_STP.txt'
EVT = 'events/ADISCORD_STP_events.txt'
ACT = 'common/on_actions/02_ADISCORD_STP_on_actions.txt'
LOC = 'common/scripted_localisation/ADISCORD_STP_scripted_loc.txt'
TOK = 'common/synchronized_dynamic_tokens/ADISCORD_tokens.txt'
changed = set()

def read(path):
    return Path(path).read_text(encoding='utf-8-sig')

def write(path, text):
    raw = Path(path).read_bytes()
    bom = raw.startswith(b'\xef\xbb\xbf')
    if path.endswith('.txt'):
        assert not bom, path
    encoding = 'utf-8-sig' if bom else 'utf-8'
    if text != read(path):
        Path(path).write_text(text, encoding=encoding, newline='\n')
        changed.add(path)

def end_brace(text, opening):
    depth = 0
    quoted = escaped = comment = False
    for i in range(opening, len(text)):
        c = text[i]
        if comment:
            if c == '\n': comment = False
            continue
        if quoted:
            if escaped: escaped = False
            elif c == '\\': escaped = True
            elif c == '"': quoted = False
            continue
        if c == '#': comment = True
        elif c == '"': quoted = True
        elif c == '{': depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0: return i + 1
    raise AssertionError('Unclosed native block')

def span(text, key, unique=True):
    matches = list(re.finditer(r'(?<![\w.])' + re.escape(key) + r'\s*=\s*\{', text))
    assert matches and (not unique or len(matches) == 1), (key, len(matches))
    m = matches[0]
    opening = text.index('{', m.start())
    return m.start(), opening, end_brace(text, opening)

def alter(text, key, fn):
    a, o, b = span(text, key)
    return text[:a] + fn(text[a:b]) + text[b:]

def append_inside(text, key, payload, unique=True):
    a, o, b = span(text, key, unique)
    return text[:b-1] + '\n' + payload + '\n' + text[b-1:]

def prepend_inside(text, key, payload, unique=True):
    a, o, b = span(text, key, unique)
    return text[:o+1] + '\n' + payload + '\n' + text[o+1:]

def set_block(text, key, body):
    a, o, b = span(text, key)
    return text[:o+1] + '\n' + body + '\n' + text[b-1:]

def once(text, old, new):
    assert text.count(old) == 1, (old[:110], text.count(old))
    return text.replace(old, new, 1)

def scalar(entries, key):
    values = [e.value for e in entries if e.key == key and not isinstance(e.value, list)]
    assert len(values) == 1, key
    return values[0]

def native_entry_span(text, entry):
    start = sum(len(line) for line in text.splitlines(keepends=True)[:entry.line-1])
    match = re.search(r'(?<![\w.])' + re.escape(entry.key) + r'\s*=\s*\{', text[start:])
    assert match, entry.key
    a = start + match.start()
    o = text.index('{', a)
    return a, o, end_brace(text, o)

# Keep original decision bodies and IDs: old category gates follow moved threats.
decisions = read(DEC)
before_ids = [a.key for c in parse_clausewitz(decisions) for a in c.value if isinstance(a.value,list)]
assert len(before_ids) == len(set(before_ids))
foreign = ['STP_ps_fund_nod','STP_ps_arm_nod','STP_ps_engineers_nod','STP_ps_expedition_nod',
           'STP_ps_nod_dispatch','STP_ps_nod_delivery','STP_ps_cancel_nod','STP_ps_nod_route_wait',
           'STP_ps_evacuate_funds','STP_ps_val_intelligence','STP_ps_val_intelligence_work',
           'STP_ps_val_intercept','STP_ps_val_intercept_work','STP_ps_val_pressure','STP_ps_val_pressure_work']
domestic = ['STP_ps_build_radio','STP_ps_build_radio_work','STP_ps_build_hq','STP_ps_build_hq_work',
            'STP_ps_prepare_evacuation','STP_ps_prepare_evacuation_work']
threats = ['STP_pw_party_nod_invasion_countdown','STP_pw_party_nod_emergency_mobilization',
           'STP_pw_party_nod_fortify_border','STP_pw_party_nod_staff_readiness']
old_category = read(CAT)
a,o,b = span(old_category,'STP_postwar_nod_ultimatum')
threat_category = old_category[a:b]
a,o,b = span(threat_category,'visible')
threat_gate = threat_category[o+1:b-1].strip()
transfers = []
for name in foreign + domestic + threats:
    a,o,b = span(decisions,name)
    payload = decisions[a:b]
    if name in threats:
        if re.search(r'\bvisible\s*=\s*\{',payload):
            payload = prepend_inside(payload,'visible',threat_gate)
        else:
            payload = prepend_inside(payload,name,'\t\tvisible = { ' + threat_gate + ' }')
    target = 'STP_party_factions' if name in domestic else 'STP_cw_external_intervention'
    transfers.append((a,b,target,'\t'+payload))
for a,b,_,_ in sorted(transfers,reverse=True):
    start = decisions.rfind('\n',0,a)+1
    if not decisions[start:a].strip(): a=start
    if b < len(decisions) and decisions[b]=='\n': b+=1
    decisions = decisions[:a]+decisions[b:]
for target in ('STP_party_factions','STP_cw_external_intervention'):
    payloads = [payload for _,_,dest,payload in transfers if dest==target]
    decisions = append_inside(decisions,target,'\n'.join(payloads))
a,o,b=span(decisions,'STP_postwar_nod_ultimatum')
assert not parse_clausewitz(decisions[o+1:b-1]), 'Old threat category still owns decisions'
decisions=decisions[:a]+decisions[b:]

# A response is offered before payment only when its whole chain fits the cargo deadline.
for name,trigger in [('STP_ps_val_intelligence','STP_ps_val_intelligence_time_available'),
                     ('STP_ps_val_intercept','STP_ps_val_intercept_time_available'),
                     ('STP_ps_fund_nod','STP_ps_nod_credit_useful')]:
    def add_gate(body, gate=trigger):
        body=append_inside(body,'available','\t\t\tcustom_trigger_tooltip = { tooltip = '+gate+'_tt '+gate+' = yes }')
        a,o,b=span(body,'complete_effect')
        reward=body[a:b]
        reward=prepend_inside(reward,'limit',gate+' = yes',unique=False)
        return body[:a]+reward+body[b:]
    decisions=alter(decisions,name,add_gate)
write(DEC,decisions)
after_ids=[a.key for c in parse_clausewitz(decisions) for a in c.value if isinstance(a.value,list)]
assert sorted(before_ids)==sorted(after_ids), 'Decision loss or duplication during consolidation'

categories=read(CAT)
a,o,b=span(categories,'STP_postwar_nod_ultimatum')
categories=categories[:a]+categories[b:]
categories=alter(categories,'STP_elections_in_the_party',lambda body:set_block(body,'visible',
    '\t\tNOT = { has_global_flag = STP_cw_started }\n\t\tNOT = { has_country_flag = STP_cw_elections_finished }'))
categories=alter(categories,'STP_elections_in_the_party',lambda body:once(body,'visible_when_empty = yes','visible_when_empty = no'))
categories=alter(categories,'STP_cw_war_council',lambda body:once(body,'visible_when_empty = yes','visible_when_empty = no'))
def external_visible(body):
    a,o,b=span(body,'visible')
    visible=body[a:b]
    visible=append_inside(visible,'OR', '''
            AND = { tag = STP has_country_flag = STP_sided_with_the_party_flag STP_cw_preparation_open = yes }
            has_variable = STP_ps_nod_receipt_type
            has_variable = STP_ps_val_intelligence_deposit
            has_variable = STP_ps_val_intercept_deposit
            has_variable = STP_ps_val_pressure_deposit
            AND = { tag = STP has_country_flag = STP_cw_postwar OR = { has_country_flag = STP_pw_party_nod_threat_active has_country_flag = STP_pw_party_nod_invasion_active } }
''',unique=False)
    return body[:a]+visible+body[b:]
categories=alter(categories,'STP_cw_external_intervention',external_visible)
write(CAT,categories)

triggers=read(TRI)
new_triggers='''
# COUNTRY STP: reserve a full response chain plus one day before departure.
STP_ps_val_intelligence_time_available = {
    VAL = {
        has_active_mission = STP_ps_val_departure
        check_variable = { var = days_mission_timeout@STP_ps_val_departure value = 22 compare = greater_than_or_equals }
    }
}
STP_ps_val_intercept_time_available = {
    VAL = {
        has_active_mission = STP_ps_val_departure
        check_variable = { var = days_mission_timeout@STP_ps_val_departure value = 15 compare = greater_than_or_equals }
    }
}
# COUNTRY STP: funding is not a purchase of automatic military intervention.
STP_ps_nod_credit_useful = {
    NOD = {
        OR = {
            STP_ps_northern_front_active = yes
            NOD_cw_intervention_possible = yes
            AND = { has_country_flag = NOD_cw_entered has_war_with = STS }
        }
    }
}
'''
for name in ('STP_ps_val_intelligence_time_available','STP_ps_val_intercept_time_available','STP_ps_nod_credit_useful'):
    assert not re.search(r'^'+name+r'\s*=',triggers,re.M)
write(TRI,triggers.rstrip()+'\n'+new_triggers)
tokens=read(TOK)
if 'STP_ps_val_departure' not in tokens.splitlines(): write(TOK,tokens.rstrip()+'\nSTP_ps_val_departure\n')

# Preserve every existing wartime penalty; out-of-war refresh must be neutral.
effects=read(EFF)
def guard_recovery(body):
    old='limit = { check_variable = { var = STP_ps_stage'
    assert body.count(old)==3
    return body.replace(old,'limit = { STP_ps_war_active = yes check_variable = { var = STP_ps_stage')
effects=alter(effects,'STP_ps_refresh_defence',guard_recovery)
def affect_current_cargo(body):
    old='VAL = { set_country_flag = { flag = STP_ps_val_pressure_active value = 1 days = 60 } }'
    new='''VAL = {
                set_country_flag = { flag = STP_ps_val_pressure_active value = 1 days = 60 }
                if = {
                    limit = { has_active_mission = STP_ps_val_departure }
                    add_days_mission_timeout = { mission = STP_ps_val_departure days = 14 }
                }
            }'''
    return once(body,old,new)
effects=alter(effects,'STP_ps_val_pressure_finish',affect_current_cargo)
write(EFF,effects)

# The desk already permits all three tools in decisions, so expose all three unlocks.
focuses=read(FOC)
found=[]
for tree in parse_clausewitz(focuses):
    if tree.key=='focus_tree':
        for f in tree.value:
            if f.key=='focus' and scalar(f.value,'id')=='STP_ps_foreign_supply_desk': found.append(f)
assert len(found)==1
a,o,b=native_entry_span(focuses,found[0])
body=focuses[a:b]
body=append_inside(body,'completion_reward','\t\t\tunlock_decision_tooltip = STP_ps_val_intercept\n\t\t\tunlock_decision_tooltip = STP_ps_val_pressure')
write(FOC,focuses[:a]+body+focuses[b:])

# Defer the layout rebuild until the side-selection transaction has completed.
events=read(EVT)
assert not re.search(r'\bid\s*=\s*ADISCORD_STP_preparation\.26\b',events)
choice=[e for e in parse_clausewitz(events) if e.key=='country_event' and scalar(e.value,'id')=='ADISCORD_STP_preparation.1']
assert len(choice)==1
a,o,b=native_entry_span(events,choice[0])
body=events[a:b]
old='mark_focus_tree_layout_dirty = yes'
assert body.count(old)==2
body=body.replace(old,old+'\n\t\t\thidden_effect = { country_event = { id = ADISCORD_STP_preparation.26 hours = 1 } }')
events=events[:a]+body+events[b:]
events+='''

# The side flags and forced focus completion must settle before recalculating offsets.
country_event = {
    id = ADISCORD_STP_preparation.26
    hidden = yes
    is_triggered_only = yes
    trigger = {
        tag = STP
        NOT = { has_global_flag = STP_cw_started }
        OR = { has_country_flag = STP_sided_with_Maksim_flag has_country_flag = STP_sided_with_the_party_flag }
    }
    immediate = { mark_focus_tree_layout_dirty = yes }
}
'''
write(EVT,events)
actions=read(ACT)
assert not re.search(r'\bon_startup\s*=',actions)
hook='''
    on_startup = {
        effect = {
            STP = {
                if = {
                    limit = {
                        exists = yes
                        NOT = { has_global_flag = STP_cw_started }
                        OR = { has_country_flag = STP_sided_with_Maksim_flag has_country_flag = STP_sided_with_the_party_flag }
                    }
                    country_event = { id = ADISCORD_STP_preparation.26 hours = 1 }
                }
                if = {
                    limit = { exists = yes STP_ps_war_active = yes has_variable = STP_ps_stage }
                    STP_ps_refresh_defence = yes
                }
            }
        }
    }
'''
write(ACT,prepend_inside(actions,'on_actions',hook))

# Read status directly from receipts and mission clocks, without polling mirrors.
scripted=read(LOC)
assert 'name = STPGetPartyForeignReport' not in scripted
scripted+='''

defined_text = {
    name = STPGetPartyForeignReport
    text = { trigger = { tag = STP has_country_flag = STP_sided_with_the_party_flag } localization_key = STP_ps_foreign_report }
    text = { localization_key = STP_ps_empty }
}
defined_text = {
    name = STPGetPartyCargoStatus
    text = { trigger = { VAL = { has_active_mission = STP_ps_val_departure } } localization_key = STP_ps_cargo_departure_report }
    text = { trigger = { VAL = { has_variable = STP_ps_val_receipt_rifles } } localization_key = STP_ps_cargo_waiting_report }
    text = { localization_key = STP_ps_cargo_none_report }
}
'''
write(LOC,scripted)

copy={
'russian': {
'STP_party_factions':'Аппарат и подготовка',
'STP_cw_war_council':'Война и восстановление',
'STP_cw_external_intervention':'Внешние операции',
'STP_PARTY_ELECTION_BRIEFING':'§YЗадача партии§!: сохранить аппарат и ключевые округа до раскола.\nСледите за объявленными операциями подполья на карте: обыски без цели помогают Шабрату. Верность аппарата влияет на темп его подготовки; победа на выборах не отменяет гражданскую войну.\nПроекты правительства находятся в разделе §Y«Аппарат и подготовка»§!, помощь Нодрулу и поставки Кефрейта — во §Y«Внешних операциях»§!.',
'STP_party_factions_desc':'Поддержка определяет готовность фракции сотрудничать, влияние — вес её требований. Договаривайтесь с теми, кто нужен выбранному курсу, а не со всеми подряд.\n[STPGetPartyPreparationReport]',
'STP_ps_preparation_report':'§YПодготовка правительства§!\nРадиосеть и резервный штаб сокращают оплаченные этапы реорганизации армии. Эвакуационный план — отдельная страховка при потере столицы. Проект даёт результат только после завершения своей миссии; фокус открывает заказ, но не оплачивает его.',
'STP_ps_war_report':'\n§YРеорганизация армии: [?STP_ps_stage|0]/4§!\n[STPGetPartyGovernment]\nПрорыв: §R[?STP_ps_breakthrough|%0]§!; планирование: §R[?STP_ps_planning|%0]§!. Оборона этим штрафом не затронута. Завершайте этапы через решения ниже; потеря работающего правительства приостанавливает подготовку.',
'STP_cw_war_council_desc':'Выберите необходимую программу, проверьте её цену и срок. Формирование войск расходует реальные резервы.\n[STPGetPartySurvival][STPGetRecoveryReport][STPGetKefreytArmyCommitment]',
'STP_cw_external_intervention_desc':'Здесь находятся помощь союзникам, противодействие поставкам и действующие внешние угрозы. Каждый заказ имеет собственные условия доставки.\n[STPGetPartyForeignReport]',
'STP_ps_foreign_report':'§YНодрул:§! [STPGetNodStatus]\n§YКефрейт:§! [STPGetPartyCargoStatus]\nРазведка занимает 7 дней, перехват — ещё 14. Оплачивайте ответ до истечения окна поставки.',
'STP_ps_cargo_departure_report':'до отправки груза §Y[?VAL.days_mission_timeout@STP_ps_val_departure|0]§! дн.',
'STP_ps_cargo_waiting_report':'груз ожидает открытия маршрута; точного окна перехвата сейчас нет.',
'STP_ps_cargo_none_report':'активной поставки нет.',
'STP_ps_val_intelligence_time_available_tt':'До отправки груза осталось не менее 22 дней: 7 на разведку, 14 на перехват и 1 день запаса.',
'STP_ps_val_intercept_time_available_tt':'До отправки груза осталось не менее 15 дней: 14 на перехват и 1 день запаса.',
'STP_ps_nod_credit_useful_tt':'Нодрул ведёт северную войну, может подготовить вмешательство или уже воюет с сопротивлением.',
'STP_ps_val_intelligence_desc':'За 7 дней установим маршрут текущей поставки. Это открывает её перехват, который потребует ещё 14 дней и отдельной оплаты. Для начала разведки нужно не менее 22 дней до отправки. Если поставка исчезнет или сменится, незавершённый заказ возвращает оплату.',
'STP_ps_val_intercept_desc':'За 14 дней подготовим перехват разведанной поставки по действующему сухопутному маршруту. Захваченный груз поступит на наши склады вместо складов сопротивления. Начать можно, пока до отправки осталось не менее 15 дней. При срыве условий незавершённый заказ возвращает оплату.',
'STP_ps_val_pressure_desc':'За 21 день организуем давление на поставщиков. По завершении действующая подготовка груза, если она ещё идёт, продлится на 14 дней. Новые поставки, начатые в следующие 60 дней, также готовятся на 14 дней дольше. Уже отправленный груз это не возвращает.',
'STP_ps_fund_nod_desc':'Передадим Нодрулу 1500 из казны для военных закупок. Подготовка отправки занимает 14 дней, доставка — ещё 7 после открытия маршрута. Деньги получает Нодрул, не наша армия; это не покупка автоматического вступления в войну. До отправки заказ можно отменить с возвратом.',
'STP_ps_foreign_supply_desk_desc':'Откроем разведку поставок Кефрейта, их перехват и давление на поставщиков. Выбирайте между захватом конкретного груза и задержкой снабжения; каждая операция требует времени и собственного бюджета.'
},
'english': {
'STP_party_factions':'Apparatus and Preparation',
'STP_cw_war_council':'War and Recovery',
'STP_cw_external_intervention':'Foreign Operations',
'STP_PARTY_ELECTION_BRIEFING':'§YParty objective§!: preserve the apparatus and key districts before the split.\nWatch announced underground operations on the map: searches without a target help Shabrat. Apparatus loyalty affects the pace of his preparations; an election victory does not prevent civil war.\nGovernment projects are under §YApparatus and Preparation§!; aid to Nodrul and Kefreyt shipments are under §YForeign Operations§!.',
'STP_party_factions_desc':'Support determines a faction\'s willingness to cooperate; influence determines the weight of its demands. Negotiate with the factions needed for your chosen course, not all of them at once.\n[STPGetPartyPreparationReport]',
'STP_ps_preparation_report':'§YGovernment preparation§!\nThe radio network and reserve headquarters shorten funded army reorganisation stages. The evacuation plan is separate insurance against losing the capital. A project delivers only when its mission finishes; its focus unlocks the order but does not pay for it.',
'STP_ps_war_report':'\n§YArmy reorganisation: [?STP_ps_stage|0]/4§!\n[STPGetPartyGovernment]\nBreakthrough: §R[?STP_ps_breakthrough|%0]§!; planning: §R[?STP_ps_planning|%0]§!. This penalty does not affect defence. Complete the stages through the decisions below; losing an operational government pauses preparation.',
'STP_cw_war_council_desc':'Choose the programme you need and check its price and duration. Unit formation consumes real reserves.\n[STPGetPartySurvival][STPGetRecoveryReport][STPGetKefreytArmyCommitment]',
'STP_cw_external_intervention_desc':'Allied aid, shipment countermeasures and active foreign threats are managed here. Each order has its own delivery conditions.\n[STPGetPartyForeignReport]',
'STP_ps_foreign_report':'§YNodrul:§! [STPGetNodStatus]\n§YKefreyt:§! [STPGetPartyCargoStatus]\nIntelligence takes 7 days; interception takes another 14. Fund a response before the shipment window closes.',
'STP_ps_cargo_departure_report':'cargo departs in §Y[?VAL.days_mission_timeout@STP_ps_val_departure|0]§! days.',
'STP_ps_cargo_waiting_report':'cargo awaits an open route; there is no confirmed interception window.',
'STP_ps_cargo_none_report':'no active shipment.',
'STP_ps_val_intelligence_time_available_tt':'At least 22 days remain before departure: 7 for intelligence, 14 for interception and a 1-day margin.',
'STP_ps_val_intercept_time_available_tt':'At least 15 days remain before departure: 14 for interception and a 1-day margin.',
'STP_ps_nod_credit_useful_tt':'Nodrul is fighting in the north, can prepare intervention, or is already fighting the resistance.',
'STP_ps_val_intelligence_desc':'Identify the current shipment\'s route in 7 days. Interception then needs another 14 days and a separate payment. Start intelligence with at least 22 days remaining before departure. An unfinished order refunds its payment if the shipment disappears or changes.',
'STP_ps_val_intercept_desc':'Prepare to intercept the identified shipment along its active land route in 14 days. Captured cargo reaches our stockpiles instead of the resistance. Start with at least 15 days remaining before departure. An unfinished order refunds its payment if its conditions cease to hold.',
'STP_ps_val_pressure_desc':'Organise supplier pressure over 21 days. On completion, a shipment still being prepared is delayed by 14 days. New shipments started over the following 60 days also take 14 extra days to prepare. Cargo that has already departed cannot be recalled.',
'STP_ps_fund_nod_desc':'Transfer 1500 from the treasury to Nodrul for military procurement. Dispatch preparation takes 14 days; delivery takes another 7 once the route opens. Nodrul receives the money, not our army; this does not buy automatic war entry. Cancel before departure to recover the payment.',
'STP_ps_foreign_supply_desk_desc':'Unlock intelligence on Kefreyt shipments, interception and supplier pressure. Choose between seizing a specific cargo and delaying supplies; each operation needs time and its own budget.'
}}
for lang,values in copy.items():
    path='localisation/'+lang+'/ADISCORD_STP_l_'+lang+'.yml'
    text=read(path)
    lines=text.splitlines()
    for key,value in values.items():
        value=value.replace('\\','\\\\').replace('"','\\"').replace('\n','\\n')
        matches=[i for i,line in enumerate(lines) if re.match(r'^ '+re.escape(key)+r':',line)]
        assert len(matches)<=1,key
        line=' '+key+':0 "'+value+'"'
        if matches: lines[matches[0]]=line
        else: lines.append(line)
    write(path,'\n'.join(lines)+'\n')
    assert Path(path).read_bytes().startswith(b'\xef\xbb\xbf'), path

for path in sorted(changed):
    if path.endswith('.txt') and path != TOK: parse_clausewitz(read(path))
print('APPLIED_FILES',sorted(changed))
print('PRESERVED_DECISIONS',len(after_ids))
