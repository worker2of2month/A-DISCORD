"""Build and package the Taran native model and model-derived interface art.

python -B -m tools.assets.source.build_taran --prepare
blender --background --factory-startup --threads 4 --python this_file -- --build
python -B -m tools.assets.source.build_taran --icons
python -B -m tools.assets.source.build_taran --check
python -B -m tools.assets.source.build_taran --apply
python -B -m tools.assets.source.build_taran --check

The staging directory retains the editable Blender model and native reimport
portrait. Entity and sprite registrations are owned by their existing builders.
"""

import argparse
import hashlib
import json
import math
from pathlib import Path
import random
import sys
from types import SimpleNamespace

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[3]
STAGE = ROOT / "work/taran-model"
DEST = ROOT / "gfx/models/units/ADISCORD_country_vehicles"
NAME = "STS_taran"
CLIPS = ("idle", "move", "attack")
TRACK_HALF = 2.9
TRACK_RADIUS = 0.78
TRACK_CENTER = 0.89
TRACK_LENGTH = TRACK_HALF * 4 + math.tau * TRACK_RADIUS
# Hull, gun, root and seven wheel joints leave forty joints for both tracks.
MAX_JOINTS = 50
TRACK_LINKS = 40
NATIVE_FILES = [f"{NAME}.mesh"]
NATIVE_FILES += [f"{NAME}_{clip}.anim" for clip in CLIPS]
NATIVE_FILES += [f"{NAME}_{channel}.dds" for channel in ("diffuse", "normal", "specular")]
UI_FILES = {
    "STP_taran_equipment.dds": "gfx/interface/technologies/STP_taran_equipment.dds",
    "STP_taran_project.dds": "gfx/interface/technologies/STP_taran_project.dds",
    "STP_taran_icon_large.dds": "gfx/interface/counters/divisions_large/STP_taran_icon.dds",
    "STP_taran_icon_small.dds": "gfx/interface/counters/divisions_small/STP_taran_icon.dds",
    "STP_taran_texticon.dds": "gfx/texticons/STP_taran_icon_small.dds",
}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_changed(path, content):
    if not path.is_file() or path.read_bytes() != content:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)


def prepare():
    from PIL import Image, ImageDraw
    from tools.assets.source.build_shl_palace import dds_bytes

    STAGE.mkdir(parents=True, exist_ok=True)
    palette = [
        (76, 80, 61), (52, 57, 46), (36, 39, 35), (106, 107, 96),
        (130, 128, 111), (37, 57, 61), (121, 68, 48), (20, 23, 22),
        (170, 169, 142), (90, 94, 73), (132, 107, 66), (87, 64, 44),
        (63, 65, 55), (202, 193, 156), (63, 72, 56), (107, 111, 94),
    ]
    atlas = Image.new("RGBA", (1024, 1024))
    rng = random.Random("STS_taran_armor")
    for index, color in enumerate(palette):
        tile = Image.new("RGBA", (256, 256))
        pixels = []
        for y in range(256):
            for x in range(256):
                wear = rng.gauss(0, 2.0)
                wear += 6 * math.sin(x * 0.047 + y * 0.032)
                wear += 4 * math.sin(x * 0.093 - y * 0.019)
                mud = max(0, (y - 160) / 96) * 13 if index in (0, 1, 9, 12) else 0
                pixels.append(tuple(max(0, min(255, round(c + wear - mud))) for c in color) + (255,))
        tile.putdata(pixels)
        draw = ImageDraw.Draw(tile)
        if index in (0, 1, 9, 12):
            draw.rectangle((3, 3, 252, 252), outline=(38, 42, 34), width=3)
            draw.line((7, 8, 249, 8), fill=(121, 123, 100), width=2)
            for x in (14, 128, 242):
                for y in (14, 242):
                    draw.ellipse((x - 3, y - 3, x + 3, y + 3), fill=(122, 122, 104))
            for _ in range(95):
                x, y = rng.randrange(256), rng.randrange(256)
                draw.line((x, y, min(255, x + rng.randrange(2, 15)), y + 1), fill=(49, 49, 41), width=1)
            for _ in range(35):
                x, y = rng.randrange(256), rng.randrange(256)
                draw.line((x, y, min(255, x + 4), y), fill=(124, 121, 102), width=1)
        if index == 2:
            for y in range(8, 256, 30):
                draw.line((0, y, 255, y), fill=(99, 94, 78), width=3)
        if index == 7:
            for y in range(3, 256, 16):
                draw.line((0, y, 255, y), fill=(59, 62, 53), width=3)
        if index == 5:
            draw.polygon(((8, 240), (8, 50), (240, 8), (240, 63)), fill=(91, 113, 112))
        if index == 8:
            draw.text((72, 70), "T-01", fill=(55, 57, 46), stroke_width=1)
            draw.line((58, 180, 198, 180), fill=(67, 70, 56), width=8)
        atlas.paste(tile, ((index % 4) * 256, (index // 4) * 256))
    specular = Image.new("RGBA", atlas.size, (0, 24, 0, 29))
    ImageDraw.Draw(specular).rectangle((256, 256, 511, 511), fill=(0, 78, 0, 92))
    maps = {
        "diffuse": atlas,
        "normal": Image.new("RGBA", atlas.size, (128, 128, 0, 128)),
        "specular": specular,
    }
    for channel, image in maps.items():
        write_changed(STAGE / f"{NAME}_{channel}.dds", dds_bytes(image))


def track_path(distance):
    distance %= TRACK_LENGTH
    straight = 2 * TRACK_HALF
    arc = math.pi * TRACK_RADIUS
    if distance < straight:
        return -TRACK_HALF + distance, TRACK_CENTER + TRACK_RADIUS, 0
    if distance < straight + arc:
        angle = (distance - straight) / TRACK_RADIUS
        return TRACK_HALF + TRACK_RADIUS * math.sin(angle), TRACK_CENTER + TRACK_RADIUS * math.cos(angle), -angle
    if distance < 2 * straight + arc:
        return TRACK_HALF - (distance - straight - arc), TRACK_CENTER - TRACK_RADIUS, -math.pi
    angle = (distance - 2 * straight - arc) / TRACK_RADIUS
    return -TRACK_HALF - TRACK_RADIUS * math.sin(angle), TRACK_CENTER - TRACK_RADIUS * math.cos(angle), -math.pi - angle


def hull(model, rings, tile, bone):
    points = []
    for z, width, front, rear, chamfer in rings:
        x = width / 2
        points.extend((a, b, z) for a, b in (
            (-x + chamfer, front), (x - chamfer, front), (x, front + chamfer),
            (x, rear - chamfer), (x - chamfer, rear), (-x + chamfer, rear),
            (-x, rear - chamfer), (-x, front + chamfer),
        ))
    faces = [tuple(reversed(range(8))), tuple(range(len(points) - 8, len(points)))]
    for ring in range(len(rings) - 1):
        faces.extend((ring * 8 + i, ring * 8 + (i + 1) % 8,
                      (ring + 1) * 8 + (i + 1) % 8, (ring + 1) * 8 + i) for i in range(8))
    model.solid(points, faces, tile, bone)


def barrel(model, bone):
    z = 2.12
    # The inner tube and recessed black breech keep the muzzle open at oblique views.
    stations = [(-1.64, .49), (-2.15, .49), (-2.58, .37), (-3.35, .34), (-3.92, .33)]
    sides = 20
    points = [(radius * math.cos(i * math.tau / sides), y,
               z + radius * math.sin(i * math.tau / sides))
              for y, radius in stations for i in range(sides)]
    faces = []
    for ring in range(len(stations) - 1):
        faces.extend((ring * sides + i, ring * sides + (i + 1) % sides,
                      (ring + 1) * sides + (i + 1) % sides, (ring + 1) * sides + i) for i in range(sides))
    model.solid(points, faces, 1, bone, smooth=True)
    inner = []
    for y, radius in ((-3.92, .245), (-3.22, .235)):
        inner.extend((radius * math.cos(i * math.tau / sides), y,
                      z + radius * math.sin(i * math.tau / sides)) for i in range(sides))
    model.solid(inner, [(i, (i + 1) % sides, (i + 1) % sides + sides, i + sides)
                       for i in range(sides)] + [tuple(range(sides, sides * 2))], 7, bone)
    ring = points[-sides:] + inner[:sides]
    model.solid(ring, [(i, (i + 1) % sides, (i + 1) % sides + sides, i + sides)
                      for i in range(sides)], 3, bone)
    for y, radius in ((-2.12, .51), (-2.56, .40), (-3.35, .365), (-3.85, .355)):
        # Reinforcing collars stop before the open bore.
        outer = []
        for yy in (y - .04, y + .04):
            outer.extend((radius * math.cos(i * math.tau / sides), yy,
                          z + radius * math.sin(i * math.tau / sides)) for i in range(sides))
        model.solid(outer, [(i, (i + 1) % sides, (i + 1) % sides + sides, i + sides)
                           for i in range(sides)], 3, bone, smooth=True)


def vehicle():
    model = cas.Model(NAME)
    model.links = {}
    model.wheels = []
    body = model.bone("hull", (0, 0, 1.1))
    gun = model.bone("gun", (0, -1.64, 2.12), body)
    hull(model, [(.55, 3.65, -3.45, 3.35, .28), (1.37, 4.20, -4.05, 3.75, .45),
                 (1.62, 4.10, -3.25, 3.55, .40)], 0, body)
    hull(model, [(1.60, 3.75, -2.05, 1.90, .27), (2.67, 3.16, -1.25, 1.58, .32)], 0, body)
    model.box((0, .25, 2.70), (2.66, 2.22, .09), 9, body)
    hull(model, [(1.76, 1.28, -2.12, -1.48, .15), (2.49, 1.25, -1.88, -1.40, .14)], 12, body)
    barrel(model, gun)
    for side in (-1, 1):
        x = side * 2.17
        for index in range(TRACK_LINKS):
            distance = TRACK_LENGTH * index / TRACK_LINKS
            y, z, angle = track_path(distance)
            bone = f"track_{index:02}"
            if bone not in model.bones:
                model.bone(bone, (0, y, z))
                model.links[bone] = distance
            rotation = Matrix.Rotation(angle, 3, "X")
            model.box((x, y, z), (.94, TRACK_LENGTH / TRACK_LINKS * .90, .15), 2, bone, rotation)
            ridge = Vector((0, 0, .095))
            model.box(Vector((x, y, z)) + rotation @ ridge,
                      (.91, .075, .055), 3, bone, rotation)
        for index, y in enumerate((-2.85, -1.9, -.95, 0, .95, 1.9, 2.85)):
            name = f"wheel_{index}"
            if name not in model.bones:
                model.bone(name, (0, y, TRACK_CENTER))
                model.wheels.append(name)
            radius = .63 if index in (0, 6) else .55
            model.rod((x - .32, y, TRACK_CENTER), (x + .32, y, TRACK_CENTER), radius, 2, name, sides=16)
            model.rod((x + side * .325, y, TRACK_CENTER), (x + side * .36, y, TRACK_CENTER), radius * .76, 1, name, sides=16)
            model.rod((x + side * .36, y, TRACK_CENTER), (x + side * .41, y, TRACK_CENTER), .15, 3, name, sides=12)
            for angle in range(0, 360, 60):
                a = math.radians(angle)
                yy, zz = y + .31 * math.sin(a), TRACK_CENTER + .31 * math.cos(a)
                model.rod((x + side * .365, yy, zz), (x + side * .385, yy, zz), .035, 3, name, sides=6)
        model.box((side * 2.14, 0, 1.76), (1.12, 6.60, .14), 9, body)
        for index, y in enumerate((-2.50, -1.50, -.50, .50, 1.50, 2.50)):
            model.box((side * 2.69, y, 1.20), (.13, .95, 1.12), 0 if index % 2 else 12, body)
            model.box((side * 2.775, y, 1.68), (.04, .80, .075), 3, body)
            for yy in (y - .32, y + .32):
                model.rod((side * 2.76, yy, 1.58), (side * 2.80, yy, 1.58), .045, 3, body, sides=6)
        model.box((side * 2.15, 2.52, 1.95), (.72, 1.12, .27), 1, body)
        for y in (2.16, 2.30, 2.44, 2.58, 2.72, 2.86):
            model.box((side * 2.15, y, 2.095), (.60, .055, .025), 7, body)
        model.box((side * 1.04, -1.74, 2.11), (.43, .24, .28), 1, body)
        model.box((side * 1.04, -1.87, 2.12), (.30, .025, .15), 5, body)
        model.box((side * 2.08, -2.77, 1.92), (.33, .30, .25), 1, body)
        model.box((side * 2.08, -2.93, 1.92), (.24, .025, .14), 13, body)
        for y in (-.75, .10, .95):
            model.box((side * 1.72, y, 2.04), (.11, .73, .55), 12, body)
        for y in (-.55, .15, .85):
            model.rod((side * 1.81, y, 2.24), (side * 1.85, y, 2.24), .045, 3, body, sides=6)
        model.rod((side * .92, 3.49, 1.42), (side * .92, 3.81, 1.42), .16, 7, body, sides=10)
        model.rod((side * 1.73, 1.10, 2.24), (side * 1.73, 1.10, 2.54), .055, 3, body, sides=8)
        model.box((side * 1.80, -.70, 2.35), (.13, 1.20, .08), 1, body)
        for y in (-1.20, -.20):
            model.rod((side * 1.79, y, 2.11), (side * 1.79, y, 2.35), .05, 3, body, sides=8)
        # Front toe armor protects the hull while leaving the track curves visible.
        model.plate([(side * .06, -4.13, .76), (side * 1.82, -3.96, .76),
                     (side * 1.66, -3.27, 1.62), (side * .06, -3.35, 1.62)], .11, 12, body, axis=1)
        for y, z in ((-3.91, .93), (-3.50, 1.46)):
            model.rod((side * 1.54, y - .07, z), (side * 1.54, y, z), .065, 3, body, sides=6)
        for x0 in (.77, 1.13):
            model.rod((side * x0, -4.10, .72), (side * x0, -4.28, .54), .055, 3, body, sides=8)
        model.rod((side * .77, -4.28, .54), (side * 1.13, -4.28, .54), .055, 3, body, sides=8)
    model.rod((-.73, .58, 2.73), (-.73, .58, 2.83), .43, 1, body, sides=16)
    model.box((-.73, .58, 2.85), (.22, .06, .055), 3, body)
    model.box((.62, -.36, 2.79), (.64, .46, .19), 1, body)
    model.box((.62, -.60, 2.80), (.50, .025, .11), 5, body)
    model.box((0, 2.73, 1.69), (1.75, 1.15, .09), 7, body)
    for y in (2.30, 2.48, 2.66, 2.84, 3.02, 3.20):
        model.box((0, y, 1.75), (1.63, .065, .055), 3, body)
    model.box((0, 3.46, 1.19), (1.85, .25, .51), 1, body)
    model.locators = {
        "root": ((0, 0, 0), "vehicle_root"),
        "barrel": ((0, -3.94, 2.12), gun),
        "left_tracks": ((-2.17, 2.45, .13), "vehicle_root"),
        "right_tracks": ((2.17, 2.45, .13), "vehicle_root"),
        "left_exhaust": ((-.92, 3.83, 1.42), body),
        "right_exhaust": ((.92, 3.83, 1.42), body),
    }
    return model


def animate(model, rig, clip):
    rig.animation_data_clear()
    for bone in rig.pose.bones:
        bone.matrix_basis = Matrix.Identity(4)
        bone.rotation_mode = "XYZ"
    scene = bpy.context.scene
    frames = 121 if clip == "move" else 31 if clip == "attack" else 2
    scene.render.fps = 30
    scene.frame_start, scene.frame_end = 1, frames
    for frame in range(1, frames + 1):
        t = (frame - 1) / (frames - 1)
        for name, distance in model.links.items():
            y0, z0, a0 = track_path(distance)
            y, z, angle = track_path(distance + t * TRACK_LENGTH) if clip == "move" else (y0, z0, a0)
            bone = rig.pose.bones[name]
            bone.location = (0, y - y0, z - z0)
            bone.rotation_euler.x = angle - a0
        for name in model.wheels:
            rig.pose.bones[name].rotation_euler.x = -math.tau * 4 * t if clip == "move" else 0
        recoil = max(0, 1 - abs(t - .10) / .10) if clip == "attack" else 0
        rig.pose.bones["gun"].location.y = .27 * recoil
        rig.pose.bones["hull"].rotation_euler.x = -.012 * recoil
        rig.pose.bones["hull"].location.z = .018 * math.sin(math.tau * 4 * t) if clip == "move" else 0
        for bone in rig.pose.bones:
            bone.keyframe_insert("location", frame=frame)
            bone.keyframe_insert("rotation_euler", frame=frame)
    scene.frame_set(1)
    bpy.context.view_layer.objects.active = rig
    pdx.export_animfile(str(STAGE / f"{NAME}_{clip}.anim"), frame_start=1, frame_end=frames)
    rig.animation_data.action.name = f"{NAME}_{clip}"
    rig.animation_data.action.use_fake_user = True


def export():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    material = pdx.create_shader(SimpleNamespace(
        shader=["PdxMeshAdvanced"], diff=[f"{NAME}_diffuse.dds"],
        n=[f"{NAME}_normal.dds"], spec=[f"{NAME}_specular.dds"],
    ), NAME, str(STAGE))
    model = vehicle()
    obj, rig = model.object(material)
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    for empty in [o for o in bpy.context.scene.objects if o.type == "EMPTY"]:
        empty.select_set(True)
    bpy.context.view_layer.objects.active = obj
    path = STAGE / f"{NAME}.mesh"
    pdx.export_meshfile(str(path), exp_selected=True)
    tree = pdx_data.read_meshfile(str(path))
    for mesh in tree.findall("./object/*/mesh"):
        skin = mesh.find("skin")
        weights, indices = skin.attrib["w"], skin.attrib["ix"]
        assert all(weights[i:i + 4] == [1, 0, 0, 0] for i in range(0, len(weights), 4))
        skin.set("bones", [1])
        # The native shader fetches every matrix before applying its weight.
        skin.set("ix", [indices[i - i % 4] for i in range(len(indices))])
        mesh.attrib["ta"] = [round(value, 5) for value in mesh.attrib["ta"]]
    pdx_data.write_meshfile(str(path), tree)
    for clip in CLIPS:
        animate(model, rig, clip)
    rig.animation_data.action = bpy.data.actions[f"{NAME}_idle"]
    bpy.context.scene.frame_set(1)
    cas.preview_materials()
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.file.pack_all()
    bpy.ops.wm.save_as_mainfile(filepath=str(STAGE / f"{NAME}.blend"))


def verify():
    path = STAGE / f"{NAME}.mesh"
    tree = pdx_data.read_meshfile(str(path))
    report = {"triangles": 0, "vertices": 0, "materials": 0, "bones": 0}
    for shape in tree.find("object"):
        bones = list(shape.find("skeleton"))
        report["bones"] = len(bones)
        assert len(bones) <= MAX_JOINTS, (len(bones), MAX_JOINTS)
        for mesh in shape.findall("mesh"):
            data = pdx_data.PDXData(mesh)
            count = len(data.p) // 3
            assert 0 < count < 65536
            assert len(data.n) == count * 3 and len(data.u0) == count * 2
            assert len(data.ta) == count * 4
            assert all(math.isfinite(value) for value in data.p + data.n + data.u0 + data.ta)
            assert all(0 <= value <= 1 for value in data.u0)
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
                assert (STAGE / getattr(data.material, key)[0]).read_bytes()[:4] == b"DDS "
            report["triangles"] += len(data.tri) // 3
            report["vertices"] += count
            report["materials"] += 1
    assert report["triangles"] < 16000 and report["materials"] == 1
    report["locators"] = [loc.tag for loc in tree.find("locator")]
    assert {"root", "barrel", "left_tracks", "right_tracks", "left_exhaust", "right_exhaust"}.issubset(report["locators"])
    report["rigid_skin_slots_validated"] = True
    report["animations"] = {}
    for clip in CLIPS:
        bpy.ops.wm.read_factory_settings(use_empty=True)
        pdx.import_meshfile(str(path), join_materials=False)
        pdx.import_animfile(str(STAGE / f"{NAME}_{clip}.anim"))
        objects = [o for o in bpy.context.scene.objects if o.type == "MESH"]
        rig = next(o for o in bpy.context.scene.objects if o.type == "ARMATURE")
        end = bpy.context.scene.frame_end
        frames = sorted({1, 2, max(2, end // 10), max(2, end // 4), max(2, end // 2), end})
        samples = []
        poses = []
        for frame in frames:
            bpy.context.scene.frame_set(frame)
            graph = bpy.context.evaluated_depsgraph_get()
            points = [o.matrix_world @ v.co for o in objects for v in o.evaluated_get(graph).data.vertices]
            assert all(math.isfinite(c) for point in points for c in point)
            assert max(point.length for point in points) < 20
            samples.append(points)
            poses.append({bone.name: bone.matrix.copy() for bone in rig.pose.bones})
        motion = max((a - b).length for points in samples[1:] for a, b in zip(samples[0], points))
        loop_error = max((a - b).length for a, b in zip(samples[0], samples[-1]))
        assert loop_error < .001, (clip, loop_error)
        if clip in ("move", "attack"):
            assert motion > .10, (clip, motion)
        def pose_motion(prefix):
            names = [name for name in poses[0] if name.startswith(prefix)]
            return max(abs(a - b) for pose in poses[1:] for name in names
                       for row0, row1 in zip(poses[0][name], pose[name]) for a, b in zip(row0, row1))
        metrics = {"samples": len(frames), "max_vertex_motion": motion, "loop_error": loop_error}
        if clip == "move":
            metrics["track_bone_motion"] = pose_motion("track_")
            metrics["wheel_bone_motion"] = pose_motion("wheel_")
            assert metrics["track_bone_motion"] > .1 and metrics["wheel_bone_motion"] > .1
        if clip == "attack":
            metrics["gun_bone_motion"] = pose_motion("gun")
            assert metrics["gun_bone_motion"] > .1
        report["animations"][clip] = metrics
    report["dimensions"] = [max(p[i] for p in samples[0]) - min(p[i] for p in samples[0]) for i in range(3)]
    report["native_reimport"] = True
    report["hoi4_runtime_verified"] = False
    report["recommended_pdxmesh_scale"] = .50
    report["files"] = {name: digest(STAGE / name) for name in NATIVE_FILES}
    report["blend_sha256"] = digest(STAGE / f"{NAME}.blend")
    report["generator_sha256"] = digest(Path(__file__))
    write_changed(STAGE / f"{NAME}_verification.json", (json.dumps(report, indent=2) + "\n").encode())
    print(json.dumps(report, indent=2), flush=True)


def render():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    pdx.import_meshfile(str(STAGE / f"{NAME}.mesh"), join_materials=False)
    pdx.import_animfile(str(STAGE / f"{NAME}_idle.anim"))
    bpy.context.scene.frame_set(1)
    cas.preview_materials()
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.samples = 48
    scene.cycles.use_denoising = True
    scene.render.resolution_x, scene.render.resolution_y = 1400, 1040
    scene.render.resolution_percentage = 100
    scene.world = bpy.data.worlds.new("Taran studio")
    scene.world.use_nodes = True
    scene.world.node_tree.nodes["Background"].inputs[0].default_value = (.24, .27, .30, 1)
    scene.world.node_tree.nodes["Background"].inputs[1].default_value = .65
    scene.view_settings.view_transform = "AgX"
    target = Vector((0, -.12, 1.20))
    bpy.ops.object.camera_add(location=(11, -15, 8.0))
    camera = bpy.context.object
    camera.rotation_euler = (target - camera.location).to_track_quat("-Z", "Y").to_euler()
    camera.data.type, camera.data.ortho_scale = "ORTHO", 11.1
    scene.camera = camera
    for location, power, size in (((-6, -10, 12), 2600, 8), ((10, -4, 8), 1800, 8), ((-5, 9, 10), 3500, 7)):
        bpy.ops.object.light_add(type="AREA", location=location)
        light = bpy.context.object
        light.data.energy, light.data.size = power, size
        light.rotation_euler = (target - light.location).to_track_quat("-Z", "Y").to_euler()
    scene.render.film_transparent = True
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.filepath = str(STAGE / f"{NAME}_portrait.png")
    bpy.ops.render.render(write_still=True)


def icons():
    from PIL import Image, ImageEnhance, ImageOps
    from tools.assets.source.build_shl_palace import dds_bytes

    portrait = Image.open(STAGE / f"{NAME}_portrait.png").convert("RGBA")
    bounds = portrait.getchannel("A").getbbox()
    assert bounds is not None
    portrait = portrait.crop(bounds)
    def fit(size, margin=4):
        image = Image.new("RGBA", size)
        scaled = ImageOps.contain(portrait, (size[0] - margin * 2, size[1] - margin * 2), Image.Resampling.LANCZOS)
        image.alpha_composite(scaled, ((size[0] - scaled.width) // 2, (size[1] - scaled.height) // 2))
        return image
    equipment = fit((176, 112))
    project = fit((128, 128), 5)
    images = {"STP_taran_equipment.dds": equipment, "STP_taran_project.dds": project}
    for filename, width, height in (("STP_taran_icon_large.dds", 76, 42),
                                    ("STP_taran_icon_small.dds", 30, 12),
                                    ("STP_taran_texticon.dds", 30, 12)):
        frame = fit((width, height), 1)
        second = ImageEnhance.Brightness(frame).enhance(1.24)
        strip = Image.new("RGBA", (width * 2, height))
        strip.alpha_composite(frame, (0, 0))
        strip.alpha_composite(second, (width, 0))
        images[filename] = strip
    for filename, image in images.items():
        write_changed(STAGE / filename, dds_bytes(image))
    report_path = STAGE / f"{NAME}_verification.json"
    report = json.loads(report_path.read_text())
    report["ui"] = {name: {"dimensions": list(image.size), "sha256": digest(STAGE / name)} for name, image in images.items()}
    report["portrait_sha256"] = digest(STAGE / f"{NAME}_portrait.png")
    write_changed(report_path, (json.dumps(report, indent=2) + "\n").encode())


def package(apply=False):
    report_path = STAGE / f"{NAME}_verification.json"
    if not report_path.is_file():
        print(json.dumps({"missing": str(report_path.relative_to(ROOT)), "applied": False}))
        return [str(report_path.relative_to(ROOT))]
    report = json.loads(report_path.read_text())
    assert report["bones"] <= MAX_JOINTS
    assert digest(Path(__file__)) == report["generator_sha256"], "Rebuild after editing the generator"
    assert digest(STAGE / f"{NAME}.blend") == report["blend_sha256"]
    assert digest(STAGE / f"{NAME}_portrait.png") == report["portrait_sha256"]
    files = {DEST / report_path.name: report_path.read_bytes()}
    for name, expected in report["files"].items():
        assert digest(STAGE / name) == expected, name
        files[DEST / name] = (STAGE / name).read_bytes()
    assert set(report["ui"]) == set(UI_FILES)
    for name, relative in UI_FILES.items():
        assert digest(STAGE / name) == report["ui"][name]["sha256"], name
        files[ROOT / relative] = (STAGE / name).read_bytes()
    changed = [str(path.relative_to(ROOT)) for path, content in files.items()
               if not path.is_file() or path.read_bytes() != content]
    if apply:
        for path, content in files.items():
            write_changed(path, content)
    print(json.dumps({"files": len(files), "changed": changed, "applied": apply}, indent=2))
    return changed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_mutually_exclusive_group(required=True)
    for action in ("prepare", "build", "render", "icons", "check", "apply"):
        actions.add_argument("--" + action, action="store_true")
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else None)
    if args.prepare:
        prepare()
    elif args.icons:
        icons()
    elif args.build or args.render:
        global bpy, bmesh, Matrix, Vector, pdx, pdx_data, cas
        import bpy
        import bmesh
        from mathutils import Matrix, Vector
        sys.path.insert(0, str(Path(__file__).parent))
        import build_country_cas as cas
        from build_shl_palace import load_exporter
        pdx = load_exporter()
        from io_pdx_mesh import pdx_data
        cas.bpy, cas.bmesh, cas.Matrix, cas.Vector = bpy, bmesh, Matrix, Vector
        if args.build:
            export()
            verify()
        render()
    else:
        changed = package(apply=args.apply)
        if args.check and changed:
            raise SystemExit(1)


if __name__ == "__main__":
    main()
