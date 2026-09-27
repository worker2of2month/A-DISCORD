"""Prepare and export the authored Crimson Sentinel on the native infantry rig.

Run in Blender with --python and pass --source, --output and --apply after --.
Without --apply, only inspect the source and report the planned triangle budget.
"""

import argparse
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace


def convert_textures(folder):
    import io
    import struct
    import numpy as np
    from PIL import Image

    def dds(image, name):
        levels = []
        while True:
            stream = io.BytesIO()
            image.save(stream, format='DDS', pixel_format='DXT5')
            levels.append(stream.getvalue())
            if image.width == 1 and image.height == 1:
                break
            image = image.resize((max(1, image.width // 2), max(1, image.height // 2)), Image.Resampling.LANCZOS)
        header = bytearray(levels[0][:128])
        struct.pack_into('<I', header, 8, struct.unpack_from('<I', header, 8)[0] | 0x20000)
        struct.pack_into('<I', header, 28, len(levels))
        struct.pack_into('<I', header, 108, 0x401008)
        (folder / name).write_bytes(header + b''.join(level[128:] for level in levels))

    diffuse = np.asarray(Image.open(folder / 'diffuse.png').convert('RGBA')).copy()
    normal = np.asarray(Image.open(folder / 'normal.png').convert('RGBA')).copy()
    orm = np.asarray(Image.open(folder / 'orm.png').convert('RGBA')).copy()
    packed_normal = np.zeros_like(normal)
    packed_normal[:, :, 0] = normal[:, :, 0]
    packed_normal[:, :, 1] = normal[:, :, 0]
    # Native UnpackRRxGNormal decodes X from green and negated Y from alpha.
    packed_normal[:, :, 3] = 255 - normal[:, :, 1]
    red = diffuse[:, :, 0].astype(float)
    green = diffuse[:, :, 1].astype(float)
    blue = diffuse[:, :, 2].astype(float)
    optics = (red > 120) & (red > green * 1.7) & (red > blue * 1.7)
    packed_normal[:, :, 2] = np.where(optics, 210, 0)
    specular = np.zeros_like(normal)
    specular[:, :, 1] = 85
    # Invert the engine's nonlinear metalness remap instead of copying PBR blue.
    metal = orm[:, :, 2].astype(float) / 255.0
    specular[:, :, 2] = np.rint((1.0 - np.sqrt(1.0 - metal)) * 255).astype('uint8')
    specular[:, :, 3] = 255 - orm[:, :, 1]
    dds(Image.fromarray(diffuse), 'VAL_crimson_diffuse.dds')
    dds(Image.fromarray(packed_normal), 'VAL_crimson_normal.dds')
    dds(Image.fromarray(specular), 'VAL_crimson_specular.dds')


if '--textures' in sys.argv:
    convert_textures(Path(sys.argv[sys.argv.index('--textures') + 1]))
    raise SystemExit(0)

import bpy
from mathutils import Quaternion, Vector


ROOT = Path(__file__).resolve().parents[3]
GAME = Path('Z:/SteamLibrary/steamapps/common/Hearts of Iron IV')
ADDON = Path.home() / 'AppData/Local/Temp/io_pdx_mesh_addon'
sys.path.insert(0, str(ADDON))
from io_pdx_mesh.pdx_blender import blender_import_export as pdx
from io_pdx_mesh import pdx_data


def arguments():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--triangles', type=int, default=30000)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--export', action='store_true')
    parser.add_argument('--check', action='store_true')
    return parser.parse_args(sys.argv[sys.argv.index('--') + 1:])


def reset_pose(rig):
    rig.animation_data_clear()
    for bone in rig.pose.bones:
        bone.matrix_basis.identity()
    bpy.context.scene.frame_set(1)
    bpy.context.view_layer.update()


def smoothstep(low, high, value):
    value = max(0.0, min(1.0, (value - low) / (high - low)))
    return value * value * (3.0 - 2.0 * value)


def authored_weights(position):
    x, y, z = position
    side = 'Left' if x > 0 else 'Right'
    x = abs(x)
    upper_body = smoothstep(3.55, 4.15, z)
    head = smoothstep(6.05, 6.30, z)
    head *= 1.0 - smoothstep(0.58, 0.84, x)
    # Rear antenna and power unit follow the spine, including the part above the head.
    backpack = smoothstep(0.12, 0.38, y) * (1.0 - smoothstep(0.65, 0.95, x))
    head *= 1.0 - backpack
    torso = {'Hip': 1.0 - upper_body, 'back_mid': upper_body * (1.0 - head), 'head': upper_body * head}
    arm_boundary = 1.20 - 0.55 * smoothstep(4.40, 5.90, z)
    arm_amount = smoothstep(arm_boundary, arm_boundary + 0.38, x)
    arm_amount *= smoothstep(3.35, 3.65, z) * (1.0 - backpack)
    arm_amount *= 1.0 - smoothstep(5.45, 5.95, z)
    forearm = smoothstep(1.44, 1.87, x)
    hand = smoothstep(2.13, 2.42, x)
    arm = {side + 'Arm': 1.0 - forearm, side + 'ForeArm': forearm * (1.0 - hand), side + 'Hand': forearm * hand}
    weights = {name: weight * (1.0 - arm_amount) for name, weight in torso.items()}
    for name, weight in arm.items():
        weights[name] = weight * arm_amount
    leg_amount = (1.0 - smoothstep(3.12, 3.69, z)) * smoothstep(0.06, 0.32, x) * (1.0 - arm_amount)
    shin = 1.0 - smoothstep(1.93, 2.32, z)
    foot = 1.0 - smoothstep(0.40, 0.78, z)
    leg = {side + 'UpLeg': 1.0 - shin, side + 'Leg': shin * (1.0 - foot), side + 'Foot': shin * foot}
    weights = {name: weight * (1.0 - leg_amount) for name, weight in weights.items()}
    for name, weight in leg.items():
        weights[name] = weight * leg_amount
    return {name: weight for name, weight in weights.items() if weight > 0.0001}


def prepare(source, output, triangle_budget):
    bpy.ops.wm.open_mainfile(filepath=str(source))
    model = next(obj for obj in bpy.context.scene.objects if obj.type == 'MESH')
    model.name = 'VAL_Crimson_Sentinel'
    model.data.name = model.name
    model.data.calc_loop_triangles()
    original_triangles = len(model.data.loop_triangles)
    original_dimensions = tuple(model.dimensions)
    for node in model.data.materials[0].node_tree.nodes:
        if node.type == 'TEX_IMAGE':
            name = {'BASE COLOR': 'diffuse', 'METALLIC ROUGHNESS': 'orm', 'NORMAL MAP': 'normal'}[node.label]
            node.image.filepath_raw = str(output / (name + '.png'))
            node.image.file_format = 'PNG'
            node.image.save()
    pdx.import_meshfile(str(ROOT / 'gfx/models/units/ADISCORD_regulars/VAL_regular.mesh'),
                        imp_mesh=True, imp_skel=True, imp_locs=True)
    rig = next(obj for obj in bpy.context.scene.objects if obj.type == 'ARMATURE')
    donors = [obj for obj in bpy.context.scene.objects if obj.type == 'MESH' and obj != model]
    body = max(donors, key=lambda obj: obj.dimensions.z)
    points = [body.matrix_world @ Vector(corner) for corner in body.bound_box]
    target_height = max(point.z for point in points) - min(point.z for point in points)
    scale = target_height / model.dimensions.z
    bpy.ops.object.select_all(action='DESELECT')
    model.select_set(True)
    bpy.context.view_layer.objects.active = model
    model.scale *= scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    model.location.z -= min((model.matrix_world @ Vector(c)).z for c in model.bound_box)
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    decimate = model.modifiers.new('Map geometry budget', 'DECIMATE')
    decimate.ratio = min(1.0, triangle_budget / original_triangles)
    decimate.use_collapse_triangulate = True
    bpy.ops.object.modifier_apply(modifier=decimate.name)
    # Raise the authored A-pose wrists to the native wrist pivots before binding.
    for vertex in model.data.vertices:
        x, _y, z = vertex.co
        arm = smoothstep(1.15, 2.30, abs(x)) * smoothstep(3.40, 3.75, z)
        vertex.co.z += 0.40 * arm
    for polygon in model.data.polygons:
        polygon.use_smooth = True

    # Imported bone display tails are not anatomical segments; use authored regions.
    groups = {bone.name: model.vertex_groups.new(name=bone.name) for bone in rig.data.bones}
    for vertex in model.data.vertices:
        position = vertex.co
        weights = authored_weights(position)
        weights = dict(sorted(weights.items(), key=lambda pair: pair[1], reverse=True)[:4])
        total = sum(weights.values())
        if total <= 0:
            raise RuntimeError(f'Unweighted vertex {vertex.index}')
        for name, weight in weights.items():
            groups[name].add([vertex.index], weight / total, 'REPLACE')
    armature = model.modifiers.new('Native infantry skin', 'ARMATURE')
    armature.object = rig
    for donor in donors:
        bpy.data.objects.remove(donor, do_unlink=True)
    reset_pose(rig)
    bpy.ops.wm.save_as_mainfile(filepath=str(output / 'Crimson_Sentinel_HOI4.blend'))
    model.data.calc_loop_triangles()
    result = {
        'source': str(source),
        'original_triangles': original_triangles,
        'triangles': len(model.data.loop_triangles),
        'vertices': len(model.data.vertices),
        'original_dimensions': original_dimensions,
        'dimensions': tuple(model.dimensions),
        'scale': scale,
        'bones': len(rig.data.bones),
        'max_influences': max(len(v.groups) for v in model.data.vertices),
    }
    (output / 'inspection.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result))
    return model, rig


def export_native(output, model, rig):
    subprocess.run(['python', str(Path(__file__).resolve()), '--textures', str(output)], check=True)
    shader = pdx.create_shader(SimpleNamespace(
        shader=['PdxMeshAdvanced'], diff=['VAL_crimson_diffuse.dds'],
        n=['VAL_crimson_normal.dds'], spec=['VAL_crimson_specular.dds']),
        'Crimson Sentinel native', str(output))
    model.data.materials.clear()
    model.data.materials.append(shader)
    reset_pose(rig)
    original_skin_export = pdx.get_mesh_skin_info

    def safe_skin(*args, **kwargs):
        skin = original_skin_export(*args, **kwargs)
        if skin:
            stride = skin['bones'][0]
            for start in range(0, len(skin['ix']), stride):
                indices = skin['ix'][start:start + stride]
                valid = next(index for index in indices if index >= 0)
                skin['ix'][start:start + stride] = [valid if index < 0 else index for index in indices]
        return skin

    # The shader reads all four bone indices, including zero-weight slots.
    mesh_path = output / 'VAL_crimson_sentinel.mesh'
    previous_mesh = mesh_path.read_bytes() if mesh_path.is_file() else None
    previous_tree = pdx_data.read_meshfile(str(mesh_path)) if previous_mesh else None
    pdx.get_mesh_skin_info = safe_skin
    try:
        pdx.export_meshfile(str(mesh_path), exp_mesh=True,
                            exp_skel=True, exp_locs=True)
    finally:
        pdx.get_mesh_skin_info = original_skin_export
    if previous_tree is not None and equivalent_mesh(previous_tree, pdx_data.read_meshfile(str(mesh_path))):
        mesh_path.write_bytes(previous_mesh)
    animation_source = GAME / 'gfx/models/units'
    clips = [('idle', 'GER_infantry_moving_mg.anim'), ('move', 'GER_infantry_moving_mg.anim'),
             ('attack', 'GER_infantry_attack_stand_mg.anim'), ('death', 'GER_infantry_death_mg.anim')]
    manifest = []
    for name, source in clips:
        reset_pose(rig)
        pdx.import_animfile(str(animation_source / source))
        if name == 'idle':
            bpy.context.scene.frame_set(1)
            base = {bone.name: bone.matrix_basis.copy() for bone in rig.pose.bones}
            # A stationary stance keeps both boots planted instead of freezing a stride.
            for bone_name in ('Hip', 'LeftUpLeg', 'LeftLeg', 'LeftFoot', 'LeftToeBase',
                              'RightUpLeg', 'RightLeg', 'RightFoot', 'RightToeBase'):
                base[bone_name].identity()
            rig.animation_data_clear()
            bpy.context.scene.frame_end = 121
            for frame in range(1, 122):
                phase = 2.0 * math.pi * (frame - 1) / 120
                for bone in rig.pose.bones:
                    bone.matrix_basis = base[bone.name]
                    if bone.name == 'Hip':
                        bone.location.z += 0.015 * math.sin(phase)
                    if bone.name == 'head':
                        bone.rotation_quaternion = bone.rotation_quaternion @ Quaternion((0, 1, 0), 0.009 * math.sin(phase))
                    for channel in ('location', 'rotation_quaternion', 'scale'):
                        bone.keyframe_insert(data_path=channel, frame=frame, group=bone.name)
        bpy.context.scene.render.fps = 24 if name == 'move' else 30
        bpy.context.view_layer.objects.active = rig
        pdx.export_animfile(str(output / f'VAL_crimson_{name}.anim'), frame_start=1,
                            frame_end=bpy.context.scene.frame_end)
        action = rig.animation_data.action
        action.name = f'VAL_crimson_{name}'
        action.use_fake_user = True
        manifest.append('animation = {\n\tname = "VAL_crimson_' + name + '_animation"\n\tfile = "VAL_crimson_' + name + '.anim"\n}')
    (output / 'VAL_crimson_animations.asset').write_text(
        '# Generated by tools/assets/source/build_crimson_sentinel.py.\n' + '\n\n'.join(manifest) + '\n',
        encoding='utf-8')
    reset_pose(rig)
    configure_preview_materials()
    bpy.ops.file.pack_all()
    bpy.ops.wm.save_as_mainfile(filepath=str(output / 'Crimson_Sentinel_HOI4.blend'))


def equivalent_mesh(first, second):
    # Parallel tangent accumulation can vary by a few float units. Retain the
    # existing binary only if topology, normals, UVs, skin and materials match exactly.
    first_nodes = list(first.iter())
    second_nodes = list(second.iter())
    if len(first_nodes) != len(second_nodes):
        return False
    for left, right in zip(first_nodes, second_nodes):
        if left.tag != right.tag or left.attrib.keys() != right.attrib.keys():
            return False
        for key, values in left.attrib.items():
            other = right.attrib[key]
            if len(values) != len(other):
                return False
            if left.tag == 'mesh' and key == 'ta':
                if any(not math.isclose(a, b, rel_tol=0, abs_tol=1e-5) for a, b in zip(values, other)):
                    return False
            elif values != other:
                return False
    return True


def validate_native(output):
    import struct

    root = pdx_data.read_meshfile(str(output / 'VAL_crimson_sentinel.mesh'))
    node = list(root.find('object'))[0]
    skeleton = node.find('skeleton')
    mesh = node.find('mesh')
    vertices = len(mesh.attrib['p']) // 3
    if not 0 < vertices < 65536:
        raise RuntimeError('Vertex index budget exceeded')
    if len(mesh.attrib['tri']) // 3 > 30000:
        raise RuntimeError('Triangle budget exceeded')
    skin = mesh.find('skin').attrib
    stride = skin['bones'][0]
    for start in range(0, len(skin['ix']), stride):
        if any(index < 0 or index >= len(skeleton) for index in skin['ix'][start:start + stride]):
            raise RuntimeError('Invalid skin index')
        if abs(sum(skin['w'][start:start + stride]) - 1.0) > 1e-5:
            raise RuntimeError('Unnormalised weights')
    for name in ('diffuse', 'normal', 'specular'):
        path = output / f'VAL_crimson_{name}.dds'
        data = path.read_bytes()
        height, width = struct.unpack_from('<II', data, 12)
        mipmaps = struct.unpack_from('<I', data, 28)[0]
        if data[:4] != b'DDS ' or data[84:88] != b'DXT5' or (width, height, mipmaps) != (2048, 2048, 12):
            raise RuntimeError(f'Invalid DDS contract: {path}')
    bone_names = {bone.tag for bone in skeleton}
    for name in ('idle', 'move', 'attack', 'death'):
        animation = pdx_data.read_meshfile(str(output / f'VAL_crimson_{name}.anim'))
        info = animation.find('info')
        if not {bone.tag for bone in info}.issubset(bone_names):
            raise RuntimeError(f'Animation skeleton mismatch: {name}')
    print(json.dumps({'native_validation': 'passed', 'export_vertices': vertices,
                      'triangles': len(mesh.attrib['tri']) // 3, 'bones': len(skeleton),
                      'dds_mip_levels': 12, 'custom_clips': 4}))


def output_hashes(output):
    return {path.name: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(output.glob('VAL_crimson_*')) if path.suffix in {'.mesh', '.dds', '.anim', '.asset'}}


def configure_preview_materials():
    # Match the native shader's Y sign and gloss-to-roughness conversion in Blender.
    for material in bpy.data.materials:
        if not material.use_nodes or not material.get('shader') or material.get('native_preview_corrected'):
            continue
        nodes = material.node_tree.nodes
        links = material.node_tree.links
        for link in list(links):
            normal_y = link.to_node.type == 'COMBINE_COLOR' and link.to_socket.name == 'Green'
            roughness = link.to_node.type == 'BSDF_PRINCIPLED' and link.to_socket.name == 'Roughness'
            if normal_y or roughness:
                source = link.from_socket
                target = link.to_socket
                links.remove(link)
                invert = nodes.new('ShaderNodeMath')
                invert.operation = 'SUBTRACT'
                invert.inputs[0].default_value = 1.0
                links.new(source, invert.inputs[1])
                links.new(invert.outputs[0], target)
        material['native_preview_corrected'] = True


def preview(output, rig):
    scene = bpy.context.scene
    configure_preview_materials()
    scene.render.engine = 'BLENDER_EEVEE_NEXT'
    scene.render.resolution_x = 700
    scene.render.resolution_y = 900
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'PNG'
    scene.world = bpy.data.worlds.new('Inspection studio')
    scene.world.color = (0.12, 0.12, 0.12)
    target = Vector((0, 0, 3.55))
    bpy.ops.object.camera_add(location=(8.2, -16.5, 7.0))
    camera = bpy.context.object
    camera.rotation_euler = (target - camera.location).to_track_quat('-Z', 'Y').to_euler()
    camera.data.type = 'ORTHO'
    camera.data.ortho_scale = 8.3
    scene.camera = camera
    before = set(scene.objects)
    pdx.import_meshfile(str(GAME / 'gfx/models/units/western_european_infantry_weapon_mg.mesh'),
                        imp_mesh=True, imp_skel=False, imp_locs=False)
    weapon = next(obj for obj in set(scene.objects) - before if obj.type == 'MESH')
    second_weapon = weapon.copy()
    scene.collection.objects.link(second_weapon)
    for location, power, size in [((2, -8, 10), 2100, 6), ((-7, -3, 6), 1200, 5), ((3, 5, 10), 1900, 4)]:
        bpy.ops.object.light_add(type='AREA', location=location)
        light = bpy.context.object
        light.data.energy = power
        light.data.size = size
        light.rotation_euler = (target - light.location).to_track_quat('-Z', 'Y').to_euler()
    for name, animation, frame in [('rest', None, 1), ('idle', 'GER_infantry_idle_mg.anim', 40),
                                    ('move', 'GER_infantry_moving_mg.anim', 12),
                                    ('attack', 'GER_infantry_attack_stand_mg.anim', 25),
                                    ('death', 'GER_infantry_death_mg.anim', 40)]:
        reset_pose(rig)
        if animation:
            custom = output / f'VAL_crimson_{name}.anim'
            pdx.import_animfile(str(custom if custom.exists() else GAME / 'gfx/models/units' / animation))
        scene.frame_set(frame)
        for item, bone in [(weapon, 'Right_Hand_node'), (second_weapon, 'Left_Hand_node')]:
            item.hide_render = animation is None
            item.matrix_world = rig.matrix_world @ rig.pose.bones[bone].matrix
        scene.render.filepath = str(output / (name + '.png'))
        bpy.ops.render.render(write_still=True)


def main():
    args = arguments()
    if args.check:
        validate_native(args.output)
        return
    if not args.apply:
        print(json.dumps({'source_exists': args.source.is_file(), 'target_triangles': args.triangles,
                          'output': str(args.output), 'apply': False}))
        return
    args.output.mkdir(parents=True, exist_ok=True)
    model, rig = prepare(args.source, args.output, args.triangles)
    if args.export:
        export_native(args.output, model, rig)
        validate_native(args.output)
        (args.output / 'package_hashes.json').write_text(json.dumps(output_hashes(args.output), indent=2), encoding='utf-8')
        bpy.ops.wm.read_factory_settings(use_empty=True)
        pdx.import_meshfile(str(args.output / 'VAL_crimson_sentinel.mesh'), imp_mesh=True,
                            imp_skel=True, imp_locs=True)
        rig = next(obj for obj in bpy.context.scene.objects if obj.type == 'ARMATURE')
    preview(args.output, rig)


if __name__ == '__main__':
    main()
