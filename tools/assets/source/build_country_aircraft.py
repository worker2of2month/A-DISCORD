"""Build shared and national aircraft using the native country-CAS exporter.

python -B -m tools.assets.source.build_country_aircraft --prepare
blender --background --factory-startup --python this_file -- --build
python -B -m tools.assets.source.build_country_aircraft --check
python -B -m tools.assets.source.build_country_aircraft --apply
python -B -m tools.assets.source.build_country_aircraft --check

Editable scenes, renders and native reimport reports stay in --output.
The package owns its named exports and delegates shared registries to their builder.
"""

import argparse
import hashlib
import json
import math
from pathlib import Path
import random
import sys


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.dont_write_bytecode = True

from tools.assets.source import build_country_cas as native
from tools.assets.source.country_vehicles import package_vehicles as registry


FAMILIES = registry.FAMILIES
NAMES = registry.SHARED_NAMES
PAINTS = {
    "SHL": ((187, 145, 92), (60, 47, 62), (214, 163, 74)),
    "DEF": ((112, 126, 123), (50, 65, 66), (209, 215, 199)),
    "ARB": ((185, 151, 94), (89, 65, 41), (47, 94, 82)),
    "WRK": ((79, 98, 76), (40, 51, 47), (193, 77, 41)),
    "RUS": ((57, 66, 78), (29, 34, 43), (147, 44, 54)),
    "NAM": ((91, 103, 91), (34, 44, 38), (184, 156, 88)),
    "IVN": ((113, 98, 72), (59, 55, 47), (185, 157, 100)),
    "MON": ((62, 78, 65), (33, 44, 38), (159, 169, 140)),
    "TVA": ((75, 87, 94), (44, 56, 63), (52, 118, 124)),
}


def prepare(output, names=None):
    from PIL import Image, ImageDraw
    from tools.assets.source.build_shl_palace import dds_bytes

    output.mkdir(parents=True, exist_ok=True)
    for family, (base, dark, accent) in PAINTS.items():
        if names and not any(name.startswith(family + "_") for name in names):
            continue
        palette = [base, dark, (22, 28, 31), (126, 134, 139), (184, 194, 190),
                   (44, 116, 146), accent, (19, 26, 30), base,
                   tuple(min(255, c + 20) for c in base), (177, 43, 31),
                   (143, 83, 45), (58, 63, 64), (214, 218, 206), (77, 89, 67), (214, 179, 75)]
        atlas = Image.new("RGBA", (512, 512))
        rng = random.Random("aircraft_" + family)
        for index, color in enumerate(palette):
            tile = Image.new("RGBA", (128, 128))
            pixels = []
            for y in range(128):
                for x in range(128):
                    wear = rng.gauss(0, 1.6) + 2.5 * math.sin(x * .055 + y * .023)
                    pixels.append(tuple(max(0, min(255, round(c + wear))) for c in color) + (255,))
            tile.putdata(pixels)
            draw = ImageDraw.Draw(tile)
            if index in (0, 1, 9):
                panel = tuple(round(c * .76) for c in color)
                for axis in (7, 63, 120):
                    draw.line((axis, 0, axis, 127), fill=panel)
                    draw.line((0, axis, 127, axis), fill=panel)
                for x in range(14, 120, 14):
                    for y in (10, 60, 117):
                        draw.point((x, y), fill=dark)
            if index == 5:
                for y in range(128):
                    draw.line((0, y, 127, y), fill=(27 + y // 8, 70 + y // 3, 99 + y // 3, 255))
            if index == 7:
                for y in range(0, 128, 10):
                    draw.line((0, y, 127, y), fill=(58, 64, 66), width=2)
            if index == 8:
                # Shared fleets use service markings instead of another country's flag.
                if family == "SHL":
                    draw.polygon(((64,9),(113,64),(64,119),(15,64)), fill=dark)
                    draw.line(((64,23),(99,64),(64,105),(29,64),(64,23)), fill=accent, width=6)
                    draw.line((40,64,88,64), fill=accent, width=4)
                    draw.line((64,38,64,90), fill=accent, width=4)
                    draw.ellipse((58,58,70,70), fill=(246,225,179))
                elif family == "ARB":
                    draw.ellipse((29, 25, 99, 101), fill=accent)
                    draw.ellipse((46, 17, 106, 86), fill=base)
                elif family == "WRK":
                    draw.polygon(((25, 32), (49, 32), (64, 68), (79, 32), (103, 32),
                                  (80, 101), (64, 85), (48, 101)), fill=accent)
                elif family == "RUS":
                    draw.polygon(((21, 52), (43, 69), (64, 28), (85, 69), (107, 52),
                                  (93, 99), (35, 99)), fill=accent)
                elif family == "NAM":
                    draw.polygon(((64, 12), (116, 64), (64, 116), (12, 64)), fill=(213, 222, 219))
                    draw.polygon(((64, 22), (106, 64), (64, 106), (22, 64)), fill=dark)
                    draw.ellipse((56, 32, 72, 48), outline=accent, width=5)
                    draw.line((64, 46, 64, 91), fill=accent, width=7)
                    draw.line((43, 58, 85, 58), fill=accent, width=5)
                    draw.arc((34, 54, 94, 98), 0, 180, fill=accent, width=7)
                    draw.polygon(((32, 74), (46, 80), (36, 88)), fill=accent)
                    draw.polygon(((96, 74), (82, 80), (92, 88)), fill=accent)
                elif family in ("IVN", "MON", "TVA"):
                    flag = Image.open(ROOT / f"gfx/flags/{family}.tga").convert("RGB")
                    tile.paste(flag.resize((104, 66), Image.Resampling.LANCZOS), (12, 31))
                else:
                    draw.line((24, 84, 64, 35, 104, 84), fill=accent, width=11)
            atlas.paste(tile, ((index % 4) * 128, (index // 4) * 128))
        maps = {
            "diffuse": atlas,
            "normal": Image.new("RGBA", atlas.size, (128, 128, 0, 128)),
            "specular": Image.new("RGBA", atlas.size, (0, 27, 0, 32)),
        }
        ImageDraw.Draw(maps["specular"]).rectangle((128, 128, 255, 255), fill=(0, 100, 0, 120))
        for role in ("fighter", "cas"):
            for channel, image in maps.items():
                (output / f"{family}_{role}_{channel}.dds").write_bytes(dds_bytes(image))


def naval_fin(model, x, y, z, height, chord, cant=0):
    model.plate([(x, y - chord * .50, z),
                 (x + cant, y + chord * .20, z + height),
                 (x + cant, y + chord * .52, z + height * .93),
                 (x, y + chord * .60, z)], .065, 0, axis=0)


def naval_stabilizer(model, side, z):
    model.plate([(side * .12, 3.12, z), (side * 2.30, 4.05, z + .08),
                 (side * 2.30, 4.53, z + .08), (side * .12, 4.43, z)], .075, 0)


def desert_airframe(model, role, tier):
    # Each station describes span, leading edge, trailing edge and dihedral.
    # Colour breaks follow the airfoil itself, including the sloping gull wings.
    attack = role == "cas"
    profiles = {
        ("fighter", 0): [(0.2, -2.31, .92, .03), (2.1, -2.08, .68, -.23), (4.8, -1.39, .69, .22),
                         (5.7, -.99, .58, .31), (6.45, -.38, .31, .38)],
        ("cas", 0): [(0.2, -1.75, 1.3, .18), (2.05, -1.9, 1.55, -.41), (5.9, -1.15, 1.23, .25),
                     (6.7, -.86, .99, .44), (7.25, -.4, .80, .55)],
        ("fighter", 1): [(.25, -3.15, 2.15, .03), (1.45, -1.95, 2.15, .03),
                         (4.3, .36, 2.47, .03), (5.65, 1.75, 2.84, .11), (6, 2.30, 2.9, .13)],
        ("cas", 1): [(.25, -1.95, 1.65, .1), (2.22, -1.64, 1.72, .22), (5.9, -2.02, .78, .42),
                     (6.64, -2.17, .43, .48), (6.95, -2.04, .12, .52)],
        ("fighter", 2): [(.25, -4.7, 3.22, .11), (2.18, -1.52, 3.22, .08), (4.1, .41, 3.74, .02),
                         (5.84, 1.18, 3.92, -.08), (6.6, 1.69, 3.48, -.15)],
        ("cas", 2): [(.2, -3.62, 2.36, .07), (2.36, -2.3, 3.02, .03), (5.75, -1.16, 1.75, .12),
                     (7.1, -.30, 2.39, .32), (8.18, 1.03, 2.84, .62)],
    }
    stations = profiles[role, tier]
    drone = attack and tier == 2
    radial_fighter = not attack and tier == 0
    booms = attack and tier == 1
    nose = -4.5 if drone else -5.0 if attack or radial_fighter else -6.35
    tail = 2.4 if drone or booms else 4.9
    w = 1.08 if drone else .85 if attack else .62
    model.loft([(nose, .065, .085, .01), (nose + .62, w * .59, .39, .04),
                (nose + 1.65, w * .94, .61, .07), (-.52, w, .68, .04),
                (1.18, w * .86, .58, .04), (tail, w * .22, .26, .07)], 0, sides=16)
    if drone:
        model.loft([(-3.38, .12, .12, .41), (-2.96, .49, .19, .54),
                    (-1.97, .51, .17, .68), (-1.58, .28, .12, .67)], 7)
        model.rod((0, -3.29, -.37), (0, -3.66, -.47), .28, 5, end_radius=.21)
    else:
        y = nose + (1.88 if radial_fighter else 1.30)
        model.loft([(y, .1, .09, .40), (y + .52, w * .60, .40, .58),
                    (y + 1.30, w * .78, .52, .66), (y + 2.1, w * .68, .38, .65),
                    (y + 2.64, .1, .10, .59)], 5, sides=12)
        for delta in (.79, 1.73):
            for sign in (-1, 1):
                model.rod((sign * w * .66, y + delta, .76), (0, y + delta + .10, 1.15), .038, 1)
    gun_x, gun_y, gun_z = (1.8, -2.68, -.16) if radial_fighter else (w * .38, nose + .20, -.17)
    for side in (-1, 1):
        for j, (a, b) in enumerate(zip(stations, stations[1:])):
            x, lead, trail, z = a
            xx, le, tr, zz = b
            color = (0, 0, 9, 1)[j]
            model.plate([(side * x, lead, z), (side * xx, le, zz), (side * xx, tr, zz),
                         (side * x, trail, z)], .135, color)
            if j in (1, 2):
                model.plate([(side * x, trail - .38, z + .079), (side * xx, tr - .28, zz + .079),
                             (side * xx, tr - .06, zz + .079), (side * x, trail - .06, z + .079)], .014, 1)
        x, lead, trail, z = stations[2]
        # Place the insignia on a broad panel immediately inboard of the coloured tip.
        x1, le, tr, z1 = stations[1]

        def marking_point(frac, chord):
            leading = le + (lead - le) * frac
            trailing = tr + (trail - tr) * frac
            return (side * (x1 + (x - x1) * frac), leading + (trailing - leading) * chord,
                    z1 + (z - z1) * frac + .078)
        model.plate([marking_point(f, c) for f, c in ((.51, .16), (.88, .16), (.88, .70), (.51, .70))], .008, 8)
        if radial_fighter:
            model.plate([(side * .08, 2.87, .20), (side * 1.38, 3.11, .24),
                         (side * 2.41, 3.85, .27), (side * 2.19, 4.29, .27),
                         (side * .13, 4.58, .20)], .103, 0)
            for j in range(4):
                y = -3.72 + .16 * j
                model.rod((side * .54, y, .16), (side * .72, y + .14, .10), .07, 11)
        elif tier == 0:
            native.engine(model, side * 2.05, -2.8, 1.78, -.30, 0, .57)
            native.wing(model, side, 2.63, .70, 3.03, 1.35, .57, z=.27, tile=1)
        else:
            ex = 2.14 if booms else 1.23 if drone else .82
            native.engine(model, side * ex, -1.88 if booms else -1.55,
                          2.71 if attack else 3.88, .37 if attack else .0, tier, .51 if attack else .43)
            if booms:
                model.loft([(-.4, .39, .45, .16), (2.2, .32, .32, .32),
                            (5.16, .17, .18, .55)], 0, x=side * ex)
                native.fin(model, side * ex, 4.45, .57, 1.43, 1.79, -side * .28)
            elif not drone and tier == 1:
                native.wing(model, side, 2.74, .78, 2.86, 1.45, .54, z=.61, tile=1)
            elif not drone:
                native.fin(model, side * 1.22, 2.86, .34, 1.42, 2.4, side * .81)
        if attack:
            for x, y in ((3.03, -.24), (4.48, -.36)):
                native.ordnance(model, side, x, y, tier)
        model.rod((side * gun_x, gun_y + .68, gun_z), (side * gun_x, gun_y, gun_z), .073, 3)
    if radial_fighter:
        model.loft([(-5.24, .60, .61, .045), (-5.04, .76, .76, .045),
                    (-4.62, .79, .78, .045), (-3.87, .70, .67, .045),
                    (-3.32, .56, .55, .055)], 9, sides=24)
        model.rod((0, -5.26, .045), (0, -5.23, .045), .59, 7, sides=24)
        for j in range(9):
            angle = math.tau * j / 9
            dx, dz = math.cos(angle), math.sin(angle)
            model.rod((dx * .21, -5.29, .045 + dz * .21),
                      (dx * .48, -5.29, .045 + dz * .48), .074, 3, sides=8)
        native.propeller(model, 0, -5.53, .045)
        model.rod((0, -5.54, .045), (0, -5.87, .045), .29, 1, end_radius=.038, sides=20)
        native.fin(model, 0, 3.85, .23, 1.64, 1.88)
    if booms:
        model.plate([(-2.22, 4.35, .70), (2.22, 4.35, .70), (2.22, 5.38, .70), (-2.22, 5.38, .70)], .11, 1)
    if (attack and tier == 0) or (not attack and tier == 1):
        native.fin(model, 0, 3.98, .29, 1.94, 2.31)
    model.locators = {"root": ((0, 0, 0), "vehicle_root"), "bomb": ((0, -.36, -.77), "vehicle_root"),
                      "gun1": ((-gun_x, gun_y, gun_z), "vehicle_root"),
                      "gun2": ((gun_x, gun_y, gun_z), "vehicle_root")}
    return model


def national_airframe(model, family, role, tier):
    # Root, break and tip stations set span, leading edge, trailing edge and height.
    wings = {
        ("TVA", "fighter"): (
            ((0.28, -1.74, 1.05, -0.16), (2.06, -1.63, 0.93, -0.49), (5.68, -0.87, 0.23, 0.28)),
            ((0.38, -2.64, 1.24, 0.02), (2.80, -0.96, 1.58, 0.04), (5.46, 1.02, 2.05, 0.20)),
            ((0.36, -3.94, 2.19, -0.13), (2.77, -0.71, 2.55, -0.10), (5.64, 1.45, 2.91, 0.03)),
        ),
        ("TVA", "cas"): (
            ((0.45, -2.05, 1.46, -0.09), (3.14, -1.96, 1.35, -0.06), (6.68, -1.14, 0.86, 0.27)),
            ((0.46, -1.65, 1.59, 0.22), (3.04, -1.08, 1.72, 0.23), (7.10, 0.08, 1.47, 0.36)),
            ((0.43, -2.69, 1.79, -0.07), (3.26, -1.75, 2.30, -0.07), (6.87, 0.49, 2.41, 0.18)),
        ),
        ("IVN", "fighter"): (
            ((0.38, -1.6, 1.0, -0.26), (3.15, -1.78, 0.62, -0.29), (5.95, -0.99, 0.42, 0.13)),
            ((0.36, -2.65, 1.70, -0.28), (2.42, -1.01, 2.12, -0.15), (5.20, 1.68, 2.65, 0.06)),
            ((0.40, -4.22, 3.72, -0.16), (2.72, -0.55, 3.57, -0.12), (6.0, 2.92, 3.82, 0.18)),
        ),
        ("IVN", "cas"): (
            ((0.38, -1.22, 1.65, 0.36), (3.16, -1.39, 1.58, 0.34), (7.22, -1.08, 0.72, 0.66)),
            ((0.40, -1.94, 1.69, 0.20), (3.14, -1.23, 1.88, 0.15), (7.0, -0.54, 1.47, -0.16)),
            ((0.40, -2.63, 2.68, 0.14), (3.08, -1.75, 2.27, 0.16), (7.40, -0.12, 1.66, 0.42)),
        ),
        ("MON", "fighter"): (
            ((0.36, -1.65, 1.35, -0.18), (3.30, -1.40, 0.98, -0.09), (5.87, -0.70, 0.24, 0.24)),
            ((0.32, -2.02, 1.66, -0.05), (2.60, -0.66, 2.05, 0.02), (5.55, 1.19, 2.20, 0.20)),
            ((0.28, -4.85, 3.15, 0.02), (2.68, -1.42, 2.52, 0.08), (6.80, 2.16, 3.10, 0.20)),
        ),
        ("MON", "cas"): (
            ((0.34, -1.83, 1.33, 0.79), (2.01, -1.91, 1.06, 0.80), (7.14, -1.51, 0.30, 0.96)),
            ((0.36, -2.14, 2.00, 0.32), (2.56, -0.74, 2.23, 0.33), (6.69, -1.48, 0.16, 0.54)),
            ((0.38, -1.37, 1.94, 0.07), (3.16, -0.93, 2.10, 0.15), (6.47, 0.28, 1.63, 0.41)),
        ),
    }
    specs = {
        # Nose, stern, fuselage radius, canopy station, tail and engine layout.
        ("TVA", "fighter"): (
            (-4.69, 4.37, 0.60, -1.49, "swept", "tractor"),
            (-5.46, 4.58, 0.76, -3.62, "high", "chin"),
            (-7.26, 5.05, 0.75, -4.81, "twin", "close"),
        ),
        ("TVA", "cas"): (
            (-4.12, 4.90, 0.89, -1.76, "oval", "radial"),
            (-5.62, 5.36, 0.91, -3.99, "high", "outboard"),
            (-6.38, 4.99, 0.98, -4.67, "swept", "dorsal"),
        ),
        ("IVN", "fighter"): (
            (-4.43, 4.82, 0.66, -1.53, "round", "radial"),
            (-6.10, 4.73, 0.66, -3.52, "swept", "side"),
            (-7.08, 4.06, 0.76, -4.42, "canard", "close"),
        ),
        ("IVN", "cas"): (
            (-4.87, 5.22, 0.94, -2.86, "twin", "wingprop"),
            (-5.35, 5.13, 0.98, -3.36, "high", "dorsal"),
            (-5.15, 2.18, 1.05, -3.34, "booms", "outboard"),
        ),
        ("MON", "fighter"): (
            (-4.95, 4.99, 0.63, -1.51, "oval", "tractor"),
            (-5.89, 5.03, 0.68, -3.40, "swept", "single"),
            (-6.82, 3.21, 0.85, -4.24, "winglets", "embedded"),
        ),
        ("MON", "cas"): (
            (-4.29, 4.40, 0.83, -1.98, "fan", "radial"),
            (-4.97, 2.52, 0.82, -3.34, "booms", "wingjet"),
            (-5.46, 5.25, 0.92, -3.71, "swept", "shoulder"),
        ),
    }
    nose, stern, width, cockpit, tail, engine = specs[family, role][tier]
    attack = role == "cas"
    depth = 0.76 if attack else 0.59
    model.loft(
        [
            (nose, 0.08, 0.10, 0),
            (nose + 0.58, width * 0.55, depth * 0.58, 0.01),
            (cockpit + 0.64, width, depth, 0.08),
            (0.16, width * 0.97, depth * 0.95, 0.06),
            (stern * 0.65, width * 0.62, depth * 0.65, 0.12),
            (stern, 0.18, 0.22, 0.18),
        ],
        0,
        sides=16,
    )
    canopy_width = width * (0.78 if attack else 0.72)
    canopy_length = 2.62 if attack else 1.94
    canopy_z = depth * 0.81
    model.loft(
        [
            (cockpit, 0.12, 0.09, canopy_z),
            (cockpit + 0.48, canopy_width, 0.33, canopy_z + 0.15),
            (cockpit + canopy_length * 0.59, canopy_width, 0.43, canopy_z + 0.19),
            (cockpit + canopy_length, 0.11, 0.09, canopy_z + 0.07),
        ],
        5,
        sides=14,
    )
    for side in (-1, 1):
        model.rod(
            (side * canopy_width * 0.95, cockpit + 0.62, canopy_z + 0.15),
            (0, cockpit + 0.73, canopy_z + 0.54),
            0.046,
            1,
        )
        if tier == 0:
            y = cockpit + canopy_length * 0.59
            model.rod(
                (side * canopy_width, y, canopy_z + 0.20),
                (side * canopy_width * 0.66, y, canopy_z + 0.53),
                0.052,
                1,
            )
            model.rod((side * canopy_width * 0.66, y, canopy_z + 0.53), (0, y, canopy_z + 0.63), 0.052, 1)
    if engine == "radial":
        native.engine(model, 0, nose - 0.28, nose + 1.60, 0, 0, width * 1.05)
    elif engine == "tractor":
        model.loft(
            [
                (nose + 0.08, 0.30, 0.35, 0),
                (nose + 0.48, 0.41, 0.46, 0.015),
                (nose + 1.08, 0.54, 0.53, 0.025),
                (nose + 1.78, 0.55, 0.50, 0.03),
            ],
            0,
            sides=18,
        )
        native.propeller(model, 0, nose + 0.01, 0)
        model.loft(
            [
                (nose - 0.39, 0.035, 0.035, 0),
                (nose - 0.25, 0.22, 0.22, 0),
                (nose - 0.04, 0.32, 0.32, 0),
                (nose + 0.04, 0.32, 0.32, 0),
            ],
            9,
            sides=18,
        )
    elif engine in ("single", "chin"):
        native.engine(model, 0, -0.32, stern - 0.04, -0.12, 1, 0.59)
        if engine == "chin":
            model.loft(
                [(nose + 0.32, 0.37, 0.25, -0.22), (nose + 0.95, 0.50, 0.35, -0.26),
                 (-2.10, 0.54, 0.33, -0.27), (-0.22, 0.36, 0.24, -0.23)],
                0,
            )
            model.rod((0, nose + 0.33, -0.22), (0, nose + 0.29, -0.22), 0.23, 7)
    if family == "IVN" and tier == 2 and not attack:
        model.loft(
            [
                (-2.91, 0.14, 0.12, 0.50),
                (-1.82, 0.42, 0.35, 0.62),
                (0.65, 0.38, 0.26, 0.60),
                (2.10, 0.15, 0.10, 0.44),
            ],
            1,
            sides=12,
        )
    if tail == "oval":
        y = stern - 0.91
        model.plate(
            [
                (0, y - 1.18, 0.16),
                (0, y - 0.62, 1.14),
                (0, y - 0.36, 1.72),
                (0, y - 0.02, 1.92),
                (0, y + 0.44, 1.91),
                (0, y + 0.73, 1.61),
                (0, y + 0.83, 0.71),
                (0, y + 0.72, 0.18),
            ],
            0.14,
            0,
            axis=0,
        )
    elif tail in ("round", "fan", "swept", "high"):
        heights = {"round": 1.61, "fan": 2.12, "swept": 2.31, "high": 2.08}
        height = heights[tail]
        chord = 2.12 if tail != "fan" else 2.70
        y = stern - 0.80
        model.plate(
            [
                (0, y - chord * 0.72, 0.19),
                (0, y - 0.21, height * 0.83),
                (0, y + 0.13, height),
                (0, y + chord * 0.45, height * 0.91),
                (0, y + chord * 0.54, 0.25),
            ],
            0.14,
            0,
            axis=0,
        )
        model.box((0, y + 0.29, height * 0.81), (0.16, 0.66, 0.15), 6)
    stations = wings[family, role][tier]
    for side in (-1, 1):
        for j, (a, b) in enumerate(zip(stations, stations[1:])):
            points = []
            for x, lead, rear, z in (a, b):
                chord = rear - lead
                points.extend(
                    [
                        (side * x, lead, z),
                        (side * x, lead + chord * 0.30, z + 0.13),
                        (side * x, rear, z + 0.012),
                        (side * x, lead + chord * 0.33, z - 0.065),
                    ]
                )
            model.solid(
                points,
                [(3, 2, 1, 0), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)],
                0 if j == 0 else 9,
            )
            if j == 1:

                def surface(f, c):
                    x, lead, rear, z = [v + (w - v) * f for v, w in zip(a, b)]
                    return side * x, lead + (rear - lead) * c, z + 0.13 - (c - 0.30) * 0.118 / 0.70 + 0.014

                for start, end, tile in ((0.43, 0.62, 8), (0.78, 0.85, 6)):
                    model.plate(
                        [surface(start, 0.34), surface(end, 0.34), surface(end, 0.74), surface(start, 0.74)],
                        0.012,
                        tile,
                    )
                model.plate(
                    [surface(0.12, 0.79), surface(0.92, 0.79), surface(0.92, 0.95), surface(0.12, 0.95)],
                    0.012,
                    1,
                )
        if engine == "wingprop":
            native.engine(model, side * 2.30, -3.0, 1.62, 0.23, 0, 0.63)
        elif engine not in ("radial", "tractor", "single", "chin"):
            x, start, end, z, r = {
                "side": (0.71, -2.92, 3.75, -0.02, 0.42),
                "close": (0.66, -1.49, 4.02, -0.11, 0.48),
                "dorsal": (1.20, 0.06, 3.83, 0.68, 0.55),
                "outboard": (2.54, -1.96, 2.30, 0.26, 0.52),
                "shoulder": (0.86, -2.20, 3.48, -0.10, 0.44),
                "wingjet": (2.15, -2.13, 2.02, 0.12, 0.56),
                "embedded": (0.82, -1.10, 2.91, 0.16, 0.42),
            }[engine]
            native.engine(model, side * x, start, end, z, tier, r)
        if tail == "booms":
            x = side * (2.54 if family == "IVN" else 2.15)
            model.loft(
                [
                    (-0.45, 0.30, 0.36, 0.22),
                    (1.17, 0.37, 0.35, 0.27),
                    (3.81, 0.23, 0.24, 0.44),
                    (5.27, 0.105, 0.15, 0.51),
                ],
                0,
                x=x,
            )
            naval_fin(model, x, 4.48, 0.53, 1.55, 1.68, side * 0.23)
            if side == 1:
                model.plate([(-x, 4.43, 0.58), (x, 4.43, 0.58), (x, 5.42, 0.58), (-x, 5.42, 0.58)], 0.10, 1)
        elif tail == "winglets":
            x, lead, rear, z = stations[2]
            naval_fin(
                model, side * (x - 0.26), lead + 0.42, z + 0.06, 0.92 if attack else 0.65, 1.14, side * 0.32
            )
        else:
            if tail in ("canard", "twin"):
                naval_fin(model, side * (1.68 if attack else 0.98), stern - 0.82, 0.34, 1.66, 1.78, side * 0.43)
            if tail == "canard":
                native.wing(model, side, 2.52, 0.79, -3.91, 1.03, 0.39, z=0.24, tile=1)
            else:
                tail_z = 1.92 if tail == "high" else 0.31
                if side == 1:
                    model.plate(
                        [
                            (-0.57, stern - 1.82, tail_z),
                            (0.57, stern - 1.82, tail_z),
                            (0.57, stern - 0.44, tail_z),
                            (-0.57, stern - 0.44, tail_z),
                        ],
                        0.17,
                        1,
                    )
                native.wing(
                    model,
                    side,
                    2.69,
                    0.56,
                    stern - 1.82,
                    1.38,
                    0.64,
                    z=tail_z,
                    tile=1,
                )
        if attack:
            # Hang the stores just below the actual wing station, including the parasol wing.
            a, b = stations[1:]
            for f in (0.20, 0.62):
                x, lead, rear, z = [v + (w - v) * f for v, w in zip(a, b)]
                y = lead + (rear - lead) * 0.43
                if z > 0.14:
                    model.box((side * x, y + 0.17, z * 0.5), (0.14, 0.65, z + 0.05), 1)
                native.ordnance(model, side, x, y, tier)
        if engine == "tractor":
            for offset in (0.93, 1.16, 1.39, 1.62):
                model.rod(
                    (side * 0.46, nose + offset, 0.12),
                    (side * 0.56, nose + offset + 0.10, 0.10),
                    0.069,
                    12,
                    sides=8,
                )
        if family == "MON" and engine == "radial":
            model.rod((side * 0.63, -0.14, -0.28), (side * 3.43, -0.70, 0.82), 0.063, 1)
        if family == "IVN":
            for vent in range(4):
                y = nose + 1.65 + vent * 0.16
                model.plate(
                    [
                        (side * width * 0.86, y, 0.12),
                        (side * width * 0.86, y + 0.07, 0.12),
                        (side * width * 0.92, y + 0.18, -0.17),
                        (side * width * 0.92, y + 0.10, -0.17),
                    ],
                    0.025,
                    7,
                    axis=0,
                )
            if tail == "canard":
                model.plate(
                    [
                        (side * 0.45, -3.68, 0.07),
                        (side * 1.08, -2.81, 0.23),
                        (side * 1.24, -0.68, 0.11),
                        (side * 0.68, -1.20, -0.13),
                    ],
                    0.08,
                    1,
                )
        # Keep the fuselage marking visible in profile as well as the top view.
        model.plate(
            [
                (side * width * 0.97, -0.14, 0.25),
                (side * width * 0.97, 0.67, 0.25),
                (side * width * 0.97, 0.67, -0.10),
                (side * width * 0.97, -0.14, -0.10),
            ],
            0.022,
            8,
            axis=0,
        )
    model.locators = {
        "root": ((0, 0, 0), "vehicle_root"),
        "bomb": ((0, -0.3, -0.88), "vehicle_root"),
        "gun1": ((-0.38, nose + 0.12, -0.24), "vehicle_root"),
        "gun2": ((0.38, nose + 0.12, -0.24), "vehicle_root"),
    }
    return model


def airframe(family, role, tier):
    model = native.Model(f"{family}_{registry.PREFIXES[tier]}{role}")
    if family in ("IVN", "MON", "TVA"):
        return national_airframe(model, family, role, tier)
    if family == "SHL":
        return desert_airframe(model, role, tier)
    attack = role == "cas"
    width = {"DEF": .70, "ARB": .82, "WRK": .94, "RUS": .88, "NAM": .66}[family]
    width *= 1.12 if attack else 1
    nose = -6.6 if family == "RUS" else -5.8
    tail = 5.35 if family != "NAM" else 4.7
    boom = family == "NAM" and attack
    aft = 2.25 if boom else tail
    model.loft([(nose, .10, .13, 0), (nose + .8, width * .64, .51, 0),
                (-3.5, width, .69, 0), (-1.1, width, .73, 0),
                (1.45, width * .77, .58, .05), (aft, .16, .20, .16)], 0,
               sides=10 if tier < 2 else 8)
    model.loft([(-4.5, .15, .14, .56), (-3.7, width * .63, .42, .71),
                (-2.45, width * .62, .48, .72), (-1.8, .16, .11, .65)], 5, sides=8)
    for y in (-3.6, -2.55):
        model.rod((-width * .58, y, .83), (0, y, 1.19), .042, 1)
        model.rod((0, y, 1.19), (width * .58, y, .83), .042, 1)
    span = {"DEF": 5.8, "ARB": 7.2, "WRK": 6.65, "RUS": 6.3, "NAM": 6.0}[family]
    span += .9 if attack else 0
    span += tier * .24
    sweep = (.25, 1.7, 2.7)[tier]
    if family == "ARB":
        sweep *= .65
    elif family == "RUS":
        sweep += .6
    root_y = -1.65
    chord = (2.45, 3.05, 3.85)[tier] + (.4 if attack else 0)
    tip_chord = 1.25 if family in ("ARB", "WRK") else .65
    for side in (-1, 1):
        native.wing(model, side, span, sweep, root_y, chord, tip_chord, z=.05)
        # Keep each marking on the local wing surface as sweep and span change.
        markings = ((1.1, (.56, .45, .016), 8),) if family == "NAM" else (
            (1.1, (.56, .45, .016), 8), (2.0, (.24, .70, .016), 6))
        for inset, size, tile in markings:
            x = span - inset
            fraction = (x - .55) / (span - .55)
            local_chord = chord * (1 - fraction) + tip_chord * fraction
            y = root_y + sweep * fraction + local_chord * .5
            if family == "NAM":
                z = .05 + .15 * fraction + .087
                model.plate([(side * x - size[0] / 2, y - size[1] / 2, z),
                             (side * x + size[0] / 2, y - size[1] / 2, z),
                             (side * x + size[0] / 2, y + size[1] / 2, z),
                             (side * x - size[0] / 2, y + size[1] / 2, z)], .002, tile)
            else:
                model.box((side * x, y, .05 + .15 * fraction + .1), size, tile)
        model.box((side * span, root_y + sweep + tip_chord * .5, .22),
                  (.15, .25, .13), 10 if side < 0 else 5)
        twin = attack or family in ("WRK", "RUS", "NAM")
        if tier == 0:
            if twin:
                engine_x = side * (2.55 if family == "ARB" else 2.0)
                native.engine(model, engine_x, -3.5, .8, .05, tier, .58)
            elif side == 1:
                native.engine(model, 0, nose - .1, -4.4, 0, tier, .53)
        else:
            engine_x = side * (1.65 if family == "WRK" else 1.15)
            native.engine(model, engine_x, -1.9, 3.35, -.03, tier, .52 if attack else .42)
            model.box((engine_x, -1.8, -.1), (.58, .12, .5), 7)
        if boom:
            model.loft([(-2.1, .28, .31, .06), (1.0, .30, .32, .1),
                        (5.65, .14, .17, .25)], 0, x=side * 2.0)
            naval_fin(model, side * 2.0, 4.65, .25, 1.35, 2.05, side * tier * .12)
            if side == 1:
                model.plate([(-2.05, 4.55, .37), (2.05, 4.55, .37),
                             (2.05, 5.8, .37), (-2.05, 5.8, .37)], .12, 1)
        else:
            if family == "NAM":
                naval_stabilizer(model, side, .15)
                if tier > 0:
                    naval_fin(model, side * 1.12, 3.85, .06, 1.45, 2.15, side * .20)
                elif side == 1:
                    naval_fin(model, 0, 3.98, .18, 1.65, 2.2)
            else:
                native.wing(model, side, 2.8 if family == "ARB" else 2.4,
                            .45 + tier * .24, 3.35, 1.4, .65, z=.28, tile=1)
            if family in ("WRK", "RUS"):
                native.fin(model, side * 1.45, 4.35, .34, 1.85, 1.9, side * .26 * tier)
            elif family != "NAM" and side == 1:
                native.fin(model, 0, 4.45, .3, 2.2, 2.0)
        if tier == 2 and family == "RUS":
            native.wing(model, side, 2.1, .65, -4.15, 1.3, .40, z=.22, tile=1)
        if attack:
            for x in (3.2, 4.6, 5.65) if family == "WRK" else (3.3, 4.85):
                native.ordnance(model, side, x, .3 + (x - 3.3) * .2, tier)
            model.box((side * width * .85, -2.8, -.28), (.16, 2.5, .5), 1)
        else:
            model.rod((side * 2.9, -1.35, -.30), (side * 2.9, .45, -.30), .11, 4)
        model.rod((side * .35, nose + .9, -.34), (side * .35, nose - .18, -.34), .075, 3)
    model.box((0, 1.3, .65), (.10, .55, .13) if family == "NAM" else (.15, .8, .22),
              1 if family == "NAM" else 6)
    if family == "NAM":
        # The stowed arrestor hook stays within the airframe's flying envelope.
        model.rod((0, 1.4, -.54), (0, 3.5, -.67), .065, 3)
        model.rod((0, 3.5, -.67), (0, 3.7, -.51), .075, 3)
        for side in (-1, 1):
            fold_x = span * .63
            fraction = (fold_x - .55) / (span - .55)
            fold_y = root_y + sweep * fraction
            fold_chord = chord * (1 - fraction) + tip_chord * fraction
            model.box((side * fold_x, fold_y + fold_chord * .5, .18),
                      (.055, fold_chord * .84, .035), 3)
    if tier > 0:
        model.loft([(-4.95, .12, .16, -.49), (-4.6, .24, .22, -.52),
                    (-4.2, .13, .12, -.46)], 7, sides=8)
    model.locators = {
        "root": ((0, 0, 0), "vehicle_root"),
        "gun1": ((-.35, nose - .18, -.34), "vehicle_root"),
        "gun2": ((.35, nose - .18, -.34), "vehicle_root"),
        "bomb": ((0, -.3, -.85), "vehicle_root"),
    }
    return model


def source_hashes():
    paths = (Path(__file__), Path(native.__file__), Path(registry.__file__))
    return {str(path.relative_to(ROOT)).replace("\\", "/"): native.digest(path) for path in paths}


def package(output, apply=False, names=None):
    selected = set(names or NAMES)
    families = {name.split("_")[0] for name in selected}
    if selected != {name for name in NAMES if name.split("_")[0] in families}:
        raise ValueError("Package complete families: all tiers share their role textures")
    report = json.loads((output / "verification.json").read_text())
    if not selected.issubset(report):
        raise ValueError("Build and verify every aircraft before packaging")
    files = {}
    for name in sorted(selected):
        row = report[name]
        if row["source_hashes"] != source_hashes():
            raise ValueError(f"Rebuild {name}: authoring code changed")
        if native.digest(output / f"{name}.blend") != row["blend_sha256"]:
            raise ValueError(f"Scene changed after native verification: {name}")
        for filename, expected in row["files"].items():
            data = (output / filename).read_bytes()
            if hashlib.sha256(data).hexdigest() != expected:
                raise ValueError(f"Unverified export: {filename}")
            files[registry.DEST / filename] = data
        if name.startswith("NAM_"):
            files[ROOT / "tools/assets/source/country_vehicles" / f"{name}.blend"] = (
                output / f"{name}.blend"
            ).read_bytes()
    report_path = ROOT / "docs/development/model-verification/aircraft_verification.json"
    installed = json.loads(report_path.read_text()) if report_path.is_file() else {}
    installed.update({name: report[name] for name in sorted(selected)})
    files[report_path] = (json.dumps(installed, indent=2) + "\n").encode()
    changed = [str(path.relative_to(ROOT)) for path, data in files.items()
               if not path.is_file() or path.read_bytes() != data]
    registry_changes = registry.package(False)
    if apply:
        for path, data in files.items():
            if str(path.relative_to(ROOT)) in changed:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
        registry.package(True)
    return changed + registry_changes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    for option in ("prepare", "build", "render", "check", "apply"):
        action.add_argument("--" + option, action="store_true")
    parser.add_argument("--output", type=Path, default=ROOT / "work/country-aircraft")
    parser.add_argument("--names", nargs="+", choices=NAMES)
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else None)
    output = args.output.resolve()
    if args.prepare:
        prepare(output, args.names)
    elif args.build or args.render:
        import bpy
        import bmesh
        from mathutils import Matrix, Vector
        from tools.assets.source.build_shl_palace import load_exporter

        native.bpy = bpy
        native.bmesh = bmesh
        native.Matrix = Matrix
        native.Vector = Vector
        native.pdx = load_exporter()
        from io_pdx_mesh import pdx_data

        native.pdx_data = pdx_data
        native.SOURCE = output
        report_path = output / "verification.json"
        report = json.loads(report_path.read_text()) if report_path.is_file() else {}
        for name in args.names or NAMES:
            family, *middle, role = name.split("_")
            prefix = middle[0] + "_" if middle else ""
            tier = registry.PREFIXES.index(prefix)
            if args.build:
                report[name] = native.export_model(family, tier, role, airframe(family, role, tier))
                report[name]["source_hashes"] = source_hashes()
                report_path.write_text(json.dumps(report, indent=2) + "\n")
                print("VERIFIED", name, report[name]["triangles"], flush=True)
            if args.render:
                folder = "NAM_naval" if family == "NAM" else f"{family}_aircraft"
                preview = ROOT / "docs/development/previews" / folder
                preview.mkdir(parents=True, exist_ok=True)
                native.render_preview(name, preview)
    else:
        changed = package(output, args.apply, args.names)
        print(json.dumps({"changed": changed, "applied": args.apply}, indent=2))
        if args.check and changed:
            raise SystemExit(1)


if __name__ == "__main__":
    main()
