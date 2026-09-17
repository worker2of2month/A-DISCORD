from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str, *, loc: bool = False) -> str:
    return (ROOT / path).read_text(encoding="utf-8-sig" if loc else "utf-8")


def write(path: str, text: str, *, loc: bool = False) -> None:
    (ROOT / path).write_text(text, encoding="utf-8-sig" if loc else "utf-8", newline="\n")


def closing_brace(text: str, opening: int) -> int:
    depth = 0
    in_string = False
    escaped = False
    in_comment = False
    for i in range(opening, len(text)):
        ch = text[i]
        if in_comment:
            if ch == "\n":
                in_comment = False
            continue
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            continue
        if ch == "#":
            in_comment = True
        elif ch == '"':
            in_string = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return i + 1
    raise RuntimeError("unclosed brace")


def named_span(text: str, name: str) -> tuple[int, int]:
    m = re.search(rf"(?m)^\s*{re.escape(name)}\s*=\s*\{{", text)
    if not m:
        raise RuntimeError(f"missing block {name}")
    opening = text.index("{", m.start(), m.end())
    return m.start(), closing_brace(text, opening)


def replace_named(text: str, name: str, replacement: str) -> str:
    start, end = named_span(text, name)
    return text[:start] + replacement.rstrip() + text[end:]


def event_span(text: str, event_id: str) -> tuple[int, int]:
    marker = f"\tid = {event_id}\n"
    pos = text.find(marker)
    if pos < 0:
        raise RuntimeError(f"missing event {event_id}")
    start = text.rfind("country_event = {", 0, pos)
    if start < 0:
        raise RuntimeError(f"missing event start {event_id}")
    opening = text.index("{", start)
    return start, closing_brace(text, opening)


def replace_event(text: str, event_id: str, replacement: str) -> str:
    start, end = event_span(text, event_id)
    return text[:start] + replacement.rstrip() + text[end:]


def patch_triggers() -> None:
    path = "common/scripted_triggers/ADISCORD_STP_scripted_triggers.txt"
    text = read(path)
    if "STP_cw_any_inspection_active = {" in text:
        raise RuntimeError("inspection-active trigger already exists")
    marker = "# COUNTRY: state flags are authoritative while inspection missions are alive.\n"
    if marker not in text:
        raise RuntimeError("inspection marker changed")
    any_active = """# COUNTRY: authoritative active-inspection state. Keep this derived from state flags;\n# do not mirror the count in another country variable.\nSTP_cw_any_inspection_active = {\n\tOR = {\n\t\t2 = { has_state_flag = STP_party_inspection_active }\n\t\t3 = { has_state_flag = STP_party_inspection_active }\n\t\t29 = { has_state_flag = STP_party_inspection_active }\n\t\t45 = { has_state_flag = STP_party_inspection_active }\n\t\t46 = { has_state_flag = STP_party_inspection_active }\n\t\t53 = { has_state_flag = STP_party_inspection_active }\n\t}\n}\n\n"""
    text = text.replace(marker, any_active + marker, 1)

    start, end = named_span(text, "NOD_cw_intervention_possible")
    block = text[start:end]
    needle = "\tNOT = { has_global_flag = STP_cw_union_wars_finished }\n"
    if needle not in block:
        raise RuntimeError("NOD intervention guard changed")
    block = block.replace(
        needle,
        needle + "\tNOT = { STS = { has_country_flag = STP_cw_last_banquet_success } }\n",
        1,
    )
    text = text[:start] + block + text[end:]
    write(path, text)


def patch_effects() -> None:
    path = "common/scripted_effects/ADISCORD_STP_scripted_effects.txt"
    text = read(path)
    scheduler = """STP_schedule_next_party_inspection = {\n\tif = {\n\t\tlimit = {\n\t\t\thas_country_flag = STP_battle_for_stelander_active\n\t\t\thas_country_flag = STP_cw_inspection_chain_open\n\t\t\tNOT = { STP_cw_two_inspections_active = yes }\n\t\t}\n\t\t# Below 50 suspicion keep one commission alive; at 50+ fill the second slot.\n\t\tif = {\n\t\t\tlimit = { NOT = { STP_cw_any_inspection_active = yes } }\n\t\t\tSTP_cw_open_one_party_inspection = yes\n\t\t}\n\t\tif = {\n\t\t\tlimit = { STP_cw_second_inspection_unlocked = yes }\n\t\t\tSTP_cw_open_one_party_inspection = yes\n\t\t}\n\t}\n}"""
    text = replace_named(text, "STP_schedule_next_party_inspection", scheduler)

    start, end = named_span(text, "STP_cw_open_one_party_inspection")
    opener = text[start:end]
    if opener.count("\n\t\t1 = { }\n") != 1:
        raise RuntimeError("unexpected empty inspection random-list branch count")
    opener = opener.replace("\n\t\t1 = { }\n", "\n", 1)
    text = text[:start] + opener + text[end:]
    write(path, text)


def patch_decisions() -> None:
    path = "common/decisions/ADISCORD_STP_decisions.txt"
    text = read(path)

    delay = """\tSTP_cw_delay_inspection = {\n\t\ticon = GFX_decision_ADISCORD_state_directive\n\t\tallowed = { tag = STP }\n\t\tvisible = {\n\t\t\thas_completed_focus = STP_Count_The_Loyalists\n\t\t\thas_country_flag = STP_sided_with_Maksim_flag\n\t\t\tSTP_cw_preparation_open = yes\n\t\t\tFROM = { has_state_flag = STP_party_inspection_active }\n\t\t}\n\t\tavailable = {\n\t\t\tcustom_trigger_tooltip = { tooltip = STP_preparation_slot_available_tt STP_has_political_action_slot = yes }\n\t\t\tFROM = { has_state_flag = STP_party_inspection_active }\n\t\t}\n\t\tstate_target = yes\n\t\ttargets = { 2 3 29 45 46 53 }\n\t\t# Ownership is stable enough for the cached target list; the live commission flag stays above.\n\t\ttarget_trigger = { FROM = { is_owned_by = ROOT } }\n\t\thighlight_states = { highlight_state_targets = { state = FROM } }\n\t\ton_map_mode = map_and_decisions_view\n\t\tcost = 35\n\t\tdays_remove = 14\n\t\tdays_re_enable = 60\n\t\tfire_only_once = no\n\t\tcancel_trigger = { hidden_trigger = { NOT = { STP_cw_preparation_open = yes } } }\n\t\tcomplete_effect = {\n\t\t\tcustom_effect_tooltip = STP_inspection_delay_result_tt\n\t\t\thidden_effect = {\n\t\t\t\tSTP_political_action_slot_consume = yes\n\t\t\t\tif = { limit = { FROM = { state = 2 } } add_days_mission_timeout = { mission = STP_party_inspection_state_2 days = 14 } }\n\t\t\t\telse_if = { limit = { FROM = { state = 3 } } add_days_mission_timeout = { mission = STP_party_inspection_state_3 days = 14 } }\n\t\t\t\telse_if = { limit = { FROM = { state = 29 } } add_days_mission_timeout = { mission = STP_party_inspection_state_29 days = 14 } }\n\t\t\t\telse_if = { limit = { FROM = { state = 45 } } add_days_mission_timeout = { mission = STP_party_inspection_state_45 days = 14 } }\n\t\t\t\telse_if = { limit = { FROM = { state = 46 } } add_days_mission_timeout = { mission = STP_party_inspection_state_46 days = 14 } }\n\t\t\t\telse_if = { limit = { FROM = { state = 53 } } add_days_mission_timeout = { mission = STP_party_inspection_state_53 days = 14 } }\n\t\t\t}\n\t\t}\n\t\tcancel_effect = { hidden_effect = { STP_political_action_slot_release = yes } }\n\t\tremove_effect = { hidden_effect = { STP_political_action_slot_release = yes } }\n\t\tai_will_do = { base = 3 }\n\t}"""
    text = replace_named(text, "STP_cw_delay_inspection", delay)

    launch = """\tSTP_cw_launch_last_banquet = {\n\t\ticon = generic_prepare_civil_war\n\t\tallowed = { tag = STS }\n\t\tvisible = {\n\t\t\thas_completed_focus = STP_cw_last_banquet\n\t\t\tNOT = { has_country_flag = STP_cw_last_banquet_launched }\n\t\t}\n\t\tavailable = {\n\t\t\thas_war_with = STP\n\t\t\tcontrols_state = 3\n\t\t\tNOT = { has_country_flag = STP_cw_last_banquet_launched }\n\t\t\tNOT = {\n\t\t\t\thas_idea = STP_cw_deliberate_offensive\n\t\t\t\thas_idea = STP_cw_static_defence\n\t\t\t\thas_idea = STP_cw_front_reorganization\n\t\t\t\thas_idea = STP_cw_offensive_preparation\n\t\t\t\thas_idea = STP_cw_defensive_preparation\n\t\t\t}\n\t\t}\n\t\tcustom_cost_text = STP_cw_command_power_25_cost\n\t\tcustom_cost_trigger = { NOT = { command_power < 25 } }\n\t\tcost = 0\n\t\tfire_only_once = yes\n\t\tcomplete_effect = {\n\t\t\tadd_command_power = -25\n\t\t\tset_country_flag = STP_cw_last_banquet_launched\n\t\t\tadd_timed_idea = { idea = STP_cw_deliberate_offensive days = 21 }\n\t\t\tactivate_mission = STP_cw_last_banquet_window\n\t\t}\n\t\tai_will_do = { base = 10 }\n\t}\n\n\tSTP_cw_last_banquet_window = {\n\t\ticon = generic_prepare_civil_war\n\t\tallowed = { tag = STS }\n\t\tactivation = { always = no }\n\t\tvisible = {\n\t\t\thas_country_flag = STP_cw_last_banquet_launched\n\t\t\tNOT = { has_country_flag = STP_cw_last_banquet_success }\n\t\t\tNOT = { has_country_flag = STP_cw_last_banquet_failed }\n\t\t}\n\t\t# Missions use available as their success condition.\n\t\tavailable = { controls_state = 28 }\n\t\tcancel_trigger = { hidden_trigger = { OR = { NOT = { has_war_with = STP } has_country_flag = STP_cw_postwar } } }\n\t\tdays_mission_timeout = 21\n\t\tis_good = yes\n\t\tselectable_mission = no\n\t\tfire_only_once = yes\n\t\tcomplete_effect = {\n\t\t\tset_country_flag = STP_cw_last_banquet_success\n\t\t\tcustom_effect_tooltip = STP_cw_last_banquet_success_tt\n\t\t\thidden_effect = {\n\t\t\t\tNOD = {\n\t\t\t\t\tif = {\n\t\t\t\t\t\tlimit = { NOT = { has_country_flag = NOD_cw_entered } }\n\t\t\t\t\t\tset_country_flag = NOD_cw_offer_shown\n\t\t\t\t\t\tclr_country_flag = NOD_cw_intervention_ready\n\t\t\t\t\t\tclr_country_flag = NOD_cw_intervention_approved\n\t\t\t\t\t\tif = { limit = { has_active_mission = NOD_cw_intervention_preparation } remove_mission = NOD_cw_intervention_preparation }\n\t\t\t\t\t\tif = { limit = { has_active_mission = NOD_cw_northern_redeployment } remove_mission = NOD_cw_northern_redeployment }\n\t\t\t\t\t\tADISCORD_economy_update_postwar_demobilization = yes\n\t\t\t\t\t\tADISCORD_economy_mark_dirty = yes\n\t\t\t\t\t}\n\t\t\t\t}\n\t\t\t\tif = { limit = { has_active_mission = STP_cw_nod_warning } remove_mission = STP_cw_nod_warning }\n\t\t\t\tif = { limit = { has_active_mission = STP_cw_nod_redeployment } remove_mission = STP_cw_nod_redeployment }\n\t\t\t\tclr_country_flag = STP_cw_nod_warning_active\n\t\t\t\tset_country_flag = STP_cw_nod_warning_cancelled\n\t\t\t}\n\t\t}\n\t\ttimeout_effect = {\n\t\t\tset_country_flag = STP_cw_last_banquet_failed\n\t\t\tadd_war_support = -0.10\n\t\t\tcustom_effect_tooltip = STP_cw_last_banquet_failure_tt\n\t\t}\n\t}"""
    text = replace_named(text, "STP_cw_launch_last_banquet", launch)
    write(path, text)


def patch_events() -> None:
    path = "events/ADISCORD_STP_events.txt"
    text = read(path)
    event = """country_event = {\n\tid = ADISCORD_STP_cw.42\n\ttitle = ADISCORD_STP_cw.42.t\n\tdesc = ADISCORD_STP_cw.42.d\n\tpicture = GFX_event_adiscord_negotiation_table\n\tis_triggered_only = yes\n\ttrigger = { NOD_cw_intervention_possible = yes NOT = { has_country_flag = NOD_cw_offer_shown } }\n\timmediate = { set_country_flag = NOD_cw_offer_shown }\n\toption = {\n\t\tname = ADISCORD_STP_cw.42.a\n\t\ttrigger = { NOD_cw_intervention_possible = yes }\n\t\tai_chance = { base = 100 }\n\t\tcustom_effect_tooltip = STP_cw_nod_consent_tt\n\t\thidden_effect = {\n\t\t\tif = {\n\t\t\t\tlimit = { NOD_cw_intervention_possible = yes }\n\t\t\t\tset_country_flag = NOD_cw_intervention_approved\n\t\t\t\tactivate_mission = NOD_cw_intervention_preparation\n\t\t\t\tif = { limit = { has_global_flag = STP_cw_started STS = { exists = yes } } STS = { STP_cw_sync_nod_warning = yes country_event = { id = ADISCORD_STP_cw.40 } } }\n\t\t\t\telse = { STP = { STP_cw_sync_nod_warning = yes country_event = { id = ADISCORD_STP_cw.40 } } }\n\t\t\t}\n\t\t}\n\t}\n\toption = {\n\t\tname = ADISCORD_STP_cw.42.b\n\t\ttrigger = { NOD_cw_intervention_possible = yes }\n\t\tai_chance = { base = 0 }\n\t\thidden_effect = {\n\t\t\tif = {\n\t\t\t\tlimit = { NOD_cw_intervention_possible = yes }\n\t\t\t\tset_country_flag = NOD_cw_refused\n\t\t\t\tclr_country_flag = NOD_cw_intervention_approved\n\t\t\t}\n\t\t}\n\t}\n\toption = {\n\t\tname = ADISCORD_STP_cw.42.c\n\t\ttrigger = { NOD_cw_intervention_possible = no }\n\t\tai_chance = { base = 100 }\n\t}\n}"""
    text = replace_event(text, "ADISCORD_STP_cw.42", event)
    write(path, text)


def replace_loc_value(text: str, key: str, value: str) -> str:
    pattern = re.compile(rf'(?m)^ {re.escape(key)}(?::0)?: ".*"$')
    replacement = f' {key}: "{value}"'
    text, count = pattern.subn(replacement, text, count=1)
    if count != 1:
        raise RuntimeError(f"expected one localisation key: {key}; got {count}")
    return text


def patch_localisation() -> None:
    path = "localisation/russian/ADISCORD_STP_l_russian.yml"
    text = read(path, loc=True)
    text = replace_loc_value(
        text,
        "STP_cw_last_banquet_desc",
        "Штаб подготовит единственный решающий бросок на Бронзовый конгресс. Приказ можно отдать из контролируемого Ниансаса. После запуска у сопротивления будет §Y21 день§!, чтобы взять Фаду; наступательный план даст атаку +15%, прорыв +20% и скорость планирования +10%. Провал срока снизит поддержку войны на §R10%§!.",
    )
    additions = {
        "STP_cw_last_banquet_window": "Последний банкет: взять Фаду",
        "STP_cw_last_banquet_window_desc": "До истечения срока сопротивление должно установить контроль над Фадой и Бронзовым конгрессом. Успех сорвёт ещё не начавшуюся интервенцию Нодрула.",
        "STP_cw_last_banquet_success_tt": "§GФада взята в срок.§! Подготовка Нодрула к вмешательству в эту гражданскую войну будет закрыта, если его войска ещё не вступили.",
        "STP_cw_last_banquet_failure_tt": "§RСрок истёк.§! Поддержка войны снижается на §R10%§!.",
        "ADISCORD_STP_cw.42.c": "Обстоятельства уже изменились. Закрыть проект.",
    }
    anchor = ' ADISCORD_STP_cw.42.b: "Не превращать влияние в оккупацию."\n'
    if anchor not in text:
        raise RuntimeError("NOD event localisation anchor changed")
    for key in additions:
        if re.search(rf"(?m)^ {re.escape(key)}(?::0)?:", text):
            raise RuntimeError(f"localisation key already exists: {key}")
    payload = "".join(f' {key}: "{value}"\n' for key, value in additions.items())
    text = text.replace(anchor, anchor + payload, 1)
    write(path, text, loc=True)


def main() -> None:
    patch_triggers()
    patch_effects()
    patch_decisions()
    patch_events()
    patch_localisation()


if __name__ == "__main__":
    main()
