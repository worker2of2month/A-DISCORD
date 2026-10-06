"""Build and package the neutral airborne battleship asset.

Python: -B -m tools.assets.source.build_zeppelin --check, then --apply
Blender: --background --factory-startup --python this_file -- --build
Python: -B -m tools.assets.source.build_zeppelin --check
Python: -B -m tools.assets.source.build_zeppelin --install --check
Python: -B -m tools.assets.source.build_zeppelin --install --apply
Python: -B -m tools.assets.source.build_zeppelin --install --check
"""

import argparse
import hashlib
import io
import json
import math
from pathlib import Path
import sys
import subprocess
from types import SimpleNamespace
import wave

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_shl_palace import dds_bytes, load_exporter

NAME = "ADISCORD_zeppelin"
OUTPUT = Path(__file__).with_name("zeppelin")
ROOT = Path(__file__).resolve().parents[3]
MODEL_DIR = Path("gfx/models/units/ADISCORD_zeppelin")
STATES = ("idle", "move", "attack")
TURRETS = ("bow", "stern", "port_fore", "port_aft", "starboard_fore", "starboard_aft")
EXHAUSTS = tuple(f"exhaust_{side}_{index}" for side in ("port", "starboard") for index in range(3))
TAU = math.tau


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def textures():
    import numpy as np
    from PIL import Image, ImageDraw

    colors = [(115, 132, 137), (32, 47, 57), (163, 135, 83), (46, 55, 60),
              (188, 198, 193), (49, 113, 137), (98, 36, 31), (15, 23, 28),
              (94, 112, 122), (141, 153, 155), (168, 175, 167), (108, 88, 65),
              (71, 80, 82), (205, 194, 156), (145, 46, 28), (213, 159, 55)]
    atlas = Image.new("RGBA", (1024, 1024))
    rng = np.random.default_rng(7701)
    for index, color in enumerate(colors):
        noise = rng.normal(0, 1.5, (256, 256, 1))
        pixels = np.clip(np.array(color)[None, None, :] + noise, 0, 255).astype("uint8")
        tile = Image.fromarray(pixels).convert("RGBA")
        draw = ImageDraw.Draw(tile)
        if index in (0, 1, 3, 8, 9):
            dark = tuple(round(c * .72) for c in color)
            light = tuple(min(255, c + 12) for c in color)
            for y in (8, 128, 247):
                draw.line((0, y, 255, y), fill=dark, width=2)
                draw.line((0, y + 2, 255, y + 2), fill=light)
                for x in range(14, 250, 24):
                    draw.ellipse((x, y + 5, x + 2, y + 7), fill=light)
            for x in (8, 247):
                draw.line((x, 0, x, 255), fill=dark, width=2)
        if index == 7:
            for y in range(0, 256, 16):
                draw.line((0, y, 255, y), fill=(66, 73, 73), width=3)
        if index == 11:
            for x in range(0, 256, 28):
                draw.line((x, 0, x, 255), fill=(65, 54, 44), width=2)
        atlas.paste(tile, ((index % 4) * 256, (index // 4) * 256))
    normal = Image.new("RGBA", atlas.size, (255, 128, 0, 128))
    spec = Image.new("RGBA", atlas.size, (0, 70, 0, 80))
    return {f"{NAME}_{channel}.dds": dds_bytes(image)
            for channel, image in (("diffuse", atlas), ("normal", normal), ("specular", spec))}


class Geometry:
    def __init__(self):
        self.vertices = []
        self.faces = []
        self.tiles = []
        self.weights = []
        self.bones = {"root": ((0, 0, 0), None)}
        self.locators = {}
        self.recoil = {}

    def bone(self, name, center, parent="root"):
        self.bones[name] = (center, parent)
        return name

    def solid(self, points, faces, tile=0, bone="root"):
        offset = len(self.vertices)
        self.vertices.extend(tuple(p) for p in points)
        self.weights.extend([bone] * len(points))
        self.faces.extend(tuple(offset + i for i in face) for face in faces)
        self.tiles.extend([tile] * len(faces))

    def box(self, center, size, tile=0, bone="root"):
        points = [(center[0] + x * size[0] / 2, center[1] + y * size[1] / 2,
                   center[2] + z * size[2] / 2)
                  for z in (-1, 1) for y in (-1, 1) for x in (-1, 1)]
        self.solid(points, [(0, 2, 3, 1), (4, 5, 7, 6), (0, 1, 5, 4),
                            (2, 6, 7, 3), (0, 4, 6, 2), (1, 3, 7, 5)], tile, bone)

    def rod(self, a, b, radius, tile=3, bone="root", end_radius=None, sides=10):
        a, b = Vector(a), Vector(b)
        axis = (b - a).normalized()
        u = axis.cross(Vector((0, 0, 1)))
        if u.length < .01:
            u = axis.cross(Vector((0, 1, 0)))
        u.normalize()
        v = axis.cross(u).normalized()
        end_radius = radius if end_radius is None else end_radius
        points = [center + (u * math.cos(TAU * i / sides) + v * math.sin(TAU * i / sides)) * r
                  for center, r in ((a, radius), (b, end_radius)) for i in range(sides)]
        faces = [tuple(reversed(range(sides))), tuple(range(sides, sides * 2))]
        faces += [(i, (i + 1) % sides, (i + 1) % sides + sides, i + sides) for i in range(sides)]
        self.solid(points, faces, tile, bone)

    def plate(self, points, thickness, tile=0, bone="root", axis=2):
        verts = []
        for side in (-1, 1):
            for point in points:
                value = list(point)
                value[axis] += side * thickness / 2
                verts.append(value)
        n = len(points)
        faces = [tuple(reversed(range(n))), tuple(range(n, n * 2))]
        faces += [(i, (i + 1) % n, (i + 1) % n + n, i + n) for i in range(n)]
        self.solid(verts, faces, tile, bone)

    def loft(self, stations, tile=0, sides=32):
        points = [(width * math.cos(i * TAU / sides), y, z + height * math.sin(i * TAU / sides))
                  for y, width, height, z in stations for i in range(sides)]
        faces = [tuple(reversed(range(sides))), tuple(range(len(points) - sides, len(points)))]
        for ring in range(len(stations) - 1):
            faces.extend((ring * sides + i, ring * sides + (i + 1) % sides,
                          (ring + 1) * sides + (i + 1) % sides, (ring + 1) * sides + i)
                         for i in range(sides))
        self.solid(points, faces, tile)

    def ring(self, y, width, height, z, tile=2):
        points = [(width * math.cos(i * TAU / 32), y, z + height * math.sin(i * TAU / 32))
                  for i in range(32)]
        for a, b in zip(points, points[1:] + points[:1]):
            self.rod(a, b, .055, tile, sides=6)

    def turret(self, name, x, y, z, direction):
        turret = self.bone(name, (x, y, z))
        guns = self.bone(name + "_recoil", (x, y, z + .55), turret)
        self.recoil[guns] = -direction
        self.rod((x, y, z - .35), (x, y, z + .16), 1.12, 2, sides=16)
        self.box((x, y, z + .55), (2.45, 2.6, 1.1), 8, turret)
        self.box((x, y - direction * .18, z + 1.12), (2.1, 1.9, .12), 9, turret)
        for index, dx in enumerate((-.65, 0, .65)):
            start = (x + dx, y + direction * .9, z + .63)
            end = (x + dx, y + direction * 4.9, z + .85)
            self.rod(start, end, .15, 3, guns, .10)
            self.rod(start, (x + dx, y + direction * 2, z + .69), .23, 1, guns)
            self.rod(end, (end[0], end[1] + direction * .02, end[2]), .076, 7, guns)
            self.locators[f"{name}_muzzle_{index + 1}"] = (end, guns, math.pi if direction > 0 else 0)

    def object(self, material):
        mesh = bpy.data.meshes.new(NAME)
        mesh.from_pydata(self.vertices, [], self.faces)
        mesh.update()
        mesh.materials.append(material)
        uv = mesh.uv_layers.new(name="UVMap")
        for face, tile in zip(mesh.polygons, self.tiles):
            drop = max(range(3), key=lambda i: abs(face.normal[i]))
            axes = [i for i in range(3) if i != drop]
            points = [mesh.vertices[mesh.loops[i].vertex_index].co for i in face.loop_indices]
            low = [min(p[a] for p in points) for a in axes]
            size = [max(p[a] for p in points) - low[j] for j, a in enumerate(axes)]
            for loop, point in zip(face.loop_indices, points):
                u, v = [(point[a] - low[j]) / max(size[j], 1e-7) for j, a in enumerate(axes)]
                uv.data[loop].uv = ((tile % 4) * .25 + .009 + u * .232,
                                    (3 - tile // 4) * .25 + .009 + v * .232)
        bm = bmesh.new()
        bm.from_mesh(mesh)
        bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
        bmesh.ops.triangulate(bm, faces=list(bm.faces))
        bm.to_mesh(mesh)
        bm.free()
        obj = bpy.data.objects.new(NAME, mesh)
        bpy.context.collection.objects.link(obj)
        for name in self.bones:
            indices = [i for i, bone in enumerate(self.weights) if bone == name]
            if indices:
                obj.vertex_groups.new(name=name).add(indices, 1, "REPLACE")
        bpy.ops.object.armature_add()
        rig = bpy.context.object
        rig.name = NAME + "_rig"
        bpy.ops.object.mode_set(mode="EDIT")
        rig.data.edit_bones.remove(rig.data.edit_bones[0])
        for name, (center, parent) in self.bones.items():
            bone = rig.data.edit_bones.new(name)
            bone.head = center
            bone.tail = Vector(center) + Vector((0, 1, 0))
            if parent:
                bone.parent = rig.data.edit_bones[parent]
        bpy.ops.object.mode_set(mode="OBJECT")
        obj.modifiers.new("Rigid animated parts", "ARMATURE").object = rig
        for name, (center, parent, yaw) in self.locators.items():
            empty = bpy.data.objects.new(name, None)
            bpy.context.collection.objects.link(empty)
            empty.parent = rig
            empty.parent_type = "BONE"
            empty.parent_bone = parent
            bpy.context.view_layer.update()
            empty.matrix_world = Matrix.Translation(Vector(center)) @ Matrix.Rotation(yaw, 4, "Z")
        return obj, rig


def geometry():
    g = Geometry()
    stations = [(-23, .22, .25, 12), (-21, 2.6, 2.7, 12), (-18, 4.6, 4.5, 12),
                (-14, 5.8, 5.5, 12), (-8, 6.6, 6, 12), (0, 6.9, 6.1, 12),
                (8, 6.4, 5.8, 12), (14, 5.3, 5, 12), (19, 3.5, 3.5, 12),
                (23, 1.4, 1.6, 12), (25, .16, .2, 12)]
    g.loft(stations)
    for y, width, height, z in stations[1:-1]:
        g.ring(y, width + .035, height + .035, z)
    for angle in range(0, 32, 4):
        points = [(w * math.cos(angle * TAU / 32), y, z + h * math.sin(angle * TAU / 32))
                  for y, w, h, z in stations]
        for a, b in zip(points, points[1:]):
            g.rod(a, b, .065, 9, sides=6)
    g.loft([(-20, .25, .2, 4.5), (-17, 2.1, .8, 4.1), (-12, 3.2, 1.3, 4),
            (10, 3.2, 1.3, 4), (16, 1.7, .8, 4.4), (19, .2, .2, 4.7)], 1, sides=12)
    g.plate([(-.1, -20, 5.1), (2.5, -16, 5.1), (3.4, -10, 5.1), (3.4, 10, 5.1),
             (1.6, 17, 5.1), (0, 19, 5.1), (-1.6, 17, 5.1), (-3.4, 10, 5.1),
             (-3.4, -10, 5.1), (-2.5, -16, 5.1)], .35, 11)
    for y in (-12, -6, 0, 6, 12):
        for sign in (-1, 1):
            g.rod((sign * 2.7, y, 4.9), (sign * 4.8, y, 8.3), .13, 2)
            g.rod((sign * 2.7, y - 1.5, 4.9), (sign * 4.8, y + 1.5, 8.3), .085, 3)
    g.turret("bow", 0, -16.4, 5.6, -1)
    g.turret("stern", 0, 15.0, 5.8, -1)
    for sign, side in ((-1, "port"), (1, "starboard")):
        for y, position in ((-7, "fore"), (7, "aft")):
            x = sign * 6.1
            g.plate([(sign * 2.5, y - 2.1, 5.6), (sign * 7.7, y - 2.1, 5.6),
                     (sign * 7.7, y + 2.1, 5.6), (sign * 2.5, y + 2.1, 5.6)], .45, 1)
            g.rod((sign * 3, y, 3.8), (x, y, 5.5), .22, 2)
            g.turret(f"{side}_{position}", x, y, 6.0, -1)
        for y in range(-11, 12, 2):
            g.box((sign * 3.16, y, 4.3), (.09, .7, .24), 5)
        for index, y in enumerate((-12, 0, 12)):
            x, z = sign * 8.7, 10.5
            g.rod((sign * 4.4, y + .7, 10), (x, y + .7, z), .27, 1)
            g.rod((sign * 4.0, y + 2, 7.5), (x, y + .9, z), .15, 2)
            g.rod((x, y - 1, z), (x, y + 1.7, z), .72, 1, end_radius=.5, sides=16)
            g.rod((x, y - 1.05, z), (x, y - .8, z), .78, 2, sides=16)
            g.locators[f"exhaust_{side}_{index}"] = ((x, y + 1.8, z + .25), "root", math.pi)
            prop = g.bone(f"prop_{side}_{index}", (x, y - 1.4, z))
            g.rod((x, y - 1.6, z), (x, y - 1, z), .27, 4, prop)
            for blade in range(4):
                angle = blade * TAU / 4 + .3
                coords = []
                for radius, offset in ((.25, -.13), (2.25, -.16), (2.55, .08), (.65, .27)):
                    coords.append((x + math.cos(angle) * radius - math.sin(angle) * offset,
                                   y - 1.4, z + math.sin(angle) * radius + math.cos(angle) * offset))
                g.plate(coords, .09, 3, prop, axis=1)
        g.plate([(0, 16, 12), (sign * 9, 22, 12), (sign * 9, 25, 12), (0, 24, 12)], .22, 1)
        g.plate([(sign * 7.4, 22, 12.14), (sign * 8.4, 22.7, 12.14),
                 (sign * 8.4, 24.7, 12.14), (sign * 7.4, 24.6, 12.14)], .04, 6)
    g.plate([(0, 15, 13), (0, 21, 21), (0, 25, 21), (0, 24, 12)], .3, 1, axis=0)
    g.plate([(.17, 21, 17), (.17, 22.5, 19.5), (.17, 24.6, 19.5), (.17, 24, 17)], .04, 6, axis=0)
    g.box((0, -11, 6.2), (2.5, 3.7, 1.6), 8)
    g.box((0, -11.7, 7.25), (3.0, 2.6, .6), 1)
    g.box((0, -13.02, 7.25), (2.6, .04, .32), 5)
    for x in (-1.51, 1.51):
        g.box((x, -11.7, 7.25), (.04, 2.15, .32), 5)
    for y in (-6, 0, 6):
        g.box((0, y, 18.1), (1.2, 2.4, .3), 3)
    g.rod((0, 0, 18.1), (0, 0, 20.3), .09, 3)
    g.rod((-2, 0, 19.7), (2, 0, 19.7), .06, 3)
    g.locators["root_locator"] = ((0, 0, 0), "root", 0)
    return g


def animate(g, rig, pdx):
    scene = bpy.context.scene
    scene.render.fps = 30
    scene.frame_start = 1
    scene.frame_end = 61
    for state in STATES:
        rig.animation_data_clear()
        for frame in range(1, 62):
            t = (frame - 1) / 60
            for bone in rig.pose.bones:
                bone.rotation_mode = "XYZ"
                bone.location = (0, 0, 0)
                bone.rotation_euler = (0, 0, 0)
                if bone.name == "root":
                    bone.location.z = .16 * math.sin(TAU * t)
                    bone.rotation_euler.x = .012 * math.sin(TAU * t)
                    if state == "move":
                        bone.rotation_euler.x -= .018
                elif bone.name.startswith("prop_"):
                    bone.rotation_euler.y = TAU * t * (4 if state == "move" else 2)
                elif state == "attack" and bone.name in g.recoil:
                    pulse = max(0, 1 - abs(t - .35) / .10)
                    bone.location.y = g.recoil[bone.name] * .38 * pulse
                bone.keyframe_insert("location", frame=frame)
                bone.keyframe_insert("rotation_euler", frame=frame)
        rig.animation_data.action.name = NAME + "_" + state
        rig.animation_data.action.use_fake_user = True
        scene.frame_set(1)
        bpy.context.view_layer.objects.active = rig
        pdx.export_animfile(str(OUTPUT / f"{NAME}_{state}.anim"), frame_start=1, frame_end=61)
    rig.animation_data.action = bpy.data.actions[NAME + "_idle"]
    scene.frame_set(1)


def studio():
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.samples = 32
    scene.cycles.use_denoising = True
    scene.render.resolution_x = 1600
    scene.render.resolution_y = 1050
    scene.render.resolution_percentage = 100
    scene.world = bpy.data.worlds.new("Zeppelin studio")
    scene.world.use_nodes = True
    scene.world.node_tree.nodes["Background"].inputs[0].default_value = (.12, .17, .23, 1)
    scene.world.node_tree.nodes["Background"].inputs[1].default_value = .55
    scene.view_settings.view_transform = "AgX"
    target = Vector((0, 1, 10))
    bpy.ops.object.camera_add(location=(48, -65, 35))
    camera = bpy.context.object
    camera.rotation_euler = (target - camera.location).to_track_quat("-Z", "Y").to_euler()
    camera.data.type = "ORTHO"
    camera.data.ortho_scale = 60
    scene.camera = camera
    for location, power, size, color in (((-18, -30, 45), 42000, 25, (1, .87, .70)),
                                         ((30, -10, 25), 33000, 22, (.68, .84, 1)),
                                         ((5, 35, 40), 55000, 18, (1, .85, .63))):
        bpy.ops.object.light_add(type="AREA", location=location)
        light = bpy.context.object
        light.data.energy = power
        light.data.size = size
        light.data.color = color
        light.rotation_euler = (target - light.location).to_track_quat("-Z", "Y").to_euler()
    for material in bpy.data.materials:
        shader = material.node_tree.nodes.get("Principled BSDF") if material.use_nodes else None
        if shader:
            for label, value in (("Roughness", .52), ("Metallic", .38)):
                for link in list(shader.inputs[label].links):
                    material.node_tree.links.remove(link)
                shader.inputs[label].default_value = value
    return camera


def verify(pdx):
    from io_pdx_mesh import pdx_data

    report = {"triangles": 0, "vertices": 0, "animations": {}, "artifact_scope": "source_asset",
              "hoi4_runtime_verified": False}
    tree = pdx_data.read_meshfile(str(OUTPUT / f"{NAME}.mesh"))
    report["locators"] = {node.tag: node.attrib for node in tree.find("locator")}
    expected_locators = {f"{turret}_muzzle_{barrel}" for turret in TURRETS for barrel in (1, 2, 3)}
    assert set(report["locators"]) == expected_locators | set(EXHAUSTS) | {"root_locator"}
    for name, locator in report["locators"].items():
        assert len(locator["p"]) == 3 and len(locator["q"]) == 4, name
        assert all(math.isfinite(v) for v in locator["p"] + locator["q"]), name
    for shape in tree.find("object"):
        bones = list(shape.find("skeleton"))
        report["bones"] = len(bones)
        for element in shape.findall("mesh"):
            data = pdx_data.PDXData(element)
            count = len(data.p) // 3
            assert 0 < count < 65536
            assert len(data.n) == count * 3 and len(data.ta) == count * 4
            assert len(data.u0) == count * 2
            assert all(math.isfinite(v) for v in data.p + data.n + data.ta + data.u0)
            assert all(0 <= v <= 1 for v in data.u0)
            assert len(data.tri) % 3 == 0 and min(data.tri) >= 0 and max(data.tri) < count
            points = [Vector(data.p[i:i + 3]) for i in range(0, len(data.p), 3)]
            assert all((points[b] - points[a]).cross(points[c] - points[a]).length > 1e-9
                       for a, b, c in zip(data.tri[::3], data.tri[1::3], data.tri[2::3]))
            assert data.skin.bones == [1]
            assert len(data.skin.ix) == len(data.skin.w) == count * 4
            for i in range(count):
                assert data.skin.w[i * 4:i * 4 + 4] == [1, 0, 0, 0]
                assert all(0 <= b < len(bones) for b in data.skin.ix[i * 4:i * 4 + 4])
            report["vertices"] += count
            report["triangles"] += len(data.tri) // 3
    assert report["triangles"] < 30000
    for state in STATES:
        bpy.ops.wm.read_factory_settings(use_empty=True)
        pdx.import_meshfile(str(OUTPUT / f"{NAME}.mesh"))
        pdx.import_animfile(str(OUTPUT / f"{NAME}_{state}.anim"))
        rig = next(o for o in bpy.context.scene.objects if o.type == "ARMATURE")
        bpy.context.scene.frame_set(1)
        recoil_start = rig.pose.bones["bow_recoil"].location.copy()
        prop_start = rig.pose.bones["prop_port_0"].matrix_basis.to_quaternion()
        bpy.context.scene.frame_set(22)
        recoil_travel = (rig.pose.bones["bow_recoil"].location - recoil_start).length
        assert recoil_travel > .3 if state == "attack" else recoil_travel < .001
        bpy.context.scene.frame_set(5)
        prop_end = rig.pose.bones["prop_port_0"].matrix_basis.to_quaternion()
        assert prop_start.rotation_difference(prop_end).angle > .2
        meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
        samples = []
        for frame in (1, 5, 16, 22, 31, 61):
            bpy.context.scene.frame_set(frame)
            graph = bpy.context.evaluated_depsgraph_get()
            points = [o.matrix_world @ v.co for o in meshes for v in o.evaluated_get(graph).data.vertices]
            assert all(math.isfinite(c) for p in points for c in p)
            assert max(p.length for p in points) < 40
            samples.append(points)
        loop = max((a - b).length for a, b in zip(samples[0], samples[-1]))
        motion = max((a - b).length for sample in samples[1:] for a, b in zip(samples[0], sample))
        assert loop < .002 and motion > .2, (state, loop, motion)
        report["animations"][state] = {"loop_error": loop, "max_vertex_motion": motion,
                                        "recoil_travel": recoil_travel, "propeller_rotation": True}
    report["native_reimport"] = True
    report["source_sha256"] = digest(Path(__file__))
    files = [f"{NAME}.mesh", f"{NAME}.blend"]
    files += [f"{NAME}_{state}.anim" for state in STATES]
    files += [f"{NAME}_{channel}.dds" for channel in ("diffuse", "normal", "specular")]
    report["files"] = {filename: digest(OUTPUT / filename) for filename in files}
    (OUTPUT / "verification.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    bpy.context.scene.frame_set(1)
    camera = studio()
    for view, location, scale in (("preview", (48, -65, 35), 60), ("side", (65, -12, 23), 59)):
        camera.location = location
        camera.rotation_euler = (Vector((0, 1, 10)) - camera.location).to_track_quat("-Z", "Y").to_euler()
        camera.data.ortho_scale = scale
        bpy.context.scene.render.filepath = str(OUTPUT / f"{NAME}_{view}.png")
        bpy.ops.render.render(write_still=True)
    print(json.dumps(report, indent=2))


def build():
    global bpy, bmesh, Vector, Matrix
    import bpy
    import bmesh
    from mathutils import Vector, Matrix
    bpy.ops.wm.read_factory_settings(use_empty=True)
    pdx = load_exporter()
    from io_pdx_mesh import pdx_data
    material = pdx.create_shader(SimpleNamespace(
        shader=["PdxMeshAdvanced"], diff=[f"{NAME}_diffuse.dds"],
        n=[f"{NAME}_normal.dds"], spec=[f"{NAME}_specular.dds"]), NAME, str(OUTPUT))
    g = geometry()
    obj, rig = g.object(material)
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    for empty in [o for o in bpy.context.scene.objects if o.type == "EMPTY"]:
        empty.select_set(True)
    bpy.context.view_layer.objects.active = obj
    path = OUTPUT / f"{NAME}.mesh"
    pdx.export_meshfile(str(path), exp_selected=True)
    tree = pdx_data.read_meshfile(str(path))
    for mesh in tree.findall("./object/*/mesh"):
        skin = mesh.find("skin")
        indices = skin.attrib["ix"]
        skin.set("bones", [1])
        # The native shader reads every index slot, including zero-weight slots.
        skin.set("ix", [indices[i - i % 4] for i in range(len(indices))])
        mesh.attrib["ta"] = [round(value, 5) for value in mesh.attrib["ta"]]
    pdx_data.write_meshfile(str(path), tree)
    animate(g, rig, pdx)
    studio()
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type == "VIEW_3D":
                area.spaces.active.shading.type = "MATERIAL"
                area.spaces.active.region_3d.view_location = (0, 0, 10)
                area.spaces.active.region_3d.view_distance = 64
                area.spaces.active.region_3d.view_rotation = Vector((48, -65, 25)).to_track_quat("Z", "Y")
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.file.pack_all()
    bpy.ops.wm.save_as_mainfile(filepath=str(OUTPUT / f"{NAME}.blend"))
    verify(pdx)


def icon_bytes(size, white=False):
    from PIL import Image, ImageDraw

    width, height = size
    mask = Image.new("L", (304, 168))
    draw = ImageDraw.Draw(mask)
    draw.ellipse((20, 36, 274, 110), fill=255)
    draw.polygon(((226, 42), (277, 10), (277, 66)), fill=255)
    draw.polygon(((225, 98), (280, 120), (270, 85)), fill=255)
    draw.rectangle((79, 104, 224, 117), fill=255)
    draw.rectangle((78, 123, 218, 136), fill=255)
    draw.rectangle((100, 112, 110, 128), fill=255)
    draw.rectangle((191, 112, 201, 128), fill=255)
    draw.line((45, 126, 95, 126), fill=255, width=8)
    draw.line((206, 126, 251, 126), fill=255, width=8)
    mask = mask.resize((width, height), Image.Resampling.LANCZOS)
    atlas = Image.new("RGBA", (width * 2, height))
    for frame, color in enumerate(((240, 240, 230), (255, 216, 112)) if white else
                                  ((24, 30, 33), (246, 235, 196))):
        icon = Image.new("RGBA", (width, height), color)
        icon.putalpha(mask)
        atlas.paste(icon, (frame * width, 0))
    return dds_bytes(atlas)


def decode_audio(filename, expected_hash):
    import numpy as np

    path = OUTPUT / "audio" / filename
    assert digest(path) == expected_hash, f"Audio source changed: {filename}"
    decoded = subprocess.check_output([
        "ffmpeg", "-v", "error", "-i", str(path), "-f", "f32le",
        "-ac", "1", "-ar", "44100", "-",
    ])
    return np.frombuffer(decoded, dtype="<f4").astype(float)


def wav_bytes(samples):
    import numpy as np

    samples = samples * (.84 / np.max(np.abs(samples)))
    pcm = np.rint(samples * 32767).astype("<i2")
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(44100)
        output.writeframes(pcm.tobytes())
    return buffer.getvalue()


def propeller_loop(source, speed):
    import numpy as np
    from scipy.signal import resample

    samples = resample(source, round(len(source) / speed))
    frequencies = np.fft.rfftfreq(len(samples), 1 / 44100)
    # A gentle low shelf adds mass while retaining the recorded blade rhythm.
    shelf = 1 + .35 / (1 + (frequencies / 160) ** 2)
    samples = np.fft.irfft(np.fft.rfft(samples) * shelf, n=len(samples))
    samples -= np.mean(samples)
    overlap = round(.12 * 44100)
    fade = np.linspace(0, 1, overlap)
    seam = samples[-overlap:] * (1 - fade) + samples[:overlap] * fade
    return np.concatenate((samples[overlap:-overlap], seam))


def audio_files(header):
    import numpy as np

    source = decode_audio("airplane_prop.flac", "9e44850a2dfdd984bc9476c207ff0a37457cb50d28bec5d2d4d69539cf2aeafd")
    cannon = decode_audio("cannon_shot_preview.mp3", "4710f7fe566f3367f5630544daceb18a1216dd9c359ccb87fe940bd0c97ee858")
    hover = propeller_loop(source, .76)
    moving = propeller_loop(source, .84)
    duration = round(1.6 * 44100)
    progress = np.linspace(0, 1, duration)
    speed = .72 + .28 * (3 * progress ** 2 - 2 * progress ** 3)
    phase = np.cumsum(speed) % len(moving)
    startup = np.interp(phase, np.arange(len(moving)), moving)
    startup *= .45 + .55 * progress
    startup[:2205] *= np.linspace(0, 1, 2205)
    startup[-8820:] *= np.linspace(1, 0, 8820)
    # The source contains two shots; retain one report and its decay.
    salvo = cannon[:round(3.8 * 44100)].copy()
    salvo[:88] *= np.linspace(0, 1, 88)
    salvo[-13230:] *= np.linspace(1, 0, 13230)
    samples = {"engine_hover": hover, "engine_move": moving,
               "engine_start": startup, "salvo": salvo}
    definitions = [header.rstrip(), 'category = {', '\tname = "Battle"', '\tsoundeffects = {']
    definitions.extend(f'\t\t{NAME}_{key}' for key in samples)
    definitions.extend(['\t}', '}', ''])
    files = {}
    volumes = {"engine_hover": .45, "engine_move": .65, "engine_start": .35, "salvo": .85}
    for key, sample in samples.items():
        effect = f"{NAME}_{key}"
        looping = key in ("engine_hover", "engine_move")
        relative = f"zeppelin/{effect}.wav"
        files[Path("sound") / relative] = wav_bytes(sample)
        definitions.extend([
            'soundeffect = {', f'\tname = "{effect}"', '\tfalloff = "falloff_100"',
            '\tsounds = {', f'\t\tsound = "{effect}_sample"', '\t}',
            f'\tvolume = {volumes[key]:.2f}', '\tmax_audible = 4',
            '\tmax_audible_behaviour = fail', '\tis3d = yes',
            f'\tloop = {"yes" if looping else "no"}',
        ])
        if looping:
            definitions.extend(['\trandom_sound_when_looping = no', '\tfade_in = 0.18', '\tfade_out = 0.25'])
        definitions.extend([
            '}', '', 'sound = {', f'\tname = "{effect}_sample"',
            f'\tfile = "{relative}"', '\tvolume = 1.0', '}', '',
        ])
    files[Path("sound/adiscord_zeppelin.asset")] = "\n".join(definitions).encode("utf-8")
    return files


def sound_event(effect, time=0, once=True):
    lines = ['\t\tevent = {', f'\t\t\ttime = {time:g}']
    if once:
        lines.append('\t\t\ttrigger_once = yes')
    lines.extend(['\t\t\tsound = {', f'\t\t\t\tsoundeffect = "{NAME}_{effect}"',
                  '\t\t\t}', '\t\t}'])
    return lines


def particle_event(effect, node, time=0, continuous=False):
    lines = ['\t\tevent = {', f'\t\t\ttime = {time:g}', f'\t\t\tnode = "{node}"',
             f'\t\t\tparticle = "{NAME}_{effect}_particle"',
             f'\t\t\tkeep_particle = {"no" if continuous else "yes"}']
    if continuous:
        lines.append('\t\t\ttrigger_once = yes')
    return lines + ['\t\t}']


def particle_definitions(header):
    lines = [header.rstrip()]
    settings = (
        ("flash", "glow.dds", "ParticleAdditive", (255, 185, 90), 180, .06, .12, 50, 4, 1.8, 1.5),
        ("smoke", "cloud_2.dds", "ParticleAlphaBlend", (170, 165, 155), 45, .16, 1.2, 45, 12, 3.2, 4),
        ("exhaust", "cloud_2.dds", "ParticleAlphaBlend", (100, 105, 110), 24, -1, .9, 8, 12, 1.4, 1.5),
    )
    for key, texture, shader, rgb, alpha, duration, life, emission, cap, size, velocity in settings:
        lines.extend([
            'particle = {', f'\tname = "{NAME}_{key}_file"', '\tsubsystem = {',
            f'\t\tname = "{key}"', f'\t\tmax_amount = {cap}', '\t\tslave_particles = 0',
            '\t\tsort = "depth"', '\t\temitter_type = "point"', '\t\tinvert = no',
            '\t\ttrail = no', f'\t\tlocal_space = {"yes" if key == "flash" else "no"}',
            '\t\tbillboard = yes', '\t\ttexture = {', f'\t\t\tfile = "gfx/particles/{texture}"',
            '\t\t\tx = 1', '\t\t\ty = 1', f'\t\t\tshader = "{shader}"', '\t\t}',
            '\t\tcolor = {', f'\t\t\tx = {rgb[0]}', f'\t\t\ty = {rgb[1]}',
            f'\t\t\tz = {rgb[2]}', f'\t\t\talpha = {alpha},fade', '\t\t}',
            '\t\tposition = {', '\t\t\tx = 0', '\t\t\ty = 0', '\t\t\tz = 0', '\t\t}',
            '\t\tstart = 0', f'\t\tduration = {duration:g}',
            '\t\temitter_yaw = { 0 0 }', '\t\temitter_pitch = { 0 0 }',
            '\t\tvelocity_pitch = { 0 8 }', '\t\tvelocity_yaw = { 0 8 }',
            f'\t\tvelocity = {{ {velocity:g} 0.2 }}', f'\t\tlife = {{ {life:g} 0.05 }}',
            f'\t\temission = {emission:g}', f'\t\tsize = {{ {size:g},grow 0.2 }}',
            '\t\trotation = { 0 180 }', '\t}',
        ])
        for name, curve in (("fade", "0 0 0.08 1 0.4 0.8 1 0"), ("grow", "0 0.35 1 1")):
            lines.extend([
                '\tanimation = {', f'\t\tname = "{name}"', '\t\tstart = 0',
                '\t\tduration = 1', '\t\trepeat = no', '\t\tminValue = 0', '\t\tmaxValue = 1',
                f'\t\tcurve = {{ {curve} }}', '\t\top = "MUL"', '\t\ttime = "life"', '\t}',
            ])
        lines.extend(['}', ''])
    return "\n".join(lines).encode("utf-8")


def package_files():
    report = json.loads((OUTPUT / "verification.json").read_text(encoding="utf-8"))
    assert report["source_sha256"] == digest(Path(__file__)), "Rebuild after source edits"
    files = {}
    for filename, expected in report["files"].items():
        assert digest(OUTPUT / filename) == expected, filename
        if not filename.endswith(".blend"):
            files[MODEL_DIR / filename] = (OUTPUT / filename).read_bytes()
    header = "# Generated by tools/assets/source/build_zeppelin.py\n"
    animations = []
    mesh = [header.rstrip(), "objectTypes = {", "\tpdxmesh = {",
            f'\t\tname = "{NAME}_mesh"', f'\t\tfile = "{MODEL_DIR.as_posix()}/{NAME}.mesh"',
            "\t\tscale = 1.0"]
    for state in STATES:
        animation = f"{NAME}_{state}_animation"
        mesh.extend(["\t\tanimation = {", f'\t\t\tid = "{state}"',
                     f'\t\t\ttype = "{animation}"', "\t\t}"])
        animations.extend(["animation = {", f'\tname = "{animation}"',
                           f'\tfile = "{NAME}_{state}.anim"', "}", ""])
    mesh.extend(["\t}", ""])
    for effect in ("flash", "smoke", "exhaust"):
        mesh.extend(['\tpdxparticle = {', f'\t\tname = "{NAME}_{effect}_particle"',
                     f'\t\ttype = "{NAME}_{effect}_file"', '\t\tscale = 1', '\t}', ''])
    mesh.extend(["}", ""])
    files[Path(f"gfx/entities/{NAME}.gfx")] = "\n".join(mesh).encode("utf-8")
    files[MODEL_DIR / "animation.asset"] = (header + "\n".join(animations)).encode("utf-8")
    entity = [header.rstrip(), "entity = {", f'\tname = "{NAME}_entity"',
              f'\tpdxmesh = "{NAME}_mesh"', '\tdefault_state = "idle"', "\tscale = 0.24"]
    state_clips = {"idle": "idle", "move": "move", "retreat": "move", "training": "idle",
                   "attack": "attack", "support_attack": "attack", "defend": "attack", "death": "idle"}
    for state, clip in state_clips.items():
        entity.extend(["\tstate = {", f'\t\tname = "{state}"', f'\t\tanimation = "{clip}"',
                       "\t\tanimation_blend_time = 0.3", "\t\tanimation_speed = 1.0"])
        if state in ("move", "retreat"):
            # A state change stops hover audio, so the moving bed must start immediately.
            entity.extend(sound_event("engine_move"))
            entity.extend(sound_event("engine_start"))
        elif state != "death":
            entity.extend(sound_event("engine_hover"))
        if clip == "attack":
            entity.extend(sound_event("salvo", time=.5, once=False))
            for turret in TURRETS:
                for barrel in (1, 2, 3):
                    entity.extend(particle_event("flash", f"{turret}_muzzle_{barrel}", time=.5))
                entity.extend(particle_event("smoke", f"{turret}_muzzle_2", time=.5))
        if state != "death":
            for node in EXHAUSTS:
                entity.extend(particle_event("exhaust", node, continuous=True))
        entity.append("\t}")
    entity.extend(["}", ""])
    for alias in (f"{NAME}_0_entity", f"VAL_{NAME}_entity", f"VAL_{NAME}_0_entity"):
        entity.extend(["entity = {", f'\tname = "{alias}"', f'\tclone = "{NAME}_entity"', "}", ""])
    files[Path(f"gfx/entities/{NAME}.asset")] = "\n".join(entity).encode("utf-8")
    sprites = [header.rstrip(), "spriteTypes = {"]
    for suffix, folder, size, white in (
        ("medium", "gfx/interface/counters/divisions_large", (76, 42), False),
        ("medium_white", "gfx/interface/counters/divisions_small", (30, 12), True),
        ("small", "gfx/texticons", (30, 12), True),
    ):
        path = Path(folder) / f"{NAME}_icon.dds"
        files[path] = icon_bytes(size, white)
        sprites.extend(["\tspriteType = {", f'\t\tname = "GFX_unit_{NAME}_icon_{suffix}"',
                        f'\t\ttexturefile = "{path.as_posix()}"', "\t\tnoOfFrames = 2", "\t}", ""])
    for key in (f"{NAME}_equipment", f"{NAME}_equipment_1"):
        sprites.extend(["\tspriteType = {", f'\t\tname = "GFX_{key}_medium"',
                        f'\t\ttexturefile = "gfx/interface/counters/divisions_large/{NAME}_icon.dds"',
                        "\t\tnoOfFrames = 2", "\t}", ""])
    sprites.extend(["}", ""])
    files[Path(f"interface/{NAME}.gfx")] = "\n".join(sprites).encode("utf-8")
    files.update(audio_files(header))
    files[Path("gfx/particles/ADISCORD_zeppelin.asset")] = particle_definitions(header)
    return files


def install(apply):
    changed = []
    for relative, expected in package_files().items():
        path = ROOT / relative
        if not path.exists() or path.read_bytes() != expected:
            changed.append(relative.as_posix())
            if apply:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(expected)
    print(json.dumps({"package_changes": changed, "applied": apply}, indent=2))
    if changed and not apply:
        raise SystemExit(1)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--install", action="store_true")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--apply", action="store_true")
    mode.add_argument("--build", action="store_true")
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    args = parser.parse_args(argv)
    if args.install:
        if args.build:
            parser.error("--install requires --check or --apply")
        install(args.apply)
        return
    if args.build:
        build()
        return
    changed = []
    for filename, expected in textures().items():
        path = OUTPUT / filename
        if not path.exists() or path.read_bytes() != expected:
            changed.append(filename)
            if args.apply:
                OUTPUT.mkdir(parents=True, exist_ok=True)
                path.write_bytes(expected)
    print(json.dumps({"texture_changes": changed, "applied": args.apply}))
    if args.check and changed:
        raise SystemExit(1)
    report_path = OUTPUT / "verification.json"
    if args.check and report_path.exists():
        report = json.loads(report_path.read_text(encoding="utf-8"))
        assert report["source_sha256"] == digest(Path(__file__)), "Rebuild after source edits"
        for filename, expected in report["files"].items():
            assert digest(OUTPUT / filename) == expected, filename
        print("Native source asset hashes verified")


if __name__ == "__main__":
    main()
