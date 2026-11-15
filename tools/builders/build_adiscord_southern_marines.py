"""Build the shared landing vest on the southern infantry rig. Run with --check or --apply."""

import argparse
from collections import defaultdict
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/assets/source"))

from build_headquarters import dds, pdx_tools
from build_northern_infantry import ARAB_TAGS, blocks


MODELS = Path("gfx/models/units/ADISCORD_regulars")
DONOR = ROOT / MODELS / "ARB_field.mesh"
NAME = "ADISCORD_southern_marine"
TEXTURE = "southern_marine_flotation.dds"
TAGS = ("EFL", *ARAB_TAGS, "SHL", "SFD", "SCD", "SMD", "SOD", "SDA")
MESH = MODELS / "southern_marine.mesh"
REPORT = Path("docs/development/model-verification/southern_marines.json")


def remove_forearm_shield(mesh):
    """Remove the buckler and both braces without cutting the sleeve or hand."""
    points = [tuple(round(v, 4) for v in xyz) for xyz in zip(*[iter(mesh.get("p"))] * 3)]
    triangles = list(zip(*[iter(mesh.get("tri"))] * 3))
    neighbors = defaultdict(set)
    for a, b, c in triangles:
        for i, j in ((a, b), (b, c), (c, a)):
            neighbors[points[i]].add(points[j])
            neighbors[points[j]].add(points[i])
    shield = set()
    sizes = []
    while neighbors:
        pending = [next(iter(neighbors))]
        island = set()
        while pending:
            point = pending.pop()
            if point not in island:
                island.add(point)
                pending.extend(neighbors.pop(point))
        if min(x for x, y, z in island) > 1.3 and max(y for x, y, z in island) > 5.0:
            shield.update(island)
            sizes.append(len(island))
    assert sorted(sizes) == [28, 32, 62], "Field shield topology changed"
    mesh.set("tri", [i for tri in triangles if points[tri[0]] not in shield for i in tri])


def build_mesh(destination):
    import bpy
    from mathutils import Vector

    pdx, native = pdx_tools()
    tree = native.read_meshfile(str(DONOR))
    shape = tree.find("object")[0]
    remove_forearm_shield(shape.find("mesh"))
    spine = shape.find("skeleton").find("back_mid").get("ix")[0]

    # The two cork panels wrap from the waist over the shoulders. The outer
    # face follows the widening chest and clears the scarf on the native rig.
    sections = (
        (.37, -.49, 4.55, .24, .07), (.37, -.56, 4.65, .28, .14),
        (.40, -.56, 5.10, .31, .18), (.44, -.51, 5.55, .31, .17),
        (.49, -.39, 5.87, .28, .15), (.51, -.18, 6.05, .25, .13),
        (.52, .09, 6.06, .24, .13), (.50, .35, 5.89, .25, .13),
        (.45, .51, 5.56, .29, .14), (.39, .58, 5.13, .28, .15),
        (.38, .55, 4.72, .25, .12), (.38, .49, 4.62, .22, .06),
    )
    sides = 16
    vertices, faces, uvs = [], [], []
    for side in (-1, 1):
        first = len(vertices)
        for index, (x, y, z, width, depth) in enumerate(sections):
            before = sections[max(index - 1, 0)]
            after = sections[min(index + 1, len(sections) - 1)]
            outward = Vector((0, before[2] - after[2], after[1] - before[1])).normalized()
            for j in range(sides):
                angle = math.tau * j / sides
                vertices.append(Vector((side * x + width * math.cos(angle), y, z))
                                + outward * depth * math.sin(angle))
        for index in range(len(sections) - 1):
            for j in range(sides):
                a = first + sides * index
                k = (j + 1) % sides
                faces.append((a + j, a + j + sides, a + k + sides, a + k))
                low, high = index / (len(sections) - 1), (index + 1) / (len(sections) - 1)
                uvs.extend(((j / sides, low), (j / sides, high),
                            ((j + 1) / sides, high), ((j + 1) / sides, low)))
        for offset, ring in ((0, range(sides)), (len(sections) - 1, reversed(range(sides)))):
            ring = list(ring)
            for j in range(1, sides - 1):
                triangle = (ring[0], ring[j], ring[j + 1])
                faces.append(tuple(first + offset * sides + k for k in triangle))
                uvs.extend((.5 + .12 * math.cos(k * math.tau / sides),
                            .5 + .04 * math.sin(k * math.tau / sides)) for k in triangle)

    # The two front closures run underneath the padded sections.
    for height in (4.85, 5.38):
        first = len(vertices)
        for x, y in ((-.27, -.62), (-.09, -.65), (.09, -.65), (.27, -.62)):
            vertices.extend(((x, y, height), (x, y, height + .085)))
        for j in range(0, 6, 2):
            faces.append(tuple(first + j + k for k in (0, 2, 3, 1)))
            uvs.extend(((0, .12), (1, .12), (1, .134), (0, .134)))

    mesh = bpy.data.meshes.new("Cork landing vest")
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    atlas = mesh.uv_layers.new()
    for loop, uv in zip(atlas.data, uvs, strict=True):
        loop.uv = uv
    for face in mesh.polygons:
        face.use_smooth = len(face.vertices) == 4
    obj = bpy.data.objects.new(mesh.name, mesh)
    geom, ids = pdx.get_mesh_info(obj, 0)
    vest = ET.Element("mesh", {key: geom[key] for key in ("p", "n", "ta", "u0", "tri", "boundingsphere")})
    ET.SubElement(vest, "aabb", {key: geom[key] for key in ("min", "max")})
    ET.SubElement(vest, "material", dict(shader=["PdxMeshAdvanced"], diff=[TEXTURE],
                                         n=["ARB_field_gear_normal.dds"], spec=["ARB_field_gear_specular.dds"]))
    ET.SubElement(vest, "skin", dict(bones=[4], ix=[spine, 0, 0, 0] * len(ids),
                                     w=[1., 0., 0., 0.] * len(ids)))
    shape.insert(list(shape).index(shape.find("skeleton")), vest)
    native.write_meshfile(str(destination), tree)
    # Keep the exact weapon and animation attachment transforms from the field model.
    marker = b"[locator\0"
    data, donor = destination.read_bytes(), DONOR.read_bytes()
    destination.write_bytes(data[:data.index(marker)] + donor[donor.index(marker):])
    loaded = native.read_meshfile(str(destination))
    exported = loaded.find("object")[0].findall("mesh")[-1]
    assert exported.find("skin").attrib == vest.find("skin").attrib
    assert exported.get("tri") == geom["tri"]


def canvas_texture():
    from PIL import Image, ImageDraw

    image = Image.new("RGB", (128, 256))
    pixels = image.load()
    for y in range(image.height):
        for x in range(image.width):
            weave = (x % 3 - 1) * 3 + (y % 4 - 2) * 2
            pixels[x, y] = (43 + weave, 75 + weave, 80 + weave)
    draw = ImageDraw.Draw(image)
    for y in (32, 101, 161, 220):
        draw.rectangle((0, y, 127, y + 8), fill=(71, 61, 43))
        for x in range(0, 128, 4):
            draw.line((x, y + 1, x + 1, y + 1), fill=(168, 145, 96))
    for y in (92, 148):
        draw.rectangle((17, y, 47, y + 5), fill=(192, 158, 84))
    return dds(image)


def bindings():
    source = (ROOT / "gfx/entities/ADISCORD_specialists.gfx").read_text(encoding="utf-8")
    base = next(b for b in blocks(source, "pdxmesh") if 'name = "ADISCORD_STP_marine_mesh"' in b)
    base = base.replace("ADISCORD_STP_marine_mesh", NAME + "_mesh")
    base = base.replace("gfx/models/units/ADISCORD_specialists/STP_marine.mesh",
                        (MODELS / "southern_marine.mesh").as_posix())
    entities = [f'entity = {{\n\tclone = "ADISCORD_STP_marine_entity"\n\tname = "{NAME}_entity"\n'
                f'\tpdxmesh = "{NAME}_mesh"\n}}']
    pools = []
    for tag in TAGS:
        for role in ("marines", "ADISCORD_marine_infantry"):
            entities.append(f'entity = {{\n\tclone = "{NAME}_entity"\n\tname = "{tag}_{role}_entity"\n}}')
        pools.append(f"{tag} = {{\n\tinfantry_equipment = {{\n\t\tpool = {{\n"
                     f"\t\t\tsub_units = {{ ADISCORD_marine_infantry }}\n\t\t\tweight = 3000\n"
                     f"\t\t\tmodels = {{ {NAME}_entity }}\n\t\t}}\n\t}}\n}}")
    header = "# Generated by tools/builders/build_adiscord_southern_marines.py\n"
    return {
        Path("gfx/entities/ADISCORD_southern_marines.gfx"): header + "objectTypes = {\n\t" + base + "\n}\n",
        Path("gfx/entities/zzzz_ADISCORD_southern_marines.asset"): header + "\n\n".join(entities) + "\n",
        Path("gfx/interface/equipmentdesigner/graphic_db/ADISCORD_southern_marines.txt"):
            header + "\n\n".join(pools) + "\n",
    }


def verification(mesh):
    return {
        "builder": hashlib.sha256(Path(__file__).read_text(encoding="utf-8").encode()).hexdigest(),
        "donor": hashlib.sha256(DONOR.read_bytes()).hexdigest(),
        "mesh": hashlib.sha256(mesh).hexdigest(),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--blender", default="C:/Program Files/Blender Foundation/Blender 4.5/blender.exe")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    outputs = {path: source.encode() for path, source in bindings().items()}
    outputs[MODELS / TEXTURE] = canvas_texture()
    if args.apply:
        with tempfile.TemporaryDirectory() as staging:
            mesh = Path(staging) / MESH.name
            subprocess.run([args.blender, "--background", "--factory-startup", "--threads", "2",
                            "--python-exit-code", "1", "--python", __file__, "--", str(mesh)], check=True)
            outputs[MESH] = mesh.read_bytes()
    elif (ROOT / MESH).is_file():
        outputs[MESH] = (ROOT / MESH).read_bytes()
    else:
        print(f"Missing {MESH}")
        return 1
    outputs[REPORT] = (json.dumps(verification(outputs[MESH]), indent=2) + "\n").encode()
    changed = [p for p, data in outputs.items() if not (ROOT / p).exists() or (ROOT / p).read_bytes() != data]
    for path in changed:
        print(path)
        if args.apply:
            (ROOT / path).write_bytes(outputs[path])
    print(f"{len(changed)} changed outputs")
    return bool(changed) and not args.apply


if __name__ == "__main__":
    if "--" in sys.argv:
        build_mesh(Path(sys.argv[sys.argv.index("--") + 1]))
    else:
        sys.exit(main())
