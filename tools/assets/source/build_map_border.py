"""Build and install the native map frame and relief of the existing game logo.

Python: --output PATH --check
Python: --output PATH --apply --blender PATH
Python: --output PATH --install --check, then --install --apply
Blender: --background --factory-startup --python this_file -- --output PATH --build
The installer owns only marked sections of the existing map/entity registries.
"""

import argparse
from collections import defaultdict
import hashlib
import io
import json
import math
from pathlib import Path
import re
import struct
import subprocess
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[3]
MODEL_DIR = Path("gfx/models/mapitems/ADISCORD_map_border")
LOGO = ROOT / "gfx/interface/logo_game.dds"
PREFIX = "ADISCORD_map_border"
MARKER = "ADISCORD map border"
SCALE = 100.0
RAIL_DEPTH = 1.0
RAIL_HEIGHT_FACTOR = 0.4
RAIL_FRONT_INSET = 2.0
LOGO_WIDTH = 8.3
LOGO_DEPTH = 1.32
LOGO_FRONT_INSET = 3.0
COLORS = (
    (43, 52, 54),
    (133, 119, 88),
    (24, 29, 30),
    (196, 199, 186),
    (57, 67, 67),
    (76, 81, 76),
    (169, 154, 115),
    (94, 103, 101),
)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def dds_bytes(image):
    """Downsample packed channels independently, including normal-map alpha."""
    from PIL import Image

    levels = []
    while True:
        stream = io.BytesIO()
        image.save(stream, format="DDS", pixel_format="DXT5")
        levels.append(stream.getvalue())
        if image.size == (1, 1):
            break
        size = tuple(max(1, value // 2) for value in image.size)
        image = Image.merge(
            "RGBA", tuple(c.resize(size, Image.Resampling.BOX) for c in image.split())
        )
    header = bytearray(levels[0][:128])
    struct.pack_into("<I", header, 8, struct.unpack_from("<I", header, 8)[0] | 0x20000)
    struct.pack_into("<I", header, 28, len(levels))
    struct.pack_into("<I", header, 108, 0x401008)
    return bytes(header) + b"".join(level[128:] for level in levels)


def simplify(points, tolerance=1.0):
    if len(points) <= 2:
        return points
    ax, ay = points[0]
    bx, by = points[-1]
    dx, dy = bx - ax, by - ay
    denominator = dx * dx + dy * dy
    distances = []
    for x, y in points[1:-1]:
        t = max(0, min(1, ((x - ax) * dx + (y - ay) * dy) / denominator))
        distances.append(math.hypot(x - ax - t * dx, y - ay - t * dy))
    distance = max(distances, default=0)
    if distance <= tolerance:
        return [points[0], points[-1]]
    index = distances.index(distance) + 1
    return simplify(points[: index + 1], tolerance)[:-1] + simplify(points[index:], tolerance)


def logo_contours(image):
    """Trace opaque light strokes, retaining counters inside letters and ornaments."""
    import numpy as np

    rgba = np.asarray(image.convert("RGBA"))
    mask = (rgba[:, :, 3] > 127) & (rgba[:, :, :3].max(axis=2) > 127)
    padded = np.pad(mask, 1)
    edges = defaultdict(list)
    neighbors = (
        (padded[:-2, 1:-1], (0, 0), (1, 0)),
        (padded[1:-1, 2:], (1, 0), (1, 1)),
        (padded[2:, 1:-1], (1, 1), (0, 1)),
        (padded[1:-1, :-2], (0, 1), (0, 0)),
    )
    for neighbor, start, end in neighbors:
        ys, xs = np.nonzero(mask & ~neighbor)
        for x, y in zip(xs.tolist(), ys.tolist()):
            edges[x + start[0], y + start[1]].append((x + end[0], y + end[1]))
    directions = {(1, 0): 0, (0, 1): 1, (-1, 0): 2, (0, -1): 3}
    contours = []
    while edges:
        start = next(iter(edges))
        point = start
        incoming = 0
        ring = [point]
        while True:
            candidates = edges[point]
            # A right turn keeps diagonally touching strokes in separate loops.
            target = min(
                candidates,
                key=lambda p: (1, 0, 3, 2)[
                    (directions[p[0] - point[0], p[1] - point[1]] - incoming) % 4
                ],
            )
            candidates.remove(target)
            if not candidates:
                del edges[point]
            incoming = directions[target[0] - point[0], target[1] - point[1]]
            point = target
            ring.append(point)
            if point == start:
                break
        area = sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(ring, ring[1:])) / 2
        if abs(area) < 4:
            continue
        pivot = max(range(1, len(ring) - 1), key=lambda i: math.dist(ring[0], ring[i]))
        simple = simplify(ring[: pivot + 1])[:-1] + simplify(ring[pivot:])[:-1]
        if len(simple) >= 3:
            contours.append(simple)
    return contours


def horizontal_logo_contours(contours):
    """Keep each original glyph and its counters while aligning the word baselines."""
    groups = defaultdict(list)
    for ring in contours:
        xs, ys = zip(*ring)
        left, right, top, bottom = min(xs), max(xs), min(ys), max(ys)
        if left >= 250 and right <= 800 and top >= 110 and bottom <= 330:
            groups["abyss"].append(ring)
        elif left >= 890 and right <= 1090 and top >= 110 and bottom <= 330:
            groups["of"].append(ring)
        elif top >= 380:
            groups["discord"].append(ring)
        elif right <= 335 and bottom <= 270:
            groups["left_ornament"].append(ring)
        elif left >= 1005 and bottom <= 270:
            groups["right_ornament"].append(ring)
    assert all(groups[name] for name in ("abyss", "of", "discord", "left_ornament", "right_ornament"))

    def bounds(rings):
        points = [point for ring in rings for point in ring]
        xs, ys = zip(*points)
        return min(xs), max(xs), min(ys), max(ys)

    text = []
    cursor = 0.0
    for word, baseline, cap_height in (("abyss", 277, 162), ("of", 277, 162), ("discord", 634, 247)):
        rings = groups[word]
        left, right, _, _ = bounds(rings)
        factor = 0.66 / cap_height
        text.extend([
            [(cursor + (x - left) * factor, (baseline - y) * factor) for x, y in ring]
            for ring in rings
        ])
        cursor += (right - left) * factor + 0.18
    left, right, bottom, top = bounds(text)
    center_x, center_y = (left + right) / 2, (bottom + top) / 2
    result = [[(x - center_x, y - center_y) for x, y in ring] for ring in text]
    text_half_width = (right - left) / 2
    for side, name in ((-1, "left_ornament"), (1, "right_ornament")):
        rings = groups[name]
        left, right, top, bottom = bounds(rings)
        factor = 0.70 / (bottom - top)
        ornament_width = (right - left) * factor
        center = side * (text_half_width + 0.22 + ornament_width / 2)
        result.extend([
            [(center + (x - (left + right) / 2) * factor, ((top + bottom) / 2 - y) * factor)
             for x, y in ring]
            for ring in rings
        ])
    left, right, bottom, top = bounds(result)
    assert right - left < LOGO_WIDTH - 0.45
    assert top - bottom < LOGO_DEPTH - 0.34
    return result


def stage_contents(output):
    import numpy as np
    from PIL import Image

    diffuse = Image.new("RGBA", (256, 128), (0, 0, 0, 255))
    specular = Image.new("RGBA", diffuse.size)
    rng = np.random.default_rng(2160)
    for index, color in enumerate(COLORS):
        grain = rng.normal(0, 1.3, (64, 64, 1))
        brushed = rng.normal(0, 0.8, (64, 1, 1))
        values = np.clip(np.array(color) + grain + brushed, 0, 255).astype("uint8")
        tile = Image.fromarray(values).convert("RGBA")
        xy = (index % 4 * 64, index // 4 * 64)
        diffuse.paste(tile, xy)
        metal = index in (1, 3, 6, 7)
        properties = (0, 105 if metal else 45, 155 if metal else 30, 115 if metal else 55)
        specular.paste(properties, (*xy, xy[0] + 64, xy[1] + 64))
    normal = Image.new("RGBA", diffuse.size, (255, 128, 0, 128))
    folder = output / "package" / MODEL_DIR
    contents = {
        folder / f"{PREFIX}_diffuse.dds": dds_bytes(diffuse),
        folder / f"{PREFIX}_normal.dds": dds_bytes(normal),
        folder / f"{PREFIX}_specular.dds": dds_bytes(specular),
    }
    with Image.open(LOGO) as image:
        contours = logo_contours(image)
        with Image.open(ROOT / "map/provinces.bmp") as provinces:
            map_size = provinces.size
        data = {
            "logo_size": image.size,
            "logo_sha256": sha(LOGO.read_bytes()),
            "map_size": map_size,
            "source_sha256": sha(Path(__file__).read_bytes()),
            "contours": contours,
        }
    contents[output / "source.json"] = (json.dumps(data, separators=(",", ":")) + "\n").encode()
    return contents


def write_contents(contents, apply):
    changed = [path for path, data in contents.items() if not path.exists() or path.read_bytes() != data]
    print(json.dumps({"changed": [str(p) for p in changed], "apply": apply}), flush=True)
    if apply:
        for path in changed:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(contents[path])
    return changed


def load_exporter():
    import inspect

    extensions = Path.home() / "AppData/Roaming/Blender Foundation/Blender"
    candidates = sorted(extensions.glob("*/extensions/user_default/io_pdx_mesh/pdx_data.py"))
    if not candidates:
        raise RuntimeError("An installed IO PDX Mesh exporter is required")
    sys.path.insert(0, str(candidates[-1].parents[1]))
    from io_pdx_mesh.pdx_blender import blender_import_export as pdx

    source = inspect.getsource(pdx.create_shader)
    for line in ('    new_shader.shadow_method = "CLIP"', '    new_shader.blend_method = "CLIP"'):
        source = source.replace(line, "")
    exec(compile(source, "<Blender material compatibility>", "exec"), pdx.__dict__)
    return pdx


def assign_uv(obj, tile):
    """Use face-local projection so vertical sides also have nondegenerate tangents."""
    obj.data.update()
    uv = obj.data.uv_layers.get("UVMap") or obj.data.uv_layers.new(name="UVMap")
    obj.data.uv_layers.active = uv
    uv.active_render = True
    low = [min(v.co[a] for v in obj.data.vertices) for a in range(3)]
    span = [max(v.co[a] for v in obj.data.vertices) - low[a] for a in range(3)]
    for face in obj.data.polygons:
        axes = sorted(range(3), key=lambda i: abs(face.normal[i]))[:2]
        points = [obj.data.vertices[obj.data.loops[i].vertex_index].co for i in face.loop_indices]
        for loop_index, point in zip(face.loop_indices, points):
            u, v = [(point[a] - low[a]) / max(span[a], 1e-8) for a in axes]
            uv.data[loop_index].uv = ((tile % 4 + 0.15 + u * 0.7) / 4, 1 - (tile // 4 + 0.15 + v * 0.7) / 2)


def build_geometry(source):
    import bpy

    parts = []

    def box(name, center, dimensions, tile, bevel=0.025):
        bpy.ops.mesh.primitive_cube_add(size=1, location=center)
        obj = bpy.context.object
        obj.name = name
        obj.dimensions = dimensions
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        if bevel:
            modifier = obj.modifiers.new("Machined edges", "BEVEL")
            modifier.width = bevel
            modifier.segments = 2
            bpy.ops.object.modifier_apply(modifier=modifier.name)
        assign_uv(obj, tile)
        parts.append(obj)
        return obj

    def bolt(x, y, z, size=1.0):
        bpy.ops.mesh.primitive_cylinder_add(
            vertices=8, radius=0.052 * size, depth=0.025 * size, location=(x, y, z)
        )
        obj = bpy.context.object
        obj.name = "Recessed octagonal fastener"
        assign_uv(obj, 7)
        parts.append(obj)
        box(
            "Fastener slot", (x, y, z + 0.014 * size),
            (0.062 * size, 0.012 * size, 0.004 * size), 2, 0,
        )

    def rail_box(name, center, dimensions, tile, bevel):
        depth_factor = RAIL_DEPTH / 2.7
        x, y, z = center
        width, depth, height = dimensions
        return box(
            name, (x, y * depth_factor, z * RAIL_HEIGHT_FACTOR),
            (width, depth * depth_factor, height * RAIL_HEIGHT_FACTOR),
            tile, bevel * RAIL_HEIGHT_FACTOR,
        )

    def join(name):
        bpy.ops.object.select_all(action="DESELECT")
        for obj in parts:
            obj.select_set(True)
        bpy.context.view_layer.objects.active = parts[0]
        bpy.ops.object.join()
        obj = bpy.context.object
        obj.name = name
        bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
        parts.clear()
        return obj

    width = source["map_size"][0] / SCALE
    rail_box("Solid perimeter backing", (width / 2, 1.35, 0.00), (width, 2.7, 0.30), 2, 0.06)
    rail_box("Gunmetal frame", (width / 2, 1.35, 0.15), (width, 2.58, 0.26), 0, 0.08)
    for y in (0.19, 2.51):
        rail_box("Raised bronze rail", (width / 2, y, 0.28), (width, 0.17, 0.20), 1, 0.035)
    for y in (0.40, 2.30):
        rail_box("Fine steel inlay", (width / 2, y, 0.295), (width, 0.035, 0.045), 7, 0.01)
    for index in range(24):
        span = width / 24
        x = (index + 0.5) * span
        rail_box("Recessed panel", (x, 1.35, 0.27), (span - 0.07, 1.67, 0.035), 2, 0.014)
        rail_box("Brushed panel face", (x, 1.35, 0.30), (span - 0.15, 1.54, 0.045), 4, 0.02)
        for offset in (-0.43, 0, 0.43):
            rail_box("Inset vent", (x + offset, 1.35, 0.326), (0.095, 0.65, 0.008), 2, 0.003)
        for dx in (-span / 2 + 0.23, span / 2 - 0.23):
            for y in (0.75, 1.95):
                bolt(x + dx, y * RAIL_DEPTH / 2.7, 0.35 * RAIL_HEIGHT_FACTOR, size=0.6)
        if index % 3 == 0:
            rail_box("Service badge", (x, 0.87, 0.338), (0.34, 0.045, 0.018), 6, 0.006)
    rail = join(PREFIX)

    box("Emblem mounting block", (0, 0, 0.12), (LOGO_WIDTH, LOGO_DEPTH, 0.12), 2, 0.045)
    box("Bronze emblem surround", (0, 0, 0.175), (LOGO_WIDTH - 0.10, LOGO_DEPTH - 0.08, 0.085), 1, 0.035)
    box("Blackened emblem bed", (0, 0, 0.21), (LOGO_WIDTH - 0.24, LOGO_DEPTH - 0.20, 0.055), 0, 0.025)
    box("Inset emblem field", (0, 0, 0.242), (LOGO_WIDTH - 0.42, LOGO_DEPTH - 0.32, 0.015), 2, 0.012)
    for x in (-LOGO_WIDTH / 2 + 0.10, LOGO_WIDTH / 2 - 0.10):
        for y in (-LOGO_DEPTH / 2 + 0.11, LOGO_DEPTH / 2 - 0.11):
            bolt(x, y, 0.224, size=0.4)
    curve = bpy.data.curves.new("Original logo contours", "CURVE")
    curve.dimensions = "2D"
    curve.resolution_u = 1
    curve.fill_mode = "BOTH"
    curve.extrude = 0.018
    # The fine ornamental strokes are narrower than a bevel at map scale.
    # A flat-topped extrusion retains their silhouette without intersecting rims.
    curve.bevel_depth = 0.0
    for points in horizontal_logo_contours(source["contours"]):
        spline = curve.splines.new("POLY")
        spline.points.add(len(points) - 1)
        for point, (x, y) in zip(spline.points, points):
            point.co = (x, y, 0, 1)
        spline.use_cyclic_u = True
    obj = bpy.data.objects.new("Raised silver logo and ornament", curve)
    bpy.context.collection.objects.link(obj)
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.convert(target="MESH")
    obj = bpy.context.object
    obj.location.z = 0.271
    assign_uv(obj, 3)
    parts.append(obj)
    plaque = join(PREFIX + "_logo")
    return rail, plaque


def check_native(path, pdx_data):
    import numpy as np

    root = pdx_data.read_meshfile(str(path))
    vertices = triangles = 0
    bounds = []
    for shape in root.find("object"):
        for mesh in shape.findall("mesh"):
            data = pdx_data.PDXData(mesh)
            count = len(data.p) // 3
            assert 0 < count < 65536, (path, count)
            assert len(data.n) == count * 3 and len(data.ta) == count * 4
            assert len(data.u0) == count * 2
            assert all(math.isfinite(v) for v in data.p + data.n + data.ta + data.u0)
            normals = np.array(data.n).reshape(-1, 3)
            tangents = np.array(data.ta).reshape(-1, 4)[:, :3]
            assert np.all(np.abs(np.linalg.norm(normals, axis=1) - 1) < 1e-4)
            assert np.all(np.abs(np.linalg.norm(tangents, axis=1) - 1) < 1e-4)
            assert np.all(np.abs(np.sum(normals * tangents, axis=1)) < 1e-4)
            assert len(data.tri) % 3 == 0 and min(data.tri) >= 0 and max(data.tri) < count
            positions = np.array(data.p).reshape(-1, 3)
            faces = np.array(data.tri).reshape(-1, 3)
            points = positions[faces]
            areas = np.linalg.norm(np.cross(points[:, 1] - points[:, 0], points[:, 2] - points[:, 0]), axis=1)
            assert np.all(areas > 1e-8), (path, "degenerate triangles")
            face_normals = np.cross(points[:, 1] - points[:, 0], points[:, 2] - points[:, 0])
            assert np.all(np.sum(face_normals * normals[faces].mean(axis=1), axis=1) > 0)
            texcoords = np.array(data.u0).reshape(-1, 2)[faces]
            first = texcoords[:, 1] - texcoords[:, 0]
            second = texcoords[:, 2] - texcoords[:, 0]
            uv_area = first[:, 0] * second[:, 1] - first[:, 1] * second[:, 0]
            assert np.all(np.abs(uv_area) > 1e-14), (path, "degenerate UVs")
            assert data.material.shader == ["PdxMeshBorder"]
            for key in ("diff", "n", "spec"):
                assert (path.parent / getattr(data.material, key)[0]).read_bytes()[:4] == b"DDS "
            low = [min(data.p[axis::3]) for axis in range(3)]
            high = [max(data.p[axis::3]) for axis in range(3)]
            assert data.aabb.min == low and data.aabb.max == high
            bounds.append([low, high])
            vertices += count
            triangles += len(data.tri) // 3
    return {
        "vertices": vertices,
        "triangles": triangles,
        "bounds": bounds,
        "degenerate_triangles": 0,
        "degenerate_uvs": 0,
        "invalid_tangents": 0,
        "sha256": sha(path.read_bytes()),
    }


def export_native(obj, path, pdx_data):
    """Deduplicate loop vertices in linear time; export Y-up with reversed winding."""
    import bmesh
    from mathutils import Vector
    import xml.etree.ElementTree as ET

    mesh = obj.data
    triangles = bmesh.new()
    triangles.from_mesh(mesh)
    bmesh.ops.remove_doubles(triangles, verts=list(triangles.verts), dist=0.000001)
    bmesh.ops.triangulate(triangles, faces=list(triangles.faces))
    bmesh.ops.dissolve_degenerate(triangles, edges=list(triangles.edges), dist=0.000001)
    bmesh.ops.triangulate(triangles, faces=list(triangles.faces))
    bmesh.ops.recalc_face_normals(triangles, faces=list(triangles.faces))
    triangles.to_mesh(mesh)
    triangles.free()
    mesh.update()
    mesh.calc_loop_triangles()
    mesh.calc_tangents(uvmap="UVMap")
    data = {key: [] for key in ("p", "n", "ta", "u0", "tri")}
    seen = {}
    for triangle in mesh.loop_triangles:
        points = [
            Vector(tuple(round(float(v), 6) for v in mesh.vertices[index].co))
            for index in triangle.vertices
        ]
        # Rounded float32 contours can leave nearly collinear cap triangles.
        if (points[1] - points[0]).cross(points[2] - points[0]).length < 1e-7:
            continue
        texcoords = [mesh.uv_layers.active.data[i].uv for i in triangle.loops]
        first_uv = texcoords[1] - texcoords[0]
        second_uv = texcoords[2] - texcoords[0]
        determinant = first_uv.x * second_uv.y - first_uv.y * second_uv.x
        first_edge, second_edge = points[1] - points[0], points[2] - points[0]
        tangent_uv = (first_edge * second_uv.y - second_edge * first_uv.y) / determinant
        bitangent_uv = (second_edge * first_uv.x - first_edge * second_uv.x) / determinant
        indices = []
        for index in triangle.loops:
            loop = mesh.loops[index]
            point = mesh.vertices[loop.vertex_index].co
            normal = loop.normal
            tangent = loop.tangent
            sign = float(loop.bitangent_sign)
            if tangent.length_squared < 1e-12:
                tangent = (tangent_uv - normal * normal.dot(tangent_uv)).normalized()
                sign = -1.0 if normal.cross(tangent).dot(bitangent_uv) < 0 else 1.0
            uv = mesh.uv_layers.active.data[index].uv
            values = (
                tuple(round(float(point[i]), 6) for i in (0, 2, 1)),
                tuple(round(float(normal[i]), 6) for i in (0, 2, 1)),
                tuple(round(float(tangent[i]), 6) for i in (0, 2, 1)) + (sign,),
                (round(float(uv.x), 6), round(1.0 - float(uv.y), 6)),
            )
            if values not in seen:
                seen[values] = len(seen)
                for key, value in zip(("p", "n", "ta", "u0"), values):
                    data[key].extend(value)
            indices.append(seen[values])
        data["tri"].extend((indices[0], indices[2], indices[1]))
    low = [min(data["p"][a::3]) for a in range(3)]
    high = [max(data["p"][a::3]) for a in range(3)]
    center = [(a + b) / 2 for a, b in zip(low, high)]
    radius = math.dist(low, high) / 2
    data["boundingsphere"] = center + [radius]
    root = ET.Element("File", {"pdxasset": [1, 0]})
    shape = ET.SubElement(ET.SubElement(root, "object"), obj.name)
    native = ET.SubElement(shape, "mesh", data)
    ET.SubElement(native, "aabb", {"min": low, "max": high})
    ET.SubElement(native, "material", {
        "shader": ["PdxMeshBorder"],
        "diff": [f"{PREFIX}_diffuse.dds"],
        "n": [f"{PREFIX}_normal.dds"],
        "spec": [f"{PREFIX}_specular.dds"],
    })
    pdx_data.write_meshfile(str(path), root)


def build(output, render):
    import bpy

    bpy.ops.wm.read_factory_settings(use_empty=True)
    pdx = load_exporter()
    from io_pdx_mesh import pdx_data

    source = json.loads((output / "source.json").read_text())
    folder = output / "package" / MODEL_DIR
    reports = {}
    for obj in build_geometry(source):
        path = folder / (obj.name + ".mesh")
        export_native(obj, path, pdx_data)
        reports[path.name] = check_native(path, pdx_data)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    for name in reports:
        pdx.import_meshfile(str(folder / name), imp_locs=False)
    width = source["map_size"][0] / SCALE
    north_origin = RAIL_FRONT_INSET / SCALE + RAIL_DEPTH / 2
    for obj in bpy.context.scene.objects:
        if obj.type == "MESH" and "logo" not in obj.name:
            obj.location.x = -width / 2
            obj.location.y = -RAIL_DEPTH / 2
        elif obj.type == "MESH":
            obj.location.y = LOGO_FRONT_INSET / SCALE + LOGO_DEPTH / 2 - north_origin
    bpy.ops.file.pack_all()
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type == "VIEW_3D":
                area.spaces.active.shading.type = "MATERIAL"
                area.spaces.active.region_3d.view_location = (0, 0.2, 0.15)
                area.spaces.active.region_3d.view_distance = 10
    bpy.ops.wm.save_as_mainfile(filepath=str(output / "ADISCORD_map_border.blend"))
    reports["source_sha256"] = source["source_sha256"]
    reports["logo_sha256"] = source["logo_sha256"]
    reports["native_reimport"] = True
    reports["hoi4_runtime_verified"] = False
    reports["placement_world"] = {
        "map_size": source["map_size"],
        "rail_depth": RAIL_DEPTH * SCALE,
        "logo_size_xz": [LOGO_WIDTH * SCALE, LOGO_DEPTH * SCALE],
        "logo_layout": "Abyss of Discord - single line",
        "logo_front_clearance": LOGO_FRONT_INSET,
        "logo_north_center": source["map_size"][1] + LOGO_FRONT_INSET + LOGO_DEPTH * SCALE / 2,
    }
    (output / "verification.json").write_text(json.dumps(reports, indent=2) + "\n")
    print(json.dumps(reports), flush=True)
    if render:
        render_preview(output, source)


def render_preview(output, source):
    import bpy
    from mathutils import Vector

    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.samples = 40
    scene.cycles.use_denoising = True
    scene.render.resolution_x = 1680
    scene.render.resolution_y = 1050
    scene.render.resolution_percentage = 100
    scene.world = bpy.data.worlds.new("Border studio")
    scene.world.use_nodes = True
    scene.world.node_tree.nodes["Background"].inputs[0].default_value = (0.18, 0.21, 0.23, 1)
    scene.world.node_tree.nodes["Background"].inputs[1].default_value = 0.5
    scene.view_settings.view_transform = "AgX"
    for material in bpy.data.materials:
        if not material.use_nodes:
            continue
        shader = material.node_tree.nodes.get("Principled BSDF")
        if shader:
            for key, value in (("Roughness", 0.42), ("Metallic", 0.62)):
                for link in list(shader.inputs[key].links):
                    material.node_tree.links.remove(link)
                shader.inputs[key].default_value = value
    for location, energy, size in (
        ((-5, -3, 8), 1100, 7),
        ((5, 4, 6), 1400, 6),
        ((0, -6, 3), 500, 8),
    ):
        bpy.ops.object.light_add(type="AREA", location=location)
        light = bpy.context.object
        light.data.energy = energy
        light.data.shape = "DISK"
        light.data.size = size
        light.rotation_euler = (-light.location).to_track_quat("-Z", "Y").to_euler()
    bpy.ops.mesh.primitive_plane_add(size=200, location=(0, 0, -0.19))
    floor = bpy.context.object
    floor.name = "Studio floor - not exported"
    material = bpy.data.materials.new("Studio charcoal")
    material.diffuse_color = (0.025, 0.030, 0.035, 1)
    floor.data.materials.append(material)
    bpy.ops.object.camera_add()
    camera = bpy.context.object
    camera.data.type = "ORTHO"
    scene.camera = camera
    for name, position, target, scale in (
        ("map_border_detail.png", (4, -7, 10), (0, 0.1, 0.15), 10.5),
        ("map_border_overview.png", (0, -8, 16), (0, 0.1, 0.15), 12),
        ("map_border_logo.png", (0, -3, 10), (0, 0.2, 0.15), 9.4),
    ):
        camera.location = position
        camera.rotation_euler = (Vector(target) - camera.location).to_track_quat("-Z", "Y").to_euler()
        camera.data.ortho_scale = scale
        scene.render.filepath = str(output / name)
        bpy.ops.render.render(write_still=True)
    width, height = [value / SCALE for value in source["map_size"]]
    north_origin = RAIL_FRONT_INSET / SCALE + RAIL_DEPTH / 2
    rail = next(obj for obj in scene.objects if obj.type == "MESH" and obj.name == PREFIX)
    southern = rail.copy()
    southern.data = rail.data
    southern.name = "South border instance"
    scene.collection.objects.link(southern)
    southern.rotation_euler.z = math.pi
    southern.location = (width / 2, -height - north_origin - RAIL_FRONT_INSET / SCALE, 0)
    bpy.ops.mesh.primitive_plane_add(size=1, location=(0, -height / 2 - north_origin, 0.01))
    map_plane = bpy.context.object
    map_plane.name = "Map footprint 5632 x 2048 - not exported"
    map_plane.dimensions = (width, height, 0)
    footprint = bpy.data.materials.new("Map footprint")
    footprint.diffuse_color = (0.085, 0.14, 0.15, 1)
    map_plane.data.materials.append(footprint)
    camera.location = (0, -height / 2 - 7, 45)
    target = Vector((0, -height / 2 - 1.0, 0))
    camera.rotation_euler = (target - camera.location).to_track_quat("-Z", "Y").to_euler()
    camera.data.ortho_scale = width + 5
    scene.render.filepath = str(output / "map_border_placement.png")
    bpy.ops.render.render(write_still=True)
    # This orthographic framing reviews the full map height at a practical
    # viewport aspect. It does not emulate the game's perspective or UI.
    scene.render.resolution_x = 2040
    scene.render.resolution_y = 1432
    camera.location = (-5, -height / 2 - north_origin, 45)
    target = Vector((-5, -height / 2 - north_origin, 0))
    camera.rotation_euler = (target - camera.location).to_track_quat("-Z", "Y").to_euler()
    camera.data.ortho_scale = 35.0
    scene.render.filepath = str(output / "map_border_camera_fit.png")
    bpy.ops.render.render(write_still=True)


def section(original, body):
    newline = "\r\n" if b"\r\n" in original else "\n"
    start, end = f"# BEGIN {MARKER}", f"# END {MARKER}"
    content = (
        start + "\n# Generated by tools/assets/source/build_map_border.py\n"
        + body + "\n" + end + "\n"
    ).replace("\n", newline).encode()
    pattern = re.escape(start.encode()) + rb".*?" + re.escape(end.encode()) + rb"\r?\n?"
    matches = list(re.finditer(pattern, original, re.S))
    assert len(matches) <= 1
    if matches:
        match = matches[0]
        return original[:match.start()] + content + original[match.end():]
    return original.rstrip(b"\r\n") + (newline * 2).encode() + content


def remove_native_borders(original):
    """Replace only the three inherited border placements; preserve other scenery."""
    text = original.decode("utf-8")
    spans = []
    for match in re.finditer(r'(?m)^type\s*=\s*\{\s*type\s*=\s*"(frame_border(?:_bottom|_logo)?_entity)"', text):
        depth = 1
        end = match.end()
        while depth:
            depth += (text[end] == "{") - (text[end] == "}")
            end += 1
        if text[end:end + 2] == "\r\n":
            end += 2
        elif text[end:end + 1] == "\n":
            end += 1
        spans.append((match.start(), end))
    if spans:
        assert len(spans) == 3, "Expected all three native frame placements"
    for start, end in reversed(spans):
        text = text[:start] + text[end:]
    return text.encode("utf-8")


def install_contents(output):
    source = json.loads((output / "source.json").read_text())
    report = json.loads((output / "verification.json").read_text())
    assert source["source_sha256"] == report["source_sha256"] == sha(Path(__file__).read_bytes())
    assert source["logo_sha256"] == report["logo_sha256"] == sha(LOGO.read_bytes())
    assert report["native_reimport"]
    contents = {}
    folder = output / "package" / MODEL_DIR
    for path in folder.iterdir():
        if path.suffix == ".mesh":
            assert report[path.name]["sha256"] == sha(path.read_bytes())
        contents[ROOT / MODEL_DIR / path.name] = path.read_bytes()
    expected = stage_contents(output)
    assert all(path.read_bytes() == data for path, data in expected.items()), "Rebuild stale source or textures"
    entities = []
    meshes = []
    for name in (PREFIX, PREFIX + "_logo"):
        entities.append(f'entity = {{\n\tname = "{name}_entity"\n\tpdxmesh = "{name}_mesh"\n}}')
        meshes.append(
            f'\tpdxmesh = {{\n\t\tname = "{name}_mesh"\n'
            f'\t\tfile = "{MODEL_DIR.as_posix()}/{name}.mesh"\n'
            '\t\tscale = 1.0\n\t\tcull_distance = 99999.0\n\t}'
        )
    blocks = {
        ROOT / "gfx/entities/mapitems_custom.asset": "\n\n".join(entities),
        ROOT / "gfx/entities/mapitems_custom.gfx": "objectTypes = {\n" + "\n\n".join(meshes) + "\n}",
    }
    width, height = source["map_size"]
    placements = defaultdict(list)
    for label, name, x, z, angle in (
        ("north", PREFIX, 0, height + RAIL_FRONT_INSET, 0),
        ("south", PREFIX, width, -RAIL_FRONT_INSET, 180),
        ("emblem", PREFIX + "_logo", width / 2, height + LOGO_FRONT_INSET + LOGO_DEPTH * SCALE / 2, 0),
    ):
        placements[name].append(
            '\tobject = {\n'
            f'\t\tname = "{PREFIX}_{label}"\n\t\tposition = {{ {x:g} 0 {z:g} }}\n'
            f'\t\trotation = {{ 0 {angle} 0 }}\n\t}}'
        )
    types = []
    for name, objects in placements.items():
        types.append(
            f'type = {{\n\ttype = "{name}_entity"\n\tuse_animation = no\n'
            f'\tscale = {SCALE:.6f}\n\talways_visible = yes\n'
            + "\n\n".join(objects) + "\n}"
        )
    blocks[ROOT / "map/ambient_object.txt"] = "\n\n".join(types)
    for path, body in blocks.items():
        original = path.read_bytes()
        if path.name == "ambient_object.txt":
            original = remove_native_borders(original)
        contents[path] = section(original, body)
    return contents


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--apply", action="store_true")
    mode.add_argument("--build", action="store_true")
    parser.add_argument("--install", action="store_true")
    parser.add_argument("--blender", type=Path)
    parser.add_argument("--no-render", action="store_true")
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else None)
    output = args.output.resolve()
    if args.build:
        build(output, render=not args.no_render)
        return
    contents = install_contents(output) if args.install else stage_contents(output)
    changed = write_contents(contents, args.apply)
    if args.check:
        raise SystemExit(bool(changed))
    if args.apply and args.blender and not args.install:
        command = [
            str(args.blender), "--background", "--factory-startup",
            "--python-exit-code", "1", "--python", str(Path(__file__).resolve()),
            "--", "--output", str(output), "--build",
        ]
        if args.no_render:
            command.append("--no-render")
        subprocess.run(command, check=True)


if __name__ == "__main__":
    main()
