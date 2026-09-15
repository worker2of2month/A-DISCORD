"""Export the prototype and verify the serialized skin, materials and geometry."""
import bpy, bmesh, sys, inspect, json, math
from pathlib import Path
from types import SimpleNamespace
from mathutils import Vector
ROOT=Path(__file__).parent
sys.path.insert(0,str(ROOT.parent))
from infantry_polish import polish_gear
from preserve_infantry_locators import preserve_locators
sys.path.insert(0,r'C:\Users\Admin\AppData\Roaming\Blender Foundation\Blender\5.2\extensions\user_default')
from io_pdx_mesh.pdx_blender import blender_import_export as pdx
from io_pdx_mesh import pdx_data
source=inspect.getsource(pdx.create_shader).replace('    new_shader.shadow_method = "CLIP"','').replace('    new_shader.blend_method = "CLIP"','')
exec(compile(source,'<Blender 5 material compatibility>','exec'),pdx.__dict__)
bpy.ops.wm.open_mainfile(filepath=str(ROOT/'Shabrat_rebel.blend'))
body=bpy.data.objects['Shabrat_body']; gear=bpy.data.objects['Shabrat_equipment']
polish_gear(gear, militia=True)
scene=bpy.context.scene
for obj,label in ((body,'body'),(gear,'gear')):
    spec=SimpleNamespace(shader=['PdxMeshAdvanced'],diff=[f'Shabrat_{label}_diffuse.dds'],n=[f'Shabrat_{label}_normal.dds'],spec=[f'Shabrat_{label}_specular.dds'])
    mat=pdx.create_shader(spec,'Shabrat_'+label,str(ROOT))
    obj.data.materials.clear();obj.data.materials.append(mat)
    for face in obj.data.polygons:face.material_index=0
    # Clausewitz packs gloss in alpha; the preview shader needs roughness.
    bsdf=mat.node_tree.nodes.get('Principled BSDF')
    rough=bsdf.inputs['Roughness'];link=rough.links[0]
    invert=mat.node_tree.nodes.new('ShaderNodeMath');invert.operation='SUBTRACT';invert.inputs[0].default_value=1
    mat.node_tree.links.new(link.from_socket,invert.inputs[1]);mat.node_tree.links.new(invert.outputs[0],rough)

bpy.ops.object.select_all(action='DESELECT')
for o in (body,gear):o.select_set(True)
for o in scene.objects:
    if o.type=='EMPTY':o.select_set(True)
pdx.export_meshfile(str(ROOT/'STP_shabrat_infantry.mesh'),exp_selected=True)
preserve_locators(ROOT/'STP_shabrat_infantry.mesh')
root=pdx_data.read_meshfile(str(ROOT/'STP_shabrat_infantry.mesh'))
report={'shapes':[]}
for shape in root.find('object'):
    skel=shape.find('skeleton')
    row={'name':shape.tag,'bones':len(skel) if skel is not None else 0,'meshes':[]}
    for m in shape.findall('mesh'):
        d=pdx_data.PDXData(m);skin=d.skin
        count=len(d.p)//3
        assert len(d.n)==len(d.p) and len(d.u0)==count*2
        assert all(math.isfinite(v) for v in d.p+d.n+d.u0)
        assert len(d.tri)%3==0 and min(d.tri)>=0 and max(d.tri)<count
        assert len(skin.w)==count*skin.bones[0]
        sums=[sum(skin.w[i:i+skin.bones[0]]) for i in range(0,len(skin.w),skin.bones[0])]
        assert all(abs(s-1)<.001 for s in sums)
        for key in ('diff','n','spec'):assert (ROOT/getattr(d.material,key)[0]).is_file()
        row['meshes'].append({'vertices':count,'triangles':len(d.tri)//3,'influences':skin.bones[0],'textures':{k:getattr(d.material,k)[0] for k in ('diff','n','spec')}})
    report['shapes'].append(row)
(ROOT/'export_report.json').write_text(json.dumps(report,indent=2))
scene.render.filepath=str(ROOT/'Shabrat_front.png')
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'Shabrat_rebel_export.blend'))
bpy.ops.render.render(write_still=True)
cam=scene.camera;target=Vector((0,-.06,3.67))
cam.location=(-8,18,7.5);cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler()
scene.render.filepath=str(ROOT/'Shabrat_back.png');bpy.ops.render.render(write_still=True)
print(json.dumps(report))
