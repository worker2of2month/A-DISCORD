"""Build regional infantry models. Preview before installing with --apply.

Blender: --background --python this_file -- --build --output PATH
Python: this_file --output PATH (stages the preview package)
Blender: --background --python this_file -- --verify --output PATH
Python: this_file --output PATH --apply, then --check
Uses the existing militia rig and locators. HAZ replaces the body with the
packed HAZ_sentinel_source.blend and fits its weights to the native rig.
Use --assets-only with --tags HAZ to retain its existing entity bindings.
Only the marked northern bindings and named model package belong to this builder.
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
RETINUE_STYLES = {
    'BJK': {'coat': (0.20, 0.025, 0.15), 'trim': (0.64, 0.39, 0.10), 'helmet': 'crown'},
    'BLD': {'coat': (0.085, 0.045, 0.18), 'trim': (0.48, 0.51, 0.55), 'helmet': 'ridge'},
    'BHG': {'coat': (0.24, 0.065, 0.095), 'trim': (0.53, 0.32, 0.14), 'helmet': 'nasal'},
    'BGT': {'coat': (0.038, 0.035, 0.065), 'trim': (0.63, 0.58, 0.45), 'helmet': 'order'},
    'BBV': {'coat': (0.115, 0.085, 0.052), 'trim': (0.34, 0.025, 0.10), 'helmet': 'brim'},
    'BCM': {'coat': (0.075, 0.085, 0.11), 'trim': (0.51, 0.43, 0.29), 'helmet': 'ridge'},
}
CONFIG = {
    'COF': ROOT / 'gfx/models/units/APH_afg_militia.mesh',
    'YPR': GAME / 'gfx/models/units/eastern_european_infantry.mesh',
    'TFF': ROOT / 'gfx/models/units/STP_infantry_hedonist.mesh',
    # Preserve the native rig and locators while replacing garments and kit.
    'RUS': ROOT / 'gfx/models/units/STP_infantry_hedonist.mesh',
    'SHL': ROOT / 'gfx/models/units/APH_irregular_infantry.mesh',
    'ARB': ROOT / 'gfx/models/units/APH_irregular_infantry.mesh',
    'NAM': ROOT / 'gfx/models/units/STP_infantry_hedonist.mesh',
    'HAZ': ROOT / 'gfx/models/units/STP_infantry_hedonist.mesh',
    'MON': ROOT / 'gfx/models/units/STP_infantry_hedonist.mesh',
    **{
        tag: ROOT / 'gfx/models/units/STP_infantry_hedonist.mesh'
        for tag in RETINUE_STYLES
    },
}
NORMALS = {
    'COF': ROOT / 'gfx/models/units/APH_afg_militia_normal.dds',
    'YPR': GAME / 'gfx/models/units/eastern_european_infantry_normal.dds',
    'TFF': ROOT / 'gfx/models/units/STP_infantry_hedonist__normal.dds',
    'RUS': ROOT / 'gfx/models/units/STP_infantry_hedonist__normal.dds',
    'SHL': ROOT / 'gfx/models/units/APH_irregular_infantry_normal.dds',
    'ARB': ROOT / 'gfx/models/units/APH_irregular_infantry_normal.dds',
    'NAM': ROOT / 'gfx/models/units/STP_infantry_hedonist__normal.dds',
    'HAZ': ROOT / 'gfx/models/units/STP_infantry_hedonist__normal.dds',
    'MON': ROOT / 'gfx/models/units/STP_infantry_hedonist__normal.dds',
    **{
        tag: ROOT / 'gfx/models/units/STP_infantry_hedonist__normal.dds'
        for tag in RETINUE_STYLES
    },
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
        yield text[match.start() : end]


def finalize_mesh(path):
    """The native shader dereferences four bone indices even at zero weight."""
    sys.path.insert(
        0,
        str(
            Path.home()
            / 'AppData/Roaming/Blender Foundation/Blender/5.2/extensions/user_default'
        ),
    )
    from io_pdx_mesh import pdx_data

    tree = pdx_data.read_meshfile(str(path))
    changed = 0
    for shape in tree.find('object'):
        bones = shape.find('skeleton')
        for mesh in shape.findall('mesh'):
            skin = mesh.find('skin')
            for i, (index, weight) in enumerate(
                zip(skin.attrib['ix'], skin.attrib['w'])
            ):
                if not 0 <= index < len(bones):
                    assert weight == 0, (path, index, weight)
                    skin.attrib['ix'][i] = 0
                    changed += 1
    if changed:
        # Retain the exact native attachment transforms after binary reserialisation.
        data = path.read_bytes()
        marker = b'[locator\0'
        assert data.count(marker) == 1
        locators = data[data.index(marker) :]
        pdx_data.write_meshfile(str(path), tree)
        data = path.read_bytes()
        path.write_bytes(data[: data.index(marker)] + locators)
    print(path.name, 'zero-weight indices repaired:', changed)


def hazard_entity(level):
    """Keep combat and weapon states without unsealing the respirator at idle."""
    suffix = '' if level == 0 else '_' + str(level + 1)
    lines = ['entity = {']
    if level > 1:
        lines.append('\tclone = "ADISCORD_hazard_infantry_2_entity"')
    lines.append(f'\tname = "ADISCORD_hazard_infantry{suffix}_entity"')
    if level < 2:
        pose = 'rifle' if level == 0 else 'mg'
        lines.extend((
            f'\tpdxmesh = "ADISCORD_HAZ_field_{pose}_mesh"',
            '\tdefault_state = "idle"',
        ))
        states = (
            ('attack', f'charge_{pose}', 2),
            ('attack', f'charge_{pose}_shoot', 1),
            ('defend', 'attack', 1),
            ('support_attack', 'support_attack', 1),
            ('move', 'move', 1),
            ('move', 'march_move', 1),
            ('retreat', 'retreat', 1),
            ('death', 'death', 1),
            ('idle', 'idle', 1),
            ('training', 'training', 1),
        )
        for name, animation, chance in states:
            lines.extend((
                '\tstate = {',
                f'\t\tname = "{name}"',
                f'\t\tanimation = "{animation}"',
                '\t\tanimation_blend_time = 0.3',
                '\t\tanimation_speed = 1.0',
                f'\t\tchance = {chance}',
            ))
            if name == 'attack':
                lines.extend(('\t\tlooping = no', '\t\tnext_state = "attack"'))
                if chance == 2:
                    weapon = 'rifle2' if level == 0 else 'rifle1'
                    lines.append(f'\t\tpropagate_state = {{ {weapon} = "idle" }}')
            if name == 'move':
                lines.append('\t\tevent = { sound = { soundeffect = "infantry_move_animation" } }')
            lines.append('\t}')
        lines.append('\tscale = 0.8')
    for name, node, pose in (
        ('rifle1', 'Right_Hand_node', 'right'),
        ('rifle2', 'Left_Hand_node', 'left'),
        ('rifle4', 'Root_node_2', 'right'),
        ('rifle3', 'mid_back_node', 'long_idle'),
    ):
        lines.extend((
            '\tattach = {',
            f'\t\tname = "{name}"',
            f'\t\t{node} = "ADISCORD_infantry_weapon_{level}_{pose}_entity"',
            '\t}',
        ))
    lines.append('}')
    return '\n'.join(lines)


def bindings():
    gfx_path = ROOT / 'gfx/entities/ADISCORD_country_infantry.gfx'
    asset_path = ROOT / 'gfx/entities/zz_ADISCORD_country_infantry.asset'
    strip = (
        lambda text: re.sub(
            re.escape(START) + '.*?' + re.escape(END), '', text, flags=re.S
        ).rstrip()
        + '\n'
    )
    gfx, asset = strip(gfx_path.read_text()), strip(asset_path.read_text())
    # NAM already had eight generic base entities in the shared minor-country
    # section. Remove those definitions before emitting the Arab replacement;
    # duplicate entity names make Clausewitz keep the earlier mesh silently.
    asset = re.sub(
        r'(?m)^entity = \{[^\r\n]*name = "NAM_infantry(?:_[2-8])?_entity"[^\r\n]*\}\r?\n',
        '',
        asset,
    )
    templates = {
        re.search(r'name\s*=\s*"([^"]+)"', b)[1]: b for b in blocks(gfx, 'pdxmesh')
    }
    meshes, entities = [], []
    retinue_meshes, retinue_entities = [], []
    # ARB is one shared mesh; country aliases below keep the engine's normal
    # <TAG>_infantry_entity lookup without duplicating binary assets.
    output_tags = tuple(CONFIG) + ARAB_TAGS
    for tag in output_tags:
        source_tag = 'ARB' if tag in ARAB_TAGS else tag
        armoured_guard = tag in RETINUE_STYLES or tag == 'MON'
        country_entities = retinue_entities if armoured_guard else entities
        for pose in ('rifle', 'mg'):
            source = templates[
                'STP_shabrat_' + ('mg_' if pose == 'mg' else '') + 'infantry_mesh'
            ]
            source = re.sub(
                r'\bname\s*=\s*"[^"]+"',
                f'name = "ADISCORD_{tag}_field_{pose}_mesh"',
                source,
                count=1,
            )
            source = re.sub(
                r'\bfile\s*=\s*"[^"]+"',
                f'file = "gfx/models/units/ADISCORD_regulars/{source_tag}_field.mesh"',
                source,
                count=1,
            )
            if armoured_guard:
                retinue_meshes.append('\t' + source)
            else:
                meshes.append(source)
        for level in range(8):
            suffix = '' if level == 0 else '_' + str(level + 1)
            pose = 'rifle' if level == 0 else 'mg'

            def entity(parent, name, pdxmesh=None):
                fields = [f'clone = "{parent}"', f'name = "{name}"']
                if pdxmesh:
                    fields.append(f'pdxmesh = "{pdxmesh}"')
                if tag in ('RUS', 'SHL', 'HAZ', 'MON') or tag in RETINUE_STYLES:
                    return 'entity = {\n\t' + '\n\t'.join(fields) + '\n}'
                return 'entity = { ' + ' '.join(fields) + ' }'

            if tag == 'HAZ':
                country_entities.append(hazard_entity(level))
                continue

            country_entities.append(
                entity(
                    f'STP_infantry{suffix}_entity',
                    f'{tag}_infantry{suffix}_entity',
                    f'ADISCORD_{tag}_field_{pose}_mesh',
                )
            )
            for role in ('ADISCORD_militia', 'ADISCORD_territorial', 'mountaineers'):
                country_entities.append(
                    entity(
                        f'{tag}_infantry{suffix}_entity', f'{tag}_{role}{suffix}_entity'
                    )
                )
            for cosmetic in {
                'YPR': ('YPR_VAL_administration',),
                'TFF': ('TFF_frontier_defense_confederation',),
                'RUS': ('RUS_last_empire',),
                'BJK': ('BJK_STP_revolution',),
            }.get(tag, ()):
                for role in (
                    'infantry',
                    'ADISCORD_militia',
                    'ADISCORD_territorial',
                    'mountaineers',
                ):
                    country_entities.append(
                        entity(
                            f'{tag}_{role}{suffix}_entity',
                            f'{cosmetic}_{role}{suffix}_entity',
                        )
                    )
    mesh_text = '\n'.join(meshes) + '\n\n' + '\n\n'.join(retinue_meshes)
    entity_text = '\n'.join(entities) + '\n\n' + '\n\n'.join(retinue_entities)
    return {
        gfx_path: (
            gfx + '\n' + START + 'objectTypes = {\n' + mesh_text + '\n}\n' + END
        ).encode(),
        asset_path: (asset + '\n' + START + entity_text + '\n' + END).encode(),
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

    sys.path.insert(
        0,
        str(
            Path.home()
            / 'AppData/Roaming/Blender Foundation/Blender/5.2/extensions/user_default'
        ),
    )
    from io_pdx_mesh.pdx_blender import blender_import_export as pdx

    if not hasattr(pdx, "_northern_shader_source"):
        pdx._northern_shader_source = inspect.getsource(pdx.create_shader)
    source = pdx._northern_shader_source
    for line in (
        '    new_shader.shadow_method = "CLIP"',
        '    new_shader.blend_method = "CLIP"',
    ):
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
        name = (
            'cap'
            if low > 6.8
            else (
                'skin'
                if low > 6 or len(component) < 100
                else 'legs' if high < 4 else 'coat'
            )
        )
        regions.update({k: name for k in component})
    bm = bmesh.new()
    bm.from_mesh(body.data)
    bmesh.ops.delete(
        bm, geom=[v for v in bm.verts if regions[key(v.co)] == 'cap'], context='VERTS'
    )
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
        shader.inputs['Roughness'].default_value = 0.90
        shader.inputs['Metallic'].default_value = 0
        coords = nodes.new('ShaderNodeTexCoord')
        noise = nodes.new('ShaderNodeTexNoise')
        noise.inputs['Scale'].default_value = 5.0
        noise.inputs['Detail'].default_value = 4
        links.new(coords.outputs['Object'], noise.inputs[0])
        ramp = nodes.new('ShaderNodeValToRGB')
        for element, factor in zip(ramp.color_ramp.elements, (0.48, 1.18)):
            element.color = (*[c * factor for c in color], 1)
        links.new(noise.outputs['Fac'], ramp.inputs[0])
        if preserve:
            bw = nodes.new('ShaderNodeRGBToBW')
            links.new(shader.inputs['Base Color'].links[0].from_socket, bw.inputs[0])
            intensity = nodes.new('ShaderNodeMath')
            intensity.operation = 'MULTIPLY_ADD'
            intensity.inputs[1].default_value = 0.9
            intensity.inputs[2].default_value = 0.42
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
        ao.inputs['Distance'].default_value = 0.15
        links.new(color_socket, ao.inputs['Color'])
        links.new(ao.outputs['Color'], shader.inputs['Base Color'])
        return mat

    materials = [
        cloth('Faded olive coat', (0.14, 0.16, 0.092), True),
        cloth('Brown wool sleeves', (0.105, 0.075, 0.048), True),
        cloth('Charcoal trousers', (0.057, 0.055, 0.043), True),
        cloth('Dusty boot leather', (0.092, 0.065, 0.040), True),
        cloth('Worn shoulder blanket', (0.145, 0.122, 0.074)),
        cloth('Canvas patches', (0.22, 0.18, 0.10)),
        cloth('Dark knitted cap', (0.039, 0.030, 0.021)),
    ]
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
    links.new(mask('Y', 0.28, 0.56), back.inputs[0])
    links.new(mask('Z', 3.65, 3.96), back.inputs[1])
    blanket = nodes.new('ShaderNodeMath')
    blanket.operation = 'MAXIMUM'
    links.new(back.outputs[0], blanket.inputs[0])
    links.new(mask('Z', 5.73, 6.04), blanket.inputs[1])
    blend = nodes.new('ShaderNodeMixRGB')
    links.new(blanket.outputs[0], blend.inputs[0])
    links.new(base_color, blend.inputs[1])
    blend.inputs[2].default_value = (0.115, 0.095, 0.061, 1)
    absolute = nodes.new('ShaderNodeMath')
    absolute.operation = 'ABSOLUTE'
    links.new(separate.outputs['X'], absolute.inputs[0])
    distance = nodes.new('ShaderNodeMath')
    distance.operation = 'SUBTRACT'
    distance.inputs[1].default_value = 0.31
    links.new(absolute.outputs[0], distance.inputs[0])
    absolute_distance = nodes.new('ShaderNodeMath')
    absolute_distance.operation = 'ABSOLUTE'
    links.new(distance.outputs[0], absolute_distance.inputs[0])
    stripe = nodes.new('ShaderNodeMath')
    stripe.operation = 'LESS_THAN'
    stripe.inputs[1].default_value = 0.045
    links.new(absolute_distance.outputs[0], stripe.inputs[0])
    stripe_height = nodes.new('ShaderNodeMath')
    stripe_height.operation = 'MULTIPLY'
    links.new(stripe.outputs[0], stripe_height.inputs[0])
    links.new(mask('Z', 5.3, 5.43), stripe_height.inputs[1])
    straps = nodes.new('ShaderNodeMixRGB')
    links.new(stripe_height.outputs[0], straps.inputs[0])
    links.new(blend.outputs[0], straps.inputs[1])
    straps.inputs[2].default_value = (0.034, 0.023, 0.014, 1)
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
            vertex.co.z += max(0, (2.45 - vertex.co.z) / 0.41) * (
                0.035 + 0.10 * math.sin(vertex.co.x * 13) ** 8
            )
    body.data.update()
    bake_diffuse(body, output / 'COF_body.png', 'COF_body')
    surface = BVHTree.FromPolygons(
        [v.co for v in body.data.vertices],
        [list(p.vertices) for p in body.data.polygons],
    )
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
            factors = poly_3d_calc(
                [body.data.vertices[i].co for i in face.vertices], point
            )
            weights = {}
            for i, factor in zip(face.vertices, factors):
                for group in body.data.vertices[i].groups:
                    name = body.vertex_groups[group.group].name
                    weights[name] = weights.get(name, 0) + max(0, factor) * group.weight
            strongest = sorted(weights.items(), key=lambda pair: pair[1], reverse=True)[
                :4
            ]
            total = sum(w for _, w in strongest)
            for name, weight in strongest:
                group = obj.vertex_groups.get(name) or obj.vertex_groups.new(name=name)
                group.add([vertex.index], weight / total, 'REPLACE')

    def patch(name, cx, cz, width, height):
        vertices = []
        for row in range(6):
            for col in range(6):
                x = cx + (col / 5 - 0.5) * width
                z = cz + (row / 5 - 0.5) * height + 0.025 * math.sin(col * 2.3)
                hit, normal, _, _ = surface.ray_cast(
                    Vector((x, -3, z)), Vector((0, 1, 0)), 6
                )
                assert hit is not None
                vertices.append(tuple(hit + normal * 0.018))
        obj = mesh(
            name,
            vertices,
            [
                (r * 6 + c, r * 6 + c + 1, (r + 1) * 6 + c + 1, (r + 1) * 6 + c)
                for r in range(5)
                for c in range(5)
            ],
            materials[5],
        )
        fitted_weights(obj)
        return obj

    patch('Lower coat repair', -0.38, 2.9, 0.37, 0.45)
    patch('Chest repair', 0.34, 5.12, 0.29, 0.31)
    patch('Side coat repair', -0.55, 4.12, 0.20, 0.24)

    # The crown follows the scalp rather than using a scaled helmet shell.
    vertices, faces = [], []
    rows, segments = 12, 40
    for row in range(rows):
        t = row / (rows - 1)
        for i in range(segments):
            a = math.tau * i / segments
            radius = math.cos(t * math.pi / 2)
            vertices.append(
                (
                    0.405 * radius * math.cos(a) + 0.045 * t,
                    -0.02 + 0.435 * radius * math.sin(a) + 0.025 * t,
                    6.98 + 0.42 * math.sin(t * math.pi / 2),
                )
            )
    faces = [
        (
            r * segments + i,
            r * segments + (i + 1) % segments,
            (r + 1) * segments + (i + 1) % segments,
            (r + 1) * segments + i,
        )
        for r in range(rows - 1)
        for i in range(segments)
    ]
    mesh('Soft knitted crown', vertices, faces, materials[6], 'head')
    vertices = [
        (
            0.413 * math.cos(i * math.tau / 64),
            -0.02 + 0.443 * math.sin(i * math.tau / 64),
            6.985 + row * 0.11,
        )
        for row in range(2)
        for i in range(64)
    ]
    mesh(
        'Turned cap hem',
        vertices,
        [(i, (i + 1) % 64, (i + 1) % 64 + 64, i + 64) for i in range(64)],
        materials[6],
        'head',
    )
    vertices = []
    for row in range(13):
        t = row / 12
        width = 0.40 * math.sin(math.pi * (0.06 + 0.87 * t)) ** 0.55
        for i in range(32):
            a = math.tau * i / 32
            folds = 1 + 0.045 * math.sin(7 * a + 3 * t)
            vertices.append(
                (
                    0.08 + width * math.cos(a) * folds,
                    1.05 + 0.67 * width * math.sin(a) * folds,
                    4.30 + 1.40 * t,
                )
            )
    faces = [
        (
            r * 32 + i,
            r * 32 + (i + 1) % 32,
            (r + 1) * 32 + (i + 1) % 32,
            (r + 1) * 32 + i,
        )
        for r in range(12)
        for i in range(32)
    ]
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
    solid.thickness = 0.009
    bpy.ops.object.modifier_apply(modifier=solid.name)
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.smart_project(island_margin=0.015)
    bpy.ops.object.mode_set(mode='OBJECT')
    bake_diffuse(equipment, output / 'COF_gear.png', 'COF_gear')
    for obj, part in ((body, 'body'), (equipment, 'gear')):
        (output / f'COF_field_{part}_diffuse.dds').write_bytes(
            (output / f'COF_{part}.png').read_bytes()
        )
        for kind in ('normal', 'specular'):
            (output / f'COF_field_{part}_{kind}.dds').write_bytes(
                (ROOT / f'gfx/models/units/APH_afg_militia_{kind}.dds').read_bytes()
            )
        bm = bmesh.new()
        bm.from_mesh(obj.data)
        bmesh.ops.triangulate(bm, faces=list(bm.faces))
        bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
        bmesh.ops.delete(
            bm,
            geom=[f for f in bm.faces if f.calc_area() < 1e-12],
            context='FACES_ONLY',
        )
        bm.to_mesh(obj.data)
        bm.free()
        spec = SimpleNamespace(
            shader=['PdxMeshAdvanced'],
            diff=[f'COF_field_{part}_diffuse.dds'],
            n=[f'COF_field_{part}_normal.dds'],
            spec=[f'COF_field_{part}_specular.dds'],
        )
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
    path.write_bytes(
        data[: data.index(marker)] + donor_data[donor_data.index(marker) :]
    )
    finalize_mesh(path)
    bpy.ops.wm.save_as_mainfile(filepath=str(output / 'COF.blend'))
    (output / 'build.json').write_text(
        json.dumps(
            {
                'donor_sha256': hashlib.sha256(donor_data).hexdigest(),
                'mesh_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            },
            indent=2,
        )
    )


def fitted_panel_factory(body, mesh, smooth=False):
    """Fit panels to the donor and interpolate weights across torso joints."""
    from mathutils import Vector
    from mathutils.bvhtree import BVHTree
    from mathutils.interpolate import poly_3d_calc

    surface = BVHTree.FromPolygons(
        [v.co for v in body.data.vertices],
        [list(p.vertices) for p in body.data.polygons],
    )

    def panel(name, cx, cz, width, height, material, back=False, offset=0.055, slant=0.0):
        vertices = []
        weights = []
        segments = 6
        for row in range(segments + 1):
            for col in range(segments + 1):
                x = (
                    cx + (col / segments - 0.5) * width
                    + (row / segments - 0.5) * slant
                )
                z = cz + (row / segments - 0.5) * height
                origin = Vector((x, 3 if back else -3, z))
                direction = Vector((0, -1 if back else 1, 0))
                point, normal, index, _ = surface.ray_cast(origin, direction, 6)
                assert point is not None, (name, x, z)
                vertices.append(tuple(point + normal * offset))
                face = body.data.polygons[index]
                factors = poly_3d_calc(
                    [body.data.vertices[i].co for i in face.vertices], point
                )
                if smooth:
                    normal = sum(
                        (body.data.vertices[i].normal * factor
                         for i, factor in zip(face.vertices, factors)),
                        Vector(),
                    ).normalized()
                    vertices[-1] = tuple(point + normal * offset)
                influence = {}
                for i, factor in zip(face.vertices, factors):
                    for group in body.data.vertices[i].groups:
                        bone = body.vertex_groups[group.group].name
                        influence[bone] = (
                            influence.get(bone, 0) + max(0, factor) * group.weight
                        )
                strongest = sorted(
                    influence.items(), key=lambda item: item[1], reverse=True
                )[:4]
                total = sum(w for _, w in strongest)
                weights.append([(bone, w / total) for bone, w in strongest])
        stride = segments + 1
        faces = [
            (
                r * stride + c,
                r * stride + c + 1,
                (r + 1) * stride + c + 1,
                (r + 1) * stride + c,
            )
            for r in range(segments)
            for c in range(segments)
        ]
        obj = mesh(name, vertices, faces, material)
        obj.vertex_groups.clear()
        for i, influence in enumerate(weights):
            for bone, weight in influence:
                group = obj.vertex_groups.get(bone) or obj.vertex_groups.new(name=bone)
                group.add([i], weight, 'REPLACE')
        return obj

    return panel


def imperial_carrier(body, mesh, cloth, trim, brass):
    """Fit segmented armour to the donor surface and interpolate its skin."""
    panel = fitted_panel_factory(body, mesh)
    armour = cloth('Charcoal armour', (0.072, 0.083, 0.087))
    webbing = cloth('Carrier webbing', (0.10, 0.075, 0.047))
    for back in (False, True):
        side = 'Rear' if back else 'Front'
        for x in (-0.42, 0.42):
            panel(side + ' carrier strap', x, 5.25, 0.15, 1.23, webbing, back)
        for z, width in ((5.48, 0.78), (5.12, 0.90), (4.77, 0.82)):
            panel(side + ' armour segment', 0, z, width, 0.30, armour, back, 0.09)
        panel(side + ' central brass clasp', 0, 5.48, 0.055, 0.23, brass, back, 0.12)
    panel('Burgundy breast tab', -0.53, 5.61, 0.16, 0.35, trim)
    panel('Brass breast tab edge', -0.53, 5.68, 0.12, 0.045, brass, offset=0.07)


def retinue_kit(tag, body, mesh, cloth, canvas, trim):
    """Short fitted armour leaves weapon grips and native leg motion free."""
    from infantry_polish import cloth_bag, helmet_shell

    style = RETINUE_STYLES[tag]
    panel = fitted_panel_factory(body, mesh)
    steel = cloth('Retinue dark steel', (0.16, 0.18, 0.20))
    leather = cloth('Retinue leather', (0.095, 0.045, 0.021))
    heraldry = cloth('House colours', style['coat'])
    helmet = helmet_shell(mesh, steel, trim, tag)
    # The narrow raised comb and flared brim distinguish houses at map scale.
    if style['helmet'] in ('crown', 'ridge', 'order'):
        for vertex in helmet.data.vertices:
            radius_squared = (
                (vertex.co.x / 0.428) ** 2
                + ((vertex.co.y + 0.065) / 0.530) ** 2
            )
            # The comb tapers to zero at the unchanged shell-to-rim seam.
            taper = max(0, 1 - radius_squared)
            vertex.co.z += 0.16 * taper * math.exp(-((vertex.co.x / 0.12) ** 2))
    if style['helmet'] == 'brim':
        vertices = [
            (0.46 * radius * math.cos(a), -0.065 + 0.56 * radius * math.sin(a), z)
            for radius, z in ((1, 6.96), (1.48, 6.86))
            for a in (math.tau * i / 40 for i in range(40))
        ]
        mesh(
            'Border kettle brim', vertices,
            [(i, (i + 1) % 40, (i + 1) % 40 + 40, i + 40) for i in range(40)],
            steel, 'head',
        )
    if style['helmet'] in ('nasal', 'order'):
        mesh(
            'Nasal guard',
            [
                (-0.035, -0.61, 6.98), (0.035, -0.61, 6.98),
                (0.03, -0.60, 6.59), (-0.03, -0.60, 6.59),
            ],
            [(0, 1, 2, 3)], trim, 'head',
        )
    if style['helmet'] == 'crown':
        vertices = []
        for upper in (False, True):
            for i in range(40):
                a = math.tau * i / 40
                z = 7.00 + (0.08 + 0.08 * (i % 8 == 0) if upper else 0)
                vertices.append((0.445 * math.cos(a), -0.065 + 0.54 * math.sin(a), z))
        mesh(
            'Royal helmet circlet', vertices,
            [(i, (i + 1) % 40, (i + 1) % 40 + 40, i + 40) for i in range(40)],
            trim, 'head',
        )
    for back in (False, True):
        side = 'Rear' if back else 'Front'
        for x in (-0.42, 0.42):
            panel(side + ' leather harness', x, 5.25, 0.14, 1.20, leather, back)
        if tag == 'BBV':
            for z in (4.80, 5.07, 5.34):
                panel(side + ' brigandine strip', 0, z, 0.80, 0.22, leather, back, 0.085)
        else:
            panel(side + ' retinue cuirass', 0, 5.18, 0.94, 1.0, steel, back, 0.09)
            panel(side + ' cuirass lower rim', 0, 4.71, 0.95, 0.065, trim, back, 0.11)
        if tag == 'BCM':
            panel(
                side + ' diagonal baldric', 0, 5.20, 0.18, 1.10,
                trim, back, 0.135, slant=0.65,
            )
        else:
            panel(side + ' house tabard', 0, 5.18, 0.26, 1.04, heraldry, back, 0.125)
        if tag not in ('BGT', 'BCM'):
            panel(side + ' heraldic bar', 0, 5.36, 0.21, 0.065, trim, back, 0.145)
        if tag == 'BGT':
            panel(side + ' order vertical', 0, 5.28, 0.065, 0.38, trim, back, 0.145)
            for x in (-0.10125, 0.10125):
                panel(side + ' order arm', x, 5.30, 0.1375, 0.065, trim, back, 0.145)
        if tag in ('BJK', 'BLD'):
            for x in (-0.34, 0.34):
                panel(side + ' short waist plate', x, 4.36, 0.28, 0.32, steel, back, 0.09)
    for part, kind, vertices, faces in cloth_bag(0.45, 0.30, 0.53):
        mesh(
            'Retinue cartridge pouch ' + part,
            [(x + 0.68, y + 0.37, z + 4.22) for x, y, z in vertices], faces,
            canvas if kind == 'canvas' else leather, 'Hip',
        )


def montar_guard_kit(body, mesh, cloth, canvas):
    """Articulated plates inherit body weights, leaving elbows and grips free."""
    from mathutils import Vector
    from mathutils.interpolate import poly_3d_calc
    from infantry_polish import cloth_bag, helmet_shell

    panel = fitted_panel_factory(body, mesh, smooth=True)
    steel = cloth('Montar blued steel', (0.12, 0.16, 0.17))
    brass = cloth('Montar aged brass', (0.52, 0.32, 0.10))
    leather = cloth('Montar black leather', (0.028, 0.025, 0.020))
    green = cloth('Montar enamel', (0.025, 0.12, 0.048))
    for material, surface in (
        (steel, (0.52, 0.80, 0.48)),
        (brass, (0.60, 0.90, 0.55)),
        (green, (0.42, 0.25, 0.55)),
        (leather, (0.22, 0.0, 0.18)),
        (canvas, (0.12, 0.0, 0.08)),
    ):
        material['mon_surface'] = surface

    def shoulder_plate(side, low, high, material, offset, name):
        vertices = []
        rows, columns = 8, 16
        for row in range(rows + 1):
            x = low + (high - low) * row / rows
            for column in range(columns + 1):
                angle = math.pi * column / columns
                vertices.append((
                    side * x,
                    0.02 - (0.44 + offset) * math.cos(angle),
                    5.59 - 0.60 * (x - 0.65) + (0.40 + offset) * math.sin(angle),
                ))
        stride = columns + 1
        plate = mesh(
            name, vertices,
            [(r * stride + c, r * stride + c + 1,
              (r + 1) * stride + c + 1, (r + 1) * stride + c)
             for r in range(rows) for c in range(columns)], material,
        )
        plate.vertex_groups.clear()
        for index, vertex in enumerate(vertices):
            angle = math.pi * (index % stride) / columns
            x = abs(vertex[0])
            center = Vector((side * x, 0.02, 5.59 - 0.60 * (x - 0.65)))
            radial = Vector((0, -math.cos(angle), math.sin(angle)))
            found, point, normal, face_index = body.ray_cast(center + radial * 3, -radial)
            assert found
            face = body.data.polygons[face_index]
            factors = poly_3d_calc([body.data.vertices[i].co for i in face.vertices], point)
            normal = sum(
                (body.data.vertices[i].normal * factor
                 for i, factor in zip(face.vertices, factors)), Vector(),
            ).normalized()
            plate.data.vertices[index].co = point + normal * offset
            weights = {}
            for source, factor in zip(face.vertices, factors):
                for influence in body.data.vertices[source].groups:
                    bone = body.vertex_groups[influence.group].name
                    weights[bone] = weights.get(bone, 0) + max(0, factor) * influence.weight
            strongest = sorted(weights.items(), key=lambda item: item[1], reverse=True)[:4]
            total = sum(weight for _, weight in strongest)
            for bone, weight in strongest:
                group = plate.vertex_groups.get(bone) or plate.vertex_groups.new(name=bone)
                group.add([index], weight / total, 'REPLACE')

    helmet_shell(mesh, steel, brass, 'MON')
    # A low longitudinal comb keeps the silhouette distinct without a tall plume.
    vertices = []
    for x in (-0.035, 0.035):
        for i in range(13):
            angle = -1.12 + 2.24 * i / 12
            vertices.append((x, -0.065 + 0.53 * math.sin(angle), 6.88 + 0.49 * math.cos(angle)))
    mesh('Imperial helmet comb', vertices, [(i, i + 1, i + 14, i + 13) for i in range(12)], brass, 'head')
    for side in (-1, 1):
        shoulder_plate(side, 0.53, 1.38, steel, 0.09, 'Guard shoulder shell')
        shoulder_plate(side, 1.30, 1.38, brass, 0.105, 'Guard shoulder rim')
        cheek_vertices = []
        for row in range(5):
            t = row / 4
            for column in range(17):
                angle = -0.85 + 1.50 * column / 16
                front = max(0, -math.sin(angle))
                rear = max(0, math.sin(angle))
                lower = 6.83 + 0.16 * front**3 - 0.055 * rear + 0.09 * abs(math.cos(angle))**8
                cheek_vertices.append((
                    side * 0.428 * (1 - 0.04 * t) * math.cos(angle),
                    -0.065 + 0.530 * (1 - 0.02 * t) * math.sin(angle),
                    lower + 0.025 - t * (0.40 + 0.05 * front),
                ))
        mesh(
            'Helmet cheek guard',
            cheek_vertices,
            [(r * 17 + c, r * 17 + c + 1, (r + 1) * 17 + c + 1, (r + 1) * 17 + c)
             for r in range(4) for c in range(16)], steel, 'head',
        )
    for back in (False, True):
        side = 'Rear' if back else 'Front'
        panel(side + ' guard cuirass', 0, 5.24, 1.12, 1.06, steel, back, 0.12)
        panel(side + ' cuirass rim', 0, 4.74, 1.13, 0.07, brass, back, 0.15)
        for z, width in ((4.61, 1.04), (4.43, 0.99)):
            panel(side + ' articulated waist', 0, z, width, 0.14, steel, back, 0.12)
        for x in (-0.36, 0.36):
            panel(side + ' short hip plate', x, 4.16, 0.30, 0.29, steel, back, 0.10)
    panel('Emerald breast shield', 0, 5.39, 0.30, 0.46, green, offset=0.16)
    panel('Imperial crown base', 0, 5.27, 0.22, 0.055, brass, offset=0.18)
    for x, height in ((-0.082, 0.13), (0, 0.19), (0.082, 0.13)):
        panel('Imperial crown point', x, 5.32 + height / 2, 0.05, height, brass, offset=0.18)
    for x in (-0.65, 0.65):
        for part, kind, vertices, faces in cloth_bag(0.31, 0.25, 0.40):
            mesh(
                'Guard ammunition pouch ' + part,
                [(vx + x, vy + 0.31, vz + 4.14) for vx, vy, vz in vertices],
                faces, canvas if kind == 'canvas' else leather, 'Hip',
            )


def bake_montar_surface(obj, output):
    """Bake specular strength, metalness and gloss separately from lit colour."""
    import bpy

    original = list(obj.data.materials)
    image = bpy.data.images.new('MON_surface', 1024, 1024, alpha=False)
    image.colorspace_settings.name = 'Non-Color'
    for index, source in enumerate(original):
        material = bpy.data.materials.new(source.name + ' surface bake')
        material.use_nodes = True
        nodes = material.node_tree.nodes
        nodes.clear()
        emission = nodes.new('ShaderNodeEmission')
        emission.inputs['Color'].default_value = (*source['mon_surface'], 1)
        target = nodes.new('ShaderNodeOutputMaterial')
        material.node_tree.links.new(emission.outputs[0], target.inputs['Surface'])
        texture = nodes.new('ShaderNodeTexImage')
        texture.image = image
        nodes.active = texture
        obj.data.materials[index] = material
    bpy.ops.object.bake(type='EMIT')
    image.filepath_raw = str(output / 'MON_surface.png')
    image.file_format = 'PNG'
    image.save()
    for index, material in enumerate(original):
        obj.data.materials[index] = material


def hazard_kit(body, mesh, cloth, suit, canvas, rubber):
    """Rigid mask follows the head; the soft collar follows the upper torso."""
    import bpy
    from infantry_polish import cloth_bag

    metal = cloth('Blackened respirator fittings', (0.038, 0.048, 0.046))
    glass = cloth('Smoked optical glass', (0.025, 0.065, 0.074))
    highlight = cloth('Glass edge reflection', (0.11, 0.19, 0.20))
    warning = cloth('Identification yellow', (0.63, 0.45, 0.075))

    def shell(name, center, radii, material, bone='head', rings=12, segments=24):
        vertices = []
        for row in range(rings + 1):
            latitude = math.pi * row / rings
            for column in range(segments):
                angle = math.tau * column / segments
                vertices.append((
                    center[0] + radii[0] * math.sin(latitude) * math.cos(angle),
                    center[1] + radii[1] * math.sin(latitude) * math.sin(angle),
                    center[2] + radii[2] * math.cos(latitude),
                ))
        faces = [
            (row * segments + i, row * segments + (i + 1) % segments,
             (row + 1) * segments + (i + 1) % segments, (row + 1) * segments + i)
            for row in range(rings) for i in range(segments)
        ]
        return mesh(name, vertices, faces, material, bone)

    def cylinder(name, center, radius, depth, material, bone='head', axis='y', tilt=0, segments=24):
        vertices = []
        for distance, scale in ((-depth / 2, 0.88), (-depth * 0.38, 1),
                                (depth * 0.38, 1), (depth / 2, 0.88)):
            for i in range(segments):
                angle = math.tau * i / segments
                a, b = radius * scale * math.cos(angle), radius * scale * math.sin(angle)
                point = (a, distance, b) if axis == 'y' else (a, b, distance)
                if tilt:
                    x, y, z = point
                    point = (x * math.cos(tilt) - y * math.sin(tilt),
                             x * math.sin(tilt) + y * math.cos(tilt), z)
                vertices.append(tuple(c + v for c, v in zip(center, point)))
        faces = [
            (row * segments + i, row * segments + (i + 1) % segments,
             (row + 1) * segments + (i + 1) % segments, (row + 1) * segments + i)
            for row in range(3) for i in range(segments)
        ]
        faces.extend((tuple(reversed(range(segments))), tuple(range(3 * segments, 4 * segments))))
        return mesh(name, vertices, faces, material, bone)

    def eyepiece(side):
        outline = [
            (0.062, 6.85), (0.125, 6.94), (0.30, 6.94), (0.385, 6.88),
            (0.41, 6.70), (0.365, 6.56), (0.25, 6.59), (0.12, 6.72),
        ]
        for _ in range(2):
            rounded = []
            for a, b in zip(outline, outline[1:] + outline[:1]):
                rounded.extend((
                    tuple(0.75 * x + 0.25 * y for x, y in zip(a, b)),
                    tuple(0.25 * x + 0.75 * y for x, y in zip(a, b)),
                ))
            outline = rounded
        cx = sum(x for x, z in outline) / len(outline)
        cz = sum(z for x, z in outline) / len(outline)
        lens_scale = 0.88
        outline = [
            (cx + (x - cx) * lens_scale, cz + (z - cz) * lens_scale)
            for x, z in outline
        ]

        def surface(name, levels, material):
            vertices = []
            for scale, depth in levels:
                for x, z in outline:
                    px = cx + (x - cx) * scale
                    vertices.append((side * px, depth + 0.42 * (px - cx), cz + (z - cz) * scale))
            count = len(outline)
            faces = [
                (row * count + i, row * count + (i + 1) % count,
                 (row + 1) * count + (i + 1) % count, (row + 1) * count + i)
                for row in range(len(levels) - 1) for i in range(count)
            ]
            if levels[-1][0] < 0.1:
                faces.append(tuple(range((len(levels) - 1) * count, len(vertices))))
            mesh(name, vertices, faces, material, 'head')

        surface('Contoured rubber eye seal', ((1.14, -0.675), (1.10, -0.725), (0.99, -0.754)), rubber)
        surface('Eyepiece retaining ring', ((1.025, -0.748), (0.98, -0.769), (0.90, -0.773)), metal)
        surface('Convex smoked eyepiece', ((0.905, -0.769), (0.67, -0.790), (0.05, -0.807)), glass)
        # A narrow baked reflection remains legible in the native diffuse atlas.
        vertices = [
            (side * (cx + (x - cx) * lens_scale),
             -0.779 + 0.42 * (x - cx) * lens_scale, cz + (z - cz) * lens_scale)
            for x, z in ((0.15, 6.893), (0.29, 6.898), (0.30, 6.886), (0.16, 6.882))
        ]
        mesh('Lens upper reflection', vertices, [(0, 1, 2, 3)], highlight, 'head')

    hood_rings = (
        (6.12, 0.35, 0.39), (6.30, 0.41, 0.46), (6.55, 0.455, 0.515),
        (6.79, 0.45, 0.515), (6.98, 0.405, 0.455),
        (7.08, 0.32, 0.365), (7.13, 0.19, 0.23), (7.14, 0.02, 0.03),
    )
    vertices = []
    segments = 40
    for row, (height, width, depth) in enumerate(hood_rings):
        for i in range(segments):
            angle = math.tau * i / segments
            fold = 0.014 * math.cos(6 * angle + row * 0.45)
            vertices.append((
                (width + fold) * math.cos(angle),
                -0.045 + (depth + fold) * math.sin(angle),
                height + 0.006 * math.sin(3 * angle),
            ))
    faces = [
        (row * segments + i, row * segments + (i + 1) % segments,
         (row + 1) * segments + (i + 1) % segments, (row + 1) * segments + i)
        for row in range(len(hood_rings) - 1) for i in range(segments)
    ]
    faces.append(tuple(range((len(hood_rings) - 1) * segments, len(vertices))))
    mesh('Fitted protective hood', vertices, faces, suit, 'head')
    shell('Soft protective collar', (0, -0.045, 6.05), (0.47, 0.44, 0.30), suit, 'back_mid')
    vertices = []
    for width, height, depth in ((0.455, 0.46, -0.43), (0.44, 0.43, -0.58), (0.405, 0.405, -0.65)):
        for i in range(segments):
            angle = math.tau * i / segments
            vertices.append((width * math.sin(angle), depth + 0.14 * abs(math.sin(angle)),
                             6.63 + height * math.cos(angle)))
    faces = [
        (row * segments + i, row * segments + (i + 1) % segments,
         (row + 1) * segments + (i + 1) % segments, (row + 1) * segments + i)
        for row in range(2) for i in range(segments)
    ]
    mesh('Hood face opening welt', vertices, faces, suit, 'head')
    mask_objects = set(bpy.context.scene.objects)
    shell('Full face respirator', (0, -0.48, 6.62), (0.39, 0.28, 0.45), rubber)
    shell('Moulded nose bridge', (0, -0.688, 6.60), (0.115, 0.16, 0.205), rubber, rings=10, segments=24)
    for side in (-1, 1):
        eyepiece(side)
        tilt = side * 0.46

        def filter_part(name, distance, radius, depth, material):
            center = (side * 0.36 - distance * math.sin(tilt),
                      -0.56 + distance * math.cos(tilt), 6.36)
            cylinder(name, center, radius, depth, material, tilt=tilt)

        filter_part('Filter threaded coupling', 0.05, 0.128, 0.12, rubber)
        filter_part('Black side filter canister', -0.06, 0.198, 0.22, metal)
        for distance in (-0.15, -0.10, 0.025):
            filter_part('Canister reinforcing bead', distance, 0.202, 0.025, rubber)
        filter_part('Recessed filter intake', -0.177, 0.108, 0.025, rubber)
        filter_part('Intake central fitting', -0.196, 0.048, 0.015, metal)
        for i in range(8):
            angle = math.tau * i / 8
            vertices = []
            for radius, offset in ((0.119, -0.03), (0.182, -0.03), (0.182, 0.03), (0.119, 0.03)):
                x = radius * math.cos(angle + offset)
                z = radius * math.sin(angle + offset)
                vertices.append((side * 0.36 + x * math.cos(tilt) + 0.18 * math.sin(tilt),
                                 -0.56 + x * math.sin(tilt) - 0.18 * math.cos(tilt), 6.36 + z))
            mesh('Filter radial reinforcement', vertices, [(0, 1, 2, 3)], rubber, 'head')
    cylinder('Exhalation valve housing', (0, -0.806, 6.38), 0.159, 0.095, metal)
    cylinder('Recessed valve grille', (0, -0.858, 6.38), 0.130, 0.018, rubber)
    cylinder('Valve diaphragm cap', (0, -0.873, 6.38), 0.049, 0.025, metal)
    for i in range(12):
        angle = math.tau * i / 12
        cylinder('Valve intake port', (0.098 * math.cos(angle), -0.874, 6.38 + 0.098 * math.sin(angle)),
                 0.010, 0.009, metal, segments=8)
    for obj in set(bpy.context.scene.objects) - mask_objects:
        for vertex in obj.data.vertices:
            vertex.co.y += 0.085

    for part, kind, vertices, faces in cloth_bag(0.92, 0.38, 1.12, (-0.23, 0.23)):
        mesh('Filter reserve pack ' + part,
             [(x, y + 0.78, z + 5.10) for x, y, z in vertices],
             faces, canvas if kind == 'canvas' else rubber)
    for side in (-1, 1):
        cylinder('Decontamination flask', (side * 0.59, 0.73, 4.97),
                 0.14, 0.68, metal, 'back_mid', axis='z')
    panel = fitted_panel_factory(body, mesh)
    panel('Sealed chest pocket', -0.25, 5.34, 0.34, 0.50, canvas)
    panel('Personal dosimeter', 0.25, 5.50, 0.22, 0.30, rubber, offset=0.09)
    panel('Dosimeter display', 0.25, 5.56, 0.13, 0.07, glass, offset=0.105)
    panel('Hazard identification strip', -0.25, 5.45, 0.24, 0.06, warning, offset=0.085)
    cylinder('Hazard badge', (0, 0.99, 5.38), 0.20, 0.02, warning, 'back_mid')
    for angle in (0, math.tau / 3, 2 * math.tau / 3):
        vertices = []
        for radius in (0.075, 0.17):
            for step in range(9):
                a = angle + math.pi / 3 * step / 8
                vertices.append((radius * math.cos(a), 1.008, 5.38 + radius * math.sin(a)))
        mesh('Hazard badge trefoil', vertices,
             [(i, i + 1, i + 10, i + 9) for i in range(8)], rubber)


def build_hazard_sentinel(output, pdx):
    """Fit the supplied A-pose to the native rig and retain its UV textures."""
    import bpy
    import bmesh
    from mathutils import Vector
    from mathutils.kdtree import KDTree
    from mathutils.bvhtree import BVHTree
    from types import SimpleNamespace
    from infantry_polish import bake_diffuse

    source = Path(__file__).with_name('HAZ_sentinel_source.blend')
    bpy.ops.wm.open_mainfile(filepath=str(source), use_scripts=False)
    body = next(obj for obj in bpy.context.scene.objects if obj.type == 'MESH')
    body.name = 'HAZ_body'
    material = body.data.materials[0]
    shader = material.node_tree.nodes.get('Principled BSDF')
    texture = shader.inputs['Base Color'].links[0].from_node.image
    texture.filepath_raw = str(output / 'HAZ_body.png')
    texture.file_format = 'PNG'
    texture.save()
    normal = shader.inputs['Normal'].links[0].from_node.inputs['Color'].links[0].from_node.image
    normal.filepath_raw = str(output / 'HAZ_body_normal.png')
    normal.file_format = 'PNG'
    normal.save()
    low = min(vertex.co.z for vertex in body.data.vertices)
    height = max(vertex.co.z for vertex in body.data.vertices) - low
    scale = 7.5 / height
    for vertex in body.data.vertices:
        vertex.co = Vector((vertex.co.x * scale, vertex.co.y * scale + 0.35,
                            (vertex.co.z - low) * scale))
        # Raise the outer sleeve to the native grip without moving the torso.
        vertex.co.z += 0.38 * min(1.0, max(0.0, (abs(vertex.co.x) - 1.0) / 1.5))
    body.data.update()
    pdx.import_meshfile(str(CONFIG['HAZ']), imp_locs=False)
    donor = max((obj for obj in bpy.context.scene.objects
                 if obj.type == 'MESH' and obj != body), key=lambda obj: len(obj.data.polygons))
    rig = next(modifier.object for modifier in donor.modifiers if modifier.type == 'ARMATURE')
    tree = KDTree(len(donor.data.vertices))
    for vertex in donor.data.vertices:
        tree.insert(vertex.co, vertex.index)
    tree.balance()
    for bone in rig.data.bones:
        body.vertex_groups.new(name=bone.name)
    for vertex in body.data.vertices:
        weights = {}
        if vertex.co.y > 0.62 and vertex.co.z > 4.15 and abs(vertex.co.x) < 1.0:
            # The breathing apparatus is rigid; arm weights must not bend its tank.
            weights['back_mid'] = 1.0
        elif vertex.co.z > 6.30:
            weights['head'] = 1.0
        else:
            for _, index, distance in tree.find_n(vertex.co, 4):
                influence = 1.0 / max(distance, 0.025) ** 2
                for group in donor.data.vertices[index].groups:
                    name = donor.vertex_groups[group.group].name
                    weights[name] = weights.get(name, 0.0) + influence * group.weight
        weights = dict(sorted(weights.items(), key=lambda item: item[1], reverse=True)[:4])
        total = sum(weights.values())
        assert total > 0
        for name, weight in weights.items():
            body.vertex_groups[name].add([vertex.index], weight / total, 'REPLACE')
    body.modifiers.new('Native infantry rig', 'ARMATURE').object = rig
    for obj in list(bpy.context.scene.objects):
        if obj not in (body, rig):
            bpy.data.objects.remove(obj, do_unlink=True)

    def face_material(name, color, roughness):
        mat = bpy.data.materials.new(name)
        mat.use_nodes = True
        node = mat.node_tree.nodes.get('Principled BSDF')
        node.inputs['Base Color'].default_value = (*color, 1)
        node.inputs['Roughness'].default_value = roughness
        return mat

    rubber = face_material('Respirator charcoal seals', (0.025, 0.030, 0.027), 0.8)
    glass = face_material('Respirator dark optical glass', (0.014, 0.036, 0.042), 0.28)
    bm = bmesh.new()
    bm.from_mesh(body.data)
    surface = BVHTree.FromBMesh(bm)
    parts = []
    for side in (-1, 1):
        x, z = side * 0.215, 6.78
        hit, _, _, _ = surface.ray_cast(Vector((x, -4, z)), Vector((0, 1, 0)))
        assert hit is not None
        for name, radius, depth, mat in (
            ('Eyepiece seal', 0.172, 0.045, rubber),
            ('Eyepiece glass', 0.139, 0.062, glass),
        ):
            bpy.ops.mesh.primitive_uv_sphere_add(segments=24, ring_count=12,
                                                location=(x, hit.y - 0.015, z))
            obj = bpy.context.object
            obj.name = name
            obj.scale = (radius, depth, radius * 1.08)
            bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
            obj.data.materials.append(mat)
            obj.vertex_groups.new(name='head').add(list(range(len(obj.data.vertices))), 1, 'REPLACE')
            obj.modifiers.new('Native infantry rig', 'ARMATURE').object = rig
            parts.append(obj)
    bm.free()
    bpy.ops.object.select_all(action='DESELECT')
    for obj in parts:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = parts[0]
    bpy.ops.object.join()
    equipment = bpy.context.object
    equipment.name = 'HAZ_gear'
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.smart_project(island_margin=0.025)
    bpy.ops.object.mode_set(mode='OBJECT')
    bake_diffuse(equipment, output / 'HAZ_gear.png', 'HAZ_gear', size=512)
    source_materials = {obj: list(obj.data.materials) for obj in (body, equipment)}
    source_indices = {}
    for obj, part in ((body, 'body'), (equipment, 'gear')):
        for face in obj.data.polygons:
            face.use_smooth = True
        bm = bmesh.new()
        bm.from_mesh(obj.data)
        bmesh.ops.triangulate(bm, faces=list(bm.faces))
        bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
        bm.to_mesh(obj.data)
        bm.free()
        source_indices[obj] = [face.material_index for face in obj.data.polygons]
        (output / f'HAZ_field_{part}_diffuse.dds').write_bytes((output / f'HAZ_{part}.png').read_bytes())
        for kind in ('normal', 'specular'):
            (output / f'HAZ_field_{part}_{kind}.dds').write_bytes(NORMALS['HAZ'].read_bytes())
        spec = SimpleNamespace(shader=['PdxMeshAdvanced'], diff=[f'HAZ_field_{part}_diffuse.dds'],
                               n=[f'HAZ_field_{part}_normal.dds'], spec=[f'HAZ_field_{part}_specular.dds'])
        obj.data.materials.clear()
        obj.data.materials.append(pdx.create_shader(spec, 'HAZ_' + part, str(output)))
        for face in obj.data.polygons:
            face.material_index = 0
    bpy.ops.object.select_all(action='DESELECT')
    body.select_set(True)
    equipment.select_set(True)
    path = output / 'HAZ_field.mesh'
    pdx.export_meshfile(str(path), exp_selected=True, exp_locs=False)
    data, donor_data = path.read_bytes(), CONFIG['HAZ'].read_bytes()
    marker = b'[locator\0'
    assert data.count(marker) == donor_data.count(marker) == 1
    path.write_bytes(data[:data.index(marker)] + donor_data[donor_data.index(marker):])
    finalize_mesh(path)
    for obj in (body, equipment):
        obj.data.materials.clear()
        for mat in source_materials[obj]:
            obj.data.materials.append(mat)
        for face, index in zip(obj.data.polygons, source_indices[obj], strict=True):
            face.material_index = index
    bpy.ops.file.pack_all()
    bpy.ops.wm.save_as_mainfile(filepath=str(output / 'HAZ.blend'))


def build_field(tag, output):
    """Keep the donor garment topology and skin while replacing its field kit."""
    import bpy
    import bmesh
    import inspect
    from types import SimpleNamespace
    from mathutils import Vector

    sys.path.insert(0, str(Path(__file__).parent))
    from infantry_polish import bake_diffuse, cloth_bag, fitted_head_cloth

    sys.path.insert(
        0,
        str(
            Path.home()
            / 'AppData/Roaming/Blender Foundation/Blender/5.2/extensions/user_default'
        ),
    )
    from io_pdx_mesh.pdx_blender import blender_import_export as pdx

    if not hasattr(pdx, "_northern_shader_source"):
        pdx._northern_shader_source = inspect.getsource(pdx.create_shader)
    source = pdx._northern_shader_source
    for line in (
        '    new_shader.shadow_method = "CLIP"',
        '    new_shader.blend_method = "CLIP"',
    ):
        source = source.replace(line, '')
    exec(compile(source, '<Blender material compatibility>', 'exec'), pdx.__dict__)
    output.mkdir(parents=True, exist_ok=True)
    if tag == 'HAZ':
        build_hazard_sentinel(output, pdx)
        return
    bpy.ops.wm.read_factory_settings(use_empty=True)
    donor = CONFIG[tag]
    pdx.import_meshfile(str(donor), imp_locs=False)
    scene = bpy.context.scene
    body = max(
        (o for o in scene.objects if o.type == 'MESH'),
        key=lambda o: len(o.data.polygons),
    )
    rig = next(m.object for m in body.modifiers if m.type == 'ARMATURE')
    for obj in list(scene.objects):
        if obj not in (body, rig):
            bpy.data.objects.remove(obj, do_unlink=True)
    body.name = tag + '_body'
    # Whole islands keep native leather pouches separate from cloth tinting.
    small_kit = set()
    native_head = set()
    if tag in ('TFF', 'YPR', 'RUS', 'NAM', 'HAZ', 'MON') or tag in RETINUE_STYLES:
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
            if tag == 'MON' and min(k[2] for k in component) > 5.8 and max(abs(k[0]) for k in component) < 0.5:
                native_head.update(component)
            if (
                min(k[2] for k in component) > 3.8
                and max(k[2] for k in component) < 5
                and len(component) < 100
            ):
                small_kit.update(component)
        if tag in ('TFF', 'RUS', 'NAM', 'HAZ', 'MON') or tag in RETINUE_STYLES:
            assert cap
            bm = bmesh.new()
            bm.from_mesh(body.data)
            bmesh.ops.delete(
                bm,
                geom=[v for v in bm.verts if tuple(round(x, 4) for x in v.co) in cap],
                context='VERTS',
            )
            bm.to_mesh(body.data)
            bm.free()
    if tag == 'HAZ':
        for vertex in body.data.vertices:
            if vertex.co.z > 6.7:
                vertex.co.z = 6.7 + (vertex.co.z - 6.7) * 0.65
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
        shader.inputs['Roughness'].default_value = 0.85
        shader.inputs['Metallic'].default_value = 0
        coordinates = nodes.new('ShaderNodeTexCoord')
        noise = nodes.new('ShaderNodeTexNoise')
        noise.inputs['Scale'].default_value = 13
        noise.inputs['Detail'].default_value = 3
        links.new(coordinates.outputs['Object'], noise.inputs[0])
        ramp = nodes.new('ShaderNodeValToRGB')
        for element, factor in zip(ramp.color_ramp.elements, (0.72, 1.16)):
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
            outside.inputs[1].default_value = 0.55
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
            clean.inputs[2].default_value = (0.50, 0.50, 0.50, 1)
            intensity = nodes.new('ShaderNodeMath')
            intensity.operation = 'MULTIPLY_ADD'
            intensity.inputs[1].default_value = 0.90
            intensity.inputs[2].default_value = 0.36
            links.new(clean.outputs[0], intensity.inputs[0])
            multiply = nodes.new('ShaderNodeMixRGB')
            multiply.blend_type = 'MULTIPLY'
            multiply.inputs[0].default_value = 1
            links.new(ramp.outputs[0], multiply.inputs[1])
            links.new(intensity.outputs[0], multiply.inputs[2])
            color_socket = multiply.outputs[0]
        ao = nodes.new('ShaderNodeAmbientOcclusion')
        ao.inputs['Distance'].default_value = 0.12
        links.new(color_socket, ao.inputs['Color'])
        links.new(ao.outputs['Color'], shader.inputs['Base Color'])
        return material

    olive = (0.155, 0.178, 0.105)
    if tag in RETINUE_STYLES:
        jacket_color = RETINUE_STYLES[tag]['coat']
        trouser_color = tuple(c * 0.45 for c in jacket_color)
        canvas_color = (0.16, 0.10, 0.045)
        wool_color = (0.04, 0.045, 0.052)
        scarf_color = RETINUE_STYLES[tag]['trim']
    elif tag in ('SHL', 'ARB'):
        jacket_color = (0.36, 0.22, 0.09)
        trouser_color = (0.22, 0.19, 0.12)
        canvas_color = (0.48, 0.33, 0.16)
        wool_color = (0.08, 0.055, 0.035)
        scarf_color = (0.68, 0.53, 0.30)
    elif tag == 'MON':
        jacket_color = (0.040, 0.115, 0.053)
        trouser_color = (0.024, 0.042, 0.030)
        canvas_color = (0.11, 0.075, 0.035)
        wool_color = (0.025, 0.027, 0.024)
        scarf_color = (0.52, 0.32, 0.10)
    elif tag == 'RUS':
        jacket_color = (0.046, 0.062, 0.072)
        trouser_color = (0.035, 0.040, 0.048)
        canvas_color = (0.11, 0.075, 0.045)
        wool_color = (0.026, 0.033, 0.042)
        scarf_color = (0.24, 0.022, 0.035)
    elif tag == 'HAZ':
        jacket_color = (0.14, 0.20, 0.105)
        trouser_color = (0.12, 0.17, 0.085)
        canvas_color = (0.065, 0.085, 0.060)
        wool_color = (0.017, 0.022, 0.020)
        scarf_color = (0.18, 0.23, 0.115)
    elif tag == 'NAM':
        jacket_color = (0.055, 0.095, 0.105)
        trouser_color = (0.035, 0.048, 0.052)
        canvas_color = (0.12, 0.075, 0.035)
        wool_color = (0.025, 0.045, 0.050)
        scarf_color = (0.62, 0.38, 0.075)
    else:
        jacket_color = olive if tag == 'YPR' else (0.16, 0.105, 0.055)
        trouser_color = (0.12, 0.14, 0.085) if tag == 'YPR' else (0.055, 0.068, 0.065)
        canvas_color = (0.14, 0.15, 0.09) if tag == 'YPR' else (0.13, 0.10, 0.067)
        wool_color = (0.065, 0.083, 0.070)
        scarf_color = (0.20, 0.215, 0.20)
    jacket = cloth('Field jacket', jacket_color, True)
    trousers = cloth('Field trousers', trouser_color, True)
    canvas = cloth('Field canvas', canvas_color)
    wool = cloth('Wool and bindings', wool_color)
    scarf = cloth('Frontier wool scarf', scarf_color)
    for mat in (jacket, trousers, canvas):
        body.data.materials.append(mat)
    if tag == 'HAZ':
        body.data.materials.append(wool)
    for face in body.data.polygons:
        x, y, z = face.center
        # Bare head, hands and original boot leather keep their authored atlas.
        skin = (z > 6.13 and abs(x) < 0.44) or (abs(x) > 2.30 and 3.9 < z < 4.85)
        if tag == 'MON':
            uv = sum(
                (body.data.uv_layers.active.data[i].uv for i in face.loop_indices),
                Vector((0, 0)),
            ) / len(face.loop_indices)
            vertex_key = tuple(round(v, 4) for v in body.data.vertices[face.vertices[0]].co)
            skin = vertex_key in native_head or (abs(x) > 2.30 and uv.x > 0.58 and uv.y > 0.70)
        if tag == 'HAZ' and skin:
            face.material_index = 4
        elif tag == 'YPR' and z > 6.80:
            face.material_index = 3
        elif (
            skin
            or z < 1.15
            or tuple(round(v, 4) for v in body.data.vertices[face.vertices[0]].co)
            in small_kit
        ):
            face.material_index = 0
        else:
            # The trouser island includes the crotch above the jacket hem. A
            # height cutoff splits its triangles and leaves a jagged colour seam.
            uv = sum(
                (body.data.uv_layers.active.data[i].uv for i in face.loop_indices),
                Vector((0, 0)),
            ) / len(face.loop_indices)
            pants = (
                uv.x < 0.44 and uv.y < 0.45
                if tag in ('TFF', 'RUS', 'NAM', 'HAZ', 'MON') or tag in RETINUE_STYLES
                else z < 3.55
            )
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

    if tag == 'MON':
        montar_guard_kit(body, mesh, cloth, canvas)
    elif tag == 'HAZ':
        hazard_kit(body, mesh, cloth, jacket, canvas, wool)
    elif tag in RETINUE_STYLES:
        retinue_kit(tag, body, mesh, cloth, canvas, scarf)
    elif tag == 'YPR':
        for part, kind, vertices, faces in cloth_bag(0.95, 0.34, 0.92, (-0.22, 0.22)):
            mesh(
                'Field pack ' + part,
                [(x, y + 0.83, z + 5.07) for x, y, z in vertices],
                faces,
                canvas if kind == 'canvas' else wool,
            )
    else:
        vertices = []
        for row in range(12):
            t = row / 11
            for i in range(40):
                a = math.tau * i / 40
                if tag == 'RUS':
                    radius = 1.07 * math.cos(t * math.pi / 2)
                    height = 7.04 + 0.34 * math.sin(t * math.pi / 2) ** 0.30
                elif tag == 'NAM':
                    radius = 1.02 * math.cos(t * math.pi / 2)
                    height = 6.98 + 0.42 * math.sin(t * math.pi / 2) ** 0.38
                else:
                    radius = math.cos(t * math.pi / 2)
                    height = 6.91 + 0.38 * math.sin(t * math.pi / 2)
                vertices.append(
                    (
                        0.43 * radius * math.cos(a) + 0.025 * t,
                        -0.07 + 0.49 * radius * math.sin(a),
                        height,
                    )
                )
        mesh(
            'Knitted field cap',
            vertices,
            [
                (
                    r * 40 + i,
                    r * 40 + (i + 1) % 40,
                    (r + 1) * 40 + (i + 1) % 40,
                    (r + 1) * 40 + i,
                )
                for r in range(11)
                for i in range(40)
            ],
            wool,
            'head',
        )
        vertices = [
            (
                0.44 * math.cos(i * math.tau / 40),
                -0.07 + 0.50 * math.sin(i * math.tau / 40),
                6.91 + r * 0.12,
            )
            for r in range(2)
            for i in range(40)
        ]
        mesh(
            'Cap fold',
            vertices,
            [(i, (i + 1) % 40, (i + 1) % 40 + 40, i + 40) for i in range(40)],
            wool,
            'head',
        )
        if tag in ('RUS', 'NAM'):
            brass = cloth('Dull brass insignia', (0.48, 0.29, 0.095))
            brim_vertices = []
            for outer in (False, True):
                for i in range(21):
                    a = math.pi + math.pi * i / 20
                    brim_vertices.append(
                        (
                            0.43 * math.cos(a),
                            -0.07 + (0.69 if outer else 0.42) * math.sin(a),
                            6.98 - (0.075 if outer else 0) * abs(math.sin(a)),
                        )
                    )
            mesh(
                'Imperial cap visor',
                brim_vertices,
                [(i, i + 1, i + 22, i + 21) for i in range(20)],
                wool,
                'head',
            )
            band_vertices = []
            for z in (6.99, 7.10):
                for i in range(40):
                    a = math.tau * i / 40
                    band_vertices.append(
                        (0.47 * math.cos(a), -0.07 + 0.53 * math.sin(a), z)
                    )
            mesh(
                'Imperial cap band',
                band_vertices,
                [(i, (i + 1) % 40, (i + 1) % 40 + 40, i + 40) for i in range(40)],
                scarf,
                'head',
            )
            badge_vertices = [
                (0, -0.577, 7.00),
                (0.075, -0.577, 7.09),
                (0, -0.577, 7.20),
                (-0.075, -0.577, 7.09),
            ]
            mesh('Imperial cap badge', badge_vertices, [(0, 1, 2, 3)], brass, 'head')
            imperial_carrier(body, mesh, cloth, scarf, brass)
        # A compact neck wrap leaves both hands and the rifle stock unobstructed.
        vertices = []
        for row in range(6):
            t = row / 5
            for i in range(40):
                a = math.tau * i / 40
                radius = 0.37 + 0.045 * math.sin(t * math.pi)
                vertices.append(
                    (
                        radius * math.cos(a),
                        -0.08 + (radius + 0.06) * math.sin(a),
                        5.98 + 0.38 * t + 0.025 * math.sin(3 * a),
                    )
                )
        mesh(
            'Wool neck wrap',
            vertices,
            [
                (
                    r * 40 + i,
                    r * 40 + (i + 1) % 40,
                    (r + 1) * 40 + (i + 1) % 40,
                    (r + 1) * 40 + i,
                )
                for r in range(5)
                for i in range(40)
            ],
            scarf,
            'head',
        )
        for part, kind, vertices, faces in cloth_bag(0.50, 0.35, 0.61):
            mesh(
                'Canvas haversack ' + part,
                [(x + 0.72, y + 0.37, z + 4.23) for x, y, z in vertices],
                faces,
                canvas if kind == 'canvas' else wool,
                'Hip',
            )
        if tag == 'SHL':
            # The wrapped head cloth is the recognisable Arab field item and
            # follows the imported head weights instead of floating in poses.
            fitted_head_cloth(body, mesh, scarf, 'Wrapped Arab head cloth', loose=True)
    bpy.ops.object.select_all(action='DESELECT')
    for obj in gear:
        obj.select_set(True)
        for face in obj.data.polygons:
            face.use_smooth = True
    bpy.context.view_layer.objects.active = gear[0]
    bpy.ops.object.join()
    equipment = bpy.context.object
    equipment.name = tag + '_gear'
    # The respirator and canisters already have closed shells.
    if tag != 'HAZ':
        solid = equipment.modifiers.new('Fabric thickness', 'SOLIDIFY')
        solid.thickness = 0.008
        bpy.ops.object.modifier_apply(modifier=solid.name)
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.smart_project(island_margin=0.015)
    bpy.ops.object.mode_set(mode='OBJECT')
    bake_diffuse(equipment, output / f'{tag}_gear.png', tag + '_gear')
    if tag == 'MON':
        bake_montar_surface(equipment, output)
    for obj, part in ((body, 'body'), (equipment, 'gear')):
        (output / f'{tag}_field_{part}_diffuse.dds').write_bytes(
            (output / f'{tag}_{part}.png').read_bytes()
        )
        for kind in ('normal', 'specular'):
            (output / f'{tag}_field_{part}_{kind}.dds').write_bytes(
                NORMALS[tag].read_bytes()
            )
        bm = bmesh.new()
        bm.from_mesh(obj.data)
        bmesh.ops.triangulate(bm, faces=list(bm.faces))
        bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
        bmesh.ops.delete(
            bm,
            geom=[f for f in bm.faces if f.calc_area() < 1e-12],
            context='FACES_ONLY',
        )
        bm.to_mesh(obj.data)
        bm.free()
        spec = SimpleNamespace(
            shader=['PdxMeshAdvanced'],
            diff=[f'{tag}_field_{part}_diffuse.dds'],
            n=[f'{tag}_field_{part}_normal.dds'],
            spec=[f'{tag}_field_{part}_specular.dds'],
        )
        mat = pdx.create_shader(spec, tag + '_' + part, str(output))
        obj.data.materials.clear()
        obj.data.materials.append(mat)
        for face in obj.data.polygons:
            face.material_index = 0
    bpy.ops.object.select_all(action='DESELECT')
    body.select_set(True)
    equipment.select_set(True)
    path = output / f'{tag}_field.mesh'
    pdx.export_meshfile(str(path), exp_selected=True, exp_locs=False)
    data, donor_data = path.read_bytes(), donor.read_bytes()
    marker = b'[locator\0'
    assert data.count(marker) == donor_data.count(marker) == 1
    path.write_bytes(
        data[: data.index(marker)] + donor_data[donor_data.index(marker) :]
    )
    finalize_mesh(path)
    if tag in ('HAZ', 'MON'):
        bpy.ops.file.pack_all()
    bpy.ops.wm.save_as_mainfile(filepath=str(output / f'{tag}.blend'))


def verify(output, tags, walk=False):
    """Re-import packaged meshes, inspect skin contracts and sample native poses."""
    import bpy
    import inspect
    from mathutils import Matrix, Vector

    sys.path.insert(0, str(Path(__file__).parent))
    sys.path.insert(
        0,
        str(
            Path.home()
            / 'AppData/Roaming/Blender Foundation/Blender/5.2/extensions/user_default'
        ),
    )
    from io_pdx_mesh.pdx_blender import blender_import_export as pdx
    from io_pdx_mesh import pdx_data

    if not hasattr(pdx, "_northern_shader_source"):
        pdx._northern_shader_source = inspect.getsource(pdx.create_shader)
    source = pdx._northern_shader_source
    for line in (
        '    new_shader.shadow_method = "CLIP"',
        '    new_shader.blend_method = "CLIP"',
    ):
        source = source.replace(line, '')
    exec(compile(source, '<Blender material compatibility>', 'exec'), pdx.__dict__)
    report = {}
    for tag in tags:
        donor = pdx_data.read_meshfile(str(CONFIG[tag]))
        donor_bones = next(
            s.find('skeleton')
            for s in donor.find('object')
            if s.find('skeleton') is not None
        )
        path = (
            output / 'package/gfx/models/units/ADISCORD_regulars' / f'{tag}_field.mesh'
        )
        inputs = [path, *sorted(path.parent.glob(f'{tag}_field_*.dds'))]
        input_hashes = {
            source: hashlib.sha256(source.read_bytes()).hexdigest()
            for source in inputs
        }
        tree = pdx_data.read_meshfile(str(path))
        assert [(n.tag, n.attrib) for n in tree.find('locator')] == [
            (n.tag, n.attrib) for n in donor.find('locator')
        ]
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
                assert (
                    len(data.tri) % 3 == 0
                    and min(data.tri) >= 0
                    and max(data.tri) < count
                )
                influences = data.skin.bones[0]
                assert 1 <= influences <= 4
                assert len(data.skin.w) == len(data.skin.ix) == count * influences
                assert all(0 <= i < len(bones) for i in data.skin.ix)
                weighted = set()
                for i in range(count):
                    weights = data.skin.w[i * influences : (i + 1) * influences]
                    indices = data.skin.ix[i * influences : (i + 1) * influences]
                    assert abs(sum(weights) - 1) < 0.001
                    weighted.update(
                        index for index, weight in zip(indices, weights) if weight > 0
                    )
                for index in weighted:
                    bone, original = bones[index], donor_bones[index]
                    assert bone.attrib.get('pa') == original.attrib.get('pa')
                    assert (
                        max(
                            abs(a - b)
                            for a, b in zip(bone.attrib['tx'], original.attrib['tx'])
                        )
                        < 0.001
                    )
                for key in ('diff', 'n', 'spec'):
                    assert (path.parent / getattr(data.material, key)[0]).is_file()
                shapes.append(
                    {
                        'vertices': count,
                        'triangles': len(data.tri) // 3,
                        'bones': len(bones),
                    }
                )
        bpy.ops.wm.read_factory_settings(use_empty=True)
        pdx.import_meshfile(str(path), imp_locs=False)
        scene = bpy.context.scene
        if tag == 'MON':
            # The importer supplies native custom normals but leaves faces flat.
            for obj in (o for o in scene.objects if o.type == 'MESH'):
                for face in obj.data.polygons:
                    face.use_smooth = True
        scene.render.engine = 'CYCLES'
        scene.cycles.samples = 24
        scene.render.resolution_x, scene.render.resolution_y = 650, 800
        scene.render.resolution_percentage = 100
        scene.world = bpy.data.worlds.new('Studio')
        scene.world.use_nodes = True
        scene.world.node_tree.nodes['Background'].inputs[0].default_value = (
            0.16,
            0.19,
            0.23,
            1,
        )
        for mat in bpy.data.materials if tag != 'MON' else ():
            if mat.use_nodes:
                shader = mat.node_tree.nodes.get('Principled BSDF')
                if shader:
                    roughness = shader.inputs['Roughness']
                    if roughness.is_linked:
                        mat.node_tree.links.remove(roughness.links[0])
                    roughness.default_value = 0.85
        if tag == 'MON':
            from build_crimson_sentinel import configure_preview_materials

            configure_preview_materials()
            bpy.ops.file.pack_all()
            bpy.ops.wm.save_as_mainfile(filepath=str(output / 'MON_native.blend'))
        for location, power, size in (
            ((4, -8, 12), 1600, 7),
            ((-6, -1, 8), 950, 6),
            ((2, 5, 11), 1700, 5),
        ):
            bpy.ops.object.light_add(type='AREA', location=location)
            obj = bpy.context.object
            obj.data.energy, obj.data.size = power, size
            obj.rotation_euler = (
                (Vector((0, 0, 4)) - obj.location).to_track_quat('-Z', 'Y').to_euler()
            )
        bpy.ops.object.camera_add(location=(9, -20, 9))
        camera = bpy.context.object
        camera.data.type, camera.data.ortho_scale = 'ORTHO', 8.7
        camera.rotation_euler = (
            (Vector((0, 0, 3.7)) - camera.location).to_track_quat('-Z', 'Y').to_euler()
        )
        scene.camera = camera
        rigs = [obj for obj in scene.objects if obj.type == 'ARMATURE']
        weapons = []
        if tag in ('MON', 'HAZ'):
            for level in (0, 1):
                before = set(scene.objects)
                pdx.import_meshfile(
                    str(ROOT / f'gfx/models/units/ADISCORD_weapons/infantry_{level}.mesh'),
                    imp_mesh=True, imp_skel=False, imp_locs=False,
                )
                imported = [obj for obj in set(scene.objects) - before if obj.type == 'MESH']
                for obj in imported:
                    if tag == 'MON':
                        for face in obj.data.polygons:
                            face.use_smooth = True
                    left = obj.copy()
                    scene.collection.objects.link(left)
                    weapons.extend(((level, obj, 'Right_Hand_node'), (level, left, 'Left_Hand_node')))
            from build_crimson_sentinel import configure_preview_materials

            configure_preview_materials()

        def place_weapons(pose):
            level = 0 if pose.endswith('rifle') else 1
            for tier, obj, bone in weapons:
                obj.hide_render = tier != level
                obj.matrix_world = (
                    rigs[0].matrix_world @ rigs[0].pose.bones[bone].matrix
                    @ Matrix.Scale(0.9 if tier == 0 else 1.0, 4)
                )

        def render_guard_details(pose):
            location = camera.location.copy()
            rotation = camera.rotation_euler.copy()
            scale = camera.data.ortho_scale
            width, height = scene.render.resolution_x, scene.render.resolution_y
            head = rigs[0].pose.bones['head']
            target = (
                rigs[0].matrix_world @ head.matrix @ head.bone.matrix_local.inverted()
                @ Vector((0, 0, 5.95))
            )
            scene.render.resolution_x = scene.render.resolution_y = 850
            camera.data.ortho_scale = 3.5
            for name, offset in (('front', (8, -16, 3)), ('side', (16, -3, 3))):
                camera.location = target + Vector(offset)
                camera.rotation_euler = (
                    (target - camera.location).to_track_quat('-Z', 'Y').to_euler()
                )
                scene.render.filepath = str(output / f'MON_{pose}_detail_{name}.png')
                bpy.ops.render.render(write_still=True)
            camera.location, camera.rotation_euler = location, rotation
            camera.data.ortho_scale = scale
            scene.render.resolution_x, scene.render.resolution_y = width, height

        poses = {}
        for pose in (
            'idle_rifle',
            'moving_rifle',
            'attack_stand_rifle',
            'idle_mg',
            'moving_mg',
            'attack_stand_mg',
        ):
            for rig in rigs:
                rig.animation_data_clear()
            pdx.import_animfile(
                str(GAME / f'gfx/models/units/GER_infantry_{pose}.anim')
            )
            frames = (1, (scene.frame_end + 1) // 2, scene.frame_end)
            for frame in frames:
                scene.frame_set(frame)
                place_weapons(pose)
                graph = bpy.context.evaluated_depsgraph_get()
                for obj in (o for o in scene.objects if o.type == 'MESH'):
                    evaluated = obj.evaluated_get(graph)
                    assert all(
                        math.isfinite(x) for v in evaluated.data.vertices for x in v.co
                    )
                    assert (
                        max(
                            (evaluated.matrix_world @ v.co).length
                            for v in evaluated.data.vertices
                        )
                        < 20
                    )
            poses[pose] = frames
            render_pose = pose in ('idle_rifle', 'moving_rifle') or (
                (tag in RETINUE_STYLES or tag in ('MON', 'HAZ'))
                and pose in ('idle_mg', 'attack_stand_mg')
            )
            if render_pose:
                scene.frame_set(frames[1])
                place_weapons(pose)
                scene.render.filepath = str(output / f'{tag}_{pose}.png')
                bpy.ops.render.render(write_still=True)
                if tag == 'MON' and pose in ('idle_rifle', 'attack_stand_mg'):
                    render_guard_details(pose)
                if pose == 'idle_rifle':
                    bpy.ops.wm.save_as_mainfile(
                        filepath=str(output / f'{tag}_preview.blend')
                    )
                    if tag == 'HAZ':
                        scene.render.resolution_x = 512
                        scene.render.resolution_y = 512
                        scene.render.film_transparent = True
                        head = rigs[0].pose.bones['head']
                        head_transform = (
                            rigs[0].matrix_world @ head.matrix
                            @ head.bone.matrix_local.inverted()
                        )
                        camera.location = head_transform @ Vector((0, -20, 6.68))
                        target = head_transform @ Vector((0, -0.05, 6.60))
                        camera.rotation_euler = (
                            (target - camera.location)
                            .to_track_quat('-Z', 'Y').to_euler()
                        )
                        camera.data.ortho_scale = 1.55
                        scene.render.filepath = str(output / 'HAZ_badge.png')
                        bpy.ops.render.render(write_still=True)
                        scene.render.resolution_x = 650
                        scene.render.resolution_y = 800
                        scene.render.film_transparent = False
                        camera.data.ortho_scale = 8.7
                    camera.location = (-9, 20, 9)
                    camera.rotation_euler = (
                        (Vector((0, 0, 3.7)) - camera.location)
                        .to_track_quat('-Z', 'Y')
                        .to_euler()
                    )
                    scene.render.filepath = str(output / f'{tag}_back.png')
                    bpy.ops.render.render(write_still=True)
                    camera.location = (9, -20, 9)
                    camera.rotation_euler = (
                        (Vector((0, 0, 3.7)) - camera.location)
                        .to_track_quat('-Z', 'Y')
                        .to_euler()
                    )
                elif walk and pose == 'moving_rifle':
                    scene.cycles.samples = 12
                    scene.render.resolution_percentage = 65
                    for index in range(12):
                        scene.frame_set(1 + round(index * (scene.frame_end - 1) / 12))
                        place_weapons(pose)
                        scene.render.filepath = str(
                            output / f'{tag}_walk_{index:02d}.png'
                        )
                        bpy.ops.render.render(write_still=True)
                    scene.cycles.samples = 24
                    scene.render.resolution_percentage = 100
        # A preview validates the imported files, not a package replaced mid-render.
        assert input_hashes == {
            source: hashlib.sha256(source.read_bytes()).hexdigest()
            for source in inputs
        }, tag + ': package changed during verification; re-run --verify'
        report[tag] = {
            'sha256': input_hashes[path],
            'textures': {
                source.name: input_hashes[source]
                for source in inputs if source.suffix == '.dds'
            },
            'shapes': shapes,
            'poses': poses,
        }
    report_path = output / 'verification.json'
    previous = json.loads(report_path.read_text()) if report_path.exists() else {}
    previous.update(report)
    report_path.write_text(json.dumps(previous, indent=2))
    print(json.dumps(report, indent=2))


def package(output, apply=False, check=False, tags=None, assets_only=False):
    import io
    import struct
    from PIL import Image, ImageOps

    tags = tuple(CONFIG) if tags is None else tuple(tags)
    files = {} if assets_only else bindings()
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
                image = Image.merge(
                    'RGBA',
                    tuple(
                        channel.resize(size, Image.Resampling.BOX)
                        for channel in image.split()
                    ),
                )
            else:
                image = image.resize(size, Image.Resampling.LANCZOS)
        header = bytearray(levels[0][:128])
        struct.pack_into(
            '<I', header, 8, struct.unpack_from('<I', header, 8)[0] | 0x20000
        )
        struct.pack_into('<I', header, 28, len(levels))
        struct.pack_into('<I', header, 108, 0x401008)
        return bytes(header) + b''.join(level[128:] for level in levels)

    if 'MON' in tags:
        source = output / 'MON_native.blend'
        if apply:
            assert source.is_file(), 'MON: run --verify before installing the source'
        files[ROOT / 'tools/assets/source/MON_imperial_guard.blend'] = (
            source if source.is_file() else output / 'MON.blend'
        ).read_bytes()
    if 'HAZ' in tags:
        files[ROOT / 'tools/assets/source/ADISCORD_hazard_infantry.blend'] = (
            output / 'HAZ.blend'
        ).read_bytes()
        badge = output / 'HAZ_badge.png'
        if apply:
            assert badge.is_file(), 'HAZ: run --verify to render the unit badge'
        if badge.is_file():
            files[ROOT / 'tools/assets/source/ADISCORD_hazard_infantry.png'] = badge.read_bytes()
    for tag in tags:
        files[dest / f'{tag}_field.mesh'] = (output / f'{tag}_field.mesh').read_bytes()
        for part in ('body', 'gear'):
            files[dest / f'{tag}_field_{part}_diffuse.dds'] = dds(
                Image.open(output / f'{tag}_{part}.png')
            )
            normal = (
                Image.open(NORMALS[tag])
                if part == 'body'
                else Image.new('RGBA', (512, 512), (255, 128, 0, 128))
            )
            if tag == 'HAZ' and part == 'body':
                # UnpackRRxGNormal reads X from green and negates alpha for Y.
                source_normal = Image.open(output / 'HAZ_body_normal.png').convert('RGB')
                red, green, _ = source_normal.split()
                normal = Image.merge('RGBA', (
                    red, red, Image.new('L', red.size, 0), ImageOps.invert(green),
                ))
            files[dest / f'{tag}_field_{part}_normal.dds'] = dds(normal, True)
            specular = Image.new('RGBA', (512, 512), (0, 48, 0, 36))
            if tag == 'MON' and part == 'gear':
                surface = Image.open(output / 'MON_surface.png').convert('RGB')
                strength, metalness, gloss = surface.split()
                specular = Image.merge('RGBA', (
                    Image.new('L', surface.size, 0), strength, metalness, gloss,
                ))
            files[dest / f'{tag}_field_{part}_specular.dds'] = dds(specular, True)
    changed = [
        str(path.relative_to(ROOT))
        for path, content in files.items()
        if not path.exists() or path.read_bytes() != content
    ]
    if apply:
        verified = json.loads((output / 'verification.json').read_text())
        for tag in tags:
            assert (
                verified[tag]['sha256']
                == hashlib.sha256(files[dest / f'{tag}_field.mesh']).hexdigest()
            ), (tag + ': re-run --verify')
            assert len(verified[tag]['textures']) == 6
            for name, digest in verified[tag]['textures'].items():
                assert digest == hashlib.sha256(files[dest / name]).hexdigest(), (
                    name + ': re-run --verify'
                )
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
    parser.add_argument('--assets-only', action='store_true',
                        help='Keep existing entity bindings when replacing an already registered model.')
    parser.add_argument(
        '--tags', nargs='+', choices=tuple(CONFIG), default=tuple(CONFIG)
    )
    parser.add_argument(
        '--walk', action='store_true', help='Render twelve additional walking frames.'
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--build', action='store_true')
    mode.add_argument('--verify', action='store_true')
    mode.add_argument(
        '--finalize',
        action='store_true',
        help='Validate and repair unused skin slots in staged exports.',
    )
    mode.add_argument('--apply', action='store_true')
    mode.add_argument('--check', action='store_true')
    args = parser.parse_args(
        sys.argv[sys.argv.index('--') + 1 :] if '--' in sys.argv else None
    )
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
        package(args.output.resolve(), args.apply, args.check, args.tags, args.assets_only)
