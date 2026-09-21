"""Re-import native tower assets, evaluate both clips, and render a geometry preview."""
import bpy
import hashlib
import json
import math
import sys
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parent
MOD = ROOT.parents[3]
DEST = MOD/'gfx/models/buildings/ADISCORD_unity_tower'
sys.path.insert(0, str(ROOT.parent/'STP_regulars'))
from export_verify import pdx, pdx_data, preview_gloss, validate_mesh
sys.path.insert(0,str(ROOT))
from build_tower import setup_camera, GROUND, DAMAGE_FLOOR
from bake_fire import preview_standard


def geometry(objects):
    graph = bpy.context.evaluated_depsgraph_get()
    points = []
    for obj in objects:
        evaluated = obj.evaluated_get(graph)
        coordinates = np.empty(len(evaluated.data.vertices)*3,dtype=np.float64)
        evaluated.data.vertices.foreach_get('co',coordinates)
        points.append(coordinates.reshape((-1,3)))
    return np.concatenate(points)


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.world = bpy.data.worlds.new('Native tower studio')
    mesh_path = DEST/'ADISCORD_unity_tower_destruction.mesh'
    tree = pdx_data.read_meshfile(str(mesh_path))
    for shape in tree.find('object'):
        for mesh in shape.findall('mesh'):
            material = pdx_data.PDXData(mesh).material
            assert material.shader == ['PdxMeshStandard'], 'standalone actor must not use a unit atlas shader'
    build_report=json.loads((ROOT/'build_report.json').read_text())
    report = {'mesh':validate_mesh(mesh_path,build_report['bones']), 'clips':{},
              'native_runtime':False,'preview':'Re-imported PDX geometry/materials in Cycles; engine particles are not rendered.',
              'hashes':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in DEST.iterdir() if p.is_file()}}
    pdx.import_meshfile(str(mesh_path),join_materials=False)
    objects = [obj for obj in scene.objects if obj.type=='MESH']
    rigs = [obj for obj in scene.objects if obj.type=='ARMATURE']
    assert rigs and len(objects)==len(build_report['mesh'])
    for material in bpy.data.materials:
        if material.use_nodes and material.node_tree.nodes.get('Principled BSDF'):
            preview_standard(material)
    setup_camera(scene)
    scene.cycles.samples=6
    scene.render.resolution_x=560
    scene.render.resolution_y=420
    frames_dir=ROOT/'preview_frames'
    frames_dir.mkdir(exist_ok=True)
    final = None
    baseline = None
    for name,frames in [('collapse',361),('ruins',31)]:
        for rig in rigs:
            rig.animation_data_clear()
        pdx.import_animfile(str(DEST/f'ADISCORD_unity_tower_{name}.anim'))
        row={'frames':frames,'checked_frames':0,'max_height':-1e9,'min_height':1e9}
        for frame in range(1,frames+1):
            scene.frame_set(frame)
            points=geometry(objects)
            if baseline is None:
                baseline=points.copy()
                lower_body=baseline[:,2]<DAMAGE_FLOOR-.5
            assert np.allclose(points[lower_body],baseline[lower_body],atol=2e-4),'intact lower tower moved'
            assert np.isfinite(points).all()
            assert np.max(np.abs(points))<80,(name,frame,'runaway geometry')
            assert points[:,2].min()>GROUND-.35,(name,frame,'below ground',float(points[:,2].min()))
            row['max_height']=max(row['max_height'],float(points[:,2].max()))
            row['min_height']=min(row['min_height'],float(points[:,2].min()))
            row['checked_frames']+=1
            if name=='ruins':
                assert np.allclose(points,final,atol=2e-4),'ruins pose does not match collapsed endpoint'
            elif frame==frames:
                final=points.copy()
                row['settled_max_height']=float(points[:,2].max())
                moved=np.linalg.norm(points-baseline,axis=1)>.01
                upper=baseline[:,2]>15
                assert np.count_nonzero(moved & upper)>50,'upper crown was not damaged'
                assert np.count_nonzero(~moved & upper)>50,'entire upper crown collapsed'
                assert points[moved,2].min()>DAMAGE_FLOOR-.4,'debris penetrated the intact lower body'
                row['moved_vertices']=int(moved.sum())
                row['stationary_lower_vertices']=int(lower_body.sum())
                row['surviving_upper_vertices']=int(np.count_nonzero(~moved & upper))
        report['clips'][name]=row
    assert all(hashlib.sha256((DEST/name).read_bytes()).hexdigest()==value for name,value in report['hashes'].items())
    (ROOT/'verification_report.json').write_text(json.dumps(report,indent=2))
    print('TOWER VERIFY',json.dumps(report['clips']))
    if '--no-render' in sys.argv:
        return
    for rig in rigs:
        rig.animation_data_clear()
    pdx.import_animfile(str(DEST/'ADISCORD_unity_tower_collapse.anim'))
    for frame in range(1,362,6):
        scene.frame_set(frame)
        scene.render.filepath=str(frames_dir/f'{frame:04}.png')
        bpy.ops.render.render(write_still=True)


if __name__=='__main__':
    main()
