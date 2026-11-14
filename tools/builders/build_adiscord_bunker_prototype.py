"""Build an isolated bunker design study; no game files or bindings are written.

--check lists the development outputs. --apply builds the editable scene and
review renders. Procedural materials are for design review, not native shaders.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import random
import subprocess
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "tools/assets/source/buildings/bunkers"
PREVIEW = ROOT / "docs/development/previews/bunker_prototype"
REPORT = ROOT / "docs/development/model-verification/bunker_prototype.json"
BLENDER = Path("C:/Program Files/Blender Foundation/Blender 4.5/blender.exe")
VIEWS = {
    "front": (12, -18, 12),
    "opposite": (-15, -16, 10),
    "rear": (13, 18, 13),
    "map": (9, -13, 23),
    "top": (0, 0, 28),
}
RENDER_NAMES = (*VIEWS, "map_256", "map_128", "map_64", "destroyed_front", "destroyed_map", "destroyed_map_128")
SHEETS = ("review_angles", "review_small", "review_destroyed")


def shader(name, color, roughness=.9, grain=.05):
    import bpy

    material = bpy.data.materials.new(name)
    material.use_nodes = True
    nodes = material.node_tree.nodes
    links = material.node_tree.links
    principled = nodes.get("Principled BSDF")
    principled.inputs["Roughness"].default_value = roughness
    coord = nodes.new("ShaderNodeTexCoord")
    noise = nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 3.2
    noise.inputs["Detail"].default_value = 4
    links.new(coord.outputs["Object"], noise.inputs["Vector"])
    ramp = nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position = .18
    ramp.color_ramp.elements[0].color = tuple(c * .68 for c in color) + (1,)
    ramp.color_ramp.elements[1].position = .84
    ramp.color_ramp.elements[1].color = tuple(c * 1.13 for c in color) + (1,)
    links.new(noise.outputs["Fac"], ramp.inputs["Fac"])
    links.new(ramp.outputs["Color"], principled.inputs["Base Color"])
    if "concrete" in name.lower():
        geometry = nodes.new("ShaderNodeNewGeometry")
        separate = nodes.new("ShaderNodeSeparateXYZ")
        links.new(geometry.outputs["Position"], separate.inputs[0])
        grime = nodes.new("ShaderNodeMapRange")
        grime.inputs["From Min"].default_value = .05
        grime.inputs["From Max"].default_value = .85
        grime.inputs["To Min"].default_value = .55
        grime.inputs["To Max"].default_value = 1
        links.new(separate.outputs["Z"], grime.inputs["Value"])
        multiply = nodes.new("ShaderNodeMixRGB")
        multiply.blend_type = "MULTIPLY"
        multiply.inputs[0].default_value = 1
        links.new(ramp.outputs["Color"], multiply.inputs[1])
        links.new(grime.outputs["Result"], multiply.inputs[2])
        links.new(multiply.outputs[0], principled.inputs["Base Color"])
    pores = nodes.new("ShaderNodeTexNoise")
    pores.inputs["Scale"].default_value = 45
    pores.inputs["Detail"].default_value = 2
    links.new(coord.outputs["Object"], pores.inputs["Vector"])
    bump = nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = .28
    bump.inputs["Distance"].default_value = grain
    links.new(pores.outputs["Fac"], bump.inputs["Height"])
    links.new(bump.outputs["Normal"], principled.inputs["Normal"])
    return material


def mesh(name, vertices, faces, material):
    import bpy

    data = bpy.data.meshes.new(name)
    data.from_pydata(vertices, [], faces)
    data.update()
    obj = bpy.data.objects.new(name, data)
    bpy.context.collection.objects.link(obj)
    if material:
        data.materials.append(material)
    return obj


def box(name, center, size, material, bevel=0):
    import bpy

    bpy.ops.mesh.primitive_cube_add(size=1, location=center)
    obj = bpy.context.object
    obj.name = name
    obj.dimensions = size
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.data.materials.append(material)
    if bevel:
        modifier = obj.modifiers.new("Cast edge", "BEVEL")
        modifier.width = min(bevel, min(size) * .45)
        modifier.segments = 1
        bpy.ops.object.modifier_apply(modifier=modifier.name)
    return obj


def ring(width, depth, cut):
    x, y = width / 2, depth / 2
    return [(-x + cut, -y), (x - cut, -y), (x, -y + cut),
            (x, y - cut), (x - cut, y), (-x + cut, y),
            (-x, y - cut), (-x, -y + cut)]


def block(name, center, layers, material):
    vertices = []
    for z, width, depth, cut in layers:
        vertices.extend((x + center[0], y + center[1], z) for x, y in ring(width, depth, cut))
    faces = [tuple(reversed(range(8)))]
    for layer in range(len(layers) - 1):
        for index in range(8):
            a = layer * 8 + index
            b = layer * 8 + (index + 1) % 8
            faces.append((a, b, b + 8, a + 8))
    faces.append(tuple(range(len(vertices) - 8, len(vertices))))
    return mesh(name, vertices, faces, material)


def subtract(obj, cutter):
    import bpy

    bpy.context.view_layer.objects.active = obj
    modifier = obj.modifiers.new("Recess", "BOOLEAN")
    modifier.operation = "DIFFERENCE"
    modifier.solver = "EXACT"
    modifier.object = cutter
    bpy.ops.object.modifier_apply(modifier=modifier.name)
    bpy.data.objects.remove(cutter, do_unlink=True)


def embrasure(obj, name, x, y, z, width, material, side=False, scale=1):
    # The mouth flares outward; the recessed inner plate remains in real shadow.
    vertices = []
    for depth, half_width, half_height in ((-.18 * scale, width / 2, .34 * scale),
                                          (.50 * scale, width * .39, .21 * scale)):
        for u, v in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
            px, py = u * half_width, depth
            if side:
                px, py = -py, px
            vertices.append((x + px, y + py, z + v * half_height))
    faces = [(0, 1, 2, 3), (7, 6, 5, 4), (4, 5, 1, 0),
             (5, 6, 2, 1), (6, 7, 3, 2), (7, 4, 0, 3)]
    subtract(obj, mesh(name + " cutting volume", vertices, faces, None))
    if side:
        box(name + " inner shadow", (x - .48 * scale, y, z), (.025, width * .80, .43 * scale), material)
    else:
        box(name + " inner shadow", (x, y + .48 * scale, z), (width * .80, .025, .43 * scale), material)


def bunker(prefix, cx, cy, scale, materials):
    concrete, roof, dark, steel, soil, timber = materials
    z = .10
    block(prefix + " buried footing", (cx, cy),
          [(-.08, 6.25 * scale, 4.35 * scale, .72 * scale),
           (.15, 6.25 * scale, 4.35 * scale, .72 * scale)], concrete)
    body = block(prefix + " walls", (cx, cy),
                 [(z, 6.2 * scale, 4.3 * scale, .72 * scale),
                  (z + 2.05 * scale, 5.95 * scale, 4.1 * scale, .70 * scale)], concrete)
    embrasure(body, prefix + " forward embrasure", cx, cy - 2.1 * scale,
              z + 1.50 * scale, 3.8 * scale, dark, scale=scale)
    embrasure(body, prefix + " flank embrasure", cx + 3.02 * scale, cy,
              z + 1.50 * scale, 1.7 * scale, dark, side=True, scale=scale)
    cap = block(prefix + " roof", (cx, cy),
                [(z + 2.01 * scale, 6.20 * scale, 4.35 * scale, .74 * scale),
                 (z + 2.20 * scale, 6.48 * scale, 4.60 * scale, .81 * scale),
                 (z + 2.72 * scale, 6.08 * scale, 4.20 * scale, .77 * scale)], roof)
    door = box(prefix + " rear entry cutter", (cx, cy + 2.08 * scale, .80 * scale),
               (.95 * scale, .95 * scale, 1.45 * scale), dark)
    subtract(body, door)
    box(prefix + " recessed steel door", (cx, cy + 1.66 * scale, .74 * scale),
        (.77 * scale, .06, 1.32 * scale), steel, .025)
    box(prefix + " rear lintel", (cx, cy + 2.14 * scale, 1.58 * scale),
        (1.2 * scale, .30 * scale, .19 * scale), concrete, .035)
    box(prefix + " roof service hatch", (cx - 1.35 * scale, cy + .85 * scale, z + 2.75 * scale),
        (.66 * scale, .72 * scale, .09 * scale), steel, .04)
    box(prefix + " protected vent", (cx + 1.60 * scale, cy + 1.25 * scale, z + 2.79 * scale),
        (.45 * scale, .44 * scale, .14 * scale), concrete, .04)
    return body, cap


def strip(name, points, widths, heights, material, reverse=False):
    from mathutils import Vector

    vertices = []
    for index, point in enumerate(points):
        previous = Vector(points[max(0, index - 1)])
        following = Vector(points[min(len(points) - 1, index + 1)])
        direction = (following - previous).normalized()
        normal = Vector((-direction.y, direction.x))
        for width, height in zip(widths, heights):
            position = Vector(point) + normal * width
            vertices.append((position.x, position.y, height))
    count = len(widths)
    faces = []
    for index in range(len(points) - 1):
        for offset in range(count - 1):
            a = index * count + offset
            faces.append((a, a + count, a + count + 1, a + 1))
    if reverse:
        faces = [tuple(reversed(face)) for face in faces]
    return mesh(name, vertices, faces, material)


def beam(name, a, b, width, height, material):
    from mathutils import Vector

    start, end = Vector(a), Vector(b)
    obj = box(name, (start + end) * .5, ((end - start).length, width, height), material)
    obj.rotation_euler.z = math.atan2(end.y - start.y, end.x - start.x)
    return obj


def build_geometry(materials):
    import bpy
    from mathutils import Vector

    concrete, roof, dark, steel, soil, timber = materials
    body, cap = bunker("Main casemate", -1.65, -.85, 1, materials)
    bunker("Flanking pillbox", 4.25, 1.35, .80, materials)
    path = [(-1.65, 1.20), (-1.65, 2.8), (.1, 4.1), (4.25, 4.1), (4.25, 2.99)]
    strip("Trench earthen banks", path,
          [-1.1, -.65, -.48, -.48, .48, .48, .65, 1.1],
          [-.035, .60, .62, .07, .07, .62, .60, -.035], soil)
    strip("Trench dark floor", path, [-.48, .48], [.075, .075], dark)
    for side in (-1, 1):
        strip("Trench timber revetment", path, [.48 * side, .48 * side], [.10, .56], timber,
              reverse=side == -1)
    for start, end in zip(path, path[1:]):
        a, b = Vector(start), Vector(end)
        direction = (b - a).normalized()
        normal = Vector((-direction.y, direction.x))
        for i in range(1, max(2, int((b - a).length / .62))):
            t = i / max(2, int((b - a).length / .62))
            position = a.lerp(b, t)
            for side in (-1, 1):
                xy = position + normal * .46 * side
                box("Trench retaining post", (*xy, .36), (.10, .10, .59), timber)
    # Short shoulder berms leave the firing face and both entrances unobstructed.
    strip("Main left shoulder earth", [(-4.50, -1.7), (-4.45, .6), (-3.85, 1.3), (-2.5, 1.65)],
          [-.6, 0, .7], [-.04, .48, -.04], soil)
    strip("Main right shoulder earth", [(1.2, -.85), (1.25, .7), (.6, 1.45), (-.8, 1.6)],
          [-.5, 0, .65], [-.04, .43, -.04], soil)
    rng = random.Random(821)
    for index, x in enumerate((-4.5, -2.7, -.9, .9, 2.7, 4.5)):
        y = -4.3 - (.28 if index % 2 else 0)
        tooth = block("Dragon tooth %02d" % index, (x, y),
                      [(.015, 1.12, 1.0, .05), (.12, 1.0, .88, .05),
                       (.93 + rng.uniform(-.08, .06), .38, .31, .025)], concrete)
        tooth.rotation_euler.z = rng.uniform(-.12, .12)
    for offset in (-.63, .77):
        beam("Roof casting joint", (-4.0, -.85 + offset, 2.824), (.6, -.85 + offset, 2.824),
             .018, .006, concrete)
    return body, cap


def prism(name, outline, bottom, top, material):
    count = len(outline)
    vertices = [(x, y, z) for z in (bottom, top) for x, y in outline]
    faces = [tuple(reversed(range(count))), tuple(range(count, count * 2))]
    for i in range(count):
        following = (i + 1) % count
        faces.append((i, following, following + count, i + count))
    return mesh(name, vertices, faces, material)


def make_ruin(body, roof, materials):
    import bpy

    concrete, top, dark, steel, soil, timber = materials
    cutter = prism("Broken roof volume",
                   [(-1.50, -3.9), (2.4, -3.9), (2.4, -.6), (1.25, -.6),
                    (1.0, -.28), (.55, -.42), (.25, -.15), (-.1, -.38),
                    (-.55, -.28), (-.45, -.82), (-.90, -1.02), (-.75, -1.45),
                    (-1.35, -1.7), (-1.15, -2.2), (-1.65, -2.5)], 1.8, 4.0, dark)
    subtract(roof, cutter)
    cutter = box("Exposed interior volume", (-1.65, -.85, 1.43), (4.75, 2.90, 2.42), dark)
    subtract(body, cutter)
    cutter = box("Breached wall cutter", (.45, -2.4, 1.8), (2.9, 2.4, 2.3), dark)
    cutter.rotation_euler.z = -.27
    subtract(body, cutter)
    for obj in list(bpy.data.objects):
        if obj.name.startswith("Roof casting joint") or obj.name.startswith("Main casemate forward embrasure inner"):
            bpy.data.objects.remove(obj, do_unlink=True)
    box("Exposed interior floor", (-1.65, -.85, .17), (4.9, 3.2, .16), dark)
    slab = prism("Fallen roof slab", [(-1.3, -.7), (-.4, -.95), (.15, -.70),
                                      (1.3, -.65), (1.45, .2), (.75, .8),
                                      (.1, .68), (-.45, .92), (-1.2, .5)], -.25, .25, top)
    slab.location = (-.15, -2.7, .66)
    slab.rotation_euler = (.17, .24, -.22)
    rng = random.Random(1944)
    for index in range(20):
        x = rng.uniform(-1.4, 1.9)
        y = rng.uniform(-3.7, -1.2)
        size = rng.uniform(.16, .50)
        chunk = box("Concrete debris %02d" % index, (x, y, .1 + size * .35),
                    (size * 1.3, size, size * .7), concrete, size * .12)
        chunk.rotation_euler = (rng.uniform(-.4, .4), rng.uniform(-.4, .4), rng.uniform(0, math.tau))


def statistics():
    import bpy

    objects = [obj for obj in bpy.data.objects if obj.type == "MESH" and not obj.name.startswith("REVIEW")]
    triangles = 0
    for obj in objects:
        assert not obj.data.validate(verbose=False, clean_customdata=False), obj.name
        assert all(math.isfinite(value) for vertex in obj.data.vertices for value in vertex.co), obj.name
        obj.data.calc_loop_triangles()
        for triangle in obj.data.loop_triangles:
            a, b, c = (obj.data.vertices[i].co for i in triangle.vertices)
            assert (b - a).cross(c - a).length > 1e-9, obj.name
        triangles += len(obj.data.loop_triangles)
    return {"objects": len(objects), "triangles": triangles, "geometry_validated": True}


def scene_setup():
    import bpy
    from mathutils import Vector

    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.samples = 24
    scene.cycles.use_denoising = True
    scene.render.resolution_x = 1200
    scene.render.resolution_y = 960
    scene.render.resolution_percentage = 100
    scene.view_settings.view_transform = "AgX"
    scene.world = bpy.data.worlds.new("Review daylight")
    scene.world.use_nodes = True
    scene.world.node_tree.nodes["Background"].inputs[0].default_value = (.48, .55, .66, 1)
    scene.world.node_tree.nodes["Background"].inputs[1].default_value = .45
    ground = shader("Review ground - excluded from model", (.11, .14, .10), grain=.06)
    box("REVIEW ground", (0, 0, -.12), (200, 200, .2), ground)
    for name, location, power, size in (
        ("Key daylight", (-7, -10, 16), 2400, 9),
        ("Sky fill", (8, 1, 12), 1100, 10),
    ):
        bpy.ops.object.light_add(type="AREA", location=location)
        lamp = bpy.context.object
        lamp.name = name
        lamp.data.energy = power
        lamp.data.shape = "DISK"
        lamp.data.size = size
        lamp.rotation_euler = (Vector((0, 0, 0)) - lamp.location).to_track_quat("-Z", "Y").to_euler()
    bpy.ops.object.camera_add()
    camera = bpy.context.object
    camera.name = "Review orthographic camera"
    camera.data.type = "ORTHO"
    camera.data.ortho_scale = 17.2
    scene.camera = camera


def set_view(position, resolution=None):
    import bpy
    from mathutils import Vector

    scene = bpy.context.scene
    camera = scene.camera
    target = Vector((.65, -.10, .45))
    camera.location = target + Vector(position)
    camera.rotation_euler = (target - camera.location).to_track_quat("-Z", "Y").to_euler()
    scene.render.resolution_x, scene.render.resolution_y = resolution or (1200, 960)


def render(name, position, resolution=None):
    import bpy

    set_view(position, resolution)
    bpy.context.scene.render.filepath = str(PREVIEW / (name + ".png"))
    bpy.ops.render.render(write_still=True)


def build():
    import bpy

    bpy.ops.wm.read_factory_settings(use_empty=True)
    generator_hash = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    materials = [shader("Weathered cast concrete", (.27, .28, .24)),
                 shader("Sloped concrete roof", (.30, .31, .27)),
                 shader("Deep recesses", (.018, .021, .018)),
                 shader("Dull olive steel", (.075, .095, .071), roughness=.72, grain=.01),
                 shader("Packed earth", (.17, .115, .065), grain=.12),
                 shader("Trench retaining timber", (.085, .060, .036), grain=.07)]
    body, roof = build_geometry(materials)
    intact_stats = statistics()
    scene_setup()
    for folder in (SOURCE, PREVIEW, REPORT.parent):
        folder.mkdir(parents=True, exist_ok=True)
    bpy.context.preferences.filepaths.save_version = 0
    for name, position in VIEWS.items():
        render(name, position)
    for pixels in (256, 128, 64):
        render("map_%d" % pixels, VIEWS["map"], (pixels, pixels))
    set_view(VIEWS["front"])
    bpy.ops.wm.save_as_mainfile(filepath=str(SOURCE / "bunker_prototype.blend"))
    make_ruin(body, roof, materials)
    ruined_stats = statistics()
    render("destroyed_front", VIEWS["front"])
    render("destroyed_map", VIEWS["map"])
    render("destroyed_map_128", VIEWS["map"], (128, 128))
    set_view(VIEWS["front"])
    bpy.ops.wm.save_as_mainfile(filepath=str(SOURCE / "bunker_destroyed_prototype.blend"))
    report = {
        "generator": Path(__file__).relative_to(ROOT).as_posix(),
        "generator_sha256": generator_hash,
        "purpose": "Design prototype only; no runtime installation",
        "native_export_verified": False,
        "hoi4_runtime_verified": False,
        "materials": "Procedural Blender materials; native texture baking pending approval",
        "intact": intact_stats,
        "destroyed": ruined_stats,
        "small_renders": "Direct orthographic renders at 256, 128 and 64 pixels; not game screenshots",
        "sources": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in SOURCE.glob("*.blend")},
    }
    REPORT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


def review_sheets():
    from PIL import Image, ImageDraw, ImageFont

    font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 22)
    small_font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 17)
    background = (28, 33, 32)
    ink = (224, 226, 217)
    gallery = Image.new("RGB", (1280, 1126), background)
    draw = ImageDraw.Draw(gallery)
    draw.text((22, 15), "A-DISCORD / ПРОТОТИП УКРЕПЛЁННОГО УЗЛА", font=font, fill=ink)
    for index, (name, label) in enumerate((("front", "01 / Спереди"), ("opposite", "02 / С другого фланга"),
                                           ("rear", "03 / С тыла"), ("top", "04 / Сверху"))):
        x, y = (index % 2) * 640, 53 + (index // 2) * 534
        picture = Image.open(PREVIEW / (name + ".png")).convert("RGB")
        gallery.paste(picture.resize((640, 512), Image.Resampling.LANCZOS), (x, y + 22))
        draw.text((x + 14, y), label, font=small_font, fill=ink)
    gallery.save(PREVIEW / "review_angles.png")

    small = Image.new("RGB", (680, 390), background)
    draw = ImageDraw.Draw(small)
    draw.text((20, 15), "МЕЛКИЙ МАСШТАБ / без увеличения", font=font, fill=ink)
    for pixels, x in ((256, 18), (128, 302), (64, 476)):
        draw.text((x, 59), "%d x %d px" % (pixels, pixels), font=small_font, fill=ink)
        picture = Image.open(PREVIEW / ("map_%d.png" % pixels)).convert("RGB")
        small.paste(picture, (x, 87 + (256 - pixels) // 2))
    draw.text((20, 361), "Ортографические рендеры Blender, не кадры из игры.", font=small_font, fill=ink)
    small.save(PREVIEW / "review_small.png")

    ruined = Image.new("RGB", (1280, 590), background)
    draw = ImageDraw.Draw(ruined)
    draw.text((22, 15), "РАЗРУШЕННОЕ СОСТОЯНИЕ / ПРОТОТИП", font=font, fill=ink)
    for index, name in enumerate(("destroyed_front", "destroyed_map")):
        picture = Image.open(PREVIEW / (name + ".png")).convert("RGB")
        ruined.paste(picture.resize((640, 512), Image.Resampling.LANCZOS), (index * 640, 62))
    ruined.save(PREVIEW / "review_destroyed.png")
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    report["previews"] = {name + ".png": hashlib.sha256((PREVIEW / (name + ".png")).read_bytes()).hexdigest()
                          for name in (*RENDER_NAMES, *SHEETS)}
    REPORT.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def stale_outputs():
    if not REPORT.exists():
        return [REPORT.relative_to(ROOT).as_posix()]
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    changed = []
    if report.get("generator_sha256") != hashlib.sha256(Path(__file__).read_bytes()).hexdigest():
        changed.append("generator fingerprint")
    for folder, expected, names in (
        (SOURCE, report.get("sources", {}), ("bunker_prototype.blend", "bunker_destroyed_prototype.blend")),
        (PREVIEW, report.get("previews", {}), tuple(name + ".png" for name in (*RENDER_NAMES, *SHEETS))),
    ):
        for name in names:
            path = folder / name
            if not path.exists() or hashlib.sha256(path.read_bytes()).hexdigest() != expected.get(name):
                changed.append(path.relative_to(ROOT).as_posix())
    return changed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--check", action="store_true")
    modes.add_argument("--apply", action="store_true")
    modes.add_argument("--build", action="store_true", help=argparse.SUPPRESS)
    arguments = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    args = parser.parse_args(arguments)
    if args.build:
        build()
    elif args.apply:
        if not stale_outputs():
            print("Prototype is current; no files changed.")
            return
        environment = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
        subprocess.run([str(BLENDER), "--background", "--factory-startup", "--python", str(Path(__file__)), "--", "--build"],
                       cwd=ROOT, env=environment, check=True)
        review_sheets()
    else:
        print("Development-only outputs; no runtime paths:")
        for path in (SOURCE / "bunker_prototype.blend", SOURCE / "bunker_destroyed_prototype.blend", PREVIEW, REPORT):
            print(path.relative_to(ROOT))
        changed = stale_outputs()
        if changed:
            print("Needs rebuilding:\n" + "\n".join(changed))
        else:
            print("Prototype source hashes match; native game verification is pending.")


if __name__ == "__main__":
    main()
