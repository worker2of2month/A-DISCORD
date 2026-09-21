import bpy,sys,inspect,json
from pathlib import Path
ROOT=Path(__file__).parent
sys.path.insert(0,r'C:\Users\Admin\AppData\Roaming\Blender Foundation\Blender\5.2\extensions\user_default')
from io_pdx_mesh.pdx_blender import blender_import_export as pdx
source=inspect.getsource(pdx.create_shader).replace('    new_shader.shadow_method = "CLIP"','').replace('    new_shader.blend_method = "CLIP"','')
exec(compile(source,'<Blender 5 material compatibility>','exec'),pdx.__dict__)
bpy.ops.wm.open_mainfile(filepath=str(ROOT/'Shabrat_rebel_export.blend'))
for obj in list(bpy.data.objects):
    if obj.type in ('MESH','ARMATURE','EMPTY'):bpy.data.objects.remove(obj,do_unlink=True)
pdx.import_meshfile(str(ROOT.parents[3]/'gfx/models/units/STP_shabrat/STP_shabrat_infantry.mesh'),join_materials=False)
for mat in bpy.data.materials:
    if not mat.use_nodes:continue
    bsdf=mat.node_tree.nodes.get('Principled BSDF')
    if not bsdf or not bsdf.inputs['Roughness'].is_linked:continue
    link=bsdf.inputs['Roughness'].links[0]
    if link.from_node.type!='TEX_IMAGE':continue
    invert=mat.node_tree.nodes.new('ShaderNodeMath');invert.operation='SUBTRACT';invert.inputs[0].default_value=1
    mat.node_tree.links.new(link.from_socket,invert.inputs[1]);mat.node_tree.links.new(invert.outputs[0],bsdf.inputs['Roughness'])
rig=next(o for o in bpy.data.objects if o.type=='ARMATURE')
scene=bpy.context.scene;scene.cycles.samples=20
report={}
for action in ('idle','moving','attack_stand'):
    rig.animation_data_clear()
    path=Path(r'Z:\SteamLibrary\steamapps\common\Hearts of Iron IV\gfx\models\units')/f'GER_infantry_{action}_rifle.anim'
    pdx.import_animfile(str(path))
    frames=[1,(scene.frame_end+1)//2,scene.frame_end]
    report[action]={'frames':scene.frame_end,'sampled':frames}
    for frame in frames:
        scene.frame_set(frame)
        scene.render.filepath=str(ROOT/f'pose_{action}_{frame}.png')
        bpy.ops.render.render(write_still=True)
    if action=='idle':bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'Shabrat_animated.blend'))
(ROOT/'animation_report.json').write_text(json.dumps(report,indent=2))
