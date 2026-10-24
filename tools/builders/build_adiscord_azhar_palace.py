"""Build the Black Harbor governor's palace and its native map bindings.

Default/--check is read-only. --apply rebuilds stale outputs with Blender and
the installed io_pdx_mesh exporter. --preview renders the exported mesh again.
Only the named sections of the shared entity and ambient registries are owned.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys
import tempfile

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.assets.source.build_shl_palace import Geometry, dds_bytes, load_exporter

NAME = "ADISCORD_AZH_black_harbor_palace"
MODEL_DIR = Path("gfx/models/buildings/AZH_palace")
SOURCE = Path("tools/assets/source/buildings/AZH/black_harbor_palace.blend")
REPORT = Path("docs/development/model-verification/AZH_palace.json")
PREVIEW = Path("docs/development/previews/AZH_palace")
POSITION = (3876.0, 10.45, 484.2)
SCALE = 0.12
PROVINCE = 493
PROVINCE_RGB = (254, 232, 65)
MARKER = "ADISCORD Azhar Black Harbor palace"
FILES = [NAME + suffix for suffix in (".mesh", "_diffuse.dds", "_normal.dds", "_specular.dds")]
INPUTS = (
    Path(__file__).relative_to(ROOT),
    Path("tools/assets/source/build_shl_palace.py"),
    Path("map/heightmap.bmp"),
    Path("map/provinces.bmp"),
    Path("map/definition.csv"),
)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def input_hashes():
    return {path.as_posix(): digest(ROOT / path) for path in INPUTS}


def textures():
    """One padded atlas; packed normal channels match PdxMeshAdvanced."""
    import numpy as np
    from PIL import Image, ImageDraw, ImageFilter

    colors = (
        (66, 68, 66), (141, 129, 107), (169, 139, 81), (38, 43, 43),
        (102, 46, 34), (83, 82, 75), (135, 126, 106), (112, 94, 62),
        (190, 158, 94), (24, 29, 29), (100, 98, 87), (99, 68, 45),
        (119, 116, 101), (57, 63, 60), (77, 36, 30), (196, 176, 132),
    )
    rng = np.random.default_rng(493)
    atlas = Image.new("RGBA", (1024, 1024))
    relief = Image.new("L", atlas.size, 128)
    for index, color in enumerate(colors):
        noise = rng.normal(0, 2.5, (256, 256, 1))
        rgb = np.clip(np.asarray(color)[None, None, :] + noise, 0, 255).astype("uint8")
        tile = Image.fromarray(rgb).convert("RGBA")
        height = Image.new("L", (256, 256), 128)
        draw = ImageDraw.Draw(tile)
        hd = ImageDraw.Draw(height)
        if index in (0, 1, 5, 6, 10, 12):
            dark = tuple(int(c * .68) for c in color)
            light = tuple(min(255, int(c * 1.13)) for c in color)
            for row, y in enumerate(range(0, 256, 64)):
                draw.line((0, y, 255, y), fill=dark, width=2)
                draw.line((0, y + 3, 255, y + 3), fill=light, width=1)
                hd.line((0, y, 255, y), fill=95, width=2)
                for x in range(-64 if row % 2 else 0, 256, 128):
                    draw.line((x, y, x, y + 64), fill=dark, width=2)
                    hd.line((x, y, x, y + 64), fill=100, width=2)
            for _ in range(35):
                x, y = map(int, rng.integers(9, 246, 2))
                draw.line((x, y, x + 1, min(y + 12, 255)), fill=dark)
        if index in (4, 14):
            draw.rectangle((10, 8, 245, 247), outline=(64, 33, 28), width=6)
            draw.rectangle((17, 16, 238, 239), outline=(142, 77, 52), width=2)
            hd.rectangle((10, 8, 245, 247), outline=90, width=6)
        if index in (2, 7, 8, 15):
            for x in (12, 243):
                draw.line((x, 0, x, 255), fill=tuple(int(c * .75) for c in color), width=2)
            for _ in range(45):
                x, y = map(int, rng.integers(0, 256, 2))
                draw.line((x, y, min(x + 10, 255), y), fill=tuple(int(c * .8) for c in color))
        if index == 3:
            draw.rectangle((6, 6, 249, 249), outline=(19, 22, 21), width=10)
            for y in range(18, 246, 29):
                draw.line((14, y, 242, y), fill=(69, 74, 65), width=3)
                hd.line((14, y, 242, y), fill=110, width=3)
        offset = ((index % 4) * 256, (index // 4) * 256)
        atlas.paste(tile, offset)
        relief.paste(height, offset)
    values = np.asarray(relief.filter(ImageFilter.GaussianBlur(1)), dtype=float)
    dy, dx = np.gradient(values)
    normal = np.zeros((1024, 1024, 4), dtype="uint8")
    normal[:, :, 0] = 255
    normal[:, :, 1] = np.clip(128 - dx * .6, 80, 176)
    normal[:, :, 3] = np.clip(128 + dy * .6, 80, 176)
    specular = Image.new("RGBA", atlas.size, (0, 28, 0, 25))
    sd = ImageDraw.Draw(specular)
    for index in (2, 7, 8, 15):
        x, y = (index % 4) * 256, (index // 4) * 256
        sd.rectangle((x, y, x + 255, y + 255), fill=(0, 125, 0, 95))
    return {
        NAME + "_diffuse.dds": dds_bytes(atlas),
        NAME + "_normal.dds": dds_bytes(Image.fromarray(normal)),
        NAME + "_specular.dds": dds_bytes(specular),
    }


class PalaceGeometry(Geometry):
    def panel(self, points, tile, subdivide=False):
        if not subdivide:
            self.face(points, tile)
            return
        from mathutils import Vector

        a, b, c, d = map(Vector, points)
        nx = max(1, math.ceil(max((b - a).length, (c - d).length) / 5))
        ny = max(1, math.ceil(max((d - a).length, (c - b).length) / 5))

        def point(u, v):
            return tuple(a * (1 - u) * (1 - v) + b * u * (1 - v)
                         + c * u * v + d * (1 - u) * v)

        for i in range(nx):
            for j in range(ny):
                self.face([point(i / nx, j / ny), point((i + 1) / nx, j / ny),
                           point((i + 1) / nx, (j + 1) / ny), point(i / nx, (j + 1) / ny)], tile)

    def taper(self, x, y, bottom, top, width, depth, inset, tile=0):
        lower = [(x - width / 2, y - depth / 2, bottom),
                 (x + width / 2, y - depth / 2, bottom),
                 (x + width / 2, y + depth / 2, bottom),
                 (x - width / 2, y + depth / 2, bottom)]
        upper = [(px + (inset if px < x else -inset),
                  py + (inset if py < y else -inset), top) for px, py, _ in lower]
        self.face(list(reversed(lower)), tile)
        self.face(upper, tile)
        for i in range(4):
            k = (i + 1) % 4
            self.panel([lower[i], lower[k], upper[k], upper[i]], tile, True)

    def rim(self, x, y, z, width, depth, tile=2, thickness=.25, height=.25):
        for side in (-1, 1):
            self.box((x, y + side * (depth - thickness) / 2, z),
                     (width, thickness, height), tile)
            self.box((x + side * (width - thickness) / 2, y, z),
                     (thickness, depth - 2 * thickness, height), tile)

    def cap(self, x, y, z, width, depth):
        self.box((x, y, z), (width, depth, .3), 1)
        self.rim(x, y, z + .22, width + .22, depth + .22, 8, .22, .16)
        self.rim(x, y, z + .5, width, depth, 1, .42, .45)
        self.rim(x, y, z + .78, width + .1, depth + .1, 2, .48, .12)

    def arch(self, y, bottom, shoulder, peak, half_width, thickness, depth, tile):
        inner = [(-half_width, bottom), (-half_width, shoulder), (0, peak),
                 (half_width, shoulder), (half_width, bottom)]
        outer = [(-half_width - thickness, bottom), (-half_width - thickness, shoulder + thickness * .5),
                 (0, peak + thickness * 1.25),
                 (half_width + thickness, shoulder + thickness * .5), (half_width + thickness, bottom)]
        for i in range(4):
            k = i + 1
            a, b = inner[i], inner[k]
            c, d = outer[k], outer[i]
            self.face([(x, y, z) for x, z in (a, b, c, d)], tile)
            self.face([(x, y + depth, z) for x, z in (d, c, b, a)], tile)
            for p, q in ((a, b), (c, d)):
                self.face([(p[0], y, p[1]), (q[0], y, q[1]),
                           (q[0], y + depth, q[1]), (p[0], y + depth, p[1])], tile)
        for i in (0, 4):
            a, b = inner[i], outer[i]
            self.face([(a[0], y, a[1]), (b[0], y, b[1]),
                       (b[0], y + depth, b[1]), (a[0], y + depth, a[1])], tile)

    def extrude_xz(self, profile, front, rear, tile):
        xmin = min(p[0] for p in profile)
        xmax = max(p[0] for p in profile)
        zmin = min(p[1] for p in profile)
        zmax = max(p[1] for p in profile)
        uv = [((x - xmin) / (xmax - xmin), (z - zmin) / (zmax - zmin)) for x, z in profile]
        self.face([(x, front, z) for x, z in profile], tile, uv)
        self.face([(x, rear, z) for x, z in reversed(profile)], tile, list(reversed(uv)))
        for i, a in enumerate(profile):
            b = profile[(i + 1) % len(profile)]
            self.face([(a[0], front, a[1]), (b[0], front, b[1]),
                       (b[0], rear, b[1]), (a[0], rear, a[1])], tile)


def geometry():
    g = PalaceGeometry()
    # Terrain-fitted base, raised paving and a continuous accessible entry stair.
    g.box((0, -1.6, .6), (43, 34, 1.2), 5)
    g.box((0, -1.6, 1.28), (43.4, 34.4, .16), 6)
    g.box((0, 1, 1.7), (38, 27, .7), 0)
    for i in range(7):
        height = (i + 1) * .12
        g.box((0, -16.6 + i * .54, 1.36 + height / 2), (7.8, .56, height), 1)

    # Separate side wings leave a real recess behind the entrance portal.
    for side in (-1, 1):
        g.box((side * 11.25, 0, 5.3), (14.5, 25, 6.5), 0)
        g.cap(side * 11.25, 0, 8.65, 14.9, 25.4)
    g.box((0, 6.7, 5.3), (8, 11.6, 6.5), 0)
    g.box((0, 4, 10.2), (24, 17, 3.1), 0)
    g.cap(0, 4, 11.9, 24.4, 17.4)
    g.box((0, 4, 12.5), (18, 12, .3), 5)

    for x in (-17.1, 17.1):
        for y in (-10.6, 10.6):
            g.taper(x, y, 2.05, 10.9, 5.2, 5.2, .75)
            g.box((x, y, 2.4), (5.5, 5.5, .65), 1)
            g.rim(x, y, 3, 5.25, 5.25, 2, .14, .13)
            g.cap(x, y, 11, 4.2, 4.2)
            g.box((x, y, 12), (2.9, 2.9, .45), 0)
            g.rim(x, y, 12.3, 3.05, 3.05, 8, .22, .18)

    # Vertical windows and masonry piers define the central administrative tower.
    g.box((0, 4.2, 16.6), (12, 9, 8), 0)
    for side in (-1, 1):
        for y in (.1, 8.3):
            g.taper(side * 5.7, y, 12.6, 20.6, 1.5, 1.5, .35, 0)
    g.cap(0, 4.2, 20.7, 12.3, 9.3)
    g.box((0, 4.2, 21.6), (6.5, 4.5, .65), 5)
    g.rim(0, 4.2, 22, 6.8, 4.8, 2, .26, .18)
    for side in (-1, 1):
        for x in (-4.5, -2.25, 0, 2.25, 4.5):
            y = 4.2 + side * 4.51
            g.box((x, y, 16.9), (.85, .12, 5.5), 9)
            g.box((x + .61, y + side * .18, 16.9), (.26, .45, 6.1), 1)
            g.box((x, y + side * .08, 14.2), (.85, .16, .2), 2)
        for y in (1.5, 4.2, 6.9):
            g.box((side * 6, y, 16.9), (.12, .9, 5.5), 9)
            g.box((side * 6.15, y + .63, 16.9), (.42, .26, 6.1), 1)
        for x in (-5.6, 5.6):
            g.lathe(x, 4.2 + side * 3.9, [(.16, 21.5), (.16, 21.9), (.06, 23)], 7, 6)

    # The pointed portal is built as nested rings, not painted on a solid wall.
    g.arch(-12.9, 2.2, 8.4, 11.9, 3.9, 1.25, 1.8, 1)
    g.arch(-13.04, 2.2, 8.15, 11.2, 3.55, .18, .2, 8)
    g.arch(-12.55, 2.2, 7.9, 10.75, 3.2, .45, 1.7, 0)
    g.arch(-11.9, 2.2, 7.45, 10, 2.8, .22, 1.4, 2)
    # Spandrels close the portal into a rectangular gatehouse above the arch.
    for side in (-1, 1):
        profile = [(side * x, z) for x, z in ((5.8, 8.4), (5.15, 9.025),
                   (0, 13.4625), (0, 14.2), (5.8, 14.2))]
        g.extrude_xz(profile, -12.72, -9.4, 1)
        g.box((side * 5.65, -8.2, 8.2), (.6, 9, 12.2), 0)
    g.box((0, -6.8, 13.3), (11.6, 5.6, 1.8), 0)
    g.cap(0, -8.2, 14.3, 11.9, 9.6)
    g.box((0, -9.95, 5.1), (5.6, .35, 5.8), 9)
    for side in (-1, 1):
        g.box((side * 1.3, -10.2, 4.9), (2.55, .2, 5.3), 7)
        for z in (3.4, 5, 6.6):
            g.box((side * 1.3, -10.33, z), (2.1, .09, 1.25), 11)
            g.box((side * 1.3, -10.4, z + .6), (2.2, .08, .1), 8)
        g.box((side * .24, -10.5, 4.6), (.12, .17, .55), 15)
        g.taper(side * 4.6, -11.1, 2.05, 9.9, 2.2, 4.2, .3, 1)
        g.cap(side * 4.6, -11.1, 10, 1.8, 3.8)

    # Recessed red wall bays and pilasters continue around all visible sides.
    for side in (-1, 1):
        for x in (7.2, 9.1, 11, 12.9):
            g.box((side * x, -12.54, 5.5), (1.28, .13, 4.7), 4)
            g.box((side * x, -12.64, 5.9), (.34, .12, 3.5), 9)
            g.box((side * (x + .82), -12.74, 5.3), (.32, .4, 5.8), 1)
        for y in (-6.4, -3.1, .2, 3.5, 6.8):
            g.box((side * 18.54, y, 5.4), (.13, 2, 4.7), 4)
            g.box((side * 18.65, y, 5.8), (.12, .5, 3.4), 9)
            g.box((side * 18.78, y + 1.4, 5.25), (.42, .4, 5.7), 1)
        for y in (-2, 1, 4, 7, 10):
            g.box((side * 12.05, y, 10.2), (.12, .55, 1.5), 9)
    for x in range(-12, 13, 3):
        g.box((x, 12.55, 5.5), (1.2, .14, 4.6), 3)
        g.box((x + 1.1, 12.72, 5.3), (.4, .4, 5.8), 1)
    for x in (-10, 10):
        g.box((x, 3, 9.7), (2.8, 4.7, .8), 5)
        g.rim(x, 3, 10.18, 3, 4.9, 2, .22, .15)
    for side in (-1, 1):
        g.box((side * 13.6, -16.7, 1.75), (11, .7, .75), 0)
        g.box((side * 13.6, -16.7, 2.2), (11.3, .9, .18), 1)
        for x in (6, 20):
            g.box((side * x, -16.7, 2), (1.25, 1.25, 1.3), 1)
            g.box((side * x, -16.7, 2.75), (1.4, 1.4, .18), 2)
    return g


def fit_foundation(g):
    """Only the underside conforms to terrain; the paving remains level."""
    data = (ROOT / "map/heightmap.bmp").read_bytes()
    width, height = struct.unpack_from("<ii", data, 18)
    assert struct.unpack_from("<H", data, 28)[0] == 8
    assert struct.unpack_from("<I", data, 30)[0] == 0
    offset = struct.unpack_from("<I", data, 10)[0]
    stride = (width + 3) // 4 * 4

    def sample(x, z):
        ix, iz = math.floor(x), math.floor(z)
        assert 0 <= ix < width - 1 and 0 <= iz < abs(height) - 1
        values = [data[offset + (iz + dz if height > 0 else -height - 1 - iz - dz) * stride + ix + dx] / 10
                  for dx, dz in ((0, 0), (1, 0), (0, 1), (1, 1))]
        fx, fz = x - ix, z - iz
        return (values[0] * (1 - fx) + values[1] * fx) * (1 - fz) + (values[2] * (1 - fx) + values[3] * fx) * fz

    for i, (x, y, z) in enumerate(g.vertices):
        if abs(z) < 1e-7:
            ground = sample(POSITION[0] + x * SCALE, POSITION[2] + y * SCALE)
            g.vertices[i] = (x, y, (ground - POSITION[1] - .04) / SCALE)


def ambient_block(original):
    """Find the unique top-level actor in both authored and Nudge formatting."""
    matches = [match for match in re.finditer(rb"(?ms)^type[ \t]*=[ \t]*\{.*?^\}", original)
               if re.search(rb'\btype\s*=\s*"' + NAME.encode() + rb'_entity"', match[0])]
    assert len(matches) == 1, "Expected one Black Harbor palace actor"
    return matches[0][0]


def native_tokens(block):
    # Nudge drops comments and changes float precision without changing the actor.
    source = re.sub(rb"#[^\r\n]*", b"", block)
    tokens = re.findall(rb'"[^"\r\n]*"|[{}=]|[^\s{}=]+', source)
    result = []
    for token in tokens:
        try:
            result.append(float(token))
        except ValueError:
            result.append(token)
    return result


def section_outputs():
    blocks = {
        "gfx/entities/mapitems_custom.gfx": (
            'objectTypes = {\n\tpdxmesh = {\n\t\tname = "' + NAME + '_mesh"\n'
            '\t\tfile = "' + (MODEL_DIR / FILES[0]).as_posix() + '"\n'
            '\t\tscale = 1\n\t\tcull_distance = 1800\n\t}\n}'
        ),
        "gfx/entities/mapitems_custom.asset": (
            'entity = {\n\tname = "' + NAME + '_entity"\n\tpdxmesh = "' + NAME + '_mesh"\n}'
        ),
        "map/ambient_object.txt": (
            'type = {\n\ttype = "' + NAME + '_entity"\n\tuse_animation = no\n'
            f'\tscale = {SCALE:.6f}\n\talways_visible = yes\n\tobject = {{\n'
            '\t\tname = "' + NAME + '"\n'
            f'\t\tposition = {{ {POSITION[0]:.3f} {POSITION[1]:.3f} {POSITION[2]:.3f} }}\n'
            '\t\trotation = { 0 0 0 }\n\t}\n}'
        ),
    }
    result = {}
    start, end = "# BEGIN " + MARKER, "# END " + MARKER
    for relative, block in blocks.items():
        path = ROOT / relative
        original = path.read_bytes()
        newline = "\r\n" if b"\r\n" in original else "\n"
        section = (start + "\n# Generated by tools/builders/build_adiscord_azhar_palace.py\n"
                   + block + "\n" + end + "\n").replace("\n", newline).encode()
        pattern = re.escape(start.encode()) + rb".*?" + re.escape(end.encode()) + rb"\r?\n?"
        matches = list(re.finditer(pattern, original, flags=re.S))
        assert len(matches) <= 1, path
        if matches:
            match = matches[0]
            result[path] = original[:match.start()] + section + original[match.end():]
        elif relative == "map/ambient_object.txt" and NAME.encode() in original:
            assert native_tokens(ambient_block(original)) == native_tokens(block.encode()), (
                "Palace placement changed in Nudge; reconcile POSITION/SCALE/rotation before rebuilding"
            )
            result[path] = original
        else:
            assert NAME.encode() not in original, f"Unowned palace entry in {path}"
            result[path] = original + newline.encode() + section
    return result


def build_native(stage):
    import bpy
    from mathutils import Vector
    from types import SimpleNamespace

    bpy.ops.wm.read_factory_settings(use_empty=True)
    pdx = load_exporter()
    g = geometry()
    fit_foundation(g)
    obj = g.make_object()
    obj.name = obj.data.name = NAME
    obj.data.materials.append(pdx.create_shader(SimpleNamespace(
        shader=["PdxMeshAdvanced"], diff=[FILES[1]], n=[FILES[2]], spec=[FILES[3]],
    ), "Black basalt, red panels and brass", str(stage)))
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    path = stage / FILES[0]
    pdx.export_meshfile(str(path), exp_selected=True, exp_skel=False, exp_locs=False)
    from io_pdx_mesh import pdx_data

    tree = pdx_data.read_meshfile(str(path))
    for shape in tree.find("object"):
        for mesh in shape.findall("mesh"):
            mesh.attrib["ta"] = [round(value, 5) for value in mesh.attrib["ta"]]
    pdx_data.write_meshfile(str(path), tree)
    bpy.ops.file.pack_all()
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type == "VIEW_3D":
                area.spaces.active.shading.type = "MATERIAL"
                region = area.spaces.active.region_3d
                region.view_location = (0, 0, 8)
                region.view_distance = 65
                region.view_rotation = Vector((42, -57, 39)).to_track_quat("Z", "Y")
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=str(stage / SOURCE.name))
    report = verify_native(stage, pdx)
    report["source_blend_sha256"] = digest(stage / SOURCE.name)
    (stage / "native.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


def verify_native(folder, pdx=None):
    import bpy

    pdx = pdx or load_exporter()
    from io_pdx_mesh import pdx_data

    tree = pdx_data.read_meshfile(str(folder / FILES[0]))
    vertices = triangles = materials = 0
    for shape in tree.find("object"):
        for element in shape.findall("mesh"):
            data = pdx_data.PDXData(element)
            count = len(data.p) // 3
            assert 0 < count < 65536
            assert len(data.n) == count * 3 and len(data.u0) == count * 2 and len(data.ta) == count * 4
            assert all(math.isfinite(v) for v in data.p + data.n + data.u0 + data.ta)
            assert len(data.tri) % 3 == 0 and min(data.tri) >= 0 and max(data.tri) < count
            assert data.material.shader == ["PdxMeshAdvanced"]
            for key, expected in zip(("diff", "n", "spec"), FILES[1:]):
                assert getattr(data.material, key) == [expected]
                raw = (folder / expected).read_bytes()
                assert raw[:4] == b"DDS " and raw[84:88] == b"DXT5"
                assert struct.unpack_from("<I", raw, 28)[0] == 11
            vertices += count
            triangles += len(data.tri) // 3
            materials += 1
    assert triangles < 15000 and materials == 1
    bpy.ops.wm.read_factory_settings(use_empty=True)
    pdx.import_meshfile(str(folder / FILES[0]), imp_locs=False)
    meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    assert len(meshes) == 1
    points = [o.matrix_world @ v.co for o in meshes for v in o.data.vertices]
    bounds = [[round(min(v[i] for v in points), 5), round(max(v[i] for v in points), 5)] for i in range(3)]
    return {
        "files": {name: digest(folder / name) for name in FILES},
        "vertices": vertices, "triangles": triangles, "materials": materials,
        "bounds_blender_xyz": bounds, "native_reimport": True,
        "placement": {"province": PROVINCE, "position": list(POSITION), "scale": SCALE},
        "hoi4_runtime_verified": False,
    }


def render_preview():
    import bpy
    from mathutils import Vector

    verify_native(ROOT / MODEL_DIR)
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.samples = 32
    scene.cycles.use_denoising = True
    scene.render.resolution_x = 1440
    scene.render.resolution_y = 1080
    scene.render.resolution_percentage = 100
    scene.world = bpy.data.worlds.new("Neutral architectural studio")
    scene.world.use_nodes = True
    scene.world.node_tree.nodes["Background"].inputs[0].default_value = (.42, .44, .48, 1)
    scene.world.node_tree.nodes["Background"].inputs[1].default_value = .55
    for material in bpy.data.materials:
        shader = material.node_tree.nodes.get("Principled BSDF") if material.use_nodes else None
        if shader:
            for link in list(shader.inputs["Roughness"].links):
                material.node_tree.links.remove(link)
            shader.inputs["Roughness"].default_value = .72
    bpy.ops.mesh.primitive_plane_add(size=200, location=(0, 0, -1.7))
    floor = bpy.context.object
    floor.name = "Studio floor, not exported"
    mat = bpy.data.materials.new("Warm neutral ground")
    mat.diffuse_color = (.32, .30, .27, 1)
    floor.data.materials.append(mat)
    for location, energy, size in (((-30, -38, 55), 32000, 22), ((32, -3, 28), 11000, 19), ((-5, 32, 45), 27000, 20)):
        bpy.ops.object.light_add(type="AREA", location=location)
        light = bpy.context.object
        light.data.energy = energy
        light.data.size = size
        light.rotation_euler = (Vector((0, 0, 8)) - light.location).to_track_quat("-Z", "Y").to_euler()
    bpy.ops.object.camera_add()
    camera = bpy.context.object
    camera.data.type = "ORTHO"
    scene.camera = camera
    (ROOT / PREVIEW).mkdir(parents=True, exist_ok=True)
    for name, position, target, scale in (
        ("three_quarter", (42, -57, 39), (0, 0, 8), 61),
        ("map", (35, -43, 67), (0, 0, 6), 59),
        ("rear", (-43, 57, 36), (0, 0, 8), 61),
    ):
        camera.location = position
        camera.rotation_euler = (Vector(target) - camera.location).to_track_quat("-Z", "Y").to_euler()
        camera.data.ortho_scale = scale
        scene.render.filepath = str(ROOT / PREVIEW / (name + ".png"))
        bpy.ops.render.render(write_still=True)


def stale_outputs():
    expected = section_outputs()
    expected.update({ROOT / MODEL_DIR / name: data for name, data in textures().items()})
    changed = [str(path.relative_to(ROOT)) for path, data in expected.items()
               if not path.exists() or path.read_bytes() != data]
    if not (ROOT / REPORT).exists():
        return changed + [REPORT.as_posix(), (MODEL_DIR / FILES[0]).as_posix(), SOURCE.as_posix()]
    report = json.loads((ROOT / REPORT).read_text(encoding="utf-8"))
    if report.get("input_sha256") != input_hashes() or not report.get("native_reimport"):
        changed.append(REPORT.as_posix())
    for name, expected_hash in report["files"].items():
        path = ROOT / MODEL_DIR / name
        if not path.exists() or digest(path) != expected_hash:
            changed.append(path.relative_to(ROOT).as_posix())
    if not (ROOT / SOURCE).exists() or digest(ROOT / SOURCE) != report.get("source_blend_sha256"):
        changed.append(SOURCE.as_posix())
    return sorted(set(changed))


def find_blender(explicit):
    candidates = [explicit, os.environ.get("BLENDER_EXE"), shutil.which("blender"),
                  "C:/Program Files/Blender Foundation/Blender 4.5/blender.exe"]
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return str(candidate)
    raise RuntimeError("Blender is required for --apply; provide --blender or BLENDER_EXE")


def run_blender(executable, arguments):
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    subprocess.run([executable, "--background", "--factory-startup", "--python-exit-code", "1",
                    "--python", str(Path(__file__)), "--", *arguments], check=True, env=env)


def apply(executable):
    hashes = input_hashes()
    with tempfile.TemporaryDirectory(prefix="adiscord-azhar-palace-") as directory:
        stage = Path(directory)
        for name, data in textures().items():
            (stage / name).write_bytes(data)
        run_blender(executable, ["--build-dir", str(stage)])
        assert hashes == input_hashes(), "Model inputs changed during export"
        report = json.loads((stage / "native.json").read_text(encoding="utf-8"))
        report["input_sha256"] = hashes
        contents = {ROOT / MODEL_DIR / name: (stage / name).read_bytes() for name in FILES}
        contents[ROOT / SOURCE] = (stage / SOURCE.name).read_bytes()
        contents[ROOT / REPORT] = (json.dumps(report, indent=2) + "\n").encode()
        contents.update(section_outputs())
        for path, data in contents.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            if not path.exists() or path.read_bytes() != data:
                path.write_bytes(data)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--apply", action="store_true")
    mode.add_argument("--preview", action="store_true")
    mode.add_argument("--build-dir", type=Path, help=argparse.SUPPRESS)
    mode.add_argument("--render-native", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--blender")
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else None)
    if args.build_dir:
        build_native(args.build_dir)
        return
    if args.render_native:
        render_preview()
        return
    changed = stale_outputs()
    print(json.dumps({"stale": changed, "apply": args.apply}), flush=True)
    if args.apply and changed:
        apply(find_blender(args.blender))
        changed = stale_outputs()
        assert not changed, changed
    if args.preview:
        if changed:
            raise RuntimeError("Rebuild stale outputs before rendering")
        run_blender(find_blender(args.blender), ["--render-native"])
    raise SystemExit(bool(changed))


if __name__ == "__main__":
    main()
