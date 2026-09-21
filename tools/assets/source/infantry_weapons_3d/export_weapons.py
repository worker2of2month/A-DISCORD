"""Export and re-import the shared weapon meshes, skins and recoil clips."""
import bpy
import json
import math
import sys
from pathlib import Path
from types import SimpleNamespace
from mathutils import Matrix, Vector

ROOT=Path(__file__).parent
MOD=ROOT.parents[3]
DEST=MOD/'gfx/models/units/ADISCORD_weapons'
REGULARS=ROOT.parent/'STP_regulars'
sys.path.insert(0,str(REGULARS))
from export_verify import pdx, pdx_data, preview_gloss, validate_mesh
sys.path.insert(0,str(ROOT.parent))
from infantry_polish import polish_normals


def validate_weapon(path):
    report=validate_mesh(path,2)
    for shape in pdx_data.read_meshfile(str(path)).find('object'):
        for node in shape.findall('mesh'):
            mesh=pdx_data.PDXData(node)
            assert all(abs(Vector(mesh.n[i:i+3]).length-1)<.001 for i in range(0,len(mesh.n),3)),str(path)+': non-unit normal'
            vertices=[Vector(mesh.p[i:i+3]) for i in range(0,len(mesh.p),3)]
            for a,b,c in zip(mesh.tri[::3],mesh.tri[1::3],mesh.tri[2::3]):
                assert (vertices[b]-vertices[a]).cross(vertices[c]-vertices[a]).length/2>1e-9,str(path)+': bevel sliver'
    return report


def export(level):
    label=f'infantry_{level}'
    bpy.ops.wm.open_mainfile(filepath=str(ROOT/f'{label}.blend'))
    scene=bpy.context.scene
    bpy.context.preferences.filepaths.save_version=0
    scene.frame_set(1)
    obj=bpy.data.objects[label]
    # Tiny bevel remnants destabilize split normals after float32 export.
    polish_normals(obj,minimum_face_area=1e-8)
    spec=SimpleNamespace(shader=['PdxMeshAdvanced'],diff=[label+'_diffuse.dds'],n=[label+'_normal.dds'],spec=[label+'_specular.dds'])
    mat=pdx.create_shader(spec,label,str(ROOT))
    obj.data.materials.clear()
    obj.data.materials.append(mat)
    for face in obj.data.polygons:
        face.material_index=0
    preview_gloss(mat)
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    for item in scene.objects:
        if item.type=='EMPTY':
            item.select_set(True)
    path=ROOT/f'{label}.mesh'
    pdx.export_meshfile(str(path),exp_selected=True)
    report=validate_weapon(path)
    bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/f'{label}_export.blend'))
    scene.render.filepath=str(ROOT/f'{label}.png')
    bpy.ops.render.render(write_still=True)
    (ROOT/f'{label}_export.json').write_text(json.dumps(report,indent=2))


def verify(level):
    label=f'infantry_{level}'
    bpy.ops.wm.open_mainfile(filepath=str(ROOT/f'{label}_export.blend'))
    for obj in list(bpy.data.objects):
        if obj.type in ('MESH','ARMATURE','EMPTY'):
            bpy.data.objects.remove(obj,do_unlink=True)
    pdx.import_meshfile(str(DEST/f'{label}.mesh'))
    for mat in bpy.data.materials:
        if mat.use_nodes and mat.node_tree.nodes.get('Principled BSDF'):
            preview_gloss(mat)
    rig=next(obj for obj in bpy.context.scene.objects if obj.type=='ARMATURE')
    scene=bpy.context.scene
    clips={}
    for suffix in ('support','fire','idle'):
        rig.animation_data_clear()
        pdx.import_animfile(str(DEST/f'{label}_{suffix}.anim'))
        movements={}
        for frame in range(1,80):
            scene.frame_set(frame)
            positions={b.name:list(b.matrix.translation) for b in rig.pose.bones}
            assert all(math.isfinite(x) for p in positions.values() for x in p)
            movements[frame]=positions
        baseline=movements[79]
        active=[frame for frame,positions in movements.items() if positions!=baseline]
        expected=json.loads((ROOT/f'{label}_build.json').read_text())['clips'][suffix]
        assert active==sorted(set(expected['fire_frames']+expected['ejection_frames']))
        assert movements[10]==baseline
        clips[suffix]={'active_frames':active,'frames':79,'restored_at_end':True}
    scene.frame_set(1)
    bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/f'{label}_animated.blend'))
    return {'mesh':validate_weapon(DEST/f'{label}.mesh'),'clips':clips}


def hold_preview(level, body_label):
    bpy.ops.wm.open_mainfile(filepath=str(REGULARS/f'{body_label}_export.blend'))
    for obj in list(bpy.data.objects):
        if obj.type in ('MESH','ARMATURE','EMPTY'):
            bpy.data.objects.remove(obj,do_unlink=True)
    pdx.import_meshfile(str(MOD/f'gfx/models/units/ADISCORD_regulars/{body_label}.mesh'),join_materials=False)
    body_rig=next(obj for obj in bpy.data.objects if obj.type=='ARMATURE')
    previous=set(bpy.data.objects)
    pdx.import_meshfile(str(DEST/f'infantry_{level}.mesh'))
    added=[obj for obj in bpy.data.objects if obj not in previous]
    weapon_rig=next(obj for obj in added if obj.type=='ARMATURE')
    for obj in added:
        if obj.type in ('MESH','EMPTY'):
            local=obj.matrix_world.copy()
            obj.parent=weapon_rig
            obj.matrix_parent_inverse=Matrix.Identity(4)
            obj.matrix_basis=local
    for mat in bpy.data.materials:
        if mat.use_nodes and mat.node_tree.nodes.get('Principled BSDF'):
            preview_gloss(mat)
    scene=bpy.context.scene
    scene.cycles.samples=20
    scene.render.resolution_percentage=85
    report=[]
    game=Path(r'Z:/SteamLibrary/steamapps/common/Hearts of Iron IV/gfx/models/units')
    for action in ('idle','moving','attack_stand'):
        body_rig.animation_data_clear()
        family='rifle' if level==0 else 'mg'
        pdx.import_animfile(str(game/f'GER_infantry_{action}_{family}.anim'))
        frame=(scene.frame_end+1)//2
        scene.frame_set(frame)
        node=max((body_rig.pose.bones[name] for name in ('Right_Hand_node','Left_Hand_node','Root_node_2','mid_back_node')),
                 key=lambda b:max(abs(s) for s in b.matrix.to_scale()))
        scale=1.0 if level==1 or (level==0 and node.name=='mid_back_node') else .9
        weapon_rig.matrix_world=body_rig.matrix_world@node.matrix@Matrix.Scale(scale,4)
        scene.render.filepath=str(ROOT/f'hold_{level}_{action}.png')
        bpy.ops.render.render(write_still=True)
        report.append({'action':action,'family':family,'frame':frame,'attachment':node.name,'scale':scale})
    (ROOT/f'hold_{level}.json').write_text(json.dumps(report,indent=2))


if __name__=='__main__':
    if '--verify' in sys.argv:
        report={str(level):verify(level) for level in range(8)}
        (ROOT/'animation_report.json').write_text(json.dumps(report,indent=2))
    elif '--holds' in sys.argv:
        for level,body in ((0,'STP_party'),(1,'STP_party'),(3,'STS_regular'),(7,'VAL_regular')):
            hold_preview(level,body)
    else:
        for level in range(8):
            export(level)
