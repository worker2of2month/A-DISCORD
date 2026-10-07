from pathlib import Path
import re
import subprocess
from tools.builders.build_adiscord_focus_trees import block_end


def read(path):
    return Path(path).read_text(encoding='utf-8-sig')


def write(path, text):
    p = Path(path)
    encoding = 'utf-8-sig' if p.read_bytes().startswith(b'\xef\xbb\xbf') else 'utf-8'
    p.write_text(text, encoding=encoding, newline='\n')


def replace(text, name, body):
    match = re.search(r'(?m)^' + re.escape(name) + r' = \{', text)
    assert match, name
    end = block_end(text, text.index('{', match.start()))
    return text[:match.start()] + body.strip() + text[end:]


def remove(text, name):
    return replace(text, name, '').replace('\n\n\n', '\n\n')


p = 'common/scripted_triggers/ADISCORD_vorkerland_triggers.txt'
s = read(p)
a = s.index('\tNOT = {\n\t\tany_country = {', s.index('RUS_crisis_can_begin = {'))
b = block_end(s, s.index('{', a))
s = s[:a] + s[b:]
old = subprocess.check_output(['git', 'show', 'af2c5b18:common/scripted_triggers/ADISCORD_vorkerland_triggers.txt']).decode('utf-8')
a = old.index('RUS_crisis_final_victory = {')
b = old.index('# COUNTRY. Victory and current sovereignty', a)
old_gate = old[a:b].replace('RUS_crisis_final_victory', 'RUS_crisis_eastern_hegemony')
s = s.replace('RUS_crisis_coalition_candidate = {', old_gate + 'RUS_crisis_coalition_candidate = {', 1)
s = replace(s, 'RUS_crisis_coalition_candidate', '''RUS_crisis_coalition_candidate = {
	exists = yes
	is_subject = no
	has_capitulated = no
	NOT = { is_in_faction_with = RUS }
	OR = {
		tag = MON
		tag = VLD
		tag = TMR
		AND = {
			has_global_flag = ADISCORD_south_final_resolved
			OR = {
				AND = { tag = SHL has_global_flag = ADISCORD_south_hegemon_SHL }
				AND = { tag = NAM has_global_flag = ADISCORD_south_hegemon_NAM }
			}
		}
		AND = {
			has_war = no
			RUS_crisis_eastern_hegemony = yes
		}
	}
}''')
s = s.replace('# Existing countries, including subjects and civil-war participants. The sealed\n# territory is a technical map owner, not a coalition government.\n', '# COUNTRY. Regional winners retain their own alliances and settlements.\n')
s = replace(s, 'RUS_crisis_defending_bloc', '''RUS_crisis_defending_bloc = {
	exists = yes
	NOT = { tag = RUS }
	NOT = { is_subject_of = RUS }
	has_war_with = RUS
}''')
s = replace(s, 'RUS_crisis_regional_wars_available', '''RUS_crisis_regional_wars_available = {
	NOT = { has_global_flag = RUS_crisis_world_ended }
}''')
s = s.replace('# COUNTRY. Story diplomacy must keep the common coalition intact.', '# COUNTRY. The epilogue is terminal; earlier regional wars remain independent.')
for tag in ('nod', 'stp', 'sts', 'val'):
    s = remove(s, f'RUS_crisis_prepare_{tag}')
s = replace(s, 'RUS_crisis_all_defenders_defeated', '''RUS_crisis_all_defenders_defeated = {
	check_variable = { var = RUS_crisis_phase value = 2 compare = equals }
	any_of_scopes = { array = global.RUS_crisis_defenders always = yes }
	NOT = {
		any_of_scopes = {
			array = global.RUS_crisis_defenders
			exists = yes
			NOT = { is_subject_of = RUS }
			NOT = { has_country_flag = RUS_crisis_capitulation_current }
			OR = {
				has_capitulated = no
				capital_scope = {
					NOT = { OR = { is_controlled_by = RUS controller = { is_subject_of = RUS } } }
				}
			}
		}
	}
}''')
s = s.replace('RUS_crisis_preparation_open = {', '''RUS_crisis_programme_focus_available = {
	custom_trigger_tooltip = {
		tooltip = RUS_crisis_programme_focus_available_tt
		RUS_crisis_project_active = yes
		RUS_lab_reactor_access = yes
		NOT = { has_global_flag = RUS_crisis_world_ended }
	}
}

RUS_crisis_preparation_open = {''', 1)
write(p, s)

p = 'common/scripted_effects/ADISCORD_vorkerland_effects.txt'
s = read(p)
s = remove(s, 'RUS_crisis_select_coalition_leader')
s = replace(s, 'RUS_crisis_begin', '''RUS_crisis_begin = {
	if = {
		limit = { RUS_crisis_can_begin = yes }
		set_variable = { var = RUS_crisis_phase value = 1 }
		activate_mission = RUS_crisis_invasion_countdown
		activate_mission = RUS_crisis_laser_countdown
		country_event = { id = ADISCORD_rus_crisis.2 }
		every_country = {
			limit = { RUS_crisis_coalition_candidate = yes }
			ADISCORD_release_non_participating_minor_optimization = yes
			set_country_flag = RUS_crisis_warned
			activate_mission = RUS_crisis_defence_countdown
			country_event = { id = ADISCORD_rus_crisis.1 }
		}
	}
}''')
s = replace(s, 'RUS_crisis_enforce_truce', '''RUS_crisis_enforce_truce = {
	if = {
		limit = {
			has_global_flag = RUS_crisis_world_ended
			NOT = { has_global_flag = RUS_crisis_truce_in_progress }
		}
		set_global_flag = RUS_crisis_truce_in_progress
		ROOT = { white_peace = FROM }
		clr_global_flag = RUS_crisis_truce_in_progress
	}
}''')
s = s.replace('# A bounded settlement at project exposure. The native peace callbacks must not\n# award territorial victories for this compulsory truce.', '# The terminal epilogue cannot open a new war after its global settlement.')
s = remove(s, 'RUS_crisis_form_coalition')
s = replace(s, 'RUS_crisis_launch', '''RUS_crisis_launch = {
	if = {
		limit = { check_variable = { var = RUS_crisis_phase value = 1 compare = equals } }
		if = {
			limit = { RUS_crisis_project_active = yes RUS_lab_reactor_access = yes }
			set_variable = { var = RUS_crisis_phase value = 2 }
			every_country = {
				limit = { RUS_crisis_coalition_candidate = yes }
				RUS_crisis_start_intervention = yes
			}
			country_event = { id = ADISCORD_rus_crisis.3 }
			country_event = { id = ADISCORD_rus_crisis.7 days = 1 }
		}
		else = { RUS_crisis_close = yes }
	}
}

# COUNTRY sovereign intervener. Each existing bloc enters its own war side.
# Register before native war callbacks, but never alter a country's faction.
RUS_crisis_start_intervention = {
	RUS_crisis_register_defender = yes
	if = {
		limit = { NOT = { has_war_with = RUS } }
		declare_war_on = { target = RUS type = annex_everything }
	}
	every_allied_country = {
		limit = { NOT = { tag = PREV } }
		RUS_crisis_join_intervention = yes
	}
	RUS_crisis_join_subjects = yes
}

# COUNTRY ally, PREV is already on the intended side of the war against RUS.
RUS_crisis_join_intervention = {
	if = {
		limit = {
			exists = yes
			has_capitulated = no
			NOT = { tag = RUS }
			NOT = { is_subject_of = RUS }
			NOT = { is_in_faction_with = RUS }
			NOT = { has_war_with = PREV }
		}
		RUS_crisis_register_defender = yes
		if = {
			limit = { NOT = { has_war_with = RUS } }
			add_to_war = {
				targeted_alliance = PREV
				enemy = RUS
				hostility_reason = asked_to_join
				single_target_only = yes
			}
		}
		RUS_crisis_join_subjects = yes
	}
}

# Dependencies are acyclic. Each subject follows its own overlord's war side.
RUS_crisis_join_subjects = {
	every_subject_country = { RUS_crisis_join_intervention = yes }
}''')
s = replace(s, 'RUS_crisis_clear_preparation', '''RUS_crisis_clear_preparation = {
	remove_ideas = RUS_crisis_reactor_guard
}''')
s = replace(s, 'RUS_crisis_clear_roster', '''RUS_crisis_clear_roster = {
	RUS_crisis_clear_preparation = yes
	for_each_scope_loop = {
		array = global.RUS_crisis_defenders
		RUS_crisis_clear_defender = yes
	}
	clear_array = global.RUS_crisis_defenders
	every_country = {
		limit = { has_country_flag = RUS_crisis_warned }
		clr_country_flag = RUS_crisis_warned
		remove_mission = RUS_crisis_defence_countdown
	}
}

RUS_crisis_clear_defender = {
	clr_country_flag = RUS_crisis_defender
	if = {
		limit = { has_country_flag = RUS_crisis_added_major }
		set_major = no
		clr_country_flag = RUS_crisis_added_major
	}
}''')
s = replace(s, 'RUS_crisis_check_external_end', '''RUS_crisis_check_external_end = {
	if = {
		limit = {
			OR = {
				check_variable = { var = RUS_crisis_phase value = 1 compare = equals }
				check_variable = { var = RUS_crisis_phase value = 2 compare = equals }
			}
		}
		if = {
			limit = { OR = { exists = no is_subject = yes } }
			RUS_crisis_close = yes
		}
		else = {
			clear_temp_array = RUS_crisis_departures
			for_each_scope_loop = {
				array = global.RUS_crisis_defenders
				if = {
					limit = { OR = { exists = no NOT = { has_war_with = RUS } } }
					RUS_crisis_clear_defender = yes
					add_to_temp_array = { array = RUS_crisis_departures value = THIS }
				}
			}
			for_each_scope_loop = {
				array = RUS_crisis_departures
				remove_from_array = { array = global.RUS_crisis_defenders value = THIS }
			}
			clear_temp_array = RUS_crisis_departures
		}
	}
}''')
# Materially useful readiness replaces the removed opponent dossiers.
s += '''
# RUS. Only held perimeter states receive fortifications and anti-air batteries.
RUS_crisis_fortify_reactor_state = {
	if = {
		limit = { is_owned_by = RUS is_controlled_by = RUS }
		add_building_construction = { type = bunker level = 2 instant_build = yes }
		add_building_construction = { type = anti_air_building level = 2 instant_build = yes }
	}
}
'''
write(p, s)
Path('_tmp_rus_regional_helpers.py').write_text(Path(__file__).read_text(encoding='utf-8') if '__file__' in globals() and Path(__file__).exists() else '', encoding='utf-8') if False else None
