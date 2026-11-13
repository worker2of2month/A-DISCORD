#!/usr/bin/env python3
"""Validate the shared A-DISCORD super-event presentation contract."""

from __future__ import annotations

from dataclasses import dataclass
import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

EVENTS = Path("events/ADISCORD_superevents.txt")
LEGACY_EVENTS = Path("events/ADISCORD_news.txt")
SCRIPTED_GUI = Path("common/scripted_guis/superevents.txt")
GUI = Path("interface/superevents.gui")
GFX = Path("interface/superevents.gfx")
SCRIPTED_LOC = Path(
    "common/scripted_localisation/ADISCORD_scripted_loc_superevents.txt"
)
EN_LOC = Path("localisation/english/ADISCORD_superevents_l_english.yml")
RU_LOC = Path("localisation/russian/ADISCORD_superevents_l_russian.yml")
SOUNDS = Path("sound/superevents_sound.asset")
SOUND_EFFECTS = Path("sound/superevents_effects.asset")
SOUND_CATEGORY = Path("sound/superevents_category.asset")
REGISTRY = Path("tools/data/adiscord_event_ids.json")
MUSIC = Path("music/ADISCORD_music.asset")
SPECIAL_SONGS = Path("music/ADISCORD_special_songs.txt")
PRESENTATION_SONGS = Path("music/ADISCORD_superevent_songs.txt")

REQUIRED_FILES = (
    EVENTS,
    SCRIPTED_GUI,
    GUI,
    GFX,
    SCRIPTED_LOC,
    EN_LOC,
    RU_LOC,
    SOUNDS,
    SOUND_EFFECTS,
    SOUND_CATEGORY,
    REGISTRY,
    MUSIC,
    Path("music/ADISCORD_songs.txt"),
    SPECIAL_SONGS,
    PRESENTATION_SONGS,
)

SUPEREVENT_IDS = (
    "ADISCORD_superevent.1",
    "ADISCORD_superevent.2",
    "ADISCORD_superevent.3",
    "ADISCORD_superevent.4",
    "ADISCORD_superevent.5",
    "ADISCORD_superevent.6",
    "ADISCORD_superevent.7",
    "ADISCORD_superevent.8",
    "ADISCORD_superevent.9",
    "ADISCORD_superevent.10",
    "ADISCORD_superevent.11",
    "ADISCORD_superevent.12",
    "ADISCORD_superevent.13",
    "ADISCORD_superevent.14",
    "ADISCORD_superevent.15",
    "ADISCORD_superevent.16",
    "ADISCORD_superevent.17",
    "ADISCORD_superevent.18",
    "ADISCORD_superevent.19",
    "ADISCORD_superevent.20",
    "ADISCORD_superevent.21",
    "ADISCORD_superevent.22",
    "ADISCORD_superevent.23",
    "ADISCORD_superevent.24",
    "ADISCORD_superevent.25",
    "ADISCORD_superevent_audio.1",
    "ADISCORD_superevent_audio.2",
    "ADISCORD_superevent_news.1",
    "ADISCORD_superevent_news.2",
)


@dataclass(frozen=True)
class SupereventPresentation:
    queue_id: int
    name: str
    dedicated_sound_effect: str | None = None


PRESENTATIONS = (
    SupereventPresentation(
        1,
        "superevent_vorkerland_civilwar",
        "superevent_vorkerland_civilwar_sound_e",
    ),
    SupereventPresentation(
        2,
        "superevent_vorkerland_dirty_opening",
        "superevent_vorkerland_dirty_opening_sound_e",
    ),
    SupereventPresentation(
        3,
        "superevent_vorkerland_worker_victory",
        "superevent_vorkerland_worker_victory_sound_e",
    ),
    SupereventPresentation(
        4,
        "superevent_vorkerland_utilitarian_victory",
        "superevent_vorkerland_utilitarian_victory_sound_e",
    ),
    SupereventPresentation(
        5,
        "superevent_vorkerland_vlad_victory",
        "superevent_vorkerland_vlad_victory_sound_e",
    ),
    SupereventPresentation(
        6,
        "superevent_vorkerland_dorian_victory",
        "superevent_vorkerland_dorian_victory_sound_e",
    ),
    SupereventPresentation(
        7,
        "superevent_stelander_empire",
        "superevent_stelander_empire_sound_e",
    ),
    SupereventPresentation(
        8,
        "superevent_stelander_party_victory",
        "superevent_stelander_party_victory_sound_e",
    ),
    SupereventPresentation(
        9,
        "superevent_stelander_shabrat_victory",
        "superevent_stelander_shabrat_victory_sound_e",
    ),
    SupereventPresentation(
        10,
        "superevent_nam_resource_war", "superevent_nam_resource_war_sound_e"
    ),
    SupereventPresentation(
        11,
        "superevent_rus_last_empire", "superevent_rus_last_empire_sound_e"
    ),
    SupereventPresentation(
        12,
        "superevent_val_commonwealth",
        "superevent_val_commonwealth_sound_e",
    ),
    SupereventPresentation(
        13,
        "superevent_stelander_great", "superevent_stelander_great_sound_e"
    ),
    SupereventPresentation(
        14,
        "superevent_rus_black_banner",
        "superevent_rus_last_empire_sound_e",
    ),
    SupereventPresentation(
        15,
        "superevent_rus_restoration",
        "superevent_rus_last_empire_sound_e",
    ),
    SupereventPresentation(
        16,
        "superevent_itora_vorkerland_war",
        "superevent_itora_vorkerland_war_sound_e",
    ),
    SupereventPresentation(
        17,
        "superevent_itora_civilwar",
        "superevent_itora_civilwar_sound_e",
    ),

    SupereventPresentation(
        18,
        "superevent_rus_khan_defeated",
        "superevent_rus_khan_defeated_sound_e",
    ),
    SupereventPresentation(
        19,
        "superevent_vorkerland_joint_victory",
        "superevent_vorkerland_joint_victory_sound_e",
    ),
    SupereventPresentation(
        20,
        "superevent_stelander_sotnikov_civilwar",
        "superevent_stelander_sotnikov_civilwar_sound_e",
    ),
    SupereventPresentation(
        21,
        "superevent_stelander_sotnikov_directory",
        "superevent_stelander_shabrat_victory_sound_e",
    ),
    SupereventPresentation(
        22,
        "superevent_stelander_sotnikov_charter",
        "superevent_stelander_shabrat_victory_sound_e",
    ),
    SupereventPresentation(
        23,
        "superevent_stelander_shabrat_republic",
        "superevent_stelander_shabrat_republic_sound_e",
    ),
    SupereventPresentation(
        24,
        "superevent_stelander_tikhoreva",
        "superevent_stelander_shabrat_victory_sound_e",
    ),
    SupereventPresentation(
        25,
        "superevent_rus_khan_died",
        "superevent_rus_khan_defeated_sound_e",
    ),
    SupereventPresentation(
        26,
        "superevent_nam_resource_war_service",
        "superevent_nam_resource_war_service_sound_e",
    ),
    SupereventPresentation(
        27,
        "superevent_nam_resource_war_district",
        "superevent_nam_resource_war_district_sound_e",
    ),
    SupereventPresentation(
        28,
        "superevent_stelander_party_victory_houses",
        "superevent_stelander_party_victory_houses_sound_e",
    ),
    SupereventPresentation(
        29,
        "superevent_stelander_party_victory_staff",
        "superevent_stelander_party_victory_staff_sound_e",
    ),
    SupereventPresentation(
        30,
        "superevent_stelander_party_victory_wallets",
        "superevent_stelander_party_victory_wallets_sound_e",
    ),
    SupereventPresentation(
        31,
        "superevent_stelander_party_victory_silence",
        "superevent_stelander_party_victory_silence_sound_e",
    ),
    SupereventPresentation(
        32,
        "superevent_stelander_party_victory_regent",
        "superevent_stelander_party_victory_regent_sound_e",
    ),
    SupereventPresentation(
        36,
        "superevent_stelander_party_victory_festival",
        "superevent_stelander_party_victory_sound_e",
    ),
    SupereventPresentation(
        37,
        "superevent_south_houses",
        "superevent_south_houses_sound_e",
    ),
    SupereventPresentation(
        38,
        "superevent_south_cities",
        "superevent_south_cities_sound_e",
    ),
    SupereventPresentation(
        39,
        "superevent_south_nur",
        "superevent_south_nur_sound_e",
    ),
    SupereventPresentation(
        40,
        "superevent_south_regency",
        "superevent_south_regency_sound_e",
    ),
    SupereventPresentation(
        41,
        "superevent_south_commune",
        "superevent_south_commune_sound_e",
    ),
    SupereventPresentation(
        42,
        "superevent_south_conclave",
        "superevent_south_conclave_sound_e",
    ),
    SupereventPresentation(
        43,
        "superevent_south_service",
        "superevent_south_service_sound_e",
    ),
    SupereventPresentation(
        44,
        "superevent_south_charter",
        "superevent_south_charter_sound_e",
    ),
    SupereventPresentation(
        45,
        "superevent_south_contracts",
        "superevent_south_contracts_sound_e",
    ),
    SupereventPresentation(
        46,
        "superevent_south_rump",
        "superevent_south_rump_sound_e",
    ),
    SupereventPresentation(
        47,
        "superevent_south_revenge",
        "superevent_south_revenge_sound_e",
    ),
    SupereventPresentation(
        48,
        "superevent_south_radical",
        "superevent_south_radical_sound_e",
    ),
    SupereventPresentation(
        49,
        "superevent_south_free_islands",
        "superevent_south_free_islands_sound_e",
    ),
    SupereventPresentation(
        50,
        "superevent_south_boards",
        "superevent_south_boards_sound_e",
    ),
    SupereventPresentation(
        51,
        "superevent_south_restitution",
        "superevent_south_restitution_sound_e",
    ),
    SupereventPresentation(
        52,
        "superevent_west_worker",
        "superevent_west_worker_sound_e",
    ),
    SupereventPresentation(
        53,
        "superevent_west_petrichev",
        "superevent_west_petrichev_sound_e",
    ),
    SupereventPresentation(
        54,
        "superevent_west_veyran",
        "superevent_west_veyran_sound_e",
    ),
    SupereventPresentation(
        55,
        "superevent_west_dorian",
        "superevent_west_dorian_sound_e",
    ),
    SupereventPresentation(
        56,
        "superevent_west_anton",
        "superevent_west_anton_sound_e",
    ),
    SupereventPresentation(
        57,
        "superevent_west_shield",
        "superevent_west_shield_sound_e",
    ),
    SupereventPresentation(
        58,
        "superevent_west_emergency",
        "superevent_west_emergency_sound_e",
    ),
    SupereventPresentation(
        59,
        "superevent_west_revanche",
        "superevent_west_revanche_sound_e",
    ),
    SupereventPresentation(
        60,
        "superevent_west_committee",
        "superevent_west_committee_sound_e",
    ),
    SupereventPresentation(
        61,
        "superevent_vorkerland_world_empire",
        "superevent_vorkerland_world_empire_sound_e",
    ),
    SupereventPresentation(
        62,
        "superevent_south_iron",
        "superevent_south_iron_sound_e",
    ),
    SupereventPresentation(
        63,
        "superevent_south_civil_service",
        "superevent_south_civil_service_sound_e",
    ),
    SupereventPresentation(
        64,
        "superevent_south_federation",
        "superevent_south_federation_sound_e",
    ),
    SupereventPresentation(
        65,
        "superevent_south_oil_union",
        "superevent_south_oil_union_sound_e",
    ),
    SupereventPresentation(
        66,
        "superevent_south_contract_republic",
        "superevent_south_contract_republic_sound_e",
    ),
    SupereventPresentation(
        67,
        "superevent_south_directorate",
        "superevent_south_directorate_sound_e",
    ),
    SupereventPresentation(
        68,
        "superevent_south_nam",
        "superevent_south_nam_sound_e",
    ),
    SupereventPresentation(
        69,
        "superevent_west_council",
        "superevent_west_council_sound_e",
    ),
    SupereventPresentation(
        70,
        "superevent_west_world_empire",
        "superevent_west_world_empire_sound_e",
    ),
    SupereventPresentation(
        71,
        "superevent_nam_veyran_proclamation",
        "superevent_nam_veyran_proclamation_sound_e",
    ),
    SupereventPresentation(
        72,
        "superevent_itora_legion_victory",
        "superevent_itora_legion_victory_sound_e",
    ),
    SupereventPresentation(
        73,
        "superevent_itora_committee_victory",
        "superevent_itora_committee_victory_sound_e",
    ),
    SupereventPresentation(
        74,
        "superevent_itora_stalk_portal",
        "superevent_itora_stalk_portal_sound_e",
    ),
)

PRESENTATIONS_BY_ID = {item.queue_id: item for item in PRESENTATIONS}


def read(root: Path, relative: Path, issues: list[str]) -> str:
    path = root / relative
    if not path.is_file():
        issues.append(f"missing required file {relative.as_posix()}")
        return ""
    try:
        return path.read_text(encoding="utf-8-sig")
    except UnicodeError as exc:
        issues.append(f"cannot decode {relative.as_posix()} as UTF-8: {exc}")
        return ""


def _braced_block(text: str, start: int) -> str:
    brace = text.find("{", start)
    if brace < 0:
        return ""
    depth = 0
    for index in range(brace, len(text)):
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    return ""


def blocks(text: str, pattern: str) -> list[str]:
    result: list[str] = []
    for match in re.finditer(pattern, text, re.MULTILINE):
        block = _braced_block(text, match.start())
        if block:
            result.append(block)
    return result


def _check_order(
    label: str,
    text: str,
    tokens: tuple[str, ...],
    issues: list[str],
) -> None:
    positions: list[int] = []
    for token in tokens:
        position = text.find(token)
        if position < 0:
            return
        positions.append(position)
    if positions != sorted(positions):
        issues.append(f"{label} does not follow canonical superevent order")


def _localisation_count(text: str, key: str) -> int:
    return len(re.findall(rf"(?m)^\s*{re.escape(key)}:\d*\s*\"", text))


def _event_block(text: str, event_id: str) -> str:
    for block in blocks(text, r"^\s*(?:country_event|news_event)\s*=\s*\{"):
        if re.search(rf"(?m)^\s*id\s*=\s*{re.escape(event_id)}\s*$", block):
            return block
    return ""


def collect_issues(root: Path = ROOT) -> list[str]:
    root = Path(root)
    issues: list[str] = []

    source = {relative: read(root, relative, issues) for relative in REQUIRED_FILES}
    if (root / LEGACY_EVENTS).exists():
        issues.append("legacy events/ADISCORD_news.txt must be removed")

    events = source.get(EVENTS, "")
    scripted_gui = source.get(SCRIPTED_GUI, "")
    gui = source.get(GUI, "")
    gfx = source.get(GFX, "")
    scripted_loc = source.get(SCRIPTED_LOC, "")
    english = source.get(EN_LOC, "")
    russian = source.get(RU_LOC, "")
    sounds = source.get(SOUNDS, "")
    sound_effects = source.get(SOUND_EFFECTS, "")
    sound_category = source.get(SOUND_CATEGORY, "")
    registry_source = source.get(REGISTRY, "")

    for namespace in (
        "ADISCORD_superevent",
        "ADISCORD_superevent_news",
        "ADISCORD_superevent_audio",
    ):
        count = len(
            re.findall(
                rf"(?m)^\s*add_namespace\s*=\s*{re.escape(namespace)}\s*$",
                events,
            )
        )
        if count != 1:
            issues.append(
                f"events: expected one namespace declaration for {namespace}, found {count}"
            )

    for event_id in SUPEREVENT_IDS:
        count = len(
            re.findall(
                rf"(?m)^\s*id\s*=\s*{re.escape(event_id)}\s*$",
                events,
            )
        )
        if count != 1:
            issues.append(
                f"events: expected one definition of {event_id}, found {count}"
            )

    expected_names = tuple(item.name for item in PRESENTATIONS)
    expected_set = set(expected_names)

    scripted_names = tuple(
        re.findall(r"(?m)^\s*(superevent_[a-z0-9_]+)\s*=\s*\{", scripted_gui)
    )
    gui_names: list[str] = []
    for block in blocks(gui, r"^\s*containerWindowType\s*=\s*\{"):
        match = re.search(r'(?m)^\s*name\s*=\s*"(superevent_[a-z0-9_]+)"\s*$', block)
        if match:
            gui_names.append(match.group(1))
    gfx_names: list[str] = []
    for block in blocks(gfx, r"^\s*spriteType\s*=\s*\{"):
        match = re.search(
            r'(?m)^\s*name\s*=\s*"GFX_(superevent_[a-z0-9_]+)"\s*$',
            block,
        )
        if match:
            gfx_names.append(match.group(1))
            texture = re.search(r'\btexturefile\s*=\s*"([^"]+)"', block, re.I)
            if not texture or not (root / texture.group(1)).is_file():
                path = texture.group(1) if texture else "(unspecified)"
                issues.append(f"GFX_{match.group(1)}: missing texture {path}")

    for item in PRESENTATIONS:
        name = item.name
        if scripted_names.count(name) != 1:
            issues.append(
                f"missing or duplicate scripted-GUI presentation {name}: "
                f"found {scripted_names.count(name)}"
            )
        bindings = blocks(scripted_gui, rf"^\s*{re.escape(name)}\s*=\s*\{{")
        if len(bindings) == 1:
            binding = bindings[0]
            if not re.search(rf'\bwindow_name\s*=\s*"{re.escape(name)}"', binding):
                issues.append(f"scripted GUI {name}: missing window binding")
            if not re.search(r"\bcontext_type\s*=\s*player_context\b", binding):
                issues.append(f"scripted GUI {name}: missing player context")
            visible = blocks(binding, r"^\s*visible\s*=\s*\{")
            if len(visible) != 1 or not re.search(
                rf"\bhas_global_flag\s*=\s*{re.escape(name)}\b", visible[0]
            ):
                issues.append(f"scripted GUI {name}: missing visibility flag")
            buttons = blocks(binding, r"^\s*superevents_button_click\s*=\s*\{")
            close = buttons[0] if len(buttons) == 1 else ""
            clear_flag = re.search(rf"\bclr_global_flag\s*=\s*{re.escape(name)}\b", close)
            dispatch = re.search(r"\bADISCORD_superevent_dispatch_next\s*=\s*yes\b", close)
            if not clear_flag or not dispatch or clear_flag.start() > dispatch.start():
                issues.append(f"scripted GUI {name}: close must clear its flag before dispatch")
        if gui_names.count(name) != 1:
            issues.append(
                f"missing or duplicate GUI window {name}: found {gui_names.count(name)}"
            )
        if gfx_names.count(name) != 1:
            issues.append(
                f"missing or duplicate GFX sprite GFX_{name}: found {gfx_names.count(name)}"
            )
        window = ""
        for block in blocks(gui, r"^\s*containerWindowType\s*=\s*\{"):
            if re.search(rf'(?m)^\s*name\s*=\s*"{re.escape(name)}"\s*$', block):
                window = block
                break
        show_sounds = re.findall(
            r"(?m)^\s*show_sound\s*=\s*([A-Za-z0-9_]+)\s*$",
            window,
        )
        if item.dedicated_sound_effect:
            if show_sounds != [item.dedicated_sound_effect]:
                issues.append(
                    f"GUI {name}: expected show_sound = "
                    f"{item.dedicated_sound_effect}, found {show_sounds}"
                )
        elif show_sounds:
            issues.append(f"GUI {name}: unexpected show_sound {show_sounds}")

        for suffix, getter in (
            ("title", "GetSupereventTitle"),
            ("quote", "GetSupereventQuote"),
            ("comment", "GetSupereventComment"),
        ):
            key = f"{name}_{suffix}"
            count = scripted_loc.count(f"localization_key = {key}")
            if count != 1:
                issues.append(f"{getter}: expected one route to {key}, found {count}")
            for language, loc in (("English", english), ("Russian", russian)):
                loc_count = _localisation_count(loc, key)
                if loc_count != 1:
                    issues.append(
                        f"missing or duplicate {language} localisation key {key}: "
                        f"found {loc_count}"
                    )

    for layer, actual in (
        ("scripted-GUI", set(scripted_names)),
        ("GUI", set(gui_names)),
        ("GFX", set(gfx_names)),
    ):
        for orphan in sorted(actual - expected_set):
            issues.append(f"orphan {layer} presentation {orphan}")

    _check_order(
        "scripted GUI",
        scripted_gui,
        tuple(f"{name} = {{" for name in expected_names),
        issues,
    )
    _check_order(
        "GUI",
        gui,
        tuple(f'name = "{name}"' for name in expected_names),
        issues,
    )
    _check_order(
        "GFX",
        gfx,
        tuple(f'name = "GFX_{name}"' for name in expected_names),
        issues,
    )
    for getter, suffix in (
        ("GetSupereventTitle", "title"),
        ("GetSupereventQuote", "quote"),
        ("GetSupereventComment", "comment"),
    ):
        getter_block = ""
        for block in blocks(scripted_loc, r"^\s*defined_text\s*=\s*\{"):
            if f"name = {getter}" in block:
                getter_block = block
                break
        if not getter_block:
            issues.append(f"missing scripted-localisation getter {getter}")
        else:
            _check_order(
                getter,
                getter_block,
                tuple(f"{name}_{suffix}" for name in expected_names),
                issues,
            )

    for language, loc in (("English", english), ("Russian", russian)):
        _check_order(
            f"{language} localisation",
            loc,
            tuple(f"{name}_title" for name in expected_names),
            issues,
        )

    # Several presentations may reuse the same registered sound.
    sound_effect_names = tuple(dict.fromkeys(
        item.dedicated_sound_effect for item in PRESENTATIONS if item.dedicated_sound_effect
    ))
    samples = {}
    for block in blocks(sounds, r"^\s*sound\s*=\s*\{"):
        name = re.search(r'\bname\s*=\s*"([^"]+)"', block)
        file = re.search(r'\bfile\s*=\s*"([^"]+)"', block)
        if not name or not file:
            issues.append("sound asset requires a sample name and file")
            continue
        if name[1] in samples:
            issues.append(f"duplicate sound sample {name[1]}")
        samples[name[1]] = file[1]
        if not (root / "sound" / file[1]).is_file():
            issues.append(f"{name[1]}: missing sound/{file[1]}")

    bindings = blocks(sound_effects, r"^\s*soundeffect\s*=\s*\{")
    for effect in sound_effect_names:
        matches = [block for block in bindings if re.search(
            rf"(?m)^\s*name\s*=\s*{re.escape(effect)}\s*$", block
        )]
        if len(matches) != 1:
            issues.append(f"sound effect {effect}: expected one definition, found {len(matches)}")
        else:
            referenced = re.findall(r"(?m)^\s*sound\s*=\s*(\w+)\s*$", matches[0])
            if len(referenced) != 1 or referenced[0] not in samples:
                issues.append(f"sound effect {effect}: expected one registered sample, found {referenced}")
        category_count = len(
            re.findall(rf"(?m)^\s*{re.escape(effect)}\s*$", sound_category)
        )
        if category_count != 1:
            issues.append(
                f"SuperEvents category: expected one reference to {effect}, found {category_count}"
            )

    _check_order("sound effects", sound_effects, sound_effect_names, issues)
    _check_order("sound category", sound_category, sound_effect_names, issues)

    # The radio database contains only the silent carriers for these windows.
    if re.search(r"(?m)^\s*music_station\s*=", source[PRESENTATION_SONGS]):
        issues.append("presentation audio guard file must not define a music station")
    if re.search(r"(?m)^\s*music\s*=", source[PRESENTATION_SONGS]):
        issues.append("presentation audio guard file must not register radio songs")

    # play_song resolves through the music database. Keep the silence carrier in
    # the real station with zero random chance so a super-event can reliably
    # interrupt whatever radio track is already playing without entering shuffle.
    for carrier in ("one_minute_of_silence", "two_minutes_of_silence"):
        silence_assets = [
            block
            for block in blocks(source[MUSIC], r"^\s*music\s*=\s*\{")
            if f'name = "{carrier}"' in block
        ]
        if (
            len(silence_assets) != 1
            or f'file = "{carrier}.ogg"' not in silence_assets[0]
        ):
            issues.append(f"{carrier}: must have exactly one music asset")

        silence_registrations = [
            block
            for block in blocks(source[SPECIAL_SONGS], r"^\s*music\s*=\s*\{")
            if f'song = "{carrier}"' in block
        ]
        if len(silence_registrations) != 1:
            issues.append(f"{carrier}: must be registered exactly once in {SPECIAL_SONGS.name}")
        elif not re.search(r"\bfactor\s*=\s*0(?:\.0+)?\b", silence_registrations[0]):
            issues.append(f"{carrier}: must have zero random-play chance")

    for effect in sound_effect_names:
        song = effect.removesuffix("_sound_e")
        assets = [
            block
            for block in blocks(source[MUSIC], r"^\s*music\s*=\s*\{")
            if f'name = "{song}"' in block
        ]
        for playlist in (root / "music").glob("*.txt"):
            if re.search(
                rf'(?m)^\s*song\s*=\s*"{re.escape(song)}"\s*$',
                playlist.read_text(encoding="utf-8-sig"),
            ):
                issues.append(
                    f"presentation music must not be registered in radio playlists: {song}"
                )
        if assets or (root / "music" / f"{song}.ogg").exists():
            issues.append(f"{song}: presentation audio belongs only in sound/")

    if (root / RU_LOC).is_file() and not (root / RU_LOC).read_bytes().startswith(
        b"\xef\xbb\xbf"
    ):
        issues.append("Russian superevent localisation must use UTF-8 BOM")

    empire = _event_block(events, "ADISCORD_superevent_news.2")
    for forbidden in (
        "transfer_state",
        "set_politics",
        "add_country_leader_role",
        "set_country_leader_portrait",
    ):
        if forbidden in empire:
            issues.append(
                f"Stelander Empire superevent must remain presentation-only: found {forbidden}"
            )

    try:
        registry = json.loads(registry_source) if registry_source else {}
    except json.JSONDecodeError as exc:
        issues.append(f"cannot parse {REGISTRY.as_posix()}: {exc}")
        registry = {}
    entries = {
        entry.get("id"): entry
        for entry in registry.get("events", [])
        if isinstance(entry, dict)
    }
    for event_id in SUPEREVENT_IDS:
        entry = entries.get(event_id)
        if entry is None:
            issues.append(f"event registry is missing {event_id}")
        elif entry.get("owner") != EVENTS.as_posix():
            issues.append(
                f"event registry owner for {event_id} must be {EVENTS.as_posix()}, "
                f"found {entry.get('owner')!r}"
            )

    if "ADISCORD_superevent_enqueue = yes" not in events:
        issues.append("events: presentation audio must use the shared unscoped helper")
    if "scoped_sound_effect" in events:
        issues.append("events: scoped_sound_effect silences observer/spectator")
    if re.search(
        r"every_country\s*=\s*\{[^{}]*limit\s*=\s*\{\s*is_ai\s*=\s*no", events, re.S
    ):
        issues.append("events: human-only country dispatch silences observer/spectator")
    for getter in ("GetSupereventTitle", "GetSupereventQuote", "GetSupereventComment"):
        if (
            f"superevent_inactive_{getter.removeprefix('GetSuperevent').lower()}"
            not in scripted_loc
        ):
            issues.append(f"{getter}: missing inactive fallback")
    for language, loc in (("English", english), ("Russian", russian)):
        for suffix in ("title", "quote", "comment"):
            if _localisation_count(loc, f"superevent_inactive_{suffix}") != 1:
                issues.append(
                    f"missing or duplicate {language} localisation key "
                    f"superevent_inactive_{suffix}"
                )

    return issues


def main() -> int:
    issues = collect_issues()
    if issues:
        print("Superevent contract validation failed:")
        for issue in issues:
            print(f"- {issue}")
        return 1
    print("Superevent contract: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
