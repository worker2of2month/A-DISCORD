"""Build native civilian and military factory models and their building entities.

Default/--check is read-only. --apply exports stale outputs with Blender and
io_pdx_mesh. --preview renders the installed meshes into development previews.
Only the marked factory sections of the shared registries belong to this builder.
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

MODEL_DIR = Path("gfx/models/buildings/ADISCORD_factories")
SOURCE_DIR = Path("tools/assets/source/buildings/factories")
REPORT = Path("docs/development/model-verification/factories.json")
PREVIEW = Path("docs/development/previews/factories")
MARKER = "ADISCORD factory models"
NATIVE_SCALE = .07
KINDS = {"civilian": "industrial_complex", "military": "arms_factory"}
TEXTURES = tuple(f"ADISCORD_factory_{channel}.dds" for channel in ("diffuse", "normal", "specular"))
SMOKE = {"civilian": ((-11.5, 7.2, 16.3),), "military": ((11.4, 7.8, 13.3),)}
DAMAGE = {"civilian": ((-7, 0, 4), (4, -8, 3)), "military": ((-5, 0, 5), (8, 2, 3))}
INPUTS = (Path(__file__).relative_to(ROOT), Path("tools/assets/source/build_shl_palace.py"))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def input_hashes():
    return {path.as_posix(): digest(ROOT / path) for path in INPUTS}


def model_name(kind):
    return f"ADISCORD_{kind}_factory"


def files():
    return [*TEXTURES, *(model_name(kind) + ".mesh" for kind in KINDS)]


def textures():
    """Shared padded atlas with independently downsampled packed normal channels."""
    import numpy as np
    from PIL import Image, ImageDraw, ImageFilter

    colors = ((147, 93, 68), (162, 161, 145), (72, 83, 87), (79, 91, 69),
              (99, 94, 83), (48, 56, 55), (37, 67, 76), (98, 108, 99),
              (197, 187, 159), (27, 32, 32), (125, 94, 56), (106, 111, 107),
              (55, 79, 81), (107, 116, 112), (111, 72, 53), (181, 146, 67))
    rng = np.random.default_rng(1946)
    atlas = Image.new("RGBA", (1024, 1024))
    relief = Image.new("L", atlas.size, 128)
    for index, color in enumerate(colors):
        noise = rng.normal(0, 3.5, (256, 256, 1))
        rgb = np.clip(np.asarray(color)[None, None, :] + noise, 0, 255).astype("uint8")
        tile = Image.fromarray(rgb).convert("RGBA")
        height = Image.new("L", (256, 256), 128)
        draw, hd = ImageDraw.Draw(tile), ImageDraw.Draw(height)
        if index in (0, 14):
            for row, y in enumerate(range(0, 256, 24)):
                draw.line((0, y, 255, y), fill=(91, 86, 74), width=2)
                hd.line((0, y, 255, y), fill=100, width=2)
                for x in range(-30 if row % 2 else 0, 256, 60):
                    draw.line((x, y, x, y + 24), fill=(91, 86, 74), width=2)
                    hd.line((x, y, x, y + 24), fill=100, width=2)
        if index in (2, 3, 7, 13):
            for x in range(0, 256, 20):
                draw.line((x, 0, x, 255), fill=tuple(int(c * .7) for c in color), width=2)
                hd.line((x, 0, x, 255), fill=100, width=2)
            for y in (15, 240):
                draw.line((0, y, 255, y), fill=tuple(min(255, c + 20) for c in color), width=2)
        if index in (6, 12):
            draw.polygon(((15, 0), (70, 0), (245, 255), (195, 255)), fill=(64, 91, 96))
            for x in (10, 89, 166, 245):
                draw.line((x, 0, x, 255), fill=(155, 163, 151), width=6)
                hd.line((x, 0, x, 255), fill=160, width=6)
            for y in (10, 89, 166, 245):
                draw.line((0, y, 255, y), fill=(155, 163, 151), width=6)
                hd.line((0, y, 255, y), fill=160, width=6)
        if index in (1, 4, 8):
            for y in (3, 128, 252):
                draw.line((0, y, 255, y), fill=tuple(int(c * .8) for c in color), width=2)
                hd.line((0, y, 255, y), fill=112, width=2)
        if index == 10:
            for x in range(0, 256, 48):
                draw.line((x, 0, x, 255), fill=(70, 52, 35), width=3)
            draw.line((0, 255, 255, 0), fill=(155, 122, 74), width=17)
        offset = (index % 4 * 256, index // 4 * 256)
        atlas.paste(tile, offset)
        relief.paste(height, offset)
    dy, dx = np.gradient(np.asarray(relief.filter(ImageFilter.GaussianBlur(.7)), dtype=float))
    normal = np.zeros((1024, 1024, 4), dtype="uint8")
    normal[:, :, 0] = 255
    normal[:, :, 1] = np.clip(128 - dx * .55, 80, 176)
    normal[:, :, 3] = np.clip(128 + dy * .55, 80, 176)
    spec = Image.new("RGBA", atlas.size, (0, 30, 0, 22))
    sd = ImageDraw.Draw(spec)
    for index in (5, 6, 11, 12):
        x, y = index % 4 * 256, index // 4 * 256
        sd.rectangle((x, y, x + 255, y + 255), fill=(0, 95, 0, 70))
    return dict(zip(TEXTURES, (dds_bytes(atlas), dds_bytes(Image.fromarray(normal)), dds_bytes(spec))))


class FactoryGeometry(Geometry):
    def panel(self, points, tile, subdivide=False):
        # The small repeated map meshes use explicit facade panels, not grid subdivision.
        self.face(points, tile)

    def beam(self, a, b, width, tile=5):
        from mathutils import Vector

        a, b = Vector(a), Vector(b)
        axis = (b - a).normalized()
        guide = Vector((0, 0, 1)) if abs(axis.z) < .9 else Vector((0, 1, 0))
        u = axis.cross(guide).normalized() * width / 2
        v = axis.cross(u).normalized() * width / 2
        low = [a - u - v, a + u - v, a + u + v, a - u + v]
        high = [p + b - a for p in low]
        self.face(list(reversed(low)), tile)
        self.face(high, tile)
        for i in range(4):
            j = (i + 1) % 4
            self.face([low[i], low[j], high[j], high[i]], tile)

    def window(self, x, y, z, width, height, side=False, tile=6, reverse=False):
        points = [(x - width / 2, y, z - height / 2),
                  (x + width / 2, y, z - height / 2),
                  (x + width / 2, y, z + height / 2),
                  (x - width / 2, y, z + height / 2)]
        if side:
            points = [(x, y + px - x, pz) for px, _, pz in points]
        if reverse:
            points.reverse()
        self.face(points, tile)

    def chimney(self, x, y, height, tile=0):
        self.box((x, y, .6), (2.5, 2.5, 1.2), 1)
        self.lathe(x, y, [(1.0, 1.2), (.95, 2.2), (.62, height - .4),
                          (.76, height - .4), (.76, height), (.49, height),
                          (.49, height - .55)], tile, 12)
        self.lathe(x, y, [(.48, height - .56), (.48, height - .54)], 9, 12)
        for z in (3.2, height * .58, height - 1):
            radius = .95 - .33 * (z - 2.2) / (height - 2.6)
            self.lathe(x, y, [(radius + .03, z), (radius + .03, z + .12)], 5, 12)

    def saw_roof(self, x, y, z, width, depth, teeth=4):
        for i in range(teeth):
            a, b = y - depth / 2 + i * depth / teeth, y - depth / 2 + (i + 1) * depth / teeth
            left, right = x - width / 2, x + width / 2
            peak = z + 1.4
            self.face([(left, a, z), (right, a, z), (right, b, peak), (left, b, peak)], 2)
            self.face([(left, b, peak), (right, b, peak), (right, b, z), (left, b, z)], 12)
            for px in (left, right):
                self.face([(px, a, z), (px, b, z), (px, b, peak)], 0)

    def gable(self, x, y, z, width, depth, rise, tile=3):
        left, right = x - width / 2, x + width / 2
        front, back = y - depth / 2, y + depth / 2
        self.face([(left, front, z), (x, front, z + rise), (x, back, z + rise), (left, back, z)], tile)
        self.face([(x, front, z + rise), (right, front, z), (right, back, z), (x, back, z + rise)], tile)
        for py in (front, back):
            self.face([(left, py, z), (right, py, z), (x, py, z + rise)], 1)


def civilian_geometry():
    g = FactoryGeometry()
    g.box((0, 0, -.15), (29, 23, .5), 4)
    for x in (-8, -1.5, 5):
        g.box((x, 1, 2.6), (5.8, 16, 5.0), 0)
        g.saw_roof(x, 1, 5.1, 6, 16)
        for side in (-1, 1):
            for y in (-4.8, -.9, 3, 6.9):
                g.window(x + side * 2.91, y, 3.4, 2.5, 2.1, side=True, reverse=side < 0)
            g.box((x + side * 2.94, 1, 1), (.12, 16.1, .26), 8)
        g.window(x, 9.01, 3.2, 3.8, 2.3, reverse=True)
    g.box((-1, -8.6, 2.0), (23, 3.2, 3.8), 0)
    g.box((-1, -8.6, 4.04), (23.5, 3.6, .28), 2)
    g.box((-1, -10.23, 3.65), (23.4, .2, .3), 8)
    for x in (-10, -7, -4, 3, 6, 9):
        g.window(x, -10.22, 2.2, 2.0, 1.8)
    g.window(-.5, -10.24, 1.5, 2.1, 2.8, tile=7)
    g.box((-.5, -10.6, 3.1), (3.1, 1.2, .2), 8)
    g.chimney(-11.5, 7.2, 16.3)
    g.chimney(10.6, 8.0, 12.8, 14)
    # The elevated tank gives civilian industry a silhouette beyond its roofs.
    for x in (9.4, 12.2):
        for y in (-3.5, -.7):
            g.beam((x, y, .15), (x, y, 7.5), .25)
    for y in (-3.5, -.7):
        g.beam((9.4, y, .6), (12.2, y, 7.1), .13)
        g.beam((12.2, y, .6), (9.4, y, 7.1), .13)
    g.lathe(10.8, -2.1, [(1.9, 7.2), (1.9, 10.0), (1.6, 10.2), (.12, 10.55)], 13, 12)
    g.lathe(10.8, -2.1, [(1.96, 7.2), (1.96, 7.4)], 5, 12)
    for x, y in ((11, -7), (12.4, -7), (12.4, -5.5)):
        g.box((x, y, .75), (1.2, 1.1, 1.3), 10)
    return g


def military_geometry():
    g = FactoryGeometry()
    g.box((0, 0, -.15), (30, 23, .5), 4)
    g.box((-4.5, 1.4, 3.1), (14.5, 17.4, 6), 1)
    g.gable(-4.5, 1.4, 6.1, 15, 17.8, 2.5)
    g.box((-4.5, 1.8, 8.4), (2.8, 13, 1.1), 12)
    g.gable(-4.5, 1.8, 8.95, 3.3, 13.4, .5, 3)
    for x in (-8.3, -.7):
        g.window(x, -7.31, 2.6, 5.0, 4.7, tile=7)
        g.box((x, -7.45, 5.1), (5.5, .6, .25), 5)
    for y in (-5, -1, 3, 7):
        g.window(-11.76, y, 4.1, 2.5, 2.0, side=True, reverse=True)
        g.box((-11.85, y + 1.8, 3), (.25, .35, 6), 8)
    g.box((7.5, 1.9, 2.05), (6.5, 16.4, 3.9), 14)
    g.box((7.5, 1.9, 4.16), (6.9, 16.8, .32), 3)
    for y in (-3.7, .4, 4.5, 8.1):
        g.window(10.76, y, 2.6, 2.8, 1.4, side=True)
    g.window(7.5, -6.31, 1.9, 4.2, 3.5, tile=7)
    g.chimney(11.4, 7.8, 13.3, 1)
    # A low enclosure leaves loading doors and roof geometry readable from the map.
    for x in (-14.4, 14.4):
        g.box((x, 0, .8), (.35, 22, 1.4), 1)
        for y in (-10.7, -3.5, 3.5, 10.7):
            g.box((x, y, 1.25), (.55, .55, 2.3), 8)
    g.box((0, 10.8, .8), (28.4, .35, 1.4), 1)
    for x, width in ((-10.3, 8), (9.5, 9.5)):
        g.box((x, -10.8, .8), (width, .35, 1.4), 1)
    for x in (-6.2, 4.6):
        g.box((x, -10.8, 1.6), (.65, .65, 3.0), 8)
    g.box((10, -8.4, 1.55), (3.2, 3.2, 2.9), 1)
    g.box((10, -8.4, 3.15), (3.6, 3.6, .3), 3)
    g.window(10, -10.02, 2.1, 2.1, 1.3)
    for x, y in ((3.3, -8.3), (4.6, -8.3), (3.3, -9.7)):
        g.box((x, y, .65), (1.1, 1.1, 1.1), 10)
    for x in (-8.3, -.7):
        for y in (-9, -8):
            g.box((x, y, .13), (4.5, .10, .04), 15)
    return g


def geometry(kind):
    g = civilian_geometry() if kind == "civilian" else military_geometry()
    g.vertices = [tuple(value * NATIVE_SCALE for value in vertex) for vertex in g.vertices]
    return g


def native_position(point):
    # Native mesh coordinates are X/right, Y/up, Z/depth; authoring uses Z/up.
    x, y, z = point
    return tuple(round(value * NATIVE_SCALE, 6) for value in (x, z, y))


def entity_text(kind):
    lines = ['entity = {', f'\tname = "building_{KINDS[kind]}"',
             '\tversion = 1', f'\tpdxmesh = "{model_name(kind)}_mesh"', '\tscale = 1']
    for prefix, points in (("factory_smoke", SMOKE[kind]), ("factory_damage", DAMAGE[kind])):
        for index, point in enumerate(points, 1):
            x, y, z = native_position(point)
            lines.extend(['\tlocator = {', f'\t\tname = "{prefix}_{index}"',
                          f'\t\tposition = {{ {x:.6f} {y:.6f} {z:.6f} }}', '\t}'])
    lines.append('\tdefault_state = "idle"')
    for state, prefix, particle, points in (
        ("idle", "factory_smoke", "factory_smoke_particle", SMOKE[kind]),
        ("damaged", "factory_damage", "building_damaged_particle", DAMAGE[kind]),
    ):
        lines.extend(['\tstate = {', f'\t\tname = "{state}"'])
        for index in range(1, len(points) + 1):
            lines.extend(['\t\tevent = {', '\t\t\ttime = 0.1',
                          f'\t\t\tnode = "{prefix}_{index}"',
                          f'\t\t\tparticle = "{particle}"', '\t\t}'])
        lines.append('\t}')
    return '\n'.join([*lines, '}'])


def section_outputs():
    meshes = []
    for kind in KINDS:
        name = model_name(kind)
        meshes.append('objectTypes = {\n\tpdxmesh = {\n'
                      f'\t\tname = "{name}_mesh"\n'
                      f'\t\tfile = "{MODEL_DIR.as_posix()}/{name}.mesh"\n'
                      '\t\tscale = 1\n\t}\n}')
    blocks = {
        "gfx/entities/mapitems_custom.gfx": '\n\n'.join(meshes),
        "gfx/entities/zz_ADISCORD_building_entities.asset": '\n\n'.join(entity_text(kind) for kind in KINDS),
    }
    result = {}
    start, end = '# BEGIN ' + MARKER, '# END ' + MARKER
    for relative, block in blocks.items():
        path = ROOT / relative
        original = path.read_bytes()
        newline = '\r\n' if b'\r\n' in original else '\n'
        section = (start + '\n# Generated by tools/builders/build_adiscord_factory_models.py\n'
                   + block + '\n' + end + '\n').replace('\n', newline).encode()
        pattern = re.escape(start.encode()) + rb'.*?' + re.escape(end.encode()) + rb'\r?\n?'
        matches = list(re.finditer(pattern, original, flags=re.S))
        if len(matches) > 1:
            raise ValueError(f'Duplicate factory section: {path}')
        if matches:
            match = matches[0]
            result[path] = original[:match.start()] + section + original[match.end():]
        else:
            for kind in KINDS:
                if model_name(kind).encode() in original:
                    raise ValueError(f'Unowned factory entry: {path}')
            result[path] = original + newline.encode() + section
    return result


def build_native(stage):
    import bpy
    from mathutils import Vector
    from types import SimpleNamespace

    pdx = load_exporter()
    from io_pdx_mesh import pdx_data

    models = {}
    for kind in KINDS:
        bpy.ops.wm.read_factory_settings(use_empty=True)
        obj = geometry(kind).make_object()
        obj.name = obj.data.name = model_name(kind)
        obj.data.materials.append(pdx.create_shader(SimpleNamespace(
            shader=["PdxMeshAdvancedSnow"], diff=[TEXTURES[0]], n=[TEXTURES[1]], spec=[TEXTURES[2]],
        ), "Factory masonry, metal and glazing", str(stage)))
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        path = stage / (model_name(kind) + '.mesh')
        pdx.export_meshfile(str(path), exp_selected=True, exp_skel=False, exp_locs=False)
        tree = pdx_data.read_meshfile(str(path))
        for shape in tree.find('object'):
            for mesh in shape.findall('mesh'):
                mesh.attrib['ta'] = [round(value, 5) for value in mesh.attrib['ta']]
        pdx_data.write_meshfile(str(path), tree)
        bpy.ops.file.pack_all()
        for screen in bpy.data.screens:
            for area in screen.areas:
                if area.type == 'VIEW_3D':
                    area.spaces.active.shading.type = 'MATERIAL'
                    region = area.spaces.active.region_3d
                    region.view_location = (0, 0, .4)
                    region.view_distance = 4
                    region.view_rotation = Vector((3, -4, 3)).to_track_quat('Z', 'Y')
        bpy.context.preferences.filepaths.save_version = 0
        source = stage / (kind + '.blend')
        bpy.ops.wm.save_as_mainfile(filepath=str(source))
        models[kind] = verify_native(stage, kind, pdx)
        models[kind]['source_blend_sha256'] = digest(source)
    report = {'models': models, 'files': {name: digest(stage / name) for name in files()},
              'native_reimport': True, 'hoi4_runtime_verified': False}
    (stage / 'native.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')


def verify_native(folder, kind, pdx=None):
    import bpy
    from mathutils import Vector

    pdx = pdx or load_exporter()
    from io_pdx_mesh import pdx_data

    path = folder / (model_name(kind) + '.mesh')
    tree = pdx_data.read_meshfile(str(path))
    vertices = triangles = materials = 0
    native_points = []
    for shape in tree.find('object'):
        for element in shape.findall('mesh'):
            data = pdx_data.PDXData(element)
            count = len(data.p) // 3
            native_points.extend(tuple(data.p[i:i + 3]) for i in range(0, len(data.p), 3))
            assert 0 < count < 65536
            assert len(data.n) == count * 3 and len(data.u0) == count * 2 and len(data.ta) == count * 4
            assert all(math.isfinite(v) for v in data.p + data.n + data.u0 + data.ta)
            assert len(data.tri) % 3 == 0 and min(data.tri) >= 0 and max(data.tri) < count
            for i in range(0, len(data.tri), 3):
                a, b, c = [Vector(data.p[j * 3:j * 3 + 3]) for j in data.tri[i:i + 3]]
                assert (b - a).cross(c - a).length > 1e-10
            assert data.material.shader == ['PdxMeshAdvancedSnow']
            for key, expected in zip(('diff', 'n', 'spec'), TEXTURES):
                assert getattr(data.material, key) == [expected]
                raw = (folder / expected).read_bytes()
                assert raw[:4] == b'DDS ' and raw[84:88] == b'DXT5'
                assert struct.unpack_from('<I', raw, 28)[0] == 11
            vertices += count
            triangles += len(data.tri) // 3
            materials += 1
    assert triangles < 3500 and materials == 1
    for point in SMOKE[kind]:
        x, y, z = native_position(point)
        rim = {p for p in native_points
               if abs(p[1] - y) < 1e-6 and math.hypot(p[0] - x, p[2] - z) < .06}
        assert len(rim) >= 12, 'Smoke locator must meet an exported chimney rim'
        assert abs(sum(p[0] for p in rim) / len(rim) - x) < 1e-6
        assert abs(sum(p[2] for p in rim) / len(rim) - z) < 1e-6
    bpy.ops.wm.read_factory_settings(use_empty=True)
    pdx.import_meshfile(str(path), imp_locs=False)
    meshes = [o for o in bpy.context.scene.objects if o.type == 'MESH']
    assert len(meshes) == 1
    points = [o.matrix_world @ v.co for o in meshes for v in o.data.vertices]
    bounds = [[round(min(v[i] for v in points), 6), round(max(v[i] for v in points), 6)] for i in range(3)]
    assert bounds[0][1] - bounds[0][0] < 2.3 and bounds[1][1] - bounds[1][0] < 1.8
    return {'vertices': vertices, 'triangles': triangles, 'materials': materials,
            'bounds_blender_xyz': bounds, 'entity': 'building_' + KINDS[kind],
            'smoke_native_xyz': [native_position(point) for point in SMOKE[kind]],
            'damage_native_xyz': [native_position(point) for point in DAMAGE[kind]]}


def render_preview():
    import bpy
    from mathutils import Vector

    pdx = load_exporter()
    for kind in KINDS:
        verify_native(ROOT / MODEL_DIR, kind, pdx)
        scene = bpy.context.scene
        scene.render.engine = 'CYCLES'
        scene.cycles.samples = 32
        scene.cycles.use_denoising = True
        scene.render.resolution_x, scene.render.resolution_y = 1440, 1080
        scene.render.resolution_percentage = 100
        scene.world = bpy.data.worlds.new('Neutral factory studio')
        scene.world.use_nodes = True
        scene.world.node_tree.nodes['Background'].inputs[0].default_value = (.35, .38, .42, 1)
        scene.world.node_tree.nodes['Background'].inputs[1].default_value = .65
        for material in bpy.data.materials:
            shader = material.node_tree.nodes.get('Principled BSDF') if material.use_nodes else None
            if shader:
                for link in list(shader.inputs['Roughness'].links):
                    material.node_tree.links.remove(link)
                shader.inputs['Roughness'].default_value = .75
        bpy.ops.mesh.primitive_plane_add(size=20, location=(0, 0, -.018))
        floor = bpy.context.object
        floor.name = 'Studio floor, not exported'
        mat = bpy.data.materials.new('Neutral ground')
        mat.diffuse_color = (.28, .27, .24, 1)
        floor.data.materials.append(mat)
        for location, energy in (((-3, -4, 5), 550), ((3, -1, 3), 220), ((0, 3, 4), 500)):
            bpy.ops.object.light_add(type='AREA', location=location)
            light = bpy.context.object
            light.data.energy, light.data.size = energy, 3
            light.rotation_euler = (Vector((0, 0, .35)) - light.location).to_track_quat('-Z', 'Y').to_euler()
        bpy.ops.object.camera_add()
        camera = bpy.context.object
        camera.data.type = 'ORTHO'
        camera.data.ortho_scale = 3.25
        scene.camera = camera
        (ROOT / PREVIEW).mkdir(parents=True, exist_ok=True)
        for view, position in (('front', (3, -4, 3)), ('map', (2, -3, 5)), ('rear', (-3, 4, 3))):
            camera.location = position
            camera.rotation_euler = (Vector((0, 0, .4)) - camera.location).to_track_quat('-Z', 'Y').to_euler()
            scene.render.filepath = str(ROOT / PREVIEW / f'{kind}_{view}.png')
            bpy.ops.render.render(write_still=True)


def stale_outputs():
    expected = section_outputs()
    expected.update({ROOT / MODEL_DIR / name: data for name, data in textures().items()})
    changed = [path.relative_to(ROOT).as_posix() for path, data in expected.items()
               if not path.exists() or path.read_bytes() != data]
    if not (ROOT / REPORT).exists():
        return [*changed, REPORT.as_posix()]
    report = json.loads((ROOT / REPORT).read_text(encoding='utf-8'))
    if report.get('input_sha256') != input_hashes() or not report.get('native_reimport'):
        changed.append(REPORT.as_posix())
    if set(report.get('files', {})) != set(files()) or set(report.get('models', {})) != set(KINDS):
        changed.append(REPORT.as_posix())
    for name in files():
        path = ROOT / MODEL_DIR / name
        if not path.exists() or digest(path) != report.get('files', {}).get(name):
            changed.append(path.relative_to(ROOT).as_posix())
    for kind in KINDS:
        source = ROOT / SOURCE_DIR / (kind + '.blend')
        if not source.exists() or digest(source) != report.get('models', {}).get(kind, {}).get('source_blend_sha256'):
            changed.append(source.relative_to(ROOT).as_posix())
    return sorted(set(changed))


def find_blender(explicit):
    for candidate in (explicit, os.environ.get('BLENDER_EXE'), shutil.which('blender'),
                      'C:/Program Files/Blender Foundation/Blender 4.5/blender.exe'):
        if candidate and Path(candidate).is_file():
            return str(candidate)
    raise RuntimeError('Blender is required for --apply; provide --blender or BLENDER_EXE')


def run_blender(executable, arguments):
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
    subprocess.run([executable, '--background', '--factory-startup', '--threads', '4',
                    '--python-exit-code', '1', '--python', str(Path(__file__)), '--', *arguments],
                   check=True, env=env)


def apply(executable):
    hashes = input_hashes()
    with tempfile.TemporaryDirectory(prefix='adiscord-factory-models-') as directory:
        stage = Path(directory)
        for name, data in textures().items():
            (stage / name).write_bytes(data)
        run_blender(executable, ['--build-dir', str(stage)])
        assert hashes == input_hashes(), 'Factory authoring inputs changed during export'
        report = json.loads((stage / 'native.json').read_text(encoding='utf-8'))
        report['input_sha256'] = hashes
        contents = {ROOT / MODEL_DIR / name: (stage / name).read_bytes() for name in files()}
        for kind in KINDS:
            contents[ROOT / SOURCE_DIR / (kind + '.blend')] = (stage / (kind + '.blend')).read_bytes()
        contents[ROOT / REPORT] = (json.dumps(report, indent=2) + '\n').encode()
        contents.update(section_outputs())
        for path, data in contents.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            if not path.exists() or path.read_bytes() != data:
                path.write_bytes(data)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--check', action='store_true')
    mode.add_argument('--apply', action='store_true')
    mode.add_argument('--preview', action='store_true')
    mode.add_argument('--build-dir', type=Path, help=argparse.SUPPRESS)
    mode.add_argument('--render-native', action='store_true', help=argparse.SUPPRESS)
    parser.add_argument('--blender')
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else None)
    if args.build_dir:
        build_native(args.build_dir)
        return
    if args.render_native:
        render_preview()
        return
    changed = stale_outputs()
    print(json.dumps({'stale': changed, 'apply': args.apply}), flush=True)
    if args.apply and changed:
        apply(find_blender(args.blender))
        changed = stale_outputs()
        assert not changed, changed
    if args.preview:
        if changed:
            raise RuntimeError('Rebuild stale outputs before rendering')
        run_blender(find_blender(args.blender), ['--render-native'])
    raise SystemExit(bool(changed))


if __name__ == '__main__':
    main()
