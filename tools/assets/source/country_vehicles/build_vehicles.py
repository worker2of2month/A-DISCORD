"""Author, export and reimport the country tanks and aircraft in background Blender."""
import argparse
import hashlib
import json
import math
import sys
from pathlib import Path
from types import SimpleNamespace

import bpy
import bmesh
from mathutils import Matrix, Vector

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT.parent / "STP_regulars"))
from export_verify import pdx, pdx_data, preview_gloss
from package_vehicles import NAMES, TAGS

TAU = math.tau


class Model:
    def __init__(self, name):
        self.name = name
        self.vertices, self.faces, self.tiles, self.weights, self.smooth = [], [], [], [], []
        self.bones = {"vehicle_root": ((0, 0, 0), None)}
        self.locators = {}
        self.links, self.wheels = {}, []

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

    def hull(self, rings, tile=0, bone="vehicle_root"):
        points = []
        for z, width, length, offset, chamfer in rings:
            x, y, c = width / 2, length / 2, chamfer
            points.extend([(a, b + offset, z) for a, b in
                           [(-x+c, -y), (x-c, -y), (x, -y+c), (x, y-c),
                            (x-c, y), (-x+c, y), (-x, y-c), (-x, -y+c)]])
        faces = [tuple(reversed(range(8))), tuple(range(len(points)-8, len(points)))]
        for ring in range(len(rings) - 1):
            faces.extend([(ring*8+i, ring*8+(i+1)%8, (ring+1)*8+(i+1)%8, (ring+1)*8+i) for i in range(8)])
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


def track_path(distance, half=2.55, radius=.64):
    straight = 2 * half
    arc = math.pi * radius
    d = distance % (2 * straight + 2 * arc)
    if d < straight:
        return -half + d, .75 + radius, 0
    if d < straight + arc:
        t = (d - straight) / radius
        return half + radius * math.sin(t), .75 + radius * math.cos(t), -t
    if d < 2 * straight + arc:
        return half - (d - straight - arc), .75 - radius, -math.pi
    t = (d - 2 * straight - arc) / radius
    return -half - radius * math.sin(t), .75 - radius * math.cos(t), -math.pi-t


def tank(tag):
    model = Model(tag + "_tank")
    body = model.bone("hull", (0, 0, 1))
    turret = model.bone("turret", (0, -.35, 1.85), body)
    gun = model.bone("gun", (0, -1.25, 2.40), turret)
    width = {"VAL": 3.8, "NOD": 3.65, "STP": 3.45}[tag]
    if tag == "VAL":
        model.hull([(.7, width-1, 5.9, .1, .35), (1.45, width, 6.5, 0, .65), (1.8, width-.6, 5.5, .25, .65)], 0, body)
        model.hull([(1.8, 2.8, 3.3, .15, .45), (2.65, 3.0, 3.05, .35, .5), (2.9, 2.4, 2.6, .4, .5)], 1, turret)
        for side in (-1, 1):
            for y in (-.65, .15, .95):
                model.box((side*1.50, y, 2.40), (.22, .68, .6), 0, turret)
            for y in (-2.5, -1.4, -.3, .8, 1.9):
                model.box((side*1.95, y, 1.45), (.18, .95, .65), 9, body)
        muzzle = -7.0
    elif tag == "NOD":
        model.hull([(.7, 2.8, 5.9, .1, .55), (1.35, width, 6.2, .0, .8), (1.6, 2.9, 5.5, .25, .9)], 0, body)
        model.hull([(1.62, 2.7, 3.1, .15, .7), (2.22, 2.9, 3.6, .3, .9), (2.65, 1.65, 2.6, .5, .6)], 0, turret)
        for side in (-1, 1):
            model.plate([(side*1.84,-2.8,1.55),(side*1.84,2.8,1.55),
                         (side*1.84,2.4,.72),(side*1.84,-2.4,.72)], .1, 1, body, axis=0)
            model.box((side*1.62, .3, 1.68), (.17, 3.8, .06), 6, body)
        muzzle = -6.8
    else:
        model.hull([(.65, 2.5, 5.75, 0, .25), (1.45, width, 6.0, 0, .4), (1.75, 2.8, 4.9, .35, .5)], 0, body)
        model.hull([(1.75, 2.6, 2.8, .05, .4), (2.4, 2.35, 2.75, .1, .55), (2.75, 1.7, 2.25, .15, .5)], 9, turret)
        for side in (-1, 1):
            for y in (-1.5, -.4, .7):
                model.box((side*1.76, y, 1.55), (.16, .90, .56), 1, body)
            model.box((side*1.65, 2.20, 1.75), (.62, 1.05, .6), 14, body)
            model.rod((side*.7,2.55,1.4),(side*.7,2.55,2), .33, 1, body)
        muzzle = -6.2
    model.box((0, -1.45, 2.4), (.85, .60, .58), 1, turret)
    model.rod((0,-1.45,2.4),(0,muzzle,2.4), .115, 0, gun, .085)
    model.rod((0,-3.0,2.4),(0,-3.6,2.4), .18, 1, gun)
    model.rod((0,muzzle+.18,2.4),(0,muzzle-.05,2.4), .17, 1, gun)
    model.rod((0,muzzle-.051,2.4),(0,muzzle-.065,2.4), .09, 7, gun)
    # Opposite shoes share a bone: straight movement needs the same Y/Z transform
    # on both sides, keeping the complete vehicle below 48 bones.
    circumference = 10.2 + TAU*.64
    for side in (-1, 1):
        x = side*(width/2-.26)
        for index in range(36):
            d = circumference*index/36
            y, z, angle = track_path(d)
            bone = model.bone(f"track_{index:02}", (0,y,z))
            model.links[bone] = d
            model.box((x,y,z), (.76,circumference/36*.88,.12), 2, bone, Matrix.Rotation(angle, 3, "X"))
        for index, y in enumerate((-2.50,-1.50,-.5,.5,1.50,2.50)):
            center = (0,y,.75)
            bone = model.bone(f"wheel_{index}", center)
            if bone not in model.wheels:
                model.wheels.append(bone)
            model.rod((x-.27,y,.75),(x+.27,y,.75), .50, 2, bone)
            model.rod((x+side*.271,y,.75),(x+side*.30,y,.75), .36, 0, bone)
            model.rod((x+side*.30,y,.75),(x+side*.34,y,.75), .13, 1, bone)
    turret_top = {"VAL":2.9, "NOD":2.65, "STP":2.75}[tag]
    for side in (-1,1):
        model.box((side*1.15,2.25,1.78), (.65,1.18,.08), 7, body)
        model.box((side*1.30,-2.55,1.55), (.24,.20,.19), 13, body)
        model.rod((side*.7,1.1,turret_top),(side*.7,1.1,turret_top+1.15), .022, 7, turret, .009, 6)
        for y in (-.8,-.42,-.04):
            model.rod((side*1.25,y,2.1),(side*1.5,y-.25,2.25), .09, 1, turret, sides=8)
    model.rod((-.45,.45,turret_top-.05),(-.45,.45,turret_top+.12), .35, 1, turret)
    model.box((.45,-.40,turret_top+.10), (.32,.45,.28), 1, turret)
    model.box((.45,-.631,turret_top+.11), (.24,.02,.16), 5, turret)
    model.box((0,.9,turret_top+.003), (.42,.30,.004), 8, turret)
    model.box((0,2.65,1.75), (.8,.4,.12), 1, body)
    model.locators = {"barrel": ((0,muzzle-.08,2.4), gun),
                      "left_tracks": ((-width/2,1.8,.1), "vehicle_root"),
                      "right_tracks": ((width/2,1.8,.1), "vehicle_root"),
                      "left_exhaust": ((-.9,3.15,1.2), body),
                      "right_exhaust": ((.9,3.15,1.2), body)}
    return model


def aircraft(tag, role):
    model = Model(f"{tag}_{role}")
    cas = role == "cas"
    length = {"VAL": 16.5, "NOD": 17.0, "STP": 14.2}[tag] * (.90 if cas else 1)
    nose, tail = -length*.55, length*.45
    width = {"VAL": .90, "NOD": .72, "STP": .74}[tag] * (1.12 if cas else 1)
    model.loft([(nose,.05,.05,0), (nose+1.4,.40,.40,0), (nose+3.4,width,.68,0),
                (-.5,width*1.25,.72,0), (tail-1.2,width*.85,.6,0), (tail,width*.62,.44,0)], 0)
    model.loft([(nose+2.5,.15,.15,.40), (nose+3.4,.48,.44,.66),
                (nose+4.4,.48,.38,.62), (nose+5.15,.2,.15,.5)], 5, sides=8)
    model.box((0,nose+4.2,1.03), (.055,1.75,.055), 1)
    # The six wing plans are intentionally different silhouettes at map zoom.
    wings = {
        ("VAL","fighter"): [(1,-2.5), (6.8,.7), (6.4,3.0), (1,2.1)],
        ("NOD","fighter"): [(.7,-4.2), (5.6,.5), (6.4,3.9), (.8,2.5)],
        ("STP","fighter"): [(.7,-2.0), (5.1,.3), (4.8,2.0), (.8,1.5)],
        ("VAL","cas"): [(1,-1.8), (7.0,-.8), (6.8,1.5), (1,2.1)],
        ("NOD","cas"): [(1,-2.7), (6.1,-.1), (5.8,2.1), (1,1.8)],
        ("STP","cas"): [(1,-1.4), (7.2,-1.0), (7.2,1.05), (1,1.7)],
    }
    for side in (-1, 1):
        polygon = [(side*x,y,-.05) for x,y in wings[tag,role]]
        model.plate(polygon,.16,0)
        # A separate trailing-edge panel remains visible without adding control-surface bones.
        far = wings[tag,role][2]
        model.plate([(side*1.5,1.55,.055),(side*(far[0]-.3),far[1]-.25,.055),
                     (side*(far[0]-.45),far[1]-.02,.055),(side*1.5,1.86,.055)], .025, 1)
        model.plate([(side*1.6,tail-2.1,.15),(side*3.3,tail-.15,.15),
                     (side*3.1,tail+.4,.15),(side*.6,tail-.2,.15)], .12, 9)
        if tag == "VAL" and not cas:
            model.plate([(side*.8,nose+3.6,0),(side*2.5,nose+4.6,0),
                         (side*2.4,nose+5.2,0),(side*.8,nose+4.8,0)], .12, 9)
        fin_x = side*.85 if tag != "STP" or cas else 0
        if side == 1 or fin_x:
            model.plate([(fin_x,tail-2.4,.40),(fin_x+side*.45,tail-1.0,2.3),
                         (fin_x+side*.45,tail-.3,2.15),(fin_x,tail+.1,.40)], .12, 1, axis=0)
        engine_x = side*(1.25 if tag == "VAL" else 1.0)
        if cas and tag == "STP":
            engine_x = side*1.7
            model.loft([(1.0,.53,.53,.75),(2,.70,.70,.75),(tail-.3,.55,.55,.75)], 1, x=engine_x)
            model.rod((engine_x,1,.75),(engine_x,.96,.75), .45, 7)
            model.rod((engine_x,tail-.28,.75),(engine_x,tail-.20,.75), .43, 7)
        elif tag == "STP":
            if side == 1:
                model.rod((0,tail-.1,0),(0,tail+.28,0), .43, 3, end_radius=.36)
                model.rod((0,tail+.29,0),(0,tail+.30,0), .30, 7)
            model.box((side*.8,nose+4.8,-.12), (.5,1.2,.65), 1)
            model.box((side*.8,nose+4.19,-.12), (.4,.025,.5), 7)
        else:
            model.loft([(nose+4.6,.45,.48,-.2), (-.5,.62,.59,-.13),
                        (tail-.2,.46,.46,-.08)], 1, x=engine_x)
            model.rod((engine_x,nose+4.59,-.2),(engine_x,nose+4.57,-.2), .39, 7)
            model.rod((engine_x,tail-.2,-.08),(engine_x,tail+.18,-.08), .46, 3, end_radius=.36)
            model.rod((engine_x,tail+.19,-.08),(engine_x,tail+.21,-.08), .31, 7)
        # Distinct external ordnance and pylons separate strike aircraft from fighters.
        stations = (2.25,3.65,5.1) if cas else (3.3,4.6)
        for x in stations:
            y = -.1 + (x-2)*(.23 if not cas else .08)
            model.box((side*x,y,-.30), (.12,.7,.50), 1)
            if cas:
                model.rod((side*x,y-1,-.63),(side*x,y+.8,-.63), .20, 14, end_radius=.16)
                model.rod((side*x,y-1.3,-.63),(side*x,y-1,-.63), .035, 1, end_radius=.20)
            else:
                model.rod((side*x,y-1.35,-.60),(side*x,y+.7,-.60), .10, 4, end_radius=.075)
                model.rod((side*x,y-1.7,-.60),(side*x,y-1.35,-.60), .015, 1, end_radius=.10)
            model.plate([(side*x-.27,y+.3,-.6),(side*x+.27,y+.3,-.6),
                         (side*x+.27,y+.65,-.6),(side*x-.27,y+.65,-.6)], .04, 1)
        emblem_x = side*(4.5 if not cas else 5.5)
        model.box((emblem_x,.3,.033), (.60,.40,.004), 8)
        model.box((side*.63,nose+3.0,-.23), (.12,.80,.12), 3)
    if cas:
        model.rod((0,nose+1.35,-.4),(0,nose+.65,-.4), .16, 3)
    model.box((0,tail-2.5,.7), (.14,1.0,.12), 6)
    model.locators = {"root": ((0,0,0), "vehicle_root"),
                      "gun1": ((-.63,nose+2.5,-.23), "vehicle_root"),
                      "gun2": ((.63,nose+2.5,-.23), "vehicle_root"),
                      "bomb": ((0,0,-.7), "vehicle_root")}
    return model


def animate(model, rig, clip):
    rig.animation_data_clear()
    for bone in rig.pose.bones:
        bone.matrix_basis = Matrix.Identity(4)
        bone.rotation_mode = "XYZ"
    scene = bpy.context.scene
    frames = 121 if clip == "move" else (31 if clip == "attack" else 2)
    scene.render.fps = 30
    scene.frame_start, scene.frame_end = 1, frames
    for frame in range(1, frames+1):
        t = (frame-1)/(frames-1)
        for name, distance in model.links.items():
            y0,z0,a0 = track_path(distance)
            y,z,a = track_path(distance+t*(10.2+TAU*.64)) if clip == "move" else (y0,z0,a0)
            bone = rig.pose.bones[name]
            bone.location = (0,y-y0,z-z0)
            bone.rotation_euler.x = a-a0
        for name in model.wheels:
            rig.pose.bones[name].rotation_euler.x = -TAU*4*t if clip == "move" else 0
        if model.links:
            recoil = max(0,1-abs(t-.10)/.10) if clip == "attack" else 0
            rig.pose.bones["gun"].location.y = .42*recoil
            rig.pose.bones["hull"].rotation_euler.x = -.018*recoil
            rig.pose.bones["hull"].location.z = .025*math.sin(TAU*4*t) if clip == "move" else 0
        for bone in rig.pose.bones:
            bone.keyframe_insert("location", frame=frame)
            bone.keyframe_insert("rotation_euler", frame=frame)
    scene.frame_set(1)
    bpy.context.view_layer.objects.active = rig
    pdx.export_animfile(str(ROOT/f"{model.name}_{clip}.anim"),frame_start=1,frame_end=frames)


def export_rigid_mesh(path):
    pdx.export_meshfile(str(path), exp_selected=True)
    tree = pdx_data.read_meshfile(str(path))
    for skin in tree.findall("./object/*/mesh/skin"):
        weights, indices = skin.attrib["w"], skin.attrib["ix"]
        assert all(weights[i:i+4] == [1, 0, 0, 0] for i in range(0, len(weights), 4))
        skin.set("bones", [1])
        # The game shader fetches all four matrices before multiplying by weights.
        # Zero-weight slots must still address a valid matrix, not exporter padding -1.
        skin.set("ix", [indices[i - i % 4] for i in range(len(indices))])
    pdx_data.write_meshfile(str(path), tree)


def inspect_mesh(path):
    report = {"triangles": 0, "materials": 0, "bones": 0}
    tree = pdx_data.read_meshfile(str(path))
    for shape in tree.find("object"):
        bones = list(shape.find("skeleton"))
        report["bones"] = len(bones)
        for mesh in shape.findall("mesh"):
            data = pdx_data.PDXData(mesh)
            n = len(data.p)//3
            assert 0 < n < 65536 and len(data.n) == n*3 and len(data.u0) == n*2
            assert all(math.isfinite(x) for x in data.p+data.n+data.u0+data.ta)
            assert all(0 <= x <= 1 for x in data.u0)
            assert min(data.tri) >= 0 and max(data.tri) < n and len(data.tri)%3 == 0
            points = [Vector(data.p[i:i+3]) for i in range(0,len(data.p),3)]
            assert all((points[b]-points[a]).cross(points[c]-points[a]).length > 1e-9
                       for a,b,c in zip(data.tri[::3],data.tri[1::3],data.tri[2::3]))
            influences = data.skin.bones[0]
            assert influences == 1, (path.name, "rigid skin must declare one influence")
            # Native files keep four storage slots even for a one-influence skin.
            assert len(data.skin.w) == len(data.skin.ix) == n*4
            for i in range(n):
                weights = data.skin.w[i*4:(i+1)*4]
                indices = data.skin.ix[i*4:(i+1)*4]
                assert abs(sum(weights)-1) < .001
                assert weights == [1, 0, 0, 0]
                assert all(0 <= bone < len(bones) for bone in indices)
            assert data.material.shader == ["PdxMeshAdvancedSnow"]
            for channel in ("diff", "n", "spec"):
                assert (path.parent/getattr(data.material,channel)[0]).is_file()
            report["triangles"] += len(data.tri)//3
            report["materials"] += 1
    report["rigid_skin_slots_validated"] = True
    report["locators"] = [loc.tag for loc in tree.find("locator")]
    return report


def verify_native(name, folder=ROOT):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    path = folder / (name + ".mesh")
    report = inspect_mesh(path)
    pdx.import_meshfile(str(path),join_materials=False)
    for mat in bpy.data.materials:
        if mat.use_nodes and mat.node_tree.nodes.get("Principled BSDF"):
            preview_gloss(mat)
    objects = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    rigs = [o for o in bpy.context.scene.objects if o.type == "ARMATURE"]
    report["animations"], report["files"] = {}, {}
    clips = ("idle", "move", "attack") if name.endswith("tank") else ("idle",)
    for clip in clips:
        for rig in rigs:
            rig.animation_data_clear()
        pdx.import_animfile(str(folder/f"{name}_{clip}.anim"))
        frames = sorted({1,2, max(2,bpy.context.scene.frame_end//10),
                         max(2,bpy.context.scene.frame_end//2), bpy.context.scene.frame_end})
        samples = []
        for frame in frames:
            bpy.context.scene.frame_set(frame)
            graph = bpy.context.evaluated_depsgraph_get()
            points = [o.matrix_world @ v.co for o in objects for v in o.evaluated_get(graph).data.vertices]
            assert all(math.isfinite(c) for p in points for c in p)
            assert max(p.length for p in points) < 25
            samples.append(points)
        motion = max((a-b).length for points in samples[1:] for a,b in zip(samples[0], points))
        loop_error = max((a-b).length for a,b in zip(samples[0],samples[-1]))
        report["animations"][clip] = {"samples": len(frames), "max_vertex_motion": motion, "loop_error": loop_error}
        if clip in ("move", "attack"):
            assert motion > .1, (name,clip,"stationary animation")
        assert loop_error < .001, (name,clip,loop_error)
    filenames = [name+".mesh"] + [name+"_"+clip+".anim" for clip in clips]
    family = "tank" if name.endswith("tank") else "air"
    filenames += [name[:3]+"_"+family+"_"+channel+".dds" for channel in ("diffuse","normal","specular")]
    report["files"] = {filename: hashlib.sha256((folder/filename).read_bytes()).hexdigest() for filename in filenames}
    for rig in rigs:
        rig.animation_data_clear()
    pdx.import_animfile(str(folder/f"{name}_idle.anim"))
    bpy.context.scene.frame_set(1)
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/f"{name}.blend"))
    return report


def build(name):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    tag, role = name.split("_")
    family = "tank" if role == "tank" else "air"
    prefix = tag + "_" + family
    spec = SimpleNamespace(shader=["PdxMeshAdvancedSnow"],diff=[prefix+"_diffuse.dds"],
                           n=[prefix+"_normal.dds"],spec=[prefix+"_specular.dds"])
    material = pdx.create_shader(spec,name,str(ROOT))
    preview_gloss(material)
    model = tank(tag) if role == "tank" else aircraft(tag,role)
    obj,rig = model.object(material)
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    for empty in [o for o in bpy.context.scene.objects if o.type == "EMPTY"]:
        empty.select_set(True)
    bpy.context.view_layer.objects.active = obj
    export_rigid_mesh(ROOT/(name+".mesh"))
    for clip in (("idle","move","attack") if role == "tank" else ("idle",)):
        animate(model,rig,clip)
    return verify_native(name)


def preview(role):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    spacing = 10 if role == "tank" else 20
    for index, tag in enumerate(TAGS):
        before = set(bpy.context.scene.objects)
        pdx.import_meshfile(str(ROOT/f"{tag}_{role}.mesh"),join_materials=False)
        # Keep meshes, rigs and their parented locators together in the preview.
        new = set(bpy.context.scene.objects)-before
        for obj in new:
            if obj.parent is None:
                obj.location.x += (index-1)*spacing
        for mat in bpy.data.materials:
            if mat.use_nodes and mat.node_tree.nodes.get("Principled BSDF"):
                preview_gloss(mat)
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.samples = 24
    scene.render.resolution_x, scene.render.resolution_y = 1920, 920
    scene.render.resolution_percentage = 100
    scene.world = bpy.data.worlds.new("Vehicle studio")
    scene.world.color = (.24,.24,.24)
    target = Vector((0,0,0))
    bpy.ops.object.camera_add(location=(12,-30,24) if role == "tank" else (14,-40,51))
    camera = bpy.context.object
    camera.rotation_euler = (target-camera.location).to_track_quat("-Z","Y").to_euler()
    camera.data.type = "ORTHO"
    camera.data.ortho_scale = 33 if role == "tank" else 65
    scene.camera = camera
    for location,power in [((0,-30,40),55000),((-25,5,30),45000),((25,25,40),65000)]:
        bpy.ops.object.light_add(type="AREA",location=location)
        lamp = bpy.context.object
        lamp.data.energy, lamp.data.size = power,30
        lamp.rotation_euler = (target-lamp.location).to_track_quat("-Z","Y").to_euler()
    bpy.context.preferences.filepaths.save_version=0
    bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/f"{role}_lineup.blend"))
    scene.render.filepath = str(ROOT/f"{role}_lineup.png")
    bpy.ops.render.render(write_still=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--names",nargs="*",choices=NAMES)
    parser.add_argument("--preview",choices=("tank","fighter","cas"))
    parser.add_argument("--verify-installed",action="store_true")
    args = parser.parse_args(sys.argv[sys.argv.index("--")+1:] if "--" in sys.argv else [])
    if args.preview:
        preview(args.preview)
    else:
        path = ROOT/"verification.json"
        report = json.loads(path.read_text()) if path.exists() else {}
        for name in args.names or NAMES:
            report[name] = verify_native(name, ROOT.parents[3]/"gfx/models/units/ADISCORD_country_vehicles") if args.verify_installed else build(name)
            path.write_text(json.dumps(report,indent=2)+"\n")
            print("VERIFIED",name,json.dumps({k:v for k,v in report[name].items() if k != "files"}))
