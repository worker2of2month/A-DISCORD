"""Build a dry-dock design prototype; never install runtime assets or bindings.

--check inspects development output hashes. --apply builds the editable scene,
review renders and report, with a no-op when all recorded outputs are current.
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

SOURCE = ROOT / "tools/assets/source/buildings/dockyard"
PREVIEW = ROOT / "docs/development/previews/dockyard_prototype"
REPORT = ROOT / "docs/development/model-verification/dockyard_prototype.json"
VIEWS = {"front": (13, -18, 15), "opposite": (-14, -17, 13),
         "rear": (14, 17, 15), "map": (8, -12, 24), "top": (0, 0, 30)}
RENDERS = (*VIEWS, "map_256", "map_128", "map_64", "damaged_front", "damaged_map")
SHEETS = ("review_angles", "review_small", "review_damaged")
STATIONS = ((-8, 1.05), (-7, 1.45), (-5, 1.55), (-3, 1.55), (0, 1.55),
            (3, 1.45), (5, 1.15), (6.8, .65), (8, .05))


def fingerprints():
    return {path.relative_to(ROOT).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in (Path(__file__), Path(kit.__file__))}


def beam(name, start, end, width, depth, material):
    from mathutils import Vector

    a, b = Vector(start), Vector(end)
    obj = kit.box(name, (a + b) * .5, (width, depth, (b - a).length), material)
    obj.rotation_euler = (b - a).to_track_quat("Z", "Y").to_euler()
    return obj


def thicken(obj, width):
    import bpy

    bpy.context.view_layer.objects.active = obj
    modifier = obj.modifiers.new("Panel thickness", "SOLIDIFY")
    modifier.thickness = width
    bpy.ops.object.modifier_apply(modifier=modifier.name)


def radius_at(x):
    for (left, a), (right, b) in zip(STATIONS, STATIONS[1:]):
        if left <= x <= right:
            return a + (b - a) * (x - left) / (right - left)
    raise ValueError(x)


def hull_section(radius):
    return [(-radius, 2.4), (-radius, 1.2), (-radius * .5, .55),
            (0, .4), (radius * .5, .55), (radius, 1.2), (radius, 2.4)]


def hull(primer, frame, dark, timber):
    import bpy

    vertices = [(x, y, z) for x, radius in STATIONS for y, z in hull_section(radius)]
    faces = []
    for station in range(len(STATIONS) - 1):
        for j in range(6):
            if j == 0 and station in (3, 4):
                continue
            a = station * 7 + j
            faces.append((a, a + 1, a + 8, a + 7))
    shell = kit.mesh("Unfinished hull plating", vertices, faces, primer)
    bpy.context.view_layer.objects.active = shell
    modifier = shell.modifiers.new("Steel shell thickness", "SOLIDIFY")
    modifier.thickness = .09
    bpy.ops.object.modifier_apply(modifier=modifier.name)
    bulkhead = kit.mesh("Stern bulkhead", vertices[:7], [tuple(reversed(range(7)))], frame)
    thicken(bulkhead, .09)
    for x in (-6, -4, -2, 0, 2, 4, 6):
        section = hull_section(radius_at(x))
        for (ya, za), (yb, zb) in zip(section, section[1:]):
            beam("Exposed hull rib", (x, ya, za), (x, yb, zb), .14, .14, frame)
        beam("Unfinished deck beam", (x, -radius_at(x), 2.35), (x, radius_at(x), 2.35), .12, .14, frame)
        kit.box("Keel support block", (x, 0, .25), (.52, 1.2, .30), timber)
    for side in (-1, 1):
        for (xa, ra), (xb, rb) in zip(STATIONS, STATIONS[1:]):
            beam("Hull sheer rail", (xa, side * ra, 2.4), (xb, side * rb, 2.4), .14, .13, frame)
    kit.box("Keel assembly spine", (-.5, 0, .56), (14.0, .22, .23), dark)
    return shell


def assembly_hall(masonry, roof_material, steel, glass):
    kit.box("Assembly hall walls", (-5.2, 5.8, 1.94), (8.6, 3.2, 2.2), masonry)
    outline = [(-9.65, 4.1, 3.04), (-.75, 4.1, 3.04), (-.75, 5.8, 3.80),
               (-9.65, 5.8, 3.80), (-9.65, 7.5, 3.04), (-.75, 7.5, 3.04)]
    roof = kit.mesh("Assembly hall pitched roof", outline, [(0, 1, 2, 3), (3, 2, 5, 4)], roof_material)
    thicken(roof, .08)
    for x in (-9.5, -.9):
        order = (2, 1, 0) if x < -5 else (0, 1, 2)
        gable = kit.mesh("Assembly hall gable", [(x, 4.2, 3.0), (x, 7.4, 3.0), (x, 5.8, 3.8)],
                         [order], masonry)
        thicken(gable, .08)
    for x in (-7.5, -3.0):
        kit.box("Assembly sliding door", (x, 4.185, 1.65), (2.7, .045, 1.55), steel)
        kit.box("Assembly door center joint", (x, 4.151, 1.65), (.035, .015, 1.55), roof_material)
    for x in (-8.5, -6.3, -4.1, -1.9):
        kit.box("Assembly clerestory", (x, 4.15, 2.70), (1.5, .04, .39), glass)
    for x in (-8.0, -6.0, -4.0, -2.0):
        beam("Hall roof seam", (x, 4.1, 3.055), (x, 5.8, 3.815), .025, .025, steel)
        beam("Hall roof seam", (x, 5.8, 3.815), (x, 7.5, 3.055), .025, .025, steel)


def gantry(paint, dark, yellow, glass):
    legs = []
    for y in (-3.65, 3.65):
        kit.box("Gantry travel rail", (0, y, .89), (19.0, .12, .10), dark)
        for foot, head in ((.1, 1.2), (3.1, 2.0)):
            kit.box("Gantry rail bogie", (foot, y, 1.05), (1.10, .65, .30), paint, .06)
            legs.append(beam("Gantry A-frame leg", (foot, y, 1.18), (head, y, 5.85), .34, .36, paint))
        beam("Gantry side cross tie", (.70, y, 3.75), (2.55, y, 3.75), .24, .24, paint)
        beam("Gantry side diagonal", (.43, y, 2.4), (2.2, y, 4.8), .18, .18, paint)
    for x in (1.2, 2.0):
        kit.box("Gantry bridge girder", (x, 0, 5.95), (.38, 8.5, .56), paint, .035)
    for y in (-3.5, -1.7, 0, 1.7, 3.5):
        beam("Gantry bridge cross tie", (1.2, y, 6.13), (2.0, y, 6.13), .14, .14, dark)
    kit.box("Gantry travelling hoist", (1.6, -.3, 5.52), (1.1, 1.25, .5), yellow, .04)
    for x in (1.35, 1.85):
        for y in (-.55, -.05):
            beam("Gantry lifting cable", (x, y, 5.27), (x, y, 3.24), .045, .045, dark)
    kit.box("Gantry hook block", (1.6, -.3, 3.12), (.72, .65, .30), yellow, .045)
    beam("Gantry hook shank", (1.6, -.3, 3), (1.6, -.3, 2.8), .11, .11, dark)
    beam("Gantry hook curve", (1.6, -.3, 2.8), (1.8, -.3, 2.76), .11, .11, dark)
    kit.box("Gantry operator cabin", (1.6, -4.15, 5.32), (1.35, 1.20, .85), paint, .045)
    kit.box("Gantry cabin glazing", (1.6, -4.76, 5.42), (1.13, .025, .40), glass)
    return legs


def jib_crane(paint, dark, yellow):
    kit.box("Small crane pedestal", (-7.8, -4.35, 1.16), (1.2, 1.2, .64), paint, .06)
    beam("Small crane mast", (-7.8, -4.35, 1.45), (-7.8, -4.35, 4.15), .32, .32, paint)
    for offset in (-.18, .18):
        beam("Small crane jib", (-7.8, -4.35 + offset, 3.7), (-5.0, -1.5 + offset, 4.35), .18, .18, paint)
    for fraction in (.2, .45, .7, .95):
        x, y, z = -7.8 + 2.8 * fraction, -4.35 + 2.85 * fraction, 3.7 + .65 * fraction
        beam("Small crane jib tie", (x, y - .18, z), (x, y + .18, z), .09, .09, dark)
    beam("Small crane support cable", (-7.8, -4.35, 4.15), (-5, -1.5, 4.35), .04, .04, dark)
    beam("Small crane lifting cable", (-5, -1.5, 4.35), (-5, -1.5, 2.92), .045, .045, dark)
    kit.box("Small crane hook", (-5, -1.5, 2.83), (.20, .20, .22), yellow)


def geometry():
    import bpy

    concrete = kit.shader("Quay concrete", (.25, .27, .25))
    dock_floor = kit.shader("Dry dock floor", (.12, .13, .12), grain=.04)
    frame = kit.shader("Ship framing steel", (.22, .28, .27), roughness=.72, grain=.012)
    primer = kit.shader("Hull red oxide primer", (.25, .075, .045), roughness=.88, grain=.02)
    dark = kit.shader("Dark rails and cables", (.035, .045, .045), roughness=.65, grain=.005)
    paint = kit.shader("Gantry blue green paint", (.08, .20, .20), roughness=.72, grain=.016)
    yellow = kit.shader("Hoist safety ochre", (.61, .36, .065), roughness=.8, grain=.012)
    brick = kit.shader("Assembly weathered brick", (.28, .13, .075))
    metal = kit.shader("Assembly sheet roof", (.13, .17, .17), roughness=.8, grain=.015)
    glass = kit.shader("Workshop dark glass", (.055, .105, .115), roughness=.35, grain=.001)
    timber = kit.shader("Keel support timber", (.13, .085, .045))
    base = kit.box("Quay body", (0, 1.0, .42), (22, 14, .84), concrete)
    cutter = kit.box("Dry dock excavation", (.80, 0, .8), (20.6, 5.0, 2.0), dark)
    kit.subtract(base, cutter)
    kit.box("Dry dock bed", (0, 0, .055), (19, 5.0, .11), dock_floor)
    kit.box("Closed caisson gate", (9.6, 0, .62), (.24, 5.0, 1.15), frame, .025)
    for y in (-2, -1, 0, 1, 2):
        kit.box("Caisson gate rib", (9.745, y, .62), (.05, .12, 1.12), metal)
    for y in (-2.65, 2.65):
        kit.box("Dock coping rim", (0, y, .87), (19.2, .30, .12), concrete, .035)
    shell = hull(primer, frame, dark, timber)
    assembly_hall(brick, metal, frame, glass)
    legs = gantry(paint, dark, yellow, glass)
    jib_crane(paint, dark, yellow)
    for stack, x in enumerate((-4.9, -1.8)):
        for layer in range(4):
            kit.box("Steel plate stack", (x, -4.7, .90 + .10 * layer), (2.45, 1.1, .085), frame)
    for x in (5.2, 7.0):
        for side in (-1, 1):
            beam("Stored hull section", (x, 4.8 + side * .8, .86), (x, 4.8 + side * 1.15, 1.9), .19, .19, primer)
        beam("Stored hull section spine", (x, 4.0, .87), (x, 5.6, .87), .19, .19, primer)
    for obj in list(bpy.data.objects):
        obj.location *= .5
        obj.scale *= .5
    return shell, legs, (primer, frame, dark, paint, metal)


def damage(shell, legs, materials):
    import bpy

    primer, frame, dark, paint, metal = materials
    hall = bpy.data.objects["Assembly hall walls"]
    interior = kit.box("Hall interior cutting volume", (-2.6, 2.9, 1.18), (3.8, 1.2, 1.50), dark)
    kit.subtract(hall, interior)
    kit.box("Exposed hall floor", (-2.6, 2.9, .45), (3.8, 1.2, .05), dark)
    roof = bpy.data.objects["Assembly hall pitched roof"]
    collapse = kit.prism("Collapsed hall roof volume",
                         [(-3.4, 1.8), (-2.1, 1.8), (-1.85, 2.3), (-2.1, 2.65),
                          (-1.9, 3.0), (-2.15, 3.8), (-3.55, 3.8), (-3.2, 3.3),
                          (-3.4, 2.9), (-3.25, 2.5)], 1.3, 2.5, dark)
    kit.subtract(roof, collapse)
    for obj in list(bpy.data.objects):
        if obj.name.startswith("Hall roof seam"):
            bpy.data.objects.remove(obj, do_unlink=True)
    fallen_roof = kit.box("Collapsed hall roof sheet", (-2.7, 2.9, .70), (1.0, .80, .05), metal)
    fallen_roof.rotation_euler = (.2, -.3, .1)
    cutter = kit.box("Damaged hull cutting volume", (2.3, -.65, 1.0), (1.35, .9, 1.5), dark)
    cutter.rotation_euler.z = -.25
    kit.subtract(shell, cutter)
    cabin = bpy.data.objects.get("Gantry operator cabin")
    if cabin:
        cabin.data.materials[0] = metal
    for index in range(5):
        panel = kit.box("Dockside fallen plating", (2.1 + index * .24, -2.45, 0), (.50, .38, .07), primer)
        panel.rotation_euler = (.12, .3, index * .55)
        bpy.context.view_layer.update()
        minimum = min((panel.matrix_world @ vertex.co).z for vertex in panel.data.vertices)
        panel.location.z = .425 - minimum
    for obj in list(bpy.data.objects):
        if obj.name.startswith("Gantry lifting cable") or obj.name.startswith("Gantry hook"):
            bpy.data.objects.remove(obj, do_unlink=True)
    kit.box("Damaged hoist on dock floor", (.8, -1.03, .18), (.45, .26, .25), paint, .03)


def check_clearances():
    import bpy

    bpy.context.view_layer.update()

    def bounds(objects, axis):
        values = [(obj.matrix_world @ vertex.co)[axis] for obj in objects for vertex in obj.data.vertices]
        return min(values), max(values)

    shell = bpy.data.objects["Unfinished hull plating"]
    hull_y = bounds([shell], 1)
    hull_top = bounds([shell], 2)[1]
    hooks = [obj for obj in bpy.data.objects if obj.type == "MESH" and obj.name.startswith("Gantry hook")]
    clearance = bounds(hooks, 2)[0] - hull_top
    assert clearance > .10, "Main crane hook touches the hull"
    for obj in bpy.data.objects:
        if obj.name.startswith("Gantry A-frame leg"):
            y0, y1 = bounds([obj], 1)
            assert y1 < -1.25 or y0 > 1.25, "Crane leg stands inside the dock"
    assert hull_y[0] > -1.25 and hull_y[1] < 1.25
    return {"main_hook_above_hull": round(clearance, 6), "hull_width": round(hull_y[1] - hull_y[0], 6)}


def build():
    import bpy

    inputs = fingerprints()
    bpy.ops.wm.read_factory_settings(use_empty=True)
    shell, legs, materials = geometry()
    clearances = check_clearances()
    intact = kit.statistics()
    kit.scene_setup()
    water = kit.shader("Review coastal water", (.045, .13, .16), roughness=.3, grain=.012)
    kit.box("REVIEW water outside quay", (55.5, 0, .16), (100, 200, .04), water)
    kit.box("REVIEW water beyond caisson", (5.18, 0, .16), (.64, 2.49, .04), water)
    bpy.context.scene.camera.data.ortho_scale = 17.8
    kit.PREVIEW = PREVIEW
    for folder in (SOURCE, PREVIEW, REPORT.parent):
        folder.mkdir(parents=True, exist_ok=True)
    for name, position in VIEWS.items():
        kit.render(name, position)
    for pixels in (256, 128, 64):
        kit.render("map_%d" % pixels, VIEWS["map"], (pixels, pixels))
    kit.set_view(VIEWS["front"])
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=str(SOURCE / "dockyard_prototype.blend"))
    damage(shell, legs, materials)
    damaged = kit.statistics()
    kit.render("damaged_front", VIEWS["front"])
    kit.render("damaged_map", VIEWS["map"])
    kit.set_view(VIEWS["front"])
    bpy.ops.wm.save_as_mainfile(filepath=str(SOURCE / "dockyard_damaged_prototype.blend"))
    report = {"generator": Path(__file__).relative_to(ROOT).as_posix(), "inputs": inputs,
              "purpose": "Development-only dry-dock study", "native_export_verified": False,
              "hoi4_runtime_verified": False, "intact": intact, "damaged": damaged,
              "clearances": clearances, "materials": "Procedural Blender review materials",
              "terrain_note": "Dock floor is above model ground; the mesh does not excavate map terrain. Review water is not an exported asset.",
              "sources": {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in SOURCE.glob("*.blend")}}
    REPORT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


def sheets():
    from PIL import Image, ImageDraw, ImageFont

    font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 22)
    caption = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 17)
    background, ink = (28, 33, 32), (224, 226, 217)
    sheet = Image.new("RGB", (1280, 1126), background)
    draw = ImageDraw.Draw(sheet)
    draw.text((22, 15), "A-DISCORD / ПРОТОТИП ВЕРФИ", font=font, fill=ink)
    for index, (name, label) in enumerate((("front", "01 / Со стороны дока"), ("opposite", "02 / С другого фланга"),
                                           ("rear", "03 / Со стороны цеха"), ("top", "04 / Сверху"))):
        x, y = index % 2 * 640, 53 + index // 2 * 534
        picture = Image.open(PREVIEW / (name + ".png")).convert("RGB")
        sheet.paste(picture.resize((640, 512), Image.Resampling.LANCZOS), (x, y + 22))
        draw.text((x + 14, y), label, font=caption, fill=ink)
    sheet.save(PREVIEW / "review_angles.png")
    sheet = Image.new("RGB", (680, 390), background)
    draw = ImageDraw.Draw(sheet)
    draw.text((20, 15), "МЕЛКИЙ МАСШТАБ / без увеличения", font=font, fill=ink)
    for pixels, x in ((256, 18), (128, 302), (64, 476)):
        draw.text((x, 59), "%d x %d px" % (pixels, pixels), font=caption, fill=ink)
        sheet.paste(Image.open(PREVIEW / ("map_%d.png" % pixels)).convert("RGB"), (x, 87 + (256 - pixels) // 2))
    draw.text((20, 361), "Рендеры Blender. Вода - окружение для просмотра.", font=caption, fill=ink)
    sheet.save(PREVIEW / "review_small.png")
    sheet = Image.new("RGB", (1280, 590), background)
    ImageDraw.Draw(sheet).text((22, 15), "ПОВРЕЖДЁННАЯ ВЕРФЬ / ПРОТОТИП", font=font, fill=ink)
    for index, name in enumerate(("damaged_front", "damaged_map")):
        picture = Image.open(PREVIEW / (name + ".png")).convert("RGB")
        sheet.paste(picture.resize((640, 512), Image.Resampling.LANCZOS), (index * 640, 62))
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
        (SOURCE, report.get("sources", {}), ("dockyard_prototype.blend", "dockyard_damaged_prototype.blend")),
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
            print("Dockyard prototype is current; no files changed.")
            return
        subprocess.run([str(kit.BLENDER), "--background", "--factory-startup", "--python", str(Path(__file__)), "--", "--build"],
                       cwd=ROOT, env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"), check=True)
        sheets()
    else:
        print("Development-only dockyard outputs:")
        for path in (SOURCE, PREVIEW, REPORT):
            print(path.relative_to(ROOT))
        changed = stale()
        print("Needs rebuilding:\n" + "\n".join(changed) if changed else "All prototype hashes match.")


if __name__ == "__main__":
    main()
