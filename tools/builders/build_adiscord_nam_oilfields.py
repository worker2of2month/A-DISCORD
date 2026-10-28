"""Build three-derrick oilfields on NAM's large starting deposits.

Default/--check is read-only. --apply exports stale assets with Blender.
--preview renders the installed native mesh into development previews.
The actors describe deposits and persist through changes of country ownership.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys
import tempfile

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.assets.source.build_shl_palace import Geometry, dds_bytes, load_exporter

NAME = "ADISCORD_NAM_oilfield"
MODEL_DIR = Path("gfx/models/buildings/NAM_oilfield")
SOURCE = Path("tools/assets/source/buildings/NAM/oilfield.blend")
REPORT = Path("docs/development/model-verification/NAM_oilfield.json")
PREVIEW = Path("docs/development/previews/NAM_oilfield")
MARKER = "ADISCORD NAM oilfields"
SCALE = .16
MIN_OIL = 24
TOWERS = ((-8, -2, 22), (7, -2, 20), (-1, 7, 24))
FILES = [NAME + suffix for suffix in (".mesh", "_diffuse.dds", "_normal.dds", "_specular.dds")]
INPUTS = (
    Path(__file__).relative_to(ROOT),
    Path("tools/assets/source/build_shl_palace.py"),
    Path("map/heightmap.bmp"), Path("map/provinces.bmp"), Path("map/rivers.bmp"),
    Path("map/definition.csv"), Path("map/buildings.txt"),
)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def oil_states():
    result = []
    for path in sorted((ROOT / "history/states").glob("*.txt")):
        text = path.read_text(encoding="utf-8-sig")
        if not re.search(r"\bowner\s*=\s*NAM\b", text):
            continue
        resources = re.search(r"\bresources\s*=\s*\{([^}]*)\}", text)
        oil = re.search(r"\boil\s*=\s*(\d+)", resources[1]) if resources else None
        if oil and int(oil[1]) >= MIN_OIL:
            result.append({
                "state": int(re.search(r"\bid\s*=\s*(\d+)", text)[1]),
                "oil": int(oil[1]), "path": path,
                "provinces": [int(p) for p in re.search(r"\bprovinces\s*=\s*\{([^}]*)\}", text)[1].split()],
                "cities": {int(p) for p in re.findall(r"victory_points\s*=\s*\{\s*(\d+)", text)},
            })
    return sorted(result, key=lambda state: state["state"])


def input_hashes():
    paths = [*INPUTS, *(s["path"].relative_to(ROOT) for s in oil_states())]
    return {path.as_posix(): digest(ROOT / path) for path in paths}


def placements():
    """Choose level inland footprints outside cities and building spawn areas."""
    import numpy as np
    from PIL import Image

    provinces = np.asarray(Image.open(ROOT / "map/provinces.bmp").convert("RGB"))
    heights = np.asarray(Image.open(ROOT / "map/heightmap.bmp"), dtype=float) / 10
    rivers = np.asarray(Image.open(ROOT / "map/rivers.bmp"))
    packed = (provinces[:, :, 0].astype("uint32") << 16) | (provinces[:, :, 1].astype("uint32") << 8) | provinces[:, :, 2]
    definitions = {}
    for line in (ROOT / "map/definition.csv").read_text(encoding="utf-8-sig").splitlines():
        fields = line.split(";")
        if fields[0].isdigit() and len(fields) >= 7:
            definitions[int(fields[0])] = fields
    obstacles = []
    for line in (ROOT / "map/buildings.txt").read_text().splitlines():
        fields = line.split(";")
        if fields[0].isdigit() and len(fields) >= 5:
            obstacles.append((float(fields[2]), float(fields[4])))
    result = []
    for state in oil_states():
        candidates = []
        for province in sorted(set(state["provinces"]) - state["cities"]):
            fields = definitions[province]
            if fields[4] != "land" or fields[6] not in ("plains", "desert", "hills"):
                continue
            r, g, b = map(int, fields[1:4])
            mask = packed == ((r << 16) | (g << 8) | b)
            rows, cols = np.nonzero(mask)
            if not len(rows):
                continue
            cx, cy = float(cols.mean()), float(rows.mean())
            for row in range(int(rows.min()) + 3, int(rows.max()) - 2):
                for col in range(int(cols.min()) + 3, int(cols.max()) - 2):
                    # A full 7x7 footprint includes the native mesh and margin.
                    if not mask[row - 3:row + 4, col - 3:col + 4].all():
                        continue
                    if not (rivers[row - 3:row + 4, col - 3:col + 4] == 255).all():
                        continue
                    patch = heights[row - 3:row + 4, col - 3:col + 4]
                    span = float(np.ptp(patch))
                    if span > .5 or float(patch.min()) < 10:
                        continue
                    x, z = float(col), float(len(heights) - 1 - row)
                    if any((x - ox) ** 2 + (z - oz) ** 2 < 5 ** 2 for ox, oz in obstacles):
                        continue
                    score = (col - cx) ** 2 + (row - cy) ** 2 + span * 100
                    candidates.append((score, province, x, z, round(float(patch.max()) - .1, 3)))
        count = math.ceil(state["oil"] / 40)
        for _, province, x, z, height in sorted(candidates):
            if any((x - p["position"][0]) ** 2 + (z - p["position"][2]) ** 2 < 16 ** 2 for p in result):
                continue
            result.append({"state": state["state"], "oil": state["oil"], "province": province,
                           "position": [x, height, z], "scale": SCALE})
            count -= 1
            if count == 0:
                break
        if count:
            raise ValueError(f"No clear, level oilfield sites in state {state['state']}: {count} missing")
    return result


def textures():
    import numpy as np
    from PIL import Image, ImageDraw

    colors = ((58, 66, 66), (139, 63, 42), (197, 186, 153), (104, 112, 107),
              (117, 107, 87), (42, 48, 47), (109, 74, 44), (179, 141, 56),
              (63, 83, 88), (32, 35, 34), (148, 148, 130), (94, 100, 91),
              (80, 63, 44), (170, 161, 136), (119, 47, 32), (213, 207, 181))
    rng = np.random.default_rng(67)
    atlas = Image.new("RGBA", (1024, 1024))
    for index, color in enumerate(colors):
        noise = rng.normal(0, 3, (256, 256, 1))
        rgb = np.clip(np.asarray(color)[None, None, :] + noise, 0, 255).astype("uint8")
        tile = Image.fromarray(rgb).convert("RGBA")
        draw = ImageDraw.Draw(tile)
        dark = tuple(int(c * .65) for c in color)
        for y in (12, 124, 244):
            draw.line((0, y, 255, y), fill=dark, width=3)
            for x in range(14, 256, 32):
                draw.ellipse((x, y + 5, x + 4, y + 9), fill=tuple(min(255, c + 30) for c in color))
        if index in (1, 3, 6, 14):
            for _ in range(50):
                x, y = map(int, rng.integers(0, 250, 2))
                draw.line((x, y, x + 3, min(255, y + 15)), fill=(105, 67, 41), width=2)
        atlas.paste(tile, (index % 4 * 256, index // 4 * 256))
    return {
        FILES[1]: dds_bytes(atlas),
        FILES[2]: dds_bytes(Image.new("RGBA", atlas.size, (255, 128, 0, 128))),
        FILES[3]: dds_bytes(Image.new("RGBA", atlas.size, (0, 65, 0, 40))),
    }


class OilfieldGeometry(Geometry):
    def beam(self, a, b, width, tile=0):
        from mathutils import Vector

        a, b = Vector(a), Vector(b)
        axis = (b - a).normalized()
        guide = Vector((0, 0, 1)) if abs(axis.z) < .9 else Vector((0, 1, 0))
        u = axis.cross(guide).normalized() * width / 2
        v = axis.cross(u).normalized() * width / 2
        low = [a - u - v, a + u - v, a + u + v, a - u + v]
        high = [p + b - a for p in low]
        self.face(list(reversed(low)), tile)
        self.face(high, tile)
        for i in range(4):
            j = (i + 1) % 4
            self.face([low[i], low[j], high[j], high[i]], tile)

    def derrick(self, x, y, height):
        self.box((x, y, -1.125), (7.2, 7.2, 3.75), 4)
        self.box((x, y, .85), (6.7, 6.7, .25), 5)

        def corners(z):
            radius = 2.8 - 2.05 * (z - 1) / (height - 1)
            return [(x + sx * radius, y + sy * radius, z)
                    for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))]

        for level in range(5):
            low = corners(1 + (height - 1) * level / 5)
            high = corners(1 + (height - 1) * (level + 1) / 5)
            tile = 0 if level < 3 else (2 if level == 3 else 1)
            for i in range(4):
                j = (i + 1) % 4
                self.beam(low[i], high[i], .34, tile)
                self.beam(high[i], high[j], .24, tile)
                self.beam(low[i], high[j], .16, tile)
                self.beam(low[j], high[i], .16, tile)
        self.box((x, y, height + .12), (2.2, 2.2, .24), 5)
        for dx in (-.65, .65):
            self.beam((x + dx, y, height + .25), (x + dx, y, height + 1.15), .2, 1)
        self.beam((x - .8, y, height + 1.15), (x + .8, y, height + 1.15), .28, 0)
        self.beam((x, y, 1), (x, y, height + 1), .11, 9)
        self.box((x, y, 2.1), (1.5, 1.5, 2.2), 1)
        self.box((x, y + 1.1, height * .62), (4.4, 2.9, .2), 5)
        for dx in (-2.1, 0, 2.1):
            self.beam((x + dx, y + 2.45, height * .62), (x + dx, y + 2.45, height * .62 + 1), .1, 7)
        self.beam((x - 2.1, y + 2.45, height * .62 + 1), (x + 2.1, y + 2.45, height * .62 + 1), .1, 7)
        # The ladder follows the tapered rear leg instead of floating vertically.
        for dx in (-.33, .33):
            self.beam((x + dx, y + 2.95, 1), (x + dx, y + .9, height), .09, 7)
        for step in range(1, int(height / .6)):
            z = step * .6
            ly = y + 2.95 - 2.05 * (z - 1) / (height - 1)
            self.beam((x - .33, ly, z), (x + .33, ly, z), .08, 7)


def geometry():
    g = OilfieldGeometry()
    for x, y, height in TOWERS:
        g.derrick(x, y, height)
        g.beam((x, y, 1.35), (x, -7, 1.35), .34, 6)
    g.beam((-8, -7, 1.35), (7, -7, 1.35), .4, 6)
    for x in (-3, 3):
        g.box((x, -10, -1.125), (5.2, 5.2, 3.75), 4)
        g.lathe(x, -10, [(2.1, .8), (2.1, 4.8), (1.95, 5.0), (.25, 5.3)], 3, 16)
        for z in (1.1, 3.0, 4.7):
            g.lathe(x, -10, [(2.14, z), (2.14, z + .12)], 0, 16)
        g.beam((x, -7, 1.35), (x, -10, 1.35), .34, 6)
        g.lathe(x, -10, [(.3, 5.3), (.3, 5.6)], 0, 8)
    g.box((9, 7, -1.125), (6, 5.2, 3.75), 4)
    g.box((9, 7, 2.4), (5.4, 4.6, 3.3), 10)
    g.box((9, 7, 4.15), (5.8, 5.0, .25), 1)
    g.box((8, 4.67, 2.1), (1.3, .08, 2.5), 5)
    g.box((10, 4.66, 2.9), (1.2, .08, 1), 8)
    g.beam((11, 8, 4.3), (11, 8, 6.1), .25, 0)
    return g


def ambient_text():
    lines = ['type = {', f'\ttype = "{NAME}_entity"', '\tuse_animation = no',
             f'\tscale = {SCALE:.6f}', '\talways_visible = yes']
    for index, site in enumerate(placements(), 1):
        x, y, z = site["position"]
        lines.extend(['\tobject = {', f'\t\tname = "{NAME}_{index}"',
                      f'\t\tposition = {{ {x:.3f} {y:.3f} {z:.3f} }}',
                      '\t\trotation = { 0 0 0 }', '\t}'])
    return "\n".join([*lines, '}'])


def ambient_block(original):
    """Find the unique top-level actor in both authored and Nudge formatting."""
    matches = [match for match in re.finditer(rb"(?ms)^type[ \t]*=[ \t]*\{.*?^\}", original)
               if re.search(rb'\btype\s*=\s*"' + NAME.encode() + rb'_entity"', match[0])]
    assert len(matches) == 1, "Expected one NAM oilfield actor"
    return matches[0][0]


def native_tokens(block):
    # Nudge drops comments and changes float precision without changing the actor.
    source = re.sub(rb"#[^\r\n]*", b"", block)
    tokens = re.findall(rb'"[^"\r\n]*"|[{}=]|[^\s{}=]+', source)
    result = []
    for token in tokens:
        try:
            result.append(float(token))
        except ValueError:
            result.append(token)
    return result


def section_outputs():
    blocks = {
        "gfx/entities/mapitems_custom.gfx": (
            'objectTypes = {\n\tpdxmesh = {\n\t\tname = "' + NAME + '_mesh"\n'
            '\t\tfile = "' + (MODEL_DIR / FILES[0]).as_posix() + '"\n'
            '\t\tscale = 1\n\t\tcull_distance = 1800\n\t}\n}'
        ),
        "gfx/entities/mapitems_custom.asset": (
            'entity = {\n\tname = "' + NAME + '_entity"\n\tpdxmesh = "' + NAME + '_mesh"\n}'
        ),
        "map/ambient_object.txt": ambient_text(),
    }
    result = {}
    start, end = "# BEGIN " + MARKER, "# END " + MARKER
    for relative, block in blocks.items():
        path = ROOT / relative
        original = path.read_bytes()
        newline = "\r\n" if b"\r\n" in original else "\n"
        section = (start + "\n# Generated by tools/builders/build_adiscord_nam_oilfields.py\n"
                   + block + "\n" + end + "\n").replace("\n", newline).encode()
        pattern = re.escape(start.encode()) + rb".*?" + re.escape(end.encode()) + rb"\r?\n?"
        matches = list(re.finditer(pattern, original, flags=re.S))
        assert len(matches) <= 1, path
        if matches:
            match = matches[0]
            result[path] = original[:match.start()] + section + original[match.end():]
        elif relative == "map/ambient_object.txt" and NAME.encode() in original:
            assert native_tokens(ambient_block(original)) == native_tokens(block.encode()), (
                "Oilfield placement changed in Nudge; reconcile placement inputs before rebuilding"
            )
            result[path] = original
        else:
            assert NAME.encode() not in original, f"Unowned palace entry in {path}"
            result[path] = original + newline.encode() + section
    return result


def build_native(stage):
    import bpy
    from mathutils import Vector
    from types import SimpleNamespace

    bpy.ops.wm.read_factory_settings(use_empty=True)
    pdx = load_exporter()
    g = geometry()
    obj = g.make_object()
    obj.name = obj.data.name = NAME
    obj.data.materials.append(pdx.create_shader(SimpleNamespace(
        shader=["PdxMeshAdvanced"], diff=[FILES[1]], n=[FILES[2]], spec=[FILES[3]],
    ), "Weathered steel, rust and concrete", str(stage)))
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    path = stage / FILES[0]
    pdx.export_meshfile(str(path), exp_selected=True, exp_skel=False, exp_locs=False)
    from io_pdx_mesh import pdx_data

    tree = pdx_data.read_meshfile(str(path))
    for shape in tree.find("object"):
        for mesh in shape.findall("mesh"):
            mesh.attrib["ta"] = [round(value, 5) for value in mesh.attrib["ta"]]
    pdx_data.write_meshfile(str(path), tree)
    bpy.ops.file.pack_all()
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type == "VIEW_3D":
                area.spaces.active.shading.type = "MATERIAL"
                region = area.spaces.active.region_3d
                region.view_location = (0, 0, 8)
                region.view_distance = 65
                region.view_rotation = Vector((42, -57, 39)).to_track_quat("Z", "Y")
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=str(stage / SOURCE.name))
    report = verify_native(stage, pdx)
    report["source_blend_sha256"] = digest(stage / SOURCE.name)
    (stage / "native.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


def verify_native(folder, pdx=None):
    import bpy
    from mathutils import Vector

    pdx = pdx or load_exporter()
    from io_pdx_mesh import pdx_data

    tree = pdx_data.read_meshfile(str(folder / FILES[0]))
    vertices = triangles = materials = 0
    for shape in tree.find("object"):
        for element in shape.findall("mesh"):
            data = pdx_data.PDXData(element)
            count = len(data.p) // 3
            assert 0 < count < 65536
            assert len(data.n) == count * 3 and len(data.u0) == count * 2 and len(data.ta) == count * 4
            assert all(math.isfinite(v) for v in data.p + data.n + data.u0 + data.ta)
            assert len(data.tri) % 3 == 0 and min(data.tri) >= 0 and max(data.tri) < count
            for i in range(0, len(data.tri), 3):
                a, b, c = [Vector(data.p[j * 3:j * 3 + 3]) for j in data.tri[i:i + 3]]
                assert (b - a).cross(c - a).length > 1e-8
            assert data.material.shader == ["PdxMeshAdvanced"]
            for key, expected in zip(("diff", "n", "spec"), FILES[1:]):
                assert getattr(data.material, key) == [expected]
                raw = (folder / expected).read_bytes()
                assert raw[:4] == b"DDS " and raw[84:88] == b"DXT5"
                assert struct.unpack_from("<I", raw, 28)[0] == 11
            vertices += count
            triangles += len(data.tri) // 3
            materials += 1
    assert triangles < 12000 and materials == 1
    bpy.ops.wm.read_factory_settings(use_empty=True)
    pdx.import_meshfile(str(folder / FILES[0]), imp_locs=False)
    meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    assert len(meshes) == 1
    points = [o.matrix_world @ v.co for o in meshes for v in o.data.vertices]
    bounds = [[round(min(v[i] for v in points), 5), round(max(v[i] for v in points), 5)] for i in range(3)]
    return {
        "files": {name: digest(folder / name) for name in FILES},
        "vertices": vertices, "triangles": triangles, "materials": materials,
        "bounds_blender_xyz": bounds, "native_reimport": True,
        "derricks_per_cluster": len(TOWERS),
        "hoi4_runtime_verified": False,
    }


def render_preview():
    import bpy
    from mathutils import Vector

    verify_native(ROOT / MODEL_DIR)
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.samples = 32
    scene.cycles.use_denoising = True
    scene.render.resolution_x = 1440
    scene.render.resolution_y = 1080
    scene.render.resolution_percentage = 100
    scene.world = bpy.data.worlds.new("Neutral architectural studio")
    scene.world.use_nodes = True
    scene.world.node_tree.nodes["Background"].inputs[0].default_value = (.42, .44, .48, 1)
    scene.world.node_tree.nodes["Background"].inputs[1].default_value = .55
    for material in bpy.data.materials:
        shader = material.node_tree.nodes.get("Principled BSDF") if material.use_nodes else None
        if shader:
            for link in list(shader.inputs["Roughness"].links):
                material.node_tree.links.remove(link)
            shader.inputs["Roughness"].default_value = .72
    bpy.ops.mesh.primitive_plane_add(size=200, location=(0, 0, 0))
    floor = bpy.context.object
    floor.name = "Studio floor, not exported"
    mat = bpy.data.materials.new("Warm neutral ground")
    mat.diffuse_color = (.32, .30, .27, 1)
    floor.data.materials.append(mat)
    for location, energy, size in (((-30, -38, 55), 32000, 22), ((32, -3, 28), 11000, 19), ((-5, 32, 45), 27000, 20)):
        bpy.ops.object.light_add(type="AREA", location=location)
        light = bpy.context.object
        light.data.energy = energy
        light.data.size = size
        light.rotation_euler = (Vector((0, 0, 8)) - light.location).to_track_quat("-Z", "Y").to_euler()
    bpy.ops.object.camera_add()
    camera = bpy.context.object
    camera.data.type = "ORTHO"
    scene.camera = camera
    (ROOT / PREVIEW).mkdir(parents=True, exist_ok=True)
    for name, position, target, scale in (
        ("three_quarter", (42, -57, 39), (0, 0, 11), 52),
        ("map", (35, -43, 67), (0, 0, 8), 51),
        ("rear", (-43, 57, 36), (0, 0, 11), 52),
    ):
        camera.location = position
        camera.rotation_euler = (Vector(target) - camera.location).to_track_quat("-Z", "Y").to_euler()
        camera.data.ortho_scale = scale
        scene.render.filepath = str(ROOT / PREVIEW / (name + ".png"))
        bpy.ops.render.render(write_still=True)


def stale_outputs():
    expected = section_outputs()
    expected.update({ROOT / MODEL_DIR / name: data for name, data in textures().items()})
    changed = [str(path.relative_to(ROOT)) for path, data in expected.items()
               if not path.exists() or path.read_bytes() != data]
    if not (ROOT / REPORT).exists():
        return changed + [REPORT.as_posix(), (MODEL_DIR / FILES[0]).as_posix(), SOURCE.as_posix()]
    report = json.loads((ROOT / REPORT).read_text(encoding="utf-8"))
    if report.get("input_sha256") != input_hashes() or not report.get("native_reimport"):
        changed.append(REPORT.as_posix())
    for name, expected_hash in report["files"].items():
        path = ROOT / MODEL_DIR / name
        if not path.exists() or digest(path) != expected_hash:
            changed.append(path.relative_to(ROOT).as_posix())
    if not (ROOT / SOURCE).exists() or digest(ROOT / SOURCE) != report.get("source_blend_sha256"):
        changed.append(SOURCE.as_posix())
    return sorted(set(changed))


def find_blender(explicit):
    candidates = [explicit, os.environ.get("BLENDER_EXE"), shutil.which("blender"),
                  "C:/Program Files/Blender Foundation/Blender 4.5/blender.exe"]
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return str(candidate)
    raise RuntimeError("Blender is required for --apply; provide --blender or BLENDER_EXE")


def run_blender(executable, arguments):
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    subprocess.run([executable, "--background", "--factory-startup", "--python-exit-code", "1",
                    "--python", str(Path(__file__)), "--", *arguments], check=True, env=env)


def apply(executable):
    hashes = input_hashes()
    with tempfile.TemporaryDirectory(prefix="adiscord-nam-oilfield-") as directory:
        stage = Path(directory)
        for name, data in textures().items():
            (stage / name).write_bytes(data)
        run_blender(executable, ["--build-dir", str(stage)])
        assert hashes == input_hashes(), "Model inputs changed during export"
        report = json.loads((stage / "native.json").read_text(encoding="utf-8"))
        report["input_sha256"] = hashes
        report["placements"] = placements()
        contents = {ROOT / MODEL_DIR / name: (stage / name).read_bytes() for name in FILES}
        contents[ROOT / SOURCE] = (stage / SOURCE.name).read_bytes()
        contents[ROOT / REPORT] = (json.dumps(report, indent=2) + "\n").encode()
        contents.update(section_outputs())
        for path, data in contents.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            if not path.exists() or path.read_bytes() != data:
                path.write_bytes(data)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--apply", action="store_true")
    mode.add_argument("--preview", action="store_true")
    mode.add_argument("--build-dir", type=Path, help=argparse.SUPPRESS)
    mode.add_argument("--render-native", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--blender")
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else None)
    if args.build_dir:
        build_native(args.build_dir)
        return
    if args.render_native:
        render_preview()
        return
    changed = stale_outputs()
    print(json.dumps({"stale": changed, "apply": args.apply}), flush=True)
    if args.apply and changed:
        apply(find_blender(args.blender))
        changed = stale_outputs()
        assert not changed, changed
    if args.preview:
        if changed:
            raise RuntimeError("Rebuild stale outputs before rendering")
        run_blender(find_blender(args.blender), ["--render-native"])
    raise SystemExit(bool(changed))


if __name__ == "__main__":
    main()
