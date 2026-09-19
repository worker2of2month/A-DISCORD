"""Temporary review-branch patch driver; not shipped to the gameplay branch."""
from pathlib import Path
import ast
import json
import re
import sys
sys.path.insert(0, str(Path.cwd()))
from tools.tests.test_validate_adiscord_val_rework import named_block_spans

CHANGED = set()

def load(path):
    return Path(path).read_bytes().decode('utf-8-sig')

def save(path, text):
    p = Path(path)
    bom = p.read_bytes().startswith(b'\xef\xbb\xbf')
    p.write_bytes((b'\xef\xbb\xbf' if bom else b'') + text.encode('utf-8'))
    CHANGED.add(str(p))

def replace(text, old, new, count=1):
    assert text.count(old) == count, (old[:120], text.count(old), count)
    return text.replace(old, new)

def edit(path, identifier, transform, focus=False):
    text = load(path)
    matches = named_block_spans(text, 'focus' if focus else identifier)
    if focus:
        matches = [b for b in matches if re.search(r'\bid\s*=\s*'+re.escape(identifier)+r'\b', b.text)]
    assert len(matches) == 1, (path, identifier, len(matches))
    b = matches[0]
    new = transform(b.text)
    assert new != b.text, (identifier, 'no change')
    save(path, text[:b.start] + new + text[b.end:])

def append_to_block(text, name, content, indent='\t\t\t'):
    matches = named_block_spans(text, name)
    assert len(matches) == 1, (name,len(matches))
    b = matches[0]
    body = b.text[:-1].rstrip() + '\n' + '\n'.join(indent+l if l else '' for l in content.splitlines()) + '\n' + indent[:-1] + '}'
    return text[:b.start] + body + text[b.end:]

def reward(path, identifier, content):
    edit(path, identifier, lambda text: append_to_block(text, 'completion_reward', content), focus=True)

def idea(path, identifier, name, fields):
    declaration = '\n\t\t'+identifier+' = {\n\t\t\tname = '+name+'\n\t\t\tallowed = { always = no }\n\t\t\tmodifier = {\n'
    declaration += ''.join('\t\t\t\t'+k+' = '+v+'\n' for k,v in fields.items())
    declaration += '\t\t\t}\n\t\t}\n'
    edit(path, 'country', lambda text: text[:-1].rstrip() + '\n' + declaration + '\t}')

def loc(path, key, value):
    text = load(path)
    pattern = re.compile(r'(?m)^([ \t]*)'+re.escape(key)+r':(?:\d+)?[ \t]*"[^\r\n]*"[ \t]*$')
    matches=list(pattern.finditer(text))
    assert len(matches) == 1, (path,key,len(matches))
    m=matches[0]
    text=text[:m.start()] + m[1] + key + ':0 "'+value+'"' + text[m.end():]
    save(path,text)

ECON='common/scripted_effects/ADISCORD_economy_effects.txt'
VAL='common/national_focus/ADISCORD_national_focus_VAL.txt'
VE='common/scripted_effects/ADISCORD_VAL_effects.txt'
VT='common/scripted_triggers/ADISCORD_VAL_rework_triggers.txt'
VD='common/decisions/ADISCORD_VAL_decisions.txt'
VI='common/ideas/ADISCORD_VAL_rework_ideas.txt'
VL='localisation/russian/ADISCORD_VAL_decisions_l_russian.yml'
STP='common/national_focus/ADISCORD_national_focus_STP.txt'
SI='common/ideas/ADISCORD_STP_civil_war_ideas.txt'
SL='localisation/russian/ADISCORD_STP_l_russian.yml'

# Monthly source coefficients: weekly conversion and every expense stay intact.
for effect, substitutions in {
    'calculate_personal_income': [('var = ADISCORD_economy_personal_income value = 1.2','var = ADISCORD_economy_personal_income value = 10'),('var = ADISCORD_economy_personal_factory_temp value = 0.06','var = ADISCORD_economy_personal_factory_temp value = 0.36'),('var = ADISCORD_economy_personal_income min = 0 max = 50','var = ADISCORD_economy_personal_income min = 0 max = 100')],
    'calculate_business_income': [('var = ADISCORD_economy_business_income value = 0.075','var = ADISCORD_economy_business_income value = 0.45'),('var = ADISCORD_economy_business_building_temp value = 1.05','var = ADISCORD_economy_business_building_temp value = 2.10'),('var = ADISCORD_economy_business_income min = 0 max = 100','var = ADISCORD_economy_business_income min = 0 max = 150')],
    'calculate_consumer_goods_income': [('var = ADISCORD_economy_consumer_goods_income value = 0.035','var = ADISCORD_economy_consumer_goods_income value = 0.21'),('var = ADISCORD_economy_consumer_goods_income min = 0 max = 50','var = ADISCORD_economy_consumer_goods_income min = 0 max = 100')],
    'calculate_factory_income': [('var = ADISCORD_economy_factory_income value = 0.015','var = ADISCORD_economy_factory_income value = 0.06')],
    'calculate_resource_income': [('var = ADISCORD_economy_resource_income value = 0.32','var = ADISCORD_economy_resource_income value = 0.48')],
}.items():
    def transform(text, pairs=substitutions):
        for old,new in pairs: text=replace(text,old,new)
        return text
    edit(ECON,'ADISCORD_economy_'+effect,transform)

# Fiscal reforms use the existing contract aggregate and survive authority bands.
fiscal='''\tset_variable = { var = VAL_contract_overall_income_factor value = 0 }
\tset_variable = { var = VAL_contract_admin_expense_factor value = 0 }
\tif = {
\t\tlimit = { has_variable = VAL_fiscal_administration_investment }
\t\tadd_to_variable = { var = VAL_contract_overall_income_factor value = VAL_fiscal_administration_investment }
\t\tset_variable = { var = VAL_contract_admin_expense_factor value = VAL_fiscal_administration_investment }
\t\tmultiply_variable = { var = VAL_contract_admin_expense_factor value = -0.5 }
\t}
'''
edit(VE,'VAL_refresh_contract_modifier',lambda text:text[:text.index('{')+1]+'\n'+fiscal+text[text.index('{')+1:])
edit('common/dynamic_modifiers/ADISCORD_VAL_contract_dynamic_modifier.txt','VAL_contract_state',lambda text:text[:-1].rstrip()+'''\n\tADISCORD_economy_overall_income_factor = VAL_contract_overall_income_factor
\tADISCORD_economy_admin_expense_factor = VAL_contract_admin_expense_factor
}''')
helper='''
VAL_invest_fiscal_administration = {
\teffect_tooltip = { swap_ideas = { remove_idea = VAL_contract_delta_dummy add_idea = VAL_fiscal_administration_delta } }
\thidden_effect = {
\t\tadd_to_variable = { var = VAL_fiscal_administration_investment value = 0.10 }
\t\tVAL_refresh_contract_modifier = yes
\t\tADISCORD_economy_mark_dirty = yes
\t}
}
'''
edit(VE,'VAL_invest_civilian_industry',lambda text:text+'\n'+helper)
idea(VI,'VAL_fiscal_administration_delta','VAL_contract_state',{'ADISCORD_economy_overall_income_factor':'0.10','ADISCORD_economy_admin_expense_factor':'-0.05'})
for identifier in ('VAL_Contract_Accounting_Office','VAL_Export_Clearing_House','VAL_Industrial_Mobilization_Plan'):
    reward(VAL,identifier,'VAL_invest_fiscal_administration = yes')
reward(VAL,'VAL_Vorkerland_Contracts_Burn','ADISCORD_economy_receive_100 = yes')

# The northern route is available to a neutral VAL after the regional war too.
edit(VAL,'VAL_frontier_conference',lambda text:replace(text,'prerequisite = { focus = VAL_The_Steel_Contract }','prerequisite = { focus = VAL_The_Steel_Contract focus = VAL_Market_Roads_North }'),focus=True)
edit(VAL,'VAL_frontier_conference',lambda text:replace(text,'available = { VAL_frontier_postwar = yes }','available = { custom_trigger_tooltip = { tooltip = VAL_frontier_postwar_ready_tt VAL_frontier_postwar = yes } }'),focus=True)
reward(VAL,'VAL_frontier_security_plan','add_political_power = 75')
reward(VAL,'VAL_frontier_logistics','add_equipment_to_stockpile = { type = motorized_equipment amount = 100 producer = VAL }')

readiness='''
# COUNTRY VAL: count fielded soldiers and replacements, not only unit counters.
VAL_ai_frontier_force_ready = {
\thas_capitulated = no
\tis_subject = no
\thas_war = no
\tNOT = { num_divisions < 12 }
\thas_army_manpower = { size > 59999 }
\tNOT = { has_equipment = { infantry_equipment < 1500 } }
\tNOT = { check_variable = { var = ADISCORD_economy_debt_crisis_level value = 3 compare = greater_than_or_equals } }
\tOR = {
\t\tADISCORD_economy_can_spend_50 = yes
\t\tcheck_variable = { var = ADISCORD_economy_weekly_balance value = 0 compare = greater_than_or_equals }
\t}
}
'''
edit(VT,'VAL_ai_frontier_preparation',lambda text:readiness+'\n'+text)
for identifier in ('VAL_frontier_demand_CIN','VAL_frontier_demand_OSF','VAL_frontier_demand_APH','VAL_frontier_demand_ERT','VAL_frontier_begin_offensive'):
    def ai(text):
        b=named_block_spans(text,'ai_will_do')
        assert len(b)==1
        new='ai_will_do = { base = 20 modifier = { factor = 0 VAL_ai_frontier_force_ready = no } }'
        return text[:b[0].start]+new+text[b[0].end:]
    edit(VD,identifier,ai)

priorities={
    'VAL_The_Contract_State':30,'VAL_The_Weaponry_Baron':15,
    'VAL_Price_Of_Loyalty':10,'VAL_Count_The_Captains':10,'VAL_One_Ledger_One_Banner':10,
    'VAL_Factories_Like_Cathedrals':18,'VAL_Keep_The_Lines_Hot':12,'VAL_Contract_Accounting_Office':16,
    'VAL_Vorkerland_Contracts_Burn':60,'VAL_Inventory_The_Empty_Yards':50,
    'VAL_Mobilize_Machine_Shops':30,'VAL_Three_Shift_Arsenals':30,'VAL_Arsenal_Reserve':20,
    'VAL_Reserve_Accounting':25,'VAL_Industrial_Mobilization_Plan':40,
    'VAL_Market_Roads_North':20,'VAL_frontier_conference':40,'VAL_frontier_logistics':35,
    'VAL_frontier_commissioners':25,'VAL_frontier_provincial_offices':25,'VAL_frontier_security_plan':45,
}
for identifier,base in priorities.items():
    def priority(text, base=base):
        b=named_block_spans(text,'ai_will_do');assert len(b)==1
        return text[:b[0].start]+'ai_will_do = { base = '+str(base)+' }'+text[b[0].end:]
    edit(VAL,identifier,priority,focus=True)

# Native previews share the same name as the live, cumulative republic modifier.
reforms={
 'count_the_cost': {
    'STP_pw_ADISCORD_economy_overall_income_factor':('0.03','0.08'),
    'STP_pw_ADISCORD_economy_treasury_capacity_factor':('0.03','0.05')},
 'reopen_tax_offices': {
    'STP_pw_ADISCORD_economy_overall_income_factor':('0.05','0.15'),
    'STP_pw_ADISCORD_economy_admin_expense_factor':('-0.03','-0.08')},
 'repair_workshops': {
    'STP_pw_production_speed_industrial_complex_factor':('0.05','0.15'),
    'STP_pw_ADISCORD_economy_treasury_capacity_factor':('0.05','0.10')},
 'stabilize_currency': {
    'ADISCORD_economy_inflation':('-3','-8'),
    'ADISCORD_economy_deficit_pressure':('-5','-10'),
    'STP_pw_ADISCORD_economy_creditworthiness_factor':('0.08','0.15'),
    'STP_pw_ADISCORD_economy_treasury_capacity_factor':('0.02','0.05')},
 'recovery_budget': {
    'STP_pw_ADISCORD_economy_overall_income_factor':('0.07','0.12'),
    'STP_pw_ADISCORD_economy_treasury_capacity_factor':('0.05','0.10'),
    'STP_pw_ADISCORD_economy_admin_expense_factor':('-0.02','-0.07'),
    'STP_pw_ADISCORD_country_development_economic_growth_factor':('0.08','0.15')},
}
for suffix, changes in reforms.items():
    identifier='STP_pc_economy_'+suffix
    def reform(text, changes=changes):
        for variable,(old,new) in changes.items():
            text=replace(text,f'var = {variable} value = {old} }}',f'var = {variable} value = {new} }}')
        return text
    edit(STP,identifier,reform,focus=True)
    preview='STP_pw_economy_'+suffix+'_delta'
    fields={variable.removeprefix('STP_pw_'):new for variable,(_,new) in changes.items() if variable.startswith('STP_pw_')}
    idea(SI,preview,'STP_pw_republic_dynamic',fields)
    reward(STP,identifier,'effect_tooltip = { add_ideas = '+preview+' }')
reward(STP,'STP_pc_economy_count_the_cost','ADISCORD_economy_receive_100 = yes')

# Keep only unique mechanics in custom prose; native effects own numeric previews.
loc(SL,'STP_pc_economy_count_the_cost','Единая государственная казна')
loc(SL,'STP_pc_economy_count_the_cost_tt','Доходы и расходы будут пересчитаны по всей объединённой территории. Реформы накапливаются в национальном духе послевоенной республики.')
loc(SL,'STP_pc_economy_reopen_tax_offices','Налоговая служба республики')
loc(SL,'STP_pc_economy_reopen_tax_offices_tt','Единый реестр плательщиков превращает военные поборы в постоянный доход государства.')
loc(SL,'STP_pc_economy_repair_workshops_tt','Гражданская фабрика строится в принадлежащем нам подконтрольном стеландском регионе со свободным местом. При отсутствии подходящего региона вместо неё поступит §G100§! в казну.')
loc(SL,'STP_pc_economy_stabilize_currency','Денежная стабилизация')
loc(SL,'STP_pc_economy_stabilize_currency_tt','Инфляция: §G-8§! п.п. Давление дефицита: §G-10§! п.п. Показатели не опускаются ниже нуля.')
loc(SL,'STP_pc_economy_recovery_budget','Первый бюджет развития')
loc(SL,'STP_pc_economy_recovery_budget_tt','Постоянные доходы, управление расходами и гражданское производство объединяются в программу долгосрочного восстановления.')

names={
 'VAL_Factories_Like_Cathedrals':('Модернизация оружейных заводов','Оружейные заводы остаются главным капиталом Кефрейта. Единый заказ на оборудование и ремонт позволит увеличить выпуск уже работающих арсеналов, не расходуя средства на пустующие корпуса.'),
 'VAL_Keep_The_Lines_Hot':('Непрерывный производственный цикл','Сменные графики, запас комплектующих и общие стандарты обслуживания должны устранить простои. Существующие мощности будут работать устойчивее, а первая партия пополнит оружейный резерв.'),
 'VAL_Export_Rifles_Not_Promises':('Национальное экспортное бюро','Экспорт требует не обещаний капитанов, а оплаченных заказов и надёжной поставки. Бюро связывает внешние контракты с реальными запасами оружия и не подменяет покупателя государственными субсидиями.'),
 'VAL_Contract_Accounting_Office':('Промышленный бюджет','Учёт государственных заказов объединит счета арсеналов, налоговые платежи и производственные планы. Реформа увеличивает постоянный доход казны и сокращает стоимость административного аппарата.'),
 'VAL_Salvage_Every_Barrel':('Восстановление оружейных резервов','Складские комиссии вернут пригодное оружие в оборот. Разбор списанного имущества позволит собрать резерв без отвлечения новых производственных линий.'),
 'VAL_Vorkerland_Contracts_Burn':('Разрыв воркерландских поставок','Распад главного рынка оставил арсеналы без оплаты, а поставщиков без гарантий. Закроем наиболее опасные обязательства и направим высвобожденные резервы на сохранение производства. Первая из шести антикризисных программ.'),
 'VAL_Inventory_The_Empty_Yards':('Инвентаризация промышленности','Правительству нужны проверенные данные о станках, сырье и незавершённых заказах. Инвентаризация определит, какие предприятия можно вернуть к работе немедленно, а какие нуждаются в переоснащении.'),
 'VAL_Mobilize_Machine_Shops':('Программа станкостроения','Зависимость от привозного оборудования делает любой разрыв торговли промышленной катастрофой. Машинные мастерские получат общий план ремонта и выпуска станков для кефрейтских заводов.'),
 'VAL_Three_Shift_Arsenals':('Расширение серийного производства','Восстановленные станки должны выпускать совместимые изделия крупными сериями. Переход на устойчивый сменный режим закрепит результат промышленной реконструкции.'),
 'VAL_Reserve_Accounting':('Система стратегических запасов','Запасы сырья и оружия будут учитывать по общим нормам. Это позволит снабжать действующую армию, выполнять внешние заказы и не останавливать заводы при очередном срыве поставок.'),
 'VAL_Industrial_Mobilization_Plan':('Новая промышленная политика','Антикризисные меры складываются в постоянную систему: производственные стандарты, управляемые резервы и предсказуемые расчёты. Закрепим восстановление промышленности и расширим доходную базу контрактного государства.'),
 'VAL_Export_Clearing_House':('Расчёты без посредников','Экспортная палата сведёт встречные обязательства и направит платежи в государственный бюджет без цепочки частных сборщиков. Доходная база расширится, административные издержки сократятся.'),
 'VAL_Northern_Clearing_House':('Второй экспортный стол','Отдельная группа расчётов позволит обслуживать второй оружейный контракт. Каждый договор по-прежнему требует собственного покупателя, его согласия на оплату и реальной партии оружия.'),
 'VAL_Market_Roads_North':('Северные торговые маршруты','Племенные рынки могут заменить часть утраченного сбыта. Откроем постоянные торговые представительства и подготовим северное направление внешней политики.'),
 'VAL_frontier_conference':('Доктрина северной экспансии','После завершения стеландских войн Кефрейт может сосредоточиться на северных территориях. Торговая сеть или завершённая стеландская кампания дают основание для новой политики. Участие в гражданской войне не является обязательным.'),
 'VAL_frontier_security_plan':('Мандат на северную кампанию','Правительство утвердит цели экспедиции и выделит политический ресурс на первый ультиматум. Отказ племён откроет решение о начале наступления. Армия должна иметь действующие части и запас оружия, а не формально раздутое число дивизий.'),
}
for identifier,(name,description) in names.items():
    loc(VL,identifier,name)
    loc(VL,identifier+'_desc',description)
save(VL,load(VL).rstrip()+'\n VAL_frontier_postwar_ready_tt:0 "Стеландские войны завершены; Кефрейт независим, не капитулировал и не выведен из регионального противостояния условиями поражения."\n')

# Repair the stale assertions from the already-present budget reduction patch.
p='tools/validators/validate_adiscord_economy_ai.py'; text=load(p)
text=replace(text,'expected = {"1": 0.60, "2": 0.80, "3": 1.00, "4": 1.30, "5": 1.60}', 'expected = {"1": 0.30, "2": 0.65, "3": 1.00, "4": 1.30, "5": 1.60}')
text=replace(text,'if len(all_multipliers) == 5','if len(all_multipliers) == 6\n        and sum(_direct_scalar(item.value, "value") == "2.00" for item in all_multipliers) == 1')
text=replace(text,'("0.45", "0.70", "1.00", "1.35", "1.80")','("0.25", "0.60", "1.00", "1.35", "1.80")')
save(p,text)
p='tools/tests/test_adiscord_economy_weekly_contracts.py';text=load(p)
text=replace(text,'1: ("§G-40%§!", "§R-8%§!")','1: ("§G-70%§!", "§R-8%§!")')
text=replace(text,'2: ("§G-20%§!", "§R-3%§!")','2: ("§G-35%§!", "§R-3%§!")')
text=replace(text,'self.assertEqual(multipliers, {0.60, 0.80, 1.00, 1.30, 1.60})','self.assertEqual(multipliers, {0.30, 0.65, 1.00, 1.30, 1.60, 2.00})')
save(p,text)
p='localisation/english/ADISCORD_economy_l_english.yml';text=load(p)
m=re.search(r'(?m)^\s*ADISCORD_economy_research_controls_tt:[^\n]+',text);assert m
line=m[0]
# Match the Russian explanatory level range without changing gameplay numbers.
first_quote=line.index('"')
line=line[:first_quote+1]+'Levels 1-5. '+line[first_quote+1:]
save(p,text[:m.start()]+line+text[m.end():])

# The authored reconstruction sequence includes the dedicated recovery branch.
p='tools/validators/validate_adiscord_stp_shabrat_ai.py';text=load(p)
module=ast.parse(text)
node=next(n for n in module.body if isinstance(n,(ast.Assign,ast.AnnAssign)) and
          ((isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='RECONSTRUCTION_FOCUSES' for t in n.targets)) or
           (isinstance(n,ast.AnnAssign) and isinstance(n.target,ast.Name) and n.target.id=='RECONSTRUCTION_FOCUSES')))
expected=('STP_cw_first_postwar_budget','STP_cw_restore_civil_authority','STP_pc_after_victory','STP_pc_economy_count_the_cost','STP_pc_economy_reopen_tax_offices','STP_pc_economy_repair_workshops','STP_pc_economy_stabilize_currency','STP_pc_economy_recovery_budget','STP_pc_development_country_must_live','STP_pc_development_posters_on_ruins','STP_pc_development_rebuild_as_duty','STP_pc_development_engineers_on_radio','STP_pc_development_reopen_universities','STP_pc_development_generation_reconstruction','STP_pc_development_national_research_institutes','STP_pc_shabrat_cabinet','STP_pw_republic_new_republic','STP_pw_republic_district_authority','STP_pw_republic_civil_records','STP_pw_republic_firm_settlement','STP_pw_republic_civil_charter','STP_pw_republic_restore_roads','STP_pw_republic_homes_for_returnees','STP_pw_republic_civil_workshops','STP_pw_republic_accountable_arsenals','STP_pw_republic_industrial_settlement','STP_pw_republic_army_register','STP_pw_republic_officer_school','STP_pw_republic_supply_service','STP_pw_republic_professional_service','STP_pw_republic_settled_state')
lines=text.splitlines(keepends=True)
lines[node.lineno-1:node.end_lineno]=['RECONSTRUCTION_FOCUSES = (\n'+''.join('    '+repr(s)+',\n' for s in expected)+')\n']
save(p,''.join(lines))

p='docs/economy/economy-player-and-runtime.md'
section='''
## Производство и доходная база

До применения налогов и национальных модификаторов месячная база личных
доходов равна 10 плюс 0,36 за гражданскую фабрику. Гражданская фабрика также
даёт 0,45 делового дохода и 0,21 дохода гражданского выпуска. Деловой центр
добавляет 2,10 к базе услуг до поправки экономической модели и 0,25 прямого
дохода. Ресурсная рента использует коэффициент 0,48 от кэшированного
ресурсного обеспечения; отсутствие ресурсов не создаёт ренту.
Военные заводы при разрешённом экспортном профиле дают 0,06 за завод,
но сохраняют содержание. Это не замена оружейным контрактам.

Коэффициенты меняют источники месячного дохода, а не единицу денег: цены,
долги, расходы и перевод 3/13 остаются самостоятельными частями расчёта.
Налоговый предпросмотр берёт ту же увеличенную базу, что недельная выплата.
Казна не пополняется при повторном открытии окна или пересчёте прогноза.
'''
save(p,load(p).rstrip()+'\n'+section)
p='docs/development/focus-effects.md'
section='''
## Фискальные реформы и северная кампания

Кефрейт проводит три фискальные реформы: промышленный бюджет, расчёты без
посредников и новая промышленная политика. Каждая прибавляет 0,10 к
`VAL_fiscal_administration_investment`. Национальный контрактный агрегат
применяет накопление как общий доход и половину его величины со знаком минус
как административный расход. Смена авторитета не сбрасывает вложения;
`VAL_fiscal_administration_delta` показывает только прибавку очередной реформы.
Шесть антикризисных ступеней промышленности сохраняют собственный прогресс.

Северная конференция требует завершения стеландских войн и допускает одну
из двух предпосылок: стальной контракт либо северные торговые маршруты.
Мандат открывает существующие ультиматумы и выдаёт 75 политической власти
на первый из них. ИИ проверяет не менее 12 дивизий, свыше 59999 человек
в действующей армии, 1500 винтовок в резерве, отсутствие войны и тяжёлого
долгового чрезвычайного положения. Для начала нужны 50 казны либо
неотрицательный недельный баланс. Это только правило ИИ; игрок сохраняет
доступ к существующей цепочке выбора. Коалиции и условия мира не обходятся.

Пять экономических фокусов Шабрата суммарно дают +35% общего дохода,
-15% административных расходов, +30% ёмкости казны, +15% строительства
гражданской промышленности, +15% кредитоспособности и +15% роста
экономического развития. Каждая прибавка показывается native dummy idea
с именем действующего республиканского агрегата. Денежная стабилизация
снижает инфляцию на 8 п.п. и давление дефицита на 10 п.п. с нижней границей 0.
Единая казна и бюджет развития дают по 100 казны; мастерские строят одну
гражданскую фабрику или выдают 100 при отсутствии подходящего региона.
'''
save(p,load(p).rstrip()+'\n'+section)

Path('/tmp/economy-changed-paths.json').write_text(json.dumps(sorted(CHANGED)),encoding='utf-8')
for path in sorted(CHANGED):
    raw=Path(path).read_bytes()
    assert (not path.startswith('common/')) or not raw.startswith(b'\xef\xbb\xbf'), path
    assert (not path.startswith('localisation/')) or raw.startswith(b'\xef\xbb\xbf'), path
print('PATCHED PATHS',json.dumps(sorted(CHANGED)))
