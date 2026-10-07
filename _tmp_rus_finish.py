exec(open('_tmp_rus_regional.py', encoding='utf-8-sig').read().split("p = 'common/scripted_triggers/ADISCORD_vorkerland_triggers.txt'")[0])

flags = ['ADISCORD_nam_resource_war_added_major', 'SHL_mzr_added_major',
         'ADISCORD_south_added_major', 'ADISCORD_west_added_major',
         'STP_cw_northern_added_major', 'VAL_frontier_added_major',
         'VAL_northern_coalition_added_major', 'VAL_final_war_added_major',
         'ADISCORD_vorkerland_pw_added_major', 'ADISCORD_vorkerland_coalition_mandatory_major']
p = 'common/scripted_triggers/ADISCORD_vorkerland_triggers.txt'
s = read(p)
s = s.replace('\t\t\thas_global_flag = ADISCORD_south_final_resolved\n', '\t\t\thas_war = no\n\t\t\thas_global_flag = ADISCORD_south_final_resolved\n')
s = remove(s, 'RUS_crisis_preparation_open')
s += '\n# COUNTRY. Temporary major ownership may overlap independent campaigns.\nRUS_crisis_other_major_required = {\n\tOR = {\n' + ''.join('\t\thas_country_flag = ' + f + '\n' for f in flags) + '\t}\n}\n'
write(p, s)

# Keep the release in its owning campaign; preserve the concurrent Khan role.
for p in list(Path('common/scripted_effects').glob('*.txt')) + list(Path('common/on_actions').glob('*.txt')):
    s = read(p)
    old = s
    for flag in flags:
        pattern = r'set_major = no(?P<space>\s+)clr_country_flag = ' + flag + r'\b'
        s = re.sub(pattern, r'RUS_crisis_release_other_major = yes\g<space>clr_country_flag = ' + flag, s)
        pattern = r'limit = \{ is_major = no \}(\s+set_country_flag = ' + flag + r'\b)'
        s = re.sub(pattern, r'limit = { OR = { is_major = no has_country_flag = RUS_crisis_added_major } }\1', s)
    if old != s:
        write(p, s)

p = 'common/scripted_effects/ADISCORD_vorkerland_effects.txt'
s = read(p)
s = s.replace('# war callbacks may immediately call allies. Naturally major countries keep it.', '# war callbacks may immediately call allies. Preserve other campaigns\' ownership.')
a = s.index('RUS_crisis_register_defender = {')
b = s.index('RUS_crisis_launch = {', a)
part = s[a:b].replace('\t\tset_country_flag = RUS_crisis_defender', '\t\tADISCORD_release_non_participating_minor_optimization = yes\n\t\tset_country_flag = RUS_crisis_defender')
part = part.replace('limit = { is_major = no }', 'limit = {\n\t\t\t\tOR = {\n\t\t\t\t\tis_major = no\n\t\t\t\t\tRUS_crisis_other_major_required = yes\n\t\t\t\t}\n\t\t\t}')
s = s[:a] + part + s[b:]
s = s.replace('\t\t\tcountry_event = { id = ADISCORD_rus_crisis.3 }', '\t\t\tfor_each_scope_loop = {\n\t\t\t\tarray = global.RUS_crisis_defenders\n\t\t\t\tcountry_event = { id = ADISCORD_rus_crisis.3 }\n\t\t\t}\n\t\t\tcountry_event = { id = ADISCORD_rus_crisis.3 }', 1)
s = replace(s, 'RUS_crisis_clear_preparation', '''RUS_crisis_clear_preparation = {
	if = {
		limit = { RUS_crisis_project_active = no }
		remove_ideas = RUS_crisis_reactor_guard
	}
}''')
s = replace(s, 'RUS_crisis_clear_defender', '''RUS_crisis_clear_defender = {
	clr_country_flag = RUS_crisis_defender
	if = {
		limit = { has_country_flag = RUS_crisis_added_major }
		if = {
			limit = { RUS_crisis_other_major_required = no }
			set_major = no
		}
		clr_country_flag = RUS_crisis_added_major
	}
}

# COUNTRY. Called by another campaign before clearing its own major receipt.
RUS_crisis_release_other_major = {
	if = {
		limit = { has_country_flag = RUS_crisis_defender }
		set_country_flag = RUS_crisis_added_major
	}
	else = { set_major = no }
}''')
a = s.index('RUS_crisis_close = {')
b = s.index('RUS_crisis_check_external_end = {', a)
part = s[a:b]
x = part.index('\t\tRUS_crisis_clear_roster = yes')
y = part.index('\n\t}\n}', x)
part = part[:x] + '''		every_country = {
			limit = {
				OR = {
					has_country_flag = RUS_crisis_warned
					has_country_flag = RUS_crisis_defender
				}
			}
			country_event = { id = ADISCORD_rus_crisis.6 }
		}
		RUS_crisis_clear_roster = yes''' + part[y:]
part = part.replace('# Peace callbacks run after native diplomacy has settled. A surviving defeated\n# coalition leader does not cancel the project while other members still fight.\n', '')
s = s[:a] + part + s[b:]
s = s.replace('# Preserve states and countries before white peace removes faction relations.', '# Preserve the full roster and territory before native peace merges war outcomes.')
write(p, s)

p = 'common/ideas/ADISCORD_vorkerland_ideas.txt'
write(p, read(p).replace('picture = generic_defence\n', 'picture = ADISCORD_law_military_cadre_army\n'))

p = 'common/ai_strategy/ADISCORD_vorkerland_ai.txt'
s = read(p)
for tag in ('WRK', 'IVN'):
    for name in (f'RUS_crisis_prepare_{tag}', f'{tag}_crisis_prepare_RUS', f'RUS_crisis_conquer_{tag}'):
        s = remove(s, name)
for name in re.findall(r'(?m)^((?:RUS_crisis_prepare_\w+|\w+_crisis_prepare_RUS)) = \{', s):
    a = s.index(name + ' = {')
    b = block_end(s, s.index('{', a))
    part = s[a:b].replace('has_country_flag = RUS_crisis_defender', 'RUS_crisis_coalition_candidate = yes')
    s = s[:a] + part + s[b:]
for tag in ('MON', 'VLD', 'TMR'):
    for name in ('RUS_crisis_prepare_VAL', 'VAL_crisis_prepare_RUS', 'RUS_crisis_conquer_VAL'):
        a = s.index(name + ' = {')
        b = block_end(s, s.index('{', a))
        s += '\n\n' + s[a:b].replace('VAL', tag)
write(p, s.rstrip() + '\n')

p = 'common/ai_strategy_plans/ADISCORD_vorkerland_plans.txt'
s = read(p)
focus_ids = ['RUS_imperial_general_staff', 'RUS_western_supply_lines', 'RUS_imperial_arsenals', 'RUS_aimaq_reserve', 'RUS_break_the_hegemon', 'RUS_register_conquered_lands', 'RUS_empire_without_rivals', 'RUS_postwar_roads', 'RUS_imperial_academy', 'RUS_tomorrow_above_ground']
s += '''
ADISCORD_rus_last_sky_plan = {
	name = "ADISCORD_rus_last_sky_plan"
	desc = "ADISCORD_rus_last_sky_plan"
	allowed = { original_tag = RUS }
	enable = {
		is_ai = yes
		RUS_crisis_programme_focus_available = yes
	}
	abort = { RUS_crisis_programme_focus_available = no }
	ai_national_focuses = {
''' + ''.join('\t\t' + name + '\n' for name in focus_ids) + '''	}
	weight = { factor = 1000 }
}
'''
write(p, s)
