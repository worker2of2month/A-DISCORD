"""Focused static contract for the scripted NAM resource war."""

from __future__ import annotations

import re
import sys
import json
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[2]
ISSUES: list[str] = []


def read(relative: str) -> str:
    path = ROOT / relative
    if not path.exists():
        ISSUES.append(f"missing {relative}")
        return ""
    return path.read_text(encoding="utf-8-sig", errors="strict")


def check(condition: bool, message: str) -> None:
    if not condition:
        ISSUES.append(message)


def balanced_braces(source: str) -> bool:
    depth = 0
    in_quote = False
    escaped = False
    for raw_line in source.splitlines():
        line = raw_line.split("#", 1)[0]
        for char in line:
            if escaped:
                escaped = False
                continue
            if char == "\\" and in_quote:
                escaped = True
            elif char == '"':
                in_quote = not in_quote
            elif not in_quote and char == "{":
                depth += 1
            elif not in_quote and char == "}":
                depth -= 1
                if depth < 0:
                    return False
    return depth == 0 and not in_quote


def matching_brace(source: str, opening: int) -> int:
    depth = 0
    in_quote = False
    for index in range(opening, len(source)):
        char = source[index]
        if char == '"':
            in_quote = not in_quote
        elif not in_quote and char == "{":
            depth += 1
        elif not in_quote and char == "}":
            depth -= 1
            if depth == 0:
                return index
    return -1


def named_block(source: str, name: str) -> str:
    match = re.search(rf"(?m)^\s*{re.escape(name)}\s*=\s*\{{", source)
    if not match:
        return ""
    opening = source.find("{", match.start(), match.end())
    closing = matching_brace(source, opening)
    return source[match.start():closing + 1] if closing >= 0 else ""


def typed_blocks(source: str, block_type: str) -> list[str]:
    blocks: list[str] = []
    for match in re.finditer(rf"(?m)^\s*{re.escape(block_type)}\s*=\s*\{{", source):
        opening = source.find("{", match.start(), match.end())
        closing = matching_brace(source, opening)
        if closing >= 0:
            blocks.append(source[match.start():closing + 1])
    return blocks


def state_source(state_id: int) -> str:
    candidates = list((ROOT / "history" / "states").glob(f"{state_id}-*.txt"))
    if len(candidates) != 1:
        ISSUES.append(f"state {state_id}: expected one history file, found {len(candidates)}")
        return ""
    return candidates[0].read_text(encoding="utf-8-sig", errors="strict")


def owner_of_state(state_id: int) -> str | None:
    match = re.search(r"(?m)^\s*owner\s*=\s*([A-Z0-9]{3})", state_source(state_id))
    return match.group(1) if match else None


def main() -> int:
    files = (
        "common/country_tags/03_ADISCORD_nam_resource_war_tags.txt",
        "common/countries/SLF.txt",
        "common/countries/cosmetic.txt",
        "common/characters/ADISCORD_nam_resource_war_characters.txt",
        "common/ideas/ADISCORD_nam_resource_war_ideas.txt",
        "common/scripted_triggers/ADISCORD_nam_resource_war_triggers.txt",
        "common/scripted_effects/ADISCORD_nam_resource_war_effects.txt",
        "common/on_actions/03_ADISCORD_nam_resource_war_on_actions.txt",
        "common/decisions/categories/ADISCORD_scenario_debug_categories.txt",
        "common/decisions/ADISCORD_scenario_debug_decisions.txt",
        "common/decisions/categories/ADISCORD_nam_resource_war_categories.txt",
        "common/decisions/ADISCORD_nam_resource_war_decisions.txt",
        "common/ai_strategy/ADISCORD_nam_resource_war_ai.txt",
        "events/ADISCORD_nam_resource_war_events.txt",
        "history/countries/SLF - Svetlogorsk Uprising.txt",
        "history/units/NAM_resource_war.txt",
        "history/units/EFL_nam_resource_war.txt",
        "history/units/AZH_nam_resource_war.txt",
        "history/units/SLF_nam_resource_war.txt",
        "common/units/ADISCORD_naval_units.txt",
        "common/units/equipment/ADISCORD_convoy_equipment.txt",
        "common/script_enums.txt",
        "history/units/NAM.txt",
        "history/units/EFL.txt",
        "history/units/AZH.txt",
        "history/countries/NAM - NamestnikLand.txt",
        "history/countries/EFL - Eflor.txt",
        "history/countries/AZH - Azhar Black Basin.txt",
        "common/ideas/ADISCORD_nam_resource_war_ideas.txt",
        "docs/lore/countries.md",
    )
    sources = {relative: read(relative) for relative in files}
    for relative, source in sources.items():
        check(balanced_braces(source), f"{relative}: unbalanced braces or quote")

    for relative in (
        "history/units/NAM_resource_war.txt",
        "history/units/EFL_nam_resource_war.txt",
        "history/units/AZH_nam_resource_war.txt",
        "history/units/SLF_nam_resource_war.txt",
    ):
        source = sources[relative]
        defined_templates = set(re.findall(
            r'division_template\s*=\s*\{\s*name\s*=\s*"([^"]+)"',
            source,
            re.DOTALL,
        ))
        referenced_templates = set(re.findall(
            r'division_template\s*=\s*"([^"]+)"',
            source,
        ))
        check(
            referenced_templates <= defined_templates,
            f"{relative}: dynamically loaded OOB references templates it does not define: "
            f"{sorted(referenced_templates - defined_templates)}",
        )
        check(
            re.search(r'(?m)^\s*(?:name|division_template)\s*=\s*[^"\s{}]+\s+[^#{}]+$', source) is None,
            f"{relative}: unquoted multiword template or division name",
        )

    effects = sources["common/scripted_effects/ADISCORD_nam_resource_war_effects.txt"]
    triggers = sources["common/scripted_triggers/ADISCORD_nam_resource_war_triggers.txt"]
    ai = sources["common/ai_strategy/ADISCORD_nam_resource_war_ai.txt"]
    on_actions = sources["common/on_actions/03_ADISCORD_nam_resource_war_on_actions.txt"]
    debug_categories = sources["common/decisions/categories/ADISCORD_scenario_debug_categories.txt"]
    debug_decisions = sources["common/decisions/ADISCORD_scenario_debug_decisions.txt"]
    prewar_categories = sources["common/decisions/categories/ADISCORD_nam_resource_war_categories.txt"]
    prewar_decisions = sources["common/decisions/ADISCORD_nam_resource_war_decisions.txt"]
    news = sources["events/ADISCORD_nam_resource_war_events.txt"]
    ideas = sources["common/ideas/ADISCORD_nam_resource_war_ideas.txt"]
    equipment_source = sources["common/units/equipment/ADISCORD_convoy_equipment.txt"]
    naval_units = sources["common/units/ADISCORD_naval_units.txt"]
    script_enums = sources["common/script_enums.txt"]
    slf_oob = sources["history/units/SLF_nam_resource_war.txt"]

    check('SLF = "countries/SLF.txt"' in sources[files[0]], "SLF tag is not registered")
    check(not (ROOT / "history" / "countries" / "SLF - Svetlogorsk Liberation Front.txt").exists()
          and not (ROOT / "history" / "countries" / "SLF - Svetlogorsk Republic.txt").exists(),
          "obsolete SLF Liberation Front/Republic country-history filename remains")
    check(re.search(r"(?m)^\s*capital\s*=\s*688\s*$", sources[
        "history/countries/SLF - Svetlogorsk Uprising.txt"
    ]) is not None, "SLF history capital must be compact internal uprising state 688")
    check(not (ROOT / "events" / "ADISCORD_nam_resource_war_news.txt").exists(),
          "NAM news must be merged into the main resource-war event file")
    check(not (ROOT / "common" / "scripted_effects" / "ADISCORD_nam_resource_war_debug_effects.txt").exists(),
          "NAM debug entry points must be merged into the main resource-war effect file")
    check(all(effect in effects for effect in (
        "ADISCORD_nam_debug_start_resource_war",
        "ADISCORD_nam_debug_resolve_coalition_victory",
        "ADISCORD_nam_debug_resolve_nam_victory",
    )), "merged NAM effects are missing compact debug entry points")
    check("ADISCORD_nam_resource_war_prepare_independence" not in effects,
          "one-shot NAM independence wrapper must be inlined into resource-war start")
    check(
        "NAM = {\n\t\tif = {\n\t\t\tlimit = { is_subject = yes }\n\t\t\toverlord = { set_autonomy = { target = NAM autonomy_state = autonomy_free } }\n\t\t}\n\t\tif = { limit = { is_in_faction = yes } leave_faction = yes }\n\t}" in effects,
        "resource-war start does not free NAM from an arbitrary overlord before leaving its faction",
    )
    nam_readiness = named_block(named_block(triggers, "ADISCORD_nam_resource_war_ready"), "NAM")
    check("has_war = no" in nam_readiness and "is_subject = no" not in nam_readiness,
          "resource-war scheduling still blocks before the start effect can free a subject NAM")
    readiness = named_block(triggers, "ADISCORD_nam_resource_war_ready")
    for state_id in (67, 688, 689, 690):
        check(f"controls_state = {state_id}" in readiness,
              f"resource-war readiness must require NAM control of state {state_id}")
    efl_readiness = named_block(readiness, "EFL")
    azh_readiness = named_block(readiness, "AZH")
    check(all(f"controls_state = {state_id}" in efl_readiness for state_id in (68, 70, 691)),
          "resource-war readiness must require EFL control of all three mainland states")
    check(all(f"controls_state = {state_id}" in azh_readiness for state_id in (69, 692)),
          "resource-war readiness must require AZH control of both mainland states")
    start = named_block(effects, "ADISCORD_nam_resource_war_start")
    faction_creation = re.compile(
        r"create_faction_from_template\s*=\s*\{\s*"
        r"template\s*=\s*faction_template_ADISCORD_standard\s+"
        r"name\s*=\s*faction_eflor_azhar_restitution_alliance\s*\}",
        re.DOTALL,
    )
    check(faction_creation.search(start) is not None,
          "resource-war start does not create the permanent EFL-AZH faction")
    check(start.count("add_to_faction = AZH") == 1,
          "EFL must add AZH to the resource-war faction exactly once")
    check(start.count("leave_faction = yes") == 3,
          "NAM, EFL, and AZH must clear obsolete faction ties before the new faction is formed")

    efl_declaration = "EFL = { declare_war_on = { target = NAM type = annex_everything } }"
    azh_join_pattern = re.compile(
        r"AZH\s*=\s*\{\s*add_to_war\s*=\s*\{\s*"
        r"targeted_alliance\s*=\s*EFL\s+enemy\s*=\s*NAM\s+"
        r"hostility_reason\s*=\s*asked_to_join\s+single_target_only\s*=\s*yes\s*\}\s*\}",
        re.DOTALL,
    )
    check(efl_declaration in start, "EFL does not declare the NAM annexation war")
    check(azh_join_pattern.search(start) is not None,
          "AZH does not join EFL's existing war against NAM")
    check("AZH = { declare_war_on = { target = NAM" not in start,
          "AZH still creates an independent second war against NAM")

    create_position = start.find("create_faction_from_template")
    declare_position = start.find(efl_declaration)
    join_position = start.find("add_to_war")
    check(-1 not in (create_position, declare_position, join_position)
          and create_position < declare_position < join_position,
          "faction creation, EFL declaration, and AZH war entry are in the wrong order")
    check("transfer_state = 68" in effects and "69 = { add_claim_by = NAM }" in effects,
          "NAM victory is missing its limited border compensation")
    check(
        "228 = { add_core_of = NAM" not in effects
        and "231 = { add_core_of = NAM" not in effects,
        "NAM victory must not turn its island colonies back into NAM cores",
    )
    check(all(f"transfer_state = {state}" in effects for state in range(225, 232)),
          "coalition treaty does not account for every NAM island state")
    check("days = 420" in effects and "days = 720" not in effects and "timeout_resolution" in effects,
          "war needs the 420-day deterministic anti-stalemate deadline")
    for equipment_id, amount, producer in (
        ("infantry_equipment", 6000, "NAM"),
        ("infantry_equipment", 3000, "EFL"),
        ("infantry_equipment", 1800, "AZH"),
        ("infantry_equipment", 1800, "SLF"),
        ("ADISCORD_squad_weapons_equipment_0", 80, "NAM"),
        ("ADISCORD_squad_weapons_equipment_0", 100, "EFL"),
        ("ADISCORD_squad_weapons_equipment_0", 20, "SLF"),
    ):
        check(
            f"type = {equipment_id} amount = {amount} producer = {producer}" in effects,
            f"incorrect resource-war stockpile for {producer}: expected {amount} {equipment_id}",
        )
    check(ai.count("manual_attack = yes") == 3 and ai.count("priority = 1500") >= 6,
          "coalition attack or NAM three-front defence AI is incomplete")
    for strategy_suffix, tag, ratio in (
        ("eflor", "EFL", "0.40"),
        ("azhar", "AZH", "0.35"),
        ("rebel", "SLF", "0.25"),
    ):
        strategy_name = f"ADISCORD_nam_resource_war_nam_{strategy_suffix}_front"
        strategy = named_block(ai, strategy_name)
        check(
            f"tag = {tag} ratio = {ratio}" in strategy
            and "execution_type = careful" in strategy
            and "manual_attack = no" in strategy,
            f"{strategy_name} is not a cautious NAM defence allocation",
        )
    check("country_event = { id = ADISCORD_nam_resource_war.2 days = 45 random_days = 30 }" in effects,
          "Svetlogorsk uprising does not leave NAM the intended 45-75 day response window")

    prewar_category = named_block(prewar_categories, "ADISCORD_nam_prewar_defence_category")
    check("tag = NAM" in prewar_category
          and "ADISCORD_vorkerland_collapse_wars_started" in prewar_category
          and "ADISCORD_nam_resource_war_started" in prewar_category,
          "NAM prewar-defence category is not scoped to the warning window")
    expected_forts = {
        "ADISCORD_nam_fortify_extraction_line": {1015: 1, 4912: 1, 8058: 2},
        "ADISCORD_nam_fortify_azhar_approaches": {461: 1, 6961: 1, 2299: 2},
    }
    for decision_name, forts in expected_forts.items():
        decision = named_block(prewar_decisions, decision_name)
        check("cost = 20" in decision and "days_remove = 35" in decision
              and "fire_only_once = yes" in decision and "base = 1000" in decision,
              f"{decision_name} lacks the bounded player/AI preparation contract")
        actual = {
            int(province): int(level)
            for level, province in re.findall(
                r"add_building_construction\s*=\s*\{\s*type\s*=\s*bunker\s+level\s*=\s*(\d+)\s+"
                r"instant_build\s*=\s*yes\s+province\s*=\s*(\d+)\s*\}",
                decision,
            )
        }
        check(actual == forts, f"{decision_name} fort line drifted: {actual}")
    check("tag = RHM" in ai and "id = EFL" in ai and "tag = MZR" in ai and "id = AZH" in ai,
          "the two profitable volunteer routes are incomplete")
    check("tag = KDR" not in ai and "tag = SDR" not in ai,
          "non-beneficiary southern states were incorrectly mobilised")
    check("skip_default_capitulation" in on_actions and on_actions.count("on_capitulation") == 1,
          "bespoke capitulation routing is incomplete")
    check(news.count("news_event = {") == 3,
          "world news must contain exactly war start and two mutually exclusive outcomes")

    news_blocks = typed_blocks(news, "news_event")
    for event_id in (
        "ADISCORD_nam_resource_news.1",
        "ADISCORD_nam_resource_news.2",
        "ADISCORD_nam_resource_news.3",
    ):
        definitions = [block for block in news_blocks if re.search(
            rf"(?m)^\s*id\s*=\s*{re.escape(event_id)}\s*$", block
        )]
        check(len(definitions) == 1, f"{event_id} must have exactly one definition")
        if definitions:
            check("is_triggered_only = yes" in definitions[0]
                  and "fire_only_once = yes" in definitions[0]
                  and "major = yes" in definitions[0]
                  and "hidden = yes" not in definitions[0],
                  f"{event_id} must be visible major, triggered-only and single-shot")

    all_script_sources = {
        path.relative_to(ROOT).as_posix(): path.read_text(encoding="utf-8-sig", errors="strict")
        for root_name in ("common", "events", "history")
        for path in (ROOT / root_name).rglob("*.txt")
    }
    expected_news_calls = {
        "ADISCORD_nam_resource_news.1": "ADISCORD_nam_resource_war_start",
        "ADISCORD_nam_resource_news.2": "ADISCORD_nam_resource_war_resolve_coalition_victory",
        "ADISCORD_nam_resource_news.3": "ADISCORD_nam_resource_war_resolve_nam_victory",
    }
    for event_id, effect_name in expected_news_calls.items():
        call_pattern = re.compile(
            rf"news_event\s*=\s*\{{\s*id\s*=\s*{re.escape(event_id)}(?:\s|\}})",
            re.DOTALL,
        )
        definition_sites = [
            relative
            for relative, source in all_script_sources.items()
            if relative.startswith("events/")
            and any(re.search(rf"(?m)^\s*id\s*=\s*{re.escape(event_id)}\s*$", block)
                    for block in typed_blocks(source, "news_event"))
        ]
        check(definition_sites == ["events/ADISCORD_nam_resource_war_events.txt"],
              f"{event_id} has missing or duplicate definitions: {definition_sites}")
        call_sites = [
            relative
            for relative, source in all_script_sources.items()
            if not relative.startswith("events/") and call_pattern.search(source)
        ]
        check(call_sites == ["common/scripted_effects/ADISCORD_nam_resource_war_effects.txt"],
              f"{event_id} has missing or duplicate/delayed call sites: {call_sites}")
        effect_block = named_block(effects, effect_name)
        check(call_pattern.search(effect_block) is not None,
              f"{event_id} is not called by its production outcome {effect_name}")
    for effect_name in (
        "ADISCORD_nam_resource_war_resolve_coalition_victory",
        "ADISCORD_nam_resource_war_resolve_nam_victory",
    ):
        outcome = named_block(effects, effect_name)
        check("ADISCORD_nam_resource_war_active = yes" in outcome
              and "set_global_flag = ADISCORD_nam_resource_war_resolved" in outcome,
              f"{effect_name} lacks the active-war/single-resolution guard")
    check("ADISCORD_nam_resource_war_start = yes" in named_block(
        effects, "ADISCORD_nam_debug_start_resource_war"
    ), "debug start does not smoke the production opening-news path")
    check("ADISCORD_nam_resource_war_resolve_coalition_victory = yes" in named_block(
        effects, "ADISCORD_nam_debug_resolve_coalition_victory"
    ), "debug coalition action does not smoke its production outcome-news path")
    check("ADISCORD_nam_resource_war_resolve_nam_victory = yes" in named_block(
        effects, "ADISCORD_nam_debug_resolve_nam_victory"
    ), "debug NAM action does not smoke its production outcome-news path")
    scenario_debug_category = named_block(
        debug_categories, "ADISCORD_scenario_debug_category"
    )
    shared_debug_tags = set(re.findall(
        r"\btag\s*=\s*([A-Z0-9]{3})\b",
        named_block(scenario_debug_category, "allowed"),
    ))
    check(shared_debug_tags == {"WRK", "WKR", "VAD", "TVA", "IVN", "NAM", "EFL", "AZH", "SLF"},
          f"shared scenario debug category has wrong allowed tags: {sorted(shared_debug_tags)}")
    for decision_name in (
        "ADISCORD_nam_debug_start_resource_war",
        "ADISCORD_nam_debug_resolve_coalition_victory",
        "ADISCORD_nam_debug_resolve_nam_victory",
    ):
        decision = named_block(debug_decisions, decision_name)
        decision_tags = set(re.findall(
            r"\btag\s*=\s*([A-Z0-9]{3})\b",
            named_block(decision, "allowed"),
        ))
        check(decision_tags == {"NAM", "EFL", "AZH", "SLF"},
              f"NAM debug decision {decision_name} has wrong allowed tags: {sorted(decision_tags)}")
    obsolete_uprising_tokens = (
        "ADISCORD_nam_resource_war_resolve_uprising_victory",
        "ADISCORD_nam_debug_resolve_uprising_victory",
        "ADISCORD_nam_resource_news.4",
        "set_cosmetic_tag = SLF_svetlogorsk_republic",
        "SLF_svetlogorsk_republic_proclaimed",
    )
    terminal_sources = "\n".join((effects, on_actions, debug_decisions, news))
    for token in obsolete_uprising_tokens:
        check(token not in terminal_sources,
              f"obsolete surviving-SLF route remains: {token}")

    capitulation = named_block(on_actions, "on_capitulation")
    coalition_route = re.search(
        r"ROOT\s*=\s*\{\s*tag\s*=\s*NAM\s*\}.*?"
        r"FROM\s*=\s*\{\s*OR\s*=\s*\{([^}]*)\}.*?"
        r"ADISCORD_nam_resource_war_resolve_coalition_victory\s*=\s*yes",
        capitulation,
        re.DOTALL,
    )
    check(coalition_route is not None
          and all(f"tag = {tag}" in coalition_route.group(1) for tag in ("EFL", "AZH", "SLF")),
          "NAM defeat by EFL, AZH, or SLF must use the coalition settlement")

    coalition_victory = named_block(
        effects, "ADISCORD_nam_resource_war_resolve_coalition_victory"
    )
    efl_settlement = named_block(coalition_victory, "EFL")
    coalition_allocations = {
        "EFL": {"67", "225", "228", "230", "231", "688"},
        "AZH": {"226", "227", "229", "689", "690"},
    }
    for recipient, expected_states in coalition_allocations.items():
        recipient_settlement = named_block(coalition_victory, recipient)
        recipient_states = set(re.findall(r"transfer_state\s*=\s*(\d+)", recipient_settlement))
        check(recipient_states == expected_states,
              f"{recipient} coalition allocation is wrong: {sorted(recipient_states)}")
        for state_id in expected_states:
            state_block = named_block(coalition_victory, state_id)
            check(re.search(rf"\badd_core_of\s*=\s*{recipient}\b", state_block) is not None,
                  f"coalition allocation state {state_id} does not add an {recipient} core")
            check(re.search(rf"\bset_state_controller_to\s*=\s*{recipient}\b", state_block) is not None,
                  f"coalition allocation state {state_id} is not controlled by {recipient}")
    check("annex_country = { target = SLF transfer_troops = no }" in efl_settlement,
          "EFL does not eliminate the temporary SLF uprising")
    check("annex_country = { target = NAM transfer_troops = no }" in coalition_victory,
          "coalition settlement lacks the NAM residual-state safety annexation")
    check("688 = { remove_core_of = SLF remove_core_of = NAM add_core_of = EFL set_state_controller_to = EFL }"
          in coalition_victory, "state 688 cleanup is incomplete")
    check("689 = { remove_core_of = NAM add_core_of = AZH set_state_controller_to = AZH }"
          in coalition_victory, "state 689 cleanup is incomplete")
    check("690 = { remove_core_of = NAM add_core_of = AZH set_state_controller_to = AZH }"
          in coalition_victory, "state 690 cleanup is incomplete")

    nam_victory = named_block(effects, "ADISCORD_nam_resource_war_resolve_nam_victory")
    check("annex_country = { target = SLF transfer_troops = no }" in nam_victory,
          "NAM victory does not eliminate a surviving SLF uprising")
    check("transfer_state = 688" in nam_victory
          and "688 = { remove_core_of = SLF add_core_of = NAM set_state_controller_to = NAM }" in nam_victory,
          "NAM victory does not restore state 688 and remove its temporary SLF core")

    for outcome in (coalition_victory, nam_victory):
        check(all(token not in outcome for token in (
            "leave_faction = yes", "remove_from_faction", "dismantle_faction"
        )), "NAM resolution must not dismantle the permanent EFL-AZH faction")

    mainland_rebellion = named_block(effects, "ADISCORD_nam_resource_war_start_mainland_rebellion")
    for token in (
        "transfer_state = 688",
        "set_capital = { state = 688 }",
        "688 = { add_core_of = SLF",
        "declare_war_on = { target = NAM",
    ):
        check(token in mainland_rebellion, f"mainland Svetlogorsk rebellion is missing {token}")
    slf_spawn_scope = named_block(mainland_rebellion, "SLF")
    check("transfer_state = 688" in slf_spawn_scope,
          "compact state 688 must be transferred inside the SLF recipient scope")
    check("transfer_state = 70" not in mainland_rebellion
          and "set_capital = { state = 70 }" not in mainland_rebellion
          and "70 = { add_core_of = SLF" not in effects,
          "SLF must not receive, core, or use EFL state 70 as its capital")
    check("ADISCORD_nam_resource_war_start_island_rebellion" not in effects,
          "obsolete island-rebellion effect still exists")
    check("transfer_state = 67" not in named_block(effects, "ADISCORD_nam_resource_war_start_mainland_rebellion"),
          "the rebellion must not remove NAM's only mainland core")
    slf_core_states = set(re.findall(
        r"(?m)^\s*(\d+)\s*=\s*\{[^\n{}]*add_core_of\s*=\s*SLF",
        mainland_rebellion,
    ))
    check(slf_core_states == {"688"},
          f"SLF must core only compact internal state 688, found {sorted(slf_core_states)}")
    defeat = named_block(effects, "ADISCORD_nam_resource_war_mark_rebels_defeated")
    check("NAM = { transfer_state = 688 }" in defeat
          and "688 = { remove_core_of = SLF set_state_controller_to = NAM }" in defeat,
          "defeated uprising must return state 688 and remove only its temporary SLF core")
    for state_id in range(225, 232):
        check(f"transfer_state = {state_id}" not in mainland_rebellion,
              f"the opening uprising still receives island state {state_id}")

    restitution_coalition = named_block(ideas, "ADISCORD_nam_restitution_coalition")
    check(
        "picture = generic_war_preparation" in restitution_coalition,
        "restitution coalition must use the registered generic_war_preparation picture",
    )

    public_sources = "\n".join((
        effects,
        news,
        ideas,
        slf_oob,
        sources["docs/lore/countries.md"],
    ))
    check("ADISCORD_nam_insurgent_columns = {" in ideas,
          "SLF insurgent-column national spirit is missing")
    check("ADISCORD_nam_republican_volunteer_columns" not in public_sources,
          "obsolete republican SLF spirit key remains")
    for obsolete in (
        "Союз свободных островов",
        "островные освободительные",
        "островного восстания",
        "Island Liberation Column",
        "Svetlogorsk Republican Corps",
        "Svetlogorsk Republic",
    ):
        check(obsolete.casefold() not in public_sources.casefold(),
              f"obsolete island-union concept remains in public content: {obsolete}")

    check("ADISCORD_coastal_patrol_ship = {" in equipment_source
          and "ADISCORD_coastal_patrol_ship_1 = {" in equipment_source,
          "coastal patrol ship archetype/equipment is missing")
    patrol_archetype = named_block(equipment_source, "ADISCORD_coastal_patrol_ship")
    patrol_variant = named_block(equipment_source, "ADISCORD_coastal_patrol_ship_1")
    check(re.search(r"(?m)^\s*type\s*=\s*screen_ship\s*$", patrol_archetype) is not None,
          "coastal patrol archetype must use the engine ship category screen_ship")
    check(re.search(r"(?m)^\s*type\s*=\s*\{\s*screen_ship\s*\}\s*$", patrol_variant) is not None,
          "coastal patrol variant must use the engine ship category screen_ship")
    equipment_bonus_enum = named_block(script_enums, "script_enum_equipment_bonus_type")
    for equipment_id in ("ADISCORD_coastal_patrol_ship", "ADISCORD_coastal_patrol_ship_1"):
        check(re.search(rf"(?m)^\s*{equipment_id}\s*$", equipment_bonus_enum) is not None,
              f"{equipment_id} is missing from script_enum_equipment_bonus_type")
    patrol_subunit = named_block(naval_units, "ADISCORD_coastal_patrol_vessel")
    check("map_icon_category = ship" in patrol_subunit
          and "type = { screen_ship }" in patrol_subunit
          and "need = { ADISCORD_coastal_patrol_ship = 1 }" in patrol_subunit,
          "custom coastal patrol subunit is missing or does not consume its ship archetype")
    fleet_contracts = (
        ("NAM", "history/units/NAM.txt", 4, 30, 2038, 689, 1, 688),
        ("EFL", "history/units/EFL.txt", 3, 20, 6495, 70, 2, 70),
        ("AZH", "history/units/AZH.txt", 2, 15, 493, 692, 1, 692),
    )
    for tag, relative, ships, convoys, port, state_id, port_level, dockyard_state_id in fleet_contracts:
        oob = sources[relative]
        check(oob.count("fleet = {") == 1, f"{tag} must have exactly one coastal fleet")
        check(oob.count("definition = ADISCORD_coastal_patrol_vessel") == ships,
              f"{tag} coastal fleet must contain exactly {ships} patrol ships")
        check(f"naval_base = {port}" in oob and f"location = {port}" in oob,
              f"{tag} fleet is not based at verified coastal province {port}")
        check(f"type = convoy_1 amount = {convoys} producer = {tag}" in oob,
              f"{tag} must receive exactly {convoys} starting convoys")
        state = state_source(state_id)
        check(re.search(rf"(?ms)^\s*{port}\s*=\s*\{{.*?naval_base\s*=\s*{port_level}\b", state) is not None,
              f"state {state_id} lacks level-{port_level} naval base at province {port}")
        dockyard_state = state_source(dockyard_state_id)
        check(re.search(r"(?m)^\s*dockyard\s*=\s*1\s*$", dockyard_state) is not None,
              f"state {dockyard_state_id} lacks its single proportional dockyard")

    uprising_state = state_source(688)
    check(re.search(r"(?ms)^\s*689\s*=\s*\{.*?naval_base\s*=\s*2\b", uprising_state) is not None,
          "state 688 lacks the level-2 Svetlogorsk port at spawn province 689")
    check(slf_oob.count("location = 689") == 3,
          "all three SLF divisions must spawn at Svetlogorsk province 689")

    starting_armies = {
        "NAM": ("history/units/NAM.txt", [176, 6099, 8058], 3),
        "EFL": ("history/units/EFL.txt", [259, 8057, 6495, 6331], 4),
        "AZH": ("history/units/AZH.txt", [367, 493, 8234], 3),
    }
    for tag, (relative, expected_locations, expected_divisions) in starting_armies.items():
        units = named_block(sources[relative], "units")
        locations = [
            int(value)
            for value in re.findall(
                r"division\s*=\s*\{.*?\blocation\s*=\s*(\d+)", units, re.DOTALL
            )
        ]
        check(units.count("division = {") == expected_divisions,
              f"{tag} must begin with {expected_divisions} deliberately weak divisions")
        check(locations == expected_locations,
              f"{tag} starting divisions are not distributed across owned states: {locations}")

    fleet_oobs = {
        path.name
        for path in (ROOT / "history" / "units").glob("*.txt")
        if "fleet = {" in path.read_text(encoding="utf-8-sig", errors="strict")
    }
    check(fleet_oobs == {"NAM.txt", "EFL.txt", "AZH.txt"},
          f"starting fleets must exist only for NAM/EFL/AZH, found {sorted(fleet_oobs)}")
    technology_manifest = json.loads(
        read("tools/data/adiscord_starting_technology_profiles.json")
    )
    for tag, relative in (
        ("NAM", "history/countries/NAM - NamestnikLand.txt"),
        ("EFL", "history/countries/EFL - Eflor.txt"),
        ("AZH", "history/countries/AZH - Azhar Black Basin.txt"),
    ):
        history = sources[relative]
        check("set_technology = {" not in history,
              f"{tag} history duplicates the generated starting technology system")
        country_profile = technology_manifest["countries"].get(tag, {})
        check("naval" in country_profile.get("profiles", ()),
              f"{tag} generated starting profile lacks naval continuity")
        for technology in ("ADISCORD_tech_coastal_patrols", "ADISCORD_tech_convoy_routing"):
            check(technology in country_profile.get("technologies_2160", ()),
                  f"{tag} generated profile lacks proportional naval technology {technology}")

    check(owner_of_state(67) == "NAM", "state 67 is no longer the NAM resource basin")
    check(owner_of_state(688) == "NAM", "state 688 must begin as a NAM core before the internal uprising")
    check(owner_of_state(689) == "NAM", "state 689 must begin as NAM's residual port city")
    check(owner_of_state(690) == "NAM", "state 690 must begin as NAM's Dryriver district")
    check(re.search(r"(?m)^\s*capital\s*=\s*689\s*$", sources[
        "history/countries/NAM - NamestnikLand.txt"
    ]) is not None, "NAM history capital must be residual port state 689")
    check(owner_of_state(68) == "EFL" and owner_of_state(70) == "EFL" and owner_of_state(691) == "EFL",
          "EFL is not NAM's actual western neighbour")
    check(owner_of_state(69) == "AZH" and owner_of_state(692) == "AZH",
          "AZH is not NAM's actual eastern neighbour")
    expected_resources = {
        67: {"oil": 80, "chromium": 6},
        688: {"oil": 12, "chromium": 1},
        689: {"oil": 36, "chromium": 5},
        690: {"oil": 36, "chromium": 3},
    }
    for state_id, resources in expected_resources.items():
        state = state_source(state_id)
        for resource, amount in resources.items():
            check(re.search(rf"(?m)^\s*{resource}\s*=\s*{amount}\s*$", state) is not None,
                  f"state {state_id} must contain {amount} {resource}")
    check(sum(resources["oil"] for resources in expected_resources.values()) == 164
          and sum(resources["chromium"] for resources in expected_resources.values()) == 15,
          "NAM resource redistribution changed the theatre's total deposits")
    azh_resources = {69: {"oil": 2, "chromium": 1}, 692: {"oil": 1, "chromium": 1}}
    for state_id, resources in azh_resources.items():
        state = state_source(state_id)
        for resource, amount in resources.items():
            check(re.search(rf"(?m)^\s*{resource}\s*=\s*{amount}\s*$", state) is not None,
                  f"state {state_id} must contain {amount} {resource}")
    check(re.search(r"(?m)^\s*arms_factory\s*=\s*1\s*$", state_source(67)) is not None
          and re.search(r"(?m)^\s*arms_factory\s*=", state_source(688)) is None,
          "NAM military industry was not moved out of the uprising district")

    nam_war_oob = sources["history/units/NAM_resource_war.txt"]
    check([int(value) for value in re.findall(r"(?m)^\s*location\s*=\s*(\d+)\s*$", nam_war_oob)]
          == [4912, 8058, 6961, 2299, 4912, 6961],
          "NAM wartime divisions are not distributed across the western and eastern fronts")

    expected_victory_points = {
        67: {1710: 2, 6099: 3},
        68: {259: 5, 6150: 2},
        69: {367: 5, 8234: 2},
        70: {2986: 2, 6495: 4},
        688: {689: 3},
        689: {2038: 5},
        690: {8058: 2, 9016: 2},
        691: {8057: 3},
        692: {493: 3, 5039: 2},
    }
    for state_id, points in expected_victory_points.items():
        state = state_source(state_id)
        for province_id, value in points.items():
            check(
                re.search(rf"victory_points\s*=\s*\{{\s*{province_id}\s+{value}\s*\}}", state) is not None,
                f"state {state_id} lacks VP {province_id} with value {value}",
            )
    check(
        sum(expected_victory_points[67].values())
        + sum(expected_victory_points[688].values())
        + sum(expected_victory_points[689].values())
        + sum(expected_victory_points[690].values()) == 17,
        "NAM mainland VP total must be 17",
    )
    check(sum(sum(expected_victory_points[state].values()) for state in (68, 70, 691)) == 16,
          "EFL mainland VP total must be 16")
    check(sum(sum(expected_victory_points[state].values()) for state in (69, 692)) == 12,
          "AZH mainland VP total must be 12")

    localisation = ROOT / "localisation" / "russian" / "ADISCORD_nam_resource_war_l_russian.yml"
    raw_loc = localisation.read_bytes() if localisation.exists() else b""
    check(raw_loc.startswith(b"\xef\xbb\xbf"), "Russian localisation must retain UTF-8 BOM")
    loc = raw_loc.decode("utf-8-sig") if raw_loc else ""
    check('faction_eflor_azhar_restitution_alliance: "Эфлорско-ажарский союз"' in loc,
          "missing Russian localisation for the permanent EFL-AZH faction")
    check('SLF: "Светлогорское восстание"' in loc,
          "SLF public name must be Svetlogorsk Uprising")
    check('SLF_humanism: "Светлогорское восстание"' in loc,
          "SLF ideology name must remain an uprising before victory")
    check('SLF_humanism_party: "Временный штаб восстания"' in loc,
          "SLF party must be the Provisional Uprising Headquarters")
    for obsolete in ("Союз свободных островов", "островные освободительные", "островного восстания", "Республиканские добровольческие"):
        check(obsolete.casefold() not in loc.casefold(), f"obsolete island-union localisation remains: {obsolete}")
    for key in (
        "SLF_Yaroslav_Veter",
        "ADISCORD_coastal_patrol_vessel",
        "ADISCORD_coastal_patrol_ship",
        "ADISCORD_coastal_patrol_ship_1",
        "modifier_experience_gain_ADISCORD_coastal_patrol_vessel_training_factor",
        "modifier_experience_gain_ADISCORD_coastal_patrol_vessel_mission_factor",
        "modifier_experience_gain_ADISCORD_coastal_patrol_vessel_combat_factor",
        "ADISCORD_nam_resource_news.1.t",
        "ADISCORD_nam_resource_news.1.d",
        "ADISCORD_nam_resource_news.1.a",
        "ADISCORD_nam_resource_news.2.t",
        "ADISCORD_nam_resource_news.2.d",
        "ADISCORD_nam_resource_news.2.a",
        "ADISCORD_nam_resource_news.3.t",
        "ADISCORD_nam_resource_news.3.d",
        "ADISCORD_nam_resource_news.3.a",
        "ADISCORD_nam_debug_start_resource_war",
        "ADISCORD_nam_debug_resolve_coalition_victory",
        "ADISCORD_nam_debug_resolve_nam_victory",
        "ADISCORD_nam_prewar_defence_category",
        "ADISCORD_nam_prewar_defence_category_desc",
        "ADISCORD_nam_fortify_extraction_line",
        "ADISCORD_nam_fortify_extraction_line_desc",
        "ADISCORD_nam_fortify_azhar_approaches",
        "ADISCORD_nam_fortify_azhar_approaches_desc",
    ):
        check(re.search(rf"(?m)^\s*{re.escape(key)}:", loc) is not None,
              f"missing localisation key {key}")
    check("ADISCORD_nam_resource_news.4" not in loc,
          "obsolete uprising-victory news localisation remains")
    check("ADISCORD_nam_debug_resolve_uprising_victory" not in loc,
          "obsolete uprising-victory debug localisation remains")
    check(loc.count("§RDEBUG:§!") == 3,
          "all three debug entry points need the red DEBUG prefix")

    for relative, size in (
        ("gfx/flags/SLF.tga", (82, 52)),
        ("gfx/flags/medium/SLF.tga", (41, 26)),
        ("gfx/flags/small/SLF.tga", (10, 7)),
    ):
        path = ROOT / relative
        check(path.exists(), f"missing {relative}")
        if path.exists():
            with Image.open(path) as image:
                check(image.size == size, f"{relative}: expected {size}, got {image.size}")

    if ISSUES:
        print("NAM resource-war validation failed:")
        for issue in ISSUES:
            print(f"- {issue}")
        return 1
    print("NAM resource-war validation passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
