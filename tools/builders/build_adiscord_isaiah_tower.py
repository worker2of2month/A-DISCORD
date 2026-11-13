"""Build Isaiah's stepped clock tower and its permanent native map actor.

--check is read-only; --apply exports stale assets with Blender/io_pdx_mesh.
--preview renders the reimported native mesh into disposable development previews.
The rear facade is local +Y; the native actor rotates about map Y.
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

NAME = "ADISCORD_isaiah_clock_tower"
MODEL_DIR = Path("gfx/models/buildings/Isaiah_clock_tower")
REPORT = Path("docs/development/model-verification/Isaiah_clock_tower.json")
PREVIEW = Path("docs/development/previews/Isaiah_clock_tower")
POSITION = (2901.5, 10.36, 618.5)
SCALE = 0.12
YAW = 0.349066
PROVINCE = 6192
PROVINCE_RGB = (168, 202, 71)
MARKER = "ADISCORD Isaiah clock tower"
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
    """Padded facade atlas and a high-contrast dial, without separate materials."""
    import numpy as np
    from PIL import Image, ImageDraw, ImageFilter

    colors = (
        (89, 94, 94), (119, 122, 117), (93, 79, 55), (93, 97, 95),
        (30, 39, 41), (55, 63, 64), (106, 109, 103), (65, 56, 42),
        (157, 130, 79), (20, 28, 31), (78, 84, 82), (50, 59, 59),
        (27, 32, 33), (96, 100, 98), (89, 94, 92), (175, 165, 133),
    )
    rng = np.random.default_rng(PROVINCE)
    atlas = Image.new("RGBA", (1024, 1024))
    relief = Image.new("L", atlas.size, 128)
    for index, color in enumerate(colors):
        noise = rng.normal(0, 3.5, (256, 256, 1))
        rgb = np.clip(np.asarray(color)[None, None, :] + noise, 0, 255).astype("uint8")
        tile = Image.fromarray(rgb).convert("RGBA")
        height = Image.new("L", (256, 256), 128)
        draw = ImageDraw.Draw(tile)
        hd = ImageDraw.Draw(height)
        if index in (0, 1, 6, 10):
            for row, y in enumerate(range(0, 256, 32)):
                draw.line((0, y, 255, y), fill=tuple(int(c * .79) for c in color))
                hd.line((0, y, 255, y), fill=106)
                for x in range(-64 if row % 2 else 0, 256, 128):
                    draw.line((x, y, x, y + 32), fill=tuple(int(c * .85) for c in color))
        if index == 3:
            # Four storeys per mapped panel keep windows regular on narrow facades.
            columns = 3 if index == 3 else 1
            for column in range(columns):
                cx = (column + .5) * 256 / columns
                width = 38 if columns == 3 else 100
                for y in (24, 80, 136, 192):
                    box = (cx - width / 2, y, cx + width / 2, y + 37)
                    draw.rectangle((box[0] - 4, y - 3, box[2] + 4, y + 42), fill=(59, 64, 62))
                    draw.rectangle(box, fill=(22, 32, 36))
                    draw.rectangle((box[0] + 3, y + 3, cx - 2, y + 15), fill=(48, 63, 68))
                    draw.line((cx, y, cx, y + 37), fill=(91, 93, 85), width=2)
                    draw.line((box[0], y + 19, box[2], y + 19), fill=(73, 79, 75), width=2)
                    draw.line((box[0] - 4, y + 42, box[2] + 4, y + 42), fill=(126, 129, 119), width=2)
                    hd.rectangle(box, fill=99)
        if index in (0, 1, 3, 5, 6, 10, 13, 14):
            # Broad mottling and long rain streaks survive the map's mip levels.
            coarse = rng.integers(135, 256, (12, 9), dtype="uint8")
            mottling = Image.fromarray(coarse).resize((256, 256), Image.Resampling.BICUBIC)
            grime = Image.new("L", (256, 256))
            gd = ImageDraw.Draw(grime)
            for _ in range(30):
                x = int(rng.integers(4, 252))
                y = int(rng.choice((8, 61, 117, 173, 229)))
                length = int(rng.integers(20, 110))
                gd.line((x, y, x, min(255, y + length)),
                        fill=int(rng.integers(35, 100)), width=int(rng.integers(2, 9)))
            gd.line((0, 9, 255, 9), fill=70, width=12)
            stains = np.asarray(grime.filter(ImageFilter.GaussianBlur(2)), dtype=float) / 255
            factor = (.64 + .36 * np.asarray(mottling, dtype=float) / 255) * (1 - stains * .65)
            aged = np.asarray(tile).copy()
            aged[:, :, :3] = np.clip(aged[:, :, :3] * factor[:, :, None], 0, 255).astype("uint8")
            tile = Image.fromarray(aged)
        if index == 12:
            draw.ellipse((13, 13, 243, 243), outline=(151, 123, 71), width=3)
            for tick in range(60):
                angle = tick * math.tau / 60
                outer = 109
                inner = 91 if tick % 5 == 0 else 102
                a = (128 + inner * math.sin(angle), 128 - inner * math.cos(angle))
                b = (128 + outer * math.sin(angle), 128 - outer * math.cos(angle))
                draw.line((a, b), fill=(227, 197, 127), width=5 if tick % 5 == 0 else 2)
            # Broad tapered hands remain legible after mipmapping.
            for angle, length, width in ((-math.pi / 15, 78, 5), (math.pi / 12, 98, 3)):
                dx, dy = math.sin(angle), -math.cos(angle)
                px, py = -dy * width, dx * width
                draw.polygon(((128 + px, 128 + py), (128 + dx * length, 128 + dy * length),
                              (128 - px, 128 - py), (128 - dx * 15, 128 - dy * 15)),
                             fill=(244, 218, 157))
            draw.ellipse((121, 121, 135, 135), fill=(209, 172, 99))
        offset = ((index % 4) * 256, (index // 4) * 256)
        atlas.paste(tile, offset)
        relief.paste(height, offset)
    values = np.asarray(relief.filter(ImageFilter.GaussianBlur(.7)), dtype=float)
    dy, dx = np.gradient(values)
    normal = np.zeros((1024, 1024, 4), dtype="uint8")
    normal[:, :, 0] = 255
    normal[:, :, 1] = np.clip(128 - dx * .55, 80, 176)
    normal[:, :, 3] = np.clip(128 + dy * .55, 80, 176)
    specular = Image.new("RGBA", atlas.size, (0, 26, 0, 25))
    draw = ImageDraw.Draw(specular)
    for index in (2, 7, 8, 15):
        x, y = index % 4 * 256, index // 4 * 256
        draw.rectangle((x, y, x + 255, y + 255), fill=(0, 110, 0, 85))
    return {
        FILES[1]: dds_bytes(atlas),
        FILES[2]: dds_bytes(Image.fromarray(normal)),
        FILES[3]: dds_bytes(specular),
    }


class TowerGeometry(Geometry):
    def panel(self, points, tile, subdivide=False):
        self.face(points, tile)

    def ledge(self, x, y, z, width, depth):
        self.box((x, y, z), (width + .3, depth + .3, .28), 5)
        self.box((x, y, z + .26), (width + .65, depth + .65, .25), 1)
        self.box((x, y, z + .46), (width + .45, depth + .45, .15), 5)

    def window_strip(self, center, width, height, axis, side, tile):
        """Geometry defines the glass and frame edges independently of atlas mipmaps."""
        horizontal = 1 - axis

        def rectangle(u, v, w, h, outward, material):
            points = []
            for du, dv in ((-w / 2, -h / 2), (w / 2, -h / 2),
                           (w / 2, h / 2), (-w / 2, h / 2)):
                p = list(center)
                p[horizontal] += u + du
                p[axis] += side * outward
                p[2] += v + dv
                points.append(tuple(p))
            if (axis == 1 and side > 0) or (axis == 0 and side < 0):
                points.reverse()
            self.face(points, material)

        rectangle(0, 0, width, height, 0, tile)
        storey = height / 4
        glass_width = width * .57
        glass_height = storey * .66
        for row in range(4):
            z = -height / 2 + (row + .5) * storey
            rectangle(0, z, glass_width + .14, glass_height + .14, .035, 1)
            rectangle(0, z, glass_width, glass_height, .055, 4)
            rectangle(0, z, .085, glass_height, .075, 1)
            rectangle(0, z, glass_width, .085, .075, 1)

    def block(self, x, y, bottom, top, width, depth, rear_clock=False):
        self.box((x, y, (bottom + top) / 2), (width, depth, top - bottom), 0)
        self.ledge(x, y, top, width, depth)
        rows = max(1, round((top - bottom) / 9))
        # Each facade panel has its own UV island, preventing stretched storeys.
        for side in (-1, 1):
            columns = max(1, round(width / 2.4))
            # The rear clock panel replaces this facade, including projecting ribs.
            if rear_clock and side == 1:
                columns = 0
            for column in range(columns):
                px = x - width / 2 + (column + .5) * width / columns
                for row in range(rows):
                    height = (top - bottom - 1) / rows
                    pz = bottom + .5 + (row + .5) * height
                    self.window_strip((px, y + side * (depth / 2 + .02), pz),
                                      width / columns - .6, height, 1, side,
                                      13 + (column + row) % 2)
                self.box((px - width / columns / 2 + .22, y + side * (depth / 2 + .34),
                          (bottom + top) / 2), (.48, .78, top - bottom + .7), 1)
            columns = max(1, round(depth / 2.4))
            for column in range(columns):
                py = y - depth / 2 + (column + .5) * depth / columns
                for row in range(rows):
                    height = (top - bottom - 1) / rows
                    self.window_strip((x + side * (width / 2 + .02), py,
                                       bottom + .5 + (row + .5) * height),
                                      depth / columns - .6, height, 0, side,
                                      13 + (column + row) % 2)
                self.box((x + side * (width / 2 + .34), py - depth / columns / 2 + .22,
                          (bottom + top) / 2), (.78, .48, top - bottom + .7), 1)

    def pinnacle(self, x, y, bottom, height, width):
        self.box((x, y, bottom + .2), (width * 1.3, width * 1.3, .4), 1)
        self.box((x, y, bottom + height * .34), (width, width, height * .6), 0)
        self.box((x, y, bottom + height * .65), (width * .7, width * .7, height * .28), 1)
        self.lathe(x, y, [(width * .38, bottom + height * .79),
                         (.04, bottom + height)], 2, 4)

    def clock(self, y, z, radius):
        # Real raised bronze rim around a circular, padded dial UV island.
        segments = 64
        for i in range(segments):
            a, b = i * math.tau / segments, (i + 1) * math.tau / segments
            def point(angle, r, py):
                return (r * math.sin(angle), py, z + r * math.cos(angle))
            self.face([point(a, radius, y), point(b, radius, y),
                       point(b, radius - .22, y + .18), point(a, radius - .22, y + .18)], 8)
            self.face([point(a, radius, y - .25), point(b, radius, y - .25),
                       point(b, radius, y), point(a, radius, y)], 7)
            self.face([(0, y + .05, z), point(a, radius - .22, y + .05),
                       point(b, radius - .22, y + .05)], 12,
                      [(.5, .5), (.5 + .49 * math.sin(a), .5 + .49 * math.cos(a)),
                       (.5 + .49 * math.sin(b), .5 + .49 * math.cos(b))])


def geometry():
    g = TowerGeometry()
    g.box((0, 0, .85), (42, 26, 1.7), 5)
    g.box((0, 0, 1.8), (42, 26, .2), 6)
    g.box((0, 0, 3.55), (39.6, 21.6, 3.3), 0)
    g.ledge(0, 0, 5.1, 39.6, 21.6)
    g.block(0, 0, 5.6, 16, 39, 21)
    g.block(0, 1, 16.5, 25, 30, 18)
    g.block(0, 1, 25.5, 38, 18, 13)
    # Upper tower has a dedicated rear clock bay above the office floors.
    g.block(0, 1, 38.5, 49.5, 10.4, 9, rear_clock=True)
    g.box((0, 5.72, 44), (9.6, .44, 9.5), 0)
    g.clock(6.05, 44.1, 3.6)
    for x in (-4.7, 4.7):
        g.box((x, 6.05, 44.05), (.62, .78, 10.1), 1)
    g.block(0, 1, 50, 55.5, 6, 5.5)
    g.box((0, 1, 56.4), (3.5, 3.3, .8), 1)
    g.lathe(0, 1, [(1.7, 56.8), (1.35, 58), (.65, 59.5), (.18, 62.5)], 1, 8)
    g.lathe(0, 1, [(.22, 62.5), (.05, 64)], 8, 8)
    for side in (-1, 1):
        g.block(side * 15.3, 0, 16.5, 23, 8, 18)
        for y in (-7.5, 7.5):
            g.pinnacle(side * 17.8, y, 23.5, 6.5, 1.6)
            g.box((side * 18.5, y, 14.5), (1, 1.2, 18), 1)
        for y in (-4.8, 6.8):
            g.pinnacle(side * 7.7, y, 38.5, 5.7, 1.3)
        for y in (-2.9, 4.9):
            g.pinnacle(side * 4.3, y, 50, 4.5, 1)
        for y in (-5.8, 7.8):
            g.box((side * 7.8, y, 31.8), (1, 1, 13.3), 1)
    # Projecting entrance with deep doors and an accessible stair on local -Y.
    g.box((0, -10, 5.4), (8, 2.4, 7), 0)
    g.ledge(0, -10, 9, 8.6, 3)
    for x in (-2.5, 0, 2.5):
        g.box((x, -11.24, 4.9), (1.7, .12, 5.4), 9)
        g.box((x, -11.35, 4.4), (1.3, .12, 4.3), 7)
        g.box((x, -11.43, 4.5), (.08, .06, 4.2), 8)
    for step in range(5):
        h = .15 * (step + 1)
        g.box((0, -12.7 + step * .28, 1.9 + h / 2), (8.4, .3, h), 1)
    return g


def map_position(x, y):
    """Blender XY to native XZ after the actor's Y-axis rotation."""
    c, s = math.cos(YAW), math.sin(YAW)
    return (POSITION[0] + SCALE * (c * x + s * y),
            POSITION[2] + SCALE * (-s * x + c * y))


def height_sampler():
    """Read native map elevations once for terrain fitting and preview placement."""
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

    return sample


def fit_foundation(g):
    """Only the underside conforms to terrain; the paving remains level."""
    sample = height_sampler()
    for i, (x, y, z) in enumerate(g.vertices):
        if abs(z) < 1e-7:
            ground = sample(*map_position(x, y))
            g.vertices[i] = (x, y, (ground - POSITION[1] - .04) / SCALE)


def ambient_block(original):
    """Find the unique top-level actor in both authored and Nudge formatting."""
    matches = [match for match in re.finditer(rb"(?ms)^type[ \t]*=[ \t]*\{.*?^\}", original)
               if re.search(rb'\btype\s*=\s*"' + NAME.encode() + rb'_entity"', match[0])]
    assert len(matches) == 1, "Expected one Isaiah clock tower actor"
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
            f'\t\trotation = {{ 0 {YAW:.6f} 0 }}\n\t}}\n}}'
        ),
    }
    result = {}
    start, end = "# BEGIN " + MARKER, "# END " + MARKER
    for relative, block in blocks.items():
        path = ROOT / relative
        original = path.read_bytes()
        newline = "\r\n" if b"\r\n" in original else "\n"
        section = (start + "\n# Generated by tools/builders/build_adiscord_isaiah_tower.py\n"
                   + block + "\n" + end + "\n").replace("\n", newline).encode()
        pattern = re.escape(start.encode()) + rb".*?" + re.escape(end.encode()) + rb"\r?\n?"
        matches = list(re.finditer(pattern, original, flags=re.S))
        assert len(matches) <= 1, path
        if matches:
            match = matches[0]
            result[path] = original[:match.start()] + section + original[match.end():]
        elif relative == "map/ambient_object.txt" and NAME.encode() in original:
            assert native_tokens(ambient_block(original)) == native_tokens(block.encode()), (
                "Tower placement changed in Nudge; reconcile POSITION/SCALE/rotation before rebuilding"
            )
            result[path] = original
        else:
            assert NAME.encode() not in original, f"Unowned tower entry in {path}"
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
    ), "Weathered limestone, dark glazing and aged bronze", str(stage)))
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
    report = verify_native(stage, pdx)
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
        "placement": {"province": PROVINCE, "position": list(POSITION),
                      "scale": SCALE, "rotation": [0, YAW, 0]},
        "hoi4_runtime_verified": False,
    }


def render_preview():
    import bpy
    from mathutils import Vector

    verify_native(ROOT / MODEL_DIR)
    for obj in bpy.context.scene.objects:
        if obj.type == "MESH":
            obj.rotation_euler.z = -YAW
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
    ground = (height_sampler()(POSITION[0], POSITION[2]) - POSITION[1]) / SCALE
    bpy.ops.mesh.primitive_plane_add(size=200, location=(0, 0, ground))
    floor = bpy.context.object
    floor.name = "Studio floor at landmark center elevation, not exported"
    mat = bpy.data.materials.new("Warm neutral ground")
    mat.diffuse_color = (.32, .30, .27, 1)
    floor.data.materials.append(mat)
    for location, energy, size in (((-30, -38, 55), 32000, 22), ((32, -3, 28), 11000, 19), ((-5, 32, 45), 27000, 20)):
        bpy.ops.object.light_add(type="AREA", location=location)
        light = bpy.context.object
        light.data.energy = energy
        light.data.size = size
        light.rotation_euler = (Vector((0, 0, 27)) - light.location).to_track_quat("-Z", "Y").to_euler()
    bpy.ops.object.camera_add()
    camera = bpy.context.object
    camera.data.type = "ORTHO"
    scene.camera = camera
    (ROOT / PREVIEW).mkdir(parents=True, exist_ok=True)
    for name, position, target, scale in (
        ("three_quarter", (70, -95, 65), (0, 0, 30), 104),
        ("map", (-70, 86, 110), (0, 0, 25), 100),
        ("rear", (-70, 95, 65), (0, 0, 30), 104),
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
        return changed + [REPORT.as_posix(), (MODEL_DIR / FILES[0]).as_posix()]
    report = json.loads((ROOT / REPORT).read_text(encoding="utf-8"))
    if report.get("input_sha256") != input_hashes() or not report.get("native_reimport"):
        changed.append(REPORT.as_posix())
    for name, expected_hash in report["files"].items():
        path = ROOT / MODEL_DIR / name
        if not path.exists() or digest(path) != expected_hash:
            changed.append(path.relative_to(ROOT).as_posix())
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
    with tempfile.TemporaryDirectory(prefix="adiscord-isaiah-clock-") as directory:
        stage = Path(directory)
        for name, data in textures().items():
            (stage / name).write_bytes(data)
        run_blender(executable, ["--build-dir", str(stage)])
        assert hashes == input_hashes(), "Model inputs changed during export"
        report = json.loads((stage / "native.json").read_text(encoding="utf-8"))
        report["input_sha256"] = hashes
        contents = {ROOT / MODEL_DIR / name: (stage / name).read_bytes() for name in FILES}
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
