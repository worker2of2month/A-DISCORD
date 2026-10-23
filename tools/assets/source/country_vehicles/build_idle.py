"""Build shared ground-vehicle idle clips from the installed native skeletons.

Blender: --background --factory-startup --python this_file -- --build
Python: -B -m tools.assets.source.country_vehicles.build_idle --check / --apply
Full model builders call export_idle so rebuilding geometry retains this motion.
"""

import argparse
import hashlib
import json
import math
from pathlib import Path
import sys
import tempfile

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
SOURCE = Path(__file__).parent
DEST = ROOT / "gfx/models/units/ADISCORD_country_vehicles"
STAGE = Path(tempfile.gettempdir()) / "adiscord-vehicle-idle"
REPORT = ROOT / "docs/development/model-verification/vehicle_idle.json"
NAMES = ("VAL_apc", "STP_apc", "STS_apc", "NAM_apc",
         "VAL_tank", "NOD_tank", "STP_tank", "STS_taran", "NOD_apc")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_changed(path, data):
    if not path.is_file() or path.read_bytes() != data:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)


def export_idle(rig, name, path, pdx):
    import bpy
    from mathutils import Matrix

    rig.animation_data_clear()
    for bone in rig.pose.bones:
        bone.matrix_basis = Matrix.Identity(4)
        bone.rotation_mode = "XYZ"
    scene = bpy.context.scene
    # Different cycle lengths avoid lockstep motion in neighbouring formations.
    end = 241 + 15 * NAMES.index(name)
    scene.frame_start, scene.frame_end = 1, end
    scene.render.fps = 30
    scene.render.fps_base = 1
    for frame in range(1, end + 1):
        phase = math.tau * (frame - 1) / (end - 1)
        hull = rig.pose.bones["hull"]
        hull.location.z = .008 * math.sin(phase * 16)
        hull.rotation_euler.x = .0015 * math.sin(phase * 12)
        if "turret" in rig.pose.bones:
            rig.pose.bones["turret"].rotation_euler.z = math.radians(6) * math.sin(phase)
        # The fixed Taran mount elevates without traversing through its casemate.
        rig.pose.bones["gun"].rotation_euler.x = -.018 * (1 - math.cos(phase * 2))
        for bone in rig.pose.bones:
            bone.keyframe_insert("location", frame=frame)
            bone.keyframe_insert("rotation_euler", frame=frame)
    scene.frame_set(1)
    bpy.context.view_layer.objects.active = rig
    pdx.export_animfile(str(path), frame_start=1, frame_end=end)
    rig.animation_data.action.name = f"{name}_idle"
    rig.animation_data.action.use_fake_user = True


def verify(name, pdx):
    import bpy

    bpy.ops.wm.read_factory_settings(use_empty=True)
    pdx.import_meshfile(str(DEST / f"{name}.mesh"), join_materials=False)
    pdx.import_animfile(str(STAGE / f"{name}_idle.anim"))
    rig = next(o for o in bpy.context.scene.objects if o.type == "ARMATURE")
    objects = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    end = bpy.context.scene.frame_end
    frames = sorted({1, 2, end - 1, end} | {1 + (end - 1) * i // 32 for i in range(33)})
    samples, poses = [], []
    for frame in frames:
        bpy.context.scene.frame_set(frame)
        graph = bpy.context.evaluated_depsgraph_get()
        points = [o.matrix_world @ v.co for o in objects for v in o.evaluated_get(graph).data.vertices]
        assert all(math.isfinite(c) for p in points for c in p)
        assert max(p.length for p in points) < 20
        samples.append(points)
        poses.append({b.name: b.matrix.copy() for b in rig.pose.bones})
    motion = max((a - b).length for points in samples[1:] for a, b in zip(samples[0], points))
    seam = max((a - b).length for a, b in zip(samples[0], samples[-1]))
    velocity_seam = max(((b - a) - (d - c)).length
                        for a, b, c, d in zip(samples[0], samples[1], samples[-2], samples[-1]))
    bone_motion = {}
    for name_bone in poses[0]:
        bone_motion[name_bone] = max(abs(a - b) for pose in poses[1:]
                                     for row0, row1 in zip(poses[0][name_bone], pose[name_bone])
                                     for a, b in zip(row0, row1))
    fixed = [n for n in bone_motion if n.startswith(("wheel_", "track_")) or n == "vehicle_root"]
    assert len(fixed) > 1
    assert all(bone_motion[n] < .00001 for n in fixed), (name, bone_motion)
    assert bone_motion["gun"] > .02
    if "turret" in bone_motion:
        assert bone_motion["turret"] > .05
    assert .05 < motion < 1.5, (name, motion)
    assert seam < .001 and velocity_seam < .005, (name, seam, velocity_seam)
    return {"samples": len(frames), "frames": end, "fps": 30,
            "max_vertex_motion": motion, "loop_error": seam,
            "velocity_loop_error": velocity_seam, "bone_motion": bone_motion,
            "stationary_bones": fixed, "native_reimport": True,
            "hoi4_runtime_verified": False}


def build():
    import bpy
    from tools.assets.source.build_shl_palace import load_exporter
    from tools.assets.source.country_vehicles import build_motorized

    pdx = load_exporter()
    STAGE.mkdir(parents=True, exist_ok=True)
    report = {"generator_sha256": digest(Path(__file__)), "models": {}, "outputs": {}}
    apc_report = json.loads(build_motorized.REPORT.read_text())
    taran_path = ROOT / "docs/development/model-verification/STS_taran_verification.json"
    taran_report = json.loads(taran_path.read_text())
    for name in NAMES:
        bpy.ops.wm.read_factory_settings(use_empty=True)
        pdx.import_meshfile(str(DEST / f"{name}.mesh"), join_materials=False)
        rig = next(o for o in bpy.context.scene.objects if o.type == "ARMATURE")
        filename = f"{name}_idle.anim"
        export_idle(rig, name, STAGE / filename, pdx)
        metrics = verify(name, pdx)
        unchanged = [f"{name}.mesh", f"{name}_move.anim", f"{name}_attack.anim"]
        unchanged += [f"{name}_{channel}.dds" for channel in ("diffuse", "normal", "specular")]
        report["models"][name] = {
            "animation": metrics, "sha256": digest(STAGE / filename),
            "inputs": {f: digest(DEST / f) for f in unchanged},
        }
        report["outputs"][str((DEST / filename).relative_to(ROOT))] = filename
        if name.endswith("_apc"):
            # Preserve the existing editable geometry, materials and other actions.
            if digest(STAGE / filename) == digest(DEST / filename):
                write_changed(STAGE / f"{name}.blend", (SOURCE / f"{name}.blend").read_bytes())
            else:
                bpy.ops.wm.open_mainfile(filepath=str(SOURCE / f"{name}.blend"))
                rig = next(o for o in bpy.context.scene.objects if o.type == "ARMATURE")
                old_idle = bpy.data.actions.get(f"{name}_idle")
                if old_idle is not None:
                    bpy.data.actions.remove(old_idle)
                pdx.import_animfile(str(STAGE / filename))
                rig.animation_data.action.name = f"{name}_idle"
                rig.animation_data.action.use_fake_user = True
                bpy.context.preferences.filepaths.save_version = 0
                bpy.context.scene.frame_set(1)
                bpy.ops.wm.save_as_mainfile(filepath=str(STAGE / f"{name}.blend"))
            row = apc_report["models"][name]
            row["animations"]["idle"] = metrics
            row["files"][filename] = digest(STAGE / filename)
            row["blend_sha256"] = digest(STAGE / f"{name}.blend")
            report["outputs"][str((SOURCE / f"{name}.blend").relative_to(ROOT))] = f"{name}.blend"
        elif name == "STS_taran":
            taran_report["animations"]["idle"] = metrics
            taran_report["files"][filename] = digest(STAGE / filename)
        print(name, metrics["max_vertex_motion"], flush=True)
    apc_report["generator_sha256"] = digest(Path(build_motorized.__file__))
    apc_report["idle_generator_sha256"] = digest(Path(__file__))
    taran_report["generator_sha256"] = digest(SOURCE.parent / "build_taran.py")
    taran_report["idle_generator_sha256"] = digest(Path(__file__))
    for path, data in ((build_motorized.REPORT, apc_report), (taran_path, taran_report)):
        write_changed(STAGE / path.name, (json.dumps(data, indent=2) + "\n").encode())
        report["outputs"][str(path.relative_to(ROOT))] = path.name
    report["output_hashes"] = {path: digest(STAGE / staged) for path, staged in report["outputs"].items()}
    write_changed(STAGE / REPORT.name, (json.dumps(report, indent=2) + "\n").encode())


def package(apply=False):
    report = json.loads((STAGE / REPORT.name).read_text())
    assert report["generator_sha256"] == digest(Path(__file__)), "Rebuild after generator edits"
    for row in report["models"].values():
        for filename, expected in row["inputs"].items():
            assert digest(DEST / filename) == expected, f"Native input changed: {filename}"
    files = {REPORT: (STAGE / REPORT.name).read_bytes()}
    for relative, staged in report["outputs"].items():
        assert digest(STAGE / staged) == report["output_hashes"][relative]
        files[ROOT / relative] = (STAGE / staged).read_bytes()
    changed = [str(path.relative_to(ROOT)) for path, data in files.items()
               if not path.is_file() or path.read_bytes() != data]
    if apply:
        for path, data in files.items():
            write_changed(path, data)
    print(json.dumps({"changed": changed, "applied": apply}, indent=2))
    return changed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    for name in ("build", "check", "apply"):
        action.add_argument("--" + name, action="store_true")
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else None)
    if args.build:
        build()
    elif package(args.apply) and args.check:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
