from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(__file__).resolve().parents[1]


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


def patch_effects() -> None:
    path = "common/scripted_effects/ADISCORD_STP_scripted_effects.txt"
    text = read(path)
    if "STP_cw_cancel_pending_nod_intervention = {" in text:
        raise RuntimeError("pending-NOD cancel helper already exists")

    old_success = """STP_cw_resolve_last_banquet_success = {
	if = {
		limit = { NOT = { has_country_flag = STP_cw_last_banquet_resolved } }
		set_country_flag = STP_cw_last_banquet_resolved
		clr_country_flag = STP_cw_last_banquet_started
		remove_mission = STP_cw_last_banquet_deadline
	}
}"""
    if text.count(old_success) != 1:
        raise RuntimeError(f"Last Banquet success block changed: {text.count(old_success)} matches")

    replacement = """# COUNTRY (STS): once the Bronze Congress is seized in time, a Nodrul
# intervention that has not entered the war is permanently closed for this civil war.
STP_cw_cancel_pending_nod_intervention = {
	if = {
		limit = { NOD = { exists = yes NOT = { has_country_flag = NOD_cw_entered } } }
		NOD = {
			set_country_flag = NOD_cw_offer_shown
			if = {
				limit = {
					OR = {
						has_country_flag = NOD_cw_intervention_approved
						has_country_flag = NOD_cw_intervention_ready
						has_active_mission = NOD_cw_intervention_preparation
						has_active_mission = NOD_cw_northern_redeployment
					}
				}
				clr_country_flag = NOD_cw_intervention_approved
				clr_country_flag = NOD_cw_intervention_ready
				if = { limit = { has_active_mission = NOD_cw_intervention_preparation } remove_mission = NOD_cw_intervention_preparation }
				if = { limit = { has_active_mission = NOD_cw_northern_redeployment } remove_mission = NOD_cw_northern_redeployment }
				ADISCORD_economy_update_postwar_demobilization = yes
				ADISCORD_economy_mark_dirty = yes
			}
		}
		if = { limit = { has_active_mission = STP_cw_nod_warning } remove_mission = STP_cw_nod_warning }
		if = { limit = { has_active_mission = STP_cw_nod_redeployment } remove_mission = STP_cw_nod_redeployment }
		clr_country_flag = STP_cw_nod_warning_active
		set_country_flag = STP_cw_nod_warning_cancelled
	}
}

STP_cw_resolve_last_banquet_success = {
	if = {
		limit = { NOT = { has_country_flag = STP_cw_last_banquet_resolved } }
		set_country_flag = STP_cw_last_banquet_resolved
		set_country_flag = STP_cw_last_banquet_success
		clr_country_flag = STP_cw_last_banquet_started
		remove_mission = STP_cw_last_banquet_deadline
		STP_cw_cancel_pending_nod_intervention = yes
	}
}"""
    text = text.replace(old_success, replacement, 1)
    write(path, text)


def patch_triggers() -> None:
    path = "common/scripted_triggers/ADISCORD_STP_scripted_triggers.txt"
    text = read(path)
    start, end = named_span(text, "NOD_cw_intervention_possible")
    block = text[start:end]
    guard = "\tNOT = { STS = { has_country_flag = STP_cw_last_banquet_success } }\n"
    if guard in block:
        raise RuntimeError("Last Banquet success guard already exists")
    anchor = "\tNOT = { has_global_flag = STP_cw_union_wars_finished }\n"
    if block.count(anchor) != 1:
        raise RuntimeError("NOD intervention anchor changed")
    block = block.replace(anchor, anchor + guard, 1)
    text = text[:start] + block + text[end:]
    write(path, text)


def patch_events() -> None:
    path = "events/ADISCORD_STP_events.txt"
    text = read(path)
    event = """country_event = {
	id = ADISCORD_STP_cw.42
	title = ADISCORD_STP_cw.42.t
	desc = ADISCORD_STP_cw.42.d
	picture = GFX_event_adiscord_negotiation_table
	is_triggered_only = yes
	trigger = { NOD_cw_intervention_possible = yes NOT = { has_country_flag = NOD_cw_offer_shown } }
	immediate = { set_country_flag = NOD_cw_offer_shown }
	option = {
		name = ADISCORD_STP_cw.42.a
		trigger = { NOD_cw_intervention_possible = yes }
		ai_chance = { base = 100 }
		custom_effect_tooltip = STP_cw_nod_consent_tt
		hidden_effect = {
			if = {
				limit = { NOD_cw_intervention_possible = yes }
				set_country_flag = NOD_cw_intervention_approved
				activate_mission = NOD_cw_intervention_preparation
				if = { limit = { has_global_flag = STP_cw_started STS = { exists = yes } } STS = { STP_cw_sync_nod_warning = yes country_event = { id = ADISCORD_STP_cw.40 } } }
				else = { STP = { STP_cw_sync_nod_warning = yes country_event = { id = ADISCORD_STP_cw.40 } } }
			}
		}
	}
	option = {
		name = ADISCORD_STP_cw.42.b
		trigger = { NOD_cw_intervention_possible = yes }
		ai_chance = { base = 0 }
		hidden_effect = {
			if = {
				limit = { NOD_cw_intervention_possible = yes }
				set_country_flag = NOD_cw_refused
				clr_country_flag = NOD_cw_intervention_approved
			}
		}
	}
	option = {
		name = ADISCORD_STP_cw.42.c
		trigger = { NOD_cw_intervention_possible = no }
		ai_chance = { base = 100 }
	}
}"""
    text = replace_event(text, "ADISCORD_STP_cw.42", event)
    write(path, text)


def patch_localisation() -> None:
    path = "localisation/russian/ADISCORD_STP_l_russian.yml"
    text = read(path, loc=True)
    if re.search(r"(?m)^ ADISCORD_STP_cw\.42\.c(?::0)?:", text):
        raise RuntimeError("stale-card localisation already exists")
    anchor = ' ADISCORD_STP_cw.42.b: "Не превращать влияние в оккупацию."\n'
    if text.count(anchor) != 1:
        raise RuntimeError("event 42 localisation anchor changed")
    text = text.replace(
        anchor,
        anchor + ' ADISCORD_STP_cw.42.c: "Бронзовый конгресс уже потерян. Закрыть проект."\n',
        1,
    )
    warning_old = "Победите партию раньше, чтобы сорвать интервенцию."
    warning_new = "Победите партию или возьмите Бронзовый конгресс в срок «Последнего банкета», чтобы сорвать интервенцию."
    if text.count(warning_old) != 1:
        raise RuntimeError("Nodrul warning prose changed")
    text = text.replace(warning_old, warning_new, 1)
    write(path, text, loc=True)


def main() -> None:
    patch_effects()
    patch_triggers()
    patch_events()
    patch_localisation()


if __name__ == "__main__":
    main()
