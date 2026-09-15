"""Export native .mesh, or re-import the installed files and exercise game poses."""
import bmesh
import bpy
import inspect
import json
import math
import sys
from pathlib import Path
from types import SimpleNamespace
from mathutils import Vector

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT.parent))
from infantry_polish import polish_gear
from preserve_infantry_locators import preserve_locators
MOD = ROOT.parents[3]
DEST = MOD / 'gfx/models/units/ADISCORD_regulars'
GAME = Path(r'Z:/SteamLibrary/steamapps/common/Hearts of Iron IV')
LABELS = ('STP_party', 'STS_regular', 'VAL_regular')
FACTIONS = json.loads((ROOT / 'factions.json').read_text())
LABELS += tuple(FACTIONS)
HEADQUARTERS = json.loads((ROOT / 'headquarters.json').read_text())
LABELS += tuple(HEADQUARTERS)
sys.path.insert(0, str(Path.home() / 'AppData/Roaming/Blender Foundation/Blender/5.2/extensions/user_default'))
from io_pdx_mesh.pdx_blender import blender_import_export as pdx
from io_pdx_mesh import pdx_data

source = inspect.getsource(pdx.create_shader)
for line in ('    new_shader.shadow_method = "CLIP"', '    new_shader.blend_method = "CLIP"'):
    source = source.replace(line, '')
exec(compile(source, '<Blender 5 material compatibility>', 'exec'), pdx.__dict__)


def preview_gloss(mat):
    shader = mat.node_tree.nodes.get('Principled BSDF')
    roughness = shader.inputs['Roughness']
    if not roughness.is_linked or roughness.links[0].from_node.type != 'TEX_IMAGE':
        return
    link = roughness.links[0]
    invert = mat.node_tree.nodes.new('ShaderNodeMath')
    invert.operation = 'SUBTRACT'
    invert.inputs[0].default_value = 1
    mat.node_tree.links.new(link.from_socket, invert.inputs[1])
    mat.node_tree.links.new(invert.outputs[0], roughness)


def validate_mesh(path, expected_bones=33):
    tree = pdx_data.read_meshfile(str(path))
    shapes = []
    for shape in tree.find('object'):
        skeleton = shape.find('skeleton')
        bones = list(skeleton) if skeleton is not None else []
        for mesh in shape.findall('mesh'):
            d = pdx_data.PDXData(mesh)
            count = len(d.p) // 3
            assert 0 < count < 65536
            assert len(d.n) == count * 3 and len(d.u0) == count * 2
            assert all(math.isfinite(x) for x in d.p + d.n + d.u0)
            assert len(d.tri) % 3 == 0 and 0 <= min(d.tri) <= max(d.tri) < count
            influences = d.skin.bones[0]
            assert 1 <= influences <= 4
            assert len(d.skin.w) == len(d.skin.ix) == count * influences
            assert len(bones) == expected_bones
            for i in range(count):
                weights = d.skin.w[i * influences:(i + 1) * influences]
                indices = d.skin.ix[i * influences:(i + 1) * influences]
                assert abs(sum(weights) - 1) < .001
                assert all(0 <= index < len(bones) for index, weight in zip(indices, weights) if weight)
            for key in ('diff', 'n', 'spec'):
                assert (path.parent / getattr(d.material, key)[0]).is_file()
            shapes.append({'name': shape.tag, 'vertices': count, 'triangles': len(d.tri)//3, 'bones': len(bones), 'influences': influences})
    return shapes


def export(label):
    bpy.ops.wm.open_mainfile(filepath=str(ROOT / f'{label}.blend'))
    objects = [bpy.data.objects[label + '_' + part] for part in ('body', 'gear')]
    polish_gear(objects[1])
    for obj, part in zip(objects, ('body', 'gear')):
        if part == 'body':
            bm = bmesh.new()
            bm.from_mesh(obj.data)
            bmesh.ops.triangulate(bm, faces=list(bm.faces))
            bm.to_mesh(obj.data)
            bm.free()
        spec = SimpleNamespace(shader=['PdxMeshAdvanced'], diff=[f'{label}_{part}_diffuse.dds'], n=[f'{label}_{part}_normal.dds'], spec=[f'{label}_{part}_specular.dds'])
        mat = pdx.create_shader(spec, label + '_' + part, str(ROOT))
        obj.data.materials.clear()
        obj.data.materials.append(mat)
        for face in obj.data.polygons:
            face.material_index = 0
        preview_gloss(mat)
    bpy.ops.object.select_all(action='DESELECT')
    for obj in objects:
        obj.select_set(True)
    if label not in FACTIONS and label not in HEADQUARTERS:
        for obj in bpy.context.scene.objects:
            if obj.type == 'EMPTY':
                obj.select_set(True)
    path = ROOT / f'{label}.mesh'
    pdx.export_meshfile(str(path), exp_selected=True, exp_locs=label not in FACTIONS and label not in HEADQUARTERS)
    if label in FACTIONS or label in HEADQUARTERS:
        donor = (GAME/'gfx/models/units/army_headquarters/generic_army_headquarters.mesh' if label in HEADQUARTERS
                 else GAME / f'gfx/models/units/{FACTIONS[label]["donor"]}_infantry.mesh')
        marker = b'[locator\0'
        source, data = donor.read_bytes(), path.read_bytes()
        assert source.count(marker) == data.count(marker) == 1
        donor_tree = pdx_data.read_meshfile(str(donor))
        exported_tree = pdx_data.read_meshfile(str(path))
        assert list(donor_tree)[-1].tag == list(exported_tree)[-1].tag == 'locator'
        donor_bones = next(shape.find('skeleton') for shape in donor_tree.find('object')
                           if shape.find('skeleton') is not None)
        weighted = {index for shape in exported_tree.find('object') for mesh in shape.findall('mesh')
                    for index,weight in zip(mesh.find('skin').attrib['ix'],mesh.find('skin').attrib['w']) if weight > 0}
        for shape in exported_tree.find('object'):
            bones = shape.find('skeleton')
            assert [b.tag for b in bones] == [b.tag for b in donor_bones]
            for index, (bone, original) in enumerate(zip(bones, donor_bones)):
                assert bone.attrib.get('pa') == original.attrib.get('pa')
                # Coordinate conversion introduces only float rounding.
                if index in weighted:
                    error = max(abs(a-b) for a,b in zip(bone.attrib['tx'],original.attrib['tx']))
                    assert error < .001, (label, bone.tag, error)
        prefix = data[:data.index(marker)]
        path.write_bytes(prefix + source[source.index(marker):])
        assert path.read_bytes()[:len(prefix)] == prefix
        result = pdx_data.read_meshfile(str(path)).find('locator')
        assert [(n.tag,n.attrib) for n in result] == [(n.tag,n.attrib) for n in donor_tree.find('locator')]
    else:
        preserve_locators(path)
    report = validate_mesh(path)
    (ROOT / f'{label}_export.json').write_text(json.dumps(report, indent=2))
    bpy.ops.wm.save_as_mainfile(filepath=str(ROOT / f'{label}_export.blend'))
    bpy.context.scene.render.filepath = str(ROOT / f'{label}_front.png')
    bpy.ops.render.render(write_still=True)
    scene = bpy.context.scene
    scene.camera.location = (-8, 18, 7.5)
    scene.camera.rotation_euler = (Vector((0,-.06,3.67))-scene.camera.location).to_track_quat('-Z','Y').to_euler()
    scene.render.filepath = str(ROOT / f'{label}_back.png')
    bpy.ops.render.render(write_still=True)
    print(label, report)


def verify(label):
    bpy.ops.wm.open_mainfile(filepath=str(ROOT / f'{label}_export.blend'))
    for obj in list(bpy.data.objects):
        if obj.type in ('MESH', 'ARMATURE', 'EMPTY'):
            bpy.data.objects.remove(obj, do_unlink=True)
    path = DEST / f'{label}.mesh'
    report = {'mesh': validate_mesh(path), 'animations': {}}
    pdx.import_meshfile(str(path), join_materials=False)
    for mat in bpy.data.materials:
        if mat.use_nodes and mat.node_tree.nodes.get('Principled BSDF'):
            preview_gloss(mat)
    rigs = [obj for obj in bpy.data.objects if obj.type == 'ARMATURE']
    scene = bpy.context.scene
    scene.cycles.samples = 16
    scene.render.resolution_percentage = 75
    for action in ('idle', 'moving', 'attack_stand'):
        for rig in rigs:
            rig.animation_data_clear()
        animpath = GAME / f'gfx/models/units/GER_infantry_{action}_rifle.anim'
        pdx.import_animfile(str(animpath))
        frames = (1, (scene.frame_end + 1)//2, scene.frame_end)
        report['animations'][action] = {'frames': scene.frame_end, 'sampled': frames}
        for frame in frames:
            scene.frame_set(frame)
            depsgraph = bpy.context.evaluated_depsgraph_get()
            for obj in [o for o in scene.objects if o.type == 'MESH']:
                evaluated = obj.evaluated_get(depsgraph)
                points = [evaluated.matrix_world @ v.co for v in evaluated.data.vertices]
                assert all(math.isfinite(x) for p in points for x in p)
                assert max(p.length for p in points) < 20, (label, action, frame, obj.name)
            scene.render.filepath = str(ROOT / f'{label}_{action}_{frame}.png')
            bpy.ops.render.render(write_still=True)
        if action == 'idle':
            bpy.ops.wm.save_as_mainfile(filepath=str(ROOT / f'{label}_animated.blend'))
    (ROOT / f'{label}_animation.json').write_text(json.dumps(report, indent=2))
    print(label, 'native re-import and 9 pose samples passed')


if __name__ == '__main__':
    verify_mode = '--verify' in sys.argv
    requested = [arg for arg in sys.argv[sys.argv.index('--')+1:] if not arg.startswith('--')] if '--' in sys.argv else []
    assert all(label in LABELS for label in requested), requested
    selected = requested or LABELS
    if verify_mode and any(label in HEADQUARTERS for label in selected):
        # Share the compatibility-patched importer with the full HQ pose validator.
        sys.modules['export_verify'] = sys.modules[__name__]
        from verify_headquarters import main as verify_hq
        verify_hq(MOD, ROOT / 'qa_20260915/headquarters_states',
                  [label for label in selected if label in HEADQUARTERS])
        selected = [label for label in selected if label not in HEADQUARTERS]
    for label in selected:
        (verify if verify_mode else export)(label)
