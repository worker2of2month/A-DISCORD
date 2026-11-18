"""Build in a temporary directory with Blender --python this_file -- --build --game GAME.

Run --prepare with system Python first. After export, --check and --apply install
the staged geometry, animation and side views. Edit the installed PNGs directly
when retouching art. Regeneration of the vehicle registries is independent.
Blender --verify reimports the installed meshes and samples their three clips.
"""

import argparse
import hashlib
import json
import math
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
sys.dont_write_bytecode = True
from tools.assets.source.country_vehicles.tank_designs import CLASSES, DESIGNS, model_name
from tools.assets.source.build_taran import hull

STAGE = Path(tempfile.gettempdir()) / "adiscord-tank-families"
DEST = ROOT / "gfx/models/units/ADISCORD_country_vehicles"
CARDS = ROOT / "gfx/interface/technologies/armor"
PAINT = {
    # Fabric swatches from the line infantry's diffuse atlas. The second colour
    # is reserved for trim, insignia and stowage.
    "NAM": ("NAM_field", (88, 80, 48), (132, 120, 79)),
    "SHL": ("SHL_line_field", (88, 80, 64), (176, 144, 91)),
    "VAL": ("VAL_regular", (38, 47, 60), (99, 113, 127)),
    "NOD": ("NOD_line", (64, 72, 80), (139, 149, 157)),
    "STS": ("STS_regular", (64, 72, 80), (153, 137, 107)),
    "SRP": ("SRP_highland", (80, 72, 40), (135, 124, 85)),
    "STP": ("STP_party", (88, 80, 56), (139, 122, 78)),
    "IVN": ("IVN_line", (112, 96, 64), (140, 132, 111)),
    "MON": ("MON_field", (32, 64, 40), (126, 135, 108)),
    "RUS": ("RUS_field", (32, 40, 40), (120, 57, 58)),
    "WRK": ("WRK_line", (64, 64, 40), (115, 110, 80)),
}
CLIPS = ("idle", "move", "attack")


def prepare():
    from PIL import Image, ImageDraw
    import numpy as np
    from tools.assets.source.build_shl_palace import dds_bytes

    STAGE.mkdir(parents=True, exist_ok=True)
    metal = Image.open(DEST / "VAL_tank_diffuse.dds").convert("L").crop((0, 0, 256, 256))
    y, x = np.mgrid[0:256, 0:256]
    field = np.asarray(metal, dtype=float) - np.median(np.asarray(metal))
    for tag, (uniform, anchor, trim) in PAINT.items():
        cloth = Image.open(DEST.parent / "ADISCORD_regulars" / (uniform + "_body_diffuse.dds")).convert("RGB")
        samples = np.asarray(cloth.resize((256, 256)), dtype=float).reshape(-1, 3)
        distance = np.linalg.norm(samples - anchor, axis=1)
        base = np.median(samples[distance <= np.percentile(distance, 5)], axis=0)
        if tag == "MON":
            # Broad steel panels receive more direct light than the folded green cloth.
            base = (0.66 * base + 0.34 * (base @ [0.299, 0.587, 0.114])) * 0.86
        canvas = np.array(trim) * 0.78
        if tag == "RUS":
            canvas = 0.70 * base + 0.30 * canvas
        rng = np.random.default_rng(sum(map(ord, tag)))
        atlas = Image.new("RGBA", (1024, 1024))
        palette = [
            base * 1.16,
            base * 0.68,
            (39, 38, 34),
            (87, 88, 82),
            trim,
            (44, 62, 66),
            base * 1.30,
            (27, 29, 27),
            base,
            base * 1.29,
            (91, 42, 35),
            canvas,
            (53, 51, 44),
            trim,
            (70, 66, 53),
            base,
        ]
        for tile, color in enumerate(palette):
            edge = np.minimum.reduce([x, 255 - x, y, 255 - y])
            grit = rng.normal(0, 3, (256, 256)) + field * 0.42
            shading = 6 - 13 * (y / 255) ** 2 - 12 * np.exp(-edge / 11)
            if tag == "VAL" and tile in (0, 9):
                shading += np.where(np.sin(x / 45 + np.cos(y / 32) * 2.1) > 0.38, -12, 3)
            pixels = np.array(color)[None, None, :] + (grit + shading)[:, :, None]
            panel = Image.fromarray(np.clip(pixels, 0, 255).astype("uint8"), "RGB")
            draw = ImageDraw.Draw(panel)
            if tile in (0, 1, 9):
                shadow = tuple(np.clip(np.array(color) * 0.57, 0, 255).astype(int))
                edge_light = tuple(np.clip(np.array(color) * 1.40 + 8, 0, 255).astype(int))
                draw.rounded_rectangle((5, 5, 250, 250), radius=9, outline=shadow, width=3)
                draw.line((13, 9, 236, 9), fill=edge_light, width=2)
                for xx in (19, 237):
                    for yy in (23, 232):
                        draw.ellipse((xx - 4, yy - 3, xx + 5, yy + 5), fill=shadow)
                        draw.line((xx - 2, yy - 2, xx + 2, yy - 2), fill=edge_light, width=2)
            if tile == 7:
                for yy in range(9, 252, 17):
                    draw.rectangle((5, yy, 250, yy + 6), fill=(17, 20, 20))
                    draw.line((8, yy + 8, 249, yy + 8), fill=(78, 77, 65), width=2)
            atlas.paste(panel, (tile % 4 * 256, tile // 4 * 256))
        stencil = Image.new("RGB", (256, 256), tuple(base.astype(int)))
        ink = tuple((base * 0.32 + np.array(trim) * 0.68).astype(int))
        mark = ImageDraw.Draw(stencil)
        if tag in ("NAM", "SHL"):
            mark.polygon(((128, 34), (224, 128), (128, 222), (32, 128)), outline=ink, width=14)
            if tag == "SHL":
                mark.line((128, 73, 128, 183), fill=ink, width=11)
                mark.line((73, 128, 183, 128), fill=ink, width=9)
        else:
            flag = Image.open(ROOT / f"gfx/flags/{tag}.tga").convert("L")
            mark_image = Image.new("RGB", flag.size, ink)
            flagsize = (160, 97)
            stencil.paste(
                mark_image.resize(flagsize), (48, 79), flag.resize(flagsize, Image.Resampling.LANCZOS)
            )
        atlas.paste(stencil, (0, 512))
        (STAGE / f"{tag}_armor_diffuse.dds").write_bytes(dds_bytes(atlas))
        if DESIGNS[tag][1] is None:
            old = Image.open(DEST / f"{tag}_tank_diffuse.dds").convert("RGBA")
            unit = old.width // 4
            # The four retained sculpts have their own UV layout. Repaint only
            # armour and mantlet swatches, preserving seams, optics and insignia.
            indices = (0, 1, 9) if tag == "SHL" else (0, 1, 6, 9, 14)
            for tile in indices:
                left, top = tile % 4 * unit, tile // 4 * unit
                original = np.asarray(
                    old.crop((left, top, left + unit, top + unit)).convert("RGB"), dtype=float
                )
                lum = original @ [0.299, 0.587, 0.114]
                gain = 0.68 if tile == 1 else 1.18 if tile in (6, 9) else 1.06
                recolored = base * gain + ((lum - np.median(lum)) * 0.97)[:, :, None]
                if tag == "SHL" and tile == 9:
                    recolored = np.array(trim) * 0.78 + ((lum - np.median(lum)) * 0.97)[:, :, None]
                old.paste(Image.fromarray(np.clip(recolored, 0, 255).astype("uint8")), (left, top))
            (STAGE / f"{tag}_medium_armor_diffuse.dds").write_bytes(dds_bytes(old))


def running_gear(m, d, width, body):
    length = d.length
    axle_span = length * 0.74
    step = axle_span / (d.wheels - 1)
    radius = min(0.58, step * 0.47)
    m.wheels = []
    for i in range(d.wheels):
        y = -axle_span / 2 + i * step
        m.wheels.append(m.bone(f"wheel_{i}", (0, y, radius + 0.13)))
    for side in (-1, 1):
        x = side * width / 2
        outer = x + side * 0.31
        # The hollow continuous belt frames the wheels even between tread shoes.
        corners = [
            (-0.50, 0.79),
            (-0.485, 1.07),
            (-0.44, 1.30),
            (0.41, 1.30),
            (0.475, 1.16),
            (0.50, 0.94),
            (0.485, 0.64),
            (0.424, 0.19),
            (0.38, 0.09),
            (-0.385, 0.09),
            (-0.427, 0.19),
            (-0.485, 0.55),
        ]
        rim = [(ay * length, az) for ay, az in corners]
        inner = [(yy * 0.966, 0.70 + (zz - 0.70) * 0.74) for yy, zz in rim]
        points = [(x + dx, yy, zz) for dx in (-0.315, 0.315) for loop in (rim, inner) for yy, zz in loop]
        n = len(rim)
        faces = []
        for j in range(n):
            k = (j + 1) % n
            faces.extend(
                [
                    (j, k, n + k, n + j),
                    (2 * n + j, 3 * n + j, 3 * n + k, 2 * n + k),
                    (j, 2 * n + j, 2 * n + k, k),
                    (n + j, n + k, 3 * n + k, 3 * n + j),
                ]
            )
        m.solid(points, faces, 2, body)
        for i, (ay, az) in enumerate(corners):
            by, bz = corners[(i + 1) % len(corners)]
            a, b = Vector((x, ay * length, az)), Vector((x, by * length, bz))
            delta = b - a
            rotation = Matrix.Rotation(math.atan2(delta.z, delta.y), 3, "X")
            count = max(1, round(delta.length / 0.23))
            for j in range(count):
                m.box(a + delta * ((j + 0.5) / count), (0.665, 0.10, 0.075), 12, body, rotation)
        for yy, zz in ((-0.445 * length, 0.84), (0.447 * length, 0.90)):
            m.rod((x - 0.26, yy, zz), (x + 0.26, yy, zz), 0.345, 12, body, sides=16)
            m.rod((x, yy, zz), (outer, yy, zz), 0.25, 1, body, sides=12)
        for i, bone in enumerate(m.wheels):
            _, y, z = m.bones[bone][0]
            m.rod((x - 0.27, y, z), (x + 0.27, y, z), radius, 2, bone, sides=18)
            m.rod((outer - side * 0.06, y, z), (outer, y, z), radius * 0.81, 0, bone, sides=20)
            m.rod(
                (outer, y, z),
                (outer + side * 0.035, y, z),
                radius * 0.74,
                1,
                bone,
                end_radius=radius * 0.66,
                sides=20,
            )
            m.rod(
                (outer + side * 0.035, y, z), (outer + side * 0.046, y, z), radius * 0.59, 0, bone, sides=20
            )
            for angle in range(0, 360, 60):
                a = math.radians(angle + 7 * i)
                yy, zz = y + math.cos(a) * radius * 0.44, z + math.sin(a) * radius * 0.44
                m.rod(
                    (outer + side * 0.046, yy, zz),
                    (outer + side * 0.052, yy, zz),
                    radius * 0.105,
                    2,
                    bone,
                    sides=8,
                )
            m.rod(
                (outer + side * 0.04, y, z),
                (outer + side * 0.10, y, z),
                radius * 0.32,
                1,
                bone,
                end_radius=radius * 0.23,
            )
            m.rod((outer + side * 0.10, y, z), (outer + side * 0.112, y, z), radius * 0.16, 12, bone, sides=8)
        skirt = d.suspension
        if skirt == "floats":
            m.loft(
                [
                    (-length * 0.48, 0.06, 0.06, 1.51),
                    (-length * 0.34, 0.40, 0.24, 1.44),
                    (length * 0.34, 0.40, 0.24, 1.44),
                    (length * 0.46, 0.21, 0.16, 1.43),
                ],
                0,
                body,
                x=x,
                sides=8,
            )
            for yy in (-0.29, -0.06, 0.22):
                y = yy * length
                m.loft([(y - 0.052, 0.42, 0.25, 1.44), (y + 0.052, 0.42, 0.25, 1.44)], 1, body, x=x, sides=8)
            m.box((x + side * 0.31, 0, 1.31), (0.12, length * 0.70, 0.085), 1, body)
            m.box((x + side * 0.405, length * 0.13, 1.47), (0.035, 0.55, 0.22), 8, body)
        elif skirt in ("scales", "slabs"):
            n = d.wheels if skirt == "scales" else 3
            pitch = length * 0.88 / n
            for i in range(n):
                y = (i - (n - 1) / 2) * pitch
                z = 0.69 if skirt == "scales" else 0.50
                m.plate(
                    [
                        (outer, y - pitch * 0.49, 1.43),
                        (outer, y + pitch * 0.49, 1.43),
                        (outer + side * 0.08, y + pitch * 0.46, z + 0.09),
                        (outer + side * 0.08, y - pitch * 0.30, z),
                    ],
                    0.09,
                    9 if i % 3 == 1 else 0,
                    body,
                    axis=0,
                )
        elif skirt == "bogies":
            for i in range(0, d.wheels - 1, 2):
                y = -axle_span / 2 + (i + 0.5) * step
                for yy in (y - step / 2, y + step / 2):
                    m.rod((outer, y, 1.1), (outer + side * 0.04, yy, radius + 0.15), 0.09, 1, body)
        m.box((x, 0, 1.34), (0.74, length * 0.86, 0.14), 1, body)
        m.box((x, 0, 1.43), (0.77, length * 0.87, 0.07), 0, body)
        for yy in (-0.32, -0.12, 0.12, 0.32):
            m.plate(
                [
                    (outer, yy * length - 0.16, 1.34),
                    (outer, yy * length + 0.17, 1.34),
                    (outer, yy * length + 0.08, 1.13),
                ],
                0.07,
                1,
                body,
                axis=0,
            )
        label = "right" if side > 0 else "left"
        m.locators[label + "_tracks"] = ((x, length * 0.41, 0.14), body)
        m.locators[label + "_exhaust"] = ((x * 0.63, length * 0.46, d.deck), body)


# Relative sections describe the different turret castings in profile.
# Each ring specifies height, width, nose and tail relative to the turret pivot.
TURRET = {
    "drum": [
        (0, 0.62, -0.60, 0.62),
        (0.17, 0.88, -0.81, 0.81),
        (0.87, 0.87, -0.79, 0.79),
        (0.95, 0.71, -0.67, 0.67),
    ],
    "needle": [(0, 0.78, -0.70, 0.67), (0.32, 1, -1.2, 0.95), (0.68, 0.49, -0.38, 0.72)],
    "wedge": [(0, 0.87, -1.05, 1.04), (0.24, 1, -1.70, 1.31), (0.69, 0.71, -0.35, 1.10)],
    "boat": [(0, 0.62, -0.69, 0.84), (0.51, 1, -1.24, 1.42), (0.85, 0.77, -0.88, 1.16)],
    "oscillating": [
        (0, 0.61, -0.61, 0.60),
        (0.36, 0.69, -0.63, 0.58),
        (0.47, 1, -1.18, 1.28),
        (0.85, 0.70, -0.90, 1.15),
    ],
    "box": [(0, 0.95, -0.84, 1.14), (0.82, 1, -0.91, 1.14), (0.97, 0.87, -0.83, 1.00)],
    "monitor": [(0, 0.75, -0.60, 0.84), (0.23, 1, -1.17, 1.05), (0.78, 0.98, -1.11, 1.03)],
    "terrace": [
        (0, 1, -1.08, 1.17),
        (0.55, 0.95, -0.91, 1.23),
        (0.62, 0.72, -0.50, 0.85),
        (1.15, 0.65, -0.29, 0.78),
    ],
    "citadel": [(0, 1, -1.07, 1.27), (0.31, 1, -1.18, 1.34), (1.18, 0.72, -0.72, 0.87)],
}


def superstructure(m, d, kind, turret, gun, size):
    y, base = d.turret_y, d.deck + 0.10
    width = 1.9 * size
    height = {"light": 0.83, "medium": 1.02, "heavy": 1.24}[kind]
    if d.turret == "dome":
        for z0, z1, r0, r1 in (
            (0, 0.16, 0.68, 1),
            (0.16, 0.52, 1, 0.94),
            (0.52, 0.78, 0.94, 0.65),
            (0.78, 0.89, 0.65, 0.34),
        ):
            m.rod(
                (0, y, base + z0 * height),
                (0, y, base + z1 * height),
                width * r0 * 0.53,
                0,
                turret,
                end_radius=width * r1 * 0.53,
                sides=20,
            )
        roof = base + 0.89 * height
    else:
        rings = TURRET[d.turret]
        hull(
            m,
            [
                (base + z * height, width * w, y + front * size, y + rear * size, min(0.34, w * width * 0.22))
                for z, w, front, rear in rings
            ],
            0,
            turret,
        )
        roof = base + rings[-1][0] * height
    gz = base + height * (0.52 if d.turret != "needle" else 0.38)
    short_mount = {"drum": 0.80, "box": 0.84, "terrace": 0.83, "monitor": 0.87}.get(d.turret, 1)
    # Render the scout's aerial, the gun shield and the turret ring as separate
    # silhouettes even at native equipment-card size.
    tip = min(-d.reach * short_mount, y - size * 1.75)
    lift = {"needle": 0.07, "drum": 0.16, "oscillating": 0.18, "box": 0.08, "dome": 0.12}.get(d.turret, 0)
    for x in (-0.28, 0.28) if d.fittings == "twin" else (0,):
        front = y - size * 0.90
        mid = front + (tip - front) * 0.40
        r = {"light": 0.10, "medium": 0.147, "heavy": 0.20}[kind]
        m.rod((x, front + 0.17, gz), (x, front - 0.34, gz), r * 2.70, 1, gun, end_radius=r * 1.70)
        m.rod((x, front - 0.30, gz), (x, mid, gz + lift * 0.41), r * 1.42, 0, gun, end_radius=r * 1.04)
        m.rod((x, mid, gz + lift * 0.41), (x, tip, gz + lift), r, 12, gun, end_radius=r * 0.76)
        if d.turret in ("box", "monitor", "citadel", "oscillating"):
            m.box((x, tip + 0.12, gz + lift), (r * 2.39, 0.37, r * 2.04), 1, gun)
            m.box((x, tip - 0.071, gz + lift), (r * 1.47, 0.02, r * 1.22), 7, gun)
        else:
            m.rod((x, tip + 0.10, gz + lift), (x, tip - 0.02, gz + lift), r * 0.94, 1, gun)
    m.locators["barrel"] = ((0, tip - 0.07, gz + lift), gun)
    m.rod((-0.20, y + 0.15, roof), (-0.20, y + 0.15, roof + 0.13), 0.33 * size, 1, turret, sides=16)
    m.box((0.34, y - 0.17, roof + 0.09), (0.30, 0.38, 0.18), 1, turret)
    m.box((0.34, y - 0.37, roof + 0.10), (0.23, 0.035, 0.11), 5, turret)
    for side in (-1, 1):
        x = side * width * 0.46
        m.box((x, y + 0.36, base + 0.42 * height), (0.15, 0.52, 0.32), 8, turret)
        for yy in (-0.51, -0.14):
            m.rod(
                (x * 0.88, y + yy, base + 0.53 * height),
                (x * 1.03, y + yy - 0.06, base + 0.53 * height),
                0.045,
                3,
                turret,
                sides=8,
            )
        m.rod(
            (x * 1.03, y - 0.57, base + 0.53 * height),
            (x * 1.03, y - 0.20, base + 0.53 * height),
            0.032,
            3,
            turret,
            sides=8,
        )
    return roof


def outfit(m, d, size, body, turret, roof):
    y, l, z = d.turret_y, d.length, d.deck
    for side in (-1, 1):
        x = side * size * 0.86
        m.box((x, -l * 0.35, z - 0.04), (0.30, 0.37, 0.20), 1, body)
        m.box((x, -l * 0.35 - 0.19, z - 0.04), (0.23, 0.04, 0.13), 13, body)
        if d.fittings in ("drums", "roll", "canopy"):
            yy = l * 0.40 if d.fittings == "drums" else y + size
            zz = z + 0.20 if d.fittings == "drums" else roof - 0.24
            bone = body if d.fittings == "drums" else turret
            m.rod((x * 0.25, yy, zz), (x * 1.18, yy, zz), 0.28 * size, 11, bone, sides=14)
            for factor in (0.39, 0.91):
                m.rod(
                    (x * factor, yy, zz), (x * factor + side * 0.06, yy, zz), 0.29 * size, 1, bone, sides=14
                )
        if d.fittings in ("bridge", "canopy", "split"):
            rr = roof + (0.13 if d.fittings == "canopy" else 0.23) * size
            for yy in (y - 0.52, y + 0.70):
                m.rod((x * 0.60, yy, roof - 0.23), (x * 0.60, yy, rr), 0.055, 3, turret)
            m.box((x * 0.60, y + 0.09, rr), (0.24 if d.fittings == "split" else 0.12, 1.52, 0.12), 9, turret)
            if d.fittings == "canopy" and side == 1:
                m.loft(
                    [
                        (y - 0.66, 0.77 * size, 0.08, rr),
                        (y - 0.34, 0.90 * size, 0.16, rr + 0.025),
                        (y + 0.34, 0.92 * size, 0.13, rr),
                        (y + 0.81, 0.82 * size, 0.16, rr - 0.05),
                    ],
                    13,
                    turret,
                    sides=8,
                )
                m.box((x, y + 0.40, roof - 0.38), (0.32, 0.82, 0.36), 11, turret)
            if d.fittings == "bridge" and side == 1:
                m.box((0, y - 0.30, rr), (1.36 * size, 0.48, 0.30), 1, turret)
                m.box((0, y - 0.55, rr + 0.01), (0.87 * size, 0.04, 0.13), 5, turret)
        if d.fittings == "lockers":
            for i in range(3):
                m.box((x * 1.49, l * 0.11 + i * 0.51, z + 0.07), (0.41, 0.47, 0.37), 11, body)
                m.box((x * 1.49, l * 0.11 + i * 0.51, z + 0.26), (0.44, 0.49, 0.05), 9, body)
        if d.fittings == "stacks":
            for i in range(2):
                yy = l * 0.27 + i * 0.34
                m.rod((x, yy, z), (x, yy, z + 0.56 + i * 0.19), 0.14, 12, body)
                m.rod((x, yy, z + 0.50 + i * 0.19), (x, yy, z + 0.59 + i * 0.19), 0.18, 3, body)
    if d.turret == "citadel":
        for side in (-1, 1):
            for i in range(3):
                yy = y + size * (-0.67 + i * 0.44)
                m.plate(
                    [
                        (side * 0.88 * size, yy - 0.17, z + 0.83 * size),
                        (side * 0.88 * size, yy + 0.23, z + 0.83 * size),
                        (side * 1.04 * size, yy + 0.21, z + 0.43 * size),
                        (side * 1.04 * size, yy - 0.21, z + 0.45 * size),
                    ],
                    0.08,
                    1 if i == 2 else 9,
                    turret,
                    axis=0,
                )
    if d.fittings in ("signal", "aerial"):
        m.rod((0.40, y + 0.54, roof - 0.10), (0.40, y + 0.57, roof + 0.64), 0.037, 3, turret)
        if d.fittings == "signal":
            m.box((0.40, y + 0.57, roof + 0.61), (0.54, 0.38, 0.24), 1, turret)
            m.box((0.40, y + 0.37, roof + 0.61), (0.43, 0.03, 0.15), 5, turret)


def build_model(tag, kind, d):
    size = {"light": 0.87, "medium": 1.09, "heavy": 1.28}[kind]
    m = native.Model(model_name(tag, kind))
    body = m.bone("hull", (0, 0, 1))
    d = d._replace(deck=d.deck + 0.25)
    width, l, z = size * 2.78, d.length, d.deck
    hull(
        m,
        [
            (0.45, width * 0.76, -l * 0.35, l * 0.37, 0.28),
            (z * 0.80, width, -l * 0.52, l * 0.47, 0.38),
            (z - 0.075, width * 0.94, -l * (0.33 if d.suspension == "floats" else 0.41), l * 0.44, 0.32),
            (z, width * 0.91, -l * (0.31 if d.suspension == "floats" else 0.39), l * 0.42, 0.33),
        ],
        0,
        body,
    )
    running_gear(m, d, width, body)
    turret = m.bone("turret", (0, d.turret_y, z + 0.06), body)
    gun = m.bone("gun", (0, d.turret_y - 0.7, z + 0.50), turret)
    m.rod((0, d.turret_y, z - 0.02), (0, d.turret_y, z + 0.16), 0.91 * size, 12, turret, sides=24)
    roof = superstructure(m, d, kind, turret, gun, size)
    outfit(m, d, size, body, turret, roof)
    m.box((0, l * 0.32, z + 0.03), (width * 0.55, l * 0.15, 0.08), 7, body)
    for i in range(6):
        m.box((0, l * (0.26 + i * 0.024), z + 0.085), (width * 0.50, 0.054, 0.04), 3, body)
    m.locators.update(root=((0, 0, 0), "vehicle_root"), exhaust=((0, l * 0.44, z), body))
    return m


def export_animation(model, rig, clip, pdx):
    rig.animation_data_clear()
    scene = bpy.context.scene
    end = {"move": 33, "idle": 97, "attack": 25}[clip]
    scene.frame_start, scene.frame_end = 1, end
    scene.render.fps = 24
    for bone in rig.pose.bones:
        bone.matrix_basis = Matrix.Identity(4)
        bone.rotation_mode = "XYZ"
    for frame in range(1, end + 1, 2):
        phase = (frame - 1) / (end - 1)
        if clip == "move":
            for name in model.wheels:
                rig.pose.bones[name].rotation_euler.x = -math.tau * phase
            rig.pose.bones["hull"].location.z = 0.023 * math.sin(phase * math.tau * 2)
        elif clip == "idle":
            rig.pose.bones["turret"].rotation_euler.z = 0.09 * math.sin(phase * math.tau)
        else:
            rig.pose.bones["gun"].location.y = 0.23 * max(0, 1 - abs(phase - 0.17) / 0.17)
        for bone in rig.pose.bones:
            bone.keyframe_insert("location", frame=frame)
            bone.keyframe_insert("rotation_euler", frame=frame)
    scene.frame_set(1)
    bpy.context.view_layer.objects.active = rig
    pdx.export_animfile(str(STAGE / f"{model.name}_{clip}.anim"), frame_start=1, frame_end=end)


def export(tag, kind, design, pdx, pdx_data):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    m = build_model(tag, kind, design)
    base = "STP_apc"
    diffuse = f"{tag}_armor_diffuse.dds"
    channels = SimpleNamespace(
        shader=["PdxMeshAdvanced"], diff=[diffuse], n=[base + "_normal.dds"], spec=[base + "_specular.dds"]
    )
    for filename in channels.diff + channels.n + channels.spec:
        if (DEST / filename).is_file() and filename != f"{tag}_armor_diffuse.dds":
            (STAGE / filename).write_bytes((DEST / filename).read_bytes())
    material = pdx.create_shader(channels, m.name, str(STAGE))
    obj, rig = m.object(material)
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    for empty in bpy.context.scene.objects:
        if empty.type == "EMPTY":
            empty.select_set(True)
    bpy.context.view_layer.objects.active = obj
    path = STAGE / (m.name + ".mesh")
    pdx.export_meshfile(str(path), exp_selected=True)
    tree = pdx_data.read_meshfile(str(path))
    for mesh in tree.findall("./object/*/mesh"):
        skin = mesh.find("skin")
        ix, w = skin.attrib["ix"], skin.attrib["w"]
        assert all(w[i : i + 4] == [1, 0, 0, 0] for i in range(0, len(w), 4))
        skin.set("bones", [1])
        skin.set("ix", [ix[i - i % 4] for i in range(len(ix))])
        mesh.set("ta", [round(v, 5) for v in mesh.attrib["ta"]])
        assert all(math.isfinite(v) for v in mesh.attrib["ta"])
        assert max(mesh.attrib["tri"]) < len(mesh.attrib["p"]) // 3 < 65536
    pdx_data.write_meshfile(str(path), tree)
    for clip in CLIPS:
        export_animation(m, rig, clip, pdx)
    return path


def side_view(path, tag, kind, pdx):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    pdx.import_meshfile(str(path), join_materials=False)
    if tag != "default" and DESIGNS[tag][CLASSES.index(kind)] is None:
        for texture in bpy.data.images:
            if Path(bpy.path.abspath(texture.filepath)).name == f"{tag}_tank_diffuse.dds":
                texture.filepath = str(STAGE / f"{tag}_medium_armor_diffuse.dds")
                texture.reload()
    for mat in bpy.data.materials:
        if not mat.use_nodes:
            continue
        nodes, links = mat.node_tree.nodes, mat.node_tree.links
        surface = nodes.get("Principled BSDF")
        if surface is None or not surface.inputs["Base Color"].links:
            continue
        diffuse = surface.inputs["Base Color"].links[0].from_socket
        occlusion = nodes.new("ShaderNodeAmbientOcclusion")
        occlusion.inputs["Distance"].default_value = 0.62
        occlusion.samples = 12
        shade = nodes.new("ShaderNodeMixRGB")
        shade.blend_type = "MULTIPLY"
        shade.inputs[0].default_value = 0.77
        links.new(diffuse, shade.inputs[1])
        links.new(occlusion.outputs["Color"], shade.inputs[2])
        links.new(shade.outputs[0], surface.inputs["Base Color"])
        bevel = nodes.new("ShaderNodeBevel")
        bevel.inputs["Radius"].default_value = 0.035
        bevel.samples = 4
        normal = surface.inputs["Normal"]
        if normal.links:
            links.new(normal.links[0].from_socket, bevel.inputs["Normal"])
        links.new(bevel.outputs["Normal"], normal)
    vertices = []
    for obj in list(bpy.context.scene.objects):
        if obj.type == "MESH":
            collision = any(mat.get(pdx.PDX_SHADER) == "Collision" for mat in obj.data.materials)
            if collision or "collision" in obj.name.lower():
                bpy.data.objects.remove(obj, do_unlink=True)
            else:
                vertices.extend(obj.matrix_world @ v.co for v in obj.data.vertices)
    lo = Vector([min(p[i] for p in vertices) for i in range(3)])
    hi = Vector([max(p[i] for p in vertices) for i in range(3)])
    center = (lo + hi) / 2
    scale = max(hi.y - lo.y, (hi.z - lo.z) * 176 / 72) * 1.04
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.samples = 20
    scene.cycles.seed = 0
    scene.render.resolution_x, scene.render.resolution_y = 704, 288
    scene.render.resolution_percentage = 100
    scene.render.film_transparent = True
    scene.world = bpy.data.worlds.new("Studio")
    scene.world.use_nodes = True
    scene.world.node_tree.nodes["Background"].inputs[0].default_value = (0.19, 0.19, 0.19, 1)
    for offset, power in (((0.72, -0.85, 1.15), 85), ((-0.45, 0.7, 1), 72), ((0.58, 0.37, 0.24), 6)):
        bpy.ops.object.light_add(type="AREA", location=center + Vector(offset) * scale)
        lamp = bpy.context.object
        lamp.data.energy, lamp.data.size = power * scale**2, scale * 0.90
        lamp.rotation_euler = (center - lamp.location).to_track_quat("-Z", "Y").to_euler()
    bpy.ops.object.camera_add(location=center + Vector((scale * 2, 0, 0)))
    camera = bpy.context.object
    camera.rotation_euler = (center - camera.location).to_track_quat("-Z", "Y").to_euler()
    camera.data.type = "ORTHO"
    camera.data.ortho_scale = scale
    scene.camera = camera
    scene.render.filepath = str(STAGE / f"{tag}_{kind}_side.png")
    bpy.ops.render.render(write_still=True)


def build(game, tags, cards_only=False):
    global bpy, Matrix, Vector, native
    import bpy
    import bmesh
    from mathutils import Matrix, Vector
    from tools.assets.source import build_country_cas as native
    from tools.assets.source.build_shl_palace import load_exporter

    pdx = load_exporter()
    from io_pdx_mesh import pdx_data

    native.bpy, native.bmesh, native.Matrix, native.Vector = bpy, bmesh, Matrix, Vector
    for tag in tags:
        for i, kind in enumerate(CLASSES):
            print(f"BUILD {tag} {kind}", flush=True)
            if tag == "default":
                mesh = game / f"gfx/models/units/tanks/generic_tank_{kind}.mesh"
            elif DESIGNS[tag][i] is None:
                mesh = DEST / (model_name(tag, kind) + ".mesh")
            elif cards_only:
                mesh = STAGE / (model_name(tag, kind) + ".mesh")
            else:
                mesh = export(tag, kind, DESIGNS[tag][i], pdx, pdx_data)
            side_view(mesh, tag, kind, pdx)


def verify_native(tags):
    import bpy
    from array import array
    from tools.assets.source.build_shl_palace import load_exporter

    pdx = load_exporter()
    from io_pdx_mesh import pdx_data

    silhouettes = set()
    for tag in tags:
        for kind in CLASSES:
            name = model_name(tag, kind)
            path = DEST / (name + ".mesh")
            tree = pdx_data.read_meshfile(str(path))
            geometry = hashlib.sha256()
            for mesh in tree.findall("./object/*/mesh"):
                geometry.update(array("f", mesh.attrib["p"]).tobytes())
                for channel in ("diff", "n", "spec"):
                    texture = mesh.find("material").attrib[channel][0]
                    assert (DEST / texture).is_file(), (name, texture)
            signature = geometry.digest()
            assert signature not in silhouettes, name
            silhouettes.add(signature)
            assert {"barrel", "left_tracks", "right_tracks"} <= {node.tag for node in tree.find("locator")}
            for clip in CLIPS:
                bpy.ops.wm.read_factory_settings(use_empty=True)
                pdx.import_meshfile(str(path), join_materials=False)
                pdx.import_animfile(str(DEST / f"{name}_{clip}.anim"))
                scene = bpy.context.scene
                rig = next(obj for obj in scene.objects if obj.type == "ARMATURE")
                poses = []
                for phase in (0, 0.13, 0.25, 1):
                    scene.frame_set(1 + round((scene.frame_end - 1) * phase))
                    pose = [value for bone in rig.pose.bones for row in bone.matrix for value in row]
                    assert all(math.isfinite(value) for value in pose), (name, clip)
                    poses.append(pose)
                motion = max(abs(a - b) for pose in poses[1:-1] for a, b in zip(poses[0], pose))
                assert motion > 0.012, (name, clip, motion)
    print(f"Verified {len(silhouettes)} distinct meshes and {len(silhouettes) * len(CLIPS)} animation clips.")


def package(apply):
    from PIL import Image, ImageFilter
    import io

    files = {}
    for tag in PAINT:
        names = [f"{tag}_armor_diffuse.dds"]
        if DESIGNS[tag][1] is None:
            names.append(f"{tag}_medium_armor_diffuse.dds")
        for name in names:
            files[DEST / name] = (STAGE / name).read_bytes()
    for tag in (*DESIGNS, "default"):
        for i, kind in enumerate(CLASSES):
            if tag != "default" and DESIGNS[tag][i] is not None:
                name = model_name(tag, kind)
                for suffix in (".mesh", *(f"_{c}.anim" for c in CLIPS)):
                    binary = (STAGE / (name + suffix)).read_bytes()
                    assert binary.startswith(b"@@b@")
                    files[DEST / (name + suffix)] = binary
            image = Image.open(STAGE / f"{tag}_{kind}_side.png").convert("RGBA")
            alpha = image.getchannel("A")
            bounds = alpha.point(lambda p: 255 if p > 25 else 0).getbbox()
            if bounds is None:
                raise ValueError(f"Empty side view: {tag} {kind}")
            image = image.crop(bounds)
            image.thumbnail((172, 68), Image.Resampling.LANCZOS)
            card = Image.new("RGBA", (176, 72))
            card.alpha_composite(image, ((176 - image.width) // 2, (72 - image.height) // 2))
            outline = Image.new("RGBA", card.size, (22, 21, 19, 0))
            outline.putalpha(
                card.getchannel("A").filter(ImageFilter.MaxFilter(3)).point(lambda a: a * 3 // 4)
            )
            outline.alpha_composite(card)
            stream = io.BytesIO()
            outline.save(stream, format="PNG")
            files[CARDS / tag / (kind + ".png")] = stream.getvalue()
    changed = [p for p, data in files.items() if not p.exists() or p.read_bytes() != data]
    if apply:
        for path in changed:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(files[path])
    print(json.dumps({"files": len(files), "changed": len(changed), "applied": apply}))
    return changed


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    for action in ("prepare", "build", "cards", "check", "apply", "verify"):
        group.add_argument("--" + action, action="store_true")
    parser.add_argument("--game", type=Path)
    parser.add_argument("--tag", choices=(*DESIGNS, "default"), action="append")
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else None)
    if args.prepare:
        prepare()
    elif args.verify:
        verify_native([tag for tag in (args.tag or DESIGNS) if tag != "default"])
    elif args.build or args.cards:
        if not args.game:
            parser.error("Rendering requires --game")
        build(args.game, args.tag or (*DESIGNS, "default"), cards_only=args.cards)
    elif package(args.apply) and args.check:
        raise SystemExit(1)
