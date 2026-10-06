"""Build three native CAS generations for STP/NOD, STS and VAL.

python -B -m tools.assets.source.build_country_cas --prepare
blender --background --factory-startup --python this_file -- --build
python -B -m tools.assets.source.build_country_cas --check
python -B -m tools.assets.source.build_country_cas --apply
The existing country-vehicle entities select early/main/future exports.
"""

import argparse
import hashlib
import json
import math
from pathlib import Path
import sys
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[3]
SOURCE = Path(__file__).with_name("country_cas")
DEST = ROOT / "gfx/models/units/ADISCORD_country_vehicles"
TAGS = ("NOD", "STP", "VAL")
PREFIXES = ("early_", "", "future_")
NAMES = tuple(f"{tag}_{prefix}cas" for tag in TAGS for prefix in PREFIXES)
TAU = math.tau


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Model:
    def __init__(self, name):
        self.name = name
        self.vertices, self.faces, self.tiles, self.weights, self.smooth = [], [], [], [], []
        self.bones = {"vehicle_root": ((0, 0, 0), None)}
        self.locators = {}

    def bone(self, name, center, parent="vehicle_root"):
        self.bones[name] = (tuple(center), parent)
        return name

    def solid(self, points, faces, tile=0, bone="vehicle_root", smooth=False):
        offset = len(self.vertices)
        self.vertices.extend(tuple(p) for p in points)
        self.weights.extend([bone] * len(points))
        self.faces.extend(tuple(offset + i for i in face) for face in faces)
        self.tiles.extend([tile] * len(faces))
        self.smooth.extend([smooth] * len(faces))

    def box(self, center, size, tile=0, bone="vehicle_root", rotation=None):
        points = [Vector((x * size[0] / 2, y * size[1] / 2, z * size[2] / 2))
                  for z in (-1, 1) for y in (-1, 1) for x in (-1, 1)]
        if rotation is not None:
            points = [rotation @ p for p in points]
        self.solid([Vector(center) + p for p in points],
                   [(0, 2, 3, 1), (4, 5, 7, 6), (0, 1, 5, 4), (2, 6, 7, 3), (0, 4, 6, 2), (1, 3, 7, 5)], tile, bone)

    def rod(self, a, b, radius, tile=3, bone="vehicle_root", end_radius=None, sides=12):
        a, b = Vector(a), Vector(b)
        axis = (b - a).normalized()
        u = axis.cross(Vector((0, 0, 1)))
        if u.length < .01:
            u = axis.cross(Vector((0, 1, 0)))
        u.normalize()
        v = axis.cross(u).normalized()
        radius2 = radius if end_radius is None else end_radius
        points = [center + (u * math.cos(TAU * i / sides) + v * math.sin(TAU * i / sides)) * r
                  for center, r in ((a, radius), (b, radius2)) for i in range(sides)]
        faces = [tuple(reversed(range(sides))), tuple(range(sides, sides * 2))]
        faces += [(i, (i + 1) % sides, (i + 1) % sides + sides, i + sides) for i in range(sides)]
        self.solid(points, faces, tile, bone)

    def plate(self, polygon, thickness, tile=0, bone="vehicle_root", axis=2):
        points = []
        for side in (-1, 1):
            for p in polygon:
                q = list(p)
                q[axis] += side * thickness / 2
                points.append(q)
        n = len(polygon)
        faces = [tuple(reversed(range(n))), tuple(range(n, n*2))]
        faces += [(i, (i+1)%n, (i+1)%n+n, i+n) for i in range(n)]
        self.solid(points, faces, tile, bone)

    def loft(self, stations, tile=0, bone="vehicle_root", x=0, sides=12):
        points = [(x + width * math.cos(i * TAU / sides), y, z + height * math.sin(i * TAU / sides))
                  for y, width, height, z in stations for i in range(sides)]
        faces = [tuple(reversed(range(sides))), tuple(range(len(points)-sides, len(points)))]
        for ring in range(len(stations)-1):
            faces.extend([(ring*sides+i, ring*sides+(i+1)%sides,
                           (ring+1)*sides+(i+1)%sides, (ring+1)*sides+i) for i in range(sides)])
        self.solid(points, faces, tile, bone, smooth=True)

    def object(self, material):
        mesh = bpy.data.meshes.new(self.name)
        mesh.from_pydata(self.vertices, [], self.faces)
        mesh.update()
        mesh.materials.append(material)
        uv = mesh.uv_layers.new(name="UVMap")
        for face, tile, smooth in zip(mesh.polygons, self.tiles, self.smooth):
            face.use_smooth = smooth
            # Project each face along its dominant normal, inside an atlas gutter.
            drop = max(range(3), key=lambda i: abs(face.normal[i]))
            axes = [i for i in range(3) if i != drop]
            points = [mesh.vertices[mesh.loops[i].vertex_index].co for i in face.loop_indices]
            low = [min(p[a] for p in points) for a in axes]
            size = [max(p[a] for p in points) - low[j] for j, a in enumerate(axes)]
            for loop, point in zip(face.loop_indices, points):
                u, v = [(point[a] - low[j]) / max(size[j], 1e-7) for j, a in enumerate(axes)]
                uv.data[loop].uv = ((tile % 4) * .25 + .008 + u * .234,
                                    1 - (tile // 4 + 1) * .25 + .008 + v * .234)
        bm = bmesh.new()
        bm.from_mesh(mesh)
        bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
        bmesh.ops.triangulate(bm, faces=list(bm.faces))
        bm.to_mesh(mesh)
        bm.free()
        obj = bpy.data.objects.new(self.name, mesh)
        bpy.context.collection.objects.link(obj)
        for name in self.bones:
            indices = [i for i, bone in enumerate(self.weights) if bone == name]
            if indices:
                obj.vertex_groups.new(name=name).add(indices, 1, "REPLACE")
        bpy.ops.object.armature_add()
        rig = bpy.context.object
        rig.name = self.name + "_rig"
        bpy.ops.object.mode_set(mode="EDIT")
        rig.data.edit_bones.remove(rig.data.edit_bones[0])
        for name, (center, parent) in self.bones.items():
            bone = rig.data.edit_bones.new(name)
            bone.head, bone.tail = center, Vector(center) + Vector((0, 1, 0))
            if parent:
                bone.parent = rig.data.edit_bones[parent]
        bpy.ops.object.mode_set(mode="OBJECT")
        obj.modifiers.new("Rigid vehicle parts", "ARMATURE").object = rig
        for name, (center, parent) in self.locators.items():
            empty = bpy.data.objects.new(name, None)
            bpy.context.collection.objects.link(empty)
            empty.parent, empty.parent_type, empty.parent_bone = rig, "BONE", parent
            bpy.context.view_layer.update()
            empty.matrix_world = Matrix.Translation(Vector(center))
        return obj, rig


def prepare():
    from PIL import Image, ImageDraw
    import random
    from tools.assets.source.build_shl_palace import dds_bytes

    SOURCE.mkdir(parents=True, exist_ok=True)
    paints = {
        "NOD": ((67, 88, 99), (34, 47, 58), (167, 196, 197)),
        "STP": ((65, 67, 68), (29, 32, 35), (172, 59, 44)),
        "VAL": ((135, 128, 96), (66, 73, 58), (214, 180, 104)),
    }
    for tag, (base, dark, accent) in paints.items():
        palette = [base, dark, (20, 24, 27), (118, 128, 135), (195, 203, 201),
                   (34, 105, 141), accent, (13, 19, 23), base,
                   tuple(min(255, c + 22) for c in base), (191, 45, 35),
                   (130, 77, 38), (58, 63, 64), (215, 219, 208), (75, 84, 65), (221, 187, 77)]
        atlas = Image.new("RGBA", (1024, 1024))
        rng = random.Random("cas_" + tag)
        for index, color in enumerate(palette):
            tile = Image.new("RGBA", (256, 256))
            pixels = []
            for y in range(256):
                for x in range(256):
                    wear = rng.gauss(0, 1.3) + 2 * math.sin(x * .04 + y * .018)
                    pixels.append(tuple(max(0, min(255, round(c + wear))) for c in color) + (255,))
            tile.putdata(pixels)
            draw = ImageDraw.Draw(tile)
            if index in (0, 1, 9):
                for a in (12, 128, 243):
                    draw.line((a, 0, a, 255), fill=tuple(round(c * .7) for c in color), width=2)
                    draw.line((0, a, 255, a), fill=tuple(round(c * .7) for c in color), width=2)
                for a in range(24, 244, 24):
                    for b in (18, 122, 237):
                        draw.ellipse((a, b, a + 2, b + 2), fill=(*dark, 255))
            if index == 5:
                for y in range(256):
                    draw.line((0, y, 255, y), fill=(24 + y // 12, 67 + y // 5, 92 + y // 4, 255))
            if index == 7:
                for y in range(0, 256, 20):
                    draw.line((0, y, 255, y), fill=(52, 60, 63), width=4)
            if index == 8:
                draw.polygon(((55, 185), (124, 65), (140, 65), (201, 185), (167, 185),
                              (130, 117), (88, 185)), fill=accent)
                draw.line((45, 211, 210, 211), fill=accent, width=9)
            atlas.paste(tile, ((index % 4) * 256, (index // 4) * 256))
        maps = {
            "diffuse": atlas,
            "normal": Image.new("RGBA", (1024, 1024), (128, 128, 0, 128)),
            "specular": Image.new("RGBA", (1024, 1024), (0, 28, 0, 34)),
        }
        ImageDraw.Draw(maps["specular"]).rectangle((256, 256, 511, 511), fill=(0, 105, 0, 125))
        for channel, image in maps.items():
            (SOURCE / f"{tag}_cas_{channel}.dds").write_bytes(dds_bytes(image))


def fin(model, x, y, z, height, chord, cant=0):
    model.plate([(x, y - chord * .55, z), (x + cant, y + chord * .12, z + height),
                 (x + cant, y + chord * .67, z + height * .85),
                 (x, y + chord * .7, z)], .10, 1, axis=0)
    model.plate([(x + cant * .8, y + chord * .22, z + height * .8),
                 (x + cant * .71, y + chord * .55, z + height * .71),
                 (x + cant * .61, y + chord * .53, z + height * .61),
                 (x + cant * .7, y + chord * .18, z + height * .7)], .12, 6, axis=0)


def wing(model, side, span, sweep, root_y, chord, tip_chord, z=0, tile=0):
    model.plate([(side * .55, root_y, z), (side * span, root_y + sweep, z + .15),
                 (side * span, root_y + sweep + tip_chord, z + .15),
                 (side * 1.5, root_y + chord, z), (side * .55, root_y + chord, z)], .17, tile)
    # A separate trailing flap keeps the wing readable at the map's small scale.
    model.plate([(side * 2.1, root_y + chord - .3, z + .11),
                 (side * (span - .45), root_y + sweep + tip_chord - .3, z + .24),
                 (side * (span - .45), root_y + sweep + tip_chord - .08, z + .24),
                 (side * 2.1, root_y + chord - .08, z + .11)], .025, 1)


def propeller(model, x, y, z):
    name = model.bone(f"prop_{'left' if x < 0 else 'right'}", (x, y, z))
    model.rod((x, y - .3, z), (x, y + .1, z), .13, 4, name, end_radius=.25)
    for index in range(4):
        angle = index * TAU / 4 + .35
        rotation = Matrix.Rotation(angle, 3, "Y")
        center = Vector((x, y, z)) + rotation @ Vector((0, 0, .72))
        model.box(center, (.18, .06, 1.22), 2, name, rotation)
        center = Vector((x, y, z)) + rotation @ Vector((0, 0, 1.26))
        model.box(center, (.19, .07, .16), 15, name, rotation)


def engine(model, x, start, end, z, tier, radius=.57):
    if tier == 0:
        model.loft([(start, radius * .82, radius * .85, z),
                    (start + .4, radius, radius, z), (end - .4, radius * .8, radius * .78, z),
                    (end, .15, .2, z)], 9, x=x)
        model.rod((x, start - .08, z), (x, start + .05, z), radius * .78, 7)
        propeller(model, x, start - .23, z)
        for side in (-1, 1):
            model.box((x + side * radius * .92, start + .9, z), (.035, .65, .3), 7)
    else:
        model.loft([(start, radius, radius * .85, z), (start + .3, radius * 1.06, radius, z),
                    (end - .55, radius * .8, radius * .78, z),
                    (end, radius * .72, radius * .7, z)], 1 if tier == 2 else 9, x=x)
        model.rod((x, start - .04, z), (x, start - .02, z), radius * .87, 7)
        model.rod((x, start - .07, z), (x, start - .04, z), radius * .22, 3)
        model.rod((x, end, z), (x, end + .22, z), radius * .7, 3, end_radius=radius * .63)
        model.rod((x, end + .23, z), (x, end + .25, z), radius * .55, 7)


def ordnance(model, side, x, y, tier):
    model.box((side * x, y + .18, -.27), (.14, .78, .55), 1)
    radius = .23 if tier == 0 else .17
    z = -.67
    model.rod((side * x, y - 1.0, z), (side * x, y + .85, z), radius, 14 if tier == 0 else 4)
    model.rod((side * x, y - 1.35, z), (side * x, y - 1.0, z), .025, 1, end_radius=radius)
    for axis in (0, 2):
        size = (.7, .4, .045) if axis == 0 else (.045, .4, .7)
        model.box((side * x, y + .6, z), size, 1)
    if tier == 2:
        model.box((side * x, y - .25, z), (.43, .35, .04), 3)


def aircraft(tag, tier):
    model = Model(f"{tag}_{PREFIXES[tier]}cas")
    width = {"NOD": 1.04, "STP": .78, "VAL": .9}[tag] * (1 + tier * .04)
    nose = -6.8 - tier * .15
    tail = 5.8 if tag != "VAL" else 3.0
    model.loft([(nose, .08, .12, -.03), (nose + .9, width * .63, .55, 0),
                (-4.6, width * .86, .7, .05), (-2.7, width, .8, .02),
                (.9, width * .95, .64, 0), (tail - .9, width * .4, .4, .06),
                (tail, .12, .16, .12)], 0, sides=12 if tier < 2 else 8)
    model.loft([(-5.1, .12, .09, .62), (-4.35, width * .55, .41, .77),
                (-2.9, width * .55, .48, .82), (-2.25, .14, .1, .69)], 5, sides=8)
    for y in (-4.25, -3.4, -2.8):
        model.rod((-width * .51, y, .93), (0, y, 1.26), .038, 1)
        model.rod((0, y, 1.26), (width * .51, y, .93), .038, 1)
    model.rod((0, -4.5, 1.12), (0, -2.7, 1.24), .045, 1)
    model.box((0, -3.0, -.58), (width * 1.36, 3.6, .28), 1)
    for side in (-1, 1):
        model.box((side * width * .87, -3.55, .17), (.14, 1.65, .45), 9)
        model.rod((side * .32, -5.4, -.37), (side * .32, -6.15, -.37), .095, 3)
        if tag == "NOD":
            span = 7.8 + tier * .25
            wing(model, side, span, .3 + tier * .28, -1.6, 3.0, 1.5)
            engine(model, side * (1.35 if tier == 2 else 2.2), -3.1 if tier == 0 else -.8,
                   1.15 if tier == 0 else 3.4, .2 if tier != 1 else .63, tier, .7)
            wing(model, side, 3.2, .65, 3.3, 1.6, .7, z=.36, tile=1)
            if tier == 0:
                if side == 1:
                    fin(model, 0, 4.8, .3, 2.3, 2.1)
            else:
                fin(model, side * (1.9 if tier == 2 else 2.65), 4.5, .5, 1.75, 1.8,
                    side * (.55 if tier == 2 else .22))
            if tier == 2:
                wing(model, side, 2.55, .45, -4.3, 1.35, .6, z=.1, tile=1)
            stations = (3.7, 5.35, 6.65) if tier < 2 else (3.9, 5.5)
            root_y = -.7
        elif tag == "STP":
            span = 6.65 + tier * .5
            wing(model, side, span, 2.0 + tier * .3, -2.0 - tier * .35, 4.6, 1.05)
            engine(model, side * (2.25 if tier == 0 else 1.15),
                   -3.1 if tier == 0 else -2.15, 1.15 if tier == 0 else 4.2,
                   -.08 if tier == 0 else -.2, tier, .5 + .03 * tier)
            wing(model, side, 2.7, 1.0, 3.2, 1.6, .5, z=.26, tile=1)
            fin(model, side * 1.4, 3.95, .35, 1.85 + .12 * tier, 2.1, side * .6)
            if tier == 2:
                wing(model, side, 2.1, .8, -4.3, 1.1, .45, z=.2, tile=1)
            stations = (3.5, 4.8) if tier < 2 else (3.4, 4.5, 5.7)
            root_y = .12
        else:
            span = 8.2 + tier * .35
            wing(model, side, span, .65 + tier * .6, -1.8, 3.4, 1.35, z=.18)
            boom_x = side * 3.0
            model.loft([(-3.4, .36, .39, .17), (-1.6, .5, .5, .17),
                        (3.2, .31, .31, .23), (6.2, .17, .18, .29)], 0, x=boom_x)
            engine(model, boom_x, -3.8 if tier == 0 else -2.8,
                   .7 if tier == 0 else 2.5, .2 if tier == 0 else .57, tier, .62)
            fin(model, boom_x, 5.3, .4, 1.8, 1.9, side * .18 * tier)
            if side == 1:
                model.plate([(-3.1, 4.7, .4), (3.1, 4.7, .4),
                             (3.1, 6.05, .4), (-3.1, 6.05, .4)], .12, 1)
            if tier == 2:
                wing(model, side, 2.0, .4, -4.3, 1.3, .65, z=.1, tile=1)
            stations = (1.8, 4.7, 6.1) if tier < 2 else (1.75, 4.8, 6.3)
            root_y = -.55
        for x in stations:
            ordnance(model, side, x, root_y + (x - 3.5) * (.27 if tag == "STP" else .10), tier)
        # Bold paint bands and insignia remain distinguishable without replacing shared fighter atlases.
        root_y, sweep, chord, tip_chord, wing_z = {
            "NOD": (-1.6, .3 + tier * .28, 3.0, 1.5, 0),
            "STP": (-2.0 - tier * .35, 2.0 + tier * .3, 4.6, 1.05, 0),
            "VAL": (-1.8, .65 + tier * .6, 3.4, 1.35, .18),
        }[tag]
        for inset, size, tile in ((1.0, (.36, .6, .014), 6), (2.05, (.62, .5, .014), 8)):
            x = span - inset
            fraction = (x - .55) / (span - .55)
            local_chord = chord * (1 - fraction) + tip_chord * fraction
            y = root_y + sweep * fraction + local_chord * .5
            z = wing_z + .15 * fraction + .09
            model.box((side * x, y, z), size, tile)
        model.box((side * span, root_y + sweep + tip_chord * .5, wing_z + .18),
                  (.16, .3, .15), 10 if side < 0 else 5)
    if tier > 0:
        model.loft([(-5.75, .17, .2, -.54), (-5.25, .27, .26, -.56),
                    (-4.85, .16, .15, -.51)], 7, sides=8)
        model.box((0, 1.5, .69), (.14, .72, .23), 6)
    if tier == 2:
        model.box((0, .4, -.67), (.9, 2.7, .12), 1)
        model.plate([(0, -.5, .73), (0, .1, 1.12), (0, .8, .73)], .06, 1, axis=0)
    model.locators = {
        "root": ((0, 0, 0), "vehicle_root"),
        "gun1": ((-.32, -6.15, -.37), "vehicle_root"),
        "gun2": ((.32, -6.15, -.37), "vehicle_root"),
        "bomb": ((0, -.5, -.85), "vehicle_root"),
    }
    return model


def preview_materials():
    for material in bpy.data.materials:
        if not material.use_nodes:
            continue
        shader = material.node_tree.nodes.get("Principled BSDF")
        if shader:
            for label, value in (("Roughness", .48), ("Metallic", .2)):
                for link in list(shader.inputs[label].links):
                    material.node_tree.links.remove(link)
                shader.inputs[label].default_value = value


def export_model(tag, tier):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    name = f"{tag}_{PREFIXES[tier]}cas"
    material = pdx.create_shader(SimpleNamespace(
        shader=["PdxMeshAdvanced"], diff=[f"{tag}_cas_diffuse.dds"],
        n=[f"{tag}_cas_normal.dds"], spec=[f"{tag}_cas_specular.dds"],
    ), name, str(SOURCE))
    model = aircraft(tag, tier)
    obj, rig = model.object(material)
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    for empty in [o for o in bpy.context.scene.objects if o.type == "EMPTY"]:
        empty.select_set(True)
    bpy.context.view_layer.objects.active = obj
    path = SOURCE / f"{name}.mesh"
    pdx.export_meshfile(str(path), exp_selected=True)
    tree = pdx_data.read_meshfile(str(path))
    for mesh in tree.findall("./object/*/mesh"):
        skin = mesh.find("skin")
        indices, weights = skin.attrib["ix"], skin.attrib["w"]
        assert all(weights[i:i + 4] == [1, 0, 0, 0] for i in range(0, len(weights), 4))
        skin.set("bones", [1])
        skin.set("ix", [indices[i - i % 4] for i in range(len(indices))])
        mesh.attrib["ta"] = [round(value, 5) for value in mesh.attrib["ta"]]
    pdx_data.write_meshfile(str(path), tree)
    scene = bpy.context.scene
    scene.render.fps = 30
    scene.frame_start, scene.frame_end = 1, 31 if tier == 0 else 2
    for frame in range(1, scene.frame_end + 1):
        for bone in rig.pose.bones:
            bone.rotation_mode = "XYZ"
            if bone.name.startswith("prop_"):
                bone.rotation_euler.y = TAU * (frame - 1) / 30
            bone.keyframe_insert("rotation_euler", frame=frame)
            bone.keyframe_insert("location", frame=frame)
    scene.frame_set(1)
    bpy.context.view_layer.objects.active = rig
    pdx.export_animfile(str(SOURCE / f"{name}_idle.anim"), frame_start=1, frame_end=scene.frame_end)
    preview_materials()
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.file.pack_all()
    bpy.ops.wm.save_as_mainfile(filepath=str(SOURCE / f"{name}.blend"))
    return verify(name)


def verify(name):
    path = SOURCE / f"{name}.mesh"
    tree = pdx_data.read_meshfile(str(path))
    report = {"triangles": 0, "materials": 0, "bones": 0}
    for shape in tree.find("object"):
        bones = list(shape.find("skeleton"))
        report["bones"] = len(bones)
        for mesh in shape.findall("mesh"):
            data = pdx_data.PDXData(mesh)
            count = len(data.p) // 3
            assert 0 < count < 65536
            assert len(data.n) == count * 3 and len(data.u0) == count * 2
            assert len(data.ta) == count * 4
            assert all(math.isfinite(x) for x in data.p + data.n + data.u0 + data.ta)
            assert all(0 <= x <= 1 for x in data.u0)
            assert len(data.tri) % 3 == 0 and min(data.tri) >= 0 and max(data.tri) < count
            points = [Vector(data.p[i:i + 3]) for i in range(0, len(data.p), 3)]
            assert all((points[b] - points[a]).cross(points[c] - points[a]).length > 1e-9
                       for a, b, c in zip(data.tri[::3], data.tri[1::3], data.tri[2::3]))
            assert data.skin.bones == [1]
            assert len(data.skin.ix) == len(data.skin.w) == count * 4
            for i in range(count):
                assert data.skin.w[i * 4:i * 4 + 4] == [1, 0, 0, 0]
                assert all(0 <= b < len(bones) for b in data.skin.ix[i * 4:i * 4 + 4])
            assert data.material.shader == ["PdxMeshAdvanced"]
            for key in ("diff", "n", "spec"):
                assert (SOURCE / getattr(data.material, key)[0]).read_bytes()[:4] == b"DDS "
            report["triangles"] += len(data.tri) // 3
            report["materials"] += 1
    report["rigid_skin_slots_validated"] = True
    report["locators"] = [loc.tag for loc in tree.find("locator")]
    assert {"root", "gun1", "gun2", "bomb"}.issubset(report["locators"])
    bpy.ops.wm.read_factory_settings(use_empty=True)
    pdx.import_meshfile(str(path), join_materials=False)
    pdx.import_animfile(str(SOURCE / f"{name}_idle.anim"))
    objects = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    samples = []
    end = bpy.context.scene.frame_end
    for frame in sorted({1, 2, max(2, end // 4), max(2, end // 2), end}):
        bpy.context.scene.frame_set(frame)
        graph = bpy.context.evaluated_depsgraph_get()
        points = [o.matrix_world @ v.co for o in objects for v in o.evaluated_get(graph).data.vertices]
        assert all(math.isfinite(c) for p in points for c in p)
        assert max(p.length for p in points) < 20
        samples.append(points)
    motion = max((a - b).length for points in samples[1:] for a, b in zip(samples[0], points))
    loop_error = max((a - b).length for a, b in zip(samples[0], samples[-1]))
    assert loop_error < .001, (name, loop_error)
    if "_early_" in name:
        assert motion > .1, (name, "propeller does not rotate")
    report["animation"] = {"samples": len(samples), "max_vertex_motion": motion, "loop_error": loop_error}
    report["native_reimport"] = True
    report["hoi4_runtime_verified"] = False
    report["dimensions"] = [max(p[i] for p in samples[0]) - min(p[i] for p in samples[0]) for i in range(3)]
    filenames = [f"{name}.mesh", f"{name}_idle.anim"]
    filenames += [f"{name[:3]}_cas_{channel}.dds" for channel in ("diffuse", "normal", "specular")]
    report["files"] = {filename: digest(SOURCE / filename) for filename in filenames}
    report["blend_sha256"] = digest(SOURCE / f"{name}.blend")
    return report


def render_preview(name):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    pdx.import_meshfile(str(SOURCE / f"{name}.mesh"), join_materials=False)
    preview_materials()
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.samples = 24
    scene.cycles.use_denoising = True
    scene.render.resolution_x, scene.render.resolution_y = 920, 730
    scene.render.resolution_percentage = 100
    scene.world = bpy.data.worlds.new("Aircraft studio")
    scene.world.use_nodes = True
    scene.world.node_tree.nodes["Background"].inputs[0].default_value = (.18, .21, .27, 1)
    scene.world.node_tree.nodes["Background"].inputs[1].default_value = .5
    scene.view_settings.view_transform = "AgX"
    target = Vector((0, -.2, 0))
    bpy.ops.object.camera_add(location=(14, -22, 23))
    camera = bpy.context.object
    camera.rotation_euler = (target - camera.location).to_track_quat("-Z", "Y").to_euler()
    camera.data.type, camera.data.ortho_scale = "ORTHO", 21.7
    scene.camera = camera
    for location, power, size in (((-8, -12, 18), 6500, 10), ((12, 2, 15), 4500, 9), ((-5, 16, 13), 7500, 8)):
        bpy.ops.object.light_add(type="AREA", location=location)
        light = bpy.context.object
        light.data.energy, light.data.size = power, size
        light.rotation_euler = (target - light.location).to_track_quat("-Z", "Y").to_euler()
    scene.render.film_transparent = True
    scene.render.filepath = str(SOURCE / f"{name}_preview.png")
    bpy.ops.render.render(write_still=True)


def package(apply=False):
    report = json.loads((SOURCE / "verification.json").read_text())
    assert set(report) == set(NAMES)
    files = {}
    for name, row in report.items():
        assert digest(SOURCE / f"{name}.blend") == row["blend_sha256"]
        for filename, expected in row["files"].items():
            assert digest(SOURCE / filename) == expected
            files[filename] = (SOURCE / filename).read_bytes()
    changed = [name for name, data in files.items()
               if not (DEST / name).is_file() or (DEST / name).read_bytes() != data]
    if apply:
        for name in changed:
            (DEST / name).write_bytes(files[name])
    return changed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    for option in ("prepare", "build", "render", "apply", "check"):
        action.add_argument("--" + option, action="store_true")
    parser.add_argument("--names", nargs="*", choices=NAMES)
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else None)
    if args.prepare:
        prepare()
    elif args.build or args.render:
        global bpy, bmesh, Matrix, Vector, pdx, pdx_data
        import bpy
        import bmesh
        from mathutils import Matrix, Vector
        sys.path.insert(0, str(Path(__file__).parent))
        from build_shl_palace import load_exporter
        pdx = load_exporter()
        from io_pdx_mesh import pdx_data
        report_path = SOURCE / "verification.json"
        report = json.loads(report_path.read_text()) if report_path.exists() else {}
        for name in args.names or NAMES:
            if args.build:
                tier = next(i for i, prefix in enumerate(PREFIXES) if name == f"{name[:3]}_{prefix}cas")
                report[name] = export_model(name[:3], tier)
                report_path.write_text(json.dumps(report, indent=2) + "\n")
                print("VERIFIED", name, report[name]["triangles"], flush=True)
            render_preview(name)
    else:
        changed = package(apply=args.apply)
        print(json.dumps({"changed": changed, "applied": args.apply}, indent=2))
        if args.check and changed:
            raise SystemExit(1)


if __name__ == "__main__":
    main()

