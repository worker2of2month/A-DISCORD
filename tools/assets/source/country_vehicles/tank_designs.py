"""National tank silhouettes. Lengths are in scene units, along the local Y axis."""

from typing import NamedTuple


class Design(NamedTuple):
    turret: str
    suspension: str
    fittings: str
    wheels: int
    length: float
    deck: float
    turret_y: float
    reach: float


# An empty medium slot uses the country's existing animated tank.
DESIGNS = {
    "NAM": (
        Design("drum", "floats", "aerial", 4, 5.4, 1.37, 0.67, 3.1),
        Design("boat", "bogies", "lockers", 6, 7.1, 1.65, -0.66, 5.2),
        Design("terrace", "floats", "bridge", 8, 8.1, 1.88, -0.20, 5.9),
    ),
    "SHL": (
        Design("needle", "open", "roll", 4, 5.6, 1.30, -0.78, 4.0),
        None,
        Design("citadel", "scales", "canopy", 7, 8.0, 1.88, 0.34, 6.2),
    ),
    "STP": (
        Design("oscillating", "bogies", "lockers", 6, 5.5, 1.39, -0.54, 4.2),
        None,
        Design("dome", "slabs", "drums", 7, 8.5, 1.74, -0.80, 6.4),
    ),
    "STS": (
        Design("box", "open", "signal", 5, 5.4, 1.58, 0.76, 3.15),
        Design("terrace", "scales", "lockers", 6, 7.3, 1.70, -0.72, 5.5),
        Design("monitor", "bogies", "stacks", 8, 8.4, 1.88, 0.40, 5.4),
    ),
    "SRP": (
        Design("dome", "open", "drums", 4, 5.1, 1.41, -0.74, 3.65),
        Design("box", "bogies", "roll", 8, 6.9, 1.57, 0.61, 4.8),
        Design("citadel", "slabs", "signal", 6, 7.8, 1.82, -0.91, 5.7),
    ),
    "VAL": (
        Design("boat", "scales", "signal", 5, 5.9, 1.34, 0.34, 4.3),
        None,
        Design("wedge", "slabs", "bridge", 8, 8.6, 1.56, 0.66, 6.8),
    ),
    "NOD": (
        Design("needle", "slabs", "signal", 5, 5.8, 1.20, 0.62, 4.35),
        None,
        Design("monitor", "scales", "split", 7, 8.0, 1.64, -0.40, 6.4),
    ),
    "RUS": (
        Design("dome", "bogies", "roll", 6, 5.4, 1.27, 0.25, 3.8),
        Design("oscillating", "open", "drums", 5, 7.2, 1.49, -0.91, 5.35),
        Design("terrace", "open", "drums", 7, 8.0, 1.79, -0.86, 6.5),
    ),
    "IVN": (
        Design("box", "bogies", "stacks", 4, 5.1, 1.61, -0.80, 3.45),
        Design("monitor", "slabs", "signal", 6, 6.8, 1.78, 0.42, 4.7),
        Design("citadel", "bogies", "split", 8, 8.4, 2.02, 0.56, 5.95),
    ),
    "MON": (
        Design("oscillating", "open", "aerial", 4, 5.3, 1.42, 0.92, 3.35),
        Design("dome", "scales", "canopy", 6, 6.8, 1.61, -0.41, 5.2),
        Design("boat", "open", "bridge", 6, 7.8, 1.69, -0.58, 6.15),
    ),
    "WRK": (
        Design("monitor", "open", "lockers", 5, 5.35, 1.46, -0.66, 3.55),
        Design("citadel", "slabs", "stacks", 5, 6.6, 1.71, 0.12, 4.95),
        Design("box", "scales", "twin", 7, 8.2, 1.94, -0.68, 6.1),
    ),
}

CLASSES = ("light", "medium", "heavy")


def model_name(tag, kind):
    if DESIGNS[tag][CLASSES.index(kind)] is None:
        return f"{tag}_tank"
    return f"{tag}_{kind}_tank"


TANK_EQUIPMENT = {
    "light": (
        "ADISCORD_recon_platform_archetype",
        "ADISCORD_light_combat_platform_2163",
        "ADISCORD_recon_drone_carrier_2170",
    ),
    "medium": (
        "ADISCORD_combat_platform_archetype",
        "ADISCORD_combat_platform_2150",
        "ADISCORD_combat_platform_2170",
        "ADISCORD_combat_platform_2183",
        "ADISCORD_combat_platform_2200",
    ),
    "heavy": (
        "ADISCORD_heavy_platform_archetype",
        "ADISCORD_heavy_combat_platform_2158",
        "ADISCORD_heavy_combat_platform_2183",
        "ADISCORD_heavy_combat_platform_2200",
    ),
}
