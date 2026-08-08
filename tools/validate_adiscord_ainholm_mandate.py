#!/usr/bin/env python3
"""Validate the three-state Nodrul-controlled Ainholm mandate."""

from __future__ import annotations

import re
import sys
from pathlib import Path

from PIL import Image

_REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(_REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPOSITORY_ROOT))

try:
    from tools.builders.build_adiscord_ainholm_mandate import (
        FLAG_DIR,
        LOCALISATION_PATH,
        ROOT,
        STATE_PROFILES,
        UNIT_PATH,
        state_path,
    )
except ModuleNotFoundError:
    from builders.build_adiscord_ainholm_mandate import (
        FLAG_DIR,
        LOCALISATION_PATH,
        ROOT,
        STATE_PROFILES,
        UNIT_PATH,
        state_path,
    )


def named_value(source: str, key: str) -> str | None:
    match = re.search(rf"(?m)^\s*{re.escape(key)}\s*=\s*([A-Za-z0-9_.-]+)", source)
    return match.group(1) if match else None


def validate() -> list[str]:
    issues: list[str] = []
    tag_file = ROOT / "common" / "country_tags" / "06_ADISCORD_nodrul_mandate_tags.txt"
    if not tag_file.exists() or 'AIN = "countries/AIN.txt"' not in tag_file.read_text(encoding="utf-8-sig"):
        issues.append("AIN country tag is not registered")

    country_definition = ROOT / "common" / "countries" / "AIN.txt"
    if not country_definition.exists() or "color = rgb" not in country_definition.read_text(encoding="utf-8-sig"):
        issues.append("AIN common country definition is missing its colour")

    country_history = ROOT / "history" / "countries" / "AIN - Ainholm Mandate.txt"
    if not country_history.exists():
        issues.append("AIN country history is missing")
    else:
        source = country_history.read_text(encoding="utf-8-sig")
        for token in ("capital = 118", 'oob = "AIN"', "recruit_character = AIN_Elias_Marven", "AIN_concession_economy"):
            if token not in source:
                issues.append(f"AIN history lacks {token}")

    nod_history = (ROOT / "history" / "countries" / "NOD - Nodral.txt").read_text(encoding="utf-8-sig")
    if "add_to_faction = AIN" not in nod_history:
        issues.append("NOD does not add AIN to its faction")
    autonomy_block = re.search(
        r"set_autonomy\s*=\s*\{\s*target\s*=\s*AIN\s*autonomous_state\s*=\s*([A-Za-z0-9_]+)\s*\}",
        nod_history,
        re.DOTALL,
    )
    if not autonomy_block or autonomy_block.group(1) != "autonomy_colony":
        issues.append("NOD does not establish AIN as a regular colony")

    for state_id, profile in STATE_PROFILES.items():
        source = state_path(state_id).read_text(encoding="utf-8-sig")
        province_block = re.search(r"\bprovinces\s*=\s*\{([^}]*)\}", source, re.DOTALL)
        actual_provinces = tuple(int(value) for value in re.findall(r"\d+", province_block.group(1))) if province_block else ()
        if set(actual_provinces) != set(profile["provinces"]):
            issues.append(f"state {state_id} province allocation drifted")
        if named_value(source, "owner") != profile["owner"]:
            issues.append(f"state {state_id} owner drifted from {profile['owner']}")
        if f"add_core_of = {profile['core']}" not in source:
            issues.append(f"state {state_id} lacks core {profile['core']}")
        actual_claims = set(re.findall(r"(?m)^\s*add_claim_by\s*=\s*([A-Z0-9]{3})\s*$", source))
        if actual_claims != set(profile["claims"]):
            issues.append(f"state {state_id} claims drifted: {sorted(actual_claims)}")
        if named_value(source, "manpower") != str(profile["population"]):
            issues.append(f"state {state_id} population drifted")
        if named_value(source, "state_category") != profile["category"]:
            issues.append(f"state {state_id} category drifted")
        for building, level in profile["buildings"].items():
            if not re.search(rf"(?m)^\s*{re.escape(building)}\s*=\s*{level}\s*$", source):
                issues.append(f"state {state_id} lacks {building}={level}")
        for resource, value in profile["resources"].items():
            if not re.search(rf"(?m)^\s*{re.escape(resource)}\s*=\s*{value}\s*$", source):
                issues.append(f"state {state_id} lacks {resource}={value}")
        for province_id, value in profile["victory_points"]:
            if f"victory_points = {{ {province_id} {value} }}" not in source:
                issues.append(f"state {state_id} lacks victory point {province_id}={value}")

    if not UNIT_PATH.exists():
        issues.append("AIN OOB is missing")
    else:
        oob = UNIT_PATH.read_text(encoding="utf-8-sig")
        if len(re.findall(r"(?m)^\s*division\s*=\s*\{", oob)) != 2:
            issues.append("AIN must start with exactly two guard divisions")

    custom_autonomy = ROOT / "common" / "autonomous_states" / "ADISCORD_nodrul_licensed_mandate.txt"
    if custom_autonomy.exists():
        issues.append("obsolete custom AIN autonomy still exists")

    required_content = {
        ROOT / "common" / "characters" / "ADISCORD_ainholm_characters.txt": "AIN_Elias_Marven",
        ROOT / "common" / "country_leader" / "ADISCORD_ainholm_traits.txt": "AIN_concessionary_director",
        ROOT / "common" / "ideas" / "ADISCORD_ainholm_ideas.txt": "AIN_concession_economy",
    }
    for path, token in required_content.items():
        if not path.exists() or token not in path.read_text(encoding="utf-8-sig"):
            issues.append(f"{path.name} lacks {token}")

    if not LOCALISATION_PATH.exists():
        issues.append("AIN Russian localisation is missing")
    else:
        raw = LOCALISATION_PATH.read_bytes()
        source = raw.decode("utf-8-sig")
        if not raw.startswith(b"\xef\xbb\xbf"):
            issues.append("AIN Russian localisation lost its UTF-8 BOM")
        for key in (
            "AIN:",
            "AIN_Elias_Marven:",
            "AIN_concession_economy:",
            "VICTORY_POINTS_147:",
            "VICTORY_POINTS_16348:",
            "VICTORY_POINTS_16314:",
        ):
            if key not in source:
                issues.append(f"AIN localisation lacks {key[:-1]}")

    for directory, expected_size in (
        (FLAG_DIR, (82, 52)),
        (FLAG_DIR / "medium", (41, 26)),
        (FLAG_DIR / "small", (10, 7)),
    ):
        flag = directory / "AIN.tga"
        if not flag.exists():
            issues.append(f"AIN flag is missing at {flag.relative_to(ROOT)}")
            continue
        with Image.open(flag) as image:
            if image.size != expected_size:
                issues.append(f"AIN flag at {flag.relative_to(ROOT)} has size {image.size}")
            if image.mode != "RGBA":
                issues.append(f"AIN flag at {flag.relative_to(ROOT)} is not 32-bit RGBA")

    if set(STATE_PROFILES) & set(range(474, 551)):
        issues.append("Ainholm mandate entered the protected western-continent state range")
    return issues


def main() -> int:
    issues = validate()
    if issues:
        print(f"Ainholm mandate validation failed with {len(issues)} issue(s):")
        for issue in issues:
            print(f"- {issue}")
        return 1
    print("Ainholm colony validation passed: states 118-119, state 120 to ORV, TFF claims both AIN states.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
