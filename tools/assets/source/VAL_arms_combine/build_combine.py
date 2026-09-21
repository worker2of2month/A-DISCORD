"""Build and package the Kefreyt landmark; run --prepare before Blender --build.

Default packaging is a dry run. --apply changes only owned assets and marked
registry sections; --check verifies byte-for-byte reproducibility of packaging.
"""
import argparse
import hashlib
import json
import math
import random
import re
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent
MOD = ROOT.parents[3]
DEST = MOD / "gfx/models/buildings/VAL_arms_combine"
KEY = "ADISCORD_kefreyt_arms_combine"
START = "# BEGIN ADISCORD Kefreyt arms combine\n"
END = "# END ADISCORD Kefreyt arms combine\n"


def prepare():
    from PIL import Image
    sys.path.insert(0, str(ROOT.parent / "WRK_unity_tower"))
    from package_tower import mip_chain
    rng = random.Random(480)
    colors = [(66, 69, 65), (85, 91, 87), (110, 61, 38), (39, 46, 45),
              (190, 126, 44), (231, 131, 53), (39, 64, 67), (105, 105, 93)]
    diffuse = Image.new("RGBA", (512, 512))
    normal = Image.new("RGBA", (512, 512), (128, 128, 0, 128))
    specular = Image.new("RGBA", (512, 512), (0, 30, 0, 30))
    for y in range(512):
        for x in range(512):
            tile = (x // 128) + 4 * (y // 256)
            noise = rng.randrange(-9, 10)
            if tile in (1, 2):
                noise += -15 if x % 12 < 3 else 4
            if tile == 0 and (y % 48 < 2 or (x + (y // 48 % 2) * 32) % 64 < 2):
                noise -= 12
            if tile == 4 and (x + y) % 48 < 22:
                color = (35, 38, 35)
            else:
                color = colors[tile]
            diffuse.putpixel((x, y), tuple(max(0, min(255, c + noise)) for c in color) + (255,))
            if tile == 5:
                normal.putpixel((x, y), (128, 128, 180, 128))
    for name, image in (("diffuse", diffuse), ("normal", normal), ("specular", specular)):
        (ROOT / f"Combine_{name}.dds").write_bytes(mip_chain(image))


def build():
    import bpy
    import bmesh
    from mathutils import Vector
    sys.path.insert(0, str(ROOT.parent / "STP_regulars"))
    from export_verify import pdx, pdx_data, preview_gloss
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.context.preferences.filepaths.save_version = 0
    spec = SimpleNamespace(shader=["PdxMeshAdvancedSnow"], diff=["Combine_diffuse.dds"],
                           n=["Combine_normal.dds"], spec=["Combine_specular.dds"])
    material = pdx.create_shader(spec, "Combine", str(ROOT))
    preview_gloss(material)
    parts = []

    def finish(obj, name, tile):
        obj.name = name
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        obj.data.materials.clear()
        obj.data.materials.append(material)
        uv = obj.data.uv_layers.active or obj.data.uv_layers.new(name="UVMap")
        # Face-local mapping keeps all UVs inside the selected atlas tile.
        u0, v0 = (tile % 4) / 4, 1 - (tile // 4 + 1) / 2
        for face in obj.data.polygons:
            for index, loop in enumerate(face.loop_indices):
                angle = 2 * math.pi * index / len(face.loop_indices) + math.pi / 4
                uv.data[loop].uv = (u0 + .125 + .115 * math.cos(angle), v0 + .25 + .235 * math.sin(angle))
        parts.append(obj)
        return obj

    def box(name, xyz, size, tile=0):
        bpy.ops.mesh.primitive_cube_add(size=1, location=xyz)
        obj = bpy.context.object
        obj.dimensions = size
        return finish(obj, name, tile)

    def cylinder(name, xyz, radius, depth, tile=2, radius_top=None):
        bpy.ops.mesh.primitive_cone_add(vertices=12, radius1=radius,
                                       radius2=radius if radius_top is None else radius_top,
                                       depth=depth, location=xyz)
        return finish(bpy.context.object, name, tile)

    def beam(name, a, b, width, tile=2):
        a, b = Vector(a), Vector(b)
        obj = box(name, (a + b) / 2, (width, width, (b - a).length), tile)
        obj.rotation_euler = (b - a).to_track_quat("Z", "Y").to_euler()
        return obj

    box("Buried continuous foundation", (0, 0, -.8), (32, 22, 2.4), 0)
    box("Loading yard", (0, 0, .45), (31.7, 21.7, .1), 3)
    for x in (-10, -1):
        box("Assembly hall", (x, 1, 2.65), (7.5, 16, 4.3), 0)
        for y in (-5, -1, 3, 7):
            roof = box("Sloping roof", (x, y, 5.1), (7.7, 4.05, .24), 1)
            roof.rotation_euler.x = .20
            box("Roof clerestory", (x, y - 1.87, 5.13), (7.45, .1, .72), 6)
            for dx in (-2.8, 0, 2.8):
                box("Clerestory mullion", (x + dx, y - 1.95, 5.13), (.10, .13, .82), 1)
        for y in range(-6, 10, 2):
            for dx in (-3.8, 3.8):
                box("Wall pier", (x + dx, y, 2.65), (.18, .32, 4.5), 1)
                box("Factory window", (x + dx * 1.005, y + .75, 3.55), (.06, 1.15, .85), 5 if y % 4 == 0 else 6)
        for dx in (-1.85, 1.85):
            box("Loading bay", (x + dx, -7.04, 1.8), (2.75, .12, 2.6), 3)
            box("Bay warning lintel", (x + dx, -7.14, 3.2), (2.95, .14, .25), 4)
        box("Roof ventilation duct", (x, 1, 5.75), (.65, 11.4, .45), 1)
    box("Foundry building", (9, 5, 3.3), (10, 8, 5.6), 2)
    box("Foundry roof", (9, 5, 6.2), (10.3, 8.3, .35), 1)
    for x in (6.1, 10, 13.3):
        cylinder("Chimney footing", (x, 7, 6.9), 1.0, 1.2, 0)
        cylinder("Tapered smokestack", (x, 7, 10.4), .70, 8, 2, .47)
        for z in (7.3, 10.5, 13.3):
            cylinder("Stack reinforcement", (x, 7, z), .77 - (z - 7.3) * .028, .18, 1)
        cylinder("Dark chimney mouth", (x, 7, 14.42), .46, .025, 3)
    for x in (6, 9, 12):
        cylinder("Storage silo", (x, -.6, 2.6), 1.12, 4.2, 1)
        cylinder("Silo dome", (x, -.6, 4.95), 1.12, .5, 1, .75)
        beam("Feed pipe", (x, -.6, 4.5), (x, 3, 4.5), .23, 2)
    for y in (-8.5, -10):
        for dy in (-.25, .25):
            box("Rail", (0, y + dy, .57), (30, .07, .12), 1)
        for x in range(-14, 15):
            box("Rail sleeper", (x, y, .52), (.16, .9, .09), 2)
    for x in (-10, -5, 4, 9):
        box("Freight wagon", (x, -9.9, 1.05), (3.4, 1.03, .7), 2)
        box("Wagon load", (x, -9.9, 1.46), (2.9, .83, .25), 3)
    for x in (4, 13):
        for y in (-6.7, -3.4):
            box("Gantry column", (x, y, 3.3), (.35, .35, 5.6), 4)
        beam("Gantry brace", (x, -6.7, 1.5), (x, -3.4, 5.6), .18, 2)
    for y in (-6.7, -3.4):
        box("Gantry girder", (8.5, y, 6.2), (10.6, .42, .55), 4)
    box("Crane trolley", (8, -5, 6.3), (.8, 4.2, .4), 1)
    beam("Crane cable", (8, -5, 6), (8, -5, 2.7), .075, 3)
    for x in (6, 9, 12):
        box("Steel stock", (x, -5, .85), (1.7, 2.1, .7), 1)
    box("Service bridge", (-5.5, 5, 3.8), (1.8, 1.4, 1.25), 1)
    for x in (-14.3, 14.5):
        for y in (-6, 0, 6):
            box("Perimeter light", (x, y, 2.6), (.09, .09, 4.2), 1)
            box("Lamp", (x, y, 4.75), (.45, .24, .16), 5)
    bpy.ops.object.select_all(action="DESELECT")
    for obj in parts:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = parts[0]
    bpy.ops.object.join()
    obj = bpy.context.object
    bpy.context.scene.cursor.location = (0, 0, 0)
    bpy.ops.object.origin_set(type="ORIGIN_CURSOR")
    obj.name = KEY
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.triangulate(bm, faces=list(bm.faces))
    bm.to_mesh(obj.data)
    bm.free()
    mesh_path = ROOT / (KEY + ".mesh")
    pdx.export_meshfile(str(mesh_path), exp_selected=True, exp_locs=False)
    report = {"parts": [], "size": list(obj.dimensions)}
    for shape in pdx_data.read_meshfile(str(mesh_path)).find("object"):
        assert shape.find("skeleton") is None
        for mesh in shape.findall("mesh"):
            data = pdx_data.PDXData(mesh)
            count = len(data.p) // 3
            assert 0 < count < 65536 and len(data.n) == count * 3 and len(data.u0) == count * 2
            assert all(math.isfinite(v) for v in data.p + data.n + data.u0 + data.ta)
            assert len(data.tri) % 3 == 0 and min(data.tri) >= 0 and max(data.tri) < count
            points = [Vector(data.p[i:i + 3]) for i in range(0, len(data.p), 3)]
            assert all((points[b] - points[a]).cross(points[c] - points[a]).length > 1e-8
                       for a, b, c in zip(data.tri[::3], data.tri[1::3], data.tri[2::3]))
            assert data.material.shader == ["PdxMeshAdvancedSnow"]
            for channel in ("diff", "n", "spec"):
                assert (ROOT / getattr(data.material, channel)[0]).is_file()
            report["parts"].append({"vertices": count, "triangles": len(data.tri) // 3})
    bpy.data.objects.remove(obj, do_unlink=True)
    pdx.import_meshfile(str(mesh_path), join_materials=False)
    for mat in bpy.data.materials:
        if mat.use_nodes:
            preview_gloss(mat)
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.samples = 24
    scene.render.resolution_x, scene.render.resolution_y = 1400, 1000
    scene.render.resolution_percentage = 100
    scene.world = bpy.data.worlds.new("Combine studio")
    scene.world.color = (.22, .22, .22)
    target = Vector((0, 0, 3))
    bpy.ops.object.camera_add(location=(39, -53, 39))
    camera = bpy.context.object
    camera.rotation_euler = (target - camera.location).to_track_quat("-Z", "Y").to_euler()
    camera.data.type, camera.data.ortho_scale = "ORTHO", 49
    scene.camera = camera
    for location, power in [((10, -25, 45), 24000), ((-30, -5, 25), 17000), ((8, 30, 35), 26000)]:
        bpy.ops.object.light_add(type="AREA", location=location)
        light = bpy.context.object
        light.data.energy, light.data.size = power, 25
        light.rotation_euler = (target - light.location).to_track_quat("-Z", "Y").to_euler()
    bpy.ops.wm.save_as_mainfile(filepath=str(ROOT / "Kefreyt_arms_combine.blend"))
    scene.render.filepath = str(ROOT / "Combine_native_preview.png")
    bpy.ops.render.render(write_still=True)
    report["mesh_sha256"] = hashlib.sha256(mesh_path.read_bytes()).hexdigest()
    (ROOT / "build_report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report))


def owned_section(path, content):
    text = path.read_text(encoding="utf-8")
    text = re.sub(re.escape(START) + r".*?" + re.escape(END), "", text, flags=re.S)
    return (text.rstrip() + "\n\n" + START + content + END).encode("utf-8")


def package(apply=False):
    names = [KEY + ".mesh"] + [f"Combine_{kind}.dds" for kind in ("diffuse", "normal", "specular")]
    files = {DEST / name: (ROOT / name).read_bytes() for name in names}
    files[MOD / "gfx/entities/mapitems_custom.gfx"] = owned_section(MOD / "gfx/entities/mapitems_custom.gfx", f'''objectTypes = {{
    pdxmesh = {{
        name = "{KEY}_mesh"
        file = "gfx/models/buildings/VAL_arms_combine/{KEY}.mesh"
        scale = 1.0
        cull_distance = 1800.0
    }}
}}
''')
    files[MOD / "gfx/entities/mapitems_custom.asset"] = owned_section(MOD / "gfx/entities/mapitems_custom.asset", f'''entity = {{
    name = "{KEY}_entity"
    pdxmesh = "{KEY}_mesh"
    default_state = "idle"
    state = {{ name = "idle" }}
}}
''')
    files[MOD / "map/ambient_object.txt"] = owned_section(MOD / "map/ambient_object.txt", f'''type = {{
    type = "{KEY}_entity"
    use_animation = no
    always_visible = yes
    scale = 0.20
    object = {{
        name = "{KEY}"
        position = {{ 3718.2 11.1 913.5 }}
        rotation = {{ 0 0 0 }}
    }}
}}
''')
    changed = [str(path.relative_to(MOD)) for path, data in files.items()
               if not path.is_file() or path.read_bytes() != data]
    if apply:
        for path, data in files.items():
            if str(path.relative_to(MOD)) in changed:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
    print(json.dumps({"changed": changed, "applied": apply}))
    return changed


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for flag in ("prepare", "build", "apply", "check"):
        parser.add_argument("--" + flag, action="store_true")
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else None)
    if args.prepare:
        prepare()
    elif args.build:
        build()
    elif package(args.apply) and args.check:
        raise SystemExit(1)
