#!/usr/bin/env python3
"""Read-only A-Discord total-conversion validator.

Checks common crash-prone HOI4 mod issues without modifying files.
Run from the mod root:
    python tools/validate_tc.py
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

_REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
if str(_REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPOSITORY_ROOT))

from tools.validators.validate_adiscord_economy_ai import validate as validate_adiscord_economy_ai
from tools.validators.validate_adiscord_event_ids import validate as validate_adiscord_event_ids
from tools.validators.validate_adiscord_strategic_resources_ui import validate as validate_adiscord_strategic_resources_ui
from tools.validators.validate_adiscord_trade_regions import validate as validate_adiscord_trade_regions
from tools.validators.validate_adiscord_vorkerland_civil_war_focus import (
    collect_issues as validate_adiscord_vorkerland_civil_war_focus,
)
from tools.validators.validate_adiscord_vorkerland_diplomacy import (
    collect_issues as validate_adiscord_vorkerland_diplomacy,
)
from tools.validators.validate_adiscord_vorkerland_focus_decisions import (
    collect_issues as validate_adiscord_vorkerland_focus_decisions,
)
from tools.validators.validate_adiscord_vorkerland_recovery import (
    collect_issues as validate_adiscord_vorkerland_recovery,
)
from tools.validators.validate_adiscord_vorkerland_story import (
    collect_issues as validate_adiscord_vorkerland_story,
)
from tools.validators.validate_adiscord_division_templates import validate as validate_adiscord_division_templates
from tools.builders.build_adiscord_map_buildings import validate as validate_adiscord_map_buildings
from tools.builders.build_adiscord_terrain_snow import validate as validate_adiscord_terrain_snow
from tools.lib.paths import repository_root


ROOT = repository_root()

GAME_DIRS = [
    "common",
    "history",
    "events",
    "interface",
    "map",
    "localisation",
    "gfx",
]

TEXT_EXTS = {".txt", ".gui", ".gfx", ".asset", ".yml", ".csv", ".map"}
BRACE_EXTS = {".txt", ".gui", ".gfx", ".asset", ".map"}

VANILLA_TAGS = {
    "AFG", "ALB", "ARG", "AST", "AUS", "BEL", "BOL", "BRA", "BUL", "CAN",
    "CHI", "CHL", "COL", "COS", "CRO", "CUB", "CZE", "DEN", "DOM", "ECU",
    "ELS", "ENG", "EST", "ETH", "FIN", "FRA", "GER", "GRE", "GUA", "HAI",
    "HOL", "HON", "HUN", "INS", "IRE", "IRQ", "ITA", "JAP", "LAT", "LIT",
    "LUX", "MAL", "MAN", "MEN", "MEX", "MON", "NEP", "NIC", "NOR", "NZL",
    "OMA", "PAN", "PAR", "PER", "PHI", "POL", "POR", "PRC", "RAJ", "ROM",
    "SAF", "SAU", "SIA", "SIK", "SLO", "SOV", "SPR", "SWE", "SWI", "TAN",
    "TIB", "TUR", "URG", "USA", "VEN", "VIN", "XSM", "YEM", "YUG", "CYP",
    "MLT", "ALG", "MOR", "TUN", "LBY", "WGR", "DDR", "ISR", "PAL", "JOR",
    "EGY", "SYR", "LEB", "KOR", "SER", "ICE",
}

VANILLA_IDEOLOGIES = {
    "democratic",
    "fascism",
    "communism",
    "neutrality",
    "conservatism",
    "liberalism",
    "socialism",
    "marxism",
    "leninism",
    "stalinism",
    "anti_revisionism",
    "anarchist_communism",
    "nazism",
    "fascism_ideology",
    "falangism",
    "rexism",
    "despotism",
    "oligarchism",
    "moderate",
    "centrism",
}


def read_text(path: Path) -> str:
    data = path.read_bytes()
    for enc in ("utf-8-sig", "utf-8", "cp1251", "latin-1"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def iter_files(*roots: str):
    for root in roots:
        base = ROOT / root
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if path.is_file() and path.suffix.lower() in TEXT_EXTS:
                yield path


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT)).replace("\\", "/")


def strip_comments(text: str) -> str:
    out = []
    for line in text.splitlines():
        in_quote = False
        escaped = False
        cut = len(line)
        for i, ch in enumerate(line):
            if ch == "\\" and in_quote and not escaped:
                escaped = True
                continue
            if ch == '"' and not escaped:
                in_quote = not in_quote
            if ch == "#" and not in_quote:
                cut = i
                break
            escaped = False
        out.append(line[:cut])
    return "\n".join(out)


def check_braces(limit: int):
    issues = []
    for path in iter_files("common", "history", "events", "interface", "map"):
        if path.suffix.lower() not in BRACE_EXTS:
            continue
        text = strip_comments(read_text(path))
        depth = 0
        for lineno, line in enumerate(text.splitlines(), 1):
            for ch in line:
                if ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth < 0:
                        issues.append(f"{rel(path)}:{lineno}: extra closing brace")
                        depth = 0
        if depth:
            issues.append(f"{rel(path)}: unbalanced braces, net +{depth}")
    return issues[:limit], len(issues)


def parse_country_tags():
    tags = {}
    dynamic_tags = set()
    tag_dir = ROOT / "common" / "country_tags"
    if not tag_dir.exists():
        return tags, dynamic_tags
    pattern = re.compile(r"^\s*([A-Z][A-Z0-9]{2,3})\s*=\s*\"([^\"]+)\"")
    for path in tag_dir.rglob("*.txt"):
        dynamic_mode = False
        for line in strip_comments(read_text(path)).splitlines():
            if re.match(r"^\s*dynamic_tags\s*=\s*yes\b", line):
                dynamic_mode = True
                continue
            match = pattern.match(line)
            if not match:
                continue
            tag, country_file = match.groups()
            tags[tag] = country_file.replace("\\", "/")
            if dynamic_mode:
                dynamic_tags.add(tag)
    return tags, dynamic_tags


def parse_ideologies():
    groups = set()
    types = set()
    ideol_dir = ROOT / "common" / "ideologies"
    for path in ideol_dir.rglob("*.txt") if ideol_dir.exists() else []:
        text = strip_comments(read_text(path))
        lines = text.splitlines()
        in_root = False
        group = None
        depth = 0
        in_types = False
        types_depth = 0
        for line in lines:
            if not in_root and re.search(r"\bideologies\s*=\s*\{", line):
                in_root = True
                depth += line.count("{") - line.count("}")
                continue
            if not in_root:
                continue
            start_depth = depth
            m = re.match(r"\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*\{", line)
            if start_depth == 1 and m:
                group = m.group(1)
                groups.add(group)
            elif group and start_depth == 2 and m and m.group(1) == "types":
                in_types = True
                types_depth = 2
            elif in_types and start_depth == 3 and m:
                types.add(m.group(1))
            depth += line.count("{") - line.count("}")
            if in_types and depth <= types_depth:
                in_types = False
            if depth <= 0:
                in_root = False
                group = None
    return groups, types


def parse_definition():
    provinces = {}
    path = ROOT / "map" / "definition.csv"
    if not path.exists():
        return provinces
    with path.open("r", encoding="utf-8-sig", errors="replace", newline="") as fh:
        reader = csv.reader(fh, delimiter=";")
        for row in reader:
            if len(row) < 5 or not row[0].isdigit():
                continue
            provinces[int(row[0])] = row[4].strip().lower()
    return provinces


def extract_block(text: str, start: int) -> str:
    open_at = text.find("{", start)
    if open_at < 0:
        return ""
    depth = 0
    for i in range(open_at, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return text[open_at + 1:i]
    return text[open_at + 1:]


def parse_states():
    states = []
    state_dir = ROOT / "history" / "states"
    if not state_dir.exists():
        return states
    for path in state_dir.rglob("*.txt"):
        text = strip_comments(read_text(path))
        sid = None
        m = re.search(r"\bid\s*=\s*(\d+)", text)
        if m:
            sid = int(m.group(1))
        provs = []
        pm = re.search(r"\bprovinces\s*=\s*\{", text)
        if pm:
            provs = [int(x) for x in re.findall(r"\d+", extract_block(text, pm.start()))]
        owners = re.findall(r"\bowner\s*=\s*([A-Z][A-Z0-9]{2,3})\b", text)
        cores = re.findall(r"\badd_core_of\s*=\s*([A-Z][A-Z0-9]{2,3})\b", text)
        category_match = re.search(r"\bstate_category\s*=\s*([A-Za-z_][A-Za-z0-9_]*)", text)
        category = category_match.group(1) if category_match else None
        manpower_match = re.search(r"\bmanpower\s*=\s*(-?\d+)", text)
        manpower = int(manpower_match.group(1)) if manpower_match else None
        vps = [int(x) for x in re.findall(r"\bvictory_points\s*=\s*\{\s*(\d+)\b", text)]
        building_provs = []
        bm = re.search(r"\bbuildings\s*=\s*\{", text)
        if bm:
            building_block = extract_block(text, bm.start())
            building_provs = [int(x) for x in re.findall(r"(?m)^\s*(\d+)\s*=\s*\{", building_block)]
        states.append(
            {
                "file": path,
                "id": sid,
                "provinces": provs,
                "owners": owners,
                "cores": cores,
                "category": category,
                "manpower": manpower,
                "vps": vps,
                "building_provs": building_provs,
            }
        )
    return states


def check_countries(tags, dynamic_tags, ideology_groups, ideology_types, limit):
    issues = []
    tag_to_history = {}
    hist_dir = ROOT / "history" / "countries"
    if hist_dir.exists():
        for path in hist_dir.rglob("*.txt"):
            m = re.match(r"([A-Z][A-Z0-9]{2,3})\b", path.name)
            if m:
                tag_to_history[m.group(1)] = path
    for tag in sorted(tags):
        if (
            tag not in dynamic_tags
            and tag not in tag_to_history
        ):
            issues.append(f"missing history/countries for tag {tag}")
    for tag, path in sorted(tag_to_history.items()):
        if tag not in tags:
            issues.append(f"{rel(path)}: history file tag {tag} is not in common/country_tags")
    for tag, country_file in sorted(tags.items()):
        cpath = ROOT / "common" / country_file
        if not cpath.exists():
            issues.append(f"common/country_tags: {tag} points to missing {country_file}")
    for tag, path in sorted(tag_to_history.items()):
        text = strip_comments(read_text(path))
        for party in re.findall(r"\bruling_party\s*=\s*([A-Za-z_][A-Za-z0-9_]*)", text):
            if party not in ideology_groups:
                issues.append(f"{rel(path)}: ruling_party {party} is not a mod ideology group")
        for block_start in [m.start() for m in re.finditer(r"\bset_popularities\s*=\s*\{|\bpopularities\s*=\s*\{", text)]:
            block = extract_block(text, block_start)
            for party in re.findall(r"\b([A-Za-z_][A-Za-z0-9_]*)\s*=", block):
                if party not in ideology_groups:
                    issues.append(f"{rel(path)}: popularity key {party} is not a mod ideology group")
        for leader_ideology in re.findall(r"\bideology\s*=\s*([A-Za-z_][A-Za-z0-9_]*)", text):
            if leader_ideology not in ideology_groups and leader_ideology not in ideology_types:
                issues.append(f"{rel(path)}: leader ideology {leader_ideology} is not defined")
    return issues[:limit], len(issues)


def check_states(tags, provinces, limit):
    issues = []
    states = parse_states()
    state_ids = defaultdict(list)
    province_to_states = defaultdict(list)
    for state in states:
        if state["id"] is None:
            issues.append(f"{rel(state['file'])}: missing state id")
        else:
            state_ids[state["id"]].append(state["file"])
        if state["category"] is None:
            issues.append(f"{rel(state['file'])}: missing state_category")
        if state["manpower"] is None:
            issues.append(f"{rel(state['file'])}: missing manpower")
        elif state["manpower"] < 1:
            issues.append(f"{rel(state['file'])}: manpower must be at least 1")
        state_provs = set(state["provinces"])
        for province in state["provinces"]:
            province_to_states[province].append(state)
            if province not in provinces:
                issues.append(f"{rel(state['file'])}: province {province} is not in map/definition.csv")
        for tag in state["owners"] + state["cores"]:
            if tag not in tags:
                issues.append(f"{rel(state['file'])}: owner/core tag {tag} is not defined")
        for vp in state["vps"]:
            if vp not in state_provs:
                issues.append(f"{rel(state['file'])}: victory_points province {vp} is outside this state")
            if vp not in provinces:
                issues.append(f"{rel(state['file'])}: victory_points province {vp} is not in definition.csv")
        for province in state["building_provs"]:
            if province not in state_provs:
                issues.append(f"{rel(state['file'])}: province building {province} is outside this state")
            if province not in provinces:
                issues.append(f"{rel(state['file'])}: province building {province} is not in definition.csv")
    for sid, files in sorted(state_ids.items()):
        if len(files) > 1:
            issues.append(f"duplicate state id {sid}: " + ", ".join(rel(f) for f in files))
    for province, owners in sorted(province_to_states.items()):
        if len(owners) > 1:
            issues.append(
                f"province {province} appears in multiple states: "
                + ", ".join(f"{s['id']} ({rel(s['file'])})" for s in owners)
            )
    land_in_states = set(province_to_states)
    for province, kind in sorted(provinces.items()):
        if province != 0 and kind == "land" and province not in land_in_states:
            issues.append(f"land province {province} from definition.csv is not assigned to any state")
    return issues[:limit], len(issues)


def check_localisation(limit):
    issues = []
    loc_dir = ROOT / "localisation"
    if not loc_dir.exists():
        return issues, 0
    header = re.compile(r"^\s*l_[A-Za-z_]+:\s*$")
    for path in loc_dir.rglob("*.yml"):
        text = read_text(path)
        first = next((line for line in text.splitlines() if line.strip()), "")
        if not header.match(first):
            issues.append(f"{rel(path)}: suspicious localisation header {first!r}")
    return issues[:limit], len(issues)


def check_special_project_leftovers(limit):
    issues = []
    patterns = [
        re.compile(r"\b(?:PROJECT|EXTRA_PROJECT)\s*=\s*sp_[A-Za-z0-9_]+"),
        re.compile(r"\bsp:[A-Za-z0-9_]+"),
        re.compile(r"\bspecial_project_specialization\b"),
        re.compile(r"\bis_special_project_(?:completed|tech)\b"),
    ]
    for path in iter_files("common", "history", "events"):
        text = strip_comments(read_text(path))
        for lineno, line in enumerate(text.splitlines(), 1):
            if any(pattern.search(line) for pattern in patterns):
                issues.append(f"{rel(path)}:{lineno}: {line.strip()[:160]}")
    return issues[:limit], len(issues)


def check_synchronized_dynamic_tokens(ideology_groups, limit):
    issues = []
    tokens = set()
    token_dir = ROOT / "common" / "synchronized_dynamic_tokens"
    if token_dir.exists():
        for path in token_dir.rglob("*.txt"):
            text = strip_comments(read_text(path))
            for line in text.splitlines():
                token = line.strip()
                if token:
                    tokens.add(token)
    for ideology in sorted(ideology_groups):
        if ideology not in tokens:
            issues.append(f"ideology group {ideology} is missing from common/synchronized_dynamic_tokens")
    return issues[:limit], len(issues)


def check_railway_gun_names(tags, limit):
    issues = []
    base = ROOT / "common" / "units" / "names_railway_guns"
    if not base.exists():
        return issues, 0
    for path in base.rglob("*.txt"):
        text = strip_comments(read_text(path))
        for tag in re.findall(r"\bfor_countries\s*=\s*\{([^}]*)\}", text):
            for country in re.findall(r"\b[A-Z][A-Z0-9]{2,3}\b", tag):
                if country not in tags:
                    issues.append(f"{rel(path)}: for_countries uses undefined tag {country}")
        for lineno, line in enumerate(text.splitlines(), 1):
            if re.search(r"\bdivision_types\s*=\s*\{\s*railway_gun\b", line):
                issues.append(f"{rel(path)}:{lineno}: railway gun name groups use 'type = railway_gun'")
    return issues[:limit], len(issues)


def check_entity_unit_mesh_refs(limit):
    issues = []
    base = ROOT / "gfx" / "entities"
    if not base.exists():
        return issues, 0
    texts = {}
    for path in base.rglob("*"):
        if path.is_file() and path.suffix.lower() in {".gfx", ".asset"}:
            texts[path] = strip_comments(read_text(path))
    defined = set()
    used = []
    for path, text in texts.items():
        for match in re.finditer(r'\bpdxmesh\s*=\s*"([^"]+)"', text):
            used.append((match.group(1), path, text[: match.start()].count("\n") + 1))
        for match in re.finditer(r'\bpdxmesh\s*=\s*\{[^{}]*?\bname\s*=\s*"([^"]+)"', text, re.S):
            defined.add(match.group(1))
    interesting = ("infantry", "weapon", "lighter", "cigarette", "STP_")
    for name, path, lineno in used:
        if any(part in name for part in interesting) and name not in defined:
            issues.append(f"{rel(path)}:{lineno}: pdxmesh {name} is not defined in gfx/entities")
    return issues[:limit], len(issues)


def check_gfx_entity_ownership(limit):
    issues = []
    entity_dir = ROOT / "gfx" / "entities"
    root_gfx = ROOT / "gfx"
    if not entity_dir.exists() or not root_gfx.exists():
        return issues, 0

    required = [
        entity_dir / "ADISCORD_country_infantry.gfx",
        entity_dir / "zz_ADISCORD_country_infantry.asset",
        entity_dir / "zz_ADISCORD_building_entities.asset",
        entity_dir / "mapitems_custom.asset",
        entity_dir / "particles_custom.gfx",
        root_gfx / "particles" / "environment" / "smog.asset",
    ]
    for path in required:
        if not path.is_file():
            issues.append(f"{rel(path)} is missing required A-Discord entity addendum")

    forbidden = [
        root_gfx / "ADISCORD_country_infantry.gfx",
        root_gfx / "buildings.asset",
        root_gfx / "particle_entities.asset",
        root_gfx / "particles.gfx",
        root_gfx / "particles_custom.gfx",
        entity_dir / "buildings.asset",
        entity_dir / "particle_entities.asset",
        entity_dir / "particles.gfx",
    ]
    for path in forbidden:
        if path.exists():
            issues.append(f"{rel(path)} overrides or duplicates the vanilla 1.19 entity database")

    for source in entity_dir.iterdir():
        mirror = root_gfx / source.name
        if source.is_file() and mirror.is_file() and source.read_bytes() == mirror.read_bytes():
            issues.append(f"{rel(mirror)} exactly duplicates {rel(source)}")

    mapitems_path = entity_dir / "mapitems_custom.asset"
    if mapitems_path.is_file():
        mapitems = read_text(mapitems_path)
        pyramid = ""
        for entity_match in re.finditer(r"\bentity\s*=\s*\{", mapitems):
            block = extract_block(mapitems, entity_match.start())
            if re.search(
                r'\bname\s*=\s*"ADISCORD_vorkerland_pyramid_entity"', block
            ):
                pyramid = block
                break
        for index in range(1, 8):
            locator = f'ADISCORD_city_smoke_{index}'
            if pyramid.count(locator) < 2:
                issues.append(
                    f"{rel(mapitems_path)}: Vorkerland pyramid is missing locator/event pair {locator}"
                )

    smog_path = root_gfx / "particles" / "environment" / "smog.asset"
    if smog_path.is_file():
        smog = read_text(smog_path)
        if "force=chaos,sidewind" in smog and not re.search(
            r'force\s*=\s*\{(?:(?!\n\s*force\s*=).)*?name\s*=\s*"sidewind"',
            smog,
            re.DOTALL,
        ):
            issues.append(f'{rel(smog_path)}: smog references undefined particle force "sidewind"')

    for path in sorted(entity_dir.glob("*.asset")):
        if re.search(r'\bname\s*=\s*"city_smoke_entity"', read_text(path)):
            issues.append(
                f"{rel(path)} globally overrides vanilla city_smoke_entity; keep custom smoke on ADISCORD entities"
            )

    terrain_path = ROOT / "interface" / "ADISCORD_terrain.gfx"
    terrain = read_text(terrain_path) if terrain_path.is_file() else ""
    if not re.search(r'\bname\s*=\s*"GFX_terrain_contaminated"', terrain):
        issues.append(
            f'{rel(terrain_path)} is missing sprite GFX_terrain_contaminated for the custom terrain'
        )
    if not re.search(
        r'\bname\s*=\s*"GFX_terrain_contaminated_winter"'
        r'(?:(?!\n\s*spriteType\s*=).)*?'
        r'\btextureFile\s*=\s*"gfx/interface/terrains/terrain_contaminated_winter\.dds"',
        terrain,
        re.DOTALL,
    ):
        issues.append(
            f'{rel(terrain_path)} is missing winter sprite GFX_terrain_contaminated_winter '
            'for the custom terrain'
        )
    winter_terrain_texture = ROOT / "gfx" / "interface" / "terrains" / "terrain_contaminated_winter.dds"
    if not winter_terrain_texture.is_file():
        issues.append(f'{rel(winter_terrain_texture)} is missing winter contaminated terrain texture')

    music_station = ROOT / "music" / "one_minute.txt"
    music_gui_path = ROOT / "interface" / "ADISCORD_musicplayer_compat.gui"
    if music_station.is_file():
        music_gui = read_text(music_gui_path) if music_gui_path.is_file() else ""
        for widget in ("one_minute_faceplate", "one_minute_stations_entry"):
            if not re.search(rf'\bname\s*=\s*"{widget}"', music_gui):
                issues.append(
                    f'{rel(music_gui_path)} is missing {widget} required by music station one_minute'
                )
    return issues[:limit], len(issues)


def check_autonomy_chains(limit):
    issues = []
    standard = {
        "autonomy_integrated_puppet",
        "autonomy_puppet",
        "autonomy_colony",
        "autonomy_dominion",
    }
    vorkerland = {
        "autonomy_district_in_Vorkerland",
        "autonomy_republic_in_Vorkerland",
    }
    feudal = {
        "autonomy_feodal_baronage",
        "autonomy_feodal_comitatus",
        "autonomy_feodal_ducatus",
    }
    contracts = {
        "autonomy_contract_protectorate",
        "autonomy_contract_client",
    }
    expected = {
        **{identifier: standard for identifier in standard},
        **{identifier: vorkerland for identifier in vorkerland},
        **{identifier: feudal for identifier in feudal},
        **{identifier: contracts for identifier in contracts},
        "autonomy_shadow_state": {"autonomy_shadow_state"},
        "autonomy_supervised_state": {"autonomy_supervised_state"},
        "autonomy_collaboration_government": {"autonomy_collaboration_government"},
    }

    autonomy_dir = ROOT / "common" / "autonomous_states"
    found = set()
    if not autonomy_dir.is_dir():
        issues.append(f"{rel(autonomy_dir)} is missing")
        return issues[:limit], len(issues)

    for path in sorted(autonomy_dir.glob("*.txt")):
        text = strip_comments(read_text(path))
        for state_match in re.finditer(r"\bautonomy_state\s*=\s*\{", text):
            block = extract_block(text, state_match.start())
            id_match = re.search(r"\bid\s*=\s*([A-Za-z0-9_]+)", block)
            if not id_match or id_match.group(1) not in expected:
                continue
            identifier = id_match.group(1)
            found.add(identifier)
            filter_match = re.search(
                r"\ballowed_levels_filter\s*=\s*\{(?P<body>[^{}]*)\}",
                block,
                re.DOTALL,
            )
            actual = set(re.findall(r"\bautonomy_[A-Za-z0-9_]+\b", filter_match.group("body"))) if filter_match else set()
            if actual != expected[identifier]:
                issues.append(
                    f"{rel(path)}: {identifier} leaks between autonomy chains; "
                    f"expected {sorted(expected[identifier])}, found {sorted(actual)}"
                )

    for identifier in sorted(set(expected) - found):
        issues.append(f"common/autonomous_states: missing audited autonomy state {identifier}")
    return issues[:limit], len(issues)


def check_vanilla_filename_leftovers(tags, limit):
    issues = []
    own_tags = set(tags)
    vanilla_tags = VANILLA_TAGS - own_tags

    ai_peace = ROOT / "common" / "peace_conference" / "ai_peace"
    if ai_peace.exists():
        for path in sorted(ai_peace.glob("*.txt")):
            stem = path.stem
            if stem in vanilla_tags:
                issues.append(f"{rel(path)}: vanilla country tag in peace AI filename")

    cost_modifiers = ROOT / "common" / "peace_conference" / "cost_modifiers"
    if cost_modifiers.exists():
        for path in sorted(cost_modifiers.glob("*_peace.txt")):
            tag = path.stem.removesuffix("_peace")
            if tag in vanilla_tags:
                issues.append(f"{rel(path)}: vanilla country tag in peace cost filename")

    flags = ROOT / "gfx" / "flags"
    if flags.exists():
        for path in flags.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in {".tga", ".dds"}:
                continue
            tag = path.stem
            if tag in vanilla_tags:
                issues.append(f"{rel(path)}: vanilla country flag file without matching mod tag")
            if path.suffix.lower() == ".tga":
                data = path.read_bytes()
                if len(data) < 18:
                    issues.append(f"{rel(path)}: malformed TGA header")
                elif data[16] != 32:
                    issues.append(f"{rel(path)}: {data[16]}bpp TGA should be 32bpp for HOI4 runtime loading")

    return issues[:limit], len(issues)


def scan_vanilla_leftovers(tags, ideology_groups, limit):
    token_hits = Counter()
    examples = defaultdict(list)
    own_tags = set(tags)
    own_ideologies = set(ideology_groups)
    vanilla_tags = VANILLA_TAGS - own_tags
    vanilla_ideologies = VANILLA_IDEOLOGIES - own_ideologies
    token_re = re.compile(r"\b([A-Z][A-Z0-9]{2,3}|[A-Za-z_][A-Za-z0-9_]*)\b")
    for path in iter_files(*GAME_DIRS):
        if "tools/" in rel(path):
            continue
        text = strip_comments(read_text(path))
        for lineno, line in enumerate(text.splitlines(), 1):
            for token in token_re.findall(line):
                if token in vanilla_tags or token in vanilla_ideologies:
                    key = f"tag:{token}" if token in vanilla_tags else f"ideology:{token}"
                    token_hits[key] += 1
                    if len(examples[key]) < limit:
                        examples[key].append(f"{rel(path)}:{lineno}: {line.strip()[:160]}")
    return token_hits, examples


def find_named_block(text: str, name: str) -> str:
    match = re.search(rf"\b{re.escape(name)}\s*=\s*\{{", text)
    if not match:
        return ""
    return extract_block(text, match.start())


def parse_localisation_keys():
    keys = set()
    loc_dir = ROOT / "localisation"
    if not loc_dir.exists():
        return keys
    for path in loc_dir.rglob("*.yml"):
        text = read_text(path)
        for line in text.splitlines():
            match = re.match(r"\s*([A-Za-z0-9_.:-]+)\s*:", line)
            if match and not match.group(1).startswith("l_"):
                keys.add(match.group(1))
    return keys


def check_economy_guardrails(limit):
    issues = []

    placeholder = ROOT / "localisation" / "russian" / "ADISCORD_technical_placeholders_l_russian.yml"
    if placeholder.exists():
        issues.append(f"{rel(placeholder)} must not be recreated")

    forbidden_patterns = {
        "money_income_factor": "fake TDA/DH money modifier",
        "tax_efficiency_factor": "fake TDA/DH tax modifier",
        "num_battalions": "unproven dynamic unit count in economy pass",
        "max_manpower": "unproven manpower shortcut in economy pass",
    }
    for path in iter_files("common", "interface", "localisation"):
        text = strip_comments(read_text(path))
        for lineno, line in enumerate(text.splitlines(), 1):
            for token, reason in forbidden_patterns.items():
                if re.search(rf"\b{re.escape(token)}\b", line):
                    issues.append(f"{rel(path)}:{lineno}: {token} ({reason})")

    on_actions = ROOT / "common" / "on_actions" / "00_ADISCORD_on_actions.txt"
    if on_actions.exists():
        text = strip_comments(read_text(on_actions))
        for pulse in ("on_monthly", "on_weekly", "on_yearly"):
            block = find_named_block(text, pulse)
            if re.search(r"\bevery_country\s*=", block):
                issues.append(f"{rel(on_actions)}: {pulse} contains every_country; keep economy pulse country-scoped")
        weekly = find_named_block(text, "on_weekly")
        if re.search(r"\bevery_owned_state\s*=", weekly):
            issues.append(f"{rel(on_actions)}: on_weekly contains every_owned_state; keep state scans out of weekly refresh")

    consumer_files = [
        ROOT / "common" / "ideas" / "ADISCORD_laws.txt",
        ROOT / "common" / "ideas" / "ADISCORD_society_development.txt",
        ROOT / "common" / "ideas" / "_economic.txt",
    ]
    for path in consumer_files:
        if not path.exists():
            continue
        text = strip_comments(read_text(path))
        for lineno, line in enumerate(text.splitlines(), 1):
            if re.search(r"\bconsumer_goods_factor\b", line):
                issues.append(f"{rel(path)}:{lineno}: consumer_goods_factor in audited economy law/development file")

    loc_keys = parse_localisation_keys()
    gui = ROOT / "interface" / "ADISCORD_economy.gui"
    if gui.exists():
        text = strip_comments(read_text(gui))
        key_re = re.compile(r'\b(?:buttonText|text|pdx_tooltip|pdx_tooltip_delayed)\s*=\s*"([^"]+)"')
        for match in key_re.finditer(text):
            key = match.group(1)
            if key.startswith("ADISCORD_") and key not in loc_keys:
                lineno = text[: match.start()].count("\n") + 1
                issues.append(f"{rel(gui)}:{lineno}: missing localisation key {key}")

    return issues[:limit], len(issues)


def check_ncns_and_campaign_compatibility(limit):
    issues = []

    descriptor = ROOT / "descriptor.mod"
    descriptor_text = read_text(descriptor) if descriptor.exists() else ""
    if 'replace_path="common/factions"' not in descriptor_text:
        issues.append("descriptor.mod: common/factions must be owned by the total conversion")

    template_path = ROOT / "common" / "factions" / "templates" / "ADISCORD_faction_templates.txt"
    manifest_path = ROOT / "common" / "factions" / "goals" / "ADISCORD_faction_manifests.txt"
    goals_path = ROOT / "common" / "factions" / "goals" / "ADISCORD_faction_goals.txt"
    leadership_rule_path = ROOT / "common" / "factions" / "rules" / "ADISCORD_change_leader_rules.txt"
    rule_group_path = ROOT / "common" / "factions" / "rules" / "groups" / "ADISCORD_rule_groups.txt"
    template_text = strip_comments(read_text(template_path)) if template_path.exists() else ""
    manifest_text = strip_comments(read_text(manifest_path)) if manifest_path.exists() else ""
    goals_text = strip_comments(read_text(goals_path)) if goals_path.exists() else ""
    leadership_rule_text = strip_comments(read_text(leadership_rule_path)) if leadership_rule_path.exists() else ""
    rule_group_text = strip_comments(read_text(rule_group_path)) if rule_group_path.exists() else ""
    if "faction_template_ADISCORD_standard" not in template_text:
        issues.append(f"{rel(template_path)}: missing A-Discord NCNS faction template")
    if "ADISCORD_faction_manifest_continuity" not in template_text:
        issues.append(f"{rel(template_path)}: template is missing the A-Discord manifest")
    if "ADISCORD_faction_manifest_continuity" not in manifest_text:
        issues.append(f"{rel(manifest_path)}: missing A-Discord faction manifest")
    if "change_leader_rule_influence" not in leadership_rule_text:
        issues.append(f"{rel(leadership_rule_path)}: missing NCNS leadership rule definition")
    if "change_leader_rule_influence" not in rule_group_text:
        issues.append(f"{rel(rule_group_path)}: NCNS leadership rule is not assigned to a rule group")

    for goal_id, unlock_effect in (
        ("ADISCORD_faction_goal_operational_continuity", "set_faction_research_unlocked"),
        ("ADISCORD_faction_goal_strategic_coordination", "set_faction_military_unlocked"),
    ):
        if not re.search(
            rf"(?s)\b{goal_id}\s*=\s*\{{.*?\bcomplete_effect\s*=\s*\{{.*?"
            rf"\b{unlock_effect}\s*=\s*yes\b",
            goals_text,
        ):
            issues.append(
                f"{rel(goals_path)}: {goal_id} must expose {unlock_effect} for locked faction-tab lookup"
            )

    faction_histories = {
        "WRK - WorkerLand.txt": "faction_vorkerland_confederation",
        "BJK - Besjaysk.txt": "faction_besjaysk_kingdom",
        "NOD - Nodral.txt": "faction_stp_nod",
    }
    country_dir = ROOT / "history" / "countries"
    for filename, faction_name in faction_histories.items():
        path = country_dir / filename
        text = strip_comments(read_text(path)) if path.exists() else ""
        if "create_faction_from_template" not in text:
            issues.append(f"{rel(path)}: starting faction is not created from an NCNS template")
        if "template = faction_template_ADISCORD_standard" not in text:
            issues.append(f"{rel(path)}: starting faction does not use the A-Discord template")
        if f"name = {faction_name}" not in text:
            issues.append(f"{rel(path)}: scripted faction name {faction_name} is missing")

    obsolete_faction = re.compile(r"(?m)^\s*create_faction\s*=")
    invalid_campaign = re.compile(r"\b(?:has|add|remove)_campaign_slot\b")
    for path in iter_files("common", "history", "events"):
        text = strip_comments(read_text(path))
        for pattern, reason in (
            (obsolete_faction, "obsolete pre-NCNS create_faction effect"),
            (invalid_campaign, "nonexistent native campaign-slot token"),
        ):
            for match in pattern.finditer(text):
                lineno = text[: match.start()].count("\n") + 1
                issues.append(f"{rel(path)}:{lineno}: {reason}")

    shared_effects_path = ROOT / "common" / "scripted_effects" / "ADISCORD_shared_action_effects.txt"
    shared_triggers_path = ROOT / "common" / "scripted_triggers" / "ADISCORD_shared_action_triggers.txt"
    shared_effects = strip_comments(read_text(shared_effects_path)) if shared_effects_path.exists() else ""
    shared_triggers = strip_comments(read_text(shared_triggers_path)) if shared_triggers_path.exists() else ""
    for token in (
        "ADISCORD_campaign_slot_grant",
        "ADISCORD_campaign_slot_consume",
        "ADISCORD_campaign_slot_release",
        "ADISCORD_available_campaign_slots",
    ):
        if token not in shared_effects:
            issues.append(f"{rel(shared_effects_path)}: missing variable-backed campaign API token {token}")
    if "ADISCORD_has_campaign_slot" not in shared_triggers or "ADISCORD_available_campaign_slots" not in shared_triggers:
        issues.append(f"{rel(shared_triggers_path)}: missing variable-backed campaign availability trigger")

    return issues[:limit], len(issues)


def print_section(title: str, issues, total: int | None = None):
    total_text = len(issues) if total is None else total
    print(f"\n== {title}: {total_text} ==")
    if not issues:
        print("OK")
        return
    for item in issues:
        print(f"- {item}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=40, help="examples per section")
    args = parser.parse_args()

    tags, dynamic_tags = parse_country_tags()
    ideology_groups, ideology_types = parse_ideologies()
    provinces = parse_definition()

    print("A-Discord total-conversion validation")
    print(f"Root: {ROOT}")
    print(f"Country tags: {len(tags)}")
    print(f"Ideology groups: {', '.join(sorted(ideology_groups)) or 'NONE'}")
    print(f"Ideology types: {len(ideology_types)}")
    print(f"Definition provinces: {len(provinces)}")

    brace_issues, brace_total = check_braces(args.limit)
    print_section("Brace balance", brace_issues, brace_total)

    country_issues, country_total = check_countries(
        tags, dynamic_tags, ideology_groups, ideology_types, args.limit
    )
    print_section("Countries and ideologies", country_issues, country_total)

    event_id_issues = validate_adiscord_event_ids()
    print_section(
        "Event ID registry",
        event_id_issues[: args.limit],
        len(event_id_issues),
    )

    state_issues, state_total = check_states(tags, provinces, args.limit)
    print_section("Map and states", state_issues, state_total)

    building_issues = validate_adiscord_map_buildings()
    print_section("Map building state assignments", building_issues[: args.limit], len(building_issues))

    terrain_snow_issues = validate_adiscord_terrain_snow()
    print_section("Permanent snow terrain", terrain_snow_issues[: args.limit], len(terrain_snow_issues))

    loc_issues, loc_total = check_localisation(args.limit)
    print_section("Localisation headers", loc_issues, loc_total)

    special_project_issues, special_project_total = check_special_project_leftovers(args.limit)
    print_section("Special project leftovers", special_project_issues, special_project_total)

    token_issues, token_total = check_synchronized_dynamic_tokens(ideology_groups, args.limit)
    print_section("Synchronized dynamic tokens", token_issues, token_total)

    railway_issues, railway_total = check_railway_gun_names(tags, args.limit)
    print_section("Railway gun names", railway_issues, railway_total)

    entity_issues, entity_total = check_entity_unit_mesh_refs(args.limit)
    print_section("Entity unit mesh refs", entity_issues, entity_total)

    gfx_entity_issues, gfx_entity_total = check_gfx_entity_ownership(args.limit)
    print_section("GFX entity ownership", gfx_entity_issues, gfx_entity_total)

    autonomy_issues, autonomy_total = check_autonomy_chains(args.limit)
    print_section("Autonomy chain isolation", autonomy_issues, autonomy_total)

    filename_issues, filename_total = check_vanilla_filename_leftovers(tags, args.limit)
    print_section("Vanilla filename leftovers", filename_issues, filename_total)

    economy_issues, economy_total = check_economy_guardrails(args.limit)
    print_section("Economy guardrails", economy_issues, economy_total)

    economy_ai_issues = validate_adiscord_economy_ai()
    print_section("Economy and AI semantics", economy_ai_issues, len(economy_ai_issues))

    strategic_resource_issues = validate_adiscord_strategic_resources_ui()
    print_section(
        "Strategic resources and economy UI",
        strategic_resource_issues[: args.limit],
        len(strategic_resource_issues),
    )

    trade_region_issues = validate_adiscord_trade_regions()
    print_section(
        "Lore trade-region geography",
        trade_region_issues[: args.limit],
        len(trade_region_issues),
    )

    vorkerland_recovery_issues = validate_adiscord_vorkerland_recovery()
    print_section(
        "Vorkerland three-claimant recovery",
        vorkerland_recovery_issues[: args.limit],
        len(vorkerland_recovery_issues),
    )

    vorkerland_focus_issues = validate_adiscord_vorkerland_civil_war_focus()
    print_section(
        "Vorkerland civil-war focus skeleton",
        vorkerland_focus_issues[: args.limit],
        len(vorkerland_focus_issues),
    )

    vorkerland_focus_decision_issues = validate_adiscord_vorkerland_focus_decisions()
    print_section(
        "Vorkerland focus-unlocked operations",
        vorkerland_focus_decision_issues[: args.limit],
        len(vorkerland_focus_decision_issues),
    )

    vorkerland_diplomacy_issues = validate_adiscord_vorkerland_diplomacy()
    print_section(
        "Vorkerland regional diplomacy",
        vorkerland_diplomacy_issues[: args.limit],
        len(vorkerland_diplomacy_issues),
    )

    vorkerland_story_issues = validate_adiscord_vorkerland_story()
    print_section(
        "Vorkerland civil-war story and news",
        vorkerland_story_issues[: args.limit],
        len(vorkerland_story_issues),
    )

    division_template_issues = validate_adiscord_division_templates()
    print_section(
        "Division template audit",
        division_template_issues[: args.limit],
        len(division_template_issues),
    )

    ncns_issues, ncns_total = check_ncns_and_campaign_compatibility(args.limit)
    print_section("NCNS factions and campaign slots", ncns_issues, ncns_total)

    token_hits, examples = scan_vanilla_leftovers(tags, ideology_groups, min(args.limit, 8))
    print(f"\n== Vanilla leftovers: {sum(token_hits.values())} hits in {len(token_hits)} tokens ==")
    if not token_hits:
        print("OK")
    else:
        for token, count in token_hits.most_common(60):
            print(f"- {token}: {count}")
            for example in examples[token]:
                print(f"  {example}")


if __name__ == "__main__":
    main()
