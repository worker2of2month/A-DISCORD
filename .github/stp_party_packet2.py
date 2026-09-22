from pathlib import Path
import re
from tools.tests.test_adiscord_stp_party_route import parse_clausewitz, one, signature

FOCUS = Path('common/national_focus/ADISCORD_national_focus_STP.txt')
EFFECTS = Path('common/scripted_effects/ADISCORD_STP_scripted_effects.txt')
DECISIONS = Path('common/decisions/ADISCORD_STP_decisions.txt')


def closing(text, opening):
    depth = 0
    quoted = comment = escaped = False
    for pos in range(opening, len(text)):
        c = text[pos]
        if comment:
            if c == '\n': comment = False
            continue
        if quoted:
            if c == '"' and not escaped: quoted = False
            escaped = c == '\\' and not escaped
            continue
        if c == '#': comment = True
        elif c == '"': quoted = True
        elif c == '{': depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0: return pos + 1
    raise AssertionError('Unclosed script block')


def named_span(text, name):
    matches = list(re.finditer(r'(?m)^[ \t]*' + re.escape(name) + r'\s*=\s*\{', text))
    assert len(matches) == 1, (name, len(matches))
    start = matches[0].start()
    return start, closing(text, text.index('{', start))


def edit_named(text, name, transform):
    start, end = named_span(text, name)
    return text[:start] + transform(text[start:end]) + text[end:]


def edit_focus(text, fid, transform):
    matches = list(re.finditer(r'(?m)^\s*id\s*=\s*' + re.escape(fid) + r'\s*$', text))
    assert len(matches) == 1, fid
    starts = list(re.finditer(r'(?m)^[ \t]*focus\s*=\s*\{', text[:matches[0].start()]))
    start = starts[-1].start()
    end = closing(text, text.index('{', start))
    return text[:start] + transform(text[start:end]) + text[end:]


def append_reward(focus, payload):
    return edit_named(focus, 'completion_reward', lambda reward: reward[:-1].rstrip() + '\n' + payload + '\n\t\t}')


def read(path):
    return path.read_text(encoding='utf-8-sig')


def write(path, text):
    bom = path.read_bytes().startswith(b'\xef\xbb\xbf')
    path.write_text(text.rstrip() + '\n', encoding='utf-8-sig' if bom else 'utf-8')
    assert path.read_bytes().startswith(b'\xef\xbb\xbf') == bom


focus = original_focus = read(FOCUS)
effects = read(EFFECTS)
decisions = original_decisions = read(DECISIONS)
original_ids = [one(f.value, 'id') for tree in parse_clausewitz(focus) if tree.key == 'focus_tree' for f in tree.value if f.key == 'focus']
targets = {
    'STP_PRESIDENT_REMAINS_IN_OFFICE': {'conservatives': 8},
    'STP_PARTY_DISCIPLINE': {'security': 10},
    'STP_EMERGENCY_PRESIDIUM': {'conservatives': 6, 'security': 6},
    'STP_THE_PARTY_CLOSES_RANKS': {'conservatives': 8, 'army': 4},
    'STP_cw_protocol_office': {'conservatives': 8},
    'STP_cw_press_office': {'radicals': 8},
    'STP_cw_party_mandate': {'conservatives': 10, 'borons': 10},
    'STP_cw_quiet_registers': {'conservatives': 10, 'borons': 6},
}
concessions = ('STP_GUARANTEE_MINISTERS', 'STP_ROTATE_DISTRICT_COMMAND', 'STP_cw_capital_oath')
for fid in (*targets, *concessions):
    def change(block, fid=fid):
        pattern = r'(?m)^(?P<indent>[ \t]*)set_temp_variable = \{ var = STP_apparatus_loyalty_change value = [0-9]+ \}\n[ \t]*STP_change_apparatus_loyalty = yes'
        found = list(re.finditer(pattern, block))
        assert len(found) == 1, fid
        indent = found[0].group('indent')
        replacement = '\n'.join(indent + f'add_to_variable = {{ var = STP_pf_{faction}_support value = {value} }}' for faction, value in targets.get(fid, {}).items())
        if fid in targets:
            replacement += '\n' + indent + 'STP_refresh_apparatus_loyalty = yes'
        block = re.sub(pattern, lambda _: replacement, block)
        tooltip = r'(?m)^[ \t]*custom_effect_tooltip = STP_cw_loyalty_plus_[0-9]+_tt[ \t]*\n'
        assert len(re.findall(tooltip, block)) == 1, fid
        replacement = '\t\t\tcustom_effect_tooltip = ' + fid + '_strategy_tt\n' if fid in targets else ''
        block = re.sub(tooltip, lambda _: replacement, block)
        return block
    focus = edit_focus(focus, fid, change)

specializations = {
    'STP_GUARANTEE_MINISTERS': (1, -4),
    'STP_defense_budget': (2, -4),
    'STP_cw_protect_congress': (1, -3),
    'STP_cw_capital_oath': (3, -7),
}
for fid, (stage, days) in specializations.items():
    payload = f'\t\t\tcustom_effect_tooltip = {fid}_strategy_tt\n\t\t\thidden_effect = {{ add_to_variable = {{ var = STP_ps_reorg_{stage}_specialization_days value = {days} }} }}'
    focus = edit_focus(focus, fid, lambda block, payload=payload: append_reward(block, payload))

# New concessions stop at 60%; historical higher influence is not confiscated.
def cap_concessions(block):
    old = '\t\tset_temp_variable = { var = STP_pf_gain value = 5 }'
    assert block.count(old) == 1
    new = old + '''
		set_temp_variable = { var = STP_pf_gain_room value = 60 }
		subtract_from_temp_variable = { var = STP_pf_gain_room value = STP_pf_old_influence }
		if = {
			limit = { check_variable = { var = STP_pf_old_influence value = 60 compare = greater_than_or_equals } }
			set_temp_variable = { var = STP_pf_gain value = 0 }
		}
		else_if = {
			limit = { check_variable = { var = STP_pf_gain_room value = 5 compare = less_than } }
			set_temp_variable = { var = STP_pf_gain value = STP_pf_gain_room }
		}'''
    return block.replace(old, new)
effects = edit_named(effects, 'STP_pf_shift', cap_concessions)

# All time adjustments belong to a new order, never the resume/load path.
for stage, faction in ((1, 'conservatives'), (2, 'merchants'), (3, 'army')):
    name = f'STP_ps_adjust_reorg_{stage}'
    assert name not in effects
    effects += f'''

# COUNTRY STP: snapshot institutional preparation and faction cooperation at payment.
{name} = {{
	if = {{
		limit = {{ STP_ps_war_active = yes has_active_mission = STP_ps_reorg_{stage} }}
		if = {{
			limit = {{ has_variable = STP_ps_reorg_{stage}_specialization_days }}
			add_days_mission_timeout = {{ mission = STP_ps_reorg_{stage} days = STP_ps_reorg_{stage}_specialization_days }}
		}}
		if = {{
			limit = {{ has_country_flag = STP_pf_initialized check_variable = {{ var = STP_pf_{faction}_support value = 35 compare = less_than }} }}
			add_days_mission_timeout = {{ mission = STP_ps_reorg_{stage} days = 7 }}
		}}
	}}
}}
'''
    for mode in ('funded', 'administrative'):
        did = f'STP_ps_reorg_{stage}_{mode}'
        def amend(block, stage=stage, name=name):
            old = f'activate_mission = STP_ps_reorg_{stage}'
            assert block.count(old) == 1
            return block.replace(old, old + '\n\t\t\t\t\t' + name + ' = yes')
        decisions = edit_named(decisions, did, amend)
    did = 'STP_pf_negotiate_' + faction
    def ai_priority(block, stage=stage, faction=faction):
        def amend(ai):
            return ai[:-1].rstrip() + f'\n\t\t\tmodifier = {{ factor = 8 STP_ps_war_active = yes check_variable = {{ var = STP_ps_stage value = {stage} compare = equals }} check_variable = {{ var = STP_pf_{faction}_support value = 35 compare = less_than }} }}\n\t\t}}'
        return edit_named(block, 'ai_will_do', amend)
    decisions = edit_named(decisions, did, ai_priority)

cleanup = '\n'.join(f'\tclear_variable = STP_ps_reorg_{i}_specialization_days' for i in (1, 2, 3))
effects = edit_named(effects, 'STP_ps_close_defence', lambda block: block[:-1].rstrip() + '\n' + cleanup + '\n}')
effects = edit_named(effects, 'STP_pf_clear', lambda block: block[:-1].rstrip() + '\n' + cleanup + '\n}')

start = '''STP_pw_party_start_nod_invasion_threat = {
	if = {
		limit = {
			tag = STP
			has_country_flag = STP_cw_postwar
			NOT = {
				OR = {
					has_country_flag = STP_pw_party_nod_threat_active
					has_country_flag = STP_pw_party_nod_invasion_active
					has_country_flag = STP_pw_party_nod_invasion_defeated
					has_country_flag = STP_pw_party_nod_invasion_lost
				}
			}
		}
		if = {
			limit = { OR = { has_capitulated = yes is_subject = yes } }
			set_country_flag = STP_pw_party_nod_invasion_lost
			mark_focus_tree_layout_dirty = yes
		}
		else_if = {
			limit = { NOD = { exists = yes has_capitulated = no is_subject = no } }
			if = {
				limit = { has_war_with = NOD }
				set_country_flag = STP_pw_party_nod_invasion_active
			}
			else = {
				set_country_flag = STP_pw_party_nod_threat_active
				activate_mission = STP_pw_party_nod_invasion_countdown
				country_event = { id = ADISCORD_STP_pc.28 hours = 1 }
			}
		}
		else = {
			set_country_flag = STP_pw_party_nod_invasion_defeated
			mark_focus_tree_layout_dirty = yes
		}
	}
}'''
launch = '''STP_pw_party_launch_nod_invasion = {
	if = {
		limit = { tag = STP has_country_flag = STP_pw_party_nod_threat_active }
		clr_country_flag = STP_pw_party_nod_threat_active
		if = {
			limit = { OR = { has_capitulated = yes is_subject = yes } }
			clr_country_flag = STP_pw_party_nod_invasion_active
			set_country_flag = STP_pw_party_nod_invasion_lost
			mark_focus_tree_layout_dirty = yes
		}
		else_if = {
			limit = { NOD = { exists = yes has_capitulated = no is_subject = no } }
			set_country_flag = STP_pw_party_nod_invasion_active
			NOD = {
				add_timed_idea = { idea = STP_pw_nod_invasion_mandate days = 365 }
				if = { limit = { ROOT = { NOT = { has_war_with = NOD } } } declare_war_on = { target = STP type = annex_everything } }
			}
			country_event = { id = ADISCORD_STP_pc.29 hours = 1 }
		}
		else = {
			clr_country_flag = STP_pw_party_nod_invasion_active
			set_country_flag = STP_pw_party_nod_invasion_defeated
			mark_focus_tree_layout_dirty = yes
		}
	}
}'''
# Use a country-scope guard before the NOD scope so native and fixture scopes agree.
launch = launch.replace('''			NOD = {
				add_timed_idea = { idea = STP_pw_nod_invasion_mandate days = 365 }
				if = { limit = { ROOT = { NOT = { has_war_with = NOD } } } declare_war_on = { target = STP type = annex_everything } }
			}''', '''			NOD = { add_timed_idea = { idea = STP_pw_nod_invasion_mandate days = 365 } }
			if = {
				limit = { NOT = { has_war_with = NOD } }
				NOD = { declare_war_on = { target = STP type = annex_everything } }
			}''')
effects = edit_named(effects, 'STP_pw_party_start_nod_invasion_threat', lambda _: start)
effects = edit_named(effects, 'STP_pw_party_launch_nod_invasion', lambda _: launch)

# Keep the existing file owners and preserve each original decision/focus identifier.
new_ids = [one(f.value, 'id') for tree in parse_clausewitz(focus) if tree.key == 'focus_tree' for f in tree.value if f.key == 'focus']
assert new_ids == original_ids
old_decisions = {d.key: d.value for c in parse_clausewitz(original_decisions) for d in c.value if isinstance(d.value, list)}
new_decisions = {d.key: d.value for c in parse_clausewitz(decisions) for d in c.value if isinstance(d.value, list)}
assert old_decisions.keys() == new_decisions.keys()
for stage in (1, 2, 3):
    for mode in ('funded', 'administrative'):
        name = f'STP_ps_reorg_{stage}_{mode}'
        a, b = named_span(original_decisions, name)
        c, d = named_span(decisions, name)
        stripped = re.sub(r'(?m)^[ \t]*STP_ps_adjust_reorg_[123] = yes\n', '', decisions[c:d])
        assert signature(parse_clausewitz(stripped)) == signature(parse_clausewitz(original_decisions[a:b])), name
for path, text in ((FOCUS, focus), (EFFECTS, effects), (DECISIONS, decisions)):
    parse_clausewitz(text)
    write(path, text)

labels = {
    'russian': {'conservatives': 'Консерваторы', 'security': 'Силовики', 'army': 'Армейское командование', 'radicals': 'Радикалы', 'borons': 'Бороны'},
    'english': {'conservatives': 'Conservatives', 'security': 'Security services', 'army': 'Army command', 'radicals': 'Radicals', 'borons': 'Borons'},
}
strategy_text = {
    'russian': {
        'STP_GUARANTEE_MINISTERS': 'Гарантии министрам сокращают этап восстановления связи на §G4 дня§! в обоих вариантах реорганизации. Уступка консерваторам сохраняет недовольство радикалов.',
        'STP_defense_budget': 'Оборонный бюджет сокращает этап восстановления снабжения на §G4 дня§! в обоих вариантах реорганизации. Военные заводы остаются альтернативой гражданскому резерву казны.',
        'STP_cw_protect_congress': 'Подготовленная оборона сокращает первый этап реорганизации на §G3 дня§!; укрепление Конгресса и оборонный резерв сохраняются. Этот курс исключает мобильный резерв.',
        'STP_cw_capital_oath': 'Мобильный резерв сокращает завершающую наступательную подготовку на §G7 дней§!. Он не отменяет предыдущие этапы и исключает курс на укрепление Конгресса.',
    },
    'english': {
        'STP_GUARANTEE_MINISTERS': 'Ministerial guarantees shorten communications recovery by §G4 days§! for either reorganisation option. The concession to conservatives retains the radicals\' opposition.',
        'STP_defense_budget': 'The defence budget shortens supply recovery by §G4 days§! for either reorganisation option. Military factories remain an alternative to the civilian treasury reserve.',
        'STP_cw_protect_congress': 'Prepared defence shortens the first reorganisation stage by §G3 days§! while retaining Congress fortification and the defensive reserve. This course excludes the mobile reserve.',
        'STP_cw_capital_oath': 'The mobile reserve shortens final offensive preparation by §G7 days§!. Earlier recovery stages remain mandatory; this course excludes Congress fortification.',
    },
}

for lang in ('russian', 'english'):
    path = Path(f'localisation/{lang}/ADISCORD_STP_l_{lang}.yml')
    loc = read(path)
    def put(key, value):
        global_dummy = None
        assert '\n' not in value and '"' not in value, key
        pattern = r'(?m)^ ' + re.escape(key) + r':(?:\d+)?[ \t]*"[^\r\n]*"[ \t]*$'
        matches = list(re.finditer(pattern, loc_values[0]))
        line = ' ' + key + ': "' + value + '"'
        assert len(matches) <= 1, key
        loc_values[0] = re.sub(pattern, lambda _: line, loc_values[0]) if matches else loc_values[0].rstrip() + '\n' + line + '\n'
    loc_values = [loc]
    for fid, supported in targets.items():
        text = '; '.join(labels[lang][faction] + ': §G+' + str(value) + '§!' for faction, value in supported.items()) + '.'
        put(fid + '_strategy_tt', ('Поддержка фракций: ' if lang == 'russian' else 'Faction support: ') + text)
    for fid, text in strategy_text[lang].items():
        put(fid + '_strategy_tt', text)
    for stage, price, base, group in ((1, 900, 21, 'консерваторов'), (2, 1800, 21, 'торговцев'), (3, 2500, 28, 'армейского командования')):
        for mode in ('funded', 'administrative'):
            duration = base + (14 if mode == 'administrative' else 0)
            if lang == 'russian':
                price_label = f'Цена: {price} казны.' if mode == 'funded' else 'Без расхода казны.'
                preparations = {1: 'Готовая радиосеть: -7 дней; гарантии министрам: -4; оборона Конгресса: -3.', 2: 'Готовый резервный штаб: -7 дней; оборонный бюджет: -4.', 3: 'Мобильный резерв: -7 дней.'}[stage]
                value = f'{price_label} Базовый срок: {duration} дн. {preparations} При поддержке {group} ниже 35 добавляется 7 дней. Срок фиксируется при начале заказа; поздние переговоры не пересчитывают его. Потеря правительства ставит работу на паузу; окончание войны возвращает неиспользованный денежный резерв.'
            else:
                price_label = f'Cost: {price} treasury units.' if mode == 'funded' else 'No treasury cost.'
                preparations = {1: 'Completed radio network: -7 days; ministerial guarantees: -4; Congress defence: -3.', 2: 'Completed reserve headquarters: -7 days; defence budget: -4.', 3: 'Mobile reserve: -7 days.'}[stage]
                group_en = {1: 'conservative', 2: 'merchant', 3: 'army command'}[stage]
                value = f'{price_label} Base duration: {duration} days. {preparations} {group_en.capitalize()} support below 35 adds 7 days. Duration is fixed when the order begins; later negotiations do not recalculate it. Loss of government pauses work; the end of war refunds the unused cash reserve.'
            put(f'STP_ps_reorg_{stage}_{mode}_desc', value)
    if lang == 'russian':
        put('STP_ps_preparation_report', '§YПодготовка правительства§!\\nГражданский курс ускоряет связь, арсеналы - снабжение, мобильный резерв - наступательную подготовку. Радиосеть и резервный штаб помогают только после завершения их оплаченных проектов. При поддержке нужной фракции ниже 35 новый этап длится на 7 дней дольше; бесплатная реорганизация остаётся доступна.')
        put('STP_party_factions_desc', 'Поддержка определяет сотрудничество фракции, влияние - её вес. Уступки одной группе сохраняют недовольство соперников: фокусы больше не обязаны усиливать всех сразу. Переговоры: 35 политической власти, общий интервал 30 дней. При влиянии от 60% новые должности не передаются, но поддержку восстановить можно.\\n[STPGetPartyPreparationReport]')
    else:
        put('STP_ps_preparation_report', '§YGovernment preparation§!\\nThe civilian course accelerates communications, arsenals accelerate supply, and the mobile reserve accelerates offensive preparation. Radio and reserve headquarters help only after their funded projects finish. A relevant faction below 35 support adds 7 days to a new stage; free reorganisation remains available.')
        put('STP_party_factions_desc', 'Support determines cooperation; influence determines political weight. Concessions retain rival opposition instead of making every faction stronger. Negotiations cost 35 political power and share a 30-day interval. At 60% influence or above, support can recover without handing over more offices.\\n[STPGetPartyPreparationReport]')
    write(path, loc_values[0])

# Preserve prices, scopes and native source ownership; add only the design contract.
doc = Path('docs/development/focus-effects.md')
text = read(doc)
heading = '### Партийная коалиция и срок реорганизации'
assert heading not in text
text += '''

### Партийная коалиция и срок реорганизации

Поддержка фракций и общая верность аппарата не взаимозаменяемы. Институциональные
фокусы повышают поддержку названных групп; уступки через `STP_pf_shift` сохраняют
потери поддержки соперников. Новая уступка передаёт не более 5 пунктов влияния и
не поднимает выбранную группу выше 60%. Историческое влияние выше 60% не изымается;
переговоры продолжают восстанавливать поддержку за ту же цену и с тем же интервалом.

Довоенные курсы сохраняют числовую поправку к соответствующему этапу:
гарантии министрам -4 дня связи, оборонный бюджет -4 дня снабжения,
оборона Конгресса -3 дня связи, мобильный резерв -7 дней наступательной подготовки.
Поправки являются результатом институтов, а не проверками старого дерева:
военное дерево загружается с `keep_completed = no`.
Радиосеть и резервный штаб сохраняют собственное сокращение на 7 дней.
При поддержке консерваторов, торговцев или командования ниже 35 соответствующий
новый этап получает 7 дополнительных дней. Цена и бесплатная административная
альтернатива не меняются. Максимально подготовленный оплаченный этап связи
занимает 7 дней, снабжения -10, наступательной подготовки -21.

`STP_ps_adjust_reorg_1/2/3` вызываются только после активации нового оплаченного
или административного заказа. Пауза и загрузка сохраняют оставшийся срок и не
применяют поправку повторно. Завершение войны и закрытие партийной механики
удаляют коэффициенты специализации. Утрата правительства сохраняет резерв
и оставшиеся дни через существующую процедуру перемещения кабинета.

Начало нодрульской угрозы вызывается наградой суверенитета и не проверяет
завершённость этого же фокуса. Активный или завершённый кризис повторно не
запускается. По истечении срока существующая война остаётся активной без второй
декларации; поражение Стеландера и недоступность Нодрула имеют разные исходы.
'''
write(doc, text)
print('SECOND_PACKAGE_APPLIED', {'focuses_retained': len(original_ids), 'decisions_retained': len(old_decisions), 'focused_rewards_changed': len(set(targets) | set(concessions) | set(specializations))})
