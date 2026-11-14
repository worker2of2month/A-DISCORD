"""Build three aligned native construction stages for NAM's Great Shift combine.

--check is read-only; --apply exports meshes and packed Blender sources.
--preview renders the exported meshes, not the authoring geometry.
"""

from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
import re
import struct
import subprocess
import sys
import tempfile

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.builders.build_adiscord_factory_models import FactoryGeometry, digest, find_blender, textures
from tools.assets.source.build_shl_palace import load_exporter

NAME = "ADISCORD_NAM_combine"
MODEL = Path("gfx/models/buildings/NAM_combine")
SOURCE = Path("tools/assets/source/buildings/NAM/combine")
REPORT = Path("docs/development/model-verification/NAM_combine.json")
PREVIEW = Path("docs/development/previews/NAM_combine")
STAGES = ("foundations", "assembly", "complete")
ASSETS = (*STAGES, "reserve")
CHIMNEYS = tuple((x, 35, 44 if i < 3 else 36)
                 for i, x in enumerate((-43, -33, -23, -13, -3, 7)))
SMOKE_PARTICLE = f"{NAME}_smoke_particle"
TEXTURES = tuple(f"{NAME}_{channel}.dds" for channel in ("diffuse", "normal", "specular"))
INPUTS = (Path(__file__).relative_to(ROOT), Path("tools/builders/build_adiscord_factory_models.py"),
          Path("tools/assets/source/build_shl_palace.py"))


def name(stage):
    return f"{NAME}_{stage}"


class CombineGeometry(FactoryGeometry):
    def chimney(self, x, y, height, tile=0):
        start = len(self.vertices)
        super().chimney(x, y, height, tile)
        self.vertices[start:] = [(x + (px - x) * 2.3, y + (py - y) * 2.3, pz)
                                 for px, py, pz in self.vertices[start:]]

    def panel(self, points, tile, subdivide=False):
        # Small masonry courses establish the scale of the landmark's long walls.
        from tools.assets.source.build_shl_palace import Geometry

        Geometry.panel(self, points, tile, subdivide=tile in (0, 14))

    def crane(self, x, y, height, direction=1):
        self.box((x, y, .5), (4, 4, 1), 1)
        for z in range(1, height, 3):
            top = min(z + 3, height)
            for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
                self.beam((x + sx, y + sy, z), (x + sx, y + sy, top), .22, 15)
                self.beam((x + sx, y + sy, z), (x - sx, y + sy, top), .12, 15)
                self.beam((x + sx, y + sy, z), (x + sx, y - sy, top), .12, 15)
        for sy in (-.65, .65):
            self.beam((x - direction * 5, y + sy, height), (x + direction * 15, y + sy, height), .25, 15)
            self.beam((x - direction * 5, y + sy, height + 1.5), (x + direction * 15, y + sy, height + 1.5), .2, 15)
            for i in range(-5, 15, 2):
                self.beam((x + direction * i, y + sy, height),
                          (x + direction * (i + 2), y + sy, height + 1.5), .13, 15)
        self.box((x - direction * 4, y, height - .6), (3, 2.3, 1.6), 1)
        self.box((x + direction * 1.5, y, height - .8), (2, 2, 1.5), 15)
        self.window(x + direction * 1.5, y - 1.01, height - .7, 1.5, .8)
        self.beam((x + direction * 11, y, height), (x + direction * 11, y, height - 9), .09, 9)
        self.box((x + direction * 11, y, height - 9), (.6, .6, .8), 5)

    def pipe(self, a, b, radius=.28):
        from mathutils import Vector

        a, b = Vector(a), Vector(b)
        axis = (b - a).normalized()
        guide = Vector((0, 0, 1)) if abs(axis.z) < .9 else Vector((0, 1, 0))
        u = axis.cross(guide).normalized() * radius
        v = axis.cross(u).normalized() * radius
        low = [a + math.cos(i * math.tau / 8) * u + math.sin(i * math.tau / 8) * v for i in range(8)]
        high = [p + b - a for p in low]
        for i in range(8):
            j = (i + 1) % 8
            self.face([low[i], low[j], high[j], high[i]], 11)
        self.face(list(reversed(low)), 5, [(.5, .5)] * 8)
        self.face(high, 5, [(.5, .5)] * 8)


def hall(g, x, y, width, depth, height, state, bays):
    g.box((x, y, .4), (width + 1, depth + 1, .8), 1)
    xs = [x - width / 2 + i * width / bays for i in range(bays + 1)]
    front, back = y - depth / 2, y + depth / 2
    if state == "foundations":
        for px in xs:
            for py in (front, back):
                g.box((px, py, 1), (2, 2, 1.2), 1)
        for py in (front, back):
            g.box((x, py, .9), (width, .7, 1), 1)
        return
    if state == "assembly":
        for px in xs:
            for py in (front, back):
                g.beam((px, py, .8), (px, py, height), .5)
            g.beam((px, front, height), (px, y, height + 4), .4)
            g.beam((px, back, height), (px, y, height + 4), .4)
            g.beam((px, front, height), (px, back, height), .3)
            g.beam((px, front + depth * .25, height), (px, y, height + 4), .2)
            g.beam((px, back - depth * .25, height), (px, y, height + 4), .2)
        for py, z in ((front, height), (back, height), (y, height + 4)):
            g.beam((xs[0], py, z), (xs[-1], py, z), .4)
        g.box((x, back, 3), (width, .5, 6), 0)
        g.box((xs[0], y, 4), (.5, depth, 8), 0)
        return
    g.box((x, y, height / 2), (width, depth, height), 0)
    # The long ridge follows the main hall, with a raised glazed clerestory.
    g.face([(xs[0] - .5, front - .5, height), (xs[-1] + .5, front - .5, height),
            (xs[-1] + .5, y, height + 4), (xs[0] - .5, y, height + 4)], 2)
    g.face([(xs[0] - .5, y, height + 4), (xs[-1] + .5, y, height + 4),
            (xs[-1] + .5, back + .5, height), (xs[0] - .5, back + .5, height)], 2)
    for px in (xs[0], xs[-1]):
        g.face([(px, front, height), (px, y, height + 4), (px, back, height)], 0)
    g.box((x, y, height + 4), (width - 5, 4, 2), 5)
    for px in xs:
        for py in (front - .2, back + .2):
            g.box((px, py, height / 2), (.6, .6, height + .4), 14)
    for i in range(bays):
        px = (xs[i] + xs[i + 1]) / 2
        for py, reverse in ((front - .32, False), (back + .32, True)):
            g.window(px, py, height * .58, width / bays - 1.4, height * .58, reverse=reverse)
        g.window(px, y - 2.02, height + 4, width / bays - .7, 1.4)
    for i in range(max(2, int(depth / 5))):
        py = front + (i + .5) * depth / max(2, int(depth / 5))
        g.window(xs[-1] + .02, py, height * .58, 3, height * .58, side=True)
    g.box((x, front - .4, 1.6), (2.5, .7, 3.2), 5)
    for py in (front, back):
        g.box((x, py, height - .4), (width + 1, .8, .55), 8)


def geometry(stage):
    if stage == "reserve":
        return reserve_geometry()
    g = CombineGeometry()
    g.box((0, 0, -7), (126, 82, 14), 4)
    hall(g, -11, 3, 66, 28, 25, stage, 14)
    hall(g, -23, -23, 48, 13, 12, "complete" if stage == "assembly" else stage, 10)
    hall(g, -20, 25, 54, 12, 14, stage, 12)
    hall(g, -54, 2, 12, 45, 10, stage, 3)
    # Two batteries flank the main hall; the shorter cluster gives a stepped skyline.
    for i, (x, y, height) in enumerate(CHIMNEYS):
        g.box((x, 35, .5), (4.5, 4.5, 1), 1)
        if stage != "foundations":
            g.chimney(x, y, height if stage == "complete" else 10 + i % 3 * 3)
    tanks = [(x, y) for x in (42, 55) for y in (3, 17, 31)]
    for x, y in tanks:
        g.lathe(x, y, [(5.4, .1), (5.4, .65)], 1, 20)
        if stage != "foundations":
            height = 4 if stage == "assembly" else 10
            g.lathe(x, y, [(4.9, .65), (4.9, height), (4.1, height + 1)], 11, 20)
            for z in (2, height - .4):
                g.lathe(x, y, [(4.95, z), (4.95, z + .2)], 5, 20)
            if stage == "complete":
                g.beam((x + 5, y, 1), (x + 5, y, height + 1), .18, 15)
                g.beam((x + 5, y + .8, 1), (x + 5, y + .8, height + 1), .18, 15)
                for z in range(1, height + 1):
                    g.beam((x + 5, y, z), (x + 5, y + .8, z), .12, 15)
    columns = ((24, -21, 33), (35, -20, 25), (46, -22, 20), (25, -3, 28), (27, 16, 22))
    for x, y, h in columns:
        g.box((x, y, .5), (7, 7, 1), 1)
        if stage == "foundations":
            continue
        height = h if stage == "complete" else h * .45
        g.lathe(x, y, [(2.2, 1), (2.2, height), (1.6, height + 1)], 7, 16)
        for z in range(5, int(height), 5):
            g.box((x, y, z), (6, 6, .25), 5)
            for sy in (-3, 3):
                g.beam((x - 3, y + sy, z + 1), (x + 3, y + sy, z + 1), .13, 15)
                for sx in (-3, 3):
                    g.beam((x + sx, y + sy, z), (x + sx, y + sy, z + 1), .13, 15)
        g.pipe((x + 2.6, y, 1.2), (x + 2.6, y, height - 1), .3)
    if stage == "foundations":
        for x, y, h, direction in ((-55, -29, 30, 1), (12, 19, 38, -1), (42, -29, 29, -1), (-50, 33, 26, 1)):
            g.crane(x, y, h, direction)
        for x in range(-43, 10, 8):
            g.box((x, -35, .8), (5, 3, 1.6), 0)
            g.box((x, 38, .6), (5, 1.4, 1.2), 2)
    else:
        if stage == "assembly":
            g.crane(12, 19, 38, -1)
            g.crane(42, -29, 31, -1)
            g.crane(-55, -29, 30, 1)
        # Two intersecting service galleries connect every process district.
        for x in range(-56, 58, 8):
            for y in (-35, -31):
                g.beam((x, y, 0), (x, y, 5), .35)
            g.beam((x, -35, 5), (x, -31, 5), .35)
        for y in range(-31, 34, 8):
            for x in (13, 17):
                g.beam((x, y, 0), (x, y, 8), .4)
            g.beam((13, y, 8), (17, y, 8), .3)
        for offset in (0, 1, 2, 3):
            g.pipe((-58, -34.5 + offset, 5.4), (58, -34.5 + offset, 5.4), .32)
            g.pipe((13.5 + offset, -34, 8.4), (13.5 + offset, 36, 8.4), .3)
        if stage == "complete":
            g.pipe((15, 36, 8.4), (15, 36, 3), .55)
            g.pipe((15, 36, 3), (0, 36, 3), .55)
            g.pipe((0, 36, 3), (0, 30, 3), .55)
            g.pipe((58, -33, 5.4), (58, -22, 5.4), .55)
            g.pipe((58, -22, 5.4), (46, -22, 5.4), .55)
            for x, y in tanks:
                g.pipe((x, y, 1.5), (15, y, 1.5), .35)
            for x, y, h in columns:
                g.pipe((15, y, 8.4), (x, y, 8.4), .45)
            # Small freight cars and sleepers supply a human-scale reference.
            for y in (-39.5, -38):
                g.beam((-60, y, .2), (60, y, .2), .12)
            for x in range(-59, 60, 2):
                g.box((x, -38.75, .1), (.3, 3, .15), 10)
            for x in (-26, -16, -6, 4):
                g.box((x, -38.75, 1), (8, 2.4, 1.1), 5)
                g.box((x, -38.75, 2.4), (7.5, 2.3, 1.8), 14)
                for dx in (-2.5, 2.5):
                    g.box((x + dx, -38.75, .6), (1.3, 2.8, .7), 9)
    return g


def reserve_geometry():
    """Small industrial works retained as an unplaced asset for a future site."""
    g = FactoryGeometry()
    g.box((0, 0, -.6), (52, 36, 1.2), 4)
    g.box((-7, 2, .3), (27, 23, .6), 1)
    for x in (-19, -11, -3, 5):
        for y in (-8, 1, 12):
            g.box((x, y, .65), (2, 2, .7), 1)
            g.beam((x, y, 1), (x, y, 12), .45)
        for a, b in (((x, -8, 12), (x, 2, 16)), ((x, 2, 16), (x, 12, 12)),
                     ((x, -8, 12), (x, 12, 12))):
            g.beam(a, b, .36)
    g.box((-7, 2, 6), (27, 23, 12), 0)
    g.gable(-7, 2, 12, 28, 24, 4, 2)
    g.box((-7, 2, 16), (3, 19, 1), 11)
    for x in (-17, -12, -7, -2, 3):
        g.window(x, -9.52, 7, 3.2, 7.8)
        g.box((x, -9.65, 11.1), (3.7, .5, .45), 8)
    for y in (-5, 0, 5, 10):
        g.window(6.52, y, 7, 3.1, 7.8, side=True)
    g.box((-7, -9.8, 2), (4, .5, 4), 5)
    for x in (-21, -16, -11, -6):
        g.chimney(x, 15, 25)
    for y in (3, 12):
        g.lathe(19, y, [(3.8, .2), (3.8, 8), (3.2, 8.65)], 11, 20)
        for z in (1, 7.8):
            g.lathe(19, y, [(3.85, z), (3.85, z + .15)], 5, 20)
    g.lathe(12, -4, [(1.8, .2), (1.8, 19), (1.3, 20)], 7, 16)
    for z in range(4, 19, 4):
        g.box((12, -4, z), (5.4, 5.4, .2), 5)
        for sx in (-2.5, 2.5):
            g.beam((12 + sx, -6.5, z), (12 + sx, -6.5, z + 1.1), .1, 15)
            g.beam((12 + sx, -6.5, z + 1.1), (12 + sx, -1.5, z + 1.1), .1, 15)
    for x in range(-22, 23, 8):
        for y in (-16, -12):
            g.beam((x, y, 0), (x, y, 3), .3)
        g.beam((x, -16, 3), (x, -12, 3), .3)
    for y in (-15.5, -14.5, -13.5, -12.5):
        CombineGeometry.pipe(g, (-23, y, 3.4), (22, y, 3.4))
    CombineGeometry.pipe(g, (12, -13.5, 3.4), (12, -4, 3.4), .5)
    CombineGeometry.pipe(g, (12, -4, 3.4), (12, -4, 18), .5)
    for y in (3, 12):
        CombineGeometry.pipe(g, (19, y, 1.2), (9, y, 1.2), .4)
    for x in (-20, -14, -8):
        g.box((x, -11, .35), (4, 1.2, .7), 1)
    return g


def entity_text(stage):
    lines = ['entity = {', f'\tname = "{name(stage)}_entity"',
             f'\tpdxmesh = "{name(stage)}_mesh"']
    if stage == "complete":
        # Mesh coordinates use Y/up; authoring geometry uses Z/up.
        # Include the rising plumes in the entity's visibility bounds.
        lines.append('\tcull_radius = 180')
        for index, (x, y, height) in enumerate(CHIMNEYS, 1):
            lines.extend(['\tlocator = {', f'\t\tname = "chimney_{index}"',
                          f'\t\tposition = {{ {x} {height} {y} }}', '\t}'])
        lines.extend(['\tdefault_state = "idle"', '\tstate = {', '\t\tname = "idle"'])
        for index in range(1, len(CHIMNEYS) + 1):
            lines.extend(['\t\tevent = {', '\t\t\ttime = 0.1',
                          f'\t\t\tnode = "chimney_{index}"',
                          f'\t\t\tparticle = "{SMOKE_PARTICLE}"',
                          '\t\t\ttrigger_once = yes', '\t\t\tkeep_particle = no', '\t\t}'])
        lines.append('\t}')
    return '\n'.join([*lines, '}'])


def section_outputs():
    meshes = [f'\tpdxmesh = {{\n\t\tname = "{name(s)}_mesh"\n\t\tfile = "{(MODEL / (name(s) + ".mesh")).as_posix()}"\n\t\tscale = 1\n\t}}' for s in ASSETS]
    # The actor's 0.09 scale also scales particles; restore a factory-sized plume.
    meshes.append(f'\tpdxparticle = {{\n\t\tname = "{SMOKE_PARTICLE}"\n'
                  '\t\ttype = "factory_smoke_file"\n\t\tscale = 12\n\t}')
    entities = [entity_text(s) for s in ASSETS]
    blocks = {"gfx/entities/mapitems_custom.gfx": "objectTypes = {\n" + "\n".join(meshes) + "\n}",
              "gfx/entities/mapitems_custom.asset": "\n\n".join(entities)}
    result = {}
    for relative, block in blocks.items():
        path = ROOT / relative
        original = path.read_bytes()
        nl = "\r\n" if b"\r\n" in original else "\n"
        start, end = f"# BEGIN {NAME}", f"# END {NAME}"
        section = (start + "\n# Generated by tools/builders/build_adiscord_nam_combine.py\n" + block + "\n" + end + "\n").replace("\n", nl).encode()
        pattern = re.escape(start.encode()) + rb".*?" + re.escape(end.encode()) + rb"\r?\n?"
        matches = list(re.finditer(pattern, original, re.S))
        assert len(matches) <= 1
        if matches:
            m = matches[0]
            result[path] = original[:m.start()] + section + original[m.end():]
        else:
            assert NAME.encode() not in original
            result[path] = original + nl.encode() + section
    return result


def input_hashes():
    return {p.as_posix(): digest(ROOT / p) for p in INPUTS}


def verify(folder, stage, pdx):
    import bpy
    from mathutils import Vector
    from io_pdx_mesh import pdx_data

    path = folder / (name(stage) + ".mesh")
    tree = pdx_data.read_meshfile(str(path))
    triangles = vertices = materials = 0
    native_points = []
    for shape in tree.find("object"):
        for element in shape.findall("mesh"):
            data = pdx_data.PDXData(element)
            native_points.extend(tuple(data.p[i:i + 3]) for i in range(0, len(data.p), 3))
            count = len(data.p) // 3
            assert 0 < count < 65536
            assert len(data.n) == count * 3 and len(data.u0) == count * 2 and len(data.ta) == count * 4
            assert all(math.isfinite(v) for v in data.p + data.n + data.u0 + data.ta)
            assert min(data.tri) >= 0 and max(data.tri) < count
            for i in range(0, len(data.tri), 3):
                a, b, c = [Vector(data.p[j * 3:j * 3 + 3]) for j in data.tri[i:i + 3]]
                assert (b - a).cross(c - a).length > 1e-8
            assert data.material.shader == ["PdxMeshAdvancedSnow"]
            for key, texture in zip(("diff", "n", "spec"), TEXTURES):
                assert getattr(data.material, key) == [texture]
                raw = (folder / texture).read_bytes()
                assert raw[:4] == b"DDS " and raw[84:88] == b"DXT5"
                assert struct.unpack_from("<I", raw, 28)[0] == 11
            vertices += count
            triangles += len(data.tri) // 3
            materials += 1
    assert triangles < 24000 and materials == 1
    if stage == "complete":
        for x, y, height in CHIMNEYS:
            rim = {p for p in native_points
                   if abs(p[1] - height) < 1e-5 and math.hypot(p[0] - x, p[2] - y) < 1.8}
            assert len(rim) >= 12, "Smoke locator must meet an exported chimney rim"
            assert abs(sum(p[0] for p in rim) / len(rim) - x) < 1e-5
            assert abs(sum(p[2] for p in rim) / len(rim) - y) < 1e-5
    bpy.ops.wm.read_factory_settings(use_empty=True)
    pdx.import_meshfile(str(path), imp_locs=False)
    objects = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    assert len(objects) == 1
    points = [v.co for v in objects[0].data.vertices]
    bounds = [[round(min(v[i] for v in points), 5), round(max(v[i] for v in points), 5)] for i in range(3)]
    expected = [[-26, 26], [-18, 18]] if stage == "reserve" else [[-63, 63], [-41, 41]]
    assert bounds[:2] == expected, bounds
    return {"vertices": vertices, "triangles": triangles, "materials": materials, "bounds": bounds}


def build(folder):
    import bpy
    from types import SimpleNamespace
    pdx = load_exporter()
    from io_pdx_mesh import pdx_data
    models = {}
    for stage in ASSETS:
        bpy.ops.wm.read_factory_settings(use_empty=True)
        obj = geometry(stage).make_object()
        obj.name = obj.data.name = name(stage)
        obj.data.materials.append(pdx.create_shader(SimpleNamespace(
            shader=["PdxMeshAdvancedSnow"], diff=[TEXTURES[0]], n=[TEXTURES[1]], spec=[TEXTURES[2]]),
            "Combine brick, steel and glass", str(folder)))
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        path = folder / (name(stage) + ".mesh")
        pdx.export_meshfile(str(path), exp_selected=True, exp_skel=False, exp_locs=False)
        tree = pdx_data.read_meshfile(str(path))
        for shape in tree.find("object"):
            for mesh in shape.findall("mesh"):
                mesh.attrib["ta"] = [round(v, 5) for v in mesh.attrib["ta"]]
        pdx_data.write_meshfile(str(path), tree)
        bpy.ops.file.pack_all()
        bpy.context.preferences.filepaths.save_version = 0
        bpy.ops.wm.save_as_mainfile(filepath=str(folder / (stage + ".blend")))
        models[stage] = verify(folder, stage, pdx)
    (folder / "native.json").write_text(json.dumps({"models": models, "native_reimport": True,
        "hoi4_runtime_verified": False}, indent=2) + "\n", encoding="utf-8")


def render():
    import bpy
    from mathutils import Vector

    pdx = load_exporter()
    (ROOT / PREVIEW).mkdir(parents=True, exist_ok=True)
    for stage in ASSETS:
        verify(ROOT / MODEL, stage, pdx)
        scene = bpy.context.scene
        scene.render.engine = "CYCLES"
        scene.cycles.samples = 32
        scene.cycles.use_denoising = True
        scene.render.resolution_x, scene.render.resolution_y = 1200, 900
        scene.render.resolution_percentage = 100
        scene.world = bpy.data.worlds.new("Combine studio")
        scene.world.use_nodes = True
        scene.world.node_tree.nodes["Background"].inputs[0].default_value = (.32, .36, .42, 1)
        scene.world.node_tree.nodes["Background"].inputs[1].default_value = .7
        if stage != "reserve":
            # The buried retaining foundation is not part of the visible skyline.
            bpy.ops.mesh.primitive_plane_add(size=1000, location=(0, 0, -.15))
            ground = bpy.data.materials.new("Neutral terrain, not exported")
            ground.diffuse_color = (.22, .22, .2, 1)
            bpy.context.object.data.materials.append(ground)
        for material in bpy.data.materials:
            node = material.node_tree.nodes.get("Principled BSDF") if material.use_nodes else None
            if node:
                for link in list(node.inputs["Roughness"].links):
                    material.node_tree.links.remove(link)
                node.inputs["Roughness"].default_value = .7
        for pos, energy in (((-60, -90, 120), 70000), ((90, -20, 80), 36000), ((0, 90, 100), 64000)):
            bpy.ops.object.light_add(type="AREA", location=pos)
            lamp = bpy.context.object
            lamp.data.energy, lamp.data.size = energy, 65
            lamp.rotation_euler = (Vector((0, 0, 6)) - lamp.location).to_track_quat("-Z", "Y").to_euler()
        bpy.ops.object.camera_add(location=(115, -165, 120))
        camera = bpy.context.object
        camera.data.type = "ORTHO"
        camera.data.ortho_scale = 77 if stage == "reserve" else 180
        camera.rotation_euler = (Vector((0, 0, 12)) - camera.location).to_track_quat("-Z", "Y").to_euler()
        scene.camera = camera
        scene.render.filepath = str(ROOT / PREVIEW / (stage + ".png"))
        bpy.ops.render.render(write_still=True)


def run_blender(args):
    subprocess.run([find_blender(None), "--background", "--factory-startup", "--threads", "4",
                    "--python-exit-code", "1", "--python", str(Path(__file__)), "--", *args],
                   env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"), check=True)


def stale():
    changed = [str(p.relative_to(ROOT)) for p, data in section_outputs().items() if p.read_bytes() != data]
    path = ROOT / REPORT
    if not path.exists():
        return [*changed, str(REPORT)]
    report = json.loads(path.read_text(encoding="utf-8"))
    if report.get("input_sha256") != input_hashes():
        changed.append(str(REPORT))
    for relative, sha in report["files"].items():
        p = ROOT / relative
        if not p.exists() or digest(p) != sha:
            changed.append(relative)
    return changed


def apply():
    hashes = input_hashes()
    with tempfile.TemporaryDirectory(prefix="adiscord-nam-combine-") as directory:
        folder = Path(directory)
        for texture, data in zip(TEXTURES, textures().values()):
            (folder / texture).write_bytes(data)
        run_blender(["--build-dir", str(folder)])
        assert hashes == input_hashes()
        report = json.loads((folder / "native.json").read_text(encoding="utf-8"))
        contents = {ROOT / MODEL / n: (folder / n).read_bytes()
                    for n in [*TEXTURES, *(name(s) + ".mesh" for s in ASSETS)]}
        contents.update({ROOT / SOURCE / (s + ".blend"): (folder / (s + ".blend")).read_bytes() for s in ASSETS})
        import hashlib

        report["files"] = {p.relative_to(ROOT).as_posix(): hashlib.sha256(data).hexdigest() for p, data in contents.items()}
        report["input_sha256"] = hashes
        contents[ROOT / REPORT] = (json.dumps(report, indent=2) + "\n").encode()
        contents.update(section_outputs())
        for path, data in contents.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            if not path.exists() or path.read_bytes() != data:
                path.write_bytes(data)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--check", action="store_true")
    modes.add_argument("--apply", action="store_true")
    modes.add_argument("--preview", action="store_true")
    modes.add_argument("--build-dir", type=Path, help=argparse.SUPPRESS)
    modes.add_argument("--render", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else None)
    if args.build_dir:
        build(args.build_dir)
        return
    if args.render:
        render()
        return
    changes = stale()
    print(json.dumps({"stale": changes}), flush=True)
    if args.apply and changes:
        apply()
        changes = stale()
        assert not changes, changes
    if args.preview:
        assert not changes, changes
        run_blender(["--render"])
    raise SystemExit(bool(changes))


if __name__ == "__main__":
    main()
