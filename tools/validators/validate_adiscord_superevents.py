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
SCRIPTED_LOC = Path("common/scripted_localisation/ADISCORD_scripted_loc_superevents.txt")
EN_LOC = Path("localisation/english/ADISCORD_superevents_l_english.yml")
RU_LOC = Path("localisation/russian/ADISCORD_superevents_l_russian.yml")
SOUNDS = Path("sound/superevents_sound.asset")
SOUND_EFFECTS = Path("sound/superevents_effects.asset")
SOUND_CATEGORY = Path("sound/superevents_category.asset")
REGISTRY = Path("tools/data/adiscord_event_ids.json")

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
)

SUPEREVENT_IDS = (
    "ADISCORD_superevent.1",
    "ADISCORD_superevent.2",
    "ADISCORD_superevent_audio.1",
    "ADISCORD_superevent_audio.2",
    "ADISCORD_superevent_news.1",
    "ADISCORD_superevent_news.2",
)


@dataclass(frozen=True)
class SupereventPresentation:
    name: str
    dedicated_sound_effect: str | None = None


PRESENTATIONS = (
    SupereventPresentation(
        "superevent_vorkerland_civilwar",
        "superevent_vorkerland_civilwar_sound_e",
    ),
    SupereventPresentation(
        "superevent_vorkerland_dirty_opening",
        "superevent_vorkerland_dirty_opening_sound_e",
    ),
    SupereventPresentation(
        "superevent_vorkerland_worker_victory",
        "superevent_vorkerland_worker_victory_sound_e",
    ),
    SupereventPresentation(
        "superevent_vorkerland_utilitarian_victory",
        "superevent_vorkerland_utilitarian_victory_sound_e",
    ),
    SupereventPresentation("superevent_vorkerland_vlad_victory"),
    SupereventPresentation("superevent_vorkerland_dorian_victory"),
    SupereventPresentation(
        "superevent_stelander_empire",
        "superevent_stelander_empire_sound_e",
    ),
)


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
            issues.append(f"events: expected one namespace declaration for {namespace}, found {count}")

    for event_id in SUPEREVENT_IDS:
        count = len(
            re.findall(
                rf"(?m)^\s*id\s*=\s*{re.escape(event_id)}\s*$",
                events,
            )
        )
        if count != 1:
            issues.append(f"events: expected one definition of {event_id}, found {count}")

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

    for item in PRESENTATIONS:
        name = item.name
        if scripted_names.count(name) != 1:
            issues.append(
                f"missing or duplicate scripted-GUI presentation {name}: "
                f"found {scripted_names.count(name)}"
            )
        if gui_names.count(name) != 1:
            issues.append(
                f"missing or duplicate GUI window {name}: found {gui_names.count(name)}"
            )
        if gfx_names.count(name) != 1:
            issues.append(
                f"missing or duplicate GFX sprite GFX_{name}: found {gfx_names.count(name)}"
            )
        expected_show_sound = (
            item.dedicated_sound_effect or "superevent_vorkerland_civilwar_sound_e"
        )
        window = ""
        for block in blocks(gui, r"^\s*containerWindowType\s*=\s*\{"):
            if re.search(rf'(?m)^\s*name\s*=\s*"{re.escape(name)}"\s*$', block):
                window = block
                break
        if f"show_sound = {expected_show_sound}" not in window:
            issues.append(f"GUI {name}: show_sound must be {expected_show_sound}")

        for suffix, getter in (
            ("title", "GetSupereventTitle"),
            ("quote", "GetSupereventQuote"),
            ("comment", "GetSupereventComment"),
        ):
            key = f"{name}_{suffix}"
            count = scripted_loc.count(f"localization_key = {key}")
            if count != 1:
                issues.append(
                    f"{getter}: expected one route to {key}, found {count}"
                )
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

    for suffix in ("title", "quote", "comment"):
        joint = f"superevent_vorkerland_joint_victory_{suffix}"
        count = scripted_loc.count(f"localization_key = {joint}")
        if count != 1:
            issues.append(f"joint-government variant must route once to {joint}, found {count}")
        for language, loc in (("English", english), ("Russian", russian)):
            loc_count = _localisation_count(loc, joint)
            if loc_count != 1:
                issues.append(
                    f"missing or duplicate {language} localisation key {joint}: "
                    f"found {loc_count}"
                )

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

    sound_items = tuple(item for item in PRESENTATIONS if item.dedicated_sound_effect)
    sound_effect_names = tuple(item.dedicated_sound_effect for item in sound_items)
    sound_names = tuple(effect.removesuffix("_e") for effect in sound_effect_names)

    for item, effect, sound in zip(sound_items, sound_effect_names, sound_names):
        effect_count = len(
            re.findall(rf"(?m)^\s*name\s*=\s*{re.escape(effect)}\s*$", sound_effects)
        )
        if effect_count != 1:
            issues.append(f"sound effect {effect}: expected one definition, found {effect_count}")
        sound_count = len(
            re.findall(rf'(?m)^\s*name\s*=\s*"{re.escape(sound)}"\s*$', sounds)
        )
        if sound_count != 1:
            issues.append(f"sound asset {sound}: expected one definition, found {sound_count}")
        category_count = len(re.findall(rf"(?m)^\s*{re.escape(effect)}\s*$", sound_category))
        if category_count != 1:
            issues.append(
                f"SuperEvents category: expected one reference to {effect}, found {category_count}"
            )

    _check_order("sound assets", sounds, sound_names, issues)
    _check_order("sound effects", sound_effects, sound_effect_names, issues)
    _check_order("sound category", sound_category, sound_effect_names, issues)

    if (root / RU_LOC).is_file() and not (root / RU_LOC).read_bytes().startswith(b"\xef\xbb\xbf"):
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

    if "ADISCORD_vorkerland_play_superevent_sound = yes" not in events:
        issues.append("events: presentation audio must use the shared unscoped helper")
    if "scoped_sound_effect" in events:
        issues.append("events: scoped_sound_effect silences observer/spectator")
    if re.search(r"every_country\s*=\s*\{[^{}]*limit\s*=\s*\{\s*is_ai\s*=\s*no", events, re.S):
        issues.append("events: human-only country dispatch silences observer/spectator")
    for getter in ("GetSupereventTitle", "GetSupereventQuote", "GetSupereventComment"):
        if f"superevent_inactive_{getter.removeprefix('GetSuperevent').lower()}" not in scripted_loc:
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
