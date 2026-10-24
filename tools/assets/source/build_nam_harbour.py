"""Build the South Harbour chancellery and its native map placement.

Python: --output PATH --check, then --apply to stage textures.
Blender: --background --python this_file -- --output PATH --build.
Python: --output PATH --install --check, then --apply, then --check.
Only marked sections of the shared map registries belong to this builder.
"""

import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import struct
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_shl_palace import Geometry, dds_bytes, load_exporter

ROOT = Path(__file__).resolve().parents[3]
NAME = "ADISCORD_NAM_harbour"
MODEL_DIR = Path("gfx/models/buildings/NAM_harbour")
POSITION = (3640.0, 10.35, 541.45)
SCALE = 0.14
DECK = 1.2
PREVIEW = ROOT / "docs/development/previews/NAM_harbour"
REPORT = ROOT / "docs/development/model-verification/NAM_harbour.json"
FILES = [f"{NAME}{suffix}" for suffix in (".mesh", "_diffuse.dds", "_normal.dds", "_specular.dds")]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def textures():
    import numpy as np
    from PIL import Image, ImageDraw, ImageFilter

    # Rows: limestone, trim, roof, steel; paving, quay, glass, wood;
    # tank, rust, dark recess, copper; mortar, cargo, fender, highlight.
    colors = [(172, 166, 148), (205, 197, 176), (68, 82, 80), (48, 56, 57),
              (151, 148, 132), (116, 119, 111), (42, 65, 73), (91, 76, 53),
              (115, 124, 124), (113, 72, 48), (27, 31, 32), (103, 99, 74),
              (132, 128, 115), (134, 112, 77), (30, 33, 31), (186, 183, 164)]
    rng = np.random.default_rng(700)
    atlas = Image.new("RGBA", (1024, 1024))
    relief = Image.new("L", atlas.size, 128)
    for index, color in enumerate(colors):
        noise = rng.normal(0, 2.2, (256, 256, 1))
        rgb = np.clip(np.array(color)[None, None, :] + noise, 0, 255).astype("uint8")
        tile = Image.fromarray(rgb).convert("RGBA")
        height = Image.new("L", (256, 256), 128)
        draw = ImageDraw.Draw(tile)
        hd = ImageDraw.Draw(height)
        if index in (0, 4, 5, 12):
            step = 48 if index == 0 else 64
            for row, y in enumerate(range(0, 256, step)):
                dark = tuple(int(c * .77) for c in color)
                draw.line((0, y, 255, y), fill=dark, width=2)
                hd.line((0, y, 255, y), fill=85, width=2)
                for x in range(-48 if row % 2 else 0, 256, 96):
                    draw.line((x, y, x, y + step), fill=dark, width=2)
                    hd.line((x, y, x, y + step), fill=85, width=2)
        if index in (2, 7, 8, 13):
            spacing = 32 if index != 8 else 85
            for x in range(0, 256, spacing):
                draw.line((x, 0, x, 255), fill=tuple(int(c * .72) for c in color), width=3)
                hd.line((x, 0, x, 255), fill=155, width=3)
            if index == 8:
                for y in (62, 126, 190):
                    draw.line((0, y, 255, y), fill=(76, 86, 85), width=3)
                    for x in range(10, 256, 24):
                        draw.ellipse((x, y + 5, x + 2, y + 7), fill=(173, 171, 151))
        if index == 6:
            draw.polygon(((18, 0), (52, 0), (228, 255), (194, 255)), fill=(63, 85, 90))
            draw.rectangle((0, 220, 255, 255), fill=(31, 48, 53))
        offset = (index % 4 * 256, index // 4 * 256)
        atlas.paste(tile, offset)
        relief.paste(height, offset)
    dy, dx = np.gradient(np.asarray(relief.filter(ImageFilter.GaussianBlur(.8)), dtype=float))
    normal = np.zeros((1024, 1024, 4), dtype="uint8")
    normal[:, :, 0] = 255
    normal[:, :, 1] = np.clip(128 - dx * .5, 85, 170)
    normal[:, :, 3] = np.clip(128 + dy * .5, 85, 170)
    spec = Image.new("RGBA", atlas.size, (0, 32, 0, 22))
    draw = ImageDraw.Draw(spec)
    for index, value in ((2, 65), (3, 90), (6, 165), (8, 95), (9, 40)):
        x, y = index % 4 * 256, index // 4 * 256
        draw.rectangle((x, y, x + 255, y + 255), fill=(0, value, 0, value))
    return {f"{NAME}_diffuse.dds": dds_bytes(atlas),
            f"{NAME}_normal.dds": dds_bytes(Image.fromarray(normal)),
            f"{NAME}_specular.dds": dds_bytes(spec)}


class HarbourGeometry(Geometry):
    def prism(self, outline, bottom, top, tile):
        low = [(x, y, bottom) for x, y in outline]
        high = [(x, y, top) for x, y in outline]
        xs, ys = zip(*outline)
        uv = [((x - min(xs)) / (max(xs) - min(xs)),
               (y - min(ys)) / (max(ys) - min(ys))) for x, y in outline]
        self.face(list(reversed(low)), tile, list(reversed(uv)))
        self.face(high, tile, uv)
        for i in range(len(low)):
            j = (i + 1) % len(low)
            self.panel([low[i], low[j], high[j], high[i]], tile, subdivide=True)

    def wing_shell(self, bottom, top, expand=0, tile=0):
        # One concave perimeter avoids coplanar faces at the junction of both wings.
        outline = [(-9 - expand, 2 - expand), (7 - expand, 2 - expand),
                   (7 - expand, -6 - expand), (13 + expand, -6 - expand),
                   (13 + expand, 9 + expand), (-9 - expand, 9 + expand)]
        self.prism(outline, bottom, top, tile)

    def beam(self, a, b, width, tile=3):
        from mathutils import Vector

        a, b = Vector(a), Vector(b)
        axis = (b - a).normalized()
        guide = Vector((0, 0, 1)) if abs(axis.z) < .9 else Vector((0, 1, 0))
        u = axis.cross(guide).normalized() * width / 2
        v = axis.cross(u).normalized() * width / 2
        lower = [a - u - v, a + u - v, a + u + v, a - u + v]
        upper = [point + b - a for point in lower]
        self.face(list(reversed(lower)), tile)
        self.face(upper, tile)
        for i in range(4):
            j = (i + 1) % 4
            self.face([lower[i], lower[j], upper[j], upper[i]], tile)

    def rail(self, a, b, height=.65, spacing=1.3):
        from mathutils import Vector

        a, b = Vector(a), Vector(b)
        count = max(1, math.ceil((b - a).length / spacing))
        for i in range(count + 1):
            p = a.lerp(b, i / count)
            self.beam(p, p + Vector((0, 0, height)), .07)
        for z in (height * .45, height):
            self.beam(a + Vector((0, 0, z)), b + Vector((0, 0, z)), .07)

    def hip_roof(self, x, y, z, w, d, height):
        base = [(x - w / 2, y - d / 2, z), (x + w / 2, y - d / 2, z),
                (x + w / 2, y + d / 2, z), (x - w / 2, y + d / 2, z)]
        if w >= d:
            a, b = (x - (w - d) / 2, y, z + height), (x + (w - d) / 2, y, z + height)
            sides = ([base[0], base[1], b, a], [base[1], base[2], b],
                     [base[2], base[3], a, b], [base[3], base[0], a])
        else:
            a, b = (x, y - (d - w) / 2, z + height), (x, y + (d - w) / 2, z + height)
            sides = ([base[0], base[1], a], [base[1], base[2], b, a],
                     [base[2], base[3], b], [base[3], base[0], a, b])
        for points in sides:
            uv = [((px - x) / w + .5, (py - y) / d + .5) if w >= d
                  else ((py - y) / d + .5, (px - x) / w + .5) for px, py, _ in points]
            self.face(points, 2, uv)
        self.beam(a, b, .12, 3)

    def window(self, x, y, z, w=.95, h=1.55, side=False):
        def part(dx, depth, dz, width, thick, height, tile):
            center = (x + depth, y + dx, z + dz) if side else (x + dx, y + depth, z + dz)
            size = (thick, width, height) if side else (width, thick, height)
            self.box(center, size, tile)

        part(0, 0, 0, w + .23, .12, h + .22, 1)
        part(0, -.075, 0, w, .08, h, 10)
        part(0, -.12, 0, w - .13, .035, h - .13, 6)
        part(0, -.15, 0, .055, .04, h, 3)
        part(0, -.15, h * .1, w, .04, .065, 3)
        part(0, -.08, -h / 2 - .12, w + .4, .38, .15, 1)

    def arch(self, x, y, bottom, radius=1.1, spring=2.1, thickness=.32):
        # Voussoirs and jambs frame a recessed opening instead of a painted arch.
        for sign in (-1, 1):
            self.box((x + sign * (radius + thickness / 2), y, bottom + spring / 2),
                     (thickness, .4, spring), 1)
        for i in range(12):
            a, b = i * math.pi / 12, (i + 1) * math.pi / 12
            ring = [(x + r * math.cos(t), bottom + spring + r * math.sin(t))
                    for r, t in ((radius, a), (radius + thickness, a),
                                 (radius + thickness, b), (radius, b))]
            front = [(px, y - .2, pz) for px, pz in ring]
            rear = [(px, y + .2, pz) for px, pz in ring]
            self.face(front, 1)
            self.face(list(reversed(rear)), 1)
            for j in range(4):
                k = (j + 1) % 4
                self.face([front[j], rear[j], rear[k], front[k]], 1)
        self.box((x, y + .22, bottom + (spring + radius) / 2),
                 (radius * 2, .1, spring + radius), 10)
        self.box((x, y + .13, bottom + spring * .45), (radius * 1.7, .12, spring * .9), 7)


def geometry():
    g = HarbourGeometry()
    # Deep foundation walls extend below sea level; only the upper quay is exposed.
    quay = [(-19, -14), (-12, -14), (-12, -4), (9, -4),
            (9, -10), (15, -10), (15, 11), (-19, 11)]
    g.prism(quay, -9.2, 1, 5)
    g.prism(quay, 1, DECK, 4)
    for x in range(-18, 16, 3):
        g.box((x, -4.09, -.5), (.35, .22, 2.4), 12)
    # The long back wing and short right wing form the chancellery courtyard.
    g.wing_shell(DECK, 9.0)
    for z, h in ((1.6, .35), (4.7, .23), (8.85, .25), (9.1, .25)):
        g.wing_shell(z - h / 2, z + h / 2, .175, 1)
    g.hip_roof(2, 5.5, 9.25, 22.7, 7.7, 2.0)
    g.hip_roof(10, -2, 9.25, 6.7, 8.7, 1.7)
    for x in (-5, -2, 1, 4, 7, 10):
        g.window(x, 1.96, 6.8)
        g.arch(x, 1.74, DECK, .8, 1.65, .24)
    for y in (-4.5, -1.6, 1.0):
        g.window(6.96, y, 6.8, side=True)
        g.window(6.96, y, 3.1, side=True)
    for x in (8.6, 11.4):
        g.window(x, -6.04, 6.8)
        g.window(x, -6.04, 3.1)
    for y in (-4.5, -1.6, 1.3, 4.2, 7.1):
        start = len(g.vertices)
        g.window(13.04, y, 6.8, side=True)
        g.window(13.04, y, 3.1, side=True)
        for i in range(start, len(g.vertices)):
            px, py, pz = g.vertices[i]
            g.vertices[i] = (26.08 - px, py, pz)
    for x in (-5, -2, 1, 4, 7, 10):
        # Rear windows face outward through a mirrored local construction.
        start = len(g.vertices)
        g.window(x, 9.04, 6.8)
        g.window(x, 9.04, 3.1)
        for i in range(start, len(g.vertices)):
            px, py, pz = g.vertices[i]
            g.vertices[i] = (px, 18.08 - py, pz)
    for x in (-2, 5, 11):
        g.box((x, 5.5, 11.2), (.65, .65, 1.7), 0)
        g.box((x, 5.5, 12.08), (.85, .85, .2), 1)
        g.box((x, 5.5, 12.2), (.4, .4, .08), 10)
    # A genuinely open passage under the tower has two supporting piers.
    for x in (-11.25, -6.75):
        g.box((x, -.3, 3.1), (1.5, 6, 3.8), 0)
    g.box((-9, -.3, 9.5), (6, 6, 9.0), 0)
    for z, w, h in ((5.2, 6.4, .35), (6.0, 6.7, .3), (13.8, 6.25, .35),
                     (14.2, 6.7, .3), (14.6, 7.15, .3), (17.65, 7.55, .35)):
        g.box((-9, -.3, z), (w, w, h), 1)
    g.arch(-9, -3.41, DECK, 1.35, 2.1, .45)
    g.window(-9, -3.34, 10.3, 1.1, 2.8)
    g.window(-12.04, -.3, 10.3, 1.1, 2.8, side=True)
    g.box((-9, -.3, 16.15), (6.35, 6.35, 2.65), 6)
    for x in (-12.22, -10.6, -9, -7.4, -5.78):
        for y in (-3.54, 2.94):
            g.box((x, y, 16.15), (.13, .13, 2.75), 3)
    for y in (-1.9, -.3, 1.3):
        for x in (-12.24, -5.76):
            g.box((x, y, 16.15), (.13, .13, 2.75), 3)
    for z in (15.0, 16.25, 17.4):
        g.box((-9, -.3, z), (6.55, 6.55, .12), 3)
    for a, b in (((-12.5, -3.8, 14.8), (-5.5, -3.8, 14.8)),
                 ((-12.5, -3.8, 14.8), (-12.5, 3.2, 14.8)),
                 ((-5.5, -3.8, 14.8), (-5.5, 3.2, 14.8)),
                 ((-12.5, 3.2, 14.8), (-5.5, 3.2, 14.8)),
                 ((-12.4, -3.7, 17.9), (-5.6, -3.7, 17.9)),
                 ((-12.4, 3.1, 17.9), (-5.6, 3.1, 17.9)),
                 ((-12.4, -3.7, 17.9), (-12.4, 3.1, 17.9)),
                 ((-5.6, -3.7, 17.9), (-5.6, 3.1, 17.9))):
        g.rail(a, b)
    g.box((-9, -.3, 18.5), (1.4, 1.4, 1.1), 0)
    g.beam((-9, -.3, 19), (-9, -.3, 22), .12)
    g.beam((-10, -.3, 20.4), (-8, -.3, 20.4), .09)
    # Loading awning, with posts outside the walking line.
    g.box((1, .1, 4.25), (11, 3.3, .18), 2)
    for x in (-4, 1, 6):
        g.beam((x, -1.35, DECK), (x, -1.35, 4.2), .15)
    # Two small rear fuel tanks remain subordinate to the tower silhouette.
    for x, y in ((-15.8, 5), (-15.8, 9)):
        g.lathe(x, y, [(1.65, DECK), (1.65, 6.1), (1.55, 6.35), (.15, 6.52)], 8, 16)
        for z in (1.45, 3.6, 5.8):
            g.lathe(x, y, [(1.69, z), (1.69, z + .12)], 3, 16)
        g.beam((x + 1.7, y, 1.3), (x + 1.7, y, 6.55), .1)
        g.beam((x + 2, y, 1.3), (x + 2, y, 6.55), .1)
        for z in range(2, 7):
            g.beam((x + 1.7, y, z), (x + 2, y, z), .08)
    g.beam((-14, 4, 1.8), (-14, 9, 1.8), .32, 9)
    # A compact riveted dock crane has an open truss, cable and hook.
    g.box((-15.5, -6.5, 1.65), (3.0, 3.3, .9), 3)
    for x in (-16.6, -14.4):
        for y in (-7.6, -5.4):
            g.beam((x, y, 2), (x, y, 5), .23)
    g.box((-15.5, -6.5, 5.2), (3, 3.1, .4), 3)
    g.box((-15.5, -5.9, 6.0), (2.1, 1.8, 1.3), 8)
    g.box((-15.5, -6.83, 6.2), (1.5, .04, .65), 6)
    for x in (-16.2, -14.8):
        a, b = (x, -6.4, 5.6), (x, -13.0, 11.5)
        c = (x, -6.1, 7.1)
        g.beam(a, b, .2)
        g.beam(c, b, .18)
        for i in range(5):
            t, u = i / 5, (i + 1) / 5
            p = tuple(a[j] + (b[j] - a[j]) * t for j in range(3))
            q = tuple(c[j] + (b[j] - c[j]) * u for j in range(3))
            g.beam(p, q, .1)
    g.beam((-16.2, -13, 11.5), (-14.8, -13, 11.5), .2)
    g.beam((-15.5, -13, 11.5), (-15.5, -13, 4.3), .055)
    g.beam((-15.5, -13, 4.3), (-15.2, -13, 3.9), .14)
    g.beam((-15.2, -13, 3.9), (-14.9, -13, 4.2), .14)
    for x, y in ((-18, -12), (-13, -12), (-18, -6), (-8, -3), (-2, -3), (4, -3), (10, -9), (14, -9)):
        g.lathe(x, y, [(.32, DECK), (.23, DECK + .55), (.38, DECK + .58), (.38, DECK + .72)], 3, 8)
    for x, y, z in ((-17, -.5, 1.7), (-17, 1, 1.7), (5, -.5, 1.7), (4.7, .5, 1.7), (5, .1, 2.65), (12, -7.5, 1.7)):
        g.box((x, y, z), (.9, .9, 1), 13)
        for dx in (-.32, .32):
            g.box((x + dx, y, z), (.08, .94, 1.03), 7)
    return g


def build(output, render=True):
    import bpy
    from types import SimpleNamespace

    bpy.ops.wm.read_factory_settings(use_empty=True)
    pdx = load_exporter()
    g = geometry()
    obj = g.make_object()
    obj.name = obj.data.name = NAME
    folder = output / "package" / MODEL_DIR
    obj.data.materials.append(pdx.create_shader(SimpleNamespace(
        shader=["PdxMeshAdvanced"], diff=[f"{NAME}_diffuse.dds"],
        n=[f"{NAME}_normal.dds"], spec=[f"{NAME}_specular.dds"]
    ), "Harbour limestone steel and glass", str(folder)))
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    path = folder / FILES[0]
    pdx.export_meshfile(str(path), exp_selected=True, exp_skel=False, exp_locs=False)
    from io_pdx_mesh import pdx_data

    tree = pdx_data.read_meshfile(str(path))
    for shape in tree.find("object"):
        for mesh in shape.findall("mesh"):
            mesh.attrib["ta"] = [round(value, 5) for value in mesh.attrib["ta"]]
    pdx_data.write_meshfile(str(path), tree)
    bpy.ops.file.pack_all()
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=str(output / "NAM_harbour.blend"))
    verify(output, pdx, render)


def verify(output, pdx=None, render=True):
    import bpy
    from mathutils import Vector

    pdx = pdx or load_exporter()
    from io_pdx_mesh import pdx_data

    folder = output / "package" / MODEL_DIR
    tree = pdx_data.read_meshfile(str(folder / FILES[0]))
    vertices = triangles = materials = 0
    for shape in tree.find("object"):
        for mesh in shape.findall("mesh"):
            data = pdx_data.PDXData(mesh)
            count = len(data.p) // 3
            assert 0 < count < 65536
            assert len(data.n) == count * 3 and len(data.u0) == count * 2 and len(data.ta) == count * 4
            assert all(math.isfinite(v) for v in data.p + data.n + data.u0 + data.ta)
            assert len(data.tri) % 3 == 0 and min(data.tri) >= 0 and max(data.tri) < count
            for i in range(0, len(data.tri), 3):
                a, b, c = [Vector(data.p[j * 3:j * 3 + 3]) for j in data.tri[i:i + 3]]
                assert (b - a).cross(c - a).length > 1e-8
            assert data.material.shader == ["PdxMeshAdvanced"]
            for key in ("diff", "n", "spec"):
                raw = (folder / getattr(data.material, key)[0]).read_bytes()
                assert raw[:4] == b"DDS " and raw[84:88] == b"DXT5"
                assert struct.unpack_from("<I", raw, 28)[0] == 11
            vertices += count
            triangles += len(data.tri) // 3
            materials += 1
    assert triangles < 20000 and materials == 1
    bpy.ops.wm.read_factory_settings(use_empty=True)
    pdx.import_meshfile(str(folder / FILES[0]), imp_locs=False)
    meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    points = [o.matrix_world @ v.co for o in meshes for v in o.data.vertices]
    report = {"files": {name: digest(folder / name) for name in FILES},
              "source_sha256": digest(Path(__file__)),
              "heightmap_sha256": digest(ROOT / "map/heightmap.bmp"),
              "vertices": vertices, "triangles": triangles, "materials": materials,
              "bounds_blender_xyz": [[round(min(v[i] for v in points), 5), round(max(v[i] for v in points), 5)] for i in range(3)],
              "native_reimport": True, "hoi4_runtime_verified": False,
              "placement": {"position": list(POSITION), "scale": SCALE, "province": 16716}}
    (output / "verification.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report), flush=True)
    if not render:
        return
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.samples = 32
    scene.cycles.use_denoising = True
    scene.render.resolution_x, scene.render.resolution_y = 1440, 1080
    scene.render.resolution_percentage = 100
    scene.world = bpy.data.worlds.new("Harbour studio")
    scene.world.use_nodes = True
    scene.world.node_tree.nodes["Background"].inputs[0].default_value = (.22, .27, .31, 1)
    scene.world.node_tree.nodes["Background"].inputs[1].default_value = .6
    for material in bpy.data.materials:
        shader = material.node_tree.nodes.get("Principled BSDF") if material.use_nodes else None
        if shader:
            for link in list(shader.inputs["Roughness"].links):
                material.node_tree.links.remove(link)
            shader.inputs["Roughness"].default_value = .7
    bpy.ops.mesh.primitive_plane_add(size=200, location=(0, 0, -1.0))
    floor = bpy.context.object
    floor.name = "Preview water (not exported)"
    material = bpy.data.materials.new("Water")
    material.diffuse_color = (.065, .12, .15, 1)
    floor.data.materials.append(material)
    for location, energy, size in (((-25, -30, 45), 26000, 20), ((25, -5, 25), 12000, 18), ((0, 30, 40), 24000, 17)):
        bpy.ops.object.light_add(type="AREA", location=location)
        light = bpy.context.object
        light.data.energy, light.data.size = energy, size
        light.rotation_euler = (Vector((0, 0, 6)) - light.location).to_track_quat("-Z", "Y").to_euler()
    bpy.ops.object.camera_add()
    camera = bpy.context.object
    camera.data.type = "ORTHO"
    scene.camera = camera
    PREVIEW.mkdir(parents=True, exist_ok=True)
    for name, location, target, scale in (("front", (36, -52, 33), (-1, 0, 7), 52),
                                          ("map", (22, -42, 65), (-1, 0, 5), 51),
                                          ("rear", (-35, 48, 30), (-1, 0, 7), 52)):
        camera.location = location
        camera.rotation_euler = (Vector(target) - camera.location).to_track_quat("-Z", "Y").to_euler()
        camera.data.ortho_scale = scale
        scene.render.filepath = str(PREVIEW / f"{name}.png")
        bpy.ops.render.render(write_still=True)


def write_changes(contents, apply):
    changed = [str(path) for path, data in contents.items() if not path.exists() or path.read_bytes() != data]
    print(json.dumps({"changed": changed, "apply": apply}), flush=True)
    if apply:
        for path, data in contents.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            if not path.exists() or path.read_bytes() != data:
                path.write_bytes(data)
    return changed


def install(output, apply):
    report = json.loads((output / "verification.json").read_text(encoding="utf-8"))
    folder = output / "package" / MODEL_DIR
    assert report["native_reimport"]
    assert report["source_sha256"] == digest(Path(__file__))
    assert report["heightmap_sha256"] == digest(ROOT / "map/heightmap.bmp")
    assert report["files"] == {name: digest(folder / name) for name in FILES}
    assert report["placement"] == {"position": list(POSITION), "scale": SCALE, "province": 16716}
    contents = {ROOT / MODEL_DIR / name: (folder / name).read_bytes() for name in FILES}
    blocks = {
        "gfx/entities/mapitems_custom.gfx": (
            f'objectTypes = {{\n\tpdxmesh = {{\n\t\tname = "{NAME}_mesh"\n'
            f'\t\tfile = "{(MODEL_DIR / FILES[0]).as_posix()}"\n'
            '\t\tscale = 1\n\t\tcull_distance = 1800\n\t}\n}'),
        "gfx/entities/mapitems_custom.asset": (
            f'entity = {{\n\tname = "{NAME}_entity"\n\tpdxmesh = "{NAME}_mesh"\n}}'),
        "map/ambient_object.txt": (
            f'type = {{\n\ttype = "{NAME}_entity"\n\tuse_animation = no\n'
            f'\tscale = {SCALE:.6f}\n\talways_visible = yes\n\tobject = {{\n\t\tname = "{NAME}"\n'
            f'\t\tposition = {{ {POSITION[0]:.3f} {POSITION[1]:.3f} {POSITION[2]:.3f} }}\n'
            '\t\trotation = { 0 0 0 }\n\t}\n}')}
    start, end = "# BEGIN ADISCORD NAM harbour", "# END ADISCORD NAM harbour"
    for relative, block in blocks.items():
        path = ROOT / relative
        original = path.read_bytes()
        newline = "\r\n" if b"\r\n" in original else "\n"
        section = (start + "\n# Generated by tools/assets/source/build_nam_harbour.py\n" + block + "\n" + end + "\n").replace("\n", newline).encode()
        pattern = re.escape(start.encode()) + rb".*?" + re.escape(end.encode()) + rb"\r?\n?"
        matches = list(re.finditer(pattern, original, flags=re.S))
        assert len(matches) <= 1
        if matches:
            match = matches[0]
            contents[path] = original[:match.start()] + section + original[match.end():]
        else:
            assert NAME.encode() not in original
            contents[path] = original + newline.encode() + section
    contents[REPORT] = (json.dumps(report, indent=2) + "\n").encode()
    return write_changes(contents, apply)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--install", action="store_true")
    parser.add_argument("--no-render", action="store_true")
    mode = parser.add_mutually_exclusive_group(required=True)
    for name in ("check", "apply", "build", "verify"):
        mode.add_argument("--" + name, action="store_true")
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else None)
    output = args.output.resolve()
    if args.build:
        build(output, render=not args.no_render)
    elif args.verify:
        verify(output, render=not args.no_render)
    else:
        changed = install(output, args.apply) if args.install else write_changes(
            {output / "package" / MODEL_DIR / name: raw for name, raw in textures().items()}, args.apply)
        if args.check:
            raise SystemExit(bool(changed))


if __name__ == "__main__":
    main()
