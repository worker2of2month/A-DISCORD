"""Static contract for the TFF-NOD wartime confederation."""

from __future__ import annotations

import re
import struct
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

CHARACTERS = Path("common/characters/TFF.txt")
HISTORY = Path("history/countries/TFF - TheFreeFrontier.txt")
ON_ACTIONS = Path("common/on_actions/03_ADISCORD_TFF_on_actions.txt")
EFFECTS = Path("common/scripted_effects/ADISCORD_TFF_effects.txt")
IDEAS = Path("common/ideas/ADISCORD_TFF_ideas.txt")
EVENTS = Path("events/ADISCORD_TFF_events.txt")
DECISIONS = Path("common/decisions/ADISCORD_TFF_decisions.txt")
CATEGORIES = Path("common/decisions/categories/ADISCORD_TFF_categories.txt")
COSMETIC = Path("common/countries/cosmetic.txt")
IDEOLOGIES = Path("common/ideologies/00_ideologies.txt")
SCRIPTED_LOC = Path("common/scripted_localisation/ADISCORD_ideologies.txt")
PORTRAITS_GFX = Path("interface/ADISCORD_leader_portraits.gfx")
MINISTERS = Path("common/ideas/ADISCORD_ministers_all_countries.txt")
RU_LOC = Path("localisation/russian/ADISCORD_TFF_l_russian.yml")
EN_LOC = Path("localisation/english/ADISCORD_TFF_l_english.yml")
RU_CHAR = Path("localisation/russian/nsb_characters_l_russian.yml")
EN_CHAR = Path("localisation/english/nsb_characters_l_english.yml")
RU_PARTIES = Path("localisation/russian/parties_l_russian.yml")
PORTRAIT = Path("gfx/leaders/TFF/portrait_TFF_Colt_Ardent.png")
ABSENT_PORTRAIT = Path("gfx/leaders/TFF/portrait_TFF_absent_government.png")
COUNTRY_TAGS = Path("common/country_tags/00_countries.txt")

BORDER_PROVINCES = ("7", "61", "16384")
DECISION_IDS = (
    "TFF_call_the_free_rifles",
    "TFF_coordinate_the_communes",
    "TFF_establish_common_supply_depots",
    "TFF_fortify_the_nodrul_border",
    "TFF_authorize_unified_field_command",
)
LOC_KEYS = (
    "TFF_frontier_defense_confederation",
    "TFF_frontier_defense_confederation_DEF",
    "TFF_frontier_defense_confederation_ADJ",
    "ADISCORD_TFF.1.t",
    "ADISCORD_TFF.1.d",
    "ADISCORD_TFF.1.a",
    "ADISCORD_TFF_empty_chair_result_tt",
    "TFF_emergency_frontier_command",
    "TFF_frontier_at_war",
    *DECISION_IDS,
)


def read(relative: Path) -> str:
    return (ROOT / relative).read_text(encoding="utf-8-sig")


def named_block(text: str, name: str) -> str:
    match = re.search(rf"(?m)^\s*{re.escape(name)}\s*=\s*\{{", text)
    if not match:
        raise ValueError(f"missing block {name}")
    start = text.find("{", match.start())
    depth = 0
    for index in range(start, len(text)):
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
            if depth == 0:
                return text[match.start() : index + 1]
    raise ValueError(f"unterminated block {name}")


def event_block(text: str, event_id: str) -> str:
    for match in re.finditer(r"(?m)^country_event\s*=\s*\{", text):
        start = text.find("{", match.start())
        depth = 0
        for index in range(start, len(text)):
            if text[index] == "{":
                depth += 1
            elif text[index] == "}":
                depth -= 1
                if depth == 0:
                    block = text[match.start() : index + 1]
                    if re.search(rf"(?m)^\s*id\s*=\s*{re.escape(event_id)}\s*$", block):
                        return block
                    break
    raise ValueError(f"missing country event {event_id}")


def loc_value(source: str, key: str) -> str:
    match = re.search(rf'(?m)^\s*{re.escape(key)}:\s*"(.*)"\s*$', source)
    return match.group(1) if match else ""


def collect_issues() -> list[str]:
    issues: list[str] = []
    paths = (
        CHARACTERS, HISTORY, ON_ACTIONS, EFFECTS, IDEAS, EVENTS, DECISIONS,
        CATEGORIES, COSMETIC, IDEOLOGIES, SCRIPTED_LOC, PORTRAITS_GFX,
        MINISTERS, RU_LOC, EN_LOC, RU_CHAR, EN_CHAR, RU_PARTIES, COUNTRY_TAGS,
    )
    texts = {}
    for path in paths:
        full = ROOT / path
        if not full.exists():
            issues.append(f"missing {path.as_posix()}")
            continue
        data = full.read_bytes()
        if path.suffix == ".txt" and data.startswith(b"\xef\xbb\xbf"):
            issues.append(f"{path.as_posix()} must be UTF-8 without a BOM")
        if path.suffix == ".yml" and not data.startswith(b"\xef\xbb\xbf"):
            issues.append(f"{path.as_posix()} must keep a UTF-8 BOM")
        texts[path] = data.decode("utf-8-sig")

    if CHARACTERS not in texts:
        return issues

    characters = texts[CHARACTERS]
    if "The_Absent_Government" not in characters:
        issues.append("The_Absent_Government must remain in common/characters/TFF.txt")
    try:
        colt = named_block(characters, "TFF_Colt_Ardent")
    except ValueError as exc:
        issues.append(str(exc))
        colt = ""
    if "GFX_portrait_TFF_Colt_Ardent" not in colt:
        issues.append("TFF_Colt_Ardent must use GFX_portrait_TFF_Colt_Ardent")
    if "ideology = tff_emergency_war_coordinator" not in colt:
        issues.append("TFF_Colt_Ardent must keep an anarchism subtype country_leader role")
    if characters.count("TFF_Colt_Ardent = {") != 1:
        issues.append("TFF_Colt_Ardent must be defined exactly once")
    if "minister_TFF_Colt_Ardent" in characters:
        issues.append("minister_TFF_Colt_Ardent must not be reused as a character ID")

    history = texts.get(HISTORY, "")
    if "recruit_character = The_Absent_Government" not in history:
        issues.append("TFF history must still recruit The_Absent_Government")
    if "recruit_character = TFF_Colt_Ardent" not in history:
        issues.append("TFF history must recruit TFF_Colt_Ardent")
    if "promote_character = { character = The_Absent_Government ideology = anarchism_ideology }" not in history:
        issues.append("TFF history must keep The Absent Government as the starting leader")
    if history.find("recruit_character = The_Absent_Government") > history.find("recruit_character = TFF_Colt_Ardent"):
        issues.append("The Absent Government must be recruited before Colt")
    if "minister_TFF_Colt_Ardent" not in history:
        issues.append("starting TFF cabinet must still include minister_TFF_Colt_Ardent")
    if "ruling_party = anarchism" not in history:
        issues.append("TFF must keep anarchism as the starting ruling party")

    ministers = texts.get(MINISTERS, "")
    if "minister_TFF_Colt_Ardent =" not in ministers:
        issues.append("minister_TFF_Colt_Ardent advisor idea must remain")

    on_actions = texts.get(ON_ACTIONS, "")
    try:
        war = named_block(on_actions, "on_war_relation_added")
    except ValueError as exc:
        issues.append(str(exc))
        war = ""
    if on_actions.count("on_war_relation_added = {") != 1:
        issues.append("TFF wartime hook must have exactly one on_war_relation_added")
    for token in (
        "ROOT = { tag = TFF }",
        "FROM = { tag = NOD }",
        "ROOT = { tag = NOD }",
        "FROM = { tag = TFF }",
        "TFF_nodrul_war_crisis_started",
        "country_event = { id = ADISCORD_TFF.1 }",
    ):
        if token not in war:
            issues.append(f"on_war_relation_added lacks {token}")
    if war.find("set_country_flag = TFF_nodrul_war_crisis_started") > war.find("country_event = { id = ADISCORD_TFF.1 }"):
        issues.append("one-shot crisis flag must be set before the event is fired")
    for recurring in ("on_daily", "on_weekly", "on_monthly", "on_yearly", "mean_time_to_happen", "every_country"):
        if recurring in on_actions:
            issues.append(f"TFF wartime on_actions must not use {recurring}")

    effects = texts.get(EFFECTS, "")
    try:
        form = named_block(effects, "ADISCORD_TFF_form_wartime_confederation")
    except ValueError as exc:
        issues.append(str(exc))
        form = ""
    for token in (
        "set_country_flag = TFF_wartime_confederation_formed",
        "set_country_flag = TFF_wartime_command_active",
        "set_cosmetic_tag = TFF_frontier_defense_confederation",
        "promote_character = { character = TFF_Colt_Ardent ideology = tff_emergency_war_coordinator }",
        "add_ideas = TFF_emergency_frontier_command",
    ):
        if token not in form:
            issues.append(f"wartime effect lacks {token}")
    if "clr_country_flag = TFF_wartime_confederation_formed" in effects:
        issues.append("historical confederation flag must not be cleared")
    if form.find("TFF_wartime_confederation_formed") == form.find("TFF_wartime_command_active"):
        issues.append("historical and current wartime flags must stay distinct")

    events = texts.get(EVENTS, "")
    if events.count("add_namespace = ADISCORD_TFF") != 1:
        issues.append("TFF event namespace declaration is missing or duplicated")
    try:
        empty_chair = event_block(events, "ADISCORD_TFF.1")
    except ValueError as exc:
        issues.append(str(exc))
        empty_chair = ""
    for token in (
        "fire_only_once = yes",
        "is_triggered_only = yes",
        "picture = GFX_event_adiscord_parliament_chamber",
        "hidden_effect = {",
        "ADISCORD_TFF_form_wartime_confederation = yes",
        "custom_effect_tooltip = ADISCORD_TFF_empty_chair_result_tt",
        "effect_tooltip = { add_ideas = TFF_emergency_frontier_command }",
    ):
        if token not in empty_chair:
            issues.append(f"Empty Chair event lacks {token}")
    if re.search(r"(?m)^\s*option\s*=", empty_chair):
        option_start = empty_chair.find("option =")
        if "ADISCORD_TFF_form_wartime_confederation = yes" in empty_chair[option_start:]:
            issues.append("transformation must not wait for the event option")

    ideas = texts.get(IDEAS, "")
    if "TFF_emergency_frontier_command =" not in ideas:
        issues.append("wartime national spirit is missing")

    decisions = texts.get(DECISIONS, "")
    categories = texts.get(CATEGORIES, "")
    try:
        category = named_block(categories, "TFF_frontier_at_war")
    except ValueError as exc:
        issues.append(str(exc))
        category = ""
    if "has_country_flag = TFF_wartime_command_active" not in category or "has_war_with = NOD" not in category:
        issues.append("wartime decision category must require active command and war with NOD")
    for decision_id in DECISION_IDS:
        try:
            decision = named_block(decisions, decision_id)
        except ValueError as exc:
            issues.append(str(exc))
            continue
        if "has_country_flag = TFF_wartime_command_active" not in decision:
            issues.append(f"{decision_id} must require TFF_wartime_command_active")
        if "has_war_with = NOD" not in decision:
            issues.append(f"{decision_id} must require war with NOD")
        if "ai_will_do" not in decision:
            issues.append(f"{decision_id} must have an AI weight")
    try:
        forts = named_block(decisions, "TFF_fortify_the_nodrul_border")
        provinces = tuple(re.findall(r"province\s*=\s*(\d+)", forts))
        if provinces != BORDER_PROVINCES:
            issues.append(f"Nodrul border forts must be {BORDER_PROVINCES}, found {provinces}")
        if "controls_state = 83" not in forts:
            issues.append("border forts must stay in TFF state 83")
    except ValueError as exc:
        issues.append(str(exc))

    cosmetic = texts.get(COSMETIC, "")
    if "TFF_frontier_defense_confederation =" not in cosmetic:
        issues.append("cosmetic tag TFF_frontier_defense_confederation is missing")

    ideologies = texts.get(IDEOLOGIES, "")
    try:
        anarchism_types = named_block(named_block(ideologies, "anarchism"), "types")
    except ValueError as exc:
        issues.append(str(exc))
        anarchism_types = ""
    if not re.search(
        r"(?s)\btff_emergency_war_coordinator\s*=\s*\{.*?can_be_randomly_selected\s*=\s*no",
        anarchism_types,
    ):
        issues.append("tff_emergency_war_coordinator must be a non-random anarchism subtype")

    scripted_loc = texts.get(SCRIPTED_LOC, "")
    if "name = GetSubIdeologyAnarchism" not in scripted_loc:
        issues.append("GetSubIdeologyAnarchism scripted loc is missing")
    elif "has_country_leader_ideology = tff_emergency_war_coordinator" not in scripted_loc:
        issues.append("GetSubIdeologyAnarchism must display the emergency coordinator title")

    gfx = texts.get(PORTRAITS_GFX, "")
    if 'name = "GFX_portrait_TFF_Colt_Ardent"' not in gfx:
        issues.append("GFX_portrait_TFF_Colt_Ardent sprite is missing")
    if 'texturefile = "gfx/leaders/TFF/portrait_TFF_Colt_Ardent.png"' not in gfx:
        issues.append("Colt portrait sprite must point at portrait_TFF_Colt_Ardent.png")
    if (ROOT / "gfx/leaders/TFF/portrait.png").exists():
        issues.append("prepared Colt portrait must be renamed, not left as portrait.png")
    portrait = ROOT / PORTRAIT
    if not portrait.is_file():
        issues.append("portrait_TFF_Colt_Ardent.png is missing")
    else:
        data = portrait.read_bytes()
        if data[:8] != b"\x89PNG\r\n\x1a\n":
            issues.append("Colt portrait must remain a PNG")
        width, height = struct.unpack(">II", data[16:24])
        if (width, height) != (156, 210):
            issues.append(f"Colt portrait size must stay 156x210, found {width}x{height}")
    if not (ROOT / ABSENT_PORTRAIT).is_file():
        issues.append("Absent Government portrait must remain in place")

    tags = texts.get(COUNTRY_TAGS, "")
    if not re.search(r'(?m)^TFF\s*=\s*"countries/TheFreeFrontier.txt"\s*$', tags):
        issues.append("real country tag TFF must remain registered")
    extra_tags = []
    for path in (ROOT / "common/country_tags").glob("*.txt"):
        extra_tags.extend(re.findall(r'(?m)^(TFF_[A-Za-z0-9_]+)\s*=\s*"countries/', path.read_text(encoding="utf-8-sig")))
    if extra_tags:
        issues.append(f"must not create a new real country tag: {extra_tags}")

    tff_sources = "".join(
        texts.get(path, "")
        for path in (ON_ACTIONS, EFFECTS, EVENTS, DECISIONS, CATEGORIES, IDEAS)
    )
    for forbidden in ("start_civil_war", "create_dynamic_country", "transfer_state", "set_state_owner"):
        if forbidden in tff_sources:
            issues.append(f"TFF wartime files must not use {forbidden}")

    ru = texts.get(RU_LOC, "")
    en = texts.get(EN_LOC, "")
    for key in LOC_KEYS:
        if not loc_value(ru, key):
            issues.append(f"missing Russian loc {key}")
        if not loc_value(en, key):
            issues.append(f"missing English loc {key}")
    if loc_value(en, "TFF_frontier_defense_confederation") != "Frontier Defense Confederation":
        issues.append("English cosmetic name drifted")
    if loc_value(en, "TFF_frontier_defense_confederation_DEF") != "the Frontier Defense Confederation":
        issues.append("English cosmetic DEF drifted")
    if loc_value(en, "TFF_frontier_defense_confederation_ADJ") != "Frontier":
        issues.append("English cosmetic ADJ drifted")
    if loc_value(ru, "TFF_frontier_defense_confederation") != "Конфедерация обороны Фронтира":
        issues.append("Russian cosmetic name drifted")
    desc = loc_value(ru, "ADISCORD_TFF.1.d").replace("\\n", "\n")
    if len(desc) > 3000 or len(desc.encode("utf-8")) > 5500:
        issues.append("Empty Chair description exceeds the editorial event-page ceiling")
    if "\u2014" in desc or "\u2022" in desc:
        issues.append("Empty Chair description must not use em-dashes or bullets")
    if not loc_value(texts.get(RU_CHAR, ""), "TFF_Colt_Ardent"):
        issues.append("Russian character name for TFF_Colt_Ardent is missing")
    if not loc_value(texts.get(EN_CHAR, ""), "TFF_Colt_Ardent"):
        issues.append("English character name for TFF_Colt_Ardent is missing")
    if loc_value(texts.get(RU_PARTIES, ""), "tff_emergency_war_coordinator") != "Чрезвычайный военный координатор":
        issues.append("Russian coordinator title drifted")
    if loc_value(en, "tff_emergency_war_coordinator") != "Emergency War Coordinator":
        issues.append("English coordinator title drifted")

    return issues


def main() -> int:
    issues = collect_issues()
    if issues:
        for issue in issues:
            print(issue)
        return 1
    print("TFF wartime contract: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
