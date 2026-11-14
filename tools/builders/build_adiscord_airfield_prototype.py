"""Build an airfield design study in development paths, without game bindings.

--check is read-only. --apply builds editable scenes and review sheets, or does
nothing when their recorded hashes match. Materials are provisional Blender
shaders; the native game uses separate textures and damage-state particles.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.builders import build_adiscord_bunker_prototype as kit

SOURCE = ROOT / "tools/assets/source/buildings/airfield"
PREVIEW = ROOT / "docs/development/previews/airfield_prototype"
REPORT = ROOT / "docs/development/model-verification/airfield_prototype.json"
VIEWS = {"front": (11, -18, 15), "opposite": (-13, -17, 12),
         "rear": (12, 18, 15), "map": (8, -12, 24), "top": (0, 0, 30)}
RENDERS = (*VIEWS, "map_256", "map_128", "map_64", "damaged_front", "damaged_map")
SHEETS = ("review_angles", "review_small", "review_damaged")
INPUTS = (Path(__file__), Path(kit.__file__))


def fingerprints():
    return {path.relative_to(ROOT).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest() for path in INPUTS}


def cylinder(name, position, radius, depth, material, vertices=12):
    import bpy

    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices, radius=radius, depth=depth, location=position)
    obj = bpy.context.object
    obj.name = name
    obj.data.materials.append(material)
    return obj


def arch_roof(name, x, y, width, depth, material, start=0, end=12):
    import bpy

    vertices = []
    for side in (-1, 1):
        for i in range(start, end + 1):
            theta = math.pi * i / 12
            vertices.append((x + width / 2 * math.cos(theta), y + side * depth / 2,
                             1.4 + 1.8 * math.sin(theta)))
    count = end - start + 1
    faces = [(i, i + count, i + count + 1, i + 1) for i in range(count - 1)]
    obj = kit.mesh(name, vertices, faces, material)
    bpy.context.view_layer.objects.active = obj
    modifier = obj.modifiers.new("Roof thickness", "SOLIDIFY")
    modifier.thickness = .09
    bpy.ops.object.modifier_apply(modifier=modifier.name)
    return obj


def arch_end(name, x, y, width, material):
    points = [(x + width / 2, y, .06), (x + width / 2, y, 1.4)]
    for i in range(1, 13):
        theta = math.pi * i / 12
        points.append((x + width / 2 * math.cos(theta), y, 1.4 + 1.8 * math.sin(theta)))
    points.append((x - width / 2, y, .06))
    return kit.mesh(name, points, [tuple(reversed(range(len(points))))], material)


def front_gable(name, x, y, material):
    lower = (3 * math.cos(math.pi / 12), 1.4 + 1.8 * math.sin(math.pi / 12))
    upper = (3 * math.cos(math.pi / 6), 1.4 + 1.8 * math.sin(math.pi / 6))
    ratio = (2.18 - lower[1]) / (upper[1] - lower[1])
    edge = lower[0] + ratio * (upper[0] - lower[0])
    points = [(x + edge, y, 2.18)]
    points.extend((x + 3 * math.cos(math.pi * i / 12), y, 1.4 + 1.8 * math.sin(math.pi * i / 12))
                  for i in range(2, 11))
    points.append((x - edge, y, 2.18))
    return kit.mesh(name, points, [tuple(range(len(points)))], material)


def thicken(obj, width):
    import bpy

    bpy.context.view_layer.objects.active = obj
    modifier = obj.modifiers.new("Sheet thickness", "SOLIDIFY")
    modifier.thickness = width
    bpy.ops.object.modifier_apply(modifier=modifier.name)


def hangar(label, x, y, materials, open_doors=False):
    masonry, metal, glass, asphalt, apron, white, yellow, shadow, steel = materials
    width, depth = 6.0, 4.8
    roof = arch_roof(label + " curved roof", x, y, width, depth, metal)
    for side in (-1, 1):
        kit.box(label + " side wall", (x + side * 2.9, y, .73), (.24, depth, 1.46), masonry)
        kit.box(label + " front portal", (x + side * 2.84, y - depth / 2, 1.09),
                (.32, .30, 2.18), masonry, .03)
    arch_end(label + " rear gable", x, y + depth / 2, width, masonry)
    gable = front_gable(label + " front gable", x, y - depth / 2, metal)
    thicken(gable, .08)
    kit.box(label + " interior floor", (x, y, .045), (5.7, depth, .06), shadow)
    if open_doors:
        for side in (-1, 1):
            kit.box(label + " open sliding door", (x + side * 3.07, y - depth / 2 - .1, 1.08),
                    (.65, .13, 2.1), steel, .02)
    else:
        for side in (-1, 1):
            kit.box(label + " closed sliding door", (x + side * 1.36, y - depth / 2 - .08, 1.10),
                    (2.69, .13, 2.16), steel, .025)
        for offset in (-2.0, -.7, .7, 2.0):
            kit.box(label + " door rib", (x + offset, y - depth / 2 - .16, 1.10), (.045, .045, 2.08), masonry)
    for offset in (-1.65, -.55, .55, 1.65):
        for i in range(12):
            theta_a, theta_b = math.pi * i / 12, math.pi * (i + 1) / 12
            a = (x + 3.015 * math.cos(theta_a), y + offset, 1.405 + 1.81 * math.sin(theta_a))
            b = (x + 3.015 * math.cos(theta_b), y + offset, 1.405 + 1.81 * math.sin(theta_b))
            # A narrow roof strip follows the arch without adding tiny corrugation geometry.
            kit.mesh(label + " roof seam", [(a[0], a[1] - .018, a[2]), (b[0], b[1] - .018, b[2]),
                                           (b[0], b[1] + .018, b[2]), (a[0], a[1] + .018, a[2])],
                     [(0, 1, 2, 3)], steel)
    return roof


def aircraft(label, x, y, material, glass, dark):
    import bpy

    vertices = []
    stations = [(-2.55, .025, .025), (-1.55, .17, .17), (-.6, .31, .29),
                (.55, .34, .29), (1.55, .26, .23), (2.25, .17, .18)]
    for dy, rx, rz in stations:
        vertices.extend((x + rx * math.cos(i * math.tau / 12), y + dy,
                         .59 + rz * math.sin(i * math.tau / 12)) for i in range(12))
    faces = [tuple(range(12)), tuple(reversed(range(60, 72)))]
    for j in range(len(stations) - 1):
        for i in range(12):
            a = j * 12 + i
            b = j * 12 + (i + 1) % 12
            faces.append((a, a + 12, b + 12, b))
    kit.mesh(label + " fuselage", vertices, faces, material)
    for side in (-1, 1):
        wing = [(x + side * .2, y - .65, .58), (x + side * 2.05, y + .60, .54),
                (x + side * 1.98, y + 1.0, .54), (x + side * .2, y + .85, .58)]
        faces = [(0, 1, 2, 3)] if side == 1 else [(3, 2, 1, 0)]
        obj = kit.mesh(label + " swept wing", wing, faces, material)
        bpy.context.view_layer.objects.active = obj
        modifier = obj.modifiers.new("Wing thickness", "SOLIDIFY")
        modifier.thickness = .07
        bpy.ops.object.modifier_apply(modifier=modifier.name)
        tail = [(x + side * .12, y + 1.45, .72), (x + side * .95, y + 2.0, .74),
                (x + side * .95, y + 2.24, .74), (x + side * .12, y + 2.10, .72)]
        tailplane = kit.mesh(label + " tailplane", tail, faces, material)
        thicken(tailplane, .035)
    fin = [(x, y + 1.0, .72), (x, y + 1.55, 1.50), (x, y + 2.1, 1.48), (x, y + 2.15, .72)]
    vertical_fin = kit.mesh(label + " vertical fin", fin, [(0, 1, 2, 3)], material)
    thicken(vertical_fin, .045)
    bpy.ops.mesh.primitive_uv_sphere_add(segments=12, ring_count=6, location=(x, y - .65, .85))
    canopy = bpy.context.object
    canopy.name = label + " canopy"
    canopy.scale = (.22, .56, .19)
    canopy.data.materials.append(glass)
    for dx, dy in ((-.38, .58), (.38, .58), (0, -1.25)):
        kit.box(label + " undercarriage", (x + dx, y + dy, .29), (.06, .06, .36), dark)
        wheel = cylinder(label + " wheel", (x + dx, y + dy, .115), .115, .095, dark, 8)
        wheel.rotation_euler.y = math.pi / 2


def geometry():
    import bpy

    materials = [kit.shader("Hangar masonry", (.28, .27, .23)),
                 kit.shader("Weathered olive roof", (.11, .15, .13), roughness=.8, grain=.018),
                 kit.shader("Tower dark glazing", (.045, .095, .12), roughness=.3, grain=.001),
                 kit.shader("Runway asphalt", (.075, .08, .075), grain=.035),
                 kit.shader("Paved apron", (.28, .27, .23), grain=.025),
                 kit.shader("Faded white paint", (.65, .64, .54), grain=.006),
                 kit.shader("Apron yellow paint", (.46, .33, .07), grain=.004),
                 kit.shader("Interior darkness", (.015, .018, .018)),
                 kit.shader("Hangar door steel", (.14, .17, .15), roughness=.8, grain=.014)]
    masonry, metal, glass, asphalt, apron, white, yellow, dark, steel = materials
    kit.box("Runway thin pavement", (0, -5, .015), (26, 3.4, .055), asphalt, .015)
    kit.box("Aircraft parking apron", (-2, 1.6, .015), (22, 5.6, .055), apron, .015)
    kit.box("Parallel taxiway", (-.5, -1.8, .017), (22, 1.3, .055), asphalt)
    for x in (-10.85, 9.85):
        kit.box("Runway connector", (x, -3.25, .018), (1.3, 3.0, .055), asphalt)
        kit.box("Taxiway connector centerline", (x, -2.8, .051), (.07, 1.65, .006), yellow)
    kit.box("Taxiway centerline", (-.5, -1.8, .052), (20.7, .07, .008), yellow)
    for x in (-9, -6, -3, 0, 3, 6, 9):
        kit.box("Runway centerline dash", (x, -5, .052), (1.4, .15, .008), white)
    for x in (-11.55, 11.55):
        for y in (-6.1, -5.65, -5.2, -4.75, -4.3, -3.85):
            kit.box("Runway threshold stripe", (x, y, .052), (1.25, .22, .008), white)
    for y in (-6.5, -3.5):
        kit.box("Runway edge line", (0, y, .052), (24.7, .06, .008), white)
    roof = hangar("West hangar", -6.4, 6.8, materials, open_doors=True)
    hangar("East hangar", .8, 6.8, materials)
    plane_material = kit.shader("Unmarked aircraft grey", (.29, .34, .34), roughness=.64, grain=.008)
    for name, x in (("West aircraft", -6.4), ("East aircraft", .8)):
        aircraft(name, x, 1.55, plane_material, glass, dark)
        kit.box("Stand guidance", (x, .15, .053), (.07, 2.1, .006), yellow)
        kit.box("Stand stop line", (x, 1.05, .054), (1.2, .07, .008), yellow)
    for x in (-10.8, -3, 4.7):
        kit.box("Apron expansion joint", (x, 1.6, .047), (.025, 5.6, .003), asphalt)
    kit.box("Tower service annex", (7.4, 5.7, .65), (3.6, 2.8, 1.3), masonry, .04)
    kit.block("Control tower shaft", (8.4, 5.7), [(0, 1.65, 1.65, .15), (3.25, 1.65, 1.65, .15)], masonry)
    kit.block("Control cabin base", (8.4, 5.7), [(2.95, 2.6, 2.4, .30), (3.17, 3.0, 2.8, .35)], masonry)
    kit.block("Control cabin glazing", (8.4, 5.7), [(3.17, 2.8, 2.6, .34), (3.92, 3.1, 2.9, .38)], glass)
    kit.block("Control cabin roof", (8.4, 5.7), [(3.92, 3.35, 3.15, .40), (4.10, 3.35, 3.15, .40)], metal)
    for dx, dy in kit.ring(3.0, 2.8, .36):
        kit.box("Control cabin mullion", (8.4 + dx, 5.7 + dy, 3.55), (.075, .075, .78), steel)
    kit.box("Tower access path", (7.4, 3.9, .02), (1.0, 1.2, .06), apron)
    kit.box("Service door", (7.1, 4.285, .60), (.7, .025, 1.15), steel)
    cylinder("Windsock mast", (10.6, 1.5, 1.25), .045, 2.5, steel)
    red = kit.shader("Faded windsock red", (.40, .075, .045), grain=.001)
    for j in range(4):
        vertices = []
        for end in (j, j + 1):
            radius = .22 - .035 * end
            vertices.extend((10.6 + .32 * end, 1.5 + radius * math.cos(i * math.tau / 8),
                             2.5 - .08 * end + radius * math.sin(i * math.tau / 8)) for i in range(8))
        faces = [(i, (i + 1) % 8, (i + 1) % 8 + 8, i + 8) for i in range(8)]
        kit.mesh("Windsock band", vertices, faces, red if j % 2 == 0 else white)
    for obj in list(bpy.data.objects):
        obj.location *= .5
        obj.scale *= .5
    return roof, materials


def damage(roof, materials):
    import bpy

    masonry, metal, glass, asphalt, apron, white, yellow, dark, steel = materials
    for obj in list(bpy.data.objects):
        if obj.name.startswith("West hangar roof seam"):
            bpy.data.objects.remove(obj, do_unlink=True)
    cutter = kit.box("Hangar roof breach", (-3.2, 3.35, 1.60), (1.75, 1.85, 1.8), dark)
    cutter.rotation_euler.z = .18
    kit.subtract(roof, cutter)
    fallen = kit.box("Collapsed curved roof panel", (-3.0, 1.85, .22), (1.5, 1.0, .09), metal)
    fallen.rotation_euler = (.20, .17, .16)
    for i in range(6):
        panel = kit.box("Roof debris", (-4 + i * .28, 1.85 + (i % 2) * .34, .12), (.30, .24, .09), steel)
        panel.rotation_euler.z = i * .57


def build():
    import bpy

    inputs = fingerprints()
    bpy.ops.wm.read_factory_settings(use_empty=True)
    roof, materials = geometry()
    clearances = check_clearances()
    intact = kit.statistics()
    kit.scene_setup()
    bpy.context.scene.camera.data.ortho_scale = 16.8
    kit.PREVIEW = PREVIEW
    for folder in (SOURCE, PREVIEW, REPORT.parent):
        folder.mkdir(parents=True, exist_ok=True)
    for name, position in VIEWS.items():
        kit.render(name, position)
    for pixels in (256, 128, 64):
        kit.render("map_%d" % pixels, VIEWS["map"], (pixels, pixels))
    kit.set_view(VIEWS["front"])
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=str(SOURCE / "airfield_prototype.blend"))
    damage(roof, materials)
    damaged = kit.statistics()
    kit.render("damaged_front", VIEWS["front"])
    kit.render("damaged_map", VIEWS["map"])
    kit.set_view(VIEWS["front"])
    bpy.ops.wm.save_as_mainfile(filepath=str(SOURCE / "airfield_damaged_prototype.blend"))
    report = {"generator": Path(__file__).relative_to(ROOT).as_posix(), "inputs": inputs,
              "purpose": "Development-only airfield design study",
              "native_export_verified": False, "hoi4_runtime_verified": False,
              "intact": intact, "damaged": damaged, "parking_clearances": clearances,
              "damage_note": "Exploratory damaged geometry; vanilla air base uses particles in a damaged state",
              "materials": "Provisional procedural Blender shaders",
              "sources": {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in SOURCE.glob("*.blend")}}
    REPORT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


def check_clearances():
    import bpy

    bpy.context.view_layer.update()

    def bounds(objects, axis):
        values = [(obj.matrix_world @ vertex.co)[axis] for obj in objects for vertex in obj.data.vertices]
        return min(values), max(values)

    apron = bpy.data.objects["Aircraft parking apron"]
    apron_front, apron_rear = bounds([apron], 1)
    result = {}
    for side in ("West", "East"):
        plane = [obj for obj in bpy.data.objects if obj.type == "MESH" and obj.name.startswith(side + " aircraft")]
        plane_front, plane_rear = bounds(plane, 1)
        assert plane_front > apron_front and plane_rear < apron_rear, side + " aircraft outside apron"
        portals = [obj for obj in bpy.data.objects if obj.name.startswith(side + " hangar front portal")]
        portals.sort(key=lambda obj: bounds([obj], 0)[0])
        opening = bounds([portals[1]], 0)[0] - bounds([portals[0]], 0)[1]
        plane_left, plane_right = bounds(plane, 0)
        assert opening > plane_right - plane_left, side + " hangar opening too narrow"
        result[side.lower()] = {"nose_to_apron_edge": round(plane_front - apron_front, 6),
                                "tail_to_apron_rear": round(apron_rear - plane_rear, 6),
                                "opening_minus_wingspan": round(opening - plane_right + plane_left, 6)}
        if side == "East":
            doors = [obj for obj in bpy.data.objects if obj.name.startswith("East hangar closed sliding door")]
            distance = bounds(doors, 1)[0] - plane_rear
            assert distance > 0, "Aircraft tail intersects closed doors"
            result[side.lower()]["tail_to_closed_door"] = round(distance, 6)
    return result


def sheets():
    from PIL import Image, ImageDraw, ImageFont

    font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 22)
    caption = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 17)
    background, ink = (28, 33, 32), (224, 226, 217)
    sheet = Image.new("RGB", (1280, 1126), background)
    draw = ImageDraw.Draw(sheet)
    draw.text((22, 15), "A-DISCORD / ПРОТОТИП АЭРОДРОМА", font=font, fill=ink)
    for index, (name, label) in enumerate((("front", "01 / Спереди"), ("opposite", "02 / С другого фланга"),
                                           ("rear", "03 / С тыла"), ("top", "04 / Сверху"))):
        x, y = index % 2 * 640, 53 + index // 2 * 534
        image = Image.open(PREVIEW / (name + ".png")).convert("RGB")
        sheet.paste(image.resize((640, 512), Image.Resampling.LANCZOS), (x, y + 22))
        draw.text((x + 14, y), label, font=caption, fill=ink)
    sheet.save(PREVIEW / "review_angles.png")
    sheet = Image.new("RGB", (680, 390), background)
    draw = ImageDraw.Draw(sheet)
    draw.text((20, 15), "МЕЛКИЙ МАСШТАБ / без увеличения", font=font, fill=ink)
    for pixels, x in ((256, 18), (128, 302), (64, 476)):
        draw.text((x, 59), "%d x %d px" % (pixels, pixels), font=caption, fill=ink)
        sheet.paste(Image.open(PREVIEW / ("map_%d.png" % pixels)).convert("RGB"), (x, 87 + (256 - pixels) // 2))
    draw.text((20, 361), "Рендеры Blender. Игровые привязки не изменены.", font=caption, fill=ink)
    sheet.save(PREVIEW / "review_small.png")
    sheet = Image.new("RGB", (1280, 590), background)
    ImageDraw.Draw(sheet).text((22, 15), "ПОВРЕЖДЁННЫЙ АНГАР / ПРОТОТИП", font=font, fill=ink)
    for index, name in enumerate(("damaged_front", "damaged_map")):
        image = Image.open(PREVIEW / (name + ".png")).convert("RGB")
        sheet.paste(image.resize((640, 512), Image.Resampling.LANCZOS), (index * 640, 62))
    sheet.save(PREVIEW / "review_damaged.png")
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    report["previews"] = {name + ".png": hashlib.sha256((PREVIEW / (name + ".png")).read_bytes()).hexdigest()
                          for name in (*RENDERS, *SHEETS)}
    REPORT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


def stale():
    if not REPORT.exists():
        return [REPORT.relative_to(ROOT).as_posix()]
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    changed = [] if report.get("inputs") == fingerprints() else ["generator inputs"]
    for folder, hashes, names in (
        (SOURCE, report.get("sources", {}), ("airfield_prototype.blend", "airfield_damaged_prototype.blend")),
        (PREVIEW, report.get("previews", {}), tuple(name + ".png" for name in (*RENDERS, *SHEETS))),
    ):
        for name in names:
            path = folder / name
            if not path.exists() or hashlib.sha256(path.read_bytes()).hexdigest() != hashes.get(name):
                changed.append(path.relative_to(ROOT).as_posix())
    return changed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--check", action="store_true")
    modes.add_argument("--apply", action="store_true")
    modes.add_argument("--build", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:])
    if args.build:
        build()
    elif args.apply:
        if not stale():
            print("Airfield prototype is current; no files changed.")
            return
        subprocess.run([str(kit.BLENDER), "--background", "--factory-startup", "--python", str(Path(__file__)), "--", "--build"],
                       cwd=ROOT, env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"), check=True)
        sheets()
    else:
        print("Development-only airfield outputs:")
        for path in (SOURCE, PREVIEW, REPORT):
            print(path.relative_to(ROOT))
        changed = stale()
        print("Needs rebuilding:\n" + "\n".join(changed) if changed else "All prototype hashes match.")


if __name__ == "__main__":
    main()
