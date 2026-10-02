"""Build the Khan bunker landmark and install its native HOI4 mesh.

Python: --output PATH --check, then --apply to stage textures.
Blender: --background --python this_file -- --output PATH --build
Python: --output PATH --install --check, then --apply, then --check.
Only marked sections of the shared map registries belong to this builder.
"""

import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import struct
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_shl_palace import Geometry, dds_bytes, load_exporter

ROOT = Path(__file__).resolve().parents[3]
NAME = "ADISCORD_RUS_khan_bunker"
MODEL_DIR = Path("gfx/models/buildings/RUS_bunker")
POSITION = (3481.85, 14.22, 945.9)
SCALE = 0.04
FILES = [f"{NAME}{suffix}" for suffix in (".mesh", "_diffuse.dds", "_normal.dds", "_specular.dds")]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def textures():
    import numpy as np
    from PIL import Image, ImageDraw, ImageFilter

    colors = [
        (115, 118, 105), (146, 145, 128), (86, 93, 72), (46, 54, 48),
        (82, 89, 72), (97, 98, 86), (126, 122, 103), (65, 70, 59),
        (158, 124, 55), (19, 25, 24), (96, 100, 65), (132, 72, 40),
        (166, 139, 57), (65, 78, 71), (106, 35, 29), (211, 181, 103),
    ]
    rng = np.random.default_rng(16531)
    atlas = Image.new("RGBA", (1024, 1024))
    relief = Image.new("L", atlas.size, 128)
    for index, color in enumerate(colors):
        noise = rng.normal(0, 4, (256, 256, 1))
        rgb = np.clip(np.array(color)[None, None, :] + noise, 0, 255).astype("uint8")
        tile = Image.fromarray(rgb).convert("RGBA")
        height = Image.new("L", (256, 256), 128)
        draw = ImageDraw.Draw(tile)
        hd = ImageDraw.Draw(height)
        if index in (0, 1, 5, 6):
            for y in (6, 126, 248):
                draw.line((0, y, 255, y), fill=tuple(int(c * .7) for c in color), width=2)
                hd.line((0, y, 255, y), fill=100, width=2)
            for x in (18, 238):
                for y in (28, 108, 148, 228):
                    draw.ellipse((x - 3, y - 3, x + 3, y + 3), fill=(73, 77, 69))
                    hd.ellipse((x - 3, y - 3, x + 3, y + 3), fill=90)
            for _ in range(25):
                x, y = rng.integers(5, 250, size=2)
                draw.line((int(x), int(y), int(x), min(255, int(y) + 25)),
                          fill=tuple(int(c * .87) for c in color), width=2)
        if index in (3, 4, 7):
            draw.rectangle((5, 5, 250, 250), outline=(31, 37, 32), width=5)
            for y in range(20, 250, 45):
                draw.line((10, y, 244, y), fill=(46, 54, 46), width=3)
                for x in (17, 239):
                    draw.ellipse((x - 3, y - 3, x + 3, y + 3), fill=(155, 148, 113))
        if index == 12:
            for x in range(-256, 512, 64):
                draw.polygon(((x, 0), (x + 30, 0), (x + 286, 256), (x + 256, 256)),
                             fill=(28, 33, 29))
        offset = ((index % 4) * 256, (index // 4) * 256)
        atlas.paste(tile, offset)
        relief.paste(height, offset)
    values = np.asarray(relief.filter(ImageFilter.GaussianBlur(1)), dtype=float)
    dy, dx = np.gradient(values)
    normals = np.zeros((1024, 1024, 4), dtype="uint8")
    normals[:, :, 0] = 255
    normals[:, :, 1] = np.clip(128 - dx * .65, 80, 176)
    normals[:, :, 3] = np.clip(128 + dy * .65, 80, 176)
    specular = Image.new("RGBA", atlas.size, (0, 24, 0, 20))
    sd = ImageDraw.Draw(specular)
    for index in (3, 4, 7, 8, 13):
        x, y = (index % 4) * 256, (index // 4) * 256
        sd.rectangle((x, y, x + 255, y + 255), fill=(0, 95, 0, 70))
    return {
        f"{NAME}_diffuse.dds": dds_bytes(atlas),
        f"{NAME}_normal.dds": dds_bytes(Image.fromarray(normals)),
        f"{NAME}_specular.dds": dds_bytes(specular),
    }


class BunkerGeometry(Geometry):
    def panel(self, points, tile, subdivide=False):
        if not subdivide:
            self.face(points, tile)
            return
        from mathutils import Vector

        a, b, c, d = map(Vector, points)
        nx = max(1, math.ceil(max((b - a).length, (c - d).length) / 4))
        ny = max(1, math.ceil(max((d - a).length, (c - b).length) / 4))

        def point(u, v):
            # Sloped bunker walls are trapezoids; preserve all four corners.
            return tuple(a * (1 - u) * (1 - v) + b * u * (1 - v)
                         + c * u * v + d * (1 - u) * v)

        for i in range(nx):
            for j in range(ny):
                self.face([point(i / nx, j / ny), point((i + 1) / nx, j / ny),
                           point((i + 1) / nx, (j + 1) / ny), point(i / nx, (j + 1) / ny)], tile)

    def tapered_block(self, x, y, bottom, top, width, depth, inset, tile):
        lower = [(x - width / 2, y - depth / 2, bottom),
                 (x + width / 2, y - depth / 2, bottom),
                 (x + width / 2, y + depth / 2, bottom),
                 (x - width / 2, y + depth / 2, bottom)]
        upper = [(px + (inset if px < x else -inset),
                  py + (inset if py < y else -inset), top) for px, py, _ in lower]
        self.face(list(reversed(lower)), tile)
        self.face(upper, tile)
        for i in range(4):
            j = (i + 1) % 4
            self.panel([lower[i], lower[j], upper[j], upper[i]], tile, True)

    def beam(self, a, b, radius=.065, tile=3):
        from mathutils import Vector

        a, b = Vector(a), Vector(b)
        direction = (b - a).normalized()
        side = direction.cross(Vector((0, 0, 1)))
        if side.length < .01:
            side = direction.cross(Vector((1, 0, 0)))
        side.normalize()
        up = direction.cross(side)
        ring = [radius * (side * math.cos(i * math.tau / 6) + up * math.sin(i * math.tau / 6))
                for i in range(6)]
        for i in range(6):
            j = (i + 1) % 6
            self.face([a + ring[i], a + ring[j], b + ring[j], b + ring[i]], tile)



def geometry():
    g = BunkerGeometry()
    g.tapered_block(0, 0, 0, 1.1, 34, 30, 1.2, 5)
    g.box((0, -10, 1.2), (25, 8, .2), 6)
    # The entry is a real recess between two structural wings, below the roof slab.
    for side in (-1, 1):
        g.tapered_block(side * 9.5, 0, 1.1, 6.8, 12, 20, 1.2, 0)
    g.box((0, 5, 3.9), (9, 10, 5.6), 0)
    g.tapered_block(0, 1, 6.7, 8.2, 29, 20, .75, 1)
    g.box((0, 1, 8.25), (25.7, 16.6, .15), 2)
    # Steel door leaves sit behind the concrete portal and its approach walls.
    g.box((0, -3.4, 3.6), (7.2, .8, 5), 9)
    for side in (-1, 1):
        g.box((side * 1.66, -3.95, 3.6), (3.24, .4, 4.7), 4)
        for z in (2, 3.65, 5.2):
            g.box((side * 1.66, -4.19, z), (3, .16, .2), 7)
        for z in (2.3, 4.9):
            g.box((side * 3.05, -4.26, z), (.35, .25, .48), 8)
        g.tapered_block(side * 4.3, -8, 1.1, 4.9, 2, 11, .25, 0)
        g.box((side * 3.54, -7.8, 4.9), (.28, 10.2, .22), 12)
    g.box((0, -7.9, 6.2), (10, 2.6, 1.7), 1)
    for x in (-3.5, 3.5):
        g.box((x, -9.32, 6.35), (.6, .25, .3), 15)
    # Flanking observation slits remain visible at the strategic-map camera angle.
    for side in (-1, 1):
        for x in (7.4, 11.5):
            g.box((side * x, -9.32, 4.8), (2.7, .15, .55), 9)
            g.box((side * x, -9.36, 5.25), (3.3, .6, .35), 1)
    g.tapered_block(-4, 3, 8.3, 10.7, 9, 7, .55, 0)
    g.box((-4, -.35, 9.5), (6.7, .16, .5), 9)
    g.box((-4, 3, 10.8), (8.5, 6.5, .4), 1)
    for x in (4.3, 8.2):
        g.box((x, 4.5, 9), (2.8, 4.3, 1.4), 7)
        for y in (3.05, 3.65, 4.25, 4.85, 5.45, 6.05):
            g.box((x, y, 9.74), (2.4, .23, .12), 3)
    for x in (-10.5, 10.5):
        g.lathe(x, 7.2, [(1, 8.3), (1, 9.4), (.8, 9.6), (.8, 10.7)], 3, 12)
        g.lathe(x, 7.2, [(1.25, 10.7), (1.25, 11), (.8, 11.3)], 7, 12)
    # Open lattice keeps the radio mast light in both silhouette and triangle count.
    for z0, z1 in ((8.3, 11.3), (11.3, 14.3), (14.3, 17.3)):
        for a, b in (((-9, 2), (-7, 2)), ((-7, 2), (-8, 3.7)), ((-8, 3.7), (-9, 2))):
            g.beam((*a, z0), (*a, z1), .085)
            g.beam((*a, z0), (*b, z1), .05)
            g.beam((*a, z1), (*b, z1), .06)
    g.beam((-8, 2.7, 16), (-8, 2.7, 20), .055)
    for z in (17.7, 18.5, 19.3):
        g.beam((-9.7, 2.7, z), (-6.3, 2.7, z), .04)
    for side in (-1, 1):
        for x in (6.5, 10, 13.5):
            g.tapered_block(side * x, -12.4, 1.3, 2.6, 1.4, 1.5, .3, 0)
    for y in (0, 3, 6):
        g.box((15.7, y, 2.05), (1.1, 2.4, 1.5), 7)
    return g


def terrain_height(x, z):
    data = terrain_height.data
    offset = struct.unpack_from("<I", data, 10)[0]
    w, h = struct.unpack_from("<ii", data, 18)
    stride = (w + 3) // 4 * 4
    ix, iz = math.floor(x), math.floor(z)
    assert 0 <= ix < w - 1 and 0 <= iz < abs(h) - 1
    values = [data[offset + (iz + dz if h > 0 else -h - 1 - iz - dz) * stride + ix + dx] / 10
              for dx, dz in ((0, 0), (1, 0), (0, 1), (1, 1))]
    fx, fz = x - ix, z - iz
    return (values[0] * (1 - fx) + values[1] * fx) * (1 - fz) + (values[2] * (1 - fx) + values[3] * fx) * fz


def load_terrain():
    terrain_height.data = (ROOT / "map/heightmap.bmp").read_bytes()
    data = terrain_height.data
    assert data[:2] == b"BM" and struct.unpack_from("<H", data, 28)[0] == 8
    assert struct.unpack_from("<I", data, 30)[0] == 0
    palette = 14 + struct.unpack_from("<I", data, 14)[0]
    assert all(data[palette + i * 4:palette + i * 4 + 3] == bytes([i, i, i]) for i in range(256))


def build(output):
    import bpy
    from mathutils import Vector
    from types import SimpleNamespace

    source_hash = digest(Path(__file__))
    bpy.ops.wm.read_factory_settings(use_empty=True)
    pdx = load_exporter()
    load_terrain()
    g = geometry()
    for i, (x, y, z) in enumerate(g.vertices):
        if abs(z) < 1e-8:
            ground = terrain_height(POSITION[0] + x * SCALE, POSITION[2] + y * SCALE)
            g.vertices[i] = (x, y, (ground - POSITION[1] - .025) / SCALE)
    obj = g.make_object()
    obj.name = obj.data.name = NAME
    folder = output / "package" / MODEL_DIR
    obj.data.materials.append(pdx.create_shader(SimpleNamespace(
        shader=["PdxMeshAdvanced"], diff=[f"{NAME}_diffuse.dds"],
        n=[f"{NAME}_normal.dds"], spec=[f"{NAME}_specular.dds"]
    ), "Khan bunker concrete and steel", str(folder)))
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    path = folder / f"{NAME}.mesh"
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
                region.view_location = (0, 0, 7)
                region.view_distance = 47
                region.view_rotation = Vector((34, -47, 24)).to_track_quat("Z", "Y")
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=str(output / "Khan_bunker.blend"))
    assert source_hash == digest(Path(__file__)), "Source changed during build"
    verify(output, pdx)


def verify(output, pdx=None):
    import bpy
    from mathutils import Vector

    pdx = pdx or load_exporter()
    from io_pdx_mesh import pdx_data

    folder = output / "package" / MODEL_DIR
    source_hash = digest(Path(__file__))
    heightmap_hash = digest(ROOT / "map/heightmap.bmp")
    hashes = {name: digest(folder / name) for name in FILES}
    tree = pdx_data.read_meshfile(str(folder / FILES[0]))
    vertices = triangles = 0
    for shape in tree.find("object"):
        for element in shape.findall("mesh"):
            data = pdx_data.PDXData(element)
            count = len(data.p) // 3
            assert 0 < count < 65536
            assert len(data.n) == count * 3 and len(data.u0) == count * 2 and len(data.ta) == count * 4
            assert all(math.isfinite(v) for v in data.p + data.n + data.u0 + data.ta)
            assert len(data.tri) % 3 == 0 and min(data.tri) >= 0 and max(data.tri) < count
            assert data.material.shader == ["PdxMeshAdvanced"]
            for key in ("diff", "n", "spec"):
                raw = (folder / getattr(data.material, key)[0]).read_bytes()
                assert raw[:4] == b"DDS " and raw[84:88] == b"DXT5"
                assert struct.unpack_from("<I", raw, 28)[0] == 11
            vertices += count
            triangles += len(data.tri) // 3
    assert triangles < 15000
    bpy.ops.wm.read_factory_settings(use_empty=True)
    pdx.import_meshfile(str(folder / FILES[0]), imp_locs=False)
    meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    points = [o.matrix_world @ v.co for o in meshes for v in o.data.vertices]
    bounds = [[round(min(v[i] for v in points), 5), round(max(v[i] for v in points), 5)] for i in range(3)]
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.samples = 24
    scene.cycles.use_denoising = True
    scene.render.resolution_x, scene.render.resolution_y = 1440, 1080
    scene.render.resolution_percentage = 100
    scene.world = bpy.data.worlds.new("Bunker studio")
    scene.world.use_nodes = True
    scene.world.node_tree.nodes["Background"].inputs[0].default_value = (.27, .31, .38, 1)
    scene.world.node_tree.nodes["Background"].inputs[1].default_value = .55
    for material in bpy.data.materials:
        shader = material.node_tree.nodes.get("Principled BSDF") if material.use_nodes else None
        if shader:
            roughness = shader.inputs["Roughness"]
            for link in list(roughness.links):
                material.node_tree.links.remove(link)
            roughness.default_value = .8
    bpy.ops.mesh.primitive_plane_add(size=200, location=(0, 0, -.2))
    floor = bpy.context.object
    floor.name = "Preview ground (not exported)"
    material = bpy.data.materials.new("Muted earth")
    material.diffuse_color = (.14, .17, .145, 1)
    floor.data.materials.append(material)
    for location, energy, size in (((-20, -28, 42), 20000, 17), ((24, -6, 25), 9000, 16), ((-8, 24, 35), 23000, 14)):
        bpy.ops.object.light_add(type="AREA", location=location)
        light = bpy.context.object
        light.data.energy, light.data.size = energy, size
        light.rotation_euler = (Vector((0, 0, 7)) - light.location).to_track_quat("-Z", "Y").to_euler()
    bpy.ops.object.camera_add()
    camera = bpy.context.object
    camera.data.type = "ORTHO"
    scene.camera = camera
    for suffix, location, target, scale in (
        ("preview", (34, -47, 34), (0, 0, 7), 47),
        ("front", (1, -55, 23), (0, 0, 7), 43),
        ("map", (28, -40, 58), (0, 0, 6), 46),
        ("rear", (-34, 44, 33), (0, 0, 7), 47),
    ):
        camera.location = location
        camera.rotation_euler = (Vector(target) - camera.location).to_track_quat("-Z", "Y").to_euler()
        camera.data.ortho_scale = scale
        scene.render.filepath = str(output / f"Khan_bunker_{suffix}.png")
        bpy.ops.render.render(write_still=True)
    assert hashes == {name: digest(folder / name) for name in FILES}, "Native inputs changed during verification"
    assert source_hash == digest(Path(__file__)), "Source changed during verification"
    assert heightmap_hash == digest(ROOT / "map/heightmap.bmp"), "Terrain changed during verification"
    report = {
        "files": hashes, "vertices": vertices, "triangles": triangles,
        "bounds_blender_xyz": bounds, "native_reimport": True,
        "placement": {"position": list(POSITION), "scale": SCALE},
        "heightmap_sha256": heightmap_hash,
        "source_sha256": source_hash, "hoi4_runtime_verified": False,
    }
    (output / "verification.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report), flush=True)


def write_changes(contents, apply):
    changed = [str(path) for path, data in contents.items() if not path.exists() or path.read_bytes() != data]
    print(json.dumps({"changed": changed, "apply": apply}), flush=True)
    if apply:
        for path, data in contents.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            if not path.exists() or path.read_bytes() != data:
                path.write_bytes(data)
    return changed


def stage(output, apply):
    folder = output / "package" / MODEL_DIR
    return write_changes({folder / name: raw for name, raw in textures().items()}, apply)


def install(output, apply):
    report = json.loads((output / "verification.json").read_text(encoding="utf-8"))
    assert report["native_reimport"]
    assert report["placement"] == {"position": list(POSITION), "scale": SCALE}
    assert report["heightmap_sha256"] == digest(ROOT / "map/heightmap.bmp")
    assert report["source_sha256"] == digest(Path(__file__))
    folder = output / "package" / MODEL_DIR
    assert report["files"] == {name: digest(folder / name) for name in FILES}
    contents = {ROOT / MODEL_DIR / name: (folder / name).read_bytes() for name in FILES}
    blocks = {
        "gfx/entities/mapitems_custom.gfx": (
            'objectTypes = {\n\tpdxmesh = {\n\t\tname = "' + NAME + '_mesh"\n'
            '\t\tfile = "' + (MODEL_DIR / FILES[0]).as_posix() + '"\n'
            '\t\tscale = 1\n\t\tcull_distance = 1800\n\t}\n}'
        ),
        "gfx/entities/mapitems_custom.asset": (
            'entity = {\n\tname = "' + NAME + '_entity"\n\tpdxmesh = "' + NAME + '_mesh"\n}'
        ),
        "map/ambient_object.txt": (
            'type = {\n\ttype = "' + NAME + '_entity"\n\tuse_animation = no\n'
            f'\tscale = {SCALE:.6f}\n\talways_visible = yes\n\tobject = {{\n'
            '\t\tname = "' + NAME + '"\n'
            f'\t\tposition = {{ {POSITION[0]:.3f} {POSITION[1]:.3f} {POSITION[2]:.3f} }}\n'
            '\t\trotation = { 0 0 0 }\n\t}\n}'
        ),
    }
    start, end = "# BEGIN ADISCORD Khan bunker", "# END ADISCORD Khan bunker"
    for relative, block in blocks.items():
        path = ROOT / relative
        original = path.read_bytes()
        newline = "\r\n" if b"\r\n" in original else "\n"
        section = (start + "\n# Generated by tools/assets/source/build_khan_bunker.py\n" + block + "\n" + end + "\n").replace("\n", newline).encode()
        pattern = re.escape(start.encode()) + rb".*?" + re.escape(end.encode()) + rb"\r?\n?"
        matches = list(re.finditer(pattern, original, flags=re.S))
        assert len(matches) <= 1, path
        if matches:
            match = matches[0]
            contents[path] = original[:match.start()] + section + original[match.end():]
        else:
            assert NAME.encode() not in original, f"Unowned bunker entry in {path}"
            contents[path] = original + newline.encode() + section
    return write_changes(contents, apply)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    mode = parser.add_mutually_exclusive_group(required=True)
    for name in ("check", "apply", "build", "verify"):
        mode.add_argument("--" + name, action="store_true")
    parser.add_argument("--install", action="store_true")
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else None)
    output = args.output.resolve()
    if args.build:
        build(output)
    elif args.verify:
        verify(output)
    else:
        changed = install(output, args.apply) if args.install else stage(output, args.apply)
        if args.check:
            raise SystemExit(bool(changed))


if __name__ == "__main__":
    main()
