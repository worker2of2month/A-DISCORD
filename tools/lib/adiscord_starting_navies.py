"""Shared starting naval rosters for country generators and bounded rebuilds."""

from __future__ import annotations

from dataclasses import dataclass
import re


@dataclass(frozen=True)
class StartingNavy:
    port: int
    heavy: int
    light: int
    escorts: int
    submarines: int
    convoys: int

    @property
    def profiles(self) -> tuple[str, ...]:
        return ("naval", "naval_taskforce") if self.light else ("naval",)


# The six established fleets retain their authored names, formations and counts.
EXISTING_FLEET_TAGS = frozenset({"STP", "VAL", "NOD", "NAM", "AZH", "EFL"})

# Ports are province IDs, checked against owned state history and physical water
# borders. Small island leagues maintain escorts; industrial powers also keep
# cruisers. RUS has no coast, so cannot host a fleet in the starting campaign.
STARTING_NAVIES = {
    "IVN": StartingNavy(16568, 2, 4, 10, 4, 80),
    "WRK": StartingNavy(4443, 1, 2, 6, 3, 60),
    "SHL": StartingNavy(3234, 0, 2, 6, 2, 60),
    "COF": StartingNavy(8540, 0, 0, 6, 0, 40),
    "YPR": StartingNavy(21, 0, 1, 6, 1, 40),
    "WIT": StartingNavy(16376, 0, 2, 8, 2, 60),
    "TFF": StartingNavy(4887, 0, 1, 6, 1, 40),
    "IIA": StartingNavy(11841, 0, 1, 6, 1, 50),
    "DAN": StartingNavy(7274, 0, 0, 4, 0, 40),
    "BCM": StartingNavy(16651, 0, 0, 4, 0, 40),
    "PIO": StartingNavy(163, 0, 0, 6, 0, 60),
    "MRV": StartingNavy(915, 0, 1, 6, 1, 50),
    "RVN": StartingNavy(10798, 0, 2, 6, 2, 60),
    "SFR": StartingNavy(4230, 0, 0, 6, 0, 40),
    "FLR": StartingNavy(4637, 0, 0, 6, 0, 40),
    "PRR": StartingNavy(9970, 0, 0, 6, 0, 40),
    "ULV": StartingNavy(5667, 0, 0, 6, 0, 40),
    "LUR": StartingNavy(11300, 0, 0, 6, 0, 40),
    "CHD": StartingNavy(1858, 0, 1, 6, 1, 50),
    "EVR": StartingNavy(6545, 0, 0, 4, 0, 40),
    "OLR": StartingNavy(8399, 0, 0, 6, 0, 40),
}

SHIP_MODELS = {
    "heavy_cruiser": ("ADISCORD_cruiser_2155", "CA"),
    "light_cruiser": ("ADISCORD_light_cruiser_2155", "CL"),
    "ADISCORD_coastal_patrol_vessel": ("ADISCORD_escort_ship_2155", "DD"),
    "submarine": ("ADISCORD_submarine_2155", "SS"),
}
FLEET_BEGIN = "\t# BEGIN generated starting navy: tools/builders/build_adiscord_starting_navies.py"
FLEET_END = "\t# END generated starting navy"


def closing_brace(source: str, opening: int) -> int:
    depth = 0
    for token in re.finditer(r'#[^\n]*|"(?:\\.|[^"\\])*"|[{}]', source[opening:]):
        if token[0] == "{":
            depth += 1
        elif token[0] == "}":
            depth -= 1
            if depth == 0:
                return opening + token.start()
    raise ValueError("Unclosed Clausewitz block")


def render_fleet(tag: str) -> str:
    navy = STARTING_NAVIES[tag]
    lines = [FLEET_BEGIN, "\tfleet = {", f'\t\tname = "{tag} - Прибрежный флот"',
             f"\t\tnaval_base = {navy.port}"]
    # Two independent surface groups can cover both ends of a short landing
    # route. Keep heavy-cruiser screens together; submarines raid separately.
    first_escorts = max(3 * navy.heavy, navy.escorts // 2)
    groups = (
        ("Первая эскадра", (navy.heavy, (navy.light + 1) // 2, first_escorts, 0)),
        ("Вторая эскадра", (0, navy.light // 2, navy.escorts - first_escorts, 0)),
        ("Подводная группа", (0, 0, 0, navy.submarines)),
    )
    counters = dict.fromkeys(SHIP_MODELS, 0)
    for name, counts in groups:
        if not sum(counts):
            continue
        lines += ["\t\ttask_force = {", f'\t\t\tname = "{tag} - {name}"',
                  f"\t\t\tlocation = {navy.port}"]
        for (unit, (model, abbreviation)), count in zip(SHIP_MODELS.items(), counts):
            for _ in range(count):
                counters[unit] += 1
                lines += [
                    "\t\t\tship = {",
                    f'\t\t\t\tname = "{tag}-{abbreviation}-{counters[unit]:02d}"',
                    f"\t\t\t\tdefinition = {unit}",
                    "\t\t\t\tstart_experience_factor = 0.15",
                    "\t\t\t\tequipment = {",
                    f"\t\t\t\t\t{model} = {{",
                    "\t\t\t\t\t\tamount = 1",
                    f"\t\t\t\t\t\towner = {tag}",
                    "\t\t\t\t\t}", "\t\t\t\t}", "\t\t\t}",
                ]
        lines.append("\t\t}")
    return "\n".join([*lines, "\t}", FLEET_END, ""])


def with_starting_navy(source: str, tag: str) -> str:
    if tag not in STARTING_NAVIES:
        return source
    generated = re.compile(re.escape(FLEET_BEGIN) + r".*?" + re.escape(FLEET_END) + r"\n?", re.S)
    source = generated.sub("", source)
    if re.search(r"\bfleet\s*=\s*\{", source):
        raise ValueError(f"{tag}: refusing to replace an authored fleet")
    match = re.search(r"(?m)^units\s*=\s*\{", source)
    if match is None:
        raise ValueError(f"{tag}: starting OOB has no units block")
    end = closing_brace(source, source.index("{", match.start()))
    return source[:end] + render_fleet(tag) + source[end:]


def with_naval_history(source: str, tag: str) -> str:
    if tag not in STARTING_NAVIES:
        return source
    navy = STARTING_NAVIES[tag]
    match = re.search(r'(?m)^oob\s*=\s*"[^"\n]+"', source)
    if match is None:
        raise ValueError(f"{tag}: country history has no starting OOB")
    grants = []
    for profile in navy.profiles:
        grant = f"ADISCORD_grant_technology_profile_{profile} = yes"
        # Hulls must be available when the OOB loads, before startup on_actions.
        if grant not in source[:match.start()]:
            source = re.sub(rf"(?m)^{re.escape(grant)}\n?", "", source)
            grants.append(grant)
    match = re.search(r'(?m)^oob\s*=\s*"[^"\n]+"', source)
    source = source[:match.start()] + "".join(line + "\n" for line in grants) + source[match.start():]
    convoy_pattern = r"(?m)^set_convoys\s*=\s*(\d+)[ \t]*$"
    if re.search(convoy_pattern, source):
        source = re.sub(convoy_pattern, lambda m: f"set_convoys = {max(navy.convoys, int(m[1]))}", source)
    else:
        source = source.rstrip() + f"\n\nset_convoys = {navy.convoys}\n"
    return source
