import sys, json, math
from pathlib import Path
import bpy
from mathutils import Vector

ROOT = Path(__file__).parent
sys.path.insert(0, r'C:\Users\Admin\AppData\Roaming\Blender Foundation\Blender\5.2\extensions\user_default')
from io_pdx_mesh.pdx_blender import blender_import_export as pdx
import inspect
source = inspect.getsource(pdx.create_shader)
source = source.replace('    new_shader.shadow_method = "CLIP"', '')
source = source.replace('    new_shader.blend_method = "CLIP"', '')
exec(compile(source, '<Blender 5 material compatibility>', 'exec'), pdx.__dict__)
import_meshfile = pdx.import_meshfile

paths = {
    'STP': r'C:\Users\Admin\Documents\Paradox Interactive\Hearts of Iron IV\mod\A-Discord\gfx\models\units\STP_infantry_hedonist.mesh',
}
report = {}
for label, path in paths.items():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    import_meshfile(path, join_materials=False)
    meshes = [o for o in bpy.context.scene.objects if o.type == 'MESH']
    for o in meshes:
        if any(m.get(pdx.PDX_SHADER)=='Collision' for m in o.data.materials):
            o.hide_render=True
    meshes=[o for o in meshes if not o.hide_render]
    report[label] = {'objects': [dict(name=o.name, vertices=len(o.data.vertices), polygons=len(o.data.polygons), bounds=[list(x) for x in o.bound_box], materials=[m.name for m in o.data.materials]) for o in meshes], 'images': [(im.name,im.filepath) for im in bpy.data.images], 'bones': {o.name:[dict(name=b.name,head=list(b.head_local),tail=list(b.tail_local)) for b in o.data.bones] for o in bpy.data.objects if o.type=='ARMATURE'}}
    for m in bpy.data.materials:
        if m.use_nodes:
            bsdf = next((n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'),None)
            if bsdf:
                for key in ('Normal','Roughness','Metallic','Alpha'):
                    for link in list(bsdf.inputs[key].links): m.node_tree.links.remove(link)
                bsdf.inputs['Roughness'].default_value=.8
                bsdf.inputs['Metallic'].default_value=0
                bsdf.inputs['Alpha'].default_value=1
    coords=[o.matrix_world@Vector(v) for o in meshes for v in o.bound_box]
    low=Vector(tuple(min(v[i] for v in coords) for i in range(3)))
    high=Vector(tuple(max(v[i] for v in coords) for i in range(3)))
    center=(low+high)/2; height=high.z-low.z
    bpy.ops.object.camera_add(location=center+Vector((height*.5,-height*1.5,height*.18)))
    cam=bpy.context.object; cam.rotation_euler=(center-cam.location).to_track_quat('-Z','Y').to_euler(); cam.data.type='ORTHO'; cam.data.ortho_scale=height*1.3
    scene=bpy.context.scene; scene.camera=cam
    for pos,power,size in [((1,-2,3),1000,2),((-2,-1,1.5),700,2),((0,2,3),1200,1.5)]:
        bpy.ops.object.light_add(type='AREA',location=center+Vector(pos)*height)
        light=bpy.context.object; light.data.energy=power*(height/2)**2; light.data.shape='DISK'; light.data.size=size*height
        light.rotation_euler=(center-light.location).to_track_quat('-Z','Y').to_euler()
    scene.world=bpy.data.worlds.new('Studio'); scene.world.color=(.15,.15,.15)
    scene.render.engine='CYCLES'; scene.cycles.samples=24
    scene.render.resolution_x=700; scene.render.resolution_y=850; scene.render.resolution_percentage=100
    scene.view_settings.view_transform='Standard'
    scene.render.filepath=str(ROOT/(label+'.png'))
    bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/(label+'.blend')))
    bpy.ops.render.render(write_still=True)
(ROOT/'inspection.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
