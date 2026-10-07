exec(open('_tmp_rus_regional.py', encoding='utf-8-sig').read().split("p = 'common/scripted_triggers/ADISCORD_vorkerland_triggers.txt'")[0])

for p in list(Path('common/scripted_effects').glob('*.txt')) + list(Path('common/on_actions').glob('*.txt')):
    s = read(p)
    old = s
    s = re.sub(r'RUS_crisis_release_other_major = yes(?P<space>\s+)clr_country_flag = (?P<flag>\w+)', r'clr_country_flag = \g<flag>\g<space>RUS_crisis_release_other_major = yes', s)
    s = s.replace('OR = { is_major = no has_country_flag = RUS_crisis_added_major }', 'OR = { is_major = no has_country_flag = RUS_crisis_added_major RUS_crisis_other_major_required = yes }')
    if s != old:
        write(p, s)

p = 'common/scripted_effects/ADISCORD_vorkerland_effects.txt'
s = read(p)
s = s.replace('# COUNTRY. Called by another campaign before clearing its own major receipt.', '# COUNTRY. Called after the ending campaign clears its own major receipt.')
s = s.replace('\telse = { set_major = no }\n}\n\nRUS_crisis_close', '\telse_if = {\n\t\tlimit = { RUS_crisis_other_major_required = no }\n\t\tset_major = no\n\t}\n}\n\nRUS_crisis_close')
s = s.replace('\t\t\tset_variable = { var = RUS_crisis_phase value = 2 }\n\t\t\tevery_country', '\t\t\tset_variable = { var = RUS_crisis_phase value = 2 }\n\t\t\tclear_global_event_target = RUS_crisis_war_anchor\n\t\t\tevery_country', 1)
s = s.replace('# COUNTRY sovereign intervener. Each existing bloc enters its own war side.\n# Register before native war callbacks, but never alter a country\'s faction.', '# COUNTRY sovereign intervener. Keep one native war without merging factions.\n# Register before callbacks; enemies of the existing war side cannot join it.')
s = replace(s, 'RUS_crisis_start_intervention', '''RUS_crisis_start_intervention = {
	if = {
		limit = { NOT = { has_global_event_target = RUS_crisis_war_anchor } }
		save_global_event_target_as = RUS_crisis_war_anchor
		RUS_crisis_register_defender = yes
		if = {
			limit = { NOT = { has_war_with = RUS } }
			declare_war_on = { target = RUS type = annex_everything }
		}
	}
	else_if = {
		limit = {
			NOT = {
				any_country = {
					has_country_flag = RUS_crisis_defender
					has_war_with = PREV
				}
			}
		}
		RUS_crisis_register_defender = yes
		if = {
			limit = { NOT = { has_war_with = RUS } }
			add_to_war = {
				targeted_alliance = event_target:RUS_crisis_war_anchor
				enemy = RUS
				hostility_reason = asked_to_join
				single_target_only = yes
			}
		}
	}
	if = {
		limit = { has_war_with = RUS }
		every_allied_country = {
			limit = { NOT = { tag = PREV } }
			RUS_crisis_join_intervention = yes
		}
		RUS_crisis_join_subjects = yes
	}
}''')
s = s.replace('\t\t\tNOT = { has_war_with = PREV }\n', '\t\t\tNOT = { has_war_with = PREV }\n\t\t\tNOT = {\n\t\t\t\tany_country = {\n\t\t\t\t\thas_country_flag = RUS_crisis_defender\n\t\t\t\t\thas_war_with = PREV\n\t\t\t\t}\n\t\t\t}\n', 1)
s = s.replace('\tclear_array = global.RUS_crisis_defenders\n', '\tclear_array = global.RUS_crisis_defenders\n\tclear_global_event_target = RUS_crisis_war_anchor\n', 1)
write(p, s)

p = 'docs/development/focus-effects.md'
s = read(p).replace('Каждый подходящий участник объявляет войну RUS, затем его\nсоюзники и зависимые страны вступают на ту же сторону через `add_to_war`.\nВраждующий с этим участником союзник и союзники RUS исключаются. Общего\nнового альянса нет; разные блоки сохраняют самостоятельные военные стороны.\nХан не объявляет эту войну сам. Уже вступивший союзник не объявляет её повторно.', 'Первый подходящий участник объявляет войну RUS; остальные участники,\nих союзники и зависимые страны вступают на ту же сторону через `add_to_war`.\nВсе сохраняют свои фракции. Страна, воюющая с уже вступившим участником,\nне может присоединиться к его стороне: принудительного перемирия нет.\nСоюзники RUS исключаются. Единый нативный объект войны позволяет major-роли\nудерживать её до поражения всего реестра. Хан не объявляет эту войну сам.')
write(p, s)

p = 'localisation/russian/ADISCORD_vorkerland_l_russian.yml'
s = read(p).replace('Участники приводят своих союзников и зависимые страны в собственную войну с Ханом.', 'Участники приводят своих союзников и зависимые страны на общую сторону войны с Ханом, сохраняя свои альянсы. Страна, воюющая с уже вступившим участником, не сможет присоединиться к его стороне.')
s = s.replace('Их союзники и зависимые страны вступают на сторону собственных штабов.', 'Их союзники и зависимые страны вступают на общую сторону войны с Ханом, сохраняя свои штабы и альянсы.')
write(p, s)
