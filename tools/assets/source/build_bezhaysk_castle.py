"""Build and install the Grayson castle at Bezhaysk's existing victory point.

Python: --output PATH --check, then --apply to stage the material atlas.
Blender: --background --python this_file -- --output PATH --build
Python: --output PATH --install --check, then --apply, then --check.
The installer owns only its marked sections of the shared map registries.
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
NAME = "ADISCORD_BJK_grayson_castle"
MODEL_DIR = Path("gfx/models/buildings/BJK_castle")
POSITION = (3782.7, 11.3, 968.2)
SCALE = 0.1
FLOOR = 3.0
FILES = [f"{NAME}{suffix}" for suffix in (".mesh", "_diffuse.dds", "_normal.dds", "_specular.dds")]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def textures():
    import numpy as np
    from PIL import Image, ImageDraw, ImageFilter

    colors = [
        (115, 117, 112), (155, 150, 134), (178, 164, 131), (52, 62, 78),
        (67, 49, 37), (96, 101, 99), (126, 121, 109), (110, 31, 64),
        (197, 154, 65), (24, 30, 33), (103, 99, 86), (116, 102, 73),
        (47, 55, 66), (177, 151, 102), (83, 30, 67), (195, 184, 156),
    ]
    rng = np.random.default_rng(16439)
    atlas = Image.new("RGBA", (1024, 1024))
    relief = Image.new("L", atlas.size, 128)
    for index, color in enumerate(colors):
        noise = rng.normal(0, 3.2, (256, 256, 1))
        rgb = np.clip(np.array(color)[None, None, :] + noise, 0, 255).astype("uint8")
        tile = Image.fromarray(rgb).convert("RGBA")
        height = Image.new("L", (256, 256), 128)
        draw, hd = ImageDraw.Draw(tile), ImageDraw.Draw(height)
        if index in (0, 1, 5, 6, 10):
            step = 48 if index in (0, 5) else 64
            for row, y in enumerate(range(0, 256, step)):
                dark = tuple(int(c * 0.68) for c in color)
                draw.line((0, y, 255, y), fill=dark, width=3)
                hd.line((0, y, 255, y), fill=75, width=3)
                for x in range(-64 if row % 2 else 0, 256, 96):
                    draw.line((x, y, x, y + step), fill=dark, width=3)
                    hd.line((x, y, x, y + step), fill=80, width=3)
        if index in (3, 12):
            for row, y in enumerate(range(0, 256, 24)):
                draw.line((0, y, 255, y), fill=(27, 33, 44), width=3)
                hd.line((0, y, 255, y), fill=80, width=3)
                for x in range(-24 if row % 2 else 0, 256, 48):
                    draw.line((x, y, x, y + 24), fill=(34, 41, 52), width=2)
        if index == 4:
            for x in range(0, 256, 32):
                draw.line((x, 0, x, 255), fill=(33, 27, 23), width=3)
            for y in (40, 208):
                draw.rectangle((0, y, 255, y + 10), fill=(30, 34, 35))
                for x in range(14, 256, 32):
                    draw.ellipse((x, y + 3, x + 3, y + 6), fill=(113, 114, 104))
        if index == 7:
            with Image.open(ROOT / "gfx/flags/BJK.tga") as flag:
                tile = flag.convert("RGBA").resize((256, 256), Image.Resampling.LANCZOS)
        if index == 14:
            draw.rectangle((12, 8, 244, 248), outline=(204, 168, 82), width=9)
            draw.rectangle((119, 40, 137, 206), fill=(225, 194, 119))
            draw.rectangle((76, 137, 180, 150), fill=(225, 194, 119))
            draw.polygon(((128, 22), (111, 61), (145, 61)), fill=(225, 194, 119))
            draw.ellipse((115, 199, 141, 222), fill=(225, 194, 119))
        offset = ((index % 4) * 256, (index // 4) * 256)
        atlas.paste(tile, offset)
        relief.paste(height, offset)
    values = np.asarray(relief.filter(ImageFilter.GaussianBlur(1.2)), dtype=float)
    dy, dx = np.gradient(values)
    normals = np.zeros((1024, 1024, 4), dtype="uint8")
    normals[:, :, 0] = 255
    normals[:, :, 1] = np.clip(128 - dx * 0.65, 80, 176)
    normals[:, :, 3] = np.clip(128 + dy * 0.65, 80, 176)
    specular = Image.new("RGBA", atlas.size, (0, 35, 0, 28))
    sd = ImageDraw.Draw(specular)
    for index, value in ((8, (0, 150, 0, 125)), (9, (0, 70, 0, 80))):
        x, y = (index % 4) * 256, (index // 4) * 256
        sd.rectangle((x, y, x + 255, y + 255), fill=value)
    return {
        f"{NAME}_diffuse.dds": dds_bytes(atlas),
        f"{NAME}_normal.dds": dds_bytes(Image.fromarray(normals)),
        f"{NAME}_specular.dds": dds_bytes(specular),
    }


class CastleGeometry(Geometry):
    def lathe(self, x, y, profile, tile=1, segments=16):
        rings = [profile[0]]
        for (r0, z0), (r1, z1) in zip(profile, profile[1:]):
            count = max(1, math.ceil(abs(z1 - z0) / 2.8)) if tile in (0, 1, 5) else 1
            for j in range(1, count + 1):
                t = j / count
                rings.append((r0 + (r1 - r0) * t, z0 + (z1 - z0) * t))
        start = len(self.faces)
        super().lathe(x, y, rings, tile, segments)
        if tile in (0, 1, 3, 5):
            # One tile spans several facets, keeping masonry and slates at wall scale.
            col, row = tile % 4, tile // 4
            for band in range(len(rings) - 1):
                for i in range(segments):
                    u, v = (i % 5) / 5, (i % 5 + 1) / 5
                    self.uvs[start + band * segments + i] = [
                        ((col + .035 + .93 * a) / 4, (3 - row + .035 + .93 * b) / 4)
                        for a, b in ((u, 0), (v, 0), (v, 1), (u, 1))
                    ]

    def wedge(self, x, y, inner, outer, a, b, bottom, top, tile=1):
        points = [(x + r * math.cos(t), y + r * math.sin(t)) for r, t in (
            (inner, a), (outer, a), (outer, b), (inner, b)
        )]
        low = [(px, py, bottom) for px, py in points]
        high = [(px, py, top) for px, py in points]
        self.face(list(reversed(low)), tile)
        self.face(high, tile)
        for i in range(4):
            j = (i + 1) % 4
            self.face([low[i], low[j], high[j], high[i]], tile)

    def tower(self, x, y, radius, height, roof=False):
        top = FLOOR + height
        self.lathe(x, y, [(radius + .35, FLOOR), (radius + .35, FLOOR + .5),
                         (radius, FLOOR + .9), (radius, top - .65)], 0, 20)
        self.lathe(x, y, [(radius, top - .65), (radius + .28, top - .3),
                         (radius + .28, top)], 2, 20)
        for level in (FLOOR + 1.15, top - 3.0):
            self.lathe(x, y, [(radius + .06, level), (radius + .06, level + .18)], 1, 20)
        for angle in (-math.pi / 2, 0, math.pi / 2, math.pi):
            cx, cy = x + (radius + .015) * math.cos(angle), y + (radius + .015) * math.sin(angle)
            dx, dy = -.15 * math.sin(angle), .15 * math.cos(angle)
            self.face([(cx - dx, cy - dy, top - 2.6), (cx + dx, cy + dy, top - 2.6),
                       (cx + dx, cy + dy, top - 1.5), (cx - dx, cy - dy, top - 1.5)], 9)
        if roof:
            self.lathe(x, y, [(radius + .6, top), (radius + .6, top + .2),
                             (.08, top + 4.9), (.06, top + 5.05)], 3, 20)
            self.lathe(x, y, [(.085, top + 4.9), (.085, top + 5.6)], 8, 8)
        else:
            for i in range(10):
                a = i * math.tau / 10
                self.wedge(x, y, radius - .35, radius + .28, a, a + .34, top, top + .85, 1)

    def wall(self, center, size, along_x):
        self.box(center, size, 0)
        x, y, z = center
        w, d, h = size
        top = z + h / 2
        self.box((x, y, top + .1), (w + .16, d + .16, .2), 2)
        count = max(2, round((w if along_x else d) / 1.45))
        for i in range(count):
            t = (i + .5) / count - .5
            self.box((x + t * w if along_x else x, y if along_x else y + t * d, top + .65),
                     (0.8 if along_x else w, d if along_x else .8, .95), 1)

    def hip_roof(self, x, y, z, w, d, height):
        base = [(x - w / 2, y - d / 2, z), (x + w / 2, y - d / 2, z),
                (x + w / 2, y + d / 2, z), (x - w / 2, y + d / 2, z)]
        a, b = (x, y - d * .23, z + height), (x, y + d * .23, z + height)
        self.face([base[0], base[1], a], 3)
        self.face([base[1], base[2], b, a], 3)
        self.face([base[2], base[3], b], 3)
        self.face([base[3], base[0], a, b], 3)
        self.box((x, y, z + height), (.18, d * .46 + .16, .18), 8)

    def flag(self, x, y, z, width=2.7):
        self.lathe(x, y, [(.07, z), (.07, z + 3.8)], 8, 8)
        # Two sides share the national flag; the silhouette is a static wind fold.
        for i in range(6):
            u, v = i / 6, (i + 1) / 6
            def point(t, h):
                return (x + width * t, y + .27 * math.sin(t * math.tau), z + 3.55 - h - .28 * t)
            points = [point(u, 1.6), point(v, 1.6), point(v, 0), point(u, 0)]
            uv = [(u, 0), (v, 0), (v, 1), (u, 1)]
            self.face(points, 7, uv)
            self.face([(a, b + .025, c) for a, b, c in reversed(points)], 7, list(reversed(uv)))

    def arch(self):
        radius, spring, top = 2.3, FLOOR + 2.5, FLOOR + 6.7
        # Each prism fills the area above the arch, leaving a real walk-through opening.
        for i in range(16):
            a, b = i * math.pi / 16, (i + 1) * math.pi / 16
            xa, za = radius * math.cos(a), spring + radius * math.sin(a)
            xb, zb = radius * math.cos(b), spring + radius * math.sin(b)
            front = [(xa, -8.3, za), (xb, -8.3, zb), (xb, -8.3, top), (xa, -8.3, top)]
            back = [(x, -6.7, z) for x, _, z in front]
            self.face(front, 1)
            self.face(list(reversed(back)), 0)
            for j in range(4):
                k = (j + 1) % 4
                self.face([front[j], back[j], back[k], front[k]], 1)
        for side in (-1, 1):
            self.box((side * 2.57, -7.5, FLOOR + 2.5), (.54, 1.85, 5), 1)
            # Open wooden leaves sit against the inner gate walls.
            self.box((side * 2.08, -5.75, FLOOR + 1.8), (.18, 2.0, 3.55), 4)
        for i in range(9):
            self.box((-1.7 + i * .425, -7.15, FLOOR + 4.35), (.06, .08, .7), 9)


def geometry():
    g = CastleGeometry()
    for x in (-8.15, 8.15):
        g.box((x, 0, FLOOR / 2), (11.7, 22, FLOOR), 5)
    g.box((0, 1.25, FLOOR / 2), (4.6, 19.5, FLOOR), 5)
    g.box((0, 1, FLOOR + .05), (26, 18, .1), 10)
    for x in (-7.65, 7.65):
        g.box((x, -9, FLOOR + .05), (10.7, 2, .1), 10)
    for x in (-10, 10):
        g.wall((x, 0, FLOOR + 2.75), (1.25, 15, 5.5), False)
    g.wall((0, 7.5, FLOOR + 2.75), (20, 1.25, 5.5), True)
    for x in (-6.45, 6.45):
        g.wall((x, -7.5, FLOOR + 2.9), (7.75, 1.6, 5.8), True)
    g.arch()
    g.wall((0, -7.5, FLOOR + 6.65), (5.7, 1.85, .3), True)
    for x in (-10, 10):
        g.tower(x, -7.5, 2.15, 7.5)
        g.tower(x, 7.2, 2.0, 8.8, roof=True)
    # The off-centre keep leaves an open approach and readable courtyard.
    g.box((2.2, 3.0, FLOOR + 5.4), (7.3, 7.0, 10.8), 0)
    for level in (FLOOR + .3, FLOOR + 5.6, FLOOR + 10.6):
        g.box((2.2, 3.0, level), (7.65, 7.35, .35), 2)
    g.hip_roof(2.2, 3.0, FLOOR + 10.85, 8.25, 8, 4.5)
    for x in (-1.4, 5.8):
        for y in (-.4, 6.4):
            g.lathe(x, y, [(0.62, FLOOR + 6), (.62, FLOOR + 12.1)], 1, 12)
            g.lathe(x, y, [(.88, FLOOR + 12.1), (.06, FLOOR + 14.7)], 3, 12)
    for x in (-.2, 2.2, 4.6):
        for z in (FLOOR + 4.0, FLOOR + 7.7):
            g.box((x, -.54, z), (.78, .16, 1.7), 2)
            g.box((x, -.635, z), (.48, .06, 1.38), 9)
            g.box((x, -.68, z), (.055, .05, 1.38), 8)
    for y in (.8, 3.1, 5.4):
        g.box((5.91, y, FLOOR + 7.7), (.16, .8, 1.7), 2)
        g.box((6.005, y, FLOOR + 7.7), (.06, .5, 1.38), 9)
    g.box((2.2, -.56, FLOOR + 1.35), (1.85, .18, 2.7), 2)
    g.box((2.2, -.69, FLOOR + 1.35), (1.45, .1, 2.4), 4)
    g.box((2.2, -.93, FLOOR + .16), (2.1, .7, .32), 1)
    g.tower(-5.2, 4.7, 1.65, 11.5, roof=True)
    g.flag(-5.2, 4.7, FLOOR + 17.0)
    g.flag(10, -7.5, FLOOR + 7.5, 2.35)
    # Banners are solid cloth slabs so both camera directions have visible faces.
    for x in (-5.7, 5.7):
        g.box((x, -8.38, FLOOR + 3.95), (1.3, .09, 2.7), 14)
        g.box((x, -8.4, FLOOR + 5.36), (1.65, .16, .15), 8)
    g.box((-6, -.2, FLOOR + 1.5), (4.5, 5.7, 3.0), 6)
    g.hip_roof(-6, -.2, FLOOR + 3.0, 5.0, 6.1, 2.2)
    g.box((-6, -3.1, FLOOR + 1.1), (1.15, .12, 2.2), 4)
    # The plinth has a central opening for steps down to the surrounding terrain.
    for i in range(9):
        top = FLOOR * (i + 1) / 9
        g.box((0, -10.85 + i * .3, top / 2), (4.6, .3, top), 6)
    return g


def terrain_height(x, z):
    data = terrain_height.data
    offset = struct.unpack_from("<I", data, 10)[0]
    w, h = struct.unpack_from("<ii", data, 18)
    stride = (w + 3) // 4 * 4
    ix, iz = math.floor(x), math.floor(z)
    assert 0 <= ix < w - 1 and 0 <= iz < abs(h) - 1
    values = [data[offset + (iz + dz if h > 0 else -h - 1 - iz - dz) * stride + ix + dx] / 10
              for dx, dz in ((0, 0), (1, 0), (0, 1), (1, 1))]
    fx, fz = x - ix, z - iz
    return (values[0] * (1 - fx) + values[1] * fx) * (1 - fz) + (values[2] * (1 - fx) + values[3] * fx) * fz


def load_terrain():
    terrain_height.data = (ROOT / "map/heightmap.bmp").read_bytes()
    data = terrain_height.data
    assert data[:2] == b"BM" and struct.unpack_from("<H", data, 28)[0] == 8
    assert struct.unpack_from("<I", data, 30)[0] == 0
    palette = 14 + struct.unpack_from("<I", data, 14)[0]
    assert all(data[palette + i * 4:palette + i * 4 + 3] == bytes([i, i, i]) for i in range(256))


def build(output):
    import bpy
    from mathutils import Vector
    from types import SimpleNamespace

    source_hash = digest(Path(__file__))
    bpy.ops.wm.read_factory_settings(use_empty=True)
    pdx = load_exporter()
    load_terrain()
    g = geometry()
    for i, (x, y, z) in enumerate(g.vertices):
        if abs(z) < 1e-8:
            ground = terrain_height(POSITION[0] + x * SCALE, POSITION[2] + y * SCALE)
            g.vertices[i] = (x, y, (ground - POSITION[1] - .22) / SCALE)
    obj = g.make_object()
    obj.name = obj.data.name = NAME
    folder = output / "package" / MODEL_DIR
    obj.data.materials.append(pdx.create_shader(SimpleNamespace(
        shader=["PdxMeshAdvanced"], diff=[f"{NAME}_diffuse.dds"],
        n=[f"{NAME}_normal.dds"], spec=[f"{NAME}_specular.dds"]
    ), "Grayson stone slate and heraldry", str(folder)))
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    path = folder / f"{NAME}.mesh"
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
                region.view_location = (0, 0, 10)
                region.view_distance = 47
                region.view_rotation = Vector((34, -47, 24)).to_track_quat("Z", "Y")
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=str(output / "Bezhaysk_castle.blend"))
    assert source_hash == digest(Path(__file__)), "Source changed during build"
    verify(output, pdx)


def verify(output, pdx=None):
    import bpy
    from mathutils import Vector

    pdx = pdx or load_exporter()
    from io_pdx_mesh import pdx_data

    folder = output / "package" / MODEL_DIR
    source_hash = digest(Path(__file__))
    heightmap_hash = digest(ROOT / "map/heightmap.bmp")
    hashes = {name: digest(folder / name) for name in FILES}
    tree = pdx_data.read_meshfile(str(folder / FILES[0]))
    vertices = triangles = 0
    for shape in tree.find("object"):
        for element in shape.findall("mesh"):
            data = pdx_data.PDXData(element)
            count = len(data.p) // 3
            assert 0 < count < 65536
            assert len(data.n) == count * 3 and len(data.u0) == count * 2 and len(data.ta) == count * 4
            assert all(math.isfinite(v) for v in data.p + data.n + data.u0 + data.ta)
            assert len(data.tri) % 3 == 0 and min(data.tri) >= 0 and max(data.tri) < count
            assert data.material.shader == ["PdxMeshAdvanced"]
            for key in ("diff", "n", "spec"):
                raw = (folder / getattr(data.material, key)[0]).read_bytes()
                assert raw[:4] == b"DDS " and raw[84:88] == b"DXT5"
                assert struct.unpack_from("<I", raw, 28)[0] == 11
            vertices += count
            triangles += len(data.tri) // 3
    assert triangles < 15000
    bpy.ops.wm.read_factory_settings(use_empty=True)
    pdx.import_meshfile(str(folder / FILES[0]), imp_locs=False)
    meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    points = [o.matrix_world @ v.co for o in meshes for v in o.data.vertices]
    bounds = [[round(min(v[i] for v in points), 5), round(max(v[i] for v in points), 5)] for i in range(3)]
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.samples = 40
    scene.cycles.use_denoising = True
    scene.render.resolution_x, scene.render.resolution_y = 1440, 1080
    scene.render.resolution_percentage = 100
    scene.world = bpy.data.worlds.new("Castle studio")
    scene.world.use_nodes = True
    scene.world.node_tree.nodes["Background"].inputs[0].default_value = (.27, .31, .38, 1)
    scene.world.node_tree.nodes["Background"].inputs[1].default_value = .55
    for material in bpy.data.materials:
        shader = material.node_tree.nodes.get("Principled BSDF") if material.use_nodes else None
        if shader:
            roughness = shader.inputs["Roughness"]
            for link in list(roughness.links):
                material.node_tree.links.remove(link)
            roughness.default_value = .8
    bpy.ops.mesh.primitive_plane_add(size=200, location=(0, 0, -.2))
    floor = bpy.context.object
    floor.name = "Preview ground (not exported)"
    material = bpy.data.materials.new("Muted earth")
    material.diffuse_color = (.14, .17, .145, 1)
    floor.data.materials.append(material)
    for location, energy, size in (((-20, -28, 42), 20000, 17), ((24, -6, 25), 9000, 16), ((-8, 24, 35), 23000, 14)):
        bpy.ops.object.light_add(type="AREA", location=location)
        light = bpy.context.object
        light.data.energy, light.data.size = energy, size
        light.rotation_euler = (Vector((0, 0, 7)) - light.location).to_track_quat("-Z", "Y").to_euler()
    bpy.ops.object.camera_add()
    camera = bpy.context.object
    camera.data.type = "ORTHO"
    scene.camera = camera
    for suffix, location, target, scale in (
        ("preview", (34, -47, 34), (0, 0, 10), 47),
        ("front", (1, -55, 23), (0, 0, 10), 43),
        ("map", (28, -40, 58), (0, 0, 6), 46),
        ("rear", (-34, 44, 33), (0, 0, 10), 47),
    ):
        camera.location = location
        camera.rotation_euler = (Vector(target) - camera.location).to_track_quat("-Z", "Y").to_euler()
        camera.data.ortho_scale = scale
        scene.render.filepath = str(output / f"Bezhaysk_castle_{suffix}.png")
        bpy.ops.render.render(write_still=True)
    assert hashes == {name: digest(folder / name) for name in FILES}, "Native inputs changed during verification"
    assert source_hash == digest(Path(__file__)), "Source changed during verification"
    assert heightmap_hash == digest(ROOT / "map/heightmap.bmp"), "Terrain changed during verification"
    report = {
        "files": hashes, "vertices": vertices, "triangles": triangles,
        "bounds_blender_xyz": bounds, "native_reimport": True,
        "placement": {"position": list(POSITION), "scale": SCALE},
        "heightmap_sha256": heightmap_hash,
        "source_sha256": source_hash, "hoi4_runtime_verified": False,
    }
    (output / "verification.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report), flush=True)


def write_changes(contents, apply):
    changed = [str(path) for path, data in contents.items() if not path.exists() or path.read_bytes() != data]
    print(json.dumps({"changed": changed, "apply": apply}), flush=True)
    if apply:
        for path, data in contents.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            if not path.exists() or path.read_bytes() != data:
                path.write_bytes(data)
    return changed


def stage(output, apply):
    folder = output / "package" / MODEL_DIR
    return write_changes({folder / name: raw for name, raw in textures().items()}, apply)


def install(output, apply):
    report = json.loads((output / "verification.json").read_text(encoding="utf-8"))
    assert report["native_reimport"]
    assert report["placement"] == {"position": list(POSITION), "scale": SCALE}
    assert report["heightmap_sha256"] == digest(ROOT / "map/heightmap.bmp")
    assert report["source_sha256"] == digest(Path(__file__))
    folder = output / "package" / MODEL_DIR
    assert report["files"] == {name: digest(folder / name) for name in FILES}
    contents = {ROOT / MODEL_DIR / name: (folder / name).read_bytes() for name in FILES}
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
    start, end = "# BEGIN ADISCORD Bezhaysk castle", "# END ADISCORD Bezhaysk castle"
    for relative, block in blocks.items():
        path = ROOT / relative
        original = path.read_bytes()
        newline = "\r\n" if b"\r\n" in original else "\n"
        section = (start + "\n# Generated by tools/assets/source/build_bezhaysk_castle.py\n" + block + "\n" + end + "\n").replace("\n", newline).encode()
        pattern = re.escape(start.encode()) + rb".*?" + re.escape(end.encode()) + rb"\r?\n?"
        matches = list(re.finditer(pattern, original, flags=re.S))
        assert len(matches) <= 1, path
        if matches:
            match = matches[0]
            contents[path] = original[:match.start()] + section + original[match.end():]
        else:
            assert NAME.encode() not in original, f"Unowned castle entry in {path}"
            contents[path] = original + newline.encode() + section
    return write_changes(contents, apply)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    mode = parser.add_mutually_exclusive_group(required=True)
    for name in ("check", "apply", "build", "verify"):
        mode.add_argument("--" + name, action="store_true")
    parser.add_argument("--install", action="store_true")
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else None)
    output = args.output.resolve()
    if args.build:
        build(output)
    elif args.verify:
        verify(output)
    else:
        changed = install(output, args.apply) if args.install else stage(output, args.apply)
        if args.check:
            raise SystemExit(bool(changed))


if __name__ == "__main__":
    main()
