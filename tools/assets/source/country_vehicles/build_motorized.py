"""Build national wheeled APCs, then check/apply the verified native package.

python -B -m tools.assets.source.country_vehicles.build_motorized --prepare
blender --background --factory-startup --threads 4 --python this_file -- --build
python -B -m tools.assets.source.country_vehicles.build_motorized --check
python -B -m tools.assets.source.country_vehicles.build_motorized --apply
python -B -m tools.assets.source.country_vehicles.build_motorized --check

The shared vehicle packager owns entity bindings. Renders are disposable.
"""

import argparse
import hashlib
import json
import math
from pathlib import Path
import random
import sys
import tempfile
from types import SimpleNamespace

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
SOURCE = Path(__file__).parent
STAGE = Path(tempfile.gettempdir()) / "adiscord-country-apc"
DEST = ROOT / "gfx/models/units/ADISCORD_country_vehicles"
PREVIEWS = ROOT / "docs/development/previews/country-apc"
REPORT = ROOT / "docs/development/model-verification/country_apc.json"
TAGS = ("VAL", "STP", "STS", "NAM", "NOD")
CLIPS = ("idle", "move", "attack")
# The native motorized frame parks its vehicle at this yaw in every attack frame.
# Counter-rotate the turret so the barrel follows the escort's combat heading.
ATTACK_TURRET_YAW = math.radians(54.57114218169362)
PAINTS = {
    "VAL": ((77, 94, 112), (39, 49, 61), (185, 194, 199)),
    "STP": ((88, 96, 64), (44, 52, 37), (188, 184, 150)),
    "STS": ((67, 88, 99), (34, 47, 58), (167, 196, 197)),
    "NAM": ((172, 148, 105), (98, 80, 55), (221, 199, 151)),
    "NOD": ((51, 65, 66), (30, 41, 43), (164, 166, 153)),
}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_changed(path, data):
    if not path.is_file() or path.read_bytes() != data:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)


def native_files(name):
    return [f"{name}.mesh", *[f"{name}_{clip}.anim" for clip in CLIPS],
            *[f"{name}_{channel}.dds" for channel in ("diffuse", "normal", "specular")]]


def prepare(tags=TAGS):
    from PIL import Image, ImageDraw
    from tools.assets.source.build_shl_palace import dds_bytes

    for tag in tags:
        base, dark, accent = PAINTS[tag]
        marking = {"STP": "STS", "STS": "NOD"}.get(tag, tag)
        palette = [base, dark, (23, 25, 25), (105, 113, 113), accent,
                   (34, 63, 75), accent, (15, 20, 21), base,
                   tuple(min(255, c + 18) for c in base), (140, 35, 27),
                   (99, 77, 50), (55, 57, 52), (207, 199, 155), (75, 80, 60), base]
        atlas = Image.new("RGBA", (512, 512))
        rng = random.Random("apc_" + tag)
        for index, color in enumerate(palette):
            tile = Image.new("RGBA", (128, 128))
            pixels = []
            for y in range(128):
                for x in range(128):
                    noise = rng.gauss(0, 1.6)
                    pixels.append(tuple(max(0, min(255, round(c + noise))) for c in color) + (255,))
            tile.putdata(pixels)
            draw = ImageDraw.Draw(tile)
            if index in (0, 1, 9):
                draw.rectangle((4, 4, 123, 123), outline=dark, width=2)
                for x in (10, 63, 117):
                    for y in (10, 117):
                        draw.ellipse((x, y, x + 2, y + 2), fill=accent)
                for _ in range(25):
                    x, y = rng.randrange(128), rng.randrange(128)
                    draw.line((x, y, x + 3, y + 1), fill=dark)
            if index == 5:
                draw.polygon(((8, 108), (8, 27), (119, 6), (119, 24)), fill=(85, 115, 127))
            if index == 7:
                for y in range(8, 128, 10):
                    draw.line((0, y, 128, y), fill=(52, 58, 57), width=2)
            if index == 8:
                if marking == "VAL":
                    draw.polygon(((25, 94), (64, 24), (103, 94), (82, 94), (64, 60), (46, 94)), fill=accent)
                elif marking == "STP":
                    points = []
                    for i in range(10):
                        angle = -math.pi / 2 + i * math.pi / 5
                        radius = 43 if i % 2 == 0 else 19
                        points.append((64 + radius * math.cos(angle), 64 + radius * math.sin(angle)))
                    draw.polygon(points, fill=accent)
                elif marking == "NAM":
                    draw.polygon(((64, 21), (107, 64), (64, 107), (21, 64)), fill=accent)
                    draw.polygon(((64, 43), (85, 64), (64, 85), (43, 64)), fill=base)
                elif marking == "NOD":
                    # Recognition bands keep small side panels readable.
                    for x in (24, 66):
                        draw.polygon(((x, 108), (x + 24, 20), (x + 41, 20), (x + 17, 108)), fill=accent)
                else:
                    draw.line((30, 30, 30, 96, 97, 96), fill=accent, width=12)
                    draw.line((97, 30, 58, 69), fill=accent, width=12)
            atlas.paste(tile, ((index % 4) * 128, (index // 4) * 128))
        specular = Image.new("RGBA", atlas.size, (0, 25, 0, 32))
        ImageDraw.Draw(specular).rectangle((128, 128, 255, 255), fill=(0, 80, 0, 95))
        for channel, texture in {
            "diffuse": atlas,
            "normal": Image.new("RGBA", atlas.size, (128, 128, 0, 128)),
            "specular": specular,
        }.items():
            write_changed(STAGE / f"{tag}_apc_{channel}.dds", dds_bytes(texture))


def wheel(model, side, y, index, radius, half_track):
    x, z = side * half_track, radius + .05
    bone = model.bone(f"wheel_{side}_{index}", (x, y, z))
    model.rod((x - .23, y, z), (x + .23, y, z), radius, 2, bone, sides=20)
    outer = x + side * .245
    model.rod((outer, y, z), (outer + side * .07, y, z), radius * .57, 1, bone, sides=16)
    model.rod((outer + side * .075, y, z), (outer + side * .13, y, z), radius * .24, 3, bone)
    for i in range(20):
        angle = i * math.tau / 20
        rotation = Matrix.Rotation(angle, 3, "X")
        center = Vector((x, y, z)) + rotation @ Vector((0, 0, radius))
        model.box(center, (.46, .14, .055), 12, bone, rotation)
    for i in range(6):
        angle = i * math.tau / 6
        model.rod((outer + side * .075, y + radius * .39 * math.sin(angle), z + radius * .39 * math.cos(angle)),
                  (outer + side * .105, y + radius * .39 * math.sin(angle), z + radius * .39 * math.cos(angle)),
                  .045, 3, bone, sides=6)
    return bone


def chassis(model, body, axles, radius, half_track, front, rear):
    model.box((0, (front + rear) / 2, .77), (1.65, rear - front - .5, .30), 1, body)
    model.wheels = [wheel(model, side, y, i, radius, half_track)
                    for side in (-1, 1) for i, y in enumerate(axles)]
    for y in axles:
        model.rod((-half_track, y, radius), (half_track, y, radius), .12, 12, body)
    model.locators = {
        "root": ((0, 0, 0), "vehicle_root"),
        "left_wheel": ((-half_track, axles[-1], .15), "vehicle_root"),
        "right_wheel": ((half_track, axles[-1], .15), "vehicle_root"),
    }


def hatch(model, body, center, width=.75, length=.85):
    x, y, z = center
    model.box(center, (width, length, .09), 1, body)
    model.box((x, y, z + .055), (width - .08, length - .08, .04), 9, body)
    model.rod((x - .16, y, z + .14), (x + .16, y, z + .14), .03, 3, body)


def headlamp(model, body, x, y, z):
    model.rod((x, y + .08, z), (x, y, z), .15, 1, body)
    model.rod((x, y - .01, z), (x, y - .025, z), .105, 13, body)


def gun_barrel(model, gun, x, start_y, end_y, z, radius):
    model.rod((x, start_y, z), (x, end_y, z), radius, 12, gun)
    model.rod((x, end_y + .12, z), (x, end_y - .05, z), radius * 1.35, 3, gun)
    model.rod((x, end_y - .055, z), (x, end_y - .065, z), radius * .78, 7, gun)
    model.locators["barrel"] = ((x, end_y - .07, z), gun)


def val_vehicle(model, body):
    # The low continuous roof and overlapping skirts define the wedge profile.
    hull(model, [(.60, 2.0, -3.10, 3.15, .32),
                 (1.25, 3.05, -3.90, 3.50, .55),
                 (1.86, 2.55, -2.20, 3.20, .32)], 0, body)
    chassis(model, body, (-2.55, -1.05, .85, 2.35), .64, 1.48, -3.90, 3.50)
    for side in (-1, 1):
        for y in (-2.05, -.65, .75, 2.15):
            model.plate([(side * 1.60, y - .66, 1.66),
                         (side * 1.60, y + .66, 1.66),
                         (side * 1.60, y + .51, 1.02),
                         (side * 1.60, y - .48, 1.13)], .14, 9, body, axis=0)
        model.box((side * 1.30, 2.42, 1.69), (.06, .61, .30), 8, body)
        model.box((side * .65, -2.27, 1.83), (.59, .17, .09), 5, body)
        headlamp(model, body, side * 1.10, -3.55, 1.36)
        model.box((side * .96, 3.36, 1.42), (.25, .08, .12), 10, body)
        hatch(model, body, (side * .60, 2.15, 1.92), .88, 1.18)
    model.box((0, 3.40, 1.35), (1.65, .12, .96), 1, body)
    model.box((0, 3.48, 1.35), (1.46, .05, .79), 9, body)
    for y in (-1.96, -1.78, -1.60, -1.42):
        model.box((.72, y, 1.91), (.82, .07, .04), 7, body)
    turret = model.bone("turret", (0, .15, 1.87), body)
    gun = model.bone("gun", (0, -.96, 2.20), turret)
    model.rod((0, .15, 1.84), (0, .15, 2.01), .77, 1, turret, sides=16)
    hull(model, [(2.00, 2.12, -1.13, 1.16, .46),
                 (2.38, 1.42, -.71, .91, .31)], 9, turret)
    model.box((0, -1.02, 2.20), (.40, .54, .24), 1, gun)
    gun_barrel(model, gun, 0, -1.25, -3.07, 2.20, .064)
    model.box((.75, .10, 2.37), (.30, .55, .26), 1, turret)
    model.box((.75, -.19, 2.39), (.23, .035, .13), 5, turret)
    model.box((0, .83, 2.33), (.96, .35, .08), 1, turret)
    model.rod((-.89, 2.78, 1.88), (-.89, 2.78, 2.72), .018, 3, body)


def nod_vehicle(model, body):
    # A short four-wheel chassis carries a raised cabin and a rear drum turret.
    hull(model, [(.65, 1.90, -2.37, 2.34, .16),
                 (1.31, 2.45, -2.83, 2.74, .22),
                 (1.78, 2.28, -2.40, 2.62, .16)], 0, body)
    chassis(model, body, (-1.86, 1.78), .86, 1.29, -2.83, 2.74)
    hull(model, [(1.58, 2.27, -1.92, 2.61, .14),
                 (2.52, 2.02, -1.35, 2.47, .16)], 0, body)
    model.box((0, -2.72, 1.41), (1.33, .12, .44), 7, body)
    for x in (-.48, -.24, 0, .24, .48):
        model.box((x, -2.79, 1.41), (.05, .035, .41), 4, body)
    for side in (-1, 1):
        model.box((side * .50, -1.57, 2.22), (.78, .07, .37), 5, body,
                  Matrix.Rotation(-.54, 3, "X"))
        model.box((side * 1.105, -.76, 2.02), (.055, .87, .81), 9, body)
        model.box((side * 1.14, -.84, 2.28), (.035, .62, .26), 5, body)
        model.box((side * 1.19, -.42, 1.93), (.04, .18, .045), 4, body)
        model.box((side * 1.11, 1.45, 2.09), (.07, 1.13, .59), 8, body)
        model.box((side * 1.17, .47, 1.76), (.10, 3.55, .09), 4, body)
        for y in (-1.86, 1.78):
            model.box((side * 1.33, y, 1.80), (.70, 1.87, .13), 1, body)
        model.box((side * 1.31, -.02, 1.01), (.48, 1.13, .12), 12, body)
        headlamp(model, body, side * .97, -2.63, 1.65)
    model.box((0, 2.62, 1.81), (1.20, .12, 1.16), 1, body)
    model.rod((.73, 2.73, 1.87), (.73, 2.99, 1.87), .52, 2, body, sides=20)
    model.rod((.73, 3.0, 1.87), (.73, 3.04, 1.87), .27, 4, body)
    hatch(model, body, (-.40, -.50, 2.57), .72, .75)
    turret = model.bone("turret", (0, 1.08, 2.51), body)
    gun = model.bone("gun", (0, .31, 2.91), turret)
    model.rod((0, 1.08, 2.51), (0, 1.08, 2.66), .86, 1, turret, sides=20)
    model.rod((0, 1.08, 2.64), (0, 1.08, 3.19), .78, 0, turret, end_radius=.70, sides=20)
    model.rod((0, 1.08, 3.19), (0, 1.08, 3.25), .73, 4, turret, sides=20)
    model.rod((0, 1.21, 3.25), (0, 1.21, 3.43), .37, 1, turret, sides=12)
    model.rod((0, 1.21, 3.43), (0, 1.21, 3.48), .40, 4, turret, sides=12)
    model.box((0, .35, 2.91), (.45, .28, .35), 1, gun)
    gun_barrel(model, gun, 0, .23, -.80, 2.91, .10)
    for side in (-1, 1):
        model.box((side * .70, 1.06, 3.03), (.04, .28, .09), 7, turret)
    model.rod((-.83, 2.16, 2.52), (-.83, 2.16, 3.23), .025, 3, body)


def stp_vehicle(model, body):
    # The engine hood, driver's cab and troop box remain separate masses.
    hull(model, [(.65, 1.86, -3.25, 2.94, .15),
                 (1.22, 2.45, -3.57, 3.24, .22)], 1, body)
    chassis(model, body, (-2.48, .91, 2.38), .76, 1.38, -3.57, 3.24)
    hull(model, [(1.18, 2.22, -3.54, -1.31, .17),
                 (1.84, 1.73, -3.28, -1.25, .15)], 0, body)
    model.box((0, -3.48, 1.52), (1.43, .10, .52), 7, body)
    for x in (-.55, -.28, 0, .28, .55):
        model.box((x, -3.55, 1.52), (.055, .055, .47), 12, body)
    hull(model, [(1.20, 2.43, -1.49, .11, .13),
                 (2.63, 2.01, -1.02, .06, .10)], 0, body)
    hull(model, [(1.18, 2.47, -.02, 3.24, .10),
                 (2.37, 2.40, -.02, 3.18, .10)], 0, body)
    for side in (-1, 1):
        model.box((side * .49, -1.16, 2.27), (.80, .07, .43), 5, body,
                  Matrix.Rotation(-.32, 3, "X"))
        model.box((side * 1.10, -.62, 2.26), (.045, .65, .39), 5, body)
        model.box((side * 1.19, -.61, 1.72), (.07, .91, .57), 9, body)
        for y in (.45, 1.48, 2.58):
            model.box((side * 1.25, y, 1.81), (.10, .09, 1.09), 1, body)
        model.box((side * 1.26, 1.92, 2.11), (.04, .60, .30), 8, body)
        model.box((side * 1.40, 1.64, 1.64), (.47, 3.05, .12), 12, body)
        model.box((side * 1.40, -2.48, 1.63), (.54, 1.90, .12), 12, body)
        model.box((side * 1.32, -.67, .94), (.51, 1.0, .12), 12, body)
        headlamp(model, body, side * .96, -3.43, 1.61)
        model.box((side * .65, 3.23, 1.79), (1.04, .10, 1.01), 9, body)
        model.box((side * .76, 2.54, 2.61), (.65, .83, .43), 14, body)
        model.box((side * .76, 2.54, 2.84), (.09, .85, .04), 11, body)
    model.rod((-1.25, .07, 1.55), (-1.25, .07, 2.89), .095, 12, body)
    model.rod((-1.25, .07, 2.89), (-1.25, .31, 2.89), .095, 12, body)
    model.box((0, -3.62, 1.00), (2.70, .20, .21), 12, body)
    turret = model.bone("turret", (0, 1.02, 2.37), body)
    gun = model.bone("gun", (0, .56, 2.99), turret)
    model.rod((0, 1.02, 2.38), (0, 1.02, 2.48), .60, 12, turret, sides=12)
    model.rod((0, 1.02, 2.47), (0, 1.02, 3.03), .14, 12, turret)
    model.box((0, 1.35, 2.65), (.44, .44, .11), 2, turret)
    model.plate([(-.76, .51, 2.64), (.76, .51, 2.64), (.70, .51, 3.27),
                 (.22, .51, 3.27), (.22, .51, 2.91), (-.22, .51, 2.91),
                 (-.22, .51, 3.27), (-.70, .51, 3.27)], .10, 0, turret, axis=1)
    for side in (-1, 1):
        model.box((side * .73, .99, 2.96), (.09, .90, .59), 9, turret)
    model.box((0, .94, 2.99), (.24, .76, .20), 12, gun)
    gun_barrel(model, gun, 0, .60, -.67, 2.99, .052)
    model.box((.31, .99, 2.93), (.37, .47, .30), 11, gun)
    model.rod((.98, 2.05, 2.38), (.98, 2.05, 3.22), .022, 3, body)


def nam_vehicle(model, body):
    # The wide boat bow and long side floats give the amphibious hull its outline.
    hull(model, [(.61, 1.55, -2.60, 2.94, .40),
                 (1.22, 2.90, -4.05, 3.54, .90),
                 (2.01, 2.76, -2.83, 3.33, .59)], 0, body)
    chassis(model, body, (-2.12, -.73, .73, 2.12), .59, 1.40, -4.05, 3.54)
    for side in (-1, 1):
        x = side * 1.53
        model.plate([(x, -3.37, 1.54), (x, -2.47, 2.00),
                     (x, 2.98, 2.00), (x, 3.53, 1.60),
                     (x, 2.93, 1.21), (x, -2.77, 1.21)], .49, 1, body, axis=0)
        model.box((side * 1.79, .18, 1.67), (.04, 4.81, .10), 6, body)
        model.box((side * 1.79, 2.27, 1.70), (.045, .62, .44), 8, body)
        model.box((side * .53, -2.24, 2.10), (.77, .82, .20), 1, body)
        model.box((side * .53, -2.67, 2.12), (.62, .05, .12), 5, body)
        headlamp(model, body, side * 1.13, -2.94, 1.93)
        model.rod((side * .95, 3.38, 1.07), (side * .95, 3.80, 1.07), .30, 12, body, sides=16)
        model.rod((side * .95, 3.81, 1.07), (side * .95, 3.83, 1.07), .23, 7, body, sides=16)
        for angle in (0, math.pi / 2):
            model.box((side * .95, 3.85, 1.07), (.43, .04, .055), 3, body,
                      Matrix.Rotation(angle, 3, "Y"))
    model.plate([(-1.04, -3.25, 1.70), (1.04, -3.25, 1.70),
                 (.89, -2.76, 1.98), (-.89, -2.76, 1.98)], .07, 9, body)
    hatch(model, body, (-.65, -.55, 2.06), .88, 1.20)
    for y in (2.53, 2.72, 2.91, 3.10):
        model.box((0, y, 2.06), (1.57, .09, .06), 7, body)
    model.box((0, 3.42, 1.69), (1.03, .12, .76), 9, body)
    turret = model.bone("turret", (.20, 1.02, 2.02), body)
    gun = model.bone("gun", (.20, .01, 2.53), turret)
    model.rod((.20, 1.02, 2.02), (.20, 1.02, 2.23), .74, 1, turret, sides=16)
    start = len(model.vertices)
    hull(model, [(2.20, 1.52, -.11, 2.15, .26),
                 (2.87, .95, .47, 1.98, .18)], 0, turret)
    for index in range(start, len(model.vertices)):
        x, y, z = model.vertices[index]
        model.vertices[index] = (x + .20, y, z)
    model.box((-.78, 1.09, 2.64), (.54, 1.36, .50), 1, turret)
    model.box((-.78, .39, 2.67), (.39, .05, .27), 5, turret)
    model.box((.88, 1.43, 2.64), (.41, 1.14, .36), 9, turret)
    model.box((.20, 1.65, 2.91), (.61, .62, .10), 1, turret)
    model.box((.20, .06, 2.53), (.43, .54, .33), 1, gun)
    gun_barrel(model, gun, .20, -.18, -1.59, 2.53, .075)
    for y in (.70, 1.0, 1.3):
        model.rod((1.04, y, 2.69), (1.22, y - .19, 2.91), .09, 12, turret, sides=8)
    model.rod((1.02, 2.20, 2.01), (1.02, 2.20, 3.18), .021, 3, body)
    model.rod((.73, 2.30, 2.01), (.73, 2.30, 2.87), .018, 3, body)


def sts_vehicle(model, body):
    # Three evenly spaced axles support a continuous hull and a narrow roof.
    hull(model, [(.62, 1.86, -2.75, 2.82, .24),
                 (1.30, 2.88, -3.43, 3.28, .48),
                 (1.94, 2.68, -2.94, 3.12, .35),
                 (2.30, 2.18, -1.75, 2.86, .23)], 0, body)
    chassis(model, body, (-2.16, 0, 2.16), .78, 1.47, -3.43, 3.28)
    for side in (-1, 1):
        # Separate angled mudguards leave the large wheels exposed.
        x = side * 1.48
        for y in (-2.16, 0, 2.16):
            model.plate([(x, y - 1.02, 1.32), (x, y - .74, 1.76),
                         (x, y + .74, 1.76), (x, y + 1.02, 1.32),
                         (x, y + .89, 1.31), (x, y + .66, 1.63),
                         (x, y - .66, 1.63), (x, y - .89, 1.31)], .54, 1, body, axis=0)
        model.box((side * .54, -1.84, 2.30), (.55, .16, .13), 1, body)
        model.box((side * .54, -1.93, 2.31), (.43, .035, .075), 5, body)
        headlamp(model, body, side * 1.08, -3.13, 1.65)
        model.box((side * 1.08, -3.05, 1.84), (.45, .37, .07), 1, body)
        model.rod((side * .84, -3.38, 1.11), (side * .84, -3.59, 1.11), .07, 3, body)
        model.box((side * 1.29, 1.96, 2.06), (.24, 1.48, .37), 1, body)
        model.box((side * 1.42, 1.96, 2.06), (.035, 1.23, .26), 8, body)
        model.box((side * .98, 3.17, 1.64), (.20, .075, .14), 10, body)
        hatch(model, body, (side * .51, 1.89, 2.35), .72, 1.04)
    # A deep rear ramp and roof hatches mark the troop compartment.
    model.box((0, 3.18, 1.52), (1.59, .14, 1.12), 1, body)
    model.box((0, 3.26, 1.55), (1.38, .055, .90), 9, body)
    for x in (-.58, .58):
        model.box((x, 3.30, 1.13), (.17, .07, .24), 12, body)
    model.rod((-.23, 3.31, 1.90), (.23, 3.31, 1.90), .03, 3, body)
    hatch(model, body, (-.52, -1.17, 2.35), .65, .71)
    for y in (-1.40, -1.21, -1.02, -.83):
        model.box((.55, y, 2.35), (.61, .09, .045), 7, body)
    model.box((1.22, 2.47, 2.28), (.19, .65, .21), 12, body)
    model.rod((1.23, 2.73, 2.33), (1.23, 3.11, 2.43), .09, 12, body)
    turret = model.bone("turret", (0, .12, 2.30), body)
    gun = model.bone("gun", (0, -.67, 2.80), turret)
    model.rod((0, .12, 2.31), (0, .12, 2.47), .69, 1, turret, sides=16)
    hull(model, [(2.46, 1.77, -.77, 1.02, .24),
                 (3.03, 1.11, -.38, .79, .19)], 9, turret)
    for side in (-1, 1):
        model.box((side * .71, .19, 2.66), (.29, 1.13, .31), 0, turret)
        for y in (.08, .30, .52):
            model.rod((side * .82, y, 2.82), (side * 1.0, y - .11, 3.02), .073, 12, turret, sides=8)
    model.box((0, -.69, 2.80), (.51, .41, .33), 1, gun)
    gun_barrel(model, gun, 0, -.88, -2.64, 2.80, .067)
    model.box((0, -1.10, 2.80), (.22, .48, .19), 0, gun)
    model.box((-.41, -.14, 3.10), (.30, .45, .24), 1, turret)
    model.box((-.41, -.38, 3.12), (.21, .035, .12), 5, turret)
    model.box((.24, .39, 3.05), (.44, .47, .07), 1, turret)
    model.rod((-.89, 2.62, 2.30), (-.89, 2.62, 3.36), .020, 3, body)


def vehicle(tag):
    model = native.Model(f"{tag}_apc")
    body = model.bone("hull", (0, 0, 1.5))
    builders = {"VAL": val_vehicle, "STP": stp_vehicle,
                "STS": sts_vehicle, "NAM": nam_vehicle, "NOD": nod_vehicle}
    builders[tag](model, body)
    return model


def animate(model, rig, clip):
    if clip == "idle":
        from tools.assets.source.country_vehicles.build_idle import export_idle

        export_idle(rig, model.name, STAGE / f"{model.name}_idle.anim", pdx)
        return
    rig.animation_data_clear()
    for bone in rig.pose.bones:
        bone.matrix_basis = Matrix.Identity(4)
        bone.rotation_mode = "XYZ"
    scene = bpy.context.scene
    end = 61 if clip == "move" else 31
    scene.frame_start, scene.frame_end = 1, end
    scene.render.fps = 30
    for frame in range(1, end + 1):
        t = (frame - 1) / (end - 1)
        for name in model.wheels:
            rig.pose.bones[name].rotation_euler.x = math.tau * 2 * t if clip == "move" else 0
        rig.pose.bones["hull"].location.z = .025 * math.sin(math.tau * 2 * t) if clip == "move" else 0
        recoil = max(0, 1 - abs(t - .1) / .1) if clip == "attack" else 0
        rig.pose.bones["turret"].rotation_euler.z = ATTACK_TURRET_YAW if clip == "attack" else 0
        rig.pose.bones["gun"].location.y = .15 * recoil
        for bone in rig.pose.bones:
            bone.keyframe_insert("location", frame=frame)
            bone.keyframe_insert("rotation_euler", frame=frame)
    scene.frame_set(1)
    bpy.context.view_layer.objects.active = rig
    pdx.export_animfile(str(STAGE / f"{model.name}_{clip}.anim"), frame_start=1, frame_end=end)
    rig.animation_data.action.name = f"{model.name}_{clip}"
    rig.animation_data.action.use_fake_user = True


def export(tag):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    name = f"{tag}_apc"
    material = pdx.create_shader(SimpleNamespace(
        shader=["PdxMeshAdvanced"], diff=[f"{name}_diffuse.dds"],
        n=[f"{name}_normal.dds"], spec=[f"{name}_specular.dds"],
    ), name, str(STAGE))
    model = vehicle(tag)
    obj, rig = model.object(material)
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    for empty in [o for o in bpy.context.scene.objects if o.type == "EMPTY"]:
        empty.select_set(True)
    bpy.context.view_layer.objects.active = obj
    path = STAGE / f"{name}.mesh"
    pdx.export_meshfile(str(path), exp_selected=True)
    tree = pdx_data.read_meshfile(str(path))
    for mesh in tree.findall("./object/*/mesh"):
        skin = mesh.find("skin")
        indices, weights = skin.attrib["ix"], skin.attrib["w"]
        assert all(weights[i:i + 4] == [1, 0, 0, 0] for i in range(0, len(weights), 4))
        skin.set("bones", [1])
        # All four matrix indices are dereferenced by the native shader.
        skin.set("ix", [indices[i - i % 4] for i in range(len(indices))])
        mesh.attrib["ta"] = [round(value, 5) for value in mesh.attrib["ta"]]
    pdx_data.write_meshfile(str(path), tree)
    for clip in CLIPS:
        animate(model, rig, clip)
    rig.animation_data.action = bpy.data.actions[f"{name}_idle"]
    bpy.context.scene.frame_set(1)
    native.preview_materials()
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.file.pack_all()
    bpy.ops.wm.save_as_mainfile(filepath=str(STAGE / f"{name}.blend"))


def verify(tag):
    name = f"{tag}_apc"
    path = STAGE / f"{name}.mesh"
    tree = pdx_data.read_meshfile(str(path))
    report = {"triangles": 0, "vertices": 0, "materials": 0}
    for shape in tree.find("object"):
        bones = list(shape.find("skeleton"))
        report["bones"] = len(bones)
        assert 0 < len(bones) <= 50
        for mesh in shape.findall("mesh"):
            data = pdx_data.PDXData(mesh)
            count = len(data.p) // 3
            assert 0 < count < 65536
            assert len(data.n) == count * 3 and len(data.u0) == count * 2
            assert len(data.ta) == count * 4
            assert all(math.isfinite(v) for v in data.p + data.n + data.u0 + data.ta)
            assert all(0 <= v <= 1 for v in data.u0)
            assert len(data.tri) % 3 == 0 and min(data.tri) >= 0 and max(data.tri) < count
            points = [Vector(data.p[i:i + 3]) for i in range(0, len(data.p), 3)]
            assert all((points[b] - points[a]).cross(points[c] - points[a]).length > 1e-9
                       for a, b, c in zip(data.tri[::3], data.tri[1::3], data.tri[2::3]))
            assert data.skin.bones == [1]
            assert len(data.skin.w) == len(data.skin.ix) == count * 4
            for i in range(count):
                assert data.skin.w[i * 4:i * 4 + 4] == [1, 0, 0, 0]
                assert all(0 <= b < len(bones) for b in data.skin.ix[i * 4:i * 4 + 4])
            assert data.material.shader == ["PdxMeshAdvanced"]
            for channel in ("diff", "n", "spec"):
                assert (STAGE / getattr(data.material, channel)[0]).read_bytes()[:4] == b"DDS "
            report["triangles"] += len(data.tri) // 3
            report["vertices"] += count
            report["materials"] += 1
    assert report["triangles"] < 16000 and report["materials"] == 1
    report["locators"] = [loc.tag for loc in tree.find("locator")]
    assert {"root", "barrel", "left_wheel", "right_wheel"} <= set(report["locators"])
    report["animations"] = {}
    for clip in CLIPS:
        bpy.ops.wm.read_factory_settings(use_empty=True)
        pdx.import_meshfile(str(path), join_materials=False)
        pdx.import_animfile(str(STAGE / f"{name}_{clip}.anim"))
        objects = [o for o in bpy.context.scene.objects if o.type == "MESH"]
        rig = next(o for o in bpy.context.scene.objects if o.type == "ARMATURE")
        end = bpy.context.scene.frame_end
        samples, poses = [], []
        for frame in sorted({1, 2, 1 + round((end - 1) * .1), max(2, end // 4), end // 2, end}):
            bpy.context.scene.frame_set(frame)
            graph = bpy.context.evaluated_depsgraph_get()
            points = [o.matrix_world @ v.co for o in objects for v in o.evaluated_get(graph).data.vertices]
            assert all(math.isfinite(c) for p in points for c in p)
            assert max(p.length for p in points) < 12
            samples.append(points)
            poses.append({bone.name: bone.matrix.copy() for bone in rig.pose.bones})
        motion = max((a - b).length for points in samples[1:] for a, b in zip(samples[0], points))
        loop_error = max((a - b).length for a, b in zip(samples[0], samples[-1]))
        assert loop_error < .001, (name, clip, loop_error)
        metrics = {"max_vertex_motion": motion, "loop_error": loop_error}
        if clip == "attack":
            # Compose the native wrapper yaw with the reimported gun transform.
            wrapper = Matrix.Rotation(-ATTACK_TURRET_YAW, 3, "Z")
            forward = Vector((0, -1, 0))
            error = max((wrapper @ (pose["gun"].to_3x3() @ forward)).angle(forward)
                        for pose in poses)
            assert error < .001, (name, "combat heading", error)
            metrics["combat_heading_error_degrees"] = math.degrees(error)
        if clip == "idle":
            assert motion > .05, (name, clip, motion)
        if clip != "idle":
            assert motion > .10, (name, clip, motion)
            prefix = "wheel_" if clip == "move" else "gun"
            selected = [n for n in poses[0] if n.startswith(prefix)]
            for bone in selected:
                if clip == "attack":
                    delta = max((pose[bone].translation - poses[0][bone].translation).length
                                for pose in poses[1:])
                else:
                    delta = max(abs(a - b) for pose in poses[1:]
                                for row0, row1 in zip(poses[0][bone], pose[bone]) for a, b in zip(row0, row1))
                assert delta > .10, (name, clip, bone, delta)
            metrics["moving_bones"] = selected
        report["animations"][clip] = metrics
    report["native_reimport"] = True
    report["rigid_skin_slots_validated"] = True
    report["hoi4_runtime_verified"] = False
    report["files"] = {f: digest(STAGE / f) for f in native_files(name)}
    report["blend_sha256"] = digest(STAGE / f"{name}.blend")
    return report


def render(tag):
    name = f"{tag}_apc"
    bpy.ops.wm.read_factory_settings(use_empty=True)
    pdx.import_meshfile(str(STAGE / f"{name}.mesh"), join_materials=False)
    native.preview_materials()
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.samples = 32
    scene.cycles.use_denoising = True
    scene.render.resolution_x, scene.render.resolution_y = 1100, 800
    scene.render.resolution_percentage = 100
    scene.world = bpy.data.worlds.new("APC studio")
    scene.world.use_nodes = True
    scene.world.node_tree.nodes["Background"].inputs[0].default_value = (.12, .15, .19, 1)
    scene.world.node_tree.nodes["Background"].inputs[1].default_value = .7
    scene.view_settings.view_transform = "AgX"
    target = Vector((0, 0, 1.35))
    bpy.ops.object.camera_add(location=(10, -13, 8))
    camera = bpy.context.object
    camera.rotation_euler = (target - camera.location).to_track_quat("-Z", "Y").to_euler()
    camera.data.type, camera.data.ortho_scale = "ORTHO", 9.5
    scene.camera = camera
    for location, power in (((-6, -10, 12), 2200), ((8, -3, 8), 1500), ((-5, 9, 10), 2800)):
        bpy.ops.object.light_add(type="AREA", location=location)
        lamp = bpy.context.object
        lamp.data.energy, lamp.data.size = power, 7
        lamp.rotation_euler = (target - lamp.location).to_track_quat("-Z", "Y").to_euler()
    scene.render.image_settings.file_format = "PNG"
    PREVIEWS.mkdir(parents=True, exist_ok=True)
    scene.render.filepath = str(PREVIEWS / f"{name}.png")
    bpy.ops.render.render(write_still=True)


def package(apply=False):
    report_path = STAGE / REPORT.name
    if not report_path.is_file():
        raise FileNotFoundError("Build and verify the APC package in Blender first")
    report = json.loads(report_path.read_text())
    assert report["generator_sha256"] == digest(Path(__file__)), "Rebuild after generator edits"
    assert report["idle_generator_sha256"] == digest(SOURCE / "build_idle.py"), "Rebuild after idle edits"
    files = {REPORT: report_path.read_bytes()}
    for tag in TAGS:
        name = f"{tag}_apc"
        row = report["models"][name]
        assert set(row["files"]) == set(native_files(name))
        for filename, expected in row["files"].items():
            assert digest(STAGE / filename) == expected
            files[DEST / filename] = (STAGE / filename).read_bytes()
        blend = STAGE / f"{name}.blend"
        assert digest(blend) == row["blend_sha256"]
        files[SOURCE / blend.name] = blend.read_bytes()
    changed = [str(path.relative_to(ROOT)) for path, data in files.items()
               if not path.is_file() or path.read_bytes() != data]
    if apply:
        for path, data in files.items():
            write_changed(path, data)
    print(json.dumps({"changed": changed, "applied": apply}, indent=2))
    return changed


def stage_preserved_models(tags):
    """Keep unselected exports byte-identical and validate their installed report."""
    if set(tags) == set(TAGS):
        return {}
    installed = json.loads(REPORT.read_text())["models"]
    preserved = {}
    for tag in TAGS:
        if tag in tags:
            continue
        name = f"{tag}_apc"
        row = installed[name]
        for filename, expected in row["files"].items():
            assert digest(DEST / filename) == expected, f"Installed export changed: {filename}"
            write_changed(STAGE / filename, (DEST / filename).read_bytes())
        blend = SOURCE / f"{name}.blend"
        assert digest(blend) == row["blend_sha256"], f"Installed scene changed: {blend.name}"
        write_changed(STAGE / blend.name, blend.read_bytes())
        preserved[name] = row
    return preserved


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_mutually_exclusive_group(required=True)
    for action in ("prepare", "build", "check", "apply"):
        actions.add_argument("--" + action, action="store_true")
    parser.add_argument("--tag", choices=TAGS, action="append",
                        help="Prepare/build selected models; preserve other verified exports")
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else None)
    tags = args.tag or TAGS
    if args.tag and not (args.prepare or args.build):
        parser.error("--tag is only valid with --prepare or --build")
    if args.prepare:
        prepare(tags)
    elif args.build:
        global bpy, bmesh, Matrix, Vector, pdx, pdx_data, native, hull
        import bpy
        import bmesh
        from mathutils import Matrix, Vector
        from tools.assets.source import build_country_cas as native
        from tools.assets.source.build_shl_palace import load_exporter
        from tools.assets.source.build_taran import hull
        pdx = load_exporter()
        from io_pdx_mesh import pdx_data
        native.bpy, native.bmesh, native.Matrix, native.Vector = bpy, bmesh, Matrix, Vector
        report = {"generator_sha256": digest(Path(__file__)),
                  "idle_generator_sha256": digest(SOURCE / "build_idle.py"),
                  "models": stage_preserved_models(tags)}
        for tag in tags:
            export(tag)
            report["models"][f"{tag}_apc"] = verify(tag)
            render(tag)
        write_changed(STAGE / REPORT.name, (json.dumps(report, indent=2) + "\n").encode())
        print(json.dumps(report, indent=2), flush=True)
    elif package(args.apply) and args.check:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
