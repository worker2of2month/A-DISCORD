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
    "DEF": ((112, 126, 123), (50, 65, 66), (209, 215, 199)),
    "ARB": ((185, 151, 94), (89, 65, 41), (47, 94, 82)),
    "WRK": ((79, 98, 76), (40, 51, 47), (193, 77, 41)),
    "RUS": ((57, 66, 78), (29, 34, 43), (147, 44, 54)),
    "NAM": ((53, 102, 111), (29, 56, 63), (216, 164, 66)),
}


def prepare(output):
    from PIL import Image, ImageDraw
    from tools.assets.source.build_shl_palace import dds_bytes

    output.mkdir(parents=True, exist_ok=True)
    for family, (base, dark, accent) in PAINTS.items():
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
                if family == "ARB":
                    draw.ellipse((29, 25, 99, 101), fill=accent)
                    draw.ellipse((46, 17, 106, 86), fill=base)
                elif family == "WRK":
                    draw.polygon(((25, 32), (49, 32), (64, 68), (79, 32), (103, 32),
                                  (80, 101), (64, 85), (48, 101)), fill=accent)
                elif family == "RUS":
                    draw.polygon(((21, 52), (43, 69), (64, 28), (85, 69), (107, 52),
                                  (93, 99), (35, 99)), fill=accent)
                elif family == "NAM":
                    draw.polygon(((64, 23), (104, 64), (64, 105), (24, 64)), fill=accent)
                    draw.polygon(((64, 45), (83, 64), (64, 83), (45, 64)), fill=base)
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


def airframe(family, role, tier):
    model = native.Model(f"{family}_{registry.PREFIXES[tier]}{role}")
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
        for inset, size, tile in ((1.1, (.56, .45, .016), 8), (2.0, (.24, .70, .016), 6)):
            x = span - inset
            fraction = (x - .55) / (span - .55)
            local_chord = chord * (1 - fraction) + tip_chord * fraction
            y = root_y + sweep * fraction + local_chord * .5
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
            native.fin(model, side * 2.0, 4.7, .35, 1.7, 1.9, side * tier * .17)
            if side == 1:
                model.plate([(-2.05, 4.55, .37), (2.05, 4.55, .37),
                             (2.05, 5.8, .37), (-2.05, 5.8, .37)], .12, 1)
        else:
            native.wing(model, side, 2.8 if family == "ARB" else 2.4,
                        .45 + tier * .24, 3.35, 1.4, .65, z=.28, tile=1)
            if family in ("WRK", "RUS") or (family == "NAM" and tier > 0):
                native.fin(model, side * 1.45, 4.35, .34, 1.85, 1.9, side * .26 * tier)
            elif side == 1:
                native.fin(model, 0, 4.45, .3, 2.2, 2.0)
        if tier == 2 and family in ("RUS", "NAM"):
            native.wing(model, side, 2.1, .65, -4.15, 1.3, .40, z=.22, tile=1)
        if attack:
            for x in (3.2, 4.6, 5.65) if family == "WRK" else (3.3, 4.85):
                native.ordnance(model, side, x, .3 + (x - 3.3) * .2, tier)
            model.box((side * width * .85, -2.8, -.28), (.16, 2.5, .5), 1)
        else:
            model.rod((side * 2.9, -1.35, -.30), (side * 2.9, .45, -.30), .11, 4)
        model.rod((side * .35, nose + .9, -.34), (side * .35, nose - .18, -.34), .075, 3)
    model.box((0, 1.3, .65), (.15, .8, .22), 6)
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


def package(output, apply=False):
    report = json.loads((output / "verification.json").read_text())
    if set(report) != set(NAMES):
        raise ValueError("Build and verify every aircraft before packaging")
    files = {}
    for name, row in report.items():
        if row["source_hashes"] != source_hashes():
            raise ValueError(f"Rebuild {name}: authoring code changed")
        if native.digest(output / f"{name}.blend") != row["blend_sha256"]:
            raise ValueError(f"Scene changed after native verification: {name}")
        for filename, expected in row["files"].items():
            data = (output / filename).read_bytes()
            if hashlib.sha256(data).hexdigest() != expected:
                raise ValueError(f"Unverified export: {filename}")
            files[registry.DEST / filename] = data
    report_path = ROOT / "docs/development/model-verification/aircraft_verification.json"
    files[report_path] = (json.dumps(report, indent=2) + "\n").encode()
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
        prepare(output)
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
                native.render_preview(name)
    else:
        changed = package(output, args.apply)
        print(json.dumps({"changed": changed, "applied": args.apply}, indent=2))
        if args.check and changed:
            raise SystemExit(1)


if __name__ == "__main__":
    main()
