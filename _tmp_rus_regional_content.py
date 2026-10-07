exec(open('_tmp_rus_regional.py', encoding='utf-8-sig').read().split("p = 'common/scripted_triggers/ADISCORD_vorkerland_triggers.txt'")[0])

p = 'common/scripted_effects/ADISCORD_STP_scripted_effects.txt'
s = remove(read(p), 'STP_khan_coalition_armistice')
s = s.replace('\t\t\tNOT = { has_country_flag = RUS_crisis_defender }\n', '')
s = s.replace('exists = yes NOT = { has_global_flag = RUS_crisis_truce_in_progress }', 'exists = yes')
write(p, s)
for region in ('west', 'south'):
    p = f'common/scripted_triggers/ADISCORD_{region}_final_war_triggers.txt'
    s = read(p)
    a = s.index('ADISCORD_' + region + '_crisis_open = {')
    b = block_end(s, s.index('{', a))
    segment = s[a:b]
    start = segment.index('\tRUS = {')
    end = block_end(segment, segment.index('{', start))
    segment = segment[:start] + segment[end:]
    write(p, s[:a] + segment + s[b:])
p = 'common/on_actions/09_ADISCORD_scripted_peace_on_actions.txt'
s = read(p)
pattern = r'\n\t{5}NOT = \{\n\t{6}AND = \{\n\t{7}ROOT = \{ has_country_flag = RUS_crisis_defender \}\n\t{7}FROM = \{ has_country_flag = RUS_crisis_defender \}\n\t{6}\}\n\t{5}\}'
s, count = re.subn(pattern, '', s)
assert count == 2, count
write(p, s)

p = 'focus_trees/RUS/main/focuses.txt'
s = read(p)
# Each focus remains in its existing owner; only the four obsolete routes disappear.
for tag in ('nod', 'stp', 'sts', 'val'):
    for tier in range(1, 5):
        match = re.search(r'\n\tfocus = \{\n\t\tid = RUS_crisis_' + tag + '_' + str(tier) + r'\n', s)
        assert match
        end = block_end(s, s.index('{', match.start()))
        s = s[:match.start()] + s[end:]
s = s.replace('\t# Each participating army has a 77-day preparation route during coalition mobilization.\n', '')

def focus_replace(source, name, content):
    match = re.search(r'\n\tfocus = \{\n\t\tid = ' + name + r'\n', source)
    assert match, name
    end = block_end(source, source.index('{', match.start()))
    return source[:match.start()] + '\n' + content.rstrip() + source[end:]

# Keep the three mobilisation branches and their real units/supplies.
a = s.index('\t\tid = RUS_break_the_hegemon')
b = block_end(s, s.rfind('{', 0, a))
segment = s[a:b].replace('cost = 3', 'cost = 1', 1)
segment = segment.replace('\t\tbypass = { check_variable = { var = RUS_crisis_phase value = 3 compare = equals } }\n', '')
segment = segment.replace('check_variable = { var = RUS_crisis_phase value = 2 compare = equals }', 'check_variable = { var = RUS_crisis_phase value = 2 compare = equals }\n\t\t\t\t\tcheck_variable = { var = RUS_crisis_phase value = 3 compare = equals }', 1)
s = s[:a] + segment + s[b:]
focus_data = (
    ('RUS_register_conquered_lands', 'GFX_focus_VAL_Army_Of_The_Ledger', 18, 18, 3, ('RUS_break_the_hegemon',), '''add_equipment_to_stockpile = { type = support_equipment amount = 300 producer = RUS }
add_equipment_to_stockpile = { type = train_equipment_1 amount = 40 producer = RUS }'''),
    ('RUS_empire_without_rivals', 'GFX_focus_STP_pw_party_civilian_retraining', 22, 18, 4, ('RUS_break_the_hegemon',), '''add_research_slot = 1
hidden_effect = { ADISCORD_economy_mark_dirty = yes }'''),
    ('RUS_postwar_roads', 'GFX_focus_VAL_Reclamation_Road_Crews', 18, 19, 3, ('RUS_register_conquered_lands',), '''176 = { RUS_crisis_fortify_reactor_state = yes }
177 = { RUS_crisis_fortify_reactor_state = yes }
188 = { RUS_crisis_fortify_reactor_state = yes }
192 = { RUS_crisis_fortify_reactor_state = yes }
add_equipment_to_stockpile = { type = ADISCORD_anti_air_equipment_2163 amount = 240 producer = RUS }'''),
    ('RUS_imperial_academy', 'GFX_focus_STP_pw_party_civilian_retraining', 22, 19, 3, ('RUS_empire_without_rivals',), '''add_tech_bonus = { name = RUS_imperial_academy bonus = 0.75 uses = 2 category = industry }
army_experience = 30'''),
    ('RUS_tomorrow_above_ground', 'GFX_focus_STP_ps_permanent_security', 20, 20, 1, ('RUS_postwar_roads', 'RUS_imperial_academy'), '''add_ideas = RUS_crisis_reactor_guard
hidden_effect = { country_event = { id = ADISCORD_rus_campaign.11 } }'''),
)
for name, icon, x, y, cost, parents, rewards in focus_data:
    rows = ['\tfocus = {', f'\t\tid = {name}', f'\t\ticon = {icon}', f'\t\tx = {x}', f'\t\ty = {y}', f'\t\tcost = {cost}', '\t\tcancel_if_invalid = yes']
    rows += [f'\t\tprerequisite = {{ focus = {parent} }}' for parent in parents]
    rows += ['\t\tavailable = { RUS_crisis_programme_focus_available = yes }', '\t\tcompletion_reward = {']
    rows += ['\t\t\t' + row for row in rewards.splitlines()]
    rows += ['\t\t}', '\t\tai_will_do = { base = 120 }', '\t}']
    s = focus_replace(s, name, '\n'.join(rows))
s = re.sub(r'\n(?:[ \t]*\n){2,}', '\n\n', s)
write(p, s)

p = 'common/ideas/ADISCORD_vorkerland_ideas.txt'
s = read(p)
for tag in ('nod', 'stp', 'sts', 'val'):
    for tier in (1, 2):
        name = f'RUS_crisis_{tag}_preparation_{tier}'
        match = re.search(r'(?m)^\t\t' + name + r' = \{', s)
        assert match, name
        end = block_end(s, s.index('{', match.start()))
        s = s[:match.start()] + s[end:]
s = s.replace('\tcountry = {', '''	country = {
		RUS_crisis_reactor_guard = {
			picture = generic_defence
			allowed = { original_tag = RUS }
			removal_cost = -1
			cancel = { RUS_crisis_project_active = no }
			modifier = {
				army_defence_factor = 0.12
				max_dig_in = 5
				supply_consumption_factor = -0.10
			}
		}''', 1)
s = re.sub(r'\n(?:[ \t]*\n){2,}', '\n\n', s)
write(p, s)

p = 'common/decisions/ADISCORD_vorkerland_decisions.txt'
s = read(p)
for tag in ('nod', 'stp', 'sts', 'val'):
    name = 'RUS_crisis_resupply_' + tag
    match = re.search(r'(?m)^\t' + name + r' = \{', s)
    assert match
    end = block_end(s, s.index('{', match.start()))
    s = s[:match.start()] + s[end:]
s = s.replace('visible = { has_country_flag = RUS_crisis_defender }', 'visible = { has_country_flag = RUS_crisis_warned }')
s = re.sub(r'\n(?:[ \t]*\n){2,}', '\n\n', s)
write(p, s)
p = 'common/decisions/categories/ADISCORD_vorkerland_categories.txt'
s = read(p).replace('OR = { tag = RUS has_country_flag = RUS_crisis_defender }', 'OR = { tag = RUS has_country_flag = RUS_crisis_warned has_country_flag = RUS_crisis_defender }')
write(p, s)
p = 'common/ai_strategy_plans/ADISCORD_vorkerland_plans.txt'
s = read(p)
for tag in ('nod', 'stp', 'sts', 'val'):
    s = remove(s, f'ADISCORD_rus_crisis_{tag}_plan')
write(p, s)

p = 'common/units/equipment/ADISCORD_air_equipment.txt'
s = read(p)
a = s.index('\tADISCORD_zeppelin_equipment = {')
b = block_end(s, s.index('{', a))
segment = s[a:b]
for key, value in dict(reliability='0.99', maximum_speed='12', armor_value='90', defense='300', breakthrough='350', soft_attack='550', hard_attack='180', ap_attack='120', air_attack='48', fuel_consumption='8').items():
    segment, count = re.subn(r'(?m)(\t\t' + key + r' = )[^\n]+', lambda m: m[1] + value, segment)
    assert count == 1, key
write(p, s[:a] + segment + s[b:])
p = 'common/units/ADISCORD_land_units.txt'
s = read(p)
a = s.index('\tADISCORD_zeppelin = {')
b = block_end(s, s.index('{', a))
segment = s[a:b]
for key, value in dict(max_strength='200', max_organisation='80', default_morale='0.6', supply_consumption='1.2').items():
    segment, count = re.subn(r'(?m)(\t\t' + key + r' = )[^\n]+', lambda m: m[1] + value, segment)
    assert count == 1, key
write(p, s[:a] + segment + s[b:])
