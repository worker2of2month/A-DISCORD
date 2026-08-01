"""Finish the state shells added in July 2026 and build desert-country flags.

The province lists remain authoritative: this builder only supplies the state
metadata that Nudge does not create (owner, core, population and buildings).
"""

from __future__ import annotations

import re
from pathlib import Path

from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = ROOT / "history" / "states"


KDR_STATES = tuple(range(234, 248))
RHM_STATES = (248, 249, 250, *range(252, 259))
SDR_STATES = (251, *range(259, 265))
MZR_STATES = tuple(range(265, 276))
KYZ_STATES = tuple(range(276, 287))
SHL_STATES = tuple(range(287, 295))
GLP_STATES = (*range(295, 303), 304, 305)

STARTING_OWNERS = {
    69: "AZH",
    174: "WEF",
    175: "WEF",
    **{state_id: "KDR" for state_id in KDR_STATES},
    **{state_id: "RHM" for state_id in RHM_STATES},
    **{state_id: "SDR" for state_id in SDR_STATES},
    **{state_id: "MZR" for state_id in MZR_STATES},
    **{state_id: "KYZ" for state_id in KYZ_STATES},
    **{state_id: "SHL" for state_id in SHL_STATES},
    **{state_id: "GLP" for state_id in GLP_STATES},
    303: "TFF",
    306: "WRK", 307: "VAD", 308: "WRK", 309: "WRK",
    310: "SOL", 311: "WRK", 312: "VLA", 313: "VLA",
    314: "VLA", 315: "TRU", 316: "TRU", 317: "TRU",
    318: "TRU", 319: "ROM", 320: "WRK", 321: "ROM",
    322: "ZAO", 323: "WRK", 324: "VAD", 325: "VAD",
    326: "PIV", 327: "WRK", 328: "PWR",
    329: "EXZ", 330: "EXZ",
}

LEGACY_OWNER_GAPS = {
    27: "WRK",
    79: "WRK",
    82: "WRK",
    194: "PWR",
    197: "VLA",
}

LEGACY_OWNER_OVERRIDES = {
    198: "VAD",
}

CAPITALS = {
    69: (367, 10),
    174: (158, 10),
    241: (971, 10),
    253: (443, 10),
    260: (197, 10),
    275: (193, 10),
    283: (1349, 10),
    294: (1198, 10),
    300: (492, 10),
}
SECONDARY_CENTRES = {
    240: (2309, 3), 248: (274, 3), 249: (488, 3),
    267: (261, 3), 278: (857, 3), 288: (834, 3),
    301: (251, 3),
}

# Smaller settlements spread VPs across the wide MZR and KYZ territories
# without also granting the population and industry of a secondary city.
MINOR_VPS = {
    265: (3465, 1), 270: (2504, 2), 273: (3643, 2),
    276: (10375, 1), 277: (6261, 2), 286: (7903, 2),
}

# Sparse deposits give every southern country something to extract and trade
# without turning the desert into a self-sufficient industrial heartland.
STATE_RESOURCES = {
    69: {"oil": 3, "chromium": 2},
    175: {"steel": 2, "aluminium": 2},
    236: {"steel": 3, "oil": 1},
    255: {"aluminium": 3, "oil": 1},
    263: {"tungsten": 2, "steel": 2},
    269: {"oil": 3, "chromium": 1},
    285: {"tungsten": 2, "aluminium": 2},
    291: {"steel": 3, "chromium": 1},
    299: {"aluminium": 3, "chromium": 1},
}

# Cities that were victory points before the Vorkerland state split. Keep the
# points on their actual urban provinces instead of losing them during rebuild.
VORKERLAND_CENTRES = {
    306: (16643, 3),
    307: (16584, 3),
    308: (16615, 3),
    309: (11795, 5),
    323: (16590, 3),
    327: (16641, 5),
}

# Explicit profiles replace the old pseudo-random 24-72k population formula
# around the densely populated Vorkernsberg conurbation.
STATE_PROFILES = {
    306: {"population": 1_180_000, "category": "large_town", "infrastructure": 3, "industry": 2, "supplies": 3.0},
    307: {"population": 620_000, "category": "town", "infrastructure": 2, "industry": 1, "supplies": 2.0},
    308: {"population": 840_000, "category": "large_town", "infrastructure": 3, "industry": 1, "supplies": 2.5},
    309: {"population": 470_000, "category": "town", "infrastructure": 3, "industry": 1, "supplies": 2.0},
    311: {"population": 560_000, "category": "rural", "infrastructure": 2, "industry": 1, "supplies": 1.5},
    320: {"population": 390_000, "category": "rural", "infrastructure": 2, "industry": 0, "supplies": 1.5},
    323: {"population": 710_000, "category": "town", "infrastructure": 2, "industry": 1, "supplies": 2.0},
    327: {"population": 310_000, "category": "town", "infrastructure": 3, "industry": 1, "supplies": 2.0},
}

EXTRA_CORES = {174: ("EFL",), 175: ("EFL",)}

# Tiny land provinces created in the same Nudge pass were left outside every
# state. Assign each to the neighbouring state with the longest shared border.
EXTRA_PROVINCES_BY_STATE = {
    258: (4759,),
    261: (3536,),
    265: (2244, 3528),
    270: (6833,),
    273: (3918, 10526),
    275: (196,),
    279: (8121,),
    288: (10490,),
    291: (946,),
}

TOWN_STATES = set(CAPITALS) | set(SECONDARY_CENTRES) | {
    306, 307, 308, 309, 318, 323, 327,
}
WASTELANDS = {238, 254, 258, 264, 267, 288, 292, 296, 329, 330}


def state_path(state_id: int) -> Path:
    matches = sorted(STATE_DIR.glob(f"{state_id}-*.txt"))
    if len(matches) != 1:
        raise RuntimeError(f"state {state_id}: expected one file, found {len(matches)}")
    return matches[0]


def population(state_id: int, owner: str) -> int:
    if state_id in STATE_PROFILES:
        return int(STATE_PROFILES[state_id]["population"])
    if owner == "EXZ":
        return 0
    if state_id == 303:
        return 9_000
    if state_id in CAPITALS:
        return {
            69: 145_000,
            174: 95_000,
            241: 135_000,
            253: 105_000,
            260: 72_000,
            275: 145_000,
            283: 112_000,
            294: 128_000,
            300: 118_000,
        }[state_id]
    if state_id in SECONDARY_CENTRES:
        return 65_000
    if 234 <= state_id <= 305:
        return 8_000 + ((state_id * 7_919) % 35_000)
    return 24_000 + ((state_id * 5_173) % 48_000)


def category(state_id: int) -> str:
    if state_id in STATE_PROFILES:
        return str(STATE_PROFILES[state_id]["category"])
    if state_id in TOWN_STATES:
        return "town"
    if state_id in WASTELANDS:
        return "wasteland"
    return "rural"


def buildings(state_id: int, owner: str) -> list[str]:
    if owner == "EXZ":
        return []
    profile = STATE_PROFILES.get(state_id)
    infrastructure = int(profile["infrastructure"]) if profile else 2
    lines = [f"infrastructure = {infrastructure}"]
    if profile:
        industry = int(profile["industry"])
        if industry:
            lines.append(f"industrial_complex = {industry}")
        return lines
    if state_id in CAPITALS:
        lines += ["industrial_complex = 2", "arms_factory = 1", "air_base = 1"]
    elif state_id in SECONDARY_CENTRES:
        lines += ["industrial_complex = 1"]
    elif state_id in TOWN_STATES:
        lines += ["industrial_complex = 1"]
    return lines


def render_state(state_id: int, owner: str) -> str:
    path = state_path(state_id)
    old = path.read_text(encoding="utf-8-sig", errors="strict")
    province_match = re.search(r"provinces\s*=\s*\{([^}]*)\}", old, re.DOTALL)
    if not province_match:
        raise RuntimeError(f"state {state_id}: missing provinces block")
    provinces = [int(value) for value in re.findall(r"\d+", province_match.group(1))]
    provinces = sorted(set(provinces) | set(EXTRA_PROVINCES_BY_STATE.get(state_id, ())))
    if not provinces:
        raise RuntimeError(f"state {state_id}: empty provinces block")

    history = [f"\t\towner = {owner}", f"\t\tadd_core_of = {owner}"]
    history.extend(f"\t\tadd_core_of = {tag}" for tag in EXTRA_CORES.get(state_id, ()))
    urban_provinces = {
        int(fields[0])
        for line in (ROOT / "map" / "definition.csv").read_text(encoding="utf-8-sig").splitlines()
        if len(fields := line.split(";")) > 6 and fields[0].isdigit() and fields[6] == "urban"
    }
    centres = {**CAPITALS, **SECONDARY_CENTRES, **MINOR_VPS, **VORKERLAND_CENTRES}
    if state_id in centres:
        province, value = centres[state_id]
        if province not in provinces:
            raise RuntimeError(f"state {state_id}: city VP {province} is outside the state")
        if province in urban_provinces:
            history.append(f"\t\tvictory_points = {{ {province} {value} }}")

    state_buildings = buildings(state_id, owner)
    if state_buildings:
        history.append("\t\tbuildings = {")
        history.extend(f"\t\t\t{line}" for line in state_buildings)
        history.append("\t\t}")

    province_lines = []
    for start in range(0, len(provinces), 12):
        province_lines.append("\t\t" + " ".join(map(str, provinces[start:start + 12])))

    profile = STATE_PROFILES.get(state_id)
    local_supplies = 0.0 if owner == "EXZ" else (
        float(profile["supplies"]) if profile else (3.0 if state_id in CAPITALS else 1.5)
    )
    resource_block = []
    if state_id in STATE_RESOURCES:
        resource_block = ["\tresources = {"]
        resource_block.extend(
            f"\t\t{resource} = {amount}"
            for resource, amount in STATE_RESOURCES[state_id].items()
        )
        resource_block.append("\t}")
    return "\n".join([
        "state = {",
        f"\tid = {state_id}",
        f'\tname = "STATE_{state_id}"',
        f"\tmanpower = {population(state_id, owner)}",
        f"\tstate_category = {category(state_id)}",
        *resource_block,
        "\thistory = {",
        *history,
        "\t}",
        "\tprovinces = {",
        *province_lines,
        "\t}",
        "\tbuildings_max_level_factor = 1.000",
        f"\tlocal_supplies = {local_supplies:.1f}",
        "}",
        "",
    ])


def draw_kdr(size: tuple[int, int]) -> Image.Image:
    width, height = size
    image = Image.new("RGB", size, (199, 139, 68))
    draw = ImageDraw.Draw(image)
    draw.polygon([(0, height), (width * 0.43, 0), (width * 0.57, 0), (width, height)], fill=(61, 47, 38))
    radius = max(2, height // 7)
    draw.ellipse((width // 2 - radius, height // 2 - radius, width // 2 + radius, height // 2 + radius), fill=(244, 225, 157))
    return image


def draw_mzr(size: tuple[int, int]) -> Image.Image:
    width, height = size
    image = Image.new("RGB", size, (37, 126, 137))
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, height * 0.65, width, height), fill=(218, 166, 73))
    cx, cy = width // 2, height // 2
    r = max(2, height // 5)
    draw.polygon([(cx, cy - r * 2), (cx - r, cy), (cx, cy + r), (cx + r, cy)], fill=(235, 245, 229))
    return image


def draw_shl(size: tuple[int, int]) -> Image.Image:
    width, height = size
    image = Image.new("RGB", size, (51, 39, 83))
    draw = ImageDraw.Draw(image)
    cx, cy = width // 2, height // 2
    rx, ry = width * 0.22, height * 0.34
    draw.polygon([(cx, cy - ry), (cx + rx, cy), (cx, cy + ry), (cx - rx, cy)], fill=(239, 180, 64))
    inset_x, inset_y = rx * 0.45, ry * 0.45
    draw.polygon([(cx, cy - inset_y), (cx + inset_x, cy), (cx, cy + inset_y), (cx - inset_x, cy)], fill=(235, 238, 232))
    return image


def draw_rhm(size: tuple[int, int]) -> Image.Image:
    width, height = size
    image = Image.new("RGB", size, (151, 66, 47))
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, height * 0.62, width, height), fill=(54, 120, 151))
    radius = max(2, height // 5)
    draw.ellipse((width // 2 - radius, height // 2 - radius, width // 2 + radius, height // 2 + radius), outline=(241, 223, 165), width=max(1, height // 13))
    return image


def draw_sdr(size: tuple[int, int]) -> Image.Image:
    width, height = size
    image = Image.new("RGB", size, (191, 113, 48))
    draw = ImageDraw.Draw(image)
    band = max(1, height // 7)
    points = [(0, height * 0.35), (width * 0.25, height * 0.62), (width * 0.5, height * 0.38), (width * 0.75, height * 0.65), (width, height * 0.4)]
    draw.line(points, fill=(238, 226, 191), width=band)
    return image


def draw_kyz(size: tuple[int, int]) -> Image.Image:
    width, height = size
    image = Image.new("RGB", size, (21, 83, 88))
    draw = ImageDraw.Draw(image)
    line = max(1, height // 9)
    draw.line((width * 0.2, height * 0.25, width * 0.8, height * 0.25), fill=(220, 180, 72), width=line)
    for x in (0.28, 0.5, 0.72):
        draw.line((width * x, height * 0.25, width * x, height * 0.76), fill=(220, 180, 72), width=line)
    draw.arc((width * 0.25, height * 0.42, width * 0.75, height * 0.95), 180, 360, fill=(231, 232, 211), width=line)
    return image


def draw_glp(size: tuple[int, int]) -> Image.Image:
    width, height = size
    image = Image.new("RGB", size, (25, 53, 83))
    draw = ImageDraw.Draw(image)
    draw.polygon([(width * 0.5, height * 0.12), (width * 0.82, height * 0.78), (width * 0.18, height * 0.78)], fill=(92, 200, 207))
    draw.polygon([(width * 0.5, height * 0.28), (width * 0.67, height * 0.67), (width * 0.33, height * 0.67)], fill=(231, 238, 218))
    return image


def draw_azh(size: tuple[int, int]) -> Image.Image:
    width, height = size
    image = Image.new("RGB", size, (108, 39, 42))
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, height * 0.72, width, height), fill=(39, 35, 32))
    radius = max(2, height // 5)
    draw.ellipse((width // 2 - radius, height // 2 - radius, width // 2 + radius, height // 2 + radius), fill=(224, 164, 57))
    inner = max(1, radius // 2)
    draw.ellipse((width // 2 - inner, height // 2 - inner, width // 2 + inner, height // 2 + inner), fill=(108, 39, 42))
    return image


def draw_wef(size: tuple[int, int]) -> Image.Image:
    width, height = size
    image = Image.new("RGB", size, (43, 103, 75))
    draw = ImageDraw.Draw(image)
    draw.polygon([(0, 0), (width, 0), (0, height)], fill=(225, 225, 205))
    draw.polygon([(width, 0), (width, height), (0, height)], fill=(196, 99, 48))
    line = max(1, height // 10)
    draw.line((width * 0.18, height * 0.65, width * 0.82, height * 0.35), fill=(39, 55, 49), width=line)
    return image


def build_flags() -> None:
    drawers = {
        "KDR": draw_kdr,
        "RHM": draw_rhm,
        "SDR": draw_sdr,
        "MZR": draw_mzr,
        "KYZ": draw_kyz,
        "SHL": draw_shl,
        "GLP": draw_glp,
        "AZH": draw_azh,
        "WEF": draw_wef,
    }
    for folder, size in ((Path(), (82, 52)), (Path("medium"), (41, 26)), (Path("small"), (10, 7))):
        target = ROOT / "gfx" / "flags" / folder
        target.mkdir(parents=True, exist_ok=True)
        for tag, drawer in drawers.items():
            drawer(size).convert("RGBA").save(target / f"{tag}.tga", compression=None)


def detach_northern_lighthouse() -> None:
    """State 303 was cut from the outer placeholder after Nudge's state pass."""
    outer = state_path(23)
    source = outer.read_text(encoding="utf-8-sig", errors="strict")
    matches = re.findall(r"(?<!\d)3261(?!\d)", source)
    if len(matches) > 1:
        raise RuntimeError("state 23: province 3261 is duplicated inside the placeholder")
    if matches:
        updated = re.sub(r"(?<!\d)3261(?!\d)\s*", "", source, count=1)
        outer.write_text(updated, encoding="utf-8", newline="\n")


def fill_legacy_owner_gaps() -> None:
    """Close obvious pre-existing grey holes without rebuilding their metadata."""
    for state_id, owner in LEGACY_OWNER_GAPS.items():
        path = state_path(state_id)
        source = path.read_text(encoding="utf-8-sig", errors="strict")
        if re.search(r"(?m)^\s*owner\s*=", source):
            continue
        history = f"\n\thistory = {{\n\t\towner = {owner}\n\t\tadd_core_of = {owner}\n\t}}\n"
        marker = re.search(r"(?m)^\s*provinces\s*=", source)
        if not marker:
            raise RuntimeError(f"state {state_id}: missing provinces block")
        updated = source[:marker.start()] + history + source[marker.start():]
        path.write_text(updated, encoding="utf-8", newline="\n")


def apply_legacy_owner_overrides() -> None:
    """Keep explicit ownership corrections without rebuilding legacy states."""
    for state_id, owner in LEGACY_OWNER_OVERRIDES.items():
        path = state_path(state_id)
        source = path.read_text(encoding="utf-8-sig", errors="strict")
        updated, owner_count = re.subn(
            r"(?m)^(\s*)owner\s*=\s*[A-Z0-9]{3}\s*$",
            rf"\1owner={owner}",
            source,
            count=1,
        )
        updated, core_count = re.subn(
            r"(?m)^(\s*)add_core_of\s*=\s*[A-Z0-9]{3}\s*$",
            rf"\1add_core_of={owner}",
            updated,
            count=1,
        )
        if owner_count != 1 or core_count != 1:
            raise RuntimeError(f"state {state_id}: could not apply owner/core override")
        path.write_text(updated, encoding="utf-8", newline="\n")


def main() -> None:
    missing = sorted(set(range(234, 331)) - set(STARTING_OWNERS))
    if missing:
        raise RuntimeError(f"new states without a starting owner: {missing}")
    detach_northern_lighthouse()
    fill_legacy_owner_gaps()
    apply_legacy_owner_overrides()
    for state_id, owner in sorted(STARTING_OWNERS.items()):
        state_path(state_id).write_text(render_state(state_id, owner), encoding="utf-8", newline="\n")
    build_flags()
    print(f"Built metadata for {len(STARTING_OWNERS)} states and flags for nine southern countries.")


if __name__ == "__main__":
    main()
