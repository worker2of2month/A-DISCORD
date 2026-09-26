"""Build the SHL palace preview and a self-contained native HOI4 mesh package.

Python: build_shl_palace.py --output PATH --check
Python: build_shl_palace.py --output PATH --apply --blender PATH
Blender: --background --factory-startup --python this_file -- --output PATH --build
Add --terrain-fit to build the foundation for the capital placement.
Python: --output PATH --install --check, then --install --apply, then --install --check
Installation owns marked sections in the existing map/entity registries.
"""

import argparse
import hashlib
import io
import json
import math
from pathlib import Path
import random
import re
import struct
import subprocess
import sys

sys.dont_write_bytecode = True
NAME = "ADISCORD_SHL_palace"
MODEL_DIR = Path("gfx/models/buildings/SHL_palace")
ATLAS_SIZE = 1024
TILE_SIZE = ATLAS_SIZE // 4
MAP_POSITION = (3993.0, 14.42, 873.0)
MAP_SCALE = .16
REPOSITORY = Path(__file__).resolve().parents[3]


def dds_bytes(image):
    """Keep independent packed channels when downsampling native material maps."""
    from PIL import Image

    levels = []
    while True:
        stream = io.BytesIO()
        image.save(stream, format="DDS", pixel_format="DXT5")
        levels.append(stream.getvalue())
        if image.size == (1, 1):
            break
        size = tuple(max(1, value // 2) for value in image.size)
        image = Image.merge("RGBA", tuple(c.resize(size, Image.Resampling.BOX) for c in image.split()))
    header = bytearray(levels[0][:128])
    flags = struct.unpack_from("<I", header, 8)[0]
    struct.pack_into("<I", header, 8, flags | 0x20000)
    struct.pack_into("<I", header, 28, len(levels))
    struct.pack_into("<I", header, 108, 0x401008)
    return bytes(header) + b"".join(level[128:] for level in levels)


def textures():
    from PIL import Image, ImageDraw, ImageFilter

    rng = random.Random(294)
    colors = [
        (196, 183, 152), (215, 203, 173), (176, 142, 85), (202, 185, 148),
        (48, 69, 65), (177, 166, 136), (183, 170, 139), (143, 111, 59),
        (47, 99, 94), (83, 75, 46), (62, 82, 36), (58, 54, 43),
        (188, 170, 129), (113, 92, 58), (123, 69, 43), (228, 214, 182),
    ]
    atlas = Image.new("RGBA", (ATLAS_SIZE, ATLAS_SIZE))
    relief = Image.new("L", atlas.size, 128)
    for index, color in enumerate(colors):
        tile = Image.new("RGBA", (TILE_SIZE, TILE_SIZE))
        pixels = []
        for y in range(TILE_SIZE):
            for x in range(TILE_SIZE):
                variation = rng.gauss(0, 2.5) + 3 * math.sin(x * .074 + y * .023)
                variation += 2 * math.sin(x * .017 - y * .051)
                pixels.append(tuple(max(0, min(255, int(c + variation))) for c in color) + (255,))
        tile.putdata(pixels)
        draw = ImageDraw.Draw(tile)
        height = Image.new("L", tile.size, 128)
        hd = ImageDraw.Draw(height)
        if index in (0, 5, 6):
            step = 64 if index == 0 else 85
            for row, y in enumerate(range(0, TILE_SIZE, step)):
                draw.line((0, y, 256, y), fill=tuple(int(c * .81) for c in color), width=2)
                draw.line((0, y + 2, 256, y + 2), fill=tuple(min(255, c + 10) for c in color))
                hd.line((0, y, 256, y), fill=95, width=2)
                for x in range(-128 if row % 2 else 0, 257, 128):
                    draw.line((x, y, x, y + step), fill=tuple(int(c * .84) for c in color))
                    hd.line((x, y, x, y + step), fill=100)
        if index == 3:
            for y in (16, 28, 222, 236):
                draw.line((0, y, 255, y), fill=(153, 133, 94), width=3)
                hd.line((0, y, 255, y), fill=96, width=3)
            for x in range(-32, 288, 32):
                draw.polygon([(x, 205), (x + 16, 53), (x + 32, 205)], fill=(162, 142, 105))
                draw.line([(x + 3, 205), (x + 16, 65), (x + 29, 205)], fill=(228, 208, 164), width=3)
                hd.polygon([(x, 205), (x + 16, 53), (x + 32, 205)], fill=105)
        if index == 4:
            for x in (8, 120, 136, 247):
                draw.line((x, 0, x, 256), fill=(166, 126, 62), width=5)
            for y in (12, 80, 174, 242):
                draw.line((0, y, 256, y), fill=(166, 126, 62), width=4)
            for cx in (65, 191):
                draw.polygon([(cx, 94), (cx + 30, 125), (cx, 157), (cx - 30, 125)], outline=(185, 146, 76), width=4)
                for y in (43, 208):
                    draw.ellipse((cx - 7, y - 7, cx + 7, y + 7), fill=(172, 134, 68))
        if index == 12:
            for inset in (9, 17):
                draw.rectangle((inset, inset, 255 - inset, 255 - inset), outline=(149, 131, 95), width=3)
            for x in (64, 128, 192):
                draw.line((x, 185, x, 64), fill=(224, 204, 162), width=9)
                for offset in (-24, 0, 24):
                    draw.line((x, 126, x + offset, 73), fill=(145, 126, 91), width=6)
                draw.arc((x - 25, 43, x + 25, 93), 0, 180, fill=(145, 126, 91), width=5)
            hd = ImageDraw.Draw(height)
            hd.rectangle((17, 17, 238, 238), outline=95, width=3)
        if index in (10, 13):
            for x in range(0, 256, 12 if index == 10 else 26):
                draw.line((x, 0, x + 40, 256), fill=tuple(int(c * .78) for c in color), width=2)
        if index == 8:
            for y in range(5, 256, 16):
                draw.arc((0, y, 255, y + 25), 190, 350, fill=(61, 119, 110), width=2)
        if index in (0, 1, 2, 3, 5, 6, 12, 15):
            stone_tone = [round(value * .9) for value in range(256)]
            tile = tile.point(stone_tone * 3 + list(range(256)))
        xy = ((index % 4) * TILE_SIZE, (index // 4) * TILE_SIZE)
        atlas.paste(tile, xy)
        relief.paste(height, xy)
    relief = relief.filter(ImageFilter.GaussianBlur(.65))
    normal = Image.new("RGBA", atlas.size)
    hp = relief.load()
    normal_pixels = []
    for y in range(ATLAS_SIZE):
        for x in range(ATLAS_SIZE):
            dx = (hp[min(x + 1, 1023), y] - hp[max(0, x - 1), y]) * .45
            dy = (hp[x, min(y + 1, 1023)] - hp[x, max(0, y - 1)]) * .45
            # Native building shaders decode tangent X from G and tangent Y from A.
            normal_pixels.append((255, int(128 - dx), 0, int(128 + dy)))
    normal.putdata(normal_pixels)
    spec = Image.new("RGBA", atlas.size, (0, 40, 0, 28))
    sd = ImageDraw.Draw(spec)
    for index, color in ((4, (0, 70, 30, 60)), (7, (0, 110, 60, 100)), (8, (0, 140, 0, 155))):
        x, y = index % 4 * TILE_SIZE, index // 4 * TILE_SIZE
        sd.rectangle((x, y, x + 255, y + 255), fill=color)
    return {f"{NAME}_diffuse.dds": dds_bytes(atlas), f"{NAME}_normal.dds": dds_bytes(normal), f"{NAME}_specular.dds": dds_bytes(spec)}


def load_exporter():
    import inspect

    extension = Path.home() / "AppData/Roaming/Blender Foundation/Blender/5.2/extensions/user_default"
    sys.path.insert(0, str(extension))
    from io_pdx_mesh.pdx_blender import blender_import_export as pdx

    source = inspect.getsource(pdx.create_shader)
    for line in ('    new_shader.shadow_method = "CLIP"', '    new_shader.blend_method = "CLIP"'):
        source = source.replace(line, "")
    exec(compile(source, "<Blender material compatibility>", "exec"), pdx.__dict__)
    return pdx


class Geometry:
    def __init__(self):
        self.vertices = []
        self.faces = []
        self.uvs = []

    def face(self, points, tile, uv=None):
        offset = len(self.vertices)
        self.vertices.extend(points)
        self.faces.append(tuple(range(offset, offset + len(points))))
        if uv is None:
            uv = [(0, 0), (1, 0), (1, 1), (0, 1)][:len(points)]
        col, row = tile % 4, tile // 4
        self.uvs.append([((col + .035 + .93 * u) / 4, (3 - row + .035 + .93 * v) / 4) for u, v in uv])

    def panel(self, points, tile, subdivide=False):
        if not subdivide:
            self.face(points, tile)
            return
        from mathutils import Vector

        a, b, c, d = map(Vector, points)
        nx = max(1, math.ceil((b - a).length / 4))
        ny = max(1, math.ceil((d - a).length / 4))
        for i in range(nx):
            for j in range(ny):
                def point(u, v):
                    return tuple(a + (b - a) * u + (d - a) * v)
                self.face([point(i / nx, j / ny), point((i + 1) / nx, j / ny), point((i + 1) / nx, (j + 1) / ny), point(i / nx, (j + 1) / ny)], tile)

    def box(self, center, size, tile=1):
        x, y, z = center
        w, d, h = (v / 2 for v in size)
        v = [(x - w, y - d, z - h), (x + w, y - d, z - h), (x + w, y + d, z - h), (x - w, y + d, z - h),
             (x - w, y - d, z + h), (x + w, y - d, z + h), (x + w, y + d, z + h), (x - w, y + d, z + h)]
        for indices in ((0, 3, 2, 1), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7), (4, 5, 6, 7)):
            self.panel([v[i] for i in indices], tile, tile in (0, 5, 6))

    def lathe(self, x, y, profile, tile=1, segments=16):
        rings = [[(x + radius * math.cos(2 * math.pi * i / segments), y + radius * math.sin(2 * math.pi * i / segments), z) for i in range(segments)] for radius, z in profile]
        for j, (lower, upper) in enumerate(zip(rings, rings[1:])):
            for i in range(segments):
                k = (i + 1) % segments
                self.face([lower[i], lower[k], upper[k], upper[i]], tile)
        self.face(list(reversed(rings[0])), tile, [(0.5 + .49 * math.cos(2 * math.pi * i / segments), 0.5 + .49 * math.sin(2 * math.pi * i / segments)) for i in reversed(range(segments))])
        self.face(rings[-1], tile, [(0.5 + .49 * math.cos(2 * math.pi * i / segments), 0.5 + .49 * math.sin(2 * math.pi * i / segments)) for i in range(segments)])

    def cornice(self, x, y, z, w, d):
        self.box((x, y, z), (w, d, .16), 2)
        self.box((x, y, z + .17), (w + .26, d + .26, .18), 15)
        self.box((x, y, z + .42), (w + .5, d + .5, .33), 1)
        self.box((x, y, z + .64), (w + .76, d + .76, .13), 15)

    def column(self, x, y, z, height):
        self.box((x, y, z + .12), (1.5, 1.5, .24), 0)
        self.lathe(x, y, [(.72, z + .24), (.72, z + .39), (.55, z + .52), (.48, z + .8), (.45, z + height * .55), (.39, z + height - 1.0), (.48, z + height - .6), (.67, z + height - .28), (.69, z + height - .16)], 1)
        self.lathe(x, y, [(.49, z + 1.3), (.49, z + 1.48)], 2)
        self.lathe(x, y, [(.54, z + height - .59), (.66, z + height - .33)], 3)
        self.box((x, y, z + height - .08), (1.48, 1.48, .16), 15)

    def palm(self, x, y, z, height, phase):
        from mathutils import Vector

        segments = 8
        rings = []
        for j in range(8):
            t = j / 7
            center = Vector((x + .24 * t * t, y + .14 * t * t, z + height * t))
            r = .19 * (1 - .38 * t)
            rings.append([center + Vector((r * math.cos(i * math.tau / segments), r * math.sin(i * math.tau / segments), 0)) for i in range(segments)])
        for a, b in zip(rings, rings[1:]):
            for i in range(segments):
                k = (i + 1) % segments
                self.face([a[i], a[k], b[k], b[i]], 13)
        crown = Vector((x + .24, y + .14, z + height))
        for j in range(10):
            angle = j * math.tau / 10 + phase
            forward = Vector((math.cos(angle), math.sin(angle), 0))
            side = Vector((-math.sin(angle), math.cos(angle), 0))
            length = 2.2 + .35 * math.sin(j * 2)
            def stem(t):
                return crown + forward * length * t + Vector((0, 0, 1.3 * math.sin(t * math.pi * .85) - .95 * t))
            for k in range(10):
                a, b = stem(k / 10), stem((k + 1) / 10)
                self.face([a - side * .018, b - side * .007, b + side * .007, a + side * .018], 10)
                self.face([a + side * .018, b + side * .007, b - side * .007, a - side * .018], 10)
            for k in range(1, 9):
                t = k / 10
                center = stem(t)
                width = .6 * math.sin(t * math.pi) + .07
                for sign in (-1, 1):
                    tip = center + side * sign * width + forward * .32 + Vector((0, 0, -.18))
                    root = center - forward * .13
                    mid = (root + tip) * .5
                    ridge = mid + Vector((0, 0, .07))
                    edge = center + forward * .14
                    self.face([root, tip, ridge], 10)
                    self.face([tip, edge, ridge], 10)
                    self.face([edge, tip, root], 10)

    def make_object(self):
        import bpy
        import bmesh

        mesh = bpy.data.meshes.new(NAME)
        mesh.from_pydata(self.vertices, [], self.faces)
        mesh.update()
        uv = mesh.uv_layers.new(name="UVMap")
        for polygon, coords in zip(mesh.polygons, self.uvs):
            for index, coord in zip(polygon.loop_indices, coords):
                uv.data[index].uv = coord
        bm = bmesh.new()
        bm.from_mesh(mesh)
        bmesh.ops.remove_doubles(bm, verts=list(bm.verts), dist=.00001)
        bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
        bmesh.ops.triangulate(bm, faces=list(bm.faces))
        assert all(face.calc_area() > 1e-10 for face in bm.faces)
        bm.to_mesh(mesh)
        bm.free()
        obj = bpy.data.objects.new(NAME, mesh)
        bpy.context.collection.objects.link(obj)
        return obj


def palace_geometry():
    g = Geometry()
    # A shallow foundation anchors the forecourt while leaving terrain placement flexible.
    g.box((0, -3, .14), (36, 29, .28), 0)
    g.box((0, -3, .34), (35.6, 28.6, .12), 6)
    g.box((0, 2.1, .73), (32, 18.6, .7), 0)
    for i in range(6):
        g.box((0, -9.3 + i * .37, .45 + i * .05), (8.8, .5, .1 + i * .1), 1)
    # The open portico ends at a recessed rear wall, with a real doorway recess.
    g.box((-8.65, 3.4, 5.5), (12.3, 11, 8.8), 0)
    g.box((8.65, 3.4, 5.5), (12.3, 11, 8.8), 0)
    g.box((0, 6.7, 5.5), (5, 4.4, 8.8), 0)
    g.box((0, 1.2, 8.85), (5, 6.8, 2.1), 0)
    g.box((0, -1.2, 4.15), (4.25, .3, 6.1), 4)
    for x in (-2.47, 2.47):
        g.box((x, -2.27, 4.55), (.45, .7, 6.9), 15)
        g.box((x, -2.65, 4.55), (.13, .06, 6.5), 2)
    g.box((0, -2.25, 8), (5.4, .75, .5), 12)
    for x in (-13.1, -9.2, 9.2, 13.1):
        g.column(x, -6.3, 1.08, 8.15)
        g.column(x, -2.8, 1.08, 8.15)
    # Pylons flank the processional opening and continue above the common roofline.
    for x in (-4.65, 4.65):
        g.box((x, -5.3, 3.43), (3.7, 3.6, 4.7), 0)
        g.cornice(x, -5.3, 5.62, 3.7, 3.6)
        g.box((x, -4.88, 6.96), (2.92, 2.78, 1.4), 11)
        g.box((x, -5.3, 8.3), (3.65, 3.6, 1.4), 0)
        g.cornice(x, -5.3, 7.48, 3.72, 3.68)
        g.box((x, -5.3, 11.38), (3.65, 3.5, 2.6), 0)
        g.cornice(x, -5.3, 12.58, 3.75, 3.6)
        g.box((x, -7.16, 3.27), (2.93, .09, 3.65), 12)
        g.box((x, -7.095, 11.53), (2.97, .07, 1.48), 12)
    g.box((0, .65, 9.65), (31.35, 17.1, .8), 1)
    g.box((0, -7.94, 9.67), (31.38, .13, .46), 3)
    # The repeated frieze uses short panels to retain the same ornament scale.
    for i in range(16):
        g.box((-14.55 + i * 1.94, -8.015, 9.67), (1.94, .035, .47), 3)
    g.cornice(0, .65, 10.08, 31.45, 17.2)
    g.box((0, 1.25, 10.85), (28.8, 14.6, .23), 5)
    for x in (-14.32, 14.32):
        g.box((x, 1.25, 11.18), (.42, 14.72, .52), 1)
    g.box((0, 8.4, 11.18), (28.22, .42, .52), 1)
    # A raised clerestory gives the otherwise flat roof a readable oblique silhouette.
    g.box((0, 4.4, 11.65), (14.7, 6.5, 1.6), 0)
    g.cornice(0, 4.4, 12.36, 14.8, 6.6)
    for x in (-5.8, -2.9, 0, 2.9, 5.8):
        g.box((x, 1.1, 11.76), (1.75, .08, .85), 11)
        g.box((x, 1.02, 11.8), (.12, .1, .86), 2)
    for x in (-14.9, 14.9):
        for y in (-.8, 2.5, 5.8):
            g.box((x, y, 4.88), (.22, 2.6, 6.9), 1)
            g.box((x * 1.009, y, 5.1), (.1, 1.78, 3.2), 12)
    for x in (-11.7, 11.7):
        g.box((x, -11.0, .57), (5.4, 6.7, .35), 1)
        g.box((x, -11.0, .78), (4.85, 6.15, .08), 9)
        g.palm(x, -10.4, .82, 5.45, .3 if x > 0 else 1.6)
        for dx, dy in ((-1.5, -1.8), (1.4, 1.6)):
            g.palm(x + dx, -11 + dy, .84, .8, .5)
    for x in (-6.8, 6.8):
        g.lathe(x, -13.4, [(1.05, .41), (1.05, .68), (.8, .75), (.73, 1.22), (.92, 1.31), (1.35, 1.66), (1.38, 1.82), (1.24, 1.86), (.88, 1.48)], 1, 20)
        g.lathe(x, -13.4, [(.9, 1.49), (.92, 1.51)], 8, 20)
        g.lathe(x, -8.0, [(.51, 1.07), (.51, 1.22), (.37, 2.13), (.61, 2.31), (.62, 2.47)], 7, 12)
    return g


def fit_foundation(geometry):
    """Extend only the foundation underside into the capital's sloping terrain."""
    data = (REPOSITORY / "map/heightmap.bmp").read_bytes()
    assert data[:2] == b"BM"
    offset = struct.unpack_from("<I", data, 10)[0]
    width, height = struct.unpack_from("<ii", data, 18)
    assert struct.unpack_from("<H", data, 28)[0] == 8
    assert struct.unpack_from("<I", data, 30)[0] == 0
    palette = 14 + struct.unpack_from("<I", data, 14)[0]
    assert all(data[palette + 4 * i:palette + 4 * i + 3] == bytes([i, i, i]) for i in range(256))
    stride = (width + 3) // 4 * 4

    def sample(x, z):
        row = z if height > 0 else -height - 1 - z
        return data[offset + row * stride + x] / 10

    def elevation(x, z):
        ix, iz = math.floor(x), math.floor(z)
        fx, fz = x - ix, z - iz
        values = [sample(ix + dx, iz + dz) for dx, dz in ((0, 0), (1, 0), (0, 1), (1, 1))]
        return (values[0] * (1 - fx) + values[1] * fx) * (1 - fz) + (values[2] * (1 - fx) + values[3] * fx) * fz

    for i, (x, y, z) in enumerate(geometry.vertices):
        if abs(z) < 1e-8:
            ground = elevation(MAP_POSITION[0] + x * MAP_SCALE, MAP_POSITION[2] + y * MAP_SCALE)
            geometry.vertices[i] = (x, y, (ground - MAP_POSITION[1] - .15) / MAP_SCALE)


def build(output, render=True, terrain_fit=False):
    import bpy
    from mathutils import Vector
    from types import SimpleNamespace

    bpy.ops.wm.read_factory_settings(use_empty=True)
    pdx = load_exporter()
    folder = output / "package" / MODEL_DIR
    geometry = palace_geometry()
    if terrain_fit:
        fit_foundation(geometry)
    obj = geometry.make_object()
    material = pdx.create_shader(SimpleNamespace(shader=["PdxMeshAdvanced"], diff=[f"{NAME}_diffuse.dds"], n=[f"{NAME}_normal.dds"], spec=[f"{NAME}_specular.dds"]), "SHL limestone and bronze", str(folder))
    obj.data.materials.append(material)
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    mesh_path = folder / f"{NAME}.mesh"
    pdx.export_meshfile(str(mesh_path), exp_selected=True, exp_skel=False, exp_locs=False)
    from io_pdx_mesh import pdx_data

    native = pdx_data.read_meshfile(str(mesh_path))
    for shape in native.find("object"):
        for mesh in shape.findall("mesh"):
            # Parallel tangent accumulation can vary in its final floating-point bits.
            mesh.attrib["ta"] = [round(value, 5) for value in mesh.attrib["ta"]]
    pdx_data.write_meshfile(str(mesh_path), native)
    # Save a textured, editable source with no preview floor in the exported selection.
    bpy.ops.file.pack_all()
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type == "VIEW_3D":
                area.spaces.active.shading.type = "MATERIAL"
                region = area.spaces.active.region_3d
                region.view_location = (0, -2, 4)
                region.view_distance = 52
                region.view_rotation = (Vector((34, -49, 33)) - Vector((0, -2, 4))).to_track_quat("Z", "Y")
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=str(output / "SHL_palace.blend"))
    verify(output, pdx, render=render, terrain_fit=terrain_fit)


def verify(output, pdx=None, render=True, terrain_fit=False):
    import bpy
    from mathutils import Vector

    pdx = pdx or load_exporter()
    from io_pdx_mesh import pdx_data

    path = output / "package" / MODEL_DIR / f"{NAME}.mesh"
    tree = pdx_data.read_meshfile(str(path))
    vertices = triangles = materials = 0
    for shape in tree.find("object"):
        for mesh in shape.findall("mesh"):
            data = pdx_data.PDXData(mesh)
            count = len(data.p) // 3
            assert 0 < count < 65536
            assert len(data.n) == count * 3 and len(data.u0) == count * 2
            assert len(data.ta) == count * 4
            assert all(math.isfinite(v) for v in data.p + data.n + data.u0 + data.ta)
            assert len(data.tri) % 3 == 0 and min(data.tri) >= 0 and max(data.tri) < count
            for key in ("diff", "n", "spec"):
                texture = path.parent / getattr(data.material, key)[0]
                assert texture.read_bytes()[:4] == b"DDS "
            vertices += count
            triangles += len(data.tri) // 3
            materials += 1
    bpy.ops.wm.read_factory_settings(use_empty=True)
    pdx.import_meshfile(str(path), imp_locs=False)
    meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    points = [o.matrix_world @ v.co for o in meshes for v in o.data.vertices]
    bounds = [round(max(v[i] for v in points) - min(v[i] for v in points), 4) for i in range(3)]
    report = {"mesh_sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "vertices": vertices, "triangles": triangles, "materials": materials, "dimensions_blender_xyz": bounds, "native_reimport": True, "hoi4_runtime_verified": False}
    if terrain_fit:
        report["placement"] = {"position": MAP_POSITION, "scale": MAP_SCALE, "terrain_fitted": True}
        report["heightmap_sha256"] = hashlib.sha256((REPOSITORY / "map/heightmap.bmp").read_bytes()).hexdigest()
    (output / "verification.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report), flush=True)
    if not render:
        return
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.samples = 32
    scene.cycles.use_denoising = True
    scene.render.resolution_x = 1440
    scene.render.resolution_y = 1080
    scene.render.resolution_percentage = 100
    scene.world = bpy.data.worlds.new("Palace studio")
    scene.world.use_nodes = True
    scene.world.node_tree.nodes["Background"].inputs[0].default_value = (.22, .26, .30, 1)
    scene.world.node_tree.nodes["Background"].inputs[1].default_value = .45
    for material in bpy.data.materials:
        if material.use_nodes:
            shader = material.node_tree.nodes.get("Principled BSDF")
            if shader:
                roughness = shader.inputs["Roughness"]
                for link in list(roughness.links):
                    material.node_tree.links.remove(link)
                roughness.default_value = .78
    bpy.ops.mesh.primitive_plane_add(size=200, location=(0, 0, -.035))
    floor = bpy.context.object
    floor.name = "Preview floor (not exported)"
    floor_mat = bpy.data.materials.new("Studio sand")
    floor_mat.diffuse_color = (.16, .18, .18, 1)
    floor.data.materials.append(floor_mat)
    for location, energy, size in (((-18, -24, 38), 15000, 18), ((20, -5, 22), 6500, 15), ((0, 25, 30), 19000, 14)):
        bpy.ops.object.light_add(type="AREA", location=location)
        light = bpy.context.object
        light.data.energy = energy
        light.data.shape = "DISK"
        light.data.size = size
        light.rotation_euler = (Vector((0, 0, 4)) - light.location).to_track_quat("-Z", "Y").to_euler()
    bpy.ops.object.camera_add(location=(34, -49, 33))
    camera = bpy.context.object
    camera.data.type = "ORTHO"
    camera.data.ortho_scale = 52
    scene.camera = camera
    for name, location, target, scale in (
        ("SHL_palace_preview.png", (34, -49, 33), (0, -2, 4), 52),
        ("SHL_palace_front.png", (2, -55, 19), (0, -1, 5.0), 44),
        ("SHL_palace_map.png", (30, -40, 53), (0, -2, 2), 52),
    ):
        camera.location = location
        camera.rotation_euler = (Vector(target) - camera.location).to_track_quat("-Z", "Y").to_euler()
        camera.data.ortho_scale = scale
        scene.render.filepath = str(output / name)
        bpy.ops.render.render(write_still=True)


def stage(output, apply):
    folder = output / "package" / MODEL_DIR
    contents = {folder / name: value for name, value in textures().items()}
    bindings = output / "package/gfx/entities"
    contents[bindings / "SHL_palace.gfx"] = ("# Generated by tools/assets/source/build_shl_palace.py\nobjectTypes = {\n\tpdxmesh = {\n\t\tname = \"" + NAME + "_mesh\"\n\t\tfile = \"" + (MODEL_DIR / (NAME + ".mesh")).as_posix() + "\"\n\t\tscale = 1\n\t\tcull_distance = 1800\n\t}\n}\n").encode()
    contents[bindings / "SHL_palace.asset"] = ("# Generated by tools/assets/source/build_shl_palace.py\nentity = {\n\tname = \"" + NAME + "_entity\"\n\tpdxmesh = \"" + NAME + "_mesh\"\n}\n").encode()
    changed = [str(path.relative_to(output)) for path, data in contents.items() if not path.exists() or path.read_bytes() != data]
    print(json.dumps({"changed": changed, "apply": apply}), flush=True)
    if apply:
        for path, data in contents.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            if not path.exists() or path.read_bytes() != data:
                path.write_bytes(data)
    return changed


def install(output, apply=False):
    """Own one marked section per shared registry and the SHL model directory."""
    report = json.loads((output / "verification.json").read_text(encoding="utf-8"))
    assert report.get("placement") == {"position": list(MAP_POSITION), "scale": MAP_SCALE, "terrain_fitted": True}
    assert report["heightmap_sha256"] == hashlib.sha256((REPOSITORY / "map/heightmap.bmp").read_bytes()).hexdigest()
    folder = output / "package" / MODEL_DIR
    assert hashlib.sha256((folder / f"{NAME}.mesh").read_bytes()).hexdigest() == report["mesh_sha256"]
    contents = {REPOSITORY / MODEL_DIR / name: (folder / name).read_bytes() for name in (f"{NAME}.mesh", f"{NAME}_diffuse.dds", f"{NAME}_normal.dds", f"{NAME}_specular.dds")}
    blocks = {}
    for suffix in ("gfx", "asset"):
        text = (output / f"package/gfx/entities/SHL_palace.{suffix}").read_text(encoding="utf-8")
        blocks[REPOSITORY / f"gfx/entities/mapitems_custom.{suffix}"] = text.split("\n", 1)[1].rstrip()
    x, y, z = MAP_POSITION
    blocks[REPOSITORY / "map/ambient_object.txt"] = (
        'type = {\n\ttype = "' + NAME + '_entity"\n\tuse_animation = no\n'
        f'\tscale = {MAP_SCALE:.6f}\n\talways_visible = yes\n\tobject = {{\n'
        '\t\tname = "' + NAME + '"\n'
        f'\t\tposition = {{ {x:.3f} {y:.3f} {z:.3f} }}\n'
        '\t\trotation = { 0 0 0 }\n\t}\n}'
    )
    start = "# BEGIN ADISCORD SHL palace"
    end = "# END ADISCORD SHL palace"
    for path, block in blocks.items():
        original = path.read_bytes()
        newline = "\r\n" if b"\r\n" in original else "\n"
        section = (start + "\n# Generated by tools/assets/source/build_shl_palace.py\n" + block + "\n" + end + "\n").replace("\n", newline).encode()
        pattern = re.escape(start.encode()) + rb".*?" + re.escape(end.encode()) + rb"\r?\n?"
        matches = list(re.finditer(pattern, original, flags=re.S))
        assert len(matches) <= 1, path
        if matches:
            match = matches[0]
            content = original[:match.start()] + section + original[match.end():]
        else:
            assert NAME.encode() not in original, f"Unowned palace entry in {path}"
            content = original + newline.encode() + section
        contents[path] = content
    changed = [str(path.relative_to(REPOSITORY)) for path, data in contents.items() if not path.exists() or path.read_bytes() != data]
    print(json.dumps({"install": changed, "apply": apply}), flush=True)
    if apply:
        for path, data in contents.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            if not path.exists() or path.read_bytes() != data:
                path.write_bytes(data)
    return changed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--apply", action="store_true")
    mode.add_argument("--build", action="store_true")
    mode.add_argument("--verify", action="store_true")
    parser.add_argument("--blender", type=Path)
    parser.add_argument("--no-render", action="store_true")
    parser.add_argument("--terrain-fit", action="store_true")
    parser.add_argument("--install", action="store_true")
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else None)
    output = args.output.resolve()
    if args.install:
        changed = install(output, apply=args.apply)
        if args.check:
            raise SystemExit(bool(changed))
    elif args.build:
        build(output, render=not args.no_render, terrain_fit=args.terrain_fit)
    elif args.verify:
        verify(output, render=not args.no_render, terrain_fit=args.terrain_fit)
    else:
        changed = stage(output, args.apply)
        if args.check:
            raise SystemExit(bool(changed))
        if args.apply and args.blender:
            command = [str(args.blender), "--background", "--factory-startup", "--python", str(Path(__file__).resolve()), "--", "--output", str(output), "--build"]
            if args.no_render:
                command.append("--no-render")
            if args.terrain_fit:
                command.append("--terrain-fit")
            subprocess.run(command, check=True)


if __name__ == "__main__":
    main()
