"""Build northern infantry models. preview before installing with --apply.

Blender: --background --python this_file -- --build --output PATH
Python: this_file --output PATH (stages the preview package)
Blender: --background --python this_file -- --verify --output PATH
Python: this_file --output PATH --apply, then --check
Uses the existing militia body, rig and locators. Only the marked northern
bindings and named model package belong to this builder.
"""
from pathlib import Path
import argparse
import hashlib
import json
import math
import re
import sys
sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[3]
GAME = Path('Z:/SteamLibrary/steamapps/common/Hearts of Iron IV')
ARAB_TAGS = ('AZH', 'GLP', 'KDR', 'KYZ', 'MZR', 'RHM', 'SDR', 'SLF')
CONFIG = {
    'COF': ROOT / 'gfx/models/units/APH_afg_militia.mesh',
    'YPR': GAME / 'gfx/models/units/eastern_european_infantry.mesh',
    'TFF': ROOT / 'gfx/models/units/STP_infantry_hedonist.mesh',
    # Preserve the native rig and locators while replacing garments and kit.
    'RUS': ROOT / 'gfx/models/units/STP_infantry_hedonist.mesh',
    'SHL': ROOT / 'gfx/models/units/APH_irregular_infantry.mesh',
    'ARB': ROOT / 'gfx/models/units/APH_irregular_infantry.mesh',
    'NAM': ROOT / 'gfx/models/units/STP_infantry_hedonist.mesh',
}
NORMALS = {
    'COF': ROOT / 'gfx/models/units/APH_afg_militia_normal.dds',
    'YPR': GAME / 'gfx/models/units/eastern_european_infantry_normal.dds',
    'TFF': ROOT / 'gfx/models/units/STP_infantry_hedonist__normal.dds',
    'RUS': ROOT / 'gfx/models/units/STP_infantry_hedonist__normal.dds',
    'SHL': ROOT / 'gfx/models/units/APH_irregular_infantry_normal.dds',
    'ARB': ROOT / 'gfx/models/units/APH_irregular_infantry_normal.dds',
    'NAM': ROOT / 'gfx/models/units/STP_infantry_hedonist__normal.dds',
}
START = '# BEGIN ADISCORD northern infantry\n'
END = '# END ADISCORD northern infantry\n'


def blocks(text, kind):
    for match in re.finditer(r'\b' + kind + r'\s*=\s*\{', text):
        depth = 1
        end = match.end()
        while depth:
            depth += (text[end] == '{') - (text[end] == '}')
            end += 1
        yield text[match.start():end]


def finalize_mesh(path):
    """The native shader dereferences four bone indices even at zero weight."""
    sys.path.insert(0, str(Path.home() / 'AppData/Roaming/Blender Foundation/Blender/5.2/extensions/user_default'))
    from io_pdx_mesh import pdx_data
    tree = pdx_data.read_meshfile(str(path))
    changed = 0
    for shape in tree.find('object'):
        bones = shape.find('skeleton')
        for mesh in shape.findall('mesh'):
            skin = mesh.find('skin')
            for i, (index, weight) in enumerate(zip(skin.attrib['ix'], skin.attrib['w'])):
                if not 0 <= index < len(bones):
                    assert weight == 0, (path, index, weight)
                    skin.attrib['ix'][i] = 0
                    changed += 1
    if changed:
        # Retain the exact native attachment transforms after binary reserialisation.
        data = path.read_bytes()
        marker = b'[locator\0'
        assert data.count(marker) == 1
        locators = data[data.index(marker):]
        pdx_data.write_meshfile(str(path), tree)
        data = path.read_bytes()
        path.write_bytes(data[:data.index(marker)] + locators)
    print(path.name, 'zero-weight indices repaired:', changed)


def bindings():
    gfx_path = ROOT / 'gfx/entities/ADISCORD_country_infantry.gfx'
    asset_path = ROOT / 'gfx/entities/zz_ADISCORD_country_infantry.asset'
    strip = lambda text: re.sub(re.escape(START) + '.*?' + re.escape(END), '', text, flags=re.S).rstrip() + '\n'
    gfx, asset = strip(gfx_path.read_text()), strip(asset_path.read_text())
    # NAM already had eight generic base entities in the shared minor-country
    # section. Remove those definitions before emitting the Arab replacement;
    # duplicate entity names make Clausewitz keep the earlier mesh silently.
    asset = re.sub(
        r'(?m)^entity = \{[^\r\n]*name = "NAM_infantry(?:_[2-8])?_entity"[^\r\n]*\}\r?\n',
        '',
        asset,
    )
    templates = {re.search(r'name\s*=\s*"([^"]+)"', b)[1]: b for b in blocks(gfx, 'pdxmesh')}
    meshes, entities = [], []
    # ARB is one shared mesh; country aliases below keep the engine's normal
    # <TAG>_infantry_entity lookup without duplicating binary assets.
    output_tags = tuple(CONFIG) + ARAB_TAGS
    for tag in output_tags:
        source_tag = 'ARB' if tag in ARAB_TAGS else tag
        for pose in ('rifle', 'mg'):
            source = templates['STP_shabrat_' + ('mg_' if pose == 'mg' else '') + 'infantry_mesh']
            source = re.sub(r'\bname\s*=\s*"[^"]+"', f'name = "ADISCORD_{tag}_field_{pose}_mesh"', source, count=1)
            source = re.sub(r'\bfile\s*=\s*"[^"]+"', f'file = "gfx/models/units/ADISCORD_regulars/{source_tag}_field.mesh"', source, count=1)
            meshes.append(source)
        for level in range(8):
            suffix = '' if level == 0 else '_' + str(level + 1)
            pose = 'rifle' if level == 0 else 'mg'
            def entity(parent, name, pdxmesh=None):
                fields = [f'clone = "{parent}"', f'name = "{name}"']
                if pdxmesh:
                    fields.append(f'pdxmesh = "{pdxmesh}"')
                if tag in ('RUS', 'SHL'):
                    return 'entity = {\n\t' + '\n\t'.join(fields) + '\n}'
                return 'entity = { ' + ' '.join(fields) + ' }'

            entities.append(entity(f'STP_infantry{suffix}_entity', f'{tag}_infantry{suffix}_entity', f'ADISCORD_{tag}_field_{pose}_mesh'))
            for role in ('ADISCORD_militia', 'ADISCORD_territorial', 'mountaineers'):
                entities.append(entity(f'{tag}_infantry{suffix}_entity', f'{tag}_{role}{suffix}_entity'))
            for cosmetic in {'YPR': ('YPR_VAL_administration',), 'TFF': ('TFF_frontier_defense_confederation',), 'RUS': ('RUS_last_empire',)}.get(tag, ()):
                for role in ('infantry', 'ADISCORD_militia', 'ADISCORD_territorial', 'mountaineers'):
                    entities.append(entity(f'{tag}_{role}{suffix}_entity', f'{cosmetic}_{role}{suffix}_entity'))
    return {
        gfx_path: (gfx + '\n' + START + 'objectTypes = {\n' + '\n'.join(meshes) + '\n}\n' + END).encode(),
        asset_path: (asset + '\n' + START + '\n'.join(entities) + '\n' + END).encode(),
    }


def build(output):
    """Tailor the existing militia body without layering another torso over it."""
    import bpy
    import bmesh
    import inspect
    from types import SimpleNamespace
    from mathutils import Vector
    from mathutils.bvhtree import BVHTree
    from mathutils.interpolate import poly_3d_calc
    sys.path.insert(0, str(Path(__file__).parent))
    from infantry_polish import bake_diffuse
    sys.path.insert(0, str(Path.home() / 'AppData/Roaming/Blender Foundation/Blender/5.2/extensions/user_default'))
    from io_pdx_mesh.pdx_blender import blender_import_export as pdx
    if not hasattr(pdx, "_northern_shader_source"):
        pdx._northern_shader_source = inspect.getsource(pdx.create_shader)
    source = pdx._northern_shader_source
    for line in ('    new_shader.shadow_method = "CLIP"', '    new_shader.blend_method = "CLIP"'):
        source = source.replace(line, '')
    exec(compile(source, '<Blender material compatibility>', 'exec'), pdx.__dict__)
    output.mkdir(parents=True, exist_ok=True)
    donor = ROOT / 'gfx/models/units/APH_afg_militia.mesh'
    bpy.ops.wm.read_factory_settings(use_empty=True)
    pdx.import_meshfile(str(donor), imp_locs=False)
    scene = bpy.context.scene
    body = bpy.data.objects['AFG_militia_model']
    rig = next(m.object for m in body.modifiers if m.type == 'ARMATURE')
    for obj in list(scene.objects):
        if obj not in (body, rig):
            bpy.data.objects.remove(obj, do_unlink=True)
    body.name = 'COF_body'

    # Identify whole anatomical/garment islands across UV seams. cutting at a
    # height would leave a hat brim and remove part of the scalp underneath.
    key = lambda co: tuple(round(x, 4) for x in co)
    keys = [key(v.co) for v in body.data.vertices]
    adjacent = {k: set() for k in keys}
    for face in body.data.polygons:
        for a, b in zip(face.vertices, (*face.vertices[1:], face.vertices[0])):
            adjacent[keys[a]].add(keys[b])
            adjacent[keys[b]].add(keys[a])
    remaining, regions = set(keys), {}
    while remaining:
        seed = remaining.pop()
        component, stack = {seed}, [seed]
        while stack:
            for k in adjacent[stack.pop()]:
                if k in remaining:
                    remaining.remove(k)
                    component.add(k)
                    stack.append(k)
        low, high = min(k[2] for k in component), max(k[2] for k in component)
        name = 'cap' if low > 6.8 else 'skin' if low > 6 or len(component) < 100 else 'legs' if high < 4 else 'coat'
        regions.update({k: name for k in component})
    bm = bmesh.new()
    bm.from_mesh(body.data)
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if regions[key(v.co)] == 'cap'], context='VERTS')
    bm.to_mesh(body.data)
    bm.free()

    original = body.data.materials[0]
    def cloth(name, color, preserve=False):
        mat = original.copy() if preserve else bpy.data.materials.new(name)
        mat.name = name
        mat.use_nodes = True
        nodes, links = mat.node_tree.nodes, mat.node_tree.links
        shader = nodes.get('Principled BSDF')
        for socket in ('Normal', 'Roughness', 'Metallic'):
            for link in list(shader.inputs[socket].links):
                links.remove(link)
        shader.inputs['Roughness'].default_value = .90
        shader.inputs['Metallic'].default_value = 0
        coords = nodes.new('ShaderNodeTexCoord')
        noise = nodes.new('ShaderNodeTexNoise')
        noise.inputs['Scale'].default_value = 5.0
        noise.inputs['Detail'].default_value = 4
        links.new(coords.outputs['Object'], noise.inputs[0])
        ramp = nodes.new('ShaderNodeValToRGB')
        for element, factor in zip(ramp.color_ramp.elements, (.48, 1.18)):
            element.color = (*[c * factor for c in color], 1)
        links.new(noise.outputs['Fac'], ramp.inputs[0])
        if preserve:
            bw = nodes.new('ShaderNodeRGBToBW')
            links.new(shader.inputs['Base Color'].links[0].from_socket, bw.inputs[0])
            intensity = nodes.new('ShaderNodeMath')
            intensity.operation = 'MULTIPLY_ADD'
            intensity.inputs[1].default_value = .9
            intensity.inputs[2].default_value = .42
            links.new(bw.outputs[0], intensity.inputs[0])
            multiply = nodes.new('ShaderNodeMixRGB')
            multiply.blend_type = 'MULTIPLY'
            multiply.inputs[0].default_value = 1
            links.new(ramp.outputs[0], multiply.inputs[1])
            links.new(intensity.outputs[0], multiply.inputs[2])
            color_socket = multiply.outputs[0]
        else:
            color_socket = ramp.outputs[0]
        ao = nodes.new('ShaderNodeAmbientOcclusion')
        ao.inputs['Distance'].default_value = .15
        links.new(color_socket, ao.inputs['Color'])
        links.new(ao.outputs['Color'], shader.inputs['Base Color'])
        return mat

    materials = [cloth('Faded olive coat', (.14, .16, .092), True),
                 cloth('Brown wool sleeves', (.105, .075, .048), True),
                 cloth('Charcoal trousers', (.057, .055, .043), True),
                 cloth('Dusty boot leather', (.092, .065, .040), True),
                 cloth('Worn shoulder blanket', (.145, .122, .074)),
                 cloth('Canvas patches', (.22, .18, .10)),
                 cloth('Dark knitted cap', (.039, .030, .021))]
    for mat in materials:
        body.data.materials.append(mat)
    # Blend cloth zones in texture space. polygon-wise colour assignment leaves
    # large triangular colour borders on the low-resolution shoulder wrap.
    nodes, links = materials[0].node_tree.nodes, materials[0].node_tree.links
    ao = next(n for n in nodes if n.type == 'AMBIENT_OCCLUSION')
    base_color = ao.inputs['Color'].links[0].from_socket
    coordinates = nodes.new('ShaderNodeTexCoord')
    separate = nodes.new('ShaderNodeSeparateXYZ')
    links.new(coordinates.outputs['Object'], separate.inputs[0])
    def mask(axis, low, high):
        node = nodes.new('ShaderNodeMapRange')
        node.interpolation_type = 'SMOOTHSTEP'
        node.inputs['From Min'].default_value = low
        node.inputs['From Max'].default_value = high
        links.new(separate.outputs[axis], node.inputs['Value'])
        return node.outputs[0]
    back = nodes.new('ShaderNodeMath')
    back.operation = 'MULTIPLY'
    links.new(mask('Y', .28, .56), back.inputs[0])
    links.new(mask('Z', 3.65, 3.96), back.inputs[1])
    blanket = nodes.new('ShaderNodeMath')
    blanket.operation = 'MAXIMUM'
    links.new(back.outputs[0], blanket.inputs[0])
    links.new(mask('Z', 5.73, 6.04), blanket.inputs[1])
    blend = nodes.new('ShaderNodeMixRGB')
    links.new(blanket.outputs[0], blend.inputs[0])
    links.new(base_color, blend.inputs[1])
    blend.inputs[2].default_value = (.115, .095, .061, 1)
    absolute = nodes.new('ShaderNodeMath')
    absolute.operation = 'ABSOLUTE'
    links.new(separate.outputs['X'], absolute.inputs[0])
    distance = nodes.new('ShaderNodeMath')
    distance.operation = 'SUBTRACT'
    distance.inputs[1].default_value = .31
    links.new(absolute.outputs[0], distance.inputs[0])
    absolute_distance = nodes.new('ShaderNodeMath')
    absolute_distance.operation = 'ABSOLUTE'
    links.new(distance.outputs[0], absolute_distance.inputs[0])
    stripe = nodes.new('ShaderNodeMath')
    stripe.operation = 'LESS_THAN'
    stripe.inputs[1].default_value = .045
    links.new(absolute_distance.outputs[0], stripe.inputs[0])
    stripe_height = nodes.new('ShaderNodeMath')
    stripe_height.operation = 'MULTIPLY'
    links.new(stripe.outputs[0], stripe_height.inputs[0])
    links.new(mask('Z', 5.3, 5.43), stripe_height.inputs[1])
    straps = nodes.new('ShaderNodeMixRGB')
    links.new(stripe_height.outputs[0], straps.inputs[0])
    links.new(blend.outputs[0], straps.inputs[1])
    straps.inputs[2].default_value = (.034, .023, .014, 1)
    links.new(straps.outputs[0], ao.inputs['Color'])
    for face in body.data.polygons:
        region = regions[key(body.data.vertices[face.vertices[0]].co)]
        x, y, z = face.center
        if region == 'skin':
            face.material_index = 0
        elif region == 'legs':
            face.material_index = 4 if z < 1.1 else 3
        elif region == 'coat':
            face.material_index = 1
    for vertex in body.data.vertices:
        if regions[key(vertex.co)] == 'coat' and vertex.co.z < 2.45:
            # Small uneven wear keeps the original split coat and leg weights.
            vertex.co.z += max(0, (2.45 - vertex.co.z) / .41) * (.035 + .10 * math.sin(vertex.co.x * 13) ** 8)
    body.data.update()
    bake_diffuse(body, output / 'COF_body.png', 'COF_body')
    surface = BVHTree.FromPolygons([v.co for v in body.data.vertices], [list(p.vertices) for p in body.data.polygons])
    gear = []
    def mesh(name, vertices, faces, material, bone='back_mid'):
        data = bpy.data.meshes.new(name)
        data.from_pydata(vertices, [], faces)
        data.update()
        obj = bpy.data.objects.new(name, data)
        scene.collection.objects.link(obj)
        obj.data.materials.append(material)
        obj.vertex_groups.new(name=bone).add(list(range(len(vertices))), 1, 'REPLACE')
        obj.modifiers.new('Infantry rig', 'ARMATURE').object = rig
        gear.append(obj)
        return obj

    def fitted_weights(obj):
        obj.vertex_groups.clear()
        for vertex in obj.data.vertices:
            point, _, index, _ = surface.find_nearest(vertex.co)
            face = body.data.polygons[index]
            factors = poly_3d_calc([body.data.vertices[i].co for i in face.vertices], point)
            weights = {}
            for i, factor in zip(face.vertices, factors):
                for group in body.data.vertices[i].groups:
                    name = body.vertex_groups[group.group].name
                    weights[name] = weights.get(name, 0) + max(0, factor) * group.weight
            strongest = sorted(weights.items(), key=lambda pair: pair[1], reverse=True)[:4]
            total = sum(w for _, w in strongest)
            for name, weight in strongest:
                group = obj.vertex_groups.get(name) or obj.vertex_groups.new(name=name)
                group.add([vertex.index], weight / total, 'REPLACE')

    def patch(name, cx, cz, width, height):
        vertices = []
        for row in range(6):
            for col in range(6):
                x = cx + (col / 5 - .5) * width
                z = cz + (row / 5 - .5) * height + .025 * math.sin(col * 2.3)
                hit, normal, _, _ = surface.ray_cast(Vector((x, -3, z)), Vector((0, 1, 0)), 6)
                assert hit is not None
                vertices.append(tuple(hit + normal * .018))
        obj = mesh(name, vertices, [(r * 6 + c, r * 6 + c + 1, (r + 1) * 6 + c + 1, (r + 1) * 6 + c) for r in range(5) for c in range(5)], materials[5])
        fitted_weights(obj)
        return obj
    patch('Lower coat repair', -.38, 2.9, .37, .45)
    patch('Chest repair', .34, 5.12, .29, .31)
    patch('Side coat repair', -.55, 4.12, .20, .24)

    # The crown follows the scalp rather than using a scaled helmet shell.
    vertices, faces = [], []
    rows, segments = 12, 40
    for row in range(rows):
        t = row / (rows - 1)
        for i in range(segments):
            a = math.tau * i / segments
            radius = math.cos(t * math.pi / 2)
            vertices.append((.405 * radius * math.cos(a) + .045 * t, -.02 + .435 * radius * math.sin(a) + .025 * t, 6.98 + .42 * math.sin(t * math.pi / 2)))
    faces = [(r * segments + i, r * segments + (i + 1) % segments, (r + 1) * segments + (i + 1) % segments, (r + 1) * segments + i) for r in range(rows - 1) for i in range(segments)]
    mesh('Soft knitted crown', vertices, faces, materials[6], 'head')
    vertices = [(.413 * math.cos(i * math.tau / 64), -.02 + .443 * math.sin(i * math.tau / 64), 6.985 + row * .11) for row in range(2) for i in range(64)]
    mesh('Turned cap hem', vertices, [(i, (i + 1) % 64, (i + 1) % 64 + 64, i + 64) for i in range(64)], materials[6], 'head')
    vertices = []
    for row in range(13):
        t = row / 12
        width = .40 * math.sin(math.pi * (.06 + .87 * t)) ** .55
        for i in range(32):
            a = math.tau * i / 32
            folds = 1 + .045 * math.sin(7 * a + 3 * t)
            vertices.append((.08 + width * math.cos(a) * folds, 1.05 + .67 * width * math.sin(a) * folds, 4.30 + 1.40 * t))
    faces = [(r * 32 + i, r * 32 + (i + 1) % 32, (r + 1) * 32 + (i + 1) % 32, (r + 1) * 32 + i) for r in range(12) for i in range(32)]
    faces.extend((tuple(reversed(range(32))), tuple(range(384, 416))))
    mesh('Gathered canvas sack', vertices, faces, materials[4])

    bpy.ops.object.select_all(action='DESELECT')
    for obj in gear:
        obj.select_set(True)
        for face in obj.data.polygons:
            face.use_smooth = True
    bpy.context.view_layer.objects.active = gear[0]
    bpy.ops.object.join()
    equipment = bpy.context.object
    equipment.name = 'COF_gear'
    solid = equipment.modifiers.new('Cloth thickness', 'SOLIDIFY')
    solid.thickness = .009
    bpy.ops.object.modifier_apply(modifier=solid.name)
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.smart_project(island_margin=.015)
    bpy.ops.object.mode_set(mode='OBJECT')
    bake_diffuse(equipment, output / 'COF_gear.png', 'COF_gear')
    for obj, part in ((body, 'body'), (equipment, 'gear')):
        (output / f'COF_field_{part}_diffuse.dds').write_bytes((output / f'COF_{part}.png').read_bytes())
        for kind in ('normal', 'specular'):
            (output / f'COF_field_{part}_{kind}.dds').write_bytes((ROOT / f'gfx/models/units/APH_afg_militia_{kind}.dds').read_bytes())
        bm = bmesh.new()
        bm.from_mesh(obj.data)
        bmesh.ops.triangulate(bm, faces=list(bm.faces))
        bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
        bmesh.ops.delete(bm, geom=[f for f in bm.faces if f.calc_area() < 1e-12], context='FACES_ONLY')
        bm.to_mesh(obj.data)
        bm.free()
        spec = SimpleNamespace(shader=['PdxMeshAdvanced'], diff=[f'COF_field_{part}_diffuse.dds'], n=[f'COF_field_{part}_normal.dds'], spec=[f'COF_field_{part}_specular.dds'])
        mat = pdx.create_shader(spec, 'COF_' + part, str(output))
        obj.data.materials.clear()
        obj.data.materials.append(mat)
        for face in obj.data.polygons:
            face.material_index = 0
    bpy.ops.object.select_all(action='DESELECT')
    body.select_set(True)
    equipment.select_set(True)
    path = output / 'COF_field.mesh'
    pdx.export_meshfile(str(path), exp_selected=True, exp_locs=False)
    data, donor_data = path.read_bytes(), donor.read_bytes()
    marker = b'[locator\0'
    assert data.count(marker) == donor_data.count(marker) == 1
    path.write_bytes(data[:data.index(marker)] + donor_data[donor_data.index(marker):])
    finalize_mesh(path)
    bpy.ops.wm.save_as_mainfile(filepath=str(output / 'COF.blend'))
    (output / 'build.json').write_text(json.dumps({'donor_sha256': hashlib.sha256(donor_data).hexdigest(), 'mesh_sha256': hashlib.sha256(path.read_bytes()).hexdigest()}, indent=2))


def imperial_carrier(body, mesh, cloth, trim, brass):
    """Fit segmented armour to the donor surface and interpolate its skin."""
    from mathutils import Vector
    from mathutils.bvhtree import BVHTree
    from mathutils.interpolate import poly_3d_calc

    surface = BVHTree.FromPolygons(
        [v.co for v in body.data.vertices],
        [list(p.vertices) for p in body.data.polygons],
    )
    armour = cloth('Charcoal armour', (.072, .083, .087))
    webbing = cloth('Carrier webbing', (.10, .075, .047))

    def panel(name, cx, cz, width, height, material, back=False, offset=.055):
        vertices = []
        weights = []
        segments = 6
        for row in range(segments + 1):
            for col in range(segments + 1):
                x = cx + (col / segments - .5) * width
                z = cz + (row / segments - .5) * height
                origin = Vector((x, 3 if back else -3, z))
                direction = Vector((0, -1 if back else 1, 0))
                point, normal, index, _ = surface.ray_cast(origin, direction, 6)
                assert point is not None, (name, x, z)
                vertices.append(tuple(point + normal * offset))
                face = body.data.polygons[index]
                factors = poly_3d_calc([body.data.vertices[i].co for i in face.vertices], point)
                influence = {}
                for i, factor in zip(face.vertices, factors):
                    for group in body.data.vertices[i].groups:
                        bone = body.vertex_groups[group.group].name
                        influence[bone] = influence.get(bone, 0) + max(0, factor) * group.weight
                strongest = sorted(influence.items(), key=lambda item: item[1], reverse=True)[:4]
                total = sum(w for _, w in strongest)
                weights.append([(bone, w / total) for bone, w in strongest])
        stride = segments + 1
        faces = [(r * stride + c, r * stride + c + 1,
                  (r + 1) * stride + c + 1, (r + 1) * stride + c)
                 for r in range(segments) for c in range(segments)]
        obj = mesh(name, vertices, faces, material)
        obj.vertex_groups.clear()
        for i, influence in enumerate(weights):
            for bone, weight in influence:
                group = obj.vertex_groups.get(bone) or obj.vertex_groups.new(name=bone)
                group.add([i], weight, 'REPLACE')
        return obj

    for back in (False, True):
        side = 'Rear' if back else 'Front'
        for x in (-.42, .42):
            panel(side + ' carrier strap', x, 5.25, .15, 1.23, webbing, back)
        for z, width in ((5.48, .78), (5.12, .90), (4.77, .82)):
            panel(side + ' armour segment', 0, z, width, .30, armour, back, .09)
        panel(side + ' central brass clasp', 0, 5.48, .055, .23, brass, back, .12)
    panel('Burgundy breast tab', -.53, 5.61, .16, .35, trim)
    panel('Brass breast tab edge', -.53, 5.68, .12, .045, brass, offset=.07)


def build_field(tag, output):
    """Keep the donor garment topology and skin while replacing its field kit."""
    import bpy
    import bmesh
    import inspect
    from types import SimpleNamespace
    from mathutils import Vector
    sys.path.insert(0, str(Path(__file__).parent))
    from infantry_polish import bake_diffuse, cloth_bag, fitted_head_cloth
    sys.path.insert(0, str(Path.home() / 'AppData/Roaming/Blender Foundation/Blender/5.2/extensions/user_default'))
    from io_pdx_mesh.pdx_blender import blender_import_export as pdx
    if not hasattr(pdx, "_northern_shader_source"):
        pdx._northern_shader_source = inspect.getsource(pdx.create_shader)
    source = pdx._northern_shader_source
    for line in ('    new_shader.shadow_method = "CLIP"', '    new_shader.blend_method = "CLIP"'):
        source = source.replace(line, '')
    exec(compile(source, '<Blender material compatibility>', 'exec'), pdx.__dict__)
    output.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    donor = CONFIG[tag]
    pdx.import_meshfile(str(donor), imp_locs=False)
    scene = bpy.context.scene
    body = max((o for o in scene.objects if o.type == 'MESH'), key=lambda o: len(o.data.polygons))
    rig = next(m.object for m in body.modifiers if m.type == 'ARMATURE')
    for obj in list(scene.objects):
        if obj not in (body, rig):
            bpy.data.objects.remove(obj, do_unlink=True)
    body.name = tag + '_body'
    # Whole islands keep native leather pouches separate from cloth tinting.
    small_kit = set()
    if tag in ('TFF', 'YPR', 'RUS', 'NAM'):
        keys = [tuple(round(x, 4) for x in v.co) for v in body.data.vertices]
        adjacent = {k: set() for k in keys}
        for face in body.data.polygons:
            for a, b in zip(face.vertices, (*face.vertices[1:], face.vertices[0])):
                adjacent[keys[a]].add(keys[b])
                adjacent[keys[b]].add(keys[a])
        remaining, cap = set(keys), set()
        while remaining:
            seed = remaining.pop()
            component, stack = {seed}, [seed]
            while stack:
                for k in adjacent[stack.pop()]:
                    if k in remaining:
                        remaining.remove(k)
                        component.add(k)
                        stack.append(k)
            if min(k[2] for k in component) > 6.9:
                cap.update(component)
            if min(k[2] for k in component) > 3.8 and max(k[2] for k in component) < 5 and len(component) < 100:
                small_kit.update(component)
        if tag in ('TFF', 'RUS', 'NAM'):
            assert cap
            bm = bmesh.new()
            bm.from_mesh(body.data)
            bmesh.ops.delete(bm, geom=[v for v in bm.verts if tuple(round(x, 4) for x in v.co) in cap], context='VERTS')
            bm.to_mesh(body.data)
            bm.free()
    original = body.data.materials[0]

    def cloth(name, color, detail=False):
        material = original.copy() if detail else bpy.data.materials.new(name)
        material.name = name
        material.use_nodes = True
        nodes, links = material.node_tree.nodes, material.node_tree.links
        shader = nodes.get('Principled BSDF')
        for socket in ('Normal', 'Roughness', 'Metallic'):
            for link in list(shader.inputs[socket].links):
                links.remove(link)
        shader.inputs['Roughness'].default_value = .85
        shader.inputs['Metallic'].default_value = 0
        coordinates = nodes.new('ShaderNodeTexCoord')
        noise = nodes.new('ShaderNodeTexNoise')
        noise.inputs['Scale'].default_value = 13
        noise.inputs['Detail'].default_value = 3
        links.new(coordinates.outputs['Object'], noise.inputs[0])
        ramp = nodes.new('ShaderNodeValToRGB')
        for element, factor in zip(ramp.color_ramp.elements, (.72, 1.16)):
            element.color = (*[c * factor for c in color], 1)
        links.new(noise.outputs['Fac'], ramp.inputs[0])
        color_socket = ramp.outputs[0]
        if detail:
            bw = nodes.new('ShaderNodeRGBToBW')
            links.new(shader.inputs['Base Color'].links[0].from_socket, bw.inputs[0])
            # Neutralise native insignia on upper sleeves and shoulder boards.
            separate = nodes.new('ShaderNodeSeparateXYZ')
            links.new(coordinates.outputs['Object'], separate.inputs[0])
            absolute = nodes.new('ShaderNodeMath')
            absolute.operation = 'ABSOLUTE'
            links.new(separate.outputs['X'], absolute.inputs[0])
            outside = nodes.new('ShaderNodeMath')
            outside.operation = 'GREATER_THAN'
            outside.inputs[1].default_value = .55
            links.new(absolute.outputs[0], outside.inputs[0])
            upper = nodes.new('ShaderNodeMapRange')
            upper.interpolation_type = 'SMOOTHSTEP'
            upper.inputs['From Min'].default_value = 5.15
            upper.inputs['From Max'].default_value = 5.50
            links.new(separate.outputs['Z'], upper.inputs['Value'])
            region = nodes.new('ShaderNodeMath')
            region.operation = 'MULTIPLY'
            links.new(outside.outputs[0], region.inputs[0])
            links.new(upper.outputs[0], region.inputs[1])
            clean = nodes.new('ShaderNodeMixRGB')
            links.new(region.outputs[0], clean.inputs[0])
            links.new(bw.outputs[0], clean.inputs[1])
            clean.inputs[2].default_value = (.50, .50, .50, 1)
            intensity = nodes.new('ShaderNodeMath')
            intensity.operation = 'MULTIPLY_ADD'
            intensity.inputs[1].default_value = .90
            intensity.inputs[2].default_value = .36
            links.new(clean.outputs[0], intensity.inputs[0])
            multiply = nodes.new('ShaderNodeMixRGB')
            multiply.blend_type = 'MULTIPLY'
            multiply.inputs[0].default_value = 1
            links.new(ramp.outputs[0], multiply.inputs[1])
            links.new(intensity.outputs[0], multiply.inputs[2])
            color_socket = multiply.outputs[0]
        ao = nodes.new('ShaderNodeAmbientOcclusion')
        ao.inputs['Distance'].default_value = .12
        links.new(color_socket, ao.inputs['Color'])
        links.new(ao.outputs['Color'], shader.inputs['Base Color'])
        return material

    olive = (.155, .178, .105)
    if tag in ('SHL', 'ARB'):
        jacket_color = (.36, .22, .09)
        trouser_color = (.22, .19, .12)
        canvas_color = (.48, .33, .16)
        wool_color = (.08, .055, .035)
        scarf_color = (.68, .53, .30)
    elif tag == 'RUS':
        jacket_color = (.046, .062, .072)
        trouser_color = (.035, .040, .048)
        canvas_color = (.11, .075, .045)
        wool_color = (.026, .033, .042)
        scarf_color = (.24, .022, .035)
    elif tag == 'NAM':
        jacket_color = (.055, .095, .105)
        trouser_color = (.035, .048, .052)
        canvas_color = (.12, .075, .035)
        wool_color = (.025, .045, .050)
        scarf_color = (.62, .38, .075)
    else:
        jacket_color = olive if tag == 'YPR' else (.16, .105, .055)
        trouser_color = (.12, .14, .085) if tag == 'YPR' else (.055, .068, .065)
        canvas_color = (.14, .15, .09) if tag == 'YPR' else (.13, .10, .067)
        wool_color = (.065, .083, .070)
        scarf_color = (.20, .215, .20)
    jacket = cloth('Field jacket', jacket_color, True)
    trousers = cloth('Field trousers', trouser_color, True)
    canvas = cloth('Field canvas', canvas_color)
    wool = cloth('Wool and bindings', wool_color)
    scarf = cloth('Frontier wool scarf', scarf_color)
    for mat in (jacket, trousers, canvas):
        body.data.materials.append(mat)
    for face in body.data.polygons:
        x, y, z = face.center
        # Bare head, hands and original boot leather keep their authored atlas.
        skin = (z > 6.13 and abs(x) < .44) or (abs(x) > 2.30 and 3.9 < z < 4.85)
        if tag == 'YPR' and z > 6.80:
            face.material_index = 3
        elif skin or z < 1.15 or tuple(round(v, 4) for v in body.data.vertices[face.vertices[0]].co) in small_kit:
            face.material_index = 0
        else:
            # The trouser island includes the crotch above the jacket hem. A
            # height cutoff splits its triangles and leaves a jagged colour seam.
            uv = sum((body.data.uv_layers.active.data[i].uv for i in face.loop_indices), Vector((0, 0))) / len(face.loop_indices)
            pants = uv.x < .44 and uv.y < .45 if tag in ('TFF', 'RUS', 'NAM') else z < 3.55
            face.material_index = 2 if pants else 1
    bake_diffuse(body, output / f'{tag}_body.png', tag + '_body')
    gear = []
    def mesh(name, vertices, faces, material, bone='back_mid'):
        data = bpy.data.meshes.new(name)
        data.from_pydata(vertices, [], faces)
        data.update()
        obj = bpy.data.objects.new(name, data)
        scene.collection.objects.link(obj)
        obj.data.materials.append(material)
        obj.vertex_groups.new(name=bone).add(list(range(len(vertices))), 1, 'REPLACE')
        obj.modifiers.new('Infantry rig', 'ARMATURE').object = rig
        gear.append(obj)
        return obj
    if tag == 'YPR':
        for part, kind, vertices, faces in cloth_bag(.95, .34, .92, (-.22, .22)):
            mesh('Field pack ' + part, [(x, y + .83, z + 5.07) for x, y, z in vertices], faces, canvas if kind == 'canvas' else wool)
    else:
        vertices = []
        for row in range(12):
            t = row / 11
            for i in range(40):
                a = math.tau * i / 40
                if tag == 'RUS':
                    radius = 1.07 * math.cos(t * math.pi / 2)
                    height = 7.04 + .34 * math.sin(t * math.pi / 2) ** .30
                elif tag == 'NAM':
                    radius = 1.02 * math.cos(t * math.pi / 2)
                    height = 6.98 + .42 * math.sin(t * math.pi / 2) ** .38
                else:
                    radius = math.cos(t * math.pi / 2)
                    height = 6.91 + .38 * math.sin(t * math.pi / 2)
                vertices.append((.43 * radius * math.cos(a) + .025 * t, -.07 + .49 * radius * math.sin(a), height))
        mesh('Knitted field cap', vertices, [(r * 40 + i, r * 40 + (i + 1) % 40, (r + 1) * 40 + (i + 1) % 40, (r + 1) * 40 + i) for r in range(11) for i in range(40)], wool, 'head')
        vertices = [(.44 * math.cos(i * math.tau / 40), -.07 + .50 * math.sin(i * math.tau / 40), 6.91 + r * .12) for r in range(2) for i in range(40)]
        mesh('Cap fold', vertices, [(i, (i + 1) % 40, (i + 1) % 40 + 40, i + 40) for i in range(40)], wool, 'head')
        if tag in ('RUS', 'NAM'):
            brass = cloth('Dull brass insignia', (.48, .29, .095))
            brim_vertices = []
            for outer in (False, True):
                for i in range(21):
                    a = math.pi + math.pi * i / 20
                    brim_vertices.append((.43 * math.cos(a), -.07 + (.69 if outer else .42) * math.sin(a), 6.98 - (.075 if outer else 0) * abs(math.sin(a))))
            mesh('Imperial cap visor', brim_vertices,
                 [(i, i + 1, i + 22, i + 21) for i in range(20)], wool, 'head')
            band_vertices = []
            for z in (6.99, 7.10):
                for i in range(40):
                    a = math.tau * i / 40
                    band_vertices.append((.47 * math.cos(a), -.07 + .53 * math.sin(a), z))
            mesh('Imperial cap band', band_vertices,
                 [(i, (i + 1) % 40, (i + 1) % 40 + 40, i + 40) for i in range(40)], scarf, 'head')
            badge_vertices = [(0, -.577, 7.00), (.075, -.577, 7.09),
                              (0, -.577, 7.20), (-.075, -.577, 7.09)]
            mesh('Imperial cap badge', badge_vertices, [(0, 1, 2, 3)], brass, 'head')
            imperial_carrier(body, mesh, cloth, scarf, brass)
        # A compact neck wrap leaves both hands and the rifle stock unobstructed.
        vertices = []
        for row in range(6):
            t = row / 5
            for i in range(40):
                a = math.tau * i / 40
                radius = .37 + .045 * math.sin(t * math.pi)
                vertices.append((radius * math.cos(a), -.08 + (radius + .06) * math.sin(a), 5.98 + .38 * t + .025 * math.sin(3 * a)))
        mesh('Wool neck wrap', vertices, [(r * 40 + i, r * 40 + (i + 1) % 40, (r + 1) * 40 + (i + 1) % 40, (r + 1) * 40 + i) for r in range(5) for i in range(40)], scarf, 'head')
        for part, kind, vertices, faces in cloth_bag(.50, .35, .61):
            mesh('Canvas haversack ' + part, [(x + .72, y + .37, z + 4.23) for x, y, z in vertices], faces, canvas if kind == 'canvas' else wool, 'Hip')
        if tag == 'SHL':
            # The wrapped head cloth is the recognisable Arab field item and
            # follows the imported head weights instead of floating in poses.
            fitted_head_cloth(body, mesh, scarf, 'Wrapped Arab head cloth', loose=True)
    bpy.ops.object.select_all(action='DESELECT')
    for obj in gear:
        obj.select_set(True)
        for face in obj.data.polygons: face.use_smooth = True
    bpy.context.view_layer.objects.active = gear[0]
    bpy.ops.object.join()
    equipment = bpy.context.object
    equipment.name = tag + '_gear'
    solid = equipment.modifiers.new('Fabric thickness', 'SOLIDIFY')
    solid.thickness = .008
    bpy.ops.object.modifier_apply(modifier=solid.name)
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.smart_project(island_margin=.015)
    bpy.ops.object.mode_set(mode='OBJECT')
    bake_diffuse(equipment, output / f'{tag}_gear.png', tag + '_gear')
    for obj, part in ((body, 'body'), (equipment, 'gear')):
        (output / f'{tag}_field_{part}_diffuse.dds').write_bytes((output / f'{tag}_{part}.png').read_bytes())
        for kind in ('normal', 'specular'):
            (output / f'{tag}_field_{part}_{kind}.dds').write_bytes(NORMALS[tag].read_bytes())
        bm = bmesh.new()
        bm.from_mesh(obj.data)
        bmesh.ops.triangulate(bm, faces=list(bm.faces))
        bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
        bmesh.ops.delete(bm, geom=[f for f in bm.faces if f.calc_area() < 1e-12], context='FACES_ONLY')
        bm.to_mesh(obj.data)
        bm.free()
        spec = SimpleNamespace(shader=['PdxMeshAdvanced'], diff=[f'{tag}_field_{part}_diffuse.dds'], n=[f'{tag}_field_{part}_normal.dds'], spec=[f'{tag}_field_{part}_specular.dds'])
        mat = pdx.create_shader(spec, tag + '_' + part, str(output))
        obj.data.materials.clear()
        obj.data.materials.append(mat)
        for face in obj.data.polygons: face.material_index = 0
    bpy.ops.object.select_all(action='DESELECT')
    body.select_set(True)
    equipment.select_set(True)
    path = output / f'{tag}_field.mesh'
    pdx.export_meshfile(str(path), exp_selected=True, exp_locs=False)
    data, donor_data = path.read_bytes(), donor.read_bytes()
    marker = b'[locator\0'
    assert data.count(marker) == donor_data.count(marker) == 1
    path.write_bytes(data[:data.index(marker)] + donor_data[donor_data.index(marker):])
    finalize_mesh(path)
    bpy.ops.wm.save_as_mainfile(filepath=str(output / f'{tag}.blend'))


def verify(output, tags, walk=False):
    """Re-import packaged meshes, inspect skin contracts and sample native poses."""
    import bpy
    import inspect
    from mathutils import Vector
    sys.path.insert(0, str(Path.home() / 'AppData/Roaming/Blender Foundation/Blender/5.2/extensions/user_default'))
    from io_pdx_mesh.pdx_blender import blender_import_export as pdx
    from io_pdx_mesh import pdx_data
    if not hasattr(pdx, "_northern_shader_source"):
        pdx._northern_shader_source = inspect.getsource(pdx.create_shader)
    source = pdx._northern_shader_source
    for line in ('    new_shader.shadow_method = "CLIP"', '    new_shader.blend_method = "CLIP"'):
        source = source.replace(line, '')
    exec(compile(source, '<Blender material compatibility>', 'exec'), pdx.__dict__)
    report = {}
    for tag in tags:
        donor = pdx_data.read_meshfile(str(CONFIG[tag]))
        donor_bones = next(s.find('skeleton') for s in donor.find('object') if s.find('skeleton') is not None)
        path = output / 'package/gfx/models/units/ADISCORD_regulars' / f'{tag}_field.mesh'
        tree = pdx_data.read_meshfile(str(path))
        assert [(n.tag, n.attrib) for n in tree.find('locator')] == [(n.tag, n.attrib) for n in donor.find('locator')]
        shapes = []
        for shape in tree.find('object'):
            bones = shape.find('skeleton')
            assert [b.tag for b in bones] == [b.tag for b in donor_bones]
            for element in shape.findall('mesh'):
                data = pdx_data.PDXData(element)
                count = len(data.p) // 3
                assert 0 < count < 65536
                assert len(data.n) == 3 * count and len(data.u0) == 2 * count
                assert all(math.isfinite(x) for x in data.p + data.n + data.u0)
                assert len(data.tri) % 3 == 0 and min(data.tri) >= 0 and max(data.tri) < count
                influences = data.skin.bones[0]
                assert 1 <= influences <= 4
                assert len(data.skin.w) == len(data.skin.ix) == count * influences
                assert all(0 <= i < len(bones) for i in data.skin.ix)
                weighted = set()
                for i in range(count):
                    weights = data.skin.w[i * influences:(i + 1) * influences]
                    indices = data.skin.ix[i * influences:(i + 1) * influences]
                    assert abs(sum(weights) - 1) < .001
                    weighted.update(index for index, weight in zip(indices, weights) if weight > 0)
                for index in weighted:
                    bone, original = bones[index], donor_bones[index]
                    assert bone.attrib.get('pa') == original.attrib.get('pa')
                    assert max(abs(a - b) for a, b in zip(bone.attrib['tx'], original.attrib['tx'])) < .001
                for key in ('diff', 'n', 'spec'):
                    assert (path.parent / getattr(data.material, key)[0]).is_file()
                shapes.append({'vertices': count, 'triangles': len(data.tri) // 3, 'bones': len(bones)})
        bpy.ops.wm.read_factory_settings(use_empty=True)
        pdx.import_meshfile(str(path), imp_locs=False)
        scene = bpy.context.scene
        scene.render.engine = 'CYCLES'
        scene.cycles.samples = 24
        scene.render.resolution_x, scene.render.resolution_y = 650, 800
        scene.render.resolution_percentage = 100
        scene.world = bpy.data.worlds.new('Studio')
        scene.world.use_nodes = True
        scene.world.node_tree.nodes['Background'].inputs[0].default_value = (.16, .19, .23, 1)
        for mat in bpy.data.materials:
            if mat.use_nodes:
                shader = mat.node_tree.nodes.get('Principled BSDF')
                if shader:
                    roughness = shader.inputs['Roughness']
                    if roughness.is_linked:
                        mat.node_tree.links.remove(roughness.links[0])
                    roughness.default_value = .85
        for location, power, size in (((4, -8, 12), 1600, 7), ((-6, -1, 8), 950, 6), ((2, 5, 11), 1700, 5)):
            bpy.ops.object.light_add(type='AREA', location=location)
            obj = bpy.context.object
            obj.data.energy, obj.data.size = power, size
            obj.rotation_euler = (Vector((0, 0, 4)) - obj.location).to_track_quat('-Z', 'Y').to_euler()
        bpy.ops.object.camera_add(location=(9, -20, 9))
        camera = bpy.context.object
        camera.data.type, camera.data.ortho_scale = 'ORTHO', 8.7
        camera.rotation_euler = (Vector((0, 0, 3.7)) - camera.location).to_track_quat('-Z', 'Y').to_euler()
        scene.camera = camera
        rigs = [obj for obj in scene.objects if obj.type == 'ARMATURE']
        poses = {}
        for pose in ('idle_rifle', 'moving_rifle', 'attack_stand_rifle', 'idle_mg', 'moving_mg', 'attack_stand_mg'):
            for rig in rigs:
                rig.animation_data_clear()
            pdx.import_animfile(str(GAME / f'gfx/models/units/GER_infantry_{pose}.anim'))
            frames = (1, (scene.frame_end + 1) // 2, scene.frame_end)
            for frame in frames:
                scene.frame_set(frame)
                graph = bpy.context.evaluated_depsgraph_get()
                for obj in (o for o in scene.objects if o.type == 'MESH'):
                    evaluated = obj.evaluated_get(graph)
                    assert all(math.isfinite(x) for v in evaluated.data.vertices for x in v.co)
                    assert max((evaluated.matrix_world @ v.co).length for v in evaluated.data.vertices) < 20
            poses[pose] = frames
            if pose in ('idle_rifle', 'moving_rifle'):
                scene.frame_set(frames[1])
                scene.render.filepath = str(output / f'{tag}_{pose}.png')
                bpy.ops.render.render(write_still=True)
                if pose == 'idle_rifle':
                    bpy.ops.wm.save_as_mainfile(filepath=str(output / f'{tag}_preview.blend'))
                    camera.location = (-9, 20, 9)
                    camera.rotation_euler = (Vector((0, 0, 3.7)) - camera.location).to_track_quat('-Z', 'Y').to_euler()
                    scene.render.filepath = str(output / f'{tag}_back.png')
                    bpy.ops.render.render(write_still=True)
                    camera.location = (9, -20, 9)
                    camera.rotation_euler = (Vector((0, 0, 3.7)) - camera.location).to_track_quat('-Z', 'Y').to_euler()
                elif walk:
                    scene.cycles.samples = 12
                    scene.render.resolution_percentage = 65
                    for index in range(12):
                        scene.frame_set(1 + round(index * (scene.frame_end - 1) / 12))
                        scene.render.filepath = str(output / f'{tag}_walk_{index:02d}.png')
                        bpy.ops.render.render(write_still=True)
                    scene.cycles.samples = 24
                    scene.render.resolution_percentage = 100
        report[tag] = {
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            'textures': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in path.parent.glob(f'{tag}_field_*.dds')},
            'shapes': shapes, 'poses': poses,
        }
    report_path = output / 'verification.json'
    previous = json.loads(report_path.read_text()) if report_path.exists() else {}
    previous.update(report)
    report_path.write_text(json.dumps(previous, indent=2))
    print(json.dumps(report, indent=2))


def package(output, apply=False, check=False):
    import io
    import struct
    from PIL import Image
    files = bindings()
    dest = ROOT / 'gfx/models/units/ADISCORD_regulars'

    def dds(image, packed=False):
        image = image.convert('RGBA')
        levels = []
        while True:
            stream = io.BytesIO()
            image.save(stream, format='DDS', pixel_format='DXT5')
            levels.append(stream.getvalue())
            if image.size == (1, 1):
                break
            size = tuple(max(1, x // 2) for x in image.size)
            if packed:
                image = Image.merge('RGBA', tuple(channel.resize(size, Image.Resampling.BOX) for channel in image.split()))
            else:
                image = image.resize(size, Image.Resampling.LANCZOS)
        header = bytearray(levels[0][:128])
        struct.pack_into('<I', header, 8, struct.unpack_from('<I', header, 8)[0] | 0x20000)
        struct.pack_into('<I', header, 28, len(levels))
        struct.pack_into('<I', header, 108, 0x401008)
        return bytes(header) + b''.join(level[128:] for level in levels)

    for tag in CONFIG:
        files[dest / f'{tag}_field.mesh'] = (output / f'{tag}_field.mesh').read_bytes()
        for part in ('body', 'gear'):
            files[dest / f'{tag}_field_{part}_diffuse.dds'] = dds(Image.open(output / f'{tag}_{part}.png'))
            normal = Image.open(NORMALS[tag]) if part == 'body' else Image.new('RGBA', (512, 512), (255, 128, 0, 128))
            files[dest / f'{tag}_field_{part}_normal.dds'] = dds(normal, True)
            files[dest / f'{tag}_field_{part}_specular.dds'] = dds(Image.new('RGBA', (512, 512), (0, 48, 0, 36)), True)
    changed = [str(path.relative_to(ROOT)) for path, content in files.items() if not path.exists() or path.read_bytes() != content]
    if apply:
        verified = json.loads((output / 'verification.json').read_text())
        for tag in CONFIG:
            assert verified[tag]['sha256'] == hashlib.sha256(files[dest / f'{tag}_field.mesh']).hexdigest(), tag + ': re-run --verify'
            assert len(verified[tag]['textures']) == 6
            for name, digest in verified[tag]['textures'].items():
                assert digest == hashlib.sha256(files[dest / name]).hexdigest(), name + ': re-run --verify'
        for path, content in files.items():
            if str(path.relative_to(ROOT)) in changed:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(content)
    elif not check:
        preview = output / 'package'
        for path, content in files.items():
            target = preview / path.relative_to(ROOT)
            target.parent.mkdir(parents=True, exist_ok=True)
            if not target.exists() or target.read_bytes() != content:
                target.write_bytes(content)
    print(json.dumps({'changed': changed, 'apply': apply}, indent=2))
    if check and changed:
        raise SystemExit(1)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--tags', nargs='+', choices=tuple(CONFIG), default=tuple(CONFIG))
    parser.add_argument('--walk', action='store_true', help='Render twelve additional walking frames.')
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--build', action='store_true')
    mode.add_argument('--verify', action='store_true')
    mode.add_argument('--finalize', action='store_true', help='Validate and repair unused skin slots in staged exports.')
    mode.add_argument('--apply', action='store_true')
    mode.add_argument('--check', action='store_true')
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else None)
    if args.build:
        for tag in args.tags:
            if tag == 'COF':
                build(args.output.resolve())
            else:
                build_field(tag, args.output.resolve())
    elif args.verify:
        verify(args.output.resolve(), args.tags, args.walk)
    elif args.finalize:
        for tag in args.tags:
            finalize_mesh(args.output.resolve() / f'{tag}_field.mesh')
    else:
        package(args.output.resolve(), args.apply, args.check)
