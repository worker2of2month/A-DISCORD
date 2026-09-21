"""Inspect native HQ clips and reconstruct their seven accessory attachments offline."""
import argparse
import importlib.util
import json
import math
import re
import sys
from pathlib import Path

import bpy
import numpy as np
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

ROOT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location(
    'infantry_pose_contracts', ROOT.parent / 'infantry_weapons_3d/qa_20260909/verify_factions.py')
poses = importlib.util.module_from_spec(spec)
spec.loader.exec_module(poses)
qa = poses.qa
CONFIG = json.loads((ROOT / 'headquarters.json').read_text())
RENDER_STATES = {'idle', 'notes', 'scout', 'move', 'charge_pistol_shoot', 'support_attack'}


def main(staging, output, labels):
    poses.native_parent_initialization()
    staging = staging.resolve()
    output = output.resolve()
    qa.OUTPUT = output
    output.mkdir(parents=True, exist_ok=True)
    report = {
        'models': {}, 'source_hashes': {},
        'validation': 'Every integer frame: native parent-relative pose, finite bounded body and accessory geometry, attachment visibility.',
        'limitations': ['Native mesh/anim data rendered offline in Blender; no HOI4 runtime or particle-effect validation.'],
    }

    def record(path):
        report['source_hashes'][str(path)] = qa.digest(path)
        return path

    meshes = {}
    entities = {}
    animations = {}
    for path in (qa.GAME / 'gfx/entities/army_headquarters.gfx', qa.GAME / 'gfx/entities/infantry.gfx',
                 staging / 'gfx/entities/ADISCORD_army_headquarters.gfx'):
        meshes.update({qa.scalar(b, 'name'): b for b in qa.blocks(record(path).read_text(), 'pdxmesh')})
    for path in (qa.GAME / 'gfx/entities/units_infantry.asset',
                 qa.GAME / 'gfx/entities/units_army_headquarters.asset',
                 staging / 'gfx/entities/zz_ADISCORD_army_headquarters.asset'):
        entities.update({qa.scalar(b, 'name'): b for b in qa.blocks(record(path).read_text(), 'entity')})
    for path in (qa.GAME / 'gfx/models/units/animation.asset',
                 qa.GAME / 'gfx/models/units/army_headquarters/animation_army_headquarters.asset'):
        animations.update({qa.scalar(b, 'name'): path.parent / qa.scalar(b, 'file')
                           for b in qa.blocks(record(path).read_text(), 'animation')})
    base = entities['ADISCORD_army_headquarters_base_entity']
    attachments = [(qa.scalar(b, 'name'), *re.findall(r'\b([A-Za-z_]\w*)\s*=\s*"([^"]+)"', b)[1])
                   for b in qa.blocks(base, 'attach')]
    assert len(attachments) == 7, attachments

    def resolve(entity):
        block = entities[entity]
        mesh = re.search(r'\bpdxmesh\s*=\s*"([^"]+)"', block)
        scale = re.search(r'\bscale\s*=\s*([\d.]+)', block)
        parent = re.search(r'\bclone\s*=\s*"([^"]+)"', block)
        inherited = resolve(parent[1]) if parent else (None, 1)
        return mesh[1] if mesh else inherited[0], float(scale[1]) if scale else inherited[1]

    for label in labels:
        bpy.ops.wm.read_factory_settings(use_empty=True)
        path = record(staging / f'gfx/models/units/ADISCORD_headquarters/{label}.mesh')
        validation = qa.validate_mesh(path)
        qa.pdx.import_meshfile(str(path), join_materials=False)
        rig = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
        bodies = [o for o in bpy.data.objects if o.type == 'MESH']
        if label == 'VAL_hq':
            shirt = next(o for o in bodies if any(n.type == 'TEX_IMAGE' and n.image and
                'body_diffuse' in n.image.filepath for m in o.data.materials for n in m.node_tree.nodes))
            equipment = next(o for o in bodies if o != shirt)
            back_webbing = [v.index for v in equipment.data.vertices if
                           .3 < abs(v.co.x) < .65 and v.co.y > .2 and 4.7 < v.co.z < 6.5]
            assert back_webbing, 'Missing rear carrier webbing'
        props = []
        for name, node, entity in attachments:
            mesh_id, scale = resolve(entity)
            path = record(qa.GAME / qa.scalar(meshes[mesh_id], 'file'))
            before = set(bpy.data.objects)
            qa.pdx.import_meshfile(str(path), join_materials=False)
            added = set(bpy.data.objects) - before
            pivot = bpy.data.objects.new(name + '_attachment', None)
            bpy.context.scene.collection.objects.link(pivot)
            for obj in added:
                if obj.parent not in added:
                    transform = obj.matrix_world.copy()
                    obj.parent = pivot
                    obj.matrix_parent_inverse = Matrix.Identity(4)
                    obj.matrix_basis = transform
            parts = [o for o in added if o.type == 'MESH' and not any(
                m.get(qa.pdx.PDX_SHADER) == 'Collision' for m in o.data.materials)]
            for obj in added:
                if obj.type == 'MESH' and obj not in parts:
                    obj.hide_render = True
            props.append((name, node, pivot, parts, scale))
        for mat in {m for obj in bpy.data.objects if obj.type == 'MESH' for m in obj.data.materials}:
            qa.preview_gloss(mat)
            for node in mat.node_tree.nodes:
                if node.type == 'TEX_IMAGE' and node.image:
                    record(Path(bpy.path.abspath(node.image.filepath)))
        qa.studio()
        model = {'mesh': validation, 'animations': {}}
        report['models'][label] = model
        bindings = re.findall(r'animation\s*=\s*\{\s*id\s*=\s*"([^"]+)"\s*type\s*=\s*"([^"]+)"',
                              meshes[f'ADISCORD_{label}_mesh'])
        assert len(bindings) == 16, (label, len(bindings))
        for state, animation_id in bindings:
            path = record(animations[animation_id])
            rig.animation_data_clear()
            for bone in rig.pose.bones:
                bone.matrix_basis.identity()
            qa.pdx.import_animfile(str(path))
            frames = bpy.context.scene.frame_end
            result = {'frames': frames, 'checked_frames': 0, 'max_radius': 0,
                      'native_pose_max_error': 0, 'visibility_segments': []}
            model['animations'][state] = result
            previous = None

            def apply_attachments():
                visible = []
                objects = list(bodies)
                for name, node, pivot, parts, scale in props:
                    matrix = rig.pose.bones[node].matrix
                    shown = max(abs(v) for v in matrix.to_scale()) > .001
                    pivot.matrix_world = rig.matrix_world @ matrix @ Matrix.Scale(scale, 4)
                    for obj in parts:
                        obj.hide_render = not shown
                    if shown:
                        visible.append(name)
                        objects.extend(parts)
                bpy.context.view_layer.update()
                return visible, objects

            for frame in range(1, frames + 1):
                bpy.context.scene.frame_set(frame)
                for bone in rig.pose.bones:
                    assert all(math.isfinite(v) for row in bone.matrix for v in row), (label, state, frame, bone.name)
                error = poses.direct_pose_error(rig, path, frame)
                result['native_pose_max_error'] = max(error, result['native_pose_max_error'])
                assert error < .001, (label, state, frame, error)
                visible, objects = apply_attachments()
                if visible != previous:
                    result['visibility_segments'].append({'start': frame, 'active': visible})
                    previous = visible
                for name, points in qa.geometry(objects).items():
                    assert np.isfinite(points).all(), (label, state, frame, name)
                    radius = float(np.linalg.norm(points, axis=1).max())
                    assert radius < 20, (label, state, frame, name, radius)
                    result['max_radius'] = max(radius, result['max_radius'])
                result['checked_frames'] += 1
            if state in RENDER_STATES:
                frame = (frames + 1) // 2
                bpy.context.scene.frame_set(frame)
                visible, objects = apply_attachments()
                result['render'] = qa.render_pose(label, state, frame, objects)
                result['render_attachments'] = visible
                if label == 'VAL_hq':
                    points = qa.geometry([shirt, equipment])
                    surface = BVHTree.FromPolygons([Vector(p) for p in points[shirt.name]],
                                                   [p.vertices for p in shirt.data.polygons])
                    gap = max(surface.find_nearest(Vector(points[equipment.name][i]))[3] for i in back_webbing)
                    result['max_back_webbing_gap'] = gap
                    assert gap < .12, (label, state, 'webbing detached from coat', gap)
            (output / 'headquarters_states_report.json').write_text(json.dumps(report, indent=2))
            print('HQ', label, state, frames, result['native_pose_max_error'], flush=True)
    report['summary'] = {
        'models': len(report['models']),
        'clips': sum(len(m['animations']) for m in report['models'].values()),
        'frames': sum(a['checked_frames'] for m in report['models'].values() for a in m['animations'].values()),
        'renders': sum('render' in a for m in report['models'].values() for a in m['animations'].values()),
        'errors': 0,
    }
    (output / 'headquarters_states_report.json').write_text(json.dumps(report, indent=2))
    print('HQ COMPLETE', report['summary'], flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--staging', type=Path, default=ROOT.parents[3])
    parser.add_argument('--output', type=Path, default=ROOT / 'qa_20260915/headquarters_states')
    parser.add_argument('--labels', nargs='+', choices=CONFIG, default=list(CONFIG))
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else [])
    main(args.staging, args.output, args.labels)
