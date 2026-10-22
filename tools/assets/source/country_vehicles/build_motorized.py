"""Build national wheeled APCs, then check/apply the verified native package.

python -B -m tools.assets.source.country_vehicles.build_motorized --prepare
blender --background --factory-startup --threads 4 --python this_file -- --build
python -B -m tools.assets.source.country_vehicles.build_motorized --check
python -B -m tools.assets.source.country_vehicles.build_motorized --apply
python -B -m tools.assets.source.country_vehicles.build_motorized --check

The shared vehicle packager owns entity bindings. Renders are disposable.
"""

import argparse
import hashlib
import json
import math
from pathlib import Path
import random
import sys
import tempfile
from types import SimpleNamespace

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
SOURCE = Path(__file__).parent
STAGE = Path(tempfile.gettempdir()) / "adiscord-country-apc"
DEST = ROOT / "gfx/models/units/ADISCORD_country_vehicles"
PREVIEWS = ROOT / "docs/development/previews/country-apc"
REPORT = ROOT / "docs/development/model-verification/country_apc.json"
TAGS = ("VAL", "STP", "STS", "NAM")
CLIPS = ("idle", "move", "attack")
PAINTS = {
    "VAL": ((77, 94, 112), (39, 49, 61), (185, 194, 199)),
    "STP": ((91, 43, 49), (44, 32, 35), (161, 132, 76)),
    "STS": ((88, 96, 64), (44, 52, 37), (188, 184, 150)),
    "NAM": ((53, 102, 111), (29, 56, 63), (216, 164, 66)),
}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_changed(path, data):
    if not path.is_file() or path.read_bytes() != data:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)


def native_files(name):
    return [f"{name}.mesh", *[f"{name}_{clip}.anim" for clip in CLIPS],
            *[f"{name}_{channel}.dds" for channel in ("diffuse", "normal", "specular")]]


def prepare():
    from PIL import Image, ImageDraw
    from tools.assets.source.build_shl_palace import dds_bytes

    for tag, (base, dark, accent) in PAINTS.items():
        palette = [base, dark, (23, 25, 25), (105, 113, 113), accent,
                   (34, 63, 75), accent, (15, 20, 21), base,
                   tuple(min(255, c + 18) for c in base), (140, 35, 27),
                   (99, 77, 50), (55, 57, 52), (207, 199, 155), (75, 80, 60), base]
        atlas = Image.new("RGBA", (512, 512))
        rng = random.Random("apc_" + tag)
        for index, color in enumerate(palette):
            tile = Image.new("RGBA", (128, 128))
            pixels = []
            for y in range(128):
                for x in range(128):
                    noise = rng.gauss(0, 1.6)
                    pixels.append(tuple(max(0, min(255, round(c + noise))) for c in color) + (255,))
            tile.putdata(pixels)
            draw = ImageDraw.Draw(tile)
            if index in (0, 1, 9):
                draw.rectangle((4, 4, 123, 123), outline=dark, width=2)
                for x in (10, 63, 117):
                    for y in (10, 117):
                        draw.ellipse((x, y, x + 2, y + 2), fill=accent)
                for _ in range(25):
                    x, y = rng.randrange(128), rng.randrange(128)
                    draw.line((x, y, x + 3, y + 1), fill=dark)
            if index == 5:
                draw.polygon(((8, 108), (8, 27), (119, 6), (119, 24)), fill=(85, 115, 127))
            if index == 7:
                for y in range(8, 128, 10):
                    draw.line((0, y, 128, y), fill=(52, 58, 57), width=2)
            if index == 8:
                if tag == "VAL":
                    draw.polygon(((25, 94), (64, 24), (103, 94), (82, 94), (64, 60), (46, 94)), fill=accent)
                elif tag == "STP":
                    points = []
                    for i in range(10):
                        angle = -math.pi / 2 + i * math.pi / 5
                        radius = 43 if i % 2 == 0 else 19
                        points.append((64 + radius * math.cos(angle), 64 + radius * math.sin(angle)))
                    draw.polygon(points, fill=accent)
                elif tag == "NAM":
                    draw.polygon(((64, 21), (107, 64), (64, 107), (21, 64)), fill=accent)
                    draw.polygon(((64, 43), (85, 64), (64, 85), (43, 64)), fill=base)
                else:
                    draw.line((30, 30, 30, 96, 97, 96), fill=accent, width=12)
                    draw.line((97, 30, 58, 69), fill=accent, width=12)
            atlas.paste(tile, ((index % 4) * 128, (index // 4) * 128))
        specular = Image.new("RGBA", atlas.size, (0, 25, 0, 32))
        ImageDraw.Draw(specular).rectangle((128, 128, 255, 255), fill=(0, 80, 0, 95))
        for channel, texture in {
            "diffuse": atlas,
            "normal": Image.new("RGBA", atlas.size, (128, 128, 0, 128)),
            "specular": specular,
        }.items():
            write_changed(STAGE / f"{tag}_apc_{channel}.dds", dds_bytes(texture))


def wheel(model, side, y, index, radius):
    x, z = side * 1.38, radius + .05
    bone = model.bone(f"wheel_{side}_{index}", (x, y, z))
    model.rod((x - .23, y, z), (x + .23, y, z), radius, 2, bone, sides=20)
    outer = x + side * .245
    model.rod((outer, y, z), (outer + side * .07, y, z), radius * .57, 1, bone, sides=16)
    model.rod((outer + side * .075, y, z), (outer + side * .13, y, z), radius * .24, 3, bone)
    for i in range(20):
        angle = i * math.tau / 20
        rotation = Matrix.Rotation(angle, 3, "X")
        center = Vector((x, y, z)) + rotation @ Vector((0, 0, radius))
        model.box(center, (.46, .14, .055), 12, bone, rotation)
    for i in range(6):
        angle = i * math.tau / 6
        model.rod((outer + side * .075, y + radius * .39 * math.sin(angle), z + radius * .39 * math.cos(angle)),
                  (outer + side * .105, y + radius * .39 * math.sin(angle), z + radius * .39 * math.cos(angle)),
                  .045, 3, bone, sides=6)
    return bone


def vehicle(tag):
    model = native.Model(f"{tag}_apc")
    body = model.bone("hull", (0, 0, 1.5))
    top = {"VAL": 2.04, "STP": 2.40, "STS": 2.14, "NAM": 2.22}[tag]
    front = -3.5 if tag != "STP" else -3.15
    rear = 3.25 if tag != "STP" else 2.9
    hull(model, [(0.65, 1.9, front + .55, rear - .25, .25),
                 (1.23, 2.62, front, rear, .30),
                 (top, 2.24, front + .95, rear - .20, .24)], 0, body)
    model.box((0, 0, .75), (1.6, 5.2, .30), 1)
    axles = (-2.15, -.72, .72, 2.15) if tag != "STP" else (-1.95, 0, 1.95)
    radius = .66 if tag != "STP" else .78
    model.wheels = [wheel(model, side, y, i, radius) for side in (-1, 1) for i, y in enumerate(axles)]
    for y in axles:
        model.rod((-1.40, y, radius), (1.40, y, radius), .12, 12)
    for side in (-1, 1):
        # Separate armour modules leave wheel travel visible below the shoulder.
        for y in (-1.6, -.45, .7, 1.85):
            model.box((side * 1.245, y, top - .37), (.12, 1.00, .53), 9, body)
        model.box((side * 1.43, .02, 1.58), (.30, rear - front - 1.0, .12), 1, body)
        model.box((side * 1.32, 1.95, top - .33), (.06, .62, .42), 8, body)
        window_z = top - .34
        window_y = front + .95 * (window_z - 1.23) / (top - 1.23) - .045
        slope = -math.atan(.95 / (top - 1.23))
        model.box((side * .68, window_y, window_z), (.62, .08, .26), 5, body,
                  Matrix.Rotation(slope, 3, "X"))
        model.rod((side * 1.08, front + .23, 1.38), (side * 1.08, front + .08, 1.38), .16, 1, body)
        model.rod((side * 1.08, front + .065, 1.38), (side * 1.08, front + .055, 1.38), .115, 13, body)
        model.box((side * 1.10, rear - .04, 1.44), (.18, .08, .14), 10, body)
        model.rod((side * 1.14, -.8, top + .01), (side * 1.14, .65, top + .01), .035, 3, body)
        model.box((side * 1.46, rear - .20, .82), (.31, .13, .70), 2)
    model.box((0, front + .16, 1.01), (2.7, .18, .18), 12, body)
    model.box((0, rear - .055, 1.53), (1.50, .12, .98), 1, body)
    model.box((0, rear + .015, 1.53), (1.35, .04, .84), 9, body)
    for x in (-.53, .53):
        model.box((x, rear + .06, 1.17), (.22, .10, .10), 3, body)
    for x in (-.60, .60):
        model.box((x, 1.55, top + .04), (.88, 1.0, .09), 1, body)
        model.rod((x - .18, 1.55, top + .13), (x + .18, 1.55, top + .13), .035, 3, body)
    for y in (-1.75, -1.55, -1.35, -1.15):
        model.box((.62, y, top + .045), (.70, .08, .04), 7, body)
    turret = model.bone("turret", (0, -.35, top), body)
    gun = model.bone("gun", (0, -.90, top + .45), turret)
    model.rod((0, -.35, top), (0, -.35, top + .17), .69, 1, turret, sides=16)
    if tag == "VAL":
        hull(model, [(top + .13, 1.25, -1.03, .29, .22),
                     (top + .58, .85, -.79, .12, .18)], 9, turret)
        model.box((.46, -.50, top + .49), (.23, .34, .27), 1, turret)
        model.box((.46, -.685, top + .49), (.16, .035, .16), 5, turret)
    elif tag == "STP":
        model.rod((0, -.35, top + .15), (0, -.35, top + .63), .60, 0, turret, end_radius=.43, sides=12)
        model.rod((0, -.35, top + .63), (0, -.35, top + .70), .46, 4, turret, sides=12)
        for side in (-1, 1):
            model.box((side * 1.27, .3, top - .05), (.08, 4.1, .085), 4, body)
    elif tag == "NAM":
        hull(model, [(top + .13, 1.35, -1.10, .45, .18),
                     (top + .65, .98, -.91, .30, .16)], 1, turret)
        model.box((.43, -.40, top + .76), (.34, .40, .35), 0, turret)
        model.box((.43, -.615, top + .77), (.25, .04, .20), 5, turret)
        model.box((0, -.3, top + .68), (.55, .70, .06), 9, turret)
        for side in (-1, 1):
            model.box((side * 1.31, .2, top - .54), (.05, 3.9, .11), 6, body)
            model.box((side * .84, 2.58, top + .15), (.43, .64, .26), 1, body)
            for y in (2.36, 2.49, 2.62, 2.75):
                model.box((side * .84, y, top + .29), (.36, .055, .035), 7, body)
            for index in range(3):
                y = -.12 + index * .17
                model.rod((side * .62, y, top + .36),
                          (side * .86, y - .14, top + .55), .075, 12, turret, sides=8)
        model.rod((.89, 1.12, top), (.89, 1.12, top + .85), .022, 3, body)
    else:
        model.box((0, -.35, top + .39), (.86, .96, .45), 1, turret)
        for side in (-1, 1):
            model.box((side * .54, -.4, top + .45), (.12, 1.04, .53), 0, turret,
                      Matrix.Rotation(side * .16, 3, "Y"))
        for side in (-1, 1):
            model.box((side * .73, 2.62, top + .22), (.56, .58, .38), 14, body)
            model.box((side * .73, 2.62, top + .42), (.09, .60, .04), 11, body)
    model.box((0, -.91, top + .44), (.30, .53, .26), 1, gun)
    model.rod((0, -1.10, top + .45), (0, -2.0, top + .45), .065, 12, gun)
    model.rod((0, -2.0, top + .45), (0, -2.13, top + .45), .09, 3, gun)
    model.rod((0, -2.14, top + .45), (0, -2.15, top + .45), .052, 7, gun)
    model.rod((-.87, 1.15, top), (-.87, 1.15, top + 1.15), .022, 3, body)
    model.locators = {
        "root": ((0, 0, 0), "vehicle_root"),
        "barrel": ((0, -2.16, top + .45), gun),
        "left_wheel": ((-1.4, 2.2, .15), "vehicle_root"),
        "right_wheel": ((1.4, 2.2, .15), "vehicle_root"),
    }
    return model


def animate(model, rig, clip):
    rig.animation_data_clear()
    for bone in rig.pose.bones:
        bone.matrix_basis = Matrix.Identity(4)
        bone.rotation_mode = "XYZ"
    scene = bpy.context.scene
    end = 61 if clip == "move" else 31
    scene.frame_start, scene.frame_end = 1, end
    scene.render.fps = 30
    for frame in range(1, end + 1):
        t = (frame - 1) / (end - 1)
        for name in model.wheels:
            rig.pose.bones[name].rotation_euler.x = math.tau * 2 * t if clip == "move" else 0
        rig.pose.bones["hull"].location.z = .025 * math.sin(math.tau * 2 * t) if clip == "move" else 0
        recoil = max(0, 1 - abs(t - .1) / .1) if clip == "attack" else 0
        rig.pose.bones["gun"].location.y = .15 * recoil
        for bone in rig.pose.bones:
            bone.keyframe_insert("location", frame=frame)
            bone.keyframe_insert("rotation_euler", frame=frame)
    scene.frame_set(1)
    bpy.context.view_layer.objects.active = rig
    pdx.export_animfile(str(STAGE / f"{model.name}_{clip}.anim"), frame_start=1, frame_end=end)
    rig.animation_data.action.name = f"{model.name}_{clip}"
    rig.animation_data.action.use_fake_user = True


def export(tag):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    name = f"{tag}_apc"
    material = pdx.create_shader(SimpleNamespace(
        shader=["PdxMeshAdvanced"], diff=[f"{name}_diffuse.dds"],
        n=[f"{name}_normal.dds"], spec=[f"{name}_specular.dds"],
    ), name, str(STAGE))
    model = vehicle(tag)
    obj, rig = model.object(material)
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    for empty in [o for o in bpy.context.scene.objects if o.type == "EMPTY"]:
        empty.select_set(True)
    bpy.context.view_layer.objects.active = obj
    path = STAGE / f"{name}.mesh"
    pdx.export_meshfile(str(path), exp_selected=True)
    tree = pdx_data.read_meshfile(str(path))
    for mesh in tree.findall("./object/*/mesh"):
        skin = mesh.find("skin")
        indices, weights = skin.attrib["ix"], skin.attrib["w"]
        assert all(weights[i:i + 4] == [1, 0, 0, 0] for i in range(0, len(weights), 4))
        skin.set("bones", [1])
        # All four matrix indices are dereferenced by the native shader.
        skin.set("ix", [indices[i - i % 4] for i in range(len(indices))])
        mesh.attrib["ta"] = [round(value, 5) for value in mesh.attrib["ta"]]
    pdx_data.write_meshfile(str(path), tree)
    for clip in CLIPS:
        animate(model, rig, clip)
    rig.animation_data.action = bpy.data.actions[f"{name}_idle"]
    bpy.context.scene.frame_set(1)
    native.preview_materials()
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.file.pack_all()
    bpy.ops.wm.save_as_mainfile(filepath=str(STAGE / f"{name}.blend"))


def verify(tag):
    name = f"{tag}_apc"
    path = STAGE / f"{name}.mesh"
    tree = pdx_data.read_meshfile(str(path))
    report = {"triangles": 0, "vertices": 0, "materials": 0}
    for shape in tree.find("object"):
        bones = list(shape.find("skeleton"))
        report["bones"] = len(bones)
        assert 0 < len(bones) <= 50
        for mesh in shape.findall("mesh"):
            data = pdx_data.PDXData(mesh)
            count = len(data.p) // 3
            assert 0 < count < 65536
            assert len(data.n) == count * 3 and len(data.u0) == count * 2
            assert len(data.ta) == count * 4
            assert all(math.isfinite(v) for v in data.p + data.n + data.u0 + data.ta)
            assert all(0 <= v <= 1 for v in data.u0)
            assert len(data.tri) % 3 == 0 and min(data.tri) >= 0 and max(data.tri) < count
            points = [Vector(data.p[i:i + 3]) for i in range(0, len(data.p), 3)]
            assert all((points[b] - points[a]).cross(points[c] - points[a]).length > 1e-9
                       for a, b, c in zip(data.tri[::3], data.tri[1::3], data.tri[2::3]))
            assert data.skin.bones == [1]
            assert len(data.skin.w) == len(data.skin.ix) == count * 4
            for i in range(count):
                assert data.skin.w[i * 4:i * 4 + 4] == [1, 0, 0, 0]
                assert all(0 <= b < len(bones) for b in data.skin.ix[i * 4:i * 4 + 4])
            assert data.material.shader == ["PdxMeshAdvanced"]
            for channel in ("diff", "n", "spec"):
                assert (STAGE / getattr(data.material, channel)[0]).read_bytes()[:4] == b"DDS "
            report["triangles"] += len(data.tri) // 3
            report["vertices"] += count
            report["materials"] += 1
    assert report["triangles"] < 16000 and report["materials"] == 1
    report["locators"] = [loc.tag for loc in tree.find("locator")]
    assert {"root", "barrel", "left_wheel", "right_wheel"} <= set(report["locators"])
    report["animations"] = {}
    for clip in CLIPS:
        bpy.ops.wm.read_factory_settings(use_empty=True)
        pdx.import_meshfile(str(path), join_materials=False)
        pdx.import_animfile(str(STAGE / f"{name}_{clip}.anim"))
        objects = [o for o in bpy.context.scene.objects if o.type == "MESH"]
        rig = next(o for o in bpy.context.scene.objects if o.type == "ARMATURE")
        end = bpy.context.scene.frame_end
        samples, poses = [], []
        for frame in sorted({1, 2, max(2, end // 10), max(2, end // 4), end // 2, end}):
            bpy.context.scene.frame_set(frame)
            graph = bpy.context.evaluated_depsgraph_get()
            points = [o.matrix_world @ v.co for o in objects for v in o.evaluated_get(graph).data.vertices]
            assert all(math.isfinite(c) for p in points for c in p)
            assert max(p.length for p in points) < 12
            samples.append(points)
            poses.append({bone.name: bone.matrix.copy() for bone in rig.pose.bones})
        motion = max((a - b).length for points in samples[1:] for a, b in zip(samples[0], points))
        loop_error = max((a - b).length for a, b in zip(samples[0], samples[-1]))
        assert loop_error < .001, (name, clip, loop_error)
        metrics = {"max_vertex_motion": motion, "loop_error": loop_error}
        if clip != "idle":
            assert motion > .10, (name, clip, motion)
            prefix = "wheel_" if clip == "move" else "gun"
            selected = [n for n in poses[0] if n.startswith(prefix)]
            for bone in selected:
                delta = max(abs(a - b) for pose in poses[1:]
                            for row0, row1 in zip(poses[0][bone], pose[bone]) for a, b in zip(row0, row1))
                assert delta > .10, (name, clip, bone, delta)
            metrics["moving_bones"] = selected
        report["animations"][clip] = metrics
    report["native_reimport"] = True
    report["rigid_skin_slots_validated"] = True
    report["hoi4_runtime_verified"] = False
    report["files"] = {f: digest(STAGE / f) for f in native_files(name)}
    report["blend_sha256"] = digest(STAGE / f"{name}.blend")
    return report


def render(tag):
    name = f"{tag}_apc"
    bpy.ops.wm.read_factory_settings(use_empty=True)
    pdx.import_meshfile(str(STAGE / f"{name}.mesh"), join_materials=False)
    native.preview_materials()
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.samples = 32
    scene.cycles.use_denoising = True
    scene.render.resolution_x, scene.render.resolution_y = 1100, 800
    scene.render.resolution_percentage = 100
    scene.world = bpy.data.worlds.new("APC studio")
    scene.world.use_nodes = True
    scene.world.node_tree.nodes["Background"].inputs[0].default_value = (.12, .15, .19, 1)
    scene.world.node_tree.nodes["Background"].inputs[1].default_value = .7
    scene.view_settings.view_transform = "AgX"
    target = Vector((0, 0, 1.35))
    bpy.ops.object.camera_add(location=(10, -13, 8))
    camera = bpy.context.object
    camera.rotation_euler = (target - camera.location).to_track_quat("-Z", "Y").to_euler()
    camera.data.type, camera.data.ortho_scale = "ORTHO", 9.5
    scene.camera = camera
    for location, power in (((-6, -10, 12), 2200), ((8, -3, 8), 1500), ((-5, 9, 10), 2800)):
        bpy.ops.object.light_add(type="AREA", location=location)
        lamp = bpy.context.object
        lamp.data.energy, lamp.data.size = power, 7
        lamp.rotation_euler = (target - lamp.location).to_track_quat("-Z", "Y").to_euler()
    scene.render.image_settings.file_format = "PNG"
    PREVIEWS.mkdir(parents=True, exist_ok=True)
    scene.render.filepath = str(PREVIEWS / f"{name}.png")
    bpy.ops.render.render(write_still=True)


def package(apply=False):
    report_path = STAGE / REPORT.name
    if not report_path.is_file():
        raise FileNotFoundError("Build and verify the APC package in Blender first")
    report = json.loads(report_path.read_text())
    assert report["generator_sha256"] == digest(Path(__file__)), "Rebuild after generator edits"
    files = {REPORT: report_path.read_bytes()}
    for tag in TAGS:
        name = f"{tag}_apc"
        row = report["models"][name]
        assert set(row["files"]) == set(native_files(name))
        for filename, expected in row["files"].items():
            assert digest(STAGE / filename) == expected
            files[DEST / filename] = (STAGE / filename).read_bytes()
        blend = STAGE / f"{name}.blend"
        assert digest(blend) == row["blend_sha256"]
        files[SOURCE / blend.name] = blend.read_bytes()
    changed = [str(path.relative_to(ROOT)) for path, data in files.items()
               if not path.is_file() or path.read_bytes() != data]
    if apply:
        for path, data in files.items():
            write_changed(path, data)
    print(json.dumps({"changed": changed, "applied": apply}, indent=2))
    return changed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_mutually_exclusive_group(required=True)
    for action in ("prepare", "build", "check", "apply"):
        actions.add_argument("--" + action, action="store_true")
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else None)
    if args.prepare:
        prepare()
    elif args.build:
        global bpy, bmesh, Matrix, Vector, pdx, pdx_data, native, hull
        import bpy
        import bmesh
        from mathutils import Matrix, Vector
        from tools.assets.source import build_country_cas as native
        from tools.assets.source.build_shl_palace import load_exporter
        from tools.assets.source.build_taran import hull
        pdx = load_exporter()
        from io_pdx_mesh import pdx_data
        native.bpy, native.bmesh, native.Matrix, native.Vector = bpy, bmesh, Matrix, Vector
        report = {"generator_sha256": digest(Path(__file__)), "models": {}}
        for tag in TAGS:
            export(tag)
            report["models"][f"{tag}_apc"] = verify(tag)
            render(tag)
        write_changed(STAGE / REPORT.name, (json.dumps(report, indent=2) + "\n").encode())
        print(json.dumps(report, indent=2), flush=True)
    elif package(args.apply) and args.check:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
