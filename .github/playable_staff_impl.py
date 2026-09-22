from pathlib import Path
import re
import sys

ROOT=Path(sys.argv[1]).resolve()
sys.path.insert(0,str(ROOT))
from tools.tests.test_adiscord_stp_preparation import parse_clausewitz, block, scalar

def read(p):return (ROOT/p).read_text(encoding='utf-8-sig')
def write(p,s):
    target=ROOT/p;target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(s,encoding='utf-8-sig' if p.endswith('.yml') else 'utf-8')
def span(text,key,start=0):
    m=re.search(r'(?m)(?<![\w.])'+re.escape(key)+r'\s*=\s*\{',text[start:])
    assert m,key
    a=start+m.start();i=start+m.end()-1;op=i;depth=0;quoted=False;comment=False;escape=False
    while i<len(text):
        c=text[i]
        if comment:
            if c=='\n':comment=False
        elif quoted:
            if escape:escape=False
            elif c=='\\':escape=True
            elif c=='"':quoted=False
        elif c=='#':comment=True
        elif c=='"':quoted=True
        elif c=='{':depth+=1
        elif c=='}':
            depth-=1
            if depth==0:return a,op,i+1
        i+=1
    raise AssertionError('unclosed '+key)
def extend(p,key,content):
    s=read(p);a,o,b=span(s,key);cl=s.rfind('\n',0,b-1)+1
    if s[cl:b-1].strip():cl=b-1
    s=s[:cl]+'\n'+content+'\n'+s[cl:];write(p,s)
def append(p,content):write(p,read(p).rstrip()+'\n\n'+content.rstrip()+'\n')
def idea_add(p,slot,content):
    s=read(p);a,o,b=span(s,'ideas')
    if re.search(r'(?m)^\s*'+re.escape(slot)+r'\s*=\s*\{',s[o:b]):extend(p,slot,content)
    else:extend(p,'ideas','\t'+slot+' = {\n'+content+'\n\t}')
def replace_once(p,a,b):
    s=read(p);assert s.count(a)==1,(p,a,s.count(a));write(p,s.replace(a,b))
def focus_reward(country,fid,content):
    p=f'common/national_focus/ADISCORD_national_focus_{country}.txt';s=read(p)
    matches=list(re.finditer(r'\bid\s*=\s*'+re.escape(fid)+r'\b',s));assert len(matches)==1,fid
    a,o,b=span(s,'completion_reward',matches[0].end())
    next_focus=s.find('\n\tfocus = {',matches[0].end());assert next_focus<0 or a<next_focus,fid
    write(p,s[:o+1]+'\n'+content+s[o+1:])

IDEAS={'STP':'common/ideas/ADISCORD_STP_civil_war_ideas.txt','VAL':'common/ideas/ADISCORD_VAL_rework_ideas.txt'}
EFFECTS={'STP':'common/scripted_effects/ADISCORD_STP_scripted_effects.txt','VAL':'common/scripted_effects/ADISCORD_VAL_effects.txt'}
TRIGGERS={'STP':'common/scripted_triggers/ADISCORD_STP_scripted_triggers.txt','VAL':'common/scripted_triggers/ADISCORD_VAL_rework_triggers.txt'}
FOCUSES={
 'STP':{
 'administration':['STP_pc_shabrat_cabinet','STP_pw_republic_district_authority','STP_pw_party_executive_secretariat'],
 'industry':['STP_pc_investment_integrated_economy','STP_pw_republic_industrial_settlement','STP_pw_party_industrial_settlement'],
 'army':['STP_pc_army_staff_doctrine','STP_pw_republic_professional_service','STP_pw_party_professional_service'],
 },
 'VAL':{'administration':['VAL_State_Contract'],'industry':['VAL_Industrial_Mobilization_Plan'],'army':['VAL_Contract_General_Staff']}}
loc={'russian':{},'english':{}}
def L(key,ru,en):
    assert key not in loc['russian'],key
    loc['russian'][key]=ru;loc['english'][key]=en

def tag_gate(tag):return 'OR = { tag = STP tag = STS }' if tag=='STP' else 'tag = VAL'
for country in ('STP','VAL'):
    gate=tag_gate(country)
    phase='\n\thas_country_flag = STP_cw_postwar' if country=='STP' else ''
    append(TRIGGERS[country],f'''# Playable staffing: original cabinet and civil-war commanders are unchanged.
{country}_qol_staff_available = {{
\t{gate}
\thas_capitulated = no{phase}
}}
''')
    for kind,focuses in FOCUSES[country].items():
        body='\n'.join('\t\thas_completed_focus = '+f for f in focuses)
        append(TRIGGERS[country],f'''{country}_qol_elite_{kind}_available = {{
\t{country}_qol_staff_available = yes
\tOR = {{
{body}
\t}}
}}''')
    L(country+'_qol_baseline_tt','Открываются базовые специалисты, промышленные компании и конструкторы. Назначения оплачиваются отдельно политической властью; новые штатные командиры прибывают один раз.','Basic specialists, industrial companies and designers become available. Appointments cost political power separately; the new regular commanders arrive only once.')
    for kind,label in [('administration','администрации'),('industry','промышленности'),('army','военного управления')]:
        L(country+'_qol_elite_'+kind+'_tt',f'Открываются ведущие специалисты {label}. Их можно назначить отдельно за §Y125§! политической власти; существующий кабинет не заменяется автоматически.',f'Unlocks elite {kind} specialists. They can be appointed separately for §Y125§! political power; the existing cabinet is not replaced automatically.')
        for f in FOCUSES[country][kind]:focus_reward(country,f,'\t\t\tcustom_effect_tooltip = '+country+'_qol_elite_'+kind+'_tt\n')

slots=('head_of_state','minister_of_defense','minister_of_economy','minister_of_health','minister_of_education','chief_of_intelligence')
people={
'STP': [('Pavel_Ruden','Павел Руден','Pavel Ruden'),('Elena_Savina','Елена Савина','Elena Savina'),('Anton_Belik','Антон Белик','Anton Belik'),('Sofia_Lanskaya','Софья Ланская','Sofia Lanskaya'),('Viktor_Kedrov','Виктор Кедров','Viktor Kedrov'),('Daria_Orlova','Дарья Орлова','Daria Orlova'),('Nikolai_Vedenin','Николай Веденин','Nikolai Vedenin'),('Maria_Serebryak','Мария Серебряк','Maria Serebryak'),('Oleg_Vershin','Олег Вершин','Oleg Vershin')],
'VAL': [('Roman_Terek','Роман Терек','Roman Terek'),('Inga_Voss','Инга Восс','Inga Voss'),('Mark_Sedov','Марк Седов','Mark Sedov'),('Alina_Greif','Алина Грейф','Alina Greif'),('Denis_Krell','Денис Крелль','Denis Krell'),('Lev_Moren','Лев Морен','Lev Moren'),('Leon_Veylan','Леон Вейлан','Leon Veylan'),('Vera_Kelm','Вера Кельм','Vera Kelm'),('Viktor_Bran','Виктор Бран','Viktor Bran')]}
traits=[
('registrar','Администратор реестров','Civil Registrar','political_power_gain = 0.05\n\t\tstability_factor = 0.01'),
('quartermaster','Войсковой снабженец','Army Quartermaster','supply_consumption_factor = -0.03\n\t\tmobilization_speed = 0.05'),
('construction','Организатор восстановления','Reconstruction Organizer','production_speed_industrial_complex_factor = 0.04\n\t\tproduction_speed_infrastructure_factor = 0.04'),
('medical','Госпитальная сеть','Hospital Network','monthly_population = 0.03\n\t\tstability_factor = 0.01'),
('education','Прикладное образование','Applied Education','research_speed_factor = 0.02'),
('security','Аналитическая служба','Intelligence Analysis','decryption = 0.05\n\t\tdrift_defence_factor = 0.10'),
('chancellor','Канцлер нового порядка','Chancellor of the New Administration','political_power_gain = 0.10\n\t\tstability_factor = 0.03'),
('industrial_planner','Промышленный планировщик','Industrial Planner','industrial_capacity_factory = 0.04\n\t\tproduction_speed_industrial_complex_factor = 0.05'),
('general_staff','Профессиональный штаб','Professional General Staff','army_org_factor = 0.04\n\t\tplanning_speed = 0.05')]
for token,ru,en,mods in traits:
    extend('common/country_leader/ADISCORD_minister_traits.txt','leader_traits',f'\tADISCORD_qol_{token} = {{\n\t\trandom = no\n\t\t{mods}\n\t}}')
    L('ADISCORD_qol_'+token,ru,en)
for country in ('STP','VAL'):
    for i,(person,ru,en) in enumerate(people[country]):
        slot=slots[i] if i<6 else slots[{6:0,7:2,8:1}[i]]
        key=f'minister_{country}_{person}'
        elite={6:'administration',7:'industry',8:'army'}.get(i)
        available=f'{country}_qol_elite_{elite}_available' if elite else f'{country}_qol_staff_available'
        cost=125 if elite else 75
        picture=f'generic_political_advisor_europe_{i%6+1}'
        idea_add(IDEAS[country],'political_advisor_'+slot,f'''\t\t{key} = {{
\t\t\tname = {key}
\t\t\tpicture = {picture}
\t\t\tallowed = {{ {tag_gate(country)} }}
\t\t\tvisible = {{ {country}_qol_staff_available = yes }}
\t\t\tavailable = {{ {available} = yes }}
\t\t\tallowed_to_remove = {{ {country}_qol_staff_available = yes }}
\t\t\tcost = {cost}
\t\t\ttraits = {{ ADISCORD_qol_{traits[i][0]} }}
\t\t\tai_will_do = {{ factor = {2 if elite else 1} }}
\t\t}}''')
        L(key,ru,en)
        L(key+'_desc',('Опытный специалист, доступный после подготовки профильного ведомства. ' if elite else 'Специалист базового кадрового резерва. ')+('В Стеландере назначение возможно только после гражданской войны.' if country=='STP' else 'Назначается в соответствующее ведомство Кефрейта.'),('An experienced specialist available after the relevant institutional focus. ' if elite else 'A specialist from the regular personnel pool. ')+('In Stelander, appointment is possible only after the civil war.' if country=='STP' else 'Can be appointed to the corresponding Kefreyt department.'))

generals={'STP':[('Pavel_Gromin','Павел Громин','Pavel Gromin',2,'infantry_leader',7),('Elena_Vetrova','Елена Ветрова','Elena Vetrova',2,'organizer',8),('Oleg_Vershin','Олег Вершин','Oleg Vershin',4,'logistics_wizard',9)],'VAL':[('Anton_Rein','Антон Рейн','Anton Rein',2,'commando',4),('Irina_Karst','Ирина Карст','Irina Karst',2,'organizer',5),('Viktor_Bran','Виктор Бран','Viktor Bran',4,'panzer_leader',6)]}
for country in ('STP','VAL'):
    for person,ru,en,skill,trait,portrait in generals[country]:
        key=f'{country}_{person}'
        gender='\n\t\tgender = female' if person.startswith(('Elena','Irina')) else ''
        extend('common/characters/'+country+'.txt','characters',f'''\t{key} = {{
\t\tname = {key}{gender}
\t\tportraits = {{ army = {{ large = GFX_Portrait_Forul_Generic_{portrait} }} }}
\t\tcorps_commander = {{
\t\t\ttraits = {{ {trait} }}
\t\t\tskill = {skill}
\t\t\tattack_skill = {skill}
\t\t\tdefense_skill = {skill}
\t\t\tplanning_skill = {skill}
\t\t\tlogistics_skill = {skill}
\t\t\tlegacy_id = -1
\t\t}}
\t}}''')
        L(key,ru,en)
    receipt='global' if country=='STP' else 'country'
    recruits='\n'.join(f'\t\tif = {{ limit = {{ NOT = {{ has_character = {country}_{x[0]} }} }} recruit_character = {country}_{x[0]} }}' for x in generals[country][:2])
    append(EFFECTS[country],f'''# Idempotent staff delivery. The receipt survives retirement and annexation.
{country}_qol_initialize_staff = {{
\tif = {{
\t\tlimit = {{ {country}_qol_staff_available = yes NOT = {{ has_{receipt}_flag = {country}_qol_regular_officers_delivered }} }}
\t\tset_{receipt}_flag = {country}_qol_regular_officers_delivered
{recruits}
\t}}
\tif = {{ limit = {{ {country}_qol_elite_army_available = yes }} {country}_qol_grant_elite_officer = yes }}
}}

# Called directly by completion rewards; never tests its own finishing focus.
{country}_qol_grant_elite_officer = {{
\tif = {{
\t\tlimit = {{ {country}_qol_staff_available = yes NOT = {{ has_{receipt}_flag = {country}_qol_elite_officer_delivered }} }}
\t\tset_{receipt}_flag = {country}_qol_elite_officer_delivered
\t\tif = {{ limit = {{ NOT = {{ has_character = {country}_{generals[country][2][0]} }} }} recruit_character = {country}_{generals[country][2][0]} }}
\t}}
}}''')
    for f in FOCUSES[country]['army']:focus_reward(country,f,'\t\t\t'+country+'_qol_grant_elite_officer = yes\n')

replace_once(EFFECTS['STP'],'\tset_country_flag = STP_cw_postwar\n','\tset_country_flag = STP_cw_postwar\n\tSTP_qol_initialize_staff = yes\n')
for country in ('STP','VAL'):
    p='common/on_actions/02_ADISCORD_'+('STP_on_actions.txt' if country=='STP' else 'VAL_rework_on_actions.txt')
    s=read(p);a,o,b=span(s,'on_startup');_,eo,eb=span(s,'effect',o)
    body='\n\t\t\t'+country+' = { '+country+'_qol_initialize_staff = yes '+country+'_qol_initialize_party_leaders = yes }\n'
    if country=='STP':body+='\t\t\tSTS = { STP_qol_initialize_staff = yes }\n'
    write(p,s[:eo+1]+body+s[eo+1:])

company_names={
'STP':[('construction','Стеландская восстановительная компания','Steland Reconstruction Company'),('precision','Бюро «Контур»','Kontur Bureau'),('integrated','Объединённые мастерские Стеланда','United Steland Workshops')],
'VAL':[('construction','Кефрейтский строительный синдикат','Kefreyt Construction Syndicate'),('precision','Лаборатория «Допуск»','Dopusk Laboratory'),('integrated','Центральный арсенальный концерн','Central Arsenal Concern')]}
for country in ('STP','VAL'):
    for i,(kind,ru,en) in enumerate(company_names[country]):
        key=country+'_qol_'+kind+'_company';gate=country+('_qol_elite_industry_available' if i==2 else '_qol_staff_available')
        bonus=('industry = 0.05','electronics = 0.05','industry = 0.10 electronics = 0.05')[i]
        mods=('production_speed_infrastructure_factor = 0.05','research_speed_factor = 0.01','industrial_capacity_factory = 0.04')[i]
        picture=('ADISCORD_law_infrastructure_regional_roadworks','ADISCORD_law_information_state_bulletins','ADISCORD_law_industrial_policy_military_prioritization')[i]
        idea_add(IDEAS[country],'industrial_concern',f'''\t\t{key} = {{
\t\t\tname = {key}
\t\t\tpicture = {picture}
\t\t\tallowed = {{ {tag_gate(country)} }}
\t\t\tvisible = {{ {country}_qol_staff_available = yes }}
\t\t\tavailable = {{ {gate} = yes }}
\t\t\tcost = {125 if i==2 else 75}
\t\t\tresearch_bonus = {{ {bonus} }}
\t\t\tmodifier = {{ {mods} }}
\t\t\tai_will_do = {{ factor = {2 if i==2 else 1} }}
\t\t}}''')
        L(key,ru,en)
        L(key+'_desc','Промышленная компания. Выбирается за политическую власть в слоте промышленного концерна; не занимает слот MIO.','An industrial concern appointed for political power in the industrial-concern slot; it does not occupy an MIO slot.')
    for f in FOCUSES[country]['industry']:focus_reward(country,f,'\t\t\tcustom_effect_tooltip = '+country+'_qol_industry_company_tt\n')
    L(country+'_qol_industry_company_tt','Открывается ведущий промышленный концерн: $'+country+'_qol_integrated_company$. Назначение: §Y125§! политической власти.','Unlocks the advanced industrial concern: $'+country+'_qol_integrated_company$. Appointment costs §Y125§! political power.')

orgs=[]
orgnames={'STP':[('Стеландский пехотный арсенал','Steland Infantry Arsenal'),('Авиационные мастерские Стеланда','Steland Air Workshops'),('Броневое бюро «Гранит»','Granit Armour Bureau')],'VAL':[('Контрактный стрелковый арсенал','Contract Small Arms Arsenal'),('Кефрейтские авиационные мастерские','Kefreyt Air Workshops'),('Тяжёлое бюро Кефрейта','Kefreyt Heavy Design Bureau')]}
for country in ('STP','VAL'):
    for i,kind in enumerate(('arsenal','airworks','armor_bureau')):
        key=country+'_qol_'+kind;gate=country+('_qol_elite_army_available' if i==2 else '_qol_staff_available')
        equipment=('infantry_equipment ADISCORD_squad_weapons_equipment support_equipment','ADISCORD_fighter_archetype ADISCORD_cas_archetype','ADISCORD_combat_platform_archetype')[i]
        research=('infantry_weapons support_tech','air_equipment','armor')[i]
        stat=('soft_attack','air_agility','armor_value')[i]
        icon=('ADISCORD_law_military_cadre_army','ADISCORD_law_information_state_bulletins','ADISCORD_law_industrial_policy_military_prioritization')[i]
        orgs.append(f'''{key} = {{
\tname = {key}
\ticon = GFX_idea_{icon}
\t# allowed is evaluated in COUNTRY scope during registration, not at unlock time.
\tallowed = {{ {tag_gate(country)} }}
\tvisible = {{ FROM = {{ {country}_qol_staff_available = yes has_dlc = "Arms Against Tyranny" }} }}
\tavailable = {{ FROM = {{ {gate} = yes has_dlc = "Arms Against Tyranny" }} }}
\tequipment_type = {{ {equipment} }}
\tresearch_categories = {{ {research} }}
\tresearch_bonus = {0.08 if i==2 else 0.05}
\ttask_capacity = 2
\tinitial_trait = {{
\t\tname = ADISCORD_qol_mio_initial
\t\tequipment_bonus = {{ reliability = 0.03 }}
\t\tproduction_bonus = {{ production_efficiency_gain_factor = 0.03 }}
\t}}
\ttrait = {{
\t\ttoken = {key}_standards
\t\tname = ADISCORD_qol_mio_standards
\t\ticon = GFX_idea_{icon}
\t\tposition = {{ x = 1 y = 0 }}
\t\tequipment_bonus = {{ reliability = 0.03 }}
\t}}
\ttrait = {{
\t\ttoken = {key}_volume
\t\tname = ADISCORD_qol_mio_volume
\t\ticon = GFX_idea_{icon}
\t\tposition = {{ x = 0 y = 1 }}
\t\tany_parent = {{ {key}_standards }}
\t\tmutually_exclusive = {{ {key}_quality }}
\t\tproduction_bonus = {{ production_cost_factor = -0.04 }}
\t}}
\ttrait = {{
\t\ttoken = {key}_quality
\t\tname = ADISCORD_qol_mio_quality
\t\ticon = GFX_idea_{icon}
\t\tposition = {{ x = 2 y = 1 }}
\t\tany_parent = {{ {key}_standards }}
\t\tmutually_exclusive = {{ {key}_volume }}
\t\tequipment_bonus = {{ {stat} = 0.04 }}
\t}}
\ttrait = {{
\t\ttoken = {key}_integration
\t\tname = ADISCORD_qol_mio_integration
\t\ticon = GFX_idea_{icon}
\t\tposition = {{ x = 1 y = 2 }}
\t\tany_parent = {{ {key}_volume {key}_quality }}
\t\tproduction_bonus = {{ production_efficiency_cap_factor = 0.04 }}
\t}}
}}
''')
        L(key,*orgnames[country][i])
        slot=('materiel_manufacturer','aircraft_manufacturer','tank_manufacturer')[i]
        fallback_bonus=('infantry_weapons = 0.05 support_tech = 0.05','air_equipment = 0.05','armor = 0.08')[i]
        bonuses=' '.join(typ+' = { reliability = 0.03 }' for typ in equipment.split())
        idea_add(IDEAS[country],slot,f'''\t\t{key}_designer = {{
\t\t\tname = {key}
\t\t\tpicture = {icon}
\t\t\tallowed = {{ {tag_gate(country)} }}
\t\t\tvisible = {{ {country}_qol_staff_available = yes NOT = {{ has_dlc = "Arms Against Tyranny" }} }}
\t\t\tavailable = {{ {gate} = yes NOT = {{ has_dlc = "Arms Against Tyranny" }} }}
\t\t\tcost = {125 if i==2 else 75}
\t\t\tresearch_bonus = {{ {fallback_bonus} }}
\t\t\tequipment_bonus = {{ {bonuses} }}
\t\t\tai_will_do = {{ factor = 1 }}
\t\t}}''')
        L(key+'_designer','$'+key+'$','$'+key+'$')
        L(key+'_designer_desc','Конструктор для кампании без Arms Against Tyranny. В кампании с дополнением вместо него доступна одноимённая MIO.','Designer for campaigns without Arms Against Tyranny. With that expansion, the corresponding MIO is available instead.')
    for f in FOCUSES[country]['army']:
        focus_reward(country,f,f'\t\t\tcustom_effect_tooltip = {country}_qol_armor_bureau_tt\n\t\t\tif = {{ limit = {{ has_dlc = "Arms Against Tyranny" }} unlock_military_industrial_organization_tooltip = mio:{country}_qol_armor_bureau }}\n')
    L(country+'_qol_armor_bureau_tt','Открывается $'+country+'_qol_armor_bureau$: MIO с Arms Against Tyranny, иначе платный конструктор.','Unlocks $'+country+'_qol_armor_bureau$: an MIO with Arms Against Tyranny, otherwise a paid designer.')
write('common/military_industrial_organization/organizations/ADISCORD_playable_organizations.txt','# Playable-country organizations. The dormant examples in mio.txt remain disabled.\n\n'+'\n'.join(orgs))
for key,ru,en in [('initial','Собранный коллектив','Established Team'),('standards','Единые допуски','Common Tolerances'),('volume','Серийное производство','Series Production'),('quality','Качество сборки','Assembly Quality'),('integration','Согласованная производственная цепь','Integrated Production Chain')]:L('ADISCORD_qol_mio_'+key,ru,en)

append(EFFECTS['STP'],'''# Sotnikov leads the legal humanists before the split; his military-directory
# role remains owned by the existing civil-war/postwar story.
STP_qol_initialize_party_leaders = {
\tif = {
\t\tlimit = {
\t\t\ttag = STP
\t\t\tNOT = { has_global_flag = STP_cw_started }
\t\t\tNOT = { has_country_flag = STP_cw_participant }
\t\t\tNOT = { has_country_flag = STP_cw_postwar }
\t\t\tNOT = { has_country_flag = STP_qol_prewar_leaders_initialized }
\t\t\tNOT = { has_government = humanism }
\t\t}
\t\tset_country_flag = STP_qol_prewar_leaders_initialized
\t\tif = {
\t\t\tlimit = { has_character = STP_grigory_sotnikov }
\t\t\tadd_country_leader_role = { character = STP_grigory_sotnikov promote_leader = yes country_leader = { ideology = humanism_ideology expire = "2200.1.1.1" } }
\t\t\tpromote_character = { character = STP_grigory_sotnikov ideology = humanism_ideology }
\t\t}
\t}
}
''')
replace_once(EFFECTS['STP'],'STP_grigory_sotnikov = { remove_country_leader_role = { ideology = steland_military_directory } }','STP_grigory_sotnikov = {\n\t\t\tremove_country_leader_role = { ideology = humanism_ideology }\n\t\t\tremove_country_leader_role = { ideology = steland_military_directory }\n\t\t}')
append(EFFECTS['VAL'],'''# Existing commanders provide named opposition figures; their command roles stay intact.
VAL_qol_initialize_party_leaders = {
\tif = {
\t\tlimit = { tag = VAL NOT = { has_country_flag = VAL_qol_party_leaders_initialized } NOT = { has_country_flag = VAL_stelander_defeated } }
\t\tset_country_flag = VAL_qol_party_leaders_initialized
\t\tif = {
\t\t\tlimit = { has_character = VAL_Boris_Gromov NOT = { has_government = chauvinism } }
\t\t\tadd_country_leader_role = { character = VAL_Boris_Gromov promote_leader = yes country_leader = { ideology = chauvinism_ideology expire = "2200.1.1.1" } }
\t\t\tpromote_character = { character = VAL_Boris_Gromov ideology = chauvinism_ideology }
\t\t}
\t\tif = {
\t\t\tlimit = { has_character = VAL_Renata_Morn NOT = { has_government = pragmatism } }
\t\t\tadd_country_leader_role = { character = VAL_Renata_Morn promote_leader = yes country_leader = { ideology = pragmatism_ideology expire = "2200.1.1.1" } }
\t\t\tpromote_character = { character = VAL_Renata_Morn ideology = pragmatism_ideology }
\t\t}
\t}
}''')
append('history/countries/STP - StepanLand.txt','STP_qol_initialize_party_leaders = yes')
append('history/countries/VAL - ValeraLand.txt','VAL_qol_initialize_staff = yes\nVAL_qol_initialize_party_leaders = yes')

L('ADISCORD_qol_no_party_leader','','')
party_specs=[
('STP','humanism','GetSTPPrewarHumanistLeader','STP_grigory_sotnikov','Сотников','Sotnikov'),
('STP','chauvinism','GetSTPPrewarNationalLeader','STP_maksim_shabrat','Шабрат','Shabrat'),
('VAL','etatism','GetVALStatePartyLeader','VAL_Valera_Solgalov','Солгалов','Solgalov'),
('VAL','hedonism','GetVALHedonistPartyLeader','VAL_Artem_Rask','Раск','Rask'),
('VAL','chauvinism','GetVALNationalPartyLeader','VAL_Boris_Gromov','Громов','Gromov'),
('VAL','pragmatism','GetVALPragmatistPartyLeader','VAL_Renata_Morn','Морн','Morn')]
for country,ideology,fn,character,ru,en in party_specs:
    guard='tag = '+country+' has_character = '+character
    if country=='STP':guard+=' NOT = { has_global_flag = STP_cw_started } NOT = { has_country_flag = STP_cw_participant } NOT = { has_country_flag = STP_cw_postwar }'
    else:guard+=' has_country_leader = { character = '+character+' ruling_only = no }'
    for long in (False,True):
        name=fn+('Long' if long else '')
        key=character+('_qol_party_label_long' if long else '_qol_party_label')
        append('common/scripted_localisation/ADISCORD_ideologies.txt',f'''defined_text = {{
\tname = {name}
\ttext = {{ trigger = {{ {guard} }} localization_key = {key} }}
\ttext = {{ localization_key = ADISCORD_qol_no_party_leader }}
}}''')
        L(key,'\\nЛидер: $'+character+'$' if long else ' ('+ru+')','\\nLeader: $'+character+'$' if long else ' ('+en+')')
        for language in ('russian','english'):
            path=f'localisation/{language}/parties_l_{language}.yml';s=read(path)
            pattern=r'(?m)^(\s*'+re.escape(country+'_'+ideology+'_party'+('_long' if long else ''))+r':(?:[0-9]+)?\s*"[^"\n]*)(")'
            s,count=re.subn(pattern,lambda m:m[1]+'['+name+']'+m[2],s)
            assert count==1,(path,name,count);write(path,s)
for language,values in loc.items():
    write(f'localisation/{language}/ADISCORD_playable_staff_l_{language}.yml','l_'+language+':\n'+''.join(' '+k+': "'+v+'"\n' for k,v in values.items()))

rows=['# Playable staff and industrial organizations','',
'Scope: the featured STP/STS and VAL campaigns. Existing cabinets and story officers are unchanged.',
'Each campaign gains six basic minister alternatives (75 PP), three elite alternatives (125 PP), two basic skill-2 commanders and one skill-4 focus commander. New STP/STS staff, concerns and designers/MIOs require STP_cw_postwar; Party victory does not additionally require independence.',
'Each campaign has three industrial concerns: two basic (75 PP), one advanced (125 PP). Three military designers are represented by MIOs with Arms Against Tyranny, and paid legacy designers without it. The two representations never become available together. MIOs support actual A-Discord equipment archetypes; their four-node trees offer a mutually exclusive quantity/quality choice.', '', '## Elite unlocks','']
for country in ('STP','VAL'):
    for kind,fs in FOCUSES[country].items():rows.append(f'- {country}, {kind}: '+', '.join('`'+f+'`' for f in fs)+'.')
rows+=['','Army unlocks also grant the new elite commander once and open the heavy MIO/designer. Industry unlocks also open the advanced concern. Ministers and companies remain paid appointments; focus rewards do not replace the cabinet.', '', '## Lifecycle', '', 'Officer grant receipts survive retirement and repeat initialization. The new Stelander roster is globally unique across the two claimant tags. The postwar settlement delivers the regular roster; startup recovers only previously undelivered staff and already-earned elite unlocks.', 'Sotnikov receives a temporary native humanist leadership role before the split. His existing postwar military-directory path is unchanged. The temporary role is removed before the civil-war nationality transfer. Shabrat already has a native chauvinist role. Both prewar labels disappear at the split, after removal from the country or retirement. Existing Kefreyt actors Solgalov/Rask and commanders Gromov/Morn name the corresponding political parties; no government is changed.', '', '## Verification boundary', '', 'Test fresh STP, Party victory, STS victory, VAL, repeated load and retired officers. Check MIO registration and progression in a NEW campaign with Arms Against Tyranny, and designer fallback without it. Local and CI checks execute source contracts, not the HOI4 engine; visual placement, saved MIO registration and campaign balance remain native playtest tasks.']
write('docs/development/playable-staff.md','\n'.join(rows)+'\n')
print('IMPLEMENTED',len(loc['russian']),'bilingual keys')

replace_once(EFFECTS['STP'], '\t\t\tNOT = { has_country_flag = STP_qol_prewar_leaders_initialized }\n\t\t\tNOT = { has_government = humanism }', '\t\t\tNOT = { has_country_flag = STP_qol_prewar_leaders_initialized }\n\t\t\tNOT = { has_government = humanism }\n\t\t\tNOT = { has_government = etatism }')
replace_once(EFFECTS['STP'], '\t\t\tlimit = { has_character = STP_grigory_sotnikov }\n\t\t\tadd_country_leader_role', '\t\t\tlimit = { has_character = STP_grigory_sotnikov }\n\t\t\tSTP_grigory_sotnikov = { remove_country_leader_role = { ideology = steland_military_directory } }\n\t\t\tadd_country_leader_role')
p='common/scripted_localisation/ADISCORD_ideologies.txt';s=read(p)
a=s.index('\ndefined_text = {\n\tname = GetSTPPrewarHumanistLeader')
base,addition=s[:a],s[a:]
for person in ('STP_grigory_sotnikov','STP_maksim_shabrat'):
    addition=addition.replace('has_character = '+person+' NOT', 'has_character = '+person+' has_country_leader = { character = '+person+' ruling_only = no } NOT')
split=addition.index('defined_text = {\n\tname = GetVALStatePartyLeader')
append('common/scripted_localisation/ADISCORD_STP_scripted_loc.txt',addition[:split].strip())
append('common/scripted_localisation/ADISCORD_VAL_contract_scripted_loc.txt',addition[split:].strip())
write(p,base)
replace_once('tools/validators/validate_adiscord_val_rework.py','    candidates = {key for key, body in ideas.items() if "name" in script_fields(body)}','''    # Selectable ministers and designers may use a display name without being
    # country-spirit previews. Only native spirit categories participate in swaps.
    spirit_ids = {entry.key for group in ideas_root
                  if group.key in {"country", "hidden_ideas"} and isinstance(group.value, list)
                  for entry in group.value if isinstance(entry.value, list)}
    candidates = {key for key in spirit_ids if "name" in script_fields(ideas[key])}''')
replace_once('tools/tests/test_validate_adiscord_val_rework.py','    def test_production_preview_contracts_are_valid(self):','''    def test_named_selectable_staff_and_designers_are_not_country_spirit_previews(self):
        original = IDEAS_PATH.read_text(encoding="utf-8-sig")
        additions = """
        political_advisor_head_of_state = {
            VAL_named_advisor = { name = VAL_named_advisor allowed = { tag = VAL } cost = 75 }
        }
        industrial_concern = {
            VAL_named_concern = { name = VAL_concern_name allowed = { tag = VAL } cost = 75 }
        }
        materiel_manufacturer = {
            VAL_named_designer = { name = VAL_designer_name allowed = { tag = VAL } cost = 75 }
        }
        """
        augmented = original[:original.rfind("}")] + additions + original[original.rfind("}"):]
        accepted, issues = self.preview_issues(ideas=augmented)
        self.assertEqual(issues, [])
        self.assertTrue({"VAL_named_advisor", "VAL_named_concern", "VAL_named_designer"}.isdisjoint(accepted))
        self.assertIn("VAL_contract_delta_dummy", accepted)

    def test_production_preview_contracts_are_valid(self):''')
