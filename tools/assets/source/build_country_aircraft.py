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


def airframe(family, role, tier):
    model = native.Model(f"{family}_{registry.PREFIXES[tier]}{role}")
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
