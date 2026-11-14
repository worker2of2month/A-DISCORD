"""Build five original export-office actors and clear regional placement sites.

--check is read-only. --apply exports native meshes and Blender sources.
--preview reimports native meshes and renders identical-scale review images.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import struct
import subprocess
import sys
import tempfile
from functools import lru_cache

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.builders.build_adiscord_factory_models import FactoryGeometry, digest, find_blender, textures
from tools.assets.source.build_shl_palace import load_exporter

NAME = "ADISCORD_NAM_export_office"
MODEL = Path("gfx/models/buildings/NAM_export_office")
SOURCE = Path("tools/assets/source/buildings/NAM/export_office")
REPORT = Path("docs/development/model-verification/NAM_export_office.json")
PREVIEW = Path("docs/development/previews/NAM_export_office")
EFFECTS = Path("common/scripted_effects/ADISCORD_NAM_export_office_visuals.txt")
STAGES = ASSETS = tuple(f"level_{level}" for level in range(1, 6))
STATES = (67, 688, 689, 690, 719)
SCALE = .07
SIZES = ((30, 24), (42, 30), (58, 40), (72, 52), (128, 92))
TEXTURES = tuple(f"{NAME}_{channel}.dds" for channel in ("diffuse", "normal", "specular"))
INPUTS = (Path(__file__).relative_to(ROOT), Path("tools/builders/build_adiscord_factory_models.py"),
          Path("tools/assets/source/build_shl_palace.py"), Path("map/provinces.bmp"),
          Path("map/heightmap.bmp"), Path("map/rivers.bmp"), Path("map/definition.csv"),
          Path("map/buildings.txt"), Path("map/ambient_object.txt"), Path("map/railways.txt"),
          Path("tools/data/nam_export_office_sites.json"), Path("map/trees.bmp"), Path("map/cities.bmp"), Path("map/cities.txt"),
          Path("map/terrain.bmp"), Path("common/terrain/00_terrain.txt"), Path("map/unitstacks.txt"))


def name(stage):
    return f"{NAME}_{stage}"


def office(g, x, y, width, depth, floors):
    height = floors * 3.2 + 1
    g.box((x, y, height / 2), (width, depth, height), 0)
    g.box((x, y, height), (width + 1, depth + 1, .8), 8)
    g.box((x, y, height + .5), (width - 1, depth - 1, .5), 3)
    for floor in range(floors):
        z = 2.1 + floor * 3.2
        for px in range(int(-width / 2) + 2, int(width / 2), 3):
            g.window(x + px, y - depth / 2 - .02, z, 1.6, 1.9)
            g.window(x + px, y + depth / 2 + .02, z, 1.6, 1.9, reverse=True)
        for py in range(int(-depth / 2) + 2, int(depth / 2), 3):
            g.window(x + width / 2 + .02, y + py, z, 1.6, 1.9, side=True)
    g.box((x, y - depth / 2 - .25, 1.6), (2.2, .6, 3.2), 5)
    g.box((x, y - depth / 2 - 1.4, 3.7), (5.5, 3.3, .4), 8)
    # Brass loading-arrow plaque remains geometric at the distant map scale.
    g.box((x, y - depth / 2 - .08, height - .8), (5.8, .18, 1), 15)


def warehouse(g, x, y, width, depth, bays):
    height = 5.2
    g.box((x, y, height / 2), (width, depth, height), 1)
    for sign in (-1, 1):
        points = [(x - width / 2 - .4, y + sign * (depth / 2 + .4), height),
                (x + width / 2 + .4, y + sign * (depth / 2 + .4), height),
                (x + width / 2 + .4, y, height + 2),
                (x - width / 2 - .4, y, height + 2)]
        g.face(points if sign == -1 else list(reversed(points)), 3)
    for sx in (-1, 1):
        points = [(x + sx * width / 2, y - depth / 2, height),
                (x + sx * width / 2, y, height + 2),
                (x + sx * width / 2, y + depth / 2, height)]
        g.face(points if sx == -1 else list(reversed(points)), 1)
    g.box((x, y - depth / 2 - 1, .5), (width + 1, 2.5, 1), 1)
    for index in range(bays):
        px = x - width / 2 + (index + .5) * width / bays
        g.box((px, y - depth / 2 - .06, 2.5), (width / bays - 1, .15, 3.5), 2)
        g.box((px, y - depth / 2 - 1.6, 4.8), (width / bays, 3.5, .3), 3)


def tank(g, x, y, radius, height):
    g.lathe(x, y, [(radius + .3, .2), (radius + .3, .8), (radius, .8),
                    (radius, height), (radius * .88, height + .5)], 11, 20)
    for z in (1, height * .5, height - .2):
        g.lathe(x, y, [(radius + .04, z), (radius + .04, z + .15)], 8, 20)
    g.lathe(x, y, [(radius * .88, height + .51), (.2, height + .7)], 7, 20)
    for px in (x - .5, x + .5):
        g.beam((px, y - radius - .15, .8), (px, y - radius - .15, height + .8), .1, 5)
    for z in range(1, int(height) + 1):
        g.beam((x - .5, y - radius - .15, z), (x + .5, y - radius - .15, z), .08, 5)


def loading_rack(g, x, y, length, lanes):
    width = 3.8 * lanes
    for px in (-length / 2, 0, length / 2):
        for py in (-width / 2, width / 2):
            g.beam((x + px, y + py, .2), (x + px, y + py, 5), .35, 15)
    g.box((x, y, 5.2), (length + 1, width + 1.2, .6), 3)
    for lane in range(lanes):
        py = y + (lane - (lanes - 1) / 2) * 3.8
        g.beam((x - length / 2, py, 4), (x + length / 2, py, 4), .22, 11)
        for px in (-length / 3, length / 3):
            g.beam((x + px, py, 4), (x + px, py, 2.5), .2, 11)
            g.box((x + px, py, .5), (3.5, 2.2, .7), 5)
            # Tank wagons give the transfer rack its function without engine particles.
            g.box((x + px, py, 1.7), (3.8, 2, 1.5), 11)


class TerminalGeometry(FactoryGeometry):
    def pipe(self, a, b, radius=.28):
        from mathutils import Vector

        a, b = Vector(a), Vector(b)
        axis = (b - a).normalized()
        guide = Vector((0, 0, 1)) if abs(axis.z) < .9 else Vector((0, 1, 0))
        u = axis.cross(guide).normalized() * radius
        v = axis.cross(u).normalized() * radius
        low = [a + math.cos(i * math.tau / 8) * u + math.sin(i * math.tau / 8) * v for i in range(8)]
        high = [point + b - a for point in low]
        self.face(list(reversed(low)), 5, [(.5, .5)] * 8)
        self.face(high, 5, [(.5, .5)] * 8)
        for i in range(8):
            j = (i + 1) % 8
            self.face([low[i], low[j], high[j], high[i]], 11)


def giant_terminal_geometry():
    """Separate storage, tank-farm and loading yards linked by service aisles."""
    g = TerminalGeometry()
    width, depth = SIZES[4]
    g.box((0, 0, -6), (width, depth, 12.4), 4)
    for x in (-49, -23):
        for y in (34, 13, -8):
            warehouse(g, x, y, 20, 11, 3)
    for column, x in enumerate((18, 36, 54)):
        for row, y in enumerate((1, 19, 37)):
            tank(g, x, y, (6.2, 6.6, 7)[column], 12 + row * 2 + (column % 2) * 2)
    for x in (7, 36):
        for y in (-18, -34):
            loading_rack(g, x, y, 18, 2)
    office(g, -49, -34, 18, 12, 4)
    office(g, -23, -34, 14, 12, 6)
    g.box((-23, -34, 21.8), (16, 14, 2), 6)
    g.box((-23, -34, 23.2), (17, 15, .5), 3)
    # Continuous light paving separates warehouse loading fronts from pipework.
    for x, y, length, breadth in ((-36, 5, 3, 76), (-7, 5, 4, 76),
                                  (21, -27, 4, 32), (62.3, 0, 1.4, 86)):
        g.box((x, y, .24), (length, breadth, .08), 1)
    g.box((26, -11.7, .24), (66, 2.4, .08), 1)
    g.pipe((9, -9, 2.2), (59, -9, 2.2), .4)
    for x, radius in ((18, 6.2), (36, 6.6), (54, 7)):
        spine = x - 8
        g.pipe((spine, -9, 2.2), (spine, 41, 2.2), .32)
        for y in (1, 19, 37):
            g.pipe((spine, y, 2.2), (x - radius + .2, y, 2.2), .3)
        for y in (-5, 10, 28, 41):
            g.box((spine, y, 1.1), (.9, 1.1, 2.2), 1)
    # The overhead feed clears the loading canopies and their access lanes.
    for x in (17.5, 46.5):
        g.pipe((x, -9, 2.2), (x, -9, 6.4), .3)
        g.pipe((x, -9, 6.4), (x, -41, 6.4), .3)
        for y in (-26, -41):
            g.beam((x, y, .2), (x, y, 6.4), .4, 5)
        for y in (-18, -34):
            g.pipe((x, y, 6.4), (x - 10.5, y, 6.4), .22)
            g.pipe((x - 10.5, y, 6.4), (x - 10.5, y, 4.7), .22)
    for x in (-58, -54, -28, -24):
        for y in (24, 3):
            g.box((x, y, 1.1), (3, 2, 2.2), 10)
    for py in (-depth / 2 + .4, depth / 2 - .4):
        g.box((0, py, .35), (width - 1, .5, .4), 8)
    for px in (-width / 2 + .4, width / 2 - .4):
        g.box((px, 0, .35), (.5, depth - 1, .4), 8)
    return g


def geometry(stage):
    level = int(stage.rsplit("_", 1)[1])
    if level == 5:
        return giant_terminal_geometry()
    width, depth = SIZES[level - 1]
    g = FactoryGeometry()
    g.box((0, 0, -6), (width, depth, 12.4), 4)
    # Every tier keeps administration and loading on the same sides of the yard.
    office(g, -width / 2 + 8, -depth / 2 + 7.2, 11, 8, min(level, 4))
    warehouse(g, -width / 2 + 10, depth / 2 - 7, 15, 9, 2)
    tank(g, width / 2 - 6, depth / 2 - 6, 3 if level == 1 else 4, 5 + level)
    loading_rack(g, width / 2 - 7, -depth / 2 + 6, 8, 1)
    if level >= 2:
        tank(g, width / 2 - 6, 0, 3.5, 6 + level)
        g.box((-1, -depth / 2 + 2, 1), (4, 3, 2), 10)
    if level >= 3:
        warehouse(g, 2, depth / 2 - 7, 16, 9, 3)
        loading_rack(g, 1, -3, 12, 2)
    if level >= 4:
        tank(g, width / 2 - 18, depth / 2 - 7, 5, 10)
        warehouse(g, -width / 2 + 10, 1, 15, 9, 2)
        # A dispatch tower, rather than a refinery stack, anchors the large terminal.
        office(g, 0, -depth / 2 + 7.2, 9, 8, level)
        g.box((0, -depth / 2 + 7.2, level * 3.2 + 2.5), (11, 10, 2), 6)
        g.box((0, -depth / 2 + 7.2, level * 3.2 + 3.8), (12, 11, .5), 3)
    # Low perimeter curbs establish a yard without a solid wall masking the buildings.
    for py in (-depth / 2 + .4, depth / 2 - .4):
        g.box((0, py, .35), (width - 1, .5, .4), 8)
    for px in (-width / 2 + .4, width / 2 - .4):
        g.box((px, 0, .35), (.5, depth - 1, .4), 8)
    return g


def state_sources():
    result = {}
    for path in (ROOT / "history/states").glob("*.txt"):
        text = path.read_text(encoding="utf-8-sig")
        match = re.search(r"\bid\s*=\s*(\d+)", text)
        if match and int(match[1]) in STATES:
            result[int(match[1])] = (path, text)
    assert set(result) == set(STATES)
    return result


def input_hashes():
    paths = [*INPUTS, *(p.relative_to(ROOT) for p, _ in state_sources().values())]
    hashes = {p.as_posix(): digest(ROOT / p) for p in paths}
    hashes["scripted_entity_obstacles"] = hashlib.sha256(json.dumps(scripted_obstacles()).encode()).hexdigest()
    return hashes


def scripted_obstacles():
    text = (ROOT / "common/scripted_effects/ADISCORD_nam_resource_war_effects.txt").read_text()
    block = text.split("NAM_combine_sync_visual = {", 1)[1]
    x = float(re.search(r"\bx\s*=\s*([\d.-]+)", block)[1])
    y = float(re.search(r"\by\s*=\s*([\d.-]+)", block)[1])
    return [(x, y, 10, "combine")]


@lru_cache(maxsize=1)
def placement_data():
    """Reserve the maximum footprint before choosing any actor's initial site."""
    import numpy as np
    from PIL import Image, ImageDraw

    rgb = np.asarray(Image.open(ROOT / "map/provinces.bmp").convert("RGB"))
    heights = np.asarray(Image.open(ROOT / "map/heightmap.bmp"), dtype=float) / 10
    rivers = np.asarray(Image.open(ROOT / "map/rivers.bmp"))
    city_raster = np.asarray(Image.open(ROOT / "map/cities.bmp"))
    trees = np.asarray(Image.open(ROOT / "map/trees.bmp").resize((rgb.shape[1], rgb.shape[0]), Image.Resampling.NEAREST))
    terrain = np.asarray(Image.open(ROOT / "map/terrain.bmp"))
    packed = (rgb[:, :, 0].astype("uint32") << 16) | (rgb[:, :, 1].astype("uint32") << 8) | rgb[:, :, 2]
    definitions = {}
    for line in (ROOT / "map/definition.csv").read_text(encoding="utf-8-sig").splitlines():
        fields = line.split(";")
        if fields[0].isdigit() and len(fields) >= 7:
            definitions[int(fields[0])] = fields
    obstacles = []
    for line in (ROOT / "map/buildings.txt").read_text().splitlines():
        fields = line.split(";")
        if fields[0].isdigit() and len(fields) >= 5:
            radius = 1.5 if fields[1] in ("bunker", "coastal_bunker", "anti_air_building") else 3.5
            obstacles.append((float(fields[2]), float(fields[4]), radius, fields[1]))
    ambient = (ROOT / "map/ambient_object.txt").read_text()
    for match in re.finditer(r"position\s*=\s*\{\s*([\d.-]+)\s+([\d.-]+)\s+([\d.-]+)", ambient):
        x, altitude, z = match.groups()
        if float(altitude) < 100:
            preceding = ambient[:match.start()]
            entity = re.findall(r'type\s*=\s*"([^"\n]+)"', preceding)[-1]
            radius = 2.25 if "NAM_oilfield" in entity else 8
            obstacles.append((float(x), float(z), radius, entity))
    # The staged combine is a scripted entity and has no ambient-object entry.
    obstacles.extend(scripted_obstacles())
    city_ids = set()
    for _, text in state_sources().values():
        city_ids.update(map(int, re.findall(r"victory_points\s*=\s*\{\s*(\d+)", text)))
    for line in (ROOT / "map/unitstacks.txt").read_text().splitlines():
        fields = line.split(";")
        if int(fields[0]) in city_ids and fields[1] == "0":
            obstacles.append((float(fields[2]), float(fields[4]), 3.5, "city_center"))
    rail_image = Image.new("1", (rgb.shape[1], rgb.shape[0]))
    rail_draw = ImageDraw.Draw(rail_image)
    centers = {}

    def center(province):
        if province not in centers:
            fields = definitions[province]
            r, g, b = map(int, fields[1:4])
            rows, cols = np.nonzero(packed == ((r << 16) | (g << 8) | b))
            centers[province] = (float(cols.mean()), float(rows.mean())) if len(rows) else None
        return centers[province]

    relevant = set()
    for _, text in state_sources().values():
        relevant.update(map(int, re.search(r"\bprovinces\s*=\s*\{([^}]*)\}", text)[1].split()))
    for line in (ROOT / "map/railways.txt").read_text().splitlines():
        values = [int(v) for v in line.split()]
        for a, b in zip(values[2:], values[3:]):
            if a in relevant or b in relevant:
                first, second = center(a), center(b)
                if first and second:
                    rail_draw.line([first, second], fill=1, width=3)
    rail = np.asarray(rail_image)
    result = []
    half_width = SIZES[-1][0] * SCALE / 2 + .2
    half_depth = SIZES[-1][1] * SCALE / 2 + .2
    # Raster cells extend half a pixel around their centers; actor clearance is separate.
    reserve_x = math.ceil(SIZES[-1][0] * SCALE / 2 - .5)
    reserve_y = math.ceil(SIZES[-1][1] * SCALE / 2 - .5)
    authored = {site["state"]: site for site in json.loads((ROOT / "tools/data/nam_export_office_sites.json").read_text())["sites"]}
    for state, (_, text) in sorted(state_sources().items()):
        province_ids = set(map(int, re.search(r"\bprovinces\s*=\s*\{([^}]*)\}", text)[1].split()))
        colors = []
        for province in province_ids:
            fields = definitions[province]
            if fields[4] == "land" and fields[6] in ("plains", "desert", "hills"):
                r, g, b = map(int, fields[1:4])
                colors.append((r << 16) | (g << 8) | b)
        state_mask = np.isin(packed, colors)
        site = authored[state]
        province = site["province"]
        x, _, z = site["position"]
        center_row, center_col = int(len(heights) - 1 - z), int(x)
        if province not in province_ids or tuple(map(int, definitions[province][1:4])) != tuple(rgb[center_row, center_col]):
            raise ValueError(f"State {state}: office anchor is outside its declared province {province}")
        footprint = np.s_[center_row - reserve_y:center_row + reserve_y + 1,
                          center_col - reserve_x:center_col + reserve_x + 1]
        # An internal province border is not an obstacle to a state-level yard.
        if not state_mask[footprint].all() or (rivers[footprint] != 255).any() or rail[footprint].any():
            raise ValueError(f"State {state}: office footprint crosses a state edge, river or railway")
        if (city_raster[footprint] != 1).any() or (terrain[footprint] == 13).any() or trees[footprint].any():
            raise ValueError(f"State {state}: office footprint overlaps a city or trees")
        patch = heights[footprint]
        span = round(float(np.ptp(patch)), 3)
        if span > .8 or float(patch.min()) < 10:
            raise ValueError(f"State {state}: office foundation does not fit the terrain")
        for ox, oz, radius, kind in obstacles:
            if abs(x - ox) < half_width + radius and abs(z - oz) < half_depth + radius:
                raise ValueError(f"State {state}: office overlaps {kind} at {ox:g}, {oz:g}")
        altitude = round(float(patch.max()) - .02, 3)
        center_height = float(heights[center_row, center_col])
        tiers = []
        for width, depth in SIZES:
            hx = math.ceil(width * SCALE / 2 - .5)
            hy = math.ceil(depth * SCALE / 2 - .5)
            patch = heights[center_row - hy:center_row + hy + 1, center_col - hx:center_col + hx + 1]
            tiers.append({"height_offset": round(float(patch.max()) - .02 - center_height, 3),
                          "height_span": round(float(np.ptp(patch)), 3)})
        result.append({"state": state, "province": province, "position": [x, altitude, z],
                       "scale": SCALE, "actor_id": 620000 + state, "height_span": span,
                       "height_offset": round(altitude - float(heights[int(len(heights) - 1 - z), int(x)]), 3),
                       "tier_terrain": tiers,
                       "terrain_grid": np.round(heights[center_row - 6:center_row + 7, center_col - 6:center_col + 7] - center_height, 3).tolist(),
                       "reserved_footprint": [2 * reserve_x + 1, 2 * reserve_y + 1],
                       "maximum_model_footprint": [round(v * SCALE, 3) for v in SIZES[-1]]})
    return result, obstacles, rail_image


def placements():
    return placement_data()[0]


def visual_effects():
    lines = ["# Generated by tools/builders/build_adiscord_nam_export_offices.py.",
             "# State scope. Native actors persist across country handoffs and ordinary save/load.",
             "# Explicit coordinates use x/map-y/height; the largest tier fits the reserved site.",
             "NAM_export_office_sync_visual = {"]
    for index, site in enumerate(placements()):
        x, altitude, y = site["position"]
        lines += [f"\t{'if' if index == 0 else 'else_if'} = {{", f"\t\tlimit = {{ state = {site['state']} }}",
                  f"\t\tdestroy_entity = {site['actor_id']}"]
        for level, stage in enumerate(STAGES, 1):
            lines += [f"\t\t{'if' if level == 1 else 'else_if'} = {{",
                      f"\t\t\tlimit = {{ check_variable = {{ var = NAM_export_office_level value = {level} compare = equals }} }}",
                      "\t\t\tcreate_entity = {", f"\t\t\t\tentity = {name(stage)}_entity",
                      f"\t\t\t\tid = {site['actor_id']}", f"\t\t\t\tx = {x:g}", f"\t\t\t\ty = {y:g}",
                      f"\t\t\t\tz = {site['tier_terrain'][level - 1]['height_offset']:g}", "\t\t\t\trotation = 0", f"\t\t\t\tscale = {SCALE}",
                      "\t\t\t\tmin_zoom = 2000", "\t\t\t}", "\t\t}"]
        lines.append("\t}")
    return ("\n".join([*lines, "}"]) + "\n").encode()


def section_outputs():
    meshes = [f'\tpdxmesh = {{\n\t\tname = "{name(s)}_mesh"\n\t\tfile = "{(MODEL / (name(s) + ".mesh")).as_posix()}"\n\t\tscale = 1\n\t}}' for s in ASSETS]
    entities = [f'entity = {{\n\tname = "{name(s)}_entity"\n\tpdxmesh = "{name(s)}_mesh"\n}}' for s in ASSETS]
    blocks = {"gfx/entities/mapitems_custom.gfx": "objectTypes = {\n" + "\n".join(meshes) + "\n}",
              "gfx/entities/mapitems_custom.asset": "\n\n".join(entities)}
    result = {ROOT / EFFECTS: visual_effects()}
    for relative, block in blocks.items():
        path = ROOT / relative
        original = path.read_bytes()
        nl = "\r\n" if b"\r\n" in original else "\n"
        start, end = f"# BEGIN {NAME}", f"# END {NAME}"
        section = (start + "\n# Generated by tools/builders/build_adiscord_nam_export_offices.py\n" + block + "\n" + end + "\n").replace("\n", nl).encode()
        pattern = re.escape(start.encode()) + rb".*?" + re.escape(end.encode()) + rb"\r?\n?"
        matches = list(re.finditer(pattern, original, re.S))
        assert len(matches) <= 1
        if matches:
            m = matches[0]
            result[path] = original[:m.start()] + section + original[m.end():]
        else:
            assert NAME.encode() not in original
            result[path] = original + nl.encode() + section
    return result


def verify(folder, stage, pdx):
    import bpy
    from mathutils import Vector
    from io_pdx_mesh import pdx_data

    path = folder / (name(stage) + ".mesh")
    tree = pdx_data.read_meshfile(str(path))
    triangles = vertices = materials = 0
    for shape in tree.find("object"):
        for element in shape.findall("mesh"):
            data = pdx_data.PDXData(element)
            count = len(data.p) // 3
            assert 0 < count < 65536
            assert len(data.n) == count * 3 and len(data.u0) == count * 2 and len(data.ta) == count * 4
            assert all(math.isfinite(v) for v in data.p + data.n + data.u0 + data.ta)
            assert min(data.tri) >= 0 and max(data.tri) < count
            for i in range(0, len(data.tri), 3):
                a, b, c = [Vector(data.p[j * 3:j * 3 + 3]) for j in data.tri[i:i + 3]]
                assert (b - a).cross(c - a).length > 1e-8
            assert data.material.shader == ["PdxMeshAdvancedSnow"]
            for key, texture in zip(("diff", "n", "spec"), TEXTURES):
                assert getattr(data.material, key) == [texture]
                raw = (folder / texture).read_bytes()
                assert raw[:4] == b"DDS " and raw[84:88] == b"DXT5"
                assert struct.unpack_from("<I", raw, 28)[0] == 11
            vertices += count
            triangles += len(data.tri) // 3
            materials += 1
    assert triangles < 24000 and materials == 1
    bpy.ops.wm.read_factory_settings(use_empty=True)
    pdx.import_meshfile(str(path), imp_locs=False)
    objects = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    assert len(objects) == 1
    points = [v.co for v in objects[0].data.vertices]
    bounds = [[round(min(v[i] for v in points), 5), round(max(v[i] for v in points), 5)] for i in range(3)]
    width, depth = SIZES[int(stage.rsplit("_", 1)[1]) - 1]
    expected = [[-width / 2, width / 2], [-depth / 2, depth / 2]]
    assert bounds[:2] == expected, bounds
    return {"vertices": vertices, "triangles": triangles, "materials": materials, "bounds": bounds}


def build(folder):
    import bpy
    from types import SimpleNamespace
    pdx = load_exporter()
    from io_pdx_mesh import pdx_data
    models = {}
    for stage in ASSETS:
        bpy.ops.wm.read_factory_settings(use_empty=True)
        obj = geometry(stage).make_object()
        obj.name = obj.data.name = name(stage)
        obj.data.materials.append(pdx.create_shader(SimpleNamespace(
            shader=["PdxMeshAdvancedSnow"], diff=[TEXTURES[0]], n=[TEXTURES[1]], spec=[TEXTURES[2]]),
            "Export office masonry, steel, storage tanks and glass", str(folder)))
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        path = folder / (name(stage) + ".mesh")
        pdx.export_meshfile(str(path), exp_selected=True, exp_skel=False, exp_locs=False)
        tree = pdx_data.read_meshfile(str(path))
        for shape in tree.find("object"):
            for mesh in shape.findall("mesh"):
                mesh.attrib["ta"] = [round(v, 5) for v in mesh.attrib["ta"]]
        pdx_data.write_meshfile(str(path), tree)
        bpy.ops.file.pack_all()
        bpy.context.preferences.filepaths.save_version = 0
        bpy.ops.wm.save_as_mainfile(filepath=str(folder / (stage + ".blend")))
        models[stage] = verify(folder, stage, pdx)
    (folder / "native.json").write_text(json.dumps({"models": models, "native_reimport": True,
        "hoi4_runtime_verified": False}, indent=2) + "\n", encoding="utf-8")


def render(folder=None, stages=ASSETS, terrain=True):
    import bpy
    from mathutils import Vector

    pdx = load_exporter()
    (ROOT / PREVIEW).mkdir(parents=True, exist_ok=True)
    for stage in stages:
        verify(folder or ROOT / MODEL, stage, pdx)
        scene = bpy.context.scene
        scene.render.engine = "CYCLES"
        scene.cycles.samples = 32
        scene.cycles.use_denoising = True
        scene.render.resolution_x, scene.render.resolution_y = 1200, 900
        scene.render.resolution_percentage = 100
        scene.world = bpy.data.worlds.new("Export-office studio")
        scene.world.use_nodes = True
        scene.world.node_tree.nodes["Background"].inputs[0].default_value = (.32, .36, .42, 1)
        scene.world.node_tree.nodes["Background"].inputs[1].default_value = .7
        if True:
            # The buried retaining foundation is not part of the visible skyline.
            bpy.ops.mesh.primitive_plane_add(size=1000, location=(0, 0, -.15))
            ground = bpy.data.materials.new("Neutral terrain, not exported")
            ground.diffuse_color = (.22, .22, .2, 1)
            bpy.context.object.data.materials.append(ground)
        for material in bpy.data.materials:
            node = material.node_tree.nodes.get("Principled BSDF") if material.use_nodes else None
            if node:
                for link in list(node.inputs["Roughness"].links):
                    material.node_tree.links.remove(link)
                node.inputs["Roughness"].default_value = .7
        for pos, energy in (((-60, -90, 120), 70000), ((90, -20, 80), 36000), ((0, 90, 100), 64000)):
            bpy.ops.object.light_add(type="AREA", location=pos)
            lamp = bpy.context.object
            lamp.data.energy, lamp.data.size = energy, 65
            lamp.rotation_euler = (Vector((0, 0, 6)) - lamp.location).to_track_quat("-Z", "Y").to_euler()
        bpy.ops.object.camera_add(location=(115, -165, 120))
        camera = bpy.context.object
        camera.data.type = "ORTHO"
        camera.data.ortho_scale = 180
        camera.rotation_euler = (Vector((0, 0, 12)) - camera.location).to_track_quat("-Z", "Y").to_euler()
        scene.camera = camera
        scene.render.filepath = str(ROOT / PREVIEW / (stage + ".png"))
        bpy.ops.render.render(write_still=True)
        if terrain and stage in ("level_1", "level_5"):
            site = next(p for p in json.loads((ROOT / REPORT).read_text())["placements"] if p["state"] == 690)
            level = int(stage.rsplit("_", 1)[1])
            actor = next(o for o in scene.objects if o.type == "MESH" and o.name != "Plane")
            actor.location.z = site["tier_terrain"][level - 1]["height_offset"] / SCALE
            bpy.data.objects.remove(bpy.data.objects["Plane"], do_unlink=True)
            points = [(float(col - 6) / SCALE, float(6 - row) / SCALE, altitude / SCALE)
                      for row, values in enumerate(site["terrain_grid"]) for col, altitude in enumerate(values)]
            faces = [(row * 13 + col, row * 13 + col + 1, (row + 1) * 13 + col + 1, (row + 1) * 13 + col)
                     for row in range(12) for col in range(12)]
            mesh = bpy.data.meshes.new("State 690 heightmap patch")
            mesh.from_pydata(points, [], [tuple(reversed(f)) for f in faces])
            terrain = bpy.data.objects.new("State 690 actual terrain", mesh)
            scene.collection.objects.link(terrain)
            terrain.data.materials.append(ground)
            scene.render.filepath = str(ROOT / PREVIEW / ("terrain_690_" + stage + ".png"))
            bpy.ops.render.render(write_still=True)


def run_blender(args):
    subprocess.run([find_blender(None), "--background", "--factory-startup", "--threads", "4",
                    "--python-exit-code", "1", "--python", str(Path(__file__)), "--", *args],
                   env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"), check=True)


def preview_sheets():
    """Show common camera scale and actual reserved map pixels, without game UI."""
    from PIL import Image, ImageDraw
    import numpy as np

    folder = ROOT / PREVIEW
    lineup = Image.new("RGB", (2000, 340), (28, 32, 34))
    draw = ImageDraw.Draw(lineup)
    for index, stage in enumerate(STAGES):
        picture = Image.open(folder / (stage + ".png")).convert("RGB").resize((400, 300))
        lineup.paste(picture, (index * 400, 30))
        draw.text((index * 400 + 12, 10), f"LEVEL {index + 1} | same camera and native scale {SCALE}", fill="white")
    lineup.save(folder / "lineup.png")
    pair = Image.new("RGB", (1800, 705), (28, 32, 34))
    pair_draw = ImageDraw.Draw(pair)
    for index, level in enumerate((4, 5)):
        picture = Image.open(folder / f"level_{level}.png").convert("RGB").resize((900, 675))
        pair.paste(picture, (index * 900, 30))
        pair_draw.text((index * 900 + 14, 10), f"LEVEL {level} | identical camera and native scale {SCALE}", fill="white")
    pair.save(folder / "level_4_vs_5.png")
    rgb = np.asarray(Image.open(ROOT / "map/provinces.bmp").convert("RGB"))
    heights = np.asarray(Image.open(ROOT / "map/heightmap.bmp"))
    rivers = np.asarray(Image.open(ROOT / "map/rivers.bmp"))
    cities = np.asarray(Image.open(ROOT / "map/cities.bmp"))
    trees = np.asarray(Image.open(ROOT / "map/trees.bmp").resize((rgb.shape[1], rgb.shape[0]), Image.Resampling.NEAREST))
    sites, obstacles, rail_image = placement_data()
    rails = np.asarray(rail_image)
    sheet = Image.new("RGB", (2000, 460), (28, 32, 34))
    legend = ImageDraw.Draw(sheet)
    legend.text((12, 8), "CYAN: level 5 | WHITE: reserved terrain | ORANGE: native anchors | BROWN: ambient | PINK: railway corridor | BLUE: river | RED: city mask | GREEN: trees", fill="white")
    for index, site in enumerate(sites):
        x, _, z = site["position"]
        row, col = int(rgb.shape[0] - 1 - z), int(x)
        cut = np.s_[row - 20:row + 20, col - 20:col + 20]
        tone = heights[cut].astype(float)
        base = np.stack([tone * .5 + 55, tone * .4 + 52, tone * .3 + 45], axis=-1).clip(0, 255).astype("uint8")
        base[rivers[cut] != 255] = (42, 110, 180)
        base[trees[cut] != 0] = (34, 95, 47)
        base[cities[cut] != 1] = (160, 65, 65)
        base[rails[cut]] = (140, 65, 150)
        panel = Image.fromarray(base).resize((400, 400), Image.Resampling.NEAREST)
        pd = ImageDraw.Draw(panel)
        for yy in range(39):
            for xx in range(39):
                if (rgb[row - 20 + yy, col - 20 + xx] != rgb[row - 20 + yy, col - 19 + xx]).any():
                    pd.line((xx * 10 + 10, yy * 10, xx * 10 + 10, yy * 10 + 10), fill=(175, 175, 175))
                if (rgb[row - 20 + yy, col - 20 + xx] != rgb[row - 19 + yy, col - 20 + xx]).any():
                    pd.line((xx * 10, yy * 10 + 10, xx * 10 + 10, yy * 10 + 10), fill=(175, 175, 175))
        for ox, oz, radius, kind in obstacles:
            if abs(ox - x) < 25 and abs(oz - z) < 25:
                px, py = 205 + (ox - x) * 10, 205 - (oz - z) * 10
                color = (165, 116, 67) if kind.startswith("ADISCORD") or kind == "combine" else (230, 154, 61)
                pd.rectangle((px - radius * 10, py - radius * 10, px + radius * 10, py + radius * 10), outline=color, width=1)
                pd.ellipse((px - 2, py - 2, px + 2, py + 2), fill=color)
        for footprint, color, thickness in ((site["reserved_footprint"], "white", 1),
                                             (site["maximum_model_footprint"], (75, 240, 240), 3)):
            half_x, half_y = (size * 5 for size in footprint)
            pd.rectangle((205 - half_x, 205 - half_y, 205 + half_x, 205 + half_y),
                         outline=color, width=thickness)
        sheet.paste(panel, (index * 400, 50))
        legend.text((index * 400 + 12, 31), f"STATE {site['state']} | x={x:g}, y={z:g} | max terrain delta {site['height_span']:.1f}", fill="white")
    sheet.save(folder / "placement_map.png")


def stale():
    changed = [str(p.relative_to(ROOT)) for p, data in section_outputs().items() if not p.exists() or p.read_bytes() != data]
    path = ROOT / REPORT
    if not path.exists():
        return [*changed, str(REPORT)]
    report = json.loads(path.read_text(encoding="utf-8"))
    if report.get("input_sha256") != input_hashes():
        changed.append(str(REPORT))
    for relative, sha in report["files"].items():
        p = ROOT / relative
        if not p.exists() or digest(p) != sha:
            changed.append(relative)
    return changed


def apply():
    hashes = input_hashes()
    with tempfile.TemporaryDirectory(prefix="adiscord-nam-export-office-") as directory:
        folder = Path(directory)
        for texture, data in zip(TEXTURES, textures().values()):
            (folder / texture).write_bytes(data)
        run_blender(["--build-dir", str(folder)])
        assert hashes == input_hashes()
        report = json.loads((folder / "native.json").read_text(encoding="utf-8"))
        contents = {ROOT / MODEL / n: (folder / n).read_bytes()
                    for n in [*TEXTURES, *(name(s) + ".mesh" for s in ASSETS)]}
        unchanged_textures = all((ROOT / MODEL / texture).exists() and
                                 (ROOT / MODEL / texture).read_bytes() == contents[ROOT / MODEL / texture]
                                 for texture in TEXTURES)
        for stage in ASSETS:
            source = ROOT / SOURCE / (stage + ".blend")
            mesh = ROOT / MODEL / (name(stage) + ".mesh")
            # An unchanged native asset retains its packed source byte-for-byte.
            if source.exists() and mesh.exists() and unchanged_textures and mesh.read_bytes() == contents[mesh]:
                contents[source] = source.read_bytes()
            else:
                contents[source] = (folder / (stage + ".blend")).read_bytes()
        import hashlib

        report["files"] = {p.relative_to(ROOT).as_posix(): hashlib.sha256(data).hexdigest() for p, data in contents.items()}
        report["input_sha256"] = hashes
        report["placements"] = placements()
        report["native_scale"] = SCALE
        report["source"] = "Original procedural architecture; shared in-repository material atlas"
        report["placement_validation"] = {
            "native_actor_collision_verified": False,
            "clearance_margin": .2,
            "building_anchor_half_extent": {"bunker_coastal_bunker_anti_air": 1.5, "other": 3.5},
            "ambient_anchor_half_extent": {"oilfield": 2.25, "combine": 10, "other": 8},
            "railway_model": "Three-pixel corridor along linked province-center segments",
            "terrain_checks": "Whole maximum-tier footprint inside its land state; no city, tree or river pixels; city centers have separate clearance",
            "grounding": "Per-tier terrain-relative height; buried foundation below the lowest footprint sample",
        }
        contents[ROOT / REPORT] = (json.dumps(report, indent=2) + "\n").encode()
        contents.update(section_outputs())
        for path, data in contents.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            if not path.exists() or path.read_bytes() != data:
                path.write_bytes(data)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--check", action="store_true")
    modes.add_argument("--apply", action="store_true")
    modes.add_argument("--preview", action="store_true")
    modes.add_argument("--build-dir", type=Path, help=argparse.SUPPRESS)
    modes.add_argument("--render", action="store_true", help=argparse.SUPPRESS)
    modes.add_argument("--render-staged", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else None)
    if args.build_dir:
        build(args.build_dir)
        return
    if args.render:
        render()
        return
    if args.render_staged:
        render(args.render_staged, ("level_4", "level_5"), terrain=False)
        return
    changes = stale()
    print(json.dumps({"stale": changes}), flush=True)
    if args.apply and changes:
        apply()
        changes = stale()
        assert not changes, changes
    if args.preview:
        assert not changes, changes
        run_blender(["--render"])
        preview_sheets()
    raise SystemExit(bool(changes))


if __name__ == "__main__":
    main()
