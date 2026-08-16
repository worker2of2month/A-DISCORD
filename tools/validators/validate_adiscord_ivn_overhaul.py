"""Validate the IVN island-administration and geography contract."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

from tools.builders import build_adiscord_island_administration_icon as icon_builder
from tools.builders import build_adiscord_ivn_geography as geography_builder
from tools.builders import build_adiscord_map_buildings as map_buildings
from tools.builders import build_adiscord_new_states as state_builder
from tools.lib.paths import repository_root


ROOT = repository_root()
EXPECTED_PROVINCE_SHA256 = (
    "4CE9521BD3ADB7966E951B534D9DEA31D0C995441CDE60E99DEC3A2D3A530511"
)


def province_geometry_issue() -> str | None:
    province_hash = hashlib.sha256((ROOT / "map/provinces.bmp").read_bytes()).hexdigest().upper()
    if province_hash != EXPECTED_PROVINCE_SHA256:
        return "map/provinces.bmp: reviewed IVN city-split geometry drifted"
    return None


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig", errors="strict")


def _state_provinces(state_id: int) -> set[int]:
    source = _text(state_builder.state_path(state_id))
    match = re.search(r"\bprovinces\s*=\s*\{([^}]*)\}", source, re.DOTALL)
    if match is None:
        raise RuntimeError(f"state {state_id}: missing provinces block")
    return {int(value) for value in re.findall(r"\d+", match.group(1))}


def _state_vps(state_id: int) -> tuple[tuple[int, int], ...]:
    return tuple(
        (int(province), int(value))
        for province, value in re.findall(
            r"\bvictory_points\s*=\s*\{\s*(\d+)\s+(\d+)\s*\}",
            _text(state_builder.state_path(state_id)),
        )
    )


def collect_issues() -> list[str]:
    issues: list[str] = []
    try:
        for state_id, expected in state_builder.IVANLAND_OVERHAUL_PROVINCES.items():
            actual = _state_provinces(state_id)
            if actual != set(expected):
                issues.append(f"state {state_id}: Ivanland province partition drifted")
        for state_id, expected in state_builder.IVANLAND_OVERHAUL_VICTORY_POINTS.items():
            if _state_vps(state_id) != expected:
                issues.append(f"state {state_id}: Ivanland victory-point manifest drifted")

        for state_id in (128, 693, 694):
            source = _text(state_builder.state_path(state_id))
            if not re.search(r"\bowner\s*=\s*IIA\b", source) or not re.search(r"\badd_core_of\s*=\s*IIA\b", source):
                issues.append(f"state {state_id}: island state must be owned and cored by IIA")

        required_tokens = {
            ROOT / "common/autonomous_states/ADISCORD_island_administration.txt": (
                "id = autonomy_island_administration", "use_overlord_color = yes", "default = no"
            ),
            ROOT / "history/countries/IVN - IvanLand.txt": (
                "target = IIA", "autonomy_state = autonomy_island_administration", "freedom_level = 0.00"
            ),
            ROOT / "history/countries/IIA - Itoran Island Administration.txt": (
                "capital = 693", 'oob = "IIA"', "recruit_character = IIA_Artem_Severin"
            ),
            ROOT / "common/characters/IIA.txt": (
                "GFX_portrait_IIA_Artem_Severin", "IIA_Artem_Severin"
            ),
            ROOT / "interface/ADISCORD_leader_portraits.gfx": (
                'name = "GFX_portrait_IIA_Artem_Severin"',
                'texturefile = "gfx/leaders/IIA/portrait_IIA_Artem_Severin.png"',
            ),
        }
        for path, tokens in required_tokens.items():
            if not path.is_file():
                issues.append(f"{path.relative_to(ROOT).as_posix()}: missing")
                continue
            source = _text(path)
            for token in tokens:
                if token not in source:
                    issues.append(f"{path.relative_to(ROOT).as_posix()}: missing {token}")

        leader_portrait = ROOT / "gfx/leaders/IIA/portrait_IIA_Artem_Severin.png"
        if not leader_portrait.is_file():
            issues.append("gfx/leaders/IIA/portrait_IIA_Artem_Severin.png: missing")
        elif leader_portrait.read_bytes()[16:24] != bytes.fromhex("0000009c000000d2"):
            issues.append("gfx/leaders/IIA/portrait_IIA_Artem_Severin.png: expected 156x210 PNG")

        ivn_oob = _text(ROOT / "history/units/IVN.txt")
        iia_oob = _text(ROOT / "history/units/IIA.txt")
        if len(re.findall(r"\bdivision\s*=\s*\{", ivn_oob)) != 16 or "location = 579" in ivn_oob:
            issues.append("history/units/IVN.txt: IVN must retain 16 divisions outside IIA")
        if len(re.findall(r"\bdivision\s*=\s*\{", iia_oob)) != 1 or "location = 579" not in iia_oob:
            issues.append("history/units/IIA.txt: IIA must have one garrison at province 579")

        issues.extend(f"island asset: {item}" for item in icon_builder.drift())
        geography_outputs = geography_builder.expected()
        issues.extend(
            f"IVN geography: {item}"
            for item in geography_builder.validate(geography_outputs)
        )
        affected_states = {25, 128, 693, 694, 695, 696, 697, 698}
        issues.extend(
            item for item in map_buildings.validate(ROOT)
            if any(f"state {state_id} " in item for state_id in affected_states)
        )

        province_issue = province_geometry_issue()
        if province_issue:
            issues.append(province_issue)
    except (OSError, RuntimeError, ValueError) as error:
        issues.append(str(error))
    return issues


def main() -> int:
    issues = collect_issues()
    if issues:
        for issue in issues:
            print(f"ERROR: {issue}")
        return 1
    print("Ivanland island-administration and geography validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
