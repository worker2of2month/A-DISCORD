"""Render national aircraft from installed meshes with Blender --python this_file -- --render.

Use --check and --apply with --tag TVA --sheets TVA.png for a single national set.
Without --tag, the sheets follow MODEL_CARD_TAGS order (IVN, MON, WRK, TVA).
Each sheet has fighters on the left, CAS on the right and generations from top to bottom.
"""

import argparse
from io import BytesIO
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
sys.dont_write_bytecode = True
from tools.assets.source.country_vehicles.package_vehicles import DEST as MODELS, MODEL_CARD_TAGS, PREFIXES

STAGE = Path(tempfile.gettempdir()) / "adiscord-national-aircraft-cards"
DEST = ROOT / "gfx/interface/technologies"


def cards():
    for tag in MODEL_CARD_TAGS:
        for role in ("fighter", "cas"):
            for tier, prefix in enumerate(PREFIXES, 1):
                name = f"{tag}_{prefix}{role}"
                card = f"ADISCORD_aircraft_{'cas_' if role == 'cas' else ''}{tag}_{tier}.png"
                yield name, card


def render():
    import bpy
    from mathutils import Vector
    from tools.assets.source import build_country_cas as native
    from tools.assets.source.build_shl_palace import load_exporter

    exporter = load_exporter()
    native.bpy = bpy
    STAGE.mkdir(parents=True, exist_ok=True)
    for name, card in cards():
        bpy.ops.wm.read_factory_settings(use_empty=True)
        exporter.import_meshfile(str(MODELS / (name + ".mesh")), join_materials=False)
        native.preview_materials()
        vertices = [
            obj.matrix_world @ v.co
            for obj in bpy.context.scene.objects
            if obj.type == "MESH"
            for v in obj.data.vertices
        ]
        lo, hi = (Vector([fn(p[i] for p in vertices) for i in range(3)]) for fn in (min, max))
        center = (lo + hi) / 2
        scene = bpy.context.scene
        scene.render.engine = "CYCLES"
        scene.cycles.samples = 28
        scene.cycles.seed = 17
        scene.render.resolution_x, scene.render.resolution_y = 880, 360
        scene.render.resolution_percentage = 100
        scene.render.film_transparent = True
        scene.view_settings.look = "AgX - Medium High Contrast"
        scene.world = bpy.data.worlds.new("Studio")
        scene.world.use_nodes = True
        scene.world.node_tree.nodes["Background"].inputs[0].default_value = (0.26, 0.28, 0.31, 1)
        # A shallow view shows wing sweep and store clearance at equipment-card scale.
        direction = Vector((1, -0.13, 0.22)).normalized()
        rotation = (-direction).to_track_quat("-Z", "Y")
        right, up = (rotation @ Vector(axis) for axis in ((1, 0, 0), (0, 1, 0)))

        def span(axis):
            return 2 * max(abs((p - center).dot(axis)) for p in vertices)

        scale = max(span(right), span(up) * 176 / 72) * 1.08
        for offset, power, size in (
            ((0.75, -0.82, 1.1), 82, 0.70),
            ((-0.48, 0.65, 0.92), 72, 0.80),
            ((0.70, 0.43, 0.23), 10, 0.75),
        ):
            bpy.ops.object.light_add(type="AREA", location=center + Vector(offset) * scale)
            lamp = bpy.context.object
            lamp.data.energy, lamp.data.size = power * scale * scale, size * scale
            lamp.rotation_euler = (center - lamp.location).to_track_quat("-Z", "Y").to_euler()
        bpy.ops.object.camera_add(location=center + direction * scale * 2)
        camera = bpy.context.object
        camera.rotation_euler = rotation.to_euler()
        camera.data.type, camera.data.ortho_scale = "ORTHO", scale
        scene.camera = camera
        scene.render.filepath = str(STAGE / card)
        bpy.ops.render.render(write_still=True)


def painted_cards(source, tag):
    from itertools import groupby
    from PIL import Image

    with Image.open(source) as sheet:
        if sheet.mode != "RGBA":
            raise ValueError(f"Expected a transparent aircraft sheet: {source}")
        width, height = sheet.size
        for column, role in enumerate(("fighter", "cas")):
            strip = sheet.crop((width * column // 2, 0, width * (column + 1) // 2, height))
            mask = strip.getchannel("A").point(lambda a: 255 if a >= 32 else 0)
            # The longest fins and external stores can cross the mathematical row boundary.
            occupied = mask.getprojection()[1]
            bands = []
            for filled, rows in groupby(enumerate(occupied), key=lambda row: bool(row[1])):
                if filled:
                    indices = [y for y, _ in rows]
                    bands.append((indices[0], indices[-1] + 1))
            if len(bands) != 3:
                raise ValueError(f"Expected three fully separated {role} silhouettes in {source}: {bands}")
            for tier, (top, bottom) in enumerate(bands, 1):
                left, _, right, _ = mask.crop((0, top, strip.width, bottom)).getbbox()
                artwork = strip.crop(
                    (max(0, left - 2), max(0, top - 2), min(strip.width, right + 2), min(height, bottom + 2))
                )
                artwork.thumbnail((172, 68), Image.Resampling.LANCZOS)
                canvas = Image.new("RGBA", (176, 72))
                canvas.alpha_composite(artwork, ((176 - artwork.width) // 2, (72 - artwork.height) // 2))
                filename = f"ADISCORD_aircraft_{'cas_' if role == 'cas' else ''}{tag}_{tier}.png"
                with BytesIO() as stream:
                    canvas.save(stream, format="PNG")
                    yield DEST / filename, stream.getvalue()


def package(apply, sheets, tags):
    outputs = dict(pair for tag, path in zip(tags, sheets, strict=True) for pair in painted_cards(path, tag))
    changes = [p for p, data in outputs.items() if not p.exists() or p.read_bytes() != data]
    if apply:
        for p in changes:
            p.write_bytes(outputs[p])
    print(f"Aircraft PNGs: {len(outputs)}, different: {len(changes)}")
    return changes


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    for mode in ("render", "check", "apply"):
        action.add_argument("--" + mode, action="store_true")
    parser.add_argument("--tag", choices=MODEL_CARD_TAGS)
    parser.add_argument("--sheets", type=Path, nargs="+", metavar="PNG")
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else None)
    if args.render:
        render()
    elif not args.sheets:
        parser.error("--check and --apply require painted --sheets")
    else:
        tags = (args.tag,) if args.tag else MODEL_CARD_TAGS
        # The original three-sheet command packages IVN, MON and WRK together.
        if not args.tag and len(args.sheets) == 3:
            tags = MODEL_CARD_TAGS[:3]
        if len(tags) != len(args.sheets):
            parser.error(f"Expected one sheet for each of {', '.join(tags)}")
        if package(args.apply, args.sheets, tags) and args.check:
            raise SystemExit(1)
